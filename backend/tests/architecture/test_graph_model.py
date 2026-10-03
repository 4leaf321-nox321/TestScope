"""지식 그래프의 정의 — **선이 가리키는 종류는 선언돼 있어야 한다.**

## 왜 이 시험이 있나

`run_by` 선이 처음부터 `division` 을 가리켰는데 **그 종류를 세운 적이 없었다**(2026-10-03).

그것이 왜 치명적인가: 구조 그림(`/graph` 의 「종류와 관계」)은 **종류 이름을 노드 id 로**
쓴다. 선언 없는 종류를 가리키는 선은 곧 **없는 노드를 가리키는 링크**이고, d3-force 는
그런 링크를 만나면 `node not found: division` 으로 **던진다.** 예외가 레이아웃 초기화에서
나므로 선 하나가 **그물 전체를 안 그리게** 만들었다 — 「그래프가 느리다 · 잘 안 보인다」 로
보고됐다.

눈으로는 안 잡힌다. 콘솔에만 한 줄 뜨고, 화면은 그냥 비거나 멎은 것처럼 보인다. 그리고
선을 더하는 사람은 종류 표를 안 보므로, 같은 실수가 다음 선에서 또 난다.

## 무엇을 못박나

**선의 양 끝 종류가 전부 `NODE_TYPES` 에 있다.** 그것 하나다. `term` 은 예외인데, 그것은
「어느 축인지 모르는 값」 을 뜻하는 특별한 꼴이라 구조 그림이 아예 뺀다(`routes.overview`).
"""

from __future__ import annotations

from app.modules.graph.model import EDGE_KINDS, NODE_TYPE_BY_SLUG, NODE_TYPES

#: 값으로 가는 선의 dst. 축을 모르니 구조 그림에서 **뺀다** — 노드로 세우지 않는다.
WILDCARD = "term"


def test_선이_가리키는_종류가_전부_선언돼_있다() -> None:
    missing: list[str] = []
    for kind in EDGE_KINDS:
        for side, slug in (("src", kind.src_type), ("dst", kind.dst_type)):
            if slug == WILDCARD:
                continue
            if slug not in NODE_TYPE_BY_SLUG:
                missing.append(f"{kind.slug}.{side} -> {slug}")
    assert missing == [], (
        "선언 안 된 종류를 가리키는 선입니다. 구조 그림이 종류 이름을 노드 id 로 쓰므로 "
        "d3-force 가 `node not found` 로 던지고 그물 전체가 안 그려집니다"
    )


def test_종류_이름과_차례가_겹치지_않는다() -> None:
    """같은 slug 가 둘이면 뒤의 것이 앞의 것을 덮고, 그 덮음은 화면에 안 보인다."""
    slugs = [one.slug for one in NODE_TYPES]
    assert len(slugs) == len(set(slugs)), "종류 이름이 겹칩니다"
    orders = [one.sort_order for one in NODE_TYPES]
    assert len(orders) == len(set(orders)), "차례가 겹칩니다 — 그리는 순서가 매번 달라집니다"


def test_층은_셋_중_하나다() -> None:
    """색 묶음과 설명이 층으로 갈린다. 새 층을 조용히 더하면 그 종류가 색 없이 그려진다."""
    for one in NODE_TYPES:
        assert one.layer in ("catalog", "vocabulary", "operations"), one.slug
