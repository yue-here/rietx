# WP-1334 — the stage that ran out of budget

Milestone: unscheduled · Status: ⬜
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
median one does not. They run a median of **201 iterations against 34**, and
concentrate in `warm_refit` (153) and `biso` (74); the worst individual
stages are `biso` at 15.98 s / 400 iterations and `phase_strain` at 8.51 s /
400, both `max_nfev`.

The ask is a per-stage rule of the shape *"if a stage exhausts its iteration
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
| **n iterations** | **+0.859** | +0.142 … +0.961 | **yes** |

Cost tracks **iteration count** at a per-iteration price linear in pattern
size: `s/iter = 4.4 µs × n_points + 2.9 ms`, r(n_points, s/iter) = **+0.972**.
Broadening moves neither the number of steps nor the price of one. So the
lever this WP pulls (fewer iterations) is the only one measured to work.

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
quantity the solver owns (relative cost decrease over the last k iterations),
never in seconds, and its default must be justified against the p90 = 92 %
tail — the point of the rule is to stop the median case without abandoning the
minority that rescues a fit.

## Non-goals

- The reporting cost that sits outside the stage brackets — 1335. #245
  measured that summing stage durations understates fit cost by ~9× under
  `stage_reports=True`; that is a different number and a different fix.
- A new solver or driver. This is a stop rule over the existing TRF path.
- Changing `Stage.ftol` or the intermediate-ftol schedule (WP-1123's rule:
  the plan alone knows which stage is last).

## Tasks

- [ ] #538: `n_iterations` documented as evaluations, `_stage_lines` prints "N ev", the ε / p90 rule stated in that unit (decided 2026-09-30)
- [ ] `StageResult.rwp` — the number `stage_end` already emits, on the object
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

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #222).
  Two of the issue's asks were checked against the tree first: `max_iter` is
  already on `StageResult.status`, `rwp` genuinely is not. Re-checked the
  same day: `STAGE_MAX_ITER` already reports the exhausted stage on the
  result and carries the package's own diagnosis, so this WP is the cost and
  the stop rule, not the report; acceptance moved to a fixture.
