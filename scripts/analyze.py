#!/usr/bin/env python3
"""Keyword scoring analysis logic - works with Tavily search results."""

import json
import re
import sys
from datetime import datetime

WEAK_DOMAINS = {
    "reddit.com", "quora.com", "stackoverflow.com", "stackexchange.com",
    "medium.com", "dev.to", "hashnode.dev", "substack.com",
    "twitter.com", "x.com", "facebook.com", "linkedin.com",
    "youtube.com", "tiktok.com", "pinterest.com",
    "zhihu.com", "weibo.com", "bilibili.com", "douban.com",
}

TOOL_INDICATORS = {
    "github.com", "huggingface.co", "producthunt.com",
    "vercel.com", "firecrawl.dev", "elevenlabs.io",
    ".io", ".dev", ".app", "docs.", "api.",
}

TLD_GEO = {
    ".cn": "CN", ".us": "US", ".in": "IN", ".uk": "UK", ".de": "DE",
    ".jp": "JP", ".kr": "KR", ".fr": "FR", ".au": "AU", ".br": "BR",
    ".ru": "RU", ".tw": "TW", ".hk": "HK", ".sg": "SG",
}

CN_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def detect_geo(results: list) -> str:
    geo_counts: dict[str, int] = {"US": 0, "CN": 0, "IN": 0, "UK": 0, "OTHER": 0}
    for r in results:
        url = r.get("url", "")
        content = (r.get("content", "") or "") + (r.get("title", "") or "")
        for tld, geo in TLD_GEO.items():
            if tld in url:
                geo_counts[geo] = geo_counts.get(geo, 0) + 2
                break
        if CN_PATTERN.search(content):
            geo_counts["CN"] += 2
        if any(d in url for d in [".com", ".org", ".net", "github.com", "arxiv.org",
                                   "huggingface.co", "producthunt.com"]):
            geo_counts["US"] += 1
    top = max(geo_counts, key=geo_counts.get)
    return top if geo_counts[top] > 0 else "US"


def analyze_trend(term: str, recent_results: list, older_results: list | None = None) -> str:
    recent_count = len(recent_results)
    older_count = len(older_results) if older_results else 0
    recent_signals = 0
    term_lower = term.lower()

    for r in recent_results:
        title = (r.get("title", "") or "").lower()
        content = (r.get("content", "") or "").lower()
        if term_lower in title:
            recent_signals += 2
        if any(w in content for w in ["launch", "release", "new", "announce", "trending",
                                         "发布", "上线", "推出", "just dropped", "now released"]):
            recent_signals += 1
        if any(w in title for w in ["2026", "2025"]):
            recent_signals += 1

    if recent_count == 0 and older_count == 0:
        return "📊平稳"
    if recent_count > max(older_count, 1) * 1.5 or recent_signals >= 4:
        return "📈上升"
    if recent_count < older_count * 0.5 and recent_signals <= 1 and older_count > 2:
        return "📉下降"
    if recent_signals >= 2:
        return "📈上升"
    return "📊平稳"


def is_weak_domain(url: str) -> bool:
    url_lower = url.lower()
    return any(w in url_lower for w in WEAK_DOMAINS)


def is_tool_site(url: str, title: str) -> bool:
    url_lower = url.lower()
    title_lower = title.lower()
    if any(t in url_lower for t in TOOL_INDICATORS):
        return True
    if any(w in title_lower for w in ["tool", "platform", "app", "api", "sdk", "docs"]):
        return True
    return False


def analyze_competition(term: str, results: list) -> tuple[str, str]:
    if not results:
        return "低", "无结果，竞争极低"

    term_lower = term.lower()
    weak_count = 0
    tool_count = 0
    exact_match_count = 0
    high_quality_count = 0
    quality_notes = []

    for r in results[:10]:
        url = r.get("url", "")
        title = r.get("title", "") or ""
        content = r.get("content", "") or ""

        if is_weak_domain(url):
            weak_count += 1
        if is_tool_site(url, title):
            tool_count += 1
        if term_lower in title.lower():
            exact_match_count += 1
        if len(content) > 200 and not is_weak_domain(url):
            high_quality_count += 1

    total = min(len(results), 10)

    if weak_count >= total * 0.6:
        quality_notes.append("弱，论坛/社媒为主")
    elif weak_count >= total * 0.3:
        quality_notes.append("中等，混有论坛帖")
    else:
        quality_notes.append("较强，专业站点多")

    if tool_count > 0:
        quality_notes.append(f"有{tool_count}个工具站")
    if exact_match_count >= total * 0.5:
        quality_notes.append("标题精准匹配多")

    if weak_count >= total * 0.5 and tool_count == 0:
        competition = "低"
    elif tool_count >= 3 or (high_quality_count >= 5 and exact_match_count >= 3):
        competition = "高"
    elif tool_count >= 1 or high_quality_count >= 3:
        competition = "中"
    else:
        competition = "低"

    return competition, "，".join(quality_notes)


def score_from_results(term: str, trend_results: list, comp_results: list,
                       older_trend_results: list | None = None) -> dict:
    trend = analyze_trend(term, trend_results, older_trend_results)
    main_geo = detect_geo(trend_results + (older_trend_results or []))
    competition, top10_quality = analyze_competition(term, comp_results)
    return {
        "term": term,
        "trend": trend,
        "main_geo": main_geo,
        "competition": competition,
        "top10_quality": top10_quality,
    }


def merge_and_save(scored_path: str, date: str, new_entries: list):
    scored = []
    if __import__("os").path.exists(scored_path):
        with open(scored_path) as f:
            existing = json.load(f)
            scored = existing.get("terms", existing) if isinstance(existing, dict) else existing

    existing_terms = {s["term"] for s in scored}
    for entry in new_entries:
        if entry["term"] not in existing_terms:
            scored.append(entry)
            existing_terms.add(entry["term"])

    output = {"date": date, "scored_at": datetime.now().isoformat(), "terms": scored}
    with open(scored_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return scored


if __name__ == "__main__":
    # CLI: python analyze.py <term> <trend_json_file> <comp_json_file>
    if len(sys.argv) < 4:
        print("Usage: analyze.py <term> <trend_results.json> <comp_results.json>")
        sys.exit(1)
    term = sys.argv[1]
    with open(sys.argv[2]) as f:
        trend_data = json.load(f)
    with open(sys.argv[3]) as f:
        comp_data = json.load(f)
    trend_results = trend_data if isinstance(trend_data, list) else trend_data.get("results", [])
    comp_results = comp_data if isinstance(comp_data, list) else comp_data.get("results", [])
    result = score_from_results(term, trend_results, comp_results)
    print(json.dumps(result, ensure_ascii=False))
