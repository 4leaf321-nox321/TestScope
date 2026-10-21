"""수신기 · 반영기 — **요청서 1.2 §5.7 을 그대로 따른다.**

    since      허브가 준 `as_of` 를 그대로 쓴다. 전 쪽을 다 받은 뒤에만 저장한다.
    cursor     해석하지 않고 그대로 돌려준다. 해석 불가(`APP-CORE-0002`)면 커서 없이 다시.
    순서       참조 대상 타입을 먼저(`ref_type_slug`). 아직 없는 병합 대상은 보류 후 재해석.
    삭제       물리 삭제 안 함 — 사용 중지 · 삭제 · 숨김은 비활성, 다시 오면 재활성.
    병합       그 값을 가리키던 시험 · 장비를 통합 대상으로 옮기고, 원 객체의 관계를 해제.
    식별자     `renamed_from` · `previous_keys` 로 찾아 식별자만 바꾼다(새로 만들지 않는다).
    전량       `since` 없이 받거나 관계 `reset` 이면 다 받은 뒤 이번에 안 온 것을
               비활성 · 해제.
    멱등       같은 것을 다시 받으면 덮어쓴다 — 두 번째 수신은 변경 0 건.

**타입 단위 트랜잭션이다.** 한 타입을 받다 실패하면 그 타입의 반영은 롤백되고 기준 시각은
그대로다 — 다음 수신이 같은 자리부터 다시 받는다.

## 온톨로지 축으로 반영한다

타입마다 축 하나(`hub_<타입>`), 객체마다 값 하나. 값의 코드가 허브 식별자, 이름이 허브 이름,
속성 칸이 허브 속성 원문이다. 그래서 기존 선택기 · 검색 · 「값 고르기」 속성 · MCP `resolve`
가 손대지 않고 허브 데이터를 쓴다. 이 축은 **잠겨 있다** — 화면 · API · MCP 로 못 고친다
(`vocabulary.hub_type_slug`).
"""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeValue
from app.modules.hub.client import HubClient, HubError
from app.modules.hub.models import (
    CoreItem,
    CoreRelation,
    CoreSyncRun,
    CoreSyncState,
    HubConnection,
)
from app.modules.notifications import rules
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.shared import secretbox
from app.shared.errors import AppError, Conflict
from app.shared.text import compare_key

AXIS_PREFIX = "hub_"
#: 이보다 오래 「실행 중」 이면 죽은 실행으로 본다 — 워커가 중간에 죽으면 표식이 남는다.
STALE_RUN = timedelta(hours=3)
#: 정기 전량 대조 주기(요청서 §5.7 8항 — 권장 주 1회).
FULL_EVERY = timedelta(days=7)


# ── 연결 ──────────────────────────────────────────────────────────────────────


def connection(db: Session) -> HubConnection:
    """연계 설정 한 줄. 없으면 빈 줄을 만든다."""
    row = db.scalar(select(HubConnection).limit(1))
    if row is None:
        row = HubConnection()
        db.add(row)
        db.flush()
    return row


def make_client(conn: HubConnection) -> HubClient:
    token = secretbox.unseal(conn.token_sealed)
    if not conn.base_url or not token:
        raise AppError(
            "TSC-HUB-0001",
            "허브 주소와 토큰 설정 필요(토큰을 못 풀면 다시 입력 — DB 를 옮겼거나"
            " JWT_SECRET 변경).",
            status=409,
        )
    return HubClient(conn.base_url, token, verify=conn.ca_bundle or True)


def axis_slug(type_slug: str) -> str:
    return (AXIS_PREFIX + type_slug)[:50]


# ── 실행 ──────────────────────────────────────────────────────────────────────


def start_run(db: Session, *, trigger: str, full: bool, by: str | None) -> CoreSyncRun:
    """실행 한 줄을 연다. **동시 실행을 막는다** — 설정 줄을 잠그고 「실행 중」 을 본다."""
    conn = db.scalar(select(HubConnection).limit(1).with_for_update())
    if conn is None:
        conn = connection(db)
    running = db.scalar(
        select(CoreSyncRun).where(
            CoreSyncRun.status == "running",
            CoreSyncRun.started_at > datetime.now(UTC) - STALE_RUN,
        )
    )
    if running is not None:
        db.rollback()
        raise Conflict("TSC-HUB-0002", "허브 수신이 이미 실행 중.")
    run = CoreSyncRun(trigger=trigger, full=full, status="running", triggered_by=by)
    db.add(run)
    db.commit()
    return run


