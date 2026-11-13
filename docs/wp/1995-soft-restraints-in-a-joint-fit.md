# WP-1995 — Soft restraints in a joint fit

Milestone: parametric · Status: 🔄 2026-11-09 — restraints reach a joint fit (PR #1492); the expression penalty task remains
Depends on: 1964 (the grammar, for the penalty task alone)
Priority: P2 2026-11-04 — was P3: the parametric milestone takes it, since an expert's restraints stop at the joint fit, and a penalty is how a bound on a nonlinear target can hold

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

**A penalty written as an expression** (from the opening of the
[parametric](../milestones/parametric.md) milestone, 2026-11-04). TOPAS has
`penalty = expr;`, which adds to χ² (forum 700), Artemis has a `restrain`
parameter type, and GSAS-II has expression restraints (`GSASIIrestrGUI.py`,
general restraints). A joint fit needs one for a second reason.
[1964](1964-a-parametric-equation-the-user-writes.md) cannot hold a bound on an
equation's target as a box, because the target is not a linear function of the
coefficients. TOPAS ignores such a bound silently (forum 767). A hinge written in
the grammar is the soft answer. Decide how its weight relates to the data's (root
CLAUDE.md: a penalty's λ is weighed against the data's), and whether its rows are
one per pattern.

## Non-goals

- Penalty rows over the pattern coordinates (smoothness, pooling, kernel
  priors). Those belong to 1325, 1962 and 1963, which reuse this seam.
- The centroid floating-origin restraint in a joint fit (WP-1912's refusal,
  `multi._refuse_centroid_origin`). It is the same once-per-structure problem.
  1912 closed with the refusal in place, and lifting it is
  [WP-2029](2029-whether-the-centroid-fixes-a-polar-origin-by-default.md)'s
  task 1, with one origin row block per shared structure or a fallback to
  `"hold"`, reusing this WP's placement once it lands.

## Tasks

- [x] `_multi_closures`: read each model's below-data blocks from
      `rows.layout`, place the soft-restraint rows once per structure without
      histogram weight, and drop the refusal. Make `BlockJacobian` agree.
- [x] Per-histogram `ValueRestraint`: decide, and refuse by name what is not
      built.
- [x] `_restraint_tension_diagnostics` and `RestraintReport` reach the joint
      result. Flip its `ABSENT` row in `multi.py`. `HistogramResult.restraints`
      has no writer today, always `None` (`schemas/results.py`, and
      `docs/docs/reference/joint.md` says so), so this is its writer.
- [x] Tests: a joint fit of two identical patterns with one bond restraint
      matches the single fit's restrained bond and restraint χ² (rows counted
      once); a joint config with restraints in `test_cross_backend.py`'s
      matrix, so the row-Jacobian is checked against FD; the stacked and
      blocked layouts agree.
- [x] Remove the refusal line from 1325's, 1962's and 1963's seams (forward
      references).
- [ ] A penalty written in 1964's grammar, as a row block in the same seam, with an
      exact derivative from the grammar's rules (§ Context, a penalty written as an
      expression). Tests: a
      hinge on a target holds it near its bound on a synthetic ramp, and the block joins
      the cross-backend matrix.
- [x] Skill: the series/joint reference's restraint row, or "none" and why.
      None (2026-11-09): see the handover entry.

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

