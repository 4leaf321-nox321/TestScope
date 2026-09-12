"""카탈로그 PDF 를 받아 파이프라인 자리에 넣고, 없어진 것을 `urls.json` 으로 되살린다.

    python tools_fetch_pdf.py <제조사> <파일.pdf> <url>   하나 받기 — 원본·텍스트·메타·URL 기록
    python tools_fetch_pdf.py --restore                   urls.json 에 있는데 pdf/ 에 없는 것을 전부 받기
    python tools_fetch_pdf.py --extract                   pdf/ 에 있는데 텍스트가 없는 것을 뽑기
    python tools_fetch_pdf.py --check                     세 목록이 맞는지만 본다(안 받는다)

`source/pdf/` 와 `source/extracted/` 는 git 밖이다(용량). **`catalog/urls.json` 이 정본**이라
운영 서버나 다른 PC 에서는 이 스크립트로 되살린다 — 객체의 `sources[].file` 이 가리키는
PDF 가 없으면 `build_graph.py` 가 거절하고, 사람이 값을 되짚어 볼 원문도 없다.

만드는 것
- pdf/<제조사>/<파일>                         원본
- extracted/text/<제조사>/<파일>.txt          쪽마다 `===== page N =====` 로 나눈 텍스트
- extracted/text/<제조사>/<파일>.meta.json    쪽수·바이트·sha256 (build_graph 가 sources.json 에 모은다)
- catalog/urls.json                           파일 -> 원본 URL

규칙
- 이미 있으면 다시 안 받는다. 받은 것이 PDF 가 아니면(봇 차단 HTML) 지우고 실패로 센다 —
  HTML 을 pdf 로 두면 다음 사람이 그것을 원문으로 믿는다.
- 실패해도 나머지는 계속 받고, 끝에 실패 목록을 내고 종료 코드 1. 봇을 막는 제조사는
  사람이 직접 받아 `pdf_직접/` 에 두었다가 `pdf/<제조사>/` 로 옮기고 `--extract` 한다.
- 텍스트는 `pdftotext -layout`(poppler) 로 뽑는다. 예전 것은 PyMuPDF 로 뽑아 줄 배치가
  다를 수 있지만 쪽 번호는 같다 — 객체의 `sources[].pages` 는 쪽 번호만 쓴다.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 절대경로를 적지 않는다 — 저장소 폴더 이름을 바꾸는 날 조용히 깨진다.
ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "pdf"
TEXT = ROOT / "extracted" / "text"
URLS = ROOT / "catalog" / "urls.json"


def load_urls() -> dict[str, str]:
    return dict(json.loads(URLS.read_text(encoding="utf-8")))


def save_urls(urls: dict[str, str]) -> None:
    URLS.write_text(
        json.dumps(dict(sorted(urls.items())), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


def fetch(rel: str, url: str) -> str | None:
    """받는다. 이미 있으면 아무것도 안 한다. 실패하면 이유를 돌려준다."""
    target = PDF / rel
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        ["curl", "-sSL", "-A", "Mozilla/5.0", "--max-time", "180", "-o", str(target), url],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        target.unlink(missing_ok=True)
        return f"받기 실패: {done.stderr.strip()[:160]}"
    with target.open("rb") as handle:
        head = handle.read(5)
    if head != b"%PDF-":
        target.unlink()
        return "PDF 가 아닙니다(봇 차단 HTML 등) — 직접 받아 pdf_직접/ 에 두세요"
    return None


def extract(rel: str) -> str | None:
    """텍스트와 메타를 뽑는다. 둘 다 있으면 안 한다. 실패하면 이유를 돌려준다."""
    pdf = PDF / rel
    stem = Path(rel).with_suffix("")
    txt = TEXT / stem.with_suffix(".txt")
    meta = TEXT / stem.with_suffix(".meta.json")
    if txt.exists() and meta.exists():
        return None
    if shutil.which("pdftotext") is None:
        return "pdftotext 가 없습니다 — poppler 를 설치하세요"
    txt.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, encoding="utf-8", errors="ignore"
    )
    if done.returncode != 0:
        return f"추출 실패: {done.stderr.strip()[:160]}"
    pages = done.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    body = "".join(f"===== page {n} =====\n{page}\n" for n, page in enumerate(pages, start=1))
    txt.write_text(body, encoding="utf-8")
    meta.write_text(
        json.dumps(
            {
                "file": rel,
                "pages": len(pages),
                "bytes": pdf.stat().st_size,
                "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "title": "",
                "author": "",
                "creation_date": "",
                "chars": len(body),
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return None


def check(urls: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(URL 은 있는데 PDF 없음, PDF 는 있는데 URL 없음, PDF 는 있는데 텍스트 없음)."""
    have = {str(p.relative_to(PDF)).replace("\\", "/") for p in PDF.rglob("*.pdf")}
    missing_pdf = sorted(set(urls) - have)
    missing_url = sorted(have - set(urls))
    missing_text = sorted(
        rel for rel in have if not (TEXT / Path(rel).with_suffix(".txt")).exists()
    )
    return missing_pdf, missing_url, missing_text


def main(argv: list[str]) -> int:
    urls = load_urls()
    if argv[:1] == ["--check"]:
        missing_pdf, missing_url, missing_text = check(urls)
        print(f"URL {len(urls)} · PDF 없음 {len(missing_pdf)} · URL 없음 {len(missing_url)} · 텍스트 없음 {len(missing_text)}")
        for title, rows in (("PDF 없음", missing_pdf), ("URL 없음(되살릴 수 없음)", missing_url), ("텍스트 없음", missing_text)):
            for rel in rows:
                print(f"  {title}: {rel}")
        return 0
    if argv[:1] == ["--restore"]:
        missing_pdf, _, _ = check(urls)
        failed: list[tuple[str, str]] = []
        for rel in missing_pdf:
            why = fetch(rel, urls[rel]) or extract(rel)
            if why:
                failed.append((rel, why))
            else:
                print(f"OK {rel}")
        print(f"되살림 {len(missing_pdf) - len(failed)} · 실패 {len(failed)}")
        for rel, why in failed:
            print(f"  실패 {rel}: {why}")
        return 1 if failed else 0
    if argv[:1] == ["--extract"]:
        _, _, missing_text = check(urls)
        failed = []
        for rel in missing_text:
            why = extract(rel)
            if why:
                failed.append((rel, why))
            else:
                print(f"OK {rel}")
        print(f"뽑음 {len(missing_text) - len(failed)} · 실패 {len(failed)}")
        for rel, why in failed:
            print(f"  실패 {rel}: {why}")
        return 1 if failed else 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    vendor, name, url = argv
    rel = f"{vendor}/{name}"
    why = fetch(rel, url) or extract(rel)
    if why:
        print(f"실패 {rel}: {why}")
        return 1
    urls[rel] = url
    save_urls(urls)
    meta = json.loads((TEXT / Path(rel).with_suffix(".meta.json")).read_text(encoding="utf-8"))
    print(f"OK {rel}: {meta['pages']}쪽 · {meta['bytes'] // 1024} KB · 글자 {meta['chars']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
