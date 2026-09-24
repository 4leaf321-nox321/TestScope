# TestScope

**조직이 보유한 시험 항목의 지도.**

    "80도 환경에서 20 kN 이상의 인장시험 가능한 장비 있어?"

이 물음에 답한다.

    물성      ⇄   시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
    인장강도  N:M   인장          80도            ASTM E8       UTM-003        3동 201호
                              20 kN 이상                    (재료시험팀)   담당 홍길동

사람은 「인장」 이 아니라 「인장강도」 로 묻는 일이 많다. 어떤 시험으로 어떤 물성을 얻는지
(물성 ⇄ 시험 항목, N:M)가 맨 앞에 있어서 그 말도 받는다(ADR 0007).

지금까지 이 물음의 답은 사람 머릿속과 전화에 있었다. 그래서 옆 사업부에 있는
장비를 모른 채 외주를 주고, 만료된 교정으로 시험을 잡고, 새 장비를 살 때 이미
있는 것을 또 산다.

## 구성

| 경로 | 내용 |
|---|---|
| `backend/app/` | FastAPI 앱. 모듈 2계층(`models`/`schemas`/`services`/`routes`) |
| `backend/app/shared/` | 오류 규약·인증·권한·감사 — 모든 모듈이 거쳐 가는 것 |
| `backend/scripts/` | 설치 시드·데모 데이터·OpenAPI 내보내기 |
| `frontend/src/modules/` | 백엔드 모듈과 **같은 이름**을 쓴다 |
| `frontend/src/shared/` | 레이아웃·UI 프리미티브·API 클라이언트 |
| `scripts/deploy/` | 설치·배포·롤백·백업·복구 (PowerShell) |
| `scripts/ci/` | 배포 패키지 생성, 기동 스크립트 템플릿 |
| `docs/adr/` | 판단이 갈렸던 결정의 기록 |
| `배포.md` | 운영 서버 절차 |

배포는 **한 프로세스**다. 백엔드가 `frontend/dist` 를 함께 서빙한다 — 배포 산출물이
하나면 롤백도 하나다.

## 개발 환경

- Python **3.13** (`py -3.13`) — wheel ABI 가 배포 서버와 일치해야 한다
- Node 20+
- PostgreSQL 17

### 포트

| | 포트 | 비고 |
|---|---|---|
| 백엔드(개발) | **8021** | 운영과 가른다 — 아래 참조 |
| 백엔드(운영) | **8020** | 배포본은 API 와 SPA 를 같은 프로세스가 낸다 |
| MCP 서버 | **8022** | 백엔드 +2. 8030 은 CrossAXTF 운영 포트라 같은 PC 에서 겹쳤다 |
| 프론트(개발) | **5200** | `strictPort` — 밀려서 다른 포트로 뜨지 않게 |
| PostgreSQL(개발) | 5432 | `backend/.env` 의 `DATABASE_URL` |
| PostgreSQL(운영) | 5434 | 운영 PC 의 PG17 — 다른 플랫폼과 인스턴스를 가른다 |
| Ollama(의미 검색, 선택) | 11434 | `OLLAMA_BASE_URL`. 없으면 검색은 이름·별칭으로만 돈다 |

「플랫폼마다 10씩」 — TestScope 는 802x 대역이다(MatNexus·ReportArchive·StandardPlatform 과
겹치지 않게). 새 서비스를 붙이면 이 대역 안에서 고른다.

개발과 운영이 같은 포트를 쓰면, 개발 백엔드를 내린 순간 프론트 프록시가 **운영
설치본에 그대로 붙는다** — 화면은 그 사실을 아무 데도 말하지 않는다.

### 가상환경 켜기

편집기(VS Code·Cursor)는 **자동으로 켠다.** Python Environments 확장이
`backend/.venv` 를 찾아 새 터미널마다 `Activate.ps1` 을 걸어 준다 — 설정할 것은
없다(기본 탐색 경로가 `.venv` 와 `*/.venv` 라 `backend/.venv` 가 걸린다).

