# WP-2125 — the pattern at values nobody has applied

Milestone: gui-overhaul · Status: ⬜
Depends on: 2123 soft (the shell the previews draw in)
Priority: P2 2026-11-09 — the server half of the milestone's fourth piece; the sliders and both previews wait on it

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

The server route meets the frame bar on both examples with the compiled tier: about 9-10 ms on
fluorapatite (evaluation, the window test, the ties and loopback HTTP) and about 1-2 ms on NAC.
It spends none of it on the page's main thread, where the JavaScript model's 17 ms would sit.
With the compiled tier off, fluorapatite takes 89-118 ms and misses the frame bar. The tier is a
hard dependency with a warned fallback, so only an install whose wheel declined sees that.

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

The three-way choice in step 4 is physics, not judgement. Each branch is the compile's own
rule (`window_sizing`, the generation margin) asked at the new values. No threshold is new.

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

- [ ] `src/rietx/gui/preview.py`: the cache, the value check, the three evaluation paths and the
  packed answer; `GuiSession.preview` and the `POST /api/preview` route
- [ ] `Refinement.set_values`' refusals factored into one check the route calls
- [ ] `CompiledModel.evaluate_parts`: the total, the background and each phase from one Bragg
  pass, bit-identical to `evaluate`
- [ ] Tests: each path chosen where it should be, each answer equal to a fresh compile at the
  values, nothing written, the 409, the refusals; the route's latency measured end to end
- [ ] Manual: the route in the GUI reference chapter, so `tests/test_gui_manual.py`'s partition
  covers it; the practice survey in `docs/practice.md`
- [ ] Skill: none, because the route serves the GUI and an agent with a shell calls
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

- **2026-11-09** — filed by a ghostshift runner, with the measurements above. No open WP owns
  the route: the milestone record lists piece 4 as not yet filed, and WP-2123 builds the shell
  only. The number is 2125, as the shift assigned it, though the milestone record claims 22xx
  for the pieces after the first. The branch starts from WP-2123's filing commit, which carries
  the milestone this file names.
