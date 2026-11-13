# WP-2145 — the `rietx watch` GUI boot test waits as long as the watcher does

Milestone: unscheduled · Status: 🔄 2026-11-13 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P3 2026-11-13 — a false red in every local full suite on this Mac, which runners report as a main failure; CI's Linux runner passes it

## Goal

`tests/test_watch_app.py::test_a_real_gui_boots_on_a_scratch_copy_and_the_project_is_untouched`
passes wherever the GUI boots inside the watcher's own deadline. Today it fails on the
maintainer's Mac whenever the boot takes more than 5 s.

## Context

### What the test does

The test is WP-1428's acceptance. It starts a `rietx watch` server, then posts to
`/api/run/<id>/gui`. That route spawns `rietx gui --scratch` on a copy of the project and
holds the request open until the child prints its boot line
(`rietx.watch._launch_gui`). The server waits for that line up to
`rietx.watch.GUI_BOOT_TIMEOUT`, 60 s. The test's client gives up sooner: `_post` opens the
request with `urllib.request.urlopen(..., timeout=5)`. So any boot slower than 5 s fails the
test with `TimeoutError: timed out` in `_post`, while the watcher itself would have served it.
The test is marked `slow`, so it runs only in full-suite runs.

### Measured

- 2026-11-13, macOS arm64, worktree venv `[dev]`, Python 3.12.10, load average 54-91:
  the test failed alone in 21 s, with `TimeoutError` in `_post` at line 62. A probe spawning
  the GUI exactly as the watcher does (`_gui_argv`, stdout read to the boot line) timed the
  boot at 14.9, 13.2 and 11.7 s in three runs. The probe script was
  `~/.cache/ghostshift/rietx/close-only-2026-11-13/time_boot.py` (maintainer-local).
- The same failure appears alone in earlier logs on this Mac: the WP-2116 runner's
  `watch.log` (2026-11-12, 1 failed in 16 s) and two `/pr-review` reruns of #1509
  (2026-11-12). The shift log of 2026-11-12 lists it as one of two tests failing on `main`
  on this Mac, with no owner.
- The Linux nightly `full` job of 2026-11-12 (run 43234222625) passed with no failure, so the
  boot there stays under 5 s.

Not measured: the boot time on this Mac at low load. So it is not known whether a quiet
machine passes the test.

### Why the fix is in the test

The 60 s deadline is the product's: it bounds how long a request thread waits for a child
that never prints. The 5 s is a test helper's default for routes that answer at once. This
one route waits on a process start, which includes importing rietx in a fresh interpreter
and copying the project. A client deadline shorter than the server's makes the test measure
the machine's speed rather than the route's contract.

## Tasks

- [x] Give the GUI post a client timeout above the watcher's own deadline, derived from
  `rietx.watch.GUI_BOOT_TIMEOUT` rather than a second literal (for example
  `GUI_BOOT_TIMEOUT + 10`). `_post` takes the timeout as an argument; the other callers keep 5 s.
- [x] Check for siblings: any other test that sends a request to a route which spawns a
  process or waits on one, with a client deadline below the server's. On 2026-11-13 a grep of
  `tests/` for `Popen` and `_gui_argv` found only this test and `test_run_control.py`, which
  waits 120 s.
- [ ] Run the test alone on this Mac, and record the boot time and load beside the result.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py::test_a_real_gui_boots_on_a_scratch_copy_and_the_project_is_untouched
.venv/bin/python -m ruff check src tests examples
```

The test passes on this Mac at the load a ghostshift suite runs under, and its client
deadline is read from `GUI_BOOT_TIMEOUT`.

## Non-goals

- Making the GUI boot faster. If the boot exceeds 60 s, that is a product defect for another WP.
- Changing `GUI_BOOT_TIMEOUT`.

## References

- WP-1428 (open in the GUI without touching the fit): the route and this acceptance test.
- `tests/CLAUDE.md` § Budgets in tests: a wall-clock budget is a runaway guard, never a timer.

## Handover log

- **2026-11-13** — filed by the close-only bookkeeping batch of 2026-11-13 (PR #1563). No open
  WP owns it. The open WPs that mention flaky or browser tests are WP-1343 (a magnetic width),
  WP-2019 (which tests each CI leg runs) and WP-2216 (the refinement window), and none covers a
  test's client deadline. The shift reported this as a browser-test start-up timeout; the
  failing test is in `test_watch_app.py`, not a `*_browser.py` file, and it drives no browser.
  The failure reproduced alone at load 54-91, with the boot at 11.7-14.9 s against a 5 s
  client deadline. Next: the first task, then the run on this Mac.
