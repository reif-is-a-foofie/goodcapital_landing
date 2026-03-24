"""
One-time migration: extract Donaldson commentary from verse_catalog.json
into cache/donaldson/ as a standalone source corpus, then strip the
donaldson field from the catalog so it's clean scripture-only data.

Run once:
  python3 extract_donaldson_source.py
"""
import json
from pathlib import Path

CACHE_DIR    = Path("/Users/reify/lds_pipeline/cache")
CATALOG_PATH = CACHE_DIR / "verse_catalog.json"
DONA_DIR     = CACHE_DIR / "donaldson"


def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(catalog):,} verses")

    DONA_DIR.mkdir(exist_ok=True)

    total_paras = 0
    verses_with_dona = 0
    all_passages = []

    for v in catalog:
        paras = v.get("donaldson", [])
        if not paras:
            continue
        verses_with_dona += 1
        total_paras += len(paras)

        key = f"{v['book']}_{v['chapter']}_{v['verse']}"
        out = {
            "book":    v["book"],
            "chapter": v["chapter"],
            "verse":   v["verse"],
            "verse_text": v.get("text", ""),
            "paragraphs": paras,
        }
        (DONA_DIR / f"{key}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        for para in paras:
            all_passages.append({
                "source": "donaldson",
                "label":  f"Donaldson on {v['book']} {v['chapter']}:{v['verse']}",
                "origin_book":    v["book"],
                "origin_chapter": v["chapter"],
                "origin_verse":   v["verse"],
                "text": para,
            })

    # Write a single flat corpus file for bulk loading
    corpus_path = DONA_DIR / "corpus.json"
    corpus_path.write_text(
        json.dumps(all_passages, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Extracted: {verses_with_dona:,} verses, {total_paras:,} paragraphs")
    print(f"Corpus written: {corpus_path}  ({corpus_path.stat().st_size/1e6:.1f} MB)")

    # Strip donaldson field from catalog
    for v in catalog:
        v.pop("donaldson", None)

    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Catalog updated: donaldson field removed from all {len(catalog):,} entries")


if __name__ == "__main__":
    main()
