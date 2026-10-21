"""기준정보 허브(StandardPlatform) 수신 — 연계 설정 · 코어 사본 · 기준 시각 · 실행 이력 · 축 잠금.

2026-10-21 사용자 결정으로 허브에서 받는다(ADR 0012 — 0011 대체). 요청서 1.2 §8 방식 A(코어 사본)와
B(온톨로지 축 반영)를 함께 쓴다.

    hub_connections        연계 설정 한 줄(주소 · 봉인한 토큰 · 받을 타입 · 야간 시각 · 카탈로그)
    core_items             받은 객체(식별자 · 이름 · 상태 · 속성 원문 · 반영된 값)
    core_relations         받은 관계((출발, 관계, 도착, 도착 타입) 넷이 식별)
    core_sync_states       타입마다 · 행/관계마다 기준 시각
    core_sync_runs         실행 이력(타입별 건수 · 오류 · request_id)
    vocabularies.hub_type_slug   허브에서 받는 축이면 그 타입 — 차 있으면 축이 잠긴다

Revision ID: 0055_hub_core_intake
Revises: 0054_review_skip_and_vote_via
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055_hub_core_intake"
down_revision = "0054_review_skip_and_vote_via"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "vocabularies", sa.Column("hub_type_slug", sa.String(length=100), nullable=True)
    )
    op.create_unique_constraint(
        "uq_vocabularies_hub_type_slug", "vocabularies", ["hub_type_slug"]
    )

    op.create_table(
        "hub_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("token_sealed", sa.Text(), server_default="", nullable=False),
        sa.Column("token_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ca_bundle", sa.String(length=500), nullable=True),
        sa.Column("selected_types", JSONB, nullable=True),
        sa.Column("nightly_at", sa.String(length=5), server_default="01:00", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("catalog", JSONB, server_default="{}", nullable=False),
        sa.Column("catalog_revision", sa.String(length=100), nullable=True),
        sa.Column("catalog_signature", sa.Text(), nullable=True),
        sa.Column("catalog_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "core_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type_slug", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("absent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("merged_into", sa.String(length=300), nullable=True),
        sa.Column("previous_keys", JSONB, server_default="[]", nullable=False),
        sa.Column("properties", JSONB, server_default="{}", nullable=False),
        sa.Column("hub_updated_at", sa.String(length=40), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("type_slug", "key", name="uq_core_items_key"),
    )
    op.create_index("ix_core_items_type_slug", "core_items", ["type_slug"])
    op.create_index("ix_core_items_term_id", "core_items", ["term_id"])

    op.create_table(
        "core_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type_slug", sa.String(length=100), nullable=False),
        sa.Column("src_key", sa.String(length=300), nullable=False),
        sa.Column("relation", sa.String(length=100), nullable=False),
        sa.Column("dst_key", sa.String(length=300), nullable=False),
        sa.Column("dst_type", sa.String(length=100), nullable=False),
        sa.Column("properties", JSONB, server_default="{}", nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("hub_updated_at", sa.String(length=40), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "type_slug", "src_key", "relation", "dst_key", "dst_type", name="uq_core_relations"
        ),
    )
    op.create_index("ix_core_relations_type_slug", "core_relations", ["type_slug"])
    op.create_index("ix_core_relations_src_key", "core_relations", ["src_key"])
    op.create_index("ix_core_relations_dst_key", "core_relations", ["dst_key"])

    op.create_table(
        "core_sync_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type_slug", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("as_of", sa.String(length=40), nullable=True),
        sa.Column("stopped", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_full_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("type_slug", "kind", name="uq_core_sync_states"),
    )

    op.create_table(
        "core_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("full", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("triggered_by", sa.String(length=200), nullable=True),
        sa.Column("counts", JSONB, server_default="{}", nullable=False),
        sa.Column("errors", JSONB, server_default="[]", nullable=False),
        sa.Column("request_ids", JSONB, server_default="[]", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_core_sync_runs_started_at", "core_sync_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_core_sync_runs_started_at", table_name="core_sync_runs")
    op.drop_table("core_sync_runs")
    op.drop_table("core_sync_states")
    op.drop_index("ix_core_relations_dst_key", table_name="core_relations")
    op.drop_index("ix_core_relations_src_key", table_name="core_relations")
    op.drop_index("ix_core_relations_type_slug", table_name="core_relations")
    op.drop_table("core_relations")
    op.drop_index("ix_core_items_term_id", table_name="core_items")
    op.drop_index("ix_core_items_type_slug", table_name="core_items")
    op.drop_table("core_items")
    op.drop_table("hub_connections")
    op.drop_constraint("uq_vocabularies_hub_type_slug", "vocabularies", type_="unique")
    op.drop_column("vocabularies", "hub_type_slug")
