#!/usr/bin/env python3
"""
build_entity_tasks.py

Scans the entity registry for enrichment gaps and writes actionable tasks
to the task ledger. Agents then claim and execute these tasks.

Gap types detected:
  - wikipedia_missing   : entity has no Wikipedia title/summary
  - born_missing        : person has no birth data
  - links_missing       : entity has no cross-links to other entities
  - corpus_missing      : no corpus analytics (talk_count, most_referenced_scripture)
  - variants_sparse     : person has fewer than 2 name variants

Run from repo root:
    python3 lds_pipeline/build_entity_tasks.py [--dry-run]
"""

import argparse
import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO    = Path(__file__).resolve().parent.parent
LEDGER  = REPO / "task-ledger.jsonl"
ENTITIES = REPO / "library" / "entities"

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

PRIORITY_FIGURES = {
    # Scripture figures most likely to appear across the corpus
    "person:moses", "person:abraham", "person:joseph_egypt", "person:elijah",
    "person:isaiah", "person:david", "person:solomon", "person:noah",
    "person:nephi_1", "person:alma_elder", "person:alma_younger", "person:moroni_bom",
    "person:mormon", "person:king_benjamin", "person:abinadi",
    "person:peter", "person:paul", "person:john_baptist", "person:john_apostle",
    "person:joseph_smith", "person:brigham_young", "person:emma_smith",
    # Key modern figures
    "person:bruce_r_mc_conkie", "person:neal_a_maxwell", "person:jeffrey_r_holland",
    "person:russell_m_nelson", "person:gordon_b_hinckley", "person:spencer_w_kimball",
    "person:ezra_taft_benson", "person:boyd_k_packer", "person:james_e_talmage",
    "person:hugh_nibley", "person:donald_w_parry",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_ledger() -> set[str]:
    """Return set of task titles already in the ledger (to avoid duplicates)."""
    if not LEDGER.exists():
        return set()
    existing = set()
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if e.get("title"):
                existing.add(e["title"])
        except Exception:
            pass
    return existing


def next_task_id() -> str:
    if not LEDGER.exists():
        return "T-0001"
    lines = [l for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    nums = []
    for line in lines:
        try:
            e = json.loads(line)
            tid = e.get("task_id", "")
            if tid.startswith("T-") and tid[2:].isdigit():
                nums.append(int(tid[2:]))
        except Exception:
            pass
    nxt = (max(nums) + 1) if nums else 1
    return f"T-{nxt:04d}"


def append_task(title: str, description: str, entity_id: str,
                gap_type: str, existing: set, dry_run: bool) -> bool:
    if title in existing:
        return False
    existing.add(title)
    tid = next_task_id()

    entry = {
        "event":       "task_registered",
        "task_id":     tid,
        "title":       title,
        "description": description,
        "entity_id":   entity_id,
        "gap_type":    gap_type,
        "status":      "pending",
        "ts":          utc_now(),
    }

    if dry_run:
        print(f"  [DRY] {tid} [{gap_type}] {title[:80]}")
        return True

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return True


def guess_wikipedia_title(entity: dict) -> str:
    """Guess the Wikipedia article title from the entity name."""
    name = entity.get("name", "")
    eid  = entity.get("id", "")

    # Known mappings
    overrides = {
        "person:joseph_egypt":       "Joseph (Genesis)",
        "person:john_baptist":       "John the Baptist",
        "person:john_apostle":       "John the Apostle",
        "person:james_zebedee":      "James, son of Zebedee",
        "person:mary_mother":        "Mary, mother of Jesus",
        "person:mary_magdalene":     "Mary Magdalene",
        "person:joseph_husband":     "Joseph, husband of Mary",
        "person:saul_king":          "Saul (Hebrew Bible)",
        "person:samuel":             "Samuel (Hebrew Bible)",
        "person:noah":               "Noah",
        "person:alma_elder":         "Alma the Elder",
        "person:alma_younger":       "Alma the Younger",
        "person:nephi_1":            "Nephi (Book of Mormon)",
        "person:moroni_bom":         "Moroni (Book of Mormon)",
        "person:captain_moroni":     "Captain Moroni",
        "person:king_benjamin":      "King Benjamin (Book of Mormon)",
        "person:brother_of_jared":   "Brother of Jared",
        "person:joseph_smith":       "Joseph Smith",
        "person:brigham_young":      "Brigham Young",
        "person:oliver_cowdery":     "Oliver Cowdery",
        "person:hyrum_smith":        "Hyrum Smith",
        "person:bruce_r_mc_conkie":  "Bruce R. McConkie",
        "person:neal_a_maxwell":     "Neal A. Maxwell",
        "person:jeffrey_r_holland":  "Jeffrey R. Holland",
        "person:russell_m_nelson":   "Russell M. Nelson",
        "person:gordon_b_hinckley":  "Gordon B. Hinckley",
        "person:spencer_w_kimball":  "Spencer W. Kimball",
        "person:ezra_taft_benson":   "Ezra Taft Benson",
        "person:boyd_k_packer":      "Boyd K. Packer",
        "person:james_e_talmage":    "James E. Talmage",
        "person:hugh_nibley":        "Hugh Nibley",
        "place:jordan_river":        "Jordan River",
        "place:adam_ondi_ahman":     "Adam-ondi-Ahman",
        "place:liberty_jail":        "Liberty Jail",
        "place:hauns_mill":          "Haun's Mill massacre",
        "place:gethsemane":          "Gethsemane",
        "place:golgotha":            "Golgotha",
        "place:sinai":               "Mount Sinai",
        "place:bethlehem":           "Bethlehem",
    }
    if eid in overrides:
        return overrides[eid]

    return name.replace(" ", "_")


def scan_people(people: list, existing: set, dry_run: bool) -> int:
    added = 0

    for entity in people:
        eid  = entity.get("id", "")
        name = entity.get("name", "")
        group = entity.get("group", "")  # scripture figures have this
        is_priority = eid in PRIORITY_FIGURES or bool(group)

        # Gap: no wikipedia enrichment
        if not entity.get("wikipedia_summary") and is_priority:
            wiki_title = guess_wikipedia_title(entity)
            title = f"Wikipedia enrichment: {name}"
            desc  = (f"Fetch Wikipedia summary and infobox for {name} "
                     f"(wikipedia_title={wiki_title}). Extract born/died dates, "
                     f"roles/titles, related persons and places from the infobox. "
                     f"Update library/entities/people.json entry {eid}.")
            if append_task(title, desc, eid, "wikipedia_missing", existing, dry_run):
                added += 1

        # Gap: no corpus analytics for priority figures
        if not entity.get("corpus_mentions") and is_priority:
            title = f"Corpus analytics: {name}"
            desc  = (f"Scan all Donaldson files and GC talks to count how many times "
                     f"{name} is mentioned. Find their most cited scripture reference. "
                     f"Add corpus_mentions and most_referenced_scripture to {eid}.")
            if append_task(title, desc, eid, "corpus_missing", existing, dry_run):
                added += 1

        # Gap: scripture figure with no related_persons
        if group and not entity.get("related_persons"):
            title = f"Cross-link persons: {name}"
            desc  = (f"Identify contemporaries, family members, and key figures associated "
                     f"with {name} from scripture text and Wikipedia. Add related_persons "
                     f"list to {eid} (e.g. Moses ↔ Aaron, Miriam, Joshua, Pharaoh).")
            if append_task(title, desc, eid, "links_missing", existing, dry_run):
                added += 1

    return added


def scan_places(places: list, existing: set, dry_run: bool) -> int:
    added = 0
    for entity in places:
        eid  = entity.get("id", "")
        name = entity.get("name", "")

        if not entity.get("wikipedia_summary"):
            wiki_title = guess_wikipedia_title(entity)
            title = f"Wikipedia enrichment: {name} (place)"
            desc  = (f"Fetch Wikipedia summary for the place '{name}' "
                     f"(wikipedia_title={wiki_title}). Extract coordinates, region, "
                     f"historical significance, related persons. Update {eid}.")
            if append_task(title, desc, eid, "wikipedia_missing", existing, dry_run):
                added += 1

        if not entity.get("related_events"):
            title = f"Add events for place: {name}"
            desc  = (f"Identify key historical/scriptural events that occurred at {name} "
                     f"and link them. e.g. Jordan River → baptism of Jesus, crossing of Israel. "
                     f"Add related_events list to {eid}.")
            if append_task(title, desc, eid, "links_missing", existing, dry_run):
                added += 1

    return added


def scan_things(things: list, existing: set, dry_run: bool) -> int:
    added = 0
    for entity in things:
        eid  = entity.get("id", "")
        name = entity.get("name", "")

        if not entity.get("wikipedia_summary"):
            title = f"Wikipedia enrichment: {name} (thing)"
            desc  = (f"Fetch Wikipedia summary for '{name}'. Extract its scriptural context, "
                     f"who used/received it, where it is now, related persons and places. "
                     f"Update {eid} in things.json.")
            if append_task(title, desc, eid, "wikipedia_missing", existing, dry_run):
                added += 1

    return added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print tasks without writing")
    args = parser.parse_args()

    people = json.loads((ENTITIES / "people.json").read_text(encoding="utf-8"))
    places = json.loads((ENTITIES / "places.json").read_text(encoding="utf-8"))
    things = json.loads((ENTITIES / "things.json").read_text(encoding="utf-8"))

    existing = load_ledger()
    print(f"Existing ledger entries: {len(existing)}")

    # Only scan priority figures and scripture people to keep ledger focused
    priority_people = [p for p in people if p["id"] in PRIORITY_FIGURES or p.get("group")]
    print(f"Scanning {len(priority_people)} priority people, {len(places)} places, {len(things)} things...")

    n_people = scan_people(priority_people, existing, args.dry_run)
    n_places = scan_places(places, existing, args.dry_run)
    n_things = scan_things(things, existing, args.dry_run)

    total = n_people + n_places + n_things
    label = "Would add" if args.dry_run else "Added"
    print(f"\n{label} {total} tasks ({n_people} people, {n_places} places, {n_things} things)")


if __name__ == "__main__":
    main()
