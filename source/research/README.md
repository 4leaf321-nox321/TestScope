# 사양 조사 — 사양이 하나도 없던 기종 126종

2026-09-12. 「사양값도 이 기종만의 사양도 없는 기종」 126종을 인터넷에서 찾아 채웠다.
결과 **126 → 12**. 남은 12 는 아래 「못 채운 것」 에 이유와 함께 적었다.

## 출처의 등급 — 어디서 온 값인지 객체가 말한다

카탈로그 객체의 `sources[]` 가 출처의 성격을 갖는다(`catalog/schema.json`). 이것이
곧 신뢰 등급이다 — 값에 따로 등급을 달지 않고, **어디서 왔는지로 가른다.**

| 등급 | `sources[]` 모양 | 뜻 | 이번 조사 |
|---|---|---|---|
| 1 | `file` (+`pages`) | 제조사 카탈로그 **PDF 원문**. `source/pdf/` 에 있고 `catalog/urls.json` 에 URL. 다시 받을 수 있다 | 공식 PDF 27건 새로 받음 |
| 2 | `url` + `retrieved` | 제조사 **웹 페이지** 사양표. PDF 가 다운로드 폼 뒤에 있거나 없는 경우. 페이지가 바뀌면 값을 되짚을 수 없다 | 24곳 |
| 3 | `url` + `retrieved` + 비고에 「후속 세대」「판매처」「대학 미러」 | 제조사가 아닌 곳이 옮겨 적었거나, 단종되어 **후속 모델 사양**으로 대신한 것 | 비고에 명시 |
| — | `origin` | MaterialTwin 행. 값은 능력행에서 옮김 | (기존) |

MaterialTwin 은 `quality_tier` 1~4 (제품에 인쇄된 값 / 핸드북 / 2차 인용 / 추정)를
쓴다. 우리 등급 1·2·3 이 그 1·(1)·3 에 해당한다. **추정값(4)은 넣지 않았다** — 값이
없으면 비워 두고 비고에 이유를 적었다(ADR 0003).

`source/pdf/` 와 `source/extracted/` 는 git 에 안 들어간다(용량). `urls.json` 이 정본이라
`catalog/tools_fetch_pdf.py --restore` 로 언제든 되살린다.

## 채운 것

| 제조사 | 기종 | 출처 | 채운 사양 |
|---|---|---|---|
| Mitutoyo | HM-210/220 ×12 · HM-122/124 · HV-110/112/114/120 · AVK-C0 · AR-10/20 · ARK/ATK-600 · ABK-1 · HR-511~523 · HR-610A/620A/620B · MZT-500 · SJ-411/412 | PDF (E4104 · E17001 · K section · HR-600 bulletin · SJ-410 bulletin) | 시험력 범위·단계, 척도, 시편 높이·깊이, 치수·질량; 조도계 Z 범위·분해능·측정력 |
| ESPEC | AR(ARS/ARG/ARL/ARU) · Criterion BTZ/BTU/BTL/BTX · TSA · TSB · TSE · EHS · PV/PH/STPH/SSPH · SU/SH · Lab · Agree ET | PDF 9건(co.jp) + Criterion(NA); Lab·ET 는 웹 | 온도·습도 범위, 용적, 승온·냉각 속도, 내부 치수, 압력 |
| Anton Paar | Hit 300 · NST3 · UNHT3 Bio · TRB RH · MCR 72/92 · SmartMelt/SmartPave | 제조사 페이지(웹); MCR 72/92 는 후속 MCR 53/73/93 | 하중·깊이·분해능, 토크·각속도·주파수 |
| Chroma · Hioki | 17011 리니어/회생 · ST5520-01 | 기존 PDF | 전압·전류·채널 |
| JEOL | JSM-IT500HR/700HR · JEM-F200 · JAMP-9510F · JPS-9030 · JSX-1000S · JXA-iHP200F/iSP100 · Synergy-ED | IT500HR 는 대학 사양표 PDF, 나머지 웹 | 가속 전압, 분해능, 시편 크기, 관전압 |
| Rigaku · Zeiss · Bruker · Keithley · Thermo · Park · Oxford | ZSX Primus 400 · SmartLab · Xradia 410/520/610/620 · GEMINI · VERTEX 70/70v · AVANCE · 4200(A)-SCS · Nexsa G2 · NX10 · Symmetry S2 | PDF(ZSX·Synergy·VERTEX·4200A·4200·Nexsa·NX10·Symmetry) / 웹(SmartLab·Xradia·GEMINI·AVANCE) | 관출력·전압, 공간 분해능·복셀, 분광 범위·분해능, SMU 범위, 스팟, 스캔 범위 |
| Renishaw · Hitachi · Nordson · Metrohm · Malvern · PerkinElmer · HORIBA · Agilent · Hirayama · Helmut Fischer · Instron · ZwickRoell | inVia ×3 · SU3800/3900 · Gen7 · 851 · Mastersizer 3000 · Frontier · GD-Profiler 2 · 5977C · PC-702R8 · XDL/XDLM/XUL/XULM · CEAST MF10/50 · Z020/Z030 | 웹 / 기존 PDF / Agilent 데이터시트 PDF | 각 장비의 대표 범위 |

