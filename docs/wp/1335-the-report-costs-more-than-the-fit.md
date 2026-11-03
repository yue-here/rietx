# WP-1335 — the report costs more than the fit

Milestone: unscheduled · Status: ✅ 2026-11-03 — a stage report costs about a third less on NAC and a sixth on the #250 shape, bit-identically on both, and its cost is in the event log (PR #1346); `summary(report=)` builds one report (PR #259); no further cut, by ruling; a joint fit's `stage_reports=` went back to the maintainer as a question (PR #1364)
Track: A long run is not one fit
Depends on: —

## Goal

Building a report stops dominating the wall clock of a refinement. The
per-phase strain analysis pays for itself only where it can produce an answer,
a caller that wants both the summary and the structured report builds one
report, and the cost of `stage_reports=True` is visible in the event log
rather than inferable from a wall-clock discrepancy.

## Context

Three issues from the same campaign, all measured, all in the report path
(#245, #250, #251). Together they are the reason a 4 s fit takes 112 s to
deliver.

**#250 — `analyse_strain` pays the expensive part before the early-out.**
`report/strain.py::analyse_strain`'s per-phase loop calls
`_strain_errors(model, values, ip)` **first** (line 268), and only afterwards
computes `live` / `n_used` and takes the guard (line 282):

```python
if n_used < max(STRAIN_MIN_REFLECTIONS, len(basis) + 1):
    out.append(StrainAnalysis(...))
    continue
```

`_strain_errors` runs `_GAUSS_NEWTON_ITERATIONS = 4` iterations per phase,
each a dense `npts × 2·n_group` `np.linalg.lstsq` with `npts = len(model.tt)`
— the full pattern. **The issue's premise that the guard does not need its
output is wrong on the tree**: `_strain_errors` returns `(d_lambda, weight)`,
`weight` feeds `live` (the √weight leverage cut just below the call), and
`live.sum()` is the `n_used` the guard tests. So the hoist is not a line move.
What the guard needs is the per-reflection leverage weight, a squared column
norm of the design; the question is whether that norm can be had without the
four Gauss-Newton solves that follow. If the design columns are built once and
the norms taken before any `lstsq`, the guard hoists; if the weights are
re-formed each iteration at the updated Λ, it does not, and the saving is one
iteration's cost rather than four. Establish which before claiming the number.
Measured on a ~49 000
point three-phase fit, timed end to end against the fit's own `wall_s`:

| | end to end | fit only | ratio |
|---|---|---|---|
| run 1 | 112.75 s | 4.14 s | 27.2× |
| run 2 | 112.43 s | 4.28 s | 26.3× |

Under `cProfile`, `np.linalg.lstsq` alone is 120.1 s of 138.8 s profiled over
80 calls. The accidental control is a joint fit of the same material at
1.11–1.14×, because `MultiHistogramRefinement` has no `.report()` and none of
this executes (that gap is 1341).

**A question #250 asks rather than asserts, and it should be answered rather
than assumed:** should a phase with **no free structural parameter** get the
pass at all? Two of the three phases above were scale-only and received the
full Gauss-Newton treatment. The docstring shows the neighbouring case was
decided deliberately — *"Runs whether or not the phase already carries a
`microstrain` block: with one, the question becomes 'is there anisotropy
*left*', which is how the result gets checked after refining it"* — and that
argument is about *refined* microstrain. Whether it extends to a phase with
nothing free is a real design call.

**#251 — `summary()` offers no way to reuse the report it builds.**
`Refinement.summary(*, deliverable, plot, plan)` calls
`report = self.report(plan=plan)` (`refine.py:1935`), formats it, and returns
only the string. There is no `report=` parameter and no accessor, so

```python
summary_text = ref.summary(deliverable=...)
report = ref.report(plan=plan)
```

runs `build_report()` twice, and with it `analyse_strain`. In a batch of a few
hundred patterns that doubling is the dominant cost of the run. Three shapes
were offered and the first is the smallest: `summary(..., report=None)`
accepting a precomputed report; a `summary_with_report() -> (str, Report)`; or
caching on the instance keyed by plan.

**#245 — `stage_reports=True` costs 6.5× the fit, and falls outside the stage
brackets.** On `tests/data/11BM_NAC.fxye` with `examples/nac_11bm.py`'s own
setup, single-threaded, median of 3:

| | median | Rwp |
|---|---|---|
| `stage_reports=True` | **1.923 s** | 0.140398 |
| `stage_reports=False` | **0.296 s** | 0.140398 |

Rwp agrees to six decimals — the refinement is bit-identical, so this is pure
reporting overhead, exactly as WP-1003/1064 promised. `cProfile` on one
`stage_reports=True` fit (2.369 s cumulative): `_stage_report` 1.767 s
(**75 % of the fit**), of which March-Dollase texture 0.932 s and Stephens
strain 0.593 s, against `_run_stage` at 0.555 s (23 %). The texture and strain
analyses re-run at **every** stage — five times here — and each costs more
than the optimisation step it reports on.

**The event-log half is the part that misled a consumer.** Measured with an
`EventStream` on the same fit:

| | wall | Σ(`stage_start`→`stage_end`) | `fit_start`→`fit_end` |
|---|---|---|---|
| `stage_reports=True` | 2.044 s | 0.225 s (**11 %**) | 2.042 s (99.9 %) |
| `stage_reports=False` | 0.440 s | 0.223 s (**50 %**) | 0.438 s (99.5 %) |

The bracketed time is essentially identical in both rows — it is the solve.
The log is not missing anything (`fit_start`→`fit_end` covers ~100 % of wall
clock either way); the trap is that **summing stage durations and calling the
result "fit cost" understates it by ~9×**, and the reporter's own aggregator
walked into exactly that. A span around the stage-report work would make the
cost countable rather than inferable. Note that `EventKind` is closed and a
new kind is an `EVENT_SCHEMA_VERSION` bump (`history/events.py`), so whether
this is a new kind or a field on an existing one is a decision to take.

**No behaviour here is wrong.** It is a cost invisible until profiled, on a
flag whose name suggests it only adds output. The reporter turned it on for
every fit of a multi-hundred-pattern batch because it seemed the diligent
choice.

## Non-goals

- The solver's own cost, and the exhausted-budget stop rule — 1334.
- A joint fit's `stage_reports=` (from 1341): offered on top of this WP once
  the per-report cost is cut far enough. *Superseded in part 2026-11-03:* the
  cut stopped at about a third by the 2026-11-02 ruling, so whether that is
  far enough is a call, and the item has no owner (WP-2028's Non-goals point
  back here). The question is in the 2026-11-03 handover entry.
- Removing the per-stage report. WP-1058's rule stands: **the report at every
  stage boundary, because a run's last state is routinely its least
  informative.** This WP makes it cheap and countable, not optional-by-stealth.

## Tasks

- [x] Separate the leverage weights from the Gauss-Newton solve in
      `_strain_errors` so the reflection-count guard runs before any `lstsq`,
      if the weights admit it; measure the recovered fraction on the #250
      shape either way.
      **Done 2026-11-02, in the bound form.** The weights are re-formed every
      iteration at the updated Λ, so the exact count is not known before the
      solves. An upper bound is: a reflection with no leverage at the start
      has none later. `_strain_errors(min_reflections=)` returns the first
      iteration's weights with no solve when that bound is under the floor.
      Recovered fraction on the #250 shape: about zero, by construction. A
      solve costs npts × (2·n_group)², and a phase under the floor has fewer
      than 16 groups. The phases that cost the 120 s pass the floor. Zero-row
      trimming of the design was measured too and dropped: the windows cover
      75-100 % of the rows on LaB6+cBN and NAC, and trimming moved Λ by up to
      1.8e-7 relative.
- [x] Decide, and write down, whether a phase with no free structural
      parameter is analysed at all — the docstring argument covers refined
      microstrain and does not obviously extend.
      **Decided 2026-11-02: analysed.** Settled by Claude under the module's
      written rule (`report/strain.py`'s docstring: the subject is the
      specimen, not the residual). A held width model is where a
      directional misfit has nowhere else to show, and acting on it is the
      Layer-2 veto's call. Written into `analyse_strain`'s docstring.
- [x] `summary()` accepts a precomputed report, or returns one; the doubling
      goes away by a documented route rather than by a caller's workaround.
      **Landed in PR #259**: `summary(report=)`, refusing `plan=` beside it;
      the test counts builds at `build_report`, the seam both routes share.
- [x] A span (or field) covering the stage-report work, so a caller summing
      events sees it; decide the `EVENT_SCHEMA_VERSION` question deliberately.
      **Done 2026-11-02: a field.** `fit_end.stage_report_seconds` is the
      wall time the rungs took, absent when no rung was built, and `rietx
      events` adds it to the fit line. Settled by Claude under
      `history/events.py`'s written rule: a new key on an existing kind does
      not bump `EVENT_SCHEMA_VERSION`, a new kind does. A span kind would
      have been the first kind added for timing alone, and WP-1024's
      precedent reused existing kinds with added keys.
- [x] Document what `stage_reports=True` costs, roughly, where the flag is
      documented — the reporter would have sampled rather than enabled it
      everywhere had the tax been stated.
      **Done 2026-11-02**: `Refinement.fit`'s docstring (its "≈2.5×" gone),
      the manual's `reference/report.md` § Reports at every stage, and the
      event tables in `reference/refinement.md` and `reference/cli.md`.
- [x] Tests: a counter over `build_report` across a `summary()` + `report()`
      pair asserts **1**; a phase below the reflection floor costs no solve.
      The counter landed with PR #259 (`tests/test_termination_view.py`); the
      floor test and the bit-identity oracles are `tests/test_report_cost.py`.
- [x] Skill: `references/batch.md` — the row on when to enable
      `stage_reports`, and the row warning that per-stage sums are not fit
      cost.
      Both rows live elsewhere since the skill was split: the cost row in
      `references/series.md` (re-measured) and the sum row as § 9c.11 of
      `references/batch-operating.md` (now naming the new field).

## Acceptance

The #245 fixture's `stage_reports=True` / `False` ratio falls well below 6.5×
with Rwp bit-identical; a `summary()` + `report()` pair builds one report.

```sh
.venv/bin/python -m pytest tests/test_report_apply.py tests/test_termination_view.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #245, #250, #251 — rietx 1.3.0, `SCHEMA_VERSION` 0.16, `main` plus
  PRs #206 and #233, single-threaded, `tests/data/11BM_NAC.fxye`.
- Root CLAUDE.md § Numbers — quote wall clock as a range with its venv and
  platform, never as a figure.

## Handover log

- **2026-11-03** (close, PR #1364) — WP-1335 closes as it stands. All
  seven tasks were done and the acceptance was read as met on 2026-11-02. The
  one item still named as open, a joint fit's `stage_reports=`, is one of this
  WP's Non-goals, offered "on top of this WP once the per-report cost is cut
  far enough". The cut stopped at about a third by the 2026-11-02 ruling, so
  whether that is far enough is a call, not a task. The texts that said the
  joint fit waits for this WP to land now say the cut stopped and the call is
  open.

  *Done.* `MultiHistogramRefinement.fit`'s docstring and the manual's
  `reference/joint.md` no longer say "until WP-1335 lands". The docstring
  keeps the #245 figure as the issue's, in the past tense. The page drops
  its single 0.36 s figure: a report's cost is set by the pattern and its
  phases, from a fraction of a second on NAC to seconds on 49 000 points,
  times the pattern count. The `### Inherited` section was consumed and
  deleted. Its #245 timings are the issue's own record. Its WP-1341 entry is
  this question, also forwarded to WP-2028's `### Inherited`, whose Non-goals
  still send the item here. The narrative went to `docs/milestones/v1.11.md`.

  *Measured.* Nothing timed, since nothing that runs changed. `[dev]` venv,
  darwin arm64: the acceptance files with the docs and joint-fit tests
  (`test_report_apply`, `test_termination_view`, `test_docs_consistency`,
  `test_docs_versions`, `test_multi_histogram`, `test_joint_report`) gave 192
  passed. No test was added. Ruff clean, Vale 0 errors. The fast suite was
  not run, since the branch changes a docstring and prose only.
  `reader_output`: unchanged (exit 0).

  *Review.* `/code-review high --fix` found eight, no code bug among them,
  and fixed five. Fixed: the page's "fixed fraction of a second" contradicted
  the 2.4-2.9 s measured on 49 000 points; WP-2028's Non-goal pointed at a
  closed WP with no note (forwarded); the docstring named "the last handover
  entry" in a newest-first log, and quoted 0.36 s in the present tense; the
  record and the Status line said "a third" and "bit-identical" without the
  sixth on the #250 shape or the two fits it was checked on. Declined three:
  the older entries' pointers to `### Inherited` are dated history; this
  placeholder (filled here); and "the docstring keeps the #245 figure", still
  true after the fix.

  *Question for the maintainer.* Should a joint fit offer
  `stage_reports=` now, and if so, where does the work live? No open WP owns
  it: WP-2028's Non-goals give it to WP-1335, and WP-1335's Non-goals put it
  on top of this one. Three choices go with building it. (1) Whether the
  one-third cut is enough. The cost is opt-in and `fit_end` carries
  `stage_report_seconds`, the two grounds the 2026-11-02 ruling gave for
  stopping. Against that, a rung is still one report per histogram per
  stage. (2) The rung shape. `StageReport` has no histogram field, so it is
  either a list per stage of per-histogram rungs or a new field. (3) Which
  compile a rung reads. `report(h)` moved off the stage's own compile
  because Layer 0 read cut peak tails as unmatched peaks (WP-1341). A single
  fit's rungs do read the stage compile, so a joint rung would carry that
  artefact after a width stage, or would pay a fresh compile per histogram
  per stage.

  *Next.* The maintainer's answer to the question above. If it is "offer
  it", file it as its own WP or fold it into WP-2028. The build starts from
  `MultiHistogramRefinement.report(h)` and `_run_plan`'s stage boundary.

- **2026-11-02** (rulings, PR #1349) — The stage reports' cost is not
  cut further. The two cuts left were fewer Gauss-Newton steps in the
  Stephens strain arm on the intermediate rungs, or a coarser March-Dollase
  grid. Either would make the rungs' numbers less accurate than the final
  report's. Asked in chat on 2026-11-02, the maintainer answered "no idea".

  *Settled by Claude: no further cut.* Grounds: root CLAUDE.md's companion
  rule, the report at every stage boundary, exists because a run's last state
  is routinely its least informative. A cheaper, less accurate rung would
  undercut the reason the feature exists. The cost is also opt-in:
  `stage_reports` is off by default, and PR #1346 put the rungs' wall time in
  `fit_end.stage_report_seconds`, so a caller sees what it pays.

  *Acceptance.* Its "well below 6.5×" is read as met by PR #1346's measurement:
  NAC with its seven stage reports at 4.7-5.7× the bare fit, CPU seconds on a
  shared machine (the entry below has the conditions), Rwp and every report
  field bit-identical. The second half, a `summary()` + `report()` pair
  building one report, landed with PR #259.

  *Next.* A joint fit's `stage_reports=` (from WP-1341, in `### Inherited`)
  is the one open item. `MultiHistogramRefinement.fit` declines it today;
  offering it means one rung per histogram per stage, built from
  `MultiHistogramRefinement.report(h)` at `_run_plan`'s stage boundary, and
  deleting the two sentences in that docstring and in
  `docs/docs/reference/joint.md` that say why it is declined.

- **2026-11-02** — a stage report costs about a third less, with every
  report number unchanged, and its cost is now in the event log. Measured on
  this machine against `main`, a NAC fit with its seven stage reports went
  from 7.1-8.3× the bare fit to 4.7-5.7×. On the 49 000-point LaB6+cBN fit,
  the shape #250 reported, one report went from 2.85-3.13 s to 2.41-2.85 s of
  CPU, so there the cut is about a sixth. What remains is arithmetic the
  answers are made of: the Stephens strain arm's four Gauss-Newton solves,
  each a dense least-squares problem over the whole pattern, and the
  March-Dollase grid's 121 powers per angle. Cutting either further would move
  rung numbers, and that is a reader-output change for the maintainer. A
  `fit_end` now carries `stage_report_seconds`, so a caller summing events
  sees the rungs' share instead of inferring it. PR #1346.

  *Done.* Task 1 in its bound form: `_strain_errors(min_reflections=)` returns
  the first iteration's leverage, with no solve, when fewer reflections than
  the floor have leverage and tanθ > 0. The weights are re-formed every
  iteration, so only that bound is known before the solves. Task 2: a phase
  with no free structural parameter is analysed, settled by Claude under
  `report/strain.py`'s own rule that the subject is the specimen; written into
  `analyse_strain`'s docstring. Task 4: a field, not a kind, settled by
  Claude under `history/events.py`'s written rule (a key on an existing kind
  does not bump `EVENT_SCHEMA_VERSION`); `rietx events` prints it on the fit
  line. The savings beyond the task list, each bit-identical:
  `strain_basis` and `zone_boundary_candidates` are cached per group (both
  are exact-rational eliminations repeated per phase per stage); the texture
  grid is scored a block of r at a time and raises each distinct cos²α to
  its power once; a rung's `_build_result(with_geometry=False)` skips the
  bond search, which no `StageReport` field reads. Docs: `fit`'s docstring
  lost its "≈2.5×", the manual's report and event pages and the skill's
  `series.md` row and § 9c.11 carry the re-measured cost and the field.

  *Measured.* `[dev]` venv, darwin arm64, CPU seconds (`time.process_time`)
  with BLAS and kernel threads pinned to 1, on a machine at load average
  30-110 from other runners' suites, so wall clock was unusable and every
  figure is a range. Bit-identity: every field of the seven NAC rungs, the
  NAC final report and the LaB6+cBN report, dumped as JSON, is byte-identical
  to an `origin/main` snapshot (`cmp`). Recovered by the floor guard on the
  #250 shape: about zero, by construction, since a solve costs
  npts × (2·n_group)² and a phase under the floor has under 16 groups.
  Trimming the design's all-zero rows was measured and dropped: the windows
  cover 75-100 % of the rows, and trimming moved Λ by up to 1.8e-7 relative.
  The fast suite did not run locally: the machine's suite lock had six
  waiters ahead of it, so CI's fast matrix is the gate. A targeted selection
  of 23 files reaching the changed modules, on the tree merged with
  `origin/main` (e4d4f044c), gave 830 passed, 2 xfailed and 3 failed. The
  three (an audit row, the events page over its size cap) were fixed and
  their files rerun green, 124 passed. This session added 17 cases from 9
  test functions, all in `tests/test_report_cost.py`: 1.25 s together
  locally, the slowest 0.52 s. The full selection did not run: the change
  claims bit-identity, checked directly on two real-data fits.
  `reader_output`: unchanged.

  *Review.* `/code-review high --fix` found seven. Fixed four: the two floors
  shared a name, the cache docstrings quoted single figures, the manual's
  cancelled `fit_end` omitted the key, the skill claimed bit-identity
  everywhere rather than where measured. Declined three: the floor guard's
  saving is near zero (kept, because the task and its test ask for it and
  it costs one comparison); `_stage_report_seconds` is instance state that a
  kept Le Bail pass does not restore (no reader); the blocked texture grid's
  bit-identity rests on numpy summing a row as it sums a 1-D array (the
  oracle test runs on every CI platform, which is the check). The
  generality judge passed the audit row's `invariant` tier and found the
  oracle test never cut the grid into blocks of more than one r; it now
  does, at 50.

  *Gotchas.* `n_reflections_used` on a phase under the floor is now counted
  at the fitted widths rather than four steps on; the two differ only where
  a reflection's leverage crosses the 1e-6 relative cut between them, and
  were equal on the brucite fixture. The events page
  (`reference/refinement.md`) sits 11 characters under its 50 000 cap, so
  `stage_report_seconds` is named on the report page, not in the events
  table's `fit_end` row. Symmetry-equivalent texture axes cannot
  be merged without changing which of them the report names, since their
  scores tie to the last bit only by accident.

  *Next.* (1) Offer `stage_reports=` on a joint fit (Inherited, from 1341):
  the cut is a third, so the per-histogram multiple the docstring warns of
  is smaller but not gone; decide whether that is enough. (2) If the
  maintainer wants rungs cheaper still, the levers move rung numbers: fewer
  Gauss-Newton steps on intermediate rungs, or a coarser r grid there. Each
  is a reader-output change and goes to the maintainer first.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #245,
  #250, #251). Verified on the tree that `analyse_strain` calls
  `_strain_errors` before its early-out and that `summary()` calls
  `self.report(plan=plan)` unconditionally. Re-checked the same day: the
  issue's premise that the guard does not need `_strain_errors`' output is
  wrong on the tree — `n_used` comes from the `weight` it returns — so the
  hoist is a separation, not a line move. Task 3 landed the same day as PR
  #259 on its own branch, being the one task here that needed no
  measurement.