**venv 를 만든 뒤에는 창을 새로 고쳐야 한다.** 확장은 **창을 열 때 한 번**
환경을 훑어 워크스페이스의 환경을 정하고, 활성화는 **터미널이 만들어질 때만**
건다. 그래서 창을 열어 둔 채로 venv 를 만들면 그 창에서는 영영 안 걸린다 —
확장 로그에는 `Resolved Python Environment` 만 쌓이고 `Terminal is activated` 가
한 줄도 안 나온다.

    Ctrl+Shift+P -> Developer: Reload Window

바깥 PowerShell 에서는 한 줄로 켠다. **점을 앞에 붙인다** — 안 붙이면 스크립트가
제 스코프에서 돌고 끝나 반쯤 켜진 상태가 된다.

```powershell
. .\activate.ps1
```

**켜지 않아도 다 된다.** 아래 명령과 CI·배포 스크립트는 전부
`.\.venv\Scripts\python.exe` 처럼 인터프리터를 직접 가리킨다 — 활성화에 기대면
"내 창에서는 되는데 CI 에서는 안 되는" 차이가 생긴다.


### 실행

```powershell
# 백엔드 (최초 1회)
cd backend
py -3.13 -m venv .venv                # PATH 의 python 은 3.12 일 수 있다
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env                # DATABASE_URL 수정. **BOM 없이 저장한다**
createdb testscope ; createdb testscope_test
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe scripts\seed_install.py   # 관리자 — 비밀번호가 1회 출력된다

# 백엔드 실행
.\.venv\Scripts\python.exe run.py

# 워커 (별도 창 — 의미 검색 색인 등 요청 밖의 일. 없어도 앱은 돈다)
.\.venv\Scripts\python.exe run_worker.py

# 프론트엔드 (별도 창)
cd frontend
npm install
npm run dev
```

`seed_install.py` 가 온톨로지 축·조건 정의·뿌리 부서·**첫 시스템 관리자**를 만든다.
이것 없이는 아무도 로그인할 수 없다 — 가입은 승인이 필요한데 승인할 사람이 없기
때문이다. 멱등하므로 두 번 돌려도 비밀번호가 되돌아가지 않는다.

개발 중에는 프론트(5200)가 `/api` 를 백엔드(8021)로 프록시한다. 배포에서는 백엔드
한 프로세스가 API 와 SPA 를 함께 서빙하므로, 프론트 코드는 **API 절대주소를 갖지
않는다**.

### 관리자 계정

| | 값 |
|---|---|
| 아이디 | `admin` |
| 비밀번호 | `seed_install.py` 가 난수로 만들어 **화면에 한 번만** 찍는다 |
| 첫 로그인 | 비밀번호 변경이 강제된다 (`must_change_password`) |
| 부서 | `hq` (본사) — 부서 관리자이자 시스템 관리자 |

**아이디는 이메일 형식이 아니어도 된다.** 사내 관리자 계정은 `admin` 처럼 짧은
아이디를 쓰고, 폐쇄망은 `.local` 같은 도메인을 쓴다 — 형식을 강하게 검사해서 얻는
것보다 **로그인 자체가 성립하지 않는 손해**가 크다. 다른 아이디를 쓰려면
`--email` 로 준다.

비밀번호를 잃었거나 아이디를 바꿔야 하면 `set_admin.py` 를 쓴다. 화면에는 그 길이
없다 — 아이디 변경은 감사 기록과 알림이 가리키는 대상을 흔들기 때문에 관리자가
콘솔에서 하는 일로 남겼다.

```powershell
.\.venv\Scripts\python.exe scripts\set_admin.py --email admin --password '...'

# 아이디까지 바꾸기
.\.venv\Scripts\python.exe scripts\set_admin.py --email admin --password '...' `
    --rename-from admin@testscope.local
