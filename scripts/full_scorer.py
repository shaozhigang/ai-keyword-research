#!/usr/bin/env python3
"""
Full keyword scoring runner.
Populates cache via Tavily MCP searches (called by agent or API),
then writes /keywords/daily_scored.json.

If TAVILY_API_KEY is set, runs fully autonomously via REST API.
Otherwise processes from .search_cache/ populated by MCP calls.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results

TAVILY_URL = "https://api.tavily.com/search"
DELAY = 5
CACHE = "/workspace/keywords/.search_cache"
SCORED = "/workspace/keywords/daily_scored.json"
RAW = "/workspace/keywords/daily_raw.json"


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def tavily_search(query, max_results=10, time_range=None):
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    payload = {"api_key": api_key, "query": query, "max_results": max_results,
               "search_depth": "advanced"}
    if time_range:
        payload["time_range"] = time_range
    req = urllib.request.Request(TAVILY_URL, data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def save_cache(term, stype, data):
    os.makedirs(CACHE, exist_ok=True)
    with open(f"{CACHE}/{sf(term)}_{stype}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)


def load_cache(term, stype):
    path = f"{CACHE}/{sf(term)}_{stype}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def fetch_term(term, use_api=True):
    trend = load_cache(term, "trend")
    comp = load_cache(term, "comp")
    if use_api and os.environ.get("TAVILY_API_KEY"):
        if not trend:
            print(f"  [trend] {term}")
            trend = tavily_search(f'"{term}" news OR trending OR launch 2026', time_range="month")
            save_cache(term, "trend", trend)
            time.sleep(DELAY)
        if not comp:
            print(f"  [comp]  {term}")
            comp = tavily_search(term)
            save_cache(term, "comp", comp)
            time.sleep(DELAY)
    if not trend or not comp:
        return None
    tr = trend.get("results", [])
    cr = comp.get("results", [])
    return score_from_results(term, tr, cr)


def finalize(date, entries):
    with open(SCORED, "w") as f:
        json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": entries},
                  f, ensure_ascii=False, indent=2)


def main():
    with open(RAW) as f:
        raw = json.load(f)
    date, terms = raw["date"], raw["new_terms"]
    use_api = bool(os.environ.get("TAVILY_API_KEY"))

    entries = []
    if os.path.exists(SCORED):
        with open(SCORED) as f:
            entries = json.load(f).get("terms", [])
    done = {e["term"] for e in entries}

    print(f"Mode: {'API' if use_api else 'cache'} | Terms: {len(terms)} | Done: {len(done)}")

    for i, term in enumerate(terms):
        if term in done:
            continue
        print(f"[{i+1}/{len(terms)}] {term}")
        try:
            result = fetch_term(term, use_api)
            if result:
                entries.append(result)
                done.add(term)
                print(f"  -> {result['trend']} | {result['main_geo']} | {result['competition']}")
                finalize(date, entries)
            else:
                print(f"  -> SKIP (cache incomplete)")
        except Exception as e:
            print(f"  -> ERROR: {e}")

    # Score any cached but unscored terms
    for term in terms:
        if term in done:
            continue
        result = fetch_term(term, use_api=False)
        if result:
            entries.append(result)
            done.add(term)
            print(f"  [cache] {term} -> {result['trend']} | {result['competition']}")

    finalize(date, entries)
    print(f"\nFinal: {len(entries)}/{len(terms)} terms scored -> {SCORED}")


if __name__ == "__main__":
    main()
