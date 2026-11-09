# WP-2121 — A restraint follows its atoms through an edit

Milestone: unscheduled · Status: ✅ 2026-11-09 — every task landed (PR #1463, merged 2026-11-08); the three questions under *Next* are answered, and labels as atom keys, the renumbering record and the construction checks move to WP-2140
Track: What fires, and what stays silent
Depends on: —

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

### 2026-11-09 (2nd session) — the three questions answered; the WP closes

The maintainer answered the question that mattered most: atoms are to be named by label
everywhere, and labels must be unique. That ends the defect class this WP patched, because an
atom's label does not change when the list is reordered. The two smaller questions were settled
under written rules and fold into the same new WP, WP-2140. Every task here landed, so the WP
closes. Next: WP-2140's first task, the assessment of label dot-paths.

*The answers*, one per question under the previous entry's *Next*.

- **Item 3, whether restraints name atoms by label.** Ruled by Yue 2026-11-09: "labels for
  everything, and make sure they're unique". Asked whether that includes parameter dot-paths
  (`phases.0.atoms.3.biso` read as `phases.0.atoms.O1.biso` in plans, holds, ties and saved
  histories), Yue answered: "yes, if this is the clear way to remedy this defect". That makes
  the remedy itself a question WP-2140 answers first, by measurement. It comes back to Yue only
  if the answer is not clear.
- **Item 2, whether the renumbering records that it fired.** Settled by Claude under DESIGN.md
  Rule 1 and Rule 4 (an automatic action records that it fired), and under the reader rule that a
  repair is made only where it can say it did. The first settlement filed it as its own WP. It
  now folds into WP-2140: label keys remove the renumbering for every reference that moves to a
  label, and whatever keeps an index still owes the record. The maintainer may reverse this.
- **Item 4, whether construction checks tether, anti-bump and value-path atoms.** Settled by
  Claude under Yue's ruling that old files must always open (2026-08-21, the compatibility
  promise): yes when a new structure is built; a saved history holding such a node opens with a
  warning and is never refused. Folded into WP-2140, since a label's existence is the same check.
  The maintainer may reverse this.