```

`seed_install.py` 는 **이미 있는 계정의 비밀번호를 되돌리지 않는다** — 설치
스크립트를 두 번 돌리는 일이 흔해서다. 그래서 복구는 이 스크립트가 맡는다.


### 데모 데이터 (선택)

빈 화면으로는 이 시스템이 무엇을 하는지 안 보인다. 장비 4대와 그 시험 항목을 넣어 두면
검색이 실제로 무엇에 답하는지 한 번에 드러난다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_demo.py
# 지울 때: scripts\seed_demo.py --purge
```

그다음 **장비 찾기**에서 `인장 / 시험 온도 80 degC 에서 / 하중 용량 20 kN 이상` 을
물어 본다.

### 부서 대장 일괄 반입

부서가 쓰던 엑셀 대장을 그대로 넣는다. **보유 장비** 화면의 「일괄 반입」.

1. **서식 내려받기** — 머리글과 보기 한 줄이 들어 있다. 어느 열에 무엇을 적는지는
   이것으로 안다.
2. 엑셀에서 채운다.
3. **머리글 줄까지 함께** 범위를 복사해 창에 **붙여넣는다.** 파일을 올리지 않는다 —
   문서 보안(DRM)이 걸린 곳에서는 파일 고르기가 막히기 때문이다. 붙여넣기는 막히지
   않는다.
4. 붙여넣으면 **넣기 전에** 줄마다 판정이 나온다. 문제가 있으면 몇 번째 줄인지
   말해 준다 — 엑셀에서 보이는 줄 번호와 같다.
5. 문제가 하나도 없어야 넣는 단추가 열린다. **전부 되거나 전부 안 되거나**다.

부서·거점·장비유형·기종은 **이름으로** 적는다. 몇 가지는 미리 알아 둘 것:

- **온톨로지에 없는 거점·분류는 여기서 안 만들어진다.** 반입이 값을 만들면 오타가
  그대로 축이 되고, 「본사」 와 「본사 」 가 서로 다른 거점이 된다.
- **기종 이름이 하나로 안 정해지면 그 줄은 거절된다.** 비슷한 기종에 끼워 넣으면
  그 장비의 하중·온도가 남의 것이 되고, 검색은 그 남의 수치로 「됩니다」 라고 답한다.
- **기종을 비우면 시험 항목이 0 건**이고, 0 건이면 그 장비는 검색에 절대 안 걸린다.
  넣기 전에 몇 대가 그런지 화면이 세어 준다.

**이미 등록된 자산번호**를 만나면 기본은 거절이다. 대장을 다시 붙여 맞추려면 창의
「이미 등록된 장비는 갱신」 을 켠다. 그때 규칙은 셋이다:

- **적힌 칸만 바꾼다.** 빈 칸은 「비운다」 가 아니라 「안 건드린다」 다 — 엑셀에 비고를
  안 적었다고 기존 비고가 지워지면 그건 갱신이 아니라 사고다. 그래서 「자산번호·설치
  위치·상태」 세 열만 긁어 와도 된다.
- **부서와 기종은 안 바꾼다.** 이관은 양쪽 관리자가 다 필요하고, 기종을 바꾸면 시험
  항목이 다시 복사되지 않는다. 다르게 적혀 있으면 그 줄을 막고 상세에서 하라고 말한다.
- **바뀔 칸은 파랗게** 칠하고 마우스를 얹으면 전후가 나온다. 누르기 전에 잘못 붙은
  열이 눈에 띄어야 한다.

### 부서 정보 주고받기 (ReportArchive)

