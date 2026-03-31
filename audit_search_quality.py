#!/usr/bin/env python3
"""
Search quality audit for the library search payload.

Reports corpus mix, payload size, source summary sizes, and
approximate top hits for a handful of representative queries.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEARCH_FILE = ROOT / "library" / "search.json"


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def escape_regex(text: str) -> str:
    return re.escape(text)


def parse_query(query: str):
    phrases = []

    def repl(match):
        phrase = normalize(match.group(1))
        if phrase:
            phrases.append(phrase)
        return " "

    stripped = re.sub(r'"([^"]+)"', repl, query)
    terms = [tok for tok in normalize(stripped).split(" ") if tok and (len(tok) > 2 or tok.isdigit())]
    return normalize(query), terms, phrases


def resolve_scripture_ref(query: str, book_names):
    if not book_names:
        return None
    names = sorted(set(book_names), key=len, reverse=True)
    pattern = r"\b(" + "|".join(escape_regex(name) for name in names) + r")\.?\s+(\d+):(\d+)\b"
    match = re.search(pattern, query or "", re.I)
    if not match:
        return None
    return {
        "label": f"{match.group(1)} {int(match.group(2))}:{int(match.group(3))}",
    }


def resolve_scripture_chapter(query: str, book_names):
    if not book_names:
        return None
    names = sorted(set(book_names), key=len, reverse=True)
    pattern = r"\b(" + "|".join(escape_regex(name) for name in names) + r")\.?\s+(\d+)\b"
    match = re.search(pattern, query or "", re.I)
    if not match:
        return None
    return {
        "book": match.group(1),
        "chapter": int(match.group(2)),
    }


def priority(row):
    if row.get("kind") == "verse":
        return 3.0
    collection = row.get("collection", "")
    if collection == "General Conference":
        return 2.5
    if collection in {"Journal of Discourses", "History of the Church"}:
        return 2.2
    return 1.8


def score(row, query):
    raw, terms, phrases = parse_query(query)
    hay = normalize(" ".join([
        row.get("t", ""),
        row.get("collection", ""),
        row.get("label", ""),
        row.get("meta", ""),
        row.get("ref", ""),
        row.get("book", ""),
    ]))
    ref = normalize(row.get("ref", ""))
    title = normalize(" ".join([
        row.get("book", ""),
        row.get("collection", ""),
        row.get("label", ""),
        row.get("meta", ""),
    ]))
    s = priority(row)

    phrase_hit = False
    for phrase in phrases:
        if phrase and (phrase in hay or phrase in ref or phrase in title):
            s += 12
            phrase_hit = True

    hit_count = 0
    for term in terms:
        if term in hay:
            s += 3.5
            hit_count += 1
        if term in ref:
            s += 4.5
        if term in title:
            s += 5.5

    if terms:
        s += hit_count * 1.25
        if hit_count == len(terms):
            s += 4

    if raw and raw in ref:
        s += 10

    if phrase_hit and row.get("kind") == "verse":
        s += 4
    if phrase_hit and row.get("kind") == "source":
        s += 6

    s -= min(len(row.get("t", "")) / 1000.0, 4)
    return s


def flatten_index(data):
    rows = []
    for doc in data:
        if doc.get("kind") == "source":
            rows.append({
                "kind": "source",
                "id": doc.get("id", ""),
                "collection": doc.get("collection", ""),
                "label": doc.get("label", ""),
                "meta": doc.get("meta", ""),
                "href": doc.get("href", ""),
                "n": 1,
                "t": doc.get("t", ""),
                "ref": f"{doc.get('collection', '')} · {doc.get('label', '')}",
            })
            continue

        for item in doc.get("vv", []):
            text = item.get("t", "")
            rows.append({
                "kind": "verse",
                "id": doc.get("id", ""),
                "book": doc.get("b", ""),
                "chapter": doc.get("c", 0),
                "n": item.get("v", 0),
                "t": text,
                "ref": f"{doc.get('b', '')} {doc.get('c', 0)}:{item.get('v', 0)}",
            })
    return rows


def main():
    if not SEARCH_FILE.exists():
        print(f"Missing {SEARCH_FILE}", file=sys.stderr)
        return 1

    data = json.loads(SEARCH_FILE.read_text(encoding="utf-8"))
    rows = flatten_index(data)
    size_kb = SEARCH_FILE.stat().st_size / 1024.0
    verse_chapters = sum(1 for row in data if row.get("kind") == "verse")
    verse_count = sum(len(row.get("vv", [])) for row in data if row.get("kind") == "verse")
    source_count = sum(1 for row in data if row.get("kind") == "source")
    source_lengths = [len(row.get("t", "")) for row in data if row.get("kind") == "source"]
    book_names = sorted({row.get("b", "") for row in data if row.get("kind") == "verse" and row.get("b")})

    print(f"search.json size: {size_kb:.1f} KB")
    print(f"entries: {len(data)}")
    print(f"scripture chapters: {verse_chapters}")
    print(f"scripture verses: {verse_count}")
    print(f"sources: {source_count}")
    if source_lengths:
        print(f"source summary length: min={min(source_lengths)} avg={sum(source_lengths)/len(source_lengths):.1f} max={max(source_lengths)}")

    queries = [
        "John 3:16",
        "Good Better Best",
        "mist",
        "Enuma Elish",
        "History of the Church",
        "1 Nephi 8",
    ]

    for query in queries:
        exact = resolve_scripture_ref(query, book_names)
        chapter = resolve_scripture_chapter(query, book_names)
        scored = []
        for row in rows:
            s = score(row, query)
            if exact and row.get("kind") == "verse" and row.get("ref") == exact["label"]:
                s += 100
            if chapter and row.get("kind") == "verse" and row.get("book") == chapter["book"] and row.get("chapter") == chapter["chapter"]:
                s += 85
                if row.get("n") == 1:
                    s += 15
            if s > 0:
                scored.append((s, row))
        scored.sort(key=lambda pair: (-pair[0], 0 if pair[1].get("kind") == "verse" else 1, str(pair[1].get("ref", ""))))

        print(f"\nQUERY: {query}")
        for s, row in scored[:5]:
            ref = row.get("ref") or f"{row.get('collection', '')} · {row.get('label', '')}"
            print(f"  {s:6.2f}  {row.get('kind'):6s}  {ref}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
