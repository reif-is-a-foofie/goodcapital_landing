#!/usr/bin/env python3
"""
Build clickable word indexes for generated source docs.

Default behavior:
  - Standard Works verses
  - All generated source collections from library/source_toc.json

Outputs:
  library/sources/<group>/<slug>_words.json
"""

import json
import math
import re
import argparse
from collections import defaultdict
from pathlib import Path

from build_word_index import SOURCE_PRIORITY, tokenize, truncate


REPO = Path(__file__).resolve().parent.parent
LIBRARY = REPO / "library"
SOURCE_TOC = LIBRARY / "source_toc.json"
STANDARD_WORKS_CATALOG = REPO / "lds_pipeline" / "cache" / "standard_works" / "verse_catalog.json"
MAX_SELECTED_STEMS = 10
MAX_CANDIDATES = 60
MAX_POSTINGS = 6000
MIN_WORD_SCORE = 0.38
MAX_MATCHES = 4
MAX_PREVIEW_LEN = 220


def morsel_sort_key(m: dict):
    return (
        SOURCE_PRIORITY.get(m.get("s", ""), 9),
        -(m.get("w", 0)),
        m.get("lb", ""),
    )

def build_scripture_morsels():
    catalog = json.loads(STANDARD_WORKS_CATALOG.read_text(encoding="utf-8"))
    morsels = []
    for row in catalog:
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        forms_by_stem = defaultdict(set)
        for form, stem in tokenize(text):
            forms_by_stem[stem].add(form)
        stems = set(forms_by_stem.keys())
        if not stems:
            continue
        morsels.append({
            "source": "standard_works",
            "label": f"{row['book']} {row['chapter']}:{row['verse']}",
            "text": text,
            "stems": stems,
            "forms_by_stem": forms_by_stem,
        })
    return morsels


def available_groups():
    toc = json.loads(SOURCE_TOC.read_text(encoding="utf-8"))
    return [collection["id"] for collection in toc]


def load_target_docs(target_groups=None):
    toc = json.loads(SOURCE_TOC.read_text(encoding="utf-8"))
    docs = []
    morsels = []
    target_groups = set(target_groups or available_groups())

    for collection in toc:
        if collection["id"] not in target_groups:
            continue
        for item in collection.get("items", []):
            html_path = LIBRARY / item["href"]
            if not html_path.exists():
                continue
            html = html_path.read_text(encoding="utf-8")
            para_texts = re.findall(r'<p class="source-para">(.*?)</p>', html, re.S)
            paragraphs = []
            for idx, raw in enumerate(para_texts, start=1):
                text = re.sub(r"<[^>]+>", " ", raw)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 60:
                    paragraphs.append({"idx": idx, "text": text, "words": {}})
                    continue
                forms_by_stem = defaultdict(set)
                for form, stem in tokenize(text):
                    forms_by_stem[stem].add(form)
                stems = set(forms_by_stem.keys())
                paragraphs.append({"idx": idx, "text": text, "words": {}, "stems": stems, "forms_by_stem": forms_by_stem})
                if stems:
                    morsels.append({
                        "source": collection["id"],
                        "label": item["label"],
                        "text": text,
                        "stems": stems,
                        "forms_by_stem": forms_by_stem,
                        "doc_id": item["id"],
                        "para_idx": idx,
                    })
            docs.append({
                "collection": collection["id"],
                "item": item,
                "html_path": html_path,
                "paragraphs": paragraphs,
            })
    return docs, morsels


def build_indexes(target_groups=None, force=False):
    docs, source_morsels = load_target_docs(target_groups)
    all_morsels = build_scripture_morsels() + source_morsels
    postings = defaultdict(list)
    for idx, morsel in enumerate(all_morsels):
        for stem in morsel["stems"]:
            postings[stem].append(idx)
    total = len(all_morsels)
    idf = {stem: math.log((total + 1) / (len(ids) + 1)) + 1.0 for stem, ids in postings.items()}

    source_offset = len(all_morsels) - len(source_morsels)
    source_lookup = {(m["doc_id"], m["para_idx"]): source_offset + idx for idx, m in enumerate(source_morsels)}

    for doc in docs:
        morsel_catalog = []
        morsel_ref = {}
        words_out = {}
        for para in doc["paragraphs"]:
            stems = para.get("stems", set())
            if not stems:
                continue

            self_idx = source_lookup.get((doc["item"]["id"], para["idx"]))
            selected = sorted(stems, key=lambda st: idf.get(st, 0), reverse=True)[:MAX_SELECTED_STEMS]
            candidate_scores = defaultdict(float)

            for stem in selected:
                ids = postings.get(stem, [])
                if len(ids) > MAX_POSTINGS:
                    continue
                base = idf.get(stem, 1.0)
                for idx in ids:
                    if idx == self_idx:
                        continue
                    morsel = all_morsels[idx]
                    weight = base * (1.12 if morsel["source"] == "standard_works" else 1.0)
                    if morsel.get("doc_id") == doc["item"]["id"]:
                        weight *= 0.86
                    candidate_scores[idx] += weight

            top_candidates = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)[:MAX_CANDIDATES]
            top_score = top_candidates[0][1] if top_candidates else 1.0

            para_words = {}
            for stem, forms in para["forms_by_stem"].items():
                match_refs = []
                for idx, score in top_candidates:
                    morsel = all_morsels[idx]
                    if stem not in morsel["stems"]:
                        continue
                    weight = round(0.18 + 0.72 * (score / top_score), 3)
                    match = {
                        "s": morsel["source"],
                        "lb": morsel["label"],
                        "x": truncate(morsel["text"], MAX_PREVIEW_LEN),
                        "w": weight,
                    }
                    if morsel.get("doc_id"):
                        match["d"] = morsel["doc_id"]
                    if morsel.get("para_idx"):
                        match["p"] = morsel["para_idx"]
                    key = (
                        match["s"], match["lb"], match["x"], match["w"],
                        match.get("d", ""), match.get("p", 0)
                    )
                    ref = morsel_ref.get(key)
                    if ref is None:
                        ref = len(morsel_catalog)
                        morsel_ref[key] = ref
                        morsel_catalog.append(match)
                    match_refs.append(ref)
                    if len(match_refs) >= MAX_MATCHES:
                        break
                if not match_refs:
                    continue
                score = round(sum(morsel_catalog[ref]["w"] for ref in match_refs), 3)
                if score < MIN_WORD_SCORE:
                    continue
                para_words[stem] = {
                    "score": score,
                    "forms": sorted(forms, key=len, reverse=True)[:3],
                    "m": match_refs,
                }

            if para_words:
                words_out[str(para["idx"])] = para_words

        words_path = doc["html_path"].with_name(doc["html_path"].stem + "_words.json")
        if words_path.exists() and not force:
            continue
        payload = {"_m": morsel_catalog, "v": words_out}
        words_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{doc['collection']} :: {doc['item']['label']}: {len(words_out)} annotated paragraphs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--groups",
        nargs="*",
        help="Optional source collection ids to build. Defaults to all collections in source_toc.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild existing _words.json files instead of skipping them.",
    )
    args = parser.parse_args()
    build_indexes(args.groups, force=args.force)
