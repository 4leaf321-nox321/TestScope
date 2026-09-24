"""설치가 심는 기준정보 — 축과 조건 정의.

**값(term)은 안 심는다.** 인장·압축이 어느 조직에나 같은 이름일 것 같지만, 실제로는
부서마다 부르는 말이 다르고 그것을 우리가 정해 주면 사람들은 자기 말로 하나를 더
만든다. 축만 세우고 값은 쓰는 사람이 채운다.

## 왜 마이그레이션이 아니라 여기인가

이것은 **행**이지 스키마가 아니다. 마이그레이션에 넣으면 시험(모델로 표를 만든다)이
그 행을 못 받아서 같은 목록을 시험 쪽에 한 벌 더 적게 되고, 두 벌은 반드시 갈린다.

## 멱등하다

설치 스크립트를 두 번 돌리는 일은 흔하다. 이미 있는 축의 이름이나 정책을 되돌리지
않는다 — 운영에서 고친 것을 설치가 덮으면 그것은 사고다.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.vocabulary.models import ConditionKey, Vocabulary
from app.modules.vocabulary.specs import SpecDefinition, SpecGroup

#: (slug, label, 어디의 축, 입력 정책, 부모 축, 순서, 설명)
#:
#: `test_item` 과 `property` 만 closed 다 — **검색의 첫 축**이라 오타가 값이 되면 그
#: 장비는 영영 검색에 안 걸린다. 나머지는 open: 막았을 때 사람이 어디로 가는지가 문제다.
#:
#: **어디의 축인지를 함께 적는다.** 한 목록에 일곱이 나란히 서면 「이게 어디 쓰이는
#: 값이지」 를 알 수 없고, 그때 제정기관 축에 회사 이름이 들어간다.
AXES: list[tuple[str, str, str, str, str | None, int, str]] = [
    (
        "test_item",
        "시험 항목",
        "common",
        "closed",
        None,
        10,
        "인장·압축·충격처럼 무엇을 재는가. 검색의 첫 축이라 오타가 값이 되면 안 걸린다. "
        "장비의 시험 항목·계열의 시험 항목·시험법이 모두 이 축을 가리킨다.",
    ),
    (
        "property",
        "물성 항목",
        "common",
        "closed",
        None,
        15,
        "인장강도·영률·유리전이온도처럼 시험으로 얻는 값. 검색이 「이 물성을 재려면」 으로 "
        "시작할 때의 첫 축이고, 값의 code 가 MaterialTwin 키(mechanical.yield_strength)라 "
        "재료 물성 쪽(MatNexus)과 같은 말을 쓴다. 시험 항목과 N:M 으로 이어진다.",
    ),
    (
        "equipment_category",
        "장비 분류",
        "catalog",
        "open",
        None,
        20,
        "만능재료시험기·충격시험기·경도계처럼 장비의 종류. 계열이 갖고, 보유 장비는 "
        "그 계열에서 물려받는다 — 카탈로그에 없는 장비만 직접 가리킨다.",
    ),
    ("manufacturer", "제조사", "catalog", "open", None, 30, "장비를 만든 회사."),
    (
        "form_factor",
        "기종 형태",
        "catalog",
        "open",
        None,
        35,
        "탁상형·바닥형·휴대형처럼 그 기종이 어떤 몸을 가졌나. 자리가 나는지, 들고 갈 "
        "수 있는지가 여기서 갈린다.",
    ),
    (
        "drive",
        "구동 방식",
        "catalog",
        "open",
        None,
        36,
        "전기기계식·유압식·진자식처럼 무엇으로 힘을 내나. 유압은 큰 하중을, 전기동력은 "
        "높은 주파수를, 진자는 충격을 낸다 — 할 수 있는 시험이 여기서 갈린다.",
    ),
    (
        "site",
        "보유 거점",
        "equipment",
        "open",
        None,
        40,
        "공장·연구소처럼 가려면 이동해야 하는 단위. 실무에서 가장 먼저 묻는 것.",
    ),
    (
        "calibration_provider",
        "교정 기관",
        "equipment",
        "open",
        None,
        45,
        "교정 성적서를 낸 곳. 자유 문자열로 두면 같은 기관이 「한국계량측정협회」 와 "
        "「(주)한국계량측정협회」 로 갈리고, 그 둘은 서로 다른 기관이 된다.",
    ),
    (
        "standard_body",
        "규격 제정기관",
        "method",
        "open",
        None,
        50,
        "ASTM · ISO · KS · 사내.",
    ),
    (
        "reliability_test_type",
        "신뢰성 시험 유형",
        "common",
        "open",
        None,
        55,
        "환경·기계·전기처럼 이 시험이 어느 갈래인가. 사내 시험 카드의 「유형」 칸이 "
        "이 축에서 고른다 — 글자로 두면 「환경」 과 「환경시험」 이 갈린다.",
    ),
    (
        "product_group",
        "적용군",
        "common",
        "open",
        None,
        56,
        "이 시험을 적용하는 제품군. 사내 시험 카드의 「적용군」 칸이 이 축에서 고른다. "
        "ERP·PLM 의 제품 코드를 가져올지는 아직 안 정했다(사내 신뢰성 반입 문서 5절).",
    ),
    (
        "reliability_category",
        "신뢰성 시험 분류",
        "common",
        "open",
        None,
        57,
        "사내 시험을 묶는 분류. 유형(환경·기계 …)보다 위이거나 옆인 갈래로, 회사마다 다르다 "
        "— 그래서 값을 코드로 심지 않고 축으로 연다.",
    ),
]

#: 축의 값이 갖는 칸. **설치가 심고, 이미 적힌 축은 안 덮는다.** 물성만 갖는다 —
#: 반입이 MaterialTwin 정의에서 기호·단위·설명을 넣고, 편집 화면이 이것을 보고 칸을 그린다.
ATTRIBUTE_SCHEMAS: dict[str, list[dict[str, str]]] = {
    "property": [
        {"key": "symbol", "label": "기호", "kind": "text", "help": "Rp0.2 · E · Tg"},
        {"key": "si_unit", "label": "SI 단위", "kind": "text", "help": "Pa · K · 1(무차원)"},
        {"key": "domain", "label": "분야", "kind": "text", "help": "mechanical · thermal …"},
        {"key": "description", "label": "설명", "kind": "text"},
        {"key": "test_standard", "label": "대표 규격", "kind": "text"},
        {
            "key": "condition_axes",
            "label": "조건 축",
            "kind": "list",
            "help": "temperature_k 처럼 값이 갈리는 축",
        },
    ],
}

#: (key, label, kind, 차원, 저장 단위, 표시 단위, 순서, 도움말)
#:
#: **저장 단위와 표시 단위를 같게 둔 것은 우연이 아니다.** 실무가 kN 과 degC 로
#: 말하는데 저장만 N·K 로 두면 화면마다 환산이 끼고, 환산이 여러 곳에 있으면
#: 언젠가 한쪽만 고쳐진다. 다른 단위가 필요해지는 날 그 조건 하나만 바꾼다.
CONDITIONS: list[tuple[str, str, str, str, str, str, int, str | None]] = [
    (
        "temperature",
        "시험 온도",
        "range",
        "temperature",
        "degC",
        "degC",
        10,
        "챔버·항온조로 낼 수 있는 시험 온도 범위.",
    ),
    (
        "force",
        "하중 용량",
        "range",
        "force",
        "kN",
        "kN",
        20,
        "이 장비가 낼 수 있는 하중. 상한을 비우면 제한 없음으로 읽힌다.",
    ),
    ("crosshead_speed", "크로스헤드 속도", "range", "speed", "mm/min", "mm/min", 30, None),
    ("frequency", "가진 주파수", "range", "frequency", "Hz", "Hz", 40, "동적 시험의 주파수."),
    (
        "specimen_thickness",
        "시편 두께",
        "range",
        "length",
        "mm",
        "mm",
        50,
        "지그가 물 수 있는 두께.",
    ),
    ("humidity", "상대 습도", "range", "ratio", "%", "%", 60, None),
    ("chamber", "항온조", "boolean", "", "", "", 70, "있나 없나. 온도 범위는 따로 적는다."),
    # 2026-09-12 — 사양이 있는데 이어 줄 축이 없어 검색이 못 쓰던 것들. 축은 사양 정의가
    # 잇는 만큼만 만든다(아래 SPEC_DEFINITION_LINKS): 잇는 정의가 없는 축은 검색 폼에
    # 아무도 안 쓰는 칸이 하나 늘 뿐이다.
    ("voltage", "전압", "range", "voltage", "V", "V", 80, "내전압·전원 시험이 거는 전압."),
    (
        "current",
        "전류",
        "range",
        "current",
        "A",
        "A",
        90,
        "접지 저항·전원 시험이 흘리는 전류.",
    ),
    (
        "torque",
        "토크",
        "range",
        "torque",
        "N·m",
        "N·m",
        100,
        "비틀림 시험기가 낼 수 있는 토크.",
    ),
    (
        "acceleration",
        "가속도",
        "range",
        "acceleration",
        "g",
        "g",
        110,
        "진동·충격 시험기가 낼 수 있는 가속도.",
    ),
    (
        "impact_energy",
        "충격 에너지",
        "range",
        "energy",
        "J",
        "J",
        120,
        "진자·낙하 해머가 가진 에너지. 샤르피·아이조드 시험이 이 축으로 묻는다.",
    ),
]

#: 사양 정의 키 -> 조건 축. **어디서 온 정의든** 이 키면 이 축이다.
#:
#: 정의는 세 길로 생긴다 — 이 파일의 `SPEC_DEFINITIONS`, 카탈로그 손 정의
#: (`catalog_specs.CATALOG_SPEC_DEFINITIONS`), 온톨로지 승격(`import_catalog`). 축 연결을
#: 각 길의 표에만 적으면 승격분은 이을 자리가 없고, 이미 만들어진 정의는 표를 고쳐도
#: 안 따라온다. 그래서 한 표에 모으고, `ensure_reference_data` 가 **비어 있는 연결만**
#: 채운다 — 사람이 화면에서 다른 축으로 바꿔 둔 것은 안 건드린다.
#:
#: 여기 없는 정의는 축이 없는 것이 맞다. 「공급 전압」 은 전원 사양이지 시험 능력이
#: 아니고, 차원이 같다고 이으면 220 V 콘센트가 「내전압 220 V 됨」 이 된다.
SPEC_DEFINITION_LINKS: dict[str, str] = {
    "force_capacity": "force",
    "force_capacity_range": "force",
    "test_load_series": "force",
    "test_load_micro": "force",
    "frequency_range": "frequency",
    "test_temperature": "temperature",
    "humidity_range": "humidity",
    "crosshead_speed": "crosshead_speed",
    "specimen_thickness": "specimen_thickness",
    "voltage_range": "voltage",
    "test_voltage": "voltage",
    "output_voltage": "voltage",
    "current_range": "current",
    "ground_bond_current": "current",
    "torque_capacity": "torque",
    "torque": "torque",
    "acceleration": "acceleration",
    "impact_energy": "impact_energy",
}

#: 종류를 바꿔야 하는 정의: 키 -> 새 종류. **문장을 구간으로** 만 있다.
#:
#: 경도계 하중은 「500 · 750 · 1000 kgf」 처럼 낱개로 오고, 처음엔 그것을 문장으로
#: 적었다. 문장은 축에 못 잇는다 — 67 기종의 경도계가 하중 사양을 갖고도 검색에는
#: 「모름」 으로 답했다. 양끝을 구간에 담고 목록은 비고에 남긴다(`_text_to_range`).
SPEC_KIND_UPGRADES: dict[str, str] = {
    "test_load_series": "range",
    "test_load_micro": "range",
}


#: (slug, label, 순서, 설명)
#:
#: 카탈로그 77개를 훑어 사람이 실제로 어떤 덩어리로 읽는지 본 결과다. 성능과 설치
#: 조건을 한 줄에 늘어놓으면 **보는 사람이 다르다** — 시험을 맡길 사람은 앞의
#: 셋만 보고, 자리를 낼 사람은 뒤의 하나만 본다.
SPEC_GROUPS: list[tuple[str, str, int, str]] = [
    ("capacity", "용량", 10, "이 장비가 낼 수 있는 크기 — 하중·토크·에너지."),
    ("range", "시험 범위", 20, "온도·속도·주파수처럼 어디부터 어디까지 되는가."),
    (
        "space",
        "시험 공간·시편",
        30,
        "무엇을 물릴 수 있나. 시편이 안 들어가면 나머지는 무의미하다.",
    ),
    (
        "accuracy",
        "정밀도·계측",
        40,
        "분해능·강성·정확도 등급. 규격이 요구하는 급을 맞추는지 보는 자리.",
    ),
    ("installation", "설치 조건", 50, "전원·치수·무게. 장비를 들이기 전에 답해야 하는 것."),
    ("configuration", "구성", 60, "구동 방식·스테이션 수·소프트웨어."),
]

#: (key, label, 그룹, kind, 차원, 단위, 검색축 조건 키, 반영 방향, 순서, 도움말)
#:
#: ## 어디서 왔나
#:
#: 제조사 카탈로그 116건에서 뽑은 장비 77개(모델 340여 개)의 사양 키를 세어
#: **자주 나오는 것부터** 심는다. weight_kg 190회, force_kN 131회, 시험 공간 100여
#: 회 — 이 순서가 곧 사람이 사양서에서 먼저 찾는 것의 순서다.
#:
#: ## 분류를 안 붙인다
#:
#: 전부 공통으로 심는다. 축의 **값**은 안 심는다는 이 파일의 원칙 때문이다 —
#: 붙일 장비 분류가 아직 없는데 분류를 붙이면, 설치 직후에는 어느 사양도 안 뜬다.
#: 좁히는 것은 자기 장비를 아는 사람이 나중에 한다(ADR 0005).
#:
#: ## 저장 단위와 표시 단위를 같게 둔다
#:
#: 조건 정의와 같은 이유다. 실무가 kN·degC 로 말하는데 저장만 N·K 이면 화면마다
#: 환산이 끼고, 그러면 언젠가 한쪽만 고쳐진다.
SPEC_DEFINITIONS: list[
    tuple[str, str, str, str, str, str, str | None, str, int, str | None]
] = [
    # --- 용량 ----------------------------------------------------------------
    (
        "force_capacity",
        "하중 용량",
        "capacity",
        "number",
        "force",
        "kN",
        "force",
        "max",
        10,
        "사양서의 최대 하중. 이 값은 시험 조건으로 따라 들어가 검색에 쓰인다.",
    ),
    ("dynamic_force", "동적 하중", "capacity", "number", "force", "kN", None, "max", 20, None),
    ("static_force", "정적 하중", "capacity", "number", "force", "kN", None, "max", 30, None),
    (
        "torque_capacity",
        "토크 용량",
        "capacity",
        "number",
        "torque",
        "N·m",
        "torque",
        "max",
        40,
        None,
    ),
    (
        "impact_energy",
        "충격 에너지",
        "capacity",
        "number",
        "energy",
        "J",
        "impact_energy",
        "max",
        50,
        "진자·낙하 해머가 가진 에너지.",
    ),
    (
        "test_load_series",
        "시험 하중 계열",
        "capacity",
        "range",
        "force",
        "kgf",
        "force",
        "max",
        60,
        "경도계가 고를 수 있는 하중의 양끝. 낱개 목록은 비고에 남는다.",
    ),
    (
        "frequency_range",
        "가진 주파수",
        "capacity",
        "range",
        "frequency",
        "Hz",
        "frequency",
        "max",
        70,
        None,
    ),
    # --- 시험 범위 ------------------------------------------------------------
    (
        "test_temperature",
        "시험 온도",
        "range",
        "range",
        "temperature",
        "degC",
        "temperature",
        "max",
        10,
        "챔버·퍼니스를 달았을 때 낼 수 있는 범위. 본체 운전 온도와 다르다.",
    ),
    (
        "heating_rate",
        "승온 속도",
        "range",
        "range",
        "temperature_rate",
        "K/min",
        None,
        "max",
        20,
        None,
    ),
    (
        "crosshead_speed",
        "크로스헤드 속도",
        "range",
        "range",
        "speed",
        "mm/min",
        "crosshead_speed",
        "max",
        30,
        None,
    ),
    ("return_speed", "복귀 속도", "range", "number", "speed", "mm/min", None, "max", 40, None),
    (
        "rotation_speed",
        "회전 속도",
        "range",
        "range",
        "rotational_speed",
        "rpm",
        None,
        "max",
        50,
        None,
    ),
    (
        "humidity_range",
        "시험 습도",
        "range",
        "range",
        "ratio",
        "%",
        "humidity",
        "max",
        60,
        None,
    ),
    (
        "chamber_mountable",
        "항온조 장착",
        "range",
        "boolean",
        "",
        "",
        None,
        "max",
        70,
        "검색축(항온조)과 잇지 않는다. 참거짓은 범위 비교가 성립하지 않아 "
        "시험 항목으로 옮길 수 없고, 옮긴 척하면 검색이 조용히 틀린다.",
    ),
    # --- 시험 공간·시편 -------------------------------------------------------
    (
        "vertical_test_space",
        "수직 시험 공간",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        10,
        "그립 사이에 남는 높이. 시편과 지그가 여기 안 들어가면 하중은 의미가 없다.",
    ),
    (
        "horizontal_test_space",
        "수평 시험 공간",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        20,
        "컬럼 사이 폭.",
    ),
    (
        "crosshead_travel",
        "크로스헤드 이동량",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        30,
        None,
    ),
    (
        "actuator_stroke",
        "액추에이터 스트로크",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        40,
        None,
    ),
    (
        "specimen_thickness",
        "시편 두께",
        "space",
        "range",
        "length",
        "mm",
        "specimen_thickness",
        "max",
        50,
        "지그가 물 수 있는 두께.",
    ),
    (
        "specimen_diameter",
        "시편 지름",
        "space",
        "range",
        "length",
        "mm",
        None,
        "max",
        60,
        None,
    ),
    ("specimen_height", "시편 높이", "space", "range", "length", "mm", None, "max", 70, None),
    (
        "throat_depth",
        "스로트 깊이",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        80,
        "경도계에서 시편을 얼마나 깊이 밀어 넣을 수 있나.",
    ),
    # --- 정밀도·계측 ----------------------------------------------------------
    (
        "position_resolution",
        "위치 분해능",
        "accuracy",
        "number",
        "length",
        "nm",
        None,
        "min",
        10,
        "작을수록 좋은 값이라 바닥으로 읽는다.",
    ),
    (
        "frame_stiffness",
        "프레임 강성",
        "accuracy",
        "number",
        "stiffness",
        "kN/mm",
        None,
        "max",
        20,
        "무른 프레임은 시편 대신 프레임이 늘어난다 — 탄성계수 측정에서 갈린다.",
    ),
    (
        "data_rate",
        "데이터 수집 속도",
        "accuracy",
        "number",
        "frequency",
        "Hz",
        None,
        "max",
        30,
        None,
    ),
    (
        "force_accuracy",
        "하중 정확도",
        "accuracy",
        "text",
        "",
        "",
        None,
        "max",
        40,
        "「±0.5% of reading down to 1/1000 of load cell capacity」 처럼 조건절이 붙는다. "
        "숫자 칸에 넣게 하면 사람은 조건절을 버리고, 그러면 그 값은 거짓이 된다.",
    ),
    (
        "accuracy_class",
        "정확도 등급",
        "accuracy",
        "text",
        "",
        "",
        None,
        "max",
        50,
        "ISO 7500-1 Class 0.5 · ASTM E83 Class B-1 처럼 규격이 매긴 급.",
    ),
    # --- 설치 조건 ------------------------------------------------------------
    (
        "power_supply",
        "전원",
        "installation",
        "text",
        "",
        "",
        None,
        "max",
        10,
        "「1PH 220 VAC 50/60 Hz」 처럼 상·전압·주파수가 한 문장으로 적힌다.",
    ),
    (
        "power_consumption",
        "소비 전력",
        "installation",
        "number",
        "power",
        "W",
        None,
        "max",
        20,
        "카탈로그가 VA·kVA 로 적은 것은 역률을 모르면 W 로 못 바꾼다 — 그때는 "
        "원문을 비고에 적는다.",
    ),
    (
        "dimension_width",
        "가로",
        "installation",
        "number",
        "length",
        "mm",
        None,
        "max",
        30,
        None,
    ),
    (
        "dimension_depth",
        "세로",
        "installation",
        "number",
        "length",
        "mm",
        None,
        "max",
        40,
        None,
    ),
    (
        "dimension_height",
        "높이",
        "installation",
        "number",
        "length",
        "mm",
        None,
        "max",
        50,
        None,
    ),
    (
        "weight",
        "무게",
        "installation",
        "number",
        "mass",
        "kg",
        None,
        "max",
        60,
        "바닥 하중과 반입 경로를 정한다. 카탈로그에 가장 흔하게 적힌 값이다.",
    ),
    (
        "operating_temperature",
        "운전 온도",
        "installation",
        "range",
        "temperature",
        "degC",
        None,
        "max",
        70,
        "**시험 온도가 아니다.** 장비 자체가 놓일 방의 온도다.",
    ),
    (
        "operating_humidity",
        "운전 습도",
        "installation",
        "range",
        "ratio",
        "%",
        None,
        "max",
        80,
        None,
    ),
    # --- 구성 ----------------------------------------------------------------
    (
        "drive_type",
        "구동 방식",
        "configuration",
        "choice",
        "",
        "",
        None,
        "max",
        10,
        "같은 하중이라도 구동이 다르면 할 수 있는 시험이 다르다 — 피로는 "
        "전기기계식으로 안 된다.",
    ),
    (
        "test_stations",
        "시험 스테이션 수",
        "configuration",
        "number",
        "count",
        "개",
        None,
        "max",
        20,
        "한 대에 몇 개를 동시에 거나. 크리프처럼 오래 거는 시험에서 처리량을 정한다.",
    ),
    (
        "software",
        "제어 소프트웨어",
        "configuration",
        "text",
        "",
        "",
        None,
        "max",
        30,
        None,
    ),
]

#: 고른 값 사양의 후보. 정의 표를 열 칸으로 늘리는 대신 여기 따로 둔다 — 서른 줄
#: 넘는 목록에서 대부분이 빈 칸인 열 하나는 읽는 사람을 방해할 뿐이다.
SPEC_CHOICES: dict[str, list[str]] = {
    "drive_type": [
        "전기기계식",
        "서보유압식",
        "전기동력식",
        "공진식",
        "진자식",
        "낙하식",
        "유압식",
        "공압식",
        "수동",
    ],
}


class ReferenceCounts(NamedTuple):
    """설치가 새로 심은 것의 수. **이름을 붙여 둔다** — 넷을 위치로 돌려주면
    부르는 쪽이 순서를 한 번 헷갈리는 것으로 요약 줄이 조용히 틀린다."""

    axes: int
    conditions: int
    spec_groups: int
    spec_definitions: int
    #: 이미 있던 정의에 축을 이어 준 수 · 문장을 구간으로 바꾼 값의 수.
    linked_definitions: int = 0
    converted_values: int = 0
    #: 보유 장비의 정식 속성 중 새로 심은 수.
    attributes: int = 0


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


#: 보유 장비의 **정식 속성** — 고정 칸에 없는 것만. 현장 장비 목록의 열(중분류·소분류·장비명·
#: 장비 용도·보유처·건물·설치 위치·담당자·자산번호·투자년도·예약 URL, 2026-09-18) 중 나머지는
#: 고정 칸이 이미 갖는다: 중분류·소분류 = 장비 분류의 군·유형, 장비명 = 장비명, 보유처 = 보유
#: 부서, 건물 = 거점, 설치 위치 = 설치 위치, 담당자 = 담당자, 자산번호 = 자산번호. 투자년도는
#: 도입일과 다른 물음(예산 집행 연도)이라 따로 둔다. 없을 때만 심는다 — 관리자가 끄거나 이름을
#: 바꾼 것을 설치가 되돌리면 안 된다.
#:
#:   (key, label, kind, unit, help, sort_order)
EQUIPMENT_ATTRIBUTES: tuple[tuple[str, str, str, str, str, int], ...] = (
    ("equipment_purpose", "장비 용도", "text", "", "이 장비로 무엇을 하나 — 한두 문장.", 1),
    (
        "investment_year",
        "투자 연도",
        "number",
        "",
        "예산이 집행된 해. 도입일(실제 들어온 날)과 다를 수 있다.",
        2,
    ),
    (
        "reservation_url",
        "장비 예약 URL",
        "text",
        "",
        "예약 시스템의 주소. http 로 시작하면 화면이 링크로 그린다.",
        3,
    ),
)


#: 신뢰성 시험의 **정식 속성** — 사내 시험 카드의 칸들(2026-09-23, 사용자가 부른 순서).
#: 이름·목적은 고정 칸이 이미 갖는다.
#:
#: **조건은 축마다 한 칸이다**(`kind="condition"`). 「-40~85 °C」 를 글로 적으면 사람은
#: 읽지만 `test_capability`(이 시험 돌릴 수 있는 장비)는 못 읽는다 — 그것이 이 플랫폼이
#: 하려는 일이다. 여기 없는 축(전압·토크 …)이 필요하면 `create_attribute_definition` 으로
#: 한 칸 더 만든다. 그 밖의 조건은 「기타 조건」 에 글로 적는다.
#:
#:   (key, label, kind, unit, 조건축 key, 기준정보 축 slug, help, sort_order)
RELIABILITY_ATTRIBUTES: tuple[
    tuple[str, str, str, str, str | None, str | None, str, int], ...
] = (
    (
        "reliability_type",
        "유형",
        "term",
        "",
        None,
        "reliability_test_type",
        "환경·기계·전기처럼 이 시험이 어느 갈래인가.",
        1,
    ),
    (
        "reliability_product_group",
        "적용군",
        "term",
        "",
        None,
        "product_group",
        "이 시험을 적용하는 제품군.",
        2,
    ),
    (
        "reliability_reference_method",
        "참조 규격",
        "method",
        "",
        None,
        None,
        "이 시험이 따르는 공인 규격(ASTM·IEC·KS …). 규격 사전에서 고른다 — 글자로 적으면 "
        "「IEC 60068-2-14」 와 「IEC60068-2-14」 가 갈린다.",
        3,
    ),
    (
        "reliability_category",
        "분류",
        "term",
        "",
        None,
        "reliability_category",
        "사내 시험을 묶는 분류. 없으면 기준정보에서 값을 더한다.",
        3,
    ),
    (
        "reliability_spec_document",
        "규격서",
        "document",
        "",
        None,
        None,
        "이 시험이 적힌 **사내 규격서**를 목록에서 고른다(「공통 → 사내 규격서」 에서 "
        "등록하고 파일을 올린다). 공개 규격(ASTM·ISO)은 위의 「참조 규격」 이다.",
        4,
    ),
    (
        "reliability_document_type",
        "문서 유형",
        "term",
        "",
        None,
        "document_type",
        "규격서·지침서·작업표준처럼 이 문서가 어느 갈래인가.",
        5,
    ),
    (
        "reliability_target",
        "시험 대상",
        "text",
        "",
        None,
        None,
        "무엇을 시험하나 — 완제품·모듈·부품·시편 중 무엇이고 어느 상태인가.",
        9,
    ),
    (
        "reliability_equipment_note",
        "시험기·비품",
        "text",
        "",
        None,
        None,
        "이 시험에 쓰는 장비와 비품. **어느 장비로 되는지는 서버가 조건으로 찾는다** "
        "— 여기는 지그·치구처럼 조건으로 안 잡히는 것을 적는 자리다.",
        10,
    ),
    (
        "reliability_sample_count",
        "시료 수",
        "number",
        "개",
        None,
        None,
        "한 번 돌릴 때의 시료 수. 등급·단계마다 다르면 「등급별 수량」 에 적는다.",
        11,
    ),
    (
        "reliability_other_conditions",
        "기타 조건",
        "text",
        "",
        None,
        None,
        "위 조건 칸으로 안 잡히는 것 — 사이클 수·유지 시간·승온 속도·분위기 가스 등. "
        "**여기 적은 것은 장비 판정에 안 쓰인다**(글자라서). 판정에 쓰려면 조건 칸을 "
        "하나 더 만든다.",
        12,
    ),
    (
        "reliability_procedure",
        "시험 절차",
        "text",
        "",
        None,
        None,
        "순서대로 무엇을 하나. 프로파일이 있으면 단계별로.",
        13,
    ),
    (
        "reliability_method",
        "시험 방법",
        "text",
        "",
        None,
        None,
        "어떤 방식으로 재나 — 절차와 달리 「무엇을 어떻게 측정하는가」 다.",
        14,
    ),
    (
        "reliability_criteria",
        "판정 기준",
        "text",
        "",
        None,
        None,
        "무엇을 합격으로 보나. 수치 기준이면 값과 단위를 같이 적는다.",
        15,
    ),
    (
        "reliability_caution",
        "주의사항",
        "text",
        "",
        None,
        None,
        "안전·취급·해석에서 놓치면 안 되는 것.",
        16,
    ),
    (
        "reliability_grade_counts",
        "등급별 수량",
        "pairs",
        "개",
        None,
        None,
        "등급마다 몇 개인가 — 「A등급 4 · B등급 4」. 이름과 숫자를 짝으로 적는다. "
        "**이름 없는 숫자는 못 읽는다**: 「4」 만 남으면 그것이 A등급인지 알 수 없다.",
        17,
    ),
    (
        "reliability_stage_counts",
        "단계별 수량",
        "pairs",
        "개",
        None,
        None,
        "단계마다 몇 개인가 — 「1단계 8 · 2단계 4」. 등급과 단계가 함께 갈리면 "
        "「적용 사양 매트릭스」 를 쓴다.",
        18,
    ),
    (
        "reliability_spec_matrix",
        "적용 사양 매트릭스",
        "matrix",
        "개",
        None,
        None,
        "사양마다 등급·단계가 따로 정해질 때 — 사양 한 줄에 그 사양의 짝들을 적는다. "
        "「사양 A: A등급 4 · B등급 2」.",
        19,
    ),
)


#: 조건 칸은 **축 목록에서 만든다.** 손으로 넷만 적어 두었더니 「전압으로 도는 시험」 을
#: 적을 자리가 없었다(2026-09-23) — 축이 늘면 칸도 따라 는다. 수치가 아닌 축(항온조 같은
#: boolean)은 빼고, 조건 갈래의 자리(5)부터 축의 차례대로 선다.
def _converge_reliability_attributes(db: Session) -> int:
    """이미 있는 칸을 표에 맞춘다 — **값이 하나도 없을 때만.**

    「규격서」 를 글자로 심었다가 목록에서 고르는 것으로 바꿨다(2026-09-23). 심는 쪽은
    「없는 것만」 이라 이미 깔린 설치는 글자인 채로 남는데, 그러면 같은 문서가 판마다
    다른 값이 되어 「이 규격서를 쓰는 시험」 을 못 묶는다.

    **값이 하나라도 적혀 있으면 안 바꾼다.** 종류를 바꾸는 순간 그 값이 읽히지 않는
    칸에 남고, 그것은 조용한 데이터 손실이다. 이름은 건드리지 않는다 — 관리자가 고친
    이름을 설치가 되돌리면 안 된다(사양 정의의 `converge_spec_definitions` 와 같은 판단).
    """
    axes = {slug: vid for vid, slug in db.execute(select(Vocabulary.id, Vocabulary.slug))}
    changed = 0
    for (
        key,
        _label,
        kind,
        _unit,
        _condition_key,
        axis_slug,
        _help,
        _order,
    ) in RELIABILITY_ATTRIBUTES:
        if kind != "term" or axis_slug not in axes:
            continue
        row = db.scalar(select(AttributeDefinition).where(AttributeDefinition.key == key))
        if row is None or row.kind == "term":
            continue
        used = db.scalar(
            select(func.count())
            .select_from(AttributeValue)
            .where(AttributeValue.definition_id == row.id)
        )
        if used:
            continue
        row.kind = "term"
        row.vocabulary_id = axes[axis_slug]
        row.unit = ""
        changed += 1
    return changed


def _condition_attributes(
    db: Session,
) -> list[tuple[str, str, str, str, str | None, str | None, str, int]]:
    rows: list[tuple[str, str, str, str, str | None, str | None, str, int]] = []
    order = 5
    for key in db.scalars(
        select(ConditionKey)
        .where(ConditionKey.kind == "range", ConditionKey.is_active.is_(True))
        .order_by(ConditionKey.sort_order, ConditionKey.key)
    ):
        rows.append(
            (
                f"reliability_cond_{key.key}",
                key.label,
                "condition",
                key.display_unit or key.si_unit,
                key.key,
                None,
                "최소·최대 중 **하나만 적어도 된다** — 비운 쪽은 「제한 없음」 이다. "
                "숫자 없이 비고만 적으면 사람은 읽지만 장비 판정에는 안 쓰인다.",
                order,
            )
        )
        order += 1
    return rows


def ensure_reliability_attributes(db: Session) -> int:
    """신뢰성 시험의 정식 속성을 심는다 — key 로 찾아 **없는 것만.**

    관리자가 끄거나 이름을 바꾼 것을 설치가 되돌리면 안 된다(보유 장비 속성과 같은 규칙).
    조건 축·기준정보 축이 아직 없으면 그 칸은 **안 심는다** — 빈 축을 가리키는 속성은
    화면에서 고를 것이 없는 칸으로 서고, 그것은 사람이 「고장」 으로 읽는다.
    """
    known = set(db.scalars(select(AttributeDefinition.key)))
    # **이름도 본다.** (대상, 이름)에 유일 색인이 걸려 있어서, key 가 달라도 이름이 같으면
    # 넣다가 터진다 — 손으로 적던 조건 넷을 축 목록으로 옮길 때 실제로 겹쳤다.
    taken = {
        label.lower()
        for label in db.scalars(
            select(AttributeDefinition.label).where(
                AttributeDefinition.target == "reliability_test",
                AttributeDefinition.is_active.is_(True),
            )
        )
    }
    conditions = {
        key: cid for cid, key in db.execute(select(ConditionKey.id, ConditionKey.key))
    }
    axes = {slug: vid for vid, slug in db.execute(select(Vocabulary.id, Vocabulary.slug))}
    added = 0
    for (
        key,
        label,
        kind,
        unit,
        condition_key,
        axis_slug,
        help_text,
        order,
    ) in [*RELIABILITY_ATTRIBUTES, *_condition_attributes(db)]:
        if key in known or label.lower() in taken:
            continue
        taken.add(label.lower())
        if kind == "condition" and condition_key not in conditions:
            continue
        if kind == "term" and axis_slug not in axes:
            continue
        db.add(
            AttributeDefinition(
                target="reliability_test",
                key=key,
                label=label,
                kind=kind,
                unit=unit,
                status="standard",
                condition_key_id=conditions.get(condition_key) if condition_key else None,
                vocabulary_id=axes.get(axis_slug) if axis_slug else None,
                help=help_text,
                sort_order=order,
            )
        )
        added += 1
    return added


def ensure_equipment_attributes(db: Session) -> int:
    """보유 장비의 정식 속성을 심는다 — key 로 찾아 없는 것만."""
    known = set(db.scalars(select(AttributeDefinition.key)))
    added = 0
    for key, label, kind, unit, help_text, order in EQUIPMENT_ATTRIBUTES:
        if key in known:
            continue
        db.add(
            AttributeDefinition(
                target="equipment",
                key=key,
                label=label,
                kind=kind,
                unit=unit,
                status="standard",
                help=help_text,
                sort_order=order,
            )
        )
        added += 1
    return added


def _text_to_range(text: str) -> tuple[float, float, str | None] | None:
    """「500 · 750 · 1000」 · 「min 0.5 · max 250」 -> (최소, 최대, 비고). 숫자가 없으면 None.

    낱개 목록이면 **목록을 비고에 남긴다.** 양끝만 남기면 「250 kgf 까지 됨」 은 답해도
    「187.5 kgf 로 되나」 는 못 답한다 — 경도계는 그 사이 값을 못 건다.
    """
    numbers = [float(one) for one in _NUMBER.findall(text)]
    if not numbers:
        return None
    is_pair = text.lstrip().lower().startswith("min ") and len(numbers) == 2
    note = None if is_pair else f"고를 수 있는 값 {text.strip()}"
    return min(numbers), max(numbers), note


def converge_spec_definitions(db: Session) -> tuple[int, int]:
    """이미 있는 정의를 표(`SPEC_DEFINITION_LINKS` · `SPEC_KIND_UPGRADES`)에 맞춘다.

    **비어 있는 것만 채운다.** 축이 이미 이어진 정의는 — 표와 다르더라도 — 사람이
    화면에서 정한 것이니 그대로 둔다. 종류 바꾸기는 문장 -> 구간 한 방향뿐이고,
    이미 구간이면 할 일이 없다. 두 번 돌려도 같다.
    """
    from app.modules.equipment.models import ModelSpecValue

    conditions = {
        key: cid for cid, key in db.execute(select(ConditionKey.id, ConditionKey.key))
    }
    definitions = {
        row.key: row
        for row in db.scalars(
            select(SpecDefinition).where(
                SpecDefinition.key.in_(set(SPEC_DEFINITION_LINKS) | set(SPEC_KIND_UPGRADES))
            )
        )
    }
    linked = converted = 0
    for key, new_kind in SPEC_KIND_UPGRADES.items():
        definition = definitions.get(key)
        if definition is None or definition.kind != "text" or new_kind != "range":
            continue
        for value in db.scalars(
            select(ModelSpecValue).where(ModelSpecValue.definition_id == definition.id)
        ):
            parsed = _text_to_range(value.text_value or "")
            if parsed is None:
                # 숫자가 없는 문장은 비고로 내려 둔다 — 지우면 그 값이 무엇이었는지
                # 알 수 없게 된다.
                value.note = " · ".join(x for x in (value.note, value.text_value) if x) or None
                value.text_value = None
                continue
            low, high, note = parsed
            value.num_min, value.num_max = low, high
            value.note = " · ".join(x for x in (value.note, note) if x) or None
            value.text_value = None
            converted += 1
        definition.kind = new_kind
    for key, condition_key in SPEC_DEFINITION_LINKS.items():
        definition = definitions.get(key)
        if definition is None or definition.condition_key_id is not None:
            continue
        if condition_key not in conditions:
            continue
        definition.condition_key_id = conditions[condition_key]
        linked += 1
    return linked, converted


def ensure_reference_data(db: Session) -> ReferenceCounts:
    """없는 축·조건·사양 정의만 만들고, 있는 정의는 축 연결이 비었으면 이어 준다."""
    known_axes = set(db.scalars(select(Vocabulary.slug)))
    added_axes = 0
    for slug, label, domain, policy, parent, order, description in AXES:
        if slug in known_axes:
            continue
        db.add(
            Vocabulary(
                slug=slug,
                label=label,
                domain=domain,
                entry_policy=policy,
                parent_slug=parent,
                sort_order=order,
                description=description,
            )
        )
        added_axes += 1

    # 속성 칸: 비어 있는 축에만 심는다 — 화면에서 고친 것을 설치가 되돌리면 사고다.
    # 세션이 autoflush 를 안 하므로 방금 더한 축을 찾으려면 먼저 내보내야 한다.
    db.flush()
    for slug, schema in ATTRIBUTE_SCHEMAS.items():
        axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
        if axis is not None and not axis.attribute_schema:
            axis.attribute_schema = schema

    known_keys = set(db.scalars(select(ConditionKey.key)))
    added_keys = 0
    for key, label, kind, dimension, si_unit, display_unit, order, help_text in CONDITIONS:
        if key in known_keys:
            continue
        db.add(
            ConditionKey(
                key=key,
                label=label,
                kind=kind,
                dimension=dimension,
                si_unit=si_unit,
                display_unit=display_unit,
                sort_order=order,
                help=help_text,
            )
        )
        added_keys += 1

    # 그룹을 먼저 심고 커밋한다 — 사양 정의가 그룹 id 를 가리킨다.
    known_groups = {
        slug: gid for gid, slug in db.execute(select(SpecGroup.id, SpecGroup.slug))
    }
    added_groups = 0
    for slug, label, order, description in SPEC_GROUPS:
        if slug in known_groups:
            continue
        group = SpecGroup(slug=slug, label=label, sort_order=order, description=description)
        db.add(group)
        db.flush()
        known_groups[slug] = group.id
        added_groups += 1

    condition_ids = {
        key: cid for cid, key in db.execute(select(ConditionKey.id, ConditionKey.key))
    }
    known_definitions = set(db.scalars(select(SpecDefinition.key)))
    added_definitions = 0
    for (
        key,
        label,
        group_slug,
        kind,
        dimension,
        unit,
        condition_key,
        reflect_as,
        order,
        help_text,
    ) in SPEC_DEFINITIONS:
        if key in known_definitions:
            continue
        db.add(
            SpecDefinition(
                key=key,
                label=label,
                group_id=known_groups[group_slug],
                kind=kind,
                dimension=dimension,
                si_unit=unit,
                display_unit=unit,
                choices=SPEC_CHOICES.get(key, []),
                # **조건이 없으면 안 잇는다.** 없는 조건을 만들어 이으면 검색 폼에
                # 아무도 안 쓰는 축이 하나 늘고, 그 축은 지워지지도 않는다.
                condition_key_id=condition_ids.get(condition_key) if condition_key else None,
                reflect_as=reflect_as,
                sort_order=order,
                help=help_text,
            )
        )
        added_definitions += 1

    db.flush()
    # **축·조건을 먼저 내보낸 뒤에 심는다** — 신뢰성 속성이 방금 만든 축을 가리킨다.
    added_attributes = ensure_equipment_attributes(db) + ensure_reliability_attributes(db)
    _converge_reliability_attributes(db)
    linked, converted = converge_spec_definitions(db)

    db.commit()
    return ReferenceCounts(
        added_axes,
        added_keys,
        added_groups,
        added_definitions,
        linked,
        converted,
        added_attributes,
    )
