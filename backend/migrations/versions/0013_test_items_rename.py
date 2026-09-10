"""「역량」 을 「시험 항목」 으로 — 표 이름까지 바꾼다.

「역량」 은 무엇이 담기는지 말해 주지 않았다. 담기는 것은 **그 장비가 하는 시험 항목과
그 조건**이고, 기준정보의 축 이름은 이미 「시험 항목」 이었다 — 같은 것을 두 이름으로
부르고 있었던 셈이다.

    capabilities              -> equipment_test_items      장비가 하는 시험 항목
    capability_limits         -> equipment_test_conditions 그 항목의 시험 조건
    model_capabilities        -> series_test_items         계열이 하는 시험 항목
    model_capability_limits   -> series_test_conditions
    model_capability_methods  -> series_test_item_methods  그 항목이 인용하는 규격

계열 것을 `model_…` 로 부르던 것도 함께 고친다. **붙는 자리는 기종이 아니라 계열이다**
(ADR 0006) — 이름이 표의 뜻과 어긋나 있었다.

제약·인덱스 이름도 함께 바꾼다. 안 바꾸면 표 이름과 제약 이름이 어긋난 채로 남고,
`alembic check` 가 매번 「고칠 것이 있다」 고 말한다.

Revision ID: 0013_test_items_rename
Revises: 0012_cited_methods
"""

from __future__ import annotations

from alembic import op

revision = "0013_test_items_rename"
down_revision = "0012_cited_methods"
branch_labels = None
depends_on = None

#: 옛 이름 -> 새 이름.
TABLES = {
    "capabilities": "equipment_test_items",
    "capability_limits": "equipment_test_conditions",
    "model_capabilities": "series_test_items",
    "model_capability_limits": "series_test_conditions",
    "model_capability_methods": "series_test_item_methods",
}

#: 칸 이름도 표를 따라간다.
COLUMNS = {
    "equipment_test_conditions": [("capability_id", "equipment_test_item_id")],
    "series_test_conditions": [("model_capability_id", "series_test_item_id")],
    "series_test_item_methods": [("model_capability_id", "series_test_item_id")],
}

#: 제약과 인덱스. (표, 옛 이름, 새 이름)
RENAMES = [
    ("equipment_test_items", "pk_capabilities", "pk_equipment_test_items"),
    ("equipment_test_items", "uq_capabilities_triple", "uq_equipment_test_items_triple"),
    (
        "equipment_test_items",
        "fk_capabilities_created_by_id_users",
        "fk_equipment_test_items_created_by_id_users",
    ),
    (
        "equipment_test_items",
        "fk_capabilities_equipment_id_equipment",
        "fk_equipment_test_items_equipment_id_equipment",
    ),
    (
        "equipment_test_items",
        "fk_capabilities_method_id_test_methods",
        "fk_equipment_test_items_method_id_test_methods",
    ),
    (
        "equipment_test_items",
        "fk_capabilities_test_item_term_id_vocabulary_terms",
        "fk_equipment_test_items_test_item_term_id_vocabulary_terms",
    ),
    ("equipment_test_conditions", "pk_capability_limits", "pk_equipment_test_conditions"),
    (
        "equipment_test_conditions",
        "uq_capability_limits_key",
        "uq_equipment_test_conditions_key",
    ),
    (
        "equipment_test_conditions",
        "fk_capability_limits_capability_id_capabilities",
        "fk_equipment_test_conditions_equipment_test_item_id_equipment_test_items",
    ),
    (
        "equipment_test_conditions",
        "fk_capability_limits_condition_key_id_condition_keys",
        "fk_equipment_test_conditions_condition_key_id_condition_keys",
    ),
    ("series_test_items", "pk_model_capabilities", "pk_series_test_items"),
    ("series_test_items", "uq_model_capabilities_triple", "uq_series_test_items_triple"),
    (
        "series_test_items",
        "fk_model_capabilities_method_id_test_methods",
        "fk_series_test_items_method_id_test_methods",
    ),
    (
        "series_test_items",
        "fk_model_capabilities_series_id_equipment_series",
        "fk_series_test_items_series_id_equipment_series",
    ),
    (
        "series_test_items",
        "fk_model_capabilities_test_item_term_id_vocabulary_terms",
        "fk_series_test_items_test_item_term_id_vocabulary_terms",
    ),
    ("series_test_conditions", "pk_model_capability_limits", "pk_series_test_conditions"),
    (
        "series_test_conditions",
        "uq_model_capability_limits_key",
        "uq_series_test_conditions_key",
    ),
    (
        "series_test_conditions",
        "fk_model_capability_limits_condition_key_id_condition_keys",
        "fk_series_test_conditions_condition_key_id_condition_keys",
    ),
    (
        "series_test_conditions",
        "fk_model_capability_limits_model_capability_id_model_ca_4950",
        "fk_series_test_conditions_series_test_item_id_series_test_items",
    ),
    ("series_test_item_methods", "pk_model_capability_methods", "pk_series_test_item_methods"),
    (
        "series_test_item_methods",
        "uq_model_capability_methods",
        "uq_series_test_item_methods",
    ),
    (
        "series_test_item_methods",
        "fk_model_capability_methods_method_id_test_methods",
        "fk_series_test_item_methods_method_id_test_methods",
    ),
    (
        "series_test_item_methods",
        "fk_model_capability_methods_model_capability_id_model_c_269f",
        "fk_series_test_item_methods_series_test_item_id_series_test_items",
    ),
]

