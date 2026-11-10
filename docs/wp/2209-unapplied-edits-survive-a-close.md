# WP-2209 — unapplied edits survive a close or a crash

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by @yue-here (ghostshift runner)
Depends on: 2133
Priority: P2 2026-11-10 — a piece the gui-overhaul milestone was opened for, ruled 2026-11-09

## Goal

An edit the action bar holds but nobody has applied is kept in a recovery copy in rietx's
state directory, keyed by the project's path and apart from the project. Closing the project,
opening another, closing the browser tab or killing the server loses at most the last half
second of typing. Reopening the project offers the kept edits, and the person restores or
discards them. The copy is deleted once the edits are applied or discarded.

## Context

### Where it is today

The GUI saves itself (save model A, ruled 2026-11-07, WP-2133). Settings persist on the verb
and the model lives in `history.jsonl`. An edit is *pending* until Apply. The action bar
(`gui/src/App.svelte`, `ActionBar`) counts three kinds of pending edit as one set:

- the Parameters panel's typed values, vary ticks, holds, limits, restraints and typed
  positions (`gui/src/panels/Params.svelte`, six maps: `edits`, `varyEdits`, `holdEdits`,
  `limitEdits`, `restraintEdits`, `positionEdits`);
- the Interactive panel's slider values (`gui/src/panels/Interactive.svelte`, `edits`,
  WP-2128);
- an edited plan in the Plan tab (`gui/src/panels/Plan.svelte`, `stages` and `guard` against
  the stored plan, WP-2127).

All three live only in the browser. A close, a crash or a tab closed loses them. Opening
another project from an open one is worse: the Parameters and Interactive panels stay mounted
across an open and keep their maps, so one project's pending values were carried into the
next project's Apply (found while reading for this WP; the Plan tab is re-created on every
open by `{#key opens}` and was safe).

The Model panel's forms and the Text panel's buffer do not share this mechanism. Each applies
through its own button and is not counted by the action bar, so they are outside this WP.

### The ruling

The maintainer, 2026-11-09, on WP-2133's brief: "I would like to follow the software field's
best practice, not necessarily diffraction". The brief showed that VS Code (hot exit), Blender
and Office AutoRecover keep a recovery copy apart from the real file. So the draft goes in
rietx's state directory, keyed by the project's path, and the project format does not change.
The draft does not travel with Save a copy, or with a move made outside the app.
`gui/STYLE.md` § Interaction carries it as a rule: "An edit is pending until Apply. Pending
edits survive a close or a crash in a recovery copy kept in rietx's state directory, apart
from the project, as editors such as VS Code keep theirs." The milestone row (Edit recovery,
`docs/milestones/gui-overhaul.md`) adds that reopening offers the edits, and the person
restores or discards them.

### Practice

Read 2026-11-10 for this WP.

- **VS Code hot exit.** Unsaved changes are backed up "as soon as the working copy reports a
  content change", into a `Backups` folder in the per-user application data
  (`~/Library/Application Support/Code/Backups` on macOS), apart from the files. A backup is
  deleted once the copy "is saved and no longer reports as dirty", so a save or a revert
  removes it. On the next launch the backups are restored as dirty editors without asking,
  "so that the user is always aware of unsaved changes". Crash recovery works whatever
  `files.hotExit` says. Sources: the VS Code user guide (Basic editing § Hot Exit), the
  Working Copies page of the VS Code wiki, the hot-exit blog post of 2016-11-30.
- **JupyterLab checkpoints** answer a different question. Autosave writes the real file every
  120 s by default. A checkpoint is a copy of the last *manual* save, kept beside the file in
  `.ipynb_checkpoints/<name>-checkpoint.ipynb`, one per file, and File › Revert Notebook to
  Checkpoint goes back to it (`jupyter_server.services.contents.filecheckpoints`:
  "only supports one checkpoint per file"). There is no copy of unsaved edits. rietx's
  history already does the checkpoint's job, with every node restorable.
