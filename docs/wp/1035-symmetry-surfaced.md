# WP-1035 — Symmetry, surfaced and editable

Milestone: v1.0 · Status: ✅ 2026-08-05
Track: The human GUI
Depends on: **1036** (its tables are what a preview would encode), 1014 (landed)
· soft: 1004

## Goal

A user can see a phase's symmetry and what it is responsible for — the symbol,
its crystal system and Laue class, the Wyckoff letter of each site, the cell
ties and held rows it causes — and can change it, through a verb that says what
the change would invalidate **before** it is applied.

## Goal, restated

The user asked *"where is the space group / symmetry information?"* and the
honest answer is that it is one string, quoted in three places and explained
in none. Everything the symmetry *does* — a tied `b`, a locked angle, a site
with two coordinate DOFs instead of three, an ADP basis of four patterns — is
visible in the parameter table as an effect with no named cause.

## Context

### What the mailbox carried, folded in on arrival (2026-08-05)

Both inherited sections were consumed at the start of the closing session and
are deleted per the protocol. What they said, and what became of it:

- **From [1034](1034-panel-layout.md)** — the pane is a tab and is routinely
  340–560 px wide (`modelStacks` reflows to one stacked column below 932 px), a
  column's minimum is a flex *basis* rather than a share, and the atom table sits
  in its own `overflow-x` wrapper. All still true, and all three shaped the
  layout: the symmetry block is not a `.cell`, every paragraph in it wraps rather
  than truncating, and the Wyckoff letter rides in the coordinate cell rather
  than a seventh column. Checked in a real browser at 341 px and 1600 px: nothing
  side-scrolls, before or after a preview.
- **From [1036](1036-crystal-system-settings.md)** — `cell_constraints(sg)` /
  `check_cell_angles(sg, angles)` are the oracles this WP's preview needed and
  they exist; `ext` and `monoclinic_unique_axis()` are load-bearing, so
  `symmetryLine` names the setting and not only the crystal system; the missing
  `Phase.space_group` validator is a deliberate deferral to
  [1003](1003-api-freeze-pypi.md), so validation stayed at the verb; and the trap
  — 79 of 564 settings served wrong under a *correct* free-parameter count —
  is why nothing here reports a count of refinable cell parameters. The stale
  `params/vector.py:141` reference below is stale in the same way it was.

### What exists (read at `660c950`)

- **`Phase.space_group: str`** (`schemas/structure.py:310`) is the only symmetry
  field — a Hermann-Mauguin symbol or an IT number as a string, resolved by
  `get_spacegroup` (`crystallography/symmetry.py:30-40`), which tries
  `find_spacegroup_by_name` then `find_spacegroup_by_number`. There is **no
  schema validator**: pydantic accepts any string, and an unresolvable one only
  fails later, where `_site_rows` catches it per phase and returns an error row
  (`gui/session.py:1919-1923`).
- `structure_from_cif` stores gemmi's canonical **`sg.xhm()`**
  (`crystallography/cif.py:81`), not the file's literal string; export writes it
  back at `cif.py:157`.
- It is quoted read-only in three places: the Model pane
  (`Model.svelte:674-676`, titled *"symmetry is derived by the CIF reader —
  re-import to change it"*), the 3D caption (`gui/structure3d.py:416` →
  `Structure3D.svelte:407`), and the CIF upload preview
  (`gui/imports.py:332`).
- **The `sites` arm already computes the hard part.** `_site_rows`
  (`gui/session.py:1908-1944`) returns `site_symmetry_order`, `special`,
  `dof_paths`, `dof_directions`, `adp_paths` and `adp_patterns`, through the
  *same* functions `ParameterTable` uses (`stabilizer_rotations` →
  `coordinate_basis` / `adp_basis`), never a second rule.

### Two measurements that decide where things go

