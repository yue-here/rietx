# WP-2018 — The clash table: actions that read or move the same parameter, measured both ways

Milestone: generality · Status: 🔄 2026-11-09 — all 42 re-derived: 22 live, 14 designed apart, 6 gone; none measured
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

- **2026-11-09** — Every entry of the clash list now has a row saying whether it still exists in today's code. Of 42 entries (the 38 numbered pairs and C3's four sub-pairs), six no longer exist, mostly because the cell clamp, the position bounds and the frozen `lor_strain` were removed since the list was written; fourteen are kept apart by the code on purpose; twenty-two are real and none of those is measured. So the list to measure has shrunk from 42 to 22, and no fit has yet said whether any of them changes an answer. *Done* (PR #1512, docs only): tasks 1 and 2 ticked; each of the 22 live rows has a dataset chosen before running (§ Datasets for the live rows), six of them needing a fixture built or a vendored file modified (C3a, C10, C12, C27, C29, and C2's low-scale probe). § The table holds all 42 at 4c55b9011 with file:line. Live (22): C1, C2, C3, C3a, C4, C7, C10, C12, C14, C18, C19, C20 (measured in part by WP-2002), C21, C22, C25 (reconciled by intersected bounds), C26, C27 (idempotent by reading), C29 (rarely binding), C33, C35, C36, C37. Gone (6): C3b, C3c, C3d, C13, C24, C30. Designed apart (14): C5, C6, C8, C9, C11, C15, C16, C17, C23, C28, C31, C32, C34, C38. C1-C3d and C6 were read in this session; C4, C5 and C7-C38 by three delegated read-only readers, spot-checked at eight lines. No clash found or routed and no issue filed, since nothing was measured. `### Inherited` kept: both entries still describe the tree. *Gotchas*: read-only verdicts, not measurements; two rows the readers flagged as narrow gaps are worth a first look: C14 (a width held on a Γ_G² row is never reported at a bound) and C15's TRF and joint-fit case (no rows built, so a negative U or V can still reach the clamp). The session was a ghostshift runner under a hard stop; no fit ran. On this Mac a pytest run with `-n` is refused unless it goes through `testslot.sh`. *Tests* (macOS arm64, `.venv` `[dev]`): `tests/test_docs_consistency.py` 25 passed; `python -m tests.reader_output` exit 0, unchanged. Next: (1) measure C1 and C3 first, both orders or with and without the action, Rwp, the shared parameter and its esd, PNGs to `tests/output/`; (2) then C14 and C10, whose gaps are reporting rather than value changes and may route straight to their owners.
- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the clash table moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

