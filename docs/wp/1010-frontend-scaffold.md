# WP-1010 — Frontend scaffold: build, committed dist, shell, plot, console

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1008

## Goal

A `gui/` TypeScript workspace whose build writes committed static assets
into `src/rietx/gui/static/`, plus the app shell, the obs/calc/diff plot
panel, and the console — the foundation every later frontend WP builds on.
Users installing the wheel never need node.

## Context

- **Svelte 5 (runes) + Vite + TS + vitest**, `package-lock.json` committed.
  Fine-grained reactivity without a virtual DOM is exactly the
  parameter-table workload (hundreds of independently-updating cells);
  ~12 kB runtime; compiled output diffs tolerably as a committed dist.
  Not load-bearing: the sync engine, decimation and fnmatch logic are
  framework-free `lib/` TS either way. Layout:

  ```
  gui/                      # TS workspace, never ships in the wheel
    package.json  package-lock.json  vite.config.ts
    src/  App.svelte  api.ts  panels/{Plot,Params,Plan,History,Report,Console,Text,Structure,Series}.svelte
          lib/{sync,decimate,fnmatch,sse}.ts
  src/rietx/gui/static/   # COMMITTED build output + build-info.json + help.json
  ```

- Build writes **stable filenames** (`app.js`, `app.css`, `vendor-cm.js` —
  no content hashes, so dist diffs stay reviewable) plus `build-info.json`
  (sha256 over sorted `gui/src/**` + lockfile).
- **Dist freshness is enforced twice**: `tests/test_gui_dist.py` recomputes
  the source hash in pure Python (no node in the default CI path) and fails
  with "run `npm --prefix gui run build`"; and `gui.yml` rebuilds on
  gui-path pushes and runs `git diff --exit-code`. The same test asserts
  `index.html` references no `https?://` asset — the offline guarantee,
  executable.
- plotly.js keeps being served from the installed Python package
  (`compare_app.py:102` trick via the WP-1008 `/plotly.js` route — no
  4.5 MB vendored copy, version locked to the `[gui]` extra).
- Plot panel: obs/calc/diff/ticks on Scattergl, client-side min/max
  decimation ported from `viz/html._minmax_decimate` (`viz/html.py:24`) to
  `lib/decimate.ts`; zoom refetches full-res via `/api/result/window`.
  Console: SSE-fed, one line per event with the API-echo per action (the
  DESIGN.md console-pane story: the log doubles as a session script).
- Shell: light/dark theming reusing compare's CSS-custom-properties
  approach.
- **CI cost, priced** (the WP-1002 rule): `gui.yml` triggers only on
  `gui/**` and `src/rietx/gui/static/**` — node setup + `npm ci` + build +
  diff + vitest ≈3 billed min; at an aggressive 40 gui-touching
  pushes/month ≈120 min against the 2000/month free tier (303 scheduled
  today). The per-push `ci.yml` job is unchanged at 5 billed min — the
  dist-hash test is milliseconds and needs no node. Goes to zero when the
  repo goes public.
- Snappiness budget (measured and reported in handovers, ranges not
  figures): interaction→paint <100 ms (decimate to ≤8 k pts/trace above
  20 k); run click→feedback <50 ms; SSE appends batched per animation
  frame. Report (don't gate): first-load JS ≤250 kB gz excluding plotly;
  boot-to-interactive <1.5 s. A raw Float64 array endpoint is the
  pre-designed fallback if a 50 k-point pattern's ~1.6 MB JSON measures
  worse than expected.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): if the rebuild-diff freshness check
proves flaky cross-OS (minifier nondeterminism), downgrade `gui.yml` to
comparing `build-info.json` only and record the measurement in the handover
log — pre-authorised fallback, not a new decision.

From **WP-1008** (GUI server, landed 2026-07-30) — the surface this scaffold
consumes now exists and runs; `rietx gui --no-open` serves it today, with a
placeholder page from `gui/server.py:_PLACEHOLDER` until `static/index.html`
exists. Six facts that change the frontend's design:

