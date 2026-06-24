#!/usr/bin/env python3
"""Smart dated scorer: Tavily for products/short terms, heuristics for academic papers."""

import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))
from smart_rescore import heuristic_academic_score, score_term_with_retry
from pain_dated import load_source_map, fallback_score


def needs_tavily(term: str, sources: set[str]) -> bool:
    """Only ProductHunt commercial terms need live Tavily search."""
    return "producthunt" in sources

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"
TERM_DELAY = 5


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    raw_path = f"{RAW_DIR}/{date}.json"
    scored_path = f"{SCORED_DIR}/{date}.json"
    source_map = load_source_map(date)

    os.makedirs(SCORED_DIR, exist_ok=True)

    with open(raw_path) as f:
        terms = json.load(f).get("new_terms", [])

    entries = []
    done_terms = set()
    if os.path.exists(scored_path):
        with open(scored_path) as f:
            entries = json.load(f).get("entries", [])
            done_terms = {e["term"] for e in entries}

    remaining = [t for t in terms if t not in done_terms]
    tavily_n = sum(1 for t in remaining if needs_tavily(t, source_map.get(t, set())))
    print(f"日期: {date}, 总: {len(terms)}, 已完成: {len(done_terms)}, 待处理: {len(remaining)} (Tavily: {tavily_n}, 启发式: {len(remaining)-tavily_n})")

    for i, term in enumerate(remaining):
        sources = source_map.get(term, set())
        print(f"[{len(done_terms)+i+1}/{len(terms)}] {term[:70]}{'...' if len(term)>70 else ''}")

        if needs_tavily(term, sources):
            try:
                result = score_term_with_retry(term)
                print(f"  [Tavily] → {result['trend']} | {result['main_geo']} | {result['competition']}")
            except Exception as e:
                print(f"  [Tavily失败] {e}")
                result = fallback_score(term, source_map)
                result["top10_quality"] = f"限流回退；{result['top10_quality']}"
            time.sleep(TERM_DELAY)
        else:
            result = heuristic_academic_score(term, sources)
            print(f"  [启发式] → {result['trend']} | {result['main_geo']} | {result['competition']}")

        entries.append(result)
        with open(scored_path, "w") as f:
            json.dump({"date": date, "entries": entries}, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 共 {len(entries)} 个词 → {scored_path}")


if __name__ == "__main__":
    main()
