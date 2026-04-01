#!/usr/bin/env python3
"""
build_discovery_feed.py
=======================
Build a discovery feed of the strongest cross-tradition verse→source links.

Reads all chapter graph JSON files and finds the highest-scoring connections
where the verse and source passage come from different traditions:
  - LDS scripture (Book of Mormon, D&C, Pearl of Great Price) ↔ Church Fathers
  - LDS scripture ↔ Jewish texts (Philo, Josephus, Pseudepigrapha)
  - Bible (OT/NT) ↔ LDS sources (GC, Journal of Discourses, Talmage)
  - Bible ↔ Ancient Texts

Output: library/discovery_feed.json
Format:
  [
    {
      "score": 0.82,
      "verse_ref": "John 1:1",
      "verse_book": "John",
      "verse_ch": 1,
      "verse_v": 1,
      "verse_text": "In the beginning was the Word...",
      "source": "ancient_texts",
      "source_label": "Philo: On the Creation",
      "source_text": "God is pure intellect...",
      "source_doc_id": "ancient_texts:the_works_of_philo_complete_and_unabridged",
      "source_para": 42,
      "tradition_pair": "NT → Jewish Texts"
    },
    ...
  ]

Run from repo root:
    python3 lds_pipeline/build_discovery_feed.py [--top-n 200]
"""

import json
import re
from collections import defaultdict
from pathlib import Path

REPO       = Path(__file__).parent.parent
CHAPTERS   = REPO / "library" / "chapters"
OUT_FILE   = REPO / "library" / "discovery_feed.json"

# Volume classification for cross-tradition filtering
VOLUMES = {
    # Bible
    "old_testament": [
        "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges",
        "ruth", "1_samuel", "2_samuel", "1_kings", "2_kings", "1_chronicles", "2_chronicles",
        "ezra", "nehemiah", "esther", "job", "psalms", "proverbs", "ecclesiastes",
        "song_of_solomon", "isaiah", "jeremiah", "lamentations", "ezekiel", "daniel",
        "hosea", "joel", "amos", "obadiah", "jonah", "micah", "nahum", "habakkuk",
        "zephaniah", "haggai", "zechariah", "malachi",
    ],
    "new_testament": [
        "matthew", "mark", "luke", "john", "acts", "romans", "1_corinthians",
        "2_corinthians", "galatians", "ephesians", "philippians", "colossians",
        "1_thessalonians", "2_thessalonians", "1_timothy", "2_timothy", "titus",
        "philemon", "hebrews", "james", "1_peter", "2_peter", "1_john", "2_john",
        "3_john", "jude", "revelation",
    ],
    "book_of_mormon": [
        "1_nephi", "2_nephi", "jacob", "enos", "jarom", "omni", "words_of_mormon",
        "mosiah", "alma", "helaman", "3_nephi", "4_nephi", "mormon", "ether", "moroni",
    ],
    "dc_pgp": [
        "doctrine_and_covenants", "moses", "abraham", "joseph_smith_matthew",
        "joseph_smith_history", "articles_of_faith",
    ],
}

SOURCE_TRADITIONS = {
    "church_fathers":        "Church Fathers",
    "ancient_texts":         "Jewish / Ancient Texts",
    "pseudepigrapha":        "Jewish / Ancient Texts",
    "apocrypha":             "Jewish / Ancient Texts",
    "sefaria":               "Jewish / Ancient Texts",
    "journal_of_discourses": "LDS Historical",
    "general_conference":    "LDS General Conference",
    "gutenberg_lds":         "LDS Historical",
    "history_of_church":     "LDS Historical",
    "joseph_smith_papers":   "LDS Historical",
    "millennial_star":       "LDS Historical",
    "times_and_seasons":     "LDS Historical",
    "pioneer_journals":      "LDS Historical",
    "bh_roberts":            "LDS Historical",
    "donaldson":             "LDS Commentary",
    "nauvoo_theology":       "LDS Historical",
    "jst":                   "JST",
    "standard_works":        "Scripture",
    "nag_hammadi":           "Ancient Texts",
    "dead_sea_scrolls":      "Jewish / Ancient Texts",
}


def book_slug_from_file(stem: str) -> str:
    """Extract book slug (lower, underscored) from chapter file stem like 'genesis_1'."""
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0].lower()
    return stem.lower()


def classify_book(book_slug: str) -> str:
    for vol, books in VOLUMES.items():
        if book_slug in books:
            return vol
    return "other"


def classify_verse_tradition(vol: str) -> str:
    if vol == "old_testament":
        return "Old Testament"
    if vol == "new_testament":
        return "New Testament"
    if vol == "book_of_mormon":
        return "Book of Mormon"
    if vol == "dc_pgp":
        return "D&C / Pearl of Great Price"
    return "Scripture"


