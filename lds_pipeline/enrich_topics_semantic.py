#!/usr/bin/env python3
"""
enrich_topics_semantic.py
Adds a semantic enrichment layer to library/entities/topics.json by querying
the FAISS embedding index with concept-rich anchor phrases for each topic.

Requires: correlate_embeddings.py to have been run first (builds the FAISS index).
"""

import json
import os
import sys
import pickle

BASE_DIR = "/Users/reify/Classified/goodcapital_landing"
TOPICS_PATH = os.path.join(BASE_DIR, "library/entities/topics.json")
INDEX_PATH = os.path.join(BASE_DIR, "lds_pipeline/cache/embeddings/faiss.index")
META_PATH = os.path.join(BASE_DIR, "lds_pipeline/cache/embeddings/metadata.pkl")

# ── Topic anchor phrases ───────────────────────────────────────────────────────
# Rich descriptive phrases that capture the CONCEPT semantically, not just keyword.

TOPIC_ANCHORS = {
    "topic:faith": "trust in God, believing without seeing, assurance of things hoped for, confidence in divine promises",
    "topic:repentance": "turning from sin, godly sorrow, forsaking wickedness, restoration through mercy",
    "topic:baptism": "immersion in water, covenant with God, born again, remission of sins through water",
    "topic:holy_ghost": "comforter sent by Christ, spirit of truth, gift of the Holy Spirit, still small voice",
    "topic:atonement": "Christ's suffering in Gethsemane, infinite sacrifice, reconciliation between God and man, mercy satisfying justice",
    "topic:resurrection": "spirit reunited with body, rising from the dead, immortality, firstfruits of them that slept",
    "topic:prayer": "communication with God, petitions before the Lord, asking in faith, thy will be done",
    "topic:revelation": "God speaking to prophets, visions from heaven, word of the Lord, open canon",
    "topic:prophecy": "foretelling future events, inspired declaration, testimony of Jesus is spirit of prophecy",
    "topic:priesthood": "authority to act in God's name, Melchizedek order, power to seal on earth and heaven",
    "topic:temple": "sacred space where heaven meets earth, ordinances for living and dead, endowment with power",
    "topic:salvation": "deliverance from sin and death, exaltation in God's presence, eternal life through Christ",
    "topic:grace": "unmerited divine favor, enabling power beyond human effort, mercy and lovingkindness",
    "topic:obedience": "keeping commandments, hearkening to the voice of the Lord, law written on heart",
    "topic:agency": "freedom to choose between good and evil, moral responsibility, opposition in all things",
    "topic:charity": "pure love of Christ, selfless service, greater than faith or hope, never faileth",
    "topic:eternal_life": "living in God's presence forever, knowing the Father and Son, inheritance of all things",
    "topic:second_coming": "Christ's return in glory, millennial reign, gathering of elect, signs of the times",
    "topic:judgment": "all accountable before God, works examined, sheep separated from goats, bar of God",
    "topic:creation": "God formed the earth, worlds without number, matter organized not created ex nihilo",
    "topic:light_of_christ": "divine intelligence given to all mankind, conscience, light that enlightens every soul",
    "topic:word_of_god": "living word, scriptures as divine instruction, logos incarnate, sword of the spirit",
    "topic:covenant": "binding promises between God and man, Abrahamic covenant, new and everlasting covenant",
    "topic:gathering": "Israel scattered and gathered again, Zion built up, lost tribes return, spiritual gathering",
    "topic:zion": "pure in heart society, city of Enoch, New Jerusalem, place of peace and holiness",
    "topic:tithing": "tenth part consecrated to God, windows of heaven opened, storehouse of the Lord",
    "topic:sabbath": "holy day of rest, remembering the Lord's creation, ceasing from worldly labor",
    "topic:fasting": "abstaining from food in spiritual devotion, humbling the soul, combined with prayer",
    "topic:scripture_study": "feasting on the word of God, searching the scriptures daily, comparing spiritual things",
    "topic:discipleship": "taking up the cross, forsaking all to follow Christ, enduring to the end",
    "topic:sin": "transgression of divine law, fallen nature, spiritual death, estrangement from God",
    "topic:forgiveness": "releasing debt of sin, mercy triumphing over judgment, clean before God",
    "topic:love": "greatest commandment, love God and neighbor, perfect love casteth out fear",
    "topic:truth": "eternal principle, God cannot lie, truth sets free, light and truth forsake evil",
    "topic:humility": "meekness before God, broken heart and contrite spirit, lowly in heart",
    "topic:knowledge": "intelligence is the glory of God, light and truth, eternal increase of wisdom",
    "topic:eternal_family": "families sealed together forever, celestial marriage, children of God eternally",
    "topic:premortal_life": "spirits before earth life, council in heaven, war in heaven, foreordination",
    "topic:plan_of_salvation": "God's great plan for eternal progression, fall and atonement designed together",
    "topic:godhead": "Father Son and Holy Ghost distinct beings, united in purpose, Joseph Smith's First Vision",
    "topic:holy_spirit": "receiving the Holy Ghost by laying on of hands, baptism of fire and the Spirit",
    "topic:endowment": "clothed with power from on high, temple ceremony, covenant of consecration",
    "topic:word_of_wisdom": "God's law of health, avoiding harmful substances, promised blessings for obedience",
    "topic:missionary_work": "every member a missionary, proclaim gospel to all nations, preparing a people",
    "topic:service": "when ye are in service of fellow beings ye are in service of God, losing self in serving",
    "topic:holy_land": "land promised to Abraham's seed, sacred geography of the Bible, land flowing with milk and honey",
    "topic:angels": "ministering spirits, messengers from God's presence, Michael Gabriel Moroni, ministering of angels",
    "topic:devil": "fallen angel Lucifer, father of lies, accuser of brethren, bound during millennium",
}

