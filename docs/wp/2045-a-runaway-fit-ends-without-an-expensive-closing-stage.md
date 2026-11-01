# WP-2045 — A runaway fit ends without an expensive closing stage

Milestone: unscheduled · Status: 🔄 2026-10-25 — built and measured (PR #1161); open for the first nightly `full` job after merge and the maintainer's call on four audit rows' grounds
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-25 — the fix is built in #1161 and 1.10.1 waits on its merge; what stays open is one nightly reading and a ruling on four rows' grounds

## Goal

The stage before a plan's closing stage converges at the solver's tolerance,
so it does not stop on the frozen-window plateau measured below and hand
the closing stage a runaway to compile (ruled 2026-10-24, option 5). The
hostile series in `tests/test_acceptance_sequential.py` (`chained_all`)
finishes on every platform. The nightly `full` job completes inside its
150-minute limit again. What the change costs the four acceptance standards
is measured and stated.

## Context

**What happens, measured 2026-10-24 by WP-2043** (macOS arm64, `[dev]`, the
1.10.0 release tree; the probe is described under Acceptance). The hostile
series carries every parameter, the phase scales included, from one IUCr
round-robin mixture to the next (cpd-1a → cpd-1b is a large swing in phase
fractions). On cpd-1b the warm attempt's one declared stage ends "converged"
at Rwp 0.760 with these values:

- `instrument.geometry.axial_sl` 557.8. Until 1.10 it had a ceiling of 0.2,
  and real instruments sit near 0.01-0.05.
- `instrument.profile.v` −5.64 deg².
- zincite's oxygen Biso 25 Å².

Then `run_stages()` appends the closing stage (WP-2002), which recompiles at
that answer with windows dropping 1e-3 of each peak (`CLOSING_WINDOW_TOL`)
and the finer axial node rule. At this answer:

| | corundum's window points | FCJ nodes, max | point-nodes per evaluation |
|---|---|---|---|
| cpd-1b's declared stage (2 % windows) | 45 035 | 13 | 352 785 |
| cpd-1a's closing stage, a normal one | 613 003 | 22 | 6 307 023 |
| cpd-1b's closing stage, at the runaway answer | 850 103 (every window is the whole 7 251-point pattern) | 1 024 | 544 128 502 |

So one evaluation of corundum alone costs about 1 500× the declared stage's
and 86× a normal closing stage's. WP-2043's lane saw it spend over 50
CPU-minutes in that closing stage without finishing. The series would have
rejected the attempt anyway (Rwp 0.760 is far outside its fence) and
escalated to the next rung, but only after the closing stage returns.

**When it started.** A snapshot just before #1085 (WP-2002's merge,
`2330afc02`) runs both patterns in 3.1 s, and its warm stage converges at
Rwp 0.139. The nightly `full` job took about 95 minutes on 2026-10-21 and
2026-10-22, and hit its 150-minute `timeout-minutes` on 2026-10-23 and
2026-10-24, the first two nightlies after #1085 merged (2026-10-22 22:30).
WP-2037's local slow run stalled on the same test the same day.

**Two changes of #1085 combine.** (1) WP-2002 B9 removed the limits chosen on
quantities where the model stays defined; `axial_sl` and `axial_hl` lost
their 0.2 ceiling (the 1.10.0 notes, Numbers that move). That was a
maintainer ruling. It is why this warm stage can walk the ratio to 557.8
instead of stopping on a bound, and this WP does not reopen it. (2) The
closing stage polishes whatever the declared stages hand it, and nothing
asks whether that answer is worth polishing or what the polish costs.

**With the closing stage off, nothing runs away** (same probe,
`closing_window_tol=None` on `qpa_plan()`, 2026-10-24). All eight patterns
finish in 9.2 s, each kept on its warm rung, and cpd-1b's warm stage
converges at Rwp 0.163 (corundum 94.84, zincite 1.08, fluorite 4.08 wt %,
weighed 94.31, 1.36, 4.33). So the runaway itself depends on the start: it
begins from cpd-1a's closing-stage answer, not its declared-stage one. A
design that only makes the expensive stage cheaper leaves a warm attempt
that still diverges and is then escalated.

**Who sees it.** A user whose fit runs away now waits with no end in sight,
where 1.9.0 returned a bad Rwp in seconds. Cancelling is cooperative and read
between residual evaluations, so it should take effect within one evaluation
(inferred, not measured). Measured only on this series. A single fit should
behave the same when its last declared stage runs away (inferred from the
mechanism: the closing stage compiles at whatever answer it is handed).
1.10.0 ships with this as a stated limit (the maintainer's ruling,
2026-10-24, option A of WP-2043): `RefinementPlan.closing_window_tol=None`
skips the closing stage.

**What the runaway is, measured 2026-10-24 after the cut** (Linux x86-64
cloud container, 4 cores, `[dev]`, Python 3.12, `OPENBLAS_NUM_THREADS=1`,
tree `7d24e09e7`; the probes are in [`2045-batch/`](2045-batch/README.md)). The
probes ran cpd-1a → cpd-1b under `chained_all`'s protocol. They wrapped
`refine.compile_model` and stopped at the runaway closing compile, which they
reached within seconds. Every time quoted below comes from one run on that
container, so it gives an order of magnitude, not a benchmark. The warm
stage ended "converged" at `axial_sl` 555, with
`w` 0.27 and `v` −5.5. Its closing compile holds 873.7 M point-nodes
(window points × FCJ nodes, all phases and lines). That is 1 608× the warm
stage's own compile, where cpd-1a's normal closing compile is 19× its last
declared stage's.

