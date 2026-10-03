"""첨부 라우터.

**읽기는 그 대상을 볼 수 있는 누구나.** 그림은 플랫폼에 들어와 조회하는 사람에게 값이
있는 것이라, 넣은 사람만 보면 아무 몫도 못 한다. 넣고 지우는 것은 그 대상을 고칠 수 있는
사람이다 — 판정은 대상 모듈이 한다(`services.require_can_edit`).
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.attachments import services
from app.modules.attachments.models import MAX_BYTES, Attachment
from app.modules.attachments.schemas import (
    AttachBatchRequest,
    AttachBatchResult,
    AttachExistingRequest,
    AttachmentOut,
    AttachmentUpdateRequest,
    AttachRowOut,
    ExtractImagesResult,
    UploadTicketOut,
)
from app.modules.attributes.models import AttributeDefinition
from app.modules.auth import security
from app.shared.auth import current_user
from app.shared.errors import AppError

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


@router.post("/upload-ticket", response_model=UploadTicketOut)
def mint_upload_ticket(user: User = Depends(current_user)) -> UploadTicketOut:
    """**PC 의 파일을 서버로 바로 올릴** 짧은 자격을 하나 낸다(5분).

    큰 파일을 AI 를 거쳐 나르면 안 된다 — 50 MB 스캔본은 base64 로 모델 문맥을 통째로
    먹는다. 그래서 바이트는 셸에서 곧장 간다(`curl`). 그때 진짜 토큰을 셸에 적으면 오래
    사는 자격이 기록에 남으므로, **올리기만 되는 티켓**을 대신 준다.
    """
    ticket, seconds = security.create_upload_ticket(user.id)
    return UploadTicketOut(ticket=ticket, expires_in_seconds=seconds)


@router.post("/upload-with-ticket", response_model=AttachmentOut, status_code=201)
async def upload_with_ticket(
    request: Request,
    target: str = Query(...),
    object_id: uuid.UUID = Query(...),
    filename: str = Query(..., max_length=255),
    definition_id: uuid.UUID | None = Query(default=None),
    caption: str = Query(default=""),
    x_upload_ticket: str = Header(...),
    db: Session = Depends(get_db),
) -> AttachmentOut:
    """티켓으로 올린다 — **몸통은 파일 바이트 그대로**(`curl --data-binary @파일`).

    multipart 가 아닌 이유: 셸에서 한 줄로 쓸 수 있어야 하고, 그 한 줄을 사람이 보고
    무엇을 올리는지 알 수 있어야 한다. 자격은 티켓이 싣고 있으므로 Bearer 를 안 받는다 —
    **그래서 티켓은 5분만 산다.**
    """
    who = security.decode_upload_ticket(x_upload_ticket)
    if who is None:
        raise AppError(
            "TSC-ATTACH-0010",
            "업로드 티켓이 유효하지 않거나 만료됨(5분). 다시 발급 필요.",
            status=401,
        )
    user = db.get(User, who)
    if user is None or user.status != "active":
        raise AppError("TSC-ATTACH-0011", "티켓 소유자를 찾을 수 없음.", status=401)

    # **한계까지만 읽는다** — 통째로 읽고 재면 1 GB 가 먼저 메모리에 올라간다.
    data = b""
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_BYTES + 1:
            break
    row = services.add(
        db,
        user,
        target=target,
        object_id=object_id,
        filename=filename,
        content_type="",
        data=data,
        definition_id=definition_id,
        caption=caption,
    )
    db.commit()
    db.refresh(row)
    return _out(db, row)


@router.post("/{attachment_id}/extract-images", response_model=ExtractImagesResult)
def extract_images(
    attachment_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ExtractImagesResult:
    """올려 둔 워드·파워포인트에서 **그림을 낱장으로 꺼낸다.** 서버가 zip 으로 푼다.

    바이트가 AI 를 안 거치는 것이 요점이다. 꺼낸 것은 문서와 같은 자리에 붙고, 문서에서
    그림 자리의 글을 설명으로 달아 둔다 — AI 는 그림을 못 보므로 그 글자가 유일한 단서다.
    """
    result = services.extract_images(db, user, source=services.get(db, attachment_id))
    db.commit()
    return ExtractImagesResult(
        source_attachment_id=result["source_attachment_id"],
        images=[_out(db, row) for row in result["images"]],
        extracted=result["extracted"],
        skipped_oversize=result["skipped_oversize"],
        skipped_kind=result["skipped_kind"],
        skipped_duplicate=result["skipped_duplicate"],
    )


@router.post("/attach-batch", response_model=AttachBatchResult)
def attach_batch(
    payload: AttachBatchRequest,
    dry_run: bool = Query(default=True),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AttachBatchResult:
    """그림 여럿을 **한 번에** 제자리로 — 규격서 한 벌에서 서른 장이 나온다.

    줄마다 「어느 그림을 · 어느 대상의 · 어느 칸에」 를 적는다. **기본은 미리보기**다
    (`dry_run=true`) — 서른 장을 엉뚱한 시험에 걸어 놓고 되돌리는 것보다 표로 먼저 보는
    편이 싸다. 사람이 확인하면 같은 것을 `dry_run=false` 로 다시 보낸다.

    줄마다 따로 판정한다 — 한 줄이 막혀도 나머지는 걸린다. 못 건 줄은 이유와 함께 남는다.
    """
    result = services.attach_batch(
        db, user, items=[one.model_dump() for one in payload.items], dry_run=dry_run
    )
    if not dry_run:
        db.commit()
    return AttachBatchResult(
        rows=[AttachRowOut(**one) for one in result["rows"]],
        attached=result["attached"],
        refused=result["refused"],
        dry_run=result["dry_run"],
    )


@router.post("/{attachment_id}/attach", response_model=AttachmentOut, status_code=201)
def attach_existing(
    attachment_id: uuid.UUID,
    payload: AttachExistingRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AttachmentOut:
    """이미 올라온 파일을 **다른 자리에도 가리킨다.** 바이트는 안 움직인다.

    규격서에 올린 그림 서른 장을 시험 서른 건에 나눠 걸 때 쓴다 — 다시 올리면 같은
    바이트가 서른 벌 생기고, 무엇보다 그 바이트가 AI 를 거쳐야 한다.
    """
    row = services.attach_existing(
        db,
        user,
        source=services.get(db, attachment_id),
        target=payload.target,
        object_id=payload.object_id,
        definition_id=payload.definition_id,
        caption=payload.caption,
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
