# WP-1334 — the stage that ran out of budget

Milestone: unscheduled · Status: 🔄 2026-11-02 — tasks 1-2 landed (PR #1343); the termination split, the stop rule and its measurement next
Track: A long run is not one fit
Depends on: —
Priority: P3 2026-09-23 — cost only: 46.6 % of stage time for a 1.23 % median gain

## Goal

A stage that exhausts its iteration budget while barely improving the cost
stops rather than escalating, and says so. A caller holding a `StageResult`
can apply the keep-the-best-pass discipline the skill asks for without parsing
the event log for a number the object was standing next to when it was
computed.

### Inherited

- **2026-11-02, from [2036](2036-main-is-green-on-every-nightly-leg.md): `solve_magnetic`'s continuation guard binds on a crawl, so a class can drop out of the ranking by rounding.** On the Cr₂WO₆ 150 K pattern, class 3's last stage (`all`) runs to `max_iter` and `strategy.magnetic._fit` continues it from where it stopped. Each 400-evaluation continuation lowers χ² by 0.0002-0.008 of about 2177. At six 1e-14 nudges of the reference's `w` on macOS arm64 it needed 3, 4, 4, 5, 10 and more than 10 continuations; the sixth hit `SOLVE_MAX_CONTINUATIONS` (10) and returned `max_iter`, as the 2026-11-01 Linux nightly did. Forward-difference moment columns crawl too (6 at the unnudged start), so the analytic column from #1206 is not the cause. A trial stopped there is listed with a caveat and **not ranked**. Here that changes nothing, since every class sits 36-45 below zero in ΔBIC. On a pattern where the crawling class is the winner, the verdict would depend on rounding. The constant's docstring calls it "a runaway guard, never a timer", and at 10 it is a timer for this fit. `tests/test_magnetic_solve_acceptance.py`'s 150 K test stopped asserting the trial converges (WP-2036); the stop rule this WP designs is what would make the status mean something. Probe: `docs/wp/2036-batch/cr2wo6_150k_continuations.py` (counts and per-continuation costs).

- **2026-10-25, from [2036](2036-main-is-green-on-every-nightly-leg.md): a stage that runs out of budget from one start in many, a last-digits matter.** `examples/guides/moment.py`'s round 1 is one all-free stage. Since #1161 it starts with the moment's `crystalaxis_y` at −1.0191353854626552e-6 μB, read back from the magCIF `solve_magnetic` wrote. From that exact value it runs 800 evaluations to `max_iter` (cost 2464.4 → 1990.3), and a 4000 cap does not converge either. The same start with only that value set to −1.0e-6, 0, +1e-6, −1e-4 or −1e-3 converges in 21-45 evaluations to 1983.6 (arm64 Mac, `[dev]`, compiled tier on and off, 1-4 threads alike). The closing stage repairs it: every route ends at Rwp 0.104747. So the cost is the budget, a `STAGE_MAX_ITER` a reader may act on, and a next fit whose step depends on where this one stopped (the guide's round 2 failed CI 10 of 19 times). Not measured: which direction it crawls along, or whether frozen windows play a part (WP-2047). To reproduce: run the guide up to `ROUNDS = 5`, dump `structure` and `fitted_instrument` with `model_dump(mode="json")`, and refit them with the guide's `everything` plan; edit the one value to see the split.

- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: the second `diverged`.** `RefinementResult.status` (`schemas/results.py:1436`) declares the same member as `StageResult.status`, and no writer exists for either: the LM driver returns 0 or 1, scipy's TRF 0 to 4, and the mapping gives `diverged` only below 0 (`optimize/least_squares.py:2470,2722`). The new manual now lists `converged` and `max_iter` (`docs/docs/concepts/fit.md` § Outputs) and says the type admits a third value nothing writes (`reference/refinement.md` § Stage results). Retiring the member changes those two lines with it; `strategy/magnetic.py:393` names it too.

- **2026-10-16, from the issue triage (#538): option (1) is mostly on main,
  from WP-1937, so the task is smaller than the entry says.** `614f24a8`
  (2026-10-10) documents `StageResult.n_iterations` as residual evaluations
  (`schemas/results.py:899-903`) and `SeriesEntry.n_iterations` as "Total
  residual evaluations" (`schemas/sequential.py:125`), `_stage_lines` prints
  "N evals" (`results.py:1167`), and Part 1 says evaluations
  (`refining.md:1072`, `series.md:253,273`, `history.md:196`). No schema
  change, as decided. Still open: the epsilon / p90 rule stated in that unit,
  and the test constant `RAMP_MAIN_UNBOUNDED_ITERATIONS`
  (`tests/test_held_phase.py:695`, comment still says "iterations") renamed,
  as the 2026-09-30 reply on #538 asked. Tick the first two clauses of the
  task at line 173 once the rule is written. Checked at origin/main 138d55dc
  by reading; the reporter's reproduction (`max_iter=1` gives 4) was not
  re-run, and under the documented unit its output is correct.

- **2026-10-10, from WP-1937: `"diverged"` now has no writer.** scipy's TRF
  never returns a negative status for a valid input (−1 comes only from
  MINPACK's `method="lm"`), and WP-1937 stopped the LM driver returning one
  for a stage that starts at its minimum. So `StageResult.status`'s
  `"diverged"` member, and the series quarantine and `SEQUENTIAL_UNRECOVERED`
  keyed on it (`sequential._reseed_needed`, the quarantine branch on
  `entry.status != "diverged"`), are reached only by test fakes. Name a
  writer (a non-finite cost, say) or retire the member for new results while
  old files still read. Also from 1937: both drivers now cap
  `max_iter × NFEV_PER_ITERATION` residual evaluations, and the LM driver's
  budget stop says `max_nfev`, as TRF's does.

- **2026-09-30, from the issue triage (issue #538): `StageResult.n_iterations`
  is scipy's `nfev`, not an iteration count, and this WP's ε / p90 rule must
  be stated in the unit the field holds.** *Reproduced at `e3e6486a`* with
  the reporter's synthetic LaB6: `max_iter=1` reports `n_iterations=4` and a
  stage that converged under `max_iter=3` reports 7 (`NFEV_PER_ITERATION = 4`
  is the cap's exchange rate). Both solver paths do it, and
  `SeriesEntry.n_iterations`' docstring ("least-squares iterations") and
  `_stage_lines`' "N it" read as iterations. Every number already quoted as
  an iteration count here, in #222 and in WP-0505 is an evaluation count; no
  comparison changes, since each is like against like. The two ways out are
  the reporter's: (1) document the field as evaluations and print "N ev"
  (cheapest, no schema change), or (2) carry a real iteration count beside it
  (TRF `njev`, `LMOutcome.njev`), a schema change. **Decided 2026-09-30: option (1).** Document `n_iterations` as residual evaluations on `StageResult` and `SeriesEntry` and print "N ev" in `_stage_lines`; no schema change. Task added below.
- **2026-09-28, from [1338](1338-the-skills-own-gates.md): `StageResult.rwp` falsifies a skill sentence.**
  `references/series.md` says `StageResult` carries no `rwp` field, and
  `test_every_negative_field_claim_is_still_true` fails once it does.
  Rewrite that sentence in the same change.

- **2026-10-11, from the issue triage (#222): the reporter's two comments of
  2026-09-02 withdraw or sharpen three claims this Context still carries.**
  (1) "A phase going to zero makes fits faster" is withdrawn. On a third
  tranche, a 182-pattern variable-temperature synchrotron series, fits ran
  13.8× slower when `PHASE_UNCONSTRAINED` fired (5.4× more evaluations, 2.2×
  more cost each), and on that tranche's other system the test was flat
  (0.94×). The effect is a threshold whose sign depends on whether the
  unsupported phase leaves a flat direction, so condition on the diagnostic
  firing and never correlate against the fraction. (2) `s/iter = 4.4 µs ×
  n_points + 2.9 ms` belongs to the first tranche: 3.35× low on the six-phase
  lab series and 0.34-0.49× on the variable-T one, so it is not quotable. Cost
  tracking the evaluation count survives (stratified r = +0.859, +0.988,
  +0.983). (3) `max_nfev` alone is not the waste signal. Over three tranches
  it was 3.9 %, 4.4 % and 2.98 % of stages, 46.6 %, 42.9 % and 23.5 % of stage
  time, and 72×, 53.6× and 18.0× the median `ftol` stage, in a different stage
  name each time. In the six-phase tranche 15 `max_nfev` `warm_refit` stages
  still cut cost by a median 2.76 %, while four `max_nfev` `strain` stages
  spent 129.3 s for 0.19 %. So the stop rule is the pair "budget exhausted and
  a near-zero relative cost reduction", blind to stage names. Checked against
  the tree at 7d9be3cb: this file's Context states claims (1) and (2) and
  keys its rule to `max_nfev` plus ε; `StageResult` has no `rwp` or
  termination field.

## Context

From issue #222, measured over a 638-pattern laboratory-XRD chemical-looping
series — 1846 fits, 56.8 min wall, single-threaded (`OMP_NUM_THREADS=1`),
durations taken from rietx's own event log:

| termination | n | total time | share of stage time | median duration |
|---|---|---|---|---|
| `ftol` | 6297 | 1056.8 s | 53.1 % | **0.042 s** |
| `max_nfev` | 258 | 927.9 s | **46.6 %** | **3.036 s** |
| `ftol+xtol` | 30 | 3.9 s | 0.20 % | — |
| `xtol` | 29 | 3.1 s | 0.15 % | — |
| `gtol` | 8 | 0.4 s | 0.02 % | — |

**3.9 % of stages consume 46.6 % of stage time.** A `max_nfev` stage costs
**72×** the median `ftol` stage and returns a **median cost reduction of
1.23 %** for it. p90 is 92 %, so a minority genuinely rescue a fit — the
median one does not. They run a median of **201 residual evaluations against
34**, and concentrate in `warm_refit` (153) and `biso` (74); the worst
individual stages are `biso` at 15.98 s / 400 evaluations and `phase_strain`
at 8.51 s / 400, both `max_nfev`. (#222 wrote "iterations"; the log's
`n_iterations` is an evaluation count, #538, so every count here is one.)

The ask is a per-stage rule of the shape *"if a stage exhausts its evaluation
budget while improving cost by less than ε, stop rather than escalate"* —
**reported, not silent**. Everything it needs is already emitted.

**Three corrections to the issue, established on the tree at `c79fb5df`.**

1. `StageResult.status` is `Literal["converged", "max_iter", "diverged"]`, so
   "this stage exhausted its budget" **is already on the object** as
   `status == "max_iter"`. What is missing is the finer split the event log
   carries (`ftol` vs `xtol` vs `gtol` vs both), which is a different and
   smaller ask than the issue's wording suggests.
2. **It is already reported, too.** `refine.py::_max_iter_diagnostics` emits
   a `STAGE_MAX_ITER` warning on the result naming every stage whose status
   is `max_iter`, and its docstring records why: `StageResult.status` "has
   carried `max_iter` all along, but folded into a per-stage record nobody
   reads in a batch run", and WP-1028 §(d) measured three identical
   NaCl/Li₂CO₃ mixtures at 39 s, 858 s and 2838 s — a 73× spread — from
   exactly this. Its suggestion text is the package's standing diagnosis:
   *the parameters freed there are probably degenerate (the agent skill §3)
   rather than merely slow: free fewer.* So "reported, not silent" is already
   true at the result level; what #222 adds is the **cost** of leaving the
   budget to run out, and a rule that stops it.
3. `rwp` genuinely is absent. `stage_end` emits `rwp=stage_rwp`, computed
   right there (`refine.py`, the `_run_plan` loop), while `StageResult`'s
   fields are `name, status, n_iterations, cost_initial, cost_final, freed,
   ftol, n_constraint_truncations, held, released`. So a caller doing
   keep-the-best has to re-derive Rwp from `cost_final` or read the log. Same
   shape as #218 and #222's own sibling ask: the quantity exists and is not
   reachable from the object the caller holds.

**What the measurement method establishes.** The
campaign started from the opposite hypothesis — that fits get slow when peaks
broaden or a phase fraction collapses. Pooled over 976 timed stage rows the
correlations point at reflection count (r = +0.398); stratifying into 12
(protocol × scan-geometry) cells reverses it:

| driver | median r within strata | range | sign consistent? |
|---|---|---|---|
| peak width | −0.147 | −0.486 … +0.190 | **no** |
| min phase fraction | +0.258 | −0.439 … +0.773 | **no** |
| n reflections | +0.052 | −0.573 … +0.636 | **no** |
| **n evaluations** | **+0.859** | +0.142 … +0.961 | **yes** |

Cost tracks **evaluation count** at a per-evaluation price linear in pattern
size: `s/eval = 4.4 µs × n_points + 2.9 ms`, r(n_points, s/eval) = **+0.972**.
Broadening moves neither the number of evaluations nor the price of one. So the
lever this WP pulls (fewer evaluations) is the only one measured to work.

One result belongs in the record: the one
repeatable phase-fraction signal has the **opposite** sign to the naive
expectation — a phase going to zero makes fits *faster*, because
`PHASE_UNCONSTRAINED` fires and rietx holds that phase's 7–9 parameters
(WP-1301). The machinery designed to protect the answer also protects the
clock.

**The stop rule is a floor under the cost, not the cure — and the package
already names the cure.** `STAGE_MAX_ITER`'s own suggestion says a stalled
stage is a degenerate group and the fix is the plan (free fewer), and #222's
census agrees: the stalls concentrate in `biso` and `warm_refit`, the classic
scale/Biso/background degeneracy. In a batch the plan is not retuned per
pattern, so a rule that stops a stage going nowhere is what bounds the cost;
it must not be read as making the plan right. **The rule is a judgement, not
a threshold to invent.** Root CLAUDE.md's rule stands: a wall-clock budget in a test is a runaway guard, never a timer.
Here the budget is in the *library*, so the criterion must be stated in the
quantity the solver owns (relative cost decrease over the last k evaluations),
never in seconds, and its default must be justified against the p90 = 92 %
tail — the point of the rule is to stop the median case without abandoning the
minority that rescues a fit.

**The rule in the unit the field holds** (#538, decided 2026-09-30). Every
count in the rule is residual evaluations. `StageResult.n_iterations` is
scipy's `nfev` on both drivers, the start included, and a stage's budget is
`Stage.max_iter × NFEV_PER_ITERATION` evaluations (4 per iteration, WP-1937),
so a default 100-iteration stage stops at 400. The rule therefore reads: a
stage whose `n_iterations` reaches `max_iter × NFEV_PER_ITERATION` and whose
relative cost decrease is below ε stops rather than escalating, and says so.
#222's 1.23 % median and 92 % p90 are whole-stage decreases,
(`cost_initial` − `cost_final`) / `cost_initial`, over stages that spent that
budget, so ε is placed against that distribution. A trailing window, if the
rule uses one, is k evaluations and never k solver steps: one LM step costs
one or more evaluations, so a window counted in steps would not match the
budget it is cut from. Which of the two forms the rule takes, and ε, are the
stop-rule task's.

## Non-goals

- The reporting cost that sits outside the stage brackets — 1335. #245
  measured that summing stage durations understates fit cost by ~9× under
  `stage_reports=True`; that is a different number and a different fix.
- A new solver or driver. This is a stop rule over the existing TRF path.
- Changing `Stage.ftol` or the intermediate-ftol schedule (WP-1123's rule:
  the plan alone knows which stage is last).

## Tasks

- [x] #538: `n_iterations` documented as evaluations, `_stage_lines` prints "N ev", the ε / p90 rule stated in that unit (decided 2026-09-30). The first two landed in WP-1937 (`614f24a8`, which prints "N evals"); the rule is § Context's "The rule in the unit the field holds"; `RAMP_MAIN_UNBOUNDED_ITERATIONS` is now `RAMP_MAIN_UNBOUNDED_EVALUATIONS`.
- [x] `StageResult.rwp` — the number `stage_end` already emits, on the object
      that was standing next to it. Name its writer at review (WP-1076: a
      declared field with no writer fails no test).
- [ ] The finer termination reason on `StageResult`, or a written statement
      that `status == "max_iter"` is the whole answer and the log's split is
      deliberately log-only.
- [ ] A stop rule: a stage exhausting its budget below a stated relative-cost
      improvement stops, and `STAGE_MAX_ITER` (or a sibling) says the rule cut
      it rather than the budget running out. Default chosen against the
      measured p90, not invented.
- [ ] Re-measure the #222 tranche shape on a suite fixture and record the
      recovered fraction, so the rule's effect is a number and not a claim.
- [ ] Tests: a stage that would exhaust its budget for nothing now stops and
      reports; a stage that would rescue the fit still runs.
- [ ] Skill: `references/batch.md` — the keep-the-best row, now expressible
      from `StageResult` alone; and the row saying what the new finding means.

## Acceptance

On a suite fixture reproducing the #222 shape (a `biso` or `warm_refit` stage
that runs to its budget for under a few per cent of cost), the `max_nfev`
share of stage time falls substantially with no converged parameter moving
beyond its esd; the number is quoted with its venv and platform (root
CLAUDE.md § Numbers). The 638-pattern tranche is the reporter's and not in the
repo.

```sh
.venv/bin/python -m pytest tests/test_schemas.py tests/test_termination_view.py -q   # plus the stop rule's own module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #222 (638-pattern laboratory chemical-looping series, 1846 fits).
  Its method note: bucketing timed fits on
  `(series_index, series_pass)` is wrong whenever an index recurs (a reseed
  retry, a verification refit, a restarted segment) — it reported 700.686 s
  against a 147.988 s wall clock, **ratio 4.73**, and nothing about the number
  looked wrong. Fixed by pairing `fit_start`/`fit_end` in order; the
  whole-run check that caught it was event-log-summed 3472.73 s against an
  independently measured 3409.27 s, ratio 1.0186. Assert that, do not assume
  it, in anything reporting a duration.

## Handover log

- **2026-11-02** — ghostshift runner, PR #1343. A caller holding a stage's
  record can now read that stage's Rwp from it, so keeping the best stage of a
  run no longer means parsing the event log. The record and the event carry
  one number, computed once, and it is written whether or not anyone asked for
  events. The WP's stop rule is now stated in the unit the solver's count
  actually holds, residual evaluations, so the threshold work has no unit left
  to argue about. Nothing about when a stage stops has changed yet.

  *Done.* Task 1: the rule is § Context's "The rule in the unit the field
  holds", the Context's counts say evaluations, and the ramp guard's constant
  is `RAMP_MAIN_UNBOUNDED_EVALUATIONS`. The field's documentation and the
  "N evals" print were already on main from WP-1937. Task 2:
  `StageResult.rwp`, `float | None`, `None` meaning a result stored before the
  field. Writers: `Refinement._run_stage` (both single-histogram runners read
  it off `_StageHold.rwp`) and the joint runner through `_stage_end_rows`,
  pooled. Schema changelog line under 0.60; three lines in the manual's
  `concepts/fit.md` § Outputs; `help.py` entry; audit
  `OTHER_RECORD_FIELDS` row. The skill sentence in `references/series.md`
  that said `StageResult` has no `rwp` is rewritten, and
  `test_every_negative_field_claim_is_still_true` now pins "`SeriesEntry`
  carries no `stages`", which is true and still the claim's phrasing.
  `/code-review high --fix` found the audit and help rows missing (both red
  tests) and a wrong "only through the events" sentence; it also added
  `CompiledModel.evaluate_with_background`, one background pass for
  `evaluate()`'s curve plus the background, bit-identical to `evaluate()` on
  both arms. Declined from it: reusing the stage's statistics for the history
  node, because the node's `n_free` is read after code that may change the
  free set, and proving it never does was out of scope.

  *Measured* (arm64 Mac, worktree `[dev]` venv, compiled tier on). Cost: the
  stage Rwp is one forward evaluation a stage, which every recorded fit
  already paid; the new charge falls on `telemetry=False` trials. NAC Le Bail
  (6 stages, 46 evaluations) with telemetry off: median 0.315 s before and
  0.320 s after, one 7-run batch each with the machine quiet. Interleaved A/B
  against an origin/main snapshot under heavy load from other sessions' suites
  (5 batches of 3): base medians 3.38-3.88 s, branch 3.31-4.24 s, so no
  difference the load lets one see. Fast suite: not completed. Other sessions' suites held the machine (6 pytest processes), and the run reached 5 % in about 12 minutes, so it was stopped. It had one failure, unidentified because a stopped run prints no summary. The 22 test files that touch the changed names passed, 1022 tests in all (`-n 4`), and CI's fast matrix is the gate.

  *Generality* (the `generality-review` judge; its table condensed to one line a question, verdicts verbatim):

  > **rietx.schemas.results.StageResult.rwp (added to `OTHER_RECORD_FIELDS`). Verdict: holds.**
  > It is the stage's Rwp, a measurement. Nothing in the package reads it to
  > decide anything, and nothing in the diff argues the other way.
  > 1. Decides nothing: no reader of a stage's `.rwp` in `src/rietx`; written by
  >    `_run_stage` (copied by `_run_plan` and `run_stage`) and the joint runner,
  >    pooled. Now computed on every stage; one forward evaluation, no answer
  >    changes. — holds
  > 2. No action, so no kind of ambiguity applies. — holds
  > 3. Case against: none found. Picking the best stage by Rwp would be the
  >    caller's choice; the field comment guards misuse (ranges, modes, frozen
  >    windows). Task 7's keep-the-best skill row would be a heuristic in skill
  >    prose the table cannot see, to be reviewed when it lands. — n/a
  > 4. Case for: no action removed or demoted. — n/a
  > 5. Tier: plain arithmetic under a cited definition (Toby 2006); measuring on
  >    the stage's frozen compile is stated in the comment, help entry and
  >    manual, and decides nothing. — holds
  > 6. No threshold, so no dataset families needed. The `run_stage` path had no
  >    test of its own in the diff. — n/a
  > 7. The field is the record; `None` (stored before the field) cannot pass
  >    for a measured value. — holds
  >
  > Second trigger: none (no inline literal, ordering or fallback chain, skill
  > rule or correction; `evaluate_with_background` is a refactor).
  > Would change the verdict: package code reading `StageResult.rwp` to pick,
  > stop, escalate or keep a stage (tasks 4 and 7).

  Author: the `run_stage` path is now covered by the new test, after this review.

  *Gotchas.* `reference/refinement.md`, the natural home of the field's row
  (§ Stage results), is at the manual's 50 000-character page cap: 49 665 on
  main, and the row plus two lines took CI's built twin to 50 352, so the field
  is documented in `concepts/fit.md` until that page is split. The telemetry
  test that decomposes a recorded stage's forward work
  (`test_what_a_recorded_stage_costs_in_forward_evaluations`) now finds a
  caller's own stream free, since every fit pays the stage Rwp. The last stage's `rwp` is not `result.statistics.rwp`: the
  result is measured on a compile at the answer, so the two differ by the
  frozen windows alone. The negative-claim regex needs the class and the
  field on one line.

  *Not settled here.* "N ev" in the 2026-09-30 decision is printed as
  "N evals" (WP-1937's spelling, on main since 2026-10-10); kept, since the
  ruling's substance is the unit and renaming the print is a reader-output
  change with nothing gained.

  Next: task 3 (the termination split, or the statement that `max_iter` is the
  whole answer), which decides what the stop rule's finding can name; then
  the stop rule against #222's p90, then its fixture measurement. The skill's
  keep-the-best row (task 7) can now cite `StageResult.rwp`.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #222).
  Two of the issue's asks were checked against the tree first: `max_iter` is
  already on `StageResult.status`, `rwp` genuinely is not. Re-checked the
  same day: `STAGE_MAX_ITER` already reports the exhausted stage on the
  result and carries the package's own diagnosis, so this WP is the cost and
  the stop rule, not the report; acceptance moved to a fixture.
