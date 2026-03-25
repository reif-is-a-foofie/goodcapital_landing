"""
First-person journals and letters of people who knew Joseph Smith.

Sources:
  - Wilford Woodruff Journal (Archive.org) — most comprehensive journal
    of Joseph Smith's teachings, recorded firsthand
  - Heber C. Kimball Journal (Archive.org)
  - Benjamin F. Johnson Letter to Elder Gibbs (Archive.org) — records
    private teachings of Joseph Smith not in official histories
  - Parley P. Pratt is in gutenberg_lds.py (he also knew Joseph personally)

These are the raw primary sources — Joseph's own words recorded by
contemporaries, often differing from edited official histories.
"""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/early_saints")

TEXTS = {
    "wilford_woodruff": {
        "title": "Wilford Woodruff Journal",
        "short": "Wilford Woodruff Journal",
        "url": "https://archive.org/download/WWJ_1833_1898/WWJ_1833_1898_djvu.txt",
        "alt_url": "https://archive.org/download/WilfordWoodruffJournal/WilfordWoodruffJournal_djvu.txt",
    },
    "heber_kimball": {
        "title": "President Heber C. Kimball's Journal",
        "short": "Heber C. Kimball Journal",
        "url": "https://archive.org/download/presidentheberck00kimbrich/presidentheberck00kimbrich_djvu.txt",
    },
    "benjamin_johnson": {
        "title": "Benjamin F. Johnson Letter to Elder Gibbs",
        "short": "B.F. Johnson Letter",
        "url": "https://archive.org/download/BenjaminFJohnsonLetterToGeorgeFGibbs/Benjamin%20F%20Johnson%20Letter%20to%20George%20F%20Gibbs_djvu.txt",
    },
}


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.txt"


def _index_cache() -> Path:
    return CACHE_DIR / "scripture_index.json"


def download_text(key: str) -> Optional[str]:
    info = TEXTS[key]
    cache = _cache_path(key)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(encoding="utf-8", errors="replace")

    for url in [info["url"]] + ([info.get("alt_url")] if info.get("alt_url") else []):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1", errors="replace")
            text = re.sub(r'\x0c', '\n\n', text)
            cache.write_text(text, encoding="utf-8")
            print(f"  {info['title']}: {len(text):,} chars cached")
            return text
        except Exception as e:
            print(f"  {info['title']}: {url} — {e}")

    return None


def download_all() -> dict:
    result = {}
    for key, info in TEXTS.items():
        text = download_text(key)
        if text:
            result[key] = {**info, "text": text}
    return result


# ── Reference indexing ────────────────────────────────────────────────────────

_REF_RE = re.compile(
    r'\b((?:\d\s)?[A-Z][a-z]+\.?\s+\d+:\d+(?:[-–]\d+)?)',
    re.MULTILINE
)

_ABBREV = {
    "Gen": "Genesis", "Ex": "Exodus", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Ps": "Psalms", "Matt": "Matthew",
    "Jn": "John", "Rev": "Revelation",
    "Ne": "Nephi", "DC": "Doctrine and Covenants", "D&C": "Doctrine and Covenants",
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


def build_index(docs: dict, max_quote_len: int = 400) -> dict:
    idx_path = _index_cache()
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))

    index = {}
    for key, doc in docs.items():
        short = doc.get("short", key)
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
                    index[idx_key].append({"source": short, "text": snippet})

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  Early Saints index: {len(index):,} refs indexed")
    return index


_index: dict = None


def get_quotes(book: str, chapter: int, verse: int, max_quotes: int = 2) -> list[dict]:
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
