# WP-2235 — predict on a grid says which peak cut it draws

Milestone: unscheduled · Status: ✅ 2026-11-22 — ruling A: after a fit `predict(grid)` compiles at the fit's peak cut, so it returns `y_calc` bit for bit; PR #PRNUM
Track: A long run is not one fit
Depends on: —

## Goal

`Refinement.predict`'s docstring and the manual's § Evaluating the model say what
`predict()` and `predict(grid)` return after a default fit, with a measured number. A test pins
that relation, so the next change to the default peak cut cannot leave the text behind.

## Context

Issue #1652 item 2 (mustachefeeling, 2026-11-17). Item 1 landed in PR #1755.

**What the two forms do.** `predict()` evaluates the last result's answer on that result's
model, so it returns `RefinementResult.y_calc`. `predict(grid)` compiles a fresh model on the
grid at `compile_model`'s default windows, which leave out 1e-3 of each peak's area
(`CLOSING_WINDOW_TOL`). Since WP-2222 turned the closing stage off, a default fit measures its
answer at the declared stages' 2 % windows (`forward.WINDOW_AREA_TOL`). So the two forms differ
by the peak tails.

**Measured at `c1033a0e8`** on the fluorapatite tutorial (`FAP.XRA`, limits 15-130°, `[dev]`,
darwin arm64), under `mccusker_structural` (11 stages) and `mccusker_default` (5):
- `predict()` equals `result.y_calc` bit for bit.
- `predict(result.two_theta)` differs from it on 5751 of 5751 channels. The largest
  difference is 1.5-1.6e-3 of the strongest peak, and the median is 9e-5.
- The docstring's recipe, `compile_model(..., window_area_tol=recorded_window_tol(result.stages[-1].window_area_tol))`,
  reproduces `predict()` exactly (0 of 5751 channels differ). The window cut is the whole
  cause.

The probe is the tutorial's own fit, then `ref.predict()`, `ref.predict(result.two_theta)` and
that recipe, compared channel by channel.

**Two texts are stale.** `docs/docs/reference/exports.md` § Evaluating the model says the forms
differ on "36 of 4200 channels, by at most 8×10⁻⁶ of the peak height", and gives a cause about
windows sized at a stage's start values. `Refinement.predict`'s bold paragraph in `refine.py`
says "After a default fit the two forms agree bit for bit". The docstring's last paragraph, on
the 2 % windows and the recipe, is right.

**The question before the rewrite.** WP-2226 (closed 2026-11-21, PR #1751) moved the GUI preview
to the last fit's peak cut, on Yue's ruling A: a preview must show the fit's own curve before any
move. `predict(grid)` could follow it. Today's docstring says the grid form is deliberately
independent of what the object has fitted, so a never-fitted twin carrying the same models
returns the same array. Following ruling A gives that property up. Either answer changes what
`predict` returns or says, so it is a reader-output change and comes to Yue before merge, with
the numbers above and what TOPAS, GSAS-II and FullProf draw on a user-supplied grid
(`docs/practice.md` § How far a peak is computed).

**Tier.** At most one default: the peak cut a grid compiles at. Named practice either way.

**Siblings.** WP-1949's Context quotes the stale 36-of-4200 figure and its Acceptance compares
against `predict` at 8e-6; its § Inherited carries a note. PR #1640 (WP-1947, open on
2026-11-21) adds a section to `exports.md` directly after this paragraph, so rebase on it if it
merges first.

### Inherited

## Rulings

**Ruled by Yue, 2026-11-22: option A.** He was brought the numbers in § Context and
`docs/practice.md` § How far a peak is computed. Once a `Refinement` has fitted,
`predict(grid)` compiles at the last fit's recorded peak cut, as WP-2226's GUI preview does
since its own ruling A. So `predict(result.two_theta)` equals `result.y_calc`. A `Refinement`
that has never fitted keeps today's default, `CLOSING_WINDOW_TOL` (1e-3 of each peak's area).

- **Alternatives.** B kept the 1e-3 default for every grid and fixed only the two texts, so
  a grid would keep differing from the fit's curve by the tails. C compiled every grid at
  2 %, which also coarsens the synthetic patterns a never-fitted object draws.
