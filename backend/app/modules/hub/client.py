"""허브 코어 API 클라이언트 — **오류를 HTTP 상태와 `error.code` 로 함께 판정한다**
(요청서 §5.8).

같은 404 라도 `APP-CORE-0001`(타입 비공개 전환)은 그 타입 수신을 멈추고, `APP-CORE-0002`(커서
해석 불가)는 커서 없이 다시 받는다 — 상태만 보면 둘을 못 가른다.

재시도 규칙:

    401 · 403            재시도 안 함 — 토큰 · 범위 문제(관리자 통지)
    404 APP-CORE-0001    타입 수신 중지
    404 APP-CORE-0002    커서 없이 재수신(부르는 쪽이 한다)
    422 APP-CORE-0003    since 형식 오류 — 저장 기준 시각 점검
    429                  잠깐 기다렸다 한 번
    5xx · 네트워크        간격을 늘려 최대 3회
    그 밖의 4xx          재시도 안 함, message · request_id 기록
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlparse

import httpx

#: 쪽 크기. 허브 기본 500, 최대 2,000.
PAGE_SIZE = 500
_TIMEOUT = 30.0
_RETRIES = 3

#: 시험이 모의 허브를 끼우는 자리. 운영에서는 비어 있다.
TRANSPORT: httpx.BaseTransport | None = None


class HubError(Exception):
    """허브가 거절했거나 닿지 못했다. `kind` 가 처리를 가른다."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        """`auth` · `type_closed` · `cursor` · `since` · `rate` · `server` · `other`."""
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "status": self.status,
            "code": self.code,
            "request_id": self.request_id,
        }


def core_base(base_url: str) -> str:
    """입력한 주소 → 코어 창구의 뿌리(`/` 로 끝남). `…/api` 도 `…/api/core` 도 받는다."""
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise HubError("other", "허브 주소가 비었음. 예: https://hub.example/api")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HubError("other", f"허브 주소 형식 오류: {base_url}")
    if not parsed.path.rstrip("/").endswith("/core"):
        base = base + "/core"
    return base + "/"


class HubClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        verify: str | bool = True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base = core_base(base_url)
        self.token = token
        self.verify = verify
        self.sleep = sleep
        self.request_ids: list[str] = []
        """받은 응답의 `request_id` — 허브 「최근 조회 이력」 과 대조한다."""

    # ── 창구 셋 ──────────────────────────────────────────────────────────────

    def catalog(self) -> dict[str, Any]:
        return self._get(self.base, None)

    def rows(
        self,
        type_slug: str,
        *,
        since: str | None,
        cursor: str | None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self._get(self.base + quote(type_slug), _params(since, cursor, limit))

    def relations(
        self,
        type_slug: str,
        *,
        since: str | None,
        cursor: str | None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self._get(
            self.base + quote(type_slug) + "/relations", _params(since, cursor, limit)
        )

    # ── 한 번 부르기 ──────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict[str, Any] | None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        rate_retried = False
        attempt = 0
        while True:
            attempt += 1
            try:
                with httpx.Client(
                    timeout=_TIMEOUT,
                    verify=self.verify,
                    transport=TRANSPORT,
                    follow_redirects=True,
                ) as client:
                    response = client.get(url, params=params, headers=headers)
            except httpx.TransportError as exc:
                if attempt <= _RETRIES:
                    self.sleep(2 ** (attempt - 1))
                    continue
                raise HubError("server", f"허브에 닿지 못함: {exc}") from exc
            request_id = response.headers.get("x-request-id")
            if response.status_code < 400:
                if request_id:
                    self.request_ids.append(request_id)
                body = response.json()
                if not isinstance(body, dict):
                    raise HubError("other", "허브 응답 형식 오류(객체가 아님).")
                return body
            error = _error_of(response)
            request_id = error.get("request_id") or request_id
            if request_id:
                self.request_ids.append(str(request_id))
            code = str(error.get("code") or "") or None
            message = str(error.get("message") or f"HTTP {response.status_code}")
            status = response.status_code
            if status == 429 and not rate_retried:
                rate_retried = True
                self.sleep(_retry_after(response))
                continue
            if status >= 500 and attempt <= _RETRIES:
                self.sleep(2 ** (attempt - 1))
                continue
            raise HubError(
                _kind(status, code), message, status=status, code=code, request_id=request_id
            )


def _params(since: str | None, cursor: str | None, limit: int | None) -> dict[str, Any]:
    # 쪽 크기는 **부를 때** 읽는다 — 기본값으로 굳히면 설정 · 시험이 바꿀 수 없다.
    params: dict[str, Any] = {"limit": limit or PAGE_SIZE}
    if since:
        params["since"] = since
    if cursor:
        # **해석하지 않는다** — 형식은 약속되지 않았다(요청서 §5.4).
        params["cursor"] = cursor
    return params


def _error_of(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error: dict[str, Any] = body["error"]
        return error
    return {}


def _retry_after(response: httpx.Response) -> float:
    raw = response.headers.get("retry-after", "")
    try:
        return min(max(float(raw), 1.0), 60.0)
    except ValueError:
        return 5.0


def _kind(status: int, code: str | None) -> str:
    if status in (401, 403):
        return "auth"
    if status == 404 and code == "APP-CORE-0001":
        return "type_closed"
    if status == 404 and code == "APP-CORE-0002":
        return "cursor"
    if status == 422 and code == "APP-CORE-0003":
        return "since"
    if status == 429:
        return "rate"
    if status >= 500:
        return "server"
    return "other"
