# WP-2140 — Every atom is named by its unique label

Milestone: unscheduled · Status: 🔄 2026-11-16 — assessment landed (#1625); label paths or renumbering waits on Yue's ruling, uniqueness and restraints-on-labels can start
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

## Findings: the assessment (task 1, 2026-11-16)

Measured on `origin/main` bc77a934e. The probes stayed in the session's scratch directory, so
each claim below names its `file:line` or the call that shows it.

**The premise holds.** On PbSO₄ (`tests/data/gsas2_pbso4.gpx`: Pb1 S2 O3 O4 O5), with a bond
restraint on S2–O3, a hold on `phases.0.atoms.4.occ` (O5) and a tie `atoms.3.biso = atoms.2.biso`
(O4 follows O3), O3 and O5 were swapped in place:

- A deep copy handed to `edit()`, the control: all three follow their atoms (bond S2–O3, hold on
  `atoms.2.occ`, tie source `atoms.4`).
- `ref.structure` itself handed to `edit()` (hole 1): the bond restrains S2–O5, the hold sits on
  O3 and the tie reads O5. No warning names any of the three.
- No `edit()` at all, then `parameters()`: the hold sits on O3. The one warning is about another
  path (`atoms.4.dof.2` dropped from a restored set).
- Hole 3: after the swap, `set_vary("phases.0.atoms.2.biso")` frees O5, which that path did not
  name when the glob was written.
- Construction checks bond, angle, planarity and torsion indices; tether, anti-bump and
  `ValueRestraint` are checked at `edit()` only (`schemas/structure.py:1855-1888`, `:1938-1958`),
  as Context says.
- A CIF with two sites labelled `O1` reads with no diagnostic (`Structure.from_cif` and
  `structure_from_cif(diagnostics=[])`, both `['Na1', 'O1', 'O1']`). Thirteen label-keyed dicts in
  `src` already assume uniqueness: `cif.py:1077` builds `{a.label: k}`, so a repeated label makes
  `CIF_SPECIES_NORMALISED` name the last atom of that label.

**What names an atom by index today** (`src`, the committed GUI dist excluded):

| Surface | Count | Where |
|---|---|---|
| Builds an index path (`atoms.{j}`) | 106 lines | readers and writers 40 (mostly `Diagnostic.where`: `io/projects/*`, `cif.py`, `magcif.py`, `io/recipe.py`, `io/exporters.py`); model and optimizer value lookups 18 (`model/forward.py:1555-1653`, `model/restraints.py:311-662`, `optimize/qpa.py:471-662`, `optimize/least_squares.py:1472,2013`); `ParameterTable` 10 (`params/vector.py:1409-1417,1982,4961-4971`); GUI server 10 (`gui/symmetry.py`, `gui/structure3d.py:1057`, `gui/imports.py:433`); renumbering 8 (`crystallography/twins.py`); other crystallography 7; `strategy/` 5; `report/` 4; `refine.py` 4 |
| Reads an index back by regex | 18 | `magnetic/moments.py:104`, `twins.py:313`, `gui/session.py:1829`, `gui/symmetry.py:310`, `io/projects/topas_refined.py:218`, `multi.py:3119`, `optimize/least_squares.py:96,98,168`, `refine.py:831,2210,8356,8523`, `schemas/sequential.py:417`, `schemas/structure.py:1906`, `sequential.py:1054`, `strategy/parameter_interval.py:93`, `strategy/staged.py:43` |
| Reads an index back by `split`/`int` | 9 | `io/projects/fullprof.py:3887`, `io/projects/topas_ties.py:433`, `io/recipe.py:1678`, `refine.py:4478,7830,8405,10403`, `params/vector.py:1884,1912` |
| GUI front end | 7 parsers, 6 builders | `gui/src/lib/model.ts:482,543,552,679-689`, `lib/paramtree.ts:240,250,289`, `next/Params.svelte:447,533,609,847`, `panels/Params.svelte:379,617` |
| Restraint fields typed `int` | 7 kinds | `schemas/structure.py:604-605,627-629,854-855,877-878,912,962`; `ValueRestraint.path` (`:646`) is an index dot-path |
| GUI routes carrying one | 9 | `PATCH /api/params`, `PUT /api/plan`, `PATCH /api/structure` (restraint indices), `POST /api/structure/aniso` and `/position` (`gui/session.py:1763,1807,1829`), `GET`/`POST /api/structure/symmetry` and `/preview` (`gui/symmetry.py:310`), `GET /api/structure3d` |
| Literal index paths outside `src` | tests 929 lines in 102 files, 36 restraint constructor lines; docs (WP files excluded) 80 lines in 29 files; examples 62; the skill 7, in each of its three copies; `src` docstrings 40 |

**What needs no change under either remedy.** Every family glob matches a label segment as well
as an index, since fnmatch's `*` matches any text: `help.py`'s 15 atom families (`:1089-1256`)
and the anisotropic opt-in (`:1362-1364`), `PLACES`' 15 atom rows (`gui/src/lib/history.ts:426-444`,
so its vitest and the dist are untouched), and the 67 `atoms.*` lines in `src` (the presets in
`strategy/staged.py`, `strategy/magnetic.py`, `purposes.py`, `viz/compare.py`). No partial-index
glob (`atoms.1*`, `atoms.?`) occurs in `src`, tests, docs or examples; 48 lines carry a
literal-index glob (`atoms.3.*`).

