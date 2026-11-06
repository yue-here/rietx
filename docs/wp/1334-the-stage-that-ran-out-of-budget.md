# WP-1334 — the stage that ran out of budget

Milestone: unscheduled · Status: ✅ 2026-11-05 — tasks 1-7 shipped (PRs #1343, #1366); the first-rung route pinned and the WP closed by PR #1430
Track: A long run is not one fit
Depends on: —

## Goal

A stage that exhausts its iteration budget while barely improving the cost
stops rather than escalating, and says so. A caller holding a `StageResult`
can apply the keep-the-best-pass discipline the skill asks for without parsing
the event log for a number the object was standing next to when it was
computed.

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
- [x] The finer termination reason on `StageResult`, or a written statement
      that `status == "max_iter"` is the whole answer and the log's split is
      deliberately log-only. `StageResult.termination`, the `stage_end`
      token; writers the three runners.
- [x] A stop rule: a stage exhausting its budget below a stated relative-cost
      improvement stops, and `STAGE_MAX_ITER` (or a sibling) says the rule cut
      it rather than the budget running out. Default chosen against the
      measured p90, not invented. `optimize.lm.SLOW_DESCENT_ESD`; its stop
      reads `converged` and the info code `STAGE_SLOW_DESCENT` names it
      (ruled by Yue 2026-11-03), its tier-3 rows approved the same day.
- [x] Re-measure the #222 tranche shape on a suite fixture and record the
      recovered fraction, so the rule's effect is a number and not a claim.
      The 2026-11-03 handover entry.
- [x] Tests: a stage that would exhaust its budget for nothing now stops and
      reports; a stage that would rescue the fit still runs.
      `tests/test_slow_descent.py`.
- [x] Skill: `references/batch.md` — the keep-the-best row, now expressible
      from `StageResult` alone; and the row saying what the new finding means.
      9c.34, and the `STAGE_SLOW_DESCENT` row in `references/diagnostics.md`.

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

- **2026-11-05** — close-out runner, PR #1430. This WP closes. The one route
  the series check could not reach now has a test: a bounded first rung whose
  closing stage the slow-descent rule stops below the bound. That rung counts
  as complete, nothing escalates, and the chain with the bound answers bit for
  bit as the chain without it. The two crawls this WP inherited are gone as
  well. `solve_magnetic` at 150 K needed 3 to more than 10 continuations and
  now needs at most 1, and the moment guide's 800-evaluation stage no longer
  occurs.

  *Done.* `tests/test_sequential.py::test_a_slow_descent_stop_below_the_bound_truncates_nothing`.
  No real fixture stops a crawl reliably across platforms, so the test forges
  one in the real driver, by `test_slow_descent.py`'s device. On p004 of the
  thermal ramp the closing stage starts 1e-5 away from its minimum with a
  Jacobian 100 times too large. The rule stops it at 204 evaluations, under a
  bound of 360 and a plan budget of 800, at Rwp 0.543699 against 0.543697. The
  test asserts the stop, `rungs_tried == ["warm"]`, `STAGE_SLOW_DESCENT` on the
  entry, equality of every value, esd, rung and code with the unbounded chain,
  and that p005's budget grew from the rung's 204. `/code-review high --fix`
  stopped the two chains' forgeries stacking on one `monkeypatch`, corrected
  two docstring claims, dropped one assertion that could not fail, and added
  the PNG (`tests/output/sequential_slow_descent_p4.png`). One more finding
  was that the record was not yet written, which this entry answers.
  `test_magnetic_solve_acceptance.py`'s 150 K docstring now quotes the rule's
  numbers.

  *The guard fails on purpose* (a pytest plugin, no source edit). A window that
  reads the budget, the rule's first form, fails on `chain_answer`. A rule stop
  counted as the bound's cut fails on `rungs_tried`. A rule stop kept out of the
  sample fails on p005's budget, 90 against 200.

  *Measured* (macOS arm64, worktree `[dev]` venv, compiled tier on).
  - `docs/wp/2036-batch/cr2wo6_150k_continuations.py` at the six 1e-14 nudges of
    `w`: class 3 takes 1, 1, 1, 1, 0 and 1 continuations, each converged, verdict
    "nothing to solve". On 2026-11-02 the same nudges took 3, 4, 4, 5, 10 and
    more than 10. Its Rwp lands at 0.097878-0.097899 across them. Linux was not
    measured, so the test still does not assert convergence.
  - `examples/guides/moment.py`, round 1's all-free stage from the magCIF start:
    13 evaluations, `exhausted_fp64`, Rwp 0.104747. No stage in the guide ends
    `slow_descent`. The 10-25 entry's 800 evaluations did not recur, and this
    run does not say which change removed them.
  - Acceptance: 379 passed over `test_schemas`, `test_termination_view`,
    `test_slow_descent` and `test_lm_solver` (4 workers). The #222 fixture's
    numbers are the 2026-11-03 entry's: 816 → 539 evaluations, worst shift 0.064
    esd.
  - Fast selection: 13922 passed, 240 skipped, 36 xfailed, none failed (`-m "not slow"`, through
    `serial.py`, on 541f0daf7 plus this branch, other sessions' runs beside it).
    No baseline was measured on that tree, so the +1 is not checked by
    subtraction. The added test took 11.66 s in that loaded run and about 5 s
    alone. It stays in the fast tier so that a merge fails on this route, as
    the bound's other rows in the file do.

  *Settled by Claude.* A first rung the rule stopped joins the bound's sample.
  Grounds: the ruling of 2026-11-03 makes such a stage `converged`, and "worked
  is convergence" is `_first_rung_budget`'s written rule. The alternative was to
  leave it out as a cheap stop that says little about a working rung's cost. The
  consequence is that one crawl can raise the bound for the rest of a chain, and
  at a high factor switch it off. Issue #222 closes with this PR, since its ask
  shipped. Its 638-pattern tranche is the reporter's and was not re-run.

  *Not generalised.* A warm stage the rule stops takes the same code path, and
  the ba2fesbse5 ramp's p11 stops that way at 107, but no test pins it. Its stop
  moves with the last digits, and the real ramp under a bound was not run. A
  bound below the rule's stop still cuts a winning rung and escalates. That is
  WP-2003's stated risk of `first_rung_factor`, and this test does not change
  it.

  Inherited: both entries consumed by the two measurements above and removed.

  Next: none here.

- **2026-11-03** — ghostshift runner, PR #1366. A stage whose cost is still
  falling, but too slowly to matter, now stops before its budget runs out and
  says so. Every stage record also names the test that ended its solve. On the
  suite fixture with the #222 shape (the GSAS-II LaB6 recipe, whose background
  hump is a degenerate direction) the fit spends 539 evaluations instead of
  816, and no parameter moves by more than 0.064 of its esd. A stage the rule
  stops reads `converged`, and an info diagnostic, `STAGE_SLOW_DESCENT`, names
  it (ruled by Yue 2026-11-03, the second runner implementing it). Its text,
  quoted in the PR body's "What a reader receives", was approved by Yue the
  same day.

  *Done.* Task 3: `StageResult.termination`, the `stage_end` token, written by
  the three runners; `None` on a record stored before it. Task 4: the
  slow-descent rule in the LM driver (`optimize.lm._descent_too_slow`).
  Once at least 100 residual evaluations have passed, it projects the decrease
  of the last 100 over the next 300. It stops the stage when that projection
  is below `SLOW_DESCENT_ESD`² × S/(N − P), the χ² one esd of joint travel
  buys. Termination `slow_descent`, status `converged`, and the info code
  `STAGE_SLOW_DESCENT` (`refine._slow_descent_diagnostics`, also called by
  the joint fit) names the cut stages. `STAGE_MAX_ITER` is the budget's alone
  again, its message byte for byte as on main. The TRF driver has no rule (scipy owns
  the loop). `SLOW_DESCENT_ESD = None` is the old driver bit for bit. Task 5:
  *Measured* below. Task 6: `tests/test_slow_descent.py` (a crawl for nothing
  stops and gives up 0.85 S against χ²_red 1.04; a crawl that halves S runs
  to its budget unchanged; a stage converging inside the window is
  untouched; the two codes' messages). `test_lm_solver.py`'s face crawl may
  now also end `slow_descent`. Task 7: batch row 9c.34 and the
  `STAGE_SLOW_DESCENT` row in `references/diagnostics.md`. Inherited pruned: the #538 entries (task 1,
  done), the 09-28 skill sentence (done in #1343) and both "`diverged` has
  no writer" entries (stale since WP-2048: `STAGE_NOT_FINITE` writes it).

  *Measured* (macOS arm64, worktree `[dev]` venv, compiled tier on, another
  shift's suites sharing the machine, so seconds are not quoted). Each fixture
  fitted with the rule off and on. Shifts are the largest |Δvalue| over the
  larger plain esd. Probe and per-stage records:
  `~/.cache/ghostshift/rietx/wp-1334/` (`probe.py`, `probe_*.json`).

  | fixture | evaluations off → on | budget stops off → on | worst shift | Rwp off → on |
  |---|---|---|---|---|
  | GSAS-II LaB6 recipe (powderline) | 816 → 539 | 2 → 1 (closing cut at 123) | 0.064 esd, background c5 | 0.084093 → 0.084098 |
  | cpd-1a + absent zircon, every stage at 1e-9 | 1221 → 935 | 2 → 1, plus `cell` (converging at 127) cut at 123 | 0.009 esd, profile v | 0.163049 → 0.163050 |
  | cpd-1a + zircon, shipped 1e-6; GSAS-II DRX_33; LaB6, FAP, cpd-1a, NAC protocols at 1e-9 | unchanged | none | 0 | bit-identical |
  | Cr₂WO₆ 150 K `solve_magnetic`, unnudged start, stop read as `max_iter` (first form) | 2540 → 1824 | class 3: 5 continuations of 400, then converged → 10 continuations cut at ~101, ends `max_iter`, unranked | — | class 3 0.0979014 → 0.0979015 |
  | the same, stop read as `converged` (ruled form) | 2540 → 913 | class 3: 5 continuations → 1 continuation, cut at 102, converged and ranked; verdict "nothing to solve" either way | — | class 3 0.0979014 → 0.0978985 |

  After the ruling, rule on (same machine and venv; `probe4.py`,
  `next_probe.py`, `cr_on3.log` in the scratch directory). A single fit stops
  where it did before the ruling, so the evaluations and shifts above hold;
  only the labels move. LaB6: the closing stage reads `converged
  slow_descent` at 123 and carries `STAGE_SLOW_DESCENT`; `extra_components`
  still spends 400 and carries `STAGE_MAX_ITER`. cpd-1a + zircon at 1e-9:
  `cell` (123) and `profile_w` (113) read `converged slow_descent`,
  `lines_axial` spends its budget, and the result reads `converged`.
  `guides/next.py`: the `cell` stage is cut, so the five suggestion gains at
  that pause move by 3 to 14 of 39 000-322 000 (322283 → 322280, 189147 →
  189145, 156429 → 156424, 129119 → 129105, 39436 → 39429). Every other
  number it quotes is unchanged, and the page and script now quote the new
  gains. `guides/stage.py` and the indexing Le Bail validation row pass
  unedited.

  So the recovered fraction on the #222-shaped fixture is 277 of the 800
  evaluations its two budget stops spent (35 %). The extra-component stage
  still runs to 400: it falls fast enough that 300 more evaluations would buy
  more than one esd. An earlier version of the rule projected over the rest
  of the stage's budget with a quarter-budget window. It cut LaB6 to 423
  evaluations, but it also cut the cpd-1a+zircon closing stage at 109 where
  it converges at 104-115. That turned the result's status to `max_iter`. It
  also gave a series' bounded first rung (WP-1127) a smaller window than the
  unbounded rung, so the bound could change an accepted answer. The fixed
  100/300 counts remove both (`/code-review` found the second).

  *Generality* (the `generality-review` judge, condensed). `SLOW_DESCENT_ESD`:
  tier 3, **weak**. The case against is a caller who raised `max_iter`
  wanting a minimum, and the cpd-1a and Cr₂WO₆ costs. The case for is GSAS-II
  stopping looser (default 3 cycles, 1e-3 per-cycle dM/M, `GSASIIobj.py:20`,
  checked); its statistic differs, so not tier 2. Three families fired, all
  development data, each measured against rietx's own budget-run answer.
  Window and horizon: tier 3, **weak**, holding for the shipped schedule only.
  `StageResult.termination` failed as filed in `OTHER_RECORD_FIELDS`. It is
  now a tier-3 action row (ambiguity 1), since it reports the stop. Skill row
  9c.34 holds. The `STAGE_MAX_ITER` skill row failed for claiming a rerun was
  not owed, and now claims only the rate. The judge would want a per-stage off
  switch, or `solve_magnetic` continuations exempt. Both are in the decision
  below.

  *Rulings.* The previous runner brought three decisions. Ruled by Yue
  2026-11-03, taking the entry's recommendation:
  1. A stage the slow-descent rule stops reports `status="converged"` with
     `termination="slow_descent"`, plus an info-level diagnostic naming the
     cut stages. Implemented as `STAGE_SLOW_DESCENT` (name settled by Claude:
     it is the termination token in the house `STAGE_*` form, as
     `STAGE_MAX_ITER` is the status's). A rule-cut stage no longer reads as
     out of budget, so `STAGE_MAX_ITER` lists only `max_iter` stages.
  2. The four tier-3 rows are approved: `SLOW_DESCENT_ESD` (1.0),
     `_SLOW_DESCENT_WINDOW` (100), `_SLOW_DESCENT_HORIZON` (300) and the
     `StageResult.termination` action row, each `approved="2026-11-03"`.
  3. Reader output: `STAGE_SLOW_DESCENT`'s code, both message forms, its
     suggestion and its help title, quoted in the PR body: text approved by
     Yue 2026-11-03, after the series check below.

  *Series check* (a separate runner, 2026-11-03, PR head `c7e7ee088`,
  macOS arm64; numbers in `~/.cache/ghostshift/rietx/wp-1334-series/report.md`).
  `sequential.py` never reads `termination`; it sees a slow-descent stop only
  as `converged`. The 47 series test files, slow rows included, pass on both
  trees, along with the series and path guides, tutorial 05 and the ladder
  bench. Bounded and unbounded first rungs still give bit-identical accepted
  values (0 of 610 and 0 of 336 differ). Against main, 6 of 184 series fits
  in 5 chains move, by at most 0.067 esd, with fewer evaluations. Their
  rungs, statuses, first-rung budgets, quarantines and series codes are
  unchanged; their `STAGE_MAX_ITER` becomes `STAGE_SLOW_DESCENT`. Untested
  route: a bounded first rung whose closing stage the rule stops below the
  bound. No fixture produced it, and it is the one route that could break the
  bit-identity.

  *Generality, second pass* (the `generality-review` judge on the ruled
  form, condensed). `STAGE_SLOW_DESCENT` code row, tier 1: **holds**. It
  reports a recorded fact and gates nothing. Like `STAGE_MAX_ITER` it is not
  in `sequential.NOT_A_SERIES_FINDING`, so a series counts it. Its
  suggestion, as first filed (tier 1, ambiguity 1): **weak**. It promised
  that freeing fewer parameters would let the stage converge, which nothing
  measures, and named one lever where `HIGH_CORRELATION` names two. Author's
  answer: reworded to point at the correlation and bound findings and defer
  the remedy to their own suggestions, ambiguity 3, as
  `STAGE_NOT_FINITE.suggestion`. The `termination` row's rewritten evidence:
  **weak** without the Cr₂WO₆ rerun. Author's answer: rerun (table above),
  and the evidence now quotes it and names the sequential consumers as not
  measured. `SLOW_DESCENT_ESD`'s corrected numbers: **holds**. The
  `STAGE_SLOW_DESCENT` skill row: **weak** for a unitless "0.5" and a
  correlation claim from one fixture. Author's answer: the number is gone,
  the claim tagged `(Hypothesis: …)`, the correlation clause cut. 9c.34 and
  the reverted `STAGE_MAX_ITER` row: **hold**.

  *Gotchas.* The rule reads N as every row the driver sees, penalty and
  restraint rows included, so its χ²_red is not quite the esds'. That is
  stated in the docstring rather than plumbed. A pull request (#1356) edits
  `strategy/staged.py`'s presets, and this branch does not touch them.

  *Not done.* The moment guide's 800-evaluation crawl (Inherited, 10-25) was
  not re-run. A per-stage off switch was not added: under the converged
  status the cases that wanted it (the guides, the `solve_magnetic`
  continuations) no longer mislabel. A series is measured in the series
  check above.

  Fast suite before the ruling (`-m "not slow"`, `[dev]`, macOS arm64, through `serial.py`,
  another shift's suites running): 5 failed, 13608 passed, 319 skipped,
  34 xfailed. `test_audit_table`'s approval row was decision 2. The other four
  were re-run alone. `test_display`'s kernel row also fails with the rule off,
  so it belongs to this machine and not to this branch. Three are this rule's
  status label. `guides/stage.py` prints `cell max_iter Rwp 0.4919` where its
  page quotes `converged`, at the same Rwp. `guides/next.py` exits 1 the same
  way. `test_indexing_consensus`'s Le Bail validation row `[1.01-some-many]`
  reads `max_iter` against `converged`, and it passes with the rule off. So a
  stage converging slowly past 100 evaluations on the shipped schedule is
  common outside the nine acceptance configurations, and under `max_iter` the
  rule mislabels it.

  After the ruling (second runner, head `239df5efc` merged with main, `[dev]`,
  macOS arm64, through `serial.py`): 1 failed, 13644 passed, 319 skipped,
  34 xfailed. The failure was the manual's page cap. The new
  `STAGE_SLOW_DESCENT` section took the generated refinement diagnostics
  page's text twin to 50 625 characters against the 50 000 cap; it had
  stood about 165 under. Most of its codes are raised in one file,
  `refine.py`, so the file-area rule cannot split it. The codes prefixed
  `STAGE_`, `PLAN_` and `HOLD_` there now go to a new page,
  `reference/diagnostics-stages.md` ("Stages and plans",
  `reference_pages.STAGE_CODE_PREFIXES`), and the six hand-written links to
  those anchors moved with them (the tutorial notebook's link edited in
  place, its outputs untouched). `test_manual`, `test_manual_api`,
  `test_gui_manual`, `test_docs_consistency` and `test_help` then pass.
  Re-run on the tree merged with main again (WP-2012's presets landed),
  same venv and route: 13646 passed, 319 skipped, 34 xfailed, none failed.
  The LaB6 hump acceptance row passes there too.
  Targeted rows, run alone: the LaB6 hump acceptance test, the `next` and
  `stage` guide rows, the indexing Le Bail validation rows,
  `test_validation_matrix`, `test_slow_descent`, `test_lm_solver`,
  `test_audit_table`, `test_help`, `test_gui_help`, `test_docs_consistency`,
  the skill tests and `test_manual_api` pass. `tests.audit_delta`: six rows
  added, none new at `unaudited`. `tests.reader_output`: unchanged. ruff clean.

  Next: the merge. The PR is ready for review, its reader text approved.

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
