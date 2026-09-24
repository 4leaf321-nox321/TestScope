"""들어오는 몸통 — **모르는 칸은 거절한다.**

파이단틱은 기본적으로 모르는 칸을 **말없이 버린다.** 기계가 칸 이름을 하나 틀리면
(`document_id` 를 `spec_document_id` 로) 서버는 201 을 주고 그 값만 사라진다 — 보낸 쪽은
들어간 줄 알고, 확인하는 사람은 화면에 없으니 「안 적었구나」 로 읽는다. **틀린 값보다
사라진 값이 안 잡힌다.**

그래서 요청 스키마는 전부 `app.shared.schemas.Request` 를 상속한다. 이 시험은 **이름 규칙이
아니라 라우터를 훑어서** 실제로 몸통으로 쓰이는 모델을 찾는다 — 이름이 `...Request` 가
아닌 중첩 모델(`AttributeValueIn`)이 정확히 그 사고가 나는 자리였다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.main import _api_router


def _body_models() -> dict[str, type[BaseModel]]:
    """라우터가 **몸통으로 받는** 모델 전부 — 중첩된 것까지."""
    found: dict[str, type[BaseModel]] = {}

    def walk_model(model: Any) -> None:
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            return
        if model.__name__ in found:
            return
        found[model.__name__] = model
        for field in model.model_fields.values():
            annotation = field.annotation
            for arg in (annotation, *getattr(annotation, "__args__", ())):
                walk_model(arg)

    def walk_routes(node: Any) -> None:
        for route in getattr(node, "routes", []) or []:
            dependant = getattr(route, "dependant", None)
            if dependant is not None:
                for param in dependant.body_params:
                    info = getattr(param, "field_info", None)
                    if info is not None:
                        walk_model(info.annotation)
            # 이 FastAPI 는 include_router 를 감싼 채로 둔다 — 안쪽으로 들어가야 보인다.
            inner = getattr(route, "original_router", None)
            if inner is not None:
                walk_routes(inner)

    walk_routes(_api_router())
    return found


def test_요청_스키마는_모르는_칸을_거절한다() -> None:
    models = _body_models()
    assert len(models) > 50, f"몸통 모델을 {len(models)}개밖에 못 찾았다 — 훑는 방법이 깨졌다"
    loose = sorted(
        name for name, model in models.items() if model.model_config.get("extra") != "forbid"
    )
    assert not loose, (
        f"모르는 칸을 조용히 버리는 스키마가 있습니다: {loose}. "
        "`app.shared.schemas.Request` 를 상속하십시오."
    )
