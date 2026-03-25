"""
Sync additional scholarly sources for the LDS corpus pipeline.

Groups:
  pseudepigrapha   — 1 Enoch, Jubilees, Testaments of XII Patriarchs (sacred-texts.com)
  apocrypha        — LXX Apocrypha: Tobit, Judith, Sirach, Wisdom, Maccabees,
                     2 Baruch, 4 Ezra (sacred-texts.com)
  nag_hammadi      — Gnostic gospels: Thomas, Philip, Apocryphon of John,
                     Gospel of Truth, etc. (gnosis.org)
  dead_sea_scrolls — Community Rule (1QS), War Scroll, Damascus Document,
                     Thanksgiving Hymns (sacred-texts.com)
  bh_roberts       — Studies of the Book of Mormon (archive.org)
  nibley           — An Approach to the Book of Mormon; Since Cumorah (archive.org)
  nauvoo_theology  — King Follett Discourse, Plurality of Gods sermons,
                     Lorenzo Snow on deification
  jst              — Joseph Smith Translation / Inspired Version
                     (sacred-texts.com + centerplace.org)

Run:
  python3 sync_extra_sources.py [--rebuild] [--group <group_name>]
"""

import argparse
import json
import re
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

try:
    import internetarchive as _ia
    _IA_AVAILABLE = True
except ImportError:
    _IA_AVAILABLE = False

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

SSL_UNVERIFIED = ssl.create_default_context()
SSL_UNVERIFIED.check_hostname = False
SSL_UNVERIFIED.verify_mode = ssl.CERT_NONE


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_url(url: str, timeout: int = 90, ssl_ctx=None) -> str:
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    ctx = ssl_ctx or ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def fetch_url_unverified(url: str, timeout: int = 90) -> str:
    """Fetch ignoring SSL cert errors (for gnosis.org self-signed cert)."""
    return fetch_url(url, timeout=timeout, ssl_ctx=SSL_UNVERIFIED)


def fetch_archive_djvu_verified(identifier: str, timeout: int = 180) -> str:
    """
    Look up the correct djvu filename via archive.org metadata API,
    then fetch it. Retries once on 503.
    """
    meta_url = f"https://archive.org/metadata/{identifier}"
    print(f"    Checking metadata: {meta_url}", flush=True)
    try:
        meta = json.loads(fetch_url(meta_url, timeout=30))
    except Exception as e:
        raise RuntimeError(f"metadata lookup failed: {e}")

    files = meta.get("files", [])
    djvu_files = [f["name"] for f in files if f["name"].endswith("_djvu.txt")]
    if not djvu_files:
        raise RuntimeError(f"no _djvu.txt in {identifier}; files: {[f['name'] for f in files[:10]]}")

    filename = djvu_files[0]
    url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(filename)}"
    print(f"    Fetching {url}", flush=True)

    for attempt in range(3):
        try:
            return fetch_url(url, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"    503 — retrying in {wait}s…", flush=True)
                time.sleep(wait)
            else:
                raise


def strip_html(html: str) -> str:
    html = re.sub(r'<(script|style|nav|footer|header)[^>]*>.*?</\1>', '',
                  html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    for ent, ch in [
        ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&nbsp;', ' '),
        ('&#39;', "'"), ('&quot;', '"'), ('&mdash;', '—'), ('&ndash;', '–'),
        ('&ldquo;', '"'), ('&rdquo;', '"'), ('&lsquo;', "'"), ('&rsquo;', "'"),
        ('&hellip;', '…'),
    ]:
        html = html.replace(ent, ch)
    html = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), html)
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


def save(dir_path: Path, filename: str, text: str, rebuild: bool = False) -> bool:
    """Save text to file. Returns True if written, False if skipped."""
    dir_path.mkdir(parents=True, exist_ok=True)
    out = dir_path / filename
    if not rebuild and out.exists() and out.stat().st_size > 5_000:
        print(f"    Cached: {filename} ({out.stat().st_size / 1024:.0f} KB)")
        return False
    out.write_text(text, encoding="utf-8")
    print(f"    Saved:  {filename} ({out.stat().st_size / 1024:.0f} KB)")
    return True


