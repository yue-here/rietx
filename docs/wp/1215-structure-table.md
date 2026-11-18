# WP-1215 — Model: the structure table

Milestone: v1.2 · Status: ✅ 2026-08-28 — one row per atom, the coordinate typed and the site answering, and the letter a column
Depends on: WP-1214

## Goal

One row per atom: label, species, Wyckoff site, editable x y z, occupancy,
Biso, aniso, vary, remove. No sub-rows, no "moves along", no separator line
sitting on the inputs.

## Context

The user: "It needs to be tidier, with one row for each atom. Editable atom
positions. 'Moves along' is not a natural UI, and clutters the interface.
Wyckoff sites don't have headings etc. Revisit fetching them automatically.
The thin line just above each atom row is too close to the editable fields."

Findings (2026-08-25, refreshed 2026-08-28 after WP-1214 —
`Model.svelte:1367-1475`):

- An atom is one to three `<tr>`s: the main row (label, species, a read-only
  `xyz` cell at 4 places, occ, Biso, aniso checkbox, `×`), then either a
  `frozen` sub-row (`fully fixed special position…`, `lib/model.ts:431-433`)
  or the DOF sub-row (`moves along` + one `[pattern]` box per DOF,
  `:1433-1453`), then an ADP sub-row (`:1455-1470`).
- The separator is `tr.sub td { border-bottom: 1px solid var(--line) }`
  (`:2052-2055`): it is the last sub-row's bottom edge, so it sits directly
  above the next atom's inputs.
- Coordinates are affine ties onto `phases.i.atoms.j.dof.k`
  (`crystallography/wyckoff.py`), so x/y/z are never typed; the editor
  offers the DOFs so "a site-symmetry violation is unrepresentable rather
  than refused" (WP-1014). `GET /api/structure`'s `sites` arm
  (`gui/symmetry.py:213-228`) carries `dof_paths`, `dof_directions`,
  `adp_paths`, `adp_patterns`, `site_symmetry_order`, `special`; the values
  come from the structure arm's `Atom.x/y/z` and the params rows.
- **A DOF is a displacement, re-anchored on every table build** (measured
  2026-08-28 on the LaB₆ fixture): `x = x₀ + Σₖ Bₖ·θₖ` anchors `const` at the
  stored `Parameter.value`, `set_values` writes x back through
  `refresh_ties` → `apply_to_models`, and the next `_working_table()` reads
  the new x₀ with every `dof.k` at 0.0 again. So a typed coordinate is a
  **delta** to solve for, never an absolute; and an axis the site holds is
  `locked`, not `tie`d (B at `6f` has `y`/`z` locked, `x` tied to `dof.0`).
- A vary request on a site frees **all** of its DOFs — "per-axis intent does
  not map onto rows such as [1,1,0]" (`params/vector.py:_collect_atom_coords`)
  — so the position carries **one** flag, not three.
- Wyckoff letters are behind a button (`Model.svelte:1259-1265` →
  `GET /api/structure/symmetry?phase=N`, `wyckoffLabel` in
  `lib/symmetry.ts:134-140`) and dropped on every head move (`:502-503`).
  The cost that argued for the button was 1.8-8.7 ms per atom **on a route
  that refetches on every head move** (WP-1035); it did not argue against
  fetching.
- The table's measured floor is 448 px + 24 (WP-1034, `MODEL_MIN.structure`
  = 472 in `lib/resize.ts`), reflowed by `lib/resize.ts:modelStacks`.

Design:

- Columns: `label · species · site · x · y · z · occ · Biso · aniso · vary ·
  ×`. `site` is the Wyckoff letter and site symmetry, fetched automatically
  and **cached by a content hash** of (space group, positions), so a head
  move that leaves the structure unchanged costs nothing.
