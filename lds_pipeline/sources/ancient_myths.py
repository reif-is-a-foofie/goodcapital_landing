"""
Ancient myths, legends, and pseudepigrapha with parallels to LDS scripture.

Sources:
  Book of Enoch (1 Enoch) — R.H. Charles trans. — Project Gutenberg
  Book of Jubilees — R.H. Charles trans. — sacred-texts.com
  Epic of Gilgamesh — Project Gutenberg
  Enuma Elish — L.W. King trans. — public domain
  Testament of the Twelve Patriarchs — R.H. Charles — Archive.org
  Josephus, Antiquities of the Jews — Sefaria API + Gutenberg
  Apocalypse of Abraham — Marquette PDF

PARALLEL MAPPING:
Many ancient texts don't cite scripture by reference, so we maintain
a curated verse → text mapping for high-value parallels. This is
supplemented by automated reference scanning.
"""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("/Users/reify/Classified/goodcapital_landing/lds_pipeline/cache/ancient_myths")

TEXTS = {
    "book_of_enoch": {
        "title": "Book of Enoch (1 Enoch)",
        "short": "1 Enoch",
        "url": "https://www.gutenberg.org/cache/epub/77935/pg77935.txt",
    },
    "book_of_jubilees": {
        "title": "Book of Jubilees",
        "short": "Book of Jubilees",
        "url": "https://www.gutenberg.org/cache/epub/8081/pg8081.txt",
    },
    "gilgamesh": {
        "title": "Epic of Gilgamesh",
        "short": "Epic of Gilgamesh",
        "url": "https://www.gutenberg.org/cache/epub/18897/pg18897.txt",
    },
    "enuma_elish": {
        "title": "Enuma Elish (Babylonian Creation Epic)",
        "short": "Enuma Elish",
        "url": "https://www.gutenberg.org/cache/epub/23873/pg23873.txt",
    },
    "testament_twelve_patriarchs": {
        "title": "Testaments of the Twelve Patriarchs",
        "short": "Testament of the Patriarchs",
        "url": "https://www.gutenberg.org/cache/epub/11827/pg11827.txt",
    },
    "josephus_antiquities": {
        "title": "Josephus, Antiquities of the Jews",
        "short": "Josephus, Antiquities",
        "url": "https://www.gutenberg.org/files/2848/2848-0.txt",
    },
}


# ── Curated parallel mapping ──────────────────────────────────────────────────
# verse_key → list of {source, excerpt, relevance_note}
# These are hand-curated parallels that automated scanning won't catch
# because the ancient texts don't cite scripture references.

