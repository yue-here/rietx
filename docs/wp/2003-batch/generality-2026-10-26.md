# WP-2003 generality review, 2026-10-26 (fourth session)

The `generality-review` agent's sections on this branch's audit-table delta and the heuristics
the table cannot see, unedited (`/wp-handover` step 7). The author's answers are in the WP
file's 2026-10-26 (fourth session) handover entry, under *Generality*.

## 1. `SeriesEntry.seeded_from` (action, tier 3, ambiguity 1)

**Verdict: holds.** The case for acting is stronger: no program or refiner I could find seeds a successor from a diverged fit. The row has four defects, though, and the maintainer should see them before batch approval.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `_audit.py` row evidence: "a diverged kept attempt seeds no successor, joins no median and supplies no first-rung sample, so the next pattern warm-starts from the last accepted one" | Accurate. `sequential.py:1721-1731` sets `previous_index = k` only when the status is not `"diverged"`. The field also records two other choices: the `on_error="carry"` skip past a pattern that raised on every rung (schema docstring, `schemas/sequential.py`), and the warm start itself (`_carry_into`, whose `rows.json` row_note keys it on this same field "with carry's tier", i.e. `invariant`). So one row carries three actions with different tiers. | weak |
| 2. Kind of ambiguity | `ambiguity=1` | Kind 1 is right for the quarantine (stopping a diverged fit from seeding the next pattern). The record's own text says so: `generality.md` § The rule, "The quarantine of a diverged pattern passes it too". | holds |
| 3. Case against | `rows.json` quarantine: "dissenter none found" | GSAS-II and MAUD stop the chain at a failure. That dissents from carrying on, not from refusing to seed from the failure, so it is not a dissent here (`docs/practice.md:250-252, 302-304`). One real alternative: after a long quarantined run, a refiner might start the successor cold rather than from an accepted pattern many steps back. The ladder's cold rung already covers that. The case the row does not state is the trigger's failure: X17's 1c `converged` at Rwp 10.83 with an `error`-level code and seeded five successors (corundum 55-73 wt % against 13.5-55.1 weighed; `batch.md` C2 Stakes). C2 question 5 was ruled "after one arm" and has not landed. The mechanical ground asks for a stated case where it fails, and this is that case, missing from the row. | weak (missing failure case) |
| 4. Case for | grounds: "Rule 1's protection: no competent refiner wants a diverged fit seeding its successors" | Strong. It is one of DESIGN.md § Rules, 1's four named protections. EasyDiffraction does the same by default: "only a fit whose `fit_result.success` is true moves the start values (checked)" (`docs/practice.md:251`). No measured cost, since it "fires in no measured family". | holds |
| 5. Tier and source | tier 3, `approved="2026-10-26"` | `batch.md` C2 "Rows that follow" says "`seeded_from` tier 1, a record", but the table says 3. The table follows the convention that an action row takes the action's tier, so 3 is defensible, but the two documents disagree. EasyDiffraction's default (checked in `practice.md`, not by me) would support tier 2 for the not-seeding half. 3 is the conservative choice. The approval is the authoring session's own, under the maintainer's delegation (`batch.md:74`). | weak (documents disagree) |
| 6. Dataset families | "fires in no measured family … shown on the injected divergence (tests/test_sequential.py)" | Zero real families. The kept case is an injected one, as the record allows for a guard ordinary fits never trigger. The row names the file but not the test: it is `test_an_unrecovered_pattern_seeds_nothing_and_joins_no_median`, which now asserts `seeded_from == [None, 0, 0]`. | holds (injected case exists) |
| 7. Record of firing | the field itself, plus `SEQUENTIAL_UNRECOVERED` naming where the successor started | Present. But `None` means both "no warm start" and "document written before the field" (schema docstring). That is WP-1076's defaulted-empty-reads-as-an-answer shape. `SeriesResult.steps` uses `None` for "not recorded"; this field cannot. | weak |

Would change the verdict: C2 question 5 landed (an `error`-level kept attempt counted as diverged) with X17 named in the row as the failure case, and one tier agreed between `batch.md` and the table for a field that records three actions.

## 2. `SeriesEntry.floored` (action, tier 3, ambiguity 1)