def scrape_sacred_texts(index_url: str, base_url: str, label: str) -> str:
    """
    Fetch a multi-chapter book from sacred-texts.com.
    Crawls chapter links found on the index page.
    """
    print(f"    Index: {index_url}")
    try:
        index_html = fetch_url(index_url)
    except Exception as e:
        print(f"    ERROR fetching index: {e}")
        return ""

    links = re.findall(r'href=["\']([^"\'#?]+\.htm[l]?)["\']', index_html, re.IGNORECASE)
    seen, chapters = set(), []
    for lnk in links:
        if lnk.startswith('http') or lnk.startswith('//'):
            continue
        lnk_lower = lnk.lower()
        if lnk_lower in seen or lnk_lower in ('index.htm', 'index.html'):
            continue
        seen.add(lnk_lower)
        chapters.append(lnk)

    if not chapters:
        print(f"    No sub-pages found; using index page as full text")
        return strip_html(index_html)

    print(f"    Fetching {len(chapters)} chapters…", flush=True)
    parts = []
    for i, lnk in enumerate(chapters, 1):
        url = base_url.rstrip('/') + '/' + lnk.lstrip('/')
        try:
            parts.append(strip_html(fetch_url(url)))
            if i % 20 == 0:
                print(f"    … {i}/{len(chapters)}", flush=True)
            time.sleep(0.4)
        except Exception as e:
            print(f"    SKIP {lnk}: {e}")

    return "\n\n" + "=" * 60 + "\n\n".join(parts)


def fetch_archive_djvu(identifier: str, filename: str = "") -> str:
    if filename:
        url = f"https://archive.org/download/{identifier}/{filename}"
        print(f"    Fetching {url}", flush=True)
        return fetch_url(url, timeout=180)
    return fetch_archive_djvu_verified(identifier)


def _get_chrome_archive_cookies() -> str:
    """Extract archive.org session cookies from Chrome's cookie database."""
    import sqlite3, shutil, tempfile, hashlib, subprocess
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        return ""
    result = subprocess.run(
        ['security', 'find-generic-password', '-w', '-s', 'Chrome Safe Storage', '-a', 'Chrome'],
        capture_output=True
    )
    if result.returncode != 0:
        return ""
    chrome_pass = result.stdout.strip()
    key = hashlib.pbkdf2_hmac("sha1", chrome_pass, b"saltysalt", 1003, 16)

    def decrypt(enc_value: bytes) -> str:
        if enc_value[:3] == b"v10":
            enc_value = enc_value[3:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend())
        dec = cipher.decryptor()
        pt = dec.update(enc_value) + dec.finalize()
        pt = pt[32:]  # skip 32-byte Chrome artifact prefix
        pad_len = pt[-1] if pt else 0
        if 1 <= pad_len <= 16:
            pt = pt[:-pad_len]
        return pt.decode("utf-8", errors="replace").strip()

    db_path = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
    if not db_path.exists():
        return ""
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(db_path), tmp)
    try:
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        cur.execute("""
            SELECT name, encrypted_value FROM cookies
            WHERE host_key LIKE '%archive.org%'
        """)
        cookies = {name: decrypt(enc) for name, enc in cur.fetchall()}
        conn.close()
    finally:
        import os; os.unlink(tmp)
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if v)


