#!/usr/bin/env python3
"""Batch save MCP search results and score. Usage: batch_save.py <json_file>

JSON format:
[
  {"term": "xxx", "trend": {...tavily response...}, "comp": {...tavily response...}},
  ...
]
"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results

CACHE = "/workspace/keywords/.search_cache"
SCORED = "/workspace/keywords/daily_scored.json"
RAW = "/workspace/keywords/daily_raw.json"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

def main():
    with open(sys.argv[1]) as f:
        batch = json.load(f)
    with open(RAW) as f:
        date = json.load(f)["date"]
    os.makedirs(CACHE, exist_ok=True)
    scored = []
    if os.path.exists(SCORED):
        with open(SCORED) as f:
            scored = json.load(f).get("terms", [])
    existing = {s["term"] for s in scored}
    for item in batch:
        term = item["term"]
        for stype in ["trend", "comp"]:
            if stype in item:
                with open(f"{CACHE}/{sf(term)}_{stype}.json", "w") as f:
                    json.dump(item[stype], f, ensure_ascii=False)
        if term not in existing:
            tr = item.get("trend", {}).get("results", [])
            cr = item.get("comp", {}).get("results", [])
            if tr and cr:
                entry = score_from_results(term, tr, cr)
                scored.append(entry)
                existing.add(term)
                print(f"{term}: {entry['trend']} | {entry['main_geo']} | {entry['competition']}")
    with open(SCORED, "w") as f:
        json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": scored},
                  f, ensure_ascii=False, indent=2)
    print(f"Total scored: {len(scored)}")

if __name__ == "__main__":
    main()
