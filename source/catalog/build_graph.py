"""장비 객체(JSON)를 검증하고 온톨로지 그래프로 엮는다.

    python build_graph.py [source 디렉터리]

만드는 것
- catalog/graph.json   노드(manufacturer·category·test_item·standard·equipment·utility)와 엣지
- catalog/index.md     제조사별 장비 목록과 핵심 한계(사람이 훑어보는 용)
- catalog/sources.json PDF 메타(쪽수·sha256) + 원본 URL

검증
- 필수 키, id 슬러그 형식, manufacturer/category/test_item 이 온톨로지에 있는지,
  relations[].type 이 relations.json 에 있는지, sources[].file 이 실제 PDF 인지.
- 어긋나면 종료 코드 1. 조용히 넘기면 그래프에 끊어진 엣지가 남고, 그때는 어느
  쪽이 맞는지 알 방법이 없다.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
CAT = ROOT / "catalog"
ONT = CAT / "ontology"
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REQUIRED = ("id", "kind", "name", "manufacturer", "category", "test_items", "sources")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    manufacturers = {m["id"]: m for m in load(ONT / "manufacturers.json")["manufacturers"]}
    categories = {c["id"]: c for c in load(ONT / "categories.json")["categories"]}
    test_items = {t["id"]: t for t in load(ONT / "test_items.json")["test_items"]}
    relations = {r["id"]: r for r in load(ONT / "relations.json")["relations"]}
    urls = load(CAT / "urls.json")
    pdf_root = ROOT / "pdf"
    # 추출 메타의 쪽수 — 출처가 없는 쪽을 가리키는 것을 잡기 위해 읽는다.
    pdf_pages: dict[str, int] = {}
    for meta_path in (ROOT / "extracted" / "text").rglob("*.meta.json"):
        try:
            meta = load(meta_path)
        except json.JSONDecodeError:
            continue
        if meta.get("file") and meta.get("pages"):
            pdf_pages[meta["file"]] = meta["pages"]

    errors: list[str] = []
    equipment: dict[str, dict] = {}
    for path in sorted((CAT / "equipment").rglob("*.json")):
        try:
            obj = load(path)
        except json.JSONDecodeError as e:
            errors.append(f"{path}: JSON 오류 {e}")
            continue
        rel = path.relative_to(CAT).as_posix()
        for key in REQUIRED:
            if key not in obj:
                errors.append(f"{rel}: 필수 키 없음 {key}")
        eid = obj.get("id", "")
        if not SLUG.match(eid):
            errors.append(f"{rel}: id 형식 {eid!r}")
        if eid in equipment:
            errors.append(f"{rel}: id 중복 {eid}")
        if obj.get("manufacturer") not in manufacturers:
            errors.append(f"{rel}: 모르는 manufacturer {obj.get('manufacturer')}")
        if obj.get("category") not in categories:
            errors.append(f"{rel}: 모르는 category {obj.get('category')}")
        for t in obj.get("test_items", []):
            if t not in test_items:
                errors.append(f"{rel}: 모르는 test_item {t}")
        for r in obj.get("relations", []):
            if r.get("type") not in relations:
                errors.append(f"{rel}: 모르는 relation type {r.get('type')}")
        for s in obj.get("sources", []):
            if "file" in s:
                if not (pdf_root / s["file"]).exists():
                    errors.append(f"{rel}: PDF 없음 {s['file']}")
                else:
                    # 없는 쪽을 가리키는 인용은 근거가 없는 것과 같다. 조용히 두면
                    # "어디서 왔나" 를 되짚을 수 없다.
                    total = pdf_pages.get(s["file"])
                    if total:
                        over = [p for p in s.get("pages", [])
                                if isinstance(p, int) and p > total]
                        if over:
                            errors.append(
                                f"{rel}: {s['file']} 는 {total}쪽인데 {over} 쪽을 인용")
            elif not s.get("url") and not s.get("origin"):
                # 제조사가 PDF 를 내지 않는 경우가 있다(웹페이지로만 사양 공개).
                # 그때는 url 을 쓰되, 셋 다 없으면 근거가 없는 것이므로 막는다.
                # origin 은 다른 시스템의 행(MaterialTwin 계측기)이다.
                errors.append(f"{rel}: sources 항목에 file 도 url 도 origin 도 없음")
        for item_id in obj.get("measurands_by_item") or {}:
            if item_id not in test_items:
                errors.append(f"{rel}: measurands_by_item 의 모르는 test_item {item_id}")
        for item_id in (obj.get("standards") or {}).get("test_methods_by_item") or {}:
            if item_id not in test_items:
                errors.append(f"{rel}: test_methods_by_item 의 모르는 test_item {item_id}")
        if obj.get("supplements") and obj["supplements"] == eid:
            errors.append(f"{rel}: supplements 가 자기 자신을 가리킴")
        obj["_file"] = rel
        equipment[eid] = obj

    if errors:
        print("\n".join(errors))
        return 1

    # --- 노드와 엣지 ---
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid: str, kind: str, **attrs):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": kind, **attrs}
        return nid

    # 분류와 시험 항목은 같은 id 를 쓰는 것이 7 개 있다(dsc·tga·dma·tma·thermal_conductivity·
    # instrumented_indentation·high_speed_tensile). 축을 접두사로 갈라 두지 않으면 먼저 만든
    # 노드가 이기고 나중 것은 사라져서, `performs` 엣지가 분류 노드를 가리키게 된다.
    def cat_id(cid):
        return "category:" + cid

    def item_id(tid):
        return "test_item:" + tid

    for m in manufacturers.values():
        node(m["id"], "manufacturer", label=m["name"], **{k: v for k, v in m.items() if k not in ("id", "name")})
    for c in categories.values():
        node(cat_id(c["id"]), "category", label=c["label"], label_ko=c["label_ko"], key=c["id"])
        if c.get("parent"):
            edges.append({"source": cat_id(c["id"]), "type": "subcategory_of", "target": cat_id(c["parent"])})
    for t in test_items.values():
        node(item_id(t["id"]), "test_item", label=t["label"], label_ko=t["label_ko"],
             measurands=t["measurands"], key=t["id"])
        for s in t.get("typical_standards", []):
            node(s, "standard", label=s)
            edges.append({"source": item_id(t["id"]), "type": "typical_standard", "target": s})

    for e in equipment.values():
        node(
            e["id"], "equipment", label=e["name"], label_ko=e.get("name_ko"), equipment_kind=e["kind"],
            category=e["category"], manufacturer=e["manufacturer"], limits=e.get("limits", {}),
            models=[m["model"] for m in e.get("models", [])], confidence=e.get("confidence", "catalog"),
            file=e["_file"],
        )
        edges.append({"source": e["id"], "type": "manufactured_by", "target": e["manufacturer"]})
        edges.append({"source": e["id"], "type": "in_category", "target": cat_id(e["category"])})
        for t in e.get("test_items", []):
            edges.append({"source": e["id"], "type": "performs", "target": item_id(t)})
        std = e.get("standards", {})
        for s in std.get("compliance", []):
            node(s, "standard", label=s)
            edges.append({"source": e["id"], "type": "complies_with", "target": s})
        for s in std.get("test_methods", []):
            node(s, "standard", label=s)
            edges.append({"source": e["id"], "type": "supports_method", "target": s})
        for r in e.get("relations", []):
            tgt = r["target"]
            # relations[] 는 온톨로지 id 를 접두사 없이 적는다. 노드 id 로 되돌린다 —
            # 안 그러면 멀쩡한 시험 항목·분류가 placeholder 로 새로 생긴다.
            if tgt in test_items and item_id(tgt) in nodes:
                tgt = item_id(tgt)
            elif tgt in categories and cat_id(tgt) in nodes:
                tgt = cat_id(tgt)
            if tgt not in nodes and tgt not in equipment:
                # 아직 객체가 없는 대상(유틸리티·미확보 기종)은 placeholder 로 남긴다 —
                # 지우면 "무엇이 빠졌나" 를 그래프가 말하지 못한다.
                node(tgt, "utility" if tgt.startswith("utility-") else "placeholder", label=tgt)
            edges.append({"source": e["id"], "type": r["type"], "target": tgt, **({"note": r["note"]} if r.get("note") else {})})
        for s in e.get("sources", []):
            if "file" in s:
                sid = "doc:" + s["file"]
                node(sid, "document", label=s["file"], url=urls.get(s["file"]))
            elif "url" in s:
                sid = "web:" + s["url"]
                node(sid, "document", label=s["url"], url=s["url"], web_only=True)
            else:
                sid = "origin:" + s["origin"]
                node(sid, "document", label=s["origin"], origin=True)
            edges.append({"source": e["id"], "type": "documented_in", "target": sid, **({"pages": s["pages"]} if s.get("pages") else {})})

    # --- 사양 키 검사: limits 는 막고, specs 는 기준선으로 조인다 -------------
    #
    # 두 층의 성격이 다르다. `limits` 는 계열 봉투라 좁고 통제되지만, `models[].specs`
    # 는 자유 형식이라 제조사마다 제 이름으로 적는다 — 지금 1,100종 넘는다.
    #
    # 전부 막으면 오늘 당장 실패한다. 그래서 **기준선**을 둔다: 지금 것은 봐주되
    # **늘면 실패시킨다.** 새 카탈로그를 넣을 때마다 「등록할 것인가, 기존 것의
    # 별칭인가」 를 그 자리에서 묻게 되고, 자연히 줄어든다.
    ont_rows = load(ONT / "condition_keys.json")["keys"]
    known_keys = {k["key"] for k in ont_rows}
    for row in ont_rows:
        known_keys |= set(row.get("aliases") or [])
        known_keys |= set(row.get("unit_variants") or {})

    unregistered: dict[str, int] = {}
    spec_unregistered: dict[str, int] = {}
    for e in equipment.values():
        for k in (e.get("limits") or {}):
            if k not in known_keys:
                unregistered[k] = unregistered.get(k, 0) + 1
        for m in (e.get("models") or []):
            for k in (m.get("specs") or {}):
                if k in ("note", "uncertain") or k in known_keys:
                    continue
                spec_unregistered[k] = spec_unregistered.get(k, 0) + 1

    if unregistered:
        print(f"경고: condition_keys.json 에 없는 limits 키 {len(unregistered)} 종 "
              f"(총 {sum(unregistered.values())}회). 축 이름이 흩어지면 검색이 갈라진다. "
              f"자주 쓰이는 것부터 등록할 것: "
              + ", ".join(k for k, _ in sorted(unregistered.items(), key=lambda x: -x[1])[:8]))

    baseline_file = ONT / "unregistered_baseline.json"
    baseline = load(baseline_file)["count"] if baseline_file.exists() else None
    found = len(spec_unregistered)
    if baseline is None:
        baseline_file.write_text(json.dumps({
            "_comment": "등재 안 된 기종 사양 키의 기준선. **줄이는 것은 자유, 늘리는 것은 실패다.**"
                        " 새 키가 필요하면 condition_keys.json 에 등록하고 이 수를 낮춘다."
                        " tools_suggest_keys.py 가 후보를 뽑아 준다.",
            "count": found,
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"기준선을 세웠습니다: 등재 안 된 기종 사양 키 {found} 종")
    elif found > baseline:
        newest = sorted(spec_unregistered.items(), key=lambda x: -x[1])[:10]
        print(f"실패: 등재 안 된 기종 사양 키가 {baseline} -> {found} 종으로 늘었습니다.")
        print("  새 키를 쓰려면 ontology/condition_keys.json 에 등록하세요"
              " (tools_suggest_keys.py 가 후보를 뽑아 줍니다).")
        print("  많이 쓰인 것: " + ", ".join(f"{k}({n})" for k, n in newest))
        return 1
    elif found < baseline:
        baseline_file.write_text(json.dumps({
            "_comment": load(baseline_file)["_comment"], "count": found,
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"등재 안 된 기종 사양 키 {baseline} -> {found} 종 (기준선을 낮췄습니다)")
    else:
        print(f"등재 안 된 기종 사양 키 {found} 종 (기준선 유지)")

    graph = {"nodes": list(nodes.values()), "edges": edges,
             "counts": {"nodes": len(nodes), "edges": len(edges), "equipment": len(equipment)}}
    (CAT / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- sources.json: meta + url ---
    sources = []
    for meta in sorted((ROOT / "extracted" / "text").rglob("*.meta.json")):
        m = load(meta)
        m["url"] = urls.get(m["file"])
        m["used_by"] = sorted(e["id"] for e in equipment.values()
                          if any(s.get("file") == m["file"] for s in e["sources"]))
        sources.append(m)
    (CAT / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- index.md ---
    def rng(v):
        if not isinstance(v, dict):
            return str(v)
        lo, hi = v.get("min"), v.get("max")
        if lo is not None and hi is not None:
            return f"{lo}–{hi}"
        if hi is not None:
            return f"≤{hi}"
        if lo is not None:
            return f"≥{lo}"
        if v.get("values"):
            return ", ".join(str(x) for x in v["values"][:8])
        return "–"

    by_maker = defaultdict(list)
    for e in equipment.values():
        by_maker[e["manufacturer"]].append(e)
    lines = ["# 장비 카탈로그 색인", "", f"장비 객체 {len(equipment)} 개 · 제조사 {len(by_maker)} · 노드 {len(nodes)} · 엣지 {len(edges)}", "",
             "`limits` 는 시리즈 전체 범위. 단위는 키 이름에 있다(kN, mm/min, degC …). 빈 칸은 미기재.", ""]
    for mid in sorted(by_maker):
        m = manufacturers[mid]
        lines += [f"## {m['name']} (`{mid}`)", "",
                  "| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |",
                  "|---|---|---|---|---|---|---|---|"]
        for e in sorted(by_maker[mid], key=lambda x: x["id"]):
            lim = e.get("limits", {})
            other = "; ".join(f"{k}={rng(v)}" for k, v in lim.items()
                              if k not in ("force_kN", "temperature_degC", "chamber") and not k.startswith("footprint"))
            # 부속·센서가 시험 장비처럼 읽히면 "이 장비로 됩니까" 에 그립이 답하게 된다.
            kind_mark = {"equipment_series": "계열", "equipment_model": "기종",
                         "accessory": "**부속**", "sensor": "**센서**"}.get(e["kind"], e["kind"])
            if e.get("supplements"):
                # 다른 출처가 같은 계열에 보탠 것 — 목록에 같은 이름이 두 줄 서는 이유다.
                kind_mark += f" (보탬→{e['supplements']})"
            temp = lim.get("temperature_degC", "–")
            temp_txt = rng(temp)
            if isinstance(temp, dict) and temp.get("requires_accessory"):
                temp_txt += " (부속)"
            lines.append(
                f"| [{e['id']}]({e['_file']}) | {kind_mark} | {e['category']} | {', '.join(e['test_items'])} | "
                f"{rng(lim.get('force_kN', '–'))} | {temp_txt} | {other[:160]} | {e.get('confidence', 'catalog')} |"
            )
        lines.append("")
    (CAT / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"equipment={len(equipment)} nodes={len(nodes)} edges={len(edges)} sources={len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
