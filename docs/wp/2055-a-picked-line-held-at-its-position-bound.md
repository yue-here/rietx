# WP-2055 — the picker holds a line shape the lab pattern does not have

Milestone: unscheduled · Status: 🔄 2026-11-06 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-26 — a diagnostic that says less than it could: 24 usable lines on 16 round-robin patterns report their position bound as their position, flagged `info`, and no case yet moves a cell

## Goal

A usable line from `pick_peaks` reports a position the data determined, not its window's
bound. Where the bound holds because the line shape the picker holds is wrong (the Kα2
weight, the axial apertures), the picker carries a shape close enough that freeing the
position does not cost an indexing acceptance row.

## Context

**Source.** Issue #1166 (2026-10-25, @mustachefeeling), the follow-up the maintainer asked
for in PR #993's round-2 review ("an issue for the usable components held at their position
bound, so it is not lost").

**Measured at c0e32ab29** (`[dev]`, macOS arm64; `rx.pick_peaks(data,
qarr_instrument())` over the 16 `tests/data/qarr/*.prn`, counting `position_at_bound`, and
among those the usable components not flagged `weak_line`):

| instrument as declared | at bound | usable, above the bar | of those below 90° |
|---|---|---|---|
| `qarr_instrument()` (Kα2 weight 0.5, apertures 0) | 87 | 24 | 19 |
| Kα2 weight 0.40 | 73 | 22 | 17 |
| S/L = H/L = 0.02 | 82 | 21 | 16 |

**The reporter's evidence, not re-run** (16-17 Oct, on the branch before #1085's closing
windows): a second solve re-centring each bound on the converged positions took the 24 to
5 and failed three `test_acceptance_indexing.py` rows (zircon and corundum named). Of the
19 freed below 90°, 17 moved to lower 2θ (two-sided binomial p = 0.001). Fitting
`axial_sl` per pattern left that drift (16 of 18 still down). Fitting the Kα2 weight too
(0.34-0.46 on most patterns) took it to 9 of 13 (p = 0.27). Against each pattern's own
lattice, 19 of the 24 sat within 0.15° of a predicted line; freed, 12 moved away and 7
toward (p = 0.36, no direction).

