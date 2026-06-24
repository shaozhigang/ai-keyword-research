#!/usr/bin/env python3
"""Smart pain research: Tavily for product/generic terms, heuristics for academic papers."""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from extract_pain import extract_pain_from_results
from pain_dated import (
    DELAY,
    load_pain_cache,
    load_source_map,
    pain_cache_path,
    process_term_pain,
    save_pain_cache,
    save_pain_output,
    tavily_search,
    SEARCH_TYPES,
)
from smart_rescore import heuristic_academic_score, needs_tavily

ACADEMIC_PAIN = {
    "term": "",
    "top_complaints": ["暂无明确用户抱怨，主要为学术/技术发布内容"],
    "workarounds": [],
    "desired_features": [],
}

RATE_LIMIT_PAIN = {
    "term": "",
    "top_complaints": ["Tavily 限流，暂无法获取用户痛点"],
    "workarounds": [],
    "desired_features": [],
}


def academic_pain(term: str) -> dict:
    e = dict(ACADEMIC_PAIN)
    e["term"] = term
    return e


def rate_limit_pain(term: str) -> dict:
    e = dict(RATE_LIMIT_PAIN)
    e["term"] = term
    return e


def process_term_pain_fast(term: str, delay: int = 8, max_retries: int = 2) -> dict:
    """Pain research with resilient per-query retries."""
    import urllib.error
    import urllib.request

    batches: dict[str, list] = {}
    failed = 0
    for stype, query_fn in SEARCH_TYPES:
        cached = load_pain_cache(term, stype)
        if cached:
            batches[stype] = cached.get("results", [])
            continue

        query = query_fn(term)
        print(f"    [{stype}] {query}", flush=True)
        payload = {"query": query, "max_results": 5, "search_depth": "advanced"}

        api_key = os.environ.get("TAVILY_API_KEY", "")
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-Client-Source"] = "MCP"
        else:
            headers["X-Tavily-Access-Mode"] = "keyless"
            headers["X-Client-Source"] = "tavily-mcp-keyless"

        data = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    "https://api.tavily.com/search",
                    data=json.dumps(payload).encode(),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                wait = delay * (2 ** attempt)
                print(f"      rate limited ({e.code}), retry in {wait}s", flush=True)
                time.sleep(wait)
            except Exception as e:
                wait = delay * (2 ** attempt)
                print(f"      error: {e}, retry in {wait}s", flush=True)
                time.sleep(wait)

        if data is None:
            failed += 1
            batches[stype] = []
            print(f"      skip {stype} after retries", flush=True)
            time.sleep(delay)
            continue

        save_pain_cache(term, stype, data)
        batches[stype] = data.get("results", [])
        time.sleep(delay)

    if failed == len(SEARCH_TYPES):
        return rate_limit_pain(term)
    return extract_pain_from_results(term, batches)


    if failed == len(SEARCH_TYPES):
        return rate_limit_pain(term)
    return extract_pain_from_results(term, batches)


def process_term_complaints_only(term: str, delay: int = 8, max_retries: int = 2) -> dict:
    """Single complaints search for fast finish under rate limits."""
    import urllib.error
    import urllib.request

    stype = "complaints"
    cached = load_pain_cache(term, stype)
    if cached:
        return extract_pain_from_results(term, {stype: cached.get("results", [])})

    query = f'"{term}" complaints OR frustrating OR broken'
    print(f"    [complaints-only] {query}", flush=True)
    payload = {"query": query, "max_results": 5, "search_depth": "advanced"}
    api_key = os.environ.get("TAVILY_API_KEY", "")
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Client-Source"] = "MCP"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"
        headers["X-Client-Source"] = "tavily-mcp-keyless"

    data = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            wait = delay * (2 ** attempt)
            print(f"      rate limited ({e.code}), retry in {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            wait = delay * (2 ** attempt)
            print(f"      error: {e}, retry in {wait}s", flush=True)
            time.sleep(wait)

    if data is None:
        return rate_limit_pain(term)
    save_pain_cache(term, stype, data)
    time.sleep(delay)
    return extract_pain_from_results(term, {stype: data.get("results", [])})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    complaints_only = "--complaints-only" in flags
    date = args[0] if args else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"/workspace/keywords/scored/{date}.json"
    pain_path = f"/workspace/keywords/pain/{date}.json"
    source_map = load_source_map(date)

    with open(scored_path) as f:
        scored = json.load(f)
    rising = [e for e in scored["entries"] if "上升" in e.get("trend", "")]

    pain_entries = []
    done = set()
    if os.path.exists(pain_path):
        with open(pain_path) as f:
            existing = json.load(f)
            pain_entries = existing.get("entries", [])
            done = {e["term"] for e in pain_entries}

    tavily_terms = []
    heuristic_terms = []
    for item in rising:
        term = item["term"]
        if term in done:
            continue
        sources = source_map.get(term, set())
        if needs_tavily(term, sources):
            tavily_terms.append(term)
        else:
            heuristic_terms.append(term)

    tavily_n = heuristic_n = 0
    print(
        f"Rising: {len(rising)} | Done: {len(done)} | "
        f"Heuristic pending: {len(heuristic_terms)} | Tavily pending: {len(tavily_terms)}",
        flush=True,
    )

    for i, term in enumerate(heuristic_terms):
        print(f"\n[H {i+1}/{len(heuristic_terms)}] {term[:70]}{'...' if len(term) > 70 else ''}", flush=True)
        heuristic_n += 1
        entry = academic_pain(term)
        print("  [启发式] 学术/论文词，跳过 Tavily", flush=True)
        pain_entries.append(entry)
        done.add(term)
        save_pain_output(date, pain_entries, pain_path)

    for i, term in enumerate(tavily_terms):
        print(f"\n[T {i+1}/{len(tavily_terms)}] {term[:70]}{'...' if len(term) > 70 else ''}", flush=True)
        tavily_n += 1
        try:
            if complaints_only:
                entry = process_term_complaints_only(term)
            else:
                entry = process_term_pain_fast(term)
        except Exception as e:
            print(f"  ERROR: {e} -> 限流回退", flush=True)
            entry = rate_limit_pain(term)

        pain_entries.append(entry)
        done.add(term)
        save_pain_output(date, pain_entries, pain_path)
        print(
            f"  -> C={len(entry['top_complaints'])} "
            f"W={len(entry['workarounds'])} "
            f"D={len(entry['desired_features'])}",
            flush=True,
        )

    print(
        f"\nFinal: {len(pain_entries)}/{len(rising)} "
        f"(Tavily: {tavily_n}, 启发式: {heuristic_n}) -> {pain_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
