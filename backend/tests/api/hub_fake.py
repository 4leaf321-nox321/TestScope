"""모의 허브 — StandardPlatform 코어 API(요청서 1.2 §5)를 **규약대로** 흉내 낸다.

인수 시험(AT-01 ~ AT-15)이 이것을 상대로 돈다(요청서 부록 B 5항). 허브의 실제 코드
(`StandardPlatform/backend/app/modules/coreapi`)를 본떠 봉투 · 쪽 넘김 · 기준 시각 · 오류
코드를 맞췄다 — 이름 · 속성은 시험마다 만든다(코드에 고정하지 않는다는 요구를 시험도 지킨다).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

TOKEN = "hub-test-token"
BASE = "https://hub.test/api"


def stamp(tick: int) -> str:
    """기준 시각 — 허브와 같은 꼴(마이크로초 · Z)이라 글자 순서가 시간 순서다."""
    return f"2026-10-21T00:{tick // 60:02d}:{tick % 60:02d}.000000Z"


@dataclass
class FakeHub:
    types: dict[str, dict[str, Any]] = field(default_factory=dict)
    """slug → {label, properties, relation_kinds}."""
    objects: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    """slug → key → 지금 상태(행 봉투 그대로, updated_at 포함)."""
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    """slug → 바뀐 차례대로의 행 — 증분이 이것을 준다."""
    relations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    tick: int = 1
    revision: int = 1
    reset_before: str | None = None
    """이 시각보다 이른 since 로 관계를 물으면 reset(보관 기한 초과)."""
    fail_page: dict[str, int] = field(default_factory=dict)
    """slug → 몇 번째 쪽에서 500 을 낼지(중단 내성 시험)."""
    bad_cursor_once: set[str] = field(default_factory=set)
    closed: set[str] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)

    # ── 허브 쪽 조작 ──────────────────────────────────────────────────────────

    def add_type(
        self,
        slug: str,
        label: str,
        properties: list[dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> None:
        self.types[slug] = {
            "label": label,
            "properties": properties or [],
            "relation_kinds": relations or [],
        }
        self.objects.setdefault(slug, {})
        self.events.setdefault(slug, [])
        self.relations.setdefault(slug, [])

    def _now(self) -> str:
        self.tick += 1
        return stamp(self.tick)

    def put(self, slug: str, key: str, label: str | None = None, **row: Any) -> dict[str, Any]:
        """객체를 만들거나 고친다. `row` 는 봉투 칸(status · properties · deleted …)."""
        current = dict(self.objects[slug].get(key) or {"_oid": key})
        current.update(
            {
                "key": key,
                "label": label or current.get("label") or key,
                "status": row.pop("status", current.get("status", "active")),
                "deleted": row.pop("deleted", False),
                "properties": row.pop("properties", current.get("properties", {})),
            }
        )
        current.update(row)
        current["updated_at"] = self._now()
        if current.get("deleted"):
            current["properties"] = {}
        self.objects[slug][key] = current
        self.events[slug].append(dict(current))
        return current

    def rename(self, slug: str, old: str, new: str) -> None:
        current = self.objects[slug].pop(old)
        previous = [*current.get("previous_keys", []), old]
        current.update({"key": new, "renamed_from": old, "previous_keys": previous})
        current["updated_at"] = self._now()
        self.objects[slug][new] = current
        self.events[slug].append(dict(current))

    def relate(
        self,
        slug: str,
        src: str,
        relation: str,
        dst: str,
        dst_type: str,
        deleted: bool = False,
    ) -> None:
        self.relations[slug].append(
            {
                "src": src,
                "relation": relation,
                "dst": dst,
                "dst_type": dst_type,
                "evidence_note": "",
                "properties": {},
                "updated_at": self._now(),
                "deleted": deleted,
            }
        )

    # ── 창구 ─────────────────────────────────────────────────────────────────

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return _error(401, "APP-AUTH-0001", "인증 필요")
        path = urlparse(str(request.url)).path.rstrip("/")
        query = {k: v[0] for k, v in parse_qs(urlparse(str(request.url)).query).items()}
        parts = path.split("/")
        # /api/core · /api/core/{type} · /api/core/{type}/relations
        if parts[-1] == "core":
            return _json(self.catalog())
        if parts[-1] == "relations":
            return self._page(parts[-2], query, relations=True)
        return self._page(parts[-1], query, relations=False)

    def catalog(self) -> dict[str, Any]:
        return {
            "system": "standardplatform",
            "revision": f"{self.revision}-test",
            "as_of": stamp(self.tick),
            "types": [
                {
                    "slug": slug,
                    "label": spec["label"],
                    "description": "",
                    "count": sum(
                        1 for row in self.objects[slug].values() if not row.get("deleted")
                    ),
                    "updated_at": stamp(self.tick),
                    "endpoint": f"{BASE}/core/{slug}",
                    "relations_endpoint": f"{BASE}/core/{slug}/relations",
                    "relations": [kind["slug"] for kind in spec["relation_kinds"]],
                    "relation_kinds": spec["relation_kinds"],
                    "properties": spec["properties"],
                }
                for slug, spec in self.types.items()
                if slug not in self.closed
            ],
        }

    def _page(self, slug: str, query: dict[str, str], *, relations: bool) -> httpx.Response:
        if slug in self.closed or slug not in self.types:
            return _error(404, "APP-CORE-0001", "공개되지 않은 타입")
        limit = int(query.get("limit", "500"))
        cursor = query.get("cursor")
        since = query.get("since")
        if cursor:
            if slug in self.bad_cursor_once:
                self.bad_cursor_once.discard(slug)
                return _error(404, "APP-CORE-0002", "커서 해석 불가")
            offset, as_of = cursor.split("|", 1)
            start = int(offset)
        else:
            start, as_of = 0, stamp(self.tick)
        reset = False
        if relations:
            if since and self.reset_before and since < self.reset_before:
                reset = True
                rows: list[dict[str, Any]] = []
            elif since:
                rows = [r for r in self.relations[slug] if r["updated_at"] > since]
            else:
                live: dict[tuple[str, str, str, str], dict[str, Any]] = {}
                for r in self.relations[slug]:
                    ident = (r["src"], r["relation"], r["dst"], r["dst_type"])
                    live[ident] = r
                rows = [r for r in live.values() if not r["deleted"]]
        elif since:
            # **객체마다 마지막 상태 한 줄** — 실제 허브는 바뀐 객체를 한 번만 준다(식별자가
            # 두 번 바뀌어도 지금 식별자로 한 줄, `previous_keys` 에 옛것들).
            latest: dict[str, dict[str, Any]] = {}
            for r in self.events[slug]:
                if r["updated_at"] > since:
                    latest.pop(r["_oid"], None)
                    latest[r["_oid"]] = r
            rows = list(latest.values())
        else:
            rows = [r for r in self.objects[slug].values() if not r.get("deleted")]
        page_no = start // max(limit, 1) + 1
        if self.fail_page.get(slug) == page_no:
            return _error(500, "APP-INTERNAL", "허브 내부 오류")
        chunk = [
            {k: v for k, v in r.items() if k != "_oid"} for r in rows[start : start + limit]
        ]
        more = start + limit < len(rows)
        body: dict[str, Any] = {
            "type_slug": slug,
            "since": since,
            "as_of": None if more else as_of,
            "next": f"{start + limit}|{as_of}" if more else None,
            "items": chunk,
        }
        if relations:
            body["reset"] = reset
        return _json(body)


def _json(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "x-request-id": f"req-{id(body)}"},
    )


def _error(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(
        status,
        content=json.dumps(
            {"error": {"code": code, "message": message, "request_id": f"err-{code}"}}
        ).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
