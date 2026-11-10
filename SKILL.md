---
name: project-memory
description: Long-running project memory kept as a tree of small markdown files (phases → steps) in memory/. Use at session start to recover context, after a plan is approved to record a new phase, and whenever a decision, finding or change is worth remembering.

---

# Project memory

Project memory lives in `memory/` as a tree of small markdown files.
Read only what you need. Write one small file at a time.

## Layout

Example from a simple to-do list web app:

```
memory/
├── index.md                          # the project's README; read first, every session
├── 01-database/                      # a phase is a directory
│   ├── index.md                      # the phase itself: goal, plan, summary
│   ├── 01-engine-choice.md           # a step without sub-steps is a file
│   └── 02-schema/                    # a step with sub-steps is a directory…
│       ├── index.md                  # …and its own notes go in index.md
│       ├── 01-users-table.md
│       └── 02-tasks-table.md
├── 02-backend/
│   ├── index.md
│   ├── 01-rest-api.md
│   └── 02-auth.md
├── 03-frontend/
│   ├── index.md
│   ├── 01-ui-framework.md
│   └── 02-task-list-page.md
└── 04-deploy/
    ├── index.md
    ├── 01-docker-image.md
    └── 02-ci-pipeline.md
```

- `memory/` is itself a directory with children, so it gets an `index.md` like every other directory.
- A step without children is a file, `NN-slug.md`. Anything with children is a directory, `NN-slug/`, with an `index.md`. Never both.
- The number keeps the order and the slug says what's inside, so `tree memory` is the outline.
- Ids come from the numbers: `01-database/02-schema/01-users-table.md` is 1.2.1.
- Every file ends in `.md`.

## Frontmatter

Every file starts with:

```markdown
---
title: Use SQLite for the database
created: 2026-10-15T14:32:07+02:00
status: done
summary: SQLite in a single file; small app, one server, no database service to run.
---
```

- `created`: when the file was written: date, time to the second, and time zone as a UTC offset (the `+02:00` above). Never write a time without the offset. For a phase, when it started. For `memory/index.md`, when the project started.
- `updated`: add it whenever you change the frontmatter later, such as the status. Same format.
- `status`: `planned`, `active`, `done`, `dropped` or `superseded`.
- `summary`: one line. This is what you scan to decide which file to open, so make it specific.
- `supersedes`: only when this entry replaces an earlier one (see Changes).

Get the time from the clock; never guess it. Both commands print the same format, such as `2026-10-15T14:32:07+02:00`:

- Linux: `date -Iseconds`
- macOS: `date +%Y-%m-%dT%H:%M:%S%z | sed -E 's/([0-9]{2})$/:\1/'`

## Reading

1. Read `memory/index.md`: what the project is, then where it stands.
2. For an outline with summaries, without opening files:
   `grep -r -m1 '^summary:' memory --include='*.md' | sort`
3. Open a phase's `index.md`, then only the entries you need. Grep `memory/` for anything that spans phases.

## Writing

- After a plan is approved, create the phase directory with an `index.md`: goal, the plan as a checklist, summary.
- Give a step its own file only if it's worth recalling later: a decision, a finding, a dead end, a non-obvious fix. Trivial steps stay as checklist lines in the phase's `index.md`.
- When a step file needs sub-steps, move `NN-slug.md` to `NN-slug/index.md` and fix the links that pointed to it.
- Don't keep lists of children in `index.md`. The directory is the list, and the grep above shows it.
- Keep each file under ~2k tokens. Link to commits and files instead of pasting logs.

## Changes

- Don't rewrite old entries. Write a new entry with `supersedes: [<old id>]`. In the old entry, set `status: superseded` and `updated:`, and leave its body as it was. For example, an entry that moves the app to Postgres has `supersedes: [1.1]`.
- Don't rewrite an approved plan either. Add a timestamped line under a `## Deviations` heading in the phase's `index.md`: what changed and why.

## memory/index.md

The root `index.md` is the project's README. It should be enough for someone new, or for you at the start of a session, to understand the project without opening anything else. It has the same frontmatter as any other file. Decide what goes in it as the project takes shape. End it with a brief **Current state** section: where things stand and what's next.

It's the one file you edit in place instead of superseding. Keep it true to the project as it is now, and set `updated:` each time. Keep it under ~2k tokens, and link to entries instead of repeating them. Update **Current state** before ending a session and whenever a phase closes.

## Closing a phase

Set `status: done` and `updated:`, rewrite `summary` as 1–3 sentences on the result, and point the **Current state** section of `memory/index.md` at the next phase.