def run(
    db: Session,
    *,
    trigger: str,
    full: bool = False,
    by: str | None = None,
    client: HubClient | None = None,
) -> CoreSyncRun:
    """카탈로그를 읽고 고른 타입을 차례로 받는다. 실행 이력을 돌려준다."""
    started = time.monotonic()
    record = start_run(db, trigger=trigger, full=full, by=by)
    errors: list[dict[str, Any]] = []
    counts: dict[str, Any] = {}
    try:
        conn = connection(db)
        api = client or make_client(conn)
        try:
            catalog = api.catalog()
        except HubError as exc:
            errors.append({"type": None, **exc.as_dict()})
            return _finish(db, record, api_ids(api), counts, errors, started)
        _apply_catalog(db, conn, catalog)
        db.commit()
        types = {str(one["slug"]): one for one in catalog.get("types") or []}
        chosen = [slug for slug in _order(types) if _selected(conn, slug)]
        for slug in chosen:
            try:
                counts[slug] = _sync_type(db, api, types[slug], full=full)
                db.commit()
            except HubError as exc:
                db.rollback()
                errors.append({"type": slug, **exc.as_dict()})
                _mark_failed(db, slug, exc)
                db.commit()
                if exc.kind == "auth":
                    # 토큰이 거절됐다 — 나머지 타입도 같은 답을 받는다. 멈추고 알린다.
                    break
        _resolve_pending(db)
        db.commit()
        return _finish(db, record, api_ids(api), counts, errors, started)
    except AppError as exc:
        db.rollback()
        errors.append({"type": None, "kind": "config", "message": exc.message})
        return _finish(db, record, [], counts, errors, started)
    except Exception as exc:
        db.rollback()
        errors.append({"type": None, "kind": "internal", "message": str(exc)[:500]})
        _finish(db, record, [], counts, errors, started)
        raise


def api_ids(api: HubClient) -> list[str]:
    return list(dict.fromkeys(api.request_ids))[:500]


def _finish(
    db: Session,
    record: CoreSyncRun,
    request_ids: list[str],
    counts: dict[str, Any],
    errors: list[dict[str, Any]],
    started: float,
) -> CoreSyncRun:
    record = db.get(CoreSyncRun, record.id) or record
    record.finished_at = datetime.now(UTC)
    record.duration_ms = int((time.monotonic() - started) * 1000)
    record.counts = counts
    record.errors = errors
    record.request_ids = request_ids
    record.status = "ok" if not errors else ("partial" if counts else "failed")
    if errors:
        # **실패는 관리자에게 알린다**(FR-13). 같은 실행에 한 번.
        rules.hub_sync_failed(db, record)
    db.commit()
    return record


def _mark_failed(db: Session, slug: str, exc: HubError) -> None:
    for kind in ("rows", "relations"):
        state = _state(db, slug, kind)
        state.last_run_at = datetime.now(UTC)
        state.last_status = "failed"
        state.last_error = f"{exc.message} ({exc.code or exc.status or exc.kind})"
        if exc.kind == "type_closed":
            state.stopped = True


def _selected(conn: HubConnection, slug: str) -> bool:
    return conn.selected_types is None or slug in conn.selected_types


def _order(types: dict[str, dict[str, Any]]) -> list[str]:
    """참조 대상 타입을 먼저 — 프로젝트 → 과제 → 개발모델. 고리가 있으면 이름순으로 끊는다."""
    deps = {
        slug: {
            str(prop.get("ref_type_slug"))
            for prop in one.get("properties") or []
            if prop.get("ref_type_slug")
            and prop.get("ref_type_slug") in types
            and prop.get("ref_type_slug") != slug
        }
        for slug, one in types.items()
    }
    out: list[str] = []
    done: set[str] = set()
    while len(out) < len(types):
        ready = sorted(slug for slug in types if slug not in done and deps[slug] <= done)
        if not ready:
            ready = [sorted(slug for slug in types if slug not in done)[0]]
        for slug in ready:
            out.append(slug)
            done.add(slug)
    return out


# ── 카탈로그 ──────────────────────────────────────────────────────────────────


