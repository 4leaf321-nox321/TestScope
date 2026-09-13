"""부속·옵션 페이지를 모은다 — 「이 그립·챔버·익스텐소미터가 어느 계열에 붙나」 의 원료.

    python tools_harvest_accessories.py             # 받고, 언급을 뽑는다 (있는 페이지는 건너뜀)
    python tools_harvest_accessories.py --only instron
    python tools_harvest_accessories.py --extract    # 받지 않고 언급만 다시 뽑는다

## 왜 따로 받나

계열 페이지에서 같은 제조사의 다른 기종 이름을 찾으면 거의 사이트 메뉴다(어느 페이지든 「3400 · 5900 · 6800」 이
서 있다). 관계는 **부속 페이지**가 말한다 — 「Compatible with 3400, 5900, 6800 Series」 처럼. 그래서 제조사
사이트맵에서 부속·옵션 경로만 골라 따로 받고, 사이트 전체에 나오는 토막은 메뉴로 보고 뺀다.

## 무엇을 만드나
- accessories/<제조사>/<n>.json   부속 페이지 하나 — url · title · text(8만 자까지) · kind
- accessory_mentions.json          페이지마다: 제목 · 본문에 나온 카탈로그 객체(사이트 공통 토막 제외) ·
                                   그 페이지가 카탈로그의 부속 객체와 맞는지(있으면 그 id)

## 메뉴 토막 거르기

제조사마다 받은 부속 페이지의 80 % 이상에 나오는 토막은 메뉴다. 「3400」 이 Instron 부속 페이지 76쪽 중
70쪽에 나오면 그건 아무 관계도 아니다. 소수 페이지에만 나오는 토막이 「이 부속이 이 계열에 붙는다」 의
낌새이고, 그것도 후보일 뿐 — 검토함에서 사람이 고른다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "catalog"
ACC = HERE / "accessories"
OUT = HERE / "accessory_mentions.json"
sys.path.insert(0, str(HERE))
from tools_harvest import PAUSE, fetch_bytes, page_content, sitemap_urls, tokens_of  # noqa: E402

# 제조사 → 사이트맵에서 고를 경로(정규식) · 상한. 영어 경로만.
VENDORS: dict[str, tuple[str, int]] = {
    "instron": (r"instron\.com/en/products/testing-accessories/[^/]+/[^/]+/?$", 120),
    "zwickroell": (r"zwickroell\.com/accessories/", 60),
    "mts": (r"mts\.com/en/products/materials/(grips|extensometers|environmental|fixtures|furnaces)[^?]*$", 120),
    "shimadzu": (r"shimadzu\.com/an/products/materials-testing[^?]*(grip|jig|extenso|chamber|furnace|accessor|fixture|option)[^?]*$", 100),
    "tinius-olsen": (r"tiniusolsen\.com/product/[^/]*(grip|fixture|extenso|chamber|furnace|accessor)[^/]*/?$", 60),
    "mecmesin": (r"mecmesin\.com/accessory/", 200),
    "testometric": (r"testometric\.co\.uk/[^/]*(grip|fixture|holder|extenso|chamber|jig)[^/]*/$", 60),
    "hegewald-peschke": (r"hegewald-peschke\.com/products/accessories[^?]*$", 60),
    "anton-paar": (r"anton-paar\.com/corp-en/products/details/[^/]*(cell|chamber|stage|fixture|holder|probe|accessor|option|module|hood|oven|humidity|temperature)[^/]*/?$", 80),
    "ametek-lloyd": (r"ametektest\.com/products/(extensometers|accessories|grips|fixtures)[^?]*$", 80),
    "emco-test": (r"emcotest\.com/en/accessories", 20),
    "bareiss": (r"bareiss\.de/en/product-overview/accessories", 20),
    "micromeritics": (r"micromeritics\.com/accessory/", 40),
    "stable-micro-systems": (r"stablemicrosystems\.com/(probes-and-attachments|[^/]*attachment)[^?]*$", 60),
    "taber": (r"taberindustries\.com/[^/]*(attachment|option|accessor)[^/]*$", 20),
    "weiss-technik": (r"weiss-technik\.com/en/products/detail/", 30),
    "q-lab": (r"q-lab\.com/(en-us/)?products/[^?]*(accessor|option|holder|rack)[^?]*$", 20),
}
BAD = re.compile(r"\.pdf$|/(de|fr|es|it|ja|zh|zh-hans|zh-hant|ko|pt|pt-br|ru|pl|nl|tr|cs|sv|da|fi|hu|th|vi)/", re.I)


def harvest(only: str | None) -> None:
    makers = {m["id"]: m for m in json.loads((CATALOG / "ontology" / "manufacturers.json").read_text(encoding="utf-8"))["manufacturers"]}
    today = date.today().isoformat()
    for vendor, (pattern, cap) in VENDORS.items():
        if only and vendor != only:
            continue
        maker = makers.get(vendor) or {}
        if not maker.get("website"):
            continue
        urls = [u for u in sitemap_urls(maker["website"]) if re.search(pattern, u) and not BAD.search(u)]
        urls = list(dict.fromkeys(urls))[:cap]
        folder = ACC / vendor
        folder.mkdir(parents=True, exist_ok=True)
        have = {json.loads(p.read_text(encoding="utf-8"))["url"] for p in folder.glob("*.json")}
        n = len(have)
        print(f"{vendor}: 사이트맵 후보 {len(urls)} · 있음 {n}")
        for url in urls:
            if url in have:
                continue
            code, raw = fetch_bytes(url)
            time.sleep(PAUSE)
            kind, title, text, _ = page_content(raw) if code == 200 else ("html", "", "", [])
            n += 1
            (folder / f"{n}.json").write_text(
                json.dumps(
                    {"manufacturer": vendor, "url": url, "retrieved": today, "status": code, "kind": kind, "title": title, "text": text[:80_000]},
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
        print(f"{vendor}: 받음 {n}", flush=True)


def extract() -> dict:
    objects = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CATALOG / "equipment").rglob("*.json"))]
    makers = {m["id"]: m for m in json.loads((CATALOG / "ontology" / "manufacturers.json").read_text(encoding="utf-8"))["manufacturers"]}
    by_maker: dict[str, list[dict]] = {}
    for o in objects:
        by_maker.setdefault(o["manufacturer"], []).append(o)
    out: dict[str, dict] = {}
    for folder in sorted(ACC.glob("*")):
        vendor = folder.name
        pages = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"), key=lambda p: int(p.stem))]
        pages = [p for p in pages if p.get("status") == 200 and p.get("text")]
        if not pages:
            continue
        # 객체 토막 — 기종 번호(「34sc-5」 「mp1200」)와 계열 이름(「allroundline」). 세 자리 숫자만인
        # 것(「300」)은 뺀다 — 온도·하중과 헷갈린다. 「3400」 같은 네 자리는 두되 메뉴 거르기에 맡긴다.
        tok_of: dict[str, list[str]] = {}
        maker_name = makers.get(vendor, {}).get("name", "")
        for o in by_maker.get(vendor, []):
            toks = [t.lower() for t in tokens_of(o, maker_name) if len(t) >= 3 and not re.fullmatch(r"\d{1,3}", t)]
            if toks:
                tok_of[o["id"]] = toks
        # 페이지마다 어느 객체가 언급되나
        per_page: list[dict[str, int]] = []
        for p in pages:
            low = p["text"].lower()
            hits: dict[str, int] = {}
            for oid, toks in tok_of.items():
                c = sum(len(re.findall(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low)) for t in toks)
                if c:
                    hits[oid] = c
            per_page.append(hits)
        # 사이트 공통(메뉴) — 80 % 이상의 페이지에 나오는 객체
        freq: dict[str, int] = {}
        for hits in per_page:
            for oid in hits:
                freq[oid] = freq.get(oid, 0) + 1
        common = {oid for oid, f in freq.items() if len(pages) >= 5 and f >= 0.8 * len(pages)}
        accessories = [o for o in by_maker.get(vendor, []) if o["kind"] in ("accessory", "sensor")]
        for p, hits in zip(pages, per_page):
            title_low = (p.get("title") or "").lower()
            matches_obj = next(
                (o["id"] for o in accessories if any(t in title_low for t in tok_of.get(o["id"], []))), None
            )
            content_hits = {oid: c for oid, c in hits.items() if oid not in common}
            out[p["url"]] = {
                "manufacturer": vendor,
                "title": p.get("title"),
                "catalog_accessory": matches_obj,
                "series_mentioned": dict(sorted(content_hits.items(), key=lambda kv: -kv[1])),
            }
        print(f"{vendor}: 부속 페이지 {len(pages)} · 메뉴로 뺀 객체 {sorted(common)}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    if not args.extract:
        harvest(args.only)
    mentions = extract()
    OUT.write_text(json.dumps({"generated": date.today().isoformat(), "pages": mentions}, ensure_ascii=False, indent=1), encoding="utf-8")
    with_hits = sum(1 for v in mentions.values() if v["series_mentioned"])
    matched = sum(1 for v in mentions.values() if v["catalog_accessory"])
    print(f"부속 페이지 {len(mentions)} · 계열 언급 있는 것 {with_hits} · 카탈로그 부속 객체와 맞는 것 {matched} → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
