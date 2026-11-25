# WP-1950 — rietx inside an application

Milestone: unscheduled · Status: 🔄 2026-11-25 — a process-wide run root, a shipped PyInstaller hook and the embedding guide landed (PR #1644); the WP closes with the maintainer's handover after the merge; a CI freeze on Linux and Windows is issue #1651
Track: Candidates — named on a use case, not yet on a measurement
Depends on: —

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

**Left open by WP-1464 (2026-11-19): the default ignores CPU affinity.**
`model.compiled.n_threads()` takes `min(8, os.cpu_count())`, and
`os.cpu_count()` counts the node's cores, not those a job is allowed
(affinity, cgroup limits; inferred, never measured). A job given four cores
on a large node then starts eight kernel threads per process.
`os.process_cpu_count()` (Python 3.13+) reads affinity. WP-1464 closed with
this open and no run limited that way measured. The embedding guide names
`RIETX_COMPILED_THREADS` as the way to cap rietx beside an application's own
parallel work, and does not recommend 1 for speed (a pool of 26 fits ran
1.9-2.8× slower at 1 than at the default, `docs/practice.md` § Inner threads
in a process pool). This WP closed without taking the affinity question up.

## Non-goals

- Changing the telemetry default (Decided 2026-10-11, above).
- The kernel thread count in a process pool (WP-1464, issue #898 (b),
  closed 2026-11-19). The affinity question it left open is in Context.
- `platformdirs` as a dependency.

## Tasks

- [x] A process-wide run root: an environment variable or a
      `runs.set_root(path)` beside `runs.set_enabled`, its name imported
      from `_about.py` (root CLAUDE.md § Conventions). It sits between
      `telemetry=` and the working directory in the precedence. Retention
      and its three guards keep working under it (WP-1403), and `rietx
      watch` is told where to look.
- [x] A PyInstaller hook shipped in the package through the `pyinstaller40`
      entry point: data files, the static page directories, the kernel
      wheel as a hidden import, and the dist-info metadata.
- [x] Verify it with a real freeze of a one-fit script in CI or a temporary
      branch workflow (no docker here): the frozen fit loads the kernels,
      stamps the real version, and writes its run where the root says.
      Done as a local macOS freeze by hand, with a control arm (handover
      log); the CI freeze, and Linux and Windows, are issue #1651.
- [x] Manual: an "Embedding rietx" section in `using/` covering telemetry
      off or redirected, the hook, and `RIETX_COMPILED_THREADS`. Landed as
      the guide page `guides/embed.md`, the manual having no `using/` tree.
- [x] Tests for the root's precedence (`tests/test_telemetry.py`).
- [x] Skill: none expected, since an agent driving rietx does not freeze it.
      Said at close (2026-11-17): no skill row; an agent that wants its runs
      elsewhere already has `telemetry=`.

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

- **2026-11-17** — closed (ghostshift runner, PR #1644). An application that
  embeds rietx can now settle where runs go once per process, with
  `RIETX_RUNS_DIR` or `rietx.runs.set_root`, instead of passing `telemetry=`
  on every call, and the telemetry default is unchanged. A PyInstaller freeze
  needs no flags for rietx any more: the package ships its own hook, and a real
  freeze showed what the hook buys (data files and the version stamp) against
  a control frozen from `main`. The manual has a guide page for all of it. A
  freeze on Linux and Windows, and a CI job that keeps freezing, are left as
  issue #1651.
  - *Done.* `_about.RUNS_DIR_ENV`; `runs.set_root` / `runs.configured_root`;
    `run_root` takes the configured root when no base is given. Precedence in
    `attach`: `RIETX_TELEMETRY=0` / `set_enabled(False)` / `telemetry=False`,
    then `telemetry=`, then a project's `live/`, then the configured root,
    then `<cwd>/.rietx/runs`. The configured root is a root rietx chose: it is
    created and pruned (WP-1403's retention and guards; `_PRUNED` is now a set
    of roots, so a root changed mid-process gets its walk), and gets the
    `.gitignore` only if it starts out empty (`RIETX_RUNS_DIR=.` must not hide
    a repository). `set_root` makes a relative path absolute at the call; a
    relative variable is resolved at each fit. `rietx watch` with no argument
    keeps scanning the working directory and prints one line naming a
    configured root it cannot be sure to list (anything but the directory or
    its `.rietx/runs`), and nothing while recording is off. Hook:
    `src/rietx/__pyinstaller/` + `[project.entry-points.pyinstaller40]`;
    `collect_data_files`, `collect_submodules` (the hook package excepted),
    `rietx_kernels` as a hidden import, `copy_metadata(DIST_NAME)`;
    `_audit.NOT_WALKED["__pyinstaller"]`. Guide `docs/docs/guides/embed.md`;
    `guides/watch.md`'s switch table and `reference/project.md`'s `.rietx`
    paragraph name the new root. Tests: 12 in `tests/test_telemetry.py`
    (precedence against `telemetry=`, a project and the working directory;
    `set_root` over the variable; absolute paths; off writes nothing; an
    unusable root declines and the fit returns; per-root pruning; the
    `.gitignore` rule; the banner), 5 in `tests/test_pyinstaller_hook.py`.
  - *Measured, the freeze* (macOS arm64, CPython 3.12, PyInstaller 6.22.3,
    rietx built from this branch as a wheel into a clean venv, onedir). Script:
    build the `fap` example's inputs from the package data, fit them with a
    plain `Refinement`, report. Hook arm, run from an empty directory with
    `RIETX_RUNS_DIR` set: frozen, compiled tier loaded
    (`compiled.unavailable()` None), provenance `1.12.0.dev0` = the installed
    metadata, `converged`, Rwp 0.09283, one run directory under the configured
    root (status `done`, `.gitignore` written), nothing in the working
    directory, no warning; 120 MB. Control arm, the same script frozen from
    `origin/main` 6f704aaa5 (no hook): `ModuleNotFoundError: No module named
    'rietx.data'` before the fit, and the version stamp fell back to
    `0.0.0+dev` with its warning; 113 MB. The compiled tier loaded in the
    control too, since PyInstaller follows the function-level `import
    rietx_kernels`; the hidden import is kept as a guard. The two PyInstaller
    warnings in both builds were outside rietx (a scipy hidden import, a
    Windows-only ctypes library).
  - *Measured, tests.* Mac `[dev]` venv, macOS arm64: `test_telemetry.py`,
    `test_runs.py`, `test_pyinstaller_hook.py`, `test_watch_app.py` 205 passed,
    1 skipped; `test_manual_api.py` + `test_docs_consistency.py` +
    `test_pyinstaller_hook.py` 50 passed; manual `sphinx -W` clean; Vale 0
    errors. The workstation (Linux x86_64, `rietx-py312`, tree on `PYTHONPATH`): canary
    at 691ee826c 287 passed, 1 failed (the audit walk had no place for
    `__pyinstaller`, fixed in 073495b20), then 288 passed, 4 skipped at
    073495b20. Fast selection on the merged tree 9d69c40d5 (`origin/main` f1187a062 merged in): 14873
    passed, 281 skipped, 32 xfailed, 2 failed in 612 s, 6.6 GB peak, 725 % on
    8 cores. Both failures were this branch's: the metadata-reader pin in
    `test_capabilities.py` matched the hook's `copy_metadata(DIST_NAME)`, and
    Vale's accept list is generated from `docs/vale/terms.txt`, where
    PyInstaller now sits. Fixed in 7b5cfba9e; both files then 64 passed on the Mac.
    The suite added 17 tests (12 + 5); the one extra skip against other
    branches' runs (281, not 280) is the hook's entry-point test, which skips
    wherever the installed dist-info predates the branch (the workstation's shared
    venv); CI installs fresh.
  - *Review.* A read-only reviewer found the banner silent for a root under
    a dot-directory of the working directory (fixed), pruning once per process
    rather than per root (fixed), a relative variable left relative (fixed), a
    `.gitignore` of `*` written into a shared directory (fixed), and an
    unguarded `resolve()` in the banner (fixed). Declined: replacing
    `DIST_NAME` in the hook with a literal to spare importing rietx in the
    build process, because CLAUDE.md § Conventions wants the name imported.
  - *Generality* (standing-in judge, Opus, read-only, unedited verdicts):
    `NOT_WALKED["__pyinstaller"]` **holds** (no module-level number). The
    `.gitignore`-only-when-empty rule **holds**; weak side: a new empty folder
    inside a repository meant to be committed gets hidden. The precedence
    chain **holds**; weak side: a project-built `Refinement` still records into
    the project's `live/` with a root set (documented, not warned). The watch
    banner **fails**: it claimed a fit records somewhere with recording off.
    Author: gated on `runs.enabled()` in 4563b711d, with a test.
  - *Pruned.* `### Inherited` from WP-1966 (the in-browser notebooks set
    `RIETX_TELEMETRY=0`): still true and still the right switch there, since
    a root does not help where nothing reads runs; the guide names that
    caller. Nothing replaced its line.
  - *Not done.* No CI freeze, and no Linux or Windows freeze (issue #1651).
    The telemetry default is unchanged (Decided 2026-10-11). Issues #893 and
    #898 (a) are answered by this PR and left for the maintainer to close.
  - *Next:* none in this WP. Issue #1651 for the CI freeze.

- **2026-10-11** — created, from the 2026-10-11 issue triage (issues #893,
  #898 (a)). Checked against the tree at `d80ca5f4`: the run root is the
  working directory by WP-1403's decision, three switches turn it off, and
  nothing moves it process-wide. numba left with WP-1940, and the tables load
  as package resources. No open WP owns it: WP-1403, 1404 and 1406 (the
  recorder) and 1940 (the wheel) are closed, and WP-1464 takes only the
  thread count. The maintainer kept the default the same day (§ Context).
  *Next:* task 1.
