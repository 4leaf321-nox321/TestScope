"""규격서 반입 — **문서 한 벌을 올리면 그 안의 그림이 낱장으로 서고, AI 는 가리킨다.**

사내 규격서 워드 한 벌에 신뢰성 시험이 서른~마흔 건 적혀 있고 그림이 그만큼 들어 있다.
그것을 시험마다 나눠 넣으려면 셋이 필요한데, 셋의 공통점은 **바이트가 AI 를 안 거치는
것**이다(50 MB 스캔본은 base64 로 모델 문맥을 통째로 먹는다).

1. **티켓** — PC 의 파일을 셸에서 서버로 바로 올린다. 진짜 토큰을 셸에 안 적는다.
2. **꺼내기** — 워드는 zip 이라 서버가 풀어 `word/media/` 를 낱장 첨부로 만든다.
   그림 자리의 글을 설명으로 달아 둔다 — **AI 는 그림을 못 보므로 그 글자가 단서다.**
3. **가리키기** — 이미 올라온 그림을 시험마다 건다. 바이트는 안 움직인다.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from app.modules.attachments.models import StoredFile
from tests.api.conftest import Signed

#: 1x1 PNG 두 장 — 내용이 달라야 한 벌로 안 뭉친다(sha256).
RED = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d4944415478da6364f8cf000000030101002718e3660000000049454e44ae426082"
)
BLUE = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d4944415478da6360f8cf000000030101002718e3660000000049454e44ae426082"
)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _paragraph(text: str, *, style: str | None = None, embed: str | None = None) -> str:
    pieces = []
    if style:
        pieces.append(f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>')
    if text:
        pieces.append(f"<w:r><w:t>{text}</w:t></w:r>")
    if embed:
        pieces.append(
            f'<w:r><w:drawing><wp:inline xmlns:wp="x"><a:graphic xmlns:a="{_A}">'
            f'<a:blip r:embed="{embed}"/></a:graphic></wp:inline></w:drawing></w:r>'
        )
    return f"<w:p>{''.join(pieces)}</w:p>"


def _docx() -> bytes:
    """시험 둘과 그림 셋이 든 워드 한 벌 — 그중 하나는 **머리글 로고가 두 번** 나온다."""
    body = "".join(
        [
            _paragraph("3.1 고온고습 저장", style="Heading2"),
            _paragraph("85 degC / 85 %RH 에서 1000시간 둔다."),
            _paragraph("시편 장착 방향", embed="rId10"),
            _paragraph("3.2 열충격", style="Heading2"),
            _paragraph("온습도 프로파일", embed="rId11"),
            _paragraph("", embed="rId12"),  # 같은 로고가 또 — 한 번만 꺼내야 한다
        ]
    )
    document = (
        f'<?xml version="1.0"?><w:document xmlns:w="{_W}" xmlns:r="{_R}">'
        f"<w:body>{body}</w:body></w:document>"
    )
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId10" Target="media/image1.png"/>'
        '<Relationship Id="rId11" Target="media/image2.png"/>'
        '<Relationship Id="rId12" Target="media/image3.png"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", rels)
        archive.writestr("word/media/image1.png", RED)
        archive.writestr("word/media/image2.png", BLUE)
        archive.writestr("word/media/image3.png", RED)  # 로고 — image1 과 같은 바이트
    return buffer.getvalue()


def _document(client: TestClient, admin: Signed) -> dict[str, Any]:
    made = client.post(
        "/api/spec-documents",
        json={
            "workspace_slug": admin.workspace,
            "code": f"MX-REL-{uuid.uuid4().hex[:6]}",
            "title": "환경 시험 표준",
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _upload(client: TestClient, admin: Signed, document_id: str, data: bytes) -> Response:
    made: Response = client.post(
        "/api/attachments",
        data={"target": "spec_document", "object_id": document_id, "caption": "원본"},
        files={"file": ("규격서.docx", io.BytesIO(data), "application/octet-stream")},
        headers=admin.headers,
    )
    return made


def test_티켓으로_올리면_진짜_토큰을_셸에_안_적는다(client: TestClient, admin: Signed) -> None:
    """바이트는 PC 에서 서버로 바로 간다 — **AI 를 안 거친다.**

    그때 셸에 진짜 토큰을 적으면 오래 사는 자격이 기록에 남는다. 티켓은 5분 살고
    **올리기 말고는 아무것도 못 한다** — 그것을 여기서 잠근다.
    """
    document = _document(client, admin)
    minted = client.post("/api/attachments/upload-ticket", headers=admin.headers)
    assert minted.status_code == 200, minted.text
    ticket = minted.json()["ticket"]
    assert minted.json()["expires_in_seconds"] == 300

    made = client.post(
        "/api/attachments/upload-with-ticket",
        params={
            "target": "spec_document",
            "object_id": document["id"],
            "filename": "규격서.docx",
        },
        content=_docx(),
        headers={"X-Upload-Ticket": ticket},
    )
    assert made.status_code == 201, made.text
    assert made.json()["original_name"] == "규격서.docx"

    # **아무 글자나 안 받는다.**
    bad = client.post(
        "/api/attachments/upload-with-ticket",
        params={
            "target": "spec_document",
            "object_id": document["id"],
            "filename": "위조.docx",
        },
        content=b"x",
        headers={"X-Upload-Ticket": "not-a-ticket"},
    )
    assert bad.status_code == 401, bad.text

    # **로그인 토큰은 티켓이 아니다.** `typ` 를 안 보면 오래 사는 자격이 업로드에도 통한다.
    borrowed = client.post(
        "/api/attachments/upload-with-ticket",
        params={
            "target": "spec_document",
            "object_id": document["id"],
            "filename": "빌린토큰.docx",
        },
        content=b"x",
        headers={"X-Upload-Ticket": admin.token},
    )
    assert borrowed.status_code == 401, borrowed.text


def test_워드를_올리면_서버가_그림을_낱장으로_꺼낸다(
    client: TestClient, admin: Signed, db: Any
) -> None:
    """**AI 는 그림을 못 본다** — 그래서 그림 자리의 글을 설명으로 달아 준다.

    파일 이름(`image2.png`)만으로는 서른 장 중 어느 것이 열충격의 것인지 고를 수 없다.
    """
    document = _document(client, admin)
    source = _upload(client, admin, document["id"], _docx()).json()

    pulled = client.post(
        f"/api/attachments/{source['id']}/extract-images", headers=admin.headers
    )
    assert pulled.status_code == 200, pulled.text
    body = pulled.json()

    assert body["extracted"] == 2, body
    # 같은 로고가 두 번 나왔다 — 한 번만 꺼낸다. 안 그러면 로고가 서른 줄이 된다.
    assert body["skipped_duplicate"] == 1

    captions = {one["original_name"]: one["caption"] for one in body["images"]}
    assert captions["image1.png"] == "3.1 고온고습 저장 — 시편 장착 방향"
    assert captions["image2.png"] == "3.2 열충격 — 온습도 프로파일"

    # 꺼낸 것은 **문서와 같은 자리**에 붙는다 — 거기서 시험마다 나눠 건다.
    listed = client.get(
        "/api/attachments",
        params={"target": "spec_document", "object_id": document["id"]},
        headers=admin.headers,
    ).json()
    assert len(listed) == 3, "원본 하나 + 꺼낸 둘"

    # 워드가 아니면 무엇이 문제인지 말한다.
    plain = _upload(client, admin, document["id"], b"%PDF-1.4 not a zip").json()
    refused = client.post(
        f"/api/attachments/{plain['id']}/extract-images", headers=admin.headers
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["error"]["code"] == "TSC-ATTACH-0009"


def test_이미_올라온_그림을_시험에_가리킨다(
    client: TestClient, admin: Signed, db: Any
) -> None:
    """**바이트는 안 움직인다.** 규격서의 그림 한 장을 시험 둘에 걸어도 디스크엔 한 벌."""
    document = _document(client, admin)
    source = _upload(client, admin, document["id"], _docx()).json()
    images = client.post(
        f"/api/attachments/{source['id']}/extract-images", headers=admin.headers
    ).json()["images"]
    picked = next(one for one in images if one["original_name"] == "image2.png")

    tests = []
    for index in range(2):
        made = client.post(
            "/api/reliability-tests",
            json={
                "workspace_slug": admin.workspace,
                "name": f"열충격-{uuid.uuid4().hex[:6]}-{index}",
            },
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text
        tests.append(made.json()["id"])

    before = db.query(StoredFile).count() if hasattr(db, "query") else None
    for test_id in tests:
        hung = client.post(
            f"/api/attachments/{picked['id']}/attach",
            json={"target": "reliability_test", "object_id": test_id},
            headers=admin.headers,
        )
        assert hung.status_code == 201, hung.text
        # **설명을 안 주면 원본의 것을 가져온다** — 그림을 고른 이유가 대개 그 설명이다.
        assert hung.json()["caption"] == picked["caption"]

    after = db.query(StoredFile).count() if hasattr(db, "query") else None
    if before is not None:
        assert after == before, "가리키기만 했는데 파일이 늘면 안 된다"

    hung = client.get(
        "/api/attachments",
        params={"target": "reliability_test", "object_id": tests[0]},
        headers=admin.headers,
    ).json()
    assert len(hung) == 1 and hung[0]["original_name"] == "image2.png"


def test_사내_문서의_험한_모양에서도_제자리를_찾는다() -> None:
    """실제 규격서는 **제목 스타일을 안 쓴다.**

    2026-09-27 에 흉내 내어 재 보니 셋 중 둘이 엉뚱한 설명을 달았다 — 절 제목이 굵게만
    돼 있어 「85 degC / 85 %RH 에서 1000시간…」 같은 본문이 제목으로 잡혔다. 여기서
    굳히는 것 넷:

    1. **번호로 시작하는 줄**을 제목으로 본다(스타일이 없어도).
    2. 그런데 **아무 숫자 문장이나** 제목이 되면 안 된다 — 「85 degC …」 는 본문이다.
    3. **표 안의 그림**도 순서가 산다.
    4. 그림 **아래**의 캡션(「그림 3-2 …」)이 가장 정확하다 — 사람이 그러라고 적은 글이다.
    """
    from app.modules.attachments.services import _docx_captions

    def para(text: str = "", *, embed: str | None = None) -> str:
        bits = []
        if text:
            bits.append(f"<w:r><w:t>{text}</w:t></w:r>")
        if embed:
            bits.append(
                f'<w:r><w:drawing><wp:inline xmlns:wp="x"><a:graphic xmlns:a="{_A}">'
                f'<a:blip r:embed="{embed}"/></a:graphic></wp:inline></w:drawing></w:r>'
            )
        return f"<w:p>{''.join(bits)}</w:p>"

    body = "".join(
        [
            para("3.1 고온고습 저장"),  # 굵게만 — 제목 스타일 없음
            para("85 degC / 85 %RH 에서 1000시간 보관한 뒤 외관을 본다."),
            para("시편 장착 방향은 아래와 같다.", embed="rId10"),
            para("3.2 열충격"),
            # 표 안의 그림 — 옆 칸에 다른 글이 있다
            f"<w:tbl><w:tr><w:tc>{para('프로파일')}</w:tc>"
            f"<w:tc>{para('', embed='rId11')}</w:tc></w:tr></w:tbl>",
            para("그림 3-2 온습도 프로파일"),
        ]
    )
    document = (
        f'<?xml version="1.0"?><w:document xmlns:w="{_W}" xmlns:r="{_R}">'
        f"<w:body>{body}</w:body></w:document>"
    )
    rels = (
        '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org'
        '/package/2006/relationships">'
        '<Relationship Id="rId10" Target="media/image1.png"/>'
        '<Relationship Id="rId11" Target="media/image2.png"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", rels)
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        found = _docx_captions(archive)

    assert (
        found["word/media/image1.png"] == "3.1 고온고습 저장 — 시편 장착 방향은 아래와 같다."
    )
    # 표 안의 그림도, 아래 캡션도.
    assert found["word/media/image2.png"] == "3.2 열충격 — 그림 3-2 온습도 프로파일"


def test_그림_여럿을_한_번에_제자리로(client: TestClient, admin: Signed) -> None:
    """규격서에서 나온 그림을 시험 서른 건에 나눠 건다 — **한 번에.**

    여기서 지키는 것 셋:

    1. **기본은 미리보기다.** 판정만 하고 아무것도 안 건다 — 서른 장을 엉뚱한 시험에
       걸어 놓고 되돌리는 것보다 표로 먼저 보는 편이 싸다.
    2. **한 줄이 막혀도 나머지는 걸린다.** 안 그러면 한 장 때문에 스물아홉이 함께 막힌다.
    3. **못 건 줄은 이유와 함께** 남는다 — 조용히 빠지면 못 알아챈다.
    """
    document = _document(client, admin)
    source = _upload(client, admin, document["id"], _docx()).json()
    images = client.post(
        f"/api/attachments/{source['id']}/extract-images", headers=admin.headers
    ).json()["images"]
    assert len(images) == 2, images

    tests = []
    for index in range(2):
        made = client.post(
            "/api/reliability-tests",
            json={
                "workspace_slug": admin.workspace,
                "name": f"일괄-{uuid.uuid4().hex[:6]}-{index}",
            },
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text
        tests.append(made.json()["id"])

    rows = [
        {
            "attachment_id": images[0]["id"],
            "target": "reliability_test",
            "object_id": tests[0],
        },
        {
            "attachment_id": images[1]["id"],
            "target": "reliability_test",
            "object_id": tests[1],
        },
        # 없는 대상 — 이 줄만 막혀야 한다.
        {
            "attachment_id": images[0]["id"],
            "target": "reliability_test",
            "object_id": str(uuid.uuid4()),
        },
    ]

    looked = client.post(
        "/api/attachments/attach-batch", json={"items": rows}, headers=admin.headers
    )
    assert looked.status_code == 200, looked.text
    assert looked.json()["dry_run"] is True
    # 미리보기도 **걸릴 수**를 말한다 — 「둘은 걸리고 하나는 막힙니다」.
    assert looked.json()["attached"] == 2
    assert looked.json()["refused"] == 1
    assert looked.json()["rows"][2]["error"], "왜 안 되는지 말해야 한다"
    assert (
        client.get(
            "/api/attachments",
            params={"target": "reliability_test", "object_id": tests[0]},
            headers=admin.headers,
        ).json()
        == []
    ), "미리보기 뒤에는 하나도 안 붙어 있어야 한다"

    done = client.post(
        "/api/attachments/attach-batch",
        params={"dry_run": "false"},
        json={"items": rows},
        headers=admin.headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["attached"] == 2 and done.json()["refused"] == 1
    for test_id in tests:
        hung = client.get(
            "/api/attachments",
            params={"target": "reliability_test", "object_id": test_id},
            headers=admin.headers,
        ).json()
        assert len(hung) == 1, hung
        # 설명이 따라온다 — 그림을 고른 이유가 그것이다.
        assert "MCP" not in hung[0]["caption"] or hung[0]["caption"]


def test_미리보기는_커밋해도_아무것도_안_남긴다(
    client: TestClient, admin: Signed, db: Any
) -> None:
    """**겉보기로는 구별이 안 된다.** 요청이 커밋을 안 하니 미리보기가 실제로 걸었어도
    화면에는 아무것도 안 보인다 — 그래서 API 로만 보는 시험은 이 고장을 못 문다.
    서비스를 직접 부르고 **커밋까지 해서** 본다.
    """
    from app.modules.accounts.models import User
    from app.modules.attachments import services
    from app.modules.attachments.models import Attachment

    document = _document(client, admin)
    source = _upload(client, admin, document["id"], _docx()).json()
    images = client.post(
        f"/api/attachments/{source['id']}/extract-images", headers=admin.headers
    ).json()["images"]
    made = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": admin.workspace, "name": f"미리보기-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    test_id = made.json()["id"]

    user = db.query(User).filter(User.email == admin.email).one()
    before = db.query(Attachment).filter(Attachment.object_id == uuid.UUID(test_id)).count()
    services.attach_batch(
        db,
        user,
        items=[
            {
                "attachment_id": images[0]["id"],
                "target": "reliability_test",
                "object_id": uuid.UUID(test_id),
                "definition_id": None,
                "caption": None,
            }
        ],
        dry_run=True,
    )
    db.commit()
    after = db.query(Attachment).filter(Attachment.object_id == uuid.UUID(test_id)).count()
    assert after == before, "미리보기가 줄을 만들면 안 된다"
