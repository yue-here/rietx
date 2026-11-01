# WP-1805 — `RigidBody`: schema, collector, anchored rotation, the body's own rows

Milestone: rigid-bodies · Status: 🔄 2026-10-08 — every original task landed from outside (PR #801, merged as `089f24bc`). The maintainer answered #801's three questions, and two follow-ups they opened remain. #824's joint-commit rollback landed (PR #825)
Depends on: 1802, 1804
Priority: P2 2026-10-06 — the feature the milestone was opened for; every later body WP depends on it

## Goal

`Phase.rigid_bodies: list[RigidBody] = []` places a `Fragment` (WP-1802) over the
phase's own atoms. Its origin and orientation refine, and its atoms come back with
esds. This is chunk R3 of issue #561, sized L.

## Context

The record is [`docs/DESIGN.md` § Parameter system](../DESIGN.md#parameter-system),
clause "Rigid bodies". WP-1804 supplies the derived block this WP declares.

- **Collector.** Origin DOFs on the origin's site-symmetry basis. Three rotation DOFs
  of a new **anchored-rotation kind**, or as many as the template's inertia rank allows
  (`Fragment`'s DOF count: two for a linear body). The kind is table data built
  where the anchor is. It is not an `Entry` field, because the kind belongs to a
  body's group of rows and a field cannot name the group (answered 2026-10-08).
- **The rotation composes at commit** (the record, re-affirmed 2026-10-06):
  R₀ ← Exp(δω)·R₀ and δω ← 0 at every `ParameterTable.commit`. The record is the
  absolute unit quaternion with w ≥ 0 (WP-1801). A rotation DOF is never in
  `_anchored_dofs`, and nothing rebases it.
  - **What composing at commit costs.** After the commit, the solver outcome's θ,
    Jacobian and correlations still describe the old chart.
    `optimize.least_squares.rechart_outcome` only flips signs today, so this WP
    extends it to carry the outcome into the composed chart.
  - **A partly free rotation is refused** (answered 2026-10-08). A body's free turn
    directions, after holds and ties, number 0, 1 or all. Two free directions of a
    three-direction body do not stay two under composition, because two turns
    combined produce the third. No matrix maps the old family onto the new one,
    so a re-chart there can only approximate. The measured approximation was no
    better than no re-chart at all (the 2026-10-08 entry).
  - **Declined alternative** (#561 re-cut comment, 2026-10-06): compose in
    `apply_to_models` and start the next table at δω = 0. The contributor measured the
    same orientation that way. The maintainer kept the record.
- **Bound the increment.** The exponential map's Jacobian degenerates as |δω| → 2π, and
  a stage folds its rotation in only at commit. So bound |δω| (a ±π box per component
  keeps |δω| < 2π) or re-anchor past π (WP-1803's 2026-10-01 handover).
- **`displace_anchored_dofs`** (the series carry, WP-1333) sets a body's increment from
  the record: δω = Log(R_target·R₀ᵀ) and δo = o_target − o₀. The subtraction rule is
  wrong by 0.0147° at 3°.
- **Body-atom rows.** x/y/z are locked rows that carry esds, the inverse of the
  moment's rule. `x.vary = True` on a body atom is refused in the shape of the
  special-position refusal.
- **The cell is a live input.** A cell-only stage and Le Bail move a body's
  fractional coordinates while its geometry in Å stays fixed.
- **Holds** apply to the body's own DOFs, never to a body atom's coordinate row.
- **Ties.** A body row or DOF as target is already refused by `Refinement.tie`. A body
  increment as the source of anything that does not reset with it is refused by name.
  A body DOF may follow another body DOF of the same kind.
- **A commit-time guard** asserts the committed body's bonds equal the template's to
  1e-9 Å. The stale-anchor arm gives 2e-3 Å against 1e-15 Å.
- **Surfaces.** `help.py` rows for the new paths. The three codes take no `help.py`
  arm (answered 2026-10-08). `help.py`'s one code arm serves the Peaks panel's
  popovers, and a fit-report code explains itself through its message, its
  `suggestion` and its skill row. `gui/src/lib/history.ts` `PLACES`
  for `phases.*.rigid_bodies.*.{origin.*,rotation.*}` and the quaternion record, then
  `npm --prefix gui test` and a rebuilt dist. `ParameterRow.held_because` gains
  `"body"`, and `tests/test_params_surface.py`'s field pin is updated deliberately.
- **No raised `api.md` cap.** Public body verbs go to the generated per-shape reference
  that WP-1812 builds. Until then they are deferred in `tests/api_surface.py`'s
  partition.

An outside branch builds most of this (`2cc57ca4`, listed on #561 on 2026-10-06). It
composes at write-back and lacks `RIGID_BODY_UNSUPPORTED`, the replay and textdoc
round trips, the hold-on-a-body-atom test and the inertia-rank DOF count.

### Inherited

- **2026-11-01, from WP-1951 (PR #1304): the body advice names every body.**
  `Refinement.hold`'s refusal on a body-placed row, and now
  `STAGE_PATH_NOT_FREE`'s site arm (`refine._site_glob_diagnostics`), both
  tell the caller to free `phases.*.rigid_bodies.*.origin.dof.*`,
  `…rotation.*` and `…torsions.*.twist`. That is every body in every phase,
  wider than the one site asked about. The generality judge marked the
  suggestion weak on it. Narrowing both to the owning body's
  `phases.<i>.rigid_bodies.<k>.` is one change; `table.body_rows()` gives
  the body's name, not its index.
- **2026-10-08, from the issue triage (issue #824): a joint commit is not
  atomic.** `MultiParameterTable.commit` (`params/multi.py`) commits its tables
  in turn with no rollback. Since #801 a table's commit-time body guard
  restores only its own state, so a refusal on histogram 1 leaves histogram 0
  committed. The reporter measured a body turned 2° on one table and not the
  other, shared atom rows apart by up to 0.0086. In PR #825 (mustachefeeling,
  open), which snapshots every table before committing any and restores all
  on a `ValueError`. Its claim was read against the issue and agrees.
  Checked against the tree at `8a47e888`: not re-run.

## Non-goals

- Special positions (WP-1807), torsions (WP-1808), restraints (WP-1809), hydrogens
  (WP-1810).

## Tasks

- [x] Schema: `RigidBody`, `BodyOrigin`, `Phase.rigid_bodies`, SCHEMA bump
- [x] Collector: origin and rotation DOFs, the derived block, the refusals by name
- [x] Anchored rotation: compose at commit, re-chart the outcome, bound |δω|; `displace_anchored_dofs` by `Log`
- [x] Commit-time rigidity guard; Le Bail force-fix; `ParameterRow.body` and `held_because`
- [x] `help.py` rows for the paths, `PLACES`, manual Part 2 equation for the body map
- [x] Cross-backend `bodies` config
- [x] Tests: the acceptance below + obs/calc/diff PNGs to `tests/output/`
- [x] Skill: a reference row for each new diagnostic code (`test_every_engine_diagnostic_code_has_a_protocol_row`)
- [ ] Read a body's rotation paths off its `RigidBodyBlock` and delete `_anchored_rotations`
      (answer a; the block already builds them and holds the anchor)
- [ ] Refuse two free turn directions on a three-direction body at stage start, naming
      the remedies (free all, hold all, or tie to one axis). Delete `_chart_matrix`'s
      `pinv` projection. Reword `RIGID_BODY_UNSUPPORTED`'s suggestion so it cannot
      steer a caller into the refused hold (answer c)
- [ ] Tests: the re-chart against a fresh solve for every allowed shape; the refusal

## Acceptance

- A body declared over the phase's own placed atoms decodes to the same coordinates
  < 1e-12.
- The spike's C₆Br body, recovered from a synthetic pattern started 3° and 10° off:
  orientation within 0.1°, and the esd covers the truth.
- Body-atom rows carry esds equal to the FD chain to 1e-9.
- The committed structure is rigid to 1e-9 Å, and a build that skips the
  re-exponentiation fails that test.
- After a commit, the re-charted outcome's correlations match a fresh solve started at
  δω = 0 on the committed values.
- A tie onto a body row and a tie from a rotation increment each raise, naming the path.
- `Refinement.hold` on a body DOF blocks a plan with `HOLD_BLOCKED_PLAN`, and on a body
  atom row it raises.
- Checkout, replay and the textdoc round trip reproduce the body.
- `test_every_engine_diagnostic_code_has_a_protocol_row` passes.
- For none, one or three free turn directions, a rotation tied to one axis and the
  linear body, the re-charted esds and correlations match a fresh solve at the
  committed values to 1e-5.
- Two free turn directions of a three-direction body raise at stage start, through a
  hold, a tie or a plan glob alike, naming the body and the remedies.

## References

- Triggs, McLauchlan, Hartley & Fitzgibbon (2000), *Bundle adjustment — a modern
  synthesis*, LNCS 1883, §2.2: the increment composed at commit.
- Issue #561; PR #596; WP-1803, WP-1514.
- Solà (2017), *Quaternion kinematics for the error-state Kalman filter*,
  arXiv:1711.02508, §7.2: the filter's reset step is the re-chart's precedent.

## Handover log

- **2026-10-08** (3rd session) — a joint fit over several histograms can no longer
  leave its tables disagreeing about a body after a refused commit. PR #825 (#824,
  head `7ebbd942`) merged as `14b4ee71`, so the `### Inherited` #824 item is done.
  *Done.* `MultiParameterTable.commit` snapshots every table before committing any
  and restores all of them on a `ValueError`. The snapshot and restore are
  `ParameterTable._commit_state` / `_restore_commit_state`, factored out of #801's
  single-table refusal, so both paths share them. The review checked that the
  restore also undoes what a table that committed successfully ran
  (`settle_anchor`, `_refresh_derived`, `_d`).
  *Gate:* stacked with the run's other merges (#829, #825, #809, #754, #749, #815)
  on `main` `a3f9140a` as `166d362e`, macOS 26.6.2 arm64, `[dev,jax]`. The full
  suite, fast and slow together, gave 9231 passed, 116 skipped, 1 xfailed and 2
  failed. Both failures also fail on `main` alone on that machine: `toy_anomalous`
  (#760, which open PR #828 fixes) and a hypothesis counterexample in
  `test_indexing_reduce.py`. `main` after the merges is content-identical to that
  tree.
  *Gotchas.* PR #823 (WP-1808, torsions) edits the same snapshot and now needs a
  rebase: its φ₀ copies and `_precommit_torsions` go into the two new methods.
  *Next:* the two open tasks above, then close.

- **2026-10-08** (2nd session) — the maintainer answered #801's three questions, so
  the WP can close once two small follow-ups land. The rotation kind stays table data,
  and the table will read it off the body's block. The three codes need no `help.py`
  arm. A body whose rotation is only partly free will be refused rather than
  approximated, because a probe showed the approximate re-chart corrects nothing and a
  held turn drifts once the data pull against it. The probe also confirmed the exact
  re-chart for an all-free body.
  *Decided.* (a) An `Entry` field is the worst option: the kind belongs to a group of
  rows plus an anchor and axes, so a per-row flag would still need the group lookup.
  Ceres and GTSAM attach the same knowledge to the parameter block, and
  `RigidBodyBlock` already holds the anchor and builds `rotation_paths`. So
  `_anchored_rotations` goes, read off the block instead. The general "blocks fold at
  commit" loop waits for its second user, WP-1808's torsions (filed there). (b)
  `help.py` has one code arm, `PEAK_DIAGNOSTIC_HELP`, and it exists for the Peaks
  panel's popovers (`gui/src/panels/Peaks.svelte`). The Report panel shows a fit code
  with its message and no help lookup, and the two `ValueError` codes reach no panel.
  The PR said `help.py` had no code arm; it has one. (c) Two free turn directions of
  three are refused at stage start, and the `pinv` projection is deleted.
  *Measured* (a scratchpad probe on `tests/test_rigid_body.py`'s synthetic C₆Br body,
  P-1, `rotation.2` held; macOS arm64, a `[dev]` venv on `089f24bc`; not committed).
  Every gap is against a fresh solve at the committed values, which moved at most
  0.0006° (esd 0.020°). With all three free, the re-chart's correlation gap is 8.6e-7
  at 10° and 2.9e-6 at 30°, against 0.088 and 0.32 without it. With `rotation.2`
  held, the esd gap at 1°/3°/10°/20°/30° is 0.23/0.69/2.4/5.4/9.1 % with the
  projection and 0.23/0.68/2.4/5.2/8.5 % without it. The projection moves the block
  only to second order in the turn, while the real difference is first order. Drift:
  with the truth off the held family along (0.3, 0.8, −0.5) and eight folding stages,
  the turn about the held axis reached 0.0086° (0.05 esd) from 10° off and 0.27°
  (0.47 esd) from 30° off. Stages stopped early at ftol 1e-1 reached 1.1° (≈ 2 esd)
  from 30° off. Almost all of it comes at the first fold, and it levels off within
  two to four stages. Declining to fold inside one fit would not prevent it, since the
  model stores only the absolute pose and the next fit's table re-centres on it.
  *Gotchas.* No package-internal hold takes part of a body's rotation: the
  absent-phase hold and the mode force-fix take every `.rigid_bodies.` path. A
  partial free set arrives only from a caller's hold or tie, a plan glob naming some
  `rotation.k`, or a caller following `RIGID_BODY_UNSUPPORTED`'s "hold them". The
  existing `test_a_held_rotation_dof_beside_a_turn_is_recharted` checks the
  arithmetic of T⁻¹·Cov·T⁻ᵀ and never compares with a fresh solve, so it could not
  see the projection fail. Issue #824's non-atomic joint commit is still in PR #825
  (the `### Inherited` note above).
  *Next:* the refusal first, because it deletes the code path the second task would
  otherwise have to keep reading; then the block read; then the tests, the new
  acceptance rows being the bar. Close after #825 lands or is folded.
- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal. The maintainer
  kept composition at commit (the record) over the write-back alternative on #561, so
  this WP also extends `rechart_outcome`. The `Log` rule in `displace_anchored_dofs`
  stays here, as the record says, rather than moving to WP-1811 as #561 proposed.
- **2026-10-08** — every task landed from outside: PR #801 (head `3ba3d8ec`),
  merged as `089f24bc` by `/pr-review` after three rounds. The PR body maps each
  acceptance row to its test in `tests/test_rigid_body.py`. Round 1 found five
  items, each fixed and pinned by a reverting test. A variable at c ≠ 1 got a
  wrong analytic column once a table held a body, because `reach_block()` is
  0/1 there. A diagonal chart that is not ±1 was handled as a sign flip. A NaN
  orientation validated. `add_body` returned an unvalidated phase. Under Le Bail
  or Pawley, `held_because` named the body before the mode. The c ≠ 1 column was
  wrong on `main` without a body too, and the fix covers both. The schema went to
  0.43, after #788's 0.42. *Gate:* stacked with #744, #776 and #746 on `5d1f5f67`
  (`0c674af8`, macOS arm64, `[dev,jax]`, nothing else running). The fast suite
  gave 8899 passed, 107 skipped, 1 xfailed, 0 failed. `-m slow` gave 290 passed,
  12 skipped, 2 failed, and both also fail on `main` alone (#820). The GUI dist
  rebuilt byte-identical, vitest gave 586 passed, and `svelte-check` 0 errors.
  `main` after the merges is content-identical to that tree. *Open, the
  maintainer's:* the PR's three questions had no explicit answer in review.
  (1) The anchored-rotation kind is table data (`_anchored_rotations`) rather than
  an `Entry` field, so `ParameterRow`'s field pin is unchanged; is that the
  equivalent the record allows? (2) `help.py` has no arm for diagnostic codes, so
  `RIGID_BODY_UNSUPPORTED` has a skill row and a `suggestion`, and the two
  `ValueError` codes name their remedy; does `help.py` gain a codes arm? (3) With
  some rotation DOFs held or tied, the re-chart is a projection,
  pinv(A)·chart·A, exact only when all of a body's rotation DOFs are free or for
  a single axis; accept that, or decline to compose such a body? *Gotchas:*
  `restore_body_anchors` is a step every restorer has to remember. Capturing the
  anchors with `start_values` would cover a third restorer, and the contributor
  left that and slicing `_chart_matrix` unfiled by agreement. *Next:* answer the
  three questions, then close, or carry them to WP-1807.
