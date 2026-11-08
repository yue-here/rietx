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
