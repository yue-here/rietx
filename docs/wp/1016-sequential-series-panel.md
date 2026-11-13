# WP-1016 — Sequential series panel

Milestone: v1.0 · Status: ✅ 2026-08-05
Track: The human GUI
Depends on: WP-1008, WP-1010, WP-1011

## Goal

An in-situ/parametric series is drivable from the GUI: multi-file upload →
ordered series → `SequentialRefinement` run with live per-pattern progress →
trajectory plots with esds, with path-dependence surfaced as the headline
warning and per-pattern drill-down into each pattern's own history tree.

## Context

- Backend exists: `SequentialRefinement` (`sequential.py:220`) /
  `refine_sequential` (`:644`) → `SeriesResult`
  (`schemas/sequential.py:111` — mode, `entries: list[SeriesEntry]`,
  x_label, direction, diagnostics, provenance). A series is N separate
  refinements chained by a warm start — one history tree per pattern,
  pinned by `TreeHeader.data_fingerprint` — not `multi.py`'s joint
  residual; the panel must not blur that.
- Events: the series needs a series-level wrapper forwarding each
  pattern's `fit_start`/`fit_end` (`history/events.py:38` EventKind) to the
  GUI's SSE stream with a `series_index` field — additive, same `v="1"`
  rule as WP-1006.
- **`direction="both"` disagreement is the headline, not a footnote**:
  `SEQUENTIAL_PATH_DEPENDENT` (emitted per parameter at `sequential.py:631`,
  consumed by `viz/plots.py:185`) is the only check separating a measured
  trajectory from an ordering artefact — a smooth curve is exactly what a
  poisoned chain produces (WP-0505's measured lesson). The panel renders
  flagged parameters' trajectories visually distinct and puts the warning
  at the top of the series view.
- Trajectory plots: per-parameter value ± esd vs series index (or x_label),
  from `SeriesResult` — the payload matches what `SeriesResult` carries
  (state, not curves; per-pattern obs/calc comes from checking out that
  pattern's tree).
- Carry-glob editor behind Advanced disclosure: WP-0505 measured that
  `carry` is a **control** for parameters that provably must not chain, not
  tuning — the editor's help text says so.
- Defaults follow the measured WP-0505 results: `refit="single"`, carry
  everything; do not re-litigate them in the UI.

## Non-goals

- No multi-histogram (joint residual) UI — different machinery
  (`multi.py`), deferred with the compare/QPA dashboard.
- No series-level parameter editing (edit the model, re-run the series).
- No trajectory analytics beyond what `SeriesResult` + its diagnostics
  already carry.

## Tasks

- [x] Multi-file upload → ordered series (reorder/remove before run);
      series run/cancel via the session worker.
- [x] Series event wrapper: per-pattern `fit_start`/`fit_end` → SSE with
      `series_index`; progress "pattern k of N".
- [x] Trajectory plots with esds; `SEQUENTIAL_PATH_DEPENDENT` parameters
      rendered distinct + headline warning; `direction="both"` toggle.
- [x] Per-pattern navigation into that pattern's own history tree (loads
      the tree, plot follows).
- [x] Carry-glob editor behind Advanced, help text per WP-0505.
- [x] `tests/test_gui_server.py`: series rows on 3 tiny synthetic patterns;
      trajectory payload matches `SeriesResult`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0505's measured findings (`refit="single"`, carry hypothesis refuted,
  path-dependence check) — summarised in CLAUDE.md's series paragraph.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **series panel** (WP-1016, `src/rietx/gui/series.py`,