ReportArchive 의 「부서 정보 내보내기」 파일을 그대로 받습니다. 컬럼과 순서가 같아
**양쪽으로 오갑니다.** 화면에서는 **관리 → 부서 정보 → 가져오기** 에 파일 내용을 붙여넣으면
미리보기(생성·갱신·건너뜀·오류) 뒤 적용합니다 — 명령줄과 같은 코드(`workspaces/imports.py`)로
판정합니다. 이미 있는 부서는 덮지 않고, 공개 정책(external_view_default)은 다른 물음이라 옮기지
않습니다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\import_workspaces.py 부서정보.csv --dry-run
.\.venv\Scripts\python.exe scripts\import_workspaces.py 부서정보.csv
.\.venv\Scripts\python.exe scripts\export_workspaces.py     # 같은 형식으로 내보내기
```

슬러그가 열쇠라 여러 번 돌려도 안 늘어나고, **이미 있는 부서는 안 덮습니다**
(`--update` 로 덮을 수 있음). 기본으로는 `org` 만 들입니다 — 저쪽 `virtual` 은
자식을 묶어 보여 주는 집계 노드고 `tf` 는 한시 조직인데, 이쪽 부서는 **장비의
소유자이자 권한의 단위**입니다(`--kinds` 로 넓힐 수 있음).

**공개 정책(`external_view_default`)은 안 옮깁니다.** 저쪽은 「이 게시판의 보고서를
다른 조직이 볼 수 있나」 이고 이쪽 `restricted` 는 「이 부서의 장비를 멤버에게만
보이나」 라 다른 물음이며, 기본값이 서로 반대라 그대로 뒤집어 넣으면 **반입 직후 모든
부서의 장비가 검색에서 사라집니다.**

### 제조사 카탈로그 들이기 (선택)

`source/catalog` 의 제조사 카탈로그를 장비 계열·기종으로 들입니다. 137계열·522기종·
사양값 1,900여 건이 한 번에 들어옵니다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\import_spec_sources.py   # 출처 문서 먼저
.\.venv\Scripts\python.exe scripts\import_catalog.py --dry-run
.\.venv\Scripts\python.exe scripts\import_catalog.py
```

(제조사, 이름) 비교키로 찾으므로 여러 번 돌려도 같은 줄이 둘로 늘지 않고, **이미
있는 값은 안 덮습니다** — 손으로 고쳐 둔 것이 사양서보다 정확합니다.

끝에 **보류한 사양 키**를 보고합니다. 정의가 없어 값을 안 들인 것들입니다 —
원본에 사양 키가 562종 있는데 76%가 단 한 곳에만 나와서, 만나는 대로 정의를 만들면
관리 화면이 못 쓰게 됩니다(ADR 0006). 필요한 것은 「장비 기종 사양」 에서 만들고 다시
돌리면 들어옵니다.

같은 반입이 **물성 항목**(`ontology/properties.json`, MaterialTwin 271키)과 **물성 ↔ 시험
항목 연결**(`ontology/property_links.json` + 객체의 measurands)도 심습니다. 연결은
「제안」 으로 들어오고, 「물성 항목」 화면에서 시스템 관리자가 확인합니다. 물성 키로 못 이은
measurand 가 있으면 끝에 보고합니다 — `property_links.json` 에 적어야 사라집니다.

화면에서 확인·지움·손으로 이은 것은 DB 행이라 다른 서버로 안 갑니다. **정본으로 되돌려
씁니다**:

```powershell
.\.venv\Scripts\python.exe scripts\export_property_links.py --check   # 무엇이 바뀌나
.\.venv\Scripts\python.exe scripts\export_property_links.py
```

`property_links.json` 의 `confirmed`(확인한 짝) · `rejected`(지운 짝) · `extras`(손으로 이은 짝)에
적히고, 그 파일을 커밋하면 패키지에 실려 운영 반입이 **확인된 채로** 넣습니다 — 같은 사람이
같은 것을 두 번 확인하지 않습니다.

#### MaterialTwin 계측기 들이기

`66_MatNexus/materialtwin-20260905/materialtwin.db`(계측기 218종·능력행 532건·물성 271종)를
카탈로그 객체로 바꾼 뒤 위 반입을 돌립니다. **DB 를 직접 들이지 않습니다** — 카탈로그의
정본은 `source/catalog` 하나이고, 반입 경로도 하나여야 같은 장비가 두 길로 안 들어옵니다.

