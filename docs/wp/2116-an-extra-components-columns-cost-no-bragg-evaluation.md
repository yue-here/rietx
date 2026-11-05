# WP-2116 — an extra component's columns cost no Bragg evaluation

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P3 2026-11-05 — a cost-only item with no user at the wall: 22 % of one acridine fit, on fits that declare `extra_components`

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

- [ ] Cost it on the other four fixtures (LaB6, FAP, cpd-1a, NAC), which the issue has not done. Stop if no fit but a hump-bearing one gains.
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

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1418). Checked against the tree at `541f0daf7`: read the `fd_cols` loop and its comment at `least_squares.py:2131-2149`, which do what the issue says; the timings were not re-run; no open WP owns it: WP-2045 is the runaway stop, and WP-1806 is the acceptance fit. Next: the four-fixture cost, which decides whether the WP is worth building.
