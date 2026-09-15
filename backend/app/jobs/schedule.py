"""주기 작업 — **워커가 스스로 넣는다.**

**메모리에 시각을 들고 있지 않는다.** 워커는 서비스라 재시작이 잦지 않지만, 배포마다
멈췄다 뜬다. 메모리에 두면 재기동마다 처음부터 돌고, 하루에 세 번 배포하면 세 번
돈다. 대신 **큐에 이미 있는지 물어본다** — 마지막으로 넣은 시각이 곧 상태다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs import kinds, queue
from app.jobs.models import Job

#: (작업 종류, 간격 초). 여기 한 줄을 더하면 워커가 알아서 넣는다.
#:
#: 색인은 하루 한 번. 카탈로그는 반입할 때 바뀌고(그때는 반입이 직접 넣는다),
#: 화면에서 고친 것은 하루 안에 따라오면 된다 — 임베딩은 공짜가 아니다.
PERIODIC: tuple[tuple[str, int], ...] = ((kinds.SEARCH_REINDEX, 24 * 3600),)


def enqueue_due(db: Session) -> list[str]:
    """돌 때가 된 주기 작업을 넣는다. 넣은 종류를 돌려준다.

    **커밋은 호출부가 한다** — `enqueue` 와 같은 규칙이다.
    """
    added: list[str] = []
    now = datetime.now(UTC)
    for kind, every in PERIODIC:
        last = db.scalar(select(func.max(Job.created_at)).where(Job.kind == kind))
        if last is not None and now - last < timedelta(seconds=every):
            continue
        # 재시도를 안 한다. 다음 주기에 어차피 다시 돈다 — 실패한 색인을 30초
        # 뒤에 또 하는 것보다 하루 뒤에 하는 편이 맞다.
        queue.enqueue(db, kind=kind, max_attempts=1)
        added.append(kind)
    return added
