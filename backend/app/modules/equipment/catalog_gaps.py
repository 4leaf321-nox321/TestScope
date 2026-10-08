"""카탈로그 보강 목록 — **미연결 장비가 왜 미연결인지를 서버가 가른다.**

대장으로 들인 장비의 상당수가 카탈로그 기종에 안 이어진 채 남는다(운영 2026-10-08, 사용자
보고: 전자계측 · 광학 · 치수 측정 · 환경 · 부속 등). 이유가 여럿이고 이유마다 할 일이 다르다.

    exact           같은 이름의 기종이 있다       → 그 기종에 잇는다
    similar         비슷한 이름의 기종이 있다     → 같은지 보고 잇거나 계열에 세운다
    series_only     계열은 있는데 기종이 없다     → 그 계열에 기종을 세운다
    not_in_catalog  제조사나 계열부터 없다        → 사양서를 조사해 정본에 넣는다
    no_model        모델명이 비어 대조 불가       → 현장에서 모델명을 채운다
    excluded        관리자가 「대상 아님」 으로 정함 → 할 일 없음(자작 장비 등)

「비슷함」 은 다른 기종일 수 있다. 한 목록에 다 섞여 있으면 관리자는 줄마다 같은 추리를
되풀이한다. 그래서 **모으는 열쇠는 기종 등록 요청과 같다**(`proposals.proposal_key`) — 고치는
길도 그 흐름을 탄다. 「요청으로 올리기」 는 요청을 만들고, 「연결」 · 「계열에 세우기」 ·
「아니오」 는 요청을 만든 뒤 바로 정한다(`proposals.decide`). 누가 언제 무엇으로 정했는지가
요청 줄과 감사에 남는다.

정본에 없는 것(`not_in_catalog`)은 **내려받아 사양서를 조사하는 목록**이 된다(CSV →
`source/catalog` 객체 → 반입). 분류에 카탈로그 코드가 없으면(운영에서 손으로 세운 분류) 그
분류부터 정본에 없다는 뜻이라 분류별 표에 따로 표시한다.

**고르지 않는다.** 비슷한 이름은 후보로 보여 줄 뿐 잇지 않는다 — 비슷한 기종을 고르면 그
장비의 하중·온도가 남의 것이 되고, 검색이 그 수치로 답한다(장비 등록 안내와 같은 이유).
"""

from __future__ import annotations

import collections
import csv
import difflib
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment import proposals
from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentModelProposal,
    EquipmentSeries,
)
from app.modules.equipment.schemas import (
    CatalogGapCandidateOut,
    CatalogGapCategoryOut,
    CatalogGapGroupOut,
    CatalogGapsOut,
    CatalogGapUnitOut,
)
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared.errors import AppError, Forbidden, NotFound
from app.shared.request_context import get_actor_token
from app.shared.text import clean, compare_key

CASES = ("exact", "similar", "series_only", "not_in_catalog", "no_model", "excluded")
CASE_LABELS = {
    "exact": "같은 기종 있음",
    "similar": "비슷한 기종 있음",
    "series_only": "계열만 있음",
    "not_in_catalog": "카탈로그에 없음",
    "no_model": "모델명 없음",
    "excluded": "카탈로그 대상 아님",
}
NO_CATEGORY = "분류 없음"

#: 비슷하다고 보는 문자열 유사도 하한. 더 낮추면 「68FM-300」 과 「68TM-30」 처럼 계열이 다른
#: 기종이 후보로 줄줄이 붙어, 사람이 후보를 안 읽게 된다.
SIMILAR = 0.75
#: 계열의 **기종 이름 공통 앞부분**을 계열 표지로 쓰는 최소 길이. 「DSOX30」 은 표지가 되고
#: 「68」 은 안 된다 — 두 글자 앞부분은 남의 계열에도 흔하다.
STEM = 4
#: 한 묶음에 실어 보내는 장비 수. 나머지는 수(`count`)로만 말한다(CSV 는 전부 싣는다).
UNITS_SHOWN = 30
#: 후보 기종 · 계열을 몇 개까지 보이나. 다섯을 넘으면 사람은 첫 줄만 본다.
CANDIDATES = 5

