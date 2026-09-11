"""보유 장비 **일괄 반입** — 엑셀에서 복사해 붙여넣은 대장을 받는다.

## 왜 이 시험이 촘촘한가

반입은 **틀리면 대장을 망친다.** 한 대씩 등록하면 틀린 것 하나가 한 줄이지만,
여기서는 300줄이다. 그리고 잘못 들어간 장비는 지우기 전까지 검색이 계속 그것으로
답한다 — 「됩니다」 라고 답한 뒤 현장에 가 보니 그런 장비가 없는 일이 생긴다.

## 여기서 지키는 것

1. **넣을 수 있는 줄은 넣고, 못 넣은 줄은 그렇게 말한다**(`imported`) — 화면이 들어간
   줄을 지워야 사람이 남은 것만 고쳐 다시 넣는다. 넣기로 한 것들은 한 트랜잭션이라,
   그중 하나가 막히면 통째로 되돌아간다.
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


def _said(row: dict[str, Any]) -> list[str]:
    """그 줄의 문제를 **사람이 읽는 말**로. 칸 키는 `_fields` 가 본다."""
    return [one["message"] for one in row["problems"]]


def _fields(row: dict[str, Any]) -> set[str | None]:
    """그 줄에서 **어느 칸이** 걸렸나. 화면이 그 칸을 붉게 칠하는 근거다."""
    return {one["field"] for one in row["problems"]}


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


def test_틀린_줄이_있어도_멀쩡한_줄은_들어간다(client: TestClient, admin: Signed) -> None:
    """문제가 있는 줄 때문에 멀쩡한 줄까지 막으면, 300줄 중 12줄이 틀렸을 때 288줄을
    다시 붙여넣어야 한다.

    전에는 통째로 막았다. 「되는 것만 넣으면 고쳐 다시 올리다가 이미 들어간 줄에서
    「이미 등록된 자산번호」 를 만난다」 는 이유였는데, **줄마다 들어갔는지를
    말해 주면**(`imported`) 화면이 그 줄을 지울 수 있고 다시 붙여넣을 것이 없어진다.
    """
    workspace, site, category = _fixture(client, admin)
    tag = uuid.uuid4().hex[:6]
    body = (
        f"{HEADER}\n"
        f"BAD-{tag}-1,만능기,{workspace},{site},3동 201호,{category},,가동,예\n"
        f"BAD-{tag}-2,충격기,없는부서,{site},3동 202호,{category},,가동,예\n"
    )
    result = _upload(client, admin, body, dry_run=False)
    assert result["created"] == 1, result
    assert result["problems"] == 1

    # **줄마다 들어갔는지를 말한다** — 화면이 들어간 줄을 지우는 근거다.
    assert [one["imported"] for one in result["rows"]] == [True, False]

    listed = client.get(f"/api/equipment?q=BAD-{tag}", headers=admin.headers)
    assert {one["asset_no"] for one in listed.json()["items"]} == {f"BAD-{tag}-1"}


def test_미리보기는_아무_줄도_들어갔다고_안_한다(client: TestClient, admin: Signed) -> None:
    workspace, site, category = _fixture(client, admin)
    body = (
        f"{HEADER}\n"
        f"PRE-{uuid.uuid4().hex[:6]},만능기,{workspace},{site},3동,{category},,가동,예\n"
    )
    result = _upload(client, admin, body)
    assert result["rows"][0]["imported"] is False, "미리보기가 들어갔다고 말했다"


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
    assert any("자산번호" in one for one in _said(bad[0]))
    # **어느 칸인지도 온다** — 화면이 그 칸을 붉게 칠한다.
    assert "asset_no" in _fields(bad[0])


def test_문제를_모아서_준다(client: TestClient, admin: Signed) -> None:
    """첫 문제에서 멈추면 사람이 고치고 올리기를 문제 수만큼 되풀이한다."""
    workspace, site, _ = _fixture(client, admin)
    body = (
        f"{HEADER}\n"
        f"MULTI-{uuid.uuid4().hex[:6]},만능기,없는부서,없는거점,3동,없는분류,,모르는상태,글쎄\n"
    )
    result = _upload(client, admin, body)
    problems = _said(result["rows"][0])
    assert len(problems) >= 4, problems
    assert workspace not in " ".join(problems)
    assert site not in " ".join(problems)
    # 걸린 칸이 넷 다 다르다 — 한 칸에 몰아 놓으면 화면이 어디를 칠할지 모른다.
    assert {"workspace", "site", "category", "status"} <= _fields(result["rows"][0])


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
    assert any("거점" in one for one in _said(result["rows"][0]))
    assert "site" in _fields(result["rows"][0])

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
    # 첫 줄은 멀쩡하므로 들어간다. 둘째 줄만 남는다.
    assert result["created"] == 1
    assert result["rows"][0]["imported"] is True
    assert result["rows"][1]["imported"] is False
    assert any("겹칩니다" in one for one in _said(result["rows"][1]))
    # 한 칸에 못 붙이는 문제다 — 어느 줄이 원본인지가 요점이다.
    assert None in _fields(result["rows"][1])


def test_이미_있는_자산번호는_덮어쓰지_않는다(client: TestClient, admin: Signed) -> None:
    """같은 번호의 다른 장비일 수도 있고, 그때 덮으면 있던 이력이 사라진다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"EXIST-{uuid.uuid4().hex[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동,{category},,가동,예\n"
    assert _upload(client, admin, body, dry_run=False)["created"] == 1

    again = _upload(client, admin, body)
    assert again["ready"] == 0
    assert any("이미 등록" in one for one in _said(again["rows"][0]))
    assert "asset_no" in _fields(again["rows"][0])


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
    assert any("기종" in one for one in _said(result["rows"][0]))
    assert "model" in _fields(result["rows"][0])


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
    assert any("보유부서" in one for one in _said(result["rows"][0])), result
    assert "workspace" in _fields(result["rows"][0])


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


