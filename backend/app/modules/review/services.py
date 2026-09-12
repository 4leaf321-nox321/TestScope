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
from app.modules.equipment import free_specs
from app.modules.equipment.models import EquipmentModel, EquipmentSeries, ModelFreeSpec
from app.modules.methods.models import TestMethod
from app.modules.methods.services import detach_citations, merge_into, promote_pending
from app.modules.properties.models import TestItemProperty
from app.modules.review.models import ReviewProposal, ReviewVote
from app.modules.review.schemas import CandidateOut, ProposalOut, QueueOut, VoteOut
from app.modules.test_items.models import (
    EquipmentTestItem,
    SeriesPendingMethod,
    SeriesTestItem,
    TestItemConditionKey,
)
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.modules.vocabulary.specs import SpecDefinition, SpecGroup
from app.shared import audit
from app.shared.errors import AppError, Forbidden, NotFound
from app.shared.text import method_key

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
        "물성 연결 의심",
        "이 시험으로 이 물성이 나오는 게 맞나. 아니면 연결을 끊는다.",
        False,
        "/properties",
    ),
    "free_spec_definitions": Queue(
        "free_spec_definitions",
        "정의로 올릴 사양",
        "여러 기종에 같은 이름으로 쌓인 「이 기종만의 사양」 을 정식 사양 칸으로 올릴지.",
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
        "시험이 내는 물성",
        "물성이 하나도 안 이어진 시험 항목 — 이 시험으로 얻는 물성이 있으면 잇는다. 여러 개.",
        True,
        "/catalog/test-items/{id}",
    ),
    "condition_axes": Queue(
        "condition_axes",
        "새 검색 조건",
        "지금 검색 조건에 없어 검색이 못 답하는 것(점도·압력·파장 …)을 조건으로 세울지.",
        False,
        "/conditions",
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
                "reason": (reason if not shown else None) if picked else one.get("reason"),
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
    _refresh_method_test_items(db, load_file("method_test_items", root))
    _refresh_test_item_axes(db, load_file("test_item_axes", root))
    _refresh_property_links(db, load_file("property_links", root))
    _refresh_free_spec_definitions(db, load_file("free_spec_definitions", root))
    _refresh_method_cleanup(db, load_file("method_cleanup", root))
    _refresh_test_item_properties(db, load_file("test_item_properties", root))
    _refresh_condition_axes(db, load_file("condition_axes", root))
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


def _refresh_method_test_items(db: Session, filed: dict[str, dict[str, Any]]) -> None:
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
        codes: list[str] = [
            code for t in derived if t in by_id and (code := by_id[t].code) is not None
        ]
        for code in (filed_row or {}).get("candidates") or []:
            if code in items and code not in codes:
                codes.append(code)
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
        candidates = _mark(
            [{"code": code, "label": items[code].value} for code in sorted(set(codes))],
            (filed_row or {}).get("recommended"),
            (filed_row or {}).get("reason"),
        )
        names = sorted(series_names.get(s, "") for s in cited)[:2]
        context = _context(
            ("인용: " + " · ".join(n for n in names if n)) if names else None, filed_row
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
        )
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(
        db, "method_test_items", {method_key(m.code) for m in methods}, "규격이 지워짐"
    )


def _refresh_test_item_axes(db: Session, filed: dict[str, dict[str, Any]]) -> None:
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
        candidates = _mark(
            [{"code": k.key, "label": k.label} for k in keys.values() if k.is_active],
            filed_row.get("recommended"),
            filed_row.get("reason"),
        )
        row = _upsert(
            db,
            "test_item_axes",
            code,
            subject_id=term.id,
            subject_label=term.value,
            context=_context(filed_row.get("context"), filed_row),
            candidates=candidates,
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")
    _sweep_gone(db, "test_item_axes", set(items), "시험 항목이 지워짐")


def _refresh_property_links(db: Session, filed: dict[str, dict[str, Any]]) -> None:
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
            candidates=_mark(
                YES_NO["property_links"], filed_row.get("recommended"), filed_row.get("reason")
            ),
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


def _refresh_free_spec_definitions(db: Session, filed: dict[str, dict[str, Any]]) -> None:
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
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


def _refresh_method_cleanup(db: Session, filed: dict[str, dict[str, Any]]) -> None:
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


def _refresh_test_item_properties(db: Session, filed: dict[str, dict[str, Any]]) -> None:
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
    for queue in QUEUES:
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
        link=queue.link.format(id=row.subject_id)
        if row.subject_id or "{id}" not in queue.link
        else None,
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
