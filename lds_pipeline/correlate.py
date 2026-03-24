"""
Semantic correlation engine.

Uses TF-IDF + cosine similarity to match verses against source passages.
Fast (~60 seconds for 40K verses × 100K passages), no GPU required,
works well for specialized biblical/theological vocabulary.

Writes per-verse top-N matches to:
  cache/correlations/{book}_{chapter}_{verse}.json

Run standalone:
  python3 correlate.py [--rebuild] [--books Genesis Exodus ...]

The verse catalog must exist first (run pipeline.py --catalog-only).
Sources are pulled from whatever is already cached in cache/.
"""

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import scipy.sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CACHE_DIR    = Path("/Users/reify/lds_pipeline/cache")
CATALOG_PATH = CACHE_DIR / "verse_catalog.json"
CORR_DIR     = CACHE_DIR / "correlations"
EMB_DIR      = CACHE_DIR / "embeddings"

TOP_N      = 10    # matches per verse per source
MIN_SCORE  = 0.08  # minimum TF-IDF cosine score (lower threshold than dense embeddings)


# ── Source loaders ────────────────────────────────────────────────────────────

def load_jd_corpus() -> list[dict]:
    """Load Journal of Discourses paragraphs from cached volume files."""
    passages = []
    jd_dir = CACHE_DIR / "jd"
    for vol_file in sorted(jd_dir.glob("vol_*.txt")):
        m = re.search(r'vol_(\d+)', vol_file.name)
        if not m:
            continue
        vol_num = int(m.group(1))
        text = vol_file.read_text(encoding="utf-8", errors="replace")
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 80]
        for para in paras:
            passages.append({
                "source": "journal_of_discourses",
                "label": f"JD Vol {vol_num}",
                "text": para[:1500],
            })
    return passages


SEFARIA_EXCLUDE_CATEGORIES = {"Tanakh"}  # scripture text itself — would match verses directly

