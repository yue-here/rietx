# WP-2237 — a project opened in the same window streams its events from the first

Milestone: gui-overhaul · Status: ✅ 2026-11-22 — the event seq keeps rising across an open; a reconnect resumes at Last-Event-ID; the client class is WP-2242
Depends on: —

## Goal

After File › Open (or an example) replaces the session's project, the Console shows the new
project's engine events from its first run, and the dropped-frame count stays honest.

## Context

Found by WP-2212's `/code-review` pass on 2026-11-22, outside that WP's diff, and checked
against the tree at `cc6e27764`.

- `GuiSession._adopt` (`src/rietx/gui/session.py`) clears the event ring and sets
  `self._seq = 0` whenever another project is opened in the session.
- Both pages call `follow()` (`gui/src/lib/stream.ts`) once, at mount
  (`gui/src/next/Frame.svelte`, `gui/src/App.svelte`), and never again on an open. The
  cursor keeps the old project's `seq`.
- On the polling path, `api.events(since)` then asks for events after the old count. The new
  project's events up to that count are never delivered. On the SSE path the stream's own
  `since` is stale the same way, and a reconnect re-opens with the stale cursor.
- Run-state frames still arrive, because they are keyed on the state and not on `seq`. So a
  run's end still reloads the result. Only the events are missing.
- The drop counter (WP-2212) sees no gap either, since `oldest` is below the cursor.

Two fixes are plausible. The server can keep `seq` rising across an open, so every cursor
stays valid. Or the page can restart `follow()` from 0 on an open. The first touches one line
and no client; check that nothing reads `seq == 1` as "a fresh session" first.

## Non-goals

- The run-state frames, which already work.

## Tasks

- [x] Choose the fix (server-side monotonic `seq`, or the page re-following on open) and write
  why in the handover.
- [x] A server test: open a second project after a run of N events, run again, and the poll
  from the old cursor returns the new run's events.
- [x] A vitest case on `follow()` if the client changes. Not owed: the client is unchanged.
- [x] Sibling, same stream (found by this session's browser probe): a reconnecting
  EventSource resumes at its `Last-Event-ID`, not at the `since` of the URL it first opened.
  Test: `test_a_reconnecting_stream_resumes_at_its_last_event_id`.
- [x] Sibling survey of per-project client state across an open: filed as WP-2242.
- [x] Skill: none. The GUI is a human surface.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py
npm --prefix gui test
```

## Handover log

- **2026-11-22** — closed. Opening another project in the same window keeps the event
  numbering rising, so a page that keeps following after the open reads the new project's
  engine events from the first. A browser probe showed the live page over SSE had mostly
  recovered on its own already: the server's stream loop takes its next cursor from the
  session, so it followed the reset once the open woke it. What lost events was the polling
  path, and the moment between the open and that wake. The same probe turned up a sibling in
  the same stream: a dropped SSE connection replayed the whole ring into the Console, and now
  resumes where it stopped. A survey for other per-project state an open leaves behind found
  a wider class in the client, filed as WP-2242. PR #1787.

  *Decision (task 1): the server keeps `seq` rising.* `GuiSession._adopt` clears the ring and
  no longer resets `_seq`. Grounds: a run's start already cleared the ring without resetting
  `_seq`, so the open was the one place that renumbered. Nothing reads `seq == 1` as a fresh
  session (grepped `src/rietx/gui`, `gui/src` and `tests/`; the review agent checked the
  client independently). One server line fixes both pages, both stream paths and any future
  host, with no dist rebuild. The runner-up, each page re-following from 0 on an open, needs
  two pages changed and a rebuild, and leaves the SSE loop's and `Last-Event-ID`'s numbering
  stale.

  *Done.* `_adopt` keeps `_seq`
  (`test_a_cursor_held_across_an_open_reads_the_new_projects_events`: poll and
  `session.follow` from the old cursor return the new run's events, and `oldest` reads no
  gap). The SSE route reads `Last-Event-ID` through `GuiSession.resume_at`, honoured only
  between the URL's `since` and the session's count, since an id past the count was numbered
  by another process (`test_a_reconnecting_stream_resumes_at_its_last_event_id`). The client
  is unchanged, so task 3's vitest case is not owed. `/code-review high --fix` found six
  things: two fixed (an ASCII-only header guard, since `"²".isdigit()` is true and `int()`
  refuses it; the test's stream helper raising on a closed stream instead of spinning). Four
  declined: an exact restart check needs a per-process epoch in the SSE `id:`, a wire-format
  change, for a window that needs a restarted server to emit more events than the old id
  before the browser's ~3 s retry; `follow()`'s stale reconnect comment in `lib/stream.ts`
  needs a dist rebuild and went to WP-2242; the older SSE test's hand-written parser is
  cleanup outside the diff; the untested restart case follows the first.

  *Sibling survey.* One read-only agent traced every piece of client state from both pages'
  open handlers. Two of its claims re-checked at the line. Node ids are `n{len:04d}`, so two
  projects with equal node counts share a head id, and every panel that reloads on `head`
  alone keeps the old project's data. Worst case: today's page keeps `applied`, and the
  Report tab's Undo then checks out the old project's undo id in the new tree. Not
  generalised here: it is a different mechanism (an id that repeats, against a counter that
  reset), it spans about eighteen items on two pages, and each fix needs a dist rebuild while
  the R6 runner works in `gui/dist`. Filed as WP-2242, P2.

  *Measured* (`[dev]` + playwright 1.65.2, darwin/arm64, load average 20-23 from other
  sessions): the fast selection 15333 passed, 436 skipped, 32 xfailed, run through ghostshift's
  `serial.py`, 11:52 wall under that load. `tests/test_gui_server.py` 195 passed alone after the review fixes.
  Every GUI browser file ran inside it and passed: test_gui_browser 4,
  test_gui_console_browser 1, test_gui_layout_browser 49, test_gui_peaks_browser 2,
  test_gui_recovery_browser 5. vitest 968 passed in 57 files (client unchanged). Probe
  (`~/.cache/ghostshift/rietx/wp-2237/probe.py`, `/next` over SSE, project B opened by the
  route): fixed tree, A's run put 3 engine events in the Console and B's run 3 more; with
  `_seq = 0` restored, also 3 more, which is how the SSE self-healing was found. Both new
  tests fail with their fix reverted (`0 == 3` on `next`; `1 == 3` on the resumed seq).
  The two added tests cost 0.71 s and 0.30 s locally (`tests.added_test_times`).

  *Gotchas.* The Context's line "On the SSE path the stream's own `since` is stale the same
  way" held for the client's cursor and a reconnect, not for the open stream itself. An
  EventSource reconnect re-opens its first URL, so the URL's `since` is the cursor at mount.

  Next: WP-2242's first task. Its Undo item on today's page moves the working state.

- **2026-11-22** — filed by WP-2212's handover from its code review's out-of-diff finding. No
  open WP owns the event stream across a project switch: the open gui-overhaul WPs are 2211
  (History), 2227 (how a refine ran) and 2231 (Plan and Text tabs), and none reads `follow()`.
  Next: the first task.
