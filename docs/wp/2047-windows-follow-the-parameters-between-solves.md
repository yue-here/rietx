# WP-2047 — Windows follow the parameters between solves

Milestone: unscheduled · Status: ✅ 2026-10-25 — the stale-window report shipped; per-evaluation windows measured and handed to WP-2051
Track: What fires, and what stays silent
Depends on: 2045 (the trigger it removes first); 2017 soft (the families this is measured on)

## Goal

No stage ends silently at an answer that exists only in its frozen
discretisation. Each stage measures, at its answer, how much Bragg intensity
its frozen windows drop against windows sized at that answer, records it,
and reports a stage whose loss exceeds its own window tolerance. Then a
prototype of windows recomputed at every evaluation is measured, to decide
whether rietx adopts the practice of GSAS-II, MAUD, RIETAN-FP and
EasyDiffraction. The four acceptance standards' answers do not move.

(Rewritten 2026-10-25 on the maintainer's ruling, Context § The ruling. The
goal as filed was a recompile between solves.)

## Context

**The sink.** Each stage freezes its windows at the values it starts from
(root CLAUDE.md § Invariants, the first). When a parameter that widens peaks
grows during the solve, the part of each peak outside its frozen window
drops out of the model. That parameter can be the axial ratios or the
widths. Its growth then removes intensity, a direction the physics does not
have. Where the start's scales are too strong, that direction lowers χ² on
the frozen model.

**Measured by WP-2045's ruling session** (2026-10-24, Linux x86-64 cloud
container, 4 cores, `[dev]`, Python 3.12, `OPENBLAS_NUM_THREADS=1`; the
runs are in WP-2045's Context, the probes in
[`2045-batch/`](2045-batch/README.md)).
The case is the hostile series' cpd-1a → cpd-1b
(`tests/test_acceptance_sequential.py`, `chained_all`):

- cpd-1b's warm stage ends "converged" at `axial_sl` 555, `w` 0.27 and `v`
  −5.5. Its frozen model reads Rwp 0.760. A fresh compile at the same values
  reads 1.29, and the stage started at 1.75.
- At that answer, the frozen windows drop 73.4 % of the Bragg intensity that
  a fresh compile computes, and χ²(fresh)/χ²(frozen) is 3.27. On each of
  cpd-1a's eight declared stages and its closing stage, the same measure is
  0.00-1.32 %, with a χ² ratio of 0.94-1.00.
- The same warm fit split into short stages, each of which recompiles
  (closing stage off; times are one run each, orders of magnitude only):

  | recompile every | outcome |
  |---|---|
  | 10 iterations | Rwp 0.142, `axial_sl` 0.0077, about 10 s |
  | 3 iterations | the same answer, about 25 s |
  | 50 iterations | worse: `axial_sl` 4 041, zincite's scale 0, Rwp 0.779 |
  | never (one frozen stage at `ftol` 1e-9) | Rwp 0.196 |

  The independent fit of cpd-1b gets 0.137.
- From the runaway answer, a re-solve on fresh windows does not come back:
  at `ftol` 1e-6 it reaches `axial_sl` 4 114 and Rwp 0.782; at 1e-9 it
  reaches 4 100 and hits its 400-evaluation cap. So the windows must follow
  while the stage is still near where it started. A check after the stage
  can refuse the answer, but cannot repair it.

WP-2045 removes the trigger measured there: the warm stage stopped on the
sink because it ran at `intermediate_ftol`. It does not remove the sink.
This WP is option 4 of WP-2045's candidates, ruled out of 2045 and into its
own WP by the maintainer on 2026-10-24 ("5 now, 4 as own WP").

**Why the freeze, and what was never measured.** The freeze dates from v0.1.
DESIGN.md rule 1 gives as its reason "window membership depends on refined
cell/zero parameters and creates gradient bias", which the record never
measured. WP-2002's sixth-round brief adds a second reason: a point entering
or leaving a window between two evaluations steps χ², and derivatives cannot
see the step. A recompile between solves keeps both safe, because no solve
ever sees a window move. Two parts are open:

- the stopping rule. A stage that recompiles must not call itself converged
  on a solve that moved its windows.
- the history record. A stage that recompiled is several compiles, and
  `StageResult`/`NodeAction` record one `window_area_tol` and one compile per
  stage today, which `replay` and a cherry-pick read.

**Practice** (`docs/practice.md` § How far a peak is computed and §
Staging). TOPAS rebuilds its peak buffer when a width moves past a set
tolerance. GSAS-II, MAUD, RIETAN-FP and EasyDiffraction recompute their
windows at every evaluation. FullProf holds its windows for a whole run, as
rietx holds them for a stage. No program's manual states what its rule costs
in accuracy.

**The tier of each rule this WP adds** (written 2026-10-25 by the session
that started it; revised after the ruling). The report is of DESIGN §
Rules' third kind: the data cannot rank a remedy here, so the stage reports
the number with its meaning and acts on nothing. Its threshold is no new
number. It is the stage's own `window_area_tol`, the area the compile
already allows each window to drop, so `lost` above it means the frozen
windows drop more than the whole allowance. Its separation is measured on
one family (normal stages at most 1.73 % against the 2 % tolerance and 2e-5
against the closing 1e-3; the hostile stage 73-99 %).

**Files.** `refine.py` (`Refinement._run_stage`, where a stage compiles and
solves), `model/forward.py` (`compile_model`'s window and FCJ sizing, and
where a staleness measure would be computed), `strategy/staged.py`
(`stage_ftols`, the closing stage), `schemas/results.py` (`StageResult`),
`schemas/history.py` (`NodeAction`).

