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

- **The defect.** Reported on main on 2026-11-08 on fluorapatite: a
  `BondRestraint(atom_i=2, atom_j=4, target=1.54, sigma=0.01)` (P3–O5), then an `edit()` whose
  structure swaps atoms 2 and 3 (P3 and F4). No warning, and the next fit restrains F4–O5, reported
  at 3.92 Å, to 1.54 Å (not re-measured here). Reproduced here on `origin/main` `1d054085d` on
  PbSO₄: a bond on S2–O4 named O3–O4 after S2 and O3 swapped, with no warning. Removing a
  restrained atom through `edit()` is accepted, and the next `fit()` raises `IndexError`.
- **Why.** `Refinement.edit` (`src/rietx/refine.py`, `edit`) reads the constraint registers it
  holds itself (`_user_holds`, `_ties`, `_free_paths`, `_held`) into the new numbering through
  `_carry_twin_moves(numbering_moves(...))` → `_renumber_atoms`. Restraints live on the candidate
  structure (`Phase.restraints`), not on the `Refinement`, so nothing renumbers them. And
  `Phase._valid_restraints` (`src/rietx/schemas/structure.py`) is a pydantic validator. It re-runs
  when `phase.atoms` is assigned (`validate_assignment`), but not after `model_copy` or an
  in-place change to the list (`del atoms[j]`, a swap), which is how a script builds the
  candidate. The GUI sends a whole structure as JSON, so it is validated on arrival and meets
  only the silent shift.
- **The seam.** `crystallography.twins.atom_moves(old, new)` already maps every atom path whose
  number changes (atoms matched by label, phases by name), and `renumber_path` reads one path
  through it. A restraint's atom index `j` on phase `i` is the path `phases.i.atoms.j`;
  `ValueRestraint.path` is a full dot-path.
- **Which numbering a candidate's restraint is in.** A caller may build the new structure by
  copying the old one (its restraints then read the old numbering) or write fresh restraints for
  the new atom list. **Its place in the list decides.** A restraint equal to the one the old
  partner phase held at the same place was carried, reads the old numbering and is renumbered.
  One appended after the old list's length, or one whose numbers name the same atoms in both
  numberings, is taken as written. Any other changed in the same edit that renumbered its atoms,
  and the edit is refused with the way to split it. A first design matched by content alone; the
  generality judge showed it misread a fresh row equal to an old one, which polyhedral sets hold
  routinely (four S–O bonds at 1.47 Å), and a test now pins that case.
- **Every kind indexes atoms.** `BondRestraint`, `AngleRestraint`, `TetherRestraint`,
  `AntiBumpRestraint` (`atom_i`, `atom_j`, `atom_k`), `PlanarityRestraint`, `TorsionRestraint`
  (`atoms`), `ValueRestraint` (`path`). `_valid_restraints` checks only the first two and the list
  kinds, so a tether or anti-bump index out of range is accepted even at construction. The edit
  now checks all seven. Construction still checks only the four, so a saved history whose node
  holds a bad tether, which `edit()` accepted before, still opens; widening construction is a
  stored-format question for the maintainer.
- **Siblings keyed by position.** `DistortionModes.base` and each `DistortionMode.vectors` hold one
  row per atom in order (WP-1419): a reorder pairs each atom with another's displacement. Rigid
  bodies (`RigidBody.atoms`, `BodyTorsion.axis`/`moves`, `riding`) name atoms by **label**, so a
  reorder leaves them right; a removed or renamed body atom is caught by
  `Phase._bodies_name_their_atoms`, which also does not re-run after `model_copy`.
- **The tier of each rule this WP adds.** The renumbering is tier 1: it follows from the
  dot-path convention and does what ties already do. Which numbering a restraint reads is the
  automatic action with an ambiguity ([DESIGN § Rules](../DESIGN.md#rules) rules 1 and 4). A row
  unchanged at its place, or one reading the same atoms either way, is kind 1 with no dissenter
  found. A changed row whose two readings differ is kind 3: the edit is refused and says why,
  since a refiner could mean either list. The renumbering records nothing when it fires,
  matching the hold and tie carry beside it (rule 5, convention); only a drop warns. Rule 4 asks
  a kind-1 action to record that it fired, and `SITE_DOFS_RENUMBERED` does so for coordinate
  directions, so the two written rules conflict here; that is the maintainer's to settle.
- **Practice.** TOPAS (`Distance_Restrain`, `Flatten`) and GSAS-II restraints name atoms by site
  label, so a reorder cannot move them (recall, not re-checked in either manual). rietx names
  them by index, the dot-path convention. Keying restraints by label would end this class of
  defect, and it is a stored-format change, so it is the maintainer's to decide.

## Non-goals

- Plan or stage globs that name a literal atom index, and the series' path-keyed reporting
  (`SeriesResult.trajectory`): WP-1991's handover lists both as not generalised.
- Restraints in a joint fit: WP-1995.

## Tasks

- [x] `twins.carry_restraints(old, new)`: each carried restraint read into the new numbering, one
      on a removed atom dropped and named; distortion-mode rows permuted on a pure reorder.
- [x] `Refinement.edit` applies it before the table check, re-runs the phase's restraint, body
      and mode validators on the candidate, and warns as the tie drop does.
- [x] The series `prepare` hook's structure goes through the same carry.
- [x] The edit checks tether and anti-bump indices and a `ValueRestraint`'s atom (construction does not; see Context).
- [x] The text document's tie refusal names the right source for a user tie.
- [x] Tests: reorder and delete on each restraint kind, distortion modes, a rigid-body atom removed,
      a fresh restraint taken as written, the series hook.
- [x] Skill: none. The warning names what was dropped and an agent need not act before the edit.

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
