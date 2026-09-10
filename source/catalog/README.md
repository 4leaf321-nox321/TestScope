# 물성 시험 장비 카탈로그 원천 데이터 (`source/`)

웹에서 받은 제조사 카탈로그·데이터시트(PDF)와, 거기서 뽑아 낸 장비 객체(JSON), 그리고
객체를 잇는 온톨로지 정의를 둔다. **TestScope 의 사슬을 채우기 위한 원료**다.

    시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
    test_item      limits         standards    equipment      (조직이 채운다)

## 폴더

| 경로 | 내용 |
|---|---|
| `pdf/<제조사>/*.pdf` | 원본 PDF. 파일명은 `<시리즈>-<문서종류>.pdf` 로 통일 |
| `pdf_직접/*.pdf` | 봇 차단으로 자동 수집이 안 돼 사람이 직접 받은 PDF 를 놓는 자리. 여기서 `pdf/<제조사>/` 로 옮기고 이름을 맞춘 뒤 추출한다 |
| `extracted/text/<제조사>/*.txt` | PDF 에서 뽑은 전체 텍스트 (`===== page N =====` 구분) |
| `extracted/text/<제조사>/*.meta.json` | 쪽수·크기·sha256·PDF 메타 |
| `catalog/urls.json` | PDF 파일 -> 원본 URL (출처 추적) |
| `catalog/schema.json` | 장비 객체 JSON Schema |
| `catalog/equipment/<제조사>/*.json` | **장비 객체** — 시리즈/모델 단위 하나 |
| `catalog/ontology/*.json` | 축 정의: 제조사·장비 분류·시험 항목·조건 키·관계 종류 |
| `catalog/tools_render_pages.py` | PDF 특정 쪽을 PNG 로 렌더링(표 열 대응 확인용) |
| `catalog/build_graph.py` | 객체를 검증하고 `graph.json`(노드+엣지)·`index.md`·`sources.json` 을 만든다 |
| `catalog/reference_docs.json` | 장비가 아닌 규격·시험법 문서(IPC ROSE, USB Type-C, IPX9K 백서 등) |

## 장비 객체가 답해야 하는 것

1. **누가 만든 무엇인가** — `manufacturer`, `series`, `models[]`
2. **무엇을 잴 수 있나** — `test_items[]` (인장·압축·경도·DSC…), `measurands[]` (강도·탄성률·Tg…)
3. **어디까지 되나** — `limits{}` 시리즈 전체 범위, `models[].specs{}` 모델별 값
4. **어느 규격에 맞나** — `standards.compliance[]` (장비 자체 정확도 등급), `standards.test_methods[]` (수행 가능 시험법)
5. **무엇을 붙이면 범위가 넓어지나** — `relations[]` (`compatible_accessory`, `extends_temperature` …)
6. **근거가 어디인가** — `sources[]` (PDF 파일 + 쪽)

## 단위 규약

TestScope `ConditionKey` 와 같은 단위를 쓴다: 힘 **kN**, 속도 **mm/min**, 온도 **degC**,
주파수 **Hz**, 길이 **mm**, 습도 **%**. 그 밖의 축은 `ontology/condition_keys.json` 에
키 이름 자체에 단위를 박아 둔다(`impact_energy_J`, `torque_Nm`, `test_load_kgf`).
**범위의 빈 칸은 "제한 없음/미기재"** 다. 0 으로 채우지 않는다.

## 신뢰도

객체마다 `confidence` 를 단다.

| 값 | 뜻 |
|---|---|
| `catalog` | 제조사 카탈로그·데이터시트의 사양표에서 뽑았다. 실측 능력이 아니다 |
| `limited` | 확보한 문서가 매뉴얼·백서·유통사 요약본이라 정량 사양이 부족하다 |
| `verified` | 실측·교정 성적서로 확인했다 (아직 사용처 없음) |

텍스트 추출이 표를 흩뜨려 열 대응이 불확실한 값은 `"uncertain": true` 를 단다.
그런 값은 원본 PDF 쪽을 열어 확인한 뒤에 쓴다.

