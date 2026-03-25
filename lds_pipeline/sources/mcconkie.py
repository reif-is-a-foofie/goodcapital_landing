"""
Bruce R. McConkie — Mormon Doctrine & Doctrinal New Testament Commentary.

Downloads from Archive.org (freely accessible). Under copyright but
Archive.org provides free access for non-commercial use.

Mormon Doctrine: topic dictionary with scripture cross-refs throughout.
DNTC: organized directly by NT verse — extremely high scripture density.

Strategy:
  - Mormon Doctrine: scan for scripture references in topic entries
  - DNTC Vol 1-3: parse verse-by-verse structure (NT only)
"""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/mcconkie")

TEXTS = {
    "mormon_doctrine": {
        "title": "Mormon Doctrine",
        "short": "McConkie, Mormon Doctrine",
        "url": "https://archive.org/download/MormonDoctrine1966_201806/MormonDoctrine1966.txt",
        "alt_url": "https://archive.org/download/MormonDoctrine1966_201806/MormonDoctrine1966_djvu.txt",
    },
    "dntc_vol1": {
        "title": "Doctrinal New Testament Commentary Vol 1",
        "short": "McConkie, DNTC Vol 1",
        "url": "https://archive.org/download/doctrinalnewtest00bruc/doctrinalnewtest00bruc_djvu.txt",
    },
    "teachings_pjs": {
        "title": "Teachings of the Prophet Joseph Smith (Joseph Fielding Smith, ed.)",
        "short": "TPJS",
        "url": "https://scriptures.byu.edu/tpjs/STPJS.pdf",  # BYU hosts this freely
        "alt_url": "https://archive.org/download/teachingsofproph00smit/teachingsofproph00smit_djvu.txt",
    },
    "words_joseph_smith": {
        "title": "Words of Joseph Smith (Ehat & Cook)",
        "short": "Words of Joseph Smith",
        "url": "https://archive.org/download/wordsofjosephsmi0000unse/wordsofjosephsmi0000unse_djvu.txt",
    },
}


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.txt"


def _index_cache() -> Path:
    return CACHE_DIR / "scripture_index.json"


def _fetch_text(url: str, alt_url: str = None) -> Optional[str]:
    for u in ([url] + ([alt_url] if alt_url else [])):
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": "LDS-Pipeline/1.0",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                # Try UTF-8 then latin-1
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("latin-1", errors="replace")
        except Exception as e:
            print(f"  fetch failed ({u}): {e}")
    return None


def download_text(key: str) -> Optional[str]:
    info = TEXTS[key]
    cache = _cache_path(key)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 5000:
        return cache.read_text(encoding="utf-8", errors="replace")

    text = _fetch_text(info["url"], info.get("alt_url"))
    if not text:
        return None

    # Clean djvu OCR artifacts
    text = re.sub(r'\x0c', '\n\n', text)   # form feeds → paragraph breaks
    text = re.sub(r' {3,}', ' ', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    cache.write_text(text, encoding="utf-8")
    print(f"  {info['title']}: {len(text):,} chars cached")
    return text


def download_all() -> dict:
    result = {}
    for key, info in TEXTS.items():
        print(f"\n  → {info['title']}")
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
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Leviticus",
    "Num": "Numbers", "Deut": "Deuteronomy", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Ezek": "Ezekiel", "Ps": "Psalms",
    "Prov": "Proverbs", "Matt": "Matthew", "Mk": "Mark",
    "Lk": "Luke", "Jn": "John", "Rom": "Romans",
    "Cor": "Corinthians", "Gal": "Galatians", "Eph": "Ephesians",
    "Heb": "Hebrews", "Rev": "Revelation",
    "Ne": "Nephi", "Alma": "Alma", "Moro": "Moroni",
    "DC": "Doctrine and Covenants", "D&C": "Doctrine and Covenants",
    "Moro": "Moroni", "Eth": "Ether",
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


def build_index(docs: dict, max_quote_len: int = 500) -> dict:
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
    print(f"  McConkie/TPJS index: {len(index):,} refs indexed")
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
