#!/usr/bin/env python3
"""Extract user pain signals from Tavily search results."""

import re
from collections import Counter

# Pain / complaint signals
COMPLAINT_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\bcomplain",
        r"\bfrustrat",
        r"\bbroken\b",
        r"\bbug(?:s|gy)?\b",
        r"\bissue(?:s)?\b",
        r"\bproblem(?:s)?\b",
        r"doesn'?t work",
        r"won'?t work",
        r"not working",
        r"too expensive",
        r"too slow",
        r"lack(?:s|ing)?\b",
        r"missing\b",
        r"no support",
        r"doesn'?t support",
        r"can'?t\b",
        r"unable to",
        r"terrible",
        r"awful",
        r"annoying",
        r"hate (?:it|this|that)",
        r"disappoint",
        r"unreliable",
        r"crash(?:es|ed|ing)?",
        r"fail(?:s|ed|ure)?",
        r"pain(?:ful)?",
        r"difficult to",
        r"hard to use",
        r"steep learning curve",
        r"poor (?:quality|performance|support)",
        r"limited\b",
        r"restrict",
        r"太贵",
        r"不支持",
        r"太慢",
        r"太难",
        r"不好用",
        r"崩溃",
        r"失败",
        r"缺少",
        r"没有.*功能",
        r"问题",
        r"抱怨",
        r"失望",
    ]
]

WORKAROUND_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"workaround",
        r"work around",
        r"instead (?:I|we|you) (?:use|built|write|script)",
        r"manually\b",
        r"by hand",
        r"hack(?:ed|ing)?",
        r"diy\b",
        r"build (?:my|our|a) own",
        r"roll (?:my|our) own",
        r"custom script",
        r"use (?:excel|spreadsheet|google sheets)",
        r"export.*import",
        r"copy.?paste",
        r"jerry.?rig",
        r"duct tape",
        r"fallback",
        r"临时方案",
        r"手动处理",
        r"自己写",
        r"绕路",
        r"替代方案",
        r"用.*代替",
        r"excel",
    ]
]

DESIRE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\bi wish\b",
        r"\bwhy can'?t\b",
        r"would be (?:nice|great|better|helpful)",
        r"if only\b",
        r"need(?:s)? (?:a |an |to )",
        r"looking for\b",
        r"hope (?:they|it|someone)",
        r"should (?:have|support|add|include)",
        r"feature request",
        r"anyone know (?:a|an|if)",
        r"is there (?:a|an) (?:tool|way|app)",
        r"wish (?:it|they|there)",
        r"want (?:it|them) to (?:add|support|fix)",
        r"missing feature",
        r"希望能",
        r"希望有",
        r"为什么没有",
        r"能不能",
        r"要是能",
        r"需要.*功能",
    ]
]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def _clean_snippet(text: str, max_len: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"Image \d+", "", text)
    if len(text) > max_len:
        text = text[: max_len - 3].rsplit(" ", 1)[0] + "..."
    return text


def _extract_sentences(content: str) -> list[str]:
    sentences = []
    for part in SENTENCE_SPLIT.split(content):
        part = part.strip()
        if len(part) > 20:
            sentences.append(part)
    return sentences


def _match_category(sentence: str, patterns: list) -> bool:
    return any(p.search(sentence) for p in patterns)


def _summarize_snippets(snippets: list[str], limit: int = 3) -> list[str]:
    """Deduplicate and pick top snippets by frequency of key terms."""
    if not snippets:
        return []

    cleaned = [_clean_snippet(s) for s in snippets]
    counter = Counter(cleaned)
    ranked = sorted(counter.items(), key=lambda x: (-x[1], -len(x[0])))
    result = []
    seen_norm = set()
    for snippet, _ in ranked:
        norm = re.sub(r"[^\w\u4e00-\u9fff]", "", snippet.lower())
        if norm in seen_norm or len(norm) < 10:
            continue
        seen_norm.add(norm)
        result.append(snippet)
        if len(result) >= limit:
            break
    return result


def extract_pain_from_results(term: str, search_batches: dict[str, list]) -> dict:
    """
    search_batches: {"reddit": [...], "complaints": [...], "alternative": [...], "producthunt": [...]}
    Each item is a Tavily result dict with title, content, url.
    """
    all_results = []
    for results in search_batches.values():
        all_results.extend(results)

    complaints_raw: list[str] = []
    workarounds_raw: list[str] = []
    desired_raw: list[str] = []

    term_lower = term.lower()

    for r in all_results:
        title = r.get("title", "") or ""
        content = r.get("content", "") or ""
        full_text = f"{title}. {content}"

        for sentence in _extract_sentences(full_text):
            sent_lower = sentence.lower()
            if term_lower not in sent_lower and len(term) > 5:
                # For multi-word terms, require at least one significant word
                words = [w for w in term_lower.split() if len(w) > 3]
                if words and not any(w in sent_lower for w in words):
                    continue

            if _match_category(sentence, COMPLAINT_PATTERNS):
                complaints_raw.append(sentence)
            if _match_category(sentence, WORKAROUND_PATTERNS):
                workarounds_raw.append(sentence)
            if _match_category(sentence, DESIRE_PATTERNS):
                desired_raw.append(sentence)

    # Fallback: extract from alternative/producthunt searches when no explicit complaints
    if not complaints_raw and search_batches.get("alternative"):
        for r in search_batches["alternative"][:5]:
            title = r.get("title", "") or ""
            if "alternative" in title.lower() or "vs" in title.lower():
                complaints_raw.append(f"用户在寻找 {term} 的替代方案：{_clean_snippet(title)}")

    if not complaints_raw and search_batches.get("complaints"):
        for r in search_batches["complaints"][:3]:
            content = r.get("content", "") or r.get("title", "")
            if content:
                complaints_raw.append(_clean_snippet(content))

    # Research/academic terms often have no user complaints
    if not complaints_raw and not workarounds_raw and not desired_raw:
        # Check if results are mostly academic
        academic_signals = sum(
            1 for r in all_results
            if any(d in (r.get("url", "") or "") for d in ["arxiv.org", "huggingface.co", "github.com", "papers"])
        )
        if academic_signals >= len(all_results) * 0.5 and all_results:
            return {
                "term": term,
                "top_complaints": ["暂无明确用户抱怨，主要为学术/技术发布内容"],
                "workarounds": [],
                "desired_features": [],
            }
        return {
            "term": term,
            "top_complaints": ["搜索结果中未发现明确用户痛点"],
            "workarounds": [],
            "desired_features": [],
        }

    return {
        "term": term,
        "top_complaints": _summarize_snippets(complaints_raw, 3),
        "workarounds": _summarize_snippets(workarounds_raw, 3),
        "desired_features": _summarize_snippets(desired_raw, 3),
    }
