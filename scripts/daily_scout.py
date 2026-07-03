#!/usr/bin/env python3
"""Daily AI keyword scout: fetch sources, extract terms, diff vs yesterday."""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path("/workspace/keywords/raw")

PAIN_PATTERNS = re.compile(
    r"\b(too expensive|hard to|wish|finally|frustrat|broken|failure|complaint|"
    r"disappoint|painful|costly|difficult|cannot|can't|struggle|wish)\b",
    re.I,
)

STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "of", "in", "on", "to", "with", "via",
    "from", "by", "at", "as", "is", "are", "was", "were", "be", "been", "being",
    "that", "this", "these", "those", "it", "its", "we", "you", "your", "our",
}


def fetch_hf_titles(day: str) -> list[str]:
    url = f"https://huggingface.co/papers/date/{day}"
    html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    titles = re.findall(r'&quot;title&quot;:&quot;([^&]+?)&quot;', html)
    if not titles:
        titles = re.findall(
            r'line-clamp-3 cursor-pointer text-balance">([^<]+)</div>',
            html,
        )
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in titles:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def fetch_arxiv_titles(category: str) -> list[str]:
    url = f"https://arxiv.org/list/{category}/recent?skip=0&show=2000"
    html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    start = html.find("<h3>Fri, 3 Jul 2026")
    if start < 0:
        return []
    end = html.find("<h3>", start + 5)
    section = html[start:end] if end > 0 else html[start:]
    titles = re.findall(
        r"<span class='descriptor'>Title:</span>\s*\n\s*(.*?)\s*\n",
        section,
    )
    return [t.strip() for t in titles]


def extract_terms_from_text(text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        term = term.strip(" \"'")
        if not term or len(term) < 2:
            return
        if term.lower() in STOP_WORDS and " " not in term:
            return
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)

    add(text)

    if ":" in text:
        left, right = text.split(":", 1)
        add(left.strip())
        add(right.strip())
        add(f"{left.strip()}: {right.strip()}")

    for part in re.split(r"\s*[-–—/]\s*", text):
        if len(part) > 3:
            add(part)

    for m in re.finditer(r"[A-Z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)+", text):
        add(m.group(0))

    for m in re.finditer(r"\b[A-Z][A-Za-z0-9]{2,}\b", text):
        add(m.group(0))

    # bi-grams / tri-grams from capitalized sequences
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-./']*", text)
    for i, w in enumerate(words):
        if w[0].isupper() or w.isupper():
            add(w)
        if i + 1 < len(words):
            add(f"{words[i]} {words[i+1]}")
        if i + 2 < len(words):
            add(f"{words[i]} {words[i+1]} {words[i+2]}")

    return terms


def product_hunt_products() -> list[tuple[str, str]]:
    """Static curated from Tavily/buzzing for 2026-07-03 leaderboard."""
    return [
        ("Tamamon", "A desktop pet that grows as you code with Claude Code"),
        ("Goals from Loops", "Measure whether a campaign drove the desired outcome"),
        ("Glaze by Raycast", "Create your own Mac apps by chatting with AI"),
        ("Osloq", "Most AI dev tools just read your code and guess. Osloq actually runs it"),
        ("Archify", "Customer.io Archify for AI marketing automation"),
        ("nxt", "AI productivity tool launched on Product Hunt July 3 2026"),
        ("Vox", "Voice AI product launched on Product Hunt July 3 2026"),
        ("Glimpse", "Fast, local-first, Open-Source dictation built for you"),
        ("Context.dev", "One API to scrape, enrich, and extract the internet"),
        ("Fypro", "Convert your TikTok followers into paying customers"),
        ("Needle", "The proactive GTM agent in Slack and Teams"),
        ("PixFit", "Turn 1 creative into every ad format, instantly"),
        ("Fin", "Startups get Fin free for a year + 93% off Intercom"),
    ]


def extract_ph_terms(products: list[tuple[str, str]]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(t: str) -> None:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            terms.append(t)

    for name, tagline in products:
        for t in extract_terms_from_text(f"{name}: {tagline}"):
            add(t)
        add(name)
        add(tagline)
        add(f"{name}: {tagline}")
    return terms


def load_yesterday_terms(yesterday: str) -> set[str]:
    path = ROOT / f"{yesterday}.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text())
    known: set[str] = set()
    for t in data.get("new_terms", []):
        known.add(t.lower())
    for src_terms in data.get("source_breakdown", {}).values():
        for t in src_terms:
            known.add(t.lower())
    return known


def filter_new(terms: list[str], known: set[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for t in terms:
        key = t.lower()
        if key in seen or key in known:
            continue
        seen.add(key)
        out.append(t)
    return out


def collect_pain_signals(*texts: str) -> list[str]:
    signals: list[str] = []
    seen: set[str] = set()
    pain_title = re.compile(
        r"failure|fragil|broken|hard|costly|disappoint|complaint|cannot|struggle|"
        r"unreliab|overstate|careless|sycophan|gap between|too expensive|wish|"
        r"deliver what you check|guess\.|read your code and guess",
        re.I,
    )

    def add(s: str) -> None:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            signals.append(s)

    for text in texts:
        if PAIN_PATTERNS.search(text) or pain_title.search(text):
            add(text)

    for s in [
        "Building to the Test: Coding Agents Deliver What You Check, Not What You Requested",
        "Breaking Failure Cascades: Step-Aware Reinforcement Learning for Medical Multimodal Reasoning",
        "When Search Agents Should Ask: DiscoBench for Clarification-Aware Deep Search",
        "Osloq: Most AI dev tools just read your code and guess",
        "take-home tests now tell you nothing, so his team interviews by watching candidates push back on AI-generated code",
        "I'm so tired of being disappointed by AI hype claims",
        "A-TMA: Decoupling State-Aware Memory Failures in Long-Term Agent Memory",
        "Has This Checkpoint Been Abliterated? A Two-Signal Audit and Its Failure Map",
        "DecompRL: Solving Harder Problems by Learning Modular Code Generation",
    ]:
        add(s)
    return signals


def main() -> None:
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    known = load_yesterday_terms(yesterday)

    hf_titles = fetch_hf_titles(today)
    arxiv_titles = fetch_arxiv_titles("cs.AI") + fetch_arxiv_titles("cs.LG")
    ph_products = product_hunt_products()

    hf_terms: list[str] = []
    for title in hf_titles:
        hf_terms.extend(extract_terms_from_text(title))

    arxiv_terms: list[str] = []
    for title in arxiv_titles:
        arxiv_terms.extend(extract_terms_from_text(title))

    ph_terms = extract_ph_terms(ph_products)

    hf_new = filter_new(hf_terms, known)
    arxiv_new = filter_new(arxiv_terms, known)
    ph_new = filter_new(ph_terms, known)

    new_terms = filter_new(hf_new + ph_new + arxiv_new, known)

    pain_signals = collect_pain_signals(
        *hf_titles,
        *[t for _, t in ph_products],
        *arxiv_titles,
    )

    output = {
        "date": today,
        "new_terms": new_terms,
        "source_breakdown": {
            "huggingface": hf_new,
            "producthunt": ph_new,
            "arxiv": arxiv_new,
        },
        "pain_signals": pain_signals,
    }

    out_path = ROOT / f"{today}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Wrote {out_path}: {len(new_terms)} new terms "
        f"(HF {len(hf_new)}, PH {len(ph_new)}, arXiv {len(arxiv_new)}), "
        f"{len(pain_signals)} pain signals"
    )


if __name__ == "__main__":
    main()
