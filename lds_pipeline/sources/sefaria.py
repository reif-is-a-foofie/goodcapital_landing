"""
Sefaria API — Rashi, Talmud, Midrash

Free REST API, no key required.
https://developers.sefaria.org/

Provides:
  - Rashi commentary on Torah (linked per verse)
  - Talmud cross-references (links endpoint)
  - Midrash Rabbah references

Caches all responses to avoid repeated network calls.
"""

import json
import re
import os
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/lds_pipeline/cache/sefaria")
BASE_URL  = "https://www.sefaria.org/api"

# Book name translation: our canonical name → Sefaria reference name
BOOK_TO_SEFARIA = {
    "Genesis":        "Genesis",
    "Exodus":         "Exodus",
    "Leviticus":      "Leviticus",
    "Numbers":        "Numbers",
    "Deuteronomy":    "Deuteronomy",
    "Joshua":         "Joshua",
    "Judges":         "Judges",
    "1 Samuel":       "I_Samuel",
    "2 Samuel":       "II_Samuel",
    "1 Kings":        "I_Kings",
    "2 Kings":        "II_Kings",
    "Isaiah":         "Isaiah",
    "Jeremiah":       "Jeremiah",
    "Ezekiel":        "Ezekiel",
    "Psalms":         "Psalms",
    "Proverbs":       "Proverbs",
    "Job":            "Job",
    "Song of Solomon":"Song_of_Songs",
    "Ruth":           "Ruth",
    "Lamentations":   "Lamentations",
    "Ecclesiastes":   "Ecclesiastes",
    "Esther":         "Esther",
    "Daniel":         "Daniel",
    "Ezra":           "Ezra",
    "Nehemiah":       "Nehemiah",
    "1 Chronicles":   "I_Chronicles",
    "2 Chronicles":   "II_Chronicles",
}

# OT books where Rashi commentary exists on Sefaria
RASHI_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "Isaiah", "Jeremiah", "Ezekiel", "Psalms", "Proverbs", "Job",
    "Song of Solomon", "Ruth", "Lamentations", "Ecclesiastes",
    "Esther", "Daniel", "Ezra", "Nehemiah",
    "1 Chronicles", "2 Chronicles",
}


def _cache_path(key: str) -> Path:
    safe = re.sub(r'[^\w\-.]', '_', key)
    return CACHE_DIR / f"{safe}.json"


def _fetch(url: str, cache_key: str) -> Optional[object]:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass  # re-fetch if corrupted

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception as e:
        msg = str(e)
        # 404 = Rashi/Targum simply doesn't cover this verse — expected, don't spam
        if "404" not in msg:
            print(f"  Sefaria fetch failed ({url}): {e}")
        # Cache negative result so we don't retry on next run
        path.write_text("null", encoding="utf-8")
        return None


def _sefaria_ref(book: str, chapter: int, verse: int) -> Optional[str]:
    sf = BOOK_TO_SEFARIA.get(book)
    if not sf:
        return None
    return f"{sf}.{chapter}.{verse}"


# ── Rashi ────────────────────────────────────────────────────────────────────

def get_rashi(book: str, chapter: int, verse: int, max_comments: int = 2) -> list[str]:
    """
    Returns list of Rashi comment strings for the given verse.
    HTML tags stripped; each string is plain text.
    """
    if book not in RASHI_BOOKS:
        return []

    ref = _sefaria_ref(book, chapter, verse)
    if not ref:
        return []

    rashi_ref = f"Rashi_on_{ref}"
    url = f"{BASE_URL}/v3/texts/{urllib.parse.quote(rashi_ref)}"
    data = _fetch(url, f"rashi_{rashi_ref}")
    if not data:
        return []

    # Sefaria v3 returns versions array — only use English versions
    versions = data.get("versions", [])
    comments = []
    for version in versions:
        if version.get("language", "") != "en":
            continue
        text = version.get("text", [])
        if isinstance(text, list):
            for item in text:
                if isinstance(item, str) and item.strip():
                    clean = _strip_html(item)
                    if clean:
                        comments.append(clean)
        elif isinstance(text, str) and text.strip():
            comments.append(_strip_html(text))
        if len(comments) >= max_comments:
            break

    return comments[:max_comments]


# ── Links (Talmud + Midrash cross-refs) ──────────────────────────────────────

def get_links(book: str, chapter: int, verse: int,
              max_talmud: int = 2, max_midrash: int = 1) -> dict:
    """
    Returns { 'talmud': [...], 'midrash': [...] }
    Each entry: { 'ref': str, 'text': str, 'source': str }
    """
    ref = _sefaria_ref(book, chapter, verse)
    if not ref:
        return {"talmud": [], "midrash": []}

    url = f"{BASE_URL}/links/{urllib.parse.quote(ref)}"
    data = _fetch(url, f"links_{ref}")
    if not data or not isinstance(data, list):
        return {"talmud": [], "midrash": []}

    talmud  = []
    midrash = []

    for link in data:
        category = link.get("category", "")
        source_ref = link.get("sourceRef", "") or link.get("ref", "")
        # Prefer English text; fall back to `text` field
        snippets = link.get("en", "") or link.get("text", "")
        if isinstance(snippets, list):
            snippets = " ".join(snippets[:2])
        text = _strip_html(str(snippets))[:300] if snippets else ""

        entry = {"ref": source_ref, "text": text, "source": category}

        if "Talmud" in category or "Bavli" in category or "Yerushalmi" in category:
            if len(talmud) < max_talmud:
                talmud.append(entry)
        elif "Midrash" in category:
            if len(midrash) < max_midrash:
                midrash.append(entry)

    return {"talmud": talmud, "midrash": midrash}


