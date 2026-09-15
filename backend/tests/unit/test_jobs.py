"""작업 큐와 워커 — 넣기·집기·실패·되살리기.

여기서 지키는 것 — 같은 작업을 두 워커가 집지 않는다 · 실패는 뒤로 미뤄 다시 하고 한도를
넘기면 failed 로 남는다 · 죽은 워커가 물고 있던 작업은 되살아난다 · 핸들러의 예외가
워커를 죽이지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.jobs import handlers, queue, schedule, worker
from app.jobs.models import Job


def _kind() -> str:
    return f"test.{uuid.uuid4().hex[:8]}"


def test_넣은_작업을_한_번만_집고_끝낸다(db: Session) -> None:
    kind = _kind()
    seen: list[dict[str, Any]] = []

    @handlers.handler(kind)
    def _run(session: Session, payload: dict[str, Any]) -> None:
        seen.append(payload)

    queue.enqueue(db, kind=kind, payload={"n": 1})
    db.commit()

    assert worker.run_once(db) is True
    assert seen == [{"n": 1}]
    job = db.scalar(db.query(Job).where(Job.kind == kind).statement)
    assert job is not None and job.status == "done" and job.attempts == 1
    # 다시 돌려도 집을 것이 없다.
    assert worker.run_once(db) is False or seen == [{"n": 1}]


def test_실패는_뒤로_미루고_한도를_넘기면_failed(db: Session) -> None:
    kind = _kind()

    @handlers.handler(kind)
    def _boom(session: Session, payload: dict[str, Any]) -> None:
        raise RuntimeError("일부러")

    queue.enqueue(db, kind=kind, max_attempts=2)
    db.commit()

    assert worker.run_once(db) is True
    job = db.scalar(db.query(Job).where(Job.kind == kind).statement)
    assert job is not None
    assert job.status == "queued" and job.attempts == 1
    assert job.last_error is not None and "일부러" in job.last_error
    assert job.run_after > datetime.now(UTC)  # 백오프

    # 시각을 당겨 다시 집게 한다.
    job.run_after = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert worker.run_once(db) is True
    db.refresh(job)
    assert job.status == "failed" and job.attempts == 2 and job.finished_at is not None


def test_죽은_워커가_물고_있던_작업은_되살아난다(db: Session) -> None:
    kind = _kind()
    job = queue.enqueue(db, kind=kind)
    db.commit()
    claimed = queue.claim_next(db, worker_id="ghost:1")
    assert claimed is not None and claimed.id == job.id
    # 오래전에 집은 것처럼 만든다.
    job.locked_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()

    assert queue.reclaim_stalled(db, older_than_seconds=300) >= 1
    db.refresh(job)
    assert job.status == "queued" and job.locked_by is None


def test_같은_종류가_대기_중이면_또_넣지_않는다(db: Session) -> None:
    kind = _kind()
    assert queue.enqueue_unless_pending(db, kind=kind) is not None
    db.commit()
    assert queue.enqueue_unless_pending(db, kind=kind) is None


def test_주기_작업은_간격_안에서는_다시_넣지_않는다(db: Session) -> None:
    # 등록된 주기 작업(색인)을 한 번 넣으면 24시간 안에는 또 안 들어간다.
    before = {kind for kind, _ in schedule.PERIODIC}
    first = set(schedule.enqueue_due(db))
    db.commit()
    again = schedule.enqueue_due(db)
    assert first <= before
    assert again == []


def test_등록되지_않은_종류는_failed_로_남고_워커는_산다(db: Session) -> None:
    kind = _kind()  # 핸들러를 등록하지 않는다
    queue.enqueue(db, kind=kind, max_attempts=1)
    db.commit()
    # 앞 시험이 남긴 작업이 먼저 집힐 수 있다 — 큐가 빌 때까지 돌린다.
    for _ in range(20):
        if not worker.run_once(db):
            break
    job = db.scalar(db.query(Job).where(Job.kind == kind).statement)
    assert job is not None and job.status == "failed"
    assert job.last_error is not None and "등록되지 않은" in job.last_error
