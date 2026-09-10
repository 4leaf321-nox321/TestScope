"""등재되지 않은 사양 키의 **등록 후보를 뽑는다.**

    python tools_suggest_keys.py              후보를 ontology/suggested_keys.json 에
    python tools_suggest_keys.py --print      화면으로만

## 왜 필요한가

`condition_keys.json` 은 `limits` 키 206종을 다 통제하지만 `models[].specs` 키
1,104종은 9%뿐이다. 기종 사양은 자유 형식이라 제조사마다 제 이름으로 적는다 —
`nominal_load_kN` · `capacity_kN` · `max_load_kN` 이 다 최대 하중이다.

**남은 951종을 손으로 치는 것은 불가능하다.** 207종을 등록한 감사는 손으로 할 수
있었지만 그 다섯 배는 못 한다. 그래서 이름·값에서 뽑아낼 수 있는 것은 뽑아 두고,
사람은 `label` 과 판정만 채운다.

## 무엇을 「등재됨」 으로 세나

**반입이 다루는 키는 세지 않는다.** 온톨로지에 등재된 것만 빼고 세면 이 도구가
「948종 남았다」 고 하는데 반입은 「917종」 이라고 한다 — 계기판이 둘이면 사람은 둘 다
안 믿는다. 실제로 그랬다.

무엇을 다루는지 아는 것은 반입이므로 그쪽 표를 읽어 온다(`app.modules.vocabulary
.catalog_specs`). 못 읽으면 **그 사실을 말하고** 온톨로지 기준으로만 센다 — 조용히
다른 수를 내놓지 않는다.

## 무엇을 추측하고 무엇을 안 하나

    단위      이름의 꼬리에서 뽑는다 (`travel_resolution_um` -> um). 41% 가 갖고 있다
    차원      단위에서 되짚는다. 모르면 비운다
    모양      값을 보고 정한다 — 이름만 보면 절반이 틀린다
    별칭 후보 같은 줄기·같은 차원의 등재 키를 가리킨다. **확정하지 않는다**
    label     비운다. **사람이 채운다** — 이름을 지어내면 그것이 진실이 된다

`role` 도 추측만 한다: 값이 문장·목록뿐이면 `descriptive`, 품번처럼 보이면
`not_spec`. 틀릴 수 있으니 사람이 넘긴다.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CAT = Path(__file__).resolve().parent
ONT = CAT / "ontology"

#: 이름 꼬리에 붙는 단위. 긴 것부터 본다 — `mm2_s` 가 `s` 보다 먼저 걸려야 한다.
UNITS = (
    "mm2_s", "cd_m2", "mm_min", "K_min", "W_mK", "mbar_L_s", "K_h", "m_s", "mm2",
    "kVA", "mWh", "mNm", "kgf", "kHz", "MHz", "kPa", "MPa", "rpm", "deg", "rad",
    "pct", "ohm", "degC", "lx", "um", "nm", "kN", "kW", "VA", "Wh", "Nm", "mV",
    "mA", "uA", "kV", "mL", "ms", "us", "mg", "ug", "min", "bar", "Pa", "Hz",
    "kg", "g", "J", "L", "V", "A", "W", "N", "K", "s", "h", "m", "mm",
)

#: 단위 -> 차원. 온톨로지가 이미 쓰는 이름을 그대로 쓴다.
DIMENSIONS = {
    "mm": "length", "um": "length", "nm": "length", "m": "length",
    "mm2": "area", "kN": "force", "N": "force", "kgf": "force", "gf": "force",
    "kg": "mass", "g": "mass", "mg": "mass", "ug": "mass",
    "degC": "temperature", "K": "temperature", "K_min": "temperature_rate", "K_h": "rate",
    "Hz": "frequency", "kHz": "frequency", "MHz": "frequency",
    "V": "voltage", "kV": "voltage", "mV": "voltage",
    "A": "current", "mA": "current", "uA": "current",
    "W": "power", "kW": "power", "VA": "power", "kVA": "power",
    "Wh": "energy", "mWh": "energy", "J": "energy",
    "Nm": "torque", "mNm": "torque", "rpm": "angular_velocity", "rad": "angle",
    "deg": "angle", "s": "time", "ms": "time", "us": "time", "min": "time", "h": "time",
    "L": "volume", "mL": "volume", "bar": "pressure", "mbar": "pressure",
    "Pa": "pressure", "kPa": "pressure", "MPa": "pressure",
    "ohm": "resistance", "pct": "ratio", "lx": "illuminance", "cd_m2": "luminance",
    "mm_min": "speed", "m_s": "speed", "mm2_s": "thermal_diffusivity",
    "W_mK": "thermal_conductivity", "mbar_L_s": "leak_rate",
}

#: 사양이 아닌 것으로 보이는 이름. **품번은 사양이 아니다** — 보류 목록 1등이라
#: 사람 눈을 뺏는다.
NOT_SPEC_HINTS = ("item_no", "part_no", "model_no", "order_no", "sku", "catalog_no")


def split_unit(key: str) -> tuple[str, str]:
    """이름을 (줄기, 단위) 로 가른다. 단위가 없으면 빈 문자열."""
    for unit in UNITS:
        if key.endswith("_" + unit):
            return key[: -(len(unit) + 1)], unit
    return key, ""


def shape_of(values: list[object]) -> str:
    """값들이 실제로 어떤 모양인가. **이름이 아니라 값을 본다.**"""
    kinds = set()
    for value in values:
        if isinstance(value, bool):
            kinds.add("boolean")
        elif isinstance(value, int | float):
            kinds.add("number")
        elif isinstance(value, dict):
            inner = set(value) - {"note", "uncertain"}
            kinds.add("range" if inner & {"min", "max", "values"} else "text")
        elif isinstance(value, list):
            kinds.add("text")
        else:
            kinds.add("text")
    if "range" in kinds:
        return "range"
    if kinds == {"number"}:
        return "number"
    if kinds == {"boolean"}:
        return "boolean"
    return "text"



def handled_by_import() -> tuple[set[str], tuple[str, ...], bool]:
    """반입이 이미 다루는 원본 키들. (키 집합, 옵션 접미사, 읽었나).

    **정본은 반입 쪽이다.** 무엇이 값으로 들어가는지는 거기서 정해지고, 여기서 한 벌
    더 적으면 둘은 반드시 갈린다 — 이 도구가 그렇게 갈려 있었다.

    못 읽어도 도는 이유: `source/` 만 따로 열어 보는 일이 있다. 그때는 온톨로지
    기준으로만 세고 **그 사실을 화면에 적는다.**
    """
    root = CAT.parents[1] / "backend"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from app.modules.vocabulary.catalog_specs import (  # noqa: PLC0415
            DIMENSION_SOURCES,
            MAX_ONLY_SOURCES,
            OPTION_RANGE_SOURCES,
            RANGE_PAIR_SOURCES,
            SOURCE_SPEC_MAP,
            TEMPERATURE_PAIR,
            VARIANT_SUFFIXES,
        )
    except Exception:
        return set(), (), False
    keys = (
        set(SOURCE_SPEC_MAP)
        | set(DIMENSION_SOURCES)
        | set(RANGE_PAIR_SOURCES)
        | set(OPTION_RANGE_SOURCES)
        | set(MAX_ONLY_SOURCES)
        | set(TEMPERATURE_PAIR)
    )
    return keys, tuple(VARIANT_SUFFIXES), True


def main() -> int:
    rows = json.loads((ONT / "condition_keys.json").read_text(encoding="utf-8"))["keys"]
    known = {row["key"] for row in rows}
    for row in rows:
        known |= set(row.get("aliases") or [])
        known |= set(row.get("unit_variants") or {})

    # 반입이 이미 다루는 키도 「남은 일」 이 아니다. 계기판을 둘로 두지 않는다.
    mapped, suffixes, linked = handled_by_import()
    known |= mapped

    # 등재 키를 줄기로 묶어 둔다 — 별칭 후보를 가리키는 데 쓴다.
    by_stem: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_stem[split_unit(row["key"])[0]].append(row)

    used_values: dict[str, list[object]] = defaultdict(list)
    used_objects: dict[str, set[str]] = defaultdict(set)
    used_categories: dict[str, Counter] = defaultdict(Counter)
    for path in sorted((CAT / "equipment").rglob("*.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        pools = [obj.get("limits") or {}]
        pools += [(model.get("specs") or {}) for model in (obj.get("models") or [])]
        for pool in pools:
            for key, value in pool.items():
                if key in ("note", "uncertain") or key in known:
                    continue
                # `vertical_test_space_mm_E2` 같은 옵션 구성. 반입이 기본 구성으로
                # 들이고 옵션은 비고에 남긴다 — 빠진 값이 아니다.
                if any(
                    key.endswith(suffix) and key[: -len(suffix)] in known
                    for suffix in suffixes
                ):
                    continue
                used_values[key].append(value)
                used_objects[key].add(obj["id"])
                used_categories[key][obj["category"]] += 1

    out = []
    for key in sorted(used_values, key=lambda one: (-len(used_values[one]), one)):
        stem, unit = split_unit(key)
        shape = shape_of(used_values[key])
        role = "measure"
        if any(hint in key for hint in NOT_SPEC_HINTS):
            role = "not_spec"
        elif shape == "text" and not unit:
            # 단위도 없고 값이 문장뿐이면 재는 값이 아니라 서술이다.
            role = "descriptive"

        # 같은 줄기의 등재 키 = 별칭이거나 단위 변형일 가능성. **확정하지 않는다.**
        candidates = [one["key"] for one in by_stem.get(stem, [])]
        out.append(
            {
                "key": key,
                "label": "",
                "unit": unit,
                "dimension": DIMENSIONS.get(unit, ""),
                "kind": shape,
                "role": role,
                "count": len(used_values[key]),
                "objects": len(used_objects[key]),
                "categories": [name for name, _ in used_categories[key].most_common(4)],
                "candidate_alias_of": candidates,
                "sample": json.dumps(used_values[key][0], ensure_ascii=False)[:80],
            }
        )

    tally = Counter(one["role"] for one in out)
    if linked:
        print(f"안 다뤄지는 키 {len(out)}종 · 값 {sum(one['count'] for one in out)}건")
    else:
        # **다르게 셌다는 사실을 말한다.** 조용히 다른 수를 내놓으면 그 수를 반입의
        # 보류 수와 비교하는 사람이 생긴다.
        print(f"온톨로지 미등재 키 {len(out)}종 · 값 {sum(one['count'] for one in out)}건")
        print("  (반입 표를 못 읽었습니다 — 반입이 이미 다루는 키가 여기 섞여 있습니다)")
    print(f"  measure {tally['measure']} · descriptive {tally['descriptive']} · "
          f"not_spec {tally['not_spec']}")
    print(f"  단위를 뽑아낸 것 {sum(1 for one in out if one['unit'])}종")
    print(f"  별칭 후보가 있는 것 {sum(1 for one in out if one['candidate_alias_of'])}종")

    if "--print" in sys.argv:
        for one in out[:30]:
            print(f"  {one['count']:4d} {one['key']:34s} {one['unit']:8s} "
                  f"{one['kind']:8s} {one['role']:12s} {','.join(one['candidate_alias_of'])}")
        return 0

    target = ONT / "suggested_keys.json"
    target.write_text(
        json.dumps(
            {
                "_comment": (
                    "tools_suggest_keys.py 가 만든 **후보**다. 사람이 label 을 채우고"
                    " role 을 확인한 뒤 condition_keys.json 으로 옮긴다."
                    " label 을 비워 둔 이유: 이름을 지어내면 그것이 진실이 된다."
                ),
                "keys": out,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\n{target.relative_to(CAT)} 에 썼습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
