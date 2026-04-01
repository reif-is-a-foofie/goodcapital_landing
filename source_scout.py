#!/usr/bin/env python3
"""
Every-four-hours source scout runner.

Searches the web for public-domain or open-licensed texts relevant to scripture
study, evaluates copyright status and semantic fit, and — when both pass —
proposes the candidate as a ledger task for human or agent review.

Never auto-ingests. The ledger task is the handoff.
"""

from __future__ import annotations

import json
import subprocess
import sys
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DIAG = ROOT / "diagnostics"
REPORT = DIAG / "source-scout-latest.json"
TXT = DIAG / "source-scout-latest.txt"
LEDGER = ROOT / "task_ledger.py"
MISSION = ROOT / "AGENT_MISSION.md"
PROFILE = ROOT / "agents" / "source_scout_profile.md"
DASHBOARD_JSON = ROOT / "library" / "source-dashboard.json"

# Copyright and relevance thresholds
COPYRIGHT_PASS = 0.7   # minimum copyright confidence score (0–1)
RELEVANCE_PASS = 0.5   # minimum semantic relevance score (0–1)

# Trusted archive domains that signal public domain
TRUSTED_DOMAINS = {
    "gutenberg.org",
    "archive.org",
    "ccel.org",
    "sacred-texts.com",
    "earlychristianwritings.com",
    "gnosis.org",
    "ecmarsh.com",
    "tertullian.org",
    "newadvent.org",
}

