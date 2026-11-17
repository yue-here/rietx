# WP-2129 — the Background tab

Milestone: gui-overhaul · Status: ✅ 2026-11-10 — the Background tab and its covariance band merged in #1488
Depends on: 2123, 2125 (the shell it draws in, and the preview route whose compile cache it reuses)

## Goal

The graph column gains a Background tab. It draws the observed pattern greyed, the background
curve at the working state's values, and a shaded band showing where that curve may move when the
free parameters refine. The band comes from rietx's own covariance, served by a new route. A
Chebyshev background offers a hold on each term, through the existing hold verb, and a P-spline
background shows its smoothness λ and lets the person edit it.

## Context

### The designs, and the rulings they rest on

The maintainer reviewed the background preview on screen in the design rounds of 2026-11-06 to
2026-11-08. The prototypes are not published, so each design this WP builds is restated here with
its ruling.

1. **The background is one group with an interactive preview.** Ruled 2026-11-06 (first Parameters
   review): "Individual background coefficients are meaningless to switch. Background is one group
   with an interactive preview: greyed data, the curve, and a shaded band for how it might move
   with the active parameters refining." So the Parameters panel offers no switch per coefficient;
   the background is one group there, and the per-term control lives in this tab.
2. **The band shows where the curve may change, and may be exaggerated.** Ruled 2026-11-07 (second
   Parameters review): "Background bands show where the curve may change when terms are held, and
   may be exaggerated." The prototype drew the band at ±3 esd and offered "Band drawn" at ×1, ×5
   and ×20. The GUI rulebook's caption rule applies (an exaggeration is not a probability), so the
   level and the multiplier are stated separately.
3. **The background preview is a graph tab.** Ruled 2026-11-07 (third review): it "should probably
   be a tab in the main panel, along with peaks." The fourth review put the graphs on the left in
   tabs, each with a title line saying what it shows (WP-2123, designs 1 and 2).
4. **A held Chebyshev term keeps its value from the previous cycle.** Ruled 2026-11-07 (third
   review): "the idea was that a held term keeps its value from the previous cycle (not from the
   click)." rietx's `Refinement.hold` (WP-1435) does exactly this. It leaves the stored value where
   the last cycle put it and blocks every later free, a plan's included. It records a `set_hold`
   node, so a hold is undone with History's checkout or with `unhold`.
5. **The points background is deferred.** Ruled 2026-11-07 (third review): it "needs more UI work,
   deferred until the GUI goes into the main repo". rietx has no such background type, and a new one
   is a stored-format change the milestone record lists as waiting on the maintainer. Not here.
6. **No click moves the layout unless it asks to** (interaction rule 8, adopted 2026-11-08). Holding
   a term and editing λ ask for no layout change, so the layout browser test covers this tab.
7. **No permanent explanatory text** (sixth review, 2026-11-07). What the band means lives in a
   tooltip, never in a line under the plot.

### What the band is

The prototype computed its band in JavaScript from matrices exported by a script: the background
basis, the structural Jacobian columns at the converged fit, and their normal matrix. It solved the
free background terms and the free structural parameters together, then drew ±3 esd of the curve
from the background block of the inverse. Here the server computes the same quantity in rietx, so
there is one copy of the statistics.

The band is the esd of a derived quantity, the background curve y_b(2θ) at each fitted channel,
taken through the whole covariance. That is the manual's estimation chapter, `est-derived` over
`est-cov`:

- J is the full weighted Jacobian at the working state's values, from the solver's own
  `_make_jacobian`, with every residual row the solver sees, P-spline penalty rows included. The
  free set is the working one: the ticked rows, less held rows and less what the intensity mode
  force-fixes. So a held term has no column and carries no variance.
- Cov = χ²_red · (JᵀJ)⁻¹ through `statistics.normal_factors`, the equilibrated guarded solve every
  esd in the package uses, with χ²_red over the data rows.
