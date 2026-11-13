# WP-1008 — GUI server, session model, `rietx gui`

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1004, WP-1005, WP-1006, WP-1007

## Goal

`rietx gui [PROJECT.rex]` serves a localhost web app whose HTTP surface
covers the full loop — project, params, plan, run/cancel, events, result,
report, history, export — with every verb a plain method on a `GuiSession`
so the transport layer stays swappable (the Tauri seam).

## Context

- **Stdlib `http.server`, decided.** It is the repo precedent twice —
  `compare_app.py` (`ThreadingHTTPServer` at `:172`, handler factory
  `_handler(state)` at `:113`) and `watch.py` (`:117`, port 8899). Zero new
  deps preserves the base-install discipline (`[gui]` = plotly only);
  offline/CSP/air-gap safe; a single-user localhost app with ~25 routes
  gains nothing from FastAPI/uvicorn (+15 MB and async ceremony). SSE works
  fine on `ThreadingHTTPServer`. Snappiness lives in payload design and the
  frontend — `rietx compare` already proves the loop feels instant.
- `src/rietx/gui/session.py` — `GuiSession` holds the `Project`,
  `Refinement`, a lock, the run state machine (`idle | running |
  cancelling`), the `CancelToken` (WP-1006), and a seq-numbered event ring
  buffer with a `threading.Condition` for SSE followers; one worker thread
  (the `compare_app._State` pattern, `:35` — lock, pending queue, daemon
  worker). **Every verb is a plain method here and `server.py` is only
  transport** — that is the Tauri/framework seam. Mutating verbs return 409
  while a run is in flight, so the GUI *structurally* cannot mutate a
  running fit's compiled state (frozen-per-stage discreteness, enforced at
  the session boundary rather than by discipline).
- Routes (all bound 127.0.0.1; Host header checked against DNS rebinding):

  ```
  GET  /  /assets/*  /plotly.js        (plotly from the installed package — compare's trick, compare_app.py:102)
  GET  /api/capabilities  /api/version     POST /api/shutdown
  POST /api/project/new|open   GET/POST /api/project(/save)   GET /api/recent
  POST /api/upload/pattern|cif|instrument                      (lands in WP-1014)
  GET/PATCH /api/structure  /api/instrument  /api/params    GET/PUT /api/plan   GET /api/plans
  POST /api/run  /api/cancel   GET /api/run/state
  GET  /api/events           (SSE; ?since=seq replay; ?poll=1 JSON fallback)
  GET  /api/result   /api/result/window?lo=&hi=   /api/report   POST /api/report/apply   (apply lands in WP-1012)
  GET  /api/history  /api/history/diff  /api/history/compare
  POST /api/history/{checkout,branch,tag,annotate}
  GET/PUT /api/textdoc       GET /api/structure3d       POST /api/export/{cif,reflections,qpa,html,result_json}
  ```

  This WP lands the session + routing skeleton and every route that needs
  only WP-1004…1007; routes marked for later WPs 404 cleanly until then.
- History verbs live on `Refinement` (`checkout` `refine.py:182`, `branch`
  `:202`, `merge` `:250`, `cherry_pick` `:309`), tree read-side on
  `RefinementTree` (`compare` `history/tree.py:231`, `diff` `:249`).
- Boot: `rietx gui [PROJECT.rex] [--port 8731] [--no-open] [--machine]`.
  Compare owns 8730 (`compare_app.py:32` `DEFAULT_PORT`); fall back to
  port 0 if busy. `--machine` prints a JSON boot line (port, project path,
  pid) — the Tauri seam. One project per process. CLI dispatch is
  hand-rolled in `cli.py:13` (`watch` `:26`, `compare` `:31`, `html` `:35`)
  — add `gui` there, argparse inside `gui/server.py:main` like the siblings.
- Run events are teed to `<project>/live/events.jsonl` so `rietx watch`
  and the GUI stay two views of one stream.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): the HTTP routes are declared
