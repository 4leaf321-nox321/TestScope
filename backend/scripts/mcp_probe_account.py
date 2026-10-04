"""MCP 왕복 확인용 **임시** 계정·토큰 — 만들고(mint), 끝나면 지운다(cleanup).

MCP 도구는 REST 를 부르는 얇은 껍데기라, curl 로는 멀쩡한데 **도구로 부르면 죽는** 고장이
있다(반환 모양 검증 · 경로 오타). 그것은 진짜로 도구를 불러 봐야만 드러나고, 부르려면 개인
토큰이 필요하다. 사람 계정의 토큰을 스크립트에 박아 둘 수는 없으므로 확인용 계정을 그때
만들고 그때 지운다 — CI 와 개발 PC 가 같은 절차를 쓴다.

    python scripts/mcp_probe_account.py mint      # 토큰 한 줄을 stdout 에 찍는다
    python scripts/mcp_probe_account.py cleanup   # 계정·토큰과 「MCP확인」 표 붙은 것 삭제

**운영 DB 에서는 안 돈다.** app_env 가 production 이면 거부한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.config import get_settings
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.attachments.models import Attachment
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.auth import security
from app.modules.auth.models import PersonalAccessToken
from app.modules.documents.models import SpecDocument
from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentModelProposal,
    EquipmentSeries,
)
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.properties.models import TestItemProperty
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.review.models import ReviewProposal
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import VocabularyAlias, VocabularyTerm
from app.modules.workspaces.models import Workspace, WorkspaceMember

survive_cp949()

EMAIL = "mcp-probe@testscope.local"
NAME = "MCP 확인용(임시)"
#: 왕복이 만드는 것에 붙는 표. 지울 때 이것으로 찾는다.
TAG = "MCP확인"
METHOD_TAG = "MCP "
#: 이름에 「MCP확인」 을 못 넣는 것들 — 규격서 코드와 계열·기종 이름. 왕복이 이 꼴로 만든다.
DOCUMENT_TAG = "MCP-DOC-"
SERIES_TAG = "MCP계열-"
MODEL_TAG = "MCP기종-"
#: 왕복이 올리는 파일 — 워드 한 벌과 그 안에서 꺼낸 그림(`word/media/a.png`).
UPLOADED_NAMES = (f"{TAG}%", "a.png", "word/media/%")


def _refuse_production() -> None:
    if get_settings().app_env == "production":
        raise SystemExit("운영(app_env=production)에서는 확인용 계정을 만들지 않습니다.")


def mint() -> int:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user is None:
            workspace = db.scalar(select(Workspace).order_by(Workspace.sort_order))
            if workspace is None:
                raise SystemExit("부서가 하나도 없습니다 — seed_install.py 를 먼저 돌리세요.")
            user = User(
                email=EMAIL,
                # 로그인은 안 한다 — 토큰으로만 부른다. 비밀번호는 아무도 모르는 난수.
                password_hash=security.hash_password(security.new_pat()[0]),
                display_name=NAME,
                status="active",
                is_system_admin=True,
                home_workspace_id=workspace.id,
            )
            db.add(user)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
        raw, prefix, token_hash = security.new_pat()
        db.add(
            PersonalAccessToken(
                user_id=user.id,
                name=NAME,
                scopes=["read", "catalog:write", "equipment:write"],
                prefix=prefix,
                token_hash=token_hash,
            )
        )
        db.commit()
        # 토큰만 stdout 에 — 스크립트가 `$token = python …` 으로 받는다.
        print(raw)
        return 0
    finally:
        db.close()


def _catalog_and_documents(db: Session) -> list[str]:
    """왕복이 만든 규격서 · 계열 · 기종과, 지운 시험에 붙어 있던 첨부.

    전에는 이것들을 안 지워서 **개발 DB 에 가짜 계열 19 · 기종 19 · 규격서 45 · 대상 없는 첨부
    150 이 쌓였다**(2026-10-04 실측). CI 는 매번 빈 DB 라 안 보이고, 개발 화면에서만 진짜
    카탈로그처럼 섞여 보인다. 장비를 먼저 지운 뒤에 부른다 — 기종은 장비가 가리킨다(RESTRICT).
    """
    gone: list[str] = []
    for paper in db.scalars(
        select(SpecDocument).where(SpecDocument.code.like(f"{DOCUMENT_TAG}%"))
    ):
        db.execute(delete(AttributeValue).where(AttributeValue.ref_document_id == paper.id))
        db.execute(
            delete(Attachment).where(
                Attachment.target == "spec_document", Attachment.object_id == paper.id
            )
        )
        db.delete(paper)  # 판(revisions)은 CASCADE
        gone.append(f"규격서 {paper.code}")
    lines = list(
        db.scalars(select(EquipmentSeries).where(EquipmentSeries.name.like(f"{SERIES_TAG}%")))
    )
    for model in db.scalars(
        select(EquipmentModel).where(
            EquipmentModel.name.like(f"{MODEL_TAG}%")
            | EquipmentModel.series_id.in_([one.id for one in lines])
        )
    ):
        db.delete(model)  # 사양 값 · 고유 사양은 CASCADE
        gone.append(f"기종 {model.name}")
    db.flush()
    for line in lines:
        db.delete(line)  # 시험 항목 · 관계 · 속성 값은 CASCADE
        gone.append(f"계열 {line.name}")
    # 전에 쌓인 것 — 시험은 지워졌는데 첨부 줄만 남은 것. **왕복이 올린 이름만** 본다.
    orphans = db.execute(
        delete(Attachment).where(
            Attachment.target == "reliability_test",
            ~select(ReliabilityTest.id)
            .where(ReliabilityTest.id == Attachment.object_id)
            .exists(),
            or_(*(Attachment.original_name.like(one) for one in UPLOADED_NAMES)),
        )
    ).rowcount
    if orphans:
        gone.append(f"대상 없는 첨부 {orphans}건")
    return gone


def cleanup() -> int:
    db = SessionLocal()
    gone: list[str] = []
    try:
        for test in db.scalars(
            select(ReliabilityTest).where(ReliabilityTest.name.like(f"{TAG}%"))
        ):
            db.execute(
                delete(AttributeValue).where(AttributeValue.reliability_test_id == test.id)
            )
            db.execute(
                delete(ReliabilityTestItem).where(
                    ReliabilityTestItem.reliability_test_id == test.id
                )
            )
            # 첨부는 대상을 FK 로 안 잇는다(대상이 여러 표라서) — 시험을 지워도 줄이 남는다.
            db.execute(
                delete(Attachment).where(
                    Attachment.target == "reliability_test", Attachment.object_id == test.id
                )
            )
            db.delete(test)
            gone.append(f"시험 {test.name}")
        for one in db.scalars(
            select(AttributeDefinition).where(AttributeDefinition.label.like(f"{TAG}%"))
        ):
            db.execute(delete(AttributeValue).where(AttributeValue.definition_id == one.id))
            db.execute(
                delete(ReviewProposal).where(
                    ReviewProposal.queue == "attribute_drafts",
                    ReviewProposal.subject_key == one.key,
                )
            )
            db.delete(one)
            gone.append(f"속성 {one.label}")
        for method in db.scalars(
            select(TestMethod).where(TestMethod.code.like(f"{METHOD_TAG}%"))
        ):
            db.execute(
                delete(MethodRequirement).where(MethodRequirement.method_id == method.id)
            )
            db.delete(method)
            gone.append(f"규격 {method.code}")
        for term in db.scalars(
            select(VocabularyTerm).where(VocabularyTerm.value.like(f"{TAG}%"))
        ):
            db.execute(
                delete(TestItemProperty).where(
                    (TestItemProperty.test_item_term_id == term.id)
                    | (TestItemProperty.property_term_id == term.id)
                )
            )
            db.execute(delete(VocabularyAlias).where(VocabularyAlias.term_id == term.id))
            db.delete(term)
            gone.append(f"값 {term.value}")
        # 확인용으로 등록한 장비와 그 기종 등록 요청. **요청부터 지운다** — 장비를 먼저
        # 지우면 CASCADE 가 지우긴 하지만, 여기서 세는 줄이 사라져 무엇이 지워졌는지 못 적는다.
        for unit in db.scalars(select(Equipment).where(Equipment.name.like(f"{TAG}%"))):
            db.execute(
                delete(EquipmentModelProposal).where(
                    EquipmentModelProposal.equipment_id == unit.id
                )
            )
            db.execute(
                delete(EquipmentTestItem).where(EquipmentTestItem.equipment_id == unit.id)
            )
            db.delete(unit)
            gone.append(f"장비 {unit.asset_no} {unit.name}")
        db.flush()
        gone += _catalog_and_documents(db)
        # **먼저 밀어 넣는다.** 한 트랜잭션에 두면 users 를 먼저 지우려 들고, 그 값을 만든
        # 사람이 이 계정이라 FK 에 걸려 전체가 되돌아간다 — 아무것도 안 지워진다.
        db.flush()
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user is not None:
            db.execute(
                delete(PersonalAccessToken).where(PersonalAccessToken.user_id == user.id)
            )
            db.execute(delete(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
            db.delete(user)
            gone.append("확인용 계정과 토큰")
        db.commit()
    finally:
        db.close()
    print("\n".join(f"지움: {one}" for one in gone) or "지울 것이 없습니다")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP 왕복 확인용 계정·토큰")
    parser.add_argument("verb", choices=("mint", "cleanup"))
    args = parser.parse_args()
    _refuse_production()
    return mint() if args.verb == "mint" else cleanup()


if __name__ == "__main__":
    sys.exit(main())