**Verdict: holds.** The case for acting is stronger, but the row's evidence cites the wrong real case and leaves out the right one.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | row evidence: "an unsupported modulus is scaled to MOMENT_FLOOR_MU_B before it seeds the successor, direction kept, the entry's own value untouched" | Accurate (`sequential.py:1728-1730`). The successor's starting magnetic moment (its modulus, the moment's size) is 1e-3 μ_B, not the noise value the previous pattern fitted. The X7 fix sets `floored` empty when the kept rung is `"cold"` (`:1693`). | holds |
| 2. Kind of ambiguity | `ambiguity=1` | Agrees. It is the absent-phase hold carried along the series. | holds |
| 3. Case against | `rows.json`: "dissenter none found" | Weak dissent. EasyDiffraction carries "the free parameters of the last successful fit" unchanged (`practice.md:238`), and `practice.md:314-318` lists the moment floor among behaviours "with no program default behind them". That is the absence of a support test, not a refiner shown the statistic choosing otherwise. A refiner cooling into the ordered phase might rather seed from a known moment (say the 4 K value) than from about zero. The cold rung offers the initial model's moment. Stated failure case on disk: `test_a_starved_chain_reports_a_supported_moment_above_the_transition_and_is_flagged` ("neither the reseed fence nor the floor carry catches the starved case"). | weak dissent |
| 4. Case for | grounds: "a modulus the pattern did not support is no measurement to warm-start from, as the absent-phase hold's cell is not" | Strong. `test_the_ascent_out_of_the_floor_terminates_at_once` shows a fit seeded at the floor reaches a supported 2.05-4.56 μ_B within a few iterations. The row also leaves out its strongest real evidence: `test_ba2fesbse5_ramp_the_moment_grows_below_the_onset_both_ways` (LLB G4.1, 12 patterns, `direction="both"`). There the backward chain cools from 200 K, 55 K is asserted unsupported, and 50 K is asserted supported and within 3σ of the forward chain. I infer the floor reaches the 50 K start there; I did not run it. | holds |
| 5. Tier and source | tier 3, rare-feature clause | Right under the clause. But the clause asks the diagnostic's explanation to name its families and say it is untested beyond them, and `SEQUENTIAL_MOMENT_HOLD`'s help text (`help.py:3839`) names none. The threshold that clause applies to, `MOMENT_SUPPORT_SIGMA`, is WP-2004's, so this may be owed there. | weak |
| 6. Dataset families | "one synthetic magnetic ramp … and the real Cr2WO6 4 K/150 K pair, which fires SEQUENTIAL_MOMENT_HOLD in every reseed arm" | Overstated. `batch.md` C8 Stakes: Cr₂WO₆ 150 K "is the last pattern and seeds no successor", so the floor never acts there. Not cited: Ba₂FeSbSe₅ (a second real neutron family, LLB). Its reference for the 50 K start is the forward chain, which verifies only; the published 4.13(4) μ_B at 1.5 K is an outer range. C8 promised a test (a magnetic ramp with an injected divergence after an unsupported pattern), and the diff does not add it. | weak |
| 7. Record of firing | the field, and `SEQUENTIAL_MOMENT_HOLD` reads it | Present (`test_an_unsupported_pattern_reseeds_its_successor_to_the_floor` asserts both). An old document reads `[]`, which says "nothing floored" about patterns no one checked, the same WP-1076 shape as item 1. | weak |

Would change the verdict: the evidence rewritten to cite Ba₂FeSbSe₅ (with a check that the backward 50 K entry really carries a `floored` path) in place of Cr₂WO₆, plus C8's injected-divergence test.

## 3. `fit:verify_steps` (default, tier `caller`, value 0)

**Verdict: holds.** The caller turns it on and picks the count k (how many of the largest steps to refit cold). The package chooses nothing inside it that moves a fitted value.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller now decides | row: "which steps it refits is the caller's k over a list sorted by size with no threshold" | True. `series.steps[:verify_steps]` (`sequential.py:1355-1357`). A bool is refused by name (`_check_verify_steps`). | holds |
| 2. Kind of ambiguity | `ambiguity=1` | For a caller row the kind matters little. Fine. | holds |
| 3. Case against | none given | The package still decides which pairs the k rows cover. Rows are ranked by size in esds of the later fit across all paths, and tied paths count separately: in the path guide, `verify_steps=3` spends all three on one pair (cubic a, b, c). The handover declined to change this ("a 'distinct pairs' count is a choice for C4's next touch", WP file :334-336). Neither choice moves a fitted value. | holds, with note |
| 4. Case for | `batch.md` C4 question 2: options (i) or (ii), "both the caller's; not (iii)" | Option (ii) as ruled. No package default for k. | holds |
| 5. Tier and source | `caller`; "no default path passes one, the GUI included (searched 2026-10-26)" | Confirmed: no `verify_steps` in `gui/src`, and `src/rietx` passes it only through `fit`. Condition 1 holds (off at 0). Condition 2 holds: nothing it computes is fed back. | holds |
| 6. Dataset families | n/a | n/a for a caller row. | n/a |
| 7. Record of firing | `SeriesStep.cold_ratio` | Present. But a requested step that could not be re-measured also reads `None`, the same as one not requested (handover: "needs a field", declined). The summary line covers both cases in prose. | weak |

