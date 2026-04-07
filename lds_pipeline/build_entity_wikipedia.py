#!/usr/bin/env python3
"""
build_entity_wikipedia.py

Fetches Wikipedia summaries and structured data for entities and enriches
library/entities/people.json, places.json, things.json in place.

Designed to be claimed as a task in the task ledger and run autonomously.

Run from repo root:
    python3 lds_pipeline/build_entity_wikipedia.py [--people] [--places] [--things] [--limit N]
    python3 lds_pipeline/build_entity_wikipedia.py --task-id T-0009 --agent WikiEnricher
"""

import argparse
import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

REPO     = Path(__file__).resolve().parent.parent
ENTITIES = REPO / "library" / "entities"
LEDGER   = REPO / "task-ledger.jsonl"

WIKIPEDIA_REST  = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKIPEDIA_INFOBOX = "https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&format=json&formatversion=2&titles={title}&rvsection=0"

RATE_LIMIT_S = 0.3  # seconds between Wikipedia requests


# ── Wikipedia title overrides ─────────────────────────────────────────────────

WIKI_TITLES: dict[str, str] = {
    "person:joseph_egypt":      "Joseph (Genesis)",
    "person:john_baptist":      "John the Baptist",
    "person:john_apostle":      "John the Apostle",
    "person:james_zebedee":     "James, son of Zebedee",
    "person:mary_mother":       "Mary, mother of Jesus",
    "person:mary_magdalene":    "Mary Magdalene",
    "person:joseph_husband":    "Joseph, husband of Mary",
    "person:saul_king":         "Saul (Hebrew Bible)",
    "person:samuel":            "Samuel (Hebrew Bible)",
    "person:noah":              "Noah",
    "person:jacob":             "Jacob",
    "person:alma_elder":        "Alma the Elder",
    "person:alma_younger":      "Alma the Younger",
    "person:nephi_1":           "Nephi (Book of Mormon)",
    "person:moroni_bom":        "Moroni (Book of Mormon)",
    "person:captain_moroni":    "Captain Moroni",
    "person:king_benjamin":     "King Benjamin (Book of Mormon)",
    "person:brother_of_jared":  "Brother of Jared",
    "person:joseph_smith":      "Joseph Smith",
    "person:emma_smith":        "Emma Smith",
    "person:brigham_young":     "Brigham Young",
    "person:oliver_cowdery":    "Oliver Cowdery",
    "person:hyrum_smith":       "Hyrum Smith",
    "person:bruce_r_mc_conkie": "Bruce R. McConkie",
    "person:neal_a_maxwell":    "Neal A. Maxwell",
    "person:jeffrey_r_holland": "Jeffrey R. Holland",
    "person:russell_m_nelson":  "Russell M. Nelson",
    "person:gordon_b_hinckley": "Gordon B. Hinckley",
    "person:spencer_w_kimball": "Spencer W. Kimball",
    "person:ezra_taft_benson":  "Ezra Taft Benson",
    "person:boyd_k_packer":     "Boyd K. Packer",
    "person:james_e_talmage":   "James E. Talmage",
    "person:hugh_nibley":       "Hugh Nibley",
    "person:donald_w_parry":    "Donald W. Parry",
    "place:jordan_river":       "Jordan River",
    "place:adam_ondi_ahman":    "Adam-ondi-Ahman",
    "place:liberty_jail":       "Liberty Jail",
    "place:hauns_mill":         "Haun's Mill massacre",
    "place:gethsemane":         "Gethsemane",
    "place:golgotha":           "Golgotha",
    "place:sinai":              "Mount Sinai",
    "place:bethlehem":          "Bethlehem",
    "place:galilee":            "Galilee",
    "place:nazareth":           "Nazareth",
    "place:capernaum":          "Capernaum",
    "place:jericho":            "Jericho",
    "place:jerusalem":          "Jerusalem",
    "place:egypt":              "Ancient Egypt",
    "place:babylon":            "Babylon",
    "place:nineveh":            "Nineveh",
    "place:damascus":           "Damascus",
    "place:athens":             "Athens",
    "place:rome":               "Rome",
}


def get_wiki_title(entity: dict) -> str:
    eid  = entity.get("id", "")
    name = entity.get("name", "")
    return (entity.get("wikipedia_title")
            or WIKI_TITLES.get(eid)
            or name)


