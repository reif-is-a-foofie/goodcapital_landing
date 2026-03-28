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


def preprocess_source_text(group_key: str, txt_path: Path, raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    stem = txt_path.stem

    if "*** START OF THE PROJECT GUTENBERG EBOOK" in text:
        text = text.split("*** START OF THE PROJECT GUTENBERG EBOOK", 1)[1]
        text = text.split("\n", 1)[1] if "\n" in text else text
    if "*** END OF THE PROJECT GUTENBERG EBOOK" in text:
        text = text.split("*** END OF THE PROJECT GUTENBERG EBOOK", 1)[0]

    if group_key == "ancient_texts":
        if stem == "book_of_enoch":
            hits = [m.start() for m in re.finditer(re.escape("The words of the blessing of Enoch"), text)]
            if hits:
                text = text[hits[-1]:]
        elif stem == "book_of_jubilees":
            matches = list(re.finditer(r"\bI\.\s+And it came to pass in the first year\b", text, re.I))
            if matches:
                text = text[matches[-1].start():]
            else:
                matches = list(re.finditer(r"\bCHAPTER\s+I\b", text, re.I))
                if matches:
                    text = text[matches[-1].start():]
            end_match = re.search(r"Herewith\s+is\s+completed\s+the\s+account\s+of\s+the\s+division\s+of\s+the\s+days\.", text, re.I)
            if end_match:
                text = text[:end_match.end()]
        elif stem == "josephus_antiquities":
            hits = [m.start() for m in re.finditer(re.escape("BOOK I."), text)]
            if len(hits) >= 2:
                text = text[hits[1]:]
        elif stem == "gilgamesh":
            matches = list(re.finditer(r"\bNow the harlot urges Enkidu\b", text, re.I))
            if matches:
                text = text[matches[0].start():]
        elif stem == "testament_twelve_patriarchs":
            matches = list(re.finditer(r"\bTHE\s+TESTAMENT\s+OF\s+REUBEN\b", text, re.I))
            if matches:
                text = text[matches[-1].start():]
            else:
                matches = list(re.finditer(r"\b1\.\s+The\s+copy\s+of\s+the\s+Testament\s+of\s+Reuben\b", text, re.I))
                if matches:
                    text = text[matches[-1].start():]
            end_match = re.search(r"Printed\s+in\s+G\w+\s+B\w+\s+b[vy]\s+R\w+\s+Clay", text, re.I)
            if end_match:
                text = text[:end_match.start()]
        text = text.lstrip("\ufeff").strip()

    return text


MONTH_ALIASES = {
    "jan": "January",
    "january": "January",
    "feb": "February",
    "february": "February",
    "mar": "March",
    "march": "March",
    "apr": "April",
    "april": "April",
    "may": "May",
    "jun": "June",
    "june": "June",
    "jul": "July",
    "july": "July",
    "aug": "August",
    "august": "August",
    "sep": "September",
    "sept": "September",
    "september": "September",
    "oct": "October",
    "october": "October",
    "nov": "November",
    "november": "November",
    "dec": "December",
    "december": "December",
}

MONTH_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(18[3-5][0-9]|1860)\b")


def roman_to_int(token: str) -> Optional[int]:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    token = re.sub(r"[^IVXLC]", "", token.upper())
    if not token:
        return None
    total = 0
    prev = 0
    for ch in reversed(token):
        val = values.get(ch)
        if not val:
            return None
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total or None


def parse_numeric_token(token: str) -> Optional[int]:
    cleaned = token.strip()
    if not cleaned:
        return None
    digits = re.sub(r"[^0-9]", "", cleaned)
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    if re.fullmatch(r"[ivxlc]+", cleaned, re.I):
        roman = roman_to_int(cleaned)
        if roman is not None:
            return roman
    simple = cleaned.lower().replace("l", "1").replace("i", "1").replace("o", "0")
    if simple.isdigit():
        try:
            return int(simple)
        except ValueError:
            return None
    return None


def normalize_month(text: str) -> Optional[str]:
    m = MONTH_RE.search(text)
    if not m:
        return None
    return MONTH_ALIASES.get(m.group(1).lower().rstrip("."), m.group(1).title())


def volume_number(text: str) -> Optional[int]:
    m = re.search(r"\b(?:Vol|Vot|Vou|Voi|Yol|VoL|Volume)\.?\s*([ivxlc0-9]{1,5})\b", text, re.I)
    if not m:
        return None
    token = m.group(1)
    value = parse_numeric_token(token)
    if value is None:
        return None
    if value > 26 and re.fullmatch(r"[xil]+", token, re.I):
        corrected = parse_numeric_token(token.lower().replace("l", "i"))
        if corrected is not None:
            value = corrected
    return value


def issue_number(text: str) -> Optional[int]:
    m = re.search(r"\bNo[\.,;:\- ]*([a-z0-9ivxlc]{1,5})\b", text, re.I)
    if not m:
        return None
    return parse_numeric_token(m.group(1))


def extract_issue_marker(group_key: str, para: str) -> Optional[dict]:
    sample = " ".join(para.split())[:320]
    if len(sample) < 24:
        return None
    year_match = YEAR_RE.search(sample)
    if not year_match:
        return None
    year = int(year_match.group(1))
    volume = volume_number(sample)
    number = issue_number(sample)
    month = normalize_month(sample)
    if volume is None or number is None:
        return None
    if not month:
        return None

    if group_key == "times_and_seasons":
        if "whole no" not in sample.lower() and "illinois" not in sample.lower():
            return None
    elif group_key == "millennial_star":
        lower = sample.lower()
        if "price" not in lower and "saturday" not in lower and "published" not in lower:
            return None

    slug_parts = [str(year), f"vol_{volume:02d}", f"no_{number:02d}"]
    if month:
        slug_parts.insert(1, slugify(month))
    title_bits = [f"Vol. {volume}", f"No. {number}"]
    if month:
        title = f"{month} {year} · " + " · ".join(title_bits)
    else:
        title = f"{year} · " + " · ".join(title_bits)
    return {
        "year": year,
        "month": month,
        "volume": volume,
        "number": number,
        "slug": "_".join(slug_parts),
        "title": title,
    }


def split_large_document(group_key: str, title: str, slug: str, paragraphs: list[str]) -> list[dict]:
    if group_key not in {"millennial_star", "times_and_seasons"}:
        return [{"slug": slug, "title": title, "paragraphs": paragraphs}]

    markers = []
    for idx, para in enumerate(paragraphs):
        marker = extract_issue_marker(group_key, para)
        if marker:
            markers.append((idx, marker))

    if len(markers) < 2:
        return [{"slug": slug, "title": title, "paragraphs": paragraphs}]

    chunks = []
    used_slugs = set()
    for pos, (start, marker) in enumerate(markers):
        end = markers[pos + 1][0] if pos + 1 < len(markers) else len(paragraphs)
        chunk_paras = paragraphs[start:end]
        if len(chunk_paras) < 8:
            continue
        base_slug = f"{slug}_{marker['slug']}"
        chunk_slug = base_slug
        bump = 2
        while chunk_slug in used_slugs:
            chunk_slug = f"{base_slug}_{bump:02d}"
            bump += 1
        used_slugs.add(chunk_slug)
        chunks.append({
            "slug": chunk_slug,
            "title": f"{title} — {marker['title']}",
            "paragraphs": chunk_paras,
        })

    usable = [chunk for chunk in chunks if len(chunk["paragraphs"]) >= 8]
    return usable or [{"slug": slug, "title": title, "paragraphs": paragraphs}]


def source_title(group_key: str, txt_path: Path, gc_meta: dict) -> str:
    if group_key == "general_conference":
        meta = gc_meta.get(txt_path.stem, {})
        title = meta.get("title", "").strip()
        return title or txt_path.stem.replace("_", " ")
    if group_key == "journal_of_discourses":
        m = re.search(r"vol[_ ]?0*(\d+)", txt_path.stem, re.I)
        if m:
            return f"Journal of Discourses Vol. {int(m.group(1))}"
    if group_key == "history_of_church":
        m = re.search(r"vol[_ ]?0*(\d+)", txt_path.stem, re.I)
        if m:
            return f"History of the Church Vol. {int(m.group(1))}"
    if group_key == "times_and_seasons":
        return "Times and Seasons"
    if group_key == "millennial_star":
        return "Millennial Star"
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


def gc_session_label(meta: dict) -> str:
    year = str(meta.get("year", "")).strip()
    session = str(meta.get("session", "")).strip()
    if not year:
        return ""
    if session == "04":
        return f"April {year}"
    if session == "10":
        return f"October {year}"
    return f"{year} {session}".strip()


def source_meta(group_key: str, txt_path: Path, gc_meta: dict, paragraph_count: int) -> str:
    if group_key == "general_conference":
        meta = gc_meta.get(txt_path.stem, {})
        parts = [meta.get("speaker", "").strip(), gc_session_label(meta)]
        return " · ".join(part for part in parts if part)
    return f"{paragraph_count} paragraphs"


def render_source_page(group_label: str, title: str, paragraphs: list[str], subtitle: str = "") -> str:
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
    .source-subtitle {{
      font-size: 14px;
      line-height: 1.4;
      color: #7a7063;
      margin: -8px 0 20px;
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
    {'<div class="source-subtitle">' + escape_html(subtitle) + '</div>' if subtitle else ''}
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
    for stale in group_out.glob("*.html"):
        stale.unlink()
    docs = []

    for txt in files:
        try:
            raw = txt.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        raw = preprocess_source_text(group["key"], txt, raw)
        paragraphs = split_paragraphs(raw)
        if not paragraphs:
            continue
        title = source_title(group["key"], txt, gc_meta)
        meta = source_meta(group["key"], txt, gc_meta, len(paragraphs))
        slug = slugify(txt.stem)
        for chunk in split_large_document(group["key"], title, slug, paragraphs):
            html = render_source_page(group["label"], chunk["title"], chunk["paragraphs"], meta)
            out_path = group_out / f"{chunk['slug']}.html"
            out_path.write_text(html, encoding="utf-8")
            docs.append({
                "id": f"{group['key']}:{chunk['slug']}",
                "label": chunk["title"],
                "href": f"sources/{group['key']}/{chunk['slug']}.html",
                "paragraphs": len(chunk["paragraphs"]),
                "meta": meta if group["key"] == "general_conference" else f"{len(chunk['paragraphs'])} paragraphs",
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
