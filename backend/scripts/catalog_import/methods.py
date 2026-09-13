"""1-b. 시험법 — 규격을 만들고, 항목 미정 인용을 정해지는 순간 링크로 올린다.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.accounts.models import User
from app.modules.methods.models import TestMethod
from app.modules.test_items.models import (
    SeriesPendingMethod,
)
from app.modules.vocabulary.models import (
    VocabularyTerm,
)
from app.shared.text import method_key
from catalog_import.source import (
    Catalog,
)
from catalog_import.terms import (
    _axis,
    _term,
)


def step_methods(
    db: Session, cat: Catalog, items: dict[str, VocabularyTerm], actor: User | None
) -> dict[str, TestMethod]:
    """1-b. 카탈로그가 인용한 시험법을 만든다.

    **판(edition)은 안 적는다.** 카탈로그는 「ASTM D638」 까지만 말하고 어느 판인지는
    말하지 않는다 — 지어내면 그 판으로 시험한 것처럼 읽힌다.

    ## 시험 항목은 온톨로지가 정한다

    객체의 `standards.test_methods` 는 계열에 붙은 **평평한 목록**이라, 그 규격이
    어느 시험 항목의 것인지 말하지 않는다. 거기서 추측하면(예: 그 객체의 첫
    시험 항목) ASTM D638 이 「마찰계수」 가 되는 일이 생긴다.

    대신 `ontology/test_items.json` 의 `typical_standards` 를 쓴다 — 사람이 항목마다
    적어 둔 것이라 근거가 있다. 객체가 `standards.test_methods_by_item` 으로 항목까지
    말하면 그것이 먼저다(MaterialTwin 능력행은 규격을 시험마다 달고 온다). 어디에도
    없는 규격은 **항목을 비워 둔다.** 모르는 것을 비워 두는 편이, 그럴듯한 오답을
    적어 두는 것보다 낫다(ADR 0003).

    ## 표기가 달라도 같은 규격이다

    이미 있는 규격은 `method_key` 로 찾는다 — 「JIS B 0601」 이 있는데 「JIS B0601」 을
    또 만들면 시험법 목록에 같은 규격이 두 줄 서고, 그때부터 어느 쪽에 조건을 적을지
    아무도 모른다.

    ## 제목은 `catalog_extension/standard_titles.json` 에서

    카탈로그는 코드만 말한다. 제목(「Standard Test Method for Tensile Properties of
    Plastics」)은 보강 원료 쪽 도구가 ANSI 웹스토어와 모은 본문에서 찾아 둔 것을 쓴다 —
    없으면 코드가 제목이다. 제목이 코드 그대로인 기존 행도 채운다(사람이 적은 제목은 안
    덮는다).
    """
    titles_path = cat.root.parent / "catalog_extension" / "standard_titles.json"
    titles: dict[str, str] = {}
    if titles_path.exists():
        for code, row in json.loads(titles_path.read_text(encoding="utf-8")).items():
            if row.get("title"):
                titles[method_key(code)] = str(row["title"])
    body_axis = _axis(db, "standard_body")
    methods: dict[str, TestMethod] = {}

    by_standard: dict[str, str] = {}
    for obj in cat.objects:
        by_item = (obj.get("standards") or {}).get("test_methods_by_item") or {}
        for item_id, codes in by_item.items():
            for code in codes:
                by_standard.setdefault(method_key(str(code)), item_id)
    for row in cat.test_items:
        for code in row.get("typical_standards") or []:
            by_standard.setdefault(method_key(str(code)), row["id"])
    # 시험이 **하나뿐인** 객체가 인용한 규격은 그 시험의 것이다 — 추측이 아니라 소거다.
    # 시험이 여럿인 객체에서는 하지 않는다: 그때가 ASTM D638 이 「마찰계수」 가 되는 자리다.
    for obj in cat.objects:
        if len(obj.get("test_items") or []) != 1:
            continue
        for code in (obj.get("standards") or {}).get("test_methods") or []:
            by_standard.setdefault(method_key(str(code)), obj["test_items"][0])

    seen: dict[str, str | None] = {}
    for obj in cat.objects:
        for code in (obj.get("standards") or {}).get("test_methods") or []:
            key = str(code).strip()
            seen.setdefault(key, by_standard.get(method_key(key)))

    known = {
        method_key(row.code): row
        for row in db.scalars(select(TestMethod).where(TestMethod.deleted_at.is_(None)))
    }
    filled = 0
    titled = 0
    for code, item_id in sorted(seen.items()):
        if not code:
            continue
        found = known.get(method_key(code))
        if found is not None:
            # **빈 칸만 채운다.** 있는 값은 안 덮는다 — 사람이 고른 항목이 더 낫다. 하지만
            # 비어 있던 285 건은 「이 규격이 무슨 시험인가」 를 아무도 안 채우던 자리다.
            if found.test_item_term_id is None and item_id and item_id in items:
                found.test_item_term_id = items[item_id].id
                filled += 1
            if found.title == found.code and method_key(code) in titles:
                found.title = titles[method_key(code)]
                titled += 1
            methods[code] = found
            continue
        # 「ASTM D638」 의 앞 토막이 제정기관이다. 못 알아보면 비워 둔다 —
        # 지어내면 그 기관이 낸 적 없는 규격이 목록에 선다.
        head = code.split()[0].split("/")[0]
        body = _term(db, body_axis, head, actor) if head.isalpha() else None
        item = items.get(item_id or "")
        found = TestMethod(
            code=code,
            title=titles.get(method_key(code), code),
            test_item_term_id=item.id if item else None,
            body_term_id=body.id if body else None,
            summary="제조사 카탈로그에서 인용",
            created_by_id=actor.id if actor else None,
        )
        db.add(found)
        db.flush()
        methods[code] = found
        known[method_key(code)] = found
    if filled:
        print(f"  시험 항목이 비어 있던 시험법 {filled}건에 항목을 채웠습니다")
    if titled:
        print(f"  제목이 코드 그대로던 시험법 {titled}건에 제목을 채웠습니다")
    return methods


def step_promote_pending(db: Session) -> int:
    """3-b. 지난 반입 뒤 사람이 시험 항목을 정한 규격의 미정 인용을 링크로 올린다.

    화면에서 정하면 그 자리에서 올라가지만(`methods.services.update`), MCP·SQL 로 정했거나
    이번 반입의 `step_methods` 가 빈 항목을 채운 경우는 여기서 올린다.
    """
    from app.modules.methods.services import promote_pending

    moved = 0
    for method in db.scalars(
        select(TestMethod)
        .join(SeriesPendingMethod, SeriesPendingMethod.method_id == TestMethod.id)
        .where(TestMethod.test_item_term_id.is_not(None))
        .distinct()
    ):
        moved += promote_pending(db, method)
    return moved
