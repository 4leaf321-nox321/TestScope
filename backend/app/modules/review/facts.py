"""검토함 줄의 **물음과 근거 자료** — 이름만 보고는 못 정한다.

「3400 — 이 계열이 무슨 시험을 하나」 는 이름만 준 것이다. 계열 이름은 제조사 안에서만 뜻이
있고, 도메인 전문가라도 「Instron · 만능시험기 · 지금 인장·압축·굽힘을 함 · ASTM D638 인용」
까지는 보여야 「접착도 하나」 를 판단한다. 그래서 줄마다

    question   그 대상에 대해 정확히 무엇을 묻는지, 정하면 무슨 일이 생기는지 — 완전한 문장
    facts      대상을 이해하는 데 필요한 사실 몇 줄(제조사·분류·소개·지금 하는 시험·인용
               규격 …)

을 붙인다. 후보 옆의 근거(`reason`)가 「왜 이 후보인가」 라면, 여기는 「대상이 무엇인가」 다.

한 번의 갱신이 계열 430·규격 600 을 돌므로 줄마다 질의하지 않는다 — `Sheet` 가 표를 한 번씩
읽어 사전으로 들고, 줄마다 사전을 찾는다.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment.models import EquipmentModel, EquipmentSeries, ModelSpecValue
from app.modules.methods.models import MethodRequirement, TestMethod, TestMethodItem
from app.modules.properties.models import TestItemProperty
from app.modules.test_items.models import (
    SeriesPendingMethod,
    SeriesTestItem,
    SeriesTestItemMethod,
    TestItemConditionKey,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.vocabulary.specs import SpecDefinition

#: 목록형 사실은 이만큼만 — 시험 항목 열둘을 다 적으면 물음보다 근거가 길어진다.
LIST_CAP = 6
SUMMARY_CAP = 220


def fact(label: str, value: str, link: str | None = None) -> dict[str, Any]:
    return {"label": label, "value": value, "link": link}


def _join(names: list[str], cap: int = LIST_CAP) -> str:
    shown = " · ".join(names[:cap])
    rest = len(names) - cap
    return shown + (f" 외 {rest}" if rest > 0 else "")


def _cut(text: str | None, cap: int = SUMMARY_CAP) -> str:
    body = " ".join((text or "").split())
    return body if len(body) <= cap else body[: cap - 1].rstrip() + "…"


@dataclass
class Sheet:
    """한 번의 갱신 동안 쓰는 사전들. 필요한 것만 게으르게 읽는다."""

    db: Session
    _terms: dict[uuid.UUID, VocabularyTerm] | None = None
    _axis_of: dict[uuid.UUID, str] | None = None
    _aliases: dict[uuid.UUID, list[str]] | None = None
    _series: dict[uuid.UUID, EquipmentSeries] | None = None
    _series_items: dict[uuid.UUID, list[uuid.UUID]] | None = None
    _series_methods: dict[uuid.UUID, list[uuid.UUID]] | None = None
    _series_models: dict[uuid.UUID, list[str]] | None = None
    _methods: dict[uuid.UUID, TestMethod] | None = None
    _method_items: dict[uuid.UUID, list[uuid.UUID]] | None = None
    _item_properties: dict[uuid.UUID, list[uuid.UUID]] | None = None
    _item_axes: dict[uuid.UUID, list[uuid.UUID]] | None = None
    _condition_keys: dict[uuid.UUID, ConditionKey] | None = None
    _requirements: dict[uuid.UUID, list[uuid.UUID]] | None = None
    _title_names: list[tuple[str, re.Pattern[str], VocabularyTerm]] | None = None
    _spec_dimensions: dict[uuid.UUID, dict[uuid.UUID, int]] | None = None
    _editions: dict[str, list[TestMethod]] | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------ 사전

    def terms(self) -> dict[uuid.UUID, VocabularyTerm]:
        if self._terms is None:
            rows = list(self.db.scalars(select(VocabularyTerm)))
            self._terms = {t.id: t for t in rows}
            slugs = {v.id: v.slug for v in self.db.scalars(select(Vocabulary))}
            self._axis_of = {t.id: slugs.get(t.vocabulary_id, "") for t in rows}
        return self._terms

    def term_value(self, term_id: uuid.UUID | None) -> str | None:
        if term_id is None:
            return None
        term = self.terms().get(term_id)
        return term.value if term else None

    def aliases(self, term_id: uuid.UUID) -> list[str]:
        if self._aliases is None:
            self._aliases = defaultdict(list)
            for alias in self.db.scalars(select(VocabularyAlias)):
                self._aliases[alias.term_id].append(alias.value)
        return self._aliases.get(term_id, [])

    def category_path(self, term_id: uuid.UUID | None) -> str | None:
        """「군 · 유형」. 유형만 있으면 유형만."""
        terms = self.terms()
        term = terms.get(term_id) if term_id else None
        if term is None:
            return None
        chain = [term.value]
        seen = {term.id}
        while term is not None and term.parent_term_id and term.parent_term_id not in seen:
            term = terms.get(term.parent_term_id)
            if term is None:
                break
            seen.add(term.id)
            chain.append(term.value)
        chain.reverse()
        return " · ".join(chain)

    def series(self) -> dict[uuid.UUID, EquipmentSeries]:
        if self._series is None:
            self._series = {s.id: s for s in self.db.scalars(select(EquipmentSeries))}
        return self._series

    def series_items(self, series_id: uuid.UUID) -> list[uuid.UUID]:
        if self._series_items is None:
            self._series_items = defaultdict(list)
            for sid, tid in self.db.execute(
                select(SeriesTestItem.series_id, SeriesTestItem.test_item_term_id).distinct()
            ):
                self._series_items[sid].append(tid)
        return self._series_items.get(series_id, [])

    def series_methods(self, series_id: uuid.UUID) -> list[uuid.UUID]:
        """이 계열이 인용한 규격 — 시험 항목에 붙은 것 + 아직 항목 미정인 것."""
        if self._series_methods is None:
            self._series_methods = defaultdict(list)
            for sid, mid in self.db.execute(
                select(SeriesTestItem.series_id, SeriesTestItemMethod.method_id)
                .join(
                    SeriesTestItem,
                    SeriesTestItem.id == SeriesTestItemMethod.series_test_item_id,
                )
                .distinct()
            ):
                self._series_methods[sid].append(mid)
            for sid, mid in self.db.execute(
                select(SeriesPendingMethod.series_id, SeriesPendingMethod.method_id)
            ):
                if mid not in self._series_methods[sid]:
                    self._series_methods[sid].append(mid)
        return self._series_methods.get(series_id, [])

    def series_models(self, series_id: uuid.UUID) -> list[str]:
        if self._series_models is None:
            self._series_models = defaultdict(list)
            for sid, name in self.db.execute(
                select(EquipmentModel.series_id, EquipmentModel.name).order_by(
                    EquipmentModel.name
                )
            ):
                self._series_models[sid].append(name)
        return self._series_models.get(series_id, [])

    def methods(self) -> dict[uuid.UUID, TestMethod]:
        if self._methods is None:
            self._methods = {
                m.id: m
                for m in self.db.scalars(
                    select(TestMethod).where(TestMethod.deleted_at.is_(None))
                )
            }
        return self._methods

    def method_items(self) -> dict[uuid.UUID, list[uuid.UUID]]:
        """규격이 덮는 시험 항목들. **한 번만 받는다** — 검토함은 줄이 수백이다."""
        if self._method_items is None:
            out: dict[uuid.UUID, list[uuid.UUID]] = {}
            for method_id, term_id in self.db.execute(
                select(TestMethodItem.method_id, TestMethodItem.test_item_term_id)
            ).all():
                out.setdefault(method_id, []).append(term_id)
            self._method_items = out
        return self._method_items

    def covers(self, method_id: uuid.UUID, term_id: uuid.UUID) -> bool:
        return term_id in self.method_items().get(method_id, [])

    def method_label(self, method_id: uuid.UUID) -> str | None:
        method = self.methods().get(method_id)
        if method is None:
            return None
        return (
            method.code if method.title == method.code else f"{method.code} — {method.title}"
        )

    def editions(self, code: str) -> list[TestMethod]:
        """같은 코드의 다른 판. 「ISO 6892-1:2016 이 인장」 이면 「ISO 6892-1:2019」 도
        인장이다."""
        if self._editions is None:
            self._editions = defaultdict(list)
            for m in self.methods().values():
                self._editions[m.code].append(m)
        return self._editions.get(code, [])

    def item_properties(self, term_id: uuid.UUID) -> list[uuid.UUID]:
        if self._item_properties is None:
            self._item_properties = defaultdict(list)
            for tid, pid in self.db.execute(
                select(TestItemProperty.test_item_term_id, TestItemProperty.property_term_id)
            ):
                self._item_properties[tid].append(pid)
        return self._item_properties.get(term_id, [])

    def item_axes(self, term_id: uuid.UUID) -> list[uuid.UUID]:
        if self._item_axes is None:
            self._item_axes = defaultdict(list)
            for tid, kid in self.db.execute(
                select(
                    TestItemConditionKey.test_item_term_id,
                    TestItemConditionKey.condition_key_id,
                )
            ):
                self._item_axes[tid].append(kid)
        return self._item_axes.get(term_id, [])

    def condition_keys(self) -> dict[uuid.UUID, ConditionKey]:
        if self._condition_keys is None:
            self._condition_keys = {k.id: k for k in self.db.scalars(select(ConditionKey))}
        return self._condition_keys

    def requirement_axes(self, method_id: uuid.UUID) -> list[uuid.UUID]:
        """규격이 요구 조건으로 적은 축들."""
        if self._requirements is None:
            self._requirements = defaultdict(list)
            for mid, kid in self.db.execute(
                select(MethodRequirement.method_id, MethodRequirement.condition_key_id)
            ):
                self._requirements[mid].append(kid)
        return self._requirements.get(method_id, [])

    def requirement_count(self, method_id: uuid.UUID) -> int:
        return len(self.requirement_axes(method_id))

    def title_matches(self, title: str) -> list[tuple[VocabularyTerm, str]]:
        """규격 제목에 **시험 항목의 영문 이름·별칭**이 들어 있나 — 「Rockwell hardness testing
        of …」 는 로크웰 경도다.

        의미 검색으로도 해 봤는데(bge-m3, 제목 ↔ 시험 항목 카드) 「Rockwell hardness → 인장
        0.61」 같은 오답이 0.6 대에 흔했다 — 「인장」 카드가 허브라 무엇이든 끌어당긴다. 글자
        일치는 87건 중 28건에 걸리고 그중 27건이 한 시험으로 떨어졌다(실측). 적게 맞히되
        맞힌 것은 믿을 수 있는 쪽을 고른다. 네 글자 미만·영문 없는 이름은 안 본다(「DMA」 는
        다른 낱말 안에 들어간다).
        """
        if self._title_names is None:
            self._title_names = []
            terms = self.terms()
            for term in terms.values():
                axis = (self._axis_of or {}).get(term.id)
                if axis != "test_item" or term.status != "active":
                    continue
                for name in [term.value, *self.aliases(term.id)]:
                    if len(name) < 4 or not re.search(r"[A-Za-z]", name):
                        continue
                    pattern = re.compile(
                        r"(?<![a-z])" + re.escape(name.lower()) + r"(?![a-z])", re.IGNORECASE
                    )
                    self._title_names.append((name, pattern, term))
        found: dict[uuid.UUID, tuple[VocabularyTerm, str]] = {}
        for name, pattern, term in self._title_names:
            if term.id not in found and pattern.search(title):
                found[term.id] = (term, name)
        return list(found.values())

    def axis_evidence(self, term: VocabularyTerm) -> dict[uuid.UUID, tuple[int, int]]:
        """검색 조건 물음의 근거 — 축마다 (그 사양이 적힌 기종 수, 요구 조건으로 적은 규격 수).

        「이 시험을 하는 계열의 기종 사양에 온도가 12기종」 이면 온도를 물어도 답이 나온다는
        뜻이고, 「이 시험의 규격 3건이 속도를 요구 조건으로 적었다」 면 속도는 이 시험의
        물음이다. 둘이 기계가 낼 수 있는 가장 강한 근거다."""
        models: dict[uuid.UUID, int] = defaultdict(int)
        methods: dict[uuid.UUID, int] = defaultdict(int)
        for sid in self.series_doing(term.id):
            for kid, n in self.spec_dimensions(sid).items():
                models[kid] += n
        for method in self.methods().values():
            if self.covers(method.id, term.id):
                for kid in self.requirement_axes(method.id):
                    methods[kid] += 1
        return {
            kid: (models.get(kid, 0), methods.get(kid, 0))
            for kid in set(models) | set(methods)
        }

    def spec_dimensions(self, series_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """이 계열의 기종 사양 중 **검색 조건 축에 이어진 것**이 축마다 몇 기종에 적혔나.
        「온도 사양이 12기종에 있다」 는 그 시험에 온도를 물어도 답이 나온다는 뜻이다."""
        if self._spec_dimensions is None:
            self._spec_dimensions = defaultdict(lambda: defaultdict(int))
            for sid, kid in self.db.execute(
                select(EquipmentModel.series_id, SpecDefinition.condition_key_id)
                .join(ModelSpecValue, ModelSpecValue.model_id == EquipmentModel.id)
                .join(SpecDefinition, SpecDefinition.id == ModelSpecValue.definition_id)
                .where(SpecDefinition.condition_key_id.is_not(None))
                .distinct()
            ):
                self._spec_dimensions[sid][kid] += 1
        return self._spec_dimensions.get(series_id, {})

    def series_doing(self, term_id: uuid.UUID) -> list[uuid.UUID]:
        self.series_items(uuid.UUID(int=0))  # 사전을 채운다
        assert self._series_items is not None
        return [sid for sid, tids in self._series_items.items() if term_id in tids]

    # ------------------------------------------------------------ 대상별 사실

    def series_facts(self, series: EquipmentSeries) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        maker = self.term_value(series.maker_term_id)
        if maker:
            out.append(fact("제조사", maker))
        category = self.category_path(series.category_term_id)
        if category:
            out.append(fact("분류", category))
        if series.kind and series.kind != "main":
            out.append(
                fact(
                    "종류",
                    {"accessory": "부속", "sensor": "센서", "software": "소프트웨어"}.get(
                        series.kind, series.kind
                    ),
                )
            )
        if series.summary:
            out.append(fact("소개", _cut(series.summary)))
        items = [v for tid in self.series_items(series.id) if (v := self.term_value(tid))]
        out.append(fact("지금 하는 시험", _join(sorted(items)) if items else "없음"))
        methods = [
            m for mid in self.series_methods(series.id) if (m := self.methods().get(mid))
        ]
        if methods:
            out.append(fact("인용 규격", _join(sorted(m.code for m in methods))))
        models = self.series_models(series.id)
        if models:
            out.append(fact("기종", f"{len(models)}종 — {_join(models, 3)}"))
        return out

    def series_display(self, series: EquipmentSeries) -> str:
        """「Instron 6800」. 계열 이름이 제조사로 시작하면(「Bruker Hysitron …」) 두 번 적지
        않는다."""
        maker = self.term_value(series.maker_term_id)
        if not maker or series.name.lower().startswith(maker.lower()):
            return series.name
        return f"{maker} {series.name}"

    def series_question(self, series: EquipmentSeries, what: str) -> str:
        return f"「{self.series_display(series)}」 계열이 {what}"

    def method_facts(
        self, method: TestMethod, citing: list[uuid.UUID]
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if method.title and method.title != method.code:
            out.append(fact("제목", _cut(method.title, 160)))
        body = self.term_value(method.body_term_id)
        if body:
            out.append(fact("제정기관", body))
        if method.edition:
            out.append(fact("판", method.edition))
        for sid in citing[:3]:
            series = self.series().get(sid)
            if series is None:
                continue
            category = self.category_path(series.category_term_id)
            doing = sorted(v for tid in self.series_items(sid) if (v := self.term_value(tid)))
            head = self.series_display(series)
            detail = " · ".join(
                one for one in (category, _join(doing, 4) if doing else None) if one
            )
            out.append(
                fact(
                    "인용한 계열",
                    f"{head}" + (f" ({detail})" if detail else ""),
                    f"/catalog/equipment-series/{sid}",
                )
            )
        if len(citing) > 3:
            out.append(fact("", f"인용 계열 {len(citing) - 3}개 더"))
        siblings = [
            m
            for m in self.editions(method.code)
            if m.id != method.id and self.method_items().get(m.id)
        ]
        for sibling in siblings[:2]:
            # 판마다 항목이 여럿일 수 있다 — 전부 적는다.
            names = [self.term_value(one) for one in self.method_items().get(sibling.id, [])]
            out.append(
                fact(
                    "다른 판",
                    f"{sibling.code}"
                    + (f":{sibling.edition}" if sibling.edition else "")
                    + f" → {_join([x for x in names if x])}",
                )
            )
        requirements = self.requirement_count(method.id)
        if requirements:
            out.append(fact("요구 조건", f"{requirements}개 적힘"))
        return out

    def edition_codes(self, method: TestMethod) -> list[tuple[str, str]]:
        """다른 판이 정한 시험 항목 (code, 근거). 후보에 얹고 추천의 근거로 쓴다."""
        out: list[tuple[str, str]] = []
        for sibling in self.editions(method.code):
            if sibling.id == method.id:
                continue
            for term_id in self.method_items().get(sibling.id, []):
                term = self.terms().get(term_id)
                if term and term.code:
                    label = sibling.code + (f":{sibling.edition}" if sibling.edition else "")
                    out.append((term.code, f"다른 판 「{label}」 이 이 시험으로 정해져 있음"))
        return out

    def test_item_facts(
        self, term: VocabularyTerm, *, with_conditions: bool = False
    ) -> list[dict[str, Any]]:
        """`with_conditions` 는 검색 조건 물음에서만 — 「기종 사양에 있는 조건」 은 그 물음의
        근거이지 물성 물음의 근거는 아니다."""
        out: list[dict[str, Any]] = []
        aliases = self.aliases(term.id)
        if aliases:
            out.append(fact("별칭", _join(aliases)))
        props = sorted(
            v for pid in self.item_properties(term.id) if (v := self.term_value(pid))
        )
        if props:
            out.append(fact("측정 물성", _join(props)))
        doing = self.series_doing(term.id)
        if doing:
            names = sorted(
                self.series_display(self.series()[sid])
                for sid in doing
                if sid in self.series()
            )
            out.append(fact("하는 계열", f"{len(doing)}개 — {_join(names, 3)}"))
        if doing and with_conditions:
            dims: dict[uuid.UUID, int] = defaultdict(int)
            for sid in doing:
                for kid, n in self.spec_dimensions(sid).items():
                    dims[kid] += n
            keys = self.condition_keys()
            shown = sorted(
                ((keys[kid].label, n) for kid, n in dims.items() if kid in keys),
                key=lambda one: -one[1],
            )
            if shown:
                out.append(
                    fact(
                        "기종 사양에 있는 조건",
                        _join([f"{label} {n}기종" for label, n in shown]),
                    )
                )
        cited: list[str] = []
        for sid in doing:
            for mid in self.series_methods(sid):
                method = self.methods().get(mid)
                if method and self.covers(method.id, term.id) and method.code not in cited:
                    cited.append(method.code)
        if cited:
            out.append(fact("이 시험의 규격", _join(sorted(cited))))
        return out

    def property_facts(
        self, prop: VocabularyTerm, *, except_item: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        self.item_properties(uuid.UUID(int=0))  # 사전을 채운다
        if prop.code:
            out.append(fact("물성 코드", prop.code))
        aliases = self.aliases(prop.id)
        if aliases:
            out.append(fact("물성 별칭", _join(aliases)))
        others = sorted(
            v
            for tid, pids in (self._item_properties or {}).items()
            if tid != except_item and prop.id in pids and (v := self.term_value(tid))
        )
        if others:
            out.append(fact("이 물성을 내는 다른 시험", _join(others)))
        return out
