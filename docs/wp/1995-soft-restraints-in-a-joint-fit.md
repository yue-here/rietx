# WP-1995 — Soft restraints in a joint fit

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: —
Priority: P3 2026-10-16 — a raise, not a wrong number, and refining each restrained pattern alone is the workaround; three open WPs name the refusal as their first seam

## Goal

A multi-histogram joint fit accepts a structure that declares soft restraints
(`Phase.restraints`). Each restraint contributes its rows **once per
structure**, not once per histogram, and the restraint reporting a single fit
gives (`RestraintReport`, `_restraint_tension_diagnostics`) reaches the joint
result.

## Context

**What refuses today.** `optimize.least_squares._multi_closures` raises
`NotImplementedError("soft restraints are not yet supported in a
multi-histogram joint refinement…")` when any histogram's `CompiledModel`
carries restraints. `multi.py`'s diagnostic table records the consequence:
`_restraint_tension_diagnostics` is `ABSENT` in a joint fit, "so there is no
tension to report". The deferral dates from WP-0406 (restraint rows,
2026-07-27). WP-0406 wrote it into the `### Inherited` of WP-0308 (the joint
residual) three days after 0308 had closed. No open WP owned it until this
one: the 2026-10-16 audit of post-close mailbox writes found it there, with
the code comment pointing at the closed file.

**Who is waiting.** Three open WPs name this refusal as their first seam:
- [1325](1325-parametric-series.md): partial pooling, or a P-spline
  smoothness penalty over the pattern coordinates (its § Non-goals, "Soft
  forms").
- [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md):
  tomography needs a regulariser.
- [1963](1963-a-kernel-over-the-pattern-coordinates.md): prior rows.
  `1325-measure/kernel_ramp.py` appends them through a script-only
  replacement of `_multi_closures`.

All three want **penalty rows in the joint residual**. This WP lifts the
refusal for the restraints a structure already declares, and leaves that row
seam for them to reuse.

**The seams.**
- `_multi_closures` stacks `[all data | all below-data rows]`. It sizes each
  histogram's below-data stripe from `bkg_penalty` alone (`n_pen[h]`), and
  every row in it takes the histogram weight `√w_h`. Restraint rows would
  break both: the stripe would be the wrong size, and the rows would carry a
  pattern's weight.
- `model/rows.py` owns the single-histogram row layout (`BLOCK_ORDER`:
  data, background_penalty, pawley_restraint, soft_restraint,
  origin_restraint). It is the one authority. Read the block offsets from
  `rows.layout(m)` and never restate them. The 2026-07-24 recipe of "a third
  offset row-block beside `pen_off`" predates `rows.py`, so take its intent,
  not its arithmetic.
- `blocked.BlockJacobian` (WP-1325) carries `n_data` and `n_pen` per
  histogram. A restraint block is a third count there too, or the blocked
  layout disagrees with the dense one.

**The one design decision: once per structure.** A shared structure is
compiled once per histogram, so every `CompiledModel` would carry the same
restraint rows. Stacked as they are, a restraint would count N times and
weigh N× against the data. This is exactly why WP-1912 refuses
`floating_origin="centroid"` in a joint fit (`multi._refuse_centroid_origin`),
and that refusal names the same problem. So take the rows from one model,
unweighted by any `√w_h`, and put them below every histogram's data and
background rows. A restraint on a per-histogram parameter (a `ValueRestraint`
on one pattern's zero) is the exception to settle: its rows belong to that
histogram alone.

**Statistics.** In a single fit, restraint rows are excluded from
χ²/Rwp/DW/Bérar-Lelann and kept in JᵀJ (root CLAUDE.md, WP-1074's c_w). The
joint path's `n_data_total` already marks the data/penalty split. Keep the
restraint rows on the penalty side of it.

## Non-goals

- Penalty rows over the pattern coordinates (smoothness, pooling, kernel
  priors). Those belong to 1325, 1962 and 1963, which reuse this seam.
- The centroid floating-origin restraint in a joint fit (WP-1912's refusal).
  It is the same once-per-structure problem; lift it here only if it falls
  out for free.

### Inherited

- **2026-10-23, from [1912](1912-a-polar-axis-has-no-origin.md) (closed): lifting the centroid's joint-fit refusal now belongs to WP-2029.** This WP's Non-goals and References name `multi._refuse_centroid_origin` as "WP-1912's refusal". 1912 closed with the refusal still in place. [WP-2029](2029-whether-the-centroid-fixes-a-polar-origin-by-default.md) task 1 lifts it, either with one origin row block per shared structure or with a fallback to `"hold"`. It reuses this WP's once-per-structure placement if that lands first. Nothing in this WP's scope changes.
- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: `HistogramResult.restraints` has no writer.** It is always `None`: `multi.py:1740` never sets it (`schemas/results.py:1178`). `docs/docs/reference/joint.md` documents it so. This WP's restraint reporting for a joint fit is its natural writer.

## Tasks

- [ ] `_multi_closures`: read each model's below-data blocks from
      `rows.layout`, place the soft-restraint rows once per structure without
      histogram weight, and drop the refusal. Make `BlockJacobian` agree.
- [ ] Per-histogram `ValueRestraint`: decide, and refuse by name what is not
      built.
- [ ] `_restraint_tension_diagnostics` and `RestraintReport` reach the joint
      result. Flip its `ABSENT` row in `multi.py`.
- [ ] Tests: a joint fit of two identical patterns with one bond restraint
      matches the single fit's restrained bond and restraint χ² (rows counted
      once); a joint config with restraints in `test_cross_backend.py`'s
      matrix, so the row-Jacobian is checked against FD; the stacked and
      blocked layouts agree.
- [ ] Remove the refusal line from 1325's, 1962's and 1963's seams (forward
      references).
- [ ] Skill: the series/joint reference's restraint row, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_restraints.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Flack, H. D. & Schwarzenbach, D. (1988). *Acta Cryst.* A44, 499–506 (one
  restraint row per structure; WP-1912's precedent).
- WP-0406 (the restraint rows), WP-0308 (the joint residual), WP-1074 (c_w),
  WP-1912 (the centroid refusal).

## Handover log

- **2026-10-16** — Renumbered twice as this branch merged main, which took
  1988 and then 1990 for other WPs the same day: filed as 1988, then 1990,
  now 1995. No commit naming 1988 or 1990 is this WP's.
- **2026-10-16** — Filed from the audit of notes written into closed WPs. No
  open WP owned the deferral: 1325, 1962 and 1963 each name it only as a seam
  to get past, and 1963 may close as moot before reaching it. So it became
  its own WP rather than a fold. Next: the first task.
