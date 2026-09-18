"""그래프 응답 — **화면이 그리는 데 필요한 것만.** 나머지는 노드를 눌렀을 때 상세가 준다."""

from __future__ import annotations

from pydantic import BaseModel

# --- 구조 그림 ------------------------------------------------------------------


class TypeNodeOut(BaseModel):
    slug: str
    label: str
    icon: str
    layer: str
    count: int
    """보이는 객체 수. 남의 부서 장비는 안 센다."""
    detail_path: str | None
    """목록 화면 주소 서식(`{id}` 없이 쓰면 목록). None 이면 화면이 없다."""


class TypeEdgeOut(BaseModel):
    relation: str
    label: str
    inverse_label: str
    directed: bool
    src_type: str
    dst_type: str
    count: int
    """실제로 걸린 관계 수. 0 이면 **정의만 있고 아직 아무것도 안 이어진** 것."""


class OverviewOut(BaseModel):
    nodes: list[TypeNodeOut]
    edges: list[TypeEdgeOut]
    object_count: int
    edge_count: int


# --- 탐색 그림 ------------------------------------------------------------------


class NodeOut(BaseModel):
    id: str
    """`<종류>:<uuid>`."""
    label: str
    key: str | None
    sublabel: str | None
    type_slug: str
    type_label: str
    status: str
    owner_workspace_slug: str | None
    degree: int
    """이 노드에 걸린 **보이는** 관계의 수 — 잘렸으면 화면의 수보다 크다."""
    truncated: bool
    """화면에 실린 것보다 관계가 더 있다. 「+N 더」 의 근거."""
    detail_path: str | None


class EdgeOut(BaseModel):
    id: str
    relation: str
    label: str
    inverse_label: str
    directed: bool
    src: str
    dst: str


class NeighborhoodOut(BaseModel):
    focus: str
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    depth: int
    fanout: int
    node_limit: int
    truncated: bool


class SubgraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    total: int
    limit: int
    offset: int
    truncated: bool


class SearchHitOut(BaseModel):
    id: str
    label: str
    key: str | None
    sublabel: str | None
    type_slug: str
    type_label: str


class BrowseOut(BaseModel):
    items: list[SearchHitOut]
    total: int
    limit: int
    offset: int


# --- 고른 노드 -------------------------------------------------------------------


class FactOut(BaseModel):
    label: str
    value: str


class RelatedOut(BaseModel):
    relation: str
    label: str
    """방향에 맞는 말 — 나가는 선이면 label, 들어오는 선이면 inverse_label."""
    outgoing: bool
    node_id: str
    node_label: str
    node_type_label: str


class NodeDetailOut(BaseModel):
    id: str
    label: str
    key: str | None
    type_slug: str
    type_label: str
    status: str
    detail_path: str | None
    facts: list[FactOut]
    related: list[RelatedOut]
    related_total: int
    """걸린 관계 전체 수. `related` 는 상한 안에서만."""
