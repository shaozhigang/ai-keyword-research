#!/usr/bin/env python3
"""Save MCP result from JSON file: mcp_save_file.py TERM STYPE MCP_RESPONSE.json"""
import json
import os
import sys

CACHE = "/workspace/keywords/.search_cache"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

term, stype, path = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path))
out = {"results": [
    {"url": r["url"], "title": r.get("title", ""), "content": (r.get("content") or "")[:2000]}
    for r in data.get("results", [])
]}
os.makedirs(CACHE, exist_ok=True)
with open(f"{CACHE}/{sf(term)}_{stype}.json", "w") as f:
    json.dump(out, f, ensure_ascii=False)
print(f"saved {term} {stype} ({len(out['results'])} results)")