```powershell
cd source\catalog
python tools_from_materialtwin.py --check      # 무엇이 생기는지만 본다
python tools_from_materialtwin.py              # equipment/*.json · ontology/properties.json 을 쓴다
python build_graph.py                          # 검증 + index.md
cd ..\..\backend
.\.venv\Scripts\python.exe scripts\import_catalog.py
```

MaterialTwin 은 기종 한 층뿐이라 **계열 묶음은 `source/materialtwin/groups.json` 이
정합니다**(사람이 확인한 표). 거기 없는 계측기는 변환기가 오류로 세웁니다. 이미 카탈로그에
있는 35종(Instron 5900 · AGS-X · HR-530 …)은 `supplements` 객체로 **없는 기종만 보태고**
(5965-E2 · HM-122 · TGA 5500), 기종마다 MaterialTwin 원문(설명·주석·능력행)은 `raw_specs`
에 통째로 남습니다.

### 사양 출처 들이기 (선택)

`source/catalog/sources.json` 의 제조사 문서 목록을 `spec_sources` 로 올린다. 모델에
사양값을 적을 때 **어느 문서 몇 쪽에서 나왔는지** 고를 수 있게 된다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\import_spec_sources.py
```

경로가 열쇠라 여러 번 돌려도 안전하다. 해시가 바뀐 문서만 개정으로 잡는다.
제조사 축에 그 이름이 아직 없는 문서는 제조사를 비운 채 들어오니, 축을 채운 뒤
다시 돌리면 이어진다.

### 프론트 타입 생성

스키마를 바꿨으면 둘을 함께 돌린다.

```powershell
cd backend  ; .\.venv\Scripts\python.exe scripts\export_openapi.py
cd ..\frontend ; npm run api:types
```

**손으로 적은 타입을 두지 않는다.** `src/shared/auth/types.ts` 와 각 모듈의
`api.ts` 는 생성된 `schema.d.ts` 에서 이름만 뽑아 쓴다 — 손으로 적으면 반드시
서버와 어긋나고, 어긋난 날 화면은 아무 말도 안 하고 undefined 를 그린다.
CI 가 생성물이 최신인지 검사한다.


## AI 에게 맡기기 (MCP)

`mcp_server/` 가 REST API 위의 **얇은 프록시**로 선다. AI 가 카탈로그를 채우고 시험 항목을
물을 수 있다.

```powershell
cd mcp_server
.
un_mcp.ps1            # HTTP — http://127.0.0.1:8022/mcp
.
un_mcp.ps1 -Stdio     # 개인 연결
```

**이 서버는 권한을 판정하지 않습니다.** 받은 토큰을 백엔드로 나르기만 합니다 —
서버가 자기 자격으로 부르면 그 순간 모든 사용자가 같은 권한을 갖습니다.

화면의 「내 정보 → 토큰」 에서 개인 토큰을 발급하고 **범위**를 고릅니다:
`read` · `catalog:write` · `equipment:write`. **기본은 읽기뿐이고**, 계정 관리와 서버
설정은 어느 범위로도 안 열립니다. 들어온 변경에는 통로(`mcp`)와 토큰 이름이 감사에
남습니다.

규약은 `mcp_server/guide/GUIDE.md` 에 있고 서버가 매 호출 읽습니다 — 클라이언트에
복사해 두면 고쳐도 옛 사본을 쓰는 사람에게는 전달되지 않습니다.

## 무엇이 어디에 있나

| 개념 | 표 | 무엇인가 |
| --- | --- | --- |
| 부서 | `workspaces` | 조직도. 장비의 소유자이자 권한의 단위. ReportArchive 와 CSV 로 오간다 |
| 계정 | `users` | 가입 신청 -> 승인 -> 활성. 지우지 않고 정지한다 |
| 온톨로지 | `vocabularies` · `vocabulary_terms` · `vocabulary_aliases` | 폼에서 고르는 값의 목록 |
| 조건 정의 | `condition_keys` | 온도·하중처럼 **칸의 계약**. 차원과 저장 단위가 붙는다 |
| 장비 계열 | `equipment_series` · `series_test_items` · `series_relations` | **제조사가 파는 계열.** 무슨 시험이 되나 · 어느 부속이 붙나 |
| 장비 기종 | `equipment_models` | 계열 안의 한 기종. **수치가 여기서 갈린다** |
| 사양 정의 | `spec_groups` · `spec_definitions` | 모델에 적을 수 있는 칸. **비어 있는 적용 분류는 공통**이다 |
| 사양 값 | `model_spec_values` · `spec_sources` | 모델이 실제로 갖는 값과 그 값이 나온 문서 |
| 보유 장비 | `equipment` · `equipment_calibrations` | **우리가 가진 개체**. 대장과 교정 이력 |
| 시험법 | `test_methods` · `method_requirements` | 규격과 그것이 요구하는 조건 |
| 시험 항목 | `equipment_test_items` · `equipment_test_conditions` | **이 대가 어떤 시험을 어디까지 하나** |
| 감사 | `audit_entries` | 되돌릴 수 없는 변경. 고칠 수 없다. **통로(화면·mcp)와 토큰 이름이 남는다** |
| 접근 로그 | `access_logs` | 사용자 지원용. 감사와 보존 기간이 다르다 |

**시험 항목이 이 시스템의 본문이다.** 장비에 온도 범위를 직접 적지 않는 이유는,
실제로는 "인장 지그로는 200도까지, 굽힘 지그로는 상온만" 같은 일이 흔하기
때문이다 — 능력은 장비의 성질이 아니라 **장비와 시험의 짝**에 붙는다(ADR 0002).

**그리고 층이 둘이다**(ADR 0004). 카탈로그는 세상에 있는 것(제조사가 파는 모델,
기관이 낸 규격)이고, 보유 장비는 **그 둘을 엮은 인스턴스**다 — 어떤 모델이며 어떤
시험법을 실제로 돌리는가.

    장비 계열 ─> 기종(사양) ─┐
                              ├─>  보유 장비 한 대  ─>  이 대의 시험 항목  ─>  검색이 답한다
    시험법(규격)            ─┘

**카탈로그가 다시 두 층이다**(ADR 0006). 계열은 「무슨 시험이 되나」 를 정하고,
기종은 「어디까지 되나」 를 정한다 — 한 계열 안에서 하중 용량이 중앙값 60배, 최대
1200배 갈리기 때문이다. 계열을 한 줄로 두면 0.5 kN 짜리 한 대를 가진 부서가
「300 kN 인장 되나요」 에 된다고 답한다.

카탈로그의 시험 항목은 **본뜨는 틀**이다. 보유 장비를 등록할 때 계열의 시험 항목이 복사되고
(`confidence=catalog`) **조건은 그 기종의 사양에서 온다.** 그 뒤로는 개체가
진실이다 — 챔버를 뗀 대가 실제로 있고, **갈라지는 것이 정상**이다.

**사양은 정의를 통제하고 값은 자유롭게 둔다**(ADR 0005). 모델에 적을 수 있는 칸은
관리자가 정하고(`spec_definitions`), 값은 모델마다 채운다. 붙는 분류를 비우면 공통
사양이다 — 전원·무게처럼 분류를 가리지 않는 것이 실제로 많다.

검색축(`condition_keys`)에 이어 둔 사양은 **보유 장비를 등록할 때 그 대의 시험 항목
조건이 된다.** 하중 용량을 사양표와 시험 항목에 두 번 적게 두면, 언젠가 한쪽만 고쳐지고
그때부터 화면에 보이는 숫자와 검색이 쓰는 숫자가 갈린다.

## 겪게 될 함정

**`.env` 에 BOM 이 붙으면 첫 줄 키가 조용히 무시된다.** PowerShell 5.1 의
`Set-Content -Encoding utf8` 과 메모장이 BOM 을 붙인다. `APP_ENV` 가 기본값으로
떨어져 운영이 development 로 뜨고, reload 가 켜진 채 돈다.

**DB 가 코드보다 뒤처지면 화면이 500 을 낸다.** 기동 로그와 서버 화면이 그것을
말해 주지만, 그 전에 다른 화면을 먼저 열면 원인이 안 적힌 500 을 본다.
마이그레이션을 만들었으면 **그 자리에서** `alembic upgrade head` 를 돌린다.

**새로 만든 API 가 404 로 오는데 코드에는 있다면 좀비 서버를 의심한다.**
Windows 는 두 프로세스가 같은 포트를 LISTEN 하는 것을 막지 않는다. reload 로 띄운
개발 서버는 부모와 자식 워커 둘인데, 부모만 죽으면 **자식이 소켓을 물고 남는다** —
그다음에 띄운 새 서버와 옛 워커가 번갈아 답하고, 그러면 `TSC-COMMON-0404` 가
띄엄띄엄 온다. `run.py` 가 뜰 때 이것을 본다: 포트를 쥔 PID 가 **이미 죽은 프로세스**면
그 부모의 워커는 아무도 안 거두는 고아라 스스로 내리고 뜬다(「죽은 부모(…)의 워커 … 를
내렸습니다」). 쥔 프로세스가 살아 있으면 남의 서버일 수 있어 거절한다 — 그때는 직접 본다.

```powershell
Get-NetTCPConnection -LocalPort 8021 -State Listen |
  Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique
