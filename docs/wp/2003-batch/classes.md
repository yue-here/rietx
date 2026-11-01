# WP-2003 batch: the chain actions, by class

Task 2's tiering half: a proposed tier for each of the 111 entries in `inventory.json`, grouped
into eleven classes for the maintainer's batch. `rows.json` beside this file holds every entry's
proposal (tier, kind, evidence as it would enter the table, grounds, class, demotion, dissenter,
response, and the decision owed). The rule is `../../milestones/generality.md` § The rule; the
measurement this leans on is `reseed.md` and the 2026-10-24 handover's *Measured* block.

**Superseded picks.** This file is the 2026-10-24 draft. `batch.md` holds the current picks,
revised against the clash table, then on 2026-10-25 against DESIGN.md § Rules on the numbers
re-measured on `main` after WP-2045, and `rows.json` follows `batch.md`. Changed: C1 (the fence
a reported ratio; escalate on diverged or raised only, the `max_iter` and `CELL_RUNAWAY`
triggers measured and not adopted), C2 (rank by the full cost; `max_iter` keeps tying
`converged`; `on_error` an open question; an `error`-level attempt counted as diverged), C3
(the bound the caller's, landing after `clashes.md` X16), C9 (the warm start the caller's, what
is carried tested for invariance; the closing stage kept) and C10 (the joint absent-phase hold
its own row). The table and the sections below are left as drafted.

**Already in the table.** 17 rows needed no approval and were written into `src/rietx/_audit.py`
on 2026-10-24 (`"applied": true` in `rows.json`), each off `UNAUDITED_BASELINE` and, for the five
codes given a response, off `RESPONSE_BASELINE`: tier 1, `SERIES_PATTERN_FAILED` (+ suggestion),
`SIZE_NORMALISED_ACROSS_WAVELENGTHS` (+ suggestion), `STAGE_FREED_NOTHING` (+ suggestion),
`NOISE_FLOOR_REL`; tier 2, `SequentialRefinement.fit:mode` and `:two_theta_limits`; caller,
`SEQUENTIAL_CANCELLED` (+ suggestion), `SEQUENTIAL_PATH_CHECK_INCOMPLETE` (+ suggestion, no
response: it raises at two levels), `PARAMETRIC_OUT_OF_RANGE` (+ suggestion), `fit:prepare`,
`fit:constrain`. 11 more were tiered by the previous session (`"status": "tiered 2026-10-24"`).

