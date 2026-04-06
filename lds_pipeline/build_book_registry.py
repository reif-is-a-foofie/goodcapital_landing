#!/usr/bin/env python3
"""
build_book_registry.py
Builds library/entities/books.json — one entry per canonical scripture book.
"""

import json
import os
import re
import glob as glob_module

BASE_DIR = "/Users/reify/Classified/goodcapital_landing"
TOC_PATH = os.path.join(BASE_DIR, "library/toc.json")
DONALDSON_DIR = os.path.join(BASE_DIR, "library/donaldson")
PEOPLE_PATH = os.path.join(BASE_DIR, "library/entities/people.json")
OUT_PATH = os.path.join(BASE_DIR, "library/entities/books.json")

# ── Testament mapping ──────────────────────────────────────────────────────────

OT = {
    "genesis","exodus","leviticus","numbers","deuteronomy","joshua","judges",
    "ruth","1_samuel","2_samuel","1_kings","2_kings","1_chronicles","2_chronicles",
    "ezra","nehemiah","esther","job","psalms","proverbs","ecclesiastes",
    "song_of_solomon","isaiah","jeremiah","lamentations","ezekiel","daniel",
    "hosea","joel","amos","obadiah","jonah","micah","nahum","habakkuk",
    "zephaniah","haggai","zechariah","malachi",
}
NT = {
    "matthew","mark","luke","john","acts","romans","1_corinthians","2_corinthians",
    "galatians","ephesians","philippians","colossians","1_thessalonians",
    "2_thessalonians","1_timothy","2_timothy","titus","philemon","hebrews",
    "james","1_peter","2_peter","1_john","2_john","3_john","jude","revelation",
}
BOM = {
    "1_nephi","2_nephi","jacob","enos","jarom","omni","words_of_mormon",
    "mosiah","alma","helaman","3_nephi","4_nephi","mormon","ether","moroni",
}
DC = {"doctrine_and_covenants","joseph_smith_history","joseph_smith_matthew","articles_of_faith"}
PGP = {"moses","abraham"}

def get_testament(slug):
    if slug in OT:  return "OT"
    if slug in NT:  return "NT"
    if slug in BOM: return "BOM"
    if slug in DC:  return "DC"
    if slug in PGP: return "PGP"
    return "OTHER"

# ── Display name helpers ───────────────────────────────────────────────────────

SPECIAL_NAMES = {
    "doctrine_and_covenants": "Doctrine and Covenants",
    "joseph_smith_history": "Joseph Smith—History",
    "joseph_smith_matthew": "Joseph Smith—Matthew",
    "articles_of_faith": "Articles of Faith",
    "words_of_mormon": "Words of Mormon",
    "song_of_solomon": "Song of Solomon",
}

ABBREVIATIONS = {
    "genesis":"Gen","exodus":"Ex","leviticus":"Lev","numbers":"Num",
    "deuteronomy":"Deut","joshua":"Josh","judges":"Judg","ruth":"Ruth",
    "1_samuel":"1 Sam","2_samuel":"2 Sam","1_kings":"1 Kgs","2_kings":"2 Kgs",
    "1_chronicles":"1 Chr","2_chronicles":"2 Chr","ezra":"Ezra","nehemiah":"Neh",
    "esther":"Esth","job":"Job","psalms":"Ps","proverbs":"Prov",
    "ecclesiastes":"Eccl","song_of_solomon":"Song","isaiah":"Isa",
    "jeremiah":"Jer","lamentations":"Lam","ezekiel":"Ezek","daniel":"Dan",
    "hosea":"Hos","joel":"Joel","amos":"Amos","obadiah":"Obad","jonah":"Jon",
    "micah":"Mic","nahum":"Nah","habakkuk":"Hab","zephaniah":"Zeph",
    "haggai":"Hag","zechariah":"Zech","malachi":"Mal",
    "matthew":"Matt","mark":"Mark","luke":"Luke","john":"John","acts":"Acts",
    "romans":"Rom","1_corinthians":"1 Cor","2_corinthians":"2 Cor",
    "galatians":"Gal","ephesians":"Eph","philippians":"Phil","colossians":"Col",
    "1_thessalonians":"1 Thes","2_thessalonians":"2 Thes","1_timothy":"1 Tim",
    "2_timothy":"2 Tim","titus":"Tit","philemon":"Philem","hebrews":"Heb",
    "james":"Jas","1_peter":"1 Pet","2_peter":"2 Pet","1_john":"1 Jn",
    "2_john":"2 Jn","3_john":"3 Jn","jude":"Jude","revelation":"Rev",
    "1_nephi":"1 Ne","2_nephi":"2 Ne","jacob":"Jacob","enos":"Enos",
    "jarom":"Jarom","omni":"Omni","words_of_mormon":"W of M","mosiah":"Mosiah",
    "alma":"Alma","helaman":"Hel","3_nephi":"3 Ne","4_nephi":"4 Ne",
    "mormon":"Morm","ether":"Ether","moroni":"Moro",
    "doctrine_and_covenants":"D&C","joseph_smith_history":"JS—H",
    "joseph_smith_matthew":"JS—M","articles_of_faith":"A of F",
    "moses":"Moses","abraham":"Abr",
}

