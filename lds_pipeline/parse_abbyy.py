"""
Parse ABBYY FineReader XML from archive.org into column-correct plain text.

ABBYY XML has bounding-box coordinates for every text block, paragraph, and
character. This lets us reconstruct proper reading order for multi-column
newspapers by sorting blocks spatially rather than relying on the naive
DjVu text which reads across columns.

Reading-order algorithm:
  For each page:
    1. Collect all blockType="Text" blocks with their bounding boxes.
    2. Determine column bands by clustering block x-centers using the page width.
    3. Sort blocks: primary=column index (left→right), secondary=top position.
    4. Concatenate block texts with paragraph breaks between blocks.

Output:
  cache/times_and_seasons/times_and_seasons_abbyy.txt
  cache/millennial_star/millennial_star_abbyy.txt

Run:
  python3 parse_abbyy.py [--rebuild]
"""

import argparse
import gzip
import io
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache")

NS = "http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml"

SOURCES = [
    {
        "identifier": "TimesAndSeasons18391846",
        "filename":   "Times_and_Seasons_1839-1846_abbyy.gz",
        "out_dir":    CACHE_DIR / "times_and_seasons",
        "out_name":   "times_and_seasons_abbyy.txt",
        "label":      "Times and Seasons (1839-1846)",
    },
    {
        "identifier": "MillennialStar18401859",
        "filename":   "Millennial_Star_Part_1_1840-1859_abbyy.gz",
        "out_dir":    CACHE_DIR / "millennial_star",
        "out_name":   "millennial_star_abbyy.txt",
        "label":      "Millennial Star (1840-1859)",
    },
]


def download_gz(identifier: str, filename: str) -> Path:
    """Download gz to local cache, return path."""
    cache_path = CACHE_DIR / "abbyy_gz" / filename
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and cache_path.stat().st_size > 1_000_000:
        print(f"    Already cached: {cache_path}")
        return cache_path
    url = f"https://archive.org/download/{identifier}/{filename}"
    print(f"    Downloading {url} ...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    cache_path.write_bytes(data)
    print(f"    Saved {cache_path.stat().st_size / 1e6:.1f} MB")
    return cache_path


def block_text(block_el) -> str:
    """Extract plain text from an ABBYY block element."""
    parts = []
    for par in block_el.iter(f"{{{NS}}}par"):
        line_texts = []
        for line in par.iter(f"{{{NS}}}line"):
            chars = []
            for char_el in line.iter(f"{{{NS}}}charParams"):
                ch = char_el.text or ""
                if ch.strip() or (chars and chars[-1] != " "):
                    chars.append(ch)
            line_texts.append("".join(chars).strip())
        par_text = " ".join(t for t in line_texts if t)
        if par_text.strip():
            parts.append(par_text.strip())
    return "\n".join(parts)


def column_index(block_l: int, block_r: int, page_width: int, n_cols: int = 2) -> int:
    """Return 0-based column index based on block center x and page width."""
    center_x = (block_l + block_r) / 2
    col_width = page_width / n_cols
    return int(center_x // col_width)


def parse_page(page_el) -> str:
    """
    Parse one ABBYY page element into ordered plain text.
    Sorts text blocks by (column_index, top) for proper reading order.
    """
    page_width  = int(page_el.get("width",  "1"))
    page_height = int(page_el.get("height", "1"))

    blocks = []
    for block in page_el.iter(f"{{{NS}}}block"):
        if block.get("blockType") != "Text":
            continue
        l = int(block.get("l", "0"))
        t = int(block.get("t", "0"))
        r = int(block.get("r", "0"))
        b = int(block.get("b", "0"))
        text = block_text(block).strip()
        if len(text) < 20:
            continue
        col = column_index(l, r, page_width)
        blocks.append((col, t, text))

    blocks.sort(key=lambda x: (x[0], x[1]))
    return "\n\n".join(text for _, _, text in blocks)


def parse_abbyy_gz(gz_path: Path) -> str:
    """Stream-parse an ABBYY gzip XML file, return full text."""
    print(f"    Parsing {gz_path.name} ({gz_path.stat().st_size / 1e6:.0f} MB)...", flush=True)

    pages_text = []
    page_count = 0

    with gzip.open(str(gz_path), "rb") as f:
        # Use iterparse to avoid loading the entire XML tree
        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            if elem.tag == f"{{{NS}}}page":
                page_text = parse_page(elem)
                if page_text.strip():
                    pages_text.append(page_text)
                page_count += 1
                if page_count % 200 == 0:
                    print(f"    ... {page_count} pages", flush=True)
                elem.clear()  # free memory

    print(f"    Parsed {page_count} pages, {len(pages_text)} with text")
    return "\n\n\n".join(pages_text)


def clean_text(text: str) -> str:
    """Final cleanup pass after ABBYY extraction."""
    # Join hyphenated line-end words
    text = re.sub(r'-\s*\n\s*([a-z])', r'\1', text)
    # Normalize whitespace within lines
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def process_source(src: dict, rebuild: bool = False) -> None:
    out_dir  = src["out_dir"]
    out_file = out_dir / src["out_name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rebuild and out_file.exists() and out_file.stat().st_size > 100_000:
        print(f"  {src['label']}: cached ({out_file.stat().st_size / 1e6:.1f} MB)")
        return

    print(f"\n  {src['label']}:", flush=True)
    gz_path = download_gz(src["identifier"], src["filename"])
    text    = parse_abbyy_gz(gz_path)
    text    = clean_text(text)
    out_file.write_text(text, encoding="utf-8")
    size_mb = out_file.stat().st_size / 1e6
    print(f"  {src['label']}: {size_mb:.1f} MB → {out_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--source", choices=["ts", "ms"], help="Only process one source")
    args = parser.parse_args()

    sources = SOURCES
    if args.source == "ts":
        sources = [SOURCES[0]]
    elif args.source == "ms":
        sources = [SOURCES[1]]

    print("=== ABBYY Column-Aware OCR Parser ===")
    for src in sources:
        try:
            process_source(src, rebuild=args.rebuild)
        except Exception as e:
            print(f"  ERROR {src['label']}: {e}")
            import traceback; traceback.print_exc()

    print("\nDone. Update correlate.py to use *_abbyy.txt instead of DjVu files.")


if __name__ == "__main__":
    main()
