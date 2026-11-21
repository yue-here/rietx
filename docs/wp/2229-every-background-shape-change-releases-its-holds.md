# WP-2229 — Every change to the background's shape releases its holds, and no pending edit outlives its path

Milestone: gui-overhaul · Status: 🔄 2026-11-21 — claimed by @yue-here (ghostshift runner)
Depends on: 2218 (the Background graph's fix this generalises)
Priority: P3 2026-11-19 — a held term can come back held on a background that never had it, and nothing says so; `unhold` by hand is the workaround, and two of the three surfaces leave with today's page at the swap

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
- [ ] Tests: `tests/test_gui_background.py` for the server arms; vitest for `dropPending` and
      for each client surface; a browser case by real clicks for any surface still mounted.
- [ ] Skill: none. The skill drives the python API, which keeps holds by path on purpose.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_background.py -p no:randomly
npm --prefix gui test && npm --prefix gui run check
```

## Handover log

- **2026-11-19** — filed by the ghostshift runner on WP-2223's branch, from WP-2218's
  review-fix bullet. No open WP owns the hold registers or the Parameters panel's pending
  edits: WP-2218 waits only on Yue's look and is not the place for a follow-on, and 2211 and
  2212 are the History table and the console. The `.rxt` claim was checked against
  `textdoc.Delta` at 0ac05af06 and looks wrong, so task 1 confirms it before anyone builds on it.
