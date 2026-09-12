"""값의 코드를 축 안에서 하나로 — 반입이 이름 대신 코드로 값을 찾게 되면서.

관리 화면이 이름을 고칠 수 있게 된 순간, 이름으로 찾는 반입은 「인장」 을 「인장 시험」 으로
바꾼 다음 「인장」 을 또 만든다. 그래서 반입이 코드(온톨로지 id)로 찾는다 — 그러려면 한 축에
같은 코드가 둘이면 안 된다. NULL 은 여럿이어도 된다: 코드 없는 값이 대부분이다.

Revision ID: 0016_term_code_unique
Revises: 0015_vocabulary_attribute_schema
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_term_code_unique"
down_revision = "0015_vocabulary_attribute_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_vocabulary_terms_code",
        "vocabulary_terms",
        ["vocabulary_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_vocabulary_terms_code", table_name="vocabulary_terms")
