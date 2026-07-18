#!/usr/bin/env python3
"""Inherit scores from PH parent titles for fragment terms still marked 分析失败."""
import json
import sys
from datetime import datetime

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-18"
SCORED = f"/workspace/keywords/scored/{DATE}.json"

with open(SCORED) as f:
    data = json.load(f)

by_term = {e["term"]: e for e in data["entries"]}
parents = [t for t, e in by_term.items() if "分析失败" not in e.get("top10_quality", "") and ":" in t]

def find_parent(term: str) -> str | None:
  best = None
  for p in parents:
    if term == p:
      return None
    if term in p or p.startswith(term) or term.startswith(p.split(":")[0].strip()):
      if best is None or len(p) > len(best):
        best = p
  return best

updated = 0
for i, e in enumerate(data["entries"]):
  if "分析失败" not in e.get("top10_quality", ""):
    continue
  parent = find_parent(e["term"])
  if not parent or parent not in by_term:
    continue
  src = by_term[parent]
  data["entries"][i] = {
    "term": e["term"],
    "trend": src["trend"],
    "main_geo": src["main_geo"],
    "competition": src["competition"],
    "top10_quality": f"继承自「{parent.split(':')[0].strip()}」；{src['top10_quality']}",
  }
  updated += 1
  print(f"inherit {e['term'][:50]} <- {parent.split(':')[0]}")

data["scored_at"] = datetime.now().isoformat()
with open(SCORED, "w") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)

remaining = sum(1 for e in data["entries"] if "分析失败" in e.get("top10_quality", ""))
print(f"Inherited {updated}, remaining failed: {remaining}")