def load_sefaria_corpus() -> list[dict]:
    """Load cached Sefaria link texts (Talmud, Midrash, Targum).
    Excludes Tanakh category (direct scripture text = self-match)."""
    passages = []
    sefaria_dir = CACHE_DIR / "sefaria"
    for f in sefaria_dir.glob("links_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not data or not isinstance(data, list):
            continue
        for link in data:
            category = link.get("category", "Unknown")
            if category in SEFARIA_EXCLUDE_CATEGORIES:
                continue
            en = link.get("en", "") or link.get("text", "")
            if isinstance(en, list):
                en = " ".join(str(s) for s in en[:3])
            en = str(en).strip()
            if len(en) < 40:
                continue
            en = re.sub(r'<[^>]+>', '', en)[:500]
            ref = link.get("sourceRef", "") or link.get("ref", "")
            passages.append({
                "source": "sefaria",
                "label": f"{category}: {ref}",
                "text": en,
            })
    return passages



def load_all_sources() -> list[dict]:
    """Load all available source corpora.

    Donaldson is excluded — it's direct per-verse commentary already stored in
    the catalog and rendered inline in the epub. The correlation pool should only
    contain truly external sources.
    """
    all_passages = []

    jd = load_jd_corpus()
    print(f"  JD passages: {len(jd):,}")
    all_passages.extend(jd)

    sefaria = load_sefaria_corpus()
    print(f"  Sefaria passages: {len(sefaria):,}")
    all_passages.extend(sefaria)

    gc = _load_plaintext_dir(CACHE_DIR / "general_conference", "general_conference", "GC")
    print(f"  General Conference: {len(gc):,}")
    all_passages.extend(gc)

    gutenberg_lds = _load_plaintext_dir(CACHE_DIR / "gutenberg_lds", "gutenberg_lds", "LDS Historical")
    print(f"  Gutenberg LDS: {len(gutenberg_lds):,}")
    all_passages.extend(gutenberg_lds)

    church_fathers = _load_plaintext_dir(CACHE_DIR / "church_fathers", "church_fathers", "Church Fathers")
    print(f"  Church Fathers: {len(church_fathers):,}")
    all_passages.extend(church_fathers)

    ancient = _load_plaintext_dir(CACHE_DIR / "ancient_myths", "ancient_texts", "Ancient Texts")
    print(f"  Ancient Texts: {len(ancient):,}")
    all_passages.extend(ancient)

    hoc = _load_plaintext_dir(CACHE_DIR / "hoc", "history_of_church", "HoC")
    print(f"  History of Church: {len(hoc):,}")
    all_passages.extend(hoc)

    jsp = _load_plaintext_dir(CACHE_DIR / "joseph_smith_papers", "joseph_smith_papers", "JSP")
    print(f"  Joseph Smith Papers: {len(jsp):,}")
    all_passages.extend(jsp)

    donaldson = _load_donaldson_corpus()
    print(f"  Donaldson: {len(donaldson):,}")
    all_passages.extend(donaldson)

    # Use ABBYY column-correct OCR if available, else fall back to DjVu
    ts_abbyy = CACHE_DIR / "times_and_seasons" / "times_and_seasons_abbyy.txt"
    ts_glob  = "times_and_seasons_abbyy.txt" if ts_abbyy.exists() else "*.txt"
    ts = _load_plaintext_dir_glob(CACHE_DIR / "times_and_seasons", "times_and_seasons", "Times & Seasons", ts_glob)
    print(f"  Times and Seasons{'(ABBYY)' if ts_abbyy.exists() else ''}: {len(ts):,}")
    all_passages.extend(ts)

    ms_abbyy = CACHE_DIR / "millennial_star" / "millennial_star_abbyy.txt"
    ms_glob  = "millennial_star_abbyy.txt" if ms_abbyy.exists() else "*.txt"
    ms = _load_plaintext_dir_glob(CACHE_DIR / "millennial_star", "millennial_star", "Millennial Star", ms_glob)
    print(f"  Millennial Star{'(ABBYY)' if ms_abbyy.exists() else ''}: {len(ms):,}")
    all_passages.extend(ms)

    pioneer = _load_plaintext_dir(CACHE_DIR / "pioneer_journals", "pioneer_journals", "Pioneer Journals")
    print(f"  Pioneer Journals: {len(pioneer):,}")
    all_passages.extend(pioneer)

    # ── Scholarly sources (sync_extra_sources.py) ──────────────────────────
    for src_dir, src_key, src_label in [
        ("pseudepigrapha",   "pseudepigrapha",   "Pseudepigrapha"),
        ("apocrypha",        "apocrypha",        "LXX Apocrypha"),
        ("nag_hammadi",      "nag_hammadi",      "Nag Hammadi"),
        ("dead_sea_scrolls", "dead_sea_scrolls", "Dead Sea Scrolls"),
        ("bh_roberts",       "bh_roberts",       "B.H. Roberts"),
        ("nibley",           "nibley",           "Nibley"),
        ("nauvoo_theology",  "nauvoo_theology",  "Nauvoo Theology"),
        ("jst",              "jst",              "JST"),
    ]:
        passages = _load_plaintext_dir(CACHE_DIR / src_dir, src_key, src_label)
        if passages:
            print(f"  {src_label}: {len(passages):,}")
            all_passages.extend(passages)

    # Deduplicate by normalized text to prevent self-matches and near-duplicates
    seen = set()
    unique = []
    for p in all_passages:
        key = re.sub(r'\s+', ' ', p["text"].lower().strip())[:200]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    removed = len(all_passages) - len(unique)
    if removed:
        print(f"  Deduped: removed {removed:,} duplicate passages")
    return unique


def _load_donaldson_corpus() -> list[dict]:
    """Load Donaldson commentary as a searchable source corpus.
    Paragraphs are labeled with their origin verse but can match any verse."""
    corpus_file = CACHE_DIR / "donaldson" / "corpus.json"
    if not corpus_file.exists():
        return []
    data = json.loads(corpus_file.read_text(encoding="utf-8"))
    return [p for p in data if len(p.get("text", "")) >= 60]


_HIGH_NON_ASCII = re.compile(r'[^\x00-\x7F]')

def _ocr_ok(text: str) -> bool:
    """Return False if text has too many non-ASCII chars (OCR garbage)."""
    non_ascii = len(_HIGH_NON_ASCII.findall(text))
    return non_ascii / max(len(text), 1) < 0.07


def _load_plaintext_dir_glob(dir_path: Path, source_name: str, label_prefix: str, glob: str) -> list[dict]:
    """Load matching files from a directory using a specific glob pattern."""
    passages = []
    if not dir_path.exists():
        return passages
    for txt_file in dir_path.glob(glob):
        text = txt_file.read_text(encoding="utf-8", errors="replace")
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 80]
        label = f"{label_prefix}: {txt_file.stem}"
        for para in paras:
            if not _ocr_ok(para):
                continue
            passages.append({
                "source": source_name,
                "label":  label,
                "text":   para[:1500],
            })
    return passages


