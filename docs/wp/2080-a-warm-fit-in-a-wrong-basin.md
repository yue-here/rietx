# WP-2080 — A warm fit that stopped in a wrong basin is kept, and nothing escalates it

Milestone: unscheduled · Status: ✅ 2026-11-08 — option B landed: the GoF step climbs a warm first rung to warm_staged (PR #1473)
Track: What fires, and what stays silent
Depends on: 2003 (C1's ruling removes the Rwp fence this case slips under; PR #1310 lands `_rejected`, the predicate a trigger would join)

## Goal

A series does not keep a warm first rung that stopped in a wrong basin while a
rung the ladder already owns would have found the right one. Either the chain
escalates such a rung by itself, on evidence other than an Rwp comparison, or it
records a number a reader can act on and the manual says how. Which of the two is
the maintainer's ruling (task 2).

## Context

**The report** (issue #1214, contributor mustachefeeling, 2026-10-29). Under the
LM default (WP-1938) the collapsed first rung of a warm pattern can settle in a
minimum well above the noise floor, while `solver="trf"` from the same start, or
the ladder's own second rung, finds the noise floor. The reseed fence compares the
pattern's Rwp with 1.25 × the median Rwp of the accepted patterns, and Rwp's noise
floor (Rexp) differs from pattern to pattern, so the bad fit sits under it.

**Reproduced on `0d735f5e5`** (macOS arm64, worktree venv `[dev]`, Python 3.12,
compiled tier on): the issue's `repro.py` prints its table to the digit. Entry 0
reaches GoF 1.017 (Rwp 0.0843, Rexp 0.0829). Entry 1's collapsed warm rung under
LM stops at GoF 2.047 (Rwp 0.1012, Rexp 0.0494), under the fence at 0.1054, and is
kept with `['warm']` tried. TRF, and `refit="stages"` under LM, reach GoF 1.049.

**The mechanism**, read off the kept fit (`series.entries[1]`, `sr.results_[1]`):
- The hexagonal phase's `cell.c` is 4.862, against 5.202 true and 5.2019 in the
  TRF fit. Its scale is 6.3e-5 (TRF: 1.95e-3), its `lor_strain` sits on its floor,
  and `sample_displacement` is −0.0183 (TRF: −0.0014).
- The warm stage converged in 44 iterations, the closing stage in 30. Both stages'
  `held` and `collapsed` are empty: the absent-phase test (WP-1301) called the
  hexagonal phase seen at the answer, so nothing restored its cell.
- The non-info codes are `CONSTRAINT_ACTIVE`, `FLOOR_HIT` and `STAGE_WINDOWS_STALE`
  on seed 2. Seed 18 carries only `STAGE_WINDOWS_STALE`, which fires on every fit
  in this family, good or bad. So no code separates the bad fits.

**Why the fence is beside the point.** WP-2003's C1 (ruled 2026-10-26, landing in
PR #1310) removes `RESEED_FACTOR` and escalates a warm rung only when it diverged
or carries an `error` code. That ruling leaves this case kept exactly as today: the
fit converged and carries no error code. C1's own brief names the observation that
would reverse its pick: "a family where a diverged-or-raised ladder keeps a warm fit
a validating reference rejects and a fact other than Rwp separates it from the fits
it accepts" (`2003-batch/batch.md` § C1). This family is one. The validating
reference is the synthetic truth, and the separating fact is the kept fit's GoF over
the GoF of the pattern it started from: 2.01 here, at most 1.126 on every fit kept
in the nine families WP-2003 measured, bar the three the retrospective below names
(1.279, 1.861 and 26.0).

**The measurement** (`2080-batch/`, both scripts committed).
- `measure_trigger.py` runs the issue's chain over pattern-1 noise seeds 2-21 under
  four triggers, each patched into `_reseed_needed` with the ladder and `_prefer`
  left as on main (macOS arm64, `[dev]`, compiled tier on):

  | trigger | seeds escalated | kept GoF > 1.5 | worst kept hex c error | pattern-1 iterations, 20 chains |
  |---|---|---|---|---|
  | main (Rwp fence) | 0 | 2 (seeds 2, 18) | −0.340 Å | 666 |
  | status only (PR #1310's C1) | 0 | 2 | −0.340 Å | 666 |
  | GoF > 1.25 × the seed pattern's GoF | 2 | 0 | 1.7e-4 Å | 883 |
  | GoF > 1.25 × the median accepted GoF | 2 | 0 | 1.7e-4 Å | 883 |

  Both GoF arms take seeds 2 and 18 to `warm_staged` (GoF 1.049 and 1.026, hex c
  within 1e-4 Å of the truth). The 18 seeds that do not fire keep their first rung,
  at a GoF ratio of 0.994-1.034. The extra 217 iterations are all on the two
  firing seeds. The two GoF arms cannot differ on this family: a two-pattern chain
  has one accepted pattern, so its median is the seed. The retrospective below is
  what separates them.
- `retro_ratio.py` reads WP-2003's committed reseed JSONs (the `off` arm: the fence
  off, so every kept warm fit is the first rung but planted T087, whose bounded
  first rung was forced to `warm_staged`; Linux x86-64, `[dev]`, measured
  2026-10-26) and counts where each GoF trigger at 1.25 would fire:

  | family | warm patterns | over seed GoF | over median GoF | what the firing pattern is |
  |---|---|---|---|---|
  | planted | 247 | 1 (T186) | 115 | an unmodelled phase from T124; the `on` arm escalated T186 through all three rungs to the same Rwp, 36 → 184 iterations |
  | cpd-noclose | 7 | 1 (1b, 1.279) | 1 | a degraded warm fit; WP-2003's option (iii) arm took it to `warm_staged` at Rwp 0.13928 from 0.16333, the independent fit's 0.13932 |
  | tut05-broken | 6 | 1 (scan12, 26.0) | 1 | the broken pattern; PR #1310's `_rejected` already escalates and quarantines it |
  | cpd, cpd-ftolnone, cr2wo6, planted-null, trigger, tut05-jump | 7, 7, 1, 247, 9, 6 | 0 (max 1.126) | 0 | — |

  The median reference costs what C1 removed the Rwp fence for: on planted it fires
  on 115 patterns, and the Rwp fence's escalations there cost 4.1× the evaluations
  and moved no value. The seed reference fires on a *step* in GoF, and a smooth
  drift under a growing misfit takes no step.
- The margin is narrow at the bottom. The largest GoF ratio kept without need is
  1.126 (cpd); the smallest that a rescue followed is 1.279 (cpd-noclose 1b, a
  variant with the closing stage off). 1.25 sits inside that gap, 2 % under the
  weaker rescue.

**Practice.** No program restarts a pattern by itself (`docs/practice.md`
§ Sequential refinement, last paragraph), so any trigger beyond divergence is
rietx's own and tier 3 (generality record § The rule). GSAS-II's sequential results
table shows each pattern's fit statistics for the user to read (recall, not checked
this session).

## Non-goals

- Why LM lands in this basin and TRF does not. Both are local solvers, and the
  issue says so; the protection is the ladder, never a solver switch.
- The Rwp fence itself: WP-2003 C1 owns it.
- The absent-phase test calling a 6.3e-5 scale seen: a single-fit question for a
  WP on WP-1301's seam, filed only if task 2's ruling leaves it the last guard.

## Tasks

- [x] Reproduce on main and name the mechanism; measure the triggers on the issue's
      family and, retrospectively, on WP-2003's nine (Context).
- [x] The maintainer's ruling (Handover log, 2026-11-02): option A, B or C, and the
      factor if B. Option B at 1.25, settled by Claude under Yue's delegation,
      2026-11-02 (handover entry of that date). The tier-3 audit row task 3 lands is
      approved under the same delegation.
- [x] After PR #1310 merges: land the ruled option on `schemas.sequential._rejected`'s
      seam. Under B: the trigger joins the ladder's escalation test only (never the
      quarantine), escalates to `warm_staged` and not to `cold`, names the fact in a
      record field on `SeriesEntry` (the GoF ratio and whether it fired), an `_audit`
      row at tier 3 with its approval, a `help.py` entry, the manual's series guide
      and a skill row. Under A: the record field, its help entry and the guide's
      paragraph, no trigger. *Landed 2026-11-08:* `sequential.GOF_STEP_FACTOR`
      and `_gof_over_seed`, joined beside `_reseed_needed` in `_chain` for the
      climb to `warm_staged` only; `SeriesEntry.warm_gof_over_seed` and
      `.escalated_on_gof`; three `_audit` rows (the constant and the flag at
      tier 3, approved 2026-11-02; the ratio at tier 1); two `help.py` entries;
      the series guide's § Restart ladder; a skill row; a release note.
- [x] Tests: the issue's seed-2 chain as a fixture (two patterns, about 3 s), asserting
      the kept rung and the hex `cell.c` within its esd of the truth; a planted-null
      chain asserting no escalation. *Landed 2026-11-08:* in
      `tests/test_sequential.py`, three dictated-GoF rows (the climb stops at
      `warm_staged`; recorded but inert at 1.25 exactly, under `reseed=False`
      and under `refit="stages"`; a diverged first rung is not a GoF
      escalation) and issue #1214's draw-2 chain; in
      `tests/test_planted_series.py`, the 24-pattern null takes no step. With
      the factor set to 1e9 the climb row and the #1214 row fail (the positive
      arm).
