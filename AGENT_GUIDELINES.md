# Agent Guidelines — The Good Project

This document is the canonical reference for any agent (Claude, autonomous script,
or human contributor) working in this repository. Read it before writing a line.

---

## 1. Design Tokens

All UI is built from these CSS custom properties. Never hardcode these values; use
the variable name everywhere so the palette stays consistent.

```css
:root {
    --bg:           #F5F2EC;   /* warm off-white page background */
    --text:         #1C1C1C;   /* primary body text */
    --muted:        #6C6C6C;   /* secondary labels, metadata, captions */
    --accent:       #9C7A4D;   /* brand amber — links, highlights, active states */
    --accent-hover: #7A5E38;   /* darkened amber for hover */
    --divider:      rgba(0,0,0,0.09);  /* hairline separators */
    --nav-h:        52px;      /* fixed navigation bar height */
    --toc-w:        340px;     /* sidebar / table-of-contents width */
    --reader-max:   760px;     /* maximum content column width */
}
```

Entity annotation colors (inline verse underlines):
- **Person** entity: `var(--accent)` dotted underline (`#9C7A4D`)
- **Place** entity: `#4a7090` dotted underline (steel blue)
- **Thing** entity: `#6a4a8c` dotted underline (muted violet)

---

## 2. Typography

```
Font stack: 'Inter', -apple-system, sans-serif
Font rendering: -webkit-font-smoothing: antialiased

Sizes used in the library:
  10px  uppercase label / provenance metadata
  11px  secondary annotations, search results, status text
  12px  TOC subtitles, nav metadata
  13px  body reading text, discovery panel entries
  14px  verse body text (--verse-font-size)
  15px  chapter headings, section sub-heads
  18px  book / major heading
  22px  primary screen title

Weight conventions:
  400 — body
  500 — slightly emphasized labels
  600 — section headers, panel titles
  700 — ALL CAPS labels (letter-spacing: .1em)

Uppercase label pattern (reuse this exact style):
  font-size: 10px; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--muted);
```

---

## 3. Layout Patterns

### Three-panel shell
```
#shell: fixed, top: var(--nav-h), fills remaining viewport
  #toc:    left panel, width: var(--toc-w), background: #FEFCF8
  #reader: center column, flex: 1, overflow-y: auto
  #panel:  right discovery panel, slides in from right, fixed width 380px
```

### Discovery panel entry
```
padding: 9px 12px
cursor: pointer
border-bottom: 1px solid var(--divider)
hover: background rgba(0,0,0,0.03)
```

### Cards (quote, hist, note)
Left accent bar: `box-shadow: inset 3px 0 0 var(--accent)`
Background: neutral, no fill by default.

### Active/selected state
Selected verse: `box-shadow: inset 3px 0 0 var(--accent), 0 0 0 1px rgba(156,122,77,0.18)`

---

## 4. Interaction Model

**Verse click** → opens discovery panel with:
1. Verse text header (verse ref + full text)
2. People · Places · Things chips (entity scan of verse text)
3. Commentary cards from the corpus (talks, books)
4. Word study entry point

**Entity chip / annotated word click** → opens entity profile panel before word study

**Word click (span.w)** → word study panel (frequency, scripture cross-refs, definition)

**TOC tile click** → loads chapter HTML into #reader via `loadChapter(id)`

Rule: every click must open something useful or do nothing. No dead ends.

---

## 5. Data Conventions

### Entity IDs
```
person:snake_case      e.g. person:joseph_smith, person:nephi_1
place:snake_case       e.g. place:jerusalem, place:jordan_river
thing:snake_case       e.g. thing:liahona, thing:urim_thummim
topic:snake_case       e.g. topic:faith, topic:atonement
book:snake_case        e.g. book:teachings_of_the_prophet
```

### Scripture figure (has `group` field)
```json
{
  "id": "person:moses",
  "name": "Moses",
  "group": "old_testament",
  "desc": "One sentence summary.",
  "variants": ["Moses", "Moshe"],
  "born": {"year": -1393, "place_name": "Egypt"},
  "died": {"year": -1273, "place_name": "Mount Nebo"},
  "wikipedia_title": "Moses",
  "wikipedia_summary": "...",
  "wikipedia_thumbnail": "https://...",
  "wikipedia_url": "https://en.wikipedia.org/wiki/Moses",
  "scripture_refs": ["exo.2.1", "num.20.1"],
  "ref_count": 842
}
```

### Modern LDS figure (no `group`)
```json
{
  "id": "person:jeffrey_r_holland",
  "name": "Jeffrey R. Holland",
  "desc": "Member of the Quorum of the Twelve Apostles.",
  "wikipedia_title": "Jeffrey R. Holland",
  "wikipedia_summary": "...",
  "wikipedia_thumbnail": "https://...",
  "roles": [{"title": "Apostle", "from": 1994}]
}
```

