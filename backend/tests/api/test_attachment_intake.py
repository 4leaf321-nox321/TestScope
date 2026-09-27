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
