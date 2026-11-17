# WP-2213 — the Text buffer and the Model forms join the recovery copy

Milestone: gui-overhaul · Status: 🔄 2026-11-17 — built, PR #1633 waits on the maintainer's wording (questions 1-4 in the handover log)
Depends on: 2209 (the recovery copy); #1523 (its pull request)
Priority: P2 2026-11-13 — the milestone's edit-recovery row, widened by the maintainer's ruling of 2026-11-10; WP-2209's store, which it lands on, is on main since #1523 and WP-2209 is closed

## Goal

An edit typed into the Text panel's document, or into a Model panel form, survives a closed
project, a closed tab and a killed server, as the action bar's edits already do (WP-2209).
Reopening the project offers it in the same dialog, with Restore, Discard and Escape. The Text
buffer comes first and may land alone; the Model forms follow.

## Context

### The ruling

WP-2209 kept only the edits the action bar counts: the Parameters panel's maps, the
Interactive panel's sliders and an edited plan. Its open question 5 asked whether the Model
forms and the Text buffer should join. The maintainer ruled on 2026-11-10: they join, the Text
buffer first, filed as one WP.

### What WP-2209 built, which this WP extends

Read `docs/wp/2209-unapplied-edits-survive-a-close.md` § The design first.

- **Server.** `src/rietx/gui/recovery.py` keeps one JSON file per project under
  `<state dir>/recovery/`, keyed by the sha256 of the project's resolved path. The client's
  draft is an **open dict**: the frontend owns its keys, so a new arm needs no server change.
  The 1 MiB draft cap applies to the whole draft.
- **Client.** `gui/src/lib/recovery.ts` defines `Draft` with one arm per panel (`params`,
  `interactive`, `plan`) and `count`, the action bar's number, which the offer's sentence
  quotes. Each panel exports `draft()` and `restoreDraft()`. `App.svelte` combines them in one
  `$effect` and hands the result to `RecoveryWriter`, which writes half a second after the
  last change and at once before an open, a new project or a close.
- **The offer.** `gui/src/panels/Recovery.svelte`. Restore puts the arms back, Discard deletes
  the copy, and Escape sets the offer aside until the next open (ruled 2026-11-10). When the
  project's head has moved since the copy was made, the dialog adds "The project has been
  refined or edited since. Restored values will replace the current ones."

### The Text buffer

`gui/src/panels/Text.svelte` over `gui/src/lib/sync.ts`. The pane is a dirty buffer over one
server rendering of the project. `SyncState` carries `base` (the rendering), `revision` (its
compare-and-swap token for `PUT /api/textdoc`) and `buffer` (what the editor shows). The
buffer is pending exactly when `buffer !== base`. Apply sends the whole document as one delta.

Two rules from `gui/CLAUDE.md` § The `.rxt` document bear on a restore:

- **There is no merge.** When the head moves under a dirty buffer, the pane goes `stale` and
  offers one way out: re-read the rendering and re-apply. A restored buffer made against an
  older head is in that state from the start.
- **Comments do not survive a re-render.** A buffer with the person's own comments loses them
  on Apply. The recovery copy keeps the buffer as typed, comments included.

So the Text arm is `{ buffer, revision }`. Restore at the same revision puts the buffer back
as a dirty buffer. Restore at another revision puts it back `stale`, which keeps the text on
screen for the person to copy from, and the only action offered is the existing re-read.

### The Model forms

`gui/src/panels/Model.svelte` holds several pending pieces, each applied by its own button:

- the instrument form's delta (`insDelta`) and the structure form's (`strDelta`);
- typed parameter values and vary ticks (`pedits`, `varyEdits`, filtered to `varyPending`);
- typed positions (`posDelta`);
- a typed space-group symbol (`symbolDraft`) and the new-atom row (`draft`).

`dirty` (line 298 on 2026-11-10) already sums most of them, so it is the natural trigger for
the arm. Each piece's restore must go through the form's own state, never by patching the
model, because the forms diff against the live project.

### Practice

WP-2209's § Practice covers the field: VS Code keeps every dirty editor in its backup,
whatever kind of editor it is. Nothing new to survey.

## Non-goals

- Counting the Text buffer or the Model forms in the action bar. They keep their own Apply
  buttons. Only the recovery copy and the offer's wording change.
- A merge of a restored Text buffer into a newer rendering (the no-merge rule above).
- Any change to the server's store, the routes or the project format.

## Open questions for the session