def signature(catalog: dict[str, Any]) -> str:
    """구조의 지문 — 타입 · 속성(자료형 · 다중 · 참조 · 고를 값) · 관계 종류. 이름 ·
    설명은 뺀다."""
    shape = []
    for one in sorted(catalog.get("types") or [], key=lambda t: str(t.get("slug"))):
        props = sorted(
            (
                str(p.get("key")),
                str(p.get("data_type")),
                bool(p.get("multi")),
                str(p.get("ref_type_slug") or ""),
                tuple(sorted(str(x) for x in p.get("enum_options") or [])),
            )
            for p in one.get("properties") or []
        )
        kinds = sorted(
            (
                str(k.get("slug")),
                json.dumps(k.get("src"), sort_keys=True, ensure_ascii=False),
                json.dumps(k.get("dst"), sort_keys=True, ensure_ascii=False),
            )
            for k in one.get("relation_kinds") or []
        )
        shape.append((str(one.get("slug")), props, kinds))
    return json.dumps(shape, ensure_ascii=False)


def _apply_catalog(db: Session, conn: HubConnection, catalog: dict[str, Any]) -> None:
    """판(`revision`)이 바뀌면 직전과 구조를 견주고 **실제로 바뀐 때만** 알린다(FR-02)."""
    new_sig = signature(catalog)
    before = conn.catalog or {}
    if conn.catalog_signature is not None and conn.catalog_signature != new_sig:
        conn.catalog_changed_at = datetime.now(UTC)
        rules.hub_catalog_changed(db, _diff(before, catalog))
    conn.catalog = catalog
    conn.catalog_revision = str(catalog.get("revision") or "") or None
    conn.catalog_signature = new_sig
    for one in catalog.get("types") or []:
        ensure_axis(db, one)


def _diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    """사람이 읽을 한 줄 — 생긴 타입 · 사라진 타입 · 칸이 바뀐 타입."""
    old = {str(t.get("slug")): t for t in before.get("types") or []}
    new = {str(t.get("slug")): t for t in after.get("types") or []}
    parts = []
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    if added:
        parts.append("새 타입 " + ", ".join(added))
    if removed:
        parts.append("빠진 타입 " + ", ".join(removed))
    changed = [
        slug
        for slug in sorted(set(new) & set(old))
        if signature({"types": [new[slug]]}) != signature({"types": [old[slug]]})
    ]
    if changed:
        parts.append("칸이 바뀐 타입 " + ", ".join(changed))
    return " · ".join(parts) or "구조 변경"


def ensure_axis(db: Session, tdef: dict[str, Any]) -> Vocabulary:
    """타입 하나의 축. 없으면 만들고, 이름 · 설명 · 칸 정의는 카탈로그를 따른다."""
    slug = str(tdef["slug"])
    axis = db.scalar(select(Vocabulary).where(Vocabulary.hub_type_slug == slug))
    if axis is None:
        axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == axis_slug(slug)))
    label = str(tdef.get("label") or slug)[:100]
    description = str(tdef.get("description") or "") or None
    schema = [
        {
            "key": str(p.get("key")),
            "label": str(p.get("label") or p.get("key")),
            "kind": "number"
            if p.get("data_type") == "number"
            else ("list" if p.get("multi") else "text"),
        }
        for p in tdef.get("properties") or []
        if p.get("key") and p.get("key") != "aliases"
    ]
    if axis is None:
        axis = Vocabulary(
            slug=axis_slug(slug),
            label=label,
            domain="hub",
            description=description,
            entry_policy="closed",
            attribute_schema=schema,
            hub_type_slug=slug,
        )
        db.add(axis)
        db.flush()
        return axis
    axis.hub_type_slug = slug
    axis.domain = "hub"
    if axis.label != label:
        axis.label = label
    if axis.description != description:
        axis.description = description
    if axis.attribute_schema != schema:
        axis.attribute_schema = schema
    return axis


# ── 행 ────────────────────────────────────────────────────────────────────────


def _state(db: Session, slug: str, kind: str) -> CoreSyncState:
    state = db.scalar(
        select(CoreSyncState).where(
            CoreSyncState.type_slug == slug, CoreSyncState.kind == kind
        )
    )
    if state is None:
        state = CoreSyncState(type_slug=slug, kind=kind)
        db.add(state)
        db.flush()
    return state


