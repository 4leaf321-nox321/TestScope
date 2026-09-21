# TestScope MCP 서버

AI 가 TestScope 에 **직접 묻고, 카탈로그를 채운다.**

```powershell
cd mcp_server
.\run_mcp.ps1            # HTTP — http://127.0.0.1:8022/mcp
.\run_mcp.ps1 -Stdio     # 개인 연결
```

가상환경이 없으면 만들고 의존성까지 넣는다. **`backend\.venv` 와 섞지 않는다** —
MCP SDK 가 언제든 프레임워크 판을 올릴 수 있고, 그때 앱이 인질이 되면 안 된다.

**설정은 `backend\.env` 한 곳에서 읽는다** — 개발·운영이 같은 키를 본다.

| 키 | 무엇을 | 기본 |
| --- | --- | --- |
| `PORT`·`APP_ENV` | 백엔드 주소를 계산한다(개발은 `PORT`+1, 운영은 `PORT`) | 8020 · development |
| `MCP_PORT` | 이 서버가 들을 포트 | 8022 (백엔드 +2) |
| `MCP_HOST` | 들을 자리. 밖에 열려면 `0.0.0.0` | 127.0.0.1 |

한 번만 다르게 띄우려면 인자가 이긴다 — `-ApiBase 'http://…/api'`, `-Port 8032`,
`-BindHost 0.0.0.0`. `TESTSCOPE_API_BASE` 같은 `TESTSCOPE_*` 는 `.env` 에 적어도
안 읽힌다(서버는 프로세스 환경변수만 본다) — 띄우는 스크립트가 넣어 준다.

## 자격

**이 서버는 권한을 판정하지 않는다.** 받은 `Authorization` 헤더를 백엔드로 나르기만
한다 — 서버가 자기 자격으로 부르면 그 순간 모든 사용자가 같은 권한을 갖는다.

TestScope 화면의 「내 정보 → 토큰」 에서 개인 토큰을 발급하고, 범위를 고른다.

| 범위 | 무엇을 |
| --- | --- |
| `read` | 모든 읽기 |
| `catalog:write` | 계열·기종·사양·기준정보 |
| `equipment:write` | 보유 장비·시험 항목·교정 |

**기본은 읽기뿐이다.** 계정 관리와 서버 설정은 어느 범위로도 안 열린다 — 표에 없는
경로는 기계 자격으로 못 쓴다. 검토함의 확정도 여기 없다: 고른 것이 곧 카탈로그 정본이라
사람이 화면에서 한다.

## 도구가 몇 개 실리나

도구 목록은 **매 턴 통째로 실린다** — 지금 69개에 5만 자 남짓이다. 읽기만 쓰는 연결이면

```powershell
.\run_mcp.ps1 -ReadOnly        # 또는 TESTSCOPE_MCP_TOOLS=read
```

로 쓰기 도구 스물넷을 뺀다(39개 · 22,000자). 어차피 범위가 없으면 403 이라, 보여 주면
고르는 일만 어려워진다.

무엇부터 부를지는 서버 안내문의 **길잡이 표**(「무엇을 물었나 -> 첫 도구」)가 말한다 —
도구 목록과 함께 항상 실린다. 자세한 것은 `get_guide("대목 이름")`.

들어온 변경에는 통로(`X-Client: mcp`)와 토큰 이름이 감사에 남는다. 소유자만 남기면
사람이 넣은 것과 AI 가 넣은 것이 구별되지 않는다.

## 도구

**`get_guide()` 를 먼저 읽는다.** 안내는 `guide/GUIDE.md` 에 있고 서버가 매 호출
읽는다 — 클라이언트에 복사해 두면 고쳐도 옛 사본을 쓰는 사람에게는 전달되지 않는다.

```
찾기       resolve · list_conditions · list_spec_definitions · list_spec_sources
검색       search_test_items · search_catalog · search_semantic · search_properties
부서       list_workspaces · resolve(kind="workspace")
계열       search_series · get_series · create_series · add_test_item · link_series
기종       search_models(series=…) · create_model · get_specs · set_spec
보유 장비   search_equipment · get_equipment · register_equipment · import_equipment
교정       get_calibrations · list_calibrations_due · add_calibration
규격       list_methods · get_method · create_method · set_requirement · import_requirements
물성 연결   search_properties · suggest_property_link(제안만) · confirm_property_links
기준정보    list_reference · list_axes · list_terms · create_term · add_term_alias · merge_terms
신뢰성 시험  list_reliability_tests · create_reliability_test · update_reliability_test
            test_capability                        ← 이 시험, 어느 장비로 돌리나
속성       list_attribute_definitions · create_attribute_definition
검토함      list_review_queues · list_review_items   ← 읽기만. 확정은 사람이 화면에서
그래프      graph_overview · graph_search · graph_node · graph_neighbors
남은 일     list_pending_work                      ← 어디부터 채울지
```

## 규약 (자세한 것은 `guide/GUIDE.md`)

1. **만들기 전에 `resolve` 로 찾는다.** 409 는 실패가 아니라 답이다.
2. **모르면 비운다.** 비슷한 것을 골라 넣지 않는다.
3. **기종은 계열부터 좁혀 고른다.** 라벨과 대조하려면 그 계열의 기종이 전부 보여야 한다.
4. **`unknown` 을 「가능합니다」 로 옮기지 않는다.**
5. 값에는 출처와 비고를 붙인다.

## 진짜로 불러 보기

```powershell
cd backend
$env:TESTSCOPE_PAT = python scripts/mcp_probe_account.py mint    # 확인용 계정·토큰
..\mcp_server\.venv\Scripts\python.exe ..\mcp_server\roundtrip.py --write
python scripts/mcp_probe_account.py cleanup                       # 만든 것과 계정을 지운다
```

CI 가 매 푸시 같은 세 명령을 돈다(빈 DB 에 시드를 심고, 백엔드를 reload 없이 띄워서).
curl 로는 멀쩡한데 도구로는 죽는 고장은 이렇게만 드러난다. `roundtrip.py` 는 `probe.py` 의
읽기 묶음을 그대로 쓰고 쓰기 사슬을 더한 것이다 — `--write` 없이 돌리면 읽기만.

## AI 가 헤매는지 재기

```powershell
.\run_mcp.ps1 -Trace                         # 호출 자취를 logs\calls.jsonl 에
.\.venv\Scripts\python.exe eval\score.py    # 물음별 자취를 다섯 항목으로 채점
```

답이 아니라 **도구 호출의 자취**를 본다 — 호출 수 · 길잡이대로 시작했나 · 필수 도구 · 금지
도구 · 빈손 호출. 자세한 것은 `eval/README.md`. pytest 처럼 「AI 가 보는 것」 을 고쳤을 때
돌려 기준선과 견준다; CI 에는 안 넣는다.

## 왜 얇은 프록시인가

DB 를 직접 안 읽는다. 필요한 계산이 생기면 **백엔드에 엔드포인트를 만든다** —
로직이 두 벌이 되면 화면과 AI 가 다른 답을 하고, 그때 어느 쪽이 맞는지 알 방법이 없다.
