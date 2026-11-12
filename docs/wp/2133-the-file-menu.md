# WP-2133 — the File menu on the project name

Milestone: gui-overhaul · Status: ✅ 2026-11-10 — the File menu merged in #1502; the draft of unapplied edits is the milestone's edit-recovery row
Depends on: 2131

## Goal

The project's name in the top bar opens the File menu: New project…, Open…, Open recent ›,
Save a copy…, Rename…, Move to…, Export ›, Close project. Work saves itself, so there is no Save
command, and ⌘S shows a brief "Saved". Save a copy copies the whole `.rex` folder with its
history; Rename and Move act on the folder; Export writes the existing export kinds where the
person chooses; Close returns to the start screen. Each verb is a server route, refused while a
run is in flight, and none overwrites a folder that already exists.

## Context

### Where it is today

The top bar shows the project's name as text, followed by the data file, the point count, the mode
and where σ came from. An `Open…` button beside it shows the start screen over the open project
(WP-2131, settled call 4, which named the File menu as the alternative). The routes a File menu
needs exist only in part:

- `POST /api/project/new`, `POST /api/project/open`, `GET /api/recent`, `POST /api/recent/remove`
  and `GET /api/fs` serve New, Open and Open recent.
- `POST /api/export/<kind>` writes six kinds (CIF, reflections, phase fractions, fit report,
  result JSON, instrument profile) through `GuiSession.export`, always into
  `<project>/exports/`, and replaces a file of the same name there without asking.
- No route copies, renames, moves or closes a project. Without Close, the last project opened is
  always the last one open, so `reopen_last` reads the recent list's head (WP-2131 call 9).
