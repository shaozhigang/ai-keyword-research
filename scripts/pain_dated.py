#!/usr/bin/env python3
"""Pain research for dated keywords/scored/{date}.json -> keywords/pain/{date}.json."""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import analyze_trend, detect_geo, analyze_competition
from extract_pain import extract_pain_from_results

TAVILY_URL = "https://api.tavily.com/search"
DELAY = 5
MAX_RETRIES = 6
CACHE_DIR = "/workspace/keywords/.pain_cache"
SEARCH_CACHE = "/workspace/keywords/.search_cache"

SEARCH_TYPES = [
    ("reddit", lambda t: f'"{t}" site:reddit.com'),
    ("complaints", lambda t: f'"{t}" complaints OR frustrating OR broken'),
    ("alternative", lambda t: f'"{t}" alternative'),
    ("producthunt", lambda t: f'"{t}" review site:producthunt.com'),
]


def safe_filename(term: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in term)


def tavily_search(query: str, max_results: int = 5) -> dict:
    payload = {"query": query, "max_results": max_results, "search_depth": "advanced"}
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
            wait = DELAY * (2 ** attempt)
            print(f"      rate limited ({e.code}), retry in {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            last_err = e
            wait = DELAY * (2 ** attempt)
            print(f"      error: {e}, retry in {wait}s", flush=True)
            time.sleep(wait)
    raise last_err


def score_term_resilient(term: str) -> dict:
    """Score a term using retry-enabled Tavily search."""
    recent_query = f'"{term}" news OR trending OR launch 2026'
    recent_data = tavily_search(recent_query, max_results=10)
    recent_results = recent_data.get("results", [])
    time.sleep(DELAY)

    older_data = tavily_search(f'"{term}"', max_results=10)
    older_results = older_data.get("results", [])
    time.sleep(DELAY)

    trend = analyze_trend(term, recent_results, older_results)
    main_geo = detect_geo(recent_results + older_results)

    comp_data = tavily_search(term, max_results=10)
    comp_results = comp_data.get("results", [])
    time.sleep(DELAY)

    competition, top10_quality = analyze_competition(term, comp_results)
    return {
        "term": term,
        "trend": trend,
        "main_geo": main_geo,
        "competition": competition,
        "top10_quality": top10_quality,
    }


def load_source_map(date: str) -> dict[str, set[str]]:
    raw_path = f"/workspace/keywords/raw/{date}.json"
    if not os.path.exists(raw_path):
        return {}
    with open(raw_path) as f:
        raw = json.load(f)
    mapping: dict[str, set[str]] = {}
    for src, terms in raw.get("source_breakdown", {}).items():
        for term in terms:
            mapping.setdefault(term, set()).add(src)
    return mapping


def fallback_score(term: str, source_map: dict[str, set[str]]) -> dict:
    sources = source_map.get(term, set())
    if sources & {"producthunt", "huggingface", "arxiv"}:
        trend = "📈上升"
        quality = f"来源标注为{','.join(sorted(sources))}新词，趋势暂按上升处理"
    else:
        trend = "📊平稳"
        quality = "评分接口限流，暂按平稳处理"
    return {
        "term": term,
        "trend": trend,
        "main_geo": "US",
        "competition": "中",
        "top10_quality": quality,
    }


def _is_failed(entry: dict) -> bool:
    return "分析失败" in entry.get("top10_quality", "")


def apply_fallback_for_failed(date: str) -> int:
    """Mark failed scores using source-based heuristics."""
    scored_path = f"/workspace/keywords/scored/{date}.json"
    source_map = load_source_map(date)
    with open(scored_path) as f:
        data = json.load(f)
    updated = 0
    for entry in data["entries"]:
        if _is_failed(entry):
            fb = fallback_score(entry["term"], source_map)
            entry.update(fb)
            updated += 1
    data["scored_at"] = datetime.now().isoformat()
    with open(scored_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


def save_pain_output(date: str, entries: list, pain_path: str):
    output = {"date": date, "entries": entries}
    os.makedirs(os.path.dirname(pain_path), exist_ok=True)
    with open(pain_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def load_pain_entries(pain_path: str) -> tuple[list, set]:
    entries = []
    done = set()
    if os.path.exists(pain_path):
        with open(pain_path) as f:
            existing = json.load(f)
            entries = existing.get("entries", [])
            done = {e["term"] for e in entries}
    return entries, done


def run_pain_for_term(date: str, term: str, pain_path: str, entries: list, done: set) -> None:
    if term in done:
        return
    print(f"\n[pain] {term}", flush=True)
    entry = process_term_pain(term)
    entries.append(entry)
    done.add(term)
    print(
        f"  -> C={len(entry['top_complaints'])} "
        f"W={len(entry['workarounds'])} "
        f"D={len(entry['desired_features'])}",
        flush=True,
    )
    save_pain_output(date, entries, pain_path)


def ensure_scored_and_pain(date: str, pain_path: str, rescore_failed: bool = True) -> None:
    scored_path = f"/workspace/keywords/scored/{date}.json"
    raw_path = f"/workspace/keywords/raw/{date}.json"
    source_map = load_source_map(date)

    entries: list[dict] = []
    if os.path.exists(scored_path):
        with open(scored_path) as f:
            data = json.load(f)
            entries = data.get("entries", [])

    if not entries:
        if not os.path.exists(raw_path):
            raise FileNotFoundError(f"Missing {raw_path}")
        with open(raw_path) as f:
            raw = json.load(f)
        entries = [{"term": t} for t in raw.get("new_terms", [])]

    pain_entries, pain_done = load_pain_entries(pain_path)
    by_term = {e["term"]: e for e in entries}
    term_order = [e["term"] for e in entries]

    to_score = [
        e["term"] for e in entries
        if len(e) <= 1 or (rescore_failed and _is_failed(e))
    ]

    if to_score:
        print(f"Scoring {len(to_score)} terms for {date}...", flush=True)

    for i, term in enumerate(to_score):
        print(f"[score {i+1}/{len(to_score)}] {term}", flush=True)
        try:
            entry = score_term_resilient(term)
            by_term[term] = entry
            print(f"  -> {entry['trend']} | {entry['main_geo']} | {entry['competition']}", flush=True)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            by_term[term] = fallback_score(term, source_map)
            by_term[term]["top10_quality"] = f"分析失败: {e}；{by_term[term]['top10_quality']}"

        scored_output = {
            "date": date,
            "scored_at": datetime.now().isoformat(),
            "entries": [by_term[t] for t in term_order if t in by_term],
        }
        os.makedirs(os.path.dirname(scored_path), exist_ok=True)
        with open(scored_path, "w") as f:
            json.dump(scored_output, f, ensure_ascii=False, indent=2)

        if "上升" in by_term[term].get("trend", ""):
            run_pain_for_term(date, term, pain_path, pain_entries, pain_done)

    # pain for already-scored rising terms (e.g. resume)
    for term in term_order:
        item = by_term.get(term, {})
        if "上升" in item.get("trend", "") and term not in pain_done:
            run_pain_for_term(date, term, pain_path, pain_entries, pain_done)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    date = args[0] if args else datetime.now().strftime("%Y-%m-%d")
    pain_path = f"/workspace/keywords/pain/{date}.json"
    score_only = "--score-only" in flags
    pain_only = "--pain-only" in flags

    fallback_only = "--fallback-only" in flags

    if fallback_only:
        n = apply_fallback_for_failed(date)
        print(f"Applied fallback to {n} terms", flush=True)
        return

    if pain_only:
        scored = json.load(open(f"/workspace/keywords/scored/{date}.json"))
        rising = [e for e in scored.get("entries", []) if "上升" in e.get("trend", "")]
        pain_entries, pain_done = load_pain_entries(pain_path)
        print(f"Rising terms: {len(rising)} | Done: {len(pain_done)}", flush=True)
        for item in rising:
            if item["term"] not in pain_done:
                run_pain_for_term(date, item["term"], pain_path, pain_entries, pain_done)
        print(f"\nFinal: {len(pain_entries)}/{len(rising)} -> {pain_path}", flush=True)
        return

    if score_only:
        ensure_scored_and_pain(date, pain_path, rescore_failed=True)
        scored = json.load(open(f"/workspace/keywords/scored/{date}.json"))
        rising = sum(1 for e in scored["entries"] if "上升" in e.get("trend", ""))
        print(f"\nScored. Rising: {rising}", flush=True)
        return

    ensure_scored_and_pain(date, pain_path, rescore_failed=True)
    pain_entries, _ = load_pain_entries(pain_path)
    scored = json.load(open(f"/workspace/keywords/scored/{date}.json"))
    rising = sum(1 for e in scored["entries"] if "上升" in e.get("trend", ""))
    print(f"\nFinal: pain {len(pain_entries)}/{rising} -> {pain_path}", flush=True)


def pain_cache_path(term: str, stype: str) -> str:
    return f"{CACHE_DIR}/{safe_filename(term)}_{stype}.json"


def load_pain_cache(term: str, stype: str) -> dict | None:
    path = pain_cache_path(term, stype)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_pain_cache(term: str, stype: str, data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(pain_cache_path(term, stype), "w") as f:
        json.dump(data, f, ensure_ascii=False)


def process_term_pain(term: str) -> dict:
    batches: dict[str, list] = {}
    for stype, query_fn in SEARCH_TYPES:
        cached = load_pain_cache(term, stype)
        if cached:
            batches[stype] = cached.get("results", [])
            continue

        query = query_fn(term)
        print(f"    [{stype}] {query}", flush=True)
        data = tavily_search(query)
        save_pain_cache(term, stype, data)
        batches[stype] = data.get("results", [])
        time.sleep(DELAY)

    return extract_pain_from_results(term, batches)


if __name__ == "__main__":
    main()
