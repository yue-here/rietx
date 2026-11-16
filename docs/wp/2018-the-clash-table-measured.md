# WP-2018 — The clash table: actions that read or move the same parameter, measured both ways

Milestone: generality · Status: 🔄 2026-11-16 — 6 of 22 live pairs measured (C1, C3, C4, C7, C10, C14); 6 questions for the maintainer
Track: The audits
Depends on: —
Priority: P3 2026-10-20 — split from WP-2002 by the maintainer; 38 candidate pairs found and none measured, and one past clash (WP-1320) changed a design

## Goal

For each pair of automatic actions that read or move the same parameter in one fit, the
measured interaction: Rwp and the parameter's value with the actions in both orders, on a
dataset that exercises both. A pair that interacts is reported with what it changes and
what a caller sees; a pair that does not is recorded as measured and independent.

## Context

**Why a clash table.** The generality milestone's plan review asked each audit to keep one,
because heuristics interact (`docs/milestones/generality.md`, the plan review): WP-1320
chose the fraction profile's axis because the collapse rule fought it. WP-2002's readers
listed 38 candidate pairs, deduplicated in `docs/wp/2002-batch/clashes.md` with the
parameter, both actions at file and line, the dataset that exercises both and which reader
named it. Nothing there is measured. Line numbers are of 2026-10-19 and have moved.

**Two pairs to start with.** C1 is WP-1320's clash: `profile_fraction` pins one width per
branch and refits through `run_stage`, against the stage-start hold and the collapse
restore. WP-1320 measured it under the pre-WP-1523 significance test and never since. C3 is
the cell window, the hold and the reset-and-hold that replaced the clamp (2026-10-20).

**What changed since the list.** The B8 cell reset replaced the clamp; the position bounds
went; Le Bail and Pawley now refine the emission lines; the package's own trials inherit
`phase_support_sigma` and `correlation_guard`. Re-derive each pair's file:line before
measuring, and drop a pair one of these changes dissolved, saying why.

