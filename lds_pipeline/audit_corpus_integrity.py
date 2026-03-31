#!/usr/bin/env python3
"""
Audit scripture integrity and semantic coverage from generated artifacts.

The script is read-only. It scans:
  - library/chapters/*.html
  - library/chapters/*_words.json
  - library/source_toc.json
  - library/sources/**/*_words.json

It produces a JSON report plus a short text summary that can be checked into
diagnostics/ or inspected locally.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup


REPO = Path(__file__).resolve().parent.parent
LIBRARY = REPO / "library"
CHAPTERS = LIBRARY / "chapters"
SOURCE_TOC = LIBRARY / "source_toc.json"
VERSE_CATALOG = REPO / "lds_pipeline" / "cache" / "standard_works" / "verse_catalog.json"


def slugify_book(book: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", book.lower()).strip("_")


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("\u00a0", " ")
    return text


def canonicalize(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]])", r"\1", text)
    return text


def load_catalog() -> dict[str, dict[str, str]]:
    catalog = json.loads(VERSE_CATALOG.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for row in catalog:
        slug = f"{slugify_book(str(row['book']))}_{int(row['chapter'])}"
        out[slug][str(int(row["verse"]))] = str(row["text"])
    return out


def extract_verse_text(verse_div) -> str:
    verse_text = verse_div.select_one(".verse-text")
    if verse_text is not None:
        text = verse_text.get_text(" ", strip=True)
    else:
        text = verse_div.get_text(" ", strip=True)
        text = re.sub(r"^\d+\s*", "", text)
    return normalize_text(text)


def load_words_payload(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_chapter_words(payload) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return 0, 0
    # Scripture chapter format: { "1": {stem: {...}}, ... }
    verse_map = payload.get("v") if "v" in payload else payload
    if not isinstance(verse_map, dict):
        return 0, 0
    annotated = 0
    matched = 0
    for verse_data in verse_map.values():
        if not isinstance(verse_data, dict) or not verse_data:
            continue
        annotated += 1
        for entry in verse_data.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("matches") or entry.get("m"):
                matched += 1
                break
    return annotated, matched


def count_source_words(payload) -> tuple[int, int]:
    if not isinstance(payload, dict) or "v" not in payload:
        return 0, 0
    verse_map = payload.get("v", {})
    if not isinstance(verse_map, dict):
        return 0, 0
    annotated = 0
    matched = 0
    for verse_data in verse_map.values():
        if not isinstance(verse_data, dict) or not verse_data:
            continue
        annotated += 1
        for entry in verse_data.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("m"):
                matched += 1
                break
    return annotated, matched


def chapter_integrity_report(catalog: dict[str, dict[str, str]]) -> dict:
    summary = {
        "chapters": 0,
        "verses": 0,
        "missing_words_files": 0,
        "verses_with_truncation": 0,
        "verses_with_escaped_markup": 0,
        "verses_with_markup_leak": 0,
    }
    chapter_rows = []
    missing_words_chapters = []
    issues = []

    for path in sorted(CHAPTERS.glob("*.html")):
        if path.name.endswith(("_notes.html", "_words.html", "_graph.html")):
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        verses = soup.select("div.verse[id]")
        if not verses:
            continue
        summary["chapters"] += 1
        slug = path.stem
        words_path = path.with_name(f"{path.stem}_words.json")
        words_payload = load_words_payload(words_path)
        if words_payload is None:
            summary["missing_words_files"] += 1
            missing_words_chapters.append(slug)
        annotated, matched = count_chapter_words(words_payload)

        chapter_issues = []
        verse_total = 0
        verse_annotated = 0
        verse_matched = 0

        for verse_div in verses:
            verse_id = verse_div.get("id", "")
            if not verse_id.startswith("v") or not verse_id[1:].isdigit():
                continue
            vnum = verse_id[1:]
            verse_total += 1
            summary["verses"] += 1
            raw = str(verse_div)
            text = extract_verse_text(verse_div)
            canon = canonicalize(catalog.get(slug, {}).get(vnum, ""))
            if canon and text:
                text_cmp = canonicalize(text)
                if text_cmp != canon:
                    # Detect clear truncation or verse corruption. Keep the heuristic narrow.
                    canonical_prefix = canon.startswith(text_cmp[: max(12, min(len(text_cmp), 80))])
                    trailing_fragment = bool(re.search(r"\b(and|to|that|of|from|shall|should|know)$", text_cmp.lower()))
                    short_ratio = len(text_cmp) / max(len(canon), 1) < 0.8
                    if canonical_prefix and (short_ratio or trailing_fragment):
                        summary["verses_with_truncation"] += 1
                        chapter_issues.append({
                            "chapter": slug,
                            "verse": vnum,
                            "kind": "truncation",
                            "excerpt": text[:180],
                            "canonical": canon[:180],
                        })

            literal_markup = "<span class=\"cw\"" in raw or "&lt;span class=\"cw\"" in raw
            literal_markup = literal_markup or "<span class=\"cw\"" in text or "&lt;span class=\"cw\"" in text
            if literal_markup:
                summary["verses_with_escaped_markup"] += 1
                chapter_issues.append({
                    "chapter": slug,
                    "verse": vnum,
                    "kind": "literal_markup",
                    "excerpt": raw[:180],
                })

            if re.search(r'<span class="cw"|<span class="w"|<a class="ref-link"', raw) and "verse-text" not in raw:
                summary["verses_with_markup_leak"] += 1
                chapter_issues.append({
                    "chapter": slug,
                    "verse": vnum,
                    "kind": "markup_leak",
                    "excerpt": raw[:180],
                })

            verse_words = {}
            if isinstance(words_payload, dict):
                verse_words = words_payload.get(vnum) if "v" not in words_payload else words_payload.get("v", {}).get(vnum, {})
            if isinstance(verse_words, dict) and verse_words:
                verse_annotated += 1
                if any(isinstance(entry, dict) and (entry.get("matches") or entry.get("m")) for entry in verse_words.values()):
                    verse_matched += 1

        chapter_rows.append({
            "chapter": slug,
            "verses": verse_total,
            "annotated_verses": verse_annotated or annotated,
            "matched_verses": verse_matched or matched,
            "coverage": round((verse_annotated or annotated) / max(1, verse_total), 3),
            "match_coverage": round((verse_matched or matched) / max(1, verse_total), 3),
            "words_file": str(words_path.relative_to(REPO)) if words_path.exists() else None,
            "issues": chapter_issues[:8],
        })
        issues.extend(chapter_issues)

    chapter_rows.sort(key=lambda row: (row["coverage"], row["match_coverage"], row["verses"]))
    return {
        "summary": summary,
        "chapters": chapter_rows,
        "issues": issues,
        "missing_words_chapters": missing_words_chapters,
    }


def source_coverage_report() -> dict:
    if not SOURCE_TOC.exists():
        return {"summary": {}, "collections": []}

    toc = json.loads(SOURCE_TOC.read_text(encoding="utf-8"))
    collection_rows = []
    summary = {
        "collections": 0,
        "docs": 0,
        "docs_with_words": 0,
        "docs_missing_words": 0,
        "annotated_paragraphs": 0,
        "matched_paragraphs": 0,
    }
    missing_docs = []

    for collection in toc:
        coll_id = collection.get("id", "")
        items = collection.get("items", [])
        summary["collections"] += 1
        collection_docs = 0
        collection_docs_with_words = 0
        annotated = 0
        matched = 0
        for item in items:
            collection_docs += 1
            summary["docs"] += 1
            html_path = LIBRARY / item["href"]
            words_path = html_path.with_name(f"{html_path.stem}_words.json")
            payload = load_words_payload(words_path)
            if payload is not None:
                collection_docs_with_words += 1
                summary["docs_with_words"] += 1
                ann, mat = count_source_words(payload)
                annotated += ann
                matched += mat
                summary["annotated_paragraphs"] += ann
                summary["matched_paragraphs"] += mat
            else:
                summary["docs_missing_words"] += 1
                missing_docs.append(str(words_path.relative_to(REPO)))
        collection_rows.append({
            "collection": coll_id,
            "docs": collection_docs,
            "docs_with_words": collection_docs_with_words,
            "annotated_paragraphs": annotated,
            "matched_paragraphs": matched,
            "doc_coverage": round(collection_docs_with_words / max(1, collection_docs), 3),
        })

    collection_rows.sort(key=lambda row: (row["doc_coverage"], row["annotated_paragraphs"]))
    return {"summary": summary, "collections": collection_rows, "missing_docs": missing_docs}


def write_report(out_json: Path, out_txt: Path, report: dict) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    lines.append("Scripture Integrity")
    lines.append("Note: 'verses_with_escaped_markup' counts literal leaked cw/span markup embedded in verse text.")
    lines.append(json.dumps(report["scripture"]["summary"], indent=2))
    lines.append("")
    lines.append("Lowest-coverage chapters")
    for row in report["scripture"]["chapters"][:20]:
        lines.append(
            f"{row['chapter']}: verses={row['verses']} annotated={row['annotated_verses']} matched={row['matched_verses']} "
            f"coverage={row['coverage']} match_coverage={row['match_coverage']}"
        )
        for issue in row.get("issues", [])[:2]:
            lines.append(f"  - {issue['kind']} v{issue['verse']}: {issue.get('excerpt', '')[:120]}")
    if report["scripture"].get("missing_words_chapters"):
        lines.append("")
        lines.append("Chapters missing word indexes")
        for slug in report["scripture"]["missing_words_chapters"][:50]:
            lines.append(slug)
    lines.append("")
    lines.append("Most markup leakage")
    markup_rows = sorted(
        ((sum(1 for i in row.get("issues", []) if i["kind"] == "literal_markup"), row["chapter"]) for row in report["scripture"]["chapters"]),
        reverse=True,
    )
    for count, chapter in markup_rows[:20]:
        if count:
            lines.append(f"{chapter}: {count}")
    lines.append("")
    lines.append("Most truncation")
    trunc_rows = sorted(
        ((sum(1 for i in row.get("issues", []) if i["kind"] == "truncation"), row["chapter"]) for row in report["scripture"]["chapters"]),
        reverse=True,
    )
    for count, chapter in trunc_rows[:20]:
        if count:
            lines.append(f"{chapter}: {count}")
    lines.append("")
    lines.append("Semantic Coverage")
    lines.append(json.dumps(report["sources"]["summary"], indent=2))
    lines.append("")
    lines.append("Lowest-coverage source collections")
    for row in report["sources"]["collections"][:20]:
        lines.append(
            f"{row['collection']}: docs={row['docs']} with_words={row['docs_with_words']} "
            f"doc_coverage={row['doc_coverage']} annotated_paragraphs={row['annotated_paragraphs']} "
            f"matched_paragraphs={row['matched_paragraphs']}"
        )
    if report["sources"].get("missing_docs"):
        lines.append("")
        lines.append("Source docs missing word indexes")
        for path in report["sources"]["missing_docs"][:100]:
            lines.append(path)
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default="diagnostics/corpus_audit.json")
    parser.add_argument("--txt-out", default="diagnostics/corpus_audit.txt")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when issues are found.")
    args = parser.parse_args()

    catalog = load_catalog()
    scripture = chapter_integrity_report(catalog)
    sources = source_coverage_report()
    report = {"scripture": scripture, "sources": sources}

    write_report(REPO / args.json_out, REPO / args.txt_out, report)

    problems = (
        scripture["summary"]["verses_with_truncation"]
        + scripture["summary"]["verses_with_escaped_markup"]
        + scripture["summary"]["verses_with_markup_leak"]
        + scripture["summary"]["missing_words_files"]
        + sources["summary"].get("docs_missing_words", 0)
    )
    print(json.dumps({
        "scripture": scripture["summary"],
        "sources": sources["summary"],
        "problems": problems,
    }, indent=2))

    return 1 if args.strict and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
