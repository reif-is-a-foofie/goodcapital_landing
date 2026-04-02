#!/usr/bin/env python3
"""
build_donaldson_index.py
========================
Extract Donaldson verse-by-verse commentary → library/donaldson/{book}_{ch}.json

Each file: { "verseNum": { "notes": [...], "words": [...], "quotes": [...] } }

  notes  — Donaldson's own running commentary (full text, not truncated)
  words  — Greek/Hebrew word analyses: [{word, greek, meaning}]
  quotes — Attributed quotes, fully structured:
           [{text, speaker, source, date, ref, type, attr}]
           type = "gc" | "jd" | "hoc" | "other"

Quote extraction: each paragraph in Donaldson's commentary that ends with
(attribution text) is treated as a complete quote. The attribution is parsed
into structured fields rather than stored as a flat string.

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
MAX_QUOTES = 6   # more room now that we have clean, complete quotes

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


# ── Word study detection ────────────────────────────────────────────────────
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
    if re.search(r'[A-Z]', greek) or re.search(r'\d', greek):
        return None
    if re.search(r'(Deseret|Bookcraft|Baker|Doubleday|Cambridge|London|Philadelphia)', expl[:60]):
        return None
    return {"word": word, "greek": greek, "meaning": expl}


# ── Attribution parser ──────────────────────────────────────────────────────

# Detect paragraph-ending attribution: (text without nested parens, 10-300 chars)
_ATTR_END_RE = re.compile(r'\(([^()]{10,300})\)\s*$')

# Page noise in attributions
_PAGE_NOISE_RE = re.compile(r'©.*?Page\s+\d+', re.IGNORECASE)

# Known publisher/place patterns that mean this is a bibliography entry, not a quote
_BIBREF_RE = re.compile(
    r'^(Salt Lake City|New York|Grand Rapids|London|Philadelphia|Chicago|'
    r'Deseret Book|Bookcraft|Baker|Eerdmans|Doubleday|Cambridge University)',
    re.IGNORECASE
)

# Year pattern
_YEAR_RE = re.compile(r'\b(1[6-9]\d\d|20[012]\d)\b')

# Month + year  e.g. "Apr. 2000" or "April 1914"
_DATE_RE = re.compile(
    r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\.?\s+(1[6-9]\d\d|20[012]\d)\b'
)

# Journal of Discourses  e.g. "JD 17:143" or "JD Vol 17:143"
_JD_RE = re.compile(r'\bJD\s+(?:Vol\.?\s*)?(\d+):(\d+)', re.IGNORECASE)

# History of Church  e.g. "HC 3:387"
_HC_RE = re.compile(r'\bH\.?C\.?\s+(\d+):', re.IGNORECASE)


def _classify_type(attr: str) -> str:
    a = attr.lower()
    if re.search(r'\bjd\b', a) or 'journal of disc' in a:
        return 'jd'
    if 'history of the church' in a or re.search(r'\bhc\s+\d', a):
        return 'hoc'
    if 'conference report' in a or re.search(r'\bensign\b', a):
        return 'gc'
    return 'other'


def parse_attribution(raw: str) -> dict:
    """
    Parse an attribution string into structured fields.

    Handles patterns like:
      "Gordon B. Hinckley, Teachings of Gordon B. Hinckley, p.281"
      "Russell M. Nelson, in Conference Report, Apr. 2000, 106; or Ensign, May 2000, 85"
      "Brigham Young, JD 17:143."
      "Joseph Smith, Discourse of 7 April 1844, recorded by Samuel W. Richards; WJS, 361."
      "Bruce R. McConkie, 'Christ and the Creation,' Ensign, June 1982."
    """
    raw = raw.strip().rstrip('.')

    # Extract date
    date = ""
    dm = _DATE_RE.search(raw)
    if dm:
        date = dm.group(0)
    else:
        ym = _YEAR_RE.search(raw)
        if ym:
            date = ym.group(0)

    # JD volume/page
    jd_vol = jd_page = ""
    jdm = _JD_RE.search(raw)
    if jdm:
        jd_vol  = jdm.group(1)
        jd_page = jdm.group(2)

    # Source type
    src_type = _classify_type(raw)

    # Speaker: first comma-delimited token that looks like a person name
    # (starts with a capital, contains a space, no digits, not "in ")
    speaker = ""
    parts = [p.strip() for p in raw.split(',')]
    if parts:
        candidate = parts[0].lstrip('in ').strip()
        # A person name: has at least one space, starts uppercase, no digits
        if (re.match(r'^[A-Z]', candidate)
                and ' ' in candidate
                and not re.search(r'\d', candidate)
                and len(candidate.split()) <= 6):
            speaker = candidate

    # Source: the main publication/book
    source = ""
    if jdm:
        source = f"Journal of Discourses {jd_vol}:{jd_page}"
    elif 'conference report' in raw.lower():
        source = "Conference Report"
    elif re.search(r'\bensign\b', raw, re.I) and 'conference report' not in raw.lower():
        source = "Ensign"
    elif 'teachings of the prophet' in raw.lower():
        source = "Teachings of the Prophet Joseph Smith"
    elif 'history of the church' in raw.lower() or re.search(r'\bhc\s+\d', raw, re.I):
        source = "History of the Church"
    elif 'words of joseph smith' in raw.lower() or re.search(r'\bwjs\b', raw, re.I):
        source = "Words of Joseph Smith"
    elif 'doctrines of salvation' in raw.lower():
        source = "Doctrines of Salvation"
    elif 'mormon doctrine' in raw.lower():
        source = "Mormon Doctrine"
    elif 'millennial star' in raw.lower():
        source = "Millennial Star"
    elif 'times and seasons' in raw.lower():
        source = "Times and Seasons"
    else:
        # Try: second or third comma token, skip short tokens and "in"
        for p in parts[1:]:
            p = p.strip().strip('"\'')
            if len(p) > 8 and not re.match(r'^(in|p\.|pp\.|vol|no|page)', p, re.I) and not re.match(r'^\d', p):
                source = p
                break

    # ref: page/volume info
    ref = ""
    if jdm:
        ref = f"Vol. {jd_vol}, p. {jd_page}"
    else:
        pm = re.search(r'p+\.\s*(\d[\d\-]+)', raw, re.I)
        if pm:
            ref = "p. " + pm.group(1)

    return {
        "speaker": speaker,
        "source":  source,
        "date":    date,
        "ref":     ref,
        "type":    src_type,
        "attr":    raw,   # keep raw for fallback display
    }


# ── Reference tools that should never appear as quote speakers ───────────────
# These are lexicons, commentaries, and study tools — not people giving talks
# or writing books about scripture. Page-header splits in the PDF cause their
# word-study paragraphs to appear as "quotes" ending with "(Robertson's NT...)"
_REFERENCE_TOOL_RE = re.compile(
    r"Robertson'?s?\s*(NT\s*Word\s*Pictures?|New\s*Testament)",
    re.IGNORECASE
)
_REFERENCE_TOOLS = {
    "robertson", "robertson's nt word pictures", "robertson's new testament",
    "bdb", "brown-driver-briggs", "tdnt", "theological dictionary",
    "bdag", "thayer", "gesenius", "strong's", "strongs",
    "new harper's bible dictionary", "harper's bible dictionary",
    "vine's expository", "vines expository",
    "interlinear", "septuagint", "lxx",
    "old testament student manual", "new testament student manual",
    "institute manual", "ces institute",
}

def _is_reference_tool(attr_raw: str) -> bool:
    """Return True if this attribution is a reference/lexicon tool, not a person."""
    if _REFERENCE_TOOL_RE.search(attr_raw):
        return True
    lower = attr_raw.lower()
    for tool in _REFERENCE_TOOLS:
        if tool in lower:
            return True
    return False


# ── Quote extraction from raw paragraphs ────────────────────────────────────

def extract_quotes_from_paragraphs(paragraphs: list) -> list:
    """
    Extract complete attributed quotes from raw Donaldson commentary paragraphs.

    Each paragraph that ends with (attribution) is a quote. We take the FULL
    paragraph text as the quote body — not a 400-char window.
    """
    seen = set()
    quotes = []

    for para in paragraphs:
        p = para.strip()
        if not p:
            continue

        # Must end with (attribution)
        m = _ATTR_END_RE.search(p)
        if not m:
            continue

        attr_raw = m.group(1).strip()

        # Skip page-header noise that leaked into attribution
        if _PAGE_NOISE_RE.search(attr_raw):
            continue
        # Skip scripture references like "(John 1:3)"
        if re.match(r'^[A-Z][a-z]+\s+\d+:\d+', attr_raw):
            continue
        # Skip pure copyright/publisher lines
        if _BIBREF_RE.match(attr_raw):
            continue
        # Skip reference tools / lexicons — not attributed quotes
        if _is_reference_tool(attr_raw):
            continue
        # Skip very short attribution-like things that are just parenthetical notes
        if len(attr_raw) < 12:
            continue
        # Must look like it has a person or publication name (contains a capital word)
        if not re.search(r'[A-Z][a-z]', attr_raw):
            continue

        # Quote text is everything before the final attribution marker
        text = p[:m.start()].strip()
        # Strip surrounding quotation marks from the quote text
        text = re.sub(r'^["\u201c\u201d\u2018\u2019"\']+', '', text).strip()
        text = re.sub(r'["\u201c\u201d\u2018\u2019"\']+$', '', text).strip()

        # Must start with a capital (complete sentence, not mid-sentence fragment)
        if not text or not text[0].isupper():
            continue
        # Must look like it starts a real sentence: at least one more word after the first
        if len(text.split()) < 6:
            continue
        if len(text) < 40:
            continue

        key = text[:60].lower()
        if key in seen:
            continue
        seen.add(key)

        parsed = parse_attribution(attr_raw)
        quotes.append({
            "text":    text,
            "speaker": parsed["speaker"],
            "source":  parsed["source"],
            "date":    parsed["date"],
            "ref":     parsed["ref"],
            "type":    parsed["type"],
            "attr":    parsed["attr"],
        })

    # Prefer GC talks and JD, then by length
    def sort_key(q):
        priority = {"gc": 0, "jd": 1, "hoc": 2, "other": 3}
        return (priority.get(q["type"], 3), -len(q["text"]))

    quotes.sort(key=sort_key)
    return quotes[:MAX_QUOTES]


# ── Note curation ────────────────────────────────────────────────────────────
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

        # Skip paragraphs that are entirely attributed quotes
        # (those end with a (citation) — they go into quotes, not notes)
        if _ATTR_END_RE.search(p):
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

    notes.sort(key=lambda x: -len(x))
    return notes[:MAX_NOTES], words[:MAX_WORDS]


# ── Main ─────────────────────────────────────────────────────────────────────
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
                    quotes       = extract_quotes_from_paragraphs(v.donaldson or [])

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
            for q in e.get('quotes', [])[:2]:
                spk  = q.get('speaker','?')
                src  = q.get('source','?')
                date = q.get('date','')
                print(f"    [{q['type']}] {spk} · {src} {date}")
                print(f"           {q['text'][:90]}")


if __name__ == "__main__":
    main()
