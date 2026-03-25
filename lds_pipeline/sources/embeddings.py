"""
Semantic Embedding Layer — the upgrade that changes everything.

Instead of only finding content that explicitly CITES a verse by reference,
this finds content that MEANS the same thing — across all 30+ sources.

How it works:
  1. Every passage from every source is chunked (~200 words) and embedded
     using sentence-transformers (all-MiniLM-L6-v2, runs locally, ~80MB).
  2. All embeddings stored in a FAISS index with source metadata.
  3. At query time: embed the verse text → find top-N most similar passages
     across all sources → return as "semantic matches" with similarity score.

This surfaces hidden connections that reference-scanning can never find:
  - Enoch describing something conceptually identical to a D&C verse
  - A Church Father discussing the same doctrine as a BoM passage
  - Gilgamesh flood details that parallel Genesis specifics
  - Nibley papers connecting temple symbolism to specific verses
  - Zohar mysticism paralleling LDS doctrines without citing the verse

Model: all-MiniLM-L6-v2
  - 80MB download (cached locally after first run)
  - 384-dimensional embeddings
  - ~14k sentences/sec on CPU
  - Strong semantic understanding
"""

import json
import re
import os
import pickle
import numpy as np
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/embeddings")
INDEX_PATH  = CACHE_DIR / "faiss.index"
META_PATH   = CACHE_DIR / "metadata.pkl"
CHUNK_SIZE  = 200   # words per chunk
CHUNK_OVERLAP = 30  # word overlap between chunks
TOP_K = 8           # candidates to retrieve
MIN_SCORE = 0.35    # minimum cosine similarity (0-1)

# Sources to include in the semantic index — everything we have
SOURCE_REGISTRY = {}  # populated by register_source()


def register_source(key: str, passages: list[dict]):
    """
    Register passages for embedding.
    Each passage: {"text": str, "source": str, "ref": str (optional), "note": str (optional)}
    Call this before build_index().
    """
    SOURCE_REGISTRY[key] = passages
    print(f"  Registered {len(passages):,} passages from: {key}")


# ── Model (lazy-loaded) ───────────────────────────────────────────────────────

_model = None
_model_lock = None

