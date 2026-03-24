"""
Parse raw extracted text into structured scripture objects.

Handles LDS canonical structure:
  Old Testament, New Testament, Book of Mormon, D&C, Pearl of Great Price

Output structure:
  Volume → Book → Chapter → Verse
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Verse:
    book:    str
    chapter: int
    verse:   int
    text:    str
    volume:  str = ""


@dataclass
class Chapter:
    book:    str
    number:  int
    volume:  str = ""
    verses:  list[Verse] = field(default_factory=list)
    heading: str = ""   # chapter intro/heading if present


@dataclass
class Book:
    name:    str
    volume:  str = ""
    chapters: list[Chapter] = field(default_factory=list)


@dataclass
class Volume:
    name:  str
    books: list[Book] = field(default_factory=list)


# ── Volume/book name maps ─────────────────────────────────────────────────────

VOLUME_MARKERS = [
    "THE OLD TESTAMENT",
    "THE NEW TESTAMENT",
    "THE BOOK OF MORMON",
    "DOCTRINE AND COVENANTS",
    "THE PEARL OF GREAT PRICE",
]

# Books in canonical order with alternate title forms
OT_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
    "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
]

NT_BOOKS = [
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
    "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy",
    "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation",
]

BOM_BOOKS = [
    "1 Nephi", "2 Nephi", "Jacob", "Enos", "Jarom", "Omni",
    "Words of Mormon", "Mosiah", "Alma", "Helaman",
    "3 Nephi", "4 Nephi", "Mormon", "Ether", "Moroni",
]

PGP_BOOKS = [
    "Moses", "Abraham", "Joseph Smith—Matthew",
    "Joseph Smith—History", "Articles of Faith",
]

ALL_BOOKS = OT_BOOKS + NT_BOOKS + BOM_BOOKS + ["Doctrine and Covenants"] + PGP_BOOKS

BOOK_TO_VOLUME = {}
for b in OT_BOOKS:
    BOOK_TO_VOLUME[b.upper()] = "Old Testament"
for b in NT_BOOKS:
    BOOK_TO_VOLUME[b.upper()] = "New Testament"
for b in BOM_BOOKS:
    BOOK_TO_VOLUME[b.upper()] = "Book of Mormon"
BOOK_TO_VOLUME["DOCTRINE AND COVENANTS"] = "Doctrine and Covenants"
for b in PGP_BOOKS:
    BOOK_TO_VOLUME[b.upper()] = "Pearl of Great Price"


# ── Parsing ───────────────────────────────────────────────────────────────────

# Match "Genesis 1:1" style references anywhere in text
_VERSE_RE = re.compile(
    r'^(\d?\s*[A-Z][A-Za-z ]+)\s+(\d+):(\d+)\s+(.*)',
    re.MULTILINE
)

# Simpler inline verse number: line starting with a digit
_INLINE_VERSE_RE = re.compile(r'^\s*(\d+)\s+(.+)')


def parse_structured_text(text: str) -> list[Volume]:
    """
    Two-pass parse:
      Pass 1 — detect volume/book/chapter headers
      Pass 2 — extract verse text
    Returns list of Volume objects.
    """
    lines = text.split('\n')
    volumes: dict[str, Volume] = {}
    current_volume = "Old Testament"
    current_book = None
    current_chapter = None
    current_chapter_num = 0

    # Build book header regex
    book_names_escaped = [re.escape(b) for b in sorted(ALL_BOOKS, key=len, reverse=True)]
    book_re = re.compile(
        r'^(' + '|'.join(book_names_escaped) + r')\s*$',
        re.IGNORECASE
    )
    chapter_re = re.compile(r'^(?:Chapter|CHAPTER|Sec(?:tion)?\.?|Section)\s+(\d+)', re.IGNORECASE)
    chapter_num_re = re.compile(r'^(\d+)\s*$')  # bare chapter number on its own line

    def get_or_create_volume(name: str) -> Volume:
        if name not in volumes:
            volumes[name] = Volume(name=name, books=[])
        return volumes[name]

    def get_or_create_book(vol: Volume, name: str) -> Book:
        for b in vol.books:
            if b.name.upper() == name.upper():
                return b
        b = Book(name=name, volume=vol.name)
        vol.books.append(b)
        return b

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Volume detection
        for vm in VOLUME_MARKERS:
            if vm in stripped.upper():
                current_volume = _normalise_volume(vm)
                current_book = None
                current_chapter = None
                break

        # Book header
        bm = book_re.match(stripped)
        if bm:
            vol = get_or_create_volume(current_volume)
            # Use canonical casing
            canon_name = _canonical_book_name(bm.group(1))
            current_book = get_or_create_book(vol, canon_name)
            current_chapter = None
            current_chapter_num = 0
            continue

        # Chapter header
        cm = chapter_re.match(stripped) or chapter_num_re.match(stripped)
        if cm and current_book is not None:
            current_chapter_num = int(cm.group(1))
            current_chapter = Chapter(
                book=current_book.name,
                number=current_chapter_num,
                volume=current_volume,
            )
            current_book.chapters.append(current_chapter)
            continue

        # Verse: starts with a number
        vm2 = _INLINE_VERSE_RE.match(stripped)
        if vm2 and current_chapter is not None:
            verse_num = int(vm2.group(1))
            verse_text = vm2.group(2).strip()
            # Accumulate continuation lines
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt:
                    break
                if _INLINE_VERSE_RE.match(nxt):
                    break
                if book_re.match(nxt) or chapter_re.match(nxt):
                    break
                verse_text += " " + nxt
                j += 1

            v = Verse(
                book=current_chapter.book,
                chapter=current_chapter.number,
                verse=verse_num,
                text=verse_text,
                volume=current_volume,
            )
            current_chapter.verses.append(v)

    # Return in canonical order
    order = ["Old Testament", "New Testament", "Book of Mormon",
             "Doctrine and Covenants", "Pearl of Great Price"]
    result = []
    for name in order:
        if name in volumes:
            result.append(volumes[name])
    return result


def _normalise_volume(marker: str) -> str:
    m = marker.upper()
    if "OLD TESTAMENT" in m:    return "Old Testament"
    if "NEW TESTAMENT" in m:    return "New Testament"
    if "BOOK OF MORMON" in m:   return "Book of Mormon"
    if "DOCTRINE" in m:         return "Doctrine and Covenants"
    if "PEARL" in m:            return "Pearl of Great Price"
    return marker.title()


def _canonical_book_name(raw: str) -> str:
    """Match raw name to canonical casing."""
    upper = raw.upper().strip()
    for b in ALL_BOOKS:
        if b.upper() == upper:
            return b
    return raw.strip()


def verses_by_ref(volumes: list[Volume]) -> dict[tuple, Verse]:
    """Build lookup: (book_name_upper, chapter, verse) → Verse"""
    idx = {}
    for vol in volumes:
        for book in vol.books:
            for ch in book.chapters:
                for v in ch.verses:
                    idx[(v.book.upper(), v.chapter, v.verse)] = v
    return idx
