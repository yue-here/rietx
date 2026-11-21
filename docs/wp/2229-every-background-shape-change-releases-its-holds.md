# WP-2229 — Every change to the background's shape releases its holds, and no pending edit outlives its path

Milestone: gui-overhaul · Status: ✅ 2026-11-21 — every instrument edit releases and frees on the server, and no pending edit outlives its path (PR #1741)
Depends on: 2218 (the Background graph's fix this generalises)

## Goal

Whatever changes the background's type or its number of terms releases the holds on the
paths that change removes or redefines, and frees the terms it adds, as the Background graph
at `/next` does since WP-2218's review. The Parameters panel drops every kind of pending edit
on a path that no longer exists, positions and restraints included.

## Context

**What WP-2218's review fixed, and where.** The hold and free registers are declarations
about a *path*, and `Refinement.edit` keeps them across a model edit. The package does this on
purpose, so a checkout restores them. A held Chebyshev `c3` therefore held the P-spline's `c3`
after a Type switch, and a cut term's hold came back when a later extension rebuilt that path.
The fix is in three places:

- `src/rietx/gui/session.py:GuiSession.instrument_patch` takes two arms, `unhold` (released
  before the edit) and `free` (freed after it), all or nothing through `rehearse`.
- `gui/src/next/background.ts` builds the arms: `kindArms` for a Type switch, `termsArms` for
  a Terms change.
- `gui/src/next/Params.svelte` `dropPending` drops pending values, vary flags, holds and limits
  on the paths such an edit removed or redefined.

WP-2218's handover (2026-11-19, the review-fix bullet) recorded three cases it left alone.

1. **Other surfaces change the background without the arms.**
   - Today's page, the Model tab's Terms (`gui/src/panels/Model.svelte` `setBackgroundTerms`):
     it sends the whole instrument through `api.patchInstrument` with no `unhold` or `free`, and
     the coefficients it adds are built as `{ value: 0 }`, so fixed.
   - Today's page, the Model tab's instrument form (`Model.svelte`, the `applyFields` call into
     `api.patchInstrument`): check whether any of its fields reaches the background's kind.
   - The `.rxt` document. The handover named it, but at 0ac05af06 its `Delta`
     (`src/rietx/gui/textdoc.py`) carries values, vary flags, settings, the plan and peak edits,
     and no model edit. A typed value or flag cannot change the background's shape there. The
     first task confirms this against the parser and drops the item if it holds.
   - The old Background tab (`gui/src/panels/Background.svelte`) sends only the P-spline's λ,
     which changes no path. Confirm it is clean.
2. **A hold recorded before the fix, on a path a cut already removed.** `termsArms` releases
   holds only on the terms the panel has rows for. A hold on `c7` left by a cut made before
   WP-2218's fix has no row, so extending the background to eight terms brings `c7` back held.
   The client cannot see that hold. Either `GET /api/background` (or the parameter rows) names
   the register's background holds, or the server's arm releases every background hold past the
   new count.
3. **Pending positions and restraints are not pruned.** `dropPending` keeps `positionEdits`
   (keyed by atom) and `restraintEdits` (keyed by path). A restraint pending on a background
   coefficient survives a cut of that coefficient, and Apply then refuses it or lands it on the
   new model's path of the same name.

**The swap.** Today's page is retired when `/next` reaches parity (WP-2214's plan). Fixing
case 1 on today's page is worth doing only if the swap is far off; the first task records
which.

**Case 1 checked against the tree, 2026-11-21 (at 8e100829b).** Three findings change the
list above.

- The `.rxt` document cannot change the background's shape. `textdoc.apply` runs
  `set_values`, `set_vary`, the plan, three settings and the peak editor, and no model edit.
  It is dropped.
- The old Background tab is clean. `lib/background.ts:withLambda` sets `lambda_smooth` alone,
  which changes no path. Dropped.
- Today's instrument form (`applyFields` in `Model.svelte`) reaches no background field:
  `lib/model.ts:instrumentFields` builds none. It is dropped as a background surface. Two
  surfaces the list missed do change the shape: **Replace from file** on both pages
  (`Model.svelte:replaceFrom`, `next/Instrument.svelte:loadProfile`) sends a whole instrument,
  whose background may be of another kind or length. The rebuilt dialog's anode choice also
  changes the number of emission lines, so a hold on `instrument.source.lines.1.weight` has
  the same defect in another family.
- So the arms move to the server: `GuiSession.instrument_patch` derives them from the two
  tables, for every client and every positional family in the instrument. Today's page
  then needs only its added terms built free. The swap is three pieces off (R5 to R7 after
  R4), so that one-line fix is worth making.

**The tier of each rule this WP adds.** None. A release or a free follows from the edit the
person asked for, and the edit's console line says so.

## Non-goals

- Changing `Refinement.edit`'s keeping of holds by path. The package keeps them for a
  checkout, and a script that edits the model owns its own registers.
- The python API's `Refinement.edit` callers outside the GUI.

## Tasks

- [x] Confirm each surface in case 1 against the tree; drop the ones that cannot change the
      background's shape, and say whether the swap makes today's page's fix moot.
- [x] Case 1: every surface left sends `unhold` and `free` built by `next/background.ts`, or
      the arms move to the server so no client can omit them.
- [x] Case 2: a hold on a background path the model lacks is released when an extension
      rebuilds that path.
- [x] Case 3: `dropPending` drops pending positions and restraints on a gone path.
- [x] Tests: `tests/test_gui_background.py` for the server arms; vitest for `dropPending` and
      for each client surface; a browser case by real clicks for any surface still mounted.
- [x] Skill: none. The skill drives the python API, which keeps holds by path on purpose.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_background.py -p no:randomly
npm --prefix gui test && npm --prefix gui run check
```

## Handover log

- **2026-11-21** — closed, PR #1741 (two ghostshift runners, one after the other). A hold or a
  free flag in the GUI is a note about a parameter's *name*, and the package keeps it when the
  model changes. Before this WP, only the Background graph at `/next` cleaned those notes up
  when a background changed type or length. Now the server does it for every instrument edit,
  whichever screen sent it. A held Chebyshev term no longer holds the P-spline term of the same
  name, a hold left on a term an old cut removed no longer comes back, and an added term is free
  as the screen built it. The same rule covers emission lines, which the new dialog's anode
  choice and Replace from file can add or remove. The Parameters panel drops every kind of
  pending edit on a path the edit ended, so Apply is not refused on a path that is gone.
  - *Done.* Case 1 checked against the tree (see Context): the `.rxt` document and the old
    Background tab cannot change the background's shape, and Replace from file on both pages
    can. `GuiSession.instrument_patch` compares the old and new parameter tables
    (`_register_arms`) and works out four lists: `release` (holds on paths the edit removes,
    redefines or builds, read off the hold register, so case 2's hold with no row is found),
    `free` (built paths the new model says vary), `fix` (built paths the new model says fixed
    and the free register still names) and `ended`. A background coefficient is *redefined*
    when the kind or the P-spline's breakpoints change. The verbs run on a history-free copy
    first (`rehearse`), so a refusal leaves everything as it was. The request's `unhold` and
    `free` fields are gone; the answer gains `released`, `freed`, `fixed` and `ended`. Every
    client echoes the registers' part (`lib/model.ts:registerEcho`) and passes `ended` to the
    Parameters panel's `dropPending`, which now drops restraints and positions too (case 3).
    Today's Model-tab Terms box builds an added term free. `next/background.ts` lost
    `kindArms`/`termsArms`.
  - *Review.* `/code-review high --fix` made three fixes (b1e50ed14): a re-knotted P-spline
    counts as redefined; the `fix` arm; `_user_holds` read without a snapshot. Two more findings
    fixed by the second runner (138cb7c6e): **4**, the Instrument dialog sent its typed values
    after a model edit that could have ended their paths, so the request could land half; it
    now drops them and says so. No dialog field ends a path today (probed on `fap` and `nac`:
    geometry kind and peak shape end none), so this is a guard. **9**, the ended test was
    written twice; `lib/model.ts:endedBy` is now the one reading.
  - *Left open.* **5**: when the current or the new model builds no parameter table,
    `_register_arms` returns `None` and the edit runs with no register work. Whether a broken
    model's holds should be released is a design call; it would go in `_register_arms`
    (`src/rietx/gui/session.py`) under a new WP. **6**: an `extra_components` or
    `peak_equations` entry that changes kind at the same index keeps its paths and is not
    treated as redefined; the rule would extend `_register_arms`' `redefined` set, under a new
    WP if the GUI grows a surface that swaps one. **7**: today's page ignores `ended`, since it
    has no pending-edit store of the Parameters panel's kind; it retires at the swap (WP-2214,
    pieces R5 to R7), so nothing is planned. **8**: `freed` and `fixed` echo the lists offered
    to `set_vary`, not its return; folded into WP-2212's `### Inherited`, since the console's
    script export is what would trust the line.
  - *Not generalised.* Structure edits: the package carries holds through an atom renumbering
    by label (#1264), which a comparison by path would undo. Today's page's Params pending
    edits. A stale entry left in the free register by a cut before this WP still warns
    "restored parameter path(s) no longer exist" on a checkout.
  - *Measured* (venv `[dev]` + playwright, darwin/arm64, on main e1f6d1ac4 merged in):
    vitest 867 passed (47 files), svelte-check 0 errors in 461 files; `tests/*_browser.py` and
    the fast suite below. `tests/test_gui_background.py` gained 8 tests and lost 1 (a rename);
    `tests/test_gui_layout_browser.py` gained 1, which skips in CI (no playwright there).
    `tests.reader_output` exit 0, unchanged. ruff clean; vale 0 errors.
  - *Generality.* Not dispatched: `_audit.py` untouched, and the release and free follow from
    the edit the person asked for, which the console line names (Context, tier).
  - Next: none in this WP. The open findings above have their places.

- **2026-11-19** — filed by the ghostshift runner on WP-2223's branch, from WP-2218's
  review-fix bullet. No open WP owns the hold registers or the Parameters panel's pending
  edits: WP-2218 waits only on Yue's look and is not the place for a follow-on, and 2211 and
  2212 are the History table and the console. The `.rxt` claim was checked against
  `textdoc.Delta` at 0ac05af06 and looks wrong, so task 1 confirms it before anyone builds on it.
