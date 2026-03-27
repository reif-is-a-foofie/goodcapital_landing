#!/usr/bin/env python3
"""
Background transformer worker for semantic correlation rebuilds.

Runs `correlate_embeddings.py` whenever watched corpus/artifact inputs change.
This is meant to stay running in the background while source and scripture data
continue to evolve, so the semantic graph stays fresh without manual orchestration.

Usage:
  python3 lds_pipeline/transformer_worker.py
  python3 lds_pipeline/transformer_worker.py --once
  python3 lds_pipeline/transformer_worker.py --interval 90
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
STATE_FILE = CACHE_DIR / "transformer_worker_state.json"
LOG_FILE = CACHE_DIR / "transformer_worker.log"
CORR_DIR = CACHE_DIR / "correlations"
WORDS_TARGETS = [
    *sorted((ROOT.parent / "library" / "sources" / "journal_of_discourses").glob("vol_*_words.json")),
    *sorted((ROOT.parent / "library" / "sources" / "history_of_church").glob("vol*_words.json")),
]

WATCH_PATHS = [
    CACHE_DIR / "verse_catalog.json",
    CACHE_DIR / "standard_works" / "verse_catalog.json",
    CACHE_DIR / "jd",
    CACHE_DIR / "general_conference",
    CACHE_DIR / "hoc",
    CACHE_DIR / "joseph_smith_papers",
    CACHE_DIR / "ancient_myths",
    CACHE_DIR / "church_fathers",
    CACHE_DIR / "gutenberg_lds",
    CACHE_DIR / "times_and_seasons",
    CACHE_DIR / "millennial_star",
    ROOT / "sources",
]

WATCH_SUFFIXES = {".json", ".txt"}


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def iter_watch_files():
    for path in WATCH_PATHS:
        if path.is_file():
            yield path
            continue
        if not path.exists() or not path.is_dir():
            continue
        for child in sorted(path.rglob("*")):
            if child.is_file() and child.suffix in WATCH_SUFFIXES:
                yield child


def build_signature() -> dict:
    hasher = hashlib.sha256()
    file_count = 0
    newest_mtime = 0.0

    for path in iter_watch_files():
        stat = path.stat()
        rel = path.relative_to(ROOT)
        hasher.update(str(rel).encode("utf-8"))
        hasher.update(str(stat.st_size).encode("utf-8"))
        hasher.update(str(int(stat.st_mtime)).encode("utf-8"))
        file_count += 1
        newest_mtime = max(newest_mtime, stat.st_mtime)

    return {
        "digest": hasher.hexdigest(),
        "file_count": file_count,
        "newest_mtime": int(newest_mtime),
    }


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def correlations_missing() -> bool:
    if not CORR_DIR.exists():
        return True
    return not any(CORR_DIR.glob("*.json"))


def source_sidecars_missing() -> bool:
    if not WORDS_TARGETS:
        return True
    return any(not path.exists() for path in WORDS_TARGETS)


def run_correlations() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "correlate_embeddings.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    tail = "\n".join((output or error).splitlines()[-8:])
    return result.returncode == 0, tail


def run_source_word_sidecars() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "build_source_words.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    tail = "\n".join((output or error).splitlines()[-8:])
    return result.returncode == 0, tail


def maybe_run(force: bool = False) -> bool:
    state = load_state()
    signature = build_signature()
    previous = state.get("signature", {})

    need_correlations = force or correlations_missing() or previous.get("digest") != signature["digest"]
    need_sidecars = force or source_sidecars_missing() or need_correlations

    if not need_correlations and not need_sidecars:
        log("No corpus or sidecar changes detected; semantic correlations remain current")
        return False

    if need_correlations:
        reason = "forced" if force else "changed inputs"
        if correlations_missing():
            reason = "missing correlation artifacts"
        log(f"Running sentence-transformer correlations ({reason})")
        ok, tail = run_correlations()
        if not ok:
            log("Transformer correlation ERROR")
            if tail:
                for line in tail.splitlines():
                    log(f"  {line}")
            state["last_error_ts"] = int(time.time())
            save_state(state)
            return False
        log("Transformer correlations complete ✓")
        if tail:
            for line in tail.splitlines():
                log(f"  {line}")

    if need_sidecars:
        sidecar_reason = "forced" if force and not need_correlations else "changed sources"
        if source_sidecars_missing():
            sidecar_reason = "missing source-word artifacts"
        if need_correlations:
            sidecar_reason = "fresh correlations"
        log(f"Refreshing source-word sidecars ({sidecar_reason})")
        words_ok, words_tail = run_source_word_sidecars()
        if not words_ok:
            log("Source-word sidecar ERROR")
            if words_tail:
                for line in words_tail.splitlines():
                    log(f"  {line}")
            state["last_error_ts"] = int(time.time())
            save_state(state)
            return False
        log("Source-word sidecars complete ✓")
        if words_tail:
            for line in words_tail.splitlines():
                log(f"  {line}")

    state["signature"] = signature
    state["last_success_ts"] = int(time.time())
    if need_sidecars:
        state["last_sidecar_ts"] = int(time.time())
    save_state(state)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Background transformer correlation worker")
    parser.add_argument("--once", action="store_true", help="Run one change check / rebuild pass and exit")
    parser.add_argument("--interval", type=int, default=180, help="Polling interval in seconds for background mode")
    parser.add_argument("--force", action="store_true", help="Force a correlation rebuild even if the watched inputs did not change")
    args = parser.parse_args()

    if args.once:
        maybe_run(force=args.force)
        return

    log("=" * 60)
    log(f"Transformer worker started (interval={args.interval}s)")
    maybe_run(force=args.force)

    while True:
        time.sleep(max(15, args.interval))
        maybe_run(force=False)


if __name__ == "__main__":
    main()
