"""
Epub/mobi text extractor.

Source is the existing .mobi or .epub from the previous pipeline.
Uses Calibre CLI to convert mobi→epub if needed, then extracts
text from epub HTML files using BeautifulSoup.

Word-merge fix applied at extraction time using the same spatial
heuristics — epub HTML word breaks are cleaner than raw PDF, so
most merges are already resolved; we apply regex cleanup for the
CamelCase residuals.
"""

import re
import os
import subprocess
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

CALIBRE = "/Users/reify/Downloads/Reif_Machine_Archive_2026-03-19/Software/calibre.app/Contents/MacOS/ebook-convert"


def mobi_to_epub(mobi_path: str, out_epub: str = None) -> str:
    """Convert mobi to epub using Calibre. Returns epub path."""
    if not out_epub:
        out_epub = str(Path(mobi_path).with_suffix(".epub"))

    if Path(out_epub).exists() and Path(out_epub).stat().st_size > 10000:
        print(f"  Using existing epub: {out_epub}")
        return out_epub

    print(f"  Converting mobi → epub via Calibre...")
    result = subprocess.run(
        [CALIBRE, mobi_path, out_epub,
         "--output-profile", "kindle",
         "--enable-heuristics"],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"Calibre conversion failed:\n{result.stderr}")
    print(f"  → {out_epub}")
    return out_epub


def extract_epub_text(epub_path: str) -> str:
    """
    Extract and clean all text from an epub file.
    Returns a single string with the full text, newlines between paragraphs.
    """
    print(f"Extracting text from: {epub_path}")
    all_parts = []

    with zipfile.ZipFile(epub_path, 'r') as z:
        # Find all HTML/XHTML content files
        html_files = sorted([
            n for n in z.namelist()
            if n.endswith(('.html', '.xhtml', '.htm'))
            and not n.endswith('toc.xhtml')
            and 'nav' not in n.lower()
        ])
        print(f"  {len(html_files)} HTML parts found")

        for fname in html_files:
            raw = z.read(fname).decode('utf-8', errors='replace')
            text = _html_to_text(raw)
            if text.strip():
                all_parts.append(text)

    full_text = '\n\n'.join(all_parts)
    clean = _fix_merges(full_text)
    print(f"  {len(clean):,} characters extracted")
    return clean


def _html_to_text(html: str) -> str:
    """
    Convert HTML to clean plain text.
    Preserves paragraph structure for verse parsing.
    """
    soup = BeautifulSoup(html, 'lxml')

    # Remove script/style
    for tag in soup(['script', 'style', 'head']):
        tag.decompose()

    # Convert <br> to newline
    for br in soup.find_all('br'):
        br.replace_with('\n')

    # Convert <p> and block elements to double-newline separated text
    lines = []
    for elem in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'span']):
        text = elem.get_text(separator=' ', strip=True)
        if text:
            lines.append(text)

    if not lines:
        # Fallback: get all text
        return soup.get_text(separator='\n', strip=True)

    return '\n'.join(lines)


# ── Word-merge fix ────────────────────────────────────────────────────────────

_CAMEL_RE = re.compile(r'([a-z])([A-Z][a-z])')

def _fix_merges(text: str) -> str:
    """Fix CamelCase merges and normalize whitespace."""
    text = _CAMEL_RE.sub(r'\1 \2', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_from_mobi(mobi_path: str, work_dir: str = "/tmp") -> str:
    """Full pipeline: mobi → epub → text. Returns clean text string."""
    epub_path = os.path.join(work_dir, "lds_source.epub")

    # Use existing /tmp/lds_ot.epub if it's there and is the OT mobi
    if os.path.exists("/tmp/lds_ot.epub"):
        epub_path = "/tmp/lds_ot.epub"
        print(f"  Using cached epub: {epub_path}")
    else:
        epub_path = mobi_to_epub(mobi_path, epub_path)

    return extract_epub_text(epub_path)
