# WP-1402 — the live picture costs 3.5 MB a stage, and the fit pays it

Milestone: unscheduled · Status: ⬜
Depends on: 1401 (the reader that displays what this writes)

## Goal

A stage's live picture becomes about 100 kB of numbers instead of a 3.5 MB
self-contained web page, the viewer loads plotly once and redraws in place, and
recording a live view stops needing plotly at all. That is what makes WP-1403's
automatic recording affordable, and it is worth doing even if 1403 never ships.

## Context

`src/rietx/viz/live.py:54-61` — `LiveSession.write_snapshot` calls
`fig.write_html(..., include_plotlyjs=True, full_html=True)` after **every
stage**. Three costs, and only the first is obvious:

1. **The fit waits on it.** The page is written on the fit's own thread, so each
   stage stops to serialise about 3.5 MB, the whole of plotly inlined afresh each
   time. A five-stage fit writes it five times.
2. **The browser rebuilds the plot from scratch.** `watch.py`'s page reloads the
   iframe when `fit.html`'s `Last-Modified` moves, so the reader's zoom is lost
   every stage — precisely when they were looking at something.
3. **Recording needs plotly installed.** A base install cannot record a live view
   at all, because building the figure is how the view is stored.

The alternative is to store the numbers and let the viewer draw them. The fit
pays a decimation and a small JSON write; the page loads plotly once from the
installed package, the way `gui/server.py:350` and `compare_app.py:103` already
do; and recording imports no plotting library.

### The break, and what it does not cost

`fit.html` stops being produced. Stated plainly because the few-users policy is
that breaks are cheap **and every one is recorded**:

- A `fit.html` already on disk still opens in a browser, and WP-1401's viewer
  still displays one where it finds one. That is pinned by a test, or the
  back-compat promise is untested prose.
- `rietx html <result.json> <out.html>` and `viz.html.write_html` are untouched,
  so the self-contained, emailable page remains a **capability**. What stops is
  producing it unasked.
- `tests/test_events_viz_history.py`'s `test_live_session_and_watch_server`
  (line 469) is the one test asserting `fit.html`: it checks the file exists
  (478) and then fetches it over HTTP from the served directory (491). Both
  change here. The `fit.html` at line 129 is `write_html`'s own output and is
  **not** affected.
- `docs/manual/using/cli.md:115` says watch "serves the directory a
  `LiveSession` writes, with a self-refreshing plot". The sentence stays true;
  the manual's fuller account is WP-1406's.

`LiveSession` is public, so this is the largest public change in the whole track
— larger than any name WP-1403 adds. Say so when it lands.

### The one authority for which points survive

`viz/compare.py:948` `decimation_index(tt, curves, max_points)` keeps each
bucket's min **and** max of every curve, never plain striding, because striding
drops peak tops. Its docstring already names why it is public: "a second
consumer arrived… a second implementation would be a second answer to *which
points survive*, the one question a plot must not disagree with the comparison
UI about." This is the third consumer and it fits that reason exactly.

It buckets in a python loop, so its per-stage cost is **measured** in WP-1404
rather than assumed free.

### Three conventions the snapshot must not get wrong

- **`delta` is always Δ/σ**, divided by the σ the `CompiledModel` stored, which
  `refine` copies to `result.sigma` verbatim. A result's σ is a lookup, never a
  re-derivation (WP-1029). The `weighted` flag reports whether σ was *measured*
  (`DataRef.has_sigma`) and changes only the axis title, because Δ/σ is what the
  fit minimised either way.
- **Ticks carry every emission line's positions**, not just the primary, or
  Layer 0 flags each Kα2 peak as an unindexed impurity — a real bug once caught
  by the misfit-injection suite. The loop in `viz/live.py:44-52` already does
  this; reuse it rather than rewriting it.
- A per-phase tick cap is a **reported** cap, never a silent one, the way
  `MAX_CANDIDATE_TICKS` is: carry the untruncated count beside the list, because
  a silent cap reads as coverage.

### The call site, and two defects in it

`refine.py:1980-1982`:

```python
if stream is not None and hasattr(stream, "write_snapshot"):
    # live monitoring (viz.live.LiveSession): rewrite the HTML view
    stream.write_snapshot(model, table, outcome, stage.name)
```

- It is inside `_run_plan` only, so **`run_stage` never refreshes the picture**.
  A caller driving one stage at a time — which is what `report/apply.py`'s
  recipes and the GUI's stage verb both do — gets events and no plot.
