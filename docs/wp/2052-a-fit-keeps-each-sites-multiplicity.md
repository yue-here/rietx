# WP-2052 — a fit keeps each site's multiplicity from start to answer

Milestone: unscheduled · Status: ✅ 2026-11-01 — a fit keeps each site's orbit split; SITE_MULTIPLICITY_KEPT names a recount (PR #1307)
Track: What fires, and what stays silent
Depends on: 1991 soft (the verb-boundary merge, PR #1014)

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

Decided 2026-11-01: option 1 with option 2 beside it. Each `fit()` and `run_stage()` decides
every site's orbit split once, from the coordinates it starts at, and hands that split to
every compile it makes, the closing compile included. A site whose returned coordinates
give another split at a fresh compile is reported as `SITE_MULTIPLICITY_KEPT`, with the atoms
per cell both ways. Option 3 is not taken. Settled by Claude under established practice:
GSAS-II reads a site's multiplicity once, at setup, and keeps it for the whole refinement
(the Practice paragraph above). The reporter recommends the same pair. The labels "decision
owed" and "the ruling stays the maintainer's" were written by Claude triage sessions
(43d164c7f, 8609e90dc), so they are evidence rather than a ruling, and none of the
maintainer's triggers holds. The change moves what some fits return, so the PR goes to the
maintainer under the reader-output rule before merge.

## Non-goals

- Changing `SITE_TOL` (#215: five-decimal files).
- Merging a site with its own image at a verb boundary: WP-1991 and PR #1014.
- Conserving occupancy × multiplicity at a snap (option 3), unless the ruling picks it.

## Tasks

- [x] Take the decision above and record it.
- [x] Find every compile inside one fit that re-decides an orbit split: stage compiles, the
  closing stage, `_final_compile`, the joint fit in `multi.py`, a series pattern's fits in
  `sequential.py`, and rigid-body atoms (#1005).
- [x] Decide each site's split once per `fit()`/`run_stage()` and pass it to every compile in
  that call (option 1), or carry the multiplicity on the compiled phase.
- [x] A finding at the end naming each site whose fresh split differs, with atoms per cell both
  ways; and `FROZEN_COMPILE_STALE`'s text stops advising another stage when the gap is a
  multiplicity change.
- [x] The coordinate walk: a coordinate DOF whose column is zero at a special position walked
  819 cells in one stage. Decide whether to wrap it at the answer or report it.
  Decided 2026-11-01: neither. The walk needed the snapped compile, and with the split kept
  it does not recur: the noise-free four-stage plan with an occupancy stage ends 2.3e-6 off
  the mirror, and 16 Poisson draws under the same plan end within 2.7e-3. Settled by Claude
  under that measurement; a revert of the freeze brings the walk back (the test below).
- [x] Tests: the issue's toy, noise-free, under the default plan, returns 12 O per cell; the
  `predict()` δ sweep pins both occupancies; a revert of the freeze fails it.
  `tests/test_site_multiplicity_kept.py`. At occupancy 1 the sweep reads 12 O at both
  offsets now, because WP-1991's construction gate merges that site onto the mirror.
- [x] Skill: the reference row for the new or changed finding code.

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

- **2026-11-01** — handed over, PR #1307. A fit now keeps every site's multiplicity from its
  start to its answer. A split pair written across a mirror that the data cannot resolve used to
  lose half its atoms at the next compile once the solver stopped on the mirror, which it does
  on most draws: on the #1088 toy, noise-free, the default plan now returns χ²_red 1e-16, 12 O
  per cell and O1 Biso 0.600 (the truth), where main returned χ²_red 23.2, 10 O and Biso −1.64.
  The returned coordinates still read as the special position to anything that compiles
  afresh, so the result now says so with `SITE_MULTIPLICITY_KEPT`, giving the atoms per cell
  both ways. The 819-cell coordinate walk under an occupancy stage is gone with the snap. The
  fix holds within one call only: between calls the split is decided afresh, and WP-2053 now
  holds that, with the stored-format question it raises.
  Next: the maintainer reviews the new finding under the reader-output rule (it changes what
  split-pair fits return) and decides whether the freeze needs a row of its own in the audit
  table (*Generality* below).

  *Done.* Decision recorded in § Context (option 1 + 2, settled by Claude under GSAS-II
  practice). `structure_factor.phase_orbit_split` is the one decider; `compile_phase_sites` and
  `compile_model` take a decided split (`ops=`, `orbit_split=`), and `forward.orbit_split_of`
  reads one off a model. `Refinement._decide_orbit_split` decides it at the start of `fit()` and
  `run_stage()` (a nested call, such as a profile-interval refit inside a fit, reuses the
  outer one) and clears it at the end. Users: each stage compile, `_final_compile`, the
  report's `_twin` compiles, and the joint runner's stage and final compiles (`multi.py`, one
  split per histogram, decided in `_run_plan`). A series runs `fit()` per pattern, so it is
  covered. Rigid-body atoms are ordinary `phase.atoms` to the compile, so they are covered.
  The freeze is one-way: a compile keeps a site's images but never withholds ones its current
  coordinates need, so a site leaving a special position (only a rigid body's pose can do that)
  takes its full orbit, as before. `structure_factor._multiplicity_kept_diagnostics` (called
  from `_final_compile` and `multi._final_compiles`, read off the compile the result is
  measured on) raises the new code, losses only. It lives in `crystallography/` so the manual
  lists it on the Structures page; the Refinement page had passed its 50 000-character cap by
  288. Help entry, audit rows (code tier 1 ambiguity 3, suggestion tier 1), silence pair,
  skill row,
  `docs/practice.md` § A site's multiplicity during a fit. `FROZEN_COMPILE_STALE`'s help now says
  its gap is never a change of composition.

  *Measured* (arm64 macOS, `[dev]`). Issue toy, 16 Poisson draws (seeds 1000-1015), one-stage
  plan and a four-stage plan ending in an occupancy stage: all 32 fits χ²_red 0.95-1.03, O1
  Biso 0.57-0.62, |Δy| ≤ 2.7e-3, no walk. 5 of 16 one-stage fits and 6 of 16 four-stage fits
  stop within the site tolerance and carry `SITE_MULTIPLICITY_KEPT`. Main at 62034506e on the
  noise-free toy: one stage 23.2 / 10 O / −1.637; occupancy plan y = −818.75, χ²_red 44.5.
  Mutation checks: forcing a fresh split in `compile_phase_sites` fails three of the new tests
  with exactly those numbers; dropping the split from the joint runner's stage compile fails
  the joint-fit test at χ²_red 23.18. `python -m tests.reader_output`: exit 0, unchanged on the
  standard fit (no site there crosses the tolerance). Fast suite before the review fixes: 5
  failed, 13190 passed, 310 skipped, 32 xfailed; four of the five were this branch's (a page
  cap, the GUI help-key fixture, the joint runner's scope census, the silence pair) and are
  fixed, the fifth is `test_display`'s stale Jupyter kernel spec on this Mac.
  Final fast suite (`-m "not slow"`, arm64 macOS, `[dev]`, no other suite running): 1 failed,
  13199 passed, 310 skipped, 32 xfailed; the failure is `test_display`'s stale Jupyter kernel
  spec on this Mac, unrelated. This branch adds 12 cases in `test_site_multiplicity_kept.py` and
  one silence-pair row; the file costs 2.41 s locally. Full suite not run.

  *Review* (`/code-review high --fix`). Applied: a trial made inside a call inherits its split
  (`_carry_into`); the split length is checked before the species boundary. Applied after
  thinking it through: the one-way rule above (its finding 5, a rigid body leaving a mirror
  kept a half orbit for the whole call). Declined: quoting `SITE_TOL` in the help text (its
  siblings state their tolerances as numbers too). Moved to WP-2053: run_stage between calls,
  the series, `replay`, the CIF writer.

  *Generality* (generality-review, abridged by the author to its verdict lines; the maintainer
  reads the full sections in this session's report). Code row: "weak", because tier 2 and
  ambiguity 1 described the freeze, not the report. Answer: retiered to tier 1, ambiguity 3,
  as `SITE_TWINS_KEPT`. Suggestion row: "weak", because the one-atom reading could name an
  occupancy above 1. Answer: offered only where it is at most 1, with a test at occupancy 1.
  The freeze: "weak", because no row or record field declares it, and in the gaining direction
  GSAS-II weights all operations by Mult/nOps where rietx gives the full orbit at the stated
  occupancy. Answer: the gaining direction is pre-WP behaviour, recorded in
  `docs/practice.md`; a seat for the freeze needs a record field or the maintainer's ruling
  that the code row is its seat, which is left to the maintainer.

  *Not generalised.* Compiles after a call decide afresh from the stored coordinates: a second
  `run_stage` (the GUI's stage path), the next fit, a series' next pattern, `replay`,
  `predict()` on a new grid, `suggest()`'s probe and the CIF writer. The finding names the
  common ones. Keeping the answer's split on the `Refinement` until an edit, and on the node for
  `replay`, would close them; the node half is a stored-format change. In WP-2053's Inherited.

  *Gotchas.* At occupancy 1 the `predict()` sweep no longer shows the 16 O reading this WP's
  Context quotes: WP-1991's construction gate merges that site onto the mirror (occupancy ×
  8/4 > 1), so both offsets read 12 O. One draw (seed 6, occupancy stage) ended 4.4e-4 off the
  mirror at occupancy 0.50005, outside the site tolerance but inside WP-1991's 5e-4 twin band,
  so the next edit or new `Refinement` would merge it and halve the site under
  `SITE_TWINS_MERGED`. That is WP-1991's documented gate, noted here only.

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1088). Checked against
  the tree at c0e32ab29: the issue's own script no longer lands inside the snap radius (its
  fit stops 1.1e-3 off the mirror), but the mechanism reproduces on noise-free data and on
  10 of 16 noise draws, and WP-2002's closing stage now exposes a one-stage plan too. No open
  WP owns it: WP-1991 owns the routes into a `Structure` and its PR #1014 declares the
  mid-fit case out of scope; WP-2002 (closing stage) is closed. Next: the decision above.
