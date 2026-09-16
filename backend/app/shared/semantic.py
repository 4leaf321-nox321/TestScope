"""의미 검색 — **낱말이 안 겹쳐도 뜻이 가까우면 찾는다.**

    「HAST」            →  시험 항목 「고온고습」
    「thermal shock」   →  「열충격」 · 열충격 챔버 계열
    「얇은 판 잡아당기는 규격」 →  ISO 6892 · ASTM E8

## 카드 단위로 건다

ReportArchive 는 긴 보고서를 조각으로 잘랐지만, 여기 데이터는 짧은 구조화 객체다.
**객체 하나 = 카드 한 장**으로 렌더링해 임베딩한다 — 시험 항목·물성·계열·기종·규격·
보유 장비·신뢰성 시험. 카드에는 이름만이 아니라 별칭·소개·이어진 것들(시험 항목이 내는
물성, 계열이 하는 시험, 규격의 제목)을 함께 적는다 — 「HAST」 가 카드 어디에도 없으면
못 찾지만, 「고온고습(85 °C/85 %) · 별칭 HAST · 물성 —」 이면 찾는다.

## 표는 마이그레이션이 아니라 여기가 만든다

**pgvector 는 선택 부품이다.** 마이그레이션에 `CREATE EXTENSION vector` 를 넣으면
확장을 아직 안 넣은 서버에서 **배포가 통째로 실패한다** — 검색의 곁가지 때문에
릴리스가 못 나가는 것은 균형이 안 맞는다.

그래서 `ensure_schema()` 가 **있으면 만들고 없으면 조용히 넘어간다.** 배포는 이것을
매번 부르므로(`scripts/ensure_semantic_schema.py`), 나중에 pgvector 를 설치하면 그다음
배포에서 저절로 생긴다.

`Base.metadata` 에 안 올리는 이유도 같다 — 올리면 autogenerate 가 확장 없는 기계에서
**이 표를 지우는 마이그레이션**을 만든다(AGENTS.md 의 all_models 함정과 같은 뿌리).
대신 `migrations/env.py` 가 이 표를 자동 생성 대상에서 뺀다. 시험 DB 에도 표가 없으므로
**시험은 mock 임베딩으로 `ensure_schema` 를 직접 부른다**(pgvector 가 없는 CI 는 건너뛴다).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.shared import embeddings
from app.shared.attribute_text import display_attribute

logger = logging.getLogger(__name__)

TABLE = "search_chunks"

#: 카드가 이보다 길면 조각낸다(계열 소개가 긴 경우). 문단 하나쯤이다.
CHUNK_CHARS = 600
CHUNK_OVERLAP = 80

#: 한 번의 검색에서 볼 조각 수.
SEARCH_LIMIT = 40

#: 카드를 만드는 종류. 화면·MCP 가 거르는 이름과 같다.
KINDS = (
    "test_item",
    "property",
    "series",
    "model",
    "method",
    "equipment",
    "reliability_test",
)

#: 카드에 이어진 것을 몇 개까지 적나. 계열 하나가 규격 40개를 인용하면 그것을 다 적어도
#: 벡터 하나에 담기지 않는다 — 앞의 것만 적고 「외 N」 으로 닫는다.
LIST_CAP = 12


@dataclass(frozen=True)
class Chunk:
    """색인할 조각 하나."""

    kind: str
    entity_id: str
    seq: int
    title: str
    body: str


@dataclass(frozen=True)
class Match:
    """찾은 조각 하나."""

    kind: str
    entity_id: str
    title: str
    snippet: str
    score: float
    """0~1. 코사인 거리를 뒤집은 것이다."""


# --- 표 -------------------------------------------------------------------------


def extension_ready(db: Session) -> bool:
    """pgvector 가 이 DB 에 켜져 있나."""
    found = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
    return bool(found)


def extension_available(db: Session) -> bool:
    """파일은 있나(켜지지는 않았어도)."""
    found = db.execute(
        text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar()
    return bool(found)


def table_ready(db: Session) -> bool:
    return db.execute(text(f"SELECT to_regclass('{TABLE}')")).scalar() is not None


def available(db: Session) -> bool:
    """의미 검색을 쓸 수 있나 — **셋이 다 있어야 한다.**

    엔진(임베딩) · 확장(pgvector) · 표. 하나라도 없으면 검색은 이름·별칭으로만 돈다.
    """
    return embeddings.enabled() and table_ready(db)


def ensure_schema(db: Session) -> bool:
    """표와 색인을 만든다. **확장이 없으면 아무것도 안 하고 False 를 준다.**

    멱등이다. 배포가 매번 불러도 되고, 나중에 pgvector 를 설치하면 그다음 배포에서
    생긴다.
    """
    if not extension_ready(db):
        if not extension_available(db):
            logger.info("pgvector 가 없습니다 — 의미 검색 표를 만들지 않습니다.")
            return False
        # 파일은 있는데 안 켜져 있으면 켠다 — 이 자리가 그 한 번을 대신한다.
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector 를 켰습니다.")

    dim = get_settings().embedding_dim
    db.execute(
        text(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            id uuid PRIMARY KEY,
            kind varchar(40) NOT NULL,
            entity_id varchar(80) NOT NULL,
            seq integer NOT NULL,
            title varchar(300) NOT NULL DEFAULT '',
            body text NOT NULL,
            embedding vector({dim}) NOT NULL,
            model varchar(80) NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (kind, entity_id, seq)
        )
        """)
    )
    db.execute(
        text(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_entity ON {TABLE} (kind, entity_id)")
    )
    # HNSW — 조각이 늘어도 검색 시간이 거의 안 는다(MatNexus 실측: 5,000개 x 1024차원에 1.4ms).
    db.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_embedding ON {TABLE} "
            f"USING hnsw (embedding vector_cosine_ops)"
        )
    )
    return True


