"""제조사 카탈로그의 사양 키를 이 시스템의 사양 정의로 잇는다.

## 왜 자동으로 만들지 않나

`source/` 의 137개 객체에 사양 키가 **562종** 있는데, 그중 429종(76%)이 단 한
객체에만 나온다. 만나는 키마다 정의를 만들면 관리 화면이 못 쓰게 되고, "오타가 새
사양이 되는 길이 없다" 는 ADR 0005 의 원칙도 함께 깨진다.

그래서 **빈도로 승격한다** — 3개 이상 객체에 나오는 키만 여기 손으로 적는다.
나머지는 반입이 보류 목록으로 **보고만 하고 값은 안 들인다.** 원본이 `source/` 에
그대로 있으니 값이 사라지는 것이 아니다: 정의를 만든 뒤 다시 돌리면 들어온다.

## 배율

원본은 실무 단위를 키 이름에 박아 둔다 — `force_kN` 과 `force_N` 이 같은 사양이다.
이 표가 배율을 들고 있어서 저장은 한 단위로 모인다. **환산을 반입 스크립트에
흩어 두면 한 곳만 고쳐지는 날이 온다.**
"""

from __future__ import annotations

#: 원본 키 -> (사양 정의 key, 배율)
#:
#: 배율은 **원본 값에 곱해서** 정의의 단위로 만드는 수다. `force_N` 은 0.001 을
#: 곱해 kN 이 된다.
SOURCE_SPEC_MAP: dict[str, tuple[str, float]] = {
    # 용량
    "force_kN": ("force_capacity", 1.0),
    "force_N": ("force_capacity", 0.001),
    "dynamic_force_kN": ("dynamic_force", 1.0),
    "static_force_kN": ("static_force", 1.0),
    "torque_Nm": ("torque_capacity", 1.0),
    "torque_mNm": ("torque_capacity", 0.001),
    "impact_energy_J": ("impact_energy", 1.0),
    "load_kg": ("chamber_load", 1.0),
    "oil_capacity_L": ("oil_capacity", 1.0),
    "test_load_kgf": ("test_load_series", 1.0),
    "test_load_gf": ("test_load_micro", 1.0),
    "indentation_force_mN": ("indentation_force", 1.0),
    "frequency_Hz": ("frequency_range", 1.0),
    "max_force_at_full_speed_kN": ("force_at_full_speed", 1.0),
    "melt_load_kg": ("melt_load", 1.0),
    "payload_kg": ("payload", 1.0),
    # 시험 범위
    "temperature_degC": ("test_temperature", 1.0),
    "melt_temperature_degC": ("melt_temperature", 1.0),
    "heating_rate_K_min": ("heating_rate", 1.0),
    "cooling_rate_K_min": ("cooling_rate", 1.0),
    "crosshead_speed_mm_min": ("crosshead_speed", 1.0),
    "return_speed_mm_min": ("return_speed", 1.0),
    "max_speed_at_full_force_mm_min": ("speed_at_full_force", 1.0),
    "rotation_rpm": ("rotation_speed", 1.0),
    "rotation_deg": ("rotation_angle", 1.0),
    "humidity_pct": ("humidity_range", 1.0),
    "chamber": ("chamber_mountable", 1.0),
    "impact_velocity_m_s": ("impact_velocity", 1.0),
    "velocity_m_s": ("velocity", 1.0),
    "vacuum_mbar": ("vacuum_level", 1.0),
    "current_A": ("current_range", 1.0),
    "voltage_V": ("voltage_range", 1.0),
    "luminance_cd_m2": ("luminance_range", 1.0),
    "thermal_conductivity_W_mK": ("thermal_conductivity", 1.0),
    "thermal_diffusivity_mm2_s": ("thermal_diffusivity", 1.0),
    # 시험 공간·시편
    "vertical_test_space_mm": ("vertical_test_space", 1.0),
    # daylight opening 은 그립 사이에 남는 높이 — 수직 시험 공간과 같은 말이다.
    "vertical_daylight_mm": ("vertical_test_space", 1.0),
    "horizontal_test_space_mm": ("horizontal_test_space", 1.0),
    "crosshead_travel_mm": ("crosshead_travel", 1.0),
    # 한 기종에 둘이 함께 적힌 적이 없다 — 같은 것을 제조사마다 달리 부른다.
    "tensile_stroke_mm": ("crosshead_travel", 1.0),
    "grip_span_mm": ("grip_span", 1.0),
    "compression_plate_mm": ("compression_plate", 1.0),
    "flexure_support_span_mm": ("flexure_support_span", 1.0),
    "stroke_mm": ("actuator_stroke", 1.0),
    "stage_travel_mm": ("stage_travel", 1.0),
    "specimen_thickness_mm": ("specimen_thickness", 1.0),
    "specimen_diameter_mm": ("specimen_diameter", 1.0),
    "specimen_height_mm": ("specimen_height", 1.0),
    "sample_length_mm": ("specimen_length", 1.0),
    "specimen_weight_kg": ("specimen_weight", 1.0),
    "sample_mass_mg": ("sample_mass", 1.0),
    "throat_depth_mm": ("throat_depth", 1.0),
    "chamber_volume_L": ("chamber_volume", 1.0),
    # 정밀도·계측
    "position_resolution_nm": ("position_resolution", 1.0),
    "balance_resolution_ug": ("balance_resolution", 1.0),
    "displacement_um": ("displacement_range", 1.0),
    "displacement_mm": ("displacement_range", 1000.0),
    "frame_stiffness_kN_mm": ("frame_stiffness", 1.0),
    "data_rate_Hz": ("data_rate", 1.0),
    "accuracy": ("accuracy_note", 1.0),
    "hardness_scales": ("hardness_scales", 1.0),
    # 설치 조건
    "power": ("power_supply", 1.0),
    "power_W": ("power_consumption", 1.0),
    "power_kW": ("power_consumption", 1000.0),
    "power_VA": ("apparent_power", 1.0),
    "power_kVA": ("apparent_power", 1000.0),
    "weight_kg": ("weight", 1.0),
    # 구성
    "stations": ("test_stations", 1.0),
    "channels": ("channel_count", 1.0),
    "principle": ("measuring_principle", 1.0),
    "cooling": ("cooling_method", 1.0),
    # --- 3차: 같은 것을 다르게 부르는 이름들 --------------------------------
    #
    # 원본이 커지면서 제조사마다 제 이름으로 적은 것이 드러났다. **온톨로지는
    # `limits` 만 통제하고 `models[].specs` 는 자유 형식**이라(build_graph 가 거기까지는
    # 안 본다), 이 층의 동의어는 여기서 이어 줄 수밖에 없다.
    "nominal_load_kN": ("force_capacity", 1.0),
    "capacity_kN": ("force_capacity", 1.0),
    "max_load_kN": ("force_capacity", 1.0),
    "max_stroke_mm": ("actuator_stroke", 1.0),
    "electrical": ("power_supply", 1.0),
    "power_supply": ("power_supply", 1.0),
    "accuracy_class": ("accuracy_class", 1.0),
    "class": ("accuracy_class", 1.0),
    # 분해능은 nm 로 모은다 — µm 로 적힌 것은 1000을 곱한다.
    "travel_resolution_um": ("position_resolution", 1000.0),
    "resolution_um": ("position_resolution", 1000.0),
    "displacement_resolution_um": ("position_resolution", 1000.0),
    # 치수를 배열이 아니라 낱개로 적는 카탈로그가 많다.
    "width_mm": ("dimension_width", 1.0),
    "depth_mm": ("dimension_depth", 1.0),
    "height_mm": ("dimension_height", 1.0),
    # 시험실(챔버) 안쪽 치수. **바깥과 다른 물음에 답한다.**
    "test_room_width_mm": ("inner_width", 1.0),
    "test_room_depth_mm": ("inner_depth", 1.0),
    "test_room_height_mm": ("inner_height", 1.0),
    "refrigerant": ("cooling_method", 1.0),
    "functions": ("test_functions", 1.0),
}

