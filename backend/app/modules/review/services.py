"""검토함 로직 — 물음마다 후보를 세우고, 고르면 **기존 규칙대로** 적용한다.

네 물음이 있다(`QUEUES`). 후보를 세우는 것(`refresh`)과 고른 것을 적용하는 것(`decide`)이
물음마다 다르고, 나머지(목록·건너뛰기·감사)는 같다.

## 후보는 어디서 오나

- **파생** — 규격의 시험 항목은 그 규격을 인용한 계열이 하는 시험들이 곧 후보다. 정본 없이도
  선다.
- **정본** — `source/catalog/proposals/<queue>.json` 의 추천·근거·이미 내린 결정. 개발자가
  미리 적어 두고 배포 패키지에 실려 운영으로 간다. 결정된 줄은 여기서 **적용까지** 한다 —
  그래야 개발 DB 에서 정한 것이 운영에 다시 묻지 않는다.

## 적용은 기존 규칙을 부른다

규격의 시험 항목을 정하면 `promote_pending` 이 인용 계열에 붙이고, 사양을 정의로 올리면
`free_specs.promote` 가 같은 원본 키의 줄을 함께 옮긴다. 검토함이 따로 규칙을 갖지 않는다 —
두 벌이면 화면에서 정한 것과 검토함에서 정한 것이 다른 결과를 낸다.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import REPO_DIR
from app.modules.accounts.models import User
from app.modules.attributes import services as attributes
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.equipment import free_specs
from app.modules.equipment.models import EquipmentModel, EquipmentSeries, ModelFreeSpec
from app.modules.methods.models import TestMethod
from app.modules.methods.services import detach_citations, merge_into, promote_pending
from app.modules.properties.models import TestItemProperty
from app.modules.review.facts import Sheet
from app.modules.review.models import ReviewProposal, ReviewVote
from app.modules.review.schemas import (
    CandidateOut,
    FactOut,
    ProposalOut,
    QueueOut,
    VoteOut,
)
from app.modules.test_items.models import (
    EquipmentTestItem,
    SeriesPendingMethod,
    SeriesTestItem,
    SeriesTestItemMethod,
    TestItemConditionKey,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.vocabulary.specs import SpecDefinition, SpecGroup
from app.shared import audit
from app.shared.attribute_text import display_attribute
from app.shared.errors import AppError, Forbidden, NotFound
from app.shared.text import clean, compare_key, method_key

#: 정본의 후보·결정 파일이 사는 곳. 반입 스크립트의 카탈로그 뿌리와 같다.
PROPOSALS_DIR = REPO_DIR / "source" / "catalog" / "proposals"


@dataclass(frozen=True)
class Queue:
    key: str
    label: str
    description: str
    multi: bool
    """여러 개를 고르나(검색축) — 아니면 하나."""
    link: str
    """상세로 가는 링크 서식. `{id}` 가 subject_id."""
    local: bool = False
    """이 설치에서 생기는 물음인가 — 정본(`proposals/*.json`)과 주고받지 않는다.

    초안 속성이 그렇다: 값을 적는 사람이 새 이름을 쓰면 생기고, 자동 key 는 설치마다 다른
    난수다. 정본에 내보내면 다른 설치에서 아무것도 안 가리키는 결정이 쌓인다.
    """


QUEUES: dict[str, Queue] = {
    "method_test_items": Queue(
        "method_test_items",
        "규격의 시험 항목",
        "카탈로그가 인용한 규격이 어느 시험의 것인지. 정하면 인용한 계열에 자동으로 붙는다.",
        False,
        "/methods/{id}",
    ),
    "test_item_axes": Queue(
        "test_item_axes",
        "시험 항목의 검색 조건",
        "이 시험을 찾을 때 무슨 조건을 묻나. 안 정하면 조건 전부를 묻는다. 여러 개를 고른다.",
        True,
        "/catalog/test-items/{id}",
    ),
    "property_links": Queue(
        "property_links",
        "물성 연결 검토",
        "이 시험으로 이 물성이 나오는 게 맞나. 아니면 연결을 끊는다.",
        False,
        "/properties",
    ),
    "free_spec_definitions": Queue(
        "free_spec_definitions",
        "사양 정의 승격",
        "여러 기종에 같은 이름으로 쌓인 「기종 고유 사양」 을 정식 사양 정의로 승격할지.",
        False,
        "/catalog/equipment-models/{id}",
    ),
    "method_cleanup": Queue(
        "method_cleanup",
        "규격 목록 정리",
        "규격군 이름만 인용된 것(「ASTM」 「IEC 60068」)은 지우고, 표기만 다른 것은 합친다.",
        False,
        "/methods/{id}",
    ),
    "test_item_properties": Queue(
        "test_item_properties",
        "시험 항목의 측정 물성",
        "물성이 하나도 안 이어진 시험 항목 — 이 시험으로 얻는 물성이 있으면 잇는다. 여러 개.",
        True,
        "/catalog/test-items/{id}",
    ),
    "condition_axes": Queue(
        "condition_axes",
        "신규 검색 조건",
        "지금 검색 조건에 없어 검색이 못 답하는 것(점도·압력·파장 …)을 조건으로 세울지.",
        False,
        "/conditions",
    ),
    "series_standards": Queue(
        "series_standards",
        "계열 인용 규격 추가",
        "제조사 웹·대리점·논문이 이 계열과 함께 적은 규격 — 카탈로그 PDF 에는 없던 것. "
        "이 계열이 정말 하는 것만 고른다. 여러 개.",
        True,
        "/catalog/equipment-series/{id}",
    ),
    "series_test_items": Queue(
        "series_test_items",
        "계열 시험 항목 추가",
        "논문이 이 기종으로 했다고 적은 시험, 제조사 페이지가 「이런 시험에 쓴다」 고 한 "
        "시험 — 카탈로그에 없던 것. 인용문을 읽고 정말 하는 것만 고른다. 여러 개.",
        True,
        "/catalog/equipment-series/{id}",
    ),
    "series_summary": Queue(
        "series_summary",
        "계열 소개문",
        "제조사 페이지의 응용 문장 — 고른 것이 계열 소개 뒤에 붙는다. 무엇에 쓰는지 말하는 "
        "문장만. 여러 개.",
        True,
        "/catalog/equipment-series/{id}",
    ),
    "attribute_drafts": Queue(
        "attribute_drafts",
        "초안 속성 정리",
        "값을 적는 사람이 새 이름을 써서 생긴 초안 속성 — 같은 뜻인 속성에 합칠지, 정식으로 "
        "올릴지, 아직 둘지. 초안은 온톨로지 밖이라 두면 검색·판정에 안 쓰인다.",
        False,
        "/attribute-definitions/reliability-test",
        local=True,
    ),
    "test_item_aliases": Queue(
        "test_item_aliases",
        "시험 항목의 별칭",
        "이 시험을 부르는 다른 이름 — 영문 라벨의 조각, 이름의 조각, 이 시험의 규격 제목에 "
        "되풀이되는 구절. 고른 것이 별칭이 되어 찾기(resolve)와 검토함의 제목 일치에 쓰인다. "
        "여러 개. 후보에 없는 표기는 직접 적는다.",
        True,
        "/catalog/test-items/{id}",
    ),
}

#: 고정 후보 — 물음이 예/아니오 꼴인 큐.
YES_NO: dict[str, list[dict[str, Any]]] = {
    "property_links": [
        {"code": "confirm", "label": "맞다 — 확인으로 올린다"},
        {"code": "reject", "label": "아니다 — 연결을 끊는다"},
    ],
    "free_spec_definitions": [
        {"code": "promote", "label": "정의로 올린다"},
        {"code": "keep", "label": "기종만의 사양으로 둔다"},
    ],
    "condition_axes": [
        {"code": "create", "label": "조건을 만든다"},
        {"code": "skip", "label": "만들지 않는다"},
    ],
}


def _require_admin(user: User) -> None:
    if not user.is_system_admin:
        raise Forbidden("TSC-REVIEW-0001", "검토는 시스템 관리자만 합니다.")


def _axis_terms(db: Session, slug: str) -> dict[str, VocabularyTerm]:
    axis_id = db.scalar(select(Vocabulary.id).where(Vocabulary.slug == slug))
    if axis_id is None:
        return {}
    return {
        t.code: t
        for t in db.scalars(
            select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == axis_id)
        )
        if t.code
    }


# --- 정본 파일 -----------------------------------------------------------------


def load_file(queue: str, root: Path = PROPOSALS_DIR) -> dict[str, dict[str, Any]]:
    """`proposals/<queue>.json` 의 줄을 subject 로 찾게. 없으면 빈 것."""
    path = root / f"{queue}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["subject"]): row for row in data.get("rows") or []}


def _mark(
    candidates: list[dict[str, Any]], recommended: str | list[str] | None, reason: str | None
) -> list[dict[str, Any]]:
    wanted = set([recommended] if isinstance(recommended, str) else (recommended or []))
    out: list[dict[str, Any]] = []
    shown = False
    for one in candidates:
        picked = one["code"] in wanted
        # 근거는 **한 번만** — 축 셋을 추천하면서 같은 문장을 세 번 붙이면 읽기만 길어진다.
        out.append(
            {
                "code": one["code"],
                "label": one["label"],
                "recommended": picked,
                "reason": (
                    ((reason if not shown else None) if reason else one.get("reason"))
                    if picked
                    else one.get("reason")
                ),
                "sources": list(one.get("sources") or []),
            }
        )
        shown = shown or picked
    return out


def _upsert(
    db: Session,
    queue: str,
    subject_key: str,
    *,
    subject_id: uuid.UUID | None,
    subject_label: str,
    context: str | None,
    candidates: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
    question: str | None = None,
    facts: list[dict[str, Any]] | None = None,
) -> ReviewProposal:
    row = db.scalar(
        select(ReviewProposal).where(
            ReviewProposal.queue == queue, ReviewProposal.subject_key == subject_key
        )
    )
    if row is None:
        # status 를 여기서 준다 — 열의 기본값은 flush 때 붙어, 그 전에 읽으면 None 이다.
        row = ReviewProposal(queue=queue, subject_key=subject_key, status="open")
        db.add(row)
    # 후보·근거는 정본이 바뀌면 따라 바뀐다. 결정은 안 건드린다.
    row.subject_id = subject_id
    row.subject_label = subject_label[:300]
    row.context = context
    row.candidates = candidates
    row.payload = payload or {}
    row.question = question
    row.facts = facts or []
    return row


def _settle(db: Session, row: ReviewProposal, choice: list[str], by: str) -> None:
    """다른 곳(화면·정본)에서 이미 정해진 것을 결정으로 적어 둔다."""
    if row.status == "decided":
        return
    row.status = "decided"
    row.choice = choice
    row.followed = _followed(row.candidates, choice)
    row.decided_by_label = by
    row.decided_at = datetime.now(UTC)


def _context(base: str | None, filed_row: dict[str, Any] | None) -> str | None:
    """대상을 이해하는 한 줄 + 정본의 귀띔(`hint`). 귀띔은 추천이 없을 때의 근거다 —
    「규격군 이름이라 특정 시험이 아니다」 처럼, 왜 추천을 안 붙였는지를 말한다."""
    hint = (filed_row or {}).get("hint")
    parts = [one for one in (base, hint) if one]
    return " — ".join(parts) if parts else None


def _free_label(label: str, source_key: str, unit: str) -> str:
    """「작동력 (actuating_force_cN · cN)」. 라벨이 원본 키 그대로면 한 번만 —
    「actuating_force_cN (actuating_force_cN)」 은 아니다."""
    if label == source_key:
        return f"{source_key} [{unit}]" if unit else source_key
    inner = " · ".join(part for part in (source_key, unit) if part)
    return f"{label} ({inner})"


def _gone(row: ReviewProposal, why: str) -> None:
    """대상이 없어졌다 — 정한 것이 아니라 **물음 자체가 사라진 것**이다. 남은 수에서 빠지고,
    「정함」 과 섞이지 않게 따로 센다. 되돌릴 수 없다(대상이 없으니)."""
    if row.status in ("decided", "gone"):
        return
    row.status = "gone"
    row.choice = None
    row.followed = None
    row.decided_by_label = why
    row.decided_at = datetime.now(UTC)


def _sweep_gone(
    db: Session, queue: str, alive: set[str], why: str, *, by_key: bool = True
) -> None:
    """열린·건너뛴 줄 중 대상이 사라진 것을 「대상 없어짐」 으로 닫는다."""
    for row in db.scalars(
        select(ReviewProposal).where(
            ReviewProposal.queue == queue, ReviewProposal.status.in_(("open", "skipped"))
        )
    ):
        marker = row.subject_key if by_key else str(row.subject_id)
        if marker not in alive:
            _gone(row, why)


def _followed(candidates: list[dict[str, Any]], choice: list[str]) -> bool | None:
    recommended = {one["code"] for one in candidates if one.get("recommended")}
    if not recommended:
        return None
    return set(choice) == recommended


# --- 후보 세우기 ---------------------------------------------------------------


def refresh(db: Session, root: Path = PROPOSALS_DIR) -> dict[str, int]:
    """네 큐의 후보를 다시 세운다 — 파생 + 정본. 이미 정해진 것은 결정으로 적는다.

    돌려주는 것은 {큐: 열린 수}.
    """
    counts: dict[str, int] = {}
    # 줄마다 붙일 물음·근거 자료의 사전 — 한 번 읽어 열 큐가 같이 쓴다.
    sheet = Sheet(db)
    _refresh_method_test_items(db, load_file("method_test_items", root), sheet)
    _refresh_test_item_axes(db, load_file("test_item_axes", root), sheet)
    _refresh_property_links(db, load_file("property_links", root), sheet)
    _refresh_free_spec_definitions(db, load_file("free_spec_definitions", root), sheet)
    _refresh_method_cleanup(db, load_file("method_cleanup", root), sheet)
    _refresh_test_item_properties(db, load_file("test_item_properties", root), sheet)
    _refresh_condition_axes(db, load_file("condition_axes", root))
    _refresh_series_standards(db, load_file("series_standards", root), sheet)
    _refresh_series_test_items(db, load_file("series_test_items", root), sheet)
    _refresh_series_summary(db, load_file("series_summary", root), sheet)
    _refresh_test_item_aliases(db, load_file("test_item_aliases", root), sheet)
    _refresh_attribute_drafts(db)
    db.flush()
    for key in QUEUES:
        counts[key] = (
            db.scalar(
                select(func.count())
                .select_from(ReviewProposal)
                .where(ReviewProposal.queue == key, ReviewProposal.status == "open")
            )
            or 0
        )
    return counts


def _refresh_method_test_items(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    items = _axis_terms(db, "test_item")
    by_id = {t.id: t for t in items.values()}
    citing: dict[uuid.UUID, set[uuid.UUID]] = {}
    for pending in db.scalars(select(SeriesPendingMethod)):
        citing.setdefault(pending.method_id, set()).add(pending.series_id)
    series_items: dict[uuid.UUID, set[uuid.UUID]] = {}
    for link in db.scalars(select(SeriesTestItem)):
        series_items.setdefault(link.series_id, set()).add(link.test_item_term_id)
    series_names: dict[uuid.UUID, str] = {
        sid: name for sid, name in db.execute(select(EquipmentSeries.id, EquipmentSeries.name))
    }

    methods = list(db.scalars(select(TestMethod).where(TestMethod.deleted_at.is_(None))))
    for method in methods:
        key = method_key(method.code)
        filed_row = filed.get(method.code) or filed.get(key)
        cited = citing.get(method.id, set())
        derived: set[uuid.UUID] = set()
        for series_id in cited:
            derived |= series_items.get(series_id, set())
        # 후보마다 **왜 이 후보인지** — 「인용한 계열 X 가 하는 시험」 「다른 판이 이미 이
        # 시험」.
        # 근거 없는 후보 목록은 첫 보기를 누르게 할 뿐이다.
        reasons: dict[str, str] = {}
        for series_id in sorted(cited, key=lambda s: series_names.get(s, "")):
            for t in series_items.get(series_id, set()):
                code = by_id[t].code if t in by_id else None
                if code and code not in reasons:
                    reasons[code] = (
                        f"인용한 계열 「{series_names.get(series_id, '')}」 가 하는 시험"
                    )
        codes: list[str] = list(reasons)
        for code in (filed_row or {}).get("candidates") or []:
            if code in items and code not in codes:
                codes.append(code)
        edition_codes = sheet.edition_codes(method)
        for code, why in edition_codes:
            if code in items and code not in codes:
                codes.append(code)
            reasons.setdefault(code, why)
        del derived
        if method.test_item_term_id is not None:
            # 이미 정해졌다 — 열린 검토가 있었으면 결정으로 닫는다.
            row = db.scalar(
                select(ReviewProposal).where(
                    ReviewProposal.queue == "method_test_items",
                    ReviewProposal.subject_key == key,
                )
            )
            if row is not None and row.status == "open":
                term = by_id.get(method.test_item_term_id)
                _settle(db, row, [term.code] if term and term.code else [], "화면에서 정함")
            continue
        decided = (filed_row or {}).get("decided")
        if not codes and not decided:
            continue
        recommended = (filed_row or {}).get("recommended")
        reason = (filed_row or {}).get("reason")
        if not recommended and len({c for c, _ in edition_codes}) == 1:
            # 정본이 추천을 못 했어도 다른 판이 이미 정해져 있으면 그것이 가장 강한 근거다.
            recommended, reason = edition_codes[0]
        if method.title != method.code:
            # 그다음 근거는 **규격 제목의 글자** — 「Rockwell hardness testing of …」 에는
            # 로크웰 경도의 영문 이름이 들어 있다. 한 시험만 걸리면 추천, 여럿이면 후보만.
            matched = [
                (term, name) for term, name in sheet.title_matches(method.title) if term.code
            ]
            for term, name in matched:
                assert term.code is not None
                if term.code not in codes:
                    codes.append(term.code)
                reasons.setdefault(term.code, f"규격 제목에 「{name}」 이 있음")
            if not recommended and len(matched) == 1:
                recommended = matched[0][0].code
                reason = f"규격 제목에 「{matched[0][1]}」 이 있음"
        candidates = _mark(
            [
                {"code": code, "label": items[code].value, "reason": reasons.get(code)}
                for code in sorted(set(codes))
            ],
            recommended,
            reason,
        )
        names = sorted(series_names.get(s, "") for s in cited)[:2]
        context = _context(
            ("인용: " + " · ".join(n for n in names if n)) if names else None, filed_row
        )
        question = (
            f"규격 「{method.code}」 는 어느 시험의 규격입니까? 정하면 이 규격을 인용한 계열 "
            f"{len(cited)}개의 그 시험에 붙고, 이 규격 기준으로 장비를 찾을 수 있게 됩니다."
        )
        row = _upsert(
            db,
            "method_test_items",
            key,
            subject_id=method.id,
            subject_label=method.code
            if method.title == method.code
            else f"{method.code} — {method.title}",
            context=context,
            candidates=candidates,
            question=question,
            facts=sheet.method_facts(
                method, sorted(cited, key=lambda s: series_names.get(s, ""))
            ),
        )
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(
        db, "method_test_items", {method_key(m.code) for m in methods}, "규격이 지워짐"
    )


def _refresh_test_item_axes(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    items = _axis_terms(db, "test_item")
    keys = {k.key: k for k in db.scalars(select(ConditionKey))}
    have: dict[uuid.UUID, set[uuid.UUID]] = {}
    for link in db.scalars(select(TestItemConditionKey)):
        have.setdefault(link.test_item_term_id, set()).add(link.condition_key_id)
    for code, term in items.items():
        filed_row = filed.get(code)
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "test_item_axes", ReviewProposal.subject_key == code
            )
        )
        if have.get(term.id):
            if row is not None and row.status == "open":
                chosen = [k.key for k in keys.values() if k.id in have[term.id]]
                _settle(db, row, sorted(chosen), "화면에서 정함")
            continue
        if filed_row is None:
            continue
        # 축마다 근거 — 이 시험을 하는 계열의 기종 사양에 실제로 있는 조건, 이 시험의 규격이
        # 요구 조건으로 적은 조건. 정본이 추천을 안 했으면 이 근거로 추천한다(규격이 적었거나
        # 두 기종 이상에 사양이 있는 축).
        evidence = sheet.axis_evidence(term)
        axis_reasons: dict[str, str] = {}
        strong: list[str] = []
        for k in keys.values():
            models_n, methods_n = evidence.get(k.id, (0, 0))
            parts = []
            if methods_n:
                parts.append(f"이 시험의 규격 {methods_n}건이 요구 조건으로 적음")
            if models_n:
                parts.append(f"이 시험을 하는 계열의 기종 사양에 {models_n}기종")
            if parts:
                axis_reasons[k.key] = " · ".join(parts)
            if methods_n or models_n >= 2:
                strong.append(k.key)
        recommended = filed_row.get("recommended") or strong or None
        reason = filed_row.get("reason") if filed_row.get("recommended") else None
        candidates = _mark(
            [
                {"code": k.key, "label": k.label, "reason": axis_reasons.get(k.key)}
                for k in keys.values()
                if k.is_active
            ],
            recommended,
            reason,
        )
        row = _upsert(
            db,
            "test_item_axes",
            code,
            subject_id=term.id,
            subject_label=term.value,
            context=_context(filed_row.get("context"), filed_row),
            candidates=candidates,
            question=(
                f"「{term.value}」 이 되는 장비를 찾을 때 어떤 조건을 물어야 합니까? 고른 "
                "조건만 검색 화면에 뜹니다(안 정하면 열두 조건을 전부 묻습니다). 여러 개를 "
                "고르고, "
                "조건이 필요 없는 시험이면 아무것도 고르지 않습니다."
            ),
            facts=sheet.test_item_facts(term, with_conditions=True),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "test_item_axes", set(items), "시험 항목이 지워짐")


def _refresh_property_links(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    if not filed:
        return
    items = _axis_terms(db, "test_item")
    props = _axis_terms(db, "property")
    links = {
        (link.test_item_term_id, link.property_term_id): link
        for link in db.scalars(select(TestItemProperty))
    }
    for subject, filed_row in filed.items():
        item_code, _, prop_code = subject.partition(":")
        item, prop = items.get(item_code), props.get(prop_code)
        if item is None or prop is None:
            continue
        link = links.get((item.id, prop.id))
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "property_links", ReviewProposal.subject_key == subject
            )
        )
        if link is None:
            # 연결이 없어졌다 — 다른 화면에서 지웠을 것이다. 「아니다」 로 정한 것과 구별한다:
            # 거기서 지운 사람의 판단은 감사에 있고, 여기서 지어 붙이면 두 기록이 어긋난다.
            if row is not None:
                _gone(row, "연결이 없어짐(다른 화면에서 지움)")
            continue
        if link.status == "confirmed":
            if row is not None and row.status == "open":
                _settle(db, row, ["confirm"], "화면에서 정함")
            continue
        row = _upsert(
            db,
            "property_links",
            subject,
            subject_id=link.id,
            subject_label=f"{item.value} → {prop.value}",
            context=_context(filed_row.get("context"), filed_row),
            question=(
                f"「{item.value}」 시험으로 「{prop.value}」 이(가) 나옵니까? 맞으면 확인 "
                "표시가 붙고, 아니면 연결이 지워져 물성으로 찾을 때 이 시험이 빠집니다."
            ),
            facts=sheet.test_item_facts(item)
            + sheet.property_facts(prop, except_item=item.id),
            candidates=_mark(
                YES_NO["property_links"], filed_row.get("recommended"), filed_row.get("reason")
            ),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


def _refresh_free_spec_definitions(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    if not filed:
        return
    groups = {g.slug: g for g in db.scalars(select(SpecGroup))}
    for subject, filed_row in filed.items():
        source_key, _, unit = subject.partition("|")
        stmt = select(ModelFreeSpec).where(ModelFreeSpec.source_key == source_key)
        if unit:
            stmt = stmt.where(ModelFreeSpec.unit == unit)
        rows = list(db.scalars(stmt))
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "free_spec_definitions",
                ReviewProposal.subject_key == subject,
            )
        )
        spec = dict(filed_row.get("definition") or {})
        if not rows:
            # 남은 줄이 없다 — 올렸거나 지웠다. 그 키의 정의가 있으면 올린 것, 없으면 지운 것.
            if row is not None and row.status in ("open", "skipped"):
                promoted = spec.get("key") and db.scalar(
                    select(SpecDefinition.id).where(SpecDefinition.key == spec["key"])
                )
                if promoted:
                    _settle(db, row, ["promote"], "화면에서 정함")
                else:
                    _gone(row, "사양 줄이 없어짐(다른 화면에서 지움)")
            continue
        group = groups.get(spec.get("group") or "")
        payload = {
            "key": spec.get("key"),
            "label": spec.get("label"),
            "group_id": str(group.id) if group else None,
            "group": spec.get("group"),
            "kind": spec.get("kind") or "number",
            "unit": spec.get("unit") or unit,
            "models": len({one.model_id for one in rows}),
        }
        sample = rows[0]
        row = _upsert(
            db,
            "free_spec_definitions",
            subject,
            subject_id=sample.model_id,
            subject_label=_free_label(sample.label, source_key, unit),
            context=_context(
                f"{payload['models']}개 기종 · 예: {sample.value_text[:60]}"
                + (
                    f" → 정의 「{spec.get('label')}」 ({spec.get('kind')}, {payload['unit']})"
                    if spec
                    else ""
                ),
                filed_row,
            ),
            candidates=_mark(
                YES_NO["free_spec_definitions"],
                filed_row.get("recommended"),
                filed_row.get("reason"),
            ),
            payload=payload,
            question=(
                f"기종 {payload['models']}개에 「{sample.label}」 이라는 이름으로 적힌 사양을 "
                "정식 사양 정의로 올립니까? 올리면 그 값들이 정의 아래로 옮겨 가고 "
                "검색·비교가 됩니다."
            ),
            facts=_free_spec_facts(sheet, rows),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


def _free_spec_facts(sheet: Sheet, rows: list[ModelFreeSpec]) -> list[dict[str, Any]]:
    """어느 기종들에 무슨 값으로 적혔나 — 「정의로 올릴 만한 사양인가」 의 근거."""
    models = {
        m.id: m
        for m in sheet.db.scalars(
            select(EquipmentModel).where(EquipmentModel.id.in_({one.model_id for one in rows}))
        )
    }
    names: set[str] = set()
    for one in rows:
        model = models.get(one.model_id)
        if model is None:
            continue
        series = sheet.series().get(model.series_id)
        maker = sheet.term_value(series.maker_term_id) if series else None
        names.add(" ".join(p for p in (maker, model.name) if p))
    shown = sorted(names)
    out = [
        {
            "label": "기종",
            "value": " · ".join(shown[:4])
            + (f" 외 {len(shown) - 4}" if len(shown) > 4 else ""),
            "link": None,
        }
    ]
    values = list(dict.fromkeys(one.value_text.strip() for one in rows if one.value_text))
    if values:
        out.append({"label": "값 예", "value": " · ".join(values[:4]), "link": None})
    return out


def _refresh_method_cleanup(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    """규격 목록 정리 — 정본이 고른 규격만. 후보: 둔다 · 지운다 · 「…」 로 합친다."""
    methods = {
        method_key(m.code): m
        for m in db.scalars(select(TestMethod).where(TestMethod.deleted_at.is_(None)))
    }
    for subject, filed_row in filed.items():
        key = method_key(subject)
        method = methods.get(key)
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "method_cleanup", ReviewProposal.subject_key == key
            )
        )
        if method is None:
            # 이미 지웠거나 합쳤다.
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, ["delete"], "화면에서 정함")
            continue
        candidates: list[dict[str, Any]] = [{"code": "keep", "label": "그대로 둔다"}]
        for other in filed_row.get("merge_into") or []:
            target = methods.get(method_key(other))
            if target is not None and target.id != method.id:
                candidates.append(
                    {"code": f"merge:{target.code}", "label": f"「{target.code}」 로 합친다"}
                )
        candidates.append({"code": "delete", "label": "목록에서 지운다"})
        cited = (
            db.scalar(
                select(func.count())
                .select_from(SeriesPendingMethod)
                .where(SeriesPendingMethod.method_id == method.id)
            )
            or 0
        )
        used = (
            db.scalar(
                select(func.count())
                .select_from(EquipmentTestItem)
                .where(EquipmentTestItem.method_id == method.id)
            )
            or 0
        )
        context = f"인용한 계열 {cited} · 이 규격을 건 보유 장비 시험 항목 {used}"
        row = _upsert(
            db,
            "method_cleanup",
            key,
            subject_id=method.id,
            subject_label=method.code,
            context=_context(context, filed_row),
            candidates=_mark(
                candidates, filed_row.get("recommended"), filed_row.get("reason")
            ),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "method_cleanup", set(methods), "규격이 지워짐")


def _refresh_test_item_properties(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    """물성이 없는 시험 항목 — 정본이 추천한 물성이 후보, 나머지는 직접 고르기."""
    items = _axis_terms(db, "test_item")
    props = _axis_terms(db, "property")
    linked = set(db.scalars(select(TestItemProperty.test_item_term_id)))
    for code, filed_row in filed.items():
        term = items.get(code)
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "test_item_properties",
                ReviewProposal.subject_key == code,
            )
        )
        if term is None:
            if row is not None:
                _gone(row, "시험 항목이 지워짐")
            continue
        if term.id in linked:
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, [], "화면에서 정함")
            continue
        wanted = filed_row.get("recommended") or []
        candidates = [
            {"code": prop, "label": props[prop].value} for prop in wanted if prop in props
        ]
        row = _upsert(
            db,
            "test_item_properties",
            code,
            subject_id=term.id,
            subject_label=term.value,
            context=_context(filed_row.get("context"), filed_row),
            candidates=_mark(candidates, wanted, filed_row.get("reason")),
            question=(
                f"「{term.value}」 시험으로 얻는 물성은 무엇입니까? 지금은 물성이 하나도 "
                "이어져 있지 않아 물성으로 찾을 때 이 시험이 안 나옵니다. 합격/불합격만 내는 "
                "시험이면 아무것도 고르지 않습니다."
            ),
            facts=sheet.test_item_facts(term),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


def _refresh_condition_axes(db: Session, filed: dict[str, dict[str, Any]]) -> None:
    """새 검색축 — 정본이 제안한 키. 이미 있으면 닫는다."""
    keys = {k.key for k in db.scalars(select(ConditionKey))}
    for key, filed_row in filed.items():
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "condition_axes", ReviewProposal.subject_key == key
            )
        )
        if key in keys:
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, ["create"], "화면에서 정함")
            continue
        axis = dict(filed_row.get("axis") or {})
        definitions = list(filed_row.get("definitions") or [])
        items = list(filed_row.get("test_items") or [])
        payload = {
            "key": key,
            "label": axis.get("label") or key,
            "dimension": axis.get("dimension") or "",
            "unit": axis.get("unit") or "",
            "definitions": definitions,
            "test_items": items,
        }
        context = (
            f"{axis.get('label')} ({axis.get('unit')}) — 이을 사양 정의 {len(definitions)}"
            f" · 물을 시험 항목 {len(items)}"
        )
        row = _upsert(
            db,
            "condition_axes",
            key,
            subject_id=None,
            subject_label=f"{axis.get('label') or key} [{axis.get('unit') or '-'}]",
            context=_context(context, filed_row),
            candidates=_mark(
                YES_NO["condition_axes"], filed_row.get("recommended"), filed_row.get("reason")
            ),
            payload=payload,
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


# --- 적용 -----------------------------------------------------------------------


def _series_of_row(
    db: Session, makers: dict[str, VocabularyTerm], filed_row: dict[str, Any]
) -> EquipmentSeries | None:
    """정본 줄의 `series`(이름) + `manufacturer` 로 계열을 찾는다 — 반입이 그 둘로 만든다."""
    maker = makers.get(str(filed_row.get("manufacturer") or ""))
    return db.scalar(
        select(EquipmentSeries).where(
            EquipmentSeries.normalized
            == compare_key(clean(str(filed_row.get("series") or ""))),
            EquipmentSeries.maker_term_id.is_(None)
            if maker is None
            else EquipmentSeries.maker_term_id == maker.id,
        )
    )


def _refresh_series_test_items(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    """계열이 하는 시험 더하기 — 정본의 후보 중 계열에 아직 없는 시험 항목."""
    makers = _axis_terms(db, "manufacturer")
    items = _axis_terms(db, "test_item")
    have: dict[uuid.UUID, set[uuid.UUID]] = {}
    for series_id, term_id in db.execute(
        select(SeriesTestItem.series_id, SeriesTestItem.test_item_term_id)
    ):
        have.setdefault(series_id, set()).add(term_id)
    alive: set[str] = set()
    for subject, filed_row in filed.items():
        series = _series_of_row(db, makers, filed_row)
        if series is None:
            continue
        alive.add(subject)
        mine = have.get(series.id, set())
        candidates = _mark(
            [
                {
                    "code": one["code"],
                    "label": items[one["code"]].value,
                    "reason": one.get("reason"),
                    "sources": one.get("sources") or [],
                }
                for one in (filed_row.get("candidates") or [])
                if isinstance(one, dict)
                and one["code"] in items
                and items[one["code"]].id not in mine
            ],
            filed_row.get("recommended"),
            filed_row.get("reason"),
        )
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "series_test_items",
                ReviewProposal.subject_key == subject,
            )
        )
        if not candidates:
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, [], "이미 있음")
            continue
        row = _upsert(
            db,
            "series_test_items",
            subject,
            subject_id=series.id,
            subject_label=series.name,
            context=_context(None, filed_row),
            candidates=candidates,
            question=sheet.series_question(
                series,
                "아래 시험도 합니까? 논문이나 제조사 페이지가 그렇게 적었지만 카탈로그 PDF "
                "에는 없던 것입니다. 인용문을 열어 읽고 정말 하는 것만 고르세요 — 고르면 그 "
                "시험이 이 계열에 붙습니다.",
            ),
            facts=sheet.series_facts(series),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "series_test_items", alive, "계열이 지워짐")


def _refresh_series_summary(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    """계열 소개에 넣을 문장 — 정본의 문장 중 아직 소개에 안 들어간 것."""
    makers = _axis_terms(db, "manufacturer")
    alive: set[str] = set()
    for subject, filed_row in filed.items():
        series = _series_of_row(db, makers, filed_row)
        if series is None:
            continue
        alive.add(subject)
        summary = series.summary or ""
        candidates = _mark(
            [
                {
                    "code": one["code"],
                    "label": one["label"],
                    "reason": None,
                    "sources": one.get("sources") or [],
                }
                for one in (filed_row.get("candidates") or [])
                if isinstance(one, dict) and one["label"] not in summary
            ],
            filed_row.get("recommended"),
            filed_row.get("reason"),
        )
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "series_summary",
                ReviewProposal.subject_key == subject,
            )
        )
        if not candidates:
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, [], "이미 들어감")
            continue
        row = _upsert(
            db,
            "series_summary",
            subject,
            subject_id=series.id,
            subject_label=series.name,
            context=_context(None, filed_row),
            candidates=candidates,
            question=sheet.series_question(
                series,
                "소개에 아래 문장을 붙입니까? 제조사 페이지의 응용 문장입니다 — 무엇에 쓰는지 "
                "말하는 문장만 고르고 마케팅 문구는 두세요. 고른 문장이 지금 소개 뒤에 "
                "붙습니다.",
            ),
            facts=sheet.series_facts(series),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "series_summary", alive, "계열이 지워짐")


def _refresh_test_item_aliases(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    """시험 항목의 별칭 — 정본(`draft_test_item_aliases.py` 가 만든 것)의 후보 중 **아직 이
    축에 없는 표기**만. 값이든 별칭이든 이미 쓰인 비교키는 뺀다(다른 시험의 이름이면
    더더욱)."""
    items = _axis_terms(db, "test_item")
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    taken: set[str] = set()
    if axis is not None:
        taken |= set(
            db.scalars(
                select(VocabularyTerm.normalized).where(
                    VocabularyTerm.vocabulary_id == axis.id
                )
            )
        )
        taken |= set(
            db.scalars(
                select(VocabularyAlias.normalized).where(
                    VocabularyAlias.vocabulary_id == axis.id
                )
            )
        )
    alive: set[str] = set()
    for code, filed_row in filed.items():
        term = items.get(code)
        if term is None:
            continue
        alive.add(code)
        candidates = _mark(
            [
                {"code": one["code"], "label": one["code"], "reason": one.get("reason")}
                for one in (filed_row.get("candidates") or [])
                if isinstance(one, dict) and compare_key(str(one["code"])) not in taken
            ],
            [
                one
                for one in (filed_row.get("recommended") or [])
                if compare_key(str(one)) not in taken
            ],
            None,
        )
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "test_item_aliases",
                ReviewProposal.subject_key == code,
            )
        )
        if not candidates:
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, [], "이미 있음")
            continue
        row = _upsert(
            db,
            "test_item_aliases",
            code,
            subject_id=term.id,
            subject_label=term.value,
            context=_context(None, filed_row),
            candidates=candidates,
            question=(
                f"「{term.value}」 을 부르는 다른 이름으로 아래 표기를 별칭에 더합니까? "
                "별칭은 찾기(resolve)가 이름보다 먼저 보는 것이라, AI 가 「thermal shock」 "
                "으로 물어도 이 시험을 찾게 됩니다. 이 시험만 가리키는 표기만 고르고, 후보에 "
                "없는 표기는 직접 적으세요."
            ),
            facts=sheet.test_item_facts(term),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "test_item_aliases", alive, "시험 항목이 지워짐")


#: 종류의 우리말. 화면(`attributes/kinds.ts`)과 같은 말을 쓴다 — 여기서만 「숫자」 라고
#: 부르면 같은 것을 두 이름으로 배우게 된다.
ATTRIBUTE_KIND_LABELS = {
    "number": "수치",
    "range": "구간",
    "text": "문장",
    "boolean": "있음/없음",
    "date": "날짜",
    "choice": "선택",
    "condition": "시험 조건",
    "term": "기준정보",
    "method": "규격",
}


def _attribute_value_counts(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(AttributeValue.definition_id, func.count())
        .where(AttributeValue.definition_id.in_(ids))
        .group_by(AttributeValue.definition_id)
    ).all()
    return {one: int(count) for one, count in rows}


def display_attribute_value(value: AttributeValue, definition: AttributeDefinition) -> str:
    """값 한 줄 — 화면·색인 카드와 같은 글자(`shared/attribute_text`). 가리키는 이름
    (기준정보 값·규격)은 여기서 안 읽는다: 예시 몇 줄에 질의를 더 붙일 일이 아니다."""
    return display_attribute(
        definition.kind,
        num_value=value.num_value,
        num_min=value.num_min,
        num_max=value.num_max,
        unit=value.unit or definition.unit,
        text_value=value.text_value,
        bool_value=value.bool_value,
        date_value=value.date_value,
    )


#: 속성이 붙는 대상의 우리말과 정의 화면 주소. 대상마다 화면이 다르므로 줄마다 링크가 다르다.
ATTRIBUTE_TARGETS: dict[str, tuple[str, str]] = {
    "reliability_test": ("신뢰성 시험", "/attribute-definitions/reliability-test"),
    "equipment": ("보유 장비", "/attribute-definitions/equipment"),
    "series": ("장비 계열", "/attribute-definitions/equipment-series"),
    "method": ("시험법·규격", "/attribute-definitions/method"),
}


def _attribute_name_key(label: str) -> str:
    """속성 이름의 비교키 — **띄어쓰기까지 지운다.** 「시험 온도」 와 「시험온도」 는 같은 칸이
    갈린 것이고, 그 둘이 다른 줄로 남으면 값이 두 군데로 쌓인다. 일반 비교키(`compare_key`)는
    구두점·공백을 남기는데(계열사 이름 때문에), 사람이 손으로 친 칸 이름에는 그 보수성이
    오히려 갈림을 못 잡는다."""
    return "".join(compare_key(label).split())


def _attribute_merge_candidates(
    draft: AttributeDefinition, siblings: list[AttributeDefinition]
) -> tuple[list[dict[str, Any]], str | None]:
    """합칠 만한 속성과, 확실한 하나가 있으면 그 코드.

    **이름이 같은 것만 추천한다**(띄어쓰기·대소문자·붙임표를 지운 비교키가 같을 때). 「시험
    온도」 와 「시험온도」 는 같은 칸이 갈린 것이 분명하지만, 「온도」 와 「보관 온도」 는 다른
    칸일 수 있다 — 후보로는 올리되 추천은 안 붙인다. 습관적으로 첫 보기를 누르는 것을
    막으려면 확신이 낮은 것에 추천이 없어야 한다.
    """
    mine = _attribute_name_key(draft.label)
    out: list[dict[str, Any]] = []
    exact: list[str] = []
    for other in siblings:
        # 종류가 다르면 값이 안 읽혀 합칠 수 없다(attributes.merge_into 가 막는다).
        if other.id == draft.id or other.kind != draft.kind or not other.is_active:
            continue
        theirs = _attribute_name_key(other.label)
        same = theirs == mine
        touching = not same and (theirs in mine or mine in theirs)
        if not same and not touching:
            continue
        code = f"merge:{other.key}"
        where = "정식" if other.status == "standard" else "초안"
        out.append(
            {
                "code": code,
                "label": f"「{other.label}」 에 합친다 ({where})",
                "reason": (
                    "띄어쓰기·대소문자를 지우면 이름이 같습니다."
                    if same
                    else "이름이 한쪽에 들어 있습니다 — 같은 칸인지 읽고 정하세요."
                ),
            }
        )
        if same:
            exact.append(code)
    # 정식이 먼저 — 같은 값이면 온톨로지에 이미 든 쪽으로 모으는 것이 낫다.
    out.sort(key=lambda one: (0 if "(정식)" in one["label"] else 1, one["label"]))
    return out, exact[0] if len(exact) == 1 else None


def _attribute_draft_facts(
    db: Session, draft: AttributeDefinition, count: int
) -> list[dict[str, Any]]:
    """이 초안이 무엇인지 — 종류·단위·몇 건·실제로 적힌 값 몇 개.

    **값을 봐야 판단이 된다.** 「시료 수」 라는 이름만으로는 합칠지 올릴지 못 정하고,
    「5」 「5개」 「5 ea」 가 섞여 있으면 그것이 곧 답이다(종류가 글자로 잡혀 있다).
    """
    label, link = ATTRIBUTE_TARGETS.get(draft.target, (draft.target, ""))
    facts: list[dict[str, Any]] = [
        {"label": "붙는 곳", "value": label, "link": link or None},
        {
            "label": "종류",
            "value": ATTRIBUTE_KIND_LABELS.get(draft.kind, draft.kind)
            + (f" · {draft.unit}" if draft.unit else ""),
        },
        {"label": "적힌 값", "value": f"{count}건"},
    ]
    samples = [
        display_attribute_value(value, draft)
        for value in db.scalars(
            select(AttributeValue)
            .where(AttributeValue.definition_id == draft.id)
            .order_by(AttributeValue.created_at)
            .limit(4)
        )
    ]
    shown = [one for one in samples if one]
    if shown:
        facts.append({"label": "값의 예", "value": " · ".join(shown)})
    return facts


def _refresh_attribute_drafts(db: Session) -> None:
    """초안 속성 — **정본이 아니라 이 설치의 상태에서** 세운다.

    초안은 값을 적는 사람이 새 이름을 쓰면 서버가 만든다. 그래서 후보 파일이 있을 수 없고,
    쌓이는 것도 설치마다 다르다. 두면 온톨로지 밖에 남아 검색·판정·색인 카드 어디에도 안
    쓰이므로, 「합칠지 · 올릴지 · 둘지」 를 묻는 자리가 있어야 한다.

    값이 0건인 초안은 묻지 않는다 — 값이 없으면 정의 화면에서 지우면 그만이고, 물음으로
    세우면 아무 일도 안 하는 줄이 검토함을 채운다.
    """
    drafts = list(
        db.scalars(
            select(AttributeDefinition)
            .where(
                AttributeDefinition.status == "draft",
                AttributeDefinition.is_active.is_(True),
            )
            .order_by(AttributeDefinition.target, AttributeDefinition.label)
        )
    )
    by_target: dict[str, list[AttributeDefinition]] = {}
    for one in db.scalars(select(AttributeDefinition)):
        by_target.setdefault(one.target, []).append(one)

    counts = _attribute_value_counts(db, [one.id for one in drafts])
    alive: set[str] = set()
    for draft in drafts:
        count = counts.get(draft.id, 0)
        if count == 0:
            continue
        alive.add(draft.key)
        merges, exact = _attribute_merge_candidates(draft, by_target.get(draft.target, []))
        target_label = ATTRIBUTE_TARGETS.get(draft.target, (draft.target, ""))[0]
        candidates = _mark(
            [
                *merges,
                {
                    "code": "standard",
                    "label": "정식으로 올린다 — 이 이름으로 굳힌다",
                    "reason": None,
                },
                {
                    "code": "keep",
                    "label": "초안으로 둔다 — 더 모아 보고 정한다",
                    "reason": None,
                },
                {"code": "off", "label": "끈다 — 새 입력에서 안 뜨게", "reason": None},
            ],
            exact,
            None,
        )
        _upsert(
            db,
            "attribute_drafts",
            draft.key,
            subject_id=draft.id,
            subject_label=f"{draft.label} ({target_label})",
            context=f"{target_label}에 {count}건 적힘",
            candidates=candidates,
            payload={
                "target": draft.target,
                "link": ATTRIBUTE_TARGETS.get(draft.target, (draft.target, ""))[1],
            },
            question=(
                f"「{draft.label}」 은 {target_label}에 {count}건 적힌 **초안** 속성입니다. "
                "초안은 온톨로지 밖이라 검색·판정·색인 카드 어디에도 안 쓰입니다. 같은 뜻인 "
                "속성이 이미 있으면 거기 합치고, 이 이름으로 굳힐 것이면 정식으로 올리세요."
            ),
            facts=_attribute_draft_facts(db, draft, count),
        )
    # 정식이 되었거나 합쳐졌거나 꺼진 초안 — 화면에서 이미 정해진 것이다.
    for row in db.scalars(
        select(ReviewProposal).where(
            ReviewProposal.queue == "attribute_drafts",
            ReviewProposal.status.in_(("open", "skipped")),
        )
    ):
        if row.subject_key in alive:
            continue
        found = db.scalar(
            select(AttributeDefinition).where(AttributeDefinition.key == row.subject_key)
        )
        if found is None:
            _gone(row, "속성이 지워짐")
        elif found.merged_into_id is not None:
            _settle(db, row, [f"merge:{row.subject_key}"], "화면에서 합침")
        elif found.status == "standard":
            _settle(db, row, ["standard"], "화면에서 정식으로 올림")
        elif not found.is_active:
            _settle(db, row, ["off"], "화면에서 끔")
        else:
            _gone(row, "값이 없어짐")


def _refresh_series_standards(
    db: Session, filed: dict[str, dict[str, Any]], sheet: Sheet
) -> None:
    """계열이 하는 규격 더하기 — 정본(`catalog_extension/tools_propose.py` 가 만든 것)의
    후보 중 아직 이 계열에 안 이어진 것. 계열은 이름(+제조사)으로 찾는다 — 반입이 그렇게
    만든다."""
    makers = _axis_terms(db, "manufacturer")
    cited: dict[uuid.UUID, set[str]] = {}
    for series_id, code in db.execute(
        select(SeriesTestItem.series_id, TestMethod.code)
        .join(
            SeriesTestItemMethod, SeriesTestItemMethod.series_test_item_id == SeriesTestItem.id
        )
        .join(TestMethod, TestMethod.id == SeriesTestItemMethod.method_id)
    ):
        cited.setdefault(series_id, set()).add(method_key(code))
    for series_id, code in db.execute(
        select(SeriesPendingMethod.series_id, TestMethod.code).join(
            TestMethod, TestMethod.id == SeriesPendingMethod.method_id
        )
    ):
        cited.setdefault(series_id, set()).add(method_key(code))
    alive: set[str] = set()
    for subject, filed_row in filed.items():
        series = _series_of_row(db, makers, filed_row)
        if series is None:
            continue
        alive.add(subject)
        have = cited.get(series.id, set())
        raw = [one for one in (filed_row.get("candidates") or []) if isinstance(one, dict)]
        candidates = _mark(
            [
                {
                    "code": one["code"],
                    "label": (
                        f"{one['code']} — {one['title']}" if one.get("title") else one["code"]
                    ),
                    "reason": one.get("reason"),
                    "sources": one.get("sources") or [],
                }
                for one in raw
                if method_key(one["code"]) not in have
            ],
            filed_row.get("recommended"),
            filed_row.get("reason"),
        )
        row = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "series_standards",
                ReviewProposal.subject_key == subject,
            )
        )
        if not candidates:
            # 후보가 전부 이어졌다 — 화면이나 반입이 이미 한 것이다.
            if row is not None and row.status in ("open", "skipped"):
                _settle(db, row, [], "이미 이어짐")
            continue
        row = _upsert(
            db,
            "series_standards",
            subject,
            subject_id=series.id,
            subject_label=series.name,
            context=_context(None, filed_row),
            question=sheet.series_question(
                series,
                "아래 규격도 씁니까? 제조사 웹·대리점·논문이 이 계열과 함께 적었지만 카탈로그 "
                "PDF 에는 없던 규격입니다. 출처를 열어 이 계열 얘기가 맞는지 보고 고르세요 — "
                "고르면 그 규격이 이 계열에 붙습니다.",
            ),
            facts=sheet.series_facts(series),
            candidates=candidates,
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "series_standards", alive, "계열이 지워짐")


def _link_series_standard(
    db: Session,
    series: EquipmentSeries,
    code: str,
    *,
    actor: User | None,
    title: str | None = None,
) -> None:
    """규격 하나를 계열에 잇는다 — 반입(`catalog_import.series`)과 같은 규칙.

    규격이 없으면 만든다(판은 안 적는다). 규격의 시험 항목이 정해져 있고 계열에 그 시험이
    있으면 거기에, 계열의 시험이 하나뿐이면 그 시험에(소거), 아니면 항목 미정 인용으로 둔다 —
    그러면 「규격의 시험 항목」 물음이 이어받는다.
    """
    method = next(
        (
            m
            for m in db.scalars(select(TestMethod).where(TestMethod.deleted_at.is_(None)))
            if method_key(m.code) == method_key(code)
        ),
        None,
    )
    if method is None:
        head = code.split()[0].split("/")[0]
        body = _axis_terms(db, "standard_body").get(head) if head.isalpha() else None
        method = TestMethod(
            code=code,
            title=title or code,
            body_term_id=body.id if body else None,
            summary="검토함에서 더함 — 제조사 웹·대리점·논문이 이 계열과 함께 적은 규격",
            created_by_id=actor.id if actor else None,
        )
        db.add(method)
        db.flush()
    items = list(
        db.scalars(select(SeriesTestItem).where(SeriesTestItem.series_id == series.id))
    )
    target = None
    if method.test_item_term_id is not None:
        target = next(
            (t for t in items if t.test_item_term_id == method.test_item_term_id), None
        )
    elif len(items) == 1:
        target = items[0]
        method.test_item_term_id = target.test_item_term_id
    if target is not None:
        exists = db.scalar(
            select(SeriesTestItemMethod.id).where(
                SeriesTestItemMethod.series_test_item_id == target.id,
                SeriesTestItemMethod.method_id == method.id,
            )
        )
        if exists is None:
            db.add(SeriesTestItemMethod(series_test_item_id=target.id, method_id=method.id))
        return
    exists = db.scalar(
        select(SeriesPendingMethod.id).where(
            SeriesPendingMethod.series_id == series.id,
            SeriesPendingMethod.method_id == method.id,
        )
    )
    if exists is None:
        db.add(SeriesPendingMethod(series_id=series.id, method_id=method.id))


def _apply(db: Session, row: ReviewProposal, choice: list[str], *, actor: User | None) -> None:
    """고른 것을 **기존 규칙으로** 적용한다. 큐마다 다르다."""
    queue = row.queue
    if queue == "method_test_items":
        if not choice:
            return
        items = _axis_terms(db, "test_item")
        term = items.get(choice[0])
        if term is None:
            raise NotFound("TSC-REVIEW-0002", f"시험 항목 코드를 모릅니다: {choice[0]}")
        method = db.get(TestMethod, row.subject_id) if row.subject_id else None
        if method is None:
            raise NotFound("TSC-REVIEW-0003", "규격을 찾을 수 없습니다.")
        method.test_item_term_id = term.id
        promote_pending(db, method)
    elif queue == "test_item_axes":
        if row.subject_id is None:
            raise NotFound("TSC-REVIEW-0003", "시험 항목을 찾을 수 없습니다.")
        keys = {k.key: k for k in db.scalars(select(ConditionKey))}
        unknown = [code for code in choice if code not in keys]
        if unknown:
            raise NotFound("TSC-REVIEW-0002", f"조건 키를 모릅니다: {', '.join(unknown)}")
        have = set(
            db.scalars(
                select(TestItemConditionKey.condition_key_id).where(
                    TestItemConditionKey.test_item_term_id == row.subject_id
                )
            )
        )
        for code in choice:
            if keys[code].id not in have:
                db.add(
                    TestItemConditionKey(
                        test_item_term_id=row.subject_id, condition_key_id=keys[code].id
                    )
                )
    elif queue == "property_links":
        link = db.get(TestItemProperty, row.subject_id) if row.subject_id else None
        if link is None:
            return  # 이미 없어졌다 — 끊기로 한 것과 같다.
        if choice == ["confirm"]:
            link.status = "confirmed"
            link.confirmed_by_id = actor.id if actor else None
            link.confirmed_at = datetime.now(UTC)
        elif choice == ["reject"]:
            db.delete(link)
        else:
            raise AppError("TSC-REVIEW-0004", "confirm 또는 reject 중 하나입니다.", status=400)
    elif queue == "free_spec_definitions":
        if choice == ["keep"]:
            return
        if choice != ["promote"]:
            raise AppError("TSC-REVIEW-0004", "promote 또는 keep 중 하나입니다.", status=400)
        source_key, _, unit = row.subject_key.partition("|")
        stmt = select(ModelFreeSpec).where(ModelFreeSpec.source_key == source_key)
        if unit:
            stmt = stmt.where(ModelFreeSpec.unit == unit)
        sample = db.scalar(stmt.limit(1))
        if sample is None:
            return
        payload = row.payload or {}
        if not payload.get("key") or not payload.get("group_id"):
            raise AppError(
                "TSC-REVIEW-0005",
                "올릴 정의의 키와 그룹이 정본에 없습니다 — 기종 상세에서 직접 올리세요.",
                status=400,
            )
        model = db.get(EquipmentModel, sample.model_id)
        if model is None:
            return
        free_specs.promote(
            db,
            model,
            sample.id,
            {
                "key": payload["key"],
                "label": payload.get("label") or sample.label,
                "group_id": uuid.UUID(str(payload["group_id"])),
                "kind": payload.get("kind") or "number",
                "unit": payload.get("unit") or "",
                "apply_same_key": True,
            },
        )
    elif queue == "attribute_drafts":
        draft = db.get(AttributeDefinition, row.subject_id) if row.subject_id else None
        if draft is None:
            return  # 이미 없어졌다.
        code = choice[0] if choice else "keep"
        if code == "keep":
            return
        if code == "standard":
            attributes.update_definition(db, draft.id, {"status": "standard"})
        elif code == "off":
            attributes.update_definition(db, draft.id, {"is_active": False})
        elif code.startswith("merge:"):
            into = db.scalar(
                select(AttributeDefinition).where(
                    AttributeDefinition.key == code.removeprefix("merge:")
                )
            )
            if into is None:
                raise NotFound("TSC-REVIEW-0002", f"합칠 속성을 모릅니다: {code}")
            # 합치는 규칙은 속성 쪽 하나다 — 값이 옮겨 가고 원래 것은 꺼진다.
            attributes.merge_into(db, draft.id, into.id)
        else:
            raise AppError("TSC-REVIEW-0004", f"모르는 선택입니다: {code}", status=400)
    elif queue == "method_cleanup":
        method = db.get(TestMethod, row.subject_id) if row.subject_id else None
        if method is None or method.deleted_at is not None:
            return
        if choice == ["keep"]:
            return
        if choice == ["delete"]:
            used = (
                db.scalar(
                    select(func.count())
                    .select_from(EquipmentTestItem)
                    .where(EquipmentTestItem.method_id == method.id)
                )
                or 0
            )
            if used:
                raise AppError(
                    "TSC-REVIEW-0012",
                    f"보유 장비 시험 항목 {used}건이 이 규격을 걸고 있어 못 지웁니다"
                    " — 합치거나 두세요.",
                    status=409,
                )
            detach_citations(db, method.id)
            method.deleted_at = datetime.now(UTC)
            return
        if len(choice) == 1 and choice[0].startswith("merge:"):
            target_code = choice[0].split(":", 1)[1]
            target = db.scalar(
                select(TestMethod).where(
                    TestMethod.deleted_at.is_(None), TestMethod.code == target_code
                )
            )
            if target is None:
                raise NotFound("TSC-REVIEW-0002", f"합칠 규격을 모릅니다: {target_code}")
            merge_into(db, actor, method.id, target.id)
            return
        raise AppError(
            "TSC-REVIEW-0004", "keep · delete · merge:<규격> 중 하나입니다.", status=400
        )
    elif queue == "test_item_properties":
        if row.subject_id is None:
            raise NotFound("TSC-REVIEW-0003", "시험 항목을 찾을 수 없습니다.")
        props = _axis_terms(db, "property")
        unknown = [code for code in choice if code not in props]
        if unknown:
            raise NotFound("TSC-REVIEW-0002", f"물성 코드를 모릅니다: {', '.join(unknown)}")
        have = set(
            db.scalars(
                select(TestItemProperty.property_term_id).where(
                    TestItemProperty.test_item_term_id == row.subject_id
                )
            )
        )
        for code in choice:
            if props[code].id in have:
                continue
            db.add(
                TestItemProperty(
                    test_item_term_id=row.subject_id,
                    property_term_id=props[code].id,
                    status="confirmed",
                    source="review",
                    created_by_id=actor.id if actor else None,
                    confirmed_by_id=actor.id if actor else None,
                    confirmed_at=datetime.now(UTC),
                )
            )
    elif queue == "condition_axes":
        if choice == ["skip"]:
            return
        if choice != ["create"]:
            raise AppError("TSC-REVIEW-0004", "create 또는 skip 중 하나입니다.", status=400)
        payload = row.payload or {}
        key = str(payload.get("key") or row.subject_key)
        if db.scalar(select(ConditionKey.id).where(ConditionKey.key == key)) is not None:
            return
        last = db.scalar(select(func.max(ConditionKey.sort_order))) or 0
        made = ConditionKey(
            key=key,
            label=str(payload.get("label") or key),
            kind="range",
            dimension=str(payload.get("dimension") or ""),
            si_unit=str(payload.get("unit") or ""),
            display_unit=str(payload.get("unit") or ""),
            sort_order=last + 10,
            help="검토함에서 세운 검색 조건.",
        )
        db.add(made)
        db.flush()
        # **빈 것만 잇는다** — 이미 다른 축에 이어진 정의는 사람이 정한 것이다.
        for definition in db.scalars(
            select(SpecDefinition).where(
                SpecDefinition.key.in_(list(payload.get("definitions") or [])),
                SpecDefinition.condition_key_id.is_(None),
            )
        ):
            definition.condition_key_id = made.id
        items = _axis_terms(db, "test_item")
        for code in payload.get("test_items") or []:
            term = items.get(code)
            if term is None:
                continue
            db.add(TestItemConditionKey(test_item_term_id=term.id, condition_key_id=made.id))
    elif queue == "series_standards":
        series = db.get(EquipmentSeries, row.subject_id) if row.subject_id else None
        if series is None:
            raise NotFound("TSC-REVIEW-0003", "계열을 찾을 수 없습니다.")
        offered = {one["code"]: one for one in row.candidates}
        unknown = [code for code in choice if code not in offered]
        if unknown:
            raise NotFound("TSC-REVIEW-0002", f"후보에 없는 규격입니다: {', '.join(unknown)}")
        for code in choice:
            label = str(offered[code].get("label") or "")
            # 라벨이 「코드 — 제목」 이면 제목을 새 시험법의 이름으로
            title = label.split(" — ", 1)[1] if " — " in label else None
            _link_series_standard(db, series, code, actor=actor, title=title)
    elif queue == "series_test_items":
        series = db.get(EquipmentSeries, row.subject_id) if row.subject_id else None
        if series is None:
            raise NotFound("TSC-REVIEW-0003", "계열을 찾을 수 없습니다.")
        items = _axis_terms(db, "test_item")
        unknown = [code for code in choice if code not in items]
        if unknown:
            raise NotFound(
                "TSC-REVIEW-0002", f"시험 항목 코드를 모릅니다: {', '.join(unknown)}"
            )
        have = set(
            db.scalars(
                select(SeriesTestItem.test_item_term_id).where(
                    SeriesTestItem.series_id == series.id
                )
            )
        )
        for code in choice:
            term = items[code]
            if term.id in have:
                continue
            db.add(
                SeriesTestItem(
                    series_id=series.id,
                    test_item_term_id=term.id,
                    note="검토함에서 더함 — 논문·제조사 웹이 이 계열로 이 시험을 한다고 적음",
                )
            )
            db.flush()
            # 이 계열이 항목 미정으로 인용해 둔 규격 중 이 시험의 것이 있으면 지금 붙는다.
            for method in db.scalars(
                select(TestMethod)
                .join(SeriesPendingMethod, SeriesPendingMethod.method_id == TestMethod.id)
                .where(
                    SeriesPendingMethod.series_id == series.id,
                    TestMethod.test_item_term_id == term.id,
                )
            ):
                promote_pending(db, method)
    elif queue == "test_item_aliases":
        if row.subject_id is None:
            raise NotFound("TSC-REVIEW-0003", "시험 항목을 찾을 수 없습니다.")
        term = db.get(VocabularyTerm, row.subject_id)
        if term is None:
            raise NotFound("TSC-REVIEW-0003", "시험 항목을 찾을 수 없습니다.")
        for value in choice:
            text_value = clean(str(value))
            if not text_value:
                continue
            existing = db.scalar(
                select(VocabularyAlias).where(
                    VocabularyAlias.vocabulary_id == term.vocabulary_id,
                    VocabularyAlias.normalized == compare_key(text_value),
                )
            )
            if existing is not None:
                if existing.term_id == term.id:
                    continue
                other = db.get(VocabularyTerm, existing.term_id)
                raise AppError(
                    "TSC-REVIEW-0010",
                    f"「{text_value}」 은 이미 「{other.value if other else '?'}」 의 "
                    "별칭입니다.",
                    status=409,
                )
            clash = db.scalar(
                select(VocabularyTerm).where(
                    VocabularyTerm.vocabulary_id == term.vocabulary_id,
                    VocabularyTerm.normalized == compare_key(text_value),
                )
            )
            if clash is not None and clash.id != term.id:
                raise AppError(
                    "TSC-REVIEW-0010",
                    f"「{text_value}」 은 시험 항목 「{clash.value}」 의 이름입니다.",
                    status=409,
                )
            if clash is None:
                db.add(
                    VocabularyAlias(
                        vocabulary_id=term.vocabulary_id,
                        term_id=term.id,
                        value=text_value,
                        normalized=compare_key(text_value),
                    )
                )
        db.flush()
    elif queue == "series_summary":
        series = db.get(EquipmentSeries, row.subject_id) if row.subject_id else None
        if series is None:
            raise NotFound("TSC-REVIEW-0003", "계열을 찾을 수 없습니다.")
        by_code = {one["code"]: one["label"] for one in row.candidates}
        unknown = [code for code in choice if code not in by_code]
        if unknown:
            raise NotFound("TSC-REVIEW-0002", f"후보에 없는 문장입니다: {', '.join(unknown)}")
        summary = series.summary or ""
        for code in choice:
            sentence = by_code[code]
            if sentence in summary:
                continue
            summary = (summary.rstrip() + "\n\n" if summary.strip() else "") + sentence
        series.summary = summary
    else:
        raise NotFound("TSC-REVIEW-0006", f"모르는 검토함입니다: {queue}")


# --- 정본으로 되돌려 쓰기 ------------------------------------------------------------


def export_decisions(
    db: Session, root: Path = PROPOSALS_DIR, *, write: bool = True
) -> dict[str, tuple[int, int, int]]:
    """결정을 `proposals/<queue>.json` 의 `decided` 에 적는다.

    돌려주는 것은 {큐: (결정 수, 적은 수, 새 줄 수)}.

    정본에서 온 결정(`decided_by_label == "정본"`)은 이미 정본에 있으니 건너뛴다. 정본에 줄이
    없는 결정(파생 후보)은 `subject` 와 `decided` 만 있는 새 줄로 더한다 — 다음 refresh 가
    후보를 다시 파생한다. `recommended`·`reason`·`hint` 는 사람이 적는 것이라 안 건드린다.
    """
    root.mkdir(parents=True, exist_ok=True)
    out: dict[str, tuple[int, int, int]] = {}
    for queue, spec in QUEUES.items():
        if spec.local:
            # 이 설치에서만 뜻이 있는 물음 — 내보내면 다른 설치에서 안 맞는 결정이 쌓인다.
            continue
        path = root / f"{queue}.json"
        doc: dict[str, Any] = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.exists()
            else {"queue": queue, "rows": []}
        )
        rows: list[dict[str, Any]] = doc.setdefault("rows", [])
        by_subject = {str(row["subject"]): row for row in rows}
        # subject_key 는 method_key(소문자·공백 정리)라 정본의 표기와 다를 수 있다.
        by_key = {method_key(str(row["subject"])): row for row in rows}
        decided = list(
            db.scalars(
                select(ReviewProposal).where(
                    ReviewProposal.queue == queue, ReviewProposal.status == "decided"
                )
            )
        )
        written = added = 0
        for one in decided:
            if one.decided_by_label == "정본":
                continue
            subject = one.subject_label.split(" — ")[0]
            target = (
                by_subject.get(one.subject_key)
                or by_key.get(one.subject_key)
                or by_subject.get(subject)
            )
            if target is None:
                target = {"subject": subject}
                rows.append(target)
                by_subject[subject] = target
                added += 1
            decision: dict[str, Any] = {
                "choice": one.choice or [],
                "by": one.decided_by_label,
                "on": one.decided_at.date().isoformat() if one.decided_at else None,
            }
            if one.note:
                decision["note"] = one.note
            if target.get("decided") != decision:
                target["decided"] = decision
                written += 1
        out[queue] = (len(decided), written, added)
        if write and (written or added):
            path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
    return out


# --- 읽기·결정 -------------------------------------------------------------------


def queues(db: Session) -> list[QueueOut]:
    rows = db.execute(
        select(ReviewProposal.queue, ReviewProposal.status, func.count()).group_by(
            ReviewProposal.queue, ReviewProposal.status
        )
    ).all()
    tally: dict[str, dict[str, int]] = {}
    for queue, status, count in rows:
        tally.setdefault(queue, {})[status] = count
    voted: dict[str, int] = {
        queue: count
        for queue, count in db.execute(
            select(ReviewProposal.queue, func.count(func.distinct(ReviewProposal.id)))
            .join(ReviewVote, ReviewVote.proposal_id == ReviewProposal.id)
            .where(ReviewProposal.status == "open")
            .group_by(ReviewProposal.queue)
        )
    }
    return [
        QueueOut(
            key=one.key,
            label=one.label,
            description=one.description,
            multi=one.multi,
            open=tally.get(one.key, {}).get("open", 0),
            decided=tally.get(one.key, {}).get("decided", 0),
            skipped=tally.get(one.key, {}).get("skipped", 0),
            gone=tally.get(one.key, {}).get("gone", 0),
            voted=voted.get(one.key, 0),
        )
        for one in QUEUES.values()
    ]


def get_proposal(db: Session, proposal_id: uuid.UUID) -> ReviewProposal:
    row = db.get(ReviewProposal, proposal_id)
    if row is None:
        raise NotFound("TSC-REVIEW-0007", "검토 항목을 찾을 수 없습니다.")
    return row


def _votes(db: Session, proposal_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ReviewVote]]:
    out: dict[uuid.UUID, list[ReviewVote]] = {}
    if not proposal_ids:
        return out
    for vote in db.scalars(
        select(ReviewVote)
        .where(ReviewVote.proposal_id.in_(proposal_ids))
        .order_by(ReviewVote.created_at)
    ):
        out.setdefault(vote.proposal_id, []).append(vote)
    return out


def proposal_out(
    row: ReviewProposal,
    votes: list[ReviewVote] | None = None,
    viewer_id: uuid.UUID | None = None,
) -> ProposalOut:
    queue = QUEUES[row.queue]
    votes = votes or []
    mine = next((one for one in votes if one.user_id == viewer_id), None)
    return ProposalOut(
        id=row.id,
        queue=row.queue,
        subject_key=row.subject_key,
        subject_id=row.subject_id,
        subject_label=row.subject_label,
        context=row.context,
        question=row.question,
        facts=[FactOut(**one) for one in (row.facts or [])],
        # 줄이 제 링크를 가지면 그것을 쓴다 — 같은 큐인데 대상마다 화면이 다른 물음이
        # 있다(초안 속성: 신뢰성 시험·보유 장비·계열·규격의 정의 화면이 각각이다).
        link=(row.payload or {}).get("link")
        or (
            queue.link.format(id=row.subject_id)
            if row.subject_id or "{id}" not in queue.link
            else None
        ),
        candidates=[CandidateOut(**one) for one in row.candidates],
        payload=row.payload,
        status=row.status,
        choice=row.choice,
        followed=row.followed,
        note=row.note,
        decided_by=row.decided_by_label,
        decided_at=row.decided_at,
        votes=[
            VoteOut(
                user_id=one.user_id,
                user=one.user_label,
                choice=list(one.choice or []),
                note=one.note,
                at=one.updated_at,
            )
            for one in votes
        ],
        my_vote=list(mine.choice or []) if mine else None,
    )


def with_votes(db: Session, row: ReviewProposal, viewer_id: uuid.UUID | None) -> ProposalOut:
    return proposal_out(row, _votes(db, [row.id]).get(row.id, []), viewer_id)


def list_proposals(
    db: Session,
    queue: str,
    *,
    status: str,
    limit: int,
    offset: int,
    viewer_id: uuid.UUID | None = None,
) -> tuple[list[ProposalOut], int]:
    if queue not in QUEUES:
        raise NotFound("TSC-REVIEW-0006", f"모르는 검토함입니다: {queue}")
    base = select(ReviewProposal).where(ReviewProposal.queue == queue)
    if status == "voted":
        # 열린 것 중 의견이 모인 줄 — 확정할 사람이 먼저 보는 자리.
        base = base.where(
            ReviewProposal.status == "open",
            ReviewProposal.id.in_(select(ReviewVote.proposal_id)),
        )
    elif status != "all":
        base = base.where(ReviewProposal.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(ReviewProposal.subject_label).limit(limit).offset(offset)
    ).all()
    votes = _votes(db, [row.id for row in rows])
    return [proposal_out(row, votes.get(row.id, []), viewer_id) for row in rows], total


def vote(
    db: Session, user: User, proposal_id: uuid.UUID, *, choice: list[str], note: str | None
) -> ReviewProposal:
    """의견을 낸다(있으면 바꾼다). **로그인한 누구나** — 데이터를 안 건드리니 넓게 연다.

    도메인 전문가가 시스템 관리자일 이유가 없다. 확정만 관리자가 한다.
    """
    row = get_proposal(db, proposal_id)
    if row.status in ("decided", "gone"):
        raise AppError("TSC-REVIEW-0011", "닫힌 항목에는 의견을 낼 수 없습니다.", status=409)
    if not QUEUES[row.queue].multi and len(choice) > 1:
        raise AppError("TSC-REVIEW-0004", "하나만 고르는 물음입니다.", status=400)
    held = db.scalar(
        select(ReviewVote).where(
            ReviewVote.proposal_id == row.id, ReviewVote.user_id == user.id
        )
    )
    if held is None:
        held = ReviewVote(proposal_id=row.id, user_id=user.id)
        db.add(held)
    held.user_label = user.display_name or user.email
    held.choice = choice
    held.note = note
    db.commit()
    db.refresh(row)
    return row


def withdraw_vote(db: Session, user: User, proposal_id: uuid.UUID) -> ReviewProposal:
    row = get_proposal(db, proposal_id)
    held = db.scalar(
        select(ReviewVote).where(
            ReviewVote.proposal_id == row.id, ReviewVote.user_id == user.id
        )
    )
    if held is not None:
        db.delete(held)
        db.commit()
    db.refresh(row)
    return row


def decide(
    db: Session, user: User, proposal_id: uuid.UUID, *, choice: list[str], note: str | None
) -> ReviewProposal:
    """고른 것을 적용하고 결정으로 남긴다. **추천을 따랐는지**도 남긴다."""
    _require_admin(user)
    row = get_proposal(db, proposal_id)
    if row.status == "decided":
        raise AppError(
            "TSC-REVIEW-0008", "이미 결정된 항목입니다. 바꾸려면 먼저 다시 여세요.", status=409
        )
    if row.status == "gone":
        raise AppError("TSC-REVIEW-0009", "대상이 없어진 항목입니다.", status=409)
    if not QUEUES[row.queue].multi and len(choice) > 1:
        raise AppError("TSC-REVIEW-0004", "하나만 고르는 물음입니다.", status=400)
    _apply(db, row, choice, actor=user)
    row.status = "decided"
    row.choice = choice
    row.followed = _followed(row.candidates, choice)
    row.note = note
    row.decided_by_id = user.id
    row.decided_by_label = user.display_name or user.email
    row.decided_at = datetime.now(UTC)
    audit.record(
        db,
        action=audit.REVIEW_DECIDED,
        actor=user,
        target_table="review_proposals",
        target_id=row.id,
        target_label=f"{QUEUES[row.queue].label}: {row.subject_label}",
        changes={
            "queue": row.queue,
            "subject": row.subject_key,
            "choice": choice,
            "followed": row.followed,
            # 그때 모여 있던 의견 — 확정이 다수와 달랐는지 나중에 볼 수 있게.
            "votes": [
                {"user": one.user_label, "choice": list(one.choice or [])}
                for one in _votes(db, [row.id]).get(row.id, [])
            ],
        },
        reason=note,
    )
    db.commit()
    db.refresh(row)
    return row


def skip(db: Session, user: User, proposal_id: uuid.UUID) -> ReviewProposal:
    _require_admin(user)
    row = get_proposal(db, proposal_id)
    if row.status in ("decided", "gone"):
        raise AppError("TSC-REVIEW-0008", "이미 닫힌 항목입니다.", status=409)
    row.status = "skipped" if row.status == "open" else "open"
    db.commit()
    db.refresh(row)
    return row


def reopen(db: Session, user: User, proposal_id: uuid.UUID) -> ReviewProposal:
    """정한 것을 다시 연다 — 다른 걸로 고르려고. **이미 일어난 일은 안 되돌린다.**

    지운 연결·만들어진 정의는 그대로다. 그것까지 여기서 되돌리면 삭제 취소 규칙이 두 벌이
    된다 — 원래 화면에서 한다. 첫 결정은 감사에 남아 있고, 여기 줄에는 다시 열었다는 사실이
    남는다.
    """
    _require_admin(user)
    row = get_proposal(db, proposal_id)
    if row.status != "decided":
        raise AppError("TSC-REVIEW-0010", "정한 항목만 다시 열 수 있습니다.", status=409)
    audit.record(
        db,
        action=audit.REVIEW_REOPENED,
        actor=user,
        target_table="review_proposals",
        target_id=row.id,
        target_label=f"{QUEUES[row.queue].label}: {row.subject_label}",
        changes={
            "queue": row.queue,
            "subject": row.subject_key,
            "previous_choice": row.choice,
            "previous_by": row.decided_by_label,
        },
    )
    row.status = "open"
    row.note = f"다시 열림 — 전에는 {row.decided_by_label} 이(가) {row.choice} 로 정함"
    row.choice = None
    row.followed = None
    row.decided_by_id = None
    row.decided_by_label = None
    row.decided_at = None
    db.commit()
    db.refresh(row)
    return row
