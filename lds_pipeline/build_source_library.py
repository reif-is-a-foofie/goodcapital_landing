#!/usr/bin/env python3
"""
Build a reader-friendly historical/source corpus from cached texts.

Outputs:
  library/sources/<group>/<slug>.html
  library/source_toc.json

The generated pages use the same reader stylesheet as the scripture reader,
but render each source as a clean article with paragraphs instead of verse
blocks. This is the foundation for exposing General Conference, Journal of
Discourses, and the rest of the source corpus inside the left-pane library.

Usage:
  python3 lds_pipeline/build_source_library.py
"""

import json
import re
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "lds_pipeline" / "cache"
LIBRARY = REPO / "library"
OUT = LIBRARY / "sources"
TOC_OUT = LIBRARY / "source_toc.json"


SOURCE_GROUPS = [
    {"key": "general_conference", "label": "General Conference", "dir": CACHE / "general_conference"},
    {"key": "journal_of_discourses", "label": "Journal of Discourses", "dir": CACHE / "jd"},
    {"key": "history_of_church", "label": "History of the Church", "dir": CACHE / "hoc"},
    {"key": "joseph_smith_papers", "label": "Joseph Smith Papers", "dir": CACHE / "joseph_smith_papers"},
    {"key": "times_and_seasons", "label": "Times and Seasons", "dir": CACHE / "times_and_seasons"},
    {"key": "millennial_star", "label": "Millennial Star", "dir": CACHE / "millennial_star"},
    {"key": "pioneer_journals", "label": "Pioneer Journals", "dir": CACHE / "pioneer_journals"},
    {"key": "gutenberg_lds", "label": "Early LDS Writings", "dir": CACHE / "gutenberg_lds"},
    {"key": "church_fathers", "label": "Church Fathers", "dir": CACHE / "church_fathers"},
    {"key": "ancient_texts", "label": "Ancient Texts", "dir": CACHE / "ancient_myths"},
    {"key": "pseudepigrapha", "label": "Pseudepigrapha", "dir": CACHE / "pseudepigrapha"},
    {"key": "apocrypha", "label": "LXX Apocrypha", "dir": CACHE / "apocrypha"},
    {"key": "nag_hammadi", "label": "Nag Hammadi", "dir": CACHE / "nag_hammadi"},
    {"key": "dead_sea_scrolls", "label": "Dead Sea Scrolls", "dir": CACHE / "dead_sea_scrolls"},
    {"key": "bh_roberts", "label": "B.H. Roberts", "dir": CACHE / "bh_roberts"},
    {"key": "nibley", "label": "Nibley", "dir": CACHE / "nibley"},
    {"key": "nauvoo_theology", "label": "Nauvoo Theology", "dir": CACHE / "nauvoo_theology"},
    {"key": "jst", "label": "Joseph Smith Translation", "dir": CACHE / "jst"},
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def split_paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    paragraphs = []
    for chunk in chunks:
        chunk = re.sub(r"[ \t]+", " ", chunk).strip()
        if len(chunk) < 60:
            continue
        paragraphs.append(chunk)
    return paragraphs


def source_title(group_key: str, txt_path: Path, gc_meta: dict) -> str:
    if group_key == "general_conference":
        meta = gc_meta.get(txt_path.stem, {})
        speaker = meta.get("speaker", "").strip()
        title = meta.get("title", "").strip()
        year = str(meta.get("year", "")).strip()
        session = str(meta.get("session", "")).strip()
        parts = [p for p in [speaker, title] if p]
        if year:
            parts.append(year if not session else f"{year} {session}")
        return " — ".join(parts) if parts else txt_path.stem.replace("_", " ")
    if group_key == "journal_of_discourses":
        m = re.search(r"vol[_ ]?0*(\d+)", txt_path.stem, re.I)
        if m:
            return f"Journal of Discourses Vol. {int(m.group(1))}"
    if group_key == "history_of_church":
        m = re.search(r"vol[_ ]?0*(\d+)", txt_path.stem, re.I)
        if m:
            return f"History of the Church Vol. {int(m.group(1))}"
    return txt_path.stem.replace("_", " ").replace("-", " ").title()


def load_gc_meta() -> dict:
    out = {}
    index_path = CACHE / "general_conference" / "talk_index.json"
    if not index_path.exists():
        return out
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return out
    for talks in index.values():
        for t in talks:
            uri = t.get("uri", "")
            safe = re.sub(r"[^\w]", "_", uri.strip("/"))
            out[safe] = t
    return out


def render_source_page(group_label: str, title: str, paragraphs: list[str]) -> str:
    body = "\n".join(f'<p class="source-para">{escape_html(p)}</p>' for p in paragraphs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="../../style/main.css">
  <style>
    .source-doc {{
      max-width: 760px;
      margin: 0 auto;
      padding: 40px 32px 120px;
    }}
    .source-kicker {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: #9C7A4D;
      margin-bottom: 10px;
    }}
    .source-title {{
      font-family: 'EB Garamond', Georgia, serif;
      font-size: 34px;
      line-height: 1.08;
      margin: 0 0 20px;
      color: #26221d;
    }}
    .source-para {{
      font-size: 18px;
      line-height: 1.78;
      color: #2f2a24;
      margin: 0 0 18px;
    }}
  </style>
</head>
<body>
  <article class="source-doc">
    <div class="source-kicker">{escape_html(group_label)}</div>
    <h1 class="source-title">{escape_html(title)}</h1>
    {body}
  </article>
</body>
</html>
"""


def build_group(group: dict, gc_meta: dict) -> Optional[dict]:
    src_dir = group["dir"]
    if not src_dir.exists():
        return None

    files = sorted(
        p for p in src_dir.glob("*.txt")
        if p.name not in {"scripture_index.json", "talk_index.json"}
    )
    if not files:
        return None

    group_out = OUT / group["key"]
    group_out.mkdir(parents=True, exist_ok=True)
    docs = []

    for txt in files:
        try:
            raw = txt.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        paragraphs = split_paragraphs(raw)
        if not paragraphs:
            continue
        title = source_title(group["key"], txt, gc_meta)
        slug = slugify(txt.stem)
        html = render_source_page(group["label"], title, paragraphs[:300])
        out_path = group_out / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        docs.append({
            "id": f"{group['key']}:{slug}",
            "label": title,
            "href": f"sources/{group['key']}/{slug}.html",
            "paragraphs": len(paragraphs),
            "meta": f"{len(paragraphs)} paragraphs",
        })

    if not docs:
        return None

    return {
        "id": group["key"],
        "label": group["label"],
        "type": "collection",
        "items": docs,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gc_meta = load_gc_meta()
    toc = []
    built_docs = 0

    for group in SOURCE_GROUPS:
        built = build_group(group, gc_meta)
        if not built:
            continue
        toc.append(built)
        built_docs += len(built["items"])
        print(f"{group['label']}: {len(built['items'])} documents")

    TOC_OUT.write_text(json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {built_docs} source documents written → {OUT}")
    print(f"Source TOC → {TOC_OUT}")


if __name__ == "__main__":
    main()