- g_k(2θ) = ∂y_b(2θ)/∂θ_k, by central difference of `CompiledModel.background` through the table's
  decode. The background is linear in its coefficients, so the difference is exact there. A column
  that does not reach the background has g = 0 and drops out.
- σ_b(2θ) = f · √(gᵀ Cov g), with f the Bérar-Lelann factor on the same residual, so the band
  carries the inflation every reported esd carries.

Because Cov is the inverse of the whole normal matrix, the band is marginal over every other free
parameter. A free scale or Biso that trades against the background widens it. That is the
prototype's "given what else is free", and it is what makes the band useful: it shows where the
data cannot tell the background from the structure.

Two readings a person needs, written into the tab's tooltip. The band is linearised at the current
values. Before a fit has converged it describes the curvature there, and nothing more. And it is
drawn at 3 esd times the chosen multiplier, so a band drawn at ×20 is a picture of the shape, not
of a probability.

The chapter's absent-rather-than-zero rule holds. With no free column reaching the background
there is nothing for the band to describe, and the route sends none. A free column the data does
not constrain (`normal_factors`' 1/d = 0) that reaches the background makes the band unmeasured,
and the route sends none, saying why.

### What exists, and what is missing

- `POST /api/preview` (WP-2125) caches a compile per working state in `gui/preview.py`, keyed on
  the history head, the mode, the limits and the excluded regions. The band reuses it.
- `Refinement.hold` and `unhold` exist; the GUI has no route to them on `main`. PR #1484 (WP-2126,
  open) adds a `hold` arm to `PATCH /api/params`. This WP adds the same arm, with the same contract
  (glob → `true` holds, `false` releases; releases before the vary flags, holds after), so the two
  merge to one.
- `PATCH /api/instrument` replaces the instrument model, which is how λ is edited. λ changes the
  penalty rows, so the band moves with it at the next fetch.
- The Model panel already sets the Chebyshev term count and the background family. Neither moves
  here.

### Tier

The band reads the fit and decides nothing, so it is no heuristic in the sense of
`docs/milestones/generality.md` § The rule. Its 3 esd and multipliers are drawing choices in the
client.

### Calls settled by Claude

No ruling covered these, so each took the smallest neutral option. Each is marked "settled by
Claude, reversible", with its alternative, and waits for the maintainer's review of the PR.

1. Settled by Claude, reversible: the band uses the working free set, the set "One cycle" refines.
   Alternative: the set the staged plan's stages would free.
2. Settled by Claude, reversible: the curve drawn is the background at the working state's values.
   The prototype's one-step prediction of the next cycle's curve is not drawn, since at a converged
   fit it is the same curve. Alternative: draw the linearised next-cycle curve too.

The visual calls below are the maintainer's to review, since visual design questions go to him.
Each took the smallest neutral option.

3. Settled by Claude, reversible: the curve and the band take `--plot-bkg`, the pattern graph's
   background colour, and the greyed data takes `--plot-obs` at 45 % opacity. The band is
   `--plot-bkg` at 28 %. Alternative: a token of the tab's own, such as the figures' warm
   background brown.
4. Settled by Claude, reversible: the band is drawn at ±3 esd, with ×1, ×5 and ×20 as a segmented
   control labelled "Band ±3 esd". These are the prototype's numbers. Alternative: a continuous
   multiplier.
5. Settled by Claude, reversible: the holds are a row of checkboxes labelled `c0`, `c1`, …, under
   the plot beside the band control. Alternative: a hold mark drawn on the plot per term.
6. Settled by Claude, reversible: λ is a text field committed on Enter or on leaving it.
   Alternative: a logarithmic slider over 1e-2 to 1e6.
7. Settled by Claude, reversible: the y frame is the prototype's, 0.7× the curve's lowest point to
   1.15× its highest, so the peaks run off the top. A flat zero curve gets ±1. Alternative: frame on
   the curve ± the drawn band, which would keep a ×20 band inside the view.