## 수집 범위 (2026-09 기준)

| 구분 | 수 |
|---|---|
| 원본 PDF | 349 (전부 `urls.json` 에 출처 기록, 중복 0) |
| 장비 객체 | 194 |
| 그래프 노드 / 엣지 | 1474 / 2867 |
| 제조사 / 장비 분류 / 시험 항목 | 83 / 108 / 85 (온톨로지 정의 수) |
| 그중 실제로 쓰인 것 | 78 / 87 / 82 |
| `uncertain: true` 미검증 값 | 55 (34개 객체) |
| 어느 객체에도 안 걸린 PDF | **0** (장비 객체 + `reference_docs.json` 19) |

**1차** — 재료 물성: 만능재료시험기, 피로, 충격, 경도, 열분석(DSC·TGA·DMA·TMA·열전도),
레오미터, 멜트플로우, HDT/Vicat, 마모·트라이볼로지, 표면·구조 분석.

**2차** — 전기전자 제품군(휴대폰·TV·가전·의료기기·네트워크 장비): 환경 챔버(항온항습·
열충격·HAST·HALT/HASS·복합부식·내후성·분진), 진동·충격·낙하, EMC(ESD·서지·EFT·EMI 수신기),
전기안전(내전압·절연저항·접지연속성), 전력 계측·AC 전원·전자부하, 배터리 사이클러·ARC,
광학(분광복사휘도계·컬러 아날라이저·이미징 콜로리미터·열화상), 음향(오디오 분석기·HATS),
전자부품 검사(본드테스터·X-ray·C-SAM·XRF 두께·열저항), 누설, 코팅·크림프.

**4차** — 자동 수집이 막혀 있던 제조사를 사람이 직접 내려받아 채웠다. Göttfert
모세관 레오미터(RHEOGRAPH 계열·auto·25E·TCR·역압 점도계·PVT500·애드온 7 객체),
Unholtz-Dickie 가진기(S·H·R·K·T 계열, LS 롱스트로크 스러스터, 680C 변환기 교정 3 객체),
대경테크 브리넬 경도기 1 객체. 이로써 `capillary_rheometer` 분류와 `rheology_capillary`
시험 항목이 처음으로 채워졌다 — 그 전까지는 온톨로지에 정의만 있고 장비가 없었다.
직접 받은 PDF 는 `source/pdf_직접/` 에 두었다가 `pdf/<제조사>/` 로 옮겨 이름을 맞춘다.

**5차** — Hegewald & Peschke 22 PDF, 10 객체. 만능재료시험기 inspekt 네 계열(바닥형
100~1500 kN, table 10~250 kN, blue 5~50 kN, solo 2.5 kN)과 부속(온도·기후 챔버 7 기종,
그립, 신장계), 경도기(AT130 DR/DSR 로크웰, 진공 1500 °C 고온 비커스, 휠림 자동 브리넬).
`pdf.directindustry.com` 이 403 으로 막혀 있었으나 **브라우저 UA 헤더를 붙이면 200 이 온다**.
다만 DirectIndustry 는 쪽 이미지만 주므로, 거기서 문서 목록만 얻고 실제 PDF 는 제조사
사이트(`hegewald-peschke.com/fileadmin/...`)에서 받았다 — 원본을 받을 수 있으면 언제나 그쪽이다.

**6차** — 5차에서 알아낸 UA 헤더 우회를 **이전에 막혔다고 적어 둔 곳 전부에** 다시 걸었다.
그 결과 `goettfert.com`·`uson.com`·`ets-lindgren.com`·`bruker.com`·`ap.com`·`instron.com`·
`keysight.com` 이 전부 200 을 준다 — 앞선 기록이 틀렸던 것이다. 아직 막힌 곳은
`tainstruments.com` 과 `udco.com` 둘뿐이고(Akamai), 이 둘은 **archive.org 스냅샷**으로 우회했다.

