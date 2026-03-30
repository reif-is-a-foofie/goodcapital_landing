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

Ensure a task exists without duplicating an open one:

```bash
python3 task_ledger.py ensure "Fix Book of Enoch editorial bracket normalization" --source beta_tester
```

## Worker rule

Workers should only:

- list tasks
- claim one task
- append notes while working
- complete or release that task

They should not mutate prior ledger rows or infer state by editing existing
entries.

## Agent Profiles

The shared mission for all automated agents lives in:

- [AGENT_MISSION.md](/Users/reify/Classified/goodcapital_landing/AGENT_MISSION.md)

Repo-owned agent profiles live in:

- [agents/socrates_profile.md](/Users/reify/Classified/goodcapital_landing/agents/socrates_profile.md)
- [agents/beta_tester_profile.md](/Users/reify/Classified/goodcapital_landing/agents/beta_tester_profile.md)

These files are intended to keep agent behavior durable across sessions instead
of leaving project intent only in chat context.

## Hourly Beta Tester

There is a local hourly beta-tester runner at [beta_tester.py](/Users/reify/Classified/goodcapital_landing/beta_tester.py).

- It runs a compact suite of audits and browser regressions.
- It writes reports to `diagnostics/beta-tester-latest.json` and `diagnostics/beta-tester-latest.txt`.
- When a high-signal check fails, it appends or updates a durable task in the ledger using `task_ledger.py ensure` and `task_ledger.py note`.
- It carries its mission and manner from the repo-owned mission/profile files above.

Launchd job template:

- [launchd/com.goodproject.beta-tester.plist](/Users/reify/Classified/goodcapital_landing/launchd/com.goodproject.beta-tester.plist)

Install locally:

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/reify/Classified/goodcapital_landing/launchd/com.goodproject.beta-tester.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.goodproject.beta-tester.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.goodproject.beta-tester.plist
```