#: 원본이 옵션 사양을 키 뒤에 붙여 구별한다 — `vertical_test_space_mm_E2`.
#:
#: **같은 사양의 다른 구성**이지 다른 사양이 아니다. 별도 정의로 만들면 사양표에
#: 거의 같은 줄이 둘씩 서고, 검색은 어느 쪽을 봐야 할지 모른다. 값은 기본 구성만
#: 들이고, 옵션 값은 비고에 남긴다.
VARIANT_SUFFIXES: dict[str, str] = {
    "_E2": "E2(확장 높이) 옵션",
    "_F2": "F2(확장 폭) 옵션",
    "_ext": "확장 구성",
}

#: 치수를 세 칸으로 나눈다. 원본은 `[W, D, H]` 또는 `{"W":…,"D":…,"H":…}` 다.
#:
#: **바깥 치수와 안쪽 치수는 다른 물음에 답한다.** 바깥은 「자리가 나나」 이고,
#: 안쪽은 「시편이 들어가나」 다 — 챔버에서는 뒤엣것이 훨씬 자주 걸린다.
FOOTPRINT_KEYS = ("dimension_width", "dimension_depth", "dimension_height")
INNER_KEYS = ("inner_width", "inner_depth", "inner_height")

#: 원본이 치수를 부르는 이름들. 제조사마다 다르고, 한 카탈로그 안에서도 갈린다.
DIMENSION_SOURCES: dict[str, tuple[str, str, str]] = {
    "footprint_mm": FOOTPRINT_KEYS,
    "dimensions_mm": FOOTPRINT_KEYS,
    "outside_mm": FOOTPRINT_KEYS,
    "outer_mm": FOOTPRINT_KEYS,
    "inner_mm": INNER_KEYS,
    "inside_mm": INNER_KEYS,
}