**provisional** at v1.0 — schemas frozen, wire surface not (recorded in
WP-1003's `### Inherited`). Don't burn effort on wire-level backcompat here.

From **WP-1006** (landed 2026-07-30): the run machinery is `CancelToken` (dumb:
`cancel()` / `is_set()` / `reset()`, reusable) and `RefinementCancelled`, both
exported from `rietx`. `fit`, `run_stage` and `refine` all take
`events=`/`cancel=`. Three things the session model should encode rather than
rediscover: (a) a cancelled run **raises**, it does not return a partial result
— the response is built from `exc.completed_stages` and `exc.node_id`, and that
node id is where the working state stands, so it is what a "resume" button
checks out; (b) `stage_start` carries **1-based** `index` and `n_stages`, so
progress needs no bookkeeping server-side; (c) a cancelled run's `fit_end`
carries `status="cancelled"` and **no** `rwp`/`gof` — read the event payload
with `.get`, never by unpacking a fixed shape, because that rule is what makes
event fields addable without a schema version bump.

From **WP-1005** (project container, landed 2026-07-30) — the session's project
half is done, and four of its decisions are load-bearing for the routes:

- `Project.create/open/save` + `project.fit(**kw)` / `project.run_stage(stage,
  **kw)`, which already supply the data *and* the document's plan/mode/limits —
  so `POST /api/run` should go through them rather than calling
  `Refinement.fit(project.data, …)` itself and re-deriving the settings.
  `project.live_dir` is where the `live/events.jsonl` tee belongs, and
  `project.exports_dir` where the export routes should write by default.
- **`GET/POST /api/project` is a *settings* endpoint, not a state endpoint.**
  `project.json` holds patterns/plan/mode/limits/`excluded_regions`/`ui`;
  `history.jsonl` holds the model, and its head is the working state. So
  `/api/params` and `/api/structure` read the refinement (whose every edit
  auto-commits a node), and `POST /api/project/save` persists only the document.
  Consequence for the UI: **there is nothing to warn about on close** — no
  unsaved model state exists — and a "save" button is honest only about
  settings. `ProjectDoc.ui` is the untyped dict the frontend owns; use it for
  disclosure level and panel layout rather than inventing a parallel store.
- **`Project.open` takes `backend`/`solver` as arguments** (they are not
  document fields, so a jax-saved project still opens where jax is absent). The
  session, not the document, decides them — a `--backend` flag or a `ui` key
  the boot path reads, and it must survive a reopen the same way.
- `Project.open` refuses — with distinct messages — a missing pattern, changed
  bytes, a same-bytes/different-numbers reader change, a history tree recorded
  against another pattern, a missing log, a future format major, and a
  multi-pattern document. **Surface the message; do not collapse them into "could
  not open project"**, because each names a different remedy and the GUI is the
  only place a user will ever read it.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): **reserve these
routes now** (404 until WP-1027 fills them) so the shape is settled before the
frontend scaffold lands — `GET/POST /api/peaks`,
`POST /api/peaks/{add,remove,move,flag,refit}`, `POST /api/index`,
`GET /api/index/result`, `POST /api/index/adopt`. The peak verbs are cheap and
synchronous; **`/api/index` is long-running and goes through WP-1006's run
state machine** (cancel, SSE progress, 409-while-running), so wire it to the
same machinery as a refinement run even though it is not one.

## Non-goals

- No frontend (WP-1010) — this WP is testable entirely over HTTP with the
  static dir empty.
- No auth/TLS/multi-user — localhost, one user, Host-header check only.
- No upload sniffing (WP-1014), no textdoc semantics (WP-1009), no report
  apply (WP-1012), no series (WP-1016) — their routes arrive with them.

## Tasks

- [x] `src/rietx/gui/{__init__,session}.py`: `GuiSession` — verbs, lock,
      state machine, ring buffer + `Condition`, worker thread, 409 rule.
- [x] `src/rietx/gui/server.py`: route table → session verbs; SSE with
      `?since=` replay and `?poll=1` fallback; Host-header check;
      `/plotly.js` from the installed package; `POST /api/shutdown`.
- [x] `cli.py`: `gui` subcommand (`--port/--no-open/--machine`, port-0
      fallback); tee run events to `live/events.jsonl`.
- [x] `tests/test_gui_server.py`: real server on port 0 — project create →
      params PATCH → run → SSE events → result → history checkout → export;
      409 while running; cancel honoured; Host-header rejection.
- [x] *(added)* `strategy.staged.resolve_plan` and `viz.compare.decimation_index`
      made public — the two seams this WP would otherwise have restated.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- `compare_app.py` — `_State`, `_plotly_js`, port; `tests/test_compare_ui.py`
  `server` fixture (`:211`) — the port-0 live-server test recipe to copy.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **GUI** (WP-1008, `gui/`) is `rietx gui [PROJECT.rex]` — stdlib
`http.server` on 127.0.0.1, the third such app here after `watch` and `compare`.
`gui/session.py` holds `GuiSession`, where **every verb is a plain method and
nothing knows about HTTP**; `gui/server.py` parses a path, calls one, serialises
the answer, and is the layer a Tauri host would replace. Its route table plus
`RESERVED_ROUTES` (paths settled here, behaviour owed by a later WP, 404 naming
it) are the complete wire surface, held disjoint by test. Four rules: mutating
verbs return **409 while a run is in flight** — frozen-per-stage discreteness
enforced structurally rather than by discipline, and that refusal outranks body
validation; **settings persist on the verb**, not on `save`, which is what keeps
WP-1005's "nothing to warn about on close" true; the **run state is not an
event** (a failed fit emits no `fit_end`, and `EventKind` is closed) so it
travels beside them as its own SSE frame type while `live/events.jsonl` stays the
one stream `watch` tails; and `/api/result` omits the curves, which
`/api/result/curves` sends once over every channel as float64 arrays (WP-1461,
D4), decimating past `CURVES_CEILING` through the *same*
`viz.compare.decimation_index` the comparison UI uses — whose count is a
budget, not a ceiling. **A multi-verb route is all or nothing** (WP-2126): its
verbs run on `session.rehearse`'s copy first. `strategy.staged.resolve_plan` (preset name + mode → plan)
is likewise one function, previously inline in `fit` and duplicated in
`sequential`.

