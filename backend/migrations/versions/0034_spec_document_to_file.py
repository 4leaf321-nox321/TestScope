"""규격서는 값이 아니라 **파일**이다 — 축과 칸을 걷어낸다.

「규격서」 를 기준정보 축(`spec_document`)의 값으로 두고 신뢰성 시험이 그것을 고르게
만들어 두었었다. 그런데 실제로 필요한 것은 **문서 그 자체**였다 — 번호만 있고 원문이
없으면 읽을 수가 없다.

그리고 여러 신뢰성 시험이 한 문서를 인용한다. 시험마다 값을 고르게 두면 같은 문서
설명을 시험마다 다시 적게 되므로, **규격(`test_methods`)에 파일을 붙이고 시험은 「참조
규격」 으로 가리킨다** — 그 칸(`reliability_reference_method`, kind=method)은 이미 있다.

**값이 있으면 안 지운다.** 개발 DB 는 0건이지만 운영에서 누가 적어 두었을 수 있고, 그때는
지우는 것이 그 사람의 입력을 조용히 버리는 일이 된다.

Revision ID: 0034_spec_document_to_file
Revises: 0033_method_test_items
"""

from __future__ import annotations

from alembic import op

revision = "0034_spec_document_to_file"
down_revision = "0033_method_test_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 신뢰성 시험의 「규격서」 칸 — 적힌 값이 없을 때만.
    op.execute(
        """
        DELETE FROM attribute_definitions d
        WHERE d.key = 'reliability_spec_document'
          AND NOT EXISTS (SELECT 1 FROM attribute_values v WHERE v.definition_id = d.id)
        """
    )
    # 2. 축 — 값이 없고, 그 축을 가리키는 속성 정의도 없을 때만.
    op.execute(
        """
        DELETE FROM vocabularies x
        WHERE x.slug = 'spec_document'
          AND NOT EXISTS (SELECT 1 FROM vocabulary_terms t WHERE t.vocabulary_id = x.id)
          AND NOT EXISTS (
              SELECT 1 FROM attribute_definitions d WHERE d.vocabulary_id = x.id
          )
        """
    )


def downgrade() -> None:
    # 되돌리지 않는다. 씨앗(`ensure_reference_data`)에서 뺐으므로 다시 심을 자리가 없고,
    # 빈 축을 되살려 봐야 화면에 쓸모없는 칸이 하나 서는 것뿐이다.
    pass