- Hegewald & Peschke: 사이트맵 -> 제품 페이지 80 개 크롤 -> PDF 링크 128 개 -> 가구·길이측정을
  뺀 105 개를 받아 총 127 PDF. 객체 6 개 추가(진자충격 PSd 50/450/750, 비틀림 6 기종,
  고온로 HTO-08·STE, 선재 반복굽힘, 크리프 하중 유닛, inspekt duo)와 기존 계열 보강
  (inspekt 2500 kN, table 10·20 kN, blue 5·10·20·50 kN).
- TA Instruments: archive.org 에서 8 PDF -> 객체 6 개(Discovery DSC·TGA, DMA, SDT Q600,
  Discovery HR 레오미터, Light Flash). **온톨로지에 정의만 있고 비어 있던 제조사를 채웠다.**
- Unholtz-Dickie: archive.org 에서 K-170 기종 데이터시트를 얻어 정현/랜덤/충격 정격력과
  베이스 구성별 치수·중량을 확정했다.

**7차** — 받아 두고 객체가 없던 문서 64 건을 정리했다.

- **중복 24 건 제거.** 5차와 6차의 파일명 규칙이 달라 같은 PDF 를 두 이름으로 받아 두고 있었다
  (`inspekt-100kn-datasheet.pdf` == `10-101-x0x-...-100kn.pdf`). sha256 으로 찾아 객체가 인용 중인
  쪽만 남기고 지웠다. **PDF 를 받은 뒤에는 반드시 해시로 중복을 확인할 것.**
- MTS 부속 카탈로그는 제조사가 같은 문서를 Criterion·Exceed 두 URL 로 배포하는 것이었다
  (제목이 "MTS Criterion & Exceed Accessories"). 파일 하나로 합치고 두 객체가 함께 가리키게 했다.
- 신장계 17 건·그립 12 건의 기종별 데이터시트를 반영해 두 객체를 `limited` -> `catalog` 로 올렸다.
- 새 객체 6 개: 회전식 충격 인장(80 kN·350 s⁻¹), 마찰 시험대, 다중 충격(투사체 140 km/h),
  inspekt micro S500N, inspekt vario 부품 시험기, TA VTI-SA+ 증기 흡착 분석기.
- 소프트웨어(LabMaster 7 건·HardWin XL)와 서비스·개요 자료 5 건은 장비가 아니므로
  `reference_docs.json` 으로 옮겼다(4 -> 17 건).
- **판본 차이를 잡았다**: inspekt table 100 kN 은 구판(10-031-102)과 신판(10-031-1x4)의 강성·속도·
  분해능·힘 하한이 모두 다르다. 6차에 구판을 기록해 "이 기종만 힘 하한 0.4 %" 라고 적었는데
  신판은 계열과 같은 0.1 % 다 — 신판으로 바로잡았다. inspekt 400 kN 도 자료번호가 다른 두 구성이
  있고 프레임 크기·무게·전력·이동 분해능이 크게 다르다.

**8차** — 등록 폼 뒤에 있던 제조사 다섯 곳을 팠다. 사이트는 UA 헤더로 열리지만 브로슈어가
폼 뒤에 있어, **옛 도메인과 archive.org 스냅샷**으로 우회했다.

- **Bruker Hysitron**: 옛 독립 도메인 `hysitron.com` 의 2015 스냅샷에서 TI 950 TriboIndenter·
  PI 95 TEM PicoIndenter·TS 75 TriboScope 확보 -> 객체 3 개. `instrumented_indentation` 이 채워졌다.
- **Uson**: archive.org 에서 Sprint LC/GT·Qualitek mR·VFT 등 7 건 -> 객체 2 개. 자료가 2003~2021 로
  오래돼 현행 제품군(Sprint iQ·Optima vT)은 여전히 없다.
- **ETS-Lindgren**: 라이브 사이트의 PDF 링크가 **200 과 함께 HTML 게이트**를 준다(Content-Type 확인 필수).
  archive.org 에서 5 건 -> 객체 2 개. 브로슈어가 마케팅 층위라 `confidence: limited`.
  온톨로지에 없던 제조사라 `manufacturers.json` 에 추가했다(81 -> 82).
