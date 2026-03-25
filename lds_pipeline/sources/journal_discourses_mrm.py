"""
Journal of Discourses — 26 volumes via jod.mrm.org

Uses the Gatsby page-data JSON API which returns clean structured discourse text.
No scraping — just JSON endpoints.

URL pattern: https://jod.mrm.org/page-data/{vol}/{discourse}/page-data.json
Each volume has a different number of discourses (check index page).
"""

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/jd")
BASE_URL = "https://jod.mrm.org/page-data/{vol}/{discourse}/page-data.json"
INDEX_URL = "https://jod.mrm.org/page-data/{vol}/page-data.json"

# Known discourse counts per volume (from jod.mrm.org)
# Approximate — fetcher stops when it gets 404
MAX_DISCOURSES_PER_VOL = 50


def _strip_html(s: str) -> str:
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _fetch_json(url: str) -> Optional[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        if "404" not in str(e):
            print(f"  JD fetch error ({url}): {e}")
        return None


def extract_discourse_text(data: dict) -> Optional[str]:
    """Extract plain text from mrm.org page-data JSON."""
    try:
        ctx = data["result"]["pageContext"]["discourse"]
    except (KeyError, TypeError):
        return None

    parts = []
    speaker = ctx.get("speaker", "")
    date = ctx.get("date", "")[:10] if ctx.get("date") else ""
    title = _strip_html(ctx.get("subtitle", "") or ctx.get("title", ""))

    if speaker:
        parts.append(f"[{speaker}, {date}] {title}")

    for col_item in ctx.get("content", []):
        for col in col_item.get("columns", []):
            text = _strip_html(str(col))
            if text:
                parts.append(text)

    return "\n\n".join(parts) if parts else None


def get_volume_discourse_pages(vol_num: int) -> list[int]:
    """Fetch the list of start_page values for a volume from the index."""
    url = INDEX_URL.format(vol=vol_num)
    data = _fetch_json(url)
    if not data:
        return []
    try:
        discourses = data["result"]["pageContext"]["discourses"]
        return [d["start_page"] for d in discourses]
    except (KeyError, TypeError):
        return []


def download_volume(vol_num: int, force: bool = False) -> Optional[str]:
    """Download all discourses for a volume, return combined text."""
    cache_file = CACHE_DIR / f"vol_{vol_num:02d}.txt"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force and cache_file.exists() and cache_file.stat().st_size > 1000:
        return cache_file.read_text(encoding="utf-8")

    print(f"  JD Vol {vol_num}: fetching index...", flush=True)
    pages = get_volume_discourse_pages(vol_num)
    if not pages:
        print(f"  JD Vol {vol_num}: no index found")
        return None

    print(f"  JD Vol {vol_num}: {len(pages)} discourses, downloading...", flush=True)
    all_texts = []

    for start_page in pages:
        url = BASE_URL.format(vol=vol_num, discourse=start_page)
        data = _fetch_json(url)
        if data is None:
            continue
        text = extract_discourse_text(data)
        if text:
            all_texts.append(text)
        time.sleep(0.15)  # polite rate limiting

    if not all_texts:
        print(f"  JD Vol {vol_num}: no text extracted")
        return None

    combined = "\n\n\n".join(all_texts)
    cache_file.write_text(combined, encoding="utf-8")
    print(f"  JD Vol {vol_num}: {len(all_texts)} discourses, {len(combined):,} chars cached")
    return combined


def download_all_volumes(vol_range: range = range(1, 27)) -> dict[int, str]:
    """Download all 26 JD volumes. Returns {vol_num: text}."""
    result = {}
    for vol_num in vol_range:
        # Skip if already cached
        cache_file = CACHE_DIR / f"vol_{vol_num:02d}.txt"
        if cache_file.exists() and cache_file.stat().st_size > 1000:
            result[vol_num] = cache_file.read_text(encoding="utf-8")
            print(f"  JD Vol {vol_num}: using cache ({cache_file.stat().st_size:,} bytes)")
            continue

        text = download_volume(vol_num)
        if text:
            result[vol_num] = text

    return result


if __name__ == "__main__":
    import sys
    vols = [int(v) for v in sys.argv[1:]] if len(sys.argv) > 1 else list(range(1, 27))
    print(f"Downloading JD volumes: {vols}")
    texts = download_all_volumes(vols)
    print(f"\nDone: {len(texts)} volumes downloaded")
