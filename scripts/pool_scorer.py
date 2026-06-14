#!/usr/bin/env python3
"""Final 6-dimension keyword scoring and pool assignment."""

import json
import re
from datetime import datetime
from pathlib import Path

RAW_PATH = Path("/workspace/keywords/daily_raw.json")
SCORED_PATH = Path("/workspace/keywords/daily_scored.json")
PAIN_PATH = Path("/workspace/keywords/daily_pain.json")
VALIDATED_PATH = Path("/workspace/keywords/pool_validated.json")
WATCH_PATH = Path("/workspace/keywords/pool_watch.json")

TREND_SCORES = {"📈上升": 5, "📊平稳": 3, "📉下降": 1}
COMP_SCORES = {"低": 5, "中": 3, "高": 1}

NOISE_PATTERNS = [
    "用户在寻找",
    "替代方案",
    "Alternatives to",
    "alternative to",
    "data:image",
    "Skip to main content",
    "arXiv preprint",
]

PAIN_WORDS = [
    "problem", "issue", "frustrat", "broken", "fail", "can't", "cannot",
    "disappoint", "lack", "missing", "error", "crash", "limitation",
    "constraint", "struggle", "difficult", "expensive", "slow", "stuck",
    "complaint", "fixing", "without", "hard to", "tricky", "gap", "pain",
    "问题", "抱怨", "太贵", "不支持", "差", "麻烦", "难", "痛点",
]

# ProductHunt / commercial product terms
PRODUCT_TERMS = {
    "Vercel Drop", "Kimi K2.7 Code", "Prometheus by Firecrawl", "CakewordAI",
    "NomNak", "Avatars in ElevenCreative", "Qursor", "Firma.dev", "Pond",
    "forward deployed agent", "vibe coding",
}

# Pure research / academic — low tool viability
RESEARCH_TERMS = {
    "MiniMax Sparse Attention", "HYDRA-X", "Robust-U1", "InterleaveThinker",
    "Mental-R1", "EvoArena", "WeaveBench", "SpatialClaw", "MaxProof",
    "FORT-Searcher", "LabVLA", "N-GRPO", "EurekAgent", "VideoMDM", "VIA-SD",
    "MoVerse", "TreeSeeker", "HarnessBridge", "EvoBrowseComp", "MaskAlign",
    "Evoflux", "ArogyaSutra", "WEAVER", "Surflo", "WebChallenger", "Flash-GMM",
    "IDEAL", "ToolSense", "PianoKontext", "Agents-K1", "AgentBeats", "EpiBench",
    "ARMOR-MAD", "TerraBench", "ReSum", "IterCAD", "EEVEE", "TRACE", "AuRA",
    "Flow-DPPO", "CITRAS-FM", "K-Forcing", "COGENT",
    "agentic RL", "sparse attention", "world model", "test-time scaling", "VLA",
    "flow matching", "GRPO", "speculative decoding",
}

# Dev-tool / benchmark / niche SaaS candidates
TOOL_TERMS = {
    "computer-use agents", "multi-agent orchestration",
}