**The phase-level facts are free.** One `get_spacegroup` call yields `number`,
`xhm()`, `hall`, `short_name`, `ext`, `crystal_system_str()`, `laue_str()`,
`point_group_hm()`, `centring_type()`, `is_centrosymmetric`, `is_sohncke`,
`is_enantiomorphic`, `is_symmorphic`, `is_reference_setting` and
`monoclinic_unique_axis` — **measured** against the worktree venv's gemmi, e.g.
`R -3 c` → number 167, xhm `R -3 c:H`, trigonal, Laue `-3m`, centring `R`. None
of them is exposed by any route today, and `crystal_system_str()` is already
computed inside `ParameterTable._collect` (`params/vector.py:141`) and
discarded. A phase symmetry summary therefore costs a lookup and may ride on
`/api/structure`.

**The per-atom Wyckoff letter is not free, and the refusal is already written
down.** `gui/session.py:574-578` says the letter needs
`wyckoff.site_constraints`, which runs spglib per atom, on a route refetched on
**every head move — including one a `set_vary` made** — so "the letter would be
decoration bought with a symmetry search per keystroke". The same docstring
names the escape at `:584-595`: a *deliberately-opened* route may do the search,
which is what `/api/structure3d` does. So the letters go on a deliberately
opened route. Note that `wyckoff.site_constraints` (`wyckoff.py:176-221`) is
currently **called from no production code at all** — only tests — and it
discards most of what spglib hands back (`pointgroup`, `hall_number`,
`equivalent_atoms`, the transformation). Nobody has timed it; a WP quoting a
budget must measure rather than repeat "expensive".

### The editing half, and why the gate is the whole job

**`PATCH /api/structure` already accepts a changed space group today.**
`structure_patch` (`gui/session.py:618-632`) validates through `_as_structure`
(pydantic plus a species check — no symmetry at all) and calls
`Refinement.edit` (`refine.py:241-264`), which swaps the models wholesale,
clears `_model` and `result_`, and **commits an `edit_model` node from a
snapshot that never builds a ParameterTable**.

The symmetry refusals live in `ParameterTable` construction, so they fire on the
*next* table build:

- an aniso tensor outside the new site's allowed subspace →
  `params/vector.py:308-313`, naming the allowed basis and the nearest allowed
  tensor;
- a Stephens block outside the new Laue subspace → `vector.py:206-211` (and an
  all-zero block with `vary=True` → `:213-219`);
- an atom with `vary=True` on a now fully fixed special position →
  `vector.py:262-265`.

So an incompatible change **succeeds, records a node, and then surfaces as a 500
`INTERNAL_ERROR`** on the panel's follow-up `GET /api/params`
(`session.py:404-406` → `Project.parameters` → `_working_table`), because a
`ValueError` from the table is not a `GuiError` (`gui/server.py:414-418`). The
head then stands at a state whose table cannot build, and the only way out is a
history checkout. **The gate has to run before `edit`, because `edit` is a point
of no return that pydantic does not guard.**

**Build the preview out of the existing rules, not a second copy of them**: copy
the structure, swap the symbol, construct a `ParameterTable` from the candidate,
and read the answer off it. The raises *are* the incompatibility list, in the
package's own words including the "nearest allowed" remediation they already
compute; the entry diff (`Entry` carries `path`/`vary`/`tie`/`locked`,
`vector.py:85-94`) *is* the tie/lock story; and `_site_rows(candidate)` against
`_site_rows(current)` *is* the per-atom lose/gain-DOF story, already in the shape
`Model.svelte` consumes. One caveat: construction stops at the **first**
incompatible item, so a complete per-atom preview loops the same
`stabilizer_rotations` + `adp_basis` + projection path `_site_rows` already
demonstrates.

### Three silent failures the table diff will not catch

Each needs its own answer; none of them raises today.

1. **A setting change reinterprets every coordinate while still resolving.**
   `R -3 c` → `R -3 c:H`, but `R -3 c:R` is the same group on rhombohedral axes.
   `is_reference_setting`, `ext` and `qualifier` are what a preview reads, and
   [1036](1036-crystal-system-settings.md) is the WP that makes the tie tables
   honest about settings in the first place — which is why this WP depends on it
   rather than the other way round.