class _Index:
    """한 타입의 사본과 축의 값 — **한 번 읽어 두고** 쪽마다 다시 묻지 않는다."""

    def __init__(self, db: Session, slug: str, axis: Vocabulary) -> None:
        self.db = db
        self.slug = slug
        self.axis = axis
        self.items: dict[str, CoreItem] = {
            row.key: row
            for row in db.scalars(select(CoreItem).where(CoreItem.type_slug == slug))
        }
        self.old: dict[str, CoreItem] = {}
        for row in self.items.values():
            for key in row.previous_keys or []:
                self.old.setdefault(key, row)
        self.terms: dict[uuid.UUID, VocabularyTerm] = {
            term.id: term
            for term in db.scalars(
                select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == axis.id)
            )
        }
        self.by_norm: dict[str, uuid.UUID] = {t.normalized: t.id for t in self.terms.values()}
        self.by_code: dict[str, uuid.UUID] = {
            t.code: t.id for t in self.terms.values() if t.code
        }
        self.aliases: set[str] = set(
            db.scalars(
                select(VocabularyAlias.normalized).where(
                    VocabularyAlias.vocabulary_id == axis.id
                )
            )
        )

    def find(self, key: str, olds: list[str]) -> CoreItem | None:
        found = self.items.get(key)
        if found is not None:
            return found
        for old in olds:
            hit = self.items.get(old) or self.old.get(old)
            if hit is not None:
                return hit
        return None


def _sync_type(
    db: Session, api: HubClient, tdef: dict[str, Any], *, full: bool
) -> dict[str, int]:
    slug = str(tdef["slug"])
    axis = ensure_axis(db, tdef)
    state = _state(db, slug, "rows")
    state.stopped = False
    since = None if full or not state.as_of else state.as_of
    index = _Index(db, slug, axis)
    had_items = bool(index.items)
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    cursor: str | None = None
    restarted = False
    as_of: str | None = None
    while True:
        try:
            page = api.rows(slug, since=since, cursor=cursor)
        except HubError as exc:
            if exc.kind == "cursor" and not restarted:
                # 커서를 못 읽었다 — 저장 기준 시각부터 처음 쪽을 다시(요청서 §5.8).
                restarted, cursor = True, None
                continue
            raise
        for row in page.get("items") or []:
            _apply_row(db, index, row, counts, seen)
        if not page.get("next"):
            as_of = page.get("as_of")
            break
        cursor = str(page["next"])
    if since is None and had_items:
        # **부재 대조** — 전량에는 삭제분이 없다. 다 받은 뒤 이번에 안 온 것을 비활성.
        for item in index.items.values():
            if item.key not in seen and not item.deleted and not item.absent:
                item.absent = True
                _project(db, index, item)
                _drop_relations(db, slug, item.key)
                counts["absent"] += 1
    state.as_of = str(as_of) if as_of else state.as_of
    state.last_run_at = datetime.now(UTC)
    state.last_status = "ok"
    state.last_error = None
    if since is None:
        state.last_full_at = datetime.now(UTC)
    out = dict(counts)
    out["catalog_count"] = int(tdef.get("count") or 0)
    out["active"] = sum(
        1 for item in index.items.values() if not (item.deleted or item.absent)
    )
    if tdef.get("relations"):
        out.update(_sync_relations(db, api, slug, full=full))
    db.flush()
    return out


def _apply_row(
    db: Session,
    index: _Index,
    row: dict[str, Any],
    counts: Counter[str],
    seen: set[str],
) -> None:
    key = str(row.get("key") or "")
    if not key:
        return
    counts["received"] += 1
    olds = [str(x) for x in [row.get("renamed_from"), *(row.get("previous_keys") or [])] if x]
    item = index.find(key, olds)
    renamed = False
    if item is not None and item.key != key:
        # **식별자 변경** — 같은 객체다. 새로 만들지 않고 식별자만 바꾼다(FR-07).
        clash = index.items.get(key)
        if clash is not None and clash.id != item.id:
            item = clash
        else:
            index.items.pop(item.key, None)
            previous = list(dict.fromkeys([*(item.previous_keys or []), item.key, *olds]))
            item.previous_keys = [one for one in previous if one != key]
            item.key = key
            index.items[key] = item
            for old in item.previous_keys:
                index.old[old] = item
            counts["renamed"] += 1
            renamed = True
    if row.get("deleted"):
        seen.add(key)
        if item is None:
            return
        was_active = not (item.deleted or item.absent)
        item.deleted = True
        item.hidden = bool(row.get("hidden"))
        item.status = str(row.get("status") or item.status)
        item.merged_into = str(row["merged_into"]) if row.get("merged_into") else None
        item.hub_updated_at = str(row.get("updated_at") or "") or item.hub_updated_at
        _project(db, index, item)
        _drop_relations(db, index.slug, item.key)
        if item.merged_into:
            if _merge(db, index, item):
                counts["merged"] += 1
            else:
                counts["merge_pending"] += 1
        elif was_active:
            counts["deactivated"] += 1
        return
    properties = row.get("properties") or {}
    previous = list(dict.fromkeys([*(row.get("previous_keys") or []), *olds]))
    if item is None:
        item = CoreItem(type_slug=index.slug, key=key, label="", status="active")
        db.add(item)
        index.items[key] = item
        counts["created"] += 1
        changed = True
    else:
        restored = item.deleted or item.absent
        changed = (
            restored
            or item.label != str(row.get("label") or key)
            or item.status != str(row.get("status") or "active")
            or (item.properties or {}) != properties
            or (item.merged_into is not None)
            or not set(previous) <= set(item.previous_keys or [])
        )
        if restored:
            counts["restored"] += 1
        elif changed:
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    if changed:
        item.label = str(row.get("label") or key)[:500]
        item.status = str(row.get("status") or "active")
        item.properties = properties
        item.deleted = False
        item.hidden = False
        item.absent = False
        item.merged_into = None
        item.previous_keys = [
            one
            for one in dict.fromkeys([*(item.previous_keys or []), *previous])
            if one != key
        ]
        for old in item.previous_keys:
            index.old[old] = item
    item.hub_updated_at = str(row.get("updated_at") or "") or item.hub_updated_at
    seen.add(key)
    if changed or renamed or item.term_id is None:
        # 식별자만 바뀌어도 값의 코드 · 별칭이 따라가야 한다.
        _project(db, index, item)


