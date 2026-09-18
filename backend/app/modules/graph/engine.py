"""그래프 엔진 — 정의(`model.py`)를 읽어 **이웃 · 유도 선 · 차수 · 이름 · 찾기**를 낸다.

큰 데이터를 통째로 안 준다(StandardPlatform 과 같은 규칙): 이웃은 한 단계씩, 노드마다 fanout
개까지, 전체 node_limit 개까지. 잘리면 잘렸다고 말한다 — 노드의 `degree`(보이는 관계 수)가
화면에 실린 수보다 크면 화면이 「+N」 을 붙인다.

노드 id 는 `"<종류>:<uuid>"`. 선 하나는 (종류 slug, src id, dst id, 행 uuid).

## 보이는 것만

보유 장비는 부서가 가린 것을 남이 못 본다(`visible_equipment_ids`) — 장비가 끝에 오는 선은 그
안에서만 긋고, 차수도 그 안에서만 센다. 지운 것(deleted_at)은 이름 찾기에서 빠지고, 이름 없는
끝을 가진 선은 버린다 — 지운 규격으로 가는 선이 그림에 남지 않게.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment, EquipmentModel, EquipmentSeries
from app.modules.graph.model import (
    EDGE_KINDS,
    NODE_TYPE_BY_SLUG,
    NODE_TYPES,
    TERM_TYPE_BY_AXIS,
    EdgeKind,
    node_id,
)
from app.modules.methods.models import TestMethod
from app.modules.reliability.models import ReliabilityTest
from app.modules.vocabulary.models import (
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.workspaces.models import Workspace
from app.shared.permissions import visible_equipment_ids


@dataclass(frozen=True)
class Edge:
    id: str
    """`<kind slug>:<row uuid>` — 같은 행이 두 응답에 실려도 하나."""
    kind: str
    src: str
    dst: str


@dataclass
class NodeInfo:
    id: str
    type_slug: str
    label: str
    key: str | None
    status: str
    sublabel: str | None = None
    workspace_slug: str | None = None


# ------------------------------------------------------------------ 축·종류


def _axis_ids(db: Session) -> dict[str, uuid.UUID]:
    return {slug: vid for vid, slug in db.execute(select(Vocabulary.id, Vocabulary.slug))}


def term_type_of(db: Session, term_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """값의 축 → 노드 종류. 속성이 가리키는 값(term)은 축을 모르고 오므로 여기서 정한다."""
    if not term_ids:
        return {}
    axes = {vid: slug for slug, vid in _axis_ids(db).items()}
    out: dict[uuid.UUID, str] = {}
    for tid, vid in db.execute(
        select(VocabularyTerm.id, VocabularyTerm.vocabulary_id).where(
            VocabularyTerm.id.in_(term_ids)
        )
    ):
        axis = axes.get(vid)
        if axis and axis in TERM_TYPE_BY_AXIS:
            out[tid] = TERM_TYPE_BY_AXIS[axis]
    return out


def _equipment_scope(db: Session, user: User) -> Select[tuple[uuid.UUID]]:
    return visible_equipment_ids(db, user)


def _scoped(kind: EdgeKind, stmt: Select[Any], db: Session, user: User) -> Select[Any]:
    """장비가 끝에 오는 선은 보이는 장비 안에서만."""
    scope = _equipment_scope(db, user)
    if kind.src_type == "equipment":
        stmt = stmt.where(kind.src_col.in_(scope))
    if kind.dst_type == "equipment":
        stmt = stmt.where(kind.dst_col.in_(scope))
    return stmt


# ------------------------------------------------------------------ 이름


def lookup(db: Session, user: User, wanted: dict[str, set[uuid.UUID]]) -> dict[str, NodeInfo]:
    """종류별 uuid 집합 → 노드 정보. 지운 것·안 보이는 것은 **빠진다**(없는 것과 같은 답)."""
    out: dict[str, NodeInfo] = {}
    axes = _axis_ids(db)
    workspaces = {w.id: w for w in db.scalars(select(Workspace))}
    for type_slug, ids in wanted.items():
        if not ids:
            continue
        node_type = NODE_TYPE_BY_SLUG.get(type_slug)
        if node_type is None:
            continue
        id_list = list(ids)
        if node_type.axis:
            axis_id = axes.get(node_type.axis)
            if axis_id is None:
                continue
            for term in db.scalars(
                select(VocabularyTerm).where(
                    VocabularyTerm.id.in_(id_list), VocabularyTerm.vocabulary_id == axis_id
                )
            ):
                out[node_id(type_slug, term.id)] = NodeInfo(
                    node_id(type_slug, term.id), type_slug, term.value, term.code, term.status
                )
        elif type_slug == "condition_key":
            for key in db.scalars(select(ConditionKey).where(ConditionKey.id.in_(id_list))):
                out[node_id(type_slug, key.id)] = NodeInfo(
                    node_id(type_slug, key.id),
                    type_slug,
                    key.label,
                    key.key,
                    "active" if key.is_active else "inactive",
                    key.display_unit or key.si_unit or None,
                )
        elif type_slug == "method":
            for m in db.scalars(
                select(TestMethod).where(
                    TestMethod.id.in_(id_list), TestMethod.deleted_at.is_(None)
                )
            ):
                out[node_id(type_slug, m.id)] = NodeInfo(
                    node_id(type_slug, m.id),
                    type_slug,
                    m.code + (f" ({m.edition})" if m.edition else ""),
                    None,
                    m.status,
                    m.title if m.title != m.code else None,
                )
        elif type_slug == "series":
            makers = (
                {
                    t.id: t.value
                    for t in db.scalars(
                        select(VocabularyTerm).where(
                            VocabularyTerm.vocabulary_id == axes.get("manufacturer")
                        )
                    )
                }
                if "manufacturer" in axes
                else {}
            )
            for s in db.scalars(
                select(EquipmentSeries).where(
                    EquipmentSeries.id.in_(id_list), EquipmentSeries.deleted_at.is_(None)
                )
            ):
                out[node_id(type_slug, s.id)] = NodeInfo(
                    node_id(type_slug, s.id),
                    type_slug,
                    s.name,
                    None,
                    s.status,
                    makers.get(s.maker_term_id) if s.maker_term_id else None,
                )
        elif type_slug == "model":
            for model in db.scalars(
                select(EquipmentModel).where(
                    EquipmentModel.id.in_(id_list), EquipmentModel.deleted_at.is_(None)
                )
            ):
                out[node_id(type_slug, model.id)] = NodeInfo(
                    node_id(type_slug, model.id), type_slug, model.name, None, "active"
                )
        elif type_slug == "equipment":
            for e in db.scalars(
                select(Equipment).where(
                    Equipment.id.in_(id_list),
                    Equipment.deleted_at.is_(None),
                    Equipment.id.in_(_equipment_scope(db, user)),
                )
            ):
                ws = workspaces.get(e.owner_workspace_id) if e.owner_workspace_id else None
                out[node_id(type_slug, e.id)] = NodeInfo(
                    node_id(type_slug, e.id),
                    type_slug,
                    e.name,
                    e.asset_no,
                    e.status,
                    ws.name if ws else None,
                    ws.slug if ws else None,
                )
        elif type_slug == "reliability_test":
            for r in db.scalars(
                select(ReliabilityTest).where(
                    ReliabilityTest.id.in_(id_list), ReliabilityTest.deleted_at.is_(None)
                )
            ):
                ws = workspaces.get(r.workspace_id)
                out[node_id(type_slug, r.id)] = NodeInfo(
                    node_id(type_slug, r.id),
                    type_slug,
                    r.name,
                    None,
                    "active",
                    ws.name if ws else None,
                    ws.slug if ws else None,
                )
        elif type_slug == "workspace":
            for wid in id_list:
                w = workspaces.get(wid)
                if w is None:
                    continue
                out[node_id(type_slug, w.id)] = NodeInfo(
                    node_id(type_slug, w.id),
                    type_slug,
                    w.name,
                    w.slug,
                    "active" if w.is_active else "archived",
                    None,
                    w.slug,
                )
    return out


# ------------------------------------------------------------------ 선


def _edges_from_rows(
    db: Session, kind: EdgeKind, rows: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]
) -> list[Edge]:
    """행 → Edge. dst 가 「값(term)」 이면 축으로 종류를 정한다."""
    if not rows:
        return []
    if kind.dst_type == "term":
        types = term_type_of(db, [dst for _, dst, _ in rows])
        return [
            Edge(
                f"{kind.slug}:{rid}",
                kind.slug,
                node_id(kind.src_type, src),
                node_id(types[dst], dst),
            )
            for src, dst, rid in rows
            if dst in types
        ]
    return [
        Edge(
            f"{kind.slug}:{rid}",
            kind.slug,
            node_id(kind.src_type, src),
            node_id(kind.dst_type, dst),
        )
        for src, dst, rid in rows
    ]


def neighbor_edges(
    db: Session,
    user: User,
    frontier: dict[str, set[uuid.UUID]],
    *,
    fanout: int,
    relations: set[str] | None,
    types: set[str] | None,
) -> list[Edge]:
    """frontier(종류별 uuid)에 닿는 선. 노드 하나가 데려오는 이웃은 fanout 개까지."""
    out: list[Edge] = []
    present = _ids_of(frontier)
    per_node: dict[str, int] = defaultdict(int)
    for kind in EDGE_KINDS:
        if relations and kind.slug not in relations:
            continue
        src_ids = frontier.get(kind.src_type, set())
        dst_ids = (
            _term_side(frontier)
            if kind.dst_type == "term"
            else frontier.get(kind.dst_type, set())
        )
        if not src_ids and not dst_ids:
            continue
        conditions = []
        if src_ids:
            conditions.append(kind.src_col.in_(list(src_ids)))
        if dst_ids:
            conditions.append(kind.dst_col.in_(list(dst_ids)))
        stmt = _scoped(kind, kind.stmt.where(or_(*conditions)), db, user)
        rows = [tuple(r) for r in db.execute(stmt).all()]
        for edge in _edges_from_rows(db, kind, rows):
            anchor, other = (
                (edge.src, edge.dst) if edge.src in present else (edge.dst, edge.src)
            )
            # 이웃 종류 거르기 — 반대쪽 끝이 고른 종류여야 한다(이미 실린 노드끼리는 그대로).
            if types and other not in present and other.split(":", 1)[0] not in types:
                continue
            if per_node[anchor] >= fanout:
                continue
            per_node[anchor] += 1
            out.append(edge)
    return out


def _ids_of(frontier: dict[str, set[uuid.UUID]]) -> set[str]:
    return {node_id(t, i) for t, ids in frontier.items() for i in ids}


def _term_side(ids: dict[str, set[uuid.UUID]]) -> set[uuid.UUID]:
    """값(term) 쪽 끝의 후보 — 축을 가진 종류의 uuid 전부."""
    out: set[uuid.UUID] = set()
    for slug, wanted in ids.items():
        if NODE_TYPE_BY_SLUG[slug].axis:
            out |= wanted
    return out


def induced_edges(
    db: Session,
    user: User,
    ids: dict[str, set[uuid.UUID]],
    *,
    relations: set[str] | None,
    limit: int,
) -> list[Edge]:
    """양 끝이 모두 `ids` 안에 있는 선 — fanout 에 밀린 관계도 양 끝이 화면에 있으면 긋는다."""
    out: list[Edge] = []
    present = _ids_of(ids)
    for kind in EDGE_KINDS:
        if relations and kind.slug not in relations:
            continue
        src_ids = ids.get(kind.src_type, set())
        dst_ids = _term_side(ids) if kind.dst_type == "term" else ids.get(kind.dst_type, set())
        if not src_ids or not dst_ids:
            continue
        stmt = _scoped(
            kind,
            kind.stmt.where(kind.src_col.in_(list(src_ids)), kind.dst_col.in_(list(dst_ids))),
            db,
            user,
        ).limit(limit)
        rows = [tuple(r) for r in db.execute(stmt).all()]
        out.extend(
            e
            for e in _edges_from_rows(db, kind, rows)
            if e.src in present and e.dst in present
        )
        if len(out) >= limit:
            return out[:limit]
    return out


def degrees(db: Session, user: User, ids: dict[str, set[uuid.UUID]]) -> dict[str, int]:
    """노드마다 **보이는** 관계의 수 — 「+N」 의 근거. 선 종류마다 양 끝에서 한 번씩 센다."""
    out: dict[str, int] = defaultdict(int)
    for kind in EDGE_KINDS:
        for col, type_slug, side in (
            (kind.src_col, kind.src_type, 0),
            (kind.dst_col, kind.dst_type, 1),
        ):
            wanted = _term_side(ids) if type_slug == "term" else ids.get(type_slug, set())
            if not wanted:
                continue
            stmt = _scoped(kind, kind.stmt.where(col.in_(list(wanted))), db, user)
            rows = [tuple(r) for r in db.execute(stmt).all()]
            if type_slug == "term":
                types = term_type_of(db, [r[1] for r in rows])
                for _src, dst, _rid in rows:
                    if dst in types:
                        out[node_id(types[dst], dst)] += 1
                continue
            for row in rows:
                out[node_id(type_slug, row[side])] += 1
    return dict(out)


# ------------------------------------------------------------------ 구조·찾기·훑기


def type_counts(db: Session, user: User) -> dict[str, int]:
    axes = _axis_ids(db)
    out: dict[str, int] = {}
    for node_type in NODE_TYPES:
        if node_type.axis:
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(VocabularyTerm)
                    .where(
                        VocabularyTerm.vocabulary_id == axes.get(node_type.axis),
                        VocabularyTerm.status == "active",
                    )
                )
                or 0
            )
        elif node_type.slug == "condition_key":
            out[node_type.slug] = int(
                db.scalar(select(func.count()).select_from(ConditionKey)) or 0
            )
        elif node_type.slug == "method":
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(TestMethod)
                    .where(TestMethod.deleted_at.is_(None))
                )
                or 0
            )
        elif node_type.slug == "series":
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(EquipmentSeries)
                    .where(EquipmentSeries.deleted_at.is_(None))
                )
                or 0
            )
        elif node_type.slug == "model":
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(EquipmentModel)
                    .where(EquipmentModel.deleted_at.is_(None))
                )
                or 0
            )
        elif node_type.slug == "equipment":
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(Equipment)
                    .where(
                        Equipment.deleted_at.is_(None),
                        Equipment.id.in_(_equipment_scope(db, user)),
                    )
                )
                or 0
            )
        elif node_type.slug == "reliability_test":
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(ReliabilityTest)
                    .where(ReliabilityTest.deleted_at.is_(None))
                )
                or 0
            )
        elif node_type.slug == "workspace":
            out[node_type.slug] = int(
                db.scalar(
                    select(func.count())
                    .select_from(Workspace)
                    .where(Workspace.is_active.is_(True))
                )
                or 0
            )
    return out


def edge_counts(db: Session, user: User) -> dict[str, int]:
    """선 종류마다 실제로 걸린 수. 값(term)으로 가는 속성 선은 축을 못 가르므로 한 수로."""
    out: dict[str, int] = {}
    for kind in EDGE_KINDS:
        stmt = _scoped(kind, kind.stmt, db, user)
        out[kind.slug] = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    return out


def search(db: Session, user: User, q: str, limit: int) -> list[NodeInfo]:
    """종류를 가리지 않고 시작점을 찾는다 — 이름·코드·별칭·자산번호."""
    needle = f"%{q.strip()}%"
    axes = _axis_ids(db)
    axis_types = {
        vid: TERM_TYPE_BY_AXIS[slug] for slug, vid in axes.items() if slug in TERM_TYPE_BY_AXIS
    }
    found: dict[str, set[uuid.UUID]] = defaultdict(set)
    alias_hits = select(VocabularyAlias.term_id).where(VocabularyAlias.value.ilike(needle))
    for term in db.scalars(
        select(VocabularyTerm)
        .where(
            VocabularyTerm.vocabulary_id.in_(list(axis_types)),
            VocabularyTerm.status == "active",
            or_(
                VocabularyTerm.value.ilike(needle),
                VocabularyTerm.code.ilike(needle),
                VocabularyTerm.id.in_(alias_hits),
            ),
        )
        .order_by(VocabularyTerm.value)
        .limit(limit)
    ):
        found[axis_types[term.vocabulary_id]].add(term.id)
    for cid in db.scalars(
        select(ConditionKey.id)
        .where(or_(ConditionKey.label.ilike(needle), ConditionKey.key.ilike(needle)))
        .limit(limit)
    ):
        found["condition_key"].add(cid)
    for mid in db.scalars(
        select(TestMethod.id)
        .where(
            TestMethod.deleted_at.is_(None),
            or_(TestMethod.code.ilike(needle), TestMethod.title.ilike(needle)),
        )
        .order_by(TestMethod.code)
        .limit(limit)
    ):
        found["method"].add(mid)
    for sid in db.scalars(
        select(EquipmentSeries.id)
        .where(EquipmentSeries.deleted_at.is_(None), EquipmentSeries.name.ilike(needle))
        .order_by(EquipmentSeries.name)
        .limit(limit)
    ):
        found["series"].add(sid)
    for mid in db.scalars(
        select(EquipmentModel.id)
        .where(EquipmentModel.deleted_at.is_(None), EquipmentModel.name.ilike(needle))
        .order_by(EquipmentModel.name)
        .limit(limit)
    ):
        found["model"].add(mid)
    for eid in db.scalars(
        select(Equipment.id)
        .where(
            Equipment.deleted_at.is_(None),
            Equipment.id.in_(_equipment_scope(db, user)),
            or_(Equipment.name.ilike(needle), Equipment.asset_no.ilike(needle)),
        )
        .order_by(Equipment.name)
        .limit(limit)
    ):
        found["equipment"].add(eid)
    for rid in db.scalars(
        select(ReliabilityTest.id)
        .where(ReliabilityTest.deleted_at.is_(None), ReliabilityTest.name.ilike(needle))
        .limit(limit)
    ):
        found["reliability_test"].add(rid)
    for wid in db.scalars(
        select(Workspace.id)
        .where(
            Workspace.is_active.is_(True),
            or_(Workspace.name.ilike(needle), Workspace.slug.ilike(needle)),
        )
        .limit(limit)
    ):
        found["workspace"].add(wid)
    infos = lookup(db, user, found)
    return sorted(infos.values(), key=lambda one: (one.label.lower(), one.type_slug))[:limit]


def browse(
    db: Session, user: User, type_slug: str, *, q: str | None, limit: int, offset: int
) -> tuple[list[NodeInfo], int]:
    """한 종류의 노드를 이름순으로 쪽 단위로 — 「무엇이 있는지 모를 때 훑는 길」."""
    node_type = NODE_TYPE_BY_SLUG[type_slug]
    needle = f"%{q.strip()}%" if q and q.strip() else None
    stmt: Select[Any]
    if node_type.axis:
        axis_id = _axis_ids(db).get(node_type.axis)
        stmt = select(VocabularyTerm.id).where(
            VocabularyTerm.vocabulary_id == axis_id, VocabularyTerm.status == "active"
        )
        if needle:
            stmt = stmt.where(VocabularyTerm.value.ilike(needle))
        stmt = stmt.order_by(VocabularyTerm.value)
    elif type_slug == "condition_key":
        stmt = select(ConditionKey.id).order_by(ConditionKey.sort_order, ConditionKey.label)
        if needle:
            stmt = stmt.where(ConditionKey.label.ilike(needle))
    elif type_slug == "method":
        stmt = (
            select(TestMethod.id)
            .where(TestMethod.deleted_at.is_(None))
            .order_by(TestMethod.code)
        )
        if needle:
            stmt = stmt.where(
                or_(TestMethod.code.ilike(needle), TestMethod.title.ilike(needle))
            )
    elif type_slug == "series":
        stmt = (
            select(EquipmentSeries.id)
            .where(EquipmentSeries.deleted_at.is_(None))
            .order_by(EquipmentSeries.name)
        )
        if needle:
            stmt = stmt.where(EquipmentSeries.name.ilike(needle))
    elif type_slug == "model":
        stmt = (
            select(EquipmentModel.id)
            .where(EquipmentModel.deleted_at.is_(None))
            .order_by(EquipmentModel.name)
        )
        if needle:
            stmt = stmt.where(EquipmentModel.name.ilike(needle))
    elif type_slug == "equipment":
        stmt = (
            select(Equipment.id)
            .where(
                Equipment.deleted_at.is_(None), Equipment.id.in_(_equipment_scope(db, user))
            )
            .order_by(Equipment.name)
        )
        if needle:
            stmt = stmt.where(
                or_(Equipment.name.ilike(needle), Equipment.asset_no.ilike(needle))
            )
    elif type_slug == "reliability_test":
        stmt = (
            select(ReliabilityTest.id)
            .where(ReliabilityTest.deleted_at.is_(None))
            .order_by(ReliabilityTest.name)
        )
        if needle:
            stmt = stmt.where(ReliabilityTest.name.ilike(needle))
    else:
        stmt = (
            select(Workspace.id)
            .where(Workspace.is_active.is_(True))
            .order_by(Workspace.sort_order, Workspace.name)
        )
        if needle:
            stmt = stmt.where(Workspace.name.ilike(needle))
    total = int(
        db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    )
    ids = list(db.scalars(stmt.offset(offset).limit(limit)))
    infos = lookup(db, user, {type_slug: set(ids)})
    ordered = [
        infos[node_id(type_slug, one)] for one in ids if node_id(type_slug, one) in infos
    ]
    return ordered, total


def all_edges_of(
    db: Session, user: User, type_slug: str, row_id: uuid.UUID, limit: int
) -> list[Edge]:
    """노드 하나에 걸린 선 전부(상한 안에서) — 고른 노드의 관계 목록."""
    return neighbor_edges(
        db, user, {type_slug: {row_id}}, fanout=limit, relations=None, types=None
    )[:limit]