2. **Orbit collisions.** `select_orbit_ops`
   (`crystallography/structure_factor.py:106-129`) dedups images *within* one
   atom's orbit; two asymmetric-unit atoms mapped onto each other by a higher
   symmetry double-count in F, and nothing checks it. The check is a pairwise
   minimum periodic distance across `expand_positions` orbits
   (`symmetry.py:89-97`).
3. **`_free_paths` silently re-frees renumbered DOFs.** `…dof.k` and `…adp.k`
   are *positional*, so after a group change `dof.0` may exist with a different
   direction; `_prepare_table(restore=True)` (`refine.py:497-507`) frees it
   without comment, and a path that vanished produces only a `warnings.warn`,
   invisible in the GUI.

### Where the symbol may be edited, and where it may not

WP-1014's founding split decides it: **if the parameter table has the path, the
parameter table owns it; anything that changes what the table *contains* goes as
a whole validated model.** The space group changes what the table contains, so
it is `PATCH /api/structure` (or a verb beside it, on the `structure_aniso`
pattern at `session.py:641-691`, which exists because both directions are
physics the client must not compute) — never `PATCH /api/params`.

Symbol validation has a precedent to copy rather than invent: `index_adopt`
maps a `ValueError` from an unresolvable symbol to
`GuiError(where=["space_group"])` (`session.py:1296-1302`).

## Non-goals

- **Not a symmetry finder.** Determining symmetry from a pattern is WP-1025's
  extinction screen, which already answers with **ranked classes, every class
  listing all its space groups**, because the extinction symbol is what a powder
  measures and a singleton there is unmeasurable. Nothing here may present a
  single derived group as a measurement.
- **Not an editable space group in the text document.** The `.rxt` document's
  editable surface is parameters and settings; a second authority on a phase's
  symmetry is what its rules forbid. The symbol appears there as a **rendered
  comment** only — the form `textdoc.py`'s own module docstring documents
  (`phase 0 "NAC"  # Ia-3d`) and never implemented — via the existing
  `_atom_comment` mechanism (`textdoc.py:422`), so **no format-version bump**.
- **Not the tie tables themselves** — [1036](1036-crystal-system-settings.md).
- **Not Wyckoff letters on `/api/structure`**, for the reason that route's own
  docstring gives.

## Tasks

- [x] **Phase symmetry summary** — symbol, IT number, crystal system, Laue
      class, point group, centring, centrosymmetric — from one gemmi lookup,
      served and rendered wherever a phase appears.
- [x] **Wyckoff letters per site on a deliberately-opened route**, with the
      per-atom cost *measured* and quoted, not assumed.
- [x] **Name the cause of a held row**: a cell tie or a locked angle says which
      symmetry element is responsible, so the parameter table stops showing
      effects with anonymous causes.
- [x] **The `.rxt` phase line carries the symbol as a comment**, with the
      render → parse → render fixed-point test still passing and no format bump.
- [x] **A preview verb** built from a candidate `ParameterTable` plus
      `_site_rows`: entries gaining/losing a tie or lock, DOF and ADP paths
      appearing/vanishing, the refusals verbatim with their nearest-allowed
      values, and the free paths that would be dropped or renumbered.
- [x] **The three silent failures** answered: a setting change flagged as one, an
      orbit-collision check, and a `_free_paths` casualty list — each surfaced in
      the preview rather than discovered afterwards. **Five**, in the end: a
      centring change and an orbit multiplicity join them, both for the same
      reason the other three qualify.
- [x] **Apply through the whole-model path**, gated on the preview, with an
      unresolvable symbol refused as `GuiError(where=["space_group"])`.
- [x] Tests: a server test that an incompatible change is **refused before any
      history node is written** (today it commits and then 500s — assert the new
      behaviour and keep a regression test for the old failure), vitest for the
      preview-rendering pure functions, and a jsdom mount test for the editor.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_wyckoff.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

