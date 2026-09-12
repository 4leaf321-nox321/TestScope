"""원본 읽기 — `source/catalog` 의 객체·온톨로지. 반입의 모든 단계가 이것을 받는다.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.vocabulary.catalog_specs import (
    SOURCE_SPEC_MAP,
    VARIANT_SUFFIXES,
)

# 패키지 안으로 한 층 들어왔다 — parents[2] 는 backend 다. 저장소 뿌리는 [3].
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "source" / "catalog"


#: 몇 개 객체에 나와야 사양 정의로 승격하나. 이 밑은 보류 목록으로만 보고한다.
PROMOTE_THRESHOLD = 3


class Catalog:
    """읽어 둔 원본. 온톨로지와 객체들."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / "equipment").rglob("*.json"))
        ]
        self.categories = self._load("ontology/categories.json", "categories")
        self.form_factors = self._load("ontology/form_factors.json", "form_factors")
        self.drives = self._load("ontology/drives.json", "drives")
        self.manufacturers = self._load("ontology/manufacturers.json", "manufacturers")
        self.test_items = self._load("ontology/test_items.json", "test_items")
        # 물성과 그 연결 규칙. 둘 다 없어도 반입은 돈다 — 옛 카탈로그 스냅샷에는 없다.
        self.properties = (
            self._load("ontology/properties.json", "properties")
            if (root / "ontology/properties.json").exists()
            else []
        )
        links_path = root / "ontology/property_links.json"
        self.property_links: dict[str, Any] = (
            json.loads(links_path.read_text(encoding="utf-8")) if links_path.exists() else {}
        )

    def _load(self, name: str, key: str) -> list[dict[str, Any]]:
        data = json.loads((self.root / name).read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = data[key]
        return rows


def _ontology(cat: Catalog) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (cat.root / "ontology" / "condition_keys.json").read_text(encoding="utf-8")
    )
    return data


def _ontology_map(cat: Catalog) -> dict[str, tuple[str, float]]:
    """온톨로지가 선언한 **별칭과 단위 변형**을 대표 키로 잇는다.

    ## 왜 온톨로지에 두나

    `nominal_load_kN` 이 `force_kN` 의 다른 이름이라는 것은 **카탈로그 도메인
    지식**이지 TestScope 내부 사정이 아니다. 여기 손 매핑표에 적어 두면 같은 지식이
    두 저장소에 갈라지고, 갈라진 뒤에는 어느 쪽이 맞는지 알 방법이 없다.

    단위 변형은 계수까지 온톨로지가 갖는다 — `force_N` 은 0.001 을 곱해 kN 이 된다.
    """
    out: dict[str, tuple[str, float]] = {}
    for row in _ontology(cat)["keys"]:
        key = row["key"]
        for alias in row.get("aliases") or []:
            out[alias] = (key, 1.0)
        for variant, factor in (row.get("unit_variants") or {}).items():
            out[variant] = (key, float(factor))
    return out


def _ontology_roles(cat: Catalog) -> dict[str, str]:
    """키마다 무엇으로 다루나 — `measure` · `descriptive` · `not_spec`.

    **서술과 품번은 정의로 세우지 않는다.** 「제어 방식」 이나 주문 번호를 사양 칸으로
    만들면 「사양 추가」 목록이 그것들로 채워지고, 그때 목록은 못 쓰게 된다. 값은
    버리지 않는다 — 원문(`raw_specs`)에 그대로 남는다.
    """
    return {row["key"]: row.get("role") or "measure" for row in _ontology(cat)["keys"]}


def _key_shape(cat: Catalog, key: str) -> str:
    """그 키의 값이 실제로 어떤 모양인가 — 정의의 `kind` 를 여기서 정한다.

    **데이터를 보고 정한다.** 이름만 보고 「수치겠지」 하면 절반이 틀리고, 틀린 칸에
    담긴 값은 저장은 되지만 화면이 못 그린다. 여러 모양이 섞이면 구간이 이긴다 —
    구간은 수치 하나도 담을 수 있지만 그 반대는 안 된다.
    """
    shapes: set[str] = set()
    for obj in cat.objects:
        for pool in [obj.get("limits") or {}] + [
            (model.get("specs") or {}) for model in (obj.get("models") or [])
        ]:
            raw = pool.get(key)
            if raw is None:
                continue
            if isinstance(raw, bool):
                shapes.add("boolean")
            elif isinstance(raw, int | float):
                shapes.add("number")
            elif isinstance(raw, dict):
                inner = set(raw) - {"note", "uncertain"}
                shapes.add("range" if inner & {"min", "max", "values"} else "text")
            else:
                shapes.add("text")
    if "range" in shapes:
        return "range"
    if shapes == {"number"}:
        return "number"
    if shapes == {"boolean"}:
        return "boolean"
    return "text"


def _variant_of(key: str) -> tuple[str, str] | None:
    """`vertical_test_space_mm_E2` 처럼 옵션 구성을 뒤에 붙인 키인가.

    **같은 사양의 다른 구성**이지 다른 사양이 아니다. 별도 정의로 만들면 사양표에
    거의 같은 줄이 둘씩 서고, 검색은 어느 쪽을 봐야 할지 모른다.
    """
    for suffix, label in VARIANT_SUFFIXES.items():
        if key.endswith(suffix):
            base = key[: -len(suffix)]
            if base in SOURCE_SPEC_MAP:
                return base, label
    return None
