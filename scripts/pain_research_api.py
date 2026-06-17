#!/usr/bin/env python3
"""Pain research using Tavily Research API (1 call per term)."""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

TAVILY_RESEARCH_URL = "https://api.tavily.com/research"
DELAY = 5
MAX_RETRIES = 5
CACHE_DIR = "/workspace/keywords/.pain_cache"


def safe_filename(term: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in term)


def tavily_research(term: str) -> dict:
    prompt = (
        f'For the AI tool/term "{term}", find user complaints, frustrations, broken features, '
        f"workarounds, alternatives, and desired features (I wish, why can't). "
        f"Focus on reddit, product hunt reviews, and user discussions. "
        f"Summarize top complaints in short Chinese phrases."
    )
    payload = {"input": prompt, "model": "mini"}
    api_key = os.environ.get("TAVILY_API_KEY", "")
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"
        headers["X-Client-Source"] = "tavily-mcp-keyless"

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                TAVILY_RESEARCH_URL,
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = e
            wait = DELAY * (2 ** attempt)
            print(f"      HTTP {e.code}, retry in {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            last_err = e
            wait = DELAY * (2 ** attempt)
            print(f"      error: {e}, retry in {wait}s", flush=True)
            time.sleep(wait)
    raise last_err


def extract_from_research(term: str, data: dict) -> dict:
    content = data.get("content", "") or ""
    sources = data.get("sources", []) or []

    complaints = []
    workarounds = []
    desired = []

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("|"):
            continue
        low = line.lower()
        if any(w in low for w in ["complaint", "frustrat", "broken", "bug", "pain", "limitation", "disappoint", "抱怨", "缺陷", "问题"]):
            complaints.append(line.lstrip("-•* ").strip())
        if any(w in low for w in ["workaround", "instead", "proxy", "third-party", "绕路", "替代", "手动"]):
            workarounds.append(line.lstrip("-•* ").strip())
        if any(w in low for w in ["wish", "why can't", "desired", "request", "希望", "期望", "需要"]):
            desired.append(line.lstrip("-•* ").strip())

    # Chinese summaries from bullet points
    def to_cn(items: list, limit: int = 3) -> list[str]:
        out = []
        for item in items:
            # extract short Chinese or English phrase
            item = re.sub(r"\[.*?\]", "", item)
            item = re.sub(r"https?://\S+", "", item)
            item = re.sub(r"\s+", " ", item).strip(" -•*")
            if len(item) < 8:
                continue
            if re.search(r"[\u4e00-\u9fff]", item):
                out.append(item[:80])
            elif any(w in item.lower() for w in ["expensive", "slow", "export", "pricing", "cms", "performance", "learning"]):
                mapping = {
                    "expensive": "定价过高",
                    "pricing": "定价不透明",
                    "export": "无法导出代码",
                    "cms": "CMS功能受限",
                    "performance": "性能慢，页面卡顿",
                    "learning": "学习曲线陡峭",
                    "broken": "功能不稳定",
                    "frustrat": "使用体验差",
                }
                for k, v in mapping.items():
                    if k in item.lower():
                        out.append(v)
                        break
                else:
                    out.append(item[:60])
            if len(out) >= limit:
                break
        return out or []

    top_complaints = to_cn(complaints, 3)
    wrk = to_cn(workarounds, 3)
    des = to_cn(desired, 3)

    if not top_complaints:
        if any(d in (s.get("url", "") or "") for s in sources for d in ["arxiv.org", "huggingface.co", "github.com"]):
            top_complaints = ["暂无明确用户抱怨，主要为学术/技术发布内容"]
        elif sources:
            top_complaints = ["搜索结果中未发现明确用户痛点"]
        else:
            top_complaints = ["暂无足够用户讨论数据"]

    return {
        "term": term,
        "top_complaints": top_complaints,
        "workarounds": wrk,
        "desired_features": des,
    }


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    scored_path = f"/workspace/keywords/scored/{date}.json"
    pain_path = f"/workspace/keywords/pain/{date}.json"

    with open(scored_path) as f:
        scored = json.load(f)
    rising = [e["term"] for e in scored["entries"] if "上升" in e.get("trend", "")]

    entries = []
    done = set()
    if os.path.exists(pain_path):
        with open(pain_path) as f:
            existing = json.load(f)
            entries = existing.get("entries", [])
            done = {e["term"] for e in entries}

    remaining = [t for t in rising if t not in done]
    print(f"Rising: {len(rising)} | Done: {len(done)} | Remaining: {len(remaining)}", flush=True)

    for i, term in enumerate(remaining):
        print(f"\n[{i+1}/{len(remaining)}] {term}", flush=True)
        cache = f"{CACHE_DIR}/{safe_filename(term)}_research.json"
        try:
            if os.path.exists(cache):
                with open(cache) as f:
                    data = json.load(f)
            else:
                data = tavily_research(term)
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache, "w") as f:
                    json.dump(data, f, ensure_ascii=False)
                time.sleep(DELAY)

            entry = extract_from_research(term, data)
            entries.append(entry)
            done.add(term)
            print(
                f"  -> C={entry['top_complaints']} W={entry['workarounds']} D={entry['desired_features']}",
                flush=True,
            )
            with open(pain_path, "w") as f:
                json.dump({"date": date, "entries": entries}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            entries.append({
                "term": term,
                "top_complaints": ["调研失败，暂无数据"],
                "workarounds": [],
                "desired_features": [],
            })
            with open(pain_path, "w") as f:
                json.dump({"date": date, "entries": entries}, f, ensure_ascii=False, indent=2)

    print(f"\nFinal: {len(entries)}/{len(rising)} -> {pain_path}", flush=True)


if __name__ == "__main__":
    main()
