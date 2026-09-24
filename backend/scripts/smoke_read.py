"""읽기 스모크 — 읽기 엔드포인트 150여 개를 이 DB 로 전부 부르고 응답을 JSON 으로 남긴다.

    python scripts/smoke_read.py out.json                  지금 코드의 응답을 남긴다
    python scripts/smoke_read.py out.json --diff before.json   전에 남긴 것과 견준다

## 왜 있나

큰 파일을 가르거나 옮길 때 「정의가 같다」(AST) 와 「시험이 초록이다」 만으로는 **이어 붙인
것이 실제 데이터로 도는가**를 못 본다. 2026-09-13 에 반입 스크립트·카탈로그·온톨로지를
갈랐을 때 이 방법으로 잡은 것이 있다 — 정의는 글자 그대로였는데 `DEFAULT_ROOT` 가 패키지
안으로 한 층 들어가 저장소 뿌리를 놓쳤다.

쓰는 법: 자르기 **전** 커밋을 `git worktree` 로 꺼내 그쪽 스크립트로 `before.json` 을 만들고
(같은 DB · 그쪽에 `.env` 복사), 자른 뒤 `--diff before.json`. 다른 줄이 환경값(요청 id ·
디스크 · 버전)뿐이어야 한다.

## 어떻게 부르나

관리자 한 명으로 로그인을 대신하고(`current_user` 를 덮어씀) 목록에서 얻은 id 로 상세까지
간다. **쓰기는 안 한다** — 검색·resolve 의 POST 는 읽기다. 요청마다 다른 칸(요청 id · 시각 ·
안 읽은 수)은 빼고 남긴다.
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.all_models  # (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.main import app
from app.modules.accounts.models import User
from app.shared import auth

survive_cp949()
# 요청 150건의 httpx 줄이 결과를 덮는다 — 요약만 보이게.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

#: 요청마다 달라지는 칸. 견줄 때 빼야 진짜 차이만 남는다.
VOLATILE = {
    "started_at",
    "created_at",
    "updated_at",
    "imported_at",
    "unread",
    "read_at",
    "request_id",
    "disk",
    "version",
}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def collect() -> dict[str, tuple[int, Any]]:
    db = SessionLocal()
    admin = db.scalar(
        select(User).where(User.is_system_admin.is_(True), User.status == "active")
    )
    if admin is None:
        raise SystemExit("활성 시스템 관리자가 없습니다 — seed_install.py 를 먼저 돌리세요.")
    app.dependency_overrides[auth.current_user] = lambda: admin
    app.state.session_factory = SessionLocal
    results: dict[str, tuple[int, Any]] = {}

    with TestClient(app) as client:

        def get(path: str, **params: Any) -> Any:
            response = client.get(path, params=params)
            key = f"GET {path} {json.dumps(params, sort_keys=True) if params else ''}".strip()
            results[key] = (response.status_code, _scrub(response.json()))
            return response.json() if response.status_code == 200 else None

        def post(path: str, body: dict[str, Any]) -> Any:
            response = client.post(path, json=body)
            results[f"POST {path} {json.dumps(body, sort_keys=True)}"] = (
                response.status_code,
                _scrub(response.json()),
            )
            return response.json() if response.status_code == 200 else None

        # --- 카탈로그: 계열 --------------------------------------------------
        series = get("/api/equipment-series", limit=30) or {}
        get("/api/equipment-series", limit=30, q="인장")
        get("/api/equipment-series", limit=30, kind="main", models="none")
        get("/api/equipment-series", limit=30, test_item="none")
        get("/api/equipment-series", limit=30, owned="true")
        options = get("/api/equipment-series/filter-options") or {}
        for one in (options.get("categories") or [])[:3]:
            get("/api/equipment-series", limit=30, category_term_id=one["value"])
        for row in (series.get("items") or [])[:6]:
            get(f"/api/equipment-series/{row['id']}")

        # --- 카탈로그: 기종 --------------------------------------------------
        models = get("/api/equipment-models", limit=30) or {}
        get("/api/equipment-models", limit=30, q="HM")
        get("/api/equipment-models", limit=30, spec="none")
        get("/api/equipment-models", limit=30, owned="true", spec="none")
        get("/api/equipment-models", limit=30, spec="uncertain")
        model_options = get("/api/equipment-models/filter-options") or {}
        for one in (model_options.get("categories") or [])[:3]:
            get("/api/equipment-models", limit=30, category_term_id=one["value"])
        for row in (models.get("items") or [])[:6]:
            get(f"/api/equipment-models/{row['id']}")
            get(f"/api/equipment-models/{row['id']}/specs")

        # --- 보유 장비 --------------------------------------------------------
        equipment = get("/api/equipment", limit=30) or {}
        get("/api/equipment/filter-options")
        get("/api/equipment", limit=30, catalog="unlinked")
        get("/api/equipment", limit=30, test_item="none")
        for row in (equipment.get("items") or [])[:4]:
            get(f"/api/equipment/{row['id']}")
            get(f"/api/equipment/{row['id']}/specs")
            get(f"/api/equipment/{row['id']}/calibrations")
            get("/api/equipment-test-items", equipment_id=row["id"])

        # --- 온톨로지 ---------------------------------------------------------
        for axis in get("/api/vocabularies") or []:
            terms = get(f"/api/vocabularies/{axis['slug']}/terms") or []
            for term in terms[:2]:
                get(f"/api/vocabularies/terms/{term['id']}/references")
        get("/api/condition-keys")
        get("/api/condition-keys", include_inactive="true")
        get("/api/spec-groups")
        get("/api/spec-definitions")
        for one in (options.get("categories") or [])[:2]:
            get("/api/spec-definitions", category_term_id=one["value"])
        get("/api/spec-sources")

        # --- 시험 항목 · 규격 · 물성 ------------------------------------------
        items = get("/api/test-items") or []
        for row in items[:8]:
            get(f"/api/test-items/{row['id']}")
        get("/api/test-items", gap="axes")
        methods = get("/api/methods", limit=30) or {}
        get("/api/methods", limit=30, test_item="none")
        get("/api/methods", limit=30, requirement="none", cited="none")
        for row in (methods.get("items") or [])[:4]:
            get(f"/api/methods/{row['id']}")
            get(f"/api/search/method-conditions/{row['id']}")
        get("/api/properties")
        get("/api/test-item-properties")

        # --- 서버 · 부서 · 감사 -----------------------------------------------
        get("/api/server/status")
        get("/api/server/maintenance")
        get("/api/server/catalog")
        get("/api/server/calibrations-due")
        get("/api/workspaces")
        get("/api/workspaces/options")
        get("/api/audit/entries", limit=20)

        # --- 검색 — 이 시스템이 존재하는 이유 ---------------------------------
        keys = {one["key"]: one["id"] for one in (get("/api/condition-keys") or [])}
        picked = items[:6]
        tensile = next((one for one in items if one.get("code") == "tensile"), None)
        if tensile is not None and tensile not in picked:
            picked.append(tensile)
        for item in picked:
            post("/api/search/test-items", {"test_item_term_id": item["id"], "conditions": []})
            post("/api/search/catalog", {"test_item_term_id": item["id"], "conditions": []})
            if "force" in keys and "temperature" in keys:
                body = {
                    "test_item_term_id": item["id"],
                    "conditions": [
                        {"condition_key_id": keys["force"], "at_least": 50},
                        {"condition_key_id": keys["temperature"], "at": 80},
                    ],
                }
                post("/api/search/test-items", body)
                post("/api/search/catalog", body)
        post("/api/resolve", {"kind": "series", "text": "6800"})
        post("/api/resolve", {"kind": "term", "axis": "equipment_category", "text": "만능"})

    db.close()
    return results


def diff(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """다른 요청의 키만. 본문이 다르면 어느 칸이 다른지 첫 하나를 함께."""
    lines: list[str] = []
    for key in sorted(set(before) | set(after)):
        if key not in before:
            lines.append(f"+ {key}")
        elif key not in after:
            lines.append(f"- {key}")
        elif before[key] != after[key]:
            lines.append(f"≠ {key}: {_first_difference(before[key], after[key])}")
    return lines


def _first_difference(left: Any, right: Any, path: str = "") -> str:
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                return _first_difference(left.get(key), right.get(key), f"{path}.{key}")
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"{path} 길이 {len(left)} → {len(right)}"
        for index, (one, other) in enumerate(zip(left, right, strict=True)):
            if one != other:
                return _first_difference(one, other, f"{path}[{index}]")
    shown_left = json.dumps(left, ensure_ascii=False)[:60]
    shown_right = json.dumps(right, ensure_ascii=False)[:60]
    return f"{path} {shown_left} → {shown_right}"


def main() -> int:
    parser = argparse.ArgumentParser(description="읽기 엔드포인트를 전부 불러 응답을 남긴다")
    parser.add_argument("out", type=Path)
    parser.add_argument("--diff", type=Path, help="전에 남긴 JSON 과 견준다")
    args = parser.parse_args()

    results = collect()
    args.out.write_text(
        json.dumps(results, ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8"
    )
    codes = collections.Counter(code for code, _ in results.values())
    print(f"요청 {len(results)}건 · 상태 {dict(sorted(codes.items()))} → {args.out}")
    if any(code >= 400 for code in codes):
        for key, (code, _) in results.items():
            if code >= 400:
                print(f"  {code} {key}")

    if args.diff:
        before = json.loads(args.diff.read_text(encoding="utf-8"))
        after = json.loads(args.out.read_text(encoding="utf-8"))
        # JSON 을 거친 뒤라 튜플이 리스트다 — 같은 모양으로 견준다.
        lines = diff(before, after)
        if lines:
            print(f"\n다른 요청 {len(lines)}건:")
            for line in lines:
                print("  " + line)
            return 1
        print("\n전과 같습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