1. The offer's sentence counts `N edits` from the action bar. With a Text arm or a Model arm,
   it needs words for them, such as "and the Text document". Bring the wording to the
   maintainer with a screenshot, as WP-2209 did.
2. Whether a restored Text buffer made against an older head should be offered at all, or only
   shown read-only. The default above restores it `stale`.

## Tasks

- [x] Text: a `text` arm in `Draft` and `readDraft`, `draft()`/`restoreDraft()` on
  `Text.svelte`, the shell's `$effect` reading it, the restore at the same and at a moved
  revision; vitest beside `lib/recovery.test.ts` and `App.test.ts`'s WP-2209 block
- [x] Text: a browser test in `tests/test_gui_recovery_browser.py`: type into the Text panel,
  close the tab, reopen, Restore, the buffer is back and dirty; by real keys and clicks
- [x] Model: a `model` arm over the pieces above, each restored through its form's state;
  vitest and one browser case
- [ ] The offer's wording for the new arms (open question 1), shown to the maintainer
- [x] Manual: `reference/gui-guide.md` § Edits not yet applied drops the sentence saying the
  Model forms and the Text document are not kept
- [x] Dist rebuilt; every `tests/*_browser.py` run locally, since CI has no playwright

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_recovery.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest tests/test_gui_recovery_browser.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2209 (the recovery copy), its § The design and § Practice.
- WP-1009 and WP-1013 (the `.rxt` document and the Text pane's sync rules).

## Handover log

### 2026-11-17 — the Text buffer and the Model forms join the recovery copy; PR #1633 waits on the maintainer

Typed edits in the Text document and in the Model panel's forms are now kept the way the action bar's edits are. They survive a closed project, a closed tab and a stopped server. Reopening the project offers them in the same dialog. The Text document comes back as typed, with the person's own comments, which an Apply would drop. A buffer typed before the project changed comes back marked stale, so it stays on screen to copy from, and the person re-reads and types the edit again. Building this found a sibling defect: opening another project carried both panes' typed edits into it. That is fixed. The offer's wording is a proposal for the maintainer (question 1 below).

*Done.*
- `lib/recovery.ts`: `Draft` gains a `text` arm (`{buffer, revision}`) and a `model` arm (the forms' typed maps `edits`, `params`, `positions`, `vary`, the new-atom row, and `count`, the number the panel shows). Neither arm is in the action bar's count. `combine` now takes the arms as one object. `readDraft` reads a copy written before this WP as having neither arm. `keptParts` puts what a copy holds into words for the dialog and the console line.
- `lib/sync.ts`: a `restored` event. At the revision the buffer was typed against, the buffer comes back dirty. At another revision it comes back stale and keeps its old revision, so a copy kept again is still stale when restored.
- `Text.svelte` exports `draft()`, `restoreDraft()` and `forget()`. While a restore is still fetching the rendering, `draft()` answers with the kept buffer, so the copy is not rewritten without it in the meantime.
- `Model.svelte` exports the same three functions. A restore sets the form's own maps and never patches the model. The arm is triggered by the typed maps, not by the panel's `dirty` count. Before the panel's first load, `dirty` reads 0, so triggering on it would delete the arm when a restore lands with the tab unopened. The atom row's state variable is renamed `atomRow`, since `draft` is now the exported function's name.
- `App.svelte` reads both arms, restores them, and calls `forget()` on both panes in `leaveEdits`. This fixes the carry-over defect, and a mutation test turns the new vitest red without the fix.
- `/next`'s Frame carries both arms as it already carried the Interactive and Plan ones, so a Parameters edit made there does not drop them.
- Manual: § Edits not yet applied says both are kept, says a Text document from before a change comes back stale, and says a typed space-group symbol is not kept.
- Screenshots of the offer, light and dark, are in `docs/wp/2213-screenshots/`. Each full window has the dialog boxed in red, with a crop beside it. Dist rebuilt.

*Review* (`/code-review high --fix`; eight findings, four fixed in their own commit). A Text restore now goes through the pane's one read path, `load()`. A failed read leaves the kept buffer waiting, where it used to drop it from the copy, and two reads in flight restore it once. `forget()` also clears the Model panel's loaded model, so a restored form is not measured against the project left behind. `readDraft` takes a Model arm only when its four maps are objects. Three findings are wording and go to the maintainer as questions 3 and 4 below. One is outside this WP: `forget()` leaves the selected phase index alone, which was already the case before this change. A three-phase project followed by a one-phase project can therefore point the Model tab at a phase that does not exist. Declined here as an existing gap that this WP does not widen.

*Settled by Claude.*
- A space-group symbol typed but not applied is not kept. The Model panel's `load()` drops it on every change to the project, so keeping it across a close would let it outlive what it survives in an open session. The alternative was to keep it as a seventh field. Grounds: the panel's own behaviour.
- The new-atom row is kept, and counts as one edit in the Model arm. The panel itself never counts it. Grounds: the WP lists it among the pending pieces, and practice (WP-2209 § Practice) keeps every dirty editor.

*Measured* (darwin/arm64, `[dev]` venv plus `playwright` 1.65 installed locally, node v24.22.1):
- vitest: 806 passed, 11 more than before (5 in `App.test.ts`, 3 in `sync.test.ts`, 2 in `recovery.test.ts`, 1 in `next/Window.test.ts`). svelte-check: 444 files, 0 errors.
- `test_gui_recovery`, `test_gui_manual`, `test_gui_dist` and `test_gui_recovery_browser`: 42 passed (the browser file went from 3 to 5).
- Every `tests/*_browser.py` file, run locally (CI has no playwright): gui and layout 40 passed; peaks, structure3d and recovery 15 passed; watch and compare 59 passed. These ran before the review fixes. The fast suite reran all of them on the final tree.
- Fast suite (`-m "not slow"`, through ghostshift's `serial.py`, browser files included, current main merged in at 44ae52fc7, load about 2): 14852 passed, 424 skipped, 32 xfailed, 13:31. The two added browser cases cost 7.6 s and 5.7 s on this run (`tests.added_test_times`). Both are in a file that already sits in the fast tier.
- `python -m tests.reader_output` exit 0. ruff clean. Vale at warning level: no alert on a line this branch wrote.
- A mutation that removes the two `forget()` calls turns the carry-over vitest red.

*Not covered.* No vitest drives a Parameters edit on `/next` with a kept Text or Model arm present. A mutation that stops `/next` carrying the arms stays green, because `/next`'s Window test has no parameter rows to edit. That test asserts the half it can reach: the offer is not shown and the copy is left alone. In the rebuild the carrying code is shared with the Interactive and Plan arms, which have no such test either.

*Scope against the rebuild.* WP-2214 and the gui-overhaul milestone say this WP shrinks in the rebuild. There a Text edit becomes a pending edit (R4), and the Model forms become dialogs that commit at once, so a Model arm has nothing to keep. This WP builds the arms for today's page, which is what `rietx gui` serves until the swap. The `text` arm in `lib/recovery.ts` and the `restored` event in `lib/sync.ts` sit in the logic layer the rebuild keeps. R4 can reuse them. The Model arm goes with today's Model panel at the swap.

*Open for the maintainer.*
1. The offer's wording (the WP's question 1). Proposed: the action bar's count first, then "N edit(s) in the Model forms", then "an edited Text document", joined with commas and "and". An example is "1 edit, 1 edit in the Model forms and an edited Text document from Nov 17, 2026, 12:44 AM, not applied when the project closed." See `docs/wp/2213-screenshots/offer-light.png` and the crops. The line for a moved head still reads "Restored values will replace the current ones." That is not quite true of a stale Text document, which replaces nothing until re-applied.
2. Whether a Text buffer typed before the project changed should be offered at all (the WP's question 2). Built as the WP's default: it is restored stale.
3. On `/next`, the offer names everything in the copy, the Text document and the Model forms included. Restore there brings back only the Parameters edits and carries the rest unseen. Should `/next`'s sentence name only what it restores?
4. The console line after Restore mixes nouns: "# 1 unapplied edit and 2 edits in the Model forms restored". It goes with question 1's wording.

Next: the maintainer's answers to 1-4, then the merge.

- **2026-11-13** — re-rated by the close-only bookkeeping batch of 2026-11-13 (PR #1563),
  which closed WP-2209. Its recovery copy merged in PR #1523 on 2026-11-11, so nothing this WP
  builds on is waiting any more. The tier stays P2. Next: as below.

- **2026-11-10** — filed by WP-2209's runner, on the maintainer's ruling of 2026-11-10
  (WP-2209's question 5). No open WP owns the work: WP-2209 left both pieces out of scope and
  WP-2133 is closed. Number 2213 is the next free one in the gui-overhaul block, claimed for
  PR #1523.
