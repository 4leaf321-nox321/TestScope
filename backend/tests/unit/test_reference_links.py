"""사양 정의 -> 검색축 연결은 **한 표**(`SPEC_DEFINITION_LINKS`)가 정한다.

정의 표 셋(온톨로지 · 카탈로그 손 정의 · 카탈로그 원본 온톨로지 승격)이 저마다 축을
적으면 어느 날
한쪽만 고쳐진다. 튜플에 적힌 축은 표와 같아야 하고, 표에 있는 축은 실제로 심는 조건
키여야 한다 — 없는 축을 가리키면 이을 곳이 없어 조용히 안 이어진다.
"""

from __future__ import annotations

from app.modules.vocabulary.catalog_specs import CATALOG_SPEC_DEFINITIONS
from app.modules.vocabulary.reference import (
    CONDITIONS,
    SPEC_DEFINITION_LINKS,
    SPEC_DEFINITIONS,
    SPEC_KIND_UPGRADES,
)


def test_튜플의_축은_연결표와_같다() -> None:
    for table in (SPEC_DEFINITIONS, CATALOG_SPEC_DEFINITIONS):
        for row in table:
            key, condition_key = row[0], row[6]
            assert SPEC_DEFINITION_LINKS.get(key) == condition_key, key


def test_연결표의_축은_전부_심는_조건_키다() -> None:
    seeded = {row[0] for row in CONDITIONS}
    assert set(SPEC_DEFINITION_LINKS.values()) <= seeded


def test_종류를_올리는_정의는_튜플에서도_이미_구간이다() -> None:
    """옛 DB 는 따라잡기가, 새 DB 는 튜플이 만든다 — 둘이 다르면 설치마다 정의가 갈린다."""
    kinds = {row[0]: row[3] for row in (*SPEC_DEFINITIONS, *CATALOG_SPEC_DEFINITIONS)}
    for key, new_kind in SPEC_KIND_UPGRADES.items():
        assert kinds[key] == new_kind, key
