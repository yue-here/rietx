# WP-1523 — A phase fitted to noise passes the support test

Milestone: unscheduled · Status: ✅ 2026-10-13 — a phase is held when its scale cannot be told from zero, conditional on the other phases' scales; PR #928
Track: What fires, and what stays silent
Depends on: — (1420 soft: the same hold, in a chain)

## Goal

A phase the pattern does not contain is held, and named by
`PHASE_UNCONSTRAINED`, whatever the fit started from. A phase fitted to noise
no longer counts as one the data can see.

## Context

Found by WP-1469 on issue #481's blank frame: every phase scale 0, so the
pattern is background and Poisson noise alone. The frame is pattern 7 of the
issue's script, and the reproduction under References rebuilds it from the
same RNG stream.

**One ordinary fit, no chain.** The blank was fitted cold with
`mccusker_default` from two starts, 2026-09-29 at `a651a7d` (Linux x86_64,
Python 3.12, `[dev]`):

| start | cell held in stages | cell reported | scale | `PHASE_UNCONSTRAINED` |
|---|---|---|---|---|
| pattern 0's fitted models (scale 5e-4) | `cell` only, released at `profile_w` | 4.14990 ± 0.0016 Å, 0.0085 Å off the ramp | 3.1e-8 ± 2.4e-8 | no |
| the issue's unfitted models (scale 7.5e-4) | `cell`, `profile_w`, `profile` | absent (held) | 1.7e-8 ± 2.5e-8 | yes |

**Why.** `CompiledModel.phase_support` is each phase's strongest modelled
point in σ of the observation noise, and `PHASE_SUPPORT_SIGMA` is 1.0
(`model/forward.py`). At the first row's answer the blank phase's support is
**2.14σ**, while its scale is 1.3σ from zero: a scale fitted to noise lifts
the strongest point above one σ, so the phase reads as seen.
`_released_phases` (`refine.py`) releases a held column when any phase it
moves rises above that threshold at the stage's landing values, and the
diagnostic reads the same vector. Which side of 1σ a noise fit lands on
depends on the start, which is the flicker.

Relevant rules, restated:

- **Root CLAUDE.md, "A phase the data cannot see is a flat direction"
  (WP-1301).** A phase is held for the stage rather than bounded, and its
  support is re-measured at the answer. A phase that appeared is released;
  one that collapsed while solving is restored and held. `phase_support` is
  the one authority for both the bound and the diagnostic, so a change to
  what "seen" means changes both together.
- **The threshold's docstring calls 1σ "not a tuned fraction"**: it says the
  comparison is against the counting statistics the phase competes with. The
  finding here is that a single-point statistic is exceeded by a fit to pure
  noise. Before changing the number, ask what the right statistic is: the
  scale's own significance, a multi-point measure, or the strongest point
  judged against what noise alone produces.

**A second failure mode of the same statistic is already on record**, in
WP-1339's Inherited (issue #219): a phase collinear with another, absent from
the specimen, read 0.65σ, 197σ or 54-56σ support depending only on its seed,
and at 57σ took the misfit with no `PHASE_UNCONSTRAINED`. That is the ridge
case; this one is the noise case. Both say `phase_support` depends on where
the fit landed, and a replacement statistic should be checked against both.

**Why a new WP rather than a fold.** 1420 owns the hold inside a chain and
fences out "`PHASE_SUPPORT_SIGMA`, or the package deciding whether a phase is
present" in its Non-goals, which is this WP's whole subject. 1339 owns the
localisation statistic and carries the #219 finding only as context.

### Decided 2026-10-04: the scale's marginal significance, at 3σ

**A phase is seen when its scale is 3σ from zero by its marginal esd**, the
esd taken over every column that can move with it: the stage's free columns
and the phase's own held structural columns. Three is
`indexing.workflow.ABSENT_SIGMA`, the multiple of its propagated σ a line's
net intensity must reach to count as present. `PHASE_SUPPORT_SIGMA` cited that
constant as "the same footing" while testing one point's height at 1σ.

**Why no statistic of the modelled curve can do it.** Under the null the
phase's cell, widths and displacements are unidentified, so the fit chooses
them to match the noise (Davies 1977, a nuisance parameter present only under
the alternative). Any function of the fitted curve is then inflated by that
choice. The scale's marginal esd counts the same freedom to first order.

Issue #481's frame at `origin/main` 69a1afc7, re-drawn over seeds (`[dev]`,
macOS arm64). Twenty blank fits (seeds 100-109, each from the two starts of
the table above) and sixteen weak real phases. Each count is the fits whose
phase read as seen, with the fit run under the rule named:

