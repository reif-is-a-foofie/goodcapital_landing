#!/usr/bin/env python3
"""
Append-only task ledger CLI.

This keeps task history immutable by only appending events to task-ledger.jsonl.
It can bootstrap stable task ids from the existing legacy queue rows so workers
can claim and complete bounded tasks without rewriting history.
"""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "task-ledger.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not LEDGER.exists():
        return rows
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_event(event: dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("ts", now_iso())
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def title_key(title: str) -> str:
    return " ".join(str(title or "").strip().lower().split())


@dataclass
class TaskState:
    task_id: str
    title: str
    status: str = "pending"
    created_ts: str = ""
    updated_ts: str = ""
    agent: str = ""
    commit: str = ""
    notes: list[dict[str, Any]] = field(default_factory=list)
    raw_events: list[dict[str, Any]] = field(default_factory=list)


def derive_states(rows: list[dict[str, Any]]) -> OrderedDict[str, TaskState]:
    legacy_latest: OrderedDict[str, dict[str, Any]] = OrderedDict()
    title_to_id: dict[str, str] = {}
    states: OrderedDict[str, TaskState] = OrderedDict()

    for row in rows:
        title = row.get("title")
        if title and row.get("type") == "queue":
            legacy_latest[title_key(title)] = row

    for row in rows:
        if row.get("event") == "task_registered":
            task_id = row["task_id"]
            title = row["title"]
            title_to_id[title_key(title)] = task_id
            state = states.get(task_id) or TaskState(task_id=task_id, title=title)
            state.created_ts = state.created_ts or row.get("ts", "")
            state.updated_ts = row.get("ts", "")
            state.status = row.get("status", state.status)
            state.commit = row.get("commit", state.commit)
            state.raw_events.append(row)
            states[task_id] = state

    for key, row in legacy_latest.items():
        task_id = title_to_id.get(key)
        if not task_id:
            continue
        state = states[task_id]
        state.status = row.get("status", state.status)
        state.commit = row.get("commit", state.commit)
        state.updated_ts = row.get("ts", state.updated_ts)

    for row in rows:
        event = row.get("event")
        task_id = row.get("task_id")
        if not event or not task_id or task_id not in states:
            continue
        state = states[task_id]
        state.raw_events.append(row)
        state.updated_ts = row.get("ts", state.updated_ts)
        if event == "task_claimed":
            state.status = "claimed"
            state.agent = row.get("agent", "")
        elif event == "task_released":
            state.status = "pending"
            state.agent = ""
        elif event == "task_completed":
            state.status = "completed"
            state.agent = row.get("agent", state.agent)
            state.commit = row.get("commit", state.commit)
        elif event == "task_blocked":
            state.status = "blocked"
            state.agent = row.get("agent", state.agent)
        elif event == "task_reopened":
            state.status = "pending"
            state.agent = ""
        elif event == "task_noted":
            state.notes.append(row)
    return states


def next_task_id(rows: list[dict[str, Any]]) -> str:
    max_id = 0
    for row in rows:
        task_id = row.get("task_id", "")
        if isinstance(task_id, str) and task_id.startswith("T-"):
            try:
                max_id = max(max_id, int(task_id.split("-", 1)[1]))
            except ValueError:
                pass
    return f"T-{max_id + 1:04d}"


def bootstrap_legacy(args: argparse.Namespace) -> int:
    rows = load_rows()
    states = derive_states(rows)
    known_titles = {title_key(state.title) for state in states.values()}
    next_rows = []
    next_id_counter = 1
    existing_ids = {state.task_id for state in states.values()}
    while f"T-{next_id_counter:04d}" in existing_ids:
        next_id_counter += 1

    seen: set[str] = set()
    for row in rows:
        title = row.get("title")
        if row.get("type") != "queue" or not title:
            continue
        key = title_key(title)
        if key in seen or key in known_titles:
            seen.add(key)
            continue
        seen.add(key)
        task_id = f"T-{next_id_counter:04d}"
        next_id_counter += 1
        next_rows.append({
            "event": "task_registered",
            "task_id": task_id,
            "title": title,
            "status": row.get("status", "pending"),
            "source": "legacy_queue",
        })

    for event in next_rows:
        append_event(event)

    print(json.dumps({"registered": len(next_rows)}, indent=2))
    return 0


def list_tasks(args: argparse.Namespace) -> int:
    states = derive_states(load_rows())
    rows = []
    for state in states.values():
        if args.status and state.status != args.status:
            continue
        rows.append({
            "task_id": state.task_id,
            "status": state.status,
            "agent": state.agent,
            "title": state.title,
            "commit": state.commit,
            "updated_ts": state.updated_ts,
        })
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


def add_task(args: argparse.Namespace) -> int:
    rows = load_rows()
    task_id = next_task_id(rows)
    append_event({
        "event": "task_registered",
        "task_id": task_id,
        "title": args.title,
        "status": "pending",
        "priority": args.priority,
    })
    print(json.dumps({"task_id": task_id, "title": args.title}, indent=2, ensure_ascii=False))
    return 0


def ensure_task(args: argparse.Namespace) -> int:
    rows = load_rows()
    states = derive_states(rows)
    wanted = title_key(args.title)
    for state in states.values():
        if title_key(state.title) == wanted and state.status != "completed":
            print(json.dumps({
                "task_id": state.task_id,
                "title": state.title,
                "status": state.status,
                "created": False,
            }, indent=2, ensure_ascii=False))
            return 0
    task_id = next_task_id(rows)
    append_event({
        "event": "task_registered",
        "task_id": task_id,
        "title": args.title,
        "status": "pending",
        "priority": args.priority,
        "source": args.source or "",
    })
    print(json.dumps({
        "task_id": task_id,
        "title": args.title,
        "status": "pending",
        "created": True,
    }, indent=2, ensure_ascii=False))
    return 0


def claim_task(args: argparse.Namespace) -> int:
    rows = load_rows()
    states = derive_states(rows)
    if args.task_id:
        state = states.get(args.task_id)
        if not state:
            raise SystemExit(f"unknown task id: {args.task_id}")
        if state.status not in {"pending", "blocked"}:
            raise SystemExit(f"task not claimable: {state.task_id} is {state.status}")
    else:
        claimable = [s for s in states.values() if s.status == "pending"]
        if not claimable:
            raise SystemExit("no pending tasks")
        state = claimable[0]
    append_event({
        "event": "task_claimed",
        "task_id": state.task_id,
        "agent": args.agent,
    })
    print(json.dumps({"task_id": state.task_id, "agent": args.agent, "title": state.title}, indent=2, ensure_ascii=False))
    return 0


def note_task(args: argparse.Namespace) -> int:
    append_event({
        "event": "task_noted",
        "task_id": args.task_id,
        "agent": args.agent,
        "note": args.note,
    })
    print(json.dumps({"task_id": args.task_id, "agent": args.agent}, indent=2))
    return 0


def complete_task(args: argparse.Namespace) -> int:
    append_event({
        "event": "task_completed",
        "task_id": args.task_id,
        "agent": args.agent,
        "commit": args.commit or "",
        "summary": args.summary or "",
    })
    print(json.dumps({"task_id": args.task_id, "agent": args.agent, "commit": args.commit or ""}, indent=2))
    return 0


def release_task(args: argparse.Namespace) -> int:
    append_event({
        "event": "task_released",
        "task_id": args.task_id,
        "agent": args.agent,
        "reason": args.reason or "",
    })
    print(json.dumps({"task_id": args.task_id, "agent": args.agent}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("bootstrap-legacy")
    p.set_defaults(func=bootstrap_legacy)

    p = sub.add_parser("list")
    p.add_argument("--status", choices=["pending", "claimed", "completed", "blocked"])
    p.set_defaults(func=list_tasks)

    p = sub.add_parser("add")
    p.add_argument("title")
    p.add_argument("--priority", default="normal")
    p.set_defaults(func=add_task)

    p = sub.add_parser("ensure")
    p.add_argument("title")
    p.add_argument("--priority", default="normal")
    p.add_argument("--source", default="")
    p.set_defaults(func=ensure_task)

    p = sub.add_parser("claim")
    p.add_argument("--task-id")
    p.add_argument("--agent", required=True)
    p.set_defaults(func=claim_task)

    p = sub.add_parser("note")
    p.add_argument("task_id")
    p.add_argument("--agent", required=True)
    p.add_argument("--note", required=True)
    p.set_defaults(func=note_task)

    p = sub.add_parser("complete")
    p.add_argument("task_id")
    p.add_argument("--agent", required=True)
    p.add_argument("--commit")
    p.add_argument("--summary")
    p.set_defaults(func=complete_task)

    p = sub.add_parser("release")
    p.add_argument("task_id")
    p.add_argument("--agent", required=True)
    p.add_argument("--reason")
    p.set_defaults(func=release_task)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
