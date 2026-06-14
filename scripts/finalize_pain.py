#!/usr/bin/env python3
"""Finalize pain entries from cache for all rising terms missing from daily_pain.json."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from extract_pain import extract_pain_from_results

CACHE_DIR = "/workspace/keywords/.pain_cache"
SCORED = "/workspace/keywords/daily_scored.json"
PAIN = "/workspace/keywords/daily_pain.json"
TYPES = ["reddit", "complaints", "alternative", "producthunt"]


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def load_batches(term):
    batches = {}
    for st in TYPES:
        path = f"{CACHE_DIR}/{sf(term)}_{st}.json"
        if not os.path.exists(path):
            return None
        with open(path) as f:
            batches[st] = json.load(f).get("results", [])
    return batches


def main():
    with open(SCORED) as f:
        scored = json.load(f)
    with open(PAIN) as f:
        pain = json.load(f)

    rising = [t["term"] for t in scored["terms"] if "上升" in t.get("trend", "")]
    done = {t["term"] for t in pain["terms"]}
    added = 0

    for term in rising:
        if term in done:
            continue
        batches = load_batches(term)
        if not batches:
            print(f"SKIP (incomplete cache): {term}")
            continue
        entry = extract_pain_from_results(term, batches)
        pain["terms"].append(entry)
        done.add(term)
        added += 1
        print(f"ADDED: {term}")

    pain["researched_at"] = datetime.now().isoformat()
    with open(PAIN, "w") as f:
        json.dump(pain, f, ensure_ascii=False, indent=2)
    print(f"\nTotal: {len(pain['terms'])}/{len(rising)} (+{added})")


if __name__ == "__main__":
    main()