- [x] Re-measure on the tree with the ruling in: the issue's 20 seeds and the
      nine families' `off` arm via `2003-batch/measure_reseed.py`, the table judged
      per pattern (WP-1124). *Measured 2026-11-08* on `3f9215121`, macOS arm64,
      `[dev]`, compiled tier on, `OPENBLAS_NUM_THREADS=1` (pearl did not answer,
      so the Mac, two processes):
      - **Issue #1214, seeds 2-21** (`2080-batch/measure_tree.py`, output
        `seeds20.jsonl`): the step fires on seeds 2 and 18 (ratio 2.012, 2.009),
        both kept `warm_staged` at GoF 1.049 and 1.026 with hex `c` −6.3e-5 and
        −1.0e-4 Å from the truth (esd 1.1e-4); the 18 others keep `warm` at
        0.994-1.034; 883 evaluations over the 20 chains. Identical to the
        patched `gof_seed` arm in Context.
      - **The nine families**, `off` against `status_nobound` (the package
        default), both run here (`2080-batch/compare_arms.py`; the records stay
        out of the tree, since they carry local interpreter paths). The ratio is
        over 1.25 on 3 of 537 warm fits, the three the retrospective named:

        | family · pattern | GoF/seed | rungs (default) | evaluations off → default | kept GoF off → default | read |
        |---|---|---|---|---|---|
        | cpd-noclose · 1b | 1.279 | warm, warm_staged | 430 → 501 | 1.786 → 1.524 | rescued: Rwp 0.16333 → 0.13928, the independent fit's 0.13932; worst Δ/esd against it 10 (scale) → 4.4 |
        | planted · T186 | 1.861 | warm, warm_staged | 36 → 108 | 5.486 → 5.486 | nothing to rescue (the cubic-to-tetragonal transition; Context's retrospective calls it the unmodelled phase, which starts at T124); values move 3e-6 esd |
        | tut05-broken · scan12 | 26.0 | warm, warm_staged, cold | 5 → 19 | 26.33 → 26.33 | `_rejected` climbs it anyway; values identical |

        cpd, cpd-ftolnone, planted-null, trigger, cr2wo6 and tut05-jump: no
        ladder or value differs, evaluations equal. **One knock-on, judged per
        pattern:** on cpd-noclose the rescued 1b seeds 1c, whose collapsed warm
        rung from there reached GoF 158 and climbed on rejection (not on the
        step) to `warm_staged` at GoF 1.589 (reference 1.586; 52 → 381
        evaluations). 1d-1h then keep `warm` at a GoF 0.025-0.042 lower than
        `off`, nearer the reference's on every pattern (e.g. 1d 1.307, off
        1.341, reference 1.320), and their worst `instrument.profile.v` distance
        to the reference falls from 2.4-5.2 to 0.7-2.1 esd; but one
        `lor_strain` per pattern now sits 4.8-7.9 esd off the reference: 0.053
        to 0.091 where the reference has 0 (1c, 1e, 1f, on the floor) or about
        0.018 (1d, 1g, 1h), and `off` 0 to 0.018. With the GoF below the
        reference's on 1d-1h, the chain sits in a lower minimum than the
        independent fits did, a strain-against-width trade the data rank by
        χ² alone; read it as a second basin, not as an error B introduced.
        This is the declared no-closing-stage variant; plain `cpd` does not
        fire. Family total 728 → 1144 evaluations.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py -q