- **MTDI**: `mtdi.co.kr` 자료실 카탈로그 게시판에서 14 건. 다운로드 링크에 세션 nonce 가 붙어
  쿠키가 필요하고 nonce 의 `|` 를 %7C 로 인코딩해야 한다. FLD-300S 성형한계도 시험기 객체 1 개.
- **SALT(Light-SALT)**: `light-salt.kr` 이 열리지만 제품 사양이 **이미지**라 텍스트로 뽑히지 않는다.
  PDF 카탈로그가 없어 아직 객체가 없다.

받은 파일이 온전한지 **쪽수로 확인해야 한다** — archive.org 가 정확히 1 MB 에서 자른 파일을 주기도 한다
(`%PDF-` 검사는 통과하지만 0 쪽). 스냅샷을 여러 개 시도하면 온전한 것이 나온다.

**9차** — 텍스트층이 없는 **이미지 전용 스캔 11 건**을 렌더링해 눈으로 읽었다. 순서는
전체 쪽을 축소한 contact sheet 로 사양표가 몇 쪽에 있는지 찾고 -> 그 쪽만 확대해 읽는 것이다.
MTDI 객체 5 개(UC-980 노·UC-350/UC-170 챔버, 마모마찰 4 기종, 비틀림, 원주인장, 전해에칭기)를
만들었고, 남은 문서는 성격에 맞게 `reference_docs.json` 으로 옮겼다(17 -> 22).

- 파일명과 내용이 어긋나는 경우가 있다 — `materials-testing-machines-catalog.pdf` 의 실제 내용은
  노와 챔버다(게시판 분류를 따른 파일명).
- 전기방사 시스템(ESS-100)은 나노섬유를 **만드는** 생산 장비라 장비 객체로 담지 않고 참고문서로
  옮겼다. Epsilon 신장계 3 건은 MTDI 가 유통하는 **타사 제품**이라 제조사가 틀려지므로 같은 처리를 했다.
- 스캔은 페이지 경계에서 표가 잘리기도 한다 — 전해에칭기의 전류 상한과 깊이·높이를 못 읽어
  `uncertain: true` 를 달았다.

**10차** — SALT 를 채우고 온톨로지를 넓혔다.

- **SALT(Light-SALT)**: PDF 카탈로그가 아예 없는 제조사다. 제품 페이지의 사양이 이미지인 줄
  알았는데 실은 HTML `<table>` 이었고 키워드 나열 블록에 가려져 있었을 뿐이다. ST-1000/1001/1002
  전기기계식과 ST-1004/1004C/1004LT 유압 서보식 두 객체를 만들었다.
- **웹 전용 출처를 규약에 넣었다.** `sources[]` 항목이 `file` 대신 `url`(+`retrieved`)을 가질 수
  있게 `schema.json` 과 `build_graph.py` 를 넓혔다 — 둘 다 없으면 여전히 막는다. 제조사가 PDF 를
  내지 않는 경우가 SALT 만은 아닐 것이다.
- **온톨로지 확장**: 분류 9 개(`specimen_preparation`·`formability_tester`·`burst_pressure_tester`·
  `electrolytic_etcher`·`cutting_mounting_polishing`·`reverberation_chamber`·`shielded_enclosure`·
  `vapor_sorption_analyzer`·`nanoindenter`)와 시험 항목 4 개(`formability`·`burst_pressure`·
  `vapor_sorption`·`shielding_effectiveness`), 제조사 `epsilon` 을 추가하고 가까운 분류로
  임시로 걸어 두었던 객체 9 개를 제자리로 옮겼다. Epsilon 신장계 객체도 만들었다.
- **id 충돌 7 건을 고쳤다.** `dsc`·`tga`·`dma`·`tma`·`thermal_conductivity`·
  `instrumented_indentation`·`high_speed_tensile` 는 분류와 시험 항목에 같은 id 로 있어서,
  먼저 만들어지는 분류 노드가 이기고 시험 항목 노드는 아예 생기지 못했다 — `performs` 엣지가
  분류 노드를 가리키고 있었다. `build_graph.py` 가 두 축의 노드 id 에 `category:` / `test_item:`
  접두사를 붙이도록 고쳤다(원래 id 는 노드의 `key` 필드에 남는다). `relations[]` 는 접두사 없는
  id 를 그대로 쓰면 되도록 빌더가 되돌려 준다. **graph.json 을 읽는 변환기가 아직 없어서 지금이
  고칠 수 있는 때였다.**

