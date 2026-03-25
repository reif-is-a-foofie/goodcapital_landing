#!/usr/bin/env python3
"""
Generate HTML chapters for the 3 missing Pearl of Great Price books:
  - Joseph Smith—Matthew (1 chapter, 55 verses)
  - Joseph Smith—History (1 chapter, 75 verses)
  - Articles of Faith (1 chapter, 13 verses)

Uses the cached PGP JSON. Applies any cached enrichment (Donaldson,
correlations) if available. Appends entries to toc.json.

Run from repo root:
    python3 lds_pipeline/generate_pgp_missing.py
"""

import json
import re
import sys
from html import escape
from pathlib import Path

REPO       = Path(__file__).parent.parent
CACHE_DIR  = Path(__file__).parent / "cache"
CHAPTERS   = REPO / "library" / "chapters"
TOC_PATH   = REPO / "library" / "toc.json"
DONA_DIR   = CACHE_DIR / "donaldson"
CORR_DIR   = CACHE_DIR / "correlations"

PGP_JSON   = CACHE_DIR / "scriptures_json" / "Pearl_of_Great_Price.json"

MISSING = {"Joseph Smith\u2014Matthew", "Joseph Smith\u2014History", "Articles of Faith"}

MAX_DONA_PARAS = 12
MAX_BLOCK_CHARS = 4000


def slug(name: str, chapter: int) -> str:
    s = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    return f"{s}_{chapter}"


def truncate(text: str, limit: int = MAX_BLOCK_CHARS) -> str:
    if not text or len(text) <= limit:
        return text
    cut = text[:limit]
    for punct in ('. ', '! ', '? '):
        pos = cut.rfind(punct)
        if pos > limit // 2:
            return cut[:pos + 1]
    pos = cut.rfind(' ')
    return (cut[:pos] + '\u2026') if pos > 0 else cut


def render_donaldson(book: str, chapter: int, verse: int) -> str:
    """Return rendered HTML for Donaldson block, or empty string."""
    path = DONA_DIR / f"{book}_{chapter}_{verse}.json"
    if not path.exists():
        return ''
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        paras = data.get('paragraphs', [])[:MAX_DONA_PARAS]
        paras = [p for p in paras if len(p.strip()) > 20]
        if not paras:
            return ''
        inner = ''.join(
            f'<p class="donaldson-para">{escape(truncate(p))}</p>'
            for p in paras
        )
        return (f'<div class="donaldson-block">'
                f'<span class="source-label">Donaldson</span>{inner}</div>')
    except Exception:
        return ''


def render_semantic(book: str, chapter: int, verse: int) -> list[str]:
    """Return list of rendered semantic-quote HTML blocks."""
    path = CORR_DIR / f"{book}_{chapter}_{verse}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        matches = sorted(data.get('matches', []), key=lambda m: m.get('score', 0), reverse=True)
        results = []
        seen_sources: dict[str, int] = {}
        for m in matches:
            score = m.get('score', 0)
            if score < 0.25:
                break
            src = m.get('source', '')
            if seen_sources.get(src, 0) >= 2:
                continue
            seen_sources[src] = seen_sources.get(src, 0) + 1
            text = truncate(m.get('text', ''), 600)
            if not text or len(text.split()) < 8:
                continue
            label = escape(src.replace('_', ' ').title())
            results.append(
                f'<div class="semantic-quote">'
                f'<div class="semantic-meta">'
                f'<span class="semantic-source">{label}</span>'
                f'</div>'
                f'<div class="semantic-text">{escape(text)}</div>'
                f'</div>'
            )
            if len(results) >= 3:
                break
        return results
    except Exception:
        return []


def render_chapter(book_name, chapter_num, verses, prev_slug, next_slug):
    """
    Returns (text_html, notes_html) for one chapter.
    text_html  — scripture text only (for initial load)
    notes_html — commentary blocks (lazy-loaded)
    """
    book_key = re.sub(r'[^a-z0-9]+', '_', book_name.lower()).strip('_')

    head_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="UTF-8">',
        f'<meta name="chapter-id" content="{slug(book_name, chapter_num)}">',
    ]
    if prev_slug:
        head_parts.append(f'<meta name="prev" content="{prev_slug}">')
    if next_slug:
        head_parts.append(f'<meta name="next" content="{next_slug}">')
    head_parts += [
        '<link rel="stylesheet" href="../style/main.css">',
        '</head>',
    ]

    header = [
        f'<h2 class="book-title">{escape(book_name)}</h2>',
        f'<p class="chapter-num">{chapter_num}</p>',
        '<div class="score-legend">'
        '<span class="score-legend-item"><span class="score-dots">\u25cf\u25cf\u25cf\u25cf\u25cf</span> direct quotation</span>'
        '<span class="score-legend-item"><span class="score-dots">\u25cf\u25cf\u25cf\u25cb\u25cb</span> thematic parallel</span>'
        '<span class="score-legend-item"><span class="score-dots">\u25cf\u25cb\u25cb\u25cb\u25cb</span> loose connection</span>'
        '</div>',
    ]

    text_verses = []
    notes_sections = []

    for v in verses:
        vnum = v['verse']
        vtext = escape(v.get('text', ''))
        vid = f'v{vnum}'

        # Scripture text span
        text_verses.append(
            f'<div class="verse" id="{vid}">\n'
            f'<span class="verse-num">{vnum}</span>'
            f'<span class="verse-text">{vtext}</span>\n'
            f'</div>'
        )

        # Notes (enrichment)
        note_blocks = []
        dona = render_donaldson(book_key, chapter_num, vnum)
        if dona:
            note_blocks.append(dona)
        note_blocks.extend(render_semantic(book_key, chapter_num, vnum))

        if note_blocks:
            notes_sections.append(
                f'<div data-verse="{vnum}">\n'
                + '\n'.join(note_blocks) + '\n'
                '</div>'
            )

    text_html = '\n'.join(
        head_parts + ['<body>', '<div class="scripture">']
        + header + text_verses
        + ['</div>', '</body>', '</html>']
    )

    if notes_sections:
        notes_html = (
            '<!DOCTYPE html>\n<html lang="en">\n<body>\n'
            + '\n'.join(notes_sections) + '\n'
            '</body>\n</html>\n'
        )
    else:
        notes_html = None

    return text_html, notes_html