- **It is a minimum of the frozen model only.** The probes evaluated the
  answer on the model the stage solved on and on fresh compiles. On the
  frozen windows Rwp is 0.760. On fresh windows it is 1.376 at the declared
  precision and 1.294 at the closing precision. The stage started at 1.748.
  At the answer the frozen windows drop **73.4 %** of the Bragg intensity
  a fresh compile computes, and χ²(fresh)/χ²(frozen) is 3.27. On each of
  cpd-1a's eight declared stages and its closing stage, the same measure is
  0.00-1.32 %, with a χ² ratio of 0.94-1.00. The mechanism, inferred from `forward.py:3980-3990`
  and `fcj.py:129-149`: as S/L grows, the asymmetry spreads each peak beyond
  the window frozen at the stage's start, and the part outside drops out of
  the model. So S/L, and the widths, act as an intensity sink, and the warm
  start's scales, carried from cpd-1a, are too strong for cpd-1b.
- **The tolerance stops the stage on the sink's plateau.** The same frozen
  stage, from the same start, ends at `axial_sl` 554.99 under `ftol` 1e-6
  and at 0.0139 (Rwp 0.196) under 1e-9. The 100-iteration cap changes
  neither (`max_iter` 100 and 400 agree). The warm stage runs at
  `intermediate_ftol` only because a closing stage follows it
  (`stage_ftols`, WP-1123). Before #1085 it was the last stage, at 1e-9.
  So #1085 combined three changes, not two: the ceiling, the closing stage,
  and the looser tolerance the closing stage gave the stage before it.
- **Windows that follow the parameters remove the runaway.** The probes ran
  the same warm fit as short stages, each recompiling, closing stage off:
  every 10 iterations ends at Rwp 0.142 (`axial_sl` 0.0077) in about 10 s,
  and every 3 at the same answer in about 25 s. The independent fit gets
  0.137. Every 50 iterations runs further away (`axial_sl` 4 041, zincite's
  scale 0, Rwp 0.779, about 4 minutes): the windows catch up too late.
- **A re-solve after the runaway does not repair it.** From the answer, on
  fresh declared-precision windows, `ftol` 1e-6 goes further (`axial_sl`
  4 114, Rwp 0.782, about 30 s). At 1e-9 it reaches 4 100 and hits its
  400-evaluation cap (about 2.5 minutes). So a check at the stage boundary
  can refuse to build on a runaway but cannot undo one.

**Moving windows were described but never offered.** The freeze dates from
v0.1 (DESIGN.md rule 1, whose stated reason, "gradient bias", the record
never measured). WP-2002's sixth-round brief listed GSAS-II, MAUD,
RIETAN-FP and EasyDiffraction as moving their windows at every evaluation,
and TOPAS as rebuilding them past a tolerance. All four of its options kept
the freeze (`2002-batch/rulings.md`, Q1). In the eighth round the maintainer
asked what those programs do. The five variants measured were all frozen
(`rulings.md`, § Eighth round).

