# R6 as built: the shift test against the 1e-9 stop it replaces

WP-2317 R6, measured 2026-11-28 on the branch `wp2317-stopping-rule` by
`measure.py` beside this file, after `origin/main` with R7 (#1881, the
per-stage window slack and its re-solve) was merged in. macOS arm64 (Darwin
25.6), Python 3.12.10, rietx 1.13.0.dev0, the worktree's own `.venv` with the
`[dev]` install, on a machine shared with other sessions. The first run, before
the merge, is in this file's history; the merge moved the counts by a few
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
| SRM 660c LaB₆ | 71 → 66 | 70 → 67 | 11 → 6 | 1.26-1.30 → 1.05-1.13 | 0.016 esd, `instrument.profile.v` |
| fluorapatite | 40 → 34 | 43 → 36 | 9 → 3 | 2.04-2.07 → 1.79-1.85 | 0.046 esd, `instrument.geometry.axial_sl` |
| 11-BM NAC | 49 → 43 | 50 → 44 | 10 → 4 | 1.26-1.43 → 1.11-1.12 | 0.010 esd, `phases.1.cell.a` |
| cpd-1a | 165 → 143 | 166 → 144 | 14 → 3 | 6.24-7.21 → 4.51-4.60 | 0.052 esd, `phases.0.atoms.0.biso` |
| Nb₁₈W₁₆O₉₃, `bigcell-structural` | 116 → 104 | 117 → 105 | 13 → 1 | 24.3-24.4 → 21.7-22.5 | 0.011 esd, `phases.0.atoms.4.dof.1` |
| Nb₁₈W₁₆O₉₃, `bigcell-lebail` | 26 → 23 | 29 → 25 | 6 → 3 | 51.4-53.7 → 50.6-54.6 | 0.015 esd, `phases.0.cell.a` |
| Nb₁₈W₁₆O₉₃, `bigcell-pawley` (2θ ≤ 90°) | 43 → 37 | 44 → 38 | 14 → 8 | 6.44-6.50 → 6.53-6.61 | 0.035 esd, `instrument.profile.v` |
| Nb₁₈W₁₆O₉₃, `bigcell-pawley-120` | 43 → 36 | 44 → 37 | 14 → 7 | 17.8-18.7 → 16.9-17.7 | 0.038 esd, `instrument.profile.u` |

The R6 probe's `bigcell` key is `bigcell-structural` and gave identical numbers
in the first run, so it was not run again. Every last stage stopped on the shift
test, and no other stage did. Rwp moved by under 5e-6 in every case.

The Pawley and Le Bail cases do not get faster in wall clock. A Pawley normal
matrix is sparse past 128 columns, so each iteration's undamped solve is a
projected-CG solve, about the cost of the evaluations it saves. The Le Bail
case's time is in its intensity partitioning, which the stop does not touch.

## Series

Each series ran once an arm, the chain warm-started pattern to pattern.

| Series | Evaluations (nfev) | Jacobians | Wall clock in s | Worst departure | Worst on the quantities read |
|---|---|---|---|---|---|
| CuCr₂O₄ ramp, 17 patterns, `mccusker_default` | 1 326 → 765 | 1 185 → 681 | 94.6 → 25.9 | 0.72 esd, pattern 16, `phases.1.cell.a` (CuO, about 1 wt%) | main-phase cell 0.006 esd; weight fractions 0.071 esd |
| cpd-1 chain, 8 patterns, `qpa_plan` | 504 → 403 | 440 → 329 | 23.1 → 29.4 | 0.45 esd, pattern 2, `instrument.geometry.axial_sl` | cells ≤ 0.12 esd; weight fractions ≤ 0.050 esd |

The series wall clocks are one run each on a shared machine. They rank
nothing: cpd-1's shipped arm ran slower with 20 % fewer evaluations.

On cpd-1 some last stages stopped first on `ftol_runs` or `exhausted_fp64`.
The cpd-1 chain's own floor is of the same size as its worst departure: under
the 1e-9 stop, one start nudge in ten moves `axial_sl` by 0.5 esd
(`../errmeasure/`). The CuCr₂O₄ worst entry is the minor phase's cell on a
flat valley, as in the R6 probe (`../convnoise/RESULTS.md`, 1.2 esd for the
damped-step reading). There the floor is 3e-4 esd, so the 0.72 is the stop's.

### Along the chain

The worst departure on each pattern, in esd, in chain order:

| Series | Per pattern |
|---|---|
| CuCr₂O₄ | 0.038, 0.042, 0.051, 0.089, 0.095, 0.043, 0.007, 0.049, 0.007, 0.007, 0.009, 0.006, 0.045, 0.012, 0.004, 0.007, 0.720 |
| cpd-1 | 0.052, 0.035, 0.449, 0.009, 0.131, 0.291, 0.220, 0.246 |

Neither grows along the chain. Each pattern starts from the last answer and is
refitted to its own stop, so a departure one pattern leaves does not build up
in the next. CuCr₂O₄'s 0.72 is on the last pattern, which seeds nothing.
Neighbour differences and the `direction="both"` gap were not measured under
the two arms.

## Reading

A single fit's last stage is a small part of its cost, so the stop saves 6-16 %
of the evaluations there, and a series 20-42 %. On a single fit every refined
value stays within 0.06 of its esd of the 1e-9 answer. On a series the worst
value is within 0.72 esd and the weight fractions within 0.071. GSAS-II's own
sequential stop leaves the same ramp's CuO cell 10.5 esd from its tight answer
(`../foreign_stops/RESULTS.md` §3).
