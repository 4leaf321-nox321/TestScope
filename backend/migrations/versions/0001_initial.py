"""초기 스키마 — 계정·부서·기준정보·장비·시험법·역량.

한 리비전에 모은 이유: 이 시점 이전의 DB 는 없다. 표를 하나씩 나눠 놓으면 첫
설치에서 열몇 번을 순서대로 돌려야 하고, 그 순서가 곧 FK 순서라 한 번 어긋나면
읽기 어렵다.

**행은 여기서 안 심는다.** 기준정보 축과 조건 정의는 설치 시드가 만든다
(`app/modules/vocabulary/reference.py`) — 마이그레이션에 넣으면 모델로 표를 만드는
시험이 그 행을 못 받아서 같은 목록을 시험 쪽에 한 벌 더 적게 되고, 두 벌은 반드시
갈린다.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _pk() -> sa.Column:
    return sa.Column("id", PgUUID(as_uuid=True), primary_key=True)


def upgrade() -> None:
    # --- 조직과 계정 --------------------------------------------------------
    #
    # workspaces 가 먼저다. users.home_workspace_id 가 그것을 가리킨다.
    op.create_table(
        "workspaces",
        _pk(),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "parent_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("restricted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)
    op.create_index("ix_workspaces_parent_id", "workspaces", ["parent_id"])

    op.create_table(
        "users",
        _pk(),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("is_system_admin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "home_workspace_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requested_workspace_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failed_logins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    op.create_table(
        "workspace_members",
        _pk(),
        sa.Column(
            "workspace_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_pair"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    # --- 토큰 ---------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        _pk(),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_agent", sa.String(300), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )

    op.create_table(
        "personal_access_tokens",
        _pk(),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_personal_access_tokens_user_id", "personal_access_tokens", ["user_id"])
    op.create_index("ix_personal_access_tokens_prefix", "personal_access_tokens", ["prefix"])
    op.create_index(
        "ix_personal_access_tokens_token_hash",
        "personal_access_tokens",
        ["token_hash"],
        unique=True,
    )

    # --- 기준정보 -----------------------------------------------------------
    op.create_table(
        "vocabularies",
        _pk(),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("entry_policy", sa.String(10), nullable=False, server_default="open"),
        sa.Column("parent_slug", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_vocabularies_slug", "vocabularies", ["slug"], unique=True)

    op.create_table(
        "vocabulary_terms",
        _pk(),
        sa.Column(
            "vocabulary_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabularies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("normalized", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column(
            "parent_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attributes", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_by_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("vocabulary_id", "normalized", name="uq_vocabulary_terms_norm"),
    )
    op.create_index("ix_vocabulary_terms_vocabulary_id", "vocabulary_terms", ["vocabulary_id"])
    op.create_index("ix_vocabulary_terms_normalized", "vocabulary_terms", ["normalized"])
    op.create_index("ix_vocabulary_terms_code", "vocabulary_terms", ["code"])
    op.create_index(
        "ix_vocabulary_terms_parent_term_id", "vocabulary_terms", ["parent_term_id"]
    )
    op.create_index("ix_vocabulary_terms_status", "vocabulary_terms", ["status"])

    op.create_table(
        "vocabulary_aliases",
        _pk(),
        sa.Column(
            "vocabulary_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabularies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("normalized", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("vocabulary_id", "normalized", name="uq_vocabulary_aliases_norm"),
    )
    op.create_index(
        "ix_vocabulary_aliases_vocabulary_id", "vocabulary_aliases", ["vocabulary_id"]
    )
    op.create_index("ix_vocabulary_aliases_term_id", "vocabulary_aliases", ["term_id"])
    op.create_index("ix_vocabulary_aliases_normalized", "vocabulary_aliases", ["normalized"])

    op.create_table(
        "condition_keys",
        _pk(),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="range"),
        sa.Column("dimension", sa.String(30), nullable=False, server_default=""),
        sa.Column("si_unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("display_unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("choices", JSONB, nullable=False, server_default="[]"),
        sa.Column("help", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_condition_keys_key", "condition_keys", ["key"], unique=True)

    # --- 장비 ---------------------------------------------------------------
    op.create_table(
        "equipment",
        _pk(),
        sa.Column("asset_no", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "category_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "manufacturer_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_no", sa.String(100), nullable=True),
        sa.Column(
            "owner_workspace_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "site_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="operational"),
        sa.Column("acquired_on", sa.Date, nullable=True),
        sa.Column(
            "contact_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_equipment_asset_no", "equipment", ["asset_no"], unique=True)
    op.create_index("ix_equipment_category_term_id", "equipment", ["category_term_id"])
    op.create_index("ix_equipment_manufacturer_term_id", "equipment", ["manufacturer_term_id"])
    op.create_index("ix_equipment_owner_workspace_id", "equipment", ["owner_workspace_id"])
    op.create_index("ix_equipment_site_term_id", "equipment", ["site_term_id"])
    op.create_index("ix_equipment_status", "equipment", ["status"])
    op.create_index("ix_equipment_deleted_at", "equipment", ["deleted_at"])

    op.create_table(
        "equipment_calibrations",
        _pk(),
        sa.Column(
            "equipment_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calibrated_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True),
        sa.Column("certificate_no", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(200), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_equipment_calibrations_equipment_id", "equipment_calibrations", ["equipment_id"]
    )
    op.create_index(
        "ix_equipment_calibrations_calibrated_on", "equipment_calibrations", ["calibrated_on"]
    )
    op.create_index(
        "ix_equipment_calibrations_next_due_on", "equipment_calibrations", ["next_due_on"]
    )

    # --- 시험법 -------------------------------------------------------------
    op.create_table(
        "test_methods",
        _pk(),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("edition", sa.String(30), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "test_item_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "body_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "superseded_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("test_methods.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "owner_workspace_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code", "edition", name="uq_test_methods_code_edition"),
    )
    op.create_index("ix_test_methods_code", "test_methods", ["code"])
    op.create_index("ix_test_methods_test_item_term_id", "test_methods", ["test_item_term_id"])
    op.create_index("ix_test_methods_body_term_id", "test_methods", ["body_term_id"])
    op.create_index("ix_test_methods_status", "test_methods", ["status"])
    op.create_index(
        "ix_test_methods_owner_workspace_id", "test_methods", ["owner_workspace_id"]
    )
    op.create_index("ix_test_methods_deleted_at", "test_methods", ["deleted_at"])

    op.create_table(
        "method_requirements",
        _pk(),
        sa.Column(
            "method_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("test_methods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "condition_key_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("condition_keys.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("min_value", sa.Float, nullable=True),
        sa.Column("max_value", sa.Float, nullable=True),
        sa.Column("text_value", sa.String(200), nullable=True),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("note", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "method_id", "condition_key_id", name="uq_method_requirements_key"
        ),
    )
    op.create_index("ix_method_requirements_method_id", "method_requirements", ["method_id"])
    op.create_index(
        "ix_method_requirements_condition_key_id", "method_requirements", ["condition_key_id"]
    )

    # --- 역량 ---------------------------------------------------------------
    op.create_table(
        "capabilities",
        _pk(),
        sa.Column(
            "equipment_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "test_item_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "method_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("test_methods.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="catalog"),
        sa.Column("verified_on", sa.Date, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "equipment_id", "test_item_term_id", "method_id", name="uq_capabilities_triple"
        ),
    )
    op.create_index("ix_capabilities_equipment_id", "capabilities", ["equipment_id"])
    op.create_index("ix_capabilities_test_item_term_id", "capabilities", ["test_item_term_id"])
    op.create_index("ix_capabilities_method_id", "capabilities", ["method_id"])
    op.create_index("ix_capabilities_confidence", "capabilities", ["confidence"])

    op.create_table(
        "capability_limits",
        _pk(),
        sa.Column(
            "capability_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "condition_key_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("condition_keys.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("min_value", sa.Float, nullable=True),
        sa.Column("max_value", sa.Float, nullable=True),
        sa.Column("text_value", sa.String(200), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "capability_id", "condition_key_id", name="uq_capability_limits_key"
        ),
    )
    op.create_index(
        "ix_capability_limits_capability_id", "capability_limits", ["capability_id"]
    )
    op.create_index(
        "ix_capability_limits_condition_key_id", "capability_limits", ["condition_key_id"]
    )

    # --- 로그와 알림 --------------------------------------------------------
    op.create_table(
        "access_logs",
        _pk(),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String(40), nullable=True),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_access_logs_user_id", "access_logs", ["user_id"])
    op.create_index("ix_access_logs_action", "access_logs", ["action"])
    op.create_index("ix_access_logs_created_at", "access_logs", ["created_at"])

    op.create_table(
        "audit_entries",
        _pk(),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column(
            "actor_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_label", sa.String(200), nullable=False),
        sa.Column("target_table", sa.String(60), nullable=False),
        # **외래키를 안 건다.** 지워진 대상의 기록이 그 삭제 때문에 사라지면 안 된다.
        sa.Column("target_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("target_label", sa.String(300), nullable=False),
        sa.Column("workspace_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("changes", JSONB, nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("request_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_entries_action", "audit_entries", ["action"])
    op.create_index("ix_audit_entries_actor_id", "audit_entries", ["actor_id"])
    op.create_index("ix_audit_entries_target_table", "audit_entries", ["target_table"])
    op.create_index("ix_audit_entries_target_id", "audit_entries", ["target_id"])
    op.create_index("ix_audit_entries_workspace_id", "audit_entries", ["workspace_id"])
    op.create_index("ix_audit_entries_request_id", "audit_entries", ["request_id"])
    op.create_index("ix_audit_entries_created_at", "audit_entries", ["created_at"])

    op.create_table(
        "notices",
        _pk(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("is_popup", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "author_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notices_published_at", "notices", ["published_at"])

    op.create_table(
        "notice_reads",
        _pk(),
        sa.Column(
            "notice_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("notice_id", "user_id", name="uq_notice_reads_pair"),
    )
    op.create_index("ix_notice_reads_notice_id", "notice_reads", ["notice_id"])
    op.create_index("ix_notice_reads_user_id", "notice_reads", ["user_id"])

    op.create_table(
        "notifications",
        _pk(),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_kind", "notifications", ["kind"])
    op.create_index("ix_notifications_read_at", "notifications", ["read_at"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    """**FK 의 역순으로 지운다.** 순서가 어긋나면 PostgreSQL 이 거부한다."""
    for table in (
        "notifications",
        "notice_reads",
        "notices",
        "audit_entries",
        "access_logs",
        "capability_limits",
        "capabilities",
        "method_requirements",
        "test_methods",
        "equipment_calibrations",
        "equipment",
        "condition_keys",
        "vocabulary_aliases",
        "vocabulary_terms",
        "vocabularies",
        "personal_access_tokens",
        "refresh_tokens",
        "workspace_members",
        "users",
        "workspaces",
    ):
        op.drop_table(table)
