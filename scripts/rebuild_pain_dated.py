#!/usr/bin/env python3
"""Build pain entries from cache for rising terms."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) if False else os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(__file__))
from extract_pain import extract_pain_from_results

CACHE_DIR = "/workspace/keywords/.pain_cache"
TYPES = ["reddit", "complaints", "alternative", "producthunt"]


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def entry_for(term: str) -> dict | None:
    batches = {}
    for st in TYPES:
        path = f"{CACHE_DIR}/{sf(term)}_{st}.json"
        if not os.path.exists(path):
            return None
        with open(path) as f:
            batches[st] = json.load(f).get("results", [])
    return extract_pain_from_results(term, batches)


def main():
    date = sys.argv[1]
    terms = sys.argv[2:]
    scored = json.load(open(f"/workspace/keywords/scored/{date}.json"))
    if not terms:
        terms = [e["term"] for e in scored["entries"] if "上升" in e.get("trend", "")]

    pain_path = f"/workspace/keywords/pain/{date}.json"
    existing = {"date": date, "entries": []}
    if os.path.exists(pain_path):
        existing = json.load(open(pain_path))

    done = {e["term"] for e in existing["entries"]}
    for term in terms:
        if term in done:
            continue
        e = entry_for(term)
        if e:
            existing["entries"].append(e)
            done.add(term)
            print(f"OK {term}")
        else:
            print(f"SKIP {term}")

    with open(pain_path, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"Total: {len(existing['entries'])}")


if __name__ == "__main__":
    main()
