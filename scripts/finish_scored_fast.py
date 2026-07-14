#!/usr/bin/env python3
"""Fast finish: heuristic for academic, single Tavily attempt or fallback for ProductHunt."""

import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))
from score_keywords import score_term
from score_dated_smart import needs_tavily
from smart_rescore import heuristic_academic_score
from pain_dated import load_source_map, fallback_score

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"
TERM_DELAY = 5


def score_once_or_fallback(term: str, source_map: dict) -> dict:
    try:
        return score_term(term)
    except HTTPError as e:
        if e.code in (429, 432):
            result = fallback_score(term, source_map)
            result["top10_quality"] = f"限流回退；{result['top10_quality']}"
            return result
        raise
    except Exception:
        result = fallback_score(term, source_map)
        result["top10_quality"] = f"限流回退；{result['top10_quality']}"
        return result


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    raw_path = f"{RAW_DIR}/{date}.json"
    scored_path = f"{SCORED_DIR}/{date}.json"
    source_map = load_source_map(date)

    with open(raw_path) as f:
        terms = json.load(f).get("new_terms", [])

    entries = []
    done = set()
    if os.path.exists(scored_path):
        with open(scored_path) as f:
            entries = json.load(f).get("entries", [])
            done = {e["term"] for e in entries}

    remaining = [t for t in terms if t not in done]
    print(f"日期: {date}, 已完成: {len(done)}, 待处理: {len(remaining)}")

    for i, term in enumerate(remaining):
        sources = source_map.get(term, set())
        print(f"[{len(done)+i+1}/{len(terms)}] {term[:70]}{'...' if len(term) > 70 else ''}")

        if needs_tavily(term, sources):
            # 已触发限流时直接回退，避免长重试拖慢全量补全
            result = fallback_score(term, source_map)
            if "producthunt" in sources:
                result["competition"] = "中"
            result["top10_quality"] = f"限流回退，ProductHunt新词；{result['top10_quality']}"
            print(f"  [回退] → {result['trend']} | {result['main_geo']} | {result['competition']}")
        else:
            result = heuristic_academic_score(term, sources)
            print(f"  [启发式] → {result['trend']} | {result['main_geo']} | {result['competition']}")

        entries.append(result)
        with open(scored_path, "w") as f:
            json.dump({"date": date, "entries": entries}, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 共 {len(entries)} 个词 → {scored_path}")


if __name__ == "__main__":
    main()
