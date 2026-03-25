#!/usr/bin/env python3
"""
annotate_critical_words.py
==========================
Wraps every content word in each verse that has at least one cross-reference
match in a <span class="w" data-st="{stem}" data-v="{vnum}" style="--ws:{score}">
where --ws (0–1 normalised) drives underline thickness + opacity in CSS.

No cutoff — every matched content word gets a span. The visual weight
communicates richness; clicking any word opens the Channel.

Run from repo root:
    python3 lds_pipeline/annotate_critical_words.py [--books genesis] [--dry-run]
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

REPO     = Path(__file__).parent.parent
CORR_DIR = Path(__file__).parent / "cache" / "correlations"
CHAPTERS = REPO / "library" / "chapters"

MIN_MATCH_SCORE = 0.18   # word must appear in at least one match above this

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


def compute_word_scores(vtext: str, matches: list) -> dict:
    """Returns {stemmed: total_score} for words that appear in any match."""
    tokens = list(tokenize(vtext))
    if not tokens:
        return {}

    stem_to_forms: dict[str, set] = defaultdict(set)
    for form, st in tokens:
        stem_to_forms[st].add(form.lower())

    scores: dict[str, float] = defaultdict(float)

    for m in matches:
        score = m.get('score', 0)
        if score < MIN_MATCH_SCORE:
            continue
        mtext = m.get('text', '').lower()
        mstems = set(stem(w) for w in re.findall(r'[a-z]+', mtext) if len(w) >= 3)

        for st, forms in stem_to_forms.items():
            if st in mstems or forms & mstems or any(f in mtext for f in forms):
                scores[st] += score

    return dict(scores)


def normalise_scores(scores: dict) -> dict:
    """Normalise to 0–1 range within this verse."""
    if not scores:
        return {}
    mx = max(scores.values())
    if mx == 0:
        return {k: 0.0 for k in scores}
    return {k: round(v / mx, 3) for k, v in scores.items()}


def annotate_verse_text(verse_html: str, vnum: int, scores: dict, norm: dict) -> str:
    """
    Replace each scored word's occurrence in <span class="verse-text">...</span>
    with <span class="w" data-st="{stem}" data-v="{vnum}" style="--ws:{norm}">word</span>.
    """
    match = re.search(r'(<span class="verse-text">)(.*?)(</span>)', verse_html, re.DOTALL)
    if not match:
        return verse_html

    pre    = verse_html[:match.start(2)]
    suf    = verse_html[match.end(2):]
    vhtml  = match.group(2)

    # Un-escape to get plain text
    plain = (vhtml
             .replace('&amp;', '&').replace('&lt;', '<')
             .replace('&gt;', '>').replace('&quot;', '"')
             .replace('&#x27;', "'").replace('&#39;', "'"))

    # Build a map: position → (end, stem, norm_score) for non-overlapping spans
    # Try to match each stem's surface forms in the plain text
    span_map: list[tuple] = []   # (start, end, stem, ns)
    used: list[tuple] = []

    stem_forms: dict[str, list[str]] = {}
    for form, st in tokenize(plain):
        if st in scores:
            stem_forms.setdefault(st, [])
            if form not in stem_forms[st]:
                stem_forms[st].append(form)

    for st, ns in sorted(norm.items(), key=lambda x: -x[1]):
        if st not in stem_forms:
            continue
        forms = stem_forms[st]
        # Try longest form first, then inflections
        # Prioritise actual forms found in the verse, then generated inflections
        inflections = [st, st+'s', st+'ed', st+'ing', st+'ly', st+'ness',
                       st+'ful', st+'ion', st+'er', st+'est']
        forms_set = set(f.lower() for f in forms)
        candidates = forms + [f for f in sorted(set(inflections), key=len, reverse=True)
                               if f not in forms_set]

        for form in candidates:
            if len(form) < 2:
                continue
            for m in re.finditer(r'\b' + re.escape(form) + r'\b', plain, re.IGNORECASE):
                s, e = m.start(), m.end()
                if any(a < e and s < b for a, b, *_ in used):
                    continue
                span_map.append((s, e, st, ns))
                used.append((s, e))
                break
            else:
                continue
            break

    span_map.sort(key=lambda x: x[0])

    # Rebuild text with spans
    out = []
    pos = 0
    for (s, e, st, ns) in span_map:
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

    return pre + ''.join(out) + suf


def _he(text: str) -> str:
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))


def process_chapter(chapter_path: Path, corr_files: dict, dry_run: bool) -> dict:
    slug = chapter_path.stem
    html = chapter_path.read_text(encoding='utf-8')

    verse_pattern = re.compile(
        r'(<div class="verse" id="v(\d+)">)(.*?)(</div>)',
        re.DOTALL,
    )

    cw_total = 0
    verse_total = 0

    def replace_verse(m):
        nonlocal cw_total, verse_total
        open_tag = m.group(1)
        vnum     = int(m.group(2))
        inner    = m.group(3)
        close    = m.group(4)
        verse_total += 1

        cf = corr_files.get(vnum)
        if not cf:
            return m.group(0)
        try:
            data    = json.loads(cf.read_text(encoding='utf-8'))
            vtext   = data.get('text', '')
            matches = sorted(data.get('matches', []),
                             key=lambda x: x.get('score', 0), reverse=True)
        except Exception:
            return m.group(0)

        scores = compute_word_scores(vtext, matches)
        if not scores:
            return m.group(0)

        norm   = normalise_scores(scores)
        new_inner = annotate_verse_text(inner, vnum, scores, norm)
        cw_total += len(scores)
        return open_tag + new_inner + close

    new_html = verse_pattern.sub(replace_verse, html)

    if not dry_run and new_html != html:
        chapter_path.write_text(new_html, encoding='utf-8')

    return {'slug': slug, 'verses': verse_total, 'cw': cw_total, 'changed': new_html != html}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--books',   nargs='+')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print('Indexing correlation files...')
    slug_to_corr: dict[str, dict[int, Path]] = defaultdict(dict)
    for f in CORR_DIR.iterdir():
        if f.suffix != '.json':
            continue
        parts = f.stem.rsplit('_', 2)
        if len(parts) != 3:
            continue
        book, ch_str, v_str = parts
        try:
            ch = int(ch_str)
            v  = int(v_str)
        except ValueError:
            continue
        bs = re.sub(r'[^a-z0-9]+', '_', book.lower()).strip('_')
        slug_to_corr[f'{bs}_{ch}'][v] = f

    files = sorted(f for f in CHAPTERS.glob('*.html')
                   if not f.stem.endswith(('_notes', '_words', '_graph')))
    if args.books:
        files = [f for f in files
                 if any(f.stem.startswith(b.lower()) for b in args.books)]

    print(f'Processing {len(files)} chapters...')
    if args.dry_run:
        print('  (dry run — no files written)')

    tv = tc = ch = err = 0
    for i, path in enumerate(files):
        slug = path.stem
        corr = slug_to_corr.get(slug, {})
        if not corr:
            continue
        try:
            s = process_chapter(path, corr, args.dry_run)
            tv += s['verses']; tc += s['cw']
            if s['changed']: ch += 1
        except Exception as e:
            print(f'  ERROR {path.name}: {e}')
            err += 1
        if (i + 1) % 200 == 0:
            print(f'  ... {i+1}/{len(files)}  ({tc} words so far)')

    print(f'\nDone. {ch} chapters changed, {tv} verses, {tc} word spans.')
    if err: print(f'  Errors: {err}')


if __name__ == '__main__':
    main()
