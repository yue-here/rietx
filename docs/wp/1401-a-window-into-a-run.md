# WP-1401 — a window into a run: find the runs that already exist

Milestone: unscheduled · Status: ⬜
Depends on: — (first rung of the live-watcher track; 1402, 1403 and 1405 all
build on the reader this lands)

## Goal

`rietx watch`, with no argument, scans the working directory and lists every
refinement run under it — the live ones and the finished ones together — and a
click opens one. It reads only directories that today's code already writes, so
nothing in `refine.py` is touched and the reader is exercised against a format a
writer really produces. The same session measures what `events=` costs today,
because that number decides whether WP-1403's automatic recording is affordable
at all.

## Context

When an agent drives rietx, the human has no window into the work. The telemetry
is good and it is unreachable, for three separate reasons.

**It is off unless the caller asks.** WP-1322 measured the consequence: three
independent subagents, each given a benchmarking task, each of which found and
read the packaged skill in full by a different route, all wrote `history=False`
— five occurrences. No event log existed afterwards, and reconstructing timing
from their own transcripts recovered 2.7–16.6 % coverage and nothing at all from
inside a solve. That is WP-1403's problem, not this one's, but it is why the
track exists.

**The human must know the directory.** `rietx watch <dir>` takes a path the agent
chose, in a process the human is not in. One directory holds one run, and
`LiveSession.__init__` truncates `events.jsonl`, so nothing is archived. This is
the gap this WP closes.

**Watching is expensive.** `LiveSession.write_snapshot` builds a self-contained
page with the whole of plotly inlined, about 3.5 MB, on the fit's own thread,
after every stage. That is WP-1402's problem.

### The decision this track rests on

The watcher **grows `rietx watch`; it is not a mode inside `rietx gui`**. Three
reasons, recorded here because the alternative will look attractive again:

- The GUI's live view is an in-process ring buffer fed by its own callback
  (`gui/session.py`, `EVENT_RING = 4096`, `_push`), so it has **no path to a run
  in another process** — which is exactly what an agent's run is. A file-tailing
  reader is new code wherever it lives; in `watch` it is the whole app rather
  than a second data path beside the first.
- The GUI is one project per session and every verb writes — that is why
  `--scratch` exists, and why `Project.open` appends a head annotation before any
  verb runs. `_require_idle()` raises 409 in 24 places. A multi-run read-only
  browser contradicts both.
- **Read-only is stronger when the app has no verbs than when a mode hides
  them.** A user cannot click what is not there. The watcher gets exactly one
  verb, cancel, in WP-1405, and nothing else.

Human-in-the-loop is not foreclosed; it is placed. Discovery, run metadata,
liveness and tailing go in `runs.py`, a plain library module with no HTTP, which
`watch.py` is transport over — the split `gui/server.py` already declares for
itself ("this module is transport only") — and which `gui/session.py` imports
when it attaches to a foreign run. Each run row carries "open in the GUI", so the
read-only/interactive boundary is a **process boundary, not a mode**.

### What exists, and where

- `src/rietx/history/events.py` (279 lines) — `EventStream(path=, callback=)`,
  `emit(kind, **data)` writing one JSON line and flushing. `EventKind` is a
  **closed** Literal of seven; `data` is an **open** dict, so a reader uses
  `.get` and never unpacks a fixed shape, and a new field bumps nothing.
  `read_events(path)` validates a log back through `EventRecord`.
- `src/rietx/viz/live.py` (66 lines) — `LiveSession(EventStream)`: truncates
  `events.jsonl` on construction, writes `fit.html` + `status.json` per stage.
- `src/rietx/watch.py` (151 lines) — `_INDEX` inline HTML, `_Handler`,
  `serve(directory, *, port=8899, open_browser=False, block=True)`,
  `main(argv)` with a positional `directory`. The page refetches the **whole**
  `events.jsonl` every second and re-renders the last 400 lines.
- `src/rietx/gui/session.py` — `GuiSession.run` opens
  `EventStream(path=p.live_dir / "events.jsonl", callback=self._push)` and
  **appends**. So a GUI project's `live/events.jsonl` is a real, populated log
  today: it is this WP's primary fixture, and the reason the reader can be built
  against a live format rather than an invented one.