# Archive.org subject/keyword queries for each gap in the corpus.
# These are used by both the Archive.org backend (keyword search) and
# the Brave backend (full web search).  Keep them specific enough to
# surface primary source texts rather than study guides.
SEARCH_QUERIES = [
    "Bhagavad Gita public domain English translation",
    "Dhammapada Buddhist scripture public domain translation",
    "Tao Te Ching public domain English translation",
    "Upanishads public domain English translation Müller",
    "Quran public domain English translation Sale Rodwell",
    "pseudepigrapha ancient Jewish texts public domain scripture",
    "Nag Hammadi Gnostic texts public domain translation",
    "Philo of Alexandria works public domain English translation",
    "Midrash rabbinic commentary public domain English translation",
    "Plotinus Enneads public domain English translation",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_dashboard() -> list[dict]:
    if not DASHBOARD_JSON.exists():
        return []
    try:
        payload = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
        return payload.get("collections", [])
    except Exception:
        return []


def ensure_task(title: str, source: str, priority: str = "normal") -> str:
    """Add a ledger task if one with this title does not already exist. Returns task_id."""
    try:
        proc = subprocess.run(
            [
                "python3", str(LEDGER),
                "ensure", title,
                "--source", source,
                "--priority", priority,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(proc.stdout or "{}")
        return str(payload.get("task_id") or "")
    except Exception:
        return ""


def note_task(task_id: str, note: str) -> None:
    if not task_id:
        return
    try:
        subprocess.run(
            [
                "python3", str(LEDGER),
                "note", task_id,
                "--agent", "SourceScout",
                "--note", note,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


def fetch_page_snippet(url: str, max_bytes: int = 8000) -> str:
    """
    Fetch the first max_bytes of a URL as text.
    Returns empty string on any network or encoding error.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TheGoodProject-SourceScout/1.0 (research; public domain text discovery)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(max_bytes)
        # Try UTF-8 first, fall back to latin-1
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return raw.decode("latin-1", errors="replace")
    except Exception:
        return ""


def score_copyright(url: str, snippet: str) -> tuple[float, str]:
    """
    Return (score 0–1, reason) for copyright confidence.

    Rules:
      1.0 — URL is on a trusted archive domain
      0.9 — snippet contains explicit "public domain" declaration
      0.85 — snippet contains CC0 / CC-BY license text
      0.8  — snippet mentions publication date clearly before 1928
      0.3  — snippet mentions "copyright" without a clear PD declaration
      0.1  — no useful signal found
    """
    url_lower = url.lower()
    snippet_lower = snippet.lower()

    # Trusted domains: presume public domain by policy
    for domain in TRUSTED_DOMAINS:
        if domain in url_lower:
            return 1.0, f"trusted archive domain ({domain})"

    # Explicit public domain statement
    if "public domain" in snippet_lower:
        return 0.9, "page declares public domain"

    # Creative Commons open licenses
    if "cc0" in snippet_lower or "creativecommons.org/licenses/by/" in snippet_lower:
        return 0.85, "Creative Commons license found"

    # Look for pre-1928 publication date
    import re
    years = re.findall(r'\b(1[0-9]{3})\b', snippet)
    pub_years = [int(y) for y in years if int(y) <= 1927]
    if pub_years:
        earliest = min(pub_years)
        return 0.8, f"publication year {earliest} is pre-1928 (US public domain)"

    # Copyright marker without PD claim
    if "copyright" in snippet_lower or "©" in snippet:
        return 0.3, "page shows copyright marker without public domain declaration"

    return 0.1, "no copyright status signals found"


def score_relevance(title: str, snippet: str, collections: list[dict]) -> tuple[float, str]:
    """
    Return (score 0–1, reason) for semantic relevance to the existing corpus.

    Uses simple keyword overlap against collection labels and known source
    categories. A full embedding comparison is left for the ingest pipeline;
    this is a lightweight gate check.
    """
    existing_labels = " ".join(c.get("label", "") for c in collections).lower()
    existing_ids = " ".join(c.get("id", "") for c in collections).lower()

    # High-value keywords for this corpus — both Abrahamic and cross-tradition
    HIGH_VALUE = [
        # Abrahamic / LDS
        "scripture", "bible", "testament", "enoch", "apocrypha", "pseudepigrapha",
        "nag hammadi", "dead sea scrolls", "midrash", "talmud", "targum", "mishnah",
        "church fathers", "origen", "clement", "irenaeus", "tertullian", "justin martyr",
        "josephus", "philo", "early christian", "gnostic", "restoration", "joseph smith",
        "theological", "covenant", "atonement", "resurrection", "creation", "flood",
        "ancient near east", "ugaritic", "biblical", "hebrew", "greek testament",
        "septuagint", "lxx", "vulgate", "dead sea", "qumran",
        # Hindu / Vedic
        "bhagavad gita", "upanishads", "vedanta", "veda", "vedic", "brahman",
        "atman", "dharma", "karma", "yoga", "sanskrit", "mahabharata", "ramayana",
        "puranas", "bhagavata", "vishnu", "shiva", "brahma", "krishna", "arjuna",
        # Buddhist
        "dhammapada", "buddhist", "buddhism", "pali canon", "suttas", "nirvana",
        "eightfold path", "four noble truths", "theravada", "mahayana", "zen",
        "lotus sutra", "diamond sutra", "heart sutra",
        # Taoist / Chinese
        "tao te ching", "taoism", "taoist", "confucius", "analects", "i ching",
        "lao tzu", "chuang tzu", "wu wei",
        # Sufi / Islamic mysticism
        "sufi", "sufism", "rumi", "hafiz", "quran", "koran", "islam", "islamic",
        "al-ghazali", "ibn arabi",
        # Ancient / Hermetic
        "hermetica", "hermeticism", "plotinus", "neoplatonism", "enneads",
        "plato", "platonic", "mystery", "mysticism", "mystical",
        # General spiritual
        "spiritual", "wisdom", "enlightenment", "meditation", "sacred", "holy",
        "eternal", "divine", "soul", "spirit", "prayer", "revelation",
    ]

    text = (title + " " + snippet).lower()
    matched = [kw for kw in HIGH_VALUE if kw in text]

    if not matched:
        return 0.1, "no relevant keywords found in title or page snippet"

    # Penalty if it duplicates an existing collection too closely
    for coll_id in existing_ids.split():
        if coll_id in text and len(coll_id) > 6:
            # Likely in a well-covered area — reduce score slightly
            score = min(0.6, 0.3 + 0.05 * len(matched))
            return score, f"relevant ({len(matched)} keyword hits) but overlaps existing collection '{coll_id}'"

    score = min(0.95, 0.4 + 0.06 * len(matched))
    return score, f"relevant — {len(matched)} keyword matches: {', '.join(matched[:6])}"


def _search_archive_org(query: str) -> list[dict]:
    """
    Search Internet Archive for public-domain texts matching query.
    Free, no API key required.
    Returns list of dicts with keys: title, url, snippet.
    """
    import urllib.parse

    # mediatype filter must live inside the query string, not as a separate param
    full_query = f"{query} AND mediatype:texts"
    params = urllib.parse.urlencode({"q": full_query, "output": "json", "rows": "5"})
    api_url = (
        f"https://archive.org/advancedsearch.php?{params}"
        "&fl[]=identifier&fl[]=title&fl[]=description&fl[]=subject"
    )
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": "TheGoodProject-SourceScout/1.0 (research; public domain text discovery)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return [{"_error": f"archive.org API error: {exc}"}]

    docs = data.get("response", {}).get("docs", [])
    results = []
    for doc in docs:
        identifier = doc.get("identifier", "")
        if not identifier:
            continue
        title = doc.get("title", identifier)
        if isinstance(title, list):
            title = title[0] if title else identifier
        desc = doc.get("description", "")
        if isinstance(desc, list):
            desc = " ".join(desc)
        subj = doc.get("subject", [])
        if isinstance(subj, list):
            subj = ", ".join(subj[:4])
        snippet = (desc[:200] + " | " + subj).strip(" |")
        url = f"https://archive.org/details/{identifier}"
        results.append({"title": str(title), "url": url, "snippet": snippet})
    return results


def _search_brave(query: str, api_key: str) -> list[dict]:
    """
    Brave Search API (free tier: 2,000 queries/month, no credit card).
    Get a free key at https://api.search.brave.com
    Returns list of dicts with keys: title, url, snippet.
    """
    import urllib.parse

    params = urllib.parse.urlencode({"q": query, "count": "5"})
    api_url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            # Handle gzip if returned
            try:
                import gzip as _gzip
                raw = _gzip.decompress(raw)
            except Exception:
                pass
            data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        return [{"_error": f"Brave API error: {exc}"}]

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", ""),
        })
    return results


def run_web_search(query: str) -> list[dict]:
    """
    Search for public-domain text candidates.

    Backend priority:
      1. Brave Search API  — if BRAVE_API_KEY env var is set
                             (free tier, get key at api.search.brave.com)
      2. Internet Archive  — always available, no key required
    Returns list of dicts with keys: title, url, snippet.
    """
    import os
    brave_key = os.environ.get("BRAVE_API_KEY", "").strip()
    if brave_key:
        results = _search_brave(query, brave_key)
        # Fall through to Archive.org if Brave returned an error
        if results and "_error" not in results[0]:
            return results

    return _search_archive_org(query)


def evaluate_candidate(title: str, url: str, snippet_from_search: str, collections: list[dict]) -> dict:
    """
    Fetch the page, score copyright and relevance, return a full evaluation dict.
    """
    result = {
        "title": title,
        "url": url,
        "search_snippet": snippet_from_search,
        "page_snippet": "",
        "copyright_score": 0.0,
        "copyright_reason": "",
        "relevance_score": 0.0,
        "relevance_reason": "",
        "passes": False,
        "task_title": "",
        "error": "",
    }

    # Fetch a page snippet for deeper evaluation
    try:
        page = fetch_page_snippet(url)
        result["page_snippet"] = page[:500]
    except Exception as exc:
        result["error"] = f"fetch failed: {exc}"
        page = snippet_from_search

    # Score copyright
    combined_text = snippet_from_search + " " + page
    c_score, c_reason = score_copyright(url, combined_text)
    result["copyright_score"] = round(c_score, 3)
    result["copyright_reason"] = c_reason

    # Score relevance
    r_score, r_reason = score_relevance(title, combined_text, collections)
    result["relevance_score"] = round(r_score, 3)
    result["relevance_reason"] = r_reason

    # Pass if both thresholds met
    passes = c_score >= COPYRIGHT_PASS and r_score >= RELEVANCE_PASS
    result["passes"] = passes

    if passes:
        result["task_title"] = (
            f"Source Scout: ingest '{title}' — "
            f"copyright={c_score:.2f} ({c_reason}), "
            f"relevance={r_score:.2f} ({r_reason}) — "
            f"URL: {url}"
        )

    return result


def main() -> int:
    DIAG.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "ts": now_iso(),
        "agent": "SourceScout",
        "mission_path": str(MISSION.relative_to(ROOT)),
        "profile_path": str(PROFILE.relative_to(ROOT)),
        "mission": read_text(MISSION),
        "profile": read_text(PROFILE),
        "queries_run": [],
        "candidates_found": 0,
        "candidates_evaluated": 0,
        "candidates_passed": 0,
        "tasks_created": [],
        "rejections": [],
        "errors": [],
    }

    lines = [f"Source scout run: {report['ts']}"]
    lines.append(f"Mission: {report['mission_path']}")
    lines.append(f"Profile: {report['profile_path']}")

    collections = load_dashboard()
    lines.append(f"Existing collections: {len(collections)}")

    seen_urls: set[str] = set()

    for query in SEARCH_QUERIES:
        report["queries_run"].append(query)
        lines.append(f"\nQuery: {query[:80]}")

        raw_results = []
        try:
            raw_results = run_web_search(query)
        except Exception as exc:
            err = f"search error for query '{query[:60]}': {exc}"
            report["errors"].append(err)
            lines.append(f"  ERROR: {err}")
            continue

        if not raw_results:
            lines.append("  no results returned")
            continue

        for item in raw_results:
            if "_error" in item:
                err = f"search API error: {item['_error']}"
                report["errors"].append(err)
                lines.append(f"  ERROR: {err}")
                continue

            url = item.get("url", "").strip()
            title = item.get("title", url).strip()
            snippet = item.get("snippet", "").strip()

            if not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            report["candidates_found"] += 1

            try:
                ev = evaluate_candidate(title, url, snippet, collections)
            except Exception as exc:
                err = f"evaluation error for {url}: {traceback.format_exc()}"
                report["errors"].append(err)
                lines.append(f"  ERROR evaluating {url}: {exc}")
                continue

            report["candidates_evaluated"] += 1

            if ev["passes"]:
                report["candidates_passed"] += 1
                task_id = ensure_task(
                    ev["task_title"],
                    source="source_scout",
                    priority="normal",
                )
                note = (
                    f"Candidate: {title} | URL: {url} | "
                    f"copyright={ev['copyright_score']} ({ev['copyright_reason']}) | "
                    f"relevance={ev['relevance_score']} ({ev['relevance_reason']})"
                )
                if task_id:
                    note_task(task_id, note)
                report["tasks_created"].append({
                    "task_id": task_id,
                    "title": title,
                    "url": url,
                    "copyright_score": ev["copyright_score"],
                    "copyright_reason": ev["copyright_reason"],
                    "relevance_score": ev["relevance_score"],
                    "relevance_reason": ev["relevance_reason"],
                })
                lines.append(f"  PASS  {title}")
                lines.append(f"        copyright={ev['copyright_score']} — {ev['copyright_reason']}")
                lines.append(f"        relevance={ev['relevance_score']} — {ev['relevance_reason']}")
                lines.append(f"        task: {task_id}")
            else:
                rejection = {
                    "title": title,
                    "url": url,
                    "copyright_score": ev["copyright_score"],
                    "copyright_reason": ev["copyright_reason"],
                    "relevance_score": ev["relevance_score"],
                    "relevance_reason": ev["relevance_reason"],
                    "error": ev.get("error", ""),
                }
                report["rejections"].append(rejection)
                lines.append(f"  SKIP  {title}")
                if ev["copyright_score"] < COPYRIGHT_PASS:
                    lines.append(f"        copyright fail ({ev['copyright_score']:.2f}): {ev['copyright_reason']}")
                if ev["relevance_score"] < RELEVANCE_PASS:
                    lines.append(f"        relevance fail ({ev['relevance_score']:.2f}): {ev['relevance_reason']}")

    # Summary
    lines.append(
        f"\nSummary: queries={len(report['queries_run'])} "
        f"found={report['candidates_found']} "
        f"evaluated={report['candidates_evaluated']} "
        f"passed={report['candidates_passed']} "
        f"tasks_created={len(report['tasks_created'])}"
    )
    if report["errors"]:
        lines.append(f"Errors: {len(report['errors'])}")

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "agent": "SourceScout",
        "candidates_passed": report["candidates_passed"],
        "tasks_created": len(report["tasks_created"]),
        "errors": len(report["errors"]),
        "report": str(REPORT.relative_to(ROOT)),
    }, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