**What WP-2045's option 5 left** (folded from `### Inherited` 2026-10-25;
PR #1161). `RefinementPlan.stage_ftols` gives the last declared stage 1e-9 when a closing stage follows. On the hostile pair cpd-1b's warm stage reaches `axial_sl` 0.0082 at Rwp 0.1398 (macOS arm64), against 0.142 for your recompile-every-10-iterations probe and 0.137 for the independent fit, so a recompiling scheme still has about 0.003 in Rwp to find on this case. The frozen-window sink itself is untouched: a stage that converges into it at 1e-9 would still hand the closing stage a runaway, and no second case is known. The new slow test `test_the_hostile_pairs_warm_stage_stops_short_of_the_runaway` fails at once on any closing compile above `axial_sl` 1, so it guards your change too. Option 5's cost table (1.04-1.07× evaluations, no answer moved on the four protocols) is in WP-2045's Context.

**The axial zero case, #774** (folded from WP-1421's `### Inherited` entry
2026-10-25; moved to WP-2051 the same day, since windows here did not come to
follow the parameters and the re-check applies only if 2051's are adopted;
kept below as the record). The case was ruled (c), documented: with both axial ratios at exactly zero and either free, the compile sizes the windows and the FCJ nodes as if each were `forward.AXIAL_SIZING_FLOOR` (0.02), so `predict()` differs from the same model held at zero by 4.8e-5 of the strongest peak (the issue's rutile reproducer). Sizing every zero model at the floor (option a) made the gap exactly 0 and a default fluorapatite `mccusker_default` fit 2.0× slower (0.64-0.71 s → 1.32-1.35 s, `[dev]`, darwin/arm64). The floor does two jobs: a live derivative column at zero (the nodes) and room for the tail the stage grows (the windows). The 4.8e-5 is the windows' job. Once windows follow the parameters between solves, that job is this WP's, so a model at zero could size its nodes from the free set and its windows from its value, which may close the gap at no cost. Unmeasured: check that free and held curves at zero then agree, and that the derivative column at zero stays correct (`test_cross_backend.py`'s axial rows). `forward.MAGNETIC_SIZING_FLOOR` has the same zero-case shape (`forward.py:4008-4013`), unmeasured; check it in the same pass. The sentence to update if the gap closes is in `help.py`'s `axial_sl`/`axial_hl` entries and `Refinement.predict`'s docstring; `docs/practice.md` § Axial divergence at zero has the survey. A second point for your acceptance: WP-1421 re-measured the closing stage against one more empty stage on the fluorapatite tutorial (0.00 % under `mccusker_default`, 9.26 % with `closing_window_tol=None`), and a hand-run `run_stage` has no closing stage, so it keeps that gap. That is your sink at the size of one stage.

**The staleness test, measured** (2026-10-25, macOS arm64, `[dev]`, Python
3.12, `OPENBLAS_NUM_THREADS=1`, on `main` at `28c88711d`; probes in
[`2047-batch/`](2047-batch/README.md)). Three candidates, asked at every
stage's answer (probe 1) and at every accepted LM iteration of every stage
(probe 3), on the four acceptance protocols and on the hostile pair under the
pre-WP-2045 schedule, which still runs away on this tree (`axial_sl`
0.036 → 558).

| Candidate | Normal stages, any iteration | Hostile warm stage | Cost of one check |
|---|---|---|---|
| `lost`: Bragg intensity the frozen windows drop, against a fresh compile | ≤ 1.73 % (LaB6's `profile` stage at its first iteration; cpd-1a's 1.35 %); every other stage ≤ 0.1 % | 93 % at the first accepted iteration; never below 73 % after it | one compile, 4-17 ms, plus two Bragg evaluations |
| χ²(fresh)/χ²(frozen) | 0.94-1.07 | 180 at the first solve's first iteration, but 1.02 at the second solve's first, where `lost` is 77 % | the same compile |
| The pseudo-Voigt area outside each frozen window, from the frozen model alone | rises ≤ 3 % above its value at the compile, which is 0.5-1.9 % | catches the first solve's cell jump (99.9 %); reads 2.5 % at `axial_sl` 558, where `lost` is 73 % | 0.1-0.3 ms |

Three findings carry into the design:

- **The hostile stage goes stale at its first step, not by drift.** The
  first accepted trial of cpd-1b's warm stage moves corundum's cell +8.2 %
  (4.7585 → 5.15 Å), its scale ×165 and two Biso to 0. The answer it
  converges to then collapses a phase, and the stage's second solve, on the
  same frozen model, carries `axial_sl` to 558. Any threshold from 0.5 % to
  50 % fires at the first iteration. A check only at a solve's end is
  therefore late, which is WP-2045's "a check after the stage can refuse the
  answer, but cannot repair it".
- **Only `lost` separates both halves.** The χ² ratio misses the second
  solve, where both models fit equally badly. The pseudo-Voigt estimate is
  blind to the axial tail, which is the documented sink. The cheap
  estimate is ruled out as the test; it could only screen for position jumps.
- **The window tolerance is a natural threshold.** A declared stage's
  windows are compiled to drop at most `WINDOW_AREA_TOL` (2 %) of each peak.
  `lost` > that tolerance means the frozen windows drop more than a fresh
  compile by more than the whole allowance. No normal stage reaches it at any
  iteration (largest 1.73 %, a margin of 1.16×); the hostile stage exceeds it
  37-46×. Half the tolerance (1 %) fires on two normal `profile` stages, both
  at their first iteration. A false alarm costs one compile and a re-solve; a
  miss costs the sink.

