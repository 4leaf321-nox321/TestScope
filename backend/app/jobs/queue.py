"""작업 큐의 조작 — 넣기, 집어가기, 끝내기.

집어가기는 `SELECT … FOR UPDATE SKIP LOCKED` 로 한다. 워커를 여러 개 띄워도
같은 작업을 두 번 집지 않는다 — 색인이 두 번 돌거나 후처리가 두 번 도는 것을
DB 가 막아 준다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs.models import Job


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    db: Session,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
    delay_seconds: int = 0,
    max_attempts: int = 3,
) -> Job:
    """작업을 넣는다. **커밋은 호출부가 한다.**

    도메인 변경과 같은 트랜잭션에 묶기 위해서다. 따로 커밋하면 「저장은 됐는데
    색인 작업은 안 들어간」 또는 그 반대 상태가 생긴다.
    """
    job = Job(
        kind=kind,
        payload=payload or {},
        max_attempts=max_attempts,
        run_after=_now() + timedelta(seconds=delay_seconds),
    )
    db.add(job)
    return job


def enqueue_unless_pending(db: Session, *, kind: str, **kw: Any) -> Job | None:
    """같은 종류가 이미 대기 중이면 안 넣는다.

    「전량 다시 색인」 처럼 **한 번 돌면 되는 일**은 열 번 눌러도 한 번이어야 한다.
    payload 가 다른 것끼리는 구별하지 않는다 — 그런 일은 이 함수를 안 쓴다.
    """
    pending = db.scalar(
        select(func.count()).select_from(Job).where(Job.kind == kind, Job.status == "queued")
    )
    if pending:
        return None
    return enqueue(db, kind=kind, **kw)


def claim_next(db: Session, *, worker_id: str) -> Job | None:
    """실행할 작업 하나를 잠그고 가져온다. 없으면 None."""
    job = db.scalar(
        select(Job)
        .where(Job.status == "queued", Job.run_after <= _now())
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None

    job.status = "running"
    job.attempts += 1
    job.locked_at = _now()
    job.locked_by = worker_id
    db.commit()
    return job


def complete(db: Session, job: Job) -> None:
    job.status = "done"
    job.finished_at = _now()
    job.last_error = None
    db.commit()


def fail(db: Session, job: Job, error: str, *, backoff_seconds: int = 30) -> None:
    """실패를 기록한다. 한도가 남았으면 뒤로 미뤄 다시 시도한다."""
    job.last_error = error[:2000]
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.finished_at = _now()
    else:
        job.status = "queued"
        job.locked_at = None
        job.locked_by = None
        job.run_after = _now() + timedelta(seconds=backoff_seconds * job.attempts)
    db.commit()


def reclaim_stalled(db: Session, *, older_than_seconds: int = 300) -> int:
    """워커가 죽어 running 으로 남은 작업을 되살린다.

    이 함수가 없으면 워커가 강제 종료될 때마다 그 작업이 영원히 running 으로
    남는다 — 서비스도 죽고, 콘솔이면 창을 닫는 일이 실제로 일어난다.
    """
    cutoff = _now() - timedelta(seconds=older_than_seconds)
    stalled = list(
        db.scalars(select(Job).where(Job.status == "running", Job.locked_at < cutoff))
    )
    for job in stalled:
        job.status = "queued"
        job.locked_at = None
        job.locked_by = None
    if stalled:
        db.commit()
    return len(stalled)


def get(db: Session, job_id: uuid.UUID) -> Job | None:
    return db.get(Job, job_id)


def latest_of_kind(db: Session, kind: str) -> Job | None:
    """이 종류의 가장 최근 작업 — 「지금 색인 중인가, 마지막은 언제 끝났나」 의 근거.

    실행 중인 것이 있으면 그것, 없으면 가장 최근에 만들어진 것.
    """
    running = db.scalar(
        select(Job)
        .where(Job.kind == kind, Job.status == "running")
        .order_by(Job.locked_at.desc())
        .limit(1)
    )
    if running is not None:
        return running
    return db.scalar(
        select(Job).where(Job.kind == kind).order_by(Job.created_at.desc()).limit(1)
    )


def summary(db: Session) -> dict[str, int]:
    """상태별 수. 관리자 「서버」 화면이 「실패 N건」 을 보일 근거."""
    rows = db.execute(select(Job.status, func.count()).group_by(Job.status)).all()
    return {status: int(count) for status, count in rows}