8. Settled by Claude, reversible: the title line reads "Background at the current values", or
   "Background, refining" during a run. The curve is at the working values, which an edit or a
   checkout moves without a fit, so "at the last fit" would be untrue after either. The fit's Rwp
   stays on the line. Alternative: "at the last fit" and "at the starting values", keyed on
   whether the working values are a fit's answer, which the client cannot tell today.
9. Settled by Claude, reversible: the view has no zoom, as the non-goals say. Alternative: the
   pattern chart's zoom.

## Non-goals

- The points background (design 5).
- The background family and the Chebyshev term count, which stay in the Model panel.
- A zoom on this view.
- Any change to `panels/Params.svelte` (PR #1484 owns it).

## Tasks

- [x] `src/rietx/gui/background.py`: the band, cached per working state; `GuiSession.background`
  and `GET /api/background`; the `hold` arm on `PATCH /api/params`
- [x] Tests: the band against an independent normal-equations computation, held and unheld, a
  free scale widening it, absent with no free background term, the hold arm, the 409, nothing
  written by the GET
- [x] Client: `lib/background.ts` (pure drawing helpers), `panels/Background.svelte`, the graph tab
  and its title line, per-term holds and the λ field; vitest
- [x] Layout browser test over the Background tab, with real clicks
- [x] Manual: the route and the tab in the GUI chapters, the band tied to the estimation
  chapter's derived-esd equation; screenshots where changed
- [x] Skill: none; the agent skill drives the python API, and the band is a GUI view

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_background.py tests/test_gui_layout_browser.py tests/test_gui_manual.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- Bérar & Lelann (1991), *J. Appl. Cryst.* **24**, 1-5: the esd inflation the band carries.
- McCusker et al. (1999), *J. Appl. Cryst.* **32**, 36-50: the whole covariance in a derived esd.
- Eilers & Marx (1996), *Stat. Sci.* **11**, 89-121: the P-spline penalty whose rows enter J.

## Handover log

- **2026-11-10, close** — closed. PR #1488 merged on 2026-11-10, with the fix for the substring
  tab selectors that #1487 had broken. The fifth and last of the milestone's five pieces is on
  `main`: the Background tab draws the background curve with rietx's own esd band, holds a
  Chebyshev term and edits a P-spline's λ. No task is open and no follow-up was named.

  *Leftovers, and where each went.* The background drawn through points a person places (design
  5) was already the second of the three decisions in `docs/milestones/gui-overhaul.md`
  § Designed, not yet filed, since it needs a new background type. The tab's colours (settled
  call 3) follow the palette piece's row, which re-measures the plot palette. The nine settled
  calls were reviewed with the PR at its merge. The narrative went to
  `docs/milestones/v1.12.md`.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here.

- **2026-11-10** — Merged main (#1479, #1484, #1483, #1490, #1498 and others) into this branch.
  The two `hold` arms on `PATCH /api/params` are now one: WP-2126's. Its
  `_apply_param_arms` survives as the one authority, with `session.rehearse` running every arm
  on `Refinement._trial(record=False)` first, so a PATCH is all or nothing. It already had this
  WP's contract (a glob maps to `true` to hold and `false` to release; releases run before the
  vary flags and holds after them) and the same `_holding` helper. This branch's inline arm
  inside `params_patch` and its second copy of `_holding` were deleted. The Background tab sends
  a hold-only body, which the surviving arm serves unchanged. One test moved:
  `test_gui_background.py`'s malformed-body refusal now matches main's combined sentence
  ("'vary' and 'hold' map dot-path glob → bool"). The dist and every screenshot were rebuilt
  on the merged tree.
  A second merge brought in WP-2128's `Single peaks` graph tab. The strip now reads `Pattern`,
  `Single peaks`, `Background`: the tab main shipped second keeps its place, and the manual's
  "second graph tab" sentence stays true. On the Background tab the title stays "Background at
  the current values" while the Interactive tab holds a preview, because this curve is drawn
  at the working values and not at the preview's. Both settled by Claude, reversible.
  Since #1487, `test_gui_peaks_browser.py` clicked the `Single peaks` graph tab: it took the
  first tab whose label contained "Peaks". It now selects the tab by its exact name, as do the
  two other substring tab selectors in `test_gui_layout_browser.py` (Background, Plan).

