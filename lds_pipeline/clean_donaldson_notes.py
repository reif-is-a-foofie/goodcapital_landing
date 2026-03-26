#!/usr/bin/env python3
"""
Remove verse-fragment leakage from generated Donaldson note blocks.

This post-processes existing library/chapters/*_notes.html files using the
same Donaldson paragraph cleaner used by the EPUB/web builder.
"""

import re
import json
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from lds_pipeline.epub.builder import _clean_donaldson_para
except ModuleNotFoundError:
    from epub.builder import _clean_donaldson_para


REPO = Path(__file__).resolve().parent.parent
CHAPTERS = REPO / "library" / "chapters"
TOC = REPO / "library" / "toc.json"
VERSE_CATALOG = REPO / "lds_pipeline" / "cache" / "standard_works" / "verse_catalog.json"

def build_chapter_index() -> dict[str, tuple[str, int]]:
    toc = json.loads(TOC.read_text(encoding="utf-8"))
    chapter_index: dict[str, tuple[str, int]] = {}
    current_book = ""
    for item in toc:
        depth = int(item.get("depth", 0))
        label = str(item.get("label", ""))
        href = str(item.get("href", ""))
        if depth == 1 and item.get("type") == "book":
            current_book = label
        elif depth == 2 and item.get("type") == "chapter" and current_book and href.startswith("chapters/"):
            try:
                chapter_index[Path(href).name] = (current_book, int(label))
            except ValueError:
                continue
    return chapter_index


def build_verse_catalog() -> dict[tuple[str, int], dict[str, str]]:
    rows = json.loads(VERSE_CATALOG.read_text(encoding="utf-8"))
    catalog: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        book = str(row.get("book", ""))
        chapter = int(row.get("chapter", 0))
        verse = str(row.get("verse", ""))
        text = str(row.get("text", "")).strip()
        if not (book and chapter and verse and text):
            continue
        catalog.setdefault((book, chapter), {})[verse] = text
    return catalog


def verse_text_map(chapter_html: Path, chapter_index: dict[str, tuple[str, int]], verse_catalog: dict[tuple[str, int], dict[str, str]]) -> dict[str, str]:
    book_chapter = chapter_index.get(chapter_html.name)
    if book_chapter:
        verses = verse_catalog.get(book_chapter, {})
        if verses:
            return verses

    soup = BeautifulSoup(chapter_html.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    mapping = {}
    for verse in soup.select("div.verse[id]"):
        vid = verse.get("id", "")
        if not vid.startswith("v"):
            continue
        text = verse.select_one(".verse-text")
        if not text:
            continue
        mapping[vid[1:]] = text.get_text(" ", strip=True)
    return mapping


def clean_notes(notes_html: Path, verses: dict[str, str]) -> tuple[bool, int]:
    soup = BeautifulSoup(notes_html.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    removed = 0
    changed = False

    for section in soup.select("div[data-verse]"):
        vnum = section.get("data-verse", "")
        verse_text = verses.get(vnum, "")
        for block in list(section.select(".donaldson-block")):
            paras = block.select(".donaldson-para")
            keep = []
            for para in paras:
                cleaned = _clean_donaldson_para(para.get_text(" ", strip=True), verse_text)
                if cleaned and len(cleaned.strip()) > 20:
                    keep.append(cleaned)
                else:
                    removed += 1
            if not keep:
                block.decompose()
                changed = True
                continue
            if len(keep) != len(paras):
                changed = True
            for para_node, text in zip(paras, keep):
                para_node.string = text
            for extra in paras[len(keep):]:
                extra.decompose()
        if not section.get_text(" ", strip=True):
            section.decompose()
            changed = True

    if changed:
        notes_html.write_text(str(soup), encoding="utf-8")
    return changed, removed


def main() -> None:
    chapter_index = build_chapter_index()
    verse_catalog = build_verse_catalog()
    changed_files = 0
    removed_paras = 0
    for notes_file in sorted(CHAPTERS.glob("*_notes.html")):
        chapter_file = CHAPTERS / (notes_file.stem.replace("_notes", "") + ".html")
        if not chapter_file.exists():
            continue
        verses = verse_text_map(chapter_file, chapter_index, verse_catalog)
        changed, removed = clean_notes(notes_file, verses)
        if changed:
            changed_files += 1
        removed_paras += removed
    print(f"Donaldson notes cleaned: {changed_files} files changed, {removed_paras} paragraphs removed")


if __name__ == "__main__":
    main()
