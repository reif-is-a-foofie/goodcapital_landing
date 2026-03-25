"""
LDS Scripture Pipeline — Configuration
Toggle sources and output options here.
"""

import os

# ── Source document paths ─────────────────────────────────────────────────────
# The full annotated PDF (all 5 standard works, Donaldson compilation) lives on
# the "disk of knowledge" external drive. When mounted, set FULL_PDF_PATH below.
# When not available, the pipeline falls back to the OT mobi + JSON for other volumes.

FULL_PDF_PATH = "/Users/reify/Downloads/LDS Scriptures.pdf"

# OT mobi fallback (always available in archive)
MOBI_PATH = '/Users/reify/Downloads/Reif_Machine_Archive_2026-03-19/LDS/01-Old-Testament-kindle/LDS Scriptures - 01-Old-Testament (2)/LDS Scriptures - 01-Old-Testament - 01-Old-Testament-kindle.mobi'
EPUB_CACHE_PATH = "/tmp/lds_ot.epub"  # pre-existing OT epub conversion

# Archive PDF (currently 0 bytes — placeholder)
PDF_PATH = "/Users/reify/Downloads/Reif_Machine_Archive_2026-03-19/LDS/LDS Scriptures.pdf"

OUTPUT_DIR = "/Users/reify/Classified/goodcapital_landing/lds_pipeline/output"
CACHE_DIR  = "/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache"

# ── Source toggles ────────────────────────────────────────────────────────────
SOURCES = {
    # ── Donaldson inline commentary (extracted from the compilation itself) ──
    "donaldson_commentary":    True,   # Lee Donaldson's per-verse notes (embedded in source PDF)

    # ── Word study ──────────────────────────────────────────────────────────
    "strongs_etymology":       True,   # Hebrew/Greek word roots (Strong's concordance)

    # ── Rabbinical / Jewish ─────────────────────────────────────────────────
    "sefaria_rashi":           True,   # Rashi commentary (Torah + Prophets)
    "sefaria_talmud":          True,   # Talmud cross-references (Sefaria API)
    "sefaria_midrash":         True,   # Midrash Rabbah
    "sefaria_targum":          True,   # Targum Onkelos (Aramaic Torah paraphrase)
    "sefaria_zohar":           False,  # Zohar — Sefaria has no English translation, skip

    # ── LDS core histories ──────────────────────────────────────────────────
    "journal_of_discourses":   True,   # 26 vols, early LDS leaders
    "history_of_church":       True,   # B.H. Roberts 7 vols
    "joseph_smith_papers":     True,   # JSP scraper (King Follett, Lectures on Faith, etc.)

    # ── LDS doctrinal works ─────────────────────────────────────────────────
    "mcconkie":                True,   # Mormon Doctrine + DNTC (Archive.org)
    "teachings_pjs":           True,   # Teachings of the Prophet Joseph Smith
    "words_joseph_smith":      True,   # Words of Joseph Smith (Ehat & Cook)

    # ── General Conference (modern prophets & apostles) ─────────────────────
    "general_conference":      True,   # 1971–present, churchofjesuschrist.org

    # ── Early Church journals (firsthand accounts of Joseph Smith) ──────────
    "wilford_woodruff":        True,   # Wilford Woodruff Journal
    "heber_kimball":           True,   # Heber C. Kimball Journal
    "benjamin_johnson":        True,   # B.F. Johnson Letter (private JS teachings)

    # ── Early Church autobiography / biography ──────────────────────────────
    "parley_pratt":            True,   # Parley P. Pratt Autobiography (Gutenberg)
    "lucy_mack_smith":         True,   # Lucy Mack Smith History (Gutenberg)
    "brigham_young":           True,   # Discourses of Brigham Young (Gutenberg)
    "william_clayton":         True,   # William Clayton Journal (Gutenberg)

    # ── Ancient texts & mythology ───────────────────────────────────────────
    "book_of_enoch":           True,   # 1 Enoch — curated parallels + full text
    "book_of_jubilees":        True,   # Book of Jubilees
    "gilgamesh":               True,   # Epic of Gilgamesh (flood parallel)
    "enuma_elish":             True,   # Babylonian creation myth (Genesis parallel)
    "josephus":                True,   # Josephus, Antiquities of the Jews
    "testament_patriarchs":    True,   # Testament of the Twelve Patriarchs

    # ── Church Fathers (pre-Nicene Christianity) ────────────────────────────
    # Origen, Clement, Irenaeus, Justin Martyr — preserved doctrines matching
    # LDS theology before they were suppressed after Nicaea (325 AD)
    "church_fathers":          True,

    # ── Semantic search ─────────────────────────────────────────────────────
    # Finds conceptually similar passages across ALL sources even without
    # explicit verse citations — surfaces hidden connections
    "semantic_search":         True,   # local embedding model, no API needed
}

# ── Which books of scripture to process ──────────────────────────────────────
INCLUDE_BOOKS = None  # None = all; e.g. ["Genesis", "Exodus"] to limit

# ── Commentary density ────────────────────────────────────────────────────────
MAX_STRONGS_WORDS_PER_VERSE    = 5
MAX_RASHI_COMMENTS_PER_VERSE   = 2
MAX_TALMUD_REFS_PER_VERSE      = 2
MAX_MIDRASH_REFS_PER_VERSE     = 1
MAX_TARGUM_PER_VERSE           = 1
MAX_ZOHAR_PER_VERSE            = 1
MAX_JD_QUOTES_PER_VERSE        = 2
MAX_HOC_QUOTES_PER_VERSE       = 1
MAX_JSP_QUOTES_PER_VERSE       = 1
MAX_MCCONKIE_PER_VERSE         = 2
MAX_GC_QUOTES_PER_VERSE        = 2
MAX_EARLY_SAINTS_PER_VERSE     = 2
MAX_GUTENBERG_LDS_PER_VERSE    = 2
MAX_ANCIENT_PER_VERSE          = 2

# Semantic search
MAX_SEMANTIC_PER_VERSE         = 3     # novel matches not found by reference scan
SEMANTIC_MIN_SCORE             = 0.38  # cosine similarity threshold (0–1)

# ── Output ────────────────────────────────────────────────────────────────────
EPUB_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "LDS_Scriptures_Enriched.epub")
WEB_OUTPUT_DIR   = "/Users/reify/Classified/goodcapital_landing/library"  # None to skip web build
EPUB_TITLE = "LDS Scriptures — Enriched Edition"
EPUB_AUTHOR = "Various"
EPUB_LANGUAGE = "en"

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_DIR = "/Users/reify/Classified/goodcapital_landing/lds_pipeline/epub/fonts"
FONT_SCRIPTURE    = "EBGaramond-Regular.otf"
FONT_SCRIPTURE_IT = "EBGaramond-Italic.otf"
FONT_COMMENTARY   = "CrimsonPro-Regular.ttf"
FONT_COMMENTARY_IT= "CrimsonPro-Italic.ttf"