- `src/rietx/project.py` — `LIVE_DIR = "live"`, `Project.live_dir` ("where an
  event stream belongs, so `rietx watch` can find it").
- `src/rietx/cli.py` (388 lines) — hand-rolled dispatch on `argv[0]`, lazy
  imports, `watch` at line 80.

### The rule this reader carries across a process boundary

`gui/session.py:27-41` states it for one process: a fit that raises emits **no**
`fit_end`, `EventKind` is closed, so the run's **state is not an event** — it
travels beside the stream and is never written to the log.

Across a process boundary the same rule needs a channel the OS maintains, because
a dead writer writes nothing:

- **Liveness is a held lock, not a pid.** The writer holds `run.lock` flock'd for
  its life; a reader takes it non-blocking and infers from the failure. Immune to
  pid reuse, needs no heartbeat contract, and the kernel releases it however the
  writer dies, `kill -9` included. `os.kill(pid, 0)` is the fallback where flock
  is unavailable, and the heartbeat age is **reported but never decides** — an
  alive process is evidence, a clock is not.
- A lock that is free while the status says running reads **abandoned**, which is
  a third answer and not a rounding of the other two.
- A different host reads **unknown**. A claim we cannot check is not a claim.

Nothing in this WP writes `run.lock` or `status.json`; WP-1403 does. The reader
ships knowing about them, treats every one as optional, and resolves a directory
that has neither as a **legacy** run — which is what every directory in the tree
today is, and what keeps them all visible forever.

### The reader constructs nothing

No `Project.open` — it appends a head annotation, which is why there is no
read-only way to open a project — no `Refinement`, no `read_pattern`. Everything
a reader needs, a writer captured. This is a hard rule in the module docstring,
not a style preference: a viewer that constructs a project mutates what it is
looking at.

### The measurement this WP owes the next one

WP-1403 proposes to record **every** fit. Whether that is affordable is decided
by a number, and the baseline half of that number needs none of this track's
code, because `events=` already exists. Two facts verified in the tree
(2026-09-13):

- `optimize/least_squares.py:1153` calls `_free_values(table, theta)` on every
  residual evaluation when `events is not None`. That is a **second full
  `table.decode`** (`least_squares.py:822`), and it happens **before** the sink is
  consulted, so no cleverness in a sink can avoid it. Then `emit` does
  `json.dumps` + write + `flush`: a syscall pair per residual evaluation, on the
  fit thread.
- `refine.py:1758-1771` computes a real `stage_end.rwp` from one `background`
  pass plus one `bragg_component` pass, **only when events were asked for**. That
  is one forward evaluation per *stage*, against a stage's hundreds.

So the cost is dominated by the eval stream and it is CPU as much as syscalls.
Measure it now, on the cases the next WPs will reuse.

## Non-goals

- **No automatic telemetry.** No `telemetry=` keyword, no recorder, no writing.
  WP-1403, and it is gated by this WP's measurement.
- **No `snapshot.json`, and `fit.html` keeps being written.** WP-1402. The page
  this WP lands shows a run's events and status; the plot stays the existing
  `fit.html` iframe where one exists.
- **No cancel.** No verb of any kind. WP-1405.
- **No manual or skill changes.** WP-1406.
- **No GUI change.** `gui/session.py` importing `runs.py` is the seam this WP
  leaves open, not work it does.

## Tasks

- [ ] `runs.py`: the run-directory model and the run-id scheme. `RunMeta` /
      `RunStatus` as pydantic `Base` models **for reading only** (the
      `EventRecord` split: no pydantic on any write path). `RunStatus.state` has
      **no default** — a defaulted `"running"` is exactly WP-1076's field whose
      empty state reads as an answer — and a status missing it resolves to
      `unknown`. Every field's writer named in the docstring, since this WP
      writes none of them.
- [ ] `runs.discover(root)`: depth- and count-bounded walk; prunes `.git`,
      `node_modules`, `.venv`, `__pycache__`, `_build`, `dist`; never follows
      symlinks; descends a `*.rex` only as far as its `live/`; reads **exactly
      two files per run**, asserted by counting opens, because a web page polls
      this. A directory with `events.jsonl` and no `meta.json` is a **legacy**
      run, synthesized from the file's mtime — which is every directory in the
      tree today.
- [ ] `runs.liveness_of`: the ordered rule above — terminal state wins, then
      foreign host, then the flock probe, then `os.kill(pid, 0)`, with the
      heartbeat age reported and never deciding. A Windows shim for the lock
      probe, and a documented fall-through when neither mechanism is available.
- [ ] `runs.tail_events`: byte-offset cursor, not the whole-file refetch the
      page does today. Carries a trailing fragment **unparsed**; resets on inode
      change or truncation and says so, so a client clears its pane rather than
      renumbering silently; counts a bad line instead of raising. Load-bearing
      rather than defensive from WP-1403 on, when writes become buffered.
- [ ] `python -m rietx.runs [DIR]` printing the discovered table — how a human
      checks the walk without a browser.
- [ ] `watch.py`: no-argument mode scanning the cwd, the run list page, and the
      JSON routes it needs (`/api/runs`, `/api/run/<id>`,
      `/api/run/<id>/events?offset=`). A directory argument that **is** a run is
      served as one and opens straight onto it, so `rietx watch ./live-dir` from
      `using/cli.md` keeps working unchanged. Polling stops when the page is
      hidden. The page says **"scanned \<root\>"**: an empty list must not read as
      "no runs exist".
- [ ] The baseline measurement: `telemetry off` against today's plain
      `events=<path>` and against `events=LiveSession(dir)`, on `nac`, `cpd-2`
      and `trigger`, three runs each, one sitting. Numbers into the handover as a
      **range**, with venv and platform named. State plainly whether WP-1403's
      premise survives.
- [ ] Tests: `tests/test_runs.py` (no fit at all — fixture directories) and
      `tests/test_watch_app.py`. Cases: a held lock against a released one, a
      foreign host, a status with no state, a torn last line, invalid JSON mid
      file, an empty directory, the depth cap, a symlink loop, the open-count
      assertion. Plus a real `<project>/live/` written by a GUI run.
- [ ] Skill: **none**, and the reason. Nothing here changes what an agent driving
      rietx should do; WP-1406 carries the whole skill change for this track,
      once there is something an agent's behaviour depends on.

## Acceptance

`rietx watch` in a tree holding a GUI project lists that project's run, and
opening it shows the events the GUI wrote. Checked by looking, not only asserted.

```sh
.venv/bin/python -m pytest tests/test_runs.py tests/test_watch_app.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m rietx.runs .
```

The baseline measurement is reported in the handover log, never asserted in a
test: a wall-clock budget in a test is a runaway guard, never a timer.

## References

- WP-1006 — run control: streaming, progress, cancellation. The origin of
  `events=`, and of the rule that the run state is not an event.
- WP-1008 — the GUI's live machinery and `/api/result/window`.
- WP-1113 — what an `eval` event carries and why (`values`, `accepted`,
  `step_norm`), which is the trajectory a sampled log would cost.
- WP-1322 — the three subagents that all disabled telemetry; the measured
  2.7–16.6 % transcript coverage. Its Task 1, the terminal-shaped post-hoc
  aggregator, stays its own; its Task 2 is discharged by WP-1403.
- WP-1076 — a declared name is a claim; a field whose empty state reads as an
  answer. Why `RunStatus.state` has no default.

## Handover log

- **2026-09-13** — created, and with it the whole live-watcher track
  (1401–1406). What this round settles is that a human will be able to see, and
  stop, a refinement an agent is running, without that costing the agent
  anything it has to remember to do. The design question that took the longest
  was where it lives, and the answer is that it grows `rietx watch` rather than
  becoming a mode in the GUI: the GUI's live view is an in-process ring that
  physically cannot see a run in another process, and read-only is a stronger
  promise when an app has no verbs than when a mode hides them. Nothing is
  implemented; six WP files and the ROADMAP rows are the whole deliverable.

  *Done.* Six self-contained WP files, one new Unscheduled section, and the
  track named in Current focus. The ROADMAP cap moved 648 → 670 with its ledger
  line, landing at 669; the section's paragraph was cut to the rungs' order and
  the one surface decision, because each file carries its reasoning in full.

  *Measured.* Nothing physical — this round measured nothing and must not be
  quoted as if it had. Fast selection 4487 passed, 127 skipped, `[dev]` venv (no
  jax, no torch), macOS arm64. Docs-only with no test added or removed, so that
  count is unchanged by construction rather than by comparison. The full suite
  was not run and is not owed: nothing here can move a measured number.

  *Gotchas for the successor.* Four cited `file:line` references in the drafts
  were wrong and are fixed; nothing tests them, so check any one you are about
  to rely on. Two facts were verified by hand and are load-bearing:
  `_free_values` is a second full `table.decode` on **every** residual
  evaluation and it runs *before* the sink is consulted, so no sink-side thrift
  avoids it; and `_abandon_on_cancel` short-circuits on `cancel is None` and
  says so in its docstring, which means WP-1405 attaching a token universally
  ends a guarantee the code currently makes. `origin/main` was ahead of the main
  checkout when this opened — WP-1344 already existed — so 14xx was taken as the
  next free block on the user's instruction; per
  `test_index_section_mirrors_the_wp_milestone_line` the number never carries
  the milestone, the `Milestone:` line does.

  *Next.* Start 1401 itself: `runs.py` plus the no-argument `rietx watch` over
  the directories today's code already writes. Its last task — the baseline
  measurement of what `events=` costs now — is the one that matters most,
  because it decides whether 1403's automatic recording ships on by default at
  all, and the three failure paths for that are already written down in 1404 so
  they cannot be quietly avoided. The track is slated for v1.5, behind v1.4's
  free-standing peaks; 1401 is the only rung that delivers a usable window on
  its own, so it is also the safe place to stop if the track is reprioritised.
