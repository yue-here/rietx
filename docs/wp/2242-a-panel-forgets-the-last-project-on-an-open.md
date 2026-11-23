# WP-2242 — a panel forgets the last project when another opens in the same window

Milestone: gui-overhaul · Status: 🔄 2026-11-23 — claimed by @yue-here (ghostshift runner)
Depends on: —
Priority: P2 2026-11-22 — Run, Apply and Undo can act on the last project's state in the new one, and nothing says so; a page reload is the workaround nobody knows to use

## Goal

After File › Open, New project, an example or a recent row replaces the session's project
without a page reload, no panel on either page shows or acts on the previous project's
state.

## Context

Found by WP-2237's sibling survey on 2026-11-22, against the tree at `4a0c73896`. WP-2237
fixed the event cursor on the server, where the cause was a counter reset on an open. The
cause here is different and lives in the client.

- **Node ids repeat across projects.** `HistoryTree` names a node `n{len:04d}`
  (`src/rietx/history/tree.py`), so two projects with the same node count share a head id.
  A panel whose reload effect reads only `head` (or `[head, protocol]`) sees no change on an
  open and keeps the previous project's data. Changing the id scheme is a stored-format
  change, so the fix is a project identity in the client.
- **Two panels already guard against it.** `/next` keys History on `project.path`
  (`gui/src/next/Frame.svelte`, `{#key project.path}`) and today's Model panel keys on
  `projectKey` (`gui/src/panels/Model.svelte`). Nothing else does.

What the survey traced, each from the page's open handler to the state. Today's page is
`gui/src/App.svelte` (reset point `opened()`/`open()`); `/next` is
`gui/src/next/Frame.svelte` (reset point `opened()`/`leaveEdits()`).

Acts on the wrong project:

- App `applied` is never cleared on an open. The Report tab's Undo then checks out the
  previous project's undo node id in the new project's tree, which names an unrelated node
  (`gui/src/panels/Report.svelte`, `undo`). Its observed Δχ² subtracts across projects.
- Plan tab on a head collision (`next/Plan.svelte`, keyed on `mode` and `head`;
  `leave()` resets to the old saved plan). Run this stage sends the old plan's stage.
- Report on a head collision (`panels/Report.svelte`, reload keyed on `head`). Apply sends
  the old suggestion's kind and paths.
- Series panel loads once per session (`panels/Series.svelte`, `loaded`) while the server
  resets the series on adopt. The tab keeps the old pattern list and answer.

Shows the wrong project:

- Params table on a head collision, both pages (`next/Params.svelte`,
  `panels/Params.svelte`, reload on `head`). An edit is typed against the old value.
- Interactive sliders, both pages: a custom slider range is carried by path
  (`lib/interactive.ts`, `prior`), and on a head collision the whole panel is stale.
- Background graph on a head collision with the same protocol, both pages.
- Text tab on `/next`: `forget()` empties the buffer and the reload waits on a `head`
  change, so on a collision the tab stays blank and Revert does nothing.
- `protocolError` on both pages survives as the red toast under the new pattern.
- `/next` `baseCurves` (and `phaseNames`, `rangeContext`) while a non-Pattern graph is up.
- `/next` Pattern `selection` by index: the new project's region at that index reads as
  selected, and Delete removes it.
- `/next` Structure camera and hidden species (`next/Structure.svelte`, `view`, `hidden`,
  `polyFormulas`).
- App History comparison (`panels/History.svelte`, `diff`, `metrics`, `against`, `pinned`).
- App Plot when neither project has a fit and the protocol matches: no refetch, so the old
  observed curve is drawn (checked by reading; confirm in a browser).
- App `indexSnapshots`, cleared only on an `index_start` event.

Session-wide on purpose, and out of scope: the theme, panel sizes and toggles, tab
choices, the Peaks and Pattern view knobs, `refineMode`, the workflow choice, and the
Console transcript with its dropped-frame count (`Frame.svelte`'s `opened()` clears only
`calls`, "the script is this project's session").

Also stale, and cheap to fix in the same rebuild: `follow()`'s doc comment
(`gui/src/lib/stream.ts`) says a reconnect re-opens with the cursor the page holds. The
browser re-opens the URL it first used and sends `Last-Event-ID`, which the server reads
since WP-2237.

Overlap: WP-2211 (History table) and WP-2231 (Plan and Text tabs) are in flight on `/next`
panels this WP touches. Read their branches before editing those panels.

The tier of each rule this WP adds: none. It adds no flag, threshold or automatic action.

## Non-goals

- The node id scheme, which is a stored-format change.
- Persisting any view choice with the project.

## Tasks

- [ ] One project identity in each page (the open handler bumps a counter beside
  `project.path`), passed to every panel whose reload reads `head`, or a `{#key}` around
  it placed after `leaveEdits` so pending edits are saved first.
- [ ] Explicit resets at the open handler: App `applied`, `indexSnapshots`,
  `protocolError`, History comparison, Series `loaded`; `/next` `protocolError`,
  `baseCurves`, Pattern `selection`, Structure camera and toggles.
- [ ] Decide per item whether today's page earns the fix before the swap (WP-2214).
  `applied`'s Undo does: it moves the working state.
- [ ] Vitest: open two projects with equal head ids and assert each panel reloads.
- [ ] A browser check per page: open A, open B with the same node count, and read each
  panel. Run every `tests/*_browser.py` the change touches.
- [ ] Skill: none. The GUI is a human surface.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py
```

## Handover log

- **2026-11-22** — filed by WP-2237's handover from its sibling survey (one read-only
  agent, two of its claims re-checked at the line: `Report.svelte`'s reload reads `head`
  alone, and node ids are `n{len:04d}`). No open WP owns per-project client state across an
  open: 2211 and 2231 each own one `/next` panel and neither reads the open handler. Next:
  the first task.
