"""사업부 — **신뢰성 시험이 사는 자리를 부서에서 사업부로 옮긴다.**

0036 은 부서에 「신뢰성 시험을 둘 수 있다」 는 표시를 달았다. 그것으로는 부족하다는 것이
곧 드러났다 — 표시는 관리자가 어디에나 켤 수 있고, 조직 개편으로 팀이 옮겨 다니면 시험이
따라다닌다. **사업부는 조직도와 다른 축이다.**

사업부는 새 표가 아니라 **이름 사전의 축**(`division`)이다. 장비가 거점·분류를 그렇게
가리키는 것과 같다 — 별칭·병합·감사·편집 화면이 이미 있고, 값을 더하는 길도 이미 있다.

    workspaces.division_term_id      이 부서의 사업부. **비우면 위에서 물려받는다**
    reliability_tests.division_term_id  시험이 속한 사업부(부서가 아니다)

**데이터는 버린다.** 운영·개발 어디에도 남길 신뢰성 시험이 없다(2026-09-29 확인). 옮길
규칙을 지어내는 것보다 비우고 시작하는 편이 정직하다 — 부서마다 흩어진 것을 사업부로
합치면 이름이 겹치고, 그 합침을 되돌릴 방법이 없다.

Revision ID: 0037_division
Revises: 0036_reliability_owner
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037_division"
down_revision = "0036_reliability_owner"
branch_labels = None
depends_on = None

#: (code, 보여 주는 값). `app/modules/vocabulary/reference.py` 의 DEFAULT_TERMS 와 같다 —
#: 그쪽은 새 설치(create_all)용이고 여기는 이미 도는 DB 용이다.
DIVISIONS = [
    ("mx", "MX"),
    ("vd", "VD"),
    ("da", "DA"),
    ("nw", "NW"),
    ("medical", "의료기기"),
    ("gtr", "GTR"),
    ("sr", "SR"),
    ("cs", "CS"),
]


def upgrade() -> None:
    # ── 축과 값 ────────────────────────────────────────────────────────────
    op.execute(
        """
        INSERT INTO vocabularies (id, slug, domain, label, entry_policy, sort_order, description)
        SELECT gen_random_uuid(), 'division', 'common', '사업부', 'closed', 5,
               'MX·VD·DA 처럼 회사를 가르는 단위. 부서(조직도)에 붙이면 그 아래가 모두 '
               '물려받고, 신뢰성 시험은 부서가 아니라 이 사업부에 속한다.'
        WHERE NOT EXISTS (SELECT 1 FROM vocabularies WHERE slug = 'division')
        """
    )
    for code, value in DIVISIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO vocabulary_terms
                    (id, vocabulary_id, value, normalized, code, attributes, status)
                SELECT gen_random_uuid(), v.id, :value, :normalized, :code, '{}'::jsonb, 'active'
                  FROM vocabularies v
                 WHERE v.slug = 'division'
                   AND NOT EXISTS (
                        SELECT 1 FROM vocabulary_terms t
                         WHERE t.vocabulary_id = v.id AND t.code = :code)
                """
            ).bindparams(value=value, normalized=value.lower(), code=code)
        )

    # ── 부서에 사업부를 붙일 자리 ──────────────────────────────────────────
    op.add_column("workspaces", sa.Column("division_term_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_workspaces_division_term_id"), "workspaces", ["division_term_id"])
    op.create_foreign_key(
        op.f("fk_workspaces_division_term_id_vocabulary_terms"),
        "workspaces",
        "vocabulary_terms",
        ["division_term_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("workspaces", "reliability_owner")

    # ── 신뢰성 시험: 부서 → 사업부 ─────────────────────────────────────────
    # 옮길 것이 없으므로 비우고 간다(위 머리말 참조). 첨부·항목·속성은 FK 로 함께 지워지지
    # 않으므로 먼저 거둔다.
    op.execute("DELETE FROM reliability_test_items")
    op.execute("DELETE FROM attachments WHERE target = 'reliability_test'")
    op.execute("DELETE FROM attribute_values WHERE reliability_test_id IS NOT NULL")
    op.execute("DELETE FROM reliability_tests")

    op.drop_index("uq_reliability_tests_workspace_name", table_name="reliability_tests")
    op.add_column(
        "reliability_tests", sa.Column("division_term_id", sa.Uuid(), nullable=False)
    )
    op.create_index(
        op.f("ix_reliability_tests_division_term_id"),
        "reliability_tests",
        ["division_term_id"],
    )
    op.create_foreign_key(
        op.f("fk_reliability_tests_division_term_id_vocabulary_terms"),
        "reliability_tests",
        "vocabulary_terms",
        ["division_term_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_reliability_tests_division_name",
        "reliability_tests",
        ["division_term_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_column("reliability_tests", "workspace_id")


def downgrade() -> None:
    op.add_column("reliability_tests", sa.Column("workspace_id", sa.Uuid(), nullable=False))
    op.drop_index("uq_reliability_tests_division_name", table_name="reliability_tests")
    op.drop_column("reliability_tests", "division_term_id")
    op.create_index(
        "uq_reliability_tests_workspace_name",
        "reliability_tests",
        ["workspace_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.add_column(
        "workspaces",
        sa.Column("reliability_owner", sa.Boolean(), server_default="false", nullable=False),
    )
    op.drop_column("workspaces", "division_term_id")
