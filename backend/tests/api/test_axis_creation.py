"""**축을 새로 세운다** — 기준정보 축과 검색 조건 축.

오래 안 열어 두었던 문이다. 이유는 그대로 유효하다: 축은 코드가 slug 를 걸어야 뜻이 있고,
여기서 만든 축에는 그런 자리가 없다. 그래도 여는 이유는 **못 만들면 사람이 뜻이 다른 값을
남의 축에 넣기** 때문이다 — 제정기관 축에 회사 이름이 들어가는 일이 실제로 있었고, 그
갈림은 되돌릴 길이 없다.

여기서 지키는 것:

1. 시스템 관리자만 만든다 — 자격이 없으면 401.
2. 같은 slug 는 409 — 축이 둘로 갈리면 값도 둘로 갈리고 합칠 길이 없다.
3. 없는 축을 부모로 걸면 422 — 계층 화면이 빈 가지를 그린다.
4. 만든 축에 **값이 바로 들어간다**(축이 서랍 노릇은 한다).
5. 조건 축도 같은 규칙이고, 만든 뒤 **시험 항목에 걸면 검색 조건으로 뜬다.**
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def test_관리자가_축을_세우고_값을_넣는다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    slug = f"failure_mode_{tag}"
    made = client.post(
        "/api/vocabularies",
        json={
            "slug": slug,
            "label": f"불량 모드-{tag}",
            "domain": "common",
            "description": "제품이 어떻게 망가졌나",
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["slug"] == slug
    assert body["domain"] == "common"
    # **소속 이름은 서버가 준다** — 화면마다 사전을 두면 한 곳만 안 고쳐진다.
    assert body["domain_label"] == "공통"
    assert body["entry_policy"] == "open"
    assert body["term_count"] == 0

    # 목록에 선다.
    listed = client.get("/api/vocabularies", headers=admin.headers).json()
    assert slug in [one["slug"] for one in listed]

    # **값이 바로 들어간다** — 축이 서랍 노릇은 한다.
    term = client.post(
        f"/api/vocabularies/{slug}/terms",
        json={"value": f"납땜 크랙-{tag}"},
        headers=admin.headers,
    )
    assert term.status_code == 201, term.text
    again = client.get("/api/vocabularies", headers=admin.headers).json()
    mine = next(one for one in again if one["slug"] == slug)
    assert mine["term_count"] == 1


def test_같은_축은_두_번_안_생기고_없는_부모는_거절한다(
    client: TestClient, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    slug = f"product_line_{tag}"
    first = client.post(
        "/api/vocabularies",
        json={"slug": slug, "label": f"제품군-{tag}"},
        headers=admin.headers,
    )
    assert first.status_code == 201, first.text

    # **409 는 실패가 아니라 답이다** — 그 축을 쓰면 된다.
    again = client.post(
        "/api/vocabularies",
        json={"slug": slug, "label": "다른 이름이어도 같은 축"},
        headers=admin.headers,
    )
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "TSC-VOCAB-0012"

    # 없는 축을 부모로 걸면 계층 화면이 빈 가지를 그린다.
    orphan = client.post(
        "/api/vocabularies",
        json={
            "slug": f"child_{tag}",
            "label": "고아",
            "parent_slug": f"없는축_{tag}",
        },
        headers=admin.headers,
    )
    assert orphan.status_code == 422, orphan.text
    assert orphan.json()["error"]["code"] == "TSC-VOCAB-0013"


def test_조건_축을_세우면_시험_항목에_걸어_검색_조건이_된다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/condition-keys",
        json={
            "key": f"salt_spray_hours_{tag}",
            "label": f"염수분무 시간-{tag}",
            "kind": "range",
            "dimension": "time",
            "si_unit": "h",
            "display_unit": "h",
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    condition_id = made.json()["id"]

    # 축만 만들면 아무 일도 안 일어난다 — **시험 항목에 걸어야** 조건으로 뜬다.
    item = term_factory("test_item", f"염수분무-{tag}")
    linked = client.put(
        f"/api/test-items/{item}/condition-keys",
        json={"condition_key_ids": [condition_id]},
        headers=admin.headers,
    )
    assert linked.status_code == 204, linked.text

    got = client.get(f"/api/test-items/{item}", headers=admin.headers).json()
    mine = next(one for one in got["condition_keys"] if one["id"] == condition_id)
    assert mine["key"] == f"salt_spray_hours_{tag}"
    assert mine["unit"] == "h"


def test_자격_없이는_축을_못_만든다(client: TestClient) -> None:
    """**축은 전사 지식이다.** 시스템 관리자만 만든다 —
    라우터가 `require_system_admin` 을 건다."""
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/vocabularies",
        json={"slug": f"no_auth_{tag}", "label": "권한 없음"},
    )
    assert made.status_code == 401, made.text

    condition = client.post(
        "/api/condition-keys",
        json={"key": f"no_auth_{tag}", "label": "권한 없음"},
    )
    assert condition.status_code == 401, condition.text