### Inherited

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** The closing stage meets every per-stage action, measured by WP-2002's test lanes. `AIR_SCATTER_UNDECLARED` scores lower under it only because its fixture is drawn at the 2 % windows (redrawn at 1e-3, every claim holds). The stopped-early `BOUND_HIT` case and the interval's short-of-minimum case no longer occur, since the closing stage carries the fit to its minimum. `HOLD_BLOCKED_PLAN`, `STAGE_PATH_UNKNOWN` and `HIGH_CORRELATION` name the closing stage. A per-stage finding repeated on the same paths is now reported once, the latest (`refine._run_plan`). Under TRF the closing stage stops CPD brucite where one S_HKL esd collapses (t = -268), LM unaffected.
- **From WP-2002 (2026-10-21, PR #1085).** C20 measured: the Suortti roughness seed, 0.3 against 0, leaves Biso, the scale and b within 2.7e-3 of an esd on five lab patterns from three laboratories (`tests/test_seed_invariance.py`), but Pitschke's c under the same literal is not invariant (zincite lands in the turned-over regime from 0). C18 measured in part: the absent-phase hold flips between `intermediate_ftol` 1e-6 and 1e-9 on cpd-1a with zircon declared, under LM (`docs/wp/2002-batch/waiting.md` § B7). Polish both orderings to a fixed point from one common start: LaB6's polish fixed points are not unique.

## Non-goals

- Fixing a clash found here. A fix is the owning audit's, or a ruling for the maintainer.
- Pairs across fits in a series (WP-2003's).

## Tasks

- [x] Re-derive the 38 pairs against the tree; drop or merge the dissolved ones with a line
      each.
- [x] Per pair, the dataset that exercises both, chosen before running.
- [ ] Measure both orders (or with and without one action, where order is fixed by the
      code): Rwp, the shared parameter, and its esd. PNGs to `tests/output/`.
- [ ] The table in this file: pair, effect, size in esds, verdict (independent, ordered,
      or a clash). A clash goes to its owner WP's `### Inherited` or to the maintainer.

## The table

Rows are added as pairs are re-derived and measured. "Read" means the file:line was re-read
against `origin/main` at 4c55b9011 (2026-11-09); nothing below is measured yet.

### Re-derivation, the C3 family (2026-11-09, read only)

The post-solve clamp to ±15 % is gone. `refine.reset_cell_runaway` (refine.py:1805, called at
:5258 and :5502, read) now puts the **whole** free cell of a phase that left
`CELL_SAFETY_FRACTION` back at the stage's start values, and the caller holds it and solves once
more (WP-2002 B8, ruled 2026-10-19). Its docstring states it writes committed values only and
never a bound the solver sees.

| # | Status | Reason (file:line, read) |
|---|---|---|
| C3 | **live, to measure** | Still a triple, with the clamp replaced by the reset: the support window (`least_squares._freeze_cell_windows`, least_squares.py:2944, called :3196; `vector.cell_window`, vector.py:606, applied :4225), the absent-phase hold, and the reset (refine.py:1805). Dataset as listed: the 68-pattern in-situ series and #481's ramp |
| C3a | **live, unchanged** | The window still binds free entries only (vector.py:4218-4226 loops `self._free_idx`), so a held cell is never windowed; the tie case stays the only one where both act |
| C3b | **dissolved** | The clamp wrote the window edge and the collapse restore the stage start. The reset now writes the stage start too, and refine.py:5360-5365 makes the two holds disjoint (a path both reach is the collapse's), so both actions write one value and one record holds each path |
| C3c | **dissolved** | The clamp is gone. The reset acts after the solve on committed values and restores the cell the stage's own residual evaluated, whose volume is positive (refine.py:1821-1826), so the degenerate-cell guard, which acts during the solve, never sees a reset value |
| C3d | **dissolved** | The clamp moved θ after the solve, under a bound test reading the first solve. Now the reset's paths are held (`set_vary(reset_hold, False)`, refine.py:5406) before the second solve (:5469), whose outcome replaces the first (:5523), and `check_guards` (called :5563) takes `free = table.free_paths` (staged.py:2283) into `bound_findings` (:2355): a reset cell is no longer a free column when the bound test runs |

### Re-derivation, C1, C2 and C6 (2026-11-09, read only)

| # | Status | Reason (file:line, read) |
|---|---|---|
| C1 | **live, to measure** | `profile_fraction` still pins one width per branch (`trial.set_vary([axis], False)`, fraction_profile.py:216) and refits through `run_stage` (:224), so each refit meets the stage-start hold and the collapse restore (refine.py:5372-5399). The module's own account of the clash (fraction_profile.py:14-23) is still dated to the pre-WP-1523 test. Dataset: `tests/test_qpa_multimodal.py`'s two-basin fixture |
| C2 | **live, narrowed, to measure** | Since #1075 each probe starts from the fit's own free set (`fresh()`, parameter_interval.py:269-279: the pinned path and every path the fit held), so a probe can no longer free a cell the fit held. Its comment says a refit may still hold *more*, since a lower pinned scale can hide a phase the fit saw: that half of the pair is what to measure. Dataset: a weak phase in a weighed mixture, as listed |
| C6 | **designed apart, confirm by measuring** | `_significance_columns` (refine.py:2205-2218) still leaves out every column that moves only displacements, occupancies and other phases' scales, so the absent-phase test cannot read a scale-B ridge as absence. The docstring's 153.7σ against 0.02σ on the fluorite is why the exclusion exists, not a measurement of the pair; the WP-2002 reader asked for one. Dataset: `tests/test_scale_b_ridge.py`'s fluorite |

### Re-derivation, C4, C5 and C7-C38 (2026-11-09, read only)

Read by three delegated read-only readers at 4c55b9011 and spot-checked here at eight of their lines (forward.py:1766, instrument.py:1224-1226, :1539, :2340-2344, vector.py:1347-1348, :2867, refine.py:1742, :5062). Line numbers are that commit's.

| # | Status | Reason (file:line) |
|---|---|---|
| C4 | **live, to measure** | Ridge hold `_hold_scale_b_ridges` (refine.py:984, called :5193 and late :5421) against the µR/µt multiplier (`_absorption`, forward.py:1310, applied :2133): the ridge probe reads a phase component that already carries A(θ) and holds the Biso/ADP columns µR shifts; nothing separates them |
| C5 | **designed apart** | The collapse set is drawn from free paths (refine.py:697, called :5347) and the ridge hold is kept out of `phase_held` through `apart` (:5295), so a ridge-held B is never restored by the collapse (:5384-5389) |
| C7 | **live, to measure** | Moment hold and turn (`_hold_flat_moments`, refine.py:1535, called :5185; turn writes :1518) against the stationary-angle test (least_squares.py:931, run :3294/:3565, read refine.py:2354): on a site held as a combination only dof2 is held (:1451-1452), so the turned dof1 stays free for the test in the same stage |
| C8 | **designed apart** | The moment hold runs after the phase hold (refine.py:5177 then :5185) and scans free paths only (:1401); the release asks only `moment_held` (:5294-5297) |
| C9 | **designed apart** | `sequential._floor_unsupported_moments` (sequential.py:1089, called :2036) acts between patterns on a copied carry source after acceptance, keeps the direction (:1151-1153) and skips rows with no verdict (:1127), never inside the fit whose collapse (refine.py:5384-5389) acted |
| C10 | **live, to measure** | The phase hold leaves a seen-lineless phase's scale free (refine.py:684, filter :697); `FLOOR_HIT` from `bound_findings` (staged.py:2057, emitted refine.py:7472) has no check against the support verdict, so a blank-frame phase can fire both |
| C11 | **designed apart** | Every seeded phase's prior significance is set to inf (refine.py:1742) before the hold reads it (:1745) |
| C12 | **live, to measure** | `seed_stephens` (vector.py:3934, called refine.py:5079-5082) skips a nonzero user-set block; such a block can start infeasible, and the cone rows are then dropped (least_squares.py:2433, built :3147). The default seed itself starts inside the cone |
| C13 | **gone** | Under a Stephens block every width reader takes `CompiledModel.lor_strain_term` (forward.py:1766), which is 0, so a locked nonzero `lor_strain` no longer enters the width sum (WP-1467) |
| C14 | **live, to measure** | Γ_G² ≥ ε rows (`gaussian_width_inequalities`, least_squares.py:2478, added :3149) against `bound_findings`' exact active set (`_exact_active_bounds`, staged.py:2032, read :2147), which covers box sides only: a U, V or gauss_* held on a row is never reported at a bound. W now has a box floor at ε (instrument.py:1539), so W alone is caught |
| C15 | **designed apart** | W's box floor equals the clamp's threshold (`TCHZ_BOUNDS`, instrument.py:1539; `_MIN_GAMMA_G2`, caglioti.py:88), and under LM the rows hold total Γ_G² ≥ ε. `FLOOR_SEEDS` (vector.py:1119) now sizes only the FD step, and lm.py:184-185 is no longer a polish. Not covered: TRF and joint fits build no rows, so a negative U or V can still reach the clamp |
| C16 | **designed apart** | The mode-fixed drop (refine.py:5066-5070) runs before the seeds (:5072-5077), as the comment at :5062 requires |
| C17 | **designed apart** | `_answer_significance` frees only `phase_held` (refine.py:2355, called :5302), drawn from free paths (:697), and `set_vary` never frees a held entry (vector.py:3822) |
| C18 | **live, to measure** | `intermediate_ftol` 1e-6 (staged.py:352, `stage_ftols` :429-465, plan.py:73) against the holds and release that read each stage's end point (refine.py:5177, :5184, :5193, :5307). WP-2002 measured one flip (C18 in § Inherited) |
| C19 | **live, to measure** | `lebail_update` after each stage's solve (refine.py:5557) still runs at the 1e-6 end point of intermediate stages |
| C20 | **live, measured in part** | `ROUGHNESS_SEED` 0.3 (staged.py:224, applied refine.py:5072-5077) with Biso still free under cumulative staging (staged.py:510). WP-2002 measured it (§ Inherited): invariant on five lab patterns except Pitschke's c |
| C21 | **live, to measure** | Extinction (extinction.py:174, stage staged.py:535) and Suortti/Pitschke roughness (corrections.py:28, :62, stage staged.py:536) are both degenerate with scale and Biso and free together in the late stages; the plan orders only when each is freed. µR is a declared float, not refined (instrument.py:1264) |
| C22 | **live, to measure** | `solve_magnetic`'s release (magnetic.py:1469, now 0.05 × seed, `SOLVE_RELEASE_FRACTION` :263) against `_hold_flat_moments` in every stage (refine.py:5184) |
| C23 | **designed apart** | `tie_to_parent` holds the cell (magnetic.py:1369), `_without_cell` strips the plan's cell glob (magnetic.py:1505, used :2396, :2465), and `set_vary` refuses held entries (vector.py:3822) |
| C24 | **gone** | Under a Stephens block `lor_strain` is force-fixed (vector.py:1347-1348) and read as 0 (forward.py:1766), and `bounds()` runs over free entries only (vector.py:4219), so the strain cap (vector.py:886) cannot reach it; the cone acts on the microstrain DOFs only (least_squares.py:2391) |
| C25 | **live, reconciled** | Size cap (vector.py:1005, applied :4231-4234) and `SIZE_LAMBDA_POWER` (multi.py:77, used :147) both act on the shared size column of a joint fit; each table reads its cap in its own scaled units and the bounds are intersected (least_squares.py:3045, docstring :3054-3059). Measure on a joint X-ray and neutron fit |
| C26 | **live, to measure** | σ widening uses the compile-time background scale (forward.py:4643-4651) while the same scale is a free design row (:4638-4640); the comment at :4644-4647 accepts the per-stage lag |
| C27 | **live, idempotent by reading** | `_floor_sigma` (pattern.py:39), Poisson fallback (:189-191), compile widening (forward.py:4651), and `RefinementResult.sig` floors again with the same function (results.py:2437-2442), a no-op on an already floored σ. The zero-esd floor stays until WP-1952 (pattern.py:28-31) |
| C28 | **designed apart** | `_fix_origin` holds through `Entry.held` (vector.py:3150); `_holdable` skips held, tied or locked entries (:3212), the take-back respects caller holds (:3189-3191), stage holds use `set_vary` on free paths (refine.py:711), and the ridge hold acts on B, not on a DOF |
| C29 | **live, rarely binding** | `MARCH_R_MIN` (structure.py:62) with its repair (:276-289), against `tie_window` (vector.py:1033, called :2796) and the unseen-phase hold (refine.py:1684). WP-2002 B9 cut the box to a 1e-6 pole guard with no ceiling (structure.py:43-60) |
| C30 | **gone** | Displacement, both capillary offsets and `zero_shift` have had no default box since 2026-10-20 (instrument.py:1224-1226, :1239-1254, :2340-2344), so there is no bound for layer 2's position actions (layer2.py:84, read :1014) to meet |
| C31 | **designed apart** | The extinction skip gate (forward.py:4557-4560) skips only at exactly 0 and outside `moving_paths`, so a stage freeing extinction turns it off; the holds come after compile (refine.py:5170-5173) and can only leave the gate evaluating an E it could have skipped (cost, never a wrong value) |
| C32 | **designed apart** | WP-1953 made the FCJ profile continuous at a zero aperture (fcj.py:22-29, :95-102), and the sizing floor (forward.py:4326-4329, `AXIAL_SIZING_FLOOR` :312) applies whenever either aperture is positive or free (:4318-4321), so landing on the zero bound (instrument.py:1255-1256) meets no jump |
| C33 | **live, to measure** | The reflection list and windows are frozen at compile-time zero and shift (`REFLECTION_MARGIN_DEG` forward.py:331, :4129-4130; `WINDOW_MIN_DEG` :220; `window_slack_deg` :4501-4502) while the now unbounded zero and shift move in the stage (:4333-4340), and Pawley's `off_data` flag (:4574) reads the compile-time list; `rewindow` (:4802) resizes windows only |
| C34 | **designed apart** | The phase scale is mode-fixed in Pawley (refine.py:341); c_w scales the soft-restraint rows only, and the Pawley rows are their own stripe (least_squares.py:1790-1795, :2326-2333; forward.py:3608-3611, :3624) |
| C35 | **live, to measure** | Equal-start seed (forward.py:4571), floors (:638, :3349, `LEBAIL_INTENSITY_FLOOR` :586) and the carried `ReflectionState` (refine.py:5131-5133, `_restore_lebail` :9603) all write `hkl_intensity` in one fit |
| C36 | **live, to measure** | `auto_background(seed=True)` (auto.py:92, :161-165, :187-188) is opt-in (default False, :97); by default the stage-start partition (refine.py:5141-5144) runs against an unfitted background, as the docstring says (auto.py:122-130) |
| C37 | **live, to measure** | A free measured-background scale (forward.py:4638-4640) and the Chebyshev rows (forward.py:4609) describe the same curve; `select.py` (:100, :114-118) only counts the scale in its BIC, and nothing in the fit separates them |
| C38 | **designed apart** | `check_wavelength_against_cell` (vector.py:2844, called least_squares.py:3194) returns early for a joint table (vector.py:2867), which hands λ to `check_wavelength_freedom` (multi.py:1377, :461-464) |

### Datasets for the live rows (2026-11-09, task 2, chosen before running)

Chosen from `tests/data/README.md` and the acceptance suites; no fit was run. Held-out families (yue-here/rietx#1052) are excluded.

| # | Dataset | Why |
|---|---|---|
| C1 | `tests/test_qpa_multimodal.py`'s synthetic two-basin trace | The pair's own fixture (WP-1320): known basins, so a profile that the collapse restore deflects is visible against the truth |
| C2 | `qarr/` round robin (`tests/test_acceptance_qpa_roundrobin.py`), the sample with the smallest weighed fraction | A weak phase with a weighed answer; an interval on its scale probes low enough to make a refit hold more than the fit did |
| C3 | `seqrefine_cucr2o4/` (WP-2003 family B: the CuO minor phase along the ramp) and `tests/test_absent_phase.py`'s fixture | The 68-pattern in-situ series of the original list is not vendored; the CuO minor phase fades along a vendored ramp, and the absent-phase fixture plants a phase whose cell can run |
| C3a | `tests/test_absent_phase.py`'s fixture plus a user tie from the absent phase's cell to the visible phase's | Read in code, the window binds only through such a tie; no vendored fit carries one, so the case is built on a fixture whose answer is known |
| C4 | `tests/test_scale_b_ridge.py`'s fluorite with µR declared, and 11-BM SRM 660a (`tests/test_acceptance_capillary.py`) for ΔB alone | The fluorite fires the ridge hold; SRM 660a pins the ΔB = c(µR)λ²/2 the hold must not undo |
| C7 | `gsas2_hb2a_cr2wo6_4K.dat` and `gsas2_bt1_lamno3_50K.gsas` (`tests/test_acceptance_magnetic.py`, `…_lamno3.py`) | Two unrelated magnetic families with published moments, on two instruments; both carry moment angles at symmetry-fixed directions |
| C10 | `tests/test_absent_phase.py`'s fixture with the absent phase's scale on its floor | Fires `PHASE_UNCONSTRAINED` by construction; whether `FLOOR_HIT` also fires on that scale is the question |
| C12 | brucite (`tests/test_acceptance_stephens.py`) started from a nonzero user block outside the cone | The default seed is inside the cone, so only a caller's infeasible block reaches the dropped-rows branch |
| C14 | 11-BM NAC (`tests/test_acceptance_nac.py`) | W sat on its floor there before WP-1938; with U, V free a Γ_G² row can bind without a box side |
| C18 | `qarr/` cpd-1a with zircon declared, at `intermediate_ftol` 1e-6 and 1e-9, and `seqrefine_cucr2o4/` | WP-2002 B7 already saw the hold flip on cpd-1a; the ramp adds a phase near the support threshold across many fits |
| C19 | #740's synthetic LaMnO₃-like Le Bail pattern (`tests/test_lebail_cycles.py`) | The listed fixture; Le Bail intensities extracted at a 1e-6 end point against a 1e-9 one |
| C20 | the five lab patterns of `tests/test_seed_invariance.py`, Suortti and Pitschke | WP-2002 measured Suortti invariant and Pitschke's c not; the remaining measurement is Pitschke's, from both seeds |
| C21 | the same five lab patterns under a plan freeing extinction and roughness | Lab Bragg-Brentano fits from three laboratories; both corrections free together is the case |
| C22 | `gsas2_hb2a_cr2wo6_4K.dat` through `solve_magnetic` | Ba₆Co₆ is not vendored; Cr₂WO₆ is a solved magnetic structure whose release can be watched against the moment hold |
| C25 | the published Nd₂Ru₂O₇ X-ray and neutron pair (README § Refinable-wavelength, `tests/test_joint_xray_neutron.py`) | The only vendored joint fit of one specimen at two wavelengths, where the size cap and the λ scale meet |
| C26 | Si SRM 640c in Kapton with its blank (`11BM_Kapton.xy`, README § The background-peak worked example), `fixed_sigma`, scale free | A measured blank whose scale the fit can move, so σ's compile-time scale and the free scale can part |
| C27 | an esd-column file with one σ set to 0 (a copy of a vendored `.xye`) | #897's two files are not vendored; the pair is idempotent by reading, so one planted zero checks it |
| C29 | no vendored textured minor phase: a synthetic two-phase pattern (`tests/_synthetic_weak_lines.py`) with March r on the minor phase | Needs building; rarely binding since B9, so it ranks last |
| C33 | 11-BM NAC cold-fitted from a cell 0.1 % short, Rietveld and Pawley | WP-1459's case: zero and shift move inside a stage whose reflection list is frozen |
| C35 | `seqrefine_cucr2o4/` chained under Le Bail | A series carry of `ReflectionState` meeting the equal-start seed and the floors |
| C36 | #740's pattern (`tests/test_lebail_cycles.py`) and `tests/test_lebail_background_hump.py` | A partition against an unfitted background, with and without `auto_background(seed=True)` |
| C37 | `11BM_Kapton.xy` with `BackgroundFixedPlusChebyshev` and a free scale | The measured curve and the Chebyshev rows describing it are both present |

### Measured (2026-11-16, task 3)

Scripts and their raw output are in `docs/wp/2018-measure/` (one JSON line per arm; PNGs to
`tests/output/wp2018/`). The package under test is `origin/main` at bc77a934e, unchanged on
this branch. An arm switches one action off by patching the function that takes it, or by
`phase_support_sigma = None` where the package offers that switch; each script's docstring
names its arms. "esd" is the arm-with-the-action's own esd of that parameter. The verdict
column is left to the maintainer: the rows say what moved and by how much, and § Questions
for the maintainer asks what the table should call it.

**C1, `profile_fraction` against the support hold and collapse** (`fraction_profile.py`; macOS
arm64, `[dev]`). The two-basin trace fit (Rwp 0.06887, W(CaF₂) = 0.93(33) %), then the shipped
12-point FWHM grid on `phases.1.lor_strain`, each refit warm from the last, in two arms: the
probe as shipped (`phase_support_sigma` 3) and the same refits with it `None`.

| FWHM (°) | 0-1.50 (8 points) | 3.47 | 7.99 | 18.4, 42.5 |
|---|---|---|---|---|
| shipped: what the refit did | 0-0.12: nothing held; 0.28-1.50: the cell held at stage start and released at the answer | cell held at stage start, never released | same | nothing held |
| W shipped − W no_support | under 4e-5 pp | −0.013 pp (5.692 % vs 5.705 %) | −0.003 pp | 0 |
| Δχ² shipped − no_support | 0 | +0.062 | +0.001 | 0 |
| CaF₂ scale, shipped − no_support | 0 | +0.007 esd | −0.004 esd | 0 |
| admissible (cut 5.19) | first four yes | no (Δχ² 14.1) | no (15.6) | 18.4 no, 42.5 yes |

The probe's own answer is identical in both arms: range 0.930-77.07 %, excess 117.77, the same
admissible flags, `QPA_FRACTION_RANGE` alone. The hold keeps the cell through the solve at two points of twelve (at three more it is released
at the answer and the refit matches the free one to 4e-5 pp), and both lie in the barrier, outside the cut by 9-10 in Δχ² either way. WP-1320's account (the width held
at 4× and 8× the fitted scale and χ² ran away, `fraction_profile.py:14-23`) is not reproduced
under the WP-1523 test: χ² at the held points is 0.06 and 0.001 above the free refit. The
module docstring still states the old measurement as current.

**C3, the support window, the support hold or collapse, and the cell reset**
(`absent_phase.py`; macOS arm64, `[dev]`). `tests/test_absent_phase.py`'s fixture (LaB₆, plus a
LaB₆ copy at a = 5.2 Å and scale 1e-9 that is not in the pattern), `mccusker_default`, eight arms:

| Arm | absent a (Å) | absent scale | Rwp | what acted, by stage | codes naming phase 1 |
|---|---|---|---|---|---|
| default | 5.2, held | 0 (at its floor), esd 5.8e-9 | 0.041557 | hold from `cell` to `closing` | `PHASE_UNCONSTRAINED` (0.0σ), `FLOOR_HIT` (ρ +0.0088) |
| no_reset | identical to default, every digit | | | | |
| no_hold | identical to default to 1e-14 relative | | | the collapse at the answer takes the cell in every stage instead | same |
| window_only (no hold, no collapse) | 5.0243(21) | 1.51(67)e-8 | 0.041525 | nothing | `PHASE_UNCONSTRAINED` (2.62σ) |
| no_support (`phase_support_sigma=None`) | identical to window_only, every digit | | | | same |
| neither (no_support, no reset) | identical to window_only, every digit | | | | same |
| escape_no_hold (positive arm) | 5.2, held | 0 | 0.041557 | the `cell` solve is made to answer 1.3 × a: reset and collapse both reach the path; the collapse records it, `cell_reset` stays empty | `CELL_RUNAWAY` (1.56 Å), `PHASE_UNCONSTRAINED`, `FLOOR_HIT` |
| escape_no_support (positive arm) | 5.0243(21) | 1.51(67)e-8 | 0.041525 | the reset puts a back at 5.2 and holds it for the `cell` stage; later stages refit it to the free answer (to 2e-10 Å) | `CELL_RUNAWAY`, `PHASE_UNCONSTRAINED` (2.62σ) |

The no_hold patch also empties the "unseen" set the width-twin hold reads (refine.py:5227); no twin hold acts in either the default or the no_hold arm here, so the numbers are unaffected. On this fixture the three actions never meet. The default cell window changed no digit (the
free answer, 5.024 Å, is inside it, and window_only equals neither exactly). The reset fires only
when an escape is injected (it does not walk since WP-1938, as `test_cell_runaway_safety.py`
says). The hold and the collapse are interchangeable: either one alone gives the default answer.
The two answers the caller can get differ in the absent phase alone. Held: a = 5.2 with no esd and
the scale on its floor. Free: a phase at 2.62σ with a cell at 5.0243(21) Å, which is noise fitted
by a phase that is not there. The visible phase moves 7e-9 Å in a (0.002 esd) and 0.004 esd in
scale between the two. When the reset and the collapse reach one path, the records stay disjoint
as refine.py:5391-5394 says, but `CELL_RUNAWAY` still fires beside `PHASE_UNCONSTRAINED` on the
same path. The second C3 dataset, the CuCr₂O₄ ramp, has no fit harness in the tree
(`tests/data/README.md` § WP-2003 series family B: "Nothing in the tree fits these files yet"),
and was not run.

**C10, the phase hold leaves the scale free, against `FLOOR_HIT`** (same fixture and arms).
Under the default plan both codes fire on the absent phase in the same fit, with no forced
value: the scale ends exactly on 0 by itself, `FLOOR_HIT` names `phases.1.scale` (ρ +0.0088,
`at_bound` True, esd 5.8e-9), and `PHASE_UNCONSTRAINED` names `phases.1.cell.a` at 0.0σ. Without
the hold (window_only, no_support) the scale leaves its floor (1.51(67)e-8), `FLOOR_HIT` does
not fire and `PHASE_UNCONSTRAINED` reads 2.62σ. So the hold (or, without it, the collapse) is
what puts the scale on its floor here, and the two codes name different paths of one phase.
Whether the caller should see one finding or two is § Questions for the maintainer, (3).

**C14, the Γ_G² ≥ ε rows against the bound test** (`gaussian_rows.py`; macOS arm64, `[dev]`;
the NAC arms also run on a Linux x86_64 machine, output not committed: Rwp equal to 12 digits and U to 7e-10 relative). Three arms:
LM as shipped, LM with `gaussian_width_inequalities` building no row, and `solver="trf"`.

On 11-BM NAC (`tests/test_acceptance_nac.py`'s protocol) the rows never come near binding: the
smallest Γ_G² over each phase's reflections is 1179 ε (NAC) and 1187 ε (CaF₂), no stage
truncated a step, and LM without the rows is the shipped fit to every digit. TRF lands within
3e-7 relative of it in U, V, W and X (Rwp to 4e-11). NAC does not exercise C14 since WP-1938 moved W's floor to ε.

So the positive arm is a synthetic LaB₆ pattern (`test_gaussian_width_floor.py`'s
construction and plan) whose true Γ_G² = 9e-4·(tanθ − 0.1)² touches 0 at 2θ = 11.43° with W
interior (9e-6):

| Arm | Γ_G² at 11.43° | U, V, W, X: shift from the no-row fit (shipped esds) | distance from the truth (own esds) | what the caller sees |
|---|---|---|---|---|
| shipped (rows) | exactly ε (ratio 1 − 2e-13); 6 steps held in `profile`, 3 in `closing` | −0.60, +0.61, −0.40, −0.67 | +0.26, −0.33, +0.52, −0.05 | `CONSTRAINT_ACTIVE` (info, `where` empty, the message names the block "instrument.profile (phases.0): 3" in stage 'closing'); `at_bound` False on U, V, W; no `BOUND_HIT` or `FLOOR_HIT`; esds as for a free fit |
| no_rows | −1.21 ε, at 1 of 17 reflections | 0 | +0.83, −0.91, +0.90, +0.68 | `RESOLUTION_NOT_POSITIVE` (warning, names U, V, W: 158 of 4200 points, worst −1.21e-8 deg²) |
| trf | −1.21 ε, the no_rows answer to 2e-9 relative in U-X | 0 | same | same |

What the re-derivation row said is half right. A width held on a row is reported, by
`CONSTRAINT_ACTIVE`, which the 2026-11-09 reading missed. But that record names no path, and
`at_bound` and `bound_findings` read box sides only, so U, V and W each read "not at a bound"
with an unconditional esd while the answer is held at ε. The rows move the answer 0.4-0.7 esd,
here toward the truth (which lies on the face). Both RESOLUTION_UNCONSTRAINED and
HIGH_CORRELATION (U-V, ρ −0.988) fire in all three arms. Question (4) below.

**C4, the scale-B ridge hold against capillary absorption** (`ridge_absorption.py`; macOS arm64,
`[dev]`; the LaB₆ `plain` arm also on a Linux x86_64 machine, output not committed: Rwp equal to
6e-14, B to 1.4e-11 Å²). Capillary absorption is A = K·exp(c·sin²θ), an exact
reparameterisation of each phase's {scale, B} whose content is ΔB = c(µR)λ²/2; the ridge hold
reads a phase component that carries A and holds the B column A's shift lands on. The probe of
every arm is recorded each time the runner asked it. The dataset row named the fluorite as the
phase that fires the hold; on that fixture it is the iron (one reflection in range, (110)), and
the fluorite is the separable neighbour.

*The ridge fixture* (`tests/test_scale_b_ridge.py`'s four phases, noise seed and `cell_then_B`
staging, moved to the `debye_scherrer` preset at Cu Kα1 with the Bragg-Brentano profile, the
pattern drawn with µR = 1.0, predicted ΔB = 0.48869 Å²):

| Arm | Fe B (Å²) | Fe separation, stage `b` (floor 6.3e-8) | Fe scale ÷ corundum scale, relative to mu_hold | Fe wt% | Rwp |
|---|---|---|---|---|---|
| mu_hold (shipped) | 0.35, held in `b`, `w`, `closing` | 5.9e-13 | 1 | 1.5084 | 0.0827765366 |
| mu_nohold (positive arm) | 0.052(2.9), free | 5.9e-13 | 0.9644 | 1.4556 | 0.0827765366 |
| nomu_hold (µR undeclared) | 0.35, held in the same stages | 7.4e-13 | 1.0613 | 1.5994 | 0.0827765366 |
| nomu_nohold | 0.049(0.57), free | 7.4e-13 | 1.0231 | 1.5427 | 0.0827765366 |

Rwp agrees across all four arms to 4e-11 (the reparameterisation and the ridge are both flat).
A changes no hold decision: the probe reads corundum 0.223 against 0.228, zincite 0.193 against
0.190 and iron 5.9e-13 against 7.4e-13 with µR declared and not, so the same phase is held in the
same stages, and `SCALE_B_INSEPARABLE` names `phases.3.atoms.0.biso` alone in both hold arms. Every
site of the three separable phases moves by ΔB between the declared and undeclared arms to within
1.3e-5 Å² of the prediction (corundum 7e-8 and 8e-8, zincite 8e-6, fluorite Ca +1.2e-5 and F
−2e-6, against esds of 1.2, 4.3 and 3e3-1e4 Å²). The iron cannot carry its share: held, its B
takes none of ΔB, and its scale takes A at (110) instead, 1.0613 measured against
exp(2ΔB·s²(110)) = 1.0613 predicted, so its weight fraction moves 6.0 % relative (0.44 of the
scale's own esd) between declaring µR and not. Free, its B walks from the 0.35 it was handed to
0.05 in both arms and takes 0.0033 Å² of ΔB (0.7 %), and the fraction moves the same 6.0 %. So
the 6 % is the ridge's, not the hold's: no setting of an iron B the data cannot see absorbs a
correction the data cannot see either. The fluorite's separation falls to 1.6e-6 (µR declared)
and 4.0e-6 (not) by the closing stage, 25-64 times the floor, in both arms.

*11-BM SRM 660a* (`tests/test_acceptance_capillary.py`'s protocol, dispersion off, µR estimated at
0.6788): the hold never fires, plain or corrected (separation 0.771-0.780, seven orders above the
floor); B(La) and B(B) move by 0.01687472 Å² between the arms, 2.3e-9 and 2.9e-9 Å² from the
predicted ΔB, and Rwp by 3e-14. The positive arm `corrected_forced` raises the floor to 2 so the
hold takes both B in the `biso` and `closing` stages: they stay at the 0.3 Å² handed in, ΔB is
lost entirely, `SCALE_B_INSEPARABLE` fires, and Rwp goes from 0.08809 to 0.11246. Had the hold
fired on SRM 660a, the ΔB measurement would have shown it.

**C7, the moment hold and turn against the stationary-angle test** (`moment_hold.py`; the
rhombohedral arms on macOS arm64, `[dev]`; Cr₂WO₆ and LaMnO₃ on a Linux x86_64 machine, py3.12).
Four arms: shipped; `no_hold` (`_flat_moment_scan` answers nothing, so no moment direction is held,
released, collapsed or turned); `no_turn` (`_turn_onto_meridians` turns nothing, so the azimuth is
held where the stage found it); `no_test` (`stationary_angle_test` answers nothing, so every angle
stays a column of the covariance).

*The two datasets chosen for the row never meet the pair.* On HB-2A Cr₂WO₆ at 4 K and BT-1 LaMnO₃
at 50 K (Pn′ma′), each with its acceptance protocol, the hold finds no flat direction in any stage,
so `no_hold` and `no_turn` are the shipped fit to every digit. The test acts alone: it zeroes the
polar angle in every stage (Cr₂WO₆ stationary at π, the moment along a, statistic ≤ 0.002 against
the cut 2.706; LaMnO₃ at π/2, 0.49-0.57), and `MOMENT_ANGLE_STATIONARY` names it. With the test
off no value moves; the modulus esd goes from 0.0450 to 0.0507 μ_B (Cr₂WO₆) and 0.0433 to 0.0482
(LaMnO₃), and the polar angle carries an esd (0.40 and 0.062 rad) where shipped it carries a profile
interval ([2.910, 3.373] and [1.400, 1.742] rad). Cr₂WO₆'s site has two moment DOFs and LaMnO₃'s
plan frees two of its three, and a combination needs the polar angle and the azimuth both free.

*The pair meets on a combination site*: `tests/test_magnetic.py`'s #599 fixture (one Mn on
rhombohedral axes, uniaxial about [111], start (3, 0.2, 0.2)), with the truth off the axis, (1.5, 2,
3) at ψ = 10.20° from [111], and on it, (2, 2, 2), each noise-free (`rh`, `rh111`) and with Poisson
noise (`rhn`, `rh111n`). The noisy rows:

| Arm | truth at 10.20°: ψ, Rwp | what the test said of the polar angle | truth on [111]: ψ, Rwp | what the test said |
|---|---|---|---|---|
| shipped | 10.34°, 0.07872 | not stationary (statistic 107-111): esd 0.0087 rad | 1.13°, 0.08332 | stationary (0.012-0.029): interval [1.070, 1.240] rad, `MOMENT_ANGLE_STATIONARY` |
| no_test | the shipped fit to every digit | — | the shipped fit to every digit; polar esd 0.089 rad, modulus esd 0.0311 against 0.0247 μ_B | — |
| no_turn | 27.84° (#599's trap), 0.1446 | **stationary** (−4e-6): interval [1.078, 1.114] at the trap's closest approach | 27.84°, 0.1591 | **stationary** (−9e-6), the same point |
| no_hold | 10.34°, 0.07872 | the pair fails jointly (107); the polar angle alone **stationary** (6e-10): interval [0.958, 1.351], azimuth esd 0.0097 rad, `unmeasured_directions` empty | 1.13°, 0.08332 | both stationary jointly (0.012-0.029), `unmeasured_directions` empty |

The noise-free rows say the same at every arm (ψ 10.199° and 0.0025° shipped, against 10.20° and 0
true; 27.84° without the turn), with the test's statistic read at roundoff in the closing stage
(χ²_red near 1e-18).

So the shipped order is what keeps the test's verdict true: the hold and the turn act at stage
start and the test reads the turned polar angle after the solve, and it gets both truths right
while changing no value (`no_test` is bit-identical in all six datasets; only esds move). Take
either half of the hold away and the test still answers, wrongly and confidently. Without the turn
the polar angle sweeps a meridian that never comes within 27.8° of [111], the test finds the
meridian's closest approach a stationary point (it is one, along that meridian), and
`MOMENT_ANGLE_STATIONARY` presents a trapped answer at Rwp 0.145 as a symmetry-fixed direction with a
0.036 rad interval. Without the hold the test refits the azimuth while it moves the polar angle,
which the flat cone lets it do at no cost, so a flat combination reads as a stationary polar angle,
the azimuth gets an esd, and the report says no direction is unmeasured. The test has no guard of
its own against either; it relies on the hold having run.

### Questions for the maintainer (2026-11-16)

Measured above; the verdict on each is a ruling, so none is written into the table yet.

1. **C1.** On the two-basin fixture the support hold changes the width profile's answer by
   nothing (range, excess and admissible flags identical; the two held points move 0.013 pp in
   W and 0.06 in χ², both outside the cut). Is C1 recorded *independent* on this evidence, and
   should `strategy/fraction_profile.py`'s docstring (lines 14-23, the pre-WP-1523 account of
   χ² running away at 4× and 8×) be rewritten to this measurement, and by which WP?
2. **C3.** On the absent-phase fixture the window and the reset never act, and the hold and
   the collapse each give the default answer alone. The measured difference the triple makes
   is the absent phase's own row: held at 5.2 Å with no esd, or free at 5.0243(21) Å and 2.62σ.
   Is that the *designed* outcome (the row reads as the hold's purpose), so C3 is recorded
   independent on this fixture? And is the CuCr₂O₄ ramp still owed for C3, given that it needs
   a series harness the tree does not have (WP-2003's family B)?
3. **C3 and C10, two codes for one cause.** When the reset and the collapse reach one path,
   `CELL_RUNAWAY` fires beside `PHASE_UNCONSTRAINED` on `phases.1.cell.a`; under the default
   plan, `FLOOR_HIT` on the scale fires beside `PHASE_UNCONSTRAINED` on the cell. Should a
   caller see both (each names a different act), or should one defer to the other? Neither
   is a wrong value; the question is what a reader is told.
4. **C14.** When the answer sits on a Γ_G² row, the only record is `CONSTRAINT_ACTIVE` with an
   empty `where`; U, V and W read `at_bound` False and carry free-fit esds. Should
   `bound_findings`' active set (and so `at_bound`) take the rows' active set as it takes the
   box's (WP-1929's "a row on its bound stays in the matrix" rule, extended to a combination),
   or should `CONSTRAINT_ACTIVE` carry the paths in `where`, or both? NAC, the dataset chosen
   for the row, never reaches it; the synthetic touching-truth pattern does.
5. **C4.** Absorption changes no ridge-hold decision, and the hold never fires on SRM 660a
   (ΔB lands to 3e-9 Å²). On the ridge phase, an undeclared µR moves the weight fraction
   6.0 % relative (0.44 of the scale's esd) with or without the hold, because B there cannot
   carry ΔB either way. Is C4 recorded *independent*? And should `SCALE_B_INSEPARABLE`, which
   already states the fraction's sensitivity per Å² of B, also say that an undeclared
   absorption correction lands on that phase's fraction rather than its B?
6. **C7.** On Cr₂WO₆ and LaMnO₃ the hold never acts, so the pair never meets; on the #599
   combination fixture the shipped order gives the test's verdict right both ways (not
   stationary at 10.3°, stationary on [111]) and the test moves no value. Is C7 recorded
   *ordered*, the order being load-bearing? The `no_hold` and `no_turn` arms show the test
   itself cannot tell a flat combination or a trapped meridian from a symmetry-fixed direction:
   should it carry a guard of its own (refusing a candidate whose Δχ² vanishes because another
   free angle absorbs the move), or is the hold's precedence the design? And should the row's
   datasets be replaced by the #599 fixture, since the two chosen ones cannot exercise it?

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Every pair in `2002-batch/clashes.md` has a measured row or a stated reason it was dropped.

## References

- WP-2002, `docs/wp/2002-batch/clashes.md`; WP-1320 (the fraction profile's clash);
  WP-1523 (the significance test).
- `docs/milestones/generality.md`, the plan review's clash-table requirement.

## Handover log

- **2026-11-16** — The first four pairs of the clash table are now measured, each with and without the action in question. On the datasets chosen for them none changes an answer anyone reads: the width profile of a trace phase gives the same range whether or not the support hold acts during its refits, and on the planted absent phase the cell window and the cell reset never act while the hold and the collapse each produce the default answer alone, and on NAC the Gaussian-width rows never come near binding. A synthetic pattern built to reach that floor shows the rows moving the widths 0.4-0.7 esd, toward the truth. What the measurements did find is about what a caller is *told*: when the fit sits on the Gaussian-width floor of a combination of U, V and W, the only record is an unlocated info message, and the three widths each say "not at a bound" with a free-fit esd; and one absent phase can draw two findings (support plus floor, or support plus runaway) for one cause. Four questions for the maintainer are written into § Questions for the maintainer; nothing was fixed, as the non-goals require. *Done* (PR #1576, docs and measurement scripts only): § Measured (2026-11-16, task 3) holds C1, C3, C10 and C14 with numbers and sizes in esds; scripts and raw JSON lines in `docs/wp/2018-measure/` (`common.py`, `fraction_profile.py`, `absent_phase.py`, `gaussian_rows.py`, three `*_results.jsonl`), PNGs to `tests/output/wp2018/`. Task 3 not ticked: 18 live pairs are still unmeasured. *Measured*: C1 on the two-basin trace, the hold keeps the cell through 2 of 12 grid refits, both in the barrier (at 3 more it is released at the answer), W moves 0.013 pp and Δχ² 0.06, the profile's range 0.930-77.07 % and excess 117.77 identical; WP-1320's runaway is not reproduced under WP-1523's test. C3 on the absent-phase fixture over eight arms: window and reset change no digit, hold ≡ collapse (1e-14), held a = 5.2 Å vs free 5.0243(21) Å at 2.62σ; two injected-escape positive arms show the reset firing and the collapse claiming a path both reach. C10: `FLOOR_HIT` and `PHASE_UNCONSTRAINED` both fire on the absent phase under the default plan, on different paths. C14 on NAC: rows never within 1179 ε, rows off is the shipped fit to every digit; on a synthetic touching-truth LaB₆ the rows hold Γ_G² at ε, move U, V, W, X 0.4-0.7 esd toward the truth, and leave only `CONSTRAINT_ACTIVE` with an empty `where`. *Gotchas*: the 2026-11-09 C14 row missed `CONSTRAINT_ACTIVE` (a channel exists, it names no path); NAC is the wrong dataset for C14 since WP-1938. `rietx.refine` imported as a module attribute is the function: the scripts use `importlib.import_module("rietx.refine")`. The NAC arms take seconds on either machine; the Linux x86_64 run agrees with the Mac to 12 digits in Rwp. *Tests*: `tests/test_docs_consistency.py` 26 passed (macOS arm64, `[dev]`); fast suite `-m "not slow" -n 6 --dist loadgroup` on a Linux x86_64 workstation venv (py3.12) at 2ee0c3af3: 14850 passed, 280 skipped, 32 xfailed, 0 failed, 595 s; no test added, so no count moved by this branch; `python -m tests.reader_output` exit 0, unchanged. *Review*: a read-only review agent checked the patches, the probe mirror and the Γ_G² formula (no code bug) and found four overstated tolerances and a wrong hold count in C1; all corrected (2ee0c3af3), plus a note that the no_hold patch also empties the width-twin hold's input (no effect on this fixture). The handover entry's first commit (c11aec119) named the workstation host, removed in 670baa1c8: a squash merge keeps it off main. No forward reference pushed: all four findings wait on rulings, and none changes another WP's work until one is made. Next: (1) the maintainer's rulings on questions (1)-(4), which set C1, C3, C10 and C14's verdict column; (2) then C4 and C7 (fixtures in the tree, no build needed), then C2, C12, C18, C19 and the rest by § Datasets; the CuCr₂O₄ ramp for C3 and C35 waits on a family-B series harness (WP-2003).

- **2026-11-09** — Every entry of the clash list now has a row saying whether it still exists in today's code. Of 42 entries (the 38 numbered pairs and C3's four sub-pairs), six no longer exist, mostly because the cell clamp, the position bounds and the frozen `lor_strain` were removed since the list was written; fourteen are kept apart by the code on purpose; twenty-two are real and none of those is measured. So the list to measure has shrunk from 42 to 22, and no fit has yet said whether any of them changes an answer. *Done* (PR #1512, docs only): tasks 1 and 2 ticked; each of the 22 live rows has a dataset chosen before running (§ Datasets for the live rows), six of them needing a fixture built or a vendored file modified (C3a, C10, C12, C27, C29, and C2's low-scale probe). § The table holds all 42 at 4c55b9011 with file:line. Live (22): C1, C2, C3, C3a, C4, C7, C10, C12, C14, C18, C19, C20 (measured in part by WP-2002), C21, C22, C25 (reconciled by intersected bounds), C26, C27 (idempotent by reading), C29 (rarely binding), C33, C35, C36, C37. Gone (6): C3b, C3c, C3d, C13, C24, C30. Designed apart (14): C5, C6, C8, C9, C11, C15, C16, C17, C23, C28, C31, C32, C34, C38. C1-C3d and C6 were read in this session; C4, C5 and C7-C38 by three delegated read-only readers, spot-checked at eight lines. No clash found or routed and no issue filed, since nothing was measured. `### Inherited` kept: both entries still describe the tree. *Gotchas*: read-only verdicts, not measurements; two rows the readers flagged as narrow gaps are worth a first look: C14 (a width held on a Γ_G² row is never reported at a bound) and C15's TRF and joint-fit case (no rows built, so a negative U or V can still reach the clamp). The session was a ghostshift runner under a hard stop; no fit ran. On this Mac a pytest run with `-n` is refused unless it goes through `testslot.sh`. *Tests* (macOS arm64, `.venv` `[dev]`): `tests/test_docs_consistency.py` 25 passed; `python -m tests.reader_output` exit 0, unchanged. Next: (1) measure C1 and C3 first, both orders or with and without the action, Rwp, the shared parameter and its esd, PNGs to `tests/output/`; (2) then C14 and C10, whose gaps are reporting rather than value changes and may route straight to their owners.
- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the clash table moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