#: 상·하한을 **두 키로 나눠 적은** 것을 구간 하나로 합친다.
#:
#: 열충격 챔버가 그렇게 적는다 — 고온조 `[50, 200]`, 저온조 `[-65, 0]`. 둘을 따로
#: 두면 어느 쪽도 「시험 온도」 가 아니어서 검색에 안 걸린다.
TEMPERATURE_PAIR = ("low_temp_degC", "high_temp_degC", "test_temperature")

#: 카탈로그를 들이며 승격한 사양 정의. 형식은 `SPEC_DEFINITIONS` 와 같다.
#:
#: 설치가 심는 38개는 어느 조직에나 있을 만한 것이고, 여기 것은 **우리가 모은
#: 카탈로그가 실제로 쓰더라**에서 왔다. 나눠 두는 이유: 설치 기본값과 우리 데이터의
#: 사정을 한 목록에 섞으면, 다음 사람이 무엇을 지워도 되는지 알 수 없다.
CATALOG_SPEC_DEFINITIONS: list[
    tuple[str, str, str, str, str, str, str | None, str, int, str | None]
] = [
    # --- 용량 ----------------------------------------------------------------
    (
        "test_load_micro",
        "미소 시험 하중",
        "capacity",
        "text",
        "force",
        "gf",
        None,
        "max",
        110,
        "마이크로 비커스가 고르는 하중들. 카탈로그가 낱개로 늘어놓아 문장 그대로 적는다.",
    ),
    (
        "indentation_force",
        "압입 하중",
        "capacity",
        "range",
        "force",
        "mN",
        None,
        "max",
        120,
        "계장화 압입(나노인덴테이션)이 거는 하중.",
    ),
    (
        "force_at_full_speed",
        "최고 속도에서의 하중",
        "capacity",
        "number",
        "force",
        "kN",
        None,
        "max",
        130,
        "**최대 하중과 다르다.** 전속으로 돌리면 낼 수 있는 하중이 줄어드는 장비가 있다.",
    ),
    ("melt_load", "MFI 하중", "capacity", "range", "mass", "kg", None, "max", 140, None),
    (
        "payload",
        "가진 하중(페이로드)",
        "capacity",
        "range",
        "mass",
        "kg",
        None,
        "max",
        150,
        "진동 시험기가 흔들 수 있는 시편·지그의 무게.",
    ),
    # --- 시험 범위 ------------------------------------------------------------
    (
        "melt_temperature",
        "실린더 온도",
        "range",
        "range",
        "temperature",
        "degC",
        None,
        "max",
        110,
        "MFI 시험기의 배럴 온도. **시험 온도와 다른 칸이다.**",
    ),
    (
        "cooling_rate",
        "냉각 속도",
        "range",
        "range",
        "temperature_rate",
        "K/min",
        None,
        "max",
        120,
        None,
    ),
    (
        "speed_at_full_force",
        "최대 하중에서의 속도",
        "range",
        "number",
        "speed",
        "mm/min",
        None,
        "max",
        130,
        "**최고 속도와 다르다.** 하중을 다 걸면 느려지는 장비가 있다.",
    ),
    (
        "rotation_angle",
        "회전각",
        "range",
        "number",
        "angle",
        "deg",
        None,
        "max",
        140,
        None,
    ),
    (
        "impact_velocity",
        "충격 속도",
        "range",
        "range",
        "speed",
        "m/s",
        None,
        "max",
        150,
        None,
    ),
    ("velocity", "이동 속도", "range", "range", "speed", "m/s", None, "max", 160, None),
    (
        "vacuum_level",
        "도달 진공도",
        "range",
        "number",
        "pressure",
        "mbar",
        None,
        "min",
        170,
        "**작을수록 좋은 값**이라 바닥으로 읽는다.",
    ),
    (
        "current_range",
        "전류 범위",
        "range",
        "range",
        "current",
        "A",
        None,
        "max",
        180,
        None,
    ),
    (
        "voltage_range",
        "전압 범위",
        "range",
        "range",
        "voltage",
        "V",
        None,
        "max",
        190,
        None,
    ),
    (
        "luminance_range",
        "휘도 측정 범위",
        "range",
        "range",
        "luminance",
        "cd/m²",
        None,
        "max",
        200,
        None,
    ),
    (
        "thermal_conductivity",
        "열전도율 측정 범위",
        "range",
        "range",
        "thermal_conductivity",
        "W/(m·K)",
        None,
        "max",
        210,
        None,
    ),
    (
        "thermal_diffusivity",
        "열확산율 측정 범위",
        "range",
        "range",
        "thermal_diffusivity",
        "mm²/s",
        None,
        "max",
        220,
        None,
    ),
    # --- 시험 공간·시편 -------------------------------------------------------
    (
        "stage_travel",
        "스테이지 이동 범위",
        "space",
        "range",
        "length",
        "mm",
        None,
        "max",
        110,
        None,
    ),
    (
        "specimen_length",
        "시편 길이",
        "space",
        "range",
        "length",
        "mm",
        None,
        "max",
        120,
        None,
    ),
    (
        "specimen_weight",
        "시편 무게",
        "space",
        "range",
        "mass",
        "kg",
        None,
        "max",
        130,
        None,
    ),
    (
        "sample_mass",
        "시료 질량",
        "space",
        "range",
        "mass",
        "mg",
        None,
        "max",
        140,
        "열분석이 다는 시료의 양.",
    ),
    (
        "chamber_volume",
        "챔버 용적",
        "space",
        "range",
        "volume",
        "L",
        None,
        "max",
        150,
        None,
    ),
    # --- 정밀도·계측 ----------------------------------------------------------
    (
        "balance_resolution",
        "저울 분해능",
        "accuracy",
        "number",
        "mass",
        "µg",
        None,
        "min",
        110,
        "**작을수록 좋은 값**이라 바닥으로 읽는다.",
    ),
    (
        "displacement_range",
        "변위 측정 범위",
        "accuracy",
        "range",
        "length",
        "µm",
        None,
        "max",
        120,
        None,
    ),
    (
        "accuracy_note",
        "정확도",
        "accuracy",
        "text",
        "",
        "",
        None,
        "max",
        130,
        "「0.1 % Full Scale @ 16 bit」 처럼 조건절이 붙는다. 숫자 칸에 넣게 하면 "
        "사람은 조건절을 버리고, 그러면 그 값은 거짓이 된다.",
    ),
    (
        "hardness_scales",
        "경도 척도",
        "accuracy",
        "text",
        "",
        "",
        None,
        "max",
        140,
        "HRC·HV·Shore A 처럼 이 장비가 낼 수 있는 척도들. 열여섯 대에 적혀 있다.",
    ),
    # --- 설치 조건 ------------------------------------------------------------
    (
        "apparent_power",
        "피상 전력",
        "installation",
        "number",
        "power",
        "VA",
        None,
        "max",
        110,
        "**소비 전력과 다르다.** 역률을 모르면 W 로 못 바꾼다 — 그래서 칸을 나눈다.",
    ),
    # --- 구성 ----------------------------------------------------------------
    (
        "channel_count",
        "채널 수",
        "configuration",
        "range",
        "count",
        "개",
        None,
        "max",
        110,
        None,
    ),
    (
        "measuring_principle",
        "측정 원리",
        "configuration",
        "text",
        "",
        "",
        None,
        "max",
        120,
        "백색광 간섭계·접촉식 프로브처럼 무엇으로 재나. 같은 값을 재도 원리가 다르면 "
        "쓸 수 있는 규격이 다르다.",
    ),
    (
        "cooling_method",
        "냉각 방식",
        "configuration",
        "text",
        "",
        "",
        None,
        "max",
        130,
        None,
    ),
    # --- 추가 승격 (2차) ------------------------------------------------------
    #
    # 첫 반입 뒤 커버율을 분류별로 재 보고 더한 것들이다. 못 들인 값이 UTM 에
    # 59건 남아 있었고, 그중 대부분이 아래 넷이었다.
    (
        "grip_span",
        "그립 간격",
        "space",
        "range",
        "length",
        "mm",
        None,
        "max",
        160,
        "그립 사이 거리. 시편 물림 길이를 정한다.",
    ),
    (
        "compression_plate",
        "압축 판 지름",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        170,
        None,
    ),
    (
        "flexure_support_span",
        "굽힘 지지 간격",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        180,
        "**규격이 지정하는 값이다.** 3점 굽힘은 지지 간격이 결과를 바꾼다.",
    ),
    (
        "inner_width",
        "내부 폭",
        "space",
        "number",
        "length",
        "mm",
        None,
        "max",
        190,
        "챔버 안쪽 치수. **바깥 치수와 다른 물음에 답한다** — 바깥은 「자리가 나나」 "
        "이고 안쪽은 「시편이 들어가나」 다.",
    ),
    ("inner_depth", "내부 깊이", "space", "number", "length", "mm", None, "max", 200, None),
    ("inner_height", "내부 높이", "space", "number", "length", "mm", None, "max", 210, None),
    (
        "chamber_load",
        "시험 영역 하중",
        "capacity",
        "range",
        "mass",
        "kg",
        None,
        "max",
        160,
        "챔버 안에 균등 분포로 올릴 수 있는 무게.",
    ),
    (
        "oil_capacity",
        "오일 용량",
        "installation",
        "number",
        "volume",
        "L",
        None,
        "max",
        120,
        "HDT·비카트 시험조가 채우는 실리콘 오일의 양.",
    ),
    (
        "test_functions",
        "시험 기능",
        "configuration",
        "text",
        "",
        "",
        None,
        "max",
        140,
        "ACW·DCW·IR 처럼 한 대가 겸하는 시험들. 카탈로그가 낱개로 늘어놓는다.",
    ),
]

