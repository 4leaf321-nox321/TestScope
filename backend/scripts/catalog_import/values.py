"""4-a. 사양값 — 원본의 값을 정의의 칸에 담는다. 못 담으면 「이 기종만의 사양」.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.equipment.models import (
    EquipmentModel,
    ModelFreeSpec,
    ModelSpecValue,
    SpecSource,
)
from app.modules.vocabulary.catalog_specs import (
    DIMENSION_SOURCES,
    MAX_ONLY_SOURCES,
    OPTION_RANGE_SOURCES,
    RANGE_PAIR_SOURCES,
    SOURCE_SPEC_MAP,
    TEMPERATURE_PAIR,
)
from app.modules.vocabulary.specs import (
    SpecDefinition,
)
from catalog_import.source import (
    Catalog,
    _ontology,
    _variant_of,
)


def _numbers(raw: Any, factor: float) -> tuple[float | None, float | None, str | None]:
    """원본 값에서 (최소, 최대, 단서) 를 뽑는다.

    원본은 네 모양으로 온다: 수치 하나 · `{min,max}` · `{values:[…]}` · 문장.
    앞의 셋만 숫자가 된다.
    """
    note = None
    if isinstance(raw, bool):
        return None, None, None
    if isinstance(raw, int | float):
        return raw * factor, raw * factor, None
    if isinstance(raw, dict):
        note = raw.get("note")
        if raw.get("uncertain"):
            # **원본 표를 잘못 읽었을 수 있다는 표시다.** 조용히 들이면 그것이
            # 진실이 된다 — 화면이 볼 수 있게 값 옆에 남긴다.
            note = f"{note} — 원본 확인 필요" if note else "원본 확인 필요"
        low, high = raw.get("min"), raw.get("max")
        values = [one for one in (raw.get("values") or []) if isinstance(one, int | float)]
        if low is None and values:
            low = min(values)
        if high is None and values:
            high = max(values)
        if low is None and high is None:
            return None, None, note
        return (
            low * factor if isinstance(low, int | float) else None,
            high * factor if isinstance(high, int | float) else None,
            note,
        )
    return None, None, None


def _fmt(number: float) -> str:
    """187.5 는 187.5 로, 1000.0 은 1000 으로 — 비고에 `.0` 이 줄줄이 붙지 않게."""
    return str(int(number)) if float(number).is_integer() else str(number)


def _as_text(raw: Any) -> str | None:
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, list):
        return " · ".join(str(one) for one in raw) or None
    if isinstance(raw, dict):
        values = raw.get("values")
        if values:
            return " · ".join(str(one) for one in values)
        parts = [f"{k} {v}" for k, v in raw.items() if k not in ("note", "uncertain")]
        return " · ".join(parts) or raw.get("note")
    if raw is None:
        return None
    return str(raw)


def _value_fields(
    definition: SpecDefinition, raw: Any, factor: float
) -> dict[str, Any] | None:
    """정의의 종류에 맞는 칸을 채운다. 못 담으면 None.

    **틀린 칸에 담긴 값은 조용히 사라진다.** 구간 사양에 수치만 넣으면 저장은 되지만
    화면은 아무것도 못 그리고, 그때 사람은 "반입이 안 됐다" 고 말한다.
    """
    low, high, note = _numbers(raw, factor)

    if definition.kind == "range":
        if low is None and high is None:
            return None
        # 낱개 목록(경도계 하중 「500 · 750 · 1000」)은 양끝만 남기면 「187.5 로 되나」
        # 를 못 답한다 — 목록을 비고에 남긴다. 둘이면 그냥 구간이다.
        listed = (
            [one for one in raw.get("values") or [] if isinstance(one, int | float)]
            if isinstance(raw, dict)
            else []
        )
        if len(listed) > 2:
            shown = " · ".join(_fmt(one * factor) for one in listed)
            note = " · ".join(x for x in (note, f"고를 수 있는 값 {shown}") if x)
        return {"num_min": low, "num_max": high, "note": note}
    if definition.kind == "number":
        picked = low if definition.reflect_as == "min" else high
        if picked is None:
            return None
        extra = None
        if low is not None and high is not None and low != high:
            # 수치 한 칸에 구간이 왔다. **버리지 않고 비고에 원문을 남긴다.**
            extra = f"원문 {low} ~ {high}"
        return {"num_value": picked, "note": " · ".join(x for x in (note, extra) if x)}
    if definition.kind == "boolean":
        text = _as_text(raw)
        if isinstance(raw, bool):
            return {"bool_value": raw, "note": None}
        if text is None:
            return None
        # `{"values": ["optional"]}` 은 「옵션으로 붙는다」 — 없다가 아니다.
        yes = any(word in text.lower() for word in ("yes", "optional", "true", "있"))
        return {"bool_value": yes, "note": text if "optional" in text.lower() else None}
    text = _as_text(raw)
    if text is None:
        return None
    return {"text_value": text[:2000], "note": note}


def _put_spec(
    db: Session,
    model: EquipmentModel,
    definition: SpecDefinition,
    raw: Any,
    factor: float,
    *,
    taken: set[uuid.UUID],
    extra_note: str | None,
    source: SpecSource | None,
    page: int | None,
) -> bool:
    """사양 값 하나를 넣는다. **이미 있으면 안 덮는다** — 손으로 고쳐 둔 것이 더 낫다.

    `taken` 을 함께 보는 이유: 원본의 서로 다른 키가 같은 정의로 모인다
    (`power_W` 와 `power_kW` 는 둘 다 소비 전력이다). DB 만 보면 아직 flush 안 된
    같은 배치의 앞줄이 안 보여서, 유일 제약이 반입 도중에 터진다 — 실제로 그렇게 겪었다.
    """
    if definition.id in taken:
        # 있는 값은 안 덮는다. 다만 **부속 표시만은 켠다** — 표시가 없던 시절에 들어온
        # 값에 원본이 「옵션 부속 기준」 이라고 적혀 있으면, 그 값은 지금 검색이 갖고
        # 있지도 않은 챔버를 전제로 답하는 자리다. 켜는 쪽은 더 조심스러워지는 방향뿐이다.
        if isinstance(raw, dict) and raw.get("requires_accessory"):
            held = db.scalar(
                select(ModelSpecValue).where(
                    ModelSpecValue.model_id == model.id,
                    ModelSpecValue.definition_id == definition.id,
                )
            )
            if held is not None and not held.requires_accessory:
                held.requires_accessory = True
        return False
    fields = _value_fields(definition, raw, factor)
    if fields is None:
        return False
    taken.add(definition.id)
    note = " · ".join(x for x in (fields.pop("note", None), extra_note) if x) or None
    # **부속 표시를 버리지 않는다.** 온톨로지가 「이 온도는 옵션 챔버 기준」 이라고
    # 적은 것(`requires_accessory`)이 여기서 빠지면 검색이 그 챔버를 전제로 답한다.
    accessory = isinstance(raw, dict) and bool(raw.get("requires_accessory"))
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            note=note,
            requires_accessory=accessory,
            source_id=source.id if source else None,
            source_page=page,
            **fields,
        )
    )
    return True


def _merge_temperature(
    db: Session,
    model: EquipmentModel,
    raw_specs: dict[str, Any],
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> bool:
    """상·하한을 두 키로 나눠 적은 온도를 **구간 하나로 합친다.**

    열충격 챔버가 그렇게 적는다 — 고온조 `[50, 200]`, 저온조 `[-65, 0]`. 둘을 따로
    두면 어느 쪽도 「시험 온도」 가 아니어서 그 챔버는 온도로 검색되지 않는다.
    """
    low_key, high_key, target = TEMPERATURE_PAIR
    if low_key not in raw_specs and high_key not in raw_specs:
        return False
    definition = definitions.get(target)
    if definition is None:
        return False

    bounds: list[float] = []
    for key in (low_key, high_key):
        raw = raw_specs.get(key)
        if isinstance(raw, int | float):
            bounds.append(float(raw))
        elif isinstance(raw, list):
            bounds.extend(float(one) for one in raw if isinstance(one, int | float))
        elif isinstance(raw, dict):
            for edge in ("min", "max"):
                if isinstance(raw.get(edge), int | float):
                    bounds.append(float(raw[edge]))
    if not bounds:
        return False
    return _put_spec(
        db,
        model,
        definition,
        {"min": min(bounds), "max": max(bounds)},
        1.0,
        taken=taken,
        extra_note="고온조·저온조 범위를 합침",
        source=source,
        page=None,
    )


def _numbers_of(raw: Any) -> list[float]:
    """배열·중첩 배열에서 수치만 훑어 낸다. 구성 배열과 이중 레인지가 둘 다 온다."""
    out: list[float] = []
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return [float(raw)]
    if isinstance(raw, list):
        for one in raw:
            out.extend(_numbers_of(one))
    return out


def _import_option_range(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definition: SpecDefinition | None,
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> bool:
    """카탈로그가 여러 값으로 적어 온 것을 **구간 하나**로 담는다.

    두 경우가 같은 모양으로 온다:

        actuator_ratings_kN [15, 25]        고를 수 있는 정격 — 그 대는 둘 중 하나다
        force_ranges_kN [4000, …, 80]       다중 레인지 로드셀 — 한 대가 전부 갖는다

    **둘 다 구간이 맞는 답이다.** 앞은 「이 기종은 15~25 로 나온다」 이고 뒤는 「80
    에서 4000 까지 잰다」 다. 최대값만 담으면 앞의 경우 15 짜리를 가진 부서가
    「25 kN 됩니까」 에 된다고 답하고, 뒤의 경우 저레인지 측정이 사라진다.

    **원문 전부를 비고에 남긴다.** 양끝만 남기면 중간 값들이 사라져 「400 kN 레인지도
    있나」 에 답할 수 없다.
    """
    if definition is None:
        return False
    values = _numbers_of(raw)
    if not values:
        return False
    note = None
    if len(values) > 2:
        note = "카탈로그가 적어 온 값들: " + ", ".join(
            f"{one:g}" for one in sorted(set(values), reverse=True)
        )
    return _put_spec(
        db,
        model,
        definition,
        {"min": min(values), "max": max(values)},
        1.0,
        taken=taken,
        extra_note=note,
        source=source,
        page=None,
    )


def _import_range_pair(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definitions: dict[str, SpecDefinition],
    targets: tuple[str, str],
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> int:
    """저·고 두 레인지를 **정의 둘로** 나눠 담는다.

    합쳐서 0.6~2600 으로 담으면 「100 W 부하 되나」 에는 맞게 답하지만, 레인지마다
    분해능이 다르다는 사실이 사라진다 — 전자부하를 고르는 사람이 보는 것이 그것이다.
    """
    if not isinstance(raw, list) or len(raw) != 2:
        return 0
    made = 0
    for one, key in zip(raw, targets, strict=True):
        definition = definitions.get(key)
        if definition is None:
            continue
        values = _numbers_of(one)
        if not values:
            continue
        payload: Any = (
            {"min": min(values), "max": max(values)}
            if definition.kind == "range"
            else values[0]
        )
        if _put_spec(
            db,
            model,
            definition,
            payload,
            1.0,
            taken=taken,
            extra_note=None,
            source=source,
            page=None,
        ):
            made += 1
    return made


def _import_max_only(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definition: SpecDefinition | None,
    source: SpecSource | None,
    taken: set[uuid.UUID],
) -> bool:
    """상한만 적힌 값을 구간의 **최대값으로만** 담는다.

    수치 하나를 구간에 그냥 넣으면 400~400 이 된다 — 「400도까지」 가 아니라 「400도
    에서만」 이 되고, 그러면 검색이 100도를 물을 때 그 장비가 조용히 빠진다.
    """
    if definition is None:
        return False
    values = _numbers_of(raw)
    if not values:
        return False
    return _put_spec(
        db,
        model,
        definition,
        {"max": max(values)},
        1.0,
        taken=taken,
        extra_note=None,
        source=source,
        page=None,
    )


#: 사양이 아니라 다른 자리로 가는 키 — 여기 있는 것은 「이 기종만의 사양」 으로도 안 간다.
_NOT_FREE_SPEC = {"note", "uncertain", "materialtwin"}

#: 이번 반입이 만든 「이 기종만의 사양」 줄 수. 사양값과 따로 센다 — 섞으면 「사양값 1848」
#: 이 정의 값처럼 읽힌다.
_FREE_MADE = 0


def _put_free_spec(
    db: Session,
    model: EquipmentModel,
    key: str,
    raw: Any,
    source: SpecSource | None,
    labels: dict[str, tuple[str, str | None, str]],
) -> bool:
    """정의 없는 키를 「이 기종만의 사양」 으로. **있는 줄은 안 덮는다** — 사람이 이름을 고쳐
    둔 것이 재반입에 돌아오면 안 된다. 품번(`not_spec`)은 사양이 아니라 안 들인다."""
    if key in _NOT_FREE_SPEC:
        return False
    label, unit, role = labels.get(key, (key, None, "measure"))
    if role == "not_spec":
        return False
    text = _as_text(raw)
    if not text:
        return False
    exists = db.scalar(
        select(ModelFreeSpec).where(
            ModelFreeSpec.model_id == model.id, ModelFreeSpec.source_key == key
        )
    )
    if exists is not None:
        return False
    global _FREE_MADE
    _FREE_MADE += 1
    db.add(
        ModelFreeSpec(
            model_id=model.id,
            label=label[:150],
            value_text=text[:4000],
            unit=unit or None,
            note=(raw.get("note") if isinstance(raw, dict) else None),
            source_key=key,
            origin="catalog",
            source_id=source.id if source else None,
        )
    )
    return True


def _free_labels(cat: Catalog) -> dict[str, tuple[str, str | None, str]]:
    """온톨로지 키 -> (라벨, 단위, 역할). 서술 키(`control` → 「제어 방식」)가 여기서 이름을
    얻는다 — 정의로는 안 서지만 「이 기종만의 사양」 으로는 들어간다."""
    out: dict[str, tuple[str, str | None, str]] = {}
    # 등록 대기열(`suggested_keys.json`)은 라벨이 비어 있지만 **키 이름에서 읽은 단위**는
    # 있다(`min_torque_nNm` → nNm). 이름은 안 지어내되 단위는 그 파일의 것을 쓴다.
    queued = cat.root / "ontology" / "suggested_keys.json"
    if queued.exists():
        for row in json.loads(queued.read_text(encoding="utf-8")).get("keys") or []:
            out[row["key"]] = (
                row["key"],
                row.get("unit") or None,
                row.get("role") or "measure",
            )
    for row in _ontology(cat)["keys"]:
        entry = (
            row.get("label") or row["key"],
            row.get("unit") or None,
            row.get("role") or "measure",
        )
        out[row["key"]] = entry
        for alias in row.get("aliases") or []:
            out.setdefault(alias, entry)
    return out


def _import_specs(
    db: Session,
    model: EquipmentModel,
    raw_specs: dict[str, Any],
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    promoted: dict[str, tuple[str, float]],
    aliases: dict[str, tuple[str, float]],
    free_labels: dict[str, tuple[str, str | None, str]] | None = None,
) -> int:
    free_labels = free_labels or {}
    taken = set(
        db.scalars(
            select(ModelSpecValue.definition_id).where(ModelSpecValue.model_id == model.id)
        )
    )
    made = 0
    if _merge_temperature(db, model, raw_specs, definitions, source, taken):
        made += 1
    for key, raw in raw_specs.items():
        if key in ("note", "uncertain", TEMPERATURE_PAIR[0], TEMPERATURE_PAIR[1]):
            continue
        extra_note = None
        variant = _variant_of(key)
        if variant is not None:
            key, extra_note = variant
        # 원본이 같은 것을 여러 이름으로 적는다. 치수는 세 칸으로 나뉜다.
        target = DIMENSION_SOURCES.get(key)
        if target is None and key.startswith("footprint_"):
            target = DIMENSION_SOURCES["footprint_mm"]
        if target is not None:
            made += _import_dimensions(db, model, raw, definitions, source, taken, target)
            continue
        # 원본이 한 칸에 두 벌·여러 구성·상한만 적어 오는 자리들. 그냥 담으면 각각
        # 다른 방식으로 틀린 값이 된다(catalog_specs 의 세 표에 이유를 적어 뒀다).
        pair = RANGE_PAIR_SOURCES.get(key)
        if pair is not None:
            made += _import_range_pair(db, model, raw, definitions, pair, source, taken)
            continue
        if key in OPTION_RANGE_SOURCES:
            if _import_option_range(
                db, model, raw, definitions.get(OPTION_RANGE_SOURCES[key]), source, taken
            ):
                made += 1
            continue
        if key in MAX_ONLY_SOURCES:
            if _import_max_only(
                db, model, raw, definitions.get(MAX_ONLY_SOURCES[key]), source, taken
            ):
                made += 1
            continue
        # 손으로 이어 둔 것이 먼저다 — 거기에는 단위 환산 같은 판단이 들어 있다.
        # 없으면 온톨로지에서 승격한 이름으로 찾는다.
        mapped = SOURCE_SPEC_MAP.get(key) or aliases.get(key) or promoted.get(key)
        if mapped is None:
            # **정의가 없는 키는 「이 기종만의 사양」 으로 들인다.** 전에는 원문 JSON 에만
            # 남아 화면에서 고칠 수도 정의로 올릴 수도 없었다. 이름은 온톨로지가 알면 그
            # 라벨, 모르면 원본 키 그대로 — 지어내지 않는다.
            _put_free_spec(db, model, key, raw, source, free_labels)
            continue
        definition = definitions.get(mapped[0])
        if definition is None:
            _put_free_spec(db, model, key, raw, source, free_labels)
            continue
        if _put_spec(
            db,
            model,
            definition,
            raw,
            mapped[1],
            taken=taken,
            extra_note=extra_note,
            source=source,
            page=None,
        ):
            made += 1
    db.flush()
    return made


def _import_dimensions(
    db: Session,
    model: EquipmentModel,
    raw: Any,
    definitions: dict[str, SpecDefinition],
    source: SpecSource | None,
    taken: set[uuid.UUID],
    target: tuple[str, str, str],
) -> int:
    """치수를 가로·세로·높이 세 칸으로 나눈다.

    원본이 `[W, D, H]` 로도 `{"W":…}` 로도 온다. **순서를 지어내지 않는다** — 배열의
    뜻이 카탈로그마다 갈릴 수 있어서, 이름표가 있는 쪽만 이름으로 믿는다.

    `target` 이 바깥 치수인지 안쪽 치수인지를 정한다 — 둘은 다른 물음에 답한다.
    """
    values: list[float | None] = []
    if isinstance(raw, dict):
        keys = {k.lower(): v for k, v in raw.items()}
        values = [
            keys.get("w") or keys.get("width"),
            keys.get("d") or keys.get("depth"),
            keys.get("h") or keys.get("height"),
        ]
    elif isinstance(raw, list) and len(raw) == 3:
        values = list(raw)
    else:
        return 0

    made = 0
    for key, value in zip(target, values, strict=False):
        definition = definitions.get(key)
        if definition is None or not isinstance(value, int | float):
            continue
        if _put_spec(
            db,
            model,
            definition,
            value,
            1.0,
            taken=taken,
            extra_note=None,
            source=source,
            page=None,
        ):
            made += 1
    return made
