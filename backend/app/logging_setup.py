"""로그 — 콘솔과 파일 양쪽에. 콘솔만으로는 창을 닫는 순간 증거가 사라진다."""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from app.config import Settings
from app.shared.request_context import get_request_id

_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.app_env == "development" else logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter(_FORMAT)
    id_filter = _RequestIdFilter()

    # 콘솔을 UTF-8 로 고정한다. Windows 콘솔 기본 코드페이지(949)로는 줄표 같은
    # 문자를 인코딩하지 못해 **로그 한 줄마다 예외가 나고**, logging 이 그 예외를
    # 대신 출력해 정작 찾으려던 줄이 트레이스백에 묻힌다.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(id_filter)
    root.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        settings.log_dir / "app.log",
        when="midnight",
        backupCount=settings.log_retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(id_filter)
    root.addHandler(file_handler)

    # uvicorn 의 기동·오류·접근 로그를 전부 우리 핸들러로 흘린다. 그러면 접근
    # 로그 줄에도 요청 id 가 붙는다 — 우리가 미들웨어에서 한 줄 더 찍으면 같은
    # 요청이 두 줄이 될 뿐이다.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
