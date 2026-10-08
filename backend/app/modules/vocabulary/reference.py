"""설치가 심는 온톨로지 — 축과 조건 정의.

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
from app.modules.vocabulary.catalog_specs import CATALOG_SPEC_DEFINITIONS
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.modules.vocabulary.seed_texts import RETIRED
from app.modules.vocabulary.specs import SpecDefinition, SpecGroup
from app.shared.text import compare_key

#: (slug, label, 어디의 축, 입력 정책, 부모 축, 순서, 설명)
#:
#: `test_item` 과 `property` 만 closed 다 — **검색의 첫 축**이라 오타가 값이 되면 그
#: 장비는 영영 검색에 안 걸린다. 나머지는 open: 막았을 때 사람이 어디로 가는지가 문제다.
#:
#: **어디의 축인지를 함께 적는다.** 한 목록에 일곱이 나란히 서면 「이게 어디 쓰이는
#: 값이지」 를 알 수 없고, 그때 제정기관 축에 회사 이름이 들어간다.
#: 축을 심을 때 **값까지** 함께 심는 것. `(code, 보여 주는 값)`.
#:
#: 사업부는 회사 구조라 설치한 사람이 지어낼 것이 아니다. 비어 있으면 부서에 아무것도
#: 못 붙이고, 그러면 신뢰성 시험 등록이 통째로 막힌다. 여기에 없는 사업부는 화면에서
#: 더한다(닫힌 축이라 시스템 관리자만).
DEFAULT_TERMS: dict[str, list[tuple[str, str]]] = {
    "division": [
        ("mx", "MX"),
        ("vd", "VD"),
        ("da", "DA"),
        ("nw", "NW"),
        ("medical", "의료기기"),
        ("gtr", "GTR"),
        ("sr", "SR"),
        ("cs", "CS"),
    ],
    # **소재는 대분류만 심는다.** 칸(장비의 「소재 종류」)이 이 축의 값을 고르게 하는데, 값
    # 고르기는 있는 값만 보여 준다 — 비어 있으면 칸을 만들어 놓고 아무도 못 쓴다. SUS304 ·
    # PC+ABS 같은 세부는 쓰는 사람이 더한다(열린 축). 세부까지 심으면 회사가 안 쓰는 이름이
    # 목록을 채운다.
    "material": [
        ("metal", "금속"),
        ("plastic", "플라스틱"),
        ("rubber", "고무·엘라스토머"),
        ("composite", "복합재"),
        ("ceramic", "세라믹"),
        ("glass", "유리"),
        ("textile", "섬유"),
    ],
}

AXES: list[tuple[str, str, str, str, str | None, int, str]] = [
    (
        "division",
        "사업부",
        "common",
        "closed",
        None,
        5,
        "MX, VD, DA 등 회사를 구분하는 단위. 부서(조직도)에 지정하면 하위 부서 전체에 적용됨. "
        "신뢰성 시험은 부서가 아닌 사업부에 소속되며, 조직 개편으로 팀이 이동해도 유지됨.",
    ),
    (
        "test_item",
        "시험 항목",
        "common",
        "closed",
        None,
        10,
        "인장, 압축, 충격 등 측정 대상. 검색의 첫 축이므로 오타가 값이 되면 검색되지 않음. "
        "장비의 시험 항목, 계열의 시험 항목, 시험법이 모두 이 축을 참조함.",
    ),
    (
        "property",
        "물성 항목",
        "common",
        "closed",
        None,
        15,
        "인장강도, 영률, 유리전이온도 등 시험으로 얻는 값. 물성 기준 검색의 첫 축. 값의 "
        "code는 MaterialTwin 키(예: mechanical.yield_strength)로, 재료 물성 "
        "시스템(MatNexus)과 같은 키 사용. 시험 항목과 N:M으로 연결됨.",
    ),
    (
        "equipment_category",
        "장비 분류",
        "catalog",
        "open",
        None,
        20,
        "만능재료시험기, 충격시험기, 경도계 등 장비의 종류. 계열에 지정하며 보유 장비는 "
        "계열의 값을 물려받음. 카탈로그에 없는 장비만 직접 지정.",
    ),
    ("manufacturer", "제조사", "catalog", "open", None, 30, "장비를 만든 회사."),
    (
        "form_factor",
        "기종 형태",
        "catalog",
        "open",
        None,
        35,
        "탁상형, 바닥형, 휴대형 등 기종의 형태. 설치 공간 확보와 휴대 가능 여부를 가르는 "
        "기준.",
    ),
    (
        "drive",
        "구동 방식",
        "catalog",
        "open",
        None,
        36,
        "전기기계식, 유압식, 진자식 등 힘을 내는 방식. 유압은 큰 하중, 전기동력은 높은 "
        "주파수, 진자는 충격에 사용. 가능한 시험이 이 값에 따라 달라짐.",
    ),
    (
        "site",
        "보유 거점",
        "equipment",
        "open",
        None,
        40,
        "공장, 연구소 등 이동이 필요한 위치 단위. 실무에서 가장 먼저 확인하는 항목.",
    ),
    (
        "calibration_provider",
        "교정 기관",
        "equipment",
        "open",
        None,
        45,
        "교정 성적서를 발행한 기관. 같은 기관이 한국계량측정협회, (주)한국계량측정협회처럼 "
        "별개 값으로 나뉘지 않도록 축의 값으로 관리.",
    ),
    (
        "standard_body",
        "규격 제정기관",
        "method",
        "open",
        None,
        50,
        "ASTM, ISO, KS, 사내 등.",
    ),
    (
        "reliability_test_type",
        "신뢰성 시험 유형",
        "common",
        "open",
        None,
        55,
        "환경, 기계, 전기 등 시험의 갈래. 사내 시험 카드의 유형 칸에서 이 축의 값을 선택함.",
    ),
    (
        "product_group",
        "적용군",
        "common",
        "open",
        None,
        56,
        "이 시험을 적용하는 제품군. 사내 시험 카드의 적용군 칸에서 이 축의 값을 선택함. ERP, "
        "PLM 제품 코드 연동 여부는 미정(사내 신뢰성 반입 문서 5절).",
    ),
    (
        "reliability_category",
        "신뢰성 시험 분류",
        "common",
        "open",
        None,
        57,
        "사내 시험을 묶는 분류. 유형(환경, 기계 등)의 상위 또는 별도 갈래로, 회사마다 다름. "
        "기본값 없이 값을 직접 추가하는 축.",
    ),
    # **보유 장비의 축이다**(`common` 이 아니다). 지금 가리키는 것은 장비의 「소재 종류」
    # 하나뿐이고, `common` 은 여러 층이 함께 가리키는 것만 둔다(AGENTS.md). 시험·물성이
    # 소재를 가리키기 시작하면 그때 올린다.
    (
        "material",
        "소재",
        "equipment",
        "open",
        None,
        58,
        "금속, 플라스틱, 고무 등 재질. 장비의 소재 종류(장비로 다루는 소재) 칸이 이 축을 "
        "참조함. 같은 소재의 다른 이름(예: SUS304, STS304, 스테인리스304)은 값을 추가하지 "
        "않고 별칭으로 등록.",
    ),
]

#: 축의 값이 갖는 칸. **설치가 심고, 이미 적힌 축은 안 덮는다.** 물성만 갖는다 —
#: 반입이 MaterialTwin 정의에서 기호·단위·설명을 넣고, 편집 화면이 이것을 보고 칸을 그린다.
ATTRIBUTE_SCHEMAS: dict[str, list[dict[str, str]]] = {
    "property": [
        {"key": "symbol", "label": "기호", "kind": "text", "help": "예: Rp0.2, E, Tg"},
        {"key": "si_unit", "label": "SI 단위", "kind": "text", "help": "예: Pa, K, 1(무차원)"},
        {"key": "domain", "label": "분야", "kind": "text", "help": "예: mechanical, thermal"},
        {"key": "description", "label": "설명", "kind": "text"},
        {"key": "test_standard", "label": "대표 규격", "kind": "text"},
        {
            "key": "condition_axes",
            "label": "조건 축",
            "kind": "list",
            "help": "물성 값이 달라지는 조건 축(예: temperature_k)",
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
        "챔버, 항온조로 낼 수 있는 시험 온도 범위.",
    ),
    (
        "force",
        "하중 용량",
        "range",
        "force",
        "kN",
        "kN",
        20,
        "장비가 낼 수 있는 하중. 상한을 비우면 제한 없음으로 처리됨.",
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
    # 2026-09-30 — 사내 신뢰성 시험 문서를 옮겨 적다 보니, 거의 모든 시험에 나오는데
    # 걸 자리가 없는 것들이 드러났다. 조건이 없으면 그 줄은 문장으로 남고, 문장은
    # 검색이 못 읽는다 — 「그 조건으로 되는 장비」 가 답이 안 나온다.
    (
        "duration",
        "유지 시간",
        "range",
        "time",
        "s",
        "h",
        62,
        "조건 유지 시간. 1000h, 500h처럼 시험 이름에 들어가는 값.",
    ),
    (
        "cycles",
        "사이클 수",
        "range",
        "",
        "",
        "회",
        63,
        "반복 횟수. 500 cycle처럼 프로파일 한 벌을 반복하는 횟수이며 단위 없음.",
    ),
    (
        "pressure",
        "기압",
        "range",
        "pressure",
        "Pa",
        "kPa",
        64,
        "감압, 가압 시험의 압력. 문서에 고도로 적힌 값은 고도(altitude)에 입력.",
    ),
    (
        "altitude",
        "고도",
        "range",
        "length",
        "m",
        "m",
        65,
        "항공 수송, 고지대 시험의 고도. 문서에 고도로 적힌 값은 기압으로 환산하지 않고 여기에 "
        "입력(환산식이 문서마다 다름).",
    ),
    (
        "ramp_rate",
        "승온·하강 속도",
        "range",
        "temperature_rate",
        "degC/s",
        "degC/min",
        66,
        "열충격, 온도 사이클 시험이 요구하는 온도 변화율. 장비 판정은 챔버가 낼 수 있는 속도 "
        "기준.",
    ),
    (
        "salt_concentration",
        "염수 농도",
        "range",
        "ratio",
        "%",
        "%",
        67,
        "염수 분무 시험의 농도(보통 5%).",
    ),
    (
        "rf_power",
        "RF 입력 전력",
        "range",
        "power",
        "W",
        "W",
        68,
        "RF 시험의 입력 전력. 문서에 dBm으로 적힌 값은 W로 환산하고 원문은 비고(note)에 기록.",
    ),
    (
        "vswr",
        "VSWR",
        "range",
        "",
        "",
        "",
        69,
        "정재파비. 단위 없는 비(比)이므로 1.5 : 1은 1.5로 입력.",
    ),
    # 2026-09-30 (둘째) — 길이 계열이 시편 두께·고도뿐이라, 낙하 152 cm 도 굽힘 1~10 mm 도
    # 걸 자리가 없었다. 같은 「길이」 지만 **묻는 물음이 다르다** — 낙하는 「몇 cm 에서
    # 떨어뜨리나」 이고 변위는 「얼마나 휘나」 다. 한 축에 뭉치면 「1 m 낙하 되는 장비」 가
    # 굽힘 시험기를 답으로 준다.
    (
        "drop_height",
        "낙하 높이",
        "range",
        "length",
        "m",
        "cm",
        71,
        "낙하, 충격 시험의 높이. 문서에 cm로 적힌 값은 cm로 입력(1 m = 100 cm 환산은 서버가 "
        "처리). 지그 낙하 152 cm처럼 시험 이름에 들어가는 값.",
    ),
    (
        "displacement",
        "변위",
        "range",
        "length",
        "m",
        "mm",
        72,
        "굽힘, 처짐 시험이 요구하는 이동량. MLCC 기판 굽힘 1~10 mm처럼 지그가 낼 수 있는 "
        "변위로 장비 판정. 크로스헤드 속도(얼마나 빨리)와 별개 조건.",
    ),
    (
        "chamber",
        "항온조",
        "boolean",
        "",
        "",
        "",
        70,
        "항온조 유무. 온도 범위는 시험 온도에 별도 입력.",
    ),
    # 2026-09-12 — 사양이 있는데 이어 줄 축이 없어 검색이 못 쓰던 것들. 축은 사양 정의가
    # 잇는 만큼만 만든다(아래 SPEC_DEFINITION_LINKS): 잇는 정의가 없는 축은 검색 폼에
    # 아무도 안 쓰는 칸이 하나 늘 뿐이다.
    ("voltage", "전압", "range", "voltage", "V", "V", 80, "내전압, 전원 시험이 거는 전압."),
    (
        "current",
        "전류",
        "range",
        "current",
        "A",
        "A",
        90,
        "접지 저항, 전원 시험이 흘리는 전류.",
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
        "진동, 충격 시험기가 낼 수 있는 가속도.",
    ),
    (
        "impact_energy",
        "충격 에너지",
        "range",
        "energy",
        "J",
        "J",
        120,
        "진자, 낙하 해머가 가진 에너지. 샤르피, 아이조드 시험의 검색 조건.",
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
    # 2026-10-08 — 신뢰성 시험이 묻는데 이어진 사양이 없어 판정이 늘 「모름」 이던 축.
    "drop_height": "drop_height",
    # **냉각 속도만 잇는다.** 승온·하강 속도 축 하나에 승온·냉각 둘을 이으면 먼저 오는 쪽이
    # 이기는데(`conditions_from_specs_bulk`), 챔버는 대개 냉각이 느리다 — 승온 10 · 냉각 5
    # K/min 챔버가 7 K/min 온도 사이클에 「됨」 이 된다. 느린 쪽으로 답하면 틀려도 보수적이다.
    "cooling_rate": "ramp_rate",
    # 변위는 「얼마나 휘게 하나」 다(기판 굽힘 1~10 mm). 장비가 밀어낼 수 있는 이동량이 답이다.
    "crosshead_travel": "displacement",
    "actuator_stroke": "displacement",
    # 저기압 챔버(2026-10-08 카탈로그 반입) — 온톨로지 `chamber_pressure_kPa` ·
    # `altitude_m` 의 승격분.
    "chamber_pressure": "pressure",
    "altitude": "altitude",
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
    ("capacity", "용량", 10, "장비가 낼 수 있는 크기(하중, 토크, 에너지)."),
    ("range", "시험 범위", 20, "온도, 속도, 주파수 등 시험 가능한 범위."),
    (
        "space",
        "시험 공간·시편",
        30,
        "물릴 수 있는 시편과 시험 공간.",
    ),
    (
        "accuracy",
        "정밀도·계측",
        40,
        "분해능, 강성, 정확도 등급. 규격이 요구하는 등급 충족 여부 확인용.",
    ),
    ("installation", "설치 조건", 50, "전원, 치수, 무게. 장비 도입 전 확인 필요 항목."),
    ("configuration", "구성", 60, "구동 방식, 스테이션 수, 소프트웨어."),
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
        "사양서의 최대 하중. 시험 조건으로 반영되어 검색에 사용됨.",
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
        "진자, 낙하 해머가 가진 에너지.",
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
        "경도계가 고를 수 있는 하중의 최솟값과 최댓값. 개별 하중 목록은 비고에 기록됨.",
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
        "챔버, 퍼니스 장착 시 낼 수 있는 범위. 본체 운전 온도와 다름.",
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
        "검색축(항온조)과 연결하지 않음. 참/거짓 값은 범위 비교가 성립하지 않아 시험 항목에 "
        "반영되지 않음.",
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
        "그립 사이에 남는 높이. 시편과 지그가 들어가야 시험 가능.",
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
        "displacement",
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
        "displacement",
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
        "경도계에서 시편을 밀어 넣을 수 있는 깊이.",
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
        "작을수록 좋은 값이므로 하한으로 처리됨.",
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
        "강성이 낮으면 시편 대신 프레임이 변형됨. 탄성계수 측정 결과에 영향.",
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
        "조건절이 붙는 값(예: ±0.5% of reading down to 1/1000 of load cell capacity). "
        "조건절을 빼지 않고 문장 그대로 입력.",
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
        "규격이 정한 등급(예: ISO 7500-1 Class 0.5, ASTM E83 Class B-1).",
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
        "상, 전압, 주파수를 한 문장으로 입력(예: 1PH 220 VAC 50/60 Hz).",
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
        "카탈로그에 VA, kVA로 적힌 값은 역률을 모르면 W로 환산 불가. 이 경우 원문을 비고에 "
        "입력.",
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
        "바닥 하중과 반입 경로 결정에 사용. 카탈로그에 가장 흔히 적힌 값.",
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
        "장비 자체가 놓일 공간의 온도(시험 온도 아님).",
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
        "같은 하중이라도 구동 방식에 따라 가능한 시험이 다름(예: 피로 시험은 전기기계식으로 "
        "불가).",
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
        "한 대에서 동시에 걸 수 있는 시편 수. 크리프처럼 장시간 시험의 처리량을 결정.",
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
    #: 옛 판 그대로이던 안내 글을 지금 글로 바꾼 수(`refresh_seed_texts`).
    refreshed_texts: int = 0


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


#: 보유 장비의 **정식 속성** — 고정 칸에 없는 것만. 현장 장비 목록의 열(중분류·소분류·장비명·
#: 장비 용도·보유처·건물·설치 위치·담당자·자산번호·투자년도·예약 URL, 2026-09-18) 중 나머지는
#: 고정 칸이 이미 갖는다: 중분류·소분류 = 장비 분류의 군·유형, 장비명 = 장비명, 보유처 = 보유
#: 부서, 건물 = 거점, 설치 위치 = 설치 위치, 담당자 = 담당자, 자산번호 = 자산번호. 투자년도는
#: 도입일과 다른 물음(예산 집행 연도)이라 따로 둔다. 없을 때만 심는다 — 관리자가 끄거나 이름을
#: 바꾼 것을 설치가 되돌리면 안 된다.
#:
#:   (key, label, kind, unit, help, sort_order, 온톨로지 축 slug)
EQUIPMENT_ATTRIBUTES: tuple[tuple[str, str, str, str, str, int, str | None], ...] = (
    (
        "equipment_purpose",
        "장비 용도",
        "text",
        "",
        "장비로 하는 일. 한두 문장으로 입력.",
        1,
        None,
    ),
    (
        "investment_year",
        "투자 연도",
        "number",
        "",
        "예산이 집행된 연도. 도입일(실제 반입일)과 다를 수 있음.",
        2,
        None,
    ),
    (
        "reservation_url",
        "장비 예약 URL",
        "text",
        "",
        "예약 시스템 주소. http로 시작하면 링크로 표시됨.",
        3,
        None,
    ),
    # **AI 가 채우는 칸.** 장비에 붙인 자료(사양서·매뉴얼 PDF)에서 뽑은 글을 여기 적으면
    # 의미 검색의 카드에 함께 실려 임베딩된다(`shared/semantic.py` 의 `_standard_attributes`
    # 가 정식 속성을 카드에 넣는다). 그러면 「얇은 판 잡아당기는 장비」 처럼 낱말이 하나도
    # 안 겹치는 물음으로도 그 장비가 걸린다.
    #
    # 사람이 읽는 칸이 아니라 **찾히기 위한 칸**이라 길어도 된다. 원문을 그대로 넣지 말고
    # 쓸 만한 대목만 간추려 넣는다 — 카드가 길수록 조각이 늘고, 조각이 늘수록 한 조각의
    # 뜻이 흐려진다.
    (
        "equipment_document_digest",
        "장비 자료 발췌",
        "text",
        "",
        "장비 자료(사양서, 매뉴얼)에서 발췌한 글. 의미 검색 대상에 포함됨. AI가 채우는 "
        "칸이며, 원문 전체가 아닌 필요한 대목만 요약해 입력.",
        4,
        None,
    ),
    # **「장비 용도」 와 다른 칸이다.** 용도는 「무엇을 하나」, 이것은 「왜 쓰나·왜 들였나」 다
    # — 투자 연도와 짝이 된다. 두 칸을 나란히 두는 것은 그 둘을 한 칸에 적으면 둘 중 하나가
    # 빠지기 때문이다(그리고 빠진 쪽은 아무도 안 찾는다).
    #
    # 차례가 뒤인 이유: 심기는 **없을 때만** 하므로(`ensure_equipment_attributes`) 앞의
    # 번호를 바꿔도 이미 깔린 곳에는 안 걸린다. 번호를 비집어 넣는 대신 뒤에 붙인다.
    (
        "equipment_usage_reason",
        "사용이유",
        "text",
        "",
        "장비를 쓰는 이유, 도입한 이유. 장비 용도(하는 일)와 별개 항목.",
        5,
        None,
    ),
    # **소재 종류는 글이 아니라 온톨로지 값이다**(사용자가 정함, 2026-10-02 「소재는 나중에
    # 온톨로지로」). 글로 두면 SUS304 · STS304 · 스테인리스304 가 다 들어와 아무도 못 거른다.
    # 한 칸에 한 값이다(적용군과 같다) — 여러 소재를 다루면 가장 주된 것을 고르거나 묶음을
    # 단다.
    (
        "equipment_material",
        "소재 종류",
        "term",
        "",
        "장비로 다루는 소재. 소재 축에서 선택. 값이 없으면 온톨로지에서 추가하고, 같은 소재의 "
        "다른 이름(STS304, SUS304)은 별칭으로 등록.",
        6,
        "material",
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
#:   (key, label, kind, unit, 조건축 key, 온톨로지 축 slug, help, sort_order)
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
        "환경, 기계, 전기 등 시험의 갈래.",
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
        "시험이 따르는 공인 규격(ASTM, IEC, KS 등). 규격 사전에서 선택.",
        3,
    ),
    (
        "reliability_category",
        "분류",
        "term",
        "",
        None,
        "reliability_category",
        "사내 시험을 묶는 분류. 값이 없으면 온톨로지에서 추가.",
        3,
    ),
    (
        "reliability_spec_document",
        "규격서",
        "document",
        "",
        None,
        None,
        "시험이 적힌 사내 규격서를 목록에서 선택. 사내 규격서는 사이드바 카탈로그 → 사내 "
        "규격서에서 등록하고 원본 파일 업로드. 공개 규격(ASTM, ISO, KS)은 별도 사전인 참조 "
        "규격 칸에서 선택.",
        4,
    ),
    (
        "reliability_document_type",
        "문서 유형",
        "term",
        "",
        None,
        "document_type",
        "규격서, 지침서, 작업표준 등 문서의 갈래.",
        5,
    ),
    (
        "reliability_target",
        "시험 대상",
        "text",
        "",
        None,
        None,
        "시험 대상(완제품, 모듈, 부품, 시편 중 무엇인지)과 그 상태.",
        9,
    ),
    (
        "reliability_equipment_note",
        "시험기·비품",
        "text",
        "",
        None,
        None,
        "시험에 쓰는 장비와 비품. 가능한 장비는 서버가 조건으로 조회함. 지그, 치구처럼 "
        "조건으로 표현되지 않는 것을 입력.",
        10,
    ),
    (
        "reliability_sample_count",
        "시료 수",
        "number",
        "개",
        None,
        None,
        "1회 시험의 시료 수. 등급, 단계마다 다르면 등급별 수량에 입력.",
        11,
    ),
    (
        "reliability_other_conditions",
        "기타 조건",
        "text",
        "",
        None,
        None,
        "조건 칸으로 표현되지 않는 조건(분위기 가스, 시편 전처리 등). "
        "여기 입력한 내용은 장비 판정에 사용되지 않음. 판정에 사용하려면 조건 칸 추가 필요.",
        12,
    ),
    (
        "reliability_procedure",
        "시험 절차",
        "text",
        "",
        None,
        None,
        "시험 순서. 프로파일이 있으면 단계별로 입력.",
        13,
    ),
    (
        "reliability_method",
        "시험 방법",
        "text",
        "",
        None,
        None,
        "측정 방식. 절차와 달리 무엇을 어떻게 측정하는지 기술.",
        14,
    ),
    (
        "reliability_criteria",
        "판정 기준",
        "text",
        "",
        None,
        None,
        "합격 판정 기준. 수치 기준이면 값과 단위를 함께 입력.",
        15,
    ),
    (
        "reliability_caution",
        "주의사항",
        "text",
        "",
        None,
        None,
        "안전, 취급, 해석에서 놓치면 안 되는 사항.",
        16,
    ),
    (
        "reliability_grade_counts",
        "등급별 수량",
        "pairs",
        "개",
        None,
        None,
        "등급별 시료 수(예: A등급 4 · B등급 4). 이름과 숫자를 짝으로 입력. 이름 없는 숫자는 "
        "입력 불가.",
        17,
    ),
    (
        "reliability_stage_counts",
        "단계별 수량",
        "pairs",
        "개",
        None,
        None,
        "단계별 시료 수(예: 1단계 8 · 2단계 4). 등급과 단계가 함께 나뉘면 적용 사양 매트릭스 "
        "사용.",
        18,
    ),
    (
        "reliability_spec_matrix",
        "적용 사양 매트릭스",
        "matrix",
        "개",
        None,
        None,
        "사양마다 등급, 단계가 따로 정해질 때 사용. 사양 한 줄에 해당 사양의 짝을 입력(예: "
        "사양 A: A등급 4 · B등급 2).",
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


#: 조건 축마다 하나씩 서는 신뢰성 속성(`reliability_cond_*`)의 안내 — 전부 같은 글이다.
#: 상수로 둔 것은 `seed_texts` 가 옛 글을 이 글로 바꿀 때 가리켜야 해서다.
CONDITION_ATTRIBUTE_HELP = (
    "최소, 최대 중 하나만 입력 가능. 비운 쪽은 제한 없음으로 처리됨. 숫자 없이 "
    "비고만 입력하면 장비 판정에 사용되지 않음."
)


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
                key.unit,
                key.key,
                None,
                CONDITION_ATTRIBUTE_HELP,
                order,
            )
        )
        order += 1
    return rows


def ensure_reliability_attributes(db: Session) -> int:
    """신뢰성 시험의 정식 속성을 심는다 — key 로 찾아 **없는 것만.**

    관리자가 끄거나 이름을 바꾼 것을 설치가 되돌리면 안 된다(보유 장비 속성과 같은 규칙).
    조건 축·온톨로지 축이 아직 없으면 그 칸은 **안 심는다** — 빈 축을 가리키는 속성은
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
    """보유 장비의 정식 속성을 심는다 — key 로 찾아 없는 것만.

    온톨로지 값을 고르는 칸(`term`)은 축이 있어야 선다 — 축을 못 찾으면 **안 심는다**(정식
    칸이 축 없이 서면 아무것도 못 고르는 칸이 된다). 축은 `ensure_reference_data` 가 먼저
    심는다.
    """
    known = set(db.scalars(select(AttributeDefinition.key)))
    axes = {slug: vid for vid, slug in db.execute(select(Vocabulary.id, Vocabulary.slug))}
    added = 0
    for key, label, kind, unit, help_text, order, axis_slug in EQUIPMENT_ATTRIBUTES:
        if key in known:
            continue
        if axis_slug is not None and axis_slug not in axes:
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
                vocabulary_id=axes[axis_slug] if axis_slug else None,
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


