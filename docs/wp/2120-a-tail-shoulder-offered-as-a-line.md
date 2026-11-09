# WP-2120 — a tail shoulder on its position bound is offered as a line

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-06 — false lines reach the engines at full weight, but no case yet moves a cell or costs an indexing row

## Goal

`pick_peaks` does not offer the engines, as a usable line, a component that is the
low-angle tail of a stronger line, or one that a re-seed put at its window's edge to fit a
neighbouring group's tail. Either it is flagged unusable, or this WP records why it stays.

## Context

**Source.** WP-2055's task 1 (2026-11-06, `a84379aac`, `[dev]`, macOS arm64), which asked
why 24 usable components on the 16 IUCr round-robin patterns end on their position bound.
WP-2055 decided the picker keeps the line shape it holds, so these two classes are what is
left, and no open WP owns them: WP-1968 (the false-line bar) and WP-1977 (Layer 0's flank
lobes) are closed, and WP-1909 is the background-flank envelope.

**Class 1, the tail shoulder.** Of the 24, eight are shoulders on the low-angle side of a
4–23× stronger line in the same group. Seven of the eight also carry `axial_tail` and sit
0.076–0.144° from any Kα1 line of their pattern's phases, so the nearest lattice line is the
strong neighbour itself: fluorite 46.918°, sample-1/2 copies at 46.90–46.95°, zircon 43.645°
and 67.674°, brucite 68.034°. Freeing the bound moves all seven further from the lattice. The
eighth (cpd-1f 68.763°, no `axial_tail`) moves onto a lattice line when freed. Declaring each
pattern's Rietveld-fitted Kα2 weight makes all seven `not_separable`, but that weight is not
available before indexing.

**Class 2, the window-edge re-seed.** Two of the 24 (cpd-1b 86.482°, cpd-1c 56.821°) sit
0.5 seed FWHM outside their window's first point. Over all 16 patterns, 120 of 1056
components sit within 0.25 FWHM of a window edge or outside it. All 120 are re-seeds,
56 already carry `duplicate_line`, and 53 are usable.

**Where.** `_axial_tail` and `_flags_for` in `indexing/pick.py`; `PEAK_UNUSABLE_FLAGS` and
`PEAK_UNDRIVEN_FLAGS` in `schemas/indexing.py`; `reseed_candidate` and `_fit_at`'s
`reseed_at` in `indexing/peakfit.py`. `axial_tail` is deliberately out of
`PEAK_UNUSABLE_FLAGS` (WP-1043: 11 unverified usable components on six other lab patterns),
so class 1 asks about the **conjunction** with `position_at_bound`, never about
`axial_tail` alone. WP-2055's harness (direction test, lattice distances, window edges) is
kept outside the tree at `~/.cache/ghostshift/rietx/wp-2055/`.

**Tier.** Making a flag combination unusable is a new judgement. It is measured on one
diffractometer only (the round robin), so the first task is a second family: the other
real lab patterns in `tests/data/` (SRM 660c, the FAP pattern, the certified corundum).
A change to `usable()` moves what every engine is driven by, so it runs
`tests/test_acceptance_indexing.py` and goes to the maintainer as a reader-output change.

## Non-goals

- The line shape the picker holds (Kα2 weight, apertures): decided in WP-2055.
- The flag's level (`info`, ruled 2026-10-21).

## Tasks

- [ ] Measure both classes on a second instrument family: count `axial_tail` ∧
      `position_at_bound` usable components and their distance to the lattice, and the
      usable window-edge re-seeds and whether a neighbouring group already holds their line.
- [ ] Decide, per class, whether it leaves `usable()`, is undriven only
      (`PEAK_UNDRIVEN_FLAGS`), or stays. Record as `Decided YYYY-MM-DD:`.
- [ ] Land it, with `tests/test_acceptance_indexing.py` green.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the `axial_tail` or `PEAK_POSITION_AT_BOUND` reference row if what a reader
      should do changes; else none.

## Acceptance

On the 16 round-robin patterns, no usable component above the false-discovery bar is a tail
shoulder 0.07° or more from every lattice line, with no indexing acceptance row lost; or the
WP records why such a component stays usable.

```sh
.venv/bin/python -m pytest tests/test_peak_bounds.py tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Madsen, I. C. et al. (2001). *J. Appl. Cryst.* 34, 409 (the IUCr CPD round robin).
- WP-2055 (the census and the direction test); issue #1166.

## Handover log

- **2026-11-06** — created from WP-2055's handover. No open WP owns either class: WP-1968
  and WP-1977 are closed, and WP-1909 is the background-flank envelope. *Next:* task 1.
