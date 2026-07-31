#!/usr/bin/env python3
"""Save single MCP tavily_search JSON response to cache. Usage: save_cursor_mcp.py TERM STYPE < response.json"""
import json
import os
import sys

CACHE = "/workspace/keywords/.search_cache"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

term, stype = sys.argv[1], sys.argv[2]
data = json.load(sys.stdin)
# MCP returns full response; cache needs {results: [...]}
if "results" in data:
    out = {"results": data["results"]}
else:
    out = data
os.makedirs(CACHE, exist_ok=True)
path = f"{CACHE}/{sf(term)}_{stype}.json"
with open(path, "w") as f:
    json.dump(out, f, ensure_ascii=False)
print(f"saved {term} {stype} ({len(out.get('results',[]))} results)")
