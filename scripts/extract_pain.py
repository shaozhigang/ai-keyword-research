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

NOISE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"skip to main content",
        r"^r/\w+",
        r"^#+ ",
        r"data:image/",
        r"!\[",
        r"^\| ",
        r"^u/\w+ avatar",
        r"more replies",
        r"^People also ask",
        r"^Open menu",
        r"^Created \w+ \d+",
        r"^Public$",
        r"^Anyone can view",
        r"^## r/\w+ Rules",
        r"^Reply\s+Share",
        r"^Promoted",
        r"^BibTeX",
        r"^@article",
    ]
]

CN_THEME_MAP = [
    (re.compile(p, re.I), cn)
    for p, cn in [
        (r"too expensive|pricing|cost(?:ly)?|expensive", "价格太贵"),
        (r"doesn'?t support|no support|not support|lack(?:s|ing)?.*support", "不支持所需功能或语言"),
        (r"too slow|slow(?:ly)?|latency|performance", "运行太慢、性能不足"),
        (r"unreliable|unpredictable|inconsistent|hallucin", "输出不稳定、不可靠"),
        (r"broken|doesn'?t work|not working|won'?t work|silently broken", "功能损坏或无法正常工作"),
        (r"bug|crash|fail(?:ure|ed|s)?", "存在 bug 或频繁崩溃"),
        (r"frustrat|annoying|terrible|awful|disappoint", "使用体验差、令人沮丧"),
        (r"difficult|hard to use|steep learning|complex", "上手难、学习曲线陡峭"),
        (r"maintenance|technical debt|maintain", "难以维护、技术债高"),
        (r"security|vulnerabilit", "存在安全漏洞"),
        (r"limited|restrict|missing feature|lack(?:s|ing)?", "功能受限或缺失"),
        (r"export|import|format", "导入导出格式不足"),
        (r"alternative|competitor|vs\b", "用户积极寻找替代方案"),
        (r"manually|by hand|workaround|excel|spreadsheet", "需手动处理或借助变通方案"),
        (r"i wish|why can'?t|would be (?:nice|great|better)", "用户期望更多功能"),
        (r"looking for|need(?:s)? (?:a |an |to )", "用户在寻找更好方案"),
        (r"no (?:login|ads)|privacy", "关注隐私或无广告体验"),
    ]
]


def _is_noise(text: str) -> bool:
    t = text.strip()
    if len(t) < 15:
        return True
    if "base64" in t or len(t) > 500 and "iVBOR" in t:
        return True
    return any(p.search(t) for p in NOISE_PATTERNS)


def _clean_snippet(text: str, max_len: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"Image \d+", "", text)
    text = re.sub(r"!\([^)]*\)", "", text)
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^Skip to main content", "", text, flags=re.I)
    if len(text) > max_len:
        text = text[: max_len - 3].rsplit(" ", 1)[0] + "..."
    return text.strip()


def _to_cn_summary(sentence: str, category: str = "complaint") -> str:
    """将英文痛点句归纳为简短中文描述。"""
    if sentence.startswith("用户在寻找"):
        return _clean_snippet(sentence, 60)
    if _is_noise(sentence):
        return ""

    cleaned = _clean_snippet(sentence, 180)
    chinese = re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fff，。！？、：；""''（）\w\s]{4,}", cleaned)
    if chinese:
        best = max(chinese, key=len)
        return _clean_snippet(best, 60)

    for pattern, label in CN_THEME_MAP:
        if pattern.search(cleaned):
            return label

    if category == "workaround":
        if re.search(r"manually|excel|spreadsheet|by hand|workaround|hack", cleaned, re.I):
            return "用户用 Excel/手动流程等变通方案"
        return _clean_snippet(cleaned, 50)
    if category == "desire":
        return _clean_snippet(cleaned, 50)
    return _clean_snippet(cleaned, 50)


def _extract_sentences(content: str) -> list[str]:
    sentences = []
    for part in SENTENCE_SPLIT.split(content):
        part = part.strip()
        if len(part) > 20:
            sentences.append(part)
    return sentences


def _match_category(sentence: str, patterns: list) -> bool:
    return any(p.search(sentence) for p in patterns)


def _summarize_snippets(snippets: list[str], limit: int = 3, category: str = "complaint") -> list[str]:
    """去重并归纳为简短中文痛点描述。"""
    if not snippets:
        return []

    summarized = []
    for s in snippets:
        cn = _to_cn_summary(s, category)
        if cn and len(cn) >= 6:
            summarized.append(cn)

    counter = Counter(summarized)
    ranked = sorted(counter.items(), key=lambda x: (-x[1], -len(x[0])))
    result = []
    seen_norm = set()
    for snippet, _ in ranked:
        norm = re.sub(r"[^\w\u4e00-\u9fff]", "", snippet.lower())
        if norm in seen_norm or len(norm) < 4:
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
            if _is_noise(sentence):
                continue
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
        "top_complaints": _summarize_snippets(complaints_raw, 3, "complaint"),
        "workarounds": _summarize_snippets(workarounds_raw, 3, "workaround"),
        "desired_features": _summarize_snippets(desired_raw, 3, "desire"),
    }