- **2026-11-09** — The GUI now has a Background graph tab. It shows the background curve over
  the greyed pattern, with a shaded band for where the curve may move when the free parameters
  refine. The band is rietx's own esd of the curve through the whole covariance, so a free scale
  or Biso that trades against the background widens it. A Chebyshev term can be held from the
  tab, through the existing hold verb, and a P-spline's smoothness λ can be edited there. The
  band is small on a converged fit (FAP: median ±3.9 counts at ±3 esd against a background of
  52-575), which is why ×5 and ×20 exist. Nine calls nothing settled are listed above for the
  maintainer, seven of them visual.

  *Done.* `GET /api/background` (`src/rietx/gui/background.py`, cached per working state on
  `gui.preview`'s key) and a `hold` arm on `PATCH /api/params` with PR #1484's contract. The
  client is `lib/background.ts` and `panels/Background.svelte`, a second entry in `GRAPH_TABS`,
  with each graph kept mounted. The manual gains `gui-guide` § The background, tied to
  `est-derived`, and a `background-tab` screenshot pair; `first-fit` and `plot-readout` were
  re-taken for the strip's second tab.

  *Measured.* The band against an independent plain-inverse computation: 5.7e-10 relative on
  FAP, 8.2e-9 on NAC; the test holds 1e-7. First call 172-210 ms, a cached one under 0.01 ms.
  Fast suite on the final tree, `[dev]` + playwright, darwin/arm64, alone (serial.py): 14513
  passed, 410 skipped, 32 xfailed, exit 0. That tree carries #1476's and #1479's tests too, so
  its counts are not main's plus this WP's. This WP added 10 python tests (9 in
  `test_gui_background.py`, 1 in `test_gui_layout_browser.py`) and 13 vitest cases (626 passed).
  Added-test times from the local junit: the band test 7.06 s, which is the module fixture's FAP
  fit shared by four tests; the browser test 1.89 s; the rest under 0.4 s. None marked slow: the
  fit is the subject and runs once a module. ruff clean; `tests.reader_output` exit 0
  (unchanged against the merge-base).

  *Review.* `/code-review high --fix` found eight; all eight were taken. Six as it proposed: the
  band counts a column only when it moves a path the curve reads (a peak component had drawn a
  zero band as measured), a refetch on mode, fit range and excluded regions, a refused hold puts
  its box back, λ commits once, a load error and a refusal are two fields, and the last channel
  draws. Two it left for the maintainer were rules, not visual calls, so they landed too: a held
  term's `held_because` is a `<Help>` term per `gui/CLAUDE.md`, and the title now reads "at the
  current values", since the curve's values move without a fit (settled call 8).

  *Generality.* No judge dispatched: `_audit.py` is untouched, and the band decides nothing. Its
  3 esd and multipliers are drawing choices in the client.

  *Gotchas.* `docs/docs/theory/estimation.md`'s built twin sits within 300 characters of the
  50 000 cap, so the band's sentence lives in the GUI guide with a link. The band on a synthetic
  project whose stage freed only the scale is absent, correctly; the browser test frees the
  terms first.

  Next: the maintainer reviews the nine settled calls on the PR, the colour and the title first.
  The PR merges after #1476 and #1479. If #1484 merges first, its `hold` arm and this one
  conflict in `session.py` and resolve to one.

- **2026-11-09** — filed by a ghostshift runner as piece 5 of the gui-overhaul milestone, which
  listed it as not yet filed. The number is 2129, the next free one after the shift's 2126-2128;
  the milestone record claims 22xx for these pieces, and 2125 already set the precedent. The branch
  stacks on WP-2123 (PR #1476) and WP-2125 (PR #1479), neither merged yet.
