#!/usr/bin/env python3
"""
build_topic_registry.py
Builds library/entities/topics.json + topics_index.json by scanning
all Donaldson files for topic terms.
"""

import json
import os
import re
import glob as glob_module

BASE_DIR = "/Users/reify/Classified/goodcapital_landing"
DONALDSON_DIR = os.path.join(BASE_DIR, "library/donaldson")
PEOPLE_PATH = os.path.join(BASE_DIR, "library/entities/people.json")
OUT_TOPICS = os.path.join(BASE_DIR, "library/entities/topics.json")
OUT_INDEX = os.path.join(BASE_DIR, "library/entities/topics_index.json")

# ── Topic seed list ────────────────────────────────────────────────────────────

TOPICS = [
    {"id": "topic:faith", "name": "Faith", "terms": ["faith", "believe", "belief", "trust in God"]},
    {"id": "topic:repentance", "name": "Repentance", "terms": ["repent", "repentance", "forgiveness of sins", "remission of sins"]},
    {"id": "topic:baptism", "name": "Baptism", "terms": ["baptism", "baptize", "baptized", "born of water", "born again"]},
    {"id": "topic:holy_ghost", "name": "Holy Ghost", "terms": ["Holy Ghost", "Holy Spirit", "Spirit of God", "Comforter", "Spirit of Truth"]},
    {"id": "topic:atonement", "name": "Atonement", "terms": ["atonement", "atone", "reconciliation", "propitiation", "redemption"]},
    {"id": "topic:resurrection", "name": "Resurrection", "terms": ["resurrection", "rise from the dead", "raised from the dead", "resurrected"]},
    {"id": "topic:prayer", "name": "Prayer", "terms": ["prayer", "pray", "petition", "intercession", "supplications"]},
    {"id": "topic:revelation", "name": "Revelation", "terms": ["revelation", "vision", "manifest", "revealed", "thus saith the Lord"]},
    {"id": "topic:prophecy", "name": "Prophecy", "terms": ["prophecy", "prophesy", "prophet", "foretell", "fulfillment of prophecy"]},
    {"id": "topic:priesthood", "name": "Priesthood", "terms": ["priesthood", "Melchizedek", "Aaronic", "ordain", "authority"]},
    {"id": "topic:temple", "name": "Temple", "terms": ["temple", "house of the Lord", "holy of holies", "sanctuary", "tabernacle"]},
    {"id": "topic:salvation", "name": "Salvation", "terms": ["salvation", "saved", "savior", "deliverance", "eternal life"]},
    {"id": "topic:grace", "name": "Grace", "terms": ["grace", "mercy", "unmerited favor", "gift of God", "lovingkindness"]},
    {"id": "topic:obedience", "name": "Obedience", "terms": ["obedience", "obey", "commandments", "keep the commandments", "law of God"]},
    {"id": "topic:agency", "name": "Agency", "terms": ["agency", "free will", "choice", "moral agency", "freedom to choose"]},
    {"id": "topic:charity", "name": "Charity", "terms": ["charity", "love of Christ", "pure love", "benevolence", "compassion"]},
    {"id": "topic:eternal_life", "name": "Eternal Life", "terms": ["eternal life", "everlasting life", "immortality", "life eternal"]},
    {"id": "topic:second_coming", "name": "Second Coming", "terms": ["second coming", "coming of Christ", "millennial", "millennium", "last days", "end times"]},
    {"id": "topic:judgment", "name": "Judgment", "terms": ["judgment", "judge", "bar of God", "day of judgment", "last judgment"]},
    {"id": "topic:creation", "name": "Creation", "terms": ["creation", "creator", "made the world", "in the beginning", "formed the earth"]},
    {"id": "topic:light_of_christ", "name": "Light of Christ", "terms": ["light of Christ", "true light", "light of the world", "divine light", "intelligence"]},
    {"id": "topic:word_of_god", "name": "Word of God", "terms": ["word of God", "word of the Lord", "logos", "scripture", "gospel"]},
    {"id": "topic:covenant", "name": "Covenant", "terms": ["covenant", "covenant people", "Abrahamic covenant", "new covenant", "everlasting covenant"]},
    {"id": "topic:gathering", "name": "Gathering of Israel", "terms": ["gathering", "gather Israel", "restoration of Israel", "lost tribes"]},
    {"id": "topic:zion", "name": "Zion", "terms": ["Zion", "city of Zion", "New Jerusalem", "Zion's camp", "pure in heart"]},
    {"id": "topic:tithing", "name": "Tithing", "terms": ["tithing", "tithe", "tenth", "storehouse"]},
    {"id": "topic:sabbath", "name": "Sabbath", "terms": ["Sabbath", "day of rest", "Lord's day", "first day of the week"]},
    {"id": "topic:fasting", "name": "Fasting", "terms": ["fast", "fasting", "abstain from food", "day of fasting"]},
    {"id": "topic:scripture_study", "name": "Scripture Study", "terms": ["search the scriptures", "study the word", "liken the scriptures", "feast upon the words"]},
    {"id": "topic:discipleship", "name": "Discipleship", "terms": ["disciple", "follow Christ", "take up your cross", "follow me"]},
    {"id": "topic:sin", "name": "Sin", "terms": ["sin", "transgression", "iniquity", "wickedness", "fallen", "carnal"]},
    {"id": "topic:forgiveness", "name": "Forgiveness", "terms": ["forgive", "forgiveness", "pardon", "remit", "cleanse from sin"]},
    {"id": "topic:love", "name": "Love", "terms": ["love", "love thy neighbor", "love God", "greatest commandment", "charity"]},
    {"id": "topic:truth", "name": "Truth", "terms": ["truth", "true", "verily I say", "amen", "the way the truth"]},
    {"id": "topic:humility", "name": "Humility", "terms": ["humble", "humility", "meek", "meekness", "lowly in heart"]},
    {"id": "topic:knowledge", "name": "Knowledge", "terms": ["knowledge", "wisdom", "understanding", "intelligence", "light and truth"]},
    {"id": "topic:eternal_family", "name": "Eternal Family", "terms": ["eternal family", "celestial marriage", "sealed", "forever families", "family proclamation"]},
    {"id": "topic:premortal_life", "name": "Premortal Life", "terms": ["premortal", "pre-existence", "before the foundation", "spirits in heaven", "council in heaven"]},
    {"id": "topic:plan_of_salvation", "name": "Plan of Salvation", "terms": ["plan of salvation", "plan of happiness", "great plan", "plan of redemption"]},
    {"id": "topic:godhead", "name": "Godhead", "terms": ["Godhead", "Trinity", "Father Son and Holy Ghost", "three persons", "one God"]},
    {"id": "topic:holy_spirit", "name": "Gift of the Holy Ghost", "terms": ["gift of the Holy Ghost", "receive the Spirit", "baptism of fire", "confirmation"]},
    {"id": "topic:patriarchal_blessing", "name": "Patriarchal Blessing", "terms": ["patriarchal blessing", "blessing", "patriarch"]},
    {"id": "topic:endowment", "name": "Endowment", "terms": ["endowment", "endued with power", "clothed with power", "temple ordinance"]},
    {"id": "topic:word_of_wisdom", "name": "Word of Wisdom", "terms": ["word of wisdom", "health law", "strong drinks", "tobacco", "hot drinks"]},
    {"id": "topic:missionary_work", "name": "Missionary Work", "terms": ["missionary", "proclaim the gospel", "preach", "sent forth", "go ye therefore"]},
    {"id": "topic:service", "name": "Service", "terms": ["service", "serve", "minister", "serving others", "when ye are in the service"]},
    {"id": "topic:holy_land", "name": "Holy Land", "terms": ["holy land", "land of Israel", "promised land", "land of promise"]},
    {"id": "topic:angels", "name": "Angels", "terms": ["angel", "angels", "heavenly messenger", "ministering of angels", "seraphim", "cherubim"]},
    {"id": "topic:devil", "name": "Devil and Adversary", "terms": ["devil", "Satan", "adversary", "lucifer", "prince of darkness", "enemy of God"]},
]

