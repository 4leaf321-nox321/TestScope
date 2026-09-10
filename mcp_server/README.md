# TestScope MCP 서버

AI 가 TestScope 에 **직접 묻고, 카탈로그를 채운다.**

```powershell
cd mcp_server
.\run_mcp.ps1            # HTTP — http://127.0.0.1:8030/mcp
.\run_mcp.ps1 -Stdio     # 개인 연결
```

가상환경이 없으면 만들고 의존성까지 넣는다. **`backend\.venv` 와 섞지 않는다** —
MCP SDK 가 언제든 프레임워크 판을 올릴 수 있고, 그때 앱이 인질이 되면 안 된다.

백엔드 주소는 `backend\.env` 의 `PORT` 를 읽어 스스로 맞춘다. 다르면
`-ApiBase 'http://…/api'` 로 직접 준다.

## 자격

**이 서버는 권한을 판정하지 않는다.** 받은 `Authorization` 헤더를 백엔드로 나르기만
한다 — 서버가 자기 자격으로 부르면 그 순간 모든 사용자가 같은 권한을 갖는다.

TestScope 화면의 「내 정보 → 토큰」 에서 개인 토큰을 발급하고, 범위를 고른다.

| 범위 | 무엇을 |
| --- | --- |
| `read` | 모든 읽기 |
| `catalog:write` | 계열·기종·사양·기준정보 |
| `equipment:write` | 보유 장비·역량·교정 |

**기본은 읽기뿐이다.** 계정 관리와 서버 설정은 어느 범위로도 안 열린다 — 표에 없는
경로는 기계 자격으로 못 쓴다.

들어온 변경에는 통로(`X-Client: mcp`)와 토큰 이름이 감사에 남는다. 소유자만 남기면
사람이 넣은 것과 AI 가 넣은 것이 구별되지 않는다.

## 도구

**`get_guide()` 를 먼저 읽는다.** 안내는 `guide/GUIDE.md` 에 있고 서버가 매 호출
읽는다 — 클라이언트에 복사해 두면 고쳐도 옛 사본을 쓰는 사람에게는 전달되지 않는다.

```
찾기      resolve · list_conditions · list_spec_definitions · list_spec_sources
검색      search_capabilities                    ← 이 시스템이 존재하는 이유
계열      search_series · get_series · create_series · add_capability · link_series
기종      search_models(series=…) · create_model · get_specs · set_spec
보유 장비  search_equipment · get_equipment · register_equipment
남은 일    list_pending_work                      ← 어디부터 채울지
```

## 규약 (자세한 것은 `guide/GUIDE.md`)

1. **만들기 전에 `resolve` 로 찾는다.** 409 는 실패가 아니라 답이다.
2. **모르면 비운다.** 비슷한 것을 골라 넣지 않는다.
3. **기종은 계열부터 좁혀 고른다.** 라벨과 대조하려면 그 계열의 기종이 전부 보여야 한다.
4. **`unknown` 을 「가능합니다」 로 옮기지 않는다.**
5. 값에는 출처와 비고를 붙인다.

## 왜 얇은 프록시인가

DB 를 직접 안 읽는다. 필요한 계산이 생기면 **백엔드에 엔드포인트를 만든다** —
로직이 두 벌이 되면 화면과 AI 가 다른 답을 하고, 그때 어느 쪽이 맞는지 알 방법이 없다.