# ── Targums (Aramaic paraphrases of Torah) ────────────────────────────────────
# Onkelos = most authoritative Aramaic Torah targum
# Jonathan = Prophets targum
# These often contain expansions and interpretations not in the Hebrew

TARGUM_SOURCES = {
    "onkelos": "Onkelos_on_the_Torah",       # Torah only
    "jonathan": "Targum_Jonathan_on_the_Torah",
    "neofiti": "Targum_Neofiti",
}

TARGUM_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "Isaiah", "Jeremiah", "Ezekiel",
}


def get_targum(book: str, chapter: int, verse: int, targum: str = "onkelos") -> Optional[str]:
    """
    Returns Targum English text for a verse via Sefaria links endpoint.
    Onkelos and Neofiti have English translations in the links API `en` field.
    """
    if book not in TARGUM_BOOKS:
        return None

    ref = _sefaria_ref(book, chapter, verse)
    if not ref:
        return None

    url = f"{BASE_URL}/links/{urllib.parse.quote(ref)}"
    data = _fetch(url, f"links_{ref}")
    if not data or not isinstance(data, list):
        return None

    for link in data:
        source_ref = link.get("sourceRef", "") or link.get("ref", "")
        category   = link.get("category", "")
        if "Targum" not in category and "Targum" not in source_ref:
            continue
        en_text = link.get("en", "") or link.get("text", "")
        if isinstance(en_text, list):
            en_text = " ".join(s for s in en_text if isinstance(s, str))
        clean = _strip_html(str(en_text)).strip()
        if clean:
            return f"{clean} ({source_ref})"

    return None


# ── Zohar (Kabbalistic Torah commentary) ─────────────────────────────────────
# The Zohar is the central text of Kabbalah. It contains mystical commentary
# on the Torah that has surprising parallels to LDS doctrines (pre-existence,
# divine council, multiple heavens, nature of God).

ZOHAR_TORAH_MAP = {
    # Sefaria's Zohar is organized by Torah portion, not chapter:verse
    # This map translates Genesis chapters to Zohar parsha names
    "Genesis": {
        (1, 1): "Zohar.Bereshit.1",
        (1, 26): "Zohar.Bereshit.2",
        (2, 1): "Zohar.Bereshit.3",
        (3, 1): "Zohar.Bereshit.4",
        (6, 9): "Zohar.Noach.1",
        (12, 1): "Zohar.Lech_Lecha.1",
        (18, 1): "Zohar.Vayera.1",
        (22, 1): "Zohar.Vayera.2",
        (28, 10): "Zohar.Vayetze.1",
    },
    "Exodus": {
        (3, 1): "Zohar.Shemot.1",
        (6, 2): "Zohar.Va'era.1",
        (20, 1): "Zohar.Yitro.1",
        (25, 1): "Zohar.Terumah.1",
    },
}


def get_zohar(book: str, chapter: int, verse: int) -> Optional[str]:
    """
    Returns a relevant Zohar passage for a Torah verse (where available).
    """
    book_map = ZOHAR_TORAH_MAP.get(book, {})
    # Find nearest entry at or before this chapter:verse
    best_ref = None
    for (ch, v), zref in sorted(book_map.items()):
        if (ch, v) <= (chapter, verse):
            best_ref = zref
        else:
            break
    if not best_ref:
        return None

    url = f"{BASE_URL}/v3/texts/{urllib.parse.quote(best_ref)}?context=0"
    data = _fetch(url, f"zohar_{best_ref.replace('.', '_')}")
    if not data:
        return None

    versions = data.get("versions", [])
    for version in versions:
        lang = version.get("language", "")
        text = version.get("text", "")
        if lang == "en" and text:
            if isinstance(text, list):
                flat = []
                for item in text:
                    if isinstance(item, str):
                        flat.append(item)
                    elif isinstance(item, list):
                        flat.extend(i for i in item if isinstance(i, str))
                text = " ".join(flat[:3])  # first 3 paragraphs
            clean = _strip_html(str(text)).strip()
            if clean:
                return clean[:500]
    return None


# ── Extended links — also captures Targum, Zohar, Josephus ───────────────────

def get_all_links(book: str, chapter: int, verse: int) -> dict:
    """
    Extended version of get_links — also returns Targum, Zohar, Josephus.
    Returns {talmud, midrash, targum, zohar, josephus}
    """
    base = get_links(book, chapter, verse)
    result = {**base, "targum": [], "zohar": [], "josephus": []}

    ref = _sefaria_ref(book, chapter, verse)
    if not ref:
        return result

    url = f"{BASE_URL}/links/{urllib.parse.quote(ref)}"
    data = _fetch(url, f"links_{ref}")
    if not data or not isinstance(data, list):
        return result

    for link in data:
        category = link.get("category", "")
        source_ref = link.get("sourceRef", "") or link.get("ref", "")
        snippets = link.get("he", "") or link.get("text", "")
        if isinstance(snippets, list):
            snippets = " ".join(snippets[:2])
        text = _strip_html(str(snippets))[:400] if snippets else ""
        entry = {"ref": source_ref, "text": text}

        if "Targum" in category or "targum" in source_ref.lower():
            result["targum"].append(entry)
        elif "Zohar" in category or "Kabbalah" in category:
            result["zohar"].append(entry)
        elif "Josephus" in source_ref or "Antiquities" in source_ref:
            result["josephus"].append(entry)

    return result


# ── HTML strip ────────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r'<[^>]+>')

def _strip_html(s: str) -> str:
    return _TAG_RE.sub('', s).strip()
