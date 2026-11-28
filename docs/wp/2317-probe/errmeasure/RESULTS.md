# How to read a speed setting's error against the 0.1-esd bar — WP-2317 probe

**Tree:** detached at `wp2317-rulings` (`680025e6a`). Large-cell fixture copied from
`main` `0b3e5c42b` into `bigcell/` (`tests/test_large_cell_refinement.py`,
`cod_2107344.cif`). **Venv:** the worktree's `.venv`, `[dev]`, CPython 3.12 arm64,
rietx 1.13.0.dev0 editable, `RIETX_COMPILED_THREADS=2`, telemetry off.
**Platform:** Darwin 25.6.0 arm64, shared machine (load 5-100 during the runs; walls
not comparable). Nothing in `src/` changed. 659 single fits (3.5 h of summed fit
wall) and 44 cpd-1 series runs.

Scripts: `run.py` (one fit per fixture × setting × seed), `run2.py` (+ the `refit`
injection and the `bigcellT` fixture), `series_run.py`, `analyse.py`,
`analyse_series.py`, `series_mean.py`, `basin_split.py`, `analyse_T.py`,
`probe_cosited.py`. Tables: `tables.txt`, `tables_series.txt`,
`tables_series_mean.txt`, `tables_basin_split.txt`, `tables_bigcellT.txt`. Raw JSON
in `results/` (not committed). Plots: `tests/output/errmeasure_*.png`.

## Method

- Fixtures, nudge and stop wrapper are `../convnoise`'s (its Method section).
  Nudge: every model `Parameter` × (1 + 1e-12·u), u ~ U[−1, 1], `default_rng(seed)`,
  structure then instrument. Seeds 0-19 for the reference, 0-9 for each setting.
- Units: |Δ| / esd, the esd the reference setting's **unnudged** fit reports
  (Bérar-Lelann-inflated), per parameter; QPA fractions as W/esd(W). Atom
  coordinate DOF rows are dropped (they are steps from each fit's own start,
  WP-1333); the coordinate rows are kept.
- Readings of setting S against reference R on one fixture:
  - **naive**: max_p |v_S(none) − v_R(none)| / e_p.
  - **floor_sub**: F_p = max over K nudged R reruns of |v_R(k) − v_R(none)| / e_p;
    reading max_p max(0, d_p − F_p). **floor_cmp**: pass iff d_p ≤ max(0.1, F_p) for
    all p. **floor_glob**: naive − max_p F_p (the "global" form).
  - **paired**: K pairs (S, k) / (R, k) with the same seed; basins are
    single-linkage clusters (0.5 esd, max-norm) of R's 11-21 answers, a candidate is
    assigned by the coordinates that separate clusters by > 1 esd; shift_k =
    max_p |v_S(k) − v_R(k)| / e_p over same-basin pairs; reported max / median / min
    and the split count.
  - **paired-mean** (added after the series control): per quantity, the mean of the
    signed paired shifts over K pairs, with its standard error.
