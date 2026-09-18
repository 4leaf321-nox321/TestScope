"""검토함 「시험 항목의 별칭」 의 초안 — `proposals/test_item_aliases.json` 을 만든다.

    python scripts/draft_test_item_aliases.py            # 정본을 다시 쓴다(결정은 보존)
    python scripts/draft_test_item_aliases.py --show     # 쓰지 않고 후보만 보여 준다

별칭은 AI 가 시험 항목을 찾아가는 첫 관문이다 — resolve 의 「별칭 일치」 가 「뜻이 가까움」
보다 먼저 오고, 검토함의 「규격 제목의 영문 이름」 추천도 별칭이 있어야 걸린다. 그런데 별칭을
사람이 빈 칸에 적으라고 하면 아무도 안 적는다. 그래서 **기계가 후보를 세우고 사람이 고른다.**

후보가 오는 길 셋 — 근거가 다르고 신뢰도가 다르다:

    1. 영문 라벨의 조각    「Abrasion / wear」 → Abrasion · wear.  「DMA (동적기계)」 → DMA ·
                            동적기계. 라벨 자체가 정본이라 **추천**.
    2. 한글 이름의 조각    「계장화 압입(나노인덴테이션)」 → 계장화 압입 · 나노인덴테이션.
                            바깥은 **추천**, 괄호 안(방법·측정량 목록)은 후보만.
    3. 규격 제목의 구절    이 시험으로 정해진 규격들의 제목에서 「Determination of tensile
                            properties」 → tensile.  둘 이상의 규격에 나오면 추천, 하나면 후보.

이미 값이거나 별칭인 것, 다른 시험 항목의 이름·별칭인 것은 세우지 않는다 — 그건 검토함이 아니라
resolve 가 답할 일이다. 정본에 이미 `decided` 가 있는 줄은 그대로 둔다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.config import REPO_DIR
from app.database import SessionLocal
from app.modules.methods.models import TestMethod
from app.modules.review.services import PROPOSALS_DIR
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.shared.text import clean, compare_key

survive_cp949()

ONTOLOGY = REPO_DIR / "source" / "catalog" / "ontology" / "test_items.json"

#: 규격 제목에서 구절을 뽑는 틀. 「Determination of X」 「Test method for X」 「X test」.
_TITLE_PATTERNS = [
    re.compile(
        r"determination of (?:the )?([a-z][a-z0-9 \-']{2,40}?)"
        r"(?=\s*[-:(,.]| of | for | at | by | in | on | using | under | with |$)"
    ),
    re.compile(
        r"test methods? for (?:the )?(?:determination of )?([a-z][a-z0-9 \-']{2,40}?)"
        r"(?=\s*[-:(,.]| of | for | at | by | in | on | using | under | with |$)"
    ),
    re.compile(
        r"(?<![a-z])([a-z][a-z0-9\-']+(?: [a-z][a-z0-9\-']+){0,2}) (?:test|testing|tests)\b"
    ),
]
#: 구절 끝의 군더더기 — 「tensile properties」 는 「tensile」 로.
_TAIL = re.compile(
    r"\s+(?:properties|property|strength|resistance|behaviou?r|characteristics|"
    r"performance|measurement|measurements|evaluation|analysis)$"
)
#: 구절을 이루는 낱말이 전부 이것들이면 시험 이름이 아니다 — 「resistance」 「measurement」.
_GENERIC = {
    "standard",
    "test",
    "tests",
    "testing",
    "method",
    "methods",
    "of",
    "for",
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "by",
    "in",
    "on",
    "at",
    "with",
    "resistance",
    "measurement",
    "measurements",
    "performance",
    "environmental",
    "determination",
    "determining",
    "measuring",
    "rating",
    "conducting",
    "evaluating",
    "evaluation",
    "properties",
    "property",
    "general",
    "specimen",
    "specimens",
    "materials",
    "material",
    "procedure",
    "procedures",
    "practice",
    "guide",
    "part",
    "requirements",
    "plastics",
    "metallic",
    "metals",
    "rubber",
    "vulcanized",
    "principles",
    "verification",
    "calibration",
    "using",
    "under",
    "sample",
    "samples",
    "products",
    "product",
    "conditions",
    "characteristics",
    "behaviour",
    "behavior",
}
#: 구절 앞의 동사·군더더기 — 「determining the charpy impact」 는 「charpy impact」.
_LEAD = re.compile(
    r"^(?:(?:determining|measuring|conducting|rating|evaluating|testing|methods? of|"
    r"method for|the|a|an|and|for|of)\s+)+"
)


def _split_label(label: str) -> tuple[list[str], list[str]]:
    """(바깥 조각, 괄호 안 조각). 「Dynamic mechanical analysis (DMA)」 → (["Dynamic
    mechanical analysis"], ["DMA"]). 「Abrasion / wear」 → (["Abrasion", "wear"], [])."""
    inner_raw = re.findall(r"\(([^()]+)\)", label)
    outer_raw = re.sub(r"\s*\([^()]*\)", "", label)

    def pieces(text: str) -> list[str]:
        return [
            # 「charge/discharge」 는 한 낱말 — 띄어 쓴 빗금만 가른다.
            one.strip()
            for one in re.split(r"\s+/\s+|\s*·\s*", text)
            if len(one.strip()) >= 2
        ]

    outer = pieces(outer_raw)
    inner = [piece for raw in inner_raw for piece in pieces(raw)]
    return list(dict.fromkeys(outer)), list(dict.fromkeys(inner))


def _title_phrases(title: str) -> list[str]:
    low = title.lower()
    found: list[str] = []
    for pattern in _TITLE_PATTERNS:
        for m in pattern.finditer(low):
            phrase = re.sub(r"\s+", " ", m.group(1).strip(" -',"))
            phrase = _LEAD.sub("", _TAIL.sub("", phrase)).strip(" -',")
            words = phrase.split()
            if len(phrase) < 5 or not words or all(w in _GENERIC for w in words):
                continue
            found.append(phrase)
    return list(dict.fromkeys(found))


class _Bucket:
    """시험 항목 하나의 후보 통. 같은 비교키는 한 번만, 이미 쓰인 표기는 안 받는다."""

    def __init__(self, taken: dict[str, str]) -> None:
        self.taken = taken
        self.seen: set[str] = set()
        self.candidates: list[dict[str, Any]] = []
        self.recommended: list[str] = []

    def keep(self, text: str, reason: str, *, recommend: bool) -> None:
        text = clean(text)
        key = compare_key(text)
        if not key or key in self.seen or key in self.taken:
            return
        self.seen.add(key)
        self.candidates.append({"code": text, "reason": reason})
        if recommend:
            self.recommended.append(text)


def draft(show: bool) -> int:
    db = SessionLocal()
    try:
        axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
        assert axis is not None
        terms = {
            t.code: t
            for t in db.scalars(
                select(VocabularyTerm).where(
                    VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.status == "active"
                )
            )
            if t.code
        }
        # 이 축에서 이미 쓰인 비교키 전부 — 값·별칭 어느 쪽이든. 후보에서 뺀다.
        taken: dict[str, str] = {t.normalized: t.value for t in terms.values()}
        for alias in db.scalars(
            select(VocabularyAlias).where(VocabularyAlias.vocabulary_id == axis.id)
        ):
            taken.setdefault(alias.normalized, alias.value)
        methods_of: dict[str, list[TestMethod]] = defaultdict(list)
        by_id = {t.id: code for code, t in terms.items()}
        for method in db.scalars(
            select(TestMethod).where(
                TestMethod.deleted_at.is_(None), TestMethod.test_item_term_id.is_not(None)
            )
        ):
            code = by_id.get(method.test_item_term_id)  # type: ignore[arg-type]
            if code and method.title != method.code:
                methods_of[code].append(method)
    finally:
        db.close()

    ontology = {
        row["id"]: row
        for row in json.loads(ONTOLOGY.read_text(encoding="utf-8"))["test_items"]
    }
    path = PROPOSALS_DIR / "test_item_aliases.json"
    previous: dict[str, dict[str, Any]] = {}
    if path.exists():
        previous = {
            str(row["subject"]): row
            for row in json.loads(path.read_text(encoding="utf-8")).get("rows") or []
        }

    rows: list[dict[str, Any]] = []
    total = 0
    for code, term in sorted(terms.items()):
        bucket = _Bucket(taken)
        keep = bucket.keep
        candidates, recommended = bucket.candidates, bucket.recommended

        entry = ontology.get(code) or {}
        label = str(entry.get("label") or "")
        outer, inner = _split_label(label)
        for piece in [*outer, *inner]:
            keep(piece, f"영문 라벨 「{label}」 의 조각", recommend=True)
        outer, inner = _split_label(term.value)
        for piece in outer:
            keep(piece, f"이름 「{term.value}」 의 조각", recommend=True)
        for piece in inner:
            # 괄호 안은 방법·측정량 목록(XPS·FT-IR·라만)인 일이 많다 — 찾는 데는 쓸모 있지만
            # 시험 이름은 아니라서 추천은 안 붙인다. 사람이 고른다.
            keep(piece, f"이름 「{term.value}」 의 괄호 안", recommend=False)

        counts: Counter[str] = Counter()
        example: dict[str, str] = {}
        for method in methods_of.get(code, []):
            for phrase in _title_phrases(method.title):
                counts[phrase] += 1
                example.setdefault(phrase, method.code)
        for phrase, n in counts.most_common(8):
            keep(
                phrase,
                f"이 시험의 규격 {n}건 제목에 나옴 — 예: {example[phrase]}",
                recommend=n >= 2,
            )

        if not candidates:
            continue
        total += len(candidates)
        row: dict[str, Any] = {
            "subject": code,
            "candidates": candidates,
            "recommended": recommended,
        }
        if previous.get(code, {}).get("decided"):
            row["decided"] = previous[code]["decided"]
        rows.append(row)
        if show:
            print(f"\n{term.value} ({code})")
            for one in candidates:
                mark = "●" if one["code"] in recommended else "○"
                print(f"  {mark} {one['code']} — {one['reason']}")

    if show:
        print(f"\n시험 항목 {len(rows)}종 · 후보 {total}")
        return 0
    path.write_text(
        json.dumps(
            {
                "queue": "test_item_aliases",
                "generated": date.today().isoformat(),
                "note": "scripts/draft_test_item_aliases.py 가 만든다 — 손으로 안 고친다. "
                "결정(decided)은 보존된다.",
                "rows": rows,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{path}: 시험 항목 {len(rows)}종 · 후보 {total}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="시험 항목 별칭 후보의 초안")
    parser.add_argument("--show", action="store_true", help="쓰지 않고 보여만 준다")
    args = parser.parse_args()
    return draft(args.show)


if __name__ == "__main__":
    raise SystemExit(main())