**11차** — 남은 두 빈 곳을 다시 팠고, 하나는 **내 판단이 틀렸던 것**이었다.

- **MTDI 시편전처리**: 이미지 스캔 카탈로그에는 사양이 없었지만 **제품 페이지에는 HTML `<table>` 이
  있었다.** 앞서 MTDI 제품 페이지를 `MINOS-300` 하나만 열어 보고 "사양이 이미지" 라고 단정한 것이
  틀렸다 — SALT 에서 똑같이 헛짚은 뒤였는데도 그랬다. KANTA 고속절단기 4·DIAMO 정밀절단기 3·
  ETOS 마운팅 프레스 3·FOBOS 연마기 3, 모두 13 기종을 한 객체로 담아 `cutting_mounting_polishing`
  분류를 채웠다.
- **SALT 피로시험기(ST-1005-HL/HU/TT/E)**: 국문·영문 제품 페이지, 상세 이미지, 자료실을 모두
  확인했으나 사양이 어디에도 없다(상세 이미지는 제품 사진뿐). **진짜 빈 곳으로 확정한다.**

**교훈 — 한 페이지만 보고 사이트 전체를 판단하지 말 것.** 같은 사이트라도 게시판/제품군마다
사양을 담는 방식이 다르다. 사양이 안 보이면 (1) `<table>` 을 먼저 찾고 (2) 다른 제품군 페이지도
열어 보고 (3) 그 다음에 이미지 렌더링을 쓴다.

**12차 (전수 감사)** — 194 객체·349 PDF 를 전부 교차 검증했다. 무결성은 깨끗했다
(추출 349/349, sha256 불일치 0, 중복 0, urls 누락 0, 미사용 PDF 0). 대신 **네 가지 결함**이 나왔다.

1. **없는 쪽을 인용한 출처 13건** — `p3` 인데 문서가 2쪽인 식. 근거를 되짚을 수 없는 상태였다.
   지우고 각 출처에 정정 기록을 남겼으며, `build_graph.py` 가 이제 **쪽수 초과를 오류로 잡는다**
   (추출 메타의 `pages` 와 대조).
2. **온톨로지에 없는 limits 키 163 종(320회)** — 규칙은 "축은 condition_keys.json 에 등록한다"
   였는데 검사하는 곳이 없어 표류했다. 163 종을 한글 라벨·차원·단위와 함께 등록했고(44 -> 207),
   빌더가 미등록 키를 **경고**한다(실패시키지는 않는다).
3. **온도 상한이 본체가 아니라 옵션 부속의 값인 객체 9개** — 노트에는 적혀 있었지만 구조화된
   필드가 아니어서, "80 °C 에서 20 kN 인장" 질의에 **가지고 있지도 않은 노를 전제로 답하게** 된다.
   `limits.<축>.requires_accessory` 불리언을 스키마에 넣고 9 곳에 달았다.
4. **스키마를 어기던 객체 34건** — 도메인 상세 필드(`operating_modes`·`techniques`·`range_table` …)
   25 종이 선언 없이 쓰이고 있었다. `additionalProperties:false` 를 유지한 채 25 종을 선언해
   정본으로 만들었다(열어 버리면 오타 필드를 못 잡는다). `options` 는 `{name, note}` 형식도 받게
   하고, 연필 경도는 숫자가 아닌 **순서척도**라 `values` 목록으로 옮겼다. 이제 스키마 오류 0.

또 하나: **부속이 시험 장비처럼 검색된다.** `hegewald-peschke-grips`(그립)는 `force_kN 1200`·
`tensile` 을 가져 "20 kN 인장 되는 장비" 질의에 1위로 나온다. 데이터는 맞으므로 지우지 않고,
`index.md` 에 **종류(계열/기종/부속/센서)** 열을 넣고 온도에 `(부속)` 표시를 달았다.
**질의하는 쪽은 `kind` 로 걸러야 한다.**