**What is stored.** A history node: `NodeAction.turn_on`, `turn_off`, `values`, `ties`,
`untied`, `held`, `unheld` (`schemas/history.py:114-149`); `RefinementState.free_paths`, `ties`,
`holds`, `stderr` (`:300-360`); the restraints inside its structure; `Diagnostic.where` (`:388`);
`TreeHeader.plan` (`:419`). `project.json`: `ProjectDoc.plan` (`schemas/project.py:155`), in a
document holding no structure. The `.rxt`: rows such as `atoms.0.biso` under a phase block
(`gui/textdoc.py:26`). Also `live/events.jsonl` (`free_paths`, `held`), a result's JSON, and the
GUI's recovery copy of unapplied edits. Version tokens: `SCHEMA_VERSION` 0.61,
`PROJECT_FORMAT_VERSION` 1.6, the textdoc `FORMAT_VERSION` 1, `EVENT_SCHEMA_VERSION` 3, the
recovery `FORMAT_VERSION` 1.

**What already names atoms by label.** Rigid bodies; a series, whose `_SeriesNumbering`
(`sequential.py:715`) matches by label and then writes the key back as an index path; the
PowderLine recipe, which keys sites by label (`io/recipe.py:1075-1112`); the report's moment rows
(`report/schemas.py:1699`).

**Labels in the files we hold.** The 19 committed CIFs (17 blocks with atom sites) carry no
repeated label, no digits-only label and none holding `.`, `*`, `?`, `[` or `]`. No wider corpus
was measured, so this says nothing about what a reader meets in general.

**The migration at read.** `migrate.py`'s textual rename cannot carry it, for three reasons. It
has no structure, and `atoms.3` becomes `atoms.O1` only through the structure the path was written
against. That structure can differ from node to node. And it is unversioned and idempotent
(`migrate.py:124-145`), so a digits-only label is indistinguishable from an old index. The module's
second repair can: `restore_declared_ranges` is structural, gated on the version a node was written
under, and applied per node at `RefinementTree.load` (`DECLARED_RANGE_READ_POINTS`,
`migrate.py:157-160`). Each node holds its own structure. Four cases need a decision beyond that:

1. A node whose action changed the atom list holds two numberings: its action's paths may name
   the parent's atoms.
2. `project.json`'s plan has no structure beside it; read it against the history head.
3. An `.rxt` is parsed against the live model (`textdoc.parse`), which has the structure.
4. `events.jsonl` sits outside `READ_POINTS` on purpose (display-only, `migrate.py:58-64`), and a
   result's JSON records a finished fit. Both can stay as written.

**The two remedies, and a third from practice.**

- **(A) Label dot-paths.** A path names the atom, so holes 1 and 3 and the no-`edit()` route close
  by construction, with no crossing point to miss. It retires the atom half of the renumbering
  (`twins.atom_moves`, `carry_restraints`, `_renumber_atoms`) and of `_SeriesNumbering`. Cost: the
  106 builders, 27 parsers and 7 front-end parsers above, about a thousand test lines, four
  format bumps (history schema, project, `.rxt`, recovery) with the structural migration, and a
  label-syntax rule that refuses labels a CIF allows, so every reader that builds atoms needs a
  rename with a `Diagnostic`. Hole 2 stays open.
- **(B) Index dot-paths with renumbering, stored references on labels.** The restraints move to
  labels; their migration is the cheapest of anything here, since a `mode="before"` validator can
  read the sibling `atoms` list in the same phase. Holds, ties, the free set and plan globs are
  dot-paths themselves, so keeping the table on indices while they hold labels means two spellings
  and a translation at every boundary; in practice (B) keeps them on indices, renumbered. Hole 1
  closes if `edit()` compares against a label snapshot of the last accepted state rather than
  `self.structure` (`numbering_moves` already accepts a `CoordinateSnapshot`, `twins.py:578`). The
  no-`edit()` route closes only if that comparison runs at every table build. Hole 3 needs saved
  plans renumbered at each edit too. The class stays open: each new register of atom paths owes
  its own renumbering, the shape of WP-1441's absences.
