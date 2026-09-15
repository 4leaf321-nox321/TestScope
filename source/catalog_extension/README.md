# 카탈로그 보강 원료 (`source/catalog_extension/`)

카탈로그 객체(`source/catalog/equipment/`)는 제조사 PDF 에 적힌 것만으로 만들었다. 그 밖에 제조사가
웹에 올린 것 — 제품 페이지 · 응용 사례 · 규격 목록 · 부속품 · 사용 설명서 — 을 객체마다 모아 둔 곳이다.
**모은 것이지 정한 것이 아니다.** 여기 있는 규격·응용은 후보이고, 검토함에서 도메인 전문가가 고른 뒤에야
객체로 간다.

    시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
                                  ^^^^^^^^^^^^^^^^^^^^^^^
                                  여기를 두껍게 하려고 모은다

## 폴더

| 경로 | 내용 |
|---|---|
| `pages/<제조사>/<객체 id>/<n>.json` | 페이지 하나 — `url` · `retrieved` · `grade` · `status` · `kind`(html/pdf) · `title` · `text`(본문, 8만 자까지) · `standards_in_page` · `followed[]`(따라간 페이지, 4만 자까지) |
| `mentions/<객체 id>.json` | 본문에서 **기계가 뽑은 후보** — `standards_found`(코드: 횟수) · `standards_new`(카탈로그에 없던 것) · `standards_nearby`(따라간 공통 페이지의 규격 — 이 객체 것이 아닐 수 있다) · `test_item_hits`(시험 항목 이름이 몇 번) · `application_sentences`(「used for …」 문장) |
| `index.json` | 객체마다 쪽수 · 글자 수 · 규격 후보 수 · 새 규격 수 · PDF 후보 수 |
| `queries.json` | 객체마다 어떤 토막으로 사이트맵에서 무엇을 골랐나(되짚기용) · `pdf_candidates`(안 받은 .pdf 주소) |
| `sitemaps/<도메인>.json` | 제조사 사이트맵의 URL 전부(캐시). 지우면 다시 받는다 |
| `pdf_cache/` | 받은 PDF 원본. git 에 안 넣는다 — 글은 `pages/` 에 있다 |
| `extra_urls.json` | **입력** — 객체 id → 검색 엔진으로 사람이 찾은 남의 페이지(대리점·대학 장비실·리뷰·논문). `tools_harvest.py --extra` 가 받아 `pages/` 에 이어 붙인다. 등급은 도메인이 정한다(제조사 도메인이면 2, 아니면 3) |
| `papers/<객체 id>.json` | **논문에서 본 사용 예**(3등급) — OpenAlex(제목·초록·주제, 언급 논문 수)와 Europe PMC(오픈액세스 전문에서 「Instron 3400」 앞뒤 문장 = `usage_snippets`), 거기서 뽑은 규격·시험 항목 낌새 |
| `wiki/<제조사>.json` | Wikipedia 제조사 소개 한 단락 (배경 — 값이 아니다) |
| `standard_titles.json` | 규격 코드 → 제목·정식 표기·출처. `tools_standard_titles.py` 가 ANSI 웹스토어 검색과 모은 본문에서 찾는다. 반입(`catalog_import/methods.py`)과 검토함이 시험법을 만들 때 이 제목을 쓴다 |
| `tools_harvest.py` | 제조사 사이트맵 + extra_urls 를 모으는 도구. 다시 돌려도 있는 객체는 건너뛴다 |
| `tools_harvest_papers.py` | 논문·Wikipedia 를 모으는 도구 |
| `tools_propose.py` | 원료에서 검토함 물음 셋(규격·시험·소개 문장)을 세운다 → `source/catalog/proposals/series_*.json` |
| `tools_standard_titles.py` | 규격 제목을 찾는다 → `standard_titles.json` |
| `accessories/<제조사>/<n>.json` | 제조사 **부속·옵션 페이지**(그립·지그·챔버·익스텐소미터) — 사이트맵에서 부속 경로만 골라 받은 것. 17개 제조사 737쪽 |
| `accessory_mentions.json` | 부속 페이지마다 본문이 말하는 계열(사이트 메뉴에 늘 나오는 토막은 뺌)과, 그 페이지가 카탈로그의 부속 객체와 맞는지. `tools_harvest_accessories.py` 가 만든다 |

