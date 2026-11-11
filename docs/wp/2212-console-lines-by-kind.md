# WP-2212 — console lines by kind: the `>>>` prompt and the session as a script

Milestone: gui-overhaul · Status: ⬜
Depends on: 2214 (the rebuild's plan: it builds on piece R1's bottom panel)
Priority: P3 2026-11-11 — P2 (a feature the open milestone was opened for), down a rung: it builds on the bottom panel, so nothing starts until the rebuild's R1 lands (re-pointed 2026-11-11 by WP-2214)

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

### Inherited

- **2026-11-11, from WP-2214** (the rebuild's plan). The maintainer ruled the same night to
  rebuild the GUI's front end beside today's instead of porting it piece by piece. PR #1521
  (WP-2206, WP-2207) closes as a source and never merges, so this WP builds in the new front
  end, on the bottom panel its piece R1 builds, as part of piece R5. The design above stands;
  what it says about `panels/History.svelte` and `panels/Console.svelte` describes today's GUI,
  which the new page replaces at the swap. WP-2214's inventory gives the homes this WP must
  keep reachable.

## Non-goals

- The History table, Compare and Restore: WP-2211.
- A console that accepts typed Python. The console shows what the window ran; agent access is
  the milestone after this one.
- Syntax colouring beyond strings and comments.

## Tasks

- [ ] Questions 1 and 2 drawn and brought to the maintainer; the rulings recorded here with
  their dates.
- [ ] The tagged line type in `say()` and `consoleLine`, every writer passing its kind; the
  echoes spelled with one receiver per name, and each `…` echo made runnable or marked. Vitest
  over the kinds and over every writer's spelling.
- [ ] `Console.svelte` draws by kind: the prompt gutter, the timestamp per entry, the muted and
  faint registers, the string token. Copy copies the calls. Vitest and the layout browser test.
- [ ] The script: a preamble, the uncapped calls, the export kind on the server and in the
  Export submenu. A test drives a short session on a copy of a shipped example (a value set, a
  stage run), runs the exported script on a second copy, and asserts the two heads hold the
  same parameter values.
- [ ] The GUI chapter on the Console and the File menu's Export, the screenshot driver, the
  screenshots retaken, each beside the prototype's at 1440 by 900 in the PR (milestone row 11).
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

- **2026-11-10** — created by a ghostshift runner from WP-2206's follow-ups. No open WP owns
  the Console: a search of the open WPs for console lines and a script export found none. WP-2133
  named the missing writer and is closed. Next: once PR #1521 merges, bring
  questions 1 and 2 to the maintainer.
