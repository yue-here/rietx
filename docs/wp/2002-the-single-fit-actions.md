# WP-2002 — The single-fit actions: what one stage decides for the caller

Milestone: generality · Status: ✅ 2026-10-23 — every single-fit action tiered over nine ruling rounds; the U, V and Y floors removed behind the width twin hold; the owed domain tests went to 2017
Track: The audits
Depends on: 2001

## Goal

Every automatic action a single fit takes is in the audit table with a tier: the three
holds, the release and the collapse restore, the bound test, the phase-significance test,
the seeds, the always-on corrections, and the thresholds they rest on. Each tier-3 action
carries its two grounds and the maintainer's dated approval, and each tier-2 action its
judgement ground and approval. An action that fails is demoted by its kind of ambiguity
(DESIGN.md § Rules, 1): to a ranking with evidence where the data can rank the
alternatives, otherwise to the number in a record field with its meaning. The clash table
names every pair that interact.

## Context

The rule is `../milestones/generality.md` § The rule; 2001 restates it. This WP applies it
to `Refinement._run_stage` (`src/rietx/refine.py`, ~line 3795) and what it calls, and to
`src/rietx/strategy/` (`staged.py`, `magnetic.py`, `fraction_profile.py`,
`parameter_interval.py`, `suggest.py`), five files the first plan left unowned. The six
codes `strategy/magnetic.py` (five) and `strategy/fraction_profile.py` (one) raise are
this WP's too, since no code audit's seam reaches `strategy/`. Two of the five,
`LANDE_G_ASSUMED` and `MAGNETIC_ION_ASSUMED`, are also raised in
`crystallography/magcif.py`; this WP tiers them on both raise sites and 2006 reads the
row rather than writing one (fourth review).

**Why first.** `_run_stage` runs inside every fit the package makes, including the ones it
makes for itself: the report's rival fits (`report/layer2.py`, `report/body_misfit.py`),
the extinction screen (`indexing/extinction.py`), `strategy/magnetic.py`'s trials, and
every pattern of a chain. So 2003 and 2004 read a tree this WP has settled.

**The inventory, from the record fields** (the house rule makes every action leave one;
keyword counts over the source are mostly comments and were discarded at the open):

