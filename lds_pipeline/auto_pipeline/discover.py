"""
Source discovery: uses Claude to suggest new scholarly sources,
then checks availability and adds candidates to the queue.

Run:
    python3 -m auto_pipeline.discover [--dry-run] [--n 10]
"""
import argparse
import json
import re
import time
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from datetime import datetime

import anthropic

QUEUE_FILE = Path(__file__).parent / 'source_queue.json'
PIPELINE_ROOT = Path(__file__).parent.parent

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LDS-pipeline/1.0)"}

# ── What's already in the corpus ─────────────────────────────────────────────

EXISTING_SOURCES = [
    "KJV Bible (all books)", "Book of Mormon", "Doctrine & Covenants",
    "Pearl of Great Price", "Journal of Discourses (26 vols)",
    "History of the Church (7 vols)", "Joseph Smith Papers",
    "General Conference talks 1971–present", "Millennial Star",
    "Times and Seasons", "Lee Donaldson commentary",
    "B.H. Roberts – Studies of the Book of Mormon",
    "Pseudepigrapha (R.H. Charles, 1913)", "LXX Apocrypha (Deuterocanonical)",
    "Nag Hammadi library", "Dead Sea Scrolls (public domain translations)",
    "Nauvoo theology: King Follett Discourse, Plurality of Gods sermons",
    "Strong's Hebrew & Greek Concordance",
    "Sefaria: Rashi, Talmud links, Midrash references",
    "McConkie – Mormon Doctrine",
    "Ancient myths (Enuma Elish, Epic of Gilgamesh, Egyptian Book of the Dead)",
    "Church Fathers excerpts",
]

DISCOVERY_PROMPT = """You are a research librarian helping build an LDS scripture annotation corpus.

The corpus already contains:
{existing}

Your task: suggest {n} additional scholarly works that would genuinely enrich this corpus.
Focus on works that:
1. Are either in the public domain OR freely available online (sacred-texts.com, Gutenberg, BYU, FAIR, archive.org open access)
2. Have verse-level or passage-level relevance to LDS scripture topics
3. Add perspectives NOT already covered: early Christianity, Jewish antiquity, Restoration history, biblical scholarship, ancient Near East, typology, comparative religion
4. Include Hugh Nibley works that are freely available (Maxwell Institute, BYU open access)

For each suggestion output a JSON object on its own line:
{{"title": "...", "author": "...", "year": ..., "why": "one sentence", "url_hint": "best URL or archive.org id or 'gutenberg' or 'sacred-texts'", "domain": "early_christianity|jewish|lds_history|biblical_scholarship|ancient_near_east|nibley|restoration"}}

Output ONLY the JSON lines, no other text.
"""

# ── Known free-text patterns for availability check ──────────────────────────

def check_url(url: str, timeout: int = 8) -> bool:
    """Return True if URL is reachable and returns text content."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return r.status == 200
    except Exception:
        return False


def check_archive_open(identifier: str) -> bool:
    """Return True if an archive.org item is NOT restricted."""
    try:
        url = f"https://archive.org/metadata/{identifier}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as r:
            meta = json.loads(r.read())
        access = meta.get("metadata", {}).get("access-restricted-item", "false")
        return str(access).lower() != "true"
    except Exception:
        return False


def resolve_availability(hint: str) -> dict:
    """
    Given a url_hint, determine fetch_type and resolved_url.
    Returns {"fetch_type": ..., "url": ..., "available": bool}
    """
    hint = hint.strip()

    if hint.startswith("http"):
        ok = check_url(hint)
        return {"fetch_type": "http", "url": hint, "available": ok}

    if hint == "gutenberg":
        return {"fetch_type": "gutenberg_search", "url": hint, "available": True}

    if hint == "sacred-texts":
        return {"fetch_type": "sacred_texts_search", "url": hint, "available": True}

    # Assume archive.org identifier
    open_access = check_archive_open(hint)
    return {
        "fetch_type": "archive_open" if open_access else "archive_restricted",
        "url": f"https://archive.org/details/{hint}",
        "identifier": hint,
        "available": open_access,
    }


# ── Queue helpers ─────────────────────────────────────────────────────────────

def load_queue() -> dict:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"candidates": [], "approved": [], "downloading": [],
            "ready": [], "rejected": [], "in_corpus": []}


def save_queue(q: dict):
    QUEUE_FILE.write_text(json.dumps(q, indent=2, ensure_ascii=False))


def already_known(q: dict, title: str) -> bool:
    title_lc = title.lower()
    for section in q.values():
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict) and item.get("title", "").lower() == title_lc:
                    return True
    return False


# ── Main discovery ────────────────────────────────────────────────────────────

def discover(n: int = 12, dry_run: bool = False):
    client = anthropic.Anthropic()
    q = load_queue()

    existing_str = "\n".join(f"  • {s}" for s in EXISTING_SOURCES)
    prompt = DISCOVERY_PROMPT.format(existing=existing_str, n=n)

    print(f"Asking Claude for {n} source suggestions…")
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    suggestions = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            s = json.loads(line)
            suggestions.append(s)
        except json.JSONDecodeError:
            pass

    print(f"Got {len(suggestions)} suggestions. Checking availability…")
    added = 0

    for s in suggestions:
        title = s.get("title", "")
        if already_known(q, title):
            print(f"  skip (known): {title}")
            continue

        avail = resolve_availability(s.get("url_hint", ""))
        time.sleep(0.3)

        candidate = {
            "title": title,
            "author": s.get("author", ""),
            "year": s.get("year"),
            "why": s.get("why", ""),
            "domain": s.get("domain", ""),
            "fetch_type": avail["fetch_type"],
            "url": avail["url"],
            "identifier": avail.get("identifier", ""),
            "available": avail["available"],
            "discovered": datetime.utcnow().isoformat(),
            "status": "candidate",
        }

        status = "✓" if avail["available"] else "✗"
        print(f"  {status} {title} [{avail['fetch_type']}]")

        if dry_run:
            continue

        if avail["available"]:
            q["candidates"].append(candidate)
        else:
            q["rejected"].append({**candidate, "reject_reason": "not_available"})
        added += 1

    if not dry_run:
        save_queue(q)
        print(f"\nAdded {added} candidates to queue → {QUEUE_FILE}")
    else:
        print(f"\n[dry-run] Would have added {added} candidates")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    discover(n=args.n, dry_run=args.dry_run)
