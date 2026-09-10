"""제조사 카탈로그(`source/catalog`)를 장비 카탈로그로 들인다.

    1. 온톨로지     제조사 · 분류(트리) · 시험 항목 · 시험법
    2. 사양 정의    빈도로 승격한 것(catalog_specs.py). 나머지는 보류로 보고만
    3. 계열         무슨 시험이 되나 · 누가 만들었나
    4. 기종         수치 사양. 보유 장비가 가리키는 것
    5. 관계         부속 호환 · 계보

**순서를 지키는 이유는 하나뿐이다** — 앞 단계가 없으면 뒷 단계가 빈 값으로 들어가고,
빈 값은 나중에 안 채워진다.

    python scripts/import_catalog.py --dry-run    무엇이 들어갈지만 본다
    python scripts/import_catalog.py

## 멱등하다

id 가 아니라 (제조사, 이름) 비교키로 찾는다. 여러 번 돌려도 같은 줄이 둘로 늘지
않는다. 이미 있는 값은 **안 덮는다** — 손으로 고쳐 둔 것이 사양서보다 정확하다.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.capabilities.models import ModelCapability
from app.modules.equipment.models import (
    EquipmentModel,
    EquipmentSeries,
    ModelSpecValue,
    SeriesRelation,
    SpecSource,
)
from app.modules.methods.models import TestMethod
from app.modules.vocabulary.catalog_specs import (
    CATALOG_SPEC_DEFINITIONS,
    CATEGORY_SPREAD,
    DIMENSION_GROUPS,
    DIMENSION_SOURCES,
    FALLBACK_GROUP,
    MIN_HINTS,
    PROMOTE_MIN_OBJECTS,
    SOURCE_SPEC_MAP,
    TEMPERATURE_PAIR,
    VARIANT_SUFFIXES,
)
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from app.shared.text import clean, compare_key

survive_cp949()

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "source" / "catalog"

#: 몇 개 객체에 나와야 사양 정의로 승격하나. 이 밑은 보류 목록으로만 보고한다.
PROMOTE_THRESHOLD = 3


class Catalog:
    """읽어 둔 원본. 온톨로지와 객체들."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / "equipment").rglob("*.json"))
        ]
        self.categories = self._load("ontology/categories.json", "categories")
        self.manufacturers = self._load("ontology/manufacturers.json", "manufacturers")
        self.test_items = self._load("ontology/test_items.json", "test_items")

    def _load(self, name: str, key: str) -> list[dict[str, Any]]:
        data = json.loads((self.root / name).read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = data[key]
        return rows


def _term(
    db: Session,
    axis: Vocabulary,
    value: str,
    actor: User | None,
    *,
    parent: VocabularyTerm | None = None,
) -> VocabularyTerm:
    """기준정보 값을 없으면 만든다. **비교키로 찾는다** — 표기가 달라도 같은 값이다.

    반입은 값을 만든다. 설치(`reference.py`)가 축만 세우고 값을 안 심는 것과 다른
    일이다 — 137개를 넣으려면 제조사와 분류가 먼저 있어야 하고, 그것을 사람에게
    손으로 시키면 아무도 안 넣는다.
    """
    key = compare_key(value)
    found = db.scalar(
        select(VocabularyTerm).where(
            VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.normalized == key
        )
    )
    if found is not None:
        return found
    found = VocabularyTerm(
        vocabulary_id=axis.id,
        value=clean(value),
        normalized=key,
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
) -> tuple[dict[str, VocabularyTerm], dict[str, VocabularyTerm], dict[str, VocabularyTerm]]:
    """1. 제조사·분류(트리)·시험 항목을 값으로 심는다."""
    makers_axis = _axis(db, "manufacturer")
    category_axis = _axis(db, "equipment_category")
    item_axis = _axis(db, "test_item")

    makers: dict[str, VocabularyTerm] = {}
    for row in cat.manufacturers:
        label = row.get("label") or row["id"]
        makers[row["id"]] = _term(db, makers_axis, label, actor)

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
            )
        pending = rest
        if not pending:
            break

    items: dict[str, VocabularyTerm] = {}
    for row in cat.test_items:
        label = row.get("label_ko") or row.get("label") or row["id"]
        items[row["id"]] = _term(db, item_axis, label, actor)

    db.flush()
    return makers, categories, items


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
    적어 둔 것이라 근거가 있다. 거기 없는 규격은 **항목을 비워 둔다.** 모르는 것을
    비워 두는 편이, 그럴듯한 오답을 적어 두는 것보다 낫다(ADR 0003).
    """
    body_axis = _axis(db, "standard_body")
    methods: dict[str, TestMethod] = {}

    by_standard: dict[str, str] = {}
    for row in cat.test_items:
        for code in row.get("typical_standards") or []:
            by_standard.setdefault(str(code).strip(), row["id"])

    seen: dict[str, str | None] = {}
    for obj in cat.objects:
        for code in (obj.get("standards") or {}).get("test_methods") or []:
            key = str(code).strip()
            seen.setdefault(key, by_standard.get(key))

    for code, item_id in sorted(seen.items()):
        if not code:
            continue
        found = db.scalar(select(TestMethod).where(TestMethod.code == code))
        if found is not None:
            methods[code] = found
            continue
        # 「ASTM D638」 의 앞 토막이 제정기관이다. 못 알아보면 비워 둔다 —
        # 지어내면 그 기관이 낸 적 없는 규격이 목록에 선다.
        head = code.split()[0].split("/")[0]
        body = _term(db, body_axis, head, actor) if head.isalpha() else None
        item = items.get(item_id or "")
        found = TestMethod(
            code=code,
            title=code,
            test_item_term_id=item.id if item else None,
            body_term_id=body.id if body else None,
            summary="제조사 카탈로그에서 인용",
            created_by_id=actor.id if actor else None,
        )
        db.add(found)
        db.flush()
        methods[code] = found
    return methods


def _ontology(cat: Catalog) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (cat.root / "ontology" / "condition_keys.json").read_text(encoding="utf-8")
    )
    return data


def _ontology_map(cat: Catalog) -> dict[str, tuple[str, float]]:
    """온톨로지가 선언한 **별칭과 단위 변형**을 대표 키로 잇는다.

    ## 왜 온톨로지에 두나

    `nominal_load_kN` 이 `force_kN` 의 다른 이름이라는 것은 **카탈로그 도메인
    지식**이지 TestScope 내부 사정이 아니다. 여기 손 매핑표에 적어 두면 같은 지식이
    두 저장소에 갈라지고, 갈라진 뒤에는 어느 쪽이 맞는지 알 방법이 없다.

    단위 변형은 계수까지 온톨로지가 갖는다 — `force_N` 은 0.001 을 곱해 kN 이 된다.
    """
    out: dict[str, tuple[str, float]] = {}
    for row in _ontology(cat)["keys"]:
        key = row["key"]
        for alias in row.get("aliases") or []:
            out[alias] = (key, 1.0)
        for variant, factor in (row.get("unit_variants") or {}).items():
            out[variant] = (key, float(factor))
    return out


def _ontology_roles(cat: Catalog) -> dict[str, str]:
    """키마다 무엇으로 다루나 — `measure` · `descriptive` · `not_spec`.

    **서술과 품번은 정의로 세우지 않는다.** 「제어 방식」 이나 주문 번호를 사양 칸으로
    만들면 「사양 추가」 목록이 그것들로 채워지고, 그때 목록은 못 쓰게 된다. 값은
    버리지 않는다 — 원문(`raw_specs`)에 그대로 남는다.
    """
    return {row["key"]: row.get("role") or "measure" for row in _ontology(cat)["keys"]}


def _key_shape(cat: Catalog, key: str) -> str:
    """그 키의 값이 실제로 어떤 모양인가 — 정의의 `kind` 를 여기서 정한다.

    **데이터를 보고 정한다.** 이름만 보고 「수치겠지」 하면 절반이 틀리고, 틀린 칸에
    담긴 값은 저장은 되지만 화면이 못 그린다. 여러 모양이 섞이면 구간이 이긴다 —
    구간은 수치 하나도 담을 수 있지만 그 반대는 안 된다.
    """
    shapes: set[str] = set()
    for obj in cat.objects:
        for pool in [obj.get("limits") or {}] + [
            (model.get("specs") or {}) for model in (obj.get("models") or [])
        ]:
            raw = pool.get(key)
            if raw is None:
                continue
            if isinstance(raw, bool):
                shapes.add("boolean")
            elif isinstance(raw, int | float):
                shapes.add("number")
            elif isinstance(raw, dict):
                inner = set(raw) - {"note", "uncertain"}
                shapes.add("range" if inner & {"min", "max", "values"} else "text")
            else:
                shapes.add("text")
    if "range" in shapes:
        return "range"
    if shapes == {"number"}:
        return "number"
    if shapes == {"boolean"}:
        return "boolean"
    return "text"


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
        made = SpecDefinition(
            key=row["key"],
            label=row["label"],
            group_id=groups[row["group"]].id,
            kind=row["kind"],
            dimension=row["dimension"],
            si_unit=row["unit"],
            display_unit=row["unit"],
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
            and key not in promoted_keys
            and key not in ("note", "uncertain")
            and not _variant_of(key)
        ),
        reverse=True,
    )
    return added, pending


def _variant_of(key: str) -> tuple[str, str] | None:
    """`vertical_test_space_mm_E2` 처럼 옵션 구성을 뒤에 붙인 키인가.

    **같은 사양의 다른 구성**이지 다른 사양이 아니다. 별도 정의로 만들면 사양표에
    거의 같은 줄이 둘씩 서고, 검색은 어느 쪽을 봐야 할지 모른다.
    """
    for suffix, label in VARIANT_SUFFIXES.items():
        if key.endswith(suffix):
            base = key[: -len(suffix)]
            if base in SOURCE_SPEC_MAP:
                return base, label
    return None


def _series_of(
    db: Session,
    obj: dict[str, Any],
    makers: dict[str, VocabularyTerm],
    categories: dict[str, VocabularyTerm],
    sources: dict[str, SpecSource],
    actor: User | None,
) -> EquipmentSeries:
    """계열 하나를 없으면 만든다. **있으면 안 덮는다.**"""
    maker = makers.get(obj["manufacturer"])
    name = clean(obj["name"])
    key = compare_key(name)
    found = db.scalar(
        select(EquipmentSeries).where(
            EquipmentSeries.normalized == key,
            EquipmentSeries.maker_term_id.is_(None)
            if maker is None
            else EquipmentSeries.maker_term_id == maker.id,
        )
    )
    if found is not None:
        return found

    first_source = (obj.get("sources") or [{}])[0].get("file")
    found = EquipmentSeries(
        name=name,
        name_ko=obj.get("name_ko"),
        normalized=key,
        maker_term_id=maker.id if maker else None,
        brand=obj.get("brand"),
        category_term_id=(
            categories[obj["category"]].id if obj["category"] in categories else None
        ),
        kind="main" if obj["kind"].startswith("equipment") else obj["kind"],
        drive=obj.get("drive") or "",
        form_factor=obj.get("form_factor") or "",
        summary=obj.get("description"),
        spec_note=_spec_note(obj),
        source_id=sources[first_source].id if first_source in sources else None,
        created_by_id=actor.id if actor else None,
    )
    db.add(found)
    db.flush()
    return found


def _spec_note(obj: dict[str, Any]) -> str | None:
    """사양 칸으로 못 담는 것을 한 덩어리로 남긴다 — 옵션·특징·비고.

    **버리지 않는다.** 지금 담을 칸이 없다는 것과 값이 쓸모없다는 것은 다르다.
    """

    def _one(value: Any) -> str:
        # 원본이 옵션을 `{name, note}` 로도 적는다 — 문자열로 뭉개면 「무엇이 어떻게
        # 달라지나」 가 사라진다(2026-09-10 스키마 개정).
        if isinstance(value, dict):
            head = str(value.get("name") or "")
            tail = str(value.get("note") or "")
            return f"{head} ({tail})" if head and tail else head or tail
        return str(value)

    parts: list[str] = []
    for label, key in (("옵션", "options"), ("특징", "features"), ("비고", "notes")):
        values = obj.get(key)
        if isinstance(values, list) and values:
            parts.append(f"[{label}] " + " · ".join(_one(one) for one in values))
        elif isinstance(values, str) and values:
            parts.append(f"[{label}] {values}")
    return "\n".join(parts) or None


def step_series(
    db: Session,
    cat: Catalog,
    makers: dict[str, VocabularyTerm],
    categories: dict[str, VocabularyTerm],
    items: dict[str, VocabularyTerm],
    methods: dict[str, TestMethod],
    actor: User | None,
) -> tuple[dict[str, EquipmentSeries], int]:
    """3. 계열과 그 역량. **무슨 시험이 되나는 계열의 성질**이다(ADR 0006)."""
    sources = {row.path: row for row in db.scalars(select(SpecSource))}
    made: dict[str, EquipmentSeries] = {}
    capabilities = 0

    for obj in cat.objects:
        series = _series_of(db, obj, makers, categories, sources, actor)
        made[obj["id"]] = series

        # **시험 항목 하나에 역량 하나.** 규격을 걸어 역량을 쪼개지 않는다.
        #
        # 카탈로그의 `test_methods` 는 계열에 붙은 평평한 목록이라, 인장 하나에
        # ASTM D638·ISO 527·ASTM E8 이 함께 걸린다. 그것을 역량 셋으로 만들면
        # **검색이 같은 장비를 여덟 줄로 답한다** — 실제로 그렇게 나왔다.
        #
        # 규격별로 조건이 갈리는 일은 실재하지만, 그것은 사양서가 아니라 그 대를
        # 돌려 본 사람이 아는 것이다. 여기서는 「이 계열은 인장이 된다」 까지만
        # 말하고, 규격은 인용 목록(`spec_note`)으로 남긴다.
        codes = [
            str(code).strip()
            for code in (obj.get("standards") or {}).get("test_methods") or []
            if str(code).strip()
        ]
        for item_id in obj.get("test_items") or []:
            term = items.get(item_id)
            if term is None:
                continue
            exists = db.scalar(
                select(ModelCapability).where(
                    ModelCapability.series_id == series.id,
                    ModelCapability.test_item_term_id == term.id,
                )
            )
            if exists is not None:
                continue
            mine = [
                one
                for one in codes
                if methods.get(one) is not None and methods[one].test_item_term_id == term.id
            ]
            db.add(
                ModelCapability(
                    series_id=series.id,
                    test_item_term_id=term.id,
                    note=("카탈로그 인용 규격: " + " · ".join(mine)) if mine else None,
                )
            )
            capabilities += 1
        db.flush()
    return made, capabilities


def _numbers(raw: Any, factor: float) -> tuple[float | None, float | None, str | None]:
    """원본 값에서 (최소, 최대, 단서) 를 뽑는다.

    원본은 네 모양으로 온다: 수치 하나 · `{min,max}` · `{values:[…]}` · 문장.
    앞의 셋만 숫자가 된다.
    """
    note = None
    if isinstance(raw, bool):
        return None, None, None
    if isinstance(raw, int | float):
        return raw * factor, raw * factor, None
    if isinstance(raw, dict):
        note = raw.get("note")
        if raw.get("uncertain"):
            # **원본 표를 잘못 읽었을 수 있다는 표시다.** 조용히 들이면 그것이
            # 진실이 된다 — 화면이 볼 수 있게 값 옆에 남긴다.
            note = f"{note} — 원본 확인 필요" if note else "원본 확인 필요"
        low, high = raw.get("min"), raw.get("max")
        values = [one for one in (raw.get("values") or []) if isinstance(one, int | float)]
        if low is None and values:
            low = min(values)
        if high is None and values:
            high = max(values)
        if low is None and high is None:
            return None, None, note
        return (
            low * factor if isinstance(low, int | float) else None,
            high * factor if isinstance(high, int | float) else None,
            note,
        )
    return None, None, None


def _as_text(raw: Any) -> str | None:
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, list):
        return " · ".join(str(one) for one in raw) or None
    if isinstance(raw, dict):
        values = raw.get("values")
        if values:
            return " · ".join(str(one) for one in values)
        parts = [f"{k} {v}" for k, v in raw.items() if k not in ("note", "uncertain")]
        return " · ".join(parts) or raw.get("note")
    if raw is None:
        return None
    return str(raw)


def _value_fields(
    definition: SpecDefinition, raw: Any, factor: float
) -> dict[str, Any] | None:
    """정의의 종류에 맞는 칸을 채운다. 못 담으면 None.

    **틀린 칸에 담긴 값은 조용히 사라진다.** 구간 사양에 수치만 넣으면 저장은 되지만
    화면은 아무것도 못 그리고, 그때 사람은 "반입이 안 됐다" 고 말한다.
    """
    low, high, note = _numbers(raw, factor)

    if definition.kind == "range":
        if low is None and high is None:
            return None
        return {"num_min": low, "num_max": high, "note": note}
    if definition.kind == "number":
        picked = low if definition.reflect_as == "min" else high
        if picked is None:
            return None
        extra = None
        if low is not None and high is not None and low != high:
            # 수치 한 칸에 구간이 왔다. **버리지 않고 비고에 원문을 남긴다.**
            extra = f"원문 {low} ~ {high}"
        return {"num_value": picked, "note": " · ".join(x for x in (note, extra) if x)}
    if definition.kind == "boolean":
        text = _as_text(raw)
        if isinstance(raw, bool):
            return {"bool_value": raw, "note": None}
        if text is None:
            return None
        # `{"values": ["optional"]}` 은 「옵션으로 붙는다」 — 없다가 아니다.
        yes = any(word in text.lower() for word in ("yes", "optional", "true", "있"))
        return {"bool_value": yes, "note": text if "optional" in text.lower() else None}
    text = _as_text(raw)
    if text is None:
        return None
    return {"text_value": text[:2000], "note": note}


def _put_spec(
    db: Session,
    model: EquipmentModel,
    definition: SpecDefinition,
    raw: Any,
    factor: float,
    *,
    taken: set[uuid.UUID],
    extra_note: str | None,
    source: SpecSource | None,
    page: int | None,
) -> bool:
    """사양 값 하나를 넣는다. **이미 있으면 안 덮는다** — 손으로 고쳐 둔 것이 더 낫다.

    `taken` 을 함께 보는 이유: 원본의 서로 다른 키가 같은 정의로 모인다
    (`power_W` 와 `power_kW` 는 둘 다 소비 전력이다). DB 만 보면 아직 flush 안 된
    같은 배치의 앞줄이 안 보여서, 유일 제약이 반입 도중에 터진다 — 실제로 그렇게 겪었다.
    """
    if definition.id in taken:
        return False
    fields = _value_fields(definition, raw, factor)
    if fields is None:
        return False
    taken.add(definition.id)
    note = " · ".join(x for x in (fields.pop("note", None), extra_note) if x) or None
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            note=note,
            source_id=source.id if source else None,
            source_page=page,
            **fields,
        )
    )
    return True


def _merge_temperature(
    db: Session,
    model: EquipmentModel,
    raw_specs: dict[str, Any],
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> bool:
    """상·하한을 두 키로 나눠 적은 온도를 **구간 하나로 합친다.**

    열충격 챔버가 그렇게 적는다 — 고온조 `[50, 200]`, 저온조 `[-65, 0]`. 둘을 따로
    두면 어느 쪽도 「시험 온도」 가 아니어서 그 챔버는 온도로 검색되지 않는다.
    """
    low_key, high_key, target = TEMPERATURE_PAIR
    if low_key not in raw_specs and high_key not in raw_specs:
        return False
    definition = definitions.get(target)
    if definition is None:
        return False

    bounds: list[float] = []
    for key in (low_key, high_key):
        raw = raw_specs.get(key)
        if isinstance(raw, int | float):
            bounds.append(float(raw))
        elif isinstance(raw, list):
            bounds.extend(float(one) for one in raw if isinstance(one, int | float))
        elif isinstance(raw, dict):
            for edge in ("min", "max"):
                if isinstance(raw.get(edge), int | float):
                    bounds.append(float(raw[edge]))
    if not bounds:
        return False
    return _put_spec(
        db,
        model,
        definition,
        {"min": min(bounds), "max": max(bounds)},
        1.0,
        taken=taken,
        extra_note="고온조·저온조 범위를 합침",
        source=source,
        page=None,
    )


def _import_specs(
    db: Session,
    model: EquipmentModel,
    raw_specs: dict[str, Any],
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    promoted: dict[str, tuple[str, float]],
    aliases: dict[str, tuple[str, float]],
) -> int:
    taken = set(
        db.scalars(
            select(ModelSpecValue.definition_id).where(ModelSpecValue.model_id == model.id)
        )
    )
    made = 0
    if _merge_temperature(db, model, raw_specs, definitions, source, taken):
        made += 1
    for key, raw in raw_specs.items():
        if key in ("note", "uncertain", TEMPERATURE_PAIR[0], TEMPERATURE_PAIR[1]):
            continue
        extra_note = None
        variant = _variant_of(key)
        if variant is not None:
            key, extra_note = variant
        # 원본이 같은 것을 여러 이름으로 적는다. 치수는 세 칸으로 나뉜다.
        target = DIMENSION_SOURCES.get(key)
        if target is None and key.startswith("footprint_"):
            target = DIMENSION_SOURCES["footprint_mm"]
        if target is not None:
            made += _import_dimensions(db, model, raw, definitions, source, taken, target)
            continue
        # 손으로 이어 둔 것이 먼저다 — 거기에는 단위 환산 같은 판단이 들어 있다.
        # 없으면 온톨로지에서 승격한 이름으로 찾는다.
        mapped = SOURCE_SPEC_MAP.get(key) or aliases.get(key) or promoted.get(key)
        if mapped is None:
            continue
        definition = definitions.get(mapped[0])
        if definition is None:
            continue
        if _put_spec(
            db,
            model,
            definition,
            raw,
            mapped[1],
            taken=taken,
            extra_note=extra_note,
            source=source,
            page=None,
        ):
            made += 1
    db.flush()
    return made


def _import_dimensions(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    taken: set[uuid.UUID],
    target: tuple[str, str, str],
) -> int:
    """치수를 가로·세로·높이 세 칸으로 나눈다.

    원본이 `[W, D, H]` 로도 `{"W":…}` 로도 온다. **순서를 지어내지 않는다** — 배열의
    뜻이 카탈로그마다 갈릴 수 있어서, 이름표가 있는 쪽만 이름으로 믿는다.

    `target` 이 바깥 치수인지 안쪽 치수인지를 정한다 — 둘은 다른 물음에 답한다.
    """
    values: list[float | None] = []
    if isinstance(raw, dict):
        keys = {k.lower(): v for k, v in raw.items()}
        values = [
            keys.get("w") or keys.get("width"),
            keys.get("d") or keys.get("depth"),
            keys.get("h") or keys.get("height"),
        ]
    elif isinstance(raw, list) and len(raw) == 3:
        values = list(raw)
    else:
        return 0

    made = 0
    for key, value in zip(target, values, strict=False):
        definition = definitions.get(key)
        if definition is None or not isinstance(value, int | float):
            continue
        if _put_spec(
            db,
            model,
            definition,
            value,
            1.0,
            taken=taken,
            extra_note=None,
            source=source,
            page=None,
        ):
            made += 1
    return made


def _model_note(row: dict[str, Any]) -> str | None:
    """기종에 붙는 단서. **`uncertain` 을 여기 남긴다.**

    원본이 「이 기종의 표를 잘못 읽었을 수 있다」 고 표시한 것이 27건 있다. 그것을
    안 옮기면 의심스러운 숫자가 확인된 숫자와 똑같이 앉아 있고, 그때 그 사실을
    아는 사람은 아무도 없다 — 실제로 첫 반입이 그랬다(ADR 0006).
    """
    parts: list[str] = []
    if row.get("uncertain"):
        parts.append("원본 확인 필요 — 카탈로그의 표를 잘못 읽었을 수 있습니다.")
    if row.get("note"):
        parts.append(str(row["note"]))
    return "\n".join(parts) or None


def step_models(
    db: Session, cat: Catalog, series: dict[str, EquipmentSeries], actor: User | None
) -> tuple[int, int, int, int]:
    """4. 기종과 그 사양값. **수치가 갈리는 자리**(ADR 0006).

    ## 계열 사양표(limits)를 어떻게 다루나

    기종이 **하나뿐인 계열**에서는 그것이 곧 그 기종의 사양이다 — 애매할 것이 없다.
    기종이 여럿이면 계열의 limits 는 **봉투**다: 0.5~300 kN 은 어느 기종의 값도
    아니다. 그것을 기종 사양으로 들이면 0.5 kN 짜리가 300 kN 된다고 답한다.
    그래서 봉투는 계열의 비고에 원문으로 남기고, 수치로는 안 들인다(ADR 0003).
    """
    definitions = {row.key: row for row in db.scalars(select(SpecDefinition))}
    sources = {row.path: row for row in db.scalars(select(SpecSource))}
    # 온톨로지에서 승격한 키 -> (정의 key, 배율 1). 원본이 이미 그 단위로 적는다.
    promoted = {row["source_key"]: (row["key"], 1.0) for row in _promotable(cat)}
    # 온톨로지가 선언한 별칭·단위 변형. **손 매핑표보다 뒤에 본다** — 거기에는
    # 이쪽만 아는 판단(정의 이름이 다른 것)이 들어 있다.
    aliases = _alias_targets(db, cat)
    marker = "원본 확인 필요"
    models = values = flagged = kept = 0

    for obj in cat.objects:
        parent = series[obj["id"]]
        first_source = (obj.get("sources") or [{}])[0].get("file")
        source = sources.get(first_source) if first_source else None
        rows = obj.get("models") or [{"model": obj["name"]}]

        made_here: list[EquipmentModel] = []
        for row in rows:
            name = clean(str(row.get("model") or obj["name"]))
            key = compare_key(name)
            found = db.scalar(
                select(EquipmentModel).where(
                    EquipmentModel.series_id == parent.id, EquipmentModel.normalized == key
                )
            )
            if found is None:
                found = EquipmentModel(
                    series_id=parent.id,
                    name=name,
                    normalized=key,
                    form_factor=row.get("form_factor") or obj.get("form_factor") or "",
                    spec_note=_model_note(row),
                    created_by_id=actor.id if actor else None,
                )
                db.add(found)
                db.flush()
                models += 1
            elif row.get("uncertain") and marker not in (found.spec_note or ""):
                # **이것만 예외로 기존 행을 고친다.** 값을 덮는 것이 아니라 빠진
                # 경고를 채우는 것이고, 안 채우면 의심스러운 숫자가 확인된 숫자와
                # 똑같이 앉아 있는다. 사람이 적어 둔 비고는 뒤에 그대로 남긴다.
                found.spec_note = "\n".join(
                    x for x in (_model_note(row), found.spec_note) if x
                )
                flagged += 1
            made_here.append(found)
            values += _import_specs(
                db, found, row.get("specs") or {}, definitions, source, promoted, aliases
            )
            # **원문을 통째로 남긴다.** 정의가 없는 키가 950종 넘고, 그 값은
            # 지금까지 버려지고 있었다 — 아는 것은 사양값으로, 전부는 여기에.
            if row.get("specs") and not found.raw_specs:
                found.raw_specs = row["specs"]
                kept += 1

        limits = obj.get("limits") or {}
        if limits and len(made_here) == 1:
            values += _import_specs(
                db, made_here[0], limits, definitions, source, promoted, aliases
            )
        if limits and not parent.raw_limits:
            kept += 1
            # 봉투는 수치로 안 들이지만(ADR 0006) **원문은 남긴다** — 사람이 읽을
            # 값이고, 기종 사양이 빈 계열에서는 이것이 유일한 근거다.
            parent.raw_limits = limits
        if limits and len(made_here) > 1:
            envelope = " · ".join(
                f"{key} {_as_text(raw)}" for key, raw in sorted(limits.items())
            )
            block = f"[계열 사양 봉투] {envelope}"
            if not (parent.spec_note or "").startswith("[계열 사양 봉투]"):
                parent.spec_note = (
                    f"{block}\n{parent.spec_note}" if parent.spec_note else block
                )
        db.flush()
    return models, values, flagged, kept


def step_relations(db: Session, cat: Catalog, series: dict[str, EquipmentSeries]) -> int:
    """5. 계열끼리의 관계. **부속이 사양값을 바꾼다**(ADR 0006)."""
    made = 0
    for obj in cat.objects:
        host = series[obj["id"]]
        for row in obj.get("relations") or []:
            part = series.get(str(row.get("target")))
            if part is None or part.id == host.id:
                # 온톨로지 노드(시험 항목·규격)를 가리키는 관계는 여기 대상이
                # 아니다 — 그것은 역량으로 이미 들어갔다.
                continue
            exists = db.scalar(
                select(SeriesRelation).where(
                    SeriesRelation.host_series_id == host.id,
                    SeriesRelation.part_series_id == part.id,
                    SeriesRelation.relation == row["type"],
                )
            )
            if exists is not None:
                continue
            db.add(
                SeriesRelation(
                    host_series_id=host.id,
                    part_series_id=part.id,
                    relation=row["type"],
                    note=row.get("note"),
                )
            )
            made += 1
    db.flush()
    return made


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
        methods = step_methods(db, cat, items, actor)
        definitions, pending = step_definitions(db, cat, categories)
        series, capabilities = step_series(db, cat, makers, categories, items, methods, actor)
        models, values, flagged, kept = step_models(db, cat, series, actor)
        relations = step_relations(db, cat, series)

        if args.dry_run:
            db.rollback()
            print("(dry-run — 되돌렸습니다)")
        else:
            db.commit()

        print(f"객체 {len(cat.objects)}건에서:")
        print(f"  제조사 {len(makers)} · 분류 {len(categories)} · 시험 항목 {len(items)}")
        print(f"  시험법 {len(methods)}")
        print(f"  사양 정의 새로 {definitions}")
        print(f"  계열 {len(series)} · 계열 역량 새로 {capabilities}")
        print(f"  기종 새로 {models} · 사양값 새로 {values}")
        if kept:
            print(f"  원문 보존 {kept}건 (정의가 없는 값도 통째로 남는다)")
        if flagged:
            print(f"  원본 확인 필요로 표시한 기종 {flagged}")
        print(f"  계열 관계 새로 {relations}")
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
