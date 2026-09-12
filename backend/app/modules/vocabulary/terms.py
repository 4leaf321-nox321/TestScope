"""축과 값 — 축 목록·속성 칸, 값의 만들기·고치기·별칭·합치기. 오타가 값이 되는 길을 막는 자리.

`services.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import UniqueConstraint, func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.vocabulary.models import (
    VOCABULARY_DOMAIN_LABELS,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.vocabulary.references import _REFERENCES
from app.modules.vocabulary.schemas import (
    AttributeField,
    TermOut,
    VocabularyOut,
)
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.text import clean, compare_key


def get_vocabulary(db: Session, slug: str) -> Vocabulary:
    found = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
    if found is None:
        raise NotFound("TSC-VOCAB-0001", f"기준정보 축을 찾을 수 없습니다: {slug}")
    return found


def _term_count(db: Session, vocabulary_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(VocabularyTerm)
            .where(VocabularyTerm.vocabulary_id == vocabulary_id)
        )
        or 0
    )


def list_vocabularies(db: Session) -> list[VocabularyOut]:
    """축 목록. **어디의 축인지를 함께 준다.**

    화면이 그것으로 묶는다 — 한 목록에 일곱이 나란히 서면 「이게 어디 쓰이는 값이지」 를
    알 수 없고, 그때 규격 제정기관 축에 회사 이름이 들어간다.
    """
    rows = db.scalars(select(Vocabulary).order_by(Vocabulary.sort_order, Vocabulary.label))
    return [
        VocabularyOut(
            id=row.id,
            slug=row.slug,
            label=row.label,
            domain=row.domain,
            # 이름까지 서버가 준다 — 화면마다 사전을 두면 한 곳만 안 고쳐진다.
            domain_label=VOCABULARY_DOMAIN_LABELS.get(row.domain, row.domain),
            description=row.description,
            entry_policy=row.entry_policy,
            parent_slug=row.parent_slug,
            sort_order=row.sort_order,
            attribute_schema=[AttributeField(**one) for one in row.attribute_schema or []],
            term_count=_term_count(db, row.id),
        )
        for row in rows
    ]


def vocabulary_out(db: Session, row: Vocabulary) -> VocabularyOut:
    return VocabularyOut(
        id=row.id,
        slug=row.slug,
        label=row.label,
        domain=row.domain,
        domain_label=VOCABULARY_DOMAIN_LABELS.get(row.domain, row.domain),
        description=row.description,
        entry_policy=row.entry_policy,
        parent_slug=row.parent_slug,
        sort_order=row.sort_order,
        attribute_schema=[AttributeField(**one) for one in row.attribute_schema or []],
        term_count=_term_count(db, row.id),
    )


def update_vocabulary(db: Session, *, slug: str, changes: dict[str, Any]) -> Vocabulary:
    """축의 이름·설명·정책·속성 칸. **slug 와 소속은 안 받는다** — 코드가 건다."""
    row = get_vocabulary(db, slug)
    if "label" in changes and changes["label"] is not None:
        row.label = clean(changes["label"])
    if "description" in changes:
        row.description = changes["description"]
    if "entry_policy" in changes and changes["entry_policy"] is not None:
        row.entry_policy = changes["entry_policy"]
    if "attribute_schema" in changes and changes["attribute_schema"] is not None:
        keys = [one["key"] for one in changes["attribute_schema"]]
        if len(keys) != len(set(keys)):
            raise AppError("TSC-VOCAB-0010", "속성 칸의 키가 겹칩니다.", status=400)
        row.attribute_schema = changes["attribute_schema"]
    db.commit()
    db.refresh(row)
    return row


def _aliases_of(db: Session, term_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(VocabularyAlias.value)
            .where(VocabularyAlias.term_id == term_id, VocabularyAlias.is_active.is_(True))
            .order_by(VocabularyAlias.value)
        )
    )


def _usage_of(db: Session, vocabulary: Vocabulary) -> dict[uuid.UUID, int]:
    """그 축의 값마다 몇 군데서 쓰이나. **셀 때 센다.**

    전에는 `vocabulary_terms.usage_count` 칸에 적어 두게 되어 있었는데, **아무도 안
    갱신했다** — 장비 700대와 계열 200개를 들이고도 모든 값이 0 이었다. 0 인 화면은
    거짓말을 하고, 그 거짓말로는 값을 지울지 말지 정할 수 없다.

    칸당 GROUP BY 한 번이다(축 하나에 두세 번). 가리키는 칸에 인덱스가 있어서 값이
    백 개든 천 개든 같은 비용이다 — 틀린 수를 싸게 얻느니 맞는 수를 이 값에 치른다.
    """
    out: dict[uuid.UUID, int] = {}
    for model, column in _REFERENCES.get(vocabulary.slug, []):
        stmt = select(column, func.count()).where(column.is_not(None)).group_by(column)
        deleted = getattr(model, "deleted_at", None)
        if deleted is not None:
            # 지운 장비가 값을 붙잡고 있으면 「쓰는 데가 있다」 가 거짓이 된다.
            stmt = stmt.where(deleted.is_(None))
        for term_id, count in db.execute(stmt).all():
            out[term_id] = out.get(term_id, 0) + count
    return out


def term_out(
    db: Session,
    term: VocabularyTerm,
    *,
    vocabulary: Vocabulary | None = None,
    usage: dict[uuid.UUID, int] | None = None,
) -> TermOut:
    """값 한 줄.

    쓰임 수는 **목록이 한 번에 세어 넘긴다**(`list_terms`). 안 넘기면 여기서 그 축을
    한 번 센다 — 한 줄을 그리려고 축 전체를 세는 셈이지만, 한 줄짜리 호출은 드물다.
    """
    vocab = vocabulary or db.get(Vocabulary, term.vocabulary_id)
    parent = db.get(VocabularyTerm, term.parent_term_id) if term.parent_term_id else None
    if usage is None:
        usage = _usage_of(db, vocab) if vocab else {}
    return TermOut(
        id=term.id,
        vocabulary_slug=vocab.slug if vocab else "",
        value=term.value,
        code=term.code,
        parent_term_id=term.parent_term_id,
        parent_value=parent.value if parent else None,
        status=term.status,
        usage_count=usage.get(term.id, 0),
        aliases=_aliases_of(db, term.id),
        attributes=term.attributes,
        created_at=term.created_at,
    )


def list_terms(
    db: Session, *, slug: str, query: str | None, include_deprecated: bool
) -> list[TermOut]:
    vocabulary = get_vocabulary(db, slug)
    stmt = select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocabulary.id)
    if not include_deprecated:
        # **기본은 숨긴다.** 폐기한 값이 피커에 뜨면 사람이 그걸 또 고른다.
        stmt = stmt.where(VocabularyTerm.status == "active")
    if query:
        stmt = stmt.where(VocabularyTerm.normalized.contains(compare_key(query)))
    rows = db.scalars(stmt.order_by(VocabularyTerm.value))
    # **한 번에 센다.** 줄마다 세면 값 108개짜리 축에서 조회가 수백 번 돈다.
    usage = _usage_of(db, vocabulary)
    return [term_out(db, row, vocabulary=vocabulary, usage=usage) for row in rows]


def _find_by_key(db: Session, vocabulary_id: uuid.UUID, key: str) -> VocabularyTerm | None:
    """값과 **별칭 양쪽**을 뒤진다.

    별칭을 안 보면 UTM 을 다시 등록할 수 있게 되고, 그 순간 별칭을 등록해 둔 뜻이
    사라진다 — 예방이 목적인 표가 아무것도 예방하지 못한다.
    """
    found = db.scalar(
        select(VocabularyTerm).where(
            VocabularyTerm.vocabulary_id == vocabulary_id, VocabularyTerm.normalized == key
        )
    )
    if found is not None:
        return found
    alias = db.scalar(
        select(VocabularyAlias).where(
            VocabularyAlias.vocabulary_id == vocabulary_id, VocabularyAlias.normalized == key
        )
    )
    return db.get(VocabularyTerm, alias.term_id) if alias else None


def create_term(
    db: Session,
    *,
    slug: str,
    value: str,
    code: str | None,
    parent_term_id: uuid.UUID | None,
    attributes: dict[str, Any],
    actor: User,
    is_admin: bool,
) -> VocabularyTerm:
    vocabulary = get_vocabulary(db, slug)

    # closed 축은 관리자만 채운다. **검색의 축이 되는 것**이라 오타 하나가 값이
    # 되면 그 장비는 영영 검색에 안 걸린다.
    if vocabulary.entry_policy == "closed" and not is_admin:
        raise AppError(
            "TSC-VOCAB-0002",
            f"{vocabulary.label}은 관리자만 값을 추가할 수 있습니다.",
            status=403,
        )

    text = clean(value)
    key = compare_key(text)
    existing = _find_by_key(db, vocabulary.id, key)
    if existing is not None:
        raise Conflict(
            "TSC-VOCAB-0003",
            f"이미 있는 값입니다: {existing.value}",
            details={"term_id": str(existing.id), "value": existing.value},
        )
    _require_free_code(db, vocabulary.id, clean(code) if code else None, exclude=None)

    term = VocabularyTerm(
        vocabulary_id=vocabulary.id,
        value=text,
        normalized=key,
        code=clean(code) if code else None,
        parent_term_id=parent_term_id,
        attributes=attributes,
        created_by_id=actor.id,
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


def _require_free_code(
    db: Session, vocabulary_id: uuid.UUID, code: str | None, *, exclude: uuid.UUID | None
) -> None:
    """한 축에 같은 코드가 둘이면 반입·검색이 어느 값을 걸지 모른다. 이름처럼 잡는다."""
    if not code:
        return
    stmt = select(VocabularyTerm).where(
        VocabularyTerm.vocabulary_id == vocabulary_id, VocabularyTerm.code == code
    )
    if exclude is not None:
        stmt = stmt.where(VocabularyTerm.id != exclude)
    clash = db.scalar(stmt)
    if clash is not None:
        raise Conflict(
            "TSC-VOCAB-0016",
            f"그 코드는 이미 「{clash.value}」 이 씁니다.",
            details={"term_id": str(clash.id), "value": clash.value},
        )


def get_term(db: Session, term_id: uuid.UUID) -> VocabularyTerm:
    term = db.get(VocabularyTerm, term_id)
    if term is None:
        raise NotFound("TSC-VOCAB-0004", "값을 찾을 수 없습니다.")
    return term


def update_term(
    db: Session,
    *,
    term_id: uuid.UUID,
    value: str | None,
    code: str | None,
    parent_term_id: uuid.UUID | None,
    status: str | None,
    attributes: dict[str, Any] | None,
    actor: User,
) -> VocabularyTerm:
    term = get_term(db, term_id)

    if value is not None:
        text = clean(value)
        key = compare_key(text)
        if key != term.normalized:
            clash = _find_by_key(db, term.vocabulary_id, key)
            if clash is not None and clash.id != term.id:
                raise Conflict("TSC-VOCAB-0003", f"이미 있는 값입니다: {clash.value}")
            # **이름 변경은 감사에 남긴다.** 이 값을 가리키는 장비 수십 대의 표시가
            # 한꺼번에 바뀌는 일이고, 나중에 "왜 이름이 달라졌지" 를 물을 자리가
            # 여기밖에 없다.
            audit.record(
                db,
                action=audit.VOCABULARY_RENAMED,
                actor=actor,
                target_table="vocabulary_terms",
                target_id=term.id,
                target_label=term.value,
                changes={"value": {"before": term.value, "after": text}},
            )
        term.value = text
        term.normalized = key

    if code is not None:
        cleaned = clean(code) or None
        _require_free_code(db, term.vocabulary_id, cleaned, exclude=term.id)
        term.code = cleaned
    if parent_term_id is not None:
        term.parent_term_id = parent_term_id
    if status is not None:
        term.status = status
    if attributes is not None:
        term.attributes = attributes

    db.commit()
    db.refresh(term)
    return term


def add_alias(db: Session, *, term_id: uuid.UUID, value: str) -> VocabularyTerm:
    term = get_term(db, term_id)
    text = clean(value)
    key = compare_key(text)

    existing = _find_by_key(db, term.vocabulary_id, key)
    if existing is not None:
        raise Conflict(
            "TSC-VOCAB-0005",
            f"그 표기는 이미 {existing.value}을(를) 가리킵니다.",
        )

    db.add(
        VocabularyAlias(
            vocabulary_id=term.vocabulary_id, term_id=term.id, value=text, normalized=key
        )
    )
    db.commit()
    db.refresh(term)
    return term


def remove_alias(db: Session, *, term_id: uuid.UUID, value: str) -> VocabularyTerm:
    """표기 하나를 뗀다. 병합이 남긴 옛 이름을 떼면 같은 오타가 또 들어올 수 있다 —
    그래도 잘못 붙은 표기를 못 떼는 것보다는 낫다. 떼는 것은 관리자다."""
    term = get_term(db, term_id)
    key = compare_key(value)
    alias = db.scalar(
        select(VocabularyAlias).where(
            VocabularyAlias.term_id == term.id, VocabularyAlias.normalized == key
        )
    )
    if alias is None:
        raise NotFound("TSC-VOCAB-0011", "그 표기가 없습니다.")
    db.delete(alias)
    db.commit()
    db.refresh(term)
    return term


def _repoint_references(
    db: Session, vocabulary: Vocabulary, source: VocabularyTerm, target: VocabularyTerm
) -> int:
    """원본을 가리키던 도메인 행을 대상으로 돌린다. **안 돌리면 병합이 RESTRICT 에 막힌다** —
    쓰이는 값일수록 합칠 일이 많은데, 바로 그 값이 합쳐지지 않는 셈이었다.

    같은 짝이 이미 대상 쪽에도 있으면(한 계열에 「인장」 과 「인장시험」 시험 항목이 둘 다)
    유일 제약에 걸린다 — 그 행은 **지운다**: 합치고 나면 같은 줄이 둘인 것이라 하나면 된다.
    """
    moved = 0
    for model, column in _REFERENCES.get(vocabulary.slug, []):
        for row in list(db.scalars(select(model).where(column == source.id))):
            if _twin_exists(db, model, column, row, target.id):
                # 대상 쪽에 같은 줄이 이미 있다. **유일 제약을 믿지 않는다** — NULL 이 낀
                # 짝(규격 없는 시험 항목)은 PostgreSQL 이 겹치는 것으로 안 본다.
                db.delete(row)
            else:
                setattr(row, column.key, target.id)
            db.flush()
            moved += 1
    return moved


def _twin_exists(db: Session, model: Any, column: Any, row: Any, target_id: uuid.UUID) -> bool:
    """`row` 의 유일 키에서 `column` 만 `target_id` 로 바꾼 줄이 이미 있나."""
    table = model.__table__
    for constraint in table.constraints:
        if not isinstance(constraint, UniqueConstraint):
            continue
        names = [one.name for one in constraint.columns]
        if column.key not in names:
            continue
        clauses = []
        for name in names:
            attr = getattr(model, name)
            value = target_id if name == column.key else getattr(row, name)
            clauses.append(attr.is_(None) if value is None else attr == value)
        pk = next(iter(table.primary_key.columns))
        twin = db.scalar(
            select(getattr(model, pk.name)).where(
                *clauses, getattr(model, pk.name) != getattr(row, pk.name)
            )
        )
        if twin is not None:
            return True
    return False


def merge_terms(
    db: Session, *, source_id: uuid.UUID, target_id: uuid.UUID, actor: User
) -> VocabularyTerm:
    """원본을 대상으로 합치고, 원본 이름을 **대상의 별칭으로 남긴다.**

    지워 버리면 같은 오타가 또 들어온다 — 그때는 아무도 그것이 예전에 합쳐졌던
    값이라는 것을 모른다.
    """
    source = get_term(db, source_id)
    target = get_term(db, target_id)
    if source.id == target.id:
        raise AppError("TSC-VOCAB-0006", "같은 값끼리는 합칠 수 없습니다.", status=400)
    if source.vocabulary_id != target.vocabulary_id:
        raise AppError("TSC-VOCAB-0007", "다른 축의 값끼리는 합칠 수 없습니다.", status=400)

    vocabulary = db.get(Vocabulary, source.vocabulary_id)
    moved = _repoint_references(db, vocabulary, source, target) if vocabulary else 0

    # 원본을 가리키던 하위 값을 대상으로 옮긴다. 안 옮기면 부모 잃은 값이 남는다.
    for child in db.scalars(
        select(VocabularyTerm).where(VocabularyTerm.parent_term_id == source.id)
    ):
        child.parent_term_id = target.id

    # 원본의 별칭도 함께 넘긴다 — 별칭의 별칭이 되면 조회가 두 단계가 된다.
    for alias in db.scalars(
        select(VocabularyAlias).where(VocabularyAlias.term_id == source.id)
    ):
        alias.term_id = target.id

    db.add(
        VocabularyAlias(
            vocabulary_id=target.vocabulary_id,
            term_id=target.id,
            value=source.value,
            normalized=source.normalized,
        )
    )
    audit.record(
        db,
        action=audit.VOCABULARY_MERGED,
        actor=actor,
        target_table="vocabulary_terms",
        target_id=target.id,
        target_label=target.value,
        changes={
            "merged_from": {"before": source.value, "after": target.value},
            "repointed": {"before": 0, "after": moved},
        },
    )
    db.delete(source)
    db.commit()
    db.refresh(target)
    return target