def fetch_archive_djvu_authenticated(identifier: str, timeout: int = 300) -> str:
    """
    Download the djvu.txt for a restricted-lending archive.org item using
    Chrome browser session cookies (handles CDL loans).
    """
    meta_url = f"https://archive.org/metadata/{identifier}"
    print(f"    Checking metadata: {meta_url}", flush=True)
    meta = json.loads(fetch_url(meta_url, timeout=30))
    files = meta.get("files", [])
    djvu_files = [f["name"] for f in files if f["name"].endswith("_djvu.txt")]
    if not djvu_files:
        raise RuntimeError(f"no _djvu.txt in {identifier}")

    filename = djvu_files[0]
    url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(filename)}"
    print(f"    Fetching (with browser cookies): {url}", flush=True)

    cookie_str = _get_chrome_archive_cookies()
    if not cookie_str:
        raise RuntimeError("Could not extract Chrome cookies for archive.org")

    headers = {**BROWSER_HEADERS, "Cookie": cookie_str}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_UNVERIFIED) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_djvu(text: str) -> str:
    text = re.sub(r'\x0c', '\n\n', text)
    text = re.sub(r'(?m)^\s*\d{1,4}\s*$', '', text)
    text = re.sub(r'(?m)^[-_=]{3,}\s*$', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    paras = text.split('\n\n')
    joined = []
    for p in paras:
        p = re.sub(r'-\s*\n\s*([a-z])', r'\1', p)
        p = p.replace('\n', ' ')
        p = re.sub(r'  +', ' ', p).strip()
        if p:
            joined.append(p)
    return '\n\n'.join(joined)


# ── Group 1: Pseudepigrapha ───────────────────────────────────────────────────
# R.H. Charles "Apocrypha and Pseudepigrapha of the Old Testament" Vol 2 (1913)
# Contains: 1 Enoch, Jubilees, Testaments of XII Patriarchs, 2 Baruch, 4 Ezra,
#           Assumption of Moses, Psalms of Solomon, Life of Adam, and more.

PSEUDEPIGRAPHA_ARCHIVE = "apocryphapseudep02charuoft"


def sync_pseudepigrapha(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "pseudepigrapha"
    out_file = out_dir / "charles_apot_vol2_pseudepigrapha.txt"
    print("\n═══ Pseudepigrapha ═══")
    print("  R.H. Charles APOT Vol 2 (1 Enoch, Jubilees, Testaments, 2 Baruch, 4 Ezra…)")
    if not rebuild and out_file.exists() and out_file.stat().st_size > 50_000:
        print(f"    Cached: {out_file.name}")
        return
    try:
        raw = fetch_archive_djvu(PSEUDEPIGRAPHA_ARCHIVE)
        text = clean_djvu(raw)
        save(out_dir, out_file.name, text, rebuild=True)
    except Exception as e:
        print(f"    ERROR: {e}")


# ── Group 2: LXX Apocrypha / Deuterocanonical ────────────────────────────────
# R.H. Charles "Apocrypha and Pseudepigrapha of the Old Testament" Vol 1 (1913)
# Contains: Tobit, Judith, Additions to Esther, Wisdom, Sirach, Baruch,
#           Letter of Jeremiah, Prayer of Azariah, Susanna, 1-4 Maccabees.

APOCRYPHA_ARCHIVE = "apocryphapseudep01charuoft"


def sync_apocrypha(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "apocrypha"
    out_file = out_dir / "charles_apot_vol1_apocrypha.txt"
    print("\n═══ LXX Apocrypha / Deuterocanonical ═══")
    print("  R.H. Charles APOT Vol 1 (Tobit, Sirach, Wisdom, Maccabees…)")
    if not rebuild and out_file.exists() and out_file.stat().st_size > 50_000:
        print(f"    Cached: {out_file.name}")
        return
    try:
        raw = fetch_archive_djvu(APOCRYPHA_ARCHIVE)
        text = clean_djvu(raw)
        save(out_dir, out_file.name, text, rebuild=True)
    except Exception as e:
        print(f"    ERROR: {e}")


# ── Group 3: Nag Hammadi library ──────────────────────────────────────────────

NAG_HAMMADI = [
    ("Gospel of Thomas (Lambdin)",           "gospel_of_thomas.txt",
     "https://gnosis.org/naghamm/gthlamb.html"),
    ("Gospel of Philip (Isenberg)",          "gospel_of_philip.txt",
     "https://gnosis.org/naghamm/gop.html"),
    ("Apocryphon of John (long recension)",  "apocryphon_of_john.txt",
     "https://gnosis.org/naghamm/apocjn.html"),
    ("Gospel of Truth (MacRae)",             "gospel_of_truth.txt",
     "https://gnosis.org/naghamm/got.html"),
    ("Treatise on the Resurrection",         "treatise_on_resurrection.txt",
     "https://gnosis.org/naghamm/treat_res.html"),
    ("On the Origin of the World",           "origin_of_the_world.txt",
     "https://gnosis.org/naghamm/origin.html"),
    ("Thunder, Perfect Mind",                "thunder_perfect_mind.txt",
     "https://gnosis.org/naghamm/thunder.html"),
    ("Exegesis on the Soul",                 "exegesis_on_the_soul.txt",
     "https://gnosis.org/naghamm/exe.html"),
    ("Book of Thomas the Contender",         "book_of_thomas.txt",
     "https://gnosis.org/naghamm/bookt.html"),
    ("Sophia of Jesus Christ",               "sophia_of_jesus_christ.txt",
     "https://gnosis.org/naghamm/sjc.html"),
    ("Dialogue of the Saviour",              "dialogue_of_the_saviour.txt",
     "https://gnosis.org/naghamm/dialog.html"),
    ("Allogenes",                            "allogenes.txt",
     "https://gnosis.org/naghamm/allogene.html"),
    ("Gospel of the Egyptians (Holy Book)",  "gospel_of_egyptians.txt",
     "https://gnosis.org/naghamm/goseqypt.html"),
    ("Hypostasis of the Archons",            "hypostasis_of_archons.txt",
     "https://gnosis.org/naghamm/hypostas.html"),
]


def sync_nag_hammadi(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "nag_hammadi"
    print("\n═══ Nag Hammadi library ═══")
    for name, out_name, url in NAG_HAMMADI:
        print(f"\n  {name}")
        out_file = out_dir / out_name
        if not rebuild and out_file.exists() and out_file.stat().st_size > 2_000:
            print(f"    Cached: {out_name}")
            continue
        try:
            html = fetch_url_unverified(url)
            text = strip_html(html)
            save(out_dir, out_name, text, rebuild=True)
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(0.5)


# ── Group 4: Dead Sea Scrolls ─────────────────────────────────────────────────

DSS_SOURCES = [
    {
        "name": "Dead Sea Scrolls (Vermes selections)",
        "out":  "dead_sea_scrolls_vermes.txt",
        "index": "https://sacred-texts.com/chr/dss/index.htm",
        "base":  "https://sacred-texts.com/chr/dss/",
    },
]

DSS_ARCHIVE = [
    {
        "name": "Dead Sea Scrolls in English — Vermes",
        "out":  "dss_vermes.txt",
        "identifier": "deadseascrollsin0000geza",
        "restricted": True,
    },
]


def sync_dead_sea_scrolls(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "dead_sea_scrolls"
    print("\n═══ Dead Sea Scrolls ═══")
    for src in DSS_SOURCES:
        print(f"\n  {src['name']}")
        out_file = out_dir / src["out"]
        if not rebuild and out_file.exists() and out_file.stat().st_size > 5_000:
            print(f"    Cached: {src['out']}")
            continue
        text = scrape_sacred_texts(src["index"], src["base"], src["name"])
        if text:
            save(out_dir, src["out"], text, rebuild=True)
        time.sleep(1)

    for src in DSS_ARCHIVE:
        print(f"\n  {src['name']}")
        out_file = out_dir / src["out"]
        if not rebuild and out_file.exists() and out_file.stat().st_size > 5_000:
            print(f"    Cached: {src['out']}")
            continue
        try:
            if src.get("restricted"):
                raw = fetch_archive_djvu_authenticated(src["identifier"])
            else:
                raw = fetch_archive_djvu(src["identifier"])
            text = clean_djvu(raw)
            save(out_dir, src["out"], text, rebuild=True)
        except Exception as e:
            print(f"    ERROR (archive.org): {e}")


# ── Group 5: B.H. Roberts ─────────────────────────────────────────────────────

BH_ROBERTS_SOURCES = [
    {
        "name": "A Comprehensive History of the Church — B.H. Roberts",
        "out":  "comprehensive_history_of_church.txt",
        "identifier": "bwb_Y0-BNX-707",
    },
]


def sync_bh_roberts(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "bh_roberts"
    print("\n═══ B.H. Roberts ═══")
    for src in BH_ROBERTS_SOURCES:
        print(f"\n  {src['name']}")
        out_file = out_dir / src["out"]
        if not rebuild and out_file.exists() and out_file.stat().st_size > 10_000:
            print(f"    Cached: {src['out']}")
            continue
        try:
            raw = fetch_archive_djvu(src["identifier"])
            text = clean_djvu(raw)
            save(out_dir, src["out"], text, rebuild=True)
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(2)


# ── Group 6: Nibley ───────────────────────────────────────────────────────────

NIBLEY_SOURCES = [
    {
        "name": "Since Cumorah — Hugh Nibley",
        "out":  "nibley_since_cumorah.txt",
        "identifier": "sincecumorah00hugh",
        "restricted": True,
    },
    {
        "name": "Mormonism and Early Christianity — Hugh Nibley",
        "out":  "nibley_mormonism_early_christianity.txt",
        "identifier": "mormonismearlych0000nibl",
        "restricted": True,
    },
    {
        "name": "Teachings of the Book of Mormon — Hugh Nibley",
        "out":  "nibley_teachings_bom.txt",
        "identifier": "teachingsofbooko0000nibl",
        "restricted": True,
    },
]


def sync_nibley(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "nibley"
    print("\n═══ Hugh Nibley ═══")
    for src in NIBLEY_SOURCES:
        print(f"\n  {src['name']}")
        out_file = out_dir / src["out"]
        if not rebuild and out_file.exists() and out_file.stat().st_size > 10_000:
            print(f"    Cached: {src['out']}")
            continue
        try:
            if src.get("restricted"):
                raw = fetch_archive_djvu_authenticated(src["identifier"])
            else:
                raw = fetch_archive_djvu(src["identifier"])
            text = clean_djvu(raw)
            save(out_dir, src["out"], text, rebuild=True)
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(2)


# ── Group 7: Nauvoo Theology ──────────────────────────────────────────────────

# Plain-text documents available from various historical sites.
# King Follett Discourse appears in JD Vol 6; also widely reproduced standalone.
NAUVOO_SOURCES = [
    {
        "name": "King Follett Discourse — Joseph Smith (1844)",
        "out":  "king_follett_discourse.txt",
        "url":  "https://www.gutenberg.org/files/4992/4992-0.txt",
        # fallback: the BYU Studies version is in their digital archive
        "fallback_url": None,
        "description": "Joseph Smith's final doctrinal sermon on the nature of God and eternal progression",
    },
    {
        "name": "Lectures on Faith — Joseph Smith / Sidney Rigdon (1835)",
        "out":  "lectures_on_faith.txt",
        "url":  "https://www.gutenberg.org/files/60315/60315-0.txt",
        "fallback_url": None,
        "description": "Lectures on Faith as published in the 1835 D&C appendix",
    },
    {
        "name": "Parley P. Pratt — Key to the Science of Theology",
        "out":  "pratt_key_to_science_of_theology.txt",
        "identifier": "keytoscienceof1874prat",
    },
    {
        "name": "Orson Pratt — The Seer (periodical, 1853–1854)",
        "out":  "orson_pratt_the_seer.txt",
        "identifier": "TheSeer18531854",
    },
]


def sync_nauvoo_theology(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "nauvoo_theology"
    print("\n═══ Nauvoo Theology / Early LDS Doctrine ═══")
    for src in NAUVOO_SOURCES:
        print(f"\n  {src['name']}")
        out_file = out_dir / src["out"]
        if not rebuild and out_file.exists() and out_file.stat().st_size > 5_000:
            print(f"    Cached: {src['out']}")
            continue

        if "url" in src:
            # Plain URL fetch
            try:
                raw = fetch_url(src["url"])
                save(out_dir, src["out"], raw, rebuild=True)
            except Exception as e:
                print(f"    ERROR (direct): {e}")
                if src.get("fallback_url"):
                    try:
                        raw = fetch_url(src["fallback_url"])
                        save(out_dir, src["out"], raw, rebuild=True)
                    except Exception as e2:
                        print(f"    ERROR (fallback): {e2}")
        else:
            try:
                raw = fetch_archive_djvu(src["identifier"])
                text = clean_djvu(raw)
                save(out_dir, src["out"], text, rebuild=True)
            except Exception as e:
                print(f"    ERROR: {e}")
        time.sleep(2)


# ── Group 8: JST / Inspired Version ──────────────────────────────────────────

JST_SOURCES = []

# Also grab the full Inspired Version from archive.org
JST_ARCHIVE = {
    "name": "Inspired Version of the Holy Scriptures (1867)",
    "out":  "inspired_version_1867.txt",
    "identifier": "inspired-version-of-the-holy-scriptures-1867",
}


def sync_jst(rebuild: bool) -> None:
    out_dir = CACHE_DIR / "jst"
    print("\n═══ Joseph Smith Translation / Inspired Version ═══")

    # Try archive.org first (most complete)
    print(f"\n  {JST_ARCHIVE['name']}")
    out_file = out_dir / JST_ARCHIVE["out"]
    if not rebuild and out_file.exists() and out_file.stat().st_size > 10_000:
        print(f"    Cached: {JST_ARCHIVE['out']}")
    else:
        try:
            raw = fetch_archive_djvu(JST_ARCHIVE["identifier"])
            text = clean_djvu(raw)
            save(out_dir, JST_ARCHIVE["out"], text, rebuild=True)
        except Exception as e:
            print(f"    ERROR (archive.org): {e}")

    # HTML scraped versions
    for src in JST_SOURCES:
        print(f"\n  {src['name']}")
        out_file = out_dir / src["out"]
        if not rebuild and out_file.exists() and out_file.stat().st_size > 5_000:
            print(f"    Cached: {src['out']}")
            continue
        text = scrape_sacred_texts(src["index"], src["base"], src["name"])
        if text:
            save(out_dir, src["out"], text, rebuild=True)
        time.sleep(1)


# ── correlate.py integration: add new dirs ───────────────────────────────────

NEW_SOURCE_DIRS = {
    "pseudepigrapha":  ("pseudepigrapha",   "Pseudepigrapha"),
    "apocrypha":       ("apocrypha",        "LXX Apocrypha"),
    "nag_hammadi":     ("nag_hammadi",      "Nag Hammadi"),
    "dead_sea_scrolls":("dead_sea_scrolls", "Dead Sea Scrolls"),
    "bh_roberts":      ("bh_roberts",       "B.H. Roberts"),
    "nibley":          ("nibley",           "Nibley"),
    "nauvoo_theology": ("nauvoo_theology",  "Nauvoo Theology"),
    "jst":             ("jst",              "JST"),
}


def print_correlate_snippet() -> None:
    print("\n" + "=" * 70)
    print("Add these to correlate.py load_all_sources():")
    print("=" * 70)
    for key, (dirname, label) in NEW_SOURCE_DIRS.items():
        print(f"""
    {key} = _load_plaintext_dir(CACHE_DIR / "{dirname}", "{key}", "{label}")
    print(f"  {label}: {{len({key}):,}}")
    all_passages.extend({key})""")


# ── Main ──────────────────────────────────────────────────────────────────────

GROUPS = {
    "pseudepigrapha":   sync_pseudepigrapha,
    "apocrypha":        sync_apocrypha,
    "nag_hammadi":      sync_nag_hammadi,
    "dead_sea_scrolls": sync_dead_sea_scrolls,
    "bh_roberts":       sync_bh_roberts,
    "nibley":           sync_nibley,
    "nauvoo_theology":  sync_nauvoo_theology,
    "jst":              sync_jst,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync additional LDS scholarly sources")
    parser.add_argument("--rebuild", action="store_true", help="Re-download even if cached")
    parser.add_argument("--group", choices=list(GROUPS), help="Only run one group")
    parser.add_argument("--list-sources", action="store_true",
                        help="Print correlate.py snippet and exit")
    args = parser.parse_args()

    if args.list_sources:
        print_correlate_snippet()
        return

    targets = {args.group: GROUPS[args.group]} if args.group else GROUPS
    for name, fn in targets.items():
        try:
            fn(args.rebuild)
        except Exception as e:
            print(f"\nERROR in group '{name}': {e}")

    print("\n\nDone. Run --list-sources to see correlate.py integration snippet.")
    print("Then rebuild TF-IDF: python3 correlate.py --rebuild")


if __name__ == "__main__":
    main()
