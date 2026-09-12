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
from datetime import UTC, datetime
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
from app.modules.equipment.models import (
    EquipmentModel,
    EquipmentSeries,
    ModelFreeSpec,
    ModelSpecValue,
    SeriesRelation,
    SpecSource,
)
from app.modules.methods.models import TestMethod
from app.modules.properties.models import TestItemProperty
from app.modules.test_items.models import (
    SeriesPendingMethod,
    SeriesTestItem,
    SeriesTestItemMethod,
)
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
    VARIANT_SUFFIXES,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.vocabulary.reference import SPEC_DEFINITION_LINKS
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from app.shared.text import clean, compare_key, method_key

survive_cp949()

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "source" / "catalog"

#: 몇 개 객체에 나와야 사양 정의로 승격하나. 이 밑은 보류 목록으로만 보고한다.
PROMOTE_THRESHOLD = 3

#: 온톨로지의 두 id 가 같은 이름을 써서 한 값에 코드 둘이 오려던 것. 끝에 보고한다.
_CODE_CLASHES: list[str] = []


class Catalog:
    """읽어 둔 원본. 온톨로지와 객체들."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / "equipment").rglob("*.json"))
        ]
        self.categories = self._load("ontology/categories.json", "categories")
        self.form_factors = self._load("ontology/form_factors.json", "form_factors")
        self.drives = self._load("ontology/drives.json", "drives")
        self.manufacturers = self._load("ontology/manufacturers.json", "manufacturers")
        self.test_items = self._load("ontology/test_items.json", "test_items")
        # 물성과 그 연결 규칙. 둘 다 없어도 반입은 돈다 — 옛 카탈로그 스냅샷에는 없다.
        self.properties = (
            self._load("ontology/properties.json", "properties")
            if (root / "ontology/properties.json").exists()
            else []
        )
        links_path = root / "ontology/property_links.json"
        self.property_links: dict[str, Any] = (
            json.loads(links_path.read_text(encoding="utf-8")) if links_path.exists() else {}
        )

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
) -> tuple[dict[str, VocabularyTerm], dict[str, VocabularyTerm], dict[str, VocabularyTerm]]:
    """1. 제조사·분류(트리)·시험 항목을 값으로 심는다."""
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

    db.flush()
    return makers, categories, items


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
    """
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
        known[method_key(code)] = found
    if filled:
        print(f"  시험 항목이 비어 있던 시험법 {filled}건에 항목을 채웠습니다")
    return methods


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
    form_factors: dict[str, uuid.UUID],
    drives: dict[str, uuid.UUID],
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
        if obj.get("supplements"):
            _supplement_series(found, obj)
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
        drive_term_id=drives.get(obj.get("drive") or ""),
        form_factor_term_id=form_factors.get(obj.get("form_factor") or ""),
        summary=obj.get("description"),
        spec_note=_spec_note(obj),
        source_id=sources[first_source].id if first_source in sources else None,
        created_by_id=actor.id if actor else None,
    )
    db.add(found)
    db.flush()
    return found


