"""
Download all LDS Standard Works from churchofjesuschrist.org study API.

Produces:
  cache/standard_works/{work_key}.json  — per-work list of verse dicts
  cache/standard_works/verse_catalog.json — full flat list (replaces PDF-extracted catalog)

Each verse dict:
  { "volume": str, "book": str, "chapter": int, "verse": int, "text": str, "uri": str }

Run:
  python3 sync_standard_works.py [--rebuild]
"""

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache")
OUT_DIR   = CACHE_DIR / "standard_works"
BASE_API  = "https://www.churchofjesuschrist.org/study/api/v3/language-pages/type/content"

WORKS = [
    ("Old Testament",         "ot",          "/scriptures/ot"),
    ("New Testament",         "nt",          "/scriptures/nt"),
    ("Book of Mormon",        "bofm",        "/scriptures/bofm"),
    ("Doctrine and Covenants","dc-testament","/scriptures/dc-testament"),
    ("Pearl of Great Price",  "pgp",         "/scriptures/pgp"),
]

# URI slug → canonical book name (from existing catalog)
SLUG_TO_BOOK = {
    "gen": "Genesis", "ex": "Exodus", "lev": "Leviticus", "num": "Numbers",
    "deut": "Deuteronomy", "josh": "Joshua", "judg": "Judges", "ruth": "Ruth",
    "1-sam": "1 Samuel", "2-sam": "2 Samuel", "1-kgs": "1 Kings", "2-kgs": "2 Kings",
    "1-chr": "1 Chronicles", "2-chr": "2 Chronicles", "ezra": "Ezra", "neh": "Nehemiah",
    "esth": "Esther", "job": "Job", "ps": "Psalms", "prov": "Proverbs",
    "eccl": "Ecclesiastes", "song": "Song of Solomon", "isa": "Isaiah",
    "jer": "Jeremiah", "lam": "Lamentations", "ezek": "Ezekiel", "dan": "Daniel",
    "hosea": "Hosea", "joel": "Joel", "amos": "Amos", "obad": "Obadiah",
    "jonah": "Jonah", "micah": "Micah", "nahum": "Nahum", "hab": "Habakkuk",
    "zeph": "Zephaniah", "hag": "Haggai", "zech": "Zechariah", "mal": "Malachi",
    "matt": "Matthew", "mark": "Mark", "luke": "Luke", "john": "John",
    "acts": "Acts", "rom": "Romans", "1-cor": "1 Corinthians", "2-cor": "2 Corinthians",
    "gal": "Galatians", "eph": "Ephesians", "philip": "Philippians", "col": "Colossians",
    "1-thes": "1 Thessalonians", "2-thes": "2 Thessalonians",
    "1-tim": "1 Timothy", "2-tim": "2 Timothy", "titus": "Titus",
    "philem": "Philemon", "heb": "Hebrews", "james": "James",
    "1-pet": "1 Peter", "2-pet": "2 Peter", "1-jn": "1 John",
    "2-jn": "2 John", "3-jn": "3 John", "jude": "Jude", "rev": "Revelation",
    "1-ne": "1 Nephi", "2-ne": "2 Nephi", "jacob": "Jacob", "enos": "Enos",
    "jarom": "Jarom", "omni": "Omni", "w-of-m": "Words of Mormon", "mosiah": "Mosiah",
    "alma": "Alma", "hel": "Helaman", "3-ne": "3 Nephi", "4-ne": "4 Nephi",
    "morm": "Mormon", "ether": "Ether", "moro": "Moroni",
    "dc": "Doctrine and Covenants",
    "moses": "Moses", "abr": "Abraham", "js-m": "Joseph Smith—Matthew",
    "js-h": "Joseph Smith—History", "a-of-f": "Articles of Faith",
}


def fetch(uri: str, retries: int = 3) -> bytes:
    url = f"{BASE_API}?lang=eng&uri={uri}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def get_chapter_uris(work_uri: str) -> list[str]:
    """Return all /study/scriptures/... chapter URIs from a work's TOC."""
    data = json.loads(fetch(work_uri))
    body = data.get("content", {}).get("body", "")
    links = re.findall(r'href=\"(/study/scriptures/[^\"?]+)(?:\?[^\"]*)?\"', body)
    return [l for l in links if re.search(r"/\d+$", l)]


def parse_verses(body: str) -> list[tuple[int, str]]:
    """Extract (verse_num, text) from chapter HTML body."""
    raw = re.findall(r'<p[^>]+id="p(\d+)"[^>]*>(.*?)</p>', body, re.DOTALL)
    results = []
    for num_str, html in raw:
        text = re.sub(r"<[^>]+>", "", html).strip()
        # Strip leading verse number (e.g. "1 In the beginning...")
        text = re.sub(r"^\d+\s+", "", text).strip()
        if text:
            results.append((int(num_str), text))
    return results


def slug_to_book(slug: str) -> str:
    if slug in SLUG_TO_BOOK:
        return SLUG_TO_BOOK[slug]
    # Fallback: title-case the slug
    return slug.replace("-", " ").title()


def download_work(volume: str, work_key: str, work_uri: str,
                  out_file: Path, rebuild: bool = False) -> list[dict]:
    if not rebuild and out_file.exists():
        print(f"  {volume}: cached ({out_file.name})")
        return json.loads(out_file.read_text(encoding="utf-8"))

    print(f"  {volume}: fetching chapter list...", flush=True)
    chapter_uris = get_chapter_uris(work_uri)
    print(f"  {volume}: {len(chapter_uris)} chapters", flush=True)

    verses = []
    for i, ch_uri in enumerate(chapter_uris):
        # ch_uri like /study/scriptures/bofm/1-ne/1
        parts = ch_uri.rstrip("/").split("/")
        ch_num = int(parts[-1])
        book_slug = parts[-2]
        book_name = slug_to_book(book_slug)

        try:
            api_uri = ch_uri.replace("/study", "")
            data = json.loads(fetch(api_uri))
            body = data.get("content", {}).get("body", "")
            verse_pairs = parse_verses(body)
            for v_num, v_text in verse_pairs:
                verses.append({
                    "volume":  volume,
                    "book":    book_name,
                    "chapter": ch_num,
                    "verse":   v_num,
                    "text":    v_text,
                    "uri":     ch_uri,
                })
            time.sleep(0.15)
        except Exception as e:
            print(f"    WARN {ch_uri}: {e}")

        if (i + 1) % 100 == 0:
            print(f"  {volume}: {i+1}/{len(chapter_uris)} chapters...", flush=True)

    out_file.write_text(json.dumps(verses, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {volume}: {len(verses):,} verses → {out_file.name}")
    return verses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Re-download even if cached")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_verses = []
    for volume, work_key, work_uri in WORKS:
        out_file = OUT_DIR / f"{work_key}.json"
        vv = download_work(volume, work_key, work_uri, out_file, rebuild=args.rebuild)
        all_verses.extend(vv)

    # Write unified catalog (replaces cache/verse_catalog.json structure)
    catalog_out = OUT_DIR / "verse_catalog.json"
    catalog_out.write_text(json.dumps(all_verses, ensure_ascii=False), encoding="utf-8")
    print(f"\nTotal: {len(all_verses):,} verses → {catalog_out}")

    # Stats by volume
    by_vol = {}
    for v in all_verses:
        by_vol.setdefault(v["volume"], 0)
        by_vol[v["volume"]] += 1
    for vol, n in by_vol.items():
        print(f"  {vol}: {n:,}")


if __name__ == "__main__":
    main()
