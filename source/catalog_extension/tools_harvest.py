"""카탈로그 보강 — 객체마다 제조사 웹 페이지(와 그 옆의 응용·규격·부속 페이지)를 모아 둔다.

    python tools_harvest.py                 전체 (있는 것은 건너뜀 — 다시 돌려도 됨)
    python tools_harvest.py --only instron  한 제조사만
    python tools_harvest.py --limit 20      앞 20 객체만 (시험 삼아)
    python tools_harvest.py --extra         extra_urls.json 의 주소(검색으로 사람이 찾은 남의 페이지)를 더 받는다

무엇을 만드나
- pages/<제조사>/<객체 id>/<n>.json   페이지 하나 — url · 받은 날 · 등급 · 종류(html/pdf) · 제목 · 본문 텍스트 · 따라간 링크
- mentions/<객체 id>.json             본문에서 뽑은 **후보** — 규격 코드 · 시험 항목 낌새 · 응용 문장 · 옆 페이지의 규격
- index.json                          객체마다 몇 쪽 · 규격 후보 몇 · 카탈로그에 없던 규격 몇
- queries.json                        어떤 토막으로 무엇을 골랐나 (되짚기용)
- sitemaps/<도메인>.json              제조사 사이트맵의 URL 전부 (캐시 — 지우면 다시 받는다)
- pdf_cache/                          받은 PDF 원본 (git 에 안 넣는다 — 글은 pages/ 에 있다)
- extra_urls.json                     (입력) 객체 id → 주소들. 검색 엔진으로 사람이 찾은 대리점·리뷰·논문 페이지.
                                      `--extra` 가 받아 pages/ 에 이어 붙이고(등급은 도메인이 정한다) mentions 를 다시 뽑는다

## 이것은 원료다, 값이 아니다

여기 모인 것은 카탈로그 객체(`catalog/equipment`)에 **들어가지 않는다.** 웹 페이지는 카탈로그 PDF 보다
등급이 낮고(제조사 페이지 2등급 · 남의 페이지 3등급 — `research/README.md` 의 등급), 자동으로
뽑은 규격·응용은 문장을 잘못 읽었을 수 있다. 사람이 검토함에서 「이 계열이 이 규격을 한다」 를
고른 뒤에야 객체로 간다. 그래서 원문 텍스트를 통째로 남긴다 — 나중에 무엇이든 다시 뽑을 수 있게.

## 어떻게 찾나 — 검색 엔진이 아니라 제조사의 사이트맵

검색 엔진(DuckDuckGo · Brave · Bing)은 스크립트로 몇 번 부르면 봇 확인 페이지를 낸다(실측: 3~5회).
대신 제조사 사이트의 `sitemap.xml`(robots.txt 가 가리키는 것)을 한 번 받아 URL 전부를 두고, 객체
이름·기종명의 토막(「6800」 「3119-160」 「platinous」)이 URL 에 들어간 페이지를 고른다. 제조사
페이지만 오므로 전부 2등급이다. 객체가 이미 아는 `sources[].url` 이 있으면 그것이 먼저다.
제조사 「문헌」 페이지는 주소가 .pdf 로 안 끝나도 PDF 를 주는 일이 많다 — 받은 바이트의 앞머리로
가려 pdftotext(poppler) 로 글을 뽑는다. 주소가 .pdf 로 끝나는 것은 받지 않고 `pdf_candidates` 로만
적는다 — 그것은 `catalog/tools_fetch_pdf.py` 의 일이다. `--search` 를 주면 검색 엔진도 시도한다
(막히면 조용히 빈 결과).

페이지에서 같은 도메인의 링크 중 **이 객체의 것**(그 페이지 아래이거나 객체 토막이 든 것)을 먼저,
application·standard·accessor·option·specification·datasheet 가 든 공통 페이지는 둘까지, 합쳐 최대
4개 더 따라간다(한 층만). 같은 글의 다른 언어판·그림은 안 따라간다. 요청 사이 1.5초 — 제조사
서버를 두드리지 않는다. 403·429 는 8초 쉬고 한 번 더.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG = ROOT / "catalog"
PAGES = HERE / "pages"
MENTIONS = HERE / "mentions"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
PAUSE = 1.5
FOLLOW_WORDS = ("application", "standard", "accessor", "option", "specification", "datasheet", "brochure", "fixture", "grip")
STANDARD_RE = re.compile(
    r"\b(ASTM|ISO|IEC|EN|DIN|JIS|KS|BS|GB/T|GB|SAE|UL|CSA|IPC|JEDEC|JESD|MIL-STD|MIL-DTL|ISTA|VDA|GM|GMW|AASHTO|TAPPI|ANSI|AATCC|USP|IEEE|ETSI|RTCA|NF|GOST|UNI|SS|EIA|ECCA)"
    r"[ -]?(?:[A-Z]{1,4}[ -]?)?\d{2,6}(?:[-–.]\d{1,4}){0,3}(?:[A-Z]{1,2})?\b"
)
APPLY_RE = re.compile(
    r"([^.]{0,160}\b(?:used for|ideal for|designed for|suitable for|applications? (?:include|range)|typical(?:ly)? used|for testing|to test|tests? (?:of|for))\b[^.]{0,200}\.)",
    re.IGNORECASE,
)


class _Text(HTMLParser):
    """스크립트·스타일을 빼고 글만. 제목·링크는 따로."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.title = ""
        self._skip = 0
        self._in_title = False
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._link_text = []
        elif tag in ("p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "td", "th", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag == "a":
            if self._href:
                self.links.append((self._href, " ".join(self._link_text).strip()))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._href is not None:
            self._link_text.append(data.strip())
        self.parts.append(data)


_CACHE: dict[str, tuple[int, bytes]] = {}


def fetch_bytes(url: str, _retry: bool = False) -> tuple[int, bytes]:
    if url in _CACHE:
        return _CACHE[url]
    done = subprocess.run(
        ["curl", "-sSL", "--compressed", "-A", UA, "--max-time", "60", "-w", "\n%{http_code}", url],
        capture_output=True,
    )
    body, _, code = done.stdout.rpartition(b"\n")
    try:
        result = (int(code.strip() or 0), body)
    except ValueError:
        result = (0, body)
    if result[0] in (403, 429, 500, 502, 503) and not _retry:
        time.sleep(8)
        return fetch_bytes(url, _retry=True)
    if len(_CACHE) < 400:
        _CACHE[url] = result
    return result


def fetch(url: str) -> tuple[int, str]:
    code, body = fetch_bytes(url)
    return code, body.decode("utf-8", errors="replace")


PDF_CACHE = HERE / "pdf_cache"  # 받은 PDF 원본 — git 에는 안 넣는다(.gitignore)


def pdf_text(body: bytes, keep_as: Path | None) -> str:
    """PDF 바이트에서 글. pdftotext(poppler) 가 없으면 빈 글 — 그때는 pdf_candidates 로만 남는다."""
    if shutil.which("pdftotext") is None:
        return ""
    if keep_as is not None:
        keep_as.parent.mkdir(parents=True, exist_ok=True)
        keep_as.write_bytes(body)
        src = keep_as
    else:
        src = HERE / "_tmp.pdf"
        src.write_bytes(body)
    done = subprocess.run(["pdftotext", "-layout", str(src), "-"], capture_output=True)
    if keep_as is None:
        src.unlink(missing_ok=True)
    if done.returncode != 0:
        return ""
    text = done.stdout.decode("utf-8", errors="ignore").replace("\r", "").replace("\f", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text


def page_content(body: bytes, keep_pdf_as: Path | None = None) -> tuple[str, str, str, list[tuple[str, str]]]:
    """(종류, 제목, 글, 링크). 제조사 「문헌」 페이지는 주소가 .pdf 로 안 끝나도 PDF 를 준다 — 앞머리로 가른다."""
    if body[:5] == b"%PDF-":
        return "pdf", "", pdf_text(body, keep_pdf_as), []
    title, text, links = to_text(body.decode("utf-8", errors="replace"))
    return "html", title, text, links


def to_text(page: str) -> tuple[str, str, list[tuple[str, str]]]:
    parser = _Text()
    try:
        parser.feed(page)
    except Exception:  # noqa: BLE001 — 깨진 HTML 도 있는 만큼은 쓴다
        pass
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return parser.title.strip(), text, parser.links


def search(query: str) -> list[str]:
    """검색 결과의 URL 들 (순서대로). Brave 가 먼저 — DuckDuckGo HTML 은 몇 번 만에 봇 확인 페이지
    (202)를 내서 뒤로 뒀다. 검색 엔진 자체는 출처가 아니다: 어디서 찾았든 페이지의 등급은 도메인이 정한다."""
    code, body = fetch(
        "https://search.brave.com/search?source=web&q=" + urllib.parse.quote(query)
    )
    out: list[str] = []
    if code == 200:
        for match in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*l1[^"]*"', body):
            url = html.unescape(match.group(1))
            if "brave.com" in domain(url) or url in out:
                continue
            out.append(url)
    if out:
        return out
    code, body = fetch("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query))
    if code != 200:
        return []
    for match in re.finditer(r"uddg=([^&\"]+)", body):
        url = urllib.parse.unquote(match.group(1))
        if url not in out:
            out.append(url)
    return out


def domain(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


SITEMAPS = HERE / "sitemaps"
LOC_RE = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\s\]]+)\s*(?:\]\]>)?\s*</loc>")


