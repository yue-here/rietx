# WP-1950 — rietx inside an application

Milestone: unscheduled · Status: 🔄 2026-11-17 — claimed by @mustachefeeling
Track: Candidates — named on a use case, not yet on a measurement
Depends on: —
Priority: P3 2026-10-11 — an application that freezes rietx with PyInstaller and runs it from a user's working directory has a workaround for each step; nothing documents them

## Goal

An application that bundles rietx with PyInstaller gets its data, static
pages, kernel wheel and version metadata from a hook the package ships.
It can point every fit's run record somewhere of its choosing once per
process. One manual section says how to embed rietx.

## Context

**The reports (issues #893, #898).** One application developer ships rietx
in a PyInstaller desktop app ("Crystal Builder").
- #893: a fit records itself under `./.rietx/runs`. In a desktop app the
  working directory may be the user's home or inside the app bundle, so they
  pass `telemetry=` on every `fit`. They ask for telemetry off by default, or
  a per-user cache directory (`platformdirs.user_cache_dir`).
- #898 (a): they collect `data/` by hand because "the f0 and f′f″ tables are
  read by file path", and include `.py` sources for numba's cache. They ask
  for a PyInstaller hook or `importlib.resources`. (b), the thread count, is
  folded into WP-1464.

**#893, checked at `d80ca5f4`.**
- `runs.run_root()` is `Path.cwd() / ".rietx" / "runs"` (`runs.py:1100-1122`).
  The first of three wins: `telemetry=`, the project's `<name>.rex/live`,
  then `run_root()` (`runs.py:1948-1951`). A read-only working directory
  latches, warns once, and the fit continues.
- The default is a decision, not an oversight. WP-1403 (✅) chose it on the
  `.git` precedent, because `rietx watch` defaults to the working directory
  (`watch/__init__.py:826`), and turned it on because WP-1322 saw three of
  three agents opt out of history. It predicted this report: "This will be
  reported as a bug at least once; the env switch and the manual sentence
  are the answer."
- Three switches already turn it off once per process: `RIETX_TELEMETRY=0`,
  `rietx.runs.set_enabled(False)` (`runs.py:1087`), and per call
  `telemetry=False` (`using/refining.md`, `using/files.md`).
- **The gap is a process-wide root.** Redirecting takes `telemetry=<root>`
  on every call. `_about.py` says `RIETX_STATE_DIR` moves only
  `$HOME/.rietx`, and no variable moves the working directory's `.rietx/`.
- Ran: a `profile_only` fit from a fresh working directory with
  `RIETX_TELEMETRY` unset wrote `.rietx/runs/<id>/` (408 kB, of which
  `events.jsonl` 303 kB and `snapshot.json` 34 kB) and nothing under the
  state directory.

**#898 (a), checked at `d80ca5f4`.**
- **numba is gone.** `pyproject.toml` on `main` has no numba. WP-1940 (✅,
  47bcc35b, 2026-10-10) moved the compiled tier into the `rietx-kernels`
  abi3 wheel. v1.7.0's `pyproject.toml` still lists `numba>=0.63`, so the
  reporter is on 1.7.0. Their `.py`-for-numba step goes away in the next
  release.
- **The tables already load through `importlib.resources`**
  (`crystallography/scattering.py:80`, `dispersion.py:88`, `attenuation.py`,
  `neutron.py`). PyInstaller still has to be told to collect them, since its
  analysis follows imports and not data files.
- **Read by path:** the browser surfaces' static directories
  (`gui/server.py:52`, `watch/__init__.py:76`, `compare_app/__init__.py:46`,
  `viz/chart.py:17`, `viz/html.py:37`). These matter only to an app that
  serves those pages.
- **Two hazards the report does not name.** The kernel wheel is imported
  inside a function (`model/compiled.py:218`). If a freeze misses it, the
  fit warns once and runs the numpy path, about 2× slower. And
  `refine._resolve_version` reads `importlib.metadata.version("rietx")`
  (`refine.py:243-262`). Without the dist-info in the bundle it warns and
  stamps every result's provenance with the development version.
- Nothing in `src`, the manual, `pyproject.toml` or the README mentions
  PyInstaller.

**Decided 2026-10-11** (the maintainer, at the issue triage; posted on
#893): the default stays. A fit with no `telemetry=` and no project still
records under the working directory's `.rietx/runs`, as WP-1403 chose.
#893 brought no evidence WP-1403 had not weighed, and the three switches
cover an embedder. This WP adds a process-wide root and changes no default.

**Prior art.** PyInstaller's documented way for a library to ship its own
hook is the `pyinstaller40` entry point: `hook-dirs =
"rietx.__pyinstaller:get_hook_dirs"`, returning absolute paths. A hook uses
`collect_data_files("rietx")`, `copy_metadata("rietx")` and
`hiddenimports` (pyinstaller.org, *Understanding PyInstaller Hooks*).
`pyinstaller-hooks-contrib` is the other route and needs a PR elsewhere.

### Inherited

- **From WP-1966 (2026-10-14): a second host where run records are useless.**
  The JupyterLite site's install cell sets `RIETX_TELEMETRY=0` before rietx
  is imported, because no `rietx watch` can read a browser tab's runs
  (`docs/lite/build.py`, `INSTALL`). A once-per-process switch from this WP
  would replace that line, so name the browser as a second caller. The same
  host also empties `fcntl`. WP-1966 made the three lock sites import `flock`
  by name, so a record written there takes the Windows path.

## Non-goals

- Changing the telemetry default (Decided 2026-10-11, above).
- The kernel thread count (WP-1464, issue #898 (b)).
- `platformdirs` as a dependency.

## Tasks

- [ ] A process-wide run root: an environment variable or a
      `runs.set_root(path)` beside `runs.set_enabled`, its name imported
      from `_about.py` (root CLAUDE.md § Conventions). It sits between
      `telemetry=` and the working directory in the precedence. Retention
      and its three guards keep working under it (WP-1403), and `rietx
      watch` is told where to look.
- [ ] A PyInstaller hook shipped in the package through the `pyinstaller40`
      entry point: data files, the static page directories, the kernel
      wheel as a hidden import, and the dist-info metadata.
- [ ] Verify it with a real freeze of a one-fit script in CI or a temporary
      branch workflow (no docker here): the frozen fit loads the kernels,
      stamps the real version, and writes its run where the root says.
- [ ] Manual: an "Embedding rietx" section in `using/` covering telemetry
      off or redirected, the hook, and `RIETX_COMPILED_THREADS`.
- [ ] Tests for the root's precedence (`tests/test_telemetry.py`).
- [ ] Skill: none expected, since an agent driving rietx does not freeze it.
      Say so at close.

## Acceptance

A frozen one-fit script runs on the compiled tier, stamps the release
version, and writes its run under the configured root. A test pins the
root's precedence against `telemetry=` and the working directory.

```sh
.venv/bin/python -m pytest tests/test_telemetry.py tests/test_runs.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #893, #898.
- PyInstaller documentation, *Understanding PyInstaller Hooks* and
  *Run-time Information*.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issues #893,
  #898 (a)). Checked against the tree at `d80ca5f4`: the run root is the
  working directory by WP-1403's decision, three switches turn it off, and
  nothing moves it process-wide. numba left with WP-1940, and the tables load
  as package resources. No open WP owns it: WP-1403, 1404 and 1406 (the
  recorder) and 1940 (the wheel) are closed, and WP-1464 takes only the
  thread count. The maintainer kept the default the same day (§ Context).
  *Next:* task 1.
