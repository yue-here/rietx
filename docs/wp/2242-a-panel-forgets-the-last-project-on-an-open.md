# WP-2242 — a panel forgets the last project when another opens in the same window

Milestone: gui-overhaul · Status: ✅ 2026-11-23 — every per-project panel on both pages is keyed on an open count; the Report undo cannot cross projects; PR #1793
Depends on: —

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
panels this WP touches. Read their branches before editing those panels. *Superseded
2026-11-23:* both branches are merged into `main`; the open overlap is PR #1792 (WP-2240), which
edits `next/Frame.svelte` and `next/Pattern.svelte` and rebuilds the dist.

The tier of each rule this WP adds: none. It adds no flag, threshold or automatic action.

## Non-goals

- The node id scheme, which is a stored-format change.
- Persisting any view choice with the project.

## Tasks

- [x] One project identity in each page (the open handler bumps a counter beside
  `project.path`), passed to every panel whose reload reads `head`, or a `{#key}` around
  it placed after `leaveEdits` so pending edits are saved first.
- [x] Explicit resets at the open handler: App `applied`, `indexSnapshots`,
  `protocolError`, History comparison, Series `loaded`; `/next` `protocolError`,
  `baseCurves`, Pattern `selection`, Structure camera and toggles.
- [x] Decide per item whether today's page earns the fix before the swap (WP-2214).
  `applied`'s Undo does: it moves the working state.
- [x] Vitest: open two projects with equal head ids and assert each panel reloads.
- [x] A browser check per page: open A, open B with the same node count, and read each
  panel. Run every `tests/*_browser.py` the change touches.
