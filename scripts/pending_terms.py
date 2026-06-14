#!/usr/bin/env python3
import json, os, sys
CACHE = "/workspace/keywords/.search_cache"
RAW = "/workspace/keywords/daily_raw.json"

def sf(t):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in t)

def needs(term, step):
    return not os.path.exists(f"{CACHE}/{sf(term)}_{step}.json")

with open(RAW) as f:
    terms = json.load(f)["new_terms"]

for term in terms:
    if needs(term, "trend"):
        print(f"TREND\t{term}")
    elif needs(term, "comp"):
        print(f"COMP\t{term}")