def _project(db: Session, index: _Index, item: CoreItem) -> None:
    """사본 하나 → 축의 값 하나. 이름이 겹치면 식별자를 붙여 가른다(축 안에서 이름은 유일)."""
    db.flush()
    term = index.terms.get(item.term_id) if item.term_id else None
    if term is None and item.key in index.by_code:
        term = index.terms.get(index.by_code[item.key])
    if term is None:
        for old in item.previous_keys or []:
            if old in index.by_code:
                term = index.terms.get(index.by_code[old])
                break
    value = item.label or item.key
    normalized = compare_key(value)
    owner = index.by_norm.get(normalized)
    if owner is not None and (term is None or owner != term.id):
        value = f"{item.label or item.key} [{item.key}]"
        normalized = compare_key(value)
    active = not (item.deleted or item.absent) and item.status == "active"
    status = "active" if active else "deprecated"
    if term is None:
        term = VocabularyTerm(
            vocabulary_id=index.axis.id,
            value=value[:200],
            normalized=normalized[:200],
            code=item.key[:120],
            attributes=dict(item.properties or {}),
            status=status,
        )
        db.add(term)
        db.flush()
        index.terms[term.id] = term
    else:
        if term.code and index.by_code.get(term.code) == term.id:
            index.by_code.pop(term.code, None)
        index.by_norm.pop(term.normalized, None)
        term.value = value[:200]
        term.normalized = normalized[:200]
        term.code = item.key[:120]
        if not (item.deleted or item.absent):
            # 지운 · 숨긴 객체는 속성이 비어 온다 — **가진 값을 둔다**(요청서 §5.4).
            term.attributes = dict(item.properties or {})
        term.status = status
    index.by_code[term.code or item.key] = term.id
    index.by_norm[term.normalized] = term.id
    item.term_id = term.id
    _aliases(db, index, item, term)


def _aliases(db: Session, index: _Index, item: CoreItem, term: VocabularyTerm) -> None:
    """옛 식별자와 허브 별칭을 값의 별칭으로 — 옛 식별자로 적힌 참조가 계속 풀린다(§5.6)."""
    raw = (item.properties or {}).get("aliases")
    names = [*(item.previous_keys or []), *(raw if isinstance(raw, list) else [])]
    for name in names:
        text = str(name).strip()
        if not text:
            continue
        normalized = compare_key(text)
        if normalized in index.aliases or normalized in index.by_norm:
            continue
        db.add(
            VocabularyAlias(
                vocabulary_id=index.axis.id,
                term_id=term.id,
                value=text[:200],
                normalized=normalized[:200],
            )
        )
        index.aliases.add(normalized)


def _merge(db: Session, index: _Index, item: CoreItem) -> bool:
    """병합 — 이 값을 가리키던 시험 · 장비를 통합 대상으로 옮긴다. 대상이 아직 없으면 보류."""
    target = index.find(item.merged_into or "", [item.merged_into or ""])
    if target is None or target.term_id is None or item.term_id is None:
        return False
    if target.id == item.id:
        return False
    db.execute(
        update(AttributeValue)
        .where(AttributeValue.term_id == item.term_id, AttributeValue.is_current.is_(True))
        .values(term_id=target.term_id)
    )
    return True