**How the rounds missed it.** B9's brief named the boxes it covered and not
the axial ratios. Those sat in the `Geometry:bounds` hand row, and the
session read "no chosen limits on quantities that remain physical" as
covering them (WP-2002's handover). But `axial_sl` 555 is a sample
half-length 555 goniometer radii long, and the revised pick kept "a box that
guards a … non-physical region". The brief said each box "guards a
runaway", yet the evidence it asked for was whether a box binds an honest
fit. The closing stage was measured on four single fits from good starts.
Nobody measured either change on a fit that runs away. The one test that
does, `chained_all`, is slow-marked and runs only in the nightly `full`
job. That job timed out as cancelled, with no durations table (WP-2036
item 1). The one local slow run on a tree with #1085 (arm64 Mac,
`12f459e5`, before #1113) finished in 18 min.

**Ruled 2026-10-24: option 5 here, for 1.10.1, and option 4 as
[WP-2047](2047-windows-follow-the-parameters-between-solves.md).** The
maintainer's answer, to the candidates below with the measurements above:
"5 now, 4 as own WP". Option 5 sets no threshold, so it adds no `_audit`
row of its own. It changes what `stage_ftols` gives the last declared
stage, so the `intermediate_ftol` rows are re-read against it.

**What option 5 costs, measured 2026-10-25** (macOS arm64, `[dev]`, compiled
tier on, tree `ab5922dd3`, another session's pytest on about three of ten
cores; `2045-batch/probe6.py`). Shipped against the last declared stage's own
`ftol` set to `optimize.lm.FTOL`, two interleaved rounds each. "Away" is the
largest shift from the shipped answer in plain esd, non-background rows
(`test_window_domain._shift`). Evaluations counted at `StageResult.n_iterations`.

| Protocol | Evaluations, whole fit | Last declared stage | Closing stage | Wall clock in s | Away |
|---|---|---|---|---|---|
| SRM 660c LaB6 | 86 → 90 (1.05×) | 7 → 11 | 12 → 12 | 0.90-1.01 → 0.87-0.94 | 0.000 |
| fluorapatite | 47 → 49 (1.04×) | 7 → 9 | 9 → 9 | 2.16-2.17 → 2.15-2.87 | 0.000 |
| cpd-1a | 167 → 175 (1.05×) | 16 from 7 | 14 → 13 | 2.90-3.03 → 2.95-3.07 | 0.0004 |
| 11-BM NAC | 43 → 46 (1.07×) | 7 → 10 | 7 → 7 | 0.79-0.95 → 0.79-0.80 | 0.000 |
| mg090 joint (11-BM + BT-1) | 143 → 143 | 3 → 3 | 8 → 8 | 6.15-6.43 → 5.69-6.22 | 0.000 |

Every arm converged, and Rwp agreed to 1e-10. The joint fit is
`test_acceptance_wavelength._joint(None)`'s protocol. So option 5 hands back
1.04-1.07× of the 1.2-1.6× `intermediate_ftol` buys, and the second task's
rule ("if option 5 costs more than that saving, put the numbers to the
maintainer") does not fire.

**Design candidates, as put to the maintainer.** Each needs the maintainer's ruling, and
the generality audit table needs a row for any threshold
(`src/rietx/_audit.py`; root CLAUDE.md § Every heuristic has a row):

1. Skip the closing stage, recorded in a field and a diagnostic, when the
   recompiled model's work exceeds a factor of the last declared stage's.
   This covers every parameter that drives windows or FCJ nodes, but it is a
   tier-3 threshold.
2. A runaway reset for the axial ratios, on the pattern WP-2002 B8 built for
   a cell (`refine.reset_cell_runaway`, `CELL_RUNAWAY`: a parameter leaving
   a window around its stage-start value is put back and held for one more
   solve). This covers this case, not V or the widths.
3. In `sequential.py`, judge a warm attempt against the fence before its
   closing stage, and run the closing stage only on the attempt kept. This
   covers series and not single fits.

Added after the measurements above:

4. **Windows follow the parameters between short solves**, as TOPAS rebuilds
   its peak buffer when a width passes a tolerance. Each solve keeps its
   windows frozen, so the invariant holds inside it. A stage ends a solve
   and recompiles when its windows have gone stale, and converges only on a
   solve that needed none. Measured on this case: no runaway, Rwp 0.142.
   Unmeasured: whether it moves the four standards' converged answers, what
   it costs them, and which staleness test triggers the recompile (dropped
   intensity separates 0-1.3 % from 73 % here, on one family).
5. **The stage before the closing stage runs at the solver's tolerance.**
   This reverses, for that one stage, what the closing stage did to
   `stage_ftols`. Measured: no runaway, Rwp 0.196. It sets no threshold. It
   removes this trigger and leaves the sink: a sink that is a true minimum of
   the frozen model would still stop a stage there. Its cost on the four
   standards is unmeasured.
6. **The closing compile refuses a stale answer.** Before solving, it compares
   the frozen and fresh models at the answer, using the dropped-intensity
   measure above. On a stale answer it skips the closing stage and says so
   rather than polishing. This guards the cost from the measured cause, not
   a work ratio, but it cannot repair the answer (the last bullet above).
7. **Windows move at every evaluation**, as GSAS-II, MAUD, RIETAN-FP and
   EasyDiffraction do. This drops the frozen-per-stage invariant. The
   analytic and FD Jacobians, FCJ node sizing, the compiled kernels' row
   ranges, the traced backends' static shapes and `replay` all rest on that
   invariant. It is not a patch-release change.

The frozen-per-stage invariant constrains 1-3 and 5-6: window ranges and FCJ
node counts are fixed at compile and never change inside a solve, so any
decision is taken at compile, from values the stage cannot change. Option 4
keeps it per solve and gives it up per stage.

**Files.** `strategy/staged.py` (`run_stages`, the closing stage),
`model/forward.py` (`compile_model`, the window and FCJ sizing), `refine.py`
(`reset_cell_runaway`), `sequential.py` (the rung ladder and fence).

**Practice.** GSAS-II floors SH/L at 0.0005 or 0.002 and sets no ceiling
(`GSASIIstrMath.py`, `GSASIIpwd.py`; checked in GSAS-II 5.8.4 source on
2026-10-24). No program surveyed has a closing stage of this kind; BGMN ends
with every parameter free and restarted from the previous answer
(`docs/practice.md` does not survey axial limits; its § Staging carries
BGMN's closing run). BGMN holds its
ray-traced instrument function for the whole fit (`practice.md` § Staging),
so its closing run cannot move the axial geometry. That precedent does not
cover a closing stage that frees `axial_sl`. GSAS-II's `dropOOBvars`
(`GSASIIstrMain.py:1198-1230`) runs after every `Refine` and after every
histogram of `SeqRefine`. It sets each variable that refined outside a
user-set limit to the limit, freezes it for later refinements with esd 0,
and warns "N variable(s) refined outside limits and were frozen". The limits
are empty by default (`parmMinDict`), so it never fires unless the user arms
it (read on GSAS-II's `main` on 2026-10-24). It is the nearest precedent for
option 2's shape. It also corrects WP-2002 B8's "I know of no program that
clamps a cell after a solve", which was recalled, not checked.

**What the ladder does with it, measured by WP-2003** (2026-10-24, PR #1150,
4-core Linux x86-64 container, `[dev]`; `docs/wp/2003-batch/reseed.md`,
families `cpd` and `cpd-noclose`). At cpd-1b the warm rung's closing stage
ran to its 400-evaluation cap in 2 300-2 600 s and came back `max_iter` at
Rwp 0.7652. Under the default fence (1.25 × the median) the ladder escalated
to `warm_staged` and kept 0.13779, against 0.13732 for the independent fit.
With the fence off, the 0.7652 fit was kept and seeded cpd-1c, whose closing
stage then crawled at about 5 evaluations a minute. With
`closing_window_tol=None` the warm rung reached 0.16333 and nothing
escalated. The time per evaluation is mostly FCJ quadrature: node counts
climb to the 512 cap, and each new count misses the `leggauss` cache
(`model/profiles/fcj.py:88-92`). On Linux with default BLAS threading one
`leggauss(444)` took 5.4-6.0 s, against 0.014 s on one thread, so set
`OPENBLAS_NUM_THREADS=1` before timing anything there. WP-2003 also added
`test_the_first_rung_bound_moves_no_accepted_value`, a second
`chained_all`-shaped chain in the same `qpa-sample1` group. Both chains cost
1 h 17 min on that machine, so the nightly's 150-minute limit counts both.

### Inherited

- **From WP-2036 (2026-10-25): the first nightly after #1161 is in, and it is this WP's last acceptance line.** Run 40184228951 on `deff4c301`: the Linux `full` job completed in 2:05:47 (4 failed / 12 157 passed / 218 skipped / 41 xfailed), and `test_acceptance_sequential.py` is absent from the 25 slowest rows. Two of the four red rows moved with #1161 on Linux and were reproduced on an arm64 Mac by 1e-14 nudges. (a) The planted series' blank frame now sometimes accepts its warm rung and refines zero shift and U..Y against noise, which flags a zero-shift step at 86→87: filed as WP-2049. (b) The alarm pin this WP re-wrote on the Mac reads +0.75 warnings per result on Linux: all six extra are brucite's `HIGH_CORRELATION` against a flat triple (`gauss_size`, `gauss_strain`, `w`, esds about 1124), a count rounding moves from 35 to 42, filed as WP-2050. Neither is a reason to revisit option 5. The pin cannot be re-written to hold on both platforms until WP-2050 lands.

## Non-goals

- Restoring the 0.2 ceilings, or any limit B9 removed. That was ruled.
- Which of S/L and H/L a fit reports. That is WP-2012.
- Every other nightly leg. That is WP-2036, which this WP unblocks for the
  `full` job.

## Tasks

- [x] The design, put to the maintainer with this file's numbers. Ruled
      2026-10-24: option 5, and option 4 filed as WP-2047.
- [x] Measure option 5 before building it, as the ruling asked: on the four
      acceptance protocols (SRM 660c LaB6, the fluorapatite tutorial,
      cpd-1a, 11-BM NAC), the whole-fit time and the largest shift in plain
      esd against the shipped tree, in the shape of WP-2002's eighth-round
      table, plus one joint fit, since `MultiHistogramRefinement.fit` reads
      `stage_ftols` too (`multi.py:1434`). On a single fit, emulate it with
      the last declared stage's own `ftol` set to `optimize.lm.FTOL`, since a
      stage's own `ftol` wins in `stage_ftols`. On a series that emulation
      does nothing: the collapsed warm plan (`sequential.py:502`) builds its
      one stage without an `ftol`. There, `probe3.py`'s single stage at
      `ftol` 1e-9 is the measured stand-in. Compare evaluations, not
      iterations: `StageResult.n_iterations` counts iterations, and WP-1123's
      saving is 1.2-1.6× fewer evaluations. If option 5 costs more than that
      saving, put the numbers to the maintainer.
- [x] The implementation: `RefinementPlan.stage_ftols` gives the last
      declared stage the solver's tolerance when a closing stage follows it,
      a stage's own `ftol` still winning. Every runner then inherits it:
      `PlanSpec` through `resolve_plan`, the joint fit through
      `multi.py:1434`, and the collapsed warm plan in `sequential.py`
      through the plan it builds. `StageResult.ftol` already records what a
      stage ran at.
- [x] A test that fails before the change: the hostile series' cpd-1b warm
      stage from cpd-1a's closing answer ends with `axial_sl` under 1 (on
      the 1.10.0 tree it reaches 555 within seconds on Linux), and a fast
      `stage_ftols` test on a plan with and without a closing stage
- [x] The `intermediate_ftol` rows in `src/rietx/_audit.py`, and the
      `INTERMEDIATE_FTOL` and `CLOSING_WINDOW_TOL` docstrings, re-read
      against the new schedule
- [x] `tests/test_acceptance_sequential.py` finishes, WP-2003's second
      chain (`test_the_first_rung_bound_moves_no_accepted_value`) included;
      VALIDATION.md's three `chained_all` rows (marked unmeasured on 1.10.0)
      re-measured
- [x] Notes for 1.10.1 (`docs/releases/`), and the 1.10.0 stated limit
      withdrawn from the skill. Staged in `1.11.0.md`, the one staging file;
      the cut names the release (ROADMAP rule 6)
- [x] Skill: the stated limit's bullet in `references/series.md` (beside
      the quarantine rule) removed or rewritten to what the fix does

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -n 4 --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The sequential suite finishes, alone on an arm64 Mac, in a time comparable to
1.9.0's (about 2.5 minutes for the module, measured by WP-2043's lane on the
pre-#1085 snapshot). The nightly `full` job completes on `main`.

WP-2043's probe (`hang/probe.py` in that session's scratchpad, not
committed) ran `SequentialRefinement(...).fit` on cpd-1a and cpd-1b under
`qpa_plan()` with `seed_scales` from cpd-1a, as `chained_all` does, wrapped
`compile_model` to log `win` and `fcj_n` per phase, and logged
`stage_start`/`stage_end` events.

## Handover log

### 2026-10-25 — option 5 measured and built: the last declared stage converges, and the hostile series finishes in 92 s

A fit no longer hands its closing stage a runaway that came only from
stopping too early. The last declared stage of a plan now converges at the
solver's tolerance even when a closing stage follows, as it did before 1.10.
On the four acceptance protocols and a real joint fit, that costs 1.04-1.07×
the evaluations and moves no answer by 0.001 esd. The hostile round-robin
series, which never finished on 1.10.0, now runs its whole test module in
92 s on an arm64 Mac, every pattern after the first kept on its warm
attempt. What it does not fix is the mechanism: a stage that converges into
a frozen-window plateau would still hand one on. That is WP-2047's.

*Done.* Inherited folded into Context and the acceptance task. Option 5
measured first (Context, "What option 5 costs"), then built in
`RefinementPlan.stage_ftols` (`endpoints` = the last declared and the last
run stage); every runner reads it. A slow test,
`test_the_hostile_pairs_warm_stage_stops_short_of_the_runaway`, fails at
once on any closing compile above `axial_sl` 1: on the parent tree
`d9faf96e4` (run from a `git archive` snapshot) it fails at 557.8 in 6 s,
and here it passes in 7-8 s. The schedule's prose was rewritten to "every
declared stage but the last" across `staged.py`, `plan.py`, `results.py`,
`help.py`, `textdoc.py`, the manual (reference and theory pages) and the
root CLAUDE.md rule. Notes are staged in `releases/1.11.0.md`, the one
staging file; the cut names the release. The skill's series bullet is now
a one-line sign and remedy tagged Hypothesis. The four `intermediate_ftol`
audit rows' shared evidence was re-measured, and `FTOL` and
`StageResult.ftol` cite the new job and the ruling. VALIDATION's three
`chained_all` rows re-measured, and the new test has its `ceiling` row.
`test_warm_start_iteration_cost_is_reported`'s strict xfail XPASSed (both
chains now mean Rwp 0.1282), so the mark is gone. Forward references went
to WP-2036 (re-rated: the `full` job is unblocked pending the first
nightly), WP-2003 (the xfail forwarded to it is gone), WP-2047 and WP-2017.

