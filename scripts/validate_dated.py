#!/usr/bin/env python3
"""Score keywords from dated raw/scored/pain files into validated/{date}.json."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
BASE = Path("/workspace/keywords")

TREND_SCORES = {"📈上升": 5, "📊平稳": 3, "📉下降": 1}
COMP_SCORES = {"低": 5, "中": 3, "高": 1}

META_COMPLAINT_PATTERNS = [
    "暂无明确用户抱怨",
    "未发现明确用户痛点",
    "主要为学术",
    "用户主动寻找替代方案",
    "搜索结果中未发现",
]

RESEARCH_TERMS = {
    "LoopCoder-v2", "ACE-Ego-0", "MotionVLA", "ProCUA-SFT", "OPD-Evolver",
    "Looped World Models", "ActWorld", "GameCraft-Bench", "Visual-Seeker", "Dr-DCI",
    "EgoCS-400K", "LectūraAgents", "RepSelect", "ChLogic", "BrowseComp-Plus",
    "disaggregated inference", "test-time computation scaling", "on-policy self-distillation",
    "dLLMs", "ZPPO", "Variable-Width Transformers", "multimodal autoregressive modeling",
    "EvolveNav", "Fixed-Point Reasoners", "DRFLOW", "WEQA", "IsabeLLM", "PseudoBench",
    "ProvenanceGuard", "LegalHalluLens", "PreAct", "FlowRAG", "DecoSearch", "LongWebBench",
    "EComAgentBench", "FinAcumen", "SEAGym", "DeepInsight", "StepGuard", "SoftMoE",
    "Ternary Mamba", "EnvRL", "AnchorKV", "Volterra Generative Models", "TuneAhead",
    "MathVis-Fine",
}

SAAS_TERMS = {
    "zero-trust AI gateway", "MCP observability", "agent harness", "local AI inference",
    "SolonGate", "ClawEase", "Polygram Coding Agent", "MakersClaw", "Swytchcode CLI",
    "Daemons by Charlie Labs", "Deep Work Plan", "memi", "Docfarm", "Invoko", "PaneFlow",
    "Locus Founder", "Wilson", "Spanly", "Henji", "Goldfish", "Infinite", "Tyto",
}

TOOL_TERMS = {
    "computer-using agents", "self-evolving agents", "Framer 3.0", "Quartz",
}

PRODUCT_BRIEFS = {
    "zero-trust AI gateway": {
        "product_direction": "面向企业的AI Agent零信任安全网关，统一管控工具调用与数据出站",
        "suggested_headline": "Zero-Trust Security for Every AI Agent You Deploy",
        "target_users": ["平台安全工程师", "AI基础设施团队", "合规与风控负责人"],
    },
    "MCP observability": {
        "product_direction": "面向MCP服务开发者的Agent可观测性平台，追踪工具调用链路与异常",
        "suggested_headline": "See Exactly What Your AI Agents Do Inside MCP",
        "target_users": ["MCP服务器维护者", "LLM应用开发者", "DevOps/SRE团队"],
    },
    "agent harness": {
        "product_direction": "面向Agent开发者的上下文编排与任务规划层，让Agent执行更稳定可复现",
        "suggested_headline": "Give Your AI Agents a Plan That Actually Works",
        "target_users": ["AI Agent开发者", "自动化工作流架构师", "企业AI产品团队"],
    },
    "local AI inference": {
        "product_direction": "面向隐私敏感用户的本地AI推理套件，一键部署模型并管理离线工作流",
        "suggested_headline": "Run Powerful AI Locally — Private, Fast, Yours",
        "target_users": ["注重隐私的专业用户", "离线场景开发者", "小型企业IT负责人"],
    },
    "computer-using agents": {
        "product_direction": "面向运营团队的浏览器自动化Agent平台，解决页面导航与CAPTCHA失败问题",
        "suggested_headline": "Automate Browser Tasks That Actually Work",
        "target_users": ["运营自动化团队", "RPA实施顾问", "客服流程优化负责人"],
    },
    "self-evolving agents": {
        "product_direction": "面向AI产品团队的自进化Agent框架，从反馈中自动优化策略与工具链",
        "suggested_headline": "AI Agents That Learn and Improve From Every Run",
        "target_users": ["AI产品经理", "Agent框架开发者", "企业自动化平台团队"],
    },
    "SolonGate": {
        "product_direction": "面向开发者的AI Agent零信任API网关，细粒度控制2,000+外部工具访问",
        "suggested_headline": "Secure AI Agent Access to 2,000+ APIs With Durable State",
        "target_users": ["SaaS平台开发者", "AI安全工程师", "集成架构师"],
    },
    "memi": {
        "product_direction": "面向Mac用户的本地优先AI邮件客户端，聚焦深度工作与隐私保护",
        "suggested_headline": "An AI Email Client Built for Focus — Runs Locally on Your Mac",
        "target_users": ["知识工作者", "独立顾问", "注重隐私的Mac用户"],
    },
    "MakersClaw": {
        "product_direction": "面向创客的AI Agent托管平台，追踪、分享并管理Agent构建产物",
        "suggested_headline": "Host, Share, and Track Everything Your AI Builds",
        "target_users": ["独立开发者", "AI创客社区", "小型产品团队"],
    },
    "Polygram Coding Agent": {
        "product_direction": "面向工程团队的AI编程Agent，联动PR、Issue、CI与文档自动化",
        "suggested_headline": "Keep PRs, Issues, CI, and Docs Moving With AI Agents",
        "target_users": ["工程团队Tech Lead", "DevOps工程师", "开源项目维护者"],
    },
    "Daemons by Charlie Labs": {
        "product_direction": "面向非技术创始人的短信驱动AI Agent，自动构建并运行轻量业务流程",
        "suggested_headline": "Text an AI Agent — It Builds and Runs Your Business",
        "target_users": ["solo创业者", "小型商户", "自由职业服务提供者"],
    },
    "disaggregated inference": {
        "product_direction": "面向GPU集群团队的推理分离调度平台，缓解饱和时延超线性增长",
        "suggested_headline": "Scale LLM Inference Without the Superlinear Latency Tax",
        "target_users": ["ML基础设施工程师", "云GPU平台运维", "大模型Serving团队"],
    },
    "PreAct": {
        "product_direction": "面向Agent开发者的预执行规划框架，降低不稳定与延迟导致的失败率",
        "suggested_headline": "Plan Before You Act — Stable AI Agents, Fewer Failures",
        "target_users": ["Agent框架开发者", "LLM应用工程师", "企业自动化团队"],
    },
}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def count_specific_complaints(complaints: list) -> int:
    count = 0
    for c in complaints or []:
        if any(p in c for p in META_COMPLAINT_PATTERNS):
            continue
        if len(c.strip()) >= 6:
            count += 1
    return count


def score_d3(pain_entry: dict | None) -> int:
    if not pain_entry:
        return 0
    count = count_specific_complaints(pain_entry.get("top_complaints", []))
    if count >= 3:
        return 5
    if count >= 1:
        return 3
    return 0


def extract_tool_count(quality: str) -> int:
    m = re.search(r"有(\d+)个工具站", quality or "")
    return int(m.group(1)) if m else 0


def get_sources(term: str, raw: dict) -> set[str]:
    sources = set()
    for src, terms in raw.get("source_breakdown", {}).items():
        if term in terms:
            sources.add(src)
    return sources


def score_d4(term: str, sources: set[str]) -> int:
    if term in SAAS_TERMS:
        return 5
    if term in TOOL_TERMS:
        return 3
    if term in RESEARCH_TERMS:
        return 1
    if "producthunt" in sources:
        return 5 if term in {"Framer 3.0", "Wolfram Language 15", "Android 17"} else 3
    if " " in term and term.lower() == term:
        return 1
    return 3


def score_d5(term: str, sources: set[str], d4: int) -> int:
    if term in SAAS_TERMS or term in {
        "computer-using agents", "self-evolving agents", "disaggregated inference",
        "MCP observability", "zero-trust AI gateway", "agent harness", "local AI inference",
    }:
        return 5
    if d4 == 1:
        return 1
    if "producthunt" in sources:
        return 5 if term in SAAS_TERMS else 3
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
        if "producthunt" in sources:
            return 3
        return 3
    if tool_count <= 1 and d3 >= 3:
        return 5
    return 1


def build_entry(term: str, scored: dict, pain: dict | None, raw: dict) -> dict | None:
    sources = get_sources(term, raw)
    d1 = TREND_SCORES.get(scored.get("trend", "📊平稳"), 3)
    d2 = COMP_SCORES.get(scored.get("competition", "中"), 3)
    d3 = score_d3(pain)
    d4 = score_d4(term, sources)
    d5 = score_d5(term, sources, d4)
    d6 = score_d6(term, scored.get("competition", "中"), scored.get("top10_quality", ""), d3, sources)
    total = d1 + d2 + d3 + d4 + d5 + d6

    if total < 18:
        return None

    entry = {
        "term": term,
        "total_score": total,
        "scores": {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5, "D6": d6},
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
    else:
        entry["status"] = "继续观察"

    return entry


def main():
    raw = load_json(BASE / "raw" / f"{DATE}.json")
    scored_data = load_json(BASE / "scored" / f"{DATE}.json")
    pain_data = load_json(BASE / "pain" / f"{DATE}.json")

    scored_map = {t["term"]: t for t in scored_data.get("entries", scored_data.get("terms", []))}
    pain_map = {t["term"]: t for t in pain_data.get("entries", pain_data.get("terms", []))}

    entries = []
    validated = watch = discarded = 0

    for term in raw.get("new_terms", []):
        if term not in scored_map:
            continue
        entry = build_entry(term, scored_map[term], pain_map.get(term), raw)
        if entry is None:
            discarded += 1
        else:
            entries.append(entry)
            if entry["status"] == "进入验证池":
                validated += 1
            else:
                watch += 1

    entries.sort(key=lambda x: -x["total_score"])
    out = {"date": DATE, "entries": entries}

    out_dir = BASE / "validated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{DATE}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"日期: {DATE}")
    print(f"验证池: {validated} | 观察池: {watch} | 丢弃: {discarded}")
    print(f"输出: {out_path}")
    for e in entries:
        s = e["scores"]
        mark = "✓" if e["status"] == "进入验证池" else "~"
        print(f"  {mark} {e['term']}: {e['total_score']} ({e['status']}) D1={s['D1']} D2={s['D2']} D3={s['D3']} D4={s['D4']} D5={s['D5']} D6={s['D6']}")


if __name__ == "__main__":
    main()
