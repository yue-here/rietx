# R6 as built: the shift test against the 1e-9 stop it replaces

WP-2317 R6, measured 2026-11-28 on the branch `wp2317-stopping-rule` by
`measure.py` beside this file, after `origin/main` with R7 (#1881, the
per-stage window slack and its re-solve) was merged in. macOS arm64 (Darwin
25.6), Python 3.12.10, rietx 1.13.0.dev0, the worktree's own `.venv` with the
`[dev]` install, on a machine shared with other sessions. Re-measured the same
day under the cap on χ²_red (8th session): the shift test's esd takes χ²_red at
no more than 1 (`optimize.lm._SHIFT_CHI2_CAP`). The uncapped figures, from the
7th session, are in brackets and in this file's history. The first run, before
the merge, is in the history too; the merge moved the counts by a few
evaluations and no worst departure past 0.15 esd.

Two arms run the shipped code and differ in one plan field. `tight` sets
`RefinementPlan.shift_over_esd_tol = None`, so every stage stops on its ftol and
the last on 1e-9, as every fit before WP-2317 did. `shipped` keeps the default
0.1. A value's departure is |shipped − tight| over the tight arm's reported esd,
taken over every refined parameter and QPA weight fraction; the worst is
quoted with its path. Evaluations are the LM driver's own counts, summed over
every solve of the fit: `nfev` residual evaluations, `njev` Jacobians. Single
fits ran the arms interleaved, twice each; wall clock is the two runs' range.
The counts were identical across repeats.

## Single fits

| Fit | Evaluations (nfev) | Jacobians | Last stage's iterations | Wall clock in s | Worst departure |
|---|---|---|---|---|---|
| SRM 660c LaB₆ | 71 → 67 [66] | 70 → 68 | 11 → 7 | 0.95-1.03 → 0.94-0.98 | 0.003 esd, `instrument.profile.y` [0.016] |
| fluorapatite | 40 → 35 [34] | 43 → 37 | 9 → 4 | 1.80-1.81 → 1.59-1.63 | 0.016 esd, `instrument.geometry.axial_sl` [0.046] |
| 11-BM NAC | 49 → 44 [43] | 50 → 45 | 10 → 5 | 1.01-1.18 → 0.95-1.03 | 0.004 esd, `phases.1.cell.a` [0.010] |
| cpd-1a | 165 → 145 [143] | 166 → 146 | 14 → 4 | 4.09-4.59 → 2.89-3.06 | 0.030 esd, `phases.0.atoms.0.biso` [0.052] |
| Nb₁₈W₁₆O₉₃, `bigcell-structural` | 116 → 104 [104] | 117 → 105 | 13 → 1 | 16.1-16.8 → 15.0-17.3 | 0.011 esd, `phases.0.atoms.4.dof.1` [0.011] |
| Nb₁₈W₁₆O₉₃, `bigcell-lebail` | 26 → 23 [23] | 29 → 25 | 6 → 3 | 37.6-40.0 → 34.3-38.8 | 0.015 esd, `phases.0.cell.a` [0.015] |
| Nb₁₈W₁₆O₉₃, `bigcell-pawley` (2θ ≤ 90°) | 43 → 37 [37] | 44 → 38 | 14 → 8 | 4.41-4.53 → 4.62-4.65 | 0.035 esd, `instrument.profile.v` [0.035] |
| Nb₁₈W₁₆O₉₃, `bigcell-pawley-120` | 43 → 37 [36] | 44 → 38 | 14 → 8 | 14.1-15.2 → 14.2-14.4 | 0.009 esd, `instrument.profile.u` [0.038] |

The R6 probe's `bigcell` key is `bigcell-structural` and gave identical numbers
in the first run, so it was not run again. Every last stage stopped on the shift
test, and no other stage did. Rwp moved by under 4e-6 in every case. The cap
costs at most two evaluations a fit against the uncapped test, and no departure
grew under it.

