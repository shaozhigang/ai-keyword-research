#!/usr/bin/env python3
"""Bootstrap scored/{date}.json from raw when Agent 2 has not run."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from pain_dated import load_source_map, fallback_score
from smart_rescore import heuristic_academic_score, needs_tavily

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    raw_path = f"{RAW_DIR}/{date}.json"
    scored_path = f"{SCORED_DIR}/{date}.json"

    if os.path.exists(scored_path):
        print(f"Already exists: {scored_path}")
        return

    with open(raw_path) as f:
        raw = json.load(f)

    source_map = load_source_map(date)
    entries = []
    for term in raw.get("new_terms", []):
        sources = source_map.get(term, set())
        if needs_tavily(term, sources):
            entries.append(fallback_score(term, source_map))
        else:
            entries.append(heuristic_academic_score(term, sources))

    output = {
        "date": date,
        "scored_at": datetime.now().isoformat(),
        "bootstrap": "heuristic (Agent 2 scored file missing)",
        "entries": entries,
    }
    os.makedirs(SCORED_DIR, exist_ok=True)
    with open(scored_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    rising = sum(1 for e in entries if "上升" in e.get("trend", ""))
    print(f"Bootstrapped {len(entries)} terms ({rising} rising) -> {scored_path}")


if __name__ == "__main__":
    main()
