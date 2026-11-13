# WP-2209 — unapplied edits survive a close or a crash

Milestone: gui-overhaul · Status: ✅ 2026-11-13 — merged in PR #1523 on 2026-11-11; unapplied edits are kept in a recovery copy and offered on reopen
Depends on: 2133

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
  `PUT /api/recovery` writes `{project, head, draft}` or deletes on `draft: null`. The write
  names its project rather than meaning the open one, and `project` must be a project
  folder. New project and Close are answered before the shell hears of them, so the shell's
  last write for the project it leaves lands after the switch; keyed to "whatever is open",
  it would put one project's edits under the next one's name. Neither route is behind the
  run's 409: like `/api/settings`, nothing here can disagree with a run, and edits made
  during a run must still be kept.
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

### Ruled by Yue 2026-11-10

The maintainer's answers to the five open questions of the first handover entry.

1. **The offer stays a modal dialog on open**, as built. Ruled by Yue 2026-11-10.
2. **Escape closes the dialog and keeps the recovery copy.** Nothing is restored and nothing
   is discarded, and the offer returns on the next open of the project. Ruled by Yue
   2026-11-10. It replaces the first cut, where Escape did nothing.
3. **The title and the first line stay.** The line shown when the project's head has moved
   becomes "The project has been refined or edited since. Restored values will replace the
   current ones." Ruled by Yue 2026-11-10.
4. **Restore stays the default and takes focus**, as built. Ruled by Yue 2026-11-10.
5. **The Text panel's buffer and the Model panel's forms join the recovery copy**, the Text
   buffer first, in one follow-up WP: WP-2213. Ruled by Yue 2026-11-10.

### Tier

No rule here reads a pattern. The retention ceiling and floor are storage constants in
`gui/`, which `_audit.NOT_WALKED` declares out of the generality walk.

## Non-goals

- The Model panel's forms and the Text panel's buffer: they apply through their own buttons.
  WP-2213 joins them to the same draft (ruled 2026-11-10).
- Finding a project's copy after the folder was moved outside the app. The copy stays under
  the old path, and retention removes it in time.
