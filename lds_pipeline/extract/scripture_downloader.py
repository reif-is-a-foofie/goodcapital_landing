"""
Download all 5 LDS standard works as structured JSON from bcbooks/scriptures-json.

Returns clean Volume/Book/Chapter/Verse objects compatible with the existing
donaldson_parser data structures, so the same epub builder renders everything.

For OT: we prefer the Donaldson compilation (already rich with commentary).
For NT, BoM, D&C, PGP: we use this clean JSON and apply the full enrichment
pipeline (McConkie DNTC for NT, JSP for D&C, etc.).
"""

import json
import re
import urllib.request
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Reuse dataclasses from donaldson_parser
from extract.donaldson_parser import (
    Verse, Chapter, Book, Volume,
    BOOK_TO_VOLUME, OT_BOOKS, NT_BOOKS, BOM_BOOKS, PGP_BOOKS
)

CACHE_DIR = Path("/Users/reify/lds_pipeline/cache/scriptures_json")

SCRIPTURE_URLS = {
    "Old Testament":          "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/old-testament.json",
    "New Testament":          "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/new-testament.json",
    "Book of Mormon":         "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/book-of-mormon.json",
    "Doctrine and Covenants": "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/doctrine-and-covenants.json",
    "Pearl of Great Price":   "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/pearl-of-great-price.json",
}


def _cache_path(vol_name: str) -> Path:
    safe = re.sub(r'[^\w]', '_', vol_name)
    return CACHE_DIR / f"{safe}.json"


def download_volume_json(vol_name: str, no_net: bool = False) -> Optional[dict]:
    cache = _cache_path(vol_name)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 1000:
        return json.loads(cache.read_text(encoding="utf-8"))

    if no_net:
        print(f"  {vol_name}: not cached, skipping (--no-net)")
        return None

    url = SCRIPTURE_URLS[vol_name]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"  Downloaded: {vol_name}")
        return data
    except Exception as e:
        print(f"  Failed {vol_name}: {e}")
        return None


def parse_json_volume(vol_name: str, data: dict) -> Volume:
    """
    Parse bcbooks JSON format into Volume object.

    bcbooks format:
    {
      "books": [
        {
          "book": "Genesis",
          "chapters": [
            {
              "chapter": 1,
              "verses": [
                {"verse": 1, "text": "In the beginning..."},
                ...
              ]
            }
          ]
        }
      ]
    }
    """
    volume = Volume(name=vol_name)

    def _make_verse(book_name, ch_num, v_data):
        # verse number may be in 'verse' or parsed from 'reference' (e.g. "D&C 1:1")
        v_num = v_data.get("verse", 0)
        if not v_num:
            ref = v_data.get("reference", "")
            m = re.search(r':(\d+)$', ref)
            v_num = int(m.group(1)) if m else 0
        return Verse(
            book=book_name, chapter=ch_num, verse=v_num,
            volume=vol_name, text=v_data.get("text", "").strip(),
            jst=None, word_studies=[], commentary=[],
        )

    # Standard format: {books: [{book, chapters: [{chapter, verses}]}]}
    if "books" in data:
        for book_data in data["books"]:
            book_name = book_data.get("book", "")
            book = Book(name=book_name, volume=vol_name)
            for ch_data in book_data.get("chapters", []):
                ch_num  = ch_data.get("chapter", 0)
                chapter = Chapter(book=book_name, number=ch_num, volume=vol_name, heading="")
                for v_data in ch_data.get("verses", []):
                    chapter.verses.append(_make_verse(book_name, ch_num, v_data))
                book.chapters.append(chapter)
            volume.books.append(book)

    # D&C format: {sections: [{section, verses}]}
    elif "sections" in data:
        book = Book(name="Doctrine and Covenants", volume=vol_name)
        for sec_data in data["sections"]:
            ch_num  = sec_data.get("section", 0)
            chapter = Chapter(book="Doctrine and Covenants", number=ch_num,
                              volume=vol_name, heading="")
            for v_data in sec_data.get("verses", []):
                chapter.verses.append(_make_verse("Doctrine and Covenants", ch_num, v_data))
            book.chapters.append(chapter)
        volume.books.append(book)

    return volume


def download_all_volumes(skip_ot: bool = True, no_net: bool = False) -> list[Volume]:
    """
    Download and parse all standard works.
    skip_ot: if True, skip OT (use Donaldson compilation instead).
    Returns list of Volume objects.
    """
    volumes = []
    order = [
        "Old Testament",
        "New Testament",
        "Book of Mormon",
        "Doctrine and Covenants",
        "Pearl of Great Price",
    ]

    for vol_name in order:
        if skip_ot and vol_name == "Old Testament":
            print(f"  Skipping {vol_name} (using Donaldson compilation)")
            continue

        data = download_volume_json(vol_name, no_net=no_net)
        if not data:
            continue

        vol = parse_json_volume(vol_name, data)
        total_verses = sum(
            len(ch.verses) for b in vol.books for ch in b.chapters
        )
        print(f"  {vol_name}: {len(vol.books)} books, {total_verses:,} verses")
        volumes.append(vol)

    return volumes


# ── Additional source maps for non-OT volumes ─────────────────────────────────

# NT: McConkie DNTC is verse-organized commentary
# BoM: Hugh Nibley has extensive BoM works; FAIR LDS has commentary
# D&C: Joseph Smith Papers has original revelation records per section
# PGP: Book of Abraham connects to Egyptian sources via Nibley

VOLUME_SOURCE_HINTS = {
    "New Testament": ["mcconkie", "sefaria_rashi", "general_conference",
                      "journal_of_discourses", "josephus"],
    "Book of Mormon": ["general_conference", "journal_of_discourses",
                       "history_of_church", "joseph_smith_papers",
                       "words_joseph_smith"],
    "Doctrine and Covenants": ["joseph_smith_papers", "words_joseph_smith",
                                "history_of_church", "wilford_woodruff",
                                "william_clayton", "general_conference"],
    "Pearl of Great Price": ["joseph_smith_papers", "ancient_myths",
                              "book_of_enoch", "book_of_jubilees",
                              "josephus", "general_conference"],
}
