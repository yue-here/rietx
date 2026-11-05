# WP-2055 — the picker holds a line shape the lab pattern does not have

Milestone: unscheduled · Status: ⬜
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

### Inherited

- 2026-10-31, from the issue triage (issue #1166): the reporter ran this WP's
  first task, the direction test, on `main` `2cf637372` (picker and
  `qarr_instrument()` byte-identical to `c0e32ab29`), with arms and a reading
  rule written down before the run. The 16 Oct census and direction reproduce
  exactly (87 at bound, 24 usable above the bar, 19 below 90°; 17 lower : 2
  higher below 90°, p = 0.0007). Declaring each pattern's own fitted Kα2
  weight gives 79 / 19 / 14 and a split of 10 : 4 (p = 0.18), but the drop is
  in the population, not the direction: the 10 low-angle components on the
  bound in both arms move 8 : 2 in both, and the 10 that leave all moved low
  when freed (five shoulders 0.09–0.12° below a line 5–14× stronger become
  `not_separable`; three change their group's count; one becomes `weak_line`).
  Fitted weights range 0.256–0.462, and brucite's fit drives it to 0, which is
  not physical for a Cu tube. Positive arm, synthetic corundum: holding 0.5
  against a true 0.44 shifts Kα1 by about −0.003°, a tenth of the median freed
  move on the real patterns (−0.023°); only a gross mismatch (0.5 held against
  0) puts usable lines on the bound. Their reading: the numbers count against
  the Kα2 weight as the main cause and do not identify the cause; eight of the
  17 declared-arm movers carry `axial_tail`, yet the aperture-fitted arm still
  gives 11 : 5. The task-2 survey of other pickers is still owed. Checked
  against the tree at d87c8cc91: no change to the picker since 2026-10-26.

## Non-goals

- The flag's level (`info`, ruled 2026-10-21) and the false-line bar: WP-1968.
- The steep-flank envelope: WP-1909.
- Layer 0's matching window in the report: WP-1977.

## Tasks

- [ ] Re-run the direction test on this tree: a second solve that re-centres each bound,
      recording each freed component's move and its distance to the pattern's own lattice,
      at the declared Kα2 weight and at a per-pattern fitted one.
- [ ] Survey what other peak pickers hold for the doublet ratio and asymmetry (GSAS-II's
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