#: 계열 이름에서 떼어 내는 일반어 — 이것까지 맞춰 보면 「Test System」 이 모든 장비에 걸린다.
_GENERIC = re.compile(
    r"\b(series|systems?|chambers?|testers?|testing|test|machines?|family|platform|"
    r"instruments?|analy[sz]ers?|meters?|universal)\b|시리즈|계열|시험기|챔버|장비",
    re.IGNORECASE,
)


def squash(text: str | None) -> str:
    """비교용으로 **글자와 숫자만** 남긴다 — `68FM-300` · `68 FM 300` · `68fm300` 이 같다."""
    return re.sub(r"[\W_]+", "", compare_key(text or ""))


def runs(text: str | None, *, codes: bool = True) -> set[str]:
    """이름 안의 **낱말을 이어 붙인 조각**(세 낱말까지). `codes` 면 숫자가 든 것만.

    카탈로그 기종 이름에는 제조사 · 설명이 붙은 것이 있다 — 「Konica Minolta CA-410
    Display Color Analyzer」 · 「ProLine Z050/TN」. 대장에는 「CA-410」 · 「Z050」 만 적힌다.
    낱말 경계로 자른 조각끼리 맞추면 「CA-410」 이 「CA-4100」 에, 「T2000」 이 「CT-2000」 에
    걸리지 않는다(글자 포함과 다른 점).
    """
    words = [word for word in re.split(r"[\s/(),;+\u2013]+", compare_key(text or "")) if word]
    out: set[str] = set()
    for start in range(len(words)):
        for end in range(start + 1, min(start + 3, len(words)) + 1):
            piece = squash("".join(words[start:end]))
            if len(piece) >= 3 and (not codes or re.search(r"\d", piece)):
                out.add(piece)
    return out


@dataclass
class _Maker:
    id: uuid.UUID
    label: str
    keys: set[str]


@dataclass
class _Model:
    id: uuid.UUID
    name: str
    key: str
    series_id: uuid.UUID
    series_name: str
    maker_id: uuid.UUID | None
    maker_label: str
    runs: set[str] = field(default_factory=set)


@dataclass
class _Series:
    id: uuid.UUID
    name: str
    maker_id: uuid.UUID | None
    maker_label: str
    #: 계열을 알아보는 표지 — 계열 이름에서 제조사 · 일반어를 뗀 것(`6800`), 이름에 든 기종
    #: 번호(`z250`), 고유 이름(`allroundline`). 대장 표기의 **낱말 조각**과 같아야 걸린다.
    marks: set[str] = field(default_factory=set)
    #: 기종 이름들의 공통 앞부분(`dsox30`). 대장 표기가 **이것으로 시작**하면 걸린다.
    stem: str = ""


@dataclass
class _Catalog:
    makers: list[_Maker]
    models: list[_Model]
    series: list[_Series]


def _common_prefix(keys: list[str]) -> str:
    if len(keys) < 2:
        return ""
    first, last = min(keys), max(keys)
    size = 0
    while size < min(len(first), len(last)) and first[size] == last[size]:
        size += 1
    return first[:size]


