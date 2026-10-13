"""사람이 적은 짧은 문자열을 다루는 규칙 — **한 곳에서.**

온톨로지(축·값·별칭)와 장비 자산번호가 같은 문제를 갖는다: 눈에 같아 보이는데
DB 는 다르게 보는 값들이다. `포스코` 와 `포스코 `(뒤 공백), `UTM-01` 과
`utm-01`. 비교키를 만드는 규칙이 모듈마다 다르면 어떤 화면은 중복을 막고 어떤
화면은 못 막는다.
"""

from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\s+")


def clean(raw: str) -> str:
    """보여 줄 값. 앞뒤 공백과 연속 공백만 정리하고 표기는 그대로 둔다."""
    return _SPACES.sub(" ", raw.strip())


def compare_key(raw: str) -> str:
    """유일성·조회에 쓰는 비교키.

    **구두점은 안 지운다.** `포스코(주)` 가 계열사 구분일 수 있다 — 그런 것을
    묶는 것은 병합 후보 탐지의 몫이고, 거기서는 **사람에게 묻는다.**

    NFKC 로 모으는 이유: 전각 `ＡＳＴＭ` 과 반각 `ASTM` 이 다른 값으로 들어오면,
    목록에 둘이 나란히 서고 아무도 그 둘이 같다는 것을 모른다.
    """
    return unicodedata.normalize("NFKC", clean(raw)).casefold()


#: 규격 번호 끝의 **판 표시** — 「:2019」 「:2019/A1:2021」 「(2019)」. 부(part) 번호
#: 「-1」 「-2-14」 는 다른 규격이라 건드리지 않는다.
_EDITION_TAIL = re.compile(
    r"\s*(?::\s*(?:19|20)\d{2}(?:\s*[+/]\s*A\d+(?::\s*(?:19|20)\d{2})?)*"
    r"|\(\s*(?:19|20)\d{2}\s*\))\s*$"
)
#: ASTM 은 판을 붙여 쓴다 — 「D638-14」 「E8/E8M-16a」 「D1238-13e1」. ASTM 에는 부 번호가
#: 없다.
_ASTM_YEAR = re.compile(r"^(ASTM\s.*?)-\d{2}[a-z]?(?:\s*e\d+)?$", re.IGNORECASE)


def method_base(code: str) -> str:
    """판 표시를 뗀 규격 번호 — 「ASTM D638-14」 → 「ASTM D638」, 「ISO 527-2:2012」 →
    「ISO 527-2」. 표기만 다른 규격(판만 붙은 것)을 정식 규격으로 묶을 때 쓴다."""
    stripped = _EDITION_TAIL.sub("", clean(code))
    astm = _ASTM_YEAR.match(stripped)
    return astm.group(1) if astm else stripped


def method_key(code: str) -> str:
    """규격 번호의 비교키. **공백을 지운다** — 「JIS B 0601」 과 「JIS B0601」 은 같은 규격인데
    출처마다 표기가 갈린다(MaterialTwin 은 붙여 쓰고 카탈로그는 띄어 쓴다). 두 행이 되면
    「이 규격 되는 장비」 가 절반만 답한다. 반입(카탈로그·요구 조건 표)이 같이 쓴다."""
    return _SPACES.sub("", compare_key(code))
