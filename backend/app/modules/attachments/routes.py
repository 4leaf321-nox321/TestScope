"""첨부 라우터.

**읽기는 그 대상을 볼 수 있는 누구나.** 그림은 플랫폼에 들어와 조회하는 사람에게 값이
있는 것이라, 넣은 사람만 보면 아무 몫도 못 한다. 넣고 지우는 것은 그 대상을 고칠 수 있는
사람이다 — 판정은 대상 모듈이 한다(`services.require_can_edit`).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.attachments import services
from app.modules.attachments.models import MAX_BYTES, Attachment
from app.modules.attachments.schemas import AttachmentOut, AttachmentUpdateRequest
from app.modules.attributes.models import AttributeDefinition
from app.shared.auth import current_user

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _out(db: Session, row: Attachment) -> AttachmentOut:
    from app.modules.attachments.models import StoredFile

    stored = db.get(StoredFile, row.file_id)
    definition = db.get(AttributeDefinition, row.definition_id) if row.definition_id else None
    return AttachmentOut(
        id=row.id,
        target=row.target,
        object_id=row.object_id,
        definition_id=row.definition_id,
        definition_label=definition.label if definition else None,
        original_name=row.original_name,
        caption=row.caption,
        content_type=stored.content_type if stored else "",
        bytes=stored.bytes if stored else 0,
        sort_order=row.sort_order,
        url=f"/api/attachments/{row.id}/file",
        created_at=row.created_at,
    )


@router.get("", response_model=list[AttachmentOut])
def list_attachments(
    target: str = Query(...),
    object_id: uuid.UUID = Query(...),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AttachmentOut]:
    return [_out(db, row) for row in services.list_for(db, target=target, object_id=object_id)]


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload(
    target: str = Form(...),
    object_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    definition_id: uuid.UUID | None = Form(default=None),
    caption: str = Form(default=""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AttachmentOut:
    """그림 한 장을 붙인다.

    **한 번에 한 장이다.** 여러 장을 한 요청에 담으면 열째에서 막혔을 때 앞의 아홉이
    들어갔는지 사람이 알 수 없다 — 화면이 한 장씩 보내고 줄마다 성패를 보인다.
    """
    # **한계까지만 읽는다.** 통째로 읽고 나서 재면 10 MB 제한이 있어도 1 GB 를 먼저
    # 메모리에 올린다 — 그것만으로 서버가 넘어간다.
    data = await file.read(MAX_BYTES + 1)
    row = services.add(
        db,
        user,
        target=target,
        object_id=object_id,
        filename=file.filename or "",
        content_type=file.content_type or "",
        data=data,
        definition_id=definition_id,
        caption=caption,
    )
    db.commit()
    db.refresh(row)
    return _out(db, row)


@router.get("/{attachment_id}/file")
def download(
    attachment_id: uuid.UUID,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """파일 자체. **보는 것은 대상을 볼 수 있는 누구나** — 그림은 조회하는 사람의 것이다."""
    row = services.get(db, attachment_id)
    data, content_type, name = services.bytes_of(db, row)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            # inline 이라 화면이 <img> 로 바로 그린다. 이름은 내려받을 때 쓰인다.
            "Content-Disposition": f"inline; filename*=UTF-8''{_quote(name)}",
            # 내용이 곧 이름(sha256)이라 바뀌지 않는다 — 오래 캐시해도 안전하다.
            "Cache-Control": "private, max-age=86400",
        },
    )


def _quote(name: str) -> str:
    from urllib.parse import quote

    return quote(name, safe="")


@router.patch("/{attachment_id}", response_model=AttachmentOut)
def update_attachment(
    attachment_id: uuid.UUID,
    payload: AttachmentUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AttachmentOut:
    row = services.update(db, user, attachment_id, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(row)
    return _out(db, row)


@router.delete("/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.remove(db, user, attachment_id)
    db.commit()