| Planted scale | max(y/σ) ≥ 1, today | ‖y/σ‖₂ ≥ 3 | Marginal z at the answer, either run | Cell error when refined |
|---|---|---|---|---|
| 0 (blank), 20 fits | 9 released, cell off up to 0.02 Å | 6 released, one cell off 0.24 Å | 0.00-2.75 | — |
| 3e-8, 8 fits | 6 | 6 | 0.0-3.4 | ≤ 1.1e-3 Å |
| 6e-8, 8 fits | 6 | 6 | 0.0-3.3 | up to 4.2e-3 Å |
| 1.2e-7, 8 fits | 8 | 8 | 4.2-5.0 | ≤ 1.2e-3 Å |
| 2.5e-7, 8 fits | 8 | 8 | 9.4-11.9 | ≤ 3e-4 Å |

The integrated norm ‖y/σ‖₂ is the scale's *conditional* z (everything else
held), and on the blank it reached 3.1-4.4 once a released cell had chased the
noise. Row 1 of the table above reads 2.06 marginal even after the chase. A
phase at 3e-8 to 6e-8 reads as unseen under the new rule. Its cell was off by
up to 1000 ppm when refined, so holding it is the honest answer.

**Where each reader gets it.** A Jacobian exists at a stage's answer and at the
end, and nowhere else.

- `phase_support` stays the cheap screen and becomes ‖y_p/σ‖₂, the
  conditional z. It bounds the marginal z from above, so a phase under 3σ
  there is unseen with no Jacobian. The stage-start hold and the cell window
  read it.
- At the answer the collapse and the release read the marginal z, and the
  release counts the held columns too, so a held cell cannot make the phase
  look better determined than it would be free.
- `PHASE_UNCONSTRAINED` and the width census read the final marginal z.
- `reflection_support` and `extra_peak_support` become the window norm
  against the same 3σ. That is `ABSENT_SIGMA`'s own test on a line.

*Revised the same day, from the landing's fixtures.* The rule above fixed
the blank frame and broke 12 fast tests in two ways. **The esd is taken
against counting noise**, from (JᵀWJ)⁻¹ with neither √χ²_red nor the
Bérar-Lelann factor. With both, a misfit anywhere made a present phase read as
absent: LaB₆ under two dead channels read 2865σ on the screen and 0.23σ by the
reported esd, and CaF₂ seeded 1.2 % off its cell read 6.74σ against 0.65σ.
**Displacement and occupancy columns are left out of the marginal**, because a
column that only rescales intensities says how the intensity splits between it
and the scale, not whether the phase is there. Kept in, the fluorite of
`tests/test_scale_b_ridge.py` read 153.7σ on the screen and 0.02σ marginal.
Three column sets were measured, each with the unscaled covariance:

| Set | Blank seen, of 20 | 3e-8 | 6e-8 | 1.2e-7 | 2.5e-7 | Misfit and ridge fixtures |
|---|---|---|---|---|---|---|
| scale and cell only | 4 | 6/8 | 6/8 | 8/8 | 8/8 | pass |
| every column but displacement and occupancy (**landed**) | 1 | 1/8 | 5/8 | 8/8 | 8/8 | pass |
| every column | 1 | 1/8 | 5/8 | 8/8 | 8/8 | ridge fails |

The one blank the landed set calls seen is seed 103 from the unfitted start,
its cell 13.4e-4 Å off.

**Not generalised, deliberately.** A joint fit (`multi.py`) keeps the screen
alone, because WP-1341 owns its report. Le Bail and Pawley fix the scale, so
the screen is all they read. The ridge case of WP-1339's Inherited (#219) is
for 1339. *Superseded in part 2026-10-12:* the reporter has since measured the
marginal z on the ridge, and the choice this WP makes there is § Decided
2026-10-12.

### Decided 2026-10-12: the hold stands on a collinear pair

Issue #219's ridge, measured by its reporter at 08176f6f: one cubic Cu phase,
modelled as the parent plus an absent `I 4/m m m` subgroup, the two scales at
ρ −0.99. Whichever phase the start leaves weaker reads under 3σ marginal and
is held, and from seeds split by δ = 5e-4 to 4e-3 that is the parent, at
0.20σ and 0.53σ. WP-1339's Inherited holds the full table.

The hold stays as it is there. At ρ −0.99 the data cannot say which of the two
phases carries the pattern, and a marginal z under 3σ says so of either one.
Standing the hold down would let a phase with no significance of its own
refine its cell, which is the case this WP exists to stop. `HIGH_CORRELATION`
fires on the two scales in every arm and names the ambiguity.

A statistic that could tell "absent" from "exchangeable with another phase" is
the scale's z marginal over every column except the other phases' scales. On a
noise phase the inflation comes from its own cell and widths, so that reading
would stay low. On the ridge it would come from the partner's scale. It is not
built here, because the reporter's script is not in the thread and the
statistic cannot be measured without it. It goes to WP-1339, which owns the
ridge. Task 6 changes how a stage reaches the hold and leaves its rule alone.
It was not measured on the ridge.

