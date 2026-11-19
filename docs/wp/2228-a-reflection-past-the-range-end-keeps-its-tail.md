# WP-2228 — A reflection centred past the range end keeps its tail

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2222 (the closing stage off by default); 2075 soft (the report half: a reflection straddling a range end)
Priority: P2 2026-11-19 — a silent wrong answer on a path few fits take: a default Le Bail cell 7-15 esd off, reported `converged`, where a strong reflection sits just past the data's end

## Goal

A reflection that rietx generates because its tail can reach the data has a
window that reaches the data. With that in place, the two closing-stage rules
that work around the range end go: a carried Pawley series no longer forces
the closing stage, and no Le Bail rule is added.

## Context

**What happens.** rietx generates reflections up to `REFLECTION_MARGIN_DEG`
(0.5°) past each end of the fitted range, so that a peak centred just outside
still puts its tail inside. Each reflection is computed over a window frozen
at the stage's start. Since WP-2222 a default fit's window drops 2 % of the
peak's area (`forward.WINDOW_AREA_TOL`). For a nearly Gaussian peak that is
about ±1 FWHM, plus the 0.3° movement slack (`WINDOW_MIN_DEG`). A reflection
centred 0.4-0.5° past the end can therefore be in the list while its window
holds no data channel. Its real tail in the data goes unmodelled.

**Measured 2026-11-19** (macOS arm64, `[dev]`, compiled tier on), on issue
#440's synthetic fluorapatite ramp (`tests/test_pawley.fap_series`: data to
74.99°, FWHM 0.064°, η 0.027, cell +0.3 % over ten patterns). (6 0 2) sits at
75.39° on pattern 2. Its 2 % window, ±0.37°, holds 0 channels; its 0.1 %
window holds 80.

- *Le Bail, single fit from the CIF cell.* The nearest in-data reflection,
  (5 -2 4) at 75.04°, takes the unmodelled tail: intensity 319 at 2 %
  against 9.9 at 0.1 %. The cell follows it. Started 0.067 % off, the cell
  lands 6.9 esd from the truth (Rwp 0.083) against 0.28 esd with the closing
  stage (Rwp 0.041). Started 0.133 % off, 15.0 against 0.37 esd. Both report
  `converged`. A closing stage at 2 % does not help (6.9 esd), so the cause
  is the window and not the extra stage.
- *Localised.* Moving the upper limit from 74.99° to 74.9° drops (6 0 2) out
  of the generated list. The 2 % fit then lands 0.16 esd from the truth.
  Limits of 74.7°, 74.4°, 74.0° and 73.0° give 0.03-0.18 esd at both window
  fractions.
- *Le Bail series.* At the default, carried or re-seeded, the cell reaches 32
  esd off at pattern 5 (Rwp 0.26 against 0.036) and recovers by pattern 7.
  With the closing stage, at 1e-3 or 2e-2, it stays within 3 esd at Rwp
  0.036-0.037. In a chain the extra stage's recompile at the answer is
  enough.
- *Pawley series.* Carried without the closing stage, the cell moves up to
  0.77 esd from the reference at pattern 5 (Rwp 0.0407 against 0.034) and
  recovers by pattern 7. Re-seeded without it, 0.03 esd. Cut at 72°, carried
  without it, 0.05 esd and no Rwp drift. WP-2222's rule forcing the closing
  stage on a carried Pawley chain answers this edge, not the carrying.
- *Unaffected.* Single Pawley and Rietveld fits on the same ramp move under
  0.15 esd with the window fraction. Rietveld's intensities come from the
  structure, so no neighbour can absorb a tail. On real 11-BM NAC, which has
  no such reflection, the Le Bail cell moves 0.01-0.02 esd.

The probe scripts were not kept. The first task rebuilds the decisive one,
the Le Bail single fit at pattern 2, as a test.

