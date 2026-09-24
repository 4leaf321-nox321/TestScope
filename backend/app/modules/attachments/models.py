"""그림과 첨부 — **파일은 한 벌, 붙는 자리는 여럿.**

사내 시험 카드에는 그림이 들어가는데 **어느 칸에 붙는지가 문서마다 다르다.** 칸마다 그림
칸을 만들면 대부분 빈 칸으로 서고, 새 자리가 생길 때마다 스키마가 바뀐다 — 그래서 붙는
자리를 데이터로 받는다(속성 모듈과 같은 판단).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 첨부를 붙일 수 있는 대상. **속성(`AttributeDefinition.target`)과 같은 말**을 쓴다 —
#: 그림이 속성 칸을 가리키므로 두 말이 갈리면 어느 칸인지 못 찾는다.
#: 파일이 붙는 대상.
#:
#: `method` 는 **규격서 원문**이 붙는 자리다. 601건 중 원문을 가진 것이 19건뿐이라
#: 「이 규격으로 시험하려면 어떤 장비가 필요한가」(요구 조건)를 채울 재료가 없었다.
#:
#: `spec_document` 는 **사내 규격서**의 파일이다 — 원본과 개정본이 함께 붙는다.
#: 공개 규격(`method`)과 다른 표인 이유는 `documents/models.py` 머리말에 있다.
ATTACHMENT_TARGETS = ("reliability_test", "method", "spec_document")

#: 받는 형식. 스캔본이 PDF 로 오는 일이 많아 그림만 받지 않고, **사내 규격서는 원본이
#: 한글·워드·엑셀로 오는 일이 흔해서** 그것도 받는다.
#:
#: **보여 주지는 않는다.** 브라우저는 이 형식들을 못 그리고, MS·구글의 온라인 뷰어는
#: 파일이 인터넷에 공개돼 있어야 해서 사내망에서는 원리상 못 쓴다. 받아 두고 내려받게
#: 하는 것이 지금의 답이다 — 화면이 그렇게 말한다.
ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "application/pdf": "pdf",
    # 문서 — 여는 것은 사람의 프로그램이다.
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/msword": "doc",
    "application/vnd.ms-excel": "xls",
    "application/vnd.ms-powerpoint": "ppt",
    "application/haansofthwp": "hwp",
    "application/x-hwp": "hwp",
    "application/vnd.hancom.hwp": "hwp",
    "application/hwp+zip": "hwpx",
}

#: 형식을 **이름으로도** 본다.
#:
#: 브라우저는 형식을 OS 에서 읽어 오는데, 한글(.hwp)처럼 그 PC 에 프로그램이 없으면
#: 빈 값이나 `application/octet-stream` 을 보낸다 — 형식만 보면 정작 받아야 할 사내
#: 규격서가 거절된다. 그래서 **형식을 모를 때만** 확장자를 본다. 아는 형식이 오면
#: 그것이 우선이다(이름은 누구나 바꿀 수 있다).
GENERIC_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})


def _by_extension() -> dict[str, str]:
    """확장자 → 대표 형식. 같은 확장자가 여럿이면 **먼저 적힌 것**이 대표다(hwp 는 셋)."""
    out: dict[str, str] = {}
    for mime, extension in ALLOWED_TYPES.items():
        out.setdefault(extension, mime)
    out["jpeg"] = "image/jpeg"
    return out


#: 확장자 → 형식. **모르고 온 것에 문 앞에서 이름을 붙여 준다.**
#:
#: 안 붙여 주면 `application/octet-stream` 이 그대로 저장되고, 그 뒤로는 그 줄을 보고
#: 무엇인지 알 길이 없다 — 화면은 「무엇으로 열라」 고 말하지 못하고, 브라우저가 못 그리는
#: 것을 `<img>` 로 그리려다 깨진 그림을 보인다. 판정은 문 앞에서 한 번 한다.
EXTENSION_TYPES = _by_extension()
ALLOWED_EXTENSIONS = frozenset(EXTENSION_TYPES)

#: 장당 한계. 넘으면 413 이 아니라 422 로 **무엇이 문제인지 말해서** 거절한다.
#:
#: 100 MB 다. ASTM·ISO 원문은 2~5 MB 지만 **사내 규격서 스캔본이 20~50 MB 로 흔하다** —
#: 10 MB 로 두면 정작 올리고 싶은 문서가 막힌다. 라우트가 이 한계까지만 읽으므로 1 GB 를
#: 보내도 메모리에 다 올라가지는 않는다.
MAX_BYTES = 100 * 1024 * 1024


class StoredFile(Base):
    """파일 한 벌. **내용이 곧 이름이다**(`sha256`).

    같은 그림이 여러 시험에 붙는다 — 표준 치구 사진, 합격 예시. 붙을 때마다 파일을 쓰면
    같은 그림이 수십 벌 쌓이고 백업이 그만큼 커진다. 내용이 같으면 이 줄 하나를 함께 쓴다.

    지우는 것은 **붙은 줄이 0 이 됐을 때뿐**이다(`attachments` 의 외래키가 RESTRICT).
    남의 시험에 붙어 있는 그림을 내가 지우면 그쪽 카드가 깨진다.
    """

    __tablename__ = "stored_files"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    path: Mapped[str] = mapped_column(String(300))
    """파일스토어 아래의 상대 경로. **DB 에는 경로와 해시만 둔다**(config 의 약속)."""
    content_type: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Attachment(Base):
    """그림 한 장이 **어디에** 붙었나."""

    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_object", "target", "object_id"),
        Index("ix_attachments_file", "file_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target: Mapped[str] = mapped_column(String(20))
    object_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))

    definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("attribute_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    """어느 칸에 붙나. **비울 수 있다** — 아무 칸에도 안 붙는 그림이 실제로 있다(부록·전경
    사진). 칸이 지워지면 그림은 카드 전체로 내려온다(SET NULL): 칸을 지웠다고 그림까지
    사라지면 사람은 그것을 사고로 읽는다."""

    file_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT")
    )
    original_name: Mapped[str] = mapped_column(String(255))
    """올린 사람이 쓰던 이름. **파일이 아니라 붙은 줄이 갖는다** — 같은 그림을 다른 이름으로
    올릴 수 있고, 내려받을 때 그 이름으로 준다."""

    caption: Mapped[str] = mapped_column(String(300), default="", server_default="")
    """무엇을 찍은 그림인가. **MCP 는 그림을 못 본다** — AI 가 읽는 것은 이 글자뿐이라,
    설명 없는 그림은 AI 에게 없는 것과 같다."""

    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
