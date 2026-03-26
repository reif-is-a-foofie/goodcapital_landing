#!/usr/bin/env python3
"""
build_word_index.py
===================
Generates {slug}_words.json per chapter from {slug}_graph.json files.
Falls back to correlation cache if available, otherwise uses graph nodes.

Format:
  {
    "1": {                          ← verse number (string key)
      "nephi": {                    ← stemmed word
        "score": 1.63,
        "forms": ["Nephi"],
        "matches": [
          {"s": "donaldson", "lb": "...", "x": "...", "w": 0.408},
          ...
        ]
      },
      ...
    }
  }

Run from repo root:
    python3 lds_pipeline/build_word_index.py [--books genesis]
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

REPO     = Path(__file__).parent.parent
CHAPTERS = REPO / "library" / "chapters"
TOC_PATH = REPO / "library" / "toc.json"

MIN_MATCH_SCORE  = 0.18
MAX_MATCHES_WORD = 8
MAX_TEXT_LEN     = 500
MAX_SCRIPTURE_FALLBACKS = 3
MAX_SCRIPTURE_POSTINGS = 600

SOURCE_PRIORITY = {
    'standard_works': 0,
    'jst': 1,
}

STOPS = {
    'the','a','an','and','or','but','in','on','of','to','for','with','by',
    'from','at','as','into','upon','unto','about','above','below','after',
    'before','through','within','without','among','between','against',
    'over','under','around','along','across','behind','beside','beyond',
    'is','was','are','were','be','been','being','have','has','had',
    'do','does','did','will','would','shall','should','may','might',
    'must','can','could',
    'having','going','coming','making','saying','knowing',
    'seeing','given','taken','come','came','went','made','said','make',
    'take','give','go','get','got','let','put','keep','kept','set',
    'brought','bring','send','sent','told','tell','find','found',
    'it','its','he','she','they','we','i','me','him','her','us',
    'them','his','hers','their','our','your','my','himself','herself',
    'themselves','itself','ourselves','yourself',
    'this','these','that','those','what','which','who','whom','whose',
    'when','where','why','how','if','then','else',
    'not','no','nor','so','yet','both','either','neither','each','all',
    'any','some','such','than','also','even','only','just','still',
    'again','now','then','here','there','thus','forth','therefore',
    'wherefore','thereof','therein','therefrom','whereby','herein',
    'yea','ye','thy','thee','thou','hath','doth','didst','wilt',
    'shalt','sayeth','saith','art','hast','canst','wouldst','shouldst',
    'things','thing','place','places','time','times','day','days',
    'way','ways','people','number','part','parts','kind','manner','means',
    'very','more','most','much','many','few','little',
    'same','other','another','every','first','last','next','own',
    'long','back','down','away','far','near','once','twice',
}


def stem(w: str) -> str:
    w = w.lower()
    for suffix in ('ness','ment','tion','sion','ing','ful','ous','ish',
                   'ive','ary','ery','ory','ly','ed','er','est','al','ic'):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[:-len(suffix)]
    if w.endswith('ies') and len(w) > 5:
        return w[:-3] + 'y'
    if w.endswith('s') and len(w) > 4 and not w.endswith('ss'):
        return w[:-1]
    return w


def tokenize(text: str):
    for w in re.findall(r"[a-zA-Z''\u2019]+", text):
        clean = w.strip("''\u2019\u2018")
        if len(clean) < 3:
            continue
        lower = clean.lower()
        if lower in STOPS:
            continue
        st = stem(lower)
        if st in STOPS or len(st) < 2:
            continue
        yield clean, st


def truncate(text: str, limit: int = MAX_TEXT_LEN) -> str:
    if not text or len(text) <= limit:
        return text
    cut = text[:limit]
    pos = cut.rfind(' ')
    return (cut[:pos] + '\u2026') if pos > limit // 2 else cut + '\u2026'


def match_sort_key(m: dict):
    return (
        SOURCE_PRIORITY.get(m.get('s', ''), 9),
        -m.get('w', 0),
        m.get('lb', ''),
    )


def load_chapter_labels() -> dict[str, dict]:
    if not TOC_PATH.exists():
        return {}
    try:
        toc = json.loads(TOC_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}

    out = {}
    current_book = None
    for item in toc:
        if item.get('type') == 'book':
            current_book = item.get('label')
        elif item.get('type') == 'chapter':
            out[item.get('id', '')] = {
                'book': current_book or '',
                'chapter': str(item.get('label', '')),
            }
    return out


def build_scripture_catalog(graph_files: list[Path]) -> tuple[dict[str, list], dict[str, float]]:
    labels = load_chapter_labels()
    verses = []
    postings = defaultdict(list)

    for gf in graph_files:
        slug = gf.stem.replace('_graph', '')
        try:
            graph = json.loads(gf.read_text(encoding='utf-8'))
        except Exception:
            continue

        chapter_meta = labels.get(slug, {})
        book = chapter_meta.get('book') or slug.rsplit('_', 1)[0].replace('_', ' ').title()
        chapter = chapter_meta.get('chapter') or slug.rsplit('_', 1)[-1]

        for node in graph.get('nodes', []):
            if node.get('t') != 'v':
                continue
            text = node.get('x', '')
            if not text:
                continue
            stems = set()
            forms_by_stem = defaultdict(set)
            for form, st in tokenize(text):
                forms_by_stem[st].add(form)
                stems.add(st)
            if not stems:
                continue
            entry = {
                'id': f'{slug}:{node.get("n")}',
                'slug': slug,
                'verse': int(node.get('n', 0) or 0),
                'label': f'{book} {chapter}:{int(node.get("n", 0) or 0)}',
                'text': text,
                'stems': stems,
                'forms_by_stem': forms_by_stem,
            }
            verse_idx = len(verses)
            verses.append(entry)
            for st in stems:
                postings[st].append(verse_idx)

    total = len(verses)
    idf = {stem: max(0.2, (1.0 + (total / (len(ids) + 1)) ** 0.15)) for stem, ids in postings.items()}
    return {'verses': verses, 'postings': postings}, idf


def add_scripture_fallbacks(
    hit_matches: list[dict],
    stem_key: str,
    verse_stems: set[str],
    scripture_ctx: Optional[dict],
    scripture_idf: Optional[dict[str, float]],
    self_ref: str,
    forms: set[str],
) -> list[dict]:
    if not scripture_ctx or not scripture_idf:
        return hit_matches
    if len(hit_matches) >= MAX_MATCHES_WORD and any(m.get('s') == 'standard_works' for m in hit_matches):
        return hit_matches

    verse_ids = scripture_ctx.get('postings', {}).get(stem_key, [])
    if not verse_ids or len(verse_ids) > MAX_SCRIPTURE_POSTINGS:
        return hit_matches

    existing = {(m.get('s', ''), m.get('lb', '')) for m in hit_matches}
    forms_lower = {f.lower() for f in forms}
    additions = []

    for idx in verse_ids:
        verse = scripture_ctx['verses'][idx]
        if verse['id'] == self_ref:
            continue
        label_key = ('standard_works', verse['label'])
        if label_key in existing:
            continue
        overlap = len(verse_stems & verse['stems'])
        if overlap < 2:
            continue
        exact_bonus = 0.1 if forms_lower & {f.lower() for f in verse['forms_by_stem'].get(stem_key, set())} else 0.0
        score = min(0.92, 0.22 + 0.06 * min(overlap, 6) + 0.05 * min(scripture_idf.get(stem_key, 1.0), 3.0) + exact_bonus)
        additions.append({
            's': 'standard_works',
            'lb': verse['label'],
            'x': truncate(verse['text']),
            'w': round(score, 3),
        })

    additions.sort(key=match_sort_key)
    return (additions[:MAX_SCRIPTURE_FALLBACKS] + hit_matches)[:MAX_MATCHES_WORD]


def build_from_graph(graph: dict, chapter_slug: str, scripture_ctx: Optional[dict] = None, scripture_idf: Optional[dict[str, float]] = None) -> dict:
    """
    Build verse→word→matches index from a chapter graph JSON.
    Graph has verse nodes (t='v') and passage nodes (t='p') with edges.
    """
    # Index passage nodes by id
    passages = {n['id']: n for n in graph['nodes'] if n.get('t') == 'p'}

    # Group edges by source verse
    verse_edges: dict[str, list] = defaultdict(list)
    for e in graph['edges']:
        verse_edges[e['s']].append(e)

    # Build verse texts from verse nodes
    verse_texts = {n['id']: (n.get('n', 0), n.get('x', ''))
                   for n in graph['nodes'] if n.get('t') == 'v'}

    chapter_index: dict[str, dict] = {}

    for vid, (vnum, vtext) in verse_texts.items():
        if not vtext:
            continue

        edges = verse_edges.get(vid, [])
        if not edges:
            continue

        # Build match list for this verse
        matches_for_verse = []
        seen = set()
        for e in sorted(edges, key=lambda x: -x.get('w', 0)):
            pid = e.get('t')
            p   = passages.get(pid)
            if not p:
                continue
            score = e.get('w', 0)
            if score < MIN_MATCH_SCORE:
                continue
            key = (p.get('src', ''), p.get('lb', '')[:60])
            if key in seen:
                continue
            seen.add(key)
            match = {
                's':  p.get('src', ''),
                'lb': p.get('lb', ''),
                'x':  truncate(p.get('x', '')),
                'w':  score,
            }
            if p.get('d'):
                match['d'] = p.get('d')
            if p.get('p'):
                match['p'] = p.get('p')
            matches_for_verse.append(match)

        if not matches_for_verse:
            continue

        # Score each content word in the verse
        tokens = list(tokenize(vtext))
        if not tokens:
            continue

        stem_to_forms: dict[str, set] = defaultdict(set)
        for form, st in tokens:
            stem_to_forms[st].add(form)
        verse_stems = set(stem_to_forms.keys())
        self_ref = f'{chapter_slug}:{vnum}'

        word_data: dict[str, dict] = {}
        for st, forms in stem_to_forms.items():
            hit_matches = []
            forms_lower = {f.lower() for f in forms}
            mstems_cache = {}

            for m in matches_for_verse:
                mtext = m.get('x', '').lower()
                if id(mtext) not in mstems_cache:
                    mstems_cache[id(mtext)] = set(
                        stem(w) for w in re.findall(r'[a-z]+', mtext) if len(w) >= 3
                    )
                mstems = mstems_cache[id(mtext)]

                if st in mstems or forms_lower & mstems or any(f in mtext for f in forms_lower):
                    hit_matches.append(m)

            if not hit_matches:
                hit_matches = add_scripture_fallbacks([], st, verse_stems, scripture_ctx, scripture_idf, self_ref, forms)
                if not hit_matches:
                    continue

            hit_matches = add_scripture_fallbacks(hit_matches, st, verse_stems, scripture_ctx, scripture_idf, self_ref, forms)
            hit_matches.sort(key=match_sort_key)
            total_score = sum(m['w'] for m in hit_matches)
            word_data[st] = {
                'score':   round(total_score, 3),
                'forms':   sorted(forms, key=len, reverse=True)[:3],
                'matches': hit_matches[:MAX_MATCHES_WORD],
            }

        if word_data:
            chapter_index[str(vnum)] = word_data

    return chapter_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--books', nargs='+')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing _words.json files')
    args = parser.parse_args()

    graph_files = sorted(CHAPTERS.glob('*_graph.json'))

    if args.books:
        graph_files = [f for f in graph_files
                       if any(f.stem.startswith(b.lower().replace(' ', '_'))
                              for b in args.books)]

    print(f'Building word indexes from {len(graph_files)} graph files...')
    scripture_ctx, scripture_idf = build_scripture_catalog(graph_files)

    written = skipped = total_words = 0
    for gf in graph_files:
        slug     = gf.stem.replace('_graph', '')
        outpath  = CHAPTERS / f'{slug}_words.json'

        if outpath.exists() and not args.force:
            skipped += 1
            continue

        try:
            graph = json.loads(gf.read_text(encoding='utf-8'))
        except Exception:
            continue

        index = build_from_graph(graph, slug, scripture_ctx, scripture_idf)
        if not index:
            continue

        wcount = sum(len(v) for v in index.values())
        total_words += wcount
        outpath.write_text(
            json.dumps(index, ensure_ascii=False, separators=(',', ':')),
            encoding='utf-8',
        )
        written += 1

        if written % 200 == 0:
            print(f'  {written} written...')

    print(f'\nDone. {written} word index files written, {skipped} skipped (already exist).')
    print(f'Total word entries: {total_words:,}')


if __name__ == '__main__':
    main()