- **Practice.** Every program in the survey has one peak cut, used for fitting and for the
  pattern it draws (TOPAS's `ymin_on_ymax`, GSAS-II's 50/75 FWHM, FullProf's `Wdt`). None
  documents a second cut for evaluating a fitted model on a new grid (recall plus the
  survey's table, not checked further). Option A makes rietx draw a fit's curve at the cut it
  fitted with, which is what each of them does.
- **What it gives up.** The grid form now depends on whether the object has fitted. A twin
  carrying the fitted models but no fit returns the 1e-3 array.
- **Implementation choice, settled by Claude under the ruling's "as the GUI preview
  does".** One method, `Refinement._peak_cut`, now answers for both `predict` and the GUI
  preview. With a history it reads the nearest stage node at or above the head, the
  preview's rule, so an edit, a checkout and a reopened project keep the fit's cut.
  Without a history it reads the last answer's compile, kept through an edit and never
  carried into a package trial. Both readings carry the window slack as well as the area
  fraction. The alternative was reading the answer's compile alone (`Refinement._model`),
  which the first commit did: the review found any edit clears it, so after a no-op
  `set_values` the grid fell back to 1e-3 and differed on 2076 of 4200 channels of the
  synthetic LaB₆ fit, and the GUI and `predict` read two authorities.

## Non-goals

- The GUI preview's cut: WP-2226 settled it.
- Turning the closing stage back on by default: WP-2222 ruled it off.

## Tasks

- [x] Bring the question above to Yue with the numbers and the practice survey.
      (Ruled 2026-11-22: option A, § Rulings.)
- [x] Implement the answer: either `predict(grid)` compiles at the last fit's recorded cut
      when one exists, or it stays at the default and says so.
- [x] Rewrite the docstring's bold paragraph and the manual's paragraph to the measured
      relation, with the number.
- [x] A test on a small synthetic fit pinning the relation between the two forms as shipped.
- [x] Skill: none, unless the answer changes what an agent passes to redraw a fit's curve.
      (None: the skill never taught the recipe, and `predict(result.two_theta)` now needs
      none.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_refine_synthetic.py tests/test_manual_api.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- WP-2222 (the closing stage off by default), WP-2226 (the preview on the declared windows).

## Handover log

- **2026-11-22** — closed (ghostshift runner, PR #PRNUM). After a fit, `predict` on a
  pattern's own grid now draws exactly the fitted curve, so a person or an agent redrawing
  a fit no longer needs the `compile_model` recipe. A `Refinement` that has never fitted
  still draws the near-complete tails a synthetic pattern wants. The price is the one Yue
  accepted under ruling A: the grid form now depends on whether the object has fitted.
  - *Done.* `Refinement.predict(grid)` compiles at the cut and slack of the fit that
    produced the working state, read by one method the GUI preview now shares
    (§ Rulings). The docstring's bold paragraph and last
    paragraph, the manual's § Evaluating the model in `exports.md`, the same claim in
    `refinement.md` § the closing stage and the `WINDOW_AREA_TOL` comment in `forward.py`
    now say so, with the number. `tests/test_refine_synthetic.py` replaces the old
    "twin equals fitted" test with one pinning the new relation: Rietveld with and
    without a history, Le Bail without, and a no-op `set_values` keeping the cut.
  - *Review* (`/code-review high --fix`, 7 findings). Fixed: the orbit-split exception
    stated in the docstring and manual (its own edit); an edit or checkout cleared the
    cut, and the GUI and `predict` read two authorities (fixed by `_peak_cut`, measured
    2076 of 4200 channels before). Declined: the moment frames under a moved angle (not
    measured, and magnetic work is Mike's); the suggest probe's `_plan_settings` cut drops
    the slack (predates this WP, a stage declaring a slack only); a comment that would go
    stale only under a fix not taken; the compiled-path rule for bit-identity tests (both
    sides of each comparison run on one path in one process).
  - *Sibling fixed.* `report/distortion.py`'s detectability probe compared a fitted
    object's `predict` with a never-fitted trial's. Under the new rule the two compile at
    different cuts and every λ would gain the tails, so the baseline now comes from the
    trial too. That keeps its numbers where they were (both sides at the default cut, as
    before). One test made the same comparison: `test_displacive_statement.py`'s BT-1
    restatement check failed at its 1e-10 bar (13.2 counts against 6975) and now builds
    both curves from unfitted objects.
  - *Not generalised, deliberately.* The result's own compile also keeps the solve's orbit
    split (WP-2052) and its moment frames (#598). A grid takes the cut only, so a site
    reported as `SITE_MULTIPLICITY_KEPT` is counted afresh and differs from `y_calc` there;
    the docstring and the manual say so. Passing the orbit split would break on a
    structure edited after the fit. The moment frames should agree to roundoff, since the
    written-back components are the solve's (not measured).
  - *Measured* (FAP tutorial, limits 15-130°, `history=False`, `[dev]`, darwin arm64,
    probe in the runner's scratch). Before: `predict(result.two_theta)` differed from
    `y_calc` on 5751 of 5751 channels, by at most 1.41e-3 (`mccusker_default`) and
    1.39e-3 (`mccusker_structural`) of the strongest peak, median 9.3e-5 and 9.2e-5.
    After: 0 of 5751 under both. A never-fitted twin is unchanged: it equals the
    default-cut compile on every channel. `predict()` equalled `y_calc` before and after.
    The new test fails both cases when the cut line is reverted (checked once).
    TESTCOUNTS
  - *Siblings in other WPs.* WP-1949's § Inherited note carries a dated "superseded in
    part" paragraph. PR #1640 (WP-1947) was still open, so no rebase was needed.
  - *Reader output.* `python -m tests.reader_output` exit 0, unchanged against
    `ca0b72210`: the change moves an array `predict` returns, not printed text.
  - Next: none. The WP closes with this PR, and with it item 2 of issue #1652.

- **2026-11-21** — created, from the 2026-11-21 issue triage (issue #1652, item 2). Checked
  against the tree at `c1033a0e8`: measured as in § Context. No open WP owns it: WP-2226
  closed with PR #1751 on the preview alone, WP-1947 closes with PR #1640, and WP-1949 is about
  an evaluation event's payload. Next: the first task.
