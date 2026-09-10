"""보유 장비 **일괄 반입** — 엑셀에서 복사해 붙여넣은 대장을 받는다.

## 왜 이 시험이 촘촘한가

반입은 **틀리면 대장을 망친다.** 한 대씩 등록하면 틀린 것 하나가 한 줄이지만,
여기서는 300줄이다. 그리고 잘못 들어간 장비는 지우기 전까지 검색이 계속 그것으로
답한다 — 「됩니다」 라고 답한 뒤 현장에 가 보니 그런 장비가 없는 일이 생긴다.

## 여기서 지키는 것

1. **전부 되거나 전부 안 되거나.** 반쯤 들어간 대장은 안 들어간 대장보다 나쁘다.
2. **미리보기는 아무것도 저장하지 않는다.**
3. **못 정하는 이름은 거절한다** — 비슷한 기종에 끼워 넣지 않는다(ADR 0003).
4. **줄 번호로 말한다** — 사람이 엑셀에서 그 줄을 찾을 수 있어야 한다.
5. **기준정보를 만들지 않는다** — 오타가 그대로 축이 되면 합칠 방법이 없다.
6. **엑셀이 주는 그대로 읽는다** — 탭 구분·`\\r\\n`·끝의 빈 줄.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed
from tests.api.test_catalog_list_cost import counted

HEADER = "자산번호,장비명,보유부서,거점,설치위치,장비유형,기종,상태,공용여부"


def _term(client: TestClient, admin: Signed, axis: str, value: str) -> str:
    response = client.post(
        f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _workspace_name(client: TestClient, admin: Signed) -> str:
    response = client.get("/api/workspaces", headers=admin.headers)
    assert response.status_code == 200, response.text
    rows = [one for one in response.json() if one["slug"] == admin.workspace]
    assert rows, "관리자의 부서를 못 찾았다"
    name: str = rows[0]["name"]
    return name


def _upload(
    client: TestClient, admin: Signed, body: str, *, dry_run: bool = True
) -> dict[str, Any]:
    """**엑셀에서 복사해 붙여넣은 것처럼** 보낸다. 파일이 아니다 — DRM 이 걸린
    환경에서는 파일을 올릴 수 없다."""
    response = client.post(
        f"/api/equipment/import?dry_run={'true' if dry_run else 'false'}",
        json={"text": body},
        headers=admin.headers,
    )
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def _fixture(client: TestClient, admin: Signed) -> tuple[str, str, str]:
    """반입이 이름으로 찾을 수 있는 부서·거점·분류 하나씩."""
    tag = uuid.uuid4().hex[:6]
    site = f"거점{tag}"
    category = f"분류{tag}"
    _term(client, admin, "site", site)
    _term(client, admin, "equipment_category", category)
    return _workspace_name(client, admin), site, category


def test_서식을_내려받으면_머리글과_보기가_온다(client: TestClient, admin: Signed) -> None:
    """**빈 서식만 주지 않는다.** 「공용여부에 뭘 적나」 를 물어야 하면 그 서식은
    절반만 쓸모가 있다."""
    response = client.get("/api/equipment/import/template", headers=admin.headers)
    assert response.status_code == 200, response.text
    body = response.content.decode("utf-8")
    # 엑셀이 UTF-8 을 알아보려면 BOM 이 있어야 한다 — 없으면 한글이 깨지고,
    # 사람은 서식이 잘못된 줄 안다.
    assert body.startswith("﻿"), "BOM 이 없다 — 엑셀에서 한글이 깨진다"
    assert "자산번호" in body and "보유부서" in body
    assert len(body.strip().splitlines()) >= 2, "보기 줄이 없다"


def test_미리보기는_아무것도_저장하지_않는다(client: TestClient, admin: Signed) -> None:
    workspace, site, category = _fixture(client, admin)
    asset_no = f"DRY-{uuid.uuid4().hex[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동 201호,{category},,가동,예\n"

    result = _upload(client, admin, body)
    assert result["total"] == 1
    assert result["ready"] == 1
    assert result["created"] == 0, "미리보기가 장비를 만들었다"

    listed = client.get(f"/api/equipment?asset_no={asset_no}", headers=admin.headers)
    assert listed.json()["total"] == 0, "미리보기 뒤에 장비가 남아 있다"


def test_확인하면_들어간다(client: TestClient, admin: Signed) -> None:
    workspace, site, category = _fixture(client, admin)
    tag = uuid.uuid4().hex[:6]
    body = (
        f"{HEADER}\n"
        f"IMP-{tag}-1,만능기,{workspace},{site},3동 201호,{category},,가동,예\n"
        f"IMP-{tag}-2,충격기,{workspace},{site},3동 202호,{category},,유휴,아니오\n"
    )
    result = _upload(client, admin, body, dry_run=False)
    assert result["created"] == 2, result

    listed = client.get(f"/api/equipment?q=IMP-{tag}", headers=admin.headers)
    assert listed.json()["total"] == 2
    rows = {one["asset_no"]: one for one in listed.json()["items"]}
    assert rows[f"IMP-{tag}-1"]["shared_use"] is True
    assert rows[f"IMP-{tag}-2"]["status"] == "idle"


def test_한_줄이라도_틀리면_아무것도_안_들어간다(client: TestClient, admin: Signed) -> None:
    """**반쯤 들어간 대장은 안 들어간 대장보다 나쁘다.**

    되는 것만 넣으면 사람은 파일을 고쳐 다시 올리다가 이미 들어간 줄에서 「이미
    등록된 자산번호」 를 만나고, 그때 무엇을 지워야 할지 모른다.
    """
    workspace, site, category = _fixture(client, admin)
    tag = uuid.uuid4().hex[:6]
    body = (
        f"{HEADER}\n"
        f"BAD-{tag}-1,만능기,{workspace},{site},3동 201호,{category},,가동,예\n"
        f"BAD-{tag}-2,충격기,없는부서,{site},3동 202호,{category},,가동,예\n"
    )
    result = _upload(client, admin, body, dry_run=False)
    assert result["created"] == 0, "틀린 줄이 있는데 넣었다"
    assert result["problems"] == 1

    listed = client.get(f"/api/equipment?q=BAD-{tag}", headers=admin.headers)
    assert listed.json()["total"] == 0, "멀쩡한 줄이 들어가 버렸다"


def test_문제를_줄_번호로_말한다(client: TestClient, admin: Signed) -> None:
    """「12번째 줄」 이라고 말해 줘야 사람이 엑셀에서 찾는다."""
    workspace, site, category = _fixture(client, admin)
    body = (
        f"{HEADER}\n"
        f"L2-{uuid.uuid4().hex[:6]},만능기,{workspace},{site},3동,{category},,가동,예\n"
        f",이름만있음,{workspace},{site},3동,{category},,가동,예\n"
    )
    result = _upload(client, admin, body)
    bad = [one for one in result["rows"] if one["problems"]]
    assert len(bad) == 1
    # 머리글 다음이 2 다 — 엑셀이 보여 주는 번호와 같아야 한다.
    assert bad[0]["line"] == 3, bad
    assert any("자산번호" in one for one in bad[0]["problems"])


def test_문제를_모아서_준다(client: TestClient, admin: Signed) -> None:
    """첫 문제에서 멈추면 사람이 고치고 올리기를 문제 수만큼 되풀이한다."""
    workspace, site, _ = _fixture(client, admin)
    body = (
        f"{HEADER}\n"
        f"MULTI-{uuid.uuid4().hex[:6]},만능기,없는부서,없는거점,3동,없는분류,,모르는상태,글쎄\n"
    )
    result = _upload(client, admin, body)
    problems = result["rows"][0]["problems"]
    assert len(problems) >= 4, problems
    assert workspace not in " ".join(problems)
    assert site not in " ".join(problems)


def test_기준정보에_없는_값을_만들지_않는다(client: TestClient, admin: Signed) -> None:
    """반입이 값을 만들면 오타가 그대로 축이 되고, 「본사」 와 「본사 」 가 서로 다른
    거점이 된다 — 그 둘은 나중에 합칠 방법이 없다."""
    workspace, _site, category = _fixture(client, admin)
    ghost = f"유령거점{uuid.uuid4().hex[:6]}"
    body = (
        f"{HEADER}\n"
        f"GHOST-{uuid.uuid4().hex[:6]},만능기,{workspace},{ghost},3동,{category},,가동,예\n"
    )
    result = _upload(client, admin, body, dry_run=False)
    assert result["created"] == 0
    assert any("거점" in one for one in result["rows"][0]["problems"])

    terms = client.get("/api/vocabularies/site/terms", headers=admin.headers)
    assert ghost not in {one["value"] for one in terms.json()}, "반입이 축의 값을 만들었다"


def test_파일_안의_자산번호_중복을_잡는다(client: TestClient, admin: Signed) -> None:
    """DB 에 없더라도 같은 번호가 두 줄에 있으면, 둘째 줄에서 막힐 때는 이미 첫 줄이
    들어간 뒤다."""
    workspace, site, category = _fixture(client, admin)
    same = f"DUP-{uuid.uuid4().hex[:6]}"
    body = (
        f"{HEADER}\n"
        f"{same},만능기,{workspace},{site},3동 201호,{category},,가동,예\n"
        f"{same},충격기,{workspace},{site},3동 202호,{category},,가동,예\n"
    )
    result = _upload(client, admin, body, dry_run=False)
    assert result["created"] == 0
    assert any("겹칩니다" in one for one in result["rows"][1]["problems"])


def test_이미_있는_자산번호는_덮어쓰지_않는다(client: TestClient, admin: Signed) -> None:
    """같은 번호의 다른 장비일 수도 있고, 그때 덮으면 있던 이력이 사라진다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"EXIST-{uuid.uuid4().hex[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동,{category},,가동,예\n"
    assert _upload(client, admin, body, dry_run=False)["created"] == 1

    again = _upload(client, admin, body)
    assert again["ready"] == 0
    assert any("이미 등록" in one for one in again["rows"][0]["problems"])


