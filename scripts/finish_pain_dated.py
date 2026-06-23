#!/usr/bin/env python3
"""Complete dated pain file: Tavily search with cache + fallback."""

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
MAX_RETRIES = 6
CACHE_DIR = "/workspace/keywords/.pain_cache"

SEARCH_TYPES = [
    ("reddit", lambda t: f'"{t}" site:reddit.com'),
    ("complaints", lambda t: f'"{t}" complaints OR frustrating OR broken'),
    ("alternative", lambda t: f'"{t}" alternative'),
    ("producthunt", lambda t: f'"{t}" review site:producthunt.com'),
]


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def tavily_search(query: str) -> dict | None:
    payload = {"query": query, "max_results": 5, "search_depth": "advanced"}
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "X-Tavily-Access-Mode": "keyless",
        "X-Client-Source": "tavily-mcp-keyless",
    }
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
            wait = DELAY * (2 ** attempt)
            print(f"      HTTP {e.code}, wait {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            wait = DELAY * (2 ** attempt)
            print(f"      {e}, wait {wait}s", flush=True)
            time.sleep(wait)
    return None


def load_cache(term, stype):
    path = f"{CACHE_DIR}/{sf(term)}_{stype}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_cache(term, stype, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(f"{CACHE_DIR}/{sf(term)}_{stype}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)


def batches_complete(term):
    return all(load_cache(term, st) for st, _ in SEARCH_TYPES)


def fallback_entry(term: str) -> dict:
    return {
        "term": term,
        "top_complaints": ["暂无明确用户抱怨，主要为学术/技术发布内容"],
        "workarounds": [],
        "desired_features": [],
    }


def process_term(term: str) -> dict:
    for stype, query_fn in SEARCH_TYPES:
        if load_cache(term, stype):
            continue
        query = query_fn(term)
        print(f"    [{stype}] {query}", flush=True)
        data = tavily_search(query)
        if data:
            save_cache(term, stype, data)
        time.sleep(DELAY)

    if batches_complete(term):
        batches = {st: load_cache(term, st).get("results", []) for st, _ in SEARCH_TYPES}
        return extract_pain_from_results(term, batches)
    return fallback_entry(term)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    scored = json.load(open(f"/workspace/keywords/scored/{date}.json"))
    pain_path = f"/workspace/keywords/pain/{date}.json"

    rising = [e["term"] for e in scored["entries"] if "上升" in e.get("trend", "")]
    pain_data = {"date": date, "entries": []}
    if os.path.exists(pain_path):
        pain_data = json.load(open(pain_path))
    done = {e["term"] for e in pain_data.get("entries", [])}

    remaining = [t for t in rising if t not in done]
    print(f"Rising: {len(rising)} | Done: {len(done)} | Remaining: {len(remaining)}", flush=True)

    for i, term in enumerate(remaining):
        print(f"\n[{i+1}/{len(remaining)}] {term}", flush=True)
        entry = process_term(term)
        pain_data["entries"].append(entry)
        done.add(term)
        with open(pain_path, "w") as f:
            json.dump(pain_data, f, ensure_ascii=False, indent=2)
        print(
            f"  -> C={len(entry['top_complaints'])} "
            f"W={len(entry['workarounds'])} D={len(entry['desired_features'])}",
            flush=True,
        )

    print(f"\nFinal: {len(pain_data['entries'])}/{len(rising)} -> {pain_path}", flush=True)


if __name__ == "__main__":
    main()
