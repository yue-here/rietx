# WP-2237 — a project opened in the same window streams its events from the first

Milestone: gui-overhaul · Status: 🔄 2026-11-22 — claimed by @yue-here (ghostshift runner)
Depends on: —
Priority: P3 2026-11-22 — a view over what the fit already knows; reloading the page is the workaround

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
- [ ] A vitest case on `follow()` if the client changes.
- [ ] Skill: none. The GUI is a human surface.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py
npm --prefix gui test
```

## Handover log

- **2026-11-22** — filed by WP-2212's handover from its code review's out-of-diff finding. No
  open WP owns the event stream across a project switch: the open gui-overhaul WPs are 2211
  (History), 2227 (how a refine ran) and 2231 (Plan and Text tabs), and none reads `follow()`.
  Next: the first task.