def _supplement_series(series: EquipmentSeries, obj: dict[str, Any]) -> None:
    """다른 출처(MaterialTwin)가 같은 계열에 보탠 비고·원문. **한 번만, 덮지 않고.**

    계열 자체는 안 고친다 — 손으로 다듬은 이름·분류가 더 낫다. 보태는 것은 그 출처의
    말(비고)과 원문(raw_limits.materialtwin)뿐이고, 표식이 이미 있으면 안 한다.
    """
    marker = "[MaterialTwin]"
    note = obj.get("notes")
    if isinstance(note, str) and note and marker not in (series.spec_note or ""):
        series.spec_note = f"{series.spec_note}\n{note}" if series.spec_note else note
    raw = obj.get("materialtwin_series")
    if raw:
        limits = dict(series.raw_limits or {})
        if "materialtwin" not in limits:
            limits["materialtwin"] = raw
            series.raw_limits = limits


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
    form_factors: dict[str, uuid.UUID],
    drives: dict[str, uuid.UUID],
    actor: User | None,
) -> tuple[dict[str, EquipmentSeries], int, int]:
    """3. 계열과 그 시험 항목. **무슨 시험이 되나는 계열의 성질**이다(ADR 0006).

    돌려주는 것: (계열, 새로 만든 시험 항목 수, 항목 미정으로 남긴 인용 수).
    """
    sources = {row.path: row for row in db.scalars(select(SpecSource))}
    made: dict[str, EquipmentSeries] = {}
    test_items = 0
    pending = 0

    for obj in cat.objects:
        series = _series_of(db, obj, form_factors, drives, makers, categories, sources, actor)
        made[obj["id"]] = series

        # **시험 항목 하나에 시험 항목 하나.** 규격을 걸어 시험 항목을 쪼개지 않는다.
        #
        # 카탈로그의 `test_methods` 는 계열에 붙은 평평한 목록이라, 인장 하나에
        # ASTM D638·ISO 527·ASTM E8 이 함께 걸린다. 그것을 시험 항목 셋으로 만들면
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
        linked_codes: set[str] = set()
        for item_id in obj.get("test_items") or []:
            term = items.get(item_id)
            if term is None:
                continue
            by_item = (obj.get("standards") or {}).get("test_methods_by_item") or {}
            listed = set(by_item.get(item_id) or [])
            mine = [
                one
                for one in codes
                if methods.get(one) is not None
                and (one in listed or methods[one].test_item_term_id == term.id)
            ]
            test_item = db.scalar(
                select(SeriesTestItem).where(
                    SeriesTestItem.series_id == series.id,
                    SeriesTestItem.test_item_term_id == term.id,
                )
            )
            if test_item is None:
                test_item = SeriesTestItem(series_id=series.id, test_item_term_id=term.id)
                db.add(test_item)
                db.flush()
                test_items += 1
            # **비고 문자열이 아니라 표로 잇는다.** 글자로 두면 시험법 453건이
            # 아무것도 가리키지 않는 목록으로 남고, 「ASTM D638 되는 장비」 를 물으면
            # 문자열을 훑는 수밖에 없다.
            #
            # 시험 항목이 **이미 있어도** 빠진 링크는 보탠다. 전에는 있는 항목을 통째로
            # 건너뛰어, 나중에 시험 항목이 정해진 규격 115 건이 영영 안 이어졌다 —
            # 두 번째 반입이 첫 반입이 못 한 일을 이어받아야 한다.
            have = {
                one.method_id
                for one in db.scalars(
                    select(SeriesTestItemMethod).where(
                        SeriesTestItemMethod.series_test_item_id == test_item.id
                    )
                )
            }
            for code in mine:
                linked_codes.add(code)
                if methods[code].id not in have:
                    db.add(
                        SeriesTestItemMethod(
                            series_test_item_id=test_item.id, method_id=methods[code].id
                        )
                    )
        # **누가 인용했나를 남긴다.** 시험이 여럿인 계열이 인용한 규격 중 어느 시험의
        # 것인지 모르는 것은 링크를 못 만든다. 그 사실을 DB 에 안 남기면 시험법이
        # 「가능 장비 없음」 으로 서고, 못 하는 시험과 끊긴 연결을 아무도 못 가른다.
        # 시험 항목이 정해지는 순간 `promote_pending` 이 여기서 링크로 올린다.
        for code in codes:
            method = methods.get(code)
            if method is None or code in linked_codes:
                continue
            if method.test_item_term_id is not None:
                # 항목은 정해졌는데 이 계열에 그 시험이 없다 — 온톨로지와 객체가 어긋난
                # 것이라 미정이 아니다. 미정 표에 넣으면 「정하면 붙는다」 가 거짓이 된다.
                continue
            exists = db.scalar(
                select(SeriesPendingMethod).where(
                    SeriesPendingMethod.series_id == series.id,
                    SeriesPendingMethod.method_id == method.id,
                )
            )
            if exists is None:
                db.add(SeriesPendingMethod(series_id=series.id, method_id=method.id))
                pending += 1
        db.flush()
    return made, test_items, pending


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


