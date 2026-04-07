#!/usr/bin/env python3
"""
build_scripture_figure_registry.py

Builds a registry of scripture figures (people who appear IN LDS canon verse text)
as opposed to the GC/Donaldson-derived people.json (modern LDS figures).

Outputs:
  library/entities/scripture_people.json
  library/entities/scripture_people_index.json

Run from repo root:
    python3 lds_pipeline/build_scripture_figure_registry.py
"""

import json
import re
from collections import defaultdict
from pathlib import Path

BASE    = Path(__file__).resolve().parent.parent
CHAPTERS = BASE / "library" / "chapters"
OUT_DIR  = BASE / "library" / "entities"

# ---------------------------------------------------------------------------
# Seed: curated scripture figures with name variants + description
# Groups: old_testament, new_testament, book_of_mormon, restoration
# ---------------------------------------------------------------------------

SCRIPTURE_FIGURES = [
    # ─── Old Testament / Bible ────────────────────────────────────────────
    {"id": "person:adam",         "name": "Adam",         "group": "old_testament",  "desc": "First man; father of the human family",
     "variants": ["Adam"]},
    {"id": "person:eve",          "name": "Eve",          "group": "old_testament",  "desc": "First woman; mother of all living",
     "variants": ["Eve"]},
    {"id": "person:enoch",        "name": "Enoch",        "group": "old_testament",  "desc": "Prophet who built Zion; translated without death",
     "variants": ["Enoch"]},
    {"id": "person:noah",         "name": "Noah",         "group": "old_testament",  "desc": "Builder of the ark; survived the flood",
     "variants": ["Noah"]},
    {"id": "person:abraham",      "name": "Abraham",      "group": "old_testament",  "desc": "Father of the faithful; made the Abrahamic covenant",
     "variants": ["Abraham", "Abram"]},
    {"id": "person:sarah",        "name": "Sarah",        "group": "old_testament",  "desc": "Wife of Abraham; mother of Isaac",
     "variants": ["Sarah", "Sarai"]},
    {"id": "person:isaac",        "name": "Isaac",        "group": "old_testament",  "desc": "Son of Abraham and Sarah; carried the covenant",
     "variants": ["Isaac"]},
    {"id": "person:rebekah",      "name": "Rebekah",      "group": "old_testament",  "desc": "Wife of Isaac; mother of Jacob and Esau",
     "variants": ["Rebekah", "Rebecca"]},
    {"id": "person:jacob",        "name": "Jacob",        "group": "old_testament",  "desc": "Son of Isaac; renamed Israel; father of the twelve tribes",
     "variants": ["Jacob", "Israel"]},
    {"id": "person:joseph_egypt", "name": "Joseph",       "group": "old_testament",  "desc": "Son of Jacob; sold into Egypt; type of Christ",
     "variants": ["Joseph"]},
    {"id": "person:moses",        "name": "Moses",        "group": "old_testament",  "desc": "Deliverer of Israel; received the law on Sinai",
     "variants": ["Moses"]},
    {"id": "person:aaron_ot",     "name": "Aaron",        "group": "old_testament",  "desc": "Brother of Moses; first high priest of Israel",
     "variants": ["Aaron"]},
    {"id": "person:miriam",       "name": "Miriam",       "group": "old_testament",  "desc": "Sister of Moses; prophetess of Israel",
     "variants": ["Miriam"]},
    {"id": "person:joshua",       "name": "Joshua",       "group": "old_testament",  "desc": "Successor of Moses; led Israel into Canaan",
     "variants": ["Joshua"]},
    {"id": "person:caleb",        "name": "Caleb",        "group": "old_testament",  "desc": "Spy who gave a faithful report; inherited Hebron",
     "variants": ["Caleb"]},
    {"id": "person:deborah",      "name": "Deborah",      "group": "old_testament",  "desc": "Judge and prophetess of Israel",
     "variants": ["Deborah"]},
    {"id": "person:gideon",       "name": "Gideon",       "group": "old_testament",  "desc": "Judge who delivered Israel from Midian",
     "variants": ["Gideon"]},
    {"id": "person:samson",       "name": "Samson",       "group": "old_testament",  "desc": "Judge of Israel; Nazirite of great strength",
     "variants": ["Samson"]},
    {"id": "person:ruth",         "name": "Ruth",         "group": "old_testament",  "desc": "Moabitess who remained loyal to Naomi; ancestor of David",
     "variants": ["Ruth"]},
    {"id": "person:hannah",       "name": "Hannah",       "group": "old_testament",  "desc": "Mother of Samuel; her prayer is a model of faith",
     "variants": ["Hannah"]},
    {"id": "person:samuel",       "name": "Samuel",       "group": "old_testament",  "desc": "Prophet, judge, and kingmaker of Israel",
     "variants": ["Samuel"]},
    {"id": "person:saul_king",    "name": "Saul",         "group": "old_testament",  "desc": "First king of Israel",
     "variants": ["Saul"]},
    {"id": "person:david",        "name": "David",        "group": "old_testament",  "desc": "Shepherd-king of Israel; ancestor of Jesus Christ",
     "variants": ["David"]},
    {"id": "person:solomon",      "name": "Solomon",      "group": "old_testament",  "desc": "Son of David; built the first temple; renowned for wisdom",
     "variants": ["Solomon"]},
    {"id": "person:elijah",       "name": "Elijah",       "group": "old_testament",  "desc": "Prophet who confronted Baal worship; translated; returned as Elias",
     "variants": ["Elijah", "Elias", "Elijah the Tishbite"]},
    {"id": "person:elisha",       "name": "Elisha",       "group": "old_testament",  "desc": "Successor of Elijah; performed many miracles",
     "variants": ["Elisha"]},
    {"id": "person:isaiah",       "name": "Isaiah",       "group": "old_testament",  "desc": "Prophet whose writings are quoted most in the Book of Mormon",
     "variants": ["Isaiah", "Esaias"]},
    {"id": "person:jeremiah",     "name": "Jeremiah",     "group": "old_testament",  "desc": "Weeping prophet of Judah; foretold the Babylonian captivity",
     "variants": ["Jeremiah"]},
    {"id": "person:ezekiel",      "name": "Ezekiel",      "group": "old_testament",  "desc": "Prophet among the exiles in Babylon; vision of the valley of dry bones",
     "variants": ["Ezekiel"]},
    {"id": "person:daniel",       "name": "Daniel",       "group": "old_testament",  "desc": "Prophet in Babylon; interpreted dreams and visions",
     "variants": ["Daniel"]},
    {"id": "person:hosea",        "name": "Hosea",        "group": "old_testament",  "desc": "Prophet whose marriage symbolized God's covenant with Israel",
     "variants": ["Hosea"]},
    {"id": "person:amos",         "name": "Amos",         "group": "old_testament",  "desc": "Prophet who cried for justice and righteousness",
     "variants": ["Amos"]},
    {"id": "person:jonah",        "name": "Jonah",        "group": "old_testament",  "desc": "Prophet sent to Nineveh; sign of Christ's burial and resurrection",
     "variants": ["Jonah"]},
    {"id": "person:micah",        "name": "Micah",        "group": "old_testament",  "desc": "Prophet who foretold the birth of Christ in Bethlehem",
     "variants": ["Micah"]},
    {"id": "person:malachi",      "name": "Malachi",      "group": "old_testament",  "desc": "Last Old Testament prophet; prophesied Elijah's return",
     "variants": ["Malachi"]},
    {"id": "person:job",          "name": "Job",          "group": "old_testament",  "desc": "Righteous man tested with suffering; affirmed the Resurrection",
     "variants": ["Job"]},
    {"id": "person:ruth",         "name": "Ruth",         "group": "old_testament",  "desc": "Moabitess renowned for loyalty to Naomi",
     "variants": ["Ruth"]},
    {"id": "person:esther",       "name": "Esther",       "group": "old_testament",  "desc": "Queen who saved the Jewish people from Haman's plot",
     "variants": ["Esther"]},
    {"id": "person:nehemiah",     "name": "Nehemiah",     "group": "old_testament",  "desc": "Governor who rebuilt the walls of Jerusalem after the exile",
     "variants": ["Nehemiah"]},
    {"id": "person:ezra",         "name": "Ezra",         "group": "old_testament",  "desc": "Scribe who led a return from Babylon and restored the law",
     "variants": ["Ezra"]},
    {"id": "person:zechariah",    "name": "Zechariah",    "group": "old_testament",  "desc": "Post-exile prophet; messianic visions of the Branch",
     "variants": ["Zechariah", "Zacharias"]},

    # ─── New Testament ────────────────────────────────────────────────────
    {"id": "person:john_baptist", "name": "John the Baptist", "group": "new_testament", "desc": "Forerunner of Christ; baptized Jesus in the Jordan River",
     "variants": ["John the Baptist", "John"]},
    {"id": "person:peter",        "name": "Peter",        "group": "new_testament",  "desc": "Chief Apostle; received keys of the kingdom; also called Simon, Cephas",
     "variants": ["Peter", "Simon Peter", "Simon", "Cephas"]},
    {"id": "person:andrew",       "name": "Andrew",       "group": "new_testament",  "desc": "Apostle; brother of Peter; first called",
     "variants": ["Andrew"]},
    {"id": "person:james_zebedee","name": "James",        "group": "new_testament",  "desc": "Apostle; son of Zebedee; brother of John",
     "variants": ["James"]},
    {"id": "person:john_apostle", "name": "John",         "group": "new_testament",  "desc": "Beloved Apostle; translated; author of Revelation and the Gospel of John",
     "variants": ["John the Apostle", "John the Beloved", "the disciple whom Jesus loved"]},
    {"id": "person:philip",       "name": "Philip",       "group": "new_testament",  "desc": "Apostle from Bethsaida; brought Nathanael to Jesus",
     "variants": ["Philip"]},
    {"id": "person:nathanael",    "name": "Nathanael",    "group": "new_testament",  "desc": "Apostle in whom there was no guile; also called Bartholomew",
     "variants": ["Nathanael", "Bartholomew"]},
    {"id": "person:matthew",      "name": "Matthew",      "group": "new_testament",  "desc": "Apostle; former publican; author of first Gospel",
     "variants": ["Matthew", "Levi"]},
    {"id": "person:thomas",       "name": "Thomas",       "group": "new_testament",  "desc": "Apostle; doubted then testified of the risen Christ",
     "variants": ["Thomas", "Didymus"]},
    {"id": "person:paul",         "name": "Paul",         "group": "new_testament",  "desc": "Apostle to the Gentiles; formerly Saul of Tarsus",
     "variants": ["Paul", "Saul of Tarsus"]},
    {"id": "person:barnabas",     "name": "Barnabas",     "group": "new_testament",  "desc": "Companion of Paul; son of consolation",
     "variants": ["Barnabas"]},
    {"id": "person:stephen",      "name": "Stephen",      "group": "new_testament",  "desc": "First Christian martyr; saw Christ at the right hand of God",
     "variants": ["Stephen"]},
    {"id": "person:mary_mother",  "name": "Mary",         "group": "new_testament",  "desc": "Mother of Jesus Christ; favored of God",
     "variants": ["Mary", "Virgin Mary", "Mary the mother of Jesus", "Mary the mother of the Lord"]},
    {"id": "person:mary_magdalene","name": "Mary Magdalene","group": "new_testament","desc": "First witness of the resurrected Christ",
     "variants": ["Mary Magdalene", "Mary of Magdala"]},
    {"id": "person:martha",       "name": "Martha",       "group": "new_testament",  "desc": "Sister of Mary and Lazarus; received testimony of the Resurrection",
     "variants": ["Martha"]},
    {"id": "person:lazarus",      "name": "Lazarus",      "group": "new_testament",  "desc": "Raised from the dead by Jesus; brother of Mary and Martha",
     "variants": ["Lazarus"]},
    {"id": "person:nicodemus",    "name": "Nicodemus",    "group": "new_testament",  "desc": "Pharisee who came to Jesus by night; learned of being born again",
     "variants": ["Nicodemus"]},
    {"id": "person:zacchaeus",    "name": "Zacchaeus",    "group": "new_testament",  "desc": "Chief publican who climbed a tree to see Jesus",
     "variants": ["Zacchaeus"]},
    {"id": "person:pilate",       "name": "Pilate",       "group": "new_testament",  "desc": "Roman governor who sentenced Jesus to crucifixion",
     "variants": ["Pilate", "Pontius Pilate"]},
    {"id": "person:herod",        "name": "Herod",        "group": "new_testament",  "desc": "Ruler who sought to kill the infant Jesus; also Herod Antipas who killed John",
     "variants": ["Herod", "Herod Antipas", "Herod the Great", "Herod the king"]},
    {"id": "person:caiaphas",     "name": "Caiaphas",     "group": "new_testament",  "desc": "High priest who condemned Jesus",
     "variants": ["Caiaphas"]},
    {"id": "person:joseph_husband","name": "Joseph of Nazareth","group": "new_testament","desc": "Husband of Mary; earthly guardian of Jesus",
     "variants": ["Joseph her husband", "Joseph the carpenter"]},
    {"id": "person:simeon",       "name": "Simeon",       "group": "new_testament",  "desc": "Righteous man who blessed the infant Jesus in the temple",
     "variants": ["Simeon"]},
    {"id": "person:anna",         "name": "Anna",         "group": "new_testament",  "desc": "Prophetess who recognized the infant Jesus in the temple",
     "variants": ["Anna"]},
    {"id": "person:timothy",      "name": "Timothy",      "group": "new_testament",  "desc": "Young companion and protégé of Paul",
     "variants": ["Timothy", "Timotheus"]},
    {"id": "person:titus_nt",     "name": "Titus",        "group": "new_testament",  "desc": "Companion of Paul; leader of the church in Crete",
     "variants": ["Titus"]},

    # ─── Book of Mormon ───────────────────────────────────────────────────
    {"id": "person:lehi",         "name": "Lehi",         "group": "book_of_mormon", "desc": "Prophet-patriarch who led his family from Jerusalem to the promised land",
     "variants": ["Lehi"]},
    {"id": "person:sariah",       "name": "Sariah",       "group": "book_of_mormon", "desc": "Wife of Lehi; mother of Nephi; murmured then believed",
     "variants": ["Sariah"]},
    {"id": "person:nephi_1",      "name": "Nephi",        "group": "book_of_mormon", "desc": "Son of Lehi; visionary prophet; founded the Nephite nation",
     "variants": ["Nephi"]},
    {"id": "person:laman",        "name": "Laman",        "group": "book_of_mormon", "desc": "Elder son of Lehi; rebellious; progenitor of the Lamanites",
     "variants": ["Laman"]},
    {"id": "person:lemuel",       "name": "Lemuel",       "group": "book_of_mormon", "desc": "Son of Lehi; followed Laman in rebellion",
     "variants": ["Lemuel"]},
    {"id": "person:sam",          "name": "Sam",          "group": "book_of_mormon", "desc": "Son of Lehi; followed Nephi in faithfulness",
     "variants": ["Sam"]},
    {"id": "person:jacob_bom",    "name": "Jacob",        "group": "book_of_mormon", "desc": "Son of Lehi; taught pure doctrine of Christ; author of the book of Jacob",
     "variants": ["Jacob"]},
    {"id": "person:joseph_bom",   "name": "Joseph",       "group": "book_of_mormon", "desc": "Youngest son of Lehi; given promises by his father",
     "variants": ["Joseph"]},
    {"id": "person:zoram",        "name": "Zoram",        "group": "book_of_mormon", "desc": "Servant of Laban who joined Lehi's family and was a free man",
     "variants": ["Zoram"]},
    {"id": "person:sherem",       "name": "Sherem",       "group": "book_of_mormon", "desc": "Anti-Christ who confronted Jacob and was struck by God",
     "variants": ["Sherem"]},
    {"id": "person:king_benjamin","name": "King Benjamin","group": "book_of_mormon", "desc": "Righteous Nephite king whose address proclaimed Christ's atoning name",
     "variants": ["Benjamin", "King Benjamin"]},
    {"id": "person:mosiah",       "name": "Mosiah",       "group": "book_of_mormon", "desc": "Prophet-king; translator of the Jaredite record",
     "variants": ["Mosiah"]},
    {"id": "person:alma_elder",   "name": "Alma",         "group": "book_of_mormon", "desc": "Priest of Noah who believed Abinadi; founded the church at the waters of Mormon",
     "variants": ["Alma"]},
    {"id": "person:alma_younger", "name": "Alma the Younger","group": "book_of_mormon","desc": "Son of Alma; angel-rebuked sinner turned mighty prophet and judge",
     "variants": ["Alma the Younger", "Alma"]},
    {"id": "person:abinadi",      "name": "Abinadi",      "group": "book_of_mormon", "desc": "Prophet martyred by fire; testimony converted Alma; prophesied of Christ",
     "variants": ["Abinadi"]},
    {"id": "person:noah_king",    "name": "King Noah",    "group": "book_of_mormon", "desc": "Wicked Nephite king who burned Abinadi",
     "variants": ["Noah", "King Noah"]},
    {"id": "person:ammon",        "name": "Ammon",        "group": "book_of_mormon", "desc": "Son of Mosiah; missionary to the Lamanites; defender of the king's flocks",
     "variants": ["Ammon"]},
    {"id": "person:aaron_bom",    "name": "Aaron",        "group": "book_of_mormon", "desc": "Son of Mosiah; missionary to Lamanites; taught the king of the Lamanites",
     "variants": ["Aaron"]},
    {"id": "person:captain_moroni","name": "Captain Moroni","group": "book_of_mormon","desc": "Commander of the Nephite armies; raised the Title of Liberty",
     "variants": ["Moroni", "Captain Moroni"]},
    {"id": "person:helaman",      "name": "Helaman",      "group": "book_of_mormon", "desc": "Son of Alma; commander of the stripling warriors; prophet",
     "variants": ["Helaman"]},
    {"id": "person:samuel_lamanite","name": "Samuel the Lamanite","group": "book_of_mormon","desc": "Lamanite prophet who prophesied from the walls of Zarahemla",
     "variants": ["Samuel the Lamanite", "Samuel"]},
    {"id": "person:nephi_son_helaman","name": "Nephi",    "group": "book_of_mormon", "desc": "Son of Helaman; prophet given sealing power; prayed for famine",
     "variants": ["Nephi"]},
    {"id": "person:ether",        "name": "Ether",        "group": "book_of_mormon", "desc": "Last Jaredite prophet; wrote the Jaredite record sealed to Moroni",
     "variants": ["Ether"]},
    {"id": "person:coriantumr",   "name": "Coriantumr",   "group": "book_of_mormon", "desc": "Last surviving Jaredite king; witnessed the destruction of his people",
     "variants": ["Coriantumr"]},
    {"id": "person:jared",        "name": "Jared",        "group": "book_of_mormon", "desc": "Brother's unnamed companion; led the Jaredites to the promised land",
     "variants": ["Jared"]},
    {"id": "person:brother_of_jared","name": "Brother of Jared","group": "book_of_mormon","desc": "Powerful prophet; saw the finger of God; shown all things",
     "variants": ["the brother of Jared", "Mahonri", "Moriancumer"]},
    {"id": "person:mormon",       "name": "Mormon",       "group": "book_of_mormon", "desc": "Nephite prophet-historian who abridged the records",
     "variants": ["Mormon"]},
    {"id": "person:moroni_bom",   "name": "Moroni",       "group": "book_of_mormon", "desc": "Son of Mormon; sealed the plates; visited Joseph Smith as an angel",
     "variants": ["Moroni"]},

    # ─── Restoration ──────────────────────────────────────────────────────
    {"id": "person:joseph_smith", "name": "Joseph Smith", "group": "restoration",    "desc": "Prophet of the Restoration; First Vision; received and translated the Book of Mormon",
     "variants": ["Joseph Smith", "Joseph Smith Jr.", "Joseph", "the Prophet Joseph", "Joseph the Prophet"]},
    {"id": "person:emma_smith",   "name": "Emma Smith",   "group": "restoration",    "desc": "Wife of Joseph Smith; first president of Relief Society",
     "variants": ["Emma Smith", "Emma"]},
    {"id": "person:brigham_young","name": "Brigham Young","group": "restoration",    "desc": "Second prophet; led pioneer exodus to Utah; colonized the West",
     "variants": ["Brigham Young", "Brigham"]},
    {"id": "person:oliver_cowdery","name": "Oliver Cowdery","group": "restoration",  "desc": "Scribe to Joseph Smith; received Aaronic and Melchizedek Priesthood",
     "variants": ["Oliver Cowdery", "Oliver"]},
    {"id": "person:hyrum_smith",  "name": "Hyrum Smith",  "group": "restoration",    "desc": "Brother of Joseph Smith; martyred at Carthage Jail",
     "variants": ["Hyrum Smith", "Hyrum"]},
    {"id": "person:john_the_revelator","name": "John the Revelator","group": "restoration","desc": "Translated Apostle; key figure in the Restoration of the priesthood",
     "variants": ["John the Revelator"]},
]