def _catalog(db: Session) -> _Catalog:
    axis = db.scalar(select(Vocabulary.id).where(Vocabulary.slug == "manufacturer"))
    makers: dict[uuid.UUID, _Maker] = {}
    if axis is not None:
        for term in db.scalars(
            select(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == axis, VocabularyTerm.status == "active"
            )
        ):
            keys = {squash(term.value)}
            if term.code:
                keys.add(squash(term.code))
            makers[term.id] = _Maker(term.id, term.value, {key for key in keys if key})
        for alias in db.scalars(
            select(VocabularyAlias).where(
                VocabularyAlias.vocabulary_id == axis, VocabularyAlias.is_active.is_(True)
            )
        ):
            if alias.term_id in makers and squash(alias.value):
                makers[alias.term_id].keys.add(squash(alias.value))

    def label_of(maker_id: uuid.UUID | None) -> str:
        return makers[maker_id].label if maker_id in makers else ""

    rows = {
        row.id: row
        for row in db.scalars(
            select(EquipmentSeries).where(EquipmentSeries.deleted_at.is_(None))
        )
    }
    models: list[_Model] = []
    by_series: dict[uuid.UUID, list[str]] = collections.defaultdict(list)
    for model in db.scalars(select(EquipmentModel).where(EquipmentModel.deleted_at.is_(None))):
        series = rows.get(model.series_id)
        if series is None:
            continue
        key = squash(model.name)
        models.append(
            _Model(
                model.id,
                model.name,
                key,
                model.series_id,
                series.name,
                series.maker_term_id,
                label_of(series.maker_term_id),
                runs(model.name),
            )
        )
        if key:
            by_series[model.series_id].append(key)

    series_list: list[_Series] = []
    for one in rows.values():
        core = one.name
        if one.maker_term_id in makers:
            label = makers[one.maker_term_id].label
            core = re.sub(re.escape(label), " ", core, flags=re.IGNORECASE)
        marks = {squash(_GENERIC.sub(" ", core))}
        stem = _common_prefix(by_series.get(one.id, []))
        # 계열 이름에 든 기종 번호(「AllroundLine … (Z005 - Z250)」 의 `z250`) · 고유 이름
        # (`AllroundLine` · `InfiniiVision` 처럼 낱말 가운데 대문자가 있는 것). 숫자만인
        # 「300」 은 남의 계열에도 흔해서 뺀다.
        marks |= {piece for piece in runs(core) if re.search(r"[a-z]", piece)}
        marks |= {
            squash(word)
            for word in re.findall(r"\b[A-Za-z]*[a-z][A-Z][A-Za-z]*\b", core)
            if len(word) >= 5
        }
        series_list.append(
            _Series(
                one.id,
                one.name,
                one.maker_term_id,
                label_of(one.maker_term_id),
                {mark for mark in marks if len(mark) >= 3},
                stem if len(stem) >= STEM else "",
            )
        )
    return _Catalog(list(makers.values()), models, series_list)


def _match_makers(catalog: _Catalog, text: str | None) -> list[_Maker]:
    """제조사 표기 → 카탈로그 제조사. 같은 이름과 **포함 관계**를 함께 본다.

    「Zwick」 ⊂ 「ZwickRoell」, 「Keysight Technologies」 ⊃ 「Keysight」. 같은 이름만 보면
    대장의 옛 사명 · 긴 사명이 전부 「제조사 모름」 이 된다. 같은 이름의 값이 따로 있어도
    포함 관계를 버리지 않는다 — 그 값에 기종이 하나도 없으면 아무것도 못 찾는다.
    """
    key = squash(text)
    if not key:
        return []
    return [
        one
        for one in catalog.makers
        if key in one.keys
        or any(len(k) >= 4 and len(key) >= 4 and (k in key or key in k) for k in one.keys)
    ]


@dataclass
class _Verdict:
    case: str
    maker_known: bool
    models: list[tuple[_Model, float]]
    series: list[_Series]


#: 기종 번호가 낱말 단위로 그대로 든 것 — 같은 기종으로 본다(1.0 은 이름 전체가 같은 것).
SAME_CODE = 0.95
#: 제조사를 적었는데 카탈로그가 모르는 제조사일 때의 「비슷함」 하한. 대장의 제조사 칸에는
#: 대리점 이름도 들어가서 다른 회사 기종도 보긴 하되, 아주 닮은 것만 후보로 둔다.
SIMILAR_UNKNOWN_MAKER = 0.9


def _score(key: str, pieces: set[str], model: _Model) -> float:
    """대장 표기와 카탈로그 기종의 닮음(0~1).

    1.0 이름 전체가 같음 · 0.95 기종 번호가 낱말 단위로 그대로 듦(같은 기종으로 봄) ·
    0.9 글자 포함(연식 · 옵션 표기만 다름) · 그 밖은 문자열 유사도.
    """
    other = model.key
    if not other:
        return 0.0
    if key == other:
        return 1.0
    if key in model.runs or other in pieces:
        return SAME_CODE
    contained = len(key) >= 3 and len(other) >= 3 and (key in other or other in key)
    matcher = difflib.SequenceMatcher(None, key, other)
    if not contained and (
        matcher.real_quick_ratio() < SIMILAR or matcher.quick_ratio() < SIMILAR
    ):
        return 0.0
    return max(matcher.ratio(), 0.9 if contained else 0.0)


