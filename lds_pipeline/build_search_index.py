#!/usr/bin/env python3
"""
Build full-text search index for LDS scripture reader.

Reads all library/chapters/*.html files (skipping *_notes.html) and outputs
library/search.json — a compact JSON array for client-side search.

Usage:
    python3 lds_pipeline/build_search_index.py
"""

import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

# Resolve paths relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parent
CHAPTERS_DIR = REPO_ROOT / "library" / "chapters"
OUTPUT_FILE  = REPO_ROOT / "library" / "search.json"


class ChapterParser(HTMLParser):
    """Extract book title, chapter number, and verse text from a chapter HTML file."""

    def __init__(self):
        super().__init__()
        self.book = ""
        self.chapter = 0
        self.verses = []

        # state flags
        self._in_book_title = False
        self._in_chapter_num = False
        self._in_verse_num = False
        self._in_verse_text = False
        self._current_verse_num = None
        self._current_verse_text_parts = []
        self._depth_verse_num = 0
        self._depth_verse_text = 0

    # ------------------------------------------------------------------
    # HTMLParser callbacks
    # ------------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()

        if tag in ("h2", "h1") and "book-title" in classes:
            self._in_book_title = True

        elif tag == "p" and "chapter-num" in classes:
            self._in_chapter_num = True

        elif tag == "span" and "verse-num" in classes:
            self._in_verse_num = True
            self._depth_verse_num = 1

        elif tag == "span" and "verse-text" in classes:
            self._in_verse_text = True
            self._depth_verse_text = 1
            self._current_verse_text_parts = []

        elif self._in_verse_text:
            # Track nested tags so we don't exit too early
            self._depth_verse_text += 1

        elif self._in_verse_num:
            self._depth_verse_num += 1

    def handle_endtag(self, tag):
        if self._in_book_title and tag in ("h2", "h1"):
            self._in_book_title = False

        elif self._in_chapter_num and tag == "p":
            self._in_chapter_num = False

        elif self._in_verse_num:
            self._depth_verse_num -= 1
            if self._depth_verse_num <= 0:
                self._in_verse_num = False

        elif self._in_verse_text:
            self._depth_verse_text -= 1
            if self._depth_verse_text <= 0:
                self._in_verse_text = False
                if self._current_verse_num is not None:
                    text = " ".join(self._current_verse_text_parts).strip()
                    # Collapse multiple spaces
                    text = re.sub(r"\s+", " ", text)
                    if text:
                        self.verses.append({"v": self._current_verse_num, "t": text})
                self._current_verse_text_parts = []

    def handle_data(self, data):
        if self._in_book_title:
            self.book += data

        elif self._in_chapter_num:
            stripped = data.strip()
            if stripped.isdigit():
                self.chapter = int(stripped)

        elif self._in_verse_num and not self._in_verse_text:
            stripped = data.strip()
            if stripped.isdigit():
                self._current_verse_num = int(stripped)

        elif self._in_verse_text:
            self._current_verse_text_parts.append(data)


def process_chapter(path: Path):
    """Parse a single chapter file and return a search index entry, or None on failure."""
    stem = path.stem  # e.g. "genesis_1"

    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return None

    parser = ChapterParser()
    parser.feed(html)

    book = parser.book.strip()
    chapter = parser.chapter
    verses = parser.verses

    # Skip files with no verse content (e.g. title page, front matter)
    if not verses:
        return None

    return {
        "id": stem,
        "b":  book,
        "c":  chapter,
        "vv": verses,
    }


def main():
    chapter_files = sorted(
        p for p in CHAPTERS_DIR.glob("*.html")
        if not p.stem.endswith("_notes")
    )

    if not chapter_files:
        print(f"ERROR: no chapter files found in {CHAPTERS_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(chapter_files)} chapter files…")

    index = []
    skipped = 0
    for path in chapter_files:
        entry = process_chapter(path)
        if entry is None:
            skipped += 1
            continue
        index.append(entry)

    # Write compact JSON (no unnecessary whitespace)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    OUTPUT_FILE.write_text(json_text, encoding="utf-8")

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(
        f"Done. {len(index)} chapters indexed, {skipped} skipped. "
        f"Output: {OUTPUT_FILE}  ({size_kb:.0f} KB)"
    )


if __name__ == "__main__":
    main()
