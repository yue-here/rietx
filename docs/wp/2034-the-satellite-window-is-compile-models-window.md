# WP-2034 — the satellite arm generates over `compile_model`'s window, not a copy of it

Milestone: magnetic · Status: ⬜
Depends on: — (1908, closed: the apparent-position shift both windows widen by; 1326, closed: the arm)
Priority: P3 2026-10-23 — a satellite that should be ranked can go unenumerated near either end of the range, unmeasured on a real pattern; the fix is one shared helper

## Goal

The satellite report arm enumerates reflections over the same Bragg-angle window
`compile_model` uses, through one helper both call. A satellite whose image
under any emission line lands inside the fitted range is enumerated.

## Context

- **Found by `/code-review high` on PR #942 (WP-1908), and left there as
  outside that diff.** It passed to 1326's `### Inherited` on 2026-10-15 and
  moved here at 1326's close, by the maintainer's decision of 2026-10-23.
- **Still true at `12f459e`.** `report/satellites._generation_window`
  (`report/satellites.py:142`) scans the 33-point shift grid that
  `compile_model` scans. It returns
  `(max(tt_min - hi_shift, 0.05), min(tt_max - lo_shift, 179.0))`.
  `compile_model`'s window (`model/forward.py:3812-3813`) subtracts the zero,
  adds `REFLECTION_MARGIN_DEG` (0.5°) on both sides, and caps at 180°. The
  arm's copy differs in three ways. It has no margin. It caps at 179°. And it
  applies the low cutoff in the shortest line's frame without translating it
  from the longest line's. So on a Cu Kα doublet, a satellite whose Kα1 image
  falls just below `tt_min` while its Kα2 image lies inside is never
  enumerated. Both callers (`:175`, `:347`) filter on the apparent position
  afterwards, so a superset is harmless and a subset is the defect.
- **Unmeasured on a real pattern.** No fixture yet puts a satellite in the
  strip either copy disagrees on.

## Non-goals

- What the arm ranks, or the candidate set (WP-1418's M-8).

## Tasks

- [x] A test that fails on the current tree: a synthetic doublet pattern with
      a satellite whose Kα1 image lies below `tt_min` and whose Kα2 image lies
      inside, which the arm must enumerate.
- [x] One helper, called by `compile_model` and by the arm, so the margin, the
      cap and the per-line frame are written once. Every satellite and
      reflection list in the tree is unchanged except where the old window
      cut one off. Name each list that changes.
- [x] Skill: none expected, since no field or code changes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_satellites.py tests/test_satellites_acceptance.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-1908](1908-a-tick-misses-the-displacement-shift.md) (PR #942);
  [WP-1326](1326-satellites-without-a-moment.md).
- #1130: taken by @mustachefeeling, with the plan this WP's handover follows.

## Handover log

- **2026-10-23** — done on `wp2034/satellite-window`, as planned on #1130
  (taken by @mustachefeeling).
  `model.forward.generation_window(tt_min, tt_max, zero, lambdas, shift)` is
  the one window. It holds the zero, the geometry's shift over 33 points of
  the range, `REFLECTION_MARGIN_DEG`, the 180° cap, and the low cutoff
  translated from the longest line's frame to the shortest line's.
  `compile_model` calls it with its compile-time `_shift_est`. The new
  `CompiledModel.generation_window(values)` calls it with the model's own
  `_position_shift_deg` at given values. `report.satellites`'
  `_satellite_positions`, `_lattice_positions` and
  `_centring_forbidden_positions` all call that method, and
  `_generation_window` is gone. `_centring_forbidden_positions` already took
  its `d_max` in the longest line's frame. It now takes both bounds in the
  shortest line's frame, which is the frame the window is returned in.

  *Tests* (`tests/test_satellites.py` § WP-2034, each failing on `12f459e5`).
  - `test_the_arm_enumerates_a_satellite_whose_kalpha2_image_alone_is_in_range`
    has two cases: no shift, and a 0.3 mm displacement with a −0.02° zero.
    The case is (1 0 3/2) of k = (0 0 1/2) on a 4 × 5 × 6 Å `P m m m` cell
    under Cu Kα. The range starts 0.002° below its Kα2 image. On main the
    peak was indexed by nothing (`matched` 0). Here (0, 0, 1/2) matches it
    at 0°.
  - `test_the_arms_lists_are_every_image_in_range_at_a_doublet_edge` has two
    cases: the satellite strip, and the nuclear (1 1 0). The arm's lattice
    list and every zone-boundary candidate's satellite list must equal a
    brute-force enumeration over integer H, placed by `apparent_two_theta`.
    On main the lattice list lacked 28.535099° and the satellite list of
    (0, 0, 1/2) lacked 31.596593°.

  *What moved.* A probe wrapped the window and the arm's three builders. For
  each call it set main's answer beside the new one: main's
  `report/satellites.py` was loaded as a sibling module, and main's
  `compile_model` window formula was run inline. Two runs:
  - the fast selection: 11 250 passed;
  - the 15 slow files that reach the arm or build a report: 91 passed. These
    include the Cu doublet patterns FAP, SRM 660c, SRM 676a and Stephens, and
    the neutron sets.

  Across both runs, all 12 350 `compile_model` windows are bit-identical, so
  no model list moves. Of the arm's lists, 762 were compared, and none lost a
  position. Only the new tests' lists gained one. So no real pattern in the
  tree has a satellite or lattice image in the strip, and the WP's "unmeasured
  on a real pattern" now reads "measured: none reaches it".

- **2026-10-23** — created by WP-1326's close, from its `### Inherited` entry
  of 2026-10-15. No open WP owns the arm's window. 1418's M-8 rewrites the
  candidate generator, not the angular window it generates over.
