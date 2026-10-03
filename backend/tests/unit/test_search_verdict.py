"""조건 판정 — **모름과 됨을 섞지 않는다.**

이 시험이 지키는 것: 장비에 그 조건이 안 적혀 있는 것과 적혀 있는데 안 되는 것을
같게 답하지 않는다. 같게 답하면 사람은 헛걸음을 하고, 그 한 번으로 시스템 전체가
안 믿긴다.
"""

from __future__ import annotations

import uuid

from app.modules.search.schemas import ConditionQuery
from app.modules.search.verdict import _asked, _range_text, _verdict
from app.modules.test_items.models import EquipmentTestCondition
from app.modules.vocabulary.models import ConditionKey

#: 어느 조건이냐는 판정에 안 쓰인다 — 값만 본다.
KEY = uuid.uuid4()


def limit(minimum: float | None, maximum: float | None) -> EquipmentTestCondition:
    return EquipmentTestCondition(min_value=minimum, max_value=maximum)


def test_없는_조건은_모름이다() -> None:
    query = ConditionQuery(condition_key_id=KEY, at=80)
    assert _verdict(query, None) == "unknown"


def test_구간_안이면_충족() -> None:
    query = ConditionQuery(condition_key_id=KEY, at=80)
    assert _verdict(query, limit(-70, 300)) == "met"


def test_구간_밖이면_미충족() -> None:
    query = ConditionQuery(condition_key_id=KEY, at=400)
    assert _verdict(query, limit(-70, 300)) == "unmet"


def test_상한이_비면_그_값_이상은_모름이다() -> None:
    """상한을 안 적은 것이 무제한이라는 뜻인지 안 적은 것인지 **구별할 수 없다.**

    된다고 답했다가 틀리면 그 한 번으로 시스템이 안 믿긴다 — 모른다고 답한다.
    """
    query = ConditionQuery(condition_key_id=KEY, at_least=20)
    assert _verdict(query, limit(0, None)) == "unknown"


def test_상한이_요구보다_크면_충족() -> None:
    query = ConditionQuery(condition_key_id=KEY, at_least=20)
    assert _verdict(query, limit(0, 50)) == "met"
    assert _verdict(query, limit(0, 10)) == "unmet"


def test_양쪽이_다_비면_모름이다() -> None:
    """범위를 안 적은 것은 통과가 아니다. 통과로 두면 아무것도 안 적힌 장비가
    모든 조건을 만족하는 것으로 나온다."""
    query = ConditionQuery(condition_key_id=KEY, at=80)
    assert _verdict(query, limit(None, None)) == "unknown"


def test_물음과_장비_범위는_축의_단위로_말한다() -> None:
    """si_unit 이 m 인 축이라도 값은 cm(display_unit)로 담겨 있다 — 글자도 cm 다.

    판정이 m 로 옮긴 1.52 를 cm 로 적던 것이 「1.52 cm 에서」 다(2026-10-03). 글자를 만드는
    쪽은 늘 `unit` 을 썼고, 값을 만드는 쪽이 따라오지 않았다 — 둘이 같은 이름을 보게 했다.
    """
    key = ConditionKey(key="drop_height", label="낙하 높이", si_unit="m", display_unit="cm")
    assert key.unit == "cm"
    assert _asked(ConditionQuery(condition_key_id=KEY, at=152), key) == "152 cm 에서"
    assert _range_text(limit(0, 200), key) == "0 cm ~ 200 cm"

    # si_unit 이 비어도 display_unit 이 있으면 그것이 단위다 — 사이클 수(「」 · 「회」).
    bare = ConditionKey(key="cycles", label="사이클 수", si_unit="", display_unit="회")
    assert bare.unit == "회"
    assert _asked(ConditionQuery(condition_key_id=KEY, at_least=24), bare) == "24 회 이상"
