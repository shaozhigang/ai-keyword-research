#!/usr/bin/env python3
"""Save MCP Tavily search batches to pain cache."""
import json
import os
import sys

CACHE_DIR = "/workspace/keywords/.pain_cache"


def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)


def save(term, stype, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = f"{CACHE_DIR}/{sf(term)}_{stype}.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"saved {path}")


if __name__ == "__main__":
    batch_path = sys.argv[1]
    with open(batch_path) as f:
        batch = json.load(f)
    for item in batch:
        save(item["term"], item["stype"], item["data"])