```

CI 와 확인 스크립트는 애초에 reload 없이 띄운다(`python -m uvicorn app.main:app --port …`)
— 워커가 없으니 고아도 없다.

**채울 자리는 홈의 「남은 일」 이 짚어 준다.** 카탈로그 전체가 아니라 **우리가
가진 것만** 센다 — 사양이 안 적힌 보유 기종, 시험 항목이 안 적힌 보유 계열, 원본
확인이 필요한 보유 기종. 전부를 채우라고 하면 목록에 끝이 없어 보여서 아무도
시작하지 않는다.

**시험 항목이 0 인 장비는 검색에 절대 안 걸린다.** 장비 목록의 「시험 항목」 칸이 그것을
말해 주고, 홈의 「남은 일」 이 숫자를 센다. 검색 결과가 비었을 때 그 숫자가
"그런 장비가 없다" 와 "아직 안 적었다" 를 가른다.

## 검증

```powershell
cd backend
.\.venv\Scripts
uff.exe format . ; .\.venv\Scripts
uff.exe check .
.\.venv\Scripts\mypy.exe
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic check   # 마이그레이션이 모델과 맞나
cd ..\frontend ; npm run build ; npm test ; npm run lint
```

CI 가 같은 것을 Windows 러너에서 강제한다(`.github/workflows/ci-windows.yml`).

## 운영 서버에 올리기

절차는 [배포.md](배포.md) 에 있다. 요약하면:

| 상황 | 스크립트 |
|---|---|
| 서버에 처음 올린다 | `precheck.ps1` -> `install.ps1` |
| 갱신한다 | `backup.ps1` -> `deploy.ps1` |
| 갱신이 잘못됐다 | `rollback.ps1` |
| 백업에서 되돌린다 | `restore.ps1` |

릴리스 자산은 **`deploy_package.zip` 하나**다 — 코드·SPA·wheel 번들·배포 스크립트가
전부 그 안에 있어서, 폐쇄망이면 이 파일만 반입하면 된다. `frontend/package.json` 의
version 을 올려 main 에 밀면 태그·릴리스가 자동으로 만들어진다.

## 지침

코드를 고칠 때의 규칙은 [AGENTS.md](AGENTS.md) 에 있다.