.venv/bin/python -m pytest tests/test_audit_table.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #1214; WP-2003 (`2003-batch/batch.md` § C1 and C2, `clashes.md`), PR #1310;
  WP-1051 (the ladder), WP-1127 (the first rung), WP-1469, WP-1938 (the LM default).
- Root CLAUDE.md § Series; DESIGN.md § Rules, 1 and 4.

## Handover log

### 2026-11-08 — option B landed; the WP closes (PR #1473)

A series no longer keeps a warm fit that converged clean in a wrong minimum when the staged
plan from the same start would find the right one. When the quick warm refit ends at more than
1.25 times the GoF of the pattern it started from, the series tries the staged plan from the
same start and keeps the better fit. It never restarts from the initial models and never
quarantines on this. On the reporter's chain both bad noise draws now land within an esd of the
true cell. On WP-2003's nine series the step fires 3 times in 537 warm fits. One of those rescues
a pattern, and its successors then sit in a lower-χ² minimum with a different strain. What it
cost: one extra staged fit where it fires, and a 1.25 resting on development data only, which
issue #1474 carries.

*Done.*
- `sequential.GOF_STEP_FACTOR` (1.25) and `_gof_over_seed`. They join `_chain`'s escalation test
  for the climb to `warm_staged` only. `_reseed_needed` and `_rejected` are unchanged, so the
  cold rung and the quarantine are untouched. Under `reseed=False` and `refit="stages"` the step
  cannot act.
- `SeriesEntry.warm_gof_over_seed` (the first warm rung's ratio) and `.escalated_on_gof` (the
  step alone climbed, and `warm_staged` was attempted). Schema note under 0.61, additive.
- `_audit` rows: the constant and the flag at tier 3, approved 2026-11-02 under the delegation;
  the ratio at tier 1. `fit:reseed`'s row is re-measured.