*Measured* (macOS arm64, `[dev]`, compiled tier on; another session's pytest
on about three of ten cores during the probes, idle during the module run).
- Option 5's cost: the table in Context.
- The hostile pair on this tree: cpd-1a cold at Rwp 0.16307; cpd-1b warm at
  Rwp 0.13984, `axial_sl` 0.0082, warm stage 291 evaluations, closing 21;
  8.1 s for both. The independent cpd-1b fit is 0.1373 (WP-2003).
- `tests/test_acceptance_sequential.py`, `-n 4`: 15 passed in 92-94 s.
  Iterations 408 restricted carry, 655 carry=*, 1255 independent; mean Rwp
  0.1282 both chains, 0.1258 independent; zero reseeds; kept first-rung
  ratios 0.064-0.080 of the running maximum.
- `intermediate_ftol` 1e-6 against `None`, largest plain-esd shift: LaB6
  8.82 (`axial_sl`, its mirrored minima, the strict xfail), FAP 0.000,
  cpd-1a 0.0004, NAC 0.000, cpd-1a with zircon declared 0.009.
- `test_staged_start_invariance.py`, `test_budget_and_tolerance_invariance.py`
  and `test_bound_hit_at_convergence.py`: 43 passed, 3 xfailed.
- The fast selection (`-m "not slow"`, `-n auto`): 2 failed, 11 672 passed,
  272 skipped, 27 xfailed in 8:05, with nothing else running. Both failures
  were this change's and are fixed: the handover log's `####` judge headings
  (the session hook reads only dated headings there, so they are now bold
  lines), and `examples/guides/path.py` (next bullet); each re-ran green. No
  fast test was added (the new test is slow), so the fast total should match
  main's.
