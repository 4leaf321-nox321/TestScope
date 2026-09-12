"""장비 분류 트리 — **묶음 분류를 고르면 그 아래 유형이 다 걸린다.**

분류 축은 21군 / 105유형의 두 층 트리다(「정적 기계 시험기」 아래 만능시험기·경도계·…).
계열은 **유형**을 가리키므로 군 자체를 가리키는 계열은 없다 — 2026-09-12 실측에서 계열
없는 분류 22종 중 16종이 군이었다. 그것은 공백이 아니라 트리의 윗층이다.

그런데 거르기는 「목록에 실제로 있는 값만」 내려보내니 군은 어디에도 안 나오고, 나온다
해도 같음 비교라 0 건이다. 사람은 「기계 시험기 전부」 를 보고 싶어 하는데 유형 여덟을
하나씩 골라야 한다. 그래서 둘을 한다:

- 고른 분류의 **가족**(자기 + 후손)으로 거른다 — `family`.
- 거르기 선택지에 군을 **아래 수를 합쳐** 올린다 — `rollup`. 군은 「묶음」 이라고 적어
  유형과 구별하고, 유형은 어느 군인지 적는다.

고리를 믿지 않는다. 트리가 고리를 이루면 걷다가 멈춘다 — 데이터가 그럴 리 없다고
믿으면 그날 요청이 영원히 돈다.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment.schemas import FilterOption
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm

CATEGORY_AXIS = "equipment_category"


@dataclass(frozen=True)
class _Node:
    id: uuid.UUID
    label: str
    parent: uuid.UUID | None


def _nodes(db: Session) -> dict[uuid.UUID, _Node]:
    axis_id = db.scalar(select(Vocabulary.id).where(Vocabulary.slug == CATEGORY_AXIS))
    if axis_id is None:
        return {}
    rows = db.execute(
        select(VocabularyTerm.id, VocabularyTerm.value, VocabularyTerm.parent_term_id).where(
            VocabularyTerm.vocabulary_id == axis_id
        )
    ).all()
    return {row[0]: _Node(row[0], row[1], row[2]) for row in rows}


def family(db: Session, term_id: uuid.UUID) -> list[uuid.UUID]:
    """자기와 후손 전부. 트리에 없는 id 면 자기만 — 모르는 것을 넓히지 않는다."""
    nodes = _nodes(db)
    children: dict[uuid.UUID | None, list[uuid.UUID]] = defaultdict(list)
    for node in nodes.values():
        children[node.parent].append(node.id)
    out: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    queue = [term_id]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        out.append(current)
        queue.extend(children.get(current, []))
    return out


def rollup(db: Session, counts: dict[uuid.UUID, int]) -> list[FilterOption]:
    """유형별 수를 받아 **군을 합쳐** 선택지로. 유형은 어느 군인지, 군은 몇을 묶는지 적는다.

    순서: 군은 합친 수가 큰 것부터, 그 아래 유형은 수가 큰 것부터. 군 없는 유형(트리
    밖 손 입력)은 맨 뒤에 그대로.
    """
    nodes = _nodes(db)
    total: dict[uuid.UUID, int] = dict(counts)
    members: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for term_id, count in counts.items():
        node = nodes.get(term_id)
        seen: set[uuid.UUID] = set()
        while node is not None and node.parent is not None and node.parent not in seen:
            seen.add(node.parent)
            total[node.parent] = total.get(node.parent, 0) + count
            members[node.parent].add(term_id)
            node = nodes.get(node.parent)

    def root_of(term_id: uuid.UUID) -> uuid.UUID:
        node = nodes.get(term_id)
        seen: set[uuid.UUID] = set()
        while node is not None and node.parent is not None and node.parent not in seen:
            seen.add(node.parent)
            node = nodes.get(node.parent)
        return node.id if node else term_id

    def option(term_id: uuid.UUID) -> FilterOption:
        node = nodes.get(term_id)
        label = node.label if node else "—"
        if term_id in members:
            detail = f"묶음 · {len(members[term_id])}개 분류"
        elif node and node.parent is not None and node.parent in nodes:
            detail = nodes[node.parent].label
        else:
            detail = None
        return FilterOption(
            value=str(term_id), label=label, count=total[term_id], detail=detail
        )

    def order(term_id: uuid.UUID) -> tuple[int, str, int, int, str]:
        root = root_of(term_id)
        node = nodes.get(term_id)
        return (
            -total.get(root, 0),
            nodes[root].label if root in nodes else "",
            0 if term_id in members else 1,
            -total[term_id],
            node.label if node else "",
        )

    return [option(term_id) for term_id in sorted(total, key=order)]