def is_cross_tradition(verse_vol: str, src: str) -> tuple[bool, str]:
    """Return (is_cross_tradition, description)."""
    vtrad = classify_verse_tradition(verse_vol)
    strad = SOURCE_TRADITIONS.get(src, "")

    if not strad or strad == "Scripture":
        return False, ""

    # Cross-tradition pairs we care about
    pairs = {
        ("New Testament", "Church Fathers"):         "NT → Church Fathers",
        ("New Testament", "Jewish / Ancient Texts"): "NT → Jewish / Ancient Texts",
        ("Old Testament", "Church Fathers"):         "OT → Church Fathers",
        ("Old Testament", "Jewish / Ancient Texts"): "OT → Jewish / Ancient Texts",
        ("Book of Mormon", "Church Fathers"):        "Book of Mormon → Church Fathers",
        ("Book of Mormon", "Jewish / Ancient Texts"):"Book of Mormon → Jewish / Ancient Texts",
        ("D&C / Pearl of Great Price", "Church Fathers"):        "D&C/PGP → Church Fathers",
        ("D&C / Pearl of Great Price", "Jewish / Ancient Texts"):"D&C/PGP → Jewish / Ancient Texts",
        ("Old Testament", "LDS Historical"):         "OT → LDS Historical",
        ("New Testament", "LDS Historical"):         "NT → LDS Historical",
        ("New Testament", "LDS General Conference"): "NT → General Conference",
        ("Old Testament", "LDS General Conference"): "OT → General Conference",
    }
    key = (vtrad, strad)
    if key in pairs:
        return True, pairs[key]
    return False, ""


def book_chapter_from_stem(stem: str) -> tuple[str, int]:
    """Return (book_display_name, chapter) from slug like 'genesis_1'."""
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        book = parts[0].replace("_", " ").title()
        # Fix common capitalizations
        replacements = {
            "Doctrine And Covenants": "D&C",
            "Joseph Smith Matthew": "Joseph Smith—Matthew",
            "Joseph Smith History": "Joseph Smith—History",
            "Articles Of Faith": "Articles of Faith",
        }
        book = replacements.get(book, book)
        return book, int(parts[1])
    return stem, 0


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=300)
    parser.add_argument("--min-score", type=float, default=0.45)
    args = parser.parse_args()

    print(f"Scanning {CHAPTERS}...")
    graph_files = sorted(CHAPTERS.glob("*_graph.json"))

    candidates = []
    seen_pairs = set()

    for gf in graph_files:
        stem = gf.stem.replace("_graph", "")
        book_slug = book_slug_from_file(stem)
        book_vol   = classify_book(book_slug)
        book_name, chapter = book_chapter_from_stem(stem)

        try:
            graph = json.loads(gf.read_text(encoding="utf-8"))
        except Exception:
            continue

        node_map = {n["id"]: n for n in graph.get("nodes", [])}
        verse_nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("t") == "v"}

        for edge in graph.get("edges", []):
            score  = edge.get("w", 0)
            if score < args.min_score:
                continue

            vnode = verse_nodes.get(edge.get("s", ""))
            pnode = node_map.get(edge.get("t", ""))
            if not vnode or not pnode or pnode.get("t") != "p":
                continue

            src = pnode.get("src", "")
            is_cross, pair_label = is_cross_tradition(book_vol, src)
            if not is_cross:
                continue

            verse_num  = vnode.get("n", 0)
            verse_text = vnode.get("x", "")
            verse_ref  = f"{book_name} {chapter}:{verse_num}"

            # Deduplicate: same verse + same source passage
            pair_key = (verse_ref, pnode.get("lb", ""), pnode.get("src", ""))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            candidates.append({
                "score":          score,
                "verse_ref":      verse_ref,
                "verse_book":     book_name,
                "verse_ch":       chapter,
                "verse_v":        verse_num,
                "verse_text":     verse_text[:200],
                "source":         src,
                "source_label":   pnode.get("lb", ""),
                "source_text":    pnode.get("x", "")[:300],
                "source_doc_id":  pnode.get("d", ""),
                "source_para":    pnode.get("p"),
                "tradition_pair": pair_label,
            })

    # Sort by score descending
    candidates.sort(key=lambda x: -x["score"])
    top = candidates[:args.top_n]

    OUT_FILE.write_text(
        json.dumps(top, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Print summary by tradition pair
    by_pair = defaultdict(list)
    for c in top:
        by_pair[c["tradition_pair"]].append(c)
    print(f"\nTop {len(top)} cross-tradition connections written to {OUT_FILE}")
    print("\nBreakdown by tradition pair:")
    for pair, entries in sorted(by_pair.items(), key=lambda x: -len(x[1])):
        top3 = entries[:3]
        print(f"  {pair}: {len(entries)} entries")
        for e in top3:
            print(f"    {e['verse_ref']} → {e['source_label'][:40]} ({e['score']:.2f})")


if __name__ == "__main__":
    main()