Would change the verdict: a default path (GUI, preset or plan) starting to pass a nonzero k.

## 4. `rietx.sequential.NOISE_FLOOR_REL` (constant, tier 1, evidence changed)

**Verdict: holds.** It is a numerical floor, and its new use (setting `size_esd` to 0 for a step that is pure floating-point noise) is arithmetic.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "SeriesStep.size_esd, which it sets to 0 under the floor (WP-2003)" | `_series_steps`: `abs(step) <= floor → size = 0.0`, with floor = 1e-9 × max(1, the path's largest \|value\|) (`_noise_floor`). It decides ranking only: a collapsed esd can no longer put noise first. | holds |
| 2. Kind of ambiguity | n/a (constant) | n/a | n/a |
| 3. Case against | none given | none found. No refined parameter I know of takes real steps of 1e-9 absolute. | none found |
| 4. Case for | "before it an unrefinable profile.y read as a 29 000x step and 1e16 sigma of path dependence" | Measured failure without it. | holds |
| 5. Tier and source | tier 1, numerical floor | Test: `test_an_inert_parameter_steps_by_zero_esds` (asserts `[0.0] * 5`). | holds |
| 6. Dataset families | CPD corundum's relative esd, "five decades" above the floor | One family for the margin, enough for a numerical floor. | holds |
| 7. Record of firing | `size_esd == 0.0` | Present. A 0 here is a measured constant trajectory, not an unchecked default. | holds |

Would change the verdict: a parameter family whose genuine steps sit within ~1e-9 of its magnitude.

## 5. `SEQUENTIAL_DISCONTINUITY` deleted, with its suggestion, `DISCONTINUITY_FACTOR`, `DISCONTINUITY_SIGMA` and `MIN_POINTS_FOR_DISCONTINUITY`

**Verdict: holds.** The removal is what the record prescribes in so many words, and no established program tests steps. The statistic left behind is narrower than the one withdrawn.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller now decides | WP Context: "a record field with no threshold, `SeriesResult.steps`" | The caller now decides whether any step is a jump, and whether to verify one (item 3). The GUI's series panel now shades only verified steps (`gui/series.py:983`), and plotting `steps` there is owed (WP task 7). GUI users lose the mark on unverified large steps. | holds, with cost |
| 2. Kind of ambiguity | `generality.md` § The rule: "the series discontinuity test … is DESIGN.md's example of Rule 1's third kind" | Agrees: the data cannot settle what a jump means (transition, sample shift, beam dump, wrong model). | holds |
| 3. Case against (the cost of removing it) | `batch.md` C4: "Agents stop on stated criteria (v1.3: 7 of 8), and `steps` states none" | Real. The old scan, at its 5× median and 3σ threshold, flagged planted T050 (a background step) and T087 (a blank frame), and missed T124 and T186 (`batch.md` C4 Stakes). The record says a contested demotion is measured on agents before it lands. I found no registered agent run on this branch (no `eval_*` mention in the WP). Rule 1's line does not move with that result, but none was given. The withdrawn statistic had two parts, the step over the path's median step and the step over the combined esd. Only an esd ratio survives, and over the later fit's esd alone (item 9). "Every withheld verdict leaves its statistic" holds only partly. | weak |
| 4. Case for (removing it) | the thresholds had "no measurement" (`batch.md` C4) | Strong. `practice.md:296`: "None of the seven … tests the step between neighbours", and GSAS-II colours Δχ² in a table only when `ShowCell` is on. The thresholds' false alarms grew with steps × paths (1, 1, 4, 3 on 248-pattern null seeds 1-4, `test_planted_series.py` `_LOOK_ELSEWHERE`). The replacement ranking also lands on an event index by chance once (seed 1, 87→88), so neither reading is clean. | holds |
| 5. Tier and source | removed; the help entry carries the reading | Per § Demotion: field, help entry `SeriesResult.steps`, one summary line naming it ("largest step … (series.steps)"). All present. `UNAUDITED_BASELINE` and `RESPONSE_BASELINE` only shrink. | holds |
| 6. Dataset families | n/a (the thresholds were unmeasured) | n/a | n/a |
| 7. Record | `SeriesResult.steps` | Present. Old documents drop `discontinuities` at read and get `steps=None`. | holds |

Would change the verdict: a registered agent run showing the new help text does not lose the planted background step and blank frame.

## 6. `fit:verify_discontinuities` (default) deleted

**Verdict: holds.** It is a rename to `verify_steps`; the off default is unchanged, and a leftover `True` is refused by name.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller now decides | old row: re-read "when WP-2003's demotion … lands" | The pairs it refitted came from the removed thresholds. Now the caller's k picks them (item 3). | holds |
| 2. Kind of ambiguity | caller | unchanged | holds |
| 3. Case against | none given | none found | none found |
| 4. Case for (keeping a bool) | none given | none found: `True` would have meant "the pairs a removed threshold flagged". | none found |
| 5. Tier | `caller` → `caller` | Same class. The breaking change is staged in `docs/releases/1.11.0.md`. | holds |
| 6. Dataset families | n/a | n/a | n/a |
| 7. Record | `cold_ratio` | Item 3. | holds |

Would change the verdict: none expected.

## 7. `LinearInequality.violated`: on-face scale floored at 1 in the row's units

(A row's "face" is where the inequality holds with equality.)

**Verdict: holds.** It is a numerical tolerance matching the two guards it names, with a measured failure without it and no measured change elsewhere. The table row for `_ON_FACE` still describes only the relative reading.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `lm.py` docstring: "The floor of 1 is for a block whose *every* row is on its face, where the largest \|slack\| is itself a rounding" | It decides which start rows the builders drop. The Gaussian and Lorentzian width builders drop violated rows; the Stephens strain and texture builders drop the whole block (`least_squares.py:1843, 1882, 1983, 2080`). The tolerance becomes 1e-9 absolute wherever every \|slack\| < 1: 1e-9 deg for Γ_L, 1e-9 deg² for Γ_G². Both are physically negligible; Γ_G² is clamped at about 1e-8 anyway. | holds |
| 2. Kind of ambiguity | n/a (numerical) | Kind 1 / tier 1 numerical. | holds |
| 3. Case against | none given | none found. Stephens rows (σ²(M) in 10⁻¹² Å⁻⁴, largest about 1e6) and texture rows (P ≈ 1) almost never meet the floor. | none found |
| 4. Case for | "the 40 patterns warm-started from there each converged at Rwp 0.433 against 0.042 (WP-2003, X16)" | Measured: planted `off_nobound` T088-T127 recover, and "every other arm of all nine families bit-identical" (WP handover, Linux x86-64). | holds |
| 5. Tier and source | "matching check_resolution_positive and check_stephens_positive" | Confirmed at `staged.py:1430, 1796, 1805` (`max(…, 1.0)`). Tests: `test_a_block_whose_every_row_is_on_its_face_is_not_violated` and `test_a_start_left_on_every_rows_face_keeps_its_rows`, both checking that a real −0.0137 still reads as violated. The `_ON_FACE` row (`_audit.py:2382`) still says only "association orders", and the `1.0` is an inline literal the table cannot see. | holds; row text stale |
| 6. Dataset families | nine families re-measured | Bit-identical on all but the bitten arm. Verification only, which is enough for a tier-1 numerical setting. | holds |
| 7. Record | none | none: a solver tolerance, consistent with the guards. | n/a |

Would change the verdict: a builder whose rows' natural units put real violations within 1e-9.

## 8. `_chain`: moment-angle profile interval skipped on rungs and verify refits, attached once, exceptions swallowed

(The profile interval is the uncertainty range given to a moment angle the fit left out of its covariance; it costs 20-32 refits per angle.)

**Verdict: weak.** The gate is sound and saves the 20-32 refits per angle on discarded attempts. The blanket `except Exception: pass` leaves no record that the interval failed, and a plain fit raises in the same case.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `sequential.py:1792-1795`: "A rung is a bet the ladder may discard … The chain attaches it once, to the attempt it keeps" | It decides which fits pay for the interval. It also decides that an unexpected raise inside `attach_stationary_intervals` costs the pattern nothing (handover: "an unexpected raise in the interval no longer ends the series"). | holds |
| 2. Kind of ambiguity | none given | The gate does not change the answer (the interval moves no fitted value). The swallow is an automatic fallback. | n/a |
| 3. Case against | none given | A plain `Refinement.fit` lets the same exception propagate (`refine.py:5247`), so a series and a single fit now behave differently on one failure. `attach_stationary_intervals` already catches `ValueError` per angle and then rebuilds the `MOMENT_ANGLE_STATIONARY` finding (`parameter_interval.py:405-419`). A non-`ValueError` raise skips that rebuild. Any angle already given an interval keeps it, while the finding stays the pre-interval one. Nothing says the computation raised. The comment "the finding says none was computed, as attach_stationary_intervals does per angle" holds only for the `ValueError` path. | weak |
| 4. Case for | WP task 3: "2.6-16.7 s on fits of 0.2-1.2 s" per discarded attempt | Strong for the gate. `test_a_chain_pays_the_interval_once_a_pattern_on_the_attempt_it_keeps` asserts no rung pays and each kept attempt does (stubbed). | holds |
| 5. Tier | none given | The gate is an answer-invariant efficiency item. Its test asserts which fits pay, not that the interval values equal a plain fit's, though both call the same function on the same `Refinement`. | holds |
| 6. Dataset families | two-site Pnma fixtures (synthetic) | One synthetic family; for an invariance item that is the test's job. | holds |
| 7. Record of firing | none for the swallow | An interval left `None` because of a raise reads the same as one never attempted or cut by a cancel. | weak |

Would change the verdict: the swallowed exception recorded (a finding naming the pattern and the error), or narrowed to the exceptions a plain fit also tolerates.

## 9. `_series_steps`: consecutive-index steps only, rejected entries dropped, size over the later fit's esd

**Verdict: weak.** Not bridging gaps is well argued. Dropping steps beside an above-fence pattern contradicts the ruling the change rests on and hides a planted transition. The later-esd denominator is given no reason.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `_series_steps` docstring: "A step into or out of a pattern the fence rejected is not a row … A row is between consecutive entries, so no gap is bridged either" | It decides which steps exist in the record, and the yardstick that ranks them (also the ranking `verify_steps` reads). | holds |
| 2. Kind of ambiguity | none given | Listing a statistic for every step is kind 3. Withholding some steps is a package decision keyed on `above_fence`, which rests on `RESEED_FACTOR` (1.25, still unaudited). | weak |
| 3. Case against | none given | (a) `rows.json`, `_chain.rwp_outlier_carve_out`: "the scan drop goes with the scan (C4)" and "the scan half leaves with SEQUENTIAL_DISCONTINUITY". The code keeps the drop. Its cost is on disk: `test_planted_series.py` `_MASKED`, where the planted transition "falls inside the second phase's run of patterns above the Rwp fence … SeriesResult.steps has no row into or out of a pattern above the fence, so the cubic cell's jump is not a step there". (b) No reason is given for the later fit's esd over the combined √(σ₁²+σ₂²) the removed scan used, the usual error of a difference. Later-only overstates a step by up to √2, and ranks the same jump differently depending on which side is better measured. (c) Ranking across paths in esd units lets precise parameters dominate. The guide says "Every step of this synthetic ramp is hundreds of esds … read the order of the list rather than a size", so ordinary thermal-expansion steps of the cell can outrank a jump in Biso or a scale, and `verify_steps=k` reads that global order. | weak |
| 4. Case for | docstring: dropping diverged steps because "a step against it cannot be read apart from that code"; no bridge because "on tutorial 05's 5 % jump the cell's largest step read 600 K → 800 K across a held 700 K pattern" | Strong for diverged entries (garbage values) and for no bridging (measured misreadings on tutorial 05 and the planted blank frame). The blank-frame case (#481: confirmed at 1.00 because both cold fits reproduce the noise) argues for the above-fence drop, and the `_MASKED` case argues against it. | holds in part |
| 5. Tier and source | none given | Not tiered. The above-fence drop inherits `RESEED_FACTOR`'s tier (unaudited); the esd choice has no source. | weak |
| 6. Dataset families | planted series (synthetic), tutorial 05 (synthetic), #481 ramp | All synthetic. No real-family reference for the ranking. | weak |
| 7. Record | `SeriesStep.size_esd`, `SeriesResult.steps` | Present. A dropped step leaves no row, and nothing on the result says which steps were withheld or why, beyond `SEQUENTIAL_RWP_OUTLIER`'s message line. | weak |

Would change the verdict: the above-fence drop removed as `rows.json` ruled (or re-ruled with the `_MASKED` case named), and a stated reason, or a switch to the combined esd, for the denominator.
