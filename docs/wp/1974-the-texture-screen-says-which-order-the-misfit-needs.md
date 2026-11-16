# WP-1974 — the texture screen says which order the misfit needs

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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

- [ ] The per-order solve beside the axis score, on the fit's frozen cell.
- [ ] The nested comparison per added order, and the record field it writes,
      with its writer named.
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

- **2026-10-15** — filed from WP-1960's Non-goals, which promised it once the
  basis existed. No open WP owns `report/texture.py`: 0307 and 1054 are
  closed, and 1335 is the report's cost. Next: the per-order solve, then
  measure on CPD-2 whether the nested comparison picks an order March-Dollase
  does not beat.
