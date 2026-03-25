#!/usr/bin/env python3
"""
build_word_index.py
===================
Generates {slug}_words.json per chapter — the data powering the Channel.

Format:
  {
    "1": {                          ← verse number (string key)
      "nephi": {                    ← stemmed word
        "score": 1.63,              ← total score across all matches
        "forms": ["Nephi"],         ← canonical surface forms found in verse
        "matches": [                ← top matches, sorted by score desc
          {"s": "donaldson", "lb": "Donaldson on 1 Nephi 1:1",
           "x": "passage text...", "w": 0.408},
          ...
        ]
      },
      ...
    },
    ...
  }

Run from repo root:
    python3 lds_pipeline/build_word_index.py [--books genesis]
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

REPO     = Path(__file__).parent.parent
CORR_DIR = Path(__file__).parent / "cache" / "correlations"
CHAPTERS = REPO / "library" / "chapters"

MIN_MATCH_SCORE = 0.18   # discard very weak matches
MAX_MATCHES_PER_WORD = 8
MAX_TEXT_LEN = 500

# ── Stop words (same set as annotate_critical_words) ──────────────────────
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
    'way','ways','man','men','people','world','words','word',
    'number','part','parts','kind','manner','means',
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
    """Yield (original_form, stemmed) for content words."""
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


def build_verse_word_index(vtext: str, matches: list) -> dict:
    """
    Returns {stemmed_word: {"score": float, "forms": [str], "matches": [...]}}
    """
    tokens = list(tokenize(vtext))
    if not tokens:
        return {}

    stem_to_forms: dict[str, set] = defaultdict(set)
    for form, st in tokens:
        stem_to_forms[st].add(form)

    # For each stem, collect matches where that stem appears in match text
    word_data: dict[str, dict] = {}

    for st, forms in stem_to_forms.items():
        hit_matches = []
        for m in matches:
            score = m.get('score', 0)
            if score < MIN_MATCH_SCORE:
                continue
            mtext = m.get('text', '').lower()
            mwords = set(stem(w) for w in re.findall(r'[a-z]+', mtext) if len(w) >= 3)
            forms_lower = {f.lower() for f in forms}

            if st in mwords or forms_lower & mwords or any(f in mtext for f in forms_lower):
                hit_matches.append(m)

        if not hit_matches:
            continue

        # Sort by score, deduplicate by (source, label), keep top N
        seen = set()
        deduped = []
        for m in sorted(hit_matches, key=lambda x: x.get('score', 0), reverse=True):
            key = (m.get('source',''), m.get('label','')[:60])
            if key not in seen:
                seen.add(key)
                deduped.append(m)
            if len(deduped) >= MAX_MATCHES_PER_WORD:
                break

        total_score = sum(m.get('score', 0) for m in deduped)

        word_data[st] = {
            'score':   round(total_score, 3),
            'forms':   sorted(forms, key=len, reverse=True)[:3],
            'matches': [
                {
                    's':  m.get('source', ''),
                    'lb': m.get('label', ''),
                    'x':  truncate(m.get('text', '')),
                    'w':  round(m.get('score', 0), 3),
                }
                for m in deduped
            ],
        }

    return word_data


def process_chapter(book: str, chapter: int, verse_files: list) -> dict:
    """Build word index for one chapter. Returns {verse_str: {stem: {...}}}."""
    chapter_index = {}

    for vf in sorted(verse_files, key=lambda f: int(f.stem.rsplit('_', 1)[-1])):
        try:
            data = json.loads(vf.read_text(encoding='utf-8'))
        except Exception:
            continue

        vnum   = data.get('verse', int(vf.stem.rsplit('_', 1)[-1]))
        vtext  = data.get('text', '')
        matches = sorted(data.get('matches', []),
                         key=lambda m: m.get('score', 0), reverse=True)

        windex = build_verse_word_index(vtext, matches)
        if windex:
            chapter_index[str(vnum)] = windex

    return chapter_index


def book_slug(book: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', book.lower()).strip('_')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--books', nargs='+')
    args = parser.parse_args()

    # Group correlation files by (book, chapter)
    by_chapter: dict[tuple, list] = defaultdict(list)
    for f in CORR_DIR.iterdir():
        if f.suffix != '.json':
            continue
        parts = f.stem.rsplit('_', 2)
        if len(parts) != 3:
            continue
        book, ch_str, v_str = parts
        try:
            ch = int(ch_str)
            int(v_str)
        except ValueError:
            continue
        by_chapter[(book, ch)].append(f)

    if args.books:
        by_chapter = {
            k: v for k, v in by_chapter.items()
            if any(book_slug(k[0]).startswith(b.lower()) for b in args.books)
        }

    print(f'Building word indexes for {len(by_chapter)} chapters...')

    written = 0
    total_words = 0
    for (book, chapter), files in sorted(by_chapter.items()):
        cslug = f'{book_slug(book)}_{chapter}'
        outpath = CHAPTERS / f'{cslug}_words.json'

        index = process_chapter(book, chapter, files)
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

    print(f'\nDone. {written} word index files, {total_words:,} word entries.')


if __name__ == '__main__':
    main()
