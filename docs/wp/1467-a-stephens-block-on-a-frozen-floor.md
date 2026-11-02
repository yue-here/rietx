# WP-1467 — a Stephens block on a frozen floor, and a clamp the solver leans on

Milestone: unscheduled · Status: ✅ 2026-11-02 — a block replaces lor_strain; the guard names the clamped share (PR #1323)
Track: What fires, and what stays silent
Depends on: — (1318 soft: its strain surface would draw the region the clamp covers)

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

**Superseded in part, 2026-11-02** (re-run on `0d735f5e5`, the review's own
`cone_probe.py`/`floor_probe.py`, worktree venv `[dev]`, macOS arm64). The
tree moved the numbers. χ² isotropic / TRF / lm: pattern 0 1.935 / 1.794 /
1.838, pattern 16 3.404 / 2.314 / 2.006, pattern 41 1.325 / 1.253 / 1.294. The
clamp zeroed under TRF: pattern 0, 55 of 94 (50.5 %); pattern 16, phase 0 36
of 94 (34.6 %) and phase 1 **none**, so the 0.5 % finding no longer fires;
pattern 41, phase 3 158 of 378 (38.9 %) and phase 4 234 of 234 (100 %). The
pattern 41 lm fit already sat below the isotropic one (1.294 against 1.325)
with the floor kept. The floor variants: keep 1.253 / 1.294, zero 1.156 /
1.170, fold 1.476 / 1.112 (TRF / lm).

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

## Non-goals

- The Gaussian/Lorentzian split itself. WP-0503's fence stands, and this WP
  makes it visible. Whether this series forces it cannot be measured without
  building it.
- `solver="lm"` as the default for a block. On pattern 41 the start alone
  moved the lm χ² from 1.196 to 1.488, so a default needs its own measurement.
- Drawing the zeroed region. WP-1318 draws the strain surface.
- The session's own report. It lives outside the repo.

## Tasks

- [x] Defect 1: a declared block replaces `lor_strain`. The Lorentzian width
      stops reading `phases.i.lor_strain` when the phase carries a block, as
      the Debye-Waller factor stops reading `biso` for an anisotropic site.
      The lock stays, so the path still exists for globs and write-back. Reach
      every reader listed under defect 1, and grow `test_cross_backend.py`'s
      configs with it. `microstructure.py` stops reporting a locked
      `lor_strain` as a reading. A fixture that declares a block over a
      nonzero `lor_strain` moves, and every other golden stays bit-identical.
      *Done 2026-11-02*: `CompiledModel.lor_strain_term` is 0 under a block, read by `_width_block` (both components), the width memo key and the compile-time window sizing. Four readers the list above missed take it too: the Γ_L ≥ 0 rows of `lorentzian_width_inequalities` (they read the stored value through `d`), `report/strain.py`, `STRAIN_UNUSUALLY_LARGE` (which flagged a width the model no longer draws), and the TOPAS writer's `_width_lines` (which wrote both terms). `microstructure_table` drops the term. New cross-backend config `stephens_over_lor_strain`. No golden declares a block over a nonzero `lor_strain`, so none moved. On pattern 41 "keep" now equals "zero" to every printed digit (TRF 1.156, lm 1.170). Not generalised: the FullProf and TOPAS-input writers refuse a block outright, so they had nothing to drop.
- [x] The seed. Compare the 1000 ppm `strain_seed` with a start at the
      `lor_strain` the phase carried, folded onto the isotropic ray, on the brucite acceptance fixture
      (`tests/test_acceptance_stephens.py`) and on patterns 0, 16 and 41 with
      the probe. Pattern 41 favoured 1000 ppm. Change the default only if the
      measurements agree, and write the result beside the manual's seed
      paragraph.
      *Done 2026-11-02*, default unchanged. Brucite acceptance protocol (`seed_brucite.py` in the session scratch, isotropic fit's `lor_strain` 29 ppm): LM χ² 7.8943 (1000 ppm), 7.8945 (800), 7.8939 (fold), all inside the cone; TRF 7.9267, 7.8034, 7.7965, 23/19/19 of 43 outside. Pattern 41 (floor fixed): LM 1.170 against fold 1.112 with the two phase fractions swapped (86.5/12.9 % against 9.5/89.6 %), TRF 1.156 against 1.476. Patterns 0 and 16 carry no `lor_strain` above 1e-100, so fold has no start to take there. The measurements disagree, so the default stays; written beside the manual's seed paragraph, at `STRAIN_SEED_PPM` and in its audit row.
- [x] Defect 3: `check_stephens_positive` computes each phase's share of
      intensity in reflections below the cone tolerance, over the fitted
      range. It rides in `GuardFinding.detail`, `str(finding)` stays
      byte-identical, and `detail`'s docstring names the second writer.
      Rietveld reads `structure_intensity_partition`; Le Bail and Pawley read
      `hkl_intensity`.
      *Done 2026-11-02*: `staged.stephens_clamp_share`, in `detail`. Rietveld weighs m·|F|² through `_total_f2`, the I_calc half of `structure_intensity_partition` without its profile loop, over reflections whose frozen window reaches the fitted data. Agrees with the review's probe to 0.4 points on patterns 0, 16 and 41 (50.3/34.9/51.5/19.4 % against 50.5/34.6/51.6/19.6 %; the probe cut at Bragg 2θ, the guard at the window).
- [x] The suggestion names `solver="lm"` first. It says `lm` makes the
      coefficients admissible, not measured, so vary the start. It keeps "do
      not report the S_HKL", and says the fit's other numbers leaned on the
      zeroed reflections in proportion to the share. The Laue-class remedy is
      conditioned on a wrong declared symmetry, or dropped.
      *Done 2026-11-02*, in the shape the inherited WP-1938 note predicted: LM is the default, so the suggestion says to refit under it when the fit ran `trf`, and to fit each histogram alone for a joint fit (no cone under either driver). The Laue-class and fit-range remedies are dropped; "restart from the isotropic limit" too, since every staged plan seeds there.
- [x] The reading, at every place listed under defects 1 and 2:
      `microstructure.md` (the block paragraph and the guard section),
      `using/data.md`, `help.py`, root CLAUDE.md, skill `diagnostics.md` and
      `abstention.md`. `abstention.md` drops "at a *higher* Rwp" as a general
      claim and says the direction varies, without naming the series.
      Re-sync with `rietx skill --install . --copy`.
      *Done 2026-11-02*: `theory/microstructure.md` (block paragraph and guard section), `reference/data.md` (the WP's `using/data.md`), `reference/refinement.md`, `concepts/plans.md`, `help.py` (three entries), root CLAUDE.md, skill `diagnostics.md` and `abstention.md`, re-synced.
- [x] The manual states the fence: Λ is purely Lorentzian here, TOPAS's `eta`
      and GSAS-II's `Mustrain;mx` split it, and a protocol using the split
      cannot be mirrored. Read Stephens (1999) before attributing the
      parameter to him. It also states TOPAS's clamp, so a TOPAS Stephens fit
      carries no evidence that σ² stayed positive.
      *Done 2026-11-02*. Stephens (1999) eq. 6 calls the mixing parameter ζ, not ξ as WP-0503 has it, and refined it to 0.404 and 0.558 in his two examples. Corrected in the manual only; WP-0503 is a closed record.
- [x] The sibling. On the fixture of `tests/test_walking_bounds.py`'s
      `test_the_collapsed_resolution_function_is_reported`, with U, V, W free, measure the share of Bragg intensity at points under
      the floor. If TRF leans on it, carry the same share in `detail`. If not,
      record the numbers here and leave it.
      *Done 2026-11-02*, left. The fixture is a flat pattern, so the measurement used LaB6 synthesised at `HEALTHY_NEGATIVE_V` and started from `COLLAPSED` (`sibling_probe.py`, session scratch). Both drivers end with all 20 on-data reflections under the floor (share 1.0), χ² 6.34 against 1.01 from the true start: TRF moved U, V, W and stayed under it, LM did not move. That is a stall on a zero gradient, not a hinge the fit benefits from, and the finding already counts every fitted point. The floor's other problem, the FD column at the clamp (the WP-2002 inherited entries), is not this task.
- [x] Tests: a block over a synthetic `lor_strain` of 0.3 and over 0 give the
      same pattern;
      the share on the synthetic brucite block `test_stephens.py` already
      drives out of the cone; the suggestion names `lm`; the rendering pin is
      unchanged.
      *Done 2026-11-02*: `test_stephens.py` (+4), `test_strain_cap.py` (+1), `test_projects_topas.py` (one case), `test_cross_backend.py` (one config).
- [x] Skill: the `diagnostics.md` and `abstention.md` rows in the reading task.
      *Done 2026-11-02* with the reading task.

## Acceptance

With the tests on synthetic fixtures and the series numbers from the probe:

- A phase carrying a block evaluates identically with `lor_strain` 0.3 and 0.
- On pattern 41 with the session's setup, the lm fit's χ² is at or below the
  isotropic fit's 1.381.
- On pattern 16 under TRF, `STEPHENS_STRAIN_NOT_POSITIVE` reports a share near
  25 % for phase 0 and under 1 % for phase 1, and names `solver="lm"`.
  *Superseded in part 2026-11-02*: on the current tree phase 1 stays inside the
  cone and phase 0 reports 34.9 %; the review's probe gives 34.6 %.
- Each hit of the grep below also says the fit leaned on the clamp.

```sh
grep -rn "not quotable" docs/docs src/rietx/help.py CLAUDE.md docs/skill/rietx
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

- **2026-11-02** — closing. A Stephens anisotropic strain block now replaces
  the isotropic strain width it locks, instead of sitting on top of a frozen
  copy of it. Before, a block declared after an isotropic fit could not make
  any reflection narrower than the old isotropic width, and on one operando
  pattern that left the anisotropic fit worse than the isotropic one it
  contains. When the trust-region driver walks the coefficients outside the
  physical set, the warning now says how much of the phase's intensity sits
  in the reflections it left with no strain width (19-52 % on the four phases
  probed), and its advice leads with the default driver, which cannot leave
  that set. The fixed 1000 ppm starting strain was compared with a start at
  the carried isotropic strain and kept, because the two drivers ranked the
  two starts differently. PR #1323.

  *Done.* All nine tasks (their notes above). Defect 1 reached four readers
  the WP's list missed (the Γ_L ≥ 0 inequality rows, `report/strain.py`,
  `STRAIN_UNUSUALLY_LARGE`, the TOPAS writer), and `/code-review high --fix`
  found two more (the CIF profile text in `io/exporters.py` and the
  peak-list widths in `io/recipe.py`, `c21ccfbcb`). The review also corrected
  the manual's seed agreement (5 in 10⁵, not 4 in 10⁴) and moved "29 ppm"
  in the `STRAIN_SEED_PPM` row next to the strain it describes. Declined
  review findings: a joint fit keeps the first firing histogram's share
  (`_stephens_once`; changing it means changing how `multi.py` merges
  findings, which WP-1946 owns with the joint seed); the Lp-free weight (the
  docstring states it, and the label now says m·|F|²); passing `values` into
  `stephens_clamp_share` (one extra decode a firing). Stephens' mixing
  parameter is ζ (eq. 6), not ξ as WP-0503 wrote; the manual says ζ.

  *Measured* (`[dev]`, macOS arm64; probes against `0d735f5e5` snapshots):
  pattern 41 "keep" equals "zero" after the fix (TRF 1.156, LM 1.170); the
  guard's shares against the review's probe 50.3/34.9/51.5/19.4 % against
  50.5/34.6/51.6/19.6 %; the brucite seed comparison and the Γ_G² sibling are
  in the task notes. Gates: fast suite on the final tree with main merged (`d07426026` plus
  the two cap trims), 13302 passed, 315 skipped, 32 xfailed, 2 failed, in
  21:32 beside another session's suite. The failures: `test_display`'s
  kernel test (a Jupyter kernel spec pointing at a deleted venv, the same
  on the pre-merge run), and `test_manual`'s twin cap, which this WP's text
  pushed 178 and 63 characters over on `reference/refinement` and
  `reference/parameters`; both trimmed, the test and `test_help` then
  27 passed. The pre-merge run (1 failed, 13294 passed, 315 skipped) is not
  comparable, since main moved between the two. Acceptance selection
  (`test_stephens`, `test_capabilities`, `test_acceptance_stephens`,
  `test_cross_backend`): 266 passed, 158 skipped (the jax/torch rows of a
  `[dev]` venv), 2 xfailed. `sphinx -W` exit 0; ruff clean;
  `python -m tests.reader_output` reports the standard fit unchanged. The
  full suite did not run: no golden or acceptance fixture declares a block
  over a nonzero `lor_strain` (the brucite fixture declares an all-zero
  block on a fresh phase, whose `lor_strain` defaults to 0).
  Added tests (local junit, the run above): six new functions,
  0.52 s together, the slowest 0.11 s; `test_stephens.py` +5 (0.51 s),
  `test_strain_cap.py` +1 (0.01 s). The cross-backend config and the TOPAS
  case are rows inside existing tests. None joins the slow tail.

  *Reader-output changes* (Yue's approval before merge): the
  `STEPHENS_STRAIN_NOT_POSITIVE` message gains the share sentence and its
  suggestion is rewritten; three `rietx.help` entries change;
  `microstructure_table` omits `lor_strain` (and `strain_agreement` is None)
  for a phase with a block; `STRAIN_UNUSUALLY_LARGE` no longer fires on a
  `lor_strain` under a block; the TOPAS writer, the refinement CIF's profile
  text and the peak-list CSV widths omit it too; fitted numbers move for any
  block declared over a nonzero `lor_strain`, including a saved project
  replayed.

  *Forwarded.* WP-1955 (`### Inherited`): the Gaussian-width floor's FD
  column and the LaB6 closing-stage xfail, with the six code citations
  repointed there. WP-1946 (`### Inherited`, Depends line): the joint fit's
  unseeded block and the seed comparison. WP-1946's priority is unchanged:
  its P3 rests on brucite's S_HKL being unquotable, which this WP did not
  move.

  *Generality* (the judge's report: the first and fourth sections verbatim,
  the others condensed; the author's answers follow).

  **`rietx.strategy.staged.STRAIN_SEED_PPM`** — **Verdict: weak.** Keeping
  1000 ppm has the stronger case. The row argues it from χ² wins, but the new
  numbers do not show those wins under the default LM driver. The real reason
  is not written in the row.

  | Question | Author's answer (where) | What I found | On this question |
  |---|---|---|---|
  | 1. What it decides | "lab_sample_refine's strain_seed, 1000 ppm on the isotropic ray" (`_audit.py`, row evidence) | It decides which minimum the fit reaches, so it can change a quoted result. On operando pattern 41 the two starts ended at phase fractions of 86.5/12.9 % and 9.5/89.6 % (WP file, Tasks, the seed note). | answered |
  | 2. Kind | Constant rows carry no `ambiguity` field: **none given** | That some start is needed is kind 1, because the width's square root has unbounded slope at zero. Which start to use is kind 2: the starts can be listed and χ² scores them. But χ² here only ranks two basins of one model, and those basins disagree on composition with nothing to judge them against. | none given |
  | 3. Case against | "The starts disagree by driver, so the fixed seed stands" (row evidence, added) | Under the default LM driver, fold was equal or lower both times: brucite 7.8939 against 7.8943, pattern 41 1.112 against 1.170. 1000 ppm won once, under TRF on pattern 41 (1.156 against 1.476), and lost under TRF on brucite (7.7965 against 7.9267). The pattern-41 LM comparison also flipped between source trees. On `95c2cae8` it was 1.196 (1000 ppm) against 1.488 (fold), per the WP's first table and the row's older clause "1.160 … against 1.482". On `0d735f5e5` it is 1.170 against 1.112. GSAS-II starts the generalised coefficients at 0.01 each, per the row's own evidence. That is a named dissent. | real, partial |
  | 4. Case for | "Some start is forced … the second compared them on 2026-10-20 and favoured 1000 ppm" (row grounds, unchanged) | The strongest case is one the row does not make: fold often has no start to use. Patterns 0 and 16 carry no `lor_strain` above 1e-100 (WP Tasks). On brucite, fold from 0.35 ppm "left the block at the singularity", χ² 8.3241 against 7.7662 (`SUGGEST_SEED_STEPHENS` row). After this WP a block replaces `lor_strain`, so a phase that has a block from the start carries 0 and fold is undefined. The grounds' "favoured 1000 ppm" is now contradicted under LM by evidence in the same row. | strong, but argued on the wrong evidence |
  | 5. Tier | tier 3, approved 2026-10-19 (B3) | Tier 3 is right. 1000 µstrain is GSAS-II's isotropic default; the row says this was checked in the source (`GSASIIddataGUI.py:180-190, :1432`), and I did not re-check it. Stephens strain is named in generality.md § The rule's "Where three families do not exist" clause, so the judgement ground alone suffices. | holds |
  | 6. Families and reference | CPD brucite, CPD corundum, operando pattern 41 (row evidence) | The row gives no laboratory or instrument for the two CPD sets, so I could not count them as unrelated. All three are development data: brucite is the acceptance fixture, and this WP was reworked on the operando series. The only reference is χ². Nothing independent stands beside pattern 41's swapped fractions to show which start lands nearer the truth. DESIGN.md Rule 4 bars an Rwp comparison as evidence, and a χ² comparison between basins is that comparison. | weak |
  | 7. Record field | not stated in the row | `StageResult.seeded` records it (`refine.py:4698-4702`, "second writer (WP-2002, B14)"). A joint fit never seeds the block; that finding was forwarded to WP-1946. | holds |

  What would change the verdict: grounds that state the real reason (fold has
  no start on a fresh phase) and give the 2026-11-02 numbers as they fall
  under LM, or a weighed composition for pattern 41 that says which of the two
  basins is right.

  **`rietx.schemas.plan.CLOSING_WINDOW_TOL`** — **Verdict: holds.** The change
  only moves the owner of the row's stated failing case from WP-1467 to
  WP-1955, and WP-1955 now carries that case. (Evidence only; value, tier and
  content unchanged; the same repoint landed in `plan.py`, the
  `test_window_domain.py` strict-xfail reason and `validation_matrix.py`; no
  `WP-1467` citation for this case is left in `src` or `tests`.) What would
  change the verdict: WP-1955 closing without taking the LaB6 case.

  **`rietx.schemas.plan.PlanSpec:closing_window_tol`** — **Verdict: holds.**
  The same repoint (`_audit.py:3893`); tier 2, its ambiguity, grounds and
  BGMN/RIETAN-FP/MAUD evidence untouched. What would change the verdict: as
  for `CLOSING_WINDOW_TOL`.

  **`staged.stephens_clamp_share`** (a heuristic the table cannot see) —
  **Verdict: weak.** Reporting a share and stopping is the right kind of
  response, and nothing acts on the number. The weakness is the meaning
  printed beside it: its label and its "in proportion" sentence claim more
  than the number measures.

  | Question | Author's answer (where) | What I found | On this question |
  |---|---|---|---|
  | 1. What it decides | "The weight of a reflection is its own integrated intensity with the scale and every angle-dependent correction left out: m·\|F\|² in Rietveld mode … the extracted per-hkl intensity … under Le Bail and Pawley" (`staged.py`, `stephens_clamp_share` docstring) | It decides which reflections count (any whose frozen window holds one fitted point, counted in full even if only a tail clips the range edge) and how each is weighted. The message calls the result "the phase's intensity on the fitted data", but Lorentz-polarisation, absorption and texture are left out. What it computes is a multiplicity times \|F\|² share, not a share of what the pattern shows. In a joint fit, `_stephens_once` keeps the first histogram's finding (`multi.py:2560-2564`), so the share describes one histogram only. | label overstates |
  | 2. Kind | **none given.** It is not a table row, and the code row `STEPHENS_STRAIN_NOT_POSITIVE` sits on `UNAUDITED_BASELINE` (`_audit.py:4988`). | Kind 3: it reports a number and acts on nothing. | holds, unrecorded |
  | 3. Case against | "the fit's other numbers leaned on them in that proportion" (message suggestion; also help.py, reference/refinement.md, skill `diagnostics.md`) | On the weight: a competent alternative weights by what the fit sees, the calculated counts or the χ² share on the reflection's points. The sibling `RESOLUTION_NOT_POSITIVE` counts fitted points. No program computes this share (practice.md's new Stephens section: TOPAS clamps and reports nothing, GSAS-II has no clamp). On "in proportion": **none given.** No measurement links the share to how far cells or fractions moved. The nearest is pattern 0, where the cone-enforced fit keeps 42 % of TRF's χ² gain (WP Context), and that is χ², not a result number. | real |
  | 4. Case for | "29 of 96 and 1 of 463 fired at one level on one pattern, carrying 25 % and 0.5 %" (`check_stephens_positive` docstring) | The case is strong: the reflection count could not separate those two findings. On the current tree the 0.5 % case no longer fires, and the four firing phases carry 19-52 % (WP Tasks; the WP-1946 note). The number moves no answer, so carrying it costs nothing. | strong |
  | 5. Tier | **none given** | The statistic is rietx's own. It has no threshold. The cone test reuses `STEPHENS_CONE_TOL` (tier 1). | none given |
  | 6. Families and reference | "Agrees with the review's probe to 0.4 points … 50.3/34.9/51.5/19.4 % against 50.5/34.6/51.6/19.6 %" (WP Tasks) | One family: the private operando series, development data. The probe used the same m·\|F\|² definition (WP Context, "used I_calc over the in-range reflections"), so the agreement verifies the code against a second implementation and validates nothing. `test_stephens.py::test_the_finding_carries_the_intensity_share_the_clamp_zeroed` checks the complement identity and the Le Bail arithmetic on synthetic brucite. | verifies only |
  | 7. Record field | `GuardFinding.detail`, then `Diagnostic.message` (`staged.py:1041-1048`) | Text only. `Diagnostic.value` stays the worst σ². An agent gets the share by parsing a sentence, whereas generality.md § Attention is a cost, clause 1, puts a number in a result field. | weak |

  What would change the verdict: a label naming what is computed ("share of
  the phase's m·\|F\|²"), or a weight that includes Lorentz-polarisation and
  texture; a measurement across the four phases tying the share to how far
  cells or fractions moved, or else dropping "in proportion"; and the share in
  a numeric field.

  **A declared Stephens block replaces `lor_strain`
  (`CompiledModel.lor_strain_term`)** — **Verdict: holds.** The case for it is
  arithmetic plus a measured χ² anomaly, and I found no competent refiner who
  wants a frozen isotropic floor under a block. (Kind 1, physics. Case
  against: none found; FullProf's `cuf1k.pcr` refines Y beside the Stephens
  terms, and rietx keeps `instrument.profile.y` under a block. Case for:
  strong, the `Atom.aniso` precedent and pattern 41's 1.427 against the
  isotropic 1.381. Tier 1 with six tests. Two readers still add `lor_strain`,
  `topas_input.py:392` and `fullprof.py:4148`; the WP says both refuse a block
  outright, not verified by the judge. A saved project with a block over a
  nonzero `lor_strain` replays to a different curve, which belongs in the
  release notes. Minor gap: `Refinement.parameters()` lists the stored value
  as a locked row and nothing on that row says the value is unused.) What
  would change the verdict: a competent protocol that holds a fixed
  per-phase isotropic strain beneath a Stephens block.

  **`STEPHENS_STRAIN_NOT_POSITIVE.suggestion`** — **Verdict: weak.** "Refit
  under LM" and "compare a few starts" are well supported. But the rewrite
  drops two remedies a competent refiner would try, its joint-fit advice
  abandons the joint fit, and its "in proportion" sentence is unmeasured.
  (Case against, real: (a) fewer free terms, as the sibling
  `TEXTURE_NOT_POSITIVE` row advises "hold the highest terms"; (b) a wider fit
  range measures more directions, and the motivating case cut at 2θ ≤ 35°;
  (c) "fit each histogram alone" gives up the shared crystallite size, and
  keeping the joint fit while reducing or dropping the block is the competent
  alternative, nor does the suggestion say a joint firing may come from the
  S ≡ 0 start; (d) "in proportion": none given. Case for, strong for what it
  kept: LM holds the cone, 0 of 43 against 19-23 under TRF on brucite, and
  starts matter on pattern 41.) What would change the verdict: restoring
  "hold the highest-order coefficients" and a conditioned "extend the fit
  range where you cut it"; a measurement backing "in proportion", or the
  sentence cut; or a maintainer ruling that a joint fit firing this guard
  should be split.

  Author's answers. `STRAIN_SEED_PPM` (weak): the row's evidence now gives
  the reason the judge names (fold has no start on a phase without a carried
  `lor_strain`, including any phase given its block at the outset) and states
  the 2026-11-02 numbers as they fall by driver; its grounds clause is older
  and left. `stephens_clamp_share` (weak): the message, `help.py`, the theory
  page, `reference/refinement.md` and the skill row now name what is computed
  (the phase's m·|F|² over the reflections in the fitted range) and drop "in
  proportion", which no measurement backs; a numeric field for the share is
  not added, since `Diagnostic.value` already carries the worst σ² and a
  second number there would need a schema field. The suggestion (weak): "in
  proportion" dropped, and a joint fit may drop the block instead of being
  split. Declined: "hold the highest-order terms" has no analogue, since all
  fifteen S_HKL are one order; "extend the fit range" is unmeasured here.


  *Gotchas.* The worktree Bash guard refuses `cd`, inline `PYTHONPATH=` and
  computed variables, so probes ran from scripts in the ghostshift scratch
  directory against `git archive` snapshots. `ParameterTable` takes no
  `mode=`; a Le Bail test builds a plain table.

  Next: none in this WP. Yue's call on the reader-output changes above, then
  merge. WP-1955 and WP-1946 hold the two follow-ups.

- **2026-09-25** — created by a review of the second agent session on
  `in-situ series 1`, asked whether rietx presents Stephens correctly. Every
  number above is the review's own re-run, not the session's pickles. The
  floor was found while explaining why lm sat above the isotropic fit. Next:
  task 1, then the seed, since both move the numbers the guard tasks report.
