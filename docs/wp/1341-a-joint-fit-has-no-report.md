# WP-1341 — a joint fit has no report

Milestone: unscheduled · Status: ✅ 2026-10-23 — a joint fit writes events, can be stopped, carries a convergence figure and gets a three-layer report per histogram (PRs #926, #937); what its guards still cannot see went to WP-2028, the fresh compile to WP-1421
Track: Render what the fit already knows
Depends on: — (1312 soft: it exercises and audits the joint fit; 1335 soft: the
report path this one gains should already be cheap; 1344 soft: it sorts each
diagnostic into per specimen, per histogram or per fit, and decides where a
per-histogram finding lives, and this report renders that)

## Goal

A converged multi-histogram refinement can be inspected: it emits events, it
carries a convergence figure, and — for whatever part of the report path is
genuinely histogram-agnostic — it reports. Where a quantity has no agreed
definition across histograms, the WP says so on the record instead of leaving
a `None` that reads as an oversight.

## Context

From issue #252. `MultiHistogramRefinement`'s entire public surface is:

```python
>>> [x for x in dir(rx.MultiHistogramRefinement) if not x.startswith('_')]
['fit', 'fitted_instruments', 'fitted_structures', 'n_histograms']
```

Three consequences, measured on a converged two-histogram fit (X-ray +
neutron, 41 free parameters, Rwp 0.088, GoF 1.47):

1. **No `.summary()` and no `.report()`** — `hasattr` is `False` for both. The
   whole Layer 0/1/2 path is unreachable for a joint fit: no `unmatched_obs`,
   no `off_region_chi2`, no `worst_absorption`, no `strain`/`microstructure`
   analysis, and nothing consuming a `Report` runs on one. The only
   diagnostics available are those on the raw result; in that fit, a single
   `BACKGROUND_ABSORPTION` — the same one the solo neutron fit reports.
2. **`fit()` has no telemetry parameters.** Its signature is
   `(self, data, *, mode='rietveld', plan='mccusker_default',
   two_theta_limits=None, weights=None)` — no `events=` and no
   `stage_reports=`. Where a solo fit leaves a per-stage record, a joint fit
   leaves nothing, and a diagnostic firing mid-refinement has nowhere to be
   seen.
3. **`result.statistics.max_shift_over_esd` is `None`.** Not a side effect of
   skipping the report — unpopulated on the multi-histogram result itself.
   Convergence quality can only be read from `status == "converged"`.

**The aside that makes the gap concrete**, and it is also 1335's control:
timing the same material three ways, a solo X-ray arm runs ~112 s end to end
against ~4 s of fitting, while the joint arm runs 6.8 s against 6.0 s — 1.1×
against 26×. **The joint fit is fast because none of the reporting machinery
exists for it.** A joint refinement is a first-class capability in the package
and a second-class citizen in its own reporting.

**The issue asks rather than asserts, and the asking is the useful part.** It
does not assume all three are oversights: `max_shift_over_esd` across
histograms with different point counts and weights may have no agreed
definition, and the report's region logic may be genuinely single-histogram in
its assumptions. **The maintainer answered on 2026-09-03: none of the three
is an intended limit; all are unimplemented.** What remains to write where a
reader meets it is the one definitional question inside (3) — what
`max_shift_over_esd` means across weighted histograms — under WP-1076's rule,
one rank up: **a declared name is a claim, and an honest empty state is
`None` with a reason, never a default that reads as an answer.**

The ordering the reporter says would help most from outside is (2), then (3),
then (1) — **an event log is the cheapest thing that makes a joint fit
debuggable at all.** Two things make (2) genuinely cheap: `events=` and
`cancel=` are already the shape `fit`/`run_stage`/`refine` take, and
`sequential.py` already showed how a multi-object run threads one stream
through per-member `data` fields without a new `EventKind` (WP-1016, which
added `series_index`/`…_label`/`…_n`/`…_pass`). A joint fit's histogram index
is the same move, and `EventKind` stays closed.

Some constraints that shape (1) and (3):

- **`bound_findings` is already multi-histogram-aware.** `_build_result` calls
  it with a `MultiParameterTable`'s bounds, and since WP-1434 with `cos=` and
  `esd=` too. So the guard path is not the obstacle; the report builder is.
  (Superseded in part 2026-10-12: the call has moved off `multi.py:477`.)
- **Sample broadening is shared and the size coefficient is not** (WP-1131):
  `MultiParameterTable` hands histogram h the factor λ_h/λ_0 for the size
  terms, so a microstructure report on a joint fit reads one specimen size
  across histograms and must not present per-histogram coefficients as
  separate findings.
- WP-1301's held-phase rule and `phase_support` are per compiled model, so a
  phase unsupported in one histogram and supported in another is a case the
  report has to have an answer for, even if that answer is "report it per
  histogram".

### What later work changed (folded from Inherited, 2026-10-12)

Each entry below arrived in this WP's Inherited section and was checked
against the tree at e1d19359 on arrival.

- **`STAGE_PATH_NOT_FREE` is not reported for a joint fit** (issue #803,
  triage 2026-10-08). PR #789 added the finding for a single histogram
  (`refine._fixed_literal_diagnostics`, fed one `ParameterTable`).
  `multi.DIAGNOSTIC_SCOPES` declares it `ABSENT`, so a joint plan naming
  `phases.0.atoms.2.x` on a special position, or `phases.0.cell.b` on a
  tetragonal phase, frees nothing and says nothing. Wiring it needs the
  helper to read each histogram's table, a finding that names which
  histogram's table holds the path fixed, and agreement with
  `_unreached_histogram_diagnostics` about what a literal matches. Done when
  a locked or tied literal reports once per path naming its stages, and
  #789's silence cases stay silent. Still true on arrival
  (`multi.py:255`). It is the task added below, landed 2026-10-12.
- **The joint fit judges support on the screen alone** (from WP-1523,
  2026-10-04). A single fit calls a phase seen when its scale is 3σ from zero
  (`refine._answer_significance`). A joint fit reads only `phase_support`,
  which on issue #481's blank frame reached 3.1-4.4σ once a released cell
  chased the noise. Whether the joint report takes the marginal test, and
  whether histograms combine in quadrature, is open. Still true on arrival
  (`multi.py:1297`). Not taken here; it went to WP-2028 at the close.
- **The joint runner runs the scale-B probe** (from WP-1534, 2026-10-04).
  `SCALE_B_INSEPARABLE` fires at top level and `DIAGNOSTIC_SCOPES` lists it
  as FIT. Nothing is left here but to render it, and `report(h)` reads only
  histogram h's own diagnostics, so that went to WP-2028.
- **The census of what `multi.py` re-derives is wider than its diagnostics**
  (from WP-1344, 2026-10-01). WP-1344 did not audit the other members that
  re-derive something `Refinement` derives. `_ticks` is the known case. The
  rule WP-1103 settled holds: a declared peak belongs to every histogram that
  sees it. WP-1908 is editing the tick builders in parallel, so the audit is
  left to a later pass. WP-1908 closed 2026-10-15; the audit went to
  WP-2028.
- **`STAGE_FREED_NOTHING` sits on the top-level diagnostics, one per
  histogram** (from WP-1414, 2026-09-22), `value` the histogram index. A
  report for a joint fit should put it beside the histogram it names.
  `STAGE_PATH_UNKNOWN` also fires on joint fits, with its suggestion naming
  the `mtable` listing, because `MultiHistogramRefinement` has no
  `parameters()`. Both went to WP-2028.
- **`worst_absorption` has an honest empty state** (from WP-1465,
  2026-09-27). `BackgroundEvidence.worst_absorption` is `float | None`, and a
  per-histogram background section built here carries `None` for a histogram
  whose screen found no target. `report/background.py`'s `assess_background`
  is the builder to reuse, and `report(h)` reaches it through the view's own
  screen (task 4).
- **Deleted on arrival:** WP-1434's note that `bound_findings` grew `cos=` and
  `esd=`, which `multi.py` already passes. It is folded into the Context
  bullet above.
- **After the work landed (2026-10-14 to -20).** WP-1325 made the joint
  support hold judge each entry a column reaches in its own histogram, and
  joint stages now write `StageResult.held_reach`. WP-1986 found that
  `for_histogram(h)` drops `tick_hkl` and `phase_agreement`. What either
  leaves open is WP-2028's.

## Non-goals

- Making the joint fit itself do more physics. This is reporting and
  telemetry over a capability that already works.
- The cost of the solo report path — 1335. This WP should land **after** or
  alongside it, or it imports a 26× tax into the one arm that does not have it.
- X-ray + neutron joint refinement as a *capability* question — issue #194,
  owned by WP-1312 (its item 3: exercise, audit and document the joint fit).
  #252's converged two-histogram fit is evidence for that task and is
  recorded there; this WP gives the fit a report.

## Tasks

- [x] Decided 2026-09-03: none of the three gaps is an intended limit. Define
      `max_shift_over_esd` across weighted histograms; if no definition holds,
      say so where the field is declared rather than leaving `None`.
      Defined 2026-10-12: one shift and one esd per column of the joint θ
      (`least_squares._final_shift_over_esd_multi`), copied onto the joint
      result's statistics.
- [x] `events=` (and `cancel=`) on `MultiHistogramRefinement.fit`, carrying
      the histogram index in `data` the way `sequential.py` carries the series
      index — no new `EventKind`. Landed 2026-10-12 with `telemetry=`,
      `label=` and `progress=`. Each kind is emitted once per fit, stage or
      evaluation, because the joint solve is one solve; the index rides in a
      `histograms` row per histogram (`history/events.py` says why it is not
      the series' per-event stamp).
- [x] `stage_reports=`, or a written reason it is not offered here.
      Not offered (2026-10-12). One rung is a report per histogram per
      stage at ~0.36 s each (#245), so it would multiply the solo tax WP-1335
      owns. The reason is in `MultiHistogramRefinement.fit`'s docstring and
      in `using/series.md`.
- [x] Whichever part of the report path is histogram-agnostic, reachable from
      a joint result; per-histogram where the quantity is per-histogram, and
      once where WP-1131 says the specimen has one of them.
      `MultiHistogramRefinement.report(h)` (2026-10-12): Layers 0-2 per
      histogram, the background section off that histogram's own screen
      (the joint result now carries every screen, `hist.<h>.`-scoped), and
      the specimen's one microstructure block in every report. It inherits
      the joint path's missing #272 recompile (handover).
- [x] `STAGE_PATH_NOT_FREE` on a joint plan (#803, folded 2026-10-12): the
      helper reads each histogram's table under the joint matching rule, one
      finding per path names the histograms whose table holds it fixed, and
      the `DIAGNOSTIC_SCOPES` row moves from `ABSENT` to `FIT`. Landed
      2026-10-12 as `multi._joint_fixed_literals` over
      `refine._fixed_literal_diagnostics(canonical=)`; single-fit output is
      unchanged.
- [x] Tests: a joint fit produces an event log a reader can partition by
      histogram; the microstructure reading agrees with the solo arms' shared
      size (WP-1131's 408.8/408.8 Å shape); `STAGE_PATH_NOT_FREE` fires on a
      joint plan and #789's silence cases stay silent. All in
      `tests/test_joint_report.py`, each landed with its feature.
- [x] Skill: the generated API index follows (`make_api_index.py`); the body
      or a reference row says what a joint fit does and does not report, since
      an agent today gets silence and no explanation. 2026-10-12: `api.md`
      lists `MultiHistogramRefinement.report` and `refine_multi`'s telemetry
      keywords; `watching.md` 9d.10 and `surprises.md` 8.30 carry the rows.
      The body is unchanged.

## Acceptance

A two-histogram fit emits an event log, carries a convergence figure or a
stated reason it cannot, and reports what the WP decided it reports.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_events_viz_history.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #252 (converged two-histogram X-ray + neutron fit, 41 free
  parameters, Rwp 0.088, GoF 1.47). Distinct from the inter-stage telemetry
  gap on single-histogram fits (#231, #245).
- WP-1016 (per-member events in a series), WP-1131 (what a joint fit shares).

## Handover log

### 2026-10-23 — closed: a joint fit can be watched, stopped and reported

A joint refinement is no longer silent about itself. It writes an event log
and a run directory, a cancel stops it between evaluations, its result carries
`max_shift_over_esd`, each histogram gets the Layer 0-2 report a single fit
gets, and a joint plan naming a fixed literal says so. What it still cannot do
is let every guard see every histogram, and that is now WP-2028's. The
maintainer decided the close today, which discharges "closing waits on the
maintainer".

**Closed on.** All seven tasks landed by 2026-10-13: PR #926 (merged at
`a3987d6a`) and its review fixes, PR #937. Issues #252 and #803 closed that
day and #245 has its line. The acceptance files re-run on this tree
(`test_multi_histogram.py`, `test_events_viz_history.py`,
`test_joint_report.py`; worktree venv, Linux x86_64): 75 passed.

**Inherited, each placed.** 1986's view gap is still true (`for_histogram`
copies `ticks` but not `tick_hkl` or `phase_agreement`,
`schemas/results.py:1821`) and is a 2028 task. 2001/2004's rule for a gate
added here goes to 2028's Context, since this WP added none; 2004's fence and
1335's Non-goals line get notes naming 2028. 1325's four open items and its notes on the three
`PARAMETRIC_*` codes go to 2028, spelled as the tree now spells them
(`parametric_equations`, `RefinedParameter.equations`); its "what changed
underneath" is one Context sentence. § What later work changed stays, each
bullet saying where it went.

*Next.* Nothing owed here. The three open questions and 1325's items are
WP-2028's. The fresh compile went to WP-1421 on 2026-10-12 (open; its
Inherited carries it). WP-1908 closed 2026-10-15, so the census is unblocked.
`Refinement.report`'s live-table read (PR-review item 9 below) went to WP-1421's Inherited.
The four `multi.py` comments naming WP-1341 as owner are a 2028 task. 1325 is told.

### 2026-10-13 — six tasks landed: events, a convergence figure, a report per histogram, and #803

A joint refinement can now be watched, stopped and inspected the way a single
fit can. It writes an event log and one run directory, it can be cancelled
mid-stage, its result carries a convergence figure, and each histogram gets a
full three-layer report. A joint plan that names a locked or tied literal path
now says so (#803). Building the report exposed a defect the joint path
already had: its curves come from the last stage's compile and were never
recompiled at the answer. A last stage that broadens the peaks leaves cut
tails, which Layer 0 then reads as unmatched peaks. That was not fixed here,
because it moves joint-fit numbers and this WP promised none would move.

**Decided.**

- `max_shift_over_esd` has a definition across weighted histograms, so it is
  measured rather than `None`. Each column of the joint θ has one shift (the
  joint solve's last accepted step) and one esd (the weighted stacked
  covariance's), and a shared column reads the same ratio in every table
  (`least_squares._final_shift_over_esd_multi`). The weights change the
  number and leave its meaning alone.
- The histogram index rides in a `histograms` row per histogram on
  `fit_start`, `stage_start`, `stage_end` and `fit_end`, beside
  `n_histograms`. The series stamps every event because each event there is
  about one pattern; a joint event is about all of them, so a per-event
  stamp would either pick one or duplicate events. No new `EventKind`, no
  `EVENT_SCHEMA_VERSION` bump (`history/events.py` docstring).
- `stage_reports=` is not offered. One rung is a report per histogram per
  stage at ~0.36 s each (#245), multiplying the tax WP-1335 owns. The reason
  is in `MultiHistogramRefinement.fit`'s docstring and `using/series.md`.
- The report is per histogram (`MultiHistogramRefinement.report(h)`): Layer 0
  to 2 off that histogram's view, compiled model and values. The specimen's
  one microstructure block, read at histogram 0's λ, is the same object in
  every report. The joint result now writes `Identifiability` with each
  histogram's background screen under `hist.<h>.` keys, and `for_histogram`
  hands each view its own rows.
- #803: `refine._fixed_literal_diagnostics(canonical=)` matches a literal as
  `MultiParameterTable.set_vary` does; `multi._joint_fixed_literals` merges a
  shared row into one finding naming its histograms. On one histogram a
  literal gets this finding or `STAGE_FREED_NOTHING`, never both.
- #442 does not fold in: the maintainer's 2026-09-24 reply ties it to the TOF
  design, and nothing here touched `unreached_histograms`.

**Done.** Commits `917f4f74` (prune) to `6e096c0f`, all `WP-1341:`. The stage
loop moved from `fit` into `MultiHistogramRefinement._run_plan`, re-indented
under a per-stage `_abandon_on_cancel` that deep-copies `self.mtable`
(2.7 ms on the LaB6 pair). `refine_multi` passes the telemetry keywords
through. `multi.py`'s `_ticks` was not touched (WP-1908 edits the tick
builders). Inherited pruned on arrival: every entry still held at `e1d19359`
except WP-1434's note, folded into the Context bullet it corrected. #803
became a checklist item; the rest moved to Context § What later work
changed, three of them still open (below).

**Measured** (`[dev]` venv, macOS arm64, synthetic fixtures from
`tests/test_multi_histogram.py`).

- Bit-identity: a dump of every parameter value and esd, `at_bound`, both
  statistics blocks, stage costs and iterations, diagnostic codes and the
  microstructure block, for the LaB6 pair under LM and TRF and for the
  WP-1131 size pair, is identical before and after the work except for the
  new `max_shift_over_esd`. The fast selection's joint tests
  (`test_multi_histogram.py`, `test_joint_xray_neutron.py`,
  `test_multi_diagnostics.py`) pass unchanged.
- `max_shift_over_esd`, LaB6 pair: converged 1.95e-3 (LM), 5.0e-7 (TRF),
  2.2e-3 and 7.4e-7 at 1:4 weights, 2.3e-5 and 1.2e-3 on one stage; starved
  to one iteration, 4.03 (LM) and 17.9 (TRF). Both sides clear the 0.1 band
  by 40× or more.
- Event log, LaB6 pair, `mccusker_default` under LM: 1 `fit_start`, 5
  `stage_start`, 38 `eval`, 5 `stage_end`, 1 `fit_end`; the last
  `stage_end` rows equal the result's histogram Rwp exactly (0.04113,
  0.06127) and its pooled `rwp` equals `fit_end`'s.
- Size: the joint block reads 408.82(4.86) Å; the two solo arms 408.71(8.05)
  and 409.20(6.43) Å.
- The #272 sibling, size pair: the result's stage-start compile gives Rwp
  0.10242 and 0.13345 with 44 and 27 unmatched peaks; a compile at the
  answer gives 0.10478 and 0.11981 with 0 and 0. On the LaB6 pair both
  reports find 0 unmatched.
- Fast selection, final tree, `[dev]` venv, macOS arm64: 9321 passed, 181
  skipped, 3 xfailed, 0 failed, in 28:39 at a load average near 130 with
  other sessions' suites running (an earlier run on the pre-review tree took
  19:19 at ~150). The darwin/arm64 goldens pass, after the review moved the
  single fit's wrappers.
- The count against a base run, from CI's py3.14 leg (Linux, `[dev]`, both
  shards' junit): `main` at `be6c3ffd` (run 38322641475) 9293 passed and 195
  skipped, 9488; #926's head `3475b2b2`, which is that commit plus this
  branch (run 38323923594), 9310 passed and 195 skipped, 9505. So +17, every
  one a pass, the 17 cases of `tests/test_joint_report.py`.
- Added-test cost, that same loaded run's junit: 54.1 s over the file; the
  two report tests 15.2 s and 14.2 s, the shift pair 11.5 s, every other
  test under 4 s. Not `slow`: they are synthetic, the report pair fits two
  and four times in seconds when the machine is quiet, and the size test's
  solo fits are the comparison it asserts.
- Full selection: not run. No measured number moves (the dump above, and
  the goldens), so the ladder's third rung does not fire.

**Review** (`/code-review high --fix`, nine findings, six taken in
`6e096c0f`): the two solver wrappers are one pair, `_cancellable` and
`_tracked`, shared with `run_least_squares`; a cancelled `stage_end` and
`fit_end` carry the `histograms` rows; an empty plan is refused before any
event; scoped paths go through `MultiParameterTable._owner`/`_unscope`; and
`Identifiability` says a joint fit leaves `extra_peak_absorption` unrun.
Declined then, and taken in the PR round below: a `free_values` method on
both table types, and `report(h)` after a cancelled second fit. Declined:
`_stage_end_rows` re-deriving the Rwp `_build_result` also computes (events
only, one evaluation per histogram per stage).

**PR review** (`/code-review medium` on #926, ten findings). #926 merged at
`a3987d6a` before this round landed, so the fixes ride a follow-up PR from
branch `wp1341-review-fixes`. Fixed, each with a test that fails without it:

1. `for_histogram(h)` kept every parameter row `hist.<h>.`-scoped, so the
   report's lookups by bare path missed a per-histogram structural row and
   the view carried other histograms' rows. It now keeps histogram h's rows
   unscoped and drops the rest, as the background screen already was.
2. A negative `h` built a prefix from the raw index; it now counts from the
   end, and an out-of-range one is refused.
3. `fit()` closed a stream it built only on success or a cancel; it now
   closes it in `finally`.
4. `tests/test_joint_report.py` joins one `xdist_group`, its module
   fixtures being shared.
5. `watching.md` 9d.10's evidence line is two sentences, in all three
   copies.
6. The count above is passed+skipped against a base run, where it was a
   collection count.
8. `ParameterTable.free_values` and `MultiParameterTable.free_values` hold
   the layout knowledge, and `least_squares._free_values` delegates.
9. `report(h)` reads values, structure, held and free paths frozen with the
   result (`_freeze_answer`), so a cancelled second fit cannot pair its
   restored table with the first fit's models. `Refinement.report` reads its
   live table the same way, left to its own change.

Declined:

7. The per-stage deep copy of the table under a cancel token stays. On a
   quiet machine (load ~3.5) it costs 1.0 ms at 3 atoms, 7.9 ms at 64 and
   34 ms at 256 atoms over two histograms, and 76 ms over four, linear and
   small against stages that run for seconds. A hand-listed snapshot
   (`_commit_state()` and vary flags) would also have to carry holds,
   frozen windows, moment frames and the combined columns; a missed one is
   a silent wrong restore, which a whole-table copy cannot make.
10. The stream, recorder and cancel attach ritual is not factored. A helper
    only `multi.py` used would remove no copy, and sharing one means editing
    `refine.py`'s three call sites, which is outside this WP.

**Gotchas.**

- `MultiParameterTable.x0()` is cached. After a commit that re-charts
  nothing it still holds the stage's start, so anything reading the answer
  decodes `outcome.theta` (as `_build_result` does and `_stage_end_rows` now
  does). The first draft of the stage-end rows read `x0()` and reported the
  stage's starting Rwp.
- An `intermediate_ftol` schedule makes a plan's prefix solve differently
  from the same stages run as a whole plan; the cancel test pins
  `intermediate_ftol=None` on both.
- Issue #283's seat test asserted the TRF driver got the cell guard itself.
  The tracker closure now sits on top, as on the single path, and each joint
  wrapper sets `__wrapped__`.

**Still open in this WP** (Context § What later work changed): whether the
joint fit takes WP-1523's marginal significance test and how histograms
combine; the audit of what else `multi.py` re-derives (WP-1344's note, left
while WP-1908 edits the tick builders); and putting `STAGE_FREED_NOTHING`
beside its histogram. `summary()` is not offered: `print(result)` is the joint
termination view.

**For the issue threads** (to batch, none posted): #252 and #803 close with
this PR; #245 gets a line that the joint fit declines `stage_reports=` until
WP-1335 lands. Texts are in the session's final report.

Next: (1) the missing #272 recompile on the joint path, forwarded to
WP-1421's Inherited, because it decides whether the joint report's Layer 0
can be trusted after a width stage; (2) the WP-1523 significance question,
which changes `PHASE_UNCONSTRAINED` on joint fits; (3) the `multi.py` census
once WP-1908 merges.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #252).
  Checked on the tree: the four-member public surface is as reported, and
  `bound_findings` is already reached from `multi.py`, so the guard path is
  not what is missing. Re-checked the same day: 1312 owns #194 and is named;
  test modules named as they exist. Decided the same day: none of the three
  gaps is intended.
