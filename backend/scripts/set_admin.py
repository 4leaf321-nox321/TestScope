"""관리자 계정을 만들거나 고친다 — **서버 콘솔에서 쓰는 복구 도구.**

비밀번호를 잊었거나, 로그인 아이디를 바꾸거나, 강제 변경 플래그를 풀어야 할 때
쓴다. 화면으로 할 수 없는 일(자기 비밀번호를 모를 때, 아이디를 바꿔야 할 때)이라
CLI 로 둔다 — 아이디 변경에 API 를 두지 않는 이유는 그것이 감사 기록·알림이
가리키는 대상을 흔들기 때문이다.

사용:
    # 새 관리자 만들기
    python scripts/set_admin.py --email admin --password '...'

    # 기존 계정의 아이디까지 바꾸기
    python scripts/set_admin.py --email admin --password '...' \
        --rename-from admin@testatlas.local

    # 임시 비밀번호를 넘겨줄 때 (첫 로그인에 변경을 강제한다)
    python scripts/set_admin.py --email admin --password '...' --force-change

**로그인 아이디는 이메일 형식이 아니어도 된다.** 사내 관리자 계정은 `admin` 처럼
짧은 아이디를 쓰는 경우가 많고, 폐쇄망은 `.local` 같은 도메인을 쓴다 — 형식을
강하게 검사해서 얻는 것보다 로그인 자체가 성립하지 않는 손해가 크다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

# **모델을 전부 등록시킨다.** 스크립트가 손대는 모델만 import 하면, 그 모델의
# 외래키가 가리키는 표가 메타데이터에 없어 SQLAlchemy 가 매핑을 못 푼다. 앱은
# main 이 전부 부르므로 안 드러나고, **배포용 스크립트에서만 터진다.**
import app.all_models  # noqa: F401,E402
from _console import survive_cp949  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.modules.accounts.models import User  # noqa: E402
from app.modules.auth import security  # noqa: E402
from app.modules.auth.models import RefreshToken  # noqa: E402
from app.modules.workspaces.models import Workspace, WorkspaceMember  # noqa: E402

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="관리자 계정 복구 도구")
    parser.add_argument(
        "--email", required=True, help="로그인 아이디 (이메일 형식이 아니어도 된다)"
    )
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--rename-from", default=None, help="이 계정의 아이디를 --email 로 바꾼다"
    )
    parser.add_argument("--display-name", default="시스템 관리자")
    parser.add_argument(
        "--force-change",
        action="store_true",
        help="첫 로그인 시 비밀번호 변경을 강제한다 (임시 비밀번호를 넘겨줄 때)",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))

        if user is None and args.rename_from:
            old = args.rename_from.strip().lower()
            user = db.scalar(select(User).where(User.email == old))
            if user is not None:
                user.email = email
                print(f"아이디 변경: {old} -> {email}")

        if user is None:
            workspace = db.scalar(select(Workspace).order_by(Workspace.created_at))
            if workspace is None:
                sys.exit("부서가 없습니다. 먼저 scripts/seed_install.py 를 실행하세요.")
            user = User(
                email=email,
                password_hash=security.hash_password(args.password),
                display_name=args.display_name,
                status="active",
                is_system_admin=True,
                home_workspace_id=workspace.id,
            )
            db.add(user)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
            print(f"관리자 생성: {email}")
        else:
            user.password_hash = security.hash_password(args.password)
            print(f"비밀번호 변경: {email}")

        user.is_system_admin = True
        user.status = "active"
        user.deleted_at = None
        user.failed_logins = 0
        user.last_failed_login_at = None
        # **기본은 강제하지 않는다.** 관리자가 아는 비밀번호를 직접 넣는 자리라,
        # 강제를 켜면 로그인하자마자 또 바꾸라고 한다. 그러면 사람은 "바꿨는데 또
        # 뜬다" 를 반복하게 된다 — 임시 비밀번호를 남에게 넘겨줄 때만 켠다.
        user.must_change_password = args.force_change

        # 비밀번호가 바뀌었으므로 기존 세션을 전부 끊는다. 바꾼 이유가 유출일 수 있다.
        revoked = 0
        for token in db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
            )
        ):
            token.revoked_at = datetime.now(UTC)
            revoked += 1

        db.commit()

        print(f"  시스템 관리자 : {user.is_system_admin}")
        print(f"  강제 변경     : {user.must_change_password}")
        if revoked:
            print(f"  끊은 세션     : {revoked}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
