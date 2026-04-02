#!/usr/bin/env python3
"""
build_donaldson_index.py
========================
Extract Donaldson verse-by-verse commentary and write per-chapter JSON files
to library/donaldson/{book_slug}_{chapter}.json

Format (each file):
  {
    "1": ["para1", "para2"],   // verse number → curated paragraphs
    "2": ["para1"],
    ...
  }

Run from repo root:
    python3 lds_pipeline/build_donaldson_index.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

REPO     = Path(__file__).parent.parent
CACHE    = REPO / "lds_pipeline" / "cache"
OUT_DIR  = REPO / "library" / "donaldson"

MAX_PER_VERSE = 4
MIN_LEN       = 55

BOOK_SLUG = {
    # OT
    "Genesis": "genesis", "Exodus": "exodus", "Leviticus": "leviticus",
    "Numbers": "numbers", "Deuteronomy": "deuteronomy", "Joshua": "joshua",
    "Judges": "judges", "Ruth": "ruth", "1 Samuel": "1_samuel",
    "2 Samuel": "2_samuel", "1 Kings": "1_kings", "2 Kings": "2_kings",
    "1 Chronicles": "1_chronicles", "2 Chronicles": "2_chronicles",
    "Ezra": "ezra", "Nehemiah": "nehemiah", "Esther": "esther",
    "Job": "job", "Psalms": "psalms", "Proverbs": "proverbs",
    "Ecclesiastes": "ecclesiastes", "Song Of Solomon": "song_of_solomon",
    "Isaiah": "isaiah", "Jeremiah": "jeremiah", "Lamentations": "lamentations",
    "Ezekiel": "ezekiel", "Daniel": "daniel", "Hosea": "hosea",
    "Joel": "joel", "Amos": "amos", "Obadiah": "obadiah",
    "Jonah": "jonah", "Micah": "micah", "Nahum": "nahum",
    "Habakkuk": "habakkuk", "Zephaniah": "zephaniah", "Haggai": "haggai",
    "Zechariah": "zechariah", "Malachi": "malachi",
    # NT
    "Matthew": "matthew", "Mark": "mark", "Luke": "luke", "John": "john",
    "Acts": "acts", "Romans": "romans", "1 Corinthians": "1_corinthians",
    "2 Corinthians": "2_corinthians", "Galatians": "galatians",
    "Ephesians": "ephesians", "Philippians": "philippians",
    "Colossians": "colossians", "1 Thessalonians": "1_thessalonians",
    "2 Thessalonians": "2_thessalonians", "1 Timothy": "1_timothy",
    "2 Timothy": "2_timothy", "Titus": "titus", "Philemon": "philemon",
    "Hebrews": "hebrews", "James": "james", "1 Peter": "1_peter",
    "2 Peter": "2_peter", "1 John": "1_john", "2 John": "2_john",
    "3 John": "3_john", "Jude": "jude", "Revelation": "revelation",
    # BoM
    "1 Nephi": "1_nephi", "2 Nephi": "2_nephi", "Jacob": "jacob",
    "Enos": "enos", "Jarom": "jarom", "Omni": "omni",
    "Words Of Mormon": "words_of_mormon", "Mosiah": "mosiah",
    "Alma": "alma", "Helaman": "helaman", "3 Nephi": "3_nephi",
    "4 Nephi": "4_nephi", "Mormon": "mormon", "Ether": "ether",
    "Moroni": "moroni",
    # DC/PGP
    "Doctrine And Covenants": "doctrine_and_covenants",
    "Moses": "moses", "Abraham": "abraham",
    "Joseph Smith—Matthew": "joseph_smith_matthew",
    "Joseph Smith—History": "joseph_smith_history",
    "Articles Of Faith": "articles_of_faith",
}

BOOK_DISPLAY = {
    "Doctrine And Covenants": "Doctrine And Covenants",
    "Joseph Smith Matthew":   "Joseph Smith\u2014Matthew",
    "Joseph Smith History":   "Joseph Smith\u2014History",
}


def display_book(raw: str) -> str:
    title = raw.replace("_", " ").title()
    return BOOK_DISPLAY.get(title, title)


def is_noise(para: str) -> bool:
    p = para.strip()
    if len(p) < MIN_LEN:
        return True
    if re.match(r'^[A-Za-z\s]+\([^)]+\)\s+[a-z]', p) and '.' not in p and len(p) < 150:
        return True
    if re.match(r'^(Conference Report|Ensign|D&C|Doc\.?\s*&?\s*Cov)', p):
        return True
    return False


def curate(paragraphs: list) -> list:
    seen = set()
    candidates = []
    for raw in paragraphs:
        p = raw.strip()
        if is_noise(p):
            continue
        key = p[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(p)
    candidates.sort(key=lambda x: -len(x))
    return candidates[:MAX_PER_VERSE]


def main():
    source_text = CACHE / "source_text.txt"
    if not source_text.exists():
        print("ERROR: cache/source_text.txt not found.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Parsing Donaldson commentary…")
    from extract.donaldson_parser import parse_donaldson
    raw_text = source_text.read_text(encoding="utf-8")
    volumes = parse_donaldson(raw_text)

    files_written = total_with_notes = 0

    for vol in volumes:
        for book in vol.books:
            bname = display_book(book.name)
            slug  = BOOK_SLUG.get(bname, bname.lower().replace(" ", "_"))

            for ch in book.chapters:
                chapter_data: dict[str, list] = {}
                for v in ch.verses:
                    paras = curate(v.donaldson or [])
                    if paras:
                        total_with_notes += 1
                        chapter_data[str(v.verse)] = paras

                if chapter_data:
                    out_path = OUT_DIR / f"{slug}_{ch.number}.json"
                    out_path.write_text(
                        json.dumps(chapter_data, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    files_written += 1

    print(f"\n{files_written} chapter files → {OUT_DIR}/")
    print(f"{total_with_notes:,} verses have curated Donaldson notes")

    # Quick check: John 1
    john1 = OUT_DIR / "john_1.json"
    if john1.exists():
        data = json.loads(john1.read_text())
        print(f"\nJohn 1: {len(data)} verses with notes ({john1.stat().st_size // 1024} KB)")
        for vnum in sorted(data.keys(), key=int)[:5]:
            print(f"  v{vnum}: {len(data[vnum])} paras, first 100: {data[vnum][0][:100]}")


if __name__ == "__main__":
    main()