- **(C) GSAS-II's hidden stable id** (`docs/practice.md` § Naming an atom). Not proposed: it adds
  an invisible key beside the visible one the user already writes.

**Settled, and the question left.** Neither remedy closes the class at comparable cost: (A)
closes it by construction at the cost above; (B) closes the three known routes at a fraction of
it and leaves the class open. The choice is a stored-format change, so it goes to Yue as the
brief below rather than being settled here. Whichever way it goes, three tasks are needed and
can start now: labels unique per phase at construction, the decision for duplicate labels at
read, and the seven restraint kinds on labels.

> **For Yue.** Label dot-paths (A) close the class by construction and cost about 140 code
> sites, about a thousand test lines and four format bumps with a per-node structural migration.
> Renumbering with restraints on labels (B) closes the three known routes at a fraction of that,
> and every new register of atom paths will owe renumbering. Which? Recommendation: (A), landed
> in two steps: restraints on labels and uniqueness first (needed under either), then the paths.
> If (A): are labels holding `.`, `*`, `?`, `[`, `]` or only digits renamed at read with a
> `Diagnostic`, or refused? And may `events.jsonl` and a result's JSON stay in the old spelling?

*2026-11-23:* the choice between (A) and (B) stays with Yue, as a stored-format change. One
sub-call is settled. If (A) is chosen, `events.jsonl` keeps the old spelling, since
`schemas/migrate.py:56-70` leaves its reader outside `READ_POINTS` on purpose. A result's JSON goes
with Yue's call. Settled by Claude under DESIGN.md Rule 5 Convention and that comment, 2026-11-23;
checked blind.

## Non-goals

- Phase keys. Phases are matched by name where unique (WP-1991), and `phases.0` stays an index
  unless the assessment shows the same defect there.
- Restraints in a joint fit: WP-1995.
- WP-1965's "subset by condition, or by label", a parametric equation's glob over atoms. It reads
  the same labels and should reuse whatever path form lands here.

## Tasks

- [x] **Assess the remedy.** (2026-11-16, #1625: § Findings; not clear at comparable cost, so
      the brief for Yue closes that section.) Compare (A) label dot-paths against (B) index dot-paths with
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

- **2026-11-16** — task 1, the assessment, by a ghostshift runner; PR #1625. No format or
  behaviour changed. The defect is real on today's main. An edit given the working structure
  itself puts a restraint, a hold and a tie on the wrong atom with nothing said. A swap with no
  edit at all moves a hold. A saved index glob frees the atom that took the old one's place. A CIF
  with a repeated label reads silently. Label dot-paths close the class by construction, but at
  about 140 code sites, a thousand test lines and four format bumps. Renumbering with restraints
  on labels closes the known routes far more cheaply and leaves the class open. That is not
  "comparable cost", so the choice went to Yue as a brief rather than being settled.
  *Done:* § Findings (counts with `file:line`, the stored surfaces, the migration analysis, the
  two remedies and GSAS-II's third), the brief that closes it, and `docs/practice.md` § Naming an
  atom (TOPAS v6 Technical Reference and GSAS-II documentation, read by one agent, no source and
  no macro body). *Measured:* the probes are listed in § Findings and stayed in the session's
  scratch directory: a PbSO₄ swap through each route, the duplicate-label CIF, and label hazards
  over the 19 committed CIFs (none). *Gotchas:* `migrate_document_text` is unversioned and
  idempotent, so it cannot tell a digits-only label from an old index. The structural per-node
  repair (`restore_declared_ranges`' pattern) is the one that can carry this. `_user_holds` is
  the user's hold register; `_held` is the stage's (root CLAUDE.md § A hold). *Not done:* no
  forward note to WP-1965 (its label glob reuses whatever form lands here, which is undecided).
  Next: Yue's answer to the brief. Meanwhile the three tasks needed under either remedy can start:
  uniqueness at construction (task 2), the duplicate-label decision at read (task 3), and the seven
  restraint kinds on labels (part of task 4), whose migration reads the sibling atom list.

- **2026-11-09** — created, from the maintainer's 2026-11-09 answers to WP-2121's questions. No
  open WP owns atom keys: WP-2121 closed today and folds its remaining items here; WP-1991 (✅)
  matched atoms by label at crossing points; WP-1965 (parametric) owns a glob subset by label, not
  a key; WP-1933, WP-1468 and WP-2003 mention labels for other purposes. Numbered 2140, past the
  2130s, because another shift is filing GUI WPs there today. Bookkeeping PR: #1513. Next: the
  assessment task, which decides between label dot-paths and stored references alone.
