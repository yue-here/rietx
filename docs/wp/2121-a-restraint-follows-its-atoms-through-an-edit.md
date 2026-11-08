# WP-2121 — A restraint follows its atoms through an edit

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-08 — a silent wrong answer on a path few fits run: an edit that reorders atoms leaves a bond restraint on two other atoms, and the next fit pulls them to the old target with nothing said

## Goal

A soft restraint names its atoms by position in `Phase.atoms`. When `Refinement.edit(structure=…)`
or a series `prepare` hook reorders, inserts or removes atoms, every restraint the new structure
carried over from the old one is renumbered onto the same atoms, as user ties and holds already are
(#1264). A restraint whose atom is gone is dropped and named in a warning. A structure whose
restraints, rigid bodies or distortion modes no longer fit its atom list is refused at the edit,
never by a bare `IndexError` at the next fit.

## Context

- **The defect, reproduced on `origin/main` `1d054085d` (2026-11-08).** Fluorapatite, phase 0,
  `BondRestraint(atom_i=2, atom_j=4, target=1.54, sigma=0.01)` (P3–O5). An `edit()` whose
  structure swaps atoms 2 and 3 (P3 and F4) gives no warning, and the next fit restrains F4–O5,
  measured at 3.92 Å, to 1.54 Å. Removing a restrained atom through `edit()` is accepted, and the
  next `fit()` raises `IndexError`.
- **Why.** `Refinement.edit` (`src/rietx/refine.py`, `edit`) reads the constraint registers it
  holds itself (`_user_holds`, `_ties`, `_free_paths`, `_held`) into the new numbering through
  `_carry_twin_moves(numbering_moves(...))` → `_renumber_atoms`. Restraints live on the candidate
  structure (`Phase.restraints`), not on the `Refinement`, so nothing renumbers them. And
  `Phase._valid_restraints` (`src/rietx/schemas/structure.py`) is a pydantic validator: it does
  not re-run after `model_copy` or a list assignment, which is how the GUI and every caller build
  the candidate.
- **The seam.** `crystallography.twins.atom_moves(old, new)` already maps every atom path whose
  number changes (atoms matched by label, phases by name), and `renumber_path` reads one path
  through it. A restraint's atom index `j` on phase `i` is the path `phases.i.atoms.j`;
  `ValueRestraint.path` is a full dot-path.
- **Which numbering a candidate's restraint is in.** A caller may build the new structure by
  copying the old one (its restraints then read the old numbering) or write fresh restraints for
  the new atom list. A restraint **equal to one the old partner phase held** was carried and reads
  the old numbering; any other was written for the new structure and is taken as written.
- **Every kind indexes atoms.** `BondRestraint`, `AngleRestraint`, `TetherRestraint`,
  `AntiBumpRestraint` (`atom_i`, `atom_j`, `atom_k`), `PlanarityRestraint`, `TorsionRestraint`
  (`atoms`), `ValueRestraint` (`path`). `_valid_restraints` checks only the first two and the list
  kinds, so a tether or anti-bump index out of range is accepted even at construction.
- **Siblings keyed by position.** `DistortionModes.base` and each `DistortionMode.vectors` hold one
  row per atom in order (WP-1419): a reorder pairs each atom with another's displacement. Rigid
  bodies (`RigidBody.atoms`, `BodyTorsion.axis`/`moves`, `riding`) name atoms by **label**, so a
  reorder leaves them right; a removed or renamed body atom is caught by
  `Phase._bodies_name_their_atoms`, which also does not re-run after `model_copy`.
- **The tier of each rule this WP adds.** The renumbering is tier 1: it follows from the
  dot-path convention and does what ties already do. The "equal to an old restraint ⇒ carried"
  reading is new judgement, an automatic action whose ambiguity is *which numbering the caller
  wrote in*. It errs only on a fresh restraint identical to an old one, which reads the same atoms
  whenever their labels did not move.

## Non-goals

- Plan or stage globs that name a literal atom index, and the series' path-keyed reporting
  (`SeriesResult.trajectory`): WP-1991's handover lists both as not generalised.
- Restraints in a joint fit: WP-1995.

## Tasks

- [ ] `twins.carry_restraints(old, new)`: each carried restraint read into the new numbering, one
      on a removed atom dropped and named; distortion-mode rows permuted on a pure reorder.
- [ ] `Refinement.edit` applies it before the table check, re-runs the phase's restraint, body
      and mode validators on the candidate, and warns as the tie drop does.
- [ ] The series `prepare` hook's structure goes through the same carry.
- [ ] `_valid_restraints` checks tether and anti-bump indices and a `ValueRestraint`'s atom.
- [ ] The text document's tie refusal names the right source for a user tie.
- [ ] Tests: reorder and delete on each restraint kind, distortion modes, a rigid-body atom removed,
      a fresh restraint taken as written, the series hook.
- [ ] Skill: none. The warning names what was dropped and an agent need not act before the edit.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_restraint_renumbering.py tests/test_site_twins_merged.py tests/test_restraints.py tests/test_one_sided_restraints.py tests/test_planarity_restraints.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- #1264 and WP-1991: the same defect for holds and ties, and the tie-drop warning this one matches.

## Handover log

- **2026-11-08** — created. No open WP owns restraints across an edit: WP-1991 (✅) fixed the
  registers the `Refinement` holds and names rigid-body paths as not generalised, and WP-1995 is
  the joint fit's restraints.
