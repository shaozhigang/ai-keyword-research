#!/usr/bin/env python3
"""Save Tavily search result to pain cache."""
import json
import sys
import os

CACHE_DIR = "/workspace/keywords/.pain_cache"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

if __name__ == "__main__":
    term, stype, data_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(data_path) as f:
        data = json.load(f)
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = f"{CACHE_DIR}/{sf(term)}_{stype}.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"saved {path}")
