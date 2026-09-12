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