- **`/api/events` multiplexes two frame types.** SSE frames arrive as
  `event: event` (an engine event dict, `id:` = its seq) and `event: state`
  (the session's coarse run state). The state frame exists because a *failed*
  fit emits no `fit_end`, so an event-only follower hangs on exactly the case it
  most needs. `?poll=1` returns both (`events` + `state`/`run`) in one JSON
  object. Read event `data` with optional-chaining only — its fields are additive
  by contract and a fixed shape will break.
- **`?since=` is a real cursor, and `oldest` tells you when it failed.** The ring
  is 4096 events (`EVENT_RING`); a staged fit emits one `eval` per residual
  evaluation and can exceed it. If `since + 1 < oldest`, frames were genuinely
  dropped — say so rather than renumbering.
- **Do not port the decimator.** `GET /api/result/window?lo=&hi=&max_points=`
  already returns decimated `two_theta/y_obs/y_calc/y_background/delta` plus
  in-window ticks, using the same `viz.compare.decimation_index` the comparison
  UI uses. A `lib/decimate.ts` (this WP's task list says "port of
  `_minmax_decimate`" — the helper is now public as `decimation_index`) would be
  a second answer to "which points survive". Fetch a window on zoom, which the
  task list already plans.
- **`max_points` is a budget, not a ceiling** — three curves' per-bucket extrema
  over `max_points // 2` buckets, measured at 4132 returned for a 4200-point
  pattern at 4000. Size arrays from `n_returned`.
- **409 is a normal answer, not an error state.** Every mutating verb returns
  `{"error": {"code": "RUN_IN_FLIGHT"}}` while a run is in flight; the UI should
  disable those controls off the `state` frame rather than surfacing a toast.
  `GET /api/params` still works and returns `live: true`, meaning the values may
  straddle two iterations.
- **A `checkout` discards the fitted curves.** `/api/result`, `/api/report` and
  the exports answer `NO_RESULT` (409) until the next run, by design. The panels
  need an empty state for "history moved, nothing computed here yet".

Panel layout and disclosure level belong in `ProjectDoc.ui` via
`POST /api/project {"ui": {...}}` (shallow-merged; a `null` value drops a key) —
persisted immediately, no save step.

## Non-goals

- No parameter editor, history panel, text pane, structure viewer, series
  (WP-1011…1016) — the panels exist as stubs wired to routes only as far as
  the plot + console need.
- No Playwright — vitest units only; server-level tests cover the contracts.
- No SSR, no router, no state library beyond runes.

## Tasks

- [x] `gui/` workspace: Svelte 5 + Vite 8 + TS + vitest, lockfile committed;
      build → `src/rietx/gui/static/` with stable filenames +
      `build-info.json`.
- [x] `tests/test_gui_dist.py`: freshness check (digest defined **once**, in
      `gui/scripts/build_info.py`) + the no-external-asset assertion + two
      checks the WP did not ask for and needed: nothing gitignores the dist, and
      the dist is in the wheel.
- [x] App shell + theming + `api.ts` + `lib/stream.ts` (SSE with `?since=`
      resume, `?poll=1` fallback, dropped-frame accounting).
- [x] Plot panel (obs/calc/diff/ticks, window refetch on zoom). **No
      `lib/decimate.ts`** — the server already decimates through the shared
      helper; a client port would be a second answer. See the handover.
- [x] Console panel on the stream with the per-action API echo.
- [x] `.github/workflows/gui.yml` (gui-paths trigger, node + build +
      `git diff --exit-code` + vitest + svelte-check), priced in the workflow
      file per the WP-1002 rule.
- [x] *(added)* `src/App.test.ts` — a jsdom mount test, standing in for the
      screenshot no browser was available to take.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_dist.py tests/test_gui_server.py -q
npm --prefix gui ci && npm --prefix gui run build && git diff --exit-code src/rietx/gui/static
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

Report in the handover (don't gate): first-load JS size, boot-to-interactive.

## References

- `viz/html.py:24` `_minmax_decimate` — the algorithm to port.
- DESIGN.md §Outputs, human-GUI paragraph + its 2026-07-29 amendment (stack
  decision).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **frontend** (WP-1010) is a Svelte 5 + Vite + TS workspace in `gui/` whose
build output is **committed** under `src/rietx/gui/static`, so installing the
wheel never needs node — and `tests/test_gui_dist.py` is what keeps that honest:
the dist's digest is recomputed in the ordinary (node-free) suite, nothing may
gitignore the dist (the repo-wide `*.html` rule matched its `index.html` once),
the built files must be *in* the wheel, and no built file may name a remote host.
The digest itself lives once, in `gui/scripts/build_info.py`, called by both the
build and the test; `build-info.json` deliberately carries no timestamp, because
`git diff --exit-code src/rietx/gui/static` has to mean "stale", not "rebuilt".
**Which points a payload carries is the server's** (`viz.compare.decimation_index`, past
`CURVES_CEILING` in the curves routes); the chart module paints
each pixel column's extremes of them (WP-1461 D5), what is drawn and never what the
readout reads. No GUI page loads plotly (WP-1462); uPlot and svgcanvas are vendored, into
`src/rietx/viz/static` by `scripts/vendor.py`, the build's first step: bump the pin, build.
**The chart module, uPlot and svgcanvas are chunks off the boot path**, fetched on the first
draw and the first SVG export, so a panel imports them dynamically or by type alone:
`test_gui_dist.py` fails on one inlined into `app.js`, which one static `import {download}`
did without anything else going red (WP-1461).
`npm run build` needs `python3`, `vitest` needs
`resolve.conditions: ["browser"]` or `mount()` comes from svelte's server build,
`@sveltejs/vite-plugin-svelte` must be v7 for Vite 8, and the toolchain needs
**node ≥ 20.12** — rolldown imports `styleText` from `node:util`, an older node
fails at *import* naming neither node nor a version, and `npm ci` under it
leaves a `node_modules` the newer one cannot use (WP-1442).

## Handover log

- **2026-07-30 (later) — the `*.html` trap had a second half, open for six WPs
  and found by CI, not locally.** This WP caught the repo-wide `*.html` rule
  matching the *dist's* `static/index.html` and un-ignored the dist. **The same
  rule was also eating `gui/index.html` — vite's entry module — which had never
  been tracked at all.**

  The two halves fail differently, and the untracked one is worse. A missing
  dist entry serves a placeholder page; a missing *source* entry means
  `npm run build` cannot start, so the frontend cannot be rebuilt from a clean
  checkout by anyone. CI's first clean-clone build of the GUI (PR #17, the only
  time this workflow has ever run) failed in 17 ms with `[UNRESOLVED_ENTRY]
  Cannot resolve entry module index.html`.

  **Why six work packages passed over it**: it falls between the two guards this
  WP built. `test_nothing_gitignores_the_dist` enumerates *dist* files, and the
  freshness digest covers `SOURCE_GLOBS = ("src/**/*",)` — so a file missing
  under `gui/src/` moves the digest and fails loudly, which is why that
  directory needs no list. `gui/index.html` is in neither set, and it exists on
  every machine that has ever run the build, so no local run could see it.

  Closed by `!gui/index.html` in `.gitignore`, tracking the file, and
  `test_a_fresh_clone_can_rebuild_the_frontend` over the seven build inputs that
  live outside both guards. It asks with **`git ls-files`, not
  `git check-ignore`**: "not ignored" is the weaker question, and this file was
  *both* ignored and never added. Verified to bite — untracking the entry fails
  it with the filename in the message.

  **The general lesson for anything with a committed build output**: a guard on
  the output cannot see a missing input, and a digest over the inputs cannot see
  an input it does not glob. Verify by building from `git archive HEAD` into a
  scratch tree — tracked files only — which is what a clone gets and what no
  amount of local testing simulates. Measured that way after the fix: the build
  succeeds and the dist is **byte-identical** to the committed one, digest
  `91c018233e9c`, on both macOS and Linux CI.

- **2026-07-30 — complete.** `npm --prefix gui run build` → 48.7 kB JS
  (19.1 kB gzip) + 3.4 kB CSS; 11 vitest tests; svelte-check 0 errors over 315
  files; `tests/test_gui_dist.py` 8 tests; fast suite 1127 passed / 107 skipped
  in 20-25 s, and the **full** suite including real-data acceptance 1196 passed /
  116 skipped in 5:02 (numpy-only `[dev]` venv). Driven end to end against the real server on a synthetic LaB6
  project: boot payloads served, `POST /api/run` → converged **Rwp 0.04153, GoF
  0.792** over five stages, and `/api/result/window?max_points=800` returning
  1498 of 4200 points with 17 LaB6 ticks — i.e. exactly what the plot panel
  consumes.

  **Visually confirmed by the user, 2026-07-30**, on the served demo project at
  `http://127.0.0.1:8731/` — the page renders and works. That closes the half of
  the acceptance line this session could not reach; what is still unmeasured is
  the *number* (boot-to-interactive), not whether the app functions.

  **Measured, reported not gated** (per the WP): first-load **52.8 kB in three
  requests** (`/`, `app.js`, `app.css`) against a ≤250 kB gz budget; server-side
  response times on localhost 0.5–0.8 ms for every JSON route, 11.9 ms for a
  4000-point window (350 kB of JSON), 6.6 ms for plotly's 4.85 MB. **Boot-to-
  interactive was not measured**: no browser automation was available in this
  session, and a number invented from payload sizes would not be a measurement.
  The page itself was confirmed by the user (above); the timing figure is the one
  acceptance item still owed, and it wants a devtools trace rather than another
  round of arithmetic.

  **Four decisions that changed the WP's plan:**

  1. **The freshness digest is defined once, in stdlib Python**
     (`gui/scripts/build_info.py`), called by both `npm run build` and the test.
     The WP asked for a JS hasher plus a Python re-implementation — two answers
     to "which files decide staleness", and the only thing the JS version buys is
     not needing `python3` on a machine that is building a Python package's
     frontend.
  2. **`build-info.json` carries nothing time-varying.** A build timestamp would
     make every rebuild a dist diff and destroy the property the digest exists
     for: `git diff --exit-code` has to mean *stale*, not *rebuilt*.
  3. **No `lib/decimate.ts`.** WP-1008's `/api/result/window` decimates with the
     same `viz.compare.decimation_index` the comparison UI uses; a client port
     would be a second answer to the one question a plot must not have two
     answers to. Zoom refetches the window instead, which is also *more* honest
     (full-resolution within the visible range rather than an interpolation of a
     decimated set).
  4. **plotly is loaded at runtime** by injecting a `<script src="/plotly.js">`
     rather than importing it, so the build never learns about it: no 4.8 MB
     vendored copy in the committed dist, and the app still boots (console,
     panels, run controls) when plotly is absent — it says so in the plot pane.

  **Two things found by checking rather than assuming**, both of which would have
  shipped silently:

  - **The repo-wide `*.html` ignore rule matched `static/index.html`.** The
    committed dist would have lacked its entry point: the freshness test passes
    on the machine that built it, and a fresh clone (or CI, or a wheel) serves
    the placeholder page instead of the app. `.gitignore` now un-ignores
    `src/rietx/gui/static/**` with a note, and `git check-ignore` is a test.
  - **The wheel contents are asserted.** `uv build --wheel` and all four dist
    files are inside. "Installing the wheel never needs node" is the premise of
    the whole design, so it is measured rather than believed.

  **Gotchas for the next frontend session.** (a) Under vitest, `svelte` resolves
  to its *server* build and `mount()` throws `lifecycle_function_unavailable`;
  the fix is `resolve: process.env.VITEST ? { conditions: ["browser"] } : undefined`
  in `vite.config.ts`, which is Svelte's own documented incantation. (b) Vite 8.1
  wants `build.codeSplitting: false` in place of rollup's
  `inlineDynamicImports` but has not added the key to its types, hence the cast.
  (c) `defineConfig` must come from `vitest/config`, not `vite`, or the `test`
  key does not type-check. (d) `@sveltejs/vite-plugin-svelte` must be **v7** for
  Vite 8 — v6 fails `npm install` on peer resolution.

  **Not done, deliberately:** every panel WP-1011…1016 owns is a named row in the
  sidebar rather than a stub component, so the next WP starts from an empty file
  instead of deleting placeholder markup.

- **2026-07-29** — created from the v1.0 GUI plan.