def sitemap_urls(website: str) -> list[str]:
    """제조사 사이트의 URL 전부(캐시). robots.txt → sitemap(index) → 하위 sitemap. 2만 개까지."""
    SITEMAPS.mkdir(exist_ok=True)
    key = domain(website) or "unknown"
    cache = SITEMAPS / f"{key}.json"
    if cache.exists():
        return list(json.loads(cache.read_text(encoding="utf-8"))["urls"])
    base = website.rstrip("/")
    candidates: list[str] = []
    code, robots = fetch(base + "/robots.txt")
    time.sleep(PAUSE)
    if code == 200:
        candidates += re.findall(r"(?im)^sitemap:\s*(\S+)", robots)
    candidates += [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/sitemap-index.xml"]
    urls: list[str] = []
    seen: set[str] = set()
    queue = list(dict.fromkeys(candidates))
    fetched = 0
    while queue and fetched < 40 and len(urls) < 20_000:
        target = queue.pop(0)
        if target in seen:
            continue
        seen.add(target)
        code, body = fetch(target)
        time.sleep(PAUSE)
        fetched += 1
        if code != 200 or "<loc>" not in body:
            continue
        for loc in LOC_RE.findall(body):
            loc = html.unescape(loc.strip())
            if loc.lower().endswith((".xml", ".xml.gz")) or "sitemap" in loc.lower().rsplit("/", 1)[-1]:
                queue.append(loc)
            else:
                urls.append(loc)
    cache.write_text(
        json.dumps({"website": website, "retrieved": date.today().isoformat(), "urls": urls}, ensure_ascii=False),
        encoding="utf-8",
    )
    return urls


STOP = {"series", "system", "systems", "model", "models", "the", "and", "for", "with", "type", "tester",
        "testers", "testing", "machine", "machines", "universal", "electrodynamic", "environmental", "chambers",
        "chamber", "instrument", "instruments", "analyzer", "analyser"}


def tokens_of(obj: dict, maker_name: str = "") -> list[str]:
    """이름·기종명에서 URL 에 나올 법한 토막. 숫자가 든 것(모델 번호)이 먼저다. 제조사 이름과
    「series」 「testing」 같은 흔한 말은 뺀다 — 그것으로 맞추면 제조사 사이트 전부가 걸린다."""
    words: list[str] = []
    maker_words = {w.lower() for w in re.split(r"[\s/(),·:&-]+", maker_name) if w}
    for text in [obj.get("name") or ""] + [m.get("model") or "" for m in obj.get("models") or []]:
        for w in re.split(r"[\s/(),·:]+", text):
            w = w.strip("-–").lower()
            if len(w) >= 3 and w not in STOP and w not in maker_words:
                words.append(w)
    digits = [w for w in words if any(ch.isdigit() for ch in w)]
    plain = [w for w in words if not any(ch.isdigit() for ch in w) and len(w) >= 5]
    out: list[str] = []
    for w in digits + plain:
        if w not in out:
            out.append(w)
    return out[:12]


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def strip_locale(path: str) -> str:
    return re.sub(r"^/[a-z]{2}(?:-[a-z]{2,5})?/", "/", path.lower()).rstrip("/")


def locale_of(path: str) -> str:
    m = re.match(r"^/([a-z]{2})(?:-[a-z]{2,5})?/", path.lower())
    return m.group(1) if m else ""


def pick_from_sitemap(urls: list[str], obj: dict, maker_name: str = "") -> tuple[list[str], list[str]]:
    """토막이 들어간 URL 을 점수로 고른다 — (페이지들, PDF 후보들). 모델 번호 토막이 하나는 맞아야
    한다(점수 3 이상) — 「1200」 같은 짧은 숫자 하나로는 안 고른다."""
    toks = tokens_of(obj, maker_name)
    if not toks:
        return [], []
    scored: list[tuple[int, int, int, str]] = []
    for url in urls:
        path = urllib.parse.urlparse(url).path.lower()
        score = 0
        for i, tok in enumerate(toks):
            t = tok.lower()
            if len(squash(t)) < 3:
                continue
            # 경계를 본다 — 「1200」 이 「cp120055」 나 「12009」 안에서 걸리면 안 된다.
            parts = [p for p in re.split(r"[-_]", t) if p]
            pattern = r"(?<![a-z0-9])" + r"[-_]?".join(re.escape(p) for p in parts) + r"(?![a-z0-9])"
            if re.search(pattern, path):
                # 모델 번호(앞쪽·숫자 있음)가 무겁고, 짧은 숫자 토막(「300」)은 가볍다
                score += (3 if any(ch.isdigit() for ch in t) and len(squash(t)) >= 4 else 1) + (1 if i == 0 else 0)
        if score < 3:
            continue
        # 제품 페이지가 문헌 목록·뉴스·영상보다 먼저
        if "/product" in path:
            score += 2
        if any(w in path for w in ("/news", "/video", "/press", "/event", "/webinar", "/blog", "/career", "/job")):
            score -= 2
        # 영어(또는 언어 없는) 경로를 앞에 — 같은 글의 de/ja/zh-hans 판을 자리 다 차지하지 않게
        locale = re.match(r"^/([a-z]{2})(?:-[a-z]{2,5})?/", path)
        foreign = 1 if locale and locale.group(1) not in ("en",) else 0
        scored.append((-score, foreign, len(path), url))
    scored.sort()
    seen_slug: set[str] = set()
    pages: list[str] = []
    pdfs: list[str] = []
    for _, _, _, url in scored:
        slug = strip_locale(urllib.parse.urlparse(url).path)
        if slug in seen_slug:
            continue
        seen_slug.add(slug)
        if url.lower().endswith(".pdf"):
            if len(pdfs) < 8:
                pdfs.append(url)
        elif len(pages) < 6:
            pages.append(url)
    return pages, pdfs


def load_objects() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CATALOG / "equipment").rglob("*.json"))]


