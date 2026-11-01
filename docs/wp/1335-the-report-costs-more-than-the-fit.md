# WP-1335 — the report costs more than the fit

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P3 2026-09-23 — cost only: a report at 26× the fit it reports on

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

### Inherited

- **2026-10-23, from [1341](1341-a-joint-fit-has-no-report.md) (closed): a joint fit has a report, so this WP's Non-goals line about it is stale.** The line "Reporting for joint fits, which has no cost because it does not exist — 1341" predates `MultiHistogramRefinement.report(h)` (2026-10-12), which builds one histogram's Layer 0-2 report and pays the same per-report cost this WP cuts. The Inherited bullet from 1341 dated 2026-10-12 (offering `stage_reports=` on a joint fit once the cost is cut) still holds. The joint report's remaining gaps are [2028](2028-a-joint-fits-guards-see-every-histogram.md)'s. Context's accidental control (the joint fit at 1.11-1.14×, "has no `.report()`") no longer holds: since 2026-10-12 the joint arm pays the report cost too.
- **2026-10-02, from the issue triage (issue #245): the cost to cut is a fixed
  ~0.36 s per stage report, and a docstring still quotes the old ratio.** The
  reporter re-measured on `3d1a6feb` (2026-09-29; `11BM_NAC.fxye`, 5 stages,
  median of 3, BLAS pinned to 1): `stage_reports=False` 0.331 s,
  `stage_reports=True` 2.136 s, 6.45×. The per-report cost is unchanged from
  the docstring's 0.33 s; the fit got about 3× faster, so the multiple grew
  and will keep growing as fits speed up. *Checked at `ca9bda29`*:
  `Refinement.fit`'s docstring (`refine.py:3376`) still says "a trajectory
  costs ≈2.5× the fit". Correct it in the same change that cuts the cost.

- **2026-10-11, from the issue triage (#245): the reporter's three paired
  timings of 2026-09-04 are not carried here.** Neutron CW, neither a
  March-Dollase nor a Stephens block, 3 292 points: 2.81 s against about
  0.55 s (5.1×). X-ray, one phase, isotropic broadening, 13 997 points: 2.92 s
  against 0.80 s (3.65×). X-ray with March-Dollase and a Stephens block,
  48 001 points: 298.22 s against 5.35 s (55.7×), with another arm at about
  26× on about 49 000 points. The reporter withdrew "scales with N_points",
  since the 13 997-point case sits below both others. They suspect the
  per-reflection texture and strain analysis at every stage, not isolated; a
  pair differing only in the Stephens block would isolate it. The same comment
  measured the bracketed `stage_start` to `stage_end` time at 2.36 s of the
  298.22 s, and says `y_obs`, `y_calc`, background and ticks are filled whether
  or not `stage_reports` is on. Checked against the tree at 7d9be3cb:
  `refine.py:4115` still says "≈2.5× the fit", `_strain_errors` is still called
  first (`report/strain.py:301`), and `references/series.md` in the skill
  already gives 6.5×.

- **From WP-1341 (2026-10-12): the joint fit waits on this WP for
  `stage_reports=`.** `MultiHistogramRefinement.fit` declines it, because one
  rung there is a report per histogram per stage, so the joint trajectory
  would cost this WP's fixed ~0.36 s times the histogram count. The reason
  is written in that method's docstring and in `docs/docs/reference/joint.md`. Once the
  per-report cost is cut, offering it there is a small change on top:
  `MultiHistogramRefinement.report(h)` already builds one histogram's report,
  and `_run_plan` has the stage boundary. Those two sentences go when it is
  offered.

## Non-goals

- The solver's own cost, and the exhausted-budget stop rule — 1334.
- Reporting for joint fits, which has no cost because it does not exist —
  1341.
- Removing the per-stage report. WP-1058's rule stands: **the report at every
  stage boundary, because a run's last state is routinely its least
  informative.** This WP makes it cheap and countable, not optional-by-stealth.

## Tasks

- [ ] Separate the leverage weights from the Gauss-Newton solve in
      `_strain_errors` so the reflection-count guard runs before any `lstsq`,
      if the weights admit it; measure the recovered fraction on the #250
      shape either way.
- [ ] Decide, and write down, whether a phase with no free structural
      parameter is analysed at all — the docstring argument covers refined
      microstrain and does not obviously extend.
- [x] `summary()` accepts a precomputed report, or returns one; the doubling
      goes away by a documented route rather than by a caller's workaround.
      **Landed in PR #259**: `summary(report=)`, refusing `plan=` beside it;
      the test counts builds at `build_report`, the seam both routes share.
- [ ] A span (or field) covering the stage-report work, so a caller summing
      events sees it; decide the `EVENT_SCHEMA_VERSION` question deliberately.
- [ ] Document what `stage_reports=True` costs, roughly, where the flag is
      documented — the reporter would have sampled rather than enabled it
      everywhere had the tax been stated.
- [ ] Tests: a counter over `build_report` across a `summary()` + `report()`
      pair asserts **1**; a phase below the reflection floor costs no solve.
- [ ] Skill: `references/batch.md` — the row on when to enable
      `stage_reports`, and the row warning that per-stage sums are not fit
      cost.

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

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #245,
  #250, #251). Verified on the tree that `analyse_strain` calls
  `_strain_errors` before its early-out and that `summary()` calls
  `self.report(plan=plan)` unconditionally. Re-checked the same day: the
  issue's premise that the guard does not need `_strain_errors`' output is
  wrong on the tree — `n_used` comes from the `weight` it returns — so the
  hoist is a separation, not a line move. Task 3 landed the same day as PR
  #259 on its own branch, being the one task here that needed no
  measurement.
