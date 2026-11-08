# WP-2113 — a background band read as unmatched peaks

Milestone: unscheduled · Status: 🔄 2026-11-08 — claimed by @mustachefeeling
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-05 — the count moves no ranking and the fit's residual plot shows the band, but the reader's impurity evidence says 72 on a pure phase

## Goal

A smooth band of background misfit in an indexing validation fit is not counted as dozens of unmatched
observed peaks, so `unmatched_observed` and `INDEX_IMPURITY_LINES` mean what a reader takes them to
mean: lines the cell does not own.

## Context

**Source.** Issue #1382, finding 1, left open when WP-1909 closed (PR #1380). Its finding 2 went to
WP-2078.

**Measured at `541f0daf7`** (`[dev]` venv, arm64 Mac): `tests._synthetic_silicon.silicon_pattern("steep")`,
a background falling from about 2300 to about 800 counts over 11-22°.
`rx.index_pattern(peaks, data=data, instrument=rx.Instrument.bragg_brentano(radiation="CuKa"),
two_theta_limits=(10.0, 110.0), preset="quick")` ranks cubic F a = 5.431 Å first, 8 of 8 lines, found
by all three engines. Its validation fit reports Rwp 0.0981, GoF 3.42 and **72 `unmatched_observed`**,
starting at 10.03°, on a pattern with no line below 28.4°. The next two candidates report 67 each. The
issue's reading matches: Δ/σ runs from about +10 at 10-17° to about −9 at 22-26° and +5 again above 108°.
Its plot is `tests/output/indexing_silicon_steep_validation.png`, once #1380 has landed the writer.

**The seam.** `indexing/workflow.py`, `validate_by_lebail`: `validation_plan(...)` chooses the fit, and
`build_layer0(result).unmatched` supplies the count (kind `unmatched_obs`). Layer 0 reads a residual
channel at Δ/σ ≥ 5 with no tick within 0.08° as a peak, one row per local maximum, so a band gives many
rows. `indexing/diagnostics.py` turns the count into `INDEX_IMPURITY_LINES`, whose suggestion ends "If
most of the pattern is unmatched, treat the cell as wrong". `consensus.py` deliberately does not read the
count, which is why the ranking does not move.

**What exists beside it.** WP-1977 (closed) gave each residual peak flank evidence, which covers the flank
lobe of a *profile* misfit, not a smooth band of *background* misfit. WP-1542 is about a Le Bail background
left at its seed, and this validation is Pawley (`VALIDATION_MODE`). WP-2074 would report where a residual
is coherent, and it fires no code.

**Two routes, not yet compared.** Let the validation's background follow the data (a higher order, or the
P-spline). Or let the unmatched count require a peak's shape, so a run of channels along one band counts
once or not at all. The first changes a fit every `index_pattern` call pays for, and the second touches
Layer 0, which every report reads.

**Tier.** A shape test on the residual is new judgement: name the families (this silicon, the indexing
acceptance lists, and a two-phase list where the unmatched lines are real), with the known impurity as
the reference. It answers by kind 3: report the number with its meaning.

## Non-goals

- The ranking, which this count does not enter.
- `FitReport` Layer 0 reading on an ordinary fit, unless the chosen route is there.

## Tasks