def test_열_목록을_서버가_준다(client: TestClient, admin: Signed) -> None:
    """**화면이 자기 목록을 따로 들지 않게** 서버가 준다.

    두 벌로 두면 열을 하나 더한 날 한쪽만 고쳐지고, 그때 사람이 채운 칸이 조용히
    버려진다 — 그 손실은 넣은 사람 눈에 안 보인다.
    """
    response = client.get("/api/equipment/import/columns", headers=admin.headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    keys = [one["key"] for one in rows]
    assert keys[:5] == ["asset_no", "name", "workspace", "site", "location"]
    assert all(one["required"] for one in rows[:5]), "필수 다섯이 필수로 안 온다"
    assert not any(one["required"] for one in rows[5:]), "안 필수인 것이 필수로 온다"

    # **별칭도 함께 온다.** 화면이 「머리글이 붙었나」 를 이것으로 판정한다 —
    # 자기 목록으로 하면 서버가 받아 주는 이름과 어긋나서, 「보유 부서」 라고 적은
    # 머리글이 값으로 읽힌다.
    by_key = {one["key"]: one for one in rows}
    assert "보유 부서" in by_key["workspace"]["aliases"]
    assert by_key["workspace"]["label"] in by_key["workspace"]["aliases"]

    # 서식의 머리글과 **같은 말**이어야 한다 — 서식을 보고 채운 사람이 표에서
    # 다른 이름을 보면 잘못 채운 줄 안다.
    template = client.get("/api/equipment/import/template", headers=admin.headers)
    head = template.content.decode("utf-8").splitlines()[0]
    for one in rows:
        assert one["label"] in head, f"서식에 없는 열 이름: {one['label']}"


def test_서버가_읽은_칸_값을_그대로_돌려준다(client: TestClient, admin: Signed) -> None:
    """화면이 다시 파싱하면 구분자 고르기·빈 줄 건너뛰기·머리글 별칭이 두 벌이 되고,
    두 벌은 반드시 어긋난다 — 그때 사람은 자기가 붙여넣은 것과 다른 표를 본다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"CELL-{uuid.uuid4().hex[:6]}"
    body = (
        HEADER.replace(",", "\t")
        + "\n"
        + "\t".join(
            [asset_no, "만능기", workspace, site, "3동, 201호", category, "", "가동", "예"]
        )
        + "\n"
    )
    row = _upload(client, admin, body)["rows"][0]
    cells = row["cells"]
    # 값 안의 쉼표가 그대로 살아 있어야 한다.
    assert cells["location"] == "3동, 201호"
    assert cells["asset_no"] == asset_no
    assert cells["site"] == site
    # 안 적은 칸도 **키는 온다** — 표가 빈 칸을 그리려면 열이 다 있어야 한다.
    assert cells["note"] == ""
    assert set(cells) == {
        one["key"]
        for one in client.get("/api/equipment/import/columns", headers=admin.headers).json()
    }


def test_축에_없는_값은_그_자리에서_만들_수_있다고_알려_준다(
    client: TestClient, admin: Signed
) -> None:
    """거점 「3공장」 이 아직 없다고 반입을 멈추면, 사람은 창을 닫고 기준정보로 가서
    만들고 돌아와 다시 붙여넣어야 한다 — 그 사이 표에서 고치던 것을 잃는다.

    **열린 축은 원래 누구나 더한다**(`entry_policy=open`). 여기서 막을 이유가 없다.
    다만 **반입이 스스로 만들지는 않는다** — 오타가 그대로 축이 되면 「본사」 와
    「본사 」 가 서로 다른 거점이 되고, 그 둘은 나중에 합칠 방법이 없다.
    """
    workspace, _site, category = _fixture(client, admin)
    fresh = f"3공장{uuid.uuid4().hex[:6]}"
    body = (
        f"{HEADER}\n"
        f"MAKE-{uuid.uuid4().hex[:6]},만능기,{workspace},{fresh},3동,{category},,가동,예\n"
    )
    row = _upload(client, admin, body)["rows"][0]
    said = next(one for one in row["problems"] if one["field"] == "site")
    assert said["make_axis"] == "site"
    assert said["make_value"] == fresh
    # 「먼저 만드세요」 라고 시키지 않는다 — 여기서 만들 수 있으니까.
    assert "먼저 만드세요" not in said["message"]

    # **반입이 만들지는 않았다.**
    terms = client.get("/api/vocabularies/site/terms", headers=admin.headers)
    assert fresh not in {one["value"] for one in terms.json()}

    # 사람이 만들면 그 다음 판정이 통과한다.
    made = client.post(
        "/api/vocabularies/site/terms", json={"value": fresh}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    assert _upload(client, admin, body)["ready"] == 1


def test_같은_이름이_여럿이면_만들라고_하지_않는다(client: TestClient, admin: Signed) -> None:
    """이미 있는데 하나로 못 정하는 것이다. 또 만들면 셋이 된다."""
    workspace, _site, category = _fixture(client, admin)
    body = (
        f"{HEADER}\n"
        f"DUPV-{uuid.uuid4().hex[:6]},만능기,{workspace},{category},3동,{category},,가동,예\n"
    )
    # 거점 자리에 분류 이름을 적었다 — 거점 축에는 없으므로 「만들 수 있다」 가 온다.
    row = _upload(client, admin, body)["rows"][0]
    said = next(one for one in row["problems"] if one["field"] == "site")
    assert said["make_axis"] == "site"


def test_카탈로그에_안_이어진_장비를_되찾을_수_있다(client: TestClient, admin: Signed) -> None:
    """**기종을 반입 창에서 만들게 하지 않는 대신** 이 길이 있어야 한다.

    기종은 전사 공용이라 시스템 관리자만 만들고, 계열이 먼저 있어야 하며, 사양 0칸
    기종을 만들면 그 장비는 조건 없이 복사되어 검색이 「모름」 으로 답한다. 그래서
    반입은 「비워 두세요」 라고 한다.

    그런데 비워 두면 그 장비는 검색에 안 걸린다. 「카탈로그에 그 기종이 없더라」 는
    사실이 반입한 사람 머릿속에만 남으면 그 장비는 영영 안 찾아진다 — 홈이 세고,
    목록이 거른다.
    """
    workspace, site, category = _fixture(client, admin)
    tag = uuid.uuid4().hex[:6]
    body = f"{HEADER}\nNOCAT-{tag},자작 치구,{workspace},{site},3동,{category},,가동,아니오\n"
    assert _upload(client, admin, body, dry_run=False)["created"] == 1

    listed = client.get("/api/equipment?catalog=unlinked&limit=200", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    found = {one["asset_no"] for one in listed.json()["items"]}
    assert f"NOCAT-{tag}" in found

    # 홈이 세는 수와 **같은 조건**이라야 그 줄을 눌러 온 사람이 같은 목록을 본다.
    rows = {
        one["key"]: one
        for one in client.get("/api/server/maintenance", headers=admin.headers).json()
    }
    said = rows["equipment_without_model"]
    assert said["link"] == "/equipment?catalog=unlinked"
    assert said["count"] == listed.json()["total"]


def _upsert(
    client: TestClient, admin: Signed, body: str, *, dry_run: bool = True
) -> dict[str, Any]:
    response = client.post(
        f"/api/equipment/import?dry_run={'true' if dry_run else 'false'}",
        json={"text": body, "update_existing": True},
        headers=admin.headers,
    )
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def test_갱신을_켜면_적힌_칸만_바꾼다(client: TestClient, admin: Signed) -> None:
    """부서는 엑셀 대장을 계속 굴린다. 300대 중 30대의 위치·상태가 바뀌었을 때 상세
    화면에서 30번 고치라는 것은 무리다.

    **빈 칸은 「비운다」 가 아니라 「안 건드린다」 다.** 엑셀에 비고를 안 적었다고 기존
    비고가 지워지면 그것은 갱신이 아니라 사고다.
    """
    workspace, site, category = _fixture(client, admin)
    asset_no = f"UPD-{uuid.uuid4().hex[:6]}"
    head = "자산번호,장비명,보유부서,거점,설치위치,장비유형,상태,비고"
    first = (
        f"{head}\n{asset_no},만능기,{workspace},{site},3동 201호,{category},가동,처음 비고\n"
    )
    assert _upload(client, admin, first, dry_run=False)["created"] == 1

    # 위치와 상태만 적고 나머지는 비웠다.
    later = f"자산번호,설치위치,상태\n{asset_no},4동 105호,유휴\n"
    preview = _upsert(client, admin, later)
    row = preview["rows"][0]
    assert row["exists"] is True
    assert row["problems"] == [], row
    # **무엇이 바뀌는지 칸마다 보인다** — 누르기 전에 잘못 붙은 열이 눈에 띈다.
    changed = {one["field"]: (one["before"], one["after"]) for one in row["changes"]}
    assert changed == {
        "location": ("3동 201호", "4동 105호"),
        "status": ("가동", "유휴"),
    }

    done = _upsert(client, admin, later, dry_run=False)
    assert done["updated"] == 1 and done["created"] == 0
    assert done["rows"][0]["imported"] is True

    got = client.get(f"/api/equipment?asset_no={asset_no}", headers=admin.headers).json()
    one = got["items"][0]
    assert one["location"] == "4동 105호"
    assert one["status"] == "idle"
    # 안 적은 칸은 그대로다.
    assert one["name"] == "만능기"
    assert one["note"] == "처음 비고"


def test_대장과_같으면_변경_없음으로_처리된다(client: TestClient, admin: Signed) -> None:
    """손댈 것이 없는 줄은 처리된 것으로 쳐서 표에서 사라진다 — 안 그러면 300줄 대장을
    다시 붙일 때마다 270줄이 「이미 등록」 으로 남아 무엇을 봐야 할지 가린다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"SAME-{uuid.uuid4().hex[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동,{category},,가동,예\n"
    assert _upload(client, admin, body, dry_run=False)["created"] == 1

    again = _upsert(client, admin, body, dry_run=False)
    assert again["unchanged"] == 1
    assert again["updated"] == 0
    assert again["rows"][0]["changes"] == []
    assert again["rows"][0]["imported"] is True


def test_갱신으로는_기종을_못_바꾼다(client: TestClient, admin: Signed) -> None:
    """기종을 바꾸면 시험 항목이 다시 복사되지 않아 조건이 옛 기종의 것으로 남는다.
    대장 갱신으로 **조용히** 일어나면 안 되는 일이라, 다르게 적혀 있으면 막고
    상세에서 하라고 말한다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"LOCK-{uuid.uuid4().hex[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동,{category},,가동,예\n"
    assert _upload(client, admin, body, dry_run=False)["created"] == 1

    tag = uuid.uuid4().hex[:8]
    series = client.post(
        "/api/equipment-series", json={"name": f"계열{tag}"}, headers=admin.headers
    )
    made = client.post(
        "/api/equipment-models",
        json={"series_id": series.json()["id"], "name": f"기종{tag}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    relinked = f"자산번호,기종\n{asset_no},기종{tag}\n"
    row = _upsert(client, admin, relinked)["rows"][0]
    assert "model" in _fields(row), row
    assert any("상세" in one for one in _said(row))


def test_갱신을_안_켜면_여전히_거절한다(client: TestClient, admin: Signed) -> None:
    """덮어쓰기는 **명시적으로 켜야** 한다. 기본이 갱신이면 다른 부서의 옛 대장을 실수로
    붙인 사람이 남의 장비 위치를 바꾼다."""
    workspace, site, category = _fixture(client, admin)
    asset_no = f"NOUP-{uuid.uuid4().hex[:6]}"
    body = f"{HEADER}\n{asset_no},만능기,{workspace},{site},3동,{category},,가동,예\n"
    assert _upload(client, admin, body, dry_run=False)["created"] == 1
    again = _upload(client, admin, body)
    assert again["rows"][0]["exists"] is True
    assert any("이미 등록" in one for one in _said(again["rows"][0]))