**Vocabulary** (as WP-2002's batch). Tier 1 physics or arithmetic; tier 2 a validating citation
or the same choice by default in one of the seven programs (`docs/practice.md`); tier 3 rietx's
own, kept only with a dated approval. `invariant` and `caller` are the record's fourth and fifth
classes. Two proposal-only words in `rows.json`: `"covered"` marks a row-less joint-fit act whose
record field already has a 2002 row and ruling, and a `null` tier with a `demotion` marks an entry
proposed for removal. A row-less entry carries `row_note`: the row it should get, or why none.

| Class | Entries | What you decide | Draft pick (2026-10-24; current in `batch.md`) |
|---|---|---|---|
| C1 The Rwp fence and status-only | 11 | What triggers the ladder | Escalate on diverged, raised or `max_iter`; the 1.25 fence a reported statistic and opt-in trigger, once one cheap arm is measured |
| C2 Ladder, quarantine, kept attempt | 13 | Confirm the protection; tier its parts | Pass; `seeded_from` lands; rank `max_iter` below converged |
| C3 First-rung budget | 4 | Invariant once the closing-stage clash is fixed | Fix, add a biting arm, then invariant |
| C4 The discontinuity scan | 7 | Approve the demotion and what picks the verified pairs | `SeriesResult.steps`, no diagnostic; the caller names the pairs |
| C5 Path dependence | 6 | A 3σ verdict inside an opt-in switch | Demote to a field of gaps; split the incomplete-check code |
| C6 Persistent-finding summary | 5 | The half cut decides existence | A field of counts, measured on agents first |
| C7 Width growth | 6 | Rulings for WP-2004 | A field; hand the three constants to 2004 |
| C8 The moment carry | 5 | Rare feature, judgement ground alone | Pass; `floored` lands; split the onset code |
| C9 Carry policy | 10 | The warm start and what it carries | `carry` tier 2 with GSAS-II's dissent; measure the Le Bail carry |
| C10 The joint fit | 26 | Holds inherit 2002; three findings | Covered; fix the `vars.X` escape; align the support statistic |
| C11 Caller and invariant rows | 18 | Plain | Add three test arms for `x`, `x_label`, `labels` |

---

## C1. The Rwp fence and the status-only alternative

**Stakes.** The fence moves every reported value of a pattern it escalates. On disk it acted on
one real pattern: IUCr CPD cpd-1b with the closing stage on, whose warm rung ended `max_iter` at
Rwp 0.7652 (3.75× the fence) with corundum *a* 4.987(88) Å against the independent fit's
4.75809(38) (4.8 % off) and a zero shift of 18.0(74)°; escalated, it kept the staged rung at
4.75804(38), 0.13 esd from the reference. Dissenter named: a refiner whose series gains a lasting
misfit (planted: 114 patterns above the fence, 4.3× the evaluations, no value past 0.0007 esd).

**Rows.** `RESEED_FACTOR`, `fit:reseed_factor`, `fit:reseed`, `_reseed_needed` (row-less),
`SEQUENTIAL_RESEED` (+ suggestion), `SeriesEntry.reseeded`, `SeriesEntry.rwp_fence`,
`SEQUENTIAL_RWP_OUTLIER` (+ suggestion), `_chain.rwp_outlier_carve_out` (row-less).

**The decision.** What sends a warm fit up the ladder: the Rwp fence at 1.25× the accepted
median (today), or status alone with `max_iter` counted as unfinished, the fence kept as a
reported number (`rwp_fence`, `above_fence`, `SEQUENTIAL_RWP_OUTLIER`) and as the trigger a caller
opts into by passing `reseed_factor`.

**Evidence.** `_reseed_needed` rejects a diverged attempt or one above the fence and never tests
`max_iter` (`sequential.py:2004-2009`); the fence is `reseed_factor` × the median of the accepted
Rwp (`:1992-2001`). No program restarts a pattern by itself (`docs/practice.md` § Sequential
refinement, closing paragraph), so every part is tier 3. Measured on eight families
(`reseed.md`): the fence acted on CPD (cpd-1b, above), on planted (115 escalations, 49 near-tie
reseeds within 7.6e-7 relative Rwp) and on tut05-broken (pattern 4 kept cold at 19× its fence;
every esd-carrying value agrees across arms to 2e-10 esd, eight esd-less rows differ). It is
bit-identical on trigger, Cr₂WO₆, tut05-jump, the planted null twin, and CPD with the closing
stage off, where nothing escalated. cpd-1b's bad warm rung came back `max_iter`, not `diverged`,
and the status arm fired `CELL_RUNAWAY` there: the fence covered for the closing stage on a warm
refit (C9's `_collapse`, and the clash table's "closing stage × fence").

**The case against the fence as trigger.** Its one real rescue is caught by counting `max_iter`
as unfinished, and on planted the status arm (which escalated only the budget-forced pattern 87)
cost 2 716 evaluations against 11 790. Rwp tracks Rexp, which is why the width screen reads GoF
(`sequential.py:283-287`), so a fence on Rwp fires on falling counts with a right model
(WP-1469's 24-pattern ramp: +55 % iterations, 18 of 18 flagged when it was a quarantine).

**The case against status-only.** Unmeasured. Counting `max_iter` escalates every warm rung that
hits its plan's own cap; Cr₂WO₆'s 150 K warm rung ends `max_iter` in every arm (824
evaluations), so status+`max_iter` would escalate it where the fence did not, at a cost no arm
has measured. And the escalation never keeps a worse attempt (`_prefer`), so the fence's
over-firing costs evaluations, not answers.

**My pick.** Escalate on diverged, raised or `max_iter`; keep 1.25 as the default of a reported
statistic and of the opt-in trigger. Not before one arm is run: status+`max_iter` on planted
(about 2.5 min an arm), CPD's first two patterns (about 40 min) and Cr₂WO₆. I would change my
mind if that arm misses cpd-1b or costs more than the fence on planted. Two fixes ride with
either ruling: `reseed=False` should not bound the first rung at all (today a bitten first rung
escalates against the switch, `sequential.py:1563-1573`, against its docstring at `:1077-1083`),
and `reseed_factor` should be validated (`inf` is accepted unchecked and also switches off the
discontinuity scan's above-fence drop).

**Rows that follow.** `SEQUENTIAL_RESEED` tier 3 with response `warning` (it says the chain
restarted, the package's own act, as `CELL_RUNAWAY` does); `SEQUENTIAL_RWP_OUTLIER` stays
`warning` while 1.25 is an approved threshold and drops to `info` if the fence becomes a reported
number; the carve-out (an above-fence pattern is not quarantined) passes with no dissenter, since
not quarantining a converged fit is no act on its values, and its scan half leaves with C4.

---

## C2. The ladder, the quarantine and the kept attempt

**Stakes.** The quarantine moves every successor of a diverged pattern; none on disk (no arm
quarantined anything on the eight families); dissenter none found. The ladder moves a pattern's
values only through the attempt it keeps (C1's cpd-1b).

**Rows.** `_ladder` (row-less), `SeriesEntry.rung`, `.rungs_tried`, `.rungs_raised`, `_prefer`
(row-less), `_chain.quarantine` (row-less), `SEQUENTIAL_UNRECOVERED` (+ suggestion),
`fit:on_error`, `_chain.on_error_carry` (row-less), `fit:refit`; applied, `SERIES_PATTERN_FAILED`
(+ suggestion, tier 1).

**The decision.** Confirm the quarantine as Rule 1's protection ("seed no successor from a
diverged fit"), and approve the ladder's parts: its rungs (collapsed warm, staged from warm,
staged cold; `RUNGS`, `sequential.py:356-360`), their order, and the give-up point after the
cold rung. Approve `SeriesEntry.seeded_from` as the quarantine's record (task 3).

**Evidence.** The rungs cost 838-904, 1 623 and 2 863 iterations on CPD sample 1 (WP-1051,
`sequential.py:550-555`). A diverged kept attempt seeds no successor, joins no median and gives
no first-rung sample (`:1685-1724`). EasyDiffraction moves its start values only on a successful
fit (checked); GSAS-II and MAUD end the chain (`docs/practice.md`). The quarantine is shown only
on an injected divergence (`tests/test_sequential.py:1158`) and a quarantined pattern's variable
(`:637`); no family on disk reaches it, so its kept case is the injected one (the record's
"a guard the goldens never exercise").

**Record.** The pattern and its rung are on the record (`2003-batch/README.md` § Quarantine's
record); the successor seeded from an earlier pattern is not. `SeriesEntry.seeded_from` closes
that, and is also where `_carry_into` and `on_error="carry"` would say which state seeded a
pattern. The middle rung's Rwp is recorded nowhere (`rwp_of` is local, `sequential.py:1545`).

**`_prefer`'s criterion.** Proposed tier 1 for its last step: of two minima of one pattern under
one weighting, the lower weighted residual is the better fit by the objective's own definition
(up to restraint and penalty rows Rwp leaves out). The truncated-below-untruncated step is
WP-1127's guard of answer invariance (C3). One part to rule: `_better` ranks `max_iter` equal to
`converged` (`sequential.py:1962`); a refiner ranks an unfinished fit below a finished one. It
decided nothing on disk.

**`on_error="carry"`.** Tier 2: EasyDiffraction carries on past a failed file and does not seed
from it (checked). It switches on an action, so the dissent counts: GSAS-II and MAUD stop the
chain, and a refiner may want the batch to stop at the first failure so the model is fixed
before 200 patterns are spent. `"raise"` keeps what converged (`sequential.py:1622-1638`), so the
choice is between finishing the batch and stopping it, not about lost work. Pick: tier 2 with the
dissent named, approved as protection of an expensive batch.

**`refit="single"`.** Tier 2 (GSAS-II and EasyDiffraction fit every pattern with one vary list,
checked), not applied because it sets the ladder's first rung. Dissent on cost only
(trigger-series: staged 1 253 nfev against collapsed 1 603).

**The case against.** The ladder's rungs and order rest on one real family's iteration counts,
and its give-up point on an injected divergence. A refiner whose model makes the staged plan the
cheaper first rung would order it first; that is a cost, and `refit="stages"` is the caller's
way.

**My pick.** Pass the quarantine and the ladder (tier 3, kind 1); `seeded_from` lands with the
ruling; `SEQUENTIAL_UNRECOVERED` tier 3 with response `warning`; rank `max_iter` below
`converged` in `_better`.

---

## C3. The first-rung budget

**Stakes.** Invariant where the bound bites no winner; where it bites one, a truncated rung the
closing stage converges is kept, within 8e-4 esd of the unbounded chain (thermal ramp at factor
0.5, the clash table). Dissenter none found.

**Rows.** `FIRST_RUNG_FACTOR`, `FIRST_RUNG_SAMPLES`, `fit:first_rung_factor`,
`_first_rung_budget` (row-less, rides `FIRST_RUNG_FACTOR`'s row).

**The decision.** The answer-invariant class, held back: since the closing stage, a truncated
warm stage followed by a converged closing stage reads `converged` (`sequential.py:213-219`), so
neither the forced escalation (`:1563`) nor `_prefer`'s rank sees the truncation.

**Evidence.** Kept first rungs cost 27-64 evaluations on trigger-series and 25-107 on
cpd-series, a losing one about 400; 0 of 1 030 and 0 of 392 accepted values moved (WP-1127). The
two invariance tests (thermal ramp, fast; CPD, slow) assert equality to the bit and every kept
first rung under its budget, so they cannot see the clash.

**My pick.** Read the truncation off the bounded warm stage's own status rather than
`result.status`, add an arm where the bound bites a winner to the fast test, then tier all four
`invariant`. Under `reseed=False`, no budget (C1).

---

## C4. The discontinuity scan

**Stakes.** No value moves: the scan reports. It fired on planted (two steps), tut05-jump
(three) and tut05-broken under an infinite fence. Dissenter named: the maintainer's own example,
a jump that is a transition, a sample shift, a beam dump or a wrong model.

**Rows.** `SEQUENTIAL_DISCONTINUITY` (+ suggestion), `DISCONTINUITY_FACTOR`,
`DISCONTINUITY_SIGMA`, `MIN_POINTS_FOR_DISCONTINUITY`, `_verify_discontinuities` (row-less,
caller), `_relative_paths` (row-less, tier 1).

**The decision.** Approve the demotion the WP's Context states: the code goes, its statistic
becomes `SeriesResult.steps` (every step in esds, largest first, no threshold) with its
`rietx.help` entry carrying the reading (what a jump can be, and that a symmetry-mode refinement
separates the cases), one line in the trajectory block, and no diagnostic. Then decide what
`verify_discontinuities` refits once no flagged pair exists.

**Evidence.** The thresholds decide whether the diagnostic exists (5× the median step and 3σ,
`sequential.py:222-229`; no measurement), so by the record's § Demotion no diagnostic remains.
Three readers of the flagged pairs move: `SeriesResult.discontinuities`, the trajectory plot's
shading, and `_verify_discontinuities` (`sequential.py:1350`). The verification ratio lives in
`Diagnostic.value` on the removed code, so it needs a field (`SeriesStep.cold_ratio`, name to
choose).

**The case against.** Agents stop on stated criteria (v1.3: 7 of 8), and `steps` states none.
The record answers it: a contested demotion is measured on agents and lands whatever the result,
with the explanation reworked if the result is poor.

**My pick.** Demote; remove the three constants with it; `verify_discontinuities` refits the
pairs the caller names, or the largest *k* steps with *k* the caller's, which keeps that switch
`caller`; gate each cold refit with `_auto_intervals = False` (task 3).

---

## C5. Path dependence

**Stakes.** No value moves: the reported entries are the forward chain's either way. No case on
disk (no measured family ran `direction="both"` in the reseed measurement). Dissenter named: a
refiner reading n paths × m patterns at 3σ, where chance flags are expected, or one reading a
sub-3σ gap repeated over every pattern as path dependence; the largest flags measured were axis
relabellings (81.5σ in Fddd, `docs/skill/rietx/references/series.md:136-150`).

**Rows.** `PATH_DEPENDENCE_SIGMA`, `SEQUENTIAL_PATH_DEPENDENT` (+ suggestion); applied,
`NOISE_FLOOR_REL` (tier 1) and `SEQUENTIAL_PATH_CHECK_INCOMPLETE` (+ suggestion, caller).

**The decision.** The switch is the caller's (`fit:direction`, caller since 2026-10-24), but
3σ is a package number used once it is on, so it is tiered on its own; it has no provenance
(`sequential.py:244-245`) and decides whether the code exists.

**My pick.** As C4: the code becomes a record field of each path's forward-backward gap in
combined esds, largest first, with its help entry; the suggestion's three alternatives move there.
`SEQUENTIAL_PATH_CHECK_INCOMPLETE` splits into a `warning` code (the comparison did not run) and
an `info` one (it ran on less), so each takes a literal response. `fit:direction`'s row is
re-read if the code goes.

---

## C6. The persistent-finding summary

**Stakes.** No value moves. It fired 26 times on CPD and 34 on trigger; its origin is WP-1110's
68-pattern series, 425 `BOUND_HIT` read as "42 of 68". Dissenter named: a refiner whose impurity
appears in the last 40 % of a ramp, hidden by "more than half".

**Rows.** `SEQUENTIAL_PERSISTENT_FINDING` (+ suggestion), `MIN_POINTS_FOR_PERSISTENCE`,
`_persistent_diagnostics.half` (row-less), `NOT_A_SERIES_FINDING` (row-less).

**The decision.** The count is tier 1. The half cut and the five-pattern minimum decide whether
the code exists, and its level is the worst occurrence's, computed at run time
(`sequential.py:2505`), so it can take no literal response.

**My pick.** A record field of counts (every per-pattern code and path with count, n and worst
level, largest first), one report line per top count naming the code and the path, which also
answers the WP's one-line-form cost (tutorial 05, cells 19 and 34); no diagnostic. A contested
demotion of a stated criterion, so the agent harness runs before it lands. The suggestion ("change
the model or the plan") goes with the code: it also fires on a declared `info` choice. If the code
stays, the half cut and the minimum are tier 3 and `NOT_A_SERIES_FINDING` tier 1 by its own rule.

---

## C7. Width growth (rulings for WP-2004)

**Stakes.** No value moves. Silent on CPD (real); fires on the synthetic soak; issue #451's
operando chain is not on disk. Dissenter named: a refiner whose strain grows for real while GoF
rises for a second, independent reason; the suggestion names only the missing component.

**Rows.** `SEQUENTIAL_WIDTH_GROWTH` (+ suggestion), `WIDTH_GROWTH_FACTOR`,
`WIDTH_GROWTH_GOF_FACTOR`, `WIDTH_GROWTH_SIGMA`, `_WIDTH_SUFFIXES` (row-less, tier 1).

**My pick.** Three tier-3 thresholds decide existence, and one real family is on disk, so a
record field: per phase width, its ratio to its first measured value with that ratio's esd, the
growth in esds, and the GoF ratio, largest first, with a help entry naming both readings. The
three constants go to WP-2004's `### Inherited` with that ruling; nothing is bumped here.

---

## C8. The moment carry (rare feature)

**Stakes.** The floor moves the successor's starting modulus, never the entry's own value.
Cr₂WO₆'s 150 K pattern fires `SEQUENTIAL_MOMENT_HOLD` in every reseed arm; dissenter none found
(an ascent out of the floor terminates at once, `tests/test_magnetic_series.py:23-27`).

**Rows.** `_floor_unsupported_moments` (row-less), `SEQUENTIAL_MOMENT_HOLD` (+ suggestion),
`SEQUENTIAL_MOMENT_ONSET` (+ suggestion).

**My pick.** Pass under the rare-feature clause (one synthetic ramp, one real neutron pair), tier
3 with grounds saying so; `SeriesEntry.floored` (task 3) is its record and the row it is keyed
on, so `SEQUENTIAL_MOMENT_HOLD` can stop cutting its list at four labels; `SEQUENTIAL_MOMENT_HOLD`
tier 3 with response `warning`. `SEQUENTIAL_MOMENT_ONSET` raises at a computed level and through
`model_copy` (`sequential.py:2699`, `2784-2858`): split it into an `info` bracket and a `warning`
code for an unconverged supported side or disagreeing chains. Its support test is WP-2004's
(`MOMENT_SUPPORT_SIGMA`).

---

## C9. The carry policy

**Stakes.** The warm start moves every value of a chain: on CPD the chain sits 7.05-14.2 esd from
the independent fits, worst path a `lor_strain` each time. Dissenter named: GSAS-II's default
(each histogram starts from its own values unless `Copy2Next` is ticked).

**Rows.** `refine_sequential:carry`, `:carry_hkl_intensities`, `fit:plan`, `_carry_into`,
`_reanchor_carried`, `_carry_variables`, `_collapse`, `_fit_one.declared_wavelengths` (row-less);
applied, `fit:mode` and `fit:two_theta_limits` (tier 2).

**Evidence.** The warm start: EasyDiffraction (checked) and FullProf's cyclic mode (inferred);
rietx carries every entry where GSAS-II and EasyDiffraction carry the varied ones, and the two
differ only where a fixed value changes during the chain (`docs/practice.md`). Extracted
intensities: no program carries them by default; GSAS-II does under its opt-in `Copy2Next`.
The width twin hold makes the selection matter: carrying the widths but not the scales averages
Rwp 0.1282 against 0.1256 carrying everything and 0.1258 independent (a strict xfail).

**My pick.** `carry` tier 2 with GSAS-II's dissent named and approved, the series verb's own act;
`carry_hkl_intensities` tier 3, pending a Le Bail and a Pawley chain run carried and not;
`fit:plan` tier 3 by extending B7's approval to the series seat; `_carry_into` tiered with
`carry` and keyed on `seeded_from`; `_reanchor_carried`, `_carry_variables` and
`declared_wavelengths` tier 1 and no row (no choice beyond `carry`'s, or a diagnostic's
reference). `_collapse` tier 3 for its details (no stage seed, the plan's largest `max_iter`,
the closing stage carried); the closing stage on a warm refit is what ran cpd-1b's cell away, so
its chain cost and effect are measured before the row is recorded (WP-2036 owns the cost).

---

## C10. The joint fit

**Stakes.** The joint holds move the shared columns they hold. No case on disk beyond the
synthetic fixtures; dissenter none found beyond those of the 2002 rulings they inherit.

**Rows.** Applied: `SIZE_NORMALISED_ACROSS_WAVELENGTHS` (+ suggestion, tier 1),
`PARAMETRIC_OUT_OF_RANGE` (+ suggestion, caller), `STAGE_FREED_NOTHING` (+ suggestion, tier 1).
Proposed: `PARAMETRIC_TARGET_UNSEEN` (tier 3 on B1's threshold, response `warning`),
`PARAMETRIC_FORM_REJECTED` (tier 2 on `FORM_TEST_LEVEL` once clash B16 is measured, response
`warning`), their suggestions (tier 1), and sixteen row-less entries.

**Covered by 2002's rows.** Each joint hold writes the single runner's record field, whose row
and ruling cover it: `_hold_unsupported_phases_multi` → `StageResult.held` (B1, approved
2026-10-23); `_rehold_multi` → `released`, `collapsed` (B1); `_hold_scale_b_ridges_multi` →
`scale_b_held` (tier 1); `_hold_flat_moments_multi` → `moment_flat_axes` (tier 1) and
`moment_turned` (B2); `_hold_width_twins_multi` → `width_twins_held` (approved 2026-10-23);
`_reset_cell_runaway_multi` → `cell_reset` (B8); `_run_plan.seed` → `seeded` (approved
2026-10-21); `_freeze_cell_windows_multi` → the single runner's cell window row (B8, approved
2026-10-20). The joint refuses Le Bail and Pawley, so no force-fix exists here.

**Tier 1, no row.** `size_value_scales` (Scherrer; reported by the applied code),
`bound_intersection` (a shared column satisfies every histogram's box), `_joint_unmeasured_phases`
(the joint face of `RefinementResult.qpa`'s tier-1 row), `_freeze_strain_cap_multi` (the widest
histogram's range, `STRAIN_CAP_RANGE_FRACTION`'s rule over the union; no test names it).
`fit:weights` (1.0: the joint χ² is the sum of each histogram's own, the joint likelihood of
independent measurements) and `SharingMap.is_shared` (Von Dreele 1997, cited at `multi.py:6`, not
read here, so tier 2 waits for the paper) sit at no `DEFAULT_SEATS` seat: a hand row (B14) or a
seat. `_ticks.extra_components` is a builder and decides nothing.

**Three findings for the batch.**
1. **A bug, not a tier**: `_cell_runaway_diagnostic(cell_runaway)` at `multi.py:1632` never folds
   `refine._vars_driven_cell_escapes` (`refine.py:1704`; the single runner folds it at 4480 and
   4710), so a `vars.X`-driven escape in a joint fit is neither reset nor named (WP Context).
2. The joint runner judges support by `CompiledModel.phase_support`, never WP-1523's scale
   significance (`multi.py:413-417`), so the two runners call a phase unseen by different
   statistics under one ruling (B1). Align, or tier the joint statistic on its own.
3. The joint runner seeds no Stephens block where the single one does (`Stage.strain_seed`).

**My pick.** Covered as listed; fix finding 1; rule finding 2 (align, pick); note finding 3.

---

## C11. Caller and invariant rows

**Stakes.** None: no reported value moves. Dissenter none found.

**Rows.** The eleven tiered on 2026-10-24 (`refine_sequential:backend`, `:solver`, `:history`;
`fit:direction`, `:verify_discontinuities`, `:on_result`, `:events`, `:cancel`, `:progress`,
`:telemetry`, `:label`); applied today, `SEQUENTIAL_CANCELLED` (+ suggestion, caller, response
`warning`, scope `series`: it passes `where=[]`), `fit:prepare`, `fit:constrain`; proposed,
`fit:x`, `fit:x_label`, `fit:labels`.

**My pick.** `x`, `x_label` and `labels` are `invariant` once an arm each joins
`test_a_series_observed_is_the_series_unobserved` (`tests/test_answer_invariant_defaults.py:171`);
`labels` needs a label-blind compare, since `chain_answer` carries the labels. `fit:direction`
and `fit:verify_discontinuities` are re-read when C5 and C4 land.