def _fmt(number: float) -> str:
    """187.5 는 187.5 로, 1000.0 은 1000 으로 — 비고에 `.0` 이 줄줄이 붙지 않게."""
    return str(int(number)) if float(number).is_integer() else str(number)


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
        # 낱개 목록(경도계 하중 「500 · 750 · 1000」)은 양끝만 남기면 「187.5 로 되나」
        # 를 못 답한다 — 목록을 비고에 남긴다. 둘이면 그냥 구간이다.
        listed = (
            [one for one in raw.get("values") or [] if isinstance(one, int | float)]
            if isinstance(raw, dict)
            else []
        )
        if len(listed) > 2:
            shown = " · ".join(_fmt(one * factor) for one in listed)
            note = " · ".join(x for x in (note, f"고를 수 있는 값 {shown}") if x)
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
        # 있는 값은 안 덮는다. 다만 **부속 표시만은 켠다** — 표시가 없던 시절에 들어온
        # 값에 원본이 「옵션 부속 기준」 이라고 적혀 있으면, 그 값은 지금 검색이 갖고
        # 있지도 않은 챔버를 전제로 답하는 자리다. 켜는 쪽은 더 조심스러워지는 방향뿐이다.
        if isinstance(raw, dict) and raw.get("requires_accessory"):
            held = db.scalar(
                select(ModelSpecValue).where(
                    ModelSpecValue.model_id == model.id,
                    ModelSpecValue.definition_id == definition.id,
                )
            )
            if held is not None and not held.requires_accessory:
                held.requires_accessory = True
        return False
    fields = _value_fields(definition, raw, factor)
    if fields is None:
        return False
    taken.add(definition.id)
    note = " · ".join(x for x in (fields.pop("note", None), extra_note) if x) or None
    # **부속 표시를 버리지 않는다.** 온톨로지가 「이 온도는 옵션 챔버 기준」 이라고
    # 적은 것(`requires_accessory`)이 여기서 빠지면 검색이 그 챔버를 전제로 답한다.
    accessory = isinstance(raw, dict) and bool(raw.get("requires_accessory"))
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            note=note,
            requires_accessory=accessory,
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


def _numbers_of(raw: Any) -> list[float]:
    """배열·중첩 배열에서 수치만 훑어 낸다. 구성 배열과 이중 레인지가 둘 다 온다."""
    out: list[float] = []
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return [float(raw)]
    if isinstance(raw, list):
        for one in raw:
            out.extend(_numbers_of(one))
    return out


