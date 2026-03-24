"""
Project Gutenberg — LDS and early Church texts (public domain)

Texts included:
  - Parley P. Pratt Autobiography (44896)
  - Lucy Mack Smith — History of Joseph Smith (45619)
  - Discourses of Brigham Young / Widtsoe (74447)
  - William Clayton Journal (45051)

All are plain text or HTML, freely downloadable.
Scripture references indexed the same way as JD/HoC.
"""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/lds_pipeline/cache/gutenberg_lds")

TEXTS = {
    "parley_pratt": {
        "title": "Parley P. Pratt Autobiography",
        "short": "Pratt, Autobiography",
        "gutenberg_id": 44896,
        "url": "https://www.gutenberg.org/files/44896/44896-0.txt",
    },
    "lucy_mack_smith": {
        "title": "History of Joseph Smith by His Mother (Lucy Mack Smith)",
        "short": "Lucy Mack Smith",
        "gutenberg_id": 45619,
        "url": "https://www.gutenberg.org/files/45619/45619-0.txt",
    },
    "brigham_young_discourses": {
        "title": "Discourses of Brigham Young (Widtsoe)",
        "short": "Discourses of Brigham Young",
        "gutenberg_id": 74447,
        "url": "https://www.gutenberg.org/files/74447/74447-0.txt",
    },
    "william_clayton": {
        "title": "William Clayton Journal",
        "short": "Clayton Journal",
        "gutenberg_id": 45051,
        "url": "https://www.gutenberg.org/files/45051/45051-0.txt",
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

    url = info["url"]
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "LDS-Pipeline/1.0",
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", errors="replace")
        cache.write_text(text, encoding="utf-8")
        print(f"  {info['title']}: {len(text):,} chars cached")
        return text
    except Exception as e:
        print(f"  {info['title']}: failed — {e}")
        return None


def download_all() -> dict[str, dict]:
    """Download all texts. Returns {key: {title, short, text}}"""
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
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Leviticus",
    "Num": "Numbers", "Deut": "Deuteronomy", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Ezek": "Ezekiel", "Ps": "Psalms",
    "Prov": "Proverbs", "Matt": "Matthew", "Mk": "Mark",
    "Lk": "Luke", "Jn": "John", "Rom": "Romans",
    "Heb": "Hebrews", "Rev": "Revelation",
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
    print(f"  Gutenberg LDS index: {len(index):,} refs indexed")
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
