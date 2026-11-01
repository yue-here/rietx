# WP-1317 — scrub the series along its own trace

Milestone: unscheduled · Status: 🔄 2026-10-21 — #218's `forward_` and `moved_paths` merged from outside as #903, and the planted-events series fixture as #1011; the scrubber is unstarted
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-09-23 — a view over what the series already knows

## Goal

An in-situ series is navigated by the experiment's own axis: a master trace
(temperature or time versus pattern index, from the series' own metadata)
carries markers wherever the series' diagnostics fired, and dragging along
it updates a linked obs/calc/diff view of that pattern at interactive speed
— the "play through the phase transition and watch the peak split" motion
that today takes ~40 clicks through drill-downs.

## Context

From issue #133, with issue #141's surviving half folded in.

**What exists.** WP-1016's series panel plots per-parameter trajectories
with esds and drills into per-pattern history trees. Navigation by the
experiment's axis, and event annotation on it, do not exist — the issue
notes v1.2's seventeen GUI WPs do not cover it.

**Why it is series-shaped, not sugar.** A transition is legible only
*across* patterns: the motivating cases in the filer's archive read as a GoF
step plus an unmatched-peak collapse over 2–3 patterns, invisible in any
single fit view. The scrubber is the human-speed version of the same
discriminators the batch heuristics already use.

**One vocabulary, already shipped — the first task.** The markers come from
what `SeriesResult` already carries: the `SEQUENTIAL_*` findings
(`PATH_DEPENDENT`, `UNRECOVERED`, `CANCELLED`, `PERSISTENT_FINDING`),
per-pattern refusals and abstentions, agreement steps. This is issue #141's
surviving insight — its proposal (a batch verb returning aggregates plus
flags, reports on demand) targeted `refine_json`, which WP-1303 deleted,
and its aggregates-plus-flags answer is what WP-1305 shipped as the series
deliverable; what remains is the rule that **the flag list and the event
markers are one vocabulary**, read from the result, never a second set
invented view-side. Later external annotations (a gas switch, a declared
transition interval) extend the same vocabulary.

**The issue's open questions are this WP's questions**: which panel owns the
trace; whether external annotations are a schema addition or view-side;
animation/export and 2-D film views (probably out, but decided here, not
assumed).

**Standing GUI gates apply**: mutating verbs 409 while a run is in flight;
`EventKind` stays closed (the run state is not an event); the GUI-manual
partition test will demand a chapter for any new tab or route, and
screenshots come from `docs/manual/make_screenshots.py`.

### Inherited

- **2026-10-26, from WP-2003 (fourth session): the series panel's "discontinuous" mark has no writer left; plot `SeriesResult.steps` instead.** WP-2003 removed `SEQUENTIAL_DISCONTINUITY` (no threshold survives) and added `SeriesResult.steps`: every refined path's step between consecutive patterns, in esds of the later fit, largest first, with `cold_ratio` set only on steps a caller re-measured with `fit(verify_steps=k)`. `src/rietx/gui/series.py` keeps the route's `discontinuous` key, now true only for such a verified step, and the GUI never passes `verify_steps`, so it is always false there. The client still reads it and still captions it "a step far larger than this parameter's own scatter" (`gui/src/lib/series.ts:65`, `:151`, `:196`; `gui/src/panels/Series.svelte:613`). WP-2037's mock-up (`docs/wp/2037-attention/examples.md` § 5) has the panel plot `series.steps` beside the trajectory. That change and its dist rebuild are owed, and the scrubber is where the series panel is being rebuilt.
- **2026-10-24, from WP-2003 (PR #1150): the planted fixture's `signals.json` is stale in its one unpinned list.** WP-2003 reran the planted-events series on the current tree (`docs/wp/2003-batch/measure_reseed.py --family planted`, all 248 patterns, default arm) and found 49 reseeds where `tests/data/planted_series/signals.json` lists 20. Nothing fails, because `tests/test_planted_series.py` pins every signal but that list. The other lists were not compared. The reseed fence's ruling (WP-2003's batch) may change the count again, so regenerate it after that lands, or pin it now and let the ruling move it on purpose.
- **2026-10-19, from WP-1986.** The GUI chapters moved to the new manual tree:
  `docs/docs/start/gui-quickstart.md`, `docs/docs/reference/gui-guide.md` and
  `docs/docs/reference/gui-power.md`, with the screenshots in `docs/docs/screenshots/` and
  the script at `docs/docs/make_screenshots.py`. `tests/test_gui_manual.py` partitions routes
  and tabs over the new pages, so the scrubber's tab or route is documented there. The old
  `docs/manual/using/gui-*.md` copies stay up, unguarded, until that tree retires.
- **Decided 2026-10-16 (maintainer, from the issue triage, #141): the
  planted-events fixture goes ahead now.** The reporter opens it as a
  tests-only PR against this WP, WP-1965 named as the second user: the seeded
  generator, the full-length series, its `refine_sequential` result and
  `to_table()` output, and a test that every planted event appears in the flag
  vocabulary. The test says it checks recovery of planted events, since the
  data come from the model being fitted.

- **2026-10-16, from the issue triage (#141): the reporter asks to schedule
  the planted-events fixture now.** Posted 2026-10-16T07:00Z, after the
  2026-10-13 entry. They propose it as this WP's first task, or under
  1325/1965: the seeded generator, a full-length series (temperature ramp,
  smooth cell expansion, four planted events), its `refine_sequential` result
  and `to_table()` output, and a check that each planted event appears in the
  flag vocabulary. Their reasons: series fits are joint since #969, and an
  August detector's thresholds inverted by 1.9.0.dev0 (their comments on
  #977). Awaiting the maintainer's go; checked against origin/main 138d55dc,
  where no generator exists under `tests/`.

- **2026-10-15, from [1325](1325-parametric-series.md), from @mustachefeeling's comments on PR #977: #141's planted-events series is wanted as a
  calibration fixture.** Their blind event detector's thresholds, tuned by
  hand on one positive and one null series in August, inverted by
  1.9.0.dev0: the positive series is missed and the null fires. A detector
  calibrated inside the suite against a seeded planted-events series would
  fail a test when a fitting change moves it. That series still owes its
  seeded generator. [1965](1965-a-law-declared-by-formula-condition-and-glob.md)
  holds the rest.

- **2026-10-11, from the issue triage (#218, in PR #903): the two asks are
  open as the reporter's PR, and the scrubber is not in it.** PR #903 (opened
  2026-10-11, fork) adds `SequentialRefinement.forward_`, published at
  WP-1333's early point under `direction="both"`, and
  `SeriesResult.moved_paths(n, min_sigma)`, which skips esd-less paths,
  coordinate DOFs and exact tied duplicates. It records
  `SeriesResult.relative_paths` and `.angle_paths` (`SCHEMA_VERSION` 0.45 to
  0.46, shared with PRs #871 and #888). The PR says `api.md` lands 72 B over
  its ceiling and leaves that to the maintainer. The claims match #218.
  Checked against the tree at d80ca5f4: neither `forward_` nor `moved_paths`
  exists under `src/`.

- **From WP-1469 (2026-09-29): a new marker for the vocabulary, and the
  panel does not draw it yet.** `SEQUENTIAL_RWP_OUTLIER` names a pattern
  every rung left above the Rwp fence (#481's blank frame is the case). Its
  verdict is `SeriesEntry.above_fence`, a **property** derived from the stored
  `SeriesEntry.rwp_fence`, so it is not in the entry's JSON: the route has to
  serve it rather than the page re-deriving it from `rwp_fence`, or the panel
  is a second authority on the fence. `plot_trajectory` boxes such a point
  (hollow square) beside the reseeded ring and the unrecovered cross, while
  `gui/src/lib/series.ts` draws only those two, so today the same series
  reads differently in the two renderers. 1469's review declined the GUI half
  as outside that diff and it was briefly filed on its own, then folded here,
  since this WP's first task is that vocabulary. The flagged step's pair is
  also a field now (`SeriesResult.discontinuities`, a `SeriesStep` per
  `SEQUENTIAL_DISCONTINUITY`, `path` its key), which is what a step marker
  should read rather than the prose.
- **From WP-1333 (2026-09-26): chart a coordinate, never its DOF.** A series
  now carries refined coordinates, so a `phases.*.atoms.*.dof.*` value is each
  pattern's step from where its fit began, not a position. A scrubber drawing
  trajectories draws the coordinate rows. A disagreement or jump it computes
  itself skips `sequential._relative_paths`, as both fences and
  `gui/series.trajectories`' `n_sigma` do.
- **From the 2026-09-01 triage's second batch (issue #207 →
  [1322](1322-events-aggregator.md))**: the headless counterpart is its own
  WP — a `rietx events` aggregator whose `termination` histogram and
  held-path counts summarise the same marker vocabulary this panel draws.
  The one-vocabulary rule now spans both consumers: neither surface invents
  a second set of names.
- **From the roadmap reorder, 2026-09-01 (issue #218)**: a scrubber over a
  `direction="both"` run needs the forward pass before the backward one
  finishes, and today it cannot have it — `sequential.py` assembles the
  forward `SeriesResult` and runs `_persistent_diagnostics` on it before the
  backward branch, exposes `self.backward_`, and has no `self.forward_`. The
  issue asks for exactly that attribute (set before the backward walk, with
  every diagnostic except the path-dependence ones, which cannot exist yet)
  or an `on_pass_complete` callback beside `progress=`, plus a
  movement-ranked `SeriesResult.moved_paths(n, min_sigma)` so every caller
  of `plot_trajectory` stops inventing the same ranking. Both belong to the
  series surface this panel reads; land them here or split them out, but
  the panel should not be the only consumer.
- **From WP-1333 (2026-09-22): half of #218 now exists, for the failure case
  only.** `_run` publishes the forward chain onto `self.results_`/`.trees_`/
  `.failures_` *before* the backward walk, and when the backward walk raises
  it also sets `self.result_` to the forward `SeriesResult` and attaches it
  to the exception as `series_result`. There is still no `self.forward_` on
  a run that is merely in progress, which is what a live scrubber needs, so
  #218's attribute or callback stays this WP's; build it on the same
  early-publication point rather than a second one. A backward pass also now
  carries its own `failures`, and `SEQUENTIAL_PATH_CHECK_INCOMPLETE` says
  when the comparison did not run or ran on fewer patterns or paths — a
  marker vocabulary this panel should draw rather than re-derive.
- **From WP-1461 (filed 2026-09-24, not started): the GUI's charts may move
  to uPlot first.** 1461 puts every browser chart on one module over uPlot
  and keeps plotly only for the 3D viewer. If it lands first, draw the trace
  and the linked pattern view on that module. Its spike measured two of this
  WP's open questions. A 200 × 22 003 in-situ map drew from a max-pooled
  pyramid at 1.6 ms per wheel event. The first zoom into each pyramid level
  cost up to two 100 ms frames, a texture upload. And a trajectory in chain
  order needs uPlot's mode 2, because a heat-then-cool series loops
  (1461 § D8). If this WP lands first, 1461's Series task inherits what it
  adds.
- **From WP-1461 (2026-09-25, 6th session): its Series task landed first,
  and mode 2 was not needed.** The panel's trajectory is `rxplot.trajectory`,
  which draws the chain in a draw hook over one pane, so a heat-then-cool
  series comes back along its own x. It takes rings and crosses per point,
  hides marks by id (`setHidden`), and names the hovered point through
  `onPoint`, picked by distance in the plane (`nearestXY`). One member's
  pattern is `rxplot.pattern` over `/api/series/curves`, and
  `/api/series/window` is gone. Build the scrubber's trace and its linked
  pattern view on those two figures. The previous bullet's mode-2 remark is
  superseded.

- **2026-10-11, from the issue triage (#218): an esd caveat and a PR offer
  are carried by no file.** `moved_paths(n, min_sigma)` ranks by peak-to-peak
  movement over the median esd. Agreement-index trajectories carry no esd
  (`stderr` is `None` throughout, as `plot_trajectory`'s docstring says), so
  they are left out of that ranking or ranked by a separate stated rule, never
  mixed in silently. The reporter offers a PR for the `forward_` attribute
  alone or with `moved_paths`, and asks which, and whether to prefer the
  callback. Checked against the tree at 7d9be3cb: no `forward_`,
  `moved_paths` or `on_pass_complete` under `src/`.
- **2026-10-13, from the issue triage (#141): the 248-pattern table will not
  come, and a synthetic series is offered instead.** Posted 2026-10-12: the
  table is from a private series. The reporter offers a series of the same
  length and shape built with rietx's own forward model, a temperature ramp
  with smooth cell expansion and four planted events (a phase transition, a
  background step, a second phase appearing, one bad pattern), with its
  `refine_sequential` result and `to_table()` output, built when this WP
  starts. Ask on #141 when it does. It is § Acceptance's series fixture with a
  known transition; ask for the seeded generator beside the outputs, so the
  fast suite can regenerate a shorter series.

## Non-goals

- **Not the batch computation** — `refine_sequential` already computes the
  findings; nothing here changes what a series run produces.
- **Not a second flag vocabulary** — read the result's.
- **Not 2-D film/waterfall rendering as a deliverable** — decided in-WP,
  and if wanted it is its own later work.

## Tasks

- [ ] The vocabulary: enumerate the marker set from `SeriesResult`'s own
      findings and per-pattern flags; write it down once, view and docs both
      quoting it.
- [ ] The trace: T/t vs index from series metadata, markers placed, owned
      by a panel decided here.
- [ ] Scrubbing: drag updates the linked pattern+fit view at interactive
      speed; the drill-down stays one click away.
- [ ] External annotations decided (schema vs view-side) and, if schema, the
      minimal addition with its round-trip test.
- [ ] GUI manual chapter + screenshots via `make_screenshots.py`; vitest
      coverage for the panel logic; `npm --prefix gui run check` clean.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_manual.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The bar: on a series fixture with a known transition, the trace shows the
event cluster where the transition is; scrubbing across it updates the fit
view with no per-step server round-trip cost beyond the pattern fetch; the
manual partition is green with the new chapter.

The shipping PR carries `Closes #133` — and `Closes #141` if that issue is
still open, since its surviving residual lands here.

## References

- Issues #133 and #141 — the motion, the measurements, and the vocabulary
  rule.
- [1016](1016-sequential-series-panel.md) — the panel this extends;
  [1305](1305-series-deliverable.md) — the series answer the vocabulary
  reads.
- `gui/CLAUDE.md` — the panel, route and manual-partition rules.

## Handover log

- **2026-10-21** — the planted-events series this WP's acceptance asks for
  merged from outside. PR #1011 (head `82cf9600`) merged as `58ccce44` by
  `/pr-review` after two rounds. Tests and test data only; no source change.
  *Done.* `tests/planted_series.py` forward-models a 3-20° capillary cooling
  ramp of a cubic perovskite with Poisson noise. It plants four events at known
  indices: a background step, one blank frame, an unmodelled rock-salt phase
  growing, and a cubic → tetragonal transition. It also has a null twin with
  none. One fixed cubic model is fitted along the chain, and `surfaced` reads
  each event off `SeriesResult` alone (`EVENT_CODES`). The fast tier regenerates
  a 24-pattern series, and `tests/data/planted_series/` holds the 248-pattern
  run's `table.csv`, `signals.json` and `null_signals.json`, not the patterns.
  Both generator and refit run under `compiled.set_enabled(False)` (the
  `numpy_path` decorator), and the Mac-generated `signals.json` reproduces
  byte for byte on Linux.
  *What it makes possible.* The acceptance's "series fixture with a known
  transition" exists, and `surfaced` is a first enumeration of task 1's marker
  vocabulary, though not yet one written once and quoted by view and docs.
  Three findings for the scrubber's design. **The blank frame** is a step in the
  phase scale and a `PHASE_UNCONSTRAINED` hold, not an Rwp outlier. **The
  transition is masked when it falls inside the second phase's run above the
  Rwp fence**: the discontinuity scan skips every step into or out of a pattern
  above the fence, so nothing marks it. That is a strict xfail; planted alone, the
  transition does start a run. **On the 248-pattern null**,
  `SEQUENTIAL_DISCONTINUITY` flags 1 to 4 noise steps on four of five seeds,
  also a strict xfail. Those two xfails go red the day something makes the event
  visible or the null clean.
  *Not done.* None of the five tasks is ticked. The scrubber is unstarted.
  *Gate:* stacked with #1069 on `main` `3437d52d` as `abe6d9e2`, Linux x86_64,
  4 cores, `[dev,jax]`, `-n 3`, nothing else running: fast 10 986 passed,
  132 skipped, 3 xfailed; `-m slow` 319 passed, 16 skipped, 1 xfailed. `main` after both merges
  (`c93b974b`) is content-identical to that tree.

- **2026-10-12** — #218's two asks merged from outside. PR #903 (head
  `0afe61b6`) merged as `75b9ee88` after four rounds, and #218 is closed.
  *Done.* `SequentialRefinement.forward_` is the forward chain's
  `SeriesResult` under `direction="both"`. It is set at WP-1333's
  early-publication point, before the backward walk starts. It carries the
  forward chain's diagnostics and none of the comparison's, and it is `None`
  on a one-direction run. `SeriesResult.moved_paths(n, min_sigma)` ranks paths
  by peak-to-peak movement over the median esd. It never ranks a path with no
  esd, a coordinate DOF (its coordinate rows are ranked instead) or a tied
  path whose curve repeats an earlier one. Angles are spread over the shortest
  covering arc. Schema 0.51 records which paths are steps and which are angles
  as `SeriesResult.relative_paths` and `.angle_paths`; `None` means "not
  recorded".
  *What it makes possible.* A live scrubber can read `forward_` from the
  runner mid-fit, and `moved_paths` chooses which trajectories to draw. A
  script reaches `forward_` from its `events=` callback, on the first event
  stamped `series_pass="backward"`. The PR chose the attribute over #218's
  callback alternative, because `backward_` and `result_` are already
  attributes published at that point.
  *Not done.* None of the five tasks. The scrubber is unstarted.
  *Gate:* stacked with #912 on `main` `a7e71bf7` as `d41a7932`, macOS arm64,
  `[dev,jax]`, nothing else running: fast 9357 passed, 113 skipped, 2 xfailed;
  `-m slow` 306 passed, 14 skipped. `main` after both merges (`a8960f79`) is
  content-identical to that tree.

- **2026-09-01** — created, from issue #133 with #141's residual
  (2026-09-01 triage). Settled: one vocabulary read from the result; first
  open decision is which panel owns the trace.
