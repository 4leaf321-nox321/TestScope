"""4. 기종 — 보유 장비가 가리키는 것. 사양값은 values 가 담는다.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.accounts.models import User
from app.modules.equipment.models import (
    EquipmentModel,
    EquipmentSeries,
    SpecSource,
)
from app.modules.vocabulary.specs import (
    SpecDefinition,
)
from app.shared.text import clean, compare_key
from catalog_import.definitions import (
    _alias_targets,
    _promotable,
)
from catalog_import.source import (
    Catalog,
)
from catalog_import.values import (
    _as_text,
    _free_labels,
    _import_specs,
)


def _model_note(row: dict[str, Any]) -> str | None:
    """기종에 붙는 단서. **`uncertain` 을 여기 남긴다.**

    원본이 「이 기종의 표를 잘못 읽었을 수 있다」 고 표시한 것이 27건 있다. 그것을
    안 옮기면 의심스러운 숫자가 확인된 숫자와 똑같이 앉아 있고, 그때 그 사실을
    아는 사람은 아무도 없다 — 실제로 첫 반입이 그랬다(ADR 0006).
    """
    parts: list[str] = []
    if row.get("uncertain"):
        parts.append("원본 확인 필요 — 카탈로그의 표를 잘못 읽었을 수 있습니다.")
    if row.get("note"):
        parts.append(str(row["note"]))
    return "\n".join(parts) or None


def step_models(
    db: Session,
    cat: Catalog,
    series: dict[str, EquipmentSeries],
    form_factors: dict[str, uuid.UUID],
    actor: User | None,
) -> tuple[int, int, int, int]:
    """4. 기종과 그 사양값. **수치가 갈리는 자리**(ADR 0006).

    ## 계열 사양표(limits)를 어떻게 다루나

    기종이 **하나뿐인 계열**에서는 그것이 곧 그 기종의 사양이다 — 애매할 것이 없다.
    기종이 여럿이면 계열의 limits 는 **봉투**다: 0.5~300 kN 은 어느 기종의 값도
    아니다. 그것을 기종 사양으로 들이면 0.5 kN 짜리가 300 kN 된다고 답한다.
    그래서 봉투는 계열의 비고에 원문으로 남기고, 수치로는 안 들인다(ADR 0003).
    """
    definitions = {row.key: row for row in db.scalars(select(SpecDefinition))}
    sources = {row.path: row for row in db.scalars(select(SpecSource))}
    # 온톨로지에서 승격한 키 -> (정의 key, 배율 1). 원본이 이미 그 단위로 적는다.
    promoted = {row["source_key"]: (row["key"], 1.0) for row in _promotable(cat)}
    # 온톨로지가 선언한 별칭·단위 변형. **손 매핑표보다 뒤에 본다** — 거기에는
    # 이쪽만 아는 판단(정의 이름이 다른 것)이 들어 있다.
    aliases = _alias_targets(db, cat)
    free_labels = _free_labels(cat)
    marker = "원본 확인 필요"
    models = values = flagged = kept = 0

    for obj in cat.objects:
        parent = series[obj["id"]]
        first_source = (obj.get("sources") or [{}])[0].get("file")
        source = sources.get(first_source) if first_source else None
        # 기종이 없는 객체는 계열 이름을 기종으로 하나 세운다 — 카탈로그가 기종을 안 나눈
        # 장비가 실재한다. 다만 **보탬 객체**(supplements)는 본 객체의 계열에 시험 항목만
        # 보태는 것이라 기종을 세우면 안 된다 — 세우면 계열 이름을 단 빈 기종이 12개 생겨
        # 「사양 없는 기종」 으로 서 있었다.
        rows = obj.get("models") or (
            [] if obj.get("supplements") else [{"model": obj["name"]}]
        )

        made_here: list[EquipmentModel] = []
        for row in rows:
            name = clean(str(row.get("model") or obj["name"]))
            key = compare_key(name)
            found = db.scalar(
                select(EquipmentModel).where(
                    EquipmentModel.series_id == parent.id, EquipmentModel.normalized == key
                )
            )
            if found is None:
                found = EquipmentModel(
                    series_id=parent.id,
                    name=name,
                    normalized=key,
                    form_factor_term_id=form_factors.get(
                        row.get("form_factor") or obj.get("form_factor") or ""
                    ),
                    spec_note=_model_note(row),
                    created_by_id=actor.id if actor else None,
                )
                db.add(found)
                db.flush()
                models += 1
            elif row.get("uncertain") and marker not in (found.spec_note or ""):
                # **이것만 예외로 기존 행을 고친다.** 값을 덮는 것이 아니라 빠진
                # 경고를 채우는 것이고, 안 채우면 의심스러운 숫자가 확인된 숫자와
                # 똑같이 앉아 있는다. 사람이 적어 둔 비고는 뒤에 그대로 남긴다.
                found.spec_note = "\n".join(
                    x for x in (_model_note(row), found.spec_note) if x
                )
                flagged += 1
            made_here.append(found)
            values += _import_specs(
                db,
                found,
                row.get("specs") or {},
                definitions,
                source,
                promoted,
                aliases,
                free_labels,
            )
            # **원문을 통째로 남긴다.** 정의가 없는 키가 950종 넘고, 그 값은
            # 지금까지 버려지고 있었다 — 아는 것은 사양값으로, 전부는 여기에.
            raw = dict(row.get("specs") or {})
            if row.get("materialtwin"):
                # MaterialTwin 원문(설명·주석·능력행)도 통째로. 사양 칸에 못 담은 시편
                # 조건·정확도·범위가 전부 여기 있다 — 「기종에 있는 데이터는 모두」.
                raw["materialtwin"] = row["materialtwin"]
            if raw and not found.raw_specs:
                found.raw_specs = raw
                kept += 1

        limits = obj.get("limits") or {}
        if limits and len(made_here) == 1:
            values += _import_specs(
                db, made_here[0], limits, definitions, source, promoted, aliases
            )
        if limits and not parent.raw_limits:
            kept += 1
            # 봉투는 수치로 안 들이지만(ADR 0006) **원문은 남긴다** — 사람이 읽을
            # 값이고, 기종 사양이 빈 계열에서는 이것이 유일한 근거다.
            parent.raw_limits = limits
        if limits and len(made_here) > 1:
            envelope = " · ".join(
                f"{key} {_as_text(raw)}" for key, raw in sorted(limits.items())
            )
            block = f"[계열 사양 봉투] {envelope}"
            if not (parent.spec_note or "").startswith("[계열 사양 봉투]"):
                parent.spec_note = (
                    f"{block}\n{parent.spec_note}" if parent.spec_note else block
                )
        db.flush()
    return models, values, flagged, kept