def _classify(catalog: _Catalog, maker_text: str | None, model_text: str | None) -> _Verdict:
    key = squash(model_text)
    makers = _match_makers(catalog, maker_text)
    maker_ids = {one.id for one in makers}
    known = bool(makers)
    if not key:
        return _Verdict("no_model", known, [], [])
    # 제조사를 알아보면 **그 제조사 안에서만** 찾는다. 다른 회사의 같은 이름은 다른 장비다.
    pool = (
        [one for one in catalog.models if one.maker_id in maker_ids]
        if known
        else catalog.models
    )
    pieces = runs(model_text)
    scored = sorted(
        ((one, round(_score(key, pieces, one), 3)) for one in pool),
        key=lambda pair: (-pair[1], pair[0].name),
    )
    # 제조사를 적었는데 못 알아본 경우의 같은 이름은 **같은 기종이라고 단정하지 않는다**
    # (「KS-500」 은 여러 회사에 있다) — 비슷한 기종으로 보여 주고 사람이 정한다.
    stated = bool(squash(maker_text))
    floor = SIMILAR_UNKNOWN_MAKER if stated and not known else SIMILAR
    same = [pair for pair in scored if pair[1] >= SAME_CODE]
    if same and (known or not stated):
        return _Verdict("exact", known, same[:CANDIDATES], [])
    near = [pair for pair in scored if pair[1] >= floor][:CANDIDATES]
    # **제조사 안에서 못 찾은 기종 번호는 다른 제조사에서도 찾는다.** 대장에는 옛 사명이
    # 그대로 남는다 — 「Agilent E4980A」(현 Keysight) · 「Olympus BX53M」(현 Evident).
    # 같은 번호라도 제조사가 다르면 같은 기종이라고 단정하지 않고 「비슷한 기종」 으로 둔다.
    # 짧거나 숫자만인 번호(「500」)는 회사마다 흔해서 이 단계에 안 태운다.
    if (
        known
        and not same
        and len(key) >= 5
        and re.search(r"[a-z]", key)
        and re.search(r"\d", key)
    ):
        elsewhere = [
            (one, SAME_CODE)
            for one in catalog.models
            if one.maker_id not in maker_ids and _score(key, pieces, one) >= SAME_CODE
        ]
        near = sorted(elsewhere + near, key=lambda pair: (-pair[1], pair[0].name))[:CANDIDATES]

    # 제조사를 모르면 계열 표지가 길 때만 믿는다 — 짧은 표지는 아무 데나 걸린다.
    shortest = 3 if known else 5
    series_pool = (
        [one for one in catalog.series if one.maker_id in maker_ids]
        if known
        else catalog.series
    )
    words = runs(model_text, codes=False) | {key}

    def evidence(one: _Series) -> int:
        hits = sum(1 for mark in one.marks if len(mark) >= shortest and mark in words)
        return hits + (1 if len(one.stem) >= shortest and key.startswith(one.stem) else 0)

    # **표지가 많이 맞는 계열이 먼저** — 「Z250 AllroundLine」 은 본체 계열(`z250` ·
    # `allroundline`)이 부속 계열(「… for AllroundLine」)보다 앞에 와야 한다.
    weighed = sorted(
        ((one, evidence(one)) for one in series_pool),
        key=lambda pair: (-pair[1], pair[0].name),
    )
    series = [one for one, hits in weighed if hits]
    if near:
        seen = {one.id for one in series}
        by_id = {one.id: one for one in catalog.series}
        for model, _ in near:
            if model.series_id not in seen and model.series_id in by_id:
                seen.add(model.series_id)
                series.append(by_id[model.series_id])
        return _Verdict("similar", known, near, series[:CANDIDATES])
    if series:
        return _Verdict("series_only", known, [], series[:CANDIDATES])
    return _Verdict("not_in_catalog", known, [], [])


def _require_admin(user: User) -> None:
    if not user.is_system_admin:
        raise Forbidden("TSC-EQUIPMENT-0045", "카탈로그 보강은 시스템 관리자 전용 작업.")


@dataclass
class _Category:
    path: str
    in_catalog: bool


