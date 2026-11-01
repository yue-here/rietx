# WP-1467 — a Stephens block on a frozen floor, and a clamp the solver leans on

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1318 soft: its strain surface would draw the region the clamp covers)
Priority: P2 2026-09-25 — a block declared over a nonzero `lor_strain` cannot narrow below it and under `solver="lm"` nothing fires; a path few fits run

## Goal

A Stephens block replaces the isotropic Lorentzian strain it locks, whatever
value that parameter held. When `STEPHENS_STRAIN_NOT_POSITIVE` fires, the
finding says how much of the phase's intensity sits in reflections the clamp
left with no strain width, and its suggestion names `solver="lm"`. Every page
that explains the flag says the fit leaned on the clamp. It no longer treats
the firing as a question about the coefficients alone.

## Context

**The evidence.** A 2026-09-25 review of the second agent session on `in-situ
series 1` in the private `yue-here/rietx-corpus-map`. The map's row also names
the three probe scripts this file's numbers come from. Quote only what the
runs did (CONTRIBUTING, WP-1450). The session's report said a Stephens block
lowered χ² by 20 to 30 %, failed the positivity guard on every pattern, and so
was not used. It then quoted the block's effect on phase fractions as its
peak-shape uncertainty.

The review re-ran the session's `aniso_test.py` protocol on three patterns:
2θ ≤ 35°, instrument held, the session's three-stage plan with
`strain_seed=1000.0`, and a block on every present phase. Source `48118bb6`,
then `95c2cae8` for the floor variants. The one configuration run on both
reproduced to the digit. Worktree venv `[dev]`, macOS.