- **One cost the table did not show.** `examples/guides/path.py`'s planted
  1.5 % cell jump at 700 K now breaks the warm start on *both* sides of the
  step. The 800 K warm start, the step back down, now fails at Rwp 0.941 and
  is fitted cold, where at 1e-6 it stopped short of that minimum and stayed
  warm. Both end at Rwp 0.0395 and 0.0402, and the jump is still flagged at
  the same pair. Ten starts nudged by 1e-14 gave the same rungs every time;
  the 700 K first attempt's Rwp ranged 0.04-0.95 (Accelerate). So converging
  the last declared stage can cost a series an extra cold fit after a real
  discontinuity. The guide and its page now say so.
- The full selection (`-n auto`, `[dev]`, macOS arm64, main at `ab5922dd3`
  merged, nothing else running): 2 failed, 12 075 passed, 283 skipped,
  42 xfailed in 29:53. Both failures were this change's, fixed and re-run
  green (6 passed). (1) `test_nac_termination_view_golden_shape`: the golden
  pinned the last declared stage at `ftol=#e#`, which now reads `ftol=solver
  default`; that one line changed. (2) `test_the_standards_fire_what_the_pin_says`:
  every purpose's warnings per result rose by exactly 1/8. One standard,
  brucite, gained one warning of a code it already fired:
  `HIGH_CORRELATION` on `lor_size` against `lor_strain`, ρ = −0.995, at the
  answer only. Size and strain widths are nearly collinear over a lab range
  (1/cos θ against tan θ), and converging the last declared stage moved
  brucite to where that pair crosses the 0.98 guard; its other four pairs
  moved by 0.001 in ρ. Re-pinned with `python -m tests.suite_alarms --write`.
  Against the fast count this session added one slow test and turned one
  strict xfail into a pass; CI's nightly holds the baseline.

