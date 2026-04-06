#!/usr/bin/env python3
"""
build_place_registry.py

Scans the Donaldson corpus for place mentions and outputs:
  library/entities/places.json
  library/entities/places_index.json
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path("/Users/reify/Classified/goodcapital_landing")
DONALDSON_DIR = BASE_DIR / "library" / "donaldson"
ENTITIES_DIR = BASE_DIR / "library" / "entities"
PEOPLE_INDEX_PATH = ENTITIES_DIR / "people_index.json"
OUT_PLACES = ENTITIES_DIR / "places.json"
OUT_INDEX = ENTITIES_DIR / "places_index.json"

MAX_EXCERPTS = 20
MAX_SENTENCE_CHARS = 400


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

PLACES_SEED = [
    # TIER 1 – LDS/Restoration sites
    {"id": "place:palmyra",           "name": "Palmyra",           "variants": [],                                              "wikipedia_title": "Palmyra, New York"},
    {"id": "place:nauvoo",            "name": "Nauvoo",            "variants": [],                                              "wikipedia_title": "Nauvoo, Illinois"},
    {"id": "place:kirtland",          "name": "Kirtland",          "variants": [],                                              "wikipedia_title": "Kirtland, Ohio"},
    {"id": "place:far_west",          "name": "Far West",          "variants": [],                                              "wikipedia_title": "Far West, Missouri"},
    {"id": "place:carthage",          "name": "Carthage",          "variants": [],                                              "wikipedia_title": "Carthage, Illinois"},
    {"id": "place:salt_lake_city",    "name": "Salt Lake City",    "variants": [],                                              "wikipedia_title": "Salt Lake City"},
    {"id": "place:harmony",           "name": "Harmony",           "variants": [],                                              "wikipedia_title": "Harmony, Pennsylvania"},
    {"id": "place:cumorah",           "name": "Cumorah",           "variants": [],                                              "wikipedia_title": "Cumorah"},
    {"id": "place:fayette",           "name": "Fayette",           "variants": [],                                              "wikipedia_title": "Fayette, New York"},
    {"id": "place:adam_ondi_ahman",   "name": "Adam-ondi-Ahman",  "variants": [],                                              "wikipedia_title": "Adam-ondi-Ahman"},
    {"id": "place:liberty_jail",      "name": "Liberty Jail",      "variants": [],                                              "wikipedia_title": "Liberty Jail"},
    {"id": "place:winter_quarters",   "name": "Winter Quarters",   "variants": [],                                              "wikipedia_title": "Winter Quarters, Nebraska"},
    {"id": "place:hauns_mill",        "name": "Haun's Mill",       "variants": ["Hauns Mill", "Hawn's Mill"],                   "wikipedia_title": "Haun's Mill massacre"},
    # TIER 2 – Biblical geography
    {"id": "place:jerusalem",         "name": "Jerusalem",         "variants": ["city of David", "holy city"],                  "wikipedia_title": "Jerusalem"},
    {"id": "place:bethlehem",         "name": "Bethlehem",         "variants": [],                                              "wikipedia_title": "Bethlehem"},
    {"id": "place:galilee",           "name": "Galilee",           "variants": ["Sea of Galilee", "lake of Gennesaret", "Tiberias"], "wikipedia_title": "Galilee"},
    {"id": "place:nazareth",          "name": "Nazareth",          "variants": [],                                              "wikipedia_title": "Nazareth"},
    {"id": "place:capernaum",         "name": "Capernaum",         "variants": [],                                              "wikipedia_title": "Capernaum"},
    {"id": "place:jericho",           "name": "Jericho",           "variants": [],                                              "wikipedia_title": "Jericho"},
    {"id": "place:jordan_river",      "name": "Jordan River",      "variants": ["Jordan", "river Jordan"],                      "wikipedia_title": "Jordan River"},
    {"id": "place:gethsemane",        "name": "Gethsemane",        "variants": ["garden of Gethsemane"],                        "wikipedia_title": "Gethsemane"},
    {"id": "place:golgotha",          "name": "Golgotha",          "variants": ["Calvary", "place of the skull"],               "wikipedia_title": "Golgotha"},
    {"id": "place:sinai",             "name": "Sinai",             "variants": ["Mount Sinai", "Mt. Sinai", "Horeb", "Mount Horeb"], "wikipedia_title": "Mount Sinai"},
    {"id": "place:egypt",             "name": "Egypt",             "variants": ["land of Egypt"],                               "wikipedia_title": "Ancient Egypt"},
    {"id": "place:babylon",           "name": "Babylon",           "variants": ["Babel"],                                       "wikipedia_title": "Babylon"},
    {"id": "place:nineveh",           "name": "Nineveh",           "variants": [],                                              "wikipedia_title": "Nineveh"},
    {"id": "place:damascus",          "name": "Damascus",          "variants": [],                                              "wikipedia_title": "Damascus"},
    {"id": "place:samaria",           "name": "Samaria",           "variants": ["Sychar"],                                      "wikipedia_title": "Samaria"},
    {"id": "place:bethany",           "name": "Bethany",           "variants": [],                                              "wikipedia_title": "Bethany, West Bank"},
    {"id": "place:bethsaida",         "name": "Bethsaida",         "variants": [],                                              "wikipedia_title": "Bethsaida"},
    {"id": "place:cana",              "name": "Cana",              "variants": [],                                              "wikipedia_title": "Cana"},
    {"id": "place:emmaus",            "name": "Emmaus",            "variants": [],                                              "wikipedia_title": "Emmaus"},
    {"id": "place:mount_of_olives",   "name": "Mount of Olives",   "variants": ["Olivet"],                                      "wikipedia_title": "Mount of Olives"},
    {"id": "place:temple_mount",      "name": "Temple Mount",      "variants": ["temple in Jerusalem", "Solomon's temple"],     "wikipedia_title": "Temple Mount"},
    {"id": "place:dead_sea",          "name": "Dead Sea",          "variants": ["Salt Sea"],                                    "wikipedia_title": "Dead Sea"},
    {"id": "place:canaan",            "name": "Canaan",            "variants": ["promised land", "land of Canaan"],             "wikipedia_title": "Canaan"},
    {"id": "place:judea",             "name": "Judea",             "variants": ["Judah", "land of Judah"],                      "wikipedia_title": "Judea"},
    {"id": "place:antioch",           "name": "Antioch",           "variants": [],                                              "wikipedia_title": "Antioch"},
    {"id": "place:rome",              "name": "Rome",              "variants": [],                                              "wikipedia_title": "Rome"},
    {"id": "place:ephesus",           "name": "Ephesus",           "variants": [],                                              "wikipedia_title": "Ephesus"},
    {"id": "place:corinth",           "name": "Corinth",           "variants": [],                                              "wikipedia_title": "Corinth"},
    {"id": "place:athens",            "name": "Athens",            "variants": [],                                              "wikipedia_title": "Athens"},
    # TIER 3 – Book of Mormon (no wikipedia_title)
    {"id": "place:bountiful",         "name": "Bountiful",         "variants": ["land of Bountiful"],                           "wikipedia_title": None},
    {"id": "place:zarahemla",         "name": "Zarahemla",         "variants": ["city of Zarahemla", "land of Zarahemla"],      "wikipedia_title": None},
    {"id": "place:land_of_nephi",     "name": "Land of Nephi",     "variants": ["city of Nephi"],                               "wikipedia_title": None},
    {"id": "place:moroni_city",       "name": "Moroni",            "variants": ["city of Moroni"],                              "wikipedia_title": None},
    {"id": "place:helam",             "name": "Helam",             "variants": ["land of Helam"],                               "wikipedia_title": None},
    {"id": "place:lehi_nephi",        "name": "Lehi-Nephi",        "variants": [],                                              "wikipedia_title": None},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def book_and_verse(filename: str, verse_key: str) -> str:
    """Convert 'john_1.json' + '5' → 'John 1:5'"""
    stem = filename.replace(".json", "")
    parts = stem.rsplit("_", 1)
    if len(parts) == 2:
        raw_book, chapter = parts
    else:
        raw_book = stem
        chapter = "?"
    book = raw_book.replace("_", " ").title()
    return f"{book} {chapter}:{verse_key}"


def extract_sentences(text: str, pattern: re.Pattern) -> list:
    """
    Split text on sentence boundaries and return sentences containing a match.
    Caps each sentence at MAX_SENTENCE_CHARS.
    """
    # Split on '. ' or '.\n' boundaries, keeping approximate sentences
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    hits = []
    for sent in raw_sentences:
        if pattern.search(sent):
            s = sent.strip()
            if len(s) > MAX_SENTENCE_CHARS:
                # Try to trim at a word boundary
                s = s[:MAX_SENTENCE_CHARS].rsplit(" ", 1)[0] + "…"
            hits.append(s)
    return hits


def build_pattern(name: str, variants: list) -> re.Pattern:
    terms = [re.escape(name)] + [re.escape(v) for v in variants]
    # Sort longest first so overlapping terms match correctly
    terms.sort(key=len, reverse=True)
    return re.compile(r'\b(' + '|'.join(terms) + r')\b', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load people index for speaker → person_id lookup
    with open(PEOPLE_INDEX_PATH) as f:
        people_index = json.load(f)

    # Collect all donaldson files
    don_files = sorted(DONALDSON_DIR.glob("*.json"))
    print(f"Found {len(don_files)} Donaldson files.")

    # Initialize place records
    places = {}
    for seed in PLACES_SEED:
        pid = seed["id"]
        places[pid] = {
            "id": pid,
            "name": seed["name"],
            "variants": seed["variants"],
            "wikipedia_title": seed.get("wikipedia_title"),
            "excerpts": [],
            "related_people": [],
            "related_things": [],
            "related_scriptures": [],
            "doc_ids": [],
            # working sets (removed before output)
            "_people_set": set(),
            "_scripture_set": set(),
            "_pattern": build_pattern(seed["name"], seed["variants"]),
        }

    total_files = len(don_files)
    for file_idx, fpath in enumerate(don_files):
        fname = fpath.name
        try:
            with open(fpath) as f:
                data = json.load(f)
        except Exception as e:
            print(f"  WARN: could not load {fname}: {e}")
            continue

        for verse_key, verse in data.items():
            scripture_ref = book_and_verse(fname, verse_key)
            notes = verse.get("notes") or []
            quotes = verse.get("quotes") or []

            for pid, place in places.items():
                pat = place["_pattern"]
                ex_list = place["excerpts"]

                # ---- notes ----
                for note in notes:
                    if not isinstance(note, str):
                        continue
                    if pat.search(note):
                        sentences = extract_sentences(note, pat)
                        for sent in sentences:
                            if len(ex_list) < MAX_EXCERPTS:
                                ex_list.append({
                                    "text": sent,
                                    "source": "donaldson",
                                    "ref": scripture_ref,
                                    "speaker": None,
                                })
                        place["_scripture_set"].add(scripture_ref)

                # ---- quotes ----
                for q in quotes:
                    qt = q.get("text") or ""
                    if not isinstance(qt, str):
                        continue
                    if pat.search(qt):
                        speaker_name = q.get("speaker") or ""
                        speaker_id = people_index.get(speaker_name.lower())
                        attr = q.get("attr") or ""
                        sentences = extract_sentences(qt, pat)
                        for sent in sentences:
                            if len(ex_list) < MAX_EXCERPTS:
                                ex_list.append({
                                    "text": sent,
                                    "source": "gc",
                                    "ref": None,
                                    "speaker": speaker_id,
                                    "attr": attr or None,
                                })
                        if speaker_id:
                            place["_people_set"].add(speaker_id)
                        place["_scripture_set"].add(scripture_ref)

    # Finalize records
    output = []
    total_excerpts = 0
    for seed in PLACES_SEED:
        pid = seed["id"]
        place = places[pid]
        place["related_people"] = sorted(place["_people_set"])
        place["related_scriptures"] = sorted(place["_scripture_set"])
        total_excerpts += len(place["excerpts"])
        # Remove working keys
        del place["_people_set"]
        del place["_scripture_set"]
        del place["_pattern"]
        output.append(place)

    # Write places.json
    with open(OUT_PLACES, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(output)} places to {OUT_PLACES}")
    print(f"Total excerpts collected: {total_excerpts}")

    # Build places_index.json
    # Map: lowercased name or variant → place_id
    # Sort entries longest-first for matching precedence
    index_entries = {}
    for place in output:
        pid = place["id"]
        index_entries[place["name"].lower()] = pid
        for v in place["variants"]:
            index_entries[v.lower()] = pid

    # Sort by key length descending
    sorted_index = dict(
        sorted(index_entries.items(), key=lambda kv: len(kv[0]), reverse=True)
    )

    with open(OUT_INDEX, "w") as f:
        json.dump(sorted_index, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(sorted_index)} index entries to {OUT_INDEX}")

    # Spot-check summary
    print("\n--- SPOT CHECK ---")
    for target_name in ["Jerusalem", "Gethsemane", "Palmyra"]:
        match = next((p for p in output if p["name"] == target_name), None)
        if match:
            exs = match["excerpts"][:2]
            print(f"\n[{target_name}] ({len(match['excerpts'])} excerpts total, "
                  f"{len(match['related_scriptures'])} scriptures)")
            for i, ex in enumerate(exs, 1):
                spk = ex.get("speaker") or "—"
                print(f"  [{i}] ref={ex.get('ref')} speaker={spk}")
                print(f"      {ex['text'][:200]}")
        else:
            print(f"\n[{target_name}] NOT FOUND in output")


if __name__ == "__main__":
    main()
