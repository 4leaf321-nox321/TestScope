"""제조사 카탈로그(`source/catalog`)를 장비 카탈로그로 들인다.

    1. 온톨로지     제조사 · 분류(트리) · 시험 항목 · 물성(properties.json) · 시험법
    2. 사양 정의    빈도로 승격한 것(catalog_specs.py). 나머지는 보류로 보고만
    2-b. 대표 사양  분류가 목록에서 무엇으로 갈리나(categories.json)
    3. 계열         무슨 시험이 되나 · 누가 만들었나
    4. 기종         수치 사양. 보유 장비가 가리키는 것
    5. 관계         부속 호환 · 계보
    6. 물성↔시험 항목  어떤 시험으로 어떤 물성을 얻나(property_links.json + 객체의 measurands)

**순서를 지키는 이유는 하나뿐이다** — 앞 단계가 없으면 뒷 단계가 빈 값으로 들어가고,
빈 값은 나중에 안 채워진다.

    python scripts/import_catalog.py --dry-run    무엇이 들어갈지만 본다
    python scripts/import_catalog.py

단계의 코드는 `catalog_import/` 패키지에 단계마다 한 모듈로 있다 — 여기는 순서와 요약뿐이다.
한 파일이 2,051줄이 되어 한 단계를 고치려면 전부를 읽어야 했다(2026-09-13 에 갈랐다).

## 멱등하다

id 가 아니라 (제조사, 이름) 비교키로 찾는다. 여러 번 돌려도 같은 줄이 둘로 늘지
않는다. 이미 있는 값은 **안 덮는다** — 손으로 고쳐 둔 것이 사양서보다 정확하다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.jobs import kinds, queue
from app.modules.accounts.models import User
from app.modules.review import services as review
from app.modules.server import catalog_state
from app.shared.audit import record
from catalog_import import terms as terms_step
from catalog_import import values as values_step
from catalog_import.definitions import step_definitions, step_headlines
from catalog_import.methods import step_methods, step_promote_pending
from catalog_import.models import step_models
from catalog_import.properties import proposed_links, step_property_links, step_property_terms
from catalog_import.series import step_relations, step_series
from catalog_import.source import DEFAULT_ROOT, PROMOTE_THRESHOLD, Catalog
from catalog_import.terms import _term, step_ontology, step_slug_axes
from catalog_import.values import _value_fields

survive_cp949()

# 다른 스크립트·시험이 여기서 가져다 쓰는 이름. 갈라 놓은 뒤에도 문은 하나다.
__all__ = ["DEFAULT_ROOT", "Catalog", "_term", "_value_fields", "main", "proposed_links"]


def main() -> int:
    parser = argparse.ArgumentParser(description="제조사 카탈로그를 장비 카탈로그로 들인다")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--dry-run", action="store_true", help="무엇이 들어갈지만 보고 되돌린다"
    )
    args = parser.parse_args()

    if not (args.root / "equipment").exists():
        print(f"카탈로그가 없습니다: {args.root}")
        return 1
    cat = Catalog(args.root)

    db = SessionLocal()
    try:
        actor = db.scalar(select(User).where(User.is_system_admin.is_(True)))

        makers, categories, items = step_ontology(db, cat, actor)
        properties, aliases = step_property_terms(db, cat, actor)
        methods = step_methods(db, cat, items, actor)
        definitions, pending = step_definitions(db, cat, categories)
        headlines, unknown_headlines = step_headlines(db, cat, categories)
        form_factors, drives = step_slug_axes(db, cat, actor)
        series, test_items, pending_methods = step_series(
            db, cat, makers, categories, items, methods, form_factors, drives, actor
        )
        promoted_methods = step_promote_pending(db)
        models, values, flagged, kept = step_models(db, cat, series, form_factors, actor)
        relations = step_relations(db, cat, series)
        links, promoted, unmapped = step_property_links(db, cat, items, properties, actor)
        # 7. 검토함 — 반입이 못 정한 것을 후보·추천과 함께 세운다. 정본(`proposals/`)에
        #    이미 내린 결정은 여기서 적용된다 — 개발 DB 에서 정한 것이 운영에 다시 묻지 않게.
        review_open = review.refresh(db, args.root / "proposals")

        if args.dry_run:
            db.rollback()
            print("(dry-run — 되돌렸습니다)")
        else:
            # **반입했다는 사실을 남긴다.** 서버 화면이 정본의 지문과 이것을 견줘
            # 「반입이 정본보다 뒤짐」 을 말한다 — 안 남기면 반입을 안 돌린 설치와
            # 돌린 설치가 화면에서 구별되지 않는다.
            source = catalog_state.fingerprint(args.root)
            record(
                db,
                action=catalog_state.IMPORTED_ACTION,
                actor=actor,
                target_table="catalog",
                target_id=None,
                target_label=f"카탈로그 {len(cat.objects)} 객체",
                changes={
                    "digest": source.digest if source else None,
                    "objects": len(cat.objects),
                    "series": len(series),
                    "models_added": models,
                    "values_added": values,
                },
                reason="scripts/import_catalog.py",
            )
            # 카탈로그가 바뀌었으니 의미 검색 카드도 다시 만든다 — 워커가 한다(꺼져 있으면
            # 워커가 조용히 넘어간다). 같은 커밋에 넣어 「반입은 됐는데 색인 작업은 안 들어간」
            # 상태를 안 만든다.
            queue.enqueue_unless_pending(db, kind=kinds.SEARCH_REINDEX, max_attempts=1)
            db.commit()

        print(f"객체 {len(cat.objects)}건에서:")
        print(f"  제조사 {len(makers)} · 분류 {len(categories)} · 시험 항목 {len(items)}")
        print(
            f"  물성 {len(properties)} (별칭 새로 {aliases})"
            f" · 물성↔시험 항목 연결 새로 {links} · 확인으로 올림 {promoted}"
        )
        print(f"  시험법 {len(methods)}")
        print(f"  사양 정의 새로 {definitions}")
        print(
            f"  분류 대표 사양 {headlines} · 기종 형태 {len(form_factors)}"
            f" · 구동 방식 {len(drives)}"
        )
        print(
            f"  계열 {len(series)} · 계열의 시험 항목 새로 {test_items}"
            f" · 항목 미정 인용 새로 {pending_methods}"
            f" · 미정에서 링크로 올림 {promoted_methods}"
        )
        print(
            f"  기종 새로 {models} · 사양값 새로 {values}"
            f" · 이 기종만의 사양 새로 {values_step._FREE_MADE}"
        )
        if kept:
            print(f"  원문 보존 {kept}건 (정의가 없는 값도 통째로 남는다)")
        if flagged:
            print(f"  원본 확인 필요로 표시한 기종 {flagged}")
        print(f"  계열 관계 새로 {relations}")
        print(
            "  검토함 열림: "
            + " · ".join(f"{review.QUEUES[k].label} {n}" for k, n in review_open.items())
        )
        if unmapped:
            # **물성 키를 못 정한 measurand.** 판정·곡선·설비값이라 물성이 아닌 것이
            # 대부분이고, 물성인데 MaterialTwin 에 키가 없는 것도 있다.
            # property_links.json 에 적어야 사라진다.
            print(
                f"\n물성 키로 못 이은 measurand {len(unmapped)}종"
                " (property_links.json 에 없음):"
            )
            for line in unmapped[:30]:
                print(f"    {line}")
        # 단계 모듈의 상태를 읽는다 — 이름을 가져오면 임포트 시점의 값(빈 것)을 든다.
        if terms_step._CODE_CLASHES:
            # 온톨로지가 두 id 에 같은 이름을 줬다. 한 값에 코드 둘이 올 수 없어 앞의 것이
            # 이겼고, 뒤의 id 로 만든 객체는 **앞의 값**을 가리킨다 — 이름을 갈라야 한다.
            print(
                f"\n같은 이름을 쓰는 온톨로지 id {len(terms_step._CODE_CLASHES)}건"
                " (이름을 가르세요):"
            )
            for line in terms_step._CODE_CLASHES:
                print(f"    {line}")
        if unknown_headlines:
            # **정의가 없는 대표 사양.** 온톨로지가 가리키는 칸이 이 시스템에 없다는
            # 뜻이라, 그 분류의 목록은 대표 없이 그려진다 — 조용히 두면 아무도 모른다.
            print(f"\n대표 사양인데 정의가 없는 키 {len(unknown_headlines)}건:")
            for category_id, key in unknown_headlines[:20]:
                print(f"    {category_id} -> {key}")
        if pending:
            # **값을 버리는 것이 아니다.** 원본이 그대로 있으니, 정의를 만든 뒤
            # 다시 돌리면 들어온다. 자동으로 만들면 오타가 새 사양이 된다.
            promote = [one for one in pending if one[0] >= PROMOTE_THRESHOLD]
            print(f"\n보류한 사양 키 {len(pending)}종 — 정의가 없어 값은 안 들였습니다.")
            if promote:
                print(f"  {PROMOTE_THRESHOLD}개 이상 객체에 나오는 것 {len(promote)}종:")
                for count, key in promote[:20]:
                    print(f"    {count:3d} {key}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
