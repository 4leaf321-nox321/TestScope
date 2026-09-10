"""기준정보 축에 **어디의 축인가**를 붙이고, 자유 문자열 둘을 축으로 올린다.

## 왜 소속이 필요한가

축이 일곱이 되면 한 목록으로는 「이게 어디 쓰이는 값이지」 를 알 수 없다. 제조사와
규격 제정기관이 나란히 서 있으면 장비를 등록하러 온 사람이 제정기관 축에 회사 이름을
넣는다 — 그리고 그 값은 아무도 안 지운다.

    equipment  보유 장비   거점 · 교정 기관
    catalog    카탈로그    장비 분류 · 제조사 · 기종 형태
    method     시험법      규격 제정기관
    common     공통        시험 항목 (개체 역량·계열 역량·시험법이 모두 가리킨다)

## 축으로 올리는 둘

**기종 형태**(`form_factor`)는 원본이 `benchtop` 으로 적어 오던 것이라 화면에 영어가
그대로 떴고, 「탁상형만」 으로 거를 수도 없었다. 값의 `code` 에 원본 슬러그를 남겨
반입이 그것으로 찾는다 — 이름을 한글로 바꿔도 반입이 안 깨진다.

**교정 기관**(`provider`)은 자유 문자열이라 같은 기관이 「한국계량측정협회」 와
「(주)한국계량측정협회」 로 갈릴 자리였다. 갈리면 「이 기관이 교정한 장비」 를 묻는
순간 절반만 답한다.

옮긴 뒤 옛 칸은 지운다. **두 벌로 두면 한쪽만 고쳐진다.**

Revision ID: 0009_vocabulary_domains
Revises: 0008_equipment_identity
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0009_vocabulary_domains"
down_revision = "0008_equipment_identity"
branch_labels = None
depends_on = None

#: 이미 있는 축이 어디 것인가. `reference.py` 의 AXES 와 같은 값이어야 한다.
_DOMAINS = {
    "test_item": "common",
    "equipment_category": "catalog",
    "manufacturer": "catalog",
    "site": "equipment",
    "standard_body": "method",
}

#: 새로 세우는 축. (slug, label, domain, entry_policy, sort_order, description)
#:
#: **설치(`reference.py`)와 같은 내용이다** — 새 설치는 거기서, 이미 도는 DB 는
#: 여기서 받는다. 둘 중 하나만 있으면 한쪽 DB 에만 축이 생긴다.
_NEW_AXES = [
    (
        "form_factor",
        "기종 형태",
        "catalog",
        "open",
        35,
        "탁상형·바닥형·휴대형처럼 그 기종이 어떤 몸을 가졌나. 자리가 나는지, 들고 갈 "
        "수 있는지가 여기서 갈린다.",
    ),
    (
        "calibration_provider",
        "교정 기관",
        "equipment",
        "open",
        45,
        "교정 성적서를 낸 곳. 자유 문자열로 두면 같은 기관이 「한국계량측정협회」 와 "
        "「(주)한국계량측정협회」 로 갈리고, 그 둘은 서로 다른 기관이 된다.",
    ),
]

_ONTOLOGY = (
    Path(__file__).resolve().parents[3]
    / "source"
    / "catalog"
    / "ontology"
    / "form_factors.json"
)


def _form_factor_labels() -> dict[str, str]:
    """원본 슬러그 -> 사람이 읽는 이름. **정본은 온톨로지다**(AGENTS.md).

    파일이 없어도 마이그레이션은 돈다 — 그때는 슬러그를 그대로 이름으로 쓴다. 배포
    묶음에 `source/` 가 없을 수 있고, 그것 때문에 스키마 이전이 멈추면 안 된다.
    """
    if not _ONTOLOGY.exists():
        return {}
    data = json.loads(_ONTOLOGY.read_text(encoding="utf-8"))
    return {
        row["id"]: (row.get("label_ko") or row.get("label") or row["id"])
        for row in data.get("form_factors", [])
    }


def _compare_key(value: str) -> str:
    """`shared.text.compare_key` 와 같은 규칙 — 공백을 지우고 소문자로.

    여기서 import 하지 않는 이유: 마이그레이션은 **그때의 코드**로 돌아야 한다.
    앱 함수가 나중에 바뀌면 이미 지나간 이전의 뜻이 함께 바뀐다.
    """
    return "".join(value.split()).lower()


def upgrade() -> None:
    bind = op.get_bind()

    # --- 축의 소속 ----------------------------------------------------------
    op.add_column(
        "vocabularies",
        sa.Column("domain", sa.String(20), server_default="common", nullable=False),
    )
    op.create_index("ix_vocabularies_domain", "vocabularies", ["domain"])
    for slug, domain in _DOMAINS.items():
        bind.execute(
            sa.text("update vocabularies set domain = :domain where slug = :slug"),
            {"domain": domain, "slug": slug},
        )

    # --- 새 축 --------------------------------------------------------------
    axis_ids: dict[str, uuid.UUID] = {}
    for slug, label, domain, policy, order, description in _NEW_AXES:
        found = bind.execute(
            sa.text("select id from vocabularies where slug = :slug"), {"slug": slug}
        ).scalar()
        if found is None:
            found = uuid.uuid4()
            bind.execute(
                sa.text(
                    "insert into vocabularies "
                    "(id, slug, label, domain, entry_policy, sort_order, description) "
                    "values (:id, :slug, :label, :domain, :policy, :order, :description)"
                ),
                {
                    "id": found,
                    "slug": slug,
                    "label": label,
                    "domain": domain,
                    "policy": policy,
                    "order": order,
                    "description": description,
                },
            )
        axis_ids[slug] = found

    def term(axis: str, value: str, code: str | None) -> uuid.UUID:
        """값 하나를 없으면 만든다. **비교키로 찾는다** — 표기가 달라도 같은 값이다."""
        key = _compare_key(value)
        found = bind.execute(
            sa.text(
                "select id from vocabulary_terms "
                "where vocabulary_id = :axis and normalized = :key"
            ),
            {"axis": axis_ids[axis], "key": key},
        ).scalar()
        if found is not None:
            return uuid.UUID(str(found))
        made = uuid.uuid4()
        bind.execute(
            sa.text(
                "insert into vocabulary_terms "
                "(id, vocabulary_id, value, normalized, code, attributes, status, usage_count) "
                "values (:id, :axis, :value, :key, :code, '{}', 'active', 0)"
            ),
            {"id": made, "axis": axis_ids[axis], "value": value, "key": key, "code": code},
        )
        return made

    # --- 기종 형태 ----------------------------------------------------------
    labels = _form_factor_labels()
    for table in ("equipment_series", "equipment_models"):
        op.add_column(table, sa.Column("form_factor_term_id", sa.Uuid(), nullable=True))
        op.create_index(f"ix_{table}_form_factor_term_id", table, ["form_factor_term_id"])
        op.create_foreign_key(
            f"fk_{table}_form_factor_term_id_vocabulary_terms",
            table,
            "vocabulary_terms",
            ["form_factor_term_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        rows = bind.execute(
            sa.text(
                # 칸 이름은 위 상수에서만 온다 — 밖에서 들어오는 값이 아니다.
                f"select distinct form_factor from {table} "
                "where form_factor is not null and form_factor <> ''"
            )
        ).fetchall()
        for (slug,) in rows:
            term_id = term("form_factor", labels.get(slug, slug), slug)
            bind.execute(
                sa.text(
                    f"update {table} set form_factor_term_id = :term where form_factor = :slug"
                ),
                {"term": term_id, "slug": slug},
            )
        op.drop_column(table, "form_factor")

    # --- 교정 기관 ----------------------------------------------------------
    op.add_column(
        "equipment_calibrations", sa.Column("provider_term_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_equipment_calibrations_provider_term_id",
        "equipment_calibrations",
        ["provider_term_id"],
    )
    op.create_foreign_key(
        "fk_equipment_calibrations_provider_term_id_vocabulary_terms",
        "equipment_calibrations",
        "vocabulary_terms",
        ["provider_term_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    providers = bind.execute(
        sa.text(
            "select distinct provider from equipment_calibrations "
            "where provider is not null and provider <> ''"
        )
    ).fetchall()
    for (name,) in providers:
        term_id = term("calibration_provider", name.strip(), None)
        bind.execute(
            sa.text(
                "update equipment_calibrations set provider_term_id = :term "
                "where provider = :name"
            ),
            {"term": term_id, "name": name},
        )
    op.drop_column("equipment_calibrations", "provider")

    # 값이 몇 군데서 쓰이는지는 기준정보 화면이 보여 준다 — 옮긴 만큼 세어 둔다.
    bind.execute(
        sa.text(
            "update vocabulary_terms t set usage_count = ("
            "  select count(*) from equipment_models m where m.form_factor_term_id = t.id"
            ") + ("
            "  select count(*) from equipment_series s where s.form_factor_term_id = t.id"
            ") + ("
            "  select count(*) from equipment_calibrations c where c.provider_term_id = t.id"
            ") where t.vocabulary_id in :axes"
        ).bindparams(sa.bindparam("axes", expanding=True)),
        {"axes": list(axis_ids.values())},
    )


def downgrade() -> None:
    # **되돌리면 값이 글자로 돌아간다.** 축에 쌓인 동의어 정리는 사라진다.
    bind = op.get_bind()

    op.add_column(
        "equipment_calibrations", sa.Column("provider", sa.String(200), nullable=True)
    )
    bind.execute(
        sa.text(
            "update equipment_calibrations c set provider = t.value "
            "from vocabulary_terms t where t.id = c.provider_term_id"
        )
    )
    op.drop_constraint(
        "fk_equipment_calibrations_provider_term_id_vocabulary_terms",
        "equipment_calibrations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_equipment_calibrations_provider_term_id", table_name="equipment_calibrations"
    )
    op.drop_column("equipment_calibrations", "provider_term_id")

    for table in ("equipment_series", "equipment_models"):
        op.add_column(
            table,
            sa.Column("form_factor", sa.String(40), server_default="", nullable=False),
        )
        bind.execute(
            sa.text(
                # 원본 슬러그는 값의 code 에 남아 있다 — 그것으로 되돌린다.
                f"update {table} x set form_factor = coalesce(t.code, '') "
                "from vocabulary_terms t where t.id = x.form_factor_term_id"
            )
        )
        op.drop_constraint(
            f"fk_{table}_form_factor_term_id_vocabulary_terms", table, type_="foreignkey"
        )
        op.drop_index(f"ix_{table}_form_factor_term_id", table_name=table)
        op.drop_column(table, "form_factor_term_id")

    op.drop_index("ix_vocabularies_domain", table_name="vocabularies")
    op.drop_column("vocabularies", "domain")
