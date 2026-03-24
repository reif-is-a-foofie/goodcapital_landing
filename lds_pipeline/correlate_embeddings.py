"""
Semantic correlation engine using sentence-transformers + FAISS.

Encodes all source passages as dense vectors, then finds top-N matches
per verse using cosine similarity. Much better semantic quality than TF-IDF
for theological/biblical text with paraphrase and concept matching.

Model: all-MiniLM-L6-v2 (22M params, 384-dim, fast on CPU)
Index: FAISS IndexFlatIP over L2-normalized vectors = cosine similarity

Writes per-verse top-N matches to:
  cache/correlations/{book}_{chapter}_{verse}.json

Run standalone:
  python3 correlate_embeddings.py [--rebuild] [--books Genesis ...]
  python3 correlate_embeddings.py --query Genesis 1 1

Called from source_worker after new content is downloaded.
"""

import argparse
import json
import os
import pickle
import re
import sys
from pathlib import Path

import numpy as np

# Force CPU — MPS hangs on Python 3.9 with sentence-transformers
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

CACHE_DIR    = Path("/Users/reify/lds_pipeline/cache")
CATALOG_PATH = CACHE_DIR / "verse_catalog.json"
CORR_DIR     = CACHE_DIR / "correlations"
EMB_DIR      = CACHE_DIR / "embeddings_dense"

MODEL_NAME = "all-MiniLM-L6-v2"   # 22M params, 384-dim, ~80s for 100K passages on CPU
BATCH_SIZE = 256
TOP_N      = 10
MIN_SCORE  = 0.30   # cosine similarity (dense embeddings score higher than TF-IDF)


# ── Source loaders (same as correlate.py) ────────────────────────────────────

def load_jd_corpus() -> list[dict]:
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
                "label":  f"JD Vol {vol_num}",
                "text":   para[:1500],
            })
    return passages


SEFARIA_EXCLUDE_CATEGORIES = {"Tanakh"}

def load_sefaria_corpus() -> list[dict]:
    """Excludes Tanakh category — direct scripture text would self-match verses."""
    passages = []
    sefaria_dir = CACHE_DIR / "sefaria"
    if not sefaria_dir.exists():
        return passages
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
                "label":  f"{category}: {ref}",
                "text":   en,
            })
    return passages


def load_donaldson_corpus(catalog: list[dict]) -> list[dict]:
    passages = []
    for v in catalog:
        for para in v.get("donaldson", []):
            if len(para) < 60:
                continue
            passages.append({
                "source": "donaldson",
                "label":  f"{v['book']} {v['chapter']}:{v['verse']}",
                "text":   para[:1500],
                "_origin": (v["book"], v["chapter"], v["verse"]),
            })
    return passages


def load_gc_corpus() -> list[dict]:
    """Load General Conference talk texts."""
    passages = []
    gc_dir = CACHE_DIR / "general_conference"
    if not gc_dir.exists():
        return passages
    index_file = gc_dir / "talk_index.json"
    if not index_file.exists():
        return passages
    try:
        index = json.loads(index_file.read_text(encoding="utf-8"))
    except Exception:
        return passages

    all_talks = {t["uri"]: t for talks in index.values() for t in talks if t.get("uri")}
    for uri, meta in all_talks.items():
        safe_key = re.sub(r'[^\w]', '_', uri.strip("/"))
        txt_file = gc_dir / f"{safe_key}.txt"
        if not txt_file.exists():
            continue
        text = txt_file.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) < 100:
            continue
        # Split into paragraphs
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 80]
        speaker = meta.get("speaker", "")
        year    = meta.get("year", "")
        session = meta.get("session", "")
        for para in paras:
            passages.append({
                "source": "general_conference",
                "label":  f"GC {year}/{session} — {speaker}",
                "text":   para[:1500],
            })
    return passages


_HIGH_NON_ASCII = re.compile(r'[^\x00-\x7F]')

def _ocr_ok(text: str) -> bool:
    """Return False if text has too many non-ASCII chars (OCR garbage)."""
    non_ascii = len(_HIGH_NON_ASCII.findall(text))
    return non_ascii / max(len(text), 1) < 0.07


def load_plaintext_dir_glob(dir_path: Path, source_name: str, label_prefix: str, glob: str) -> list[dict]:
    """Load matching files from a directory using a specific glob pattern."""
    passages = []
    if not dir_path.exists():
        return passages
    for txt_file in dir_path.glob(glob):
        if txt_file.name == "scripture_index.json":
            continue
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


def load_plaintext_dir(dir_path: Path, source_name: str, label_prefix: str) -> list[dict]:
    """Generic loader for a directory of .txt files."""
    passages = []
    if not dir_path.exists():
        return passages
    for txt_file in dir_path.glob("*.txt"):
        if txt_file.name == "scripture_index.json":
            continue
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


