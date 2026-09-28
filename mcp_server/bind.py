"""밖에 열 때의 판정 — **허용 Host 없이는 안 연다.**

`server.py` 가 아니라 여기 있는 이유는 `merge.py` 와 같다: 저쪽은 `mcp` 패키지를 들여오므로
시험이 그것까지 설치해야 한다. 이 판정은 문자열 몇 줄이라 떼어 두고 단위 시험으로 덮는다.

## 왜 막는가

공식 SDK 는 **듣는 자리가 localhost 일 때만** DNS rebinding 보호를 저절로 켠다
(`mcp/server/lowlevel/server.py` 의 `streamable_http_app`). 그 밖의 값이면 설정이
`None` 으로 남고, `TransportSecurityMiddleware` 는 하위 호환을 위해 **보호를 끈 채**
돈다. 즉 `MCP_HOST` 를 `0.0.0.0` 으로 바꾸는 것만으로 **지금 있던 Host·Origin 검사가
조용히 사라진다.**

실측(2026-09-28, 같은 서버에서 바인딩만 바꿈):

    MCP_HOST=127.0.0.1   Host: evil.example → 421   Origin: http://evil… → 403
    MCP_HOST=0.0.0.0     Host: evil.example → 200   Origin: http://evil… → 200

조용히 꺼지는 기본값은 두지 않는다. 밖에 열려면 허용 Host 를 **말로 적게** 한다.

## 글자 그대로 견준다

서버는 요청의 Host 헤더와 이 목록을 문자 그대로 맞춘다 — 같은 서버라도 허용에
`127.0.0.1:8022` 만 있으면 `localhost:8022` 로 들어온 요청은 421 로 거절된다.
**쓰는 사람이 등록에 적는 주소를 그대로**(포트까지) 넣어야 한다.

와일드카드는 `호스트:*`(포트 자리) 하나뿐이다 — `*.사내` 같은 것은 SDK 가 모른다.
"""

from __future__ import annotations

#: 이 셋은 밖이 아니다 — 목록 없이 열어도 된다.
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

#: localhost 로 들을 때의 기본 허용 목록. SDK 가 저절로 넣던 것과 같은 셋이다
#: (`[::1]:*` 를 빼면 IPv6 로 붙던 클라이언트가 그날부터 421 을 받는다).
LOCAL_ALLOWED = ["127.0.0.1:*", "localhost:*", "[::1]:*"]

REFUSAL = (
    "MCP_HOST={host} 로 밖에 열려면 MCP_ALLOWED_HOSTS 를 함께 주세요"
    " (backend\\.env, 쉼표로 여럿). 사람들이 등록에 적는 주소를 포트까지 그대로 적습니다"
    " — 예: MCP_ALLOWED_HOSTS=10.240.25.85:8022,127.0.0.1:8022."
    " 허용 Host 없이 열면 DNS rebinding 보호가 무의미해집니다."
)


def parse_allowed(raw: str | None) -> list[str]:
    """쉼표로 갈라 빈 칸을 버린다. `.env` 에서 온 값이라 공백이 섞인다."""
    return [one.strip() for one in (raw or "").split(",") if one.strip()]


def allowed_hosts(host: str, raw: str | None) -> list[str]:
    """이 바인딩에서 허용할 Host 목록.

    **밖에 열면서 목록이 비면 `ValueError`.** 부르는 쪽이 기동을 멈춘다 — 경고만 찍고
    뜨면 아무도 안 읽고, 보호가 없는 줄 모른 채 몇 달이 간다.
    """
    listed = parse_allowed(raw)
    if host in LOCAL_HOSTS:
        # 안에서 들어도 사람이 적어 줬으면 그것을 쓴다. 적은 것이 안 듣는 편이 더 나쁘다.
        return listed or list(LOCAL_ALLOWED)
    if not listed:
        raise ValueError(REFUSAL.format(host=host))
    return listed
