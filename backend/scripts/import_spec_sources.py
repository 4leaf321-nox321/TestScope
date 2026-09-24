"""제조사 문서 목록을 `spec_sources` 로 들인다.

사양값을 손으로 옮겨 적을 때 **어느 문서 몇 쪽에서 나왔는지** 댈 수 있어야 한다.
없으면 반년 뒤 "이 300 kN 어디서 나왔냐" 를 아무도 답할 수 없고, 카탈로그가
개정돼도 무엇을 다시 봐야 하는지 모른다(ADR 0005).

읽는 것은 `source/catalog/sources.json` — 수집 스크립트가 PDF 를 훑어 만든 목록이다.

    python scripts/import_spec_sources.py
    python scripts/import_spec_sources.py --manifest ../source/catalog/sources.json

## 멱등하다

경로가 열쇠다. 이미 있는 줄은 **해시가 달라졌을 때만** 고친다 — 같은 이름으로 새
판이 들어오는 일이 흔하고, 그때 바뀐 사실이 보여야 그 문서에서 온 값을 다시 볼
대상으로 잡을 수 있다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.equipment.models import SpecSource
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.shared.text import compare_key

survive_cp949()

#: 저장소 뿌리에서 본 기본 위치. 수집 도구가 여기에 만든다.
DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "source" / "catalog" / "sources.json"


def _published_on(raw: str | None) -> date | None:
    """PDF 의 `D:20150508160625+02'00'` 를 날짜로 읽는다.

    **찍힌 날이지 발행일이 아니다.** 그래도 같은 모델의 두 판 중 어느 것이 새
    것인지는 이것으로 갈린다 — 모르는 것보다 낫고, 틀릴 때는 눈에 띄게 틀린다.
    """
    if not raw or not raw.startswith("D:") or len(raw) < 10:
        return None
    try:
        return date(int(raw[2:6]), int(raw[6:8]), int(raw[8:10]))
    except ValueError:
        return None


def _makers(db) -> dict[str, VocabularyTerm]:  # type: ignore[no-untyped-def]
    """제조사 축의 값들을 비교키로 집는다. **없는 것은 안 만든다** —
    온톨로지의 값은 쓰는 사람이 채운다는 규칙이 여기서도 같다."""
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "manufacturer"))
    if axis is None:
        return {}
    return {
        term.normalized: term
        for term in db.scalars(
            select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == axis.id)
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="제조사 문서 목록을 들인다")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"목록이 없습니다: {args.manifest}")
        return 1
    rows = json.loads(args.manifest.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        makers = _makers(db)
        known = {row.path: row for row in db.scalars(select(SpecSource))}

        added = changed = unmatched = 0
        for row in rows:
            path = str(row["file"]).replace("\\", "/")
            maker_slug = path.split("/", 1)[0]
            # 폴더 이름이 제조사 슬러그다: `ametek-lloyd` -> `ametek lloyd`.
            maker = makers.get(compare_key(maker_slug.replace("-", " ")))
            if maker is None:
                unmatched += 1

            found = known.get(path)
            if found is None:
                db.add(
                    SpecSource(
                        path=path,
                        title=row.get("title") or None,
                        maker_term_id=maker.id if maker else None,
                        sha256=row.get("sha256"),
                        pages=row.get("pages"),
                        published_on=_published_on(row.get("creation_date")),
                    )
                )
                added += 1
                continue

            # **해시가 바뀐 것만 고친다.** 매번 덮으면 무엇이 새 판인지 안 보인다.
            if found.sha256 and row.get("sha256") and found.sha256 != row["sha256"]:
                found.sha256 = row["sha256"]
                found.pages = row.get("pages")
                found.published_on = _published_on(row.get("creation_date"))
                changed += 1

        db.commit()
        print(f"사양 출처: 새로 {added}건, 개정 {changed}건 (전체 {len(rows)}건)")
        if unmatched:
            # 제조사 축에 그 이름이 아직 없다는 뜻이다. 값을 여기서 만들지 않는
            # 것은 규칙이라, 나중에 축을 채우고 다시 돌리면 이어진다.
            print(f"  제조사를 못 찾은 문서 {unmatched}건 — 제조사 축을 채운 뒤 다시 돌리세요")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
