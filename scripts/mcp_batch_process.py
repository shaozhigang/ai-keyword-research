#!/usr/bin/env python3
"""
Batch keyword scorer using Tavily search (same API as MCP tavily_search / tavily-mcp keyless mode).
Saves cache files and writes daily_scored.json using analyze.py logic.
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
    """Call Tavily search API (keyless mode, same as MCP tavily-mcp)."""
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
    }
    if time_range:
        payload["time_range"] = time_range
    api_key = os.environ.get("TAVILY_API_KEY", "")
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Client-Source"] = "MCP"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"
        headers["X-Client-Source"] = "tavily-mcp-keyless"
    req = urllib.request.Request(
        TAVILY_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def save_cache(term, stype, data):
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{sf(term)}_{stype}.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def load_cache(term, stype):
    path = f"{CACHE}/{sf(term)}_{stype}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def process_term(term):
    trend = load_cache(term, "trend")
    comp = load_cache(term, "comp")

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

    tr = trend.get("results", [])
    cr = comp.get("results", [])
    return score_from_results(term, tr, cr)


def main():
    with open(RAW) as f:
        raw = json.load(f)
    date, terms = raw["date"], raw["new_terms"]

    scored = []
    done = set()
    if os.path.exists(SCORED):
        with open(SCORED) as f:
            existing = json.load(f)
            scored = existing.get("terms", [])
            done = {s["term"] for s in scored}

    remaining = [t for t in terms if t not in done]
    print(f"Total: {len(terms)} | Done: {len(done)} | Remaining: {len(remaining)}")

    for i, term in enumerate(remaining):
        idx = terms.index(term) + 1
        print(f"[{idx}/{len(terms)}] {term}")
        try:
            entry = process_term(term)
            scored.append(entry)
            done.add(term)
            print(f"  -> {entry['trend']} | {entry['main_geo']} | {entry['competition']} | {entry['top10_quality']}")
            with open(SCORED, "w") as f:
                json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": scored},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Ensure all terms with complete cache are scored
    by_term = {s["term"]: s for s in scored}
    for term in terms:
        if term in by_term:
            continue
        tp, cp = f"{CACHE}/{sf(term)}_trend.json", f"{CACHE}/{sf(term)}_comp.json"
        if os.path.exists(tp) and os.path.exists(cp):
            with open(tp) as f:
                tr = json.load(f).get("results", [])
            with open(cp) as f:
                cr = json.load(f).get("results", [])
            by_term[term] = score_from_results(term, tr, cr)

    final = [by_term[t] for t in terms if t in by_term]
    with open(SCORED, "w") as f:
        json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": final},
                  f, ensure_ascii=False, indent=2)
    print(f"\nFinal: {len(final)}/{len(terms)} terms scored -> {SCORED}")


if __name__ == "__main__":
    main()