## 발견한 것 — 사양이 없던 이유가 「못 찾아서」 만이 아니었다

1. **보탬 객체가 빈 기종을 세우고 있었다.** MaterialTwin 보탬 객체(`supplements`, 기종 없음)
   12건에서 반입이 계열 이름을 단 자리표시 기종을 만들었다(「Instron 9400 Series … Drop
   Tower」 라는 이름의 기종). 반입을 고쳤고(`step_models`) 개발 DB 의 12건을 지웠다.
2. **파일럿 데이터가 섞여 있다.** 「5982」「Criterion 43」「HIT450P」「HR-530」 은 계열 이름이
   기종 이름과 같은 손 데이터(2026-09-09, 출처 없음, 보유 장비 1대씩)다. 카탈로그에 같은
   기종이 사양과 함께 있다 — 그 보유 장비를 카탈로그 기종에 다시 잇고 이 계열은 지우면
   된다(「기종 미연결 장비」 작업).
3. **단종·후속 세대.** Anton Paar MCR 72/92, ESPEC Lab/ET, Zeiss SUPRA, JEOL IT500/700HR
   은 제조사 페이지에서 내려갔거나 후속으로 바뀌었다. 후속 사양을 넣은 곳은 비고에 적었다.

## 못 채운 것 (12)

| 기종 | 이유 |
|---|---|
| 5982 · Criterion 43 · HIT450P · HR-530 | 파일럿 손 데이터 — 카탈로그 기종에 있음(위 2) |
| PPA 시리즈 기타 모델 · WT5000 전류센서 엘리먼트 | 「그 밖」 묶음 줄 — 사양이 있을 수 없다 |
| Criterion ECT-3 | ESPEC NA 브로슈어에 없음(구형) |
| ETS-Lindgren ELF 자기 차폐 | 주문 설계 설비 — 표준 사양표가 없다 |
| Hirayama PC-304R8D/422R8D 듀얼 | 단일형 사양(PC-702R8 행)은 채움; 듀얼은 판매처 페이지에 수치 없음 |
| Lansmont PDT-80M · Shinyei ASQ · Thermotron S/SM | 제조사 사이트가 사양을 PDF 폼 뒤에 둠 — 다음 조사 |

## 다시 돌리는 법

```
python source/catalog/tools_fetch_pdf.py <vendor> <file.pdf> <url>   # 받고 뽑고 urls.json 에 적음
python source/catalog/tools_fetch_pdf.py --restore                   # 다른 PC: urls.json 으로 전부 되살림
python source/catalog/build_graph.py
python backend/scripts/import_catalog.py
```

이번에 쓴 새 사양 키 55종은 `ontology/condition_keys.json` 에 등록했다(등록 안 된 키는
반입이 「이 기종만의 사양」 으로 들인다).
