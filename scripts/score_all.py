#!/usr/bin/env python3
"""
Score all keywords from daily_raw.json using cached Tavily search results.
Cache files are written by the scoring agent via MCP tavily_search calls.

Usage:
  python score_all.py status          # show progress
  python score_all.py save <term> <trend_json> <comp_json>  # save one term's results
  python score_all.py finalize        # write daily_scored.json from cache
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results, merge_and_save

CACHE_DIR = "/workspace/keywords/.search_cache"
SCORED_PATH = "/workspace/keywords/daily_scored.json"
RAW_PATH = "/workspace/keywords/daily_raw.json"


def safe_filename(term: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in term)


def get_terms():
    with open(RAW_PATH) as f:
        return json.load(f)


def status():
    raw = get_terms()
    terms = raw["new_terms"]
    done_trend = done_comp = done_scored = 0
    for term in terms:
        sf = safe_filename(term)
        if os.path.exists(f"{CACHE_DIR}/{sf}_trend.json"):
            done_trend += 1
        if os.path.exists(f"{CACHE_DIR}/{sf}_comp.json"):
            done_comp += 1
    if os.path.exists(SCORED_PATH):
        with open(SCORED_PATH) as f:
            d = json.load(f)
            done_scored = len(d.get("terms", []))
    print(f"Total: {len(terms)} | Trend cached: {done_trend} | Comp cached: {done_comp} | Scored: {done_scored}")
    pending = []
    for term in terms:
        sf = safe_filename(term)
        if not os.path.exists(f"{CACHE_DIR}/{sf}_trend.json"):
            pending.append(("trend", term))
        elif not os.path.exists(f"{CACHE_DIR}/{sf}_comp.json"):
            pending.append(("comp", term))
    if pending:
        print(f"Next: {pending[0][0]} -> {pending[0][1]}")
    return pending


def save_term(term: str, trend_path: str, comp_path: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    sf = safe_filename(term)
    if trend_path != "-":
        with open(trend_path) as f:
            data = json.load(f)
        with open(f"{CACHE_DIR}/{sf}_trend.json", "w") as f:
            json.dump(data, f)
    if comp_path != "-":
        with open(comp_path) as f:
            data = json.load(f)
        with open(f"{CACHE_DIR}/{sf}_comp.json", "w") as f:
            json.dump(data, f)


def save_search_result(term: str, search_type: str, result_json: str):
    """Save a single search result (trend or comp) from JSON string."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    sf = safe_filename(term)
    data = json.loads(result_json) if isinstance(result_json, str) else result_json
    path = f"{CACHE_DIR}/{sf}_{search_type}.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Saved {search_type} for: {term}")


def finalize():
    raw = get_terms()
    date = raw["date"]
    terms = raw["new_terms"]
    entries = []
    for term in terms:
        sf = safe_filename(term)
        trend_path = f"{CACHE_DIR}/{sf}_trend.json"
        comp_path = f"{CACHE_DIR}/{sf}_comp.json"
        if not os.path.exists(trend_path) or not os.path.exists(comp_path):
            print(f"SKIP (incomplete): {term}")
            continue
        with open(trend_path) as f:
            trend_data = json.load(f)
        with open(comp_path) as f:
            comp_data = json.load(f)
        trend_results = trend_data.get("results", []) if isinstance(trend_data, dict) else trend_data
        comp_results = comp_data.get("results", []) if isinstance(comp_data, dict) else comp_data
        entry = score_from_results(term, trend_results, comp_results)
        entries.append(entry)
        print(f"  {entry['term']}: {entry['trend']} | {entry['main_geo']} | {entry['competition']} | {entry['top10_quality']}")

    all_scored = merge_and_save(SCORED_PATH, date, entries)
    print(f"\nDone: {len(all_scored)} terms -> {SCORED_PATH}")
    return all_scored


if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        status()
    elif cmd == "save_result" and len(sys.argv) >= 5:
        save_search_result(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "finalize":
        finalize()
    else:
        print(__doc__)