`panels/Series.svelte`, `lib/series.ts`) is the ninth tab and the only one whose
subject is a *method* rather than a model: N separate refinements chained by a
warm start, so **a smooth curve is exactly what a poisoned chain produces** and
the presentation is built around that. Five rules. **A series lives beside the
project, not inside it** — staged uploads, in-memory trees, a session-scoped
answer, `ProjectDoc.patterns` still length 1 — and its protocol (mode, plan,
limits, exclusions) is *quoted* from `project.json` rather than offered, because
one protocol over N specimens is what makes their trajectories comparable. That
is not a shortcut: an upload token dies with the session, so a persisted series
needs a document, which is WP-1003's to decide. **The order is the series**, so
every edit is a whole-list `PUT` and every file is read *there* (WP-1014's
two-phase property at N files) — with a member already described not re-read,
since a staged upload is immutable and re-reading forty patterns per keystroke
proves nothing. **The walks' disagreement is the record's number, read and never
recomputed** (WP-2003, C5): `SeriesResult.direction_gaps` holds every gap in
esds, unthresholded, and `series.trajectories` serves each path's largest, so no
path is called path-dependent. **The list opens in the series' own order, and a
gap ranking is the reader's choice** (ruled by the maintainer 2026-11-04): with no
fence, a clean ramp's gaps are noise, and ranked by them the panel opened on
`instrument.background.c1` with `phases.0.cell.a` sixth (`lib/series.ts`'s
`rankTrajectories`); the largest gap stays one click away on the gap line. And **a per-pattern tree is read-only here** —
one tree per pattern, pinned by `data_fingerprint`, so a node cannot be checked
out into this project; what makes the chain navigable is the root node's
`series_warm_start_node` note. Two shared authorities came out of it rather than second copies: `curve_arrays`, in
`viz.packed` since the file `write_html` writes became a third drawer (so no two pictures draw
residuals under two σ policies), and `session.tree_payload`.

