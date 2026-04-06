#!/usr/bin/env python3
"""
build_thing_registry.py

Scans the Donaldson corpus for thing/artifact mentions and outputs:
  library/entities/things.json
  library/entities/things_index.json
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
OUT_THINGS = ENTITIES_DIR / "things.json"
OUT_INDEX = ENTITIES_DIR / "things_index.json"

MAX_EXCERPTS = 20
MAX_SENTENCE_CHARS = 400


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

THINGS_SEED = [
    # RESTORATION ARTIFACTS
    {
        "id": "thing:urim_and_thummim",
        "name": "Urim and Thummim",
        "variants": ["interpreters", "seer stone", "Nephite interpreters"],
        "wikipedia_title": "Urim and Thummim (Latter Day Saints)",
    },
    {
        "id": "thing:gold_plates",
        "name": "Gold plates",
        "variants": ["golden plates", "plates of Nephi", "brass plates", "plates of Mormon", "plates of Ether", "Jaredite record"],
        "wikipedia_title": "Golden plates",
    },
    {
        "id": "thing:brass_plates",
        "name": "Brass plates",
        "variants": ["plates of brass", "plates of Laban"],
        "wikipedia_title": "Brass plates of Laban",
    },
    {
        "id": "thing:liahona",
        "name": "Liahona",
        "variants": ["compass", "ball of curious workmanship", "director"],
        "wikipedia_title": "Liahona (scriptures)",
    },
    {
        "id": "thing:sword_of_laban",
        "name": "Sword of Laban",
        "variants": ["sword of Laban"],
        "wikipedia_title": "Sword of Laban",
    },
    {
        "id": "thing:breastplate",
        "name": "Breastplate",
        "variants": ["breastplate of Aaron"],
        "wikipedia_title": "Breastplate (Latter Day Saints)",
    },
    {
        "id": "thing:nephite_records",
        "name": "Nephite records",
        "variants": ["plates of Zeniff", "plates of Alma"],
        "wikipedia_title": None,
    },
    {
        "id": "thing:sealing_power",
        "name": "Sealing power",
        "variants": ["keys of the kingdom", "binding and loosing"],
        "wikipedia_title": "Sealing (Latter Day Saints)",
    },
    {
        "id": "thing:priesthood_keys",
        "name": "Priesthood keys",
        "variants": ["keys of the priesthood", "Melchizedek priesthood", "Aaronic priesthood"],
        "wikipedia_title": "Priesthood (Latter Day Saints)",
    },
    # BIBLICAL OBJECTS
    {
        "id": "thing:ark_of_the_covenant",
        "name": "Ark of the covenant",
        "variants": ["ark", "ark of God", "ark of the Lord", "mercy seat"],
        "wikipedia_title": "Ark of the Covenant",
    },
    {
        "id": "thing:tabernacle",
        "name": "Tabernacle",
        "variants": ["tent of meeting", "wilderness tabernacle"],
        "wikipedia_title": "Tabernacle (Judaism)",
    },
    {
        "id": "thing:temple",
        "name": "Temple",
        "variants": ["house of the Lord", "house of God", "Solomon's temple", "second temple", "Herod's temple"],
        "wikipedia_title": "Temple in Jerusalem",
    },
    {
        "id": "thing:manna",
        "name": "Manna",
        "variants": ["bread from heaven", "bread of heaven"],
        "wikipedia_title": "Manna",
    },
    {
        "id": "thing:rod_of_aaron",
        "name": "Rod of Aaron",
        "variants": ["rod of Moses", "brazen serpent", "serpent of brass", "rod of God"],
        "wikipedia_title": "Aaron's rod",
    },
    {
        "id": "thing:burning_bush",
        "name": "Burning bush",
        "variants": ["bush that burned"],
        "wikipedia_title": "Burning bush",
    },
    {
        "id": "thing:pillar_of_fire",
        "name": "Pillar of fire",
        "variants": ["pillar of cloud", "pillar of light"],
        "wikipedia_title": "Pillar of fire and cloud",
    },
    {
        "id": "thing:staff_of_moses",
        "name": "Staff of Moses",
        "variants": ["rod of Moses", "Moses' rod"],
        "wikipedia_title": None,
    },
    {
        "id": "thing:stone_tablets",
        "name": "Stone tablets",
        "variants": ["tables of stone", "tablets of stone", "ten commandments", "law of Moses"],
        "wikipedia_title": "Ten Commandments",
    },
    {
        "id": "thing:altar",
        "name": "Altar",
        "variants": ["altar of sacrifice", "brazen altar", "altar of incense"],
        "wikipedia_title": "Altar",
    },
    {
        "id": "thing:menorah",
        "name": "Menorah",
        "variants": ["candlestick", "seven-branched candlestick", "lampstand"],
        "wikipedia_title": "Menorah (Temple)",
    },
    {
        "id": "thing:veil_of_the_temple",
        "name": "Veil of the temple",
        "variants": ["veil", "inner veil", "curtain of the temple"],
        "wikipedia_title": "Veil (religion)",
    },
    {
        "id": "thing:anointing_oil",
        "name": "Anointing oil",
        "variants": ["holy anointing oil", "oil of consecration"],
        "wikipedia_title": None,
    },
    {
        "id": "thing:crown_of_thorns",
        "name": "Crown of thorns",
        "variants": ["thorns"],
        "wikipedia_title": "Crown of thorns",
    },
    {
        "id": "thing:baptism",
        "name": "Baptism",
        "variants": ["baptized", "immersion", "font", "baptismal font"],
        "wikipedia_title": "Baptism",
    },
    {
        "id": "thing:sacrament",
        "name": "Sacrament",
        "variants": ["Lord's supper", "bread and wine", "bread and water"],
        "wikipedia_title": "Sacrament (Latter Day Saints)",
    },
    {
        "id": "thing:incense",
        "name": "Incense",
        "variants": ["incense offering", "altar of incense", "sweet incense"],
        "wikipedia_title": None,
    },
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
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    hits = []
    for sent in raw_sentences:
        if pattern.search(sent):
            s = sent.strip()
            if len(s) > MAX_SENTENCE_CHARS:
                s = s[:MAX_SENTENCE_CHARS].rsplit(" ", 1)[0] + "…"
            hits.append(s)
    return hits


def build_pattern(name: str, variants: list) -> re.Pattern:
    terms = [re.escape(name)] + [re.escape(v) for v in variants]
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

    # Initialize thing records
    things = {}
    for seed in THINGS_SEED:
        tid = seed["id"]
        things[tid] = {
            "id": tid,
            "name": seed["name"],
            "variants": seed["variants"],
            "wikipedia_title": seed.get("wikipedia_title"),
            "excerpts": [],
            "related_people": [],
            "related_places": [],
            "related_scriptures": [],
            "doc_ids": [],
            # working sets (removed before output)
            "_people_set": set(),
            "_scripture_set": set(),
            "_pattern": build_pattern(seed["name"], seed["variants"]),
        }

    for fpath in don_files:
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

            for tid, thing in things.items():
                pat = thing["_pattern"]
                ex_list = thing["excerpts"]

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
                        thing["_scripture_set"].add(scripture_ref)

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
                            thing["_people_set"].add(speaker_id)
                        thing["_scripture_set"].add(scripture_ref)

    # Finalize records
    output = []
    total_excerpts = 0
    for seed in THINGS_SEED:
        tid = seed["id"]
        thing = things[tid]
        thing["related_people"] = sorted(thing["_people_set"])
        thing["related_scriptures"] = sorted(thing["_scripture_set"])
        total_excerpts += len(thing["excerpts"])
        del thing["_people_set"]
        del thing["_scripture_set"]
        del thing["_pattern"]
        output.append(thing)

    # Write things.json
    with open(OUT_THINGS, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(output)} things to {OUT_THINGS}")
    print(f"Total excerpts collected: {total_excerpts}")

    # Build things_index.json
    index_entries = {}
    for thing in output:
        tid = thing["id"]
        index_entries[thing["name"].lower()] = tid
        for v in thing["variants"]:
            index_entries[v.lower()] = tid

    # Sort by key length descending
    sorted_index = dict(
        sorted(index_entries.items(), key=lambda kv: len(kv[0]), reverse=True)
    )

    with open(OUT_INDEX, "w") as f:
        json.dump(sorted_index, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(sorted_index)} index entries to {OUT_INDEX}")

    # Spot-check summary
    print("\n--- SPOT CHECK ---")
    for target_name in ["Urim and Thummim", "Ark of the covenant", "Baptism"]:
        match = next((t for t in output if t["name"] == target_name), None)
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
