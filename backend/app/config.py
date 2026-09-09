"""설정 — DB행 → 환경변수 → 기본값 3단 fallback.

세 번째 단(DB행)은 아직 비어 있지만 자리를 지금 만들어 둔다. 자주 바뀌는 값
(워커 수·타임아웃·임계값)을 나중에 관리 화면에서 고치려면 **읽는 지점이 한 곳**
이어야 하기 때문이다. os.getenv 가 코드에 흩어지면 값 하나를 바꾸는 데 재배포가
필요해진다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    # utf-8-sig 로 읽는다. BOM 이 붙은 .env 는 **첫 줄 키만 조용히 무시된다** —
    # 그 키가 기본값으로 떨어지므로, 운영이 development 로 떠서 reload 가 켜진 채
    # 돈다. 서버에서 메모장으로 .env 를 고치기만 해도 같은 일이 나므로 읽는 쪽에서
    # 흡수한다.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8-sig", extra="ignore"
    )

    app_env: str = "development"
    """development | production. 기동 방식과 로그 수준을 가른다."""

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/testatlas"

    host: str = "0.0.0.0"
    port: int = 8020
    """8020 고정. 0.0.0.0 은 IPv4 전역 바인딩이라 localhost(::1) 로는 닿지 않는다 —
    확인은 127.0.0.1 로 한다. 개발 백엔드는 8021 을 쓴다(vite.config.ts 주석)."""

    log_dir: Path = BACKEND_DIR / "logs"
    log_retention_days: int = 30

    filestore_dir: Path = BACKEND_DIR / "filestore"
    """장비 사진·교정 성적서 같은 첨부가 사는 곳. DB 에는 경로와 해시만 둔다."""

    frontend_dist: Path = REPO_DIR / "frontend" / "dist"
    """존재하면 API 와 같은 프로세스가 SPA 를 서빙한다. 개발 중에는 없다."""

    jwt_secret: str = "dev-only-insecure-secret-change-me"
    """운영에서는 설치 스크립트가 난수로 만들어 .env 에 넣는다.

    기본값이 운영에 새어 나가면 아무나 토큰을 위조할 수 있으므로,
    app_env=production 이면서 이 값이 그대로면 **기동을 거부한다**(main.py)."""

    access_token_minutes: int = 720  # 12시간
    refresh_token_days: int = 30
    refresh_cookie_name: str = "tas_refresh"
    refresh_cookie_secure: bool = False
    """사내망 http 배포가 기본이라 False. https 로 서비스하면 True 로 올린다.
    (True 인데 http 로 접속하면 브라우저가 쿠키를 버려 로그인이 유지되지 않는다)"""

    login_delay_after: int = 5
    """같은 계정의 로그인 실패가 이 횟수부터 응답을 늦춘다. **잠그지 않는다** —
    관리자 복구가 서버 콘솔뿐인 시스템에서 잠금은 자해다."""
    login_delay_step_seconds: int = 2
    login_delay_max_seconds: int = 30
    login_failure_window_minutes: int = 15
    """이 시간 안의 실패만 센다. 지나면 처음부터."""

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5200", "http://127.0.0.1:5200"]
    )
    """개발 서버(Vite)용. 배포에서는 동일 출처라 필요 없다."""


class RuntimeSettingProvider(Protocol):
    """DB 기반 런타임 설정의 자리. runtime_settings 표가 생기면 여기에 끼운다."""

    def get(self, key: str) -> str | None: ...


class _NullProvider:
    def get(self, key: str) -> str | None:
        return None


_provider: RuntimeSettingProvider = _NullProvider()


def set_runtime_provider(provider: RuntimeSettingProvider) -> None:
    global _provider
    _provider = provider


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_setting(key: str) -> str | None:
    """3단 fallback 으로 값 하나를 읽는다. DB 행이 있으면 환경변수를 이긴다."""
    from_db = _provider.get(key)
    if from_db is not None:
        return from_db
    value = getattr(get_settings(), key, None)
    return None if value is None else str(value)