- Pending edits live in the browser (the action bar's pending count, WP-2123). The server keeps
  no draft, so a pending edit does not survive a closed tab or a crash.

The project facts this rests on (root CLAUDE.md § Project): a project is a `.rex/` directory,
`project.json` holds settings and `history.jsonl` holds the model, and every model verb writes
its node at once. So saving is about settings, nothing is ever unsaved, and moving the folder
moves everything. The history log is the one file a live project holds a path to
(`RefinementTree.path`, appended per node); everything else is derived from `Project.path`.

### The design, and the rulings it rests on

The maintainer ruled on 2026-11-07 (file and project I/O, the fifth design session):

1. **Save model A.** Autosave, no Save command. ⌘S shows a short "Saved". The File menu holds
   New, Open, Open recent, Save a copy… (the folder with its history), Rename…, Move to…,
   Export, Close. Pending edits persist with the project as a draft across close and crash.
   Going back is History's Restore.
2. **A text file beside the project** (`.rxt` written next to the `.rex`): deferred to the move
   into the main repo. Not here.

Eight calls Claude settled in that session drew no objection on 2026-11-07. Four bear on this
WP: **Open takes a `.rex` only**; **Export opens a save dialog, starting in the folder that holds
the `.rex`** (after File › Export in every document app; the alternative kept writing into
`exports/`, which a macOS package would hide); **Save a copy keeps the history, and Rename and
Move act on the folder** (the macOS document model); **an in-app recent list**. Two are not here:
registering `.rex` as a macOS package waits for the desktop app, and so does dragging a file
onto the window.

The menu as the maintainer saw it on 2026-11-07 (round 6, "looks good" on that round's other
changes): it opens from the project name in the top bar, as a macOS document title and Figma's
file name do. New project… ⌘N, Open… ⌘O, Open recent › (with Clear the list), Save a copy… ⇧⌘S,
Rename… (the name becomes editable in place), Move to…, Show in Finder, Export › (CIF,
reflections, phase fractions, fit report, result JSON, instrument profile, pattern plot, console
as a Python script), Close project ⌘W. Save a copy and Export open a small dialog with a name and
a folder. Phase fractions is disabled for one phase. Submenus open on hover or click.

What a browser changes. A page cannot show the system's save dialog, reveal a folder, or take
⌘N and ⌘W from the browser. So the folder comes from the existing folder browser (WP-1205,
`GET /api/fs`, confined to the home directory and the working directory), Show in Finder waits
for the desktop app, and so do the ⌘N and ⌘W shortcuts. The pattern plot is already a PNG/SVG
button on the plot (WP-1461), and the console script has no writer yet, so Export lists the six
kinds the server writes.

Rules from the design rounds that bind this work: no click moves the layout unless it asks to
(2026-11-07; the layout browser test); no permanent explanatory text, an explanation lives in a
tooltip (2026-11-07, repeated 2026-11-08); sentence-case headings (2026-11-06); undo replaces
warnings, and asking-to-choose is kept apart from confirming (interaction rule 11, adopted
2026-11-08).

### The maintainer's rulings of 2026-11-09

Two questions this branch raised were ruled by the maintainer on 2026-11-09.

1. **The unapplied-edit draft follows the software field's practice.** The maintainer's words:
   "I would like to follow the software field's best practice, not necessarily diffraction". The
   brief showed that VS Code (hot exit), Blender and Office AutoRecover keep a recovery copy apart
   from the real file. So the draft of pending edits goes in rietx's state directory, keyed by the
   project's path, and the project format does not change. The draft does not travel with Save a
   copy or with a move. Nothing is built here: the draft is a follow-up WP.
2. **The `gui/CLAUDE.md` cap rises by 7 lines** for the File menu's three standing rules: "go".
   The bump carries its diary row in `tests/test_docs_consistency.py` and its paragraph in
   `docs/milestones/process.md`.

### Rulebook seams

- **The 409 contract** (`gui/CLAUDE.md`, WP-1008): a mutating verb returns 409 while a run is in
  flight, and that refusal outranks body validation. Copy, rename, move and close all take it:
  a copy taken while a stage appends to `history.jsonl` could copy half a line.
- **Path safety is containment** (WP-1205): a client-typed path is resolved and checked against
  the two browsable roots, never sanitised. A destination folder takes the same gate, and a name
  is refused if it carries a separator or is a dot name.
- **No overwrite.** A destination folder that exists is refused (409 `DESTINATION_EXISTS`); a
  folder is never replaced. An export into a chosen folder refuses an existing file unless the
  request says `overwrite`, which the dialog sends only after showing the refusal.
- **Routes** (WP-1017): every new route needs its line in a GUI chapter, which
  `tests/test_gui_manual.py` holds both ways.
- **One filled primary per view** (`lib/style.test.ts`): each dialog's own button.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`.

## Non-goals

- A draft of pending edits that survives close and crash. The server keeps none today (pending
  edits are browser state, WP-2123). Ruled by the maintainer on 2026-11-09: the draft lives in
  rietx's state directory, keyed by the project's path, with no project-format change. It is a
  follow-up WP.
- `.rxt` beside the project (deferred by the maintainer, 2026-11-07).
- Registering `.rex` as a macOS package, Show in Finder, ⌘N and ⌘W, and dragging a file onto the
  window: the desktop app's.
- Exporting the pattern plot (already the plot's own PNG/SVG buttons) and the console as a
  Python script (no writer exists).

## Tasks

- [x] Server: `POST /api/project/copy`, `/rename`, `/move`, `/close`, `POST /api/recent/clear`;
  `export` takes a `directory` and `overwrite`; a closed project is not reopened at launch.
  Each refusal tested: an existing destination, a destination outside the roots, a bad name, a
  folder moved into itself, a run in flight.
- [x] Frontend: `panels/FileMenu.svelte` on the project name, `lib/filemenu.ts` (items and the
  export kinds, pinned to `EXPORT_DEFAULTS`), the Save a copy and Export dialogs over the folder
  browser, Rename in place, ⌘S "Saved", ⌘O and ⇧⌘S; the header's `Open…` goes.
- [x] The layout browser test opens the menu, its submenus and both dialogs with real clicks, and
  renames in place, and nothing moves; the dist rebuilt.
- [x] The GUI chapters: the header table, a File menu section, the route table, the keyboard.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_file_menu.py tests/test_gui_layout_browser.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- WP-2131 (the start screen, whose settled calls 4 and 9 this WP takes over), WP-1205 (the
  folder browser and its containment gate), WP-1214 (the export gate).

## Moved from gui/CLAUDE.md

On 2026-11-10 WP-2134 folded this WP's additions to `gui/CLAUDE.md` into the
condensed rulebook as standing rules, each still naming this WP. The text below is
the paragraph that file carried for this WP until then, verbatim. Where it and the
rulebook disagree, the rulebook is current.

**The File menu** (WP-2133, `panels/FileMenu.svelte`, `lib/filemenu.ts`) acts on
the folder. **A rename or a move keeps the session's `Project`** and repoints the
two paths a live one holds (`Project.path`, `RefinementTree.path`); a third such
field joins `GuiSession._relocate`. **A destination passes `_browsable_folder` and
`_project_name`**, never sanitised, and an existing one is refused, never replaced.
**Close is a `closed` mark on the recent list's head**, which `reopen_last` reads.

## Handover log

- **2026-11-10** — closed. PR #1502 merged on 2026-11-10, after #1498. Clicking the project's
  name on `main` opens the File menu, and copy, rename, move and close are server verbs that
  refuse rather than overwrite. A pending edit still does not survive a close or a crash. That
  is the one piece of work this WP named next.

  *Leftovers, and where each went.* The draft of unapplied edits, ruled on 2026-11-09 to live in
  rietx's state directory with no project-format change, is the row "Edit recovery" in
  `docs/milestones/gui-overhaul.md` § Designed, not yet filed. Exporting the console as a Python
  script needs a writer that does not exist; the console itself is the row "Bottom panel".
  `.rxt` kept beside the project is the third of the milestone's open decisions. ⌘N, ⌘W, Show
  in Finder and the `.rex` package wait for the desktop app and are not carried here. The
  thirteen settled calls were reviewed with the PR at its merge. The narrative went to
  `docs/milestones/v1.12.md`.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here.

- **2026-11-09** — the File menu is built, on real routes, and every task is ticked. Clicking
  the project's name now opens New, Open, Open recent, Save a copy, Rename, Move to, Export and
  Close. Copy, rename, move and close are server verbs. Each one refuses an existing destination,
  a folder outside the browser's two roots, a bad name, a folder moved into itself, and a run in
  flight. An export can now go to a folder the person picks, and replaces a file there only when
  asked. Closing a project now survives a relaunch: the next `rietx gui` shows the start screen.
  The header's `Open…` button is gone. A pending edit still does not survive a close or a crash,
  because the server keeps no draft. That is the next item, ruled on 2026-11-09 (§ The
  maintainer's rulings of 2026-11-09).

  *Done.* Server: `project_copy`, `project_rename`, `project_move`, `project_close` and
  `recent_clear` in `session.py`, five routes, and `export` taking `directory`/`overwrite`.
  Frontend: `panels/FileMenu.svelte`, `lib/filemenu.ts` (the items as data, with `EXPORT_KINDS`
  pinned to `EXPORT_DEFAULTS` by `test_gui_file_menu.py`), a `heading`/`start` pair on
  `Browse.svelte`. The manual's header table, a File menu section, five route rows and three
  keyboard rows, plus the first-fit screenshot pair. `gui/CLAUDE.md` takes three rules.
  `/code-review high --fix` found nine. Seven are fixed in `714db343d`: a relative open put
  Save a copy inside the project, a move renamed a suffix-less folder, a case-only rename was
  refused on APFS, an unwritable export was a 500, `/x.rex` sat in itself, a browser started
  outside its roots opened empty, and the console's scrolling closed the menu. Two are declined.
  The `.pick` padding finding is wrong: `app.css` exempts that register from the rule, and the
  start screen's menu does the same. The check-then-move race is every 409 verb's pattern,
  which only a change to the shared run lock can close.

  *Measured* (worktree `[dev]` venv, darwin/arm64). vitest 639 passed in 25 files, 626 before,
  +13: eight in `filemenu.test.ts`, five in `App.test.ts`. Four `App.test.ts` tests that
  clicked the header's `Open…` now reach the start screen through the palette. svelte-check
  0 errors, 0 warnings. `test_gui_file_menu.py` 13 passed. `test_gui_layout_browser.py`
  18 passed, 16 before, +2. Its new File menu test was made to fail once, with the menu forced
  static: the header grew 282 px and the test named it. `test_gui_manual.py` 10 passed.
  Fast suite on the tree merged with `origin/main` (`eee8486d5`): 14498 passed, 410 skipped, 32 xfailed and 1 failed, in 8:39 under serial.py's lock with nothing else running. The one failure was this branch's gui/CLAUDE.md going over its line cap. It is fixed by a shorter rule and a +7 cap with its reason, and test_docs_consistency.py then passed 25. The 23 tests added over main (#1498's six server tests included) cost 10.5 s, 7.4 s of that in the browser file, which skips on CI.
  `tests.reader_output` exit 0, unchanged. ruff clean.

  *Gotchas.* The branch sits on `wp2131-gui-start-screen` (#1498) and must merge after it.
  Close replaces WP-2131's settled call 9: "the last project" now means the one open at quit,
  read off a `closed` mark on the recent list's head.

  *Settled by Claude, reversible, for the maintainer* (call; alternative):
  1. The header's `Open…` is gone, and File › Open… opens the folder browser directly. The start
     screen over a project is reached from the palette. Alternative: keep `Open…` for the start
     screen.
  2. The name is a `.pick` button with a hover tint and a ▾. Alternative: the round-6 prototype's
     border on hover.
  3. The menu copies the start screen's row menus, a grey hover. Alternative: the prototype's
     accent-filled hover.
  4. Submenus open on hover or click, with no arrow-key navigation. Alternative: full keyboard
     menu navigation.
  5. Export starts from the server's file names (`refinement.cif` and so on). Alternative: names
     built from the project, such as `fap.cif`.
  6. Save a copy starts beside the project, as Export does. Alternative: the last folder used.
  7. An existing export file is refused once, and the button then reads `Replace`. Alternative: a
     separate confirm.
  8. Save a copy keeps the window on the original and leaves Recent alone. Alternative: open the
     copy.
  9. A copy includes `live/`, the run records. Alternative: leave them out.
  10. Phase fractions is disabled for one phase and outside Rietveld mode. Alternative: enabled,
      with the server's refusal.
  11. A refusal shows for 4 s under the name and in the console. Alternative: a line in the menu.
  12. The rename box is a 16em overlay that also commits on blur. Alternative: Enter only.
  13. ⌘N, ⌘W and Show in Finder are left out, and so are the plot and console-script exports,
      which the desktop app and the plot's own buttons hold.

  Next: (1) review and merge #1498, then this one, #1502; (2) a draft of pending edits that survives
  close and crash. Ruled 2026-11-09: it goes in the state directory, keyed by the project's path,
  with no project-format change, as a follow-up WP; (3) the maintainer's rulings on the visual
  calls above.

- **2026-11-09** — filed by a ghostshift runner, as 2133 because 2132 was taken on `main` the same
  day. No open WP owned the File menu: WP-2131's non-goals name it as a later WP, and the
  milestone's other open WPs (2125-2130) are the Parameters panel, the Plan tab, previews, the
  Background tab and the Peaks panel. Next: start the checklist.
