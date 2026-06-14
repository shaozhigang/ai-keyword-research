#!/usr/bin/env python3
"""Extract user pain signals from Tavily search results and summarize in Chinese."""

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
        r"unpredictable",
        r"crash(?:es|ed|ing)?",
        r"fail(?:s|ed|ure)?",
        r"pain(?:ful)?",
        r"difficult to",
        r"hard to use",
        r"steep learning curve",
        r"poor (?:quality|performance|support)",
        r"limited\b",
        r"restrict",
        r"hostage",
        r"stuck\b",
        r"hallucinat",
        r"maintenance",
        r"technical debt",
        r"vulnerabilit",
        r"scalability",
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
        r"instead (?:I|we|you|they) (?:use|built|write|script|deploy|switch)",
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
        r"drag.?and.?drop",
        r"jerry.?rig",
        r"duct tape",
        r"fallback",
        r"self.?host",
        r"migrat",
        r"switch(?:ed|ing)? to",
        r"use (?:fly\.io|coolify|docker|netlify)",
        r"临时方案",
        r"手动处理",
        r"自己写",
        r"绕路",
        r"替代方案",
        r"用.*代替",
        r"excel",
        r"downloaded? all",
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
        r"wish list",
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

NOISE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"base64",
        r"Skip to main content",
        r"Open menu",
        r"Open navigation",
        r"Sign Up",
        r"Log In",
        r"Reply\s+Share",
        r"Image \d+",
        r"u/[\w-]+ avatar",
        r"javascript:void",
        r"Sort by:",
        r"Promoted",
        r"Thumbnail image",
        r"^#+ ",
        r"^\| ",
        r"^:\s*r/",
        r"^More replies",
        r"^Public$",
        r"^Best$",
        r"^FeedAbout",
    ]
]

THEME_SUMMARIES = [
    (r"too expensive|pricing|cost|charge|bandwidth.*price", "定价过高，流量上来后成本飙升"),
    (r"unreliable|unpredictable|hallucinat", "输出不稳定，结果不可预测"),
    (r"frustrat|annoying|hate|awful|terrible", "使用体验差，令人沮丧"),
    (r"maintenance|technical debt|maintain", "难以维护，技术债快速累积"),
    (r"security vulner|owasp", "生成代码存在安全漏洞"),
    (r"doesn'?t support|no support|lack(?:s|ing)?|missing|limited", "缺少关键功能或支持"),
    (r"too slow|slow|latency|performance", "性能慢，响应延迟高"),
    (r"steep learning curve|hard to use|difficult", "学习曲线陡峭，上手困难"),
    (r"bug|broken|crash|fail|not working|doesn'?t work", "频繁出 bug，功能不稳定"),
    (r"scalability|scale|retention", "扩展性差，大规模部署受限"),
    (r"hostage|stuck|trap", "平台锁定，迁移困难"),
    (r"deploy|deployment", "部署流程复杂，上线容易踩坑"),
    (r"debug|back.?and.?forth|loop", "调试循环冗长，反复返工"),
    (r"control|prompt|context", "难以控制输出，依赖精细 prompt"),
    (r"edge case", "边界情况处理差，反复返工调试"),
    (r"alternative|vs\b|competitor", "用户主动寻找替代方案"),
    (r"太贵", "定价过高"),
    (r"不支持", "不支持所需功能或语言"),
    (r"太慢", "运行速度太慢"),
    (r"不好用", "整体不好用"),
]

WORKAROUND_SUMMARIES = [
    (r"excel|spreadsheet|google sheets", "用户用 Excel/表格手动处理"),
    (r"self.?host|docker|fly\.io|coolify|caprover", "转向自托管或其他部署平台"),
    (r"drag.?and.?drop|migrat|download", "批量下载后拖拽迁移部署"),
    (r"manually|by hand", "手动逐步处理"),
    (r"custom script|build.*own|roll.*own", "自己写脚本或自建工具"),
    (r"switch(?:ed|ing)? to|instead.*use", "改用其他工具/平台"),
    (r"copy.?paste|export.*import", "导出再导入的复制粘贴流程"),
    (r"hack|workaround|jerry|duct tape", "用临时 hack 绕过限制"),
]

DESIRE_SUMMARIES = [
    (r"\bi wish\b|wish list|would be (?:nice|great|better)", "希望增加更完善的功能"),
    (r"\bwhy can'?t\b", "质疑为何不支持某能力"),
    (r"should (?:have|support|add|include)|feature request", "期望官方支持更多功能"),
    (r"batch|bulk|api", "需要批量处理或 API 接入"),
    (r"automatic|inherit|simplif", "希望自动化简化工作流"),
    (r"better tool|looking for", "在寻找更好的工具方案"),
    (r"中文|chinese|i18n|localiz", "需要中文或多语言支持"),
    (r"export|format", "需要更多导出格式"),
]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")
ACADEMIC_DOMAINS = ("arxiv.org", "huggingface.co", "github.com", "papers", "semanticscholar", "aclanthology", "pubmed", "nature.com", "ncbi.nlm.nih.gov")


def _is_noise(text: str) -> bool:
    if len(text) < 25:
        return True
    if any(p.search(text) for p in NOISE_PATTERNS):
        return True
    if text.count("...") > 2:
        return True
  # base64 blobs
    if len(text) > 200 and re.search(r"[A-Za-z0-9+/]{80,}", text):
        return True
    return False


def _clean_snippet(text: str, max_len: int = 100) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"Image \d+", "", text)
    text = re.sub(r"!\(data:image[^)]+\)", "", text)
    text = re.sub(r"^#+\s*", "", text)
    if len(text) > max_len:
        text = text[: max_len - 3].rsplit(" ", 1)[0] + "..."
    return text.strip()


