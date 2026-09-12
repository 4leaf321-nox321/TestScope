"""6. 물성 — 물성 축의 값과 물성↔시험 항목 연결(property_links.json + measurands).

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import collections
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.accounts.models import User
from app.modules.properties.models import TestItemProperty
from app.modules.vocabulary.models import (
    VocabularyAlias,
    VocabularyTerm,
)
from app.shared.text import clean, compare_key
from catalog_import.source import (
    Catalog,
)
from catalog_import.terms import (
    _axis,
    _term,
)

# ── 물성 ──────────────────────────────────────────────────────────────────────


def step_property_terms(
    db: Session, cat: Catalog, actor: User | None
) -> tuple[dict[str, VocabularyTerm], int]:
    """1-d. 물성 항목을 기준정보 축 `property` 의 값으로 심는다. {key: 값}.

    **key 가 `code` 다.** 한글 이름은 사람이 바꿀 수 있지만 `mechanical.yield_strength` 는
    MatNexus 와 공유하는 이름이라 안 바뀐다 — 반입도 화면도 검색도 code 로 건다.
    기호·단위·도메인은 `attributes` 에 들어가 화면이 그대로 보인다. 별칭(「항복강도」·
    「Rp0.2」·「0.2% proof stress」)은 축 별칭으로 — 사람이 그 말로 쳐도 찾히게.
    """
    if not cat.properties:
        return {}, 0
    axis = _axis(db, "property")
    out: dict[str, VocabularyTerm] = {}
    aliases_added = 0
    known_aliases = {
        row.normalized
        for row in db.scalars(
            select(VocabularyAlias).where(VocabularyAlias.vocabulary_id == axis.id)
        )
    }
    for row in cat.properties:
        key = row["key"]
        found = db.scalar(
            select(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.code == key
            )
        )
        if found is None:
            found = _term(db, axis, row.get("name_ko") or key, actor)
            found.code = key
        # 이름이 바뀌었어도 안 덮는다. 다만 속성이 비어 있으면 채운다 — 처음 심을 때다.
        if not found.attributes:
            found.attributes = {
                k: v
                for k, v in (
                    ("domain", row.get("domain")),
                    ("symbol", row.get("symbol")),
                    ("si_unit", row.get("si_unit")),
                    ("value_type", row.get("value_type")),
                    ("description", row.get("description")),
                    ("test_standard", row.get("test_standard")),
                    ("condition_axes", row.get("condition_axes")),
                )
                if v
            }
        out[key] = found
        for alias in row.get("aliases") or []:
            text = clean(str(alias.get("alias") if isinstance(alias, dict) else alias))
            norm = compare_key(text)
            if not text or norm in known_aliases or norm == found.normalized:
                continue
            db.add(
                VocabularyAlias(
                    vocabulary_id=axis.id, term_id=found.id, value=text, normalized=norm
                )
            )
            known_aliases.add(norm)
            aliases_added += 1
    db.flush()
    return out, aliases_added


def _link_targets(
    links: dict[str, Any], item_id: str, measurand: str
) -> list[tuple[str, str | None]]:
    """measurand id -> [(물성 키, 단서)]. 이미 물성 키(점이 있다)면 그대로.

    `overrides` 가 `measurands` 보다 먼저다 — `impact_strength` 는 샤르피와 아이조드가
    다른 키다. null 로 적힌 것은 **일부러 안 잇는 것**이라 비어 있는 것과 다르다.
    """
    if "." in measurand:
        return [(measurand, None)]
    overrides = links.get("overrides") or {}
    scoped = f"{item_id}:{measurand}"
    if scoped in overrides:
        target = overrides[scoped]
    else:
        table = links.get("measurands") or {}
        if measurand not in table:
            return [("?", None)]
        target = table[measurand]
    if target is None:
        return []
    if isinstance(target, list):
        return [(str(one), None) for one in target]
    return [(str(target), None)]


def proposed_links(
    cat: Catalog, *, known_items: set[str], known_keys: set[str]
) -> tuple[dict[tuple[str, str], tuple[str, str | None]], collections.Counter[str]]:
    """반입이 제안할 (시험 항목 id, 물성 키) -> (출처, 단서).

    **되돌리기 스크립트도 이것을 쓴다** — 두 곳이 제각기 세면 「지운 것」 이 어느 쪽
    기준인지 알 수 없다.

    세 곳에서 온다.

        test_items.json 의 measurands   시험 항목마다 사람이 적은 「얻는 것」      ontology
        property_links.json 의 extras    measurand 로는 안 나오지만 그 시험이 내는 것  ontology
        객체의 measurands_by_item        MaterialTwin 능력행 (기종·물성·기법)      materialtwin
        객체의 measurands (시험이 하나일 때만)                                    ontology

    객체 수준 `measurands` 는 시험이 여럿이면 어느 시험의 것인지 말하지 못한다 —
    만능시험기의 「인장강도·압축강도·굽힘강도」 를 인장·압축·굽힘 셋에 다 걸면 「굽힘으로
    인장강도」 가 된다. 그래서 시험이 하나인 객체에서만 쓴다.

    `rejected` 에 적힌 짝은 뺀다 — 사람이 화면에서 지운 것이고, 되돌리기가 정본에 적었다.
    """
    links = cat.property_links
    wanted: dict[tuple[str, str], tuple[str, str | None]] = {}
    unmapped: collections.Counter[str] = collections.Counter()
    rejected = set(links.get("rejected") or [])

    def want(item_id: str, key: str, source: str, note: str | None) -> None:
        if item_id not in known_items or key not in known_keys:
            if key != "?" and key not in known_keys:
                unmapped[f"물성 키 없음 {key}"] += 1
            return
        if f"{item_id}:{key}" in rejected:
            return
        have = wanted.get((item_id, key))
        # 단서가 있는 쪽이 이긴다 — 「영률: 신율계 필요」 를 이름만 있는 줄이 덮으면
        # 그 조건은 아무 데도 안 남는다.
        if have is None or (note and not have[1]):
            wanted[(item_id, key)] = (source, note)

    def from_measurand(item_id: str, measurand: str, source: str) -> None:
        for key, note in _link_targets(links, item_id, measurand):
            if key == "?":
                unmapped[measurand] += 1
                continue
            want(item_id, key, source, note)

    for row in cat.test_items:
        for measurand in row.get("measurands") or []:
            from_measurand(row["id"], str(measurand), "ontology")
    for item_id, extras in (links.get("extras") or {}).items():
        for one in extras:
            if isinstance(one, dict):
                want(item_id, str(one["key"]), "ontology", one.get("note"))
            else:
                want(item_id, str(one), "ontology", None)
    for obj in cat.objects:
        for item_id, keys in (obj.get("measurands_by_item") or {}).items():
            for key in keys:
                from_measurand(item_id, str(key), "materialtwin")
        if len(obj.get("test_items") or []) == 1:
            for measurand in obj.get("measurands") or []:
                from_measurand(obj["test_items"][0], str(measurand), "ontology")
    return wanted, unmapped


def step_property_links(
    db: Session,
    cat: Catalog,
    items: dict[str, VocabularyTerm],
    properties: dict[str, VocabularyTerm],
    actor: User | None,
) -> tuple[int, int, list[str]]:
    """6. 물성 ↔ 시험 항목. **제안으로 넣는다** — 사람이 화면에서 확인한다.

    확인은 데이터라 운영으로 안 간다. 그래서 정본(`property_links.json`)에 `confirmed`
    목록을 둔다 — 되돌리기 스크립트(`export_property_links.py`)가 개발에서 확인한 것을 거기
    적고, 반입은 그 짝을 **확인된 채로** 넣거나 이미 있는 제안을 확인으로 올린다.
    사람이 확인한 것을 다른 서버에서 또 확인하게 하지 않는다.

    있는 연결의 단서·출처는 안 건드린다 — 화면에서 고친 것이 더 낫다.
    """
    if not properties:
        return 0, 0, []
    wanted, unmapped = proposed_links(cat, known_items=set(items), known_keys=set(properties))
    confirmed = set(cat.property_links.get("confirmed") or [])

    existing = {
        (row.test_item_term_id, row.property_term_id): row
        for row in db.scalars(select(TestItemProperty))
    }
    made = promoted = 0
    now = datetime.now(UTC)
    for (item_id, key), (source, note) in sorted(wanted.items()):
        pair = (items[item_id].id, properties[key].id)
        is_confirmed = f"{item_id}:{key}" in confirmed
        found = existing.get(pair)
        if found is not None:
            if is_confirmed and found.status != "confirmed":
                found.status = "confirmed"
                found.confirmed_at = now
                found.confirmed_by_id = actor.id if actor else None
                promoted += 1
            continue
        db.add(
            TestItemProperty(
                test_item_term_id=pair[0],
                property_term_id=pair[1],
                status="confirmed" if is_confirmed else "suggested",
                source=source,
                note=note,
                created_by_id=actor.id if actor else None,
                confirmed_by_id=actor.id if (actor and is_confirmed) else None,
                confirmed_at=now if is_confirmed else None,
            )
        )
        made += 1
    db.flush()
    report = [f"{count:3d} {name}" for name, count in unmapped.most_common()]
    return made, promoted, report
