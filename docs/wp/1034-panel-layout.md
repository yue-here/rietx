# WP-1034 — Model and Text in the right panel

Milestone: v1.0 · Status: ✅ 2026-08-05
Track: The human GUI
Depends on: 1013, 1014, 1029 (all landed) · soft: 1032

## Goal

Editing a parameter and seeing the fit change are the same glance: the model
editor and the text document become tabs in the right panel beside the plot,
with a full-window mode kept for the two things that are genuinely wide, and the
open/recent screen reachable without restarting the program.

## Context

**The user's words**: *"Text mode and model mode should fall into the right
panel; users are used to viewing the change in refinement after making edits to
the parameters."* That is a workflow argument, and it is a good one — every
other panel in the app is beside the plot, and the two that are not are the two
where an edit most obviously wants a before/after.

**This re-opens a decision that was taken twice, on grounds that were sound.**
WP-1013 made the text pane a mode over the whole window because five tabs
already filled the sidebar and its content is line-oriented — the `.rxt` columns
are aligned precisely so a rectangular selection can hit one field, which a
340-560 px sidebar undoes. WP-1014 made the model pane a mode for two further
reasons: an atom table is eight columns wide, and it is the only pane that must
work with **no project open at all**, which no tab can. WP-1029 then declined to
re-litigate either, and settled the *control* instead — one segmented
`[ Plot | Model | Text ]` in the header (`App.svelte:81-85`).

**What has changed since, and it is the whole case for revisiting**: WP-1029
made the panel column draggable. `.side` is `flex: 0 0 clamp(340px, 38%, 560px)`
until a drag replaces it with a number, and its `max-width` is **72 %** of the
window (`App.svelte:762-773`); `fitColumns` re-clamps a stored width at render
so one chosen at 1500 px cannot leave a column 24 px wide at 1000 px
(`lib/resize.ts:61-71`). So "the sidebar is too narrow for this" may simply no
longer be true — but **nobody has measured it**, and that is task 1.

### The recon that comes first

The user chose "tabs, with a full-window escape hatch kept" **without numbers in
front of them**. The decision stands; this WP's first job is to put the numbers
behind it, and to say so if they contradict it:

- The Model pane's **minimum content width** — it is three columns today
  (`Model.svelte`, with two `Splitter` grips at `:805-809` and `:873-877`), and
  the atom table is the widest content. Measure at what width it stops being
  readable, on NAC (four species, aniso) rather than on a two-atom cell.
- Whether the atom table fits at **560 px**, the current `clamp` ceiling, and at
  the 72 % `max-width`.
- The `.rxt` document's natural column width — the format is column-aligned by
  design, so the number is the longest rendered line on a real project, not a
  guess.

If those numbers say the pane cannot work as a tab even dragged wide, **report
back rather than shipping a cramped tab**: the escape hatch would then be the
primary surface and the tab a shortcut to it, which is a different design and
the user should get to choose it with the measurements in hand.

### The recon, measured

**2026-08-05**, Chrome for Testing (playwright chromium-1223) against the
shipped build on a real NAC project — COD 1000236 read `aniso=True` (six atoms,
four species, an aniso tensor on every site) plus the CaF₂ impurity phase,
`11BM_NAC.fxye`, limits 2–24° — at a 900 px viewport height and
`deviceScaleFactor: 2`. The `.protocol` strip WP-1033 added is present in every
row below, which is what the inherited note asked for.

| window | `.side` | plot column | `.protocol` | plot height | 6 tabs | 8 tabs |
|---|---|---|---|---|---|---|
| 1500 | 560 (clamp ceiling) | 940 | 32 px, one row | 749 | fits (559) | fits (559) |
| 1200 | 456 | 744 | 32 px | 716 | fits (455) | fits (455) |
| 1000 | 380 | 620 | 64 px, **two rows** | 667 | fits (379) | **overflows** |
| 860 | 340 (clamp floor) | 520 | 64 px, two rows | 650 | fits (339) | **overflows** |

