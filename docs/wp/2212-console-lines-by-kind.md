# WP-2212 — console lines by kind: the `>>>` prompt and the session as a script

Milestone: gui-overhaul · Status: 🔄 2026-11-21 — claimed by @yue-here (ghostshift runner)
Depends on: 2214 (the rebuild's plan: it builds on piece R1's bottom panel)
Priority: P2 2026-11-17 — was P3: R1's bottom panel landed with WP-2215 (#1534), so nothing blocks it; a feature the open milestone was opened for

## Goal

Each Console line knows its kind. A call the window ran shows behind a `>>>` prompt, its
continuation lines behind `...`, and what came back (engine events, results, refusals) in the
muted register. File › Export offers "Console as a Python script". It writes the session's calls as a `.py`
file that runs on a copy of the project.

## Context

### Where it starts

WP-2206 (PR #1521, not yet merged on 2026-11-10) moved the Console into the bottom panel and
gave it the prototype's Copy, and left this as its follow-up. After that PR,
`gui/src/panels/Console.svelte` draws `lines: string[]` as one `<pre>`. Every line is a plain
string, so the panel cannot tell a call from an event. The writers:

- `say(line)` in `gui/src/App.svelte` appends to `lines` and keeps the last 400
  (`lines.slice(-400)`). Most panels reach it through a callback; on `main` of 2026-11-10,
  15 files under `gui/src/panels/` use the word `say`.
- What they write is mixed. Calls (`project.save()`, `ref.set_values({...})`, a route's
  `api_call`), comments (`# project: …`), refusals (`refused: …`, `peaks: …`), run states
  (`FAILED …`, `cancelled at stage …`), and engine events through `lib/stream.ts:consoleLine`.
- The calls name seven different receivers, counted over `gui/src` on `main` of 2026-11-10:
  `ref.` (17 sites), `project.` (7), `tree.` (3),
  `instrument.` (2), `shutil.` (2), `structure.` (1) and `session.` (1). `session.settings_patch` is not public API. Some are not runnable as written: `ref.fit(data, plan=…)`,
  `index_pattern(peaks, data=…, instrument=…)`, and `project.open(${path})` without quotes.

WP-2133 (the File menu, closed) left the console export out of its Export submenu because no
writer existed (its settled call 13). This WP is that writer.

### The design, and the rulings it rests on

The prototypes are not published, so the design is restated here.

- **The rulings.** "A collapsible console showing what the Python is actually doing" (the
  maintainer's sixth review, 2026-11-07). The File menu lists "Console as a Python script"
  under Export (the file and project I/O ruling, 2026-11-07, whose eight settled calls drew no
  objection). Port acceptance (2026-11-09): a piece hews close to the prototype through
  `gui/STYLE.md`, and completes what the prototype left unfinished by the guide's motives.
- **The prototype's Console** is the session as a script, in the monospace face. Each entry is
  a timestamp line (`HH:MM:SS`, faint), then the calls, then their output. A call's first line
  takes a `>>> ` prompt and each further line `... `, the prompt drawn in the faint ink and not
  part of the copied text. Output lines are muted. Comments are faint and italic. String
  literals take a colour of their own. The session opens with the lines that bind the names
  the calls use: `import rietx as rx`, `p = rx.Project.open("<name>.rex")`,
  `ref = p.refinement`.
- **Copy** copies the calls alone, one per line, without prompts, timestamps or output.
- **Export** names the file after the project (`fluorapatite.py` in the prototype), through the
  Export dialog WP-2133 built.

### What the prototype does not settle

1. **Engine events.** The prototype's console holds only calls and their one-line results. The
   real one also streams engine events. They can run to thousands of lines a fit. Claude's
   reading: an event is output, drawn muted under the call that started the run, and left out
   of Copy and the script. Whether events fold under their call is a visual question for the
   maintainer.
2. **The string colour.** The prototype hard-codes a green in each theme. A colour is a token
   in `src/rietx/viz/theme.py` (milestone acceptance row 4), and a new token is a visual
   question for the maintainer.
3. **What a script can repeat.** A call echoed with `…` cannot run. Each echo either becomes the
   real call or is written to the script as a comment saying what it stands for. The 400-line
   cap drops a long session's start, so the script is built from a store of calls that is not
   capped, or says at its head that it is partial.

### Rulings

Questions 1 and 2 went to the maintainer on 2026-11-21 as drawn options: whole windows of the
prototype with the changed region boxed, on a private page.

- **Question 1, 2026-11-21, the maintainer: events fold under their call.** Under a run's call,
  one muted line sums the events ("42 engine events, 5 stages, 30 evaluations" on the options
  page), closed by default. A click opens it, and the events list indented and muted under
  their call. Events stay out of Copy and the script.
- **Question 2, 2026-11-21, on no objection: one string token**, `#2f6f3e` in the light theme
  and `#8fc79d` in the dark, as drawn on the options page. It goes into
  `src/rietx/viz/theme.py`. It was offered as "this lands unless you object", and the
  maintainer answered the other questions without objecting.

### Seams

- **One tagged line type.** `say()` and `consoleLine` write `{kind, text}` with kind one of
  call, output, comment, refusal and event. `Console.svelte` draws by kind. Copy and the script
  read the call lines. Every writer passes its kind, so a new writer cannot forget one.
- **One receiver per name.** The script's preamble binds every name a call uses. The cheaper
  route is one spelling across the echoes (`p` for the project and `ref` for its refinement, as
  the prototype has). `session.settings_patch` is a GUI setting, so it becomes a comment.
- **The export.** WP-2133's Export dialog and `GuiSession.export(kind, body)`, with
  `directory` and `overwrite`, write into the project's `exports/`. The script kind joins
  `EXPORT_DEFAULTS` and `tests/test_gui_file_menu.py`'s pin.
- **No click moves the layout** (milestone row 1): a prompt is drawn in a fixed gutter, so a
  line's text starts at one edge whatever its kind.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`.

### Folded in on arrival

Pruned 2026-11-21 at start: all four entries still hold on `origin/main` (`d76e4dd48`), so each became a task below.


- **2026-11-11, from WP-2214** (the rebuild's plan). The maintainer ruled the same night to
  rebuild the GUI's front end beside today's instead of porting it piece by piece. PR #1521
  (WP-2206, WP-2207) closes as a source and never merges, so this WP builds in the new front
  end, on the bottom panel its piece R1 builds, as part of piece R5. The design above stands;
  what it says about `panels/History.svelte` and `panels/Console.svelte` describes today's GUI,
  which the new page replaces at the swap. WP-2214's inventory gives the homes this WP must
  keep reachable.
- **2026-11-21, from WP-2229** (its review's finding 8, left open). `PATCH /api/instrument`
  answers `freed` and `fixed` as the lists it offered `ref.set_vary`, not what the verb
  returned (`GuiSession.instrument_patch` in `src/rietx/gui/session.py`). `set_vary` can refuse
  a locked or force-fixed path and returns what it changed (root CLAUDE.md § A hold). The
  console line `ref.set_vary([...], True)` then names a path that stayed fixed. A console that
  exports itself as a script inherits that line; take the verb's return in the answer before
  the export trusts it.
- **2026-11-21, from WP-2229** (its review's finding 5, left open; settled by Claude under
  WP-2229's own rule, at the maintainer's word "settle it yourself"). `_register_arms`
  (`src/rietx/gui/session.py`) returns `None` when either model builds no parameter table, and
  `instrument_patch` then edits with no register work. A failing *new* table is harmless: the
  edit is refused. A failing *old* table with a working new one lands the edit untidied. The
  one instrument-side way found is a free capillary offset with no `goniometer_radius_mm`
  (`ParameterTable`'s refusal in `params/vector.py`); structure-side refusals fail both
  tables. A hold left that way can reattach to a background term of the same name. Fix: when
  only the old table fails, work from the registers. Release every held `instrument.` path
  the new table lacks, and every held background path when the kind or breakpoints changed.
  Leave the free arm to the new model's `vary` as now. One server test that breaks the old
  model this way. Folded here beside finding 8 because both live in `instrument_patch`.
- **2026-11-21, issue triage (#1656 item 1): the Console always says 0 frames dropped.**
  Checked at `c1033a0e8`. `gui/src/next/Console.svelte` prints "N frames dropped" when
  `dropped > 0`. `Frame.svelte` (line 57) and `App.svelte` (line 86) each declare
  `let dropped = $state(0)` and never assign it. `follow()` in `gui/src/lib/stream.ts` keeps
  a `Cursor` whose `dropped` count `advance()` grows on the polling path, then never hands
  it to a caller. The SSE path moves `cursor.seq` on each event without checking for a gap,
  so it counts nothing. WP-2214's inventory keeps the line (row 150, "N frames dropped").
  Fix: `follow()` reports its losses on both paths through a callback or its state, and the
  Console reads it. One vitest case per path, with a batch whose `oldest` skips ahead.

## Non-goals

- The History table, Compare and Restore: WP-2211.
- A console that accepts typed Python. The console shows what the window ran; agent access is
  the milestone after this one.
- Syntax colouring beyond strings and comments.

## Tasks

- [x] Questions 1 and 2 drawn and brought to the maintainer; the rulings recorded here with
  their dates (§ Rulings, 2026-11-21).
- [x] The tagged line type in `say()` and `consoleLine`, every writer passing its kind; the
  echoes spelled with one receiver per name, and each `…` echo made runnable or marked. Vitest
  over the kinds and over every writer's spelling.
- [x] `Console.svelte` draws by kind: the prompt gutter, the timestamp per entry, the muted and
  faint registers, the string token. Copy copies the calls. Vitest and the layout browser test.
- [x] The script: a preamble, the uncapped calls, the export kind on the server and in the
  Export submenu. A test drives a short session on a copy of a shipped example (a value set, a
  stage run), runs the exported script on a second copy, and asserts the two heads hold the
  same parameter values.
- [ ] The GUI chapter on the Console and the File menu's Export, the screenshot driver, the
  screenshots retaken, each beside the prototype's at 1440 by 900 in the PR (milestone row 11).
- [x] `follow()` reports the frames it lost on both paths, and the Console reads the count
  (#1656 item 1, folded above). One vitest case per path.
- [ ] `instrument_patch` answers what `set_vary` returned (WP-2229 finding 8), and works from
  the registers when only the old table fails (finding 5). One server test each.
- [ ] Skill: none. The GUI is a human surface, and an agent drives the python API.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_file_menu.py tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The browser files skip in CI (no playwright there), so the PR quotes their local counts.

## References

- The maintainer's rulings of 2026-11-07 (sixth review, file and project I/O) and 2026-11-09
  (port acceptance), restated above.
- WP-1029 (the Console's sized pane), WP-2133 (the File menu and its Export dialog), WP-2206
  (the bottom panel).

## Handover log

- **2026-11-21** — The maintainer has ruled the console's two open visual questions from drawn
  options, so the session that builds it can start on the code. A fit's engine events fold
  into one muted summary line under the call that started it, closed by default, and a click
  lists them. String literals take one green token in each theme. Nothing is built yet.
  *Done*: § Rulings written; the questions task ticked. The string token was offered as
  "lands unless you object" and drew no objection, which § Rulings says. Next: the tagged line
  type in `say()` and `consoleLine`, since the fold, Copy and the script export all read the
  kind it carries.

- **2026-11-10** — created by a ghostshift runner from WP-2206's follow-ups. No open WP owns
  the Console: a search of the open WPs for console lines and a script export found none. WP-2133
  named the missing writer and is closed. Next: once PR #1521 merges, bring
  questions 1 and 2 to the maintainer.
