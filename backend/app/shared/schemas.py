"""들어오는 몸통의 공통 바탕 — **모르는 칸은 거절한다.**

파이단틱은 기본적으로 모르는 칸을 **말없이 버린다.** 그래서 기계가 칸 이름을 하나 틀리면
(`document_id` 를 `spec_document_id` 로) 서버는 201 을 주고 그 값만 사라진다 — 보낸 쪽은
들어간 줄 알고, 확인하는 사람은 화면에 없으니 「안 적었구나」 로 읽는다. **틀린 값보다
사라진 값이 안 잡힌다.**

신뢰성 시험은 값 하나가 틀리면 그 조건으로 장비를 고르고 그 장비로 보고서가 나간다. 그
정합성을 지키려고 후보/확정을 만들어 놓고 문을 열어 두면 안 된다.

그래서 요청 스키마는 전부 이것을 상속한다. 파이단틱 v2 는 `model_config` 를 **바탕과
합치므로**, 자기 설정(별칭 같은 것)을 더 적어도 이 규칙은 남는다.
`tests/architecture/test_request_schemas.py` 가 라우터를 훑어 빠진 것을 잡는다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Request(BaseModel):
    """요청 몸통. 모르는 칸이 오면 422 로 **무엇이 틀렸는지 말하고** 거절한다."""

    model_config = ConfigDict(extra="forbid")
