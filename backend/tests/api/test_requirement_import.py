"""요구 조건 표 반입 — **규격서를 보고 적은 표를 통째로 받는다.**

규격 464 중 3 에만 요구 조건이 있다. 상세 화면에서 한 줄씩 넣게 되어 있는데, 규격서를 펴
놓고 한 화면씩 오가며 넣는 일은 아무도 안 한다.

여기서 지키는 것:

1. 규격은 표기 차이를 무시하고 잡는다(「ISO6892-1」 = 「ISO 6892-1」). 조건은 이름으로.
2. 단위를 같이 적어도 되지만 **다른 단위면 거절한다** — N 을 kN 으로 들이면 천 배 틀린다.
3. `dry_run` 이 기본이고, 같은 규격·조건이 이미 있으면 「덮어쓴다」 고 미리 말한다.
4. 문제 없는 줄은 넣고 문제 있는 줄은 남긴다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _method(client: TestClient, admin: Signed, code: str) -> dict[str, Any]:
    made = client.post(
        "/api/methods",
        json={"code": code, "title": "Standard", "test_item_term_ids": []},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def test_표기가_달라도_규격을_잡고_단위는_조건의_것이어야_한다(
    client: TestClient, admin: Signed
) -> None:
    code = f"ISO {uuid.uuid4().hex[:5]}"
    method = _method(client, admin, code)
    squeezed = code.replace(" ", "")
    text = (
        "규격\t조건\t최소\t최대\t필수\t비고\n"
        f"{squeezed}\t하중 용량\t20 kN\t\t예\t7500-1 1급\n"
        f"{code}\t시험 온도\t10\t35 °C\t\t\n"
        f"{code}\t하중 용량\t20 N\t\t\t\n"
        f"{code}\t없는 조건\t1\t\t\t\n"
    )
    preview = client.post(
        "/api/methods/requirements/import", json={"text": text}, headers=admin.headers
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["dry_run"] is True
    rows = {row["line"]: row for row in body["rows"]}
    # 붙여 쓴 표기도 같은 규격이다.
    assert rows[2]["code"] == code and rows[2]["problems"] == []
    # 단위가 다르면 거절 — 「20 N」 을 kN 으로 들이면 천 배 틀린다.
    assert any("단위" in one for one in rows[4]["problems"])
    assert any("조건 정의에 없습니다" in one for one in rows[5]["problems"])
    assert body["summary"] == {
        "total": 4,
        "ready": 2,
        "problems": 2,
        "created": 0,
        "replaced": 0,
    }

    # 아직 아무것도 안 들어갔다.
    read = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert read["requirements"] == []

    put = client.post(
        "/api/methods/requirements/import?dry_run=false",
        json={"text": text},
        headers=admin.headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["summary"]["created"] == 2
    read = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    got = {
        one["condition_label"]: (one["min_value"], one["max_value"])
        for one in read["requirements"]
    }
    assert got == {"하중 용량": (20.0, None), "시험 온도": (10.0, 35.0)}


def test_이미_있는_조건은_덮어쓴다고_미리_말한다(client: TestClient, admin: Signed) -> None:
    code = f"ASTM E{uuid.uuid4().hex[:4]}"
    _method(client, admin, code)
    text = f"규격,조건,최소\n{code},하중 용량,10\n"
    first = client.post(
        "/api/methods/requirements/import?dry_run=false",
        json={"text": text},
        headers=admin.headers,
    )
    assert first.json()["summary"]["created"] == 1
    again = client.post(
        "/api/methods/requirements/import", json={"text": text}, headers=admin.headers
    )
    assert again.json()["rows"][0]["replaces"] is True


def test_같은_규격_조건이_두_줄이면_둘째_줄을_막는다(
    client: TestClient, admin: Signed
) -> None:
    code = f"KS B {uuid.uuid4().hex[:4]}"
    _method(client, admin, code)
    text = f"규격,조건,최소\n{code},하중 용량,10\n{code},하중 용량,20\n"
    body = client.post(
        "/api/methods/requirements/import", json={"text": text}, headers=admin.headers
    ).json()
    assert body["rows"][0]["problems"] == []
    assert any("2번째 줄" in one for one in body["rows"][1]["problems"])


def test_서식과_열을_내려준다(client: TestClient, admin: Signed) -> None:
    columns = client.get("/api/methods/requirements/import/columns", headers=admin.headers)
    assert columns.status_code == 200, columns.text
    assert [one["key"] for one in columns.json()][:3] == ["code", "edition", "condition"]
    template = client.get("/api/methods/requirements/import/template", headers=admin.headers)
    assert template.status_code == 200
    # 보기 줄은 실제 규격의 값이다.
    assert "ISO 6892-1" in template.text
