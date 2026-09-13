# WP-1405 — the human stops the run

Milestone: unscheduled · Status: ⬜
Depends on: 1403 (the recorder that polls); 1401 (the page the button is on)

## Goal

A human watching a run an agent is driving can stop it, from the browser, in
another process, without corrupting anything: the in-flight stage is abandoned,
the models are restored, the completed stages are kept, and the agent's process
raises the `RefinementCancelled` it already knows how to handle.

## Context

### The seam is a file

The watcher writes `<run>/cancel`; the recorder notices and sets a `CancelToken`.
That is the whole mechanism, and it is a file rather than a socket because the
two processes already share exactly one thing — a directory — and adding a second
channel would mean the watcher could reach a fit it cannot see.

`optimize/cancel.py` is unchanged: `CancelToken` wraps a `threading.Event`
(`cancel()`, `is_set()`, `reset()`, `__bool__`), and `RefinementCancelled`
carries `.stage`, `.completed_stages` and `.node_id`. The token is read in a
residual wrapper installed **before** the event wrapper, so cancellation stays
cooperative, read between residual evaluations, and never an interrupt — which is
what keeps frozen-per-stage discreteness true.

### Composition, and the cost it ends

**If the caller passed a token, the recorder sets theirs** and never makes a
second: one authority per run for "stop". If the caller passed none, `fit`
creates one, and only when the recorder is active.

That last clause has a price, and it is this WP's alone.
`refine.py:1543-1546` short-circuits on `cancel is None` and says so in the
docstring: *"the copies are taken only when a token is present, so an ordinary
fit pays nothing."* Attaching a token so this button works ends that guarantee —
two `model_copy(deep=True)` a stage, scaling with atom count. It is configuration
3 of WP-1404's matrix, and if that row is expensive, the answer is to attach the
token lazily (only once a `cancel` file has been seen) rather than to drop the
feature. Measure before choosing.

### Polling cadence

A `stat` per residual evaluation is the same syscall problem WP-1403's buffered
flush exists to avoid, so the cancel probe **shares the flush clock**: at most
one probe per cadence. Latency is then the cadence plus the residual evaluation
in flight, which on a large pattern is the dominant term anyway. The page says so
rather than appearing to hang.

The coupling that clock hides: the recorder only gets control when something
calls it, so a probe "per cadence" is really *per cadence, at an event*. With
the shipping eval stream that is every residual evaluation and the distinction
is invisible — but WP-1403's mitigation 3 (thinning) and WP-1404's configuration
1 (stage boundaries only) both take the eval events away, and the probe would
then fire once a **stage**. On the long runs this button exists for that is
minutes, not the cadence. So the probe is hung on the *unthinned* evaluation
boundary, not on the emitted event: it is a wall-clock test in the residual
wrapper that already reads the token, and it survives whatever WP-1404 decides
about what gets written. Assert it: a test with eval events off must still
cancel within a cadence.

### What the agent's process sees, and why that is the point

Nothing new. Routing through the shipped token means a human's cancel and an
agent's own `token.cancel()` are indistinguishable downstream: the in-flight
stage is abandoned, no history node is written, no table is committed, the
structure and instrument are restored from the copies above, and
`RefinementCancelled` carries what completed. A cancelled `fit_end` carries
`status="cancelled"` and **omits** `rwp`/`gof`, because there is no fitted result
to report — which is the same open-dict rule seen from the reader's side.

The recorder additionally writes a terminal status naming the run cancelled and
**who asked**, so the watcher can distinguish a human's stop from an agent's own
in the record even though the fit cannot.

### What the confirm dialog must say

An agent that does not catch `RefinementCancelled` sees a traceback. So a human
clicking a browser button can put a traceback into an agent's session. That is
the sharpest consequence of this whole track and it belongs in the dialog, not in
a docs footnote:

- name the run and the stage in flight;
- say it raises in the process running the fit;
- say the completed stages are kept.

Two clicks, and no keyboard shortcut. WP-1406 puts the same fact in the skill
body, because an agent needs to know a `RefinementCancelled` it did not request
is not a bug in its own call.

### Three hygiene rules