# --- 카드 -----------------------------------------------------------------------


def split(body: str) -> list[str]:
    """긴 글을 조각으로. **문장 경계를 먼저 본다** — 문장 가운데를 자르면 뜻이 상한다."""
    clean = " ".join((body or "").split())
    if not clean:
        return []
    if len(clean) <= CHUNK_CHARS:
        return [clean]

    made: list[str] = []
    at = 0
    while at < len(clean):
        end = min(at + CHUNK_CHARS, len(clean))
        if end < len(clean):
            window = clean.rfind(". ", at + CHUNK_CHARS // 2, end)
            if window == -1:
                window = clean.rfind(" ", at + CHUNK_CHARS // 2, end)
            if window != -1:
                end = window + 1
        made.append(clean[at:end].strip())
        if end >= len(clean):
            break
        at = max(end - CHUNK_OVERLAP, at + 1)
    return [one for one in made if one]


def _listed(label: str, items: list[str]) -> str:
    """「규격: ISO 6892-1 · ASTM E8 외 3」 — 비면 아무것도 안 적는다."""
    cleaned = [one for one in items if one]
    if not cleaned:
        return ""
    shown = " · ".join(cleaned[:LIST_CAP])
    rest = len(cleaned) - LIST_CAP
    return f"{label}: {shown}" + (f" 외 {rest}" if rest > 0 else "")


def _card(title: str, lines: list[str]) -> str:
    """카드 본문. 첫 줄이 이름이고, 빈 줄은 빼서 벡터가 이름에 쏠리지 않게 한다."""
    return "\n".join([title, *[one for one in lines if one]])


def _terms(db: Session, slug: str) -> list[tuple[str, str, str | None]]:
    return [
        (str(term_id), value, code)
        for term_id, value, code in db.execute(
            text("""
            SELECT t.id, t.value, t.code FROM vocabulary_terms t
            JOIN vocabularies v ON v.id = t.vocabulary_id
            WHERE v.slug = :slug AND t.status = 'active'
            ORDER BY t.value
            """),
            {"slug": slug},
        ).all()
    ]


def _aliases(db: Session, slug: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for term_id, alias in db.execute(
        text("""
        SELECT a.term_id, a.value FROM vocabulary_aliases a
        JOIN vocabularies v ON v.id = a.vocabulary_id
        WHERE v.slug = :slug AND a.is_active ORDER BY a.value
        """),
        {"slug": slug},
    ).all():
        out[str(term_id)].append(alias)
    return out


def _grouped(db: Session, sql: str, **params: Any) -> dict[str, list[str]]:
    """(키, 값) 두 열을 키별 목록으로. 카드가 이어진 것을 적는 데 쓴다."""
    out: dict[str, list[str]] = defaultdict(list)
    for key, value in db.execute(text(sql), params).all():
        if value:
            out[str(key)].append(str(value))
    return out


def _test_item_cards(db: Session) -> list[Chunk]:
    aliases = _aliases(db, "test_item")
    properties = _grouped(
        db,
        """
        SELECT l.test_item_term_id, p.value FROM test_item_properties l
        JOIN vocabulary_terms p ON p.id = l.property_term_id
        ORDER BY l.status DESC, p.value
        """,
    )
    axes = _grouped(
        db,
        """
        SELECT k.test_item_term_id, c.label FROM test_item_condition_keys k
        JOIN condition_keys c ON c.id = k.condition_key_id ORDER BY c.sort_order
        """,
    )
    methods = _grouped(
        db,
        """
        SELECT test_item_term_id, code || CASE WHEN title <> code THEN ' ' || title ELSE '' END
        FROM test_methods WHERE deleted_at IS NULL AND test_item_term_id IS NOT NULL
        ORDER BY code
        """,
    )
    made: list[Chunk] = []
    for term_id, value, code in _terms(db, "test_item"):
        body = _card(
            f"시험 항목: {value}",
            [
                _listed("별칭", aliases.get(term_id, [])),
                f"코드: {code}" if code else "",
                _listed("얻는 물성", properties.get(term_id, [])),
                _listed("검색 조건", axes.get(term_id, [])),
                _listed("규격", methods.get(term_id, [])),
            ],
        )
        made.append(Chunk("test_item", term_id, 0, value, body))
    return made


def _property_cards(db: Session) -> list[Chunk]:
    aliases = _aliases(db, "property")
    tests = _grouped(
        db,
        """
        SELECT l.property_term_id, t.value FROM test_item_properties l
        JOIN vocabulary_terms t ON t.id = l.test_item_term_id ORDER BY t.value
        """,
    )
    made: list[Chunk] = []
    for term_id, value, code in _terms(db, "property"):
        body = _card(
            f"물성: {value}",
            [
                _listed("별칭", aliases.get(term_id, [])),
                f"코드: {code}" if code else "",
                _listed("얻는 시험", tests.get(term_id, [])),
            ],
        )
        made.append(Chunk("property", term_id, 0, value, body))
    return made


def _series_cards(db: Session) -> list[Chunk]:
    tests = _grouped(
        db,
        """
        SELECT s.series_id, t.value FROM series_test_items s
        JOIN vocabulary_terms t ON t.id = s.test_item_term_id ORDER BY t.value
        """,
    )
    standards = _grouped(
        db,
        """
        SELECT s.series_id, m.code FROM series_test_items s
        JOIN series_test_item_methods sm ON sm.series_test_item_id = s.id
        JOIN test_methods m ON m.id = sm.method_id AND m.deleted_at IS NULL
        ORDER BY m.code
        """,
    )
    models = _grouped(
        db,
        "SELECT series_id, name FROM equipment_models WHERE deleted_at IS NULL ORDER BY name",
    )
    rows = db.execute(
        text("""
        SELECT s.id, s.name, s.name_ko, s.summary, mk.value, ct.value
        FROM equipment_series s
        LEFT JOIN vocabulary_terms mk ON mk.id = s.maker_term_id
        LEFT JOIN vocabulary_terms ct ON ct.id = s.category_term_id
        WHERE s.deleted_at IS NULL AND s.kind = 'main'
        ORDER BY s.name
        """)
    ).all()
    made: list[Chunk] = []
    for series_id, name, name_ko, summary, maker, category in rows:
        sid = str(series_id)
        title = f"{maker} {name}" if maker else name
        body = _card(
            f"장비 계열: {title}",
            [
                f"한글 이름: {name_ko}" if name_ko else "",
                f"분류: {category}" if category else "",
                _listed("되는 시험", tests.get(sid, [])),
                _listed("인용 규격", standards.get(sid, [])),
                _listed("기종", models.get(sid, [])),
                f"소개: {summary}" if summary else "",
            ],
        )
        for seq, piece in enumerate(split(body)):
            made.append(Chunk("series", sid, seq, title, piece))
    return made


def _model_cards(db: Session) -> list[Chunk]:
    rows = db.execute(
        text("""
        SELECT m.id, m.name, m.name_ko, m.summary, m.spec_note, s.name, mk.value, ct.value
        FROM equipment_models m
        JOIN equipment_series s ON s.id = m.series_id
        LEFT JOIN vocabulary_terms mk ON mk.id = s.maker_term_id
        LEFT JOIN vocabulary_terms ct ON ct.id = s.category_term_id
        WHERE m.deleted_at IS NULL AND s.deleted_at IS NULL
        ORDER BY m.name
        """)
    ).all()
    made: list[Chunk] = []
    for model_id, name, name_ko, summary, spec_note, series, maker, category in rows:
        title = f"{maker} {name}" if maker else name
        body = _card(
            f"장비 기종: {title}",
            [
                f"한글 이름: {name_ko}" if name_ko else "",
                f"계열: {series}",
                f"분류: {category}" if category else "",
                f"소개: {summary}" if summary else "",
                f"사양 비고: {spec_note}" if spec_note else "",
            ],
        )
        for seq, piece in enumerate(split(body)):
            made.append(Chunk("model", str(model_id), seq, title, piece))
    return made


def _method_cards(db: Session) -> list[Chunk]:
    rows = db.execute(
        text("""
        SELECT m.id, m.code, m.edition, m.title, m.summary, t.value
        FROM test_methods m
        LEFT JOIN vocabulary_terms t ON t.id = m.test_item_term_id
        WHERE m.deleted_at IS NULL
        ORDER BY m.code
        """)
    ).all()
    made: list[Chunk] = []
    for method_id, code, edition, title, summary, test_item in rows:
        label = f"{code} {title}" if title and title != code else code
        body = _card(
            f"시험법·규격: {label}",
            [
                f"판: {edition}" if edition else "",
                f"시험 항목: {test_item}" if test_item else "",
                f"요약: {summary}" if summary else "",
            ],
        )
        for seq, piece in enumerate(split(body)):
            made.append(Chunk("method", str(method_id), seq, label, piece))
    return made


def _equipment_cards(db: Session) -> list[Chunk]:
    tests = _grouped(
        db,
        """
        SELECT e.equipment_id, t.value FROM equipment_test_items e
        JOIN vocabulary_terms t ON t.id = e.test_item_term_id ORDER BY t.value
        """,
    )
    rows = db.execute(
        text("""
        SELECT e.id, e.asset_no, e.name, e.maker_text, e.model_text, e.location, e.note,
               w.name, ct.value, st.value, m.name, mk.value
        FROM equipment e
        JOIN workspaces w ON w.id = e.owner_workspace_id
        LEFT JOIN vocabulary_terms ct ON ct.id = e.category_term_id
        LEFT JOIN vocabulary_terms st ON st.id = e.site_term_id
        LEFT JOIN equipment_models m ON m.id = e.model_id
        LEFT JOIN equipment_series s ON s.id = m.series_id
        LEFT JOIN vocabulary_terms mk ON mk.id = s.maker_term_id
        WHERE e.deleted_at IS NULL
        ORDER BY e.asset_no
        """)
    ).all()
    attributes = _standard_attributes(db, "equipment_id")
    made: list[Chunk] = []
    for (
        equipment_id,
        asset_no,
        name,
        maker_text,
        model_text,
        location,
        note,
        workspace,
        category,
        site,
        model_name,
        maker,
    ) in rows:
        eid = str(equipment_id)
        model_label = " ".join(
            one for one in (maker or maker_text, model_name or model_text) if one
        )
        body = _card(
            f"보유 장비: {name} ({asset_no})",
            [
                f"기종: {model_label}" if model_label else "",
                f"분류: {category}" if category else "",
                f"부서: {workspace}",
                f"위치: {site} {location}".strip() if site or location else "",
                _listed("되는 시험", tests.get(eid, [])),
                *attributes.get(eid, []),
                f"비고: {note}" if note else "",
            ],
        )
        for seq, piece in enumerate(split(body)):
            made.append(Chunk("equipment", eid, seq, f"{name} ({asset_no})", piece))
    return made


def _standard_attributes(db: Session, column: str) -> dict[str, list[str]]:
    """대상마다 **정식 속성**의 「이름: 값」 줄. 초안은 표시와 수집용이라 카드에 넣지 않는다 —
    초안이 쌓여도 검색 품질이 흔들리지 않아야 한다(attributes/models.py)."""
    assert column in ("reliability_test_id", "equipment_id")
    rows = db.execute(
        text(f"""
        SELECT v.{column}, d.label, d.kind, v.num_value, v.num_min, v.num_max,
               v.unit, v.text_value, v.bool_value, v.date_value, t.value, m.code
        FROM attribute_values v
        JOIN attribute_definitions d ON d.id = v.definition_id AND d.status = 'standard'
        LEFT JOIN vocabulary_terms t ON t.id = v.term_id
        LEFT JOIN test_methods m ON m.id = v.method_id
        WHERE v.{column} IS NOT NULL
        ORDER BY d.sort_order, d.label
        """)
    ).all()
    out: dict[str, list[str]] = {}
    for row in rows:
        shown = display_attribute(
            row[2],
            num_value=row[3],
            num_min=row[4],
            num_max=row[5],
            unit=row[6] or "",
            text_value=row[7],
            bool_value=row[8],
            date_value=row[9],
            term_value=row[10],
            method_code=row[11],
        )
        if shown:
            out.setdefault(str(row[0]), []).append(f"{row[1]}: {shown}")
    return out


def _reliability_cards(db: Session) -> list[Chunk]:
    tests = _grouped(
        db,
        """
        SELECT r.reliability_test_id, t.value FROM reliability_test_items r
        JOIN vocabulary_terms t ON t.id = r.test_item_term_id ORDER BY t.value
        """,
    )
    attributes = _standard_attributes(db, "reliability_test_id")
    rows = db.execute(
        text("""
        SELECT r.id, r.name, r.purpose, w.name FROM reliability_tests r
        JOIN workspaces w ON w.id = r.workspace_id
        WHERE r.deleted_at IS NULL ORDER BY r.name
        """)
    ).all()
    made: list[Chunk] = []
    for test_id, name, purpose, workspace in rows:
        body = _card(
            f"신뢰성 시험: {name}",
            [
                f"부서: {workspace}",
                _listed("쓰는 시험 항목", tests.get(str(test_id), [])),
                f"목적: {purpose}" if purpose else "",
                *attributes.get(str(test_id), []),
            ],
        )
        for seq, piece in enumerate(split(body)):
            made.append(Chunk("reliability_test", str(test_id), seq, name, piece))
    return made


def collect(db: Session) -> list[Chunk]:
    """색인할 카드를 전부 모은다. 종류마다 질의 몇 번 — 줄마다 세지 않는다."""
    made: list[Chunk] = []
    made.extend(_test_item_cards(db))
    made.extend(_property_cards(db))
    made.extend(_series_cards(db))
    made.extend(_model_cards(db))
    made.extend(_method_cards(db))
    made.extend(_equipment_cards(db))
    made.extend(_reliability_cards(db))
    return made


# --- 색인 -----------------------------------------------------------------------


def _to_literal(vector: list[float]) -> str:
    """pgvector 는 `'[1,2,3]'` 모양의 문자열을 받는다."""
    return "[" + ",".join(f"{one:.7g}" for one in vector) + "]"


def reindex(db: Session, *, batch: int | None = None) -> dict[str, int]:
    """카드를 전부 다시 색인한다. **모델이 바뀌면 이것을 다시 돌린다.**

    조각 단위로 갈아 끼운다 — 중간에 실패해도 이미 넣은 것은 남고, 다시 돌리면
    이어서 채운다. 사라진 객체의 조각은 끝에 지운다.
    """
    if not embeddings.enabled():
        return {"chunks": 0, "skipped": 1}
    if not ensure_schema(db):
        return {"chunks": 0, "skipped": 1}

    model = embeddings.fingerprint()
    chunks = collect(db)
    size = batch or get_settings().embedding_batch

    seen: set[tuple[str, str, int]] = set()
    written = 0
    for at in range(0, len(chunks), size):
        window = chunks[at : at + size]
        vectors = embeddings.embed([one.body for one in window])
        for one, vector in zip(window, vectors, strict=True):
            db.execute(
                text(f"""
                INSERT INTO {TABLE} (id, kind, entity_id, seq, title, body, embedding, model)
                VALUES (:id, :kind, :entity_id, :seq, :title, :body,
                        CAST(:embedding AS vector), :model)
                ON CONFLICT (kind, entity_id, seq) DO UPDATE
                SET title = EXCLUDED.title, body = EXCLUDED.body,
                    embedding = EXCLUDED.embedding, model = EXCLUDED.model,
                    updated_at = now()
                """),
                {
                    "id": str(uuid.uuid4()),
                    "kind": one.kind,
                    "entity_id": one.entity_id,
                    "seq": one.seq,
                    "title": one.title[:300],
                    "body": one.body,
                    "embedding": _to_literal(vector),
                    "model": model,
                },
            )
            seen.add((one.kind, one.entity_id, one.seq))
            written += 1
        db.commit()

    # **사라진 것을 지운다.** 계열을 지웠는데 조각이 남으면 검색 결과에 「없는 것」 이
    # 나오고, 눌러도 아무 데도 안 간다.
    removed = 0
    rows = db.execute(text(f"SELECT kind, entity_id, seq FROM {TABLE}")).all()
    stale = [one for one in rows if (one[0], one[1], one[2]) not in seen]
    for kind, entity_id, seq in stale:
        db.execute(
            text(f"DELETE FROM {TABLE} WHERE kind = :k AND entity_id = :e AND seq = :s"),
            {"k": kind, "e": entity_id, "s": seq},
        )
        removed += 1
    db.commit()
    return {"chunks": written, "removed": removed}


# --- 검색 -----------------------------------------------------------------------


def search(
    db: Session,
    query: str,
    *,
    kinds: list[str] | None = None,
    visible_equipment: list[str] | None = None,
    limit: int = SEARCH_LIMIT,
) -> list[Match]:
    """뜻이 가까운 카드들. **못 쓰면 빈 목록이다** — 예외를 던지지 않는다.

    검색은 이 기능 없이도 답해야 한다. 엔진이 죽었다고 검색 화면이 오류를 띄우면,
    사람은 검색이 고장 났다고 읽는다.

    `visible_equipment` 는 **이 사람이 볼 수 있는 보유 장비 id** — 가리는 부서의 장비가
    벡터로 새면 안 된다. None 이면 안 거른다(시스템 관리자). 다른 종류는 전사 공용이다.
    """
    if not query.strip() or not available(db):
        return []
    try:
        vector = embeddings.embed_one(query)
    except embeddings.EmbeddingError as failed:
        logger.warning("의미 검색을 건너뜁니다: %s", failed)
        return []

    clauses = ["TRUE"]
    params: dict[str, Any] = {"q": _to_literal(vector), "limit": limit}
    if kinds:
        clauses.append("kind = ANY(:kinds)")
        params["kinds"] = list(kinds)
    if visible_equipment is not None:
        clauses.append("(kind <> 'equipment' OR entity_id = ANY(:visible))")
        params["visible"] = list(visible_equipment)

    rows = db.execute(
        text(f"""
        SELECT kind, entity_id, title, body, 1 - (embedding <=> CAST(:q AS vector)) AS score
        FROM {TABLE}
        WHERE {" AND ".join(clauses)}
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :limit
        """),
        params,
    ).all()

    # 같은 객체의 조각이 여럿 걸린다 — **가장 가까운 조각 하나만** 남긴다.
    best: dict[tuple[str, str], Match] = {}
    for kind, entity_id, title, body, score in rows:
        key = (kind, entity_id)
        if key in best:
            continue
        best[key] = Match(
            kind=kind,
            entity_id=entity_id,
            title=title or "",
            snippet=(body or "")[:240],
            score=float(score),
        )
    return list(best.values())


def stats(db: Session) -> dict[str, Any]:
    """무엇이 얼마나 색인돼 있나. 화면이 「의미 검색 꺼짐」 을 말할 근거."""
    if not table_ready(db):
        return {"ready": False, "chunks": 0, "kinds": {}, "extension": extension_ready(db)}
    rows = db.execute(text(f"SELECT kind, count(*) FROM {TABLE} GROUP BY kind")).all()
    return {
        "ready": available(db),
        "extension": True,
        "chunks": sum(int(one[1]) for one in rows),
        "kinds": {one[0]: int(one[1]) for one in rows},
    }