def main():
    pgp = json.loads(PGP_JSON.read_text(encoding='utf-8'))
    toc  = json.loads(TOC_PATH.read_text(encoding='utf-8'))

    # Find if Pearl of Great Price volume already in TOC
    pgp_vol_idx = next((i for i, e in enumerate(toc)
                        if e.get('type') == 'volume' and e.get('label') == 'Pearl of Great Price'), None)

    if pgp_vol_idx is None:
        print("Pearl of Great Price volume not found in TOC — this script expects it to exist.")
        print("Make sure Abraham and Moses chapters were generated first.")
        sys.exit(1)

    # Find where to insert (after Abraham — last chapter before next volume or end)
    # Find the last entry in the PGP section
    insert_at = len(toc)
    for i in range(pgp_vol_idx + 1, len(toc)):
        if toc[i].get('type') == 'volume' and i != pgp_vol_idx:
            insert_at = i
            break

    # Figure out the slug just before our insertion for prev/next links
    # Last chapter slug currently in the TOC before insertion point
    last_slug = None
    for e in toc[:insert_at]:
        if e.get('type') == 'chapter' and e.get('id'):
            last_slug = e['id']

    new_toc_entries = []
    generated = []
    prev_s = last_slug

    for book_data in pgp['books']:
        bname = book_data['book']
        if bname not in MISSING:
            continue

        print(f"\nGenerating: {bname}")
        chapters = book_data['chapters']
        bslug_0 = slug(bname, chapters[0]['chapter'])

        # Book entry
        new_toc_entries.append({
            'id': None, 'label': bname,
            'href': f'chapters/{bslug_0}.html',
            'depth': 1, 'type': 'book',
            'first_chapter': bslug_0,
        })

        for ch in chapters:
            cnum = ch['chapter']
            cslug = slug(bname, cnum)
            verses = ch['verses']

            # Determine next slug (peek ahead in book list)
            next_s = None
            # Will be updated after all books processed

            text_html, notes_html = render_chapter(bname, cnum, verses, prev_s, None)

            CHAPTERS.mkdir(parents=True, exist_ok=True)
            (CHAPTERS / f'{cslug}.html').write_text(text_html, encoding='utf-8')
            if notes_html:
                (CHAPTERS / f'{cslug}_notes.html').write_text(notes_html, encoding='utf-8')

            print(f"  {cslug}.html — {len(verses)} verses"
                  + (f' + {len(notes_html)//1024}kb notes' if notes_html else ''))

            new_toc_entries.append({
                'id': cslug, 'label': str(cnum),
                'href': f'chapters/{cslug}.html',
                'depth': 2, 'type': 'chapter',
            })
            generated.append(cslug)
            prev_s = cslug

    # Patch next/prev links in generated files
    # First generated chapter: prev = last_slug
    # Between them: chain prev/next
    for i, cslug in enumerate(generated):
        prev_s2 = generated[i - 1] if i > 0 else last_slug
        next_s2 = generated[i + 1] if i < len(generated) - 1 else None
        path = CHAPTERS / f'{cslug}.html'
        html = path.read_text(encoding='utf-8')
        if prev_s2 and f'content="{prev_s2}"' not in html:
            html = html.replace(
                '<link rel="stylesheet" href="../style/main.css">',
                f'<meta name="prev" content="{prev_s2}">\n<link rel="stylesheet" href="../style/main.css">'
            )
        if next_s2 and f'content="{next_s2}"' not in html:
            html = html.replace(
                '<link rel="stylesheet" href="../style/main.css">',
                f'<meta name="next" content="{next_s2}">\n<link rel="stylesheet" href="../style/main.css">'
            )
        path.write_text(html, encoding='utf-8')

    # Insert into TOC
    toc[insert_at:insert_at] = new_toc_entries
    TOC_PATH.write_text(
        json.dumps(toc, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    print(f"\nDone. {len(generated)} chapters generated.")
    print(f"TOC updated: {len(toc)} entries total.")


if __name__ == '__main__':
    main()
