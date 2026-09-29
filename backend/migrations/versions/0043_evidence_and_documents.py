"""근거를 붙일 칸, 번호 없는 규격서, 개정 이력, 시험 항목 제안.

사내 문서 수백 건을 옮겨 적으며 드러난 것들(2026-09-30). 넷 다 **지금은 비고 문장으로
밀어 넣는 우회책**이 쓰이고 있고, 문장으로 들어간 것은 검색도 추적도 안 된다.

**① 값에 근거를 붙일 칸**(`attribute_values`). 지금은 「기타 조건」 에 「시험 조건 원문 …」
을 글자로 넣는다. `note` 는 옮겨 적은 사람의 **해석**이고, 원문은 **증거**다 — 그 둘이 한
칸에 섞이면 검토하는 사람이 「이게 문서에 있는 말인가 옮긴 사람의 말인가」 를 못 가른다.

    source_text      원문 스니펫 — 문서에 적힌 그대로
    original_value   환산 전 값 — 158
    original_unit    환산 전 단위 — degF

환산을 따로 남기는 이유: `70 degC` 만 보면 그것이 문서의 값인지 158 °F 를 옮긴 값인지 알
수 없고, **환산이 틀렸을 때 되짚을 자리가 없다.**

**② 규격서 번호가 없을 수 있다**(`spec_documents`). 사내 문서에 번호가 안 붙은 것이 실제로
있는데 `code` 가 필수라, 옮기는 사람이 번호를 지어내거나 등록을 포기했다. 번호를 지어내면
그것이 문서관리 시스템의 번호인 줄 알고 누가 찾으러 간다.

    code          널 허용 — 없으면 없다고 둔다(제목으로 찾는다)
    pages         「12-18」 처럼 어디를 봤나
    is_excerpt    발췌인가 — 전문을 안 본 채 옮긴 것은 그렇게 보여야 한다
    source_path   원본이 어디 있나(사내 경로·URL)

`code` 를 널로 열면서 유일 인덱스도 **널을 서로 다르게** 본다 — 번호 없는 문서 여럿이
한 부서에 설 수 있다. 번호가 있는 것끼리는 예전처럼 하나다.

**③ 개정 이력**(`spec_document_revisions`). 지금은 `revision` 글자 하나라 「이 시험은 개정
18에서 신설」 을 못 적는다. 개정을 줄로 쌓고, 시험이 **어느 개정에서 들어왔는지**와 **어느
개정까지 사람이 봤는지**를 각각 가리킨다.

    시험.introduced_revision_id   이 시험이 신설된 개정
    시험.reviewed_revision_id     사람이 마지막으로 확인한 개정

문서가 개정되면 **확정은 그대로 두고 표만 붙는다**(사람이 고른 규칙) — 수십 건이 한꺼번에
후보로 내려가면 그날 일이 멈춘다. `reviewed_revision_id` 가 최신 개정보다 뒤면 「개정 19
기준으로 아직 안 본 시험」 이고, 사람이 본 것부터 표를 뗀다.

**④ 시험 항목 제안**(`test_item_proposals`). 시험 항목 축은 closed 라 기계가 값을 못
더한다 — 옳다(검색의 첫 축이라 오타 하나가 값이 된다). 그런데 못 더하는 쪽에 **말할 자리도**
없어서, 스무 건 중 아홉 건이 시험 항목 없이 들어오고 **왜 비었는지가 아무 데도 안 남았다.**

제안을 줄로 받아 검토 목록에 모은다. 관리자가 축에 세우거나 기존 값에 이으면, 그 제안을
낸 시험들에 한 번에 걸린다 — 같은 말이 스무 번 나오면 스무 번 판단하지 않는다.

Revision ID: 0043_evidence_and_documents
Revises: 0042_drop_and_displacement
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0043_evidence_and_documents"
down_revision = "0042_drop_and_displacement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ① 값에 근거를 붙일 칸
    op.add_column("attribute_values", sa.Column("source_text", sa.Text(), nullable=True))
    op.add_column(
        "attribute_values", sa.Column("original_value", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "attribute_values", sa.Column("original_unit", sa.String(length=40), nullable=True)
    )

    # ② 규격서 — 번호 없음, 쪽수, 발췌, 원본 경로
    op.alter_column(
        "spec_documents", "code", existing_type=sa.String(length=100), nullable=True
    )
    op.add_column("spec_documents", sa.Column("pages", sa.String(length=60), nullable=True))
    op.add_column(
        "spec_documents",
        sa.Column("is_excerpt", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("spec_documents", sa.Column("source_path", sa.Text(), nullable=True))
    # **널끼리는 서로 다르다** — 번호 없는 문서 여럿이 한 부서에 설 수 있어야 한다.
    op.drop_index("uq_spec_documents_workspace_code", table_name="spec_documents")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_spec_documents_workspace_code
            ON spec_documents (workspace_id, code)
         WHERE deleted_at IS NULL AND code IS NOT NULL
        """
    )

    # ③ 개정 이력
    op.create_table(
        "spec_document_revisions",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("spec_documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_via", sa.String(length=100), nullable=True),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "label", name="uq_spec_document_revisions_label"),
    )
    for column in ("introduced_revision_id", "reviewed_revision_id"):
        op.add_column(
            "reliability_tests",
            sa.Column(
                column,
                PgUUID(as_uuid=True),
                # **개정을 지워도 시험은 남는다** — 어느 개정이었는지를 잃을 뿐이고,
                # 그것 때문에 시험이 사라지면 훨씬 나쁘다.
                sa.ForeignKey("spec_document_revisions.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    op.create_index(
        "ix_reliability_tests_reviewed_revision_id",
        "reliability_tests",
        ["reviewed_revision_id"],
    )

    # ④ 시험 항목 제안
    op.create_table(
        "test_item_proposals",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("text", sa.String(length=200), nullable=False),
        # 같은 말을 모으는 비교키 — 띄어쓰기·대소문자를 지운 것. 스무 건에서 같은 말이
        # 나오면 한 줄로 서서, 관리자가 스무 번이 아니라 한 번 판단한다.
        sa.Column("normalized", sa.String(length=200), nullable=False, index=True),
        sa.Column(
            "reliability_test_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("reliability_tests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_via", sa.String(length=100), nullable=True),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.UniqueConstraint(
            "reliability_test_id", "normalized", name="uq_test_item_proposals_pair"
        ),
    )


def downgrade() -> None:
    op.drop_table("test_item_proposals")
    op.drop_index("ix_reliability_tests_reviewed_revision_id", table_name="reliability_tests")
    op.drop_column("reliability_tests", "reviewed_revision_id")
    op.drop_column("reliability_tests", "introduced_revision_id")
    op.drop_table("spec_document_revisions")
    op.drop_index("uq_spec_documents_workspace_code", table_name="spec_documents")
    # 번호 없는 문서를 되돌릴 수 없다 — `code` 가 다시 필수가 되므로 자리를 채워 둔다.
    op.execute("UPDATE spec_documents SET code = '(번호 없음)' WHERE code IS NULL")
    op.alter_column(
        "spec_documents", "code", existing_type=sa.String(length=100), nullable=False
    )
    op.create_index(
        "uq_spec_documents_workspace_code",
        "spec_documents",
        ["workspace_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_column("spec_documents", "source_path")
    op.drop_column("spec_documents", "is_excerpt")
    op.drop_column("spec_documents", "pages")
    op.drop_column("attribute_values", "original_unit")
    op.drop_column("attribute_values", "original_value")
    op.drop_column("attribute_values", "source_text")
