#!/usr/bin/env python3
"""Copy pain cache from canonical PH products to name/fragment variants."""
import json
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from pain_dated import SEARCH_TYPES, pain_cache_path, load_source_map
from smart_pain_dated import get_ph_core_terms, is_junk_fragment
from smart_rescore import needs_tavily


def sf(t: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def find_parent(term: str, canonical: list[str]) -> str | None:
    if term in canonical:
        return term
    for parent in canonical:
        name = parent.split(":")[0].strip()
        if term == name:
            return parent
        if term.startswith(f"{name}:"):
            return parent
    return None


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    raw = json.load(open(f"/workspace/keywords/raw/{date}.json"))
    ph_list = raw.get("source_breakdown", {}).get("producthunt", [])
    canonical: list[str] = []
    seen: set[str] = set()
    for t in ph_list:
        if ":" not in t:
            continue
        name = t.split(":")[0].strip()
        if name in seen:
            continue
        seen.add(name)
        canonical.append(t)

    with open(f"/workspace/keywords/scored/{date}.json") as f:
        rising = [
            e["term"]
            for e in json.load(f)["entries"]
            if "上升" in e.get("trend", "")
        ]
    source_map = load_source_map(date)
    ph_core = get_ph_core_terms(date)

    copied = 0
    for term in rising:
        sources = source_map.get(term, set())
        if not (term in ph_core or needs_tavily(term, sources)):
            continue
        if is_junk_fragment(term, sources, date):
            continue
        parent = find_parent(term, canonical)
        if not parent or parent == term:
            continue
        for st, _ in SEARCH_TYPES:
            src = pain_cache_path(parent, st)
            dst = pain_cache_path(term, st)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
                copied += 1
    print(f"Propagated {copied} cache files for {date}")


if __name__ == "__main__":
    main()