# Deduplicate by id (tithing appears twice in seed list)
seen_ids: set[str] = set()
unique_topics = []
for t in TOPICS:
    if t["id"] not in seen_ids:
        seen_ids.add(t["id"])
        unique_topics.append(t)
TOPICS = unique_topics

# ── Helpers ────────────────────────────────────────────────────────────────────

CHAPTER_RE = re.compile(r'^(.+?)_(\d+)\.json$')

def make_person_id(name: str) -> str:
    s = name.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return f"person:{s}"

# Load people index for name resolution
people_data = json.load(open(PEOPLE_PATH))
name_to_id: dict[str, str] = {}
for p in people_data:
    name_to_id[p["name"].lower()] = p["id"]
    for v in p.get("variants", []):
        name_to_id[v.lower()] = p["id"]

def resolve_person_id(name: str) -> str:
    lo = name.lower().strip()
    return name_to_id.get(lo, make_person_id(name))

def extract_sentence(text: str, term: str) -> str:
    """Return the sentence containing `term` (case-insensitive)."""
    lo = text.lower()
    idx = lo.find(term.lower())
    if idx == -1:
        return ""
    # Find sentence boundaries
    start = text.rfind('.', 0, idx)
    start = 0 if start == -1 else start + 1
    end = text.find('.', idx)
    end = len(text) if end == -1 else end + 1
    return text[start:end].strip()