Its **five keys on every event** are the thing to know outside the panel:
`SequentialRefinement.fit` takes `events=`/`cancel=` (since this WP — WP-1008's
charter said it already did), and `_SeriesStream` stamps
`series_index`/`series_label`/`series_n`/`series_pass`/`series_cold` onto
existing kinds, so `EVENT_SCHEMA_VERSION` does not move and "pattern k of N"
reaches the run record through the *existing* `stage`/`stage_index`/`n_stages`.
The console pays for that: five fields on every `eval` pushed the cost off the
right edge, so `lib/stream.ts` folds them into one `[T300 1/3 ↩]` prefix.
Measured browser facts: the plot is the chart module's canvas since WP-1461, in
a host that clips it, and its `ResizeObserver` refits it 539 → 1480 px when the
column takes the window, so no canvas overhangs a control (WP-1015's trap was
plotly's); a *rotated* y-axis title shares the fixed left margin with the tick
labels, so `phases.0.cell.a` clipped to `aes.0.cell.a` and the axis takes the
**leaf** (the heading above carries the path); and the staged table's floor is
per column — core 308 px, detail 231 — reflowed by `lib/resize.ts:seriesCompact`
beside `modelStacks`, because the reorder buttons are the last column and the
panel's main verb.

## Handover log

- **2026-08-05 — closed ✅.** Branch `wp1016-series-panel`, eleven commits.

  **Done.** The library half first, because the WP's charter was wrong about it:
  WP-1008's Inherited said "`SequentialRefinement` already emits per-pattern
  events and takes `events=`/`cancel=`" and **it did neither** —
  `_fit_one` called `ref.fit(data, mode=, plan=, two_theta_limits=)` and nothing
  else. So `fit` now takes both, `_SeriesStream` (an `EventStream` subclass, so
  `as_event_stream` passes it through and the pattern's fit does not close the
  stream the series owns) stamps `series_index`/`series_label`/`series_n`/
  `series_pass`/`series_cold` onto existing kinds, and `unique_labels` came out of
  `_labels_for` so a caller can *show* the names the run will use. Cancellation
  **returns** what completed with a new `SEQUENTIAL_CANCELLED` — WP-1006's rule
  one rank up, since the in-flight pattern is abandoned by `Refinement.fit` itself
  while the walked ones are committed fits that raising would discard — and a
  cancelled forward chain skips the verification pass, because the comparison is
  between two *complete* chains.

  Then six routes (`GET`/`PUT /api/series`, `POST /api/series/run`, `GET
  /api/series/{result,window,history}`) over a new `gui/series.py`, and the ninth
  tab. Two shared authorities rather than second copies: `session.curve_window`
  and `session.tree_payload` hoisted out of `result_window`/`history`, and
  `project.fitted_mask` made a function so a series member asks the same question
  about which channels a run fits.

  **The three seams WP-1008 left to settle, settled.** (a) A series lives
  **beside** the project: staged uploads, in-memory trees, a session-scoped
  answer, `ProjectDoc.patterns` still length 1 — and it inherits the *project's*
  protocol (mode, plan, limits, exclusions), quoted rather than offered, because
  one protocol over N specimens is what makes their trajectories comparable. (b)
  It rides the one run machine as `kind: "series"`, and "pattern k of N" reaches
  the run record through the **existing** `stage`/`stage_index`/`n_stages` — the
  same reuse an indexing run makes, so no field and no `EventKind` is new. (c) No
  second container verb: an upload token dies with the session, so a *persisted*
  series needs a document, which is left to **1003** below rather than added here.

  **Measured, and one of them changed the design.** The clean three-pattern ramp
  **agrees** between chain directions — every parameter's between-chain distance
  under 5e-4 σ — which is the right answer and left the flagged branch
  unexercised, so `n_sigma` is pinned against the fence on a *constructed* 4.95σ
  disagreement instead (`test_the_served_disagreement_is_the_fences_own_arithmetic`).
  It also killed the first ranking rule: sorting *unflagged* trajectories by that
  noise put `phases.0.cell.a` eighth of fifteen. And the staged table's floor is
  per column — core 308 px (index, label, coordinate, the reorder buttons), detail
  231 — measured in a browser, now `lib/resize.ts:seriesCompact`.

  **A fifth defect came from auditing my own unmeasured claim**, which is this
  WP's lesson turned on itself. `lib/series.ts` said a `null` in
  `error_y.array` leaves a gap; measured against plotly 3.7.0 it does not — the
  bar's two caps are drawn at the point with zero height between them,
  byte-identical to what a `0` produces, so a pattern that estimated nothing
  rendered as one that measured the value exactly. The bars now ride an invisible
  carrier trace over the subset that *has* an esd (a tied path with no esd
  anywhere went from three flat caps to none). And the measurement that stays: a
  well-determined trajectory shows **no visible bar** — σ(a) 6.5e-6 Å against a
  4.8e-3 Å axis over 189 px is a 0.5 px bar, and 0.5 px is exactly what was
  drawn. Scaling it to be seen would be WP-1029's "an exaggeration is not a
  probability" one panel over.

  **The browser pass found four defects and one negative**, per the standing
  streak. Ranked-by-noise (above); the table side-scrolling its own main verb off
  the right edge; the console rendering five series keys as fields on **every**
  `eval`, so the cost was pushed off the edge (now one `[T300 1/3 ↩]` prefix in
  `lib/stream.ts`); and the per-pattern plot's x axis anchored to the upper
  subplot, so "2θ (deg)" ran through the middle of the residual (`Plot.svelte`
  already had `anchor: "y2"`). The negative is worth keeping: **this plot is
  plotly SVG, not canvas** — zero canvas elements, zero unreachable controls after
  scrolling — so WP-1015's swallowed-click trap cannot apply to it, because
  `Plot.svelte` draws its residual with `scattergl` and *that* is what made it a
  canvas there. The `ResizeObserver` still earns its place: 539 → 1480 px when the
  column takes the window. The jsdom mounts found two more first (a page reload
  lost a finished series; `bind:value` made the carry glob depend on an `input`
  event having fired before the `change`).

  **A cap decision, deliberately.** `CLAUDE.md` was at its 700-line cap, and this
  WP's root-level rule is 5 lines of library contract. Compression was tried —
  four passages tightened, the GUI paragraph's duplication of `gui/CLAUDE.md`
  removed — and the document has no narrative left to move, so `SIZE_CAPS` is 720
  with the reasoning in the test's own comment, including the 25 lines of
  bullet-list reflow slack a future session should spend before raising it again.

  **Next / gotchas.** [1017](1017-gui-manual-onboarding.md) is the last GUI WP and
  now documents nine tabs, not eight; the Build panel's owed list is empty and the
  mechanism is kept for the next one. Series settings are session-scoped, which is
  the one thing a user will notice as missing — that is 1003's call, and the
  Inherited note is filed there.

- **2026-07-29** — created from the v1.0 GUI plan.
