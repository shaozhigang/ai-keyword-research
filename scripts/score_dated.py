#!/usr/bin/env python3
"""Score keywords from keywords/raw/{date}.json → keywords/scored/{date}.json."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from score_keywords import score_term

RAW_DIR = "/workspace/keywords/raw"
SCORED_DIR = "/workspace/keywords/scored"


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    raw_path = f"{RAW_DIR}/{date}.json"
    scored_path = f"{SCORED_DIR}/{date}.json"

    os.makedirs(SCORED_DIR, exist_ok=True)

    with open(raw_path) as f:
        raw = json.load(f)

    terms = raw.get("new_terms", [])
    entries = []
    done_terms = set()

    if os.path.exists(scored_path):
        with open(scored_path) as f:
            existing = json.load(f)
            entries = existing.get("entries", [])
            done_terms = {e["term"] for e in entries}

    remaining = [t for t in terms if t not in done_terms]
    print(f"日期: {date}, 总词数: {len(terms)}, 已完成: {len(done_terms)}, 待处理: {len(remaining)}")

    for i, term in enumerate(remaining):
        print(f"[{len(done_terms) + i + 1}/{len(terms)}]", end=" ")
        try:
            result = score_term(term)
            entries.append(result)
            print(f"  → {result['trend']} | {result['main_geo']} | {result['competition']}")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            entries.append({
                "term": term,
                "trend": "📊平稳",
                "main_geo": "US",
                "competition": "中",
                "top10_quality": f"分析失败: {e}",
            })

        output = {"date": date, "entries": entries}
        with open(scored_path, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 共评分 {len(entries)} 个词，结果已写入 {scored_path}")


if __name__ == "__main__":
    main()
