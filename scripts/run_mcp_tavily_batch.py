#!/usr/bin/env python3
"""Run pending Tavily searches via local tavily-mcp stdio server."""
import json
import os
import re
import subprocess
import sys
import time

CACHE = "/workspace/keywords/.search_cache"
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-18"
DELAY = 5
MCP_BIN = "/workspace/node_modules/tavily-mcp/build/index.js"


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def parse_tavily_text(text):
    """Parse tavily-mcp text output into {results: [{url, title, content}]}"""
    if text.strip().startswith("{"):
        return json.loads(text)
    results = []
    blocks = re.split(r"\n(?=Title: )", text)
    for block in blocks:
        if not block.strip() or not block.startswith("Title:"):
            continue
        m_title = re.match(r"Title: (.+)", block)
        m_url = re.search(r"^URL: (.+)$", block, re.M)
        m_content = re.search(r"^Content: (.+?)(?:\n(?:Raw Content|Favicon):|\Z)", block, re.S | re.M)
        if m_title and m_url:
            results.append({
                "title": m_title.group(1).strip(),
                "url": m_url.group(1).strip(),
                "content": (m_content.group(1).strip() if m_content else ""),
            })
    return {"results": results}


class McpClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["node", MCP_BIN],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._id = 0

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _recv_id(self, expected_id):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                err = self.proc.stderr.read()
                raise RuntimeError(f"MCP server closed: {err}")
            msg = json.loads(line)
            if msg.get("id") == expected_id:
                return msg

    def initialize(self):
        self._id += 1
        rid = self._id
        self._send({
            "jsonrpc": "2.0",
            "id": rid,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "batch-runner", "version": "1.0"},
            },
        })
        resp = self._recv_id(rid)
        if "error" in resp:
            raise RuntimeError(resp["error"])
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def search(self, query, max_results=10, time_range=None):
        args = {"query": query, "max_results": max_results}
        if time_range:
            args["time_range"] = time_range
        self._id += 1
        rid = self._id
        self._send({
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {"name": "tavily_search", "arguments": args},
        })
        resp = self._recv_id(rid)
        if "error" in resp:
            raise RuntimeError(resp["error"])
        if resp.get("result", {}).get("isError"):
            text = resp["result"]["content"][0]["text"]
            raise RuntimeError(text[:200])
        text = resp["result"]["content"][0]["text"]
        return parse_tavily_text(text)

    def close(self):
        self.proc.terminate()


def pending_searches():
    scored = json.load(open(f"/workspace/keywords/scored/{DATE}.json"))
    failed = [e["term"] for e in scored["entries"] if "分析失败" in e.get("top10_quality", "")]
    needs = []
    for term in failed:
        if not os.path.exists(f"{CACHE}/{sf(term)}_trend.json"):
            needs.append((term, "trend", f'"{term}" news OR trending OR launch 2026', "month"))
        if not os.path.exists(f"{CACHE}/{sf(term)}_comp.json"):
            needs.append((term, "comp", term, None))
    return needs


def save_cache(term, stype, data):
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{sf(term)}_{stype}.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"saved {term} {stype} ({len(data.get('results', []))} results)")


def main():
    needs = pending_searches()
    print(f"Pending searches: {len(needs)}", flush=True)
    if not needs:
        subprocess.run([sys.executable, "/workspace/scripts/rescore_mcp_dated.py", "apply-cached", DATE])
        return

    client = McpClient()
    try:
        client.initialize()
        for i, (term, stype, query, tr) in enumerate(needs):
            print(f"[{i+1}/{len(needs)}] {stype}: {term[:70]}", flush=True)
            try:
                data = client.search(query, max_results=10, time_range=tr)
                save_cache(term, stype, data)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
            if i < len(needs) - 1:
                time.sleep(DELAY)
    finally:
        client.close()

    subprocess.run([sys.executable, "/workspace/scripts/rescore_mcp_dated.py", "apply-cached", DATE], check=True)


if __name__ == "__main__":
    main()