def _categories(db: Session) -> dict[uuid.UUID, _Category]:
    """장비 분류 → 「상위 > 하위」 경로와 **카탈로그 정본에 있는 분류인가**(코드 유무)."""
    axis = db.scalar(select(Vocabulary.id).where(Vocabulary.slug == "equipment_category"))
    if axis is None:
        return {}
    terms = {
        row.id: row
        for row in db.scalars(
            select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == axis)
        )
    }
    out: dict[uuid.UUID, _Category] = {}
    for term in terms.values():
        parent = terms.get(term.parent_term_id) if term.parent_term_id else None
        path = f"{parent.value} > {term.value}" if parent else term.value
        out[term.id] = _Category(path, bool(term.code))
    return out


def _path(categories: dict[uuid.UUID, _Category], unit: Equipment) -> str:
    one = categories.get(unit.category_term_id) if unit.category_term_id else None
    return one.path if one else NO_CATEGORY


@dataclass
class _Group:
    key: str
    case: str
    maker_text: str | None
    model_text: str | None
    units: list[Equipment]
    verdict: _Verdict


def _groups(db: Session, categories: dict[uuid.UUID, _Category]) -> list[_Group]:
    catalog = _catalog(db)
    units = db.scalars(
        select(Equipment)
        .where(Equipment.deleted_at.is_(None), Equipment.model_id.is_(None))
        .order_by(Equipment.asset_no)
    )
    buckets: dict[str, list[Equipment]] = collections.defaultdict(list)
    for unit in units:
        model_text = clean(unit.model_text or "")
        if model_text:
            key = proposals.proposal_key(clean(unit.maker_text or "") or None, model_text)
        else:
            # 모델명이 없으면 묶을 열쇠가 없다 — 분류 · 제조사 표기로 나눠 보여 준다.
            key = f"no_model|{_path(categories, unit)}|{squash(unit.maker_text)}"
        buckets[key].append(unit)

    rejected = {
        (row.equipment_id, row.normalized)
        for row in db.scalars(
            select(EquipmentModelProposal).where(EquipmentModelProposal.status == "rejected")
        )
    }
    cache: dict[tuple[str, str], _Verdict] = {}
    out: list[_Group] = []
    for key, mine in buckets.items():
        maker = clean(mine[0].maker_text or "") or None
        model = clean(mine[0].model_text or "") or None
        pair = (squash(maker), squash(model))
        if pair not in cache:
            cache[pair] = _classify(catalog, maker, model)
        verdict = cache[pair]
        case = verdict.case
        # **관리자가 이미 「아니오」 한 것은 일감에서 뺀다.** 안 빼면 자작 장비가 매일 같은
        # 자리에 서 있고, 목록이 영영 0 이 안 되면 사람은 그 목록을 안 본다.
        if model and all((unit.id, key) in rejected for unit in mine):
            case = "excluded"
        out.append(_Group(key, case, maker, model, mine, verdict))
    order = {case: rank for rank, case in enumerate(CASES)}
    out.sort(key=lambda one: (order[one.case], -len(one.units), one.model_text or "", one.key))
    return out


def _workspaces(db: Session) -> dict[uuid.UUID, str]:
    return {row.id: row.name for row in db.scalars(select(Workspace))}


def _departments(workspaces: dict[uuid.UUID, str], units: list[Equipment]) -> list[str]:
    return sorted({workspaces.get(unit.owner_workspace_id, "") for unit in units} - {""})