**1 · The Model pane's minimum content width is 472 px** — the atom table's
`min-content` is **448 px** and the column adds 24 px of padding. Below it the
column side-scrolls: by 15 px at 456, 91 px at 380, 131 px at 340, and what
scrolls is *the whole column*, so the cell row and the headings leave with the
table (visible in the 860 px screenshot: `10.25710.25790` where a, b, c should
be). At 472 the table is whole with its `occ` box at its 44 px floor; at 560
nothing is at a floor (narrowest input 74 px).

**2 · It fits at 560, and a drag reaches it at every width measured.** The
clamp ceiling leaves 88 px spare, and the 72 % `max-width` is 1080 / 864 / 720 /
619 px at the four windows — all above 472. What the *default* cannot do is
reach 472 below a ~1245 px window (38 % of the window ≥ 472).

**3 · The `.rxt` document has two widths, and only the larger one is the
comments'**: 165 lines, 12 px `ui-monospace` at 7.3 px/char, 47 px gutter. The
**editable columns** — everything left of the trailing `#`, which is what a
rectangular selection has to hit — are at most 69 chars, **546 px with the
gutter**. The whole line with its comment reaches 98 chars, **756 px**. So at
the 560 px ceiling **0 of 165 lines** scroll an editable column while 110 scroll
their comment; at 456 px, 60 lines lose an editable column; at 340 px, 85 do.
Comments stop scrolling only past 720 px.

**Verdict: the tabs decision stands, and it acquires a condition.** WP-1013's
argument was that a 340–560 px sidebar undoes the `.rxt` alignment; measured,
that is true at the 340 px floor and **false at the 560 px ceiling**, where every
field a rectangular selection needs is on screen. Both panes therefore work as
tabs *at the ceiling and above*, and neither works at the floor — which is what
makes the full-window hatch load-bearing rather than decorative at ≤1000 px
windows, and what the Model pane's reflow is for.

### What the change touches

- **The tab strip goes eight wide.** It is already six
  (`App.svelte:630-637`: Parameters, Plan, Peaks, Report, History, Build) —
  WP-1013 predicted five was the limit and it has been over that since WP-1027.
  **Settle overflow before adding tabs, not after**: a strip that silently
  truncates is worse than the mode buttons it replaces. Measured: eight labels
  need **415 px** squeezed and 533 px unsqueezed, so they fit at the 560 and
  456 px sidebars and overflow at 380 and 340 — i.e. below a ~1090 px window.
- **Everything stays mounted.** The current panels are hidden with
  `class:hidden`, never unmounted, because switching must not throw away a
  filter, a pending edit, an unsaved stage list or a two-node comparison
  (`App.svelte:638-639`); the text pane additionally builds its editor on first
  entry and keeps a typed buffer across a visit elsewhere. Both properties must
  survive the move.
- **`Model.svelte` reflows to one column when narrow**, its 3D column becoming a
  collapsible section rather than a third of a 400 px pane. Note what that
  interacts with: the viewer's plot needs its `ResizeObserver`, because plotly's
  `responsive: true` listens for **window** resizes only and an oversized canvas
  swallows the clicks of any control under it — a trap that has now bitten two
  panels.
- **The full-window hatch stays** for both, and the header control has to make
  "where am I" and "where can I go" one reading, which is WP-1029's stated
  reason for the segmented three. Two routes to one pane is the cost the user
  accepted; the control must not become two controls again.
- **The open/recent screen rides along.** The import wizard *is* `Model.svelte`
  (`showWizard = !project || wizardOpen`, `:134`), so once Model is a tab the
  wizard is in the right panel. Half the route back already exists — the
  palette's "Import a new project" sets `wizardOpen` with a project open
  (`Model.svelte:451`, `App.svelte:414-415`). What is missing is the **recent
  list inside the wizard** rather than only in the empty state
  (`App.svelte:589-604`, fed by `api.recent()` only when `GET /api/project`
  fails with `NO_PROJECT`), a header control beside the palette entry, and a
  decision about what "open another" does to the session in flight.

### Rules that bind the implementation

