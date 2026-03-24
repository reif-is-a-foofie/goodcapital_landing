"""
Verse Catalog — persistent JSON layer between parsing and enrichment.

Saves the full parsed verse structure (book/chapter/verse/text/jst/donaldson)
to cache/verse_catalog.json after Stage 2. This is the foundation everything
else builds on. Sources read this and write their own enrichment caches.

Schema per verse:
  {
    "book":      "Genesis",
    "chapter":   1,
    "verse":     1,
    "volume":    "Old Testament",
    "text":      "IN the beginning...",
    "jst":       "...",                 # null if absent
    "donaldson": ["para1", "para2"]     # Donaldson inline commentary
  }
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from extract.donaldson_parser import Volume

CATALOG_PATH = Path("/Users/reify/lds_pipeline/cache/verse_catalog.json")


def save_catalog(volumes: list) -> Path:
    """Serialize parsed volumes to JSON catalog. Returns path written."""
    records = []
    for vol in volumes:
        for book in vol.books:
            for ch in book.chapters:
                for v in ch.verses:
                    records.append({
                        "book":      v.book,
                        "chapter":   v.chapter,
                        "verse":     v.verse,
                        "volume":    v.volume,
                        "text":      v.text,
                        "jst":       v.jst,
                        "donaldson": getattr(v, "donaldson", []),
                    })
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  Catalog saved: {len(records):,} verses → {CATALOG_PATH}")
    return CATALOG_PATH


def load_catalog() -> list[dict]:
    """Load catalog from JSON. Returns list of verse dicts."""
    if not CATALOG_PATH.exists():
        return []
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_to_volumes(records: list[dict]):
    """Reconstruct lightweight Volume/Book/Chapter/Verse objects from catalog."""
    from extract.donaldson_parser import Volume, Book, Chapter, Verse
    from dataclasses import field

    volumes_map: dict[str, Volume] = {}
    books_map:   dict[str, Book]   = {}
    chaps_map:   dict[tuple, Chapter] = {}

    for r in records:
        vol_name  = r["volume"]
        book_name = r["book"]
        ch_num    = r["chapter"]
        v_num     = r["verse"]

        if vol_name not in volumes_map:
            volumes_map[vol_name] = Volume(name=vol_name)

        bk_key = f"{vol_name}|{book_name}"
        if bk_key not in books_map:
            bk = Book(name=book_name, volume=vol_name)
            volumes_map[vol_name].books.append(bk)
            books_map[bk_key] = bk

        ch_key = (vol_name, book_name, ch_num)
        if ch_key not in chaps_map:
            ch = Chapter(book=book_name, number=ch_num, volume=vol_name, heading="")
            books_map[bk_key].chapters.append(ch)
            chaps_map[ch_key] = ch

        verse = Verse(
            book=book_name,
            chapter=ch_num,
            verse=v_num,
            volume=vol_name,
            text=r.get("text", ""),
            jst=r.get("jst"),
            donaldson=r.get("donaldson", []),
        )
        chaps_map[ch_key].verses.append(verse)

    order = ["Old Testament", "New Testament", "Book of Mormon",
             "Doctrine and Covenants", "Pearl of Great Price"]
    return [volumes_map[n] for n in order if n in volumes_map]
