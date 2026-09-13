# 검토함의 정본 (`proposals/`)

반입이 못 정한 것을 **후보·추천·근거**와 함께 적어 두는 자리다. 개발자가 미리 적고, 배포
패키지에 실려 운영으로 가며, 화면(「관리 → 검토함」)에서 **도메인 전문가가 고른다.** 고른
것은 `backend/scripts/export_review.py` 가 `decided` 로 되돌려 써서 다음 반입이 다시 묻지
않고 적용한다.

| 파일 | 물음 | subject | 후보 |
|---|---|---|---|
| `method_test_items.json` | 이 규격은 어느 시험의 것인가 | 규격 코드 | 시험 항목 코드(인용한 계열의 시험이 파생 후보로 더해짐) |
| `test_item_axes.json` | 이 시험은 무슨 조건을 묻나 | 시험 항목 코드 | 조건 키 — 여러 개 |
| `property_links.json` | 이 시험으로 이 물성이 나오나 | `시험코드:물성코드` | `confirm` / `reject` |
| `free_spec_definitions.json` | 이 사양을 정의로 올리나 | `원본키|단위` | `promote` / `keep` + `definition` |
| `method_cleanup.json` | 이 규격을 지우나 · 합치나 | 규격 코드 | `keep` / `delete` / `merge:<규격>` (`merge_into` 에 적은 것) |
| `test_item_properties.json` | 이 시험이 내는 물성은 | 시험 항목 코드 | 물성 코드 — 여러 개 (추천만 후보, 나머지는 직접 고르기) |
| `condition_axes.json` | 새 검색축을 만드나 | 축 키 | `create` / `skip` + `axis`(label·dimension·unit) · `definitions` · `test_items` |
| `series_standards.json` | 이 계열이 이 규격도 하나 | 카탈로그 객체 id (+ `series` 이름 · `manufacturer` 로 계열을 찾는다) | 규격 코드 — 여러 개. 후보가 `{code, reason, sources[]}` 로 출처를 든다. `source/catalog_extension/tools_propose.py` 가 만든다 — 손으로 안 고친다 |
| `series_test_items.json` | 이 계열이 이 시험도 하나 | 카탈로그 객체 id (위와 같음) | 시험 항목 코드 — 여러 개. 후보가 `{code, reason(인용문), sources[]}`. 같은 도구가 만든다 |
| `series_summary.json` | 이 문장을 계열 소개에 넣을까 | 카탈로그 객체 id (위와 같음) | `s1`…`s5` — 여러 개. 후보가 `{code, label(문장), sources[]}`. 같은 도구가 만든다 |

줄의 모양:

```json
{"subject": "ASTM D3580",
 "candidates": ["mechanical_shock", "vibration_sine_random"],
 "recommended": "vibration_sine_random",
 "reason": "ASTM D3580 — 제품의 수직 선형 진동 시험",
 "decided": {"choice": ["vibration_sine_random"], "by": "김전문", "on": "2026-09-20", "note": null}}
```

- `recommended` 는 **확실한 것만**. 확신이 없거나 규격군 이름이면 `hint` 만 적는다 —
  왜 추천을 안 붙였는지가 화면에 보인다. 근거 없는 추천은 첫 보기를 누르게 할 뿐이다.
- `decided` 는 사람이 손으로 적지 않는다. 화면에서 고르고 `export_review.py` 로 되돌린다.
- `recommended`·`reason`·`hint` 는 되돌려 쓸 때 안 건드린다.
