#!/usr/bin/env python3
"""
repair_truncated_verses.py
==========================
Repairs truncated verse text in scripture chapter HTML files by replacing
verse-text span content with properly annotated text from the verse catalog.

A verse is considered truncated when its extracted text is a prefix of the
canonical text AND is significantly shorter (< 80% length) OR ends on a
common conjunction/preposition.

Run from repo root:
    python3 lds_pipeline/repair_truncated_verses.py [--dry-run] [--books genesis exodus ...]
"""

import argparse
import html
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parent.parent
CHAPTERS = REPO / "library" / "chapters"
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


def load_catalog() -> dict:
    catalog = json.loads(VERSE_CATALOG.read_text(encoding="utf-8"))
    out: dict = {}
    for row in catalog:
        slug = f"{slugify_book(str(row['book']))}_{int(row['chapter'])}"
        if slug not in out:
            out[slug] = {}
        out[slug][str(int(row["verse"]))] = str(row["text"])
    return out


def is_truncated(text_cmp: str, canon: str) -> bool:
    """Return True if text_cmp appears to be a truncated prefix of canon."""
    if not canon or not text_cmp:
        return False
    canonical_prefix = canon.startswith(text_cmp[: max(12, min(len(text_cmp), 80))])
    trailing_fragment = bool(re.search(r"\b(and|to|that|of|from|shall|should|know)$", text_cmp.lower()))
    short_ratio = len(text_cmp) / max(len(canon), 1) < 0.8
    return canonical_prefix and (short_ratio or trailing_fragment)


def _he(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def normalise_scores(word_data: dict) -> dict:
    if not word_data:
        return {}
    scores = [v.get("score", 0) for v in word_data.values() if isinstance(v, dict)]
    mx = max(scores) if scores else 0
    if mx == 0:
        return {k: 0.0 for k in word_data}
    return {k: round(v.get("score", 0) / mx, 3) for k, v in word_data.items() if isinstance(v, dict)}


def find_spans(plain: str, word_data: dict, norm: dict) -> list:
    spans = []
    used: list = []
    for st, ns in sorted(norm.items(), key=lambda x: -x[1]):
        entry = word_data.get(st)
        if not entry or not isinstance(entry, dict):
            continue
        forms = entry.get("forms", [st])
        inflections = [st, st + "s", st + "ed", st + "ing", st + "ly",
                       st + "ness", st + "ful", st + "ion", st + "er", st + "est"]
        forms_set = set(f.lower() for f in forms)
        candidates = forms + [f for f in inflections if f not in forms_set]
        for cand in candidates:
            if len(cand) < 2:
                continue
            for m in re.finditer(r"\b" + re.escape(cand) + r"\b", plain, re.IGNORECASE):
                s, e = m.start(), m.end()
                if any(a < e and s < b for a, b in used):
                    continue
                spans.append((s, e, st, ns))
                used.append((s, e))
    return sorted(spans, key=lambda x: x[0])


def annotate_text(plain: str, vnum: int, word_data: dict) -> str:
    """Annotate verse text with .w spans."""
    if not word_data:
        return _he(plain)
    norm = normalise_scores(word_data)
    if not norm:
        return _he(plain)
    spans = find_spans(plain, word_data, norm)
    if not spans:
        return _he(plain)
    out = []
    pos = 0
    for (s, e, st, ns) in spans:
        if s < pos:
            continue
        out.append(_he(plain[pos:s]))
        out.append(
            f'<span class="w" data-st="{st}" data-v="{vnum}" style="--ws:{ns}">'
            f"{_he(plain[s:e])}"
            f"</span>"
        )
        pos = e
    out.append(_he(plain[pos:]))
    return "".join(out)


def repair_chapter(chapter_path: Path, catalog_chapter: dict, dry_run: bool) -> dict:
    """Repair truncated verses in one chapter HTML file."""
    slug = chapter_path.stem
    html_text = chapter_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    words_path = chapter_path.with_name(f"{slug}_words.json")
    words_data: dict = {}
    if words_path.exists():
        try:
            raw = json.loads(words_path.read_text(encoding="utf-8"))
            # Scripture chapter format may be flat {vnum: {stem:...}} or wrapped {"v": {...}}
            if "v" in raw:
                words_data = raw["v"]
            else:
                words_data = raw
        except Exception:
            pass

    repaired = 0
    changed = False

    for verse_div in soup.select("div.verse[id]"):
        verse_id = verse_div.get("id", "")
        if not verse_id.startswith("v") or not verse_id[1:].isdigit():
            continue
        vnum = verse_id[1:]

        canon_raw = catalog_chapter.get(vnum, "")
        if not canon_raw:
            continue
        canon = canonicalize(canon_raw)

        verse_text_span = verse_div.select_one(".verse-text")
        if verse_text_span is None:
            continue

        current_text = canonicalize(normalize_text(verse_text_span.get_text(" ", strip=True)))
        if not is_truncated(current_text, canon):
            continue

        # Repair: re-annotate from canonical text
        vdata = words_data.get(str(int(vnum)), {})
        # Use the canonical text (original verse text) as the plain input
        plain = canon_raw  # use the raw catalog text (not canonicalized) to preserve spacing
        new_inner = annotate_text(plain, int(vnum), vdata)

        # Replace verse-text span content
        new_span_html = f'<span class="verse-text">{new_inner}</span>'
        new_span = BeautifulSoup(new_span_html, "html.parser").find("span", class_="verse-text")
        verse_text_span.replace_with(new_span)
        repaired += 1
        changed = True

    new_html = str(soup)
    if not dry_run and changed:
        chapter_path.write_text(new_html, encoding="utf-8")

    return {"slug": slug, "repaired": repaired, "changed": changed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--books", nargs="+", help="Limit to specific book slugs")
    args = parser.parse_args()

    print("Loading verse catalog...")
    catalog = load_catalog()

    files = sorted(
        f for f in CHAPTERS.glob("*.html")
        if not any(s in f.name for s in ("_notes", "_words", "_graph"))
    )

    if args.books:
        files = [
            f for f in files
            if any(f.stem.startswith(b.lower().replace(" ", "_")) for b in args.books)
        ]

    print(f"Scanning {len(files)} chapter files...")
    if args.dry_run:
        print("  (dry run — no files will be written)")

    total_repaired = 0
    total_changed = 0
    errors = 0

    for i, path in enumerate(files):
        slug = path.stem
        chapter_catalog = catalog.get(slug, {})
        if not chapter_catalog:
            continue
        try:
            result = repair_chapter(path, chapter_catalog, args.dry_run)
            if result["repaired"]:
                total_repaired += result["repaired"]
                if result["changed"]:
                    total_changed += 1
                if not args.dry_run or result["repaired"] > 5:
                    print(f"  {slug}: repaired {result['repaired']} verses")
        except Exception as e:
            print(f"  ERROR {path.name}: {e}")
            errors += 1

        if (i + 1) % 200 == 0:
            print(f"  ... {i + 1}/{len(files)} chapters scanned")

    print(f"\nDone. {total_repaired} verses repaired across {total_changed} chapters.")
    if errors:
        print(f"  Errors: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
