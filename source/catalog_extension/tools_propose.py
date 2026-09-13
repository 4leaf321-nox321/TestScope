"""보강 원료에서 검토함 물음 셋을 세운다.

    python tools_propose.py            # source/catalog/proposals/ 에 셋을 (다시) 쓴다
    python tools_propose.py --check    # 무엇이 서는지만 본다

| 파일 | 물음 | 원료 |
|---|---|---|
| `series_standards.json`  | 이 계열이 이 규격도 하나 | 페이지 본문의 규격 코드 · 논문 문장의 규격 |
| `series_test_items.json` | 이 계열이 이 시험도 하나 | 논문이 그 기종을 쓰면서 적은 시험(「tensile tests … Instron 34TM-5」) · 제조사 페이지의 「used for tensile, compression …」 문장 |
| `series_summary.json`    | 이 문장을 계열 소개에 넣을까 | 제조사 페이지의 응용 문장 |

## 규격 (`series_standards`)

## 무엇을 후보로 세우나

객체마다 `mentions/<id>.json` 의 `standards_found`(그 객체의 페이지 본문에서 나온 규격)와
`papers/<id>.json` 의 `usage_snippets[].standards`(논문이 그 기종을 쓰면서 함께 적은 규격) 중,
카탈로그 객체가 **아직 인용하지 않는** 규격이 후보다. 따라간 공통 페이지의 규격(`standards_nearby`)은
제조사 전체 목록이라 후보로 안 세운다.

## 추천은 무엇에 붙나

- 제조사 페이지(2등급)에 나온 규격 → 추천
- 남의 페이지(3등급) 둘 이상에 나온 규격 → 추천
- 하나에만, 또는 논문 문장에만 나온 규격 → 후보로만 (사람이 근거 링크를 보고 고른다)

규격군 이름만 남은 것(「ASTM」 「ISO 9001」 같은 품질 규격, 「IEC 60309」 같은 전원 커넥터 규격)은
잡음이라 뺀다 — 목록은 `NOISE` 에.

## 시험 항목 (`series_test_items`)

시험 항목 이름은 문장 어디에나 나온다(「compression」 이 압축 공기일 수 있다). 그래서 **이 기종을 언급한
문장 안에서만** 본다 — 논문의 `usage_snippets`(기종명 앞뒤 350자)와 제조사 페이지의 응용 문장(「used for …」
「tests of …」). 낱말은 `TEST_WORDS` 의 정규식으로 잡고, 카탈로그 객체에 **이미 있는 시험은 뺀다.**
논문 둘 이상 또는 제조사 문장에 나오면 추천.

## 소개 문장 (`series_summary`)

제조사 페이지(2등급)의 응용 문장 중 이 계열 이름 토막이 든 것, 최대 5개. 고르면 계열 `summary` 에 붙는다.

## 결정은 어디로 가나

검토함이 확정하면 DB 에서 그 계열의 시험 항목에 규격이 붙고(`review.services._apply`),
`export_review.py` 가 이 파일의 `decided` 에 되돌려 쓴다. 반입은 `review.refresh` 가 `decided` 를
읽어 같은 일을 하므로, 카탈로그 객체 JSON 을 고치지 않아도 운영 서버에 그대로 간다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "catalog"
OUT = CATALOG / "proposals" / "series_standards.json"
OUT_ITEMS = CATALOG / "proposals" / "series_test_items.json"
OUT_SUMMARY = CATALOG / "proposals" / "series_summary.json"
TITLES = HERE / "standard_titles.json"  # tools_standard_titles.py 가 만든다 — 없으면 제목 없이
sys.path.insert(0, str(HERE))

# 규격이 아니거나(품질·안전·전원 규격), 규격군 이름만인 것. 정규식.
NOISE = re.compile(
    r"^(ISO ?900[01]|ISO ?1400[01]|ISO ?45001|ISO ?17025|ISO ?13485|ISO ?27001|ISO ?9000"
    r"|IEC ?60309|IEC ?60320|IEC ?61010|IEC ?60204|IEC ?61326|IEC ?60529|IEC ?62061"
    r"|EN ?6[01]\d{3}(?![-–.])"  # EN 61010 같은 안전 규격 — 시험법이 아니다
    r"|UL ?61010|UL ?508|CSA ?C22|GB ?\d{1,3}$|SS ?\d+|BSP ?\d+|EIA ?\d{3}$|IPC ?\d{1,3}$"
    r"|ASTM ?\d|ISO ?\d{1,2}$|IEC ?\d{1,3}$|DIN ?\d{1,3}$|JIS ?\d|KS ?\d|EN ?\d{1,3}$"
    r"|MIL-STD-\d{1,2}$|USP ?\d|ETSI|RTCA|IEEE ?\d{1,3}$|JESD ?22$|JEDEC ?22$|JESD ?47$)",
    re.IGNORECASE,
)
MAX_PER_SERIES = 30
# 규격 모양 — 기관 뒤에 (띄고) 문자 묶음이 오거나 바로 숫자. 「ENERGY 21XX」 는 EN 뒤에 붙은 글자라 아니다.
SHAPE = re.compile(
    r"^(ASTM|ISO|IEC|EN|DIN|JIS|KS|BS|GB/T|GB|SAE|UL|CSA|IPC|JEDEC|JESD|MIL-STD|MIL-DTL|ISTA|VDA|GMW|GM|AASHTO"
    r"|TAPPI|ANSI|AATCC|IEEE|NF|GOST|UNI|ECCA)(?:[ -][A-Z]{1,4})?[ -]?\d",
    re.IGNORECASE,
)


# 시험 항목 id → 문장에서 잡을 낱말. 짧은 낱말(「peel」 「tear」)은 「test/testing/strength」 와 같이 나올 때만.
TEST_WORDS: dict[str, str] = {
    "tensile": r"\btensile\b(?! impact)|\buniaxial tension\b|\btension tests?\b",
    "compression": r"\bcompress(?:ion|ive) (?:test|strength|modulus|load|behavio|propert)",
    "flexure": r"\b(?:flexur(?:e|al)|bending|three-point bend|3-point bend|four-point bend)\b",
    "peel": r"\bpeel(?:ing)? (?:test|strength|adhesion|force)",
    "tear": r"\btear(?:ing)? (?:test|strength|resistance)",
    "shear": r"\b(?:lap[- ]shear|shear (?:test|strength|modulus))",
    "puncture": r"\bpuncture (?:test|resistance|strength)",
    "creep": r"\bcreep\b",
    "relaxation": r"\bstress[- ]relaxation\b",
    "fatigue": r"\bfatigue\b(?! crack)",
    "fracture_toughness": r"\b(?:fracture toughness|crack growth|crack propagation|K_?IC)\b",
    "torsion": r"\btorsion(?:al)?\b",
    "hardness_vickers": r"\bvickers\b",
    "hardness_knoop": r"\bknoop\b",
    "hardness_brinell": r"\bbrinell\b",
    "hardness_rockwell": r"\brockwell\b",
    "hardness_shore": r"\b(?:shore [A-D]\b|durometer)",
    "hardness_leeb": r"\bleeb\b",
    "instrumented_indentation": r"\b(?:nano-?indentation|instrumented indentation|nanoindent)",
    "scratch_pencil_hardness": r"\b(?:scratch (?:test|resistance|hardness)|pencil hardness)",
    "abrasion": r"\b(?:abrasion|taber|wear resistance)\b",
    "friction_wear_tribo": r"\b(?:tribolog|pin-on-disk|pin-on-disc|ball-on-disk|reciprocating wear)",
    "friction_coefficient": r"\bcoefficient of friction\b",
    "charpy_impact": r"\bcharpy\b",
    "izod_impact": r"\bizod\b",
    "drop_weight_impact": r"\b(?:drop[- ]weight|drop tower|falling weight)\b",
    "free_fall_drop": r"\b(?:free[- ]fall|drop test)",
    "tensile_impact": r"\btensile impact\b",
    "high_speed_tensile": r"\bhigh (?:strain[- ]rate|speed) tensile\b",
    "dma": r"\b(?:dynamic mechanical|DMA|storage modulus|loss modulus|tan ?δ|tan delta)\b",
    "dsc": r"\b(?:differential scanning|DSC|glass transition|melting enthalpy)\b",
    "tga": r"\b(?:thermogravimetr|TGA)\b",
    "tma": r"\b(?:thermomechanical analy|TMA|coefficient of thermal expansion|CTE)\b",
    "dilatometry": r"\bdilatomet",
    "thermal_conductivity": r"\b(?:thermal (?:conductivity|diffusivity)|laser flash|hot disk)\b",
    "rheology_rotational": r"\b(?:rheolog|rheometer|viscoelastic|oscillatory shear|viscosity)\b",
    "rheology_capillary": r"\bcapillary rheomet",
    "melt_flow": r"\b(?:melt flow|MFR|MFI|MVR)\b",
    "hdt": r"\b(?:heat deflection|heat distortion|HDT)\b",
    "vicat": r"\bvicat\b",
    "temperature_cycling": r"\b(?:thermal cycling|temperature cycl)",
    "thermal_shock": r"\bthermal shock\b",
    "damp_heat": r"\b(?:damp heat|85 ?°?C ?/ ?85 ?%|temperature[- ]humidity|humidity test)",
    "hast": r"\b(?:HAST|highly accelerated stress|pressure cooker)\b",
    "halt_hass": r"\b(?:HALT|HASS)\b",
    "vibration_sine_random": r"\b(?:random vibration|sine vibration|vibration test|shaker)\b",
    "mechanical_shock": r"\b(?:mechanical shock|half[- ]sine|shock pulse|shock test)",
    "salt_spray_corrosion": r"\b(?:salt (?:spray|fog)|cyclic corrosion)\b",
    "accelerated_weathering": r"\b(?:weathering|xenon arc|UV exposure|QUV)\b",
    "dielectric_withstand": r"\b(?:hipot|dielectric (?:withstand|strength)|withstand voltage)",
    "insulation_resistance": r"\binsulation resistance\b",
    "leak_rate": r"\b(?:leak (?:test|rate|detection)|helium leak)",
    "coating_thickness": r"\bcoating thickness\b",
    "coating_adhesion": r"\b(?:cross-?(?:cut|hatch)|adhesion test)",
    "surface_topography": r"\b(?:surface roughness|profilomet|topograph|step height)",
    "contact_angle": r"\b(?:contact angle|surface energy|wettability)\b",
    "particle_size": r"\b(?:particle size|zeta potential|dynamic light scattering|DLS)\b",
    "density_porosity": r"\b(?:pycnomet|porosimet|BET surface|true density)",
    "crystal_structure_analysis": r"\b(?:X-?ray diffraction|XRD|crystallin)",
    "composition_analysis": r"\b(?:XRF|XPS|EDS|EDX|elemental (?:analysis|composition)|Auger)\b",
    "microscopy": r"\b(?:SEM|TEM|AFM|scanning electron|transmission electron|atomic force)\b",
    "optical_spectroscopy": r"\b(?:UV-?Vis|FT-?IR|Raman|ellipsomet|fluorescence spectr|absorbance)",
    "electrical_transport": r"\b(?:four[- ]point probe|Hall (?:effect|mobility)|sheet resistance|I-V characteristic)",
    "battery_cycle_life": r"\b(?:charge[- /]discharge|cycl(?:e|ing) life|galvanostatic|C-rate)\b",
    "thermal_runaway_calorimetry": r"\b(?:thermal runaway|accelerating rate calorimet|ARC\b)",
    "wire_bond_strength": r"\b(?:wire[- ]bond|die shear|ball shear|bond pull)",
    "crimp_pull_strength": r"\bcrimp",
    "xray_void_inspection": r"\b(?:X-?ray inspection|computed tomography|micro-?CT|void(?:ing)? (?:analysis|inspection))",
    "acoustic_delamination": r"\b(?:scanning acoustic|C-SAM|acoustic microscop|delamination)",
    "esd_immunity": r"\b(?:electrostatic discharge|ESD)\b",
    "emi_emission": r"\b(?:EMI|radiated emission|conducted emission)\b",
    "surge_eft_immunity": r"\b(?:surge|EFT|burst immunity)\b",
    "thermography": r"\b(?:thermograph|infrared (?:camera|imaging)|thermal imag)",
    "texture": r"\btexture analy",
    "water_content": r"\bkarl fischer\b",
    "vapor_sorption": r"\b(?:vapor sorption|DVS|water uptake)\b",
    "formability": r"\b(?:forming limit|FLD|FLC|Erichsen|cupping)\b",
    "burst_pressure": r"\b(?:burst (?:pressure|test)|hoop stress)",
    "seal_strength": r"\bseal strength\b",
    "mechanical_endurance": r"\b(?:endurance test|cycle life test|durability test)",
    "thermal_resistance": r"\b(?:junction[- ]to[- ]|thermal resistance|R_?th\b|structure function)",
    "thermal_profiling": r"\breflow profil",
    "photometry_colorimetry": r"\b(?:luminance|chromaticity|colorimet|photomet)",
    "audio_performance": r"\b(?:THD\+?N|frequency response|audio analy)",
    "power_consumption": r"\b(?:power analy|efficiency measurement|standby power)",
    "solderability": r"\b(?:solderability|wetting balance)",
    "shielding_effectiveness": r"\bshielding effectiveness\b",
    "dust_ingress": r"\b(?:dust (?:test|ingress)|IP[56]X)\b",
    "water_ingress": r"\b(?:water ingress|IPX[0-9]|rain test|immersion test)\b",
    "altitude_low_pressure": r"\b(?:altitude|low[- ]pressure) test",
    "hardness_irhd": r"\bIRHD\b",
    "thermomechanical_fatigue": r"\bthermo-?mechanical fatigue\b",
    "battery_abuse": r"\b(?:nail penetration|crush test|overcharge test)",
    "ground_bond": r"\bground bond\b",
}
TEST_RE = {k: re.compile(v, re.IGNORECASE) for k, v in TEST_WORDS.items()}
CUE = re.compile(
    r"\b(test|tests|tested|testing|measure|measured|measurement|perform|performed|determin|characteriz|evaluat|analy|used for|ideal for|suitable for)",
    re.IGNORECASE,
)


def key(code: str) -> str:
    """비교키 — 공백을 지우고, 판(edition)을 뗀다: MIL-STD-883E → MIL-STD-883, ASTM D638-2014 → ASTM D638."""
    k = re.sub(r"\s+", "", code).upper().replace("–", "-")
    k = re.sub(r"-(19|20)\d\d$", "", k)
    if k.startswith(("MIL-STD-", "MIL-DTL-", "MIL-PRF-")):
        k = re.sub(r"(\d)[A-Z]$", r"\1", k)
    return k


def pretty(code: str) -> str:
    """「ASTMD638」 → 「ASTM D638」. 기관 뒤에 띄어쓰기 하나."""
    code = re.sub(r"-(19|20)\d\d$", "", code.replace("–", "-").upper())
    if code.startswith(("MIL-STD-", "MIL-DTL-", "MIL-PRF-")):
        return re.sub(r"(\d)[A-Z]$", r"\1", code)
    m = re.match(r"^([A-Z]+(?:/[A-Z]+)?)[ -]?(.*)$", code)
    if not m:
        return code
    body, rest = m.group(1), m.group(2).strip()
    return f"{body} {rest}" if rest else body


def known_codes(obj: dict) -> set[str]:
    st = obj.get("standards") or {}
    out = {key(str(c)) for c in (st.get("compliance") or [])}
    out |= {key(str(c)) for c in (st.get("test_methods") or [])}
    for lst in (st.get("test_methods_by_item") or {}).values():
        out |= {key(str(c)) for c in lst}
    return out


def evidence_for(oid: str) -> dict[str, dict]:
    """규격 → {grade2: [url…], grade3: [url…], papers: [pmcid…]}."""
    found: dict[str, dict] = {}

    def slot(code: str) -> dict:
        return found.setdefault(key(code), {"code": pretty(code), "grade2": [], "grade3": [], "papers": []})

    for page in sorted((HERE / "pages").glob(f"*/{oid}/*.json"), key=lambda p: int(p.stem)):
        d = json.loads(page.read_text(encoding="utf-8"))
        if d.get("status") != 200:
            continue
        for code in d.get("standards_in_page") or []:
            bucket = "grade2" if d.get("grade") == 2 else "grade3"
            s = slot(code)
            if d["url"] not in s[bucket]:
                s[bucket].append(d["url"])
    papers = HERE / "papers" / f"{oid}.json"
    if papers.exists():
        d = json.loads(papers.read_text(encoding="utf-8"))
        for snip in d.get("usage_snippets") or []:
            for code in snip.get("standards") or []:
                s = slot(code)
                if snip.get("pmcid") and snip["pmcid"] not in s["papers"]:
                    s["papers"].append(snip["pmcid"])
    return found


def _decided_before(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows") or []
    return {r["subject"]: r["decided"] for r in rows if r.get("decided")}


def _doc(queue: str, rows: list[dict]) -> dict:
    return {
        "queue": queue,
        "generated": date.today().isoformat(),
        "note": "source/catalog_extension/tools_propose.py 가 만든다. decided 만 사람(검토함)이 채운다.",
        "rows": rows,
    }


def _excerpt(text: str, m: re.Match, span: int = 110) -> str:
    a, b = max(0, m.start() - span), min(len(text), m.end() + span)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


def _mention_sentence(text: str) -> str:
    """usage_snippet 은 기종 언급 앞 350자 + 뒤 350자다. 언급 자리(≈350)를 품은 문장 하나."""
    pos = 350 if len(text) > 400 else len(text) // 2
    starts = [m.end() for m in re.finditer(r"[.;!?]\s+(?=[A-Z(])", text[:pos])]
    a = starts[-1] if starts else 0
    m = re.search(r"[.;!?]\s+(?=[A-Z(])", text[pos:])
    b = pos + m.start() + 1 if m else len(text)
    return text[a:b].strip()


def build_test_items(objects: list[dict], items: dict[str, dict]) -> list[dict]:
    """이 계열이 이 시험도 하나 — 기종을 언급한 논문 문장과 제조사 응용 문장에서."""
    rows = []
    decided_before = _decided_before(OUT_ITEMS)
    for obj in objects:
        oid = obj["id"]
        have = set(obj.get("test_items") or [])
        hits: dict[str, dict] = {}

        def add(item: str, kind: str, source: str, quote: str) -> None:
            h = hits.setdefault(item, {"papers": [], "pages": [], "quotes": []})
            bucket = h["papers"] if kind == "paper" else h["pages"]
            if source not in bucket:
                bucket.append(source)
            if len(h["quotes"]) < 3 and quote not in h["quotes"]:
                h["quotes"].append(quote)

        papers = HERE / "papers" / f"{oid}.json"
        if papers.exists():
            for snip in json.loads(papers.read_text(encoding="utf-8")).get("usage_snippets") or []:
                # 앞뒤 350자 창 전체가 아니라 **기종을 언급한 그 문장**만 본다 — 논문의 방법 절은 장비를
                # 줄줄이 나열해서, 창 전체로 보면 옆 장비의 SEM·XRD 가 이 계열의 시험이 된다.
                sentence = _mention_sentence(snip.get("text") or "")
                for item, rx in TEST_RE.items():
                    if item in have or item not in items:
                        continue
                    m = rx.search(sentence)
                    if m:
                        add(item, "paper", snip.get("pmcid") or "?", _excerpt(sentence, m))
        for page in sorted((HERE / "pages").glob(f"*/{oid}/*.json"), key=lambda p: int(p.stem)):
            d = json.loads(page.read_text(encoding="utf-8"))
            if d.get("status") != 200 or d.get("grade") != 2 or d.get("kind") != "html":
                continue
            for sentence in re.split(r"(?<=[.!?])\s+|\n", d.get("text") or ""):
                sentence = sentence.strip()
                if not (40 <= len(sentence) <= 300) or not CUE.search(sentence):
                    continue
                for item, rx in TEST_RE.items():
                    if item in have or item not in items:
                        continue
                    if rx.search(sentence):
                        add(item, "page", d["url"], sentence)
        cands = []
        for item, h in hits.items():
            score = 2 * len(h["papers"]) + 3 * len(h["pages"])
            recommended = len(h["papers"]) >= 2 or len(h["pages"]) >= 1
            parts = []
            if h["pages"]:
                parts.append(f"제조사 문장 {len(h['pages'])}")
            if h["papers"]:
                parts.append(f"논문 {len(h['papers'])}편")
            cands.append(
                {
                    "code": item,
                    "reason": " · ".join(parts) + " — 「" + h["quotes"][0][:160] + "」",
                    "sources": h["pages"][:3] + h["papers"][:3],
                    "_w": score,
                    "_r": recommended,
                }
            )
        if not cands:
            continue
        cands.sort(key=lambda c: (-c["_w"], c["code"]))
        cands = cands[:12]
        recommended = [c["code"] for c in cands if c["_r"]]
        for c in cands:
            c.pop("_w"), c.pop("_r")
        row = {
            "subject": oid,
            "series": obj["name"],
            "manufacturer": obj["manufacturer"],
            "candidates": cands,
            "recommended": recommended,
            "reason": "논문 둘 이상이 이 기종으로 그 시험을 했거나, 제조사 문장이 말한다" if recommended else None,
            "hint": "낱말이 문장에 나온 것뿐이다 — 인용문을 읽고 이 계열이 그 시험을 **하는** 것인지 본다(옆 장비 얘기일 수 있다)",
        }
        if oid in decided_before:
            row["decided"] = decided_before[oid]
        rows.append(row)
    return rows


def build_summary(objects: list[dict]) -> list[dict]:
    """이 문장을 계열 소개에 넣을까 — 제조사 페이지의 응용 문장."""
    from tools_harvest import APPLY_RE, tokens_of

    rows = []
    decided_before = _decided_before(OUT_SUMMARY)
    for obj in objects:
        oid = obj["id"]
        toks = [t.lower() for t in tokens_of(obj) if len(t) >= 3]
        seen: list[str] = []
        cands = []
        for page in sorted((HERE / "pages").glob(f"*/{oid}/*.json"), key=lambda p: int(p.stem)):
            d = json.loads(page.read_text(encoding="utf-8"))
            if d.get("status") != 200 or d.get("grade") != 2:
                continue
            for m in APPLY_RE.finditer(d.get("text") or ""):
                sentence = re.sub(r"\s+", " ", m.group(1)).strip()
                if not (60 <= len(sentence) <= 320) or sentence in seen:
                    continue
                low = sentence.lower()
                if not any(t in low for t in toks) and "series" not in low:
                    continue
                if "cookie" in low or "©" in sentence or "privacy" in low:
                    continue
                seen.append(sentence)
                cands.append({"code": f"s{len(cands) + 1}", "label": sentence, "sources": [d["url"]]})
                if len(cands) >= 5:
                    break
            if len(cands) >= 5:
                break
        if not cands:
            continue
        row = {
            "subject": oid,
            "series": obj["name"],
            "manufacturer": obj["manufacturer"],
            "candidates": cands,
            "recommended": [],
            "hint": "고른 문장이 계열 소개 뒤에 붙는다. 마케팅 문구는 빼고, 무엇에 쓰는지 말하는 문장만",
        }
        if oid in decided_before:
            row["decided"] = decided_before[oid]
        rows.append(row)
    return rows


def build() -> dict:
    rows = []
    objects = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CATALOG / "equipment").rglob("*.json"))]
    decided_before = _decided_before(OUT)
    titles = json.loads(TITLES.read_text(encoding="utf-8")) if TITLES.exists() else {}
    for obj in objects:
        oid = obj["id"]
        have = known_codes(obj)
        evid = evidence_for(oid)
        cands = []
        for k, e in evid.items():
            if k in have or NOISE.match(e["code"]) or not SHAPE.match(e["code"]):
                continue
            weight = 3 * len(e["grade2"]) + len(e["grade3"]) + 0.5 * len(e["papers"])
            recommended = bool(e["grade2"]) or len(e["grade3"]) >= 2
            parts = []
            if e["grade2"]:
                parts.append(f"제조사 페이지 {len(e['grade2'])}쪽")
            if e["grade3"]:
                parts.append(f"남의 페이지 {len(e['grade3'])}쪽")
            if e["papers"]:
                parts.append(f"논문 {len(e['papers'])}편")
            cands.append(
                {
                    "code": e["code"],
                    "title": (titles.get(e["code"]) or {}).get("title"),
                    "reason": " · ".join(parts),
                    "sources": (e["grade2"] + e["grade3"])[:4] + e["papers"][:2],
                    "_w": weight,
                    "_r": recommended,
                }
            )
        if not cands:
            continue
        cands.sort(key=lambda c: (-c["_w"], c["code"]))
        cands = cands[:MAX_PER_SERIES]
        recommended = [c["code"] for c in cands if c["_r"]]
        for c in cands:
            c.pop("_w"), c.pop("_r")
        row = {
            "subject": oid,
            "series": obj["name"],
            "manufacturer": obj["manufacturer"],
            "candidates": cands,
            "recommended": recommended,
            "reason": "제조사 페이지에 나왔거나 남의 페이지 둘 이상이 함께 적은 규격" if recommended else None,
            "hint": "인용 페이지가 이 계열 것인지 링크로 확인 — 대리점 목록 페이지는 옆 제품의 규격일 수 있다",
        }
        if oid in decided_before:
            row["decided"] = decided_before[oid]
        rows.append(row)
    return _doc("series_standards", rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    objects = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CATALOG / "equipment").rglob("*.json"))]
    items = {
        row["id"]: row
        for row in json.loads((CATALOG / "ontology" / "test_items.json").read_text(encoding="utf-8"))["test_items"]
    }
    docs = [
        (OUT, build()),
        (OUT_ITEMS, _doc("series_test_items", build_test_items(objects, items))),
        (OUT_SUMMARY, _doc("series_summary", build_summary(objects))),
    ]
    for path, doc in docs:
        n_c = sum(len(r["candidates"]) for r in doc["rows"])
        n_r = sum(len(r.get("recommended") or []) for r in doc["rows"])
        print(f"{doc['queue']}: 계열 {len(doc['rows'])} · 후보 {n_c} · 추천 {n_r}")
        if not args.check:
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