def _load_plaintext_dir(dir_path: Path, source_name: str, label_prefix: str) -> list[dict]:
    passages = []
    if not dir_path.exists():
        return passages
    for txt_file in dir_path.glob("*.txt"):
        text = txt_file.read_text(encoding="utf-8", errors="replace")
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 80]
        label = f"{label_prefix}: {txt_file.stem}"
        for para in paras:
            if not _ocr_ok(para):
                continue
            passages.append({
                "source": source_name,
                "label":  label,
                "text":   para[:1500],
            })
    return passages


# ── TF-IDF vectorization ──────────────────────────────────────────────────────

def build_tfidf(all_texts: list[str], cache_file: Path, rebuild: bool = False):
    """
    Fit TF-IDF vectorizer on all texts (verses + passages combined).
    Returns (vectorizer, sparse matrix of shape [n_texts, n_features]).
    Caches to disk as pickle.
    """
    if not rebuild and cache_file.exists():
        print(f"  Loading cached TF-IDF matrix from {cache_file.name}")
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    print(f"  Building TF-IDF over {len(all_texts):,} texts...", flush=True)
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),      # unigrams + bigrams for phrase matching
        min_df=2,                 # ignore hapax legomena
        max_df=0.95,              # ignore too-common terms
        sublinear_tf=True,        # log(1+tf) scaling
        strip_accents="unicode",
        stop_words="english",
    )
    matrix = vectorizer.fit_transform(all_texts)
    print(f"  Matrix: {matrix.shape[0]:,} × {matrix.shape[1]:,} features")

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "wb") as f:
        pickle.dump((vectorizer, matrix), f)

    return vectorizer, matrix


# ── Correlation ───────────────────────────────────────────────────────────────

