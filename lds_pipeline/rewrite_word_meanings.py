#!/usr/bin/env python3
"""
rewrite_word_meanings.py
========================
Take the scholarly Donaldson word studies (Greek/Hebrew grammar terms, citations,
academic prose) and rewrite them in plain English for a general reader.

Adds a `plain` field to each word entry in every donaldson chapter JSON.

Run from repo root:
    python3 lds_pipeline/rewrite_word_meanings.py [--dry-run]
"""

import json
import sys
import time
from pathlib import Path

import anthropic

REPO    = Path(__file__).parent.parent
DONA    = REPO / "library" / "donaldson"

SYSTEM = """\
You rewrite biblical word studies into plain English for a general adult reader.
The reader has no background in Greek, Hebrew, or biblical scholarship.

Rules:
- 2–3 sentences max
- No grammar terms (no "aorist", "imperfect", "participle", "nominative", etc.)
- No scholar names, no citations, no "Robertson says…", no footnote references
- No Greek or Hebrew characters or transliterations in the explanation
- Start with what the word *means* — its core idea
- End with why that meaning matters for understanding *this passage*
- Write in present tense, active voice, plain words
"""

def rewrite(client, word: str, greek: str, meaning: str) -> str:
    prompt = (
        f"Word: {word} (Greek: {greek})\n\n"
        f"Original scholar's note:\n{meaning}\n\n"
        "Rewrite this as 2–3 plain English sentences for a general reader."
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def main():
    dry_run = "--dry-run" in sys.argv

    client = anthropic.Anthropic()

    files = sorted(DONA.glob("*.json"))
    print(f"Scanning {len(files)} chapter files…")

    # Collect all (file, verse_key, word_index, word_entry) needing rewrite
    work = []
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        changed = False
        for vk, entry in data.items():
            for i, w in enumerate(entry.get("words", [])):
                if w.get("meaning") and not w.get("plain"):
                    work.append((fp, vk, i, w))

    print(f"  {len(work)} word entries need rewriting")
    if dry_run:
        for fp, vk, i, w in work[:5]:
            print(f"  [{fp.stem} v{vk}] {w['word']} ({w['greek']})")
            print(f"    original: {w['meaning'][:120]}…")
        return

    # Group by file so we only read/write each file once
    by_file: dict[Path, list] = {}
    for item in work:
        by_file.setdefault(item[0], []).append(item)

    total_done = 0
    for fp, items in by_file.items():
        data = json.loads(fp.read_text(encoding="utf-8"))

        for _, vk, i, w in items:
            plain = rewrite(client, w["word"], w["greek"], w["meaning"])
            data[vk]["words"][i]["plain"] = plain
            total_done += 1
            print(f"  [{fp.stem} v{vk}] {w['word']} ({w['greek']})")
            print(f"    → {plain[:100]}")
            # Light rate-limit pause
            time.sleep(0.2)

        fp.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    print(f"\nDone. {total_done} entries rewritten across {len(by_file)} files.")


if __name__ == "__main__":
    main()
