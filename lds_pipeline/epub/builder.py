"""
epub3 builder — assembles the enriched LDS Scripture epub.

Takes structured volumes + per-verse enrichment and produces a valid epub3
with embedded fonts, CSS, and proper navigation.

Source blocks are rendered in descending relevance order using TF-IDF
correlation scores. Every source type is scored; fixed high-priority items
(JST, word studies, Donaldson) use their correlation score where available
and a sensible default where not.
"""

import json
import os
import re
import sys
from pathlib import Path
from ebooklib import epub

sys.path.insert(0, str(Path(__file__).parent))
from curate_sources import curate, render_dots, score_to_dots, MIN_SCORE

FONT_DIR  = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/epub/fonts")
CSS_PATH  = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/epub/styles.css")
_DONA_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/donaldson")
_CORR_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/correlations")

# Canonical display names — used everywhere a source label appears
SOURCE_NAMES = {
    "jst":                   "Joseph Smith Translation",
    "donaldson":             "Donaldson",
    "journal_of_discourses": "Journal of Discourses",
    "history_of_church":     "History of the Church",
    "joseph_smith_papers":   "Joseph Smith Papers",
    "general_conference":    "General Conference",
    "sefaria":               "Sefaria",
    "church_fathers":        "Church Fathers",
    "ancient_texts":         "Ancient Texts",
    "pseudepigrapha":        "Pseudepigrapha",
    "apocrypha":             "LXX Apocrypha",
    "nag_hammadi":           "Nag Hammadi",
    "dead_sea_scrolls":      "Dead Sea Scrolls",
    "bh_roberts":            "B.H. Roberts",
    "nibley":                "Nibley",
    "gutenberg_lds":         "Early LDS Writings",
    "millennial_star":       "Millennial Star",
    "times_and_seasons":     "Times and Seasons",
    "nauvoo_theology":       "Nauvoo Theology",
    "pioneer_journals":      "Pioneer Journals",
    "mcconkie":              "McConkie",
}

# Maps enrichment dict keys → correlation source key (for scoring)
_CORR_KEY = {
    "jd":            "journal_of_discourses",
    "hoc":           "history_of_church",
    "gc":            "general_conference",
    "jsp":           "joseph_smith_papers",
    "rashi":         "sefaria",
    "talmud":        "sefaria",
    "midrash":       "sefaria",
    "targum":        "sefaria",
    "zohar":         "sefaria",
    "mcconkie":      "journal_of_discourses",
    "early_saints":  "pioneer_journals",
    "gutenberg_lds": "gutenberg_lds",
    "church_fathers":"church_fathers",
    "ancient":       "ancient_texts",
}


def _strip_verse_quote(para: str, verse_text: str) -> str:
    if not verse_text or not para:
        return para
    dash_pos = para.find('—')
    if dash_pos > 0:
        prefix = para[:dash_pos].strip().lower()
        verse_norm = verse_text.strip().lower()
        prefix_words = prefix.split()
        verse_words = verse_norm.split()
        shared = sum(1 for w in prefix_words if w in set(verse_words))
        if shared >= min(3, len(prefix_words)) and len(prefix_words) <= len(verse_words) + 4:
            remainder = para[dash_pos + 1:].strip()
            if len(remainder) > 20:
                return remainder
    return para


def build_epub(volumes, enrichment: dict, config, output_path: str) -> str:
    book = epub.EpubBook()
    book.set_title(config.EPUB_TITLE)
    book.set_language(config.EPUB_LANGUAGE)
    book.add_author(config.EPUB_AUTHOR)
    book.set_identifier("lds-scriptures-enriched-2026")

    for fname in [
        config.FONT_SCRIPTURE, config.FONT_SCRIPTURE_IT,
        config.FONT_COMMENTARY, config.FONT_COMMENTARY_IT,
    ]:
        fpath = Path(config.FONT_DIR) / fname
        if fpath.exists():
            mime = "font/otf" if fname.endswith(".otf") else "font/ttf"
            font_item = epub.EpubItem(
                uid=f"font_{fname}",
                file_name=f"fonts/{fname}",
                media_type=mime,
                content=fpath.read_bytes(),
            )
            book.add_item(font_item)

    css_item = epub.EpubItem(
        uid="stylesheet",
        file_name="style/main.css",
        media_type="text/css",
        content=CSS_PATH.read_text(encoding="utf-8"),
    )
    book.add_item(css_item)

    spine   = ["nav"]
    toc     = []
    all_chapters = []

    for volume in volumes:
        vol_toc_entries = []
        for bk in volume.books:
            book_chapters = []
            for ch in bk.chapters:
                html = _render_chapter(ch, enrichment, config)
                slug = _slug(f"{bk.name}_{ch.number}")
                epub_ch = epub.EpubHtml(
                    title=f"{bk.name} {ch.number}",
                    file_name=f"text/{slug}.xhtml",
                    lang="en",
                    content=html.encode("utf-8"),
                )
                epub_ch.add_item(css_item)
                book.add_item(epub_ch)
                all_chapters.append(epub_ch)
                spine.append(epub_ch)
                book_chapters.append(epub_ch)

            if book_chapters:
                vol_toc_entries.append(
                    epub.Section(bk.name,
                        [epub.Link(c.file_name, c.title, "") for c in book_chapters])
                )

        if vol_toc_entries:
            toc.append(epub.Section(volume.name, vol_toc_entries))

    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    epub.write_epub(output_path, book)
    print(f"\nEpub written: {output_path}")
    return output_path


