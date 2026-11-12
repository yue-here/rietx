# WP-2125 — the pattern at values nobody has applied

Milestone: gui-overhaul · Status: ✅ 2026-11-09 — the route landed; the sliders and previews are the next piece
Depends on: 2123 soft (the shell the previews draw in)

## Goal

`rietx gui` serves a route that returns the calculated pattern, its background, each phase's
contribution and the reflection ticks at parameter values the person has not applied. Nothing
is committed and the project does not change. On the shipped examples it answers inside one
animation frame, so the Interactive tab's sliders can drag the model over the data.

## Context

### What the previews need, and the rulings behind them

The maintainer reviewed the preview modes on screen in the design rounds of 2026-11-06 to
2026-11-08. The prototypes are not published, so the designs this route serves are restated
here with their rulings.

1. **Sliders move the model by hand, and nothing refines until the person asks.** Ruled
   2026-11-07 (second Parameters review): a peak comparison panel of "sliders as visual
   fitting without refinement, against data and model". The fourth review renamed the tab
   Interactive, and its help line reads "Move the model by hand and watch the graphs".
2. **A full-pattern mode as well as single peaks.** Ruled 2026-11-07 (third review): the slider
   panel and the single-peak comparison plots are liked, and a full-pattern mode is wanted too.
3. **The comparison scale is fixed at the last fit.** Ruled 2026-11-07 (fourth review): "that's
   the logical expectation of someone trying to compare something". The route therefore serves
   curves only. The y range and every peak window stay the client's, read off the last fit.
4. **A preview never looks like a changed fit.** Ruled 2026-11-07 (fourth review): the graphs
   carry a title saying what they show. The prototype's title reads "Preview, not refined ·
   Rwp x %, last fit 9.28 %", so the route returns the preview's Rwp beside its curves.
5. **The slider ranges.** The prototype gives each slider a default range from the last fit:
   zero shift ±2 FWHM; a cell length the relative change that moves the highest-angle peak by
   2 FWHM; a scale ×0.5 to ×2 on a log track; a width term from half to double the peak width;
   the axial S/L and H/L from 0 to 3× their value. These ranges set how far a drag can take the
   frozen model, measured below.

The design rounds' handover listed this route as missing for the port. Its instruction: measure
the server route first, then settle against the alternative, which is shipping the prototype's
JavaScript peak model. That model matches rietx to 0.08 esd rms on fluorapatite (largest
difference 6.5 counts at 25.78°, page Rwp 9.29 % against rietx 9.28 %), using rietx's TCH
widths and a JavaScript port of rietx's FCJ axial-divergence images. It recalculates the whole
pattern in 17 ms on the main thread.

### How the forward model can be evaluated off a stage

A compiled model freezes four things at compile: the reflection list, the per-(line, reflection)
point windows, the FCJ quadrature node counts and the symmetry-op subsets (root CLAUDE.md,
frozen-per-stage discreteness). An evaluation at new values on a frozen model is exact only
while those still describe the new values. Two tools in `model/forward.py` already answer that:

- `window_sizing(model, values)` sizes every window and node count at `values`, reading the
  peaks the model draws there. It costs 0.09-0.25 ms on the examples.
- `rewindow(model, values)` builds a new frozen model with windows and nodes sized at `values`
  and everything else the compile's. It never touches a solve on the old model, so the
  invariant holds.

Each window is `k(η)·Γ` plus `WINDOW_MIN_DEG` (0.3°) of movement slack. The reflection list
covers `REFLECTION_MARGIN_DEG` (0.5°) beyond the fitted range. A list that holds a reflection
the new values push out of range is a harmless superset; one that misses a reflection pushed in
is wrong.

### Measured, 2026-11-09

`.venv` `[dev]`, darwin arm64, compiled tier on unless stated, run alone under the suite lock.
Ranges are min-max over 15 repeats (5 for compiles). `fap` is the fluorapatite example
(Cu Kα doublet, 5750 fitted points, 329 reflections, axial divergence on); `nac` is the 11-BM
example (22 003 points, two phases with 129 and 11 reflections, no axial term). Each was fitted
with its default plan first.

