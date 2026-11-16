# WP-1974 — the texture screen says which order the misfit needs

Milestone: unscheduled · Status: 🔄 2026-11-16 — tasks 1-2 measured (PR #1604); task 3 waits on the maintainer's thresholds
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1960 (the basis)
Priority: P3 2026-10-15 — a workaround covers it: declare orders 4, 6 and 8 by hand and compare the fits

## Goal

After a fit with no texture block, the FitReport says how much of the
intensity misfit a spherical-harmonics texture of each order would explain.
So an order is chosen from the data, before any refit.

## Context

### What exists

`report/texture.py` is the Layer-1 March-Dollase screen. It extracts a
per-reflection correction f_k from the residual, a Le Bail-style partition
splitting overlaps by calculated share. It then scores each candidate axis by

    R² = 1 − Σ_k w_k (f_k − P_k)² / Σ_k w_k (f_k − 1)²

with w_k the reflection's calculated area. It runs outside the maturity gate,
because uncorrected texture is a common cause of an immature fit.

WP-1960's P is affine in its coefficients, so f_k − 1 ≈ Σ_t w_l·C_t·K_t(h_k).
Each order is then one weighted linear solve on the same f_k, and its R²
compares directly with an axis's. The pieces are public:
`crystallography.spherical_harmonics.texture_basis(sg, order, cell)
.at_reflections(hkl, cell)` for K, and
`model.preferred_orientation.texture_term_weights(degrees,
TEXTURE_SAMPLE_PSI_DEG[geometry.kind])` for w_l.

### What constrains the design

- **Terms grow fast.** −1 has 14 at order 4 and 44 at order 8. A raw R² always
  rises with the order, so each added order is a nested comparison, the rule
  Layer 1 already follows for collinear templates.
- **Some terms are invisible to the partition.** Reflections the Laue class
  leaves inequivalent but the metric puts at one position (hkl and khl in
  −3m1) take opposite signs on a term like c4_3. The partition gives both the
  same f, so that term explains nothing here. WP-1960 measured the same term at
  0.93 ± 22.7 in a refit. The screen must not suggest it.
- **March-Dollase is one parameter.** On CPD-2 brucite (WP-1960) the worst
  weighed-fraction error was 2.80 wt % under March-Dollase, 3.41 at order 4
  and 2.71 at order 6. A screen that prefers an order where one axis explains
  as much is wrong. *Superseded in part 2026-11-16:* on main at `bc77a934e`
  (darwin/arm64, `[dev]`) the same protocol reads 3.01 under March-Dollase
  (r = 0.668), 3.71 at order 4, 2.91 at order 6 and 3.60 at order 8, the
  1.10.0 numbers `test_sample2_brucite_spherical_harmonics` already quotes.
  The order is unchanged: order 6 just ahead of the axis, order 4 behind it.
- **A suggestion passes the FitReport's four gates**, and is never a confident
  wrong singleton (root CLAUDE.md).

## Non-goals

- Refitting each order. A stage does that.
- Positivity of a suggested set. The fit's guard owns it
  (`TEXTURE_NOT_POSITIVE`).
- The pole-figure render (WP-1318's sampler, `sphere_points`).

## Tasks

- [x] The per-order solve beside the axis score, on the fit's frozen cell.
      *2026-11-16:* `report.texture._order_screen`, private and called by
      nothing, so no report moves. It fits f_k ≈ a + Σ_t b_t·(M·w_l K_t)_k,
      M the extraction's own partition (`_partitioned`, the extraction
      applied to the phase's peaks times K), on the axis score's baseline;
      C_t = b_t/a. The rank is read on columns scaled to their unpartitioned
      norm, and each term's visibility ‖M·K_t‖/‖K_t‖ rides beside it.
      Measured in the handover entry; three tests in `tests/test_texture.py`.
- [ ] The nested comparison per added order, and the record field it writes,
      with its writer named. *2026-11-16, half done:* the comparison is in
      `_order_screen` and measured (handover entry): per order, the F
      statistic and p on the rank the order adds, ΔBIC = n·ln(SS_hi/SS_lo) +
      Δp·ln n, ΔBIC against the best March-Dollase axis at one shape
      parameter, and rms(P − 1) as the strength. The field is **proposed, not
      added**, since a report-schema change is the maintainer's: see the
      handover entry's questions.
- [ ] The Layer-2 action naming an order, only past the gates. The
      March-Dollase action stays where an axis explains as much.
- [ ] Tests: an order-4 specimen fitted bare suggests 4, a March-Dollase one
      still suggests an axis, a random powder suggests nothing, and CPD-2
      brucite is the real case. PNGs to `tests/output/`.
- [ ] Manual: the screen's section in Part 1, and Part 2 if the comparison is
      new arithmetic.
- [ ] Skill: `numbers.md`'s `refine_preferred_orientation` row, which routes
      between March-Dollase and an order today.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_texture.py tests/test_preferred_orientation.py tests/test_fitreport_layers.py
.venv/bin/python -m ruff check src tests examples
```

The bar: the three synthetic cases above suggest what they were built with,
and CPD-2 brucite's suggestion is reported beside its weighed-fraction errors.

## References

- Von Dreele, R. B. (1997). *J. Appl. Cryst.* 30, 517-525.
- Dollase, W. A. (1986). *J. Appl. Cryst.* 19, 267.
- WP-1960, the basis and the CPD-2 numbers.

## Handover log

- **2026-11-16** — tasks 1 and 2 measured; PR #1604. The order screen works
  where it can see the reflections. Fitted bare, built order-4 and order-6
  specimens pick their own order, March-Dollase ones keep their axis in two
  of three cases, and random powders pick nothing. The coefficients come back
  to about 1 % when noise-free. On CPD-2 brucite the screen sees order 4
  clearly beside its axis, but only when brucite's Biso is held. The QPA
  protocol frees it, and the Biso then runs to 22 Å² and hides all but seven
  reflections from both screens. Nothing reaches a report yet: no threshold,
  record field or action is decided here. Those are the maintainer's, and the
  questions are below.

  - **Done.** `report.texture._order_screen` (private; nothing calls it) and
    its partition `_partitioned`. Tests in `tests/test_texture.py`: the
    built order-4 specimen, a term the partition averages away, a random
    powder's amplitude, and the rank tolerance's gap over seven phases.
    `_ORDER_RANK_TOL` has a tier-1 `_audit` row. Task 2 is half done: the
    comparison is in, the field only proposed (questions).
  - **Measured** (darwin/arm64, `[dev]`, on main `bc77a934e`; probes and logs
    in the runner's scratch, not committed). Synthetic phases fitted bare
    (scale and background) under Poisson noise, screened at the report's
    windows (`WINDOW_AREA_TOL`):

    | specimen | R² by order 2/4/6/8 | F p of the order that adds | ΔBIC vs axis | axis R² |
    |---|---|---|---|---|
    | order 4, −3m1 | .771/.988/.988/.989 | 4: 1e-19; 6: 0.70 | 4: −56 | .920 (1,−1,0) |
    | order 4, mmm | .191/.974/.975/.976 | 4: 1e-62; 6: 0.79 | 4: −257 | .454 |
    | order 4, m-3m | —/.962/.964/.964 | 4: 2e-16; 6: 0.30 | 4: −18 | .915 |
    | order 6, −3m1 | .713/.913/.988/.989 | 6: 9e-12; 8: 0.56 | 6: −73 | .829 |
    | MD r 0.6 (001), −3m1 | .850/.991/.997/.998 | 8: 0.41 | +133/+46/+16/+23 | .997 (0,0,1) |
    | MD r 0.8 (001), −3m1 | .948/.992/.992/.993 | 6: 0.96 | 4: **−2.9** | .990 (0,0,1) |
    | MD r 0.7 (100), mmm | .861/.977/.994/.995 | 8: 0.046 | +274/+124/+20/+29 | .993 (1,0,0) |
    | random −3m1 / mmm / m-3m | ≤ .16 / ≤ .04 / ≤ .07 | all > 0.24 | all > −0.2 | ≤ .01 |

    rms(P − 1) of the fitted orders: 0.13-1.9 on the built arms, 0.003-0.016
    on the noisy random ones. Noise-free, the random ones leave only the
    report windows' own misfit (rms 1e-5 to 3e-4), and m-3m's order 6 still
    reads F p 0.026 on it. So R² and F alone can pass a confident wrong
    singleton, and the amplitude has to sit beside them.
  - **What the partition buys.** With unpartitioned K, the noise-free order-4
    −3m1 fit reads c4_3 as −0.091 (truth −0.15, partitioned −0.147) and adds
    a spurious order-6 step (F p 0.0036). On a one-atom −3m1 phase c4_3,
    c6_3 and c8_3 have visibility 0 and drop out of the rank. The rank gap
    over −1, 2/m, mmm, −3m1, 6/mmm and m-3m at orders 2-8 runs from 7.6e-16
    dropped to 0.13 kept.
  - **CPD-2 brucite** (the round-robin QPA protocol, `qpa_plan`; weighed-
    fraction errors in wt %):

    | fit | worst error | brucite | notes |
    |---|---|---|---|
    | bare, protocol (Biso free) | 41.07 | +41.07 | Mg, O Biso 22.0, 23.3 Å²; 7 live reflections |
    | bare, brucite Biso held | 2.80 | +1.31 | 35 live, Kish 6.9 |
    | bare, no Biso stage | 3.42 | +1.00 | |
    | March-Dollase (001) | 3.01 | +2.15 | r 0.668(4) |
    | order 4 | 3.71 | +3.71 | C2,0 1.402(44), C4,0 0.720(59), C4,3 −0.117(55) |
    | order 6 | 2.91 | +1.82 | |
    | order 8 | 3.60 | +3.60 | |

    The screen on the Biso-held bare fit: R² 0.910/0.993/0.996/0.998 at
    orders 2-8. F(4|2) 197, p 2e-18, ΔBIC −84.6. F(6|4) p 0.0057, ΔBIC
    −4.8. F(8|6) p 0.0027, ΔBIC −8.8. ΔBIC against the axis is +14.4 at order
    2 and −70.2 at order 4. Its order-4 C (1.42, 0.86, −0.19) sits within
    about 2.5 esd of the refit's. The axis screen names (2,1,0) at r 2.24,
    R² 0.940, with (0,0,1) runner-up at r 0.675, R² 0.932, which is the
    refit's r. On the protocol's own bare fit the order screen means nothing
    (7 reflections, R² 1 at order 6 on rank 5), and the axis screen names
    (0,1,−1) at R² 0.68.
  - **Biso absorbs texture in any bare fit that frees it.** Synthetic order-4
    −3m1: R² at order 4 falls from 0.988 to 0.716. A MD r 0.6 specimen goes
    from 34 live reflections to 8. This is the existing axis screen's
    behaviour too, and the report already speaks before the maturity gate
    for the same reason (`report/__init__.py`).
  - **Tests.** `tests/test_texture.py` 58 passed (51 before plus 7 added; the
    added cost 1-2 s serially). `test_preferred_orientation.py` 20 passed,
    `test_fitreport_layers.py` 72 passed, `test_audit_table.py` 23 passed,
    all serial, darwin/arm64, `[dev]`. The fast selection was not run
    locally, where a full run is gated off this machine. The change reaches
    no default path, so CI's fast matrix on the ready PR gives the count. The full
    selection did not run, since nothing measured can move.
    `tests.reader_output`: exit 0, unchanged. `tests.audit_delta` adds one
    row, `_ORDER_RANK_TOL`, at tier 1. Two made-to-fail checks: with M
    replaced by the identity, the order-4 test and the visibility test both
    fail.
  - **Review.** A read-only review agent read the diff. It found no bug on
    the single-phase path, one risk and six nits, all fixed or written down
    in `abdcabae`:
    - The risk (now in the docstring, not fixed): on overlapped reflections
      of a multi-phase pattern, the constant a stands for the other phases'
      share 1 − M·1 only where a = 1. Its bias is (a − 1)(M·1 − 1), at most
      0.015 in its probe. The axis score carries the same.
    - The nits, all fixed: a guard for under two live reflections; NaN
      where no axis was scored; validated orders; NaN for C at a = 0; one
      partition per phase; a positive strength bar in the first test.
  - **Generality** (judge's verdicts, condensed; the full tables went to the
    PR):
    - **Rank tolerance: weak, as first written.** It was moved off the
      walked constants, which the judge called a dodge. Answered: it is now
      `_ORDER_RANK_TOL` with a tier-1 row and the gap test the judge asked
      for (seven phases including −1 and 2/m).
    - **`orders = (2, 4, 6, 8)`: weak.** No evidence on the cap at 8, and no
      program default is checked.
    - **`max_index`, `min_weight_frac`: hold as copies of `analyse_texture`'s,
      which have no row** (WP-2004's).
    - **Statistics: hold as measurements, with four items owed before task 3
      sets a threshold.** The judge's (i)-(iv):
      - (i) the p-values are not calibrated, now said in the docstring;
      - (ii) n against n_eff;
      - (iii) no axis-ΔBIC where no axis was scored, now NaN;
      - (iv) this entry.
  - **Questions for the maintainer** (task 3 needs them; nothing here
    decides them):
    1. **The record field.** Proposed:
       `TextureAnalysis.orders: list[TextureOrder] | None`, with `None`
       meaning not measured. Each row would hold order, n_terms, rank, r2,
       rms_p, f_stat, p_value, delta_bic, delta_bic_vs_axis and the names of
       terms below a visibility floor. Writer: `analyse_texture`, through
       `_order_screen`. It bumps the report schema. Or keep it off the record
       until task 3 needs it?
    2. **The thresholds.** Which statistic suggests an order (F p, ΔBIC
       between orders, or both), and at what? What rms(P − 1) floor does a
       suggestion need? The measured window is 0.016 on noisy random
       powders against 0.13 on the weakest built arm.
    3. **n or n_eff.** Should ΔBIC and the F dof charge the live count
       (35 on CPD-2) or the Kish count (6.9)?
    4. **When the axis "explains as much".** MD r 0.8 gives ΔBIC −2.9 at
       order 4 against its own axis. Is that the axis's, or the order's?
    5. **The order cap.** Is 8 enough, or does a strongly textured specimen
       need 10 or more?
    6. **Biso in the bare fit.** The QPA protocol's bare fit blinds both
       screens on CPD-2. Should the screen read the stage before Biso (the
       stage-report trajectory), or say it was blinded?
  - **Gotchas.** `texture_basis` builds degrees from 2 up, so order L's
    terms are a prefix of order L+2's; the screen relies on it and asserts
    it. A cubic class has no order-2 term (rank 0, statistics NaN).
    `compile_model` with no window tolerance reads a different floor from
    the report's model: pass `WINDOW_AREA_TOL`, as `_reading_models` does.

  Next: the maintainer's answers to questions 1-3, then task 3 (the Layer-2
  action and its `_audit` rows), then task 4's CPD-2 test from the numbers
  above, then the manual and skill rows. Question 6 decides whether task 3
  must also read the stage trajectory.

- **2026-10-15** — filed from WP-1960's Non-goals, which promised it once the
  basis existed. No open WP owns `report/texture.py`: 0307 and 1054 are
  closed, and 1335 is the report's cost. Next: the per-order solve, then
  measure on CPD-2 whether the nested comparison picks an order March-Dollase
  does not beat.