The Pawley and Le Bail cases do not get faster in wall clock. A Pawley normal
matrix is sparse past 128 columns, so each iteration's undamped solve is a
projected-CG solve, about the cost of the evaluations it saves. The Le Bail
case's time is in its intensity partitioning, which the stop does not touch.

## Series

Each series ran once an arm, the chain warm-started pattern to pattern.

| Series | Evaluations (nfev) | Jacobians | Wall clock in s | Worst departure | Worst on the quantities read |
|---|---|---|---|---|---|
| CuCr₂O₄ ramp, 17 patterns, `mccusker_default` | 1 326 → 848 [765] | 1 185 → 759 | 83.0 → 51.2 | 0.68 esd, pattern 16, `phases.1.cell.a` (CuO, about 1 wt%) [0.72] | main-phase cell 0.006 esd; weight fractions 0.071 esd |
| cpd-1 chain, 8 patterns, `qpa_plan` | 504 → 453 [403] | 440 → 390 | 24.9 → 23.3 | 0.13 esd, pattern 2, `instrument.geometry.axial_sl` [0.45] | cells ≤ 0.030 esd; weight fractions ≤ 0.027 esd |

The series wall clocks are one run each on a shared machine. They rank
nothing: in the uncapped run cpd-1's shipped arm ran slower with 20 % fewer
evaluations.

On cpd-1 some last stages stopped first on `ftol_runs` or `exhausted_fp64`.
The cpd-1 chain's own floor is of the same size as its worst departure: under
the 1e-9 stop, one start nudge in ten moves `axial_sl` by 0.5 esd
(`../errmeasure/`). The CuCr₂O₄ worst entry is the minor phase's cell on a
flat valley, as in the R6 probe (`../convnoise/RESULTS.md`, 1.2 esd for the
damped-step reading). There the floor is 3e-4 esd, so the 0.68 is the stop's.

### Along the chain

The worst departure on each pattern, in esd, in chain order:

| Series | Per pattern |
|---|---|
| CuCr₂O₄ | 0.020, 0.024, 0.028, 0.061, 0.073, 0.030, 0.002, 0.025, 0.004, 0.005, 0.002, 0.005, 0.040, 0.002, 0.004, 0.001, 0.675 |
| cpd-1 | 0.030, 0.003, 0.125, 0.003, 0.060, 0.003, 0.001, 0.046 |

Neither grows along the chain. Each pattern starts from the last answer and is
refitted to its own stop, so a departure one pattern leaves does not build up
in the next. CuCr₂O₄'s 0.68 is on the last pattern, which seeds nothing.
Neighbour differences and the `direction="both"` gap were not measured under
the two arms.

## Reading

A single fit's last stage is a small part of its cost, so the stop saves 5-14 %
of the evaluations there, and a series 10-36 %. On a single fit every refined
value stays within 0.04 of its esd of the 1e-9 answer. On a series the worst
value is within 0.68 esd and the weight fractions within 0.071. GSAS-II's own
sequential stop leaves the same ramp's CuO cell 10.5 esd from its tight answer
(`../foreign_stops/RESULTS.md` §3).

## Why the esd is capped

Tutorial 05's 2 % cell jump, refitted warm (`tests/test_instrument_hold_noise.py::test_the_tutorials_step_is_reached_warm`),
logged at each shift-test reading by a probe kept in the runner's scratch:

| Gate | Where the last stage's first solve stopped | Outcome |
|---|---|---|
| none (σ at χ²_red) | χ²_red 632, the undamped step reading 0.076 esd (1.9 at χ²_red = 1), right after one step that lowered χ² 956-fold | Rwp 0.966, a = 4.16284 Å against 4.24821; rescued only by the series ladder's `warm_staged` rung |
| the step just taken must pass the scaled test too | χ²_red 632, two steps later: the taken step read 0.019, the undamped one 0.066 | the same false stop; a later re-solve happened to recover it |
| σ at min(χ²_red, 1) | χ²_red 1.03 | the warm rung itself, Rwp 0.0395 |

With the cap every shift-test stop in that run fell at χ²_red 1.03-1.04.
