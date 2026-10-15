"""신뢰성 시험 **수행 가능 현황** — 「우리 시험을 지금 돌릴 수 있나」 를 시험마다 한 줄로.

시험 하나씩 「되는 장비」 창(`capability`)을 열어 보면 답은 있는데, 사업부의 시험 수십 건 중
**장비가 0대인 것 · 1대뿐이라 그 장비가 서면 멈추는 것 · 교정이 곧 끝나는 장비에 기대는 것**을
한눈에 볼 자리가 없었다(2026-10-16). 그것을 시험마다 한 줄로 세운다.

## 판정은 새로 만들지 않는다

시험 항목마다 조건 속성을 검색 조건으로 옮겨(`capability.asked_conditions`) 검색의 판정
(`search.services.judge`)을 그대로 탄다 — 「되는 장비」 창과 같은 답이어야 한다. 상태(고장 ·
점검 · 폐기 제외)도 검색이 이미 거른다. 여기서 더하는 것은 **교정**뿐이다:

- 돌릴 수 있음(`ready`) — 조건이 다 맞고(match · accessory) 교정이 유효하다.
- 확인 필요(`check`) — 조건 일부가 장비에 안 적혀 있거나(partial · unknown), 교정 대상인데
  이력이 없다. **됨으로 세지 않는다**(ADR 0003) — 그렇다고 「안 됨」 도 아니다.
- 교정 만료(`expired`) — 차기 교정일이 지났다. 그 장비로 낸 값은 못 믿는다.
- 교정 임박(`soon`) — 돌릴 수 있음 중 60일 안에 교정이 끝나는 것(알림 · 홈과 같은 60일).

## 시험의 상태는 **병목 항목**이 정한다

시험은 쓰는 시험 항목이 **전부** 되어야 돈다. 그래서 항목마다 센 뒤 가장 적은 항목이 시험의
상태다: 0대(불가) · 0대인데 확인할 것이 있음(확인 필요) · 1대(1대뿐) · 교정이 곧 끝나면 1대
이하로 떨어짐(교정 임박) · 그 밖(여유). 시험 항목이 안 적힌 시험은 셀 것이 없다(항목 없음).

조건 묶음이 여럿이면 **모든 묶음을 한꺼번에** 묻는다(`capability` 의 `items` 와 같은 답) —
예외 경로까지 이 시험을 통째로 돌릴 장비다. 보수적인 쪽이 현황판에 맞다: 여유로 보였는데
막히는 것이 그 반대보다 비싸다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment
from app.modules.equipment.services import calibration_dues
from app.modules.notifications.rules import CALIBRATION_HORIZON_DAYS
from app.modules.reliability.capability import asked_conditions
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import CoverageItemOut, CoverageOut, CoverageRowOut
from app.modules.search import services as search_services
from app.modules.search.schemas import ConditionQuery, SearchRequest
from app.modules.vocabulary.models import VocabularyTerm
from app.shared.permissions import division_map

#: 조건이 다 맞는다고 말할 수 있는 판정. 부분 · 모름은 「확인 필요」 다.
SURE = frozenset({"match", "accessory"})
_VERDICT_RANK = {"match": 0, "accessory": 1, "partial": 2, "unknown": 3}

#: 시험 상태의 차례 — 급한 것이 위로.
State = Literal["none", "check", "single", "soon", "no_items", "ok"]
STATES: tuple[State, ...] = ("none", "check", "single", "soon", "no_items", "ok")

_Asked = tuple[tuple[object, ...], ...]


def _key(conditions: list[ConditionQuery]) -> _Asked:
    """같은 물음은 한 번만 판정한다 — 같은 시험 항목을 같은 조건으로 묻는 시험이 많다."""
    # 정렬 열쇠는 글자로 — 빈 칸(None)과 수를 견주면 정렬이 깨진다.
    return tuple(
        sorted(
            (
                (str(one.condition_key_id), one.at, one.at_least, one.at_most, one.text or "")
                for one in conditions
            ),
            key=repr,
        )
    )


def board(
    db: Session,
    user: User,
    *,
    division_term_id: uuid.UUID | None = None,
    today: date | None = None,
) -> CoverageOut:
    """확정된 최신판 신뢰성 시험마다 수행 가능한 장비 수. 사업부를 주면 그 사업부만.

    장비는 사업부로 좁히지 않는다(`capability` 와 같다) — 옆 사업부에 있으면 빌리러 간다.
    대신 항목마다 **시험의 사업부가 가진 것**을 따로 센다(`in_division`).
    """
    today = today or date.today()
    horizon = today + timedelta(days=CALIBRATION_HORIZON_DAYS)
    stmt = select(ReliabilityTest).where(
        ReliabilityTest.deleted_at.is_(None),
        ReliabilityTest.superseded_by_id.is_(None),
        ReliabilityTest.status == "confirmed",
    )
    if division_term_id is not None:
        stmt = stmt.where(ReliabilityTest.division_term_id == division_term_id)
    tests = list(db.scalars(stmt.order_by(ReliabilityTest.name)))

    items: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {one.id: [] for one in tests}
    for test_id, term_id, value in db.execute(
        select(
            ReliabilityTestItem.reliability_test_id,
            ReliabilityTestItem.test_item_term_id,
            VocabularyTerm.value,
        )
        .join(VocabularyTerm, VocabularyTerm.id == ReliabilityTestItem.test_item_term_id)
        .where(ReliabilityTestItem.reliability_test_id.in_(list(items)))
        .order_by(VocabularyTerm.value)
    ):
        items[test_id].append((term_id, value))
    division_terms = {
        term.id: term
        for term in db.scalars(
            select(VocabularyTerm).where(
                VocabularyTerm.id.in_({one.division_term_id for one in tests})
            )
        )
    }

    # 1) 판정 — 장비마다 가장 나은 판정 하나. 같은 장비에 같은 시험 항목이 규격별로 여럿 적혀
    # 있어도 장비는 한 대다.
    judged: dict[tuple[uuid.UUID, _Asked], dict[uuid.UUID, str]] = {}
    asked: dict[uuid.UUID, tuple[_Asked, int, int]] = {}
    for test in tests:
        conditions, skipped = asked_conditions(db, test.id)
        key = _key(conditions)
        asked[test.id] = (key, len(conditions), len(skipped))
        for term_id, _ in items[test.id]:
            if (term_id, key) in judged:
                continue
            found, _unmet = search_services.judge(
                db, user, SearchRequest(test_item_term_id=term_id, conditions=conditions)
            )
            best: dict[uuid.UUID, str] = {}
            for test_item, verdict, _matches in found:
                held = best.get(test_item.equipment_id)
                if held is None or _VERDICT_RANK.get(verdict, 9) < _VERDICT_RANK.get(held, 9):
                    best[test_item.equipment_id] = verdict
            judged[(term_id, key)] = best

    # 2) 교정 · 소유 사업부 — 나온 장비 전부를 한 번에.
    equipment_ids = {eid for best in judged.values() for eid in best}
    owners = {
        row.id: row.owner_workspace_id
        for row in db.scalars(select(Equipment).where(Equipment.id.in_(equipment_ids)))
    }
    dues = calibration_dues(db, list(equipment_ids))
    divisions = division_map(db)

    def calibration(equipment_id: uuid.UUID) -> str:
        due, _estimated, missing = dues.get(equipment_id, (None, False, False))
        if missing:
            return "missing"
        if due is None:
            return "ok"
        if due < today:
            return "expired"
        return "soon" if due <= horizon else "ok"

    rows: list[CoverageRowOut] = []
    for test in tests:
        key, asked_count, skipped_count = asked[test.id]
        outs: list[CoverageItemOut] = []
        for term_id, value in items[test.id]:
            ready = soon = check = expired = mine = 0
            for equipment_id, verdict in judged[(term_id, key)].items():
                state = calibration(equipment_id)
                if state == "expired":
                    expired += 1
                    continue
                if verdict in SURE and state in ("ok", "soon"):
                    ready += 1
                    soon += state == "soon"
                    owner = owners.get(equipment_id)
                    mine += owner is not None and divisions.get(owner) == test.division_term_id
                else:
                    check += 1
            outs.append(
                CoverageItemOut(
                    term_id=term_id,
                    value=value,
                    ready=ready,
                    in_division=mine,
                    soon=soon,
                    check=check,
                    expired=expired,
                )
            )
        state, bottleneck = _state(outs)
        division = division_terms.get(test.division_term_id)
        rows.append(
            CoverageRowOut(
                test_id=test.id,
                name=test.name,
                division_code=(division.code or "") if division else "",
                division_name=division.value if division else "",
                state=state,
                bottleneck=bottleneck.value if bottleneck else None,
                ready=bottleneck.ready if bottleneck else 0,
                items=outs,
                conditions_asked=asked_count,
                skipped_conditions=skipped_count,
            )
        )
    rows.sort(key=lambda row: (STATES.index(row.state), row.division_name, row.name))
    counts: dict[str, int] = {state: 0 for state in STATES}
    for row in rows:
        counts[row.state] += 1
    return CoverageOut(
        computed_at=datetime.now(UTC),
        horizon_days=CALIBRATION_HORIZON_DAYS,
        counts=counts,
        rows=rows,
    )


def _state(outs: list[CoverageItemOut]) -> tuple[State, CoverageItemOut | None]:
    """시험의 상태와 그것을 정한 항목(병목)."""
    if not outs:
        return "no_items", None
    weakest = min(outs, key=lambda one: (one.ready, one.check, one.value))
    if weakest.ready == 0:
        return ("check" if weakest.check else "none"), weakest
    if weakest.ready == 1:
        return "single", weakest
    # 교정이 곧 끝나는 장비가 빠지면 1대 이하로 떨어지는 항목이 있나.
    lapsing = min(outs, key=lambda one: (one.ready - one.soon, one.value))
    if lapsing.ready - lapsing.soon <= 1:
        return "soon", lapsing
    return "ok", weakest
