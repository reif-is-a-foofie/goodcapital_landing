#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(line_buffering=True)  # flush on every newline even when redirected
"""
LDS Scriptures — Enriched Edition Pipeline
==========================================

Usage:
  python pipeline.py [--quick] [--books Genesis Exodus ...]

  --quick       Process only the first 3 books (for testing)
  --books ...   Process only the named books

Stages:
  1. Extract PDF text using word-box method (fixes word-merge bug)
  2. Parse into Volume/Book/Chapter/Verse structure
  3. Download & index all enrichment sources (cached after first run)
  4. Assemble epub3 with embedded fonts and per-verse enrichment
"""

import sys
import os
import argparse
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Add project root to path ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

import config as cfg
from extract.epub_extractor    import extract_from_mobi, extract_epub_text
from extract.donaldson_parser  import parse_donaldson, verses_by_ref
from extract.scripture_downloader import download_all_volumes as download_json_volumes
from extract.catalog           import save_catalog, load_catalog, catalog_to_volumes
from epub.builder           import build_epub, build_web, init_web, write_book_chapters, build_backlinks

# Sources
from sources import strongs, sefaria
from sources import journal_discourses  as jd
from sources import history_church      as hoc
from sources import joseph_smith_papers as jsp
from sources import mcconkie
from sources import general_conference  as gc
from sources import early_saints
from sources import gutenberg_lds
from sources import ancient_myths
from sources import embeddings as sem
from sources import church_fathers

_push_lock = threading.Lock()