- `help.py` entries for both fields. The series guide's restart-ladder text moves to a new page,
  `reference/series-ladder.md`: `reference/series.md` sat at 49 998 of its 50 000-character
  cap. Stubs under the old headings keep `#restart-ladder` and `#quarantine` landing (tutorial
  05 links them on the stable docs). Also `docs/practice.md`'s rietx row, a 1.12.0 release
  note, the regenerated API index, and the Vale accept list (`GoF`, with the two `GOF` spellings
  in `theory/estimation.md` aligned).
- GUI Series panel: the `restaged` and `hard` chips say when the GoF step climbed (`hard`
  becomes a plain `GoF step` chip there). There is no new `title=`, since `help.test.ts`
  ratchets them. Dist rebuilt; vitest 607 passed, svelte-check 0 errors.
- No skill row. The row and body sentence put `references/series.md` 540 B over its budget
  (CI lint, flagged by the shift lead), and they restated `help.py`. A test ties the 1.25 quoted
  in help and in the guide to the constant.
- Tests: four dictated-GoF rows in `tests/test_sequential.py` (the climb stops at
  `warm_staged`; inert at exactly 1.25, under `reseed=False` and under `refit="stages"`; not
  credited when a diverged rung or a caller's `reseed_factor` climbs anyway), the factor-prose
  row, issue #1214's draw-2 chain, and the planted null taking no step. Positive arm: with the
  factor at 1e9 the climb row and the #1214 row fail.

*Measured.* Task 5's tables above (macOS arm64, `[dev]`, compiled tier on; pearl did not
answer two wake attempts, so the Mac with two processes). Suites on `6adf0b1f8`, equal to
`origin/main` 63d7c120a merged (main had not moved), macOS arm64, `[dev]`, Python 3.12, `-n 4
--dist loadgroup`: full suite 15 293 passed, 424 skipped, 51 xfailed, 2 failed in 41 min. One failure was this branch's own factor-prose row, which read the guide sentence from the page the split had emptied. It is fixed in `e49a26c77` and passes alone. The other, `test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment` (a magnetic two-site solve, moment 0.6995 against 3.5), fails identically on `origin/main` 63d7c120a in a detached tree. It predates this branch and no series code reaches it. Added tests' cost (`tests.added_test_times`, that run's junit
on this Mac): 2.80 s over the 7 added tests, the #1214 chain 1.19 s the largest; per file `test_sequential.py` 2.80 s (6), `test_planted_series.py` 0.00 s (1, on the module's shared null fixture). Touched selections: `tests/test_sequential.py` 156 passed before the
new rows; `test_audit_table`, `test_help`, `test_gui_help`, `test_gui_dist` 69 passed;
`test_manual`, `test_manual_api`, `test_vale`, `test_docs_consistency` 128 passed;
`tests.skill_caps` exit 0; `python -m tests.reader_output` exit 0 (unchanged).

*Review.* `/code-review high --fix` ran from the session's start directory, the main checkout on
a stale local branch, and reviewed that branch rather than this one. It left uncommitted fixes in
a new worktree, `worktrees/review-vt-patches-fixes` (branch `review/vt-patches-fixes`), which this
session did not touch. This diff was reviewed by an Opus agent instead. It confirmed the
escalation logic in every case (forced, raised rungs, cold after `warm_staged`, quarantined
seeds, `on_error`, the backward chain, JSON round trip) and found:
the flag set before `warm_staged` ran, so a cancel there left a flag no other field showed
(fixed); the GUI chips' wording (fixed); three docstrings (fixed); help text missing the fence
and the bound (fixed); a GoF of 0 not refused (fixed); the #1214 row hard-coding 1.25 (fixed).
Declined: a test for the first-rung bound's `forced` case. `forced` implies the climb whatever
the step says, and the review checked it in code.

*Generality* (the judge's sections, unedited; author's lines marked "Answer"):

**rietx.sequential.GOF_STEP_FACTOR (constant, tier 3, 1.25)**