def init_web(volumes, config, output_dir: str) -> list:
    """
    One-time setup for the web reader. Call this before enrichment starts.

    Writes toc.json, CSS, and title page immediately so the reader is
    navigable even before chapters arrive.

    Returns all_slugs — ordered list of chapter ids needed for prev/next
    links. Pass this to write_book_chapters() for each book.
    """
    out = Path(output_dir)
    (out / "chapters").mkdir(parents=True, exist_ok=True)
    (out / "style").mkdir(exist_ok=True)

    (out / "style" / "main.css").write_text(
        CSS_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )

    all_slugs = ["title_page"]
    for volume in volumes:
        for bk in volume.books:
            for ch in bk.chapters:
                all_slugs.append(_slug(f"{bk.name}_{ch.number}"))

    _write_title_page(out / "chapters" / "title_page.html")

    toc = [{"id": "title_page", "label": "Title Page",
             "href": "chapters/title_page.html", "depth": 0, "type": "front"}]
    for volume in volumes:
        toc.append({"id": None, "label": volume.name,
                    "href": None, "depth": 0, "type": "volume"})
        for bk in volume.books:
            first_slug = _slug(f"{bk.name}_1") if bk.chapters else None
            toc.append({"id": None, "label": bk.name,
                        "href": f"chapters/{first_slug}.html" if first_slug else None,
                        "depth": 1, "type": "book", "first_chapter": first_slug})
            for ch in bk.chapters:
                slug = _slug(f"{bk.name}_{ch.number}")
                toc.append({"id": slug, "label": str(ch.number),
                             "href": f"chapters/{slug}.html", "depth": 2, "type": "chapter"})

    (out / "toc.json").write_text(
        json.dumps(toc, ensure_ascii=False, separators=(',', ':')),
        encoding="utf-8"
    )
    print(f"  Web: toc.json written ({len(all_slugs)-1} chapters)")
    return all_slugs


def write_book_chapters(bk, enrichment: dict, config, output_dir: str,
                        all_slugs: list) -> int:
    """
    Render and write all chapters for one book. Call after enriching each book.
    Produces two files per chapter:
      {slug}.html        — scripture text only (fast initial load)
      {slug}_notes.html  — commentary blocks (lazy-loaded by reader)
    Returns the number of chapters written.
    """
    out = Path(output_dir)
    written = 0
    for ch in bk.chapters:
        slug = _slug(f"{bk.name}_{ch.number}")
        idx  = all_slugs.index(slug) if slug in all_slugs else -1
        prev = all_slugs[idx - 1] if idx > 0 else None
        nxt  = all_slugs[idx + 1] if idx >= 0 and idx < len(all_slugs) - 1 else None
        text_html, notes_html = _render_chapter_split(slug, prev, nxt, ch, enrichment)
        (out / "chapters" / f"{slug}.html").write_text(text_html, encoding="utf-8")
        if notes_html:
            (out / "chapters" / f"{slug}_notes.html").write_text(notes_html, encoding="utf-8")
        written += 1
    return written


def build_web(volumes, enrichment: dict, config, output_dir: str) -> str:
    """Full batch build — used when not streaming per-book."""
    all_slugs = init_web(volumes, config, output_dir)
    for volume in volumes:
        for bk in volume.books:
            write_book_chapters(bk, enrichment, config, output_dir, all_slugs)
    build_backlinks(output_dir)
    n = len(all_slugs) - 1
    print(f"\nWeb build written: {output_dir}  ({n} chapters)")
    return output_dir


