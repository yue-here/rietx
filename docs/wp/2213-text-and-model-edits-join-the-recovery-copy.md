# WP-2213 — the Text buffer and the Model forms join the recovery copy

Milestone: gui-overhaul · Status: ⬜
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

- [ ] Text: a `text` arm in `Draft` and `readDraft`, `draft()`/`restoreDraft()` on
  `Text.svelte`, the shell's `$effect` reading it, the restore at the same and at a moved
  revision; vitest beside `lib/recovery.test.ts` and `App.test.ts`'s WP-2209 block
- [ ] Text: a browser test in `tests/test_gui_recovery_browser.py`: type into the Text panel,
  close the tab, reopen, Restore, the buffer is back and dirty; by real keys and clicks
- [ ] Model: a `model` arm over the pieces above, each restored through its form's state;
  vitest and one browser case
- [ ] The offer's wording for the new arms (open question 1), shown to the maintainer
- [ ] Manual: `reference/gui-guide.md` § Edits not yet applied drops the sentence saying the
  Model forms and the Text document are not kept
- [ ] Dist rebuilt; every `tests/*_browser.py` run locally, since CI has no playwright

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

- **2026-11-13** — re-rated by the close-only bookkeeping batch of 2026-11-13 (PR #1563),
  which closed WP-2209. Its recovery copy merged in PR #1523 on 2026-11-11, so nothing this WP
  builds on is waiting any more. The tier stays P2. Next: as below.

- **2026-11-10** — filed by WP-2209's runner, on the maintainer's ruling of 2026-11-10
  (WP-2209's question 5). No open WP owns the work: WP-2209 left both pieces out of scope and
  WP-2133 is closed. Number 2213 is the next free one in the gui-overhaul block, claimed for
  PR #1523.
