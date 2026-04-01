#!/usr/bin/env python3
"""
Source Ingestor — T-0073

Takes a Source Scout ledger task (by task ID) and runs the fetched source
through the library pipeline so it appears in the reader.

Pipeline stages executed:
  1. Parse task notes to extract title, URL, copyright/relevance metadata
  2. Fetch the page and strip HTML to clean plain text
  3. Save text to the correct cache subdirectory
  4. Run build_source_library.py  → generates HTML pages + source_toc.json
  5. Run build_source_words.py    → generates _words.json per document
  6. Run build_search_index.py    → refreshes library/search.json
  7. Run build_source_dashboard.py → refreshes source-dashboard.json

Review gate: the ingestor stops BEFORE correlate_embeddings (expensive CPU
job). It creates a human-review task instead. A human or a downstream agent
can run correlate_embeddings after verifying the content is acceptable.

Conservative policy:
  - Requires both copyright_score >= 0.7 AND relevance_score >= 0.5
  - If either score is below threshold, writes a review task and exits
  - If fetch fails or yields < 500 words, writes a review task and exits
  - Never overwrites an existing cache file — creates a review task instead
  - All actions are recorded in the task notes

Usage:
  python3 source_ingestor.py --task-id T-XXXX
  python3 source_ingestor.py --task-id T-XXXX --dry-run
  python3 source_ingestor.py --task-id T-XXXX --group gutenberg_lds
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "task_ledger.py"
PIPELINE_DIR = ROOT / "lds_pipeline"
CACHE_DIR = PIPELINE_DIR / "cache"
LIBRARY = ROOT / "library"
DIAG = ROOT / "diagnostics"

# All known cache subdirectories that map to known source groups.
# New sources will be placed in the most appropriate group based on
# content keywords, or in "gutenberg_lds" as a safe default.
GROUP_CACHE_MAP = {
    "gutenberg_lds":        CACHE_DIR / "gutenberg_lds",
    "church_fathers":       CACHE_DIR / "church_fathers",
    "ancient_texts":        CACHE_DIR / "ancient_myths",
    "pseudepigrapha":       CACHE_DIR / "pseudepigrapha",
    "apocrypha":            CACHE_DIR / "apocrypha",
    "nag_hammadi":          CACHE_DIR / "nag_hammadi",
    "dead_sea_scrolls":     CACHE_DIR / "dead_sea_scrolls",
    "history_of_church":    CACHE_DIR / "hoc",
    "joseph_smith_papers":  CACHE_DIR / "joseph_smith_papers",
    "pioneer_journals":     CACHE_DIR / "pioneer_journals",
    "journal_of_discourses": CACHE_DIR / "jd",
    "bh_roberts":           CACHE_DIR / "bh_roberts",
    "nibley":               CACHE_DIR / "nibley",
    "nauvoo_theology":      CACHE_DIR / "nauvoo_theology",
}

# Keyword hints used to auto-select the best group
GROUP_KEYWORDS: list[tuple[str, list[str]]] = [
    ("pseudepigrapha",   ["pseudepigrapha", "enoch", "jubilees", "baruch", "esdras", "maccabees",
                          "testament of", "apocalypse of", "ascension of"]),
    ("apocrypha",        ["apocrypha", "septuagint", "lxx", "deuterocanonical", "tobit", "judith",
                          "wisdom of solomon", "sirach", "ecclesiasticus"]),
    ("nag_hammadi",      ["nag hammadi", "gnostic", "gospel of thomas", "gospel of philip",
                          "coptic", "gospel of truth"]),
    ("dead_sea_scrolls", ["dead sea scrolls", "qumran", "community rule", "war scroll",
                          "damascus document", "manual of discipline"]),
    ("church_fathers",   ["origen", "clement", "irenaeus", "tertullian", "justin martyr",
                          "eusebius", "church fathers", "ante-nicene", "patristic", "chrysostom"]),
    ("ancient_texts",    ["gilgamesh", "enuma elish", "ugaritic", "ancient near east",
                          "josephus", "philo of alexandria", "akkadian"]),
    ("pioneer_journals", ["pioneer", "wilford woodruff", "heber kimball", "brigham young journal"]),
    ("nauvoo_theology",  ["nauvoo", "times and seasons", "millennial star"]),
    ("bh_roberts",        ["b.h. roberts", "comprehensive history", "seventy's course", "defense of the faith"]),
    ("history_of_church", ["history of the church", "joseph smith history"]),
    ("joseph_smith_papers", ["joseph smith papers"]),
    ("journal_of_discourses", ["journal of discourses"]),
]

COPYRIGHT_PASS = 0.7
RELEVANCE_PASS = 0.5
MIN_WORD_COUNT = 500


# ── Ledger helpers ──────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_ledger(*args: str, **kwargs) -> dict:
    """Call task_ledger.py with args, return parsed JSON output."""
    cmd = ["python3", str(LEDGER)] + list(args)
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False, **kwargs)
    try:
        return json.loads(result.stdout or "{}")
    except Exception:
        return {"_raw": result.stdout, "_err": result.stderr}


def ledger_note(task_id: str, note: str, agent: str = "source-ingestor") -> None:
    run_ledger("note", task_id, "--agent", agent, "--note", note)


def ledger_complete(task_id: str, summary: str, agent: str = "source-ingestor") -> None:
    run_ledger(
        "complete", task_id,
        "--agent", agent,
        "--summary", summary,
    )


def ledger_ensure(title: str, source: str = "source-ingestor", priority: str = "normal") -> str:
    """Ensure a task exists and return its id."""
    result = run_ledger("ensure", title, "--source", source, "--priority", priority)
    return str(result.get("task_id", ""))


def load_task_state(task_id: str) -> Optional[dict]:
    """Return the current state dict for a task, or None."""
    result = run_ledger("list")
    tasks = result if isinstance(result, list) else []
    for t in tasks:
        if t.get("task_id") == task_id:
            return t
    return None


def load_task_notes(task_id: str) -> list[str]:
    """Return note strings from task_ledger.py list --notes output."""
    # We use list (full output) and find the task
    rows = load_rows_raw()
    notes = []
    for row in rows:
        if row.get("event") == "task_noted" and row.get("task_id") == task_id:
            notes.append(row.get("note", ""))
    return notes


def load_rows_raw() -> list[dict]:
    ledger_file = ROOT / "task-ledger.jsonl"
    if not ledger_file.exists():
        return []
    rows = []
    for line in ledger_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def get_task_row(task_id: str) -> Optional[dict]:
    """Return the task_registered row for a given task_id."""
    for row in load_rows_raw():
        if row.get("event") == "task_registered" and row.get("task_id") == task_id:
            return row
    return None


# ── Task metadata parsing ───────────────────────────────────────────────────

def parse_scout_task(task_id: str) -> dict:
    """
    Extract URL, title, copyright score, and relevance score from the
    task title + notes written by source_scout.py.

    Scout task title format:
      "Source Scout: ingest 'Title' — copyright=0.95 (...), relevance=0.82 (...) — URL: https://..."

    Scout note format:
      "Candidate: Title | URL: https://... | copyright=0.95 (reason) | relevance=0.82 (reason)"

    Returns a dict with keys:
      title, url, copyright_score, copyright_reason, relevance_score, relevance_reason, raw_title
    """
    row = get_task_row(task_id)
    if not row:
        return {"error": f"task {task_id} not found in ledger"}

    raw_title = row.get("title", "")
    result = {
        "task_id": task_id,
        "raw_title": raw_title,
        "title": "",
        "url": "",
        "copyright_score": 0.0,
        "copyright_reason": "",
        "relevance_score": 0.0,
        "relevance_reason": "",
        "error": "",
    }

    # Parse from title first: "Source Scout: ingest 'Title' — ... — URL: https://..."
    url_m = re.search(r'URL:\s*(https?://\S+)', raw_title)
    if url_m:
        result["url"] = url_m.group(1).rstrip(".,")

    title_m = re.search(r"ingest '([^']+)'", raw_title)
    if title_m:
        result["title"] = title_m.group(1)

    copy_m = re.search(r'copyright=([0-9.]+)', raw_title)
    if copy_m:
        result["copyright_score"] = float(copy_m.group(1))

    rel_m = re.search(r'relevance=([0-9.]+)', raw_title)
    if rel_m:
        result["relevance_score"] = float(rel_m.group(1))

    # Supplement from notes (more detailed)
    notes = load_task_notes(task_id)
    for note in notes:
        # "Candidate: Title | URL: ... | copyright=0.95 (reason) | relevance=0.82 (reason)"
        if not result["url"]:
            m = re.search(r'URL:\s*(https?://\S+)', note)
            if m:
                result["url"] = m.group(1).rstrip(".,|")

        if not result["title"]:
            m = re.match(r'Candidate:\s*(.+?)\s*\|', note)
            if m:
                result["title"] = m.group(1).strip()

        m = re.search(r'copyright=([0-9.]+)\s*\(([^)]+)\)', note)
        if m:
            result["copyright_score"] = float(m.group(1))
            result["copyright_reason"] = m.group(2).strip()

        m = re.search(r'relevance=([0-9.]+)\s*\(([^)]+)\)', note)
        if m:
            result["relevance_score"] = float(m.group(1))
            result["relevance_reason"] = m.group(2).strip()

    if not result["url"]:
        result["error"] = "could not parse URL from task title or notes"
    if not result["title"]:
        result["title"] = result["url"] or task_id

    return result


# ── HTML → text extraction ───────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Simple HTML → plain text stripper."""
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "blockquote"}:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse runs of blank lines to double-newlines (paragraph breaks)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def resolve_archive_org_url(url: str) -> str:
    """
    If url is an archive.org/details/{identifier} page, resolve it to the
    best available plain-text download URL using the metadata API.
    Returns the original url unchanged if not an archive.org details link
    or if resolution fails.
    """
    m = re.match(r'https?://archive\.org/details/([^/?#]+)', url)
    if not m:
        return url
    identifier = m.group(1)
    meta_url = f"https://archive.org/metadata/{identifier}/files"
    try:
        req = urllib.request.Request(
            meta_url,
            headers={"User-Agent": "TheGoodProject-Ingestor/1.0 (research; public-domain text ingestion)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return url

    files = data.get("result", [])
    # Prefer: full .txt → _djvu.txt → _abbyy.gz (skip images/zips/pdfs)
    txt_files = [f["name"] for f in files if isinstance(f, dict) and f.get("name", "").endswith(".txt")]
    djvu_files = [f["name"] for f in files if isinstance(f, dict) and f.get("name", "").endswith("_djvu.txt")]
    # Pick shortest name (usually the primary text file, not _meta.txt)
    candidates = [n for n in txt_files if not n.endswith("_meta.txt") and not n.endswith("_files.xml")]
    if not candidates:
        candidates = djvu_files
    if not candidates:
        return url  # fall through — let fetch deal with the HTML page

    best = sorted(candidates, key=len)[0]
    return f"https://archive.org/download/{identifier}/{best}"


def fetch_and_clean(url: str, max_bytes: int = 500_000) -> tuple[str, str]:
    """
    Fetch URL and return (clean_plaintext, error_string).
    error_string is empty on success.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TheGoodProject-Ingestor/1.0 (research; public-domain text ingestion)",
                "Accept": "text/html,text/plain;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_bytes = resp.read(max_bytes)
        # Detect encoding from Content-Type or assume UTF-8
        content_type = resp.headers.get("Content-Type", "")
        enc_m = re.search(r'charset=([^\s;]+)', content_type, re.I)
        encoding = enc_m.group(1).strip('"') if enc_m else "utf-8"
        try:
            raw = raw_bytes.decode(encoding, errors="replace")
        except (LookupError, ValueError):
            raw = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        return "", f"fetch failed: {exc}"

    # If we got plain text (Project Gutenberg .txt, etc.)
    if not raw.lstrip().startswith("<"):
        return raw.strip(), ""

    # Strip HTML
    extractor = _TextExtractor()
    try:
        extractor.feed(raw)
    except Exception:
        pass
    text = extractor.get_text()

    # Strip Gutenberg boilerplate
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG EBOOK",
        "*** START OF THIS PROJECT GUTENBERG EBOOK",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG EBOOK",
        "*** END OF THIS PROJECT GUTENBERG EBOOK",
    ]
    for marker in start_markers:
        if marker in text:
            text = text.split(marker, 1)[1]
            if "\n" in text:
                text = text.split("\n", 1)[1]
            break
    for marker in end_markers:
        if marker in text:
            text = text.split(marker, 1)[0]
            break

    return text.strip(), ""


# ── Group selection ──────────────────────────────────────────────────────────

def select_group(title: str, url: str, text_snippet: str) -> str:
    """
    Return the best-fit source group key for this content.
    Falls back to "gutenberg_lds" if nothing matches clearly.
    """
    combined = (title + " " + url + " " + text_snippet[:2000]).lower()
    for group, keywords in GROUP_KEYWORDS:
        if any(kw in combined for kw in keywords):
            return group
    return "gutenberg_lds"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ── Pipeline runner ──────────────────────────────────────────────────────────

def run_script(script_name: str, *extra_args: str) -> tuple[bool, str]:
    """
    Run a pipeline script (relative to lds_pipeline/).
    Returns (success, combined_output).
    """
    script = PIPELINE_DIR / script_name
    if not script.exists():
        return False, f"script not found: {script}"
    cmd = ["python3", str(script)] + list(extra_args)
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    combined = result.stdout + result.stderr
    success = result.returncode == 0
    return success, combined


# ── Diagnostic report ────────────────────────────────────────────────────────

def write_report(task_id: str, report: dict) -> Path:
    DIAG.mkdir(parents=True, exist_ok=True)
    path = DIAG / f"source-ingestor-{task_id}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Main ingest logic ────────────────────────────────────────────────────────

def ingest(task_id: str, forced_group: Optional[str] = None, dry_run: bool = False,
           url_override: Optional[str] = None) -> int:
    """
    Full ingest pipeline for a single task.
    Returns 0 on success, 1 on error, 2 if routed to human review.
    """
    report: dict = {
        "ts": now_iso(),
        "task_id": task_id,
        "agent": "source-ingestor",
        "dry_run": dry_run,
        "steps": [],
        "outcome": "unknown",
    }

    def step(name: str, ok: bool, detail: str = "") -> None:
        report["steps"].append({"step": name, "ok": ok, "detail": detail[:400] if detail else ""})
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}" + (f": {detail[:120]}" if detail else ""))

    def request_review(reason: str, note: str) -> int:
        print(f"\n  => Routing to human review: {reason}")
        review_title = f"Source ingestor review needed for {task_id}: {reason[:60]}"
        if not dry_run:
            review_id = ledger_ensure(review_title, source="source-ingestor", priority="normal")
            if review_id:
                ledger_note(review_id, f"Original task: {task_id} — {note}")
            ledger_note(task_id, f"REVIEW REQUESTED: {reason} — {note}")
        report["outcome"] = "review_requested"
        report["review_reason"] = reason
        step("request_review", True, reason)
        return 2

    print(f"\n=== Source Ingestor: {task_id} ===")
    if dry_run:
        print("  (DRY RUN — no files written, no ledger mutations)")

    # ── Step 1: Parse task metadata ──────────────────────────────────────────
    print("\n[1] Parsing task metadata...")
    meta = parse_scout_task(task_id)
    if meta.get("error"):
        step("parse_task", False, meta["error"])
        report["outcome"] = "error"
        write_report(task_id, report)
        return 1

    url = url_override or meta["url"]
    title = meta["title"]
    copyright_score = meta["copyright_score"]
    relevance_score = meta["relevance_score"]
    step("parse_task", True, f"title='{title}' url={url} copyright={copyright_score} relevance={relevance_score}")
    report["meta"] = meta

    # ── Step 2: Score gating ─────────────────────────────────────────────────
    print("\n[2] Checking scores...")
    if copyright_score < COPYRIGHT_PASS:
        return request_review(
            f"copyright score {copyright_score:.2f} is below threshold {COPYRIGHT_PASS}",
            f"reason: {meta.get('copyright_reason', 'unknown')}",
        )
    if relevance_score < RELEVANCE_PASS:
        return request_review(
            f"relevance score {relevance_score:.2f} is below threshold {RELEVANCE_PASS}",
            f"reason: {meta.get('relevance_reason', 'unknown')}",
        )
    step("score_gate", True, f"copyright={copyright_score} >= {COPYRIGHT_PASS}, relevance={relevance_score} >= {RELEVANCE_PASS}")

    # ── Step 2b: Resolve archive.org details URL to actual text file ─────────
    resolved_url = resolve_archive_org_url(url)
    if resolved_url != url:
        step("resolve_url", True, f"archive.org → {resolved_url.split('/')[-1]}")
        url = resolved_url

    # ── Step 3: Fetch and clean ──────────────────────────────────────────────
    print(f"\n[3] Fetching {url}...")
    text, fetch_err = fetch_and_clean(url)
    if fetch_err:
        step("fetch", False, fetch_err)
        return request_review(
            "fetch failed",
            f"URL {url} could not be retrieved: {fetch_err}",
        )

    word_count = len(text.split())
    step("fetch", True, f"{word_count} words fetched")
    if word_count < MIN_WORD_COUNT:
        return request_review(
            f"only {word_count} words extracted (minimum {MIN_WORD_COUNT})",
            f"URL {url} returned too little usable text — may need manual download",
        )

    # ── Step 4: Select group ─────────────────────────────────────────────────
    print("\n[4] Selecting source group...")
    group = forced_group or select_group(title, url, text)
    cache_subdir = GROUP_CACHE_MAP.get(group)
    if cache_subdir is None:
        return request_review(
            f"unknown group key '{group}'",
            f"Group '{group}' has no known cache directory mapping",
        )
    step("select_group", True, f"group='{group}' → cache={cache_subdir.relative_to(ROOT)}")
    report["group"] = group

    # ── Step 5: Write text to cache ──────────────────────────────────────────
    slug = slugify(title) or f"ingest_{task_id.lower()}"
    cache_file = cache_subdir / f"{slug}.txt"
    print(f"\n[5] Writing to cache: {cache_file.relative_to(ROOT)}")

    if cache_file.exists():
        return request_review(
            f"cache file already exists: {cache_file.relative_to(ROOT)}",
            "Human should verify whether this is a duplicate or an update",
        )

    if not dry_run:
        cache_subdir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(text, encoding="utf-8")

    step("write_cache", True, f"{cache_file.relative_to(ROOT)} ({word_count} words)")
    report["cache_file"] = str(cache_file.relative_to(ROOT))

    # ── Step 6: Build source library (HTML pages + source_toc.json) ──────────
    print("\n[6] Running build_source_library.py...")
    if not dry_run:
        ok, out = run_script("build_source_library.py")
        step("build_source_library", ok, out[-300:] if out else "")
        if not ok:
            return request_review(
                "build_source_library.py failed",
                out[-400:],
            )
    else:
        step("build_source_library", True, "skipped (dry run)")

    # ── Step 7: Build word indexes for the new group ──────────────────────────
    print(f"\n[7] Running build_source_words.py --groups {group}...")
    if not dry_run:
        ok, out = run_script("build_source_words.py", "--groups", group, "--force")
        step("build_source_words", ok, out[-300:] if out else "")
        if not ok:
            return request_review(
                "build_source_words.py failed",
                out[-400:],
            )
    else:
        step("build_source_words", True, "skipped (dry run)")

    # ── Step 8: Rebuild search index ─────────────────────────────────────────
    print("\n[8] Running build_search_index.py...")
    if not dry_run:
        ok, out = run_script("build_search_index.py")
        step("build_search_index", ok, out[-300:] if out else "")
        if not ok:
            # Non-fatal: search index can be rebuilt later
            step("build_search_index_warn", False, "continuing despite search index error")
    else:
        step("build_search_index", True, "skipped (dry run)")

    # ── Step 9: Rebuild source dashboard ─────────────────────────────────────
    print("\n[9] Running build_source_dashboard.py...")
    if not dry_run:
        ok, out = run_script("build_source_dashboard.py")
        step("build_source_dashboard", ok, out[-200:] if out else "")
    else:
        step("build_source_dashboard", True, "skipped (dry run)")

    # ── Step 10: Create review task (human gate before correlate_embeddings) ──
    review_title = (
        f"Source ingestor: review '{title}' before running correlate_embeddings "
        f"— group={group}, task={task_id}"
    )
    print(f"\n[10] Creating review task for embedding correlation...")
    review_note = textwrap.dedent(f"""
        Source '{title}' has been ingested and appears in the library.
        Cache file: {cache_file.relative_to(ROOT) if not dry_run else '(dry run)'}
        Group: {group}
        URL: {url}
        Copyright: {copyright_score} ({meta.get('copyright_reason', '')})
        Relevance: {relevance_score} ({meta.get('relevance_reason', '')})

        To complete semantic integration, run:
          cd {ROOT}
          python3 lds_pipeline/correlate_embeddings.py --rebuild

        This is expensive (~5–10 min CPU). Verify the source content first.
    """).strip()

    if not dry_run:
        review_id = ledger_ensure(review_title, source="source-ingestor", priority="normal")
        if review_id:
            ledger_note(review_id, review_note)
        step("create_review_task", bool(review_id), review_id or "task creation failed")
        report["review_task_id"] = review_id
    else:
        step("create_review_task", True, "skipped (dry run)")

    # ── Step 11: Complete original task ──────────────────────────────────────
    summary = (
        f"Ingested '{title}' → {group} (copyright={copyright_score}, relevance={relevance_score}). "
        f"Library updated. Correlation pending human review."
    )
    if not dry_run:
        ledger_note(task_id, f"INGESTED: {summary}")
        ledger_complete(task_id, summary)
        step("complete_task", True, summary[:100])
    else:
        step("complete_task", True, "skipped (dry run)")

    report["outcome"] = "success" if not dry_run else "dry_run_success"

    # ── Write diagnostic report ───────────────────────────────────────────────
    report_path = write_report(task_id, report)
    print(f"\n  Report: {report_path.relative_to(ROOT)}")

    print(f"\n=== Done: {report['outcome']} ===")
    _print_summary(report)
    return 0


def _print_summary(report: dict) -> None:
    meta = report.get("meta", {})
    steps_ok = sum(1 for s in report["steps"] if s["ok"])
    steps_total = len(report["steps"])
    print(f"""
Summary:
  Task:      {report['task_id']}
  Title:     {meta.get('title', '')}
  URL:       {meta.get('url', '')}
  Group:     {report.get('group', 'n/a')}
  Cache:     {report.get('cache_file', 'n/a')}
  Steps:     {steps_ok}/{steps_total} OK
  Outcome:   {report['outcome']}
  Review ID: {report.get('review_task_id', 'n/a')}
""")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a Source Scout ledger task into the library pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python3 source_ingestor.py --task-id T-0088
              python3 source_ingestor.py --task-id T-0088 --dry-run
              python3 source_ingestor.py --task-id T-0088 --group pseudepigrapha
        """),
    )
    parser.add_argument(
        "--task-id", required=True,
        help="Ledger task ID to ingest (e.g. T-0088)",
    )
    parser.add_argument(
        "--group",
        choices=list(GROUP_CACHE_MAP.keys()),
        default=None,
        help="Force a specific source group (default: auto-detected from content)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and validate but do not write files or mutate the ledger",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Override the URL from the task (useful when the scout found a restricted scan)",
    )
    args = parser.parse_args()

    try:
        return ingest(args.task_id, forced_group=args.group, dry_run=args.dry_run, url_override=args.url)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 1
    except Exception:
        print(f"\nUnhandled error:\n{traceback.format_exc()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