# --- 온톨로지에서 승격하기 ----------------------------------------------------
#
# `source/catalog/ontology/condition_keys.json` 이 **사양 키의 정본**이 됐다.
# 2026-09-10 감사에서 207종에 한글 이름·차원·단위를 달았고, `build_graph.py` 가
# 거기 없는 키를 쓰면 거절한다 — 즉 **사람이 검토한 어휘**다.
#
# 그래서 정의를 손으로 적는 대신 그 목록에서 승격한다. 「오타가 새 사양이 되는 길이
# 없다」(ADR 0005)는 그대로다: 검토를 우리가 하느냐 온톨로지가 하느냐만 다르고,
# **아무 키나 받는 것이 아니다.** 온톨로지에 없는 키는 여전히 보류된다.
#
# 아래 표는 그 승격에 필요한 두 가지 판단만 담는다 — 어느 그룹에 넣을지, 어느
# 방향으로 읽을지.

#: 차원 -> 사양 그룹. 온톨로지의 `dimension` 을 그대로 받는다.
#:
#: 모르는 차원은 「용량」 이 아니라 **「구성」** 으로 보낸다. 성능처럼 보이게 두면
#: 사람이 그 칸을 성능으로 읽고, 그러면 안 재 본 것이 재 본 것처럼 보인다.
DIMENSION_GROUPS: dict[str, str] = {
    "force": "capacity",
    "torque": "capacity",
    "energy": "capacity",
    "power": "installation",
    "mass": "space",
    "length": "space",
    "area": "space",
    "volume": "space",
    "angle": "range",
    "speed": "range",
    "angular_velocity": "range",
    "acceleration": "range",
    "frequency": "range",
    "temperature": "range",
    "temperature_rate": "range",
    "rate": "range",
    "humidity": "range",
    "pressure": "range",
    "flow": "range",
    "voltage": "range",
    "current": "range",
    "resistance": "range",
    "viscosity": "range",
    "thermal_conductivity": "range",
    "luminance": "range",
    "illuminance": "range",
    "wavelength": "range",
    "leak_rate": "range",
    "time": "accuracy",
    "ratio": "accuracy",
    "level": "accuracy",
    "count": "configuration",
    "mode": "configuration",
    "grade": "configuration",
}

