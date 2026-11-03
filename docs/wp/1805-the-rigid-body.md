# WP-1805 — `RigidBody`: schema, collector, anchored rotation, the body's own rows

Milestone: rigid-bodies · Status: ✅ 2026-11-03 — every task landed: a body turn free in two directions of three is refused at stage start, rotation paths read off the block (PR #1388); leftovers in issue #1390
Depends on: 1802, 1804

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
- [x] Read a body's rotation paths off its `RigidBodyBlock` and delete `_anchored_rotations`
      (answer a; the block already builds them and holds the anchor)
- [x] Refuse two free turn directions on a three-direction body at stage start, naming
      the remedies (free all, hold all, or tie to one axis). Delete `_chart_matrix`'s
      `pinv` projection. Reword `RIGID_BODY_UNSUPPORTED`'s suggestion so it cannot
      steer a caller into the refused hold (answer c)
- [x] Tests: the re-chart against a fresh solve for every allowed shape; the refusal
- [x] Narrow the body advice to the owning body (from WP-1951's `### Inherited`, PR #1304):
      `Refinement.hold`'s refusal on a body row, `STAGE_PATH_NOT_FREE`'s body arm and the
      body-atom `vary` refusal name `phases.<i>.rigid_bodies.<k>.`'s own DOFs, not every body's

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

### 2026-11-03 (4th session) — a partly free turn is refused; every allowed turn re-charts exactly; WP closed

A rigid body whose turn could refine in two directions of its three no longer runs. The stage
refuses it before anything is written, names the body and which of its turn parameters are
free, held or tied, and gives the three ways out: free all, hold all, or tie the turn to one
axis. Every shape a stage does allow (no direction free, one, all, a turn tied to one axis, the
linear body) now restates the solver's errors exactly after the commit composes the turn,
measured against a fresh solve at 3e-12 to 1e-6. The refused shape misses by 2.6 % in an esd,
which the deleted approximation did not close. Advice that named every body in every phase now
names the one body asked about. One thing is lost: a profile interval of one rotation parameter
of a three-direction body has no ends now, because each of its refits is the refused shape.
That loss and three other leftovers are issue #1390.

*Done* (PR #1388, draft opened at the claim, ready at this entry).
- `_anchored_rotations` deleted: every reader asks the body's block, `block.rotation_paths(bbase)`
  (answer a). `e53bb62ed`.
- `ParameterTable.free_turn_directions` counts a body's free directions as the rank of its
  rotation rows of C over the free columns, so a hold, a tie and a glob count alike;
  `refuse_partial_turns` raises `RIGID_BODY_PARTIAL_TURN` for any count but 0, 1 or k. Both
  runners call it once the free set is settled: `Refinement._run_stage` after the mode
  force-fix, the joint runner per histogram table (`joint=True` words the remedy for a fit with
  no hold or tie verb). `_chart_matrix` lost the pinv(A)·chart·A projection: A⁻¹·chart·A where
  every direction is free, the identity where one is (J_l(t·a)·a = a). `684417078`.
- `RIGID_BODY_UNSUPPORTED`'s suggestion asks `free_turn_directions(without=…)` what holding the
  blind DOFs would leave, and names the whole turn when that is the refused shape. `help.py`'s
  entry now points at the suggestion (one line, local to the entry). New skill row for the
  refusal in `references/abstention.md`, both committed copies re-synced (answer c).
- WP-1951's inherited item, folded in as a task: `Refinement.hold`'s refusal,
  `STAGE_PATH_NOT_FREE`'s body arm and the body-atom `vary` refusal name
  `phases.<i>.rigid_bodies.<k>.`'s own DOFs (`ParameterTable.body_row_bases`). The body arm had
  no test; it has one. `3a7b2510c`, `ed8eedb2b`.
- Tests: `9d6b5f812` plus the review's. The #801 regression test that used the refused shape
  (`rotation.2` held) now builds its non-signed-identity chart from the linear body, as
  committed and as its exact diagonal.

*Measured* (macOS 26 arm64, this worktree's `[dev]` venv). Re-chart against a fresh solve at the
committed values, 10° start, largest gap over the whole outcome:

| shape | correlation | esd (relative) |
|---|---|---|
| none free | 3.0e-12 | 3.0e-12 |
| one free | 2.9e-10 | 4.7e-10 |
| all three free | 1.0e-6 | 5.3e-7 |
| tied to one axis | 4.0e-11 | 7.8e-11 |
| linear, one free | 5.0e-11 | 1.7e-10 |
| linear, both free | 2.2e-8 | 1.2e-10 |
| refused: two of three | 3.6e-2 | 2.6e-2 |

The refused row agrees with the 2nd session's 2.4 % at 10°. With `refuse_partial_turns` made a
no-op, the four refusal tests fail and the rest pass. Fast suite on this branch merged with
`origin/main` at `ea981ccac`: 13752 passed, 318 skipped, 34 xfailed, 0 failed, 12:33 (a serial
lock queue ahead of it). The known main defect `test_eval_skill.py::…placement_episode…` (#1384)
did not fail here. `tests/test_rigid_body.py` collects 57 against main's 41: +16 cases (one test
renamed, net 0), all passes. `tests.added_test_times`, local junit: 9.57 s over the 10 added
functions, the largest the profile test at 3.59 s (a fit plus two refused refits; not `slow`,
being one fit). Full suite not run: no `slow` test reaches a body (`grep` over the test files;
the cross-backend `bodies` config is fast), and the change moves only body stages.
`tests.reader_output`: exit 0, unchanged against the merge-base. Vale (`rietx_vale.sh`): 0 errors.

*Review* (`/code-review high --fix origin/main..HEAD`, 9 findings). Fixed: a hold sweeping two
bodies named one body with another's globs (now each body, its own globs, with a test); the joint
refusal named verbs `MultiHistogramRefinement` lacks; the remedy for a held or tied DOF now says
unhold or untie first; ranks go through `lapack.svd` (the fit-path rule); the unsupported advice
parsed the body off the path name (now `body_dof_bases`); `refuse_partial_turns` spelt the paths
itself; `body_row_bases` was rebuilt per glob. The body-atom refusal omitting twists was declined
by the review for its pinned text and fixed here. Declined: the check runs before the support
hold, so cross-body ties can reach the refused shape after it (issue #1390, item 3). The review
also found the profile-interval loss (item 4).

*Generality.* Not dispatched: no `_audit.py` change, and nothing added is a heuristic. The
refusal rests on composition (two turns compose into a third), with no threshold. The advice
keeps its one `suggestion=` site.

*Gotchas.* `_displace_body_rotations` writes held rotation increments in a series carry, which
breaks the one-direction identity chart at the first commit (issue #1390, item 1). A cross-body
rotation tie at a scale other than 1 gives two bodies conflicting chart blocks on one column,
and the second written wins. That predates this work (item 2). `help.py`'s longer first wording
put `reference/diagnostics-refinement` 124 characters over the manual's 50 000 cap
(`test_every_page_has_a_twin_that_keeps_the_contract`), so that page has almost no room left.

*Next:* none here; the WP is closed. Issue #1390 carries the four leftovers, item 4 with a
question for the maintainer (exempt a profile refit, or ask for a turn's interval another way).

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
