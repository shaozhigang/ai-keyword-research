#!/usr/bin/env python3
"""Resume pain research with resilient Tavily retries (no crash on 429)."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from smart_pain_dated import process_term_pain_fast, save_pain_output


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    delay = 8
    for a in sys.argv[1:]:
        if a.startswith("--delay="):
            delay = int(a.split("=", 1)[1])

    date = args[0] if args else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"/workspace/keywords/scored/{date}.json"
    pain_path = f"/workspace/keywords/pain/{date}.json"

    with open(scored_path) as f:
        rising = [
            e["term"]
            for e in json.load(f)["entries"]
            if "上升" in e.get("trend", "")
        ]

    entries = []
    done = set()
    if os.path.exists(pain_path):
        with open(pain_path) as f:
            existing = json.load(f)
            entries = existing.get("entries", [])
            done = {e["term"] for e in entries}

    remaining = [t for t in rising if t not in done]
    print(
        f"Rising: {len(rising)} | Done: {len(done)} | Remaining: {len(remaining)} | delay={delay}s",
        flush=True,
    )

    for i, term in enumerate(remaining):
        print(f"\n[{i + 1}/{len(remaining)}] {term[:80]}", flush=True)
        entry = process_term_pain_fast(term, delay=delay)
        entries.append(entry)
        done.add(term)
        save_pain_output(date, entries, pain_path)
        print(
            f"  -> C={len(entry['top_complaints'])} "
            f"W={len(entry['workarounds'])} "
            f"D={len(entry['desired_features'])}",
            flush=True,
        )

    print(f"\nFinal: {len(entries)}/{len(rising)} -> {pain_path}", flush=True)


if __name__ == "__main__":
    main()