def build_backlinks(output_dir: str):
    """
    Post-processing pass: scan all chapter HTML files for outbound ref-links,
    build a reverse index, then inject 'Referenced from' sections into targets.

    Safe to run incrementally — rewrites only files that have new incoming refs.
    """
    out = Path(output_dir) / "chapters"
    if not out.exists():
        return

    # Step 1: collect all outbound links from every chapter
    # outbound[source_slug] = [(target_slug, target_verse, display_text)]
    _link_re = re.compile(
        r'<a class="ref-link" href="\.\./chapters/([^.]+)\.html#v(\d+)">([^<]+)</a>'
    )
    outbound: dict = {}
    for f in out.glob("*.html"):
        src_slug = f.stem
        html     = f.read_text(encoding="utf-8")
        links    = _link_re.findall(html)
        if links:
            outbound[src_slug] = links   # [(target_slug, verse_num, display)]

    if not outbound:
        return

    # Step 2: build reverse index
    # backlinks[target_slug][verse_num] = [(src_slug, display_text), ...]
    backlinks: dict = {}
    for src_slug, links in outbound.items():
        for target_slug, verse_num, display in links:
            backlinks.setdefault(target_slug, {}).setdefault(verse_num, [])
            entry = (src_slug, display)
            if entry not in backlinks[target_slug][verse_num]:
                backlinks[target_slug][verse_num].append(entry)

    # Step 3: rewrite target files — append backlinks block inside each verse div
    _verse_end_re = re.compile(r'(<div class="verse" id="v(\d+)">.*?)(</div>)', re.DOTALL)

    updated = 0
    for target_slug, verse_map in backlinks.items():
        target_file = out / f"{target_slug}.html"
        if not target_file.exists():
            continue
        html = target_file.read_text(encoding="utf-8")

        def _inject(m):
            v_num = m.group(2)
            refs  = verse_map.get(v_num, [])
            if not refs:
                return m.group(0)
            links_html = ''.join(
                f'<a class="backlink-ref" href="../chapters/{src}.html">{disp}</a>'
                for src, disp in refs
            )
            backlink_block = (
                f'<div class="backlinks">'
                f'<span class="backlinks-label">Referenced from</span>'
                f'{links_html}</div>'
            )
            return m.group(1) + backlink_block + m.group(3)

        new_html = _verse_end_re.sub(_inject, html)
        if new_html != html:
            target_file.write_text(new_html, encoding="utf-8")
            updated += 1

    print(f"  Backlinks: updated {updated} chapters")


def _write_title_page(path: Path):
    path.write_text(
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="chapter-id" content="title_page">\n'
        '<link rel="stylesheet" href="../style/main.css">\n'
        '</head>\n<body>\n'
        '<h1 class="book-title">LDS Scriptures — Enriched Edition</h1>\n'
        '<p class="chapter-num" style="font-size:1rem;color:#888;margin-top:1em">'
        'Annotated with Donaldson commentary, Jewish sources, Church history, '
        'and cross-corpus semantic matches.</p>\n'
        '</body>\n</html>\n',
        encoding="utf-8",
    )


def _render_chapter_html(slug: str, prev, nxt, ch, enrichment: dict) -> str:
    """Render a chapter as standalone HTML5 (legacy batch build — not used by streaming)."""
    text_html, _ = _render_chapter_split(slug, prev, nxt, ch, enrichment)
    return text_html


def _render_chapter_split(slug: str, prev, nxt, ch, enrichment: dict):
    """
    Render a chapter into two HTML strings:
      (text_html, notes_html)

    text_html   — scripture verses only, suitable for fast initial load.
                  Wrapped in <div class="scripture"> for CSS scoping.
    notes_html  — commentary blocks keyed by verse number via data-verse attributes.
                  None if the chapter has no notes.
    """
    head_lines = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="UTF-8">',
        f'<meta name="chapter-id" content="{slug}">',
    ]
    if prev: head_lines.append(f'<meta name="prev" content="{prev}">')
    if nxt:  head_lines.append(f'<meta name="next" content="{nxt}">')
    head_lines += ['<link rel="stylesheet" href="../style/main.css">', '</head>']

    header = [
        f'<h2 class="book-title">{_esc(ch.book)}</h2>',
        f'<p class="chapter-num">{ch.number}</p>',
        '<div class="score-legend">'
        '<span class="score-legend-item"><span class="score-dots">●●●●●</span> direct quotation</span>'
        '<span class="score-legend-item"><span class="score-dots">●●●○○</span> thematic parallel</span>'
        '<span class="score-legend-item"><span class="score-dots">●○○○○</span> loose connection</span>'
        '</div>',
    ]
    if ch.heading:
        header.append(f'<h3 class="chapter-heading">{_esc(ch.heading)}</h3>')

    text_verses  = []
    notes_blocks = []  # [(verse_num, html), ...]

    # Commentary CSS classes — these go into the notes file
    _NOTES_CLASSES = re.compile(
        r'class="(jst-block|etymology-block|rabbinical-block|lds-commentary-block|'
        r'fathers-block|ancient-block|donaldson-block|jsp-block|'
        r'semantic-quote|semantic-block|backlinks)"'
    )

    for verse in ch.verses:
        key = (verse.book.upper(), verse.chapter, verse.verse)
        enr = enrichment.get(key) or {}
        verse_lines = _render_verse(verse, enr)
        verse_html  = _linkify_refs('\n'.join(verse_lines))

        # Split text span line from commentary block lines
        # verse_lines[0] = <div class="verse" id="vN">
        # verse_lines[1] = <span class="verse-num">...</span><span class="verse-text">...</span>
        # verse_lines[2..N-1] = commentary blocks
        # verse_lines[-1] = </div>
        text_only_lines = []
        note_only_lines = []
        in_verse = False
        for line in verse_lines:
            if line.startswith('<div class="verse"'):
                in_verse = True
                text_only_lines.append(line)
            elif line == '</div>' and in_verse:
                in_verse = False
                text_only_lines.append(line)
            elif in_verse and _NOTES_CLASSES.search(line):
                note_only_lines.append(line)
            else:
                text_only_lines.append(line)

        text_verses.append('\n'.join(text_only_lines))
        if note_only_lines:
            notes_blocks.append((verse.verse, '\n'.join(note_only_lines)))

    text_html = '\n'.join(
        head_lines + ['<body>', '<div class="scripture">']
        + header + text_verses
        + ['</div>', '</body>', '</html>']
    )

    if notes_blocks:
        notes_parts = [
            f'<div data-verse="{vnum}">\n{content}\n</div>'
            for vnum, content in notes_blocks
        ]
        notes_html = (
            '<!DOCTYPE html>\n<html lang="en">\n<body>\n'
            + '\n'.join(notes_parts) + '\n'
            + '</body>\n</html>\n'
        )
    else:
        notes_html = None

    return text_html, notes_html


