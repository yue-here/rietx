# WP-2141 — A declared peak on its floor reads the bound test

Milestone: unscheduled · Status: 🔄 2026-11-13 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: 1914 soft (PR #1506 lands the same reading for widths)
Priority: P3 2026-11-09 — a diagnostic that can stay silent under `solver="trf"` on a declared peak with no area; the default LM solver lands the area exactly on its floor, so default fits are right

## Goal

`EXTRA_PEAK_NO_INTENSITY` fires where the package's one bound test (`staged.bound_findings`,
read as `FLOOR_HIT`) says a declared peak's area sits on its floor, under either solver and in a
joint fit.

## Context

- **What the code does.** `refine._extra_peak_diagnostics` decides "this declared peak has no
  area" with its own proximity test: `area <= 0` or `|area - lo| <= BOUND_HIT_RTOL·max(1, |lo|)`
  (`BOUND_HIT_RTOL` = 1e-10). The docstring calls this the bound test's distance "where no solve
  stands behind it". A solve does stand behind it here.
- **Why it can miss.** Since WP-1938 the default LM driver lands a floored value exactly on its
  bound, so the proximity test holds. TRF keeps its iterates strictly inside the bounds and stops
  just above the floor. WP-1914 measured that on a width: `gauss_size` stored 3.4×10⁻²⁴ deg²
  under TRF, read as a 4.3×10¹³ Å domain size while `FLOOR_HIT` beside it said the width was on
  its floor. An area stopped the same distance above zero escapes a 1e-10 window. Not measured on
  a declared peak.
- **Order in a joint fit.** `multi.py` calls `_extra_peak_diagnostics` inside its per-histogram
  loop (line 2508 on 2026-11-09), before `bound_findings` runs (line 2546), so the bound test's
  answer does not exist yet when the peak is judged. The single fit calls it from
  `_build_result` (`refine.py`, after the ticks); check whether the bound findings exist there.
- **The rule to follow.** Yue ruled on 2026-10-09 that a reading at a floor reads the flag ("read
  the flag", recorded in WP-1914's Inherited, from WP-1929). WP-1914's PR #1506 does that for
  widths: `microstructure_table(floors=)` reads a width named by `FLOOR_HIT` as `at_zero`, wired
  through `refine._build_result` and, for joint fits, `multi._hist0_floors`. `replay` runs no bound
  test, so it reads the recorded `FLOOR_HIT` diagnostics. Reuse that wiring once #1506 merges.
  Root CLAUDE.md states the same rule as an invariant: where a fact has a computing authority, a
  second surface is a projection of it, never re-derived.
- **Found by** WP-1914's sibling sweep (PR #1506, *Siblings*). No open WP owns extra peaks:
  WP-1103 (✅) shipped `PeakComponent`.
- **Tier.** No threshold changes: the code stops using its own and reads the authority's. Tier 1.

## Non-goals

- `report/magnetic._width_support_findings`, which has the same shape (a 1e-12 proximity) but
  only picks which cause an info message names; magnetic-path decisions are Mike's.
- `EXTRA_PEAK_ON_REFLECTION`, the other half of the same function.

## Tasks

- [ ] Read `FLOOR_HIT` (or `bound_findings` directly) in `_extra_peak_diagnostics`; keep the
      `area <= 0` clause for an area whose stated lower bound is below zero.
- [ ] In the joint fit, run the bound test before the extra-peak diagnostics, or pass its
      findings in.
- [ ] `replay` reads the recorded `FLOOR_HIT` diagnostics, as WP-1914's fallback does.
- [ ] Tests: a declared peak with no feature under it, fitted under `lm` and `trf`, single and
      joint; the code fires in all four. Pin the rule, never where TRF stops.
- [ ] Find the remaining siblings: any other reader deciding "on its floor" by its own distance.
      Fix the class or say which were left and why.
- [ ] Skill: none; the code's row and suggestion are unchanged.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extra_components.py tests/test_multi_diagnostics.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1914 (PR #1506), WP-1929 (the bound test's active set), WP-1938 (native bounds), WP-1103.

## Handover log

- **2026-11-09** — created, from WP-1914's sibling sweep (PR #1506). No open WP owns extra peaks;
  WP-1103, which shipped them, is closed. Read against the tree at `origin/main` on 2026-11-09:
  the proximity test and the joint-fit call order are as described; nothing was run. Numbered
  2141, past the 2130s, because another shift is filing GUI WPs there today. Bookkeeping PR:
  #1513. Next: wait for #1506 to merge, then reuse its `floors=` wiring.
