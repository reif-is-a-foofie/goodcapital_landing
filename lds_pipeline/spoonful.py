#!/usr/bin/env python3
"""
spoonful.py
===========
Daemon: make dense commentary readable through insertions only.

Spoonful reads Donaldson notes (and eventually other corpus sources) and
adds [bracketed clarifications] and natural paragraph breaks — never
deleting or changing the original words.

Output is stored as a `spoon` dict alongside the original data:

  verse_entry["spoon"] = {
      "notes": ["annotated text 1", ...],
  }

Designed to run continuously as a launchd daemon. Each run processes a
batch of unprocessed notes, then exits. launchd restarts it on schedule.

Usage:
    python3 lds_pipeline/spoonful.py [--batch N] [--dry-run]

Environment:
    ANTHROPIC_API_KEY  — required
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

REPO    = Path(__file__).parent.parent
DONA    = REPO / "library" / "donaldson"
LOG     = REPO / "diagnostics" / "spoonful-latest.txt"

DEFAULT_BATCH = 30   # notes per run
MODEL         = "claude-haiku-4-5-20251001"

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM = """\
You are Spoonful. Your job is to make dense scholarly commentary readable \
through insertions only — you never delete or change any word.

RULES (strictly enforced):
1. Every word from the original must appear in your output, unchanged, in the same order.
2. You may INSERT [bracketed clarifications] inline, 2–8 words each, where the text is opaque.
3. You may INSERT blank lines (paragraph breaks) at major topic shifts.
4. You may INSERT numbering or line breaks to format run-together lists.
5. Do NOT add brackets around LDS terms readers know (Atonement, Priesthood, etc.).
6. Do NOT bracket self-explanatory proper names or scripture references.
7. Return ONLY the modified text — no preamble, no explanation, no summary.

What to bracket:
- Untranslated foreign terms: Bereshith → Bereshith [Hebrew: "in the beginning"]
- Abbreviations: WJS → WJS [Words of Joseph Smith]
- Cryptic scholar names mid-sentence: Heraclitus → Heraclitus [Greek philosopher, c. 500 BC]
- Greek/Hebrew grammar terms: imperfect of eimi → imperfect [past-ongoing tense] of eimi
- Obscure publication abbreviations: ZNW → ZNW [a German New Testament journal]

What NOT to bracket:
- Genesis 1:1, John 3:16, D&C 93 — scripture refs are self-explanatory
- Brigham Young, Joseph Smith, Gordon B. Hinckley — well-known figures
- Conference Report, Ensign, JD — readers of this corpus know these
"""


def spoonful_note(client, text: str) -> str:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    return msg.content[0].text.strip()


# ── Work discovery ─────────────────────────────────────────────────────────────

def find_work(limit: int) -> list[tuple[Path, str, int, str]]:
    """
    Return up to `limit` (file, verse_key, note_idx, original_text) tuples
    where the note has not yet been processed by Spoonful.
    """
    work = []
    files = sorted(DONA.glob("*.json"))
    random.shuffle(files)   # spread work across corpus each run

    for fp in files:
        if len(work) >= limit:
            break
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue

        for vk, entry in data.items():
            if len(work) >= limit:
                break
            notes = entry.get("notes", [])
            if not notes:
                continue
            spoon = entry.get("spoon", {})
            spoon_notes = spoon.get("notes", [])

            for i, raw in enumerate(notes):
                if len(work) >= limit:
                    break
                # Skip if already processed (spoon_notes[i] exists and non-empty)
                if i < len(spoon_notes) and spoon_notes[i]:
                    continue
                if not raw or len(raw) < 80:
                    continue
                work.append((fp, vk, i, raw))

    return work


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch",   type=int, default=DEFAULT_BATCH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    work = find_work(args.batch)
    log_lines = [f"Spoonful run — {len(work)} notes to process"]

    if not work:
        log_lines.append("Nothing to do.")
        LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        return

    if args.dry_run:
        for fp, vk, i, raw in work[:5]:
            print(f"[{fp.stem} v{vk} note{i}] {raw[:80]}…")
        return

    # Group by file so we read/write each file once
    by_file: dict[Path, list] = {}
    for item in work:
        by_file.setdefault(item[0], []).append(item)

    done = errors = 0

    for fp, items in by_file.items():
        data = json.loads(fp.read_text(encoding="utf-8"))

        for _, vk, i, raw in items:
            try:
                annotated = spoonful_note(client, raw)
                # Sanity check: annotated must contain most of the original words
                orig_words = set(raw.lower().split())
                anno_words = set(annotated.lower().split())
                overlap = len(orig_words & anno_words) / max(len(orig_words), 1)
                if overlap < 0.7:
                    log_lines.append(f"  SKIP low overlap {overlap:.2f}: {fp.stem} v{vk} note{i}")
                    errors += 1
                    time.sleep(0.3)
                    continue

                entry = data.setdefault(vk, {})
                spoon = entry.setdefault("spoon", {})
                spoon_notes = spoon.setdefault("notes", [None] * len(entry.get("notes", [])))
                # Extend if needed
                while len(spoon_notes) <= i:
                    spoon_notes.append(None)
                spoon_notes[i] = annotated
                spoon["notes"] = spoon_notes

                done += 1
                log_lines.append(f"  OK [{fp.stem} v{vk} note{i}]")
                time.sleep(0.4)   # gentle rate limiting

            except Exception as e:
                log_lines.append(f"  ERR [{fp.stem} v{vk} note{i}]: {e}")
                errors += 1
                time.sleep(1.0)

        fp.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    log_lines.append(f"\nDone: {done} processed, {errors} errors.")
    summary = "\n".join(log_lines)
    print(summary)
    LOG.write_text(summary + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
