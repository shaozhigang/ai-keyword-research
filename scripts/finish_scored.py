#!/usr/bin/env python3
"""Finish remaining keyword scores with single Tavily attempt + fallback."""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from score_keywords import score_term, SEARCH_DELAY
from pain_dated import load_source_map, fallback_score

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"


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
    print(f"待完成: {len(remaining)}")

    for i, term in enumerate(remaining):
        print(f"[{len(done)+i+1}/{len(terms)}] {term}")
        try:
            result = score_term(term)
            print(f"  OK → {result['trend']} | {result['competition']}")
        except Exception as e:
            print(f"  FAIL ({e}) → fallback")
            result = fallback_score(term, source_map)
            if "producthunt" in source_map.get(term, set()):
                result["competition"] = "中"
                result["top10_quality"] = f"限流回退，ProductHunt新词；{result['top10_quality']}"
        entries.append(result)
        with open(scored_path, "w") as f:
            json.dump({"date": date, "entries": entries}, f, ensure_ascii=False, indent=2)
        time.sleep(15)

    print(f"完成 {len(entries)}/{len(terms)}")


if __name__ == "__main__":
    main()
