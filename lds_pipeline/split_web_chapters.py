#!/usr/bin/env python3
"""
split_web_chapters.py
=====================
Splits each monolithic chapter HTML file into two files:

  {slug}.html        — scripture text only (verse-num + verse-text), fast to load
  {slug}_notes.html  — commentary blocks only, lazy-loaded as user scrolls

Also truncates any single commentary block that exceeds MAX_BLOCK_CHARS,
fixing the moroni_10 pipeline bug (one Donaldson block with 17,009 paragraphs).

Run from repo root:
    python lds_pipeline/split_web_chapters.py [--dir library/chapters] [--dry-run]
"""

import argparse
import os
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

# ── Config ────────────────────────────────────────────────────────────────────
CHAPTERS_DIR  = Path("library/chapters")

# Commentary classes (everything that is NOT verse text)
NOTES_CLASSES = {
    "jst-block", "etymology-block", "rabbinical-block", "lds-commentary-block",
    "fathers-block", "ancient-block", "donaldson-block", "jsp-block",
    "semantic-quote", "semantic-block", "backlinks",
}

# Per-element text cap: truncate any single block exceeding this many characters
MAX_BLOCK_CHARS = 4000

# Maximum paragraphs inside a single donaldson-block
MAX_DONA_PARAS = 12


def _truncate_block(tag):
    """
    Truncate oversized commentary blocks in-place.
    For donaldson-block: cap paragraph count, then total char length.
    For all blocks: cap total innerHTML.
    """
    if not tag or isinstance(tag, NavigableString):
        return

    # Cap donaldson paragraphs
    if "donaldson-block" in (tag.get("class") or []):
        paras = tag.find_all("p", class_="donaldson-para")
        if len(paras) > MAX_DONA_PARAS:
            for p in paras[MAX_DONA_PARAS:]:
                p.decompose()

    # Cap total text length
    text = tag.get_text()
    if len(text) > MAX_BLOCK_CHARS:
        # Walk text nodes inside and truncate the last one that pushes us over
        total = 0
        for child in tag.descendants:
            if isinstance(child, NavigableString):
                remaining = MAX_BLOCK_CHARS - total
                if remaining <= 0:
                    child.replace_with("")
                elif len(child) > remaining:
                    snip = child[:remaining]
                    # cut at word boundary
                    pos = snip.rfind(" ")
                    if pos > remaining // 2:
                        snip = snip[:pos]
                    child.replace_with(snip + "…")
                    total = MAX_BLOCK_CHARS
                else:
                    total += len(child)


