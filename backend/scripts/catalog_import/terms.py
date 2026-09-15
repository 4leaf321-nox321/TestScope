"""1. 온톨로지 — 제조사·분류(트리)·시험 항목·형태·구동 방식을 축의 값으로.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.accounts.models import User
from app.modules.vocabulary.models import (
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.shared.text import clean, compare_key
from catalog_import.source import (
    Catalog,
)

#: 온톨로지의 두 id 가 같은 이름을 써서 한 값에 코드 둘이 오려던 것. 끝에 보고한다.
_CODE_CLASHES: list[str] = []


def _term(
    db: Session,
    axis: Vocabulary,
    value: str,
    actor: User | None,
    *,
    parent: VocabularyTerm | None = None,
    code: str | None = None,
) -> VocabularyTerm:
    """기준정보 값을 없으면 만든다. **코드로 먼저, 그다음 비교키로 찾는다.**

    코드(온톨로지 id — `tensile` · `universal_testing_machine` · `instron`)가 있으면 그것으로
    찾는다. 이름으로만 찾으면 관리 화면에서 「인장」 을 「인장 시험」 으로 바꾼 다음 반입이
    「인장」 을 **또 만든다** — 편집을 넓힌 순간부터 실제로 나는 사고다. 기종 형태·구동
    방식이 원본 슬러그로 찾던 것(`_slug_axis`)을 모든 축으로 넓힌 것이다.

    코드 없이 이름으로 찾힌 값에는 코드를 **채운다**(다음부터는 코드로 찾힌다). 다른
    코드가 이미 붙어 있으면 온톨로지 쪽 두 id 가 같은 이름을 쓰는 것이다 — 덮지 않고
    그 값을 쓰되 `_CODE_CLASHES` 에 남겨 끝에 보고한다.

    반입은 값을 만든다. 설치(`reference.py`)가 축만 세우고 값을 안 심는 것과 다른
    일이다 — 137개를 넣으려면 제조사와 분류가 먼저 있어야 하고, 그것을 사람에게
    손으로 시키면 아무도 안 넣는다.
    """
    if code:
        by_code = db.scalar(
            select(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.code == code
            )
        )
        if by_code is not None:
            return by_code
    key = compare_key(value)
    found = db.scalar(
        select(VocabularyTerm).where(
            VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.normalized == key
        )
    )
    if found is not None:
        if code and not found.code:
            found.code = code
        elif code and found.code != code:
            _CODE_CLASHES.append(
                f"{axis.slug}: 「{found.value}」 = {found.code} 인데 {code} 도 같은 이름"
            )
        return found
    found = VocabularyTerm(
        vocabulary_id=axis.id,
        value=clean(value),
        normalized=key,
        code=code,
        parent_term_id=parent.id if parent else None,
        created_by_id=actor.id if actor else None,
    )
    db.add(found)
    db.flush()
    return found


def _axis(db: Session, slug: str) -> Vocabulary:
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
    if axis is None:
        raise SystemExit(
            f"기준정보 축 '{slug}' 가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요."
        )
    return axis


def step_ontology(
    db: Session, cat: Catalog, actor: User | None
) -> tuple[
    dict[str, VocabularyTerm], dict[str, VocabularyTerm], dict[str, VocabularyTerm], int
]:
    """1. 제조사·분류(트리)·시험 항목을 값으로 심는다. 마지막은 새로 넣은 시험 항목 별칭 수."""
    makers_axis = _axis(db, "manufacturer")
    category_axis = _axis(db, "equipment_category")
    item_axis = _axis(db, "test_item")

    makers: dict[str, VocabularyTerm] = {}
    for row in cat.manufacturers:
        label = row.get("label") or row["id"]
        makers[row["id"]] = _term(db, makers_axis, label, actor, code=row["id"])

    # **부모를 먼저 만든다.** 트리라 상위 분류가 있어야 하위가 그것을 가리킨다.
    categories: dict[str, VocabularyTerm] = {}
    pending = list(cat.categories)
    for _ in range(4):  # 깊이는 2 지만 순서가 섞여 있어도 돌게 둔다
        rest = []
        for row in pending:
            parent_id = row.get("parent")
            if parent_id and parent_id not in categories:
                rest.append(row)
                continue
            categories[row["id"]] = _term(
                db,
                category_axis,
                row.get("label_ko") or row.get("label") or row["id"],
                actor,
                parent=categories.get(parent_id) if parent_id else None,
                code=row["id"],
            )
        pending = rest
        if not pending:
            break

    items: dict[str, VocabularyTerm] = {}
    for row in cat.test_items:
        label = row.get("label_ko") or row.get("label") or row["id"]
        items[row["id"]] = _term(db, item_axis, label, actor, code=row["id"])

    # **별칭 — 영문 라벨과 다른 표기.** 사람도 AI 도 「thermal shock」 「HAST」 로 묻는데
    # 값 이름은 한글이라 이름 매칭이 다 빠지고, 그때 resolve 는 벡터 후보로 떨어져 되묻는다.
    # 물성(properties.py)과 같은 규칙: 있는 별칭은 안 덮고, 값 이름과 같은 것은 안 넣는다.
    # 별칭은 화면에서도 더할 수 있으므로 반입은 **더하기만** 한다.
    item_aliases = _test_item_aliases(db, item_axis, cat.test_items, items)

    db.flush()
    return makers, categories, items, item_aliases


def _test_item_aliases(
    db: Session,
    axis: Vocabulary,
    rows: list[dict[str, Any]],
    items: dict[str, VocabularyTerm],
) -> int:
    """`label`(영문)과 `aliases` 를 시험 항목 별칭으로. 더한 수를 돌려준다."""
    known = {
        one.normalized
        for one in db.scalars(
            select(VocabularyAlias).where(VocabularyAlias.vocabulary_id == axis.id)
        )
    }
    added = 0
    for row in rows:
        term = items.get(row["id"])
        if term is None:
            continue
        candidates: list[str] = []
        if row.get("label"):
            candidates.append(str(row["label"]))
        for alias in row.get("aliases") or []:
            candidates.append(str(alias.get("alias") if isinstance(alias, dict) else alias))
        for raw in candidates:
            text = clean(raw)
            norm = compare_key(text)
            if not text or not norm or norm == term.normalized or norm in known:
                continue
            db.add(
                VocabularyAlias(
                    vocabulary_id=axis.id, term_id=term.id, value=text, normalized=norm
                )
            )
            known.add(norm)
            added += 1
    return added


def _slug_axis(
    db: Session,
    axis_slug: str,
    rows: list[dict[str, Any]],
    actor: User | None,
) -> dict[str, uuid.UUID]:
    """원본 슬러그로 도는 축을 심는다. {원본 슬러그: 값 id}.

    **원본 슬러그를 값의 `code` 에 남긴다.** 사람이 이름을 「탁상형」 에서 「벤치탑」 으로
    바꿔도 반입은 code 로 찾으므로 안 깨진다 — 이름으로 찾으면 그날 같은 것이 두 값으로
    갈린다.
    """
    axis = _axis(db, axis_slug)
    out: dict[str, uuid.UUID] = {}
    for row in rows:
        slug = row["id"]
        label = row.get("label_ko") or row.get("label") or slug
        found = db.scalar(
            select(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.code == slug
            )
        )
        if found is None:
            found = _term(db, axis, label, actor)
            found.code = slug
        out[slug] = found.id
    db.flush()
    return out


def step_slug_axes(
    db: Session, cat: Catalog, actor: User | None
) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]:
    """1-c. 원본 슬러그로 도는 축들 — 기종 형태와 구동 방식.

    둘 다 원본이 `benchtop`·`servohydraulic` 처럼 영어 슬러그로 적어 오던 것이다.
    자유 문자열로 두면 화면에 영어가 그대로 뜨고 「유압식만」 으로 거를 수도 없다.
    """
    return (
        _slug_axis(db, "form_factor", cat.form_factors, actor),
        _slug_axis(db, "drive", cat.drives, actor),
    )