- **Item 5, the follow-ups.** Each moves to WP-2140 after the fold check (no open WP owns atom
  keys; WP-1965's "subset by label" is a parametric glob, not a key). (a) An edit given the very
  object `ref.structure` renumbers nothing: label keys dissolve it for every reference that moves
  to a label, and WP-2140 checks what is left. (b) A restraint's `op_index` is not re-read when
  an edit moves its atom onto or off a special position: a label does not fix it, so it is a
  WP-2140 task. (c) The GUI refuses a structure upload that removes a restrained atom, where
  `edit()` drops the restraint with a warning: WP-2140's construction check decides one
  behaviour for both. (d) Re-running the generality judge on the prefix rule is moot where
  restraints move to labels, and WP-2140 runs it if any restraint keeps an index.

*Done.* Status line closed (✅), `Priority:` line deleted, narrative moved to the v1.12 record.
No code or test changed. Bookkeeping PR: #1513.

### 2026-11-09 — bookkeeping: PR #1463 merged, and the WP stays open

The fix is on main. PR #1463 merged on 2026-11-08 at 14:00 UTC as `527048aa4`, so a restraint
follows its atoms through an edit in every build from that commit on. The status line still said
the PR was open, and now records the merge. The WP stays open. Three of the decisions under the
previous entry's *Next* are the maintainer's, and none has been made.

*Done.* Status line synced to the tree: `git branch -r --contains 527048aa4` names `origin/main`,
and `gh pr view 1463` reads `MERGED`. No code, test or other WP changed. Bookkeeping PR: #1500.

*Next*, in order. Item 1 of the previous *Next* (review and merge) is done. Items 2-4 wait for the
maintainer: whether the renumbering records that it fired, whether restraints name atoms by label,
and whether construction checks tether, anti-bump and value-path atoms. Item 5's follow-ups each
become a WP after the fold check. The WP closes once the three decisions are answered.

### 2026-11-08 (2nd session) — the review's two refusal messages

A `/pr-review` re-gate of PR #1463 found the logic sound and two refusals worded wrongly. Both now
say what happened. An edit refused because a restraint's numbering is ambiguous no longer opens
with "this model names an atom it does not have", which was false there. And removing an atom
together with the restraint on it, when that restraint is not last, is still refused, but the
message now says why: each later restraint moved up a place, so it reads as changed. Next: the
maintainer merges, and settles the three decisions under *Next* below.

*Done.* `Refinement.edit` wraps `carry_restraints` and `_check_atom_references` separately, so
only the second refusal carries the missing-atom sentence. The ambiguity message in
`twins.carry_restraints` adds the sentence on deletion and is split into one clause per sentence.
The 1.12.0 *Code to check* note adds the same sentence. Tests: the σ-edit case asserts the refusal
no longer says "does not have"; a new case removes O3 and the S2–O3 bond in one edit, expects the
refusal, then removes O3 alone and gets S2–O5 kept with a warning.

*Measured.* Before these edits, on the merged tree `a723b0eea` (macOS arm64, Python 3.12,
`[dev,jax]`, nothing else running): fast selection 14 522 passed, 243 skipped, 32 xfailed;
`tests/test_acceptance_sequential.py -m slow` 16 passed; `tests.audit_delta` no row changed;
`tests.reader_output` unchanged. After them: `tests/test_restraint_renumbering.py` and
`tests/test_sequential.py` 195 passed. The full `-m slow` suite was not run.

*Not changed, deliberately.* The rule itself: a deletion inside the restraint list still refuses
when atoms renumber. Matching an order-preserving subsequence of the old list would accept it, but
that is the content matching the generality judge failed (a fresh row can equal an old one).

### 2026-11-08 — every task landed; the PR waits for approval

A restraint now stays on the atoms it was written for when an edit reorders, inserts or removes
atoms. Before, swapping two atoms moved a bond restraint onto a different pair, and the next fit
pulled that pair toward the old target with nothing said. A restraint whose atom is removed is
dropped and named in a warning, where the next fit used to crash. An edit that changes a restraint
while also renumbering its atoms is now refused, because the numbers could mean either atom list.
A series `prepare` hook gets the same treatment, and so does a distortion-mode record. Next: the
maintainer approves posting the PR, and settles the two questions under *Next*.

*Done.* `twins.carry_restraints(old, new)` reads each restraint of the new structure through
`atom_moves`, for all seven kinds. A restraint equal to the one the old phase held **at the same
place** is carried and renumbered. One appended after the old rows, or one naming the same atoms in
both numberings, is taken as written. Any other changed beside a renumbering raises `ValueError`.
A carried restraint on a removed atom is dropped and named in `restraints_dropped_message` (the tie
drop's words). A `DistortionModes` record carried unchanged is permuted with a pure reorder.
`Refinement.edit` runs the carry and `Structure._check_atom_references` (restraint indices of all
seven kinds, rigid-body labels, mode-row counts, value paths) before the table check. The series
`_fit_one` runs both after `prepare`. Construction is unchanged: the tether, anti-bump and
value-path checks run at the edit only, so a saved history holding such a node still opens. The
GUI text document's refusal now names `ref.untie()`/`ref.tie()` for a user tie. The 1.12.0 notes
stage the change under *Code to check* and *Changed*. The `edit()` docstring says the rule.

*Not generalised, deliberately.* (1) A caller who mutates `ref.structure` in place and passes that
same object to `edit()` gets no renumbering of restraints, holds or ties: old and new are one
object. Fixing it needs a snapshot of the committed structure. (2) A restraint's `op_index` picks an
image from the atom's orbit; an edit that moves a site onto or off a special position changes that
orbit, and the index is not re-read. (3) Plan and stage globs naming a literal atom index, as
WP-1991 left them. (4) The GUI sends a whole structure as JSON, which is validated on arrival, so a
GUI removal of the last-listed restrained atom is refused there by `Phase`'s own check, before
`edit()` could drop it with a warning.

*Measured.* PbSO₄ (`tests/data/gsas2_pbso4.gpx`), macOS arm64, Python 3.12, `[dev]` venv. On
`origin/main` `1d054085d` a bond on S2–O4 named O3–O4 after an S2/O3 swap, with no warning.
`tests/test_restraint_renumbering.py` adds 38 tests; each restraint kind is run through a swap, a
removal ahead of it and a removal of its own atom. Fast selection (`-m "not slow"`, junit on this tree at `3cdc940b5` plus this entry): 14 785 collected, 14 335 passed, 448 skipped, 2 failed. Both failures were this entry's own (a stale index and headings the hook cannot read), fixed before commit, and `test_docs_consistency.py` then passed. The 38 added cases are 19 functions costing 0.73 s together (`tests.added_test_times`, one local run). No baseline was run on `origin/main`, so the count check rests on collection: the branch adds exactly those 38 and changes no other test file.

*Review.* `/code-review high --fix` reported 8. Fixed: a no-move fast path and an O(n) carried
check (an anti-bump list of thousands of rows cost n × m model comparisons per edit and per series
pattern); the series hook now runs the same atom-reference checks as `edit()`; a test for a value
path following its phase; one helper for parsing an atom path. Declined: the same-object case
(above, not generalised); refusing old documents (moot since the checks left construction); the
duplicated atom-path regex in `schemas/structure.py` (`schemas` cannot import
`crystallography.twins` without a cycle); the series warning's `stacklevel` (the depth to the
caller's frame varies). `test_manual_api` then found the two `check_atom_references` methods in no
manual bucket; they became private.

*Generality.* The judge's report on commit `91d14fa12`, unedited apart from its headings, set in bold to sit inside this entry:

**Item 1: `crystallography/twins.py::carry_restraints`, the renumbering and the drop**

**Verdict: holds.** The evidence for acting is much stronger. Renumbering an untouched restraint has no dissenter. The open point is that nothing records that the action fired.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | "every restraint the new structure carried over from the old one is renumbered onto the same atoms … A restraint whose atom is gone is dropped and named in a warning" (WP Goal) | Matches the diff. It is always on, with no switch, in `Refinement.edit` (refine.py, before the table check) and in the series `_fit_one` after `prepare` (sequential.py). Atoms are matched through the existing `atom_moves`/`_matched_atoms` label matcher, which ties and holds already use (#1264, the earlier fix for holds and ties). | stated correctly |
| 2. Kind of ambiguity | "The renumbering is tier 1: it follows from the dot-path convention and does what ties already do" (WP Context, tier line). No kind is named for this half. | Kind 1 fits. Which atom a number means after a reorder is settled by the label match. No `_audit.py` row exists, so there is no `ambiguity` field to check. | agrees |
| 3. Case against | Not addressed for this half | Renumbering an untouched carried restraint: none found. Dropping versus refusing: a refiner who deletes a restrained atom to replace it, for example O5 by a split pair O5a/O5b, could want the edit refused so they re-restrain the replacement. The drop is a Python `UserWarning`, not a `Diagnostic`, so it reaches neither the result nor the history node. The upstream matcher maps an atom renamed beside a removal to "no partner" (`_matched_atoms` docstring), so that atom's restraints are dropped although it still exists. The warning names them. Practice: the author's TOPAS/GSAS-II label keying is "recall, not re-checked". I could not check it here. `docs/practice.md` has no row on how restraints name atoms. | weak case |
| 4. Case for | "the next fit restrains F4–O5, measured at 3.92 Å, to 1.54 Å" with no warning. A removal is accepted "and the next `fit()` raises `IndexError`" (WP Context, reproduced on `1d054085d`). | The measured cost is a 2.4 Å misfit that the fit pulls on in silence. Leaving it to the caller means renumbering every restraint by hand on every reorder. Anti-bump lists can run to "thousands of rows" (comment in twins.py). The neighbouring convention already carries holds and ties (#1264, `_renumber_atoms`). | strong case |
| 5. Tier and source | tier 1 (WP Context) | Tier 1 is sound: reading an index through a label map is arithmetic. Tests are in `tests/test_restraint_renumbering.py`: `test_a_restraint_follows_its_atoms_through_a_swap`, `…_when_one_ahead_of_them_goes`, `test_a_restraint_on_a_removed_atom_is_dropped_and_named`, `test_the_swapped_bond_restrains_the_distance_it_was_written_for`, `test_a_value_restraint_follows_its_phase_when_a_phase_is_inserted_ahead` and `test_a_series_prepare_that_removes_an_atom_moves_the_restraints_with_it`. Program defaults: recall only, not checked. | holds |
| 6. Dataset families | none given | There is no threshold. The tests use one fixture, PbSO₄ from `tests/data/gsas2_pbso4.gpx` (development data). They verify the code and validate nothing. | n/a |
| 7. What says it fired | "It records nothing when it fires, matching the hold and tie carry it sits beside (rule 5, convention); only a drop warns" (WP Context) | There is no record field and no diagnostic code. Rule 4 says "Kind 1 … records that it fired", and generality.md § The rule says "a kept action leaves a record field". The convention the author cites is real for #1264's atom renumbering, which only warns. In the same function (`_carry_twin_moves`), the coordinate-direction renumbering does raise `SITE_DOFS_RENUMBERED`, a warning diagnostic. So the convention is split. Whether Rule 5's convention or Rule 4 governs is the maintainer's call. | weak |

Evidence that would change the verdict: a check of GSAS-II or TOPAS showing that it refuses an atom deletion a restraint names, rather than dropping the restraint, would move the drop half to weak.

**Item 2: the "equal to an old restraint ⇒ carried" rule inside `carry_restraints`**

**Verdict: fails on kind and record, and is weak on the case against.** The evidence against is stronger than the WP states. The named dissenter is not a corner case: restraint sets routinely hold rows that are equal in everything but their atom numbers.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | "A restraint **equal to one the old partner phase held** was carried and reads the old numbering; any other was written for the new structure and is taken as written" (WP Context) | It decides which numbering each restraint in the new structure is in, without the caller saying. It is implemented as set membership on (class name, `model_dump_json()`) over the old phase's restraints (twins.py, `carried = {...}`). A row's position in the list is ignored. | stated correctly |
| 2. Kind of ambiguity | "new judgement, an automatic action whose ambiguity is *which numbering the caller wrote in* … it is kind 1 with one named dissenter" (WP Context) | Rule 1: "if a competent refiner who would act otherwise can be named, the action moves to the second or third kind." Naming a dissenter while keeping kind 1 contradicts that gate. The pattern cannot score which numbering the caller meant, so kind 2 ranking does not apply. Kind 3 means report and stop, which here is a refusal or a request to the caller. The other route is a design that removes the ambiguity. | fails |
| 3. Case against | "a caller who reorders atoms and rewrites a restraint with the very indices an old one had, meaning the atoms now at those numbers. That restraint is read as carried and moved." (WP Context) | This case is common, for four reasons. All four are my reading of the code; none was run. **(a)** Polyhedral sets share kind, target and σ: four S–O bonds at 1.47 Å, six O–S–O angles at 109.47°. The branch's own `test_a_restraint_written_for_the_new_numbering_is_taken_as_written` gives the fresh S2–O3 bond `target=1.48` against the carried 1.47. At 1.47, the fixture's own S–O target, the fresh `(atom_i=1, atom_j=4)` row equals the old row. It would then be moved onto S2–O5, leaving S2–O3 unrestrained and S2–O5 restrained twice, in silence. **(b)** `rietx.model.restraints.anti_bump_restraints` builds rows with one `min_distance`/σ/weight per species pair. The `RESTRAINT_PAIRS_STALE` suggestion (the warning for a contact that came inside its anti-bump minimum) tells the caller to "rebuild the list with anti_bump_restraints from these coordinates". A caller who reorders or removes an atom and rebuilds the list in the same structure has every regenerated row that matches an old (i, j, op_index, translation) row read as old-numbered. On a reorder that row moves to other atoms in silence. On a removal it can be dropped, with a warning naming a row the caller just wrote. **(c)** A 1.11 caller who worked around the defect by renumbering restraints by hand loses the fix. Swapped equal-target rows, for example (1,2) and (1,4) both at 1.47, each equal an old row and are moved back, so the original defect returns. That case is not under the release note's § Code to check. **(d)** The reverse case: a carried restraint that the caller also edits in the same candidate, for example a tightened σ, no longer equals the old row. It is "taken as written" in the old numbering, which is the original defect, unless the index falls out of range. `test_an_edit_that_moves_no_atom_leaves_the_restraints_alone` covers only the case with no atom moved. Designs a competent author could choose instead: a position-aware match (new row k equals old row k); the old list as a prefix of the new one (prefix renumbered, appended rows taken as written), which settles (a), (c) and the test's case; refusing an edit that both moves atoms and changes restraints; or keying restraints by label (the author's own option, a stored-format change). What limits the damage: no code under `src/rietx/gui` writes restraints (grep), so GUI edits always meet the copy case. The misfires are on the API, agent and series-hook paths. | strong case |
| 4. Case for | "A caller may build the new structure by copying the old one … or write fresh restraints for the new atom list" (WP Context) | Without some rule, every copy-and-edit, the path that "the GUI and every caller" use (WP Context), keeps the original defect. The equality test costs one set lookup per row. It handles the common case correctly: copy, reorder, leave the restraints alone. This supports having *a* rule. It does not single out set-membership equality over the position-aware or prefix variants, which handle the same common case. | moderate case |
| 5. Tier and source | "new judgement" (WP Context). No tier number is given. | This is rietx's own rule, so tier 3. It needs grounds and the maintainer's dated approval. The established programs key restraints by label (recall, not checked), so they never face this ambiguity. No audit row exists: `_audit.py` is untouched, and its module docstring lists always-on actions among what its guard cannot see. | tier 3, unapproved |
| 6. Dataset families | none given | There is no threshold. One fixture (PbSO₄, development data) verifies the code. The judgement ground decides this item. | n/a |
| 7. What says it fired | "It records nothing when it fires" (WP Context) | Nothing records whether a row was classed as carried or as fresh. Cases (a), (c) and (d) misclassify in silence. Rule 4 requires kind 1 to record that it fired. | fails |

Evidence that would change the verdict: two kinds of evidence would move this to holds. One is evidence that callers never write restraints into a structure that also moves atoms, from the skill's examples, the tests and agent transcripts. The other is a redesign (position or prefix match, or refusing mixed edits) with a test at equal targets (1.47 against 1.47) and a record of which rows were renumbered.

**Item 3: `carry_restraints`' permutation of `DistortionModes` rows**

**Verdict: holds.** The evidence for acting is stronger. A wrong permutation would be refused by the existing drift check, so it could not mislead in silence.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | "distortion-mode rows permuted on a pure reorder" (WP Tasks). The docstring says the record is permuted only when "carried unchanged … where the atoms were only reordered; any other change … leaves it to the phase's own check" (twins.py). | The guard is: the record equals the old one, every old atom has a partner, and the order is a true permutation. An insertion or removal is left to `_modes_cover_the_atoms`, which refuses a count mismatch. | stated correctly |
| 2. Kind of ambiguity | none given | Kind 1, arithmetic. `DistortionModes.base` is "the parent-derived position of each entry of `Phase.atoms`", one row per atom in order (schemas/structure.py docstring). | kind 1 |
| 3. Case against | none given | none found. A caller who reorders atoms to fix a record they think is misordered cannot start from such a record in a working `Refinement`. The table build already refuses stored coordinates that disagree with base + Σ amplitude·vector, within `DISTORTION_DRIFT_TOL` (the allowed gap between them). | none found |
| 4. Case for | "a swap gave each atom the other's base and displacement, and the table refused the edit for a coordinate drift the edit never made" (docstring of `test_distortion_mode_rows_follow_their_atoms_through_a_swap`) | Without the permutation, a pure reorder needs the record rebuilt with `displacive_statement`. | strong case |
| 5. Tier and source | none given | Tier 1: an index permutation. `test_distortion_mode_rows_follow_their_atoms_through_a_swap` asserts that each atom's coordinates are unchanged (`pytest.approx`), and `test_removing_an_atom_a_mode_record_covers_refuses_the_edit` covers the removal. Program practice: not checked. | holds |
| 6. Dataset families | none given | There is no threshold. One synthetic phase (`tests/test_distortion_block._phase`). | n/a |
| 7. What says it fired | none given | Nothing records it. The drift check is the safety net: a wrong permutation refuses the edit instead of moving atoms. | acceptable given the net |

Evidence that would change the verdict: a phase where a wrong permutation passes the drift check, for example two atoms whose base rows and displacements coincide, would weaken it.

**Item 4: the new refusals (`Structure.check_atom_references` at edit and series; tether, anti-bump and value-path checks at construction)**

**Verdict: holds.** The evidence for acting is stronger: a refusal at the source replaces an `IndexError` at the next fit. One cost to stored projects is unmeasured.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides unasked | "refused at the edit, never by a bare `IndexError` at the next fit" (WP Goal). "Each failed only at the next fit before, with an `IndexError` or a missing path" (release note). | Three refusals. `edit()` and the series path re-run the restraint, rigid-body and mode checks on the candidate. `Phase._valid_restraints` now also checks tether and anti-bump indices. A new `Structure` validator checks a `ValueRestraint` path on an atom. | stated correctly |
| 2. Kind of ambiguity | none given | Kind 1, arithmetic: an index past the end of the atom list names no atom. | kind 1 |
| 3. Case against | none given | For the edit-time refusal: none found. For the construction-time checks: a history record holds `RefinementState.structure`, and it is validated on read (`history/store.py`, `read_numbered_records`). One bad node fails the whole file as "malformed history record". On main, `edit()` accepted removing a tethered or anti-bumped atom, the defect this WP fixes, so a 1.11 tree can hold such a node. On this branch that tree fails to open; before, it opened and failed only on a fit from that node. Bond, angle, planarity and torsion rows already behave this way on main, so the change widens an existing behaviour to three more kinds. I did not measure whether any such tree exists. The release note mentions building a model and says nothing of stored projects. A `ValueRestraint` path is checked only at the `Structure` level, so a `Phase` built alone still passes. | weak case |
| 4. Case for | the reproduction: "the next `fit()` raises `IndexError`" (WP Context) | The refusal names the record at the edit. It closes a gap in a rule that already covered four of the seven restraint kinds (the Rule 5 convention). | strong case |
| 5. Tier and source | none given | Tier 1. Tests in `tests/test_restraint_renumbering.py`: `test_a_new_restraint_out_of_range_refuses_the_edit`, `test_a_one_sided_restraint_out_of_range_is_refused_when_built`, `test_a_value_restraint_on_an_atom_the_phase_lacks_is_refused_when_built`, `test_removing_an_atom_a_mode_record_covers_refuses_the_edit` and `test_a_rigid_body_follows_a_swap_by_label_and_refuses_losing_an_atom`. | holds |
| 6. Dataset families | none given | There is no threshold. | n/a |
| 7. What says it fired | the `ValueError` text: "refused rather than recorded" (refine.py `edit`), "after prepare: …" (sequential.py) | The raised error names the record that no longer fits. That message is the record. | holds |

Evidence that would change the verdict: a stored 1.11 tree that this branch cannot open, with no repair path, would make the construction-time half weak. It would stay weak until a load-time repair or a release-note line exists.

*Author's answer to item 2.* Redesigned onto the judge's prefix alternative with refusal of mixed
edits (commit `09001aa00`). Cases (a), (c) and (d) are tests: (a) is taken as written, (c) and (d)
refuse with the way to split the edit. Case (b) is covered by the same rule: a rebuilt list whose
rows differ at their places refuses where its numbers would read other atoms. The judge did not
re-run on the redesign. *Answer to item 4.* The three checks left construction (same commit).

*Next*, in order. The maintainer approved posting on 2026-11-08, and the PR is open for review.

1. **Review and merge the PR.** CI is the gate (ruff, the fast suite on every supported Python,
   a `[dev,jax]` job). The full selection did not run here; the change moves no measured number,
   so the nightly is its first full run.
2. **Decide whether the renumbering records that it fired.** DESIGN rule 4 asks a kind-1 action
   to record that it fired, and `SITE_DOFS_RENUMBERED` does so for coordinate directions. The hold
   and tie carry (#1264) records nothing, and this WP matched it. A yes adds a warning
   `Diagnostic` (a code, its help entry and skill row, an audit row) for holds, ties and
   restraints together, as its own WP.
3. **Decide whether restraints name atoms by label**, as TOPAS and GSAS-II do (recall, not checked
   in their manuals). It would end this class of defect, including the ambiguity this WP refuses.
   It is a stored-format change, so it needs a schema version and a reader for index-keyed files.
4. **Decide whether construction checks tether, anti-bump and value-path atoms.** Today only the
   edit does (Context). Checking at construction would also refuse a saved history holding such a
   node; nobody has measured whether one exists.
5. **Follow-ups, each its own WP after the fold check.** (a) `edit()` given the very object
   `ref.structure` renumbers nothing, for holds, ties or restraints: needs a snapshot of the last
   committed structure (proposed as a session card on 2026-11-08). (b) A restraint's `op_index`
   is not re-read when an edit moves its atom onto or off a special position. (c) The GUI's
   structure upload validates on arrival, so removing the last-listed restrained atom there is
   refused instead of dropped with a warning. (d) Optionally, re-run the generality judge on the
   redesigned rule (commit `09001aa00`); it judged the first design only.

- **2026-11-08** — created. No open WP owns restraints across an edit: WP-1991 (✅) fixed the
  registers the `Refinement` holds and names rigid-body paths as not generalised, and WP-1995 is
  the joint fit's restraints.