def diagnose(
    db: Session,
    user: User,
    *,
    case: str | None = None,
    category_term_id: uuid.UUID | None = None,
    query: str | None = None,
) -> CatalogGapsOut:
    """미연결 장비 전부를 여섯 경우로 가른다 — 요약 · 분류별 표 · 묶음 목록.

    **요약과 분류별 표는 거르지 않는다.** 묶음 목록만 `case` · `category_term_id` · `query` 로
    거른다 — 거른 숫자로 요약이 바뀌면 사람은 전체 규모를 놓친다.
    """
    _require_admin(user)
    categories = _categories(db)
    groups = _groups(db, categories)
    workspaces = _workspaces(db)
    open_rows = {
        (row.equipment_id, row.normalized)
        for row in db.scalars(
            select(EquipmentModelProposal).where(
                EquipmentModelProposal.status == proposals.OPEN
            )
        )
    }

    by_case: collections.Counter[str] = collections.Counter()
    table: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    term_of: dict[str, uuid.UUID | None] = {}
    for group in groups:
        by_case[group.case] += len(group.units)
        for unit in group.units:
            path = _path(categories, unit)
            table[path][group.case] += 1
            term_of[path] = unit.category_term_id if path != NO_CATEGORY else None

    needle = squash(query)
    rows: list[CatalogGapGroupOut] = []
    for group in groups:
        if case and group.case != case:
            continue
        if category_term_id and all(
            unit.category_term_id != category_term_id for unit in group.units
        ):
            continue
        if needle and needle not in squash(
            f"{group.maker_text or ''}{group.model_text or ''}"
        ):
            continue
        rows.append(_group_out(group, categories, workspaces, open_rows))

    def in_catalog(path: str) -> bool:
        term_id = term_of.get(path)
        return bool(term_id and term_id in categories and categories[term_id].in_catalog)

    return CatalogGapsOut(
        units=sum(by_case.values()),
        by_case={one: by_case.get(one, 0) for one in CASES},
        case_labels=CASE_LABELS,
        by_category=[
            CatalogGapCategoryOut(
                category=path,
                category_term_id=term_of.get(path),
                in_catalog=in_catalog(path),
                total=sum(counts.values()),
                by_case={one: counts.get(one, 0) for one in CASES},
            )
            for path, counts in sorted(
                table.items(), key=lambda pair: (-sum(pair[1].values()), pair[0])
            )
        ],
        groups_total=len(groups),
        groups=rows,
    )


def _group_out(
    group: _Group,
    categories: dict[uuid.UUID, _Category],
    workspaces: dict[uuid.UUID, str],
    open_rows: set[tuple[uuid.UUID, str]],
) -> CatalogGapGroupOut:
    paths = collections.Counter(_path(categories, unit) for unit in group.units)
    return CatalogGapGroupOut(
        key=group.key,
        case=group.case,
        case_label=CASE_LABELS[group.case],
        maker_text=group.maker_text,
        model_text=group.model_text,
        maker_known=group.verdict.maker_known,
        count=len(group.units),
        categories=[path for path, _ in paths.most_common()],
        departments=_departments(workspaces, group.units),
        units=[
            CatalogGapUnitOut(
                id=unit.id,
                asset_no=unit.asset_no,
                name=unit.name,
                workspace=workspaces.get(unit.owner_workspace_id),
                category=_path(categories, unit) if unit.category_term_id else None,
            )
            for unit in group.units[:UNITS_SHOWN]
        ],
        models=[
            CatalogGapCandidateOut(
                id=model.id,
                label=model.name,
                detail=" · ".join(
                    part for part in (model.maker_label, model.series_name) if part
                )
                or None,
                score=score,
            )
            for model, score in group.verdict.models
        ],
        series=[
            CatalogGapCandidateOut(id=one.id, label=one.name, detail=one.maker_label or None)
            for one in group.verdict.series
        ],
        open_requests=sum(1 for unit in group.units if (unit.id, group.key) in open_rows),
    )


#: CSV 의 열. **사양서 조사의 출발점**이라 조사하는 사람이 읽는 순서로 둔다.
CSV_HEADER = (
    "경우",
    "제조사(표기)",
    "모델명(표기)",
    "제조사 카탈로그 등록",
    "대수",
    "장비 분류",
    "부서",
    "후보 기종",
    "후보 계열",
    "자산번호",
    "묶음 열쇠",
)


def to_csv(db: Session, user: User) -> str:
    """보강 목록 전체를 CSV 로 — 카탈로그 정본(`source/catalog`) 조사에 들고 가는 표.

    자산번호는 **전부** 싣는다(화면은 서른 대까지). 조사한 뒤 어느 장비가 이어질지를 표만
    보고 알아야 한다.
    """
    _require_admin(user)
    categories = _categories(db)
    workspaces = _workspaces(db)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for group in _groups(db, categories):
        paths = collections.Counter(_path(categories, unit) for unit in group.units)
        writer.writerow(
            [
                CASE_LABELS[group.case],
                group.maker_text or "",
                group.model_text or "",
                "있음" if group.verdict.maker_known else "없음",
                len(group.units),
                " · ".join(path for path, _ in paths.most_common()),
                " · ".join(_departments(workspaces, group.units)),
                " · ".join(f"{m.name} ({m.maker_label})" for m, _ in group.verdict.models),
                " · ".join(one.name for one in group.verdict.series),
                " ".join(unit.asset_no for unit in group.units),
                group.key,
            ]
        )
    # 엑셀이 한글을 깨지 않게 BOM 을 앞에 둔다(대장 서식과 같은 이유).
    return "﻿" + buffer.getvalue()


