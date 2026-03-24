"""
Download LDS historical periodicals and pioneer journals from archive.org.

Sources:
  Times and Seasons (1839-1846)     — Nauvoo newspaper, Joseph Smith editor
  Millennial Star (1840-1859)       — UK mission periodical, Parley Pratt editor
  Wilford Woodruff Journals         — 31 years of daily journal entries
  Lucy Mack Smith History           — History of the Prophet Joseph Smith
  Juvenile Instructor (samples)     — Early doctrinal essays, 1866-1929

Writes plain .txt files to:
  cache/times_and_seasons/
  cache/millennial_star/
  cache/pioneer_journals/

Run:
  python3 sync_periodicals.py [--rebuild]
"""

import argparse
import re
import time
import urllib.request
from pathlib import Path

CACHE_DIR = Path("/Users/reify/lds_pipeline/cache")

ARCHIVE_BASE = "https://archive.org/download"

SOURCES = [
    {
        "dir":        "times_and_seasons",
        "identifier": "TimesAndSeasons18391846",
        "filename":   "Times_and_Seasons_1839-1846_djvu.txt",
        "label":      "Times and Seasons (1839-1846)",
        "out_name":   "times_and_seasons_1839_1846.txt",
    },
    {
        "dir":        "millennial_star",
        "identifier": "MillennialStar18401859",
        "filename":   "Millennial_Star_Part_1_1840-1859_djvu.txt",
        "label":      "Millennial Star (1840-1859)",
        "out_name":   "millennial_star_1840_1859.txt",
    },
    {
        "dir":        "pioneer_journals",
        "identifier": "wilfordwoodruff00unkngoog",
        "filename":   "wilfordwoodruff00unkngoog_djvu.txt",
        "label":      "Wilford Woodruff Journals",
        "out_name":   "wilford_woodruff_journals.txt",
    },
    {
        "dir":        "pioneer_journals",
        "identifier": "HistoryOfTheProphetJosephSmithByHisMotherLucyMackSmith",
        "filename":   "history_of_prophet_joseph_smith_Lucy_mack_smith_djvu.txt",
        "label":      "Lucy Mack Smith — History of Joseph Smith",
        "out_name":   "lucy_mack_smith_history.txt",
    },
]


def clean_djvu_text(text: str) -> str:
    """
    DjVu OCR text has page markers and line-break artifacts. Clean them.

    DjVu breaks at every printed line, so paragraphs appear as many
    single-newline-separated lines. We rejoin those, while preserving
    real paragraph breaks (double newlines).
    """
    # Page break form-feed → paragraph break
    text = re.sub(r'\x0c', '\n\n', text)
    # Remove standalone page number lines
    text = re.sub(r'(?m)^\s*\d{1,4}\s*$', '', text)
    # Remove lines that are just dashes/underscores (decorative rules)
    text = re.sub(r'(?m)^[\-_=]{3,}\s*$', '', text)
    # Collapse 3+ blank lines to double newline (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Join lines WITHIN each paragraph (DjVu breaks at every print line).
    # Work paragraph by paragraph so we never collapse real paragraph breaks.
    paragraphs = text.split('\n\n')
    joined = []
    for para in paragraphs:
        # Join end-of-line hyphenation: "diffi-\nculties" or "diffi- \nculties" → "difficulties"
        para = re.sub(r'-\s*\n\s*([a-z])', r'\1', para)
        # Join remaining single newlines with a space
        para = para.replace('\n', ' ')
        # Normalize internal whitespace
        para = re.sub(r'  +', ' ', para).strip()
        if para:
            joined.append(para)

    return '\n\n'.join(joined)


OCR_GARBAGE_RE = re.compile(r'[§©®†‡¶°½¼¾×÷]{2,}|(?:[^\x00-\x7F].*?){5,}')

def ocr_quality_ok(text: str) -> bool:
    """Return False if text has too many OCR artifacts to be useful."""
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii / max(len(text), 1) > 0.08:
        return False
    if OCR_GARBAGE_RE.search(text):
        return False
    return True


def fetch_archive_text(identifier: str, filename: str) -> str:
    url = f"{ARCHIVE_BASE}/{identifier}/{filename}"
    print(f"  Fetching {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return raw


def download_source(src: dict, rebuild: bool = False) -> None:
    out_dir = CACHE_DIR / src["dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / src["out_name"]

    if not rebuild and out_file.exists() and out_file.stat().st_size > 10_000:
        size_mb = out_file.stat().st_size / 1e6
        print(f"  {src['label']}: cached ({size_mb:.1f} MB)")
        return

    print(f"\n  {src['label']}: downloading...", flush=True)
    raw = fetch_archive_text(src["identifier"], src["filename"])
    cleaned = clean_djvu_text(raw)
    out_file.write_text(cleaned, encoding="utf-8")
    size_mb = out_file.stat().st_size / 1e6
    print(f"  {src['label']}: {size_mb:.1f} MB → {out_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    print("=== Downloading LDS Historical Periodicals & Pioneer Journals ===")
    for src in SOURCES:
        try:
            download_source(src, rebuild=args.rebuild)
            time.sleep(1)
        except Exception as e:
            print(f"  ERROR {src['label']}: {e}")

    print("\nDone.")
    print("Add these directories to correlate.py load_all_sources():")
    print("  cache/times_and_seasons/  → source_name='times_and_seasons'")
    print("  cache/millennial_star/    → source_name='millennial_star'")
    print("  cache/pioneer_journals/   → source_name='pioneer_journals'")


if __name__ == "__main__":
    main()
