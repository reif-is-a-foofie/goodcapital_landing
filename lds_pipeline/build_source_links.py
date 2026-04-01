#!/usr/bin/env python3
"""
build_source_links.py
=====================
Build a reverse index from the chapter graph files:
  source paragraph → list of verses that semantically reference it

Output: library/source_links.json
Format:
  {
    "doc_id": {
      "para_idx": [
        {"book": "Genesis", "ch": 1, "v": 3, "score": 0.71, "ref": "Genesis 1:3"}
      ]
    }
  }

Only paragraphs with resolved doc_id (d) and paragraph index (p) are indexed.

Run from repo root:
    python3 lds_pipeline/build_source_links.py
"""

import json
from collections import defaultdict
from pathlib import Path

REPO       = Path(__file__).parent.parent
CHAPTERS   = REPO / "library" / "chapters"
OUT_FILE   = REPO / "library" / "source_links.json"
MAX_REFS   = 20   # max verses per paragraph in the index


def build_ref_label(book: str, chapter: int, verse: int) -> str:
    return f"{book} {chapter}:{verse}"


def main():
    # Map: doc_id → para_idx → list of verse refs
    index: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    graph_files = sorted(CHAPTERS.glob("*_graph.json"))
    print(f"Scanning {len(graph_files):,} chapter graph files...")

    for gf in graph_files:
        try:
            graph = json.loads(gf.read_text(encoding="utf-8"))
        except Exception:
            continue

        nodes   = graph.get("nodes", [])
        edges   = graph.get("edges", [])

        # Build local node lookup
        node_map = {n["id"]: n for n in nodes}

        # Build verse node lookup by id
        verse_nodes = {n["id"]: n for n in nodes if n.get("t") == "v"}

        # For each edge, check if the target (passage) has d+p resolved
        for edge in edges:
            src_id = edge.get("s", "")
            tgt_id = edge.get("t", "")
            score  = edge.get("w", 0)

            vnode = verse_nodes.get(src_id)
            pnode = node_map.get(tgt_id)

            if not vnode or not pnode:
                continue
            if pnode.get("t") != "p":
                continue

            doc_id  = pnode.get("d")
            para_p  = pnode.get("p")
            if not doc_id or para_p is None:
                continue

            book    = vnode.get("bk") or ""
            chapter = vnode.get("ch") or 0
            verse   = vnode.get("n") or 0

            # Fall back: book/chapter from filename stem
            if not book or not chapter:
                stem = gf.stem.replace("_graph", "")
                # Stem format: book_slug_chapter  e.g. genesis_1
                parts = stem.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    chapter = int(parts[1])
                    book = parts[0].replace("_", " ").title()

            verse_num = vnode.get("n", 0)
            if not book or not chapter:
                continue

            ref_entry = {
                "book":  book,
                "ch":    chapter,
                "v":     verse_num,
                "score": score,
                "ref":   build_ref_label(book, chapter, verse_num),
            }

            key = str(para_p)
            refs = index[doc_id][key]
            if len(refs) < MAX_REFS:
                refs.append(ref_entry)

    # Sort each para's refs by score descending, deduplicate
    output = {}
    total_entries = 0
    for doc_id, paras in index.items():
        output[doc_id] = {}
        for para_key, refs in paras.items():
            # Deduplicate by (book, ch, v)
            seen = set()
            unique = []
            for r in sorted(refs, key=lambda x: -x["score"]):
                key2 = (r["book"], r["ch"], r["v"])
                if key2 not in seen:
                    seen.add(key2)
                    unique.append(r)
            output[doc_id][para_key] = unique[:MAX_REFS]
            total_entries += len(unique)

    OUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    doc_count  = len(output)
    para_count = sum(len(paras) for paras in output.values())
    print(f"Done. {doc_count} documents, {para_count} paragraphs, {total_entries} verse refs → {OUT_FILE}")


if __name__ == "__main__":
    main()