And by hand, on the NAC project (COD 1000236 + `11BM_NAC.fxye`, **`I 21 3`** —
the draft said `Ia-3d`, and the CIF does not — six atoms over four species,
aniso): read the symmetry summary, check the Wyckoff letters against the
published site list, then attempt a change that must be refused — an aniso
tensor is the easy one — and confirm **the head has not moved** afterwards.

Done 2026-08-05 in headless Chromium at 1600 px and at 900 px (the 341 px
sidebar). The letters came back `12b 2..` / `8a .3.` / `24c 1`, matching
Na₂Ca₃Al₂F₁₄'s published sites; `R -3 c` was refused on γ with Apply disabled;
`I 41 3 2` applied and left one `edit_model` node. It also found the orbit
multiplicity gap — see the handover.

## References

- International Tables for Crystallography Vol. A — the letters, classes and
  settings being displayed.
- `gui/CLAUDE.md` — WP-1014's owns-the-path split; WP-1025's ranked-class rule.
- `docs/wp/1025-extinction-symbol.md` — why a single space group is never a
  measurement.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**Symmetry, surfaced and editable** (WP-1035, `src/rietx/gui/symmetry.py`,
`gui/src/lib/symmetry.ts`) is the phase's space group stopping being one
read-only string quoted in three places while everything it *does* — a tied `b`,
a locked angle, two DOFs instead of three — showed in the parameter table as an
effect with no named cause. Five rules. **Two tiers, split by a measurement**:
the phase facts are one `get_spacegroup` call, so they ride on `GET
/api/structure` beside `sites` as `symmetry` + `causes`, while a Wyckoff letter
is spglib per atom (**1.8-8.7 ms**, measured, and an orbit expansion is another
0.4-1.3) and lives on the deliberately-opened `GET /api/structure/symmetry` — the
escape that route's own docstring had already named. **`causes` names the
symmetry and stays silent where symmetry is not the subject**: it supplies the
missing subject of `held_because`'s "structurally fixed by symmetry **or by the
model**", so a locked `lor_strain` (the Stephens block's) keeps the anonymous
version rather than getting a wrong cause. **The preview is a diff of two
`ParameterTable`s and duplicates no rule** — the raises *are* the incompatibility
list, nearest-allowed values included, and since a table stops at the first bad
item the per-atom pass probes one atom at a time against a *real* table rather
than parsing a sentence this package owns elsewhere. **The gate is
`Refinement.edit`'s, not this layer's** — the failure was never a GUI one, so it
was fixed where it lived (root CLAUDE.md), and all `GuiSession._edit` adds is the
**address**: the refusal's leading dot-path, which a form needs to highlight the
field. And **the notes are for what a table diff structurally cannot see**: a
setting change, a centring change, `_free_paths` casualties (dropped *and*
renumbered — `…dof.k` is positional), an orbit collision, and the **orbit
multiplicity**, which a browser found by taking NAC from `I 21 3` to `I 41 3 2` —
same orders, same DOFs, same ties, same centring, empty diff, and 84 atoms in the
cell becoming 168. Two corollaries: a **blocked** preview is given no
consequences at all, since they would be computed from operators the model cannot
carry; and **a shared orbit is judged as a group, by its occupancies**. Atoms the
symmetry merges are one *site*, so the members are the connected components of
the coincidence relation and the verdict is the sum over the whole group — three
atoms at 0.4 are over-occupied where no pair of them is, which makes pairwise not
a coarser answer but a wrong one. Over 1 blocks; at or under it the same geometry
is a legal mixed site and F is right for it. **No prior art to copy, checked**:
GSAS-II recomputes every site symmetry on a space-group change
(`G2spc.UpdateSytSym`) and runs no such check, and TOPAS's `occ_merge` rescales
occupancies continuously during *structure solution* rather than refusing an edit
— deliberately not copied, because it silently rewrites a number the user typed,
which is the objection that made `check_cell_angles` refuse rather than
normalise.