#: 그 밖의 차원이 갈 곳. **모르면 성능이 아니다.**
FALLBACK_GROUP = "configuration"

#: 몇 개 객체에 나와야 승격하나. **1이다 — 온톨로지가 이미 걸렀다.**
#:
#: 처음에는 3으로 뒀는데 그러면 승격이 13건에 그쳤다. 온톨로지 키 207종 중 대부분이
#: 한두 객체에만 나오기 때문이다 — 그런데 그것은 **드물다는 뜻이지 검토를 안 거쳤다는
#: 뜻이 아니다.** ADR 0005 가 막으려던 것은 「만나는 키마다 정의를 만드는 것」 이고,
#: 그 검토를 지금은 온톨로지가 한다.
#:
#: 대신 분류를 붙인다(아래 CATEGORY_SPREAD) — 안 붙이면 UTM 화면에 배터리 사이클러
#: 사양이 뜨고, 그때 목록은 못 쓰게 된다.
PROMOTE_MIN_OBJECTS = 1

#: 이 수보다 많은 분류에서 쓰이면 **공통**으로 둔다.
#:
#: 무게·전원처럼 분류를 가리지 않는 것이 실재한다. 그런 것에 분류를 열 개 붙이면
#: 목록만 길어지고 거르는 값은 없다 — 「거의 어디나」 는 「어디나」 로 적는 편이 낫다.
CATEGORY_SPREAD = 6

#: 작을수록 좋은 값들. 이 조각이 이름에 있으면 **바닥**으로 읽는다.
#:
#: 분해능 0.1 µm 은 「0.1까지 잰다」 이지 「0.1까지만」 이 아니다. 하나로 정해 두면
#: 절반이 거꾸로 반영되고, 거꾸로 반영된 값은 검색이 조용히 틀린 답을 내는
#: 방식으로만 드러난다.
MIN_HINTS = ("resolution", "minimum", "min_", "accuracy", "uniformity", "fluctuation")