# Deduplicate by id (some entries may be repeated for clarity)
_seen_ids = set()
FIGURES = []
for fig in SCRIPTURE_FIGURES:
    if fig["id"] not in _seen_ids:
        _seen_ids.add(fig["id"])
        FIGURES.append(fig)


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def build_variant_pattern(variants: list[str]) -> re.Pattern:
    """Compile a regex that matches any variant as a whole word."""
    parts = sorted(variants, key=len, reverse=True)  # longest first
    escaped = [re.escape(v) for v in parts]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


def scan_chapter_html(path: Path, pattern: re.Pattern) -> list[dict]:
    """
    Find all verse divs containing a match and return minimal refs.
    Returns list of {"slug": ..., "verse": ..., "label": ...}
    """
    try:
        html = path.read_text(encoding="utf-8")
    except Exception:
        return []

    slug = path.stem  # e.g. john_1
    refs = []

    # Find verse divs
    for m in re.finditer(r'<div class="verse" id="v(\d+)"[^>]*>(.*?)</div>', html, re.DOTALL):
        verse_num = m.group(1)
        verse_html = m.group(2)
        # Strip tags to get plain text
        verse_text = re.sub(r"<[^>]+>", " ", verse_html)
        if pattern.search(verse_text):
            refs.append({
                "slug":  slug,
                "verse": int(verse_num),
            })
    return refs


