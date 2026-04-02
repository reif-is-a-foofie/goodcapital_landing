#!/usr/bin/env python3
"""
build_donaldson_index.py
========================
Extract Donaldson verse-by-verse commentary → library/donaldson/{book}_{ch}.json

Each file: { "verseNum": { "notes": [...], "words": [...], "quotes": [...] } }

  notes  — Donaldson's own running commentary (full text, not truncated)
  words  — Greek/Hebrew word analyses: [{word, greek, meaning}]
  quotes — Attributed quotes from GC talks, JD, Talmage, etc.
           [{text, attr, type}]  type = "gc" | "jd" | "hoc" | "other"

Run from repo root:
    python3 lds_pipeline/build_donaldson_index.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

REPO    = Path(__file__).parent.parent
CACHE   = REPO / "lds_pipeline" / "cache"
OUT_DIR = REPO / "library" / "donaldson"

MAX_NOTES  = 4
MAX_WORDS  = 8
MAX_QUOTES = 4

BOOK_SLUG = {
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
    "1 Nephi": "1_nephi", "2 Nephi": "2_nephi", "Jacob": "jacob",
    "Enos": "enos", "Jarom": "jarom", "Omni": "omni",
    "Words Of Mormon": "words_of_mormon", "Mosiah": "mosiah",
    "Alma": "alma", "Helaman": "helaman", "3 Nephi": "3_nephi",
    "4 Nephi": "4_nephi", "Mormon": "mormon", "Ether": "ether",
    "Moroni": "moroni",
    "Doctrine And Covenants": "doctrine_and_covenants",
    "Moses": "moses", "Abraham": "abraham",
    "Joseph Smith\u2014Matthew": "joseph_smith_matthew",
    "Joseph Smith\u2014History": "joseph_smith_history",
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


# ── Word study detection ───────────────────────────────────────────────────────
# Matches: "Word (greek). Explanation..." or "The Word (logos). Logos is from..."
_WORD_PAT = re.compile(
    r'^(?:The\s+)?([A-Z][a-zA-Z\s\-\']{1,25}?)\s*\(([a-zA-Z\u0370-\u03FF]{2,20})\)[.,]?\s+(.{30,})',
    re.DOTALL
)

def try_extract_word(para: str):
    """If para is a Greek/Hebrew word study, return dict; else None."""
    m = _WORD_PAT.match(para.strip())
    if not m:
        return None
    word  = m.group(1).strip()
    greek = m.group(2).strip()
    expl  = m.group(3).strip()
    # Reject if greek looks like a city/publisher name (has uppercase or digits)
    if re.search(r'[A-Z]', greek) or re.search(r'\d', greek):
        return None
    # Reject bibliography entries: meaning is a place/publisher
    if re.search(r'(Deseret|Bookcraft|Baker|Doubleday|Cambridge|London|Philadelphia)', expl[:60]):
        return None
    return {"word": word, "greek": greek, "meaning": expl}


# ── Note curation ─────────────────────────────────────────────────────────────
_NOISE_PAT = re.compile(
    r'^(Conference Report|Ensign,|D&C\s+\d|Doc\.?\s*&|^\d{4}\))', re.I
)

def curate_notes(paragraphs: list) -> tuple:
    """Split donaldson paragraphs into (notes, words), curated."""
    seen_notes = set()
    seen_words = set()
    notes = []
    words = []

    for raw in paragraphs:
        p = raw.strip()
        if not p:
            continue

        # Try word study first
        ws = try_extract_word(p)
        if ws:
            key = ws['word'].lower()
            if key not in seen_words:
                seen_words.add(key)
                words.append(ws)
            continue

        # Skip bare noise
        if len(p) < 55:
            continue
        if _NOISE_PAT.match(p):
            continue

        key = p[:80].lower()
        if key in seen_notes:
            continue
        seen_notes.add(key)
        notes.append(p)

    # Most substantive notes first
    notes.sort(key=lambda x: -len(x))
    return notes[:MAX_NOTES], words[:MAX_WORDS]


def curate_quotes(commentary_items: list) -> list:
    """Extract attributed quotes from CommentaryItem objects."""
    seen = set()
    quotes = []

    for c in commentary_items:
        text = (c.text or '').strip()
        attr = (c.attribution or '').strip()

        if len(text) < 50:
            continue

        # Skip misclassified bibliography entries
        if re.search(r':\s*(Deseret|Bookcraft|Baker|Eerdmans|Doubleday|Cambridge)', attr):
            continue
        # Skip if attribution is just a city/publisher
        if re.match(r'^(Salt Lake|New York|Grand Rapids|London|Philadelphia)', attr):
            continue

        key = text[:60].lower()
        if key in seen:
            continue
        seen.add(key)

        quotes.append({
            "text": text,
            "attr": attr,
            "type": c.source_type or 'other',
        })

    quotes.sort(key=lambda x: -len(x['text']))
    return quotes[:MAX_QUOTES]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    source_text = CACHE / "source_text.txt"
    if not source_text.exists():
        print("ERROR: cache/source_text.txt not found.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Parsing Donaldson commentary…")
    from extract.donaldson_parser import parse_donaldson
    raw_text = source_text.read_text(encoding="utf-8")
    volumes  = parse_donaldson(raw_text)

    files_written = total_verses = 0

    for vol in volumes:
        for book in vol.books:
            bname = display_book(book.name)
            slug  = BOOK_SLUG.get(bname, bname.lower().replace(" ", "_"))

            for ch in book.chapters:
                chapter_data: dict = {}

                for v in ch.verses:
                    notes, words = curate_notes(v.donaldson or [])
                    quotes       = curate_quotes(v.commentary or [])

                    if notes or words or quotes:
                        total_verses += 1
                        entry: dict = {}
                        if notes:  entry["notes"]  = notes
                        if words:  entry["words"]  = words
                        if quotes: entry["quotes"] = quotes
                        chapter_data[str(v.verse)] = entry

                if chapter_data:
                    out_path = OUT_DIR / f"{slug}_{ch.number}.json"
                    out_path.write_text(
                        json.dumps(chapter_data, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    files_written += 1

    print(f"\n{files_written} chapter files → {OUT_DIR}/")
    print(f"{total_verses:,} verses have content")

    # Spot-check John 1
    john1 = OUT_DIR / "john_1.json"
    if john1.exists():
        data = json.loads(john1.read_text())
        print(f"\nJohn 1: {len(data)} verses ({john1.stat().st_size // 1024} KB)")
        for vnum in ['1', '3', '5', '9', '14']:
            if vnum not in data: continue
            e = data[vnum]
            print(f"  v{vnum}: {len(e.get('notes',[]))} notes, "
                  f"{len(e.get('words',[]))} words, {len(e.get('quotes',[]))} quotes")
            for w in e.get('words', [])[:3]:
                print(f"    {w['word']} ({w['greek']}): {w['meaning'][:70]}")
            for q in e.get('quotes', [])[:1]:
                print(f"    quote: [{q['type']}] {q['attr'][:60]}")
                print(f"           {q['text'][:80]}")


if __name__ == "__main__":
    main()