A fresh compile costs 4-17 ms against whole fits of 0.6-3.4 s here, with
8-12 compiles a fit (probe 1). One check per stage end would add about
5-15 % to these short fits unless it reuses the next stage's compile, which
is at the same values; one per iteration would add about 50 %.

**Two rules, emulated** (probe 4, same machine and tree; 2026-10-25). Each
wraps the solver so a stage's solve becomes several solves, with a fresh
compile between two of them when `lost` exceeds the compile's own window
tolerance. `end` checks when a solve ends and re-solves, at most five times.
`chunkN` solves N iterations at a time and checks between chunks. The
emulation sits inside the solver call, so the stage's phase-collapse check
still runs after it, on the last model.

| Rule | cpd-1b, pre-2045 schedule | cpd-1b, shipped schedule | Four protocols: evaluations against shipped |
|---|---|---|---|
| shipped | runs away, `axial_sl` 558 | Rwp 0.1398, `axial_sl` 0.0082, 312 evaluations, 6 s | — |
| `end` | Rwp 0.1398, `axial_sl` 0.0082, 170 evaluations, 207 s | over 300 s, aborted | 1.00× on all four; no recompile |
| `chunk10` | runs away, `axial_sl` 4.8 | runs away, `axial_sl` 7.9 | 1.00-1.02×; no recompile |
| `chunk3` | Rwp 0.1398, `axial_sl` 0.0082, 118 evaluations, 5.6 s | Rwp 0.1398, `axial_sl` 0.0082, 145 evaluations, 7.1 s | 1.00-1.10× (cpd-1a 193 against 175); no recompile |

No rule recompiled any stage of the four protocols. Every answer stayed
within 0.001 esd of shipped. Wall time on them rose 2-47 %, mostly the
probe's own fresh compile per check; the first three families ran while the
machine was swapping, so those seconds are rough.

- **`end` rebuilds at the runaway, and that model is enormous.** Under the
  shipped schedule the warm stage's first solve converges after 230
  iterations with corundum's *a* at 41.04 Å (from 4.76). `lost` there is
  99.93 %, and the fresh compile has 354 million window points against
  68 thousand, which paged the machine. The shipped stage survives that
  answer because the collapse check restores the phase and solves again; the
  `end` rule compiled before the collapse check could act. A real
  implementation would check after the support step, but the old schedule's
  second solve also ends at `axial_sl` 558, where `end` paid 207 s.
- **`chunk3` works by catching the first step.** Its one recompile is at
  iteration 3, after the cell jump of 4.76 → 5.15 Å, while the model is
  still near where it started. The stage then never collapses, so the
  second solve's axial jump never happens. `chunk10` checks too late.
  The chunk size is therefore a tuned number whose margin is unknown: 3
  works and 10 fails, on one case.
- **The emulated check is wrong on a Le Bail stage unless it carries the
  extracted intensities** (`refine._carry_lebail`); without them NAC's
  first stages read 41-47 % lost and recompiled at the cap.

**The ruling** (maintainer, 2026-10-25, "go" on the session's proposal).
Four options were put: report a stale stage (1), recompile every N
iterations (2), check every accepted step and recompile on a trip (3), and
nothing (4). A check at each solve's end was out in all of them, since it
recompiles at the runaway. The maintainer then asked about windows
recomputed at every evaluation, which this WP had listed as a non-goal. The
session's view was that this is the right end state, since it removes the
sink rather than detecting it and matches four of the five programs
surveyed. Two costs are unmeasured. The residual steps by a tail value
whenever a window edge crosses a point, and whether LM still meets `ftol`
1e-9 is unknown; GSAS-II's windows run 50 FWHM below a peak and 75 above
(`GSASIIstrMath.py:4071-4077` in 5.8.4, read this session), where rietx's
reach about 16 FWHM of a Lorentzian at the 2 % tolerance. And the frozen
layout is built into the compiled kernels, the batched forward, the
derivative bases and jax's static shapes. Ruled: option 1 now, then a
prototype of per-evaluation windows, measured before anything is adopted.
Options 2 and 3 are dropped, since adoption would make them throwaway.

**The report, measured** (2026-10-25, same machine, `[dev]`, run alone;
probes 5 and 6). `forward.rewindow` resizes a compiled model's windows and
FCJ node counts at given values on its frozen reflection list, reading the
peaks `phase_peaks` draws; `forward.window_loss` compares the two models'
Bragg sums. At every stage answer of the four protocols and the hostile pair
it agrees with a fresh compile to six decimals (probe 5). Its node counts
come from `fcj.fcj_node_counts`, a vectorised twin of the compile's
per-reflection call, which was 80 % of its time; the compile keeps the
scalar call, since a vectorised transcendental may land an ulp away and a
count on a ceiling would move every converged fit. One check costs 1-4 ms on
a declared stage and up to 22 ms on a closing stage, whose 1e-3 windows make
each Bragg evaluation dearer. In whole fits, timed seven times each way and
interleaved:

| | NAC | LaB6 | Fluorapatite | cpd-1a |
|---|---|---|---|---|
| Added per fit | 15 ms | 21 ms | 51 ms | 46 ms |
| Ratio | 1.034 | 1.046 | 1.041 | 1.029 |
| Largest stage loss | 0.00 % | 1.61 % | 0.02 % | 1.32 % |

NAC's 15 ms is inside the per-stage budget its shortest fit sets (17.7 ms,
root CLAUDE.md). No standard raises `STAGE_WINDOWS_STALE`. The hostile pair
under the shipped schedule records −1e-5 on cpd-1b's warm stage, after the
collapse check restored it, and stays silent. Under the pre-2045 schedule
the warm stage's `stage_end` reads 73.4 %. The fit cannot run to its result
there, since the closing compile at `axial_sl` 558 runs for tens of minutes;
the slow test reads the event and stops at that compile.

