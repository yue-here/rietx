# WP-1949 — an accepted evaluation carries what a preview draws

Milestone: unscheduled · Status: 🔄 2026-11-25 — built in #1623; the spelling was accepted as built (2026-11-17); the WP closes with the maintainer's handover after the merge
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-11 — a live preview keeps a shadow refinement and re-predicts every frame (about 0.7 s a frame on a large framework); the workaround works and costs a throttle

## Goal

A caller watching a fit through `events=` can draw the current curve, atoms
and cell from an accepted `eval` event, without a second refinement. It is
opt-in, the default event stays as small as it is, and the recorder's
`events.jsonl` never carries the curve.

## Context

**The report (issue #892).** An application previews a running fit live.
An accepted `eval` event carries only the free values (`data.values`, in
the `free_paths` order `stage_start` gives). To draw the pattern the app
keeps a "shadow" refinement of the same phase. Each frame it resets the
atoms to their starting positions (a `dof` value is a step from where the
atom was), calls `set_values`, then `predict`. That is about 5 ms a frame on
rutile and about 0.7 s on MFU-4l (the reporter's numbers), so they throttle
frames. They ask for an off-by-default option to put `y_calc`, the current
atom positions and the cell on accepted `eval` events.

**Checked at `d80ca5f4`.**
- The TRF wrapper emits `eval` with `stage`, `n_eval`, `cost`, `accepted`,
  `step_norm` and `values` (`optimize/least_squares.py:1677-1690`). The LM
  driver's `trial_cb` (`:1346-1353`) emits the same plus `lam`, and is handed
  θ and the cost, not the residual.
- `values` is `_free_values` (`:1308-1319`): `table.decode(θ)` filtered to
  `free_paths`. The decode already holds every moving path, including the
  tied `x`/`y`/`z` and the cell (92 keys on FAP). The filter discards them.
  A coordinate is absolute in the decode (root CLAUDE.md, WP-1432), so
  carrying the moving paths removes the reporter's reset step.
- **The curve is already computed.** The residual is
  `sqrt_w·(y_obs − model.evaluate(...))` (`model/rows.py:136`), so inside the
  TRF wrapper `y_calc = y_obs − r[:n_data]/sqrt_w` on the fitted channels.
  `predict()` differs from it on 36 of 4200 channels at up to 8e-6 because
  it freezes the windows differently (its docstring).
- **What it costs if serialised.** FAP.XRA (5753 points, `mccusker_structural`):
  86 `eval` events, 70 accepted, 10.6 ms an evaluation. An accepted line is
  256 B. `json.dumps` of `y_calc` takes 1.65 ms and 111 kB an event (50 kB at
  3 decimals). On every accepted event that is about 7.8 MB a fit and 16 %
  on evaluation time. Handing a callback an ndarray costs a slice and a
  divide.
- `EventStream.emit` (`history/events.py:152`) runs the callback on the fit
  thread and `json.dumps` the event for its file sink (`:156`). An ndarray
  cannot pass that. A new key in `data` needs no `EVENT_SCHEMA_VERSION`
  bump (`events.py` docstring).

**Rules this meets.** A live view is numbers a viewer draws, never a page
the fit builds (root CLAUDE.md, WP-1402). `viz/snapshot.py` already writes
the curve once a stage, decimated to `MAX_POINTS = 4000`. WP-1402 and
WP-1403 measured megabytes a stage when a page rode the fit, so the
recorder's `events.jsonl` must not receive a per-evaluation curve. A
per-stage charge is judged on the shortest fit (WP-1413). The recorder is
attached beside a caller's stream, never inside it (WP-1403), so a payload
can reach the caller's callback and skip the recorder.

**Superseded in part, 2026-11-16 (checked at `bc77a934e`).** The default
driver is now LM (`DEFAULT_SOLVER`), so the TRF wrapper is the selectable
path and `trial_cb` the common one. The two emitters are `_tracked`
(`optimize/least_squares.py:3024`) and `_lm_outcome.trial_cb` (`:3084`), and
the LM driver calls `on_trial` from one site (`optimize/lm.py:643`), still
without the residual. The recorder is chained *into* the caller's stream as
its first callback (`runs.attach`, `_combined`), not beside it, so a payload
reaching the caller's callback reaches `RunRecorder.record` too, which must
drop it. The re-measured costs are under Task 1 below.

**The tier of each rule this WP adds.** One switch, off by default, that
decides nothing for the caller: `caller` (an opt-in the user asks for; no
threshold, no automatic action). No number is added.

### Inherited

- **2026-11-21, issue triage (#1652 item 2): the "36 of 4200 channels at up
  to 8e-6" bullet above is stale.** At `c1033a0e8`, after a default fit on
  the fluorapatite tutorial, `predict()` equals `result.y_calc` bit for bit,
  and `predict(grid)` differs from it on every channel by up to 1.6e-3 of the
  strongest peak. The cause is the window cut: a grid compiles at 1e-3 of
  each peak's area, and the fit measured at the declared stages' 2 %
  (WP-2222). The measurement and the docs fix sit in WP-2235. So
  the Acceptance's comparison of an `eval` event's curve with `predict` at
  the event's values compiles at the window the stage ran at, with the recipe
  in `predict`'s docstring (`compile_model(..., window_area_tol=...)`). A bar
  of 8e-6 against `predict(grid)` cannot pass today.
  **Superseded in part, 2026-11-22 (WP-2235, Yue's ruling A).** On a fitted
  `Refinement`, `predict(grid)` now compiles at the last fit's peak cut and
  slack, so `predict(result.two_theta)` equals `result.y_calc` bit for bit
  (0 of 5751 channels differ on the fluorapatite tutorial). The recipe is no
  longer needed on the fitted object itself. A twin that has not been
  fitted, such as a `_trial`, still compiles at 1e-3. What remains between
  an `eval` event's curve and `predict` at its values is that the event's
  windows were sized at the stage's start values: the class the stale
  bullet's 36-of-4200 figure measured, not re-measured since.

## Non-goals

- The per-stage `snapshot.json` and `rietx watch` (unchanged).
- A post-hoc aggregate of an events log (WP-1322).
- Throttling events by count (WP-1413's rule: by time, if ever).

## Tasks

- [x] Measure first, on a model whose evaluation is dear (the reporter's
      MFU-4l class, or the largest structure in `tests/data`): evaluations
      per fit, accepted share, and the per-event cost of (a) the moving-path
      values, (b) an ndarray `y_calc` handed to a callback, (c) a decimated
      JSON `y_calc`. Record the numbers here.

      **Measured 2026-11-16** at `bc77a934e`, `[dev]` venv, macOS arm64,
      default LM driver, `mccusker_structural`, `RIETX_TELEMETRY=0`; each
      cost is the best of three `timeit` repeats on the last stage's model.
      HKUST-1 is `tests/data/cod_4002052.cif` (Cu₃(BTC)₂, Fm-3m,
      a = 26.3 Å, V = 18 132 Å³, the largest cell in `tests/data` and the
      reporter's MOF class), fitted to its own synthetic Cu Kα pattern
      (4-60° 2θ, 0.01° step, Poisson noise, cell started 0.05 % long).

      | | FAP.XRA | HKUST-1 |
      |---|---|---|
      | fitted points | 5753 | 5600 |
      | stages / `eval` events / accepted | 12 / 124 / 124 | 12 / 45 / 45 |
      | free / moving paths (last stage) | 34 / 47 | 32 / 51 |
      | one residual evaluation | 3.4 ms | 0.30 ms |
      | fit wall (solve) | 2.9 s (2.1 s) | 9.5 s (3.4 s) |
      | today's accepted `eval` line | 988 B | 954 B |
      | (a) moving-path values, decode + pick | 0.014 ms, 2150 B as JSON | 0.019 ms, 2320 B as JSON |
      | (b) ndarray `y_calc = y_obs − r·σ` | 0.006 ms | 0.005 ms |
      | (c) JSON `y_calc` at `MAX_POINTS` (step 2), full / 3 dp | 1.38 / 0.75 ms, 55.7 / 24.8 kB | 1.16 / 0.63 ms, 55.0 / 24.9 kB |
      | the reporter's shadow `predict(grid)`, one frame | 21.6 ms | 548 ms |

      Every LM `eval` was accepted on both fits (the driver's linear model
      discards most rejected steps unevaluated), so "accepted only" thins
      nothing here. (a)+(b) cost 0.02 ms an event, 2.5 ms over FAP's whole
      fit (0.1 % of its solve) and over 20 000× under one shadow frame on
      HKUST-1. (c) costs 171 ms and 6.9 MB a FAP fit at full precision (8 %
      of the solve), 93 ms and 3.1 MB at 3 dp, on every sink the stream
      writes. `y_obs − r·σ` agrees with `model.evaluate` at the event's
      values to 1.4e-18 of the curve's maximum on FAP and exactly on
      HKUST-1. A residual evaluation of the MOF is cheap: what costs the
      reporter 0.5-0.7 s a frame is the compile `predict` does, which the
      preview removes.
- [x] Decided 2026-11-17: accepted as built (maintainer, PR #1623 review).
      Decide the spelling and record it as `Decided YYYY-MM-DD:`. The
      options are a `fit(..., eval_payload=...)` flag, or a property of the
      callback the caller passes. Decide too whether `y_calc` reaches only
      an in-process callback (ndarray, never the file sink) or also the file
      at `MAX_POINTS`.

      **Proposed 2026-11-16, built as proposed; the ruling is Yue's**
      (it adds a key to the event dict a callback receives). A property of
      the stream: `EventStream(callback=cb, preview=True)`, refused without a
      callback. No `fit` argument, because the stream already reaches the
      solver through every entry point (`fit`, `run_stage`, `refine`, a
      series) and is the one object that knows a callback is there. Each
      accepted `eval` then reaches the callback with a top-level `preview`
      key beside `data`: `two_theta` (the stage's fitted grid, a read-only
      view), `y_calc` (an ndarray, `y_obs − r·σ`) and `values` (every
      moving path, absolute). **`y_calc` reaches the in-process callback
      only**, never a file at `MAX_POINTS`: the JSON form costs 8 % of a
      FAP solve and 6.9 MB a fit on every sink (Task 1), and the per-stage
      `snapshot.json` already writes the curve to disk. The moving values
      ride the same way, so the opt-in changes no file at all. A joint fit
      refuses the option with a `ValueError` (its data rows are several
      histograms'); that is left for a follow-up issue.
- [x] Carry the moving-path values (coordinates and cell, absolute) on
      accepted `eval` events under the opt-in, on both drivers. The LM path
      needs the residual plumbed to `trial_cb`.
      *Done 2026-11-16:* `lm.minimize`'s `on_trial` takes the trial
      residual as a sixth argument; `_preview_builder`
      (`optimize/least_squares.py`) decodes θ and picks `moving_paths`,
      fixed once a stage.
- [x] Carry `y_calc` under the decided form. Test: on accepted events it
      equals `y_obs − r/sqrt_w` and lands within the documented 8e-6 of
      `predict()` at the event's values. The recorder's `events.jsonl` is
      byte-identical with the option on and off.
      *Done 2026-11-16:* the last accepted preview sits 4.38e-6 of the
      curve's maximum from `predict()` on both drivers (synthetic fixture);
      `RunRecorder.record` drops the key, and
      `test_a_preview_leaves_every_log_byte_identical` fails with the drop
      removed (checked once: the recorder latched on the ndarray).
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.
      *Done 2026-11-16:* six in `tests/test_events_viz_history.py` (both
      drivers, off, refused without a callback, a series, a joint fit) and
      one in `tests/test_telemetry.py`;
      `tests/output/wp1949_preview_obs_calc_diff.png` is drawn from one
      preview alone.
- [x] Manual (`using/refining.md` § events) and the event table in the
      skill's API index.
      *Done 2026-11-16, superseded in part:* the manual's events section is
      now `docs/docs/guides/watch.md` § Read the events yourself, and the new
      § Draw the fit as it runs sits under it. The skill's API index has no
      event table (`make_api_index.py` renders call signatures, and
      `EventStream` is not among them), so the row went to the reference
      below instead.
- [x] Skill: one row in the reference that documents `events=`. Nothing in
      the body.
      *Done 2026-11-16:* `references/watching.md` § 9d.11, synced to both
      committed copies.

## Acceptance

With the option on, a callback draws the curve and the atoms from accepted
`eval` events alone and matches `predict()` at those values within 8e-6.
With it off, every event and the recorder's log are byte-identical to
today's.

```sh
.venv/bin/python -m pytest tests/test_events_viz_history.py tests/test_telemetry.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #892.

## Handover log

- **2026-11-17** — review fix-ups on PR #1623. Task 4's "on accepted
  events it equals `y_obs − r/sqrt_w`" is now a test:
  `test_a_previewed_curve_is_its_own_events_residual` checks every
  preview against its own event's residual on a toy model, on both
  drivers. It fails when LM hands `on_trial` the incumbent residual, and
  when the preview lags one accepted evaluation, where the `predict()` bar
  still passes (checked once each). The manual, skill 9d.11 and the events
  docstring now say a magnetic fit's moment components are not in
  `values` (#1626). The 8e-6 bar's margin (7.45e-6 with an excluded
  region) is noted in the test as a property of `predict()`.
- **2026-11-16** — built, in PR #1623 (ghostshift runner). A program
  watching a fit can now draw the current curve, the atom positions and the
  cell from the event stream alone. It asks once, with
  `EventStream(callback=..., preview=True)`, and nothing written to disk
  changes. The reporter's alternative, a second refinement re-predicted every
  frame, costs about half a second a frame on a large MOF cell. Carrying the
  preview costs 0.02 ms an accepted evaluation. What is not settled is the
  spelling, which touches the event dict a callback receives. That is Yue's
  call, so Task 2 stays open with the proposal written into it.
  *Done:* Tasks 1 and 3-7 (each ticked with its note). Read-only review
  agent, four findings, all answered:
  - the joint-fit refusal now fires before a run is recorded;
  - the flag is a read-only property;
  - Pawley and Le Bail are tested, and the Le Bail step is documented;
  - magnetic moment components are not in `values`, which went to issue
    #1626 together with joint fits.
  *Measured:* Task 1's table. The last accepted preview sits from
  `predict()` by 4.38e-6 of the curve maximum in Rietveld mode (both
  drivers), 4.8e-20 in Pawley mode and 2.6e-4 in Le Bail mode. Le Bail's
  residual uses intensities frozen per solve. Gates:
  - fast suite on a Linux workstation: 14859 passed, 280 skipped, 32 xfailed, 0 failed,
    in 1130 s (`[dev]`-equivalent venv, Linux x86_64, `-n 4`, at
    `91cf502c1`, beside another job). The 7 added tests (9 cases) cost
    2.4 s together on that run;
  - canary (touched files + audit_table + help +
    docs_consistency + lm_solver, `-n 4`): 234 passed, 1 skipped in 38 s,
    436 MB;
  - `python -m tests.reader_output`: exit 0;
  - Vale (whole-manual CI step): 0 errors;
  - ruff clean.

  9 cases added: 8 in `test_events_viz_history.py` and 1 in
  `test_telemetry.py`. The telemetry test fails when the recorder's drop is
  removed (checked once). No generality judge: no `_audit.py` change and no
  heuristic (one off-by-default switch, tier `caller`).
  *Gotchas:* the recorder sits *inside* the caller's callback chain, despite
  the WP's original Context, so any new sink chained there must drop the key
  too (`events._without_preview`). The WP's manual path
  (`using/refining.md`) and "event table in the API index" are stale. The
  manual section is now `docs/docs/guides/watch.md`, and the index has no
  event table.
  *Next:* the spelling is decided (2026-11-17, accepted as built); the WP
  closes in the maintainer's handover after the merge. Issue #1626 holds the
  joint-fit and magnetic-moment follow-ups.
- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #892).
  Checked against the tree at `d80ca5f4`: an `eval` event carries only the
  free values on both drivers, the decode it filters already holds the
  coordinates and cell, and `y_calc` is recoverable from the residual the
  TRF wrapper holds. No open WP owns it: WP-1402, 1404, 1413 and 1438 (the
  live view and its cost) are closed, and WP-1322 aggregates a log after the
  fact. *Next:* task 1.
