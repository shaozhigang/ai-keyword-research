#!/usr/bin/env python3
"""Save Tavily MCP result and optionally score incrementally."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import score_from_results

CACHE = "/workspace/keywords/.search_cache"
SCORED = "/workspace/keywords/daily_scored.json"
RAW = "/workspace/keywords/daily_raw.json"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

def save(term, stype, data):
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{sf(term)}_{stype}.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    return path

def try_score(term):
    tp = f"{CACHE}/{sf(term)}_trend.json"
    cp = f"{CACHE}/{sf(term)}_comp.json"
    if not os.path.exists(tp) or not os.path.exists(cp):
        return None
    with open(tp) as f: tr = json.load(f).get("results", [])
    with open(cp) as f: cr = json.load(f).get("results", [])
    return score_from_results(term, tr, cr)

def append_scored(entry):
    from datetime import datetime
    with open(RAW) as f:
        date = json.load(f)["date"]
    scored = []
    if os.path.exists(SCORED):
        with open(SCORED) as f:
            d = json.load(f)
            scored = d.get("terms", [])
    if any(s["term"] == entry["term"] for s in scored):
        return
    scored.append(entry)
    with open(SCORED, "w") as f:
        json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": scored},
                  f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "save":
        term, stype, jfile = sys.argv[2], sys.argv[3], sys.argv[4]
        with open(jfile) as f:
            data = json.load(f)
        save(term, stype, data)
        entry = try_score(term)
        if entry:
            append_scored(entry)
            print(json.dumps(entry, ensure_ascii=False))
        else:
            print(f"Cached {stype} for {term}")
    elif cmd == "status":
        with open(RAW) as f:
            terms = json.load(f)["new_terms"]
        done = sum(1 for t in terms if os.path.exists(f"{CACHE}/{sf(t)}_trend.json") and os.path.exists(f"{CACHE}/{sf(t)}_comp.json"))
        scored_n = 0
        if os.path.exists(SCORED):
            with open(SCORED) as f:
                scored_n = len(json.load(f).get("terms", []))
        print(f"Cached: {done}/{len(terms)}, Scored: {scored_n}")
