# WP-1027 — GUI peak picker and indexing panel

Milestone: v1.0 · Status: ✅ 2026-08-01 — browser pass done (two measured pointer defects fixed), extinction screen served and rendered; the indexing line ends in pixels
Track: Indexing
Depends on: 1010, 1011, 1018-1024 (1009 touched)

## Goal

A human can see every fitted peak against the data, correct the ones the fitter
got wrong, run indexing, and read the candidate table — including what the data
cannot distinguish — without leaving the browser.

## Goal, restated

Peak picking is the one step in this workflow where a human eye genuinely beats
the algorithm: a shoulder the fitter missed is obvious on screen and invisible
in a number. This panel exists for that, not for convenience.

## Context

- **Stack is already decided** (DESIGN.md §Outputs, 2026-07-29 amendment):
  local web app, stdlib `http.server`, SSE on `ThreadingHTTPServer`, Svelte 5 +
  TypeScript with **committed** build assets shipping in the wheel, plotly from
  the installed package, `[gui]` extra = plotly only. Every verb is a plain
  method on `GuiSession`; `server.py` is transport only, so a Tauri shell can
  wrap it later.
- **Session verbs** (all plain methods):

  ```python
  pick_peaks(**opts) -> PeakList
  add_peak(two_theta) -> PeakList        # seed + refit that group
  remove_peak(i) -> PeakList
  move_peak(i, two_theta) -> PeakList    # drag → reseed + refit the group
  set_peak_flags(i, *, use_for_indexing=None, flags=None) -> PeakList
  refit_group(g, *, n_components=None) -> PeakList
  index(**opts) -> str                   # run id — long-running
  index_result() -> IndexingResult
  adopt_candidate(i, *, space_group=None) -> str   # history node id
  ```

  Every verb echoes its equivalent API call into the console pane
  (`session.move_peak(7, 23.451)`), so the session log stays a reproducible
  script — the GUI's standing rule from DESIGN.md §Outputs.
- **The peak-list verbs are cheap and synchronous; `index()` is not.** It goes
  through WP-1006's run state machine — cancel token, SSE progress, the
  409-while-running rule. That means the run kind must not be refinement-only;
  an Inherited-mailbox note was left in WP-1006 for exactly this.
- **Peak lists are a project artifact, not a history node.** They live in
  WP-1005's `.rex/` container as `peaks.json`, keyed by `data_fingerprint`, so
  a peak list can never be displayed against the wrong pattern — the same
  device `TreeHeader.data_fingerprint` uses for history trees. By contrast
  `adopt_candidate` **is** a model edit and goes through
  `Refinement.edit(structure=…, label="adopted indexed cell …")`, which already
  records an `edit_model` node: **no new NodeKind**.
- **The plot shows the fitted group profile over the data**, not just a tick
  mark, plus a per-group residual strip. That is the whole point: it is what
  lets a human see the `PEAK_UNRESOLVED_SHOULDER` case the fitter reported but
  could not resolve. Peak markers carry `2θ ± σ` error bars; excluded peaks are
  drawn hollow; flags drive colour.
- **Interactions**: click empty space → `add_peak`; drag a marker →
  `move_peak`; shift-click → cycle `impurity_candidate` / `excluded_by_user`;
  right-click a group → "fit N components". Peak-list diagnostics render as an
  inline strip, not a modal — they are information, not an interruption.
- **The candidate view is deliberately a table**, one row per candidate, one
  column per FoM panel member, `found_by` as engine chips, ambiguity partners
  as an expandable sub-row. A table cannot express a confident singleton, which
  is the same property WP-1024 gives the API. **"Adopt" is per-row and disabled
  with a tooltip when `confidence != "high"`** — the UI must not be the place
  the gate leaks.
- **`.rxt` gains a `peaks` block** (format reserved by WP-1009). Peaks are not
  refinable parameters, so they carry **no `@` marker** — that is the visual
  distinction from every other block:

  ```
  peaks 20                              # pick_peaks(min_sigma=5.0, shape=tchz)
    #      2theta      esd     fwhm         I    flags
     0     8.4712   0.0009   0.0812     10420
     1    10.7743   0.0011   0.0834      3310   impurity
     2    12.0316   0.0026   0.0901       220   kbeta_ghost excluded
  ```

  On apply, **only the `2theta` and `flags` columns are editable** — a 2θ edit
  is a `move_peak` (refit the group), a flags edit is `set_peak_flags`; every
  other column is derived and regenerated on the next render. Same
  all-or-nothing delta semantics and 1-based line numbers as the rest of the
  format, and the existing hypothesis `render → parse → render` fixed-point
  test extends to cover it.

