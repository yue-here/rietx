# Convergence noise against measurable change — WP-2317 R6 measurements

**Tree:** detached at `wp2317-rulings`, commit `aa612fe02`. Large cell from
`wp2317-cod-bigcells` (PR #1866, `8a859c90b`): `tests/test_large_cell_refinement.py`
and `tests/data/cod_2107344.cif` copied to `bigcell/` here, the case rebuilt as
`examples/bench_refinement.py`'s `bigcell-structural`. **Venv:** the worktree's
`.venv`, `[dev]`, CPython 3.12.10 arm64, rietx 1.13.0.dev0 editable.
**Platform:** Darwin 25.6.0 arm64, shared machine (walls not comparable; counts
only). Nothing in the package was changed. Scripts: `stops.py`, `single.py`,
`series.py`, `analyse_*.py`, `perq_series.py`, `worst_series.py`. The raw
`results/*.json` (1.7 MB) are not committed: `single.py` and `series.py` rebuild them,
reading the large cell from `tests/` (on `main` since PR #1866).

## Method

- **The stops.** `stops.py` replaces `rietx.optimize.lm.minimize` (the module
  attribute `least_squares` calls) with a wrapper. It is a measurement harness,
  not a package change.
  - `ftol` 1e-8 … 1e-4: `Stage.ftol` on the plan's **last declared stage**. The
    package's rule is unchanged: relative decrease in S under `ftol` on three
    consecutive accepted iterations. The cpd-1a protocol's closing stage copies
    that `ftol` (`RefinementPlan` line 464), so it gets the same stop.
  - **GSAS-II-like** (`gsas`): stop at the first accepted iteration whose relative
    decrease in S is under 1e-3 (`min dM/M`, one cycle suffices). `gsas3` adds the
    3-cycle cap of one `Refine` call, counted from the last stage's start.
  - **FullProf-like** (`fp0.2`, `fp0.1`): stop at the first accepted iteration
    where every free column's last shift is under 0.2 (0.1) × its esd. The esd is
    recomputed **at that iterate** from the solver's Jacobian,
    √(χ²_red·diag((JᵀJ)⁻¹)) with Jacobi equilibration and no Bérar-Lelann
    factor, as FullProf's own test uses its standard esd.
  - Both custom stops are **real stops**, not post-hoc picks: a sentinel `ftol` on
    the last stage selects the rule; the wrapper's Jacobian hook tests each new
    accepted point and ends the solve there (the outcome is rebuilt at that
    point by one `max_nfev=1` call, whose extra evaluation is not counted). Every
    other stage runs exactly as shipped. So in a series each pattern's warm start
    carries the looser answer forward, as it would in use.
- **Reference:** the shipped schedule (intermediate 1e-6, last 1e-9).
- **Floor:** five reruns at 1e-9 with every model `Parameter` value outside the
  source multiplied by 1 + 1e-12·u, u uniform in [−1, 1] (two reruns for each
  series). This nudges the start of the whole plan, so it measures what a
  user's rerun of the same fit would see.
- **Departure:** |value − 1e-9 value| / esd, per parameter, with the esd the
  1e-9 fit reports (Bérar-Lelann-inflated, `RefinedParameter.stderr`). Raw-esd
  figures (`stderr_uncorrected`) are given where they matter; the inflation f is
  in each table header. Families: cell; zero/displacement; profile (U V W X Y,
  phase size/strain, axial, line weights); Biso/coords; scale; background.
  "Phase frac" is the QPA weight fraction over its own esd.
- **ΔS** is given two ways: on the **solver's own frozen model** (2 × the LM
  cost of the last solve), and on the **reported** χ² (`statistics.chi2` ×
  (N−P)). They differ: see "recompile gap".
- **Evaluations** are residual evaluations of the last stage as LM counts them
  (`nfev`); Jacobian evaluations in brackets.

**Fixtures** (acceptance protocols): `srm660c`, `fap`, `nac` from
`rietx.viz.compare.STANDARD_BY_KEY[...].build` (the compare registry,
asserted field by field against the acceptance suites by
`tests/test_compare_ui.py`); `cpd1a` from `tests/test_acceptance_qpa_roundrobin`
(`qpa_plan()` with its closing stage, `seed_scales`); `bigcell` =
`bigcell-structural` (Nb₁₈W₁₆O₉₃, COD 2107344, simulated pattern, 2θ ≤ 90°,
`mccusker_structural`, co-sited Nb/W tied, 117 free columns).

**Series:** `cucr2o4` = WP-2081's `default` route
(`docs/wp/2081-batch/measure_real_ramp.py`): 17 patterns 6.8-288.7 K,
`SequentialRefinement(...).fit(plan=mccusker_default)`, CuCr₂O₄ + CuO (≈1.1 wt%).
`cpd1` = `tests/test_acceptance_sequential.py`'s `chained` fixture: cpd-1a…h,
`carry=CARRY`, the seed hook, `qpa_plan()`. In both, a warm pattern runs **one**
stage, the plan's last, so the last-stage stop governs nearly all of a series'
cost (21 solves for 17 patterns in `cucr2o4`).

## Part 1 — convergence noise in a single fit

### Summary: largest departure per family, over all five fixtures, in reported esd

| stop | cell | zero/disp | profile | Biso/coords | scale | background | phase frac | worst fixture | last-stage evals (srm/fap/nac/cpd1a/big) |
|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  | 9/9/10/29/14 |
| ftol1e-8 | 0.00058 | 0.00054 | 0.00046 | 0.006 | 0.00053 | 0.00076 | 0.00036 | bigcell | 9/9/9/25/6 |
| ftol1e-7 | 0.00075 | 0.00063 | 0.00049 | 0.0075 | 0.00081 | 0.00095 | 0.00081 | bigcell | 9/8/8/20/5 |
| ftol1e-6 | 0.00075 | 0.00063 | 0.001 | 0.0075 | 0.0025 | 0.00095 | 0.0025 | bigcell | 9/7/7/15/5 |
| ftol1e-5 | 0.0017 | 0.0012 | 0.011 | 0.0091 | 0.0083 | 0.0045 | 0.0083 | srm660c | 6/6/6/12/5 |
| ftol1e-4 | 0.007 | 0.0039 | 0.011 | 0.016 | 0.015 | 0.0045 | 0.015 | cpd1a | 6/5/6/10/5 |
| gsas | 0.027 | 0.039 | 0.046 | 0.058 | 0.054 | 0.014 | 0.054 | cpd1a | 3/3/3/6/3 |
| gsas3 | 0.027 | 0.039 | 0.046 | 0.058 | 0.054 | 0.014 | 0.054 | cpd1a | 3/3/3/6/3 |
| fp0.2 | 0.026 | 0.039 | 0.044 | 0.052 | 0.05 | 0.012 | 0.05 | cpd1a | 4/3/4/7/3 |
| fp0.1 | 0.0084 | 0.013 | 0.034 | 0.03 | 0.027 | 0.0099 | 0.027 | srm660c | 4/4/5/9/3 |
| nudge0 | 9e-07 | 9.3e-07 | 1.9e-07 | 1.9e-06 | 5.9e-08 | 1.6e-07 | 5.5e-08 | bigcell | 9/9/10/29/14 |
| nudge1 | 1.4e-06 | 1.4e-06 | 1.9e-07 | 1.2e-06 | 9.6e-08 | 1.3e-07 | 6.9e-08 | cpd1a | 9/9/10/29/14 |
| nudge2 | 0.039 | 0.01 | 0.011 | 4.3 | 0.014 | 0.061 | 9.5e-08 | bigcell | 9/9/10/29/9 |
| nudge3 | 6.4e-07 | 6.3e-07 | 2.1e-07 | 4.5e-06 | 4.1e-08 | 4e-07 | 3.8e-08 | bigcell | 9/9/10/29/14 |
| nudge4 | 0.039 | 0.01 | 0.011 | 4.3 | 0.014 | 0.061 | 9e-08 | bigcell | 9/9/10/29/9 |

Largest departure in **raw** (uninflated) esd, worst parameter, measured:

| stop | srm660c | fap | nac | cpd1a | bigcell |
|---|---|---|---|---|---|
| ftol 1e-6 | 0 | 0.00084 | 0.0041 | 0.0091 | 0.013 |
| ftol 1e-4 | 0.03 | 0.01 | 0.011 | 0.054 | 0.013 |
| GSAS-like | 0.13 | 0.095 | 0.21 | 0.19 | 0.015 |
| FullProf 0.2 | 0.096 | 0.095 | 0.08 | 0.18 | 0.015 |
| FullProf 0.1 | 0.096 | 0.032 | 0.03 | 0.10 | 0.015 |

Read off these tables (measured):

- Every stop tested keeps every family under 0.06 reported esd on all five
  single fits. ftol ≤ 1e-4 keeps it under 0.016; 1e-6 under 0.0075.
- The cost saved on a single fit is small: the last stage is 9-29 evaluations
  at 1e-9 out of 40-165 for the whole fit. 1e-6 saves 0-14 evaluations (0-9 %
  of a fit), 1e-4 saves 3-19 (4-12 %), the GSAS-like stop 6-23 (8-14 %).
- **Floor.** On four fixtures the 1e-12 nudge moves nothing by more than 1.4e-6
  esd. On the large cell, 2 of 5 nudges land in **another answer**: O atoms 23
  and 27 move 3.3-4.3 esd (y, x), and the reported χ² is 1.49 lower
  (0.76 χ²_red). The two answers are both converged (`ftol_runs`, max shift/esd
  4e-4). So on the large cell the 1e-9 answer is one of at least two nearby
  minima, and which one a fit reaches depends on the 13th digit of the start.
  That path dependence is 250× larger than anything any stop added there.

### Per-fixture tables (reported esd; ΔS on the reported χ²)


#### srm660c: N-P = 5314, chi2_red = 3.5646, S = 18942.4, esd_inflation = 2.810, n_free = 18
| stop | evals last stage (J) | evals total | ΔS | ΔS/χ²_red | cell | zero/disp | profile | Biso/coords | scale | background | phase frac | max shift/esd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 9 (10) | 69 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5.7e-05 |
| ftol1e-8 | 9 (10) | 69 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5.7e-05 |
| ftol1e-7 | 9 (10) | 69 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5.7e-05 |
| ftol1e-6 | 9 (9) | 69 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5.7e-05 |
| ftol1e-5 | 6 (6) | 66 | 0.0144 | 0.00403 | 0.00078 | 0.0012 | 0.011 | 0.0036 | 0.003 | 0.0045 | 0 | 0.016 |
| ftol1e-4 | 6 (6) | 66 | 0.0144 | 0.00403 | 0.00078 | 0.0012 | 0.011 | 0.0036 | 0.003 | 0.0045 | 0 | 0.016 |
| gsas | 3 (3) | 63 | 0.125 | 0.0352 | 0.011 | 0.01 | 0.046 | 0.01 | 0.0091 | 0.0094 | 0 | 0.21 |
| gsas3 | 3 (3) | 63 | 0.125 | 0.0352 | 0.011 | 0.01 | 0.046 | 0.01 | 0.0091 | 0.0094 | 0 | 0.21 |
| fp0.2 | 4 (4) | 64 | 0.0707 | 0.0198 | 0.0075 | 0.0089 | 0.034 | 0.0093 | 0.0078 | 0.0099 | 0 | 0.012 |
| fp0.1 | 4 (4) | 64 | 0.0707 | 0.0198 | 0.0075 | 0.0089 | 0.034 | 0.0093 | 0.0078 | 0.0099 | 0 | 0.012 |
| nudge0 | 9 (10) | 69 | -8.25e-07 | -2.32e-07 | 1.5e-07 | 3.2e-08 | 2.8e-08 | 3.1e-09 | 1.7e-09 | 2.8e-09 | 0 | 5.7e-05 |
| nudge1 | 9 (10) | 69 | 2.1e-06 | 5.89e-07 | 1.2e-08 | 7.5e-09 | 1.9e-07 | 2.9e-08 | 3e-08 | 4.6e-08 | 0 | 5.7e-05 |
| nudge2 | 9 (10) | 69 | -9.41e-07 | -2.64e-07 | 7.4e-08 | 2.5e-08 | 1.8e-07 | 3.6e-08 | 3.6e-08 | 4.8e-08 | 0 | 5.7e-05 |
| nudge3 | 9 (10) | 69 | 6.09e-07 | 1.71e-07 | 6e-08 | 3.8e-09 | 2e-07 | 3.6e-08 | 3.6e-08 | 4.9e-08 | 0 | 5.7e-05 |
| nudge4 | 9 (10) | 69 | -2.62e-06 | -7.36e-07 | 1.6e-08 | 5e-08 | 3.5e-08 | 1.6e-09 | 1.2e-09 | 1.5e-09 | 0 | 5.7e-05 |

#### fap: N-P = 5730, chi2_red = 2.7284, S = 15633.9, esd_inflation = 2.141, n_free = 20
| stop | evals last stage (J) | evals total | ΔS | ΔS/χ²_red | cell | zero/disp | profile | Biso/coords | scale | background | phase frac | max shift/esd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 9 (10) | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9e-05 |
| ftol1e-8 | 9 (9) | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9e-05 |
| ftol1e-7 | 8 (8) | 39 | -9.44e-06 | -3.46e-06 | 4.7e-05 | 7.4e-05 | 9e-05 | 5.5e-06 | 1.3e-05 | 7.7e-06 | 0 | 0.0003 |
| ftol1e-6 | 7 (7) | 38 | -4.02e-05 | -1.47e-05 | 0.00021 | 0.00032 | 0.00039 | 2.4e-05 | 5.9e-05 | 3.4e-05 | 0 | 0.001 |
| ftol1e-5 | 6 (6) | 37 | -0.000132 | -4.82e-05 | 0.00074 | 0.0012 | 0.0014 | 9e-05 | 0.00022 | 0.00012 | 0 | 0.0033 |
| ftol1e-4 | 5 (5) | 36 | -0.000307 | -0.000113 | 0.0025 | 0.0039 | 0.0047 | 0.00034 | 0.00077 | 0.00042 | 0 | 0.01 |
| gsas | 3 (3) | 34 | -0.181 | -0.0662 | 0.026 | 0.039 | 0.044 | 0.0053 | 0.0091 | 0.0045 | 0 | 0.067 |
| gsas3 | 3 (3) | 34 | -0.181 | -0.0662 | 0.026 | 0.039 | 0.044 | 0.0053 | 0.0091 | 0.0045 | 0 | 0.067 |
| fp0.2 | 3 (3) | 34 | -0.181 | -0.0662 | 0.026 | 0.039 | 0.044 | 0.0053 | 0.0091 | 0.0045 | 0 | 0.067 |
| fp0.1 | 4 (4) | 35 | 0.0868 | 0.0318 | 0.0084 | 0.013 | 0.015 | 0.0013 | 0.0027 | 0.0014 | 0 | 0.029 |
| nudge0 | 9 (10) | 40 | -4.9e-06 | -1.79e-06 | 4.1e-08 | 1.3e-08 | 1.5e-08 | 4.6e-08 | 1.4e-08 | 8.1e-09 | 0 | 9e-05 |
| nudge1 | 9 (10) | 40 | -1.28e-07 | -4.71e-08 | 1.1e-08 | 4.3e-09 | 4.3e-09 | 3.2e-08 | 2.8e-09 | 1.8e-09 | 0 | 9e-05 |
| nudge2 | 9 (10) | 40 | -1.72e-06 | -6.3e-07 | 3.2e-08 | 2e-08 | 2.8e-08 | 4.6e-08 | 4.9e-08 | 1.6e-08 | 0 | 9e-05 |
| nudge3 | 9 (10) | 40 | 2.36e-06 | 8.64e-07 | 5.2e-08 | 2.9e-09 | 4.2e-09 | 3.6e-08 | 2.3e-10 | 1.7e-09 | 0 | 9e-05 |
| nudge4 | 9 (10) | 40 | 3.22e-06 | 1.18e-06 | 3.2e-08 | 4.1e-08 | 4.2e-08 | 3.1e-08 | 5e-09 | 4.3e-09 | 0 | 9e-05 |

#### nac: N-P = 21979, chi2_red = 12.4846, S = 274398.2, esd_inflation = 8.036, n_free = 24
| stop | evals last stage (J) | evals total | ΔS | ΔS/χ²_red | cell | zero/disp | profile | Biso/coords | scale | background | phase frac | max shift/esd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 10 (10) | 49 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4.7e-05 |
| ftol1e-8 | 9 (9) | 48 | 1.46e-06 | 1.17e-07 | 4.7e-05 | 1.7e-07 | 6.8e-07 | 1.7e-05 | 7.8e-06 | 2.7e-07 | 7.8e-06 | 0.00013 |
| ftol1e-7 | 8 (8) | 47 | 1.92e-05 | 1.54e-06 | 0.00017 | 6.3e-07 | 2.5e-06 | 6e-05 | 2.7e-05 | 9.6e-07 | 2.7e-05 | 0.00033 |
| ftol1e-6 | 7 (7) | 46 | 0.000158 | 1.27e-05 | 0.00051 | 1.8e-06 | 7.3e-06 | 0.00017 | 7.5e-05 | 2.7e-06 | 7.5e-05 | 0.00088 |
| ftol1e-5 | 6 (6) | 45 | 0.00117 | 9.35e-05 | 0.0014 | 4.8e-06 | 2.1e-05 | 0.00043 | 0.00019 | 7.1e-06 | 0.00019 | 0.0023 |
| ftol1e-4 | 6 (6) | 45 | 0.00117 | 9.35e-05 | 0.0014 | 4.8e-06 | 2.1e-05 | 0.00043 | 0.00019 | 7.1e-06 | 0.00019 | 0.0023 |
| gsas | 3 (3) | 42 | -0.806 | -0.0645 | 0.027 | 0.00071 | 0.0041 | 0.0064 | 0.0026 | 0.0006 | 0.0025 | 0.15 |
| gsas3 | 3 (3) | 42 | -0.806 | -0.0645 | 0.027 | 0.00071 | 0.0041 | 0.0064 | 0.0026 | 0.0006 | 0.0025 | 0.15 |
| fp0.2 | 4 (4) | 43 | 0.0587 | 0.0047 | 0.01 | 2.3e-05 | 0.0004 | 0.0026 | 0.0011 | 4.8e-05 | 0.001 | 0.017 |
| fp0.1 | 5 (5) | 44 | 0.00831 | 0.000666 | 0.0037 | 1.5e-05 | 7.4e-05 | 0.0011 | 0.00048 | 1.8e-05 | 0.00048 | 0.0062 |
| nudge0 | 10 (10) | 49 | -0.000108 | -8.63e-06 | 1.1e-07 | 5.6e-09 | 2.7e-09 | 3.7e-08 | 7.4e-09 | 1.9e-09 | 1.6e-09 | 4.7e-05 |
| nudge1 | 10 (10) | 49 | -0.000127 | -1.02e-05 | 3.4e-08 | 2e-08 | 1.6e-09 | 3.3e-08 | 1.8e-09 | 6.7e-10 | 9.4e-10 | 4.7e-05 |
| nudge2 | 10 (10) | 49 | -4.13e-05 | -3.31e-06 | 4.9e-08 | 9.6e-09 | 7.2e-09 | 2.3e-08 | 1.2e-08 | 2.3e-09 | 5.1e-10 | 4.7e-05 |
| nudge3 | 10 (10) | 49 | -0.000111 | -8.85e-06 | 9e-08 | 2.6e-09 | 4e-09 | 2.5e-08 | 1.2e-08 | 2.1e-09 | 2e-10 | 4.7e-05 |
| nudge4 | 10 (10) | 49 | 0.000334 | 2.67e-05 | 3.5e-08 | 1.2e-08 | 6e-09 | 2.8e-08 | 6e-09 | 8.1e-10 | 5.5e-09 | 4.7e-05 |

#### cpd1a: N-P = 7213, chi2_red = 1.8355, S = 13239.8, esd_inflation = 3.357, n_free = 38
| stop | evals last stage (J) | evals total | ΔS | ΔS/χ²_red | cell | zero/disp | profile | Biso/coords | scale | background | phase frac | max shift/esd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 29 (29) | 165 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00014 |
| ftol1e-8 | 25 (25) | 161 | -0.000154 | -8.38e-05 | 9.1e-05 | 7.6e-06 | 0.00019 | 0.00036 | 0.00036 | 9.9e-05 | 0.00036 | 0.00024 |
| ftol1e-7 | 20 (20) | 156 | -0.000165 | -9e-05 | 0.00026 | 1.1e-05 | 0.00029 | 0.00085 | 0.00081 | 0.00021 | 0.00081 | 0.0013 |
| ftol1e-6 | 15 (15) | 151 | -0.000102 | -5.55e-05 | 0.00066 | 7.4e-05 | 0.001 | 0.0027 | 0.0025 | 0.0006 | 0.0025 | 0.0029 |
| ftol1e-5 | 12 (12) | 148 | 0.000446 | 0.000243 | 0.0017 | 0.00033 | 0.0047 | 0.0091 | 0.0083 | 0.002 | 0.0083 | 0.0067 |
| ftol1e-4 | 10 (10) | 146 | 0.00678 | 0.00369 | 0.007 | 0.00057 | 0.0097 | 0.016 | 0.015 | 0.0036 | 0.015 | 0.014 |
| gsas | 6 (6) | 142 | 0.0789 | 0.043 | 0.013 | 0.0014 | 0.04 | 0.058 | 0.054 | 0.014 | 0.054 | 0.04 |
| gsas3 | 6 (6) | 142 | 0.0789 | 0.043 | 0.013 | 0.0014 | 0.04 | 0.058 | 0.054 | 0.014 | 0.054 | 0.04 |
| fp0.2 | 7 (7) | 143 | 0.0755 | 0.0411 | 0.024 | 0.0012 | 0.039 | 0.052 | 0.05 | 0.012 | 0.05 | 0.044 |
| fp0.1 | 9 (9) | 145 | 0.00857 | 0.00467 | 0.0071 | 0.00079 | 0.02 | 0.03 | 0.027 | 0.0066 | 0.027 | 0.023 |
| nudge0 | 29 (29) | 165 | 8.98e-07 | 4.89e-07 | 9e-07 | 9.3e-07 | 1.9e-07 | 7.4e-08 | 5.9e-08 | 2.8e-08 | 5.5e-08 | 0.00014 |
| nudge1 | 29 (29) | 165 | -3.55e-06 | -1.93e-06 | 1.4e-06 | 1.4e-06 | 1.7e-07 | 9.6e-08 | 9.6e-08 | 3.2e-08 | 6.9e-08 | 0.00014 |
| nudge2 | 29 (29) | 165 | -1.52e-07 | -8.26e-08 | 9.2e-07 | 8.7e-07 | 5.9e-07 | 6.5e-08 | 8.6e-08 | 9e-08 | 9.5e-08 | 0.00014 |
| nudge3 | 29 (29) | 165 | 1.09e-07 | 5.96e-08 | 6.4e-07 | 6.3e-07 | 1.7e-07 | 1.7e-08 | 4.1e-08 | 2.7e-08 | 3.8e-08 | 0.00014 |
| nudge4 | 29 (29) | 165 | -2.24e-06 | -1.22e-06 | 9.6e-07 | 9.2e-07 | 4.3e-07 | 4.6e-08 | 7.6e-08 | 7.1e-08 | 9e-08 | 0.00014 |

#### bigcell: N-P = 4133, chi2_red = 1.9614, S = 8106.4, esd_inflation = 1.712, n_free = 117
| stop | evals last stage (J) | evals total | ΔS | ΔS/χ²_red | cell | zero/disp | profile | Biso/coords | scale | background | phase frac | max shift/esd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 14 (13) | 118 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00031 |
| ftol1e-8 | 6 (5) | 110 | 0.000143 | 7.28e-05 | 0.00058 | 0.00054 | 0.00046 | 0.006 | 0.00053 | 0.00076 | 0 | 0.0015 |
| ftol1e-7 | 5 (4) | 109 | 0.000206 | 0.000105 | 0.00075 | 0.00063 | 0.00049 | 0.0075 | 0.00064 | 0.00095 | 0 | 0.00096 |
| ftol1e-6 | 5 (4) | 109 | 0.000206 | 0.000105 | 0.00075 | 0.00063 | 0.00049 | 0.0075 | 0.00064 | 0.00095 | 0 | 0.00096 |
| ftol1e-5 | 5 (4) | 109 | 0.000206 | 0.000105 | 0.00075 | 0.00063 | 0.00049 | 0.0075 | 0.00064 | 0.00095 | 0 | 0.00096 |
| ftol1e-4 | 5 (4) | 109 | 0.000206 | 0.000105 | 0.00075 | 0.00063 | 0.00049 | 0.0075 | 0.00064 | 0.00095 | 0 | 0.00096 |
| gsas | 3 (2) | 107 | 0.000333 | 0.00017 | 0.00091 | 0.00067 | 0.0005 | 0.009 | 0.00062 | 0.0012 | 0 | 0.0012 |
| gsas3 | 3 (2) | 107 | 0.000333 | 0.00017 | 0.00091 | 0.00067 | 0.0005 | 0.009 | 0.00062 | 0.0012 | 0 | 0.0012 |
| fp0.2 | 3 (2) | 107 | 0.000333 | 0.00017 | 0.00091 | 0.00067 | 0.0005 | 0.009 | 0.00062 | 0.0012 | 0 | 0.0012 |
| fp0.1 | 3 (2) | 107 | 0.000333 | 0.00017 | 0.00091 | 0.00067 | 0.0005 | 0.009 | 0.00062 | 0.0012 | 0 | 0.0012 |
| nudge0 | 14 (13) | 118 | -4.07e-08 | -2.08e-08 | 2e-08 | 9.7e-09 | 8.5e-08 | 1.9e-06 | 4.8e-08 | 1.6e-07 | 0 | 0.00031 |
| nudge1 | 14 (13) | 118 | -1.02e-07 | -5.18e-08 | 9.6e-08 | 2.3e-08 | 4.9e-08 | 1.2e-06 | 9.9e-09 | 1.3e-07 | 0 | 0.00031 |
| nudge2 | 9 (9) | 122 | -1.49 | -0.759 | 0.039 | 0.01 | 0.011 | 4.3 | 0.014 | 0.061 | 0 | 0.00037 |
| nudge3 | 14 (13) | 118 | 1.05e-07 | 5.33e-08 | 1.6e-07 | 3.8e-08 | 2.1e-07 | 4.5e-06 | 3.6e-08 | 4e-07 | 0 | 0.00031 |
| nudge4 | 9 (9) | 122 | -1.49 | -0.759 | 0.039 | 0.01 | 0.011 | 4.3 | 0.014 | 0.061 | 0 | 0.00036 |

### ΔS on the solver's own model, and the recompile gap

The solver minimises S on a model frozen at the last stage's start. The
reported χ² is evaluated afterwards. Their difference at the same answer,
"recompile gap", is measured here; its mechanism was not measured.

| fixture | recompile gap at the 1e-9 answer | ΔS_solver, 1e-6 | 1e-4 | GSAS-like | FP 0.2 | FP 0.1 | gap moves between stops by |
|---|---|---|---|---|---|---|---|
| srm660c | +7.33 χ² = 2.06 χ²_red | 0 | 0.0027 χ²_red | 0.033 | 0.017 | 0.017 | 0.01 χ² |
| fap | +2.33 = 0.85 χ²_red | 6e-7 | 7.5e-5 | 0.0067 | 0.0067 | 0.0008 | 0.29 χ² (0.1 χ²_red) |
| nac | −2.54 = −0.20 χ²_red | 1.4e-5 | 9.7e-5 | 0.038 | 0.0047 | 0.0007 | 1.28 χ² (0.1 χ²_red) |
| cpd1a | +0.80 = 0.43 χ²_red | 0.0013 | 0.0097 | 0.058 | 0.056 | 0.019 | 0.03 χ² |
| bigcell | 0 | 1.1e-4 | 1.1e-4 | 1.7e-4 | 1.7e-4 | 1.7e-4 | 0 |

ΔS_solver is in χ²_red units, i.e. the joint movement in esd², since an esd is
√(χ²_red·(JᵀJ)⁻¹). So the GSAS-like stop on these fits gives up at most 0.058
esd² of joint travel, √ = 0.24 esd. The FAP and NAC GSAS-like stops show a
*negative* reported ΔS (−0.18 and −0.81 χ²) because the recompile gap moved by
more than ΔS_solver. Inference: on these fixtures the reported χ² carries
±0.1 χ²_red of evaluation noise between two nearby answers, independent of the
stop.

Raw lines: `tables_solver_dS.txt`.

## Part 2 — differences across a series

### What the series resolve, at the shipped 1e-9 (measured)


#### cucr2o4: 17 patterns; reference rungs ['cold', 'warm']
| quantity | median |Δ| | median esd(Δ) | median |Δ|/esd(Δ) | min |Δ|/esd(Δ) |
|---|---|---|---|---|
| W[CuCr2O4] | 0.000297 | 0.00359 | 0.0807 | 0.00477 |
| W[CuO] | 0.000297 | 0.00359 | 0.0807 | 0.00477 |
| phases.0.cell.a | 0.00455 | 0.000443 | 10.7 | 0.251 |
| phases.0.cell.b | 0.000502 | 0.0373 | 0.0227 | 0.00379 |
| phases.0.cell.c | 0.000198 | 0.0374 | 0.0175 | 0.00373 |
| phases.1.cell.a | 0.00143 | 0.00462 | 0.295 | 0.0222 |
| phases.1.cell.b | 0.00141 | 0.00336 | 0.333 | 0.0038 |
| phases.1.cell.beta | 0.0268 | 0.0661 | 0.327 | 0.00492 |
| phases.1.cell.c | 0.000727 | 0.00639 | 0.11 | 0.0183 |

| stop | evals total | evals last stage | rungs | max single-pattern dep (esd): cell zero/disp profile Biso/coords scale background | max jitter in Δ cell (esd(Δ)) | max jitter in Δ W (esd(Δ)) |
|---|---|---|---|---|---|
| ftol1e-9 | 1293 | 1230 | ['cold', 'warm'] | 0 0 0 0 0 0 | 0 | 0 |
| ftol1e-8 | 1089 | 1026 | ['cold', 'warm'] | 0.0058 0.00014 0.0035 0 0.00012 0.0001 | 0.0054 | 0.00011 |
| ftol1e-6 | 695 | 632 | ['cold', 'warm'] | 0.68 0.0042 0.025 0 0.071 0.0036 | 0.44 | 0.051 |
| ftol1e-4 | 293 | 230 | ['cold', 'warm'] | 1.7 0.01 0.19 0 0.22 0.0099 | 1.2 | 0.16 |
| gsas | 183 | 120 | ['cold', 'warm'] | 1.8 0.27 0.4 0 0.25 0.021 | 1.3 | 0.16 |
| gsas3 | 140 | 77 | ['cold', 'warm'] | 11 8.3 3.3 0 6 0.35 | 3.7 | 0.34 |
| fp0.2 | 300 | 237 | ['cold', 'warm'] | 1.7 0.054 0.2 0 0.22 0.0096 | 1.2 | 0.15 |
| fp0.1 | 363 | 300 | ['cold', 'warm'] | 1.2 0.05 0.13 0 0.089 0.0047 | 1 | 0.12 |
| nudge0 | 1315 | 1252 | ['cold', 'warm'] | 0.00027 3.4e-05 0.00079 0 1.6e-05 1.8e-05 | 0.00024 | 1.2e-05 |
| nudge1 | 1300 | 1237 | ['cold', 'warm'] | 0.00027 1.1e-05 0.00077 0 1.2e-05 1.8e-05 | 0.00023 | 1e-05 |

#### cpd1: 8 patterns; reference rungs ['cold', 'warm']
| quantity | median |Δ| | median esd(Δ) | median |Δ|/esd(Δ) | min |Δ|/esd(Δ) |
|---|---|---|---|---|
| W[corundum] | 0.272 | 0.00695 | 40 | 5.08 |
| W[fluorite] | 0.164 | 0.00527 | 32.8 | 0.493 |
| W[zincite] | 0.2 | 0.0051 | 39 | 8.35 |
| phases.0.cell.a | 0.000199 | 0.000657 | 0.238 | 0.0238 |
| phases.0.cell.b | 0.000199 | 0.000657 | 0.238 | 0.0238 |
| phases.0.cell.c | 0.000463 | 0.00204 | 0.196 | 0.0132 |
| phases.1.cell.a | 0.000164 | 0.000427 | 0.423 | 0.0147 |
| phases.1.cell.b | 0.000164 | 0.000427 | 0.423 | 0.0147 |
| phases.1.cell.c | 0.000166 | 0.000699 | 0.201 | 0.00792 |
| phases.2.cell.a | 0.000351 | 0.000724 | 0.506 | 0.0139 |
| phases.2.cell.b | 0.000351 | 0.000724 | 0.506 | 0.0139 |
| phases.2.cell.c | 0.000351 | 0.000724 | 0.506 | 0.0139 |

| stop | evals total | evals last stage | rungs | max single-pattern dep (esd): cell zero/disp profile Biso/coords scale background | max jitter in Δ cell (esd(Δ)) | max jitter in Δ W (esd(Δ)) |
|---|---|---|---|---|---|
| ftol1e-9 | 517 | 381 | ['cold', 'warm'] | 0 0 0 0 0 0 | 0 | 0 |
| ftol1e-8 | 479 | 343 | ['cold', 'warm'] | 0.007 0.02 0.072 0.045 0.056 0.026 | 0.0083 | 0.037 |
| ftol1e-6 | 419 | 283 | ['cold', 'warm'] | 0.027 0.021 0.22 0.048 0.059 0.024 | 0.019 | 0.036 |
| ftol1e-4 | 340 | 204 | ['cold', 'warm'] | 0.042 0.042 0.1 0.02 0.015 0.0098 | 0.026 | 0.016 |
| gsas | 269 | 133 | ['cold', 'warm'] | 1.3 1.2 18 0.22 0.22 2.2 | 0.95 | 0.2 |
| gsas3 | 209 | 73 | ['cold', 'warm'] | 5.7 2.6 20 11 26 2.6 | 4.9 | 5.6 |
| fp0.2 | 312 | 176 | ['cold', 'warm'] | 1.4 1 18 0.22 0.21 2.2 | 1.1 | 0.2 |
| fp0.1 | 322 | 186 | ['cold', 'warm'] | 0.041 0.032 0.071 0.04 0.027 0.014 | 0.019 | 0.028 |
| nudge0 | 499 | 363 | ['cold', 'warm'] | 0.17 0.28 0.5 0.022 0.011 0.025 | 0.13 | 0.0092 |
| nudge1 | 513 | 377 | ['cold', 'warm'] | 0.014 0.027 0.071 0.0072 0.0096 0.005 | 0.012 | 0.0043 |

### Per quantity: max single-pattern departure / max jitter in a neighbour difference, both in esd

Jitter = |Δ_k(stop) − Δ_k(1e-9)| / esd(Δ_k), Δ_k = value_{k+1} − value_k,
esd(Δ_k) = √(e_k² + e_{k+1}²) at 1e-9. `cell.b` rows omitted (they track a, or
c in the orthorhombic case).

#### cucr2o4 (phase 0 CuCr₂O₄, phase 1 CuO ≈ 1 wt%)

| stop | W[CuCr2O4] | W[CuO] | phases.0.cell.a | phases.0.cell.c | phases.1.cell.a | phases.1.cell.beta | phases.1.cell.c |
|---|---|---|---|---|---|---|---|
| ftol1e-9 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| ftol1e-8 | 0.00012 / 0.00011 | 0.00012 / 0.00011 | 0.00014 / 0.00015 | 5.4e-05 / 5.4e-05 | 0.005 / 0.004 | 0.0028 / 0.0025 | 0.0016 / 0.0011 |
| ftol1e-6 | 0.071 / 0.051 | 0.071 / 0.051 | 0.0059 / 0.0043 | 0.00035 / 0.00034 | 0.68 / 0.44 | 0.66 / 0.44 | 0.14 / 0.095 |
| ftol1e-4 | 0.22 / 0.16 | 0.22 / 0.16 | 0.012 / 0.011 | 0.0042 / 0.0028 | 1.4 / 0.84 | 1.7 / 1.2 | 0.33 / 0.37 |
| gsas | 0.25 / 0.16 | 0.25 / 0.16 | 0.3 / 0.14 | 0.014 / 0.011 | 1.8 / 0.86 | 1.4 / 1 | 0.41 / 0.32 |
| gsas3 | 0.83 / 0.34 | 0.83 / 0.34 | 11 / 3.7 | 0.081 / 0.072 | 2.2 / 0.94 | 1.9 / 1.1 | 0.63 / 0.34 |
| fp0.2 | 0.22 / 0.15 | 0.22 / 0.15 | 0.043 / 0.033 | 0.004 / 0.0032 | 1.4 / 0.77 | 1.7 / 1.2 | 0.35 / 0.44 |
| fp0.1 | 0.09 / 0.12 | 0.09 / 0.12 | 0.053 / 0.039 | 0.0095 / 0.008 | 0.8 / 0.57 | 1.2 / 1 | 0.36 / 0.33 |
| nudge0 | 1.3e-05 / 1.2e-05 | 1.3e-05 / 1.2e-05 | 4.1e-05 / 3.1e-05 | 3.2e-05 / 3.2e-05 | 0.00018 / 0.00013 | 0.00027 / 0.00024 | 0.00013 / 9.9e-05 |
| nudge1 | 1.1e-05 / 1e-05 | 1.1e-05 / 1e-05 | 4.1e-05 / 3.1e-05 | 3.1e-05 / 3.1e-05 | 0.00018 / 0.00012 | 0.00027 / 0.00023 | 0.00013 / 9.4e-05 |

#### cpd1

| stop | W[corundum] | W[fluorite] | W[zincite] | phases.0.cell.a | phases.0.cell.c | phases.1.cell.a | phases.1.cell.c | phases.2.cell.a | phases.2.cell.c |
|---|---|---|---|---|---|---|---|---|---|
| ftol1e-9 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| ftol1e-8 | 0.056 / 0.037 | 0.037 / 0.026 | 0.039 / 0.026 | 0.007 / 0.0083 | 0.0045 / 0.0046 | 0.0055 / 0.0074 | 0.0058 / 0.0071 | 0.0053 / 0.0071 | 0.0053 / 0.0071 |
| ftol1e-6 | 0.055 / 0.036 | 0.034 / 0.024 | 0.041 / 0.023 | 0.027 / 0.018 | 0.02 / 0.014 | 0.026 / 0.019 | 0.026 / 0.018 | 0.026 / 0.018 | 0.026 / 0.018 |
| ftol1e-4 | 0.018 / 0.016 | 0.014 / 0.014 | 0.011 / 0.014 | 0.032 / 0.024 | 0.028 / 0.023 | 0.042 / 0.026 | 0.042 / 0.025 | 0.034 / 0.026 | 0.034 / 0.026 |
| gsas | 0.064 / 0.052 | 0.21 / 0.17 | 0.23 / 0.2 | 1.2 / 0.89 | 1.1 / 0.84 | 1.2 / 0.94 | 1.3 / 0.95 | 1.2 / 0.91 | 1.2 / 0.91 |
| gsas3 | 7.8 / 5.4 | 7.1 / 4.4 | 5.7 / 5.6 | 5.3 / 4 | 5.3 / 4.9 | 5.3 / 4.1 | 5.2 / 4 | 5.7 / 4.8 | 5.7 / 4.8 |
| fp0.2 | 0.11 / 0.068 | 0.21 / 0.2 | 0.22 / 0.2 | 1.3 / 1 | 1.2 / 0.93 | 1.4 / 1.1 | 1.4 / 1.1 | 1.3 / 1 | 1.3 / 1 |
| fp0.1 | 0.028 / 0.027 | 0.026 / 0.025 | 0.028 / 0.028 | 0.025 / 0.019 | 0.024 / 0.012 | 0.041 / 0.018 | 0.041 / 0.016 | 0.025 / 0.017 | 0.025 / 0.017 |
| nudge0 | 0.013 / 0.0091 | 0.012 / 0.0067 | 0.0087 / 0.0092 | 0.17 / 0.13 | 0.16 / 0.12 | 0.17 / 0.13 | 0.17 / 0.13 | 0.17 / 0.13 | 0.17 / 0.13 |
| nudge1 | 0.005 / 0.003 | 0.0039 / 0.0043 | 0.0069 / 0.0026 | 0.011 / 0.01 | 0.012 / 0.012 | 0.013 / 0.011 | 0.013 / 0.011 | 0.014 / 0.012 | 0.014 / 0.012 |

### What the series tables say (measured unless marked)

- **Cost.** In a series the stop is nearly the whole bill. `cucr2o4`: 1 293
  evaluations at 1e-9 (72 a pattern in the last stage), 1 089 at 1e-8, 695 at
  1e-6, 293 at 1e-4, 183 GSAS-like, 300 FullProf 0.2, 363 FullProf 0.1. `cpd1`:
  517, 479, 419, 340, 269, 312, 322.
- **Main-phase quantities survive loose stops.** CuCr₂O₄ cell a: ≤ 0.012 esd
  departure at 1e-4, ≤ 0.053 at FullProf 0.1, 0.3 at GSAS-like; its neighbour
  steps are 10.7 esd(Δ) (median), so the jitter is ≥ 30× under the step.
- **A minor phase's cell does not.** CuO (≈ 1 wt%) cell a and β: 0.68 esd at
  1e-6, 1.4-1.7 at 1e-4 and FullProf 0.2, 1.2 at FullProf 0.1, against a floor
  of 3e-4 esd. The neighbour-difference jitter reaches 0.44 esd(Δ) at 1e-6 and
  1.2 at 1e-4. Inference: CuO's cell lies on a flat valley that the 1e-9 stage
  crawls along for ~70 evaluations a pattern.
- **A crawling stage stops in the wrong place under both foreign tests.** In
  `cpd1`, pattern cpd-1f: GSAS-like and FullProf 0.2 both stop with `axial_sl`
  at 0.0016 against 0.0388 at 1e-9 (18 esd), χ²_red 2.15 against 1.97 (9 %
  higher, 1 330 χ²), every cell 1.2-1.4 esd off, and the status says converged.
  ftol 1e-4 and FullProf 0.1 land within 0.1 esd. Inference: under LM damping
  a crawl takes short steps, so a shift/esd test passes; and it lowers χ² by
  < 0.1 % a cycle, so the GSAS-II test passes. WP-2045 recorded the same
  shape for cpd-1b at 1e-6 (`docs/wp/2045-*.md` lines 100-110, read). Hill
  (1992) said it of the round robin: termination at shifts of 30 % of the esd
  "leaves considerable scope for further improvement" (p. 10 of the PDF).
- **The series floor is not zero.** In `cpd1`, one of two 1e-12 nudges moved
  cpd-1h's `axial_sl` 0.50 esd, displacement 0.28 and zero 0.25 esd, with χ² 2.2
  higher (1.2 χ²_red). That is the path dependence the root CLAUDE.md names for
  chains; it is larger than every 1e-8, 1e-6 and 1e-4 departure in that series.
- Phase fractions: CuCr₂O₄/CuO W jitter 0.05 esd(Δ) at 1e-6, 0.16 at 1e-4 and
  GSAS-like, 0.34 GSAS-3-cycle; W esd 0.36 wt%, so 0.16 esd ≈ 0.06 wt%. cpd-1:
  ≤ 0.04 esd(Δ) at ≤ 1e-4, 0.2 at GSAS-like and FullProf 0.2, 5.6 at GSAS-3-cycle.

### Application magnitudes

| Quantity | Typical magnitude | Source | Read or recall |
|---|---|---|---|
| Thermal expansion, oxides | ≈ 5-10 × 10⁻⁶ /K (Al₂O₃ ≈ 8, MgO ≈ 13) | handbook values | recall |
| Thermal expansion, metals | ≈ 10-25 × 10⁻⁶ /K (Fe ≈ 12, Cu ≈ 17, Al ≈ 23) | handbook values | recall |
| Cell step between ramp points | CuCr₂O₄ a: median 0.0046 Å a step (≈ 600 ppm, ≈ 17 K spacing, transition included) = 10.7 esd(Δ) | this run | measured |
| Cell esd, lab | SRM 660c 3.6 ppm (1.3 raw); FAP 9-12 ppm; cpd-1 phases 50-950 ppm | this run | measured |
| Cell esd, synchrotron | NAC 3.9 ppm (0.5 raw); CuCr₂O₄ at 10 K: 8.53611(2) Å = 2.3 ppm (Suchomel et al. 2012, Table I, via `tests/data/README.md`) | this run; README | measured; read (secondary) |
| Certified cell uncertainty | SRM 660c a = 4.156882(21) Å, 5 ppm | `viz/compare.py` standard description | read (secondary) |
| In-situ phase-fraction change per pattern | ≈ 0.1-1 wt% a pattern in kinetics work | none checked | recall |
| Strain resolved in strain mapping | ≈ 1e-4 lab, ≈ 1e-5 (10 µε) synchrotron | none checked | recall |
| QPA round-robin spread, CPD-supplied data | sample 1a s.d. 0.37 (corundum 1.2 wt%), 0.40 (zincite 4 wt%), 0.54 wt% (fluorite 95 wt%) over 42 analyses; relative-bias spread at 30 wt% 5-9 % (all), 1-5 % (25-75th percentile) | Madsen et al. 2001, *J. Appl. Cryst.* 34, 409, Table 4 (p. 6 of the PDF) and Table 19 (p. 12) | read |
| QPA round-robin spread, sample 2 | CPD-supplied, 50th-percentile s.d. 0.51-0.79 wt%; all analyses 2.6-7.4 wt% | Scarlett et al. 2002, *J. Appl. Cryst.* 35, 383, sample-2 summary table (p. 6 of the PDF) | read |
| Cell spread across labs | PbSO₄ X-ray: variance ratio ℜ = σ_ext²/σ_int² = 201, 220, 292 for a, b, c, so labs scatter √ℜ = 14-17 × their own Rietveld esd; σ_ext of the mean 288-412 × 10⁻⁶ Å | Hill 1992, *J. Appl. Cryst.* 25 (doi:10.1107/S0021889892003649), Table 8 (p. 13 of the PDF) | read |
| Convergence criteria in use (1992) | shifts 1 % to 30 % of the esd | Hill 1992, Table 4 (p. 7 of the PDF) | read |

Set against those (inferred): the single-fit stop noise of ≤ 0.06 esd is
≈ 0.2 ppm on SRM 660c's 3.6 ppm cell esd, which is 0.02 K of oxide expansion
at 10⁻⁵ /K. It is 250× under Hill's inter-lab scatter (14-17 esd). On QPA, the
1e-4 series jitter (0.06 wt%) is 6-9× under the round robin's best-case
spread (0.37-0.54 wt%). The CuO cell's 1.7 esd at 1e-4 is 0.005 Å; CuO's own
esd is 660 ppm, which is ~66 K of expansion, so nothing anyone resolves on that
phase moves, but the 0.1-esd bar is broken by 17×.
## Part 3 — rietx's own χ²-based decisions against the loose-stop ΔS

How a stop's ΔS enters each statistic (inferred from the formulas, quoted
from source): with S the unreduced χ², χ²_red = S/(N−P) and f the
Bérar-Lelann factor, a one-parameter Hamilton F is ΔS/χ²_red (raw N) or
ΔS/(χ²_red·f²) (N_eff); ΔBIC is ΔS/χ²_red − k ln N (raw) or
ΔS/(χ²_red f²) − k ln N_eff; a χ² ratio moves by ΔS/S. So the column
"stop noise" below is ΔS/χ²_red from part 1 (solver's own model), or ΔS/S for
the ratio tests.

Stop noise measured in part 1, solver's own S, worst over the five single-fit
fixtures: 1e-6 → ≤ 0.0013 χ²_red; 1e-4 → ≤ 0.0097 χ²_red; GSAS-like → ≤ 0.058
χ²_red; FullProf 0.2 → ≤ 0.056 χ²_red. As ΔS/S: ≤ 3e-7 (1e-6), ≤ 1.3e-6
(1e-4), ≤ 8e-6 (GSAS-like). **But** the reported χ² differs from the solver's
by the recompile gap, 0.2-2.1 χ²_red at the answer, and that gap itself moves
by up to 0.1 χ²_red between two nearby answers (FAP 2.13-2.42 χ², NAC
−2.54 to −3.82 χ²). In the series, a stop that leaves a fit mid-crawl moves
one pattern's S by up to 0.19 χ²_red·(N−P) = 1 330 χ² (cpd-1f, GSAS-like and
FullProf 0.2).

