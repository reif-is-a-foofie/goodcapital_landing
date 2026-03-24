"""
Joseph Smith Papers — scraper for josephsmithpapers.org

No public API exists. This module:
  1. Fetches known JSP document URLs (curated list of most scripture-heavy docs)
  2. Extracts text from the HTML
  3. Indexes by scripture reference

Documents included:
  - King Follett Discourse
  - Lectures on Faith
  - Joseph Smith's journal entries referencing scriptures
  - Selected letters and revelations

The JSP website terms of service allow personal, non-commercial use.
We cache aggressively to minimize requests.
"""

import re
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/lds_pipeline/cache/jsp")

# Curated high-value JSP documents with scripture density
JSP_DOCUMENTS = {
    "king_follett": {
        "url": "https://www.josephsmithpapers.org/paper-summary/discourse-7-april-1844-as-reported-by-wilford-woodruff/1",
        "title": "King Follett Discourse (Apr 7, 1844)",
    },
    "lectures_on_faith_1": {
        "url": "https://www.josephsmithpapers.org/paper-summary/lecture-first-circa-26-december-1834-9-january-1835/1",
        "title": "Lectures on Faith, Lecture 1",
    },
    "lectures_on_faith_2": {
        "url": "https://www.josephsmithpapers.org/paper-summary/lecture-second-circa-26-december-1834-9-january-1835/1",
        "title": "Lectures on Faith, Lecture 2",
    },
    "lectures_on_faith_7": {
        "url": "https://www.josephsmithpapers.org/paper-summary/lecture-seventh-circa-26-december-1834-9-january-1835/1",
        "title": "Lectures on Faith, Lecture 7",
    },
    "wentworth_letter": {
        "url": "https://www.josephsmithpapers.org/paper-summary/church-history-1-march-1842/1",
        "title": "Wentworth Letter (History of the Church)",
    },
    "dc_76_vision": {
        "url": "https://www.josephsmithpapers.org/paper-summary/revelation-16-february-1832-dc-76/1",
        "title": "Vision of the Three Degrees (D&C 76)",
    },
    "dc_section_1": {
        "url": "https://www.josephsmithpapers.org/paper-summary/revelation-1-november-1831-dc-1/1",
        "title": "D&C Section 1 Revelation Record",
    },
    "grove_experience": {
        "url": "https://www.josephsmithpapers.org/paper-summary/history-circa-summer-1832/1",
        "title": "Joseph Smith History (1832 Account)",
    },
    "liberty_jail_letters": {
        "url": "https://www.josephsmithpapers.org/paper-summary/letter-to-the-church-circa-25-march-1839/1",
        "title": "Letters from Liberty Jail (D&C 121-123)",
    },
}


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.txt"


def _index_cache() -> Path:
    return CACHE_DIR / "scripture_index.json"


def _fetch_html(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; LDS-Study-Tool/1.0)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  JSP fetch failed ({url}): {e}")
        return None


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from JSP HTML page."""
    # Remove scripts, styles, nav
    html = re.sub(r'<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', html, flags=re.DOTALL|re.IGNORECASE)
    # Extract main content div (JSP uses .transcript or .document-content)
    for pattern in [
        r'<div[^>]+class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]+class="[^"]*document[^"]*"[^>]*>(.*?)</div>',
        r'<article[^>]*>(.*?)</article>',
        r'<main[^>]*>(.*?)</main>',
    ]:
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if m:
            html = m.group(1)
            break

    # Strip remaining tags
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def download_document(key: str, doc: dict) -> Optional[str]:
    cache = _cache_path(key)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 500:
        return cache.read_text(encoding="utf-8")

    html = _fetch_html(doc["url"])
    if not html:
        return None

    text = _extract_text_from_html(html)
    if len(text) < 200:
        print(f"  JSP {key}: too short ({len(text)} chars), may have failed")
        return None

    cache.write_text(text, encoding="utf-8")
    print(f"  JSP {key}: {len(text):,} chars cached")
    time.sleep(1.5)  # polite delay
    return text


def download_all_documents() -> dict[str, dict]:
    """Download all curated JSP documents. Returns {key: {title, text}}"""
    result = {}
    for key, doc in JSP_DOCUMENTS.items():
        text = download_document(key, doc)
        if text:
            result[key] = {"title": doc["title"], "text": text}
    return result


# ── Reference indexing ────────────────────────────────────────────────────────

_REF_RE = re.compile(
    r'\b((?:\d\s)?[A-Z][a-z]+\.?\s+\d+:\d+(?:[-–]\d+)?)',
    re.MULTILINE
)

_ABBREV = {
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Leviticus",
    "Num": "Numbers", "Deut": "Deuteronomy", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Ezek": "Ezekiel", "Ps": "Psalms",
    "Prov": "Proverbs", "Matt": "Matthew", "Jn": "John",
    "Rom": "Romans", "Heb": "Hebrews", "Rev": "Revelation",
    "Ne": "Nephi", "Alma": "Alma", "Moro": "Moroni",
    "DC": "Doctrine and Covenants", "D&C": "Doctrine and Covenants",
}


def _parse_ref(raw: str) -> Optional[tuple]:
    m = re.match(r'(\d?\s*[A-Za-z&]+\.?)\s+(\d+):(\d+)', raw.strip())
    if not m:
        return None
    book = _ABBREV.get(m.group(1).rstrip("."), m.group(1).rstrip("."))
    try:
        return (book.upper(), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def build_index(docs: dict[str, dict], max_quote_len: int = 400) -> dict:
    idx_path = _index_cache()
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))

    index = {}
    for key, doc in docs.items():
        title = doc["title"]
        paragraphs = re.split(r'\n{2,}', doc["text"])
        for para in paragraphs:
            refs = _REF_RE.findall(para)
            for raw_ref in refs:
                parsed = _parse_ref(raw_ref)
                if not parsed:
                    continue
                idx_key = f"{parsed[0]}_{parsed[1]}_{parsed[2]}"
                snippet = para.strip()[:max_quote_len].replace('\n', ' ')
                if idx_key not in index:
                    index[idx_key] = []
                if not any(snippet[:50] in q["text"] for q in index[idx_key]):
                    index[idx_key].append({"source": title, "text": snippet})

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  JSP index: {len(index):,} refs indexed")
    return index


_index: dict = None


def get_quotes(book: str, chapter: int, verse: int, max_quotes: int = 1) -> list[dict]:
    global _index
    if _index is None:
        _index = _load_index()
    if _index is None:
        return []
    key = f"{book.upper()}_{chapter}_{verse}"
    return _index.get(key, [])[:max_quotes]


def _load_index() -> Optional[dict]:
    idx_path = _index_cache()
    if idx_path.exists():
        try:
            return json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None
