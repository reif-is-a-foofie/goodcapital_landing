#!/usr/bin/env python3
"""
build_graph.py
==============
Pre-compute per-chapter graph JSON files from correlation cache.

Output: library/chapters/{slug}_graph.json
Format:
  {
    "nodes": [
      {"id": "v1",  "t": "v", "n": 1,   "x": "verse text..."},
      {"id": "p_0", "t": "p", "src": "donaldson", "lb": "label...", "x": "passage text..."}
    ],
    "edges": [
      {"s": "v1", "t": "p_0", "w": 0.41}
    ]
  }

Node types:  v = verse, p = passage
Source keys map to colors in the reader.

Run from repo root:
    python3 lds_pipeline/build_graph.py [--books genesis] [--min-score 0.25]
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

REPO        = Path(__file__).parent.parent
CORR_DIR    = Path(__file__).parent / "cache" / "correlations"
CHAPTERS    = REPO / "library" / "chapters"

MIN_SCORE   = 0.25
MAX_MATCHES = 5   # top N matches per verse to include

# Truncate passage text for the graph (shown in hover/popover)
MAX_TEXT_LEN = 400


def book_to_slug_prefix(book: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', book.lower()).strip('_')


def chapter_slug(book: str, chapter: int) -> str:
    return f"{book_to_slug_prefix(book)}_{chapter}"


def truncate(text: str, limit: int = MAX_TEXT_LEN) -> str:
    if not text or len(text) <= limit:
        return text
    cut = text[:limit]
    pos = cut.rfind(' ')
    return (cut[:pos] + '\u2026') if pos > limit // 2 else cut + '\u2026'


def build_chapter_graph(book: str, chapter: int, verse_files: list[Path], min_score: float = MIN_SCORE) -> dict:
    """Build graph dict for one chapter from its verse correlation files."""
    nodes = []
    edges = []
    passage_index: dict[str, str] = {}   # (source, label) → node id

    for vf in sorted(verse_files, key=lambda f: int(f.stem.rsplit('_', 1)[-1])):
        try:
            data = json.loads(vf.read_text(encoding='utf-8'))
        except Exception:
            continue

        vnum   = data.get('verse', int(vf.stem.rsplit('_', 1)[-1]))
        vtext  = data.get('text', '')
        vid    = f'v{vnum}'

        nodes.append({
            'id': vid,
            't':  'v',
            'n':  vnum,
            'x':  truncate(vtext, 200),
        })

        matches = sorted(
            data.get('matches', []),
            key=lambda m: m.get('score', 0),
            reverse=True,
        )

        count = 0
        for m in matches:
            score = m.get('score', 0)
            if score < min_score:
                break
            if count >= MAX_MATCHES:
                break

            src   = m.get('source', '')
            label = m.get('label', src)
            pkey  = f'{src}\x00{label}'

            if pkey not in passage_index:
                pid = f'p_{len(passage_index)}'
                passage_index[pkey] = pid
                nodes.append({
                    'id':  pid,
                    't':   'p',
                    'src': src,
                    'lb':  label,
                    'x':   truncate(m.get('text', ''), MAX_TEXT_LEN),
                })
            else:
                pid = passage_index[pkey]

            edges.append({'s': vid, 't': pid, 'w': round(score, 3)})
            count += 1

    return {'nodes': nodes, 'edges': edges}


def main():
    parser = argparse.ArgumentParser(description='Build per-chapter graph JSON')
    parser.add_argument('--books',     nargs='+', help='process only these book prefixes')
    parser.add_argument('--min-score', type=float, default=MIN_SCORE)
    args = parser.parse_args()

    min_score = args.min_score

    # Group correlation files by (book, chapter)
    by_chapter: dict[tuple, list[Path]] = defaultdict(list)
    for f in CORR_DIR.iterdir():
        if not f.suffix == '.json':
            continue
        # filename: "Book Name_chapter_verse.json"
        # split on last two underscores
        stem = f.stem
        parts = stem.rsplit('_', 2)
        if len(parts) != 3:
            continue
        book, ch_str, ve_str = parts
        try:
            ch = int(ch_str)
            int(ve_str)
        except ValueError:
            continue
        by_chapter[(book, ch)].append(f)

    # Filter by book prefix if requested
    if args.books:
        def matches_filter(book: str) -> bool:
            prefix = book_to_slug_prefix(book)
            return any(prefix.startswith(b.lower()) for b in args.books)
        by_chapter = {k: v for k, v in by_chapter.items() if matches_filter(k[0])}

    print(f"Building graphs for {len(by_chapter)} chapters...")

    written = 0
    skipped = 0
    for (book, chapter), files in sorted(by_chapter.items()):
        cslug  = chapter_slug(book, chapter)
        outpath = CHAPTERS / f'{cslug}_graph.json'

        graph = build_chapter_graph(book, chapter, files, min_score)

        if not graph['nodes']:
            skipped += 1
            continue

        outpath.write_text(
            json.dumps(graph, ensure_ascii=False, separators=(',', ':')),
            encoding='utf-8',
        )
        written += 1

        if written % 100 == 0:
            print(f'  {written} written...')

    print(f'\nDone. {written} graph files written, {skipped} skipped (no nodes).')


if __name__ == '__main__':
    main()
