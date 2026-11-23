# WP-2244 — the help popover at `/next`: a help term there opens its explanation

Milestone: gui-overhaul · Status: 🔄 2026-11-23 — claimed by a ghostshift runner
Depends on: —
Priority: P2 2026-11-23 — a defect on the rebuild's page: every help term at `/next` does nothing when clicked

## Goal

Clicking a help term on the rebuilt page `/next` opens the same popover it opens on today's page
`/`: the term's `rietx.help` entry, or the server's sentence about one row, with the manual link.
Both pages mount one shared popover component, so the two cannot drift apart again.

## Context

Found 2026-11-23 by the WP-2240 runner (its handover, "Found, not fixed"): `/next` mounts no help
popover. `HELP_CONTEXT` is set only in `gui/src/App.svelte`, so every `<Help>` term at `/next`
finds no opener (`gui/src/Help.svelte` degrades to a term that does nothing, by design, for
component tests). At `origin/main` `42fddf0fe` the dead terms are a held parameter's reason and a
parameter's name (`next/Params.svelte`), the instrument editor's labels (`next/Instrument.svelte`),
the Plan tab's Free and Fix verbs, held rows and stage settings (`next/Plan.svelte`), and the
candidate notes (`next/Indexing.svelte`). The shared New project dialog (`panels/NewProject.svelte`)
carries terms too.

- `gui/CLAUDE.md` § House style and help: "What a name means is an entry in `rietx.help`,
  reached through `<Help>` (WP-1203). One instance in `App.svelte`." This WP makes the one
  instance a component each page mounts once.
- `/next`'s layers each take Esc on the window in the capture phase (`next/Menu.svelte`,
  `next/Settings.svelte`, `next/HelpBox.svelte`). Today's page closes the popover from its own
  keydown, ahead of the Esc that cancels a run.
- The popover is drawn by `app.css`'s `.popover` register, which `/next` already loads.
- The tier of each rule this WP adds: none. It adds no flag, threshold or automatic action.

## Non-goals

- The look of the popover at `/next` (font, width, placement). If it raises a question
  `gui/STYLE.md` does not settle, it is recorded for the maintainer with a screenshot.
- WP-2240's relation marks, which use `title=` because no popover existed. That branch is open
  (#1792) and converts them itself.

## Tasks

- [x] 1. Survey what else only `/` mounts at its root that a `/next` control depends on.
- [x] 2. One shared popover component and opener, mounted by both `App.svelte` and
  `next/Frame.svelte`; vitest for `/next`.
- [x] 3. A real-click browser test: a help term at `/next` opens its popover; the dist rebuilt.
- [x] Skill: none. The agent skill drives the Python API, never the GUI.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check && npm --prefix gui run build
git diff --exit-code src/rietx/gui/static
.venv/bin/python -m pytest tests/test_gui_layout_browser.py -k help_term -n 0
```

## References

WP-1203 (the help popover), WP-2215 (the frame at `/next`), WP-2240's handover of 2026-11-23.

## Handover log

- **2026-11-23** — created.
