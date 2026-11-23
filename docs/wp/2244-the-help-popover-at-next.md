# WP-2244 — the help popover at `/next`: a help term there opens its explanation

Milestone: gui-overhaul · Status: ✅ 2026-11-23 — both pages mount one help popover; a click in it closes no layer; PR #1803
Depends on: —

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

### 2026-11-23 — closed: one help popover for both pages (PR #1803)

A help term on the rebuilt page `/next` now opens its explanation, as it does on today's
page. Before this, every term there did nothing when clicked: a parameter's name, a held row's
reason, the Plan tab's Free and Fix, the stage settings' labels and the instrument editor's.
The popover is now one component that both pages mount, so a third page cannot forget it. A
click inside the popover no longer closes the dialog or floating panel whose label it explains,
and a scroll in an unrelated pane, such as the console following a run, no longer closes it.

No open WP owned this. WP-2240's runner found it and wrote that it "belongs to the rebuild's
shell", whose WP (2215) is closed.

*Done.*

- `gui/src/HelpPopover.svelte`: `provideHelp()` sets the opener every `<Help>` reads and adds
  three window listeners at page init, in the capture phase, before any panel's or layer's.
  Esc closes the popover and stops there (`stopImmediatePropagation`), so it neither cancels a
  run on `/` nor closes the dialog the term sits in. A pointerdown, mousedown or click inside
  the popover stops there too, so no layer reads it as a click away. `<HelpPopover>` draws the
  state. `App.svelte` lost its copy of all this; `next/Frame.svelte` gained four lines.
- `Help.svelte`: a term that unmounts closes its popover, so a layer closed by a submit leaves
  nothing drawn over the page. `HelpOpener` gained `close()` for this.
- Tests: `gui/src/next/help.test.ts` (6 vitests: opens with the entry and link; Esc first and
  focus back; a press inside reaches no later listener; a scroll elsewhere keeps it, a document
  scroll closes it; an unmounted term closes it). Two real-click chromium tests in
  `tests/test_gui_layout_browser.py`: a parameter's name at `/next` opens a popover on top,
  inside the window and holding focus; a stage-settings label's popover survives a click on
  itself and its Esc leaves the settings open.
- The survey (task 1): of what `App.svelte` mounts at its root, only the help popover and its
  context were missing at `/next`. `/next` already mounts the recovery offer, New project, the
  palette and the system-theme listener. `HELP_CONTEXT` was the only context `/` set.

*Review.* `/code-review high --fix` found nine points. Fixed: the scroll that closed the
popover from any pane (the console's included); the click-away that each layer would have had
to remember (made structural, replacing a one-off exception in `next/Plan.svelte`); the popover
outliving its term. Declined: shortcuts (`.`, ⌘⏎, ⌘K) still fire while the popover holds focus,
as on `/`; the popover sits outside an `aria-modal` dialog's subtree, as on `/`; a `helpOpener()`
helper and moving `size` off the shared host, both cosmetic.

*Measured* (arm64 Mac, `[dev]` venv plus `playwright` installed into it, Node v24.22.1): vitest
61 files, 988 passed before the review fixes; svelte-check 489 files, 0 errors; the two new
browser tests pass, and the stage-settings test fails with the click-away guard removed.

*Not generalised.* WP-2240's relation marks (`≡ #1`) still carry their sentence as `title=`,
because #1792 wrote them before a popover existed; that WP converts them. The shortcut and
`aria-modal` points above are `/`'s behaviour too and belong to the swap.

*Settled.* Both pages share the component, rather than a copy in `Frame.svelte` (gui/CLAUDE.md:
one instance). On `/`, Esc now closes the popover before an open palette, since the popover is
drawn over it (z-index 60 against 10). The popover keeps `app.css`'s `.popover` drawing at
`/next`; its shadow (4 px / 16 px) differs from `/next`'s menus (8 px / 24 px), left alone
because changing it changes `/` too.

*Question for the maintainer (visual).* A popover opened from the stage settings is placed
below its label by the same rule as everywhere, so it covers the settings' lower fields until
closed (`2244-screenshots/next-stage-settings-popover.png`, whole window). Keep that, or place
a popover opened inside a floating layer beside the layer? Nothing is changed until answered.

Next: none for this WP. WP-2240 may now turn its relation marks' `title=` into `<Help>`.

- **2026-11-23** — created.
