#!/usr/bin/env python3
"""Complete pain file: Tavily for core products, inherit for PH fragments, resilient fallback."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from extract_pain import extract_pain_from_results
from pain_dated import SEARCH_TYPES, load_pain_cache, save_pain_output
from smart_pain_dated import (
    academic_pain,
    not_found_pain,
    process_term_pain_fast,
    rate_limit_pain,
)

PH_PRODUCTS = [
    "Vida: Clone yourself. Let AI do the work before you ask",
    "ChecklistFox: AI checklist maker for beautiful pdfs, free & instant",
    "PhoneDeck: Turn your iPhone into a free Mac controller",
    "CentryAI: Subscription tracker built by someone who forgot 11 of them",
    "Termi Protocol: Watch your AI coding agents build, live in 3D",
]


def find_ph_parent(term: str) -> str | None:
    for parent in PH_PRODUCTS:
        name = parent.split(":")[0].strip()
        if term == parent or term == name:
            return parent
        if term in parent or parent.startswith(term) or term.startswith(name):
            return parent
    return None


def batches_complete(term: str) -> bool:
    return all(load_pain_cache(term, st) for st, _ in SEARCH_TYPES)


def entry_from_cache(term: str) -> dict | None:
    if not batches_complete(term):
        return None
    batches = {st: load_pain_cache(term, st).get("results", []) for st, _ in SEARCH_TYPES}
    return extract_pain_from_results(term, batches)


def clone_entry(term: str, source: dict) -> dict:
    return {
        "term": term,
        "top_complaints": list(source.get("top_complaints", [])),
        "workarounds": list(source.get("workarounds", [])),
        "desired_features": list(source.get("desired_features", [])),
    }


def main():
    delay = 10
    for a in sys.argv[1:]:
        if a.startswith("--delay="):
            delay = int(a.split("=", 1)[1])

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    date = args[0] if args else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"/workspace/keywords/scored/{date}.json"
    pain_path = f"/workspace/keywords/pain/{date}.json"

    with open(scored_path) as f:
        rising = [
            e["term"]
            for e in json.load(f)["entries"]
            if "上升" in e.get("trend", "")
        ]

    entries: list[dict] = []
    by_term: dict[str, dict] = {}
    if os.path.exists(pain_path):
        with open(pain_path) as f:
            existing = json.load(f)
            entries = existing.get("entries", [])
            by_term = {e["term"]: e for e in entries}

    remaining = [t for t in rising if t not in by_term]
    print(
        f"Rising: {len(rising)} | Done: {len(by_term)} | Remaining: {len(remaining)} | delay={delay}s",
        flush=True,
    )

    # 1) PH 核心产品优先做完整四路搜索
    core_pending = [p for p in PH_PRODUCTS if p in remaining]
    for i, term in enumerate(core_pending):
        print(f"\n[PH {i + 1}/{len(core_pending)}] {term}", flush=True)
        entry = entry_from_cache(term)
        if entry is None:
            try:
                entry = process_term_pain_fast(term, delay=delay)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                entry = rate_limit_pain(term)
        by_term[term] = entry
        if term not in {e["term"] for e in entries}:
            entries.append(entry)
        save_pain_output(date, entries, pain_path)
        print(
            f"  -> C={len(entry['top_complaints'])} "
            f"W={len(entry['workarounds'])} D={len(entry['desired_features'])}",
            flush=True,
        )

    remaining = [t for t in rising if t not in by_term]

    # 2) PH 碎片词继承父产品痛点
    still: list[str] = []
    for term in remaining:
        parent = find_ph_parent(term)
        if parent and parent in by_term:
            entry = clone_entry(term, by_term[parent])
            by_term[term] = entry
            entries.append(entry)
            print(f"[inherit] {term} <- {parent.split(':')[0]}", flush=True)
        else:
            still.append(term)

    save_pain_output(date, entries, pain_path)
    remaining = still
    print(f"After inherit: {len(remaining)} remaining", flush=True)

    # 3) 其余词：有完整缓存则提取，否则 Tavily 搜索
    for i, term in enumerate(remaining):
        print(f"\n[{i + 1}/{len(remaining)}] {term[:80]}", flush=True)
        entry = entry_from_cache(term)
        if entry is None:
            try:
                entry = process_term_pain_fast(term, delay=delay)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                entry = rate_limit_pain(term)
        by_term[term] = entry
        entries.append(entry)
        save_pain_output(date, entries, pain_path)
        print(
            f"  -> C={len(entry['top_complaints'])} "
            f"W={len(entry['workarounds'])} D={len(entry['desired_features'])}",
            flush=True,
        )

    # 按 scored 顺序重排
    ordered = [by_term[t] for t in rising if t in by_term]
    save_pain_output(date, ordered, pain_path)
    print(f"\nFinal: {len(ordered)}/{len(rising)} -> {pain_path}", flush=True)


if __name__ == "__main__":
    main()