def build_patterns(terms: list[str]):
    return [(t, re.compile(r'\b' + re.escape(t) + r'\b', re.IGNORECASE)) for t in terms]

# ── Per-topic accumulators ─────────────────────────────────────────────────────

# topic_id -> {excerpts, related_people, related_scriptures}
accum: dict[str, dict] = {}
for t in TOPICS:
    accum[t["id"]] = {
        "terms": t["terms"],
        "name": t["name"],
        "excerpts": [],
        "related_people": set(),
        "related_scriptures": set(),
    }

# Pre-build compiled patterns per topic
topic_patterns = {}
for t in TOPICS:
    topic_patterns[t["id"]] = build_patterns(t["terms"])

# ── Scan all Donaldson files ───────────────────────────────────────────────────

don_files = sorted(glob_module.glob(os.path.join(DONALDSON_DIR, "*.json")))
print(f"Scanning {len(don_files)} Donaldson files...")

for fpath in don_files:
    fname = os.path.basename(fpath)
    m = CHAPTER_RE.match(fname)
    if not m:
        continue
    book_slug = m.group(1)
    chapter_num = m.group(2)

    try:
        verse_data = json.load(open(fpath))
    except Exception:
        continue

    for verse_num, verse in verse_data.items():
        ref_str = f"{book_slug.replace('_', ' ').title()} {chapter_num}:{verse_num}"

        notes = verse.get("notes", [])
        quotes = verse.get("quotes", [])

        for topic_id, patterns in topic_patterns.items():
            acc = accum[topic_id]
            max_excerpts = 8

            # -- Scan notes --
            for note_text in notes:
                if not isinstance(note_text, str):
                    continue
                for term, pat in patterns:
                    if pat.search(note_text):
                        sentence = extract_sentence(note_text, term)
                        if sentence and len(acc["excerpts"]) < max_excerpts:
                            acc["excerpts"].append({
                                "text": sentence[:600],
                                "source": "donaldson",
                                "ref": ref_str,
                                "speaker": None,
                                "attr": None,
                            })
                        acc["related_scriptures"].add(ref_str)
                        break  # one match per note per topic is enough

            # -- Scan quotes --
            for q in quotes:
                q_text = q.get("text", "")
                if not isinstance(q_text, str):
                    continue
                speaker = q.get("speaker", "")
                for term, pat in patterns:
                    if pat.search(q_text):
                        pid = resolve_person_id(speaker) if speaker else None
                        if pid:
                            acc["related_people"].add(pid)
                        if len(acc["excerpts"]) < max_excerpts:
                            acc["excerpts"].append({
                                "text": extract_sentence(q_text, term)[:600] or q_text[:600],
                                "source": "gc",
                                "ref": ref_str,
                                "speaker": pid,
                                "attr": q.get("attr", ""),
                            })
                        acc["related_scriptures"].add(ref_str)
                        break

# ── Build output ───────────────────────────────────────────────────────────────

topics_out = []
for t in TOPICS:
    tid = t["id"]
    acc = accum[tid]
    topics_out.append({
        "id": tid,
        "name": acc["name"],
        "terms": t["terms"],
        "excerpts": acc["excerpts"],
        "related_people": sorted(acc["related_people"]),
        "related_places": [],
        "related_things": [],
        "related_scriptures": sorted(acc["related_scriptures"]),
    })

topics_index = {t["name"].lower(): t["id"] for t in topics_out}

os.makedirs(os.path.dirname(OUT_TOPICS), exist_ok=True)
with open(OUT_TOPICS, "w") as f:
    json.dump(topics_out, f, indent=2, ensure_ascii=False)
with open(OUT_INDEX, "w") as f:
    json.dump(topics_index, f, indent=2, ensure_ascii=False)

print(f"Wrote {len(topics_out)} topics to {OUT_TOPICS}")
print(f"Wrote topics index to {OUT_INDEX}")

# ── Summary ────────────────────────────────────────────────────────────────────

total_excerpts = sum(len(t["excerpts"]) for t in topics_out)
total_scriptures = sum(len(t["related_scriptures"]) for t in topics_out)
n = len(topics_out)

print(f"\nTotal topics: {n}")
print(f"Avg excerpts per topic: {total_excerpts/n:.1f}")
print(f"Avg scriptures per topic: {total_scriptures/n:.1f}")

top5 = sorted(topics_out, key=lambda t: len(t["related_scriptures"]), reverse=True)[:5]
print("\nTop 5 topics by scripture count:")
for t in top5:
    print(f"  {t['name']:<30} {len(t['related_scriptures'])} scriptures, {len(t['excerpts'])} excerpts, {len(t['related_people'])} people")