def slug_to_label(slug: str) -> str:
    """john_1 → John 1,  1_nephi_3 → 1 Nephi 3"""
    parts = slug.rsplit("_", 1)
    if len(parts) == 2:
        book_part, ch = parts
        book = book_part.replace("_", " ").title()
        return f"{book} {ch}"
    return slug.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    chapter_files = sorted(CHAPTERS.glob("*.html"))
    print(f"Scanning {len(chapter_files)} chapter files...")

    figures = []
    index: dict[str, str] = {}  # variant_lower → figure_id

    for fig in FIGURES:
        pattern = build_variant_pattern(fig["variants"])
        refs = []
        seen_slugs: set[str] = set()

        for cf in chapter_files:
            matches = scan_chapter_html(cf, pattern)
            for ref in matches:
                key = f"{ref['slug']}:{ref['verse']}"
                if key not in seen_slugs:
                    seen_slugs.add(key)
                    refs.append({
                        "slug":  ref["slug"],
                        "verse": ref["verse"],
                        "label": f"{slug_to_label(ref['slug'])}:{ref['verse']}",
                    })

        entry = {
            "id":          fig["id"],
            "name":        fig["name"],
            "group":       fig["group"],
            "desc":        fig["desc"],
            "variants":    fig["variants"],
            "scripture_refs": sorted(refs, key=lambda r: (r["slug"], r["verse"])),
            "ref_count":   len(refs),
        }
        figures.append(entry)

        # Build index
        for v in fig["variants"]:
            vl = v.lower()
            if vl not in index:
                index[vl] = fig["id"]

        print(f"  {fig['name']:25s}: {len(refs):4d} verse appearances")

    # Sort: most-referenced first
    figures.sort(key=lambda f: -f["ref_count"])

    # Write outputs
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json  = OUT_DIR / "scripture_people.json"
    out_index = OUT_DIR / "scripture_people_index.json"

    out_json.write_text(
        json.dumps(figures, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    out_index.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    total_refs = sum(f["ref_count"] for f in figures)
    print(f"\nDone. {len(figures)} figures, {total_refs:,} total verse appearances.")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_index}")


if __name__ == "__main__":
    main()
