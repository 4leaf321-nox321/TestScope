"""첨부를 넣고·읽고·지운다.

## 파일은 내용으로 모은다

같은 그림이 여러 시험에 붙는다. 올라온 바이트의 `sha256` 이 같으면 **파일을 다시 쓰지
않고** 있는 줄을 함께 쓴다 — 표준 치구 사진 한 장이 시험 서른에 붙어도 디스크에는 한 벌이다.

## 지우는 것은 붙은 줄이고, 파일은 그 뒤에 따라 지워진다

붙은 줄을 지우고 **그 파일을 가리키는 줄이 0 이면** 그때 파일을 지운다. 남의 시험에
붙어 있는 그림을 내가 지우면 그쪽 카드가 깨진다.

## 권한은 대상이 정한다

「이 그림을 넣어도 되나」 는 「이 시험을 고쳐도 되나」 와 같은 물음이다 — 그래서 여기서
따로 판정하지 않고 **대상 모듈의 판정을 부른다.** 두 벌이면 그림만 넣을 수 있는 사람이
생긴다.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
import time
import uuid
import xml.etree.ElementTree as ElementTree
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.accounts.models import User
from app.modules.attachments.models import (
    ALLOWED_EXTENSIONS,
    ALLOWED_TYPES,
    ATTACHMENT_TARGETS,
    EXTENSION_TYPES,
    GENERIC_TYPES,
    MAX_BYTES,
    Attachment,
    StoredFile,
)
from app.modules.attributes.models import AttributeDefinition
from app.shared.errors import AppError, Forbidden, NotFound
from app.shared.text import clean


def _check_target(target: str) -> None:
    if target not in ATTACHMENT_TARGETS:
        raise AppError(
            "TSC-ATTACH-0001",
            f"첨부를 붙일 수 없는 대상입니다: {target}",
            details={"targets": list(ATTACHMENT_TARGETS)},
        )


def require_can_edit(db: Session, user: User, *, target: str, object_id: uuid.UUID) -> None:
    """이 대상을 고칠 수 있나 — **대상 모듈의 판정을 그대로 부른다.**

    첨부만의 권한 규칙을 여기 두면 두 벌이 되고, 그때 「시험은 못 고치는데 그림은 붙는」
    사람이 생긴다. 대상이 늘면 여기 한 줄을 더한다.
    """
    _check_target(target)
    if target == "reliability_test":
        # 순환 import 를 피한다 — 신뢰성 모듈이 첨부를 읽는다(카드에 그림을 실으려고).
        from app.modules.reliability import services as reliability

        reliability.require_editable(db, user, object_id)
    elif target == "method":
        # **규격서는 시스템 관리자만 올린다.** 규격은 전사 공용이고 그 원문은 여러 부서가
        # 함께 보는 것이라, 한 부서가 올린 판이 전사의 근거가 되면 안 된다. 부서가 가진
        # 규격(사내 시험법)도 같다 — 파일은 관리자를 거친다.
        from app.modules.methods.models import TestMethod

        row = db.get(TestMethod, object_id)
        if row is None or row.deleted_at is not None:
            raise NotFound("TSC-METHODS-0001", "규격을 찾을 수 없습니다.")
        if not user.is_system_admin:
            raise Forbidden(
                "TSC-ATTACH-0006",
                "공개 규격의 원문은 시스템 관리자만 올리고 지웁니다.",
            )
    elif target == "spec_document":
        # 사내 규격서는 **그 부서**가 만들고 고친다 — 시스템 관리자를 거치게 하면
        # 문서가 안 올라온다(신뢰성 시험과 같은 규칙).
        from app.modules.documents import services as documents

        documents.require_editable(db, user, object_id)


def _resolve_type(content_type: str, filename: str) -> str | None:
    """받을 형식인가, 받는다면 **무엇이라 적어 둘 것인가.** 못 받으면 `None`.

    **형식을 모를 때만 이름을 본다.** 브라우저는 형식을 OS 에서 읽어 오는데, 한글(.hwp)
    처럼 그 PC 에 프로그램이 없으면 빈 값이나 `application/octet-stream` 을 보낸다 —
    형식만 보면 정작 받아야 할 사내 규격서가 거절된다. 아는 형식이 오면 그것이 우선이다
    (이름은 누구나 바꿀 수 있다).

    모르고 온 것에는 **여기서 이름을 붙인다.** 그대로 저장하면 그 뒤로는 그 줄을 보고
    무엇인지 알 길이 없어서, 화면이 「한글로 여십시오」 라고 말하지 못한다.
    """
    if content_type in ALLOWED_TYPES:
        return content_type
    if content_type.lower() not in GENERIC_TYPES:
        return None
    suffix = Path(filename).suffix.lstrip(".").lower()
    return EXTENSION_TYPES.get(suffix)


def _store(data: bytes, content_type: str) -> tuple[str, Path]:
    """바이트를 파일스토어에 둔다. 이미 있으면 안 쓴다. (sha256, 상대 경로)."""
    digest = hashlib.sha256(data).hexdigest()
    # 한 폴더에 수만 개가 쌓이면 파일 탐색기부터 느려진다 — 앞 두 자로 가른다.
    relative = Path(digest[:2]) / digest
    full = get_settings().filestore_dir / relative
    if not full.exists():
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
    return digest, relative


def add(
    db: Session,
    user: User,
    *,
    target: str,
    object_id: uuid.UUID,
    filename: str,
    content_type: str,
    data: bytes,
    definition_id: uuid.UUID | None = None,
    caption: str = "",
) -> Attachment:
    """그림 한 장을 붙인다. 커밋은 부르는 쪽이 한다."""
    require_can_edit(db, user, target=target, object_id=object_id)
    resolved = _resolve_type(content_type, filename)
    if resolved is None:
        raise AppError(
            "TSC-ATTACH-0002",
            f"받을 수 없는 형식입니다: {content_type or '(모름)'}",
            details={"allowed": sorted(ALLOWED_EXTENSIONS)},
            status=422,
        )
    if not data:
        raise AppError("TSC-ATTACH-0003", "빈 파일입니다.", status=422)
    if len(data) > MAX_BYTES:
        raise AppError(
            "TSC-ATTACH-0004",
            f"한 장에 {MAX_BYTES // 1024 // 1024} MB 까지입니다 "
            f"(올린 것은 {len(data) / 1024 / 1024:.1f} MB).",
            status=422,
        )
    if definition_id is not None:
        definition = db.get(AttributeDefinition, definition_id)
        if definition is None or definition.target != target:
            raise AppError(
                "TSC-ATTACH-0005",
                "그 칸은 이 대상의 칸이 아닙니다.",
                status=422,
            )

    digest, relative = _store(data, resolved)
    stored = db.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
    if stored is None:
        stored = StoredFile(
            sha256=digest,
            path=str(relative).replace("\\", "/"),
            content_type=resolved,
            bytes=len(data),
        )
        db.add(stored)
        db.flush()

    last = (
        db.scalar(
            select(func.max(Attachment.sort_order)).where(
                Attachment.target == target, Attachment.object_id == object_id
            )
        )
        or 0
    )
    row = Attachment(
        target=target,
        object_id=object_id,
        definition_id=definition_id,
        file_id=stored.id,
        original_name=clean(filename)[:255] or "이름 없음",
        caption=clean(caption)[:300],
        sort_order=last + 1,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def attach_existing(
    db: Session,
    user: User,
    *,
    source: Attachment,
    target: str,
    object_id: uuid.UUID,
    definition_id: uuid.UUID | None = None,
    caption: str | None = None,
) -> Attachment:
    """이미 올라온 파일을 **다른 자리에도 가리킨다.** 바이트는 안 움직인다.

    파일은 내용으로 모여 있으므로(sha256) 붙는 줄만 하나 더 만들면 된다 — 규격서 하나에
    올린 그림 서른 장을 시험 서른 건에 나눠 거는 일이 이 길로 된다. 그림을 다시 올리게
    하면 같은 바이트가 서른 벌 생기고, 무엇보다 **그 바이트가 AI 를 거쳐야** 한다.

    권한은 **가는 쪽**이 정한다(`require_can_edit`) — 보는 것은 누구나 하므로 원본 쪽에
    따로 묻지 않는다. 설명을 안 주면 원본의 것을 그대로 가져온다: 그림을 고른 이유가
    대개 그 설명이라, 비워 두면 받는 쪽에서 무엇인지 알 수 없다.
    """
    require_can_edit(db, user, target=target, object_id=object_id)
    if definition_id is not None:
        definition = db.get(AttributeDefinition, definition_id)
        if definition is None or definition.target != target:
            raise AppError("TSC-ATTACH-0005", "그 칸은 이 대상의 칸이 아닙니다.", status=422)

    last = (
        db.scalar(
            select(func.max(Attachment.sort_order)).where(
                Attachment.target == target, Attachment.object_id == object_id
            )
        )
        or 0
    )
    row = Attachment(
        target=target,
        object_id=object_id,
        definition_id=definition_id,
        file_id=source.file_id,
        original_name=source.original_name,
        caption=clean(caption)[:300] if caption is not None else source.caption,
        sort_order=last + 1,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


#: 오피스 문서 안에서 그림이 사는 곳. 확장자가 아니라 **압축 안의 경로**로 가른다.
_MEDIA_DIRS = ("word/media/", "ppt/media/", "xl/media/")

#: 한 번에 꺼낼 수 있는 장수와 장당 크기. 없으면 200쪽짜리 문서가 서버를 채운다.
_MAX_IMAGES = 200
_MAX_IMAGE_BYTES = 20 * 1024 * 1024

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"


#: 번호로 시작하는 절 제목 — 「3.1 고온고습 저장」 「3.1.2 …」 「4. 판정」.
#:
#: **스타일만 보면 못 찾는다.** 사내 문서는 제목 스타일 없이 굵게만 쓰는 일이 흔하고,
#: 그러면 그림에 붙는 설명이 「…아래와 같다.」 가 되어 어느 시험의 것인지 알 수 없다
#: (실측 2026-09-27: 흉내 낸 규격서에서 셋 중 둘이 그랬다).
#: 「3.1 …」 처럼 **여러 단**이거나, 「4. …」 처럼 **문장부호가 붙은** 것만 제목으로 본다.
#: 느슨하게 잡으면 「85 degC / 85 %RH 에서 1000시간…」 같은 본문이 제목이 되어, 그림에
#: 엉뚱한 설명이 붙는다(실측 2026-09-27).
_SECTION = re.compile(r"^\s*(?:\d+(?:[.-]\d+)+\s+\S|\d+(?:[.-]\d+)*\s*[.)]\s+\S)")

#: 그림 **아래**에 붙는 캡션 — 「그림 3-1 시편 장착」 「Figure 2. Profile」.
_FIGURE = re.compile(r"^\s*(그림|사진|도면|figure|fig\.?|table|표)\s", re.IGNORECASE)

_VML = "{urn:schemas-microsoft-com:vml}"


def _text_of(paragraph: Any) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{_W}t")).strip()


def _embeds_of(paragraph: Any) -> list[str]:
    """이 문단이 가리키는 그림의 관계 id. **옛 모양(VML)도 본다** — 한글에서 옮긴 문서에
    흔하다."""
    found = [
        one.get(f"{_R}embed") for one in paragraph.iter(f"{_A}blip") if one.get(f"{_R}embed")
    ]
    found += [
        one.get(f"{_R}id") for one in paragraph.iter(f"{_VML}imagedata") if one.get(f"{_R}id")
    ]
    return [one for one in found if one]


def _docx_captions(archive: zipfile.ZipFile) -> dict[str, str]:
    """그림마다 **문서에서 그 자리의 글**을 뽑는다 — `word/media/image7.png` → 설명.

    **AI 는 그림을 못 본다.** 파일 이름만 있으면 서른 장 중 어느 것이 열충격 시험의
    것인지 고를 방법이 없다 — 이 글자가 유일한 단서다. 그래서 뜯는 쪽이 만들어야 할
    것은 이미지가 아니라 **이 목록**이다.

    설명은 「절 제목 — 그림 옆의 글」 로 만든다. 셋을 본다:

    * **절 제목**은 스타일(`Heading…`)이거나 **번호로 시작하는 줄**이다(`_SECTION`).
      사내 문서는 제목 스타일을 잘 안 쓴다.
    * **그림 옆의 글**은 같은 문단의 글, 없으면 **바로 아래 캡션**(「그림 3-1 …」),
      그것도 없으면 직전 문단.
    * 표 안의 그림도 같다 — 문단을 문서 순서로 훑으므로 표 안이든 밖이든 순서가 산다.
    """
    try:
        rels = ElementTree.fromstring(archive.read("word/_rels/document.xml.rels"))
        body = ElementTree.fromstring(archive.read("word/document.xml"))
    except (KeyError, ElementTree.ParseError):
        return {}

    target_of = {
        one.get("Id", ""): one.get("Target", "") for one in rels.iter(f"{_PKG}Relationship")
    }
    paragraphs = list(body.iter(f"{_W}p"))
    texts = [_text_of(one) for one in paragraphs]

    def _heading(index: int) -> bool:
        style = paragraphs[index].find(f"{_W}pPr/{_W}pStyle")
        if style is not None and (style.get(f"{_W}val") or "").lower().startswith(
            ("heading", "제목")
        ):
            return True
        text = texts[index]
        return bool(text) and len(text) <= 60 and bool(_SECTION.match(text))

    found: dict[str, str] = {}
    heading = ""
    previous = ""
    for index, paragraph in enumerate(paragraphs):
        embeds = _embeds_of(paragraph)
        if not embeds:
            if texts[index]:
                if _heading(index):
                    heading = texts[index]
                previous = texts[index]
            continue

        near = texts[index]
        if not near:
            # 바로 아래 줄이 캡션이면 그것이 가장 정확하다 — 사람이 그러라고 적은 글이다.
            for after in range(index + 1, min(index + 3, len(paragraphs))):
                if texts[after] and _FIGURE.match(texts[after]):
                    near = texts[after]
                    break
        near = near or previous
        parts = [one for one in (heading, near) if one]
        if len(parts) == 2 and parts[0] == parts[1]:
            parts = parts[:1]
        label = " — ".join(parts)[:300]
        for rid in embeds:
            name = target_of.get(rid, "").rsplit("/", 1)[-1]
            if name:
                found.setdefault(f"word/media/{name}", label)
    return found


def extract_images(db: Session, user: User, *, source: Attachment) -> dict[str, Any]:
    """올려 둔 오피스 문서에서 **그림을 낱장으로 꺼낸다.** 서버가 푼다.

    워드·파워포인트는 사실 zip 이라 `word/media/` 에 그림이 원본 그대로 들어 있다.
    **바이트가 AI 를 안 거치는 것이 요점이다** — 문서 한 벌만 올리면 그 안의 서른 장이
    서버 안에서 낱장 첨부가 되고, AI 는 그 id 와 설명만 보고 제자리에 건다.

    꺼낸 것은 **문서와 같은 자리**(같은 target/object)에 붙는다 — 규격서에 올린 문서면
    규격서에. 거기서 `attach_existing` 으로 시험마다 나눠 건다.

    같은 그림이 여러 쪽에 나오면(머리글의 로고) **한 번만 꺼낸다** — 안 그러면 로고가
    서른 줄이 되어 정작 볼 것을 가린다. 바이트는 어차피 한 벌이지만 줄은 는다.
    """
    require_can_edit(db, user, target=source.target, object_id=source.object_id)
    stored = db.get(StoredFile, source.file_id)
    if stored is None:
        raise NotFound("TSC-ATTACH-0007", "파일 기록이 없습니다.")
    full = get_settings().filestore_dir / stored.path
    if not full.exists():
        raise NotFound("TSC-ATTACH-0008", "파일이 파일스토어에 없습니다.")

    try:
        archive = zipfile.ZipFile(BytesIO(full.read_bytes()))
    except zipfile.BadZipFile as exc:
        raise AppError(
            "TSC-ATTACH-0009",
            "이 파일에서는 그림을 꺼낼 수 없습니다 — 워드·파워포인트·엑셀만 됩니다.",
            status=422,
        ) from exc

    captions = _docx_captions(archive)
    made: list[Attachment] = []
    seen: set[str] = set()
    skipped_big = 0
    skipped_kind = 0
    skipped_same = 0
    with archive:
        names = sorted(
            one
            for one in archive.namelist()
            if one.startswith(_MEDIA_DIRS) and not one.endswith("/")
        )
        for name in names:
            if len(made) >= _MAX_IMAGES:
                break
            data = archive.read(name)
            if len(data) > _MAX_IMAGE_BYTES:
                skipped_big += 1
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                skipped_same += 1
                continue
            plain = name.rsplit("/", 1)[-1]
            if _resolve_type("", plain) is None:
                # emf·wmf 처럼 브라우저가 못 그리는 것은 꺼내도 볼 수가 없다.
                skipped_kind += 1
                continue
            seen.add(digest)
            made.append(
                add(
                    db,
                    user,
                    target=source.target,
                    object_id=source.object_id,
                    filename=plain,
                    content_type="",
                    data=data,
                    caption=captions.get(name, ""),
                )
            )
    return {
        "source_attachment_id": source.id,
        "images": made,
        "extracted": len(made),
        "skipped_oversize": skipped_big,
        "skipped_kind": skipped_kind,
        "skipped_duplicate": skipped_same,
    }


def get(db: Session, attachment_id: uuid.UUID) -> Attachment:
    row = db.get(Attachment, attachment_id)
    if row is None:
        raise NotFound("TSC-ATTACH-0006", "첨부를 찾을 수 없습니다.")
    return row


def list_for(db: Session, *, target: str, object_id: uuid.UUID) -> list[Attachment]:
    _check_target(target)
    return list(
        db.scalars(
            select(Attachment)
            .where(Attachment.target == target, Attachment.object_id == object_id)
            .order_by(Attachment.sort_order, Attachment.created_at)
        )
    )


def update(
    db: Session, user: User, attachment_id: uuid.UUID, changes: dict[str, Any]
) -> Attachment:
    """설명과 붙는 자리를 고친다. **파일은 안 바꾼다** — 다른 그림이면 새로 붙인다."""
    row = get(db, attachment_id)
    require_can_edit(db, user, target=row.target, object_id=row.object_id)
    if "caption" in changes and changes["caption"] is not None:
        row.caption = clean(str(changes["caption"]))[:300]
    if "definition_id" in changes:
        definition_id = changes["definition_id"]
        if definition_id is not None:
            definition = db.get(AttributeDefinition, definition_id)
            if definition is None or definition.target != row.target:
                raise AppError(
                    "TSC-ATTACH-0005", "그 칸은 이 대상의 칸이 아닙니다.", status=422
                )
        row.definition_id = definition_id
    if "sort_order" in changes and changes["sort_order"] is not None:
        row.sort_order = int(changes["sort_order"])
    db.flush()
    return row


def remove(db: Session, user: User, attachment_id: uuid.UUID) -> None:
    row = get(db, attachment_id)
    require_can_edit(db, user, target=row.target, object_id=row.object_id)
    _drop(db, [row])


def remove_all(db: Session, *, target: str, object_id: uuid.UUID) -> int:
    """대상이 지워질 때 그 그림도 함께. **권한은 부르는 쪽이 이미 봤다.**"""
    rows = list_for(db, target=target, object_id=object_id)
    _drop(db, rows)
    return len(rows)


def _drop(db: Session, rows: list[Attachment]) -> None:
    """붙은 줄을 지우고, **그 파일을 가리키는 줄이 0 이면** 파일도 지운다."""
    file_ids = {row.file_id for row in rows}
    for row in rows:
        db.delete(row)
    db.flush()
    for file_id in file_ids:
        left = (
            db.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(Attachment.file_id == file_id)
            )
            or 0
        )
        if left:
            continue
        stored = db.get(StoredFile, file_id)
        if stored is None:
            continue
        full = get_settings().filestore_dir / stored.path
        # **파일을 먼저 지우고 줄을 지운다.** 반대로 하면 줄은 없는데 파일이 남아
        # 디스크만 먹고, 그것을 알아챌 자리가 없다. 파일이 이미 없으면 조용히 넘어간다.
        with contextlib.suppress(OSError):  # 권한·잠금 — 줄은 지우고 파일만 남는다
            full.unlink(missing_ok=True)
        db.delete(stored)
    db.flush()


def bytes_of(db: Session, row: Attachment) -> tuple[bytes, str, str]:
    """내려받을 것 — (바이트, 형식, 이름). 파일이 없으면 404 로 말한다."""
    stored = db.get(StoredFile, row.file_id)
    if stored is None:
        raise NotFound("TSC-ATTACH-0007", "파일 기록이 없습니다.")
    full = get_settings().filestore_dir / stored.path
    if not full.exists():
        # **DB 에는 있는데 파일이 없다.** 복구가 반쪽이었거나 사람이 지운 것이다 —
        # 빈 바이트를 주면 깨진 그림으로 보이고, 그때 원인을 못 찾는다.
        raise NotFound(
            "TSC-ATTACH-0008",
            "파일이 파일스토어에 없습니다 — 백업 복구가 DB 만 된 것일 수 있습니다.",
        )
    return full.read_bytes(), stored.content_type, row.original_name


def sweep_filestore(
    db: Session, *, older_than_hours: float = 24.0, delete: bool = False
) -> dict[str, Any]:
    """**주인 없는 파일을 쓸어낸다** — 그리고 그 반대도 말한다.

    ## 왜 생기나

    올리기는 ① 디스크에 쓰고 ② 표에 적는 순서다. ②가 안 되고 되돌아가면 ①의 파일만
    남는다 — 아무 줄도 안 가리키는 바이트다. 2026-09-24 개발 DB 실측: 디스크 18개 중 16개.

    **순서를 뒤집지 않는 이유**: 표를 먼저 적으면 그 사이에 프로세스가 죽었을 때 「줄은
    있는데 파일이 없는」 첨부가 남는다. 그쪽이 더 나쁘다 — 화면에 깨진 그림으로 서고,
    사람은 파일이 지워진 줄 안다. 스치고 지나간 바이트는 나중에 지우면 되지만, 가리키는
    줄이 있는데 없는 파일은 아무도 못 되살린다.

    ## 갓 올라온 것은 안 건드린다

    `older_than_hours` 가 그것이다. 지금 올라가는 중인 파일은 아직 표에 안 적혔을 수
    있다 — 그걸 지우면 멀쩡한 올리기를 우리가 깨뜨린다.

    돌려주는 것: 지운(또는 지울) 파일 수와 바이트, 그리고 **표에는 있는데 파일이 없는**
    것들. 뒤쪽은 지울 수 없는 고장이라 세어서 말만 한다.
    """
    root = get_settings().filestore_dir
    # **한 번만 읽는다.** 줄마다 객체를 세우면 5만 건짜리 파일스토어에서 두 벌이 뜬다 —
    # 필요한 것은 해시와 경로 둘뿐이다.
    stored = db.execute(select(StoredFile.sha256, StoredFile.path)).all()
    known = {row.sha256 for row in stored}
    cutoff = time.time() - older_than_hours * 3600

    orphans: list[Path] = []
    freed = 0
    recent = 0
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file() or path.name in known:
                continue
            fact = path.stat()
            if fact.st_mtime > cutoff:
                recent += 1  # 아직 올라가는 중일 수 있다 — 건드리지 않는다
                continue
            orphans.append(path)
            freed += fact.st_size

    if delete:
        for path in orphans:
            with contextlib.suppress(OSError):  # 잠긴 파일은 다음 번에 지워진다
                path.unlink()

    missing = [row.sha256 for row in stored if not (root / row.path).exists()]
    return {
        "orphans": len(orphans),
        "bytes": freed,
        "deleted": delete,
        "skipped_recent": recent,
        "missing_files": missing,
    }