**weak.** The case for the action is the stronger side. The threshold's case is not yet earned: only one dataset family has a fire checked against a true value, and that family is development data.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | Row `evidence`: "a collapsed warm first rung whose GoF exceeds 1.25x the GoF of the pattern its warm start came from climbs to warm_staged only, never cold or the quarantine, and the better attempt is kept (_prefer)". (GoF is goodness of fit, Rwp/Rexp. The collapsed warm rung is one combined stage started from the previous pattern's values. `warm_staged` is the full staged plan from the same start. `_prefer` is the function that picks which attempt is kept.) | Matches the code (diff of `sequential.py`, `_chain`). `step` is tested only at `rung == "warm_staged"` and only under `reseed=True`. The ratio is the first warm attempt's GoF over the kept GoF of the last accepted pattern. The step spends one extra staged fit per firing pattern, and it can change which minimum is kept. | clear |
| 2. Kind of ambiguity | The GoF-step action is filed as kind 1 on the `escalated_on_gof` row (`ambiguity=1`). This constant row has no ambiguity field. | Kind 1 fits the action, because the extra fit can only lower that pattern's χ². The number 1.25 is a tier-3 threshold placed on top of a kind-1 act. | agrees |
| 3. Case against acting | Handover 2026-11-02, "What would reopen it": "A second family with kept fits near 1.2 reopens the factor." Row: planted T186 is "an unmodelled phase; nothing to rescue". | Two situations a competent refiner would face differently. **(a) A count-time step.** GoF² is χ²/(N−P) with w = 1/σ², so at a fixed relative misfit GoF grows as √counts once systematic error dominates. A scan with ≥1.56× the counts of its seed can therefore cross 1.25 with no wrong basin. An example is a ramp-and-dwell protocol, where short ramp scans alternate with long dwell scans. No family measured has such a step; this is arithmetic, not measured. The cost is compute, since the better fit is kept. **(b) A real transition.** T186 in `tests/planted_series.py` is the cubic → tetragonal transition, with the unmodelled rock-salt phase present since T124 (`2003-batch/batch.md` family table). The row and the WP name only the unmodelled phase. At a transition a refiner changes the model, not the start. Measured cost: 36 → 108 evaluations, values moved 3e-6 esd. **(c) A downstream knock-on missing from the row.** On cpd-noclose (the CPD round-robin tray with the closing stage off) the rescued 1b seeds 1c-1h. There one `lor_strain` per pattern moves 4.8-7.9 esd away from the independent-fit reference, while `profile.v` moves nearer (WP task 5). The handover reads this as a second, lower-χ² basin. The rule's clause that the action leaves the number no further from its reference is not met on `lor_strain`. That reference is rietx's own independent fit, so it only verifies. | substantive, cost-only for (a) and (b); (c) belongs in the row |
| 4. Case for acting | Grounds: "the escalation can only lower the pattern's chi2, since the better attempt is kept". Measured in WP Context: issue #1214's draws 2 and 18 were kept with hexagonal c 0.34 Å off at GoF 2.05. Escalated, they reach GoF 1.049 and 1.026 with c within 1e-4 Å of the synthetic truth (esd 1.1e-4). Cost +217 iterations over 20 chains, all of them on the two that fired. | Confirmed by the committed test `test_issue_1214s_warm_fit_in_a_wrong_basin_climbs_and_lands_on_the_truth`, which asserts c within its esd of the truth. With the factor at 1e9 it fails (positive arm, per WP task 4). Leaving it to the caller costs a silent wrong cell that seeds every later pattern, and no code separates it (WP Context: no non-info code tells seeds 2 and 18 from good fits). Fires on 3 of 537 warm fits. | strong |
| 5. Tier and source | "No program restarts a pattern by itself (practice.md § Sequential refinement), so tier 3." | Checked in this repository: `docs/practice.md` § Sequential refinement, "When a fit goes wrong". GSAS-II, EasyDiffraction and MAUD restart none (marked checked in source). TOPAS and BGMN are inferred. FullProf and RIETAN-FP are "not established". So tier 3 is right. That table's rietx row still lists only divergence, raise and error codes as triggers, so it is stale after this change. | holds |
| 6. Unrelated families | Row: "measured on the issue's synthetic family and the nine, untested beyond them". | **Firing where the fault is:** one family with a validating reference, #1214's synthetic two-phase chain, which is the family the trigger was designed on. Plus CPD (IUCr CPD sample 1, lab Cu Kα), but only in a declared non-default variant with the closing stage off, and only against rietx's own independent fit, which verifies. **Silent where no fault:** CPD (default; max ratio 1.126), Cr₂WO₆ (HB-2A neutron; one warm fit), and the synthetic planted-null, trigger and tut05-jump families. **Stated failure case:** planted T186 (misdescribed, see row 3). **All development data:** 1.25 was placed inside the 1.126-1.279 gap measured on these same series, and no sealed family exists. Under default settings the smallest ratio a rescue followed is 2.01. The 1.279 bound comes from the non-default variant. The three-family bar is not met on the firing side, and this is not a rare feature, so the rare-feature exception does not apply. | short of the bar |
| 7. Record that it fired | `SeriesEntry.escalated_on_gof`, `SeriesEntry.warm_gof_over_seed` | Both are written in `_chain`. No diagnostic code, which is right for an action record under "Attention is a cost", clause 1. | holds |

Evidence that would change the verdict: a second and third unrelated family, at least one of them sealed, where the step fires on a fit a validating reference rejects. Also any family whose kept fits sit near 1.2. Separately, the row should name T186 as the cubic → tetragonal transition and record the cpd-noclose `lor_strain` knock-on.

**rietx.schemas.sequential.SeriesEntry.warm_gof_over_seed (action, tier 1, ambiguity 3)**

