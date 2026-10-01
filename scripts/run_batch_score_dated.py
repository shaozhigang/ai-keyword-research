#!/usr/bin/env python3
"""Memory-efficient batch scorer: heuristic bulk, then Tavily for ProductHunt only."""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from pain_dated import fallback_score, load_source_map
from score_dated_smart import needs_tavily
from score_keywords import score_term
from smart_rescore import heuristic_academic_score

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"
TERM_DELAY = 5


def _ph_needs_tavily(entry: dict | None) -> bool:
    if entry is None:
        return True
    q = entry.get("top10_quality", "")
    if "有" in q and "工具站" in q:
        return False
    if "论坛/社媒" in q or "专业站点多" in q:
        return False
    markers = ("学术论文", "短学术", "来源标注", "趋势暂按上升", "限流回退")
    return any(m in q for m in markers)


def _write_scored(scored_path: str, date: str, terms: list[str], term_to_entry: dict) -> None:
    ordered = [term_to_entry[t] for t in terms if t in term_to_entry]
    with open(scored_path, "w") as f:
        json.dump({"date": date, "entries": ordered}, f, ensure_ascii=False, indent=2)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    raw_path = f"{RAW_DIR}/{date}.json"
    scored_path = f"{SCORED_DIR}/{date}.json"
    os.makedirs(SCORED_DIR, exist_ok=True)

    source_map = load_source_map(date)
    with open(raw_path) as f:
        terms = json.load(f).get("new_terms", [])

    term_to_entry: dict[str, dict] = {}
    if os.path.exists(scored_path):
        with open(scored_path) as f:
            for e in json.load(f).get("entries", []):
                term_to_entry[e["term"]] = e

    ph_terms = [t for t in terms if needs_tavily(t, source_map.get(t, set()))]
    heuristic_terms = [t for t in terms if t not in ph_terms]

    print(
        f"日期: {date}, 总: {len(terms)}, 已有: {len(term_to_entry)}, "
        f"PH/Tavily: {len(ph_terms)}, 启发式: {len(heuristic_terms)}"
    )

    # Phase 1: heuristics in memory
    added = 0
    for term in heuristic_terms:
        if term in term_to_entry:
            continue
        term_to_entry[term] = heuristic_academic_score(term, source_map.get(term, set()))
        added += 1
    print(f"阶段1 启发式补全: +{added} (累计 {len(term_to_entry)})")

    ordered = [term_to_entry[t] for t in terms if t in term_to_entry]
    with open(scored_path, "w") as f:
        json.dump({"date": date, "entries": ordered}, f, ensure_ascii=False, indent=2)

    # Phase 2: Tavily for ProductHunt terms
    ph_remaining = [t for t in ph_terms if _ph_needs_tavily(term_to_entry.get(t))]

    print(f"阶段2 Tavily 待处理: {len(ph_remaining)}")
    tavily_ok = tavily_fail = 0
    for i, term in enumerate(ph_remaining):
        print(f"[PH {i + 1}/{len(ph_remaining)}] {term[:80]}")
        try:
            result = score_term(term)
            tavily_ok += 1
            print(f"  → {result['trend']} | {result['main_geo']} | {result['competition']}")
        except Exception as e:
            tavily_fail += 1
            print(f"  Tavily失败: {e}")
            result = fallback_score(term, source_map)
            result["top10_quality"] = f"限流回退；{result['top10_quality']}"
        term_to_entry[term] = result
        _write_scored(scored_path, date, terms, term_to_entry)
        if i + 1 < len(ph_remaining):
            time.sleep(TERM_DELAY)

    missing = [t for t in terms if t not in term_to_entry]
    if missing:
        print(f"警告: 仍有 {len(missing)} 词未评分，使用回退")
        for t in missing:
            term_to_entry[t] = fallback_score(t, source_map)

    ordered = [term_to_entry[t] for t in terms]
    with open(scored_path, "w") as f:
        json.dump({"date": date, "entries": ordered}, f, ensure_ascii=False, indent=2)

    print(f"\n完成! {len(ordered)} 词 → {scored_path} (Tavily成功 {tavily_ok}, 回退 {tavily_fail})")


if __name__ == "__main__":
    main()