def _extract_sentences(content: str) -> list[str]:
    sentences = []
    for part in SENTENCE_SPLIT.split(content):
        part = part.strip()
        if not _is_noise(part):
            sentences.append(part)
    return sentences


def _match_category(sentence: str, patterns: list) -> bool:
    return any(p.search(sentence) for p in patterns)


def _english_ratio(text: str) -> float:
    letters = sum(1 for c in text if c.isascii() and c.isalpha())
    return letters / max(len(text), 1)


def _theme_summary(sentence: str, themes: list[tuple[str, str]], fallback_prefix: str) -> str | None:
    for pattern, summary in themes:
        if re.search(pattern, sentence, re.I):
            return summary
    cleaned = _clean_snippet(sentence, 60)
    if re.search(r"[\u4e00-\u9fff]{2,}", cleaned):
        return cleaned
    if _english_ratio(cleaned) > 0.55:
        return None
    return f"{fallback_prefix}：{cleaned}" if len(cleaned) > 15 else None


def _summarize_to_chinese(snippets: list[str], themes: list, fallback_prefix: str, limit: int = 3) -> list[str]:
    if not snippets:
        return []

    summaries = []
    for s in snippets:
        summary = _theme_summary(s, themes, fallback_prefix)
        if summary and len(summary) >= 4:
            summaries.append(summary)

    counter = Counter(summaries)
    ranked = sorted(counter.items(), key=lambda x: (-x[1], -len(x[0])))
    result = []
    seen = set()
    for summary, _ in ranked:
        if summary.startswith("用户反馈：") and _english_ratio(summary) > 0.4:
            continue
        if summary.startswith("用户期望：") and _english_ratio(summary) > 0.4:
            continue
        norm = re.sub(r"[^\w\u4e00-\u9fff]", "", summary.lower())
        if norm in seen or len(norm) < 4:
            continue
        seen.add(norm)
        result.append(summary)
        if len(result) >= limit:
            break
    return result


def _term_relevant(sentence: str, term: str) -> bool:
    sent_lower = sentence.lower()
    term_lower = term.lower()
    if term_lower in sent_lower:
        return True
    words = [w for w in re.split(r"[\s.\-]+", term_lower) if len(w) > 3]
    if not words:
        words = [w for w in term_lower.split() if len(w) > 2]
    if words and any(w in sent_lower for w in words):
        return True
    # For product searches, also match related brand words
    brand_aliases = {
        "vercel drop": ["vercel", "replit", "deploy", "drag"],
        "prometheus by firecrawl": ["firecrawl", "prometheus", "scrape", "crawl"],
        "vibe coding": ["vibe", "vibecod", "ai cod", "llm", "prompt"],
        "sparse attention": ["sparse", "attention", "long context"],
        "agentic rl": ["agent", "reinforcement", "rl"],
        "computer-use agents": ["computer", "agent", "browser", "gui"],
        "world model": ["world model", "simulation"],
        "test-time scaling": ["test-time", "scaling", "inference"],
        "multi-agent": ["multi-agent", "orchestrat"],
        "forward deployed agent": ["forward deploy", "agent", "fde"],
    }
    for key, aliases in brand_aliases.items():
        if key in term_lower:
            return any(a in sent_lower for a in aliases)
    return len(term) <= 5


def _is_academic_heavy(results: list) -> bool:
    if not results:
        return False
    academic = sum(
        1 for r in results
        if any(d in (r.get("url", "") or "") for d in ACADEMIC_DOMAINS)
    )
    return academic >= len(results) * 0.5


def _is_research_term(search_batches: dict[str, list]) -> bool:
    """Research papers often pollute reddit results; check core batches only."""
    core = (search_batches.get("complaints") or []) + (search_batches.get("alternative") or [])
    if not core:
        return False
    academic = sum(
        1 for r in core
        if any(d in (r.get("url", "") or "") for d in ACADEMIC_DOMAINS)
    )
    return academic >= len(core) * 0.6


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
            tl = title.lower()
            if "alternative" in tl or "vs" in tl or "competitor" in tl:
                complaints_raw.append(f"Users seeking alternatives to {term}: {title}")

    if not complaints_raw and search_batches.get("complaints"):
        for r in search_batches["complaints"][:3]:
            content = r.get("content", "") or r.get("title", "")
            if content and not _is_noise(content):
                for sentence in _extract_sentences(content):
                    if _match_category(sentence, COMPLAINT_PATTERNS):
                        complaints_raw.append(sentence)

    if not complaints_raw and not workarounds_raw and not desired_raw:
        if _is_academic_heavy(all_results) or _is_research_term(search_batches):
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

    complaints = _summarize_to_chinese(complaints_raw, THEME_SUMMARIES, "用户反馈", 3)
    workarounds = _summarize_to_chinese(workarounds_raw, WORKAROUND_SUMMARIES, "用户绕路方案", 3)
    desired = _summarize_to_chinese(desired_raw, DESIRE_SUMMARIES, "用户期望", 3)

    if _is_academic_heavy(all_results) or _is_research_term(search_batches):
        return {
            "term": term,
            "top_complaints": ["暂无明确用户抱怨，主要为学术/技术发布内容"],
            "workarounds": [],
            "desired_features": [],
        }

    if not complaints:
        complaints = ["搜索结果中未发现明确用户痛点"]

    return {
        "term": term,
        "top_complaints": complaints,
        "workarounds": workarounds,
        "desired_features": desired,
    }