def csv_filename() -> str:
    return f"testscope-catalog-gaps-{date.today():%Y%m%d}.csv"


def _ensure_requests(db: Session, user: User, group: _Group) -> int:
    """그 묶음의 장비마다 열린 요청이 있게 한다. **새로 만들거나 다시 연 수**를 돌려준다.

    전에 「아니오」 로 닫은 요청이 있으면 다시 연다 — 요청 줄은 (장비, 열쇠)에 하나뿐이고,
    관리자가 마음을 바꾸는 일이 실제로 있다.
    """
    if not group.model_text:
        raise AppError(
            "TSC-EQUIPMENT-0047",
            "모델명이 없는 장비는 대조 불가. 장비 화면에서 모델명 입력 필요.",
        )
    have = {
        row.equipment_id: row
        for row in db.scalars(
            select(EquipmentModelProposal).where(
                EquipmentModelProposal.normalized == group.key
            )
        )
    }
    note = f"카탈로그 보강 목록에서 올림: {CASE_LABELS[group.case]}"
    if group.verdict.models:
        note += " · 후보 " + ", ".join(model.name for model, _ in group.verdict.models[:3])
    elif group.verdict.series:
        note += " · 계열 " + ", ".join(one.name for one in group.verdict.series[:3])
    touched = 0
    for unit in group.units:
        row = have.get(unit.id)
        if row is not None:
            if row.status != proposals.OPEN:
                row.status = proposals.OPEN
                row.model_id = None
                row.decided_at = None
                row.decided_by_id = None
                touched += 1
            continue
        db.add(
            EquipmentModelProposal(
                equipment_id=unit.id,
                maker_text=group.maker_text,
                model_text=group.model_text,
                normalized=group.key,
                note=note,
                status=proposals.OPEN,
                submitted_via=get_actor_token(),
                created_by_id=user.id,
            )
        )
        touched += 1
    db.flush()
    return touched


def request(db: Session, user: User, keys: list[str]) -> dict[str, Any]:
    """묶음들을 **기종 등록 요청으로 올린다** — 정하는 일은 요청 화면(또는 `resolve`)이 한다.

    모델명이 없는 묶음은 건너뛴다(요청은 모델명이 열쇠다). 이미 열린 요청은 다시 안 만든다.
    """
    _require_admin(user)
    wanted = set(keys)
    requested = 0
    skipped: list[str] = []
    found: set[str] = set()
    for group in _groups(db, _categories(db)):
        if group.key not in wanted:
            continue
        found.add(group.key)
        if not group.model_text:
            skipped.append(group.key)
            continue
        requested += _ensure_requests(db, user, group)
    db.commit()
    return {"requested": requested, "skipped": skipped, "missing": sorted(wanted - found)}


def resolve(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """한 묶음을 정한다 — **요청을 만든 뒤 그 요청을 정하는 것과 같다**(`proposals.decide`).

    `model_id`(있는 기종에 연결) · `series_id`+`name`(그 계열에 기종을 세우고 연결) ·
    `reject`(카탈로그 대상 아님) 중 **하나만.** 요청 흐름을 지나게 둔 것은 기록 때문이다 —
    누가 언제 무엇으로 정했는지가 요청 줄과 감사에 남고, 한 대가 막혀도 나머지는 이어진다.
    """
    _require_admin(user)
    key = str(payload.get("key") or "")
    group = next((one for one in _groups(db, _categories(db)) if one.key == key), None)
    if group is None:
        raise NotFound(
            "TSC-EQUIPMENT-0046", "해당 묶음을 찾을 수 없음(이미 연결됐을 수 있음)."
        )
    # **여기서 커밋하지 않는다.** 정하기가 실패하면(인자 둘 · 없는 기종) 방금 만든 요청도 함께
    # 사라져야 한다 — 남으면 관리자가 누르지도 않은 요청이 목록에 선다.
    _ensure_requests(db, user, group)
    decision = {
        name: payload.get(name) for name in ("model_id", "series_id", "name", "reject")
    }
    return proposals.decide(db, user, {"normalized": group.key, **decision})
