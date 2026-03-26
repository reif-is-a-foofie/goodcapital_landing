#!/usr/bin/env python3

import json
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parent
TOC = REPO / "library" / "source_toc.json"
WORDS = REPO / "library" / "chapters"


def main() -> None:
    data = json.loads(TOC.read_text(encoding="utf-8"))
    all_ids = []
    collection_sizes = {}

    for collection in data:
        items = collection.get("items", [])
        collection_sizes[collection["id"]] = len(items)
        for item in items:
            all_ids.append(item["id"])
            href = REPO / "library" / item["href"]
            if not href.exists():
                raise SystemExit(f"missing href target: {item['id']} -> {item['href']}")

    dupes = [doc_id for doc_id, count in Counter(all_ids).items() if count > 1]
    if dupes:
        raise SystemExit(f"duplicate source doc ids: {dupes[:10]}")

    if collection_sizes.get("times_and_seasons", 0) < 20:
        raise SystemExit("times_and_seasons split regression: expected at least 20 issue docs")

    if collection_sizes.get("millennial_star", 0) < 100:
        raise SystemExit("millennial_star split regression: expected at least 100 issue docs")

    john_words = json.loads((WORDS / "john_3_words.json").read_text(encoding="utf-8"))
    pharisee = john_words.get("1", {}).get("pharisee", {})
    jd_matches = [
        match for match in pharisee.get("matches", [])
        if match.get("s") == "journal_of_discourses"
    ]
    if not jd_matches:
        raise SystemExit("john_3 pharisee regression: expected a Journal of Discourses match")
    if not jd_matches[0].get("d") or not jd_matches[0].get("p"):
        raise SystemExit("john_3 pharisee regression: scripture-side source match missing stable doc/paragraph ids")

    print("source artifact regression passed")
    for key in ("times_and_seasons", "millennial_star"):
        print(f"{key}: {collection_sizes.get(key, 0)} docs")
    print(f"john_3 pharisee doc target: {jd_matches[0]['d']} ¶{jd_matches[0]['p']}")


if __name__ == "__main__":
    main()
