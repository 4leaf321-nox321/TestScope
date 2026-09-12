"""MaterialTwin 계측기 카탈로그를 **이 저장소의 장비 객체로 바꾼다.**

    python tools_from_materialtwin.py --db <materialtwin.db>        객체·물성 온톨로지를 쓴다
    python tools_from_materialtwin.py --db <materialtwin.db> --check  쓰지 않고 보고만

MaterialTwin(`66_MatNexus/materialtwin-20260905/materialtwin.db`)에는 계측기 218종·능력행
532건·물성 정의 271종이 있다. 셋 다 이쪽 사슬의 원료다:

    물성(property_definition)  ->  properties.json          기준정보 축 `property` 의 값
    계측기(instrument)         ->  equipment/<제조사>/*.json 계열·기종
    능력행(instrument_capability) -> 객체의 test_items · measurands_by_item · 규격 · 온도

## 왜 DB 를 직접 반입하지 않고 객체 JSON 으로 바꾸나

카탈로그의 정본은 `source/catalog` 이고 반입 경로는 `import_catalog.py` 하나다. 두 번째
반입기를 두면 같은 장비가 두 길로 들어와 어느 쪽이 맞는지 알 수 없게 된다. 여기서는
**MaterialTwin 을 또 하나의 카탈로그 출처로** 다룬다 — PDF 대신 DB 행이 근거다.

## 계열은 여기서 묶는다

MaterialTwin 은 기종 한 층뿐이다. Instron 5942·5943·… 이 각각 따로 서 있다. 그것을
그대로 들이면 기종 하나짜리 계열이 218개 생기고, 「이 계열은 무슨 시험이 되나」 를
218번 적게 된다. 묶음 규칙은 `source/materialtwin/groups.json` 이 갖는다 — **사람이
확인한 표**이고, 거기 없는 계측기는 이 도구가 오류로 세운다.

## 이미 있는 것에는 보탠다

35종은 카탈로그 객체가 이미 갖고 있다(Instron 5900 · AGS-X · HR-530 …). 그 객체를
고쳐 쓰지 않고 `supplements` 객체를 따로 낸다 — 이름·제조사·분류가 같아서 반입이 같은
계열로 합치고, **이미 있는 기종은 빼고** 없는 기종만 붙는다(5965-E2 · HM-122 · TGA 5500).

## 하중용량은 사양이지 물성 범위가 아니다

MaterialTwin 은 「하중용량 10 kN」 을 일부러 능력행 range 에 안 넣었다(인장강도 범위가
아니므로). 여기서는 그것을 **기종 사양 `force_kN`** 으로 되살린다 — 이쪽에서는 사양이
맞는 자리다. 능력행의 시편 온도 범위는 `temperature_degC` 로 간다.

## 원문은 통째로 남긴다

기종마다 `materialtwin` 블록에 설명·주석·능력행 전부를 그대로 둔다. 반입이 그것을
`raw_specs` 로 보존한다. 「이 값이 어디서 왔나」 를 되짚을 수 있어야 한다.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ONT = HERE / "ontology"
RULES = HERE.parent / "materialtwin"
DEFAULT_DB = Path(r"F:\data\0_Program\66_MatNexus\materialtwin-20260905\materialtwin.db")
SNAPSHOT = "materialtwin-20260905"

#: MaterialTwin vendor -> 온톨로지 제조사 id. 없던 제조사는 아래 NEW_MANUFACTURERS 로 만든다.
VENDORS: dict[str, str] = {
    "Agilent": "agilent",
    "Anton Paar": "anton-paar",
    "Brookfield AMETEK": "brookfield-ametek",
    "Bruker": "bruker",
    "Bruker BioSpin": "bruker",
    "Buehler": "buehler",
    "Carl Zeiss SMT": "zeiss",
    "ESPEC": "espec",
    "Filmetrics": "filmetrics",
    "HORIBA Scientific": "horiba",
    "Hitachi High-Tech": "hitachi-high-tech",
    "Hot Disk": "hot-disk",
    "Instron": "instron",
    "J.A. Woollam": "ja-woollam",
    "JEOL": "jeol",
    "KLA": "kla",
    "KLA-Tencor": "kla",
    "KRÜSS": "kruss",
    "Keithley": "keithley",
    "Keithley (Tektronix)": "keithley",
    "Lake Shore Cryotronics": "lake-shore",
    "METTLER TOLEDO": "mettler-toledo",
    "MTS": "mts",
    "Malvern": "malvern-panalytical",
    "Malvern Panalytical": "malvern-panalytical",
    "Metrohm": "metrohm",
    "Micromeritics": "micromeritics",
    "Mitutoyo": "mitutoyo",
    "NETZSCH": "netzsch",
    "Nordson Test & Inspection": "nordson-dage",
    "Ossila": "ossila",
    "Oxford Instruments": "oxford-instruments",
    "Park Systems": "park-systems",
    "PerkinElmer": "perkinelmer",
    "Q-Lab": "q-lab",
    "Renishaw": "renishaw",
    "Rigaku": "rigaku",
    "Shimadzu": "shimadzu",
    "TA Instruments": "ta-instruments",
    "Thermo Scientific": "thermo-fisher",
    "ZEISS": "zeiss",
    "Zygo": "zygo",
}

NEW_MANUFACTURERS: list[dict[str, Any]] = [
    {"id": "agilent", "name": "Agilent Technologies", "name_ko": "애질런트", "country": "US", "website": "https://www.agilent.com", "domains": ["chromatograph_mass_spectrometer"]},
    {"id": "brookfield-ametek", "name": "Brookfield AMETEK", "name_ko": "브룩필드", "country": "US", "parent": "AMETEK", "website": "https://www.brookfieldengineering.com", "domains": ["viscometer"]},
    {"id": "filmetrics", "name": "Filmetrics (KLA)", "name_ko": "필메트릭스", "country": "US", "parent": "KLA", "website": "https://www.filmetrics.com", "domains": ["film_thickness_analyzer"]},
    {"id": "horiba", "name": "HORIBA Scientific", "name_ko": "호리바", "country": "JP", "website": "https://www.horiba.com", "domains": ["composition_spectrometer", "optical_spectrometer"]},
    {"id": "ja-woollam", "name": "J.A. Woollam", "name_ko": "울람", "country": "US", "website": "https://www.jawoollam.com", "domains": ["film_thickness_analyzer"]},
    {"id": "jeol", "name": "JEOL", "name_ko": "지올", "country": "JP", "website": "https://www.jeol.com", "domains": ["electron_microscope", "composition_spectrometer"]},
    {"id": "kruss", "name": "KRÜSS", "name_ko": "크루스", "country": "DE", "website": "https://www.kruss-scientific.com", "domains": ["contact_angle_analyzer"]},
    {"id": "keithley", "name": "Keithley (Tektronix)", "name_ko": "키슬리", "country": "US", "parent": "Tektronix", "website": "https://www.tek.com/keithley", "domains": ["electrical_property_tester"]},
    {"id": "lake-shore", "name": "Lake Shore Cryotronics", "name_ko": "레이크쇼어", "country": "US", "website": "https://www.lakeshore.com", "domains": ["electrical_property_tester"]},
    {"id": "metrohm", "name": "Metrohm", "name_ko": "메트롬", "country": "CH", "website": "https://www.metrohm.com", "domains": ["karl_fischer_titrator"]},
    {"id": "micromeritics", "name": "Micromeritics", "name_ko": "마이크로메리틱스", "country": "US", "website": "https://www.micromeritics.com", "domains": ["pycnometer_porosimeter"]},
    {"id": "ossila", "name": "Ossila", "name_ko": "오실라", "country": "GB", "website": "https://www.ossila.com", "domains": ["electrical_property_tester"]},
    {"id": "oxford-instruments", "name": "Oxford Instruments", "name_ko": "옥스퍼드 인스트루먼츠", "country": "GB", "website": "https://www.oxinst.com", "domains": ["electron_microscope"]},
    {"id": "park-systems", "name": "Park Systems", "name_ko": "파크시스템스", "country": "KR", "website": "https://www.parksystems.com", "domains": ["atomic_force_microscope"]},
    {"id": "renishaw", "name": "Renishaw", "name_ko": "레니쇼", "country": "GB", "website": "https://www.renishaw.com", "domains": ["composition_spectrometer"]},
    {"id": "rigaku", "name": "Rigaku", "name_ko": "리가쿠", "country": "JP", "website": "https://www.rigaku.com", "domains": ["xray_diffractometer", "composition_spectrometer"]},
    {"id": "zeiss", "name": "ZEISS", "name_ko": "자이스", "country": "DE", "website": "https://www.zeiss.com", "domains": ["electron_microscope", "xray_inspection"]},
    {"id": "zygo", "name": "Zygo (AMETEK)", "name_ko": "자이고", "country": "US", "parent": "AMETEK", "website": "https://www.zygo.com", "domains": ["optical_profilometer"]},
]

#: 모델명에서 떼는 말 — 기존 객체의 기종과 견줄 때 상표가 끼면 같은 기종을 못 알아본다.
BRAND_WORDS = (
    "wilson", "discovery", "surftest", "criterion", "kinexus", "landmark", "ceast",
    "instron", "q-fog", "walk-in", "platinous", "lab series", "agree",
)

#: 규격 문자열에서 버릴 토막 — 규격이 아니거나(BET·ANSI·VDA) 번호가 없는 것.
NOT_A_STANDARD = {"BET", "ANSI", "VDA", "ISO", "ASTM", "JIS"}
#: MaterialTwin 이 「ISO 1997」 로 적은 것은 ISO 4287:1997(조도)이다.
STANDARD_FIXES = {"ISO 1997": "ISO 4287"}
_YEAR = re.compile(r"(?:[:\-]| )(19|20)\d{2}[a-z]?$")
_SPACED = re.compile(r"^(ASTM|JIS|ISO|IEC|DIN|EN|KS) ([A-Z]) (\d)")

_FORCE = re.compile(r"하중용량\s*(\d+(?:\.\d+)?)\s*kN")
_SPEED = re.compile(r"(?:최대속도|크로스헤드 속도)\s*(?:(\d+(?:\.\d+)?)\s*~\s*)?(\d+(?:\.\d+)?)\s*mm/min")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def norm(text: str) -> str:
    return re.sub(r"[\s\-_/·()]", "", text).lower()


def core(model: str, vendor_words: list[str]) -> str:
    """상표·괄호를 뗀 모델명 비교키."""
    text = re.sub(r"\([^)]*\)", " ", model.lower())
    for word in (*BRAND_WORDS, *vendor_words):
        text = text.replace(word.lower(), " ")
    return norm(text)


def standard_codes(raw: str | None) -> list[str]:
    """능력행의 규격 문자열을 규격 번호 목록으로. **판(연도)은 뗀다** — 카탈로그가
    말하는 것은 「이 규격을 지원한다」 까지고, 어느 판인지는 그 판으로 시험했다는 뜻이
    된다."""
    out: list[str] = []
    for one in (raw or "").split(" / "):
        code = one.strip()
        if not code:
            continue
        code = STANDARD_FIXES.get(code, code)
        code = _YEAR.sub("", code)
        code = _SPACED.sub(r"\1 \2\3", code)
        code = re.sub(r"\s+", " ", code)
        if code in NOT_A_STANDARD or not re.search(r"\d", code):
            continue
        if code not in out:
            out.append(code)
    return out


class Rules:
    def __init__(self) -> None:
        links = load(ONT / "property_links.json")
        self.techniques: list[dict[str, Any]] = links["techniques"]
        self.test_items = {t["id"] for t in load(ONT / "test_items.json")["test_items"]}
        self.categories = {c["id"] for c in load(ONT / "categories.json")["categories"]}
        self.form_factors = {f["id"] for f in load(ONT / "form_factors.json")["form_factors"]}
        self.drives = {d["id"] for d in load(ONT / "drives.json")["drives"]}

    def test_item_of(self, *texts: str | None) -> str | None:
        """기법 문자열 -> 시험 항목. 앞 규칙부터 처음 맞는 것. 여러 문자열이면 앞의 것이
        더 구체적이다(능력행의 기법이 계측기의 기법보다 먼저)."""
        for text in texts:
            if not text:
                continue
            for rule in self.techniques:
                if any(word.lower() in text.lower() for word in rule["match"]):
                    return str(rule["test_item"])
        return None


def form_factor_of(text: str) -> str | None:
    if "단일컬럼" in text:
        return "single_column_tabletop"
    if "이중컬럼" in text:
        return "dual_column_tabletop"
    if "워크인" in text or "Walk-in" in text:
        return "walk_in"
    if "휴대형" in text:
        return "portable"
    if "바닥형" in text or "플로어" in text:
        return "floor"
    if "탁상형" in text or "벤치탑" in text:
        return "benchtop"
    return None


def drive_of(text: str) -> str | None:
    if "서보유압" in text:
        return "servohydraulic"
    if "유압식" in text or "유압" in text:
        return "hydraulic"
    if "스크류" in text or "전동" in text:
        return "electromechanical"
    if "분동" in text:
        return "dead_weight"
    return None


class Twin:
    """읽어 둔 MaterialTwin."""

    def __init__(self, db_path: Path) -> None:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        self.propdefs = [dict(r) for r in con.execute("select * from property_definition order by id")]
        self.instruments = {
            r["id"]: dict(r)
            for r in con.execute(
                "select i.*, s.title as source_title from instrument i"
                " left join source s on s.id = i.source_id order by i.id"
            )
        }
        self.caps: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for r in con.execute("select * from instrument_capability order by instrument_id, id"):
            self.caps[r["instrument_id"]].append(dict(r))
        con.close()


def build_properties(twin: Twin) -> dict[str, Any]:
    aliases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    snapshot = RULES / "matnexus_aliases.json"
    if snapshot.exists():
        for row in load(snapshot)["aliases"]:
            aliases[row["key"]].append({k: v for k, v in row.items() if k != "key"})
    rows = []
    for p in twin.propdefs:
        axes = p.get("condition_axes")
        rows.append(
            {
                "key": p["key"],
                "domain": p["domain"],
                "name_ko": p["name"],
                "symbol": p.get("symbol"),
                "si_unit": p.get("si_unit"),
                "value_type": p["value_type"],
                "description": p.get("description"),
                "test_standard": p.get("test_standard"),
                "condition_axes": json.loads(axes) if isinstance(axes, str) else (axes or []),
                "aliases": aliases.get(p["key"], []),
            }
        )
    return {
        "_comment": (
            f"물성 항목 — 기준정보 축 property 의 값. MaterialTwin property_definition "
            f"({SNAPSHOT}, {len(rows)}종)을 tools_from_materialtwin.py 가 옮긴 것이고 key 가 "
            "값의 code 다. aliases 는 MatNexus property_aliases 스냅샷. 손으로 고치지 말고 "
            "MaterialTwin 쪽을 고친 뒤 다시 돌린다 — 두 곳에서 고치면 갈린다."
        ),
        "source": SNAPSHOT,
        "properties": rows,
    }


_TEMPERATURE_WORDS = ("온도", "항온", "챔버", "가열", "냉각", "°C", "스테이지", "노(", " 노 ", "히터")


def _temperature_is_optional(notes: str | None) -> bool:
    """주석의 **같은 문장** 안에 「옵션」 과 온도 말이 함께 있나. 문장 단위로 보는 이유:
    Litesizer 주석은 pH 적정 옵션을, FluoroMax 는 검출기 옵션을 말하는데 온도 범위는 본체
    것이다 — 주석 전체에서 「옵션」 만 찾으면 그 둘이 옵션 챔버로 읽힌다."""
    for sentence in re.split(r"[.。!?]\s|\s—\s|\n", notes or ""):
        if "옵션" in sentence and any(word in sentence for word in _TEMPERATURE_WORDS):
            return True
    return False


#: 능력행의 **측정 범위**를 기종 사양으로 옮기는 표 — (물성 키, 원본 단위) -> (사양 키, 배율).
#:
#: 능력행은 「이 장비가 무엇을 어디까지 재나」 를 물성마다 적어 온다. 그 수치는 그 장비를
#: 가르는 사양인데(점도계는 점도 범위로 갈리고 분광기는 파장으로 갈린다), 전에는 스냅샷
#: 원문에만 남고 사양표에는 아무것도 안 들어갔다 — 사양이 빈 기종 224 중 113 이 그것이다.
#:
#: **(물성, 단위) 쌍으로 건다.** 물성만 보면 틀린다: `optical.transmittance` 의 범위가
#: `nm` 로 적혀 있으면 그것은 투과율이 아니라 **파장**이다(185~900 nm). 단위를 안 보고
#: 「투과율 185~900 %」 로 적으면, 지어낸 값이 사양표에 진실로 앉는다.
#:
#: 표에 없는 쌍은 **안 들인다** — 원문에는 그대로 남아 사람이 화면에서 옮겨 적을 수 있다.
CAPABILITY_SPECS: dict[tuple[str, str], tuple[str, float]] = {
    ("rheological.viscosity", "cP"): ("viscosity_cP", 1.0),
    ("rheological.yield_stress", "Pa"): ("yield_stress_Pa", 1.0),
    ("mechanical.hardness_shore_a", "ShoreA"): ("hardness_shore_a", 1.0),
    ("mechanical.hardness_shore_d", "ShoreD"): ("hardness_shore_d", 1.0),
    ("mechanical.storage_modulus", "Pa"): ("modulus_Pa", 1.0),
    ("mechanical.loss_modulus", "Pa"): ("modulus_Pa", 1.0),
    # 분광·타원계의 nm 는 **파장**이다. 물성이 무엇이든 같은 칸으로 간다.
    ("optical.transmittance", "nm"): ("wavelength_nm", 1.0),
    ("optical.reflectance", "nm"): ("wavelength_nm", 1.0),
    ("optical.refractive_index", "nm"): ("wavelength_nm", 1.0),
    ("optical.extinction_coefficient", "nm"): ("wavelength_nm", 1.0),
    ("optical.birefringence", "nm"): ("wavelength_nm", 1.0),
    ("optical.emission_peak_wavelength", "nm"): ("wavelength_nm", 1.0),
    ("optical.refractive_index", "1"): ("refractive_index", 1.0),
    ("optical.excited_state_lifetime", "s"): ("excited_state_lifetime_s", 1.0),
    ("structure.layer_thickness", "nm"): ("layer_thickness_nm", 1.0),
    ("structure.layer_thickness", "µm"): ("layer_thickness_um", 1.0),
    ("structure.layer_thickness", "mm"): ("layer_thickness_mm", 1.0),
    ("structure.particle_diameter", "nm"): ("particle_diameter_nm", 1.0),
    ("structure.molecular_weight", "Da"): ("molecular_weight_Da", 1.0),
    ("structure.pore_diameter", "m"): ("pore_diameter_um", 1_000_000.0),
    ("thermal.diffusivity", "mm^2/s"): ("thermal_diffusivity_mm2_s", 1.0),
    ("thermal.conductivity", "W/(m·K)"): ("thermal_conductivity_W_mK", 1.0),
    ("thermal.conductivity", "W/m/K"): ("thermal_conductivity_W_mK", 1.0),
    ("physical.contact_angle_water", "°"): ("contact_angle_deg", 1.0),
    ("physical.surface_energy", "mN/m"): ("surface_energy_mN_m", 1.0),
    ("physical.zeta_potential", "V"): ("zeta_potential_V", 1.0),
    ("electrical.carrier_mobility", "m^2/(V*s)"): ("carrier_mobility_m2_Vs", 1.0),
    ("electrical.carrier_concentration", "1/m^3"): ("carrier_concentration_m3", 1.0),
    ("electrical.surface_resistivity", "Ω/square"): ("surface_resistivity_ohm_sq", 1.0),
}


def capability_specs(caps: list[dict[str, Any]]) -> dict[str, Any]:
    """능력행의 측정 범위 -> 기종 사양. 같은 칸이 여럿이면 **가장 넓은 것**으로 합친다.

    한 장비가 같은 물성을 기법 둘로 재면(범위가 갈린다) 둘 다 그 장비가 할 수 있는 것이라
    봉투가 맞다. 대신 합쳤다는 사실을 비고에 남긴다 — 안 남기면 어느 기법의 수치인지
    되짚을 수 없고, 그 수치를 믿고 시험을 잡은 사람이 막힌다.
    """
    out: dict[str, dict[str, Any]] = {}
    merged: set[str] = set()
    for cap in caps:
        unit = cap.get("range_unit")
        target = CAPABILITY_SPECS.get((cap.get("property_key") or "", unit or ""))
        if target is None:
            continue
        key, factor = target
        low, high = cap.get("range_min"), cap.get("range_max")
        if low is None and high is None:
            continue
        row = out.setdefault(key, {})
        for side, value, pick in (("min", low, min), ("max", high, max)):
            if value is None:
                continue
            scaled = float(value) * factor
            if side in row:
                merged.add(key)
                row[side] = pick(row[side], scaled)
            else:
                row[side] = scaled
    for key in merged:
        out[key]["note"] = "능력행 여럿을 합친 범위 (기법마다 갈린다)"
    return {key: value for key, value in out.items() if value}


def model_specs(inst: dict[str, Any], caps: list[dict[str, Any]]) -> dict[str, Any]:
    """기종 사양 — 설명·주석의 수치, 능력행의 온도, 그리고 능력행의 측정 범위."""
    specs: dict[str, Any] = dict(capability_specs(caps))
    text = " ".join(x for x in (inst.get("description"), inst.get("notes")) if x)
    if m := _FORCE.search(text):
        specs["force_kN"] = float(m.group(1))
    if m := _SPEED.search(text):
        low, high = m.group(1), m.group(2)
        specs["crosshead_speed_mm_min"] = (
            {"min": float(low), "max": float(high)} if low else {"max": float(high)}
        )
    lows = [c["temperature_min_k"] for c in caps if c.get("temperature_min_k") is not None]
    highs = [c["temperature_max_k"] for c in caps if c.get("temperature_max_k") is not None]
    if lows or highs:
        rng: dict[str, Any] = {}
        if lows:
            rng["min"] = round(min(lows) - 273.15, 2)
        if highs:
            rng["max"] = round(max(highs) - 273.15, 2)
        if lows and highs and (len(set(lows)) > 1 or len(set(highs)) > 1):
            rng["note"] = "능력행마다 온도 범위가 달라 가장 넓은 것을 적었다"
        # MaterialTwin 주석이 「옵션 항온조 기준」 이라고 말하면 본체 값이 아니다. 빠뜨리면
        # 「80 °C 인장」 에 갖고 있지도 않은 챔버를 전제로 답한다(12차 감사의 그 함정).
        # **「옵션」 이 온도 얘기일 때만** — 검출기 옵션·적정 옵션이 같은 주석에 흔하다.
        if any(_temperature_is_optional(c.get("notes")) for c in caps):
            rng["requires_accessory"] = True
            rng["note"] = " · ".join(
                x for x in (rng.get("note"), "옵션 항온조·노 기준 (MaterialTwin 주석)") if x
            )
        specs["temperature_degC"] = rng
    return specs


def twin_block(inst: dict[str, Any], caps: list[dict[str, Any]]) -> dict[str, Any]:
    """원문 통째 — 반입이 raw_specs 로 보존한다."""
    keep = (
        "property_key", "technique", "standard", "range_min", "range_max", "range_unit",
        "resolution", "accuracy", "temperature_min_k", "temperature_max_k", "specimen",
        "mapping_confidence", "source_detail", "notes",
    )
    return {
        "snapshot": SNAPSHOT,
        "instrument_id": inst["id"],
        "category": inst["category"],
        "technique": inst.get("technique"),
        "description": inst.get("description"),
        "notes": inst.get("notes"),
        "doc_path": inst.get("doc_path"),
        "source_title": inst.get("source_title"),
        "capabilities": [{k: c.get(k) for k in keep if c.get(k) is not None} for c in caps],
    }


def convert(twin: Twin, rules: Rules, existing: dict[str, dict[str, Any]], report: list[str]) -> list[dict[str, Any]]:
    groups = load(RULES / "groups.json")["groups"]
    covered: set[int] = set()
    objects: list[dict[str, Any]] = []

    for group in groups:
        ids = [int(x) for x in group["instruments"]]
        covered.update(ids)
        base = existing.get(group["supplements"]) if group.get("supplements") else None
        if group.get("supplements") and base is None:
            report.append(f"오류: supplements 대상이 없습니다 — {group['supplements']}")
            continue

        insts = [twin.instruments[i] for i in ids if i in twin.instruments]
        missing = [i for i in ids if i not in twin.instruments]
        if missing:
            report.append(f"오류: MaterialTwin 에 없는 계측기 id {missing} ({group.get('id') or group.get('supplements')})")
        if not insts:
            continue
        vendor_words = sorted({w for i in insts for w in i["vendor"].lower().split()}, key=len, reverse=True)

        # --- 기종 --------------------------------------------------------------
        existing_cores: list[str] = []
        if base:
            existing_cores = [core(m["model"], vendor_words) for m in base.get("models") or []]
            existing_cores.append(core(base["name"], vendor_words))
        models: list[dict[str, Any]] = []
        test_items: list[str] = list(group.get("test_items") or (base or {}).get("test_items") or [])
        by_item: dict[str, list[str]] = defaultdict(list)
        methods_by_item: dict[str, list[str]] = defaultdict(list)
        measurands: list[str] = []
        confidences: list[str] = []
        series_notes: list[str] = []
        for inst in insts:
            caps = twin.caps.get(inst["id"], [])
            confidences.extend(c["mapping_confidence"] for c in caps)
            mine = core(inst["model"], vendor_words)
            if base and any(
                have == mine or (len(mine) >= 3 and have.startswith(mine)) for have in existing_cores
            ):
                report.append(f"이미 있음: {inst['vendor']} {inst['model']} ∈ {base['id']}")
                # 기종은 있지만 능력행은 보탤 것이 있을 수 있다 — 시험 항목·규격은 아래서 모은다.
                keep_model = False
            else:
                keep_model = True
            if base and not re.search(r"\d", inst["model"]) and not caps:
                # 「TSA series 2·3존 열충격조」 같은 계열 설명 — 기종이 아니다.
                series_notes.append(f"{inst['model']}: {inst.get('description') or ''}")
                keep_model = False

            for cap in caps:
                item = rules.test_item_of(cap.get("technique"), inst.get("technique"))
                if item is None:
                    if len(test_items) == 1:
                        item = test_items[0]
                    else:
                        report.append(
                            f"기법을 시험 항목으로 못 읽음: {inst['vendor']} {inst['model']} —"
                            f" {cap.get('technique')!r} ({cap['property_key']})"
                        )
                        continue
                if item not in rules.test_items:
                    report.append(f"온톨로지에 없는 시험 항목 {item} ({inst['model']})")
                    continue
                if item not in test_items:
                    test_items.append(item)
                if cap["property_key"] not in by_item[item]:
                    by_item[item].append(cap["property_key"])
                if cap["property_key"] not in measurands:
                    measurands.append(cap["property_key"])
                for code in standard_codes(cap.get("standard")):
                    if code not in methods_by_item[item]:
                        methods_by_item[item].append(code)
            if not caps and not group.get("test_items") and not base:
                item = rules.test_item_of(inst.get("technique"), inst.get("description"))
                if item and item not in test_items:
                    test_items.append(item)

            if keep_model:
                row: dict[str, Any] = {"model": inst["model"]}
                specs = model_specs(inst, caps)
                if specs:
                    row["specs"] = specs
                ff = form_factor_of(inst.get("description") or "")
                if ff and ff in rules.form_factors:
                    row["form_factor"] = ff
                if inst.get("description"):
                    row["note"] = inst["description"]
                row["materialtwin"] = twin_block(inst, caps)
                models.append(row)

        if base and not models and not by_item and not methods_by_item and not series_notes:
            report.append(f"보탤 것 없음: {base['id']}")
            continue

        if not test_items:
            report.append(f"시험 항목이 비었습니다: {group.get('id') or base['id']} — groups.json 에 test_items 를 적으세요")

        first = insts[0]
        obj: dict[str, Any] = {
            "id": f"{base['id']}-materialtwin" if base else group["id"],
            "kind": "equipment_series" if (len(models) > 1 or base) else "equipment_model",
            "name": base["name"] if base else group["name"],
            "manufacturer": base["manufacturer"] if base else group["manufacturer"],
            "category": base["category"] if base else group["category"],
            "test_items": test_items,
            "measurands": measurands,
            "sources": [
                {
                    "origin": f"{SNAPSHOT}/instrument/{i['id']}",
                    "note": " · ".join(x for x in (i.get("source_title"), i.get("doc_path")) if x),
                }
                for i in insts
            ],
            "confidence": "catalog" if "high" in confidences else "limited",
        }
        if base:
            obj["supplements"] = base["id"]
        else:
            if group.get("name_ko"):
                obj["name_ko"] = group["name_ko"]
            text = " ".join(x for x in (first.get("description"), first.get("technique")) if x)
            drive = drive_of(text)
            if drive and drive in rules.drives:
                obj["drive"] = drive
            ff = form_factor_of(text)
            if ff and ff in rules.form_factors and all(
                form_factor_of(i.get("description") or "") == ff for i in insts
            ):
                obj["form_factor"] = ff
            obj["description"] = first.get("technique") or first.get("description")
            if group["manufacturer"] not in rules_manufacturers():
                report.append(f"온톨로지에 없는 제조사 {group['manufacturer']}")
            if group["category"] not in rules.categories:
                report.append(f"온톨로지에 없는 분류 {group['category']} ({group['id']})")
        if by_item:
            obj["measurands_by_item"] = dict(by_item)
        if methods_by_item:
            flat = sorted({c for codes in methods_by_item.values() for c in codes})
            obj["standards"] = {"compliance": [], "test_methods": flat, "test_methods_by_item": dict(methods_by_item)}
        if models:
            obj["models"] = models
        if series_notes:
            # 기종이 아니라 계열 설명이다. 비고로 남기고 원문은 통째로 — 반입이 계열의
            # spec_note 와 raw_limits 에 보탠다.
            obj["notes"] = "[MaterialTwin] " + " / ".join(series_notes)
            obj["materialtwin_series"] = [
                twin_block(i, twin.caps.get(i["id"], []))
                for i in insts
                if not re.search(r"\d", i["model"]) and not twin.caps.get(i["id"])
            ]
        # 계열 온도 봉투 — 기종이 여럿이면 반입이 비고로만 남긴다(ADR 0006).
        temps = [m["specs"]["temperature_degC"] for m in models if "temperature_degC" in (m.get("specs") or {})]
        if temps and len(models) == len(insts):
            envelope: dict[str, Any] = {}
            lows = [t["min"] for t in temps if "min" in t]
            highs = [t["max"] for t in temps if "max" in t]
            if lows:
                envelope["min"] = min(lows)
            if highs:
                envelope["max"] = max(highs)
            obj["limits"] = {"temperature_degC": envelope}
        objects.append(obj)

    for iid, inst in twin.instruments.items():
        if iid not in covered:
            report.append(f"묶음에 없는 계측기: #{iid} {inst['vendor']} {inst['model']}")
    return objects


_MANUFACTURERS: set[str] | None = None


def rules_manufacturers() -> set[str]:
    global _MANUFACTURERS
    if _MANUFACTURERS is None:
        _MANUFACTURERS = {m["id"] for m in load(ONT / "manufacturers.json")["manufacturers"]}
    return _MANUFACTURERS


def ensure_manufacturers(report: list[str], *, write: bool) -> None:
    path = ONT / "manufacturers.json"
    data = load(path)
    have = {m["id"] for m in data["manufacturers"]}
    added = []
    for row in NEW_MANUFACTURERS:
        if row["id"] in have:
            continue
        data["manufacturers"].append({**row, "registered": f"2026-09-12 {SNAPSHOT} 계측기 반입"})
        added.append(row["id"])
    global _MANUFACTURERS
    if added:
        data["manufacturers"].sort(key=lambda m: m["id"])
        report.append(f"제조사 새로 {len(added)}: {', '.join(added)}")
        if write:
            dump(path, data)
    # --check 에서도 「없는 제조사」 로 세지 않는다 — 쓰면 생길 것이다.
    _MANUFACTURERS = {m["id"] for m in data["manufacturers"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="MaterialTwin 계측기를 장비 객체로 바꾼다")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--check", action="store_true", help="쓰지 않고 보고만 한다")
    args = parser.parse_args()
    if not args.db.exists():
        print(f"MaterialTwin DB 가 없습니다: {args.db}")
        return 1

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    report: list[str] = []
    twin = Twin(args.db)
    ensure_manufacturers(report, write=not args.check)
    rules = Rules()
    existing = {
        obj["id"]: obj
        for obj in (load(p) for p in sorted((HERE / "equipment").rglob("*.json")))
        if not obj.get("supplements")
    }
    properties = build_properties(twin)
    objects = convert(twin, rules, existing, report)

    if not args.check:
        dump(ONT / "properties.json", properties)
        for obj in objects:
            dump(HERE / "equipment" / obj["manufacturer"] / f"{obj['id']}.json", obj)

    fresh = [o for o in objects if not o.get("supplements")]
    extra = [o for o in objects if o.get("supplements")]
    print(f"MaterialTwin {len(twin.instruments)} 계측기 · 능력행 {sum(len(v) for v in twin.caps.values())}")
    print(f"  물성 {len(properties['properties'])}종 -> ontology/properties.json")
    print(f"  새 객체 {len(fresh)} (기종 {sum(len(o.get('models') or []) for o in fresh)})")
    print(f"  보탬 객체 {len(extra)} (기종 {sum(len(o.get('models') or []) for o in extra)})")
    errors = [r for r in report if r.startswith("오류") or r.startswith("묶음에 없는")]
    notes = [r for r in report if r not in errors]
    if notes:
        print(f"\n참고 {len(notes)}건:")
        for one in notes:
            print("   ", one)
    if errors:
        print(f"\n오류 {len(errors)}건:")
        for one in errors:
            print("   ", one)
        return 1
    print("\n(--check 였습니다 — 아무것도 쓰지 않았습니다)" if args.check else "\n썼습니다. 다음: python build_graph.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