**Which stages the code reports** (a session judgement, 2026-10-25, for the
maintainer to reverse). The fast suite found a sixth fit: the calibrate
guide (`examples/guides/calibrate.py`), whose `sample_profile` stage frees
the sample broadening from zero and ends with its windows dropping 12.1 %.
The three stages after it refit from that answer on fresh windows, and the
guide's size lands within its esd of the true value. So the field records
every stage, and `STAGE_WINDOWS_STALE` reports only the stages whose answer
reaches the result with at most one refit: the last stage, and the one
before it when the last is the closing stage. The runaway is the last
declared stage, which only the closing stage refits, and that did not repair
it. The alternative is to report every stage, which warns on the calibrate
guide's correct fit. The rule is read off the record (`CLOSING_STAGE_NAME`),
so the joint runner, which has no plan at that point, applies it too.

**The prototype, measured** (2026-10-25, same machine, `[dev]`, numpy path,
compiled tier on; probes 7 and 8, probe 7 by a lane whose hostile result the
session re-ran). Windows and FCJ node counts are resized at every residual
and Jacobian evaluation by wrapping the solver's two closures
(`least_squares._make_residual`, `_make_jacobian`) with `rewindow`'s rule.

| | NAC | LaB6 | Fluorapatite | cpd-1a |
|---|---|---|---|---|
| Evaluations, shipped → per evaluation | 46 → 49 | 90 → 110 | 49 → 83 | 175 → 216 |
| Fit time ratio (median of 5, interleaved) | 1.24 | 1.63 | 1.66 | 2.08 |
| Resizing seconds a fit | 0.12 | 0.21 | 0.35 | 1.25 |
| Residual calls that moved a window | 17/56 | 56/124 | 67/108 | 186/243 |
| Largest answer shift, plain esd | 0.0002 | 0.025 | 0.042 | 0.99 (`profile.v`) |
| Polished at 5e-5: points apart, χ² shipped / per evaluation | — | 5.1 esd, 3.518 / 3.549 | 0.0 esd, 2.747 / 2.747 | 0.95 esd, 1.847 / 1.845 |

(NAC polished 0.0 esd apart at 12.406 both.) Every stage converges in both
arms, no stage reaches its budget, and the count of each LM termination is
unchanged per family. Near the answers a window edge crossing a point steps
the cost by 1e-10 to 1.6e-5 of itself, 10² to 10⁴ times what `ftol` 1e-9
resolves, and the extra evaluations sit in the late stages, where LM rejects
more trials. The hostile pair does not run away under per-evaluation
windows under either schedule: cpd-1b Rwp 0.13944, `axial_sl` 0.00758, in
41 evaluations under the pre-2045 schedule and 70 under the shipped one,
against shipped's 312 and 0.13984. The warm stage never collapses a phase.