## 등급 — 카탈로그 PDF 보다 낮다

`source/research/README.md` 의 출처 등급을 그대로 쓴다.

| 등급 | 무엇 | 여기서는 |
|---|---|---|
| 1 | 제조사 PDF(카탈로그·데이터시트) | `source/catalog/pdf/` — 객체의 값은 여기서만 |
| 2 | 제조사 웹 페이지 | `pages/` 대부분. 사이트맵에서 골랐으므로 제조사 도메인이다 |
| 3 | 남의 페이지(대리점·대학 장비실·논문·리뷰) | `extra_urls.json` 으로 받은 `pages/` 와 `papers/` 전부 |

객체의 `limits`·`specs` 같은 **값은 여기서 고치지 않는다.** 여기서 얻는 것은 「이 계열이 이 규격을 한다」
「이 시험에도 쓴다」 「이 부속이 붙는다」 같은 **연결**이고, 그것도 검토함을 거친다.

## 어떻게 모았나

1. 객체가 이미 아는 `sources[].url`(연구 때 넣은 제조사 페이지)이 있으면 그것부터.
2. 제조사 사이트의 `sitemap.xml`(robots.txt 가 가리키는 것)을 받아 URL 전부를 두고, 객체 이름·기종명의
   토막(「6800」 「3119-160」 「platinous」)이 경로에 **낱말 경계로** 들어간 페이지를 점수로 고른다.
   모델 번호 토막이 하나는 맞아야 한다. 제품 페이지가 앞, 뉴스·영상이 뒤, 영어판이 앞(같은 글의
   de/ja/zh 판은 하나만). 객체마다 6쪽까지.
3. 제조사 「문헌」 페이지는 주소가 .pdf 로 안 끝나도 PDF 를 준다 — 받은 바이트의 앞머리로 가려
   pdftotext(poppler) 로 글을 뽑는다. `.pdf` 로 끝나는 주소는 받지 않고 `pdf_candidates` 로만 적는다
   (그것은 `catalog/tools_fetch_pdf.py` 의 일).
4. 페이지 안의 같은 도메인 링크 중 이 객체의 것(그 페이지 아래 · 객체 토막이 든 것)을 먼저, 응용·규격·
   부속·사양 같은 공통 페이지는 둘까지, 합쳐 4개 더 따라간다(한 층만). 공통 페이지의 규격은
   `standards_nearby` 로 따로 둔다 — 제조사 전체 규격 목록이지 이 계열의 것이 아니다.

검색 엔진은 스크립트로는 쓰지 못한다 — 몇 번 부르면 봇 확인 페이지가 온다(실측: DuckDuckGo·Brave·
Mojeek·Qwant·Yandex 모두 3~5회). 대신 **사람(과 Claude)이 검색해서 고른 주소를 `extra_urls.json` 에 적고**
`--extra` 로 받는다 — 2026-09-13 에 객체마다 「제조사 기종 applications」 로 찾아 대리점(DirectIndustry·
AZoM·LabWrench·ATEC)·대학 장비실·리뷰·arXiv 논문 페이지를 5~8개씩 넣었다. 요청 사이 1.5초, 403/429 는
8초 쉬고 한 번 더.

### 논문 (`tools_harvest_papers.py`)

- OpenAlex `works?search="Instron 3400" OR "Instron 34SC-5" …` — 언급 논문 수와 인용 많은 50편(제목·연도·
  저널·주제·초록). 키 없이 하루 약 100건까지 — 넘으면 `count` 가 null 로 남고, 다음 날 `--fill-openalex`
  로 채운다.
