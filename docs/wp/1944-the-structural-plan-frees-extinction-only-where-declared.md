# WP-1944 — the structural plan frees extinction only where it says it does

Milestone: unscheduled · Status: 🔄 2026-11-04 — option A built; PR #1391 ready for review, two questions for the maintainer
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-11 — a plan frees a parameter its description says it leaves alone, and the esd shows the data cannot see it; nothing fires

## Goal

`mccusker_structural` frees extinction on exactly the phases its description
says, and every text describing the stage says the same thing as the code.

## Context

**The report (issue #877).** `PLAN_INFO["mccusker_structural"]`
(`strategy/staged.py`) says the plan frees "preferred orientation,
extinction and surface roughness where declared". The stages, checked at
`f11e22d3`:
- `Stage("preferred_orientation", ["phases.*.preferred_orientation.r"])`
  matches only phases that declared a PO block (`Phase.preferred_orientation`
  defaults to `None`).
- `_ROUGHNESS_STAGE` frees `instrument.geometry.surface_roughness.*`, an
  opt-in block that defaults to `None`.
- `Stage("extinction", ["phases.*.extinction"], seed=1e-3)` matches every
  phase. `Phase.extinction` is a plain `Parameter` at 0 (`schemas/structure.py`),
  and a PbSO₄ table at `f11e22d3` lists `phases.0.extinction` as refinable
  with nothing holding it.

So "where declared" is true for two of the three. The filer's agent fitted
the PbSO₄ round-robin neutron pattern with this plan and got extinction
1.2(3.5) µm² with no diagnostic (filer's numbers, `bdaa7b62`).

**Three texts make the claim, and one is accurate.**
- `PLAN_INFO`'s description: "where declared", false for extinction.
- The comment above `Phase.extinction`: "it is opt-in and never perturbs a
  structure that does not free it". The plan frees it unasked.
- The skill's plan table (`docs/skill/rietx/SKILL.md`): "PO, extinction,
  roughness", which is accurate for the code as it stands.

**Who depends on the current behaviour.** 29 files in `tests/`, `examples/`,
the manual and the skill name the plan. `test_extinction.py::
test_mccusker_structural_frees_extinction_after_displacement` pins the glob
and the seed. Which golden numbers move if extinction becomes opt-in is not
measured. Task 1 measures it.

**Decided 2026-10-11** (the maintainer, at the issue triage; posted on
#877): measure first. Neither fix is chosen until task 1's count exists. A
plan where extinction is rarely significant favours the opt-in, and one
where it often is favours correcting the texts.

**Decided 2026-11-03:** option A, the opt-in (the maintainer, on task 1's
count). `Phase.extinction` defaults to `None`, and the structural plan frees
it only on a phase that declares it. The ruling approves the stored-format
change. The PR still goes to the maintainer before merge, because it changes
the stored format. A second ruling the same evening widened the WP: opt-in
physics must be findable from a fit's output (§ Handover log, 2026-11-04).

**The sibling class, not generalised here.** A freed parameter the data do
not determine, reported with no diagnostic. WP-1523 settled it for a phase
scale (significance under 3σ, `refine._answer_significance`). WP-1914 owns
it for a sample-broadening coefficient at its softplus floor. This WP fixes
the plan and its texts. A general "esd exceeds value" diagnostic is not in
it.

### Inherited

- **2026-10-24, from [2044](2044-the-sabine-laue-factor-is-continuous.md):
  the QPA guide's free fit moved.** With Sabine's Laue factor continuous, the
  guide's first fit (11-BM NAC + CaF₂, `mccusker_structural`) gives CaF₂
  3.58 ± 3.53 wt% and extinction 1919 ± 4066 µm², the same on macOS and Linux,
  where 1.9.0 gave 3.09 ± 2.32. `HIGH_CORRELATION` reads scale ~ extinction at
  ρ = +0.998. That fit is this WP's worked case: an extinction the data cannot
  see, freed by the plan on a weak phase. The held fit is unchanged at
  1.37 ± 0.07 wt%. Re-pin `examples/guides/qpa.py` and its page if this WP
  changes what the plan frees.
  The fit moves a quoted weight fraction by more than the fraction itself,
  which may move this WP's priority row (noted by WP-2043).

## Non-goals

- A general significance diagnostic for every freed parameter (above).
- The extinction model itself (`model/extinction.py`, WP-0506, WP-1451).

## Tasks

- [x] Measure: every acceptance fixture and example that runs
      `mccusker_structural`, with the extinction value and esd each ends at.
      Count those where extinction is significant (over 3σ) and those where
      it is not.
- [x] Decide on that count, and record it here as `Decided YYYY-MM-DD:`. One
      option corrects the description and the schema comment to say every
      phase. The other makes the stage free only declared phases: an opt-in
      `Phase.extinction` defaulting to `None` like PO, with old files that
      store a value opening unchanged.
- [x] Implement the decision. Update `test_extinction.py`, and the skill
      table if its text changes. A changed golden says which number moved
      and why.
- [x] Tests + obs/calc/diff PNGs to `tests/output/` for any fit whose number
      moves.
- [x] Skill: the plan table row in `SKILL.md` matches the code; nothing else
      expected.

## Acceptance

`PLAN_INFO`, the schema comment, the skill table and the stage agree, and a
test asserts which phases the extinction stage frees on a two-phase model
with one phase declared and one not.

```sh
.venv/bin/python -m pytest tests/test_extinction.py tests/test_capabilities.py tests/test_skill.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #877.
- Sabine, T. M. (1988). *Acta Cryst.* A44, 368, and Sabine, Von Dreele &
  Jørgensen (1988), *Acta Cryst.* A44, 374 — the extinction model
  (`model/extinction.py` carries the full list).

## Handover log

### 2026-11-04 (2nd session) — merged with main, review fixes, PR #1391 ready

The branch now sits on current main and is up for review as PR #1391. The
code review's fixes move one quoted number: the skill's diagnostics row
now gives NAC's score as 8.1, the value this file's table already held,
in place of 4.4. A second defect the
review found predates this WP and is filed as WP-2088: assigning a
parameter to a field that declares a range drops the range. This WP's own
opt-in follow-up is renumbered WP-2087, because PR #1406 claims 2086.

*Done.* `1e50a6f01`: the code review's six accepted fixes (an assigned
`Parameter` or dict for `extinction` inherits min, max and unit in
`Phase._declare_extinction`; partner columns move θ through
`table.decode`, so a rigid body or distortion mode is one column; the
partner pattern covers every atom parameter; only the phases a column
reaches are re-evaluated; dead checks removed). Declined: a threshold
constant of its own, which is the maintainer's question. `4e1ef2dbc`:
origin/main merged (182 commits). Main had split the refinement
diagnostics page too (Stages and plans, Background selection); both
splits are kept, with Corrections beside them. WP-2088 filed.

*Measured.* Fast selection on the merged tree (worktree `.venv` `[dev]`,
darwin arm64, Python 3.12, `-n auto`, through the ghostshift serial
lock): 2 failed, 13 809 passed, 319 skipped, 36 xfailed in 715 s. The
two reds were `test_skill_cli`'s committed-copy drift after the merge,
re-synced in `b108e1a72`; that file with `test_skill.py` and
`test_docs_consistency.py` then gave 212 passed. The four added tests
cost 1.72 s together, all in `test_extinction.py`, 1.64 s of it
`test_an_undeclared_extinction_the_strong_lines_ask_for_is_named`.
`tests.reader_output` exits 0 against the merge-base: the standard LaB6
fit frees no extinction and the new warning stays silent there.
Plots of the qpa guide (undeclared, Rwp 0.0884; CaF₂ declared, Rwp
0.0828) and the hump guide's Si fit (Biso 0.4245 ± 0.0116, Rwp 0.1165)
match the re-pinned numbers. In the qpa zoom the CaF₂ line near 7.5°
is calculated slightly above observed, the signature the pointer
scores at 14.6, under its gate. The Si fit's largest residual sits on
its strongest line with observed above calculated, the opposite sign
to extinction. The full selection did not run. This session changed a
diagnostic and merged main, and the acceptance suites run in the
nightly job once the branch lands.

*Next:* the maintainer reviews PR #1391 and answers its two questions:
`EXTINCTION_UNDECLARED` at tier 3 with grounds and an approval, and a
threshold of its own or the air-scatter 25. Either is a row edit in
`_audit.py`. Then WP-2087, starting with the Stephens action.

- **2026-11-04** — extinction is now off unless a phase declares it, and a fit
  says when a phase's strongest lines ask for it. The structural plan no
  longer frees a coefficient the data almost never determine (1 value in 98
  passed 3σ over 69 fits, a false positive), and that pulled a 1.3 wt %
  impurity to 3.6 ± 3.5 wt %. The cost is
  that a real extinction now needs a declaration, and the pointer that names
  it misses a weak one (0.5 µm² planted on LaB6 scores 14 against a gate of
  25). Every other opt-in correction was checked for a pointer; three lack
  one and are filed as WP-2087.

  The maintainer's two rulings, recorded as given:

  > RULING 1 (Yue, 2026-11-03 ~21Z): "we shouldn't have extinction as a
  > default in the most popular plan. opt-in only."

  > RULING 2 (Yue, same evening): opt-in physics must be FINDABLE — "check
  > this for extinction and any other opt-in features."

  Ruling 1 chose option A and approved its stored-format change, with the PR
  still going to the maintainer before merge. Ruling 2 added three parts:
  an evidence-gated pointer for extinction, a sweep of every opt-in
  correction for a discovery path, and a test that no preset frees a
  correction the model does not declare.

  *Option A, as built.* `Phase.extinction: Parameter | None = None`. A number
  declares it (`phase.extinction = 0.0` becomes a parameter bounded at 0 in
  µm²). A stored value from an older file opens unchanged, as a declaration.
  An undeclared phase has no table entry, so no glob can free it, and the
  forward model skips the factor at compile. The writers (CIF, TOPAS `.inp`,
  FullProf `.pcr`) treat an undeclared phase as extinction off.

  *The pointer.* `EXTINCTION_UNDECLARED` (warning) is the air-scatter
  screen's one-column score test on the extinction column at 0. The column
  is projected off the background, every phase's scale, and each free column
  of θ that reaches a Biso, ADP, occupancy, coordinate, PO or texture entry,
  moved through C. The score is in reduced-χ² units with the esd inflation
  included, so it reads as the squared significance a declared coefficient
  would be reported at. It fires at the air-scatter screen's level, 25 (5σ),
  reused rather than a new number. Measured with the gate off, after the
  generality review's fixes (all development data):

  | fit | score | |
  |---|---|---|
  | LaB6 synthetic, ext 2.5 planted | 230 | fires |
  | the same, Biso and B coordinate free | 78 | fires |
  | LaB6 synthetic, 0.5 planted | 14 (9 with Biso free) | silent: a miss |
  | LaB6 synthetic, none planted | 0.17 (1.8 with Biso free) | silent |
  | 11-BM NAC + CaF₂ (QPA guide) | NAC 8.1, CaF₂ 14.6 | silent |
  | Si 640c (hump guide) | 0.13 | silent |
  | FAP (interval guide) | leans negative | silent |

  Two earlier forms were measured and dropped. Projected off the phase's own
  scale and the background alone, NAC scored 277 and CaF₂ 1945, against
  refit significances of 2.8σ and 0.5σ. Adding the phase's Biso columns, then
  the other phase's columns, and dividing by the esd inflation (8.2 on that
  fit) brought both down to 4.4 and 14.6. Adding the coordinate and
  occupancy columns (the first form's `occupancy` pattern matched no path)
  took NAC to 8.1.

  *The sweep* (ruling 2, part 2). For each opt-in correction: the
  declaration, what points at it, on what evidence, and whether the pointer
  names the declaration.

  | correction | declaration | pointer | evidence | names it? | gap |
  |---|---|---|---|---|---|
  | extinction | `phase.extinction = 0.0` | `EXTINCTION_UNDECLARED` (new) | score test, strong lines over-calculated | yes | fixed here |
  | March-Dollase PO | `Phase.preferred_orientation = PreferredOrientation(axis=...)` | action `refine_preferred_orientation` (`report/layer2.texture_actions`) | per-reflection obs/calc corrections fit a March model, R² gate | yes | none |
  | spherical-harmonics texture | `Phase.texture = SphericalHarmonicTexture(order=4)` | the same action, when its axis is ambiguous | runner-up axis fits nearly as well | yes, added here | fixed here |
  | hump (`extra_components`) | `instrument.extra_components = [HumpComponent(...)]` | action `increase_background_flexibility` | between-peak residual systematic (Durbin-Watson, χ² share) | yes, added here | fixed here |
  | sharp extra peak | `instrument.extra_components = [PeakComponent(...)]` | Layer 0 unindexed-peak regions, `add_impurity_phase` | an unexplained line | no | WP-2087 territory, not listed there: a peak usually wants a phase |
  | Stephens microstrain | `Phase.microstrain = StephensStrain.isotropic(...)` | none; `FitReport.strain` is computed and read by nothing | width anisotropy by hkl | no | needs design, WP-2087 |
  | anisotropic ADPs | `Atom.aniso = AnisoU(...)` | none | none exists | no | needs design, WP-2087 |
  | surface roughness | `instrument.geometry.surface_roughness = RoughnessSuortti()` | `BISO_NEGATIVE` prose only | negative Biso | no | needs the geometry at the raise site, WP-2087 |
  | absorption µR / µt | `geometry.capillary_radius_mm` or `thickness_mm` (or `mu_r`/`mu_t`) | `BISO_NEGATIVE`, `BISO_UNUSUALLY_LARGE` prose only | Biso anomaly | no | needs the geometry at the raise site, WP-2087 |
  | air scatter | `instrument.background.air_scatter = Parameter(value=1e-3, min=0.0)` | `AIR_SCATTER_UNDECLARED` | score test on a 1/(2θ) column | yes | none (the model this WP copied) |
  | magnetic moments | `Phase.magnetic_symmetry`, `Atom.moment` | `report/satellites.py` | unindexed satellite lines | yes | none |

  `parent_cell` turned out to be indexing evidence (`SupercellCheck`), not a
  correction. `distortion_modes`, `floating_origin` and `particle_radius_um`
  declare a description, not an intensity correction, so they are out of
  the sweep.

  *The preset test* (ruling 2, part 3).
  `test_no_preset_frees_a_correction_the_model_does_not_declare` runs every
  stage of every preset against a model declaring no opt-in correction, and
  asserts that no opt-in path is freed.

  *Reaching every reader.* A `Parameter` handed to `extinction` inherits its
  range and unit, as every declared field does (issue #204). An opt-in field
  has no default to carry them, so `Phase._declared_optional` names a
  factory, and both the constructor and the history repair
  (`schemas.migrate.declared_range_repairs`) read it through
  `_declared_default`. The TOPAS not-written check and the GSAS-II CIF clause
  skip an undeclared phase. A joint fit asks `EXTINCTION_UNDECLARED` per
  histogram (`multi.DIAGNOSTIC_SCOPES`). The pointer has a test, a silence
  pair (`tests/silence.py`) and a row in the skill's diagnostics reference.

  *What moved, and why.* Each guide fit below freed extinction under the old
  default. None declares it now, except where the page's story needs it.

  | page | before | after | why |
  |---|---|---|---|
  | qpa | CaF₂ 3.58 ± 3.53 wt %, Rwp 0.082 | 1.34 ± 0.11 wt %, Rwp 0.088 | the extinction-scale trade (ρ = +0.998) is gone. The page now shows it in its own section, declared on CaF₂: 3.69 ± 3.63 wt % |
  | qpa, Biso held | 1.37 ± 0.07 | 1.41 ± 0.07 | only the Biso is held now |
  | tie | 35 / 33 free, tied Biso esd 0.079 | 34 / 32, 0.077 | one parameter fewer; FAP's extinction had ended at 0 |
  | hump | Si Biso 0.443(100), 0.446(18), 0.448(39) | 0.417(65), 0.425(12), 0.425(26) | extinction no longer trades against Biso. The esd ratios the page quotes (5.6 and 2.5) are unchanged |
  | joint | z(Al) esd ratio 3.6, x(O) joint ratio 0.67 | 3.4, 0.66 | corundum's extinction no longer free |
  | next | | unchanged | the guide scores extinction, so its structure declares it |
  | switching (TOPAS) | free paths end `phases.0.extinction`; `scale_pks` named | end `phases.0.atoms.0.dof.0`; no `scale_pks` | the writer writes no extinction for an undeclared phase |
  | tutorial 02, landing panel | three warnings, one `FLOOR_HIT` on extinction | two warnings | same Rwp, 0.0898 |

  The refinement diagnostics page passed the manual's 50 000-character
  twin cap with the new code. Nearly every refinement code is raised in
  `refine.py`, so no file prefix separates them. Codes naming a physical
  correction moved to a new Corrections page
  (`reference_pages.CORRECTION_CODE_PREFIXES`), and 18 links followed.

  *Generality* (`generality-review`, run on the branch at `efc450c90`;
  sections pasted unedited, each author answer under a `fails` marked
  **Answer**, applied in `c7ee226b1`).

  > **`EXTINCTION_UNDECLARED` (code, tier 1, ambiguity 1, warning): fails.**
  > The row should not stand at tier 1. The case for having a pointer is
  > strong, since the maintainer's second ruling asks for one and the code
  > changes no fitted value. But the row as written does not hold: its
  > threshold is an unaudited number, its firing side is one synthetic
  > fixture, and its evidence names a partner column the code never builds.
  > Keep the code, re-tier it and fix the evidence.
  > (1) It decides when to speak (score ≥ 25), that the leftover strong-line
  > deficit reads as extinction, and that this is a `warning`. (2) The
  > attribution is kind 2: preferred orientation, opt-in and so not
  > projected in a default fit, draws the same deficit; detector count-rate
  > non-linearity is kind 3. Fails. (3) Strong case against: a lab refiner
  > with platy crystals refines PO first; TOPAS, RIETAN-FP and BGMN have no
  > powder extinction parameter; `_EXTINCTION_PARTNER` matches `occupancy`
  > where the path is `.occ`; coordinates excluded with no reason; a tied
  > Biso gets one site's column; the firing test frees no Biso. (4) Moderate
  > case for: without a pointer real extinction is never named; a false fire
  > costs one refit; the 0.5 µm² plant is a miss the table called silence.
  > (5) Tier fails: the threshold `AIR_SCATTER_UNDECLARED_SCORE` is itself
  > unaudited, and the borrowing divides by the squared inflation; with one
  > firing family the rare-feature clause gives tier 3 with `grounds` and
  > `approved`. (6) Weak: one synthetic firing family, three development
  > families silent, the projection reworked on NAC. (7) Record holds.
  > *What would change the verdict:* the screen run under
  > `mccusker_structural` (Biso free) on a planted case and on one real
  > specimen with a known extinction, the occupancy regex fixed, and the
  > threshold row audited.

  **Answer:** fixed the occupancy pattern, added coordinates, built every
  partner column through C, set ambiguity 2, added the structural-plan
  firing case (78) and recorded the 0.5 µm² miss. Tier 3 needs the
  maintainer's approval, so the row stays at tier 1 and the PR asks for it.
  No real specimen with a known extinction is in the test data.

  > **`EXTINCTION_UNDECLARED.suggestion`: weak.** Naming the declaration is
  > arithmetic; the rest steers toward one hypothesis and one plan. It names
  > PO as a rival but not PO's declaration, and tells a caller on another
  > plan to switch. *What would change the verdict:* a plan-neutral step and
  > the PO declaration.

  (Applied: the suggestion now says "free phases.N.extinction and refit"
  and names `structure.phases[N].preferred_orientation`.)

  > **`rietx.refine._EXTINCTION_PROBE`: weak.** The number is fine for a
  > threshold of 25, but "to fp64" is wrong: the forward difference carries a
  > relative error of about x/2, roughly 1e-4 on the LaB6 fixture (scaled,
  > not measured). Tier 1 for a numerical setting needs a test holding its
  > error under a stated bar. *What would change the verdict:* that test, and
  > evidence saying "~1e-4 relative".

  (Applied: the evidence says so, and
  `test_the_extinction_probe_column_is_the_derivative_at_zero` holds it to
  1e-3 against a finer forward difference. A central difference cannot be
  the reference: the Laue factor is 1 for every x < 0.)

  > **`refine._EXTINCTION_PARTNER`: fails.** It decides which explanations
  > the score has already ruled out, and it does not do what its docstring
  > says: `occupancy` never matches `.occ`; coordinates are left out; it reads
  > `free_paths` and perturbs values directly, bypassing C, so a tied or
  > variable-driven Biso gets one site's column (the root rule: "can this
  > parameter move?" is `moving_paths` and `column_reach`, never
  > `free_paths`). *What would change the verdict:* the regex matching `occ`
  > and the coordinate DOFs, partner columns built through C, and the NAC
  > score re-measured.

  **Answer:** all three done; NAC re-measured at 8.1, CaF₂ 14.6.

  > **Reuse of `AIR_SCATTER_UNDECLARED_SCORE` (25): weak.** Five sigma is
  > defensible, but the borrowed number is unaudited and used differently
  > (air scatter also gates on a 0.5 % χ² share and divides by no
  > inflation), so a retune of either test moves the other. *What would
  > change the verdict:* a constant of its own, audited with the 69 fits
  > named as development data.

  (Not applied: a new constant would enter the table needing its own tier,
  and tier 3 is the maintainer's. The PR asks.)

  > **`docs/reference_pages.CORRECTION_CODE_PREFIXES`: holds.** Not a
  > heuristic; it decides which manual page lists a code.

  > **Default change (`Phase.extinction` now `None`): holds.** Weak case for
  > the old default, a measured case against it, practice (GSAS-II off by
  > default; TOPAS, RIETAN-FP, BGMN have no such parameter) and the ruling.
  > Loose ends: `test_acceptance_nac.py` and `test_acceptance_srm660c.py`
  > still freed an undeclared extinction, and `help.py` gives
  > `default="0.0"`.

  (Applied: both guards declare extinction and pass. The help entry's
  `default` stays `0.0`: it is the value a declaration takes, as for the
  optional blocks' parameters, and `test_help` reads it off a declared
  fixture.)

  *Next:* the maintainer reviews PR #1391, with its "What a reader
  receives" section, and decides two things it asks: whether
  `EXTINCTION_UNDECLARED` moves to tier 3 with grounds and an approval,
  and whether it gets a threshold of its own rather than the air-scatter
  screen's. Either answer is a row edit in `_audit.py`. Then WP-2087,
  starting with the Stephens action.

- **2026-11-03** — task 1 measured. Nothing in `src/` changed. A ghostshift
  runner did the work. The decision brief below waits on the maintainer.

  *What ran.* A probe was put on `PYTHONPATH` as a `sitecustomize.py`, so it
  reached pytest, its workers and every example subprocess. It recorded each
  `Refinement.fit` and `MultiHistogramRefinement.fit`. It ran over 24 files:
  the 22 test files that name the plan, plus `test_examples.py` and
  `test_tutorials.py`, with their slow rows. Each file ran twice. The first run
  used the tree as it is. In the second, the plan's extinction stage matched
  nothing. An opt-in `Phase.extinction` would do exactly that on a model that
  declares no extinction. Stages a test writes for itself (`test_acceptance_nac`,
  `test_acceptance_srm660c`, `test_injected_extinction_is_recovered_within_esds`)
  kept their own glob. Worktree venv `[dev]`, darwin arm64, Python 3.12,
  `-n 4`, at `aa5206d73`. The baseline took 8:06 and the opt-in run 5:00.
  Another runner's suite was running beside both.

  *The count.* 101 fits ran a plan carrying the extinction stage. They are 69
  distinct fits once repeats of a shared fixture are merged. They hold 99
  extinction values:
  - 2 over 3σ. One is
    `test_injected_extinction_is_recovered_within_esds` (2.65 ± 0.16, 16.6σ).
    It plants extinction and frees it with its own stage, so neither fix
    touches it. The other is `test_aniso_adp.py::test_round_trip_recovers_an_anisotropic_perturbation`
    (0.644 ± 0.21, 3.1σ). Its synthetic pattern has no extinction planted, so
    the plan found extinction that is not there.
  - 50 above zero and under 3σ.
  - 47 at exactly 0, the lower bound.

  No real-data fit reaches 3σ. In order of significance:
  - 11-BM NAC from the QPA guide: NAC 246 ± 88 (2.8σ) and CaF₂ 1919 ± 4066 (0.5σ).
  - Si 640c from the hump guide: 23-29, at 0.3σ to 2.2σ.
  - The Nd₂Ru₂O₇ wavelength acceptance fits: 2.9-3.4 ± 1.6 (1.7σ to 2.1σ).
  - The published Cu 311 histogram: 0.2σ and 1.5σ.
  - FAP, the corundum joint guide and the tutorials: at or near 0.

  *What moves if the stage frees nothing.* Eleven tests go red, against none in
  the baseline (baseline 889 passed, 2 skipped, 2 xfailed; opt-in 11 failed,
  878 passed). Six of them assert the current behaviour itself:
  - `test_extinction.py::test_mccusker_structural_frees_extinction_after_displacement`
    pins the stage's glob.
  - `test_extinction.py::test_the_extinction_column_agrees_with_central_differences_on_the_qpa_fit`
    needs CaF₂ extinction free.
  - `test_sequential.py::test_a_warm_refit_lifts_no_carried_floor_value` uses
    `phases.0.extinction` as its floored row.
  - `guides/interval.py` profiles `phases.0.extinction` on FAP, and the row is
    gone (`KeyError`).
  - `guides/tie.py` counts free parameters, 35 and 33, and each drops by one.
  - `switching.py` lists the first free paths on the TOPAS page.

  Five pin a number the change moves:
  - `guides/qpa.py`: the free fit's CaF₂ goes from 3.58 ± 3.53 to
    1.34 ± 0.11 wt%. That is close to the held fit's 1.37 ± 0.07. Rwp rises
    from 0.0816 to 0.0884, because NAC's own 2.8σ extinction is no longer
    freed either. The two `HIGH_CORRELATION` findings the page explains are
    gone.
  - `guides/hump.py` (Si 640c): the three quoted Biso values move by up to
    1.7 esd (4.9 %). The scale moves 1.5-2.1 esd (2.2-2.3 %).
  - `guides/joint.py`: a quoted ratio of two esds changes at its second decimal.
  - `test_acceptance_wavelength.py::test_the_neutron_widths_leave_one_esd_at_every_start`:
    a pinned width goes from 0.0102922 to 0.0103546, a 0.6 % change against a
    1e-6 tolerance.
  - `test_tutorials.py[02_simple_rietveld]`: the tutorial no longer prints
    `FLOOR_HIT`, which the landing page quotes.

  Two patterns hold across all 101 fits. First, where extinction sat at 0,
  nothing moves (under 1e-6 esd). The one change there is that a `FLOOR_HIT`
  warning about extinction disappears, in 45 of the 101 fits. Second, where
  extinction was above 0, the phase scale moves most. It moves 0.1-2.8 esd
  (0.1-3.2 %), because extinction and scale both damp the strong low-angle
  lines. Biso moves up to 1.7 esd and a coordinate up to 0.6 esd (at most
  1230 ppm in x). The largest cell move is 9 ppm (0.84 esd, CaF₂ in the QPA
  fit). The obs/calc/diff plots of the QPA fit both ways show no visible
  difference in the fit. They were looked at, and they are in the runner's
  scratch directory.

  Practice: `docs/practice.md` § Extinction › "Is powder extinction refined
  unasked?" was added this session. GSAS-II was checked in its 5.8.4 source.

  *Next:* the maintainer decides (brief below). Then tasks 3-5.

### 2026-11-03 — decision brief (waits on the maintainer)

**The decision.** Should `mccusker_structural` keep freeing extinction on
every phase, or free it only where the user asked? This comes to you for two
reasons. Your 2026-10-11 ruling reserved the choice until this count existed.
Option A is also a stored-format change.

**Why it matters.** Extinction is a correction that weakens the strongest
reflections of a phase made of large, perfect crystallites. The structural
plan frees it on every phase today, after the displacement parameters, and
its description says "where declared". On these 69 fits the data almost
never determine it: 1 value in 98 from the plan's own stage passes 3σ, and
that one is a false positive on synthetic data. When it is freed and
undetermined, it trades off against the phase scale. The weak phase in a
mixture is hit hardest. The QPA guide's CaF₂ reads 3.58 ± 3.53 wt% with it
free and 1.34 ± 0.11 wt% without. Elsewhere a user sees scales move up to
3 %, Biso up to 5 %, and a `FLOOR_HIT` warning on nearly half of all
structural fits about a parameter they never asked for. Importance: moderate.
Weight fractions from a two-phase structural fit are what most users of this
plan quote, and the bias is silent.

**Aim.** I read this as serving accuracy and honest reporting for the
scientist running a preset (`rulings-lead-with-accuracy`). A fit should not
spend a free parameter the data cannot see, on a quantity the user did not
ask for.

**Options.**
- *A. Opt-in on the phase (the WP's second fix).* `Phase.extinction` defaults
  to `None`, as `preferred_orientation` does, and the stage frees only phases
  that declare one. Old files that store a value open unchanged. The numbers
  above are what A produces on these fixtures. Measured. Cost: a schema change,
  11 tests and pages re-pinned, three guide narratives rewritten (qpa,
  interval, tie), and the landing-page quote. Reversible, though a file saved
  in the new format would not open in an older rietx.
- *B. Correct the texts (the WP's first fix).* The description and the schema
  comment say "every phase". Nothing numeric moves, and the QPA bias and the
  45 `FLOOR_HIT` warnings stay. Cost: two strings. Reversible.
- *C. Drop the stage from the preset.* No schema change. A user who wants
  extinction adds a stage, as the NAC and SRM 660c acceptance tests already
  do. The numbers are identical to A's: the probe measured this exact case.
  Cost: A's re-pins without the schema work. The plan's three "where
  declared" corrections then stop working the same way, because PO and
  roughness stay opt-in on the model.
- *Doing nothing* leaves a description that contradicts the code.

**Practice.** No surveyed program refines powder extinction unless the user
asks (`docs/practice.md`, checked except FullProf). GSAS-II keeps the
parameter on every phase at 0 with its refine flag off. TOPAS, RIETAN-FP and
BGMN have no powder extinction parameter. FullProf holds `Extinc` at a
codeword of 0 (recall, not checked). None of them ships a staged plan, so
none has a stage that could free it on the user's behalf. B is the only
option that departs from this practice.

**Recommendation.** A, at the level of a lean. Choosing A or C over B is a
clear call, for three reasons: the count, your ruling's own criterion ("rarely
significant favours the opt-in") and every program's practice. The crux
between A and C is how a scientist running a preset should ask for
extinction. Under A they declare it on the phase, which is how they already
ask for PO and surface roughness, and how GSAS-II's per-phase flag works.
Under C they must write a plan. C loses on that point, though it is cheaper.
This rests on a guess about how users work. If you would rather presets
never carry opt-in physics, pick C. One observation would flip the pick: a
real-data fixture where the plan's extinction passes 3σ and moves a quoted
number toward a certificate. None of the 69 does.

- **2026-11-02** — no decision changes. The 2026-11-01 decision briefs
  re-read this WP and confirmed that the maintainer's ruling of 2026-10-11
  stands: measure first, and let the count decide. So the next step is
  task 1, the measurement. One strong hint exists already (§ Inherited, from
  WP-2044): on the QPA guide's fit, freeing extinction moves CaF₂ to
  3.58 ± 3.53 wt% against 1.37 ± 0.07 wt% held. No surveyed program refines
  powder extinction unasked: TOPAS has no keyword for it, RIETAN-FP has
  none, and FullProf has one empirical parameter (`docs/practice.md`
  § Extinction). If the count favours the opt-in, making `Phase.extinction`
  optional is a stored-format change, and it goes back to the maintainer as
  one consent line. Recorded by a ghostshift runner in PR #1317; nothing
  was run. *Next:* task 1.

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #877).
  Checked against the tree at `f11e22d3`: the extinction stage's glob
  matches every phase, and PO and roughness are the only opt-in blocks among
  the three. No open WP owns it: WP-1914 is the sibling for sample
  broadening and touches no plan, and no open WP names `PLAN_INFO` or the
  extinction stage. *Next:* task 1.