- A list of every kept copy (Blender's File › Recover). Each copy is offered by its project.
- Any change to the project format.

## Tasks

- [x] Server: `gui/recovery.py`, the two routes, `_relocate` moves the copy, `example_reset`
  discards it, tests in `tests/test_gui_recovery.py`
- [x] Client: `lib/recovery.ts`, `draft()`/`restoreDraft()` on the three panels, the shell's
  writer and offer, the carry-over across an open fixed, vitest
- [x] Manual: the routes in a GUI chapter, the offer described; `tests/test_gui_manual.py`
- [x] Browser: a test that closes with pending edits, reopens, restores and discards, by real
  clicks; every `tests/*_browser.py` run locally
- [x] Dist rebuilt; `npm --prefix gui test` and `npm --prefix gui run check`
- [x] Skill: none. The GUI is not a surface an agent driving rietx uses
- [x] The rulings of 2026-11-10: Escape sets the offer aside (vitest and a real-key browser
  test), the head-moved line reworded in the dialog and the manual, WP-2213 filed

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

- **2026-11-13** — closed by the close-only bookkeeping batch of 2026-11-13 (PR #PRNUM), a
  repair. PR #1523 merged on 2026-11-11 with every task ticked, and two `WP-2209:` commits of
  that day never reached this log. The GUI now keeps edits a person has made but not applied
  in a recovery copy outside the project, and offers them again when the project reopens after
  a close or a crash. That is shipped on `main` and goes out with v1.12.

  *Changed by this repair.* Status ✅, the `Priority:` line removed, the narrative moved to
  `docs/milestones/v1.12.md`. The `### Inherited` note from WP-2143 is removed as consumed: it
  recorded a fix WP-2143 made itself, that `recovery.move` keys the old copy by the path its
  caller gives (PR #1539), pinned by
  `test_a_move_keys_the_old_copy_by_the_path_it_was_given`. It asked nothing of this WP.

  Next: none in this WP. WP-2213 joins the Text panel's buffer and the Model panel's forms to
  the same recovery copy.

- **2026-11-11** — (reconstructed post hoc) from the commits. `249465671` committed the entry
  headed "2026-11-10 — the maintainer's five rulings applied" just after midnight, so its
  commit carries this date. `5606c61b4` merged `main` and rebuilt the GUI dist after #1528 and
  #1530. PR #1523 merged at 02:16 UTC. The commits do not say whether the suite was rerun on the
  merged tree; CI on #1523 was the gate.

### 2026-11-10 — the maintainer's five rulings applied; PR #1523 waits on the merge

The maintainer answered the five open questions on 2026-11-10 (§ Ruled by Yue 2026-11-10).
Two changed the dialog. Escape now closes it and keeps the copy: nothing is restored or
discarded, and the next open of the project offers the copy again. The line shown when the
project's head has moved now reads "The project has been refined or edited since. Restored
values will replace the current ones." The manual's § Edits not yet applied says both. The
follow-up for the Text buffer and the Model forms is filed as WP-2213, in this PR. Origin/main
was merged in, with no conflict.

*Done.* `panels/Recovery.svelte` calls a new `onlater` on Escape, and `App.svelte`'s
`setAsideKept` clears the offer and prints one console line. A vitest in `App.test.ts`'s
WP-2209 block presses Escape, makes an edit, and reopens the project from the start screen.
`tests/test_gui_recovery_browser.py` gains the same story by real keys and clicks: Escape,
Close project from the File menu, the recent row, offered again. The reworded line is
asserted in the vitest that covers a moved head. No screenshot shows the dialog, so none was
regenerated. Dist rebuilt.

*A consequence of ruling 2, settled by Claude.* After Escape the writer stays disarmed until
the project is next opened. So an edit made after Escape is not kept, and a crash before the
next open loses it. Arming the writer instead would let that edit overwrite the copy the
person set aside, which ruling 2 keeps. The manual says that such edits are not kept. A
mutation that arms the writer on Escape turns the new vitest red.

*Measured* (darwin/arm64, `[dev]` venv plus `playwright` 1.65 installed locally, node
v24.22.1). vitest 733 passed (732 before, +1). svelte-check 419 files, 0 errors. ruff clean.
`tests/test_gui_recovery.py`, `test_gui_manual.py` and `test_gui_dist.py` 35 passed.
`tests/test_gui_recovery_browser.py` 3 passed, run alone. Fast suite (`-m "not slow"`,
through ghostshift's `serial.py`, browser files included, load 8 to 25): 14631 passed, 410
skipped, 32 xfailed, 1 failed, 14:35. The failure is
`test_manual.py::test_every_page_has_a_twin_that_keeps_the_contract`: the twin of
`theory/estimation` builds to 50 048 characters against a 50 000 cap. It fails the same way
on a snapshot of origin/main (68fd06973), so it is not this branch's. `python -m
tests.reader_output` exit 0. Vale at warning level: no alert on a line this branch wrote.

Next: the merge.

### 2026-11-10 — the recovery copy built and offered; PR #1523, waiting on the maintainer's look

An edit in the action bar's count now survives a closed project, a closed tab and a killed
server. The GUI writes the pending edits to a small file in rietx's state directory half a
second after each change, and at once before an open, a new project or a close. Reopening
the project shows a dialog, "Unapplied edits", with Restore and Discard. The copy holds only
proposed edits and is deleted once they are applied, reverted or discarded, so it never
competes with the history for a parameter's value. Building it found a defect: opening
another project kept the Parameters and Interactive panels' pending values, so the next
Apply sent one project's typed values to another. Opening now clears them, after keeping
them as the old project's copy. The merge waits on the maintainer's look (milestone row 10)
and on the five open questions below.

*Done.* `src/rietx/gui/recovery.py` (the store: atomic write, sha256 key of the resolved
path, record tag, age-and-size prune behind three guards); `GuiSession.recovery` and
`recovery_put`; `GET`/`PUT /api/recovery`; `_relocate` re-keys the copy and `example_reset`
discards it. Client: `gui/src/lib/recovery.ts` (the draft's shape and `RecoveryWriter`, which
debounces, drops writes while disarmed and sends the unsent one with `keepalive` on
`pagehide`), `draft()`/`restoreDraft()` on Params, Interactive and Plan,
`gui/src/panels/Recovery.svelte` (the dialog), the shell's wiring in `App.svelte`. Manual:
`reference/gui-guide.md` § Edits not yet applied, and the two routes in `gui-power.md`.

*A design change made while building.* The first cut refused a write whose `project` was not
the open one. That lost edits: New project and Close are answered before the shell hears of
them, so the shell's last write for the project it leaves arrives after the switch. The write
now names its project and needs only a project folder there (`project.json`).

*Measured* (darwin/arm64, `[dev]` venv plus `playwright` 1.65 installed locally for the
browser rows, node v24.22.1). `tests/test_gui_recovery.py` 10 passed.
`tests/test_gui_recovery_browser.py` 2 passed, by real clicks and keys: a value typed, the
server restarted over the same state directory, Restore, then Revert deleting the copy; a
value typed and the tab closed inside the half-second, Discard. With the `pagehide` handler
blanked the closed-tab test fails, and with the panel clear or the flush removed from
`leaveEdits` two vitest cases fail, so each guard can go red. vitest 732 passed (717 before
this branch, +10 in `lib/recovery.test.ts`, +5 in `App.test.ts`; eight existing
`App.test.ts` lookups of "the PUT" now name their route, and `lib/style.test.ts` admits the
dialog's one primary). svelte-check 0 errors. `python -m tests.reader_output` exit 0.
Every `tests/*_browser.py`, one file at a time: gui 4, layout 28, peaks 2, recovery 2, compare 6, html 12, rxplot 41, structure3d 6, watch 53, all passed (154). Fast suite (`-m "not slow"`, through ghostshift's `serial.py`, after the review fixes): 14631 passed, 410 skipped, 32 xfailed, 10:44 on a machine shared with other runners. This branch adds 12 tests, all passing locally (the two browser ones skip in CI, which has no playwright). No local baseline on main was run, so the +12 is the added count and not a measured delta. `tests.added_test_times`: 12.14 s over the 12, the slowest 5.52 s (the browser restart test); per file 7.32 s `test_gui_recovery_browser.py`, 4.82 s `test_gui_recovery.py`. Neither joins the slow tail.

*Gotcha: a module-scoped GUI fixture now carries pending edits between tests.*
`tests/test_gui_layout_browser.py` serves one session to many tests. A test leaving an edit
pending left a copy, and every later page opened under the offer's modal: at least 10 of
its first 19 cases failed. Its pages now answer `/api/recovery` themselves
(`_keep_no_edits`), because clearing the copy before each page races the closing page's own
last write. A new browser module sharing one session and leaving edits pending needs the
same.

*Review* (`/code-review high --fix`): nine findings, five fixed in one commit. A temporary
name per thread, so two writes for one project cannot share one file. The writer flushes
before an example reset, which a late write would otherwise undo. Tab stays inside the
dialog. The page-hide send counts as sent, so it is not sent twice. A failed Discard is
retried. Four declined: a write in flight during a rename can land under the old key
(closing it needs a File-menu flush before the rename, outside this diff); the PUT checks
only that `project` is a project folder, not that it is open or recent (the path is only
hashed into a file name, never written to); an edit typed while the offer's GET is pending
is kept only from the next change; a malformed copy is not offered and is left to
retention.

*Generality*: no judge dispatched. The branch leaves `_audit.py` alone, and its constants
(the retention ceiling and floor, the 1 MiB draft cap, the half-second debounce) live in
`gui/recovery.py` and the frontend, which the walk leaves out (`_audit.WALKED` takes only
`gui/imports.py` and `gui/symmetry.py`). None reads a pattern.

*Settled by Claude, for review.*
1. Scope is the action bar's three kinds of pending edit (Parameters, Interactive, Plan). The
   Model forms and the Text buffer apply through their own buttons, so they do not share the
   mechanism; the brief said to include them only if they did.
2. The write names its project rather than meaning the open one (above). Alternative: a
   pre-switch hook in every panel that opens or closes a project, which is more code at more
   call sites.
3. A rename or move made in the app re-keys the copy; Save a copy leaves it behind (ruled);
   resetting an example discards it, since the reset asks to start the example over.
4. Retention: 16 MiB ceiling, a week's floor by file time, oldest first, warn and keep, on
   `runs.py`'s rule. A copy is a few kilobytes, so the ceiling bounds a defect and deletes
   nothing in normal use. A copy left by a folder moved outside the app or by `--scratch` stays
   until then.
5. The offer restores even when the project's head has moved since, and says "The project
   has changed since." VS Code also restores over a file changed on disk and leaves the
   conflict to the save.
6. Writes are not behind the run's 409, like `/api/settings`.
7. Half a second of debounce, plus `keepalive` on `pagehide`. VS Code backs up on every
   content change; half a second keeps a typing burst to one write.

*Open questions for the maintainer* (visual, so not settled; the plainest choice was taken).
1. The offer is a modal dialog on open, drawn as the File menu's dialogs are. The modal also
   stops an edit being made before the answer, which would overwrite the kept copy.
   Alternatives: a line in the action bar, or VS Code's way, restoring without asking.
2. Escape does nothing while the dialog is up. Restore and Discard are the only ways out,
   because Escape as Discard loses work and Escape as Restore surprises.
3. The words: title "Unapplied edits"; "N edits from 10 Nov 2026, 09:05, not applied when the
   project closed."; "The project has changed since." when the head moved.
4. Restore is the filled primary and takes focus, so Enter restores.
5. Whether the Model forms and the Text buffer should join the copy (a follow-up).

Next: the maintainer looks at the dialog on screen and answers the five questions; then merge.

- **2026-11-10** — created by the shift lead's assignment (number 2209 in the gui-overhaul
  block), from the milestone's "Edit recovery" row. No open WP owns the work: WP-2133 closed
  with the draft named as its follow-up.
