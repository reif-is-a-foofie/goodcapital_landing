#!/usr/bin/env python3
"""
Source Worker — continuously downloads and caches all source corpora.

Run in a separate terminal:
  python3 source_worker.py
  python3 transformer_worker.py

Checks every source, downloads what's missing, sleeps, repeats.
Safe to kill and restart anytime — all downloads are idempotent.
Logs to cache/source_worker.log.

Sources managed:
  - Journal of Discourses (26 vols, jod.mrm.org)
  - Project Gutenberg texts (Enoch, Jubilees, Gilgamesh, Parley Pratt, etc.)
  - Church Fathers (ANF via archive.org)
  - General Conference talks (churchofjesuschrist.org study API)
  - Josephus Antiquities (Gutenberg)
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache")
LOG_FILE  = CACHE_DIR / "source_worker.log"

SLEEP_BETWEEN_VOLS  = 0.3   # seconds between requests within a source
SLEEP_BETWEEN_RUNS  = 3600  # seconds between full-sweep cycles (1 hour)


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ── Journal of Discourses (jod.mrm.org) ──────────────────────────────────────

def sync_jd() -> None:
    """Download any missing JD volumes."""
    from sources.journal_discourses_mrm import download_volume, CACHE_DIR as JD_CACHE
    missing = []
    for vol in range(1, 27):
        f = JD_CACHE / f"vol_{vol:02d}.txt"
        if not f.exists() or f.stat().st_size < 1000:
            missing.append(vol)

    if not missing:
        log("JD: all 26 volumes cached ✓")
        return

    log(f"JD: downloading {len(missing)} missing volumes: {missing}")
    for vol in missing:
        try:
            download_volume(vol)
            time.sleep(SLEEP_BETWEEN_VOLS)
        except Exception as e:
            log(f"JD Vol {vol}: ERROR — {e}")


# ── Gutenberg plain-text sources ──────────────────────────────────────────────

GUTENBERG_SOURCES = {
    # Ancient texts
    "book_of_enoch":    ("https://www.gutenberg.org/cache/epub/77935/pg77935.txt",   "cache/ancient_myths/book_of_enoch.txt"),
    "gilgamesh":        ("https://www.gutenberg.org/cache/epub/18897/pg18897.txt",   "cache/ancient_myths/gilgamesh.txt"),
    "enuma_elish":      ("https://www.gutenberg.org/ebooks/9914.txt.utf-8",          "cache/ancient_myths/enuma_elish.txt"),
    "josephus":         ("https://www.gutenberg.org/files/2848/2848-0.txt",          "cache/ancient_myths/josephus_antiquities.txt"),
    # LDS historical
    "parley_pratt":     ("https://www.gutenberg.org/files/44896/44896-0.txt",        "cache/gutenberg_lds/parley_pratt.txt"),
    "lucy_mack_smith":  ("https://www.gutenberg.org/files/45619/45619-0.txt",        "cache/gutenberg_lds/lucy_mack_smith.txt"),
    "brigham_young":    ("https://www.gutenberg.org/cache/epub/74447/pg74447.txt",   "cache/gutenberg_lds/brigham_young_discourses.txt"),
    "william_clayton":  ("https://www.gutenberg.org/files/45051/45051-0.txt",        "cache/gutenberg_lds/william_clayton.txt"),
    # Church Fathers (ANF series via Gutenberg — individual volumes)
    "anf_vol1":         ("https://www.gutenberg.org/cache/epub/23209/pg23209.txt",   "cache/church_fathers/anf_vol1.txt"),   # Apostolic Fathers, Justin, Irenaeus
    "anf_vol2":         ("https://www.gutenberg.org/cache/epub/23985/pg23985.txt",   "cache/church_fathers/anf_vol2.txt"),   # Hermas, Tatian, Athenagoras, Theophilus, Clement
    "anf_vol3":         ("https://www.gutenberg.org/cache/epub/26351/pg26351.txt",   "cache/church_fathers/anf_vol3.txt"),   # Tertullian
    "anf_vol4":         ("https://www.gutenberg.org/cache/epub/28381/pg28381.txt",   "cache/church_fathers/anf_vol4.txt"),   # Tertullian cont., Minucius Felix, Commodian, Origen
    "anf_vol5":         ("https://www.gutenberg.org/cache/epub/28853/pg28853.txt",   "cache/church_fathers/anf_vol5.txt"),   # Hippolytus, Cyprian, Caius, Novatian, Appendix
    "anf_vol6":         ("https://www.gutenberg.org/cache/epub/32468/pg32468.txt",   "cache/church_fathers/anf_vol6.txt"),   # Gregory Thaumaturgus, Dionysius, Julius Africanus, Anatolius, Methodius, Arnobius
}


def sync_clean_ancient_texts() -> None:
    """Refresh cache files that now have better clean-source fetchers than raw OCR."""
    try:
        from sources import ancient_myths
    except Exception as e:
        log(f"Clean ancient texts: import ERROR — {e}")
        return

    targets = ["book_of_jubilees", "testament_twelve_patriarchs"]
    refreshed = 0
    for key in targets:
        cache = ancient_myths._cache_path(key)
        dirty = True
        if cache.exists() and cache.stat().st_size > 1000:
            dirty = not ancient_myths._is_clean_cache(key, cache.read_text(encoding="utf-8", errors="replace"))
        if not dirty:
            continue
        try:
            text = ancient_myths.download_text(key)
            if text:
                refreshed += 1
                log(f"  clean {key}: {len(text):,} chars")
        except Exception as e:
            log(f"  clean {key}: ERROR — {e}")
        time.sleep(SLEEP_BETWEEN_VOLS)
    if refreshed == 0:
        log("Clean ancient texts: caches already clean ✓")


def sync_gutenberg() -> None:
    """Download any missing Gutenberg texts."""
    missing = []
    for key, (url, rel_path) in GUTENBERG_SOURCES.items():
        dest = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline") / rel_path
        if not dest.exists() or dest.stat().st_size < 5000:
            missing.append((key, url, dest))

    if not missing:
        log("Gutenberg: all texts cached ✓")
        return

    log(f"Gutenberg: downloading {len(missing)} missing texts")
    for key, url, dest in missing:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = fetch(url, timeout=60)
            dest.write_bytes(data)
            log(f"  {key}: {len(data):,} bytes → {dest.name}")
        except Exception as e:
            log(f"  {key}: ERROR — {e}")
        time.sleep(SLEEP_BETWEEN_VOLS)


# ── General Conference ────────────────────────────────────────────────────────

GC_CACHE = CACHE_DIR / "general_conference"
GC_INDEX_FILE = GC_CACHE / "talk_index.json"
GC_CONTENT_API = "https://www.churchofjesuschrist.org/study/api/v3/language-pages/type/content?lang=eng&uri="
GC_YEAR_RANGE = range(1971, 2026)
GC_SESSIONS = ["04", "10"]  # April and October


def fetch_gc_session_index(year: int, session: str) -> list[dict]:
    """Fetch list of talk URIs for a GC session from the HTML body."""
    uri = f"/general-conference/{year}/{session}"
    url = GC_CONTENT_API + urllib.request.quote(uri, safe="")
    try:
        data = json.loads(fetch(url, timeout=15))
        body = data.get("content", {}).get("body", "")
        # Talk links sit inside <li data-content-type="general-conference-talk">
        hrefs = re.findall(
            r'data-content-type="general-conference-talk">\s*<a href="([^"]+)"', body
        )
        talks = []
        for href in hrefs:
            # href is like /study/general-conference/2024/04/11oaks?lang=eng
            # strip /study prefix and query string to get the canonical URI
            clean = re.sub(r'\?.*$', '', href.replace('/study', ''))
            # Extract speaker slug for title placeholder
            slug = clean.rstrip('/').split('/')[-1]
            talks.append({
                "year": year, "session": session,
                "uri": clean,
                "slug": slug,
            })
        return talks
    except Exception:
        return []


def fetch_gc_talk_text(uri: str) -> str:
    """Fetch full text of a talk — strips all HTML tags from body."""
    url = GC_CONTENT_API + urllib.request.quote(uri, safe="")
    try:
        data = json.loads(fetch(url, timeout=20))
        body = data.get("content", {}).get("body", "")
        # Extract title and author from meta if present
        title = data.get("meta", {}).get("title", "")
        # Strip HTML, collapse whitespace
        text = re.sub(r'<[^>]+>', ' ', body)
        text = re.sub(r'\s+', ' ', text).strip()
        if title:
            text = title + "\n\n" + text
        return text
    except Exception:
        return ""


def parse_gc_cached_metadata(text: str) -> dict:
    text = str(text or "").strip()
    if not text:
        return {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {}
    title = lines[0]
    body = " ".join(lines[1:4])
    speaker = ""
    match = re.search(r'\bBy\s+(.+?)(?=\s+Of the\b|\s{2,}|$)', body, re.I)
    if match:
        speaker = re.sub(r'\s+', ' ', match.group(1)).strip(' ,')
    return {
        "title": title,
        "speaker": speaker,
    }


def enrich_gc_talk_metadata(talk: dict, text: str) -> bool:
    meta = parse_gc_cached_metadata(text)
    changed = False
    for key in ("title", "speaker"):
        value = meta.get(key, "").strip()
        if value and talk.get(key) != value:
            talk[key] = value
            changed = True
    return changed


def sync_gc() -> None:
    """
    Build or extend the General Conference talk index and download talk text.
    Only downloads talks not already cached.
    """
    GC_CACHE.mkdir(parents=True, exist_ok=True)

    # Load existing index
    if GC_INDEX_FILE.exists():
        index = json.loads(GC_INDEX_FILE.read_text(encoding="utf-8"))
    else:
        index = {}

    new_talks = 0
    meta_updates = 0
    for year in GC_YEAR_RANGE:
        for session in GC_SESSIONS:
            sess_key = f"{year}-{session}"
            if sess_key in index:
                continue  # already fetched

            talks = fetch_gc_session_index(year, session)
            if not talks:
                index[sess_key] = []
                continue

            index[sess_key] = talks
            log(f"  GC {sess_key}: {len(talks)} talks found")
            time.sleep(0.2)

        if year % 10 == 0:
            GC_INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # Download missing talk texts
    all_talks = [t for talks in index.values() for t in talks]
    log(f"GC: {len(all_talks):,} talks indexed across {len(index)} sessions")

    for talk in all_talks:
        uri = talk.get("uri", "")
        if not uri:
            continue
        safe_key = re.sub(r'[^\w]', '_', uri.strip("/"))
        dest = GC_CACHE / f"{safe_key}.txt"
        text = ""
        if dest.exists() and dest.stat().st_size > 100:
            text = dest.read_text(encoding="utf-8")
        else:
            text = fetch_gc_talk_text(uri)
            if text:
                dest.write_text(text, encoding="utf-8")
                new_talks += 1
        if text and enrich_gc_talk_metadata(talk, text):
            meta_updates += 1
        time.sleep(0.15)

    GC_INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"GC: {new_talks} new talk texts downloaded")
    if meta_updates:
        log(f"GC: enriched metadata for {meta_updates} talks")


# ── History of Church (B.H. Roberts) ─────────────────────────────────────────

HOC_CACHE = CACHE_DIR / "hoc"
HOC_SOURCES = {
    "vol1": "https://www.gutenberg.org/files/47091/47091-0.txt",
    "vol2": "https://www.gutenberg.org/files/47745/47745-0.txt",
    "vol3": "https://www.gutenberg.org/files/48080/48080-0.txt",
    "vol4": "https://www.gutenberg.org/files/48289/48289-0.txt",
    "vol5": "https://www.gutenberg.org/files/48290/48290-0.txt",
    "vol6": "https://www.gutenberg.org/files/48419/48419-0.txt",
    "vol7": "https://archive.org/download/HistoryOfTheChurchhcVolumes1-7original1902EditionPdf/HistoryOfTheChurchhcVolumes1-7original1902EditionPdf_djvu.txt",
}


def sync_hoc() -> None:
    """Download History of the Church volumes."""
    HOC_CACHE.mkdir(parents=True, exist_ok=True)
    missing = []
    for key, url in HOC_SOURCES.items():
        dest = HOC_CACHE / f"{key}.txt"
        if not dest.exists() or dest.stat().st_size < 5000:
            missing.append((key, url, dest))

    if not missing:
        log("HoC: all 7 volumes cached ✓")
        return

    log(f"HoC: downloading {len(missing)} missing volumes")
    for key, url, dest in missing:
        try:
            data = fetch(url, timeout=60)
            dest.write_bytes(data)
            log(f"  HoC {key}: {len(data):,} bytes")
        except Exception as e:
            log(f"  HoC {key}: ERROR — {e}")
        time.sleep(0.5)


# ── Joseph Smith Papers ───────────────────────────────────────────────────────

JSP_CACHE = CACHE_DIR / "joseph_smith_papers"
JSP_BASE  = "https://www.josephsmithpapers.org/paper-summary"

JSP_DOCUMENTS = {
    "journal_1832_1834":         "journal-1832-1834",
    "journal_1835_1836":         "journal-1835-1836",
    "journal_1837":              "journal-march-september-1838",
    "journal_1841_1842":         "journal-december-1841-december-1842",
    "history_vol_a1":            "history-1838-1856-volume-a-1-23-december-1805-30-august-1834",
    "king_follett_discourse":    "discourse-7-april-1844-as-reported-by-times-and-seasons",
    "lectures_on_faith":         "doctrine-and-covenants-1835",
    "first_vision_account_1832": "history-circa-summer-1832",
    "letter_liberty_jail":       "letter-to-the-church-and-edward-partridge-20-march-1839",
}


def _fetch_jsp_page_text(slug: str, page: int) -> tuple[str, int]:
    """Fetch one page of a JSP document. Returns (text, total_pages)."""
    url = f"{JSP_BASE}/{slug}/{page}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html, re.DOTALL)
        if not m:
            return "", 0
        data = json.loads(m.group(1))
        props = data.get("props", {}).get("pageProps", {})
        summary = props.get("summary", {})
        total = int(summary.get("numberOfPages", 0) or 0)
        clear = summary.get("clearText", "")
        text  = re.sub(r"<[^>]+>", " ", clear)
        # Strip JSP hyperlink-anchor remnants (plain text from nav elements)
        text  = re.sub(r"\s*View Glossary\s*", " ", text)
        text  = re.sub(r"\s*View Full Bio\s*", " ", text)
        text  = re.sub(r"\[\s*\d+\s+lines\s+blank\s*\]", " ", text)
        text  = re.sub(r"Note [A-Z] see page \d+", " ", text)
        text  = re.sub(r"\s+", " ", text).strip()
        return text, total
    except Exception:
        return "", 0


def sync_jsp() -> None:
    """Download Joseph Smith Papers documents page by page."""
    JSP_CACHE.mkdir(parents=True, exist_ok=True)
    new_docs = 0

    for key, slug in JSP_DOCUMENTS.items():
        dest = JSP_CACHE / f"{key}.txt"
        if dest.exists() and dest.stat().st_size > 2000:
            continue

        log(f"  JSP: fetching {key}")
        pages = []
        page1_text, total = _fetch_jsp_page_text(slug, 1)
        if not page1_text or total == 0:
            log(f"  JSP {key}: not found or empty")
            continue

        pages.append(page1_text)
        for p in range(2, min(total + 1, 300)):
            text, _ = _fetch_jsp_page_text(slug, p)
            if text:
                pages.append(text)
            time.sleep(0.2)

        combined = "\n\n".join(pages)
        dest.write_text(combined, encoding="utf-8")
        log(f"  JSP {key}: {len(pages)} pages, {len(combined):,} chars")
        new_docs += 1
        time.sleep(0.5)

    if new_docs == 0:
        log("JSP: all documents cached ✓")
    else:
        log(f"JSP: {new_docs} documents downloaded")


# ── Main loop ─────────────────────────────────────────────────────────────────

def count_cached_passages() -> int:
    """Count total source passages currently on disk (proxy for 'did something change')."""
    total = 0
    jd_dir = CACHE_DIR / "jd"
    if jd_dir.exists():
        for f in jd_dir.glob("vol_*.txt"):
            total += f.stat().st_size // 600   # rough paragraph estimate
    for subdir in ["gutenberg_lds", "church_fathers", "ancient_myths", "hoc"]:
        d = CACHE_DIR / subdir
        if d.exists():
            for f in d.glob("*.txt"):
                total += f.stat().st_size // 600
    gc_dir = CACHE_DIR / "general_conference"
    if gc_dir.exists():
        total += sum(1 for f in gc_dir.glob("*.txt"))
    return total


def run_correlations() -> None:
    """Trigger dense embedding correlation rebuild."""
    import subprocess
    log("--- Running sentence-transformer correlations ---")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "correlate_embeddings.py")],
        capture_output=True, text=True, cwd=str(Path(__file__).parent)
    )
    if result.returncode == 0:
        log("Correlations complete ✓")
        for line in result.stdout.strip().splitlines()[-5:]:
            log(f"  {line}")
    else:
        log(f"Correlation ERROR: {result.stderr[-500:]}")


def run_once(correlate: bool = True) -> None:
    log("=" * 60)
    log("Source worker sweep started")

    before = count_cached_passages()

    log("--- Journal of Discourses ---")
    sync_jd()

    log("--- Gutenberg texts ---")
    sync_gutenberg()

    log("--- Clean ancient text transcriptions ---")
    sync_clean_ancient_texts()

    log("--- History of the Church ---")
    sync_hoc()

    log("--- Joseph Smith Papers ---")
    sync_jsp()

    log("--- General Conference ---")
    sync_gc()

    after = count_cached_passages()
    log(f"Sweep complete  (passages: {before:,} → {after:,})")

    if correlate and after != before:
        log(f"New content detected ({after - before:,} passage units added), triggering correlations")
        run_correlations()
    elif correlate:
        log("No new content — skipping correlation re-run")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="LDS source corpus downloader")
    parser.add_argument("--once", action="store_true", help="Run one sweep then exit")
    parser.add_argument("--no-correlate", action="store_true",
                        help="Skip correlation step even when new content found")
    parser.add_argument("--source", choices=["jd", "gutenberg", "gc", "hoc", "jsp", "transformer"],
                        help="Run only a specific source")
    args = parser.parse_args()

    if args.source:
        {
            "jd": sync_jd,
            "gutenberg": sync_gutenberg,
            "gc": sync_gc,
            "hoc": sync_hoc,
            "jsp": sync_jsp,
            "transformer": run_correlations,
        }[args.source]()
        return

    correlate = not args.no_correlate

    if args.once:
        run_once(correlate=correlate)
        return

    # Continuous loop
    while True:
        try:
            run_once(correlate=correlate)
        except KeyboardInterrupt:
            log("Interrupted by user")
            sys.exit(0)
        except Exception as e:
            log(f"ERROR in sweep: {e}")

        log(f"Sleeping {SLEEP_BETWEEN_RUNS}s until next sweep...")
        time.sleep(SLEEP_BETWEEN_RUNS)


if __name__ == "__main__":
    main()
