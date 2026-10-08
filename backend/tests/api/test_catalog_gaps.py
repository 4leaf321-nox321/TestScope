"""카탈로그 보강 목록 — **미연결 장비를 왜 미연결인지로 가른다.**

운영에서 미연결 장비가 분류마다 남았는데(2026-10-08, 사용자 보고) 이유가 넷이었다: 모델명이
없어 대조 불가 · 카탈로그에 기종이 없음 · 비슷하지만 다른 기종 · 계열은 있지만 기종이 없음.
이유마다 할 일이 다르므로 서버가 가르고, 고치는 길은 기종 등록 요청의 흐름을 탄다.

여기서 지키는 것:

1. 다섯 경우가 실제로 갈린다(같은 기종 · 비슷한 기종 · 계열만 · 카탈로그에 없음 · 모델명 없음).
2. 「요청으로 올리기」 는 기종 등록 요청을 만든다 — 모델명이 없는 묶음은 건너뛴다.
3. 연결 · 계열에 세우기 · 아니오가 묶음의 장비 전부에 걸리고, 아니오 한 묶음은 일감에서 빠진다.
4. 정하기가 실패하면 **요청도 남지 않는다** — 누르지도 않은 요청이 목록에 서면 안 된다.
5. 시스템 관리자 전용. CSV 는 조사에 들고 가는 표라 자산번호를 전부 싣는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, category_id, site_id


def _equipment(
    client: TestClient, admin: Signed, maker: str | None, model: str | None
) -> dict[str, Any]:
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"GAP-{uuid.uuid4().hex[:8]}",
            "name": "보강 대상 장비",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
            "maker_text": maker,
            "model_text": model,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    out: dict[str, Any] = made.json()
    return out


def _catalog(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str], tag: str
) -> dict[str, Any]:
    """제조사 하나 · 계열 하나 · 기종 둘(`{TAG}X-100` · `{TAG}X-200`)."""
    maker_id = term_factory("manufacturer", f"Gapco{tag}")
    series = client.post(
        "/api/equipment-series",
        json={
            "name": f"Gapco {tag.upper()}X Series",
            "maker_term_id": maker_id,
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    models = {}
    for code in ("100", "200"):
        made = client.post(
            "/api/equipment-models",
            json={"series_id": series.json()["id"], "name": f"{tag.upper()}X-{code}"},
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text
        models[code] = made.json()["id"]
    return {"maker": maker_id, "series": series.json()["id"], "models": models}


def _gaps(client: TestClient, admin: Signed, tag: str) -> dict[str, Any]:
    got = client.get("/api/equipment-models/gaps", params={"q": tag}, headers=admin.headers)
    assert got.status_code == 200, got.text
    out: dict[str, Any] = got.json()
    return out


def _by_model(body: dict[str, Any]) -> dict[str | None, dict[str, Any]]:
    """모델명 표기(대문자로) → 묶음. 묶음의 표기는 첫 장비의 것이라 대소문자가 갈린다."""
    return {
        group["model_text"].upper() if group["model_text"] else None: group
        for group in body["groups"]
    }


def test_미연결_장비를_경우별로_가른다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    up = tag.upper()
    catalog = _catalog(client, admin, term_factory, tag)
    _equipment(client, admin, f"Gapco{tag}", f"{up}X-100")  # 같은 기종
    _equipment(client, admin, f"gapco {tag}", f"{tag}x-100")  # 대소문자·띄어쓰기만 다름
    _equipment(client, admin, f"Gapco{tag}", f"{up}X-110")  # 비슷하지만 다른 기종
    _equipment(client, admin, f"Gapco{tag}", f"{up}X-ULTRA9")  # 계열만 있음
    _equipment(client, admin, f"Nobody{tag}", f"QQ-{up}")  # 제조사부터 없음
    _equipment(client, admin, f"Gapco{tag}", None)  # 모델명 없음

    groups = _by_model(_gaps(client, admin, tag))

    same = groups[f"{up}X-100"]
    assert same["case"] == "exact"
    # 대소문자·띄어쓰기만 다른 두 대는 한 묶음이다 — 기종 등록 요청과 같은 열쇠.
    assert same["count"] == 2
    assert [one["id"] for one in same["models"]] == [catalog["models"]["100"]]

    near = groups[f"{up}X-110"]
    assert near["case"] == "similar"
    # **후보로만 보인다** — 비슷한 기종을 고르면 그 장비의 수치가 남의 것이 된다.
    assert catalog["models"]["100"] in [one["id"] for one in near["models"]]
    assert catalog["series"] in [one["id"] for one in near["series"]]

    family = groups[f"{up}X-ULTRA9"]
    assert family["case"] == "series_only"
    assert [one["id"] for one in family["series"]] == [catalog["series"]]
    assert family["models"] == []

    missing = groups[f"QQ-{up}"]
    assert missing["case"] == "not_in_catalog"
    assert missing["maker_known"] is False

    blank = groups[None]
    assert blank["case"] == "no_model"
    assert blank["maker_known"] is True


def test_옛_사명으로_적힌_기종은_다른_제조사에서_찾아_후보로_둔다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """대장에는 옛 사명이 남는다(「Agilent E4980A」 → 현 Keysight). 제조사 안에서 못 찾은
    기종 번호를 다른 제조사에서 찾되, **같은 기종이라고 단정하지 않는다**(비슷한 기종)."""
    tag = uuid.uuid4().hex[:6]
    up = tag.upper()
    catalog = _catalog(client, admin, term_factory, tag)
    term_factory("manufacturer", f"Oldco{tag}")  # 카탈로그에 있는 다른 제조사(기종 없음)
    _equipment(client, admin, f"Oldco{tag}", f"{up}X-100")

    moved = _by_model(_gaps(client, admin, tag))[f"{up}X-100"]
    assert moved["case"] == "similar"
    assert moved["maker_known"] is True
    assert [one["id"] for one in moved["models"]] == [catalog["models"]["100"]]


def test_요청으로_올리고_연결하고_세우고_아니오_한다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    up = tag.upper()
    catalog = _catalog(client, admin, term_factory, tag)
    same = _equipment(client, admin, f"Gapco{tag}", f"{up}X-100")
    family = _equipment(client, admin, f"Gapco{tag}", f"{up}X-ULTRA9")
    _equipment(client, admin, f"Gapco{tag}", f"{up}X-110")
    _equipment(client, admin, f"Gapco{tag}", None)
    groups = _by_model(_gaps(client, admin, tag))

    # 1. 요청으로 올린다 — 모델명이 없는 묶음은 건너뛴다(요청은 모델명이 열쇠다).
    raised = client.post(
        "/api/equipment-models/gaps/requests",
        json={"keys": [groups[f"{up}X-100"]["key"], groups[None]["key"]]},
        headers=admin.headers,
    )
    assert raised.status_code == 200, raised.text
    assert raised.json()["requested"] == 1
    assert raised.json()["skipped"] == [groups[None]["key"]]
    listed = client.get("/api/equipment-models/proposals", headers=admin.headers).json()
    assert groups[f"{up}X-100"]["key"] in [one["normalized"] for one in listed]
    assert _by_model(_gaps(client, admin, tag))[f"{up}X-100"]["open_requests"] == 1

    # 2. 같은 기종에 잇는다 — 요청 흐름을 지나므로 요청 줄도 정해진다.
    linked = client.post(
        "/api/equipment-models/gaps/resolve",
        json={"key": groups[f"{up}X-100"]["key"], "model_id": catalog["models"]["100"]},
        headers=admin.headers,
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["linked"] == 1
    row = client.get(f"/api/equipment/{same['id']}", headers=admin.headers).json()
    assert row["model_id"] == catalog["models"]["100"]

    # 3. 계열에 기종을 세우고 잇는다.
    made = client.post(
        "/api/equipment-models/gaps/resolve",
        json={
            "key": groups[f"{up}X-ULTRA9"]["key"],
            "series_id": catalog["series"],
            "name": f"{up}X-ULTRA9",
        },
        headers=admin.headers,
    )
    assert made.status_code == 200, made.text
    assert made.json()["status"] == "created" and made.json()["linked"] == 1
    row = client.get(f"/api/equipment/{family['id']}", headers=admin.headers).json()
    assert row["model_id"] == made.json()["model_id"]

    # 4. **정하기가 실패하면 요청도 남지 않는다** — 인자 둘은 400 이고, 요청 목록에 안 선다.
    near_key = groups[f"{up}X-110"]["key"]
    both = client.post(
        "/api/equipment-models/gaps/resolve",
        json={"key": near_key, "model_id": catalog["models"]["100"], "reject": True},
        headers=admin.headers,
    )
    assert both.status_code == 400, both.text
    assert both.json()["error"]["code"] == "TSC-EQUIPMENT-0044"
    listed = client.get("/api/equipment-models/proposals", headers=admin.headers).json()
    assert near_key not in [one["normalized"] for one in listed]

    # 5. 아니오 — 장비는 미연결로 남고, 일감에서 빠진다(「카탈로그 대상 아님」).
    no = client.post(
        "/api/equipment-models/gaps/resolve",
        json={"key": near_key, "reject": True},
        headers=admin.headers,
    )
    assert no.status_code == 200, no.text
    assert no.json()["status"] == "rejected"
    after = _gaps(client, admin, tag)
    remaining = _by_model(after)
    assert f"{up}X-100" not in remaining and f"{up}X-ULTRA9" not in remaining
    assert remaining[f"{up}X-110"]["case"] == "excluded"

    # 모델명 없는 묶음은 묶음으로 못 잇는다 — 장비 화면에서 모델명을 채워야 한다.
    blank = client.post(
        "/api/equipment-models/gaps/resolve",
        json={"key": groups[None]["key"], "model_id": catalog["models"]["200"]},
        headers=admin.headers,
    )
    assert blank.status_code == 400, blank.text
    assert blank.json()["error"]["code"] == "TSC-EQUIPMENT-0047"


def test_CSV_는_자산번호를_전부_싣는다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    rows = [_equipment(client, admin, f"Csvco{tag}", f"CSV-{tag}") for _ in range(2)]

    got = client.get("/api/equipment-models/gaps/export", headers=admin.headers)
    assert got.status_code == 200, got.text
    assert got.headers["content-type"].startswith("text/csv")
    assert "attachment" in got.headers["content-disposition"]
    text = got.content.decode("utf-8")
    # 엑셀이 한글을 깨지 않게 BOM 이 앞에 온다.
    assert text.startswith("﻿경우,")
    line = next(one for one in text.splitlines() if f"CSV-{tag}" in one)
    assert all(row["asset_no"] in line for row in rows)
    assert "카탈로그에 없음" in line


def test_시스템_관리자만_본다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    from app.modules.accounts.models import User
    from app.modules.auth import security
    from app.modules.workspaces.models import WorkspaceMember

    tag = uuid.uuid4().hex[:6]
    email = f"gap-member-{tag}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-member"),
        display_name="구성원",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
    db.commit()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "pw-member"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for method, path, body in (
        ("GET", "/api/equipment-models/gaps", None),
        ("GET", "/api/equipment-models/gaps/export", None),
        ("POST", "/api/equipment-models/gaps/requests", {"keys": ["x"]}),
        ("POST", "/api/equipment-models/gaps/resolve", {"key": "x", "reject": True}),
    ):
        refused = client.request(method, path, json=body, headers=headers)
        assert refused.status_code == 403, (path, refused.text)
        assert refused.json()["error"]["code"] == "TSC-EQUIPMENT-0045"