def _import_option_range(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definition: SpecDefinition | None,
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> bool:
    """카탈로그가 여러 값으로 적어 온 것을 **구간 하나**로 담는다.

    두 경우가 같은 모양으로 온다:

        actuator_ratings_kN [15, 25]        고를 수 있는 정격 — 그 대는 둘 중 하나다
        force_ranges_kN [4000, …, 80]       다중 레인지 로드셀 — 한 대가 전부 갖는다

    **둘 다 구간이 맞는 답이다.** 앞은 「이 기종은 15~25 로 나온다」 이고 뒤는 「80
    에서 4000 까지 잰다」 다. 최대값만 담으면 앞의 경우 15 짜리를 가진 부서가
    「25 kN 됩니까」 에 된다고 답하고, 뒤의 경우 저레인지 측정이 사라진다.

    **원문 전부를 비고에 남긴다.** 양끝만 남기면 중간 값들이 사라져 「400 kN 레인지도
    있나」 에 답할 수 없다.
    """
    if definition is None:
        return False
    values = _numbers_of(raw)
    if not values:
        return False
    note = None
    if len(values) > 2:
        note = "카탈로그가 적어 온 값들: " + ", ".join(
            f"{one:g}" for one in sorted(set(values), reverse=True)
        )
    return _put_spec(
        db,
        model,
        definition,
        {"min": min(values), "max": max(values)},
        1.0,
        taken=taken,
        extra_note=note,
        source=source,
        page=None,
    )


def _import_range_pair(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definitions: dict[str, SpecDefinition],
    targets: tuple[str, str],
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> int:
    """저·고 두 레인지를 **정의 둘로** 나눠 담는다.

    합쳐서 0.6~2600 으로 담으면 「100 W 부하 되나」 에는 맞게 답하지만, 레인지마다
    분해능이 다르다는 사실이 사라진다 — 전자부하를 고르는 사람이 보는 것이 그것이다.
    """
    if not isinstance(raw, list) or len(raw) != 2:
        return 0
    made = 0
    for one, key in zip(raw, targets, strict=True):
        definition = definitions.get(key)
        if definition is None:
            continue
        values = _numbers_of(one)
        if not values:
            continue
        payload: Any = (
            {"min": min(values), "max": max(values)}
            if definition.kind == "range"
            else values[0]
        )
        if _put_spec(
            db,
            model,
            definition,
            payload,
            1.0,
            taken=taken,
            extra_note=None,
            source=source,
            page=None,
        ):
            made += 1
    return made


def _import_max_only(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definition: SpecDefinition | None,
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> bool:
    """상한만 적힌 값을 구간의 **최대값으로만** 담는다.

    수치 하나를 구간에 그냥 넣으면 400~400 이 된다 — 「400도까지」 가 아니라 「400도
    에서만」 이 되고, 그러면 검색이 100도를 물을 때 그 장비가 조용히 빠진다.
    """
    if definition is None:
        return False
    values = _numbers_of(raw)
    if not values:
        return False
    return _put_spec(
        db,
        model,
        definition,
        {"max": max(values)},
        1.0,
        taken=taken,
        extra_note=None,
        source=source,
        page=None,
    )


#: 사양이 아니라 다른 자리로 가는 키 — 여기 있는 것은 「이 기종만의 사양」 으로도 안 간다.
_NOT_FREE_SPEC = {"note", "uncertain", "materialtwin"}
#: 이번 반입이 만든 「이 기종만의 사양」 줄 수. 사양값과 따로 센다 — 섞으면 「사양값 1848」
#: 이 정의 값처럼 읽힌다.
_FREE_MADE = 0


def _put_free_spec(
    db: Session,
    model: EquipmentModel,
    key: str,
    raw: Any,
    source: SpecSource | None,
    labels: dict[str, tuple[str, str | None, str]],
) -> bool:
    """정의 없는 키를 「이 기종만의 사양」 으로. **있는 줄은 안 덮는다** — 사람이 이름을 고쳐
    둔 것이 재반입에 돌아오면 안 된다. 품번(`not_spec`)은 사양이 아니라 안 들인다."""
    if key in _NOT_FREE_SPEC:
        return False
    label, unit, role = labels.get(key, (key, None, "measure"))
    if role == "not_spec":
        return False
    text = _as_text(raw)
    if not text:
        return False
    exists = db.scalar(
        select(ModelFreeSpec).where(
            ModelFreeSpec.model_id == model.id, ModelFreeSpec.source_key == key
        )
    )
    if exists is not None:
        return False
    global _FREE_MADE
    _FREE_MADE += 1
    db.add(
        ModelFreeSpec(
            model_id=model.id,
            label=label[:150],
            value_text=text[:4000],
            unit=unit or None,
            note=(raw.get("note") if isinstance(raw, dict) else None),
            source_key=key,
            origin="catalog",
            source_id=source.id if source else None,
        )
    )
    return True


def _free_labels(cat: Catalog) -> dict[str, tuple[str, str | None, str]]:
    """온톨로지 키 -> (라벨, 단위, 역할). 서술 키(`control` → 「제어 방식」)가 여기서 이름을
    얻는다 — 정의로는 안 서지만 「이 기종만의 사양」 으로는 들어간다."""
    out: dict[str, tuple[str, str | None, str]] = {}
    # 등록 대기열(`suggested_keys.json`)은 라벨이 비어 있지만 **키 이름에서 읽은 단위**는
    # 있다(`min_torque_nNm` → nNm). 이름은 안 지어내되 단위는 그 파일의 것을 쓴다.
    queued = cat.root / "ontology" / "suggested_keys.json"
    if queued.exists():
        for row in json.loads(queued.read_text(encoding="utf-8")).get("keys") or []:
            out[row["key"]] = (
                row["key"],
                row.get("unit") or None,
                row.get("role") or "measure",
            )
    for row in _ontology(cat)["keys"]:
        entry = (
            row.get("label") or row["key"],
            row.get("unit") or None,
            row.get("role") or "measure",
        )
        out[row["key"]] = entry
        for alias in row.get("aliases") or []:
            out.setdefault(alias, entry)
    return out


def _import_specs(
    db: Session,
    model: EquipmentModel,
    raw_specs: dict[str, Any],
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    promoted: dict[str, tuple[str, float]],
    aliases: dict[str, tuple[str, float]],
    free_labels: dict[str, tuple[str, str | None, str]] | None = None,
) -> int:
    free_labels = free_labels or {}
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
        # 원본이 한 칸에 두 벌·여러 구성·상한만 적어 오는 자리들. 그냥 담으면 각각
        # 다른 방식으로 틀린 값이 된다(catalog_specs 의 세 표에 이유를 적어 뒀다).
        pair = RANGE_PAIR_SOURCES.get(key)
        if pair is not None:
            made += _import_range_pair(db, model, raw, definitions, pair, source, taken)
            continue
        if key in OPTION_RANGE_SOURCES:
            if _import_option_range(
                db, model, raw, definitions.get(OPTION_RANGE_SOURCES[key]), source, taken
            ):
                made += 1
            continue
        if key in MAX_ONLY_SOURCES:
            if _import_max_only(
                db, model, raw, definitions.get(MAX_ONLY_SOURCES[key]), source, taken
            ):
                made += 1
            continue
        # 손으로 이어 둔 것이 먼저다 — 거기에는 단위 환산 같은 판단이 들어 있다.
        # 없으면 온톨로지에서 승격한 이름으로 찾는다.
        mapped = SOURCE_SPEC_MAP.get(key) or aliases.get(key) or promoted.get(key)
        if mapped is None:
            # **정의가 없는 키는 「이 기종만의 사양」 으로 들인다.** 전에는 원문 JSON 에만
            # 남아 화면에서 고칠 수도 정의로 올릴 수도 없었다. 이름은 온톨로지가 알면 그
            # 라벨, 모르면 원본 키 그대로 — 지어내지 않는다.
            _put_free_spec(db, model, key, raw, source, free_labels)
            continue
        definition = definitions.get(mapped[0])
        if definition is None:
            _put_free_spec(db, model, key, raw, source, free_labels)
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
    db: Session,
    cat: Catalog,
    series: dict[str, EquipmentSeries],
    form_factors: dict[str, uuid.UUID],
    actor: User | None,
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
    free_labels = _free_labels(cat)
    marker = "원본 확인 필요"
    models = values = flagged = kept = 0

    for obj in cat.objects:
        parent = series[obj["id"]]
        first_source = (obj.get("sources") or [{}])[0].get("file")
        source = sources.get(first_source) if first_source else None
        # 기종이 없는 객체는 계열 이름을 기종으로 하나 세운다 — 카탈로그가 기종을 안 나눈
        # 장비가 실재한다. 다만 **보탬 객체**(supplements)는 본 객체의 계열에 시험 항목만
        # 보태는 것이라 기종을 세우면 안 된다 — 세우면 계열 이름을 단 빈 기종이 12개 생겨
        # 「사양 없는 기종」 으로 서 있었다.
        rows = obj.get("models") or (
            [] if obj.get("supplements") else [{"model": obj["name"]}]
        )

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
                    form_factor_term_id=form_factors.get(
                        row.get("form_factor") or obj.get("form_factor") or ""
                    ),
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
                db,
                found,
                row.get("specs") or {},
                definitions,
                source,
                promoted,
                aliases,
                free_labels,
            )
            # **원문을 통째로 남긴다.** 정의가 없는 키가 950종 넘고, 그 값은
            # 지금까지 버려지고 있었다 — 아는 것은 사양값으로, 전부는 여기에.
            raw = dict(row.get("specs") or {})
            if row.get("materialtwin"):
                # MaterialTwin 원문(설명·주석·능력행)도 통째로. 사양 칸에 못 담은 시편
                # 조건·정확도·범위가 전부 여기 있다 — 「기종에 있는 데이터는 모두」.
                raw["materialtwin"] = row["materialtwin"]
            if raw and not found.raw_specs:
                found.raw_specs = raw
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
                # 아니다 — 그것은 시험 항목으로 이미 들어갔다.
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

        if args.dry_run:
            db.rollback()
            print("(dry-run — 되돌렸습니다)")
        else:
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
            f"  기종 새로 {models} · 사양값 새로 {values} · 이 기종만의 사양 새로 {_FREE_MADE}"
        )
        if kept:
            print(f"  원문 보존 {kept}건 (정의가 없는 값도 통째로 남는다)")
        if flagged:
            print(f"  원본 확인 필요로 표시한 기종 {flagged}")
        print(f"  계열 관계 새로 {relations}")
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
        if _CODE_CLASHES:
            # 온톨로지가 두 id 에 같은 이름을 줬다. 한 값에 코드 둘이 올 수 없어 앞의 것이
            # 이겼고, 뒤의 id 로 만든 객체는 **앞의 값**을 가리킨다 — 이름을 갈라야 한다.
            print(f"\n같은 이름을 쓰는 온톨로지 id {len(_CODE_CLASHES)}건 (이름을 가르세요):")
            for line in _CODE_CLASHES:
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