# ── Chapter renderer ───────────────────────────────────────────────────────────

def _render_chapter(ch, enrichment: dict, config) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!DOCTYPE html>',
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">',
        '<head>',
        f'  <title>{_esc(ch.book)} {ch.number}</title>',
        '  <link rel="stylesheet" type="text/css" href="../style/main.css"/>',
        '</head>',
        '<body>',
        f'<h2 class="book-title">{_esc(ch.book)}</h2>',
        f'<p class="chapter-num">{ch.number}</p>',
    ]
    if ch.heading:
        lines.append(f'<h3 class="chapter-heading">{_esc(ch.heading)}</h3>')

    for verse in ch.verses:
        key = (verse.book.upper(), verse.chapter, verse.verse)
        enr = enrichment.get(key) or {}
        lines.extend(_render_verse(verse, enr))

    lines += ['</body>', '</html>']
    return '\n'.join(lines)


def _render_verse(verse, enr: dict) -> list[str]:
    """
    Render one verse + all its annotations sorted by relevance score.
    Returns a list of HTML lines.
    """
    # ── Load correlation scores for this verse ────────────────────────────
    corr_file = _CORR_DIR / f"{verse.book}_{verse.chapter}_{verse.verse}.json"
    corr_data = {}
    if corr_file.exists():
        corr_data = json.loads(corr_file.read_text(encoding="utf-8"))

    # Best score per source key from correlation file
    source_scores: dict[str, float] = {}
    for m in corr_data.get("matches", []):
        src = m["source"]
        source_scores[src] = max(source_scores.get(src, 0.0), m["score"])

    def score(corr_key: str, default: float) -> float:
        return source_scores.get(corr_key, default)

    # ── Collect scored blocks ─────────────────────────────────────────────
    # Each entry: (score, html_string)
    blocks: list[tuple[float, str]] = []

    # ── JST ───────────────────────────────────────────────────────────────
    if hasattr(verse, 'jst') and verse.jst:
        blocks.append((
            score("jst", 0.90),
            f'<div class="jst-block">'
            f'<span class="source-label">{SOURCE_NAMES["jst"]}</span>'
            f'<div class="jst-text">{_esc(verse.jst)}</div>'
            f'</div>'
        ))

    # ── Word studies ──────────────────────────────────────────────────────
    if hasattr(verse, 'word_studies') and verse.word_studies:
        inner = ''.join(
            f'<div class="etymology-entry">'
            f'<span class="etym-word">{_esc(ws.word)}</span> — '
            f'<span class="etym-xlit">{_esc(ws.original)}</span>'
            + (f' <span class="etym-def">{_esc(ws.meaning)}</span>' if ws.meaning else '')
            + f'</div>'
            for ws in verse.word_studies
        )
        blocks.append((
            0.88,  # word studies are always highly relevant
            f'<div class="etymology-block">'
            f'<span class="etym-label">Word Study</span>'
            + inner +
            f'</div>'
        ))

    # ── Strong's (from enrichment) ────────────────────────────────────────
    if enr.get("etymology"):
        blocks.append((
            0.85,
            f'<div class="etymology-block">'
            f'<span class="etym-label">Strong\'s Concordance</span>'
            + ''.join(enr["etymology"]) +
            f'</div>'
        ))

    # ── Donaldson commentary ──────────────────────────────────────────────
    dona_file = _DONA_DIR / f"{verse.book}_{verse.chapter}_{verse.verse}.json"
    if dona_file.exists():
        dona_data = json.loads(dona_file.read_text(encoding="utf-8"))
        verse_text = getattr(verse, 'text', '') or ''
        cleaned = [_strip_verse_quote(p, verse_text) for p in dona_data.get("paragraphs", [])]
        cleaned = [p for p in cleaned if len(p.strip()) > 20]
        cleaned = [_truncate(p, 800) for p in cleaned[:12]]  # cap paragraphs + length
        if cleaned:
            paras = ''.join(f'<p class="donaldson-para">{_esc(p)}</p>' for p in cleaned)
            blocks.append((
                score("donaldson", 0.80),
                f'<div class="donaldson-block">'
                f'<span class="source-label">{SOURCE_NAMES["donaldson"]}</span>'
                + paras +
                f'</div>'
            ))

    # ── Verse.commentary (JD / HOC / GC from Donaldson compilation) ──────
    # Note: 'other' type is dropped — covered by Donaldson block above
    if hasattr(verse, 'commentary') and verse.commentary:
        for items, corr_key, label, css in [
            ([c for c in verse.commentary if c.source_type == 'jd'],
             "journal_of_discourses", SOURCE_NAMES["journal_of_discourses"], "jd-quote"),
            ([c for c in verse.commentary if c.source_type == 'hoc'],
             "history_of_church", SOURCE_NAMES["history_of_church"], "hoc-quote"),
            ([c for c in verse.commentary if c.source_type == 'gc'],
             "general_conference", SOURCE_NAMES["general_conference"], "gc-quote"),
        ]:
            if items:
                quotes = ''.join(
                    f'<div class="{css}">{_esc(c.text)}'
                    f'<span class="vol-ref"> — {_esc(c.attribution)}</span></div>'
                    for c in items
                )
                blocks.append((
                    score(corr_key, 0.25),
                    f'<div class="lds-commentary-block">'
                    f'<span class="source-label">{label}</span>'
                    + quotes +
                    f'</div>'
                ))

    # ── Enrichment sources ────────────────────────────────────────────────

    if enr.get("rashi"):
        blocks.append((
            score(_CORR_KEY["rashi"], 0.25),
            f'<div class="rabbinical-block">'
            f'<span class="source-label">Rashi</span>'
            + ''.join(f'<div class="rashi-comment">{_esc(c)}</div>' for c in enr["rashi"])
            + f'</div>'
        ))

    if enr.get("talmud"):
        blocks.append((
            score(_CORR_KEY["talmud"], 0.25),
            f'<div class="rabbinical-block">'
            f'<span class="source-label">Talmud</span>'
            + ''.join(
                f'<div class="talmud-ref">{_esc(r["text"])}'
                f'<span class="source-ref"> — {_esc(r["ref"])}</span></div>'
                for r in enr["talmud"]
            )
            + f'</div>'
        ))

    if enr.get("midrash"):
        blocks.append((
            score(_CORR_KEY["midrash"], 0.25),
            f'<div class="rabbinical-block">'
            f'<span class="source-label">Midrash</span>'
            + ''.join(
                f'<div class="midrash-ref">{_esc(r["text"])}'
                f'<span class="source-ref"> — {_esc(r["ref"])}</span></div>'
                for r in enr["midrash"]
            )
            + f'</div>'
        ))

    if enr.get("targum"):
        blocks.append((
            score(_CORR_KEY["targum"], 0.20),
            f'<div class="rabbinical-block">'
            f'<span class="source-label">Targum Onkelos</span>'
            f'<div class="talmud-ref">{_esc(enr["targum"])}</div>'
            f'</div>'
        ))

    if enr.get("zohar"):
        blocks.append((
            score(_CORR_KEY["zohar"], 0.20),
            f'<div class="rabbinical-block">'
            f'<span class="source-label">Zohar</span>'
            f'<div class="talmud-ref">{_esc(enr["zohar"])}</div>'
            f'</div>'
        ))

    if enr.get("jd"):
        quotes = ''.join(
            f'<div class="jd-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">JD Vol. {q["vol"]}</span></div>'
            for q in enr["jd"]
        )
        blocks.append((
            score(_CORR_KEY["jd"], 0.25),
            f'<div class="lds-commentary-block">'
            f'<span class="source-label">{SOURCE_NAMES["journal_of_discourses"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("hoc"):
        quotes = ''.join(
            f'<div class="hoc-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">HC Vol. {q["vol"]}</span></div>'
            for q in enr["hoc"]
        )
        blocks.append((
            score(_CORR_KEY["hoc"], 0.25),
            f'<div class="lds-commentary-block">'
            f'<span class="source-label">{SOURCE_NAMES["history_of_church"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("jsp"):
        quotes = ''.join(
            f'<div class="jsp-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">{_esc(q.get("source",""))}</span></div>'
            for q in enr["jsp"]
        )
        blocks.append((
            score(_CORR_KEY["jsp"], 0.25),
            f'<div class="jsp-block">'
            f'<span class="source-label">{SOURCE_NAMES["joseph_smith_papers"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("mcconkie"):
        quotes = ''.join(
            f'<div class="jd-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">{_esc(q.get("source",""))}</span></div>'
            for q in enr["mcconkie"]
        )
        blocks.append((
            score(_CORR_KEY["mcconkie"], 0.22),
            f'<div class="lds-commentary-block">'
            f'<span class="source-label">{SOURCE_NAMES["mcconkie"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("early_saints"):
        quotes = ''.join(
            f'<div class="jsp-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">{_esc(q.get("source",""))}</span></div>'
            for q in enr["early_saints"]
        )
        blocks.append((
            score(_CORR_KEY["early_saints"], 0.20),
            f'<div class="jsp-block">'
            f'<span class="source-label">Pioneer Journals</span>'
            + quotes + f'</div>'
        ))

    if enr.get("gutenberg_lds"):
        quotes = ''.join(
            f'<div class="jd-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">{_esc(q.get("source",""))}</span></div>'
            for q in enr["gutenberg_lds"]
        )
        blocks.append((
            score(_CORR_KEY["gutenberg_lds"], 0.20),
            f'<div class="lds-commentary-block">'
            f'<span class="source-label">{SOURCE_NAMES["gutenberg_lds"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("church_fathers"):
        quotes = ''.join(
            f'<div class="fathers-quote">{_esc(_truncate(q["text"]))}'
            f'<span class="vol-ref">{_esc(q.get("source",""))}</span></div>'
            for q in enr["church_fathers"]
        )
        blocks.append((
            score(_CORR_KEY["church_fathers"], 0.20),
            f'<div class="fathers-block">'
            f'<span class="source-label">{SOURCE_NAMES["church_fathers"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("ancient"):
        quotes = ''.join(
            f'<div class="ancient-quote">{_esc(q["text"])}'
            f'<span class="vol-ref">{_esc(q.get("source",""))}</span></div>'
            for q in enr["ancient"]
        )
        blocks.append((
            score(_CORR_KEY["ancient"], 0.20),
            f'<div class="ancient-block">'
            f'<span class="source-label">{SOURCE_NAMES["ancient_texts"]}</span>'
            + quotes + f'</div>'
        ))

    if enr.get("gc"):
        quotes = ''.join(
            f'<div class="gc-quote">{_esc(q["snippet"])}'
            + (f'<span class="vol-ref">{_esc(q.get("author",""))}, {q.get("year","")}</span>'
               if q.get("author") else '')
            + f'</div>'
            for q in enr["gc"]
        )
        blocks.append((
            score(_CORR_KEY["gc"], 0.22),
            f'<div class="lds-commentary-block">'
            f'<span class="source-label">{SOURCE_NAMES["general_conference"]}</span>'
            + quotes + f'</div>'
        ))

    # ── Semantic / correlation matches ────────────────────────────────────
    # Curate already filters, deduplicates, and sorts by score.
    # Render each as its own block so it lands in the right position
    # relative to the other scored blocks.
    curated = curate(
        corr_data.get("matches", []),
        verse.book, verse.chapter, verse.verse,
    )
    for m in curated:
        src   = _esc(m["source_label"])
        ref   = _esc(m.get("ref", ""))
        text  = _esc(_truncate(m["text"]))
        blocks.append((
            m["score"],
            f'<div class="semantic-quote">'
            f'<div class="semantic-meta">'
            f'<span class="semantic-source">{src}</span>'
            + (f'<span class="semantic-ref">{ref}</span>' if ref else '')
            + f'</div>'
            f'<div class="semantic-text">{text}</div>'
            f'</div>'
        ))

    # ── Deduplicate blocks by content fingerprint ─────────────────────────
    # Strips HTML tags to compare raw text; drops near-duplicate passages
    # that appear in both the Donaldson block and an enrichment index.
    def _fingerprint(html: str) -> str:
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html))[:120].strip().lower()

    seen_fps: set = set()
    deduped: list = []
    for score, html in blocks:
        fp = _fingerprint(html)
        if fp and fp not in seen_fps:
            seen_fps.add(fp)
            deduped.append((score, html))
    blocks = deduped

    # ── Sort all blocks by score descending ───────────────────────────────
    blocks.sort(key=lambda x: x[0], reverse=True)

    lines = [f'<div class="verse" id="v{verse.verse}">']
    lines.append(
        f'<span class="verse-num">{verse.verse}</span>'
        f'<span class="verse-text">{_esc(verse.text)}</span>'
    )
    # Inject score dots into each block's source-label line
    for block_score, html in blocks:
        if block_score > 0:
            dots = render_dots(score_to_dots(block_score))
            # Insert dots after the first source-label or etym-label span
            html = re.sub(
                r'(<span class="(?:source-label|etym-label|semantic-source)">[^<]*</span>)',
                r'\1' + dots,
                html, count=1
            )
        lines.append(html)
    lines.append('</div>')
    return lines


def _truncate(text: str, limit: int = 600) -> str:
    """Truncate at sentence boundary near limit, not mid-word."""
    if not text or len(text) <= limit:
        return text
    # Try to cut at last sentence-ending punctuation before limit
    cut = text[:limit]
    for punct in ('. ', '! ', '? ', '.\n'):
        pos = cut.rfind(punct)
        if pos > limit // 2:
            return cut[:pos + 1]
    # Fall back to last word boundary
    pos = cut.rfind(' ')
    return (cut[:pos] + '…') if pos > 0 else cut


def _esc(s: str) -> str:
    if not s:
        return ''
    return (str(s)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;'))


def _slug(s: str) -> str:
    return re.sub(r'[^\w]', '_', s).lower()


# ── Scripture reference auto-linker ────────────────────────────────────────────

# Maps every common abbreviation/name to (canonical_book_name, slug_prefix)
# slug_prefix matches _slug(book_name + "_")
_REF_MAP = {
    # Old Testament
    "genesis": "genesis", "gen": "genesis", "gen.": "genesis",
    "exodus": "exodus", "exod": "exodus", "exod.": "exodus", "ex": "exodus", "ex.": "exodus",
    "leviticus": "leviticus", "lev": "leviticus", "lev.": "leviticus",
    "numbers": "numbers", "num": "numbers", "num.": "numbers",
    "deuteronomy": "deuteronomy", "deut": "deuteronomy", "deut.": "deuteronomy", "dt": "deuteronomy",
    "joshua": "joshua", "josh": "joshua", "josh.": "joshua",
    "judges": "judges", "judg": "judges", "judg.": "judges",
    "ruth": "ruth",
    "1 samuel": "1_samuel", "1 sam": "1_samuel", "1 sam.": "1_samuel", "1sam": "1_samuel",
    "2 samuel": "2_samuel", "2 sam": "2_samuel", "2 sam.": "2_samuel", "2sam": "2_samuel",
    "1 kings": "1_kings", "1 kgs": "1_kings", "1 kgs.": "1_kings", "1kgs": "1_kings",
    "2 kings": "2_kings", "2 kgs": "2_kings", "2 kgs.": "2_kings", "2kgs": "2_kings",
    "1 chronicles": "1_chronicles", "1 chr": "1_chronicles", "1 chron": "1_chronicles",
    "2 chronicles": "2_chronicles", "2 chr": "2_chronicles", "2 chron": "2_chronicles",
    "ezra": "ezra", "nehemiah": "nehemiah", "neh": "nehemiah", "neh.": "nehemiah",
    "esther": "esther", "esth": "esther",
    "job": "job",
    "psalms": "psalms", "psalm": "psalms", "ps": "psalms", "ps.": "psalms", "psa": "psalms",
    "proverbs": "proverbs", "prov": "proverbs", "prov.": "proverbs",
    "ecclesiastes": "ecclesiastes", "eccl": "ecclesiastes", "ecc": "ecclesiastes",
    "song of solomon": "song_of_solomon", "song": "song_of_solomon", "ss": "song_of_solomon",
    "isaiah": "isaiah", "isa": "isaiah", "isa.": "isaiah",
    "jeremiah": "jeremiah", "jer": "jeremiah", "jer.": "jeremiah",
    "lamentations": "lamentations", "lam": "lamentations",
    "ezekiel": "ezekiel", "ezek": "ezekiel", "ezek.": "ezekiel", "eze": "ezekiel",
    "daniel": "daniel", "dan": "daniel", "dan.": "daniel",
    "hosea": "hosea", "hos": "hosea", "joel": "joel", "amos": "amos",
    "obadiah": "obadiah", "obad": "obadiah",
    "jonah": "jonah", "jon": "jonah", "micah": "micah", "mic": "micah",
    "nahum": "nahum", "nah": "nahum", "habakkuk": "habakkuk", "hab": "habakkuk",
    "zephaniah": "zephaniah", "zeph": "zephaniah",
    "haggai": "haggai", "hag": "haggai",
    "zechariah": "zechariah", "zech": "zechariah",
    "malachi": "malachi", "mal": "malachi",
    # New Testament
    "matthew": "matthew", "matt": "matthew", "matt.": "matthew", "mt": "matthew",
    "mark": "mark", "mk": "mark",
    "luke": "luke", "lk": "luke",
    "john": "john", "jn": "john",
    "acts": "acts",
    "romans": "romans", "rom": "romans", "rom.": "romans",
    "1 corinthians": "1_corinthians", "1 cor": "1_corinthians", "1cor": "1_corinthians",
    "2 corinthians": "2_corinthians", "2 cor": "2_corinthians", "2cor": "2_corinthians",
    "galatians": "galatians", "gal": "galatians",
    "ephesians": "ephesians", "eph": "ephesians",
    "philippians": "philippians", "phil": "philippians",
    "colossians": "colossians", "col": "colossians",
    "1 thessalonians": "1_thessalonians", "1 thess": "1_thessalonians",
    "2 thessalonians": "2_thessalonians", "2 thess": "2_thessalonians",
    "1 timothy": "1_timothy", "1 tim": "1_timothy",
    "2 timothy": "2_timothy", "2 tim": "2_timothy",
    "titus": "titus", "tit": "titus",
    "philemon": "philemon", "phlm": "philemon",
    "hebrews": "hebrews", "heb": "hebrews",
    "james": "james", "jas": "james",
    "1 peter": "1_peter", "1 pet": "1_peter",
    "2 peter": "2_peter", "2 pet": "2_peter",
    "1 john": "1_john", "1 jn": "1_john",
    "2 john": "2_john", "3 john": "3_john",
    "jude": "jude",
    "revelation": "revelation", "rev": "revelation", "rev.": "revelation",
    # Book of Mormon
    "1 nephi": "1_nephi", "1 ne": "1_nephi", "1ne": "1_nephi",
    "2 nephi": "2_nephi", "2 ne": "2_nephi", "2ne": "2_nephi",
    "jacob": "jacob", "enos": "enos", "jarom": "jarom", "omni": "omni",
    "mosiah": "mosiah", "alma": "alma",
    "helaman": "helaman", "hel": "helaman",
    "3 nephi": "3_nephi", "3 ne": "3_nephi",
    "4 nephi": "4_nephi", "4 ne": "4_nephi",
    "mormon": "mormon", "morm": "mormon",
    "ether": "ether", "moroni": "moroni", "moro": "moroni",
    # D&C / PGP
    "doctrine and covenants": "doctrine_and_covenants",
    "d&c": "doctrine_and_covenants", "dc": "doctrine_and_covenants",
    "moses": "moses", "abraham": "abraham", "abr": "abraham",
}

# Build regex: longest names first to avoid partial matches
_REF_NAMES = sorted(_REF_MAP.keys(), key=len, reverse=True)
_REF_NAMES_ESC = [re.escape(n) for n in _REF_NAMES]
_REF_RE = re.compile(
    r'\b(' + '|'.join(_REF_NAMES_ESC) + r')\.?\s+(\d+):(\d+)',
    re.IGNORECASE
)


def _linkify_refs(html: str) -> str:
    """
    Replace scripture references in commentary HTML with anchor links.
    Only applied to text nodes inside annotation divs, not verse text itself.
    Skips anything inside an existing <a> tag.
    """
    def replace(m):
        name = m.group(1).rstrip('.')
        ch   = m.group(2)
        v    = m.group(3)
        slug_prefix = _REF_MAP.get(name.lower(), _slug(name))
        slug = f"{slug_prefix}_{ch}"
        display = m.group(0)
        return f'<a class="ref-link" href="../chapters/{slug}.html#v{v}">{display}</a>'

    # Only linkify inside annotation blocks — skip the verse-text span
    # Strategy: split on verse-text span, linkify everything after it
    marker = 'class="verse-text"'
    idx = html.find(marker)
    if idx == -1:
        return html
    # Find end of the verse-text span
    end = html.find('</span>', idx)
    if end == -1:
        return html
    end += len('</span>')

    before = html[:end]
    after  = html[end:]

    # Don't linkify inside existing <a> tags
    def linkify_outside_anchors(text):
        result = []
        pos = 0
        for a_match in re.finditer(r'<a[\s>].*?</a>', text, re.DOTALL):
            chunk = text[pos:a_match.start()]
            result.append(_REF_RE.sub(replace, chunk))
            result.append(a_match.group(0))
            pos = a_match.end()
        result.append(_REF_RE.sub(replace, text[pos:]))
        return ''.join(result)

    return before + linkify_outside_anchors(after)
