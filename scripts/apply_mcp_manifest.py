#!/usr/bin/env python3
"""Process manifest of MCP search results: [{term, stype, data: {results:[...]}}]"""
import json
import os
import subprocess
import sys

CACHE = "/workspace/keywords/.search_cache"
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-18"


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def save(term, stype, data):
    out = {"results": data.get("results", [])} if "results" in data else data
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{sf(term)}_{stype}.json"
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"saved {term} {stype} ({len(out.get('results', []))} results)")


manifest = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mcp_manifest.json"))
for item in manifest:
    save(item["term"], item["stype"], item["data"])

subprocess.run([sys.executable, "/workspace/scripts/rescore_mcp_dated.py", "apply-cached", DATE], check=True)