def _push_web(output_dir: str, book_name: str = ""):
    """Commit and push web chapters in the background. Safe to call concurrently."""
    import subprocess
    repo = str(Path(output_dir).parent)
    with _push_lock:
        msg = f"auto: {book_name} chapters" if book_name else "auto: update chapters"
        subprocess.run(['git', '-C', repo, 'add', 'library/'], capture_output=True)
        r = subprocess.run(['git', '-C', repo, 'commit', '-m', msg], capture_output=True)
        if b'nothing to commit' in r.stdout + r.stderr:
            return
        subprocess.run(['git', '-C', repo, 'push'], capture_output=True)
        print(f"  → pushed {book_name or 'web'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="LDS Enriched Scripture Pipeline")
    parser.add_argument("--quick",        action="store_true", help="Process first 3 books only")
    parser.add_argument("--books",        nargs="+", help="Specific books to include")
    parser.add_argument("--no-net",       action="store_true", help="Skip network sources, use cache only")
    parser.add_argument("--catalog-only", action="store_true", help="Parse + save catalog, then exit")
    args = parser.parse_args()

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    os.makedirs(cfg.CACHE_DIR,  exist_ok=True)

    # ── Stage 1: Source extraction ────────────────────────────────────────────
    print("\n═══ Stage 1: Text Extraction ═══")
    text_cache = Path(cfg.CACHE_DIR) / "source_text.txt"

    # If the full PDF (all standard works) is available, prefer it.
    # It contains the complete Donaldson compilation for every book.
    full_pdf = cfg.FULL_PDF_PATH
    full_pdf_available = (
        full_pdf and
        Path(full_pdf).exists() and
        Path(full_pdf).stat().st_size > 100_000
    )

    if full_pdf_available:
        # Invalidate OT-only cache if full PDF is now available
        marker = Path(cfg.CACHE_DIR) / "source_text_full.marker"
        if not marker.exists():
            print(f"  Full PDF detected — rebuilding text cache from complete compilation")
            text_cache.unlink(missing_ok=True)
            marker.touch()

    if text_cache.exists():
        print(f"  Using cached text: {text_cache}")
        raw_text = text_cache.read_text(encoding="utf-8")
    elif full_pdf_available:
        print(f"  Extracting from full PDF (all standard works): {full_pdf}")
        from extract.pdf_extractor import extract_full_pdf
        raw_text = extract_full_pdf(full_pdf)
        text_cache.write_text(raw_text, encoding="utf-8")
        print(f"  Cached to: {text_cache}")
    else:
        print("  Full PDF not available — using OT mobi + JSON for other volumes")
        if Path(cfg.EPUB_CACHE_PATH).exists():
            raw_text = extract_epub_text(cfg.EPUB_CACHE_PATH)
        else:
            raw_text = extract_from_mobi(cfg.MOBI_PATH)
        text_cache.write_text(raw_text, encoding="utf-8")
        print(f"  Cached to: {text_cache}")

    # ── Stage 2: Structure parsing ────────────────────────────────────────────
    print("\n═══ Stage 2: Parsing Structure ═══")
    volumes = parse_donaldson(raw_text)

    # If full PDF gives us all 5 volumes, we're done.
    # Otherwise supplement with clean JSON for NT, BoM, D&C, PGP.
    have_volumes = {v.name for v in volumes if sum(len(b.chapters) for b in v.books) > 0}
    missing = [n for n in ["New Testament","Book of Mormon",
                            "Doctrine and Covenants","Pearl of Great Price"]
               if n not in have_volumes]
    if missing:
        print(f"\n  Supplementing from JSON: {', '.join(missing)}")
        json_vols = download_json_volumes(skip_ot=True, no_net=args.no_net)
        for jv in json_vols:
            if jv.name in missing:
                volumes.append(jv)
                print(f"  + {jv.name}: {sum(len(b.chapters) for b in jv.books)} chapters")

    # Filter books if requested
    include_books = args.books or cfg.INCLUDE_BOOKS
    if args.quick:
        for vol in volumes:
            vol.books = vol.books[:3]
        volumes = [v for v in volumes if v.books]
        print(f"  Quick mode: limited to 3 books per volume")
    elif include_books:
        include_upper = {b.upper() for b in include_books}
        for vol in volumes:
            vol.books = [b for b in vol.books if b.name.upper() in include_upper]
        volumes = [v for v in volumes if v.books]

    total_verses = sum(
        len(ch.verses)
        for vol in volumes for bk in vol.books for ch in bk.chapters
    )
    total_books = sum(len(vol.books) for vol in volumes)
    print(f"  {len(volumes)} volumes, {total_books} books, {total_verses:,} verses")

    verse_index = verses_by_ref(volumes)

    # ── Save verse catalog (always — independent of source downloads) ─────────
    save_catalog(volumes)

    if args.catalog_only:
        print(f"\n✓ Catalog saved. Run without --catalog-only to build epub.")
        return

    # ── Stage 3: Download enrichment sources ─────────────────────────────────
    print("\n═══ Stage 3: Enrichment Sources ═══")

    jd_index          = {}
    hoc_index         = {}
    jsp_index         = {}
    mcconkie_index    = {}
    early_saints_idx  = {}
    gutenberg_idx     = {}
    ancient_idx       = {}
    cf_index          = {}

    if not args.no_net:
        if cfg.SOURCES.get("journal_of_discourses"):
            print("\n  → Journal of Discourses (26 vols)")
            jd_texts = jd.download_all_volumes()
            jd_index = jd.build_index(jd_texts)

        if cfg.SOURCES.get("history_of_church"):
            print("\n  → History of the Church (7 vols)")
            hoc_texts = hoc.download_all_volumes()
            hoc_index = hoc.build_index(hoc_texts)

        if cfg.SOURCES.get("joseph_smith_papers"):
            print("\n  → Joseph Smith Papers")
            jsp_docs = jsp.download_all_documents()
            jsp_index = jsp.build_index(jsp_docs)

        if any(cfg.SOURCES.get(k) for k in ["mcconkie","teachings_pjs","words_joseph_smith"]):
            print("\n  → McConkie / Teachings of Joseph Smith / Words of JS")
            mcc_docs = mcconkie.download_all()
            mcconkie_index = mcconkie.build_index(mcc_docs)

        if any(cfg.SOURCES.get(k) for k in ["wilford_woodruff","heber_kimball","benjamin_johnson"]):
            print("\n  → Early Saints Journals (Woodruff, Kimball, B.F. Johnson)")
            es_docs = early_saints.download_all()
            early_saints_idx = early_saints.build_index(es_docs)

        if any(cfg.SOURCES.get(k) for k in ["parley_pratt","lucy_mack_smith","brigham_young","william_clayton"]):
            print("\n  → Gutenberg LDS texts (Pratt, Lucy Smith, Brigham Young, Clayton)")
            gb_docs = gutenberg_lds.download_all()
            gutenberg_idx = gutenberg_lds.build_index(gb_docs)

        if any(cfg.SOURCES.get(k) for k in [
            "book_of_enoch","book_of_jubilees","gilgamesh","enuma_elish",
            "josephus","testament_patriarchs"
        ]):
            print("\n  → Ancient texts (Enoch, Jubilees, Gilgamesh, Josephus...)")
            anc_docs = ancient_myths.download_all()
            ancient_idx = ancient_myths.build_index(anc_docs)

        if cfg.SOURCES.get("church_fathers"):
            print("\n  → Church Fathers (Origen, Clement, Irenaeus, Justin Martyr...)")
            cf_docs = church_fathers.download_all()
            cf_index = church_fathers.build_index(cf_docs)

        if cfg.SOURCES.get("strongs_etymology"):
            print("\n  → Strong's Concordance (Hebrew + Greek)")
            strongs.load_hebrew()
            strongs.load_greek()

        if any(cfg.SOURCES.get(k) for k in ["sefaria_rashi","sefaria_talmud","sefaria_midrash","sefaria_targum","sefaria_zohar"]):
            print("\n  → Sefaria API (Rashi, Talmud, Midrash, Targum, Zohar) — on-demand per verse")

        if cfg.SOURCES.get("general_conference"):
            print("\n  → General Conference (1971–present) — on-demand per verse")

        # Build semantic index from all downloaded source files
        if cfg.SOURCES.get("semantic_search"):
            print("\n  → Building semantic embedding index...")
            sem.load_all_cached_sources()
            sem.build_index()
    else:
        print("  --no-net: using cached data only")
        jd_index         = jd._load_index()           or {}
        hoc_index        = hoc._load_index()          or {}
        jsp_index        = jsp._load_index()          or {}
        mcconkie_index   = mcconkie._load_index()     or {}
        early_saints_idx = early_saints._load_index() or {}
        gutenberg_idx    = gutenberg_lds._load_index()or {}
        ancient_idx      = ancient_myths._load_index() or {}
        cf_index         = church_fathers._load_index() or {}

    # ── Stage 4: Build per-verse enrichment ──────────────────────────────────
    print("\n═══ Stage 4: Building Enrichment ═══")
    enrichment = {}

    _print_lock = threading.Lock()

    def _enrich_book(bk, cfg, args,
                     jd_index, hoc_index, jsp_index, mcconkie_index,
                     early_saints_idx, gutenberg_idx, ancient_idx, cf_index):
        """Return a partial enrichment dict covering all verses in *bk*."""
        book_enr = {}
        verse_count = 0
        with _print_lock:
            print(f"  {bk.name} ({sum(len(c.verses) for c in bk.chapters)} verses)...")
        for ch in bk.chapters:
            for verse in ch.verses:
                key = (verse.book.upper(), verse.chapter, verse.verse)
                enr = {}

                # Donaldson inline commentary (from the compilation itself)
                if cfg.SOURCES.get("donaldson_commentary"):
                    paras = getattr(verse, 'donaldson', [])
                    if paras:
                        enr["donaldson"] = paras

                # Etymology — verse-accurate Strong's via OSHB tagged text
                if cfg.SOURCES.get("strongs_etymology"):
                    is_ot = verse.book.upper() in strongs.OT_BOOKS
                    if is_ot:
                        entries = strongs.get_verse_strongs(
                            verse.book, verse.chapter, verse.verse,
                            max_words=cfg.MAX_STRONGS_WORDS_PER_VERSE,
                        )
                    else:
                        entries = strongs.get_verse_strongs_nt(
                            verse.book, verse.chapter, verse.verse,
                            verse_text=verse.text,
                            max_words=cfg.MAX_STRONGS_WORDS_PER_VERSE,
                        )
                    etym_html = [strongs.format_etymology_html(e) for e in entries]
                    etym_html = [h for h in etym_html if h]
                    if etym_html:
                        enr["etymology"] = etym_html

                # Rashi (OT only, network)
                if cfg.SOURCES.get("sefaria_rashi") and not args.no_net:
                    comments = sefaria.get_rashi(
                        verse.book, verse.chapter, verse.verse,
                        max_comments=cfg.MAX_RASHI_COMMENTS_PER_VERSE
                    )
                    if comments:
                        enr["rashi"] = comments

                # Talmud + Midrash
                if (cfg.SOURCES.get("sefaria_talmud") or cfg.SOURCES.get("sefaria_midrash")) \
                   and not args.no_net:
                    links = sefaria.get_links(
                        verse.book, verse.chapter, verse.verse,
                        max_talmud=cfg.MAX_TALMUD_REFS_PER_VERSE,
                        max_midrash=cfg.MAX_RASHI_COMMENTS_PER_VERSE,
                    )
                    if links["talmud"]:  enr["talmud"]  = links["talmud"]
                    if links["midrash"]: enr["midrash"] = links["midrash"]

                # Sefaria extended (Targum, Zohar)
                if any(cfg.SOURCES.get(k) for k in ["sefaria_targum","sefaria_zohar"]) \
                   and not args.no_net:
                    if cfg.SOURCES.get("sefaria_targum"):
                        t = sefaria.get_targum(verse.book, verse.chapter, verse.verse)
                        if t: enr["targum"] = t
                    if cfg.SOURCES.get("sefaria_zohar"):
                        z = sefaria.get_zohar(verse.book, verse.chapter, verse.verse)
                        if z: enr["zohar"] = z

                # Journal of Discourses
                if cfg.SOURCES.get("journal_of_discourses") and jd_index:
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = jd_index.get(vk, [])[:cfg.MAX_JD_QUOTES_PER_VERSE]
                    if q: enr["jd"] = q

                # History of the Church
                if cfg.SOURCES.get("history_of_church") and hoc_index:
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = hoc_index.get(vk, [])[:cfg.MAX_HOC_QUOTES_PER_VERSE]
                    if q: enr["hoc"] = q

                # Joseph Smith Papers
                if cfg.SOURCES.get("joseph_smith_papers") and jsp_index:
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = jsp_index.get(vk, [])[:cfg.MAX_JSP_QUOTES_PER_VERSE]
                    if q: enr["jsp"] = q

                # McConkie + Teachings of JS + Words of JS
                if mcconkie_index:
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = mcconkie_index.get(vk, [])[:cfg.MAX_MCCONKIE_PER_VERSE]
                    if q: enr["mcconkie"] = q

                # Early Saints journals (Woodruff, Kimball, B.F. Johnson)
                if early_saints_idx:
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = early_saints_idx.get(vk, [])[:cfg.MAX_EARLY_SAINTS_PER_VERSE]
                    if q: enr["early_saints"] = q

                # Gutenberg LDS (Pratt, Lucy Smith, Brigham Young, Clayton)
                if gutenberg_idx:
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = gutenberg_idx.get(vk, [])[:cfg.MAX_GUTENBERG_LDS_PER_VERSE]
                    if q: enr["gutenberg_lds"] = q

                # Church Fathers
                if cfg.SOURCES.get("church_fathers"):
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    q = cf_index.get(vk) or church_fathers.get_quotes(
                        verse.book, verse.chapter, verse.verse, max_quotes=2)
                    if q: enr["church_fathers"] = q[:2]

                # Ancient myths & parallels
                if ancient_idx or cfg.SOURCES.get("book_of_enoch"):
                    vk = f"{verse.book.upper()}_{verse.chapter}_{verse.verse}"
                    if ancient_idx:
                        q = ancient_idx.get(vk, [])[:cfg.MAX_ANCIENT_PER_VERSE]
                    else:
                        q = ancient_myths.get_parallels(verse.book, verse.chapter, verse.verse)[:cfg.MAX_ANCIENT_PER_VERSE]
                    if q: enr["ancient"] = q

                # General Conference (network, on-demand)
                if cfg.SOURCES.get("general_conference") and not args.no_net:
                    q = gc.get_quotes(verse.book, verse.chapter, verse.verse,
                                      max_quotes=cfg.MAX_GC_QUOTES_PER_VERSE)
                    if q: enr["gc"] = q

                # Semantic matches — hidden connections across all sources
                if cfg.SOURCES.get("semantic_search"):
                    matches = sem.search(
                        verse.text, verse.book, verse.chapter, verse.verse,
                        top_k=cfg.MAX_SEMANTIC_PER_VERSE,
                        min_score=cfg.SEMANTIC_MIN_SCORE,
                    )
                    # Filter out sources already covered by reference matching
                    already = {q.get("source","") for q in
                               enr.get("jd",[]) + enr.get("hoc",[]) +
                               enr.get("mcconkie",[]) + enr.get("ancient",[])}
                    novel = [m for m in matches
                             if m["text"][:60] not in str(already)]
                    if novel: enr["semantic"] = novel

                if enr:
                    book_enr[key] = enr
                verse_count += 1

        return book_enr, verse_count

    # ── Init web reader (toc + CSS) before enrichment so it's live immediately ─
    web_slugs = None
    if cfg.WEB_OUTPUT_DIR:
        print("\n═══ Stage 4a: Web reader init ═══")
        web_slugs = init_web(volumes, cfg, cfg.WEB_OUTPUT_DIR)
        threading.Thread(
            target=_push_web, args=(cfg.WEB_OUTPUT_DIR, "toc"), daemon=True
        ).start()

    # Collect all books across volumes to submit as concurrent tasks
    all_books = [bk for vol in volumes for bk in vol.books]

    processed = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(
                _enrich_book, bk, cfg, args,
                jd_index, hoc_index, jsp_index, mcconkie_index,
                early_saints_idx, gutenberg_idx, ancient_idx, cf_index,
            ): bk
            for bk in all_books
        }
        for future in as_completed(futures):
            bk = futures[future]
            book_enr, verse_count = future.result()
            enrichment.update(book_enr)
            processed += verse_count

            # Stream-deploy: write this book's chapters and push live
            if cfg.WEB_OUTPUT_DIR and web_slugs:
                write_book_chapters(bk, enrichment, cfg, cfg.WEB_OUTPUT_DIR, web_slugs)
                threading.Thread(
                    target=_push_web, args=(cfg.WEB_OUTPUT_DIR, bk.name), daemon=True
                ).start()

    enriched_count = len(enrichment)
    print(f"\n  {processed:,} verses processed, {enriched_count:,} have enrichment")

    # ── Stage 5: Build epub ───────────────────────────────────────────────────
    print("\n═══ Stage 5: Building epub ═══")
    output = build_epub(volumes, enrichment, cfg, cfg.EPUB_OUTPUT_PATH)
    size_mb = Path(output).stat().st_size / 1_048_576
    print(f"  epub: {output} ({size_mb:.1f} MB)")

    # ── Stage 6: Backlinks + final web push ──────────────────────────────────
    if cfg.WEB_OUTPUT_DIR:
        print("\n═══ Stage 6: Backlinks ═══")
        build_backlinks(cfg.WEB_OUTPUT_DIR)
        _push_web(cfg.WEB_OUTPUT_DIR, "final")

    print(f"\n✓ Done!")


if __name__ == "__main__":
    main()
