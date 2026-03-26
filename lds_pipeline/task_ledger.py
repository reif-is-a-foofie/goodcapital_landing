#!/usr/bin/env python3
"""
Append-only task ledger helper.

Examples:
  python3 lds_pipeline/task_ledger.py append --type completed --title "Add traversal smoke regression" --commit d7b1edbb
  python3 lds_pipeline/task_ledger.py append --type queue --title "Split source periodicals into natural issue units"
  python3 lds_pipeline/task_ledger.py tail
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "task-ledger.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_entry(entry: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def tail(limit: int) -> None:
    if not LEDGER.exists():
        return
    lines = [line for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in lines[-limit:]:
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    append_parser = sub.add_parser("append")
    append_parser.add_argument("--type", required=True)
    append_parser.add_argument("--title", required=True)
    append_parser.add_argument("--status", default="")
    append_parser.add_argument("--commit", default="")
    append_parser.add_argument("--notes", default="")

    tail_parser = sub.add_parser("tail")
    tail_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    if args.cmd == "append":
        entry = {
            "ts": utc_now(),
            "type": args.type,
            "title": args.title,
        }
        if args.status:
            entry["status"] = args.status
        if args.commit:
            entry["commit"] = args.commit
        if args.notes:
            entry["notes"] = args.notes
        append_entry(entry)
    elif args.cmd == "tail":
        tail(args.limit)


if __name__ == "__main__":
    main()
