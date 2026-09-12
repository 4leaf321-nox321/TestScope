"""화면에서 확인·지움·손으로 이은 물성 연결을 **정본으로 되돌려 쓴다.**

    python scripts/export_property_links.py            property_links.json 을 고친다
    python scripts/export_property_links.py --check    무엇이 바뀔지만 보인다

## 왜 필요한가

물성 ↔ 시험 항목 연결은 반입이 「제안」 으로 넣고 사람이 화면에서 확인한다. 그 확인은
**DB 행**이라 운영 서버로 안 간다 — 운영에서 카탈로그를 들이면 254 건이 다시 제안으로 서고,
같은 사람이 같은 것을 또 확인해야 한다. 그래서 확인 결과를 정본(`source/catalog/ontology/
property_links.json`)에 적는다. 그 파일은 패키지에 실리고, 반입이 그것을 읽어 확인된 채로
넣는다.

세 가지를 적는다.

    confirmed   화면에서 확인한 짝 — 반입이 confirmed 로 넣는다
    rejected    반입이 제안했을 텐데 DB 에 없는 짝 — 사람이 지운 것. 반입이 다시 안 만든다
    extras      DB 에 있는데 반입이 제안하지 않는 짝 — 손으로 이은 것. extras 에 더한다

## 덮어쓰지 않는다

`confirmed` 와 `rejected` 는 **합집합**이다 — 다른 사람이 다른 서버에서 확인한 것을 지우지
않는다. 같은 짝이 confirmed 였다가 화면에서 지워지면 rejected 로 옮긴다(둘에 다 있을 수 없다).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.properties.models import TestItemProperty
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.shared.text import compare_key
from import_catalog import DEFAULT_ROOT, Catalog, proposed_links

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="물성 연결의 확인 결과를 정본으로 되돌려 쓴다"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--check", action="store_true", help="쓰지 않고 보고만 한다")
    args = parser.parse_args()

    cat = Catalog(args.root)
    path = args.root / "ontology" / "property_links.json"
    links = json.loads(path.read_text(encoding="utf-8"))

    # 시험 항목은 값(한글 이름)으로 심기므로 이름 -> 온톨로지 id 를 되짚는다.
    item_id_of = {
        compare_key(row.get("label_ko") or row.get("label") or row["id"]): row["id"]
        for row in cat.test_items
    }
    known_keys = {row["key"] for row in cat.properties}

    db = SessionLocal()
    try:
        axis = {row.slug: row.id for row in db.scalars(select(Vocabulary))}
        terms = {row.id: row for row in db.scalars(select(VocabularyTerm))}
        in_db: dict[tuple[str, str], TestItemProperty] = {}
        unknown = 0
        for row in db.scalars(select(TestItemProperty)):
            item = terms.get(row.test_item_term_id)
            prop = terms.get(row.property_term_id)
            item_id = item_id_of.get(compare_key(item.value)) if item else None
            key = prop.code if prop and prop.vocabulary_id == axis.get("property") else None
            if item_id is None or key is None or key not in known_keys:
                unknown += 1
                continue
            in_db[(item_id, key)] = row
    finally:
        db.close()

    proposed, _ = proposed_links(
        cat, known_items=set(item_id_of.values()), known_keys=known_keys
    )

    confirmed = set(links.get("confirmed") or [])
    rejected = set(links.get("rejected") or [])
    extras = links.setdefault("extras", {})
    added_extras = 0

    for (item_id, key), row in in_db.items():
        pair = f"{item_id}:{key}"
        if row.status == "confirmed":
            confirmed.add(pair)
            rejected.discard(pair)
        if (item_id, key) not in proposed and key not in {
            (one["key"] if isinstance(one, dict) else one) for one in extras.get(item_id, [])
        }:
            # 손으로 이은 것 — 정본에 없으면 다른 서버에서는 안 생긴다.
            extras.setdefault(item_id, []).append(
                {"key": key, "note": row.note} if row.note else key
            )
            added_extras += 1
    for pair_tuple in proposed:
        pair = f"{pair_tuple[0]}:{pair_tuple[1]}"
        if pair_tuple not in in_db:
            rejected.add(pair)
            confirmed.discard(pair)

    before = (len(links.get("confirmed") or []), len(links.get("rejected") or []))
    links["confirmed"] = sorted(confirmed)
    links["rejected"] = sorted(rejected)
    print(f"DB 연결 {len(in_db)}건 (정본으로 못 되짚은 것 {unknown})")
    print(f"  confirmed {before[0]} -> {len(confirmed)}")
    print(f"  rejected  {before[1]} -> {len(rejected)}")
    print(f"  손으로 이은 것을 extras 에 더함 {added_extras}")
    if args.check:
        print("(--check 였습니다 — 아무것도 쓰지 않았습니다)")
        return 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(links, ensure_ascii=False, indent=1) + "\n")
    print(f"썼습니다: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
