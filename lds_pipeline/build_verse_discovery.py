#!/usr/bin/env python3
"""
build_verse_discovery.py
========================
Build a verse-indexed cross-tradition discovery map.

Scans all chapter graph JSON files and collects cross-tradition source passage
links for every verse that has them.

Output: library/verse_discovery.json
Format:
  {
    "Genesis 1:1": [
      {
        "score": 0.75,
        "source": "church_fathers",
        "source_label": "Philo: On the Creation §1",
        "source_text": "In the beginning God made the heaven...",
        "source_doc_id": "ancient_texts:philo_on_creation",
        "source_para": 42,
        "tradition_pair": "OT → Jewish / Ancient Texts"
      }
    ]
  }

Each verse lists its top cross-tradition connections (up to MAX_PER_VERSE),
sorted by score descending.

Run from repo root:
    python3 lds_pipeline/build_verse_discovery.py [--min-score 0.40]
"""

import json
import re
from collections import defaultdict
from pathlib import Path

REPO      = Path(__file__).parent.parent
CHAPTERS  = REPO / "library" / "chapters"
OUT_FILE  = REPO / "library" / "verse_discovery.json"

MAX_PER_VERSE = 8   # max cross-tradition passages per verse

# ── Reuse classification from build_discovery_feed.py ─────────────────────────

VOLUMES = {
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

CROSS_TRADITION_PAIRS = {
    ("New Testament",          "Church Fathers"):          "NT → Church Fathers",
    ("New Testament",          "Jewish / Ancient Texts"):  "NT → Jewish / Ancient Texts",
    ("Old Testament",          "Church Fathers"):          "OT → Church Fathers",
    ("Old Testament",          "Jewish / Ancient Texts"):  "OT → Jewish / Ancient Texts",
    ("Book of Mormon",         "Church Fathers"):          "Book of Mormon → Church Fathers",
    ("Book of Mormon",         "Jewish / Ancient Texts"):  "Book of Mormon → Jewish / Ancient Texts",
    ("D&C / Pearl of Great Price", "Church Fathers"):      "D&C/PGP → Church Fathers",
    ("D&C / Pearl of Great Price", "Jewish / Ancient Texts"): "D&C/PGP → Jewish / Ancient Texts",
    ("Old Testament",          "LDS Historical"):          "OT → LDS Historical",
    ("New Testament",          "LDS Historical"):          "NT → LDS Historical",
    ("New Testament",          "LDS General Conference"):  "NT → General Conference",
    ("Old Testament",          "LDS General Conference"):  "OT → General Conference",
    ("Book of Mormon",         "LDS Historical"):          "Book of Mormon → LDS Historical",
    ("Book of Mormon",         "LDS General Conference"):  "Book of Mormon → General Conference",
    ("D&C / Pearl of Great Price", "LDS Historical"):      "D&C/PGP → LDS Historical",
    ("D&C / Pearl of Great Price", "LDS General Conference"): "D&C/PGP → General Conference",
}


def book_slug_from_stem(stem: str) -> str:
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0].lower()
    return stem.lower()


def classify_volume(book_slug: str) -> str:
    for vol, books in VOLUMES.items():
        if book_slug in books:
            return vol
    return "other"


VERSE_TRADITION = {
    "old_testament":  "Old Testament",
    "new_testament":  "New Testament",
    "book_of_mormon": "Book of Mormon",
    "dc_pgp":         "D&C / Pearl of Great Price",
}

BOOK_DISPLAY = {
    "Doctrine And Covenants": "D&C",
    "Joseph Smith Matthew":   "Joseph Smith—Matthew",
    "Joseph Smith History":   "Joseph Smith—History",
    "Articles Of Faith":      "Articles of Faith",
    "Song Of Solomon":        "Song of Solomon",
    "Words Of Mormon":        "Words of Mormon",
}


def book_name_from_stem(stem: str) -> tuple[str, int]:
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        raw = parts[0].replace("_", " ").title()
        return BOOK_DISPLAY.get(raw, raw), int(parts[1])
    return stem, 0


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=float, default=0.40)
    args = parser.parse_args()

    print(f"Scanning {CHAPTERS}...")
    graph_files = sorted(CHAPTERS.glob("*_graph.json"))
    print(f"  {len(graph_files):,} chapter graph files")

    # verse_ref → list of cross-tradition entries (deduped by doc+para)
    index: dict[str, list] = defaultdict(list)
    seen_pairs: set = set()

    for gf in graph_files:
        stem     = gf.stem.replace("_graph", "")
        book_slug = book_slug_from_stem(stem)
        vol       = classify_volume(book_slug)
        vtrad     = VERSE_TRADITION.get(vol, "")
        if not vtrad:
            continue  # skip books we don't classify

        book_name, chapter = book_name_from_stem(stem)

        try:
            graph = json.loads(gf.read_text(encoding="utf-8"))
        except Exception:
            continue

        node_map    = {n["id"]: n for n in graph.get("nodes", [])}
        verse_nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("t") == "v"}

        for edge in graph.get("edges", []):
            score = edge.get("w", 0)
            if score < args.min_score:
                continue

            vnode = verse_nodes.get(edge.get("s", ""))
            pnode = node_map.get(edge.get("t", ""))
            if not vnode or not pnode or pnode.get("t") != "p":
                continue

            src   = pnode.get("src", "")
            strad = SOURCE_TRADITIONS.get(src, "")
            if not strad or strad == "Scripture":
                continue

            pair_label = CROSS_TRADITION_PAIRS.get((vtrad, strad), "")
            if not pair_label:
                continue

            verse_num = vnode.get("n", 0)
            verse_ref = f"{book_name} {chapter}:{verse_num}"

            # Deduplicate by verse + doc + para (fall back to label when d/p absent)
            pair_key = (verse_ref, pnode.get("d", "") or pnode.get("lb", ""), pnode.get("p"))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            index[verse_ref].append({
                "score":          score,
                "source":         src,
                "source_label":   pnode.get("lb", ""),
                "source_text":    pnode.get("x", "")[:300],
                "source_doc_id":  pnode.get("d", ""),
                "source_para":    pnode.get("p"),
                "tradition_pair": pair_label,
            })

    # Sort each verse's entries by score, keep top MAX_PER_VERSE
    output = {}
    for verse_ref, entries in sorted(index.items()):
        entries.sort(key=lambda x: -x["score"])
        output[verse_ref] = entries[:MAX_PER_VERSE]

    OUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    from collections import Counter
    pair_counts = Counter(
        e["tradition_pair"]
        for entries in output.values()
        for e in entries
    )
    print(f"\nVerse discovery index: {len(output):,} verses → {OUT_FILE}")
    print("\nCross-tradition pairs:")
    for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
        print(f"  {pair}: {count:,} connections across {sum(1 for v in output.values() if any(e['tradition_pair']==pair for e in v)):,} verses")


if __name__ == "__main__":
    main()
