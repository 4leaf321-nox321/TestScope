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
from app.modules.methods.services import promote_pending
from app.modules.properties.models import TestItemProperty
from app.modules.review.models import ReviewProposal
from app.modules.review.schemas import CandidateOut, ProposalOut, QueueOut
from app.modules.test_items.models import (
    SeriesPendingMethod,
    SeriesTestItem,
    TestItemConditionKey,
)
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.modules.vocabulary.specs import SpecGroup
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
        "시험 항목의 검색축",
        "이 시험을 찾을 때 무슨 조건을 묻나. 안 정하면 축 전부를 묻는다. 여러 개를 고른다.",
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
    return [
        {
            "code": one["code"],
            "label": one["label"],
            "recommended": one["code"] in wanted,
            "reason": reason if one["code"] in wanted else one.get("reason"),
        }
        for one in candidates
    ]


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
        if not codes:
            continue
        candidates = _mark(
            [{"code": code, "label": items[code].value} for code in sorted(set(codes))],
            (filed_row or {}).get("recommended"),
            (filed_row or {}).get("reason"),
        )
        names = sorted(series_names.get(s, "") for s in cited)[:2]
        context = ("인용: " + " · ".join(n for n in names if n)) if names else None
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
        decided = (filed_row or {}).get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


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
            context=filed_row.get("context"),
            candidates=candidates,
        )
        decided = filed_row.get("decided")
        if decided and row.status == "open":
            _apply(db, row, list(decided.get("choice") or []), actor=None)
            _settle(db, row, list(decided.get("choice") or []), decided.get("by") or "정본")


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
        if link is None or link.status == "confirmed":
            if row is not None and row.status == "open":
                _settle(db, row, ["confirm" if link else "reject"], "화면에서 정함")
            continue
        row = _upsert(
            db,
            "property_links",
            subject,
            subject_id=link.id,
            subject_label=f"{item.value} → {prop.value}",
            context=filed_row.get("context"),
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
        if not rows:
            # 남은 줄이 없다 — 이미 올렸거나 지웠다.
            if row is not None and row.status == "open":
                _settle(db, row, ["promote"], "화면에서 정함")
            continue
        spec = dict(filed_row.get("definition") or {})
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
            subject_label=f"{sample.label} ({source_key}{' · ' + unit if unit else ''})",
            context=(
                f"{payload['models']}개 기종 · 예: {sample.value_text[:60]}"
                + (
                    f" → 정의 「{spec.get('label')}」 ({spec.get('kind')}, {payload['unit']})"
                    if spec
                    else ""
                )
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
    else:
        raise NotFound("TSC-REVIEW-0006", f"모르는 검토함입니다: {queue}")


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
    return [
        QueueOut(
            key=one.key,
            label=one.label,
            description=one.description,
            multi=one.multi,
            open=tally.get(one.key, {}).get("open", 0),
            decided=tally.get(one.key, {}).get("decided", 0),
            skipped=tally.get(one.key, {}).get("skipped", 0),
        )
        for one in QUEUES.values()
    ]


def get_proposal(db: Session, proposal_id: uuid.UUID) -> ReviewProposal:
    row = db.get(ReviewProposal, proposal_id)
    if row is None:
        raise NotFound("TSC-REVIEW-0007", "검토 항목을 찾을 수 없습니다.")
    return row


def proposal_out(row: ReviewProposal) -> ProposalOut:
    queue = QUEUES[row.queue]
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
    )


def list_proposals(
    db: Session, queue: str, *, status: str, limit: int, offset: int
) -> tuple[list[ProposalOut], int]:
    if queue not in QUEUES:
        raise NotFound("TSC-REVIEW-0006", f"모르는 검토함입니다: {queue}")
    base = select(ReviewProposal).where(ReviewProposal.queue == queue)
    if status != "all":
        base = base.where(ReviewProposal.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(ReviewProposal.subject_label).limit(limit).offset(offset)
    ).all()
    return [proposal_out(row) for row in rows], total


def decide(
    db: Session, user: User, proposal_id: uuid.UUID, *, choice: list[str], note: str | None
) -> ReviewProposal:
    """고른 것을 적용하고 결정으로 남긴다. **추천을 따랐는지**도 남긴다."""
    _require_admin(user)
    row = get_proposal(db, proposal_id)
    if row.status == "decided":
        raise AppError("TSC-REVIEW-0008", "이미 결정된 항목입니다.", status=409)
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
        },
        reason=note,
    )
    db.commit()
    db.refresh(row)
    return row


def skip(db: Session, user: User, proposal_id: uuid.UUID) -> ReviewProposal:
    _require_admin(user)
    row = get_proposal(db, proposal_id)
    if row.status == "decided":
        raise AppError("TSC-REVIEW-0008", "이미 결정된 항목입니다.", status=409)
    row.status = "skipped" if row.status == "open" else "open"
    db.commit()
    db.refresh(row)
    return row
