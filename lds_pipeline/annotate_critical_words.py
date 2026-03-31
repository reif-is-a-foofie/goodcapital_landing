#!/usr/bin/env python3
"""
annotate_critical_words.py
==========================
Wraps every content word in each verse that has cross-reference matches in a
  <span class="w" data-st="{stem}" data-v="{vnum}" style="--ws:{norm}">word</span>
where --ws (0–1 normalised per verse) drives underline thickness + opacity.

Reads match data from {slug}_words.json (built by build_word_index.py).

Run from repo root:
    python3 lds_pipeline/annotate_critical_words.py [--books genesis] [--dry-run] [--force]
"""

import argparse
import json
import html
import re
from pathlib import Path

REPO     = Path(__file__).parent.parent
CHAPTERS = REPO / "library" / "chapters"


def normalise_scores(word_data: dict) -> dict:
    """Return {stem: norm_score} (0-1) for the verse."""
    if not word_data:
        return {}
    mx = max(v['score'] for v in word_data.values())
    if mx == 0:
        return {k: 0.0 for k in word_data}
    return {k: round(v['score'] / mx, 3) for k, v in word_data.items()}


def find_spans(plain: str, word_data: dict, norm: dict) -> list:
    """
    Returns list of (start, end, stem, norm_score) for non-overlapping word spans.
    Processes highest-scored stems first; uses canonical forms from words.json.
    """
    spans = []
    used: list[tuple] = []

    for st, ns in sorted(norm.items(), key=lambda x: -x[1]):
        entry  = word_data.get(st)
        if not entry:
            continue
        forms  = entry.get('forms', [st])

        # Build candidate list: actual verse forms first, then inflections
        inflections = [st, st+'s', st+'ed', st+'ing', st+'ly', st+'ness',
                       st+'ful', st+'ion', st+'er', st+'est']
        forms_set   = set(f.lower() for f in forms)
        candidates  = forms + [f for f in inflections if f not in forms_set]

        for cand in candidates:
            if len(cand) < 2:
                continue
            for m in re.finditer(r'\b' + re.escape(cand) + r'\b', plain, re.IGNORECASE):
                s, e = m.start(), m.end()
                if any(a < e and s < b for a, b in used):
                    continue
                spans.append((s, e, st, ns))
                used.append((s, e))

    return sorted(spans, key=lambda x: x[0])


def _he(text: str) -> str:
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))


_LITERAL_MARKUP_NOISE = re.compile(
    r'(&lt;|<)\s*(?:span|a)\b[^>]*(?:&gt;|>)|'
    r'(&lt;|<)\s*/\s*(?:span|a)\s*(?:&gt;|>)',
    re.IGNORECASE,
)


def clean_plain_text(plain: str) -> str:
    """Strip literal escaped markup that leaked into verse text before re-annotation."""
    plain = _LITERAL_MARKUP_NOISE.sub(" ", plain)
    plain = plain.replace("`", " ")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


def annotate_text(plain: str, vnum: int, word_data: dict) -> str:
    """Annotate clean verse text with .w spans."""
    if not word_data:
        return _he(plain)

    norm = normalise_scores(word_data)
    if not norm:
        return _he(plain)

    spans = find_spans(plain, word_data, norm)
    if not spans:
        return _he(plain)

    out = []
    pos = 0
    for (s, e, st, ns) in spans:
        if s < pos:
            continue
        out.append(_he(plain[pos:s]))
        out.append(
            f'<span class="w" data-st="{st}" data-v="{vnum}" style="--ws:{ns}">'
            f'{_he(plain[s:e])}'
            f'</span>'
        )
        pos = e
    out.append(_he(plain[pos:]))
    return ''.join(out)


def process_chapter(chapter_path: Path, words_data: dict, dry_run: bool) -> dict:
    """Annotate one chapter HTML file using its pre-built words JSON."""
    from bs4 import BeautifulSoup

    slug = chapter_path.stem
    html_text = chapter_path.read_text(encoding='utf-8')
    soup = BeautifulSoup(html_text, 'html.parser')

    verse_count = cw_total = 0
    changed = False

    for verse_div in soup.select('div.verse[id]'):
        verse_id = verse_div.get('id', '')
        if not verse_id.startswith('v') or not verse_id[1:].isdigit():
            continue
        vnum = int(verse_id[1:])
        verse_count += 1
        vdata = words_data.get(str(vnum), {})
        if not vdata:
            continue

        verse_num = verse_div.find('span', class_='verse-num')
        if not verse_num:
            continue

        verse_copy = BeautifulSoup(str(verse_div), 'html.parser').find('div', class_='verse')
        for tag in verse_copy.find_all('div', class_='backlinks'):
            tag.decompose()
        for tag in verse_copy.find_all('span', class_='verse-num'):
            tag.decompose()
        plain = html.unescape(verse_copy.get_text('', strip=False))
        plain = clean_plain_text(plain)
        if not plain:
            continue

        new_inner = annotate_text(plain, vnum, vdata)
        backlinks_html = ''.join(
            str(tag) for tag in verse_div.find_all('div', class_='backlinks', recursive=False)
        )
        rebuilt_html = (
            f'<div class="verse" id="{verse_id}">'
            f'{str(verse_num)}'
            f'<span class="verse-text">{new_inner}</span>'
            f'{backlinks_html}'
            f'</div>'
        )
        replacement = BeautifulSoup(
            rebuilt_html,
            'html.parser',
        ).find('div', class_='verse')
        if str(replacement) == str(verse_div):
            continue
        verse_div.replace_with(replacement)
        cw_total += len(vdata)
        changed = True

    new_html = str(soup)

    if not dry_run and new_html != html_text:
        chapter_path.write_text(new_html, encoding='utf-8')

    return {
        'slug':    slug,
        'verses':  verse_count,
        'cw':      cw_total,
        'changed': changed or new_html != html_text,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--books',   nargs='+')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force',   action='store_true',
                        help='Re-annotate even chapters that already have .w spans')
    args = parser.parse_args()

    files = sorted(f for f in CHAPTERS.glob('*.html')
                   if not any(s in f.name for s in ('_notes', '_words', '_graph')))

    if args.books:
        files = [f for f in files
                 if any(f.stem.startswith(b.lower().replace(' ', '_'))
                        for b in args.books)]

    if not args.force:
        files = [f for f in files
                 if 'class="w"' not in f.read_text(encoding='utf-8', errors='ignore')]

    print(f'Annotating {len(files)} chapters...')
    if args.dry_run:
        print('  (dry run)')

    tv = tc = changed = errors = 0
    for i, path in enumerate(files):
        slug       = path.stem
        words_path = CHAPTERS / f'{slug}_words.json'

        if not words_path.exists():
            continue

        try:
            words_data = json.loads(words_path.read_text(encoding='utf-8'))
        except Exception:
            continue

        try:
            s = process_chapter(path, words_data, args.dry_run)
            tv += s['verses']; tc += s['cw']
            if s['changed']: changed += 1
        except Exception as e:
            print(f'  ERROR {path.name}: {e}')
            errors += 1

        if (i + 1) % 200 == 0:
            print(f'  ... {i+1}/{len(files)}')

    print(f'\nDone. {changed} chapters changed, {tv} verses, {tc} word entries.')
    if errors:
        print(f'  Errors: {errors}')


if __name__ == '__main__':
    main()