def test_기종을_하나로_못_정하면_거절한다(client: TestClient, admin: Signed) -> None:
    """비슷한 기종에 끼워 넣으면 그 장비의 하중·온도가 남의 것이 되고, 검색은 그
    남의 수치로 「됩니다」 라고 답한다."""
    workspace, site, category = _fixture(client, admin)
    body = (
        f"{HEADER}\n"
        f"NOMODEL-{uuid.uuid4().hex[:6]},만능기,{workspace},{site},3동,{category},"
        f"세상에없는기종{uuid.uuid4().hex[:6]},가동,예\n"
    )
    result = _upload(client, admin, body)
    assert result["ready"] == 0
    assert any("기종" in one for one in result["rows"][0]["problems"])


def test_기종을_이으면_시험_항목이_복사된다(client: TestClient, admin: Signed) -> None:
    """**이것이 반입의 핵심이다.** 기종을 안 이으면 시험 항목이 0 건이고, 0 건이면
    그 장비는 검색에 절대 안 걸린다 — 대장에만 있고 아무도 못 찾는다."""
    workspace, site, _ = _fixture(client, admin)
    tag = uuid.uuid4().hex[:8]
    series = client.post(
        "/api/equipment-series", json={"name": f"계열{tag}"}, headers=admin.headers
    )
    assert series.status_code == 201, series.text
    item = _term(client, admin, "test_item", f"항목{tag}")
    client.post(
        f"/api/equipment-series/{series.json()['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    model_name = f"기종{tag}"
    made = client.post(
        "/api/equipment-models",
        json={"series_id": series.json()["id"], "name": model_name},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    asset_no = f"LINK-{tag[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동,,{model_name},가동,예\n"
    preview = _upload(client, admin, body)
    assert preview["rows"][0]["model_linked"] is True, "미리보기가 연결을 안 알려 준다"

    assert _upload(client, admin, body, dry_run=False)["created"] == 1
    listed = client.get(f"/api/equipment?asset_no={asset_no}", headers=admin.headers)
    row = listed.json()["items"][0]
    assert row["test_items"] == [f"항목{tag}"], row


def test_엑셀에서_복사한_탭_구분도_읽는다(client: TestClient, admin: Signed) -> None:
    """**엑셀이 클립보드에 넣는 것은 탭이다.** 쉼표만 받으면 붙여넣기가 통째로
    거절되고, 그때 사람은 무엇이 문제인지 알 수 없다."""
    workspace, site, category = _fixture(client, admin)
    body = (
        HEADER.replace(",", "\t")
        + "\n"
        + "\t".join(
            [
                f"TAB-{uuid.uuid4().hex[:6]}",
                "만능기",
                workspace,
                site,
                "3동 201호",
                category,
                "",
                "가동",
                "예",
            ]
        )
        + "\n"
    )
    assert _upload(client, admin, body)["ready"] == 1


def test_값_안의_쉼표를_탭이_지켜_준다(client: TestClient, admin: Signed) -> None:
    """「3동, 201호」 처럼 값에 쉼표가 들어가면 쉼표로는 칸이 밀린다. 엑셀에서 복사한
    탭 구분에서는 안 밀린다 — 탭은 칸 사이에만 있다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"COMMA-{uuid.uuid4().hex[:6]}"
    body = (
        HEADER.replace(",", "\t")
        + "\n"
        + "\t".join(
            [asset_no, "만능기", workspace, site, "3동, 201호", category, "", "가동", "예"]
        )
        + "\n"
    )
    assert _upload(client, admin, body, dry_run=False)["created"] == 1
    listed = client.get(f"/api/equipment?asset_no={asset_no}", headers=admin.headers)
    assert listed.json()["items"][0]["location"] == "3동, 201호"


def test_엑셀이_붙인_줄바꿈과_빈_줄을_견딘다(client: TestClient, admin: Signed) -> None:
    """엑셀 클립보드는 `\r\n` 을 쓰고 끝에 빈 줄을 남긴다."""
    workspace, site, category = _fixture(client, admin)
    body = (
        HEADER.replace(",", "\t")
        + "\r\n"
        + "\t".join(
            [
                f"CRLF-{uuid.uuid4().hex[:6]}",
                "만능기",
                workspace,
                site,
                "3동",
                category,
                "",
                "가동",
                "예",
            ]
        )
        + "\r\n\r\n"
    )
    assert _upload(client, admin, body)["ready"] == 1


def test_아무것도_안_붙여넣으면_그렇게_말한다(client: TestClient, admin: Signed) -> None:
    response = client.post(
        "/api/equipment/import", json={"text": "   \n\n"}, headers=admin.headers
    )
    assert response.status_code == 400, response.text
    assert "머리글" in response.text


def test_머리글이_모자라면_무엇이_없는지_말한다(client: TestClient, admin: Signed) -> None:
    response = client.post(
        "/api/equipment/import",
        json={"text": "자산번호,장비명\nA-1,만능기\n"},
        headers=admin.headers,
    )
    assert response.status_code == 400, response.text
    assert "보유부서" in response.text


def test_미리보기는_권한도_본다(client: TestClient, admin: Signed, db: Session) -> None:
    """**미리보기가 통과시킨 것은 저장도 통과해야 한다.**

    권한을 저장 때만 보면 「300줄 다 됩니다」 라고 해 놓고 저장에서 403 이 터지고,
    전부 되돌아간다. 그 한 번으로 사람은 미리보기를 두 번 다시 안 믿는다.
    """
    workspace, site, category = _fixture(client, admin)

    # 남의 부서 관리자 한 명. 자기 부서만 등록할 수 있다.
    other = Workspace(
        slug=f"other-{uuid.uuid4().hex[:8]}", name=f"다른팀{uuid.uuid4().hex[:4]}"
    )
    db.add(other)
    db.flush()
    email = f"lead-{uuid.uuid4().hex[:8]}@testscope.local"
    lead = User(
        email=email,
        password_hash=security.hash_password("lead-password"),
        display_name="다른팀장",
        status="active",
        home_workspace_id=other.id,
    )
    db.add(lead)
    db.flush()
    db.add(WorkspaceMember(workspace_id=other.id, user_id=lead.id, role="manager"))
    db.commit()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "lead-password"}
    ).json()["access_token"]

    body = (
        f"{HEADER}\n"
        f"PERM-{uuid.uuid4().hex[:6]},만능기,{workspace},{site},3동,{category},,가동,예\n"
    )
    response = client.post(
        "/api/equipment/import?dry_run=true",
        json={"text": body},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ready"] == 0, "미리보기가 남의 부서를 통과시켰다"
    assert any("보유부서" in one for one in result["rows"][0]["problems"]), result


def test_미리보기_질의가_줄_수를_따라_늘지_않는다(client: TestClient, admin: Signed) -> None:
    """**여기가 상한을 정하던 자리였다.**

    전에는 줄마다 부서·거점·분류·기종·자산번호를 다시 물어서, 2000줄짜리 대장 하나가
    질의를 16,000회 하고 7초를 썼다(실측). 그래서 상한을 낮게 잡아야 했다.

    지금은 이름을 쪽 단위로 한 번에 찾는다(`Lookup`). 이 시험은 그 성질이 되돌아오지
    않게 막는다 — 줄마다 `db.get` 하나를 넣는 사람은 그것이 대장에서 2000번이라는
    것을 모른다.
    """
    workspace, site, category = _fixture(client, admin)
    tag = uuid.uuid4().hex[:6]

    def paste(count: int) -> str:
        rows = [
            f"COST{tag}-{i},장비{i},{workspace},{site},3동 {i}호,{category},,가동,아니오"
            for i in range(count)
        ]
        return HEADER + "\n" + "\n".join(rows) + "\n"

    def cost(count: int) -> int:
        with counted() as seen:
            result = _upload(client, admin, paste(count))
        assert result["total"] == count, result
        return len(seen)

    few, many = cost(3), cost(30)
    # 열 배로 늘려도 그대로여야 한다. 고정비가 조금 붙는 것은 봐 준다.
    assert many <= few + 2, f"3줄에 {few}회 · 30줄에 {many}회 — 줄마다 묻고 있다"
    assert many <= 20, f"30줄에 질의 {many}회"
