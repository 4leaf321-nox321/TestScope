"""장비 찾기.

    시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치

## 왜 SQL 한 방으로 안 거르나

조건 판정에 **모른다** 가 있기 때문이다. 장비에 그 조건이 안 적혀 있는 것과 적혀
있는데 안 되는 것은 다르고, 앞의 것은 결과에서 빼면 안 된다 — 빼면 사람은
"우리한테 그 장비 없구나" 로 읽는데, 실제로는 아직 안 적었을 뿐이다.

그래서 후보를 SQL 로 좁히고(항목·부서·거점·상태), 조건 판정은 파이썬에서 한다.
후보 수는 장비 수 규모라 이 방식으로 충분하다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import AVAILABLE_STATUSES, Equipment, EquipmentCalibration
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.properties.services import test_item_ids_for_property
from app.modules.search.schemas import (
    ConditionMatch,
    ConditionQuery,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.modules.test_items.models import EquipmentTestCondition, EquipmentTestItem
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared.permissions import visible_equipment_ids

#: 결과 상한. 넘으면 사람이 안 읽는다 — 좁히라고 말하는 편이 낫다.
MAX_HITS = 200


def _fmt(value: float | None, unit: str) -> str:
    """숫자를 사람이 읽는 꼴로. **단위를 빼지 않는다** — 20 만 적으면 N 인지
    kN 인지 알 수 없고, 그 둘은 자릿수가 셋 다르다."""
    if value is None:
        return "제한 없음"
    text = f"{value:g}"
    return f"{text} {unit}".strip()


def _asked(query: ConditionQuery, key: ConditionKey) -> str:
    unit = key.display_unit or key.si_unit
    if query.at is not None:
        return f"{_fmt(query.at, unit)} 에서"
    if query.at_least is not None:
        return f"{_fmt(query.at_least, unit)} 이상"
    if query.at_most is not None:
        return f"{_fmt(query.at_most, unit)} 이하"
    if query.text:
        return query.text
    return "지정 없음"


def _range_text(limit: EquipmentTestCondition | None, key: ConditionKey) -> str | None:
    if limit is None:
        return None
    if limit.text_value:
        return limit.text_value
    unit = key.display_unit or key.si_unit
    return f"{_fmt(limit.min_value, unit)} ~ {_fmt(limit.max_value, unit)}"


def _verdict(query: ConditionQuery, limit: EquipmentTestCondition | None) -> str:
    """조건 하나의 판정. met · unmet · unknown.

    **비어 있는 한쪽은 "제한 없음" 이다.** 0 으로 취급하면 상한을 안 적은 장비가
    전부 탈락한다 — 실제로 사람들은 아는 쪽만 적는다.
    """
    if limit is None:
        return "unknown"

    if query.text is not None:
        if limit.text_value is None:
            return "unknown"
        return "met" if limit.text_value.strip() == query.text.strip() else "unmet"

    if query.at is not None:
        if limit.min_value is not None and query.at < limit.min_value:
            return "unmet"
        if limit.max_value is not None and query.at > limit.max_value:
            return "unmet"
        # 양쪽 다 비어 있으면 범위를 안 적은 것이다 — 통과가 아니라 모름이다.
        if limit.min_value is None and limit.max_value is None:
            return "unknown"
        return "met"

    if query.at_least is not None:
        if limit.max_value is None:
            # 상한을 안 적었다. 무제한이라는 뜻일 수도, 안 적은 것일 수도 있다 —
            # **구별할 수 없으면 모른다고 답한다.** 된다고 답했다가 틀리면 그
            # 한 번으로 시스템 전체가 안 믿긴다.
            return "unknown"
        return "met" if limit.max_value >= query.at_least else "unmet"

    if query.at_most is not None:
        if limit.min_value is None:
            return "unknown"
        return "met" if limit.min_value <= query.at_most else "unmet"

    return "unknown"


def _candidates(db: Session, user: User, request: SearchRequest) -> list[EquipmentTestItem]:
    """SQL 로 좁힐 수 있는 것만 좁힌다 — 항목·규격·부서·거점·상태."""
    stmt = (
        select(EquipmentTestItem)
        .join(Equipment, Equipment.id == EquipmentTestItem.equipment_id)
        .where(EquipmentTestItem.equipment_id.in_(visible_equipment_ids(db, user)))
    )
    if request.test_item_term_id:
        stmt = stmt.where(EquipmentTestItem.test_item_term_id == request.test_item_term_id)
    elif request.property_term_id:
        # 물성 -> 그것을 내는 시험 항목 전부. **연결이 없으면 빈 목록**이지 전체가
        # 아니다 — 전체로 풀면 「인장강도」 를 물은 사람이 염수분무 챔버를 받는다.
        stmt = stmt.where(
            EquipmentTestItem.test_item_term_id.in_(
                test_item_ids_for_property(db, request.property_term_id)
            )
        )
    if request.method_id:
        # **규격 미지정 시험 항목도 남긴다.** "인장은 된다" 만 적힌 장비를 빼면, 아직
        # 규격까지 안 채운 부서의 장비가 통째로 안 보인다.
        stmt = stmt.where(
            (EquipmentTestItem.method_id == request.method_id)
            | (EquipmentTestItem.method_id.is_(None))
        )
    if not request.include_unavailable:
        stmt = stmt.where(Equipment.status.in_(AVAILABLE_STATUSES))
    if request.workspace_slug:
        workspace = db.scalar(
            select(Workspace).where(Workspace.slug == request.workspace_slug)
        )
        stmt = stmt.where(
            Equipment.owner_workspace_id == (workspace.id if workspace else None)
        )
    if request.site_term_id:
        stmt = stmt.where(Equipment.site_term_id == request.site_term_id)

    return list(db.scalars(stmt.limit(MAX_HITS * 5)))


def _limits_by_key(
    db: Session, test_item_ids: list[uuid.UUID]
) -> dict[Any, EquipmentTestCondition]:
    """(시험 항목 id, 조건 id) -> 범위.

    **한 번에 읽는다** — 시험 항목마다 조회하면 N+1 이다.
    """
    if not test_item_ids:
        return {}
    rows = db.scalars(
        select(EquipmentTestCondition).where(
            EquipmentTestCondition.equipment_test_item_id.in_(test_item_ids)
        )
    )
    return {(row.equipment_test_item_id, row.condition_key_id): row for row in rows}


def _hit_verdict(matches: list[ConditionMatch]) -> str | None:
    """시험 항목 하나의 종합 판정. None 이면 결과에서 뺀다.

    **하나라도 안 되면 뺀다.** 안 되는 장비를 목록에 남기는 것은 답이 아니라
    소음이고, 사람은 목록이 길면 위에서부터 읽다가 틀린 것을 고른다.
    """
    if any(one.verdict == "unmet" for one in matches):
        return None
    if not matches:
        return "match"
    if all(one.verdict == "unknown" for one in matches):
        return "unknown"
    if any(one.verdict == "unknown" for one in matches):
        return "partial"
    return "match"


#: 결과 정렬 우선순위. **확실한 것이 위로 온다.**
_VERDICT_RANK = {"match": 0, "partial": 1, "unknown": 2}
_CONFIDENCE_RANK = {"verified": 0, "catalog": 1, "limited": 2}


def search(db: Session, user: User, request: SearchRequest) -> SearchResponse:
    candidates = _candidates(db, user, request)
    limits = _limits_by_key(db, [one.id for one in candidates])

    keys = {
        key.id: key
        for key in db.scalars(
            select(ConditionKey).where(
                ConditionKey.id.in_([one.condition_key_id for one in request.conditions])
            )
        )
    }

    hits: list[SearchHit] = []
    unmet = 0
    for test_item in candidates:
        matches: list[ConditionMatch] = []
        for query in request.conditions:
            key = keys.get(query.condition_key_id)
            if key is None:
                continue
            limit = limits.get((test_item.id, key.id))
            matches.append(
                ConditionMatch(
                    condition_key_id=key.id,
                    condition_label=key.label,
                    display_unit=key.display_unit or key.si_unit,
                    verdict=_verdict(query, limit),
                    asked=_asked(query, key),
                    condition_range=_range_text(limit, key),
                )
            )

        verdict = _hit_verdict(matches)
        if verdict is None:
            unmet += 1
            continue

        equipment = db.get(Equipment, test_item.equipment_id)
        if equipment is None:  # pragma: no cover - FK 가 막는다
            continue
        hits.append(_hit(db, test_item, equipment, verdict, matches))

    # 확실한 것이 위로, 그다음은 검증된 시험 항목, 그다음은 자산번호. **늘 결정적이다** —
    # 같은 검색을 두 번 했을 때 순서가 다르면 사람은 결과를 못 믿는다.
    hits.sort(
        key=lambda hit: (
            _VERDICT_RANK.get(hit.verdict, 9),
            _CONFIDENCE_RANK.get(hit.confidence, 9),
            hit.asset_no,
        )
    )

    expanded: list[str] = []
    if request.property_term_id and not request.test_item_term_id:
        ids = test_item_ids_for_property(db, request.property_term_id)
        expanded = sorted(
            db.scalars(select(VocabularyTerm.value).where(VocabularyTerm.id.in_(ids)))
        )

    return SearchResponse(
        hits=hits[:MAX_HITS],
        total=len(hits),
        unmet_count=unmet,
        unregistered_equipment=_unregistered_count(db, user),
        expanded_test_items=expanded,
    )


def _hit(
    db: Session,
    test_item: EquipmentTestItem,
    equipment: Equipment,
    verdict: str,
    matches: list[ConditionMatch],
) -> SearchHit:
    item = db.get(VocabularyTerm, test_item.test_item_term_id)
    method = db.get(TestMethod, test_item.method_id) if test_item.method_id else None
    workspace = (
        db.get(Workspace, equipment.owner_workspace_id)
        if equipment.owner_workspace_id
        else None
    )
    site = db.get(VocabularyTerm, equipment.site_term_id) if equipment.site_term_id else None
    contact = db.get(User, equipment.contact_user_id) if equipment.contact_user_id else None
    due = db.scalar(
        select(EquipmentCalibration.next_due_on)
        .where(EquipmentCalibration.equipment_id == equipment.id)
        .order_by(EquipmentCalibration.calibrated_on.desc())
        .limit(1)
    )
    return SearchHit(
        equipment_test_item_id=test_item.id,
        equipment_id=equipment.id,
        asset_no=equipment.asset_no,
        equipment_name=equipment.name,
        status=equipment.status,
        workspace_name=workspace.name if workspace else None,
        site=site.value if site else None,
        location=equipment.location,
        contact_name=contact.display_name if contact else None,
        test_item=item.value if item else "",
        method_code=f"{method.code} {method.edition or ''}".strip() if method else None,
        confidence=test_item.confidence,
        note=test_item.note,
        verdict=verdict,
        conditions=matches,
        calibration_due_on=due.isoformat() if due else None,
    )


def _unregistered_count(db: Session, user: User) -> int:
    """시험 항목이 하나도 안 적힌 장비 수.

    **검색에 절대 안 걸리는 것들이다.** 결과가 빈약할 때 이 숫자가 "그런 장비가
    없다" 인지 "아직 안 적었다" 인지를 가른다.
    """
    registered = select(EquipmentTestItem.equipment_id).distinct()
    return (
        db.scalar(
            select(func.count())
            .select_from(Equipment)
            .where(
                Equipment.id.in_(visible_equipment_ids(db, user)),
                Equipment.id.not_in(registered),
            )
        )
        or 0
    )


def method_conditions(db: Session, method_id: uuid.UUID) -> list[ConditionQuery]:
    """시험법이 요구하는 조건을 **검색 물음으로 바꾼다.**

    사람이 규격 하나를 고르면 조건 칸이 자동으로 채워져야 한다 — 아니면 규격서를
    펴 놓고 숫자를 옮겨 적어야 하고, 그 옮겨 적기에서 자릿수가 틀린다.

    min 만 있으면 그 값 이상, max 만 있으면 그 값 이하, 둘 다 있으면 양끝을 각각
    묻는다(가운데 한 점만 물으면 범위를 좁게 적은 장비가 걸러지지 않는다).
    """
    rows = db.scalars(
        select(MethodRequirement).where(MethodRequirement.method_id == method_id)
    )
    out: list[ConditionQuery] = []
    for row in rows:
        if row.text_value is not None:
            out.append(
                ConditionQuery(condition_key_id=row.condition_key_id, text=row.text_value)
            )
            continue
        if row.min_value is not None:
            out.append(
                ConditionQuery(condition_key_id=row.condition_key_id, at_most=row.min_value)
            )
        if row.max_value is not None:
            out.append(
                ConditionQuery(condition_key_id=row.condition_key_id, at_least=row.max_value)
            )
    return out