- Europe PMC — 같은 구절로 오픈액세스 논문을 찾고, 인용 많은 8편의 전문(XML)에서 「제조사 … 기종」 이
  40자 안에 같이 나오는 자리 앞뒤 350자를 `usage_snippets` 로 둔다. MDPI Materials·Polymers 가 PMC 에
  있어 재료 시험 논문이 꽤 잡힌다. 예: 「Tensile tests were measured using an Instron 34TM-5 universal
  testing system equipped with a 100 N sensor」.
- 구절은 `phrases_of()` 가 만든다: 제조사 이름(별칭 포함 — Bruker/Hysitron) + 계열 토막 + 기종 코드.
  이름이 같은 쌍둥이 객체(`-materialtwin`)는 `same_as` 로만 적는다.

## 이것으로 무엇을 했나 — 검토함 물음 셋

`tools_propose.py` 가 세운다(2026-09-13). 도메인 전문가가 검토함에서 고르면 그 자리에서 계열에 붙고,
`backend/scripts/export_review.py` 가 정본의 `decided` 에 되돌려 쓴다.

| 물음 | 원료 | 세운 것 |
|---|---|---|
| 계열이 하는 규격 더하기 | 페이지 본문·논문 문장의 규격 코드 (`standards_nearby` 는 안 씀) | 203 계열 · 후보 1,880 |
| 계열이 하는 시험 더하기 | 논문의 **기종을 언급한 그 문장** · 제조사 응용 문장 | 101 계열 · 후보 246 |
| 계열 소개에 넣을 문장 | 제조사 페이지의 「used for …」 문장 + OpenAlex 「논문 N편이 이 기종을 언급 — 주된 분야 …」 한 줄 | 162 계열 · 285 문장 |

안 세운 것: 부속·옵션 관계. 부속 페이지를 따로 받아 봤다(`tools_harvest_accessories.py`, 737쪽) — 261쪽이
계열을 말한다(「AutoX750 익스텐소미터: 5900·6800·3400 에」 「Shimadzu 세라믹 굽힘 지그: AG-X 계열에」). 그런데
그 부속 대부분이 **카탈로그에 객체로 없다**(부속 객체는 12개뿐). 양 끝이 다 카탈로그에 있는 새 쌍은 8건이고
그마저 약해서 검토함 물음으로 세우지 않았다. 이 원료의 쓸모는 관계가 아니라 **부속 객체를 카탈로그에 더하는
조사**(`source/catalog/equipment/` 에 그립·지그·챔버 객체를 만드는 일) 쪽이다 — 그때 `accessory_mentions.json`
의 「이 부속이 어느 계열을 말하나」 가 `relations` 의 초안이 된다.

## 2026-09-13 수집 결과

278 객체 · 1,953 쪽(제조사 2등급 467 · 남의 페이지 3등급 1,486 · 그중 PDF 197) · 규격 후보가 하나라도 나온
객체 206 · 카탈로그에 없던 규격 코드 1,194종(잡음 포함 — 검토함 전). 논문: Europe PMC 사용 문장 882개(150 객체),
OpenAlex 278 객체(사흘에 걸쳐 — 하루 예산 약 100건). 9-15 에 남은 객체도 채워 278 객체 전부 한 쪽 이상(2,073쪽).

## 다시 돌리기

    cd source/catalog_extension
    python tools_harvest.py                  # 전체 — 있는 객체는 건너뜀
    python tools_harvest.py --only espec     # 한 제조사
    python tools_harvest.py --only espec --redo
    python tools_harvest.py --extra          # extra_urls.json 의 주소를 더 받는다(있는 주소는 건너뜀)
    python tools_harvest_papers.py           # 논문·Wikipedia — 있는 객체는 건너뜀
    python tools_harvest_papers.py --fill-openalex   # OpenAlex 예산에 걸려 비었던 것만
    python tools_standard_titles.py          # 규격 제목 — 있는 코드는 건너뜀 (ANSI 웹스토어, 1.5초/건)
    python tools_propose.py                  # 검토함 물음 셋 다시 세우기 (decided 보존)

pdftotext 가 없으면 PDF 페이지의 `text` 가 비고 `kind` 만 `pdf` 로 남는다.