- **The recorder deletes a stale `cancel` at start.** Impossible in the run-id
  layout, possible in the flat legacy one, where a leftover file would cancel the
  next fit instantly.
- **Cancel is POST only.** A GET that cancels is one prefetching browser away
  from a bad day.
- **The route resolves the run against the served root and refuses anything
  outside it.** `SimpleHTTPRequestHandler` handles traversal for static files; a
  hand-written JSON route does not get that for free, and `watch` has a verb now.

### Written so intervention can follow

The file is **request-shaped, not a flag**. A later vocabulary — pause, edit a
parameter, re-run a stage — is the same seam with more words in it, and the
recorder declines by name anything it does not know. Nothing here forecloses the
human-in-the-loop work; it is the first member of a set.

The wider seam stays where WP-1401 put it: intervention belongs in the GUI, which
already owns editing and its 409 contract, reached from the watcher's "open in
the GUI" link. This button is the exception that proves it — one verb, because
stopping a runaway is the one thing a reader cannot do from the other side.

### One question left open on purpose

Cancel ships **enabled**, with a flag to serve strictly read-only, for a reader
who is not the person who should be stopping things. The argument for the reverse
default — a flag to *enable* it — is that the button can put a traceback into an
agent's session, and making that a deliberate act is cheap. Decide it in this WP
with the dialog in front of you, and record which way and why.

## Non-goals

- **No second intervention verb.** No pause, no parameter edit, no re-run. The
  request shape is prepared; nothing else is built.
- **No timeout.** `threading.Timer(30, token.cancel)` composes, and
  `optimize/cancel.py` declines to provide one on purpose.
- **No change to `optimize/cancel.py`**, to `RefinementCancelled`'s fields, or to
  the residual wrapper's order.
- **No cancel for a run the watcher did not find**, and none across hosts: a run
  on another machine reads `unknown` and offers no button.

## Tasks

- [ ] The recorder's cancel poll, on the flush clock, with the stale-file
      deletion at start.
- [ ] Token composition: set the caller's if there is one, else create one, and
      only when the recorder is active. Decide lazy-versus-eager attachment
      against WP-1404's configuration 3 and record the choice.
- [ ] The terminal status naming the run cancelled and who asked.
- [ ] The POST route, the run-id resolution against the served root, the
      traversal refusal, and the read-only serving flag.
- [ ] The confirm dialog, with the three sentences above. Looked at, not only
      asserted.
- [ ] Tests: the cancel file sets a caller's own token rather than a second one;
      a recorded fit with no caller token still cancels; a fit with eval events
      off cancels within a cadence, not a stage; `RefinementCancelled`'s
      three fields are unchanged; a GET does not cancel; the read-only flag
      refuses; traversal is refused. Plus a `slow`-marked two-process test — a
      subprocess runs a long fit, the parent writes the file, and the child's
      exit and terminal status are asserted.
- [ ] Skill: **none here**, but this WP is what makes WP-1406's body sentence
      true. Note it in 1406's `### Inherited` when this lands.

## Acceptance

Two terminals: a long fit in one, `rietx watch` in the other. The button stops
it, the script prints its completed stages rather than a traceback from the
telemetry, and the run reads cancelled afterwards.

```sh
.venv/bin/python -m pytest tests/test_run_control.py tests/test_telemetry.py tests/test_watch_app.py
.venv/bin/python -m pytest -m slow tests/test_run_control.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1006 — cooperative cancellation, read between residual evaluations;
  `RefinementCancelled.completed_stages`; why there is no timeout.
- WP-1207 — a run started is a 200 whose failure only ever reaches the event
  stream; the precedent for what a route refuses up front against what it lets
  the worker report.
- The root CLAUDE.md § Telemetry/cancel — the in-flight stage is abandoned, no
  node, no commit, models restored.

## Handover log

- **2026-09-13** — created. The seam is a file because the two processes already
  share a directory and nothing else. The sharpest fact in the whole track lives
  here: a human's click can raise in an agent's process, so the dialog says so
  and WP-1406 puts it in the skill body. Left open on purpose: whether cancel
  should be opt-in rather than opt-out — decide it with the dialog in front of
  you.
