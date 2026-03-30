#!/usr/bin/env python3
"""
Build a compact project progress summary for the title page.

Outputs:
  - library/project-progress.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "task-ledger.jsonl"
OUT = ROOT / "library" / "project-progress.json"


def load_rows() -> list[dict]:
    rows = []
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


def build() -> dict:
    rows = load_rows()
    completed = []
    agent_counts: Counter[str] = Counter()
    commit_count = 0
    seen = set()

    for row in rows:
        if row.get("type") == "queue" and row.get("status") == "completed":
            title = str(row.get("title") or "").strip()
            commit = str(row.get("commit") or "").strip()
            key = ("legacy", title, commit)
            if key in seen:
                continue
            seen.add(key)
            agent = "Codex"
            summary = title or "Completed work"
            completed.append({
                "task_id": "",
                "agent": agent,
                "commit": commit,
                "summary": summary,
                "ts": row.get("ts", ""),
            })
            agent_counts[agent] += 1
            if commit:
                commit_count += 1
            continue

        if row.get("event") != "task_completed":
            continue
        agent = str(row.get("agent") or "Unknown")
        commit = str(row.get("commit") or "").strip()
        summary = str(row.get("summary") or "").strip()
        key = ("event", row.get("task_id", ""), commit, row.get("ts", ""))
        if key in seen:
            continue
        seen.add(key)
        completed.append({
            "task_id": row.get("task_id", ""),
            "agent": agent,
            "commit": commit,
            "summary": summary,
            "ts": row.get("ts", ""),
        })
        agent_counts[agent] += 1
        if commit:
            commit_count += 1

    completed.sort(key=lambda row: row.get("ts", ""), reverse=True)
    agent_rows = [
        {"agent": agent, "completed": count}
        for agent, count in agent_counts.most_common()
    ]

    return {
        "totals": {
            "completed_tasks": len(completed),
            "recorded_commits": commit_count,
            "active_agents": len(agent_rows),
        },
        "agents": agent_rows,
        "recent_completions": completed[:10],
    }


def main() -> int:
    payload = build()
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["totals"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
