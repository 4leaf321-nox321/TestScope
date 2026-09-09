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


def main() -> int:
    rows = json.loads((ONT / "condition_keys.json").read_text(encoding="utf-8"))["keys"]
    known = {row["key"] for row in rows}
    for row in rows:
        known |= set(row.get("aliases") or [])
        known |= set(row.get("unit_variants") or {})

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
    print(f"등재 안 된 키 {len(out)}종 · 값 {sum(one['count'] for one in out)}건")
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