Accuracy is a wash on these families. Fluorapatite and NAC polish to one
point. cpd-1a reaches a second minimum 0.95 esd away with χ² 0.1 % lower; the
manual already records start-dependence there (two Biso starts 15 esd apart
on fluorite's strain). LaB6's polished points sit 5 esd apart on `profile.u`
with shipped's χ² 0.9 % lower, inside the known defect where U sits under
the Γ_G² floor (`test_the_closing_stage_meets_the_bar`'s docstring). One LM
trial on cpd-1a's `lines_axial` stage sat at `axial_sl` 1096, where the
resized model held 17.8× the compile's window points; LM rejected it, but an
implementation needs a policy for trial points far from the start. Not
covered: the traced backends (jax needs static shapes), the magnetic
family, the extra peaks, and LM's width inequalities, built once per solve
from the start's windows.

## Non-goals

- Recompiling between solves within a stage (options 2 and 3 of the
  ruling). Dropped for the prototype.
- The peaks buffer, shape reuse across reflections for speed. That is fenced
  to v2 with FPA (root CLAUDE.md, the backends paragraph; WP-1122).
- Restoring an axial ceiling, which B9 never named (WP-2045's Context, How
  the rounds missed it). That is a ruling of its own if it is wanted.

## Tasks

- [x] The staleness test: what a stage measures between solves, at what
      cost, and its threshold. Two candidates were measured on one family:
      intensity dropped by the frozen windows, and the χ² ratio fresh/frozen.
      The threshold gets an `_audit` row (root CLAUDE.md § Every heuristic
      has a row), since tier 3 on one family is all that is known.
- [x] The design, put to the maintainer (Context § Two rules, emulated, and
      § The ruling). Ruled 2026-10-25: report now, then the per-evaluation
      prototype.
- [x] `forward.rewindow(model, values)`: a copy of a compiled model whose
      windows and FCJ node counts are sized at `values` on its frozen
      reflection list, without a compile. Its agreement with a fresh compile
      and its cost are measured on the four protocols.
- [x] The report: each stage measures `lost` at its answer through
      `rewindow`, records it in `StageResult.window_loss` and `NodeMetrics.window_loss`
      (a measurement, so the metrics and not `NodeAction`, which a replay
      reruns), raises `STAGE_WINDOWS_STALE` above the stage's own
      `window_area_tol`. Its `_audit` row, and its cost on NAC, the
      shortest fit, against the per-stage budget (root CLAUDE.md, a
      per-stage charge)
- [x] Tests: the hostile pair under the pre-2045 schedule reads 73 % on the
      warm stage's `stage_end` (its result is never reached: the closing
      compile at the runaway takes tens of minutes); the four protocols raise
      nothing (`test_window_domain.py`); the field reaches the node in
      `tests/test_window_loss.py`
- [x] Skill and manual: the diagnostic's reference row; the manual's generated pages carry the code and the field from `help.py`, and
      `reference/refinement.md` stays as it was, being at its 50 000-character cap
- [x] The prototype: windows recomputed at every evaluation on the numpy
      path, on the hostile pair under the pre-2045 schedule and the four
      protocols: answer shift in esd, evaluations, time, and whether LM
      still meets `ftol` 1e-9. Then a brief to the maintainer: adopt, and
      at what cost, or not (Context § The prototype, measured). Ruled
      2026-10-25: file it here, and test a fast resizing with a tapered
      edge in WP-2051 (PR #1174)
- [x] #774's zero case: moved to WP-2051 with its Context paragraph, since
      it changes only if windows follow the parameters

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -n 4 --dist loadgroup
.venv/bin/python -m pytest tests/test_staged_start_invariance.py -n 4 --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The hostile pair under the pre-2045 schedule raises the stale-window
diagnostic, and the four standards raise none and move not at all. The
report costs NAC, the shortest fit, no more than the per-stage budget, or
the excess is stated. The prototype's measurements and the brief that
follows them are in the Context.

## Handover log

### 2026-10-25 — the stale-window report shipped, per-evaluation windows measured and handed on (closed)

A stage that ends on peak windows its peaks have outgrown now says so. Every
stage records the share of the Bragg intensity its frozen windows dropped at
its answer, and the stage whose answer reaches the result warns past its own
window tolerance. The one known runaway reads 73 %, the four acceptance
standards at most 1.6 %, and the measurement costs 3-5 % of a fit.
Recompiling between solves was measured and dropped. A check at a solve's end
rebuilt windows at the runaway and paged the machine, and a check every N
iterations worked only at N = 3 on one case. Windows resized at every
evaluation, the practice of four of the five programs surveyed, removed the
runaway at 1.24-2.08× the fit time, with no accuracy gain on the standards.
The maintainer asked for that design to be tested fast, which is WP-2051.

**Done.** `forward.rewindow` and `forward.window_loss` (no compile; the
compile's window arithmetic shared through `_window_bounds`, the node rule
through `fcj._node_rule`, the Voigt width pair through
`CompiledModel.peak_gamma_eta`); `fcj.fcj_node_counts`, a vectorised twin
pinned to the compile's per-reflection call over a grid;
`StageResult.window_loss`, `NodeMetrics.window_loss` and `stage_end`'s
`window_loss`, written by all three runners (a joint fit records its worst
histogram); `STAGE_WINDOWS_STALE` (warning, tier 3, ambiguity 3) with its
help entry, skill row, silence pair, audit rows, `DIAGNOSTIC_SCOPES` row
and a place in `NOT_A_SERIES_FINDING`; slow tests on the hostile pair (both
schedules) and on the four protocols (`test_window_domain.py`); probes 4-8
and their README. `reference/refinement.md` is unchanged, being at its
50 000-character cap; the generated result-field and diagnostic pages carry
the field and the code.

**Ruled 2026-10-25.** Option 1 (report) over recompiling every N iterations,
recompiling on a tripped step, and nothing; then, after the prototype, file
it here and test a compiled resizing with a tapered edge in WP-2051 (its
PR is #1174, filed from a scratch snapshot of `main` through the git data API).
Issue #774's re-check moved there.

**A session judgement for the maintainer to reverse.** The code reports the
last stage and the one before a closing stage only (Context § Which stages
the code reports). The calibrate guide's `sample_profile` stage ends at
12.1 % and the stages after it repair it; reporting every stage would warn
on that correct fit.

**Measured** (macOS arm64, `[dev]`, Python 3.12, `OPENBLAS_NUM_THREADS=1`):
Context §§ The staleness test, Two rules emulated, The report, The
prototype. Timings were taken alone: a pytest beside probe 6 once put
389 ms on a 51 ms charge, and the first probe 4 pass ran while the Mac
swapped 14.4 GB.

**Lanes.** One, the prototype (probe 7), dispatched at 397K context:

| lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prototype | 25 | 67 | 397K | 77K | 9K of 9K | 9 | 27K | 3 | 0 | opus-5-5 | 3.83 | 1.18 | 8.74 | +3.57 |

Estimates ran 2.68× short. The selective policy's replay row with these
inputs: lane when main > 150K and item ≥ 20 requests, −10 % (292 sessions).
Its hostile-pair result was re-run here and reproduced.

**Code review** (`/code-review high --fix`): eight findings, five fixed
(the schema changelog for the two fields; the closing stage told by its
recorded fraction as well as its name; three copied rules shared), one taken
by hand (`NOT_A_SERIES_FINDING`), two declined. A joint fit's warning names
no histogram: recording which needs a new field, and joint fits are few.
The extra Bragg evaluation a stage pays: measured and inside the budget.

**Generality** (the `generality-review` agent's sections, unedited; the
author's answers follow).

**`STAGE_WINDOWS_STALE` (code), `src/rietx/_audit.py:963-982`**

**holds.** The case for reporting is stronger: the code ends a known silent failure at 3-5 % extra fit time, and it stays quiet on four unrelated datasets. Three sub-answers are weak: the grounds leave out TOPAS, the margin's own choice is not cited, and the `approved` date covers a rule the WP marks unratified.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "fires when StageResult.window_loss … passes the stage's own window_area_tol" (row evidence, `_audit.py:964-967`) | It decides when a frozen-window loss becomes a `warning`, meaning "act before quoting a result number". The threshold sits at exactly 1× the stage's own tolerance (`refine.py:7365-7366`). It takes no action. | agrees |
| 2. Kind of ambiguity | `ambiguity=3`; "the data cannot rank a remedy here" (WP Context, "The tier of each rule this WP adds") | The statistic itself is arithmetic: how much intensity the frozen windows drop. What stays open is whether the answer is wrong and which remedy fixes it. A better start needs facts the caller holds, such as the expected cell. Kind 3 fits the verdict. | agrees |
| 3. Case against acting (the warning) | none given | No measured case lies between 1.61 % (the largest normal stage at its answer) and 73 % (the runaway). So no evidence shows whether a mild loss on the stage before a closing stage is already repaired by the closing refit. The one mid-range stale stage measured (the calibrate guide, 12 %) was repaired by later refits. FullProf freezes windows for a whole run and reports nothing (`docs/practice.md:29`). That is a dissent from saying anything at all, but it is a weak one for a report. | weak case |
| 4. Case for acting | "the QPA round-robin chain's runaway before WP-2045 reads 73 %" (row evidence). Cost "1.029-1.046" ratio, 15-51 ms a fit (WP Context, "The report, measured") | Strong. Before WP-2045 the warm stage reached `axial_sl` 558 (an axial-divergence ratio; the independent fit gets 0.0082) and reported "converged". The existing `FROZEN_COMPILE_STALE` misses half of that runaway (`refine.py:7356-7358`). The WP says the frozen-window trap itself is untouched by WP-2045. Five of the seven programs keep windows current: four every evaluation, TOPAS past a tolerance (`docs/practice.md:26-32`). So rietx is the outlier, and saying so is cheap. | strong |
| 5. Tier and source | tier 3. Grounds: "No surveyed program reports this: GSAS-II, MAUD, RIETAN-FP and EasyDiffraction resize every evaluation and FullProf never does" (`_audit.py:975-978`) | Tier 3 is right. **The grounds name five of the seven programs.** They omit TOPAS, which rebuilds its peak buffer once a width moves past `aberration_range_change_allowed` (`docs/practice.md:26`, marked checked; also `docs/wp/2045-…md:131`). They also omit BGMN ("not documented", `practice.md:31`). The conclusion survives, since TOPAS acts rather than reports. The row says "no number is new" (`_audit.py:966-967`). By `generality.md` § The rule, a factor is a threshold of its own, and 1× is a choice: the WP measured that 0.5× fires on two normal `profile` stages (WP Context, "The staleness test, measured", third bullet). The row should cite that. The threshold also inherits `WINDOW_AREA_TOL`, a tier-3 constant (`_audit.py:1873`), so retuning that constant moves this threshold without reopening this row. Finally, `approved="2026-10-25"` covers the evidence text, which includes the stage-selection rule (item 4). The WP calls that rule "a session judgement … for the maintainer to reverse" (WP Context, "Which stages the code reports"), so the date overstates what was ruled. | weak (grounds incomplete; approval overreach) |
| 6. Dataset families | "the four acceptance protocols' stages reach 1.73 % against 2 % … 73 % (WP-2047 probes 3 and 5, one family)" (`_audit.py:967-970`) | **Silent:** four unrelated families: SRM 660c LaB6, the fluorapatite tutorial, cpd-1a and 11-BM NAC. This is held by `tests/test_window_domain.py:458`. The reference is the windows sized afresh, which is arithmetic, not a certified value. The row quotes 1.73 %, which is the largest loss at any iteration (probe 3). The code tests the answer, where the largest is 1.61 % (WP table; the test's docstring). So the true margin is 1.24×, not 1.16×. **Fires:** one real family (QPA round robin, cpd-1b), and only under a schedule the test monkeypatches back to pre-WP-2045 (`tests/test_acceptance_sequential.py:224`). That test reads the field from the `stage_end` event, not the diagnostic. The diagnostic itself fires only on synthetic LaB6 (`tests/silence.py`, `tests/test_window_loss.py:76`). The reference for "wrong" is the independent fit's own result, which verifies and does not validate. The rule's clause on guards that ordinary fits never trigger allows keeping it on a named injected case, and the row names one. | holds, at the floor |
| 7. What says it fired | the code's `value` = `StageResult.window_loss` | The code, `StageResult.window_loss`, `NodeMetrics.window_loss` and the `stage_end` event's `window_loss`. | holds |

Evidence that would change the verdict: a real stage before a closing stage with a loss between 2 % and 73 % whose answer the closing stage repairs, which would make this warning a false alarm.

Author: the row now names TOPAS and BGMN, cites 0.5× firing, quotes the 1.24× margin at the answer and the coupling to `WINDOW_AREA_TOL`, marks the stage selection unruled, and narrows the approval to the report and its threshold.

**`STAGE_WINDOWS_STALE.suggestion` (suggestion, one site), `src/rietx/_audit.py:3825-3831`**

**weak.** Of the suggestion's two sentences, only the second has measured support. The first prescribes one remedy, and the one other stale stage measured had already followed that remedy.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "names the order the shipped plans already take, scales and cell before widths and axial terms" (`_audit.py:3826-3827`) | It points the reader at one remedy: "Start this stage closer: refine scales and the cell before the widths or the axial terms, or seed the scales. On the case measured, a further stage from this answer ran further away." (`refine.py:7378-7381`) | agrees |
| 2. Kind | `ambiguity=3` | Kind 3 may suggest, as with the series-discontinuity precedent. | agrees |
| 3. Case against | none given | (a) The only other stale stage measured, the calibrate guide's `sample_profile` at 12.1 %, came after scales and cell, so this advice would not have applied to it. (b) A FullProf user facing windows that are too narrow widens them with `Wdt` (`practice.md:29`). rietx has the matching knob, `Stage.window_slack_deg`, declared "by fits whose start may sit far from the data" (`schemas/plan.py:212-216`). The suggestion does not mention it, and it is unmeasured either way. (c) "Or seed the scales" has no evidence. | real case |
| 4. Case for | "WP-2045's re-solve from the runaway went from axial_sl 558 to 4114" (`_audit.py:3827-3829`) | Verified: `docs/wp/2045-…md:121-125` ("A re-solve after the runaway does not repair it … 4 114"). That supports the second sentence only. For the first, whether reordering or a closer start cures a stale stage: none given. The order itself is McCusker et al. 1999 (`strategy/staged.py:3-5`), but that cites plan order in general, not this fault. | partial |
| 5. Tier | tier 3; grounds "The stage's own act is the cause, so the remedy is the plan's order." (`_audit.py:3830`) | Tier 3 is right. The grounds do not follow: what fixed the runaway was the tolerance schedule (WP-2045) and windows that follow the parameters (WP Context, "The prototype, measured"). Plan order did not fix it. | fails (grounds) |
| 6. Families | none given beyond the hostile pair | One family for the warning sentence. Zero for the remedy. | weak |
| 7. What says it fired | n/a | `Diagnostic.suggestion` on `STAGE_WINDOWS_STALE` | holds |

Evidence that would change the verdict: the hostile stage, or any stale stage, rerun under the suggested order (or with `window_slack_deg`), with the loss and the answer reported.

Author (fails): the suggestion now says only "refit from starting values nearer the data, and do not polish this answer", the second half measured; the row's grounds name the start as the one lever the measured steps depend on (both were the stage's first accepted step, probe 2) and say the remedy is unmeasured.

**`OTHER_RECORD_FIELDS` + `rietx.schemas.results.StageResult.window_loss`, `src/rietx/_audit.py:486`**

**holds.** It is a measurement with an honest `None`, and the action keyed on it has its own row. Two small gaps follow.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "a measurement, so the metrics and not `NodeAction`" (WP Tasks) | Nothing on its own. It feeds item 1, which carries its own row. `None` means "nobody looked" (`schemas/results.py`, field docstring), and the writers are named: `refine.py:4786`, `multi.py:1664-1686`. This meets the root CLAUDE.md rule that a new field names its writers. | holds |
| 2. Kind | n/a (no action) | A joint fit records the **worst** histogram (`multi.py:1686`), which is a small choice. It is conservative for a threshold, but the record and the message lose *which* histogram was stale. | minor |
| 3. Case against listing it as no-action | none found | none found | — |
| 4. Case for treating it as an action | none found | none found | — |
| 5. Tier | n/a | The field's help (`help.py:5243-5244`) says "Above the stage's window fraction it feeds `STAGE_WINDOWS_STALE`". It omits that only the last stage, or the stage before closing, is reported. A user who sees 12 % on an earlier stage with no warning has no explanation for the silence. The value also leaves out magnetic and extra-peak staleness (`forward.py:4239`), and the help does not say so. | weak (help text) |
| 6. Families | four protocols plus the hostile pair | as in item 1 | — |
| 7. What says it fired | the field itself | — | holds |

Evidence that would change the verdict: none expected. Fixing the help text closes the gaps.

Author: the help now states the stage selection and that magnetic windows and extra peaks are not measured. Naming the joint fit's histogram is declined here (code review's finding too): it needs a new field.

**Which stages are reported (`refine._window_loss_diagnostics`, `src/rietx/refine.py:7360-7362`; no row of its own)**

**weak.** Each side rests on one fit. The cut between "one refit does not repair" and "several refits do" comes from stage position and name, not from anything measured about repair.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides (it reports less) | "reports only the stages whose answer reaches the result with at most one refit" (WP Context, "Which stages the code reports") | It suppresses the warning on every stage but the last, plus the one before it when the last is named `CLOSING_STAGE_NAME` (the closing stage's name). The caller must compare each `window_loss` against `window_area_tol` themselves to see an earlier stale stage. A hand-run `run_stage` always reports its one stage (`refine.py:5758`). | agrees |
| 2. Kind | not stated | Kind 3: a choice about what to report. | — |
| 3. Case against suppressing | "The alternative is to report every stage, which warns on the calibrate guide's correct fit" (WP Context) | Measured: none found. The author's premise, "refitted … by every stage after it" (`refine.py:7375-7376`), is structurally true, because staging within a plan is cumulative (`refine.py:5129`). But "repaired" rests on one synthetic fit (`examples/guides/calibrate.py`: synthetic LaB6 and CeO2). The same evidence base shows that one refit from a runaway does *not* repair it (`docs/wp/2045-…md:121-125`). In that case the refit runs further and would likely be stale itself, so the last stage would fire. No case is known where an earlier stale answer survives to the result while the last stage stays silent. | none measured |
| 4. Case for suppressing | the calibrate guide's `sample_profile` at 12.1 %, "size within its esd of the truth" (row evidence, `_audit.py:970-972`) | One synthetic fit. Under the five-channel attention rule (`generality.md` § "Attention is a cost", clause 1), a warning on a correct fit is a real cost. The number stays in the field, so nothing is lost. | one case |
| 5. Tier | not stated. The WP says "for the maintainer to reverse" | Tier 3. It is folded into item 1's evidence, and so it is covered by that row's `approved` date without a ruling (see item 1, question 5). | weak (unratified) |
| 6. Families | one each way | The suppression has one synthetic case. The inclusion of the stage before closing has one real family (QPA round robin). | weak |
| 7. What says it fired | — | Nothing records that a stage was over its tolerance and suppressed. The field help does not mention the suppression (`help.py:5243`). | gap |

Evidence that would change the verdict: a stage before the last one, on real data, over its tolerance, with the answer measured after the later stages. A repair on a second family would support the rule. A surviving error would reverse it.

Author: marked unruled in the row and handed to the maintainer in this entry; the help now mentions the suppression. Since a review fix, a user's own last stage named "closing" no longer counts as the closing stage.

**`forward.rewindow` sizing from drawn widths, and `fcj.fcj_node_counts` (no row of its own)**

**holds** for its use. It computes a measurement and moves no fitted value, and its agreement with a fresh compile is measured. **weak** as tier-1 evidence: the strongest measurement lives in a probe script, not a test.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "reads the peaks the forward model draws … where the compile reads its own width estimate, so the two agree to that estimate's ~1 %" (`forward.py:4236-4238`) | It decides the reference windows the loss is measured against. Three sub-rules differ from `compile_model`. (a) Widths come from `phase_peaks`, which returns the widths the forward model actually draws, not the compile's own estimate. (b) The axial floor is applied when "any `fcj_n`" (FCJ node count) is non-zero (`forward.py:4250`), where the compile asks "axial free" (`forward.py:3797`). When a stage ends exactly at zero with no nodes, this can only make the loss read low, never fire falsely. (c) The magnetic family and the extra peaks keep their frozen windows (`forward.py:4239`), so their staleness reads as zero. | agrees, with the gaps noted |
| 2. Kind | n/a: a numerical setting | Under the B10 ruling (2026-10-19: a numerical setting is tier 1 once a test bounds its error over every input it claims to handle) | — |
| 3. Case against | none given | (c) above is the one material gap: the field's number reads as an answer about magnetic windows that nothing measured. The scalar and vectorised node counts can land an ulp apart on a ceiling (`fcj.py:157-160`). That affects only this measurement and is negligible at the measured margin. | minor |
| 4. Case for | "agrees with a fresh compile to six decimals" at every stage answer (WP Context, "The report, measured"); "80 %" of its time was the scalar node call (`fcj.py:156-157`) | Measured in `docs/wp/2047-batch/probe5.py` on four families plus the hostile pair. The hostile pair is the same family as cpd-1a, so that is four families, not five. This is verification and validates nothing (Rule 2). | strong |
| 5. Tier | none stated | Tier 1 needs a committed test with a stated bar over the claimed domain. The committed tests cover synthetic LaB6 only: \|loss\| < 1e-4 at the compile's own values (`tests/test_window_loss.py:60`), and agreement with a fresh compile to 1e-3 on two moves (`:76`). No test pins `fcj_node_counts` to `fcj_node_count`. Until a test carries the probe's bar, the `WINDOW_MIN_DEG` precedent puts it at tier 3 under B10 option 2 (`_audit.py:1896-1904`). | weak |
| 6. Families | "five families" (dispatch) | Four, counted by laboratory, instrument and material. The reference is a fresh compile, which verifies. | overstated by one |
| 7. What says it fired | n/a | n/a | — |

Evidence that would change the verdict: a test asserting `fcj_node_counts` equals `fcj_node_count` element by element over a grid, plus the probe's per-stage agreement on the four protocols moved into `tests/test_window_domain.py`. Both together would support tier 1.

Author: `test_the_vectorised_node_count_is_the_compiles` now pins the two counts equal over 3 977 points in eight cases (all equal). The per-stage agreement on the four protocols stays in probe 5; moving it into `test_window_domain.py` is left to WP-2051, which rebuilds the resizing anyway.

**Tests** (macOS arm64, `[dev]`, Python 3.12, run alone). Fast selection on
the final source tree: 11 788 passed, 272 skipped, 28 xfailed, and 1 failed,
this entry's own heading form, fixed after. The added fast tests are
`tests/test_window_loss.py`'s 20 cases, 1.70 s in all on this run
(`tests.added_test_times`; the slowest, a two-stage fit, 1.00 s), plus one
silence pair and the parametrised audit and help rows the new names add;
main's own count was not re-measured, which is CI's job. Slow: the two
hostile-pair tests and the four `test_no_protocol_stage_ends_on_stale_windows`
rows, 6 passed in 15 s; the new hostile test was made to fail once with the
measurement stubbed to zero. The full selection was not run: the change reads
the model after each solve and moves no fitted number (probe 6's Rwp equal
with and without it, and the darwin/arm64 bit-identity goldens in the fast
selection pass after the review moved the compile's window arithmetic into a
shared helper).

**Next.** WP-2051: profile one resize, then vectorise, then a tapered edge,
then probes 7 and 8 again for the maintainer's ruling. Open: whether the
stage selection stands.

- **2026-10-24** — filed by WP-2045's ruling session, on the maintainer's
  ruling ("5 now, 4 as own WP"). No open WP owns window rebuilding:
  2017 measures tier-3 thresholds and does not change the window rule, and
  1122's v2 fence covers shape reuse, not when a window is rebuilt. Next:
  the staleness test, then the design brief.
