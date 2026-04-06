#!/usr/bin/env python3
"""
Build entity registry from corpus.
Output: library/entities/people.json + people_index.json
"""

import json
import os
import re
import glob
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONALDSON_DIR = os.path.join(BASE, "library", "donaldson")
SOURCE_TOC = os.path.join(BASE, "library", "source_toc.json")
OUT_DIR = os.path.join(BASE, "library", "entities")

# Honorifics to strip for ID normalization (keep in display name)
HONORIFICS = re.compile(
    r"^(Elder|President|Brother|Sister|Dr\.|Prof\.|Bishop|Apostle|"
    r"Elder and Apostle|Pres\.|Rev\.|Brother and Sister|"
    r"Managing Director|Acting)\s+",
    re.IGNORECASE,
)

# GC meta: "Speaker Name [Role] · Month Year"
GC_META_RE = re.compile(r"^(.+?)\s+·\s+(\w+ \d{4})$")

# Remove trailing role qualifiers like "Of the Quorum..." for ID
ROLE_SUFFIX_RE = re.compile(
    r"\s+(Of the|To the|First|Second|Acting|Emeritus).+$", re.IGNORECASE
)


def normalize_name(name: str) -> str:
    """Strip honorifics + role suffixes → produce a stable ID key."""
    name = name.strip()
    # Strip leading honorifics (may be stacked)
    for _ in range(4):
        m = HONORIFICS.match(name)
        if m:
            name = name[m.end():]
        else:
            break
    # Strip trailing role qualifiers
    name = ROLE_SUFFIX_RE.sub("", name).strip()
    return name


def make_id(display_name: str) -> str:
    """person:b_h_roberts from any display name."""
    core = normalize_name(display_name)
    slug = re.sub(r"[^a-z0-9]+", "_", core.lower()).strip("_")
    return f"person:{slug}"


def parse_gc_speaker(meta: str):
    """Return (speaker_display, date_str) or (None, None)."""
    m = GC_META_RE.match(meta)
    if not m:
        return None, None
    speaker_raw = m.group(1).strip()
    date_str = m.group(2).strip()
    return speaker_raw, date_str


# ── Collect data ────────────────────────────────────────────────────────────

# person_id → {name, variants set, quote_count, talk_count, doc_ids set, roles set}
registry = defaultdict(lambda: {
    "name": "",
    "variants": set(),
    "quote_count": 0,
    "talk_count": 0,
    "doc_ids": set(),
    "roles": set(),
})


def register_person(display_name: str, doc_id: str = None,
                    is_talk: bool = False, is_quote: bool = False):
    if not display_name or len(display_name) < 3:
        return
    pid = make_id(display_name)
    rec = registry[pid]
    # Prefer shorter display name (less honorific clutter)
    if not rec["name"] or len(normalize_name(display_name)) < len(normalize_name(rec["name"])):
        rec["name"] = display_name
    rec["variants"].add(display_name)
    rec["variants"].add(normalize_name(display_name))
    if doc_id:
        rec["doc_ids"].add(doc_id)
    if is_talk:
        rec["talk_count"] += 1
    if is_quote:
        rec["quote_count"] += 1


# 1. Donaldson corpus — quotes[].speaker
print("Scanning Donaldson corpus...")
don_files = glob.glob(os.path.join(DONALDSON_DIR, "*.json"))
for fpath in sorted(don_files):
    try:
        data = json.load(open(fpath))
    except Exception as e:
        print(f"  skip {fpath}: {e}")
        continue
    for verse_num, verse in data.items():
        if not isinstance(verse, dict):
            continue
        for q in verse.get("quotes", []):
            speaker = q.get("speaker", "").strip()
            source = q.get("source", "").strip()
            doc_id = q.get("d", "") or q.get("doc_id", "")
            if speaker:
                # Try to resolve doc_id from source+date for GC quotes
                if not doc_id and source in ("Conference Report", "General Conference"):
                    date = q.get("date", "")
                    # Build approximate doc_id hint (no exact match needed)
                    doc_id = f"general_conference:{date.lower().replace(' ','_')}"
                register_person(speaker, doc_id=doc_id or None, is_quote=True)

print(f"  {len(registry)} people after Donaldson scan")

# 2. source_toc.json — GC talks with meta "Speaker · Month Year"
print("Scanning source_toc.json GC entries...")
toc = json.load(open(SOURCE_TOC))

def walk_toc(items):
    for item in items:
        meta = item.get("meta", "")
        doc_id = item.get("id", "")
        sub = item.get("items", [])
        if meta and doc_id.startswith("general_conference:general_conference"):
            speaker, date = parse_gc_speaker(meta)
            if speaker:
                register_person(speaker, doc_id=doc_id, is_talk=True)
        if sub:
            walk_toc(sub)

walk_toc(toc)
print(f"  {len(registry)} people after GC scan")

# 3. gutenberg_lds / pioneer_journals — label often is the speaker name
print("Scanning named gutenberg/pioneer sources...")
for entry in toc:
    eid = entry.get("id", "")
    if eid in ("gutenberg_lds", "pioneer_journals"):
        for item in entry.get("items", []):
            label = item.get("label", "")
            doc_id = item.get("id", "")
            # Heuristic: labels like "Brigham Young Discourses" → extract person name
            m = re.match(r"^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(Discourse|Journal|History|Letter)",
                         label)
            if m:
                register_person(m.group(1), doc_id=doc_id, is_talk=True)

print(f"  {len(registry)} people after gutenberg/pioneer scan")

# ── Build output ─────────────────────────────────────────────────────────────

people = []
for pid, rec in registry.items():
    if rec["quote_count"] + rec["talk_count"] == 0:
        continue
    people.append({
        "id": pid,
        "name": rec["name"],
        "variants": sorted(rec["variants"]),
        "roles": sorted(rec["roles"]),
        "doc_ids": sorted(rec["doc_ids"]),
        "quote_count": rec["quote_count"],
        "talk_count": rec["talk_count"],
    })

people.sort(key=lambda x: -(x["quote_count"] + x["talk_count"]))

# people_index: lowercased name + all variants → person_id
# Sorted longest-first so JS can match greedily
index = {}
for p in people:
    for v in [p["name"]] + p["variants"]:
        key = v.lower().strip()
        if key and len(key) >= 3:
            index[key] = p["id"]

os.makedirs(OUT_DIR, exist_ok=True)

with open(os.path.join(OUT_DIR, "people.json"), "w") as f:
    json.dump(people, f, indent=2, ensure_ascii=False)

with open(os.path.join(OUT_DIR, "people_index.json"), "w") as f:
    # Sort keys longest-first for greedy JS matching
    sorted_index = dict(sorted(index.items(), key=lambda x: -len(x[0])))
    json.dump(sorted_index, f, indent=2, ensure_ascii=False)

print(f"\nDone.")
print(f"  {len(people)} people → library/entities/people.json")
print(f"  {len(index)} name variants → library/entities/people_index.json")
print(f"\nTop 10:")
for p in people[:10]:
    print(f"  {p['name']:40s}  quotes={p['quote_count']:3d}  talks={p['talk_count']:3d}")
