#!/usr/bin/env python3
"""
Autonomous keyword scorer using Tavily REST API.
Falls back to processing cached MCP results if no API key.

Set TAVILY_API_KEY env var, or populate /workspace/keywords/.search_cache/ manually.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results, merge_and_save

TAVILY_URL = "https://api.tavily.com/search"
DELAY = 5
CACHE_DIR = "/workspace/keywords/.search_cache"
SCORED_PATH = "/workspace/keywords/daily_scored.json"
RAW_PATH = "/workspace/keywords/daily_raw.json"


def safe_filename(term: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in term)


def tavily_search(query: str, max_results: int = 10, time_range: str | None = None) -> dict:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
    }
    if time_range:
        payload["time_range"] = time_range
    req = urllib.request.Request(
        TAVILY_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def save_cache(term: str, search_type: str, data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    sf = safe_filename(term)
    with open(f"{CACHE_DIR}/{sf}_{search_type}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)


def load_cache(term: str, search_type: str) -> dict | None:
    sf = safe_filename(term)
    path = f"{CACHE_DIR}/{sf}_{search_type}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def process_term(term: str, use_api: bool = True) -> dict:
    trend_data = load_cache(term, "trend")
    comp_data = load_cache(term, "comp")

    if use_api and os.environ.get("TAVILY_API_KEY"):
        if not trend_data:
            print(f"  [trend] searching: {term}")
            trend_data = tavily_search(f'"{term}" news OR trending OR launch 2026', time_range="month")
            save_cache(term, "trend", trend_data)
            time.sleep(DELAY)
        if not comp_data:
            print(f"  [comp] searching: {term}")
            comp_data = tavily_search(term)
            save_cache(term, "comp", comp_data)
            time.sleep(DELAY)
    elif not trend_data or not comp_data:
        raise RuntimeError(f"Missing cache for {term}")

    trend_results = trend_data.get("results", [])
    comp_results = comp_data.get("results", [])
    return score_from_results(term, trend_results, comp_results)


def main():
    with open(RAW_PATH) as f:
        raw = json.load(f)
    date = raw["date"]
    terms = raw["new_terms"]

    done = set()
    if os.path.exists(SCORED_PATH):
        with open(SCORED_PATH) as f:
            existing = json.load(f)
            done = {s["term"] for s in existing.get("terms", [])}

    use_api = bool(os.environ.get("TAVILY_API_KEY"))
    print(f"Mode: {'API' if use_api else 'cache-only'} | Total: {len(terms)} | Done: {len(done)}")

    scored_entries = []
    if os.path.exists(SCORED_PATH):
        with open(SCORED_PATH) as f:
            existing = json.load(f)
            scored_entries = existing.get("terms", [])

    for i, term in enumerate(terms):
        if term in done:
            continue
        print(f"[{i+1}/{len(terms)}] {term}")
        try:
            result = process_term(term, use_api=use_api)
            scored_entries.append(result)
            print(f"  -> {result['trend']} | {result['main_geo']} | {result['competition']} | {result['top10_quality']}")
            output = {"date": date, "scored_at": datetime.now().isoformat(), "terms": scored_entries}
            with open(SCORED_PATH, "w") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nComplete: {len(scored_entries)} terms scored -> {SCORED_PATH}")


if __name__ == "__main__":
    main()