| Decision (source) | Threshold | Typical margin (source) | Stop noise vs threshold | Flips? |
|---|---|---|---|---|
| Hamilton F, `report.layer2.hamilton_justified` (α 0.05; body_misfit α 0.001; extinction screen raw N) | F > F_crit(k, N−P): 3.84 for k = 1 at 5 %, 10.8 at 0.1 % | none measured here; any case within ±δF of F_crit is at risk | δF ≤ 0.0013 (1e-6), ≤ 0.01 (1e-4), ≤ 0.06 (GSAS/FP0.2) on raw N; smaller by f² (1.3-65) at N_eff | single fit: no, except a case within 1.5 % of F_crit (GSAS-like); a crawling series member: yes |
| ΔBIC: `compare_freed`, distortion, body_misfit (`MISFIT_BIC` 10), extinction (`DECISIVE_DELTA_BIC` 10, raw N), magnetic ties (6, 10), suggestion prediction, peak components (6) | 6 or 10 | #270 (layer2 docstring, read): raw-N ΔBIC +36 to +211 that N_eff turned negative; extinction "very strong" > 10 (Kass & Raftery 1995, quoted in source) | ≤ 0.06 at the loosest stop | no (≥ 100× margin) |
| Rival-model χ² ratio, `RIVAL_DECISIVE_MIN_CHI2_RATIO` | ratio ≥ 1.10 decisive; tie band [0.99, 1.01] | SRM 660c knocked displacement 1.1679; ties 1.0075 and 1.0001 (source docstring, read) | ΔS/S ≤ 8e-6 | no |
| Profile intervals, `schemas.interval` | Δχ² = 3.84 at 95 %, scaled by χ²_red·f² (BT-1: threshold 30.3, read; scaling inferred from `FRACTION_PROFILE_DCHI2`'s docstring); settle test `PARAMETER_INTERVAL_CHI2_TOL` = 1 % of threshold | windows alternate between compiles 0.2-3 χ² apart (docstring, read) | each probe is a refit: ΔS ≤ 0.06 χ²_red against a settle tolerance of 0.038·f² χ²_red, i.e. 0.049 χ²_red at white noise (f = 1.13) | **GSAS-like and FP0.2 noise-dominated** at f ≲ 1.5; 1e-4 at 20 % of the tolerance; 1e-6 safe |
| Phase significance, `_answer_significance` / `PHASE_UNCONSTRAINED` (`PHASE_SUPPORT_SIGMA` 3) | scale ≥ 3 esd | cpd-1a corundum (1.15 wt%) 9.0 σ raw esd (2.7 at inflated esd); NAC CaF₂ 93 σ (measured) | z moves ≤ 0.1 at every stop (measured, cpd-1a) | no, unless a phase sits within 0.1 σ of 3 |
| Suggestion verify, `predict_then_verify` | χ²_red falls by > 1 % | none measured | ΔS/S ≤ 8e-6 (single); 9 % on a crawling series member | no on a single fit |
| Le Bail gap, `LEBAIL_GAP_NOTABLE` | ratio ≥ 1.5 | 2.36 pore proxy vs ≤ 1.00 controls (docstring, read) | ≤ 1e-5 relative | no |
| `FROZEN_COMPILE_CHI2_REL` | as-optimised vs recompiled χ² differ > 1 % | measured gap 0.003-0.04 % (part 1) | ≤ 1e-5 relative | no |
| `SLOW_DESCENT_ESD` (lm.py) | stop when the next 300 evaluations would buy < 1²·χ²_red | is itself a stop: concedes up to 1 esd of joint travel; fires only past 100 evaluations | — | — |
| Moment-angle Λ test (WP-1929) | Λ = Δχ²/(χ²_red f²) vs χ² 95 % point | not measured | as Hamilton at N_eff | no on a single fit |
| Indexing `CELL_EQUALITY_CHI2` 16.81 | χ² of a cell difference in esd units | not a fit χ² | cell moves ≤ 0.03 esd (single fit) | no |

## Recommendation (inferred from the measurements above)

- **Keep the package's own test, three consecutive relative decreases under
  `ftol`.** Do not replace it with the GSAS-II single-cycle test or a FullProf
  shift/esd test. Both foreign tests stopped cpd-1f mid-crawl, 18 esd from the
  answer, reporting converged. A shift/esd test is only safe *in conjunction*
  with the `ftol` rule.
- **Single fit, last stage: 1e-6 meets the 0.1-esd bar** with ≥ 13× margin on all
  five fixtures (worst 0.0075 reported esd, 0.013 raw). 1e-4 also meets it
  (≤ 0.016 reported, ≤ 0.054 raw). Either buys little: 0-9 % (1e-6) or 4-12 %
  (1e-4) of a fit's evaluations, since the earlier stages dominate.
- **A series' warm rungs need a tighter stop: 1e-9, or 1e-8 at the loosest.**
  A warm pattern runs only the last stage, so there the stop is the cost
  (1e-6 halves `cucr2o4`'s 1 293 evaluations). At 1e-6 the 1-wt% CuO cell sits
  0.68 esd off and its neighbour differences jitter 0.44 esd(Δ). That is 7×
  and 4× the bar. At 1e-8 it is 0.005 esd. That is the carve-out the data
  support: a minor phase's cell along a chain.
- **Profile-interval refits need a tight stop.** Their settle test is 1 % of
  the Δχ² threshold, 0.049 χ²_red at white residuals. The GSAS-like and
  FullProf 0.2 stops leave up to 0.058 χ²_red, which is at or above that
  tolerance. 1e-6 leaves 0.0013.
- **The decision carve-out is not needed on χ² grounds.** Every other χ²-based
  threshold has ≥ 100× margin over a single fit's stop ΔS. The exception is a
  case sitting within ~1.5 % of an F or Λ cut. The reported χ² already carries
  0.2-2 χ²_red of recompile gap, which moves 0.1 χ²_red between nearby answers.
- **The bar is already broken by path dependence, not by the stop.** On the
  large cell, 2 of 5 nudges of 1e-12 reach another minimum with O coordinates
  4.3 esd away. In `cpd1`, one nudge moved axial_sl 0.5 esd. A tolerance study
  cannot fix either.

## Not measured

- The three compounding places WP-2222 keeps tight: a Pawley series carrying
  intensities, `lab_calibrate`, and the guides. Nor a Le Bail or Pawley single
  fit: the large cell ran only `bigcell-structural`.
- The mechanism of the recompile gap.
- Thermal expansion, in-situ fraction steps and strain-mapping resolution are
  recall. Journal volume and page numbers for Madsen 2001 (34, 409) and
  Scarlett 2002 (35, 383) are recall too; table and PDF page numbers were
  read from the papers via `paper-reader`.