**holds.** The ratio is arithmetic, recorded without a verdict, and it follows the `rwp_over_median` precedent (tier 1, ambiguity 3). One sentence of its help text overstates what a jump means.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | Row: "arithmetic: the first warm attempt's GoF over the GoF of the pattern its warm start came from … recorded on every warm pattern whether or not the step can act". | It decides nothing. `_gof_over_seed` returns `None` for a missing attempt, a missing seed, or a non-finite or non-positive GoF. On an escalated entry it holds the first attempt's ratio, not the kept one's, and the schema docstring says so. | clear |
| 2. Kind | `ambiguity=3` | A reported statistic. The threshold that acts on it sits on its own row. | agrees |
| 3. Case against | none given | For a kind-3 field: it reports and stops. The help entry (`help.py`, `SeriesEntry.warm_gof_over_seed`) says "a jump here is a worse fit and not fewer counts". The manual (`docs/docs/reference/series.md:550`) contrasts GoF with "Rwp, which moves with the counts". By the arithmetic in the first item's row 3, GoF also moves with counts once systematic misfit dominates, so a jump can mean more counts at the same misfit. | wording issue only |
| 4. Case for | Schema docstring: "GoF and not Rwp because it divides the misfit by the pattern's own noise: issue #1214's first rung sat under the Rwp fence at 2.01 times its seed's GoF". | Leaving the field out would hide the one number that separated the #1214 fits. Measured: 2.01 on the bad fits against 0.994-1.034 on the 18 good ones. | strong |
| 5. Tier | tier 1, "arithmetic" | Correct: a quotient with no free factor. | holds |
| 6. Families | not applicable (no threshold) | — | — |
| 7. Record | itself; also asserted under `refit="stages"` and `reseed=False` by `test_the_gof_step_is_recorded_where_it_does_not_act` | — | holds |

Evidence that would change the verdict: none expected for the tier. Help text that names the count-time case would remove the wording issue.

**rietx.schemas.sequential.SeriesEntry.escalated_on_gof (action, tier 3, ambiguity 1, approved 2026-11-02)**

