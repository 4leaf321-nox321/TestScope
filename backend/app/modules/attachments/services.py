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
import time
import uuid
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