CURATED_PARALLELS = {
    # Genesis 1 — Creation
    "GENESIS_1_1": [
        {"source": "Enuma Elish", "note": "Babylonian creation parallel",
         "excerpt": "When on high the heaven had not been named, firm ground below had not been called by name, naught but primordial Apsu, their begetter, and Tiamat, she who bore them all, their waters commingling as a single body — no reed hut had been matted, no marsh land had appeared..."},
        {"source": "Book of Jubilees 2:1-3", "note": "Jubilees account of creation days",
         "excerpt": "For on the first day He created the heavens which are above and the earth and the waters and all the spirits which serve before him — the angels of the presence, and the angels of sanctification..."},
    ],
    "GENESIS_1_2": [
        {"source": "Book of Enoch 69:16-17", "note": "Enoch on the spirit moving on the waters",
         "excerpt": "And the oath was sworn by means of it, and the heaven was suspended before the world was created, and for ever. And through it the earth was founded upon the water, and from the secret recesses of the mountains come beautiful waters, from the creation of the world and unto eternity."},
    ],
    "GENESIS_1_26": [
        {"source": "Book of Jubilees 2:14", "note": "Jubilees — creation of man in God's image",
         "excerpt": "And after all this He created man, a man and a woman created He them, and gave them dominion over all that is upon the earth..."},
    ],
    # Genesis 2 — Garden of Eden
    "GENESIS_2_7": [
        {"source": "Book of Enoch 98:3", "note": "Enoch on the creation of man's spirit",
         "excerpt": "For ye have been created like the holy ones of heaven, eternal spirits, not dying unto all the generations of the world; therefore did He give you power..."},
    ],
    # Genesis 5 — Enoch
    "GENESIS_5_24": [
        {"source": "1 Enoch 1:1-3", "note": "Enoch's own account of his calling",
         "excerpt": "The words of the blessing of Enoch, wherewith he blessed the elect and righteous, who will be living in the day of tribulation, when all the wicked and godless are to be removed. And he took up his parable and said — Enoch a righteous man, whose eyes were opened by God, saw the vision of the Holy One in the heavens, which the angels showed me..."},
        {"source": "Book of Jubilees 4:17-23", "note": "Jubilees account of Enoch's translation",
         "excerpt": "And he was the first among men that are born on earth who learnt writing and knowledge and wisdom and who wrote down the signs of heaven according to the order of their months in a book, that men might know the seasons of the years according to the order of their separate months..."},
    ],
    # Genesis 6 — Nephilim / Sons of God
    "GENESIS_6_1": [
        {"source": "1 Enoch 6:1-8", "note": "The Watchers — expanded account of the sons of God",
         "excerpt": "And it came to pass when the children of men had multiplied that in those days were born unto them beautiful and comely daughters. And the angels, the children of heaven, saw and lusted after them, and said to one another: Come, let us choose us wives from among the children of men and beget us children..."},
    ],
    "GENESIS_6_2": [
        {"source": "1 Enoch 7:1-6", "note": "The fallen angels take wives",
         "excerpt": "And all the others together with them took unto themselves wives, and each chose for himself one, and they began to go in unto them and to defile themselves with them, and they taught them charms and enchantments, and the cutting of roots, and made them acquainted with plants. And they became pregnant, and they bare great giants..."},
    ],
    "GENESIS_6_4": [
        {"source": "1 Enoch 15:8-12", "note": "The Nephilim and evil spirits",
         "excerpt": "And now, the giants, who are produced from the spirits and flesh, shall be called evil spirits upon the earth, and on the earth shall be their dwelling. Evil spirits have proceeded from their bodies; because they are born from men and from the holy Watchers is their beginning and primal origin..."},
        {"source": "Book of Jubilees 5:1-10", "note": "Jubilees on the Nephilim and the flood",
         "excerpt": "And it came to pass when the children of men began to multiply on the face of the earth and daughters were born unto them, that the angels of God saw them on a certain year of this jubilee, that they were beautiful to look upon; and they took themselves wives of all whom they chose..."},
    ],
    # Genesis 6-9 — The Flood
    "GENESIS_6_14": [
        {"source": "Epic of Gilgamesh, Tablet XI", "note": "Gilgamesh flood narrative — parallel to Noah",
         "excerpt": "Tear down your house and build a boat! Abandon wealth and seek living beings! Spurn possessions and keep alive living beings! Make all living beings go up into the boat. The boat which you are to build, its dimensions must measure equal to each other: its length must correspond to its width..."},
    ],
    "GENESIS_7_4": [
        {"source": "Epic of Gilgamesh, Tablet XI (cont.)", "note": "Gilgamesh flood — the rain",
         "excerpt": "Six days and seven nights the wind blew, the downpour, the tempest, and the flood overwhelmed the land. When the seventh day arrived, the tempest, flood and onslaught which had struggled like a woman in labor, blew themselves out..."},
    ],
    "GENESIS_8_6": [
        {"source": "Epic of Gilgamesh, Tablet XI (the birds)", "note": "Sending out the birds",
         "excerpt": "When a seventh day arrived I sent forth a dove and released it. The dove went off, but came back to me; no perch was visible so it circled back to me. I sent forth a swallow and released it. The swallow went off, but came back to me..."},
    ],
    # Genesis 14 — Melchizedek
    "GENESIS_14_18": [
        {"source": "Book of Jubilees 13:25-27", "note": "Jubilees on Melchizedek",
         "excerpt": "And he gave to Abram a tenth of the firstfruits of all that he possessed. And Abram ate and drank he and all the men who were with him. And he returned to Beer-sheba, and Melchizedek, king of Salem, brought out bread and wine..."},
    ],
    # Genesis 18 — Three visitors to Abraham
    "GENESIS_18_1": [
        {"source": "Josephus, Antiquities 1.11.2", "note": "Josephus on the three angels to Abraham",
         "excerpt": "Now Abraham was visited by three angels in the form of men. He received them gladly and killed a calf and set a meal before them. Two of the angels went to Sodom, but one remained to speak with Abraham about the destruction of Sodom..."},
    ],
    # Exodus 3 — Burning Bush / Divine Name
    "EXODUS_3_14": [
        {"source": "Josephus, Antiquities 2.12.4", "note": "Josephus on the divine name I AM",
         "excerpt": "Whereupon God declared to him his holy name, which had never been discovered to men before; concerning which it is not lawful for me to say any more..."},
        {"source": "Targum Onkelos, Exodus 3:14", "note": "Aramaic Targum rendering of the divine name",
         "excerpt": "And God said to Moses: I AM WHO I AM; and He said: Thus shall you say to the children of Israel: I AM has sent me to you. (Ehyeh asher Ehyeh — the eternal, self-subsistent one who was, is, and will be)"},
    ],
    # Exodus 20 — Ten Commandments
    "EXODUS_20_3": [
        {"source": "Enuma Elish", "note": "Context: Israel told to reject Babylonian pantheon",
         "excerpt": "Then Marduk rose to dominion over all the gods, and the great gods proclaimed his fifty names, each name representing an aspect of his power over creation. This was the pantheon Israel was commanded to reject in favor of one God."},
    ],
    # Isaiah 14 — Lucifer
    "ISAIAH_14_12": [
        {"source": "1 Enoch 86:1-3", "note": "Enoch on the fall of a star (Lucifer parallel)",
         "excerpt": "And again I saw with mine eyes as I slept, and I saw the heaven above, and behold a star fell from heaven, and it arose and eat and pastured amongst those oxen. And after that I saw the large and the black oxen, and behold they all changed their stalls and pastures and their cattle, and began to lament one with another..."},
    ],
    # Psalms 82 — Divine Council
    "PSALMS_82_1": [
        {"source": "Ugaritic Baal Cycle (KTU 1.2)", "note": "Divine assembly parallel in Canaanite myth",
         "excerpt": "The divine assembly gathered — El, father of years, presided over the council of the gods. Among the sons of El, among the assembly of the holy ones. (Ugaritic: phr m'd, 'assembly of the appointed ones') This exact structure — a divine council over which God presides — appears in Psalms 82:1, Job 1-2, and Isaiah 6."},
        {"source": "1 Enoch 14:18-23", "note": "Enoch's vision of the divine throne room",
         "excerpt": "I looked and saw therein a lofty throne: its appearance was as crystal, and the wheels thereof as the shining sun, and there was the vision of cherubim. And from underneath the throne came streams of flaming fire so that I could not look thereon. And the Great Glory sat thereon, and His raiment shone more brightly than the sun and was whiter than any snow..."},
    ],
    # Ezekiel 1 — Chariot / Merkabah
    "EZEKIEL_1_4": [
        {"source": "1 Enoch 71:5-7", "note": "Enoch's vision of the divine chariot (merkabah)",
         "excerpt": "And I fell on my face, And my whole body became relaxed, And my spirit was transfigured; And I cried with a loud voice with the spirit of power, And blessed and glorified and extolled. And these are the blessings: 'Blessed is He, and may the name of the Lord of Spirits be blessed for ever and ever.'"},
    ],
    # Daniel 7 — Son of Man
    "DANIEL_7_13": [
        {"source": "1 Enoch 46:1-4", "note": "Enoch's vision of the Son of Man — parallel to Daniel 7",
         "excerpt": "And there I saw One who had a head of days, And His head was white like wool, And with Him was another being whose countenance had the appearance of a man, And his face was full of graciousness, like one of the holy angels. And I asked the angel who went with me and showed me all the hidden things, concerning that Son of Man, who he was, and whence he was, and why he went with the Head of Days? And he answered and said unto me: This is the Son of Man who hath righteousness, With whom dwelleth righteousness, And who revealeth all the treasures of that which is hidden..."},
    ],
    # Revelation 12 — War in Heaven
    "REVELATION_12_7": [
        {"source": "1 Enoch 54:6", "note": "Enoch on Michael and the fallen angels",
         "excerpt": "And Michael, and Gabriel, and Raphael, and Phanuel shall take hold of them on that great day, and cast them on that day into the burning furnace, that the Lord of Spirits may take vengeance on them for their unrighteousness in becoming subject to Satan and leading astray those who dwell on the earth."},
    ],
}


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.txt"