- **Widths persist in `ProjectDoc.ui`, owned by the shell**, and the splitter
  **reports a size and never writes one** (`onsize(size, done)`, false on every
  pointer move and true once on release). Do not add a second splitter.
- **A stored size must be re-clamped at render**, not only at drag —
  `fitColumns` exists because a drag clamps against the extent it happens in and
  nothing clamps a width that outlives its window.
- **An effect that reads the project *object* refires on every `ui`-only PATCH**
  — Model reloads on a boolean `$derived` keyed to the project *path*, or a pane
  drag refetches three routes and the 3D geometry with the head unmoved.
- A drag is **refused persistence while a run is in flight** (409); that is a
  known wart filed as a freeze question in [1003](1003-api-freeze-pypi.md), not
  this WP's to settle.
- **Protocol controls may not be moved in beside drawing controls** (WP-1033).
  The `.protocol` strip is separate from `.knobs` because one set changes what
  is fitted and the other changes only the picture; if this WP reflows the plot
  column, that separation is the thing to preserve — a rule in `gui/CLAUDE.md`,
  not a layout preference.

## Non-goals

- **Not the repairs** ([1032](1032-gui-repairs.md)) or the fitted range
  ([1033](1033-plot-range-regions.md)).
- **Not a redesign of the panels themselves** — this moves them and reflows
  `Model.svelte`; it does not restyle the parameter table.
- **Not the manual** ([1017](1017-gui-manual-onboarding.md)); write into that
  WP's inherited mailbox on sign-off, because this WP changes the two sentences
  that chapter would have opened with.
- **Not multi-project**: "open another" replaces the session's project as it
  does today; nothing here opens two at once.

## Tasks

- [x] **Recon**: the three measurements above, on NAC, at 1500/1200/1000/860 px.
      Write the numbers into this file. If they contradict the tabs decision,
      stop and report rather than shipping a cramped tab. — § "The recon,
      measured": 472 px for the Model tab, 546/756 px for the `.rxt` document's
      two widths, and the decision stands with a condition.
- [x] **Tab-strip overflow** settled first — scroll, wrap, or a grouped
      overflow control — with a mount test that a hidden tab is still reachable.
      — **wrap**: the buttons no longer grow to fill the row and no label is
      ever shortened, so a strip too narrow for eight takes a second row. One
      row at a 455 px column and above, two at 379 and 339.
- [x] **Model and Text as tabs**, both still always-mounted, the text pane still
      building its editor on first entry and keeping its buffer.
- [x] **`Model.svelte` reflows to one column** below a threshold, 3D collapsible,
      with the `ResizeObserver` intact for the viewer. — `modelStacks` in
      `lib/resize.ts`, threshold 932 px = the three columns' floors; the header's
      own `3D` button is the collapse control in both layouts.
- [x] **The full-window hatch**, reachable from one control that still answers
      "where am I" in one reading, and from the palette. — it is the *column*
      that expands, tab strip and all, so the hatch covers eight panels rather
      than the two that used to have a mode; header control `Split | Full`.