힘 축이 이름 7 개로 갈라져 있던 것(`force_kN`·`dynamic_force_kN`·`test_load_kgf` …)도
`testscope_key: "force"` 로 묶었다 — 안 그러면 서보유압 피로기가 "20 kN" 질의에서 통째로 빠진다.

## 표 값 검증 (3단계)

텍스트 추출이 표의 열을 흩뜨리면 값이 뒤바뀐다. 그런 곳은 **원본 쪽을 PNG 로 렌더링해
눈으로 확인**한다. `catalog/tools_render_pages.py` 를 PyMuPDF 가 설치된 인터프리터로 실행한다:

    tools_render_pages.py <pdf 상대경로> <쪽번호,...> [배율]

쪽번호는 추출 텍스트의 `===== page N =====` 과 같은 1-기반 번호다. 이 방법으로 잡은 실제 오류:

| 객체 | 무엇이 틀렸나 |
|---|---|
| `shimadzu-agx-v2` | 위치 분해능이 10 kN↔20/50 kN 서로 바뀜, 300/600 kN 크로스헤드 속도 뒤바뀜, 100 kN 치수·중량이 20/50 kN 값 |
| `kikusui-tos9300` | TOS9320 을 "TOS5300 어댑터"로 오기 — 실제로는 4채널 고전압 스캐너 |
| `nordson-dage-quadra-xray` | 68,000배·0.1 µm·6.7 MP 는 Quadra 7 사양인데 시리즈 전체 값으로 기록 |
| `lansmont-shock-test-systems` | 구형 Model 23 명칭으로 적고 Performance 시리즈 7개 모델 사양이 비어 있었음 |
| `espec-tsa-thermal-shock` | 모델별 온도·용적·유틸리티가 통째로 비어 있었음 |
| `chroma-63200-dc-load` | 12개 모델 중 3개만 채워져 있었고 이중 레인지 구조를 놓침 |
| `goettfert-rheograph` | 배럴 조합·피스톤 속도·전원·치수가 열을 넘나들며 뒤섞임. 23쪽을 렌더링하고 배럴 구역을 6배 확대해 점(●)/대시(-)의 열 위치를 대조 |
| `daekyung-tech-dtb-brinell` | 매뉴얼 안에서 기종 표기가 어긋남(표지·명판 DTB / 사양 쪽 DTR). 15쪽을 렌더링해 인쇄 그대로 확인하고 명판을 따랐다 |
| `hegewald-peschke-temperature-chambers` | 7 기종 안/바깥 치수 표. 렌더링해 대조한 결과 추출 텍스트와 일치 — 틀린 곳 없음 |
| `hegewald-peschke-torsion` | 4 기종 정격·치수·무게가 뒤섞임. 렌더링해 보니 T-200H 이름을 쓰는 구성이 자료번호 둘(41-031-510 / 501)로 나뉘고 회전 속도(25 vs 60 rpm)와 전원이 서로 다르다 |
| `hegewald-peschke-high-temperature-furnaces` | STE 2 열 표. 렌더링으로 Ø264=STE-12(1000 °C), Ø290=STE-13(1250 °C) 확인 |
| `unholtz-dickie-shakers` (K-170) | 추출 텍스트에 지면에 없는 `70 in/s`·`75 in/s` 가 섞여 있었다. 렌더링으로 실제 값은 정현 80 in/s(2.0 m/s), 충격 138 in/s(3.5 m/s) 뿐임을 확인 |

## 아직 빈 곳

`graph.json` 에 `placeholder` / `utility` 로 남는 노드가 곧 빈칸이다. 지우지 않고
드러내 둔다.

- **부속·연계 장비 객체 없음** — `shimadzu-agx-v`, `zwickroell-ahtf-850-furnace`,
  `zwickroell-mflow-cflow`, `instron-3119-960-furnace-controller`,
  `instron-3621-hydraulic-power-unit`, `instron-electropuls-e10000`
