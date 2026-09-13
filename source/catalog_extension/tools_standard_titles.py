"""규격 코드에 제목을 단다 — `standard_titles.json` (코드 → 제목·정식 표기·출처).

    python tools_standard_titles.py              # proposals/series_standards.json 의 후보 + 카탈로그 인용 규격
    python tools_standard_titles.py --only "ASTM D638"

## 어디서

1. **모은 페이지·논문 본문** — 「ASTM D638 Standard Test Method for Tensile Properties of Plastics」 처럼 코드
   뒤에 제목이 따라오는 자리. 공짜지만 143/883 정도만 잡힌다.
2. **ANSI 웹스토어 검색**(webstore.ansi.org/search/find?st=코드) — ISO·IEC·ASTM·BS·EN·DIN 을 다 판다. 결과 목록의
   「코드:연도」 줄 다음 줄이 제목이다. 정식 표기(판·연도)도 여기서 온다. 요청 사이 1.5초.
   MIL-STD·JIS·GB 는 잘 없다 — 그것은 1 로 남는다.

## 이것은 규격의 「이름」 이지 값이 아니다

검토함이 규격을 계열에 붙일 때 시험법 행을 새로 만들면 제목이 코드 그대로였다(「ASTM D638 — ASTM D638」).
여기 제목이 있으면 그것을 쓴다. 제목이 틀려도 검색 결과가 달라지지는 않는다 — 사람이 읽는 이름일 뿐이다.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import time
import urllib.parse
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "catalog"
OUT = HERE / "standard_titles.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
PAUSE = 1.5
NATIONAL = {"BS", "BSEN", "DIN", "DINEN", "DS", "DSEN", "NF", "NFEN", "SS", "SSEN", "UNE", "UNEEN", "EN", "ENISO", "ISO", "IEC"}
TITLE_WORDS = re.compile(
    r"(?:Standard (?:Test Methods?|Practices?|Specifications?|Guide|Terminology|Classification)"
    r"|Test method|Metallic materials|Plastics|Rubber|Environmental testing|Standard)\b[^.\n|]{8,140}",
    re.I,
)


def key(code: str) -> str:
    """비교키 — 공백·판·연도를 뗀다. 「IEC 60068-2-14 Ed. 7.0 b:2023」 → 「IEC60068-2-14」,
    「ASTM D638-22」 → 「ASTMD638」, 「ISO 527-2:2025」 → 「ISO527-2」."""
    k = code.upper().replace("–", "-")
    k = re.sub(r"\bED\.?\s*\d+(\.\d+)?\s*[A-Z]{0,2}\b", "", k)
    k = re.sub(r":(19|20)\d\d.*$", "", k)
    k = re.sub(r"\s+", "", k)
    k = re.sub(r"-(19|20)\d\d$", "", k)
    k = re.sub(r"-\d\d$", "", k) if re.match(r"^ASTM", k) else k  # ASTM 의 「-22」 는 연도
    if k.startswith(("MIL-STD-", "MIL-DTL-")):
        k = re.sub(r"(\d)[A-Z]$", r"\1", k)
    return k


def wanted_codes() -> list[str]:
    codes: set[str] = set()
    path = CATALOG / "proposals" / "series_standards.json"
    if path.exists():
        for row in json.loads(path.read_text(encoding="utf-8"))["rows"]:
            codes |= {c["code"] for c in row["candidates"]}
    for p in (CATALOG / "equipment").rglob("*.json"):
        st = json.loads(p.read_text(encoding="utf-8")).get("standards") or {}
        codes |= {str(c) for c in st.get("test_methods") or []}
        for lst in (st.get("test_methods_by_item") or {}).values():
            codes |= {str(c) for c in lst}
    return sorted(c for c in codes if c and re.search(r"\d", c))


CODE_TITLE = re.compile(
    r"\b((?:ASTM|ISO|IEC|EN|DIN|JIS|KS|BS|GB/T|GB|SAE|UL|CSA|IPC|JEDEC|JESD|MIL-STD|MIL-DTL|ISTA|VDA|GMW|AASHTO"
    r"|TAPPI|ANSI|AATCC|IEEE)(?:[ -][A-Z]{1,4})?[ -]?\d{2,6}(?:[-–.]\d{1,4}){0,3})"
    r"(?:[-–:]\d{2,4})?(?:\s*\(\d{4}\))?\s*[:–—-]?\s*(" + TITLE_WORDS.pattern + ")"
)


def from_text(codes: list[str]) -> dict[str, dict]:
    """모은 본문에서 「코드 제목」 을 찾는다 — 본문 한 번 훑어 코드별로 모은다(코드마다 훑으면
    3천만 자 × 천 번이라 한 시간이 넘는다). 같은 제목이 여러 번이면 그것."""
    wanted = {key(c): c for c in codes}
    counts: dict[str, dict[str, int]] = {}

    def scan(text: str) -> None:
        for m in CODE_TITLE.finditer(text):
            k = key(m.group(1))
            if k not in wanted:
                continue
            t = re.sub(r"\s+", " ", m.group(2)).strip(" -–—:")[:140]
            bucket = counts.setdefault(wanted[k], {})
            bucket[t] = bucket.get(t, 0) + 1

    for f in (HERE / "pages").glob("*/*/*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("status") == 200:
            scan(d.get("text") or "")
        for fo in d.get("followed") or []:
            scan(fo.get("text") or "")
    for f in (HERE / "papers").glob("*.json"):
        for snip in json.loads(f.read_text(encoding="utf-8")).get("usage_snippets") or []:
            scan(snip["text"])
    out: dict[str, dict] = {}
    for code, bucket in counts.items():
        best = max(bucket.items(), key=lambda kv: (kv[1], -len(kv[0])))
        if best[1] >= 2 or best[0].lower().startswith(("standard ", "test method")):
            out[code] = {"title": best[0], "source": "harvested text", "hits": best[1]}
    return out


def from_ansi(code: str) -> dict | None:
    url = "https://webstore.ansi.org/search/find?in=1&st=" + urllib.parse.quote(code)
    page = ""
    for attempt in range(3):
        done = subprocess.run(["curl", "-sSL", "--compressed", "-A", UA, "--max-time", "40", url], capture_output=True)
        time.sleep(PAUSE)
        page = done.stdout.decode("utf-8", errors="replace")
        if "/standards/" in page:
            break
        time.sleep(5 * (attempt + 1))  # 가끔 빈 페이지를 준다 — 쉬었다가 다시
    rows: list[tuple[str, str]] = []
    for m in re.finditer(r'<a[^>]+href="(/standards/[^"]+)"[^>]*>(.*?)</a>', page, re.S):
        text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if text:
            rows.append((m.group(1), text))
    want = key(code)

    def title_after(i: int, href: str) -> str | None:
        for href2, text2 in rows[i + 1 : i + 3]:
            if href2 == href and key(text2) != want and len(text2) > 12:
                return text2[:200]
        return None

    # 1) 코드가 같은 정식 표기 줄(판만 다름) — 「ISO 527-2:2025」 「ASTM D638-22」
    # 2) 국가 채택판 — 「BS EN ISO 527-2」 「DIN EN 10002-5」 가 같은 규격이다
    # 3) 「ISO 1133」 처럼 지금은 「ISO 1133-1」 로 갈라졌거나 「ASTM A956/A956M」 로 합쳐진 것 — 그 첫 부분
    for pass_no in (1, 2, 3):
        for i, (href, text) in enumerate(rows):
            k = key(re.sub(r"\(.*?\)", "", text))
            hit = (
                k == want
                if pass_no == 1
                else (k.endswith(want) and k[: -len(want)] in NATIONAL)
                if pass_no == 2
                else (k.startswith(want + "-") or k.startswith(want + "/"))
            )
            if not hit:
                continue
            title = title_after(i, href)
            if title is None:
                continue
            found = {
                "title": title,
                "designation": text,
                "source": "webstore.ansi.org",
                "url": "https://webstore.ansi.org" + href,
            }
            if pass_no > 1:
                found["note"] = "같은 코드가 없어 " + ("국가 채택판" if pass_no == 2 else "첫 부분/합본") + " 의 제목"
            return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only")
    parser.add_argument("--no-web", action="store_true", help="모은 본문에서만")
    parser.add_argument("--retry-missing", action="store_true", help="제목이 없는 것도 다시")
    args = parser.parse_args()
    have: dict[str, dict] = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    codes = [args.only] if args.only else wanted_codes()
    todo = [c for c in codes if c not in have or (args.retry_missing and not have[c].get("title"))]
    print(f"규격 {len(codes)} · 제목 있음 {len(codes) - len(todo)} · 찾을 것 {len(todo)}")
    today = date.today().isoformat()
    text_titles = from_text(todo) if todo else {}
    print(f"본문에서 {len(text_titles)}")
    for n, code in enumerate(todo, 1):
        found = None if args.no_web else from_ansi(code)
        if found:
            have[code] = {**found, "retrieved": today}
            print(f"[{n}/{len(todo)}] {code} → {found['title'][:70]}", flush=True)
        elif code in text_titles:
            have[code] = {**text_titles[code], "retrieved": today}
            print(f"[{n}/{len(todo)}] {code} → (본문) {text_titles[code]['title'][:70]}", flush=True)
        else:
            have[code] = {"title": None, "source": None, "retrieved": today}
        if n % 20 == 0:
            OUT.write_text(json.dumps(have, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    OUT.write_text(json.dumps(have, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"제목 있음 {sum(1 for v in have.values() if v.get('title'))}/{len(have)} → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