def known_standards(obj: dict) -> set[str]:
    standards = obj.get("standards") or {}
    codes = set()
    for key in ("compliance", "test_methods"):
        codes |= {str(c) for c in standards.get(key) or []}
    for lst in (standards.get("test_methods_by_item") or {}).values():
        codes |= {str(c) for c in lst}
    return codes


def norm(code: str) -> str:
    return re.sub(r"\s+", " ", code.replace("–", "-")).strip().upper()


def extract(texts: list[str], test_items: list[dict], obj: dict) -> dict:
    joined = "\n".join(texts)
    standards: dict[str, int] = {}
    for m in STANDARD_RE.finditer(joined):
        code = norm(m.group(0))
        standards[code] = standards.get(code, 0) + 1
    known = {norm(c) for c in known_standards(obj)}
    item_hits: dict[str, int] = {}
    lower = joined.lower()
    for item in test_items:
        needles = {item["label"].lower()} | {part.strip().lower() for part in item["label"].split("/")}
        needles = {n for n in needles if len(n) >= 4}
        count = sum(lower.count(n) for n in needles)
        if count:
            item_hits[item["id"]] = count
    applications = []
    seen = set()
    for m in APPLY_RE.finditer(joined):
        sentence = re.sub(r"\s+", " ", m.group(1)).strip()
        if 40 <= len(sentence) <= 400 and sentence not in seen:
            seen.add(sentence)
            applications.append(sentence)
        if len(applications) >= 25:
            break
    return {
        "standards_found": dict(sorted(standards.items(), key=lambda kv: -kv[1])),
        "standards_new": sorted(c for c in standards if c not in known),
        "test_item_hits": dict(sorted(item_hits.items(), key=lambda kv: -kv[1])),
        "application_sentences": applications,
    }


