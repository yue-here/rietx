# WP-1955 — a column at a zero aperture, and a column the agreement matrix cannot see

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-26 — two measurements the same day: WP-2003's double-zero aperture collapsing a warm-started CPD fit (Rwp 0.79-10.7 against 0.109), and #1075's LM ending converged at S/L = H/L = 0 on lab_bragg_brentano from defaults while one TRF stage drops χ² by ~1 200 χ²_red·f²; the single-zero column is still off its difference with no test

## Goal

The numpy analytic `axial_hl` column at H/L = 0 matches the feasible side's
one-sided difference, as the jax and torch columns already do. The
cross-backend agreement matrix checks a small column at its own scale, so a
column tiny beside the largest is checked rather than skipped. Whether the
column error moved any reported number is measured and written down.

## Context

**Where it came from.** WP-1953's second session (2026-10-12, PR #918), two
review findings it declined because they reach beyond that WP. Measured there
on macOS arm64, `[dev,jax,torch]`, Python 3.12.10.

**The column.** WP-1953 made one FCJ aperture at 0 the h → 0⁺ limit, so LM's
exact bounded step now lands H/L on 0 (`fcj.fcj_live`, `test_e8`'s verify
stage). On `test_cross_backend.py`'s `axial_one_zero` config the `axial_hl`
column at H/L = 0 has a one-sided central difference of norm 0.04696. jax and
torch meet it to rel-L2 1.5e-3
(`test_a_zero_aperture_column_meets_its_one_sided_difference`). The numpy
analytic column has norm 0.0486 and sits 0.240 rel-L2 off the same reference.
No test checks the numpy column there. The fix the review named changes how
`model/forward.py` differences the FCJ nodes at a bound, so it moves every fit
that frees an axial ratio from 0.

**Why it can matter.** A row on its bound stays in the covariance (root
CLAUDE.md, the equilibrated normal matrix, WP-1929), so the esds of S/L and its
neighbours at H/L = 0 read this column. The bound test reads the residual's
cosine with it (`LSQOutcome.residual_cosine`, WP-1434). Neither consequence is
measured.

**The matrix's cut.** `test_cross_backend.py` treats a column as dead when its
norm is under `DEAD_COL_FRAC` (1e-6) of the largest column. The axial column at
H/L = 0 is 0.047 against a largest of 1.82e6, so every backend row skips it.
That is why the traced columns' error (a jax column of norm 3360 against the
reference's 0.047, from a tie at the FCJ kink) went
unseen until CI's jax job hit a different config, and why #918 added a
dedicated test. Any column small beside the largest escapes the same way: a
moment angle near a fixed direction, a weak phase, a parameter in small units.
WP-1953 found a third of all fast-suite LM solves start with a column under
1e-6 of the largest.

**A sibling not probed.** `caglioti.py`'s `xp.maximum(g2, _MIN_GAMMA_G2)` ties
when U and V are both zero beside W on its floor. It is the only other
`minimum` or `maximum` on the traced path found sitting on a bound LM lands on.
`sharp_widths` covers W on its floor with U and V nonzero.

### Inherited

- **From WP-2003 (2026-10-26): both apertures at 0 cost an answer, not only an esd.** CPD
  sample 1b fitted independently under `qpa_plan()` ends with S/L and H/L both on their
  floors at 0 (S/L esd 251). A warm refit of 1c from that state collapses: Rwp 10.724 with
  the closing stage off, 0.791 with it on (S/L to 64.8 and 4284, `STAGE_WINDOWS_STALE`),
  against the independent 1c's 0.10901. The same start with S/L lifted to 0.011 converges at
  0.10881 in 39 evaluations. Reading: the column at the double zero is nearly flat, the first
  LM step is tens to thousands of units, and the windows sized from `AXIAL_SIZING_FLOOR` at
  compile are stale for the rest of the solve. The default CPD chain escapes only because its
  own 1b ends off the floor. Measurement and reproduction: `docs/wp/2003-batch/clashes.md`
  X17 (`measure_reseed.py --family cpd-noclose --arm status_runaway`, and the probe it
  describes). A remedy is this WP's shape one rank out, WP-1938's rule: a floor or a lift where
  the column is live, and it moves every fit that frees an aperture from 0.

- **2026-10-26 issue triage: #1075 repro 1, LM stops with both axial ratios at 0
  on `lab_bragg_brentano` from the constructor's defaults, and calls it
  converged.** Checked against the tree at c0e32ab29 (1.11.0.dev0, macOS arm64,
  numpy), the issue's script with `auto_background(...).background`: Si, Cu Kα,
  truth S/L 0.035, H/L 0.025, transparency 0.0005 (not refined by the plan),
  seed 1. The fit ends `converged`, Rwp 0.0834, S/L = H/L = 0.0 ± 103.8,
  `at_bound` True, `FLOOR_HIT` (plus `FLAT_DIRECTION`, `HIGH_CORRELATION`,
  `RESOLUTION_UNCONSTRAINED`). One more LM stage moves nothing; one TRF stage
  over the same free set reaches Rwp 0.0454 with 0.0329/0.0267, Δχ² −15 905 =
  −1 198 χ²_red·f²; LM from 1e-4 stops at 8e-5. `profile_interval` on S/L
  returns [0.0, 0.0] with `fit_is_minimum=True`. Since the issue's run on
  `d885ade2` the bound flag has started firing, and the profile has stopped
  noticing. Mechanism (the reporter's): the FCJ shift is quadratic in the
  apertures, so both columns are ~1e-6 of the largest at 0, the same scale this
  WP's matrix cut skips, and the way down is a joint move with zero,
  displacement and the widths that Gauss–Newton cannot see from a vanishing
  column. Without the transparency LM left 0 in 42 of 42 fits. This is the
  driver's handling of a small column, which this WP's non-goals give to
  WP-1953; 1953 is closed and its fix does not reach this case, so it lands
  here. Re-rated P3 → P2.

## Non-goals

- The FCJ limit itself and the traced kink: shipped in WP-1953 (#918).
- The LM driver's handling of a small column: WP-1953 (#923).

## Tasks

- [ ] Measure the numpy analytic `axial_hl` and `axial_sl` columns at one
      zero aperture against the one-sided difference, and find the line in
      `model/forward.py` where the node differencing departs from it. A test
      that fails on `main`.
- [ ] Fix it, and re-measure the fits that free one aperture from 0:
      `test_e8`, QPA cpd-1a's `lines_axial` stage, the Stephens brucite
      protocol. Record the esds of S/L before and after.
- [ ] The dead-column cut: count the configs whose columns fall under
      `DEAD_COL_FRAC`, and decide whether the matrix checks such a column
      against its own difference at its own scale, as the zero-aperture test
      does. Record it as `Decided YYYY-MM-DD:`.
- [ ] Probe the Caglioti tie: U = V = 0 with W on its floor, traced against
      numpy.

## Acceptance

The numpy, jax and torch `axial_hl` columns at H/L = 0 meet the one-sided
difference under one bar, and no backend row skips a live column for its size
alone.

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_lab_instrument.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1953 (the FCJ limit, the traced kink, the curvature rule) and its second
  session's handover entry.
- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.*
  **27**, 892-900.

## Handover log

- **2026-10-13** — Filed from WP-1953's close. No open WP owns it: 1467 is a
  Stephens clamp, and the WPs citing the agreement matrix are magnetic,
  rigid-body and test-tier work. The two findings combine because both are a
  column tiny beside the largest, on one test file.
