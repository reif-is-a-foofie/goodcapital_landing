"""
Journal of Discourses — 26 volumes, public domain.

Downloads plain-text versions from Archive.org and builds a searchable
index: scripture_ref → list of relevant quotes.

Archive.org IDs for JD volumes: JoDV01 through JoDV26
Text files are available as {id}_djvu.txt or similar.
"""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/lds_pipeline/cache/jd")

# Archive.org item IDs for Journal of Discourses volumes
JD_ARCHIVE_IDS = [
    "journalofdiscou01brig",  # Vol 1
    "journalofdiscou02brig",  # Vol 2
    "journalofdiscou03brig",  # Vol 3
    "journalofdiscou04brig",  # Vol 4
    "journalofdiscou05brig",  # Vol 5
    "journalofdiscou06brig",  # Vol 6
    "journalofdiscou07brig",  # Vol 7
    "journalofdiscou08brig",  # Vol 8
    "journalofdiscou09brig",  # Vol 9
    "journalofdiscou10brig",  # Vol 10
    "journalofdiscou11brig",  # Vol 11
    "journalofdiscou12brig",  # Vol 12
    "journalofdiscou13brig",  # Vol 13
    "journalofdiscou14brig",  # Vol 14
    "journalofdiscou15brig",  # Vol 15
    "journalofdiscou16brig",  # Vol 16
    "journalofdiscou17brig",  # Vol 17
    "journalofdiscou18brig",  # Vol 18
    "journalofdiscou19brig",  # Vol 19
    "journalofdiscou20brig",  # Vol 20
    "journalofdiscou21brig",  # Vol 21
    "journalofdiscou22brig",  # Vol 22
    "journalofdiscou23brig",  # Vol 23
    "journalofdiscou24brig",  # Vol 24
    "journalofdiscou25brig",  # Vol 25
    "journalofdiscou26brig",  # Vol 26
]

ARCHIVE_META_URL = "https://archive.org/metadata/{id}"
ARCHIVE_TEXT_URL = "https://archive.org/download/{id}/{id}_djvu.txt"


def _text_cache(vol_num: int) -> Path:
    return CACHE_DIR / f"vol_{vol_num:02d}.txt"


def _index_cache() -> Path:
    return CACHE_DIR / "scripture_index.json"


def download_volume(vol_num: int) -> Optional[str]:
    """Download and cache plain text for one volume (1-indexed)."""
    cache = _text_cache(vol_num)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(encoding="utf-8", errors="replace")

    archive_id = JD_ARCHIVE_IDS[vol_num - 1]

    print(f"  JD Vol {vol_num}: downloading...", flush=True)
    # First try djvu.txt
    url = ARCHIVE_TEXT_URL.format(id=archive_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")
        cache.write_text(text, encoding="utf-8")
        print(f"  JD Vol {vol_num}: {len(text):,} chars cached")
        return text
    except Exception:
        pass

    # Try metadata to find actual file names
    try:
        meta_url = ARCHIVE_META_URL.format(id=archive_id)
        with urllib.request.urlopen(meta_url, timeout=15) as r:
            meta = json.loads(r.read())
        files = meta.get("files", [])
        txt_files = [f for f in files if f.get("name", "").endswith(".txt")]
        if txt_files:
            fname = txt_files[0]["name"]
            url2 = f"https://archive.org/download/{archive_id}/{fname}"
            with urllib.request.urlopen(url2, timeout=30) as r:
                text = r.read().decode("utf-8", errors="replace")
            cache.write_text(text, encoding="utf-8")
            print(f"  JD Vol {vol_num}: {len(text):,} chars (via metadata)")
            return text
    except Exception as e:
        print(f"  JD Vol {vol_num}: skipped — {e}")

    return None


def download_all_volumes(volumes: list[int] = None) -> dict[int, str]:
    """Download specified volumes (default: all 26). Returns {vol_num: text}."""
    vols = volumes or list(range(1, 27))
    result = {}
    for v in vols:
        text = download_volume(v)
        if text:
            result[v] = text
    return result


# ── Scripture reference indexing ─────────────────────────────────────────────

# Matches scripture references like "Gen. 1:1", "John 3:16", "D&C 76:22"
_REF_RE = re.compile(
    r'\b((?:\d\s)?[A-Z][a-z]+\.?\s+\d+:\d+(?:[-–]\d+)?)',
    re.MULTILINE
)

# Normalize abbreviations to canonical book names
_ABBREV = {
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Leviticus",
    "Num": "Numbers", "Deut": "Deuteronomy", "Josh": "Joshua",
    "Judg": "Judges", "Isa": "Isaiah", "Jer": "Jeremiah",
    "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea",
    "Ps": "Psalms", "Prov": "Proverbs", "Matt": "Matthew",
    "Mk": "Mark", "Lk": "Luke", "Jn": "John", "Rom": "Romans",
    "Cor": "Corinthians", "Gal": "Galatians", "Eph": "Ephesians",
    "Phil": "Philippians", "Col": "Colossians", "Thes": "Thessalonians",
    "Tim": "Timothy", "Heb": "Hebrews", "Jas": "James",
    "Pet": "Peter", "Rev": "Revelation",
    "Ne": "Nephi", "Mosiah": "Mosiah", "Alma": "Alma",
    "Hel": "Helaman", "Eth": "Ether", "Moro": "Moroni",
    "DC": "Doctrine and Covenants", "D&C": "Doctrine and Covenants",
}


def _parse_ref(raw: str) -> Optional[tuple]:
    """Parse 'Gen. 1:1' → ('Genesis', 1, 1) or None."""
    m = re.match(r'(\d?\s*[A-Za-z&]+\.?)\s+(\d+):(\d+)', raw.strip())
    if not m:
        return None
    abbr = m.group(1).rstrip(".")
    book = _ABBREV.get(abbr, abbr)
    try:
        return (book.upper(), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def build_index(vol_texts: dict[int, str], max_quote_len: int = 400) -> dict:
    """
    Build scripture_ref → [quotes] index from all volume texts.
    Returns { "GENESIS_1_1": [{"vol": int, "text": str}, ...] }
    """
    idx_path = _index_cache()
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))

    index = {}
    for vol_num, text in vol_texts.items():
        # Split into paragraphs
        paragraphs = re.split(r'\n{2,}', text)
        for para in paragraphs:
            refs = _REF_RE.findall(para)
            for raw_ref in refs:
                parsed = _parse_ref(raw_ref)
                if not parsed:
                    continue
                key = f"{parsed[0]}_{parsed[1]}_{parsed[2]}"
                snippet = para.strip()[:max_quote_len].replace('\n', ' ')
                if key not in index:
                    index[key] = []
                # Avoid near-duplicates
                if not any(snippet[:50] in q["text"] for q in index[key]):
                    index[key].append({"vol": vol_num, "text": snippet})

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  JD index: {len(index):,} scripture refs indexed")
    return index


_index: dict = None


def get_quotes(book: str, chapter: int, verse: int, max_quotes: int = 2) -> list[dict]:
    """
    Returns up to max_quotes JD quotes for a scripture reference.
    Each: { "vol": int, "text": str }
    """
    global _index
    if _index is None:
        _index = _load_index()
    if _index is None:
        return []

    key = f"{book.upper()}_{chapter}_{verse}"
    quotes = _index.get(key, [])
    return quotes[:max_quotes]


def _load_index() -> Optional[dict]:
    idx_path = _index_cache()
    if idx_path.exists():
        try:
            return json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None
