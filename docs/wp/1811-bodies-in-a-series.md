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
