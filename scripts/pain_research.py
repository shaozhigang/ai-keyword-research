#!/usr/bin/env python3
"""
Batch pain-point research using Tavily search (keyless mode, same as MCP tavily-mcp).
Reads daily_scored.json, searches rising terms, writes daily_pain.json.
"""

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
DELAY = 5
MAX_RETRIES = 5
CACHE_DIR = "/workspace/keywords/.pain_cache"
SCORED_PATH = "/workspace/keywords/daily_scored.json"
PAIN_PATH = "/workspace/keywords/daily_pain.json"

SEARCH_TYPES = [
    ("reddit", lambda t: f'"{t}" site:reddit.com'),
    ("complaints", lambda t: f'"{t}" complaints OR frustrating OR broken'),
    ("alternative", lambda t: f'"{t}" alternative'),
    ("producthunt", lambda t: f'"{t}" review site:producthunt.com'),
]


def safe_filename(term: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in term)


def tavily_search(query: str, max_results: int = 5) -> dict:
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
    }
    api_key = os.environ.get("TAVILY_API_KEY", "")
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Client-Source"] = "MCP"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"
        headers["X-Client-Source"] = "tavily-mcp-keyless"

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
            if e.code == 429:
                wait = DELAY * (2 ** attempt)
                print(f"      rate limited, retry in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            last_err = e
            wait = DELAY * (2 ** attempt)
            print(f"      error: {e}, retry in {wait}s")
            time.sleep(wait)
    raise last_err


def cache_path(term: str, stype: str) -> str:
    return f"{CACHE_DIR}/{safe_filename(term)}_{stype}.json"


def load_cache(term: str, stype: str) -> dict | None:
    path = cache_path(term, stype)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_cache(term: str, stype: str, data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path(term, stype), "w") as f:
        json.dump(data, f, ensure_ascii=False)


def process_term(term: str) -> dict:
    batches: dict[str, list] = {}

    for stype, query_fn in SEARCH_TYPES:
        cached = load_cache(term, stype)
        if cached:
            batches[stype] = cached.get("results", [])
            continue

        query = query_fn(term)
        print(f"    [{stype}] {query}")
        data = tavily_search(query)
        save_cache(term, stype, data)
        batches[stype] = data.get("results", [])
        time.sleep(DELAY)

    return extract_pain_from_results(term, batches)


def main():
    refresh = "--refresh" in sys.argv
    rebuild = "--rebuild" in sys.argv

    with open(SCORED_PATH) as f:
        scored = json.load(f)

    date = scored.get("date", datetime.now().strftime("%Y-%m-%d"))
    rising = [t for t in scored["terms"] if "上升" in t.get("trend", "")]
    print(f"Rising terms: {len(rising)} | refresh={refresh} | rebuild={rebuild}")

    if rebuild:
        pain_entries = []
        for i, item in enumerate(rising):
            term = item["term"]
            print(f"[{i + 1}/{len(rising)}] rebuild {term}")
            batches = {}
            for stype, _ in SEARCH_TYPES:
                cached = load_cache(term, stype)
                if not cached:
                    print(f"  SKIP (no cache for {stype})")
                    continue
                batches[stype] = cached.get("results", [])
            if len(batches) < len(SEARCH_TYPES):
                print(f"  SKIP incomplete cache")
                continue
            entry = extract_pain_from_results(term, batches)
            pain_entries.append(entry)
        output = {
            "date": date,
            "researched_at": datetime.now().isoformat(),
            "terms": pain_entries,
        }
        with open(PAIN_PATH, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nRebuilt: {len(pain_entries)}/{len(rising)} terms -> {PAIN_PATH}")
        return

    pain_entries = [] if refresh else []
    done = set()
    if not refresh and os.path.exists(PAIN_PATH):
        with open(PAIN_PATH) as f:
            existing = json.load(f)
            pain_entries = existing.get("terms", [])
            done = {p["term"] for p in pain_entries}

    terms_to_process = [t["term"] for t in rising] if refresh else [
        t["term"] for t in rising if t["term"] not in done
    ]
    print(f"Done: {len(done)} | To process: {len(terms_to_process)}")

    for i, term in enumerate(terms_to_process):
        idx = (0 if refresh else len(done)) + i + 1
        print(f"[{idx}/{len(rising)}] {term}")
        try:
            if refresh:
                for stype, query_fn in SEARCH_TYPES:
                    query = query_fn(term)
                    print(f"    [{stype}] {query}")
                    data = tavily_search(query)
                    save_cache(term, stype, data)
                    time.sleep(DELAY)
                batches = {
                    st: load_cache(term, st).get("results", [])
                    for st, _ in SEARCH_TYPES
                }
                entry = extract_pain_from_results(term, batches)
            else:
                entry = process_term(term)
            pain_entries.append(entry)
            done.add(term)
            print(f"  -> complaints={len(entry['top_complaints'])} "
                  f"workarounds={len(entry['workarounds'])} "
                  f"desired={len(entry['desired_features'])}")
            output = {
                "date": date,
                "researched_at": datetime.now().isoformat(),
                "terms": pain_entries,
            }
            with open(PAIN_PATH, "w") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nFinal: {len(pain_entries)}/{len(rising)} terms -> {PAIN_PATH}")


if __name__ == "__main__":
    main()