def refresh_seed_texts(db: Session) -> int:
    """설치가 심은 안내 글을 지금 판의 글로 바꾼다 — **옛 판 그대로인 것만.**

    시드는 없는 행만 심으므로 글을 고쳐도 설치된 DB 에는 안 들어간다. 덮어쓰면 화면에서
    사람이 고친 글이 사라지므로, DB 의 글이 `seed_texts.RETIRED` 의 옛 글과 **똑같을 때만**
    바꾼다. 두 번 돌려도 같다.
    """
    changed = 0

    def renewed(kind: str, key: str, stored: str | None, now: str | None) -> str | None:
        nonlocal changed
        if not stored or not now or stored == now:
            return None
        if stored not in RETIRED.get(kind, {}).get(key, ()):
            return None
        changed += 1
        return now

    axes = {row[0]: row[6] for row in AXES}
    for axis in db.scalars(select(Vocabulary).where(Vocabulary.slug.in_(axes))):
        text = renewed("axis", axis.slug, axis.description, axes[axis.slug])
        if text:
            axis.description = text
        fields = {one["key"]: one.get("help") for one in ATTRIBUTE_SCHEMAS.get(axis.slug, [])}
        if not fields or not axis.attribute_schema:
            continue
        rebuilt: list[dict[str, str]] = []
        touched = False
        for field in axis.attribute_schema:
            key = str(field.get("key"))
            help_text = renewed(
                "axis_field", f"{axis.slug}.{key}", field.get("help"), fields.get(key)
            )
            if help_text:
                field = {**field, "help": help_text}
                touched = True
            rebuilt.append(field)
        if touched:
            # JSON 칸은 안을 고쳐도 바뀐 줄로 안 친다 — 새 목록으로 갈아 끼운다.
            axis.attribute_schema = rebuilt

    conditions = {row[0]: row[7] for row in CONDITIONS}
    for condition in db.scalars(select(ConditionKey).where(ConditionKey.key.in_(conditions))):
        text = renewed("condition", condition.key, condition.help, conditions[condition.key])
        if text:
            condition.help = text

    groups = {row[0]: row[3] for row in SPEC_GROUPS}
    for group in db.scalars(select(SpecGroup).where(SpecGroup.slug.in_(groups))):
        text = renewed("spec_group", group.slug, group.description, groups[group.slug])
        if text:
            group.description = text

    # 카탈로그 반입이 심는 정의(`catalog_specs`)도 같은 표에 산다 — 그쪽도 없는 것만 심는다.
    definitions = {row[0]: row[9] for row in (*CATALOG_SPEC_DEFINITIONS, *SPEC_DEFINITIONS)}
    for spec in db.scalars(select(SpecDefinition).where(SpecDefinition.key.in_(definitions))):
        text = renewed("spec_definition", spec.key, spec.help, definitions[spec.key])
        if text:
            spec.help = text

    attributes = {row[0]: row[6] for row in RELIABILITY_ATTRIBUTES}
    attributes.update({row[0]: row[4] for row in EQUIPMENT_ATTRIBUTES})
    for attribute in db.scalars(select(AttributeDefinition)):
        if attribute.key.startswith("reliability_cond_"):
            text = renewed(
                "condition_attribute", "*", attribute.help, CONDITION_ATTRIBUTE_HELP
            )
        elif attribute.key in attributes:
            text = renewed(
                "attribute", attribute.key, attribute.help, attributes[attribute.key]
            )
        else:
            continue
        if text:
            attribute.help = text
    return changed


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

    # **값까지 심는 축이 있다.** 사업부는 회사 구조라 설치한 사람이 지어낼 것이 아니고,
    # 비어 있으면 부서에 아무것도 못 붙여서 신뢰성 시험 등록이 통째로 막힌다.
    # **하나라도 있으면 안 건드린다** — 지운 값을 설치가 되살리면 그것은 사고다.
    for slug, values in DEFAULT_TERMS.items():
        axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
        if axis is None:
            continue
        has_any = db.scalar(
            select(func.count())
            .select_from(VocabularyTerm)
            .where(VocabularyTerm.vocabulary_id == axis.id)
        )
        if has_any:
            continue
        for order, (code, value) in enumerate(values, start=1):
            db.add(
                VocabularyTerm(
                    vocabulary_id=axis.id,
                    value=value,
                    normalized=compare_key(value),
                    code=code,
                    sort_order=order * 10,
                )
            )
    db.flush()

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
    refreshed = refresh_seed_texts(db)

    db.commit()
    return ReferenceCounts(
        added_axes,
        added_keys,
        added_groups,
        added_definitions,
        linked,
        converted,
        added_attributes,
        refreshed,
    )
