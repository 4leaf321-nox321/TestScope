"""기준정보 허브 수신 — 인수 시험 AT-01 ~ AT-15(요청서 1.2 §11)와 TestScope 쪽 약속.

허브는 모의 서버(`hub_fake.FakeHub`)로 대신한다(요청서 부록 B 5항). 타입 이름 · 속성은 시험마다
지어 만든다 — 수신 모듈이 타입명을 코드에 고정하지 않는다는 것을 시험이 함께 지킨다.

TestScope 쪽 약속:

- 받은 타입마다 온톨로지 축이 서고(`hub_<타입>`), 객체가 그 축의 값이 된다. 축은 잠긴다.
- 기계 자격이 **허브 칸만** 보내면 그 칸만 바뀐다 — 확정된 신뢰성 시험에도(사용자 결정).
- 토큰은 봉인돼 DB 에 있고 화면 · API 로 다시 안 나온다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs import handlers, kinds
from app.jobs.models import Job
from app.modules.hub import client as hub_client
from app.modules.hub import jobs as hub_jobs
from app.modules.hub import sync
from app.modules.hub.client import HubClient
from app.modules.hub.models import CoreItem, CoreRelation, CoreSyncRun, CoreSyncState
from app.modules.notifications.models import Notification
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.shared import secretbox
from tests.api.conftest import Signed
from tests.api.hub_fake import BASE, TOKEN, FakeHub


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeHub]:
    fake = FakeHub()
    monkeypatch.setattr(hub_client, "TRANSPORT", httpx.MockTransport(fake.handler))
    yield fake


def _plm(fake: FakeHub) -> dict[str, str]:
    """프로젝트 → 과제 → 개발모델(원 모델 관계) — 이름은 시험마다 새로."""
    tag = uuid.uuid4().hex[:6]
    project, task, model = f"proj_{tag}", f"task_{tag}", f"model_{tag}"
    fake.add_type(project, "프로젝트")
    fake.add_type(
        task,
        "과제",
        [
            {
                "key": "project",
                "label": "프로젝트",
                "data_type": "object_ref",
                "ref_type_slug": project,
            }
        ],
    )
    fake.add_type(
        model,
        "개발모델",
        [
            {"key": "task", "label": "과제", "data_type": "object_ref", "ref_type_slug": task},
            {
                "key": "series",
                "label": "시리즈",
                "data_type": "enum",
                "enum_options": ["X1", "X2"],
            },
        ],
        [
            {
                "slug": "derived_from",
                "label": "원 모델",
                "src": [{"slug": model, "interface": False, "types": [model]}],
                "dst": [{"slug": model, "interface": False, "types": [model]}],
            }
        ],
    )
    return {"project": project, "task": task, "model": model}


def _connect(db: Session, types: list[str]) -> None:
    conn = sync.connection(db)
    conn.base_url = BASE
    conn.token_sealed = secretbox.seal(TOKEN)
    conn.selected_types = types
    conn.catalog = {}
    conn.catalog_signature = None
    conn.catalog_changed_at = None
    db.commit()


def _run(db: Session, *, full: bool = False, token: str = TOKEN) -> CoreSyncRun:
    return sync.run(
        db,
        trigger="manual",
        full=full,
        by="시험",
        client=HubClient(BASE, token, sleep=lambda _s: None),
    )


def _item(db: Session, slug: str, key: str) -> CoreItem:
    db.expire_all()
    found = db.scalar(select(CoreItem).where(CoreItem.type_slug == slug, CoreItem.key == key))
    assert found is not None, f"{slug}:{key} 를 못 받음"
    return found


def _term(db: Session, item: CoreItem) -> VocabularyTerm:
    assert item.term_id is not None
    term = db.get(VocabularyTerm, item.term_id)
    assert term is not None
    return term


def _seed(fake: FakeHub, slugs: dict[str, str]) -> None:
    fake.put(slugs["project"], "P-1", "프로젝트 1")
    fake.put(slugs["task"], "T-1", "과제 1", properties={"project": "P-1"})
    fake.put(slugs["model"], "M-100", "SM-X100", properties={"task": "T-1", "series": "X1"})
    fake.put(slugs["model"], "M-090", "SM-X090", properties={"task": "T-1", "series": "X1"})
    fake.relate(slugs["model"], "M-100", "derived_from", "M-090", slugs["model"])


# --- AT-01 · AT-02 · AT-03 · AT-04 ---------------------------------------------------


def test_at01_인증_거부는_실패로_남고_관리자에게_알린다(
    hub: FakeHub, db: Session, admin: Signed
) -> None:
    slugs = _plm(hub)
    _connect(db, list(slugs.values()))
    record = _run(db, token="wrong-token")
    assert record.status == "failed"
    assert record.errors[0]["kind"] == "auth"
    assert record.errors[0]["status"] == 401
    told = db.scalars(
        select(Notification).where(
            Notification.kind == "hub.sync_failed",
            Notification.dedupe_key == f"hub.sync_failed:{record.id}",
        )
    ).all()
    assert told, "관리자 알림이 없다"


def test_at02_at03_카탈로그로_고르고_전량_수신_건수가_카탈로그와_같다(
    hub: FakeHub, db: Session, client: TestClient, admin: Signed
) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))

    checked = client.post("/api/hub/check", headers=admin.headers)
    assert checked.status_code == 200, checked.text
    assert checked.json()["ok"] is True
    assert {one["slug"] for one in checked.json()["types"]} >= set(slugs.values())

    record = _run(db, full=True)
    assert record.status == "ok", record.errors
    for slug in slugs.values():
        counted = record.counts[slug]
        assert counted["received"] == counted["catalog_count"] == counted["active"]

    status = client.get("/api/hub/status", headers=admin.headers).json()
    rows = {one["slug"]: one for one in status["types"]}
    model = rows[slugs["model"]]
    assert model["active"] == model["catalog_count"] == 2
    assert model["axis_slug"] == f"hub_{slugs['model']}"
    assert model["relations"] == 1
    # 참조 대상 타입부터 받았다(프로젝트 → 과제 → 개발모델).
    order = [
        call
        for call in hub.calls
        if "/relations" not in call
        and call.rstrip("/").split("/")[-1].split("?")[0] in slugs.values()
    ]
    firsts = [call.split("/core/")[1].split("?")[0] for call in order]
    assert (
        firsts.index(slugs["project"])
        < firsts.index(slugs["task"])
        < firsts.index(slugs["model"])
    )


def test_at04_두_번_받으면_두_번째는_변경_0건(
    hub: FakeHub, db: Session, admin: Signed
) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    assert _run(db, full=True).status == "ok"
    again = _run(db)
    for slug in slugs.values():
        counted = again.counts[slug]
        for key in (
            "created",
            "updated",
            "deactivated",
            "restored",
            "merged",
            "renamed",
            "absent",
        ):
            assert counted.get(key, 0) == 0, (slug, key, counted)
        assert counted.get("relations_added", 0) == 0
    full_again = _run(db, full=True)
    assert all(
        full_again.counts[slug].get("updated", 0) == 0
        and full_again.counts[slug].get("absent", 0) == 0
        for slug in slugs.values()
    )


# --- AT-05 · AT-06 -----------------------------------------------------------------


def test_at05_수정_한_건은_증분에서_한_건만(hub: FakeHub, db: Session, admin: Signed) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    _run(db, full=True)
    hub.put(
        slugs["model"], "M-100", "SM-X100 개선", properties={"task": "T-1", "series": "X2"}
    )
    record = _run(db)
    assert record.counts[slugs["model"]].get("updated") == 1
    item = _item(db, slugs["model"], "M-100")
    assert item.properties["series"] == "X2"
    term = _term(db, item)
    assert term.value == "SM-X100 개선" and term.code == "M-100"
    assert term.attributes["series"] == "X2"


def test_at06_사용_중지_삭제_숨김은_비활성_복원은_재활성(
    hub: FakeHub, db: Session, admin: Signed
) -> None:
    slugs = _plm(hub)
    model = slugs["model"]
    _seed(hub, slugs)
    hub.put(model, "M-050", "SM-X050", properties={"task": "T-1", "series": "X1"})
    hub.put(model, "M-040", "SM-X040", properties={"task": "T-1", "series": "X2"})
    _connect(db, list(slugs.values()))
    _run(db, full=True)

    hub.put(model, "M-090", status="deprecated")
    hub.put(model, "M-050", deleted=True)
    hub.put(model, "M-040", deleted=True, hidden=True)
    record = _run(db)
    assert record.counts[model].get("deactivated") == 2  # 삭제 · 숨김 — 사용 중지는 수정이다

    deprecated = _item(db, model, "M-090")
    assert deprecated.status == "deprecated" and not deprecated.deleted
    assert _term(db, deprecated).status == "deprecated"
    gone = _item(db, model, "M-050")
    assert gone.deleted and _term(db, gone).status == "deprecated"
    hidden = _item(db, model, "M-040")
    assert hidden.deleted and hidden.hidden
    # 숨김은 지운 것이 아니다 — 가진 값을 둔다.
    assert hidden.properties == {"task": "T-1", "series": "X2"}
    assert _term(db, hidden).attributes.get("series") == "X2"

    hub.put(
        model, "M-050", "SM-X050", deleted=False, properties={"task": "T-1", "series": "X1"}
    )
    restored = _run(db)
    assert restored.counts[model].get("restored") == 1
    back = _item(db, model, "M-050")
    assert not back.deleted and _term(db, back).status == "active"
    # 물리 삭제는 없다.
    assert db.scalar(
        select(CoreItem).where(CoreItem.type_slug == model, CoreItem.key == "M-040")
    )


# --- AT-07 · AT-08 -----------------------------------------------------------------


def _hub_field(client: TestClient, admin: Signed, db: Session, model_slug: str) -> str:
    axis = db.scalar(select(Vocabulary).where(Vocabulary.hub_type_slug == model_slug))
    assert axis is not None
    made = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"대상 개발모델 {model_slug}",
            "kind": "term",
            "vocabulary_id": str(axis.id),
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _reliability(client: TestClient, admin: Signed, attributes: list[dict[str, Any]]) -> str:
    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"허브 시험 항목-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert item.status_code == 201, item.text
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "mx",
            "name": f"허브 연결 시험-{uuid.uuid4().hex[:6]}",
            "test_item_term_ids": [item.json()["id"]],
            "attributes": attributes,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _values(client: TestClient, admin: Signed, test_id: str) -> list[dict[str, Any]]:
    got: list[dict[str, Any]] = client.get(
        f"/api/reliability-tests/{test_id}", headers=admin.headers
    ).json()["attributes"]
    return got


def test_at07_병합은_참조를_옮기고_원_객체의_관계를_해제한다(
    hub: FakeHub, db: Session, client: TestClient, admin: Signed
) -> None:
    slugs = _plm(hub)
    model = slugs["model"]
    _seed(hub, slugs)
    hub.put(model, "M-080", "SM-X080", properties={"task": "T-1"})
    hub.relate(model, "M-090", "derived_from", "M-080", model)
    _connect(db, list(slugs.values()))
    _run(db, full=True)

    field = _hub_field(client, admin, db, model)
    old = _term(db, _item(db, model, "M-090"))
    test_id = _reliability(client, admin, [{"definition_id": field, "term_id": str(old.id)}])

    hub.put(model, "M-090", deleted=True, status="deprecated", merged_into="M-100")
    hub.relate(model, "M-100", "derived_from", "M-080", model)
    record = _run(db)
    assert record.counts[model].get("merged") == 1

    target = _term(db, _item(db, model, "M-100"))
    linked = [one for one in _values(client, admin, test_id) if one["definition_id"] == field]
    assert [one["term_id"] for one in linked] == [str(target.id)]
    db.expire_all()
    rels = {
        (row.src_key, row.dst_key): row.deleted
        for row in db.scalars(select(CoreRelation).where(CoreRelation.type_slug == model))
    }
    assert rels[("M-090", "M-080")] is True  # 원 객체의 관계는 해제
    assert rels[("M-100", "M-090")] is True  # 원 객체를 끝으로 하던 관계도
    assert rels[("M-100", "M-080")] is False  # 통합 대상의 관계는 반영


def test_at08_식별자를_두_번_바꿔도_객체는_하나이고_옛_식별자가_풀린다(
    hub: FakeHub, db: Session, client: TestClient, admin: Signed
) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    _run(db, full=True)
    before = _item(db, slugs["task"], "T-1")
    term_id = before.term_id

    hub.rename(slugs["task"], "T-1", "T-1B")
    hub.rename(slugs["task"], "T-1B", "T-1C")
    record = _run(db)
    assert record.counts[slugs["task"]].get("renamed") == 1
    assert record.counts[slugs["task"]].get("created", 0) == 0

    db.expire_all()
    rows = list(db.scalars(select(CoreItem).where(CoreItem.type_slug == slugs["task"])))
    assert [row.key for row in rows] == ["T-1C"]
    assert set(rows[0].previous_keys) >= {"T-1", "T-1B"}
    term = _term(db, rows[0])
    assert term.id == term_id and term.code == "T-1C"
    aliases = set(
        db.scalars(select(VocabularyAlias.value).where(VocabularyAlias.term_id == term.id))
    )
    assert {"T-1", "T-1B"} <= aliases

    # 개발모델의 참조 값은 발신 시점 식별자(T-1) 그대로다 — 옛 식별자로도 풀린다.
    detail = client.get(
        f"/api/hub/types/{slugs['model']}/items/M-100", headers=admin.headers
    ).json()
    assert detail["properties"]["task"] == "T-1"
    assert detail["references"]["T-1"] == "과제 1"


# --- AT-09 · AT-10 · AT-11 · AT-12 -------------------------------------------------


def test_at09_관계_추가_해제와_도착_타입별_구분(
    hub: FakeHub, db: Session, admin: Signed
) -> None:
    slugs = _plm(hub)
    model, task = slugs["model"], slugs["task"]
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    _run(db, full=True)
    # 끝이 인터페이스인 관계 — 같은 도착 식별자가 다른 타입에 있다.
    hub.relate(model, "M-100", "derived_from", "SAME", model)
    hub.relate(model, "M-100", "derived_from", "SAME", task)
    hub.relate(model, "M-100", "derived_from", "M-090", model, deleted=True)
    record = _run(db)
    assert record.counts[model].get("relations_added") == 2
    assert record.counts[model].get("relations_removed") == 1
    db.expire_all()
    same = list(
        db.scalars(
            select(CoreRelation).where(
                CoreRelation.type_slug == model, CoreRelation.dst_key == "SAME"
            )
        )
    )
    assert sorted(row.dst_type for row in same) == sorted([model, task])


def test_at10_초기화_신호면_전량_다시_받고_없는_관계를_해제한다(
    hub: FakeHub, db: Session, admin: Signed
) -> None:
    slugs = _plm(hub)
    model = slugs["model"]
    _seed(hub, slugs)
    hub.put(model, "M-080", "SM-X080")
    hub.relate(model, "M-090", "derived_from", "M-080", model)
    _connect(db, list(slugs.values()))
    _run(db, full=True)
    # 허브가 해제 기록을 잃었다(보관 기한 90일 초과) — 관계 하나가 사라졌는데 해제 행이 없다.
    hub.relations[model] = [r for r in hub.relations[model] if r["src"] != "M-090"]
    hub.reset_before = "9999"
    record = _run(db)
    assert record.counts[model].get("reset") == 1
    assert record.counts[model].get("relations_removed") == 1
    db.expire_all()
    gone = db.scalar(
        select(CoreRelation).where(
            CoreRelation.type_slug == model, CoreRelation.src_key == "M-090"
        )
    )
    assert gone is not None and gone.deleted


def test_at11_쪽_크기_2_로도_전부_받는다(
    hub: FakeHub, db: Session, admin: Signed, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hub_client, "PAGE_SIZE", 2)
    slugs = _plm(hub)
    model = slugs["model"]
    for n in range(7):
        hub.put(model, f"M-{n:03d}", f"모델 {n}")
    _connect(db, [model])
    record = _run(db, full=True)
    assert record.counts[model]["received"] == record.counts[model]["catalog_count"] == 7
    pages = [call for call in hub.calls if f"/core/{model}?" in call]
    assert len(pages) == 4


def test_at12_중단되면_기준_시각을_안_옮기고_다시_받으면_빠짐_없다(
    hub: FakeHub, db: Session, admin: Signed, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hub_client, "PAGE_SIZE", 2)
    slugs = _plm(hub)
    model = slugs["model"]
    for n in range(5):
        hub.put(model, f"M-{n:03d}", f"모델 {n}")
    _connect(db, [model])
    hub.fail_page[model] = 2
    broken = _run(db, full=True)
    assert broken.status in ("failed", "partial")
    db.expire_all()
    state = db.scalar(
        select(CoreSyncState).where(
            CoreSyncState.type_slug == model, CoreSyncState.kind == "rows"
        )
    )
    assert state is not None and state.as_of is None  # 다 못 받았다 — 기준 시각 그대로
    # 타입 단위 롤백 — 반쯤 받은 것이 남지 않는다.
    assert not db.scalars(select(CoreItem).where(CoreItem.type_slug == model)).all()

    hub.fail_page.clear()
    hub.bad_cursor_once.add(model)  # 커서 해석 불가도 한 번 — 처음부터 다시
    ok = _run(db, full=True)
    assert ok.status == "ok", ok.errors
    keys = sorted(db.scalars(select(CoreItem.key).where(CoreItem.type_slug == model)))
    assert keys == [f"M-{n:03d}" for n in range(5)]


# --- AT-13 · AT-14 · AT-15 ---------------------------------------------------------


def test_at13_속성이_늘어도_무중단이고_구조_변경만_알린다(
    hub: FakeHub, db: Session, admin: Signed
) -> None:
    slugs = _plm(hub)
    model = slugs["model"]
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    _run(db, full=True)

    def changes() -> int:
        return len(
            db.scalars(
                select(Notification).where(Notification.kind == "hub.catalog_changed")
            ).all()
        )

    before = changes()
    hub.revision += 1  # 판만 바뀜 — 구조는 그대로
    _run(db)
    assert changes() == before

    hub.types[model]["properties"].append(
        {"key": "launch", "label": "출시일", "data_type": "date"}
    )
    hub.put(
        model, "M-100", "SM-X100", properties={"task": "T-1", "launch": "2027-01-01", "x": 1}
    )
    record = _run(db)
    assert record.status == "ok"
    assert changes() > before
    assert _item(db, model, "M-100").properties["launch"] == "2027-01-01"


def test_at14_받은_축은_잠겨_있다(
    hub: FakeHub, db: Session, client: TestClient, admin: Signed
) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    _run(db, full=True)
    axis = f"hub_{slugs['model']}"
    added = client.post(
        f"/api/vocabularies/{axis}/terms",
        json={"value": "몰래 넣은 모델"},
        headers=admin.headers,
    )
    assert added.status_code == 409
    assert added.json()["error"]["code"] == "TSC-VOCAB-0020"
    term = _term(db, _item(db, slugs["model"], "M-100"))
    renamed = client.patch(
        f"/api/vocabularies/terms/{term.id}",
        json={"value": "바꾼 이름"},
        headers=admin.headers,
    )
    assert renamed.status_code == 409
    axes = {
        one["slug"]: one
        for one in client.get("/api/vocabularies", headers=admin.headers).json()
    }
    assert axes[axis]["hub_type_slug"] == slugs["model"]
    assert axes[axis]["domain"] == "hub"


def test_at15_수동_실행과_이력(
    hub: FakeHub, db: Session, client: TestClient, admin: Signed
) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    queued = client.post("/api/hub/run", json={"full": True}, headers=admin.headers)
    assert queued.status_code == 202, queued.text
    again = client.post("/api/hub/run", json={}, headers=admin.headers)
    assert again.status_code == 409  # 동시 실행 방지
    job = db.get(Job, uuid.UUID(queued.json()["job_id"]))
    assert job is not None and job.payload["full"] is True
    handlers.load_all()
    handlers.get(kinds.HUB_SYNC)(db, job.payload)
    db.delete(job)
    db.commit()

    history = client.get("/api/hub/runs", headers=admin.headers).json()
    latest = history[0]
    assert latest["trigger"] == "manual" and latest["status"] == "ok"
    assert latest["counts"][slugs["model"]]["received"] == 2
    assert latest["request_ids"]


# --- TestScope 쪽 약속 ---------------------------------------------------------------


def test_토큰은_봉인돼_있고_다시_안_나온다(
    db: Session, client: TestClient, admin: Signed
) -> None:
    saved = client.put(
        "/api/hub/connection",
        json={
            "base_url": BASE,
            "token": "secret-plain-token",
            "nightly_at": "01:00",
            "enabled": True,
        },
        headers=admin.headers,
    )
    assert saved.status_code == 200, saved.text
    assert "secret-plain-token" not in saved.text
    assert saved.json()["has_token"] and saved.json()["token_readable"]
    db.expire_all()
    conn = sync.connection(db)
    assert conn.token_sealed.startswith("dpapi:v1:")
    assert "secret-plain-token" not in conn.token_sealed
    assert secretbox.unseal(conn.token_sealed) == "secret-plain-token"
    # 토큰 없이 다시 저장해도 토큰은 그대로다.
    client.put(
        "/api/hub/connection",
        json={"base_url": BASE, "nightly_at": "02:30", "enabled": True},
        headers=admin.headers,
    )
    db.expire_all()
    assert secretbox.unseal(sync.connection(db).token_sealed) == "secret-plain-token"
    conn = sync.connection(db)
    conn.enabled = False
    db.commit()


def test_야간_시각이_지나면_하루_한_번_넣는다(db: Session) -> None:
    conn = sync.connection(db)
    conn.base_url, conn.token_sealed, conn.enabled, conn.nightly_at = BASE, "x", True, "01:00"
    db.commit()
    for job in db.scalars(select(Job).where(Job.kind == kinds.HUB_SYNC)):
        db.delete(job)
    db.commit()
    # KST 01:10 = UTC 16:10(전날).
    at = datetime(2026, 10, 20, 16, 10, tzinfo=UTC)
    assert hub_jobs.enqueue_nightly(db, at) is True
    db.commit()
    assert hub_jobs.enqueue_nightly(db, at) is False  # 같은 밤에 두 번은 안 넣는다
    # **넣은 작업을 치운다** — 남기면 작업 큐 시험이 그것을 집어 간다.
    for job in db.scalars(select(Job).where(Job.kind == kinds.HUB_SYNC)):
        db.delete(job)
    conn.enabled = False
    db.commit()


def test_기계_자격은_확정된_시험에_허브_칸만_붙인다(
    hub: FakeHub, db: Session, client: TestClient, admin: Signed
) -> None:
    slugs = _plm(hub)
    _seed(hub, slugs)
    _connect(db, list(slugs.values()))
    _run(db, full=True)
    field = _hub_field(client, admin, db, slugs["model"])
    purpose = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=admin.headers,
    ).json()
    text_field = next(one for one in purpose if one["kind"] == "text")
    test_id = _reliability(
        client, admin, [{"definition_id": text_field["id"], "text_value": "원래 값"}]
    )
    detail = client.get(f"/api/reliability-tests/{test_id}", headers=admin.headers).json()
    assert detail["status"] == "confirmed"

    made = client.post(
        "/api/auth/tokens",
        json={
            "name": f"MCP-허브-{uuid.uuid4().hex[:6]}",
            "scopes": ["read", "equipment:write"],
        },
        headers=admin.headers,
    )
    machine = {"Authorization": f"Bearer {made.json()['token']}", "X-Client": "mcp"}
    target = _term(db, _item(db, slugs["model"], "M-100"))
    linked = client.patch(
        f"/api/reliability-tests/{test_id}",
        json={"attributes": [{"definition_id": field, "term_id": str(target.id)}]},
        headers=machine,
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["status"] == "confirmed"
    values = {one["definition_id"]: one for one in _values(client, admin, test_id)}
    assert values[field]["term_id"] == str(target.id)
    assert values[text_field["id"]]["text_value"] == "원래 값"  # 다른 값은 그대로

    # 허브 칸이 아닌 것을 섞으면 보통의 규칙 — 확정된 시험은 기계 자격으로 못 고친다.
    refused = client.patch(
        f"/api/reliability-tests/{test_id}",
        json={"attributes": [{"definition_id": text_field["id"], "text_value": "바꿈"}]},
        headers=machine,
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "TSC-RELIABILITY-0005"
