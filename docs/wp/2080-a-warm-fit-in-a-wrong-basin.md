# WP-2080 — A warm fit that stopped in a wrong basin is kept, and nothing escalates it

Milestone: unscheduled · Status: 🔄 2026-11-02 — reproduced and measured; the trigger waits on the maintainer's ruling and on PR #1310
Track: What fires, and what stays silent
Depends on: 2003 (C1's ruling removes the Rwp fence this case slips under; PR #1310 lands `_rejected`, the predicate a trigger would join)
Priority: P2 2026-11-02 — a silent wrong answer on a path every warm series runs: 2 of 20 noise draws of the reporter's synthetic chain keep a cell 0.34 Å and 0.072 Å off its true value, with nothing at warning level naming it; the workaround (`refit="stages"`) is cheap once known

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
in the nine families WP-2003 measured.

**The measurement** (`2080-batch/`, both scripts committed).
- `measure_trigger.py` runs the issue's chain over pattern-1 noise seeds 2-21 under
  four triggers, each patched into `_reseed_needed` with the ladder and `_prefer`
  left as on main (macOS arm64, `[dev]`, compiled tier on):

  | trigger | seeds escalated | kept GoF > 1.5 | worst kept hex c error | iterations, 20 chains |
  |---|---|---|---|---|
  | main (Rwp fence) | 0 | 2 (seeds 2, 18) | −0.340 Å | 666 |
  | status only (PR #1310's C1) | 0 | 2 | −0.340 Å | 666 |
  | GoF > 1.25 × the seed pattern's GoF | 2 | 0 | 1.7e-4 Å | 883 |
  | GoF > 1.25 × the median accepted GoF | 2 | 0 | 1.7e-4 Å | 883 |

  Both GoF arms take seeds 2 and 18 to `warm_staged` (GoF 1.049 and 1.026, hex c
  within 1e-4 Å of the truth). The 18 seeds that do not fire keep their first rung,
  at a GoF ratio of 0.994-1.034. The extra 217 iterations are all on the two
  firing seeds.
- `retro_ratio.py` reads WP-2003's committed reseed JSONs (the `off` arm: the fence
  off, so every kept warm fit is the first rung; Linux x86-64, `[dev]`, measured
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

### Inherited

## Non-goals

- Why LM lands in this basin and TRF does not. Both are local solvers, and the
  issue says so; the protection is the ladder, never a solver switch.
- The Rwp fence itself: WP-2003 C1 owns it.
- The absent-phase test calling a 6.3e-5 scale seen: a single-fit question for a
  WP on WP-1301's seam, filed only if task 1's ruling leaves it the last guard.

## Tasks

- [x] Reproduce on main and name the mechanism; measure the triggers on the issue's
      family and, retrospectively, on WP-2003's nine (Context).
- [ ] The maintainer's ruling (Handover log, 2026-11-02): option A, B or C, and the
      factor if B.
- [ ] After PR #1310 merges: land the ruled option on `schemas.sequential._rejected`'s
      seam. Under B: the trigger joins the ladder's escalation test only (never the
      quarantine), escalates to `warm_staged` and not to `cold`, names the fact in a
      record field on `SeriesEntry` (the GoF ratio and whether it fired), an `_audit`
      row at tier 3 with its approval, a `help.py` entry, the manual's series guide
      and a skill row. Under A: the record field, its help entry and the guide's
      paragraph, no trigger.
- [ ] Tests: the issue's seed-2 chain as a fixture (two patterns, about 3 s), asserting
      the kept rung and the hex `cell.c` within its esd of the truth; a planted-null
      chain asserting no escalation.
- [ ] Re-measure on the tree with the ruling in: the issue's 20 seeds and the
      nine families' `off` arm via `2003-batch/measure_reseed.py`, the table judged
      per pattern (WP-1124).

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

- **2026-11-02** — created, from issue #1214 (a ghostshift runner, one session). No
  open WP owns a trigger for a converged warm fit in a wrong basin: WP-2003 tiers the
  existing fence and ladder, and its C1 ruling removes the fence. A new trigger is a
  new tier-3 action with its own approval, and WP-2003's Non-goals send new chain
  classifiers to a follow-up WP. WP-2003 is in flight on PR #1310, so this WP depends
  on it rather than editing its file. Reproduced on `0d735f5e5` to the issue's digits;
  measured as in Context. No code changed. Filed in PR #PR. *Next:* the ruling below,
  then task 3 once PR #1310 merges.

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
  - *Options.* (A) Keep C1 as ruled: no trigger, add the GoF ratio to each series
    entry and a paragraph in the series guide. Nothing extra runs; the reader has to
    spot it. (B) Escalate the first try to the staged plan when its GoF exceeds 1.25×
    the GoF of the pattern it started from, and keep whichever fits better. Measured:
    rescues both bad draws to within 1e-4 Å, fires on 3 of 537 kept warm fits across
    WP-2003's families (one rescue, one with nothing to rescue at +148 iterations, one
    broken pattern #1310 already catches), +33 % iterations over the 20 chains, all on
    the two that fired. Undoable by one line. (C) The same test against the median
    GoF of all accepted patterns, the issue's option 1: same rescues, but fires on
    115 of 247 planted patterns, the cost C1 removed the Rwp fence for. Dropped: the
    issue's option 2 (fire on `FLOOR_HIT`), since seed 18 carries none.
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
