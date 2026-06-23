#!/usr/bin/env python3
"""Smart rescore: Tavily for products/short terms, heuristics for academic papers."""

import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(__file__))
import score_keywords
score_keywords.SEARCH_DELAY = 12
from score_keywords import score_term
from pain_dated import load_source_map, fallback_score

SCORED_DIR = "/workspace/keywords/scored"
RETRY_DELAY = 30
MAX_RETRIES = 6
TERM_DELAY = 12


def heuristic_academic_score(term: str, sources: set[str]) -> dict:
    """Heuristic for long academic paper titles when Tavily is rate-limited."""
    src = ",".join(sorted(sources)) if sources else "academic"
    short_name = term.split(":")[0].strip() if ":" in term else term
    is_short = len(short_name) < 25 and ":" not in term

    if is_short:
        competition = "中"
        quality = f"短学术新词，来源{src}，前排多为论文/代码页"
    else:
        competition = "低"
        quality = f"弱，主要为学术论文/预印本，来源{src}"

    return {
        "term": term,
        "trend": "📈上升",
        "main_geo": "US",
        "competition": competition,
        "top10_quality": quality,
    }


GENERIC_HINTS = (
    " agents", " models", " matching", " memory", " optimization",
    " distillation", " editing", " scaling", " gap", " bias",
    " integrity", " synthesis", " backpropagation", " tax",
    " representations", " networks", " decoding", " runtime",
    " contagion", " connectivity", " operating system",
)


def is_generic_keyword(term: str) -> bool:
    lower = term.lower()
    if term.startswith("AI "):
        return True
    # Multi-word phrases that are not title-cased project names
    if " " in term:
        words = term.split()
        lower_words = sum(1 for w in words if w == w.lower() or "-" in w)
        if lower_words >= max(1, len(words) - 1):
            return True
    return any(h in lower for h in GENERIC_HINTS) and not re.match(r"^[A-Z][A-Za-z0-9-]+$", term)


def is_long_paper_title(term: str) -> bool:
    return ":" in term or len(term) > 55


def needs_tavily(term: str, sources: set[str]) -> bool:
    if "producthunt" in sources:
        return True
    if is_long_paper_title(term):
        return False
    if is_generic_keyword(term):
        return True
    return False


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

    print(f"日期: {date}, 待处理: {len(failed_indices)}/{len(entries)}")

    tavily_count = heuristic_count = 0

    for n, idx in enumerate(failed_indices):
        term = entries[idx]["term"]
        sources = source_map.get(term, set())
        print(f"[{n + 1}/{len(failed_indices)}] {term[:60]}{'...' if len(term) > 60 else ''}")

        if needs_tavily(term, sources):
            tavily_count += 1
            try:
                result = score_term_with_retry(term)
                print(f"  [Tavily] → {result['trend']} | {result['main_geo']} | {result['competition']}")
            except Exception as e:
                print(f"  [Tavily失败] {e} -> 启发式")
                result = fallback_score(term, source_map)
                result["top10_quality"] = f"限流回退；{result['top10_quality']}"
            time.sleep(TERM_DELAY)
        else:
            heuristic_count += 1
            result = heuristic_academic_score(term, sources)
            print(f"  [启发式] → {result['trend']} | {result['main_geo']} | {result['competition']}")

        entries[idx] = result
        data["entries"] = entries
        with open(scored_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    ok = sum(1 for e in entries if "分析失败" not in e.get("top10_quality", ""))
    print(f"\n完成! 成功 {ok}/{len(entries)} (Tavily: {tavily_count}, 启发式: {heuristic_count})")


if __name__ == "__main__":
    main()