**holds.** As the record of the GoF-step escalation, the case for acting is the stronger side. Its tier rides on `GOF_STEP_FACTOR`, and that row's weakness carries over.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | Row: "records that the GoF step alone sent the pattern from the collapsed warm rung to warm_staged … neither rejected, over a caller's reseed_factor nor cut by the first-rung bound". | The code sets it as `gof_escalated or (step and not needed and not forced)`, so it is False when another trigger would have climbed anyway. `test_a_rejected_rung_past_the_gof_step_is_not_called_a_gof_escalation` pins that. | clear |
| 2. Kind | `ambiguity=1` | The act is: one more fit from the same warm start, keeping the lower-cost result. Kind 1 is defensible, since a refiner shown a pattern at twice its neighbour's GoF would not keep it unexamined. | agrees |
| 3. Case against | Handover: B "departs from practice as the ladder already does". | Dissenter: a refiner who holds one protocol for every pattern so that trajectories stay comparable (FullProf's cyclic mode, "same refinement conditions for every pattern", practice.md, marked inferred). The ladder already breaks that homogeneity, and this flag makes each break visible. Also the count-step and transition cases from the first item. | weak dissent; cost-only |
| 4. Case for | Grounds: "The record of the escalation, tiered with it". | Without the flag a reader cannot tell a GoF-step climb from a rejection climb. `rungs_tried` alone does not say why. | strong |
| 5. Tier | tier 3, approved 2026-11-02 "under the maintainer's delegation" | The delegation is recorded in the WP handover of 2026-11-02 ("use your best judgement on on 2080"). It approves the factor and the row, as the dispatch says. | holds |
| 6. Families | as for `GOF_STEP_FACTOR` | as there | as there |
| 7. Record | itself | `test_a_gof_step_climbs_to_warm_staged_and_never_cold` asserts True, `not reseeded`, and `rungs_tried == ["warm", "warm_staged"]`. The null-series test asserts it never fires on planted-null. | holds |

Evidence that would change the verdict: a case where the flag reads True while `needed` or `forced` also held. None found in the code or tests.

**rietx.sequential.SequentialRefinement.fit:reseed (default; evidence changed)**

**weak.** The added clause is accurate, but the row's existing measured sentence is now false on this tree, and the grounds do not cover the new branch.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | Evidence now adds: "and to warm_staged only on the GoF step (GOF_STEP_FACTOR, WP-2080)". | Accurate. `reseed=True` (the default) now switches on one more trigger. | clear |
| 2. Kind | `ambiguity=1` (unchanged) | unchanged | agrees |
| 3. Case against | unchanged text | The evidence still says "on this tree with no bound, the default since C3, planted escalates nothing in 3 111 evaluations (2026-11-02, macOS arm64)". WP task 5 (2026-11-08) measures planted T186 escalating under the default on this tree (36 → 108 evaluations). The sentence is stale. | finding |
| 4. Case for | Grounds: "Trying a colder start on a rejected fit and keeping the better is what a refiner does by hand". | The GoF step is neither a colder start nor a rejected fit. Its grounds live on `GOF_STEP_FACTOR`'s row, and this row does not point there. | gap |
| 5. Tier | tier 3, approved 2026-11-03 | The approval predates the added trigger. The trigger's own approval (2026-11-02, delegation) sits on the constant's row. | holds, but the row should cite it |
| 6. Families | unchanged | — | — |
| 7. Record | — | `SeriesEntry.rungs_tried`, `.escalated_on_gof` | holds |

Evidence that would change the verdict: the planted sentence updated to this tree's measurement (T186 escalated, evaluations re-counted), and the grounds pointing to `GOF_STEP_FACTOR` for the non-rejected branch.

**Skill: `entry.escalated_on_gof` row and body sentence (docs/skill/rietx/references/series.md)**

**holds.** The row names a field, which is what DESIGN.md § Rules, 4 asks of a new skill row. Two wording and staleness points.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it tells an agent to do | Row: "Read a converged warm fit with no code as its pattern's answer: a collapsed warm rung can stop in a wrong basin. `True` means its GoF exceeded 1.25× …". Body: "A clean collapsed warm fit at over 1.25× its seed pattern's GoF climbs to the staged warm rung only (`entry.escalated_on_gof`)." | The table column is "What it means you must not do". The row says what not to do but not what to do for a wrong basin at a ratio ≤ 1.25, which the step leaves untouched. "Clean" in the body sentence is undefined; it means not rejected. | minor |
| 2. Kind | — | It describes package behaviour and a field, which Rule 3 allows ("makes the API and the feedback surface known accurately"). | agrees |
| 3. Case against | none given | It nearly restates `help.py`'s `SeriesEntry.escalated_on_gof` entry, and per CLAUDE.md (WP-1338) the package's own output is the cheapest place. The literal "1.25" is spelled in the skill, in two `help.py` entries and in the manual, and no test ties any of them to `GOF_STEP_FACTOR` (grep: the constant is referenced only in `_audit.py`, `sequential.py`, the schema and `test_planted_series.py`). A retune fails `test_audit_table.py` but leaves these four texts wrong. | finding |
| 4. Case for | "(Measured: #1214, a minor phase's c 0.34 Å off at ratio 2.01; `warm_staged` landed within 1e-4 Å)" | An agent reading a series summary needs to know a GoF-step climb is not a reseed (`reseeded` stays False). The row says so. | holds |
| 5. Source | `(Measured: #1214 …)` | The trap is a rietx behaviour shown on a contributor's synthetic chain and reproduced in rietx runs. That is acceptable for a row describing the package's own field. It would not be acceptable as a refining rule. | holds |
| 6. Families | — | — | — |
| 7. Field named | `entry.escalated_on_gof` | It exists and has a writer (`_chain`). | holds |

Evidence that would change the verdict: a test, or a substitution from the live constant, that keeps "1.25" in help, skill and manual in step with `GOF_STEP_FACTOR`. Also a clause on what to read when the ratio is high but under the factor.

Answer (GOF_STEP_FACTOR, weak): the row now names T186 as the transition, records the
cpd-noclose knock-on, the default-settings rescue at 2.01 and the count-time dissent. The
three-family bar is issue #1474.
Answer (fit:reseed, weak): its planted sentence is re-measured on this tree (T186, 3 183
evaluations) and its grounds point to `GOF_STEP_FACTOR`'s row.
Answer (warm_gof_over_seed wording): help, the guide and `docs/practice.md` now say GoF moves
with counts under a systematic misfit.
Answer (skill row): removed for the budget, as above; the 1.25 in help and in the guide is tied
to the constant by test.

*Gotchas.* A session started outside the worktree runs `/code-review` against whatever its start
directory holds. Here that was the main checkout's stale branch. Review by agent on a diff file
instead. `reference/series.md` has no room left (45 589 of 50 000 after this split); the next
addition there should go to a sibling page. The two `measure_reseed.py` records carry the
interpreter's local path, so they stay out of the tree; `2080-batch/compare_arms.py`
rebuilds the table from any pair.

*Next:* none in this WP. Issue #1474 holds what is left: the factor on two more unrelated
families, at least one sealed, and the count-time case measured. Forward references: none
needed. WP-2003's note from this WP asks for nothing unless the ruling revisits C1, and B does
not. WP-2081 lists this trigger as a non-goal.

### 2026-11-02 (2nd session) — the ruling: option B

Option B is the ruling. A warm pattern whose first try ends
with a GoF above 1.25 times the GoF of the pattern it started from climbs one rung, to
the staged plan from the same warm state, and the better of the two fits is kept.
Settled by Claude under Yue's delegation, 2026-11-02. Yue's words: "use your best
judgement on on 2080". The lead session picked B, and a ghostshift runner recorded it.

*Grounds.* B can only lower each pattern's χ², because the better attempt is kept. It
fires only where the reversal condition of WP-2003's C1 ruling (2026-10-26) holds: a
kept warm fit that a validating reference rejects, separated from the accepted fits by
a fact other than Rwp. Option A loses because a ratio in one row of hundreds is easy to
miss. Option C fires on 115 of 247 patterns of the planted family, the cost C1 removed
the Rwp fence for.

*What would reopen it.* The margin for the factor is thin. The largest ratio kept
without need is 1.126 and the smallest rescued is 1.279. A second family with kept fits
near 1.2 reopens the factor.

*What it does not touch.* B escalates to `warm_staged` and never to `cold`, so it sends
no extra pattern to the rung that restarts from the initial models. That rung is where a
series loses a held setup parameter's value (WP-2081 measures it), so B does not
interact with how a series holds what the setup fixes.

*Approval.* The tier-3 `_audit` row that task 3 adds is approved under the same
delegation, and task 3 records that approval in the row.

*Next:* task 3 once PR #1310 merges. Filed alongside this entry in PR #1333.

- **2026-11-02** — created, from issue #1214 (a ghostshift runner, one session).
  The report holds on today's main: a series can keep a converged fit that sits in a
  wrong minimum, twice the noise of its neighbour, and say nothing. Removing the Rwp
  limit (PR #1310) does not change that. One cheap test separates these fits from
  every fit kept in WP-2003's nine series: the fit's GoF against the GoF of the
  pattern it started from. Escalating on it rescued both bad cases measured. No code
  changed; whether to add the test is the maintainer's call.

  *Done.* Filed: no open WP owns a trigger for a converged warm fit in a wrong
  basin. WP-2003 tiers the existing fence and ladder, its C1 ruling removes the
  fence, and its Non-goals send new chain classifiers to a follow-up WP. A new
  trigger is a new tier-3 action with its own approval. WP-2003 is in flight on
  PR #1310, so this WP depends on it, and WP-2003 got one `### Inherited` line.
  Reproduced on `0d735f5e5` to the issue's digits. Measured as in Context, scripts in
  `2080-batch/`. Filed in PR #1324.

  *Gotchas.* `measure_trigger.py` patches `_reseed_needed` on main's signature; after
  PR #1310 that seam is `schemas.sequential._rejected`, so the script needs porting
  before task 5. The retrospective reads `off` arms measured on Linux x86-64 with the
  compiled tier off.

  *Next:* the ruling below, then task 3 once PR #1310 merges.

  **The question for the maintainer.** Should a warm pattern climb one rung when its
  fit is much worse, against the noise, than the fit it started from?
  - *Why it matters.* A series fits each pattern from its neighbour's answer, with
    one combined refinement first and the full staged plan only if that first try
    is rejected. Today the first try is rejected by an Rwp limit, which PR #1310
    removes; afterwards only divergence or an error-level code rejects it. On the
    reporter's chain the first try keeps the minor phase's c axis 0.34 Å off (6.5 %),
    with GoF 2.05 where the neighbour reached 1.02, and the staged plan from the same
    start finds the truth. A user sees a converged fit and no warning, and the next
    pattern starts from it. Moderate: 2 of 20 noise draws here, one variant pattern
    in WP-2003's nine families, and the reporter's private in-situ series.
  - *Aim.* A series answer as good as fitting each pattern carefully by hand, for a
    user who runs hundreds of patterns and reads only the summary.
  - *Options.* (A) Keep C1 as ruled (the approved 2026-10-26 rule for the chain:
    escalate a first try only when it diverged or carries an error-level code): no
    trigger, add the GoF ratio to each series entry and a paragraph in the series guide.
    Nothing extra runs; the reader has to spot it. (B) Escalate the first try to the
    staged plan when its GoF exceeds 1.25× the GoF of the pattern it started from,
    and keep whichever fits better. Measured: rescues both bad draws to within
    1e-4 Å. It fires on 3 of 537 warm fits across the nine test series WP-2003
    measured (the series tests for C1). One fire is a rescue. One has nothing to
    rescue; the Rwp limit's three-rung climb cost it +148 iterations, and B's single
    rung would cost less (not measured). One is a broken pattern #1310 already
    catches. On the reporter's chain B costs +33 % of the second pattern's
    iterations, all on the two draws that fired. Undoable by one line. (C) The same
    test against the median GoF of all accepted patterns, the issue's option 1:
    same rescues, but fires on 115 of 247 patterns of "planted" (WP-2003's
    248-pattern series with an unmodelled phase from pattern 124), the cost C1
    removed the Rwp fence for. Dropped: the issue's option 2 (fire on `FLOOR_HIT`), since seed 18 carries none.
  - *Practice.* No program restarts a pattern by itself (`docs/practice.md`, checked);
    GSAS-II's results table leaves the judgement to the user (recall). So B departs
    from practice as the ladder already does; A matches it.
  - *Recommendation.* B, a lean. The crux is whether one extra fit on a GoF step is
    worth spending without asking. It can only lower the pattern's own χ², because
    the better attempt is kept, and it fires where C1's own reversal condition holds.
    A loses because the reader must notice a ratio on one pattern in hundreds. What
    would flip it: a family where B fires often with nothing to rescue, as the median
    form does on planted. The factor's margin is thin (1.126 kept without need, 1.279
    rescued), so a second family near 1.2 would move the factor or the pick.
