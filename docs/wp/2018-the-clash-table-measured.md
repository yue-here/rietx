# WP-2018 — The clash table: actions that read or move the same parameter, measured both ways

Milestone: generality · Status: 🔄 2026-11-16 — 12 of 22 live pairs measured (C1, C2, C3, C4, C7, C10, C12, C14, C18, C19, C20, C21); 12 questions for the maintainer
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
`[dev]`; the LaB₆ `plain` arm also on a Linux x86_64 machine, its record the file's last two
lines: Rwp equal to 6e-14, B to 1.4e-11 Å²). Capillary absorption is A = K·exp(c·sin²θ), an exact
reparameterisation of each phase's {scale, B} whose content is ΔB = c(µR)λ²/2; the ridge hold
reads a phase component that carries A and holds the B column A's shift lands on. The probe of
every arm is recorded each time the runner asked it. The dataset row named the fluorite as the
phase that fires the hold; on that fixture it is the iron (one reflection in range, (110)), and
the fluorite is the neighbour above the probe's floor (though `FLAT_DIRECTION` still reads its
scale and B as one direction, ρ +1.000, in every arm).

*The ridge fixture* (`tests/test_scale_b_ridge.py`'s four phases, noise seed and `cell_then_B`
staging, moved to the `debye_scherrer` preset at Cu Kα1 with the Bragg-Brentano profile, the
pattern drawn with µR = 1.0, predicted ΔB = 0.48869 Å²):

| Arm | Fe B (Å²) | Fe separation, stage `b` (floor 6.3e-8) | Fe scale ÷ corundum scale, relative to mu_hold | Fe wt% | Rwp |
|---|---|---|---|---|---|
| mu_hold (shipped) | 0.35, held in `b`, `w`, `closing` | 5.9e-13 | 1 | 1.5084 | 0.0827765366 |
| mu_nohold (positive arm) | 0.052(2.9), free | 5.9e-13 | 0.9644 | 1.4556 | 0.0827765366 |
| nomu_hold (µR undeclared) | 0.35, held in the same stages | 7.4e-13 | 1.0613 | 1.5994 | 0.0827765366 |
| nomu_nohold | 0.049(0.57), free | 7.4e-13 | 1.0231 | 1.5427 | 0.0827765366 |

