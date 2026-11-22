# WP-2235 — predict on a grid says which peak cut it draws

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P3 2026-11-21 — the manual and a docstring state a difference between `predict`'s two forms that is 200× too small; no fit moves, and the docstring's own recipe is the workaround

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

## Non-goals

- The GUI preview's cut: WP-2226 settled it.
- Turning the closing stage back on by default: WP-2222 ruled it off.

## Tasks

- [ ] Bring the question above to Yue with the numbers and the practice survey.
- [ ] Implement the answer: either `predict(grid)` compiles at the last fit's recorded cut
      when one exists, or it stays at the default and says so.
- [ ] Rewrite the docstring's bold paragraph and the manual's paragraph to the measured
      relation, with the number.
- [ ] A test on a small synthetic fit pinning the relation between the two forms as shipped.
- [ ] Skill: none, unless the answer changes what an agent passes to redraw a fit's curve.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_refine_synthetic.py tests/test_manual_api.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- WP-2222 (the closing stage off by default), WP-2226 (the preview on the declared windows).

## Handover log

- **2026-11-21** — created, from the 2026-11-21 issue triage (issue #1652, item 2). Checked
  against the tree at `c1033a0e8`: measured as in § Context. No open WP owns it: WP-2226
  closed with PR #1751 on the preview alone, WP-1947 closes with PR #1640, and WP-1949 is about
  an evaluation event's payload. Next: the first task.
