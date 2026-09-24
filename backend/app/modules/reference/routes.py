"""온톨로지 허브 라우터 — 읽기는 로그인한 누구나. 정의·등록은 각 화면이 한다."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.reference import services
from app.modules.reference.schemas import ObjectKindOut
from app.shared.auth import current_user

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/overview", response_model=list[ObjectKindOut])
def reference_overview(
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ObjectKindOut]:
    """객체 종류마다 한 줄 — 저장 방식 · 건수 · 고정 칸 · 관리자가 정의한 칸(종류·수·초안 수) ·
    목록과 정의 화면 주소. 「이 시스템의 온톨로지가 무엇인가」 의 답."""
    return services.overview(db)
