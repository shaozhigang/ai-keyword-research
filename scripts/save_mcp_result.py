#!/usr/bin/env python3
"""Save MCP Tavily result from stdin: save_mcp_result.py <term> <trend|comp>"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_save import save, try_score, append_scored

term, stype = sys.argv[1], sys.argv[2]
data = json.load(sys.stdin)
save(term, stype, data)
entry = try_score(term)
if entry:
    append_scored(entry)
    print(json.dumps(entry, ensure_ascii=False))
else:
    print(f"Cached {stype} for {term}")
