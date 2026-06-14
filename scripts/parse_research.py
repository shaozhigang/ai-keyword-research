#!/usr/bin/env python3
"""Parse tavily_research output into scored keyword entry."""
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from analyze import analyze_competition, detect_geo, analyze_trend


def parse_research(term: str, research: dict) -> dict:
    content = research.get("content", "") or ""
    sources = research.get("sources", [])
    content_lower = content.lower()

    # Trend
    if any(w in content_lower for w in ["rising", "increasing", "growing", "spike", "surge", "上升", "增长"]):
        trend = "📈上升"
    elif any(w in content_lower for w in ["declining", "decreasing", "falling", "下降", "衰退"]):
        trend = "📉下降"
    elif any(w in content_lower for w in ["stable", "steady", "平稳", "稳定"]):
        trend = "📊平稳"
    else:
        # Use search result signals
        results = [{"url": s.get("url", ""), "title": s.get("title", ""), "content": ""} for s in sources]
        trend = analyze_trend(term, results, None)

    # Geo
    results_for_geo = [{"url": s.get("url", ""), "title": s.get("title", ""),
                        "content": s.get("title", "")} for s in sources]
    if "china" in content_lower or "chinese" in content_lower or "cn" in content_lower:
        main_geo = "CN"
    elif "india" in content_lower:
        main_geo = "IN"
    elif "united states" in content_lower or "us market" in content_lower:
        main_geo = "US"
    else:
        main_geo = detect_geo(results_for_geo)

    # Competition from research text
    if any(w in content_lower for w in ["low competition", "竞争低", "竞争等级：低", "rating: low", "rating:** low"]):
        competition = "低"
    elif any(w in content_lower for w in ["high competition", "竞争高", "rating: high", "rating:** high", "highly competitive"]):
        competition = "高"
    elif "medium competition" in content_lower or "moderate competition" in content_lower or "medium competitive" in content_lower:
        competition = "中"
    else:
        comp_results = [{"url": s.get("url", ""), "title": s.get("title", ""),
                         "content": ""} for s in sources]
        competition, _ = analyze_competition(term, comp_results)

    # Quality description
    weak_count = sum(1 for s in sources if any(w in s.get("url", "").lower()
                     for w in ["reddit.com", "quora.com", "youtube.com", "twitter.com", "x.com"]))
    tool_count = sum(1 for s in sources if any(w in s.get("url", "").lower()
                     for w in ["github.com", "huggingface.co", ".io", ".dev", "producthunt.com"]))
    total = len(sources) or 1
    if weak_count >= total * 0.5:
        quality = "弱，论坛/社媒为主"
    elif tool_count >= 2:
        quality = f"较强，有{tool_count}个工具站"
    elif weak_count >= total * 0.3:
        quality = "中等，混有论坛帖"
    else:
        quality = "较强，专业站点多"

    if "forum" in content_lower or "reddit" in content_lower:
        if "弱" not in quality:
            quality += "，含论坛帖"

    return {
        "term": term,
        "trend": trend,
        "main_geo": main_geo,
        "competition": competition,
        "top10_quality": quality,
    }


if __name__ == "__main__":
    term = sys.argv[1]
    with open(sys.argv[2]) as f:
        research = json.load(f)
    print(json.dumps(parse_research(term, research), ensure_ascii=False))