- [x] Skill: none. The GUI is a human surface.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py
```

## Handover log

- **2026-11-23** — closed. Opening another project in the same window now shows that
  project in every panel, on both pages, even when the two projects' histories are the same
  length. Before, a panel that waited for the history head to change kept the last project's
  numbers, and the Report tab could undo a suggestion by checking out a node from the last
  project's history in the new one. Each page now counts the projects it has opened, and
  every panel whose contents belong to the project is rebuilt when that count moves. The
  next project's fit is read before any panel is rebuilt, so none shows the last project's
  fit, even for a moment. A reload was the workaround before. PR #1793.

  *Decision (task 1): rebuild the panels, rather than hand each one the count to reload
  on.* Settled by Claude under the WP's own task 1, which names both, and the class rule
  ("fix the class"). Rebuilding reaches state nobody listed (a selection index, a camera, a
  slider range, a Series `loaded` flag) with no per-panel edit for a future panel to
  forget; the runner-up needs about eighteen. Each page counts opens (`opens`, bumped in the
  one function every opener lands in: `App.svelte:adopt` and `Frame.svelte:opened`), after
  `leaveEdits` has kept the pending edits. `{#key opens}` wraps today's Background graph
  and all ten side tabs (Plan's own key folded in), and at `/next` the graph pane, the
  Indexing, Parameters, Interactive, Plan and Text panes, and History (two `{#key
  project.path}` replaced, since a reset example keeps its path). Left mounted on purpose:
  today's Plot, for its view knobs (scale, residual, hidden layers), which the open asks
  to redraw through `plotKey`; Model, mounted once by WP-1205's rule, which now reloads on
  `opens` rather than the path; the Console and the action bar.

  *Done.* Resets beside the keyed panels. Today's page clears `applied` (so the Report's
  undo node never reaches another project's checkout), `indexSnapshots`, `protocolError`,
  the zoom, the hovered peak, the curves the sliders measure from, and the pending counts
  and preview the keyed panels hand up. `/next` clears the same mirrors (pending counts,
  holds, slider values and previews, the Text preview), `protocolError`, `baseCurves` and
  the status readout. Both pages read the fit (today's also the peak list) before
  publishing the project, so the keyed panels mount on the next project's in one flush.
  Task 3: every item on today's page took the fix, since keying cost the same there as at
  `/next`. `lib/stream.ts`'s `follow()` comment now says a reconnect sends `Last-Event-ID`.
  The rule ("a panel whose state is the project's sits inside `{#key opens}`") went into
  gui/CLAUDE.md and came out again: that file sits at its byte budget
  (`tests.rulebook_limits`), and the vitest tour below is the check that keeps it, failing
  on a panel that reads its routes once and keys on `head`.

  *Review* (`/code-review high --fix`, eight findings). Six fixed: Model kept its chosen
  phase index across an open, and a two-phase project's second phase then read past a
  one-phase project's last (reset on `forget`, clamped on load); `adopt` clears `applied`
  and the peak list outright, in place of a count tag on `applied`; the browser check waits
  for the project's own name in the Text buffer; two comments. Two the reviewer left as
  decisions, both fixed here by one change: the keyed panels mounted on the last project's
  fit for one round trip (today's Report offered its diagnostics with live Apply buttons),
  and `/next`'s Pattern graph fetched the curves twice per open. Reading the fit before
  publishing the project fixed both (gui/CLAUDE.md's "two assignments either side of an
  await are two flushes"); the `/next` vitest pins one curves request per open.

  *Not generalised.* The server keeps no project identity of its own: a checkout carries no
  token naming the project it was meant for, so a third client page would need the same
  care. `tree_id` cannot serve, being the data's fingerprint, which two projects on one
  pattern share; a session counter on the wire was dropped as a wire change for a case
  the client now closes. A response from a panel the rebuild destroyed that lands after the
  open is not guarded; an open waits on `leaveEdits`, the open request and the fit, and
  none was seen.

  *Measured* (`[dev]` + playwright 1.65.2, darwin/arm64, worktree venv, load average about
  2, no other suite running). vitest 986 passed in 60 files (981 in 59 on `main`; +5 cases,
  +1 file), svelte-check 487 files 0 errors. The five new vitest cases fail on `main`'s
  pages (`/api/params 1 of 3` and `1 of 4` short; curves `1` against `2`; "applied
  refine_cell" still shown). GUI browser files, run inside the fast selection on the final dist, all passed: test_gui_browser 4, test_gui_console_browser 1, test_gui_layout_browser 51, test_gui_peaks_browser 2, test_gui_recovery_browser 5, test_gui_switch_browser 2 (new), 65 in all; the same 65 passed alone before the review fixes.
  `tests/test_gui_switch_browser.py`'s two rows fail on `main`'s dist (timed out waiting for
  b's cell, 30 s). Fast selection, through ghostshift's `serial.py`, alone on the machine: 15359 passed, 438 skipped, 32 xfailed, 8:14 wall. This branch adds two pytest rows, both in the new browser file; `main` moved since WP-2237's count, so the delta is stated, not subtracted. Added-test cost (`tests.added_test_times`, this run): 4.08 s and 1.73 s, 5.81 s for the file, each a real chromium page; it skips in CI with every browser file.

  *Gotchas.* In a worktree-isolated runner, a Bash command whose text mentions a git verb
  in prose (a heredoc holding "checkout", or the word in a test name) is refused as git;
  write the text to the scratch directory and apply it with a script. A Parameters number
  is drawn in several spans, so `inner_text()` returns `4\n.\n1`; read `text_content()`.

  Next: none on this WP. PR #1792 (WP-2240) edits `next/Frame.svelte` and
  `next/Pattern.svelte` and rebuilds the dist, so whichever of #1792 and #1793 merges
  second merges `main` and rebuilds.

- **2026-11-22** — filed by WP-2237's handover from its sibling survey (one read-only
  agent, two of its claims re-checked at the line: `Report.svelte`'s reload reads `head`
  alone, and node ids are `n{len:04d}`). No open WP owns per-project client state across an
  open: 2211 and 2231 each own one `/next` panel and neither reads the open handler. Next:
  the first task.
