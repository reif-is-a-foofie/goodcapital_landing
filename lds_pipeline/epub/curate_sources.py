"""
Source curation logic for per-verse connected passages display.

Rules applied before rendering:
  1. Score floor    — drop anything below MIN_SCORE (TF-IDF noise)
  2. Self-filter    — drop Donaldson entries that are *about this verse*
                      (already shown in the Donaldson block)
  3. Source cap     — keep at most MAX_PER_SOURCE matches from any one corpus
  4. Display cap    — hard ceiling of DISPLAY_MAX total entries
  5. Label cleanup  — normalize source labels for epub display

Score bands (used for dot-rating in CSS):
  ≥ 0.50  →  5 dots  very strong (direct quote / near-exact phrase)
  ≥ 0.40  →  4 dots  strong
  ≥ 0.30  →  3 dots  moderate
  ≥ 0.20  →  2 dots  weak
  <  0.20 →  never shown
"""

import re

MIN_SCORE      = 0.25
MAX_PER_SOURCE = 2
DISPLAY_MAX    = 5

SOURCE_LABELS = {
    "journal_of_discourses": "Journal of Discourses",
    "sefaria":               "Sefaria",
    "general_conference":    "General Conference",
    "gutenberg_lds":         "Early LDS Writings",
    "church_fathers":        "Church Fathers",
    "ancient_texts":         "Ancient Texts",
    "history_of_church":     "History of the Church",
    "joseph_smith_papers":   "Joseph Smith Papers",
    "donaldson":             "Donaldson Commentary",
    "times_and_seasons":     "Times and Seasons",
    "millennial_star":       "Millennial Star",
    "pioneer_journals":      "Pioneer Journals",
    "pseudepigrapha":        "Pseudepigrapha",
    "apocrypha":             "LXX Apocrypha",
    "nag_hammadi":           "Nag Hammadi",
    "dead_sea_scrolls":      "Dead Sea Scrolls",
    "bh_roberts":            "B.H. Roberts",
    "nibley":                "Nibley",
    "nauvoo_theology":       "Nauvoo Theology",
    "jst":                   "Joseph Smith Translation",
}


def score_to_dots(score: float) -> int:
    """Return 1–5 dot rating for a relevance score."""
    if score >= 0.50: return 5
    if score >= 0.40: return 4
    if score >= 0.30: return 3
    if score >= 0.20: return 2
    return 1


def _is_prose(text: str) -> bool:
    """
    Return True if the text is genuine prose worth displaying.
    Rejects headers, OCR fragments, and bare scripture citations.

    Signals of a non-prose passage:
      - Fewer than 20 words (bare citation or header)
      - High uppercase ratio: if >40% of alpha chars are uppercase it's
        a headline/masthead, not commentary
      - No sentence-terminal punctuation (no . ! ?) — not a complete thought
      - All non-empty lines are uppercase — newspaper column header pattern
    """
    if not text or not text.strip():
        return False

    words = text.split()
    if len(words) < 8:
        return False

    alpha = [c for c in text if c.isalpha()]
    if alpha:
        upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
        if upper_ratio > 0.40:
            return False

    if not re.search(r'[.!?]', text):
        return False

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines and all(ln == ln.upper() for ln in lines):
        return False

    return True


def _is_self_ref(label: str, book: str, chapter: int, verse: int) -> bool:
    """Return True if a Donaldson label refers to this exact verse."""
    pattern = rf"Donaldson on {re.escape(book)}\s+{chapter}:{verse}\b"
    return bool(re.search(pattern, label, re.IGNORECASE))