def harvest_pages(
    obj: dict,
    picks: list[tuple[str, int]],
    folder: Path,
    saved_before: int,
    texts_before: list[str],
    test_items: list[dict],
    today: str,
    index: dict,
    maker: dict,
    pdf_candidates: list[str],
) -> None:
    """주소들을 받아 folder 에 이어 붙이고(번호는 saved_before 다음부터) mentions·index 를 다시 쓴다."""
    oid = obj["id"]
    vendor = obj["manufacturer"]
    folder.mkdir(parents=True, exist_ok=True)
    texts: list[str] = list(texts_before)
    nearby_texts: list[str] = []
    followed_urls: set[str] = {u for u, _ in picks}
    saved = saved_before
    for url, grade in picks:
        code, raw = fetch_bytes(url)
        time.sleep(PAUSE)
        kind, title, text, links = (
            page_content(raw, PDF_CACHE / vendor / oid / f"{saved + 1}.pdf") if code == 200 else ("html", "", "", [])
        )
        followed: list[dict] = []
        if code == 200 and grade == 2 and kind == "html":
            extra = 0
            base_path = urllib.parse.urlparse(url).path.rstrip("/") + "/"
            toks = [t.lower() for t in tokens_of(obj, maker.get("name", ""))]
            for href, label in links:
                if extra >= 4:
                    break
                full = urllib.parse.urljoin(url, href).split("#", 1)[0]
                if domain(full) != domain(url) or full == url or full.lower().endswith(".pdf"):
                    continue
                if full in followed_urls:
                    continue
                path = urllib.parse.urlparse(full).path.lower()
                if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".mp4")):
                    continue
                loc = locale_of(path)
                if strip_locale(path) == strip_locale(base_path) or (loc and loc != "en" and loc != locale_of(base_path)):
                    continue  # 같은 글의 de/es/zh 판
                own = path.startswith(base_path) or any(len(t) >= 4 and t in path for t in toks)
                blob = (href + " " + label).lower()
                if not own and not any(w in blob for w in FOLLOW_WORDS):
                    continue
                if not own and extra >= 2:
                    continue  # 공통 메뉴(응용·규격 목록)는 둘까지만
                followed_urls.add(full)
                code2, raw2 = fetch_bytes(full)
                time.sleep(PAUSE)
                if code2 != 200:
                    continue
                kind2, title2, text2, _ = page_content(raw2)
                if len(text2) < 300:
                    continue
                followed.append(
                    {
                        "url": full,
                        "kind": kind2,
                        "title": title2,
                        "text": text2[:40_000],
                        "standards_in_page": sorted({norm(m.group(0)) for m in STANDARD_RE.finditer(text2)}),
                    }
                )
                nearby_texts.append(text2[:40_000])
                extra += 1
        saved += 1
        (folder / f"{saved}.json").write_text(
            json.dumps(
                {
                    "object": oid,
                    "url": url,
                    "retrieved": today,
                    "grade": grade,
                    "status": code,
                    "kind": kind,
                    "title": title,
                    "text": text[:80_000],
                    "standards_in_page": sorted({norm(m.group(0)) for m in STANDARD_RE.finditer(text)}),
                    "followed": followed,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        if text:
            texts.append(text[:80_000])
    mentions = extract(texts, test_items, obj) if texts else {}
    previous = json.loads((MENTIONS / f"{oid}.json").read_text(encoding="utf-8")) if saved_before and (MENTIONS / f"{oid}.json").exists() else {}
    nearby = set(previous.get("standards_nearby") or [])
    if nearby_texts:
        # 따라간 페이지(문헌 목록·응용 페이지)의 규격은 **이 객체의 것이 아닐 수 있다** — 따로 둔다.
        nearby |= {norm(m.group(0)) for t in nearby_texts for m in STANDARD_RE.finditer(t)}
    if nearby:
        mentions["standards_nearby"] = sorted(nearby - set(mentions.get("standards_found", {})))
    (MENTIONS / f"{oid}.json").write_text(
        json.dumps({"object": oid, "manufacturer": vendor, "pages": saved, "harvested": today, **mentions}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    index[oid] = {
        "manufacturer": vendor,
        "pages": saved,
        "chars": sum(len(t) for t in texts) + sum(len(t) for t in nearby_texts),
        "standards_found": len(mentions.get("standards_found", {})),
        "standards_new": len(mentions.get("standards_new", [])),
        "pdf_candidates": len(pdf_candidates) or (index.get(oid) or {}).get("pdf_candidates", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="제조사 웹 페이지를 모아 카탈로그 보강 원료로 둔다")
    parser.add_argument("--only", help="제조사 id 하나만")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--redo", action="store_true", help="있는 것도 다시 받는다")
    parser.add_argument("--search", action="store_true", help="검색 엔진도 시도한다(막히기 쉽다)")
    parser.add_argument("--extra", action="store_true", help="extra_urls.json 의 주소를 더 받는다")
    args = parser.parse_args()

    manufacturers = {
        m["id"]: m for m in json.loads((CATALOG / "ontology" / "manufacturers.json").read_text(encoding="utf-8"))["manufacturers"]
    }
    test_items = json.loads((CATALOG / "ontology" / "test_items.json").read_text(encoding="utf-8"))["test_items"]
    urls_known = set(json.loads((CATALOG / "urls.json").read_text(encoding="utf-8")).values())
    objects = load_objects()
    if args.only:
        objects = [o for o in objects if o["manufacturer"] == args.only]
    if args.limit:
        objects = objects[: args.limit]

    PAGES.mkdir(exist_ok=True)
    MENTIONS.mkdir(exist_ok=True)
    queries_path = HERE / "queries.json"
    queries = json.loads(queries_path.read_text(encoding="utf-8")) if queries_path.exists() else {}
    index_path = HERE / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    today = date.today().isoformat()

    extra_path = HERE / "extra_urls.json"
    extra = json.loads(extra_path.read_text(encoding="utf-8")) if args.extra and extra_path.exists() else {}
    if args.extra:
        objects = [o for o in objects if extra.get(o["id"])]

    for n, obj in enumerate(objects, 1):
        oid = obj["id"]
        vendor = obj["manufacturer"]
        folder = PAGES / vendor / oid
        maker = manufacturers.get(vendor, {})
        site = domain(maker.get("website") or "")
        existing = sorted(folder.glob("*.json"), key=lambda p: int(p.stem)) if folder.exists() else []
        if args.extra:
            have = {json.loads(p.read_text(encoding="utf-8"))["url"] for p in existing}
            picks = [(u, 2 if site and domain(u) == site else 3) for u in extra[oid] if u not in have]
            if not picks:
                print(f"[{n}/{len(objects)}] {oid} — 더 받을 주소 없음")
                continue
            texts_before = [json.loads(p.read_text(encoding="utf-8")).get("text") or "" for p in existing]
            harvest_pages(obj, picks, folder, len(existing), texts_before, test_items, today, index, maker, [])
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[{n}/{len(objects)}] {oid}: 더 받음 {len(picks)} · 쪽 {index[oid]['pages']} · 규격 {index[oid]['standards_found']}")
            continue
        if existing and not args.redo:
            print(f"[{n}/{len(objects)}] {oid} — 있음, 건너뜀")
            continue
        name = re.sub(r"\(.*?\)", "", obj["name"]).strip()
        short = " ".join(name.split()[:6])
        picks: list[tuple[str, int]] = []
        pdf_candidates: list[str] = []
        # 1) 객체가 이미 아는 제조사 페이지(연구 때 넣은 url 출처)
        for src in obj.get("sources") or []:
            url = src.get("url")
            if url and not url.lower().endswith(".pdf") and url not in [p for p, _ in picks]:
                picks.append((url, 2 if site and domain(url) == site else 3))
        # 2) 제조사 사이트맵에서 이름 토막으로
        site_urls = sitemap_urls(maker["website"]) if maker.get("website") else []
        pages, pdfs = pick_from_sitemap(site_urls, obj, maker.get("name", ""))
        for url in pages:
            if url not in [p for p, _ in picks]:
                picks.append((url, 2))
        pdf_candidates = [u for u in pdfs if u not in urls_known]
        # 3) (선택) 검색 엔진
        q_vendor = f"{maker.get('name', vendor)} {short}" + (f" site:{site}" if site else "")
        if args.search and len(picks) < 3:
            for url in search(q_vendor)[:6]:
                time.sleep(PAUSE)
                if url.lower().endswith(".pdf"):
                    if url not in urls_known and url not in pdf_candidates:
                        pdf_candidates.append(url)
                    continue
                if url not in [p for p, _ in picks]:
                    picks.append((url, 2 if site and domain(url) == site else 3))
        picks = picks[:6]
        queries[oid] = {
            "tokens": tokens_of(obj, maker.get("name", "")),
            "sitemap_urls": len(site_urls),
            "vendor_query": q_vendor if args.search else None,
            "picked": [u for u, _ in picks],
            "pdf_candidates": pdf_candidates,
            "on": today,
        }

        harvest_pages(obj, picks, folder, 0, [], test_items, today, index, maker, pdf_candidates)
        queries_path.write_text(json.dumps(queries, ensure_ascii=False, indent=1), encoding="utf-8")
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print(
            f"[{n}/{len(objects)}] {oid}: 쪽 {saved} · 글자 {index[oid]['chars']:,} · 규격 {index[oid]['standards_found']}"
            f"(새 {index[oid]['standards_new']}) · PDF 후보 {len(pdf_candidates)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