- [x] Measure both routes on the steep and flat silicon and on a two-phase list with real impurity lines: the count, the fit's cost, and whether a real line stays counted. (2026-11-08, table in the handover log; the choice between them waits on a ruling.)
- [ ] Land the chosen route, with its `_audit` row.
- [ ] Tests: the steep silicon reports no unmatched line below 28°, and a planted impurity line stays reported. PNGs to `tests/output/`.
- [ ] Skill: the `INDEX_IMPURITY_LINES` row if its meaning changes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_peak_picking_flank.py tests/test_acceptance_indexing.py
```

## References

- Issue #1382; WP-1909; WP-1977; WP-2074.

## Handover log

- **2026-11-08** — measured both routes, landed nothing (PR #1472, draft). Tree `63d7c120a`, `[dev]` venv,
  arm64 Mac. Candidate: the cubic F a = 5.4311 Å cell `index_pattern(..., preset="quick")` ranks first on the
  steep silicon (72 unmatched, Rwp 0.0981, reproduced), validated with `validate_by_lebail(..., peaks=,
  two_theta_limits=(10, 110), with_result=True)`. Route A swaps `Instrument.background` before the fit; route B
  re-reads the default fit's residual with `find_peaks(..., prominence=5)` (B1; adding a 0.5° cap on the width at
  half prominence changed one row by one). "+imp" plants six pseudo-Voigt lines (FWHM 0.06°, 400-1500 counts,
  Poisson seed 2) at 20, 24, 35, 41, 52 and 63°; 20 and 24° sit on the band.

  | pattern | route | bkg terms | unmatched | below 28° | planted kept | Rwp | GoF |
  |---|---|---|---|---|---|---|---|
  | steep | default Chebyshev | 4 | 72 | 56 | — | 0.0981 | 3.42 |
  | steep | A: `auto_background(kind="chebyshev")` | 16 | 0 | 0 | — | 0.0289 | 1.01 |
  | steep | A: Chebyshev 12 | 12 | 0 | 0 | — | 0.0295 | 1.03 |
  | steep | A: `auto_background()` P-spline, λ 1 | 15 knots | 16 | 16 | — | 0.0450 | 1.57 |
  | steep | B1: prominence ≥ 5σ | 4 | 5 | 0 | — | 0.0981 | 3.42 |
  | steep+imp | default | 4 | 73 | 55 | 6/6 | 0.1028 | 3.59 |
  | steep+imp | A: auto Chebyshev | 16 | 6 | 2 | 6/6 | 0.0454 | 1.59 |
  | steep+imp | A: P-spline | 15 knots | 20 | 16 | 6/6 | 0.0566 | 1.98 |
  | steep+imp | B1 | 4 | 10 | 2 | 6/6 | 0.1028 | 3.59 |
  | flat | default, A (all three), B1 | 4/5/12/15 knots | 0 | 0 | — | 0.027-0.030 | 1.00-1.12 |
  | flat+imp | default, A (all three), B1 | 4/5/12/15 knots | 6 | 2 | 6/6 | 0.040-0.042 | 1.49-1.57 |

  Cost: every validation fit took 0.06-0.11 s whichever background (eight reflections; real patterns not timed),
  and `auto_background` takes 0.02-0.04 s, paid once per `index_pattern` call since it reads the data only. B1's
  five steep rows all sit above 49° (four of them 49.16, 59.57, 66.53 and 108.28°, the last in the band's
  upper end); their cause was not read.
  Reading: route A with the existing data-sized Chebyshev (`auto_background`, BIC + Durbin-Watson) removes the
  band entirely, keeps every planted line including the two on the band, and is machinery the package already
  has; the P-spline at its default λ is too stiff for this band. Route B also keeps every planted line but adds
  a tier-3 constant to the Layer 0 every `FitReport` reads, and leaves the validation at Rwp 0.098.
  **Question for the maintainer:** land route A (validation background sized by
  `auto_background(kind="chebyshev")` over `two_theta_limits`, once per call), which changes a fit every
  `index_pattern` call pays and the validation Rwp/GoF each candidate reports, or route B, or neither? Not
  measured yet, and owed before either lands: `tests/test_acceptance_indexing.py` under the chosen route (the
  ranking does not read the count, but the grade's inputs were not checked). Next: the ruling, then tasks 2-4.
  Probe script kept outside the repo (maintainer-local scratch).
- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1382, finding 1). Checked against the tree at `541f0daf7`: reproduced to the issue's numbers, 72 unmatched at Rwp 0.098 and GoF 3.42; no open WP owns it: WP-1977 is closed and covers flanks, WP-1542 is the Le Bail route, and WP-2074 fires nothing. Next: measure the two routes.