def _index_cache() -> Path:
    return CACHE_DIR / "scripture_index.json"


def download_text(key: str) -> Optional[str]:
    info = TEXTS.get(key)
    if not info:
        return None
    cache = _cache_path(key)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(encoding="utf-8", errors="replace")

    for url in [info["url"]] + ([info.get("alt_url")] if info.get("alt_url") else []):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LDS-Pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1", errors="replace")
            cache.write_text(text, encoding="utf-8")
            print(f"  {info['title']}: {len(text):,} chars cached")
            return text
        except Exception as e:
            print(f"  {info['title']}: {url} — {e}")

    return None


def download_all() -> dict:
    result = {}
    for key in TEXTS:
        text = download_text(key)
        if text:
            result[key] = {**TEXTS[key], "text": text}
    return result


def get_parallels(book: str, chapter: int, verse: int) -> list[dict]:
    """
    Return curated ancient text parallels for a verse.
    Each: {source, note, text}
    """
    key = f"{book.upper()}_{chapter}_{verse}"
    raw = CURATED_PARALLELS.get(key, [])
    # Normalize: curated entries use "excerpt"; builder expects "text"
    return [{"source": p["source"], "note": p.get("note", ""),
             "text": p.get("text") or p.get("excerpt", "")} for p in raw]


# ── Auto-index from downloaded texts ─────────────────────────────────────────

