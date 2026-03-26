#!/usr/bin/env python3
"""
Build compact Strong's sidecars for scripture chapters.

Output:
  library/chapters/{slug}_strongs.json

Format:
  {
    "7": [
      {"sn":"H5315","xl":"nephesh","lm":"נֶפֶשׁ","pr":"neh'-fesh","gl":"properly, a breathing creature..."},
      ...
    ]
  }
"""

import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from lds_pipeline.sources import strongs
except ModuleNotFoundError:
    from sources import strongs


REPO = Path(__file__).resolve().parent.parent
CHAPTERS = REPO / "library" / "chapters"
VERSE_CATALOG = REPO / "lds_pipeline" / "cache" / "standard_works" / "verse_catalog.json"


def slugify_book(book: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", book.lower()).strip("_")


def compact_entry(entry: dict) -> dict:
    return {
        "sn": entry.get("strongs_num", ""),
        "lm": entry.get("lemma", ""),
        "xl": entry.get("xlit", ""),
        "pr": entry.get("pron", ""),
        "gl": (entry.get("strongs_def") or entry.get("kjv_def") or "")[:220],
        "kj": (entry.get("kjv_def") or "")[:180],
        "dv": (entry.get("derivation") or "")[:150],
    }


def build():
    rows = json.loads(VERSE_CATALOG.read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for row in rows:
        book = str(row.get("book", "")).strip()
        chapter = int(row.get("chapter", 0))
        verse = int(row.get("verse", 0))
        text = str(row.get("text", "")).strip()
        if not (book and chapter and verse and text):
            continue
        grouped[(book, chapter)].append((verse, text))

    written = 0
    for (book, chapter), verses in sorted(grouped.items()):
        book_upper = book.upper()
        if book_upper not in strongs.OT_BOOKS and book_upper not in strongs.NT_BOOKS:
            continue

        payload = {}
        for verse, text in sorted(verses):
            if book_upper in strongs.OT_BOOKS:
                entries = strongs.get_verse_strongs(book, chapter, verse, max_words=6)
            else:
                entries = strongs.get_verse_strongs_nt(book, chapter, verse, verse_text=text, max_words=6)
            if entries:
                payload[str(verse)] = [compact_entry(entry) for entry in entries]

        if not payload:
            continue

        slug = f"{slugify_book(book)}_{chapter}"
        out = CHAPTERS / f"{slug}_strongs.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written += 1
        if written % 100 == 0:
            print(f"{written} strongs sidecars written...")

    print(f"Done. {written} strongs sidecars written.")


if __name__ == "__main__":
    build()