PRODUCT_BRIEFS = {
    "NomNak": {
        "product_direction": "面向内容创作者的轻量命名与品牌词生成工具，解决产品取名难、域名冲突多的痛点",
        "suggested_headline": "Name Your Product in Seconds — No More Domain Drama",
        "target_users": ["独立开发者", "早期创业团队", "品牌策划自由职业者"],
    },
    "Firma.dev": {
        "product_direction": "面向SaaS团队的嵌入式电子签名API，替代笨重的传统签章方案",
        "suggested_headline": "Drop-In E-Signatures Built for SaaS Teams",
        "target_users": ["SaaS产品经理", "B2B平台开发者", "合规运营负责人"],
    },
    "Pond": {
        "product_direction": "面向远程团队的轻量协作看板，聚焦小团队任务流转而非重型项目管理",
        "suggested_headline": "Project Management That Stays Out of Your Way",
        "target_users": ["10人以下创业团队", "自由职业者协作小组", "非技术项目经理"],
    },
    "Vercel Drop": {
        "product_direction": "面向前端团队的即时预览分享工具，解决代码审查看不到视觉差异的痛点",
        "suggested_headline": "Share Live Previews Before You Merge",
        "target_users": ["前端工程师", "设计开发协作团队", "开源项目维护者"],
    },
    "Prometheus by Firecrawl": {
        "product_direction": "面向AI应用开发者的网页抓取+监控一体化SaaS，替代自建爬虫基础设施",
        "suggested_headline": "Web Data for AI Apps — Monitored, Scaled, Ready",
        "target_users": ["AI应用开发者", "数据工程团队", "需要网页数据的产品团队"],
    },
    "CakewordAI": {
        "product_direction": "面向烘焙爱好者的AI配方生成与步骤指导工具",
        "suggested_headline": "Bake Anything With AI-Guided Recipes",
        "target_users": ["家庭烘焙爱好者", "小型烘焙工作室", "美食内容创作者"],
    },
    "Qursor": {
        "product_direction": "面向开发者的AI代码编辑器替代品，聚焦特定语言栈的深度优化",
        "suggested_headline": "The AI Code Editor That Actually Gets Your Stack",
        "target_users": ["全栈独立开发者", "小团队技术负责人", "AI编程早期采用者"],
    },
    "Avatars in ElevenCreative": {
        "product_direction": "面向营销团队的AI数字人视频生成工具，降低真人拍摄成本",
        "suggested_headline": "Create Talking-Head Videos Without a Camera",
        "target_users": ["营销内容团队", "电商卖家", "在线教育创作者"],
    },
    "Kimi K2.7 Code": {
        "product_direction": "面向开发者的AI代码生成API封装层，专注Triton内核级优化场景",
        "suggested_headline": "Ship Production-Grade AI Code, Not Library Wrappers",
        "target_users": ["ML工程师", "GPU内核开发者", "AI基础设施团队"],
    },
    "forward deployed agent": {
        "product_direction": "面向AI创业公司的FDE工作流平台，将客户现场痛点快速转化为产品能力",
        "suggested_headline": "Turn Customer Pain Into Product Features — Fast",
        "target_users": ["AI创业公司创始人", "Forward Deployed Engineer", "企业AI解决方案架构师"],
    },
    "vibe coding": {
        "product_direction": "面向非技术创始人的结构化AI编程引导工具，解决vibe coding产出不可维护代码的痛点",
        "suggested_headline": "Build Apps With AI — Without the Technical Debt",
        "target_users": ["非技术创业者", "产品经理原型验证", "独立创客"],
    },
    "computer-use agents": {
        "product_direction": "面向运营团队的浏览器自动化Agent平台，解决CAPTCHA和页面导航失败问题",
        "suggested_headline": "Automate Browser Tasks That Actually Work",
        "target_users": ["运营自动化团队", "RPA实施顾问", "客服流程优化负责人"],
    },
    "HarnessBridge": {
        "product_direction": "面向Agent开发者的环境接口中间件，减少重复交互和token浪费",
        "suggested_headline": "Cut Agent Token Costs by 65% With Smarter Interfaces",
        "target_users": ["AI Agent开发者", "LLM应用工程师", "Agent框架维护者"],
    },
    "multi-agent orchestration": {
        "product_direction": "面向企业的多Agent编排与监控平台，解决Agent协作不可见、难调试的痛点",
        "suggested_headline": "Orchestrate AI Agents With Full Visibility",
        "target_users": ["企业AI平台团队", "DevOps工程师", "AI解决方案架构师"],
    },
}


def is_specific_complaint(text: str) -> bool:
    if not text or len(text.strip()) < 20:
        return False
    if any(p in text for p in NOISE_PATTERNS):
        return False
    lower = text.lower()
    return any(w in lower for w in PAIN_WORDS)


def score_d3(pain_entry: dict | None) -> int:
    if not pain_entry:
        return 0
    complaints = pain_entry.get("top_complaints", [])
    count = sum(1 for c in complaints if is_specific_complaint(c))
    if count >= 3:
        return 5
    if count >= 1:
        return 3
    return 0


def extract_tool_count(quality: str) -> int:
    m = re.search(r"有(\d+)个工具站", quality or "")
    return int(m.group(1)) if m else 0


def score_d4(term: str, sources: set[str]) -> int:
    if term in PRODUCT_TERMS or "producthunt" in sources:
        if term.endswith(".dev") or " by " in term:
            return 5
        return 5 if term in PRODUCT_TERMS else 3
    if term in TOOL_TERMS:
        return 3
    if term in RESEARCH_TERMS:
        return 1
    # General concepts with spaces tend to be research topics
    if " " in term and term.lower() == term:
        return 1
    return 3


def score_d5(term: str, sources: set[str], d4: int) -> int:
    if term in PRODUCT_TERMS or "producthunt" in sources:
        return 5
    if d4 == 1:
        return 1
    if term in TOOL_TERMS:
        return 3
    if term in {"computer-use agents", "forward deployed agent", "vibe coding",
                "multi-agent orchestration", "HarnessBridge"}:
        return 5
    return 3


def score_d6(term: str, competition: str, quality: str, d3: int, sources: set[str]) -> int:
    tool_count = extract_tool_count(quality)
    if competition == "高" and tool_count >= 5:
        return 1
    if competition == "高" and tool_count >= 3:
        return 1 if d3 < 5 else 3
    if competition == "低":
        return 5
    if competition == "中":
        if d3 >= 5 and tool_count <= 2:
            return 5
        if tool_count <= 1:
            return 5
        return 3
    # high competition but fewer tools
    if tool_count <= 1 and d3 >= 3:
        return 5
    if "producthunt" in sources and tool_count <= 4:
        return 3
    return 1