*Superseded in part 2026-10-13, from the issue triage's re-run:* the
reporter's script is now in the thread (posted 2026-10-12 00:11Z), so the
reason above for not measuring is gone. The script is fully synthetic: cubic
Cu Poisson-sampled from the package's forward model, arms ANISO-TRUTH,
ISO-TRUTH and TWO-PHASE-TRUTH, each fitted as parent+iso, parent+Stephens,
and parent plus an `I 4/m m m` subgroup from a degenerate seed and from seeds
split by δ = 5e-4 to 4e-3. Run unmodified at c3d0367 (17 s of fits), the
ISO-TRUTH and pre-split rows reproduce the reporter's e6d5f9ea numbers to the
digit. On one cubic phase the degenerate seed holds the phantom subgroup
(0.81σ), and every split seed holds the **parent** (0.0 against 1095.97,
ρ −1.000). One row moved. TWO-PHASE-TRUTH from the degenerate seed, a real
40 % subgroup, now holds the **real parent** (`cell.a`, `lor_strain`) at
sup0 8.2 against the subgroup's 741.6σ. The subgroup then carries a
tetragonality of −1.04(3)e-3 against a true +3.0e-3, at Rwp 0.0403. The
reporter had sup0 203.2, the subgroup at 18.0 and ρ −1.000 there, at Rwp
0.0405. So the hold lands on whichever phase the seed left weaker, real or
not, and that includes a real phase whose companion then carries a
distortion of the wrong sign. The choice above was made without this
measurement, so it is reopened as task 7, and § Decided 2026-10-13
supersedes it.

### Decided 2026-10-13: the hold stands down on a collinear pair

**A phase's scale significance is conditional on every other phase's
scale.** `refine._significance_columns` leaves out a column that moves only
other phases' scales, as it already left out one that moves only
displacements or occupancies. A phase is held when its scale cannot be told
from zero. Being exchangeable with another phase is not a reason to hold it,
and `HIGH_CORRELATION` on the two scales reports that case, as it already did
in every arm.

**Why this column set.** On the ridge, the marginal z's inflation comes from
the partner's scale. Conditional on it, the parent reads 45-90σ where it read
0.12-3.0σ marginal. On a noise phase the inflation comes from its own cell
and widths, which stay in the marginal, so the noise case is unchanged. The
blank frame is a single phase, so there it is identical by construction.

**Measured** on the branch tree after task 6 (`.venv` `[dev]`, Linux x86_64,
Python 3.12). The tool was #219's script run at the reporter's protocol:
0.005° grid, two passes of scale/cell/strain. It covered three arms, 5
Poisson seeds (1000-1004) and four subgroup seeds (δ = 0, 5e-4, 1e-3, 2e-3),
60 fits under each rule.

| Arm, seed | Fits | Real phase held, before → after | Phantom held | Tetragonality ×1e-3 (truth) |
|---|---|---|---|---|
| ISO-TRUTH, split | 15 | 9 → 0 | 15 → 0 | after: −0.01 to +0.30 (0) |
| ISO-TRUTH, degenerate | 5 | 0 → 0 | 5 → 5, one released at its answer | 0 |
| TWO-PHASE-TRUTH, degenerate | 5 | 4 → 0 | — | −0.93 to −1.02 both (+3.0) |
| TWO-PHASE-TRUTH, split | 15 | 1 → 0 | — | 3.4-4.5 both, one 1.21 → 1.04 |
| ANISO-TRUTH, any | 20 | — | identical | identical |

**The wrong-sign tetragonality is the start's, not the hold's.** TWO-PHASE-TRUTH
from the degenerate seed lands at −1.0e-3 against +3.0e-3 with no hold at
all, in all 5 seeds. That is the reporter's 2026-09-04 caution: the identity
point lands a real split in the wrong sign. Nothing in the hold can fix it.
The remedy is ± seeds and a comparison, which belongs to WP-1339's ask (3).

**What else moves.** A reading probe ran over 44 fast-tier files touching the
hold, QPA and multi-phase fits: 2332 tests and 1465 readings, 363 of them
with two or more scales free. It logged each `_scale_significance` call under
both column sets. No decision flipped in either direction. The conditional
reading was at most 1.09× the marginal one there, against about 30× on the
ridge.

## Non-goals

- The chain-level consequences. 1469 already leaves a pattern above the Rwp
  fence out of the step scan, and 1420 owns a held phase re-entering a chain.
- Retuning `PHASE_SUPPORT_SIGMA` by eye. Whatever replaces the test is
  measured on the suite's absent-phase fixtures (`tests/test_absent_phase.py`,
  `tests/test_held_phase.py`) as well as on this frame.