def correlate(verses: list[dict], passages: list[dict],
              full_matrix: scipy.sparse.csr_matrix,
              n_verses: int, books_filter: set = None) -> None:
    """
    For each verse, find top-N matching passages using TF-IDF cosine similarity.
    full_matrix rows: [verse_0 ... verse_N, passage_0 ... passage_M]
    n_verses: number of verse rows at the start of full_matrix.
    Writes one JSON file per verse to cache/correlations/.
    """
    CORR_DIR.mkdir(parents=True, exist_ok=True)

    verse_matrix   = full_matrix[:n_verses]
    passage_matrix = full_matrix[n_verses:]

    print(f"  Correlating {n_verses:,} verses against {len(passages):,} passages...", flush=True)

    # Process in chunks to avoid huge memory spike
    CHUNK = 500
    written = 0
    for chunk_start in range(0, n_verses, CHUNK):
        chunk_end = min(chunk_start + CHUNK, n_verses)
        chunk_verses = verses[chunk_start:chunk_end]
        chunk_matrix = verse_matrix[chunk_start:chunk_end]

        # cosine_similarity returns dense [chunk × passages]
        sims = cosine_similarity(chunk_matrix, passage_matrix)

        for i, v in enumerate(chunk_verses):
            if books_filter and v["book"] not in books_filter:
                continue

            row = sims[i]
            # Get top-N indices sorted by score
            top_idx = np.argpartition(row, -TOP_N)[-TOP_N:]
            top_idx = top_idx[np.argsort(row[top_idx])[::-1]]

            matches = []
            for rank, idx in enumerate(top_idx):
                score = float(row[idx])
                if score < MIN_SCORE:
                    continue
                p = passages[idx]
                matches.append({
                    "rank":   rank + 1,
                    "score":  round(score, 4),
                    "source": p["source"],
                    "label":  p["label"],
                    "text":   p["text"],
                })

            key = f"{v['book']}_{v['chapter']}_{v['verse']}"
            out_file = CORR_DIR / f"{key}.json"
            out_file.write_text(
                json.dumps({
                    "book": v["book"], "chapter": v["chapter"], "verse": v["verse"],
                    "text": v["text"],
                    "matches": matches,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            written += 1

        if chunk_start % 5000 == 0 and chunk_start > 0:
            print(f"  ... {chunk_start:,}/{n_verses:,} verses processed", flush=True)

    print(f"  Written: {written:,} correlation files → {CORR_DIR}")


# ── Query helper ──────────────────────────────────────────────────────────────

def query_verse(book: str, chapter: int, verse: int) -> dict:
    """Load pre-computed correlations for a verse."""
    key = f"{book}_{chapter}_{verse}"
    out_file = CORR_DIR / f"{key}.json"
    if not out_file.exists():
        return {}
    return json.loads(out_file.read_text(encoding="utf-8"))


def print_verse_correlations(book: str, chapter: int, verse: int) -> None:
    """Pretty-print correlations for a verse."""
    data = query_verse(book, chapter, verse)
    if not data:
        print(f"No correlations for {book} {chapter}:{verse} (run correlate.py first)")
        return
    print(f"\n{'='*70}")
    print(f"{book} {chapter}:{verse}")
    print(f"{data['text']}")
    print(f"{'='*70}")
    for m in data.get("matches", []):
        print(f"\n[{m['rank']}] {m['source']} | {m['label']} (score: {m['score']})")
        print(f"  {m['text'][:200]}...")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Semantic verse correlator")
    parser.add_argument("--rebuild", action="store_true",
                        help="Force rebuild embeddings even if cached")
    parser.add_argument("--books", nargs="+",
                        help="Only correlate these books (default: all)")
    parser.add_argument("--query", nargs=3, metavar=("BOOK", "CH", "V"),
                        help="Query correlations for a single verse")
    args = parser.parse_args()

    # Query mode
    if args.query:
        book, ch, v = args.query[0], int(args.query[1]), int(args.query[2])
        print_verse_correlations(book, ch, v)
        return

    if not CATALOG_PATH.exists():
        print("ERROR: verse catalog not found. Run: python3 pipeline.py --catalog-only")
        sys.exit(1)

    print("\n═══ Loading catalog ═══")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    print(f"  {len(catalog):,} verses loaded")

    books_filter = set(args.books) if args.books else None
    if books_filter:
        print(f"  Filtering to: {books_filter}")

    print("\n═══ Loading source corpora ═══")
    passages = load_all_sources()
    print(f"  Total passages: {len(passages):,}")

    if not passages:
        print("No source passages found. Run pipeline.py first to cache sources.")
        sys.exit(1)

    EMB_DIR.mkdir(parents=True, exist_ok=True)

    if books_filter:
        subset = [v for v in catalog if v["book"] in books_filter]
    else:
        subset = catalog

    verse_texts  = [v["text"] for v in subset]
    source_texts = [p["text"] for p in passages]
    all_texts    = verse_texts + source_texts

    tfidf_cache = EMB_DIR / "tfidf.pkl"
    if args.rebuild:
        tfidf_cache.unlink(missing_ok=True)

    print("\n═══ TF-IDF vectorization ═══")
    _, full_matrix = build_tfidf(all_texts, tfidf_cache, rebuild=args.rebuild)

    print("\n═══ Correlating ═══")
    correlate(subset, passages, full_matrix, len(subset), books_filter)

    print("\nDone. Query with: python3 correlate.py --query Genesis 1 1")


if __name__ == "__main__":
    main()
