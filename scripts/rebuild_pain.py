#!/usr/bin/env python3
"""Rebuild daily_pain.json from cached Tavily search results."""
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


def sf(term: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in term)


def load_batches(term: str) -> dict | None:
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

    rising = [t["term"] for t in scored["terms"] if "上升" in t.get("trend", "")]
    entries = []

    for term in rising:
        batches = load_batches(term)
        if not batches:
            print(f"SKIP (incomplete cache): {term}")
            continue
        entry = extract_pain_from_results(term, batches)
        entries.append(entry)
        print(
            f"{term}: complaints={len(entry['top_complaints'])} "
            f"workarounds={len(entry['workarounds'])} "
            f"desired={len(entry['desired_features'])}"
        )

    output = {
        "date": scored.get("date", datetime.now().strftime("%Y-%m-%d")),
        "researched_at": datetime.now().isoformat(),
        "terms": entries,
    }
    with open(PAIN, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nRebuilt {len(entries)}/{len(rising)} terms -> {PAIN}")


if __name__ == "__main__":
    main()
