"""카탈로그 기종 등록 요청 — **못 고르는 쪽에 말할 자리.**

장비를 등록할 때 카탈로그에 그 기종이 없으면 비워 두게 되어 있다. 그 안내는 맞다: 비슷한
기종을 고르면 그 장비의 하중·온도가 **남의 것**이 되고, 조건으로 장비를 찾는 화면이 그
수치로 답한다. 그런데 비워 둔 다음에 **왜 비었는지가 아무 데도 안 남았다** — 제조사·모델명을
글자로 적긴 하지만 그것은 표시용이고, 관리자는 미연결 목록에서 그 글자를 보고 짐작해야 했다.

카탈로그 정본을 아무나 못 고치는 것은 그대로 둔다(기종을 고르면 그 계열의 시험 항목이
복사되고 조건 판정이 그 사양을 쓴다). 대신 시험 항목 제안(`reliability/proposals.py`)과
**같은 모양**으로 요청을 받는다 — 닫힌 축에 값을 못 더하는 자리의 방식이 하나여야, 다음에
같은 문제가 나왔을 때 또 새로 고민하지 않는다.

    누구나 요청을 남긴다  →  같은 말끼리 모인다  →  관리자가 한 번 정한다
                                                 →  요청한 장비들에 한꺼번에 걸린다

**정하면 그 장비들이 실제로 이어진다.** 여기까지 안 하면 관리자는 기종을 세우고 나서
장비를 하나씩 열어 다시 고르게 되고, 그 일이 밀리면 요청은 남았는데 장비는 여전히
미연결인 상태가 된다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentModelProposal,
    EquipmentSeries,
)
from app.modules.equipment.schemas import (
    EquipmentModelProposalGroupOut,
    EquipmentModelProposalOut,
)
from app.shared import audit
from app.shared.errors import AppError, Forbidden, NotFound
from app.shared.permissions import get_equipment, require_owner_edit
from app.shared.request_context import get_actor_token
from app.shared.text import clean, compare_key

OPEN = "open"
#: 정한 것들 — 이미 있던 기종에 이었다 · 카탈로그에 세웠다 · 아니라고 했다.
DECIDED = ("linked", "created", "rejected")


def proposal_key(maker: str | None, model: str) -> str:
    """같은 요청을 모으는 비교키 — 제조사와 모델명을 합쳐 띄어쓰기까지 지운다.

    「Instron 68FM-300」 과 「instron 68fm-300」 이 다른 줄로 서면 관리자가 같은 판단을 두
    번 한다. 시험 항목 제안·속성 이름과 같은 규칙이다.
    """
    return "".join(compare_key(f"{maker or ''} {model}").split())


def said(row: EquipmentModelProposal) -> str:
    """사람이 읽는 한 줄 — 「Instron 68FM-300」. 제조사를 안 적었으면 모델명만."""
    return f"{row.maker_text} {row.model_text}".strip() if row.maker_text else row.model_text


def _out(db: Session, row: EquipmentModelProposal) -> EquipmentModelProposalOut:
    equipment = db.get(Equipment, row.equipment_id)
    model = db.get(EquipmentModel, row.model_id) if row.model_id else None
    return EquipmentModelProposalOut(
        id=row.id,
        maker_text=row.maker_text,
        model_text=row.model_text,
        text=said(row),
        note=row.note,
        status=row.status,
        equipment_id=row.equipment_id,
        equipment_asset_no=equipment.asset_no if equipment else "(장비 없음)",
        equipment_name=equipment.name if equipment else "(장비 없음)",
        model_id=row.model_id,
        model_name=model.name if model else None,
        submitted_via=row.submitted_via,
        created_at=row.created_at,
    )


def of_equipment(db: Session, equipment_id: uuid.UUID) -> list[EquipmentModelProposalOut]:
    """그 장비에 붙은 요청 — **왜 기종이 비었는지가 그 장비 화면에 보인다.**"""
    rows = db.scalars(
        select(EquipmentModelProposal)
        .where(EquipmentModelProposal.equipment_id == equipment_id)
        .order_by(EquipmentModelProposal.created_at)
    )
    return [_out(db, one) for one in rows]


def add(
    db: Session, user: User, equipment_id: uuid.UUID, payload: dict[str, Any]
) -> EquipmentModelProposalOut:
    """요청 한 줄. **그 장비를 고칠 수 있는 사람이면 낼 수 있다.**

    카탈로그에 기종을 세우는 것이 아니라 「이런 기종을 못 찾았다」 를 적는 것이라, 정본의
    빗장을 건드리지 않는다.
    """
    equipment = get_equipment(db, user, equipment_id)
    # 권한 규칙은 **공용 자리 하나**다 — 장비를 고칠 수 있는 사람이면 요청도 낼 수 있다.
    require_owner_edit(
        db,
        user,
        equipment.owner_workspace_id,
        what="보유 장비",
        code="TSC-EQUIPMENT",
        role="member",
    )
    model_text = clean(str(payload.get("model_text") or ""))
    if not model_text:
        raise AppError("TSC-EQUIPMENT-0040", "요청할 모델명을 적어 주십시오.")
    maker_text = clean(str(payload.get("maker_text") or "")) or None
    key = proposal_key(maker_text, model_text)
    if not key:
        raise AppError("TSC-EQUIPMENT-0040", "요청할 모델명을 적어 주십시오.")

    found = db.scalar(
        select(EquipmentModelProposal).where(
            EquipmentModelProposal.equipment_id == equipment.id,
            EquipmentModelProposal.normalized == key,
        )
    )
    if found is not None:
        # **같은 요청을 두 번 내도 거절하지 않는다.** 등록 창을 다시 저장하는 일이 흔하고,
        # 그때 409 가 오면 사람은 저장이 실패한 것으로 읽는다.
        if payload.get("note"):
            found.note = str(payload["note"])
            db.commit()
        return _out(db, found)

    row = EquipmentModelProposal(
        equipment_id=equipment.id,
        maker_text=maker_text,
        model_text=model_text,
        normalized=key,
        note=payload.get("note") or None,
        status=OPEN,
        submitted_via=get_actor_token(),
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(db, row)


def groups(
    db: Session, *, include_decided: bool = False
) -> list[EquipmentModelProposalGroupOut]:
    """같은 요청끼리 모은 검토 목록 — **건수가 큰 것이 먼저.**

    같은 기종을 다섯 부서가 요청했으면 그것은 카탈로그에 있어야 할 기종이 거의 확실하고,
    한 번 세우면 다섯 대가 함께 이어진다. 한 번 나온 것은 자작 장비일 수 있어 뒤에 둔다.
    """
    stmt = select(EquipmentModelProposal)
    if not include_decided:
        stmt = stmt.where(EquipmentModelProposal.status == OPEN)
    rows = list(db.scalars(stmt))
    buckets: dict[str, list[EquipmentModelProposal]] = {}
    for one in rows:
        buckets.setdefault(one.normalized, []).append(one)
    out = [
        EquipmentModelProposalGroupOut(
            normalized=key,
            # 표기가 갈리면 **가장 많이 쓰인 것**을 대표로 — 라벨을 그대로 옮긴 사람이
            # 여럿이면 그 표기가 실물에 가깝다.
            text=max(
                {said(one) for one in mine},
                key=lambda t: sum(1 for x in mine if said(x) == t),
            ),
            count=len(mine),
            proposals=[_out(db, one) for one in sorted(mine, key=lambda x: x.created_at)],
        )
        for key, mine in buckets.items()
    ]
    out.sort(key=lambda one: (-one.count, one.text))
    return out


def decide(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """요청 한 묶음을 정한다 — **시스템 관리자만.**

    `model_id` 를 주면 이미 있는 기종에 잇고, `series_id` + `name` 을 주면 그 계열에 기종을
    세운 뒤 잇는다. 둘 다 없으면 아니라고 한 것이다(`rejected`) — 자작 장비처럼 카탈로그에
    올릴 것이 아닌 경우가 실제로 있다.

    이은 기종은 **요청한 장비들에 한꺼번에 걸린다.** 여기까지 안 하면 관리자는 기종을 세우고
    나서 장비를 하나씩 열어 다시 골라야 하고, 그 일이 밀리면 요청은 정해졌는데 장비는
    여전히 미연결로 남는다.
    """
    from app.modules.equipment import services

    if not user.is_system_admin:
        raise Forbidden(
            "TSC-EQUIPMENT-0041",
            "카탈로그 기종은 시스템 관리자가 세웁니다 — 기종을 고르면 그 계열의 시험 항목이"
            " 복사되고 조건 판정이 그 사양을 씁니다.",
        )
    key = str(payload["normalized"]).strip()
    rows = list(
        db.scalars(
            select(EquipmentModelProposal).where(
                EquipmentModelProposal.normalized == key,
                EquipmentModelProposal.status == OPEN,
            )
        )
    )
    if not rows:
        raise NotFound("TSC-EQUIPMENT-0042", "그 기종 등록 요청을 찾을 수 없습니다.")

    model: EquipmentModel | None = None
    status = "rejected"
    if payload.get("model_id"):
        model = db.get(EquipmentModel, uuid.UUID(str(payload["model_id"])))
        if model is None or model.deleted_at is not None:
            raise NotFound("TSC-EQUIPMENT-0042", "그 기종을 찾을 수 없습니다.")
        status = "linked"
    elif payload.get("series_id"):
        model = _create_model(db, user, payload)
        status = "created"

    linked = 0
    failed: list[dict[str, str]] = []
    for one in rows:
        one.status = status
        one.model_id = model.id if model else None
        one.decided_at = datetime.now(UTC)
        one.decided_by_id = user.id
        if model is None:
            continue
        try:
            # **제 경로를 지난다.** 기종을 이으면 개체가 적어 둔 분류·제조사·모델명을
            # 서버가 비우는데, 그 규칙은 `services.update` 한 곳에만 있다.
            services.update(db, user, one.equipment_id, {"model_id": model.id}, commit=False)
            linked += 1
        except AppError as stopped:
            # **한 대가 막혀도 나머지는 잇는다** — 열 대 중 한 대가 폐기됐다고 전부
            # 되돌리면 관리자는 그 한 대를 찾아 고치고 처음부터 다시 눌러야 한다.
            failed.append({"equipment_id": str(one.equipment_id), "reason": stopped.message})
    audit.record(
        db,
        action=audit.EQUIPMENT_MODEL_PROPOSAL_DECIDED,
        actor=user,
        target_table="equipment_model_proposals",
        target_id=rows[0].id,
        target_label=f"{said(rows[0])} → {model.name if model else '아니오'} ({len(rows)}건)",
    )
    db.commit()
    return {
        "normalized": key,
        "status": status,
        "model_id": str(model.id) if model else None,
        "model_name": model.name if model else None,
        "decided": len(rows),
        "linked": linked,
        "failed": failed,
    }


def _create_model(db: Session, user: User, payload: dict[str, Any]) -> EquipmentModel:
    """계열 아래 기종을 세운다 — **카탈로그의 제 경로를 지난다**(`catalog.create_model`).

    기종 한 줄에는 비교키·계열 안 이름 유일성 같은 불변식이 걸려 있고, 여기서 모델을 직접
    만들면 그중 하나를 빠뜨린다. 시험 항목 제안이 `terms.create_term` 을 부르는 것과 같은
    이유다(거기서 `normalized` 를 빠뜨려 NOT NULL 에 걸린 적이 있다).
    """
    from app.modules.equipment import catalog

    series_id = uuid.UUID(str(payload["series_id"]))
    series = db.get(EquipmentSeries, series_id)
    if series is None or series.deleted_at is not None:
        raise NotFound("TSC-EQUIPMENT-0042", "그 계열을 찾을 수 없습니다.")
    name = clean(str(payload.get("name") or ""))
    if not name:
        raise AppError("TSC-EQUIPMENT-0040", "세울 기종의 이름을 적어 주십시오.")
    return catalog.create_model(db, user, {"series_id": series_id, "name": name})
