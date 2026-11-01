# WP-2002 clash candidates, deduplicated

Every pair of actions that read or move the same parameter, merged from the six readers'
notes (reader letters R, S, O, M, P, B as in `inventory.json`). Nothing here is measured.
"Source" names the readers that listed the pair, by letter and their own item number.
Line numbers are the worktree's on 2026-10-19. A file:line I re-read this session is marked
(read); the rest are the readers' and unverified.

Two entries are the ones the brief asked to mark: **C1 is WP-1320's clash** and **C3 is the
cell window, hold and clamp triple**.

## Pairs that act on the same parameter

| # | Parameter | Action A (file:line) | Action B (file:line) | Dataset that exercises both | Source |
|---|---|---|---|---|---|
| **C1** | `phases.N.scale`, the pinned width (`lor_size`, `lor_strain`, `gauss_*`), `phases.N.cell.*` | **WP-1320.** `profile_fraction` pins one width per branch and refits through `run_stage` (strategy/fraction_profile.py:212-218, read) | stage-start hold (refine.py:3946, read) and the collapse restore at the answer (refine.py:4114-4133, read) | `tests/test_qpa_multimodal.py`'s synthetic two-basin trace fixture; #203's reporter data is not in the repo. WP-1320 measured the clash under the pre-WP-1523 test (fraction_profile.py:17-19, read), never since | R1, S1 |
| C2 | the same, on any pinned path, including a phase scale | `profile_interval` pins a path and refits (strategy/parameter_interval.py:185-215) | the same hold and collapse | a weak phase in a weighed mixture: the qarr round-robin sample with the smallest weighed fraction, or #481's planted weak phases | R2, S2 |
| **C3** | `phases.N.cell.*` of a phase near or under 3σ | **The triple.** Cell window, declared for phases with `phase_support` under 3 (optimize/least_squares.py:2177-2196, called :2393, read) | absent-phase hold, same screen or lower (refine.py:1175-1223, called :3946, read); post-solve clamp to ±15 % (refine.py:1227-1286, called :4009 and :4192, read) | the 68-pattern in-situ series (the original 39 293 Å runaway); the synthetic two-phase LaB₆ with a 2 % trace at the same cell (the clamp's trigger); #481's ramp | P1, O1, R12 |
| C3a | the same | the hold sets `vary=False` first (refine.py:3946), and `ParameterTable.bounds()` windows free entries only (params/vector.py:3769, read) | the window | any of C3's: read in code, the window can bind only on a free cell column of an unseen phase that also drives a visible phase's cell through a tie | P1 |
| C3b | the same | clamp writes the window edge after the solve (refine.py:4009) | collapse restore writes the stage-start value (refine.py:4121) | a phase that both escapes 15 % and collapses under 3σ in one stage | R9 |
| C3c | the same | clamp, after the solve | degenerate-cell guard, during it (optimize/least_squares.py:965-1000) | the two-phase LaB₆ reproduction | R10, O11 |
| C3d | the same | clamp moves θ after the solve | bound test reads the active set "only while θ still sits on the limit" (strategy/staged.py:1740, :1838-1844) | a clamped cell on a bound | R11, S10 |
| C4 | `phases.N.atoms.*.biso` and adp | scale-B ridge hold (refine.py:718, :739; late hold :4148) | capillary µR or flat-plate µt correction shifts every Biso by c(µR)λ²/2 (refine.py:6578, :6608; model/forward.py:1110) | the fluorite ridge fixture (`test_scale_b_ridge`) with µR declared; 11-BM SRM 660a for the ΔB alone | R3 |
| C5 | `phases.N.atoms.*.biso` | ridge hold, never released in-stage (refine.py:3961) | collapse restore writes B back to stage start (refine.py:4121) | a phase both ridged and collapsed | R4 |
| C6 | `phases.N.atoms.*.biso` | `_significance_columns` leaves displacement columns out (refine.py:1605) | ridge hold (refine.py:718) | fluorite: 153.7σ screen against 0.02σ marginal over B. Designed to avoid the clash; confirm | R5 |
| C7 | moment angles `dof1`, `dof2` | moment hold and turn (refine.py:1096; writes :1079) | stationary-angle test zeroes the same columns from the covariance (optimize/least_squares.py:787; read by refine.py:1729) | Cr₂WO₆ 4 K (HB-2A), LaMnO₃ 50 K (BT-1) | R6, O9 |
| C8 | moment `dof0..2` of an invisible phase | phase hold takes them (refine.py:1223) | moment hold and the release's direction probe (refine.py:4040-4067) | a magnetic phase near onset (no family on disk) | R7 |
| C9 | moment directions | collapse restore of flat-now directions (refine.py:4094, :4121) | `sequential._floor_unsupported_moments` (sequential.py:851, 2003's) | a magnetic series through the ordering temperature | R8, O9 |
| C10 | `phases.N.scale` | phase hold keeps the scale free (refine.py:1115) | FLOOR_HIT on a scale at 0 (strategy/staged.py:1740) | #481's blank frames: an absent phase fires PHASE_UNCONSTRAINED and FLOOR_HIT together | R13, S9 |
| C11 | `phases.N.scale`, structure | the hold reads the previous stage's significance (refine.py:1215-1220) | a stage seed moves the phase, so its prior is dropped (refine.py:1218, :3873) | the ramp with the roughness stage in the plan. Designed | R14 |
| C12 | `phases.N.microstrain.dof.*` | Stephens strain seed at 1000 ppm (refine.py:3869) | LM cone inequality skipped when the start is infeasible (optimize/least_squares.py:1775) | brucite (`test_acceptance_stephens.py`). Low risk: the seed sits strictly inside the cone | R15, S6, O2 |
| C13 | `phases.N.microstrain.dof.*`, `lor_strain` | the same seed | a nonzero `lor_strain` locked under the block stays in the width sum (WP-1467) | WP-1467's pattern 41: χ² 1.286 with the floor kept against 1.160 with it zeroed, same seed | S5 |
| C14 | `instrument.profile.u/v/w`, `gauss_*` | Γ_G² ≥ 1e-8 linear-inequality rows (optimize/least_squares.py:1865) | bound test's active set, which may cover box rows only (strategy/staged.py:1740) | 11-BM NAC, where W sat on its floor before WP-1938 | R16, O4, P9, M4 |
| C15 | the same | `caglioti._MIN_GAMMA_G2` clamp (model/profiles/caglioti.py:88) | `FLOOR_SEEDS`, the LM polish (optimize/lm.py:184-185), `TCHZ_BOUNDS`' W floor (schemas/instrument.py:1493) | the same | O4, P9, M4 |
| C16 | any freed path in Le Bail or Pawley | mode-fixed drop (refine.py:3855) | stage seed (refine.py:3863). Ordered "before the seeds" by design | a Le Bail fit with the roughness stage | R17 |
| C17 | a user-held path | `Refinement.hold` via `Entry.held` (refine.py:3817) | `_answer_significance` frees held columns for the test (refine.py:1731) | read as safe by R | R18 |
| C18 | `phases.N.scale`, the held paths | `intermediate_ftol` stops every stage but the last at 1e-6 (strategy/staged.py:318-339) | the three holds and the release read that stage's end point (refine.py:1691, :1096, :3953) | #481's ramp under `mccusker_structural`, at 1e-6 and 1e-9 | S3 |
| C19 | Le Bail intensities, `instrument.background.*` | `intermediate_ftol` | `lebail_update` after each stage's solve (refine.py:4232) | #740's synthetic LaMnO₃-like pattern | S4 |
| C20 | `instrument.geometry.surface_roughness.*`, `phases.*.atoms.*.biso` | roughness stage seed 0.3 (strategy/staged.py:198; refine.py:3863) | Biso still free in that stage (cumulative staging) | any lab Bragg-Brentano fixture with a roughness block, at seeds 0 and 0.3 | S7, M2 |
| C21 | `phases.N.scale`, `phases.N.atoms.*.biso` | extinction (model/extinction.py:3-14) | capillary absorption (model/absorption.py:30-47) and roughness (model/corrections.py:28-90), all degenerate with scale and B. Plan order: displacement, extinction, roughness (strategy/staged.py:395-406) | a lab fit carrying all three | M2 |
| C22 | moment `dof*` | `solve_magnetic` releases an absent site at 0.1 µB (strategy/magnetic.py:1404-1424) | `_hold_flat_moments` in every trial's `_run_stage` (refine.py:3953) | Ba₆Co₆ (GSAS-II Magnetic-III tutorial, not vendored) | S8 |
| C23 | `phases.*.cell.*` | `tie_to_parent` cell hold (strategy/magnetic.py:1454, :1482) | the solve plan's cell stage frees it. Designed | any `tie_to_parent=True` solve | S11 |
| C24 | `lor_strain`, `gauss_strain` | strain cap (params/vector.py:3783-3785) | Stephens cone and the `lor_strain` lock; absent-phase hold on a phase's widths | #140's CuO → Cu series (the strain runaway) | O2, P2 |
| C25 | `lor_size`, `gauss_size` | size cap (params/vector.py:3786-3788) | per-wavelength value scale `SIZE_LAMBDA_POWER` (params/multi.py, 2003's) | a joint X-ray and neutron fit | O3, P3 |
| C26 | `instrument.background.scale` and the weights | σ widening uses the scale the stage compiled at (model/forward.py:4011-4017) | the same scale as a free row (model/forward.py:4000-4003) | any fit with a measured blank and `fixed_sigma` | P4 |
| C27 | σ itself | `_floor_sigma` (schemas/pattern.py:43), Poisson fallback (:179), compile widening (model/forward.py:4017) | `RefinementResult.sig` floors again (schemas/results.py:1700); Bérar-Lelann scales esds only | #897's two files (one zero esd) | P5 |
| C28 | `phases.N.atoms.M.dof.*`, body origins | floating-origin hold (params/vector.py:2725) | user hold, absent-phase hold and ridge hold on the same paths | a polar-group fit with `floating_origin` set | P7, M7 |
| C29 | `phases.N.preferred_orientation.r` | March-Dollase box and its silent repair (schemas/structure.py:41-42, :256) | `tie_window` derives a tied source's window from that box (params/vector.py:1026); unseen-phase hold | a textured minor phase | P8, M8 |
| C30 | zero shift, `sample_displacement`, capillary offsets | their default boxes (schemas/instrument.py:2249, :1227-1241) | layer 2's geometry-keyed position actions (`report/layer2._POSITION_ACTIONS_BY_GEOMETRY`) | 11-BM, where zero and displacement ride to a bound (WP-1073) | P11 |
| C31 | `phases.N.extinction` | skip gate (model/forward.py:3951-3953) | extinction stage frees it (strategy/staged.py:406); absent-phase hold (refine.py:513, :1571) | a weak phase with extinction declared | M1 |
| C32 | `instrument.geometry.axial_sl`, `axial_hl` | FCJ sizing floor (model/forward.py:3698-3706) | LM exact step lands the ratio on its zero bound (WP-1953) | a lab fit freeing axial divergence | M3 |
| C33 | the frozen window and reflection list | `REFLECTION_MARGIN_DEG` and `WINDOW_MIN_DEG` / `window_slack_deg` (model/forward.py:3743, :3890) | zero shift and geometry shift (model/forward.py:3709-3724); Pawley `off_data` flag (:3966) | a series pattern cold-fitted from a cell 0.1 % short (WP-1459) | M5 |
| C34 | the Pawley intensity block | equal-split restraint (model/forward.py:3146-3197) | mode-fixed `.scale` and `.atoms.`; `restraint_weight_scale` (model/forward.py:3130) | FAP Pawley | M6 |
| C35 | Le Bail buffer `hkl_intensity` | equal-start seed (model/forward.py:3964) | floors (:2913, :2924, :3046); series carry as `ReflectionState` | #740 | M11 |
| C36 | `instrument.background.c0..cN` | `auto_background(seed=True)` writes start values (background/auto.py:101, :125-126) | Le Bail partitions at stage compile against the background at that moment (WP-1542) | #740's pattern | B2 |
| C37 | `instrument.background.scale`, `c*` | a free measured-background scale | the Chebyshev coefficients describing the same curve (background/select.py:108-112) | any fit with `BackgroundFixedPlusChebyshev` and a free scale | B7 |
| C38 | a free cell and a free wavelength | `check_wavelength_against_cell` (optimize/least_squares.py:2391) | the joint rule in params/multi.py (2003's) | a joint fit freeing λ | P10 |

## Interactions inside one action (not a pair, listed so no one re-finds them)

- Two eigenvalue cuts on one normal matrix: the LM step discards below ε·max(m, n)·λ_max
  (optimize/lm.py:749, about 2e-12 for 10⁴ rows), the covariance below 1e-15
  (`PINV_RCOND`). A direction between the two gets no step and a finite, very large
  variance. (O6)
- Four esd scales for one parameter: the reported esd carries √χ²_red and the
  Bérar-Lelann factor f; the absent-phase test carries neither; the moment-angle test
  χ²_red·f²; ΔBIC charges N/f². A "3σ" means three different things across the package.
  (O7, O8)
- On-face tolerances: `lm._ON_FACE` 1e-9 against `STEPHENS_CONE_TOL` and
  `RESOLUTION_CONE_TOL` (strategy/staged.py:1266, :1596) are equal by comment only. (O10)
- Termination: `intermediate_ftol`, the 1e-9 literal, LM's three-run rule and
  `_PREDICTED_FLOOR` jointly decide when a stage stops. (O12)
- TRF's start nudge 1e-12 (optimize/least_squares.py:942) against scipy's `active_mask`
  rtol 1e-12; possibly meant to agree, unverified. (O5)
- `exchangeability_scan` frees held candidates and restores them in `finally`; it reads what
  `set_vary` returned, so a user hold is respected. (O13)
- Bounds order in `ParameterTable.bounds()`: window, strain cap, size cap, tie window,
  value scale. Non-commuting and documented (params/vector.py:3759-3767, read). (P6)

## Resolved or designed apart (no measurement needed)

- `auto_background`'s air term against the plans' `instrument.background.*` glob: an
  undeclared term has no row (WP-1454). (B1)
- P-spline penalty against `project.fitted_mask`: couples by design (WP-1454). (B3)
- `restraint_weight_scale` against the background penalty: c_w multiplies restraint rows
  only (model/forward.py:3119-3133). (B4)
- Dead channels against signal cutoffs at a range edge, and the three writers of
  `ObservedPeak.flags`: suggestions and indexing's (2007). (B5, B6)