def fetch_wikipedia_summary(title: str):
    """Fetch the REST summary endpoint; return parsed dict or None on failure."""
    url = WIKIPEDIA_REST.format(title=urllib.parse.quote(title, safe="(),'"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GoodProject/1.0 (https://thegoodproject.ai)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("type") == "disambiguation":
                return None
            return data
    except Exception:
        return None


def parse_infobox(wikitext: str) -> dict:
    """Extract key infobox fields from raw wikitext."""
    fields = {}
    for m in re.finditer(r"\|\s*(\w+)\s*=\s*([^\|}{]+)", wikitext):
        key = m.group(1).strip()
        val = m.group(2).strip()
        # Clean wikitext markup
        val = re.sub(r"\[\[([^\]|]+)\|[^\]]*\]\]", r"\1", val)  # [[link|text]] → link
        val = re.sub(r"\[\[([^\]]+)\]\]", r"\1", val)             # [[link]] → link
        val = re.sub(r"\{\{[^}]*\}\}", "", val)                    # {{templates}}
        val = re.sub(r"<[^>]+>", "", val)                          # HTML tags
        val = re.sub(r"'{2,}", "", val)                             # bold/italic
        val = val.strip()
        if val and len(val) < 200:
            fields[key] = val
    return fields


def extract_born(fields: dict, summary_extract: str):
    """Try to extract birth year and place from infobox fields."""
    year = None
    place = None

    # birth_date field
    bd = fields.get("birth_date", "")
    ym = re.search(r"\b(\d{4})\b", bd)
    if ym:
        year = int(ym.group(1))

    # birth_place field
    bp = fields.get("birth_place", "")
    if bp:
        place = bp.split(",")[0].strip()  # first component

    # Fallback: scan extract
    if not year:
        m = re.search(r"\b(born|b\.)\s+\w+\s+\d+,\s+(\d{4})", summary_extract, re.IGNORECASE)
        if not m:
            m = re.search(r"\((\d{4})[–-]", summary_extract)
        if m:
            year = int(m.group(1) if len(m.groups()) == 1 else m.group(2)
                       if m.lastindex and m.lastindex >= 2 else m.group(1))

    if year or place:
        out: dict = {}
        if year:
            out["year"] = year
        if place:
            out["place_name"] = place
        return out
    return None


def extract_died(fields: dict, summary_extract: str):
    dd = fields.get("death_date", "")
    ym = re.search(r"\b(\d{4})\b", dd)
    year = int(ym.group(1)) if ym else None
    dp = fields.get("death_place", "")
    place = dp.split(",")[0].strip() if dp else None

    if not year:
        m = re.search(r"\((\d{4})[–-](\d{4})\)", summary_extract)
        if m:
            year = int(m.group(2))

    if year or place:
        out: dict = {}
        if year:
            out["year"] = year
        if place:
            out["place_name"] = place
        return out
    return None


def extract_roles(fields: dict) -> list[dict]:
    """Extract orderd list of roles/positions from infobox."""
    roles = []
    for i in range(1, 10):
        pos = (fields.get(f"position_or_quorum{i}", "")
               or fields.get(f"office{i}", "")
               or fields.get(f"title{i}", ""))
        if not pos:
            break
        role: dict = {"title": pos}
        d_in = fields.get(f"start{i}", fields.get(f"in{i}", ""))
        d_out = fields.get(f"end{i}", fields.get(f"out{i}", ""))
        ym = re.search(r"\b(\d{4})\b", d_in)
        if ym:
            role["from"] = int(ym.group(1))
        ym = re.search(r"\b(\d{4})\b", d_out)
        if ym:
            role["to"] = int(ym.group(1))
        roles.append(role)
    return roles


def enrich_entity(entity: dict, dry_run: bool = False) -> bool:
    """
    Fetch Wikipedia data and update entity in place.
    Returns True if enrichment succeeded.
    """
    # Skip already enriched
    if entity.get("wikipedia_summary") and not dry_run:
        return False

    wiki_title = get_wiki_title(entity)
    summary_data = fetch_wikipedia_summary(wiki_title)
    if not summary_data or not summary_data.get("extract"):
        return False

    extract   = summary_data.get("extract", "")
    desc_wiki = summary_data.get("description", "")
    thumbnail = (summary_data.get("thumbnail") or {}).get("source", "")
    wiki_url  = (summary_data.get("content_urls") or {}).get("desktop", {}).get("page", "")

    # Prefer the entity's own desc if it has one, else use Wikipedia's
    if not entity.get("desc") and desc_wiki:
        entity["desc"] = desc_wiki

    entity["wikipedia_title"]   = wiki_title
    entity["wikipedia_summary"] = extract[:600]
    if thumbnail:
        entity["wikipedia_thumbnail"] = thumbnail
    if wiki_url:
        entity["wikipedia_url"] = wiki_url

    # Parse infobox for structured fields
    # (quick approach: use extract for born/died since infobox requires a second call)
    born = extract_born({}, extract)
    if born:
        entity.setdefault("born", born)

    died = extract_died({}, extract)
    if died:
        entity.setdefault("died", died)

    return True


def process_file(path: Path, limit, dry_run: bool,
                 filter_fn=None) -> tuple[int, int]:
    """Load entity list, enrich, save back. Returns (enriched, skipped)."""
    entities = json.loads(path.read_text(encoding="utf-8"))
    enriched = skipped = 0

    for entity in entities:
        if filter_fn and not filter_fn(entity):
            continue
        if limit and enriched >= limit:
            break

        name = entity.get("name", entity.get("id", "?"))
        ok = enrich_entity(entity, dry_run)
        if ok:
            enriched += 1
            status = "[DRY] would enrich" if dry_run else "enriched"
            print(f"  {status}: {name}")
            time.sleep(RATE_LIMIT_S)
        else:
            skipped += 1

    if not dry_run:
        path.write_text(
            json.dumps(entities, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    return enriched, skipped


def mark_task(task_id: str, agent: str, commit: str, notes: str) -> None:
    from datetime import datetime, timezone
    entry = {
        "event":   "task_completed",
        "task_id": task_id,
        "agent":   agent,
        "commit":  commit,
        "notes":   notes,
        "ts":      datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--people",   action="store_true", help="Enrich people.json")
    parser.add_argument("--places",   action="store_true", help="Enrich places.json")
    parser.add_argument("--things",   action="store_true", help="Enrich things.json")
    parser.add_argument("--all",      action="store_true", help="Enrich all entity files")
    parser.add_argument("--limit",    type=int, default=None, help="Max entities to enrich per file")
    parser.add_argument("--scripture-only", action="store_true", help="Only scripture figures")
    parser.add_argument("--priority-only",  action="store_true", help="Only priority figures")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--task-id",  default="", help="Mark this task complete when done")
    parser.add_argument("--agent",    default="WikiEnricher")
    args = parser.parse_args()

    PRIORITY_IDS = {
        "person:moses", "person:abraham", "person:joseph_egypt", "person:elijah",
        "person:isaiah", "person:david", "person:nephi_1", "person:alma_younger",
        "person:moroni_bom", "person:king_benjamin", "person:abinadi",
        "person:peter", "person:paul", "person:john_baptist", "person:john_apostle",
        "person:joseph_smith", "person:brigham_young",
        "person:bruce_r_mc_conkie", "person:neal_a_maxwell", "person:jeffrey_r_holland",
        "person:russell_m_nelson", "person:gordon_b_hinckley", "person:james_e_talmage",
        "person:hugh_nibley", "person:spencer_w_kimball", "person:ezra_taft_benson",
        "person:boyd_k_packer",
    }

    def people_filter(e):
        if args.scripture_only:
            return bool(e.get("group"))
        if args.priority_only:
            return e["id"] in PRIORITY_IDS or bool(e.get("group"))
        return True

    do_people = args.people or args.all
    do_places = args.places or args.all
    do_things = args.things or args.all

    if not (do_people or do_places or do_things):
        # Default: priority people + all places + all things
        do_people = do_places = do_things = True
        if not args.priority_only and not args.scripture_only:
            args.priority_only = True

    total_enriched = 0

    if do_people:
        print(f"Enriching people ({ENTITIES / 'people.json'})...")
        n, s = process_file(ENTITIES / "people.json", args.limit, args.dry_run, people_filter)
        total_enriched += n
        print(f"  people: {n} enriched, {s} skipped")

    if do_places:
        print(f"Enriching places ({ENTITIES / 'places.json'})...")
        n, s = process_file(ENTITIES / "places.json", args.limit, args.dry_run)
        total_enriched += n
        print(f"  places: {n} enriched, {s} skipped")

    if do_things:
        print(f"Enriching things ({ENTITIES / 'things.json'})...")
        n, s = process_file(ENTITIES / "things.json", args.limit, args.dry_run)
        total_enriched += n
        print(f"  things: {n} enriched, {s} skipped")

    print(f"\nTotal enriched: {total_enriched}")

    if args.task_id and not args.dry_run and total_enriched > 0:
        import subprocess
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        mark_task(args.task_id, args.agent, commit,
                  f"Enriched {total_enriched} entities with Wikipedia data")
        print(f"Marked {args.task_id} complete in ledger")


if __name__ == "__main__":
    main()