*Gotchas.*
- A probe's emulation (a stage's own `ftol`) is inert on this tree, since
  option 5 gives the same schedule; `2045-batch/README.md` says so.
- The cpd-1b runaway reads 557.8 on arm64 and 555 on Linux. The notes and
  the test docstring quote 557.8 (the arm64 run that fails the test); the
  73 % and 1 608× figures in `staged.py` are the Linux probe's at 555.
- The manual's reference page sits at about 49 600 of its 50 000-character
  cap, so the next addition there needs a cut or a split.
- A worktree session cannot `cd`; the snapshot run used `PYTHONPATH` on
  the snapshot's root and `src` with the venv's interpreter.

*Review* (`/code-review high --fix`). Six findings. Fixed: the solver-seam
test still pinned every pre-closing stage at 1e-6 (red under LM and TRF);
the reference page passed its character cap (the why-paragraph moved to the
theory page); the GUI document's tolerance comment; the root CLAUDE.md rule
(left to me, done); the new test read eight patterns for two (done).
Declined: choosing between 557.8 and 555 in the notes, handled in Gotchas
above instead.

*Generality* (the `generality-review` judge, report pasted as given):

**`rietx.optimize.lm.FTOL`**

**Verdict: holds for the edit, weak as a row.** The evidence for keeping 1e-9 is the stronger side. But this change gives the value a new job, and the row carries none of the evidence for that job.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the closing stage and the last declared stage solve at it (WP-2045)" (`_audit.py:2053`) | Correct. In `staged.py`, `stage_ftols` now gives both stages `None` (the solver default) through `endpoints`. FTOL also now decides whether the stage before the closing stage gets past the plateau that frozen windows create. The closing stage is the final stage WP-2002 added, recompiled with tight windows. WP Context: "ends at `axial_sl` 554.99 under `ftol` 1e-6 and at 0.0139 (Rwp 0.196) under 1e-9". The row does not say this. | holds, incomplete |
| 2. Kind of ambiguity | **none given**: the row has no `ambiguity` field | Not new to this change. The schedule rows beside it claim kind 1. | none given |
| 3. Case against | already on the row: SciPy's default is 1e-8 and GSAS-II's `min dM/M` is 1e-3, both marked checked | For the new job, none found. The WP shows that 1e-6 fails. Nothing between 1e-6 and 1e-9, and nothing tighter, was measured. | none found (new job) |
| 4. Case for | not on the row | WP probes: 555 against 0.0139. New slow test `test_the_hostile_pairs_warm_stage_stops_short_of_the_runaway`. `tests/validation_matrix.py` records it reaching `axial_sl` 0.0082, and says "the parent tree fails it at 557.8". Cost is 1.04-1.07× the evaluations (WP Context table). | strong, but not cited on the row |
| 5. Tier | 3, grounds unchanged. Delegated 2026-10-23, with WP-2017 (the second-pass audit) to refit "at 1e-8 and 1e-10" | Tier 3 still fits. The new job makes that refit matter more: whether the runaway comes back at 1e-8 is unmeasured. Only the GSAS-II and SciPy defaults are checked on the row. I checked no others. | holds |
| 6. Families | "this value itself was never varied" | The new job rests on one family: the IUCr CPD round-robin pair cpd-1a → cpd-1b, with every parameter carried from one pattern to the next. The reference is rietx's own independent fit (Rwp 0.1373), so it verifies the code and validates nothing. | weak |
| 7. What records it | — | `StageResult.ftol` reads `None`. `tests/test_closing_stage.py` asserts `[1e-6, None, None]`. | holds |

Would change the verdict: WP-2017's 1e-8 and 1e-10 refits running the cpd-1a → cpd-1b pair, and the row citing the new test.

*Author's answer:* the row now cites the new job, its one family and the new test (`d86504ea2`), and the 1e-8 refit on the pair went to WP-2017's Inherited.

**`rietx.schemas.plan.INTERMEDIATE_FTOL`, `PlanSpec:intermediate_ftol`, `StageSpec:ftol`, `StageResult.ftol`**

All four rows carry the same evidence string, so this one section covers them. INTERMEDIATE_FTOL is the constant. The two `Spec` rows are the defaults that apply it. `StageResult.ftol` is the action row for the schedule.

