"""첫 설치 — 기준정보 축, 뿌리 부서, 시스템 관리자 계정 하나.

**이것 없이는 아무도 로그인할 수 없다.** 가입은 승인이 필요하고 승인할 사람이
없기 때문이다. 그래서 설치 스크립트가 반드시 한 번 돈다.

**멱등하다.** 두 번 돌려도 이미 있는 관리자의 비밀번호를 되돌리지 않고, 이미 있는
축의 이름이나 정책도 덮지 않는다 — 설치 스크립트를 다시 돌리는 일은 흔하다.

    python scripts/seed_install.py --email admin --name 관리자

비밀번호를 안 주면 난수로 만들어 **화면에 한 번만** 찍는다. 그 계정은
must_change_password 로 만들어지므로 첫 로그인에서 반드시 바뀐다.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.vocabulary.reference import ensure_reference_data
from app.modules.workspaces.models import Workspace, WorkspaceMember

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="TestScope 첫 설치 시드")
    parser.add_argument("--email", default="admin")
    parser.add_argument("--name", default="시스템 관리자")
    parser.add_argument("--password", default=None)
    parser.add_argument("--workspace-slug", default="hq")
    parser.add_argument("--workspace-name", default="본사")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # **기준정보 축이 먼저다.** 축이 없으면 장비를 등록할 때 고를 값이 없고,
        # 그러면 사람은 빈 칸으로 저장한다 — 그 빈 칸은 나중에 안 채워진다.
        counts = ensure_reference_data(db)
        if any(counts):
            print(
                f"기준정보: 축 {counts.axes}개, 조건 정의 {counts.conditions}개, "
                f"사양 그룹 {counts.spec_groups}개, 사양 정의 {counts.spec_definitions}개 추가"
                f" · 검색축 이음 {counts.linked_definitions}개"
                f", 문장→구간 {counts.converted_values}건"
            )
        else:
            print("기준정보: 이미 갖춰져 있습니다")

        workspace = db.scalar(select(Workspace).where(Workspace.slug == args.workspace_slug))
        if workspace is None:
            workspace = Workspace(slug=args.workspace_slug, name=args.workspace_name)
            db.add(workspace)
            db.flush()
            print(f"부서 생성: {workspace.slug} ({workspace.name})")

        email = args.email.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            # **이미 있으면 비밀번호를 덮어쓰지 않는다.** 설치 스크립트를 두 번
            # 돌리는 일은 흔하고, 그때 관리자 비밀번호가 조용히 바뀌면 아무도
            # 못 들어간다. 권한만 확인해 준다.
            if not user.is_system_admin:
                user.is_system_admin = True
                print(f"기존 계정에 시스템 관리자 권한 부여: {email}")
            db.commit()
            print(f"이미 있는 계정입니다: {email} (비밀번호는 그대로)")
            return 0

        password = args.password or secrets.token_urlsafe(9)
        user = User(
            email=email,
            password_hash=security.hash_password(password),
            display_name=args.name,
            status="active",
            is_system_admin=True,
            home_workspace_id=workspace.id,
            # 난수 비밀번호를 콘솔에서 받아 적는 방식이라, 첫 로그인에서 반드시
            # 바꾸게 한다 — 안 그러면 그 값이 그대로 남는다.
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
        db.commit()

        print(f"관리자 계정 생성: {email}")
        print(f"임시 비밀번호: {password}")
        print("첫 로그인에서 비밀번호를 바꿔야 합니다.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