**Mechanism, untested.** Too much Kα2 on a line's high-angle side pulls the fitted Kα1
component low; the position bound (half the window's seed FWHM from the seed) stops it.
Whether the fitted 0.34-0.46 is an instrument property or a proxy for profile shape the
model lacks is unsettled. The single-weight census above moved the
bound count little, so the direction test, not the count, is the evidence to repeat.

**Where the picker reads its shape.** `peakfit._GroupModel` (`indexing/peakfit.py:179-184`)
takes `source.lines[l].weight` and `geometry.axial_sl/hl` and holds them;
`pick_peaks`' docstring (`indexing/pick.py:59-63`) states the contract. The Kα2 gain is
weight × the two lines' Lp ratio (`peakfit.py:206-232`), because holding the bare weight
biased the Kα1 position (−2e-4°, measured, `peakfit.py:39-43`).

**Rules this meets.** `PEAK_POSITION_AT_BOUND` stays `info` (ruled 2026-10-21 on #993). A
position bound is a correctness parameter of the search, so any change runs
`tests/test_acceptance_indexing.py` (`src/rietx/indexing/CLAUDE.md`: a real ranking
regression once sat under 115 green fast tests). A change to what the picker holds moves
every pick, so the C3 screen and the driven set are re-measured.

**Tier.** Refining the Kα2 weight in the picker would be a default action; it needs named
practice (what other pickers do) or a measurement on several families. Holding a declared
weight is the caller's choice and changes nothing.

### Findings, 2026-11-06 (task 1, re-run on `a84379aac`)

Measured on `a84379aac` (`[dev]`, macOS arm64) with an independent harness kept outside the
tree (`~/.cache/ghostshift/rietx/wp-2055/direction.py`). The second solve starts from each
group's converged state with every position box re-centred on the converged positions, and
keeps the new fit only if it converges, χ² does not rise and no two components swap order.
The population is the usable components above the false-discovery bar that end on their
position bound. Distance to the lattice is to the nearest Kα1 line of the pattern's own
phases (the `test_acceptance_qpa_roundrobin` cells), after a zero and cos θ shift fitted to
the usable lines of groups with no bound hit. The picker has not changed behaviour since
`c0e32ab29`; WP-2030 only added the `instrument_undeclared` field.

| arm | at bound | usable, above the bar | below 90° | freed below 90°, lower : higher | p | toward : away from the lattice | median freed move |
|---|---|---|---|---|---|---|---|
| declared (`qarr_instrument()`) | 87 | 24 | 19 | 17 : 2 | 0.0007 | 8 : 11 | −0.023° |
| each pattern's fitted Kα2 weight | 79 | 19 | 14 | 10 : 4 | 0.18 | 9 : 4 | −0.015° |
| same, brucite left at 0.5 | 79 | 21 | 16 | 12 : 4 | 0.077 | 10 : 5 | −0.019° |
| one Kα2 weight for all, 0.40 | 73 | 22 | 17 | 11 : 6 | 0.33 | 10 : 7 | −0.009° |
| apertures S/L = H/L = 0.02 | 82 | 21 | 16 | 15 : 0 | 0.00006 | 7 : 10 | −0.023° |

The fitted weights are the reporter's (issue #1166, 2026-10-27, the `lines_axial` stage of
the QPA plan): 0.441–0.449 on sample 1, 0.371–0.462 elsewhere, 0.256 on magnetite and 0 on
brucite. Every census and every direction count reproduces the reporter's to the digit. The
toward : away column differs from theirs by one or two, because the lattice shift here is
fitted independently.

**What the 24 are** (declared arm), read component by component and drawn in
`tests/output/wp2055_bound_held_vs_freed.png`:

- **8 shoulders on the low-angle tail of a 4–23× stronger line.** Seven carry `axial_tail`
  and sit 0.076–0.144° from any lattice line of their pattern, so the nearest line is the
  strong neighbour itself (fluorite 46.918°, three sample-1/2 copies at 46.90–46.95°, zircon
  43.645° and 67.674°, brucite 68.034°). They are the strong line's tail, not lines. Freed,
  all seven move further from the lattice. The eighth (cpd-1f 68.763°) moves onto a
  lattice line when freed.
- **2 components at the edge of their window** (cpd-1b 86.482°, cpd-1c 56.821°), each 0.5
  seed FWHM outside the window's first point. The drawn one, cpd-1b's, fits the tail of a
  line in the neighbouring group. Across all 16 patterns, 120 of 1056 components sit within
  0.25 FWHM of a window edge or outside it. All 120 are re-seeds, 56 carry `duplicate_line`,
  and 53 are usable.
- **9 real lines** within 0.05° of a lattice line. Freed, they move −0.024° to +0.057°: five
  closer to the lattice, three further and one unchanged.
- **5 isolated broad components** at 86–142°, 0.08–0.26° from any lattice line.

**Reading.** Declaring each pattern's fitted Kα2 weight removes all seven tail shoulders from
the population: they move into the strong line and come out `not_separable`, which is
unusable. That is the right outcome for those seven. But the same arm adds five new bound-held
components, all 0.08–0.30° from any lattice line, so the count falls only from 24 to
19. Declaring the axial apertures instead makes the low-angle pull stronger (15 : 0). In no arm
does freeing a component bring it closer to the lattice, so the bound is not hiding better
positions. The fitted weight is not an instrument property either: 0 on brucite and 0.256 on
magnetite, on one diffractometer with one Cu tube, mean the weight is absorbing profile shape
the model lacks. The reporter's synthetic corundum arm (not re-run here) agrees: a weight held
at 0.5 against a true 0.44 moves Kα1 by −0.003°, a tenth of the median freed move.

## Non-goals

- The flag's level (`info`, ruled 2026-10-21) and the false-line bar: WP-1968.
- The steep-flank envelope: WP-1909.
- Layer 0's matching window in the report: WP-1977.

## Tasks

- [x] Re-run the direction test on this tree: a second solve that re-centres each bound,
      recording each freed component's move and its distance to the pattern's own lattice,
      at the declared Kα2 weight and at a per-pattern fitted one.
- [x] Survey what other peak pickers hold for the doublet ratio and asymmetry (GSAS-II's
      peak fit, FullProf's WinPLOTR, DICVOL's input lists, TOPAS's peak-fit mode); add a
      `docs/practice.md` section.
- [ ] Decide, from the two above, whether the picker refines the Kα2 weight (or an
      aperture) per pattern before fitting lines, or reports the bound as today. Record
      as `Decided YYYY-MM-DD:`.
- [ ] Land it, with `tests/test_acceptance_indexing.py` green and the census table
      re-measured.
- [ ] Tests + obs/calc/diff PNGs of three bound-held lines before and after to
      `tests/output/`.
- [ ] Skill: the `PEAK_POSITION_AT_BOUND` reference row, if what it means changes; else
      none, because the flag's help entry already says the position is the bound's.

## Acceptance

On the 16 round-robin patterns, the usable components above the false-discovery bar that
end on their position bound fall from 24, with no indexing acceptance row lost; or the WP
records why holding the declared shape is right and the census stands.

```sh
.venv/bin/python -m pytest tests/test_peak_bounds.py tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Madsen, I. C. et al. (2001). *J. Appl. Cryst.* 34, 409 (the IUCr CPD round robin).
- Issue #1166; PR #993 and its round-2 review; WP-1968.

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1166). Checked against
  the tree at c0e32ab29: the census reproduces exactly (87 components on their position
  bound, 24 usable above the bar, 19 below 90°); declaring the Kα2 weight at 0.40 gives 73,
  22 and 17, so the count barely moves and the reporter's direction test is the evidence
  to repeat. No open WP owns it: WP-1968 owns the flags and the false-line bar and has
  only PNGs open; WP-1909 is the steep-flank envelope; WP-1977 is the report's Layer 0.
  *Next:* task 1.