| Pattern | χ² isotropic | χ² Stephens, TRF | χ² Stephens, lm | In-range reflections the clamp zeroed under TRF (share of the phase's m·\|F\|²) |
|---|---|---|---|---|
| 0, one phase | 1.943 | 1.799 | 1.883 | phase 0: 34 of 94 (33 %) |
| 16, two phases | 3.403 | 2.301 | 2.008 | phase 0: 29 of 94 (25 %); phase 1: 1 of 436 (0.5 %) |
| 41, two phases | 1.381 | 1.286 | 1.427 | phase 3: 92 of 378 (25 %); phase 4: 192 of 234 (84 %) |

The isotropic fits are identical under both solvers on all three patterns.

**Defect 1: the block stacks on the width it locks.** A declared block
force-fixes `phases.i.lor_strain` (`params/vector.py`, commented "the
Atom.aniso ⇒ biso bargain, one level up"). `force_fixed` keeps the stored
value, and the width law still reads it. `forward.py` passes
`instrument.profile.y + phases.i.lor_strain` and Λ(hkl) together into
`lorentzian_fwhm`. So a block declared over a nonzero `lor_strain` adds
Λ ≥ 0 on top of a frozen isotropic width and cannot go below it. The ADP half
of that bargain holds. An anisotropic site's Debye-Waller factor never reads
`biso` (`crystallography/structure_factor._orbit_terms`). The Stephens half
does not.

The docs describe the Stephens lock as if it worked like the ADP one. Root CLAUDE.md and
`docs/manual/microstructure.md` both say the block "subsumes" `lor_strain`.
`docs/manual/using/data.md` says declaring the block "locks `Phase.lor_strain`,
whose column is identically the isotropic direction". The block nests the
isotropic model only when the lock removes the term: at S = ε²·[M²],
Λ = (180/π)·10⁻⁶·ε for every reflection. That is a `lor_strain` of the same value.
`refine.py`'s `STRAIN_UNUSUALLY_LARGE` docstring states half of the defect:
"a locked term keeps whatever value it was given".

`lor_strain` defaults to 0.0, so a block declared on a fresh phase is
unaffected. A nonzero value reaches a block through `Refinement.edit` after an
isotropic fit, a structure built from refined values, or a checkout. The
session built its structures from refined templates, and phase 4's carried a
nonzero `lor_strain`. No phase on patterns 0 and 16 carries one above 1e-100.
Pattern 41 with phase 4's floor handled three ways:

| Variant | χ² TRF | χ² lm | Phase 4 zeroed under TRF |
|---|---|---|---|
| floor kept (the session's setup) | 1.286 | 1.427 | 84 % |
| `lor_strain` set to 0, the same 1000 ppm seed | 1.160 | 1.196 | 12 % (phase 3: 40 %) |
| `lor_strain` set to 0, block started on the isotropic ray at the template's value | 1.482 | 1.488 | 0 % (phase 3: 7 %) |

With the floor kept, the lm fit sits above the isotropic fit it should nest.
With the floor removed, lm lands 13 % below it. Starting the block at the
template's isotropic strain gave both solvers a worse minimum than the
isotropic fit. On one pattern's evidence that start is not a safe default.
With the floor removed, TRF and lm moved phase 4's weight fraction by similar
amounts in the same direction. The third start left it near the isotropic
value at a worse χ².

`Refinement.suggest` probes a declared block at `SUGGEST_SEED_STEPHENS`
(1000 ppm) through `ParameterTable.seed_stephens`, so it measures a block's
gain on top of the same floor.

Every reader of the width: `forward.py`'s `_width_block` (the sum above), the
width memo key in the same file (it lists `lor_strain`), the compile-time
window sizing (`phase.lor_strain.value` beside `instrument.profile.y`), and
`model/microstructure.py`, which reports `lor_strain` as a strain reading and
compares it with `gauss_strain`.

**Defect 2: the clamp carries load, and the flag is read as a coefficient
problem.** `crystallography/stephens.strain_width_deg` masks σ²(M) ≤ 0 to zero
width with a double `where`. Under TRF the solver pushes σ² negative across a
region of directions, and those reflections lose all strain width. The
zero-width set is a free hinge. On pattern 0, where no floor confounds it, the
cone-enforced fit keeps 42 % of TRF's χ² gain (0.060 of 0.144). On pattern 16
the cone-enforced fit is better than TRF (2.008 against 2.301). On pattern 0
the zeroed set splits evenly by k parity: 13 of 39 k-odd reflections and 22 of
57 k-even, each carrying 17 % of the intensity. It is a region of directions.

A fit that leaned on the clamp is not a Stephens fit. Its χ², fractions and
cells carry the hinge as well as its S_HKL. Every reader of the flag says the
firing is about quotability:

- `docs/manual/microstructure.md` § The positivity cone, the seed and the
  guard: "Read a firing as 'these coefficients are not quotable', never as
  evidence of anisotropy."
- `src/rietx/help.py`, the `phases.*.microstrain.dof.*` entry: the same
  sentence.
- Root CLAUDE.md, the anisotropic-strain invariant: the same sentence.
- Skill `references/diagnostics.md`: the abstention is "Report any S_HKL".
- Skill `references/abstention.md`: names `solver="lm"` and says it lands "at a
  *higher* Rwp", measured on brucite. Pattern 16 went the other way.
- Skill `SKILL.md` rule 22 comes closest: "each say a number in the result did
  not come from the data".

`viz/compare.py` already has the reading this WP wants: "a variant can win
panel 3 and still be inadmissible".

The diagnostic (`refine.py`, the `nonpositive_strain` loop in
`_guard_diagnostics`) says "those reflections silently get no strain
broadening at all". That is right. Its suggestion offers three remedies and
leaves out `solver="lm"`:

- "restart from the isotropic limit". Every staged plan already seeds there
  through `Stage.strain_seed`.
- "refine fewer patterns (a higher-symmetry Laue class has fewer)". The Laue
  class is the declared symmetry, so this fixes only a wrong declaration.
- "extend the fit range". That needs data the user may not have.

**Defect 3: the finding counts reflections, not intensity.**
`GuardFinding.nonpositive_strain` (`strategy/staged.py`) renders "(n of N
reflections, worst σ²(M) … at hkl)" over the whole compiled list, in the
fitted range or not. On pattern 16 the two phases printed "29 of 96, worst
−7.14e+06" and "1 of 463, worst −1.24e−01". The second sits just past
`STEPHENS_CONE_TOL` (1e-9 of the phase's largest |σ²|) and carries 0.5 % of
the phase's intensity. Both fire at the same level with the same suggestion.
The worst σ² is in 10⁻¹² Å⁻⁴ monomial units and does not compare across
phases. The share of the phase's intensity in zeroed reflections separates the
two.

`check_stephens_positive` already takes the compiled model.
`CompiledModel.structure_intensity_partition(values)` returns each phase's
(I_obs, I_calc) with I_calc = m·|F|², and refuses outside Rietveld mode. Le
Bail and Pawley carry `CompiledPhase.hkl_intensity`. The review's probe used
I_calc over the in-range reflections.

`str(finding)` is pinned byte for byte by
`tests/test_capabilities.py::test_rendered_findings_are_unchanged`. WP-1434
added evidence through `GuardFinding.detail`, which the diagnostic appends and
`__str__` omits. That field's docstring names `at_bound` as its only writer
and `BOUND_HIT` as its only reader, so a second writer updates it (WP-1076).

**Prior art.** TOPAS's shipped Stephens macros compute
`pp = D_spacing^2 * Sqrt(Max(mhkl,0))`, the same clamp, and report nothing.
`Stephens_tetragonal` wraps mhkl in `Abs()` first, which folds a negative σ²
back into a positive width. A TOPAS fit can lean on the hinge unseen. Each
macro splits the width with a mixing parameter:
`gauss_fwhm = 1.8/π · pp · (1-eta) · Tan(Th)` and
`lor_fwhm = 1.8/π · pp · eta · Tan(Th)`. GSAS-II carries the same split as
`Mustrain;mx`. WP-0503 fenced it: "Λ is pure Lorentzian here … Revisit only if
a real dataset forces it." WP-0503 attributes the parameter to Stephens as ξ,
and this review did not read the paper. The manual says only that Λ is "added
to the Lorentzian FWHM". A reader mirroring a TOPAS protocol cannot see that
the split is missing.

**The sibling, and what is not one.** `caglioti.gaussian_fwhm` floors Γ_G² at
`_MIN_GAMMA_G2` (1e-8 deg²), another clamp on a width variance, guarded by
`RESOLUTION_NOT_POSITIVE`. Its suggestion already says "anything judged
against them is unsafe", so defect 2's reading does not carry over. Its
finding counts fitted points, so defect 3 might. Whether TRF leans on that
floor is not measured. `ADP_NOT_POSITIVE_DEFINITE` is not a sibling. The
Debye-Waller factor is not floored, so there is no hinge to lean on.

### Inherited

- **From WP-2002 (2026-10-23, 8th session, PR #1113): a joint fit ignores `Stage.strain_seed`.** `MultiHistogramRefinement.fit`'s stage loop calls only `seed_floored` (`multi.py` ~1371-1373), never `seed_stephens`, so a joint fit through `lab_sample_refine` starts a freed all-zero Stephens block at S ≡ 0, where the width's square root has unbounded slope, and nothing says so. The single runner records its seed in `StageResult.seeded` since 2002's B14; the joint runner's docstring now states the gap. Fixing it moves joint fits that seed a block.

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** Every plan now ends in a closing stage at 1e-3 windows, and on SRM 660c LaB6 its answer sits 0.908 plain esd from the converged-tails answer in `profile.u`. At that answer the highest-angle reflections' Gaussian variance U·tan²θ + V·tanθ + W is under the clamp floor, a second recompile moves u by 1 esd and a third by 0.002. `tests/test_window_domain.py::test_the_closing_stage_meets_the_bar[lab6]` is a strict xfail citing this WP, and turns green when the clamp stops moving u.
- **2026-10-11, from WP-1938 (2nd session): LM is the default on that
  branch, and the stall is the model's edge.** Once 1938 merges, a
  single-histogram fit holds the cone by default. So
  `STEPHENS_STRAIN_NOT_POSITIVE` fires only under `solver="trf"` and in a
  joint fit, and this WP's "names `solver="lm"`" suggestion becomes "the
  default holds the cone". Brucite + Stephens under LM (D8's exact step) ends
  with 6 of 43 reflections exactly on σ² = 0, with zero strain width at the
  edge rather than outside it. Lifting any of them raises the cost as √h,
  and LM stops with one face set at costs 4e-5 apart (χ²_red 7.7177-7.7202
  over five starts). 1938 recorded that as an exception (its D9), and
  WP-1946 owns a formulation that cannot go negative. The intensity in
  reflections the clamp leaves at zero width, which this WP's finding is to
  report, now also arises on the cone's face under LM.

- **2026-10-10, from WP-1937: the flip to `solver="lm"` moved to WP-1938.**
  This WP's suggestion that names `solver="lm"` changes shape only when 1938
  makes it the default. Measured there, in physical coordinates: brucite +
  Stephens under LM stalls against the cone (χ²_red spread 1.6e-6 over five
  starts nudged by 1e-14, 8 truncated steps in `sample_broadening`).
  WP-1938 owns that stall as a task.

- **2026-09-28, from [1338](1338-the-skills-own-gates.md): `references/diagnostics.md` is closed to growth.**
  Every skill file now has a ceiling and a budget below it
  (`tests/skill_caps.py`), and the budget fails a change that grows a file
  past it. `diagnostics.md` (35 111 B) and `diagnostics-indexing.md`
  (35 124 B) sit over their 34 600 B budget, so a row this WP adds there
  comes with an equal cut in the same change, or goes to the file a reader
  meets the code in (the criterion in the `REFERENCE_MAX_BYTES` comment).
  CI's lint job reports each changed file's headroom on the draft PR.
- **2026-10-09, from WP-1929 (2nd session): `solver="lm"` may become the
  default.** WP-1937 replaces the LM driver's BCCG step with an exact
  bounded solve (BVLS) and, once its statuses and budgets match TRF's, makes
  it the default. The Stephens cone stays a linear inequality around that
  step. If 1937 lands first, the suggestion task here ("names `solver="lm"`
  first") becomes a statement that the default already enforces the cone,
  and the measured TRF-versus-LM table should be re-run under the new step.
  On brucite aniso (WP-1929's grid, physical coordinates) LM reached χ²_red
  8.0006 against TRF's 7.636, which carries `STEPHENS_STRAIN_NOT_POSITIVE`.

- **From WP-2002 (2026-10-19, PR #1050).** Batch class B3. GSAS-II starts a new histogram's generalised strain coefficients at 0.01 each (`GSASIIddataGUI.py:1432-1433`); 1000 µstrain on the isotropic ray is its Reset button, a user's act. So `lab_sample_refine`'s 1000 ppm seed matches GSAS-II's isotropic default only. The batch keeps that seed at tier 3 until a second family compares starts, and this WP's start comparison is the obvious one.

- **From WP-2002 (2026-10-21, PR #1085).** The Γ_G² floor is leaned on, under LM. This WP's sibling paragraph says whether a fit leans on `_MIN_GAMMA_G2` was not measured. It is: the SRM 660c and cpd-1a protocol answers end with high-angle reflections on the floor (`CONSTRAINT_ACTIVE`; a Kα2 reflection near 149.7° on LaB6, corundum past 150° on cpd-1a). There the FD width column is 2.2e-2 off the right derivative, because the step moves Γ_G² by about 0.7 of the floor, and a polish under a 5e-7 FD step or a 1e-10 floor stops 1.2 plain esd away on `profile.u` at χ² 0.25 % worse. An FD step of 1e-8 does not cure it. A candidate fix is analytic width scalars at the clamp (`optimize/least_squares.py:1873-1970`, the clamp at `caglioti.py:292`, the width step at `least_squares.py:1112-1121`). Tests: `tests/test_gaussian_width_floor.py`, and `tests/test_cross_backend.py::test_fd_columns_hold_at_every_protocol_answer` (strict xfails on lab6 and cpd1a).

## Non-goals

- The Gaussian/Lorentzian split itself. WP-0503's fence stands, and this WP
  makes it visible. Whether this series forces it cannot be measured without
  building it.
- `solver="lm"` as the default for a block. On pattern 41 the start alone
  moved the lm χ² from 1.196 to 1.488, so a default needs its own measurement.
- Drawing the zeroed region. WP-1318 draws the strain surface.
- The session's own report. It lives outside the repo.

## Tasks

- [ ] Defect 1: a declared block replaces `lor_strain`. The Lorentzian width
      stops reading `phases.i.lor_strain` when the phase carries a block, as
      the Debye-Waller factor stops reading `biso` for an anisotropic site.
      The lock stays, so the path still exists for globs and write-back. Reach
      every reader listed under defect 1, and grow `test_cross_backend.py`'s
      configs with it. `microstructure.py` stops reporting a locked
      `lor_strain` as a reading. A fixture that declares a block over a
      nonzero `lor_strain` moves, and every other golden stays bit-identical.
- [ ] The seed. Compare the 1000 ppm `strain_seed` with a start at the
      `lor_strain` the phase carried, folded onto the isotropic ray, on the brucite acceptance fixture
      (`tests/test_acceptance_stephens.py`) and on patterns 0, 16 and 41 with
      the probe. Pattern 41 favoured 1000 ppm. Change the default only if the
      measurements agree, and write the result beside the manual's seed
      paragraph.
- [ ] Defect 3: `check_stephens_positive` computes each phase's share of
      intensity in reflections below the cone tolerance, over the fitted
      range. It rides in `GuardFinding.detail`, `str(finding)` stays
      byte-identical, and `detail`'s docstring names the second writer.
      Rietveld reads `structure_intensity_partition`; Le Bail and Pawley read
      `hkl_intensity`.
- [ ] The suggestion names `solver="lm"` first. It says `lm` makes the
      coefficients admissible, not measured, so vary the start. It keeps "do
      not report the S_HKL", and says the fit's other numbers leaned on the
      zeroed reflections in proportion to the share. The Laue-class remedy is
      conditioned on a wrong declared symmetry, or dropped.
- [ ] The reading, at every place listed under defects 1 and 2:
      `microstructure.md` (the block paragraph and the guard section),
      `using/data.md`, `help.py`, root CLAUDE.md, skill `diagnostics.md` and
      `abstention.md`. `abstention.md` drops "at a *higher* Rwp" as a general
      claim and says the direction varies, without naming the series.
      Re-sync with `rietx skill --install . --copy`.
- [ ] The manual states the fence: Λ is purely Lorentzian here, TOPAS's `eta`
      and GSAS-II's `Mustrain;mx` split it, and a protocol using the split
      cannot be mirrored. Read Stephens (1999) before attributing the
      parameter to him. It also states TOPAS's clamp, so a TOPAS Stephens fit
      carries no evidence that σ² stayed positive.
- [ ] The sibling. On the fixture of `tests/test_walking_bounds.py`'s
      `test_the_collapsed_resolution_function_is_reported`, with U, V, W free, measure the share of Bragg intensity at points under
      the floor. If TRF leans on it, carry the same share in `detail`. If not,
      record the numbers here and leave it.
- [ ] Tests: a block over a synthetic `lor_strain` of 0.3 and over 0 give the
      same pattern;
      the share on the synthetic brucite block `test_stephens.py` already
      drives out of the cone; the suggestion names `lm`; the rendering pin is
      unchanged.
- [ ] Skill: the `diagnostics.md` and `abstention.md` rows in the reading task.

## Acceptance

With the tests on synthetic fixtures and the series numbers from the probe:

- A phase carrying a block evaluates identically with `lor_strain` 0.3 and 0.
- On pattern 41 with the session's setup, the lm fit's χ² is at or below the
  isotropic fit's 1.381.
- On pattern 16 under TRF, `STEPHENS_STRAIN_NOT_POSITIVE` reports a share near
  25 % for phase 0 and under 1 % for phase 1, and names `solver="lm"`.
- Each hit of the grep below also says the fit leaned on the clamp.

```sh
grep -rn "not quotable" docs/manual src/rietx/help.py CLAUDE.md docs/skill/rietx
.venv/bin/python -m pytest tests/test_stephens.py tests/test_capabilities.py tests/test_acceptance_stephens.py tests/test_cross_backend.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Stephens, P. W. (1999). Phenomenological model of anisotropic peak
  broadening in powder diffraction. *J. Appl. Cryst.* 32, 281-289.
- TOPAS wiki, Stephens peak-shape macros,
  <https://topas.awh.durham.ac.uk/doku.php?id=stephens_peakshape> (read
  2026-09-25).
- WP-0503 (the block, the lock, the split fence), WP-0601 (the cone under
  `lm`), WP-1434 (`GuardFinding.detail`), WP-1076 (a new writer names both
  ends of its field).

## Handover log

- **2026-09-25** — created by a review of the second agent session on
  `in-situ series 1`, asked whether rietx presents Stephens correctly. Every
  number above is the review's own re-run, not the session's pickles. The
  floor was found while explaining why lm sat above the isotropic fit. Next:
  task 1, then the seed, since both move the numbers the guard tasks report.
