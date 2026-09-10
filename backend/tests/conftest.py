"""테스트 공통 준비.

**개발 DB 를 건드리지 않는다.** 접속 정보는 개발 .env 에서 읽되 데이터베이스
이름만 `<이름>_test` 로 바꿔 쓴다 — 비밀번호를 두 곳에 적으면 한쪽만 고쳐지고,
그때 시험이 도는 곳이 어디인지 아무도 모른다.

**스위트를 두 번 동시에 띄우지 않는다.** 둘 다 같은 시험 DB 를 비우므로 서로의
데이터를 지운다.

bcrypt 라운드를 낮춘다. 시험 하나가 계정을 만들고(해시) 로그인하므로(검증),
운영 라운드 그대로면 그 시간은 인증 로직이 아니라 **bcrypt 의 설계 목적**을 재는
데 쓰인다 — 시험이 보려는 것이 아니다. 검사하는 것은 그대로다: 같은 알고리즘,
같은 전처리, 같은 경로.
"""

from __future__ import annotations

import os

os.environ.setdefault("TSC_BCRYPT_ROUNDS", "4")


def _test_database_url() -> str:
    """개발 접속 정보에서 시험 DB 주소를 만든다.

    `DATABASE_URL` 을 직접 주면 그것을 그대로 쓴다(CI 가 그렇게 한다). 안 주면
    .env 의 값에서 **데이터베이스 이름만** 바꾼다.
    """
    explicit = os.environ.get("TSC_TEST_DATABASE_URL")
    if explicit:
        return explicit

    # .env 를 읽는 경로는 앱과 같아야 한다 — 여기서 따로 파싱하면 BOM 처리 같은
    # 사정이 갈린다.
    from app.config import Settings

    url = Settings().database_url
    base, _, name = url.rpartition("/")
    return f"{base}/{name}_test" if base else url


os.environ["DATABASE_URL"] = _test_database_url()

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.all_models  # noqa: F401,E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """표를 만들고 시작한다.

    마이그레이션을 돌리지 않는 이유: 시험이 보려는 것은 **지금 코드의 모델**이다.
    마이그레이션이 모델과 어긋났는지는 `alembic check` 가 본다.

    **스키마를 통째로 지운다.** `metadata.drop_all` 은 지금 모델이 아는 표만
    지우는데, 지난 판이 남긴 표가 옛 외래키로 그 표들을 붙들고 있으면 거기서
    막힌다 — 그리고 그 실패는 "테이블을 지울 수 없음" 이라는, 원인이 안 적힌
    말로 온다. 실제로 그렇게 겪었다.
    """
    name = engine.url.database or ""
    if not name.endswith("_test"):
        # **여기서 막지 않으면 개발 DB 가 통째로 날아간다.** DATABASE_URL 을
        # 잘못 준 날 그 사실을 알려 줄 자리는 여기뿐이다.
        raise RuntimeError(f"시험 DB 가 아닙니다: {name}. 이름이 _test 로 끝나야 합니다.")

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """진짜 앱을 부른다.

    접근 로그 미들웨어가 요청 처리 **밖에서** DB 를 쓰므로, 그 세션 공장도 시험
    DB 를 가리켜야 한다 — 안 그러면 접근 로그만 개발 DB 에 쌓인다.
    """
    fastapi_app.state.session_factory = SessionLocal
    with TestClient(fastapi_app) as test_client:
        yield test_client
