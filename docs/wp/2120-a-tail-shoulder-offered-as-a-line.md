# WP-2120 — a tail shoulder on its position bound is offered as a line

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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
`axial_tail` alone. WP-2055's harness (direction test, lattice distances, window edges) was
kept outside the tree at `~/.cache/ghostshift/rietx/wp-2055/`. *Superseded in part
2026-11-16:* that directory is gone, and task 1's findings below come from a new harness.

**Tier.** Making a flag combination unusable is a new judgement. It is measured on one
diffractometer only (the round robin), so the first task is a second family: the other
real lab patterns in `tests/data/` (SRM 660c, the FAP pattern, the certified corundum).
A change to `usable()` moves what every engine is driven by, so it runs
`tests/test_acceptance_indexing.py` and goes to the maintainer as a reader-output change.

### Findings, task 1 (2026-11-16, `bc77a934e`, `[dev]`, macOS arm64)

WP-2055's harness was no longer on disk, so a new one measured both classes. It runs
`pick_peaks` on each pattern with its acceptance suite's own instrument. The lattice is the
Kα1 lines of the pattern's phases (the round-robin start cells, the SRM 660c and SRM 1976a
certified cells, the GSAS fluorapatite cell). Each pattern's offset
z + s·cosθ + t·tanθ is fitted on its strong, unflagged, matched lines (I/σ_I ≥ 20). The
residual rms of those lines is 0.002–0.022° on the round robin, 0.0012° on SRM 660c, 0.006°
on fluorapatite and 0.0022° on SRM 1976a. Distances below are after that offset. The second
family is three unrelated lab instruments: SRM 660c (NIST, graphite monochromator,
R = 217.5 mm), the GSAS-II fluorapatite tutorial pattern, and SRM 1976a on an X'Pert with an
X'Celerator (R = 240 mm). The "certified corundum" this WP named is read as SRM 1976a. SRM
676a is `qarr/corundum.prn`, which is the round robin itself.

**The census has moved since WP-2055.** The round robin now has 31 usable components on their
position bound, where WP-2055 counted 24. Class 1 is still eight components, but brucite 71.800°
now carries `axial_tail` in place of cpd-1f 68.763°. Class 2's counts are unchanged:
120 of 1056 components, 56 of them `duplicate_line` and 53 usable.

**Class 1** (usable ∧ `axial_tail` ∧ `position_at_bound`):

| family | n | above the FDR bar | sits below its strong mate by | ratio | distance to the lattice |
|---|---|---|---|---|---|
| round robin | 8 | 8 | 0.75–0.95 FWHM | 4.1–13.7× | 0.070–0.142° (seven); 0.011° (brucite 71.800°) |
| SRM 660c | 1 | 0 (`weak_line`) | 0.82 FWHM | 6.1× | 0.038° |
| SRM 1976a | 2 | 2 | 0.62–0.75 FWHM | 4.0–6.7× | 0.038, 0.039° |
| fluorapatite | 0 | — | — | — | — |

In 10 of the 11 the nearest lattice line is the strong mate's own line. The mate sits on that
line (|Δ| ≤ 0.050°) and the component sits below it on the tail side. Nothing in the phase list
puts a line at the component, so in all ten it is a tail by attribution. The eleventh is brucite
71.800°, which is 0.011° from brucite (112). A Rietveld fit of `brucite.prn` (the round-robin QPA
protocol with texture, Rwp 18 %) gives (112) 0.25 % of (201)'s intensity, but the component is
24 % of its mate. So the component's area is about 100 times what the line under it can supply.
By position it is on the lattice, and by intensity it is the (201) tail. In degrees the distances
scale with the line width: the shoulders sit 0.62–0.95 fitted FWHM below their mate in every
family. That gives 0.07–0.14° on the round robin (FWHM 0.11–0.23°) and 0.04° on the
narrow-line instruments (FWHM 0.05–0.07°). The acceptance's 0.07° is therefore a round-robin
number. On SRM 1976a the same tails sit inside it.

**Class 2** (usable re-seeds within 0.25 seed FWHM of their window's edge, or outside it):

| family | usable | above FDR | outside the window | ≥ 0.07° off the lattice | a neighbouring group holds the same lattice line | on the lattice, held by no neighbour |
|---|---|---|---|---|---|---|
| round robin | 53 | 46 | 29 | 43 | 35 | 7 |
| SRM 660c | 0 | — | — | — | — | — |
| SRM 1976a | 1 | 1 | 0 | 1 | 1 | 0 |
| fluorapatite | 4 | 2 | 4 | 2 | 3 | 0 |

The window edge does separate the false lines from the true ones on the round robin. Of the
usable components above the bar there, 38 of 46 edge re-seeds are ≥ 0.07° off the lattice,
against 28 of 97 inner re-seeds and 62 of 628 detected components. But six of the 46 are on a
lattice line that no other group holds. Taking class 2 out would lose those six lines. The
second family has three such components in all, too few to measure the rule on.

## Non-goals

- The line shape the picker holds (Kα2 weight, apertures): decided in WP-2055.
- The flag's level (`info`, ruled 2026-10-21).

## Tasks

- [x] Measure both classes on a second instrument family: count `axial_tail` ∧
      `position_at_bound` usable components and their distance to the lattice, and the
      usable window-edge re-seeds and whether a neighbouring group already holds their line.
- [x] Decide, per class, whether it leaves `usable()`, is undriven only
      (`PEAK_UNDRIVEN_FLAGS`), or stays. Record as `Decided YYYY-MM-DD:`.
      **Decided 2026-11-16 (class 1): it leaves `usable()`.** A new flag, `tail_shoulder`,
      is raised on the conjunction and is in `PEAK_UNUSABLE_FLAGS`, while neither flag
      alone moves. The rule is no bar of ours: it combines two existing flags, and the
      acceptance above sets the outcome. Task 1 found every such component on three lab
      families to be its mate's own tail. Undriven-only was weighed and rejected: it keeps
      the shoulder in scoring, so every candidate would be charged for not indexing a
      "line" that is the strong line's tail. That is the case `PEAK_UNUSABLE_FLAGS`
      exists for (`not_separable`'s "a shape, not a line"). It is still a new judgement
      (tier 3) and a reader-output change, so it goes to the maintainer.
      **Not decided (class 2): it stays usable, and the question goes to the maintainer.**
      Placing it needs a bar the WP does not set: how near a window's edge a re-seed must
      sit (WP-2055's 0.25 seed FWHM was a census window, not a rule). On the round robin
      that bar would also take six on-lattice lines no other group holds. The second
      family has three such components, too few to measure on.
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