def get_sources(term: str, raw: dict) -> set[str]:
    sources = set()
    for src, terms in raw.get("source_breakdown", {}).items():
        if term in terms:
            sources.add(src)
    return sources


def build_entry(term: str, scored: dict, pain: dict | None, raw: dict) -> dict:
    sources = get_sources(term, raw)
    d1 = TREND_SCORES.get(scored.get("trend", "📊平稳"), 3)
    d2 = COMP_SCORES.get(scored.get("competition", "中"), 3)
    d3 = score_d3(pain)
    d4 = score_d4(term, sources)
    d5 = score_d5(term, sources, d4)
    d6 = score_d6(term, scored.get("competition", "中"), scored.get("top10_quality", ""), d3, sources)
    total = d1 + d2 + d3 + d4 + d5 + d6

    entry = {
        "term": term,
        "total_score": total,
        "scores": {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5, "D6": d6},
        "trend": scored.get("trend"),
        "competition": scored.get("competition"),
        "main_geo": scored.get("main_geo"),
    }

    if total >= 24:
        entry["status"] = "进入验证池"
        brief = PRODUCT_BRIEFS.get(term, {})
        entry["product_direction"] = brief.get(
            "product_direction",
            f"基于「{term}」场景的工具化产品，解决用户核心痛点",
        )
        entry["suggested_headline"] = brief.get(
            "suggested_headline",
            f"Solve {term} Problems — Faster and Smarter",
        )
        entry["target_users"] = brief.get(
            "target_users",
            ["早期采用者", "技术团队负责人", "独立开发者"],
        )
    elif total >= 18:
        entry["status"] = "继续观察"
    return entry


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge_pool(path: Path, new_entries: list[dict], remove_terms: set[str] | None = None) -> list[dict]:
    existing = []
    if path.exists():
        data = load_json(path)
        existing = data.get("entries", data) if isinstance(data, dict) else data

    remove = remove_terms or set()
    by_term = {e["term"]: e for e in existing if e["term"] not in remove}
    for entry in new_entries:
        by_term[entry["term"]] = entry

    return sorted(by_term.values(), key=lambda x: -x["total_score"])


def main():
    raw = load_json(RAW_PATH)
    scored_data = load_json(SCORED_PATH)
    pain_data = load_json(PAIN_PATH)
    date = raw.get("date", datetime.now().strftime("%Y-%m-%d"))

    scored_map = {t["term"]: t for t in scored_data.get("terms", [])}
    pain_map = {t["term"]: t for t in pain_data.get("terms", [])}

    validated = []
    watch = []
    discarded = 0

    for term in raw.get("new_terms", []):
        if term not in scored_map:
            continue
        entry = build_entry(term, scored_map[term], pain_map.get(term), raw)
        if entry["total_score"] >= 24:
            validated.append(entry)
        elif entry["total_score"] >= 18:
            watch.append(entry)
        else:
            discarded += 1

    validated_terms = {e["term"] for e in validated}
    validated_entries = merge_pool(VALIDATED_PATH, validated)
    watch_entries = merge_pool(WATCH_PATH, watch, remove_terms=validated_terms)

    validated_out = {
        "date": date,
        "scored_at": datetime.now().isoformat(),
        "count": len(validated_entries),
        "entries": validated_entries,
    }
    watch_out = {
        "date": date,
        "scored_at": datetime.now().isoformat(),
        "count": len(watch_entries),
        "entries": watch_entries,
    }

    with open(VALIDATED_PATH, "w", encoding="utf-8") as f:
        json.dump(validated_out, f, ensure_ascii=False, indent=2)
    with open(WATCH_PATH, "w", encoding="utf-8") as f:
        json.dump(watch_out, f, ensure_ascii=False, indent=2)

    print(f"日期: {date}")
    print(f"验证池: {len(validated)} | 观察池: {len(watch)} | 丢弃: {discarded}")
    for e in sorted(validated, key=lambda x: -x["total_score"]):
        s = e["scores"]
        print(f"  ✓ {e['term']}: {e['total_score']} (D1={s['D1']} D2={s['D2']} D3={s['D3']} D4={s['D4']} D5={s['D5']} D6={s['D6']})")
    for e in sorted(watch, key=lambda x: -x["total_score"]):
        s = e["scores"]
        print(f"  ~ {e['term']}: {e['total_score']} (D1={s['D1']} D2={s['D2']} D3={s['D3']} D4={s['D4']} D5={s['D5']} D6={s['D6']})")


if __name__ == "__main__":
    main()
