"""
History of the Church — B.H. Roberts, 7 volumes, public domain.

Fetches HTML from Project Gutenberg (volumes 1-6) and Archive.org (vol 7),
strips markup, and builds a scripture-reference index identical in structure
to the Journal of Discourses indexer.

Gutenberg IDs:
  Vol 1: 47091   Vol 2: 47745   Vol 3: 48080
  Vol 4: 48289   Vol 5: 48290   Vol 6: 48419
  Vol 7: Archive.org (identifier: HistoryOfTheChurchVol7)
"""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/hoc")

GUTENBERG_VOLUMES = {
    1: "https://www.gutenberg.org/files/47091/47091-0.txt",
    2: "https://www.gutenberg.org/files/47745/47745-0.txt",
    3: "https://www.gutenberg.org/files/48080/48080-0.txt",
    4: "https://www.gutenberg.org/files/48289/48289-0.txt",
    5: "https://www.gutenberg.org/files/48290/48290-0.txt",
    6: "https://www.gutenberg.org/files/48419/48419-0.txt",
}

ARCHIVE_VOL7 = (
    "https://archive.org/download/"
    "HistoryOfTheChurchhcVolumes1-7original1902EditionPdf/"
    "HistoryOfTheChurchhcVolumes1-7original1902EditionPdf_djvu.txt"
)


def _cache_path(vol: int) -> Path:
    return CACHE_DIR / f"vol_{vol}.txt"


def _index_cache() -> Path:
    return CACHE_DIR / "scripture_index.json"


def download_volume(vol: int) -> Optional[str]:
    cache = _cache_path(vol)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(encoding="utf-8", errors="replace")

    url = GUTENBERG_VOLUMES.get(vol)
    if vol == 7:
        url = ARCHIVE_VOL7

    if not url:
        return None

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "LDS-Pipeline/1.0",
            "Accept": "text/plain,text/html;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", errors="replace")
        # Strip HTML tags if present
        clean = re.sub(r'<[^>]+>', ' ', raw)
        clean = re.sub(r'&[a-zA-Z]+;', ' ', clean)
        clean = re.sub(r' {2,}', ' ', clean)
        cache.write_text(clean, encoding="utf-8")
        print(f"  HoC Vol {vol}: {len(clean):,} chars cached")
        return clean
    except Exception as e:
        print(f"  HoC Vol {vol}: failed — {e}")
        return None


def download_all_volumes() -> dict[int, str]:
    result = {}
    for v in range(1, 8):
        text = download_volume(v)
        if text:
            result[v] = text
    return result


# ── Reference parsing (shared pattern with JD) ───────────────────────────────

_REF_RE = re.compile(
    r'\b((?:\d\s)?[A-Z][a-z]+\.?\s+\d+:\d+(?:[-–]\d+)?)',
    re.MULTILINE
)

_ABBREV = {
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Leviticus",
    "Num": "Numbers", "Deut": "Deuteronomy", "Josh": "Joshua",
    "Judg": "Judges", "Isa": "Isaiah", "Jer": "Jeremiah",
    "Ezek": "Ezekiel", "Dan": "Daniel", "Ps": "Psalms",
    "Prov": "Proverbs", "Matt": "Matthew", "Mk": "Mark",
    "Lk": "Luke", "Jn": "John", "Rom": "Romans",
    "Gal": "Galatians", "Eph": "Ephesians", "Heb": "Hebrews",
    "Jas": "James", "Rev": "Revelation",
    "Ne": "Nephi", "Mosiah": "Mosiah", "Alma": "Alma",
    "DC": "Doctrine and Covenants", "D&C": "Doctrine and Covenants",
}


def _parse_ref(raw: str) -> Optional[tuple]:
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
    idx_path = _index_cache()
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))

    index = {}
    for vol_num, text in vol_texts.items():
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
                if not any(snippet[:50] in q["text"] for q in index[key]):
                    index[key].append({"vol": vol_num, "text": snippet})

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  HoC index: {len(index):,} refs indexed")
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
