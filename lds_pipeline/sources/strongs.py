"""
Strong's Concordance — verse-accurate Hebrew/Greek word lookup.

Uses the OpenScriptures Morphological Hebrew Bible (OSHB) to get the
exact Strong's numbers for every word in every OT verse, rather than
guessing from English text.

OT: per-book XML from openscriptures/morphhb (GitHub) — one download per book,
    cached forever. Each word's lemma attribute contains the Strong's number.
NT: falls back to a curated Greek map (morphgnt uses SBL lemmas, not Strong's nums).
LDS scriptures: no Strong's tagging available — skipped.

Word selection: load all Strong's numbers for the verse, drop function-word
blocklist entries, then rank by definition richness (longer entry = more
theologically significant content word).
"""

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

CACHE_DIR   = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/strongs")
HEBREW_URL  = "https://raw.githubusercontent.com/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js"
GREEK_URL   = "https://raw.githubusercontent.com/openscriptures/strongs/master/greek/strongs-greek-dictionary.js"
HEBREW_CACHE = CACHE_DIR / "hebrew.json"
GREEK_CACHE  = CACHE_DIR / "greek.json"

# OSHB XML per book — cached as parsed JSON index
OSHB_BASE  = "https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/{abbr}.xml"
OSHB_CACHE = CACHE_DIR / "oshb"

# ── Book name → OSHB file abbreviation ───────────────────────────────────────
_OSHB_ABBR = {
    "GENESIS": "Gen", "EXODUS": "Exod", "LEVITICUS": "Lev",
    "NUMBERS": "Num", "DEUTERONOMY": "Deut", "JOSHUA": "Josh",
    "JUDGES": "Judg", "RUTH": "Ruth", "1 SAMUEL": "1Sam",
    "2 SAMUEL": "2Sam", "1 KINGS": "1Kgs", "2 KINGS": "2Kgs",
    "1 CHRONICLES": "1Chr", "2 CHRONICLES": "2Chr", "EZRA": "Ezra",
    "NEHEMIAH": "Neh", "ESTHER": "Esth", "JOB": "Job",
    "PSALMS": "Ps", "PROVERBS": "Prov", "ECCLESIASTES": "Eccl",
    "SONG OF SOLOMON": "Song", "ISAIAH": "Isa", "JEREMIAH": "Jer",
    "LAMENTATIONS": "Lam", "EZEKIEL": "Ezek", "DANIEL": "Dan",
    "HOSEA": "Hos", "JOEL": "Joel", "AMOS": "Amos", "OBADIAH": "Obad",
    "JONAH": "Jonah", "MICAH": "Mic", "NAHUM": "Nah",
    "HABAKKUK": "Hab", "ZEPHANIAH": "Zeph", "HAGGAI": "Hag",
    "ZECHARIAH": "Zech", "MALACHI": "Mal",
}

# ── Function-word blocklist — Strong's numbers not worth annotating ───────────
# Particles, prepositions, conjunctions, common auxiliaries
_BLOCKLIST = {
    "H853",  # את  direct object marker (untranslated)
    "H3588", # כִּי that, because, for
    "H834",  # אֲשֶׁר which, who, that (relative pronoun)
    "H413",  # אֶל to, toward
    "H5921", # עַל upon, over, against
    "H854",  # אֶת with, near
    "H3807", # לְ preposition prefix
    "H3808", # לֹא not
    "H3605", # כֹּל all, every
    "H3651", # כֵּן so, thus, therefore
    "H5750", # עוֹד yet, still, again
    "H4480", # מִן from, out of
    "H3644", # כְּמוֹ like, as
    "H518",  # אִם if
    "H3588", # כִּי (duplicate)
    "H1571", # גַּם also, even
    "H2050", # particle
    "H1992", # הֵם they (pronoun)
    "H1931", # הוּא he/she/it (pronoun)
    "H2088", # זֶה this
    "H3602", # כָּכָה thus
    "H5704", # עַד until, as far as
    "H0",    # (sometimes used as placeholder)
}


# ── Lexicon loading ───────────────────────────────────────────────────────────

def _download_strongs(url: str, cache_path: Path) -> dict:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    print(f"  Downloading Strong's from {url}...")
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read().decode("utf-8")
    m = re.search(r'=\s*(\{.*\})\s*;?\s*$', raw, re.DOTALL)
    if not m:
        m = re.search(r'(\{.*\})', raw, re.DOTALL)
    if not m:
        raise ValueError(f"Unexpected Strong's format from {url}")
    data = json.loads(m.group(1))
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Cached {len(data):,} entries → {cache_path}")
    return data


