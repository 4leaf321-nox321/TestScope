"""카탈로그 반입은 **손으로 고쳐 둔 사양을 안 덮는다.**

## 왜 이 시험이 있나

규칙은 처음부터 코드에 있었다 — `_import_specs` 가 그 기종의 기존 값 정의를 **DB 에서**
읽어 `taken` 에 담고, `_add_value` 가 `definition.id in taken` 이면 바로 돌아간다. 주석도
「손으로 고쳐 둔 것이 사양서보다 정확하다」 라고 적어 두었다.

**그런데 그것을 지키는 시험이 없었다.** `taken` 을 DB 에서 안 읽게 바꾸는 리팩터 한 번이면
보호가 조용히 사라지고, 그 다음 운영 반입에서 손으로 고친 값이 전부 사양서 값으로 돌아간다 —
그리고 고친 사람은 사라진 줄도 모른다. 주석은 보증이 아니다.

빈말이 아니다: 두 기종(인스트론 9450RHK · 9420 High Energy)의 단위환산을 사람이 운영
서버에서 직접 했다(2026-10-03). 이 시험은 그 작업을 지키려고 있다.

같은 규칙을 API 쪽에서 지키는 것은 `test_spec_overwrite.py` 다 — 두 경로가 같은 약속을
한다는 것이 이 두 파일의 요지다.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment.models import EquipmentModel, EquipmentSeries, ModelSpecValue
from app.modules.vocabulary.specs import SpecDefinition

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from catalog_import.values import _import_specs  # type: ignore[import-not-found]

#: 원본 카탈로그가 쓰는 키. 정의 이름과 **다르다** — 반입이 그 둘을 잇는 것이 일이다.
SOURCE_KEY = "weight_kg_for_test"


def _model(db: Session) -> EquipmentModel:
    # `normalized` 는 비교키라 NOT NULL 이다 — 반입이 id 가 아니라 이것으로 찾는다.
    name = f"계열-{uuid.uuid4().hex[:6]}"
    series = EquipmentSeries(name=name, normalized=name.lower())
    db.add(series)
    db.flush()
    kind = f"기종-{uuid.uuid4().hex[:6]}"
    model = EquipmentModel(series_id=series.id, name=kind, normalized=kind.lower())
    db.add(model)
    db.flush()
    return model


def _weight(db: Session) -> SpecDefinition:
    """설치가 심어 두는 수치 사양. 분류를 안 붙여서 어느 기종에서도 쓴다."""
    found = db.scalar(select(SpecDefinition).where(SpecDefinition.key == "weight"))
    assert found is not None, "설치 씨앗에 weight 가 없다"
    return found


def _held(db: Session, model: EquipmentModel, definition: SpecDefinition) -> ModelSpecValue:
    row = db.scalar(
        select(ModelSpecValue).where(
            ModelSpecValue.model_id == model.id,
            ModelSpecValue.definition_id == definition.id,
        )
    )
    assert row is not None
    return row


def test_손으로_고친_값을_반입이_안_덮는다(db: Session) -> None:
    model = _model(db)
    definition = _weight(db)
    # 사람이 단위환산을 해 둔 값. 비고까지 적었다 — 그 비고가 근거다.
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            num_value=30.0,
            note="kg 으로 환산 (운영에서 사람이 고침)",
        )
    )
    db.flush()

    # 사양서는 다른 수를 말한다. 반입을 돌린다.
    #
    # `aliases` 로 **원본 키 → 정의** 짝을 직접 준다. 안 주면 반입이 그 키를 「이 기종만의
    # 사양」 으로 돌려서 `taken` 검사를 아예 안 지나고, 그러면 이 시험이 거짓으로 통과한다.
    made = _import_specs(
        db,
        model,
        {SOURCE_KEY: 300.0},
        {definition.key: definition},
        None,
        {},
        {SOURCE_KEY: (definition.key, 1.0)},
    )
    db.flush()

    # **안 덮었다.** 새로 만든 것도 없다.
    assert made == 0, "반입이 있는 자리에 값을 새로 넣었다"
    row = _held(db, model, definition)
    assert row.num_value == 30.0, "사람이 고친 값이 사양서 값으로 돌아갔다"
    assert row.note == "kg 으로 환산 (운영에서 사람이 고침)", "근거가 사라졌다"


def test_빈_자리는_반입이_채운다(db: Session) -> None:
    """안 덮는다는 것이 **아무것도 안 넣는다**는 뜻이면 반입이 쓸모가 없다."""
    model = _model(db)
    definition = _weight(db)
    made = _import_specs(
        db,
        model,
        {SOURCE_KEY: 300.0},
        {definition.key: definition},
        None,
        {},
        {SOURCE_KEY: (definition.key, 1.0)},
    )
    db.flush()
    assert made == 1
    assert _held(db, model, definition).num_value == 300.0


def test_반입은_규격의_시험_항목을_표로_채운다(db: Session) -> None:
    """**규격의 시험 항목은 표다**(`TestMethodItem`, 2026-09-24). 반입의 시험법 단계가 옛 칸
    (`test_methods.test_item_term_id`)을 보고 있어서, 시험법이 하나라도 있는 DB 에서는 반입이
    통째로 죽었다(2026-10-08 에 찾음). 빈 규격은 채우고, 새 규격은 항목과 함께 선다.
    """
    from types import SimpleNamespace

    from app.modules.methods.models import TestMethod, TestMethodItem
    from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
    from catalog_import.methods import (  # type: ignore[import-not-found]
        step_methods,
        step_promote_pending,
    )

    tag = uuid.uuid4().hex[:6]
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    assert axis is not None
    term = VocabularyTerm(
        vocabulary_id=axis.id, value=f"반입항목-{tag}", normalized=f"반입항목{tag}"
    )
    db.add(term)
    old = TestMethod(code=f"ZZ {tag}-1", title=f"ZZ {tag}-1")
    db.add(old)
    db.flush()

    catalog = SimpleNamespace(
        root=Path(__file__).resolve().parent / "없는-카탈로그",
        test_items=[],
        objects=[
            {
                "id": f"obj-{tag}",
                "test_items": ["item_x"],
                "standards": {"test_methods": [f"ZZ {tag}-1", f"ZZ {tag}-2"]},
            }
        ],
    )
    methods = step_methods(db, catalog, {"item_x": term}, None)
    step_promote_pending(db)  # 옛 칸을 보던 질의 — 깨지지 않고 돈다

    def covered(method: TestMethod) -> list[object]:
        return list(
            db.scalars(
                select(TestMethodItem.test_item_term_id).where(
                    TestMethodItem.method_id == method.id
                )
            )
        )

    assert covered(old) == [term.id], "비어 있던 규격의 시험 항목을 채운다"
    assert covered(methods[f"ZZ {tag}-2"]) == [term.id], "새 규격은 항목과 함께 선다"
    db.rollback()


def test_반입은_운영에서_만든_분류를_별칭으로_찾아_코드를_붙인다(db: Session) -> None:
    """운영에서 손으로 만든 분류(「치수형상측정장비」)를 정본이 나중에 들일 때, 이름이 한
    글자만 달라도 같은 분류가 **두 줄로 서던** 것을 별칭으로 막는다(2026-10-08). 다른 코드가
    붙은 값은 별칭이 같아도 안 잡는다 — 그것은 다른 분류다.
    """
    from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
    from catalog_import.terms import _term  # type: ignore[import-not-found]

    tag = uuid.uuid4().hex[:6]
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "equipment_category"))
    assert axis is not None
    handmade = VocabularyTerm(
        vocabulary_id=axis.id,
        value=f"치수형상측정장비{tag}",
        normalized=f"치수형상측정장비{tag}",
    )
    taken = VocabularyTerm(
        vocabulary_id=axis.id,
        value=f"남의분류{tag}",
        normalized=f"남의분류{tag}",
        code=f"other_{tag}",
    )
    db.add_all([handmade, taken])
    db.flush()

    found = _term(
        db,
        axis,
        f"치수·형상 측정장비 {tag}",
        None,
        code=f"dimensional_{tag}",
        aliases=[f"치수형상측정장비{tag}"],
    )
    assert found.id == handmade.id, "별칭으로 운영의 값을 찾는다(새 줄을 세우지 않는다)"
    assert found.code == f"dimensional_{tag}", (
        "찾은 값에 코드를 붙인다(다음부터 코드로 찾힌다)"
    )

    fresh = _term(
        db, axis, f"새 분류 {tag}", None, code=f"fresh_{tag}", aliases=[f"남의분류{tag}"]
    )
    assert fresh.id != taken.id, "다른 코드가 붙은 값은 별칭이 같아도 잡지 않는다"
    assert taken.code == f"other_{tag}"
    db.rollback()


def _rerun(
    db: Session, model: EquipmentModel, definition: SpecDefinition, specs: dict[str, Any]
) -> None:
    """반입 한 번 — 기종 사양을 넣고 끝맺는다(`finish_refresh`)."""
    from catalog_import import values  # type: ignore[import-not-found]

    values._REFRESH.clear()
    _import_specs(
        db,
        model,
        specs,
        {definition.key: definition},
        None,
        {},
        {SOURCE_KEY: (definition.key, 1.0)},
    )
    values.finish_refresh(db)
    db.flush()


def test_반입이_넣고_아무도_안_고친_값은_정본을_따른다(db: Session) -> None:
    """정본이 값을 바로잡으면(사양서 대조) 재반입이 따라가야 한다 — 안 따라가면 정본을 고쳐도
    운영 값은 영영 처음 넣은 웹 요약 그대로다(2026-10-08)."""
    model = _model(db)
    definition = _weight(db)
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            num_value=30.0,
            note="웹 요약",
            origin="catalog",
        )
    )
    db.flush()

    _rerun(db, model, definition, {SOURCE_KEY: 300.0})

    row = _held(db, model, definition)
    assert row.num_value == 300.0, "반입 값이 정본의 새 값을 안 따라갔다"
    assert row.note is None, "정본에 없는 옛 비고가 남았다"


def test_사람이_고친_반입_값은_정본이_바뀌어도_지킨다(db: Session) -> None:
    """반입이 넣은 값이라도 **누가 고쳤으면**(`updated_by_id`) 그 사람의 값이 이긴다."""
    from app.modules.accounts.models import User

    model = _model(db)
    definition = _weight(db)
    editor = User(
        email=f"spec-editor-{uuid.uuid4().hex[:6]}@testscope.local",
        password_hash="x",
        display_name="사양 편집자",
        status="active",
    )
    db.add(editor)
    db.flush()
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            num_value=30.0,
            note="운영에서 사람이 고침",
            origin="catalog",
            updated_by_id=editor.id,
        )
    )
    db.flush()

    _rerun(db, model, definition, {SOURCE_KEY: 300.0})

    row = _held(db, model, definition)
    assert row.num_value == 30.0 and row.note == "운영에서 사람이 고침"


def test_정본에서_빠진_반입_값은_지운다(db: Session) -> None:
    """사양서 대조에서 「확실하지 않다」 고 정본이 뺀 값이 DB 에 남으면, 검색이 정본이 버린
    숫자로 답한다. 지우는 것은 반입이 넣고 아무도 안 고친 줄뿐이다."""
    model = _model(db)
    definition = _weight(db)
    db.add(
        ModelSpecValue(
            model_id=model.id, definition_id=definition.id, num_value=30.0, origin="catalog"
        )
    )
    db.flush()

    _rerun(db, model, definition, {})

    gone = db.scalar(
        select(ModelSpecValue).where(
            ModelSpecValue.model_id == model.id,
            ModelSpecValue.definition_id == definition.id,
        )
    )
    assert gone is None


def test_정의로_세운_값은_반입이_지우지_않는다(db: Session) -> None:
    """「이 기종만의 사양」 을 정의로 세우면 값이 `origin='catalog'` 를 그대로 갖고 옮겨진다.
    그 정의는 반입의 짝표에 없으므로 「정본에서 빠짐」 으로 읽혀 지워지면 안 된다."""
    from app.modules.vocabulary.specs import SpecGroup

    model = _model(db)
    weight = _weight(db)
    group = db.scalar(select(SpecGroup).limit(1))
    assert group is not None
    raised = SpecDefinition(
        key=f"raised_{uuid.uuid4().hex[:6]}", label="관리자가 세운 사양", group_id=group.id
    )
    db.add(raised)
    db.flush()
    db.add(
        ModelSpecValue(
            model_id=model.id, definition_id=raised.id, num_value=7.0, origin="catalog"
        )
    )
    db.flush()

    _rerun(db, model, weight, {SOURCE_KEY: 300.0})

    kept = _held(db, model, raised)
    assert kept.num_value == 7.0


def test_수치_하나에_비고를_붙인_꼴도_값으로_들인다(db: Session) -> None:
    """`{"value": 300, "note": …}` 를 못 읽던 때는 그 값이 **조용히 빠졌다**(2026-10-08, 사양서
    대조가 수백 곳에 쓴 꼴). 숫자와 비고가 함께 들어와야 한다."""
    model = _model(db)
    definition = _weight(db)

    _rerun(db, model, definition, {SOURCE_KEY: {"value": 300.0, "note": "본체만"}})

    row = _held(db, model, definition)
    assert row.num_value == 300.0
    assert row.note == "본체만"


def test_승격_정의의_종류는_반입_값뿐일_때만_데이터에_맞춘다(db: Session) -> None:
    """종류는 처음 세울 때의 값 모양으로 정해져 그 뒤로 안 바뀌었다 — 나중 객체가 구간으로
    적어도 「글」 로 남아 수치 검색에 안 쓰였다. 값이 전부 반입 값이면 맞추고, 사람 값이 있으면
    둔다."""
    from app.modules.vocabulary.specs import SpecGroup
    from catalog_import.definitions import (  # type: ignore[import-not-found]
        KIND_ALIGNED,
        _align_kind,
    )

    group = db.scalar(select(SpecGroup).limit(1))
    assert group is not None
    model = _model(db)

    def promoted(origin: str) -> SpecDefinition:
        made = SpecDefinition(
            key=f"aligned_{uuid.uuid4().hex[:6]}",
            label="승격분",
            group_id=group.id,
            kind="text",
            help="제조사 카탈로그 2건에서 쓰인 사양(`x_mm`).",
        )
        db.add(made)
        db.flush()
        db.add(
            ModelSpecValue(
                model_id=model.id, definition_id=made.id, text_value="5 ~ 10", origin=origin
            )
        )
        db.flush()
        return made

    only_import = promoted("catalog")
    hand_touched = promoted("manual")
    KIND_ALIGNED.clear()

    _align_kind(db, {"key": only_import.key, "kind": "range"})
    _align_kind(db, {"key": hand_touched.key, "kind": "range"})

    assert only_import.kind == "range"
    assert hand_touched.kind == "text", "사람이 손댄 값이 있는 정의의 종류를 바꿨다"
    aligned = list(KIND_ALIGNED)
    assert aligned == [only_import.key]
    db.rollback()
