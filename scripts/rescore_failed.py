#!/usr/bin/env python3
"""Re-score failed entries in keywords/scored/{date}.json with retry/backoff."""

import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))
import score_keywords
score_keywords.SEARCH_DELAY = 12
from score_keywords import score_term, SEARCH_DELAY

SCORED_DIR = "/workspace/keywords/scored"
RETRY_DELAY = 30
MAX_RETRIES = 6
TERM_DELAY = 15


def score_term_with_retry(term: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return score_term(term)
        except HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                print(f"  429 限流，等待 {wait}s 后重试 ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                print(f"  错误，等待 {wait}s 后重试 ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("unreachable")


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"{SCORED_DIR}/{date}.json"

    with open(scored_path) as f:
        data = json.load(f)

    entries = data.get("entries", [])
    failed_indices = [
        i for i, e in enumerate(entries)
        if "分析失败" in e.get("top10_quality", "")
    ]

    print(f"日期: {date}, 待重试: {len(failed_indices)}/{len(entries)}")

    for n, idx in enumerate(failed_indices):
        term = entries[idx]["term"]
        print(f"[{n + 1}/{len(failed_indices)}]", end=" ")
        try:
            result = score_term_with_retry(term)
            entries[idx] = result
            print(f"  → {result['trend']} | {result['main_geo']} | {result['competition']}")
        except Exception as e:
            print(f"  ✗ 仍失败: {e}")
            entries[idx] = {
                "term": term,
                "trend": "📊平稳",
                "main_geo": "US",
                "competition": "中",
                "top10_quality": f"分析失败: {e}",
            }

        data["entries"] = entries
        with open(scored_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        time.sleep(TERM_DELAY)

    ok = sum(1 for e in entries if "分析失败" not in e.get("top10_quality", ""))
    print(f"\n完成! 成功 {ok}/{len(entries)} -> {scored_path}")


if __name__ == "__main__":
    main()
