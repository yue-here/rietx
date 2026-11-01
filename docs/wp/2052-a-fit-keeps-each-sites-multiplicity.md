# WP-2052 — a fit keeps each site's multiplicity from start to answer

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: 1991 soft (the verb-boundary merge, PR #1014)
Priority: P2 2026-10-26 — a silent wrong composition (10 O for 12, Biso −1.6) on 10 of 16 fits of an unresolved split pair under the default plan; P2 rather than P1 because only split-pair models across a special position meet it, and χ²_red ≈ 24 shows the user something is wrong

## Goal

A fit never changes a site's multiplicity between its own stages or at its closing compile.
When the coordinates a fit returns would give a different multiplicity at a fresh compile,
the result says so with the atoms per cell both ways.

## Context

Issue #1088 (mustachefeeling, 2026-10-21), from scoping #1010 (split sites).

**Mechanism.** Every compile decides each atom's orbit split from its current coordinates:
`model.forward.compile_model` → `crystallography.structure_factor.compile_phase_sites`
→ `select_orbit_ops(sg, xyz)` → `symmetry.site_orbit` against `SITE_TOL = 1e-4`
(an effective 5e-5 on a mirror, where the image moves 2δy). That runs at every stage compile
(`refine.py` `_run_stage`), at the closing stage `RefinementPlan.closing_stage` appends
(WP-2002), and at `Refinement._final_compile`. A half-occupied general atom (the usual way to
write a split pair across a mirror) that a stage drives onto the mirror is therefore counted
at the special multiplicity by the next compile, occupancy unchanged. The site loses half its
atoms. `SITE_SNAPPED_TO_SPECIAL_POSITION` runs once, on the starting coordinates
(`_symmetry_silence_diagnostics`), so nothing names the change.

**Why it is common, not a coincidence.** The split-pair model's cost is even in δ (the
distance off the mirror), so δ = 0 is always a stationary point. Whenever the data do not
resolve a split, the solver converges onto the mirror to its own precision, far inside 5e-5.

**Measured at c0e32ab29** (scripts in the 2026-10-26 triage lane, re-run from the issue's
reproducer: Pnma toy, CW neutron 1.5 Å, 10-150° 2θ; truth O1 on the mirror (4c); model O1
general at y = 0.27, occupancy ½ held; counts by `optimize.qpa.phase_zmv`):

- `predict()`: at occupancy ½, Rwp 0.241 with 10 O per cell for δ ≤ 5e-5, and 7e-7 with 12 O
  from δ = 6e-5. At occupancy 1 the reverse: 6e-7, then 0.673 with 16 O.
- Noise-free data, default closing stage: one-stage and three-stage plans both end with the
  declared stages at cost 1, then the closing stage starts at 61 974 and ends at 32 367.
  Returned: χ²_red 23.2, 10 O per cell, O1 Biso −1.637. Only finding: `BISO_NEGATIVE`.
- Same with the closing stage off (`closing_window_tol=None`): χ²_red 44.5, 10 O, Biso 0.599,
  and `FROZEN_COMPILE_STALE` (info), whose help text advises another stage.
- Adding an occupancy stage: occupancy goes to 1.0000 (`OCCUPANCY_ABOVE_ONE`) and O1 y walks
  to −818.7505, because the y column is zero at the mirror. With the closing stage the
  result returns occupancy 0.5, 10 O and χ²_red 44.5, and the finding quotes the stage's own
  χ² as 9.2e-13 against 123 994 fresh.
- 16 Poisson draws at the issue's counts, default plan (one stage + closing): 10 of 16 return
  10 O per cell with χ²_red 24.0-24.6; 6 stop 1.4e-3 to 2.5e-3 off the mirror with 12 O and
  χ²_red ≈ 1.

**Practice.** GSAS-II (5.8.4 source, read 2026-10-26) fixes a site's multiplicity for the
whole refinement. `Amul` comes from the stored atom record at setup (`GSASIIstrIO.py:1762`),
the structure factor weights every operation by `Mult·frac/nOps` (`GSASIIstrMath.py:1279`),
and the multiplicity is rewritten only when the user edits or transforms the atom
(`GSASIIphsGUI.py:2980`, `GSASIIscriptable.py:5915`, `GSASIIlattice.py:1049`). TOPAS and
FullProf were not checked. Add the row to `docs/practice.md`.