def _get_model():
    global _model, _model_lock
    import threading
    if _model_lock is None:
        _model_lock = threading.Lock()
    if _model is None:
        with _model_lock:
            if _model is None:  # double-checked locking
                from sentence_transformers import SentenceTransformer
                print("  Loading embedding model (all-MiniLM-L6-v2)...")
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                print("  Model ready.")
    return _model


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, source: str, ref: str = "", note: str = "") -> list[dict]:
    """Split text into overlapping word chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + CHUNK_SIZE]
        chunk_text  = " ".join(chunk_words)
        if len(chunk_text.strip()) > 50:  # skip tiny fragments
            chunks.append({
                "text":   chunk_text,
                "source": source,
                "ref":    ref,
                "note":   note,
            })
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def chunk_all_sources() -> list[dict]:
    """Convert all registered sources into chunks ready for embedding."""
    all_chunks = []
    for key, passages in SOURCE_REGISTRY.items():
        for p in passages:
            text   = p.get("text", "")
            source = p.get("source", key)
            ref    = p.get("ref", "")
            note   = p.get("note", "")
            if len(text.split()) <= CHUNK_SIZE:
                if len(text.strip()) > 50:
                    all_chunks.append({"text": text, "source": source, "ref": ref, "note": note})
            else:
                all_chunks.extend(_chunk_text(text, source, ref, note))
    return all_chunks


# ── Index build ───────────────────────────────────────────────────────────────

def build_index(force: bool = False) -> bool:
    """
    Build the FAISS index from all registered sources.
    Skips if index already exists (use force=True to rebuild).
    Returns True if built, False if skipped.
    """
    if INDEX_PATH.exists() and META_PATH.exists() and not force:
        print(f"  Semantic index exists ({INDEX_PATH.stat().st_size / 1e6:.1f} MB) — skipping build")
        return False

    import faiss

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model = _get_model()

    chunks = chunk_all_sources()
    if not chunks:
        print("  No sources registered — cannot build index")
        return False

    print(f"  Embedding {len(chunks):,} chunks...")
    texts = [c["text"] for c in chunks]

    # Encode in batches to show progress
    batch_size = 512
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        vecs  = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        embeddings.append(vecs)
        if i % 5000 == 0 and i > 0:
            print(f"    {i:,}/{len(texts):,} chunks embedded")

    matrix = np.vstack(embeddings).astype("float32")

    # Normalize for cosine similarity (inner product on unit vectors = cosine)
    faiss.normalize_L2(matrix)

    # Build HNSW index (fast approximate nearest neighbor)
    dim = matrix.shape[1]
    index = faiss.IndexHNSWFlat(dim, 32)   # 32 neighbors per node
    index.hnsw.efConstruction = 200
    index.hnsw.efSearch = 64
    index.add(matrix)

    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(chunks, f)

    size_mb = INDEX_PATH.stat().st_size / 1e6
    print(f"  FAISS index built: {len(chunks):,} chunks, {size_mb:.1f} MB → {INDEX_PATH}")
    return True


# ── Query ─────────────────────────────────────────────────────────────────────

_index    = None
_metadata = None


def _load_index():
    global _index, _metadata
    if _index is not None:
        return True
    if not INDEX_PATH.exists():
        return False

    import faiss
    _index = faiss.read_index(str(INDEX_PATH))
    _index.hnsw.efSearch = 64
    with open(META_PATH, "rb") as f:
        _metadata = pickle.load(f)
    return True


def search(verse_text: str, book: str, chapter: int, verse_num: int,
           top_k: int = TOP_K, min_score: float = MIN_SCORE) -> list[dict]:
    """
    Find semantically similar passages for a verse.

    Returns list of dicts: {text, source, ref, note, score}
    Filtered to min_score and deduplicated.
    """
    if not _load_index():
        return []

    model = _get_model()
    query = f"{book} {chapter}:{verse_num} — {verse_text}"
    vec = model.encode([query], convert_to_numpy=True).astype("float32")
    import faiss as _faiss
    _faiss.normalize_L2(vec)

    scores, indices = _index.search(vec, top_k * 3)  # over-fetch, then filter

    results = []
    seen_texts = set()

    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or score < min_score:
            continue
        chunk = _metadata[idx]
        # Deduplicate by first 80 chars
        key = chunk["text"][:80]
        if key in seen_texts:
            continue
        seen_texts.add(key)

        results.append({
            "text":   chunk["text"],
            "source": chunk["source"],
            "ref":    chunk.get("ref", ""),
            "note":   chunk.get("note", ""),
            "score":  round(float(score), 3),
        })

        if len(results) >= top_k:
            break

    return results


# ── Source loading helpers ────────────────────────────────────────────────────
# These load from the existing cached source files and register them

def load_source_file(path: str, source_label: str, ref: str = "") -> list[dict]:
    """Load a plain text file and create passage list."""
    p = Path(path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    # Split into paragraphs
    paragraphs = [s.strip() for s in re.split(r'\n{2,}', text) if len(s.strip()) > 80]
    return [{"text": para, "source": source_label, "ref": ref} for para in paragraphs]


def load_all_cached_sources():
    """
    Load every cached source text file into the registry.
    Call this before build_index().
    """
    base = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache")

    source_dirs = {
        "jd":             ("Journal of Discourses",         "vol_*.txt"),
        "hoc":            ("History of the Church",         "vol_*.txt"),
        "strongs":        None,   # skip — already structured
        "sefaria":        None,   # skip — per-verse JSON
        "gutenberg_lds":  ("Gutenberg LDS",                 "*.txt"),
        "mcconkie":       ("McConkie / Teachings of JS",    "*.txt"),
        "early_saints":   ("Early Church Journals",         "*.txt"),
        "ancient_myths":  ("Ancient Texts",                 "*.txt"),
        "jsp":            ("Joseph Smith Papers",           "*.txt"),
    }

    for dir_name, spec in source_dirs.items():
        if spec is None:
            continue
        label, pattern = spec
        dir_path = base / dir_name
        if not dir_path.exists():
            continue
        passages = []
        for fpath in dir_path.glob(pattern):
            if fpath.stat().st_size < 500:
                continue
            text = fpath.read_text(encoding="utf-8", errors="replace")
            paras = [s.strip() for s in re.split(r'\n{2,}', text) if len(s.strip()) > 80]
            passages.extend({"text": p, "source": label, "ref": fpath.stem} for p in paras)
        if passages:
            register_source(dir_name, passages)

    # Also register curated ancient parallels
    from sources.ancient_myths import CURATED_PARALLELS
    ancient_passages = []
    for verse_key, parallels in CURATED_PARALLELS.items():
        for p in parallels:
            ancient_passages.append({
                "text":   p["excerpt"],
                "source": p["source"],
                "ref":    verse_key,
                "note":   p["note"],
            })
    if ancient_passages:
        register_source("ancient_curated", ancient_passages)
        print(f"  Registered {len(ancient_passages)} curated ancient parallels")
