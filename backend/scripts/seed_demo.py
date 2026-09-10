"""데모 데이터 — **설치는 이것을 부르지 않는다.**

빈 화면으로는 이 시스템이 무엇을 하는지 보이지 않는다. 장비 몇 대와 그 역량을
넣어 두면 검색 화면이 실제로 무엇에 답하는지 한 번에 드러난다.

    python scripts/seed_demo.py            # 없는 것만 넣는다
    python scripts/seed_demo.py --purge    # 데모가 만든 것을 지운다

**자산번호에 DEMO- 를 붙인다.** 나중에 무엇이 데모였는지 알아볼 수 있어야 지울 수
있다 — 섞여 버리면 운영 장비와 구별할 방법이 없다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.capabilities.models import (
    Capability,
    ModelCapability,
    ModelCapabilityLimit,
)
from app.modules.equipment.catalog import copy_capabilities_to
from app.modules.equipment.models import (
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
)
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared.text import clean, compare_key

survive_cp949()

#: 데모가 만든 장비의 표식. 지울 때 이것으로 찾는다.
PREFIX = "DEMO-"

#: (자산번호, 이름, 분류, 제조사, 모델, 거점, 위치, 상태)
EQUIPMENT = [
    (
        f"{PREFIX}UTM-001",
        "만능재료시험기 300kN",
        "만능재료시험기",
        "Instron",
        "5982",
        "본사 연구동",
        "3동 201호",
        "operational",
    ),
    (
        f"{PREFIX}UTM-002",
        "만능재료시험기 50kN",
        "만능재료시험기",
        "MTS",
        "Criterion 43",
        "본사 연구동",
        "3동 203호",
        "operational",
    ),
    (
        f"{PREFIX}IMP-001",
        "샤르피 충격시험기",
        "충격시험기",
        "Zwick",
        "HIT450P",
        "제2공장",
        "가공동 1층",
        "operational",
    ),
    (
        f"{PREFIX}HRD-001",
        "로크웰 경도계",
        "경도계",
        "Mitutoyo",
        "HR-530",
        "본사 연구동",
        "3동 105호",
        "maintenance",
    ),
]

#: (자산번호, 시험 항목, 신뢰도, 비고, {조건 키: (최소, 최대)})
CAPABILITIES: list[
    tuple[str, str, str, str | None, dict[str, tuple[float | None, float | None]]]
] = [
    (
        f"{PREFIX}UTM-001",
        "인장",
        "verified",
        None,
        {"temperature": (-70, 300), "force": (0, 300), "crosshead_speed": (0.001, 500)},
    ),
    (
        f"{PREFIX}UTM-001",
        "압축",
        "catalog",
        None,
        {"force": (0, 300), "temperature": (-70, 300)},
    ),
    (
        f"{PREFIX}UTM-002",
        "인장",
        "verified",
        None,
        {"temperature": (10, 35), "force": (0, 50), "crosshead_speed": (0.005, 1000)},
    ),
    # **온도를 일부러 안 적은 역량.** 검색이 "모른다" 를 어떻게 보여 주는지 드러난다.
    (
        f"{PREFIX}IMP-001",
        "충격",
        "verified",
        "저온 시험은 별도 냉각조 필요 — 담당자 확인",
        {"force": (0, 450)},
    ),
    (f"{PREFIX}HRD-001", "경도", "catalog", "지그 제작 2주 소요", {}),
]

#: (규격 번호, 판, 제목, 시험 항목, 기관, {조건 키: (최소, 최대)})
METHODS: list[tuple[str, str, str, str, str, dict[str, tuple[float | None, float | None]]]] = [
    (
        "ASTM E8/E8M",
        "2024",
        "Standard Test Methods for Tension Testing of Metallic Materials",
        "인장",
        "ASTM",
        {"force": (20, None)},
    ),
    (
        "ISO 6892-1",
        "2019",
        "Metallic materials - Tensile testing at room temperature",
        "인장",
        "ISO",
        {"temperature": (10, 35), "force": (20, None)},
    ),
    (
        "ASTM E23",
        "2023",
        "Standard Test Methods for Notched Bar Impact Testing",
        "충격",
        "ASTM",
        {"force": (0, 400)},
    ),
]


def _term(db: Session, axis_slug: str, value: str, actor: User) -> VocabularyTerm:
    """기준정보 값을 없으면 만든다. **비교키로 찾는다** — 표기가 달라도 같은 값이다."""
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == axis_slug))
    if axis is None:
        raise SystemExit(
            f"기준정보 축 '{axis_slug}' 가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요."
        )
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
        created_by_id=actor.id,
    )
    db.add(found)
    db.flush()
    return found


def _model(db: Session, maker: str, category: str, name: str, actor: User) -> EquipmentModel:
    """카탈로그 항목을 없으면 만든다 — **계열과 기종을 함께.**

    제조사·분류는 계열이 갖고, 보유 장비가 가리키는 것은 기종이다(ADR 0006).
    데모는 기종 하나짜리 계열을 만든다 — 단품을 넣는 가장 짧은 길이 그것이고,
    실무에서도 카탈로그에 없는 장비는 그렇게 들어온다.
    """
    maker_term = _term(db, "manufacturer", maker, actor)
    normalized = compare_key(name)
    series = db.scalar(
        select(EquipmentSeries).where(
            EquipmentSeries.normalized == normalized,
            EquipmentSeries.maker_term_id == maker_term.id,
        )
    )
    if series is None:
        series = EquipmentSeries(
            name=clean(name),
            normalized=normalized,
            maker_term_id=maker_term.id,
            category_term_id=_term(db, "equipment_category", category, actor).id,
            summary="데모 데이터",
            created_by_id=actor.id,
        )
        db.add(series)
        db.flush()

    found = db.scalar(
        select(EquipmentModel).where(
            EquipmentModel.series_id == series.id, EquipmentModel.normalized == normalized
        )
    )
    if found is not None:
        return found
    found = EquipmentModel(
        series_id=series.id,
        name=clean(name),
        normalized=normalized,
        summary="데모 데이터",
        created_by_id=actor.id,
    )
    db.add(found)
    db.flush()
    return found


def _conditions(db: Session) -> dict[str, ConditionKey]:
    return {row.key: row for row in db.scalars(select(ConditionKey))}


def purge(db: Session) -> int:
    """데모가 만든 장비와 그 아래 것들을 지운다. 기준정보 값은 남긴다 —
    운영에서 이미 쓰고 있을 수 있고, 그것을 지우면 가리키던 것이 끊긴다."""
    rows = list(db.scalars(select(Equipment).where(Equipment.asset_no.startswith(PREFIX))))
    for row in rows:
        db.delete(row)  # 역량·교정은 CASCADE 로 함께 간다
    for method in db.scalars(select(TestMethod).where(TestMethod.summary == "데모 데이터")):
        db.delete(method)
    # 장비를 먼저 지운 뒤라야 모델을 지울 수 있다(RESTRICT).
    for model in db.scalars(
        select(EquipmentModel).where(EquipmentModel.summary == "데모 데이터")
    ):
        db.delete(model)
    db.commit()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="TestScope 데모 데이터")
    parser.add_argument("--purge", action="store_true", help="데모가 만든 것을 지운다")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.purge:
            print(f"데모 장비 {purge(db)}대를 지웠습니다.")
            return 0

        actor = db.scalar(select(User).where(User.is_system_admin.is_(True)))
        if actor is None:
            raise SystemExit(
                "시스템 관리자가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요."
            )
        workspace = db.scalar(select(Workspace).order_by(Workspace.sort_order))
        if workspace is None:
            raise SystemExit("부서가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요.")
        conditions = _conditions(db)
        if not conditions:
            raise SystemExit("조건 정의가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요.")

        # --- 시험법 --------------------------------------------------------
        methods: dict[str, TestMethod] = {}
        for code, edition, title, item, body, requirements in METHODS:
            found = db.scalar(
                select(TestMethod).where(
                    TestMethod.code == code, TestMethod.edition == edition
                )
            )
            if found is None:
                found = TestMethod(
                    code=code,
                    edition=edition,
                    title=title,
                    test_item_term_id=_term(db, "test_item", item, actor).id,
                    body_term_id=_term(db, "standard_body", body, actor).id,
                    summary="데모 데이터",
                    created_by_id=actor.id,
                )
                db.add(found)
                db.flush()
                for key, (low, high) in requirements.items():
                    db.add(
                        MethodRequirement(
                            method_id=found.id,
                            condition_key_id=conditions[key].id,
                            min_value=low,
                            max_value=high,
                        )
                    )
            methods[code] = found

        # --- 장비 ----------------------------------------------------------
        made = 0
        for asset_no, name, category, maker, model, site, location, status in EQUIPMENT:
            if db.scalar(select(Equipment).where(Equipment.asset_no == asset_no)):
                continue
            equipment = Equipment(
                asset_no=asset_no,
                name=name,
                model_id=_model(db, maker, category, model, actor).id,
                site_term_id=_term(db, "site", site, actor).id,
                location=location,
                status=status,
                owner_workspace_id=workspace.id,
                contact_user_id=actor.id,
                created_by_id=actor.id,
            )
            db.add(equipment)
            db.flush()
            # 교정 하나는 일부러 지난 날짜로 둔다 — 홈의 「남은 일」 이 실제로 뜬다.
            overdue = asset_no.endswith("HRD-001")
            db.add(
                EquipmentCalibration(
                    equipment_id=equipment.id,
                    calibrated_on=date.today() - timedelta(days=400 if overdue else 60),
                    next_due_on=date.today() + timedelta(days=-35 if overdue else 305),
                    certificate_no=f"CAL-{asset_no[-3:]}",
                    provider="한국계량측정협회",
                )
            )
            made += 1

        db.flush()

        # --- 역량 ----------------------------------------------------------
        by_asset = {
            row.asset_no: row
            for row in db.scalars(
                select(Equipment).where(Equipment.asset_no.startswith(PREFIX))
            )
        }
        capabilities = 0
        for asset_no, item, confidence, note, limits in CAPABILITIES:
            unit = by_asset.get(asset_no)
            if unit is None or unit.model_id is None:
                continue
            term = _term(db, "test_item", item, actor)
            # **시험 항목에 맞는 규격만 건다.** 아무거나 걸면 압축에 충격 규격이
            # 붙고, 데모를 보는 사람이 그것을 옳은 예로 읽는다.
            method = {"인장": methods.get("ASTM E8/E8M"), "충격": methods.get("ASTM E23")}.get(
                item
            )

            # **사양서에 먼저 적는다.** 카탈로그가 이 시스템의 정의 층이고, 보유
            # 장비는 거기서 복사해 만든 개체다(ADR 0004). 데모가 그 순서를 그대로
            # 보여 줘야 사람이 어디에 무엇을 적는지 안다.
            series_id = db.get(EquipmentModel, unit.model_id).series_id  # type: ignore[union-attr]
            spec = db.scalar(
                select(ModelCapability).where(
                    ModelCapability.series_id == series_id,
                    ModelCapability.test_item_term_id == term.id,
                )
            )
            if spec is None:
                spec = ModelCapability(
                    series_id=series_id,
                    test_item_term_id=term.id,
                    method_id=method.id if method else None,
                    note=note,
                )
                db.add(spec)
                db.flush()
                for key, (low, high) in limits.items():
                    db.add(
                        ModelCapabilityLimit(
                            model_capability_id=spec.id,
                            condition_key_id=conditions[key].id,
                            min_value=low,
                            max_value=high,
                        )
                    )

            exists = db.scalar(
                select(Capability).where(
                    Capability.equipment_id == unit.id,
                    Capability.test_item_term_id == term.id,
                )
            )
            if exists is not None:
                continue

            # 사양서를 이 개체로 복사한다 — 앱이 장비를 등록할 때 하는 것과 같은 일이다.
            copy_capabilities_to(db, unit, actor)
            db.flush()

            # **한 대만 실제로 해 봤다고 적는다.** 그래야 검색 결과에서 catalog 와
            # verified 가 어떻게 다르게 보이는지 드러난다.
            if confidence != "catalog":
                copied = db.scalar(
                    select(Capability).where(
                        Capability.equipment_id == unit.id,
                        Capability.test_item_term_id == term.id,
                    )
                )
                if copied is not None:
                    copied.confidence = confidence
                    copied.verified_on = date.today() - timedelta(days=30)
            capabilities += 1

        db.commit()

        # **데모 장비가 가리키는 모델**을 기준으로 센다. 모델을 누가 만들었는지로
        # 거르면(요약 문구 같은 것) 마이그레이션이 옮겨 온 모델이 빠져 요약 줄이
        # 0 을 말한다 — 실제로 그렇게 틀렸다.
        demo_units = select(Equipment.id).where(Equipment.asset_no.startswith(PREFIX))
        demo_series = select(EquipmentModel.series_id).where(
            EquipmentModel.id.in_(
                select(Equipment.model_id).where(
                    Equipment.asset_no.startswith(PREFIX), Equipment.model_id.is_not(None)
                )
            )
        )
        specs = (
            db.scalar(
                select(func.count())
                .select_from(ModelCapability)
                .where(ModelCapability.series_id.in_(demo_series))
            )
            or 0
        )
        copied_count = (
            db.scalar(
                select(func.count())
                .select_from(Capability)
                .where(Capability.equipment_id.in_(demo_units))
            )
            or 0
        )
        print(
            f"데모: 장비 {made}대, 카탈로그 사양 역량 {specs}건 "
            f"-> 복사된 개체 역량 {copied_count}건, 시험법 {len(methods)}건"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