### Topic entry
```json
{
  "id": "topic:faith",
  "name": "Faith",
  "desc": "One sentence definition.",
  "wikipedia_summary": "...",
  "related_scriptures": ["heb.11.1", "alma.32.21"],
  "canonical_verses": ["heb.11.1"]
}
```

### Scripture reference format
`book_abbrev.chapter.verse` — e.g. `1ne.3.7`, `jn.3.16`, `dc.76.22`

---

## 6. File Map

```
library/
  index.html              — single-page library app (all JS inline)
  entities/
    people.json           — 1,660+ persons (scripture figures + modern LDS)
    people_index.json     — name variant → entity ID lookup
    places.json           — 48+ places
    places_index.json     — name → place ID
    things.json           — 26+ scriptural objects
    things_index.json     — name → thing ID
    topics.json           — 49 topics with related_scriptures
  chapters/               — 1,584 chapter HTML files, one per canonical chapter

lds_pipeline/
  task_ledger.py          — append-only JSONL ledger + agent CLI
  build_entity_wikipedia.py  — Wikipedia REST enrichment per entity
  build_entity_tasks.py      — gap scanner → batch tasks in ledger
  build_scripture_figure_registry.py  — seeds scripture figures from verse text

task-ledger.jsonl         — live event log (replayed to derive task state)
AGENT_GUIDELINES.md       — this file
AGENT_MISSION.md          — product mission and quality standard
agents/                   — individual agent profile documents
```

---

## 7. Distributed Agent Workflow

Agents operate against the shared `main` branch. The ledger is the coordination
bus. Every state change must be pushed to origin immediately.

### Startup sequence
```bash
git pull origin main                         # get latest ledger state
python3 lds_pipeline/task_ledger.py next --agent MyAgent
# → prints JSON with task_id, title, description
# → automatically commits + pushes ledger (claim recorded for all agents)
```

### Do the work
Execute the task. Edit files. Run pipeline scripts. Verify output.

### Completion sequence
```bash
git add <specific files changed>
git commit -m "T-XXXX: short description of what was done"
git push origin main

python3 lds_pipeline/task_ledger.py complete \
  --task-id T-XXXX \
  --agent MyAgent \
  --commit $(git rev-parse --short HEAD) \
  --notes "brief result summary"
# → automatically pushes ledger update to origin

# REQUIRED: spawn one follow-on task from your learnings
python3 lds_pipeline/task_ledger.py append \
  --type queue \
  --title "Descriptive title of the next thing that should be done"
# → the title must stem from something you observed while doing the task
# → it must align with the project mission (deepen reading, improve links, clean corpus)
# → one task, not a list — the most valuable next step you can name
```

### The follow-on task rule

Every agent is required to append one new task before calling the session complete.
This is not optional and not a formality. It is the mechanism that keeps the queue
alive and mission-aligned without human curation.

The follow-on task should come from direct observation:
- A gap you found while doing the work ("Moses is enriched but Aaron has no born/died data")
- A related pattern that would compound the value ("places are annotated but events are not")
- A regression you noticed ("verse 1 Ne 3:7 text renders with a stray bracket")
- A missing cross-link that would help a reader ("Faith topic has no link to figures known for faith")

Bad follow-on task: vague, broad, or not grounded in what you just did.
Good follow-on task: specific, actionable, connected to what you observed.

### Conflict avoidance
- Claim before writing. Never start work on a task you haven't claimed.
- Push the ledger immediately on claim — `task_ledger.py` does this automatically.
- If `git pull` shows a conflict on `task-ledger.jsonl`, the ledger is append-only:
  accept both sides (keep all lines from both versions) — no line is ever deleted.
- Never rebase or force-push `main`.

### One task at a time
An agent should hold at most one claimed task. Complete or reopen before claiming next.

---

## 8. Quality Gates

Before pushing any library change:

1. Open `library/index.html` in a browser.
2. Navigate to at least one chapter (e.g. John 1).
3. Click a verse. Confirm discovery panel opens.
4. If entity annotation was changed: click a person name. Confirm entity profile.
5. If word index was changed: click a content word. Confirm word study shows results.

For pipeline changes: run with `--dry-run` first, inspect output, then run live.

---

## 9. What Not to Do

- Do not use `git push --force` on `main`.
- Do not delete lines from `task-ledger.jsonl`.
- Do not hardcode pixel values or colors that are already in the token set.
- Do not create new entity files (people2.json, etc.) — always extend the existing files.
- Do not add `console.log` to production library/index.html.
- Do not create new JS frameworks, build steps, or package.json dependencies.
  The library is intentionally zero-dependency at runtime.
- Do not invent new entity ID patterns — follow the existing `type:snake_case` convention.