| Cost | fap | nac |
|---|---|---|
| one evaluation, pattern and background | 8.2-9.4 ms | 0.5-1.3 ms |
| the same with the compiled tier off | 89-118 ms | 2.8-3.4 ms |
| each phase's own contribution, all phases | 8.3-9.5 ms | 0.5 ms |
| a full compile at the working state | 13-16 ms | 16-18 ms |
| `rewindow` | 2.9-3.1 ms | 0.6-0.7 ms |
| `window_sizing` | 0.16-0.25 ms | 0.09-0.14 ms |
| edited values through the table's ties (`refresh_ties`, `decode`) | 0.22-0.38 ms | 0.24-0.38 ms |
| building the working table | 2.8-3.6 ms | 8.1-8.4 ms |
| HTTP on loopback, `GET /api/version` | 0.19-0.32 ms | 0.19-0.38 ms |
| HTTP on loopback, `GET /api/result/curves` (389 kB, 2.0 MB) | 1.5-1.7 ms | 6.5-6.9 ms |

Accuracy across each slider's default range, at ±¼, ±½ and ±1 of it. The reference is a fresh
compile at the new values. "Frozen" evaluates on the compile from the last fit's values;
"rewindowed" on `rewindow` of it.

| Slider | frozen, largest error | rewindowed, largest error |
|---|---|---|
| scale, both examples | 0 | 0 |
| zero shift ±2 FWHM, cell a ±2 FWHM at the top | fap 0.019 σ, nac 0.037 σ | fap 0.019 σ, from 2 extra reflections at the edge; otherwise ≤ 1e-13 σ |
| Caglioti U, W ×¼ to ×4; Lorentzian X ×½ to ×2 | fap 0.015 σ, nac 0.12 σ | 0 |
| Lorentzian size, ×½ to ×2 (nac: from 0) | fap 0.034 σ, nac 0.26 σ | 0 |
| axial S/L, fap 0.042 to 0.067 | 0.06-0.72 σ | 0 |
| axial S/L, nac from 0 to 0.0125-0.05 | 516-834 σ | 0 |

Three findings follow. A frozen window costs at most a few hundredths of an esd until the width
terms grow, because its 0.3° slack covers every position slider. An FCJ term switched on from
zero has no quadrature nodes in the frozen model, so the asymmetry is missing outright. And
`rewindow` reproduces a fresh compile to 1e-13 σ in every case, because it is the compile's own
sizing rule. The largest drawn-position move across all the default ranges was 0.15°, a third
of the reflection margin.

### The latency bar

A drag is an animation under Google's RAIL model (web.dev, "Measure performance with the RAIL
model", checked 2026-11-09). RAIL budgets 10 ms of work per frame at 60 frames a second, so
that motion looks smooth, and 100 ms for a response to feel immediate. It excludes drags from
the 100 ms response rule. The slider thumb moves natively with the pointer. The preview curve
follows whenever an answer lands, so its bar is the round trip: one 16.7 ms frame to follow the
thumb with at most a frame of lag, and 100 ms as the limit past which it trails visibly.

The route as built meets the frame bar on both examples, measured through the real server on
loopback with the compiled tier, 15 requests after 2 warm-ups, alone under the suite lock:

| Request | fap | nac |
|---|---|---|
| the last fit's values (`frozen`) | 11.0-15.7 ms | 2.1-2.4 ms |
| zero shift +1 FWHM (`frozen`) | 10.3-11.3 ms | 2.2-2.4 ms |
| Caglioti W ×4 (fap `rewindowed`, nac `frozen`) | 13.9-14.8 ms | 2.1-2.5 ms |
| zero shift +1° (`recompiled`) | 25.4-26.4 ms | 17.9-20.7 ms |
| in-process at the last fit's values | 10.0-10.6 ms | 1.5-1.6 ms |

The answer body is 205 kB on fap and 885 kB on nac. None of the time is spent on the page's
main thread, where the JavaScript model's 17 ms would sit. A recompile misses the frame bar and
stays inside 100 ms; the default slider ranges never reach one. Two cases trail further. On fap
a position edit of 2 FWHM can add one FCJ node to some reflection and goes `rewindowed`, about
13-14 ms. On nac an axial S/L moved off zero is `rewindowed` and exact, but one preview takes
about 140 ms (in-process, not under the lock), because the FCJ images on 22 003 points cost that
much in any fit. With the compiled tier off, fluorapatite's evaluation alone takes 89-118 ms.
The tier is a hard dependency with a warned fallback, so only an install whose wheel declined
sees that.

### The settlement: the server route

Settled by Claude under the measurements above and two written rules, root CLAUDE.md's one
authority for the residual (Ω's two builders, and a display that reads fields and never
computes) and its rule that every weighted residual divides by the result's own σ. The
alternative is shipping the prototype's JavaScript peak model, which is faster per tick (2-3 ms
for one slider) but differs from rietx by 0.08 esd rms and would need a second copy of every
correction a project can switch on. The server route is exact to rietx's own window tolerance
and inside the frame bar, so the duplicate buys nothing the person would see. The browser build
planned after the desktop app runs rietx itself in Pyodide, where the route becomes an
in-process call. Whether its numpy path meets the bar there is that build's measurement.

