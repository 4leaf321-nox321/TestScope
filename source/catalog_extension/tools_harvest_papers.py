"""카탈로그 보강 — 논문에서 「이 장비를 무엇에 어떻게 썼나」 를 모은다 (3등급 · 사용 예).

    python tools_harvest_papers.py                 전체 (있는 것은 건너뜀)
    python tools_harvest_papers.py --only instron
    python tools_harvest_papers.py --limit 10

어디서
- OpenAlex  (api.openalex.org)   제목·초록·주제 — 「Instron 5967」 을 언급한 논문 수와 상위 50편
- Europe PMC (ebi.ac.uk/europepmc) 오픈액세스 전문 — 언급 앞뒤 문장을 뽑는다. MDPI Materials·Polymers 가
  PMC 에 있어 재료 시험 논문이 꽤 잡힌다
- Wikipedia                        제조사 소개 한 단락 (배경 — 값이 아니다)

무엇을 만드나
- papers/<객체 id>.json   query · openalex{count, works[]} · europepmc{count, papers[]} · usage_snippets[] ·
                          standards_found · test_item_hits
- wiki/<제조사>.json       제목 · 요약 · url

## 이것은 원료다

논문이 「Instron 5967 로 ASTM D638 인장」 이라 했다고 그 계열이 그 규격에 맞는 것은 아니다 — 저자가
그렇게 썼다는 것뿐이다. 그러나 「이 계열을 실제로 무엇에 쓰나」 의 가장 넓은 표본이고, 제조사가
말하지 않는 용도(치과·생체·식품)가 여기서 나온다. 검토함에서 사람이 고른다.

요청 사이 0.4초. 둘 다 키가 없어도 된다. 다만 OpenAlex 는 하루 예산이 있어(키 없이 약 100건) 넘으면 429 를
낸다 — `count` 가 null 로 남은 객체는 다음 날 `--fill-openalex` 로 채운다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "catalog"
PAPERS = HERE / "papers"
WIKI = HERE / "wiki"
PAUSE = 0.4
UA = "TestScope-catalog-harvest/1 (+https://github.com/; contact via repo)"

sys.path.insert(0, str(HERE))
from tools_harvest import STANDARD_RE, known_standards, norm  # noqa: E402

MAKER_SUFFIX = re.compile(
    r"\b(Corporation|Corp\.?|Inc\.?|GmbH|Co\.,? ?Ltd\.?|Ltd\.?|LLC|AG|AB|KK|K\.K\.|S\.A\.|Company|Group|Technologies|Technology"
    r"|Analyzing & Testing|Analytical Science|Digital Industries|Test & Inspection|Test & Measurement|Sensing|Scientific"
    r"|Electronics|Metrology|Manufacturing|Industries|Cryotronics|Testing Machinery|Laboratory)\b\.?",
    re.IGNORECASE,
)
GENERIC = {"series", "system", "systems", "tester", "testers", "testing", "machine", "machines", "universal",
           "analyzer", "analyzers", "analyser", "chamber", "chambers", "test", "kit", "model", "and", "for", "with",
           "single", "column", "dual", "floor", "table", "type", "high", "low", "the", "of", "to", "kn", "kv", "hz"}


def maker_names(name: str) -> list[str]:
    """「Bruker (Hysitron)」 → [Bruker, Hysitron] · 「Teseq / AMETEK CTS」 → [Teseq, AMETEK CTS] ·
    「Anton Paar GmbH」 → [Anton Paar]. 논문이 부르는 이름들 — 첫째가 주 이름."""
    parts = re.findall(r"\(([^)]*)\)", name)
    head = re.sub(r"\(.*?\)", "", name)
    out: list[str] = []
    for piece in re.split(r"\s*/\s*", head) + parts:
        piece = MAKER_SUFFIX.sub("", piece).replace(",", " ")
        piece = re.sub(r"\s+", " ", piece).strip(" -")
        if piece and not re.search(r"[가-힣]", piece) and piece.lower() not in {p.lower() for p in out}:
            out.append(piece)
    return out or [name]


def maker_short(name: str) -> str:
    return maker_names(name)[0]


MODEL_RE = re.compile(r"\b[A-Z]{1,6}[- ]?\d[\w.\-]*\b")


def phrases_of(obj: dict, makers: list[str]) -> list[str]:
    """논문이 쓸 법한 「제조사 + 기종」 구절들. 「Instron 5967」 「Anton Paar MCR 302」 「Bruker D8 ADVANCE」.
    계열 이름에서 나온 것이 먼저, 모델 코드가 뒤. 제조사 별칭(Hysitron·Wilson)은 앞 두 기종에만 붙인다."""
    pieces: list[str] = []

    maker_words = {w.lower() for m in makers for w in m.split()}

    def add(piece: str) -> None:
        piece = re.sub(r"[()가-힣]", "", re.sub(r"\s+", " ", piece))
        ws = [w for w in piece.split() if w.lower() not in maker_words]
        piece = " ".join(ws).strip(" -–—/,")
        if len(piece) < 2 or piece.lower() in GENERIC:
            return
        if piece.lower() not in {p.lower() for p in pieces}:
            pieces.append(piece)

    maker = makers[0]
    name = re.sub(r"\(.*?\)", "", obj["name"])
    for m in makers:
        name = re.sub(re.escape(m), "", name, count=1, flags=re.IGNORECASE)
    name = name.strip(" -–:")
    words = [w for w in name.split() if w.lower() not in GENERIC and w not in ("/", "&")]
    if words:
        first = words[0]
        if any(ch.isdigit() for ch in first) or (first.isupper() and len(first) >= 2) or re.match(r"^[A-Z][a-z]+[A-Z]", first):
            if len(words) > 1 and (any(ch.isdigit() for ch in words[1]) or words[1].isupper()):
                add(" ".join(words[:2]))
            add(first)
    for piece in MODEL_RE.findall(name):
        add(piece)
    for m in obj.get("models") or []:
        code = (m.get("model") or "").strip()
        for piece in re.split(r"\s*/\s*", code):
            piece = re.sub(r"\(.*?\)", "", piece).strip()
            ws = piece.split()
            if not ws:
                continue
            # 「MCR 303」 「Z010」 「34SC-05」 처럼 숫자나 대문자 약자가 있어야 구절이 된다
            if any(ch.isdigit() for ch in piece) or (len(ws) <= 2 and ws[0].isupper()):
                add(" ".join(ws[:3]))
    if not pieces and words:
        # 「Kinexus」 「inVia」 「Discovery DSC」 처럼 숫자 없는 제품명 — 앞 두 낱말
        add(" ".join(words[:2]))
        add(words[0])
    pieces = pieces[:6]
    out = [f"{maker} {p}" for p in pieces]
    for alias in makers[1:2]:
        out += [f"{alias} {p}" for p in pieces[:2]]
    return out[:8]


def get_json(url: str) -> dict | None:
    done = subprocess.run(["curl", "-sS", "--compressed", "-A", UA, "--max-time", "60", url], capture_output=True)
    time.sleep(PAUSE)
    try:
        return json.loads(done.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        return None


def get_text(url: str) -> str:
    done = subprocess.run(["curl", "-sS", "--compressed", "-A", UA, "--max-time", "60", url], capture_output=True)
    time.sleep(PAUSE)
    return done.stdout.decode("utf-8", errors="replace")


def abstract_of(work: dict) -> str:
    inv = work.get("abstract_inverted_index") or {}
    if not inv:
        return ""
    slots: dict[int, str] = {}
    for word, positions in inv.items():
        for p in positions:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))


def openalex(phrases: list[str]) -> dict:
    q = " OR ".join(f'"{p}"' for p in phrases)
    url = (
        "https://api.openalex.org/works?search=" + urllib.parse.quote(q)
        + "&per-page=50&sort=cited_by_count:desc"
        + "&select=id,doi,title,publication_year,cited_by_count,primary_location,topics,abstract_inverted_index,open_access"
    )
    data = get_json(url) or {}
    works = []
    for w in data.get("results") or []:
        loc = w.get("primary_location") or {}
        works.append(
            {
                "id": w.get("id"),
                "doi": w.get("doi"),
                "title": w.get("title"),
                "year": w.get("publication_year"),
                "cited": w.get("cited_by_count"),
                "venue": (loc.get("source") or {}).get("display_name"),
                "topics": [t.get("display_name") for t in (w.get("topics") or [])[:3]],
                "oa_url": (w.get("open_access") or {}).get("oa_url"),
                "abstract": abstract_of(w)[:3000],
            }
        )
    return {"query": q, "count": (data.get("meta") or {}).get("count"), "works": works}


def europepmc(phrases: list[str], max_fulltext: int = 8) -> tuple[dict, list[dict]]:
    q = "(" + " OR ".join(f'"{p}"' for p in phrases) + ") AND OPEN_ACCESS:y"
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=" + urllib.parse.quote(q)
        + "&format=json&pageSize=25&resultType=lite&sort=CITED%20desc"
    )
    data = get_json(url) or {}
    papers = []
    snippets: list[dict] = []
    # 「Instron … 3400」 또는 「3400 … Instron」 이 40자 안에 같이 있는 자리만 — 「3400」 홀로는 아무거나 맞는다
    patterns = []
    for p in phrases:
        if " " not in p:
            continue
        mk, model = p.split(" ", 1)
        mk_re = re.escape(mk).replace(r"\ ", r"\s+")
        model_re = r"(?<![A-Za-z0-9])" + re.escape(model).replace(r"\ ", r"[\s-]*").replace(r"\-", r"[\s-]*") + r"(?![A-Za-z0-9])"
        patterns.append(re.compile(mk_re + r"[^.;]{0,40}?" + model_re + "|" + model_re + r"[^.;]{0,40}?" + mk_re, re.IGNORECASE))
    fetched = 0
    for r in (data.get("resultList") or {}).get("result") or []:
        entry = {
            "pmcid": r.get("pmcid"),
            "doi": r.get("doi"),
            "title": r.get("title"),
            "journal": r.get("journalTitle"),
            "year": r.get("pubYear"),
            "cited": r.get("citedByCount"),
        }
        if r.get("pmcid") and fetched < max_fulltext:
            xml = get_text(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{r['pmcid']}/fullTextXML")
            fetched += 1
            text = re.sub(r"<[^>]+>", " ", xml)
            text = re.sub(r"\s+", " ", text)
            found = 0
            seen_at: set[int] = set()
            for pat in patterns:
                for m in pat.finditer(text):
                    if found >= 4:
                        break
                    if any(abs(m.start() - a) < 300 for a in seen_at):
                        continue
                    seen_at.add(m.start())
                    window = text[max(0, m.start() - 350) : m.end() + 350].strip()
                    snippets.append(
                        {
                            "pmcid": r["pmcid"],
                            "title": r.get("title"),
                            "year": r.get("pubYear"),
                            "text": window,
                            "standards": sorted({norm(x.group(0)) for x in STANDARD_RE.finditer(window)}),
                        }
                    )
                    found += 1
            entry["snippets"] = found
            entry["standards_in_paper"] = sorted({norm(m.group(0)) for m in STANDARD_RE.finditer(text)})[:40]
        papers.append(entry)
    return {"query": q, "count": data.get("hitCount"), "papers": papers}, snippets


def wikipedia(maker: dict) -> dict | None:
    name = maker_short(maker.get("name", ""))
    data = get_json(
        "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch="
        + urllib.parse.quote(name)
    )
    hits = ((data or {}).get("query") or {}).get("search") or []
    for h in hits:
        title = h.get("title", "")
        words = [w for w in re.split(r"[\s&/-]+", name) if len(w) >= 3]
        # 제목이 제조사 이름으로 시작해야 한다 — 「Instrument Systems」 에 「Instrument landing system」 이 오면 안 된다
        if not words or not title.lower().startswith(" ".join(words).lower()[: len(words[0]) + 1].rstrip()):
            continue
        if len(words) >= 2 and not all(w.lower() in title.lower() for w in words[:2]):
            continue
        summary = get_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")))
        # 회사 글이어야 한다 — 「Bareiss algorithm」 「Lake Shore Drive」 가 아니라
        if summary and summary.get("extract") and re.search(
            r"(compan|manufactur|corporation|instrument|equipment|maker|subsidiary|brand|supplier|conglomerate|multinational|forum|organization)",
            summary["extract"], re.I,
        ):
            return {"title": title, "extract": summary["extract"], "url": (summary.get("content_urls") or {}).get("desktop", {}).get("page")}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="논문에서 장비 사용 예를 모은다")
    parser.add_argument("--only")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--fill-openalex", action="store_true", help="OpenAlex 가 비어 있는(예산 초과로 못 받은) 것만 다시")
    args = parser.parse_args()

    manufacturers = {
        m["id"]: m for m in json.loads((CATALOG / "ontology" / "manufacturers.json").read_text(encoding="utf-8"))["manufacturers"]
    }
    test_items = json.loads((CATALOG / "ontology" / "test_items.json").read_text(encoding="utf-8"))["test_items"]
    objects = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CATALOG / "equipment").rglob("*.json"))]
    if args.only:
        objects = [o for o in objects if o["manufacturer"] == args.only]
    if args.limit:
        objects = objects[: args.limit]
    PAPERS.mkdir(exist_ok=True)
    WIKI.mkdir(exist_ok=True)
    today = date.today().isoformat()
    by_name: dict[str, str] = {}

    for n, obj in enumerate(objects, 1):
        oid = obj["id"]
        out = PAPERS / f"{oid}.json"
        if args.fill_openalex:
            if not out.exists():
                continue
            prev = json.loads(out.read_text(encoding="utf-8"))
            if "openalex" not in prev or prev["openalex"].get("count") is not None:
                continue
            oa = openalex(prev["phrases"])
            if oa.get("count") is None:
                print(f"[{n}/{len(objects)}] {oid} — OpenAlex 아직 안 됨(예산). 멈춤")
                return 1
            prev["openalex"] = oa
            blob = "\n".join([w["abstract"] for w in oa["works"]] + [s_["text"] for s_ in prev.get("usage_snippets", [])])
            standards: dict[str, int] = {}
            for m in STANDARD_RE.finditer(blob):
                code = norm(m.group(0))
                standards[code] = standards.get(code, 0) + 1
            known = {norm(c) for c in known_standards(obj)}
            prev["standards_found"] = dict(sorted(standards.items(), key=lambda kv: -kv[1]))
            prev["standards_new"] = sorted(c for c in standards if c not in known)
            out.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[{n}/{len(objects)}] {oid}: OpenAlex {oa.get('count')} 채움", flush=True)
            continue
        if out.exists() and not args.redo:
            print(f"[{n}/{len(objects)}] {oid} — 있음")
            continue
        maker = manufacturers.get(obj["manufacturer"], {})
        wiki_path = WIKI / f"{obj['manufacturer']}.json"
        if maker and not wiki_path.exists():
            w = wikipedia(maker)
            wiki_path.write_text(json.dumps({"manufacturer": obj["manufacturer"], "retrieved": today, **(w or {"title": None})}, ensure_ascii=False, indent=1), encoding="utf-8")
        phrases = phrases_of(obj, maker_names(maker.get("name") or obj["manufacturer"]))
        if obj["name"] in by_name:
            out.write_text(json.dumps({"object": oid, "same_as": by_name[obj["name"]], "harvested": today}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[{n}/{len(objects)}] {oid} — {by_name[obj['name']]} 과 같은 이름")
            continue
        by_name[obj["name"]] = oid
        if not phrases:
            out.write_text(json.dumps({"object": oid, "phrases": [], "harvested": today, "note": "구절을 못 만들었다"}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[{n}/{len(objects)}] {oid} — 구절 없음")
            continue
        oa = openalex(phrases)
        epmc, snippets = europepmc(phrases)
        blob = "\n".join([w["abstract"] for w in oa["works"]] + [s["text"] for s in snippets])
        standards: dict[str, int] = {}
        for m in STANDARD_RE.finditer(blob):
            code = norm(m.group(0))
            standards[code] = standards.get(code, 0) + 1
        known = {norm(c) for c in known_standards(obj)}
        lower = blob.lower()
        hits = {}
        for item in test_items:
            needles = {n_.strip().lower() for n_ in item["label"].split("/")} | {item["label"].lower()}
            count = sum(lower.count(n_) for n_ in needles if len(n_) >= 4)
            if count:
                hits[item["id"]] = count
        out.write_text(
            json.dumps(
                {
                    "object": oid,
                    "manufacturer": obj["manufacturer"],
                    "phrases": phrases,
                    "harvested": today,
                    "openalex": oa,
                    "europepmc": epmc,
                    "usage_snippets": snippets,
                    "standards_found": dict(sorted(standards.items(), key=lambda kv: -kv[1])),
                    "standards_new": sorted(c for c in standards if c not in known),
                    "test_item_hits": dict(sorted(hits.items(), key=lambda kv: -kv[1])),
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(
            f"[{n}/{len(objects)}] {oid}: {phrases[:2]} · OpenAlex {oa.get('count')} · EPMC {epmc.get('count')} · 문장 {len(snippets)} · 규격 {len(standards)}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
