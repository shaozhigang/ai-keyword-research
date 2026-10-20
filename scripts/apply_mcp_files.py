#!/usr/bin/env python3
"""Save multiple MCP JSON files from manifest and apply-cached."""
import json
import os
import subprocess
import sys

CACHE = "/workspace/keywords/.search_cache"
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-18"
MANIFEST = sys.argv[2] if len(sys.argv) > 2 else "/tmp/mcp_manifest.json"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

for item in json.load(open(MANIFEST)):
    data = json.load(open(item["file"]))
    out = {"results": [
        {"url": r["url"], "title": r.get("title", ""), "content": (r.get("content") or "")[:2000]}
        for r in data.get("results", [])
    ]}
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{sf(item['term'])}_{item['stype']}.json"
    json.dump(out, open(path, "w"), ensure_ascii=False)
    print(f"saved {item['term'][:40]} {item['stype']} ({len(out['results'])})")

subprocess.run([sys.executable, "/workspace/scripts/rescore_mcp_dated.py", "apply-cached", DATE], check=True)