**Verdict: weak.** The re-measured evidence is accurate and more current than the text it replaces. But the grounds were not rewritten. They still argue from a failing case the new evidence no longer lists, and the approval is dated before that case changed. The case against the loose tolerance is now the better-evidenced side.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "behind the closing stage, with the last declared stage converged (WP-2045), 1e-6 against every stage at 1e-9…" (`_audit.py:982`, `2615`, `2947`, `3003`) | Every declared stage except the last now stops at 1e-6 rather than 1e-9. After this change one fewer stage is loosened. | holds |
| 2. Kind of ambiguity | `ambiguity=1` on three rows. INTERMEDIATE_FTOL has **none given**. | Kind 1 holds only if LaB6's 8.82 esd is read the evidence's way: "its mirrored S/L and H/L minima (WP-2012)". These are two equally good minima with the two axial ratios exchanged, and the Biso start test reaches both too. On that reading the tolerance only picks between them. | holds on that reading |
| 3. Case against | "fails on SRM 660c, 8.82 esd on axial_sl … a strict xfail" | Confirmed: `tests/test_staged_start_invariance.py` has a strict xfail with reason "8.82 esd on axial_sl (WP-2002, 2026-10-23)". The esd here is plain, without the Bérar-Lelann inflation. This failure predates WP-2045. The old row's "0.000" for LaB6 was a 2026-10-21 reading and was already stale, so the edit corrects it. A refiner who runs every stage to convergence (`intermediate_ftol=None`) lands in LaB6's other minimum. `docs/practice.md` § Staging does not survey per-stage tolerances, so I could not find what the seven programs do. | case real, and stated |
| 4. Case for | grounds: "kept on four families with its failing case stated, where the alternative is the arm that runs out of budget" | The arm that "runs out of budget" was the old failing case: cpd-1a with an absent zircon, where at 1e-9 zircon's cell walked to the stage's iteration limit. The new evidence has that case passing at 0.009. So the grounds' one accuracy argument for 1e-6 is gone, and only cost remains: "1.00-2.15x fewer evaluations … of which converging the last declared stage hands back 1.04-1.07x". The joint fit's 1.00× (143 → 143) sits outside that quoted range. `PlanSpec`'s field description (`plan.py:263`) still says "1.2-1.6x fewer". | weak: grounds not re-read |
| 5. Tier | 3, `approved="2026-10-21"` | Tier 3 is right: the schedule is rietx's own, from WP-1123. But the 2026-10-21 approval covered "four families with its failing case stated", and that case was zircon. The failing case is now LaB6, and three families hold, not four. The maintainer has not approved that. | weak |
| 6. Families | FAP, cpd-1a and 11-BM NAC within the bar; LaB6 fails | Three unrelated families by laboratory, instrument and material: the GSAS-II tutorial fluorapatite (lab), the IUCr CPD round robin (lab Cu), and 11-BM (synchrotron). The zircon case is cpd-1a again, not a fourth family. The reference is rietx's own all-1e-9 run, so this verifies and validates nothing. The rule asks the row to say which, and it does not. That gap predates this change. | meets the count; reference kind not stated |
| 7. What records it | `StageResult.ftol` | Written on every stage and asserted in `tests/test_closing_stage.py`. | holds |

Would change the verdict: grounds rewritten to the current failing case and the cost-only argument, then a fresh approval date from the maintainer. Alternatively, a measurement where 1e-6 beats 1e-9 on accuracy.

*Author's answer:* left for the maintainer, since the grounds and the approval date are the ruling's record. This entry's Next puts it to them.

**`RefinementPlan.stage_ftols`: the last declared stage converges (not seen by the table)**

**Verdict: holds.** No new row is needed. The case for the rule is strong: a measured runaway, removed at a measured cost of 1.04-1.07×. Its place in the table is the `StageResult.ftol` action row, and that row's grounds do not yet cite the ruling.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "Option 5 sets no threshold, so it adds no `_audit` row of its own" (WP, "Ruled 2026-10-24") | True. It reuses FTOL and INTERMEDIATE_FTOL and adds no number. It is a scheduling rule, which the table sees through `StageResult.ftol`, the action row keyed on the record field. A stage's own `ftol` still wins. | holds |
| 2. Kind of ambiguity | inherits `StageResult.ftol`'s `ambiguity=1` | Kind 1 is plausible. The stage was stopping on an artefact: its frozen windows dropped "73.4 %" of the Bragg intensity a fresh compile computes (WP Context). No refiner wants a stage to stop there. | holds |
| 3. Case against | "It removes this trigger and leaves the sink: a sink that is a true minimum of the frozen model would still stop a stage there" (WP, option 5) | That is a limit of the fix, not a dissent. The cost is 1.04-1.07×. I found no competent refiner who would loosen this stage. The WP's Practice section says no surveyed program has a closing stage of this kind. | none found |
| 4. Case for | WP Context and cost table | Under 1e-6 the stage stopped at `axial_sl` 555, against 0.0139 under 1e-9. The closing compile held 1 608× the point-nodes of the stage before it. 1.10.0's hostile series did not finish after 50+ CPU-minutes, and the nightly hit its 150-minute limit. After the change, every pattern after the first is kept on its warm attempt. The largest shift is 0.000-0.0004 esd on five protocols, Rwp agreeing to 1e-10. | strong |
| 5. Tier | maintainer's ruling, 2026-10-24 | It is part of rietx's own tier-3 schedule. The `StageResult.ftol` grounds still read only "WP-1123 … ruled 2026-10-21", with no mention of the 2026-10-24 ruling. I found no practice survey on per-stage tolerances in the repository. | holds; ruling unrecorded on the row |
| 6. Families | five protocols for cost | The cost and the unmoved answers rest on five: LaB6, FAP, cpd-1a, NAC, and the mg090 joint fit (11-BM X-ray with BT-1 neutron). All are against rietx's own shipped run, so they verify. The defect rests on one family, the CPD pair. The WP marks single fits as "inferred from the mechanism", not measured. | defect on one family; cost on five |
| 7. What records it | "`StageResult.ftol` already records what a stage ran at" | Confirmed: `None` on the last declared stage, asserted in `tests/test_closing_stage.py`. No diagnostic, and none is needed for a schedule. | holds |