**Invariant.** Frozen-per-stage discreteness (root CLAUDE.md) lists symmetry-op subsets
among what is computed at stage compile. Freezing the split once per fit is stricter than
that invariant, and does not break it.

**Tier.** Named practice (GSAS-II) for the freeze. The report's wording is new judgement
with no threshold: any multiplicity change is reported.

**Note for WP-1991.** Its Priority line says "a refined coordinate cannot drift there". That
holds for a site already special (its coordinate is locked) and fails for a general atom at
partial occupancy, as above. PR #1014's body declares the mid-fit case out of its scope.

**Decision owed before code** (issue #1088's options): (1) decide the split once per `fit()`
and reuse it for every compile, reporting a site whose fresh split differs; (2) report only;
(3) conserve occupancy × multiplicity at a snap (the reporter declines it, as
`gui/symmetry.py::_collisions` does). Record the ruling here as `Decided YYYY-MM-DD: …`.

### Inherited

- 2026-10-31, from the issue triage (issue #1088): the reporter's view on the
  decision owed before code (2026-10-28). Option 1 (decide each site's orbit
  split once per `fit()` and reuse it for every stage compile and the closing
  compile), with option 2 beside it (after option 1, a site whose fresh orbit
  would differ at the end is reported with its atoms per cell both ways, in a
  sentence naming the cause). Not option 3, which rewrites an occupancy the
  caller set. Their grounds are the 2026-10-26 measurements recorded here (the
  closing stage giving 10 O per cell at χ²_red 23.2 on noise-free data, 10 of
  16 Poisson draws failing, O1's y walking to −818.75 under an occupancy
  stage) and GSAS-II reading the multiplicity once at setup. Checked against
  the tree at d87c8cc91: PR #1014 (merged 2026-10-29, WP-1991) covers the verb
  boundaries only. There a part-occupied site at or below occupancy × (images
  before / after) = 1 is left as stored with `SITE_TWINS_KEPT` giving both
  readings, and its PR body states that a stage compile mid-fit is outside it.
  So this WP's mid-fit case is unchanged, and the ruling stays the
  maintainer's.

## Non-goals

- Changing `SITE_TOL` (#215: five-decimal files).
- Merging a site with its own image at a verb boundary: WP-1991 and PR #1014.
- Conserving occupancy × multiplicity at a snap (option 3), unless the ruling picks it.

## Tasks

- [ ] Take the decision above and record it.
- [ ] Find every compile inside one fit that re-decides an orbit split: stage compiles, the
  closing stage, `_final_compile`, the joint fit in `multi.py`, a series pattern's fits in
  `sequential.py`, and rigid-body atoms (#1005).
- [ ] Decide each site's split once per `fit()`/`run_stage()` and pass it to every compile in
  that call (option 1), or carry the multiplicity on the compiled phase.
- [ ] A finding at the end naming each site whose fresh split differs, with atoms per cell both
  ways; and `FROZEN_COMPILE_STALE`'s text stops advising another stage when the gap is a
  multiplicity change.
- [ ] The coordinate walk: a coordinate DOF whose column is zero at a special position walked
  819 cells in one stage. Decide whether to wrap it at the answer or report it.
- [ ] Tests: the issue's toy, noise-free, under the default plan, returns 12 O per cell; the
  `predict()` δ sweep pins both occupancies; a revert of the freeze fails it.
- [ ] Skill: the reference row for the new or changed finding code.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_<this WP's file>.py -q
.venv/bin/python -m pytest tests/test_site_twins_merged.py -q   # once PR #1014 lands
.venv/bin/python -m ruff check src tests examples
```

## References

- International Tables for Crystallography Vol. A (site multiplicity).
- GSAS-II 5.8.4 source, files above.
- Issues #1088, #1007, #1010, #1014, #215, #1005.

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1088). Checked against
  the tree at c0e32ab29: the issue's own script no longer lands inside the snap radius (its
  fit stops 1.1e-3 off the mirror), but the mechanism reproduces on noise-free data and on
  10 of 16 noise draws, and WP-2002's closing stage now exposes a one-stage plan too. No open
  WP owns it: WP-1991 owns the routes into a `Structure` and its PR #1014 declares the
  mid-fit case out of scope; WP-2002 (closing stage) is closed. Next: the decision above.
