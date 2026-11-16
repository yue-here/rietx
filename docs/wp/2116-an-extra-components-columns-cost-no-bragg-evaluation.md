# WP-2116 — an extra component's columns cost no Bragg evaluation

Milestone: unscheduled · Status: ✅ 2026-11-12 — tasks 2-5 done (PR #1546): a hump's columns are a closed form and a declared peak's difference the peak alone; task 3 declined with its measurement
Track: A long run is not one fit
Depends on: —

## Goal

A background hump's position, height and FWHM columns are computed from the component alone, so a
Jacobian no longer pays full-model evaluations at the closing windows to differentiate a term that does
not depend on them.

## Context

**Source.** Issue #1418, Michael's measurements of 2026-11-05 on acridine form IX (WP-1806 part 1, PR #1416
at `4935f767e`, 6 601 points, 23 atoms in one rigid body). All numbers below are the issue's, on darwin
arm64, `[dev,jax]`, and were not re-run in this triage. The issue says Michael's side takes the work, so
check who holds it before starting.

**What was measured.** One closing-stage evaluation costs 8.0× one in the stage before it, reproducibly, and
nothing is one-off. The windows give about 5× and the FCJ node rule about 2×, and they multiply. Both are
tied to the tenth-of-sigma bar and the eighth round's ruling (`docs/wp/2002-batch/rulings.md`), so they are
out of scope here. On this cell the 1e-3 windows already cover 63 % of the pattern at the median.

**The third cost, which the bar does not involve.** The fallback at `optimize/least_squares.py:2131`
evaluates the whole model once for `r0` and once per column in `fd_cols`. A hump has three parameters with
no analytic branch, so each Jacobian makes four full evaluations, and each re-evaluates every Bragg window.
They took 49 % of the closing Jacobian (0.352 s of 0.715 s) and 35 % of `biso`'s. With the hump held (38 free
parameters against 41), the closing Jacobian drops from 0.673 to 0.345 s, about 4.6 s of the closing stage's
12.0 s. Across the whole fit, FD evaluations total 6.6 s of 30 s (22 %). The comment above that loop says
three residual evaluations per hump are why analytic columns "are not worth writing". That was true before
the closing windows.

**A smaller exact saving in the same loop.** `r0` repeats the residual the solver has just computed at the
same θ, which is 12 % of the closing Jacobian here.