def load_all_sources() -> list[dict]:
    all_passages = []

    jd = load_jd_corpus()
    print(f"  JD: {len(jd):,} passages")
    all_passages.extend(jd)

    sefaria = load_sefaria_corpus()
    print(f"  Sefaria: {len(sefaria):,} passages")
    all_passages.extend(sefaria)

    gc = load_gc_corpus()
    print(f"  General Conference: {len(gc):,} passages")
    all_passages.extend(gc)

    gutenberg_lds = load_plaintext_dir(CACHE_DIR / "gutenberg_lds", "gutenberg_lds", "LDS Historical")
    print(f"  Gutenberg LDS: {len(gutenberg_lds):,} passages")
    all_passages.extend(gutenberg_lds)

    church_fathers = load_plaintext_dir(CACHE_DIR / "church_fathers", "church_fathers", "Church Fathers")
    print(f"  Church Fathers: {len(church_fathers):,} passages")
    all_passages.extend(church_fathers)

    ancient_myths = load_plaintext_dir(CACHE_DIR / "ancient_myths", "ancient_myths", "Ancient Texts")
    print(f"  Ancient Texts: {len(ancient_myths):,} passages")
    all_passages.extend(ancient_myths)

    hoc = load_plaintext_dir(CACHE_DIR / "hoc", "history_of_church", "HoC")
    print(f"  History of Church: {len(hoc):,} passages")
    all_passages.extend(hoc)

    jsp = load_plaintext_dir(CACHE_DIR / "joseph_smith_papers", "joseph_smith_papers", "JSP")
    print(f"  Joseph Smith Papers: {len(jsp):,} passages")
    all_passages.extend(jsp)

    donaldson_file = CACHE_DIR / "donaldson" / "corpus.json"
    if donaldson_file.exists():
        donaldson = [p for p in json.loads(donaldson_file.read_text()) if len(p.get("text","")) >= 60]
        print(f"  Donaldson: {len(donaldson):,} passages")
        all_passages.extend(donaldson)

    ts_abbyy = CACHE_DIR / "times_and_seasons" / "times_and_seasons_abbyy.txt"
    ts_glob  = "times_and_seasons_abbyy.txt" if ts_abbyy.exists() else "*.txt"
    ts = load_plaintext_dir_glob(CACHE_DIR / "times_and_seasons", "times_and_seasons", "Times & Seasons", ts_glob)
    print(f"  Times and Seasons{'(ABBYY)' if ts_abbyy.exists() else ''}: {len(ts):,} passages")
    all_passages.extend(ts)

    ms_abbyy = CACHE_DIR / "millennial_star" / "millennial_star_abbyy.txt"
    ms_glob  = "millennial_star_abbyy.txt" if ms_abbyy.exists() else "*.txt"
    ms = load_plaintext_dir_glob(CACHE_DIR / "millennial_star", "millennial_star", "Millennial Star", ms_glob)
    print(f"  Millennial Star{'(ABBYY)' if ms_abbyy.exists() else ''}: {len(ms):,} passages")
    all_passages.extend(ms)

    pioneer = load_plaintext_dir(CACHE_DIR / "pioneer_journals", "pioneer_journals", "Pioneer Journals")
    print(f"  Pioneer Journals: {len(pioneer):,} passages")
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
        passages = load_plaintext_dir(CACHE_DIR / src_dir, src_key, src_label)
        if passages:
            print(f"  {src_label}: {len(passages):,} passages")
            all_passages.extend(passages)

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


# ── Embedding ─────────────────────────────────────────────────────────────────

def get_model():
    from sentence_transformers import SentenceTransformer
    print(f"  Loading model {MODEL_NAME} (CPU)...", flush=True)
    return SentenceTransformer(MODEL_NAME, device="cpu")


def embed_texts(model, texts: list[str], desc: str = "") -> np.ndarray:
    """Encode texts, return L2-normalized float32 array."""
    if desc:
        print(f"  Encoding {len(texts):,} {desc}...", flush=True)
    vecs = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,   # L2-normalize → dot product = cosine
    )
    return vecs.astype(np.float32)


def load_or_build_passage_embeddings(model, passages: list[dict], rebuild: bool = False) -> np.ndarray:
    """Build passage embeddings, caching to disk."""
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = EMB_DIR / "passages.npy"
    meta_file  = EMB_DIR / "passages_meta.pkl"

    if not rebuild and cache_file.exists() and meta_file.exists():
        stored_count = pickle.loads(meta_file.read_bytes())
        if stored_count == len(passages):
            print(f"  Loading cached passage embeddings ({stored_count:,})...")
            return np.load(str(cache_file))
        else:
            print(f"  Passage count changed ({stored_count} → {len(passages)}), rebuilding...")

    texts = [p["text"] for p in passages]
    vecs  = embed_texts(model, texts, "source passages")
    np.save(str(cache_file), vecs)
    meta_file.write_bytes(pickle.dumps(len(passages)))
    print(f"  Saved passage embeddings → {cache_file}")
    return vecs