# ── FAISS search (direct model access, bypassing verse-centric search()) ───────

sys.path.insert(0, os.path.join(BASE_DIR, "lds_pipeline"))

from sources.embeddings import _get_model, _load_index
import sources.embeddings as _emb_mod


def search_semantic(query_text: str, top_k: int = 8, min_score: float = 0.35) -> list[dict]:
    """
    Embed a concept/anchor phrase and return top_k similar passages from the FAISS index.
    Operates directly on the embedding model — no verse-centric query format.
    """
    if not _load_index():
        return []

    import faiss
    import numpy as np

    _index = _emb_mod._index
    _metadata = _emb_mod._metadata

    if _index is None or _metadata is None:
        return []

    model = _get_model()
    vec = model.encode([query_text], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(vec)

    scores, indices = _index.search(vec, top_k * 3)

    results = []
    seen = set()

    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or float(score) < min_score:
            continue
        chunk = _metadata[idx]
        key = chunk["text"][:80]
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "text": chunk["text"],
            "source": chunk.get("source", ""),
            "ref": chunk.get("ref", ""),
            "score": round(float(score), 3),
            "semantic": True,
        })
        if len(results) >= top_k:
            break

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # 1. Check FAISS index
    if not os.path.exists(INDEX_PATH):
        print("FAISS index not built yet — semantic enrichment will run after correlate_embeddings.py is run")
        sys.exit(0)

    print(f"FAISS index found: {INDEX_PATH}")
    index_mb = os.path.getsize(INDEX_PATH) / 1e6
    print(f"  Index size: {index_mb:.1f} MB")

    # 2. Load topics.json
    if not os.path.exists(TOPICS_PATH):
        print(f"ERROR: topics.json not found at {TOPICS_PATH}")
        print("Run build_topic_registry.py first.")
        sys.exit(1)

    with open(TOPICS_PATH) as f:
        topics = json.load(f)
    print(f"Loaded {len(topics)} topics from {TOPICS_PATH}")

    # 3. Enrich each topic that has an anchor
    topics_enriched = 0
    total_semantic_excerpts = 0
    faith_sample = None

    for topic in topics:
        tid = topic["id"]
        anchor = TOPIC_ANCHORS.get(tid)
        if not anchor:
            continue

        # Search FAISS with the anchor phrase
        semantic_hits = search_semantic(anchor, top_k=8, min_score=0.35)

        if not semantic_hits:
            continue

        # Build dedup key set from existing excerpts (first 80 chars)
        existing_keys = set()
        for ex in topic.get("excerpts", []):
            existing_keys.add(ex.get("text", "")[:80])

        # Filter out duplicates, mark as semantic
        new_semantic = []
        for hit in semantic_hits:
            key = hit["text"][:80]
            if key not in existing_keys:
                existing_keys.add(key)
                new_semantic.append(hit)

        if not new_semantic:
            continue

        # Merge: existing string-match excerpts first, then semantic
        merged = topic.get("excerpts", []) + new_semantic

        # Sort: string-match (no semantic key) first, then semantic; within each group by score desc
        def sort_key(ex):
            is_semantic = 1 if ex.get("semantic") else 0
            score = -ex.get("score", 0.0)
            return (is_semantic, score)

        merged.sort(key=sort_key)
        topic["excerpts"] = merged

        topics_enriched += 1
        total_semantic_excerpts += len(new_semantic)

        # Capture faith sample for reporting
        if tid == "topic:faith" and faith_sample is None:
            faith_sample = new_semantic

        print(f"  {tid:<40} +{len(new_semantic)} semantic excerpts (top score: {new_semantic[0]['score']:.3f})")

    # 4. Save updated topics.json
    with open(TOPICS_PATH, "w") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)

    print(f"\nSaved enriched topics to {TOPICS_PATH}")
    print(f"\n--- Summary ---")
    print(f"Topics enriched:          {topics_enriched}")
    print(f"Total semantic excerpts:  {total_semantic_excerpts}")
    print(f"Avg per enriched topic:   {total_semantic_excerpts / max(topics_enriched, 1):.1f}")

    # 5. Faith sample report
    if faith_sample:
        print(f"\n--- Faith semantic sample (passages not requiring the word 'faith') ---")
        non_faith = [h for h in faith_sample if "faith" not in h["text"].lower()]
        shown = non_faith[:5] if non_faith else faith_sample[:5]
        for i, h in enumerate(shown, 1):
            excerpt = h["text"][:200].replace("\n", " ")
            print(f"\n  [{i}] score={h['score']} source={h['source']} ref={h.get('ref','')}")
            print(f"      {excerpt}...")
        if not non_faith:
            print("  (all top faith hits contained the word 'faith' — try lowering min_score or expanding anchor)")
    else:
        print("\nNo faith semantic hits found (FAISS index may be empty or scores below threshold).")


if __name__ == "__main__":
    main()