def make_display_name(slug):
    if slug in SPECIAL_NAMES:
        return SPECIAL_NAMES[slug]
    # Handle numbered books like "1_nephi" -> "1 Nephi"
    m = re.match(r'^(\d+)_(.+)$', slug)
    if m:
        num = m.group(1)
        rest = " ".join(w.capitalize() for w in m.group(2).split("_"))
        return f"{num} {rest}"
    return " ".join(w.capitalize() for w in slug.split("_"))

# ── make_id: same logic as entity registry ────────────────────────────────────

def make_person_id(name: str) -> str:
    s = name.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return f"person:{s}"

# ── Load people index ──────────────────────────────────────────────────────────

people_data = json.load(open(PEOPLE_PATH))
# Build name -> id map (including variants)
name_to_id: dict[str, str] = {}
for p in people_data:
    name_to_id[p["name"].lower()] = p["id"]
    for v in p.get("variants", []):
        name_to_id[v.lower()] = p["id"]

def resolve_person_id(speaker_name: str) -> str:
    lo = speaker_name.lower().strip()
    if lo in name_to_id:
        return name_to_id[lo]
    # fallback: make_id style
    return make_person_id(speaker_name)

# ── Load TOC ───────────────────────────────────────────────────────────────────

toc = json.load(open(TOC_PATH))

# Derive book -> [chapter_ids] from chapter entries
CHAPTER_RE = re.compile(r'^(.+?)_(\d+)$')

book_chapters: dict[str, list[str]] = {}
for entry in toc:
    if entry.get("type") == "chapter" and entry.get("id"):
        cid = entry["id"]
        m = CHAPTER_RE.match(cid)
        if m:
            bslug = m.group(1)
            if bslug not in book_chapters:
                book_chapters[bslug] = []
            book_chapters[bslug].append(cid)

print(f"Found {len(book_chapters)} books in TOC")

# ── Build registry ─────────────────────────────────────────────────────────────

books_out = []

for slug, chapter_ids in sorted(book_chapters.items()):
    # Collect donaldson files for this book
    pattern = os.path.join(DONALDSON_DIR, f"{slug}_*.json")
    don_files = sorted(glob_module.glob(pattern))

    related_people_ids: set[str] = set()
    description_excerpts: list[dict] = []
    donaldson_chapter_count = len(don_files)

    for fpath in don_files:
        try:
            verse_data = json.load(open(fpath))
        except Exception:
            continue
        for verse_num, verse in verse_data.items():
            for q in verse.get("quotes", []):
                speaker = q.get("speaker", "")
                if speaker:
                    pid = resolve_person_id(speaker)
                    related_people_ids.add(pid)
                    if len(description_excerpts) < 5:
                        description_excerpts.append({
                            "text": q.get("text", "")[:500],
                            "speaker": pid,
                            "attr": q.get("attr", ""),
                            "source": q.get("type", "gc"),
                        })

    books_out.append({
        "id": f"book:{slug}",
        "name": make_display_name(slug),
        "abbreviation": ABBREVIATIONS.get(slug, make_display_name(slug)),
        "slug": slug,
        "testament": get_testament(slug),
        "chapter_ids": chapter_ids,
        "donaldson_chapter_count": donaldson_chapter_count,
        "related_people": sorted(related_people_ids),
        "related_places": [],
        "related_things": [],
        "description_excerpts": description_excerpts,
    })

# ── Write output ───────────────────────────────────────────────────────────────

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w") as f:
    json.dump(books_out, f, indent=2, ensure_ascii=False)

print(f"\nWrote {len(books_out)} books to {OUT_PATH}")

# ── Summary ────────────────────────────────────────────────────────────────────

with_coverage = [b for b in books_out if b["donaldson_chapter_count"] > 0]
print(f"Books with Donaldson coverage: {len(with_coverage)} / {len(books_out)}")

top5 = sorted(books_out, key=lambda b: len(b["related_people"]), reverse=True)[:5]
print("\nTop 5 books by related_people count:")
for b in top5:
    print(f"  {b['name']:<35} {len(b['related_people'])} people, {b['donaldson_chapter_count']} donaldson chapters")
