"""2. 사양 정의 — 손 정의와 온톨로지 승격, 분류 붙이기, 대표 사양.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import collections
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.vocabulary.catalog_specs import (
    CATALOG_SPEC_DEFINITIONS,
    CATEGORY_SPREAD,
    DIMENSION_GROUPS,
    DIMENSION_SOURCES,
    FALLBACK_GROUP,
    MAX_ONLY_SOURCES,
    MIN_HINTS,
    OPTION_RANGE_SOURCES,
    PROMOTE_MIN_OBJECTS,
    RANGE_PAIR_SOURCES,
    SOURCE_SPEC_MAP,
    TEMPERATURE_PAIR,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    VocabularyTerm,
)
from app.modules.vocabulary.reference import SPEC_DEFINITION_LINKS
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from catalog_import.source import (
    Catalog,
    _key_shape,
    _ontology,
    _ontology_map,
    _variant_of,
)


def _alias_targets(db: Session, cat: Catalog) -> dict[str, tuple[str, float]]:
    """온톨로지의 별칭·단위 변형을 **우리 정의 이름**으로 옮긴다.

    온톨로지는 자기 키(`force_kN`)로 말하고 우리 정의는 다른 이름(`force_capacity`)
    을 쓴다. 그 사이를 잇는 것이 손 매핑표이므로, 별칭이 가리키는 대표 키를 한 번 더
    통과시킨다 — 안 그러면 별칭은 있는데 갈 곳이 없다.
    """
    promoted = {row["source_key"]: row["key"] for row in _promotable(cat)}
    out: dict[str, tuple[str, float]] = {}
    for source_key, (base, factor) in _ontology_map(cat).items():
        target = SOURCE_SPEC_MAP.get(base)
        if target is not None:
            out[source_key] = (target[0], factor * target[1])
        elif base in promoted:
            out[source_key] = (promoted[base], factor)
    return out


def _promotable(cat: Catalog) -> list[dict[str, Any]]:
    """온톨로지에서 승격할 키들. **흔한 것부터, 이미 있는 것은 빼고.**"""
    # 서술·비사양은 정의로 세우지 않는다 — 값은 원문에 그대로 남는다.
    onto = {
        row["key"]: row
        for row in _ontology(cat)["keys"]
        if (row.get("role") or "measure") == "measure"
    }
    per_object: collections.Counter[str] = collections.Counter()
    for obj in cat.objects:
        seen = set(obj.get("limits") or {})
        for model in obj.get("models") or []:
            seen |= set(model.get("specs") or {})
        per_object.update(seen)

    # 그 키를 실제로 쓰는 장비 분류들. **온톨로지는 분류를 말하지 않는다** —
    # 데이터가 말한다.
    categories_of: dict[str, set[str]] = {}
    for obj in cat.objects:
        seen = set(obj.get("limits") or {})
        for model in obj.get("models") or []:
            seen |= set(model.get("specs") or {})
        for one in seen:
            categories_of.setdefault(one, set()).add(obj["category"])

    out: list[dict[str, Any]] = []
    for key, count in per_object.most_common():
        if count < PROMOTE_MIN_OBJECTS or key not in onto:
            continue
        # 이미 손으로 이어 둔 키는 건드리지 않는다 — 그 매핑에는 단위 환산 같은
        # 판단이 들어 있다(force_N 은 0.001 을 곱해 kN 이 된다).
        if key in SOURCE_SPEC_MAP or key in DIMENSION_SOURCES:
            continue
        if key in (TEMPERATURE_PAIR[0], TEMPERATURE_PAIR[1]):
            continue
        row = onto[key]
        dimension = row.get("dimension") or ""
        out.append(
            {
                "source_key": key,
                # 정의 key 는 단위 꼬리를 뗀다 — `force_kN` 이 아니라 `force`.
                # 단위는 옆 칸이 갖는다(ADR 0005).
                "key": _definition_key(key, row.get("unit") or ""),
                "label": row.get("label") or key,
                "group": DIMENSION_GROUPS.get(dimension, FALLBACK_GROUP),
                "kind": _key_shape(cat, key),
                "dimension": dimension,
                "unit": row.get("unit") or "",
                "reflect_as": ("min" if any(hint in key for hint in MIN_HINTS) else "max"),
                # 여러 분류에 걸치면 공통으로 둔다 — 「거의 어디나」 는 「어디나」 로
                # 적는 편이 낫다(ADR 0005: 비어 있으면 공통).
                "categories": (
                    sorted(categories_of.get(key, set()))
                    if len(categories_of.get(key, set())) <= CATEGORY_SPREAD
                    else []
                ),
                "count": count,
            }
        )
    return out


def _categories_by_key(cat: Catalog) -> dict[str, set[str]]:
    """원본 키를 실제로 쓰는 장비 분류들.

    **온톨로지는 분류를 말하지 않는다** — 데이터가 말한다.
    """
    out: dict[str, set[str]] = {}
    for obj in cat.objects:
        seen = set(obj.get("limits") or {})
        for model in obj.get("models") or []:
            seen |= set(model.get("specs") or {})
        for key in seen:
            out.setdefault(key, set()).add(obj["category"])
    return out


def _hand_definition_categories(cat: Catalog) -> dict[str, set[str]]:
    """손으로 적은 정의 -> 그 값이 실제로 나오는 분류들.

    ## 왜 손 정의에도 붙이나

    전에는 승격분에만 붙였다. 그래서 손으로 적은 정의 97종이 전부 **공통**이 되어,
    UTM 의 사양 화면에 「정전압 범위(저)」 와 「MFI 하중」 이 함께 떴다 — 그러면
    「사양 추가」 목록은 못 쓰게 된다. 승격분에 분류를 붙인 이유와 똑같은 이유다.

    **여러 분류에 걸치면 공통으로 둔다**(CATEGORY_SPREAD). 무게·전원처럼 어디에나
    있는 것이 실재하고, 그런 것에 분류를 열 개 붙이면 목록만 길어지고 거르는 값은 없다.
    """
    by_key = _categories_by_key(cat)
    out: dict[str, set[str]] = {}
    #: 원본 키 -> 정의 이름. 값이 들어가는 길 전부를 본다.
    routes: dict[str, list[str]] = {}
    for source_key, (target, _factor) in SOURCE_SPEC_MAP.items():
        routes.setdefault(source_key, []).append(target)
    for source_key, target in OPTION_RANGE_SOURCES.items():
        routes.setdefault(source_key, []).append(target)
    for source_key, target in MAX_ONLY_SOURCES.items():
        routes.setdefault(source_key, []).append(target)
    for source_key, pair in RANGE_PAIR_SOURCES.items():
        routes.setdefault(source_key, []).extend(pair)
    for source_key, targets in routes.items():
        for target in targets:
            out.setdefault(target, set()).update(by_key.get(source_key, set()))
    return out


def _definition_key(source_key: str, unit: str) -> str:
    """원본 키에서 사양 정의의 이름을 만든다.

    단위 꼬리를 뗀다(`force_kN` -> `force`). 단위는 정의의 옆 칸이 갖고, 이름에
    박아 두면 나중에 단위를 바꿀 때 **키까지 바꿔야 한다** — 키는 코드와 반입이
    걸고 있어서 못 바꾼다.
    """
    tail = re.sub(r"[^a-z0-9]+", "_", unit.lower()).strip("_")
    name = source_key
    for candidate in (tail, tail.replace("_", ""), source_key.rsplit("_", 1)[-1].lower()):
        if candidate and name.lower().endswith("_" + candidate):
            name = name[: -(len(candidate) + 1)]
            break
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return (name or source_key.lower())[:60]


def step_definitions(
    db: Session, cat: Catalog, categories: dict[str, VocabularyTerm]
) -> tuple[int, list[tuple[int, str]]]:
    """2. 승격한 사양 정의를 심고, 보류 목록을 만든다.

    보류는 **값을 안 들이는 것**이지 버리는 것이 아니다. 원본이 `source/` 에 그대로
    있으니, 정의를 만든 뒤 다시 돌리면 들어온다.
    """
    groups = {row.slug: row for row in db.scalars(select(SpecGroup))}
    if not groups:
        raise SystemExit("사양 그룹이 없습니다. 먼저 scripts/seed_reference.py 를 돌리세요.")
    conditions = {row.key: row for row in db.scalars(select(ConditionKey))}
    known = set(db.scalars(select(SpecDefinition.key)))

    added = 0
    for (
        key,
        label,
        group_slug,
        kind,
        dimension,
        unit,
        condition_key,
        reflect_as,
        order,
        help_text,
    ) in CATALOG_SPEC_DEFINITIONS:
        if key in known:
            continue
        db.add(
            SpecDefinition(
                key=key,
                label=label,
                group_id=groups[group_slug].id,
                kind=kind,
                dimension=dimension,
                si_unit=unit,
                display_unit=unit,
                condition_key_id=(
                    conditions[condition_key].id
                    if condition_key and condition_key in conditions
                    else None
                ),
                reflect_as=reflect_as,
                sort_order=order,
                help=help_text,
            )
        )
        added += 1
    db.flush()
    known |= {row[0] for row in CATALOG_SPEC_DEFINITIONS}

    # **손 정의에도 분류를 붙인다.** 안 붙이면 그 정의는 공통이 되어 모든 장비의
    # 사양 화면에 뜬다 — UTM 에 「정전압 범위」 가 뜨는 목록은 아무도 안 쓴다.
    hand = _hand_definition_categories(cat)
    rows = {row.key: row for row in db.scalars(select(SpecDefinition))}
    for key, names in hand.items():
        definition = rows.get(key)
        if definition is None or not names or len(names) > CATEGORY_SPREAD:
            continue
        terms = [categories[one].id for one in sorted(names) if one in categories]
        if not terms:
            continue
        attached = set(
            db.scalars(
                select(SpecDefinitionCategory.category_term_id).where(
                    SpecDefinitionCategory.definition_id == definition.id
                )
            )
        )
        for term_id in terms:
            if term_id in attached:
                continue
            db.add(
                SpecDefinitionCategory(definition_id=definition.id, category_term_id=term_id)
            )
    db.flush()

    # --- 온톨로지에서 승격 ---------------------------------------------------
    #
    # 손으로 적은 목록만으로는 못 따라간다 — 원본이 커질 때마다 사람이 따라 적어야
    # 하고, 안 적으면 그만큼 조용히 버려진다(실측: 객체가 148 -> 194 로 늘자 커버율이
    # 63% -> 51% 로 떨어졌다).
    #
    # 온톨로지는 사람이 검토한 어휘다. 거기서 올라온 것은 **이름과 단위가 이미
    # 정해진** 키다.
    promoted = 0
    for row in _promotable(cat):
        if row["key"] in known:
            continue
        # 축 연결은 한 표(`SPEC_DEFINITION_LINKS`)가 정한다 — 승격분도 거기 있으면 잇는다.
        # 차원이 같다고 잇지는 않는다: 「공급 전압」 은 전원 사양이지 시험 능력이 아니다.
        linked_key = SPEC_DEFINITION_LINKS.get(row["key"])
        made = SpecDefinition(
            key=row["key"],
            label=row["label"],
            group_id=groups[row["group"]].id,
            kind=row["kind"],
            dimension=row["dimension"],
            si_unit=row["unit"],
            display_unit=row["unit"],
            condition_key_id=(
                conditions[linked_key].id if linked_key and linked_key in conditions else None
            ),
            reflect_as=row["reflect_as"],
            # 승격분은 뒤에 세운다 — 손으로 적은 것이 위에 오는 편이,
            # 화면에서 먼저 보이는 것이 흔한 사양이라 낫다.
            sort_order=900,
            help=f"제조사 카탈로그 {row['count']}건에서 쓰인 사양(`{row['source_key']}`).",
        )
        db.add(made)
        db.flush()
        # **분류를 붙인다.** 안 붙이면 UTM 화면에 배터리 사이클러 사양이 뜨고,
        # 그때 「사양 추가」 목록은 못 쓰게 된다(ADR 0005: 비어 있으면 공통).
        for slug in row["categories"]:
            term = categories.get(slug)
            if term is not None:
                db.add(SpecDefinitionCategory(definition_id=made.id, category_term_id=term.id))
        known.add(row["key"])
        promoted += 1
    added += promoted
    db.flush()

    per_object: collections.Counter[str] = collections.Counter()
    for obj in cat.objects:
        keys = set(obj.get("limits") or {})
        for model in obj.get("models") or []:
            keys |= set(model.get("specs") or {})
        per_object.update(keys)
    # **온톨로지가 아는 것은 보류가 아니다.** 서술(descriptive)과 품번(not_spec)도
    # 등록된 것이고, 값은 원문에 그대로 남는다 — 보류 목록에 두면 아직 할 일이
    # 남은 것처럼 보여서 사람이 그 목록을 안 믿게 된다.
    known_by_ontology = set(_ontology_map(cat))
    for row in _ontology(cat)["keys"]:
        known_by_ontology.add(row["key"])
    promoted_keys = {row["source_key"] for row in _promotable(cat)} | known_by_ontology
    pending = sorted(
        (
            (count, key)
            for key, count in per_object.items()
            if key not in SOURCE_SPEC_MAP
            and key not in DIMENSION_SOURCES
            and key not in RANGE_PAIR_SOURCES
            and key not in OPTION_RANGE_SOURCES
            and key not in MAX_ONLY_SOURCES
            # 고온조·저온조는 「시험 온도」 하나로 합쳐 들인다(_merge_temperature).
            # 들이면서 보류로 세면 그 목록은 영영 안 줄어드는 두 줄을 달고 있게 된다.
            and key not in TEMPERATURE_PAIR
            and key not in promoted_keys
            and key not in ("note", "uncertain")
            and not _variant_of(key)
        ),
        reverse=True,
    )
    return added, pending


def step_headlines(
    db: Session, cat: Catalog, categories: dict[str, VocabularyTerm]
) -> tuple[int, list[tuple[str, str]]]:
    """2-b. 분류의 **대표 사양**을 그 분류 값에 적는다.

    목록 한 줄이 기종을 가르려면 어느 사양을 보여 줄지 알아야 하고, 그 답은 분류마다
    다르다 — 만능시험기는 하중이고 챔버는 온도다. 화면이 정하면 화면마다 갈리고,
    「많이 채워진 것」 으로 자동으로 고르면 데이터가 늘 때 대표가 조용히 바뀐다.
    **정본은 온톨로지의 `headline_specs`** 다.

    정의가 없는 키는 **안 적고 보고한다.** 적어 두면 목록이 빈 칸을 그리는데, 그
    빈 칸은 「값이 아직 없다」 와 구별되지 않는다.
    """
    known = set(db.scalars(select(SpecDefinition.key)))
    unknown: list[tuple[str, str]] = []
    written = 0
    for row in cat.categories:
        term = categories.get(row["id"])
        wanted = list(row.get("headline_specs") or [])
        if term is None or not wanted:
            continue
        unknown.extend((row["id"], key) for key in wanted if key not in known)
        keys = [key for key in wanted if key in known]
        if not keys or term.attributes.get("headline_specs") == keys:
            continue
        # **새 dict 를 넣는다.** JSONB 를 제자리에서 고치면 SQLAlchemy 가 바뀐 줄을
        # 못 보고, 그러면 커밋이 조용히 아무것도 안 쓴다.
        term.attributes = {**term.attributes, "headline_specs": keys}
        written += 1
    db.flush()
    return written, unknown