### What the route does

`POST /api/preview` with `{"values": {path: number}}`, every path one `PATCH /api/params` would
accept. Each answer:

1. Builds, once per working state, the working table and a compile at the project's settings.
   The cache key is the history head, the mode, the 2θ limits and the excluded regions, so any
   verb that moves the model or the protocol invalidates it.
2. Refuses what `set_values` refuses, with the same sentences: an unknown path, a locked or tied
   one, a value outside its bounds. The check is `set_values`' own, factored out so the two
   cannot disagree.
3. Writes the values into the table, follows the ties, decodes, and puts the table back.
4. Chooses how to evaluate, cheapest first, and says which in `evaluated`:
   - `frozen` when every window sized at the new values, slack removed, lies inside the frozen
     one and no node count grows;
   - `rewindowed` when a window or node count would grow, through `rewindow`;
   - `recompiled` when any reflection's drawn position moves by `REFLECTION_MARGIN_DEG` or more,
     through a compile at the new values, since the frozen list may then miss a reflection.
5. Returns a packed body (`viz/packed.py`): the fitted channels' 2θ, the calculated curve, the
   background, each phase's contribution, and in the header the Rwp at these values, the ticks
   and their Miller indices from `refine`'s own tick builder, and `head`.

The route answers 409 while a run is in flight, like every route that compiles. It writes
nothing: the project directory, the history and `project.json` stay byte for byte.

### The tier of each rule this WP adds

A numerical setting, the first kind of ambiguity: it sets how close the drawn curve is to what
applying the values would give, and chooses no model. The window and node branches are the
compile's own sizing rule asked at the new values. The chain rests on two tier-3 rows,
`WINDOW_MIN_DEG` and `REFLECTION_MARGIN_DEG`, so it is not tier 1 as first written here
(generality review, 2026-11-09). Two gaps it leaves are stated, not measured:

- The recompile trigger waits until a listed reflection has moved 0.5°. A fresh compile at the
  new values lists every reflection within 0.5° of the range, so a reflection that started just
  past the margin and moved inward by δ is missing from a frozen answer. Its tail inside the
  range sits at least 0.5° − δ from its centre. The default slider ranges move a peak at most
  0.15°, where the measured cost was 0.019 σ. Moves from 0.15° to 0.5° are not measured.
- A node count between the compile's and the sizing rule's own count at the base values stays
  frozen. That error is not measured either.

A wavelength edit keeps the compile's f′ and f″ on the frozen and rewindowed paths. No slider
in the design moves a wavelength.

## Non-goals

- The Interactive tab, the Pattern and Peaks previews and their drawing. They are piece 4's
  client half, in `gui/src`, after the shell (WP-2123) lands.
- A route serving the background preview's matrices. It is piece 5's, the Background tab. The
  matrices are a basis, a penalty and the band, which this route's machinery does not build.
- Per-peak curves. The single-peak comparison plots draw the total curve inside a peak's
  window at the last fit's scale, which this route serves.
- Le Bail and Pawley intensities moving with a slider. A preview holds the head's extracted
  intensities fixed, as `replay` does.

## Tasks

- [x] `src/rietx/gui/preview.py`: the cache, the value check, the three evaluation paths and the
  packed answer; `GuiSession.preview` and the `POST /api/preview` route
- [x] `Refinement.set_values`' refusals factored into one check the route calls
- [x] `CompiledModel.evaluate_parts`: the total, the background and each phase from one Bragg
  pass, bit-identical to `evaluate`
- [x] Tests: each path chosen where it should be, each answer equal to a fresh compile at the
  values, nothing written, the 409, the refusals; the route's latency measured end to end
- [x] Manual: the route in the GUI reference chapter, so `tests/test_gui_manual.py`'s partition
  covers it; the practice survey in `docs/practice.md`
- [x] Skill: none, because the route serves the GUI and an agent with a shell calls
  `Refinement` directly (root CLAUDE.md, one integration surface)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_preview.py tests/test_gui_server.py tests/test_gui_manual.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The preview's end-to-end latency on both examples is quoted in the handover entry as a range,
measured alone, with the compiled tier on.

## References

- Google, web.dev, "Measure performance with the RAIL model": the 10 ms frame and 100 ms
  response budgets, and drags counted as animation.
- Finger, Cox & Jephcoat (1994), *J. Appl. Cryst.* **27**, 892-900: the axial-divergence
  asymmetry whose quadrature nodes a frozen model lacks when S/L starts at zero.

