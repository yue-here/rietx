# WP-2116 — an extra component's columns cost no Bragg evaluation

Milestone: unscheduled · Status: 🔄 2026-11-09 — task 1 done (PR #1441). Ruled by Yue 2026-11-09, "many users fit humps": the WP stays open and unscheduled for the analytic hump columns (tasks 2-5)
Track: A long run is not one fit
Depends on: —
Priority: P3 2026-11-09 — a cost-only item: 18-24 % of a fit that frees a hump (acridine), on a path many users run (Yue, 2026-11-09); it changes no number

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

- [ ] Compute the hump's three columns from the component, keeping the whole-model route for any tie reaching outside it.
- [ ] Reuse `r0` where the spelling allows it, or record why not.
- [ ] A cross-backend row, and a test that the component columns match the whole-model FD column to the bar the step allows.
- [ ] Rewrite the "not worth writing" comment with the measurement.
- [ ] Skill: none, since no surface changes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_extra_components.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #1418; WP-1102, WP-1103 (the extra components), WP-2002 (the closing stage), WP-1806.

## Handover log

- **2026-11-09** — the maintainer ruled, and the WP stays open. Yue's words, 2026-11-09: "many users fit humps". So the stop rule of task 1 does not close the WP. The analytic hump columns (tasks 2-5) stay here, unscheduled, for whoever takes them next. Issue #1418 stays open with the WP. *Done.* Status line records the ruling. The priority line keeps P3 and drops "no user at the wall", which the ruling contradicts. That re-rating was settled by Claude under the template's rubric: a cost-only item with no wrong number is P3 whoever pays it. No task, code or test changed. Bookkeeping PR: #1513. Next: tasks 2-5 in order, starting with the hump's three columns computed from the component alone. Check first whether Michael's side still holds the work (Context, Source).
- **2026-11-09** — bookkeeping: task 1 is on main. Michael's PR #1441 (docs only, this file and the index) merged on 2026-11-09 at 10:42 UTC as `9979cee7c`. It carried both of his 2026-11-06 entries and the task-1 tick (`9e05e742c`), so task 1 was already ticked and nothing else here changes. A reviewer proposed closing the WP as 🛑 under its stop rule, together with issue #1418. That rule was written by the 2026-11-05 triage session (`0a011a5ad`), a Claude session, so it is evidence and not a ruling: the close waits on the maintainer, and the status stays 🔄. Bookkeeping PR: #1500. Next: the maintainer closes the WP (🛑, with its record move and #1418) or keeps it open for the next hump-bearing fit.
- **2026-11-06** — task 1 done, and the WP stops here by its own rule. LaB6, FAP, cpd-1a and NAC (the `tests/test_window_domain._protocol` fits, closing stage at 1e-3) declare no extra component. The FD fallback never runs on LaB6, FAP or NAC. On cpd-1a it runs once, for `axial_sl` while `axial_ok` is false in `lines_axial`, a column no component-only evaluation could replace. The `r0` repeat happens only when `fd_cols` is non-empty, so on these fits it costs something only where a hump is free. Acridine, re-run as the positive arm on `263227986` with #1416's `_fit`, reproduced the issue: hump FD + `r0` 49 % of the closing Jacobian (`r0` 12 %), 24 % of the fit. Sum check: FD seconds within 1.3 % of 4 × the median residual per Jacobian. Method: the first `evaluate` in a Jacobian is `r0`, and each later one is a column, classed by the decoded paths it moves. Measured on darwin arm64, 4 threads, 1-min load 4.4–6.9. Table and setup on #1418. Not done: tasks 2–5. Next: the maintainer closes the WP (🛑, with its record move) or keeps it for the next hump-bearing fit.
- **2026-11-06** — taken by Michael's side for task 1, the cost on LaB6, FAP, cpd-1a and NAC, measured on the Mac at `263227986` with acridine re-run as the positive arm. Nothing in `src/` changes in task 1. Next: the per-fixture table, then the stop rule.
- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1418). Checked against the tree at `541f0daf7`: read the `fd_cols` loop and its comment at `least_squares.py:2131-2149`, which do what the issue says; the timings were not re-run; no open WP owns it: WP-2045 is the runaway stop, and WP-1806 is the acceptance fit. Next: the four-fixture cost, which decides whether the WP is worth building.
