"""사람 확인 증표 — AI 화면의 확인 창에서 사람이 수락한 요청에만 서명한다(ADR 0013).

백엔드는 사람 몫의 결정(신뢰성 시험 확정 · 관리 작업 …)을 기계 자격으로 받을 때 이 증표를
본다(`backend/app/shared/confirm.py`). **서명 방식이 둘에서 같아야 한다** — 백엔드 시험
(`tests/unit/test_confirm.py`)이 이 모듈을 import 해 맞대 본다. 그래서 `mcp` 패키지를 안
들여온다(`merge.py` 와 같은 이유).

열쇠는 `JWT_SECRET` 에서 뽑는다 — 환경변수가 이기고, 없으면 `backend\\.env`, 그것도 없으면
백엔드의 개발 기본값. 백엔드가 같은 순서로 읽으므로 같은 PC 의 둘은 같은 열쇠를 갖는다.
AI 는 이 열쇠를 모르므로 증표를 못 만든다.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

HEADER = "X-Human-Confirm"
VERSION = "v1"

#: 백엔드 `app/config.py` 의 기본값. 개발 PC 의 `.env` 에는 대개 `JWT_SECRET` 이 없다 —
#: 그때 둘이 같은 기본값을 써야 증표가 맞는다(운영은 기본값이면 백엔드가 안 뜬다).
DEV_SECRET = "dev-only-insecure-secret-change-me"


def derive_key(secret: str) -> bytes:
    """`JWT_SECRET` 에서 증표 열쇠를 뽑는다. 세션 서명과 같은 열쇠를 그대로 쓰지 않는다."""
    return hmac.new(secret.encode(), b"testscope-human-confirm-v1", hashlib.sha256).digest()


def signature(
    key: bytes,
    *,
    ts: str,
    nonce: str,
    method: str,
    path: str,
    query: str,
    token: str,
    body: bytes,
) -> str:
    """요청 하나에 대한 서명. 토큰과 본문은 해시로만 싣는다(증표에 비밀이 안 남게)."""
    message = "\n".join(
        (
            VERSION,
            ts,
            nonce,
            method.upper(),
            path,
            query,
            hashlib.sha256(token.encode()).hexdigest(),
            hashlib.sha256(body).hexdigest(),
        )
    )
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def proof(
    key: bytes,
    *,
    method: str,
    path: str,
    query: str,
    token: str,
    body: bytes,
    now: float | None = None,
) -> str:
    """`X-Human-Confirm` 값 — 버전 · 시각 · 일회 값 · 서명. 2분 안에 한 번만 쓰인다."""
    ts = str(int(time.time() if now is None else now))
    nonce = secrets.token_hex(12)
    sign = signature(
        key, ts=ts, nonce=nonce, method=method, path=path, query=query, token=token, body=body
    )
    return ".".join((VERSION, ts, nonce, sign))


def load_key(env_file: Path) -> bytes:
    """백엔드와 같은 순서로 `JWT_SECRET` 을 찾아 열쇠를 만든다."""
    secret = os.environ.get("JWT_SECRET")
    if not secret and env_file.exists():
        for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip().upper() == "JWT_SECRET":
                secret = value.strip().strip('"').strip("'")
    return derive_key(secret or DEV_SECRET)