- Settings. Stops (R = shipped plan): last-stage `ftol` 1e-6, 1e-3, 1e-2, 1e-1; the
  GSAS-II-like stop. Windows (R = `closing_window_tol` 1e-3, the closing stage on
  for all fixtures; it is off by default since WP-2222, on in cpd1a's `qpa_plan`):
  1e-2, 1e-1, and None (no closing stage, the 2 % declared-stage windows).

## Measured: bigcell's "two minima" are two models

The bigcell fixture's `co_sited()` rounds coordinates to 1e-4 to decide which atoms
share a site. W8 (atom 23) and Nb8 (atom 27) sit at x = 0.42515, exactly on a
rounding boundary, so the 1e-12 nudge alone decides whether they are tied
(`probe_cosited.py`: tied for seeds none, 0, 1, 3; untied for 2, 4, 6, 10).
Untied, the fit has 120 free parameters instead of 117, S is 1.49 lower
(8104.87 vs 8106.36) and χ²_red is higher (1.962438 vs 1.961374, since N−P falls).
The "separating coordinates" convnoise called O23/O27 are W8/Nb8 x and y,
3.0-4.3 esd apart because a co-sited pair left free walks the near-flat direction
`tie_co_sited`'s docstring warns of. With the ties decided on the unnudged start
(`bigcellT`), the floor is ≤ 4.5e-6 esd and there is one minimum. No fixture shows
two minima of one model in a single fit.

## M1 — floor vs K, shipped settings (max departure, reported esd)

| fixture | K = 3 | 5 | 10 | 20 | P90 of per-seed worst, K = 3/5/10 | minima |
|---|---|---|---|---|---|---|
| srm660c | 1.9e-7 | 2.0e-7 | 2.3e-7 | 2.3e-7 | ≤ 2e-7 | 1 |
| fap | 4.9e-8 | 5.2e-8 | 1.0e-7 | 1.0e-7 | ≤ 9e-8 | 1 |
| nac | 1.2e-7 | 1.2e-7 | 1.4e-7 | 1.4e-7 | ≤ 1.3e-7 | 1 |
| cpd1a | 1.4e-6 | 1.4e-6 | 1.4e-6 | 1.5e-6 | ≤ 1.3e-6 | 1 |
| bigcell (as shipped) | 4.34 | 4.34 | 4.34 | 4.34 | 3.47 / 4.34 / 4.34 | 2 models, 13 + 8 of 21 starts |
| bigcellT (ties fixed) | 1.9e-6 | 4.5e-6 | 4.5e-6 | — | ≤ 3.4e-6 | 1 |
| cpd-1 series (8 patterns) | 0.504 | 0.504 | 0.504 | — | 0.445 / 0.386 / 0.239 | 1 cluster (one model) |

Series per-seed worst departures (seeds 0-9): 0.50, 0.07, 0.21, 0.21, 0.06, 0.10,
0.07, 0.016, 0.07, 0.001 esd, worst on cpd-1h `axial_sl` or `profile.v`. The max is
stable from K = 3 here only because seed 0 is the outlier; 1 start in 10 reaches
0.5 esd, 3 in 10 exceed 0.2 (measured). Inferred: a K = 3 floor misses the
0.5-esd tail with probability ≈ 0.7.

## M2 — readings, K = 5 (K = 10 gives the same verdicts)

Single fits. Values are the worst quantity in esd; background coefficients
included / excluded.

| setting | srm660c | fap | nac | cpd1a | bigcell | all readings agree? |
|---|---|---|---|---|---|---|
| ftol 1e-6 | 0 | 0.0004 | 0.0005 | 0.0027 | 0.0075 | yes, pass |
| GSAS-like | 0.046 | 0.044 | 0.027 | 0.058 | 0.009 | yes, pass |
| ftol 1e-3 | 0.026 | 0.0047 | 0.0037 | 0.016 | 0.0075 | yes, pass |
| ftol 1e-1 | 0.034 | 0.015 | 0.010 | 0.031 | 0.0075 | yes, pass |
| window 1e-2 | 0.46 / 0.047 | 1.31 / 0.052 | 0.29 / 0.010 | 0.69 / 0.18 | 1.63 / 0.46 | no: floor_glob passes bigcell |
| window 1e-1 | 6.0 / 1.03 | 5.5 / 1.82 | 0.41 / 0.032 | 2.4 / 0.52 | 7.2 / 3.1 | yes, fail |
| window None | 0.72 / 0.098 | 2.25 / 0.42 | 0.35 / 0.019 | 1.30 / 0.31 | 3.0 / 0.74 | no: floor_glob passes bigcell |

- On srm660c, fap, nac and cpd1a the floor is ≤ 1.5e-6 esd, so naive, floor_sub,
  floor_cmp, floor_glob and paired return the same number to 1e-6 (measured).
- No ftol, down to 1e-1, produces a ≥ 0.3-esd single-fit error: the last stage
  of a staged plan starts near the answer, and ftol 1e-1 moved no quantity more
  than 0.034 esd (measured; the mechanism is inferred). The ≥ 0.3 single-fit errors
  here are the window settings.
- The window error lands mostly in the background (c0, c2, c3: 0.29-7.2 esd);
  without the background it is 0.01-3.1 esd (worst Biso, lor_size, profile X, a
  scale). The fit plots are indistinguishable by eye (bigcell window 1e-1 has
  7.2 esd on c0 and Rwp 0.0365 against 0.0352).
- **bigcell** (shipped fixture, floor 4.0-4.3 esd on W8/Nb8): floor_glob passes
  window 1e-2 (1.63 esd) and window None (3.0 esd). floor_sub and floor_cmp fail
  them, through parameters outside the W8/Nb8 band. Split by model
  (`tables_basin_split.txt`), window 1e-2 moves Nb8 x by +0.002 esd in the
  117-parameter pairs and −0.63 in the 120-parameter pairs; window None moves W8 y
  −0.20 and −1.05. naive (unnudged start, 117 model) sees the first number only;
  floor_sub on that parameter sees nothing (F = 3.0-4.3); paired sees both.
- **Split pairs: 0** in every setting × fixture (single fits, bigcell and the
  series). The seed fixes the model and the path; no last-stage setting moved a
  start into the other model.

cpd-1 series (R = ftol 1e-9 shipped, K = 5 and 10; worst quantity over 8 patterns):

| setting | naive | floor_sub | floor_glob | paired max / median / min | paired-mean, K = 11 (se) |
|---|---|---|---|---|---|
| GSAS-like | 18 FAIL | 18 FAIL | 17.5 FAIL | 18 / 18 / 18 FAIL | −18.0 (0.001), 52 quantities > 0.1 |
| ftol 1e-6 | 0.216 FAIL | 0.102 FAIL | **0 PASS** | 0.41 / 0.22 / 0.11 FAIL | −0.168 (0.030), 3 quantities > 0.1 and > 2 se |
| numpy tier (true effect ≈ 0) | 0.071 pass | 0 pass | 0 pass | **0.35 / 0.07 / 0.056 FAIL** | +0.039 (0.033), 0 quantities |

The numpy-tier control is the shipped settings with `RIETX_COMPILED=0`: the same
model, arithmetic differing at a rounding bound. Its paired shifts reach 0.35 esd
(4 of 11 pairs over 0.1), from the path dependence alone. ftol 1e-6's single-pair
shifts (0.11-0.41) overlap them. The **mean** of the paired shifts separates the
two: ftol 1e-6 has 3 quantities with |mean| > 0.1 esd and > 2 se, the control none.

## M3 — injected error on bigcell

`refit@<DOF>@0.4`: after the shipped fit, set one coordinate to its own answer
+ 0.4 esd through its DOF, hold it, and re-solve once with every glob the plan
freed (2 % windows). Reference: the same two-step fit with nothing held. The
injected error is 0.4000 esd on the held coordinate in every start (measured).
The held path leaves `RefinementResult.parameters` (WP-1999); its value is rebuilt
from the first fit plus the recorded move.

| injected | its floor F_p | naive | floor_sub (on it / overall) | floor_glob | paired, every pair | split |
|---|---|---|---|---|---|---|
| W8 x +0.4 (atom 23) | 3.02 | 0.40 FAIL | **0 pass** / 0.19 FAIL (via atom 4 Biso, dragged 0.20) | **0 pass** | 0.399-0.400 FAIL | 0 / 10 |
| atom 4 y +0.4 | 0.098 | 0.40 FAIL | 0.30 FAIL | **0 pass** | 0.399-0.400 FAIL | 0 / 10 |

An O27 injection was dropped: in the 117-parameter model Nb8 follows W8 by tie.

## M4 — direction

- Per (setting, fixture, cell parameter) the sign of the paired shift is the same
  in 11 of 11 pairs, and the size is identical to 3 digits (single fits). The one
  exception is bigcell window 1e-1, cell b: 8 of 11 positive, the sign depending on
  the model. Across fixtures the sign is not shared: window 1e-2 moves SRM 660c and
  FAP cells up, NAC phase 0 and every cpd-1a cell down, bigcell a and b up and c
  down (measured). So the direction is systematic per setting and specimen, not a
  property of the setting.
- SRM 660c: the shipped answer is a = 4.1568836(149) Å, 0.38 ppm above the
  certificate 4.156882(21) Å: +0.11 esd, +0.08 of the certificate's uncertainty
  (5.1 ppm = 1.4 esd). Moves inside 0.1 esd: 66, 22 of them (33 %) further from
  the certificate. Moves outside 0.1 esd: 11 (window 1e-1, +0.33 esd), all further.
  "Further" is exactly the set of upward moves, because the answer sits above the
  certificate (measured).
- Inferred: a move inside the bar is ≤ 0.36 ppm, 0.07 of the certificate's
  uncertainty. Deciding at 2σ of the certificate whether a move approaches the
  true cell needs a move of about 10 ppm, 2.9 esd. The certificate cannot decide a
  direction inside the bar, and no other fixture carries a reference value tighter
  than its esd (cpd-1a's weighed composition: not checked here).

## Answers

1. **Floor stability** (measured): on single fits the floor is ≤ 4.5e-6 esd at every
   K once the bigcell tie defect is removed; K = 3 is enough to see that. In the
   series it is 0.5 esd, carried by 1 start in 10, so K = 3 estimates it badly.
2. **Verdicts** (measured): every reading gives the right verdict on the four clean
   single fixtures. floor_glob lets ≥ 0.3-esd errors pass: bigcell window 1e-2
   (1.63), window None (3.0), both injections (0.4), series ftol 1e-6 (0.22-0.41).
   floor_sub lets the 0.4-esd injection on W8 x pass on that parameter. naive reads
   one start: it misses the 0.63- and 1.05-esd W8/Nb8 errors that exist only in the
   other model's pairs, and in the series it reads one draw of 0.07-0.35.
3. **R-paired** closes R-floor's hole wherever the pair's fits share a model and a
   path (single fits; 0 splits in every case). Taken as a max over pairs it fails
   a zero-effect change in a path-dependent series (0.35 esd). Its **mean** over
   pairs, against its standard error, passes the control and fails ftol 1e-6 and
   the GSAS-like stop there.
4. **Direction** inside the bar carries no information about accuracy here: it is
   a fixed sign per setting and specimen, and the certificate's 5 ppm is 14 times
   the bar.

## Defect noticed, not fixed

`tests/test_large_cell_refinement.py::co_sited` (on `main`) rounds to 4 decimals,
and W8/Nb8 sit on a half-way value, so the tie set depends on the 13th digit of the
coordinates. convnoise's RESULTS reads this as "a second minimum" with "O23/O27";
both readings are wrong (measured above). Deciding co-siting by a tolerance
(|Δx| < 1e-4) instead of by rounding would remove it (inferred).

The raw `results/*.json` (7.8 MB) are not committed; the scripts rebuild them.