## Tasks

- [x] Reproduce both rows in a test from a synthetic blank frame, and record
      the support and the scale significance at each stage's landing values
      (`tests/test_phase_significance.py`, each test's docstring).
- [x] Decide the statistic, recorded here with the measurement that chose it
      (§ Decided 2026-10-04). What moves on the fixtures is counted with the
      landing, in the handover entry.
- [x] Land it in `phase_support` (or beside it, as the one authority both
      consumers read), so the hold and `PHASE_UNCONSTRAINED` agree:
      `phase_support` is the screen, `refine._answer_significance` the test.
- [x] Tests: the blank frame holds its cell and fires `PHASE_UNCONSTRAINED`
      from both starts; a weak but real phase is still released.
- [x] Skill: the `PHASE_UNCONSTRAINED` row, if its meaning moves; otherwise
      "none", said here. It moved: `references/abstention.md`'s row states
      the 3σ significance, and `judging.md`'s QPA-scan note names the constant
      in place of "1σ".
- [x] The stage-start hold reads the previous answer's significance, not the
      screen alone. Today a phase whose screen passes 3σ while its marginal z
      does not is freed at every stage start. It chases the noise, collapses,
      is restored and solves again, so it pays one extra solve per stage and
      can trip `CELL_RUNAWAY` on the way (review of 2026-10-04, item 4). Seed
      107 of the sweep shows it on the last stage of `mccusker_default`. A
      longer plan shows it per stage. Measure the solves saved, and count what
      moves on the absent-, held-phase and scale-B fixtures. Landed as
      `_hold_unsupported_phases`' `prior`, which `_run_plan` hands in. Seed
      107 now solves 5 times for 5 stages and 11 for `mccusker_structural`'s
      11, against 6 and 18. The prior changed no stage start of the 184 on
      the three fixture files, so nothing there moved. The sweep and the one
      weak fit it moved are in the 2026-10-13 handover entry.
- [x] Decide whether the support hold stands down on a collinear pair,
      measured on #219's script (§ Decided 2026-10-12 and its 2026-10-13
      note). The candidate statistic is the scale's z marginal over every
      column except the other phases' scales. Measure it on the script's
      arms and on this WP's blank-frame sweep before choosing, and record
      the choice with its numbers. It stands down: § Decided 2026-10-13.
      Landed in `_significance_columns`, guarded by
      `test_a_collinear_partner_does_not_hold_the_only_real_phase` (seeds
      2002 and 2003 fail under the old rule) and
      `test_only_the_partner_scales_leave_the_marginal`.

## Acceptance

Issue #481's blank frame, fitted alone from either start, reports no cell for
LaB6 and carries `PHASE_UNCONSTRAINED`; the suite's absent- and held-phase
tests pass unchanged or with each moved assertion justified here.

