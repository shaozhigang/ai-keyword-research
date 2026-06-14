#!/usr/bin/env python3
"""Batch keyword scorer - reads cached Tavily results and writes daily_scored.json."""

import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results, merge_and_save

CACHE_DIR = "/workspace/keywords/.search_cache"
SCORED_PATH = "/workspace/keywords/daily_scored.json"
RAW_PATH = "/workspace/keywords/daily_raw.json"


def safe_filename(term: str) -> str:
    return term.replace("/", "_").replace(" ", "_").replace(".", "_")


def process_cached():
    with open(RAW_PATH) as f:
        raw = json.load(f)
    date = raw["date"]
    terms = raw["new_terms"]

    scored_entries = []
    for term in terms:
        sf = safe_filename(term)
        trend_path = os.path.join(CACHE_DIR, f"{sf}_trend.json")
        comp_path = os.path.join(CACHE_DIR, f"{sf}_comp.json")

        if not os.path.exists(trend_path) or not os.path.exists(comp_path):
            print(f"SKIP (no cache): {term}")
            continue

        with open(trend_path) as f:
            trend_data = json.load(f)
        with open(comp_path) as f:
            comp_data = json.load(f)

        trend_results = trend_data.get("results", trend_data) if isinstance(trend_data, dict) else trend_data
        comp_results = comp_data.get("results", comp_data) if isinstance(comp_data, dict) else comp_data

        entry = score_from_results(term, trend_results, comp_results)
        scored_entries.append(entry)
        print(f"OK: {term} → {entry['trend']} | {entry['main_geo']} | {entry['competition']}")

    if scored_entries:
        all_scored = merge_and_save(SCORED_PATH, date, scored_entries)
        print(f"\nSaved {len(all_scored)} terms to {SCORED_PATH}")
    else:
        print("No cached results to process")


def list_pending():
    with open(RAW_PATH) as f:
        raw = json.load(f)
    terms = raw["new_terms"]

    done = set()
    if os.path.exists(SCORED_PATH):
        with open(SCORED_PATH) as f:
            existing = json.load(f)
            done = {s["term"] for s in existing.get("terms", [])}

    pending = []
    for term in terms:
        sf = safe_filename(term)
        trend_path = os.path.join(CACHE_DIR, f"{sf}_trend.json")
        comp_path = os.path.join(CACHE_DIR, f"{sf}_comp.json")
        if term not in done and (not os.path.exists(trend_path) or not os.path.exists(comp_path)):
            pending.append(term)

    print(json.dumps(pending, ensure_ascii=False))


if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "pending":
        list_pending()
    else:
        process_cached()
