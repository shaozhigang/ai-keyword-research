#!/usr/bin/env python3
"""Regenerate daily_pain.json from pain cache for all rising terms."""
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

    rising = [t["term"] for t in scored["terms"] if "上升" in t.get("trend", "")]
    terms = []
    for term in rising:
        batches = load_batches(term)
        if not batches:
            print(f"SKIP (no cache): {term}")
            continue
        entry = extract_pain_from_results(term, batches)
        terms.append(entry)
        print(f"{term}: C={len(entry['top_complaints'])} W={len(entry['workarounds'])} D={len(entry['desired_features'])}")

    output = {
        "date": scored.get("date", datetime.now().strftime("%Y-%m-%d")),
        "researched_at": datetime.now().isoformat(),
        "terms": terms,
    }
    with open(PAIN, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(terms)} terms -> {PAIN}")


if __name__ == "__main__":
    main()
