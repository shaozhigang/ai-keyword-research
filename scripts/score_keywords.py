#!/usr/bin/env python3
"""Score keywords using Tavily search API for trend and competition analysis."""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TAVILY_API_URL = "https://api.tavily.com/search"
SEARCH_DELAY = 5  # seconds between searches

# Domains indicating weak/low-quality results
WEAK_DOMAINS = {
    "reddit.com", "quora.com", "stackoverflow.com", "stackexchange.com",
    "medium.com", "dev.to", "hashnode.dev", "substack.com",
    "twitter.com", "x.com", "facebook.com", "linkedin.com",
    "youtube.com", "tiktok.com", "pinterest.com",
    "zhihu.com", "weibo.com", "bilibili.com", "douban.com",
    "forum", "discuss", "community",
}

# Domains indicating tool/product sites
TOOL_INDICATORS = {
    "github.com", "huggingface.co", "producthunt.com",
    "vercel.com", "firecrawl.dev", "elevenlabs.io",
    ".io", ".dev", ".app", "docs.", "api.",
}

# Country TLD mapping
TLD_GEO = {
    ".cn": "CN", ".us": "US", ".in": "IN", ".uk": "UK", ".de": "DE",
    ".jp": "JP", ".kr": "KR", ".fr": "FR", ".au": "AU", ".br": "BR",
    ".ru": "RU", ".tw": "TW", ".hk": "HK", ".sg": "SG",
}

# Chinese character detection
CN_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def tavily_search(query: str, max_results: int = 10, time_range: str | None = None,
                  start_date: str | None = None) -> dict:
    """Call Tavily search API (supports keyless mode like MCP tavily-mcp)."""
    api_key = os.environ.get("TAVILY_API_KEY", "")

    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
    }
    if api_key:
        payload["api_key"] = api_key
    if time_range:
        payload["time_range"] = time_range
    if start_date:
        payload["start_date"] = start_date

    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Client-Source"] = "MCP"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"
        headers["X-Client-Source"] = "tavily-mcp-keyless"

    last_err = None
    for attempt in range(6):
        try:
            req = Request(
                TAVILY_API_URL,
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            with urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            last_err = e
            if e.code in (429, 432, 503) and attempt < 5:
                wait = SEARCH_DELAY * (2 ** attempt)
                print(f"    API {e.code}，{wait}s 后重试 ({attempt + 1}/5)")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            last_err = e
            if attempt < 5:
                wait = SEARCH_DELAY * (2 ** attempt)
                print(f"    错误: {e}，{wait}s 后重试 ({attempt + 1}/5)")
                time.sleep(wait)
            else:
                raise
    raise last_err


def detect_geo(results: list) -> str:
    """Detect main geographic region from search results."""
    geo_counts: dict[str, int] = {"US": 0, "CN": 0, "IN": 0, "UK": 0, "OTHER": 0}

    for r in results:
        url = r.get("url", "")
        content = r.get("content", "") + r.get("title", "")

        # TLD detection
        for tld, geo in TLD_GEO.items():
            if tld in url:
                geo_counts[geo] = geo_counts.get(geo, 0) + 2
                break

        # Chinese content
        if CN_PATTERN.search(content):
            geo_counts["CN"] += 2

        # Domain-based hints
        if any(d in url for d in [".com", ".org", ".net", "github.com", "arxiv.org",
                                   "huggingface.co", "producthunt.com"]):
            geo_counts["US"] += 1

    top = max(geo_counts, key=geo_counts.get)
    return top if geo_counts[top] > 0 else "US"


def analyze_trend(term: str, recent_results: list, older_results: list) -> str:
    """Compare recent vs older search volume signals to determine trend."""
    recent_count = len(recent_results)
    older_count = len(older_results)

    # Check for recent news/announcements
    recent_signals = 0
    for r in recent_results:
        title = r.get("title", "").lower()
        content = r.get("content", "").lower()
        term_lower = term.lower()
        if term_lower in title:
            recent_signals += 2
        if any(w in content for w in ["launch", "release", "new", "announce", "trending",
                                         "发布", "上线", "推出"]):
            recent_signals += 1
        if any(w in title for w in ["2026", "2025"]):
            recent_signals += 1

    # Compare result counts and relevance
    if recent_count == 0 and older_count == 0:
        return "📊平稳"

    if recent_count > older_count * 1.5 or recent_signals >= 4:
        return "📈上升"
    if recent_count < older_count * 0.5 and recent_signals <= 1:
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
    """Analyze competition level and top10 quality."""
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
        title = r.get("title", "")
        content = r.get("content", "")

        if is_weak_domain(url):
            weak_count += 1

        if is_tool_site(url, title):
            tool_count += 1

        if term_lower in title.lower():
            exact_match_count += 1

        if len(content) > 200 and not is_weak_domain(url):
            high_quality_count += 1

    total = min(len(results), 10)

    # Build quality description
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

    # Competition level
    if weak_count >= total * 0.5 and tool_count == 0:
        competition = "低"
    elif tool_count >= 3 or (high_quality_count >= 5 and exact_match_count >= 3):
        competition = "高"
    elif tool_count >= 1 or high_quality_count >= 3:
        competition = "中"
    else:
        competition = "低"

    return competition, "，".join(quality_notes)


def score_term(term: str) -> dict:
    """Score a single keyword term."""
    print(f"  分析: {term}")

    # Trend search - recent 30 days
    recent_query = f'"{term}" news OR trending OR launch 2026'
    recent_data = tavily_search(recent_query, max_results=10, time_range="month")
    recent_results = recent_data.get("results", [])
    time.sleep(SEARCH_DELAY)

    trend = analyze_trend(term, recent_results, [])
    main_geo = detect_geo(recent_results)

    # Competition search
    comp_query = term
    comp_data = tavily_search(comp_query, max_results=10)
    comp_results = comp_data.get("results", [])
    time.sleep(SEARCH_DELAY)

    competition, top10_quality = analyze_competition(term, comp_results)

    return {
        "term": term,
        "trend": trend,
        "main_geo": main_geo,
        "competition": competition,
        "top10_quality": top10_quality,
    }


def main():
    raw_path = "/workspace/keywords/daily_raw.json"
    scored_path = "/workspace/keywords/daily_scored.json"

    with open(raw_path) as f:
        raw = json.load(f)

    terms = raw.get("new_terms", [])
    date = raw.get("date", datetime.now().strftime("%Y-%m-%d"))

    # Load existing progress
    scored = []
    done_terms = set()
    if os.path.exists(scored_path):
        with open(scored_path) as f:
            existing = json.load(f)
            if isinstance(existing, dict) and "terms" in existing:
                scored = existing["terms"]
            elif isinstance(existing, list):
                scored = existing
            done_terms = {s["term"] for s in scored}

    remaining = [t for t in terms if t not in done_terms]
    print(f"日期: {date}, 总词数: {len(terms)}, 已完成: {len(done_terms)}, 待处理: {len(remaining)}")

    for i, term in enumerate(remaining):
        print(f"[{len(done_terms) + i + 1}/{len(terms)}]", end=" ")
        try:
            result = score_term(term)
            scored.append(result)
            print(f"  → {result['trend']} | {result['main_geo']} | {result['competition']}")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            scored.append({
                "term": term,
                "trend": "📊平稳",
                "main_geo": "US",
                "competition": "中",
                "top10_quality": f"分析失败: {e}",
            })

        # Save progress after each term
        output = {"date": date, "scored_at": datetime.now().isoformat(), "terms": scored}
        with open(scored_path, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 共评分 {len(scored)} 个词，结果已写入 {scored_path}")


if __name__ == "__main__":
    main()
