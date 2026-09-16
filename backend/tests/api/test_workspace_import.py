"""부서 정보 가져오기 — ReportArchive 내보내기를 붙여넣어 조직도를 들인다.

여기서 지키는 것 — 미리보기와 적용이 같은 판정 · 부모가 뒤에 와도 depth 로 먼저 만든다 · 있는
부서는 안 덮는다(update_existing 이면 덮음) · TF 는 건너뛴다 · slug 는 고쳐 쓰지 않는다 ·
공개 정책(external_view_default)은 옮기지 않는다 · 시스템 관리자만.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.api.conftest import Signed

HEADER = (
    "slug,name,parent_slug,parent_name,depth,path,kind,status,description,"
    "sort_order,external_view_default,member_count,managers,created_at"
)


def _csv(*rows: str) -> str:
    return "﻿" + "\n".join([HEADER, *rows]) + "\n"


def test_미리보기_뒤_적용하고_두_번째는_건너뛴다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    text = _csv(
        # 자식이 먼저 와도(엑셀에서 정렬한 파일) depth 로 부모를 먼저 만든다.
        f"lab-{tag},재료시험팀,div-{tag},개발본부,1,개발본부 / 재료시험팀,org,active,"
        "장비 많음,2,true,3,홍길동,2026-01-01",
        f"div-{tag},개발본부,,,0,개발본부,org,active,,1,false,10,,2026-01-01",
        f"tf-{tag},신제품 TF,div-{tag},개발본부,1,개발본부 / 신제품 TF,tf,active,"
        ",3,false,2,,2026-01-01",
        f"Bad Slug {tag},이름,,,0,,org,active,,4,false,0,,2026-01-01",
    )
    preview = client.post("/api/workspaces/import", json={"text": text}, headers=admin.headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["dry_run"] is True
    assert (body["created"], body["skipped"], body["errors"]) == (2, 1, 1)
    actions = {row["slug"]: row["action"] for row in body["rows"]}
    assert actions[f"div-{tag}"] == "create" and actions[f"lab-{tag}"] == "create"
    assert actions[f"tf-{tag}"] == "skip_kind"
    assert actions[f"Bad Slug {tag}"] == "error"
    # 미리보기는 아무것도 안 만든다.
    listed = client.get("/api/workspaces?all=true", headers=admin.headers).json()
    assert not any(one["slug"] == f"div-{tag}" for one in listed)

    applied = client.post(
        "/api/workspaces/import",
        params={"dry_run": "false"},
        json={"text": text},
        headers=admin.headers,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["created"] == 2
    listed = {
        one["slug"]: one
        for one in client.get("/api/workspaces?all=true", headers=admin.headers).json()
    }
    assert listed[f"lab-{tag}"]["parent_slug"] == f"div-{tag}"
    assert listed[f"lab-{tag}"]["sort_order"] == 2
    # **공개 정책은 안 옮긴다** — external_view_default=true 였지만 restricted 는 기본 false.
    assert listed[f"lab-{tag}"]["restricted"] is False

    # 두 번째 반입: 있는 부서는 건너뛴다. 이름을 바꿔 와도 안 덮는다.
    again = client.post(
        "/api/workspaces/import",
        params={"dry_run": "false"},
        json={"text": _csv(f"lab-{tag},이름바꿈,div-{tag},,1,,org,active,,2,false,0,,")},
        headers=admin.headers,
    ).json()
    assert again["created"] == 0 and again["skipped"] == 1
    assert client.get("/api/workspaces?all=true", headers=admin.headers).json()
    listed = {
        one["slug"]: one
        for one in client.get("/api/workspaces?all=true", headers=admin.headers).json()
    }
    assert listed[f"lab-{tag}"]["name"] == "재료시험팀"

    # update_existing 이면 덮는다 — 이름·보관 상태.
    updated = client.post(
        "/api/workspaces/import",
        params={"dry_run": "false"},
        json={
            "text": _csv(f"lab-{tag},이름바꿈,div-{tag},,1,,org,archived,,5,false,0,,"),
            "update_existing": True,
        },
        headers=admin.headers,
    ).json()
    assert updated["updated"] == 1
    listed = {
        one["slug"]: one
        for one in client.get("/api/workspaces?all=true", headers=admin.headers).json()
    }
    assert (
        listed[f"lab-{tag}"]["name"] == "이름바꿈"
        and listed[f"lab-{tag}"]["is_active"] is False
    )


def test_형식이_아니면_무엇이_없는지_말한다(client: TestClient, admin: Signed) -> None:
    wrong = client.post(
        "/api/workspaces/import", json={"text": "a,b\n1,2\n"}, headers=admin.headers
    )
    assert wrong.status_code == 422
    assert "slug" in wrong.json()["error"]["message"]

    # 탭으로 붙여넣어도(엑셀 복사) 읽는다.
    tag = uuid.uuid4().hex[:6]
    tabbed = "slug\tname\tparent_slug\tkind\n" + f"tab-{tag}\t탭부서\t\torg\n"
    got = client.post("/api/workspaces/import", json={"text": tabbed}, headers=admin.headers)
    assert got.status_code == 200 and got.json()["created"] == 1