- **Blender** writes `quit.blend` to the temp directory on quit and an autosave file on a
  timer, both offered from File › Recover. **Office AutoRecover** offers recovered documents
  in a Document Recovery pane on the next start (the workshop's survey of 2026-11-07).

Where this WP departs: VS Code restores without asking, and the ruling asks rietx to offer.
The offer is a choice between two outcomes, so it is interaction rule 11's asking-to-choose
(`gui/STYLE.md`), never a confirmation.

### The design

- **Server.** `src/rietx/gui/recovery.py` owns the files: one JSON file per project under
  `<state dir>/recovery/`, named by the sha256 of the project's resolved path. It carries a
  record tag, the path, the head node the edits were made against, the time, and the client's
  draft as an open dict (the frontend owns its keys, as it owns `ui`). A write goes to a
  temporary name and is renamed into place, so a crash mid-write leaves the last good copy.
  Two routes: `GET /api/recovery` answers the open project's copy or `null`, and
  `PUT /api/recovery` writes `{project, draft}` or deletes on `draft: null`. A `project`
  that is not the open one is refused, so a write sent before an open landed cannot land on
  the next project. Neither route is behind the run's 409: like `/api/settings`, nothing here
  can disagree with a run, and edits made during a run must still be kept.
- **One authority per fact** (root CLAUDE.md § Project). The copy holds *proposed* edits only.
  It never holds the project's values, so it cannot disagree with `history.jsonl`. It is
  deleted when the edits are applied, reverted or discarded.
- **Retention follows `runs.py`'s discipline**: by age and size, never by count. A byte
  ceiling, a week's floor, oldest first, and over the ceiling with nothing old enough it warns
  and keeps. A file is deleted only after three guards, asked at the call: its name is a
  recovery name, it is a direct child of the recovery folder, and it carries the record tag.
- **The File menu.** A rename or a move made in the app moves the copy to the new key
  (`GuiSession._relocate`). Save a copy leaves it behind, as ruled. Resetting an example
  discards it, since the person asked to start that example over.
- **Client.** Each of the three panels exports `draft()` and `restoreDraft()`. The shell
  writes the combined draft half a second after the last change, writes it at once before
  an open, a new project or a close, and sends it with `keepalive` when the page is hidden.
  Opening a project clears the panels' pending maps (the carry-over defect above), then asks
  for the project's copy. A copy found is offered in a small modal dialog. Writing is held
  until the dialog is answered, so an unanswered offer is never overwritten.

### Tier

No rule here reads a pattern. The retention ceiling and floor are storage constants in
`gui/`, which `_audit.NOT_WALKED` declares out of the generality walk.

## Non-goals

- The Model panel's forms and the Text panel's buffer: they apply through their own buttons.
  A follow-up joins them to the same draft if the maintainer wants it.
- Finding a project's copy after the folder was moved outside the app. The copy stays under
  the old path, and retention removes it in time.
- A list of every kept copy (Blender's File › Recover). Each copy is offered by its project.
- Any change to the project format.

## Tasks

- [ ] Server: `gui/recovery.py`, the two routes, `_relocate` moves the copy, `example_reset`
  discards it, tests in `tests/test_gui_recovery.py`
- [ ] Client: `lib/recovery.ts`, `draft()`/`restoreDraft()` on the three panels, the shell's
  writer and offer, the carry-over across an open fixed, vitest
- [ ] Manual: the routes in a GUI chapter, the offer described; `tests/test_gui_manual.py`
- [ ] Browser: a test that closes with pending edits, reopens, restores and discards, by real
  clicks; every `tests/*_browser.py` run locally
- [ ] Dist rebuilt; `npm --prefix gui test` and `npm --prefix gui run check`
- [ ] Skill: none. The GUI is not a surface an agent driving rietx uses

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_recovery.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest tests/test_gui_recovery_browser.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The milestone's row 10: the maintainer looks at the offer on screen before the merge.

## References

- VS Code user guide, Basic editing § Hot Exit; VS Code wiki, Working Copies; "Hot Exit in
  Insiders", VS Code blog, 2016-11-30.
- JupyterLab user guide, Working with files § autosave; `jupyter_server` source,
  `services/contents/filecheckpoints.py`.
- WP-2133 § The maintainer's rulings of 2026-11-09, item 1.

## Handover log

- **2026-11-10** — created by the shift lead's assignment (number 2209 in the gui-overhaul
  block), from the milestone's "Edit recovery" row. No open WP owns the work: WP-2133 closed
  with the draft named as its follow-up.
