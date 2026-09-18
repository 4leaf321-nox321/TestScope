"""이름으로 찾는다 — **AI 가 쓰는 첫 도구.**

## 왜 목록 검색으로는 부족한가

`/equipment-models?q=…` 는 「비슷한 것들」 을 준다. AI 에게 필요한 것은 그게 아니라
**「하나로 정해졌나」** 다. 정해졌으면 id 를 쓰고, 아니면 물어야 하고, 없으면 비워
둬야 한다. 그 셋을 목록만 보고 판단하게 두면 AI 는 첫 줄을 집는다 — 틀린 줄도
첫 줄이면 집는다.

## 네 단계로 좁힌다

    1. 비교키가 정확히 같다      -> exact
    2. 별칭이 정확히 같다        -> exact (기준정보 값만)
    3. 이름에 포함된다           -> candidates
    4. 뜻이 가깝다               -> candidates (의미 검색이 켜져 있을 때만)

정확히 하나만 남아도 **곧바로 exact 로 올리지 않는다**(포함 검색은 우연히 하나일
수 있다). 다만 후보가 하나면 화면·AI 둘 다 그것을 쓰기 쉬우므로 `hint` 로 말한다.

4 는 글자가 하나도 안 겹칠 때를 위한 것이다 — 「HAST」 를 물었는데 값은 「고가속 습열」 이고
별칭에도 없을 때. 후보일 뿐이고 **exact 로는 절대 안 올린다**: 벡터가 가깝다는 것은 같다는
뜻이 아니다. 의미 검색이 꺼져 있으면(pgvector·Ollama 없음) 이 단계는 그냥 비어 있다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment, EquipmentModel, EquipmentSeries
from app.modules.methods.models import TestMethod
from app.modules.reliability.models import ReliabilityTest
from app.modules.resolve.schemas import ResolveCandidate, ResolveResponse
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import semantic
from app.shared.errors import AppError
from app.shared.permissions import visible_equipment
from app.shared.text import clean, compare_key

_EXACT = "정확히 같음"
_ALIAS = "별칭"
_PART = "이름에 포함"
_NEAR = "뜻이 가까움"

#: 이보다 멀면 후보로 안 올린다. bge-m3 실측(2026-09-15): 맞는 것은 0.5 위, 엉뚱한 것은
#: 0.4 안팎 — 「HAST」 에 「마모」 가 0.395 로 따라왔다.
_NEAR_MIN_SCORE = 0.45


def _near(db: Session, text: str, kind: str, limit: int) -> list[ResolveCandidate]:
    """뜻이 가까운 후보. 의미 검색이 없으면 빈 목록 — 예외를 안 낸다."""
    made: list[ResolveCandidate] = []
    for found in semantic.search(db, text, kinds=[kind], limit=limit):
        if found.score < _NEAR_MIN_SCORE:
            continue
        made.append(
            ResolveCandidate(
                id=uuid.UUID(found.entity_id),
                label=found.title,
                detail=f"유사도 {found.score:.2f}",
                why=_NEAR,
            )
        )
    return made


def _answer(
    exact: ResolveCandidate | None, candidates: Sequence[ResolveCandidate]
) -> ResolveResponse:
    if exact is not None:
        return ResolveResponse(
            match="exact",
            id=exact.id,
            label=exact.label,
            candidates=[exact],
            hint="하나로 정해졌습니다. 이 id 를 그대로 쓰세요.",
        )
    if not candidates:
        return ResolveResponse(
            match="none",
            id=None,
            label=None,
            candidates=[],
            # **지어내지 마라**가 핵심이다. 없는 것을 만들지, 비워 둘지는 부르는
            # 쪽의 판단이지만, 비슷한 이름을 골라 넣는 것만은 아니다.
            hint="찾지 못했습니다. 새로 만들거나 비워 두세요 — 비슷한 이름을 "
            "골라 넣지 마세요.",
        )
    if len(candidates) == 1:
        return ResolveResponse(
            match="candidates",
            id=None,
            label=None,
            candidates=list(candidates),
            hint="후보가 하나입니다. 맞는지 확인한 뒤 그 id 를 쓰세요 — "
            "이름의 일부가 우연히 겹쳤을 수 있습니다.",
        )
    return ResolveResponse(
        match="candidates",
        id=None,
        label=None,
        candidates=list(candidates),
        hint=f"후보가 {len(candidates)}개입니다. 고르지 말고 사람에게 물으세요.",
    )


def _series_label(db: Session, row: EquipmentSeries) -> str:
    maker = db.get(VocabularyTerm, row.maker_term_id) if row.maker_term_id else None
    name = row.name_ko or row.name
    return f"{maker.value} {name}" if maker else name


def _resolve_series(db: Session, text: str, maker: str | None, limit: int) -> ResolveResponse:
    key = compare_key(text)
    stmt = select(EquipmentSeries).where(EquipmentSeries.deleted_at.is_(None))
    if maker:
        makers = select(VocabularyTerm.id).where(
            VocabularyTerm.normalized == compare_key(maker)
        )
        stmt = stmt.where(EquipmentSeries.maker_term_id.in_(makers))

    hit = db.scalars(stmt.where(EquipmentSeries.normalized == key)).all()
    if len(hit) == 1:
        row = hit[0]
        return _answer(
            ResolveCandidate(
                id=row.id, label=_series_label(db, row), detail=row.name, why=_EXACT
            ),
            [],
        )

    like = f"%{clean(text)}%"
    rows = db.scalars(
        stmt.where(EquipmentSeries.name.ilike(like) | EquipmentSeries.name_ko.ilike(like))
        .order_by(EquipmentSeries.name)
        .limit(limit)
    ).all()
    candidates = [
        ResolveCandidate(id=row.id, label=_series_label(db, row), detail=row.name, why=_PART)
        for row in rows
    ]
    if not candidates and not maker:
        candidates = _near(db, text, "series", limit)
    return _answer(None, candidates)


def _resolve_model(db: Session, text: str, maker: str | None, limit: int) -> ResolveResponse:
    """기종을 찾는다. **계열과 제조사를 이름에 붙여 돌려준다.**

    `68FM-300` 하나만 보여 주면 후보 셋이 전부 같아 보인다 — 무엇으로 골라야 할지
    화면도 AI 도 알 수 없다.
    """
    key = compare_key(text)
    stmt = select(EquipmentModel).where(EquipmentModel.deleted_at.is_(None))
    if maker:
        makers = select(VocabularyTerm.id).where(
            VocabularyTerm.normalized == compare_key(maker)
        )
        stmt = stmt.where(
            EquipmentModel.series_id.in_(
                select(EquipmentSeries.id).where(EquipmentSeries.maker_term_id.in_(makers))
            )
        )

    def _label(row: EquipmentModel) -> tuple[str, str | None]:
        series = db.get(EquipmentSeries, row.series_id)
        maker_term = (
            db.get(VocabularyTerm, series.maker_term_id)
            if series and series.maker_term_id
            else None
        )
        head = " ".join(
            part for part in (maker_term.value if maker_term else None, row.name) if part
        )
        return head, series.name if series else None

    hit = db.scalars(stmt.where(EquipmentModel.normalized == key)).all()
    if len(hit) == 1:
        head, detail = _label(hit[0])
        return _answer(
            ResolveCandidate(id=hit[0].id, label=head, detail=detail, why=_EXACT), []
        )

    like = f"%{clean(text)}%"
    series_like = select(EquipmentSeries.id).where(
        EquipmentSeries.name.ilike(like) | EquipmentSeries.name_ko.ilike(like)
    )
    rows = db.scalars(
        stmt.where(
            EquipmentModel.name.ilike(like)
            | EquipmentModel.name_ko.ilike(like)
            | EquipmentModel.series_id.in_(series_like)
        )
        .order_by(EquipmentModel.name)
        .limit(limit)
    ).all()
    out: list[ResolveCandidate] = []
    for row in rows:
        head, detail = _label(row)
        out.append(ResolveCandidate(id=row.id, label=head, detail=detail, why=_PART))
    return _answer(None, out)


def _resolve_term(db: Session, text: str, axis: str | None, limit: int) -> ResolveResponse:
    """기준정보 값을 찾는다. **별칭도 본다.**

    중복은 사후에 합치는 것보다 애초에 안 생기게 하는 것이 싸다 — 「UTM」 으로 물은
    사람에게 「만능재료시험기」 를 돌려주는 자리가 여기다.
    """
    if not axis:
        raise AppError(
            "TSC-RESOLVE-0001",
            "기준정보 값을 찾으려면 축(axis)이 필요합니다.",
            status=400,
            details={"axis": "manufacturer · equipment_category · test_item · site"},
        )
    vocabulary = db.scalar(select(Vocabulary).where(Vocabulary.slug == axis))
    if vocabulary is None:
        raise AppError("TSC-RESOLVE-0002", f"없는 축입니다: {axis}", status=400)

    key = compare_key(text)
    exact = db.scalar(
        select(VocabularyTerm).where(
            VocabularyTerm.vocabulary_id == vocabulary.id,
            VocabularyTerm.normalized == key,
        )
    )
    if exact is not None:
        return _answer(
            ResolveCandidate(id=exact.id, label=exact.value, detail=axis, why=_EXACT), []
        )

    alias = db.scalar(
        select(VocabularyAlias).where(
            VocabularyAlias.vocabulary_id == vocabulary.id,
            VocabularyAlias.normalized == key,
            VocabularyAlias.is_active.is_(True),
        )
    )
    if alias is not None:
        term = db.get(VocabularyTerm, alias.term_id)
        if term is not None:
            return _answer(
                ResolveCandidate(
                    id=term.id,
                    label=term.value,
                    detail=f"별칭 「{alias.value}」",
                    why=_ALIAS,
                ),
                [],
            )

    like = f"%{clean(text)}%"
    rows = db.scalars(
        select(VocabularyTerm)
        .where(
            VocabularyTerm.vocabulary_id == vocabulary.id,
            VocabularyTerm.value.ilike(like),
        )
        .order_by(VocabularyTerm.value)
        .limit(limit)
    ).all()
    candidates = [
        ResolveCandidate(id=row.id, label=row.value, detail=axis, why=_PART) for row in rows
    ]
    # 카드가 있는 축(시험 항목·물성)만 뜻으로도 찾는다.
    if not candidates and axis in ("test_item", "property"):
        candidates = _near(db, text, axis, limit)
    return _answer(None, candidates)


def _resolve_method(db: Session, text: str, limit: int) -> ResolveResponse:
    key = compare_key(text)
    stmt = select(TestMethod).where(TestMethod.deleted_at.is_(None))

    rows = db.scalars(stmt.where(TestMethod.code.ilike(clean(text)))).all()
    exact = [row for row in rows if compare_key(row.code) == key]
    if len(exact) == 1:
        row = exact[0]
        return _answer(
            ResolveCandidate(
                id=row.id,
                label=f"{row.code} {row.edition or ''}".strip(),
                detail=row.title,
                why=_EXACT,
            ),
            [],
        )

    like = f"%{clean(text)}%"
    found = db.scalars(
        stmt.where(TestMethod.code.ilike(like) | TestMethod.title.ilike(like))
        .order_by(TestMethod.code)
        .limit(limit)
    ).all()
    candidates = [
        ResolveCandidate(
            id=row.id,
            label=f"{row.code} {row.edition or ''}".strip(),
            detail=row.title,
            why=_PART,
        )
        for row in found
    ]
    if not candidates:
        candidates = _near(db, text, "method", limit)
    return _answer(None, candidates)


def _workspace_id(db: Session, slug: str | None) -> uuid.UUID | None:
    """부서 slug -> id. 없는 slug 는 거절한다 — 조용히 무시하면 **부서를 좁힌 줄 알고**
    받은 후보를 사람이 전사 것으로 오해한다."""
    if not slug:
        return None
    row = db.scalar(select(Workspace).where(Workspace.slug == slug))
    if row is None:
        raise AppError("TSC-RESOLVE-0004", f"없는 부서입니다: {slug}", status=400)
    return row.id


def _resolve_reliability_test(
    db: Session, text: str, workspace: str | None, limit: int
) -> ResolveResponse:
    """부서가 등록한 시험 절차를 찾는다. **이름은 부서를 가로질러 겹친다.**

    「고온고습 1000h」 는 거의 모든 부서에 하나씩 있다. 그래서 이름이 정확히 같아도
    **둘 이상이면 exact 가 아니다** — 부서(`workspace`)를 함께 주거나, 사람에게 어느
    부서의 것인지 물어야 한다. 이름표에 부서를 붙여 후보끼리 구별되게 한다.
    """
    stmt = select(ReliabilityTest).where(ReliabilityTest.deleted_at.is_(None))
    picked = _workspace_id(db, workspace)
    if picked is not None:
        stmt = stmt.where(ReliabilityTest.workspace_id == picked)

    def _label(row: ReliabilityTest) -> tuple[str, str | None]:
        team = db.get(Workspace, row.workspace_id)
        return row.name, team.name if team else None

    key = compare_key(text)
    same = [row for row in db.scalars(stmt) if compare_key(row.name) == key]
    if len(same) == 1:
        head, detail = _label(same[0])
        return _answer(
            ResolveCandidate(id=same[0].id, label=head, detail=detail, why=_EXACT), []
        )
    if len(same) > 1:
        # **같은 이름이 여럿이면 고르지 않는다.** 부서를 주면 하나로 줄어든다.
        return _answer(
            None,
            [
                ResolveCandidate(
                    id=row.id, label=_label(row)[0], detail=_label(row)[1], why=_EXACT
                )
                for row in same[:limit]
            ],
        )

    like = f"%{clean(text)}%"
    rows = db.scalars(
        stmt.where(ReliabilityTest.name.ilike(like) | ReliabilityTest.purpose.ilike(like))
        .order_by(ReliabilityTest.name)
        .limit(limit)
    ).all()
    return _answer(
        None,
        [
            ResolveCandidate(id=row.id, label=_label(row)[0], detail=_label(row)[1], why=_PART)
            for row in rows
        ],
    )


def _resolve_equipment(
    db: Session, user: User, text: str, workspace: str | None, limit: int
) -> ResolveResponse:
    """보유 장비를 자산번호·이름으로 찾는다. **볼 수 있는 것만** 본다.

    자산번호는 유일하므로 그것이 정확히 맞으면 exact 다. 이름은 안 그렇다 —
    「만능재료시험기」 는 한 부서에만 넷일 수 있고, 그때 첫 줄을 집으면 하중이 다른 장비의
    수치로 답하게 된다(계열이 아니라 기종을 가리키게 한 것과 같은 이유다).
    """
    stmt = visible_equipment(db, user)
    picked = _workspace_id(db, workspace)
    if picked is not None:
        stmt = stmt.where(Equipment.owner_workspace_id == picked)

    def _label(row: Equipment) -> tuple[str, str | None]:
        team = db.get(Workspace, row.owner_workspace_id) if row.owner_workspace_id else None
        place = " · ".join(
            part for part in (team.name if team else None, row.location) if part
        )
        return f"{row.name} ({row.asset_no})", place or None

    key = compare_key(text)
    by_asset = [row for row in db.scalars(stmt) if compare_key(row.asset_no) == key]
    if len(by_asset) == 1:
        head, detail = _label(by_asset[0])
        return _answer(
            ResolveCandidate(id=by_asset[0].id, label=head, detail=detail, why=_EXACT), []
        )

    like = f"%{clean(text)}%"
    rows = db.scalars(
        stmt.where(Equipment.asset_no.ilike(like) | Equipment.name.ilike(like))
        .order_by(Equipment.asset_no)
        .limit(limit)
    ).all()
    return _answer(
        None,
        [
            ResolveCandidate(id=row.id, label=_label(row)[0], detail=_label(row)[1], why=_PART)
            for row in rows
        ],
    )


def _resolve_workspace(db: Session, text: str, limit: int) -> ResolveResponse:
    """부서를 slug 나 이름으로 찾는다. **쓰기 API 가 요구하는 것은 slug 다.**

    「DX 부문」 이라고 말한 사람에게 필요한 것은 `dx` 이고, 그 둘을 잇는 자리가 여기다 —
    없으면 AI 가 이름을 slug 로 짐작해 넣고, 그 짐작은 대개 404 이거나 남의 부서다.
    """
    key = compare_key(text)
    rows = list(db.scalars(select(Workspace)))
    same = [row for row in rows if key in (compare_key(row.slug), compare_key(row.name))]
    if len(same) == 1:
        return _answer(
            ResolveCandidate(
                id=same[0].id, label=same[0].name, detail=f"slug: {same[0].slug}", why=_EXACT
            ),
            [],
        )
    text_key = clean(text).casefold()
    found = [
        row
        for row in rows
        if text_key in row.name.casefold() or text_key in row.slug.casefold()
    ]
    return _answer(
        None,
        [
            ResolveCandidate(id=row.id, label=row.name, detail=f"slug: {row.slug}", why=_PART)
            for row in found[:limit]
        ],
    )


def resolve(
    db: Session, payload: dict[str, Any], *, user: User | None = None
) -> ResolveResponse:
    """이름 하나를 id 로. `kind="equipment"` 만 **보는 사람**이 필요하다 — 가시성이
    사람마다 다르기 때문이다(가린 부서의 장비는 후보에도 안 선다). 서버 안쪽에서 규격을
    집을 때처럼 사람이 없는 자리도 있어 선택 인자로 둔다."""
    kind = payload["kind"]
    text = payload["text"]
    limit = payload.get("limit") or 8
    maker = payload.get("maker")
    workspace = payload.get("workspace")

    if kind == "series":
        return _resolve_series(db, text, maker, limit)
    if kind == "model":
        return _resolve_model(db, text, maker, limit)
    if kind == "term":
        return _resolve_term(db, text, payload.get("axis"), limit)
    if kind == "reliability_test":
        return _resolve_reliability_test(db, text, workspace, limit)
    if kind == "equipment":
        if user is None:  # pragma: no cover - 라우터는 늘 사람을 준다
            raise AppError(
                "TSC-RESOLVE-0005", "보유 장비는 보는 사람이 있어야 찾습니다.", status=400
            )
        return _resolve_equipment(db, user, text, workspace, limit)
    if kind == "workspace":
        return _resolve_workspace(db, text, limit)
    return _resolve_method(db, text, limit)


def resolve_term_id(
    db: Session, axis: str, text: str | None, *, field: str
) -> uuid.UUID | None:
    """이름 하나를 기준정보 id 로 바꾼다. **못 정하면 거절한다.**

    쓰기 API 가 이름을 받을 때 쓰는 자리다. 후보가 여럿이면 고르지 않는다 — 여기서
    첫 줄을 집으면 그 선택은 아무 데도 안 남고, 틀렸을 때 찾을 방법이 없다.
    """
    if not text:
        return None
    answer = _resolve_term(db, text, axis, 5)
    if answer.match == "exact" and answer.id is not None:
        return answer.id
    raise AppError(
        "TSC-RESOLVE-0003",
        f"{field}: 「{text}」 을(를) 하나로 정할 수 없습니다. id 로 주거나 "
        f"기준정보에서 먼저 만드세요.",
        status=400,
        details={
            "field": field,
            "axis": axis,
            "candidates": [
                {"id": str(one.id), "label": one.label} for one in answer.candidates
            ],
        },
    )