- **2026-11-09** — A joint fit now takes a structure's soft restraints. Before,
  any restraint made a multi-pattern fit raise; now a restraint on the shared
  structure counts once, however many patterns see it, so it weighs against
  the data exactly as in a single fit. A restraint that reads a per-pattern
  parameter (a pattern's zero shift, a bond under a per-pattern cell) holds in
  each pattern. Each pattern reports its restraints, and a restraint fighting
  the data is named once or on its pattern's list. The expression penalty
  (task 6) is not started.
  - *Done.* Tasks 1-5 and 7, in PR #1492. `_multi_closures` stacks
    `[data | background penalty | soft restraint]` off `rows.layout`, refusing a
    non-empty block it does not place (`_JOINT_BLOCKS`). `_joint_restraint_shared`
    decides once-or-per-histogram per compiled item: shared when every path it
    reads is bare under `MultiParameterTable.row_path` and no per-histogram row
    reaches it through `ParameterTable.entry_reach` (free or fixed, so the answer
    does not move with the free set). Restraint rows carry no `√w_h`.
    `BlockJacobian` takes `n_restr`, a third stripe. Task 2's decision: a
    `ValueRestraint` on a per-histogram path is every histogram's own row; a
    `hist.N.`-scoped path is refused by name. `HistogramResult.restraints` gets
    its writer, and `RefinementResult.restraints` mirrors histogram 0's.
    `RESTRAINT_TENSION` is `(HISTOGRAM, SPECIMEN)`, `RESTRAINT_PAIRS_STALE`
    `SPECIMEN` (histogram 0's copy). Joint compiles now take the stage's
    `restraint_weight_scale`, which they had dropped (c_w was 1 in every joint
    stage). Manual: `reference/joint.md` § Soft restraints.
  - *Task 7, none.* An agent declares restraints and reads `result.restraints`
    as in a single fit, and the per-pattern placement is in the refusal message
    and the manual. Under the skill's placement rule nothing earns a row.
  - *Measured* (Mac arm64, `.venv` `[dev]`, jax 0.12 added for the matrix; the
    workstation did not answer, so every run here was on the Mac at `-n 2`).
    Joint fit of one rutile pattern twice at weight ½ against the single fit:
    O x equal to 3e-13, restraint χ² to 4e-10 relative; the single fit at
    restraint weight 2 sits 5e-5 away in x, so a twice-counted row is
    separable. Selection `test_restraints test_parametric_series
    test_multi_histogram test_multi_diagnostics test_cross_backend`: 468 passed, 111 skipped, 4 xfailed. Fast selection (`-m "not slow"`, `-n 4`): 14535 passed, 244 skipped, 32 xfailed in 11 min (testslot, `-n 4`); the tests added are 4 net in `test_restraints` (one refusal test replaced) and 8 cases in `test_cross_backend` (the restrained state across 7 method rows, one layout test), 1.2 s in all on that run.
    Cross-backend `-k multi`: 10 passed, 4 skipped (torch absent).
    `tests.reader_output` exit 0 (unchanged).
  - *Review.* No `/code-review` (it cannot be pointed at this worktree from a
    ghostshift runner); an Opus subagent reviewed the diff and found no bugs.
    Taken: classify through `entry_reach` instead of free-column reach (a held
    per-histogram body input was misread as shared, and the answer moved with
    the free set); the `added_columns_gain` docstring; a manual sentence that a
    pattern's `restraint_chi2` counts the shared rows too. Declined: exact
    restraint rows in `_stacked_rows`, which only sizes the layout choice.
  - *Generality.* No `_audit.py` change, no threshold, code, field or default
    added; the judge was not dispatched. Rows without `√w_h` are the WP's own
    design (§ The one design decision).
  - *Overlap.* `multi._build_result` is edited by open PRs #1477, #1405, #1272
    and #1108 at other lines; `test_cross_backend.py` by #1372 and #1108 at
    other lines. `reference/joint.md` is also WP-2103's manual task.
  - Next: task 6, the expression penalty. Two questions decide its shape
    before code: how its weight relates to the data's (root CLAUDE.md: a
    penalty's λ is weighed against the data's, √(λ·m)/σ̄) and whether its rows
    are one per pattern or once per fit; both are the maintainer's to rule if
    the grammar does not settle them. It reuses `_JOINT_BLOCKS` and
    `n_restr`'s stripe, or adds a fourth.
- **2026-11-04** — Moved into the `parametric` milestone and re-rated P2 on the
  maintainer's opening of it, with the expression penalty added. Next: the first task.
- **2026-10-16** — Renumbered twice as this branch merged main, which took
  1988 and then 1990 for other WPs the same day: filed as 1988, then 1990,
  now 1995. No commit naming 1988 or 1990 is this WP's.
- **2026-10-16** — Filed from the audit of notes written into closed WPs. No
  open WP owned the deferral: 1325, 1962 and 1963 each name it only as a seam
  to get past, and 1963 may close as moot before reaching it. So it became
  its own WP rather than a fold. Next: the first task.