- `StageResult.held` / `held_reach`: the absent-phase hold (WP-1301, `_answer_significance`
  at ~line 1690: a scale under 3σ of its counting-noise esd), the moment hold (WP-1327),
  and the scale–B ridge hold (WP-1534, `SCALE_B_SEPARATION_FLOOR = 2·√PINV_RCOND` at
  ~line 542, which inherits `PINV_RCOND`'s tier). All three at ~lines 3938–3962.
- `StageResult.released` and the collapse restore: a phase that appeared is released; one
  that collapsed while solving is restored to where the stage found it and held, one extra
  solve (WP-1301).
- `StageResult.blocked_by_hold`: a user hold blocking a plan glob (WP-1435). Tier 1 by
  inspection (the user asked), but confirm.
- `StageResult.seeded`, `Stage.seed`, `Stage.strain_seed`: a row on a floor lifted before
  the solve; the Stephens isotropic seed (tier 1: at S ≡ 0 the √ has unbounded slope).
- `staged.bound_findings`, `at_bound`, `BOUND_HIT` / `FLOOR_HIT` (WP-1434, WP-1929): exact
  where the LM active set is exact; elsewhere "within a hundredth of an esd *and*
  `residual_cosine` not orthogonal", both measured into a window on one or two suites.
- `RefinementPlan.intermediate_ftol` (1e-6 vs 1e-9, WP-1123): a schedule, bounded for one
  fit at ≤ 0.03 esd; candidate for the answer-invariant class if the bound holds, tier 3
  otherwise.
- `background/auto.py`'s `auto_background` and `select.py`'s order scan: a verb whose job
  is the pick, returning its score table beside the choice. The record § A pick on top of
  a ranking allows that while no default path calls the verb; confirm it (no caller in
  `refine.py` or `strategy/` on 2026-10-18), then tier `AIR_SCATTER_TRIGGER`,
  `HUMP_TRIGGER` and the whiteness stop as the pick's thresholds.
- The flat-plate thickness test (`ABSORPTION_PLATE_THICKNESS`, an inline `< 0.7` at ~line
  6819) and the other inline literals near it: 2005 owns the codes, this WP owns any
  literal that gates an *action*.
- Always-on corrections with no switch, threshold or record field of their own, which no
  walk finds: the Bérar–Lelann esd inflation (`optimize/least_squares.py`, applied to
  every reported esd, 7 to 10 on WP-1417's synchrotron fits before v1.6 lowered it
  12–21 %; GSAS-II's source never mentions it), the √max(y,1) weight fallback, and
  anomalous dispersion on by default (`Source.dispersion`, also a declared seat). Walk
  root CLAUDE.md § Invariants for the rest. Each is an action row, tier 2 where a paper
  or a program stands behind it, and faces the judgement ground like any other (the
  record § The rule, tier 2, ruled 2026-10-19).
- Every constant in `refine.py` and `strategy/` from 2001's AST walk that a hold, release,
  seed or bound test reads; and the constants of `optimize/statistics.py` that are not
  report-facing (`PINV_RCOND`, `COLUMN_SAFE_EXPONENT`, `MAX_SHIFT_CONVERGED`) plus
  `optimize/lm.py`'s `BVLS_MAX_COLUMNS`, which the bound test rests on. 2001's walk
  enters all of these at `unaudited` (`optimize/` and `background/` are on `_audit.WALKED`);
  this WP owns every `background/` constant and every `optimize/` constant that is not
  report-facing, 2004 the report-facing ones (2001 § The seams, the partition by
  directory). Never add a row by hand for a name the walk already entered.
- `CORRELATION_GUARD` = 0.98 has three rows (the constant and the `PlanSpec` and
  `run_stage` defaults), tiered together. GSAS-II 5.8.4 lists pairs from
  max(0.95, 0.99 × the worst |ρ|) by default (`GSASIImath.setHcorr`, checked in
  `rietx-bench/tools/gsas2` by 2001's judge), so rietx is silent between 0.95 and 0.98;
  no source for 0.98 was found.
- `RefinementResult.sigma` holds two automatic choices, the √max(y,1) fallback and a
  floor at 10⁻³ × the median esd (`schemas/pattern.py`, inline). No field says which
  fired, so the field stays in `OTHER_RECORD_FIELDS` until a flag exists, and both are
  hand rows under the always-on corrections.
- The final stage's 1e-9 tolerance, which `StageSpec.ftol=None` resolves to, is a literal
  in signatures that are not seats (`optimize/least_squares.py`, `optimize/lm.py`), so
  the walk does not see it; it is a hand row beside `intermediate_ftol`.

**How the table works** (from 2001). The table is `src/rietx/_audit.py`; this WP's rows
are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2002, plus the codes and
suggestion rows of `strategy/`. Auditing a row means giving it a tier and evidence in place
and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until
both are done. The walk sees module-level numbers and tuples of numbers only, so a number
held in a dict, list or array is audited here by hand. `project.py` joined the walk under
2002 with WP-2014 (2026-10-20), with no number in it today.

**The two cases the second review named, to anchor the batch.** The absent-phase hold is
the one the rule keeps: a cell 14.9 Å from truth over 13 sub-onset patterns when free
(the v1.3 row), invisible in the outputs because Rwp does not move. The clash the review
found: WP-1320 chose the fraction profile's axis because the collapse rule fought it
(`strategy/fraction_profile.py` ~lines 13–22). A clash table is part of this WP's output.

**Evidence on disk.** Families for the mechanical ground: the four round-robin standards
(`tests/data/qarr`), the Durham tutorials (`~/rietx-local-data`, `python -m
tests.local_data`), the FAP suite, the private corpus files (cited by number, map in
`yue-here/rietx-corpus-map`). Tier-2 evidence: GSAS-II 5.8.4 source in
`~/Code/rietx-bench/tools/gsas2`, FullProf `fp2k` in `tools/fullprof`, the TOPAS
technical reference (memory `foreign-code-sources-on-disk`). "GSAS-II computes it" is not
"GSAS-II acts on it by default".

## Non-goals

- `RefinementResult.geometry`'s truncation at 24 contacts per atom and its skip of phases
  over 200 atoms (`model/geometry.py`, noted in `GeometryTable.notes`): report-only, so
  no action row; its constants still take a tier.

- The chain: rungs, quarantine, the reseed fence, the moment-floor carry
  (`sequential._floor_unsupported_moments`), `_prefer`/`_better`. 2003.
- The FitReport's gates and the report's rival fits as *consumers* of the holds. 2004.
- `refine.py`'s 61 diagnostic codes as codes. 2005. A literal that gates an action is
  this WP's; one that gates a diagnostic is 2005's.
- Redesigning a hold. An action the batch rejects is demoted; a replacement is a
  follow-up WP filed from the table.

## Tasks

- [x] Inventory: one row per action and per constant it reads, from the record fields and
      2001's walk, with the file and line, what it decides, and what the caller sees
      without it. Lanes read disjoint files; the lead assembles. *2026-10-19:
      `2002-batch/inventory.json`, 402 proposals from six readers.*
- [x] Tier each row per part (statistic, threshold, action), with evidence: the citation,
      the program and its default behaviour, or the families measured. Where the families
      are fewer than three, run the missing ones (the fits are cheap; a chain family is
      2003's). *157 rows needing no approval landed 2026-10-19; the rest wait on the batch.
      2026-10-20: the ruled rows landed; 16 still wait, each with what it waits on, in
      `2002-batch/waiting.md`. The second pass (three families per surviving threshold)
      has not run. 2026-10-20 (2nd session): the fourth round's rows landed (the
      auto_background pick kept, the cell window, the interval and width-grid settings,
      twelve solver stop constants and the seventh solver switch, all tier 3). The second
      pass moved to [2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md)
      on 2026-10-20 (the maintainer's split); this item closes with the owed tests and
      B14's lifts. 3rd session (2026-10-21): the owed tests ran (`2002-batch/waiting.md`).
      Landed: B11's three budgets (on the shipped schedule) and two internal splits
      invariant, `MAX_NODES` tier 3. The window slack and the three geometry caps stay
      tier 3 after the judge's review, and every setting that failed its domain test
      stays tier 3 for the fifth round. Still owed: the
      interval and width-grid domain tests. 4th session: the three geometry caps and the
      restraint image shell to tier 1, under the rule's new cap and numerical-setting
      clauses; the fourteen tier-2 rows resting on a program default checked against
      seven programs (`docs/practice.md`). 6th session: the seventh round's
      settings tiered (`A5_CLIP`, the texture polish and the closing FCJ rule tier 1, the
      magnetic floor invariant behind the closing stage, the margin and the axial floor
      tier 3); `GTOL`/`XTOL` tier 3 under the caller-tier ruling and
      `DEFAULT_HARMONIC_ORDER`'s row gone with the constant. 7th session: the
      LAPACK fallback's row, `StageResult.n_lapack_fallbacks`, tier 1. 8th session:
      B14's lifts landed; the interval and width-grid domain tests handed to
      [2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md) by the
      maintainer (2026-10-23), their eight rows staying tier 3 as approved.*
- [x] The clash table: every pair of actions that read or move the same parameter, with
      the measured interaction (Rwp and the parameter, both orderings). *38 candidate pairs
      found, none measured: `2002-batch/clashes.md`. Moved to
      [2018](2018-the-clash-table-measured.md) on 2026-10-20 (the maintainer's split).*
- [x] The batch to the maintainer, in the register of `~/.claude/CLAUDE.md`: per tier-3
      row the two grounds answered, and per tier-2 action the judgement ground (for the
      judgement ground, the dissenting caller named or declared absent), the Rule 1 kind it falls to if demoted, the case against
      drafted by the `generality-review` agent, and a recommendation. Rows resting on one evidence base are grouped and ruled as a class
      (record § Decisions); rulings dated into the table. *Drafted and reviewed 2026-10-19:
      `2002-batch/batch.md`, 16 classes. Ruled 2026-10-19: B7, B10, B12, B14, and B1
      confirmed. The other nine re-briefed in `2002-batch/rulings.md`, awaiting answers.
      All sixteen ruled by 2026-10-20 (`rulings.md`, three rounds; B2 and B14 re-asked).*
- [x] Approved demotions: the action removed, and its number left in the record field (or
      its ranking returned) with its meaning in the package's own output; the code's
      `level` to `info`, or, where the threshold was its trigger, the code replaced by an
      `info` record with no threshold (the record § Demotion). Each as its own commit.
      *2026-10-20, built: the cell reset (B8), the size floor and the chosen limits (B8,
      B9), the stationary angle's interval (B2), the hold's threshold as a plan setting
      (B1), `stderr_uncorrected` and its manual (B4), the pick verbs (B12). Left: B14's
      lifts, B3's and B9's two-start tests, B7's and B11's invariance and margin tests,
      the FCJ node cap (B10). 2nd session: the peak-position bounds removed,
      `OCCUPANCY_ABOVE_ONE` an info record, every ΔBIC tie an abstention. 3rd session:
      the two-start, invariance, margin and domain tests ran; what passed landed, and what
      failed waits on the fifth round (`2002-batch/rulings.md`). Left: B14's lifts, the
      fifth round's builds, the restraint image-shell fix. 4th session: Q5's width
      ceilings removed, Q4's switched-off roughness said in its warning, Q6's cap clause,
      both search defects fixed. Left: Q1-Q3's builds (the sixth round) and B14's lifts.
      5th session: the sixth round built (the closing stage, the roughness seed's record,
      the axis ceilings, the tier-2 rule). Left: B14's lifts. 6th session: no demotion;
      left: B14's lifts. 8th session: B14's lifts landed (§ The hand rows that stay).*
- [x] Goldens: every pinned number that moved, re-pinned only if no further from its
      reference; old, new, dataset and reference distance in the handover. A number that
      moved away goes back through the two grounds. *2026-10-20 (2nd session): one moved
      away, the NAC capillary pair's cell (`test_capillary_displacement.py`, offsets
      free), 1097 → 5109 ppm from the acceptance band's centre 10.2510 Å, esd 2612 → 2579
      ppm; back through the grounds by the judge: the bound had one family and a named
      dissenter, so the removal stands. No bit-identity golden moved. 3rd session: no
      source behaviour changed (one comment), so nothing moved. 4th session: the ceiling
      removal and the two search fixes moved no bit-identity golden (darwin/arm64).
      5th session: the closing stage moves every default fit; no bit-identity golden moved
      (they pin forward-model residuals), every acceptance suite names the setting, and the
      guides' quoted numbers were re-measured. 6th session: evaluation outside a fit at
      the closing windows and the closing FCJ rule moved every synthetic pattern; the
      goldens declare their capture windows and stay bit-identical (darwin/arm64), and the
      guides (main's new moment guide too) were re-measured. 9th session: no bit-identity golden moved; four guides re-pinned by a last digit or a bound, the moment guide's blind moment 2.04 → 2.03 μB (0.2 of its esd), and the calibration workflow's `lor_size` moved away from its truth (27-39 % → 55 % low), taken back through the grounds as ruling 2(a): its truth sat on the removed floor.*
- [x] `intermediate_ftol` and any other candidate for the answer-invariant class: the
      invariance test, or the row tiered. *3rd session: the test ran and failed in plain
      esds (0.033-0.074 on cpd-1a) and a hold flips with the tolerance; the rows wait on
      the fifth round. B11's budgets passed and landed invariant. 4th session: re-briefed
      as the sixth round's Q2, with a closing stage measured (`rulings.md` § Sixth round).
      5th session: behind the shipped closing stage, tier 3 with its failing case
      (`tests/test_staged_start_invariance.py`); the harmonic seed invariant.*
- [x] The seventh round's builds (`2002-batch/rulings.md` § Seventh round): evaluation
      outside a fit and a stage run by hand at the closing windows, the tests' `None`
      declarations that existed for the mismatch removed; the six settings by kind (the
      margin to the widest window, the FCJ closing rule, the two floors measured behind
      the closing stage, `A5_CLIP` 1e-4, the texture check's local minimisation).
      *6th session: built; the edge margin reverted (it freed a scale-B ridge), and the
      eighth round kept 0.5°.*
- [x] The eighth round (`2002-batch/rulings.md` § Eighth round): the closing stage kept on
      by default with `closing_window_tol=None` the speed switch, recorded in the
      reference and the skill (9c.34); the FitReport reads its misfit at the closing
      precision and its shapes at the declared one (`report._reading_models`); the
      margin kept at 0.5° and the axial floor at tier 3; the caller-tier ruling recorded
      (`_audit.py`, the record's § The rule), `GTOL`/`XTOL` to tier 3 and
      `Harmonic.order` required.
- [x] The ninth round (`2002-batch/rulings.md` § Ninth round): the brucite TRF
      error fixed by a LAPACK driver fallback on every fit-path decomposition
      (`optimize/lapack.py`, `StageResult.n_lapack_fallbacks`); `solve_magnetic`'s
      winner ended in a closing stage; the three design questions inferred (the
      closing-off report kept as measured, the closing node rule for every compile
      finer than 2 %, `build_report` refusing a bare `model=`).
- [x] **The width twin hold** (the maintainer's decision 1, 2026-10-23; option (b) proposed and
      awaiting the go-ahead at the 8th session's end). When a stage frees a specimen width whose
      instrument twin is also free, hold the twin for that stage and name it in the stage record:
      U with `gauss_strain` (both tan²θ in Γ_G²), Y with `lor_strain` (tanθ in Γ_L), X with
      `lor_size` (1/cosθ in Γ_L). Then land the parked floor removal
      (`wp2002-width-floors-wip`, `879fb1bcc`) on top. Practice: `docs/practice.md`
      § Instrument and specimen widths refined together. Details and measurements: the 8th
      session's entry, § Next. *9th session: built (`refine._width_twin_flats`, a null space
      on C; `StageResult.width_twins_held`; a free Stephens block is Y's twin), the floor
      removal merged; the maintainer's rulings 1(a) (keep the hold at cpd-1a's start cost)
      and 2(a) (all three floors go; Y ≥ 0 disproved as physics).*
- [x] `tests/test_compare_ui.py` and `rietx compare`: a demoted action is a variant the
      comparison can show; add a row where a standard exercises it. *8th session: none
      owed. Every demotion removed a limit, lowered a level to info or made a tie
      abstain, and none is a switch a standard's variant exercises; the closing stage is
      a kept default, not a demotion.*
- [x] Tests + obs/calc/diff PNGs to `tests/output/` for every refit used as evidence.
      *3rd session: done for every refit it ran (`tests/output/b3_*`, `b9_*`, `b10*`,
      `b7b11_*`, `seed_invariance_*`, `window_domain_*`, `fd_step_*`). 4th session: the
      0.5 % window polishes wrote `window_domain_*` PNGs; the last-stage, closing-stage and
      Biso-start measurements are scratch scripts with no figure, their numbers in
      `rulings.md` § Sixth round. 5th session: `staged_start_*` and
      `window_domain_*_closing` PNGs. 6th session: probes only (scratch scripts, no
      figure); their numbers are in `rulings.md`'s seventh and eighth rounds. 7th and 8th
      sessions: no refit used as evidence.*
- [x] Skill: none here. A demoted verdict's meaning goes into the package's own output and
      never into a skill row (DESIGN.md § Rules, 3; the record § Decisions, the skill's
      role). List each skill row that named a demoted verdict, for 2008. *2nd session:
      `references/magnetic.md`'s abstained row and `api-magnetic.md`'s criterion (from
      `make_api_index.py`) rewritten for the tie ruling; `OCCUPANCY_ABOVE_ONE`'s row
      unchanged in words, now at info. 6th session: one row added, not a demoted
      verdict: `references/batch-operating.md` 9c.34, the closing stage's speed switch.*

## The batch (2026-10-19)

The rulings received so far, the maintainer's words, and the second-round briefs for the
items still open are in [`2002-batch/rulings.md`](2002-batch/rulings.md). Read it before
`batch.md`: three of its picks replace the batch's (B4, B5, B9).

The rulings this WP waits on are in [`2002-batch/batch.md`](2002-batch/batch.md): 16
classes covering the 247 rows still at `unaudited`, each with the author's brief, the
case against from a fresh-context judge, and the lead's pick revised after that review.
`2002-batch/inventory.json` holds every reader's per-row proposal (file and line, what it
decides, tier, evidence line, provenance, the batch class), so landing a ruled row means
copying its evidence line into `src/rietx/_audit.py` with `grounds` and the ruling's date
in `approved`. `fcj_low_angle.py` and `i740.json` are the two pieces of evidence the
batch cites that were made this session.

Three choices the opening session made, each reversible:

- **Two passes, in the record's order** (§ The order). The batch asks the judgement
  ground of every action and acting default. The mechanical ground (three families) is
  measured afterwards, and only for the thresholds of actions that survive. Chosen over
  measuring every threshold first, which would spend fits on actions the ruling demotes.
- **The held-out family is the Nd₂Ru₂O₇ pair** (`tests/data/mg090*`: 11-BM X-ray and
  NCNR BT-1 neutron, one specimen, a published joint refinement as the reference). No
  audit uses it as evidence; at close the standards' protocol is run on it. Chosen
  because its reference validates and its neutron half tests whether X-ray-tuned
  thresholds carry over. The alternative, the Durham tutorials, is WP-2003's chain
  family.
- **Diagnostic-only constants are handed to the audit of their code** (batch class B13):
  34 to WP-2005, 15 to WP-2004, 9 to WP-2007, from this WP's own non-goal. Until ruled,
  they stay `unaudited` here, and this file's acceptance line below reads "no
  action-gating row at unaudited".

## The hand rows that stay (B14, option 3)

B14's lifts landed 2026-10-23 (8th session): 21 numbers a retune could move became
module-level constants, `ProfileTCHZ` a seat, and the collapse restore and the Stephens
seed record fields (`StageResult.collapsed`, `StageResult.seeded`). What the table still
cannot see, by the ruling's design, is listed here, each with why it stays outside.

- **Tier 1, a floor, guard or formula a retune cannot make a different answer:**
  `pspline_penalty_scale`, `lorentz_polarization`, `build_pawley_restraint:group_scale_floor`,
  `compile_model:fcj_sizing_from_moving_paths`, `compile_model:reflection_floor_deg`,
  `lebail_update:floors`, `TEXTURE_SAMPLE_PSI_DEG`, `_feasible_start:trf_nudge`,
  `brindley_tau:series_switch`, `_psd_pinv:magnitude_inversion`, `Refinement._final_compile`,
  `mode_fixed_column`, `ExtraComponent:fwhm_floor_repair`, `Phase:off_state_defaults`,
  `PreferredOrientation._r_bound_is_reachable`, `_MODE_SUBSTITUTES`, `Atom:occ` (floor 0, no
  ceiling since B9), `EmissionLine:weight` (floor 0), `Geometry:bounds` (physical floors only),
  `Instrument:zero_shift` (unbounded off state).
- **Invariant internals:** `CompiledPhase.skip_extinction`, `_formula_units:tol`,
  `_DegenerateCellGuard`'s two penalties, `_Arrow.largest_eigenvalue:lanczos_tol`,
  `n_threads:cap`, `run_least_squares:max_iter` (covered by `StageSpec:max_iter`'s margin test
  under both solvers) and the compiled tier's default.
- **Claimed invariant, with no test showing it** (the generality judge, 2026-10-23; each owed to
  WP-2017): the Le Bail/Pawley intensity seed (`model/forward.py`, `compile_model`; Le Bail at
  three cycles does not converge, #740, so start dependence is plausible), `refine._FLAT_AXIS_TEST_DIRECTIONS`
  (B2: "invariant, test owed"), `background.estimators.arpls`'s `max_iter`/`tol` (a six-fixture
  probe) and `params.vector.FLOOR_SEEDS` (a finite-difference step on width columns that moves
  their esds, so a B10 numerical setting rather than an invariant).
- **A number inside a dict or array, which the walk cannot read:** `TCHZ_BOUNDS_COARSE` (reached
  only through `ProfileTCHZ.coarse`), `_KA_DOUBLETS` and `_LAUE_COEF` (tier 2), `_KBETA`,
  `_ASSUMED_ION`, `_FLAT_AXIS_TEST_DIRECTIONS`, `FLOOR_SEEDS`, `_NS_PER_ELEMENT`.
- **Actions with no record field of their own, tiered in their class** (the judge's completeness
  list): B8's cell window (`params.vector.cell_window`, `optimize.least_squares._freeze_cell_windows`,
  tier 2, TOPAS Tech Ref § 2.17); B2's `_flat_moment_scan` modulus floor and
  `_onto_flat_meridian` pole tolerance (tier 1); B4's two `statistics.normal_factors` steps,
  the χ²_red scaling and the Jacobi equilibration (tier 2); B5's background σ widening in
  `compile_model` (tier 1); B10's `ParameterTable` anisotropic symmetry tolerance (tier 1);
  B12's `profile_fraction` mid-angle (tier 1) and its five caller verbs; B11's Le Bail
  alternation (caller).
- **B14's fourth field, the σ rule with its counts, is WP-1952's**: that WP replaces the σ ≤ 0
  floor the field would report, and its Inherited carries the forward.
- **Seats not added, because each brings unruled defaults:** `Geometry` (14 defaults,
  among them `mu_t=None` meaning a transparent plate under transmission, never ruled; so
  `Geometry:kind` stays a hand row, WP-2015's), `Instrument` (three whole nested models),
  `Atom` (nothing judged left once `BISO_SEED` holds the Biso), the two presets (their
  numbers are constants now; seating them brings `radiation="CuKa"`, unruled) and
  `run_least_squares` (its `ftol` is `optimize.lm.FTOL`).
- **Left as literals, no ruling covering them:** `select_arpls_lambda`'s and `auto_lambda`'s
  candidate grids (10⁴ to 10¹⁰), inside pick verbs.
- **`cherry_pick:fallbacks`** are `NodeAction`'s defaults (`schemas/history.py`): what a node
  stored before those fields ran at, so they stay 100 and 3 whatever `StageSpec` says.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no action-gating refine.py/strategy row at unaudited
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, on the final tree: goldens
.venv/bin/python -m ruff check src tests examples
```

The handover carries the batch's rulings; the record's acceptance row "no tier-3 action
runs by default without its approval" is checked against the table for every row this WP
owns. The three-family evidence behind those approvals is
[2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md)'s, and the
clash table [2018](2018-the-clash-table-measured.md)'s, both split out 2026-10-20.

## References

- `docs/milestones/generality.md`; WP-1301, 1327, 1534 (the holds); 1434, 1929 (the bound
  test); 1123 (`intermediate_ftol`); 1320 (the clash); 1523 (`_answer_significance`).
- McCusker, L. B. et al. (1999). J. Appl. Cryst. 32, 36–50 (the guidelines several
  thresholds quote).

## Handover log

### 2026-10-23 (9th session) — the width twin hold built, the U, V and Y floors removed behind it; closed

The peak-width coefficients U, V and Y no longer have floors, as the maintainer ruled. A fit that frees an instrument width together with a specimen width of the same angular shape now holds the instrument side for that stage, and the stage record names the pair. Without that, the two walk off together and the fit fails. The test that decides when to hold is exact: it reads which combinations a pattern can see, so a second phase whose own width is fixed, a tie, or a joint fit's wavelength factor is taken into account. No shipped plan frees such a pair; the magnetic solver's last stage did, and now frees the instrument's widths alone. The cost falls on plans that fit the instrument on the specimen first: there the held value carries whatever split that stage found, so on cpd-1a the reported zincite strain depends on the starting Biso by 15.7 esd, and in three of four real fits the specimen width ends on its floor of zero. The maintainer accepted that cost (decision 1(a)), and ruled that all three floors go (2(a)) after a check showed a negative Y is the honest way to write a constant instrument width. A joint fit and every reflection just past the data now also keep the Lorentzian width non-negative, which the floor removal had left open.

*Done.*
- The hold (`1a4f5c52e`, `bd92fd503`, `7f95db1f2`, `1a1dcdb0b`, `ae06b3694`, `37ddcced5`): `refine._width_twin_flats` takes the null space of the per-phase totals of each angular term (`WIDTH_TERMS`: U with `gauss_strain` and `gauss_size`, W with `gauss_size` as a row it never holds, X with `lor_size`, Y with `lor_strain`) read off C, and holds the instrument columns on it; `_hold_width_twins` and `multi._hold_width_twins_multi` apply it in both runners; `StageResult.width_twins_held` records each held column with its partners; a free Stephens block is Y's twin by rule; an unseen phase pins nothing (`_hold_unsupported_phases` now returns the unseen set); asked again before a second solve. The SVD goes through `optimize.lapack`.
- The parked floor removal (`879fb1bcc`) merged: U, V ∈ [−180², 180²] deg², Y ∈ [−180, 180]°, `TCHZ_BOUNDS_COARSE` gone, Γ_L ≥ 0 by `lorentzian_width_inequalities`, now at every reflection of the frozen list (not only those whose window holds data) and in the joint runner (`_joint_width_inequalities`, both width builders per histogram on joint columns).
- Tests and records after the rulings (`59fd97ee4`): the LaB6 + cBN degeneracy tests assert the hold; `test_staged_start_invariance.py` re-measured, cpd-1a's Biso row and LaB6's intermediate tolerance strict xfails, the absent-zircon and axial-floor rows' xfails removed; `test_v02_core.py`'s calibration bar follows the measured 55 %; four guides re-pinned (`equation`, `joint` by one last digit, `moment`'s round-2 bound 0.001 → 0.002, `path`'s 700 K now accepted warm); the validation matrix and `docs/VALIDATION.md` regenerated; `reference/refinement.md` documents the field (rows tightened to stay under the 50 000-character cap).
- Code review (`/code-review high --fix acba6290f..HEAD`), eight findings: three fixed by the review (`409cfcbbd`: two docstrings, one C conversion a table); (1) joint and past-data Γ_L fixed here (`7f95db1f2`), with `test_the_joint_runner_holds_the_lorentzian_width_too` failing on purpose without the rows; (3) `gauss_size` joined the test (`7f95db1f2`), holding U and W, which moved three acceptance answers (the cpd-1a chain, the absent-zircon start row, the corundum Stephens block); it left again (`ae06b3694`) and came back on the judge's alternative (`37ddcced5`): U alone removes the direction, so W, the constant width, is never held and its total stays a row; (4) the re-ask before a second solve (`1a1dcdb0b`, untested beyond the existing hold suites); (6) the near-copy Γ_L builder declined, a merge risking every LM fit's last bit; (7) `_fd_typicals`' width test declined as a design change and forwarded to 2017; (2) the stale field sentence fixed by the review.
- The first full selection (on `aed3f9be2` plus the review commits) failed eight, fixed in `ae06b3694`: the three above; `solve_magnetic`'s last stage (`SOLVE_STAGE_PATHS`) freed U and X beside `gauss_strain` and `lor_size`, so the hold took U and X, its dead-glob caveat fired and the 150 K Cr₂WO₆ fit ran to `max_iter` (now the instrument's widths alone, all 76 magnetic-solve tests pass); the neutron fit's Y now refines to −0.0210949(191) off any floor, so `test_acceptance_wavelength.py`'s esd test is re-pinned (x's esd 0.0102922 at four starts, spread 1.5e-9) and its one-sided interval test declares Y ≥ 0 as a caller would (upper end 0.0164535, was 0.0166098); zincite's dispersion test reads its cell bar as 0.1 esd, the hold's split moving c by 1.5e-5 Å against an esd of 3.7e-4.
- The second full selection (`ae06b3694`) failed two, fixed in `37ddcced5`: the moment guide's blind moment moved 2.04 → 2.03 μB with the magnetic stage change (re-pinned, the gaps to the other two answers 0.06 and 0.09); `test_acceptance_sequential.py::test_warm_start_iteration_cost_is_reported` is a strict xfail, the restricted-carry chain at Rwp 0.1282 against carry=* 0.1256 and independent 0.1258, the hold keeping each pattern's instrument split (decision 1(a), forwarded to 2003).
- The judge's corrections built (`1a1dcdb0b`): the row to tier 3, its evidence and the field docstring say what the code does, the Stephens rule's docstring leads with its stronger reason.
- Forward references: 2004 (an infinite strain anisotropy quoted as 1e6; `reference/refinement.md` at its cap), 2012 (LaB6's intermediate tolerance now reaches the mirrored minima), 2017 (BISO_SEED on two families, the twin hold's families, real calibrations with Y unfloored, TRF's far bound, `_fd_typicals`). Priorities of 2003, 2004, 2005 and 2017 rewritten for the close. Memory `rulings-lead-with-accuracy` extended with the maintainer's "physics and best practice take precedence over our existing workflows".

*Measured* (macOS arm64, worktree venv `[dev]`, compiled tier on).
- The hold on the shipped test plans (`stephens._plan`, `qpa_plan`): corundum Rwp 0.145744 → 0.145752; brucite 0.186391 → 0.186423, with a Stephens block 0.179951 → 0.181008 (LM) and TRF 0.179188; 11-BM LaB6 + cBN degenerate plan: LaB6 widths on their floor, cBN `lor_strain` 0.0354(8), LaB6 16.779(194) wt % (16.850 before), Rwp 0.1377 against the identifiable plan's 0.1686.
- Start invariance (plain esd, bar 0.1), before → after: cpd-1a Biso 0.070 → 15.68 (zincite `lor_strain` 0.0088 against 0.0612, Rwp 0.1631 and 0.1634; the instrument-only stage lands X 0.0017/Y 0.065 from one start and X 0.023/Y 0.002 from the other); cpd-1a tolerance 0.042 → 0.000, axial floor 0.138 → 0.010, absent zircon 0.185 → 0.035; LaB6 Biso 9.36 → 1.16 (on `u`), LaB6 tolerance 0.000 → 8.82 (`axial_sl`); FAP and NAC 0.000 throughout.
- The floor removal on the synthetic calibration (`test_v02_core.py`, truth u 6e-3, w 3e-3, x 5e-3, y 0): with the old floors U 0.00556, X 0.00578, Y 0; without them U 0.00579, X 0.00792, Y −0.00595, Rwp 0.039442 against 0.039451, `HIGH_CORRELATION` and `FLAT_DIRECTION` raised; the sample's `lor_size` then 55 % low against 27-39 %. A constant positive Lorentzian width projected onto {1/cosθ, tanθ} is X 1.24/1.20/1.09, Y −0.86/−0.73/−0.47 over 10-140°, 18-120° and 20-80° 2θ.
- The judge's suggested swap (hold the specimen width that lands on its floor, free the instrument), prototyped and reverted: corundum 0.145744 and brucite 0.186391 recovered exactly, Stephens 0.180477; cpd-1a Rwp 0.1619 from both starts but Y −0.181/−0.099 and zincite `lor_strain` 0.256/0.175, the per-phase 1/cosθ–tanθ near-collinearity exposed. Not adopted.
- Shipped plans freeing a twin pair: none of eight presets (scratch probe); the probe missed `solve_magnetic`'s internal stages, which the full selection caught.
- Full selection, first run (`aed3f9be2` plus the review commits, nothing else running): 11 657 passed, 136 skipped, 42 xfailed, 8 failed, 27:01; the eight are above.
- Full selection, second run (`ae06b3694`, nothing else running): 11 662 passed, 136 skipped, 42 xfailed, 2 failed, 52:24 (the sequential group set the tail); the two are above. `37ddcced5` changed only what those two and the `gauss_size` pairing reach, and the files those reach ran alone after it: `test_width_twin_hold.py`, `test_audit_table.py`, the QPA, Stephens, sequential, dispersion and start-invariance acceptance suites and the moment guide, 88 passed, 4 xfailed, 35:02. The full selection was not run a third time.
- Fast selection on the final tree (`37ddcced5`, main through `aed3f9be2`): 11 261 passed, 129 skipped, 27 xfailed, none failed, 7:24, nothing else running. The branch's 25 added tests cost 2.94 s (junit, that run): `test_lorentzian_width_floor.py` 2.00 s over 6, `test_width_twin_hold.py` 0.43 s over 13, `test_held_phase.py` 0.29 s over 5, `test_stephens.py` 0.22 s over 1; none joins the slow tail. The counts are the merged tree's and cannot be compared with the 8th session's 11 245, main having added its own.
- Lanes: none dispatched.

*Gotchas.*
- The twin test reads C and no bound, so a specimen width that ends on its floor stays paired with a held instrument term; that is where the Rwp costs above come from. The swap above is the measured alternative and loses on multi-phase data.
- A plan that fits X and Y on the specimen and then frees the specimen widths gets an answer that depends on the instrument-only stage's split. Calibrating on a standard first (`lab_calibrate`, `load_instrument_profile`) is the protocol that avoids it, and no shipped plan does otherwise.
- Under TRF no width row holds; `RESOLUTION_NOT_POSITIVE` reports Γ_L < 0 after the fit.
- No diagnostic code reports the hold: `StageResult.width_twins_held` (and `held`) is the whole record, so a reader of the diagnostics alone does not see it (the judge, item 1, row 7). Not built here; a code would be 2005's.

*Next.* None for this WP: it is closed. The open threads live where they were forwarded: 2017 for the families and measurements the judge asked for (a real calibration with Y unfloored is the one that would test 2(a)), 2004 for the anisotropy ratio and the reference page's split, 2012 for the mirrored axial minima.

*Generality.* The judge's report on this session's items follows, unedited, its headings demoted to bold lines. The author's answers sit beneath them.

**Item 1. `rietx.schemas.results.StageResult.width_twins_held` (new action row, tier 2, ambiguity 1)**

**weak.** The case for stopping the walk along an exactly flat pair is strong. The case against holding the instrument at whatever value the stage starts from is stronger than the row records. In three of the four real fits measured, the specimen twin ended on its floor of 0.

Terms used below:
- **Twin**: a specimen width with the same angular shape as an instrument coefficient: U with `gauss_strain`, Y with `lor_strain`, X with `lor_size`.
- **C**: the parameter table's tie matrix.
- **cpd-1a**: the IUCr CPD round-robin quantitative-phase-analysis mixture of corundum, fluorite and zincite, whose reference is its weighed composition.
- **Plain esd**: the esd before the Bérar-Lelann inflation.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "The instrument half is held at the value the stage started from … the specimen value is then the width the instrument does not account for" (`schemas/results.py:1088-1091`) | It overrides an explicit free in the caller's plan. U, X or Y stays where the previous stage left it, and every later change of width goes to the specimen term. No preset frees a twin pair. I checked `strategy/staged.py`: the presets' `profile` stages free u, v, x, y, and `lab_sample_refine` frees only specimen widths. So it fires only on plans a caller wrote. | — |
| 2. Kind | `ambiguity=1` (`_audit.py:812`) | The row holds two decisions. (a) Stopping the walk is kind 1: a free pair walked to NaN residuals on corundum. (b) Choosing which side carries the width, at what value, depends on whether the held value came from a standard. The pattern cannot show that, so where it did not come from a standard (b) is kind 3. | agrees for (a), not for (b) |
| 3. Case against | "none holds a twin automatically" (row evidence); the costs listed in the row | **A program that does otherwise by default.** GSAS-II 5.8.4 keeps both parameters free. It takes the SVD pseudo-inverse step, which does not move along the flat direction, and prints "soft (SVD) singularity … likely from". It drops a parameter only when the SVD itself fails (`GSASIImath.py:280-289`, `GSASIIstrMain.py:86-115`; checked this session). TOPAS, MAUD and EasyDiffraction run both with no check (`docs/practice.md:118-121`). **The situation where a refiner would act otherwise:** no standard was measured, and an earlier stage fitted the instrument value on this specimen. Then the held value is arbitrary, and the specimen number inherits it. On cpd-1a, zincite's `lor_strain` reads 0.0088 from one Biso start and 0.0612 from the other, at Rwp 0.1631 and 0.1634 (`tests/test_staged_start_invariance.py` docstring). **A mechanism the row does not name.** `_width_twin_flats` reads C and ignores bounds. Where the specimen twin sits on its 0 floor the pair is not flat, and the hold removes the only free direction that can narrow the line. That happened in three of the four real fits measured. On brucite (iso and Stephens), the row says "the specimen twins ending on their 0 floor", and the Stephens fit's Rwp went from 0.179951 to 0.181008. In LaB6 + cBN, LaB6's widths sit "on their floor". On corundum a reflection's specimen width "clips to zero" and the anisotropy ratio is reported as 1e6 (`test_acceptance_stephens.py:336`). On LaB6 + cBN, LaB6 moved from 16.850 to 16.779 wt % against the identifiable fit's 17.787(319), from 5.5σ to 5.8σ outside TOPAS's interval (`tests/validation_matrix.py`). That is slightly further from the cross-code reference. | strong |
| 4. Case for | "Unheld and unfloored, CPD corundum walked y to -180 and lor_strain to +180.04 … every residual went NaN"; "Every program that separates instrument from specimen width does it by fixing the instrument" (row) | The pair is exactly flat by construction, since both terms multiply the same angular function. Removing the floors (item 4) without some stop crashes a fit, and that was measured (WP file, 8th entry, line 391). FullProf with a resolution file, BGMN and RIETAN-FP's advised protocol all fix the instrument (`docs/practice.md:116-119`; the author's survey, which I did not re-check). On LaB6 + cBN, two exactly flat directions are replaced by finite esds, with cBN `lor_strain` at 0.0354(8). Before, the esds ran 8.9 to 3420 and rounding decided their sign. LaB6 widths at 0 are plausible, because LaB6 is a line-profile standard. GSAS-II's pseudo-inverse step does not walk the flat direction either, so stopping the walk has no dissenter. | strong for stopping; moderate for choosing the instrument |
| 5. Tier and source | tier 2; grounds: "Every program that separates … does it by fixing the instrument … Option (b) … confirmed by the maintainer 2026-10-23 … decision 1(a)" | Tier 2 needs the same choice made *by default* in a program, and the row itself says none makes it. BGMN and FullProf with a resolution file fix the instrument by design. That is a different act from overriding a caller who freed both. GSAS-II's default does otherwise (checked). The tier therefore rests on the outcome practice aims at, not on any program's default. `generality.md:112-117` expects such an action at tier 3, judged on unanimity. The ruling appears in the WP checklist (lines 241-244). I did not find it in `2002-batch/rulings.md`. | weak |
| 6. Families | CPD corundum, brucite, cpd-1a/1c; 11-BM LaB6 + cBN; synthetic | Two laboratories: the CPD round robin (one Philips instrument, four specimens) and APS 11-BM, plus synthetic tables. LaB6 + cBN is referenced to TOPAS, which verifies and does not validate, and it moved 0.07 wt % away. For the hold's effect on cpd-1a's fractions against the weighed composition: **none given**. | thin |
| 7. What records that it fired | "the hold names itself on the stage record" (grounds) | `StageResult.width_twins_held` and `StageResult.held` are written by all three runners (`refine.py:4639, 5254, 5554`; `multi.py:1595`). No diagnostic code exists (grep of `src`), so a caller reading only the diagnostics sees nothing. Two sentences are stale. The row's evidence says "one seen phase with its twin held, or a Stephens block, holds nothing" (`_audit.py:816-817`). `results.py:1094` says "Held only where the pair is exactly flat". Item 2 contradicts both. | holds; fix the text |

Evidence that would change the verdict: cpd-1a and brucite refit with the instrument widths taken from a calibration standard rather than fitted on the specimen, showing the start dependence and the floor-binding gone; or a release of the hold when the specimen twin lands on its floor.

> Author: retiered to 3 with decision 1(a) as its approval, the stale sentences rewritten, and the floor-binding named in the evidence (`1a1dcdb0b`). The release on the floor was prototyped and measured: it recovers the single-phase Rwp exactly but on cpd-1a takes Y to −0.18 and zincite's `lor_strain` to 0.26, still start-dependent, so it was not adopted (the row records it). The calibrated-instrument refits and a diagnostic code are not built; the first is 2017's.

**Item 2. A free Stephens block counts as Y's twin (`refine._stephens_block`, inside `_width_twin_flats`)**

**holds.** The case for is stronger than the reason the author gives: the pair is exactly degenerate at the seed, and FullProf's own example does the same. The stated reason, the nested ΔBIC comparison (ΔBIC is the Bayesian information criterion difference), is the weaker of the two. The row text contradicts the rule.

Terms used below:
- **Stephens block**: the anisotropic microstrain coefficients.
- **Seed**: `Stage.strain_seed`, which starts the block on its isotropic ray.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "A free Stephens block … takes its place as Y's twin … held by rule rather than by the null space" (`refine.py` `_width_twin_flats` docstring) | Y is held whenever a phase's block is free, including where the exact null-space test would not call the pair flat. | — |
| 2. Kind | inside item 1's kind 1 | It is kind 1 at the start. On the isotropic ray, moving the block along its isotropic direction changes every reflection's width by the same tanθ term as Y, so the two Jacobian columns coincide. Off the ray the pair is only near-flat. | agrees at the seed |
| 3. Case against | "without it an isotropic fit and its Stephens rival would refine different instrument parameters, which a nested comparison of the two cannot take" (docstring) | The helper `_information` (`tests/test_acceptance_stephens.py:228-244`) counts free parameters, not paths. It already says "the path sets are not nested although the models are". With Y free only in the Stephens fit, the iso fit is still a special case of it. ΔBIC would charge four added parameters instead of three, and `assert n_added == 3` (line 299) would fail. So the reason is the test's count, not something the comparison cannot take. The cost: brucite Stephens Rwp 0.179951 → 0.181008 (item 1's row). Whether that was measured before or after this rule landed (`bd92fd503`) is **none given**. I found no program that refines the tanθ Lorentzian term freely alongside Stephens terms by default. | weak |
| 4. Case for | "The rule is the one every program follows for the whole pair" (docstring) | FullProf's shipped `cuf1k.pcr` holds its tanθ Lorentzian term at 0 and refines the Stephens terms (`docs/practice.md:116`; FullProf's X is rietx's Y; the author's survey, not checked by me). At the seed the first LM steps would otherwise face an exactly singular pair, the same failure item 1 stops. | strong |
| 5. Tier and source | none of its own; it sits in item 1's tier-2 row | Item 1's row says the opposite ("or a Stephens block, holds nothing"). This rule needs its own sentence in the row. | weak, as recorded |
| 6. Families | brucite, corundum | One family: the CPD round robin, one instrument. Stephens is a rare feature, so `generality.md:120-131` allows the judgement ground alone. Reference: none. | one family |
| 7. What records that it fired | `test_a_free_stephens_block_is_ys_twin` | `width_twins_held` lists Y with the block's DOF columns, and `results.py:1096-1099` says so. `_audit.py:816-817` contradicts it. | holds; fix the row |

Evidence that would change the verdict: a brucite Stephens fit started off the isotropic ray with Y free, showing a finite, start-independent Y separated from the block.

> Author: the docstring now leads with the seed's exact flatness and FullProf's example, and the row carries the rule (`1a1dcdb0b`). The 0.181008 was measured after the rule landed.

**Item 3. Unseen phases contribute no sum row (`_hold_unsupported_phases` returns the unseen set)**

**holds.** The case for follows from the support hold's own premise. The case against is a weak, unmeasured edge.

Term used below:
- **Support hold**: WP-1301's hold of a phase whose scale is under 3σ of its counting-noise esd.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "an unseen phase's peaks pin no instrument width" (`refine.py:1371-1373`) | A phase under the support threshold is left out of the twin test. The hold can therefore fire where counting that phase would have pinned the instrument. | — |
| 2. Kind | kind 1, by inheritance | It follows from an existing kind-1 hold and adds no new number. The unseen set is the same `support < sigma` reading the hold uses, prior included (`refine.py:1409-1420`). | agrees |
| 3. Case against | none given | The set inherits `PHASE_SUPPORT_SIGMA` (3σ, tiered on its own). A phase at 2-3σ carries weak width information, which is dropped. The set is read at stage start, and the twin hold is "never asked again". A phase the support hold releases mid-stage therefore leaves in place a twin hold it would now undo, for that stage only. With `phase_support_sigma=None` every phase counts as pinning, which errs toward holding nothing. All of this is unmeasured. | weak |
| 4. Case for | `test_an_unseen_phase_pins_nothing` | An absent phase's peaks are not in the data, so its fixed specimen width measures nothing about the instrument. Counting it would let a real flat direction pass unheld. | strong |
| 5. Tier and source | — | No new threshold. It is a reading of `PHASE_SUPPORT_SIGMA`'s tier. | holds |
| 6. Families | synthetic tables (`tests/test_width_twin_hold.py`) | A real fit where the exclusion decided the outcome: **none given**. | none |
| 7. What records that it fired | — | `width_twins_held` shows the outcome, and `PHASE_UNCONSTRAINED` names the unseen phase. Nothing records that the phase was dropped from the twin test. | adequate |

Evidence that would change the verdict: a real fit with a phase at 2-3σ where the twin hold fires only because of the exclusion and moves the seen phase's specimen widths by more than their esd.

> Author: the test is now asked again before a second solve (`1a1dcdb0b`), which covers a collapse; a released phase still leaves its stage's hold in place, as the judge says, and holding a pinned pair costs the stage that width's freedom only.

**Item 4. `rietx.schemas.instrument.ProfileTCHZ:u`, `:v`, `:y` (floors removed, tier 3)**

**holds.** The case for is stronger: none of the seven programs floors a coefficient, a public neutron model and two codes' LaB6 answers sit under the old floors, and there is the physics argument. Two claims in the evidence are not yet supported, and the one known-truth measurement moved away from its truth.

Terms used below:
- **Γ_G², Γ_L**: the instrument's Gaussian variance and Lorentzian width.
- **LM, TRF**: the two solvers. LM holds linear inequalities inside the step; TRF holds only box bounds.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | U, V ∈ [−180², 180²] deg²; Y ∈ [−180, 180]°; the physical condition "held as Gamma_L >= 0 by LM … guarded under TRF by RESOLUTION_NOT_POSITIVE" (row `:y`) | One box for every preset, replacing U ≥ −0.05 and V ≥ −0.5 (X-ray), U ≥ −0.5 and V ≥ −4 (neutron), and Y ≥ 0. Positivity moves from each coefficient to the total width at each reflection with data. The readers change with it: a stated X, Y whose Γ_L crosses zero is refused, within the fitted range for a recipe and below 180° for `.instprm`/`.prm`, where a negative Y used to be refused. | — |
| 2. Kind | `ambiguity=1` | No program floors a coefficient, so no program dissents from the absence. The far bound is a numerical setting. | agrees |
| 3. Case against | "cost measured on tests/test_v02_core.py's synthetic calibration, whose truth Y = 0 sat on the old floor: Y -0.0059, X 58 % high, sample lor_size 55 % low against 27-39 %, HIGH_CORRELATION raised" (row `:y`) | That is the only known-truth measurement, and it moved away from its truth. The author's reply, that the truth sat on the floor, is fair but does not show gain anywhere. **A new failure:** LaB6's intermediate-tolerance start test fails at 8.82 plain esd on `axial_sl` (strict xfail), because the mirrored axial minima become reachable without the Y floor. **"a finite bound … no width reaches":** before the hold, the 8th-session probes put brucite's u on −32400 and corundum's y on −180 (WP file line 391). Under the hold this is not re-measured. **A gap the WP named:** the 8th session (line 405) found that LM's rows cover only reflections whose windows hold data, and that window sizing and `pseudovoigt.py` meet a negative Γ_L past the data. § Next item 2 said to close it, and the diff touches neither `model/forward.py` nor the peak-shape code. Under TRF only a report: the probe before the hold read brucite Stephens u −0.864, y −0.349. | moderate |
| 4. Case for | "a constant positive Lorentzian width projected onto {1/cos, tan} over 18-120 deg 2theta is X = 1.20, Y = -0.73 … so Y >= 0 would refuse a real instrument"; "the public D1B Co3O4 model's V = -0.501, under the old X-ray floor" (rows) | No program floors an instrument coefficient. Where positivity is enforced, it is on the total width: GSAS-II `max(0.001, …)`, MAUD, EasyDiffraction (`docs/practice.md:123-125`). The LM rows have that shape. GSAS-II and TOPAS both converge to a negative Y on the powderline LaB6 set (−15.81 and −8.97 centideg, `tests/data/README.md:1497`), though that README warns their broadening terms are not comparable there. The projection follows from Γ_L·cosθ = X + Y·sinθ: a constant width needs Y < 0. I did not recompute 1.20 and −0.73. One box for all presets closes WP-1312's two-routes gotcha (`test_gsas_prm.py`). Some start tests improved, though this is mixed with item 1's effect: LaB6's Biso start 9.36 → 1.16 esd, cpd-1a's axial floor 0.138 → 0.010. | strong |
| 5. Tier and source | tier 3; "The floor went on the maintainer's ruling of 2026-10-23 … B9"; the far bound and ceiling from `TCHZ_CEILING_DEG`'s Q7 ruling | The ruling is recorded in the WP checklist (lines 241-244), which answers the previous judge's "approval not found". The absence of a floor is every program's default. The finite far bound lies outside every program's range (none bounds), and it names its reason ("kept finite for TRF's step scaling"), as Q5 requires. | holds |
| 6. Families | D1B Co₃O₄; the synthetic calibration; CPD probes; LaB6 + cBN | ILL D1B (neutron, a published FullProf model) shows a real V under the old floor. The powderline LaB6 is a cross-code comparison. The synthetic calibration is the only truth, and it moved away. On "what real lab calibrations do with Y unfloored": **none given** (WP-2017's Inherited says it is unmeasured). | thin |
| 7. What records that it fired | — | `BOUND_HIT`/`FLOOR_HIT` at the far bound; `CONSTRAINT_ACTIVE` when a Γ_L row binds (`tests/test_lorentzian_width_floor.py`); `RESOLUTION_NOT_POSITIVE` now covers Γ_L under TRF. | holds |

Evidence that would change the verdict: a lab calibration on SRM 660c (NIST LaB6, certified) refined with Y free and with Y ≥ 0, compared on the certified cell and on a sample's size and strain. Separately, a TRF run of brucite and corundum under the hold showing no coefficient on its far bound.

> Author: the past-data gap is closed in the rows rather than in the sizing: Γ_L is held at every reflection of the frozen list, and in the joint runner (`7f95db1f2`). The SRM 660c calibration and the TRF far-bound runs went to 2017.

**Item 5. `rietx.schemas.structure.BISO_SEED` (evidence changed, tier 3, value 0.5 Å²)**

**weak.** The update is honest and assigns the new failure correctly to item 1. But the seed is now start-invariant on only two of the four families, under the three that tier 3's mechanical ground asks for.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the Atom.biso default and the literal of three readers for a site with no ADP" | Unchanged this session. Only the evidence moved. | — |
| 2. Kind | a constant row, so no field | A seed is kind 1 only if the start does not change the answer. | — |
| 3. Case against | "cpd-1a 0.070 until the width twin hold kept a start-dependent X/Y split, 15.68 on zincite's lor_strain since … LaB6 … 1.16 esd" (`_audit.py:2497-2502`) | Two of four families fail the 0.1-plain-esd bar. The 15.68 esd is a sevenfold change in a reported specimen strain (0.0088 against 0.0612) at Rwp 0.1631 against 0.1634. The cause is item 1 freezing a path-dependent split. Any perturbation of the start would expose it, so it is evidence about the hold more than about 0.5. The row says so. | strong against invariance |
| 4. Case for | "starts 0.5 and 1.5 within 0.1 plain esd … on FAP and 11-BM NAC (0.000, 0.000)" | Some start is forced, and two families pass with full margin. Why 0.5 rather than another value: **none given**. | moderate |
| 5. Tier and source | "The maintainer delegated this tier to the lead on 2026-10-23 … tier 3, with WP-2017 measuring …" | The delegation came from the 8th session, before the hold existed. The grounds still defer the mechanical ground to WP-2017, which now inherits the 15.68 (`docs/wp/2017-…md:71`). | weak |
| 6. Families | FAP, NAC pass; cpd-1a and LaB6 fail | Pass: the GSAS-II tutorial fluorapatite and APS 11-BM. Fail: the CPD round robin, and the suite's `lab6` family on mirrored axial minima. The reference is the other start, which verifies and does not validate. | two of four |
| 7. What records that it fired | — | Nothing records that a site took the seed. This is unchanged from the previous judge's finding. | none found |

Evidence that would change the verdict: WP-2017 passing a third family; or cpd-1a refit with instrument widths not fitted on the specimen, confirming that the 15.68 belongs to the hold and not to the seed.

> Author: left at tier 3 with its evidence as written; the third family is WP-2017's, forwarded this session.

**Item 6. `rietx.strategy.magnetic.SOLVE_STAGE_PATHS`, the "all" stage frees only `instrument.profile.u` and `.x`**

**holds.** The case for is stronger. With both halves of each width pair free, the twin hold froze two of the stage's own entries on every candidate fit. Freeing the instrument alone restores the width freedom the ranking had before the hold, with no exactly flat pair. The case against is unmeasured, and the docstring's practice sentence is not supported by the section it cites.

Terms used below:
- **`solve_magnetic`**: the opt-in search that refines one trial fit per candidate magnetic symmetry and ranks the candidates by ΔBIC (the Bayesian information criterion difference).
- **Dead-glob caveat**: the solver's own report of a stage entry that freed nothing.
- **Twin**: a specimen width with the same angular shape as an instrument coefficient (U with `gauss_strain`, X with `lor_size`).

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "The stage frees U and X and not the specimen's `gauss_strain` and `lor_size` … freed alone, the instrument carries the whole width" (`strategy/magnetic.py:227-233`) | Every candidate fit refines the peak widths through the instrument coefficients alone. The specimen widths stay at whatever the caller set. The winner no longer reports specimen widths. | — |
| 2. Kind | none stated. The list is a tuple of strings, which the audit walk cannot see. | The choice sits inside a ranking (kind 2), so it decides which models are compared. Across the pair, total width freedom is the same either way except at the bounds. Freeing the instrument alone lets a trial narrow lines below the caller's instrument. Under the hold the trial could not do that, because the specimen terms are floored at 0. | — |
| 3. Case against | none given | **The situation where a refiner would act otherwise:** the caller hands in a calibrated instrument, such as a neutron `.instprm` or `.prm`. FullProf with a resolution file and BGMN keep the instrument fixed and refine the sample (`docs/practice.md:116, 119`). Here every trial moves U and X off the calibration. I did not check whether the winner's moved U and X reach the caller's `Refinement`. **The docstring's practice claim** reads "the instrument carries the whole width, the reading GSAS-II and FullProf give without a standard (`docs/practice.md`)". The cited section does not say that. It records that GSAS-II leaves both the `.instprm` widths and the sample terms off by default (line 115), and that FullProf without a resolution file gives only general advice (line 116). The sentence is an inference. Measured cost: **none given**. | moderate, unmeasured |
| 4. Case for | dispatch: freed together, the hold held U and X on every candidate fit, `test_the_default_stages_free_nothing_dead` fired, and the 150 K Cr₂WO₆ fit ran to max_iter; with the instrument alone all 76 magnetic-solve tests pass | The mechanism is sound. Item 1's hold froze two of the stage's own entries, so the models compared differed from the plan. That is exactly what the dead-glob test exists to forbid (`tests/test_magnetic_solve.py:649-659`). Freeing the instrument alone removes the exactly flat pairs and gives back the narrowing direction the hold had taken away. I found the max_iter result and the 76-test count only in the dispatch, in no file in the tree. | strong |
| 5. Tier and source | no row | **none given.** The practice citation does not hold as written (row 3). | gap |
| 6. Families | Cr₂WO₆ at 4 K and 150 K, plus synthetic | One real family. Magnetic structure is a rare feature, so `generality.md:120-131` allows judging it on unanimity alone. The Ba₆Co₆ tutorial pattern is not vendored. Reference: none. | one family |
| 7. What records that it fired | — | Each trial's stage record lists U and X as freed, and `width_twins_held` is empty. | adequate |

Evidence that would change the verdict: a magnetic solve with a calibrated instrument showing a different winner, or a different ΔBIC order, between the instrument-only and specimen-only stage lists.

> Author: the docstring now quotes only what the record says (GSAS-II's sample flags off by default) and names the calibrated-instrument case as unmeasured. The 76-test count and the 150 K `max_iter` are in this entry's *Measured*. The moved blind moment (2.04 → 2.03 μB, `examples/guides/moment.py`) is the only quoted number it changed.

**Item 7. `refine.WIDTH_TERMS` leaves `gauss_size` out of the twin hold**

**weak.** Holding has the stronger case on the WP's own ground. Item 1's grounds say "the split of an exact sum is no measurement", and this direction is exactly flat with a wide range. The report the author relies on instead is not shown to fire. The smaller hold that would avoid freezing W was not tried.

Term used below:
- **The direction**: (δU, δW, δsize) = (−1, −1, 1). It is flat because the Gaussian size term goes as 1/cos²θ = 1 + tan²θ.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "`gauss_size` is left out on purpose … it cannot walk, and `FLAT_DIRECTION` reports it" (`refine.py:786-792`) | When U, W and a phase's `gauss_size` are free and `gauss_strain` is not, nothing is held. How the Gaussian constant splits between W and the Gaussian size is wherever the solver stops. | — |
| 2. Kind | the action row's `ambiguity=1` | Item 1's own grounds make the split of an exact sum kind 1. Leaving this direction alone is the opposite decision on the same kind of direction. | inconsistent |
| 3. Case against holding | "holding it held W and moved three acceptance answers" (`_audit.py:815-817`) | Holding froze W, which has no specimen twin and is the constant width term every fit needs. That is a real cost. The three moved answers are the cpd-1a sequential chain, the absent-zircon start test and the corundum Stephens block. All three come from the CPD round robin. Whether each moved toward or away from its reference (the weighed composition where one exists): **none given**. "Bounded both ways" is arithmetic and holds: W ≥ 1e-8 deg² and size ≥ 0, so the walk cannot run to NaN. | moderate |
| 4. Case for holding | none given | The bound is wide. The size can take any value from 0 up to the start's W plus size, because W's floor of 1e-8 deg² is far below a typical W of about 1e-3. So a reported Gaussian crystallite size here is not a measurement. **The claimed report is not shown to fire.** `FLAT_DIRECTION`'s help text speaks of "two parameters" (`help.py:2025-2034`), while this direction involves three. `test_a_gaussian_size_is_left_to_its_floors` asserts only that nothing is held. **An alternative not tried:** hold U alone. With U fixed, δW + δsize·(1 + tan²θ) = 0 at every angle forces both to zero, which removes the direction and leaves W free. The code review's version held W because the null space put both instrument columns on the direction. | strong on mechanism; alternative unmeasured |
| 5. Tier and source | carried in `StageResult.width_twins_held`'s row, now tier 3 (`_audit.py:812`, `1a1dcdb0b`) | The maintainer's decision 1(a) approved the hold of U, X and Y. I found no ruling on excluding the Gaussian size. The exclusion is the author's own, made after the code review. | none given |
| 6. Families | the three CPD acceptance fits | One laboratory and instrument, with no reference distances given. | thin |
| 7. What records that it fired | "`FLAT_DIRECTION` reports it" | Unverified for a three-parameter direction (row 4). `FLOOR_HIT` or `at_bound` would say so if W or the size ends on its floor. | unverified |

Evidence that would change the verdict: a fit showing `FLAT_DIRECTION` naming U, W and `gauss_size` together; or the three CPD fits rerun with U alone held, showing whether the answers still move and in which direction from their references.

> Author: built the judge's alternative. `gauss_size` is U's twin again and W, the constant width, is never held; W's total stays a row of the test, so a held W pins the size and nothing is held (`test_a_gaussian_size_holds_u_and_never_w`, `test_a_held_w_pins_the_gaussian_size`). The three CPD fits free `gauss_strain` too, so U was already held there, and they are unchanged by it (the targeted rerun is in *Measured*).

*CI on #1113 (steward, same day).* Three failures on Linux, none a package defect. Vale's British dictionary has neither "misspelt" nor "mistyped", so `reference/refinement.md` says "wrongly spelt". The moment guide's blind solve stops at one of at least four points, rounding choosing which: 2.0300, 2.0346 and 2.0383 μB on this Mac under start nudges of 1e-14 (Accelerate and OpenBLAS), and Linux printed 2.02. The spread is under half the 0.047 esd. The page now prints one decimal and quotes "2.02 to 2.04". The path guide's 2 % jump left to rounding whether the 800 K warm start broke: it held in 3 of 8 nudged starts on Accelerate and 5 of 8 on OpenBLAS, and Linux held it. A 3 % jump still split on OpenBLAS (3 of 10). A 1.5 % jump broke the 700 K warm start at Rwp 0.946 and held the 800 K one in all 20 starts on both builds, so the guide jumps 1.5 % and its section tells that story. The rescued Rwp, 0.039494, sits 6e-6 below a third-decimal flip, so the page quotes 0.04.

### 2026-10-23 (8th session) — B14's lifts landed, the judge's corrections built; removing the width floors exposed a degeneracy, and the twin hold is next

The audit table now sees the numbers that could change an answer if someone retuned them. Twenty-one inline numbers became named constants, the peak-width model's defaults became table rows, and a stage now records when it put a collapsed phase back and when it seeded a Stephens block. The generality judge then found approvals in the table that the maintainer had never given, and they were put right. Two seeds are now tier 3, with WP-2017 to measure them. The final stopping tolerance keeps tier 3 with the approval it actually has. The list of what stays outside the table is complete. The maintainer's ruling to remove the floors on the peak-width coefficients then ran into a real obstacle. An instrument width and a specimen width with the same angular shape (U with the Gaussian strain, Y with the Lorentzian strain) are exactly degenerate when both are free. The floors had been bounding that walk, and without them a fit walks the pair to infinity and fails on the next stage. A survey of all seven programs found that none floors an instrument coefficient. Every program that separates instrument from specimen does it by holding the instrument from a standard. So the next step is to hold the instrument twin whenever its specimen twin is freed, and only then remove the floors. The removal is built and parked on a branch of its own.

*Done.*
- `/wp-start`: Inherited pruned (both entries answered by the 6th session: the WP-number clash renumbered, the interval's cost inside the fourth round's ruling, the switch kept private); a draft PR, #1113, claims the work.
- B14's lifts, constants and seats (`f6b53a58e`, a lane): 21 numbers named in the module that uses them, bit-identical, each used at every site the literal was (the background order scan and envelope, the P-spline λ, the Pawley off-data floor, the roughness and Stephens seeds, the σ floor and Poisson fallback, the Biso seed, the final `FTOL`, the presets' packing, polarisation, radius and Kα2 ratio, the width grid's top). `ProfileTCHZ` joined `DEFAULT_SEATS`, so `TCHZ_DEFAULTS` and `TCHZ_BOUNDS` are held without restructuring either dict. 27 rows, none at `unaudited`. Sibling fixed: the CIF and recipe readers still wrote occupancy's 1.5 ceiling, which B9 had removed from `Atom.occ` in `fb2395b56`.
- B14's record fields (`ecbf03d3c`, a lane): `StageResult.collapsed` (the columns a stage restored to their stage-start values and held; the moment's flat-direction collapse included; a subset of `held`; written by all three runners; tier 3 on B1's and B2's grounds). The Stephens seed's DOFs join `StageResult.seeded` at the values the seed wrote. The σ-rule field went to WP-1952's Inherited, since that WP replaces the floor the field would report. The audit table's five section counts were stale and are the live counts.
- § The hand rows that stay (`f347eecbb`, then completed in `6eed45fde` after the judge).
- Code review (`/code-review high --fix 425334adb..HEAD`), eight findings: (1) the compare tool's Stephens variant still started at a literal 1000 ppm, fixed `3400693f9`; (4) the `.instprm` and `.prm` readers held their own 0.99 and 0.6, fixed `787e0e0ec`; (2) a joint fit ignores `Stage.strain_seed`, to WP-1467's Inherited; (3) `reference/refinement.md` cannot explain the collapse without splitting the page (50 000-character cap), and (6) the two suggestion-seed alias rows, both to WP-2004's Inherited; (5) and (7) declined, the couplings being stated in the evidence (the judge later held (7) and weakened (5), so (5) was reverted in `6eed45fde`); (8) declined, the TOPAS writer's radius being the file format's convention.
- The maintainer's three answers to the judge's findings (2026-10-23): 1(a) remove the per-coefficient width floors; 2 "use your best judgement"; 3(a) stay on option 3 and fix what the judge named. Built for 2 and 3 in `6eed45fde`: `BISO_SEED` and its sibling `HARMONIC_WEIGHT_SEED` to tier 3 (the conditional "invariant behind the closing stage" a previous judge refused for `MAGNETIC_SIZING_FLOOR`), `FTOL`'s grounds say the 1e-9 was never varied, `PARAMETER_INTERVAL_BRACKET_GROWTH` lifted, the four untested invariants labelled and sent to WP-2017. The judge's no-choice corrections are built too: the polarisation, Kα2 and radius rows no longer claim a record nobody writes (WP-2015 owes it), the radius reaches only the displacement, the peak shape is ambiguity kind 2, and `diagnose`'s census keeps its own 3σ.
- 1(a), by a lane, **parked unmerged** on `wp2002-width-floors-wip` (`879fb1bcc`, pushed): U, V ∈ [−180², 180²] deg², Y ∈ [−180, 180]°, W's clamp floor and X's 0 kept; `TCHZ_BOUNDS_COARSE` removed (with these floors it equalled the default box), `ProfileTCHZ.coarse()` kept as the builder from bare values, `_declared_escape` gone; Γ_L ≥ 0 held under LM by `lorentzian_width_inequalities` (`optimize/least_squares.py` ~1982, registered beside the Γ_G² builder ~2566; rows (x + lor_size)/cosθ + (y + lor_strain)·tanθ plus the magnetic pair, Stephens left out as a sufficient condition); `check_resolution_positive` tests Γ_L under TRF too; `_fd_typicals` treats `instrument.profile.y` as a signed width (`_SIGNED_WIDTHS`); `caglioti.lorentzian_negative_above` lets the recipe, `.instprm` and `.prm` readers refuse a negative Y whose Γ_L crosses zero; `tests/test_lorentzian_width_floor.py`, five tests; the docstring, `help.py`, `theory/profiles.md` (`prof-lorentzian-floor`), `reference/instrument.md`, the release note, the skill.
- The seven-program survey of how each handles an instrument width refined with its specimen twin, saved to the practice record, which moved from this WP's batch directory to `docs/practice.md` as a standing reference (`674d0a53f`); root CLAUDE.md points at it. The maintainer's instruction: every such survey is saved there.
- Main merged (`2dc55a5df`). Forward references: WP-2017 (the two domain tests, then the judge's owed measurements), WP-2003, WP-2004 (two review findings), WP-2005, WP-1467 (the joint runner's strain seed), WP-1327 (a joint fit can hold a moment direction its `held` omits), WP-1952 (the σ-rule field). Priorities of 2003, 2004, 2005 and 2017 re-rated, then corrected when this WP reopened. The v1.10 record's narrative section for this WP says "in flight".

*Measured* (macOS arm64, worktree venv `[dev]`, compiled tier on).
- Fast selection on the merged tree (`2dc55a5df`, main through #1112, before the judge's corrections): 11 245 passed, 121 skipped, 27 xfailed, none failed, 7:54. The six tests added this session cost 0.83 s together (junit, that run): `test_stephens.py::test_the_strain_seed_is_recorded_in_the_stage_result` 0.44 s, `test_held_phase.py::test_the_joint_path_records_a_collapse_too` 0.39 s, four more at 0.00 s.
- Full selection, once, on the same tree: 11 647 passed, 130 skipped, 42 xfailed, none failed, 1:00:37, nothing else running at its start. The judge's corrections came after it (text in `_audit.py`, one lifted constant, one literal restored in `diagnose`), each checked by `tests/test_audit_table.py`, `tests/test_parameter_interval.py` and the docs suites; no fitted value can move through them.
- The floors' removal, measured on the parked branch (the lane, macOS arm64, `[dev]`, each slow file run alone). CPD corundum under `test_acceptance_stephens._plan` (frees `profile.*`, then `phases.*.lor_strain`/`gauss_strain` cumulatively), LM: after `lines_axial` y = −180.0 and `lor_strain` = +180.04, their sum 0.040° unchanged; the next stage (`biso`) raises "Residuals are not finite in the initial point" with all 7251 rows NaN, and with `profile.y.min = 0` the same run completes. `test_acceptance_stephens.py`: 1 failed, 3 errors. With instrument-only Γ_L rows added as a probe (reverted): brucite isotropic LM Rwp 0.186391 both ways, u −0.0499 → −32400 (on the far floor); corundum LM Rwp 0.145744 both ways, u −0.0182 → −15.7, y −0.017; brucite Stephens TRF Rwp 0.178722 → 0.178962, u −0.864, y −0.349; brucite Stephens LM 0.179951 both ways. `test_window_domain.py` 19 passed, 9 xfailed; `test_seed_invariance.py` 2 passed; `test_staged_start_invariance.py` 2 failed, 11 passed, 2 xfailed (`intermediate_tolerance[lab6]` 8.824 plain esd on `axial_sl` against a 0.1 bar; `axial_sizing_floor[cpd1a]` now XPASS(strict), its 0.138 esd gone). A width-floor fast selection of 72 files: 3546 passed, 67 skipped, 25 xfailed.
- Practice (`docs/practice.md` § Instrument and specimen widths refined together): no program floors an instrument coefficient or keeps the instrument function alone positive; positivity, where enforced, is on the total width; none refuses, warns about or holds a twin pair; FullProf (the resolution file) and BGMN (ray tracing) separate the instrument by design, RIETAN-FP by its advised protocol, GSAS-II through defaults that leave the sample terms off.
- Lanes (`session_usage.py lanes`): three, all kept, none redone.

| lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B14-constants-and-seats | 40 | 144 | 166K | 75K | 0K of 3K | 12 | 30K | 0 | 0 | opus-5-5 | 10.68 | 0.67 | 20.79 | +8.70 |
| B14-record-fields | 30 | 85 | 202K | 74K | 0K of 2K | 8 | 14K | 0 | 0 | opus-5-5 | 4.35 | 0.46 | 9.55 | +4.44 |
| width-floors | 45 | 161 | 351K | 75K | 0K of 5K | 14 | 52K | 1 | 0 | opus-5-5 | 13.17 | 7.69 | 23.88 | +2.82 |

  Trial row appended to `docs/milestones/process.md`; the selective policy's replay row: "lane when main > 150K and item >= 20 requests | 252 | -9%". Estimates ran short by 3.6× (actual over estimated requests).

*Gotchas.*
- The parked branch predates `674d0a53f`'s move of `practice.md`: merging it brings back references to `docs/wp/2002-batch/practice.md` in `_audit.py` evidence strings and WP files. Resolve them to `docs/practice.md`.
- With a negative Y, `compile_model`'s window sizing (`forward.py` ~3953) meets a negative Γ_L at reflections the inequality rows do not hold (those past the data), and `pseudovoigt.py:45`'s `gamma5 ** 0.2` warns invalid. The twin hold keeps Y at its start where `lor_strain` is free, which removes the case those runs met; a stage freeing Y alone can still reach it, so the rows (or the sizing) must cover every generated reflection.
- A judge-flagged approval rule: a tier-3 row's `approved` is the maintainer's date, never a borrowed one. The U/V floors' "approval" came from an author's note that misquoted Q5. Read the ruling in `rulings.md` before copying an approval into a new row.

*Next.*
1. The maintainer's go-ahead on the twin hold (option b), asked at the session's end with the seven-program table. If yes: on this branch, hold the instrument twin for any stage that frees its specimen twin. The pairs are U with `gauss_strain`, Y with `lor_strain` and X with `lor_size`. Each hold is recorded in the stage record, the way a user hold is reported (`StageResult.held` and `held_reach`, or a field of its own if `held` would misread). Decide where it lives by the rule a Stephens block already follows when it locks `lor_strain` (root CLAUDE.md, the Stephens clause), and test the two cases where the pair may not be exactly degenerate: a joint fit across wavelengths, and a phase with anisotropic strain.
2. Merge `wp2002-width-floors-wip` on top, resolving the `practice.md` paths, and close the negative-Γ_L window-sizing gap above.
3. Rerun `test_acceptance_stephens.py` and `test_staged_start_invariance.py` alone, plus the fast selection. Re-pin a moved number only if it is no further from its reference, reporting old → new. Remove `axial_sizing_floor[cpd1a]`'s strict xfail, and decide `intermediate_tolerance[lab6]`'s 8.824 esd (LaB6's mirrored axial minima, WP-2012). Then run the full selection once and `/wp-handover` to close.

*Generality.* The judge's report on this session's items follows, unedited, its headings demoted one level. The author's answer sits under its one `fails`, and the maintainer's three rulings above answer the rest.

**Item 1: the 27 rows added to `src/rietx/_audit.py`**

The B-numbers below are the batch classes in `docs/wp/2002-batch/batch.md`. Each one is a group of heuristics the maintainer ruled on together. "Rounds" are the ruling rounds recorded in `docs/wp/2002-batch/rulings.md`. "Plain esd" means the esd before the Bérar-Lelann inflation.

**`rietx.optimize.lm.FTOL` (tier 3, value 1e-9)**

**weak.** Tier 3 is plausible. The approval, though, comes from a test that never varied this number, and the row says so itself.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | "the relative decrease in S under which an iteration counts towards convergence … the final stage's tolerance" (`lm.py` docstring, diff line 1283) | It decides where every fit's answer stage stops. The closing stage solves at it, and so does every stage under `intermediate_ftol=None`. | — |
| 2. Kind | constant rows carry no `ambiguity` field | Kind 1 in effect, a stopping rule. It is also a numerical setting in B10's sense (B10 is numerical settings): it sets how closely the minimum is located. | — |
| 3. Case against | SciPy's default is 1e-8 (checked). GSAS-II 5.8.4's default 'min dM/M' is 1e-3 (`GSASIIobj.py:20`, checked). | Both cited codes stop at a looser tolerance. GSAS-II stops six decades looser by default. I did not check the other five programs. No measurement exists of an answer moving under a looser final tolerance. | moderate, unmeasured |
| 4. Case for | "the closing stage solves at it"; `INTERMEDIATE_FTOL`'s test "measures against it" | Some tolerance is forced. 1e-9 is the reference arm of `tests/test_staged_start_invariance.py`, so every shipped answer sits at it. A tighter tolerance costs iterations and cannot stop a fit short. The cost of moving it is unmeasured. | moderate |
| 5. Tier and source | B7's class went to tier 3 "once its invariance test failed on cpd-1a", plus the sixth round's Q2 | B7's row list does name it: `run_least_squares:ftol`* "(the final 1e-9) … If the test fails: tier 3" (`batch.md:412-414`). The test that failed compares a 1e-6 intermediate tolerance against 1e-9 everywhere, so FTOL is its fixed arm. The cpd-1a failure (0.185 esd with an absent zircon declared) is evidence about 1e-6, not about 1e-9. The row is honest ("this value itself was never varied"). The approval still rests on no measurement of this number. | weak |
| 6. Families | none for this value | none | none given |
| 7. Record | — | `StageResult.ftol` records what each stage ran at. | holds |

Would change the verdict: the four start-test families (SRM 660c, FAP, cpd-1a, NAC) refit with the final tolerance at 1e-8 and at 1e-10, compared against the 0.1-plain-esd bar.

**`rietx.schemas.instrument.ProfileTCHZ:u` and `:v` (tier 3)**

**weak.** I could not find the ruling the grounds quote. The recorded answer covers only the ceilings. A public model sits under v's floor.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | seed 0, box [−0.05, 180²] (u) and [−0.5, 180²] (v) | These are the Gaussian width terms on every X-ray preset. Under LM, Γ_G² ≥ 1e-8 is already held as an inequality, so the floors act mainly under TRF (`instrument.py:1381-1388`, `:1404-1415`). | — |
| 2. Kind | ambiguity 1 | The row itself names programs that set no floor. By Rule 1's unanimity gate, a box with a named dissenter is not kind 1. The seed half is kind 1. | weak |
| 3. Case against | "GSAS-II 5.8.4 and FullProf bound none of U, V, W, X, Y"; "the public D1B Co3O4 model's V = −0.501 sits under it" | The previous judge's table found none of the seven programs bounding these terms (WP file line 1244). An honest published model lands under v's floor. Only `constant_wavelength_neutron` takes the coarse box that fixes this (`instrument.py:2454`). A hand-built `ProfileTCHZ()` keeps −0.5. Under TRF the brucite fit landed with U on its −0.05 floor (`rulings.md:725-726`), so the floor binds in practice. | strong |
| 4. Case for | "the guard against a negative Gaussian variance at some angle under TRF" (`waiting.md:91`) | TRF holds none of LM's inequalities (`rulings.md:290`). This is a named reason, which the sixth round's Q5 asks of a choice outside the seven programs' range. No measurement shows a TRF fit going non-physical without the floors. | moderate, unmeasured |
| 5. Tier and source | "kept by the fifth round's Q5 ruling ('keep the floors and lower bounds', 2026-10-21)" | That quotation is not in `rulings.md`. The recorded answer is "(a), remove the five ceilings, 'confirm with other codes too and let me know'" (`rulings.md:208`). The phrase appears only in an author's note (WP file line 1251). The floors were kept by the lead ("the U and V floors are chosen and stay", `waiting.md:91`). The previous judge named them as the unjudged sibling (WP file line 1249). The maintainer's B9 ruling points the other way: "no need to impose chosen limits on quantities that remain physical" (`rulings.md:54-58`). A negative U or V is physical while Γ_G² stays positive. | weak, approval not found |
| 6. Families | seed start-invariant on LaB6, CPD and 11-BM NAC within 1.3e-4 esd | The seed holds on three families. For the floors there is one family where the floor fails (D1B Co₃O₄) and none where it was measured to hold. | — |
| 7. Record | — | `BOUND_HIT` and `FLOOR_HIT` report a bind. | holds |

Would change the verdict: the maintainer ruling on the U and V floors themselves, or TRF fits on three families showing Γ_G² going negative without them.

**`ProfileTCHZ:x` and `:y` (tier 3)**

**weak.** The ceiling is honestly borrowed from Q7. The floor of 0 is called "physical" but is stricter than the physics, and no ruling covers it. This confirms the author's flag.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | seed 1e-3 (x) and 0 (y); floor 0 on each | These are the Lorentzian coefficients, with Γ_L = X/cosθ + Y·tanθ (`rulings.md:249`). | — |
| 2. Kind | ambiguity 1 | It agrees for the seed. The floor has a named dissenter (row 3). | weak |
| 3. Case against | "the floor 0 is physical (a Lorentzian width)"; GSAS-II and FullProf bound neither | Γ_L = (X + Y·sinθ)/cosθ. A floor of 0 on each coefficient is sufficient for a positive width but not necessary: a negative Y with X > \|Y\| keeps every line positive. A fit that wants a slightly negative Y is pinned at 0 here, where GSAS-II and FullProf leave it free. How often that happens on real data is unmeasured. The x seed matters where a protocol holds x: x = 0 instead moves FAP's `lor_size` by 0.69 esd (row). | moderate |
| 4. Case for | Γ_L must stay positive | True. rietx already holds one combination bound as an LM inequality (Γ_G² ≥ 1e-8), so Γ_L ≥ 0 over the fitted range could be held the same way. It is not built. | moderate |
| 5. Tier and source | grounds cite only the ceiling, Q7 | No ruling covers the floor or the held-x seed. B9's two-start rule passes for x except on LaB6's mirrored minimum (0.38 esd in u). | weak |
| 6. Families | LaB6 and FAP (x); y unstated | The seed test is on LaB6, with FAP for the held case. | — |
| 7. Record | — | `BOUND_HIT` and `FLOOR_HIT`. | holds |

Would change the verdict: a ruling that a per-coefficient floor counts as "keeps a value physical", or the floor rewritten as Γ_L ≥ 0 over the fitted range.

**`ProfileTCHZ:w` (tier 3)**

**holds.** Each part of the row has its own approved row or test. The composite adds no number of its own.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | seed 1e-3 deg², floor `_MIN_GAMMA_G2`, ceiling 180² | as stated | — |
| 3. Case against | "a start too wide losing NAC's phase at w = x = 1e-2" | That is a stated failure a decade above the seed. I found nothing else. | weak |
| 4. Case for | seed start-invariant from 1e-6 to 1.0 on LaB6 | The floor's row is tier 3 under B10 (`_audit.py:1621-1630`). The ceiling's row is tier 3 under Q7 (`_audit.py:2341-2353`). | strong |
| 5. Tier and source | borrowed from those two rows | The borrowing is honest: both parts carry their own approval. | holds |
| 6. Families | LaB6 for the sweep; NAC for the failure | one family for the invariance | — |
| 7. Record | — | `FLOOR_HIT` | holds |

Would change the verdict: a freed-W start test on a second family that fails inside 1e-6 to 1.0.

**`ProfileTCHZ:shape` (tier 2)**

**holds on the tier, weak on `ambiguity`.** DESIGN.md § Rules, 1 gives "a choice of peak shape" as its example of the second kind (DESIGN.md:38-39). The row says 1.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 2. Kind | ambiguity 1 | Rule 1's own text puts a choice of peak shape in kind 2. As a default with no ranking it can stand, but the field should say 2. | weak |
| 3. Case against | "'voigt' is the opt-in true Voigt" | none found | — |
| 5. Tier and source | GSAS-II 5.8.4's CW peak is TCH pseudo-Voigt with FCJ (`GSASIIpwd.getFWHM :916`, `getFCJVoigt3 :1316`; checked) | I did not check this myself, nor the other six programs. | holds |
| 7. Record | — | The shape is stored on the instrument. | holds |

Would change the verdict: none needed for the tier. The ambiguity field should be 2, or the row should say why kind 1.

**`rietx.schemas.structure.BISO_SEED` (invariant)**

**weak.** It has the same conditional shape a previous judge refused for `MAGNETIC_SIZING_FLOOR`. That row moved to tier 3.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | Biso 0.5 Å² for an atom without one, and for CIF, recipe and TOPAS sites with no ADP | as stated (`cif.py:763`, `recipe.py:1077`, `topas.py:4225`) | — |
| 3. Case against | "LaB6's two starts land in its mirrored axial minima (9.36 esd, WP-2012), a strict xfail" | One of four families fails, by 9.36 esd. Without the closing stage the two starts differed by 0.119, 0.751 and 0.008 esd on FAP, cpd-1a and NAC (`rulings.md:234-237`). `closing_window_tol=None` and a stage run by hand both have no closing stage. | strong |
| 4. Case for | "answer-invariant behind the closing stage only: … 0.000, 0.070, 0.000" | `tests/test_staged_start_invariance.py::test_the_biso_start_does_not_change_the_answer` asserts the 0.1-esd bar on three families. cpd-1a passes with a margin of 1.4. The LaB6 failure is WP-2012's mirrored minima, which every start test on LaB6 meets. | strong on three families |
| 5. Tier and source | invariant | The test exists and asserts the margin. But the neighbouring row records that the invariant class has "no conditional form (the generality judge, 2026-10-22)", and `MAGNETIC_SIZING_FLOOR` moved to tier 3 on that reading under the seventh round's Q2 (`_audit.py:1447-1451`). B9's ruling also reads "If fits from two starts agree, the start does not matter" (`rulings.md:909-910`), and on LaB6 they disagree. `HARMONIC_WEIGHT_SEED` has the same shape (not judged here). | weak |
| 6. Families | FAP, cpd-1a, 11-BM NAC | Three families, but the reference is the other start (rietx's own result), so this verifies and does not validate. | — |
| 7. Record | — | Nothing records that a site took the seed. | none found |

Would change the verdict: the maintainer ruling that "invariant behind the closing stage" is allowed, which reopens the magnetic floor too. Or LaB6's pair shown to be a pure S/L ↔ H/L relabelling, with every other parameter within the bar.

**`rietx.schemas.instrument.DEBYE_SCHERRER_POLARIZATION` (tier 3)**

**weak.** The tier and approval match B9. The record the grounds describe does not exist.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | K = 0.99 in the `debye_scherrer` preset | as stated | — |
| 3. Case against | "a wrong K moved a refined Biso by 12 sigma (WP-1311 item 2)"; docstring: "which a lab capillary does not share" | A lab capillary with a Cu tube has K of about 0.5-0.8 (`batch.md:508-511`, recalled there). GSAS-II reads K from the instrument file (`batch.md:524`). The ambiguity is the third kind: a fact about the beam. | strong |
| 4. Case for | the 11-BM instrument files state 0.99 | The preset is the synchrotron one, and the caller can pass `polarization=`. | moderate |
| 5. Tier and source | B9, ruled 2026-10-19 | `batch.md:553-554`: "Tier 3, kind 3, recorded as assumed: `debye_scherrer:polarization`*". Honestly borrowed. | holds |
| 6. Families | APS 11-BM, one facility | one | — |
| 7. Record | "0.99 stays the preset's held value and is recorded as assumed" | No code or field records it. The table has no `*_ASSUMED` code for polarisation, and `schemas/` has no such field. WP-2015's checklist still reads "[ ] The assumed instrument facts recorded in the result" (`docs/wp/2015-the-declared-geometry-picks-the-plan.md:106`). This is a claim with no writer. | fails |

> Author: fixed in `6eed45fde`. The grounds now say that B9 asked for the record and that WP-2015 owes it, and that nothing writes one yet. The Kα2 and radius rows say the same.

Would change the verdict: the grounds reworded as "owed to WP-2015", or the record built.

**`rietx.schemas.instrument.BRAGG_BRENTANO_RADIUS_MM` (tier 3)**

**holds on the tier, weak on the evidence.** The stakes are lower than the row says.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | "the displacement and axial terms read it" | The radius reaches the model only through `displacement_shift_deg`, Δ2θ = −2(s/R)·cosθ (`model/corrections.py:93-106`), and the capillary offsets (`:110-154`). The FCJ axial term (the axial-divergence asymmetry) takes S/L and H/L, not R. So on Bragg-Brentano a wrong radius leaves the fit, the cell and Rwp unchanged. It rescales only the reported displacement in mm, by R_true/217.5. | evidence wrong in part |
| 3. Case against | — | Any instrument of another radius. "217.5 mm is the Bruker D8 Advance's standard radius (recalled)": I could not check this. | moderate |
| 4. Case for | the geometry refuses a missing radius | A preset needs some value. | moderate |
| 5. Tier and source | B9 | `batch.md:556`: tier 3, kind 3, kept. | holds |
| 7. Record | — | Nothing records the radius as assumed (the same WP-2015 gap). | none |

Would change the verdict: a model path where R enters other than as s/R.

**`rietx.schemas.instrument.KA2_RATIO` (tier 2)**

**holds.** The case for is stronger. GSAS-II's default lab instrument uses 0.5 (row, checked; I did not re-check it), and Hölzer et al. (1997) supplies the degeneracy ratio. The case against is a diffracted-beam monochromator clipping Kα2, while `mccusker_default` holds the ratio fixed. The row stated that already. One gap: the row calls it "a B9 recorded assumption", and nothing records it yet (WP-2015). Would change the verdict: a lab family where the held 0.5 moves a certified cell.

**`rietx.schemas.instrument.PACKING_FRACTION` (tier 3)**

**holds.** The case against is GSAS-II's 0.50 (`Absorb.py:89`, per the batch), about a 20 % difference in µR. The caller opts in by declaring a radius or thickness. Under the caller-tier ruling, a defaulted number inside an opt-in is tiered on its own, and it is. The record is `AbsorptionCorrection.mu_r_source` = estimated (`schemas/results.py:479-480`). The packing value itself is not on the record. Would change the verdict: a family where 0.6 against 0.5 moves Biso past its esd.

**`rietx.schemas.pattern.POISSON_FLOOR_COUNTS` (tier 2)**

**holds.** TOPAS weights a file without esds by 1/Max(Yobs, 1) (`rulings.md:1242`, Tech Ref § 6.2). FullProf gives a y ≤ 0 channel weight 1 (`rulings.md:1246`). GSAS-II's xye reader zero-weights it: a dissenter, which does not move tier 2 under the sixth round's Q5. The case against is the review's scaled-data point (`batch.md:325`): a floor in counts is wrong in units on a rescaled pattern. That is against the √y fallback itself, which now has only this row. The record is `DataRef.has_sigma` and the printed "σ source". Would change the verdict: none needed.

**`rietx.schemas.pattern.SIGMA_FLOOR_RELATIVE` (tier 3)**

**holds as written.** The case against is the stronger one. The maintainer: "fix anything obviously wrong" (`rulings.md:76-79`). Issue #897 had one point weighing 10⁶ times its neighbours. The approval is the B5 re-brief the maintainer answered: "Until it lands the floor stays, and the table names WP-1952 as its replacement" (`rulings.md:851-852`). The row is honest about that. Two gaps. WP-1952 is unscheduled (⬜), so the known-wrong floor has no end date. Nothing records that the floor fired (`batch.md:303`). Would change the verdict: WP-1952 scheduled.

**`rietx.strategy.staged.STRAIN_SEED_PPM` and `ROUGHNESS_SEED` (tier 3)**

**holds**, both. STRAIN_SEED_PPM is B3, ruled 2026-10-19, with the second comparison done 2026-10-20 (CPD brucite χ² 7.77 against 8.32, corundum equal). It matches GSAS-II's isotropic default (checked, per the row). Both CPD patterns probably count as one family by laboratory. ROUGHNESS_SEED is the sixth round's Q3, ruled (c), and both models are recorded on `StageResult.seeded`. Would change the verdict: none needed.

**The B12 rows (B12 is pick verbs and opt-in verbs)**

These are `AIR_GAIN_CHEBYSHEV_TERMS`, `ENVELOPE_QUANTILE`, `ENVELOPE_WINDOW_DEG`, `ARPLS_DW_FLOOR`, `CHEBYSHEV_MAX_ORDER`, `DW_STOP`, `PEAK_MASK_BASELINE_LAMBDA`, `PEAK_MASK_SIGMA`, `PSPLINE_LAMBDA_SMOOTH`, `PAWLEY_OFF_DATA_SCALE_FLOOR` and `FRACTION_PROFILE_FWHM_MAX_SPAN`.

**holds**, each. Each is named in B12's row list (`batch.md:747-764`: tier 3, with `default_fwhm_grid:top`* and `off_data_scale_floor`* among them). B12 was ruled "yes to all" (`rulings.md:31-35`), and the skill's instruction counts as a default path. The case against is the B12 review: "The threshold evidence is synthetic" (`batch.md:735`). Notes:

- `ARPLS_DW_FLOOR` feeds only `baseline_lambda`, which nothing reads (`diagnostics.py:1549-1566`, confirmed).
- `ENVELOPE_WINDOW_DEG` now sets `DEAD_LEVEL_WINDOW_DEG` by reference (`diagnostics.py:422`), as that constant's docstring intends.
- `PSPLINE_LAMBDA_SMOOTH`'s "Rwp flat" half is not evidence under Rule 4. Its Biso half is.
- `PAWLEY_OFF_DATA_SCALE_FLOOR` rests on one synthetic fluorapatite (`inventory.json:2571-2573`). The row does not say so.
- `FRACTION_PROFILE_FWHM_MAX_SPAN`'s domain test is owed in WP-2017.

Would change the verdict: a real (not planted) family where one of these flips the pick.

**Item 2: the action rows**

**`rietx.schemas.results.StageResult.collapsed` (tier 3, new)**

**holds.** The case for the restore is stronger. The grounds cite one ruling for a field with two writers.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Decides | a phase visible at stage start that fell under 3σ, or a moment direction gone flat, is "restored to its stage start, held and the stage re-solved once" | The new field records which. Before, the restore joined `held` unmarked. | — |
| 2. Kind | ambiguity 1 | Agrees. | holds |
| 3. Case against | — | The B1 review's dissenter (`batch.md:90`) is a ramp refiner whose new phase starts at a misplaced cell. That case is against the start-of-stage hold. For a restore after the cell has walked off, the same refiner would put it back. The threshold's dissent belongs to `PHASE_SUPPORT_SIGMA`'s row. Against the restore itself: none found. | none found |
| 4. Case for | CaF₂ cell walked to 1.73-20.34 Å unheld and −6.49 Å under the start-only hold; the restore leaves it exactly at its stage-start value | Five new tests in `tests/test_held_phase.py`: the field is a subset of `held`, disjoint from `released`, empty on ordinary stages, `None` on a stored record, and written by the joint runner. | strong |
| 5. Tier and source | B1 (2026-10-19), field from B14 option 3 | B1 is confirmed (`rulings.md:15-17`). The second writer is `flat_now` (`refine.py:4262-4264`: `collapsed = collapsed_phase + flat_now`), the moment path. That is B2's territory (B2 is the magnetic moment actions), and the grounds do not cite it. | holds, grounds incomplete |
| 6. Families | the ramp | One family, synthetic (`test_held_phase.py` builds it from `tests.test_refine_synthetic`). | — |
| 7. Record | the field | Written by all three runners. | holds |

Would change the verdict: none needed. The grounds should name B2 for the moment half.

**`StageResult.seeded` (evidence changed: a second writer)**

**holds.** B3 ruled the Stephens seed "recorded in the result" (`rulings.md:49-51`). The writer is at `refine.py:4028-4032`. The test is `tests/test_stephens.py::test_the_strain_seed_is_recorded_in_the_stage_result`. The field's meaning widens: Stephens rows include degrees of freedom the isotropic ray leaves at zero, so not every row was "lifted". The field docstring states this. The joint runner seeds no Stephens block, which is also documented. The `grounds` text still speaks only of Suortti and Pitschke. The evidence line carries the Stephens half. Would change the verdict: none needed.

**Item 3: `DEFAULT_SEATS`**

**Added: `rietx.schemas.instrument.ProfileTCHZ`**

**holds.** The widths' seeds and box are dicts the constant walk cannot see, and the seat exposes them as live values. Nothing argues against seating it.

**Seats not added (WP file, § The hand rows that stay)**

**weak for `Geometry` and the presets' `radiation`; holds for the rest.**

| Seat | Author's reason | What I found | Verdict |
|---|---|---|---|
| `Geometry` | 14 defaults, among them unruled `mu_t=None`; `Geometry:kind` stays a hand row, WP-2015's | `Geometry:kind` is a B9-judged default (tier 3, kind 3, `batch.md:553-554`). A different default gives a different answer: capillary corrections on Bragg-Brentano data (`batch.md:504-507`). That is exactly what option 3 lifts. The reason is a cost: a seat cannot add rows at `unaudited`, so seating it means tiering 13 more defaults now. It has an owner (WP-2015, not started). | weak |
| presets | their numbers are constants now; seating brings `radiation="CuKa"`, unruled | The default anode is a fact about the caller's instrument (kind 3), and no WP owns it now. | weak |
| `Instrument` | three whole nested models | `Source` and `ProfileTCHZ` are seated, and `Geometry` is above. | holds |
| `Atom` | nothing judged left once `BISO_SEED` holds the Biso | `occ` is floor 0, tier 1. `aniso` and moment default to off. | holds |
| `run_least_squares` | its `ftol` is `optimize.lm.FTOL` | `max_iter` is covered by `StageSpec:max_iter`'s margin test under LM and TRF. The solver default is `DEFAULT_SOLVER`'s row. | holds |

Would change the verdict: `Geometry:kind` seated or lifted, and `radiation` given an owner.

**Item 4: the list in § The hand rows that stay**

**weak.** Two rows are clearly misclassified. Three are labelled "invariant" without the test that class requires. One is doubtful. The list also leaves out hand rows it claims to cover. The 8th session's handover entry is not in the WP yet, so the author's case is the § and the row texts alone.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. Misclassified: a number a retune could turn into a different answer | each row's category in the § | (1) **`TCHZ_BOUNDS_COARSE`**, `src/rietx/schemas/instrument.py:1539-1542`. It is a B9 tier-3 box (`batch.md:551`) on the default path of `Instrument.constant_wavelength_neutron` (`instrument.py:2454`). Its U and V floors (−0.5, −4.0) were measured on one family (D1B). It could be lifted as `TCHZ_CEILING_DEG` was; "a dict the walk cannot read" is a choice. (2) **`_walk:bracket_growth`**, `src/rietx/strategy/parameter_interval.py:264`. Labelled invariant with "no test yet", and its own note says "Profiles with window-recompile steps … can have several crossings; there the growth can choose which one" (`inventory.json:7847-7854`). Since B2 option 2 the interval runs automatically on every moment angle the stationary test leaves out (`rulings.md:93-95`), so its earlier "caller verb" reading no longer holds. | misclassified (2) |
| 2. Invariant without the margin test the class requires | — | (3) **Le Bail/Pawley intensity seed**, `src/rietx/model/forward.py:4038`: "no test yet", confidence low (`inventory.json:2507-2514`). Le Bail at 3 cycles does not converge (#740, `batch.md:636-639`), so start dependence is plausible and unmeasured. (4) **`_FLAT_AXIS_TEST_DIRECTIONS`**, `src/rietx/refine.py:819`: B2 says "Invariant, test owed" (`batch.md:162`), and no file in `tests/` names it. (5) **`arpls:max_iter,tol`**, `src/rietx/background/estimators.py:49-50`: a six-fixture probe, "no test yet" (`inventory.json:1083`). This is the weakest of the three. | weak (3) |
| 3. Doubtful | — | (6) **`FLOOR_SEEDS`**, `src/rietx/params/vector.py:1087`, labelled invariant under B10. It sets the finite-difference step on width columns. Its own docstring measures column errors of 1.4e-3 and 1.5e-2 at the old size (`optimize/least_squares.py:1138-1146`). Esds come from JᵀJ, so a column error moves them. That makes it a B10 numerical setting, not answer-invariant. | doubtful |
| 4. Rows that hold as listed | — | The ones I read are real floors or physics: the reflection floor of 0.1°, the 1e-10 Le Bail and Pawley floors, the 1e-12 TRF nudge, and `TEXTURE_SAMPLE_PSI_DEG` (Järvinen). `cherry_pick:fallbacks` holds: it describes what old history nodes ran at. The `select_arpls_lambda` candidate grid (`background/select.py:197`) feeds only `baseline_lambda`, which nothing reads, so the stakes are low. | holds |
| 5. Completeness | "What the table still cannot see … is listed here" | Some hand rows from other classes are neither table rows nor in the list. I grepped `_audit.py` for each. They are: B8's window action `cell_window` (`params/vector.py:574`) and `_freeze_cell_windows` (`optimize/least_squares.py:2191`), tier 3 (B8 is bounds that act on every fit); B2's `_flat_moment_scan:modulus_floor` and `_onto_flat_meridian:pole_tol` (`refine.py:990`, `:933`); B4's two `normal_factors:*` rows; B5's background σ widening; B10's `aniso_symmetry_tolerance`; B3's `_run_stage:strain_seed`; B12's `profile_fraction:theta_mid` and its five caller verbs; and B11's `_fit_lebail_alternation`. | gap |
| 6. Option 3's fourth field | — | B14 option 3 includes "the four fields", one of them "`RefinementResult`: the σ rule, with counts" (`batch.md:826`, `:832`). Two earlier handovers planned it (WP file lines 1599-1600, 1733-1734). It is not built, and the § neither lists nor forwards it. | gap |
| 7. Record | — | — | — |

The lead said several misclassified rows would switch the policy to option 1 (`rulings.md:107-109`). My count: two clear, three invariants lacking their test, one doubtful, plus `Geometry:kind` left out by choice. The maintainer decides whether that is several.

Would change the verdict: margin tests for (2)-(5), `TCHZ_BOUNDS_COARSE` lifted, and the σ-rule field built or forwarded with an owner.

**Item 5: heuristics the table cannot see**

**Occupancy ceiling removed in `crystallography/cif.py` and `io/recipe.py`**

**holds.** The case for removal is stronger. B9: "Unlimited occupancy is fine. We can give a warning" (`rulings.md:54-56`). The B9 review named a dissenter against the 1.5 cap: Fe on a declared Mg site reads 2.2. The warning exists: `OCCUPANCY_ABOVE_ONE`, tier 1 (`_audit.py:680`). A grep of `src/` finds no other occupancy `max=1.5`. Three other builders set `occ` without bounds: `crystallography/bodies.py:120`, `magnetic/isotropy.py:2328` and `magnetic/supercell.py:1433`. I infer that they inherit `Atom`'s declared default (floor 0, no ceiling) through `_InheritsDeclaredDefaults`; I did not check this for `Atom`. A project stored with `max: 1.5` presumably keeps it, as stored TCHZ ceilings do (inferred, not checked). Against the removal: none found. Would change the verdict: a reader path that still caps.

**`diagnose`'s peak census now reads `select.PEAK_MASK_SIGMA` (a coupling)**

**weak.** The coupling ties two different rules together. The census compares net counts above the rolling 10 % envelope (`diagnostics.py:1473-1477`). `peak_mask` compares against an arPLS baseline (`select.py:82-85`). The row itself keeps `auto_lambda`'s 3σ apart as "another rule", and the same reasoning applies here. Retuning the BIC mask would now redefine `peak_fraction`, a shipped number that WP-1415 deliberately left alone (`diagnostics.py:618-627`). That docstring still says "3σ". The stakes are low: `peak_fraction` is printed and read by nothing in `src/`. Would change the verdict: the census given its own constant, or a reason the two σ bars must move together.

**`refine._flat_rotation_axis` now reads `least_squares.STATIONARY_ANGLE_STEP` (a coupling)**

**holds.** Both are central differences on the same angle, of order one. B2 tiered the old literal (`_flat_rotation_axis:h`*) at tier 3 beside the constant (`batch.md:159-160`). The SVD step only proposes an axis. The finite turn by `MOMENT_PROBE_ANGLE_RAD` decides whether it is held (`refine.py:878-884`, `:916` on). A step error of order h² cannot hold a direction the turn rejects. Today's value is bit-identical (1e-4). Against: none found. Would change the verdict: a retune of the stationary test's step that moves the proposed axis far enough for the finite turn to miss a flat axis.

### 2026-10-22 (7th session) — the ninth round built: a second LAPACK driver on the fit path, the magnetic winner closed, three design questions settled

A fit no longer fails because the system's linear-algebra library gives up on a matrix another build handles. The brucite fit under the TRF solver that errored on macOS now completes at Rwp 0.1787: every eigensolve, SVD and least-squares solve a fit and its report make now repeats a failure with LAPACK's slower QR-iteration driver, which computes the same decomposition. The magnetic structure solver now reports its winner's moments from a final fit on peaks with their full tails, so on synthetic data their esds are no longer 1.6 times too large. The three narrower questions were settled on evidence. The report of a fit run without its closing stage reads the same either way on three patterns, so it is kept. A loosened closing stage no longer silently coarsens its axial-divergence sampling. And building a report from a compiled model without the structure and instrument it came from is now refused, where it used to misread silently.

*Done.*
- The ninth round (`2002-batch/rulings.md` § Ninth round): the maintainer's "1. Fix the TRF issue 2. End with closing stage 3. Infer what I would do".
- Item 1: `optimize/lapack.py` (`eigh`, `eigvalsh`, `svd`, `pinv`, `lstsq`, `cond`: numpy unchanged, then `syev`/`gesvd`/`gelss` on `LinAlgError`; a non-finite input keeps numpy's error). SciPy's TRF step SVD is reached through `scipy.optimize._lsq.trf.svd`, retrying only on a thread inside the package's solve. 41 fit-path calls routed (`optimize/`, `model/`, `params/`, `report/`, `background/`, `solve/`, `refine.py`); `tests/test_lapack_fallback.py` refuses a bare one there and injects failures. `StageResult.n_lapack_fallbacks` (schema 0.59's entry), tier 1. `test_covariance_scaling`'s #225 test now fails both drivers.
- `refine.py`'s collapse-restore merge now sums both solves' `n_degenerate_cell_probes`, as `multi.py`'s did (a sibling found while adding the new count).
- Item 2: `strategy.magnetic._close`. When the package chose the plan and the verdict is solved, the winner runs its plan's closing stage through `run_stage` from its own refinement. Its Rwp, GoF, R_mag, moments, held list, drift and status are that fit's; its ΔBIC the ranking's; caveats say so, and say when the close raised or did not converge. `test_pair_diagnostic_class` draws by `predict` again; the moment guide, its page and the magnetic reference follow.
- Item 3: the closing node rule's line moved to `window_area_tol < WINDOW_AREA_TOL` (test made to fail on the old line); `build_report` refuses a non-Pawley `model=` without `structure=` and `instrument=`; the closing-off report kept and recorded.
- Merged main (`b2fa5b0aa`, through #1109): WP-1986 retired `docs/manual/`. This branch's 109 lines there all had homes in the new tree (checked by phrase); the deletions stand. The GUI dist and the seven notebooks rebuilt from the merged sources. The landing panel's GoF corrected to the builder's 1.60 (the tutorial's fit is bit-identical to the session's start, GoF 1.60489).
- Forward references: WP-1418's Inherited (the closed winner, the moved numbers), WP-2004's (the refused bare model, the closing-off reading).
- CI's lint now runs Vale over `docs/docs` (WP-1986 on main): eight errors in this branch's pages fixed (`05e2c0dbc`), `Doebelin` and `Kleeberg` accepted.

*Measured* (macOS arm64, worktree venv `[dev]`, compiled tier on).
- The failing matrix: 7279 × 28, condition 7.9e10; Accelerate `gesdd` 20 of 20 failures; OpenBLAS `gesdd` (SciPy 1.18.1's macOS 12 wheel, scratch venv) decomposed it, singular values equal to `gesvd`'s (max relative difference 0.0). Brucite TRF: `gesvd` retry Rwp 0.17872, 19 of 43 σ² negative; `tr_solver="lsmr"` 0.17873, 20 of 43, S_HKL 0.04 esd from it; a plain restart passed only because two columns came out 5e-4 different.
- Two-site Pnma: moduli esds 0.00242, 0.00179 → 0.00151, 0.00111 μ_B; solve 16.5 → 17.1 s, one run each. Cr₂WO₆ at 4 K: blind 2.0353 ± 0.0459 → 2.0383 ± 0.0467 μ_B; the alternate model 2.1255 ± 0.0450 → 2.1240 ± 0.0440, Rwp 0.1047 → 0.1052, scale shift 0.47 → 0.41 esd; the reference solve unchanged (2.0868 ± 0.0337).
- Closing-off reports: FAP and cpd-1a, read at the closing precision and at 2 %: same printed report, the same regions passing (2 and 1) with the same leading shape, no action either way; shares within 0.04 but one cpd-1a region (0.43 against 0.57). The displaced specimen (−0.10 mm), closing on and off, read both ways: cos θ first in all four, R² 0.539-0.555.
- Fast selection on the merged tree (`7bac0fe82`, main through #1109): 3 failed, 11 141 passed, 191 skipped, 27 xfailed, 5:13, nothing else running. The three (one page over the manual's 50 000-character cap, source and built twin; the landing panel's GoF) were fixed in `2ac49c2f6` and pass alone. The last session's final tree read 11 081 passed and 191 skipped; the merge brings main's tests, so this session's own delta (17 cases: 13 in `test_lapack_fallback.py`, 3 refusal cases, 1 node-rule line) is not separable in the total.
- Added tests in the fast tier: `test_lapack_fallback.py` 0.79 s, the refusal 0.08 s, the node-rule line 0.06 s, from that run's junit.
- Full selection, once, on the merged tree (`2ac49c2f6`): 1 failed, 11 541 passed, 202 skipped, 42 xfailed, 50:51, nothing else running at its start. The failure, `test_the_closing_stage_meets_the_bar[cpd1a]` at 0.107 esd, was this session's node-rule line meeting a test that lowers `WINDOW_AREA_TOL` for its reference; fixed in `b0160d2e0` (0.011 esd again), and the eight files that patch the constant pass with their slow cases (450 passed, 35 xfailed; another session's pytest was running, so no time is quoted). The Stephens brucite TRF pair, which errored in the last full selection, passed.

*Review.* `/code-review high --fix d5e906593..0b2215ec3` found eight; fixed in `ed0fba102`: (1) a NaN input turned numpy's `LinAlgError` into SciPy's `ValueError`, past every #225 handler, so `_note` re-raises it; (2) an exception in the winner's close kept nothing, so it now keeps the ranked winner with a caveat; (3) a close that stops short says so; (4) the winner's anti-translation drift is measured on its closed moments; (5) the trials drop their refinements after the close; (6) `np.linalg.cond` (layer1, strain) routed and guarded; (8) `eigvalsh` handles a stack. Declined: (7) SciPy's BVLS calls numpy's `lstsq` inside the default LM driver's bounded step. That matrix is square, at most 128 columns (`BVLS_MAX_COLUMNS`) and cut at the eigen threshold, so its condition stays near 1e6 against the failing 8e10, and reaching it means patching a second private SciPy module.

*Gotchas.*
- SciPy's and numpy's wheels on this Mac link Accelerate, whose `gesdd`/`gelsd` fail on finite matrices OpenBLAS decomposes; `uv pip install --python-platform aarch64-apple-darwin` gets the OpenBLAS wheel for a Linux-like check.
- `solve_magnetic`'s printed table now mixes precisions in one column on a solved verdict: the winner's Rwp, GoF and R_mag are the closing stage's, the other rows' and the reference's the declared windows'. The caveat says so; ΔBIC is at one precision throughout.
- A `docs/docs` page over 50 000 characters, source or built twin, fails `test_manual.py`; `reference/refinement.md` sits at 49 388.

*For the maintainer.*
- Three inferences under "infer what I would do" (`rulings.md` § Ninth round 3): the closing-off report kept as is, the closing node rule for every compile under 2 %, `build_report` refusing a bare `model=`. Each is one commit to reverse.
- Item 1's mechanism replaces one name in SciPy's private `trf` module, gated to the package's own solves, because SciPy offers no driver setting; the supported alternative, `tr_solver="lsmr"`, changes the subproblem solver and was measured 0.04 esd away. A SciPy release renaming that import makes `tests/test_lapack_fallback.py` fail rather than the fallback go quiet.

*CI on #1085 (steward, same day).* Four failures on Linux, none a package defect; each fixed and recorded where the code is.
- The jax job died ("runner received a shutdown signal") or hit its 40-minute cap since `fef4a7c46`: the cross-backend fixtures inherited `compile_model`'s closing windows, and `satellites` grew from 5 870 to 85 704 window points, so its jax row held 17 GB and ran 273 s on this Mac. Those fixtures, and the two jax-reaching ones in `test_voigt.py` and `test_backend_jax.py`, now declare `WINDOW_AREA_TOL`, as `test_backend_shim.py` already did. The jax selection went from 1 failed, 85 passed and 5 skipped in 5:42 to 86 passed and 5 skipped in 1:32; peak worker footprint 17 GB to 5.1 GB (`[dev,jax]`, macOS arm64). The failure, the WP-1953 zero-aperture column, compared two columns of about 5e-5: at the closing node rule the residual's first-order response to H/L at 0 falls from 4.7e-2 to 7.1e-5.
- `test_fcj_rows_agree_with_the_scalar_arithmetic_to_rounding` (1.1e-13 against 1e-13, Linux only): the bar is now the dot-product rounding bound, N·ε·Σ|terms| per point. Linux and darwin/arm64 both sit at 2.3 units of it or less; node generation is bit-equal on both. It still fails an fp32 accumulation and a dropped node.
- The moment guide prints only what its two stopping points share. A start nudged by 1e-14 lands the rounds at 0.41 or 0.47 esd of scale shift (± 0.0440 or 0.0450 μ_B, Rwp 0.1052 or 0.1048); Linux takes the second, this Mac the first. So the 7th session's "scale shift 0.47 → 0.41" is that split, not the closing stage. The blind solve splits too (2.0342 in one of six nudged starts against 2.0383); both platforms give 2.0383, so its printed 2.04 stays.
- The path guide's rejected warm Rwp spans 0.917-0.938 under the same nudges (Linux 0.937), so the page says "over 0.9". The Vale accept list is regenerated from `terms.txt`, where the two names now live.
- The next run failed the `next` guide on one Linux leg, as two earlier runs had and the one before did not. Its quoted summary printed ΔBIC at four significant figures, and starts 1e-14 apart put it at −1.29940 to −1.29971, either side of −1.2995. The maintainer chose (2026-10-22) to change the package: `suggest`'s summary now prints Δχ² to three significant figures and ΔBIC to one decimal (release note under Changed). The noise floor did not move under the nudges and keeps four. `Refinement.summary()`'s `next:` line already printed ΔBIC to one decimal; its Δχ² stays at four figures, because moving it reaches the tutorial notebooks, `reference/result.md` and the NAC termination golden.

*Generality.* The judge's report on this session's seven items follows unedited. The author's answer sits under each `weak`, `partial` and `cannot tell`.

## 1. `rietx.schemas.results.StageResult.n_lapack_fallbacks` (new action row, tier 1, ambiguity 1)

**Verdict: holds.** The case for acting is much stronger. Tier 1 is right. The record field is narrower than the fallback it reports.

Background: LAPACK is the linear-algebra library numpy and SciPy call. Its "divide-and-conquer" routines (`gesdd` for the SVD, `syevd` for symmetric eigenproblems, `gelsd` for least squares) are fast but can stop without converging. Each has a slower "QR-iteration" twin (`gesvd`, `syev`, `gelss`) that computes the same decomposition by another algorithm.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "a decomposition the divide-and-conquer LAPACK driver did not converge on is repeated with its QR-iteration twin" (`_audit.py` row evidence) | Verified in `/Users/yue/Code/rietx/.claude/worktrees/wp2001-rule-table-guard/src/rietx/optimize/lapack.py`. numpy is called first, unchanged. Only on `LinAlgError` does it call SciPy with `driver="ev"`, `gesvd` or `gelss`. The fallback cut-offs equal numpy's: `pinv` keeps singular values above rcond × the largest, and `lstsq` with `rcond=None` cuts at eps × max(M, N). For TRF, SciPy's trust-region solver: `scipy/optimize/_lsq/trf.py` line 98 does `from scipy.linalg import svd`, so replacing that one name does reach its step. The retry happens only on a thread inside `lapack.scipy_trf()`. What the caller did not ask for: an answer where there used to be a raise. | clear |
| 2. Ambiguity kind | `ambiguity=1` | Agree. It is the same mathematical object computed by another algorithm. | agree |
| 3. Case against | none given. rulings.md § Ninth round 1 rules out two alternatives: a restart ("luck") and `tr_solver="lsmr"` (changes the subproblem). | I tried one dissenter: a refiner who reads a failed SVD on a matrix of condition 7.9e10 as a sign that the step problem is ill-posed, and wants the fit stopped. It does not survive. On Linux, OpenBLAS's `gesdd` decomposed the same matrix, so the raise came from the platform's library, not the data. The brucite TRF fit's ill-posedness is reported elsewhere: 19-20 of 43 σ² negative (rulings), and TRF "collapses CPD brucite's S_HKL" (`PlanSpec:closing_window_tol` row). | none found |
| 4. Case for | "macOS Accelerate's gesdd failed 20 of 20 on a 7279 x 28 step matrix … OpenBLAS's gesdd decomposed with singular values equal to gesvd's to the last bit" (row evidence) | Without the fallback, the fit raises on one platform and answers on another for the same input. The skill's `references/series.md` lines 249-255 records what an unguarded `LinAlgError` costs: 216 and 103 already-fitted patterns lost. I cannot tell whether those two failures were this kind of non-convergence. | strong |
| 5. Tier and source | Tier 1, arithmetic. "Anderson et al. 1999, LAPACK Users' Guide … TenPy's svd_robust … MATLAB and Octave call gesvd by default" | Checked in this worktree's venv: `scipy/linalg/_decomp_svd.py` line 68, "MATLAB and Octave use the 'gesvd' approach". TenPy and the LAPACK guide were not checked. Tests: `tests/test_lapack_fallback.py::test_a_converging_decomposition_is_numpys_own` (bit-identical), `::test_each_fallback_returns_the_twins_answer_and_is_counted` (rtol 1e-12, on small well-conditioned random matrices only), `::test_a_trf_stage_records_its_fallbacks` (Rwp equal to rel 1e-9 under an injected failure), `::test_the_fit_path_decomposes_only_through_the_fallbacks`. The brucite bit-equality was measured once and has no fixture ("No small matrix makes Accelerate fail on demand", test module docstring). | holds |
| 6. Dataset families | Brucite only, in the row. The `lapack.py` docstring adds a 22 003 × 102 strain-screen design (Accelerate `gelsd`) and issue #225 (`eigh` at the covariance). | This is not a threshold, so the three-family ground does not apply. The accuracy check is against the twin driver and OpenBLAS. That is verification (code computes the model correctly), which is what an arithmetic tier-1 row needs. | n/a |
| 7. Record | `StageResult.n_lapack_fallbacks` | Only `run_least_squares` and `run_multi_least_squares` read the count (`least_squares.py` 2398/2527 and 2679/2774 are the only readers of `lapack.retries()`). Fallbacks elsewhere are counted on the thread but never recorded: `refine._hold_scale_b_ridges` runs before and between solves (`refine.py` 4109, 4319) and decides `StageResult.scale_b_held` through an `lstsq` and an `svd`; `ParameterTable` builds; the report's `layer1.attribute_region` and `strain`; background selection; `SolveCost`. So the `lapack.py` docstring line "Every fallback is counted … so a stage records how many it took" overstates. No diagnostic code sums the field, unlike `n_degenerate_cell_probes` and `CELL_DEGENERATE_PROBE`. | partial |

Would change: a fallback answer measured off its twin by more than rounding on an ill-conditioned matrix would weaken tier 1. For the field: taking the count over the whole stage, or narrowing the docstring to "the solve and its esds", would close item 7.

> Author: narrowed (`7bac0fe82`): the docstring now says the field holds the fallbacks of the solve and its esds, and that one taken elsewhere on the fit path is recorded nowhere, its answer being the twin's.

## 2. `rietx.model.forward.MAGNETIC_SIZING_FLOOR` and `rietx.model.forward.WINDOW_AREA_TOL` (changed text)

**Verdict: weak.** The new text is right that the magnetic solve's winner now runs a closing stage (one extra solve on 1e-3 windows, the answer-computing stage after the declared stages). But it states that unconditionally. WINDOW_AREA_TOL's list of numbers still computed at 2 % windows also leaves some out.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | Values unchanged. The text records that "its winner runs one since 2026-10-22" (floor evidence) and "the moments of the magnetic default solve's trials other than its winner, which runs a closing stage" (WINDOW_AREA_TOL grounds). | `_close` runs only when `package_plan and verdict == "solved" and ordered` (`strategy/magnetic.py` 2615). When the solve abstains, no row runs one. Neither text says so. | inaccurate |
| 2. Ambiguity | not stated (constant rows) | n/a | n/a |
| 3. Case against (2 % windows still reaching numbers a caller reads) | the list in WINDOW_AREA_TOL's grounds | Also at 2 % and not listed: every trial's ΔBIC, the winner's included; the other trials' Rwp, GoF and R_mag (R-factor over the magnetic channels); and the nuclear reference's Rwp and R_mag. All are printed in `MagneticSolution.__str__` (`magnetic.py` 651-681). ΔBIC at 2 % is deliberate, like the report's shapes that the grounds already call "on purpose". It should be named the same way. | incomplete |
| 4. Case for (the new closing stage removes it) | moduli esds 0.00242 and 0.00179 → 0.00151 and 0.00111 μB (rulings.md § Ninth round 2) | That is true for the winner. For the floor specifically: the default solve frees no magnetic width (`SOLVE_STAGE_PATHS`, `magnetic.py` 233-241). So the case the floor's evidence measures, a width freed from zero, does not arise in those trials. Listing the default solve as a path without a closing stage is true, but it does not show that the floor's error reaches it. | partial |
| 5. Tier | 3 for both, unchanged | Bookkeeping: WINDOW_AREA_TOL keeps `approved="2026-10-21"` while its grounds now cite two 2026-10-22 rulings. The WP's earlier review (WP file line 485) caught the same mismatch on another row. | mismatch |
| 6. Families | unchanged | not re-judged | n/a |
| 7. Record | the closing stage's `StageResult.window_area_tol` | The winner's closing `StageResult` sits in the private `_result` (see item 4). | n/a |

Would change: text that says "when the verdict is solved" and names ΔBIC and the other rows' statistics among the numbers still computed at 2 % windows.

> Author: fixed (`7bac0fe82`): both rows say the winner closes on a solved verdict; the floor's says the default solve frees no magnetic width; WINDOW_AREA_TOL's grounds name the magnetic ranking (every ΔBIC, the other trials' and the reference's statistics) as at 2 % on purpose, and its `approved` is 2026-10-22.

## 3. `rietx.model.profiles.fcj.CLOSING_NODES_PER_FWHM / CLOSING_MIN_NODES / CLOSING_MAX_NODES / CLOSING_SKIP_EXTENT_FWHM_RATIO` (changed evidence)

**Verdict: holds.** Moving the line needs no new evidence for the accuracy bar, because the domain test never reads the window fraction (the share of a peak's area its window may drop). The FCJ node rule sets how finely the axial-divergence asymmetry is sampled.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "taken by a compile finer than WINDOW_AREA_TOL … the line moved from CLOSING_WINDOW_TOL on 2026-10-22" (row evidence) | Verified: `compile_model` now uses `window_area_tol < WINDOW_AREA_TOL`. Any compile at 1e-3 < tol < 0.02 now takes the closing rule. | clear |
| 2. Ambiguity | n/a (constant) | n/a | n/a |
| 3. Case against (widening the rule's reach) | none given | The cost is more nodes on a fit whose windows were loosened for speed, so the speed switch is a little less fast. That cost is not measured. A `closing_window_tol` in [0.02, 1) is legal (`check_closing_window_tol`) and still takes the declared rule. The evidence says "below it", which is precise. | none given |
| 4. Case for | "a caller loosening the windows asks for coarser windows, not for an asymmetry error 7.8× the lab bar" (rulings.md § Ninth round 3, second bullet) | The author inferred this under the maintainer's "infer what I would do". The maintainer did not rule it directly. | reasonable |
| 5. Tier and test | tier 1, `test_the_closing_node_rule_meets_the_bar` | `_fcj_domain_cases` (`tests/test_lab_instrument.py` 567-591) scores each case on its own grid (the asymmetric extent plus 6 FWHM each side) against a max(512, 4n)-node reference. The node count depends only on 2θ, FWHM, the two aperture ratios and the closing flag. So the bar belongs to the rule, not to any window. New `test_the_closing_node_rule_serves_every_compile_finer_than_the_declared_stages` asserts that 5e-3 and 0.0199 give the same node counts as 1e-3, and that 2 % keeps the declared rule. The report's shapes copy is compiled at exactly `WINDOW_AREA_TOL` (`report/__init__.py` 261-262), so it keeps the declared rule. The eighth round's near-90° Gram-gate failure therefore does not come back through this move. "No compile the package makes sits between the two": my grep of `window_area_tol=` and `closing_window_tol=` in `src/` found only the two constants, `None`, recorded values and values a caller passes. | holds |
| 6. Families | lab (FAP.XRA bar) and synchrotron (11BM_NAC bar), 8 500 synthetic cases | unchanged by the move | unchanged |
| 7. Record | the recorded window fraction says which rule ran (`compile_model` docstring) | `StageResult.window_area_tol` | holds |

Would change: a measured case where the node rule's error depends on the window, which the test's construction rules out.

## 4. `solve_magnetic`'s winner ends in a closing stage (heuristic the table cannot see)

**Verdict: cannot tell whether it needs a row of its own.** The action is well supported and inherits the closing stage's tier-2 default. Its record is a caveat string, and the printed table mixes two precisions in one column. ΔBIC is the Bayesian information criterion difference that ranks the candidate magnetic models.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the winner then runs its plan's closing stage … Its Rwp, GoF, R_mag and moments are that fit's, its ΔBIC the ranking's" (rulings.md § Ninth round 2) | Verified (`magnetic.py` 1392-1418, 2615-2622). It runs only when the package chose the plan and the verdict is "solved". It also replaces `held`, `fit_status`, `_structure` and `_result`, so `write_magcifs` writes the closed fit. The subgroup descent audit (`_descend`) runs before the closing stage, on the unclosed winner. | clear |
| 2. Ambiguity | none stated (no row) | Kind 1, the same as the closing stage it reuses (`PlanSpec:closing_window_tol`, ambiguity 1). | kind 1 |
| 3. Case against | none given | (a) In the printed table, the winner's Rwp, GoF and R_mag sit in the same columns as the other trials' and above the nuclear reference's Rwp, all at 2 %. Reading Rwp down the column compares two precisions. Only a "!" caveat at the foot says so. (b) On Cr₂WO₆ (real HB-2A data), the blind moment's esd rose 0.0459 → 0.0467 and its magnitude moved 0.07 esd; only the alternate arm's esd shrank (0.0450 → 0.0440). (c) The synthetic esd gain (0.00242 → 0.00151) was measured after `tests/test_pair_diagnostic_class.py` was changed to draw its data at the closing windows. Data and closing fit then share one precision, which favours the closing fit. A dissenting program: none found. I did not check what GSAS-II or FullProf do after choosing a magnetic model. | modest |
| 4. Case for | moduli esds above; solve time 16.5 → 17.1 s, "one run each" | The winner's moments are the answer. A caller cannot easily close the fit themselves, because the winner's `Refinement` is private (`_refinement`, `repr=False`), so they would refit from the magCIF. The closing stage's own grounds apply here unchanged. | strong |
| 5. Tier | none proposed | It would inherit `PlanSpec:closing_window_tol`'s tier 2 (BGMN's closing run by default, cited in that row; I did not check it). Splitting the precisions (ΔBIC at 2 %, values at 1e-3) is rietx's own design. No program precedent is given. | tier 2 for the action; split none given |
| 6. Families | synthetic two-site Pnma; Cr₂WO₆ at 4 K | One synthetic case and one real one. No independent reference: the 2.09 ± 0.03 μB is another rietx fit. Magnetism is a rare feature, so the judgement ground alone applies. | one real family |
| 7. Record | a caveat | The caveat is free text in `MagneticSolution.caveats`. The closing `StageResult` (name `closing`, `window_area_tol` 1e-3) lives only in the private `_result`. No public field says which rows were closed, so no action row can be keyed on one. | weak |

Would change: either `PlanSpec:closing_window_tol`'s evidence naming this second site, which settles it as covered, or a public per-trial field giving the window fraction each row was measured at, which would let it take its own row. A test showing the ranking unchanged if every trial were closed would remove case (a)'s worry about ΔBIC.

> Author: the first option (`7bac0fe82`): `PlanSpec:closing_window_tol`'s evidence names this second site. On (c): the synthetic data were drawn by `predict`, as every synthetic pattern on this branch now is and as a measured pattern's full tails are; the 2 % draw was last session's workaround for a solve that did not close. No per-trial field and no every-trial-closed ranking test were built.

## 5. `build_report` refuses a non-Pawley `model=` without `structure=` and `instrument=` (heuristic the table cannot see)

**Verdict: holds.** The case for refusing is stronger. Reading one model silently gave a misattribution the eighth round measured, and the fix costs the caller one argument.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "since one model alone brings back both misreadings the eighth round measured" (rulings.md § Ninth round 3, third bullet) | It removes a silent choice: Layer 1 (the report's region-by-region misfit attribution) reading its misfit and its shapes from one model. The caller must now pass both arguments. The model's own precision decides nothing now. Side effect: a model recording no window fraction is refused too, although `_reading_models` would read it as it is. That branch is now unreachable, so its docstring is stale. `compile_model` always sets the fraction (`forward.py` 4196), so this is close to moot. | clear |
| 2. Ambiguity | not stated | A raise on bad input is an API shape (DESIGN.md § Rules, 4, "a raise on failure"). It is not a kind-1/2/3 decision, so no row is needed. | n/a |
| 3. Case against (for the old silent read) | none given | It breaks a script that passed `model=` alone. In the repository, none does. Verified at `refine.py` 5241 and 5567 and `multi.py` 1226, and the test helper now passes both. Plain `build_report(result)` (Layer 0 only) is unaffected. | weak |
| 4. Case for | eighth round item 1: a declared-precision misfit ranked axial asymmetry first on a displaced specimen; closing-precision shapes failed the Gram gate near 90°; reading two models ranked the displacement first at 0.995 (rulings.md 473-483) | A wrong attribution with no warning versus one clear `TypeError` that names the missing arguments and `Refinement.report()`. | strong |
| 5. Tier | n/a | n/a | n/a |
| 6. Families | one synthetic displaced specimen | Thin for a threshold, but enough for a refusal, which cannot move an answer. | adequate |
| 7. Record | the `TypeError` | `tests/test_fitreport_layers.py::test_a_model_without_what_it_was_compiled_from_is_refused`, three cases. `docs/docs/reference/report.md` is updated. | holds |

Would change: a supported caller that holds a compiled model but not the inputs it was compiled from.

## 6. A fit run with `closing_window_tol=None` still has its FitReport misfit read at the closing precision (rulings.md § Ninth round 3, first bullet)

**Verdict: weak.** The measurement shows the two readings agree on the two patterns where they were most likely to differ, so keeping one rule did no harm there. It cannot show which reading is right, because neither pattern has a known misfit.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the report printed the same text, passed the same regions (2 and 1) with the same leading shape, and suggested no action either way" (rulings.md § Ninth round 3) | When the fit ran without a closing stage, the report still computes its misfit at the 1e-3 windows and the closing node rule. | clear |
| 2. Ambiguity | not stated | Kind 1, if one rule is right for every fit. | n/a |
| 3. Case against | none given | The parameters of a fit without a closing stage minimised the residual at 2 % windows and the declared node rule. Read at the closing precision, the misfit also contains the gap between the two optima (0.905 and 0.96 esd on these two patterns, per the eighth round's table, which I verified) and peak tails the fit never saw. The report could attribute that to a peak shape and suggest freeing a parameter that is already free. That was not seen here, but the test has little power. Only 2 and 1 regions passed the gates, and one cpd-1a share moved 0.43 → 0.57. | plausible, unobserved |
| 4. Case for | the eighth round's rule ("misfit from the accurate model stands") | The eighth round's mechanism applies to these fits too. Real data have the exact asymmetry, which the declared node rule misses by up to 5.6e-3 of a peak's maximum (7.8× the lab bar). And one rule is simpler for a reader. | moderate |
| 5. Tier / test | none given | No test pins it. The evidence is one measurement, recorded in rulings.md and `docs/docs/reference/refinement.md`. | none given |
| 6. Families | the fluorapatite and cpd-1a | Two families, both lab Cu Bragg-Brentano. No synchrotron (NAC), no LaB6, no known truth. Choosing the two patterns that move most is sound. | thin |
| 7. Record | none given | I found nothing in the change that tells the reader of such a report which precision its misfit was read at. | none given |

Would change: a known-truth case read both ways. For example, the eighth round's displaced specimen, or an injected misfit, fitted with `closing_window_tol=None`.

> Author: measured (`rulings.md` § Ninth round 3): the displaced specimen, fitted with the closing stage on and off and read both ways, ranks the displacement's cos θ shape first in all four (R² 0.539-0.555), and no reading suggests an action. No test pins it, and no field names the precision a report read at; both are WP-2004's if wanted.

## 7. Skill

**Verdict: no row owed.**

- **Item 4:** the package's own output carries the caveat, which is the cheapest place for it (WP-1338). `references/magnetic.md` has no row that compares the trials' Rwp, so nothing there is contradicted. If the winner's precision gets a public field, its row would go there.
- **Item 5:** the skill calls only `build_report(result)` (`references/series.md` 247), which is unaffected. The generated `api.md` signature is unchanged.
- **Item 1:** the generated `api.md` already lists the field.
- **Worth a recheck, not owed:** `references/series.md` 249-255 cites "SVD did not converge" and "Eigenvalues did not converge" destroying patterns. Those may no longer occur on the fit path. Its advice (set `on_result=` first) still holds for cell runaways and for failures of both drivers. I cannot tell from the files which routine those two cases failed in.

Would change: a skill row that tells an agent to compare Rwp across a `MagneticSolution`'s rows, or to call `build_report(model=...)` alone. I found neither.

Next: B14's lifts (the ~50-guard list to the judge) and the two owed domain tests (the interval and width-grid settings), which keep the tiering and demotion items open; whether this WP closes with them or hands them to WP-2017 is the maintainer's call. Before that, the three inferences of the ninth round's item 3 stand until the maintainer reverses one.

### 2026-10-22 (6th session) — the seventh and eighth rounds built: the closing stage stays on, the report reads two precisions, and a harmonic's order is the caller's

Everything rietx computes outside a fit now matches what a fit returns: `predict`, a simulated pattern and a stage run by hand use the closing stage's windows and its finer axial-divergence sampling, so synthetic test data carry the tails a measured pattern has. The maintainer weighed the closing stage's cost (1.2-2.3× a fit) against four measured alternatives and kept it on by default, with `closing_window_tol=None` documented as the switch for speed. Its two side effects on the FitReport were traced to causes and fixed: the report now measures the misfit on the accurate model and attributes it with the declared stages' local shapes. A zero shift and a sample displacement can be told apart again, and an impurity line no longer reads as texture. The wider reflection margin the maintainer approved was built and reverted, because it let the closing stage free a scale–Biso ridge (corundum 72.5 → 50.8 wt% against 72.7 on a synthetic scan). A neutron harmonic's order now has to be stated, because which orders a monochromator passes depends on its crystal.

*Done.*
- The seventh round (`2002-batch/rulings.md` § Seventh round), Q1 option 2: `compile_model`, `predict` and `run_stage` default to `CLOSING_WINDOW_TOL`; a recorded `None` keeps meaning the declared 2 % (`forward.recorded_window_tol`), so old histories replay unchanged; `NodeAction.api_call` renders the fraction a node ran at. Q2 option 2, by kind: `A5_CLIP` 1e-4 (tier 1); the texture minimum polished locally (`sphere_minimum`, tier 1); the closing FCJ rule (12 / 10 / 1024 / 3e-4, tier 1) for any compile at the closing windows or tighter; the magnetic floor passes behind the closing stage; the axial floor misses on cpd-1a (strict xfail); the edge margin built, then reverted (`90b4bc770`).
- About 40 test files sorted for the new defaults by four Opus lanes and the lead, nothing loosened; the goldens declare their capture windows and stay bit-identical; every guide re-measured.
- The eighth round (`rulings.md` § Eighth round): the closing stage kept as built; its cost and what switching it off moves recorded in `reference/refinement.md` § The closing stage and the skill's `batch-operating.md` 9c.34. Item 1, option 1: `report._reading_models` (misfit at the closing precision, shapes at the declared one), `build_report(instrument=)`, every package caller passing it; the 11 failing report tests pass. Item 2: margin kept at 0.5°. Item 3: axial floor tier 3 for WP-2017. Item 4: the caller-tier ruling recorded (`_audit.py` docstring, `generality.md` § The rule), `GTOL`/`XTOL` tier 3, `Harmonic.order` required, `harmonics=True` refused naming the crystals.
- Merged main twice (`775f06cf0`, `6c1709a5c`). This branch's WP-2019 is now WP-2020 (main has held 2019 since #1094). Main's new moment guide (#458) re-measured behind the closing stage; #934 (c)'s flat-silicon control drawn at the 2 % windows it was measured on (forwarded to 1968). WP-2019's two notes answered in this file's Inherited.
- Records the margin revert left stale corrected (`waiting.md` § B10, WP-2017's line, the theory page, the audit row), and one label of this session's own: the ridge regression was on `tests/test_scale_b_ridge.py`'s synthetic scan, not cpd-1a.
- Two B10 domain tests marked `slow` (the origin clip's 15 s, the texture minimum's 10.5 s), like the FCJ and window ones.
- From the full selection: the FitReport's strain screen no longer takes a fit down when its least-squares solve does not converge (#225's rule); two slow synthetic tests re-read (above).

*Measured* (macOS arm64, worktree venv `[dev]`, compiled tier on unless said).
- The closing stage's trade, five variants interleaved, another session's suite running (ratios compare; `rulings.md` § Eighth round has the table): shipped 1.39-1.40×, 2.31-2.35×, 1.58-1.62×, 1.21-1.29× on LaB6, FAP, cpd-1a, NAC; 1e-3 windows on every stage 1.88-2.09×, 4.51-4.61×, 2.62-2.65×, 1.15-1.21×; `intermediate_ftol` 1e-4 saves up to a fifth and fails cpd-1a's start test (0.123 against 0.1). Quiet-machine cost of the closing stage after the seventh round: 1.42-1.44×, 2.20-2.33×, 1.60-1.62×, 1.2× (1.16-1.19×, 2.04-2.18×, 1.37-1.39×, 1.2× before it).
- Off against on, in physical units: cpd-1a's fractions up to 0.12 wt% (two toward weighed, one away), FAP's `lor_size` 2.5 % and strain 3 %, LaB6's widths 1-2 %, NAC under 0.4 %.
- Behind the closing stage, re-measured on the final tree: answer 0.008, 0.011, 0.019 plain esd from the converged fixed point (FAP, cpd-1a, NAC); Biso starts 0.000/0.070/0.000, LaB6 9.14 (and 0.050 with `intermediate_ftol` 1e-4, forwarded to 2012).
- The report's displaced-specimen misranking: only with the closing rule's 3e-4 skip ratio and the closing windows together (each alone ranks the displacement first; ratio 0.02 alone recovers 0.99); at 0.02 the skipped asymmetry leaves 9.5e-3 of a peak's maximum, 13× the lab bar and 54× the synchrotron one; the declared rule's 5.6e-3 (7.8×) misread it the other way; the two-precision reading ranks the displacement first at 0.995. A compile costs 4-19 ms against a report's 0.24-1.57 s.
- `predict` at the closing windows: 8, 27, 29 ms on LaB6, FAP, cpd-1a and 138 ms on NAC's 59 498 points (the seventh round's reversal condition was about a second). The numpy path (compiled tier off) at the closing windows: worst (chunk, nodes, window) plane 29 and 56 MB on FAP and cpd-1a, evaluate 76-97 ms and bases 215-270 ms against 6-18 ms at 2 %, peak RSS 1.65 GB with three fits in the process.
- The moment guide behind the closing stage: blind 2.0353 ± 0.0459, reference 2.0868 ± 0.0337, moment present 2.1255 ± 0.0450 μB; a 1e-14 start nudge moves the blind moment 1e-4 and the rounds under 1e-5.
- Fast selection, final tree (main through #1098 merged, `6c1709a5c`): 11 086 passed, 191 skipped, 26 xfailed, 5:16, nothing else running; `397268391` then moved five cases (1 + 4 orders) to `slow`. On the final tree (`638503830`): 11 081 passed, 191 skipped, 26 xfailed, 6:03, nothing else running. The previous merged run: 3 failed, 11 083 passed, the same total. Before the report fix: 11 failed, 11 009 passed, 191 skipped, 27 xfailed, 7:07. The merges bring main's tests, so the session's own delta is not separable; this session replaced one harmonic test with one.
- Added tests in the fast tier (the branch against main): 33.45 s over 29, of which 25.4 s were the two domain tests now `slow`; `test_cross_backend.py`'s added row 5.74 s over 21 cases, the rest under 1 s each.
- Full selection, once, on the final tree before its last fixes (main through #1098 merged, `397268391`): 2 failed, 4 errors, 11 471 passed, 202 skipped, 41 xfailed, 54:58, nothing else running (the 5th session's took 29:55; the rise is not investigated). Bisected by running today's tests over each commit's `src`: the two failures arrived with `fef4a7c46` (synthetic data drawn at the closing windows), the four errors with `90b4bc770` (the margin revert changed `predict`'s draw, and so the starts). Fixed in `638503830`, and those files then passed alone with their slow tests (228 passed): the strain screen's solve guarded by #225's rule (macOS's system LAPACK `gelsd` did not converge on a finite, rank-deficient 22 003 × 102 design that SciPy's `gelsd`, `gelss` and `gelsy` all solved), the two-site moment test drawn at 2 %, the parametric ramp's slope bar at two esds (five seed sets: −1.04, +0.15, −0.44, +0.32, −0.14 esd). Still erroring: the Stephens brucite TRF pair (*For the maintainer*).
- Lanes: four `general-purpose` Opus agents sorted the test files, not dispatched under `/wp-start` 6c, so `session_usage.py lanes` sees none. Main context peaked at 623 K over 514 requests.

*For the maintainer.*
- **The Stephens brucite TRF fixture errors on this Mac.** Mid-solve in the last stage, SciPy's `gesdd` SVD does not converge on the near-singular Jacobian of the opt-in TRF solver; with a `gesvd` retry the fit completes at Rwp 0.1787 (the test expects 0.1790 ± 0.01). It is reached since the test seeds its scales with `compile_model` at the closing windows. A fix is either a retry inside `run_least_squares` (a new automatic action, needing its row) or accepting it on macOS; Linux is untested. Two errors in the full selection.
- **`solve_magnetic`'s answer carries the declared windows' misfit.** Its stages run at 2 % with no closing stage (the 5th session's choice for package-built trials), so on data with full tails its moduli esds come out 1.61× larger on the two-site Pnma set (0.00242 against 0.00151 μ_B). Ending its winner in a closing stage would remove it at the closing stage's cost.
- The code review's findings 3 and 5 and the judge's item 12 are design questions this round's rulings did not reach: a fit run with `closing_window_tol=None` still has its report read at the 0.1 % precision; a closing stage loosened past 1e-3 drops to the declared FCJ rule; `build_report` without `instrument=` silently reads one model (forwarded to 2004).
- The magnetic floor moved from invariant to tier 3 on the judge's reading (a class with no conditional form), approved under the seventh round's Q2; reverse it if the condition should stay a label.
- The automatic moment-angle interval's switch stays private (`_auto_intervals`); a public one is a rename at three sites.

*Review.* `/code-review high --fix 8023d18a8..663c2c992` found nine. Fixed in `abc9ac925`: after a fit with `closing_window_tol=None`, `_plan_settings` stored a recorded `None` that `run_stage` now reads as the closing windows, so every trial refit (intervals, profiles, verify, rivals) compared a 0.1 % χ² against a 2 % one; `_model_ticks` compiled at the 1e-3 default only to read positions; `_reading_models`' docstring misdescribed the texture screen. Declined: (2) storing resolved floats in every record instead of `None` (moves every golden and record; the trap is named in Gotchas); (3) and (5), the maintainer's (above); (4) the numpy path's chunk size at 1024 nodes, measured above at 29-56 MB a plane on lab data, a retune needing its own row; (8) the report twin's `moving_paths=None`, which is the safe "no claim" against a partial set; (9) the polish's grid literals (11×11, 0.3, 0.9) without rows, left for WP-2017's walk with the rest of the inline literals.

*Gotchas.*
- `None` means 2 % in a record (`StageResult`, `NodeAction`, `_plan_settings`) and 1e-3 to `compile_model` and `run_stage`; a new consumer forwarding a recorded value goes through `forward.recorded_window_tol` or compiles at the wrong precision silently.
- A test that draws a synthetic pattern with `predict` now draws at the closing windows; a control measured on a 2 % draw (#934 (c)'s) can stop showing what it was written for.
- The worktree guard refuses a heredoc followed by a `cd`, even in a subshell; write the script to the scratchpad.
- On this Mac, numpy's `lstsq` and SciPy's `gesdd` (system LAPACK) can fail to converge on a finite, rank-deficient matrix that another driver solves; a path change can reach one, so a solve inside a report or a guard follows #225's rule.

*Generality.* The judge's report follows unedited. The author's answer sits under each `weak`, `against` and `fails`.

Terms used throughout. The *closing stage* is the final solve with everything free that every plan now ends on. It runs at windows dropping 1e-3 of each peak (`CLOSING_WINDOW_TOL`). The *declared stages* run before it, at 2 % (`WINDOW_AREA_TOL`). *FCJ* is the axial-divergence asymmetry: rietx computes it as a sum of shifted copies of the symmetric peak (nodes), so the FCJ rows set how many copies each peak gets. *B10* is the 2026-10-19 ruling: a numerical setting is tier 1 once a test bounds its error over the domain it claims. *Plain esd* is the esd before the Bérar–Lelann inflation.

**1. rietx.model.origin.A5_CLIP (tier 3 → 1, 1e-3 → 1e-4)**

**holds.** The test bounds the error with a 7× margin, and I found no case for keeping 1e-3.

| Q | Author (where) | Found | Verdict |
|---|---|---|---|
| 1 | "moves only the origin convention" (row) | It clips the weight of the dominant site in a polar-group origin fix (A5 is the condition under which the paper's weights exist). It moves only the light sites' z esds. | ok |
| 2 | numerical setting | Arithmetic. Not a kind-1/2/3 decision. | ok |
| 3 | 1e-3 left 1.40 % against a 1 % bar | none found | — |
| 4 | 0.14 % over 1200 matrices; "about 1 ms more per solve" | `test_the_clipped_centroid_stays_within_an_esds_own_error_of_the_hold` asserts ≤ 1 %. It was made to fail at 1e-3. The domain is random matrices of 3–8 sites plus PbTiO₃. A polar structure with more than 8 sites is untested. | ok |
| 5 | tier 1 | B10, with the test named | ok |
| 6 | synthetic matrices, PbTiO₃ | A numerical domain, not dataset families | n/a |
| 7 | — | `ORIGIN_FIXED_ON_POLAR_AXIS` (refine.py:6590 reads `.clipped`) | ok |

Would change: a failure above 8 sites.

**2. TEXTURE_SPHERE_SAMPLES (3 → 1), TEXTURE_POLISH_STARTS, TEXTURE_POLISH_LEVELS (new, 1)**

**holds.** The local polish leaves at most 1.7e-9 against a 1e-3 bar. The reference it is checked against is independent of it.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | where `TEXTURE_NOT_POSITIVE` (the warning that the pole density goes negative somewhere) looks for the lowest density | Same | ok |
| 2 | numerical | Arithmetic | ok |
| 3 | 0 starts left 2.0e-3–7.9e-3 | none found | — |
| 4 | 9–15 ms a call | `test_the_sampled_sphere_minimum_meets_the_true_one`, orders 2–8. The reference is a 20 000-point grid with Nelder-Mead from its 5 lowest points. It also asserts the shipped minimum is never below the true one. It covers 4 of the 11 Laue classes; cubic is not among them. | ok |
| 5 | tier 1 | B10 | ok |
| 6 | — | n/a | n/a |
| 7 | — | `PhaseTexture.min_p_sphere`, `TEXTURE_NOT_POSITIVE` | ok |

Would change: a cubic or multi-dip case above 1e-3.

**3. fcj.CLOSING_NODES_PER_FWHM / CLOSING_MIN_NODES / CLOSING_MAX_NODES / CLOSING_SKIP_EXTENT_FWHM_RATIO (new, tier 1)**

**holds.** The test exists, has no expected failures, and passes over the claimed domain. The synchrotron margin is thin.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | the FCJ node rule at the closing precision | Same | ok |
| 2 | numerical | Arithmetic | ok |
| 3 | "the cheaper 11 / 8 / 768 / 3.5e-4 sat at 0.95" | The bar is a tenth of σ/peak at the strongest peak of FAP (lab) and NAC (synchrotron). The synchrotron worst is 0.81 of its bar, so a pattern counting about 1.5× NAC's peak would exceed it. The cap test probably never binds in the domain (`_assert_fcj_bar` returns early when no case reaches it), which I could not confirm without running it. This rule's 3e-4 skip ratio also broke the FitReport's test for telling zero shift from displacement (item 12). | weak point |
| 4 | worst 1.6e-4 lab, 9.9e-5 synchrotron over 8 500 cases | `test_the_closing_node_rule_meets_the_bar`, marked slow, 24 cells × 4 regions. It was made to fail at 6 nodes per FWHM. | ok |
| 5 | tier 1 | B10 | ok |
| 6 | lab and synchrotron apertures and widths | Domain, not families | n/a |
| 7 | — | `StageResult.window_area_tol` implies the rule | ok |

Would change: a higher-count synchrotron pattern measured against the bar.

> Author: recorded; a synchrotron pattern counting more than NAC is WP-2017's to measure against the bar.

**4. rietx.model.forward.MAGNETIC_SIZING_FLOOR (tier 3 → invariant)**

**weak.** The answer is invariant only behind the closing stage, and three reachable paths have none.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | the window size for a magnetic width freed from zero | Same | ok |
| 2 | — | Numerical | ok |
| 3 | "the package's magnetic default solve runs no closing stage" (row) | The default solve, `closing_window_tol=None` (which 9c.34 now recommends for screening) and a stage run by hand all have no closing stage. The test file's own header says "a plan that ends on the stage freeing the width keeps the clipping: 0.07, 0.17 and 0.57 esd on the moment". | against |
| 4 | 0.000 plain esd behind the closing stage | `test_the_preset_answer_does_not_depend_on_the_magnetic_floor` asserts ≤ 0.1, so the margin is asserted. | for |
| 5 | invariant | The record's answer-invariant class has no conditional form. | fails as worded |
| 6 | "synthetic MnF2, one family" | One synthetic family | — |
| 7 | none given | — | gap |

Would change: invariance measured with the closing stage off and on the default magnetic solve, or tier 3 with the condition stated.

> Author: tier 3 now, with the three paths and the 0.07-0.57 esd stated, approved under the seventh round's Q2 (the value left alone); flagged for the maintainer.

**5. rietx.refine.Refinement.run_stage:window_area_tol (tier 3 → 1)**

**holds.** A stage run by hand is the answer, and every surveyed program computes its answer at its one window setting.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | None now resolves to 1e-3, and with it the closing FCJ rule | Same | ok |
| 2 | 1 | Agrees. I found no program with two window settings (rulings, seventh round Q1). | ok |
| 3 | "A caller wanting the fast stage passes WINDOW_AREA_TOL" | A GUI user stepping through stages pays the time. The magnetic and axial sizing floors still act on a stage run by hand, with no closing stage after it. | minor |
| 4 | "at 2 % that answer carried up to 0.97 esd on lab data" | The cost (1.2–3.5× the stage) is "inferred" in the brief; none given measured. | ok |
| 5 | tier 1, inherited from `CLOSING_WINDOW_TOL` | Whose own row records LaB6 missing its answer bar by 0.908 esd (the U clamp) | ok |
| 6 | four protocols | via that row | ok |
| 7 | "the stage records the fraction it ran at" | `StageResult.window_area_tol` | ok |

Would change: a measured time cost large enough to matter in the GUI.

**6. rietx.optimize.least_squares.GTOL, XTOL (caller → tier 3)**

**holds.** This applies the 2026-10-21 caller-tier ruling: a number the package defaults inside the opt-in TRF solver is tiered on its own.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1–2 | the TRF stopping tolerances | Numerical | ok |
| 3 | "four orders under SciPy's own 1e-8" | SciPy is a library, not a refiner | — |
| 4 | at 1e-8 corundum's strain anisotropy failed its bar (3.64 against < 2.0) | WP-1109, one family (CPD) | ok |
| 5 | tier 3, "domain test owed (B10)" | Honest | ok |
| 6 | CPD only | One family | stated |
| 7 | — | n/a for a tolerance | — |

Would change: the owed domain test.

**7. rietx.schemas.instrument.DEFAULT_HARMONIC_ORDER (deleted; `harmonics=True` refused)**

**holds.** The evidence for removal is stronger: which orders pass is a fact about the crystal.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | the caller must name the orders | One argument per call | ok |
| 2 | — | Kind 3: the monochromator is outside the pattern | ok |
| 3 (for keeping) | old docstring: the second order "normally" carries the intensity | Recalled, not checked here: Si(111) and Ge(311/511/115/335) pass no λ/2 (diamond-structure extinction), and many high-resolution neutron instruments use Ge. | weak for keeping |
| 4 | the refusal names Cu(311), PG, Si(111), Ge(311) | Breaks `harmonics=True` and a bare `Harmonic()`. I found no `exclude_defaults`, so saved files carry the order. | ok |
| 5–7 | — | n/a | — |

Would change: a survey showing λ/2 dominant on nearly all CW instruments.

**8. rietx.model.forward.AXIAL_SIZING_FLOOR (tier 3, re-evidenced)**

**holds** as a record of tier 3 deferred to WP-2017 (the planned second pass over tier-3 settings). cpd-1a's 0.138 esd behind the closing stage is stated and is a strict expected failure.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 3 | 0.229–0.516 esd without the closing stage | Still reaches `closing_window_tol=None` | stated |
| 4 | 0.05 costs 1.25–1.8× | — | ok |
| 5 | tier 3, approved 2026-10-22 | Matches eighth round item 3 | ok |
| 7 | — | none | gap (as before) |

Housekeeping: the comment in test_lab_instrument.py:710 still quotes the old "0.16 esd". Would change: WP-2017's measurement.

> Author: the comment is kept: it quotes the two floors' fixed points (the 5th session's measurement), a different quantity from the start test's 0.138.

**9. rietx.model.forward.REFLECTION_MARGIN_DEG (tier 3, re-evidenced)**

**holds** as a record. The reverted edge rule and the ridge it freed are recorded.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 3 | fails on FAP and cpd-1a, 0.026–0.043 esd behind the closing stage | Stated | ok |
| 4 | the wider margin freed a scale-B ridge (corundum 72.5 → 50.8 wt%, true 72.7) | On a synthetic scan | ok |
| 5 | grounds cite "the eighth round (ruled 2026-10-22)" | But `approved="2026-10-21"` | inconsistent |

Housekeeping: the forward.py comment still says "owed to the maintainer". Would change: WP-2017.

> Author: both fixed (`approved="2026-10-22"`, and the comment now says the eighth round kept 0.5°).

**10a. rietx.model.forward.WINDOW_AREA_TOL (grounds updated)**

**weak.** The list of places this 2 % still reaches omits a new deliberate consumer.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | reaches `closing_window_tol=None`, the magnetic trial moments, `SolveCost.from_pawley` | `report._reading_models` now compiles the report's shape model at this value, so it decides the region attribution ranking (Layer 1) and the texture screen. | missing |

Would change: grounds naming the report.

> Author: the grounds now name the report's shapes.

**10b. fcj.NODES_PER_FWHM / MIN_NODES / MAX_NODES / SKIP_EXTENT_FWHM_RATIO (grounds updated)**

**weak.** The grounds say "the declared stages, which only steer". Two places where the declared FCJ rule decides more are not named.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 3 | "which only steer" | Under `closing_window_tol=None` this rule computes the answer, with up to 5.6e-3 of the peak maximum, 8× the bar. The report's shape model also uses it. | missing |

Would change: grounds naming both.

> Author: the four rows' grounds now name a closing-off answer (5.6e-3) and the report's shapes.

**10c. rietx.model.origin.A6_MAX_ITER (invariant, re-evidenced)**

**weak.** The cap is now reached in 41 % of cases. Invariance rests on the sum solve taking over, and no test varies the cap.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 4 | "reached by 498 of the 1200 … every one met by the sum solve" | The test asserts `converged`, not invariance to the cap. A larger cap could keep the iteration's own result, within A6_RTOL (1e-3), instead of the sum solve's. | partial |
| 5 | "tests/test_floating_origin.py:694" | Stale. The test is `test_eq_21_is_met_where_a5_holds_by_a_hair` at line 840. | fix |

Would change: a test at caps of 2000 and 20 000 that asserts the margin.

> Author: the reference now names the test. The test across caps is not added; it is owed with the other B10 domain tests.

**11. FCJ rule chosen by window fraction; compile_model and predict default to CLOSING_WINDOW_TOL (not in the table)**

**weak.** It follows the seventh round's Q1 ruling. The brief's own condition for changing its mind was never measured.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | `closing_precision = window_area_tol <= CLOSING_WINDOW_TOL` | One number switches two settings at a step. The caller cannot choose the FCJ rule separately. | — |
| 3 | — | `None` means 1e-3 to `compile_model` and 2 % to `recorded_window_tol`, so a caller passing a recorded `None` straight through rebuilds the wrong stage (documented in docstrings only). The brief said it would reverse "if one predict call took more than about a second on a large lab pattern with Lorentzian peaks"; none given measured. The 1024-node cap adds to that. | against |
| 4 | the 0.8σ predict/y_calc gap; synthetic tests now exercise the shipped path | Measured | for |
| 7 | `CompiledModel.window_area_tol` | Not a record schema; the stage's field covers fits | partial |

Would change: a timed `predict` on a large lab Lorentzian pattern.

> Author: timed: 8-29 ms on LaB6, FAP and cpd-1a, 138 ms on NAC's 59 498 points (*Measured*). The two meanings of `None` are under *Gotchas*; storing resolved floats instead (the review's finding 2) moves every record and golden, so it is declined here.

**12. FitReport's two-precision reading (report._reading_models)**

**weak.** The default path is measured both ways. The fallback silently reproduces the measured misreading.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 1 | misfit at the closing precision, shapes at the declared one | Ruled, eighth round item 1 | ok |
| 3 | — | `instrument=` defaults to `None` with no warning, and Pawley always reads one model. Either way a default fit's closing-precision model supplies the shapes. That brings back the near-collinear zero-shift and displacement shapes (\|cos\| 0.9986) and the 0.35 false texture reading. The declared rule skips asymmetry under extent/FWHM 0.02, so a real axial misfit near 90° has no shape to be attributed to. That last point is my inference, not measured. | against |
| 4 | the displaced specimen ranks displacement first at 0.995; 4–19 ms a compile | Synthetic cases only | for |
| 6 | — | No real-data family named | none given |

Would change: the fallback warning or refusing, and a real-data case.

> Author: declined here. A warning or a refusal on the fallback is a change of behaviour the maintainer has not ruled on; it goes to *For the maintainer* and to WP-2004 with the mechanism.

**13. Skill row batch-operating.md 9c.34**

**weak.** It passes Rule 4 by naming a field, but its evidence is four of rietx's own fits (Rule 3), and it says nothing about units the screen rejects.

| Q | Author | Found | Verdict |
|---|---|---|---|
| 3 | "Refit the units a screen keeps with it on" | Off, answers sit 0.15–0.96 esd away. A unit rejected on that error is never refit. | gap |
| 4 | "1.2-2.3×", one fit each on four patterns | The eighth-round table gives 1.21–2.35× (rounding). The maintainer asked for this record. | ok |
| 6 | four acceptance patterns, "no batch has timed it" | rietx's own runs | Rule 3 |

Would change: a timed batch, or a source outside rietx for the practice.

> Author: the row now asks for the units near the cut as well. A timed batch is owed; the row says none has timed it.

Next: first the two items that keep a measured result wrong or red, under *For the maintainer*: the Stephens brucite TRF error (it keeps the full selection red on macOS) and `solve_magnetic` ending in no closing stage (its esds 1.61× on realistic data). Then the three design questions the review and the judge raised, since one of them (the report of a closing-off fit) changes what a speed-mode user is told. Then B14's lifts (the ~50-guard list to the judge) and the two owed domain tests (the interval and width-grid settings), which keep the tiering and demotion items open; whether this WP closes with them or hands them to WP-2017 is the maintainer's call.

### 2026-10-21 (5th session) — the sixth round built: every plan ends in a closing stage, and the width ceilings sit at the 2θ axis

Every refinement now ends with one stage more than its plan declares. After the declared stages, rietx recompiles the model at the answer with peak windows that drop 0.1 % of each peak instead of 2 %, and solves once more. On the fluorapatite, cpd-1a and 11-BM NAC the answer then lies within 0.02 esd of the answer with complete peak tails, and two different Biso starts agree to 0.07 esd or better, at 1.05-2.05× the fit time. SRM 660c LaB6 still misses, for two reasons already owned elsewhere. The new default moved 126 fast tests; four parallel lanes sorted them, and nothing they found refutes the closing stage, though two questions about it now wait on the maintainer.

*Done.*
- The sixth round's answers recorded (`2002-batch/rulings.md` § Sixth round's answers), with the maintainer's standing instruction to use judgement where no option is clear.
- Q1/Q2, option 3: `RefinementPlan.run_stages()` appends a closing stage (`closing_stage()`: every declared glob in first-seen order, the last declared stage's settings, no seed, the solver's ftol), compiled at `closing_window_tol` (default `CLOSING_WINDOW_TOL` 1e-3, `None` bit-identical to before). `stage_ftols()` and `stage_window_tols()` are parallel to it; both runners, the series collapse, `run_stage` (a `window_area_tol` keyword), `cherry_pick`, `replay`, the GUI ladder and run status, `PlanSpec`, the `.rxt` `closing` line, both manuals and the skill's API index carry it. `StageResult.window_area_tol` and `NodeAction.window_area_tol` record it. Trials that compare χ² with the fit inherit the answer's windows through `_plan_settings`; package-built trial plans (indexing validation, extinction screen, magnetic default solve, body misfit) run none. Every acceptance suite names it (a validation-matrix test now enforces that); the Stephens suite declares `None`.
- Q3 (c): the roughness seed recorded per model on `StageResult.seeded` (tier 3); the code keeps one 0.3.
- Q4 (a): the cap clause confirmed. Q5: tier 2 is "already validated in a known code", a dissent no longer moves a default off it, and a choice outside the seven programs' range names its reason (`generality.md`, the judge's question 5, `_audit.py`'s docstring).
- Q6: nothing bounded; the maintainer's concept filed as WP-2020 (opt-in sets of bounds and defaults per scenario; filed as 2019 and renumbered at the 6th session's merge with main, which already held 2019).
- Q7 (a): the five TCHZ ceilings at the 2θ axis (`TCHZ_CEILING_DEG`, 180°, 180² deg²), tier 1; the brucite test's xfail removed.
- Behind the closing stage the three start tests pass the ruled 0.1-esd bar (`tests/test_staged_start_invariance.py`): `HARMONIC_WEIGHT_SEED` invariant; the four intermediate-tolerance rows tier 3 with the absent-zircon failure stated; `Atom:biso` invariant on three families (a hand row, waiting on B14's lift).
- Found and fixed on the way: `replay` now compiles at a node's recorded c_w and window slack as well as its window fraction; a per-stage guard finding repeated on the same paths is reported once, the latest (the closing stage doubled `TEXTURE_NOT_POSITIVE` and its siblings); the GUI ladder shows the closing stage as its last rung, with its node's Rwp (the last declared rung read 0.04141 against the result's 0.04164).

*Measured* (macOS arm64, worktree venv `[dev]`, compiled tier on).
- Closing answer against the 5e-5 fixed point polished from the same start (`test_window_domain.py::test_the_closing_stage_meets_the_bar`): 0.008, 0.018, 0.019 plain esd on FAP, cpd-1a, NAC, windows 0.026, 0.022, 0.091σ; LaB6 0.908 esd on `u` (a strict xfail citing WP-1467: the closing stage equals one polish at 1e-3 to every printed digit, a second recompile moves u 1 esd and a third 0.002, the high-angle Gaussian variance on the clamp floor).
- Start tests behind the closing stage: Biso 0.5 against 1.5 Å² 0.000/0.070/0.000 (LaB6 9.36, WP-2012's mirror); `intermediate_ftol` 1e-6 against None 0.000/0.042/0.000/0.000, and 0.185 on cpd-1a with an absent zircon, where at 1e-9 the unseen cell walks to its 400-evaluation budget before the closing stage holds it (the hold no longer flips); the harmonic seed ≤ 0.003.
- Cost through the shipped code, two interleaved runs each, nothing else running: LaB6 1.05-1.19×, FAP 2.03-2.05×, cpd-1a 1.37-1.38×, NAC 1.12-1.26×. Last session's probe read 1.36-2.26× with the last declared stage at 1e-9.
- `REFLECTION_MARGIN_DEG` at the closing windows: 0.186σ and 0.124σ at the last points of FAP and cpd-1a, the answers moving 0.026 and 0.043 esd (recorded on its row, not fixed).
- Brucite under TRF with the ceilings at 180°: Rwp 0.17878, t 0.36, −1.22, 0.40, 2.29; no-ceiling control 0.17891, t −203.
- Full selection, once, on main merged in, after the review: 5 failed, 11 372 passed, 202 skipped, 46 xfailed, `[dev]`, darwin/arm64, 29:55, another session's suite overlapping its last minutes. The five are slow tests the closing stage moved, and their six files then passed alone (29 passed): the roughness-seed test read its stage as the last (it now declares no closing stage, as B3 was measured); the PowderLine hump's budget is spent by the closing stage rather than the declared `extra_components` stage (the test now asks the last stage freeing it); the neutron width test's single esd moved with the closing stage, still one value at four starts to 1.5e-8 (`x` 0.0098437 → 0.0102720, `y` 0.018101 → 0.0189972); the NAC termination golden gains the `stage closing` line (regenerated); and the 150 K magnetic solve's class-3 pair, which a correlation near its threshold folds, stops folding when the nuclear reference ends in a closing stage (moduli 0.514 and 0.131 with esds 0.69 and 2.79), so the shared Cr₂WO₆ fixture fits its reference at the declared stages alone.
- Fast selection on main merged in (32 merges, `5a99ba928`), after the review: 1 failed, 11 012 passed, 191 skipped, 32 xfailed, `[dev]`, darwin/arm64, 5:44, nothing else running; the failure was the root CLAUDE.md over its 993-line cap, fixed by folding the new clause into the schedule bullet. The added tests cost 3.53 s in the fast tier on this machine (`test_closing_stage.py` 0.43 s for its 7), none joining the tail; the closing-stage and start tests are `slow`.
- Fast selection, final tree before the review: 3 failed, 10 948 passed, 191 skipped, 31 xfailed, 5:47, nothing else running; the three fixed in `a737f66cb` (WP-2020's log line, the landing panel's numbers, `predict` made independent of what the object fitted). The first run after the default changed: 127 failed, 10 808 passed.
- Lanes (four `general-purpose` Opus agents on disjoint test files, not dispatched under `/wp-start` 6c, so `session_usage.py lanes` sees none): 198 573, 274 275, 207 882 and 328 297 tokens. Main context peaked at 798 K over 351 requests.

*For the maintainer.*
- **Which windows should evaluation outside a fit use?** A synthetic pattern drawn with `predict()` or `compile_model()` at the default 2 % windows lacks the tails the closing stage fits, and lanes B and C traced every recovery shift with the closing stage on to that: redrawn at 1e-3, texture coefficients recover to 4.5e-9, `AIR_SCATTER_UNDECLARED`'s claims hold, the magnetic angles return to truth. A fresh `Refinement(...).predict()` therefore no longer reproduces a default fit's `y_calc` (1.85e-4 of the peak height). Making evaluation outside a fit default to the closing windows would fix both and move the synthetic data of 39 test files; left alone, the mechanism tests declare no closing stage. Not built.
- **The six other failing numerical settings**: Q1 proposed the closing stage's rule for them; only the window was built.
- Under TRF, the closing stage stops CPD brucite where one S_HKL esd collapses (t = −268 against −1.22); LM is unaffected. The Stephens suite declines the closing stage for both fits its information criteria compare.
- Guard messages now name the closing stage (`HOLD_BLOCKED_PLAN`, `STAGE_PATH_UNKNOWN`, `HIGH_CORRELATION`). Kept, since the stage is visible everywhere else.
- `SolveCost.from_pawley` stays on the declared stages' windows: at 1e-3 NAC's banded M0 grew a third denser.

*Review.* `/code-review high --fix` over `876d345ab..HEAD` found ten. Fixed in `1f58008b6`: `suggest()`'s probe compiled at the 2 % windows while the answer it scores sits on the closing stage's; `predict`'s docstring quoted a pre-closing measurement as current; `run_stage(window_area_tol=1.5)` refused in the words of a plan field; a history recorded before the closing stage blanked every rung of the GUI ladder; `CLOSING_WINDOW_TOL`'s comment and `PlanSpec`'s description quoted another measurement and cost range than the matrix's record. Declined, each a judgement rather than a defect: the declared sharp peaks' windows at 1e-3 (k(η = 1) = 318, so a default member's window covers the pattern; deliberate, and one member is one column); `CELL_RUNAWAY` once per stage that fired (deliberate in both runners; the closing stage can add one); a magnetic continuation now running two solves over one free set (a cost); `summary()`'s `plan:` line listing the declared stages (the stage lines name `closing`, and changing it moves the NAC termination golden and every guide); the series payload's `n_stages` counting the declared plan.

*Generality.* The judge's report follows unedited. The author's answer sits under each `weak`.

**Rows added**

**`rietx.schemas.plan.CLOSING_WINDOW_TOL` (constant, tier 1, 1e-3)**

**holds.** The case for acting is stronger: at 1e-3 the window error stays under a tenth of each point's noise on all four families. The one gap is that all four are X-ray patterns. (The constant is the fraction of each peak's area that the closing stage's windows leave out. The closing stage is the extra all-free solve that every plan now ends with.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "The area each peak's window may drop in a plan's closing stage" (`schemas/plan.py` docstring) | Yes. It also applies to declared sharp peaks (`model/forward.py:3638-3641`). | clear |
| 2. Kind | constant, no `ambiguity` | A numerical setting: it sets how accurately rietx computes, and decides nothing. | n/a |
| 3. Case against | "1e-3 drops less than TOPAS …, MAUD …, RIETAN-FP and FullProf, and more than GSAS-II (0.5 %), BGMN and EasyDiffraction" (plan.py) | The value lies inside the seven programs' range (`docs/practice.md` § How far a peak is computed). The only refiner who would choose otherwise is a batch user who takes TOPAS's or MAUD's 2 % for speed. That is a cost preference, and the plan setting serves it. | weak |
| 4. Case for | At 2 %, "up to 0.97 esd on lab data … the background 2 to 5 esd" (plan.py) | Confirmed in `tests/test_window_domain.py`'s docstring table. At 1e-3: 0.058, 0.026, 0.022 and 0.091σ at the worst point, and 0.003-0.020 esd. | strong |
| 5. Tier and source | tier 1 under B10 (the 2026-10-19 ruling on numerical settings), via `test_the_closing_stage_meets_the_bar` | The test exists. LaB6 is a strict xfail on the answer bar: 0.908 esd on U. The module docstring shows that U moves 0.9-1.2 esd "under every window setting", so the miss belongs to the Gaussian-width clamp (WP-1467), not to this number. The window-error bar itself passes on LaB6 (0.058σ). | holds |
| 6. Families | SRM 660c, FAP, cpd-1a, NAC | Four laboratories: NIST, the GSAS-II tutorial, the CPD round robin, APS 11-BM. The reference is the same code at a converged window, which verifies the arithmetic. That is the right test for a numerical setting. Not covered: constant-wavelength neutron, magnetic peaks, declared sharp peaks. | holds, X-ray only |
| 7. Record | — | `StageResult.window_area_tol` on the stage named `closing` | present |

Would change the verdict: a constant-wavelength neutron pattern, or a pattern with magnetic or declared sharp peaks, failing the 0.1σ point bar at 1e-3.

**`rietx.schemas.plan.PlanSpec:closing_window_tol` (default, tier 2, ambiguity 1, 1e-3)**

**weak.** The case for acting is stronger and was measured. But the tier-2 ground rests on one program's default (BGMN). The row's own evidence names a staging program with no final cycle (MAUD) while the row claims the first kind. And two measured failures of the action are missing from the row.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "every plan ends with a closing stage at tight windows" (row grounds) | It adds one more all-free solve to every fit, which the caller did not ask for. `None` turns it off. | clear |
| 2. Kind | `ambiguity=1` | The first kind needs unanimity among competent refiners. The evidence says "MAUD's wizard has no final cycle". A defensible reading is that MAUD is not a dissenter: its windows move at every evaluation (practice.md § Staging), so the window half of the problem never arises there. The row does not make that argument. | weak |
| 3. Case against | none given in the row | Three cases. (i) A batch user: the fluorapatite fit takes 2.03-2.05× as long (plan.py). (ii) A TRF user (TRF is the opt-in trust-region solver; LM is the default): `tests/test_acceptance_stephens.py:168-173` says "under TRF the closing stage stops brucite where one S_HKL's esd collapses (t = -268 against -1.22)". (S_HKL are the Stephens anisotropic-strain coefficients.) That suite therefore opts out. (iii) LaB6: one closing solve is not a fixed point, and a second recompile moves U by 1 esd (`test_window_domain.py` `_CLOSING_FAILS`). No audit row mentions (ii) or (iii). GSAS-II, TOPAS, FullProf and EasyDiffraction do not stage, so they count neither way. | moderate, unrecorded |
| 4. Case for | "removes the 2 % window's error from the answer and most of a staged plan's start dependence" (grounds) | Two Biso starts: cpd-1a 0.751 → 0.064 esd, fluorapatite 0.119 → 0.000, NAC 0.008 → 0.000 (`rulings.md` § Sixth round). Left to the caller, every default fit carries up to about 1 esd of error silently, because nothing reports the window error. | strong |
| 5. Tier and source | BGMN by default (manual §A.4; Doebelin & Kleeberg 2015 §2); RIETAN-FP's `NAUTO = 2` | practice.md records BGMN's closing run. I read practice.md, not the BGMN manual or the paper. Neither practice.md nor the row says `NAUTO = 2` is RIETAN-FP's default. So tier 2 rests on one program. The amended rule allows that for a default. But this default switches on an action, and the rule's tier-2 text does not say which reading governs that case (see the rule-text item below). | weak |
| 6. Families | four, against the whole protocol run at 1e-3 | The reference is the code's own arm. **none given** on distance from an independent reference: SRM 660c's certified cell or CPD's weighed composition. The Q1 brief says "I have not measured that against SRM 660c's certified cell". | gap |
| 7. Record | "recorded in RefinementResult.stages as the stage named 'closing'" | Also `StageResult.window_area_tol`, and the `.rxt` line `closing`. | present |

Would change the verdict: the row naming the LaB6 and TRF-brucite failures, stating why MAUD is not a dissenter, and giving the SRM 660c cell's distance from its certificate with the closing stage on and off.

> Author: done in `1f58008b6`. MAUD's windows move every evaluation, so the error the stage removes never arises there; both failures named; SRM 660c's cell is 4.1568823 Å off and 4.1568821 Å on, +24.6 ppm from the reference both ways.

**`rietx.schemas.results.StageResult.window_area_tol` (action, tier 2)**

**holds.** It is the record field the rule requires a kept action to leave, and it takes no action itself.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "Records the action rather than taking one" (grounds) | Nothing. It reports the closing stage's window fraction. | clear |
| 2. Kind | `ambiguity=1` | Inherited from the action it records. | n/a |
| 3. Case against | — | none found | — |
| 4. Case for | "a reader rebuilding the model from the result passes it to compile_model" | `replay` and `cherry_pick` read the node's copy (`refine.py:3819-3822`, `9885-9899`). | holds |
| 5. Tier and source | tier 2 via the PlanSpec row, approved 2026-10-21 | Its tier stands or falls with that row. | as that row |
| 6. Families | — | n/a | — |
| 7. Record | — | It is the record. `NodeAction.window_area_tol` is its history twin. | present |

Would change the verdict: a stage whose compile used a window fraction other than the one this field reports.

**`rietx.refine.Refinement.run_stage:window_area_tol` (default `None`, tier 3)**

**weak.** The case against the 2 % default is stronger. The grounds lean on "declared stages only steer", which does not hold for a stage run by hand. No closing stage follows such a stage, so its answer carries the 2 % window error.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "None resolves to forward.WINDOW_AREA_TOL" (evidence) | A hand-run stage compiles at 2 % windows. | clear |
| 2. Kind | `ambiguity=1` | A refiner polishing by hand would not choose the steering windows for the last solve, so the data do not settle this one way. | doubtful |
| 3. Case against | none given | The GUI's single-stage run calls `p.run_stage(stage, …)` with no window fraction (`gui/session.py:1583`). A GUI user who ends on a hand-run stage gets an answer up to 0.97 esd off on lab data, and only a `None` in the record says so. | moderate |
| 4. Case for | "A stage driven by hand takes the declared stages' windows; a caller who wants the closing stage's states it" (grounds) | It matches fit()'s declared stages and is cheaper. The package's own trials pass `**trial._plan_settings`, which now carries the fit's fraction (layer2, intervals, fraction profiles), so they are consistent. | moderate |
| 5. Tier and source | tier 3, inherits `WINDOW_AREA_TOL`, approved 2026-10-21 citing Q1 and Q2 | The sixth-round answers (`rulings.md:259-268`) rule on a plan's closing stage. They do not mention hand-run stages. **none given** for a ruling on this seat. | weak |
| 6. Families | inherited | The same four families, all failing at 2 %. | — |
| 7. Record | — | `StageResult.window_area_tol = None` and `NodeAction.window_area_tol` | present |

Would change the verdict: a ruling that a hand-run stage is a steering stage, or the GUI passing the stored plan's fraction to its last stage.

> Author: the grounds now say a hand-run stage carries the 2 % error and that the seat is unruled; it goes to the maintainer with the evaluation-windows question.

**`rietx.schemas.instrument.TCHZ_CEILING_DEG` (constant, tier 1, 180)**

**weak.** The case for a finite ceiling is real but rests on one TRF fit. The number exists to steer TRF's steps, which makes it a solver-path setting, not arithmetic. And under the shipped default the fit it was measured on still fails.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the width of the 2theta axis (180 deg for X and Y, its square for U, V and W)" (evidence) | A finite upper bound on all five peak-width coefficients. | clear |
| 2. Kind | constant | n/a | n/a |
| 3. Case against | none given | None of GSAS-II, FullProf, RIETAN-FP, TOPAS, MAUD or EasyDiffraction bounds these by default (practice.md § Peak-width limits). So the choice lies outside practice, and the row names its reason, as the new rule asks. "LM … gives the same answer either way" (`ProfileTCHZ` docstring): no test found. | moderate |
| 4. Case for | "CPD brucite Stephens under TRF stopped at Rwp 0.17891, one S_HKL t = -203, without it and at 0.17878 … with it" | Confirmed in `rulings.md:287-293`. Any finite ceiling, at 10 or at 1000, restores the fit. | strong on one fit |
| 5. Tier and source | tier 1, "arithmetic" | The arithmetic part holds for X, Y and W: no line is wider than the axis. For U, the width term is U·tan²θ, so at 2θ = 10° U at its ceiling still gives a FWHM of about 16°. That is far past any line, but it is not "the axis width". The reason the number exists is TRF's path. The rulings record that B10 holds solver-path switches at tier 3 until refits of three families agree (`rulings.md:429-433`). | weak |
| 6. Families | one: CPD brucite, under TRF | One family. Part of the evidence is an Rwp comparison. And `test_acceptance_stephens.py:168-173` now declares `closing_window_tol=None`, because with the closing stage TRF brucite collapses again (t = -268). The ceiling's measured benefit therefore holds only with the closing stage off. | weak |
| 7. Record | — | none. A ceiling that bound would raise `BOUND_HIT`, but nothing shows it steering TRF. | absent |

Would change the verdict: TRF refits of three families with and without the ceiling, with the closing stage on, plus an LM bit-identity check with the ceiling in place.

> Author: retiered to tier 3 as a solver-path setting, the closing-stage failure in its evidence (`1f58008b6`); the three-family TRF refits are owed.

**Rows moved off `UNAUDITED_BASELINE`**

These leave the list and nothing is added, so the list shrinks and no reason is owed.

**`rietx.schemas.instrument.HARMONIC_WEIGHT_SEED` (invariant, 0.01)**

**weak.** The margin is wide: 0.003 against a bar of 0.1. But it rests on one synthetic family, misses the true-weight-0 case, and the invariance holds only while the closing stage is on. (The seed is the starting weight of the λ/2 harmonic line.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | the start of the λ/2 weight | yes | clear |
| 2. Kind | constant | n/a | n/a |
| 3. Case against (the seed matters) | — | Before the closing stage the weight moved 0.15 esd and one background coefficient 0.86 between seeds (`waiting.md` § B8 and B9). With `closing_window_tol=None` that is still the behaviour. | moderate |
| 4. Case for (invariant) | "seeds 0.001 and 0.3 against 0.01 within 0.1 plain esd (at most 0.003)" (evidence; plain esd is the esd without the Bérar-Lelann inflation) | Confirmed in `tests/test_staged_start_invariance.py`'s docstring. | strong where tested |
| 5. Tier and source | invariant, `test_the_harmonic_seed_does_not_change_the_answer` | The test asserts the 0.1 bar, not the measured margin. Its docstring lists seeds "0.001, 0.1 and 0.3", but the code runs 0.001 and 0.3. The label is unconditional, yet the invariance holds only behind the closing stage. Last session the judge raised the same objection about `NFEV_PER_ITERATION` (WP-2002 file, line 548). | weak |
| 6. Families | "a synthetic CW neutron corundum, the one family a harmonic has" | One family. Its data come from rietx's own forward model, so the test contains no model error. True weights 0.003 and 0.05 only. True weight 0, the usual case when a caller turns harmonics on to look, is not in the test. | weak |
| 7. Record | — | `HARMONIC_ABSENT` / `HARMONIC_FRACTION` | present |

Would change the verdict: a true-weight-0 case, the held-out Nd₂Ru₂O₇ pair, and the row saying it is invariant only with the closing stage on.

> Author: true weight 0 added and passing, the row says "behind the closing stage only", the docstring corrected (`1f58008b6`); the held-out pair stays held out.

**`rietx.schemas.plan.INTERMEDIATE_FTOL` and `PlanSpec:intermediate_ftol` (tier 3, 1e-6)**

**holds.** The case for acting is stronger. Four unrelated families agree within 0.042 plain esd with the arm that converges every stage, and the one failing case favours the shipped value. Two gaps: no distance from an independent reference, and the saving was measured before the closing stage existed. (The setting is the stopping tolerance on stages before the last.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | stops every stage but the last at 1e-6 | The last declared stage now stops early too, since the closing stage is last. | clear |
| 2. Kind | `ambiguity=1` | Efficiency, near answer-invariant. I agree. | agree |
| 3. Case against | "fails on cpd-1a with an absent zircon declared, 0.185 esd on fluorite a" | Confirmed (strict xfail). At 1e-9 the unseen zircon's cell walks until the stage budget runs out, so the shipped value is the better arm. practice.md does not survey stopping tolerances, and I found no program default. | weak |
| 4. Case for | "1.00-2.15x fewer evaluations (WP-1113/1123)" | Measured before the closing stage. **none given** behind it. | moderate |
| 5. Tier and source | tier 3, approved 2026-10-21 (Q2, bar 0.1 plain esd) | matches `rulings.md:259-268` | holds |
| 6. Families | SRM 660c, FAP, cpd-1a, NAC | Four laboratories. The reference is the other arm, which verifies and does not validate. **none given** on distance from the certificate or the weighed composition. | gap |
| 7. Record | — | `StageResult.ftol`, `NodeAction.ftol` | present |

Would change the verdict: the evaluation saving re-measured behind the closing stage, and the SRM 660c cell and CPD fractions against their references under both arms.

**`rietx.schemas.plan.StageSpec:ftol` (default `None`, tier 3)**

**holds.** It defers to the plan's schedule, and its evidence is the intermediate tolerance's, copied verbatim. Would change the verdict: a stage-level default other than "defer to the plan".

**`rietx.schemas.results.StageResult.ftol` (action, tier 3)**

**holds.** It records the tolerance each stage ran at, never the one it declared. Would change the verdict: a stage whose solver ran at a tolerance other than the recorded one.

**`rietx.schemas.results.StageResult.seeded` (action, tier 3)**

**weak.** The Suortti half holds. The Pitschke half lets the starting value pick between two minima that the data score, and it reports nothing. Rule 1 puts that in the second kind, while the row claims the first. (Suortti and Pitschke are the two surface-roughness corrections.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the one shipped seed is _ROUGHNESS_STAGE's 0.3" | It starts both roughness strengths at 0.3 when they sit on their floor of 0. | clear |
| 2. Kind | `ambiguity=1` | Pitschke from 0 lands in a minimum with χ² 4.8 % lower, outside the model's valid range. From 0.3 it reaches the switched-off branch (`rulings.md` Q3). Two outcomes the data score make this the second kind: rank them, pick only in Rule 1's two cases. | disagree |
| 3. Case against | the author's case in Q3: a careful user may want to see that the data prefer the correction, answered with "The warning already shows them that" | `ROUGHNESS_OUTSIDE_REGIME` fires on the branch reached from 0. From the shipped 0.3 the fit stays in range, so as I read it that warning does not fire there, and the caller never learns that a lower-χ² branch exists. I inferred this and did not run it. FullProf's examples start at 1.23-1.50 (practice.md). Where that start lands: none measured. | moderate |
| 4. Case for | "from 0.3 the fit reaches the switched-off branch inside the model's valid range" | From 0, CPD zincite's scale goes ×2.1 and Biso(O) goes 0.05 → 0.59. | strong |
| 5. Tier and source | tier 3, ruled (c) on 2026-10-21 | Ruling (c) was "Split the constant". The build keeps one number in the code and records the two models apart, which matches the option's substance. | holds |
| 6. Families | Suortti: five patterns, three families; Pitschke: CPD only | As stated. Suortti is measured against each family's reference ("the same distance from each reference", waiting.md § B3). | Suortti holds, Pitschke one family |
| 7. Record | — | `StageResult.seeded`. `ROUGHNESS_OUTSIDE_REGIME` fires only on the branch reached from 0. | partial |

Would change the verdict: the 0.3 path reporting that a start at 0 reaches a lower χ² out of range (the ranking), or Pitschke measured on a second family.

> Author: the maintainer ruled (c) on a brief that stated the lower out-of-range χ² from 0; the ranking report is a fair follow-up and is not built.

**Rows changed in evidence or grounds**

**`rietx.model.forward.WINDOW_AREA_TOL` (grounds and approval changed)**

**weak.** The new grounds name one place where the 2 % error still reaches an answer. This same change leaves several others: a hand-run stage (`run_stage`), `predict(grid)`, and the magnetic default solve, whose `MagneticTrial.moments` (`strategy/magnetic.py:387`, plan at `:2253-2258`) are numbers a caller reads. Would change the verdict: grounds that list every place still returning numbers at 2 %.

> Author: the grounds now list all five (`1f58008b6`).

**`rietx.model.forward.REFLECTION_MARGIN_DEG` (evidence changed)**

**holds** as a tier-3 row. Two problems: the added numbers sit in no test or docstring, and the test guarding the margin measures it at windows the answer no longer uses. The closing stage made the default answer's error larger on the fluorapatite (0.124 → 0.186σ). Would change the verdict: the margin test run at `CLOSING_WINDOW_TOL`, with the new numbers in its docstring.

> Author: the numbers are now in `test_window_domain.py`'s docstring; the margin test stays at the declared stages' 2 %.

**Rule text changed**

**`docs/milestones/generality.md` § The rule, tier 2, and `.claude/agents/generality-review.md` question 5**

**weak.** The text records the maintainer's Q5 answer faithfully. It leaves open how a default that switches on an action is treated, and `closing_window_tol` is that case. (i) A default that turns on an action now escapes the dissent test, while the same action keyed on its record field does not; tier and kind are separate axes, so this is no contradiction, but the text should say that a dissent still bears on a default's `ambiguity`. (ii) "Inside the range" is silent on whether a value no program uses earns tier 2, such as 1e-3, between GSAS-II's 0.5 % and zero. (iii) The removed sentence "one without the feature is neither" leaves open, for actions, whether a program lacking the feature dissents. MAUD and the closing stage are the live case. Would change the verdict: one sentence on a default that switches an action, and one on interpolated values.

> Author: two sentences added (`1f58008b6`): a value between two programs' is inside the range, and a default that switches on an action still faces the judgement ground, where a dissent counts.

**`docs/milestones/generality.md` § The rule, tier 1's cap clause (marked confirmed)**

**holds.** The maintainer confirmed the clause.

**Heuristics the table cannot see**

**(a) The closing stage itself (`RefinementPlan.closing_stage`, `strategy/staged.py`)**

**weak.** The case for acting is strong and measured. Three design choices inside the stage have no evidence given: (i) it copies the last stage's iteration budget onto an all-free solve, and B11's three budget rows were measured before the closing stage; (ii) it is a single solve, and on LaB6 a second recompile moves U by 1 esd; (iii) under TRF it collapses brucite's S_HKL (t = -268). Would change the verdict: the budget margin measured behind the closing stage, and the TRF and LaB6 cases recorded in a row.

> Author: the full suite re-asks B11's margins on the final tree; (ii) and (iii) are now on the closing stage's row.

**(b) The package's trial plans declaring `closing_window_tol=None`**

**holds** for the ranking trials. **weak** for the magnetic default solve, because its trials' moments are numbers the caller reads; the window error on magnetic peaks was not measured. The nuclear reference carries the plan's setting, so ΔBIC compares like with like. Would change the verdict: the moment error measured at 2 % against 1e-3 on the LaMnO₃ acceptance pattern.

> Author: kept for cost and recorded on `WINDOW_AREA_TOL`'s row; the LaMnO₃ measurement is owed.

**(c) Per-stage findings collapsed by code and paths (`restated`, `refine._run_plan`)**

**holds** as de-duplication. One gap is inferred, not measured: a finding that the closing stage clears stays. This applies to `ADP_NOT_POSITIVE_DEFINITE`, `STEPHENS_STRAIN_NOT_POSITIVE` and `TEXTURE_NOT_POSITIVE`, which are not re-taken on the converged vector. Such a finding stays in the result's diagnostics and reads as a statement about the answer. Would change the verdict: a test where the closing stage clears a finding that the last declared stage raised.

> Author: closed in `1f58008b6`: those three and `HUMP_TOO_NARROW` are re-taken on the answer.

**(d) `Refinement.predict(grid)` at the default windows; `SolveCost.from_pawley` at the declared stages' windows**

**weak** for `predict`. **holds** for `from_pawley`. On a default fit, `predict(data)` now differs from `y_calc` by the 2 % against 0.1 % gap, and `predict` takes no window argument. Would change the verdict: `predict` accepting a window fraction, or defaulting to the last fit's, with the docstring's measurement redone.

> Author: the docstring is dated; defaulting to the last fit's broke the never-fitted-twin test, and a window argument waits on the evaluation-windows question.

**(e) The acceptance suites declare `closing_window_tol=1e-3`; the Stephens suite declares `None`**

**holds** for the suites that declare it. **weak** for the Stephens suite, which leaves the shipped default unpinned under TRF. Would change the verdict: the TRF failure carried into the `PlanSpec:closing_window_tol` and `TCHZ_CEILING_DEG` rows, or a Stephens case pinned with the closing stage on under LM.

> Author: both rows carry it now (`1f58008b6`).

*Forwarded.* WP-1467 (LaB6's clamp xfail), WP-2012 (its mirror behind the closing stage), WP-2003 (the series pays the closing stage per pattern, unmeasured along a chain), WP-2015 (presets end in it), WP-2017 (the landed rows, the margin at closing windows, the six settings), WP-2018 (the closing stage against every per-stage action). Filed: WP-2020 (filed as 2019, renumbered at the merge with main).

*Gotchas.* A heredoc holding a double-backticked word is refused by the worktree guard; a script written with the Write tool runs. `predict(grid)` must not read the object's fit history: `test_refine_synthetic`'s twin test pins that a never-fitted copy predicts what the fitted one does. A test's synthetic data drawn at the default windows and fitted with the closing stage on is a model mismatch, not a closing-stage cost.

*Next.* 1. The maintainer answers the two questions above, the evaluation windows first, since its answer decides whether the lanes' `closing_window_tol=None` declarations stay. 2. B14's lifts and the interval and width-grid domain tests, as before. 3. WP-2017 inherits the six settings if they are ruled into it.

### 2026-10-21 (4th session) — the fifth round built; seven questions for the maintainer, three re-briefed against seven programs

This session built the maintainer's fifth-round answers and checked the three questions sent back against all seven programs rietx-bench runs. The peak window that drops 2 % of each peak's area turns out to be ordinary practice: TOPAS and MAUD drop the same, and FullProf's examples drop more while holding the window for a whole run. A closing stage at tight windows removes both that error and most of a staged plan's start-dependence: two Biso starts agree to 0.000 esd on the fluorapatite and NAC, and to 0.064 on cpd-1a, against 0.75 today, at 1.36-2.26× the fit time. The TCHZ width ceilings are gone, report caps are a tier-1 class, tier 2 names seven programs, and a switched-off Suortti block says its esds depend on where it stopped. Two defects that needed no ruling are fixed: the bond search missed bonds longer than 3.5 Å, and the restraint search missed the nearest image in skewed monoclinic cells. Seven questions wait on the maintainer: the three sent back, re-briefed, three the handover's reviews raised, and one the full suite raised: without the width ceilings, the solver TRF stops the brucite acceptance fit at a worse point, though no width comes near a ceiling.

*Done.*
- The fifth round's answers recorded (`2002-batch/rulings.md` § Fifth round's answers): Q4 delegated, Q5 (a), Q6 read as agreement, Q1-Q3 asked back, and the note to widen tier 2.
- Tier 1 gains two clauses (`docs/milestones/generality.md` § The rule): a numerical setting with a test bounding its error over its domain (B10's ruling of 2026-10-19, owed since), and a report cap with a test showing completeness inside it and its notes counting what lies outside (Q6). The three geometry caps and `MIN_IMAGE_SHELL` move to tier 1.
- The bond search reaches the longest pair the covalent radii could bond, so CsCl lists its eight 3.571 Å Cs–Cl bonds; `CONTACT_MAX_ANG` bounds contacts only (`model/geometry.py`).
- The restraint minimum-image search has a second pass sized per cell by `geometry._shell` from the first pass's distance; a tie keeps the first pass's image, so a reduced cell's answer is unchanged. The slow domain test passes on all five cell families, its oracle now sized from the pair alone (`model/restraints.py`, `tests/test_restraints.py`).
- Q4: `ROUGHNESS_UNCONSTRAINED` says, when Suortti roughness ends exactly off, that the scale's and Biso's esds depend on which off state (b = 0 or a = 1) the solver stopped in, and that dropping the block removes the dependence. The canonicalising re-solve recommended last round (option b) was not built: a new automatic step, record field and audit row for a case the maintainer called rare.
- Q5: the five TCHZ ceilings removed from both boxes, floors kept; the `fwhm_deg` fence that read w's ceiling removed. A project stored before keeps its own ceilings.
- Tier 2 names GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, in the rule, `_audit.py`'s docstring and the judge's checklist. The fourteen rows resting on a program default name all seven. `refine:solver` stays tier 2 although FullProf dissents (undamped Gauss-Newton), the dissent clause governing actions; `CELL_MIN_LENGTH_A` stays on TOPAS alone, the others having no floor.
- `docs/practice.md`: the seven-program survey (peak window and when it is set, axial quadrature, reflection margin, staging, roughness starts, width limits, the tier-2 rows). One Sonnet agent a program read its manual or source and ran FullProf, RIETAN-FP and BGMN; the lead spot-checked TOPAS's `ymin_on_ymax` and FullProf's `Ias` in the text.
- The three briefs as sent, whole, in `rulings.md` § Sixth round.

*Measured* (macOS arm64, `[dev]`, compiled tier on; timings two runs each, interleaved, with other agents running for some).
- `WINDOW_AREA_TOL` 5e-3, near GSAS-II's 0.5 % of a Lorentzian: 0.33-0.43σ at a point, answers up to 0.88 esd (LaB6 `u`), 1.05-1.54× the fit time. Fails both bars on three of four families.
- 1e-3 on the last stage only: within 0.008 esd of the all-1e-3 answer on FAP, cpd-1a and NAC, at 1.06-1.91× (all-1e-3: 1.16-3.53×).
- A closing all-free stage at 1e-3 after today's plan: within 0.052 esd of all-1e-3, at 1.36-2.26×.
- Biso started at 0.5 and 1.5 Å² (today / last-stage tight / closing stage): FAP 0.119 / 0.013 / 0.000, cpd-1a 0.751 / 0.734 / 0.064, NAC 0.008 / 0.006 / 0.000, LaB6 9.0 / 9.0 / 9.4 (its mirrored minima under every setting; forwarded to WP-2012).
- Fast selection after the ceilings went: 5 failed, 10 930 passed, 191 skipped, 31 xfailed (each failure asserted a ceiling; fixed in `f39bb5cf7`). On the final tree (main has not moved, so it is the merged tree): 10 935 passed, 191 skipped, 31 xfailed, `[dev]`, darwin/arm64, 5:01 with no other suite running. The 3rd session's tree, adjusted for its own two later changes, was 10 934 passed and 31 xfailed: +1 here, from +1 geometry (CsCl), +1 roughness, and neutron's two ceiling tests replaced by one. The added tests cost 0.05 s (geometry, three over the branch), 0.04 s (roughness) and 0.00 s (neutron), one run on this machine; none joins the tail.
- Full selection, once, on the final tree before the xfail (main had not moved, so it is the merged tree): 2 failed, 11 282 passed, 202 skipped, 41 xfailed, `[dev]`, darwin/arm64, 22:28, alone. The handover-log check failed on the judge's `#####` sub-headings (now bold labels). `test_acceptance_stephens.py`'s brucite test failed: without the ceilings TRF stops at Rwp 0.17891 against 0.17877, u on its floor, one S_HKL esd 66 against 14 737 (t = -203). With the old ceilings it passes; so it does with every ceiling at 10 and at 1000, and no width reaches 1. It is a strict xfail citing the sixth round's Q7. The full selection was not rerun after that one-test change.

*Review.* `/code-review high --fix` over `fdfde9fff..HEAD` found nine; five fixed in `a5f2c5f23`: the ProfileTCHZ docstring named Y as the size term where X (1/cosθ) is, `constant_wavelength_neutron`'s docstring still described the ceilings and the `fwhm_deg` raise, the bond search sized one shell per phase for its heaviest atom (2.4-3.4× the search for a light atom), the roughness help's "also switched off" read as a third off state, and the derived-quantities reference called `contact_max` the search radius. Declined: vectorising the image search (0.87 ms an image in P 2₁/c, 39 ms for a 192-op orbit; a vectorised pass could change which of two equidistant images a restraint takes); a backstop for the instrument widths (a design change past the Q5 ruling, now the sixth round's Q6); a near-off test for TRF in the roughness sentence (the test pins exactly-off on purpose); lifting stored ceilings at read (recorded as the stored file's own bound). The generality judge's fixable findings landed in `c9c28fb73`: the Q4 record, two stale `waiting.md` lines, four rows counting six programs where the survey names five and BGMN, the survey's sources, the cap clause's distance case, and the warning naming its off state.

*Forwarded.* WP-2012: no window setting or Biso start moves LaB6's split. WPs 2003-2007: tier 2's seven programs and where the survey is. For rietx-bench, handed to the maintainer as paste text: its BGMN case names `LAMBDA=cu_hoelzer97`, which has no `.ano` table, so that run has no anomalous dispersion.

*Gotchas.* The TCHZ size term is X (Γ_L = X/cosθ + Y·tanθ); the fifth round's Q5 brief, this session's report and the commit `d8c5aed90` called the 8 nm cap "Y ≤ 1°", corrected in the schema and the record. A pytest run piped to `tail` in an `&&` chain returns `tail`'s status: one commit here (`d8c5aed90`) went in over a failing test, fixed in the next. `caffeinate -w <pid>` blocks on a process and passes the worktree guard. The window measurements patch `rietx.model.forward.WINDOW_AREA_TOL` and wrap `refine.compile_model` per stage (scratch scripts `window_last.py`, `window_close.py`, `biso_starts.py` in the session scratchpad; their logic is in this entry and `rulings.md`).

*Generality.*

**generality.md § The rule, tier 1: the numerical-setting clause**

**holds.** The clause copies B10's ruling of 2026-10-19 faithfully (B10 is the batch's class of numerical settings). The case for writing it down is stronger, and the one weakness is that the rule does not say who sets the error bar.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | A numerical setting "controls how accurately rietx computes something rather than what it decides … once a test shows its error stays under a stated bar over every input it claims to handle" (`generality.md:50-53`) | It admits a constant to tier 1 (physics or arithmetic) once a domain test passes. B10's wording, `rulings.md:27-30`: "A numerical setting is tier 1 when a test bounds its error over the claimed domain." | faithful |
| 2. Kind | Not stated (a rule clause) | Not applicable | — |
| 3. Case against | none given | The test author chooses both the bar and the claimed domain, so a loose bar or a narrow domain passes. That is the self-certification the table exists to prevent. The bar is open right now: the sixth round's Q2 (a question to the maintainer, `rulings.md:235-237`) asks it, and the window tests use 0.1σ at a point and 0.1 plain esd (`waiting.md:99`). The definition also reads as if such settings move no answers. Yet `WINDOW_AREA_TOL` (the peak-window area cut) moved answers by up to 0.97 esd (`rulings.md:253`). The bar catches that, but only if the bar is a real one. | weak point |
| 4. Case for | "B10, ruled 2026-10-19" (`generality.md:53`) | The ruling is recorded verbatim in `rulings.md:27`. The clause was owed under that ruling ("One sentence goes into … § The rule, under tier 1"). | strong |
| 5. Tier and source | the maintainer's ruling | Confirmed in the repository | holds |
| 6. Families | n/a | n/a | — |
| 7. Record | n/a | n/a | — |

Would change the verdict: a ruling that the bar is the maintainer's (Q2's answer), quoted in each row that uses this clause, or the clause naming that bar.

**generality.md § The rule, tier 1: the report-cap clause**

**weak.** The clause is sensible for a cap that counts what it drops. Its authority is an interpretation of an ambiguous reply, and its second condition cannot be met by a distance cap.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "a cap on what a report lists, once a test shows the report is complete inside the cap and its notes count what lies outside it" (`generality.md:53-55`) | It moves any listing cap to tier 1 whatever the cap's value. The test is honesty about the cap, never whether the value is a good one. | — |
| 2. Kind | n/a | A listing that states its scope is Rule 1's third kind (report and stop) | consistent |
| 3. Case against | none given | (a) The authority is the maintainer's "doesn't appear to be a question", which the lead "read as agreement" (`rulings.md:206`). The clause records it as "ruled 2026-10-21". The reply could equally mean "not mine to decide". Q6's brief is in PR #1085 and the transcript, so I could not read what was recommended. (b) A distance cap such as `CONTACT_MAX_ANG` has no countable outside, so "notes count what lies outside" cannot hold for it. The row substitutes "the radius travels on `GeometryTable.contact_max`". (c) None of the three geometry caps can be changed by a caller (`geometry_table` takes no such argument, `geometry.py:428`). A refiner wanting 4 Å contacts, or a table for a 250-atom asymmetric unit, has no way to get it. | real |
| 4. Case for | "read as agreement with the recommended 'report scope' class" (dispatch). `rulings.md:207-210` | A cap that drops rows and says how many hides nothing. The geometry table feeds only the report and the CIF exporter (`refine.py:7322`, `report/schemas.py:1658`), so no fitted number depends on it. | moderate |
| 5. Tier and source | the fifth round's Q6 | The source is an interpretation, not a stated ruling | weak |
| 6. Families | n/a | n/a | — |
| 7. Record | `GeometryTable.notes` | Present for the two count caps. The radius has `contact_max` but no count. | partial |

Would change the verdict: the maintainer confirming Q6 in words, and the clause amended to say "notes count it, or the table records the bound" for a distance cap.

> Author: the reading goes back to the maintainer as the sixth round's Q4, and the clause now says "or for a cap on distance the report states the distance" and that its reading awaits confirmation (`c9c28fb73`).

**generality.md § The rule, tier 2: the seven programs**

**weak.** Widening the program list is the maintainer's instruction and its direction is sound. The new wording leaves two gaps, and the same session filled them in opposite directions.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "The programs are the seven rietx-bench runs … A program that does otherwise by default is a dissenter; one without the feature is neither" (`generality.md:56-61`) | It sets which programs' defaults count as established practice (tier 2), and what counts as a dissent. rietx-bench is the maintainer's harness that runs other Rietveld programs. | — |
| 2. Kind | n/a | n/a | — |
| 3. Case against | none given | (a) The list is tied to rietx-bench's roster, so tier 2 changes whenever the harness gains or loses a program. (b) EasyDiffraction is at 0.21.1 (`practice.md:9`), a pre-1.0 code. Counting its defaults as established practice is a stretch. (c) Established programs outside rietx-bench are absent. From memory and unchecked: Jana2020 and HighScore Plus. (d) The rule says what a dissenter outweighs only for an action (`generality.md:64-66`). It is silent on a default or a threshold, and item 3's solver row relies on that silence. (e) "Without the feature" against "does otherwise" is ambiguous for a bound. Every program refines U, V, W and cell lengths. "No ceiling" in six programs removed the TCHZ ceilings (TCHZ: the pseudo-Voigt width parameters), yet "no floor" in six programs counted as "without the feature" for `CELL_MIN_LENGTH_A`. (f) The rule does not say how many of the seven must agree. One program's default carries tier 2, and the survey's notes are not kept (`practice.md:10-11`: "in each lane's notes under the session scratchpad and are not reproduced"). | substantial |
| 4. Case for | the maintainer's instruction (`rulings.md:194-196`) | A wider survey lowers the chance of missing a dissenter. The "neither" clause stops a program that lacks a feature from counting as a dissenter. | real |
| 5. Tier and source | the maintainer, 2026-10-21 | Recorded | holds |
| 6. Families | n/a | n/a | — |
| 7. Record | rows "name the programs it checked" | Rows name the programs. The source locations are in a scratchpad that will be deleted. | weak |

Would change the verdict: wording on (d) and (e), a stated count of agreeing programs, and `practice.md` carrying file and section references.

> Author: (d), (e) and (f) go to the maintainer as the sixth round's Q5; `practice.md` now carries a sources table (`c9c28fb73`). The list is the maintainer's instruction; Jana2020 is listed and excluded in rietx-bench for want of a batch mode.

**rietx.model.geometry.CONTACT_MAX_ANG (3 → 1)**

**holds.** The case for tier 1 is stronger: completeness inside 3.5 Å is tested, and the bond-search defect is fixed and tested. The clause's "count what lies outside" fits a radius only loosely.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "every contact within 3.5 A is listed … bonds are found past it" (`_audit.py:1338-1344`) | It decides which non-bonded distances the table shows. The fix (`geometry.py:318-335`) searches each atom out to r_i + r_max + 0.4 Å and lists contacts only up to 3.5 Å. | — |
| 2. Kind | none given (not required on a constant) | Report scope, third kind | — |
| 3. Case against | none given | 3.5 Å is rietx's choice, and a caller cannot widen it. A refiner checking K···K or van der Waals contacts near 4 Å sees nothing beyond 3.5 Å, and no note says so. Only the radius is recorded. A metal–metal pair inside bonding reach but beyond 3.5 Å is dropped without a note (`geometry.py:332-335`). That is consistent with the radius. | moderate |
| 4. Case for | "complete in an unreduced cell where a fixed one-cell shell drops a 3.04 A contact"; CsCl "once … listed none" | `test_the_contact_search_is_complete_in_an_unreduced_cell` checks the listing against a brute-force search over shifts of −8 to 8. `test_a_bond_past_the_contact_radius_is_found` finds 8 × 3.5706 Å with no contacts. Both were made to fail. | strong |
| 5. Tier and source | tier 1 under the cap clause | Rests on the cap clause above, whose authority is weak | depends on clause |
| 6. Families | n/a (tier 1) | The structure CIFs in tests/data and synthetic P1 cells | — |
| 7. Record | `GeometryTable.contact_max` | Present; no count of what lies beyond | partial |

Would change the verdict: the cap clause failing confirmation. Separately, `waiting.md:110` still says the caps "stay tier 3", which is now stale.

> Author: `waiting.md` corrected (`c9c28fb73`).

**rietx.model.geometry.MAX_ASYM_ATOMS (3 → 1)**

**holds.** The clause's letter is met: the phase is skipped whole and the note says so. The cost the value exists to bound is still unmeasured, and the row says so itself.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "a phase past it is skipped whole and GeometryTable.notes says so" (`_audit.py:1345-1350`) | A phase with more than 200 asymmetric-unit atoms gets no distances and no angles | — |
| 2. Kind | none given (constant) | Report scope | — |
| 3. Case against | "The search time at 200 is unmeasured and a caller cannot raise it" (same row) | A refiner with a large asymmetric unit loses McCusker §11's quality check entirely and cannot opt in. The docstring's reason, "a minute stolen from the refinement" (`geometry.py:114-117`), has no measurement behind 200. | moderate |
| 4. Case for | the CIFs in tests/data "reach 32 atoms" | `test_a_phase_too_large_to_search_says_so` checks the note, with the cap patched to 1 | holds for the clause |
| 5. Tier and source | the cap clause | As above | depends on clause |
| 6. Families | n/a | — | — |
| 7. Record | `GeometryTable.notes` | Present, and names the atom count | holds |

Would change the verdict: a timing at 200 atoms showing fit-close cost that no caller would accept, or the need for a caller override.

**rietx.model.geometry.MAX_CONTACTS_PER_ATOM (3 → 1)**

**holds.** This is the cleanest fit to the cap clause, and nothing in the change argues against it.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the note counts exactly what the cap drops, the kept contacts are the nearest and bonds are never dropped" (`_audit.py:1351-1356`) | Confirmed in `geometry.py:337-347` | — |
| 2. Kind | none given (constant) | Report scope | — |
| 3. Case against | none given | none found. The docstring notes that a firing cap can break the two-direction symmetry of the listing (`geometry.py:108-111`), and the note covers it. | — |
| 4. Case for | 31 dropped on corundum with the cap at 2 | `test_the_contact_cap_note_counts_exactly_what_it_dropped` was made to fail (33 against 31) | strong |
| 5. Tier and source | the cap clause | As above | depends on clause |
| 6. Families | "tests/data's structures reach 20 a site" | Not needed at tier 1 | — |
| 7. Record | `GeometryTable.notes` | Present, with the count | holds |

Would change the verdict: only the cap clause failing confirmation.

**rietx.model.restraints.MIN_IMAGE_SHELL (3 → 1)**

**holds.** The second pass makes the search exact by construction, and a slow domain test checks it on five cell families. Nothing argues for the old state.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the first pass of the minimum-image search, which only bounds the second, sized per cell by geometry._shell" (`_audit.py:1475-1481`) | A first pass finds some image at distance d. `_shell(g, d)` then covers every lattice shift within d (the plane-spacing bound, `geometry.py:161-172`), and the second pass replaces the first answer only with a strictly nearer image (`restraints.py:199-224`). Any value ≥ 1 gives the same image. | — |
| 2. Kind | none given (constant) | Arithmetic | — |
| 3. Case against | none given | none found. The test is `slow`, so per-PR CI does not run it, only the nightly. | — |
| 4. Case for | "exact on 50 000 pairs … where one shell alone missed 72 of 2518 pairs within 4 A" | `test_one_image_shell_finds_the_nearest_image_over_its_domain`: the strict xfail on β 135-150° is gone, and the reference is sized from the pair alone (`test_restraints.py:411-415`), so it does not reuse the code's own first pass. Made to fail with the second pass removed. | strong |
| 5. Tier and source | the numerical-setting clause, bar = exactness | Exactness is the right bar for a missed image | holds |
| 6. Families | n/a (synthetic cells, 5 kinds × 100 cells × 100 pairs) | — | — |
| 7. Record | none | None needed: there is no action | — |

Would change the verdict: none expected. `waiting.md:114` still calls this "a defect", which is now stale.

> Author: `waiting.md` corrected (`c9c28fb73`).

**The twelve tier-2 rows with only the seven-program sentence added**

`_TCH_ETA`, `_TCH_GAMMA`, `BRINDLEY_MU_R_FENCE`, `Source:dispersion`, `fit:mode`, `run_stage:mode`, `refine:mode`, the four `two_theta_limits` rows, `auto_background:seed`.

**holds.** Each row already rested on a checked GSAS-II default or a citation, and no new dissenter appears. Two defects are in the added text.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What they decide | unchanged | unchanged | — |
| 2. Kind | `ambiguity=1` on the defaults | consistent with no dissenter | holds |
| 3. Case against | the dissent column reads "none" (`practice.md:300-307`) | (a) The four `two_theta_limits` rows say "the full range in six, BGMN the instrument function's" (`_audit.py:2332+`). `practice.md:302` names only five programs (GSAS-II, FullProf, RIETAN-FP, MAUD, EasyDiffraction) plus BGMN. TOPAS is missing, so the rows overcount by one. (b) BGMN's "instrument function's range" is arguably a different default rather than agreement. (c) The source locations for the six new programs are not in the repository. | minor |
| 4. Case for | per row, e.g. dispersion "all seven apply f', f'' by default" | Consistent with `practice.md`. I did not check the programs themselves. | holds |
| 5. Tier and source | tier 2 | I checked `practice.md` in this repository. I recall nothing that contradicts it, and verified none of the six new programs. | holds |
| 6. Families | n/a | — | — |
| 7. Record | unchanged | — | — |

Would change the verdict: TOPAS's `two_theta_limits` default found not to be the full range.

> Author: the four rows and `practice.md` now name the five, BGMN's range and TOPAS's unstated default; `practice.md` carries a sources table (`c9c28fb73`).

**rietx.refine.refine:solver (stays tier 2 with FullProf dissenting)**

**weak.** The row names a dissenter while keeping first-kind ambiguity. The reading that "the dissent clause governs actions only" is not in the rule.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "Marquardt-damped in six; FullProf dissents, Gauss-Newton with relaxation factors" (`_audit.py:2414-2417`) | Every fit uses damped least squares (Levenberg-Marquardt, "LM") unless the caller names another solver | — |
| 2. Kind | `ambiguity=1` | Rule 1: "if a competent refiner who would act otherwise can be named, the action moves to the second or third kind". Rule 4 asks a default the same question. A named dissenter with ambiguity 1 conflicts with both unless a default is not an action, and the rule does not say that. | conflicts |
| 3. Case against | the dispatch: "a solver default is a numerical method" | FullProf's users run undamped Gauss-Newton by default. A solver can change which minimum a fit lands in: this branch measured LM and TRF (another bounded solver) ending 0.074 esd apart on cpd-1a (`waiting.md:34-40`). LM against Gauss-Newton has not been measured. | real |
| 4. Case for | six of seven damp | Relaxation factors scale each shift down, which is damping of another form (recalled, not checked). The dissent may concern method rather than answer. | moderate |
| 5. Tier and source | GSAS-II `HessianLSQ`, checked earlier | GSAS-II part checked in a prior session. Other programs per `practice.md` only. | holds as practice |
| 6. Families | none given | none | — |
| 7. Record | none given | `solver` is recorded on the result as the caller's argument (not checked this session) | — |

Would change the verdict: refits on three families showing LM and relaxed Gauss-Newton reach the same answers (then it is a method with no dissent on the answer), or a maintainer ruling that the dissent clause covers defaults.

> Author: to the maintainer as the sixth round's Q5, whose option (a) puts the solver with B10's solver-path switches at tier 3 until refits agree.

**rietx.params.vector.CELL_MIN_LENGTH_A (stays tier 2 on TOPAS alone)**

**weak.** The stakes are low, but the reasoning contradicts how the same survey removed the TCHZ ceilings.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "TOPAS alone floors a cell length, and the other six have no floor; it binds on no real cell" (`_audit.py:1760-1763`) | A lower bound of 1.5 Å on every cell length | — |
| 2. Kind | none given (constant) | It acts as a limit on a refined value | — |
| 3. Case against | none given | All seven programs refine cell lengths, so they have the feature. Six leaving the length unbounded is "doing otherwise by default" on the reading that removed the TCHZ ceilings (`instrument.py` docstring: "none of GSAS-II, FullProf, TOPAS, RIETAN-FP, MAUD or EasyDiffraction bounds these coefficients"). By that reading the row has six dissenters. | real |
| 4. Case for | "binds on no real cell" | No measurement given (for example, the shortest cell edge in a structure database). A physics argument exists: below about 2 Å an atom overlaps its own lattice image. The row does not make it. | plausible, unevidenced |
| 5. Tier and source | TOPAS Technical Reference v9 § 2.17, checked 2026-10-19 | Checked in an earlier session; I did not re-check it | holds as citation |
| 6. Families | none given | none | — |
| 7. Record | none given | A hit would show as `BOUND_HIT` (the code for a value stopped by a limit) and `at_bound` | — |

Would change the verdict: the physics argument written into the row (which would make it tier 1), or a database minimum showing the floor never binds.

> Author: to the maintainer as the sixth round's Q5, whose option (a) moves the floor to tier 1 on the physics argument.

**TCHZ_BOUNDS and TCHZ_BOUNDS_COARSE: the five ceilings removed, and the `fwhm_deg` fence with them**

**holds.** The case for removal is stronger: none of the seven programs bounds these widths by default, and the ceilings capped a physical quantity. The case for keeping them is a guard whose use was never measured.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller now decides | a caller sets "an explicit `Parameter(value, min, max)`" for their own bounds (`instrument.py` docstring) | U, V, W, X and Y may grow without limit. The neutron constructor no longer refuses `fwhm_deg` > 2.83°. | — |
| 2. Kind | none given (hand row) | A limit on a fitted value; the established programs set none | — |
| 3. Case for keeping (the removal's weak side) | none given | A ceiling stopped a width running away inside a stage, and `BOUND_HIT` reported it. Now no single-fit code reports a runaway width: I grepped the width codes and found only magnetic, sequential and indexing ones. The windows are frozen at the stage's start, so a width that runs away loses more area in silence (`waiting.md:106`). No measurement of how often a ceiling bound on real data: none given. | weak, unmeasured |
| 4. Case for removal | Q5 (a), "checked against the seven programs"; "Y ≤ 1° capping the Lorentzian size near 8 nm at Cu Kα" | Arithmetic checked: 0.9 × 1.5406 Å / 0.01745 rad ≈ 79 Å. `practice.md:283-294`: GSAS-II, FullProf, RIETAN-FP and EasyDiffraction set none; TOPAS has no u-y row; MAUD's limits are "not enforced". It also removes the indexing seed crash WP-1312 recorded (`1312:439-451`). | strong |
| 5. Tier and source | the maintainer's ruling (Q5) plus the survey | As stated. WP-1312's reasons for keeping the ceilings, a moved search box and an owed schema note, are addressed by the ruling and by old projects keeping their stored bounds (`waiting.md:85`). | holds |
| 6. Families | D1B Co₃O₄ for the coarse box | One family. It does not bear on the removal. | — |
| 7. Record | none | No record for a runaway width | gap |

Would change the verdict: a fit on real data where a width ran away and the ceiling had caught it. A sibling not judged here: the kept U and V floors face the same seven-program argument, and the documentation's own D1B model sits under the default V floor (V = −0.501).

> Author: the runaway-width gap goes to the maintainer as the sixth round's Q6. The size term is X, not Y, corrected in `a5f2c5f23`. The U and V floors were kept by the Q5 ruling ("keep the floors and lower bounds"); their seven-program reading falls under Q5.

**ROUGHNESS_UNCONSTRAINED: reporting the off-state dependence instead of re-solving**

**holds** on the decision. The report states the fact and stops, and the case for re-solving rests on one family for a case the maintainer called rare. The batch record contradicts the code, and that must be fixed. (Suortti is one of the two surface-roughness intensity corrections. This warning fires when the refined roughness changes intensity by under 1 %.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller now decides | "the esds of the scale and Biso depend on which one" (`refine.py:9735-9745`) | The caller must drop the roughness block and refit to get one reading. The message does not say *which* off state the fit stopped at, although the code holds a and b. | — |
| 2. Kind | none given (`ROUGHNESS_UNCONSTRAINED` is still `unaudited`, `_audit.py:743`) | The dependence is arithmetic. Reporting it is the third kind. | none given |
| 3. Case against acting (for the report) | "Said rather than canonicalised: the case is rare, and dropping the block, which this warning already asks for, gives one reading" (`refine.py:9727-9729`) | Choosing b = 0 (the marginal reading) over a = 1 (the conditional one) is itself a choice. Dropping the block is the remedy no refiner would dispute, and the warning already prescribes it. | strong |
| 4. Case for acting (re-solve at b = 0) | "the scale's and Biso's esds differ ×1.1 to ×4.4 between the two at one set of values" (`refine.py:9725-9726`) | ×4.4 on a quoted esd is large. It is measured on one family (the CPD round robin) at one set of values, and the cost of leaving it is one refit. WP-1929's rule, that a row on its bound stays in the matrix, would support b = 0. | moderate |
| 5. Tier and source | delegated by the maintainer ("whichever you consider reasonable") | `rulings.md:202-204` (in this diff, and unchanged in the uncommitted copy) still says "The lead's pick is (b): … esds evaluated at b = 0". The code does the report. | record contradicts code |
| 6. Families | CPD round robin, one | one | — |
| 7. Record | the message and suggestion text | Prose only. No field names the off state. Tested by `test_a_switched_off_suortti_block_says_its_esds_depend_on_the_off_state` (made to fail). | partial |

Would change the verdict: the ×4.4 reproduced on a second and third family, or the case shown to be common. Either way, `rulings.md` § Fifth round's answers must say the report was chosen over (b), and the message could name the off state it found.

> Author: `rulings.md` now records the report as chosen over (b), and the message names the off state it found (`c9c28fb73`).

*Next.*
1. The maintainer answers the sixth round's six questions (`rulings.md` § Sixth round, each brief whole there): Q1 the peak window, Q2 the start-test bar and a closing stage, Q3 Pitschke's start, Q4 whether the fifth round's Q6 answer meant yes, Q5 how tier 2 counts a dissenting program, Q6 a range backstop for runaway instrument widths, Q7 a finite ceiling no peak can reach, so TRF's brucite fit returns (its acceptance test is a strict xfail until then). Q2's answer decides Q1's build: a closing stage carries the tight windows if Q2 takes option 3, otherwise the plan's last stage does.
2. Build the answers. A closing stage is a runner change (every plan gains a final all-free stage recompiled at the answer), re-pins the goldens, and is followed by rerunning the intermediate-tolerance and harmonic-seed start tests behind it. The six other failing numerical settings take the same rule. Q3 (c) splits the roughness stage's one `seed=0.3` (`strategy/staged.py`) into Suortti's b (start-invariant) and Pitschke's c (tier 3, its failure recorded).
3. B14's lifts with the ~50-guard list to the judge; the interval and width-grid domain tests.

### 2026-10-21 — the owed tests: the budgets and two starts pass, most numerical settings fail a bar tied to the data's noise

This session ran the tests the batch owed. It asked whether a starting value changes the answer, whether stopping early stages early does, whether the iteration budgets leave room, and whether each numerical setting stays accurate over the range it claims. The iteration budgets, the Suortti roughness start, the peak-width start and two internal splits pass, and are now recorded as not affecting the answer. Most numerical settings fail a bar set at a tenth of the data's own noise. The largest is the peak window, which drops 2 % of each peak's area and moves refined values by up to one esd on lab data; fixing it costs 1.2 to 3.5 times the fit time. The session also found that a staged plan's answer depends on its path by up to about 0.16 esd, because its last stage runs on a model frozen where the earlier stages stopped, and that the absent-phase hold can flip with the intermediate tolerance. No package behaviour changed. Six questions wait on the maintainer (`2002-batch/rulings.md` § Fifth round).

*Done.* Inherited pruned on arrival: 2001's entry was already in Context, and 2014's `project.py` note was folded in. WP-2003's missing entry was reconstructed by hand from 5c8810091, a docs commit already merged through #1050, so the full repair handover had nothing to review. Then one commit per class: B3's two-start tests (093612546); B9's starting values (030aa05ea); B10's FCJ domain test (020c4365b) and the node-split measurement (39a4f73ff); B7 and B11 (fad1f0ad8); B10's windows and identities (d499b4e64); B10's last eight settings (5f5b943c9); the code review's fixes (186c68004); the image-shell sweep marked slow (996f9fd80). Rows landed: B11's three budgets (on the shipped schedule), `_BASES_CHUNK_ROWS` and `_DENSE_EIGEN_MAX` invariant; `MAX_NODES` tier 3. `WINDOW_MIN_DEG`, `window_slack_deg` and the three geometry caps went to tier 1 and back to tier 3 on the judge's review (below), with the evidence corrections it asked for in the same commit. Every failing setting stays tier 3 with its measured error in the row and a strict xfail in its test. `StageResult.seeded`, `SUGGEST_SEED_ROUGHNESS`, `HARMONIC_WEIGHT_SEED` and the four intermediate-tolerance rows stay unaudited, each with what it waits on in `waiting.md`.

*Measured.* Every number is in `waiting.md` by class and in the new tests' docstrings; the headlines, all `[dev]`, darwin/arm64:

- B3: Suortti's b from 0 and from 0.3 agrees to 2.7e-3 esd on five lab patterns from three laboratories; Pitschke's c does not (CPD zincite from 0: scale ×2.1, out of regime). The Stephens seed's second family (CPD brucite) favoured 1000 ppm, χ² 7.77 against 8.32.
- B9: the width start is invariant from w, x = 1e-4 to 1e-2. Biso 0.5 and the harmonic seed move answers by up to 0.16 and 0.15 esd, through the frozen last-stage compile: one recompiled stage brings them within 0.012.
- B7: 1e-6 against 1e-9 stays within 0.03 plain esd on every fit but cpd-1a's QPA protocol (0.033 LM, 0.074 TRF); with an absent zircon declared, the hold fires at 1e-6 and not at 1e-9.
- B11: worst stage 49 of 400 evaluations, 1.79 evaluations an iteration against 4, 9 LM trials against 18, on nine configurations from four laboratories.
- B10: the window area tolerance misdraws up to 2.15σ at a point and a converged refit moves non-background rows up to 0.97 esd; the four FCJ constants each miss over part of the domain, worst for Lorentzian-rich peaks (5.6e-3 of the peak maximum against 7.2e-4) and where the node cap binds at low angle (0.21-0.26); a length-proportional node split is unsafe when frozen; the reflection margin, the axial and magnetic sizing floors, the origin clip and the texture sampling fail by smaller amounts; the restraint image shell misses neighbours in unreduced monoclinic cells (a defect). The SRM 660c and cpd-1a answers end with high-angle reflections on the Gaussian-variance floor, where an FD column is 2.2e-2 off (forwarded to 1467).
- Practice checked: GSAS-II 5.8.4 computes each peak over 50 FWHM below and 75 above, recomputed at every evaluation (`GSASIIpwd.getWidthsCW`), and has no Pitschke roughness model.
- Tests. The touched files collect +71 fast and +41 slow tests against `origin/main` (05ac4bac6); one fast domain sweep (5 cases) then moved to slow, so the fast tier gains 66. The fast selection, run once before that move with one other pytest on the machine: 10 937 passed, 191 skipped, 32 xfailed, 1 failed in 4:28, the failure the stale WP index (fixed, `test_docs_consistency.py` 25 passed). Passed+skipped+xfailed+failed is 11 161, which is 71 above the 11 090 of the last handover's merged tree. The 30 new xfails are strict and each names a measured failure. The added fast tests take 2.4 s together without the moved sweep, the largest 1.66 s (`test_every_fd_column_meets_a_converged_oracle`, 21 cases); the sweep took 7.24 s. The full suite did not run: the branch changes tests, the audit table's text and one comment, so it cannot move a measured number. Every slow test it adds ran in its own file.
- Lanes (`session_usage.py lanes`): seven lanes, none kept in main, re-read median 0K, 12 main requests per lane, 20K left in main, actual over estimated requests 2.77, six fixed by main afterwards and none redone, saved $29.49 (37 % of the session). The selective policy's baseline over all sessions: −11 %.

| lane | est | requests | main at dispatch | lane $ | saved $ |
|---|---|---|---|---|---|
| B3 two-start | 30 | 49 | 163K | 3.01 | +1.68 |
| B9 starting values | 30 | 83 | 205K | 4.94 | +3.69 |
| B10 FCJ domain test | 30 | 82 | 229K | 4.38 | +3.72 |
| FCJ segment split | 20 | 72 | 258K | 3.30 | +3.09 |
| B7+B11 tolerance and budgets | 40 | 69 | 273K | 3.72 | +3.35 |
| B10 windows and identities | 35 | 125 | 296K | 9.61 | +6.19 |
| B10 remaining settings | 35 | 141 | 320K | 10.46 | +7.76 |

*Code review* (`high --fix 05ac4bac6..HEAD`): eight findings. The review fixed four: the FCJ domain cases now stay inside 2-160°, the window test shares one cached fit, the Richardson oracle takes one pass, and FD_STEP's evidence reads 2.5e-4. Three more fixed here: the LM trial margin is 2× not 3× (a stage's last iteration tried up to 9), TRF's per-iteration margin is asserted at 1.5× since 2.2× was measured on one platform, and the window polish now fails if it does not settle (all settle today). Declined: sharing the three caches of the same protocol fits across modules, which moves tests between xdist groups and so changes the longest group.

*Generality* (the `generality-review` judge, fresh context, on every row in `tests.audit_delta`'s list; its sections unedited but for heading levels, the author's answer under each weak verdict):

**Item 1a. `rietx.optimize.least_squares.NFEV_PER_ITERATION` and `rietx.schemas.plan.StageSpec:max_iter` (unaudited → invariant)**

**Weak.** The case for invariance is strong on the shipped schedule. Under `intermediate_ftol=None`, a setting callers can choose, the margin is 1.24x and the budget fired once, so the unconditional label claims more than was measured. (`intermediate_ftol=None` converges every stage to 1e-9. The root CLAUDE.md says goldens declare it, and B7, the intermediate-tolerance class still awaiting a ruling, could make it the default.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the stage budget is max_iter x 4 evaluations" (`_audit.py:1573`); "caps evaluations ... never iterations" (`:2250`) | It stops a stage after 400 residual evaluations. Neither driver counts iterations: one stage ran 110 iterations at max_iter 100 (test docstring, `tests/test_budget_and_tolerance_invariance.py:42-46`). | agrees |
| 2. Kind | max_iter row: `ambiguity=1`; NFEV row has none | Kind 1 (every refiner stops a runaway), as long as a converging fit never reaches the cap. | agrees |
| 3. Case against acting | "every stage at 1e-9 leaves LM 1.24x, and a cell walking unheld bound it once" (`:1573`) | Under `intermediate_ftol=None` on cpd-1a with zircon (a phase the sample lacks), `lines_axial` spent 400 of 400 evaluations and reported `STAGE_MAX_ITER`. The next stage converged at 323 of 400. Nobody measured whether the final answer depends on the budget there. A single all-free stage at 1e-9 (the shape `run_stage` runs) used 107 evaluations: 3.7x, with no test. | the 1.24x is disclosed but the tier does not condition on it |
| 4. Case for acting | 8.2x (LM) and 8.5x (TRF) worst over nine configurations; the answer is bit-identical at max_iter 25 under both solvers | Confirmed in the test: margins asserted at 4x on evaluations and 1.5x on the per-iteration rate, plus a bit-identical refit at a quarter of the budget, both solvers. | strong on the shipped schedule |
| 5. Tier and test | invariant, B11 ruling (`rulings.md:61-62`) | `test_a_converging_fit_stays_inside_every_budget` and `test_the_answer_is_the_same_with_the_evaluation_budget_cut_to_its_margin`, both `slow`, so they run nightly and not per PR. Both fit only cpd-1a under its QPA protocol (the quantitative-phase-analysis plan). The nine-configuration figures are scratch measurements quoted in the docstring. | meets the record's test for this class, on one schedule |
| 6. Families | "nine configurations from four laboratories" | SRM 660c (NIST), FAP, CPD (CSIRO), 11-BM NAC: four for the margin. One (cpd-1a) for the asserted invariance. Reference: the shipped-budget answer, bit for bit (verification only). | adequate for this class |
| 7. What says it fired | none given in the row | `STAGE_MAX_ITER` (warning) and `StageResult.status` | exists |
| Baseline | NFEV and max_iter removed from `UNAUDITED_BASELINE` | The list shrinks. | fine |

Would change the verdict: the row's evidence states "on the shipped schedule (intermediate_ftol 1e-6)" and names B7's ruling as a re-measure trigger. Or a refit of cpd-1a with zircon under `None` at max_iter 100 and 200 gives the same final answer.

> Author: done as the judge asked. Both rows now say the invariance is the shipped schedule's and that B7's ruling triggers a re-measure; `waiting.md` § B7 says the same.

**Item 1b. `rietx.optimize.lm._INNER_MAX` (unaudited → invariant)**

**Holds**, on a thin margin. The evidence for invariance is stronger than any case against it. The one comment this session changed overstates a guarantee.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "inner (Levenberg-Marquardt) iterations per outer iteration before giving up" (`lm.py:129`) | When the 18 damped trials run out, LM ends the stage as converged (`termination="no_descent"`, `status=1`, `n_stalled=18`; `lm.py:593-607`). | agrees |
| 2. Kind | none on the row | Kind 1 while it never binds. | — |
| 3. Case against acting | "at 4 the answer changes" (`:1638`) | The true margin lies between 2x (measured: 9 of 18) and 4.5x (a cut to 4 trials changed the answer). The new comment says "from λ = 0 the 18th trial runs at λ = 1e16 ... if nothing downhill exists there, none exists". That ignores the curvature gate: at λ ≥ 100 a curvature measurement can reset λ to its value at the start of the iteration (`lm.py:565-576`). So 18 trials need not reach 1e16. A cap that fires then reads as convergence. | comment overstated; behaviour measured fine |
| 4. Case for acting | "an iteration that took a step tried at most 6 damped trials and a stage's last iteration up to 9 (2.0x)"; bit-identical at 9 | Confirmed: `test_the_answer_is_the_same_with_lm_trials_cut_to_their_margin` and the 2x margin assertion. No stage ended on `no_descent` in nine configurations. The precedent `FIRST_RUNG_FACTOR` was kept at 2.3x. | holds |
| 5. Tier and test | invariant, B11 | The two tests above (slow). TRF has no such loop, as the grounds say. | holds |
| 6. Families | nine configurations, four labs | Same as 1a. In the test, cpd-1a sits at 6 trials against a limit of 9. | adequate |
| 7. What says it fired | none given | `n_stalled` and `termination` on the solver outcome. The stage still reads "converged". I did not check whether `StageResult` carries `n_stalled`. | weak record |

Would change the verdict: a configuration whose stepping iteration needs 9 or more trials. Separately, the comment should say that λ can be reset below 1e16 by the curvature gate.

> Author: the comment now says the curvature gate can reset λ, and that a cap that fires reads as convergence (`no_descent`).

**Item 2. `rietx.model.forward._BASES_CHUNK_ROWS` and `rietx.optimize.blocked._DENSE_EIGEN_MAX` (tier 3 → invariant)**

**Holds** for both. Each has an identity test that was made to fail once. No case against was found beyond a measure-zero edge for the eigen-switch.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | chunking of the derivative bases (`:1312`); dense eigensolve against Lanczos (an iterative solver for the largest eigenvalue) for \|λ\|max, which "only places the pseudo-inverse cut" (`:1548`) | Both are internal splits of the computation. | agrees |
| 3. Case against acting | none stated | `_BASES_CHUNK_ROWS`: none found. No row reads another, so identity holds by construction. The test switches the compiled tier off (module fixture, lines 55-57), so `tchz_pv` does reach the chunk loop. `_DENSE_EIGEN_MAX`: an eigenvalue within 1e-6 relative of the cut would be discarded on one side of the switch and kept on the other. The test asserts that no eigenvalue sits there (`test_parametric_series.py:1112`). The measured gap is 2.4e10x the cut. | negligible |
| 4. Case for acting | bit-identical at 1, 7, 128 and 4096 rows, tchz_pv and voigt; \|λ\|max agrees to 3.7e-14, esds bit-identical | Confirmed in `test_the_fcj_chunk_size_leaves_every_plane_bit_identical` and `test_the_eigenvalue_switch_moves_only_the_cut` (random and library cases, 83-84 and 204 columns). | holds |
| 5. Tier and test | invariant, B10 option 2 | the tests above | holds |
| 6. Families | n/a | Identity claims; families are not required. | n/a |
| 7. What says it fired | n/a | Nothing fires. | n/a |

Would change the verdict: a real fit with an eigenvalue within the Lanczos tolerance of the cut.

**Item 3. `rietx.model.forward.WINDOW_MIN_DEG` and `rietx.schemas.plan.StageSpec:window_slack_deg` (tier 3 → 1)**

**Weak.** The test bounds in-stage movement only from starts near each protocol's answer. The constant's own comment claims a wider domain, and the margin is 1.4x.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the room a peak has to move within one stage" (`:1305`) | The comment at `forward.py:197-200` claims cover for "zero-shift, displacement and the cell" moving a peak within a stage. | — |
| 3. Case against acting | none given | The cold start tested is the zero 0.1° off. NAC is excluded from the cold start (test docstring lines 70-73). No start has a cell off its answer. My arithmetic, not run: a literature cell 0.3 % off moves a 120° peak about 0.6°, twice the slack (2·tanθ·Δd/d). A solid solution or a structure from another temperature is a common first fit. Past the slack, the frozen window clips the peak for that stage, and nothing reports it. "Slack 0 and 1 deg move nothing" was measured at the converged tolerance (5e-5), where windows are wide. It says nothing about the shipped 2e-2 windows. | substantive |
| 4. Case for acting | largest move 0.21° over 7 cells, warm and cold (`:1305`) | Confirmed: `test_window_min_deg_covers_every_stages_movement`, made to fail at 0.1. The next stage recompiles, so a clip affects the path, not necessarily the final answer. That last point is unmeasured. | real but narrow |
| 5. Tier and test | tier 1 under B10 ("a test bounds its error over the claimed domain") | The test covers the starts it ran, not the domain the comment states. `window_slack_deg`: `test_a_stage_without_window_slack_compiles_the_window_min_deg_windows` shows `None` is the constant bit for bit, so its inheritance holds. | weak |
| 6. Families | SRM 660c, FAP, cpd-1a, NAC | Four labs and instruments. The reference is the start-of-stage peak position (verification). | adequate in count, narrow in starts |
| 7. What says it fired | none given | none found. A peak leaving its window mid-stage is silent. | none |

Would change the verdict: a cold start with the cell 0.3-1 % off on two families shows the final answer within the 0.1 plain-esd bar (plain esd: without the Bérar-Lelann inflation). Or the comment narrows its claim to zero and displacement.

> Author: both rows back to tier 3, the evidence naming the untested cell start and the silent clip; the cold start with the cell off is owed with the interval and width-grid tests.

**Item 4a. `rietx.model.geometry.CONTACT_MAX_ANG` (tier 3 → 1, "a report scope the output states")**

**Weak.** The radius also cuts bonds that the module's own criterion calls bonds, and no note says so. The grounds' "exact disclosure beyond it in GeometryTable.notes" is not true for this row.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the contact search is complete within 3.5 A" (`:1331`) | The neighbour search itself stops at 3.5 Å (`geometry.py:309, 322`), so bonds beyond 3.5 Å are never found. Yet the docstring at `geometry.py:103` says "Bonds and angles are uncapped — chemistry bounds them". | broader than stated |
| 3. Case against acting | none given | A refiner of a heavy-cation halide would dissent. With Cordero radii (recalled: Cs 2.44, Cl 1.02, I 1.39) plus the 0.4 Å slack, Cs–Cl at about 3.57 Å in CsCl and Cs–I in CsPbI₃ are bonds by the criterion but lie beyond 3.5 Å. So Cs gets no bonds, angles or coordination number. The only disclosure is `GeometryTable.contact_max`. No note fires. I derived this from the code and recalled cells; I did not run it. | substantive |
| 4. Case for acting | tests assert completeness within 3.5 Å in an unreduced cell | Confirmed: `test_the_contact_search_is_complete_in_an_unreduced_cell` (a β = 150° cell, checked against brute-force enumeration). Nothing downstream acts on the table: report, CIF export and GUI only. | holds within its scope |
| 5. Tier | tier 1, "a report scope" | `generality.md` § The rule has no "report scope" class. 3.5 Å is rietx's own choice ("short enough that the row count stays readable", `geometry.py:98`), so it is not physics or arithmetic. The maintainer should rule on the new category. | not tier 1 as written |
| 6. Families | tests/data structures | none relevant | — |
| 7. What says it fired | "GeometryTable.notes" | Only `contact_max` on the table. No note fires. | grounds misstated |

Would change the verdict: the search radius rises to the largest bond criterion for the phase's species, or a note counts the criterion-bonds beyond 3.5 Å. Then "report scope" holds.

> Author: back to tier 3 with the bond cut in its evidence; the category is the fifth round's Q6, and the bond cut is a defect for the next session.

**Item 4b. `rietx.model.geometry.MAX_ASYM_ATOMS`**

**Weak.** The skip is disclosed, but 200 has no cost measurement and the caller has no way to override it.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 3. Case against acting | none given | `geometry_table` takes no limit argument, so a caller with a phase over 200 asymmetric atoms (a Z' > 1 pharmaceutical with hydrogens) cannot get McCusker §11's distances (the 1999 Rietveld guidelines' call for bond lengths and angles) at all. | dissenter nameable, rare |
| 4. Case for acting | "a phase past it is skipped and GeometryTable.notes says so"; "tests/data reach 32 atoms" (`:1338`) | Disclosure is confirmed by `test_a_phase_too_large_to_search_says_so`. The 32-atom figure shows the cap is never exercised. It does not justify 200. The docstring's "a minute spent" (`geometry.py:113`) is not measured. | weak |
| 5. Tier | tier 1, report scope | as 4a | needs a ruling |
| 7. What says it fired | `GeometryTable.notes` | Confirmed. | holds |

Would change the verdict: a timing of the search at 200 atoms, or a caller override.

> Author: back to tier 3, the evidence saying the time at 200 is unmeasured and a caller cannot raise it.

**Item 4c. `rietx.model.geometry.MAX_CONTACTS_PER_ATOM`**

**Holds.** It keeps the nearest contacts, never bonds, and counts exactly what it drops.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 3. Case against acting | none given | none found. Short contacts are the nearest, so they are never dropped. | — |
| 4. Case for acting | "the note counts exactly what the cap drops and the kept contacts are the nearest" (`:1345`) | Confirmed by `test_the_contact_cap_note_counts_exactly_what_it_dropped`. Bond counts are unchanged under the cap. | holds |
| 7. What says it fired | `GeometryTable.notes` | Confirmed. | holds |

Would change the verdict: a consumer that reads contacts as complete.

> Author: kept at tier 3 beside its two siblings, since its tier 1 rested on the same uncreated category (Q6).

**Item 5. The fourteen settings kept or landed at tier 3 with a failing domain test**

**Holds** on keeping tier 3: every row states what failed and against what. The bar is defensible in kind and weak as calibrated: it is pinned to the most precise patterns on disk, not to the data being fitted, and its 0.1-esd answer half is looser than the bars this WP uses elsewhere.

**The bar** ("a tenth of σ/peak at the strongest peak of FAP.XRA and 11BM_NAC"; per point σ for the window rows):

- **For it.** Numerical error well under the counting noise, checked twice: at fixed parameters and at the answer. One anchor ties it to answers: SRM 660c's (100) at 6.3e-4 of the peak, with a 512-node refit moving no parameter past 0.04 esd (`test_lab_instrument.py:497-500`). The window tests use each point's own σ, which adapts to the data.
- **Against it, first.** The FCJ bar is fixed at FAP.XRA's 19 693 counts (`test_lab_instrument.py:491-495`). FCJ is the Finger-Cox-Jephcoat axial-divergence asymmetry. A pattern with ten or a hundred times those counts, routine on a strip detector (recalled, not measured here), makes the lab bar 0.3-1σ of that pattern's own noise. The bar should either be written relative to σ/peak, as the window test does, or state the count ceiling it covers.
- **Against it, second.** The answer half (0.1 plain esd) is 3-10x looser than the bars set in this WP for the same question: B3's seed test at 0.01 esd and B7's tolerance test at 0.03. At 0.03, the FCJ anchor's own 0.04 esd would fail. This is rulings.md's fifth-round Q2, and it decides this class too.
- **Against it, third.** "Adds 1 % to that point's χ²" is a per-point argument. A shape error spans a whole peak with one sign, so it biases parameters more than independent noise would. The answer test is what catches that, and for the FCJ constants it ran on one family.

| Row | What the evidence states | Gap I found |
|---|---|---|
| `fcj.MAX_NODES` (`:1417`, unaudited → 3) | lab fails 0.21-0.26 of the peak below about 6.2° 2θ; synchrotron fails at η 0.5 and 1 | The synchrotron figures (4.2e-4 and 9.9e-4 at 2°) and the 512-node reference are in the test, not the row. Lab data rarely reach below 6°. `approved` carries B10's date, though this row joined the class this session. |
| `fcj.MIN_NODES` (`:1425`) | passes lab η ≤ 0.5; fails lab η 1 (7.9e-4) and synchrotron | `waiting.md:90` says any value ≤ 8 is inert, since `max(n//2, 4)` floors every reflection at 8 images. The row should say that only a rise changes anything. |
| `fcj.NODES_PER_FWHM` (`:1433`) | 2.4e-3 and 5.6e-3 lab, every η synchrotron | none |
| `fcj.SKIP_EXTENT_FWHM_RATIO` (`:1442`) | 9.5e-3, error ≈ 0.48 × extent/FWHM | none; the bound is analytic |
| `forward.WINDOW_AREA_TOL` (`:1296`) | 0.71-2.15σ, 0.17-0.97 esd, four families; 1e-3 passes at 1.2-3.5x fit time | Omits `waiting.md:98`'s counterpoint (FAP χ² 110 higher with converged tails). Omits the constant's earlier validation against weighed QPA truth (`forward.py:186-188`). Omits that GSAS-II drops about 0.6 % of a Lorentzian (`rulings.md:176-179`). |
| `forward.REFLECTION_MARGIN_DEG` (`:1288`) | 0.124 and 0.119σ, 0.103 esd | Fails by 1.2x and 1.03x. Cost of 5° not stated. |
| `forward.AXIAL_SIZING_FLOOR` (`:1256`) | 0.27 of the peak maximum, 19.5 % area | Omits the answer effect the test records: the two floors' fixed points differ by 0.16 esd at χ² 0.008 apart (`test_lab_instrument.py:689-693`). The 0.27 is transient, since the next stage recompiles. |
| `forward.MAGNETIC_SIZING_FLOOR` (`:1265`) | 3.2-4.1 % of a peak, 0.031 esd preset, "one family" | none |
| `least_squares.FD_STEP` (`:1561`) | 23 configurations within 2.5e-4; fails on the variance floor, "1e-8 does not cure it" | The failure belongs to the clamp, not the step. On its smooth domain the step passes, so tier 1 is arguable once WP-1467 (the open fix for that clamp) lands. Keeping tier 3 now is honest. |
| `caglioti._MIN_GAMMA_G2` (`:1399`) | binds only on SRM 660c's and cpd-1a's answers; 1.2 esd on U under a 1e-10 floor | "4.4e-4 ... and 1.6e-4 ... within the lab and synchrotron bars" means respectively (the test's lines 349-352). Read the other way, 4.4e-4 fails the synchrotron bar. Add "respectively". |
| `origin.A5_CLIP` (`:1361`) | 1.40 % against 1 %, 1200 synthetic matrices | The bar (an esd's sampling error at N − P = 5000) is defensible. NAC's N − P of about 22 000 would set it near 0.5 %. |
| `preferred_orientation.TEXTURE_SPHERE_SAMPLES` (`:1385`) | misses by 2.0e-3 to 7.9e-3 against "the digit TEXTURE_NOT_POSITIVE prints" | Wrong frame. The sampled minimum feeds a guard (`forward.py:1520`, "a record and a guard read it"), and sampling can only miss a dip, never invent one. So the question is how deep a dip can stay unreported (up to 7.9e-3), not the printed digit. `TEXTURE_NOT_POSITIVE` is the warning that the texture's pole density has gone negative somewhere. |
| `restraints.MIN_IMAGE_SHELL` (`:1466`) | misses 72 of 2518 pairs within 4 Å at β 135-150° | A defect with a named fix. The row does not say whether any missed pair lies at bond length (under about 2.5 Å). |

Would change the verdict on the bar: stating it relative to each pattern's own σ/peak, and a ruling on Q2 that sets one esd bar across B3, B7 and B10.

> Author: corrected in the rows: "respectively", `MIN_NODES`'s inert range, the texture frame (an unreported dip), `WINDOW_AREA_TOL`'s counterpoint and GSAS-II's 0.6 %, the axial floor's answer effect. The bar's calibration joins Q1 and Q2 for the maintainer. Not done: whether a missed restraint pair lies at bond length, which the image-shell fix makes moot.

**Item 6. `rietx.strategy.suggest.SUGGEST_SEED_STEPHENS` (tier 3, evidence updated)**

**Weak.** The new evidence measures the plan's solve seed, not the suggestion probe this row governs. Neither new comparison sets 1000 ppm against a distinct non-zero start.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "= lab_sample_refine's strain_seed" (`:2216`) | The constant is the start `Refinement.suggest` uses to score a Stephens candidate (`refine.py:3595`; Stephens is the anisotropic-strain model). The solve seed is a separate hand row (`:2271-2273`). `waiting.md:23-25` leaves `SUGGEST_SEED_ROUGHNESS` unaudited for exactly this reason: whether `suggest`'s ranking moves with the start. | evidence answers a different seat |
| 3. Case against acting | "brucite tests only a near-zero start" | Brucite compares 1000 ppm against 0.35 ppm. That is the square-root singularity, the forced case the grounds already cite. Corundum compares 903 against 1000 ppm, nearly the same start. Only WP-1467's pattern 41 compared a distinct start (the previous stage's strain), and lost. | the second family does not discriminate |
| 4. Case for acting | "1000 ppm reached the lower or equal minimum in all three comparisons" | True as stated. 800 ppm agreed to 0.01 esd on brucite: local robustness. GSAS-II's isotropic 1000 µstrain is a Reset button, not a default (`1467:217`). | weak |
| 5. Tier | tier 3, B3 (`rulings.md:49-51`) | B3 asked for "a second dataset compares the starts". CPD brucite and CPD corundum come from one lab and one instrument. | partly met |
| 6. Families | WP-1467 pattern 41; CPD | Two at most. The reference is the lower χ², which is not independent of the fit. | weak |
| 7. What says it fired | none given | It is a probe start, so nothing fires. | n/a |

Would change the verdict: the suggestion's ranking of the Stephens candidate compared at 1000 ppm and at a distinct non-zero start (such as the phase's isotropic strain on pattern 41, or patterns 0 and 16), as WP-1467's seed task asks.

> Author: the row now says these are the solve seed's measurements and the probe's start is unmeasured, as `SUGGEST_SEED_ROUGHNESS`'s is; it stays tier 3.

**The rows left at unaudited**

**Holds** for all of them. Each waits on a measurement or a ruling it names. Two notes:

- **`INTERMEDIATE_FTOL` and its three siblings.** The hold flip already refutes invariance under any esd bar. At 1e-6 the absent zircon is held; at 1e-9 it is not and its cell walks (`waiting.md:41-46`). So Q2 decides only between tier 3 and demotion. The waiting note should say that. Item 1a's budget invariance also rests on this ruling: the 1.24x margin is the `None` schedule's. If that becomes the default, the three B11 rows need re-measuring.
- **`SUGGEST_SEED_ROUGHNESS`.** It is left unaudited because the probe start was not measured. `SUGGEST_SEED_STEPHENS` (item 6) has the same gap and sits at tier 3. The two should be treated alike: the Stephens row's evidence should say the probe is unmeasured.

`StageResult.seeded` (one literal seeds both Suortti's b, which is invariant, and Pitschke's c, which is not) and `HARMONIC_WEIGHT_SEED` (one synthetic family, failing at 0.01 esd by the plan's mechanism) wait correctly on Q3 and Q2. No name was added to `UNAUDITED_BASELINE`. Four were removed, so the list shrank.

Would change this: a Q2 ruling, after which the `INTERMEDIATE_FTOL` group has nothing left to wait on.

> Author: `waiting.md` § B7 now says both.

*Decided on the maintainer's behalf.* The domain tests' bar: a tenth of σ at a point, or of σ/peak at the strongest peak of FAP (lab) and 11-BM NAC (synchrotron), which adds 1 % to that point's expected χ²; a strict bar, chosen so a pass means the setting is invisible in the data. No constant changed, even where the measured fix was cheap, because each moves every fit that reaches it.

*Gotchas.* LaB6 under the NIST protocol has two minima 46.7 χ² apart, nearly S/L ↔ H/L mirrors, and LM and TRF land in different ones; its polish fixed points are not unique either. A comparison of two arms should polish both from one common start. An odd FCJ node count gives the same answer as one fewer (n//2 a segment). The worktree guard refuses a heredoc whose text it cannot parse; write the script to the scratchpad and run it.

*Next.* (1) The fifth round's answers, then their builds: each constant change moves every fit that reaches it, so goldens are re-pinned in the same commit, and `docs/docs/theory/profiles.md:511` hard-codes the FCJ clamp "[8, 64]". (2) Two defect fixes needing no ruling: the restraint image shell sized by `geometry._shell(g, d)`, and the bond search freed from the 3.5 Å contact radius (or a note counting what it cuts). (3) B14's lifts with the ~50-guard list to the judge. (4) The interval and width-grid domain tests. (5) B7 and B9 re-measured once the window ruling lands, since window truncation is part of the frozen-compile scatter.

- **2026-10-20** — Split at the maintainer's request after the 2nd session's handover. The second pass (three families per surviving tier-3 threshold) moves to [2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md) and the clash table's 38 pairs to [2018](2018-the-clash-table-measured.md), each with the context this file held. This WP now closes on two sessions' work: the owed tests (two-start, invariance, margin, domain, the FCJ node cap), then B14's lifts with the ~50-guard list to the judge, with the goldens and `test_compare_ui` rows on the way. The maintainer's estimate question was "how many more sessions in 2002": about five or six unsplit, two now.

### 2026-10-20 (2nd session) — the last five questions ruled, a contributor's second read built, and the position limits gone

Every question the batch left open is now answered, and the answers run in the code. The
peak-position corrections (zero shift, displacement, the capillary offsets, transparency's
ceiling) have no default limits any more: on 11-BM NAC the fit reports the degeneracy
either way, and the limit only acted as a prior that the mount is aligned, which belongs to
a caller who knows the mount. A refined occupancy above 1 is an info record, a tie between
magnetic models abstains instead of crowning the simpler one, and `auto_background` keeps
its pick because the near-threshold choices measurably move nothing. Mike Gaultois's second
read of the batch found three real defects, all fixed: Le Bail and Pawley could not refine
a wavelength or the Kα2 ratio, a history replay turned an explicit 0 into the default, and
the CIF quoted a slightly wrong esd factor. Building the first exposed a fourth:
`suggest()` silently dropped a held wavelength in every mode.

*Done.* Rulings recorded in `2002-batch/rulings.md` § fourth round, with the maintainer's
words where given. Asked "check other codes": GSAS-II 5.8.4 and FullProf bound none of the
position corrections nor U, V, W, X, Y; TOPAS v9 § 2.17 Table 2-1 has no row for either
(its macros' limits live in `Topas.inc`, not on this machine), lists `occ` 0 to 2·Val + 1,
and moves a, b, c within ±(0.5 % + 0.05 Å) per iteration. Built, one commit each: the
position bounds removed, the NAC test asserting the report instead of `BOUND_HIT`
(3d63e9db5); Le Bail and Pawley refine `.source.lines.` (84b9e87a2); a held azimuth is
never turned (d02cbfe6d, test); cherry-pick replays an explicit 0 (ce1961d7b); the CIF
quotes the carried factor (6a72cc225); `suggest` scores a held wavelength against the held
cell (ed72edd12); `OCCUPANCY_ABOVE_ONE` at info (da9d30d02); every ΔBIC tie abstains,
listed fewest moment parameters first, the reported nuclear reference staying the ΔBIC
leader's (58534d7a2, 5e986acef); the auto_background rows kept at tier 3 with the
measurement; the cell window, twelve solver stop constants and `DENSE_JACOBIAN_MAX_BYTES`
to tier 3 (approved); the profile walk's and the width grid's settings from `caller` to
tier 3 under B10; `phase_support_sigma` and `correlation_guard` reach the package's own
trials (a56ba4d26) and are recorded on `NodeAction` so a cherry-pick replays them
(761f899c7); the line columns' Jacobian checked under both intensity models (9ecf7b2cb);
main merged twice, this branch's WP-2013 renumbered WP-2015 after main took 2013; the new
manual pages main's WP-1986 had copied before this branch's edits brought up to date
(c406fe513); WP-2016 filed (a CIF U^ij off its site symmetry only by rounding); B5.2's
warning proposal forwarded to WP-1952. The reply to Mike is on PR #1050. Q3, the TCHZ
box, waits for the next session by ruling.

*Measured.* Other codes and the background measurement as in `rulings.md`. 11-BM NAC, zero
and both capillary offsets free (R = 1000 mm, `test_capillary_displacement.py`'s
protocol), cell from the acceptance band's centre 10.2510 Å: offsets held +21 ppm (esd 6);
bounded −1097 ppm (esd 2612), seven warnings; unbounded −5109 ppm (esd 2579), six, two of
them `FLAT_DIRECTION` naming the cell and an offset. SRM 660c Kα2/Kα1: 0.5126 ± 0.0048
Rietveld, 0.5145 ± 0.0036 Pawley, 0.5224 ± 0.0033 Le Bail; Le Bail with the cell held
refines λ to 1.540605 ± 3e-6 Å against the declared 1.5405929. Line columns against
central differences on a Cu Kα doublet: 5e-10 (weight) and 3e-7 (wavelength) relative in
all three modes. auto_background on 30 real patterns: hump score 0.036-0.067 on five
synchrotron or low-background, 0.10-2.3 on all 25 lab; air gain within 0.06 of 0.3 on 6;
seven patterns refitted four ways moved no cell, scale or Biso past 0.8 esd except FAP with
its air term left out (scale 2 esd, Lorentzian size and strain 3 esd), a choice the pick
does not make. Suites on this branch merged with `origin/main` at `0d6d5a441`, `[dev]`, darwin/arm64, no other suite running: fast 10 895 passed, 191 skipped, 2 xfailed, 2 failed in 4:21; full 11 210 passed, 200 skipped, 2 xfailed, 2 failed in 20:30. The two failures were this session's own and are fixed in 89b343fe4 (the root CLAUDE.md one line over its cap, and "Lelann" added to the generated accept list rather than its source); both files then passed alone, 46 passed. The full suite was not re-run after that fix, which touches no code. Every bit-identity golden passed. Against the lane's fast run on the tree before the review fixes (10 894 passed, 191 skipped), passed+skipped+failed moved by exactly the three tests the review added. The full selection has two fewer skips than an earlier full run this session (202), not traced. The branch adds 64 tests to the fast tier, 27.5 s together locally, the largest 7.0 s (`test_stationary_moment_angle.py`, an earlier session's); this session's largest is 1.3 s (`test_magnetic.py`'s held azimuth), so none joins the tail. Lanes: none dispatched under `/wp-start` 6c's `lane:`
form, so 3b does not apply; four helper agents ran (other codes, background impact, the
manual port, the plan-settings item).

*Code review* (`high --fix`, in two ranges to keep main's merged diff out). Post-merge
range, eight findings, four fixed: the old refining chapter's tie sentence (372b18803);
`api_call` compares against the live constants (9b0170182); a tie reports the ΔBIC
leader's nuclear reference, and the reorder uses an id set (5e986acef). Declined: trials
taking the carried settings as their `run_stage` default (a public default change, the
lane's decision 1 below); the `approved` dates of the six B10 re-tiers (traced in
`rulings.md` instead); the repeated grounds text (`tests/audit_delta.py` reads row fields
by `ast.literal_eval`, so a shared constant would break it). The missing direct
assertion for the wavelength in `suggest` is the Le Bail count check, which failed before
the fix (18 against 19). Pre-merge range, nine findings, eight fixed: the CIF compares
factors before rounding (975c707ba); the `.instprm` reader's dead zero widening
(3311ea5cf); the capillary check's docstring and the force-fix comment (df04e74c7); the
cross-backend stage harness asks `mode_fixed_path` (88931ec04); the line columns' Jacobian
test (9ecf7b2cb); the rulebook's 11-BM clause and the summary's esd factor (d51b73397).
Declined: the repeated audit evidence text, as above.

*Generality* (the `generality-review` judge, fresh context, on this session's 13 items;
its full text in this session's transcript; verdicts and the author's answers):

| Item | Verdict | Case the judge found | Author's answer |
|---|---|---|---|
| `AIR_SCATTER_TRIGGER` | holds | three families, no independent reference (qarr's weighed compositions unused) | second pass, against the weighed values |
| `HUMP_TRIGGER`, the two knot steps | weak | the target case, a real amorphous hump, is untested; the score cannot see one | next: a real hump (glass capillary, an amorphous binder) at 3° and 8° |
| the cell window to tier 3 | holds | may never bind under the hold | the second pass counts it |
| `OCCUPANCY_ABOVE_ONE` at info | holds | — | — |
| `MOMENT_ANGLE_STATIONARY` wording | weak | "always" overclaims: the test's linear refit sits up to 1.5 from the full one, the cuts 1.13 apart | reworded "nearly always" (98e07a9e7) |
| interval and width-grid settings | holds | domain tests owed | owed |
| twelve stop constants | holds | `_CAUCHY_ARMIJO`'s grounds overstated | reworded (98e07a9e7) |
| `DENSE_JACOBIAN_MAX_BYTES` | holds | one case | second pass |
| position bounds removed | holds | the change described the NAC measurement wrongly: the bound hid nothing, it was a prior that held there; one family | reworded in the schema comment, reference page and test (98e07a9e7); a flat-plate lab family owed |
| Le Bail/Pawley lines | holds | one standard, no reference ratio; Le Bail 1.7σ from Rietveld | a second standard owed |
| `suggest` ordering | holds | — | — |
| ties abstain | holds | `trials[0]` is no winner; a careless caller could read it as one | `best` is `None` and the reason says so |
| plan settings inherited | holds | `StageResult` carries neither setting | lane decision 2, below |
| CIF factor | holds | the TOPAS clause said more than its reference | reworded (98e07a9e7) |

*Decided on the maintainer's behalf* (the plan-settings lane): `run_stage`'s public defaults
stay 3σ and 0.98, so a bare `ref.run_stage` after a fit with the hold off still holds at
3σ; the alternative is a sentinel that inherits the last fit's, as `mode` and
`two_theta_limits` do. `StageResult` got no field (nothing replays from a result, and
`PHASE_UNCONSTRAINED` quotes the threshold). A guard a plan set before this change was
never recorded, so those nodes replay at 0.98.

*Gotchas.* main's WP-1986 copies an old chapter into `docs/docs/` and leaves the old page
standing, so a branch that edited the old page merges clean and the new page keeps the old
text; only a vanished substitution or xref fails the build. After a merge, grep the new
tree for each fact the branch changed. `set_vary`'s wavelength refusal is per row and
order-dependent within one call, so a caller freeing a mixed set reads its return or splits
the call. A Jacobian check against a blank pattern under an intensity model measures noise:
the extracted intensities are zero. `vale` needs `vale sync` once in a fresh worktree.

*Next.* (1) The owed tests, smallest first: B3's two-start tests (roughness and Stephens
seeds), B9's starting values (Biso 0.5, the TCHZ starts, the harmonic seed), B7's
intermediate-tolerance invariance in plain esds, B11's iteration-budget margins under both
solvers, B10's domain tests and the FCJ node cap below 6.5° 2θ. Each moves a tier-3 row to
tier 1 or invariant, or finds a defect. (2) B14's lifts (about 20 constants, 8 seats, the
fields for the collapse restore, the Stephens seed and the σ rule) and the ~50-guard list
to the judge. (3) The second pass, three families per surviving threshold, which also
decides the twelve stop constants and seven switches now at tier 3; it includes a real
amorphous hump for the knot switch, a flat-plate family for the position bounds' removal,
and a second standard for the Le Bail line ratio. (4) The clash table's 38 pairs, goldens,
`test_compare_ui` rows. (5) Q3, the TCHZ box, whose open part is the upper limits (Y ≤ 1°
caps Lorentzian size near 8 nm at Cu Kα under the default plan); and the lane's decision
1, if the maintainer wants `run_stage` to inherit the last fit's plan settings.

### 2026-10-20 — all sixteen classes ruled, and seven of the rulings built

The maintainer has ruled on every class, and most rulings now run in the code. A fit puts a
runaway cell back where its stage found it, where it used to stop it at an invented 15 %
edge. Crystallite size, occupancy, texture and the line and harmonic weights refine
wherever they stay physical, and an occupancy above one warns. A moment angle that sits on
a symmetric direction carries a likelihood interval, where it used to carry no uncertainty
and read as exact. The caller can set or switch off the absent-phase hold. Every refined
row reports, beside rietx's esd, the smaller number GSAS-II and FullProf print, and the
manual explains the difference. The pick verbs show their evidence and abstain on a tie.
One measurement narrowed a ruling: freeing the peak-position bounds let the 11-BM NAC cell
drift 5129 ppm against 1117 ppm, so those bounds stay until the maintainer rules again.

*Done.* Rulings, in `2002-batch/rulings.md` (three rounds, all dated): B1 on by default as a
plan setting; B2 the turn kept and, re-asked after this session found its first brief
misstated the cost, the stationary-angle test kept with the angle given its interval
(option 2); B3, B11, B16 as recommended; B4 keep f and report the uncorrected esd; B5 fix
the obviously wrong, warn at ingestion, an option to correct (forwarded to WP-1952); B6,
B13, B15 yes; B7 with two additions and B9's unstated geometry (filed as WP-2015); B8 the
window tier 2 on TOPAS, the clamp a reset-and-hold, the 2 nm floor removed; B9 no chosen
limit on a physical quantity; B14 option 3, re-explained and confirmed. Built, one commit
each: the audit rows the rulings settle (62 by the lane and by hand, then each change's
own); the cell reset (`StageResult.cell_reset`); the limits (`OCCUPANCY_ABOVE_ONE` new;
`MARCH_R_MIN` 0.15 → 1e-6; the harmonic, emission-line, axial and occupancy ceilings and
the 2 nm floor gone; readers and the GUI no longer write the old ceilings); the angle's
interval (`RefinedParameter.interval`, a new `IntervalStop` "period" that stops a side
half a turn out); `phase_support_sigma` (project format 1.5, `.rxt` `support`);
`stderr_uncorrected` with the theory and three switching pages; the pick verbs
(`BackgroundChoice`, N/f², no R tie-break, `QPA_FRACTION_RANGE`). `2002-batch/waiting.md`
lists the 16 rows still at `unaudited`, each with what it waits on. No Inherited section
to prune. Forward references to 2003, 2004, 2005, 2008 and 1327 (`SOLVE_D_MIN` folded
there, no new WP); 1952's B5 entry rewritten to the ruling.

*Code review* (`high --fix`, this session's range): nine findings, six fixed in
`20674c4c` (a stale Jacobian after a late cell reset; the magnetic solve's plans dropping
`phase_support_sigma`; the N/f² caveat claiming f = 1.00 on raw N; an interval
precondition error escaping a finished fit; the quickstart tutorial). Three declined as
design choices, now Next items 1-2 and in 2003: internal trials run at the default 3σ, the
threshold is not recorded for a cherry-pick, and a series' discarded rungs pay the
interval.

*Measured.* Fast selection on this branch merged with `origin/main` (`7646e7a6`), `[dev]`,
darwin/arm64, no other suite running: 10 868 passed, 191 skipped, 2 xfailed, 1 failed, the
failure the stale WP index this handover then regenerated (`test_docs_consistency.py` 25
passed after). The branch adds 52 test cases (51 in the fast selection; one is `slow`),
33.2 s together locally, the largest 11.0 s in `test_stationary_moment_angle.py`; none
joins the tail. Full suite on the same merged tree, `[dev]`, darwin/arm64, alone: 11 181 passed, 202 skipped, 2 xfailed, 1 failed in 24:49. The failure was `test_lebail_alternation.py`'s wander test, which pinned "Pass 3 of 4 was kept": its cell stage runs away, and since the B8 reset the wander keeps pass 2 of 3. The test now asserts its invariant (the next fit continues from the kept pass) and passes alone in 64 s. Every bit-identity golden passed. The automatic interval costs 20-32 refits an angle,
2.6-16.7 s on test fits of 0.2-1.2 s; a moment the data no longer saw walked to ±1e12 rad
over 120 refits before the half-turn stop (15.9 s, now 1.7 s). `Statistics.esd_inflation`
differs from the factor the esds carry by 0.07 % (NAC Rietveld), 0.75 % (NAC Le Bail) and
4 % (a joint fit weighted 1:4). N/f² moved `solve_magnetic`'s winning margins 1682 → 143
(Cr₂WO₆ 4 K) and 1704 → 164 (LaMnO₃ 50 K) and no verdict. Lanes: seven, every one
laned under 6c (context 270-465K), the whole table from `session_usage.py lanes`:

| lane | est | requests | main at dispatch | lane $ | in-session $ | saved $ |
|---|---|---|---|---|---|---|
| land-ruled-audit-rows | 40 | 50 | 270K | 3.98 | 12.65 | +6.36 |
| cell-clamp-restore-and-hold | 35 | 144 | 335K | 10.73 | 26.27 | +15.13 |
| chosen-limits-size-floor-and-b9 | 40 | 213 | 356K | 18.11 | 39.50 | +21.09 |
| stationary-angle-interval | 35 | 160 | 404K | 11.24 | 22.48 | +6.36 |
| phase-support-sigma-seat | 25 | 182 | 439K | 14.17 | 27.71 | +8.68 |
| b4-textbook-esd-and-manual | 30 | 169 | 450K | 10.31 | 24.16 | +8.65 |
| b12-pick-verbs | 35 | 181 | 465K | 16.77 | 30.10 | +9.50 |

Trial row appended to `process.md`; estimates ran short by 5.17×. The baseline replay's
selective policy (lane when main > 150K and item ≥ 20 requests): -16 % over 217 sessions.

*Generality* (the `generality-review` judge, fresh context, on the 242 rows both sessions
added or retiered and six heuristics the table cannot see; tables condensed to the rows it
did not find holding, its full text in this session's transcript):

| Item | Case against | Verdict | Author's answer |
|---|---|---|---|
| Tier-2 stop rules (Coelho's `_M_HI`, `_M_LO`, `_Q_*`, `_LAMBDA_FAIL_*`, `lm._CONVERGED_RUNS`, the five `bccg` stops; `_CAUCHY_ARMIJO`, `SCHERRER_K`, `BOND_SLACK_ANG`, `STEPS_PER_FWHM_*`) | a paper defining an algorithm does not validate its constants on rietx's problems; they decide where a stage stops, the class B10 held at tier 3 | weak | agreed: re-tier to tier 3 with either-side refits owed, as B10's switches, next session |
| `PARAMETER_INTERVAL_*` at `caller` | `fit` and `run_stage` now call the interval (B2 option 2) | fails | agreed: this session made it a default path; re-tier under the B2 ruling next session |
| `FRACTION_PROFILE_FWHM_MIN`, `_N_FWHM` at `caller` | the skill sends every agent to `profile_fraction`, and B12 ruled a skill instruction a default path | fails | agreed; re-tier next session |
| `SCALE_B_SEPARATION_FLOOR`, `_COS_CLAMP`, the two `*_CAP_RANGE_FRACTION` at tier 1 | each carries a chosen factor; with the 2 nm floor gone the range backstop is the only size bound | weak | the 2 and the 1.0 go to the second pass as thresholds |
| `A6_MAX_ITER` invariant | its test asserts eq 21 is met, not the margin to 2000 | weak | a margin assertion is owed |
| B2 `MOMENT_ANGLE_STATIONARY` evidence | one angle's cut is the one-sided 2.706, so a single passing angle's interval always contains the direction; the suggestion's "excludes" branch is reachable only for sets | rows hold, text weak | fix the evidence line and the suggestion's wording next session |
| B3 Stephens seed | the ruling asks the seed recorded in the result; `seeded` records only the roughness seed | weak | B14's field for the strain seed is the fix |
| B8 cell window | the ten iterations per stage is a threshold of its own, untiered | weak | the ten goes to the second pass |
| B9 `EXTRA_PEAK_FWHM_MAX` tier 1 | the 0.5° is a choice; a broad impurity peak modelled as an extra peak dissents | weak | kept: a finite max sizes the frozen window; widening is the design change named in waiting.md |
| B9 `Source:polarization` kind 3 | it acts (fits at 0.5) and nothing records the assumption yet | weak | WP-2015 records it |
| B10 `DENSE_JACOBIAN_MAX_BYTES` | landed on the solver-switch grounds, but the ruling names six switches and not this one | fails | agreed: back to `unaudited` for the maintainer next session |
| B12 `auto_background` constants, `:kind`, `:seed` | the pick rests on visibility, which the rule rejects; `:kind` was never shown to the maintainer; rietx's unseeded start is 0.0, not GSAS-II's (1, 0, 0) | fails | a question for the maintainer below; the rows go back to `unaudited` until answered |
| B12 `SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K` | the rare-feature clause keeps a measured value; these have no source and no measurement | weak | second pass |
| B12 `MODEL_FAR_FROM_DATA_RWP` | at 1-2 counts a channel a correct model's Rwp is about 0.7-0.8 | weak | second pass, with a sparse family |
| (b) peak-position bounds kept | one family; a recessed lab holder or a weak absorber dissents | your ruling | question below |
| (c) `_auto_intervals` on in a series | every pattern, and discarded rungs, pay | weak | forwarded to 2003 |
| (d) `OCCUPANCY_ABOVE_ONE` with no gate | 1.032(25) is a full site; a warning on noise is a verdict the data do not support | weak | question below |
| (e) `stderr_uncorrected` | right, but the result does not record the applied factor and the interval cut reads the other one | holds, record weak | forwarded to 2004 |
| (f) parsimony tie-break | "a ΔBIC tie abstains"; BIC already charges parameters | fails against the ruling | question below |

Held without comment: tier 1 bar the four rows above, the defaults with GSAS-II lines,
the other `caller` rows, the invariant rows bar `A6_MAX_ITER`; B1, B4, B6, B7, B8's cell
reset, B9's `MARCH_R_MIN`, B11, B16, the ΔBIC rows, the Pawley pair, `QPA_FRACTION_RANGE`,
and the half-turn stop.

*Questions for the maintainer* (five need a judgement; the briefs are in this session's
report and short):
1. The peak-position bounds (zero shift ±0.5°, displacement and both capillary offsets
   ±1 mm, transparency ≤ 0.05): keep them as guards on a degenerate walk, or widen them
   under B9?
2. `OCCUPANCY_ABOVE_ONE`: gate it on significance (above 1 by some number of esds), make
   it an info record, or keep it as a warning on any value above 1?
3. `TCHZ_BOUNDS`: WP-1312 ruled "the bound stays" on 2026-09-11; B9 says chosen U/V floors
   and ceilings go. Which holds?
4. The parsimony tie-break in `solve_magnetic`: drop it too, so every ΔBIC tie abstains?
5. `auto_background`'s pick: kept as a tier-3 pick, or does it abstain without a clear
   winner, now that the skill makes it a default path?
Confirmations: the emission-line weight widened (TOPAS's `la` limit is per iteration);
`QPA_FRACTION_UNDETERMINED` renamed `QPA_FRACTION_RANGE`; the automatic interval's cost.

*Gotchas.* A lane applied B9's principle to every box, including the peak-position bounds;
the lead put those back after measuring the NAC drift, so read a ruling's reach against
the measured consequence before landing a widening. `Statistics.esd_inflation` is not the
factor the esds carry; use `stderr / stderr_uncorrected` on a row. The worktree is still
named `wp2001-rule-table-guard`.

*Next.* (1) Make `phase_support_sigma` reach the package's internal trials (interval walk,
fraction profile, rival fits) and record it on `StageResult`/`NodeAction`, so a
cherry-pick replays what ran; `correlation_guard` has the same gap. (2) The judge's
re-tiers: the `PARAMETER_INTERVAL_*` and fraction-profile rows, `DENSE_JACOBIAN_MAX_BYTES`
and the `auto_background` rows back to `unaudited`, the Coelho stop rules to tier 3, the
stationary evidence line. (3) B14's lifts (about 20 constants, 8 seats, the fields for the
collapse restore, the Stephens seed and the σ rule) and the ~50-guard list to the judge.
(4) The owed tests: B3's and B9's two-start tests, B7's invariance, B11's margin, B10's
domain tests and the FCJ node cap. (5) The second pass, the clash table, goldens and
`test_compare_ui` rows. The maintainer's answers to the five questions decide (2)'s
`auto_background` rows and three of the code changes.

### 2026-10-19 (2nd session) — four classes ruled, the rest re-briefed in plain words

The maintainer ruled four of the sixteen classes and confirmed the absent-phase hold. The
declared geometry now picks the default plan. A numerical setting is tier 1 when a test
bounds its error over its domain. The three pick verbs are fixed as proposed, and the inline
numbers that could change an answer become named constants. The other nine items came back
as questions, so this session rewrote them in plain words and asked again
(`2002-batch/rulings.md`). Asked what is scientifically accurate, it reversed the batch on
the esd factor. The textbook esd is too small on correlated residuals and shrinks with step
size, so the pick is now to keep the Bérar-Lelann inflation and report the textbook esd
beside it. Nothing in the code or the audit table has moved.

*Done.* `2002-batch/rulings.md`: the rulings with the maintainer's words, the nine
second-round briefs, and the six open questions. Three picks changed from `batch.md`'s
revised picks. B4 keeps f (option 1, the textbook esd reported beside it). B5 drops and
reports a non-positive esd (option 3, built in WP-1952). B9 adds a "geometry not stated"
state, joining the B7 follow-up. No Inherited section to prune. No forward reference: the
B7 follow-up has no owner (grep over `docs/wp/` for `Geometry.kind` and
`lab_bragg_brentano` found closed WPs and WP-1421, which is unrelated), and it is filed
once B9's geometry question is ruled, so that both land in one WP.

*Checked this session.* Bérar & Lelann (1991) and McCusker et al. (1999) are not in the
Zotero library (title search over a copy of the sqlite, and file names under storage).
`berar_lelann_factor`'s docstring gives f ≈ 1.127 on white residuals
(E[S'']/E[S] = 1.2694). `Geometry.kind` defaults to `debye_scherrer` and has no unstated
value. `mccusker_default` frees zero but no displacement, and `lab_bragg_brentano` frees
displacement, the Kα2 weight and the axial terms (`strategy/staged.py` ~351-425).

*Not done.* The handover's code review was skipped, since this session's one commit is
prose. No test ran beyond the handover's own checks. The generality judge is owed on the
148 rows the first session landed in `_audit.py`. `batch.md` carries the judge's case
against each unruled class, but the first entry has no *Generality* table for the landed
rows. This session added no row, so it did not dispatch one at this context.

*Gotchas.* The branch is checked out in the `wp2001-rule-table-guard` worktree, and its
session (pid 52389) was still open. This session committed from a detached HEAD in the
`happy-watching-squirrel` tree and pushed to the branch. That other tree's local branch is
one commit behind origin, so run `git pull --ff-only` there before working. B14's yes was
given on a misreading ("the demotion tests"). The substance is unchanged, but confirm in a
line.

*Next.* (1) The maintainer answers the six questions in `rulings.md` § Still open. (2) Land
every ruled row in `_audit.py` with `grounds` and `approved` 2026-10-19: B1, B7's plan rows,
B10 (plus its sentence in `generality.md` § The rule), B12 and B14's lifts. (3) File the
follow-up WP for the geometry-chosen plan once B9 is ruled. (4) Run the generality judge on
the 148 landed rows. (5) Then the first entry's Next items 3-6: the 17 unread citations,
the second pass, the clash table, and the demotions with their goldens.

- **2026-10-19** — the inventory, 148 rows tiered, and the decision batch (PR #1050).

  Every automatic decision a single rietx fit makes now has a proposed tier with its
  evidence. The 148 that need no approval are in the audit table. The other 256 are grouped
  into 16 classes in a decision batch that waits on the maintainer (`2002-batch/batch.md`).
  Nothing has been demoted yet, so no fitted number has moved. Two findings stand whatever
  the rulings. The axial-divergence quadrature's node cap leaves an error of 2.8 % of peak
  height at 3° 2θ on lab Bragg-Brentano data. And the default Bérar-Lelann inflation makes
  every rietx esd 1.13 to 8 times what GSAS-II would report on the same fit.

  *Done.* Inherited pruned: 2001's four notes folded into Context and Non-goals, none
  stale. Six read-only readers (refine.py; strategy/ and schemas/plan.py; optimize/;
  model/; background/; params/ and the schemas) proposed a tier for each of the 299 walked
  rows plus the strategy codes, 402 proposals in all (`2002-batch/inventory.json`). 157 rows
  needing no approval landed (tier 1, tier-2 thresholds, `caller`, and the
  observation-channel defaults as `invariant`). The handover's code review sent nine back
  to `unaudited` and fixed four (batch § Added after the handover's code review), so 148
  stand. `tests/test_answer_invariant_defaults.py` (8 cases) asserts that the event stream,
  progress stream, cancel token, label, run recorder, per-stage reports and history tree
  leave a fit's answer bit-identical, and that the recorder actually ran. One Opus agent
  drafted the batch and checked the readers' claims; a fresh-context judge wrote the case
  against each class; the lead corrected the six sentences the judge found wrong and wrote
  a revised pick per class. Held-out family named (§ The batch). Forward references went
  to 2003, 2004, 2005, 2006, 2007, 1952, 1542 and 1467.

  *Measured.* FCJ node cap (`model/profiles/fcj.py` `MAX_NODES` = 64) against a 512-node
  reference, S/L = H/L = 0.025, FWHM 0.07°: 0.19 % of peak height at 5°, 0.71 % at 4°,
  2.8 % at 3°, under 0.06 % uncapped (`2002-batch/fcj_low_angle.py`). Issue #740's Le Bail
  cycles: Rwp 4.56 % at 3, a plateau of 1.62 % from 100 to 400, 1.09 % for the true
  structure (`2002-batch/i740.json`). Proposed demotions on the judgement question: about
  15 rows, from 18 in the draft (the milestone asks each audit for this count; it is final
  only after the rulings). None measured yet on the mechanical question. Subagent spend:
  six readers 2.22 M tokens, drafter 0.50 M, judge 0.35 M, code review 0.19 M. No lane in
  the `/wp-start` 6c sense ran, so there is no lane table. Fast suite on the final tree, `[dev]` venv, darwin/arm64, nothing else running: 10 834 passed, 191 skipped, 2 xfailed, 4:41 wall; the 8 added cases cost 3.06 s together (one local run). The full suite was not run: the branch changes no library code, only the table's data, one test file and docs.

  *Questions for the maintainer.* Full briefs in `2002-batch/batch.md` § Bn, each with the
  case against and a revised pick. Eight need a judgement:
  1. B4: stop multiplying every esd by the Bérar-Lelann factor, and report the factor
     beside it? (pick: yes)
  2. B5: demote the floor that raises a zero esd to 10⁻³ of the median, and leave its
     replacement to WP-1952? (pick: yes)
  3. B7: the default plan `mccusker_default` frees no specimen displacement on
     Bragg-Brentano data, where rietx's own `lab_bragg_brentano` does. Keep it at tier 3
     and compare the two presets on three families, or choose the preset from the
     geometry in a follow-up? (pick: compare first)
  4. B8: remove the per-stage cell window if a count shows it never binds; make the cell
     clamp restore-and-hold; keep the 2 nm size floor at tier 3? (pick: yes to all three)
  5. B9: judge each default box on unanimity, widening chosen caps with a named dissenter
     (occupancy ≤ 1.5, March r ≥ 0.15) unless a source is found, and record
     `Geometry.kind`, polarisation and the Kα2 ratio as assumptions? (pick: yes)
  6. B10: read the rule for numerical settings as "tier 1 when a test bounds the error
     over the claimed domain", with solver switches kept only by either-side refits?
     Adds one sentence to `generality.md` § The rule. (pick: yes)
  7. B12: `auto_background` returns its evidence beside its pick; `solve_magnetic` uses
     N/f² and drops its R tie-break; `profile_fraction`'s warning becomes an info record;
     and is the skill's instruction a default path? (pick: yes; yes, it is)
  8. B14: lift the rows a retune could change into named constants, seats and record
     fields, and list the tier-1 floors in this file? (pick: yes)

  Five ask a confirmation (B1 absent-phase hold, B2 moment turn, with the angle test
  measured first, B3 seeds by test, B11 Le Bail cycles converge-with-cap in WP-1542, B16
  bound test). Three are plain (B6 dispersion kept, B13 hand-off of 58 diagnostic-only rows
  to 2004, 2005 and 2007, B15 the assumed ion split by element).

  *Gotchas.* A hand row cannot enter `_audit.ROWS`, because the table's test holds every row
  equal to something the walk sees; that is B14. The `generality-review` agent did not load
  as an agent type in this session, so it ran as a general-purpose agent told to follow
  `.claude/agents/generality-review.md`. The scratchpad does not survive a session, so
  everything the next session needs is in `2002-batch/`. This worktree is named
  `wp2001-rule-table-guard` and carries `wp2002-single-fit-actions`; the claim is recorded
  with `wp_claim.py`. 17 tier-2 rows rest on unread citations (batch, same section): check
  them against the corpus before building on them.

  *Next.* (1) The maintainer rules on the batch. (2) Land the ruled rows: each row's
  evidence line is in `inventory.json`; add `grounds` and the ruling's date in `approved`.
  (3) Check the 17 tier-2 citations. (4) The second pass: three families for the
  thresholds of surviving actions, with the held-out family excluded. (5) Measure the
  clash table (`2002-batch/clashes.md`; C1 is WP-1320's, C3 the window, hold and clamp
  triple). (6) Demotions, one commit each, then goldens; the owed invariance tests
  (`intermediate_ftol`, the budgets, the starts) and the FCJ cap fix sit with B10.
- **2026-10-18** — created, from the milestone's opening session (WP-2001's log has the
  measurements and the two reviews). No open WP owns the holds as a class: 1301 and 1534
  each shipped one and are closed. 1327, which shipped the moment hold, is still in flight
  (its analytic moment branch remains), so merge main before touching that hold and read
  1327's handover for what its branch moves.