- x y z editable. A typed coordinate goes to `POST /api/structure/position
  {atom, xyz}`: the server projects onto the site's DOF basis and, when the
  residual exceeds a tolerance (1e-6 in fractional units), **refuses** naming
  the free direction(s) and the nearest allowed position, because silently
  rewriting a number the user typed is the objection that made
  `check_cell_angles` refuse rather than normalise. On a general position the
  projection is the identity and any value is accepted; it lands as three DOF
  values through `set_values`, one `set_value` node, like every other typed
  number here. A fully fixed position renders read-only.
- The **`vary` column is the position's flag** — the one WP-1214 could not
  draw beside a value, because the value it is about is three cells wide and
  the DOFs it sets are freed together. `occ` and `Biso` keep their own
  in-cell flags.
- ADPs in a per-atom disclosure on the `aniso` cell; the sub-rows go, and
  with them the separator.

Carried in from **WP-1214** (2026-08-28, shipped; `### Inherited` consumed
2026-08-28):

- **Every value in this panel carries a refine flag beside it**, drawn by one
  `{#snippet varyBox(path)}` in `Model.svelte` (`:836-851`) and addressed by
  `data-vary="<parameter path>"`. The flag belongs *after* its value in the
  DOM — inside a `<label>`, the first labelable descendant is what the label
  names, so a flag placed first steals the value's label. The aniso checkbox
  is addressed by `data-aniso` for the same reason: "the first checkbox in
  the table" stopped being an address.
- A **held** value gets a mark rather than a box, and there are **four**
  reasons (`heldGlyph` in `lib/table.ts:112-119`). A locked coordinate wears
  `🔒`; the position's `vary` cell on a fully fixed site has no row at all,
  so the frozen sentence is what the cell carries.
- The phase's scale and its four sample-broadening terms are a `Phase` grid
  between the cell row and the atom table (`lib/model.ts:phaseFields`). It is
  the structure column's third block; the corrections (extinction, preferred
  orientation, Stephens) are still nowhere, deliberately.

Carried in from **WP-1201** (2026-08-25, shipped):

- The phase selector `nav.phases` is the `.segmented` register. Keep it
  segmented if this WP reworks the structure column.
- The atom table is `var(--text-sm)`, its `th` and the sub-labels are
  `var(--text-xs)`, and the per-row remove button is a plain `button.ghost`
  at the one button size (~22 px, chosen so the register fits a table row). A
  literal `font-size`, `padding` or `border-radius` on a register in this
  panel fails `gui/src/lib/style.test.ts`.
- A field is control-sized with **no exception** — a field that needs to feel
  prominent gets width and padding, never a step of its own. Two panels had
  put the size back with `font: inherit` on `input`; that is the shape to
  avoid.

## Non-goals

- Adding or removing atoms differently (the existing whole-model edit).
- The 3D viewer.

## Tasks

