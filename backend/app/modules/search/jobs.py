"""검색 색인 작업 — **저장 요청 안에서 임베딩하지 않는다.**

계열 하나를 고칠 때 임베딩 왕복(수백 ms)을 요청 안에 끼우면, 고치는 사람이 그 대가를
매번 치른다. 워커가 뒤에서 한다 — 반입이 끝날 때 넣고(`import_catalog.py`), 하루 한 번
주기로도 돈다(`app/jobs/schedule.py`).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.jobs import handlers, kinds
from app.shared import embeddings, semantic

logger = logging.getLogger(__name__)


@handlers.handler(kinds.SEARCH_REINDEX)
def reindex(db: Session, payload: dict[str, Any]) -> None:
    """카드를 다시 색인한다.

    **꺼져 있으면 조용히 넘어간다.** 임베딩 백엔드가 `off` 인 것은 고장이 아니라
    설정이고, 실패로 쌓이면 진짜 실패가 묻힌다.
    """
    if not embeddings.enabled():
        logger.info("의미 검색이 꺼져 있습니다 — 색인을 건너뜁니다.")
        return
    try:
        counted = semantic.reindex(db)
        logger.info(
            "색인 완료: 조각 %s개 · 정리 %s개", counted.get("chunks"), counted.get("removed")
        )
    except embeddings.EmbeddingError as failed:
        # 엔진이 잠깐 죽은 것과 설정이 꺼진 것은 다르다 — 이쪽은 재시도할 값이 있다.
        logger.warning("색인 실패: %s", failed)
        raise