**How far a window reaches, against TOPAS.** TOPAS cuts each peak at 0.001
of its own height (`docs/practice.md` § How far a peak is computed).
rietx's 2 % of each peak's own area matches that only for a pure Lorentzian.
For a mixed peak TOPAS's window is wider: 1.6 against 1.0 FWHM at η = 0, 4.2
against 1.6 at η = 0.1, 11.2 against 9.5 at η = 0.6, before rietx's 0.3°
slack. On this ramp TOPAS's window would be ±0.13°. TOPAS would therefore
leave the same tail unmodelled, and its 0.5° margin (`extra_X_right`) is
rietx's.

**Tier.** To be set by the fix: a window rule for reflections whose window
does not reach the data is a new default, tier 2 if it follows a program's
rule, tier 3 otherwise.

**Maintainer's direction, 2026-11-19.** Fix the edge itself (option C of the
session's brief), on established practice, rather than keeping the closing
stage for Le Bail or carried Pawley.

## Practice

Surveyed 2026-11-19, recorded in `docs/practice.md` § A reflection centred
past the range end. **No program has a mechanism for this edge.** TOPAS and
FullProf generate the reflection and give it a free intensity on whatever
sliver of data its window reaches. GSAS-II and RIETAN-FP do not generate it,
so its tail goes unmodelled and a neighbour absorbs it, as here. FullProf
(`Dum = 3`) and RIETAN-FP (`H` in the `.lst`) leave edge reflections out of
R_Bragg and say so in their output. GSAS-II's Pawley help advises against
reflections past the limits. The literature read covers each peak's own
cut-off and nothing about a peak centred outside the data.

So the mechanism is rietx's own, tier 3, and needs the maintainer's
approval. Candidates, from what rietx already has:

- *A window that reaches the data.* A reflection generated inside the margin
  but centred outside the range gets a window sized at
  `CLOSING_WINDOW_TOL`, or at least to the data's end. Its tail is then
  modelled, as at 0.1 % today. Cost: a few windows per fit. Its Le Bail
  intensity rests on a sliver of data: at 0.1 % on the ramp, (6 0 2) took
  2.77e4, ten times the strongest in-range reflection, harmlessly for the
  cell. Pawley's ridge (WP-1459) already bounds that intensity.
- *Not generating it* (GSAS-II, RIETAN-FP). This leaves the tail unmodelled,
  which is the failure measured here. Dropped.
- *Flagging it* (FullProf, RIETAN-FP). Report only, WP-2075's half. It does
  not fix the cell.

## Non-goals

- Reporting a reflection that straddles a range end: WP-2075.
- Windows that follow the parameters during a stage (WP-2047, WP-2051, closed).
- The closing stage's default (WP-2222, ruled).

## Tasks

- [ ] Reproduce the four measurements of § Context as a test on `fap_series` (Le Bail single fit at pattern 2 from the CIF cell, cell within 1 esd of the truth at the default plan)
- [ ] Choose the mechanism from § Practice, measure it on the ramp and on NAC, and bring the choice to the maintainer if practice does not settle it
- [ ] Implement it in `compile_model`'s window sizing; `_audit.py` row for the new default
- [ ] Remove the carried-Pawley closing-stage rule (`SequentialRefinement.fit`) and `tests/test_sequential.py::test_a_carried_pawley_chain_runs_the_closing_stage`; the Pawley series lands within 0.1 esd of the closing answer without it
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected (the fix needs no caller action); say so at handover or add a row if the mechanism leaves the caller a choice

## Acceptance

`.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_pawley.py tests/test_sequential.py -k "range_end or carried or fap"`
green, with the default Le Bail fit of pattern 2 within 1 esd of the truth
and the carried Pawley chain within 0.1 esd of its closing-stage answer.

## Handover log

- **2026-11-19** — created from WP-2222's follow-ups. No open WP owns the
  window at a range end: WP-2075 reports a straddling reflection and changes
  no model. In the same session the maintainer approved
  `Refinement.run_stage:window_area_tol` at tier 2 on TOPAS's cut (the
  `_audit.py` row's `approved`), and the carried-Pawley rule's comment and
  test docstring now name this cause.
