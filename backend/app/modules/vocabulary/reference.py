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

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.vocabulary.models import ConditionKey, Vocabulary
from app.modules.vocabulary.specs import SpecDefinition, SpecGroup

#: (slug, label, 입력 정책, 부모 축, 순서, 설명)
#:
#: `test_item` 만 closed 다 — **검색의 첫 축**이라 오타가 값이 되면 그 장비는 영영
#: 검색에 안 걸린다. 나머지는 open: 막았을 때 사람이 어디로 가는지가 문제다.
AXES: list[tuple[str, str, str, str | None, int, str]] = [
    (
        "test_item",
        "시험 항목",
        "closed",
        None,
        10,
        "인장·압축·충격처럼 무엇을 재는가. 검색의 첫 축이라 오타가 값이 되면 안 걸린다.",
    ),
    (
        "equipment_category",
        "장비 분류",
        "open",
        None,
        20,
        "만능재료시험기·충격시험기·경도계처럼 장비의 종류.",
    ),
    ("manufacturer", "제조사", "open", None, 30, "장비를 만든 회사."),
    (
        "site",
        "보유 거점",
        "open",
        None,
        40,
        "공장·연구소처럼 가려면 이동해야 하는 단위. 실무에서 가장 먼저 묻는 것.",
    ),
    ("standard_body", "규격 제정기관", "open", None, 50, "ASTM · ISO · KS · 사내."),
]

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
]


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
        "사양서의 최대 하중. 이 값은 역량 조건으로 따라 들어가 검색에 쓰인다.",
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
        None,
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
        None,
        "max",
        50,
        "진자·낙하 해머가 가진 에너지.",
    ),
    (
        "test_load_series",
        "시험 하중 계열",
        "capacity",
        "text",
        "force",
        "kgf",
        None,
        "max",
        60,
        "경도계가 고를 수 있는 하중들. 카탈로그가 낱개로 늘어놓아 문장 그대로 적는다.",
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
        "역량으로 옮길 수 없고, 옮긴 척하면 검색이 조용히 틀린다.",
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


def ensure_reference_data(db: Session) -> ReferenceCounts:
    """없는 축·조건·사양 정의만 만든다."""
    known_axes = set(db.scalars(select(Vocabulary.slug)))
    added_axes = 0
    for slug, label, policy, parent, order, description in AXES:
        if slug in known_axes:
            continue
        db.add(
            Vocabulary(
                slug=slug,
                label=label,
                entry_policy=policy,
                parent_slug=parent,
                sort_order=order,
                description=description,
            )
        )
        added_axes += 1

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

    db.commit()
    return ReferenceCounts(added_axes, added_keys, added_groups, added_definitions)
