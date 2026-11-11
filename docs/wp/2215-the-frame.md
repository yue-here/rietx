# WP-2215 — the frame: the rebuild's first piece, served at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-11 — the frame is built at `/next`; the maintainer's review rulings are applied, and it waits on the merge
Depends on: 2214 (the rebuild's plan and inventory)
Priority: P2 2026-11-11 — a feature the open milestone was opened for: every later piece of the rebuild mounts in this frame

## Goal

The rebuilt GUI gets its frame, as a second page of the same build. `rietx gui --new` opens
the browser at `/next`; `/` stays today's GUI, unchanged. The frame is what every later piece
mounts in: the top bar, the status bar, the two side panels and the bottom panel with their
toggles and sashes, the workflow menu, the File menu, Settings, the command palette and the
keys, one menu component every later piece uses, the start screen, New project and the
recovery offer, and the Console. It is judged whole beside the prototype at 1440 × 900, light
and dark.

## Context

WP-2214 is the plan. Its § The pieces names R1 and the inventory rows it owns: 1-24 (top bar,
action bar), 147-151 (the Console in the bottom panel) and 212-242 (start screen, New project,
File menu, keys, palette). Its § Two front ends, one server fixes the shape: `gui/next.html`
with its code under `gui/src/next/`, beside `gui/index.html` and `gui/src/App.svelte`, both
importing `gui/src/lib`, `gui/src/api.ts` and `gui/src/tokens.css`, both written into the
committed dist, one session behind both pages. The maintainer's five rulings of 2026-11-11 are
recorded in WP-2214 § Questions; R1 is bound by two of them. The status bar's right half holds
the report's count of findings only, never the mode or the σ source (question 3). Each piece of
chrome text on WP-2214's audit list is settled while its piece is built and listed in the PR
(question 4).

How the frame reads, restated from the prototype (WP-2214 § What the prototype is): a top bar
holding, left to right, the graphs toggle, the workflow menu, the project name that opens the
File menu, a gap, Settings and the model toggle. Below it the graphs on the left and the model
on the right, each with a tab strip ending in a `?` box, split by a sash. The action bar ends
the model panel. Under both, the bottom panel (Console, History), hidden at first. Along the
foot, the status bar, with the console toggle at its left. The bars never change shape, so no
toggle moves (`gui/STYLE.md` § Layout and panels).

What it carries from closed work (WP-2214 § What happens to the open GUI pull requests):

- from #1521 (WP-2206, WP-2207), `lib/statusbar.ts` with its tests, the Console's Copy and
  Follow, the bottom panel's sized pane, and the first-run-moves-nothing browser case;
- from #1524 (WP-2204), `lib/workflows.ts` with its tests, and the placeholder screen's content;
- from branch `wp2213-the-graph-window` (head eaabe834f), `panels/Menu.svelte` and
  `lib/portal.ts`;
- from #1522 (WP-2201), the `style.test.ts` guard against uppercase and tracked headings. The
  new page's stylesheet starts in sentence case.

## Tasks

- [x] The page: `gui/next.html` and `gui/src/next/`, built in a second Vite pass; the server
  serves it at `/next`; `rietx gui --new` opens the browser there. `/` is unchanged. The
  manual's route partition needs no entry: `/next` is a page like `/`, outside the route
  table `test_gui_manual.py` partitions.
- [x] The frame: top bar, status bar, the graphs and model columns with their tab strips,
  their collapse toggles (⌘1, ⌘2) and the sash, the bottom panel with the Console (⌘J); the
  run state and Stop in the status bar (⌘.).
- [x] One menu component and the workflow menu on it.
- [x] The File menu and the project name, mounted from today's `FileMenu`.
- [x] Settings (⌘,): theme as Match system, Light, Dark; the About line with the version.
- [x] The command palette (⌘K) and the keys (rows 228-240), with `?` listing them.
- [x] The start screen and New project mounted in the frame. The recovery offer moves to
  R2: it offers pending edits back, and `/next` has none until R2 brings the edit verbs.
- [x] The action bar (rows 18-24) moves to R2, whose row in WP-2214 § The pieces names "the
  action bar with one Apply": every control in it acts on edits R2 brings.
- [x] `gui/CLAUDE.md` gains a `gui/src/next/` line; the `style.test.ts` sentence-case guard
  covers `gui/src/next/`.
- [x] Screenshots of each screen beside the prototype's, light and dark, at 1440 × 900, under
  `docs/wp/2215-screenshots/` (the prototype's own stay in the runner's scratch).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Questions

Answered by the maintainer on 2026-11-11, on PR #1534. Each item keeps its question and ends
with the ruling in the maintainer's words.

1. **The workflow menu's mark for an unbuilt workflow.** R1 wrote "placeholder" after each
   workflow that is not built. The maintainer had ruled on 2026-11-10 that such an entry says
   "not built yet" everywhere. **Ruled 2026-11-11: "Yes."** R1 merges once the menu, the
   palette and every other label in `gui/src/next/` say "not built yet". Done:
   `lib/workflows.ts:NOT_BUILT_MARK`.
2. **The fonts.** `gui/STYLE.md` § Type sets words in Instrument Sans, Greek in IBM Plex Sans
   and numbers in IBM Plex Mono, each served by the app itself. R1 named the faces but shipped
   no files, so a machine without them drew the system face. Settled by Claude under the
   2026-11-06 type ruling and STYLE's "every font is served by the app itself": ship them as
   files, as the manual does. **Ruled 2026-11-11: "Agree."** Done: the manual's
   Instrument Sans and Plex Mono files byte for byte, a Greek-only Plex Sans in weights 400,
   500 and 600, each with its OFL text, under `gui/src/next/static/fonts/` and declared in
   `gui/src/next/fonts.css` alone.
3. **The status bar when no fit runs.** The review asked whether the idle bar should say the
   last run's status (`runWords` can). The frame leaves it empty. **Ruled 2026-11-11:
   "Agree."** It stays empty; nothing to build.

## References

- [WP-2214](2214-the-gui-rebuild-plan-and-inventory.md), the plan and the inventory; `gui/STYLE.md`;
  `gui/CLAUDE.md`; the milestone record `docs/milestones/gui-overhaul.md`.

## Handover log

- **2026-11-11** — The maintainer's three review rulings on PR #1534 are applied (§ Questions).
  The workflow menu and the command palette now mark each unbuilt workflow "not built yet",
  and no label in `gui/src/next/` says "placeholder". The frame now draws in its own faces:
  Instrument Sans for words, IBM Plex Mono for numbers and code, and IBM Plex Sans for Greek.
  The idle status bar stays empty.

  *Done.* The fonts are 13 woff2 files and 3 licence texts (218 638 bytes) under
  `gui/src/next/static/fonts/`. The second build pass copies them into the dist's `fonts/`
  (vite's `publicDir`, set for that pass only), and `gui/src/next/fonts.css` declares them
  with `font-display: swap` and a unicode-range each. Ten files are the manual's, byte for
  byte. The three Plex Sans Greek files come from `@fontsource/ibm-plex-sans` 5.3.0 on npm
  (tarball sha256 `232592af…3213`), the source WP-2021 used. `next.css` points
  `--mono-family` at Plex Mono, with Plex Sans after it for Greek. Today's page is byte for
  byte as it was: the build changed `next.css`, `next.js` and `build-info.json` and added
  `fonts/`, nothing else. `tests/test_gui_dist.py` gains one case: the shared files equal the
  manual's, every family has its licence, the rebuild's stylesheet declares exactly the files
  shipped, and `app.css` declares none. Its remote-host check now reads the stylesheets too.
  The wheel carries the fonts, so ATTRIBUTION.md says so.

  *Measured* (`[dev]` venv, darwin arm64). vitest 762 passed in 37 files (unchanged: the
  edits renamed labels); svelte-check 433 files, 0 errors; `tests/test_gui_dist.py` 16 passed
  (one new); every `tests/*_browser.py` file, python `playwright` installed: 158 passed, 0
  skipped. No Python outside `tests/` changed, so the fast suite was not rerun. The screens
  under `docs/wp/2215-screenshots/` were retaken with the fonts loaded. `gui/CLAUDE.md` takes
  no fonts rule: it sits at its 667-line cap, and the rule lives in `vite.config.ts`,
  `fonts.css` and the test.

  Next: the maintainer merges #1534; R2 follows.
- **2026-11-11** — The rebuilt GUI now has a frame you can open:
  `rietx gui --new` serves it at `/next`, beside today's page, which is unchanged. It has the
  prototype's top bar and status bar, the graphs and model columns with their tab strips,
  toggles and sash, the bottom panel with the Console, the workflow and File menus, Settings,
  the command palette and the list of keys, and the start screen with New project. The panes
  are empty: the later pieces fill them. Two tasks moved to R2 because they act on edits, and
  `/next` has none until R2 brings them: the action bar and the recovery offer.

  *Done.* The page is a second Vite pass (`vite build --mode next`), because one multi-entry
  pass made today's page load a shared chunk. The second pass prefixes its own chunks
  (`next-*`), so it can never overwrite a chunk `app.js` imports; today's dist stayed byte
  for byte. The server serves `/next` through one page lookup that the not-built banner
  shares. The frame carries `lib/statusbar.ts` (#1521) and `lib/workflows.ts` (#1524) with
  their tests, `Menu.svelte` from branch `wp2213-the-graph-window`, and #1521's Console. Its
  stylesheet `gui/src/next/next.css` draws the prototype's sizes over `app.css`: 14 px words,
  36 px bars and tab strips, 30 px buttons, icon buttons with a border on hover only, tabs
  that keep their weight when selected. A key never opens a second dialog over one already
  up. Screens: `docs/wp/2215-screenshots/`.

  *Settled under `gui/STYLE.md` or the plan* (each listed in the PR):
  the action bar and the recovery offer go to R2 (WP-2214's R2 row names the action bar);
  Settings has the theme and About only, density and number format waiting for the pieces
  that draw what they change (the milestone row now says so); the workflow button is as wide
  as its name, as the prototype's is, so the project name beside it moves when the workflow
  changes; the File menu keeps today's `▾` caret; index and series show as placeholders in
  `/next` until R6 and R7; `?` boxes on the tab strips (row 246) wait for the help piece.

  *Measured* (`[dev]` venv, darwin arm64; another shift's sessions may have shared the
  machine). Fast suite on the final tree: 14557 passed, 424 skipped, 32 xfailed, 8-8.5 min,
  the same total (14981) as before the review fixes; the one added python case,
  `test_the_rebuilt_page_is_served_beside_todays`, costs 0.03 s. The browser module skips at
  import without python `playwright`, so its two new cases add no count here.
  vitest 762 passed in 37 files (14 new in `next/`, 3 in `lib/workflows.test.ts`, the carried
  statusbar cases); svelte-check 433 files, 0 errors. `tests.reader_output`: unchanged. Vale:
  0 errors. The six GUI browser files (python `playwright` installed): 87 passed, 0 skipped, 2 new.

  *Review.* `/code-review high --fix` found nine; six fixed in one commit (stacked dialogs,
  the second pass's chunk names, an unguarded boot, the banner, the duplicated page branch,
  the `title=` budget). Declined: the Console's dropped-frames count is always 0, here and in
  `App.svelte`, because `follow()` does not report its losses (a `lib/stream.ts` change for
  R5, which owns the bottom panel); `lib/style.test.ts`'s register guards do not scan
  `gui/src/next/` yet, which needs a call on whether `.ib` and `.mbtn` are registers; the
  status bar shows nothing when idle, where `runWords` can say the last run's status.

  *Gotchas.* The worktree guard refuses heredocs with `${`; edits went through scripts in
  the runner's scratch. A browser test needs python `playwright` in the worktree venv
  (`uv pip install --python .venv/bin/python playwright`), or the module skips green.

  Next: the maintainer looks at the screens beside the prototype's (paths in PR #1534). Then
  R2, which takes the action bar, the recovery offer and the hover readout, and decides
  whether `.ib` and `.mbtn` join the register table and its guard.
- **2026-11-11** — filed by a ghostshift runner from WP-2214's piece R1, the last task of that
  WP, which closes with it. No open WP owned the frame: WP-2214's plan names it as the first
  piece and leaves it to be filed. The number was checked against `origin/main`, the remote
  branches and the open pull requests.
