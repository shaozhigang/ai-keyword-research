#!/usr/bin/env python3
"""
Process all keywords: reads terms, scores from cache, reports pending.
Run alongside agent MCP calls that populate .search_cache/
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results

CACHE = "/workspace/keywords/.search_cache"
SCORED = "/workspace/keywords/daily_scored.json"
RAW = "/workspace/keywords/daily_raw.json"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

def get_pending():
    with open(RAW) as f:
        terms = json.load(f)["new_terms"]
    pending = []
    for term in terms:
        if not os.path.exists(f"{CACHE}/{sf(term)}_trend.json") or \
           not os.path.exists(f"{CACHE}/{sf(term)}_comp.json"):
            pending.append(term)
    return pending

def score_all_cached():
    with open(RAW) as f:
        raw = json.load(f)
    date, terms = raw["date"], raw["new_terms"]
    entries = []
    for term in terms:
        tp, cp = f"{CACHE}/{sf(term)}_trend.json", f"{CACHE}/{sf(term)}_comp.json"
        if not os.path.exists(tp) or not os.path.exists(cp):
            continue
        with open(tp) as f: tr = json.load(f).get("results", [])
        with open(cp) as f: cr = json.load(f).get("results", [])
        entries.append(score_from_results(term, tr, cr))
    from datetime import datetime
    out = {"date": date, "scored_at": datetime.now().isoformat(), "terms": entries}
    with open(SCORED, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return len(entries)

if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    if sys.argv[1:] == ["pending"]:
        print(json.dumps(get_pending(), ensure_ascii=False))
    elif sys.argv[1:] == ["score"]:
        n = score_all_cached()
        print(f"Scored {n} terms")
    else:
        pending = get_pending()
        print(f"Pending: {len(pending)}")
        for t in pending[:5]:
            print(f"  - {t}")
