#!/usr/bin/env python3
"""Extract user pain signals from Tavily search results."""

import re
from collections import Counter

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
        r"over.?priced",
        r"hostage",
        r"stuck",
        r"hallucinat",
        r"unpredictable",
        r"maintenance",
        r"technical debt",
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
        r"self.?host",
        r"migrat",
        r"drag.?and.?drop",
        r"switch(?:ed|ing)? to",
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
        r"wish list",
        r"希望能",
        r"希望有",
        r"为什么没有",
        r"能不能",
        r"要是能",
        r"需要.*功能",
    ]
]

# Map English pain themes to concise Chinese one-liners
COMPLAINT_THEMES = [
    (r"too expensive|over.?priced|pricing|cost.*high|charge", "定价过高，规模化后成本难以承受"),
    (r"doesn'?t support|no support|lack.*support|not support", "缺少关键功能或语言支持"),
    (r"too slow|slow|latency|performance", "运行速度慢或性能不足"),
    (r"broken|doesn'?t work|not working|won'?t work|crash", "功能不稳定或经常崩溃"),
    (r"bug|issue|problem|fail", "存在明显缺陷或可靠性问题"),
    (r"frustrat|annoying|hate|terrible|awful|disappoint", "使用体验差，用户普遍感到沮丧"),
    (r"hallucinat|unpredictable|unreliable", "输出不可预测，结果不可靠"),
    (r"steep learning|hard to use|difficult", "学习曲线陡峭，上手门槛高"),
    (r"missing|lack|limited|restrict", "功能受限或缺少必要能力"),
    (r"maintenance|technical debt|maintain", "长期维护成本高，不适合生产环境"),
    (r"hostage|stuck|lock.?in", "平台锁定，迁移困难"),
    (r"security|vulnerabilit|compliance|hipaa", "安全合规风险令人担忧"),
    (r"alternative|competitor|vs\b", "用户主动寻找替代方案，说明现有方案不满意"),
    (r"export|import|format", "导入导出格式受限"),
    (r"chinese|中文|language|i18n|localiz", "不支持中文或本地化不足"),
]

WORKAROUND_THEMES = [
    (r"excel|spreadsheet|google sheets", "用户用 Excel/表格手动处理"),
    (r"manually|by hand|copy.?paste", "用户手动复制粘贴完成操作"),
    (r"custom script|build.*own|roll.*own|diy|hack", "用户自己写脚本或搭建替代方案"),
    (r"self.?host|docker|fly\.io|coolify|caprover", "用户选择自托管或换用其他部署平台"),
    (r"migrat|switch|move.*to|drag.?and.?drop", "用户迁移到其他工具或平台"),
    (r"workaround|fallback|instead", "用户采用临时绕路方案凑合使用"),
    (r"export.*import", "用户通过导出再导入的方式绕过限制"),
]

DESIRE_THEMES = [
    (r"\bi wish\b|\bwhy can'?t\b|if only", "用户希望产品具备目前缺失的能力"),
    (r"batch|bulk|api|webhook|integrat", "用户需要批量处理或 API 接入能力"),
    (r"support|add|include|feature", "用户希望增加特定功能支持"),
    (r"automatic|auto\b|inherit|link", "用户希望自动化减少手动配置步骤"),
    (r"chinese|中文|localiz|i18n", "用户希望支持中文或本地化"),
    (r"cheaper|affordable|pricing", "用户希望降低价格或提供更灵活计费"),
    (r"faster|speed|performance|parallel", "用户希望提升速度或并行处理能力"),
    (r"document|tutorial|intuitive|understand", "用户希望有更清晰的学习资源或文档"),
    (r"maintenance|maintain|long.?term", "用户希望产品能长期稳定维护"),
]

