"""반입이 시험 항목의 영문 라벨·별칭을 축 별칭으로 넣는다 — 사람도 AI 도 영문으로 묻는다.

물성은 처음부터 그랬는데 시험 항목은 없어서 96종 전부 별칭이 0 이었고, resolve 는 매번 벡터
후보로 떨어져 되물었다. 여기서 지키는 것 — 영문 라벨과 aliases 가 별칭이 된다 · 값 이름과 같은
것은 안 넣는다 · 두 번 돌려도 안 겹친다 · 사람이 화면에서 더한 별칭은 안 건드린다.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from catalog_import.terms import _term, _test_item_aliases


def _aliases_of(db: Session, term: VocabularyTerm) -> set[str]:
    return set(
        db.scalars(
            select(VocabularyAlias.value).where(
                VocabularyAlias.term_id == term.id, VocabularyAlias.is_active.is_(True)
            )
        )
    )


def test_영문_라벨과_aliases_가_별칭이_되고_두_번_돌려도_안_겹친다(db: Session) -> None:
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    assert axis is not None
    actor = db.scalar(select(User).limit(1))
    tag = uuid.uuid4().hex[:6]
    rows = [
        {
            "id": f"thermal_shock_{tag}",
            "label_ko": f"열충격-{tag}",
            "label": f"Thermal shock {tag}",
            "aliases": [
                f"TS-{tag}",
                {"alias": f"열충격-{tag}"},
            ],  # 값 이름과 같은 것은 안 들어간다
        },
        {"id": f"bare_{tag}", "label_ko": f"맨값-{tag}"},  # 영문 라벨도 별칭도 없다
    ]
    items = {
        row["id"]: _term(db, axis, row.get("label_ko") or row["id"], actor, code=row["id"])
        for row in rows
    }
    db.flush()

    added = _test_item_aliases(db, axis, rows, items)
    db.commit()
    assert added == 2
    assert _aliases_of(db, items[f"thermal_shock_{tag}"]) == {
        f"Thermal shock {tag}",
        f"TS-{tag}",
    }
    assert _aliases_of(db, items[f"bare_{tag}"]) == set()

    # 사람이 화면에서 더한 별칭은 그대로, 반입은 더하기만.
    db.add(
        VocabularyAlias(
            vocabulary_id=axis.id,
            term_id=items[f"thermal_shock_{tag}"].id,
            value=f"PCT-{tag}",
            normalized=f"pct-{tag}",
        )
    )
    db.commit()
    assert _test_item_aliases(db, axis, rows, items) == 0
    db.commit()
    assert f"PCT-{tag}" in _aliases_of(db, items[f"thermal_shock_{tag}"])
