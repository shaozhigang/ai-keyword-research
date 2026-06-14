#!/usr/bin/env python3
"""Process cached search results into daily_scored.json for all terms with complete cache."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results

CACHE = "/workspace/keywords/.search_cache"
SCORED = "/workspace/keywords/daily_scored.json"
RAW = "/workspace/keywords/daily_raw.json"


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def main():
    with open(RAW) as f:
        raw = json.load(f)
    date, terms = raw["date"], raw["new_terms"]

    scored = []
    if os.path.exists(SCORED):
        with open(SCORED) as f:
            scored = json.load(f).get("terms", [])
    by_term = {s["term"]: s for s in scored}

    for term in terms:
        tp = f"{CACHE}/{sf(term)}_trend.json"
        cp = f"{CACHE}/{sf(term)}_comp.json"
        if not os.path.exists(tp) or not os.path.exists(cp):
            continue
        with open(tp) as f:
            tr = json.load(f).get("results", [])
        with open(cp) as f:
            cr = json.load(f).get("results", [])
        by_term[term] = score_from_results(term, tr, cr)

    entries = [by_term[t] for t in terms if t in by_term]
    with open(SCORED, "w") as f:
        json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": entries},
                  f, ensure_ascii=False, indent=2)
    pending = [t for t in terms if not (os.path.exists(f"{CACHE}/{sf(t)}_trend.json") and os.path.exists(f"{CACHE}/{sf(t)}_comp.json"))]
    print(f"Scored: {len(entries)}/{len(terms)}, Pending cache: {len(pending)}")
    if pending:
        print("Next:", pending[0])


if __name__ == "__main__":
    main()