Rwp agrees across all four arms to 3e-11 (the reparameterisation and the ridge are both flat).
A changes no hold decision: the probe reads corundum 0.223 against 0.228, zincite 0.193 against
0.190 and iron 5.9e-13 against 7.4e-13 with µR declared and not, so the same phase is held in the
same stages, and `SCALE_B_INSEPARABLE` names `phases.3.atoms.0.biso` alone in both hold arms. Every
site of the three phases above the floor moves by ΔB between `mu_hold` and `nomu_hold` to within
1.3e-5 Å² of the prediction (corundum 7e-8 and 8e-8, zincite 8e-6, fluorite Ca +1.2e-5 and F
−2e-6, against esds of 1.2, 4.3 and 3e3-1e4 Å²); between the two free arms, where the iron's B
moves too, to within 4.7e-3 Å² (zincite −4.6e-3). The iron cannot carry its share: held, its B
takes none of ΔB, and its scale takes A at (110) instead, 1.0613 measured against
exp(2ΔB·s²(110)) = 1.0613 predicted, so its weight fraction moves 6.0 % relative (0.44 of the
held fit's scale esd) between declaring µR and not. Free, its B walks from the 0.35 it was handed to
0.05 in both arms and takes 0.0033 Å² of ΔB (0.7 %), and the fraction moves the same 6.0 % (0.17
and 0.87 of the free fits' scale esds, µR declared and not). So
the 6 % is the ridge's, not the hold's: no setting of an iron B the data cannot see absorbs a
correction the data cannot see either. The fluorite's separation falls to 1.6e-6 (µR declared)
and 4.0e-6 (not) by the closing stage in the hold arms (25 and 64 times the floor), and to 8.8e-6
and 1.7e-6 in the free arms.

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
polar angle in every stage (Cr₂WO₆ stationary at 0, then π, the moment along ±a, statistic ≤ 0.002 against
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
of every converging arm (χ² 4e-22 to 2e-13); the trapped `no_turn` arms end at χ² 2.6-2.9, so
their statistic is a reading.

So the test's verdict is right when the hold and the turn have acted: they act at stage start,
the test reads the turned polar angle after the solve, and it gets both truths right while
changing no value (`no_test` is bit-identical in all six datasets; only esds and intervals move).
Take either half of the hold away and the test still answers, wrongly. Without the turn the polar
angle ends 27.84° from [111], at the point the test finds stationary along its meridian (it is
one, along that meridian), and `MOMENT_ANGLE_STATIONARY` presents a trapped answer at Rwp 0.145 as
a symmetry-fixed direction with a 0.036 rad interval: wrong and confident. Without the hold the
answer itself is the shipped one (ψ and Rwp equal), but the test refits the azimuth while it moves
the polar angle, which the flat cone allows at no cost, so a flat combination reads as a
stationary polar angle with a 0.39 rad interval (45 times the shipped esd), the azimuth gets an
esd of its own, and the report says no direction is unmeasured: the verdict and the report are
wrong, the values are not. `_refitted_increase` refits every other free angle and has no check
for a flat combination, so the test's verdict is right only after the hold has run. No arm
reorders the two; each removes one.

**C12, the Stephens seed's skip against the cone rows' drop** (`stephens_start.py`; macOS arm64,
`[dev]`, 4 s a fit). Brucite under `tests/test_acceptance_stephens.py`'s LM protocol (strain seed
800 ppm in `sample_broadening`, `intermediate_ftol` 1e-6, no closing stage), from five starting
blocks. The record says, per solve that frees the block, whether the σ²(M) ≥ 0 rows were built
and how many of the stage's 43 reflections start outside the cone.

| Arm (start; driver) | seed | rows in the 3 strain stages | reflections out at the end | Rwp | what the caller sees |
|---|---|---|---|---|---|
| zero (the test's: all-zero block; LM) | writes the 800 ppm ray | built, all three | 0 (one at −1.9e-18 of the largest σ², on the face) | 0.181470 | `CONSTRAINT_ACTIVE` (27 steps held in `biso`) |
| ray (the caller hands in `isotropic(800)`; LM) | skips it | built, all three | 0 (roundoff) | 0.180448 | `CONSTRAINT_ACTIVE` |
| out (the ray with s004 negated, 12 of 43 out; LM) | skips it | **dropped, all three** (12, 24, 19 out at their starts) | **19**, worst σ² −0.51 of the largest | 0.180540 | `STEPHENS_STRAIN_NOT_POSITIVE` (44.8 % of m·\|F\|²); nothing says the rows were dropped |
| out_seeded (out, the skip removed; LM) | overwrites it with the ray | built, all three | 0 (roundoff) | 0.181936 | `CONSTRAINT_ACTIVE` |
| out_trf (out; TRF) | skips it | none (TRF) | 19 | 0.180554 | `STEPHENS_STRAIN_NOT_POSITIVE` |
| zero_trf (the test's TRF fit) | writes the ray | none (TRF) | 19 | 0.180419 | `STEPHENS_STRAIN_NOT_POSITIVE` (the positive arm: it fires) |
| trf_then_lm (zero_trf's fitted models, refitted under LM) | skips it | **dropped, all three** (19 out at each start) | **19** | 0.179462 | `STEPHENS_STRAIN_NOT_POSITIVE` (44.7 %), suggesting "Under solver='trf', refit with the default LM driver" |
| trf_then_lm_seeded (the same, the skip removed) | overwrites it | built, all three | 0 (roundoff) | 0.180299 | `CONSTRAINT_ACTIVE` |

The zero and zero_trf rows reproduce the test module's 1.10.0 figures (LM 18.15 % with none
out, TRF 18.04 % with 19 of 43). A caller's block that starts outside the cone turns the LM
fit into an unconstrained one for the whole plan: the seed leaves it (it is not all zero), the
rows are dropped at each stage's start because the start violates them, and since the solve
then never returns inside, every later stage drops them too. The answer is TRF's (out against
out_trf: 19 of 43 out both, Rwp to 1.4e-5, the four DOFs within 0.14 of TRF's esds), and the
record looks like TRF's: the guard fires, `CONSTRAINT_ACTIVE` does not, and no field or code
says the driver held nothing. The realistic route there is the guard's own advice: refitting
the TRF answer under LM (`trf_then_lm`) carries the out-of-cone block in, and the LM fit ends
19 of 43 out again with the same suggestion to switch to LM. Without the skip (`*_seeded`) the
same starts end inside the cone. The ray arm shows the skip costs nothing when the caller's
block is inside: the rows hold; it lands in another of brucite's minima (dof 3 at 15630(5261)
against 7840(4819)), because a nonzero block broadens the peaks from the first stage (stage-1
Rwp 0.770 against 0.802), the multi-start spread the test module documents. Also seen, not
pursued: both `trf_then_lm` arms fire `RESOLUTION_NOT_POSITIVE`, which zero_trf does not, and
`trf_then_lm`'s dof 0 reads −9050(110) against zero_trf's −8623(165886). Question (7).

**C2, the profile interval's refits against the support hold** (`scale_interval.py`). Two
datasets, each with the interval as shipped and with the hold and the collapse at the answer
switched off during the interval only (`no_hold`); the fit is the same in both arms, and every
refit's held, released and collapsed paths are recorded.

*The trace, the positive arm* (`test_qpa_multimodal.py`'s two-basin fit, macOS arm64, `[dev]`):
CaF₂'s scale 2.688e-6, esd 9.61e-7, the fit holding nothing. The cut is Δχ² 5.196.

| Arm | lower end (esd below) | upper end (esd above) | refits | what the refits held |
|---|---|---|---|---|
| shipped | 1.3935469e-6 (1.347) | **4.6094e-6 (2.000)** | 30 | CaF₂'s `cell.a` and `lor_strain` at 7.66e-7 and every lower-side probe after it, and at every upper-side probe from 5.144e-6 down to 4.6099e-6, though not at 6.531e-6 |
| no_hold | 1.3935465e-6 (1.347) | 5.1460e-6 (2.558) | 24 | nothing |

On the lower side the hold changes nothing: a held refit's χ² equals the free one's to 2e-5,
and the ends agree to 3e-7 relative. On the upper side it moves the answer. Held, the refit at
5.144e-6 reads Δχ² 10.67, free 5.19, so the hold alone puts that value outside the cut. Every
Brent probe between 4.6094e-6 and 5.144e-6 was held and read Δχ² 11.05-11.20, so the end Brent
returned is the bracket's inner point, the unheld probe at exactly +2 esd (Δχ² 3.33): the
shipped interval is 14 % narrower (3.22e-6 against 3.75e-6) and its upper end is a step in the
profile the hold made (Δχ² 3.33 to 11.20 across 4.8e-10 in the scale), not a crossing of the
cut. Which probe is held is not monotone in the pinned value (6.531e-6 free, 5.144e-6 held, in
one walk), but it is monotone in walk order: on each side, once a probe was held every later
probe was (lower side: 1.727e-6 free, then 7.66e-7 and all after it held; upper side: 3.649e-6,
4.609e-6 and 6.531e-6 free, then 5.144e-6 and all after it held). A refit through `run_stage`
passes no prior significance, so its stage-start hold reads the screen at the state the probe
starts from, which is the previous probe's answer; why each side switched where it did was not
traced. Every held refit fires `PHASE_UNCONSTRAINED` inside the walk; the interval's
own record (`ParameterInterval.points`) carries none of it. Question (8).

*cpd-1a, the dataset chosen for the row* (`qpa_plan()`, three phases; Linux x86_64, py3.12, 43
and 45 s, 380 MB): corundum's scale 1.608(612)e-5, W = 1.72(64) wt % against 1.15 weighed. Both
arms make the same 28 refits to every digit, no refit holds anything, and the interval is
[8.787e-6, 3.705e-5], 1.19 esd below and 3.43 esd above (cut Δχ² 77.4): a lopsided profile, but
not the hold's. The weighed trace phase sits far enough above the support threshold that no
pinned value inside its interval reaches it, so the pair does not meet on cpd-1a.

**C18, `intermediate_ftol` against the holds that read each stage's end** (`ftol_holds.py`;
Linux x86_64, py3.12, 11-45 s, ≤ 366 MB). cpd-1a with zircon declared (a phase the sample
lacks), `qpa_plan()`, LM, at 1e-6 and None, with and without the closing stage:

| Arm | zircon held before the last stage | the last stage | zircon W (wt %) | largest move between tolerances | iterations, 1e-6 / None |
|---|---|---|---|---|---|
| close (shipped) | never, either tolerance | `closing`: 9 structural paths collapsed and held, either tolerance; `PHASE_UNCONSTRAINED` | 0.03(7) | 0.0053 plain esd (fluorite `lor_strain`) | 380 / 677 |
| open (B7's arms, no closing stage) | never, either tolerance | `biso`: nothing of zircon held; zircon free, a = 6.6145(78) Å, scale 6.5(3.5)e-7 (plain esd); no `PHASE_UNCONSTRAINED` | 0.08(16) | 0.065 plain esd (fluorite `a`, then zero and displacement) | 266 / 561 |

B7's flip (2026-10-21: at 1e-6 the last stage held nine zircon paths, at 1e-9 nothing) does not
reproduce on this tree: in no stage of any arm does the tolerance change what is held. Every
hold, release and collapse decision is the same at 1e-6 and 1e-9, both with the closing stage
(which holds zircon either way, as `test_staged_start_invariance.py` asserts) and without it
(which never holds it). The tolerance moves only values, within 0.0053 plain esd behind the
closing stage and 0.065 without it, and halves the iterations. The ramp half of the row
(`seqrefine_cucr2o4/`) needs the series harness C3 lacks, and was not run. Question (10).

**C19, the Le Bail partition at an intermediate stage's end** (`lebail_ftol.py`; macOS arm64,
`[dev]`). `test_lebail_cycles.py`'s #740 pattern under its `profile_only` Le Bail plan, with
and without the closing stage, at `intermediate_ftol` 1e-6 and None (every stage at 1e-9): each
pair is the same fit to every digit, parameters and extracted intensities alike. The tolerance
never governs a stage here: each ends in 2-3 LM iterations on another stop, and the LM driver's
`ftol` test needs three consecutive iterations under it, so the positive arms at 1e-2, 1e-1 and
5e-1 are bit-identical too. With the closing stage the cell lands at −1.5, −4.6 and −1.4 ppm
from the truth and Rwp 0.010660 against the true structure's 0.010879; without it, −1.7, −6.3,
−1.3 ppm and 0.012097. So on the dataset chosen for the row the pair cannot meet, and a
positive arm on it cannot fail. Question (9).

**C20, the roughness seed against Biso, Pitschke's c** (`roughness_seed.py`; macOS arm64,
`[dev]`, ≤ 4 s a fit). The remaining half of WP-2002's measurement: the five lab patterns of
`tests/test_seed_invariance.py`, each under its acceptance protocol with a `RoughnessPitschke`
block and the shipped roughness stage appended last (no closing stage, as that test runs), c
seeded to 0.3 against c started on its floor of 0. "Plain esd" is `stderr_uncorrected`, and
the worst move is over every Biso, scale, c and τ, in the smaller of the two arms' plain esds.

| Family | c, τ from the seed | c, τ from 0 | worst move (plain esd) | χ², zero − seeded, relative |
|---|---|---|---|---|
| FAP (GSAS protocol) | 1.1325(786), 0.1113, `ROUGHNESS_OUTSIDE_REGIME` | the same | 6e-6 | −9e-13 |
| SRM 660c LaB₆ (NIST protocol) | 4e-16, τ 0: off | 0 on its floor, τ 0.05: off | 0.013 (La Biso) | −1.4e-6 |
| CPD corundum | 0, τ 0: off | **0.022(145), τ 0.3 on its ceiling** (`BOUND_HIT`, `ROUGHNESS_OUTSIDE_REGIME`) | **0.83 (Al Biso)** | −4.3e-4 |
| CPD fluorite | 1.08 ± 55.9, 0.0116 | 0.89 ± 34.7, 0.0143 | 0.0055 (c) | +1.9e-6 |
| CPD zincite | 0, τ 0: off | 0, τ 0.05: off | 6e-6 | +4e-12 |

Four families are start-invariant at WP-2002's bar; corundum is not. From 0 its fit walks τ to
the 0.3 ceiling, past sinθ at the lowest angle (0.221 at 25.5°), with c small but free, and the
Biso and scale esds grow 2.2-3.3× and 11× (the off state from the seed has no c or τ column, so the
neighbours' esds there are conditional, as WP-2002 found for Suortti). Al Biso moves 0.83 plain
esd (0.2273(117) to 0.2177(384) Å²), larger than the 0.26 WP-2002 recorded on corundum, and
zincite's turned-over landing that WP-2002 recorded from c = 0 does not reproduce (both starts
off). The seed is the one that keeps corundum out of the outside-the-regime answer (FAP's τ is
outside the regime from both starts, and both agree); both corundum answers converge. Question (11).

**C21, extinction and roughness free together** (`extinction_roughness.py`; macOS arm64,
`[dev]`). The same five protocols (no closing stage) with neither correction, primary
extinction alone (`Phase.extinction = 0.0`, the plan's `extinction` stage), Suortti roughness
alone (the shipped roughness stage), both in the plan's order, and both swapped. Worst move over
every Biso, scale and extinction coefficient, in the smaller plain esd:

| Family | which turns on alone | both, against the one that turned on | both, against swapped | esds with both, against that one alone |
|---|---|---|---|---|
| FAP | roughness (b 0.81, a 0.54; scale 123 esd from neither); extinction stays on its floor | 0.0001 | 0.0008 | ×1.00 |
| SRM 660c LaB₆ | neither (extinction on its floor, roughness off) | 0.0082 (against extinction alone) | 0.0003 | ×1.06-1.16 |
| CPD corundum | extinction (2.87(62) µm²; scale 4.8 esd from neither); roughness off | 0.0066 | 0.0072 | ×1.16-2.22 |
| CPD fluorite | roughness (b 0.028 ± 1.50, a 0.54 ± 22.7: a hinge); extinction on its floor | < 1e-4 | 0.0011 | ×1.33-1.39 |
| CPD zincite | extinction (0.54(10) µm²; scale 8.7 esd from neither); roughness off (a on 1) | < 1e-4 | < 1e-4 | ×1.01-2.29 |

On every pattern at most one of the two leaves its identity, and which one is the pattern's,
not the plan's: declaring both, in either order, gives the answer of the one the data used to
0.0082 plain esd, and reduced χ² to 3.8e-4 relative (each idle correction is one more free
parameter in N − P).
Each correction alone moves the scale by 4.8-123 esd, so a shared trade would show at this size;
none appears. What the idle partner does change is the esds: a declared but idle correction
keeps its floored row in the covariance (WP-1929's marginal reading), so its neighbours' esds
grow, up to 2.29× on zincite (extinction on, roughness off) and 2.22× on corundum; between the
two orders the corundum esds differ by the same factor because roughness lands in two different
off states (a = 0.885, b = 0 in the plan's order; a = 1, b = 0 swapped, where b's column is
identically zero and leaves the covariance). Question (12).

**C3a, the support window on an unseen phase's cell that drives a visible one**
(`tied_window.py`; macOS arm64, `[dev]`, ≤ 1 s a fit). C3's fixture with the visible LaB₆'s
a tied to the absent copy's (`ref.tie("phases.0.cell.a", "phases.1.cell.a", scale=4.1606/5.2)`),
`mccusker_default`. The window keys on the free column's path (`_cell_parameter_name`,
vector.py:600, applied in `bounds()` :4409), so it bounds the absent phase's a and through the
tie the visible one; the support hold reads what the column moves (`column_reach`), so it
never holds it.

| Arm | visible a − truth (Å) | absent a (Å) | Rwp | held | codes naming phase 1 |
|---|---|---|---|---|---|
| notie (C3's default) | +1.64e-7 (esd 4.34e-6) | 5.2, held | 0.041557 | `phases.1.cell.a`, `cell` to `closing` | `PHASE_UNCONSTRAINED` (cell.a, 0σ), `FLOOR_HIT` (scale) |
| tie | +1.64e-7 (esd 4.34e-6) | 5.195001(5) | 0.041557 | nothing | the same two |
| tie_no_window, tie_no_support | identical to tie, every digit and iteration count | | | | |
| tie_narrow (positive arm: window ±0.01 %, no pad) | **+2.34e-3** | 5.197920 | 0.3736 | nothing | the same two; no `BOUND_HIT` |
| notie_narrow (control) | identical to notie, every digit | | | | |

On the fixture the window does not bind: the source travels 0.005 Å against a ±0.31 Å
window, and the visible cell lands where it lands untied (to 1e-14 Å, its esd to 2e-7
relative). The hold correctly leaves the tied column free. Two things a caller is told are not
what happened. First, `PHASE_UNCONSTRAINED` still names `phases.1.cell.a` and says "1 of its
parameters was refined without signal", while that column is the visible cell's and carries
its esd (5.42e-6 = 4.34e-6 / 0.8001). Second, the positive arm shows that when the window does
bind, nothing reports it: the source ends where four stages in a row (`cell` to `closing`), each stopped on
its lower edge, put it (5.2 × (1 − 1e-4)⁴ = 5.1979203, to every digit), the visible cell stops 2.34e-3 Å
(about 540 of the tie arm's esds) short and Rwp is 9× the free fit's, yet `at_bound` reads False and
no `BOUND_HIT` fires. Read, not traced: the stage commits the answer (refine.py:5273) before
`check_guards` (:5594) calls `table.bounds()` again, and `cell_window` anchors on the entry's
current value, so the guard sees a window centred on the answer rather than the one the solver
stopped on. That reaches any binding support window, tied or not; this fixture is the only one
here where one binds. Question (13).

**C22, `solve_magnetic`'s one-site release against the flat-moment hold** (`release_hold.py`;
macOS arm64, `[dev]`, 12-15 s an arm). The chosen dataset cannot exercise the pair: Cr₂WO₆
has one magnetic site, and `_starts` returns before any release when a class has fewer than two
(magnetic.py:1553-1554, read; `test_a_single_site_class_is_started_once`), so it was not run.
The two-site Pnma fixture of `tests/test_magnetic_solve.py` (Mn1 3.5 µB and Mn2 0.7 µB along x,
A-type 62.448, CW neutrons) was run through `solve_magnetic` instead: four classes, each fitted
from the flat seed and from each site alone then released, 21 fits an arm with the nuclear
reference. Arms: shipped; no_hold (`_flat_moment_scan` holding nothing, C7's arm); tiny (the
release at 1e-4 of the seed rather than 0.05); tiny_no_hold.

| Class (BNS) | shipped: start, ΔBIC | no_hold | tiny | tiny_no_hold |
|---|---|---|---|---|
| 62.448 (the truth) | flat, 1037.42 (Rwp 0.011395) | identical | identical | identical |
| 62.441 | Mn2 released, 144.628 | the same to 1e-6 | the same to 1e-6 | the same to 1e-6 |
| 62.447 | Mn2 released, 3.4185 | identical | 3.4185 | 3.4185 |
| 62.446 | Mn2 released, **−19.99** | Mn1 released, **−29.98** | flat, −19.99 | Mn2 released, −29.98 |

The hold acts in 8 of the 20 shipped trial fits, always on an azimuth: of a moment the leg
left on the polar axis (held at the moment stage's start and released at its answer), or, in
62.446, of both sites once their moduli collapse to 0.11 µB with esds of 540-550 µB. A released
site's angles are held only there (two fits), as the flat start's fit of the same class holds
them too. The verdict, the winner, its start and its ΔBIC are the same in every arm, and so is
the runner-up's to 1e-6. Two things move, both in the class the data reject. First, at 1e-4
the released starts of 62.446 end in another minimum (Rwp 0.5060993 against 0.5060964) with no
hold acting, so the release fraction does decide where a released site lands. Second, the hold
moves 62.446's ΔBIC by 9.99 at an Rwp equal to 1e-9 relative, because ΔBIC's parameter charge is
the count of *free* moment rows in the result (`n_moment`, magnetic.py:1610-1611, read): a held
azimuth is not charged. Question (14).

**C25, the size cap against `SIZE_LAMBDA_POWER` in a joint fit** (`joint_size_cap.py`; macOS
arm64, `[dev]`, about 3.5 s an arm). The published Nd₂Ru₂O₇ pair of
`tests/test_acceptance_wavelength.py` (11-BM X-ray as histogram 0, the CW neutron pattern as
histogram 1, λ ratio 3.727) under its own `mccusker_structural` protocol, both λ held, with a
`size` stage appended that frees `lor_size` and `gauss_size`. Each stage's cap freeze is logged
per histogram table. Arms: shipped; no_cap; no_lambda (`SIZE_LAMBDA_POWER` emptied); tight
(`SIZE_CAP_RANGE_FRACTION` 1e-8, a cap of 4.05e-7°) and tight_no_lambda; tight6 (1e-6, a
cap of 4.05e-5°, just under the fitted size); and three arms starting both sizes at 2e-5
(column units) rather than 0: seeded, tight6_seeded, tight6_seeded_no_lambda.

| Arm | lor_size (°, column) | gauss_size | Rwp X-ray, neutron | what the cap did |
|---|---|---|---|---|
| shipped | 4.81(25)e-5 | 3.2(55)e-5 | 0.0919566, 0.0623754 | never armed |
| no_cap, tight, tight6 | identical to shipped, every digit | | | never armed |
| no_lambda, tight_no_lambda | 4.80(25)e-5 | 3.6(59)e-5 | 0.0919565, 0.0623747 | never armed |
| seeded | 6.81(25)e-5 | 5.2(55)e-5 | 0.0919567, 0.0623754 | never armed |
| tight6_seeded | 5.13(25)e-5 | 0, on its floor (`FLOOR_HIT`) | 0.0919534, 0.0623760 | armed in `size` only |
| tight6_seeded_no_lambda | 5.26(25)e-5 | 0, on its floor | 0.0919534, 0.0623762 | armed in `size` only (`gauss_size`) |

The sizes are not resolved on this pair (each within its esd of 0). Started at 0 they sit at 0
at every stage's compile until the closing stage moves them, so the cap, which arms only on a copy that
has already reached it at compile (`size_cap_hi`, vector.py:1033), never arms: switching it
off or narrowing it to 1/119 of the fitted size changes no digit. `SIZE_LAMBDA_POWER` off moves
the sizes 0.0006 and 0.0064 esd and the cell 5e-5 esd. The seeded positive arm shows the two
meeting as WP-1131's docstring says (least_squares.py:3294-3313): at the `size` stage's compile
the neutron copy of `lor_size` (7.45e-5°) arms and the X-ray copy (2e-5°) does not, so the
intersected bound is the neutron table's, 1.0866e-5 in column units (4.05e-5° / 3.727); both
copies of `gauss_size` arm and the neutron's binds, 1.18e-10 (1.64e-9 / 13.89). The stage
starts above both bounds and ends with both sizes at 0. The closing stage then compiles at 0,
nothing arms, and it takes `lor_size` to 5.13e-5°, 1.27× the cap, unchecked. In every arm the
closing stage sets the size the caller reads, and it compiles before any copy reaches a cap.
Question (15).

**C26, σ widened at the compile-time blank scale while the scale is free**
(`blank_sigma_scale.py`; macOS arm64, `[dev]`, about 4 s a fit). Si SRM 640c in Kapton with its
measured blank, the `blank_free` protocol of `tests/test_acceptance_si640c.py` (3 Chebyshev
terms, the blank's esd column as `fixed_sigma`, its scale free from 1.0). Each compile's blank
scale is logged. The fit compiles eight times: the six declared stages, the closing stage, and
the report's fresh compile at the answer, which keeps the solve's σ (`fresh.sigma =
model.sigma`, refine.py:6433). Arms: start_1 (shipped); start_conv and start_3 (the scale started
at 0.85 and at 3.0); again (one more declared stage freeing every glob, so the closing stage
compiles one solve later); pinned (every compile widens σ at the start_1 answer's scale,
0.841316, by setting the scale for the compile alone; a free scale is a design row, so the
compile reads it only for σ); no_sigma (the blank's esd column dropped: no widening).

| Arm | scale the closing stage compiled at | answer's scale | worst move against start_1 (esd) | σ against σ at the answer's scale |
|---|---|---|---|---|
| start_1 | 0.837415 | 0.84132(1074) | — | up to 0.24 % |
| start_conv, start_3 | 0.837415 | the same | 2.5e-6, 1.4e-6 | up to 0.24 % |
| again | 0.837429 | the same to 1.3e-7 | 9.3e-5 | up to 0.24 % |
| pinned (σ at 0.841316 in every stage) | (σ at 0.841316) | 0.84128(1075) | **0.0061** (c0; scale 0.0036, `lor_size` 0.0047) | 0.0024 % |
| no_sigma (positive arm) | — | 0.84528(999) | **0.80** (c0; `lor_size` 0.67, scale 0.40, Biso 0.22) | the widening itself is up to 45 % of σ_y |

The per-stage lag does not survive the plan: only the first compiles see the start (1.0, 0.85
or 3.0), and from the fourth compile on every arm compiles at the same scale to 1e-6. What reaches
the caller is the closing stage's own move: it compiles at 0.837415 and lands at 0.841316, 0.36
of the scale's esd, so the σ the result divides by is the one at 0.837415, within 0.24 % of
the σ at the answer on every channel (the widening it carries is up to 45 %). The pinned arm,
where every stage weights at the answer's scale, moves no value by more than 0.0061 esd
against the shipped fit, while dropping the widening moves values up to 0.80 esd, so the arms
can see a weighting effect of this kind; the lag is about 1/130 of it. Question (16).

**C27, the rules that act on σ** (`zero_sigma.py`; macOS arm64, `[dev]`, about 3 s a fit).
Re-derived first: WP-1952 has landed, so the row read at 4c55b9011 is out of date. There is no
`_floor_sigma` any more. A stated σ ≤ 0 leaves the fit under the reader option
`nonpositive_sigma="exclude"`, the default (`PatternData.in_range_mask`, pattern.py:236), or
takes the Poisson fallback √max(y, 1) under `"poisson"` (`_poisson_where_nonpositive`,
pattern.py:41, which `PatternData.sig` applies at :211). `RefinementResult.sig` applies the same
function to the σ the fit stored (results.py:2466), and the compile still widens σ for a
measured blank (C26). The dataset as chosen: a copy of `11BM_LaB6_cBN_mg2044.xye` with σ planted
at the strongest channel in the fitted range (8.070°, LaB₆ 110, y = 122 248, file σ 355.8),
under `test_acceptance_lab6_cbn.py`'s `PLAN_SHARED`. Arms: original; zero_exclude; zero_poisson;
floor (the positive arm: σ = 1e-3 × the column's median, 0.0115, what the retired floor gave a
zero, and which no rule touches).

| Arm | channels fitted (`sigma_rule`) | σ stored at the channel | LaB₆ wt % | worst move (esd) | `sig()` = `sigma` |
|---|---|---|---|---|---|
| original | 44 895 file | 355.8 | 17.787(319) | — | bit for bit |
| zero_exclude | 44 894 file, 1 excluded; reader's `PATTERN_SIGMA_NONPOSITIVE` | not in the fit | 17.729(319) | 0.28 (LaB₆ scale) | bit for bit |
| zero_poisson | 44 894 file + 1 Poisson | 349.6 | 17.788(319) | 0.009 | bit for bit |
| floor (positive arm) | 44 895 file | 0.0115 | 18.455(319) | **3.6** (LaB₆ scale); Rwp 6.4e-5, `STAGE_MAX_ITER` | bit for bit |

The rules no longer stack: in every arm the σ the result stores is the σ the fit used and
`sig()` returns it unchanged, so the second application is a no-op on a fit's own result, as
its docstring says (it acts only on a hand-built result). A planted zero is now one channel's
worth of data: dropped by default, it moves the LaB₆ scale 0.28 esd and its fraction 0.18 esd
because the channel is a peak top; weighted as Poisson, 0.009 esd. The positive arm shows what
the retired floor did with the same zero: one channel carrying about a million times its
neighbours' weight, the LaB₆ scale 3.6 esd away and an Rwp of 6.4e-5. The blank's widening was
measured in C26 and does not meet these rules (it adds to a σ that is already positive).
Question (17).

**C29, the March-Dollase floor, the tie window and the unseen-phase hold** (`march_minor.py`;
macOS arm64, `[dev]`, under 1 s a fit). The dataset built as chosen: no vendored pattern has a
textured minor phase, so the `weak_second_phase` construction of `tests/_synthetic_weak_lines.py`
(Mo host, α-MoO₃ trace, its synchrotron instrument, Poisson counts on 7700) with the oxide drawn
at r = 0.6 along [010], at trace 0 (absent), 0.006 (the fixture's) and 0.03. Fitted with both
phases declared and MoO₃'s r free from 1.0 (plan: scales and background, cells, r; closing
stage), each trace under shipped, nosupport (`phase_support_sigma = None`), tied (r = 0.5·vars.rv,
rv free from 2, so `tie_window` gives rv ≥ 2e-6) and tied_nosupport; and a positive arm at trace
0 with r started at 2e-6 and the hold off, so the floor can be met.

| Trace | shipped | nosupport | tied | tied_nosupport |
|---|---|---|---|---|
| 0 | r held from `texture` on (with the cell), `PHASE_UNCONSTRAINED` 0.85σ names r | r 1.04(46), `PHASE_UNCONSTRAINED` 2.33σ names r | rv held, the code names rv | rv 2.08(92), r 1.04(46); the code names the cell only |
| 0.006 | r 0.6030(23), nothing held | identical | r the same to 7e-10 | identical to tied |
| 0.03 | r 0.6008(6), nothing held | identical | r the same to 3e-11 | identical to tied |
| 0, pole (positive arm) | — | Rwp NaN, `STAGE_NOT_FINITE` in all four stages, `MODEL_FAR_FROM_DATA` | — | — |

Where the oxide is there (at 0.006 and 0.03) the hold never acts and the tie window, 2e-6
against rv ≈ 1.2, never binds: the four arms agree to 7e-10, and r lands 1.33 and 1.30
esd from the truth. Where it is absent the hold holds r, through the variable as well (the column
reaches only the unseen phase), and without the hold r wanders to 1.04 ± 0.46, nowhere near the
floor; so on this fixture the pair never meets. One finding beside it, from the positive arm:
the floor is not a place the model is defined. MoO₃'s (0k0) lie exactly on the [010] axis, and
`cos2_alpha` returns their cos²α as 1 ± 2.2e-16 (5 of the 11 off by one ulp, 3 of them above 1).
At r = 2e-6 the bracket r²cos²α + sin²α/r is then dominated by the rounding (2.2e-16/r = 1.1e-10
against r² = 4e-12), negative where cos²α rounds above 1, and `march_term` returns NaN for 3 of
the 11, and 8e14-2e15 instead of 1.25e17 for two more; at the floor itself, 1e-6, the same three
are NaN. At 1e-5 all eleven are finite, but five still read 7.4e14-1.46e15 against
1e15. The floor's docstring (structure.py:51) says every factor is finite in fp64 at every
angle on the bound itself. Question (18).

**C33, positions that move inside a stage whose list and windows are frozen**
(`frozen_positions.py`; macOS arm64, `[dev]`, about 1 s a fit). 11-BM NAC (`build_nac_inputs`)
cold-fitted from a cell 0.1 % short, Rietveld under `mccusker_default` and Pawley under
`pawley_default`, with the zero started at 0 (shipped), +0.1° and +0.6° (the positive arm,
past the 0.5° reflection margin). Every solve logs the zero at its start and its answer (no
geometric shift is free in either plan). The arm with less of the freeze runs each declared
stage three times in a row (16 solves against 6), so the list and the windows are recompiled
at two more points along every stage's path; it is run from 0 and from +0.1°.

| Arm | Rietveld: a (Å), zero (°), Rwp | largest in-stage zero move | Pawley: a, zero, Rwp | largest in-stage zero move |
|---|---|---|---|---|
| 0 | 10.251212(56), −0.00024(7), 0.1401 | 0.0056° (`zero`) | 10.251213(54), −0.00025(7), 0.1345 | 0.0052° |
| 0, repeated | the same to 8e-12 Å and 1e-11° | 0.0056° | the same to 2e-11 Å and 4e-11° | 0.0052° |
| +0.1 | scale on its floor, cell held from `cell` on; zero 0.1, no esd; Rwp 0.838, `MODEL_FAR_FROM_DATA` | 0 | 10.2653(78), 0.153(12), Rwp 0.836, `MODEL_FAR_FROM_DATA` | 0.040° (`cell`) |
| +0.1, repeated | identical | 0 | the same to 2.3e-7 Å | 0.039° |
| +0.6 | as +0.1 | 0 | 10.2450(65), 0.594(11), Rwp 0.831 | 0.0033° |

Recompiling three times as often changes no answer: from 0 the repeated arms agree to 1e-11,
and from +0.1° the Pawley fit lands in the same wrong basin to 2.3e-7 Å. In the converged fits
no stage moves the zero more than 0.0056°, under 2 % of the 0.3° of movement headroom every
window carries (`WINDOW_MIN_DEG`), and the Pawley off-data ridge marks the same eight reflections either
way. A 0.1° start error fails for reasons that are not the freeze: in Rietveld the scale falls to its floor in the first stage (`FLOOR_HIT`), after which
nothing of the phase moves the pattern, so the zero's column is flat: it never moves and ends
with no esd, and the support hold takes the cell from `cell` on; in Pawley the fit reaches the zero-cell
correlation's other basin (ρ = 0.985). So on NAC the pair does not change an answer, and the
positive arm cannot make it act, because the scale's floor or the basin decides first. Question
(19).

**C36, the background's start against the Le Bail partition at stage compile**
(`lebail_bkg_seed.py`; macOS arm64, `[dev]`, under 1 s a fit). Three patterns of one synthetic
Pnma phase (CW neutron 2.4 Å, drawn with W = 0.25, X = 0.001, U = V = Y = 0, true cell known):
#740's (`test_lebail_cycles.py`, strong peaks on a 300 + 2·2θ pedestal) and the two of
`test_lebail_background_hump.py` (the phase at 1/50 of that scale on the same pedestal, and
with a 600-count hump at 50°), each fitted as that module fits (`profile_only` Le Bail from the
true cell and widths). Arms: zero (`auto_background`, the default: every coefficient 0), seed
(`seed=True`), truth (the positive arm: the true curve held, four Chebyshev terms free from 0).

| Pattern | arm | Rwp | background / truth at 50° | W (truth 0.25) | Y (truth 0) | cell axis furthest from the truth, in its esds (ppm) |
|---|---|---|---|---|---|---|
| #740 | zero / seed / truth | 0.0108 / 0.0107 / 0.0108 | 1.004 / 1.004 / 0.994 | 0.2500 / 0.2499 / 0.2498 (6e-4) | within 1.2 esd of 0 in all three | b, −4.7(13) in all three |
| flat | zero | 0.0547 | 0.978 | 0.219(20) | **0.079(25)**, U −0.016(8), X on its floor | c, −36(36) |
| flat | seed | 0.0468 | 0.983 | 0.249(12) | 0.034(14) | b, −38(20) |
| flat | truth | 0.0425 | 0.987 | 0.254(10) | 0.012(11) | b, −40(16) |
| hump | zero | 0.1001 | 0.817 | 0.190(55), `RESOLUTION_NOT_POSITIVE` | 0.030(67) | a, −60(130) |
| hump | seed | 0.0934 | 0.830 | 0.255(47) | −0.017(59) | a, −72(106) |
| hump | truth | 0.0405 | 0.996 | 0.253(10) | 0.010(12) | b, −41(16) |

On #740's pattern, where the peaks dwarf the pedestal, the start changes nothing (cell within
0.6 esd, widths within 0.4 esd, across all three). Where the phase is weak against the
pedestal the partition against an unfitted background does reach the answer: from zero, Y
ends 3.1 esd from its true 0 and U 1.9 esd negative on the flat pattern, and W 1.1 esd low with
`RESOLUTION_NOT_POSITIVE` on the hump; the seed takes W to within 0.1 esd of the truth on
both, but Y stays 2.4 esd off on the flat pattern and the hump's background still ends at 0.83
of the truth (WP-1542's 0.83, reproduced). Only the true curve held brings every width within
1.1 esd and the background to within 1.3 %. The cells move less: between the zero and truth arms by at most 1.2 of the truth arm's esds
on the flat pattern and 2.5 on the hump (0.4 of the zero arm's own, which are 6× wider), and
the axis furthest from the truth is as far in the truth arm (2.6 esd) as in any other, so what
the start moves first is the profile and the esds. Question (20).

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
   6.0 % relative (0.44 of the held fit's scale esd) with or without the hold, because B there cannot
   carry ΔB either way. Is C4 recorded *independent*? And should `SCALE_B_INSEPARABLE`, which
   already states the fraction's sensitivity per Å² of B, also say that an undeclared
   absorption correction lands on that phase's fraction rather than its B?
6. **C7.** On Cr₂WO₆ and LaMnO₃ the hold never acts, so the pair never meets; on the #599
   combination fixture the shipped order gives the test's verdict right both ways (not
   stationary at 10.3°, stationary on [111]) and the test moves no value. The arms remove the
   hold or the turn rather than reorder them, so what is measured is a dependency: the test's
   verdict is right only once both have acted. Is C7 recorded *ordered* on that evidence? The
   `no_hold` and `no_turn` arms show the test itself cannot tell a flat combination or a trapped
   meridian from a symmetry-fixed direction: should it carry a guard of its own (refusing a
   candidate whose Δχ² vanishes because another free angle absorbs the move), or is the hold's
   precedence the design? And should the row's
   datasets be replaced by the #599 fixture, since the two chosen ones cannot exercise it?
7. **C12.** A caller's Stephens block that starts outside the cone makes the default LM fit
   unconstrained for the whole plan (the seed skips a nonzero block, the rows drop at every
   infeasible start), with nothing in the record saying so; following
   `STEPHENS_STRAIN_NOT_POSITIVE`'s own advice from a TRF answer lands there (19 of 43 out,
   the same suggestion again). Is C12 recorded a *clash*? And which of these, if any, is the
   owner's to do: (a) a record or code when a phase's cone rows are dropped; (b) the
   suggestion to stop telling an LM fit to switch to LM; (c) put an infeasible start back on
   the isotropic ray (as `seed_stephens` does for a zero block, and as the `*_seeded` arms show
   holds the cone), which changes a caller's starting values and so is a default flip?
8. **C2.** On the trace the hold acts inside the interval's refits and narrows the upper end
   by 0.56 esd (14 % of the width), and that end sits on a step the hold made rather than a
   crossing of the cut. On cpd-1a's corundum (1.15 wt % weighed) no refit holds anything
   (§ below). Is C2 recorded a *clash* on the trace's evidence? Should the interval's refits
   hold only what the fit held (no stage-start hold and no collapse inside `_walk`), or should
   a held refit end the side as `"error"` the way an unmeasurable point does, so a hold never
   becomes an end?
9. **C19.** On #740's pattern `intermediate_ftol` never binds (2-3 iterations a stage), so the
   partition never runs at a 1e-6 end point that differs from 1e-9. Is C19 recorded *does not
   meet on this dataset*, and is a dataset whose Le Bail stages run long owed, or is the row
   closed by the closing stage (which repartitions at the answer in every arm)?
10. **C18.** On cpd-1a with zircon declared no hold decision changes with the tolerance, with
    or without the closing stage; B7's flip no longer reproduces. Is C18 recorded
    *independent* on this evidence? Without the closing stage the absent zircon ends free
    with no `PHASE_UNCONSTRAINED` (scale 1.8 plain esd from zero); is that the support test's
    designed reading, or worth a row of its own?
11. **C20.** Pitschke's c is start-invariant on four of the five lab patterns; on CPD corundum
    the start at 0 reaches τ's ceiling outside the model's regime and moves Al Biso 0.83 plain
    esd, while the shipped seed stays off. Is C20 recorded *ordered* (the seed is load-bearing
    for Pitschke on corundum), and is a Pitschke row owed in
    `tests/test_seed_invariance.py`, which today asserts Suortti only?
12. **C21.** On five lab patterns from three laboratories at most one of extinction and
    roughness turns on, and the order changes no value (≤ 0.0072 plain esd). Is C21 recorded
    *independent* on this evidence? The idle partner inflates the neighbours' esds up to 2.3×,
    and on corundum the order picks which of two off states roughness reports, and so which
    esds: is that WP-1929's designed marginal reading, or a report an idle correction owes
    (for instance, that it ended at its identity)?
13. **C3a.** With a user tie from an unseen phase's cell to a visible one, the shipped window
    does not bind on the fixture and the visible cell is the untied answer, so is C3a recorded
    *independent* there? Two reports are owed a ruling. (a) `PHASE_UNCONSTRAINED` names the tied
    source as "refined without signal" while it carries the visible cell's esd: should the
    finding leave out a column whose reach includes a seen phase, as the hold already does?
    (b) When a support window binds (the ±0.01 % positive arm), `at_bound` and `BOUND_HIT` stay
    silent, because the guard recomputes the window around the committed answer: should
    `check_guards` read the bounds the solver used (frozen with the window set), and is that
    the owner's fix (WP-1110's window) or a new row?
14. **C22.** On the two-site fixture the release and the flat-moment hold never meet on a class
    the data support: winner, start and ΔBIC are the same with the hold off and with the release
    at 1e-4. Is C22 recorded *independent* on this evidence, given that the dataset chosen for it
    (Cr₂WO₆, one site) cannot exercise it? And one finding beside the pair: a held azimuth is not
    charged in ΔBIC (`n_moment` counts free moment rows), so the hold raised the rejected class
    62.446's ΔBIC by 9.99 at an unchanged χ². Should ΔBIC charge the class's moment DOFs whatever
    a stage held, or is a held direction rightly free of charge?
15. **C25.** On the Nd₂Ru₂O₇ pair the size cap never arms (the sizes are unresolved and only
    the closing stage moves them), and a positive arm shows the cap and the λ scaling meeting
    as WP-1131 documents: the neutron copy arms first and its bound, in column units, is the one
    the intersection keeps. Is C25 recorded *independent* (reconciled by design) on this
    evidence? And beside the pair: the cap arms only at a compile where a copy has already
    reached it, so a size the closing stage moves past it (1.27× in the positive arm) is never
    capped. Is that the intended reach of a stage-granularity backstop, or does the closing
    stage owe the cap a second look?
16. **C26.** On Si 640c in Kapton the stage-start scale's lag washes out of every intermediate
    stage, and what reaches the caller is the closing stage's own move (0.36 esd of the
    scale), which leaves `result.sigma` within 0.24 % of σ at the answer and the values within
    0.0061 esd of a fit weighted at the answer throughout. Is C26 recorded *independent* (the
    lag accepted, as forward.py's comment says) on this evidence, and is the bar for "the
    lag is accepted" the maintainer's to state?
17. **C27.** Since WP-1952 the σ rules no longer stack: `RefinementResult.sig` returns a fit's
    σ unchanged in every arm, and a planted zero is excluded (0.28 esd on a peak top) or Poisson
    weighted (0.009 esd), where the retired floor moved the scale 3.6 esd. Is C27 recorded
    *dissolved* by WP-1952, and should the row's file:line be rewritten to the rules above?
18. **C29.** On a synthetic textured MoO₃ trace the floor, the tie window and the hold never
    meet: the hold holds an absent phase's r (directly or through a variable), and a seen
    phase's r is the same in all four arms. Is C29 recorded *independent* on this evidence? And
    the positive arm's finding, for B9's owner: at the 1e-6 floor (and at 2e-6) `march_term`
    returns NaN for reflections on the texture axis whose cos²α rounds above 1, so a fit started
    there is NaN in every stage. Should `cos2_alpha` clamp to [0, 1], should the floor rise
    to where the rounding no longer sets the factor (2.2e-16/r equals r² at r = 6e-6, and
    at 1e-5 five of eleven factors are still off), or both, and does the
    floor's docstring need correcting either way?
19. **C33.** On NAC cold-fitted from a cell 0.1 % short, recompiling the list and the windows
    three times as often changes no answer (1e-11 from a zero of 0; the same wrong basin from
    +0.1°), and no converged stage moves the zero more than 0.0056°. Is C33 recorded
    *independent* on this evidence? A larger start error fails before the freeze can act (the
    Rietveld scale floors in the first stage; Pawley lands in the zero-cell basin at ρ 0.985),
    so is a dataset that moves a position by more than the 0.3° headroom inside one stage and
    still converges owed, or is the row closed?
20. **C36.** On #740's pattern the background's start changes nothing; on the weak-phase
    patterns of `test_lebail_background_hump.py` the first partition against an unfitted
    background leaves the profile 1.1-3.1 esd off from a zero start, the seed recovers W but
    not Y (2.4 esd) or the hump, and only the true curve recovers both. Is C36 recorded
    *ordered* (the partition reads the background the stage starts from, by design), and is
    #725's question, whether `seed=True` should be the default, answered or reopened by these
    numbers? (The verdict on a default is the maintainer's.)

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

- **2026-11-16 (third round)** — Six more pairs of the clash table are measured, so 12 of the 22 live pairs now have numbers. Two of them change what a caller gets. First, a user-supplied anisotropic-strain block that starts outside the physically allowed region makes the default solver fit it with no positivity constraint at all, for the whole refinement, and nothing in the result says so; the easiest way to get there is to follow the existing warning's own advice and refit an unconstrained answer with the default solver (C12). Second, the profile-likelihood interval for a weak phase's scale can be cut short by the hold that freezes an unseen phase's cell, because each refit inside the interval re-decides that hold: on the trace-phase fixture the upper end lands 0.56 esd early, on a jump the hold made rather than where the profile crosses the threshold (C2). The other four do not interact on their datasets: the intermediate stage tolerance changes no hold decision on cpd-1a with zircon (the flip WP-2002 recorded no longer reproduces), never even binds on the Le Bail fixture, the roughness seed matters for Pitschke's model only on CPD corundum, and extinction and roughness never both turn on. Six questions for the maintainer, (7)-(12), join the six already waiting; nothing was fixed. *Done* (PR #1576, docs and measurement scripts only): § Measured gains C12, C2, C18, C19, C20, C21; scripts `stephens_start.py`, `scale_interval.py`, `ftol_holds.py`, `lebail_ftol.py`, `roughness_seed.py`, `extinction_roughness.py` with their raw JSON lines in `docs/wp/2018-measure/`. *Measured*: C12 on brucite (LM protocol of `test_acceptance_stephens.py`) from eight starts: from a block outside the cone the rows drop in all three strain stages and the fit ends 19 of 43 reflections out, Rwp 0.18054, TRF's answer to 0.14 of TRF's esds; the carried TRF answer refitted under LM ends 19 of 43 out again; with the seed's skip removed both end inside. C2 on the trace and on cpd-1a's corundum: trace upper end 4.609e-6 shipped against 5.146e-6 with the hold off during the interval (lower ends equal to 3e-7); on cpd-1a no refit holds anything and both arms agree to every digit. C18 on cpd-1a + zircon at 1e-6 and None, with and without the closing stage: identical hold decisions in every stage, values within 0.0053 plain esd (0.065 without the closing stage), iterations halved. C19 on #740's pattern: 1e-6, None, and the positive arms 1e-2, 1e-1, 5e-1 bit-identical (2-3 iterations a stage). C20 on five lab patterns: Pitschke's c start-invariant except CPD corundum, where the start at 0 reaches τ's ceiling outside the regime and moves Al Biso 0.83 plain esd. C21 on the same five: at most one of extinction and roughness leaves its identity, either order within 0.0072 plain esd; the idle partner inflates neighbours' esds up to 2.3×. *Gotchas*: the C12 dataset row's "user block outside the cone" is reached naturally by carrying a TRF answer into an LM refit. The C19 fixture cannot exercise its pair: a positive arm there cannot fail (question 9). The C2 cpd-1a row cannot either: corundum's trace is too well determined for a pinned scale to reach the support threshold, so the trace fixture is the one that does. The CuCr₂O₄ ramp half of C18 waits on the same series harness as C3. Plain esds (`stderr_uncorrected`) are used for C18, C20, C21 as WP-2002 did. *Tests*: no file under `src/` or `tests/` changed, so the fast suite was not rerun (last run at 2ee0c3af3, entry below); `tests/test_docs_consistency.py`, ruff and `python -m tests.reader_output` as in the PR body. A Linux x86_64 workstation (py3.12) ran C2 on cpd-1a and the four C18 arms (11-45 s each, ≤ 380 MB, one pinned core each); the rest ran on macOS arm64, `[dev]` (≤ 4 s a fit). *Review*: a read-only review agent confirmed every arm's patch acts as stated and the numbers against the JSON; it found the C2 hold's mechanism stated beyond what was traced (a prior that `run_stage` does not pass), the C20 χ² signs and FAP's own outside-the-regime flag missing, and five figures (a tolerance of 0.13 for 0.133, an esd rounded wrong, a Δχ² range, fluorite's roughness esds taken from the wrong arm, a χ² tolerance of 2.8e-4 for 3.8e-4); all corrected (1827dc79d). Next: (1) the maintainer's rulings on questions (1)-(12); (2) C22, C25, C26, C27, C29, C33, C35, C36, C37 and C3a by § Datasets, of which C35 waits on the series harness.

- **2026-11-16 (second round)** — Two more pairs of the clash table are measured, the capillary absorption correction against the hold that freezes a displacement parameter the data cannot separate from its phase's scale (C4), and the hold that freezes an unseen magnetic moment direction against the test that decides whether a moment angle sits on a symmetry-fixed direction (C7). Neither changes an answer anyone reads on the datasets chosen for it: absorption moves no hold decision, and on SRM 660a the hold never fires, so the predicted displacement shift lands to 3e-9 Å²; on Cr₂WO₆ and LaMnO₃ the moment hold never acts, so the pair never meets. What the measurements did find: a phase with one reflection in range cannot carry an absorption correction in its displacement parameter, held or free, so an undeclared µR moves its weight fraction 6 % instead; and on the one fixture where the moment pair does meet (#599's rhombohedral site), the angle test gives the right verdict only because the hold and the turn ran first, and without either it certifies a trapped or a flat direction as symmetry-fixed. Two questions for the maintainer, (5) and (6), join the four already waiting; nothing was fixed. *Done* (PR #1576, docs and measurement scripts only): § Measured gains C4 and C7; scripts `ridge_absorption.py` and `moment_hold.py` with their raw JSON lines in `docs/wp/2018-measure/`. *Measured*: C4 on `test_scale_b_ridge.py`'s four phases moved to a capillary with µR = 1.0, hold on and off, µR declared and not: the probe reads iron at 5.9e-13 and 7.4e-13 against the 6.3e-8 floor either way; sites above the floor move by ΔB to 1.3e-5 Å²; the iron's scale takes exp(2ΔB·s²(110)) = 1.0613 (measured 1.0613). On SRM 660a the separation is 0.771-0.780 and the forced-hold positive arm loses ΔB entirely (Rwp 0.088 to 0.112). C7 over four arms (shipped, no hold, no turn, no test) on Cr₂WO₆ 4 K, LaMnO₃ 50 K and the #599 fixture with the truth at 10.2° from [111] and on it, noise-free and Poisson: switching the test off moves no value in any of the six datasets, only esds (the modulus ×1.11-1.26 wherever the test zeroes an angle); without the turn the fit ends at #599's trap, 27.84° from [111], and the test calls it stationary; without the hold the values are the shipped ones but the polar angle reads stationary with a 0.39 rad interval and the report says nothing is unmeasured. *Gotchas*: the C4 dataset row named the fluorite as the phase the hold fires on; it is the iron. The two magnetic datasets chosen for C7 cannot exercise it (two moment DOFs at most); the #599 fixture does. `ref.fit` inside the tests' own `_fit` helpers records a run unless `RIETX_TELEMETRY=0`, which `moment_hold.py` sets. The noise-free #599 rows read the test's statistic at roundoff (χ² 4e-22 to 2e-13), which is why the Poisson variants exist. *Tests*: no file under `src/` or `tests/` changed, so the fast suite was not rerun (last run at 2ee0c3af3, see the entry below); `tests/test_docs_consistency.py` and the other gates as in the PR body. A Linux x86_64 workstation (py3.12) ran the Cr₂WO₆ and LaMnO₃ arms and one LaB₆ arm (4-52 s each, ≤ 330 MB); the rest ran on macOS arm64, `[dev]`. *Review*: a read-only review agent confirmed every arm switches off what it claims and every number against the JSON; it found the C4 ΔB and esd figures quoted for the hold arms as if for all four, two fluorite and Cr₂WO₆ wordings, and C7's dependency written as an order no arm tested; all corrected (6e969871a). Next: (1) the maintainer's rulings on questions (1)-(6); (2) C2, C12 (brucite from a user block outside the cone), C18, C19 and the rest by § Datasets.

- **2026-11-16** — The first four pairs of the clash table are now measured, each with and without the action in question. On the datasets chosen for them none changes an answer anyone reads: the width profile of a trace phase gives the same range whether or not the support hold acts during its refits, and on the planted absent phase the cell window and the cell reset never act while the hold and the collapse each produce the default answer alone, and on NAC the Gaussian-width rows never come near binding. A synthetic pattern built to reach that floor shows the rows moving the widths 0.4-0.7 esd, toward the truth. What the measurements did find is about what a caller is *told*: when the fit sits on the Gaussian-width floor of a combination of U, V and W, the only record is an unlocated info message, and the three widths each say "not at a bound" with a free-fit esd; and one absent phase can draw two findings (support plus floor, or support plus runaway) for one cause. Four questions for the maintainer are written into § Questions for the maintainer; nothing was fixed, as the non-goals require. *Done* (PR #1576, docs and measurement scripts only): § Measured (2026-11-16, task 3) holds C1, C3, C10 and C14 with numbers and sizes in esds; scripts and raw JSON lines in `docs/wp/2018-measure/` (`common.py`, `fraction_profile.py`, `absent_phase.py`, `gaussian_rows.py`, three `*_results.jsonl`), PNGs to `tests/output/wp2018/`. Task 3 not ticked: 18 live pairs are still unmeasured. *Measured*: C1 on the two-basin trace, the hold keeps the cell through 2 of 12 grid refits, both in the barrier (at 3 more it is released at the answer), W moves 0.013 pp and Δχ² 0.06, the profile's range 0.930-77.07 % and excess 117.77 identical; WP-1320's runaway is not reproduced under WP-1523's test. C3 on the absent-phase fixture over eight arms: window and reset change no digit, hold ≡ collapse (1e-14), held a = 5.2 Å vs free 5.0243(21) Å at 2.62σ; two injected-escape positive arms show the reset firing and the collapse claiming a path both reach. C10: `FLOOR_HIT` and `PHASE_UNCONSTRAINED` both fire on the absent phase under the default plan, on different paths. C14 on NAC: rows never within 1179 ε, rows off is the shipped fit to every digit; on a synthetic touching-truth LaB₆ the rows hold Γ_G² at ε, move U, V, W, X 0.4-0.7 esd toward the truth, and leave only `CONSTRAINT_ACTIVE` with an empty `where`. *Gotchas*: the 2026-11-09 C14 row missed `CONSTRAINT_ACTIVE` (a channel exists, it names no path); NAC is the wrong dataset for C14 since WP-1938. `rietx.refine` imported as a module attribute is the function: the scripts use `importlib.import_module("rietx.refine")`. The NAC arms take seconds on either machine; the Linux x86_64 run agrees with the Mac to 12 digits in Rwp. *Tests*: `tests/test_docs_consistency.py` 26 passed (macOS arm64, `[dev]`); fast suite `-m "not slow" -n 6 --dist loadgroup` on a Linux x86_64 workstation venv (py3.12) at 2ee0c3af3: 14850 passed, 280 skipped, 32 xfailed, 0 failed, 595 s; no test added, so no count moved by this branch; `python -m tests.reader_output` exit 0, unchanged. *Review*: a read-only review agent checked the patches, the probe mirror and the Γ_G² formula (no code bug) and found four overstated tolerances and a wrong hold count in C1; all corrected (2ee0c3af3), plus a note that the no_hold patch also empties the width-twin hold's input (no effect on this fixture). The handover entry's first commit (c11aec119) named the workstation host, removed in 670baa1c8: a squash merge keeps it off main. No forward reference pushed: all four findings wait on rulings, and none changes another WP's work until one is made. Next: (1) the maintainer's rulings on questions (1)-(4), which set C1, C3, C10 and C14's verdict column; (2) then C4 and C7 (fixtures in the tree, no build needed), then C2, C12, C18, C19 and the rest by § Datasets; the CuCr₂O₄ ramp for C3 and C35 waits on a family-B series harness (WP-2003).

- **2026-11-09** — Every entry of the clash list now has a row saying whether it still exists in today's code. Of 42 entries (the 38 numbered pairs and C3's four sub-pairs), six no longer exist, mostly because the cell clamp, the position bounds and the frozen `lor_strain` were removed since the list was written; fourteen are kept apart by the code on purpose; twenty-two are real and none of those is measured. So the list to measure has shrunk from 42 to 22, and no fit has yet said whether any of them changes an answer. *Done* (PR #1512, docs only): tasks 1 and 2 ticked; each of the 22 live rows has a dataset chosen before running (§ Datasets for the live rows), six of them needing a fixture built or a vendored file modified (C3a, C10, C12, C27, C29, and C2's low-scale probe). § The table holds all 42 at 4c55b9011 with file:line. Live (22): C1, C2, C3, C3a, C4, C7, C10, C12, C14, C18, C19, C20 (measured in part by WP-2002), C21, C22, C25 (reconciled by intersected bounds), C26, C27 (idempotent by reading), C29 (rarely binding), C33, C35, C36, C37. Gone (6): C3b, C3c, C3d, C13, C24, C30. Designed apart (14): C5, C6, C8, C9, C11, C15, C16, C17, C23, C28, C31, C32, C34, C38. C1-C3d and C6 were read in this session; C4, C5 and C7-C38 by three delegated read-only readers, spot-checked at eight lines. No clash found or routed and no issue filed, since nothing was measured. `### Inherited` kept: both entries still describe the tree. *Gotchas*: read-only verdicts, not measurements; two rows the readers flagged as narrow gaps are worth a first look: C14 (a width held on a Γ_G² row is never reported at a bound) and C15's TRF and joint-fit case (no rows built, so a negative U or V can still reach the clamp). The session was a ghostshift runner under a hard stop; no fit ran. On this Mac a pytest run with `-n` is refused unless it goes through `testslot.sh`. *Tests* (macOS arm64, `.venv` `[dev]`): `tests/test_docs_consistency.py` 25 passed; `python -m tests.reader_output` exit 0, unchanged. Next: (1) measure C1 and C3 first, both orders or with and without the action, Rwp, the shared parameter and its esd, PNGs to `tests/output/`; (2) then C14 and C10, whose gaps are reporting rather than value changes and may route straight to their owners.
- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the clash table moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

