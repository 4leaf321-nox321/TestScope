"""허브 연계 설정 · 현황 · 이력 · 수신 데이터 조회."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.jobs import kinds, queue
from app.jobs.models import Job
from app.modules.accounts.models import User
from app.modules.hub import sync
from app.modules.hub.client import HubClient, HubError, core_base
from app.modules.hub.models import (
    CoreItem,
    CoreRelation,
    CoreSyncRun,
    CoreSyncState,
    HubConnection,
)
from app.modules.hub.schemas import (
    HubCheckOut,
    HubConnectionOut,
    HubItemDetailOut,
    HubItemOut,
    HubItemPage,
    HubPublicTypeOut,
    HubRelationOut,
    HubRunOut,
    HubStateOut,
    HubStatusOut,
    HubTypeOut,
    HubTypeStatusOut,
)
from app.modules.vocabulary.models import Vocabulary
from app.shared import audit, secretbox
from app.shared.errors import AppError, Conflict, Forbidden, NotFound
from app.shared.request_context import get_actor_token

#: 수신 데이터 목록의 상한.
MAX_ITEMS = 200


def _counts(db: Session, stmt: Any) -> dict[str, int]:
    """(타입, 수) 줄 → 사전."""
    return {str(slug): int(count) for slug, count in db.execute(stmt).all()}


def _types(conn: HubConnection, catalog: dict[str, Any] | None = None) -> list[HubTypeOut]:
    source = catalog if catalog is not None else (conn.catalog or {})
    return [
        HubTypeOut(
            slug=str(one.get("slug")),
            label=str(one.get("label") or one.get("slug")),
            description=str(one.get("description") or ""),
            count=int(one.get("count") or 0),
            properties=len(one.get("properties") or []),
            relations=[str(x) for x in one.get("relations") or []],
            selected=conn.selected_types is None or one.get("slug") in conn.selected_types,
        )
        for one in source.get("types") or []
    ]


def connection_out(db: Session) -> HubConnectionOut:
    conn = sync.connection(db)
    return HubConnectionOut(
        base_url=conn.base_url,
        has_token=bool(conn.token_sealed),
        token_readable=bool(secretbox.unseal(conn.token_sealed)),
        token_set_at=conn.token_set_at,
        ca_bundle=conn.ca_bundle,
        selected_types=conn.selected_types,
        nightly_at=conn.nightly_at,
        enabled=conn.enabled,
        catalog_revision=conn.catalog_revision,
        catalog_as_of=(conn.catalog or {}).get("as_of"),
        catalog_changed_at=conn.catalog_changed_at,
        types=_types(conn),
    )


def update_connection(db: Session, user: User, payload: dict[str, Any]) -> HubConnectionOut:
    """연계 설정을 바꾼다. **토큰은 감사에도 안 남긴다** — 바뀌었다는 사실만.

    **기계 자격은 토큰을 못 넣고 못 지운다**(2026-10-22 사용자 결정). 다른 설정은 사람이 AI
    화면에서 수락하면 MCP 로도 바꾸지만(ADR 0013), 토큰을 실어 보내면 평문 비밀이 AI 대화
    기록에 남는다 — 그래서 토큰 칸은 화면에서만.
    """
    if get_actor_token() is not None and (payload.get("token") or payload.get("clear_token")):
        raise Forbidden(
            "TSC-HUB-0007",
            "허브 토큰은 화면(관리 > 허브 연계)에서만 입력 · 삭제. 평문 비밀이 AI 대화 기록에"
            " 남음. 다른 설정(주소 · 받을 타입 · 야간 시각 · 켜기)은 MCP 로 가능.",
        )
    conn = sync.connection(db)
    base_url = str(payload.get("base_url") or "").strip()
    if base_url:
        try:
            core_base(base_url)
        except HubError as exc:
            raise AppError("TSC-HUB-0003", exc.message, status=400) from exc
    before = {
        "base_url": conn.base_url,
        "selected_types": conn.selected_types,
        "nightly_at": conn.nightly_at,
        "enabled": conn.enabled,
        "ca_bundle": conn.ca_bundle,
    }
    conn.base_url = base_url
    token_changed = False
    if payload.get("clear_token"):
        conn.token_sealed = ""
        conn.token_set_at = None
        token_changed = True
    elif payload.get("token"):
        conn.token_sealed = secretbox.seal(str(payload["token"]).strip())
        conn.token_set_at = datetime.now(UTC)
        token_changed = True
    conn.ca_bundle = (str(payload.get("ca_bundle") or "").strip()) or None
    selected = payload.get("selected_types")
    conn.selected_types = None if selected is None else sorted({str(x) for x in selected})
    conn.nightly_at = str(payload.get("nightly_at") or "01:00")
    conn.enabled = bool(payload.get("enabled"))
    if conn.enabled and not (conn.base_url and conn.token_sealed):
        raise AppError("TSC-HUB-0004", "자동 수신을 켜려면 허브 주소와 토큰 필요.", status=400)
    after = {
        "base_url": conn.base_url,
        "selected_types": conn.selected_types,
        "nightly_at": conn.nightly_at,
        "enabled": conn.enabled,
        "ca_bundle": conn.ca_bundle,
    }
    changes: dict[str, Any] = {
        key: {"before": before[key], "after": after[key]}
        for key in before
        if before[key] != after[key]
    }
    if token_changed:
        changes["token"] = {
            "before": "(숨김)",
            "after": "(바뀜)" if conn.token_sealed else "(지움)",
        }
    audit.record(
        db,
        action=audit.HUB_CONNECTION_UPDATED,
        actor=user,
        target_table="hub_connections",
        target_id=conn.id,
        target_label="기준정보 허브 연계",
        changes=changes,
    )
    db.commit()
    return connection_out(db)


def check(db: Session) -> HubCheckOut:
    """연결 점검 — 카탈로그를 받아 본다. 받은 카탈로그는 타입 고르기에 쓰려고 둔다."""
    conn = sync.connection(db)
    try:
        api: HubClient = sync.make_client(conn)
    except AppError as exc:
        return HubCheckOut(ok=False, message=exc.message)
    try:
        catalog = api.catalog()
    except HubError as exc:
        return HubCheckOut(
            ok=False,
            message=f"{exc.message} ({exc.code or exc.status or exc.kind})",
            request_id=exc.request_id,
        )
    conn.catalog = catalog
    conn.catalog_revision = str(catalog.get("revision") or "") or conn.catalog_revision
    db.commit()
    return HubCheckOut(
        ok=True,
        message=f"연결 정상 — 공개 타입 {len(catalog.get('types') or [])}종",
        system=str(catalog.get("system") or "") or None,
        revision=str(catalog.get("revision") or "") or None,
        as_of=str(catalog.get("as_of") or "") or None,
        types=_types(conn, catalog),
        request_id=api.request_ids[-1] if api.request_ids else None,
    )


def seen_catalog_change(db: Session) -> None:
    conn = sync.connection(db)
    conn.catalog_changed_at = None
    db.commit()


def _state_out(state: CoreSyncState | None) -> HubStateOut | None:
    if state is None:
        return None
    return HubStateOut(
        as_of=state.as_of,
        last_run_at=state.last_run_at,
        last_status=state.last_status,
        last_error=state.last_error,
        last_full_at=state.last_full_at,
        stopped=state.stopped,
    )


def run_out(row: CoreSyncRun) -> HubRunOut:
    return HubRunOut(
        id=row.id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        trigger=row.trigger,
        full=row.full,
        status=row.status,
        triggered_by=row.triggered_by,
        counts=row.counts or {},
        errors=row.errors or [],
        request_ids=row.request_ids or [],
        duration_ms=row.duration_ms,
    )


def status(db: Session) -> HubStatusOut:
    conn = sync.connection(db)
    states = {(row.type_slug, row.kind): row for row in db.scalars(select(CoreSyncState))}
    totals = _counts(
        db,
        select(CoreItem.type_slug, func.count()).group_by(CoreItem.type_slug),
    )
    actives = _counts(
        db,
        select(CoreItem.type_slug, func.count())
        .where(CoreItem.deleted.is_(False), CoreItem.absent.is_(False))
        .group_by(CoreItem.type_slug),
    )
    relations = _counts(
        db,
        select(CoreRelation.type_slug, func.count())
        .where(CoreRelation.deleted.is_(False))
        .group_by(CoreRelation.type_slug),
    )
    axes = {
        str(hub): str(slug)
        for hub, slug in db.execute(
            select(Vocabulary.hub_type_slug, Vocabulary.slug).where(
                Vocabulary.hub_type_slug.is_not(None)
            )
        ).all()
    }
    catalog_types = {
        str(one.get("slug")): one for one in (conn.catalog or {}).get("types") or []
    }
    slugs = list(catalog_types) + sorted(set(totals) - set(catalog_types))
    pending = db.scalar(
        select(Job.status)
        .where(Job.kind == kinds.HUB_SYNC, Job.status.in_(("queued", "running")))
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    last = db.scalar(select(CoreSyncRun).order_by(CoreSyncRun.started_at.desc()).limit(1))
    return HubStatusOut(
        configured=bool(conn.base_url and conn.token_sealed),
        enabled=conn.enabled,
        nightly_at=conn.nightly_at,
        catalog_changed_at=conn.catalog_changed_at,
        pending_job=pending,
        last_run=run_out(last) if last else None,
        types=[
            HubTypeStatusOut(
                slug=slug,
                label=str((catalog_types.get(slug) or {}).get("label") or slug),
                axis_slug=axes.get(slug),
                selected=conn.selected_types is None or slug in conn.selected_types,
                catalog_count=int((catalog_types.get(slug) or {}).get("count") or 0),
                received=int(totals.get(slug, 0)),
                active=int(actives.get(slug, 0)),
                relations=int(relations.get(slug, 0)),
                rows=_state_out(states.get((slug, "rows"))),
                relation_state=_state_out(states.get((slug, "relations"))),
            )
            for slug in slugs
        ],
    )


def request_run(db: Session, user: User, *, full: bool) -> Job:
    """수동 실행 — 작업 큐에 넣는다. 이미 대기 · 실행 중이면 409."""
    conn = sync.connection(db)
    if not (conn.base_url and conn.token_sealed):
        raise AppError("TSC-HUB-0001", "허브 주소와 토큰 설정 필요.", status=409)
    waiting = db.scalar(
        select(Job.id).where(Job.kind == kinds.HUB_SYNC, Job.status.in_(("queued", "running")))
    )
    if waiting is not None:
        raise Conflict("TSC-HUB-0002", "허브 수신이 이미 대기 · 실행 중.")
    job = queue.enqueue(
        db,
        kind=kinds.HUB_SYNC,
        payload={
            "trigger": "manual",
            "full": full,
            "by": user.display_name or user.email,
        },
        max_attempts=1,
    )
    db.commit()
    return job


def runs(db: Session, *, limit: int, offset: int) -> list[HubRunOut]:
    rows = db.scalars(
        select(CoreSyncRun).order_by(CoreSyncRun.started_at.desc()).limit(limit).offset(offset)
    )
    return [run_out(row) for row in rows]


# ── 수신 데이터 조회 — 누구나 ────────────────────────────────────────────────


def public_types(db: Session) -> list[HubPublicTypeOut]:
    axes = list(db.scalars(select(Vocabulary).where(Vocabulary.hub_type_slug.is_not(None))))
    totals = _counts(
        db,
        select(CoreItem.type_slug, func.count()).group_by(CoreItem.type_slug),
    )
    actives = _counts(
        db,
        select(CoreItem.type_slug, func.count())
        .where(CoreItem.deleted.is_(False), CoreItem.absent.is_(False))
        .group_by(CoreItem.type_slug),
    )
    last: dict[str, datetime] = {
        str(slug): when
        for slug, when in db.execute(
            select(CoreItem.type_slug, func.max(CoreItem.received_at)).group_by(
                CoreItem.type_slug
            )
        ).all()
    }
    return sorted(
        (
            HubPublicTypeOut(
                slug=str(axis.hub_type_slug),
                label=axis.label,
                axis_slug=axis.slug,
                active=int(actives.get(str(axis.hub_type_slug), 0)),
                total=int(totals.get(str(axis.hub_type_slug), 0)),
                last_received_at=last.get(str(axis.hub_type_slug)),
            )
            for axis in axes
        ),
        key=lambda one: one.label,
    )


def _state_of(item: CoreItem) -> str:
    if item.merged_into:
        return "merged"
    if item.hidden:
        return "hidden"
    if item.deleted:
        return "deleted"
    if item.absent:
        return "absent"
    if item.status != "active":
        return "deprecated"
    return "active"


def _ref_props(db: Session, type_slug: str) -> dict[str, str]:
    """이 타입의 참조 속성 → 참조 대상 타입(카탈로그에서)."""
    conn = sync.connection(db)
    for one in (conn.catalog or {}).get("types") or []:
        if one.get("slug") == type_slug:
            return {
                str(p.get("key")): str(p.get("ref_type_slug"))
                for p in one.get("properties") or []
                if p.get("data_type") == "object_ref" and p.get("ref_type_slug")
            }
    return {}


def resolve_key(db: Session, type_slug: str, key: str) -> CoreItem | None:
    """식별자 하나 → 객체. **옛 식별자도 푼다** — 참조 값은 발신 시점 식별자다(§5.6)."""
    found = db.scalar(
        select(CoreItem).where(CoreItem.type_slug == type_slug, CoreItem.key == key)
    )
    if found is not None:
        return found
    return db.scalar(
        select(CoreItem).where(
            CoreItem.type_slug == type_slug, CoreItem.previous_keys.contains([key])
        )
    )


def _item_out(db: Session, item: CoreItem, refs: dict[str, str]) -> HubItemOut:
    names: dict[str, str] = {}
    for prop, target in refs.items():
        raw = (item.properties or {}).get(prop)
        for key in raw if isinstance(raw, list) else ([raw] if raw else []):
            hit = resolve_key(db, target, str(key))
            if hit is not None:
                names[str(key)] = hit.label
    return HubItemOut(
        key=item.key,
        label=item.label,
        status=item.status,
        state=_state_of(item),
        merged_into=item.merged_into,
        previous_keys=list(item.previous_keys or []),
        properties=dict(item.properties or {}),
        references=names,
        hub_updated_at=item.hub_updated_at,
        received_at=item.received_at,
        term_id=item.term_id,
    )


def items(
    db: Session,
    type_slug: str,
    *,
    q: str | None,
    state: str | None,
    limit: int,
    offset: int,
) -> HubItemPage:
    stmt = select(CoreItem).where(CoreItem.type_slug == type_slug)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(CoreItem.key.ilike(like), CoreItem.label.ilike(like)))
    if state == "active":
        stmt = stmt.where(
            CoreItem.deleted.is_(False),
            CoreItem.absent.is_(False),
            CoreItem.status == "active",
        )
    elif state == "inactive":
        stmt = stmt.where(
            or_(
                CoreItem.deleted.is_(True),
                CoreItem.absent.is_(True),
                CoreItem.status != "active",
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CoreItem.label).limit(min(limit, MAX_ITEMS)).offset(offset)
    )
    refs = _ref_props(db, type_slug)
    return HubItemPage(items=[_item_out(db, row, refs) for row in rows], total=total)


def item_detail(db: Session, type_slug: str, key: str) -> HubItemDetailOut:
    item = resolve_key(db, type_slug, key)
    if item is None:
        raise NotFound("TSC-HUB-0005", f"받은 객체가 아님: {type_slug} {key}")
    base = _item_out(db, item, _ref_props(db, type_slug))

    def rel_out(row: CoreRelation, other_type: str, other_key: str) -> HubRelationOut:
        other = resolve_key(db, other_type, other_key)
        return HubRelationOut(
            src=row.src_key,
            relation=row.relation,
            dst=row.dst_key,
            dst_type=row.dst_type,
            dst_label=other.label if other else None,
            deleted=row.deleted,
        )

    outgoing = [
        rel_out(row, row.dst_type, row.dst_key)
        for row in db.scalars(
            select(CoreRelation).where(
                CoreRelation.type_slug == type_slug, CoreRelation.src_key == item.key
            )
        )
    ]
    incoming = [
        rel_out(row, row.type_slug, row.src_key)
        for row in db.scalars(
            select(CoreRelation).where(
                CoreRelation.dst_type == type_slug, CoreRelation.dst_key == item.key
            )
        )
    ]
    return HubItemDetailOut(**base.model_dump(), outgoing=outgoing, incoming=incoming)