def split_chapter(src_path: Path, dry_run: bool = False) -> dict:
    """
    Split one chapter file. Returns stats dict.
    Modifies src_path in-place (text only), writes src_path with _notes suffix.
    """
    slug = src_path.stem
    notes_path = src_path.parent / f"{slug}_notes.html"

    html = src_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if not body:
        return {"slug": slug, "skipped": True}

    # ── Separate header elements ──────────────────────────────────────────────
    # These go into the text file (always).
    header_html_parts = []
    for tag in body.children:
        if isinstance(tag, NavigableString):
            continue
        cls = tag.get("class") or []
        if tag.name in ("h1", "h2", "h3") or "chapter-num" in cls or "score-legend" in cls:
            header_html_parts.append(str(tag))

    # ── Process verse divs ────────────────────────────────────────────────────
    verse_divs = body.find_all("div", class_="verse")

    text_verses_html = []      # verse text only
    notes_sections_html = []   # notes per verse
    total_notes_chars = 0
    verse_count = 0
    notes_verse_count = 0

    for verse_div in verse_divs:
        verse_id = verse_div.get("id", "")   # e.g. "v1"

        # Older pipeline builds omitted id attributes — derive from verse-num span
        if not verse_id or not re.search(r"\d", verse_id):
            num_span = verse_div.find("span", class_="verse-num")
            if num_span:
                num_text = num_span.get_text().strip()
                if num_text.isdigit():
                    verse_id = f"v{num_text}"
                    verse_div["id"] = verse_id  # fix in the soup tree too

        verse_num = re.sub(r"[^0-9]", "", verse_id)

        # Separate text spans from commentary blocks
        text_children = []
        notes_children = []

        for child in verse_div.children:
            if isinstance(child, NavigableString):
                continue
            child_cls = set(child.get("class") or [])
            if child_cls & NOTES_CLASSES:
                _truncate_block(child)
                notes_children.append(str(child))
            else:
                text_children.append(str(child))

        # Text verse (always includes the verse div wrapper)
        text_verses_html.append(
            f'<div class="verse" id="{verse_id}">\n'
            + "\n".join(text_children) + "\n</div>"
        )

        # Notes section (only if there are blocks to include)
        if notes_children and verse_num:
            notes_html = "\n".join(notes_children)
            total_notes_chars += len(notes_html)
            notes_sections_html.append(
                f'<div data-verse="{verse_num}">\n{notes_html}\n</div>'
            )
            notes_verse_count += 1

        verse_count += 1

    # ── Build text-only chapter file ──────────────────────────────────────────
    # Get head from original soup
    head = soup.head
    head_html = str(head) if head else "<head><meta charset=\"UTF-8\"></head>"

    text_file_html = (
        "<!DOCTYPE html>\n"
        f"<html lang=\"en\">\n{head_html}\n<body>\n"
        "<div class=\"scripture\">\n"
        + "\n".join(header_html_parts) + "\n"
        + "\n".join(text_verses_html) + "\n"
        "</div>\n"
        "</body>\n</html>\n"
    )

    # ── Build notes file ──────────────────────────────────────────────────────
    if notes_sections_html:
        notes_file_html = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<body>\n"
            + "\n".join(notes_sections_html) + "\n"
            "</body>\n</html>\n"
        )
    else:
        notes_file_html = None

    if not dry_run:
        src_path.write_text(text_file_html, encoding="utf-8")
        if notes_file_html:
            notes_path.write_text(notes_file_html, encoding="utf-8")
        elif notes_path.exists():
            notes_path.unlink()  # remove stale notes file

    return {
        "slug": slug,
        "text_size": len(text_file_html),
        "notes_size": len(notes_file_html) if notes_file_html else 0,
        "verses": verse_count,
        "notes_verses": notes_verse_count,
        "skipped": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Split chapter HTML into text + notes files")
    parser.add_argument("--dir",     default=str(CHAPTERS_DIR), help="chapters directory")
    parser.add_argument("--books",   nargs="+", help="process only these book prefixes (e.g. moroni)")
    parser.add_argument("--dry-run", action="store_true", help="parse but do not write")
    args = parser.parse_args()

    chapters_dir = Path(args.dir)
    files = sorted(chapters_dir.glob("*.html"))
    # Exclude _notes files (already split)
    files = [f for f in files if not f.stem.endswith("_notes")]

    if args.books:
        files = [f for f in files if any(f.stem.startswith(b) for b in args.books)]

    print(f"Processing {len(files)} chapter files in {chapters_dir}")
    if args.dry_run:
        print("  (dry run — no files written)")

    total_text  = 0
    total_notes = 0
    biggest_before = 0
    biggest_after  = 0
    errors = 0

    for i, path in enumerate(files):
        before_size = path.stat().st_size
        biggest_before = max(biggest_before, before_size)

        try:
            stats = split_chapter(path, dry_run=args.dry_run)
        except Exception as e:
            print(f"  ERROR {path.name}: {e}", file=sys.stderr)
            errors += 1
            continue

        if stats.get("skipped"):
            continue

        total_text  += stats["text_size"]
        total_notes += stats["notes_size"]
        biggest_after = max(biggest_after, stats["text_size"])

        if before_size > 200_000 or stats["notes_size"] > 200_000:
            print(f"  {path.name}: {before_size//1024}kb → text {stats['text_size']//1024}kb "
                  f"+ notes {stats['notes_size']//1024}kb")

        if (i + 1) % 200 == 0:
            print(f"  ... {i+1}/{len(files)}")

    print(f"\nDone.")
    print(f"  Text files avg:   {total_text // max(len(files),1) // 1024}kb")
    print(f"  Notes total:      {total_notes // 1024}kb across {len(files)} chapters")
    print(f"  Largest text file: {biggest_after // 1024}kb  (was {biggest_before // 1024}kb)")
    if errors:
        print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
