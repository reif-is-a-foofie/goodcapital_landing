#!/usr/bin/env python3
"""
Build full-text search index for LDS scripture reader.

Reads scripture chapters plus generated source documents and outputs
library/search.json for client-side search.

Usage:
    python3 lds_pipeline/build_search_index.py
"""

import argparse
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser
from bs4 import BeautifulSoup

# Resolve paths relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parent
CHAPTERS_DIR = REPO_ROOT / "library" / "chapters"
TOC_FILE     = REPO_ROOT / "library" / "toc.json"
SOURCE_TOC   = REPO_ROOT / "library" / "source_toc.json"
SOURCE_ROOT  = REPO_ROOT / "library" / "sources"
OUTPUT_FILE  = REPO_ROOT / "library" / "search.json"
SOURCE_SUMMARY_LIMIT = 1200


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


def build_toc_lookup():
    if not TOC_FILE.exists():
        return {}
    try:
        toc = json.loads(TOC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    lookup = {}
    current_book = ""
    for item in toc:
        item_type = item.get("type")
        if item_type == "book":
            current_book = item.get("label", "") or current_book
        elif item_type == "chapter":
            chapter_id = item.get("id") or ""
            if not chapter_id:
                continue
            chapter_num = 0
            label = str(item.get("label", "")).strip()
            if label.isdigit():
                chapter_num = int(label)
            else:
                try:
                    chapter_num = int(Path(chapter_id).stem.rsplit("_", 1)[-1])
                except Exception:
                    chapter_num = 0
            lookup[chapter_id] = {
                "book": current_book,
                "chapter": chapter_num,
            }
    return lookup


TOC_LOOKUP = build_toc_lookup()


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

    fallback = TOC_LOOKUP.get(stem, {})
    if not book:
        book = fallback.get("book", "")
    if not chapter:
        chapter = fallback.get("chapter", 0)

    # Skip files with no verse content (e.g. title page, front matter)
    if not verses:
        return None

    return {
        "kind": "verse",
        "id": stem,
        "b":  book,
        "c":  chapter,
        "vv": verses,
    }


def load_source_docs():
    if not SOURCE_TOC.exists():
        return []
    toc = json.loads(SOURCE_TOC.read_text(encoding="utf-8"))
    docs = []
    for collection in toc:
        raw_items = collection.get("items", [])
        flat_items = []
        for it in raw_items:
            if it.get("type") == "group":
                flat_items.extend(it.get("items", []))
            else:
                flat_items.append(it)
        for item in flat_items:
            html_path = REPO_ROOT / "library" / item.get("href", "")
            if not html_path.exists():
                continue
            try:
                soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
            except Exception:
                continue
            paragraphs = []
            for idx, para in enumerate(soup.select("p.source-para"), start=1):
                text = para.get_text(" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    continue
                paragraphs.append(text)
            if not paragraphs:
                continue
            summary = " ".join(paragraphs[:3]).strip()
            summary = re.sub(r"\s+", " ", summary).strip()
            if len(summary) > SOURCE_SUMMARY_LIMIT:
                summary = summary[:SOURCE_SUMMARY_LIMIT].rsplit(" ", 1)[0].rstrip() + "…"
            docs.append({
                "kind": "source",
                "id": item.get("id", html_path.stem),
                "s": collection.get("id", ""),
                "collection": collection.get("label", ""),
                "label": item.get("label", ""),
                "meta": item.get("meta", ""),
                "href": item.get("href", ""),
                "t": summary,
            })
    return docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-sources", action="store_true", default=True)
    args = parser.parse_args()

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

    if args.include_sources:
        index.extend(load_source_docs())

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
