# WP-2114 — turn families composition does not keep: a series carry, cross-body ties, a late hold, a profile

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1805 (PR #1388 lands the refusal these items extend); 1811 soft (the series carry)
Priority: P3 2026-11-05 — a re-charted esd is approximate on shapes few fits reach, nothing here moves a value, and three of the four items are read and not measured

## Goal

Every way into a rigid body's turn family is either exact or refused. A series carry, a cross-body
rotation tie and a late package hold cannot make `ParameterTable._chart_matrix` re-chart an esd it
cannot compute. A profile of one turn direction of three has an answer.

## Context

**Source.** Issue #1390. WP-1805 closes in PR #1388, which refuses a body whose turn is free in two
directions of three (`RIGID_BODY_PARTIAL_TURN`). `_chart_matrix` is then exact in the shapes a stage
allows: no direction free, one, or every direction. Four ways into a turn family remain. Items 1-3 were
found by reading the code and item 4 was measured. `refuse_partial_turns` and `free_turn_directions`
are on PR #1388's head and not yet on main. `_chart_matrix`, `_displace_body_rotations` and
`_refuse_body_increment_tie` are on main at `541f0daf7` (`params/vector.py`).

**1. A series carry writes a held rotation increment.** `_displace_body_rotations`, the rotation half of
`displace_anchored_dofs`, writes θ = E⁺·Log(R_target·R₀ᵀ) into every untied rotation entry of the body,
held ones included. A body with one free turn direction then starts its stage at δω = a·t + d, with
d ≠ 0 on the held components. The stage-start check counts free directions, so it passes. At the commit
the chart on the free column stays the identity, which is exact only while ω* ∥ a. So the re-charted esd
and correlations of that column are approximate. The error is O(|d|·|δ|) and appears only at the first
commit after the carry, since a commit zeroes every increment. Options: compose a carry's held
components into R₀ before the stage, or treat a nonzero held increment beside a free one as the refused
shape. WP-1811 owns bodies in a series, and its carry goes through this function.

**2. Rotations tied across bodies at a scale other than 1.** A body DOF may follow another body DOF of the
same kind. Tie body B's rotation to body A's at c ≠ 1, and both bodies' charts land on A's columns.
`_chart_matrix` writes each body's block in turn, so B's J_l(c·ω)⁻¹ overwrites A's J_l(ω)⁻¹. The two bodies
need different matrices on one column. At c = 1, with E = I for both, the blocks agree and the re-chart is
exact. A linear body's E moves with its anchor, so there even c = 1 may disagree. This predates #1388.
Options: refuse a cross-body rotation tie at stage start unless the two charts agree (c = 1, both bodies
with three directions), or refuse cross-body rotation ties outright.

**3. A package hold after the check can make the refused shape.** `Refinement._run_stage` runs
`refuse_partial_turns` before WP-1301's support hold. With item 2's ties, body A's `rotation.1` and
`rotation.2` can follow body B in a seen phase while A's own `rotation.0` is held with A's unseen phase.
That leaves A with two free directions after the check passed, and `_chart_matrix` skips the re-chart.
Refusing cross-body rotation ties closes this as well. Otherwise the check also runs after the holds.

**4. A profile of one turn direction of three has no ends.** `Refinement.profile_interval` pins one DOF and
refits the rest as stages, so on a three-direction body each refit is the refused shape. Each side stops
on `"error"`, with the refusal as its reason. #1388 pins that with
`test_a_profile_of_one_turn_direction_of_three_says_why_it_has_no_ends`. Before #1388 the call returned an
interval off refits whose esds were re-charted by the deleted projection. A profile reads only χ², so the
re-chart was never used for it. What remains is the held direction's drift at each fold: from the
2026-10-08 probe, 0.05 esd from 10° off, and small near the answer. To decide: exempt a profile refit from
the refusal, or ask a turn's interval another way. WP-2060 owns `profile_interval` and is still open, so
read its handover first.

**The instrument.** `tests/test_rigid_body.py`'s `_recharted_and_fresh` measures a re-chart against a fresh
solve at the committed values. Items 1-3 need it before anything changes.

**Tier.** A refusal states what the arithmetic cannot do, so it is tier 1 and carries no threshold.

## Non-goals

- A body's series trajectory: WP-1811.
- Where a body's origin sits: that question is with the maintainer in issue 1417, which has no WP yet.

## Tasks

- [ ] Measure items 1-3 with `_recharted_and_fresh`: the esd error against a fresh solve on a planted carry, and on a cross-body tie at c ≠ 1. A measured error under the esd's own precision closes that item as a note.
- [ ] Item 1: compose a carry's held components into R₀, or refuse the shape.
- [ ] Items 2 and 3: refuse the cross-body ties the charts cannot serve, which also closes item 3, or run the check after the holds.
- [ ] Item 4: decide and land the profile's route, with its test replacing or keeping `test_a_profile_of_one_turn_direction_of_three_says_why_it_has_no_ends`.
- [ ] Tests for each shape in `tests/test_rigid_body.py`.
- [ ] Skill: a row for any new refusal in the diagnostics reference, or "none" if the code stays `RIGID_BODY_PARTIAL_TURN`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_rigid_body.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #1390; WP-1805, WP-1811, WP-2060; PR #1388.

## Handover log

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1390). Checked against the tree at `541f0daf7` and PR #1388's WP file: the named functions exist as the issue says, and items 1-3 were read, not run; no open WP owns the seam: WP-1805 closes in #1388, WP-1811 owns the carry and not the chart, and WP-2060 owns the profile and not the refusal. Combined because all four sit on `_chart_matrix` and `_recharted_and_fresh`. Next: the measurement, which may retire items.