# ── FAISS index ───────────────────────────────────────────────────────────────

def build_faiss_index(passage_vecs: np.ndarray):
    """Build an in-memory FAISS flat inner-product index."""
    import faiss
    dim   = passage_vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(passage_vecs)
    print(f"  FAISS index: {index.ntotal:,} vectors, dim={dim}")
    return index


# ── Correlation ───────────────────────────────────────────────────────────────

def correlate(verses: list[dict], passages: list[dict],
              model, passage_vecs: np.ndarray,
              books_filter: set = None) -> None:
    CORR_DIR.mkdir(parents=True, exist_ok=True)

    if books_filter:
        subset = [v for v in verses if v["book"] in books_filter]
    else:
        subset = verses

    print(f"  Building FAISS index over {len(passages):,} passages...")
    index = build_faiss_index(passage_vecs)

    print(f"  Encoding {len(subset):,} verses...")
    verse_texts = [v["text"] for v in subset]
    verse_vecs  = embed_texts(model, verse_texts, "verses")

    print(f"  Searching top-{TOP_N} for {len(subset):,} verses...", flush=True)
    # FAISS batch search
    scores_all, indices_all = index.search(verse_vecs, TOP_N)

    written = 0
    for i, v in enumerate(subset):
        matches = []
        for rank in range(TOP_N):
            score = float(scores_all[i, rank])
            if score < MIN_SCORE:
                continue
            idx = int(indices_all[i, rank])
            p   = passages[idx]
            matches.append({
                "rank":   rank + 1,
                "score":  round(score, 4),
                "source": p["source"],
                "label":  p["label"],
                "text":   p["text"],
            })

        key      = f"{v['book']}_{v['chapter']}_{v['verse']}"
        out_file = CORR_DIR / f"{key}.json"
        out_file.write_text(
            json.dumps({
                "book": v["book"], "chapter": v["chapter"], "verse": v["verse"],
                "text": v["text"],
                "matches": matches,
                "engine": "sentence_transformers",
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written += 1

    print(f"  Written: {written:,} correlation files → {CORR_DIR}")


# ── Query helper ──────────────────────────────────────────────────────────────

def print_verse_correlations(book: str, chapter: int, verse: int) -> None:
    key      = f"{book}_{chapter}_{verse}"
    out_file = CORR_DIR / f"{key}.json"
    if not out_file.exists():
        print(f"No correlations for {book} {chapter}:{verse}")
        return
    data = json.loads(out_file.read_text(encoding="utf-8"))
    engine = data.get("engine", "tfidf")
    print(f"\n{'='*70}")
    print(f"{book} {chapter}:{verse}  [{engine}]")
    print(f"{data['text']}")
    print(f"{'='*70}")
    for m in data.get("matches", []):
        print(f"\n[{m['rank']}] {m['source']} | {m['label']} (score: {m['score']})")
        print(f"  {m['text'][:300]}...")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dense embedding verse correlator")
    parser.add_argument("--rebuild", action="store_true",
                        help="Force rebuild passage embeddings")
    parser.add_argument("--books", nargs="+",
                        help="Only correlate these books")
    parser.add_argument("--query", nargs=3, metavar=("BOOK", "CH", "V"),
                        help="Query a single verse")
    args = parser.parse_args()

    if args.query:
        book, ch, v = args.query[0], int(args.query[1]), int(args.query[2])
        print_verse_correlations(book, ch, v)
        return

    if not CATALOG_PATH.exists():
        print("ERROR: verse catalog not found. Run: python3 pipeline.py --catalog-only")
        sys.exit(1)

    print("\n═══ Loading catalog ═══")
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    print(f"  {len(catalog):,} verses")

    print("\n═══ Loading source corpora ═══")
    passages = load_all_sources()
    print(f"  Total: {len(passages):,} passages")

    if not passages:
        print("No source passages found.")
        sys.exit(1)

    print("\n═══ Embedding ═══")
    model = get_model()
    passage_vecs = load_or_build_passage_embeddings(model, passages, rebuild=args.rebuild)

    print("\n═══ Correlating ═══")
    books_filter = set(args.books) if args.books else None
    correlate(catalog, passages, model, passage_vecs, books_filter)

    print("\nDone. Query with: python3 correlate_embeddings.py --query Genesis 1 1")


if __name__ == "__main__":
    main()
