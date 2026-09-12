"""시험 항목마다 뜻이 있는 검색축을 **첫 값으로** 심는다 — 사람이 화면에서 고친다.

    python scripts/seed_test_item_axes.py

인장은 하중·속도·온도, 챔버는 온도·습도. 이것은 카탈로그가 갖고 있지 않은 지식이라
반입이 못 채우고, 96 종을 화면에서 하나씩 정하기 전까지 검색은 축 일곱 개를 다 묻는다.
여기 적은 것은 **논쟁의 여지가 없는 것만**이다 — 나머지는 비워 두고 시험 항목 화면이
「검색축 없음」 으로 센다. 멱등이고 **더하기만 한다**: 여기 적힌 짝이 없으면 더하고, 사람이
화면에서 더한 축은 그대로 둔다(빼지 않는다 — 사람이 정한 것을 되돌리면 안 된다). 축이
늘어난 릴리스(전압·전류·토크·가속도·충격 에너지, 2026-09-12)를 배포한 뒤 다시 돌리면
샤르피에 충격 에너지가 붙는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.test_items.models import TestItemConditionKey
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm

survive_cp949()

#: 시험 항목 코드(온톨로지 id) -> 조건 키. 코드로 건다 — 이름은 바뀔 수 있다.
AXES: dict[str, tuple[str, ...]] = {
    "tensile": ("force", "crosshead_speed", "temperature"),
    "compression": ("force", "crosshead_speed", "temperature"),
    "flexure": ("force", "crosshead_speed", "temperature"),
    "shear": ("force", "crosshead_speed"),
    "peel": ("force", "crosshead_speed"),
    "tear": ("force", "crosshead_speed"),
    "fatigue": ("force", "frequency", "temperature"),
    "creep": ("force", "temperature"),
    "damp_heat": ("temperature", "humidity"),
    "thermal_shock": ("temperature",),
    "hast": ("temperature", "humidity"),
    "temperature_cycling": ("temperature",),
    "vibration_sine_random": ("frequency", "acceleration"),
    "mechanical_shock": ("acceleration",),
    "hardness_vickers": ("force",),
    "hardness_rockwell": ("force",),
    "hardness_brinell": ("force",),
    "charpy_impact": ("temperature", "impact_energy"),
    "izod_impact": ("temperature", "impact_energy"),
    "drop_weight_impact": ("impact_energy",),
    "tensile_impact": ("impact_energy",),
    "hdt": ("force", "temperature"),
    "vicat": ("force", "temperature"),
    "torsion": ("torque",),
    "dielectric_withstand": ("voltage",),
    "insulation_resistance": ("voltage",),
    "ground_bond": ("current",),
    "battery_cycle_life": ("voltage", "current"),
}


def main() -> int:
    db = SessionLocal()
    try:
        axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
        if axis is None:
            print("시험 항목 축이 없습니다.")
            return 1
        terms = {
            t.code: t
            for t in db.scalars(
                select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == axis.id)
            )
            if t.code
        }
        keys = {k.key: k for k in db.scalars(select(ConditionKey))}
        added = skipped = missing = 0
        for code, wanted in AXES.items():
            term = terms.get(code)
            if term is None:
                missing += 1
                print(f"  시험 항목 코드 없음: {code}")
                continue
            have = set(
                db.scalars(
                    select(TestItemConditionKey.condition_key_id).where(
                        TestItemConditionKey.test_item_term_id == term.id
                    )
                )
            )
            for key in wanted:
                if key not in keys:
                    print(f"  조건 키 없음: {key}")
                    continue
                if keys[key].id in have:
                    skipped += 1
                    continue
                db.add(
                    TestItemConditionKey(
                        test_item_term_id=term.id, condition_key_id=keys[key].id
                    )
                )
                added += 1
        db.commit()
        print(f"검색축 더함 {added} · 이미 있어 건너뜀 {skipped} · 코드 없음 {missing}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
