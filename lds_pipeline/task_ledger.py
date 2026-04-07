#!/usr/bin/env python3
"""
Append-only immutable task ledger with autonomous agent checkout.

The ledger is a JSONL file where each line is an event.  State is always
derived by replaying all events — nothing is ever mutated in place.

Event types
-----------
task_queued   — new work item added
task_noted    — candidate/informational note (not claimable work)
task_claimed  — agent has taken ownership
task_completed — agent finished the work
task_reopened — previously completed task needs rework

Agent workflow
--------------
1. list pending unclaimed tasks:
       python3 lds_pipeline/task_ledger.py list

2. claim the next available task (returns the task_id claimed):
       python3 lds_pipeline/task_ledger.py next --agent MyAgent

3. or claim a specific task:
       python3 lds_pipeline/task_ledger.py claim --task-id T-0009 --agent MyAgent

4. mark complete:
       python3 lds_pipeline/task_ledger.py complete --task-id T-0009 --agent MyAgent --commit abc123 --notes "rebuilt word indexes"

Other commands
--------------
    python3 lds_pipeline/task_ledger.py append --type queue --title "Some new task"
    python3 lds_pipeline/task_ledger.py tail [--limit 20]
    python3 lds_pipeline/task_ledger.py status --task-id T-0009
    python3 lds_pipeline/task_ledger.py reopen --task-id T-0009 --notes "regression found"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO   = Path(__file__).resolve().parent.parent
LEDGER = REPO / "task-ledger.jsonl"


# ---------------------------------------------------------------------------
# Core I/O
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append(entry: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_events() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [
        json.loads(line)
        for line in LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# State projection
# ---------------------------------------------------------------------------

def _project(events: list[dict]) -> dict[str, dict]:
    """
    Replay all events and return a dict of task_id → current task state.
    Only events with a task_id contribute to projectable state.
    """
    tasks: dict[str, dict] = {}
    _next_seq = [0]

    for ev in events:
        tid = ev.get("task_id")
        if not tid:
            # Legacy entries without task_id: try to derive one from sequence
            continue

        kind = ev.get("event", ev.get("type", ""))

        if kind in ("task_queued", "queue") and tid not in tasks:
            _next_seq[0] += 1
            tasks[tid] = {
                "task_id":    tid,
                "title":      ev.get("title", ""),
                "description":ev.get("description", ""),
                "status":     "pending",
                "claimed_by": None,
                "claim_ts":   None,
                "completed_by": None,
                "complete_ts":  None,
                "commit":     None,
                "notes":      ev.get("notes", ""),
                "ts":         ev.get("ts", ""),
                "event":      kind,
            }

        elif kind == "task_noted" and tid not in tasks:
            tasks[tid] = {
                "task_id":    tid,
                "title":      ev.get("note", ev.get("title", ""))[:120],
                "description":ev.get("note", ""),
                "status":     "noted",
                "claimed_by": None,
                "claim_ts":   None,
                "completed_by": None,
                "complete_ts":  None,
                "commit":     None,
                "notes":      "",
                "ts":         ev.get("ts", ""),
                "event":      kind,
            }

        elif kind == "task_claimed" and tid in tasks:
            tasks[tid]["status"]     = "claimed"
            tasks[tid]["claimed_by"] = ev.get("agent")
            tasks[tid]["claim_ts"]   = ev.get("ts")

        elif kind in ("task_completed", "completed") and tid in tasks:
            tasks[tid]["status"]       = "completed"
            tasks[tid]["completed_by"] = ev.get("agent", ev.get("claimed_by"))
            tasks[tid]["complete_ts"]  = ev.get("ts")
            tasks[tid]["commit"]       = ev.get("commit", "")
            if ev.get("notes"):
                tasks[tid]["notes"] = ev["notes"]

        elif kind == "task_reopened" and tid in tasks:
            tasks[tid]["status"]     = "pending"
            tasks[tid]["claimed_by"] = None
            tasks[tid]["claim_ts"]   = None
            if ev.get("notes"):
                tasks[tid]["notes"] = ev["notes"]

    return tasks


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args) -> None:
    """List tasks — defaults to pending+claimed (uncompleted) work items."""
    events = _load_events()
    tasks  = _project(events)

    filter_status = set(args.status) if args.status else {"pending", "claimed"}
    filter_agent  = args.agent

    rows = [
        t for t in tasks.values()
        if t["status"] in filter_status
        and (not filter_agent or t.get("claimed_by") == filter_agent)
        and t["status"] != "noted"  # exclude informational notes by default
    ]
    rows.sort(key=lambda t: t["task_id"])

    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("No matching tasks.")
        return

    col = 80
    for t in rows:
        claimed = f" [claimed by {t['claimed_by']}]" if t.get("claimed_by") else ""
        print(f"{t['task_id']:8s} [{t['status']:8s}]{claimed}")
        print(f"         {t['title'][:col]}")
        if t.get("notes"):
            print(f"         notes: {t['notes'][:col]}")
        print()


def cmd_claim(args) -> None:
    events = _load_events()
    tasks  = _project(events)

    tid = args.task_id
    if tid not in tasks:
        print(f"ERROR: task {tid} not found.", file=sys.stderr)
        sys.exit(1)

    t = tasks[tid]
    if t["status"] == "completed":
        print(f"ERROR: task {tid} is already completed.", file=sys.stderr)
        sys.exit(1)
    if t["status"] == "claimed" and t["claimed_by"] != args.agent:
        print(f"ERROR: task {tid} is already claimed by {t['claimed_by']}.", file=sys.stderr)
        sys.exit(1)

    _append({
        "event":   "task_claimed",
        "task_id": tid,
        "agent":   args.agent,
        "ts":      utc_now(),
    })
    print(f"Claimed {tid} for agent {args.agent}.")


def cmd_next(args) -> None:
    """Claim and print the next unclaimed pending task for an agent."""
    events = _load_events()
    tasks  = _project(events)

    candidates = [
        t for t in tasks.values()
        if t["status"] == "pending"
    ]
    # Exclude Source Scout candidate notes from autonomous work queue
    candidates = [t for t in candidates if not t["title"].startswith("Source Scout:")]
    candidates.sort(key=lambda t: t["task_id"])

    if not candidates:
        print("No pending tasks available.")
        return

    t = candidates[0]
    _append({
        "event":   "task_claimed",
        "task_id": t["task_id"],
        "agent":   args.agent,
        "ts":      utc_now(),
    })
    print(json.dumps({
        "task_id":     t["task_id"],
        "title":       t["title"],
        "description": t["description"],
        "notes":       t["notes"],
    }, ensure_ascii=False))


def cmd_complete(args) -> None:
    events = _load_events()
    tasks  = _project(events)

    tid = args.task_id
    if tid not in tasks:
        print(f"ERROR: task {tid} not found.", file=sys.stderr)
        sys.exit(1)

    entry = {
        "event":   "task_completed",
        "task_id": tid,
        "agent":   args.agent,
        "ts":      utc_now(),
    }
    if args.commit:
        entry["commit"] = args.commit
    if args.notes:
        entry["notes"] = args.notes
    _append(entry)
    print(f"Completed {tid}.")


def cmd_reopen(args) -> None:
    events = _load_events()
    tasks  = _project(events)

    tid = args.task_id
    if tid not in tasks:
        print(f"ERROR: task {tid} not found.", file=sys.stderr)
        sys.exit(1)

    entry = {
        "event":   "task_reopened",
        "task_id": tid,
        "ts":      utc_now(),
    }
    if args.notes:
        entry["notes"] = args.notes
    _append(entry)
    print(f"Reopened {tid}.")


def cmd_status(args) -> None:
    events = _load_events()
    tasks  = _project(events)

    tid = args.task_id
    if tid not in tasks:
        print(f"Task {tid} not found.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(tasks[tid], ensure_ascii=False, indent=2))


def cmd_append(args) -> None:
    """Legacy: add a new task or completion record."""
    entry: dict = {"ts": utc_now()}

    if args.type in ("queue", "pending"):
        entry["event"] = "task_queued"
    elif args.type == "completed":
        entry["event"] = "task_completed"
    else:
        entry["event"] = args.type

    # Auto-assign a task_id if not provided
    if args.task_id:
        entry["task_id"] = args.task_id
    else:
        # Derive next ID from existing ledger
        events  = _load_events()
        existing = {e.get("task_id", "") for e in events if e.get("task_id")}
        nums    = [int(t[2:]) for t in existing if t.startswith("T-") and t[2:].isdigit()]
        nxt     = (max(nums) + 1) if nums else 1
        entry["task_id"] = f"T-{nxt:04d}"

    entry["title"] = args.title
    if args.status:
        entry["status"] = args.status
    if args.commit:
        entry["commit"] = args.commit
    if args.notes:
        entry["notes"] = args.notes

    _append(entry)
    print(f"Appended {entry['task_id']}: {entry['event']}")


def cmd_tail(args) -> None:
    if not LEDGER.exists():
        return
    lines = [l for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    for line in lines[-args.limit:]:
        print(line)


def cmd_stats(args) -> None:
    events = _load_events()
    tasks  = _project(events)
    from collections import Counter
    counts = Counter(t["status"] for t in tasks.values())
    for status, n in sorted(counts.items()):
        print(f"  {status:12s} {n}")
    print(f"  {'total':12s} {len(tasks)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Task ledger for autonomous agent workflow.")
    sub    = parser.add_subparsers(dest="cmd", required=True)

    # list
    p = sub.add_parser("list", help="List tasks by status")
    p.add_argument("--status", nargs="+", default=None,
                   help="Filter by status (pending claimed completed noted). Default: pending+claimed")
    p.add_argument("--agent", default=None, help="Filter by claimed agent")
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_list)

    # claim
    p = sub.add_parser("claim", help="Claim a specific task for an agent")
    p.add_argument("--task-id", required=True)
    p.add_argument("--agent",   required=True)
    p.set_defaults(func=cmd_claim)

    # next
    p = sub.add_parser("next", help="Claim and return the next unclaimed pending task")
    p.add_argument("--agent", required=True)
    p.set_defaults(func=cmd_next)

    # complete
    p = sub.add_parser("complete", help="Mark a task as completed")
    p.add_argument("--task-id", required=True)
    p.add_argument("--agent",   required=True)
    p.add_argument("--commit",  default="")
    p.add_argument("--notes",   default="")
    p.set_defaults(func=cmd_complete)

    # reopen
    p = sub.add_parser("reopen", help="Reopen a completed or claimed task")
    p.add_argument("--task-id", required=True)
    p.add_argument("--notes",   default="")
    p.set_defaults(func=cmd_reopen)

    # status
    p = sub.add_parser("status", help="Show full state of one task")
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_status)

    # stats
    p = sub.add_parser("stats", help="Show task counts by status")
    p.set_defaults(func=cmd_stats)

    # append (legacy + new tasks)
    p = sub.add_parser("append", help="Append a raw event (legacy + new task creation)")
    p.add_argument("--type",    required=True)
    p.add_argument("--title",   required=True)
    p.add_argument("--task-id", default="")
    p.add_argument("--status",  default="")
    p.add_argument("--commit",  default="")
    p.add_argument("--notes",   default="")
    p.set_defaults(func=cmd_append)

    # tail
    p = sub.add_parser("tail", help="Print last N raw ledger lines")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_tail)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
