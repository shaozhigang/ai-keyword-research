#!/usr/bin/env python3
"""Parallel worker: score + pain for a slice of dated terms."""

import fcntl
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from pain_dated import (
    DELAY,
    fallback_score,
    load_source_map,
    process_term_pain,
    score_term_resilient,
    _is_failed,
)

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"
PAIN_DIR = "/workspace/keywords/pain"
LOCK_DIR = "/workspace/keywords/.locks"


def with_lock(name: str):
    os.makedirs(LOCK_DIR, exist_ok=True)
    path = f"{LOCK_DIR}/{name}.lock"
    f = open(path, "w")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_scored(date: str, entries: list):
    path = f"{SCORED_DIR}/{date}.json"
    os.makedirs(SCORED_DIR, exist_ok=True)
    with with_lock(f"scored-{date}"):
        data = {"date": date, "scored_at": datetime.now().isoformat(), "entries": entries}
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def upsert_scored_entry(date: str, entry: dict, term_order: list):
    path = f"{SCORED_DIR}/{date}.json"
    with with_lock(f"scored-{date}"):
        data = load_json(path, {"date": date, "entries": []})
        by_term = {e["term"]: e for e in data.get("entries", [])}
        by_term[entry["term"]] = entry
        data["entries"] = [by_term[t] for t in term_order if t in by_term]
        data["scored_at"] = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def append_pain_entry(date: str, entry: dict):
    path = f"{PAIN_DIR}/{date}.json"
    os.makedirs(PAIN_DIR, exist_ok=True)
    with with_lock(f"pain-{date}"):
        data = load_json(path, {"date": date, "entries": []})
        done = {e["term"] for e in data.get("entries", [])}
        if entry["term"] in done:
            return
        data["entries"].append(entry)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def needs_score(entry: dict) -> bool:
    return "trend" not in entry or (entry.get("top10_quality", "").startswith("分析失败"))


def main():
    if len(sys.argv) < 4:
        print("Usage: parallel_pain_worker.py <date> <worker_id> <num_workers>")
        sys.exit(1)

    date = sys.argv[1]
    worker_id = int(sys.argv[2])
    num_workers = int(sys.argv[3])

    raw_path = f"{RAW_DIR}/{date}.json"
    scored_path = f"{SCORED_DIR}/{date}.json"
    source_map = load_source_map(date)

    with open(raw_path) as f:
        raw = json.load(f)
    term_order = raw.get("new_terms", [])
    my_terms = [t for i, t in enumerate(term_order) if i % num_workers == worker_id]

    scored_data = load_json(scored_path, {"date": date, "entries": []})
    by_term = {e["term"]: e for e in scored_data.get("entries", [])}
    for t in term_order:
        by_term.setdefault(t, {"term": t})

    print(f"Worker {worker_id}/{num_workers}: {len(my_terms)} terms", flush=True)

    for i, term in enumerate(my_terms):
        entry = by_term.get(term, {"term": term})
        if needs_score(entry):
            print(f"[W{worker_id} score {i+1}/{len(my_terms)}] {term}", flush=True)
            try:
                entry = score_term_resilient(term)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                entry = fallback_score(term, source_map)
                entry["top10_quality"] = f"分析失败: {e}；{entry['top10_quality']}"
            by_term[term] = entry
            upsert_scored_entry(date, entry, term_order)
            print(f"  -> {entry.get('trend')} | {entry.get('main_geo')} | {entry.get('competition')}", flush=True)

        if "上升" in entry.get("trend", ""):
            pain_path = f"{PAIN_DIR}/{date}.json"
            pain_data = load_json(pain_path, {"date": date, "entries": []})
            done = {e["term"] for e in pain_data.get("entries", [])}
            if term not in done:
                print(f"[W{worker_id} pain] {term}", flush=True)
                pain_entry = process_term_pain(term)
                append_pain_entry(date, pain_entry)
                print(
                    f"  -> C={len(pain_entry['top_complaints'])} "
                    f"W={len(pain_entry['workarounds'])} "
                    f"D={len(pain_entry['desired_features'])}",
                    flush=True,
                )

    print(f"Worker {worker_id} done.", flush=True)


if __name__ == "__main__":
    main()
