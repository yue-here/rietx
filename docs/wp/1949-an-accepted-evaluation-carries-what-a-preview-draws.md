# WP-1949 — an accepted evaluation carries what a preview draws

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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
- [ ] Decide the spelling and record it as `Decided YYYY-MM-DD:`. The
      options are a `fit(..., eval_payload=...)` flag, or a property of the
      callback the caller passes. Decide too whether `y_calc` reaches only
      an in-process callback (ndarray, never the file sink) or also the file
      at `MAX_POINTS`.
- [ ] Carry the moving-path values (coordinates and cell, absolute) on
      accepted `eval` events under the opt-in, on both drivers. The LM path
      needs the residual plumbed to `trial_cb`.
- [ ] Carry `y_calc` under the decided form. Test: on accepted events it
      equals `y_obs − r/sqrt_w` and lands within the documented 8e-6 of
      `predict()` at the event's values. The recorder's `events.jsonl` is
      byte-identical with the option on and off.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.
- [ ] Manual (`using/refining.md` § events) and the event table in the
      skill's API index.
- [ ] Skill: one row in the reference that documents `events=`. Nothing in
      the body.

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

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #892).
  Checked against the tree at `d80ca5f4`: an `eval` event carries only the
  free values on both drivers, the decode it filters already holds the
  coordinates and cell, and `y_calc` is recoverable from the residual the
  TRF wrapper holds. No open WP owns it: WP-1402, 1404, 1413 and 1438 (the
  live view and its cost) are closed, and WP-1322 aggregates a log after the
  fact. *Next:* task 1.