REDDIT_NOISE = re.compile(
    r"(Skip to main content|Open menu|Sign Up|Log In|Reply\s+Share|"
    r"Image \d+|u/[\w-]+\s+avatar|Sort by:|Best\s+Top\s+New|"
    r"!\(data:image|More replies|Comment deleted)",
    re.I,
)
BASE64_NOISE = re.compile(r"!\(data:image[^)]+\)|[A-Za-z0-9+/]{80,}={0,2}")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def _clean_content(text: str) -> str:
    text = BASE64_NOISE.sub("", text)
    text = REDDIT_NOISE.sub(" ", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_snippet(text: str, max_len: int = 100) -> str:
    text = _clean_content(text)
    if len(text) > max_len:
        text = text[: max_len - 3].rsplit(" ", 1)[0] + "..."
    return text


def _extract_sentences(content: str) -> list[str]:
    content = _clean_content(content)
    sentences = []
    for part in SENTENCE_SPLIT.split(content):
        part = part.strip()
        if len(part) > 25 and not part.startswith("r/"):
            sentences.append(part)
    return sentences


def _match_category(sentence: str, patterns: list) -> bool:
    return any(p.search(sentence) for p in patterns)


def _term_relevant(sentence: str, term: str) -> bool:
    sent_lower = sentence.lower()
    term_lower = term.lower()
    if term_lower in sent_lower:
        return True
    words = [w for w in re.split(r"[\s.\-/]+", term_lower) if len(w) > 3]
    if not words:
        return True
    return any(w in sent_lower for w in words)


def _theme_summarize(snippets: list[str], themes: list[tuple], fallback_fn) -> list[str]:
    """Map raw snippets to concise Chinese theme summaries."""
    if not snippets:
        return []

    theme_hits: Counter = Counter()
    for snippet in snippets:
        for pattern, label in themes:
            if re.search(pattern, snippet, re.I):
                theme_hits[label] += 1

    if theme_hits:
        ranked = [label for label, _ in theme_hits.most_common(3)]
        return ranked

    return fallback_fn(snippets)


def _fallback_complaints(snippets: list[str], limit: int = 3) -> list[str]:
    result = []
    seen = set()
    for s in snippets:
        cleaned = _clean_snippet(s, 60)
        norm = re.sub(r"[^\w\u4e00-\u9fff]", "", cleaned.lower())
        if len(norm) < 12 or norm in seen:
            continue
        seen.add(norm)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _fallback_short(snippets: list[str], limit: int = 3) -> list[str]:
    return _fallback_complaints(snippets, limit)


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

    for r in all_results:
        title = r.get("title", "") or ""
        content = r.get("content", "") or ""
        full_text = f"{title}. {content}"

        for sentence in _extract_sentences(full_text):
            if not _term_relevant(sentence, term):
                continue
            if _match_category(sentence, COMPLAINT_PATTERNS):
                complaints_raw.append(sentence)
            if _match_category(sentence, WORKAROUND_PATTERNS):
                workarounds_raw.append(sentence)
            if _match_category(sentence, DESIRE_PATTERNS):
                desired_raw.append(sentence)

    if not complaints_raw and search_batches.get("alternative"):
        for r in search_batches["alternative"][:5]:
            title = r.get("title", "") or ""
            if re.search(r"alternative|vs|competitor|替代", title, re.I):
                complaints_raw.append(title)

    if not complaints_raw and search_batches.get("complaints"):
        for r in search_batches["complaints"][:3]:
            content = r.get("content", "") or r.get("title", "")
            if content and _term_relevant(content, term):
                complaints_raw.append(content)

    if not complaints_raw and not workarounds_raw and not desired_raw:
        academic_signals = sum(
            1
            for r in all_results
            if any(
                d in (r.get("url", "") or "")
                for d in ["arxiv.org", "huggingface.co/papers", "github.com", "papers."]
            )
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
        "top_complaints": _theme_summarize(
            complaints_raw, COMPLAINT_THEMES, _fallback_complaints
        ),
        "workarounds": _theme_summarize(
            workarounds_raw, WORKAROUND_THEMES, _fallback_short
        ),
        "desired_features": _theme_summarize(
            desired_raw, DESIRE_THEMES, _fallback_short
        ),
    }
