"""
Parser for the Lee Donaldson LDS Scriptures compilation.

Actual format (confirmed from source text):
  Book Ch:V            ← standalone line, primary verse delimiter
                       ← blank line
  {num} [¶] {KJV text} ← verse text line (may start with ¶)
                       ← blank line
  JST: {text}          ← optional JST variant paragraph
  {commentary para}    ← one or more Donaldson commentary paragraphs
  ...                  ← (until the next Book Ch:V line)

  Also present:
  - Page headers: "12/23/2010 © ... Page N"  — filtered out
  - Book intro paragraphs before chapter 1   — filtered
  - Chapter summaries ("Chapter 1 — ...")    — filtered
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class WordStudy:
    word:      str
    original:  str
    meaning:   str


@dataclass
class CommentaryItem:
    text:        str
    attribution: str
    source_type: str   # 'jd', 'hoc', 'gc', 'other'


@dataclass
class Verse:
    book:         str
    chapter:      int
    verse:        int
    volume:       str
    text:         str                         # KJV scripture text
    jst:          Optional[str]               # JST variant
    word_studies: list[WordStudy]             = field(default_factory=list)
    commentary:   list[CommentaryItem]        = field(default_factory=list)
    # Donaldson inline commentary (raw paragraphs, kept as their own source)
    donaldson:    list[str]                   = field(default_factory=list)
    raw:          str                         = ""


@dataclass
class Chapter:
    book:     str
    number:   int
    volume:   str
    heading:  str
    verses:   list[Verse] = field(default_factory=list)


@dataclass
class Book:
    name:     str
    volume:   str
    chapters: list[Chapter] = field(default_factory=list)


@dataclass
class Volume:
    name:  str
    books: list[Book] = field(default_factory=list)


# ── Book / volume maps ────────────────────────────────────────────────────────

OT_BOOKS = [
    "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges",
    "Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles",
    "Ezra","Nehemiah","Esther","Job","Psalms","Proverbs","Ecclesiastes",
    "Song of Solomon","Isaiah","Jeremiah","Lamentations","Ezekiel","Daniel",
    "Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk",
    "Zephaniah","Haggai","Zechariah","Malachi",
]
NT_BOOKS = [
    "Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians",
    "2 Corinthians","Galatians","Ephesians","Philippians","Colossians",
    "1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus",
    "Philemon","Hebrews","James","1 Peter","2 Peter","1 John","2 John",
    "3 John","Jude","Revelation",
]
BOM_BOOKS = [
    "1 Nephi","2 Nephi","Jacob","Enos","Jarom","Omni","Words of Mormon",
    "Mosiah","Alma","Helaman","3 Nephi","4 Nephi","Mormon","Ether","Moroni",
]
PGP_BOOKS = ["Moses","Abraham","Joseph Smith—Matthew","Joseph Smith—History","Articles of Faith"]

ALL_BOOKS = OT_BOOKS + NT_BOOKS + BOM_BOOKS + ["Doctrine and Covenants"] + PGP_BOOKS

BOOK_TO_VOLUME: dict[str, str] = {}
for _b in OT_BOOKS:   BOOK_TO_VOLUME[_b.upper()] = "Old Testament"
for _b in NT_BOOKS:   BOOK_TO_VOLUME[_b.upper()] = "New Testament"
for _b in BOM_BOOKS:  BOOK_TO_VOLUME[_b.upper()] = "Book of Mormon"
BOOK_TO_VOLUME["DOCTRINE AND COVENANTS"] = "Doctrine and Covenants"
for _b in PGP_BOOKS:  BOOK_TO_VOLUME[_b.upper()] = "Pearl of Great Price"

# ── Regexes ───────────────────────────────────────────────────────────────────

# Standalone verse-reference line: "Genesis 1:1"  (full line, nothing else)
_SORTED_BOOKS = sorted(ALL_BOOKS, key=len, reverse=True)
_VERSE_REF_RE = re.compile(
    r'^(' + '|'.join(re.escape(b) for b in _SORTED_BOOKS) + r')\s+(\d+):(\d+)\s*$',
    re.IGNORECASE,
)

# Verse text: line starting with a number (and optional ¶)
_VERSE_TEXT_RE = re.compile(r'^(\d{1,3})\s+¶?\s*(.*)', re.DOTALL)

# JST marker
_JST_RE = re.compile(r'^\s*JST\s*:', re.IGNORECASE)

# Page-header noise
_PAGE_RE = re.compile(r'©.*?Page\s+\d+', re.IGNORECASE)

# Attribution patterns for commentary classification
_ATTRIBUTION_RE = re.compile(
    r'\(([^()]{10,200}(?:JD|Journal|Conference|Ensign|History|Teachings|WJS|'
    r'Discourses|Discourse|Doctrine|McConkie|Maxwell|Packer|Nelson|Kimball|'
    r'Hunter|Hinckley|Smith|Young|Taylor|Woodruff|Snow|Grant|Lee|Benson|'
    r'Monson|Eyring|Uchtdorf|Holland|Oaks|Bednar|Cook|Christofferson|'
    r'Andersen|Rasband|Stevenson|Renlund|Soares)[^()]{0,100})\)',
    re.IGNORECASE,
)

# Hebrew word study: word [transliteration meaning]
_WORD_STUDY_RE = re.compile(r'\b([a-zA-Z\-\']{3,})\s+\[([^\]]+)\]')


def _canonical_book(raw: str) -> str:
    u = raw.strip().upper()
    for b in ALL_BOOKS:
        if b.upper() == u:
            return b
    return raw.strip()


def _classify_attribution(attr: str) -> str:
    a = attr.lower()
    if 'jd' in a or 'journal of disc' in a:        return 'jd'
    if 'history of the church' in a or ' hc ' in a: return 'hoc'
    if 'conference report' in a or 'ensign' in a:  return 'gc'
    return 'other'


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_donaldson(text: str) -> list[Volume]:
    """
    Parse the full Donaldson compilation text into structured Volume objects.

    Strategy: use "Book Ch:V" standalone lines as the primary delimiters.
    Collect all text between two such lines as one verse block.
    """
    lines = text.split('\n')

    # Pass 1: locate every standalone verse-reference line
    ref_positions: list[tuple[int, str, int, int]] = []   # (line_idx, book, ch, v)
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        m = _VERSE_REF_RE.match(stripped)
        if m:
            book = _canonical_book(m.group(1))
            ch   = int(m.group(2))
            v    = int(m.group(3))
            ref_positions.append((idx, book, ch, v))

    # Pass 2: build structure
    volumes:  dict[str, Volume] = {}
    books:    dict[str, Book]   = {}
    chapters: dict[tuple, Chapter] = {}   # (book_upper, ch) → Chapter

    def get_volume(name: str) -> Volume:
        if name not in volumes:
            volumes[name] = Volume(name=name)
        return volumes[name]

    def get_book(book_name: str) -> Book:
        key = book_name.upper()
        if key not in books:
            vol_name = BOOK_TO_VOLUME.get(key, "Old Testament")
            vol = get_volume(vol_name)
            b = Book(name=book_name, volume=vol_name)
            vol.books.append(b)
            books[key] = b
        return books[key]

    def get_chapter(book_name: str, ch_num: int) -> Chapter:
        key = (book_name.upper(), ch_num)
        if key not in chapters:
            bk = get_book(book_name)
            vol_name = BOOK_TO_VOLUME.get(book_name.upper(), "Old Testament")
            ch = Chapter(book=book_name, number=ch_num, volume=vol_name, heading="")
            bk.chapters.append(ch)
            chapters[key] = ch
        return chapters[key]

    for i, (ref_idx, book, ch_num, v_num) in enumerate(ref_positions):
        # Collect raw lines of this verse block (up to next reference)
        next_ref_idx = ref_positions[i + 1][0] if i + 1 < len(ref_positions) else len(lines)
        block_lines = lines[ref_idx + 1 : next_ref_idx]

        verse = _parse_verse_block(v_num, block_lines, book, ch_num)
        chap = get_chapter(book, ch_num)
        chap.verses.append(verse)

    # Return in canonical order
    order = ["Old Testament", "New Testament", "Book of Mormon",
             "Doctrine and Covenants", "Pearl of Great Price"]
    return [volumes[n] for n in order if n in volumes]


# ── Verse block parser ────────────────────────────────────────────────────────

def _parse_verse_block(verse_num: int, block_lines: list[str],
                       book: str, chapter: int) -> Verse:
    """
    Given the lines between two reference markers, extract:
      - KJV scripture text
      - JST variant
      - Donaldson commentary paragraphs (the new source)
      - Word studies
      - Attributed commentary items (classified by source)
    """
    # Split block into paragraphs (blank-line separated)
    paragraphs: list[str] = []
    current: list[str] = []
    for line in block_lines:
        stripped = line.strip()
        # Skip page noise
        if _PAGE_RE.search(stripped):
            continue
        if stripped:
            current.append(stripped)
        else:
            if current:
                paragraphs.append(' '.join(current))
                current = []
    if current:
        paragraphs.append(' '.join(current))

    kjv_text  = ""
    jst_text  = None
    commentary_paras: list[str] = []

    for para in paragraphs:
        # Is this the verse text line?
        m = _VERSE_TEXT_RE.match(para)
        if m and int(m.group(1)) == verse_num and not kjv_text:
            kjv_text = m.group(2).strip()
            continue

        # Is this a JST block?
        if _JST_RE.match(para):
            jst_text = _JST_RE.sub('', para).strip()
            continue

        # Otherwise it's Donaldson commentary
        if para:
            commentary_paras.append(para)

    # Extract structured word studies and attributed items from commentary
    combined = ' '.join(commentary_paras)
    word_studies    = _extract_word_studies(combined)
    attributed_items = _extract_commentary(combined)

    volume = BOOK_TO_VOLUME.get(book.upper(), "Old Testament")
    return Verse(
        book=book,
        chapter=chapter,
        verse=verse_num,
        volume=volume,
        text=kjv_text,
        jst=jst_text,
        word_studies=word_studies,
        commentary=attributed_items,
        donaldson=commentary_paras,
        raw=' '.join(block_lines),
    )


def _extract_word_studies(text: str) -> list[WordStudy]:
    studies = []
    seen = set()
    for m in _WORD_STUDY_RE.finditer(text):
        word    = m.group(1)
        content = m.group(2).strip()
        parts   = content.split(None, 1)
        original = parts[0].rstrip(':') if parts else content
        meaning  = parts[1] if len(parts) > 1 else ""

        if word.upper() == word:           # skip all-caps noise
            continue
        if word.lower() in seen:           # deduplicate
            continue
        if ':' not in content:              # require "transliteration: meaning" colon
            continue
        if re.search(r':\s*\d', content):   # scripture ref colon like "Matthew 13:33"
            continue
        if re.match(r'^\d', original):     # year/number: [1977]
            continue
        if len(original) < 2 or len(original) > 25:
            continue
        if not re.search(r'[a-z]', original):  # all caps or symbols
            continue

        seen.add(word.lower())
        studies.append(WordStudy(word=word, original=original, meaning=meaning))
    return studies[:6]


def _extract_commentary(text: str) -> list[CommentaryItem]:
    items = []
    for m in _ATTRIBUTION_RE.finditer(text):
        attr_text = m.group(1).strip()
        start = max(0, m.start() - 400)
        ctx   = text[start : m.start()].strip()
        sentences = re.split(r'(?<=[.!?])\s+', ctx)
        quote = ' '.join(sentences[-3:]).strip()
        if len(quote) > 30:
            items.append(CommentaryItem(
                text=quote,
                attribution=attr_text,
                source_type=_classify_attribution(attr_text),
            ))
    return items


# ── Utility ───────────────────────────────────────────────────────────────────

def verses_by_ref(volumes: list[Volume]) -> dict[tuple, Verse]:
    """Build (BOOK_UPPER, chapter, verse) → Verse index."""
    idx = {}
    for vol in volumes:
        for book in vol.books:
            for ch in book.chapters:
                for v in ch.verses:
                    idx[(v.book.upper(), v.chapter, v.verse)] = v
    return idx
