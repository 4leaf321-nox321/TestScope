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

from sqlalchemy import delete, select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.config import get_settings
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.auth import security
from app.modules.auth.models import PersonalAccessToken
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.properties.models import TestItemProperty
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.review.models import ReviewProposal
from app.modules.vocabulary.models import VocabularyAlias, VocabularyTerm
from app.modules.workspaces.models import Workspace, WorkspaceMember

survive_cp949()

EMAIL = "mcp-probe@testscope.local"
NAME = "MCP 확인용(임시)"
#: 왕복이 만드는 것에 붙는 표. 지울 때 이것으로 찾는다.
TAG = "MCP확인"
METHOD_TAG = "MCP "


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