def _resolve_pending(db: Session) -> None:
    """보류한 병합을 다시 — 대상이 이번 수신에서 뒤늦게 들어왔을 수 있다."""
    pending = list(
        db.scalars(
            select(CoreItem).where(
                CoreItem.deleted.is_(True), CoreItem.merged_into.is_not(None)
            )
        )
    )
    by_type: dict[str, list[CoreItem]] = {}
    for item in pending:
        by_type.setdefault(item.type_slug, []).append(item)
    for slug, items in by_type.items():
        axis = db.scalar(select(Vocabulary).where(Vocabulary.hub_type_slug == slug))
        if axis is None:
            continue
        index = _Index(db, slug, axis)
        for item in items:
            _merge(db, index, item)


# ── 관계 ──────────────────────────────────────────────────────────────────────


def _drop_relations(db: Session, slug: str, key: str) -> None:
    """끝점 정리 — 지워지거나 병합된 객체를 끝으로 하는 관계를 해제(§5.7 9항)."""
    db.execute(
        update(CoreRelation)
        .where(CoreRelation.type_slug == slug, CoreRelation.src_key == key)
        .values(deleted=True)
    )
    db.execute(
        update(CoreRelation)
        .where(CoreRelation.dst_type == slug, CoreRelation.dst_key == key)
        .values(deleted=True)
    )


def _sync_relations(db: Session, api: HubClient, slug: str, *, full: bool) -> dict[str, int]:
    state = _state(db, slug, "relations")
    since = None if full or not state.as_of else state.as_of
    existing = {
        (row.src_key, row.relation, row.dst_key, row.dst_type): row
        for row in db.scalars(select(CoreRelation).where(CoreRelation.type_slug == slug))
    }
    had = bool(existing)
    counts: Counter[str] = Counter()
    seen: set[tuple[str, str, str, str]] = set()
    cursor: str | None = None
    restarted = False
    as_of: str | None = None
    while True:
        try:
            page = api.relations(slug, since=since, cursor=cursor)
        except HubError as exc:
            if exc.kind == "cursor" and not restarted:
                restarted, cursor = True, None
                continue
            raise
        if page.get("reset") and since is not None:
            # **초기화 신호** — 기준 시각이 해제 기록 보관 기한을 넘었다. 전량 다시 받고
            # 대조한다.
            since, cursor, seen = None, None, set()
            counts["reset"] += 1
            continue
        for rel in page.get("items") or []:
            ident = (
                str(rel.get("src")),
                str(rel.get("relation")),
                str(rel.get("dst")),
                str(rel.get("dst_type") or slug),
            )
            seen.add(ident)
            row = existing.get(ident)
            if rel.get("deleted"):
                if row is not None and not row.deleted:
                    row.deleted = True
                    counts["relations_removed"] += 1
                continue
            props = rel.get("properties") or {}
            note = str(rel.get("evidence_note") or "") or None
            if row is None:
                row = CoreRelation(
                    type_slug=slug,
                    src_key=ident[0],
                    relation=ident[1],
                    dst_key=ident[2],
                    dst_type=ident[3],
                )
                db.add(row)
                existing[ident] = row
                counts["relations_added"] += 1
            elif row.deleted:
                counts["relations_added"] += 1
            elif (row.properties or {}) != props or row.evidence_note != note:
                counts["relations_updated"] += 1
            row.properties = props
            row.evidence_note = note
            row.deleted = False
            row.hub_updated_at = str(rel.get("updated_at") or "") or row.hub_updated_at
        if not page.get("next"):
            as_of = page.get("as_of")
            break
        cursor = str(page["next"])
    if since is None and had:
        for ident, row in existing.items():
            if ident not in seen and not row.deleted:
                row.deleted = True
                counts["relations_removed"] += 1
    state.as_of = str(as_of) if as_of else state.as_of
    state.last_run_at = datetime.now(UTC)
    state.last_status = "ok"
    state.last_error = None
    if since is None:
        state.last_full_at = datetime.now(UTC)
    return dict(counts)


def due_full(db: Session) -> bool:
    """정기 전량 대조 때가 됐나 — 마지막 전량이 7일보다 오래됐으면."""
    last = db.scalar(
        select(CoreSyncRun.started_at)
        .where(CoreSyncRun.full.is_(True), CoreSyncRun.status.in_(("ok", "partial")))
        .order_by(CoreSyncRun.started_at.desc())
        .limit(1)
    )
    return last is None or datetime.now(UTC) - last > FULL_EVERY