- It tests `stream`, so once WP-1403 chains a recorder onto a caller's own
  `EventStream.callback`, `hasattr` is False and no snapshot is written at all.

Fix both by building the sink list **once**, explicitly, and calling it from both
loops. Duck typing stays — it is what lets `viz/live.py` work with no import from
`refine.py` into `viz/` — what changes is that the candidate set is declared
rather than being whatever `stream` happened to be. In `run_stage` the snapshot
goes **before** `_record`, so a watcher never shows a state the history log has
not yet claimed.

### One shared plotly route

`gui/server.py:350` and `compare_app.py:103` each have their own `_plotly_js()`,
serving plotly out of the installed python package so a page works air-gapped and
no dist vendors it. A third copy in `watch.py` would break "two things are
written once and consumed everywhere". One small module, three call sites,
separately committable — and this is the moment, because the third copy is about
to be written.

Note what is *not* being consolidated: the three servers' `_send`/`_json`
helpers, route dispatch and handler factories stay deliberately duplicated
(`gui/CLAUDE.md` records that as a choice). This is one shared function, not the
start of a framework.

## Non-goals

- **No automatic recording.** WP-1403. This WP changes what a `LiveSession`
  writes when a caller asks for one; it does not make anyone ask.
- **No cancel and no verbs.** WP-1405.
- **No manual or skill prose.** WP-1406, which carries the whole break notice.
- **No `EventStream.emit` change.** Buffering is WP-1403's, and it must not
  arrive early by accident here.
- **No new `EventKind`.** Nothing here is an event.

## Tasks

- [ ] `viz/plotlyjs.py`: one `plotly_js()`, with `gui/server.py` and
      `compare_app.py` switched to it and their local copies deleted. Lands
      alone, so a regression here is bisectable away from the rest.
- [ ] The snapshot writer: decimated `two_theta` / `y_obs` / `y_calc` / `y_bkg`
      / `delta`, ticks per phase with the untruncated count beside them, the
      stage's statistics, `weighted`, and the schema version. Atomic
      `tmp.replace`, as `write_snapshot` already does — never a torn read.
      Every field's writer named at review.
- [ ] `viz/live.py` keeps `LiveSession` as a thin shim over the shared writer,
      writing into a flat directory (what `using/cli.md` documents). **Plotly
      leaves this module entirely**, pinned by a test that puts `None` into
      `sys.modules["plotly"]` and records a run.
- [ ] `refine.py`: the explicit sink list, `_run_plan` switched to it, and the
      missing `run_stage` call site added before `_record`. A test per defect,
      because neither is covered today.
- [ ] `fit.html` stops being written. Rewrite
      `test_live_session_and_watch_server` to assert `snapshot.json`, and
      add the second test — a pre-existing `fit.html` is still served — without
      which the back-compat claim is prose.
- [ ] Report the measured size of one stage's snapshot on each of `nac`,
      `cpd-2` and `trigger`, as a range. "How big does this get" is the first
      question a reader asks and it must not be answered with an invented
      number.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`, looked at: the snapshot's
      curves must be the fit's curves, and a decimated plot that has dropped a
      peak top is visible long before it is assertable.
- [ ] Skill: **none**. WP-1406 carries the track's skill change.

## Acceptance

A recorded stage produces a snapshot whose decimated curves reproduce the fit's,
in a process where plotly cannot be imported.

```sh
.venv/bin/python -m pytest tests/test_events_viz_history.py tests/test_compare_ui.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Snapshot sizes reported in the handover as a range with venv and platform named.

## References

- WP-1029 — every weighted residual divides by `RefinementResult.sig()`; σ is a
  lookup, never a re-derivation; `weighted` is `DataRef.has_sigma`.
- WP-1008 — `/api/result/window`, `decimation_index`'s second consumer.
- WP-1120 — two spellings of Ω one to two ulp apart, and the rule that a caller
  owns which it reproduces. The same discipline applies to a plot's points: one
  authority, passed in, never re-implemented.
- `gui/CLAUDE.md` — why the three servers duplicate their transport helpers, and
  therefore what this WP is and is not consolidating.

## Handover log

- **2026-09-13** — created. Split from WP-1401 so that the `fit.html` break, the
  largest public change in this track, lands in a commit of its own rather than
  inside a larger one. It is worth shipping on its own terms: even if WP-1403's
  automatic recording never happens, a live view that costs 100 kB instead of
  3.5 MB, keeps the reader's zoom and needs no plotting library to record is
  strictly better than what a caller gets today.
