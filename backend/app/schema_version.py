"""DB 스키마가 코드보다 뒤처져 있는가 — **기동할 때 한 번 본다.**

뒤처진 채로 두면 사람은 그 사실을 **화면의 500 으로** 먼저 만난다. ORM 이 없는
컬럼을 SELECT 하기 때문인데, 오류 본문에는 "DB 가 한 리비전 뒤에 있다" 가 안
적힌다. 기동을 막지는 않는다 — 뒤처진 상태로도 되는 일이 많고, DB 에 못 붙는
상황에서 서버까지 안 뜨면 원인을 볼 화면조차 없다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

#: alembic.ini 는 backend/ 에 있다. 이 파일은 backend/app/ 이다.
_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def code_head() -> str | None:
    try:
        config = Config(str(_ALEMBIC_INI))
        # alembic.ini 의 상대 경로는 backend/ 기준이다. 다른 디렉터리에서 켜져도
        # 같은 답이 나와야 한다.
        script_location = config.get_main_option("script_location") or "migrations"
        config.set_main_option("script_location", str(_ALEMBIC_INI.parent / script_location))
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception:  # pragma: no cover - 마이그레이션 폴더가 없는 설치
        logger.debug("마이그레이션 head 를 읽지 못했습니다.", exc_info=True)
        return None


def db_revision(engine: Engine) -> str | None:
    try:
        with engine.connect() as connection:
            found = connection.scalar(text("SELECT version_num FROM alembic_version"))
        return str(found) if found is not None else None
    except Exception:
        logger.debug("alembic_version 을 읽지 못했습니다.", exc_info=True)
        return None


def warn_if_behind(engine: Engine) -> str | None:
    head = code_head()
    current = db_revision(engine)
    if head is None or current is None or current == head:
        return None

    logger.warning(
        "데이터베이스가 코드보다 뒤처져 있습니다: %s -> %s. "
        "`alembic upgrade head` 를 돌리세요. "
        "그전까지는 새 컬럼을 읽는 화면이 500 으로 실패합니다.",
        current,
        head,
    )
    return head