## Handover log

### 2026-11-09 — the route built, reviewed and handed over

The GUI can now ask rietx for the calculated pattern at values nobody has applied, and get it
back inside one animation frame on both shipped examples. Nothing is written, so a slider can
drag the model over the data without moving the project or its history. The server route won
against shipping the prototype's JavaScript peak model: it is exact to rietx's own window
tolerance, it costs the page's main thread nothing, and it keeps one copy of the physics. The
sliders and the two previews that draw from it are the next piece, in `gui/src`.

*Done.* Every task, in PR #1479. `POST /api/preview` in `gui/preview.py`, with `GuiSession.preview` and one
route line; `Refinement._refuse_value_edits`, the check `set_values` and the preview share;
`CompiledModel.evaluate_parts`, bit-identical to `evaluate`; `_tick_rows(support=False)`; a
`component=` argument on `window_sizing` for a magnetic family; the route in the GUI reference
chapter; the hand-fitting survey in `docs/practice.md`. Tests: `tests/test_gui_preview.py`, 29.

*Measured.* The tables in § Context, all `[dev]`, darwin arm64. The route's round trip through
the real server: fap 10.3-15.7 ms `frozen`, 13.9-14.8 ms `rewindowed`, 25.4-26.4 ms
`recompiled`; nac 2.1-2.5 ms `frozen`, 17.9-20.7 ms `recompiled`. The timing ran on the tree
before the review fixes, which add checks only for a magnetic phase. Fast suite on the merged tree (main at 5ae35232c), `[dev]` darwin arm64, alone under the suite lock: 14369 passed, 416 skipped, 32 xfailed in 10:15. The 29 added cases are all passes and cost 14.7 s in that run, 8.6 s of it the first test, which builds both examples' fits for the module.
`python -m tests.reader_output` exit 0, unchanged against the merge-base.

*Review.* `/code-review high --fix` found nine problems and fixed six in one commit: a magnetic
family that grows or appears from zero now forces a recompile; a recompile carries the cached
compile's orbit split, moment frames and σ; the header names every row an edit moved; a bound
refusal on the recompiled path is a 400; one context manager sets and restores the table. It
left two. The preview sends every fitted channel without the curves route's decimation past
150 000 channels, which is a wire-contract question for the client half. A tied row pushed past
its bounds is drawn on the frozen and rewindowed paths, not refused, since refusing would
restate `apply_to_models`' sentence.

*Generality.* The judge rated the evaluation chain weak as a tier claim and the tick flag holds.
Its sections, unedited in substance: the window branch could not be faulted, because a frozen
answer is accepted only where each peak's core still fits its frozen window; the recompile
trigger is looser than a fresh compile's list, leaving an edge gap at moves between 0.15° and
0.5° that nothing measures; the node-count comparison against the larger of two counts is a
hysteresis no test covers; the chain rests on two tier-3 rows, so it is not tier 1; no `_audit`
row is possible, since the table excludes a fallback chain. Author's answer: § The tier of each
rule now says all of that, and the module docstring no longer claims no threshold is new. The
tick flag decides nothing anyone reads.

*Settled by Claude.*
- The server route over the JavaScript model, under the measurements and root CLAUDE.md's one
  authority for the residual. Alternative: ship the JS model, 2-3 ms a tick, 0.08 esd rms off.
- The number 2125, as the shift assigned it, though the milestone record claims 22xx for the
  pieces after the first. Alternative: 2201.
- The branch starts at WP-2123's filing commit (`e49f3d9c3`), a fast-forward of `main`, so the
  milestone this file names exists on the branch. Alternative: `Milestone: unscheduled`, moved
  later.
- The route is idle-only (409 while a run is in flight), like `report`. Alternative: serve
  previews during a run off the models a stage is writing.

*Next.* The client half of piece 4 (the Interactive tab, the Pattern and Peaks previews), after
WP-2123 merges. It should keep one request in flight and send the latest values when it lands,
so a fast drag never queues. Then piece 5's background matrices route, which this machinery
does not build. Measuring the edge gap (moves of 0.15-0.5° near a strong reflection at the range
edge) would lift the chain's tier.

- **2026-11-09** — filed by a ghostshift runner, with the measurements above. No open WP owns
  the route: the milestone record lists piece 4 as not yet filed, and WP-2123 builds the shell
  only. The number is 2125, as the shift assigned it, though the milestone record claims 22xx
  for the pieces after the first. The branch starts from WP-2123's filing commit, which carries
  the milestone this file names.
