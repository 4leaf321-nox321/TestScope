"""보강 원료에서 검토함 물음을 세운다 — 「이 계열이 이 규격도 하나」 (`proposals/series_standards.json`).

    python tools_propose.py            # source/catalog/proposals/series_standards.json 을 (다시) 쓴다
    python tools_propose.py --check    # 무엇이 서는지만 본다

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

## 결정은 어디로 가나

검토함이 확정하면 DB 에서 그 계열의 시험 항목에 규격이 붙고(`review.services._apply`),
`export_review.py` 가 이 파일의 `decided` 에 되돌려 쓴다. 반입은 `review.refresh` 가 `decided` 를
읽어 같은 일을 하므로, 카탈로그 객체 JSON 을 고치지 않아도 운영 서버에 그대로 간다.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "catalog"
OUT = CATALOG / "proposals" / "series_standards.json"

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


def build() -> dict:
    rows = []
    objects = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CATALOG / "equipment").rglob("*.json"))]
    previous = json.loads(OUT.read_text(encoding="utf-8"))["rows"] if OUT.exists() else []
    decided_before = {r["subject"]: r.get("decided") for r in previous if r.get("decided")}
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
    return {
        "queue": "series_standards",
        "generated": date.today().isoformat(),
        "note": "source/catalog_extension/tools_propose.py 가 만든다. decided 만 사람(검토함)이 채운다.",
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    doc = build()
    n_c = sum(len(r["candidates"]) for r in doc["rows"])
    n_r = sum(len(r["recommended"]) for r in doc["rows"])
    print(f"계열 {len(doc['rows'])} · 후보 {n_c} · 추천 {n_r}")
    if not args.check:
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