- [x] `POST /api/structure/position` (projection, refusal wording, tests on
      NAC's special positions and a general position). *The fixture is LaB₆,
      not NAC — it already carries both special positions this needs (`1a`
      fully fixed, `6f` one-DOF) and a two-DOF site is one appended atom, so
      importing a second structure would have bought nothing.*
- [x] Automatic Wyckoff with the content-hash cache (server-side cache keyed
      on the hash; `tests/test_gui_server.py` counts the spglib calls across
      two head moves without a structure change). *Keyed on the content tuple
      itself rather than a digest of it — a content hash with the collisions
      taken out. Measured: cold 9.7-12.2 ms for 2-6 atoms (2.0-5.5 ms an atom,
      inside WP-1035's 1.8-8.7), warm 1-3 us.*
- [x] The table: one row per atom, the columns above, the ADP disclosure;
      `modelStacks` floor re-measured; `model.test.ts`.
- [x] Browser pass on NAC (special positions) and the corundum example;
      screenshot at the floor width; dist. *The second project is
      **fluorapatite**, not corundum: corundum is a round-robin `.prn` and its
      data fence keeps it out of the wheel (WP-1204), so it is not an example
      project and cannot be opened. FAP is the better second case anyway —
      seven sites, four Wyckoff letters, and it is what sets the floor.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "position or wyckoff"
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-0301 (affine site constraints), WP-1014, WP-1035 (symmetry surfaced).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**One row per atom, and the coordinate is a cell in it** (WP-1215,
`Model.svelte`, `lib/model.ts:positionEdits`, `gui/symmetry.py:position_values`).
Four rules. **A coordinate is typed and the site answers**: `POST
/api/structure/position` takes a whole position — the projection is a whole
position, since a `[1 1 0]` site cannot say what x should be without y — least-
squares it onto the site's own basis, and **refuses** an unreachable one naming
the directions it allows and the nearest position they reach. Never snapped:
that would move the atom to a *different site* than the one asked for, which is
`check_cell_angles`' objection one rank up. It is a `set_value` node, not an
`edit_model` one, because a position changes what the table holds and never what
it contains — the line `structure_aniso` is on the other side of. The client
computes none of it; a second copy of the DOF basis there is `symbolChanged`'s
trap. **A vary key is a path *or a glob***: a site's DOFs are freed together
("per-axis intent does not map onto rows such as [1,1,0]"), so the position's one
box says `phases.i.atoms.j.dof.*` and records one node, and a group that
disagrees with itself answers `null` and draws the DOM's `indeterminate` —
`false` over a half-freed site is untrue about the other half. **A memoised
answer may be asked for automatically, and the route it is on stays split**: the
Wyckoff search is keyed on (space group, positions) — the content tuple, not a
digest, and not the label, which cannot change a letter — so the `site` column
fetches itself, but a *miss* still costs 2.0-5.5 ms an atom, so it is not folded
into `GET /api/structure` and not awaited with it. Three client rules ride with
that and each is a bug the other two do not cover: the effect keys on `stamp`,
not `head`, because a local write calls `load()` and moves no head prop; the
better `causes` are held in their own field, because merged, two concurrent
fetches would let arrival order decide the sentence; and a stale *response* is
dropped rather than a fresh request. And **a width written in three places has
one test**: the atom table's floor is the table's `min-width`, the structure
column's `flex-basis` and `MODEL_MIN`, and only the third had one — the basis
was still WP-1034's number, so at exactly the stacking threshold the column came
out short and side-scrolled the table the threshold exists to give room to. Two
corollaries, both found by looking: a `colspan` cell's grid **is** part of the
table's min-content, so a track floor there must be `min(210px, 100%)` or opening
a disclosure widens the whole table; and the threshold must count the **grips
inside the row it is measuring**, which no version of it had.

## Handover log

- **2026-08-28** — The atom table reads like an atom table. An atom is one row
  with its coordinates in it, so changing a position means typing x, y and z
  where they are shown, rather than learning that a coordinate is really a
  displacement along `[1 1 0]` and typing that instead. The site still decides
  what is legal, but it decides it *out loud*: a position the symmetry cannot
  reach is refused, and the refusal names the directions the site allows and
  the nearest position they lead to, so the choice stays the user's rather than
  being made for them by a silent snap. The Wyckoff letter stopped being a
  button and became a column, because a search worth 2.0-5.5 ms an atom is
  worth that *once* and the head moves that used to re-pay it change no
  coordinate. What it cost is width: eleven columns need 642 px where seven
  needed 448, so the model pane stacks into one column at 1136 px instead of
  932, and in a narrow sidebar the table starts scrolling sooner than it did.

  **Done.** `POST /api/structure/position` takes `{atom, xyz}`, least-squares
  it onto the site's own DOF basis (`symmetry.position_values`) and commits a
  `set_value` node — not an `edit_model` one, because a position changes what
  the table *holds* and never what it *contains*. A missing atom is an
  `IndexError` → 404 as `structure_symmetry` already answers for a missing
  phase; a malformed path is a 400, because they are different repairs.
  `site_letters` is memoised on (space group, positions) — the content tuple,
  not a digest, and not the label, which cannot change a letter — so the panel
  fetches it on every head move, in parallel with the other three. The table is
  `label · species · site · x · y · z · occ · Biso · aniso · vary · ×`, one
  `<tr>`, with the U^ij patterns behind a per-atom disclosure; the DOF sub-row,
  the ADP sub-row and the separator that sat on the next atom's inputs are all
  gone. `lib/model.ts` grew `positionEdits`/`xyzText`, `lib/table.ts` grew
  `varyTargets`/`varyOfAll`/`varyEditFor`/`varyStillPending`, `lib/resize.ts`
  grew `GRIP`/`modelThreshold`. Four rules in `gui/CLAUDE.md` (cap 902 → 938,
  reason beside it); `using/model.md` gains the two paragraphs a reader of the
  panel needs.

  **Measured** (`[dev]`, darwin/arm64 — no jax/torch). The Wyckoff search:
  cold **9.7-12.2 ms** for 2-6 atoms (2.0-5.5 ms an atom, inside WP-1035's
  1.8-8.7), warm **1-3 µs**. The table's `min-content`, in a real browser and
  in the widest state it reaches: **642 px** on the fluorapatite example with
  one atom anisotropic (610 plain), against 599/567 on NAC — so
  `MODEL_MIN.structure` is 642 + 24 px of column padding = **666**, and the
  stacking threshold is 666 + 200 + 260 + two 5 px grips = **1136**. Verified
  at both ends: at 1136 the table wrap is 642/642 and does not scroll, at 1135
  it stacks. Counts: `tests/test_gui_server.py` **149 → 153** (both ends
  measured, +4, no new skips); gui vitest **551 → 567** (+16: one Wyckoff test
  replaced by two, +6 `positionEdits`, +4 glob-vary, +3 mount-level, +1 grip,
  +1 the review's rounding regression).
  Fast selection 3201 passed / 122 skipped and full suite **3342 passed / 131
  skipped** in 21:00 — the full suite re-run after the review's fixes landed,
  on a tree `origin/main` had not moved under, so it is the merged tree's count
  and needed no merge. Their pre-change baselines were
  not measured in this venv, so the exact-N check rests on the per-file
  measurement above, where both ends are.

  **Gotchas**, all three found by looking rather than by a test. A `colspan`
  cell's grid **is** part of the table's min-content: four 210 px U^ij patterns
  made the whole table 840 px the moment a disclosure opened, scrolling label,
  species and site off the left edge, until the track floor became
  `min(210px, 100%)`. `.dof input` was sizing the refine flag beside the value
  and drawing it as a squashed circle — WP-1214's `.cellrow` trap in the one
  place it was not fixed. And the atom table's floor is written in **three**
  places, of which only `MODEL_MIN` had a test: `.column.structure`'s
  `flex-basis` was still WP-1034's 472, so at exactly the stacking threshold
  the column came out 505 px and side-scrolled the table the threshold exists
  to give room to; the threshold itself never counted the two grips *inside*
  the row it measures, a gap that was there at 932 too. One more from the
  handover's own name audit: `lettersBusy` lost its only reader when the button
  went, which left the `site` column drawing `—` during the fetch — an absent
  answer wearing the shape of a real one, so it now draws `…` while busy.

  **Not done, deliberately.** The fixture for the position tests is LaB₆ rather
  than NAC (it already carries `1a` fully fixed and `6f` one-DOF, and a two-DOF
  site is one appended atom), and the second browser project is fluorapatite
  rather than corundum — corundum is a round-robin `.prn` whose data fence
  keeps it out of the wheel (WP-1204), so it is not an example project and
  cannot be opened. Both are noted on their checklist items.

  **Next: [1216](1216-instrument-form.md)**, then
  [1217](1217-history-graph-compare.md), then [1017](1017-gui-manual-onboarding.md).
  1216 inherits the two things this WP changed under it: the form column's 200 px
  is now measured against a 1136 px threshold, and at that width WP-1214's second
  control in the `Instrument` heading clips `Save profile…` to `Sa… prof`.

- **2026-08-25** — created from the v1.2 triage.
