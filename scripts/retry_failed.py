#!/usr/bin/env python3
"""Retry failed terms with longer delay."""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import score_from_results

TAVILY_URL = "https://api.tavily.com/search"
DELAY = 10
CACHE = "/workspace/keywords/.search_cache"
SCORED = "/workspace/keywords/daily_scored.json"

FAILED = [
    "sparse attention",
    "computer-use agents",
    "VLA",
    "speculative decoding",
    "vibe coding",
]


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def tavily_search(query, max_results=10, time_range=None, retries=3):
    payload = {"query": query, "max_results": max_results, "search_depth": "advanced"}
    if time_range:
        payload["time_range"] = time_range
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "X-Tavily-Access-Mode": "keyless",
        "X-Client-Source": "tavily-mcp-keyless",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                TAVILY_URL, data=json.dumps(payload).encode(), headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}")
            time.sleep(DELAY * (attempt + 2))
    raise RuntimeError(f"All retries failed for: {query}")


def save_cache(term, stype, data):
    os.makedirs(CACHE, exist_ok=True)
    with open(f"{CACHE}/{sf(term)}_{stype}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    with open(SCORED) as f:
        data = json.load(f)
    entries = data["terms"]
    by_term = {e["term"]: e for e in entries}

    for term in FAILED:
        print(f"Retry: {term}")
        trend = tavily_search(f'"{term}" news OR trending OR launch 2026', time_range="month")
        save_cache(term, "trend", trend)
        time.sleep(DELAY)
        comp = tavily_search(term)
        save_cache(term, "comp", comp)
        time.sleep(DELAY)
        entry = score_from_results(term, trend.get("results", []), comp.get("results", []))
        by_term[term] = entry
        print(f"  -> {entry['trend']} | {entry['main_geo']} | {entry['competition']}")

    # Preserve order from daily_raw
    with open("/workspace/keywords/daily_raw.json") as f:
        terms = json.load(f)["new_terms"]
    final = [by_term[t] for t in terms if t in by_term]
    data["terms"] = final
    data["scored_at"] = datetime.now().isoformat()
    with open(SCORED, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Done: {len(final)}/64")


if __name__ == "__main__":
    main()