Would change the verdict: a second family where the last declared stage stops on the plateau even at 1e-9. That is the open case WP-2047 inherits, and it would argue for a guard with its own row. Separately, the `StageResult.ftol` grounds should cite the 2026-10-24 ruling.

*Author's answer:* the `StageResult.ftol` grounds now cite the 2026-10-24 ruling (`d86504ea2`).

Next: the maintainer, on two things. First, the path guide's extra cold
fit (Measured, "One cost the table did not show"): an answer-neutral cost,
recorded and not acted on. Second, the four schedule rows' grounds (the
judge's second section). They still argue from the zircon failing case, which now
passes at 0.009; the failing case is LaB6's mirrored minima, which is
WP-2012's. Rewriting them and re-dating the approval is the maintainer's
call. Then, after #1161 merges, read the first nightly `full` job: it is
this WP's last acceptance line, and WP-2036's.

### 2026-10-24 (2nd session) — ruled: the stage before the closing stage converges, and windows that follow the parameters get a WP of their own

The runaway that stalls the hostile series is not a real answer. It exists
only because each stage freezes its peak windows. As the axial ratio grows,
each peak spreads past its frozen window and the overflow drops out of the
model. So growing the ratio can only remove intensity, and with the warm
start's scales too strong for the next mixture, that lowers the error. The
warm stage stops there only because a closing stage now follows it, which
loosens its tolerance; at the tolerance it ran at before 1.10, the same
stage from the same start finds a sane answer. Windows recompiled every few
iterations avoid the runaway entirely and give the best answer measured.
The maintainer ruled the tolerance change for 1.10.1 and the recompiling
windows into WP-2047.

*Done.* The design was put to the maintainer in three rounds: options 1-3
(work ratio, axial reset, fence first), then how the rounds missed it and
what practice says, then whether windows that move at every evaluation were
considered. Each answer is in Context: "What the runaway is", "Moving
windows were described but never offered", "How the rounds missed it" and
the Practice paragraph (GSAS-II's `dropOOBvars`, checked on its `main`).
Candidates 4-7 were added and the ruling recorded above them. Goal and tasks
were rewritten to option 5. WP-2047 was filed for option 4. WP-2036 was
re-rated P1 → P2 with this WP as a hard dependency. The five probes are in
`2045-batch/`. No code changed.

*Measured* (Linux x86-64 cloud container, 4 cores, `[dev]`, Python 3.12,
`OPENBLAS_NUM_THREADS=1`, tree `7d24e09e7`, one run per probe). The runaway
reproduces within seconds at `axial_sl` 555. Its closing compile is 873.7 M point-nodes, 1 608×
the warm stage's, against 19× for cpd-1a's normal one. The full set (frozen
against fresh Rwp, intensity dropped, the `ftol` and K tables, the
re-solves) is in Context's four bullets.

*Gotchas.*
- `rietx.refine` is the exported function. The module is
  `sys.modules["rietx.refine"]`, where the probes patch `compile_model`.
- The probes are records, not tests, and nothing runs them
  (`2045-batch/README.md`).
- A force push to the session's branch was refused by the harness. The
  branch's old tip was an ancestor of `main`, so a fast-forward push did
  the job.
- A stage's own `ftol` never reaches a series' warm stage, which is built
  without one, so the single-fit emulation does nothing there (second task).

*Review* (`/code-review high`, run without `--fix` because the probes record
runs whose numbers are already quoted). Ten findings. Fixed: the "Next"
decision rule had been written inverted; the series emulation gap; the
joint fit's use of `stage_ftols`; single-figure timings, now one-run orders
of magnitude; the Practice paragraph contradicting itself; probe2's
docstring and its iterations labelled "evals"; probe.py's abort test,
aligned with the other four (both tests fire at the same compile in the
recorded run, so no number moves). Checked, not changed: probe4 pairs
consecutive compiles as stages, which holds for the recorded run (eight
declared stages, then the closing compile, then the final compile; the
wording now says so). Declined: one shared helper for the five probes,
because rewriting a record changes the script that produced its numbers.

*Verified.* The branch changes only `docs/wp/`. The probes sit outside
`testpaths` and ruff's targets, and they compile and pass `ruff check`.
`tests/test_docs_consistency.py` passes, 25 tests. No count can move, so
neither the fast nor the full selection ran. No generality judge was
dispatched: `_audit.py` is untouched, and option 5 adds no threshold until
it is built.

Next: measure option 5 on the four standards and one joint fit before
building it (the second task). If it costs no more than what
`intermediate_ftol` saves, build it (third and fourth tasks). If it costs
more, the numbers go to the maintainer before any code.

- **2026-10-24** — filed by WP-2043's session (the 1.10 cut), after its
  VALIDATION lane found the hostile series never finishing and the session
  reproduced the cause. No open WP owns the closing stage's cost: 2036 owns
  the nightly legs being green and gets an Inherited pointer, 2012 owns the
  axial pair's identity, 2020 owns opt-in bound sets. The maintainer chose to
  cut 1.10.0 with the limit stated and fix it here.
