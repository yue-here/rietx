# WP-1811 — bodies in a series

Milestone: rigid-bodies · Status: ⬜
Depends on: 1805, 1333
Priority: P3 2026-10-06 — a series with a body is the in-situ case; a single fit is not affected

## Goal

A sequential refinement carries a body from pattern to pattern by its absolute
quaternion and origin, never by its increment. This is chunk R11 of issue #561, sized S.

## Context

- `sequential.py` carries `Structure` values. A carry transfers the quaternion and the
  origin. The successor's increment is set by `displace_anchored_dofs` through `Log`
  (WP-1805), never by copying the increment.
- The wrong rule, carrying the increment, is off by 0.0147° at 3° (WP-1803's record).
- The trajectory is the quaternion.

### Inherited

- **2026-11-15, from the issue triage (issue #1558): the carry is built, and the
  orientation never reaches the result.** *Checked against the tree at `98d7ba8e3`:*
  `_carry_into` (`sequential.py:786`) passes each body's quaternion, origin and torsions
  to `ParameterTable.displace_anchored_dofs` (`params/vector.py:3678`, the call at
  `sequential.py:838`). The increment-carry failure is pinned by
  `test_the_series_carry_sets_the_increment_by_log_not_by_subtraction`
  (`tests/test_rigid_body.py:515`). So the first task and the third acceptance line
  are done in substance; whoever starts this WP ticks them with what did it. The
  reporter measured, not rerun here: three-pattern C₆Br ramps at 3° and 15° steps read
  the planted turns within 0.07°, and every direction gap is 0.0. What is missing:
  - No quaternion reaches `SeriesResult`. `rotation.k` is an increment a commit
    zeroes, so it reads 0.0 on every pattern, and `steps` and `direction_gaps` skip it
    as a relative path. A torsion's twist is the same. So the acceptance line "the
    trajectory is the quaternion" fails today.
  - The stored quaternion is canonical, w ≥ 0 (`crystallography/rotation.py:17`). On a
    ramp across w = 0 the whole vector changes sign between neighbours (dot −0.9997), so
    a plotted z component jumps by 1.6 for a 3° turn.
  - `SequentialRefinement.fitted_structures` (`sequential.py:2338`) holds the first chain
    only, as a list over the patterns that have an entry, so a pattern that raised
    shifts every later index.
  The reporter offers a rewrite of this WP's goal, tasks and acceptance around the
  result surface: a continuous quaternion and the turn from the first accepted pattern
  with a propagated esd, per body and per chain, and orientations compared modulo ±q and
  the body's point group. It also asks three design questions (a typed field or
  absolute rows; which covariance gives the turn's esd; whether `fitted_structures`
  changes what its callers read). Each is a scope or reader-output call, held for the
  maintainer on 2026-11-15, so this WP's goal is unchanged until that answer.

- **2026-11-05, from the issue triage (issue #1390, item 1):** `_displace_body_rotations` writes
  into held rotation entries too, so a body with one free turn direction starts its stage with a
  nonzero held increment, and the esd re-charted at the first commit is approximate. WP-2114 owns
  the fix. Read its Context before relying on a carried body's first-pattern esds.

## Non-goals

- Bodies in a joint fit (`multi.py`).

## Tasks

- [ ] The carry rule in `sequential.py`
- [ ] Tests (the acceptance below) + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: a row in the series reference if the trajectory shape changes what an agent reads

## Acceptance

- A three-pattern ramp with a rotating body agrees under `direction="both"`.
- The trajectory is the quaternion.
- A carry of the increment fails the test by the spike's 0.0147° at 3°.

## References

- Issue #561; PR #596; WP-1333.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
