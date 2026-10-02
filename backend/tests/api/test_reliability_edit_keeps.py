"""칸 하나를 고칠 때 **잃지 말아야 하는 둘** — 원문 근거와 고친 때.

운영에서 두 건이 함께 올라왔다(2026-10-03):

1. `set_reliability_attributes` 가 **보내지 않은 칸의 원문 근거를 지운다**
   (`source_text` · `original_value` · `original_unit`).
2. **고쳐도 `updated_at` 이 갱신되지 않는다.**

둘 다 같은 구조에서 나온다. `PATCH` 의 `attributes` 는 보낸 것으로 **통째로 갈아 끼우고**
(그 판의 값을 지우고 다시 넣는다), 값은 시험 행이 아니라 **딴 표**에 있다.

1 은 MCP 쪽 `merge.as_input` 이 되돌려 보낼 칸 목록에서 원문 근거 셋을 빼먹어서 났다 —
한 칸을 고치면 **안 건드린 줄 전부**의 근거가 날아갔다. 그 판단은 `test_mcp_merge.py` 가
지킨다. 여기서는 **서버가 그 셋을 받아 되돌려 주는지**를 본다: 받지 않으면 MCP 가 아무리
실어 보내도 소용이 없다.

2 는 `updated_at` 이 `onupdate=func.now()` 인데 그것이 **이 행이 UPDATE 될 때만** 돈다는
것이다. 속성만 바꾸면 행이 안 더러워져 UPDATE 가 아예 안 나가고, 날짜는 그대로다 —
목록을 「최근 고친 것」 으로 보는 사람은 방금 고친 줄을 못 찾는다.

**되찾을 수 없는 것부터 지킨다.** `note` 는 옮긴 사람의 해석이라 다시 쓸 수 있지만 원문은
문서를 다시 열어야 나온다. `70 degC` 만 남으면 그것이 문서의 값인지 158 °F 를 옮긴 값인지
알 길이 없다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed

#: 문서에서 옮긴 값의 **증거** 셋.
PROVENANCE = {
    "source_text": "Operating temperature: -40 to 257 degF",
    "original_value": "-40 to 257",
    "original_unit": "degF",
}


def _conditions(client: TestClient, admin: Signed) -> dict[str, Any]:
    rows = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=admin.headers,
    ).json()
    return {one["label"]: one for one in rows if one["kind"] == "condition"}


def _made(client: TestClient, admin: Signed) -> tuple[dict[str, Any], dict[str, Any]]:
    """원문 근거를 붙인 시험 하나. 조건 둘 — 하나를 고치고 **다른 하나**를 본다."""
    axes = _conditions(client, admin)
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "mx",
            "name": f"원문 보존-{uuid.uuid4().hex[:6]}",
            "attributes": [
                {
                    "definition_id": axes["시험 온도"]["id"],
                    "num_min": -40,
                    "num_max": 125,
                    **PROVENANCE,
                },
                {"definition_id": axes["상대 습도"]["id"], "num_min": 85},
            ],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return made.json(), axes


def test_원문_근거를_넣고_되받는다(client: TestClient, admin: Signed) -> None:
    """**서버가 받아 돌려주지 않으면** MCP 가 실어 보내도 소용이 없다."""
    row, _ = _made(client, admin)
    temp = next(one for one in row["attributes"] if one["label"] == "시험 온도")
    for key, value in PROVENANCE.items():
        assert temp[key] == value, f"{key} 가 안 돌아왔다"


def test_다른_칸을_고쳐도_원문_근거가_남는다(client: TestClient, admin: Signed) -> None:
    """운영 보고 1. **안 건드린 줄**의 근거가 사라지는 것이 그 고장이었다."""
    row, axes = _made(client, admin)
    temp = next(one for one in row["attributes"] if one["label"] == "시험 온도")

    # MCP 가 하는 것과 같은 모양 — 지금 있는 줄을 되돌려 보내면서 한 줄만 고친다.
    patched = client.patch(
        f"/api/reliability-tests/{row['id']}",
        json={
            "attributes": [
                {
                    "definition_id": temp["definition_id"],
                    "num_min": temp["num_min"],
                    "num_max": temp["num_max"],
                    **PROVENANCE,
                },
                {"definition_id": axes["상대 습도"]["id"], "num_min": 90},
            ]
        },
        headers=admin.headers,
    )
    assert patched.status_code == 200, patched.text
    after = next(one for one in patched.json()["attributes"] if one["label"] == "시험 온도")
    for key, value in PROVENANCE.items():
        assert after[key] == value, f"다른 칸을 고쳤는데 {key} 가 사라졌다"


def test_속성만_고쳐도_고친_때가_남는다(client: TestClient, admin: Signed) -> None:
    """운영 보고 2.

    값은 딴 표에 있어 시험 행이 안 더러워지고, 그러면 `onupdate` 이 아예 안 돈다. 목록을
    「최근 고친 것」 으로 보는 사람이 방금 고친 줄을 못 찾는다.
    """
    row, axes = _made(client, admin)
    before = row["updated_at"]

    patched = client.patch(
        f"/api/reliability-tests/{row['id']}",
        json={"attributes": [{"definition_id": axes["상대 습도"]["id"], "num_min": 90}]},
        headers=admin.headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["updated_at"] > before, "속성만 고쳤더니 고친 때가 그대로다"


def test_시험_항목만_고쳐도_고친_때가_남는다(client: TestClient, admin: Signed) -> None:
    """시험 항목도 딴 표다 — 같은 구멍이라 같이 막는다."""
    row, _ = _made(client, admin)
    before = row["updated_at"]
    # 시험 DB 의 시험 항목 축은 비어 있다 — 쓸 것을 만들어 쓴다(닫힌 축이라 관리자다).
    made = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"고온고습-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    patched = client.patch(
        f"/api/reliability-tests/{row['id']}",
        json={"test_item_term_ids": [made.json()["id"]]},
        headers=admin.headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["updated_at"] > before, "시험 항목을 고쳤더니 고친 때가 그대로다"
