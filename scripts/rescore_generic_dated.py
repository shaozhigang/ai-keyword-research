#!/usr/bin/env python3
"""Rescore generic/short terms with Tavily (academic titles stay heuristic)."""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from smart_rescore import needs_tavily, score_term_with_retry
from pain_dated import load_source_map

SCORED_DIR = "/workspace/keywords/scored"
TERM_DELAY = 5


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"{SCORED_DIR}/{date}.json"
    source_map = load_source_map(date)

    with open(scored_path) as f:
        data = json.load(f)
    entries = data["entries"]
    term_to_idx = {e["term"]: i for i, e in enumerate(entries)}

    to_rescore = [
        t
        for t in term_to_idx
        if needs_tavily(t, source_map.get(t, set()))
        and (
            "学术" in entries[term_to_idx[t]].get("top10_quality", "")
            or "预印本" in entries[term_to_idx[t]].get("top10_quality", "")
        )
    ]
    print(f"日期: {date}, Tavily补扫: {len(to_rescore)} 词")

    tavily_ok = tavily_fail = 0
    for n, term in enumerate(to_rescore):
        idx = term_to_idx[term]
        print(f"[{n + 1}/{len(to_rescore)}] {term[:70]}{'...' if len(term) > 70 else ''}")
        try:
            result = score_term_with_retry(term)
            trend = result["trend"]
            geo = result["main_geo"]
            comp = result["competition"]
            print(f"  [Tavily] → {trend} | {geo} | {comp}")
            tavily_ok += 1
        except Exception as e:
            print(f"  [失败] {e} → 保留启发式")
            tavily_fail += 1
            continue

        entries[idx] = result
        data["entries"] = entries
        with open(scored_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        time.sleep(TERM_DELAY)

    print(f"\n完成! Tavily成功: {tavily_ok}, 失败保留启发式: {tavily_fail}")


if __name__ == "__main__":
    main()