def _clean_label(raw_label: str) -> str:
    """
    Clean a raw corpus label into a short human-readable reference.

    Examples:
      'JD Vol 10'                            → 'Vol. 10'
      'Donaldson on Isaiah 3:2'              → 'Cross-ref · Isaiah 3:2'
      'GC: general_conference_2011_10_...'   → 'October 2011'
      'Millennial Star: millennial_star_abbyy' → '1840–1859'
      'Sefaria: Talmud: Chagigah 12a:16'    → 'Chagigah 12a:16'
    """
    label = raw_label.strip()

    if label.startswith("Donaldson on "):
        ref = label[len("Donaldson on "):]
        return f"Cross-ref · {ref}"

    if label.startswith("JD Vol "):
        vol = label[len("JD Vol "):]
        return f"Vol. {vol}"

    if label.startswith("GC: "):
        slug = label[4:]
        m = re.search(r'(\d{4})_(04|10)', slug)
        if m:
            month = "April" if m.group(2) == "04" else "October"
            return f"{month} {m.group(1)}"
        return slug.replace("general_conference_", "").replace("_", " ").title()[:40]

    if "millennial_star_abbyy" in label or "millennial_star" in label.lower():
        return "1840–1859"

    if "times_and_seasons" in label.lower():
        return "1839–1846"

    if "wilford_woodruff" in label.lower():
        return "Wilford Woodruff Journals"

    if "lucy_mack_smith" in label.lower():
        return "Lucy Mack Smith"

    # Any "Category: ..." prefix — strip to get the actual book+ref
    m = re.match(r'(?:Talmud|Kabbalah|Midrash|Chasidut|Quoting Commentary|Commentary|Targum|Musar|Responsa|Halakha|Jewish Law|Liturgy)[:\s]+(.+)', label)
    if m:
        return m.group(1).strip()[:60]

    if ": " in label:
        _, ref = label.split(": ", 1)
        return ref[:60]

    return label[:60]


_BIBLE_BOOKS = re.compile(
    r'\b(Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|'
    r'Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalms|Proverbs|'
    r'Ecclesiastes|Isaiah|Jeremiah|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|'
    r'Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|'
    r'Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|'
    r'Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|'
    r'James|Peter|Jude|Revelation)\b.*$'
)


def _sefaria_book_name(raw_label: str) -> str:
    """
    Extract just the book/source name from a raw Sefaria label.

    Examples:
      'Commentary: Rashi on Genesis 24:37:1'       → 'Rashi'
      'Kabbalah: Zohar, Beshalach 28:401'           → 'Zohar'
      'Targum: Onkelos Genesis 37:15'               → 'Onkelos'
      'Targum: Targum Jonathan on Genesis 24:40'    → 'Targum Jonathan'
      'Midrash: Pirkei DeRabbi Eliezer 54:2'        → 'Pirkei DeRabbi Eliezer'
      'Quoting Commentary: Covenant...; Genesis;..' → 'Covenant and Conversation'
    """
    label = raw_label.strip()
    # Strip category prefix
    m = re.match(r'^[^:]+:\s+(.+)', label)
    body = m.group(1) if m else label

    # Semicolons separate title from book/section — take first part
    if ';' in body:
        body = body.split(';')[0].strip()

    # "X on BookName Ref" → take X
    m = re.match(r'^(.+?)\s+on\s+\w', body)
    if m:
        return m.group(1).strip()

    # "X, SectionName Ref" → take X
    m = re.match(r'^([^,]+),', body)
    if m:
        return m.group(1).strip()

    # Strip trailing Bible book name + ref (e.g. "Onkelos Genesis 37:15")
    name = _BIBLE_BOOKS.sub('', body).strip()
    if not name:
        name = body
    # Strip trailing verse refs (digits, colons, hyphens at end)
    name = re.sub(r'[\s\d.:–-]+$', '', name).strip()
    return name[:40]


def curate(matches: list[dict], book: str, chapter: int, verse: int) -> list[dict]:
    """
    Apply all curation rules to a raw matches list from a correlation file.
    Returns a filtered, cleaned list ready for rendering.
    """
    results = []
    source_counts: dict[str, int] = {}

    for m in sorted(matches, key=lambda x: x["score"], reverse=True):
        score = m.get("score", 0)

        if score < MIN_SCORE:
            continue

        if not _is_prose(m.get("text", "")):
            continue

        source = m.get("source", "")
        label  = m.get("label", "")

        if source == "donaldson" and _is_self_ref(label or "", book, chapter, verse):
            continue

        count = source_counts.get(source, 0)
        if count >= MAX_PER_SOURCE:
            continue
        source_counts[source] = count + 1

        if source == "sefaria":
            source_label = _sefaria_book_name(label)
        else:
            source_label = SOURCE_LABELS.get(source, source)

        results.append({
            "source_key":   source,
            "source_label": source_label,
            "ref":          _clean_label(label),
            "text":         m["text"],
            "score":        score,
            "dots":         score_to_dots(score),
        })

        if len(results) >= DISPLAY_MAX:
            break

    return results


def render_dots(n: int, total: int = 5) -> str:
    """Return HTML dot-rating string."""
    filled = "●" * n
    empty  = "○" * (total - n)
    return f'<span class="score-dots">{filled}{empty}</span>'