- [x] **Recent list inside the wizard**, a header route to it with a project
      open, and the "open another" behaviour decided and written down. —
      `Open…` in the header; opening one **replaces** the session's project with
      no prompt, because settings persist on the verb and the log is on disk, so
      there is nothing unsaved (and a run in flight is refused by
      `project_open`'s own 409).
- [x] Tests: mount tests for tab reachability, the reflow threshold's pure
      function, buffer survival across a tab switch, and the wizard's recent
      list with a project open. — vitest 321 → 330.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

And in a real browser on the NAC project (COD 1000236 + `11BM_NAC.fxye`), in
both themes at 1500 px and at 1000 px: edit a cell parameter in the Model tab
and **watch the plot beside it**, which is the entire point of the WP; then
confirm the atom table is readable at the width the recon said it needed, and
that a typed text buffer survives a trip to Parameters and back.

jsdom has no layout, so the reflow's *behaviour* is testable and its *effect* is
not — the screenshot is the check. Playwright's viewport option is
`newContext({ viewport })`, **not** `viewportSize`, which is silently ignored.

### What the browser pass found

Run on the NAC project at 1500 / 1200 / 1000 / 860 px in both themes, against
the built dist. Four things, and only the first was in the plan:

- **Three columns still split evenly, so the reflow threshold was not the
  whole fix.** At a 1000 px pane `modelStacks` correctly says "do not stack",
  and the structure column then got **306 px** against the 472 it needs, while
  the two columns that needed less had more than enough — `flex: 1 1 0` shares
  free space equally from a zero basis. Each column now *starts* at its own
  floor (472 / 200 / 260) and shares the surplus with the 3D column's 1.25
  preference intact: 1000 px → 490 / 218 / 282, 1500 px → 644 / 372 / 475.
- **A lone wrapped tab read as a banner.** With the buttons growing to fill
  their row, `Build` alone on the second row stretched across the whole 339 px
  column. They no longer grow.
- **The header pushed two controls off the window** at 860 px with a fitted
  project: `Cancel` and `⌘K` sat 118 px past the right edge, because the row's
  only shrinkable item is the filename and it had already collapsed to nothing.
  The header wraps now — the tab strip's rule one rank up — and `.project` takes
  `flex-basis: 0`, or its natural width forces a break at 1200 px for nothing.
- **The two panels contradicted each other about whether a fit existed.** An
  edit discards the curves server-side (`refine.set_values`: "the fitted curve
  and statistics described the *old* values") but the *run frame* survives it,
  so the header printed `Rwp 9.582%` beside a plot saying "No fitted curves
  yet". Invisible while the editor was a mode over the window; unmissable the
  moment they share a screen. The frame is now the source only while a run is in
  flight.

And one thing that is **not** a defect but is the WP's premise, narrowed: the
before/after glance has a gap in the middle. Applying an edit empties the plot
— by design, one rank down — so the sequence is *edit → the curves go → Run →
the new curves land beside the editor*, verified end to end (Rwp 9.582 %,
cell 10.3 → refined back to 10.25121). The manual chapter should say so; the
alternative, drawing curves that describe values the model no longer holds, is
the thing this package refuses everywhere else.

## References

- `docs/wp/1013-text-pane-sync.md` and `docs/wp/1014-import-structure-editing.md`
  — the two decisions this WP revisits, and why they were right when taken.
- `docs/wp/1029-gui-usability.md` — the splitter, the segmented control, and
  `fitColumns`.
- `gui/CLAUDE.md` — the always-mounted rule and the `responsive: true` trap.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**One column, nine panels** (WP-1034, `App.svelte`, `Model.svelte`,
`lib/resize.ts`) is where the panels live: Model and Text stopped being modes
over the window and became tabs beside the plot, and the full-window surface
they had is now **the column expanding, tab strip and all** — one hatch for
every panel instead of two, with the header's `Split | Full` the only control
for it (session-local: a layout is a view choice, not a setting). Five rules,
each a measurement in the WP. **A panel's minimum width is measured, not
chosen** — the atom table's `min-content` lives in `MODEL_MIN` (`lib/resize.ts`), the `.rxt`
document's *editable* columns end at 546 px with the gutter and its trailing
comments at 756, against a sidebar that clamps at 340–560 and drags to 72 %: so
WP-1013's "a narrow sidebar undoes the alignment" is true at the floor and false
at the ceiling. **A column that must not lose gets a flex *basis*, not a share**
— equal `flex: 1 1 0` gave the structure column 306 px of a 1000 px pane while
the columns needing less had plenty, and a basis is not a maximum, so a drag
still overrides it. **Overflow is wrap, never truncation, and it applies to the
header too**: no tab label is shortened, the buttons do not grow (a lone wrapped
tab stretched into a banner), and the header wraps because at 860 px it had
pushed `Cancel` and `⌘K` past the window's edge — a wrapping row breaks on its
items' *bases*, so anything meant to ellipsise instead needs `flex-basis: 0`.
**A statistic outlives the thing it describes**: an edit discards the curves
server-side, but the run frame keeps its Rwp, so the header printed a fit's Rwp
beside a plot saying there was none — the frame is the source only while a run
is in flight. That class of bug is invisible until two panels share a screen,
which is the argument for tabs restated as a defect. And **opening another
project replaces the session's** with no prompt and no dialog: settings persist
on the verb and the log is on disk, so there is nothing unsaved, and a run in
flight is already refused by `project_open`'s 409. **There is no read-only way
to open one** — every verb writes into the directory and `Project.open` appends
a head annotation before any verb runs — so looking without changing means a
copy: `rietx gui --scratch` (byte-for-byte, temp dir), `--state-dir` to put the
recent list somewhere else, and `*.rex/` in `.gitignore` (WP-1204).

## Handover log

- **2026-08-05** — **closed.** Every task landed, in two commits on
  `wp1034-panel-layout` (branched off `main` at `4ed0604`): the recon, then the
  move itself.

  **Done.** Task 1's three measurements are in § "The recon, measured" and they
  *narrowed* the user's decision rather than contradicting it — 472 px for the
  Model tab, 546 px for the `.rxt` document's editable columns and 756 for its
  comments, against a sidebar that clamps at 340–560 and drags to 72 %. Then:
  eight tabs with a wrapping strip; Model and Text as always-mounted tabs; the
  full-window mode generalised from *two private modes* to *the column
  expanding, tab strip and all*, under one `Split | Full` control; the model
  pane stacking below 932 px with its 3D as a section and its atom table in its
  own scroller; the recent list inside the wizard with `Open…` as the header
  route. vitest 321 → 330, `svelte-check` clean, fast suite unmoved at
  1660/108 (no Python test was added or needed).

  **The browser pass earned its keep again, four times** — § "What the browser
  pass found" has them. The one to carry forward is the rule, not the fix: **a
  defect can be invisible until two panels share a screen.** The header had
  been printing a fit's Rwp beside a plot that said there were no curves for as
  long as `set_values` has discarded them; nothing about it was new, and it was
  simply not visible while the editor covered the plot.

  **What a successor should know.** The reflow threshold is arithmetic over
  three floors in `lib/resize.ts`, and the floors are *measurements* — if the
  atom table gains a column, re-measure `MODEL_MIN.structure` rather than
  nudging it. The `Full` layout is deliberately **not** persisted (a layout is a
  view choice, WP-1033's line); if that turns out to be wrong in use, the fix is
  one `ui` key and `readUi`. And the WP's own premise is now narrowed in writing:
  an applied edit empties the plot until the next run, by a rule one rank down,
  so the glance is *edit → Run → compare*.

  **Not done, on purpose:** nothing from the task list. Forward references went
  to [1017](1017-gui-manual-onboarding.md) (the chapter's opening sentences, and
  the edit-empties-the-plot fact only a manual can state),
  [1016](1016-sequential-series-panel.md) (it is the ninth tab; the strip wraps
  and the hatch is free) and [1035](1035-symmetry-surfaced.md) (the pane it
  edits is now routinely 340–560 px and stacks).

- **2026-08-04** — created from a user's list after driving the shipped GUI,
  alongside [1032](1032-gui-repairs.md), [1033](1033-plot-range-regions.md),
  [1035](1035-symmetry-surfaced.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **This is the only redesign in the set, and it was separated out for that
  reason**: the other GUI items are hour-sized repairs that must not be held
  hostage to it.

  **The user's decision is on record and is binding: tabs, with the full-window
  mode kept.** It was taken without measurements — a planning failure worth
  naming, since the numbers were available and nobody fetched them — so task 1
  fetches them, and contradicting the decision *with numbers* is a legitimate
  outcome the user asked to hear about.

  **The strongest argument for the change is not aesthetic.** Every other panel
  is beside the plot; the two that are not are the two where an edit most wants
  a before/after. The strongest argument against is still WP-1013's and it has
  not been refuted, only made measurable: the `.rxt` format's columns are
  aligned so a rectangular selection can hit one field, and a narrow pane undoes
  that. Both of those sentences should survive into the manual.
