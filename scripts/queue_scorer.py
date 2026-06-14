#!/usr/bin/env python3
"""Queue-based scorer: writes search requests, waits for MCP results in cache."""
import json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import score_from_results

CACHE = "/workspace/keywords/.search_cache"
QUEUE = "/workspace/keywords/.search_queue"
SCORED = "/workspace/keywords/daily_scored.json"
RAW = "/workspace/keywords/daily_raw.json"
TIMEOUT = 300

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

def get_terms():
    with open(RAW) as f:
        return json.load(f)

def is_complete(term):
    return (os.path.exists(f"{CACHE}/{sf(term)}_trend.json") and
            os.path.exists(f"{CACHE}/{sf(term)}_comp.json"))

def write_queue(term, step):
    os.makedirs(QUEUE, exist_ok=True)
    with open(f"{QUEUE}/current.json", "w") as f:
        json.dump({"term": term, "step": step, "ts": datetime.now().isoformat()}, f)

def wait_cache(term, step):
    path = f"{CACHE}/{sf(term)}_{step}.json"
    for _ in range(TIMEOUT):
        if os.path.exists(path):
            return True
        time.sleep(1)
    return False

def append_scored(entry, date):
    scored = []
    if os.path.exists(SCORED):
        with open(SCORED) as f:
            scored = json.load(f).get("terms", [])
    if any(s["term"] == entry["term"] for s in scored):
        return
    scored.append(entry)
    with open(SCORED, "w") as f:
        json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": scored},
                  f, ensure_ascii=False, indent=2)

def main():
    raw = get_terms()
    date, terms = raw["date"], raw["new_terms"]
    pending = [t for t in terms if not is_complete(t)]
    print(f"Pending: {len(pending)}/{len(terms)}")
    for i, term in enumerate(pending):
        print(f"\n[{i+1}/{len(pending)}] {term}")
        for step in ["trend", "comp"]:
            if os.path.exists(f"{CACHE}/{sf(term)}_{step}.json"):
                continue
            write_queue(term, step)
            print(f"  WAIT: {step}")
            if not wait_cache(term, step):
                print(f"  TIMEOUT: {step}")
                break
            time.sleep(5)
        if is_complete(term):
            with open(f"{CACHE}/{sf(term)}_trend.json") as f:
                tr = json.load(f).get("results", [])
            with open(f"{CACHE}/{sf(term)}_comp.json") as f:
                cr = json.load(f).get("results", [])
            entry = score_from_results(term, tr, cr)
            append_scored(entry, date)
            print(f"  SCORED: {entry['trend']} | {entry['main_geo']} | {entry['competition']}")
    print("\nDone.")

if __name__ == "__main__":
    main()