## Handover log

- **2026-07-30 — complete.** 30 tests in `tests/test_gui_server.py` (2.6 s
  serial), fast suite 1097 passed / 107 skipped in 30 s on a numpy-only
  `[dev]` venv, ruff clean, and the real CLI exercised by hand: `rietx gui
  --machine --no-open` prints `{"url": …, "port": 8731, "project": null, "pid":
  …}`, `/` serves the placeholder, `/plotly.js` 4.85 MB out of the installed
  package, `/api/peaks` 404s naming WP-1027, `Host: evil.test` 403s, and
  `POST /api/shutdown` stops the process.

  **Done:** `gui/session.py` (35 verbs, lock, `idle|running|cancelling`,
  4096-event ring + `Condition`, one worker thread), `gui/server.py` (route table
  as data, SSE + `?since=` replay + `?poll=1`, Host/Origin check, static +
  `/plotly.js`, port-0 fallback, `--machine`), `cli.py gui`, and the two seams
  (`resolve_plan`, `decimation_index`).

  **Five decisions that were not in the charter:**

  1. **The run state is not an event.** A *failed* fit emits no `fit_end` (only
     success and cancel do), so a follower watching engine events alone hangs on
     the one case it most needs to see. `EventKind` is closed and WP-1006
     declined to add a kind for a guess, so the state travels beside the events:
     SSE frame type `state` vs `event`, a `state`/`run` key in the poll payload,
     and nothing extra written to `live/events.jsonl`. That keeps "the GUI and
     `rietx watch` are two views of one stream" literally true.
  2. **Settings persist on the verb, not on Save.** WP-1005 made "there is
     nothing to warn about on close" true for the model; a settings route that
     deferred to `Project.save` would have made it false again for the plan and
     the excluded regions. `POST /api/project/save` stays as an honest flush.
  3. **A state refusal outranks a body complaint.** Found by the test: with a run
     in flight, `PATCH /api/structure` with an invalid structure returned 400
     "structure has no phases" — true, and useless, because the real problem was
     the running fit. `_require_idle()` now runs before validation in both model
     patches.
  4. **`/api/history/branch` names a fork point.** This DAG has no moving refs,
     only `head` and tags, and a fork appears when you run from a node that
     already has a child — so a `branch` route that created something would be
     lying, and one that only checked out would be a second spelling of
     `checkout`. It is checkout + `tree.tag`, documented as such.
  5. **The preset a project chose is not recoverable from its document** —
     `ProjectDoc.plan` is an expanded `PlanSpec` with no name. `GET /api/plan`
     therefore *derives* `preset` by comparing the stored spec against all seven
     registry presets (`null` for an edited plan), the same
     derived-predicate style as `capabilities().features`. Selecting a preset
     stores it expanded **through the mode**, because `Project.fit` passes
     `doc.plan` verbatim: picking `mccusker_default` in Le Bail mode has to store
     `profile_only`'s stages, and doing it in the editor makes the mapping
     visible instead of surprising.

  **Two measured facts the frontend needs:**

  - `max_points` on `/api/result/window` is a **budget, not a ceiling** — the
    index set is three curves' per-bucket extrema over `max_points // 2` buckets,
    so it can overshoot (measured: 4132 for a 4200-point pattern at 4000).
    `n_returned` is the length to trust.
  - **A `checkout` discards the fitted curves** (`Refinement.checkout` clears
    `result_`/`_model`, correctly — they described values it just replaced), so
    `/api/result`, `/api/report` and every export answer `NO_RESULT` until the
    next run. A history panel must expect that, and it is asserted rather than
    left to be discovered.

  **Gotchas.** (a) `Project.create` and a subsequent `Project.open` of the same
  directory are two objects over one set of files; a test asserting against the
  created one passes by accident until they disagree (cost one debugging round —
  `_open()` in the test module returns `session.project` for that reason).
  (b) `ThreadingHTTPServer.serve_forever` polls at 0.5 s, which is pure teardown
  cost in a module with ~15 server fixtures: 14 s → 2.6 s with
  `poll_interval=0.02`. (c) SSE stays on `protocol_version = "HTTP/1.0"` so a
  streaming body needs neither `Content-Length` nor chunked framing; EventSource
  reconnects on close, which `?since=` then replays.

  **Not done, deliberately:** nothing. The frontend is WP-1010 and the reserved
  routes are listed in `session.RESERVED_ROUTES`, which
  `test_no_route_is_declared_twice` holds disjoint from `ROUTES`.

- **2026-07-29** — created from the v1.0 GUI plan. Precedents verified: the
  `_State` pattern, the `/plotly.js` trick, port ownership (compare 8730,
  watch 8899), and the hand-rolled CLI dispatch.