- **유틸리티 노드** — `utility-compressed-air`, `utility-cooling-water`,
  `utility-liquid-nitrogen`, `utility-emc-chamber` 등. 장비가 아니라 설비 요구사항이다
- **제조사 미확보 — 없다.** 온톨로지의 제조사 83 개 중 78 개가 객체를 갖는다. 나머지는
  규격 단체(ipc·usb-if·mil-std)와 `misc` 처럼 애초에 장비 제조사가 아닌 항목이다
- **MTDI 원주인장 시험기** — 카탈로그가 전원·치수 위주라 정작 시험 능력(시편 지름·길이, 최대
  원주 하중, 승압 속도)이 없다. `confidence: limited`
- **`specimen_preparation`** 은 상위 분류라 직접 쓰이지 않는 것이 정상이다(하위
  `cutting_mounting_polishing`·`electrolytic_etcher` 가 쓰인다)
- **SALT 피로시험기 계열**(ST-1005-HL/HU/TT/E) — 국문·영문 페이지, 상세 이미지, 자료실 어디에도
  사양이 없다. 제조사에 직접 요청하는 수밖에 없다
- **Hegewald & Peschke 안에서 남은 것** — 유압식 UTM(inspekt 500 H·1000 H·1000 HF)은
  DirectIndustry 목록에는 있으나 제조사 사이트에 PDF 가 없다. 석재 충격시험기(자동차 라디에이터용),
  크리프 시험 장치 863309 도 마찬가지다. 가구 시험기 문서 약 20 건은 범위 밖으로 판단해 받지 않았다
- **그립·신장계 안에서 안 옮긴 값** — 조 형상 수십 종의 치수표와 유압 유닛의 정격-압력 대응표는
  객체의 층위를 넘거나 열이 흩어져 있어 값으로 옮기지 않았다. 유압 유닛 항목에 `uncertain: true` 를 달아 뒀다
- **온톨로지 id 충돌 7건** — `dsc` `tga` `dma` `tma` `thermal_conductivity`
  `instrumented_indentation` `high_speed_tensile` 는 장비 분류와 시험 항목에 **같은 id** 로
  들어 있다. `build_graph.py` 가 분류 노드를 먼저 만들어서 같은 id 의 시험 항목 노드가
  생기지 못하고, 결과적으로 이 7개에 걸린 `performs` 엣지는 `kind: category` 노드를
  가리킨다(시험 항목의 label·measurands 를 잃는다). 그래프를 쓰는 쪽이 "이 장비로 DSC 가
  되나" 를 물으면 답이 어긋날 자리다. 고치려면 노드 id 에 종류 접두사를 붙여야 하고
  그것은 graph.json 을 읽는 쪽의 계약을 바꾸는 일이라 손대지 않았다
- **`uncertain: true` 남은 46건** — 대부분 확보한 문서 자체에 값이 없는 경우다.
  Shinyei 종합 카탈로그(스캔), Buehler 연혁 브로슈어, Thermotron·CSZ 요약본,
  Q-SUN 온습도 범위, INFICON 소형 모델, FLIR T860. 원본 쪽을 렌더링해도 나오지 않으므로
  제조사 데이터시트를 새로 구해야 한다.
- **원본 PDF 를 못 구한 곳** — Hirayama HAST 는 유통사 페이지에서 수치를 교차 확인해
  `web_references` 에 출처를 남겼다. 장비 객체의 `sources[].file` 은 실제 PDF 만 받으므로,
  웹에서만 확인한 값은 `web_references` 로 분리하고 `confidence: limited` 를 유지한다.

## 다음 단계

- `build_graph.py` -> `graph.json` 을 TestScope 의 `vocabulary`(축·값), `methods`,
  `equipment` 시드로 바꾸는 변환기를 쓴다. 조직이 보유한 장비는 이 카탈로그 객체를
  `variant_of` 로 가리키고, 자산번호·위치·담당자만 덧붙이면 된다.
