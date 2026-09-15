"""의미 검색 — 카드·색인·검색의 배관.

mock 임베딩으로 돈다(뜻은 없다 — 넣은 것을 그대로 찾을 수 있나만 본다). pgvector 가 없는
기계에서는 표를 못 만드니 건너뛴다 — CI 가 그렇다. 개발 PC 에는 있어서 여기서 돈다.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.shared import embeddings, semantic


@pytest.fixture
def mock_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "embedding_backend", "mock")


def _test_item(db: Session, value: str, alias: str) -> VocabularyTerm:
    axis = db.scalar(db.query(Vocabulary).where(Vocabulary.slug == "test_item").statement)
    assert axis is not None
    term = VocabularyTerm(vocabulary_id=axis.id, value=value, normalized=value.lower())
    db.add(term)
    db.flush()
    db.add(
        VocabularyAlias(
            vocabulary_id=axis.id, term_id=term.id, value=alias, normalized=alias.lower()
        )
    )
    db.commit()
    return term


def test_꺼져_있으면_검색은_빈_목록이고_예외가_없다(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 개발 .env 가 ollama 로 켜져 있어도 이 시험은 「꺼짐」 을 본다.
    monkeypatch.setattr(get_settings(), "embedding_backend", "off")
    assert embeddings.enabled() is False
    assert semantic.search(db, "인장") == []
    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed_one("인장")


def test_mock_은_같은_글에_같은_단위벡터를_준다(mock_backend: None) -> None:
    one = embeddings.embed_one("열충격")
    assert one == embeddings.embed_one("열충격")
    assert len(one) == embeddings.dimension()
    assert abs(sum(x * x for x in one) - 1.0) < 1e-6


def test_카드에는_별칭과_이어진_것이_적힌다(db: Session) -> None:
    tag = uuid.uuid4().hex[:6]
    term = _test_item(db, f"고온고습-{tag}", f"HAST-{tag}")
    cards = {c.entity_id: c for c in semantic.collect(db) if c.kind == "test_item"}
    card = cards[str(term.id)]
    assert card.title == f"고온고습-{tag}"
    assert f"HAST-{tag}" in card.body  # 별칭으로도 찾히게


def test_색인하고_찾고_사라진_것은_지운다(db: Session, mock_backend: None) -> None:
    if not semantic.extension_available(db):
        pytest.skip("pgvector 가 없는 기계 — 표를 못 만든다")
    assert semantic.ensure_schema(db) is True
    db.commit()

    tag = uuid.uuid4().hex[:6]
    term = _test_item(db, f"낙하-{tag}", f"drop-{tag}")
    counted = semantic.reindex(db)
    assert counted["chunks"] >= 1

    # mock 은 뜻이 없다 — 카드 본문을 그대로 물으면 그 카드가 1위다.
    card = next(c for c in semantic.collect(db) if c.entity_id == str(term.id))
    found = semantic.search(db, card.body, kinds=["test_item"], limit=5)
    assert found and found[0].entity_id == str(term.id)
    assert found[0].score > 0.99

    # 가시성: 보유 장비 종류는 준 id 만 남는다(다른 종류는 그대로).
    found = semantic.search(db, card.body, visible_equipment=[], limit=5)
    assert all(m.kind != "equipment" for m in found)

    # 객체가 사라지면 다음 색인이 조각을 지운다.
    db.execute(text("DELETE FROM vocabulary_aliases WHERE term_id = :t"), {"t": term.id})
    db.execute(text("DELETE FROM vocabulary_terms WHERE id = :t"), {"t": term.id})
    db.commit()
    counted = semantic.reindex(db)
    assert counted["removed"] >= 1
    assert semantic.search(db, card.body, kinds=["test_item"], limit=5)[:1] == [] or (
        semantic.search(db, card.body, kinds=["test_item"], limit=5)[0].entity_id
        != str(term.id)
    )
