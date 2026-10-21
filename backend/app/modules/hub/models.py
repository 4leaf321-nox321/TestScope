"""기준정보 허브(StandardPlatform) 수신 — **받은 것을 그대로 남기는 자리.**

허브의 코어 API(`/api/core`)에서 받은 객체 · 관계를 원문 그대로 보관한다(요청서 1.2 §8 방식 A).
TestScope 기능은 이것을 직접 읽지 않고 **온톨로지 축에 반영된 값**을 쓴다(방식 B) — 타입마다
축 하나, 객체마다 값 하나. 여기는 그 반영의 근거이자 부재 대조 · 감사 대조의 자리다.

**물리 삭제하지 않는다.** 허브에서 지워진 것 · 사용 중지된 것 · 조회 범위를 벗어난 것(숨김) ·
병합된 것은 표시만 바꾼다 — 시험 · 장비가 그 값을 가리키고 있을 수 있다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HubConnection(Base):
    """연계 설정 — **한 줄뿐이다.** 허브는 하나다.

    토큰은 암호화해 둔다(`app.shared.secretbox`). 화면에는 「설정됨」 만 보인다 — 다시 보여
    주면 화면을 본 사람 누구나 허브 전체를 읽는 자격을 갖게 된다.
    """

    __tablename__ = "hub_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    base_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    """허브 주소. `https://호스트/api` 도 `…/api/core` 도 받는다."""
    token_sealed: Mapped[str] = mapped_column(Text, default="", server_default="")
    token_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ca_bundle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """사내 인증서 묶음 경로. 비우면 시스템 기본(certifi)."""
    selected_types: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    """받을 타입. **비우면(NULL) 카탈로그의 공개 타입 전부** — 허브가 타입을 새로 열면 다음
    수신부터 저절로 받는다. 목록이면 그것만."""
    nightly_at: Mapped[str] = mapped_column(String(5), default="01:00", server_default="01:00")
    """야간 자동 수신 시각(KST, HH:MM)."""
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    """야간 자동 수신을 켰나. 꺼도 수동 실행은 된다."""
    catalog: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    """마지막으로 받은 카탈로그 원문 — 타입 고르기 화면과 구조 변경 대조가 쓴다."""
    catalog_revision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    catalog_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    """구조의 지문(타입 · 속성 · 관계 종류). `revision` 이 바뀌어도 이것이 같으면 안
    알린다."""
    catalog_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """구조가 실제로 바뀐 때. 관리자가 확인하면 비운다(`catalog_seen`)."""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CoreItem(Base):
    """허브 객체 하나의 사본 — 식별자 · 이름 · 상태 · 속성 원문."""

    __tablename__ = "core_items"
    __table_args__ = (UniqueConstraint("type_slug", "key", name="uq_core_items_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type_slug: Mapped[str] = mapped_column(String(100), index=True)
    key: Mapped[str] = mapped_column(String(300))
    """허브 식별자. 식별자가 없는 타입은 허브가 이름으로 대신 준다(비고유 · 가변)."""
    label: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")
    """허브의 상태 — `active` · `deprecated`."""
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    """조회 범위를 벗어났다(소유 부서 이동 등). 지운 것이 아니라 가진 값은 그대로 둔다."""
    absent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    """전량 대조에서 안 왔다 — 표식 없이 사라진 것(토큰 계정의 범위 축소 등)."""
    merged_into: Mapped[str | None] = mapped_column(String(300), nullable=True)
    previous_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    hub_updated_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """이 객체가 반영된 온톨로지 값."""


class CoreRelation(Base):
    """허브 관계 하나 — **(출발, 관계, 도착, 도착 타입) 넷이 식별한다.**

    식별자는 타입 안에서만 고유하고, 끝이 인터페이스인 관계는 같은 도착 식별자가 다른 타입에
    있을 수 있다(요청서 §5.5).
    """

    __tablename__ = "core_relations"
    __table_args__ = (
        UniqueConstraint(
            "type_slug", "src_key", "relation", "dst_key", "dst_type", name="uq_core_relations"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type_slug: Mapped[str] = mapped_column(String(100), index=True)
    """출발 객체의 타입."""
    src_key: Mapped[str] = mapped_column(String(300), index=True)
    relation: Mapped[str] = mapped_column(String(100))
    dst_key: Mapped[str] = mapped_column(String(300), index=True)
    dst_type: Mapped[str] = mapped_column(String(100))
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    hub_updated_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CoreSyncState(Base):
    """타입마다 · 행/관계마다 **어디까지 받았나**(기준 시각)."""

    __tablename__ = "core_sync_states"
    __table_args__ = (UniqueConstraint("type_slug", "kind", name="uq_core_sync_states"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type_slug: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(10))
    """`rows` · `relations`."""
    as_of: Mapped[str | None] = mapped_column(String(40), nullable=True)
    """허브가 준 기준 시각 **그대로**. 전 쪽을 다 받은 뒤에만 바뀐다."""
    stopped: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    """허브가 이 타입을 닫았다(`APP-CORE-0001`). 카탈로그에 다시 서면 풀린다."""
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_full_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """마지막 전량 수신(부재 대조까지 한 것)."""


class CoreSyncRun(Base):
    """수신 한 번 — 언제 · 어떻게 · 타입마다 몇 건 · 결과 · 오류."""

    __tablename__ = "core_sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(20))
    """`schedule` · `manual` · `reconcile`(주간 전량 대조)."""
    full: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(20), default="running")
    """`running` · `ok` · `partial`(일부 타입 실패) · `failed`."""
    triggered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    """타입마다 {created, updated, unchanged, deactivated, restored, merged, renamed, absent,
    relations_added, relations_removed, received, catalog_count}."""
    errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    request_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    """허브 응답의 `request_id` — 허브 「최근 조회 이력」 과 대조한다."""
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
