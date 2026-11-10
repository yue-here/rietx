# WP-2140 — Every atom is named by its unique label

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-09 — the remedy for a class of silent wrong answers (a reference that lands on another atom after a reorder), ruled by the maintainer; a stored-format change, so it starts with an assessment

## Goal

Every reference to an atom names it by its site label, and a label is unique within its phase.
A restraint, a rigid body, a tie, a hold, a plan glob, a dot-path and a saved history all reach
the same atom after any reorder, insertion or removal. Every saved project from before the change
still opens.

## Context

- **The ruling.** Yue, 2026-11-09, answering WP-2121's question on restraints: "labels for
  everything, and make sure they're unique". Asked whether that includes parameter dot-paths
  (`phases.0.atoms.3.biso` read as `phases.0.atoms.O1.biso` in plans, holds, ties and saved
  histories), Yue answered: "yes, if this is the clear way to remedy this defect". So the scope is
  every atom reference, and the first task tests whether label dot-paths are that clear way.
- **The defect class.** An index names an atom by its place in `Phase.atoms`, and a place changes
  when the list does. WP-1991 (#1264) made holds, ties and carried values follow their atoms
  through an edit by matching atoms by label (`crystallography.twins.atom_moves`,
  `_matched_atoms`, `_renumber_atoms`). WP-2121 (#1463) did the same for the seven restraint
  kinds (`twins.carry_restraints`). Both renumber at each crossing point, and WP-2121 left three
  holes that renumbering at crossing points cannot reach:
  1. An edit given the very object `ref.structure`, mutated in place, renumbers nothing for
     holds, ties or restraints, since old and new are one object.
  2. A restraint's `op_index` picks an image from its atom's orbit. An edit that moves the site
     onto or off a special position changes the orbit, and the index is not re-read.
  3. A plan or stage glob naming a literal atom index (`phases.0.atoms.3.*`) is not renumbered.
  A label key removes the first and third. The second is about the orbit and survives any key.
- **What already uses labels.** Rigid bodies (`RigidBody.atoms`, `BodyTorsion.axis`/`moves`,
  `riding`) name atoms by label, checked by `Phase._bodies_name_their_atoms`. A series keys each
  trajectory by phase name and atom label (`sequential._SeriesNumbering`), and
  `sequential._refuse_duplicate_names` refuses a repeated label within a phase (Yue's ruling,
  2026-11-01). That refusal is the model for this WP's uniqueness rule, which today holds in a
  series and nowhere else.
- **Practice.** TOPAS (`Distance_Restrain`, `Flatten`) and GSAS-II restraints name atoms by site
  label (recall, not re-checked in either manual). GSAS-II keys refinable parameters by atom number
  (`0::Ax:3`, also recall), so the programs may answer the dot-path half differently. Check both
  manuals in the assessment and save the survey to `docs/practice.md`.
- **What a label dot-path must survive.** Dot-paths are split on `.` and glob-matched with
  fnmatch, so a label holding `.`, `*`, `?`, `[` or `]` cannot be a path segment (root CLAUDE.md,
  Conventions: no brackets in paths). A label spelled as digits (`3`) reads the same as an index.
  CIF labels are free text, so the reader meets both.
- **What a dot-path change touches.** The assessment measures each of these, with counts:
  - `src/rietx/help.py`: the `phases.*.atoms.*.…` families (coordinates, `dof`, `occ`, `biso`,
    `u11`…`u23`, `adp`, `moment`). A family glob still matches a label segment, so the families
    may not change at all.
  - `gui/src/lib/history.ts`: `PLACES`, one print format per family, held equal to the
    vocabulary by its vitest (`gui/CLAUDE.md`). A family change means `npm --prefix gui test`
    and a rebuilt dist.
  - `src/rietx/schemas/migrate.py`: `READ_POINTS`, the three points a stored document is read.
    Its repair is a static textual rename (old name to new name). An index-to-label migration is
    not one: it needs the structure stored in the same document to map `atoms.3` to `atoms.O1`,
    and that structure can differ from node to node of one history. This is the largest unknown.
  - Every `atoms.` glob in the plan presets (`strategy/staged.py`, `strategy/suggest.py`,
    `strategy/magnetic.py`; 10 `"phases.*.atoms…"` literals in `strategy/` on 2026-11-09). A
    wildcard segment matches a label as well as an index.
  - `ParameterTable` (`params/vector.py`), which builds the paths, and every reader that parses
    an atom index back out of a path (`twins`, `schemas/structure.py`'s atom-path regex).
- **The two remedies the assessment compares.** (A) Label dot-paths: the table builds
  `phases.0.atoms.O1.biso`, and stored references move to labels. (B) Index dot-paths kept, with
  renumbering at every crossing point, and only stored references (restraints, ties, holds,
  saved plans) moved to labels. A reference that keeps an index under (B) still owes the
  renumbering record below.
- **Folded from WP-2121 (closed 2026-11-09).**
  - *The renumbering records that it fired.* Settled by Claude under DESIGN.md Rule 1 and Rule 4
    (an automatic action records that it fired) and the reader rule that a repair is made only
    where it can say it did. `SITE_DOFS_RENUMBERED` already records the coordinate-direction
    case. Whatever still renumbers after this WP records it: one warning `Diagnostic` for holds,
    ties and restraints together, with its help entry, skill row and audit row. The maintainer
    may reverse this.
  - *Construction checks every atom a restraint names.* Settled by Claude under Yue's ruling
    that old files must always open (2026-08-21, the compatibility promise). `Phase._valid_restraints`
    checks bond, angle, planarity and torsion indices at construction; tether, anti-bump and a
    `ValueRestraint`'s atom are checked only at `edit()`. Building a new structure checks all
    seven kinds. A saved history holding such a node opens with a warning and is never refused.
    Under labels this is one check: the label exists in the phase. The maintainer may reverse
    this.
  - *The GUI and the API disagree on a removed restrained atom.* The GUI validates a whole
    structure on arrival, so it refuses removing the last-listed restrained atom, where `edit()`
    drops the restraint with a warning. The construction check above decides one behaviour for
    both.
  - *The generality judge never re-ran on WP-2121's prefix rule* (commit `09001aa00`). Moot for
    every restraint that moves to a label. If any keeps an index, run the judge on it.
- **Stored format.** This is a stored-format change: `project.json`, `history.jsonl`, saved
  plans and the `.rxt` document all hold atom paths. It needs a version bump on each format it
  touches (`_about.py` names the tokens; root CLAUDE.md, Conventions) and a migration at read.
  rietx users are few and in direct contact, so old code may break, but every old file opens.
- **Tier.** Label keys follow from the dot-path convention: tier 1. Uniqueness enforcement is a
  refusal with the reason named: kind 1. A reader that repairs duplicate labels makes an
  automatic action, so it records a `Diagnostic` (root CLAUDE.md, a silent correction is a
  reader's to make).

## Non-goals

- Phase keys. Phases are matched by name where unique (WP-1991), and `phases.0` stays an index
  unless the assessment shows the same defect there.
- Restraints in a joint fit: WP-1995.
- WP-1965's "subset by condition, or by label", a parametric equation's glob over atoms. It reads
  the same labels and should reuse whatever path form lands here.

## Tasks

- [ ] **Assess the remedy.** Compare (A) label dot-paths against (B) index dot-paths with
      renumbering and only stored references on labels. For each, measure what it touches (the
      list in Context, with counts), what the migration at read needs (above all whether
      `migrate.py`'s textual rename can carry it), and which of WP-2121's three holes it closes.
      Check TOPAS's and GSAS-II's manuals and save the survey to `docs/practice.md`. Settle it if
      one remedy closes the class at comparable cost. Bring it to Yue only if it is not clear,
      as a full brief.
- [ ] **Labels unique per phase, at construction.** A `Phase` with a repeated label is refused,
      naming the labels, as `sequential._refuse_duplicate_names` does today. A label that cannot
      be a path segment (`.`, `*`, `?`, `[`, `]`, or digits only) is refused too, if (A) wins.
- [ ] **Labels unique per phase, at read.** For each reader that builds atoms (CIF, the foreign
      project formats, the GSAS-II `.gpx`), decide by name what a duplicate label does: refused
      naming the file and the labels, or renamed with a `Diagnostic` naming each rename. Never a
      silent rename.
- [ ] **Every atom reference by label.** Restraints of all seven kinds, ties, holds, plan and
      stage globs, and whatever the assessment adds. Rigid bodies already comply.
- [ ] **Migration at read.** Every old index-keyed file opens: projects, histories, saved plans,
      `.rxt`. A test opens a project saved before the change and fits from its head.
- [ ] **Stored-format version bump** on each format touched, with the bump comment that is the
      changelog, and the change staged in the release record and notes on the day it lands.
- [ ] **The renumbering record** for whatever keeps an index (Context, folded from WP-2121).
- [ ] **Construction checks every atom a restraint names**, and a saved history holding a bad
      reference opens with a warning (Context). The GUI upload and `edit()` agree.
- [ ] **`op_index` re-read** when an edit moves a restrained atom onto or off a special
      position, or a refusal that names the restraint.
- [ ] Tests: a reorder, an insertion and a removal through each reference kind, an in-place
      mutation of `ref.structure`, a literal-index plan glob, a duplicate label at construction
      and at read, an old project opening.
- [ ] Skill: the path form an agent writes in a plan, tie or hold, if it changes; the uniqueness
      refusal's suggestion carries the rest.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_restraint_renumbering.py tests/test_site_twins_merged.py tests/test_restraints.py tests/test_sequential.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1991 (#1264, #1360) and WP-2121 (#1463): the renumbering this WP replaces or completes.
- `docs/DESIGN.md` § Rules, rules 1 and 4.

## Handover log

- **2026-11-09** — created, from the maintainer's 2026-11-09 answers to WP-2121's questions. No
  open WP owns atom keys: WP-2121 closed today and folds its remaining items here; WP-1991 (✅)
  matched atoms by label at crossing points; WP-1965 (parametric) owns a glob subset by label, not
  a key; WP-1933, WP-1468 and WP-2003 mention labels for other purposes. Numbered 2140, past the
  2130s, because another shift is filing GUI WPs there today. Bookkeeping PR: #1513. Next: the
  assessment task, which decides between label dot-paths and stored references alone.
