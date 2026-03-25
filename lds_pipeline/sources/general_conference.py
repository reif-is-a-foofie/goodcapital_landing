"""
General Conference talks — 1971 to present.
Source: churchofjesuschrist.org (free, publicly accessible)

Strategy:
  1. Use the Church's search API with scripture references as queries
  2. Cache results per (book, chapter, verse) key
  3. Extract quote snippets containing the reference

The Church's search endpoint accepts:
  GET /search?lang=eng&query=BOOK+CHAPTER:VERSE&facets=type:talk
Returns JSON with talk metadata and snippets.
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/gc")
BASE_SEARCH = "https://www.churchofjesuschrist.org/search"
BASE_CONTENT = "https://www.churchofjesuschrist.org"

# Abbreviations used in GC talks for scripture books
BOOK_ABBREV = {
    "Genesis": "Gen", "Exodus": "Ex", "Leviticus": "Lev",
    "Numbers": "Num", "Deuteronomy": "Deut", "Joshua": "Josh",
    "Judges": "Judg", "1 Samuel": "1 Sam", "2 Samuel": "2 Sam",
    "1 Kings": "1 Kgs", "2 Kings": "2 Kgs", "Isaiah": "Isa",
    "Jeremiah": "Jer", "Ezekiel": "Ezek", "Psalms": "Ps",
    "Proverbs": "Prov", "Matthew": "Matt", "Mark": "Mark",
    "Luke": "Luke", "John": "John", "Acts": "Acts",
    "Romans": "Rom", "1 Corinthians": "1 Cor", "2 Corinthians": "2 Cor",
    "Galatians": "Gal", "Ephesians": "Eph", "Hebrews": "Heb",
    "Revelation": "Rev", "1 Nephi": "1 Ne", "2 Nephi": "2 Ne",
    "Mosiah": "Mosiah", "Alma": "Alma", "Helaman": "Hel",
    "3 Nephi": "3 Ne", "4 Nephi": "4 Ne", "Mormon": "Morm",
    "Ether": "Ether", "Moroni": "Moro",
    "Doctrine and Covenants": "D&C",
    "Moses": "Moses", "Abraham": "Abr",
}


def _cache_path(book: str, chapter: int, verse: int) -> Path:
    safe_book = re.sub(r'[^\w]', '_', book)
    return CACHE_DIR / f"{safe_book}_{chapter}_{verse}.json"


def _fetch_talks_for_verse(book: str, chapter: int, verse: int) -> list[dict]:
    """
    Fetch GC talk snippets mentioning this verse.
    Returns list of {title, author, year, url, snippet}.
    """
    cache = _cache_path(book, chapter, verse)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass

    results = []

    # Build query strings — try full name and abbreviation
    queries = [f"{book} {chapter}:{verse}"]
    abbrev = BOOK_ABBREV.get(book)
    if abbrev and abbrev != book:
        queries.append(f"{abbrev} {chapter}:{verse}")

    for query in queries:
        params = urllib.parse.urlencode({
            "lang": "eng",
            "query": query,
            "facets": "type:talk",
            "page": "1",
        })
        url = f"{BASE_SEARCH}?{params}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; LDS-Study-Tool/1.0)",
                "Accept": "application/json, text/html",
                "X-Requested-With": "XMLHttpRequest",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8", errors="replace")

            # Parse JSON response if returned
            try:
                data = json.loads(raw)
                hits = data.get("results", data.get("hits", {}).get("hits", []))
                for hit in hits[:5]:
                    src = hit.get("_source", hit)
                    title  = src.get("title", "")
                    author = src.get("author", src.get("byline", ""))
                    year   = str(src.get("year", src.get("publishedAt", "")))[:4]
                    path   = src.get("url", src.get("path", ""))
                    snippet = src.get("snippet", src.get("body", ""))[:400]
                    if title and snippet:
                        results.append({
                            "title": title, "author": author,
                            "year": year, "url": path, "snippet": snippet,
                        })
            except json.JSONDecodeError:
                # HTML response — extract snippet text
                snippets = re.findall(
                    r'<div[^>]+class="[^"]*snippet[^"]*"[^>]*>(.*?)</div>',
                    raw, re.DOTALL | re.IGNORECASE
                )
                titles = re.findall(
                    r'<(?:h\d|a)[^>]+class="[^"]*title[^"]*"[^>]*>(.*?)</(?:h\d|a)>',
                    raw, re.DOTALL | re.IGNORECASE
                )
                for i, snippet in enumerate(snippets[:4]):
                    clean = re.sub(r'<[^>]+>', '', snippet).strip()
                    title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
                    if clean and len(clean) > 50:
                        results.append({
                            "title": title, "author": "", "year": "",
                            "url": "", "snippet": clean[:400],
                        })

        except Exception as e:
            pass  # silently skip network failures

        if results:
            break
        time.sleep(0.5)

    cache.write_text(json.dumps(results, ensure_ascii=False))
    return results


def get_quotes(book: str, chapter: int, verse: int, max_quotes: int = 3) -> list[dict]:
    """
    Returns up to max_quotes GC talk snippets for a verse.
    Each: {title, author, year, snippet}
    """
    results = _fetch_talks_for_verse(book, chapter, verse)
    return results[:max_quotes]


# ── Bulk index builder (offline mode) ────────────────────────────────────────
# For books with heavy coverage, pre-build an index from downloaded talk texts.

def build_offline_index(talks_dir: str) -> dict:
    """
    If you have downloaded GC talk texts to a directory,
    this builds a scripture-ref → quotes index.
    talks_dir: path containing .txt files of talk content
    """
    _REF_RE = re.compile(
        r'\b((?:\d\s)?[A-Z][a-z]+\.?\s+\d+:\d+)',
        re.MULTILINE
    )
    index = {}
    for fpath in Path(talks_dir).glob("*.txt"):
        text  = fpath.read_text(encoding="utf-8", errors="replace")
        title = fpath.stem.replace("_", " ")
        paras = re.split(r'\n{2,}', text)
        for para in paras:
            for ref in _REF_RE.findall(para):
                key = _normalise_ref(ref)
                if not key:
                    continue
                if key not in index:
                    index[key] = []
                snippet = para.strip()[:400].replace('\n', ' ')
                index[key].append({"title": title, "snippet": snippet})
    return index


def _normalise_ref(raw: str) -> Optional[str]:
    m = re.match(r'(\d?\s*[A-Za-z]+\.?)\s+(\d+):(\d+)', raw.strip())
    if not m:
        return None
    _ABBREV = {
        "Gen": "GENESIS", "Ex": "EXODUS", "Lev": "LEVITICUS",
        "Num": "NUMBERS", "Deut": "DEUTERONOMY", "Isa": "ISAIAH",
        "Matt": "MATTHEW", "Jn": "JOHN", "Rev": "REVELATION",
        "Ne": "NEPHI", "DC": "DOCTRINE AND COVENANTS", "D&C": "DOCTRINE AND COVENANTS",
    }
    book = _ABBREV.get(m.group(1).rstrip("."), m.group(1).upper())
    return f"{book}_{m.group(2)}_{m.group(3)}"
