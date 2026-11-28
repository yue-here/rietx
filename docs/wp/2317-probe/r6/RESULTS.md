# R6 as built: the shift test against the 1e-9 stop it replaces

WP-2317 R6, measured 2026-11-28 on the branch `wp2317-stopping-rule` by
`measure.py` beside this file. macOS arm64 (Darwin 25.6), Python 3.12.10, rietx
1.13.0.dev0, the worktree's own `.venv` with the `[dev]` install, on a machine
shared with other sessions.

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
| SRM 660c LaB₆ | 69 → 65 | 71 → 66 | 9 → 5 | 2.97-3.01 → 2.33-2.55 | 0.026 esd, `instrument.profile.v` |
| fluorapatite | 40 → 34 | 43 → 36 | 9 → 3 | 3.98-5.10 → 3.24-4.33 | 0.044 esd, `instrument.geometry.axial_sl` |
| 11-BM NAC | 49 → 43 | 50 → 44 | 10 → 4 | 3.36-3.43 → 3.04-3.27 | 0.010 esd, `phases.1.cell.a` |
| cpd-1a | 165 → 143 | 166 → 144 | 14 → 3 | 12.4-20.9 → 8.7-10.8 | 0.052 esd, `phases.0.atoms.0.biso` |
| Nb₁₈W₁₆O₉₃, `bigcell-structural` | 116 → 104 | 117 → 105 | 13 → 1 | 38.5-50.3 → 33.4-45.1 | 0.011 esd, `phases.0.atoms.4.y` |
| Nb₁₈W₁₆O₉₃, `bigcell-lebail` | 26 → 23 | 29 → 25 | 6 → 3 | 88.9-104.0 → 79.4-104.5 | 0.015 esd, `phases.0.cell.a` |
| Nb₁₈W₁₆O₉₃, `bigcell-pawley` (2θ ≤ 90°) | 43 → 37 | 44 → 38 | 14 → 8 | 8.6-11.5 → 10.2-10.5 | 0.036 esd, `instrument.profile.v` |
| Nb₁₈W₁₆O₉₃, `bigcell-pawley-120` | 43 → 36 | 44 → 37 | 14 → 7 | 35.1-43.1 → 35.0-39.7 | 0.038 esd, `instrument.profile.u` |

`bigcell` (the R6 probe's key) and `bigcell-structural` are one fit and gave
identical numbers. Every last stage stopped on the shift test, and no other
stage did. Rwp moved by under 5e-6 in every case.

The Pawley cases do not get faster. Their normal matrix is sparse past 128
columns, so each iteration's undamped solve is a projected-CG solve, about the
cost of the evaluations it saves.

## Series

Each series ran once an arm, the chain warm-started pattern to pattern.

| Series | Evaluations (nfev) | Jacobians | Wall clock in s | Worst departure | Worst on the quantities read |
|---|---|---|---|---|---|
| CuCr₂O₄ ramp, 17 patterns, `mccusker_default` | 1 293 → 748 | 1 162 → 658 | 102.7 → 43.5 | 0.72 esd, pattern 16, `phases.1.cell.a` (CuO, about 1 wt%) | main-phase cell 0.006 esd; weight fractions 0.071 esd |
| cpd-1 chain, 8 patterns, `qpa_plan` | 516 → 411 | 451 → 344 | 37.7 → 30.5 | 0.59 esd, pattern 2, `instrument.profile.v` | cells ≤ 0.19 esd; weight fractions ≤ 0.050 esd |

On cpd-1 some last stages stopped first on `ftol_runs` or `exhausted_fp64`.
The cpd-1 chain's own floor is of the same size: under the 1e-9 stop, one
start nudge in ten moves `axial_sl` by 0.5 esd (`../errmeasure/`). The CuCr₂O₄
worst entry is the minor phase's cell on a flat valley, as in the R6 probe
(`../convnoise/RESULTS.md`, 1.2 esd for the damped-step reading). The undamped
test takes about twice the probe's 363 evaluations on the ramp and halves its
worst departure.

## Reading

A single fit's last stage is a small part of its cost, so the stop saves 6-16 %
of the evaluations there, and a series 20-42 %. On a single fit every refined value stays within 0.06
of its esd of the 1e-9 answer; on a series within 0.72, the weight fractions
within 0.071. That is inside the 0.1 band the test uses, and the departure a
user publishing at McCusker's criterion already accepts.