**Why it needs care.**
- The comment names what makes this path safe: a background-peak parameter is outside every analytic branch,
  and `scalar_chain_supported` says so. `_column_extras` sends a tied column to the whole-model FD column, so
  a hump parameter tied to anything outside the component must keep that route (root CLAUDE.md, "An analytic
  Jacobian branch claims what one parameter name reaches").
- A component-only difference and a whole-model difference agree only to rounding, so the columns are not
  bit-identical, and a converged fit that frees a hump can move in its last digits. Say which goldens moved.
- A cached `r0` is safe only if it is the same spelling of the residual: two functions build Ω, 1-2 ulp apart
  on purpose (root CLAUDE.md, Conventions).
- `Instrument.extra_components` has two members, and a third audits every reader of the list first. An
  evaluator here must take any member, so read that convention before writing it.

**A plan finding from the same issue, recorded and not acted on.** The hexagon-body fit's 733 evaluations in
`profile_cell` are not a property of the stage: two of eight noise draws ran long (733 and 1 080), and with the
pose fitted first `profile_cell` took 14-15 on all eight and reached the same final cost. Whether a body plan
frees the pose first is a heuristic, and the issue proposes no change. It belongs to whichever WP writes a
body's default plan.

**Tier.** This changes no default and no threshold: tier 1, arithmetic.

## Non-goals

- `CLOSING_WINDOW_TOL` and the closing node rule (`test_the_closing_node_rule_meets_the_bar`).
- Analytic columns for other FD paths.

## Tasks

- [x] Cost it on the other four fixtures (LaB6, FAP, cpd-1a, NAC), which the issue has not done. Stop if no fit but a hump-bearing one gains.
  Done 2026-11-06: none of the four declares an extra component, so only acridine gains and the WP stops here.

  | fit | declares `extra_components` | columns in `fd_cols` | hump FD / `r0`, share of the closing Jacobian | hump FD + `r0`, share of the fit |
  |---|---|---|---|---|
  | LaB6 | no | none, in any of 8 stages | 0 / 0 | 0 |
  | FAP | no | none, in any of 7 stages | 0 / 0 | 0 |
  | cpd-1a | no | `axial_sl` in 1 of 23 `lines_axial` Jacobians | 0 / 0 | 0 (that call 0.1 %, not a component column) |
  | NAC | no | none, in any of 7 stages | 0 / 0 | 0 |
  | acridine IX | `HumpComponent` | its 3 parameters, in every Jacobian of all 5 stages | 37 % / 12 % | 24 % (hump 18 %, `r0` 6 %) |

- [x] Compute the hump's three columns from the component, keeping the whole-model route for any tie reaching outside it.
  Done 2026-11-12: `background.models.hump_partials` is the closed form, and `least_squares._component_columns` gates it on the column's whole reach. A tie between two humps or a named variable driving one keeps the closed form, through the local Jacobian's coefficients. A tie reaching any other path keeps the whole-model FD. The sibling member, a declared sharp peak, now differences `extra_peak_curve` alone, at the same step.
- [x] Reuse `r0` where the spelling allows it, or record why not.
  Recorded why not, 2026-11-12. The spelling would allow it: `rows._data_rows` builds the data rows as the fallback does, from the same Le Bail snapshot. But `r0` is computed only when some column still takes the whole-model FD, and after task 2 a hump fit has none. Measured on acridine IX, the fallback ran in 0 of 84 Jacobians (336 Bragg evaluations before). On the other four fixtures it ran once in total (cpd-1a's `axial_sl`, task 1's table). A cache would share mutable state between the residual and Jacobian closures to save one evaluation in that one call. Settled by Claude under the smallest-change rule; reopen if a common fit is measured paying `r0`.
- [x] A cross-backend row, and a test that the component columns match the whole-model FD column to the bar the step allows.
  Done 2026-11-12: the `extra_components_tied` row in `tests/test_cross_backend.py` (two tied humps, a variable, a hump driving the zero shift), and five tests in `tests/test_extra_components.py`. The closed form meets a complex-step derivative to 1e-14 of each column's scale, and the whole-model FD at 0.50 of a bar measured from the step.
- [x] Rewrite the "not worth writing" comment with the measurement.
  Done 2026-11-12: the fallback loop's comment in `_make_jacobian` now names what still takes it and quotes issue #1418's 49 % and 24 %. The `scalar_chain_supported` comment in `model/forward.py` names the component branch instead of the whole-model FD.
- [x] Skill: none, since no surface changes. Confirmed 2026-11-12: no name, output or field changed, and `tests.reader_output` exits 0.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_extra_components.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #1418; WP-1102, WP-1103 (the extra components), WP-2002 (the closing stage), WP-1806.

## Handover log

- **2026-11-12** — tasks 2-5 done, and the WP closes (✅). A fit that frees a background hump no longer re-evaluates every Bragg peak to differentiate it. The hump's three columns are now an exact closed form, so they are both cheaper and more accurate than the forward difference they replace. On acridine form IX the Jacobians took 12.8-13.7 s against 20.8-31.6 s before, the same 84 Jacobians and iterations, and the answer moved by at most 3.1e-6 of an esd. A declared sharp peak's columns stopped paying Bragg evaluations too. The review found an older defect in the same loop and it is fixed: a background coefficient tied to anything outside the linear block came back with its smoothness-penalty rows at zero.
  *Done.* `background.models.hump_partials` is the closed form, beside `hump_curve`. `least_squares._component_columns` gates it on the column's whole reach, read from the compiled model (`component_paths`, `peak_components`). A tie between humps, a named variable or an expression keeps the closed form, with the coefficient read off C, or off the local Jacobian when a derived row exists. Any tie reaching another path keeps the whole-model FD. A declared peak's columns difference `extra_peak_curve` alone at the same `fd_step`. The fallback now writes the penalty rows of every background coefficient in a column's reach (`bkg_part`), exactly from the penalty matrix. Task 3 was declined with its measurement (the task line). Comments rewritten in `_make_jacobian`, `scalar_chain_supported`, `fd_step` and `hump_curve`.
  *Tests.* `tests/test_extra_components.py`: seven new cases (complex-step oracle at 1e-14 of each column's scale; the column equals the closed form to the bit with zero Bragg evaluations; the whole-model FD within a bar measured from the step, at 0.50 of it for position and width and 0.17 for height; the gate keeps a hump tied to the zero shift on the FD; a peak's columns equal the whole-model FD to the cancellation floor with zero Bragg evaluations; a tied P-spline coefficient keeps its penalty rows, two shapes). That last test failed on the old code for both shapes, so the defect predates WP-2116. `tests/test_cross_backend.py`: the `extra_components_tied` row (two humps with tied widths, a variable on both positions, an expression on a third height, one height driving the zero shift and a P-spline coefficient), and `NO_FD_CONFIGS` for `extra_components`, which now has no FD column. Made to fail twice: dropping the tie coefficient failed the fd, jax and jax+fp32 rows of the new config, and skipping the penalty rows put that column 0.105 rel-L2 off the central FD.
  *Measured.* Acridine IX deposited start (`tests/test_acceptance_acridine_ix._fit`), this branch against a `git archive` of `origin/main` at `08d15cc61`, two runs each, darwin arm64, `[dev,jax]`, other runners on the machine (1-min load 6.5-16.9): whole fit 37.2-42.5 s against 41.0-54.8 s; Jacobians 12.8-13.7 s against 20.8-31.6 s; Bragg evaluations 105 against 441, of which 0 against 336 inside a Jacobian; iterations per stage 16, 34, 6, 12, 14 on both. Answer: Rwp 0.0584238766737 on both, worst parameter shift 3.1e-6 esd and worst esd change 5.8e-6 relative, both on the hump width; each tree bit-identical between its two runs. `python -m tests.reader_output` exit 0. Counts: fast selection on the merged tree 14757 passed, 252 skipped, 32 xfailed (darwin arm64, `[dev,jax]`, 17 min at 1-min load 24-82 beside other runners' suites); collection in the two touched files grew by 14 (+6 `test_extra_components.py`, +8 `test_cross_backend.py` for the new row), the six added functions 0.20 s together. Full suite: full selection on the same tree 15707 passed, 259 skipped, 51 xfailed and 2 failed (52 min under the machine lock, 1-min load 4-13 at its ends). Both failures fail alone on a `git archive` of `origin/main` at `506289499` as well, so neither is this branch's: `test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment` (the winner lands on the swapped minimum, m₁ 0.70 against 3.5) and `test_watch_app.py::test_a_real_gui_boots_on_a_scratch_copy_and_the_project_is_untouched` (the spawned GUI times out). The four hump-bearing acceptance files (acridine IX, extra peaks, powderline, Si 640c) passed. Main then moved and was merged in again at `506289499`. Its only change outside `docs/` was `tests/test_acceptance_acridine_ix.py` and `tests/validation_matrix.py` (WP-1806's free-atom control), so those two files were rerun on the final tree: 781 passed.
  *Review.* `/code-review high` found nine items. Fixed: the penalty-row defect (above, and its two comments), C read directly where no derived row exists, the `fd_step`, `hump_curve` and `extra_peak` docstrings. Declined: differencing one peak at a time (an extra peak is a windowed pseudo-Voigt, cheap beside the Bragg sum it no longer pays, and P is small); the GUI background band's central difference in `src/rietx/gui/background.py`, which could read `hump_partials` but sits in a tree another runner owns. The WP's "changes no number" was true of the plan and false of the build, so the priority line is gone with the close.
  *Generality.* Not dispatched: no row, threshold, default or automatic action changed. The new routes compute the same column as before, exactly or to rounding, so the change is tier 1 arithmetic as the Context said.
  PR: #1546. Next: the maintainer merges it, and issue #1418 closes with it. The GUI background band could then read `hump_partials` (see *Review*), a call for whoever next works on that band.
- **2026-11-09** — the maintainer ruled, and the WP stays open. Yue's words, 2026-11-09: "many users fit humps". So the stop rule of task 1 does not close the WP. The analytic hump columns (tasks 2-5) stay here, unscheduled, for whoever takes them next. Issue #1418 stays open with the WP. *Done.* Status line records the ruling. The priority line keeps P3 and drops "no user at the wall", which the ruling contradicts. That re-rating was settled by Claude under the template's rubric: a cost-only item with no wrong number is P3 whoever pays it. No task, code or test changed. Bookkeeping PR: #1513. Next: tasks 2-5 in order, starting with the hump's three columns computed from the component alone. Check first whether Michael's side still holds the work (Context, Source).
- **2026-11-09** — bookkeeping: task 1 is on main. Michael's PR #1441 (docs only, this file and the index) merged on 2026-11-09 at 10:42 UTC as `9979cee7c`. It carried both of his 2026-11-06 entries and the task-1 tick (`9e05e742c`), so task 1 was already ticked and nothing else here changes. A reviewer proposed closing the WP as 🛑 under its stop rule, together with issue #1418. That rule was written by the 2026-11-05 triage session (`0a011a5ad`), a Claude session, so it is evidence and not a ruling: the close waits on the maintainer, and the status stays 🔄. Bookkeeping PR: #1500. Next: the maintainer closes the WP (🛑, with its record move and #1418) or keeps it open for the next hump-bearing fit.
- **2026-11-06** — task 1 done, and the WP stops here by its own rule. LaB6, FAP, cpd-1a and NAC (the `tests/test_window_domain._protocol` fits, closing stage at 1e-3) declare no extra component. The FD fallback never runs on LaB6, FAP or NAC. On cpd-1a it runs once, for `axial_sl` while `axial_ok` is false in `lines_axial`, a column no component-only evaluation could replace. The `r0` repeat happens only when `fd_cols` is non-empty, so on these fits it costs something only where a hump is free. Acridine, re-run as the positive arm on `263227986` with #1416's `_fit`, reproduced the issue: hump FD + `r0` 49 % of the closing Jacobian (`r0` 12 %), 24 % of the fit. Sum check: FD seconds within 1.3 % of 4 × the median residual per Jacobian. Method: the first `evaluate` in a Jacobian is `r0`, and each later one is a column, classed by the decoded paths it moves. Measured on darwin arm64, 4 threads, 1-min load 4.4–6.9. Table and setup on #1418. Not done: tasks 2–5. Next: the maintainer closes the WP (🛑, with its record move) or keeps it for the next hump-bearing fit.
- **2026-11-06** — taken by Michael's side for task 1, the cost on LaB6, FAP, cpd-1a and NAC, measured on the Mac at `263227986` with acridine re-run as the positive arm. Nothing in `src/` changes in task 1. Next: the per-fixture table, then the stop rule.
- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1418). Checked against the tree at `541f0daf7`: read the `fd_cols` loop and its comment at `least_squares.py:2131-2149`, which do what the issue says; the timings were not re-run; no open WP owns it: WP-2045 is the runaway stop, and WP-1806 is the acceptance fit. Next: the four-fixture cost, which decides whether the WP is worth building.
