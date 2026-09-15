"""워커 기동 진입점.

API 와 **별도 프로세스**로 돈다. 운영은 `TestScope-Worker` 서비스(service.ps1)가 이것을
띄우고, 개발은 창 하나를 더 열어 실행한다.

    .\.venv\Scripts\python.exe run_worker.py

처리 중 멈추면 그 작업은 다음 기동 때 `reclaim_stalled` 이 되살린다 — 영영 `running`
으로 남지 않는다.
"""

from __future__ import annotations

from app.config import get_settings
from app.jobs.worker import main
from app.logging_setup import setup_logging


def run() -> None:
    settings = get_settings()
    setup_logging(settings)
    print(
        f"""
    ================================================================
      TestScope 워커
      env      : {settings.app_env}
      logs     : {settings.log_dir}
    ================================================================
    """
    )
    main()


if __name__ == "__main__":
    run()
