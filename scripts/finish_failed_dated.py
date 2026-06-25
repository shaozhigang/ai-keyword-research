#!/usr/bin/env python3
"""Finish failed entries: one Tavily attempt with backoff, then source-based fallback."""

import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))
import score_keywords

score_keywords.SEARCH_DELAY = 15
from score_keywords import score_term
from pain_dated import load_source_map, fallback_score
from smart_rescore import heuristic_academic_score, needs_tavily

SCORED_DIR = "/workspace/keywords/scored"
TERM_DELAY = 25
MAX_RETRIES = 1
RETRY_BASE = 30


def score_with_retry(term: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return score_term(term)
        except HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                wait = RETRY_BASE * attempt
                print(f"  429 限流，等待 {wait}s ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("unreachable")


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"{SCORED_DIR}/{date}.json"
    source_map = load_source_map(date)

    with open(scored_path) as f:
        data = json.load(f)

    entries = data.get("entries", [])
    failed_indices = [
        i for i, e in enumerate(entries)
        if "分析失败" in e.get("top10_quality", "")
    ]

    print(f"日期: {date}, 待完成: {len(failed_indices)}/{len(entries)}")

    for n, idx in enumerate(failed_indices):
        term = entries[idx]["term"]
        sources = source_map.get(term, set())
        print(f"[{n + 1}/{len(failed_indices)}] {term[:70]}")

        if not needs_tavily(term, sources):
            result = heuristic_academic_score(term, sources)
            print(f"  [启发式] → {result['trend']} | {result['competition']}")
        else:
            try:
                result = score_with_retry(term)
                print(f"  [Tavily] → {result['trend']} | {result['competition']}")
            except Exception as e:
                print(f"  [回退] {e}")
                result = fallback_score(term, source_map)
                if "producthunt" in sources:
                    result["competition"] = "中"
                    result["top10_quality"] = (
                        f"限流回退，ProductHunt新词；前排多为产品页/社媒"
                    )
                else:
                    result["top10_quality"] = f"限流回退；{result['top10_quality']}"

        entries[idx] = result
        data["entries"] = entries
        with open(scored_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if n + 1 < len(failed_indices):
            time.sleep(TERM_DELAY)

    ok = sum(1 for e in entries if "分析失败" not in e.get("top10_quality", ""))
    print(f"\n完成! 成功 {ok}/{len(entries)} -> {scored_path}")


if __name__ == "__main__":
    main()