_hebrew: dict = None
_greek:  dict = None


def load_hebrew() -> dict:
    global _hebrew
    if _hebrew is None:
        _hebrew = _download_strongs(HEBREW_URL, HEBREW_CACHE)
    return _hebrew


def load_greek() -> dict:
    global _greek
    if _greek is None:
        _greek = _download_strongs(GREEK_URL, GREEK_CACHE)
    return _greek


def lookup(strongs_num: str) -> Optional[dict]:
    if not strongs_num:
        return None
    prefix = strongs_num[0].upper()
    num    = strongs_num[1:]
    if prefix == "H":
        data = load_hebrew()
    elif prefix == "G":
        data = load_greek()
    else:
        return None
    return data.get(strongs_num) or data.get(num)


# ── OSHB verse index ──────────────────────────────────────────────────────────
# Cache: OSHB_CACHE/{abbr}.json  →  {"1:1": ["H7225","H1254",...], ...}

_oshb_loaded: dict[str, dict] = {}   # abbr → {ch:v → [strongs_nums]}

_OSHB_NS = "http://www.bibletechnologies.net/2003/OSIS/namespace"


def _load_oshb_book(book_upper: str) -> dict:
    """Return {chapter:verse → [strongs_nums]} for one OT book. Cached."""
    abbr = _OSHB_ABBR.get(book_upper)
    if not abbr:
        return {}

    if abbr in _oshb_loaded:
        return _oshb_loaded[abbr]

    OSHB_CACHE.mkdir(parents=True, exist_ok=True)
    json_cache = OSHB_CACHE / f"{abbr}.json"

    if json_cache.exists():
        cached = json.loads(json_cache.read_text(encoding="utf-8"))
        # Older runs cached empty verse arrays because the OSIS namespace was wrong.
        if any(cached.values()):
            _oshb_loaded[abbr] = cached
            return _oshb_loaded[abbr]

    # Download and parse XML
    url = OSHB_BASE.format(abbr=abbr)
    print(f"  Downloading OSHB {abbr} from {url}...", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            xml_bytes = r.read()
    except Exception as e:
        print(f"  Warning: could not download OSHB {abbr}: {e}")
        _oshb_loaded[abbr] = {}
        return {}

    index: dict[str, list[str]] = {}
    try:
        root = ET.fromstring(xml_bytes)

        # OSHB uses OSIS milestone model: <verse sID="Gen.1.1"/> ... <verse eID="Gen.1.1"/>
        # Words are siblings of the verse milestone, NOT children.
        # We walk all elements in document order, tracking the current verse.
        current_cv = None
        for el in root.iter():
            tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag

            if tag == 'verse':
                sid = el.get('sID') or el.get('osisID')
                eid = el.get('eID')
                if sid:
                    parts = sid.split('.')
                    if len(parts) == 3:
                        current_cv = f"{int(parts[1])}:{int(parts[2])}"
                        index.setdefault(current_cv, [])
                elif eid:
                    current_cv = None

            elif tag == 'w' and current_cv is not None:
                lemma = el.get('lemma', '')
                for part in lemma.split('/'):
                    part = part.strip()
                    clean = re.sub(r'\s+[a-z]$', '', part)
                    clean = re.sub(r'[a-z]$', '', clean)
                    digits = re.sub(r'\D', '', clean)
                    if digits:
                        index[current_cv].append(f'H{digits}')

    except ET.ParseError as e:
        print(f"  Warning: XML parse error for {abbr}: {e}")
        index = {}

    json_cache.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  Cached OSHB {abbr}: {len(index)} verses")
    _oshb_loaded[abbr] = index
    return index


def _entry_richness(entry: dict) -> int:
    """Score an entry by how much useful content it has."""
    sdef  = entry.get("strongs_def", "") or ""
    kjvd  = entry.get("kjv_def", "") or ""
    deriv = entry.get("derivation", "") or ""
    return len(sdef) + len(kjvd) + len(deriv)


# ── Public API ────────────────────────────────────────────────────────────────

def get_verse_strongs(book: str, chapter: int, verse: int, max_words: int = 4) -> list[dict]:
    """
    Return up to max_words Strong's entries for the most significant words
    in this verse, using the OSHB tagged text (OT only).

    Each entry is a dict:
        strongs_num, lemma, xlit, pron, strongs_def, kjv_def, derivation
    """
    book_upper = book.upper()
    index = _load_oshb_book(book_upper)
    if not index:
        return []

    cv_key = f"{chapter}:{verse}"
    nums   = index.get(cv_key, [])
    if not nums:
        return []

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in nums:
        if n not in seen and n not in _BLOCKLIST:
            seen.add(n)
            unique.append(n)

    # Look up each and rank by definition richness
    candidates = []
    for num in unique:
        entry = lookup(num)
        if entry:
            candidates.append((num, entry, _entry_richness(entry)))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return [{"strongs_num": n, **e} for n, e, _ in candidates[:max_words]]


def format_etymology_html(entry: dict) -> str:
    """Format one Strong's entry as an HTML etymology-entry div."""
    num   = entry.get("strongs_num", "")
    lemma = entry.get("lemma", "")
    xlit  = entry.get("xlit", "")
    pron  = entry.get("pron", "")
    sdef  = (entry.get("strongs_def") or entry.get("kjv_def") or "")[:220]
    deriv = (entry.get("derivation") or "")[:150]

    parts = []
    if lemma: parts.append(f"<span class='etym-lemma'>{lemma}</span>")
    if xlit:  parts.append(f"<span class='etym-xlit'>{xlit}</span>")
    if pron:  parts.append(f"<span class='etym-pron'>({pron})</span>")
    if sdef:  parts.append(f"<span class='etym-def'>{sdef}</span>")
    if deriv: parts.append(f"<span class='etym-deriv'><em>from:</em> {deriv}</span>")

    if not parts:
        return ""

    label = f"{num} · {xlit}" if xlit else num
    return (
        f"<div class='etymology-entry'>"
        f"<span class='etym-word'>{label}</span> — "
        + " · ".join(parts) +
        f"</div>"
    )


# ── NT Strong's via MorphGNT ─────────────────────────────────────────────────

MORPHGNT_BASE  = "https://raw.githubusercontent.com/morphgnt/sblgnt/master/{book}-morphgnt.txt"
MORPHGNT_CACHE = CACHE_DIR / "morphgnt"

# MorphGNT book codes → canonical NT book name (upper)
_MORPHGNT_BOOKS = {
    "MATTHEW": "61-Mt", "MARK": "62-Mk", "LUKE": "63-Lk", "JOHN": "64-Jn",
    "ACTS": "65-Ac", "ROMANS": "66-Ro", "1 CORINTHIANS": "67-1Co",
    "2 CORINTHIANS": "68-2Co", "GALATIANS": "69-Ga", "EPHESIANS": "70-Eph",
    "PHILIPPIANS": "71-Php", "COLOSSIANS": "72-Col",
    "1 THESSALONIANS": "73-1Th", "2 THESSALONIANS": "74-2Th",
    "1 TIMOTHY": "75-1Ti", "2 TIMOTHY": "76-2Ti", "TITUS": "77-Tit",
    "PHILEMON": "78-Phm", "HEBREWS": "79-Heb", "JAMES": "80-Jas",
    "1 PETER": "81-1Pe", "2 PETER": "82-2Pe", "1 JOHN": "83-1Jn",
    "2 JOHN": "84-2Jn", "3 JOHN": "85-3Jn", "JUDE": "86-Jud",
    "REVELATION": "87-Re",
}
# Note: morphgnt file format has 7 tab-separated fields per word:
# bcv  pos  parse  text  word  normalized  lemma
# bcv is BBCCCVVV e.g. 61001001

_morphgnt_loaded: dict = {}   # book_upper → {"ch:v": [strongs_nums]}
_greek_reverse:   dict = None # lemma_lower → strongs_num


def _build_greek_reverse() -> dict:
    """Build reverse map: greek lemma (lowercase) → Strong's number."""
    global _greek_reverse
    if _greek_reverse is not None:
        return _greek_reverse
    data = load_greek()
    rev = {}
    for num, entry in data.items():
        lemma = entry.get("lemma", "")
        if lemma:
            # Normalize: strip accents would be ideal but lowercase is a start
            rev[lemma.lower()] = num
            # Also index without trailing numbers/punctuation
            clean = re.sub(r'[\d,;]+$', '', lemma).strip().lower()
            if clean and clean != lemma.lower():
                rev.setdefault(clean, num)
    _greek_reverse = rev
    return rev


def _load_morphgnt_book(book_upper: str) -> dict:
    """Return {"ch:v": [strongs_nums]} for one NT book. Cached."""
    code = _MORPHGNT_BOOKS.get(book_upper)
    if not code:
        return {}
    if book_upper in _morphgnt_loaded:
        return _morphgnt_loaded[book_upper]

    MORPHGNT_CACHE.mkdir(parents=True, exist_ok=True)
    json_cache = MORPHGNT_CACHE / f"{code}.json"

    if json_cache.exists():
        cached = json.loads(json_cache.read_text(encoding="utf-8"))
        # Older runs parsed chapter/verse boundaries incorrectly from MorphGNT.
        if any(str(key).startswith("1:") for key in cached.keys()):
            _morphgnt_loaded[book_upper] = cached
            return _morphgnt_loaded[book_upper]

    url = MORPHGNT_BASE.format(book=code)
    print(f"  Downloading MorphGNT {code}...", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8")
    except Exception as e:
        print(f"  Warning: could not download MorphGNT {code}: {e}")
        _morphgnt_loaded[book_upper] = {}
        return {}

    rev = _build_greek_reverse()
    index: dict = {}

    # MorphGNT format (7 space-separated fields per word):
    # bcv  part-of-speech  parsing  text  word  normalized  lemma
    # bcv is BBCCCVVV (e.g. 61001001 = Matt 1:1)
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 7:
            continue
        bcv   = parts[0]          # e.g. "040101" for John 1:1
        lemma = parts[6].lower()  # last field

        if len(bcv) == 6:
            ch = str(int(bcv[0:3]))
            v  = str(int(bcv[3:6]))
        elif len(bcv) >= 8:
            ch = str(int(bcv[2:5]))
            v  = str(int(bcv[5:8]))
        else:
            continue
        cv_key = f"{ch}:{v}"

        snum = rev.get(lemma)
        if snum:
            index.setdefault(cv_key, [])
            if snum not in index[cv_key]:
                index[cv_key].append(snum)

    json_cache.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  Cached MorphGNT {code}: {len(index)} verses")
    _morphgnt_loaded[book_upper] = index
    return index


# ── NT fallback (Greek map) ───────────────────────────────────────────────────

OT_BOOKS = set(_OSHB_ABBR.keys())
NT_BOOKS = set(_MORPHGNT_BOOKS.keys())

_GREEK_MAP = {
    "lord": "G2962", "god": "G2316", "holy": "G40", "spirit": "G4151",
    "glory": "G1391", "grace": "G5485", "gospel": "G2098", "faith": "G4102",
    "love": "G26", "mercy": "G1656", "salvation": "G4991", "truth": "G225",
    "light": "G5457", "peace": "G1515", "life": "G2222", "eternal": "G166",
    "logos": "G3056", "baptize": "G907", "repent": "G3340", "church": "G1577",
    "kingdom": "G932", "covenant": "G1242", "blood": "G129", "heart": "G2588",
    "soul": "G5590", "flesh": "G4561", "angel": "G32", "prophet": "G4396",
    "priest": "G2409", "temple": "G3485", "heaven": "G3772", "judgment": "G2920",
    "righteous": "G1342", "hope": "G1680", "servant": "G1401", "king": "G935",
    "word": "G3056", "born": "G1080", "resurrection": "G386", "sin": "G266",
    "forgive": "G863", "commandment": "G1785", "witness": "G3144",
}


def get_verse_strongs_nt(book: str, chapter: int, verse: int,
                          verse_text: str = "", max_words: int = 4) -> list[dict]:
    """
    NT Strong's lookup: uses MorphGNT tagged text when available,
    falls back to keyword matching against the Greek map.
    """
    index = _load_morphgnt_book(book.upper())
    if index:
        cv_key = f"{chapter}:{verse}"
        nums   = index.get(cv_key, [])
        unique = [n for n in dict.fromkeys(nums) if n not in _BLOCKLIST]
        candidates = []
        for num in unique:
            entry = lookup(num)
            if entry:
                candidates.append((num, entry, _entry_richness(entry)))
        candidates.sort(key=lambda x: x[2], reverse=True)
        if candidates:
            return [{"strongs_num": n, **e} for n, e, _ in candidates[:max_words]]

    # Fallback: keyword map
    words = set(re.findall(r'\b[a-z]{3,}\b', verse_text.lower()))
    results, seen = [], set()
    for word, gnum in _GREEK_MAP.items():
        if word in words and gnum not in seen:
            entry = lookup(gnum)
            if entry:
                seen.add(gnum)
                results.append({"strongs_num": gnum, **entry})
        if len(results) >= max_words:
            break
    return results


# ── Backwards-compatible shims (used by pipeline.py) ─────────────────────────

def extract_key_words(verse_text: str, book_name: str, max_words: int = 5) -> list:
    """Shim: returns empty list — pipeline now calls get_verse_strongs directly."""
    return []


def format_etymology_entry(word: str, book_name: str) -> Optional[str]:
    """Shim: no-op — pipeline now calls format_etymology_html directly."""
    return None