### What the landed neighbours settled (Inherited, pruned 2026-07-31)

**Peak-list semantics (WP-1026).** `pick_peaks` emits components flagged
`not_separable` — shape the fitter believes in, a line it does not — kept in
`PeakList.peaks` but excluded from `usable()` like the Kβ/W ghosts. On real lab
data `len(peaks.peaks) != len(peaks.usable())` is the *normal* case (8 of 63 on
bundled corundum), so the panel renders both, distinguished. `not_separable` is
the flag a user most wants to overrule; `excluded` is the existing route for a
caller's own decision, and overruling `not_separable` is a *different* act that
should look different. A pattern full of `not_separable` usually means a
mis-declared instrument profile — an actionable message, not a peak-picking one.
And a `from_positions` list indexes despite its assumed σ, but every line carries
`sigma_assumed` — the panel must say "precision assumed", never quote σ(Q)/Q as a
property of the data.

**Arrived after this WP closed, with WP-1030's merge on 2026-08-04 — two things
the panel may not honour, because 1030 was on a worktree branch while this one
shipped.** Check both before trusting the panel's FoM display:

- **The figure-of-merit panel is seven members, not five**: `m_rev` and `m_sym`
  (Oishi-Tomiyasu 2013) joined M₂₀, F_N and the three coverage fractions.
  Anything laying the panel out by a fixed count, or assuming the members are
  comparable in scale, needs re-reading — **`m_sym` is a product of two ratios
  and runs four to five orders above the rest** (~2×10⁵ against M₂₀'s ~10²), so
  a shared axis or a bar chart across members will be unreadable. Every member
  carries its own `blind_spot` string, which is what belongs beside a value.
- **A search over the package's *default* short-axis bound is now affordable at
  low symmetry** — monoclinic over d ∈ [2, 20] Å with a declared volume window
  completes in ~32 s where it previously did not finish at all. A panel offering
  "search monoclinic" no longer has to insist on a narrow `min_d_axis` first.
  Still ~30 s, so it wants the streaming/cancellation path, not a blocking call.

**Correction (pruned): `ObservedPeak.origin` does not exist.** The note here
attributing a `"fitted"`/`"manual"`/`"edited"` origin field to WP-1018 was wrong
— no such field is in `schemas/indexing.py` and WP-1018's file never mentions
it. The *need* is real (a hand-placed peak and a fitted one carry different
weight), so **this WP adds the field** (default `"fitted"`, set by the GUI's
add/move verbs) rather than pretending to inherit it.

**The candidate answer (WP-1024).** `best_or_none()` returning `None` is the
*expected* first outcome (on real lab data with no measured shift,
`shift_allowance_assumed` caps everything at `medium`), so the candidate list is
the primary view and the singleton a badge on it. `confidence_caveats` is the
closed `IndexCaveat` vocabulary → chips, coloured red from
`INDEX_REFUTING_CAVEATS` (served, never hand-listed client-side). Per-candidate
diagnostics live on `candidates[i].diagnostics` — rendering only
`result.diagnostics` drops the most actionable messages.
`AmbiguityPartner.discriminating_two_theta` now lies *outside* the measured
range: render "collect to here" beyond the pattern's right edge. Progress and
cancellation are wired (`index_start`/`index_end`, per-engine
`stage_start`/`stage_end` with `engine`/`index`/`n_stages`;
`EVENT_SCHEMA_VERSION` is `"2"`; a **new** EventKind is a bump, a new `data`
field is not).

**Extinction (WP-1025).** The panel after "adopt this cell" is another table:
`determine_extinction_symbol` → ranked `ExtinctionScreen`, one row per class
with `symbol`, *all* its `space_groups`, `delta_bic`, `n_absent`/`n_testable`,
refuting hkl. One space group rendered singly is unmeasurable, not merely
unsupported; `EXTINCTION_GROUPS_NOT_SEPARABLE` is an `info` that must be shown.
Cost: one shared profile fit (~2 s) then ~0.1 s per class (7 classes hexagonal,
71 orthorhombic P).

**Server machinery (WP-1008/1006).** The ten routes are reserved in
`gui.session.RESERVED_ROUTES`; filling one in is a `ROUTES` entry plus a
`GuiSession` method. `GuiSession.run(body)` is the long-running machinery —
add a `kind: "index"` branch; the run record's fields are generic enough, no
new keys. Mutating verbs 409 while busy.

**Text document (WP-1009/1013).** The `peaks` block name is reserved in `rxt 1`
(`textdoc.RESERVED_BLOCKS`) — filling it needs no format bump. Grammar rules: an
annotation containing spaces renders last on its line; column widths are per
block. No `@` markers — peaks are not parameters, and the scanner's green `@` is
a vary token that must not appear here. The `peaks` keyword already highlights;
`test_textdoc.py::test_the_highlighter_quotes_the_parsers_words` pins the word
lists in `gui/src/lib/rxt.ts` to the parser's, so new flag words in the peaks
block are a failing test until restated there — deliberate.

**Frontend facts (WP-1010…1015, 1029).** `Peaks` is a sidebar tab; tabs stay
mounted. Reuse `lib/table.ts` (virtual window, esd formatting, `num()` for
`"Infinity"` strings). `lib/plotly.ts` `loadPlotly()` is the one runtime loader;
**any plot with controls below it needs `ResizeObserver` → `Plotly.Plots.resize`
on the plot div** (plotly's `responsive: true` is window-only; an oversized
canvas swallows clicks and maps a picker's click to the wrong 2θ). The plot takes
a `zoom` prop and refetches `/api/result/window`; clicking to *add* a peak needs
a click handler nothing has registered yet; a click on √-scaled intensities maps
back through `lib/plot.ts`'s `scaleValues` (√ is applied to the data, only tick
labels map back); the shared 2θ axis is anchored to the lower subplot
(`xaxis.anchor: "y2"`), so pixel→2θ off the upper plot's geometry is wrong.
`Plot.draw`-style fetches stay guarded (a checkout clears the result server-side
mid-flight); `test-setup.ts` stubs `Plotly`, `ResizeObserver` (jsdom also lacks
`DragEvent`). `gd.layout` read back is not a reading of the view; compare
screenshots, not hashes. `worstRegions` ranks by χ² share, not local Rwp — a
candidate list should not rank on a normalised quantity alone.
`GET /api/structure3d` draws an adopted cell immediately — a cheap sanity check
no figure of merit provides. A full-window mode (like Model) is an available
shape if the panel outgrows the sidebar; the wizard's structure step is
currently *required*, so an index-from-nothing flow needs a wizard branch that
creates the project with a Le Bail placeholder — recorded here as follow-on,
not this WP's checklist.

## Non-goals

- No new indexing capability — this WP is a surface over WP-1018-1025.
- No structure solution view.
- No new dependency: plotly is already the `[gui]` extra, and the panel adds
  nothing.

## Tasks

- [x] `GuiSession` verbs above, each with its console-pane API echo.
- [x] Fill in the WP-1008 routes; `/api/index` on the run state machine with
      SSE progress and cancel.
- [x] `peaks.json` in the `.rex/` container, keyed by `data_fingerprint`;
      `adopt_candidate` through `Refinement.edit`.
- [x] Frontend: peak layer (markers, σ error bars, fitted group profile,
      residual strip), the four interactions, the diagnostics strip.
- [x] Frontend: candidate table with the FoM columns, engine chips, ambiguity
      sub-rows, and the gated Adopt button.
- [x] `.rxt` `peaks` block: render, parse, apply (2θ and flags only); extend
      the fixed-point property test.
- [x] `tests/test_gui_peaks.py`: verbs round-trip through the live server;
      a peak list keyed to one pattern is refused against another; `.rxt`
      fixed point (in `test_textdoc.py`, beside the other fixed-point
      properties); **Adopt is disabled for a `medium` candidate** (the gate
      does not leak into the UI — asserted server-side there and from the
      JS side in `App.test.ts`).
- [x] Real-browser pass over the pointer layer (Chrome-for-Testing on the
      qarr corundum project): all four gestures verified with sub-pixel
      pixel→2θ mapping; two measured defects fixed (`grabToleranceDeg`,
      the 3×FWHM whisker cap) plus the boot restore of a held answer.
- [x] Extinction screen served: `/api/index/extinction` as a fourth run
      kind + the ranked-classes table in the adopt flow, chips gated by
      the server's adopt arm.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_peaks.py -q
.venv/bin/python -m pytest tests/test_textdoc.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: a peak can be added, dragged, flagged and refitted through the live
server with the console echo matching the API call that would reproduce it; the
`.rxt` round trip is a fixed point; and no UI path adopts a candidate that
`best_or_none()` would not return.

## References

- DESIGN.md §Outputs, 2026-07-29 amendment — the stack decision.
- `viz/compare.py` + `compare_app.py`, `watch.py` — the stdlib-`http.server`
  precedent this follows.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **peak picker and indexing panel** (WP-1027, `src/rietx/gui/peaks.py`,
`panels/Peaks.svelte`, `lib/peaks.ts`, the plot's peak layer) is where the
indexing line meets the GUI line. Peak lists are a **project artifact**
(`peaks.json`, keyed by `data_fingerprint` and refused against the wrong
pattern); every edit refits exactly one group through the picker's own solver,
and the human-owned facts (`origin`, `excluded`) carry across refits. **A cross-group
mark (`duplicate_line`, the ghosts) follows the edit by its judgement's change alone**
(WP-2030); a new cross-group flag joins `_follow_cross_group_marks`. The plot
is an editing surface **only while the Peaks tab is active**, and every pointer
verb has a non-pointer route (typed 2θ, the `.rxt` peaks block — whose only
editable columns are `2theta` and `flags`; everything else is derived and
regenerated). Two pointer rules are measured, not aesthetic: the **move
gesture's grab radius is `grabToleranceDeg` — min(10 px, 1.5× median fitted
FWHM)** — because a pixel radius alone is ±1.9° at the survey view, where a
zoom drag starting 0.9° from a marker silently moved a line 11° (the coarse
10 px stays for shift-toggle and click-to-add, whose precision comes from the
group refit); and a drawn **σ whisker is capped at 3×FWHM**, because a
degenerate component reports σ in tens of degrees (111° measured) and an
uncapped error bar spans the pattern (under plotly it owned the autorange). `/api/index` and
`/api/index/extinction` are run *kinds* on the one machine — a cancelled
search or screen **returns** what it has and its status is read off the token.
Both tables' badges follow the server (`adopt`, `best`); the screen is gated on neither the adopt verdict nor a phase
(a read-only measurement; a pattern-only project is where indexing starts). **Any candidate can be adopted** (Yue's
ruling B, 2026-11-08, WP-2124): the arm's `picked` is the gate's pick, its `why` the sentence an adoption of any other
row writes into the `edit_model` node. The old panel still enables Adopt, and a space-group chip of an unrefuted
class, on `allowed`, which carries `picked` under its old name until the port redraws it.

Its second pass (2026-07-31) added three browser facts; the one about plotly's
screen-relative `lightposition` left with plotly (WP-1462), whose renderer lights
from a fixed direction in view space, so the key follows every rotation by
construction. **A style sampled synchronously inside an effect races the
shell's `applyTheme` effect in the same flush** — `Plot.svelte` and the 3D
panel's `rebuild` each await one microtask before `getComputedStyle`, or the
first dark repaint wears light ink. And **an effect that reads the project
*object* refires on every ui-only PATCH** — Model reloads on a boolean
`$derived` (`hasProject`), or a theme click refetches three routes plus the 3D
geometry with the head unmoved.

## Handover log

- **2026-08-01** — **closed.** The two open items, done. **(1) Browser pass**
  (Chrome-for-Testing, qarr corundum project, screenshots in the job
  scratchpad's `pass1…5/`): all four gestures verified with sub-pixel
  pixel→2θ mapping (move echo 0.0 px off at survey and zoomed ranges); four
  defects found, none visible to jsdom, all fixed with the measurement in the
  commit: a 10 px grab radius is ±1.9° at the survey view and a zoom drag
  starting 0.9° from a line *moved it 11°* → `grabToleranceDeg` =
  min(10 px, 1.5× median fitted FWHM) for the move capture only (coarse
  10 px stays for shift-toggle/add/refit); a degenerate component's σ(2θ) =
  111° error bar owned the autorange (−88°…164°) → drawn whiskers cap at
  3×FWHM, the table keeps the number; boot never asked
  `/api/index/result`, so a reload after a 4-minute search showed an empty
  panel → boot restores the answer and the screen; and three stacked
  `.scroll` tables flex-shrank each other to a 70 px sliver → no shrink +
  45vh cap. One false alarm: the round-1 "missing refit echo" was headless
  playwright auto-dismissing `window.prompt` — register `page.on("dialog")`
  before concluding anything about a prompt-gated verb. **(2) Extinction
  decided for implementation**: `POST`/`GET /api/index/extinction`, a fourth
  run kind on the one machine (cancel-aware; a cancelled screen *returns*,
  unfitted classes stay `screened=False`, `best_or_none` abstains),
  **ungated** — a screen is a read-only measurement and the adopt gate stays
  on adopt — with the served `best` quoted from the screen's own gate, a
  staleness rule (a new index run clears it; candidates renumbered), and the
  panel table whose space-group chips act only when the adopt arm allows and
  the class is unrefuted. Verified live: 8 monoclinic-P classes in 4 s and
  71 orthorhombic-P in a later run, refuting hkl named, zero acting chips on
  a `low` candidate. **Measured**: fast 1577/108 (+2 exactly), full
  1663/117 (+2 exactly, 9:05 loaded), vitest 282 (+6: 4 `grabToleranceDeg`,
  2 extinction mounts), svelte-check 0/0, ruff clean, dist rebuilt.
  **Next**: nothing here — the index-from-nothing wizard branch stays
  recorded as follow-on in Context, and the manual's share is in WP-1017's
  Inherited. **Gotchas**: the extinction answer is session-scoped like the
  index result (boot restores both, in that order — `loadIndexAnswer`
  clears the screen it assumes stale); `_summarize_extinction` reads the
  cancel token because the screen returns partial rather than raising; and
  twice this session a playwright `waitForFunction` with an async predicate
  resolved before the condition held — when a probe disagrees with the app,
  re-probe with `curl` + a DOM read before touching the code.

- **2026-07-31** — the whole checklist landed in one session; 🔄 only for what
  a browser must confirm. **Done** (six commits): the indexing-side seams
  (`fit_group_at`, `group_profile`, `pick_peaks_with_state`, `peaks_of_group`,
  `flag_ghosts(only=)`, and `ObservedPeak.origin` — added *here*, the old
  WP-1018 attribution was stale); `gui/peaks.py` (peaks.json keyed by
  `data_fingerprint` and refused against the wrong pattern; every edit refits
  exactly one group through the picker's own solver and flag translation;
  human-owned facts — `origin`, `excluded` — carry across refits; ghost
  recompute scoped to the spliced components); the ten routes live
  (`RESERVED_ROUTES` now empty) with `/api/index` as a third `kind` on the one
  run machine (`_work` takes a per-kind `summarize`; a cancelled search
  *returns*, so its status reads the token); `index_adopt` re-asks
  `best_or_none()` server-side (`ADOPT_GATED`), lands one `edit_model` node,
  and flips the mode to lebail; the `.rxt` peaks block (2theta/flags editable,
  count/esd/fwhm/I refused as derived, omitted row = no opinion, flags
  vocabulary quoted from `PeakFlag` and pinned into `rxt.ts` as the parity
  test's fifth list); the frontend (Peaks tab, plot peak layer with σ error
  bars / hollow-unusable / diamond-manual markers, group profiles and
  per-group residual strips, raw-pattern drawing when no result exists, the
  four pointer gestures gated on the tab being active, candidate table with
  served-constant chip colouring and the server-driven Adopt).
  **Measured**: fast suite 1575 passed / 108 skipped (numpy-only `[dev]`
  worktree venv; +8 = 6 `test_gui_peaks` + 2 textdoc peaks tests over the
  1567/108 baseline); vitest 276 (was 261); svelte-check 0/0; ruff clean;
  dist rebuilt (app.js 192 kB, under vendor-cm's 328 kB split).
  **Next**: (1) drive the four pointer gestures in a real Chrome
  (playwright-core is cached per the memory note; jsdom cannot see the
  pixel→2θ mapping, the capture-phase marker drag, or an oversized canvas —
  the exact class every previous plot feature shipped a bug in) on a dataset
  that indexes end-to-end (qarr corundum), screenshots compared not hashed;
  (2) decide the extinction-screen table (WP-1025 context in this file):
  `adopt` takes `space_group=` but nothing serves
  `determine_extinction_symbol` yet — a `/api/index/extinction` route + a
  table in the adopt flow, or an explicit deferral note here; (3) the
  index-from-nothing wizard branch stays recorded as follow-on in Context.
  **Gotchas**: the session caches one `PeakEditor` keyed on
  (instrument dump, limits, exclusions) — the first peaks GET after a reopen
  pays one `detect_peaks`; a move beyond its group's window is remove+add and
  `excluded` does not survive the crossing (documented on the verb); textdoc
  peak applies re-locate each peak *by position* between edits because a
  refit re-sorts the list; `GET /api/peaks` is deliberately not idle-gated
  but every mutating peak verb is; on the clean synthetic pattern
  `refit_group(n_components=N)` can refuse with "the residual proposes no
  position" — that is designed, not a bug.

- **2026-07-29** — created from the indexing plan.