#: 인덱스. 제약과 달리 `alter index` 로 바꾼다.
INDEXES = [
    ("ix_capabilities_confidence", "ix_equipment_test_items_confidence"),
    ("ix_capabilities_equipment_id", "ix_equipment_test_items_equipment_id"),
    ("ix_capabilities_method_id", "ix_equipment_test_items_method_id"),
    ("ix_capabilities_test_item_term_id", "ix_equipment_test_items_test_item_term_id"),
    (
        "ix_capability_limits_capability_id",
        "ix_equipment_test_conditions_equipment_test_item_id",
    ),
    (
        "ix_capability_limits_condition_key_id",
        "ix_equipment_test_conditions_condition_key_id",
    ),
    ("ix_model_capabilities_method_id", "ix_series_test_items_method_id"),
    ("ix_model_capabilities_series_id", "ix_series_test_items_series_id"),
    ("ix_model_capabilities_test_item_term_id", "ix_series_test_items_test_item_term_id"),
    (
        "ix_model_capability_limits_condition_key_id",
        "ix_series_test_conditions_condition_key_id",
    ),
    (
        "ix_model_capability_limits_model_capability_id",
        "ix_series_test_conditions_series_test_item_id",
    ),
    ("ix_model_capability_methods_method_id", "ix_series_test_item_methods_method_id"),
    (
        "ix_model_capability_methods_model_capability_id",
        "ix_series_test_item_methods_series_test_item_id",
    ),
]


def upgrade() -> None:
    for old, new in TABLES.items():
        op.rename_table(old, new)
    for table, columns in COLUMNS.items():
        for old, new in columns:
            op.alter_column(table, old, new_column_name=new)
    for table, old, new in RENAMES:
        op.execute(f'alter table {table} rename constraint "{old}" to "{new}"')
    for old, new in INDEXES:
        op.execute(f'alter index "{old}" rename to "{new}"')


def downgrade() -> None:
    for old, new in INDEXES:
        op.execute(f'alter index "{new}" rename to "{old}"')
    for table, old, new in RENAMES:
        op.execute(f'alter table {table} rename constraint "{new}" to "{old}"')
    for table, columns in COLUMNS.items():
        for old, new in columns:
            op.alter_column(table, new, new_column_name=old)
    for old, new in TABLES.items():
        op.rename_table(new, old)