```sh
.venv/bin/python -m pytest tests/test_absent_phase.py tests/test_held_phase.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #481 (the ramp and its script); WP-1469's handover (where this was
  found); WP-1301 (the hold), WP-1458 (`phase_support` per emission line).
- The reproduction, run from the repo root:

  ```python
  # the issue's script to its first fit, then pattern 7 alone
  ref = rx.Refinement(first.fitted_structure, first.fitted_instrument)
  r = ref.fit(patterns[7], plan="mccusker_default")
  [(st.name, st.held, st.released) for st in r.stages]
  ```

## Handover log

### 2026-10-13 (2nd session) — closed: the hold stands down on a collinear pair

Two phases that can draw the same pattern are no longer treated as absent. Before, when a model held a phase plus a subgroup of it, the test asked whether each scale was 3σ from zero with the other's scale free to compensate. Both then failed, so the hold took whichever the start left weaker. On issue #219's cubic Cu that was the only real phase in 9 of 15 split starts. Now each scale is judged with the other phases' scales held. A phase fitted to noise still reads low, and a phase another can stand in for reads high. The ambiguity is left to `HIGH_CORRELATION`, which fires on the two scales. The wrong-sign tetragonality the triage found is not the hold's: it comes back with no hold at all, from the degenerate start. Nothing else in the suite moved. With task 7 every task is done, and the WP closes.

**Done.** `refine._significance_columns` takes the phase index and leaves out a column whose every path is a displacement, an occupancy or another phase's scale (`8a1a898` widened "every path one kind" to "every path any of them"). `_SCALE_PATH` is imported from `optimize.least_squares`. Two new tests in `tests/test_phase_significance.py`. `test_a_collinear_partner_does_not_hold_the_only_real_phase` is #219's ridge, compacted to a 0.02° grid and one pass. Under the old rule seeds 2002 and 2003 fail (2 of 2000-2011); all twelve pass under the new one. `test_only_the_partner_scales_leave_the_marginal` covers the column rule, `vars` columns included. The decision and its 60-fit table are § Decided 2026-10-13, which supersedes § Decided 2026-10-12. The skill's `PHASE_UNCONSTRAINED` row and `using/model.md` say the other scales are held; the skill copies were re-synced.

**Measured** (`.venv` `[dev]`, Linux x86_64, Python 3.12, 4 cores, no other session running). #219's script reproduces on this branch's tree before the change, with rows moved from the triage's c3d0367 run by task 6's prior. One example: ISO-TRUTH from a split seed now held both phases. The sweep is in § Decided 2026-10-13. A reading probe logged every `_scale_significance` call under both column sets. Over 44 fast-tier files (2332 tests, 1465 readings, 363 with partner scales) and over the whole slow selection (1944 readings, 762 with partner scales), no hold decision flipped in either direction. In the fast files the conditional reading was at most 1.09× the marginal one. Blank-frame sweep: a single phase, so the two rules are identical by construction there.

Counts on main `908c481` merged into this branch (`ff7a0f3`). Fast selection, verbatim with a junit file: 9337 passed, 192 skipped, 1 xfailed, none failed, total 9530, in 18:35. This session added 3 cases. No pre-session baseline was taken on this platform, and the last quoted total (9524) was macOS on an older main, so the delta is not checked. Added-test cost from that run: the collinear test 5.83 s (2 cases), the column test 0.00 s. The collinear test is the only guard on the ridge, so it stays in the fast tier. Slow selection: 300 passed, 19 skipped, 1 failed, in 35:00. The failure is `test_acceptance_lab6_cbn.py::test_the_correlation_diagnostic_separates_the_two` ("the degenerate fit raised no HIGH_CORRELATION at all"). It fails identically with the new rule disabled, at this branch's pre-merge `8a1a898`, and on `origin/main` `908c481` itself, so it is not this PR's. The nightly on main has failed its last three runs. Sent to 1930's Inherited.

**Review pass.** `/code-review high --fix` found 5 and fixed 4: a column driving both a B and another phase's scale stayed in the marginal; a third copy of the scale regex; and the `phase_support` docstring and `_OCCUPANCY_PATH` comment not naming the partner scale. Declined, finding 5: an absent subgroup with a substantial fitted scale is no longer held, and only `HIGH_CORRELATION` reports it. That is this decision. On #219 the phantom's tetragonality from a split seed comes back −0.01 to +0.30e-3 against a true 0, so the refined cell says nothing false.

**Gotchas.** `HIGH_CORRELATION` is now the only report on a collinear pair, and it lists the worst |ρ| first under `HIGH_CORRELATION_MAX`. A pair whose scales sit just under its threshold gets neither diagnostic. The ISO-TRUTH degenerate seed still holds the phantom, because its scale sits near zero. In one of five seeds the phantom was released at the answer, having picked up scale at the identity point.

**Forward references.** 1339 (ask 3: ± seeds off the identity point is the only remedy for the wrong-sign start, and the hold no longer picks a side). 1420 (its goal names the identity-point subgroup as the case the hold cannot judge; under this rule a phantom with real scale there is not held at all). 1930 (the `lab6_cbn` failure on Linux). New WP-1958 for the `trf` scale walk the previous entry left unfiled: no open WP owns it. 1534 and 1463 are closed, and 1420 is about re-entry in a chain.

**Lanes.** None dispatched; one item kept, `land-ridge` (est 15).

Next: nothing in this WP. For the maintainer: PR #928 is ready for review. The `lab6_cbn` slow failure is red on main on Linux and is 1930's to place.

- **2026-10-13** — A plan no longer frees a phase it has just called unseen. Each stage now reads the previous stage's answer as well as the quick screen. So a phase whose scale was fitted to noise stays held from the stage start. Before, it was freed, chased the noise, collapsed and solved a second time, once per stage. On issue #481's blank frame under the 11-stage structural plan that cost 18 solves and 233 iterations; it now costs 11 and 59. The answers move only at the threshold: of 64 fits of weak real phases, one went from refined to held, at 2.46σ. The WP stays open for one decision the issue triage reopened the same day: whether the hold stands down when two phases' scales are collinear.

  **Done.** `_hold_unsupported_phases` takes `prior`, the previous stage's `_answer_significance`, and holds a phase that either reading puts under 3σ. `_run_plan` hands it in. `run_stage`, joint fits and the first stage of each pattern in a series start without one. New tests in `tests/test_phase_significance.py`: seed 107 under `mccusker_default` solves once per stage, the same blank under `mccusker_structural` holds the cell from `profile` on, and a phase the prior holds is released when the answer sees it. `using/refining.md` says a stage reads the previous answer. A root `CLAUDE.md` clause was added and reverted, because the file sits at its pinned 978 lines; the rule is in the docstring and the test guards it.

  **Inherited, pruned.** The #219 ridge entry became § Decided 2026-10-12: the hold stands on a collinear pair, and the statistic that could stand it down went to 1339. The WP-1534 entry (Fe with no reflection walks its scale) no longer reproduces under the default LM driver, and task 6 cannot reach it, since the hold never holds a scale; see Findings. The WP-1903 entry asked to be deleted.

  **Measured** (`.venv` `[dev]`, macOS arm64, shared with other sessions at load averages 35 to 170, so no wall clock is quoted). Issue #481's frame, blank seeds 100-109 and weak phases at four planted scales on seeds 100-103, each from the fitted and the unfitted start. Solves are calls to `run_least_squares`.

  | Planted | Plan | Fits | Solves before → after (stages) | Iterations | Cell reported |
  |---|---|---|---|---|---|
  | 0 | default | 20 | 103 → 101 (100) | 2545 → 2490 | 0 → 0 |
  | 0 | structural | 20 | 248 → 221 (220) | 2921 → 1993 | 0 → 0 |
  | 3e-8 | default | 8 | 46 → 45 (40) | 1208 → 1179 | 2 → 2 |
  | 3e-8 | structural | 8 | 134 → 95 (88) | 2814 → 704 | 0 → 0 |
  | 6e-8 | default | 8 | 40 → 40 (40) | 727 → 727 | 8 → 8 |
  | 6e-8 | structural | 8 | 104 → 96 (88) | 1140 → 828 | 0 → 0 |
  | 1.2e-7 | default | 8 | 40 → 40 (40) | 349 → 349 | 8 → 8 |
  | 1.2e-7 | structural | 8 | 103 → 96 (88) | 1129 → 808 | 1 → 0 |
  | 2.5e-7 | default | 8 | 40 → 40 (40) | 282 → 282 | 8 → 8 |
  | 2.5e-7 | structural | 8 | 88 → 88 (88) | 492 → 492 | 8 → 8 |

  In all, 946 solves became 862 over 832 stages, so the second solves went from 114 to 30, and iterations from 13 607 to 9852. `CELL_RUNAWAY` fired in none of the 104 fits on either side, so the review's "can trip `CELL_RUNAWAY`" did not reproduce at `e1d19359`. The one moved fit is planted 1.2e-7, seed 100, fitted start, `mccusker_structural`. Before, `extinction` collapsed the phase, `roughness` freed it again, and its answer read at least 3σ, so the cell came back 4.15764 ± 0.00081 Å, 1.0e-3 Å off. Now `roughness` holds it from the start, its answer reads 2.46σ with the held columns freed, and the cell stays held. That plan already held the phase in the other 7 of those 8 fits.

  On the absent-, held-phase and scale-B files the prior changed none of 184 stage starts. Their solves (75, 112, 21) and every assertion are unchanged. Across the fast selection, with a plugin wrapping the hold, the prior acted at 28 of 3437 stage starts, in five tests. Eight are the two seed-107 tests. Eighteen are `test_extra_components`' hump fixture, which asserts nothing that moved: 18 solves became 12 in each arm, iterations went 205 → 72 with the peak and 139 → 67 without, the hump's fwhm 5.43387 → 5.43382 (esd 0.355), Rwp +6e-8, and `PHASE_UNCONSTRAINED` fires either way, reading 0.22σ → 1.08σ with the peak and 0.82σ → 1.01σ without. Two are `test_diagnostics_geometry`'s flat corundum, 7 solves → 6.

  Fast selection, verbatim with a junit file: 9305 passed, 181 skipped, 3 xfailed, 1 failed, total 9490. The plugin run before the last added test totalled 9489, so the total moved by the 2 added tests. The failure was `test_structure_extent.py::test_three_cells_a_side_build_in_no_more_than_a_moment`, a wall-clock guard, at load average 130; it passed alone. The slow selection ran once, with the counting plugin, on the tree before the docs-only merge of `be6c3ffd`: 297 passed, 22 skipped, 1 failed. The prior acted at none of its 1939 stage starts, so no acceptance number can have moved. The failure was `test_indexing_engines.py::test_dichotomy_recovers_a_monoclinic_cell` asserting `search_complete`, the budget load sensor `tests/CLAUDE.md` names; it passed alone at load 2.4 in 72 s. After the merge, `test_docs_consistency.py`, `test_skill.py` and `test_skill_cli.py` passed (206). Main then moved 40 commits (WP-1953, 1908 and 1341 among them), so the branch was merged again at `1307cb2f` and the fast selection re-run verbatim on that tree: 9341 passed, 181 skipped, 1 xfailed, none failed, total 9523, which includes main's own additions. Seed 107's records are unchanged on it. The slow selection was not re-run on the merged tree. Wall clock was 30:21 fast and 50:44 slow, both under that load, so neither is a timing. The two added tests cost 5.37 s and 2.71 s in the fast run's junit (8.08 s for the file's additions, same load). The structural-plan test is the larger; it stays in the fast tier because it is the only guard on the per-stage claim, and its fit took 2.44 s in the sweep.

  **Review pass.** `/code-review high --fix` found 8 and fixed 3: a dead length check, a mode gate repeated at the call site, and a docstring that now names a stage seed as what can stale the prior. For its finding 4 I added the prior-held release test. Declined: `run_stage`, and so the GUI's stage-by-stage path, keeps the screen alone, because a reading carried across verbs goes stale after `set_values` or a checkout; stepping a plan by hand still pays the second solve per stage. Also declined: a record field naming which reading decided a hold. `StageResult.held` names what was held, `PHASE_UNCONSTRAINED` quotes the deciding reading, and a field would move the schema. Its findings 3 and 8 are this entry.

  **Findings, no owner.** Under `solver="trf"` a phase with no reflection in range walks its scale. On WP-1534's four-phase fixture over 25-33° Cu Kα, two scale-and-background stages take Fe's scale from 1e-4 to 164.7, and QPA reads iron at 99.99 wt%. `PHASE_UNCONSTRAINED` and `QPA_ESD_UNAVAILABLE` fire. Under the default LM driver the scale stays at its start, and QPA reads iron at 0.61 wt%, which is the start value. The hold's rule "never its scale" assumes the scale has a column. WP-1534 and WP-1463 are closed, so this needs a WP.

  **Merge-gate review (PR #928, `/code-review medium`, eight findings).** Fixed: the collapse branch had lost its only test in this file, so a forced 0σ answer on a phase both readings pass now takes it, and the test checks the cell is put back to the stage start before the second solve (`test_held_phase.py`'s `collapsed_fit` takes it too, with no prior); a stage seed now drops the prior of every phase it reached, since a seeded scale would otherwise stay held on a reading from before the seed; the docstring names the three things that move a phase off the reading (a seed, a collapse, a cell clamp); `PHASE_UNCONSTRAINED` says its reading is the last stage's answer, which kept the hold; the screen is computed once and the prior applied to it; the manual says `run_stage`, `cherry_pick` and the GUI's stage path read the screen alone; and the seed-107 tests now assert the mechanism, conditional on where each answer landed, in place of `not released` on readings 0.39σ to 2.4σ under the threshold. Declined, finding 2: no `NodeAction` field for the prior. `cherry_pick` replays an action onto another branch or sample, where a reading of the source state is the wrong input, and the field would move the schema. Reproduced on seed 107: cherry-picking `profile` onto `profile_w` solves twice in 43 iterations, against once in 15 in the fit, and ends with the cell held all the same. That gap is folded into 1420's Inherited, the same hold crossing a verb boundary. After merging main at `12a7b307` (`.venv` `[dev]`, macOS arm64, shared at load average 43 to 67): the three hold files 95 passed, and the fast selection 9342 passed, 181 skipped, 1 xfailed, none failed, total 9524, one more than the last merged run for the added collapse test.

  **Reopened.** Merging main brought the issue triage's 2026-10-13 re-run of #219's script into this file's Inherited. It shows the hold landing on a real phase while its companion carries a wrong-sign tetragonality, and it asked the working session to add a task. It is folded into § Decided 2026-10-12's dated note and task 7, and the Status and Priority lines are back. The WP-1534 and WP-1903 entries that merge carried back stay pruned, for the reasons under *Inherited, pruned*.

  **Gotchas.** The prior is per fit. A held phase is judged at its held values, so a borderline phase gets no second look with its columns refining; that is the one fit the sweep moved. A stage seed moves values between the prior and the stage start, and since the minimum is taken it errs only towards holding. Skill: the `PHASE_UNCONSTRAINED` row is unchanged, because what fires it and what it means did not move; "it releases itself in the stage where the phase appears" still holds. Forward references went to 1339 (the ridge statistic) and 1420 (the prior is per fit, and a re-entry count can move).

  Next: task 7. Run #219's script, then measure the candidate statistic (the scale's z marginal over every column except the other phases' scales) on its arms and on this WP's blank sweep before choosing. Elsewhere: 1420 holds the chain re-entry and the cherry-pick gap, and the `trf` scale walk needs filing.
- **2026-10-04** — A phase that is not in the pattern is now held and named by `PHASE_UNCONSTRAINED`, from either start. The old test asked whether one point of the phase's curve rose above 1σ of the noise. A scale fitted to pure noise lifts that point past 1σ, because the fit also moves the phase's cell to wherever the noise peaks. The new test asks whether the phase's scale is 3σ from zero, with an esd that counts that freedom. Indexing already asks a line for that 3σ. On 20 blank frames it calls 1 seen, where the old test called 9. The cost is that a phase at about 1/16 000 of a strong one's scale is now mostly held (1 of 8 fits saw it, against 6 of 8 before). Its cell came back up to 1000 ppm off when refined, so that loses no measurement.

  **Done.** The decision and the seed sweep that chose it are in § Decided 2026-10-04, revised the same day. `phase_support` is the screen ‖y_p/σ‖₂. `refine._answer_significance` is the test: scale over its esd from (JᵀWJ)⁻¹ against counting noise, marginal over every column but displacements and occupancies, with a held phase's columns freed for the measurement and z capped at the screen. `PHASE_SUPPORT_SIGMA` is 3.0, held equal to `ABSENT_SIGMA` by test. Reflection and declared-peak support are window norms. A phase still held at the end quotes the reading its hold was decided on, and the message says so. New `tests/test_phase_significance.py` covers the blank from both starts, seed 107's collapse path, a weak real phase from both starts, a release, the threshold and the norms. The skill's `PHASE_UNCONSTRAINED` row, the QPA-scan note, the manual's `model.md` and `series.md`, and the root rule are restated.

  **Measured** (`.venv` `[dev]`, macOS arm64, machine idle at launch). Fast selection: 8164 passed, 159 skipped (total 8323), 3:16. Full selection: 8427 passed, 168 skipped (total 8595), 19:55. The new file adds 9 cases. No pre-session baseline was taken, so the passed+skipped delta is not checked. The only moved assertion is `test_reflection_support_is_phase_support_one_rank_down`: best == phase (76.47) became 0 < best (50.90) ≤ phase, because a norm sums every line. The 7 added functions cost 5.48 s in one fast run: the blank frame 3.00 s (2 cases), the weak phase 1.41 s (2), the seed-107 blank 0.72 s, the release 0.33 s, the rest under 0.03 s. None joins the slow tail.

  **Lanes.** One lane, `land` (est 60, 182 requests), dispatched at 229K main context. Re-read 74K of 127K, 27 main requests and 72K left in main to check it, 12 main edits after it, $14.80 lane against $22.66 modelled in-session, saved +$5.17. One item was kept, `skill` (est 6, 8 requests, at 302K). Session: 97 main requests, peak 319K, $8.24. Trial row appended to `process.md`. The lane was resumed once by `SendMessage` with the revised design after its first report. The tool counts that as no redo, and its 182 requests span both rounds. The replay with these numbers prints the selective policy at +26% under "saving by policy" (+28% with mo doubled, +35% with one lane in five redone). The same run prints −31%, −32% and −22% by peak-context band. I did not resolve the two signs, and WP-1903 should read them.

  **Review pass.** `/code-review high --fix` found 9 and fixed 6:
  - anisotropic ADP columns stayed in the marginal, because my trim of the `u11`…`u23` alternatives was wrong (an `adp.k` column moves tied U^ij entries);
  - the esd squared a tiny column, where `covariance_estimates` now takes it;
  - z was not capped at the screen;
  - the "when its hold was decided" wording also reached joint, Le Bail and Pawley fits;
  - a comment in `_build_result` was wrong;
  - stale manual and skill text.

  Its dispersion finding I fixed myself: the test now declares the default it was measured with, so nothing moved. Declined: the backend re-trace when a held column is freed, which costs only jax and torch time. Its item 4 became task 6.

  **Gotchas.** `replay()` and any caller without a fit's stage vector read the screen, so a replay of a fit that collapsed a phase can drop its `PHASE_UNCONSTRAINED`. A phase held at the end can read far above 3σ after the second solve (up to 1888σ at 6 fast-suite stage answers) while staying held, because the rule allows one second solve and never a third. The finding quotes the decision-time reading for that reason. No Part 2 manual equation was added: the theory manual never carried the support test. Forward references went to 1339 (the #219 ridge, unmeasured under the marginal), 1341 (joint fits still read the screen alone), 1420 (weak phases re-enter later) and 1534 (displacements are left out because of its ridge).

  Next: task 6 first, because it decides whether a noise phase costs one extra solve per stage. Feed the previous answer's significance into the next stage's start hold, measure the solves saved on seed 107 under a plan longer than `mccusker_default`, and re-run the absent-, held-phase and scale-B files. Then close the WP.
- **2026-09-29** — created, from WP-1469's session. Both rows of the table
  measured at `a651a7d`; the support at the answer (2.14σ) was read by
  compiling the fitted models and calling `phase_support` on them. Next:
  task 1, then the decision in task 2, which is the whole WP.