_REF_RE = re.compile(
    r'\b((?:\d\s)?[A-Z][a-z]+\.?\s+\d+:\d+(?:[-–]\d+)?)',
    re.MULTILINE
)

_ABBREV = {
    "Gen": "Genesis", "Ex": "Exodus", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Ps": "Psalms", "Ezek": "Ezekiel",
    "Dan": "Daniel", "Matt": "Matthew", "Jn": "John",
    "Rev": "Revelation",
}


def _parse_ref(raw: str) -> Optional[tuple]:
    m = re.match(r'(\d?\s*[A-Za-z&]+\.?)\s+(\d+):(\d+)', raw.strip())
    if not m:
        return None
    book = _ABBREV.get(m.group(1).rstrip("."), m.group(1).rstrip("."))
    try:
        return (book.upper(), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def build_index(docs: dict) -> dict:
    """Build auto-index from texts that DO contain scripture references (like Josephus)."""
    idx_path = _index_cache()
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))

    index = {}

    # Add curated parallels first
    for key, parallels in CURATED_PARALLELS.items():
        index[key] = [{"source": p["source"], "text": p["excerpt"], "note": p["note"]}
                      for p in parallels]

    # Auto-scan Josephus (has scripture refs)
    for key in ["josephus_antiquities", "testament_twelve_patriarchs"]:
        doc = docs.get(key)
        if not doc:
            continue
        short = TEXTS[key]["short"]
        paragraphs = re.split(r'\n{2,}', doc["text"])
        for para in paragraphs:
            refs = _REF_RE.findall(para)
            for raw_ref in refs:
                parsed = _parse_ref(raw_ref)
                if not parsed:
                    continue
                idx_key = f"{parsed[0]}_{parsed[1]}_{parsed[2]}"
                snippet = para.strip()[:400].replace('\n', ' ')
                if idx_key not in index:
                    index[idx_key] = []
                if not any(snippet[:50] in q["text"] for q in index[idx_key]):
                    index[idx_key].append({"source": short, "text": snippet, "note": ""})

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"  Ancient myths index: {len(index):,} verse keys indexed (curated + auto)")
    return index


_index: dict = None


def get_quotes(book: str, chapter: int, verse: int, max_quotes: int = 2) -> list[dict]:
    global _index
    if _index is None:
        _index = _load_index()
    if _index is None:
        # Fallback to curated only
        return get_parallels(book, chapter, verse)[:max_quotes]
    key = f"{book.upper()}_{chapter}_{verse}"
    return _index.get(key, [])[:max_quotes]


def _load_index() -> Optional[dict]:
    idx_path = _index_cache()
    if idx_path.exists():
        try:
            return json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None
