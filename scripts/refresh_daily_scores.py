#!/usr/bin/env python3
"""Refresh all keyword scores via Tavily keyless API (same as MCP)."""
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
    payload = {"query": query, "max_results": max_results, "search_depth": "advanced"}
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
        TAVILY_URL, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def save_cache(term, stype, data):
    os.makedirs(CACHE, exist_ok=True)
    with open(f"{CACHE}/{sf(term)}_{stype}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    with open(RAW) as f:
        raw = json.load(f)
    date, terms = raw["date"], raw["new_terms"]
    entries = []

    print(f"Refreshing {len(terms)} terms (delay={DELAY}s between searches)")

    for i, term in enumerate(terms):
        print(f"[{i+1}/{len(terms)}] {term}")
        try:
            trend = tavily_search(f'"{term}" news OR trending OR launch 2026', time_range="month")
            save_cache(term, "trend", trend)
            time.sleep(DELAY)

            comp = tavily_search(term)
            save_cache(term, "comp", comp)
            time.sleep(DELAY)

            entry = score_from_results(term, trend.get("results", []), comp.get("results", []))
            entries.append(entry)
            print(f"  -> {entry['trend']} | {entry['main_geo']} | {entry['competition']} | {entry['top10_quality']}")

            with open(SCORED, "w") as f:
                json.dump({"date": date, "scored_at": datetime.now().isoformat(), "terms": entries},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone: {len(entries)}/{len(terms)} -> {SCORED}")


if __name__ == "__main__":
    main()
