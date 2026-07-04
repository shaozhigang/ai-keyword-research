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


def _arxiv_day_label(day: str) -> str:
    """Map YYYY-MM-DD to arXiv section header like 'Sat, 4 Jul 2026'."""
    from datetime import datetime

    dt = datetime.strptime(day, "%Y-%m-%d")
    return dt.strftime("%a, %-d %b %Y")


def fetch_arxiv_titles(category: str, day: str | None = None) -> list[str]:
    url = f"https://arxiv.org/list/{category}/recent?skip=0&show=2000"
    html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    label = _arxiv_day_label(day) if day else None
    if label:
        start = html.find(f"<h3>{label}")
        if start >= 0:
            end = html.find("<h3>", start + 5)
            section = html[start:end] if end > 0 else html[start:]
            titles = re.findall(
                r"<span class='descriptor'>Title:</span>\s*\n\s*(.*?)\s*\n",
                section,
            )
            return [t.strip() for t in titles]
    # Weekend/holiday: no submissions for requested day
    return []


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


def product_hunt_products(day: str) -> list[tuple[str, str]]:
    """Fetch Product Hunt daily leaderboard via Tavily extract."""
    import time

    parts = day.split("-")
    url = f"https://www.producthunt.com/leaderboard/daily/{parts[0]}/{int(parts[1])}/{int(parts[2])}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "X-Tavily-Access-Mode": "keyless"},
    )
    # Tavily extract API (keyless)
    payload = json.dumps({"urls": [url], "extract_depth": "advanced", "format": "markdown"}).encode()
    api_req = urllib.request.Request(
        "https://api.tavily.com/extract",
        data=payload,
        headers={"Content-Type": "application/json", "X-Tavily-Access-Mode": "keyless"},
        method="POST",
    )
    try:
        resp = json.loads(urllib.request.urlopen(api_req, timeout=90).read())
        content = ""
        for r in resp.get("results", []):
            content += r.get("raw_content", "") + "\n"
    except Exception:
        time.sleep(5)
        content = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")

    products: list[tuple[str, str]] = []
    for m in re.finditer(
        r"\[\d+\.\s+([^\]]+)\]\(https://www\.producthunt\.com/products/[^)]+\)([^\[]+)",
        content,
    ):
        name = m.group(1).strip()
        tagline = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", m.group(2))
        tagline = re.sub(r"\[Promoted\][^\n]*", "", tagline)
        tagline = re.sub(r"\s+", " ", tagline).strip(" !")
        if name and tagline:
            products.append((name, tagline))
    return products


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

    return signals


def main() -> None:
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    known = load_yesterday_terms(yesterday)

    hf_titles = fetch_hf_titles(today)
    arxiv_titles = fetch_arxiv_titles("cs.AI", today) + fetch_arxiv_titles("cs.LG", today)
    ph_products = product_hunt_products(today)

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
