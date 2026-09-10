"""구동 방식을 축으로 올린다 — 형태·교정 기관과 같은 이유.

`electromechanical`·`servohydraulic` 이 화면에 영어 그대로 떴고, 「유압식만」 으로 거를
수도 없었다. 그런데 **무엇으로 힘을 내나는 그 장비가 무엇을 할 수 있나와 곧장
이어진다** — 유압은 큰 하중을, 전기동력은 높은 주파수를, 진자는 충격을 낸다. 고르는
사람이 실제로 묻는 축이다.

값의 `code` 에 원본 슬러그를 남긴다(0009 와 같은 규칙). 이름을 한글로 바꿔도 반입이
code 로 찾으므로 안 깨진다.

Revision ID: 0010_drive_axis
Revises: 0009_vocabulary_domains
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0010_drive_axis"
down_revision = "0009_vocabulary_domains"
branch_labels = None
depends_on = None

_AXIS = (
    "drive",
    "구동 방식",
    "catalog",
    "open",
    36,
    "전기기계식·유압식·진자식처럼 무엇으로 힘을 내나. 유압은 큰 하중을, 전기동력은 높은 "
    "주파수를, 진자는 충격을 낸다 — 할 수 있는 시험이 여기서 갈린다.",
)

_ONTOLOGY = (
    Path(__file__).resolve().parents[3] / "source" / "catalog" / "ontology" / "drives.json"
)


def _labels() -> dict[str, str]:
    """원본 슬러그 -> 사람이 읽는 이름. 파일이 없으면 슬러그를 그대로 쓴다 —
    배포 묶음에 `source/` 가 없다고 스키마 이전이 멈추면 안 된다."""
    if not _ONTOLOGY.exists():
        return {}
    data = json.loads(_ONTOLOGY.read_text(encoding="utf-8"))
    return {
        row["id"]: (row.get("label_ko") or row.get("label") or row["id"])
        for row in data.get("drives", [])
    }


def _compare_key(value: str) -> str:
    """`shared.text.compare_key` 와 같은 규칙. 마이그레이션은 **그때의 코드**로 돈다."""
    return "".join(value.split()).lower()


def upgrade() -> None:
    bind = op.get_bind()
    slug, label, domain, policy, order, description = _AXIS

    axis_id = bind.execute(
        sa.text("select id from vocabularies where slug = :slug"), {"slug": slug}
    ).scalar()
    if axis_id is None:
        axis_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "insert into vocabularies "
                "(id, slug, label, domain, entry_policy, sort_order, description) "
                "values (:id, :slug, :label, :domain, :policy, :order, :description)"
            ),
            {
                "id": axis_id,
                "slug": slug,
                "label": label,
                "domain": domain,
                "policy": policy,
                "order": order,
                "description": description,
            },
        )

    op.add_column("equipment_series", sa.Column("drive_term_id", sa.Uuid(), nullable=True))
    op.create_index("ix_equipment_series_drive_term_id", "equipment_series", ["drive_term_id"])
    op.create_foreign_key(
        "fk_equipment_series_drive_term_id_vocabulary_terms",
        "equipment_series",
        "vocabulary_terms",
        ["drive_term_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    labels = _labels()
    rows = bind.execute(
        sa.text(
            "select distinct drive from equipment_series where drive is not null and drive <> ''"
        )
    ).fetchall()
    for (code,) in rows:
        value = labels.get(code, code)
        key = _compare_key(value)
        term_id = bind.execute(
            sa.text(
                "select id from vocabulary_terms "
                "where vocabulary_id = :axis and normalized = :key"
            ),
            {"axis": axis_id, "key": key},
        ).scalar()
        if term_id is None:
            term_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "insert into vocabulary_terms "
                    "(id, vocabulary_id, value, normalized, code, attributes, status, usage_count) "
                    "values (:id, :axis, :value, :key, :code, '{}', 'active', 0)"
                ),
                {"id": term_id, "axis": axis_id, "value": value, "key": key, "code": code},
            )
        bind.execute(
            sa.text("update equipment_series set drive_term_id = :term where drive = :code"),
            {"term": term_id, "code": code},
        )
    op.drop_column("equipment_series", "drive")

    bind.execute(
        sa.text(
            "update vocabulary_terms t set usage_count = ("
            "  select count(*) from equipment_series s where s.drive_term_id = t.id"
            ") where t.vocabulary_id = :axis"
        ),
        {"axis": axis_id},
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "equipment_series",
        sa.Column("drive", sa.String(30), server_default="", nullable=False),
    )
    # 원본 슬러그는 값의 code 에 남아 있다 — 그것으로 되돌린다.
    bind.execute(
        sa.text(
            "update equipment_series s set drive = coalesce(t.code, '') "
            "from vocabulary_terms t where t.id = s.drive_term_id"
        )
    )
    op.drop_constraint(
        "fk_equipment_series_drive_term_id_vocabulary_terms",
        "equipment_series",
        type_="foreignkey",
    )
    op.drop_index("ix_equipment_series_drive_term_id", table_name="equipment_series")
    op.drop_column("equipment_series", "drive_term_id")
