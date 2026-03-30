# Immutable Task Ledger

The task system is append-only.

- Source of truth: [task-ledger.jsonl](/Users/reify/Classified/goodcapital_landing/task-ledger.jsonl)
- CLI: [task_ledger.py](/Users/reify/Classified/goodcapital_landing/task_ledger.py)

Nothing rewrites prior rows. New state is expressed by appending events.

## Event model

- `task_registered`
- `task_claimed`
- `task_noted`
- `task_released`
- `task_completed`
- `task_blocked`
- `task_reopened`

Legacy `{"type":"queue", ...}` rows are preserved. The CLI can bootstrap stable
task ids from those old entries so workers can claim real tasks without
rewriting history.

## Basic use

Bootstrap ids for the legacy queue:

```bash
python3 task_ledger.py bootstrap-legacy
```

List tasks:

```bash
python3 task_ledger.py list
python3 task_ledger.py list --status pending
```

Add a new task:

```bash
python3 task_ledger.py add "Fix Book of Enoch editorial bracket normalization"
```

Claim the next pending task:

```bash
python3 task_ledger.py claim --agent Nash
```

Claim a specific task:

```bash
python3 task_ledger.py claim --task-id T-0007 --agent Locke
```

Attach a note:

```bash
python3 task_ledger.py note T-0007 --agent Locke --note "Found 404 truncated verses in current audit."
```

Release a task:

```bash
python3 task_ledger.py release T-0007 --agent Locke --reason "Blocked on source rebuild."
```

Complete a task:

```bash
python3 task_ledger.py complete T-0007 --agent Locke --commit abc1234 --summary "Rebuilt affected chapters and reran audit."
```

## Worker rule

Workers should only:

- list tasks
- claim one task
- append notes while working
- complete or release that task

They should not mutate prior ledger rows or infer state by editing existing
entries.