## Handover log

- **2026-08-05 (second pass, on review)** — two things the reviewer would not
  accept as they stood, both now fixed in place rather than filed.

  **The gate was in the wrong package.** The first pass put it in
  `GuiSession._edit`, which protects a browser and leaves a Python caller
  standing in exactly the trap the WP describes: `ref.edit(structure=…)` accepted
  a model with no parameter table, wrote a node, and raised from whatever next
  asked for the table. Nothing about that was a GUI concern, so the check moved
  into **`Refinement.edit`** — it builds the *proposed* pair's table and refuses
  rather than recording. Two callers in the package and one in `examples/`, so
  the move was small; `GuiSession._edit` now only adds the **address** (the
  refusal's leading dot-path) that a form needs to highlight a field.
  `tests/test_history.py` carries the library-level row, including the repair
  path: the gate reads the candidate, so an edit that undoes the damage is not
  refused by it.

  **The collision check was pairwise, and pairwise is wrong, not coarse.**
  Coincidence is transitive — A with B and B with C means all three are one site
  — and the verdict is a *sum of occupancies over the site*. Three atoms at
  occ 0.4 are 1.2 on one site and over-occupied while no pair of them exceeds 1,
  so `orbit_collisions` now returns the **connected components** of the
  coincidence relation and `_collisions` sums over the group. It also fixes the
  advice: "keep one atom of the 3" is a sentence a pairwise message cannot write.

  **How TOPAS and GSAS-II handle this, asked and answered.** Neither does what
  this preview does, which is worth knowing before assuming there was an obvious
  design to copy.

  - **GSAS-II** recomputes every atom's site symmetry and multiplicity on a
    space-group change (`G2spc.UpdateSytSym`, called straight from the General
    tab's handler), shows an informational operator dialog, and **does not warn,
    confirm, or check for atoms that become equivalent**. Coordinates are not
    transformed — that is a separate, explicit *Transform Phase* operation
    (X′ = M(X−U)+V, with an Origin 1 → Origin 2 option), which is the same split
    this WP's `setting_change` note describes. The multiplicity change *is*
    visible, because GSAS-II's atom table has a multiplicity column; nothing
    draws attention to it.
  - **TOPAS** has no symmetry-edit gate at all — the space group is a line in an
    input file. `num_posns` on a `site` line "corresponds to the number of unique
    equivalent position generated from the space group; `num_posns` is updated on
    termination of refinement", i.e. the multiplicity is a **post-hoc readout**
    written back after the fit, not a pre-flight check. Its `occ_merge`
    (Favre-Nicolin & Černý 2002) *is* prior art for the double count —
    `occ_xyz = 1 / (1 + intersecting fractional volumes)`, explicitly "useful for
    identifying special positions" — but it is a continuous rescaling used during
    **structure solution**, and sites in `$sites` cannot then have their
    occupancies refined.

    Rescaling was considered and declined: it silently rewrites a number the user
    typed, which is the objection that made `check_cell_angles` refuse rather
    than normalise (WP-1036). If a future WP wants the TOPAS behaviour it should
    be an opt-in verb that says what it changed, not a side effect of an edit.

- **2026-08-05** — **closed.** Every task landed; both inherited sections were
  consumed on arrival (1034's width facts are in the panel's comments and its
  styles; 1036's four corrections were all still true and are quoted where they
  act). Four commits: the server, its tests, the panel, and what the browser
  found.

  **Where things are.** `src/rietx/gui/symmetry.py` (new) — phase facts, the
  cause map, the letters, the preview; `gui/src/lib/symmetry.ts` (new) — the
  formatters, nothing else. Three routes: `GET /api/structure/symmetry?phase=N`,
  `POST /api/structure/symmetry/preview`, `POST /api/structure/symmetry`.
  `_site_rows` moved out of `session.py` as `symmetry.site_rows`.

  **Two measurements, both of which decided a design.** A Wyckoff letter costs
  **1.8-8.7 ms an atom** (`site_constraints`, spglib) — 13 ms for NAC's six
  sites, 13 ms for LaB₆'s two — and an orbit expansion is another **0.4-1.3 ms an
  atom**, so both stay off `/api/structure`, which refetches on every head move
  including one a `set_vary` made. The WP's premise held: nobody had timed
  either, and the numbers are the reason the split is where it is rather than a
  restatement of "expensive".

  **The bug the WP predicted was real and was not about the space group.**
  Measured before the fix: `PATCH /api/structure` with an incompatible aniso
  tensor **succeeded**, committed `n0003`, and `params()` then raised a bare
  `ValueError` → 500. The gate therefore went into `_edit`, the one funnel every
  whole-model verb passes, and it tests the **candidate**, which is what keeps an
  edit that *repairs* a broken head from being refused by it. That escape path is
  asserted, 500 and all.

  **What the browser pass added, and it is the WP's own lesson repeating.** On
  real NAC, `I 21 3` → `I 41 3 2` moves **no parameter at all** — same
  stabiliser orders, same DOF counts, same ties, same centring — while every
  orbit doubles and the cell goes from 84 atoms to 168. The panel read "no
  parameter gains or loses a tie". So the site diff carries the orbit
  multiplicity and a `multiplicity_change` note carries the total. jsdom could
  not have found it: it is not a rendering fault, it is a *crystallographic*
  question about which symbols a person actually types. The same pass found a
  refused preview being given consequences ("the cell would hold 198 atoms" for
  an `R -3 c` over a 90° cell) — a blocked preview now prints only the refusal
  and the note that explains it.

  **Two judgements a successor may want to revisit.** An orbit collision blocks
  only when the shared occupancies sum past 1: a mixed site (Na 0.5 + Ca 0.5 on
  one orbit) is standard modelling and F is right for it, so the criterion is
  physical rather than a guess about intent — but it is pairwise, and a
  three-atom shared site is only caught as three pairs. And `held_because` was
  **not** changed: the cause is a second sentence served beside it, because
  `ParameterRow` mirrors `Entry` field for field and a third deliberate extra is
  not a thing to add days before the API freeze (`docs/wp/1003`).

  **One correction for the docs.** This WP's own Acceptance section, and
  [1009](1009-textdoc-format.md) line 28, say NAC is `Ia-3d` with four species.
  It is **`I 21 3` (No. 199), six atoms, four species** — that is what
  `tests/data/cod_1000236.cif` stores and what the page renders. The `.rxt`
  module docstring's example carried the same error and is fixed; the two
  planning docs are left as they are, recorded here.

  **Not done, and deliberately.** Nothing writes a Wyckoff letter into the model
  or the `.rxt` document, no symbol is *derived* from the pattern (that is
  WP-1025's ranked classes, and the non-goal stands), and `causes` says nothing
  about a row symmetry does not hold — a locked `lor_strain` belongs to the
  Stephens block and keeps `held_because`'s anonymous sentence.

- **2026-08-04** — created from the user's question *"where is the space group /
  symmetry information?"*, alongside [1032](1032-gui-repairs.md),
  [1033](1033-plot-range-regions.md), [1034](1034-panel-layout.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **The user chose "show it, explain it, and make it editable"** over
  display-only. That is binding.

  **Two findings a successor should not re-derive.** The phase-level symmetry
  facts are a free gemmi lookup (measured, listed above) while the per-atom
  Wyckoff letter is a spglib search the `/api/structure` docstring already
  refuses — so the split is decided, not open. And **`PATCH /api/structure`
  already accepts a space-group change today**, committing a history node before
  anything symmetry-aware runs, so the failure mode is a 500 on the next
  `GET /api/params` with a head that cannot build a table. That is arguably a
  bug that exists right now, independent of this feature, and fixing it *is*
  most of this WP.

  **The preview is a diff of two ParameterTables** — that is the design, and its
  virtue is that it duplicates no rule. Resist writing a second compatibility
  checker; the raises already carry their own remediation values.
