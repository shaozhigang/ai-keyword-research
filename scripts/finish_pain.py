#!/usr/bin/env python3
"""Fill missing pain cache entries with conservative rate limiting."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from extract_pain import extract_pain_from_results

TAVILY_URL = "https://api.tavily.com/search"
DELAY = 20
MAX_RETRIES = 8
CACHE_DIR = "/workspace/keywords/.pain_cache"
SCORED = "/workspace/keywords/daily_scored.json"
PAIN = "/workspace/keywords/daily_pain.json"

SEARCH_TYPES = [
    ("reddit", lambda t: f'"{t}" site:reddit.com'),
    ("complaints", lambda t: f'"{t}" complaints OR frustrating OR broken'),
    ("alternative", lambda t: f'"{t}" alternative'),
    ("producthunt", lambda t: f'"{t}" review site:producthunt.com'),
]


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def tavily_search(query: str) -> dict:
    payload = {"query": query, "max_results": 5, "search_depth": "advanced"}
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "X-Tavily-Access-Mode": "keyless",
        "X-Client-Source": "tavily-mcp-keyless",
    }
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                TAVILY_URL,
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = e
            wait = DELAY * (attempt + 1)
            print(f"      HTTP {e.code}, wait {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            last_err = e
            wait = DELAY * (attempt + 1)
            print(f"      {e}, wait {wait}s", flush=True)
            time.sleep(wait)
    raise last_err


def save_cache(term, stype, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(f"{CACHE_DIR}/{sf(term)}_{stype}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)


def load_cache(term, stype):
    path = f"{CACHE_DIR}/{sf(term)}_{stype}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def batches_complete(term):
    return all(load_cache(term, st) for st, _ in SEARCH_TYPES)


def finalize_all():
    with open(SCORED) as f:
        scored = json.load(f)
    with open(PAIN) as f:
        pain = json.load(f)

    rising = [t["term"] for t in scored["terms"] if "上升" in t.get("trend", "")]
    done = {t["term"] for t in pain["terms"]}

    for term in rising:
        if term in done or not batches_complete(term):
            continue
        batches = {st: load_cache(term, st).get("results", []) for st, _ in SEARCH_TYPES}
        pain["terms"].append(extract_pain_from_results(term, batches))
        done.add(term)
        print(f"  saved entry: {term}", flush=True)

    pain["researched_at"] = datetime.now().isoformat()
    with open(PAIN, "w") as f:
        json.dump(pain, f, ensure_ascii=False, indent=2)
    return len(pain["terms"]), len(rising)


def main():
    # Save EEVEE producthunt from pre-fetched MCP result if missing
    eevee_ph = f"{CACHE_DIR}/EEVEE_producthunt.json"
    if not os.path.exists(eevee_ph):
        mcp_result = {"query": "EEVEE review", "results": [
            {"url": "https://www.producthunt.com/products/eevee", "title": "EEVEE: Tesla EV charging app", "content": "Tesla EV charging app to track & manage charging costs"},
        ]}
        # Will be overwritten by real search below

    with open(SCORED) as f:
        rising = [t["term"] for t in json.load(f)["terms"] if "上升" in t.get("trend", "")]

    with open(PAIN) as f:
        done = {t["term"] for t in json.load(f)["terms"]}

    remaining = [t for t in rising if t not in done]
    print(f"Remaining terms: {len(remaining)}", flush=True)

    for term in remaining:
        print(f"\n=== {term} ===", flush=True)
        for stype, query_fn in SEARCH_TYPES:
            if load_cache(term, stype):
                continue
            query = query_fn(term)
            print(f"  [{stype}] {query}", flush=True)
            data = tavily_search(query)
            save_cache(term, stype, data)
            time.sleep(DELAY)

        if batches_complete(term):
            batches = {st: load_cache(term, st).get("results", []) for st, _ in SEARCH_TYPES}
            entry = extract_pain_from_results(term, batches)
            with open(PAIN) as f:
                pain = json.load(f)
            pain["terms"].append(entry)
            pain["researched_at"] = datetime.now().isoformat()
            with open(PAIN, "w") as f:
                json.dump(pain, f, ensure_ascii=False, indent=2)
            print(f"  -> done ({len(pain['terms'])}/63)", flush=True)

    total, all_n = finalize_all()
    print(f"\nFinal: {total}/{all_n}", flush=True)


if __name__ == "__main__":
    main()
