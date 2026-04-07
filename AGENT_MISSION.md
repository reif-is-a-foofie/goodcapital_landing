# The Good Project — Agent Mission

Read `MISSION.md` first — all of it. That document is the soul of the project.
It contains the vision in the words of the prophets, what we are building, and
the four methods that govern every decision: Connection, Spiritual Arcing,
Depth and Breadth, and Everything Has a Story.
This document is the operational layer for executing inside that vision.

Its product goal is simple:

- create the shortest path to both depth and breadth on a single subject
- let a serious reader move from one verse or paragraph into the best connected
  material without losing provenance or context
- prefer clarity, usefulness, and insight over ornamental features

## Product Standard

Agents working on this project should optimize for:

- clean reading first
- deep linking that actually opens the source and keeps recursion alive
- provenance that stays visible, so readers know what kind of text they are in
- interfaces that reduce friction instead of adding ceremony
- regression resistance, because silent corpus breakage destroys trust

## Manner

The style should be disciplined and product-focused:

- build something people doing real study would actually want to use
- favor concrete gains over abstract cleverness
- surface the shortest useful path, then let power users go deeper
- treat every broken verse, dead link, and unreadable source as product debt
- prefer honest diagnostics over flattering metrics

## Definition Of Better

A change is better when it helps a reader:

- understand where a text comes from
- see why a connection matters
- reach a stronger source faster
- keep traversing without confusion
- trust that the text on screen is clean, accurate, and readable

## Agent Federation

This project runs distributed agents that each pull the repository, claim a task
from the shared ledger, execute it, and push results back. Every claim and completion
is pushed to origin immediately so all agents see current state.

Before starting any work:

```bash
git pull origin main
python3 lds_pipeline/task_ledger.py next --agent YourAgentName
```

When done:

```bash
git add <files>
git commit -m "T-XXXX: description"
git push origin main
python3 lds_pipeline/task_ledger.py complete --task-id T-XXXX --agent YourAgentName \
  --commit $(git rev-parse --short HEAD) --notes "what was done"

# Required: spawn one follow-on task from what you observed while doing the work
python3 lds_pipeline/task_ledger.py append --type queue \
  --title "The next most valuable thing to do, grounded in what you just learned"
```

The queue never runs dry because every agent feeds it. Every new task must be
grounded in direct observation and must serve the mission: deepen reading, improve
connections, clean the corpus, or make traversal faster and more trustworthy.

Full design system reference: `AGENT_GUIDELINES.md`
