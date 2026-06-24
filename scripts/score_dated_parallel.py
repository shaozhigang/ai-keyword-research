#!/usr/bin/env python3
"""Parallel keyword scorer: split work across workers, merge partial results."""

import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))
from score_keywords import score_term, SEARCH_DELAY
from smart_rescore import score_term_with_retry
from pain_dated import load_source_map, fallback_score

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"
TERM_DELAY = 5


def merge_partials(date: str, num_workers: int) -> dict:
    scored_path = f"{SCORED_DIR}/{date}.json"
    merged: dict[str, dict] = {}

    if os.path.exists(scored_path):
        with open(scored_path) as f:
            for e in json.load(f).get("entries", []):
                merged[e["term"]] = e

    for w in range(num_workers):
        partial = f"{SCORED_DIR}/{date}.w{w}.json"
        if os.path.exists(partial):
            with open(partial) as f:
                for e in json.load(f).get("entries", []):
                    merged[e["term"]] = e

    with open(f"{RAW_DIR}/{date}.json") as f:
        terms = json.load(f).get("new_terms", [])

    entries = [merged[t] for t in terms if t in merged]
    output = {"date": date, "entries": entries}
    with open(scored_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return output


def score_one(term: str, sources: set[str]) -> dict:
    try:
        return score_term_with_retry(term)
    except Exception as e:
        result = fallback_score(term, {term: sources})
        result["top10_quality"] = f"限流回退；{result['top10_quality']}"
        return result


def worker(date: str, worker_id: int, num_workers: int):
    raw_path = f"{RAW_DIR}/{date}.json"
    partial_path = f"{SCORED_DIR}/{date}.w{worker_id}.json"
    source_map = load_source_map(date)

    with open(raw_path) as f:
        terms = json.load(f).get("new_terms", [])

    merge_partials(date, num_workers)
    scored_path = f"{SCORED_DIR}/{date}.json"
    with open(scored_path) as f:
        done = {e["term"] for e in json.load(f).get("entries", [])}

    my_terms = [t for i, t in enumerate(terms) if i % num_workers == worker_id and t not in done]
    entries = []
    if os.path.exists(partial_path):
        with open(partial_path) as f:
            entries = json.load(f).get("entries", [])

    print(f"Worker {worker_id}: {len(my_terms)} terms to process")

    for i, term in enumerate(my_terms):
        print(f"[W{worker_id} {i+1}/{len(my_terms)}] {term[:70]}")
        try:
            result = score_one(term, source_map.get(term, set()))
            entries.append(result)
            print(f"  → {result['trend']} | {result['main_geo']} | {result['competition']}")
        except Exception as e:
            entries.append({
                "term": term,
                "trend": "📊平稳",
                "main_geo": "US",
                "competition": "中",
                "top10_quality": f"分析失败: {e}",
            })
        with open(partial_path, "w") as f:
            json.dump({"date": date, "entries": entries}, f, ensure_ascii=False, indent=2)
        merge_partials(date, num_workers)
        time.sleep(TERM_DELAY)

    print(f"Worker {worker_id} done.")


def main():
    if len(sys.argv) < 2:
        print("Usage: score_dated_parallel.py DATE [worker_id] [num_workers]")
        sys.exit(1)

    date = sys.argv[1]
    if len(sys.argv) == 2:
        num_workers = 4
        os.makedirs(SCORED_DIR, exist_ok=True)
        import subprocess
        procs = []
        for w in range(num_workers):
            p = subprocess.Popen(
                [sys.executable, __file__, date, str(w), str(num_workers)],
                stdout=open(f"{SCORED_DIR}/{date}.w{w}.log", "w"),
                stderr=subprocess.STDOUT,
            )
            procs.append(p)
            time.sleep(2)
        for p in procs:
            p.wait()
        out = merge_partials(date, num_workers)
        print(f"Merged {len(out['entries'])} entries -> {SCORED_DIR}/{date}.json")
        return

    worker_id = int(sys.argv[2])
    num_workers = int(sys.argv[3])
    worker(date, worker_id, num_workers)


if __name__ == "__main__":
    main()
