# WP-1816 — a rigid body keeps its declared bonds, and anti-bump checks the pairs a torsion folds

Milestone: rigid-bodies · Status: ⬜
Depends on: 2144 (the warning this narrows); 1814 soft (its torsion test, PR #1510, and its Z-matrix reach)
Priority: P3 2026-11-13 — a workaround covers it (WP-2144's warning names the body, and a hand-written row restrains a pair); the graph has several waiting consumers

## Goal

A stored `RigidBody` carries the bonds its builder declared, or `None` when
none were declared. With bonds, the anti-bump builder and the stale check
keep a row for each intra-body pair four or more bonds apart that a declared
torsion moves. Without bonds, WP-2144's warning stays the answer.

## Context

**Ruled by Yue 2026-11-13** on issue #1507 ("both": WP-2144 now, this WP
for the direction). The stored `RigidBody` keeps its declared bonds:
an optional field, `None` meaning undeclared, so files written before it
open unchanged. WP-1319's rule is kept: bonds are declared, never perceived
from distances. With bonds, anti-bump restrains intra-body pairs four or more
bonds apart that a torsion moves. Pairs one to three bonds apart are
excluded, not scaled. A floor on a torsion's two ends (the pair three bonds
apart) biases the conformation, and a preference for a conformation belongs
in a torsion prior. Without bonds: WP-2144's warning.

**Counting bonds.** "n bonds apart" is the shortest path along the bond
graph. One bond apart is a bonded pair (force-field "1-2"), two is the ends
of a bond angle ("1-3"), three is the ends of a torsion ("1-4"), four is
"1-5". The ruling restrains four and more and excludes one to three.

**What exists, checked 2026-11-13 at `4c442c0dd`.**

- `crystallography.fragments.Fragment.bonds` (`fragments.py:136`) is
  `tuple[tuple[int, int], ...] | None`: declared, `None` when none were,
  never inferred (module docstring, "Bonds are declared, never perceived").
  `from_zmatrix(lines, bonds=None)` takes them as an argument, because a
  Z-matrix distance reference is not always a bond.
- `crystallography.bodies.add_body` accepts a `Fragment` as its template and
  keeps only its `xyz` (`bodies.py:108-120`). The bonds are dropped there,
  because `schemas.structure.RigidBody` (`structure.py:751`) has no field
  for them. `body_from_atoms` has no bonds argument.
- `model.restraints.anti_bump_restraints(..., exclude_same_body=True)` skips
  every pair inside one copy of a body (identity operation, the shift that
  keeps the image in the same molecule). `stale_anti_bump_pairs` skips the
  same pairs. WP-2144 documented this and added
  `RESTRAINT_BODY_CONTACTS_UNCHECKED`, which fires for any torsion body that
  turned and counts the rows the list holds inside it
  (`model.restraints.body_own_rows`). A hand-written row for one pair does
  not silence it, because the end-of-run search still skips the body's other
  pairs (WP-2144's review).
- The reproduction from #1507 is `tests/test_one_sided_restraints.py`'s
  `_chain_phase`: N1–C2–C3–C4–C5–O6 with torsions about C2–C3 and C4–C5,
  N1···O6 at 4.50 Å at the template and 1.50 Å at twists of −120° and
  −120°, under a 3.0 Å N–O minimum. N1 and O6 are five bonds apart, so the
  ruling gives them a row.

**Which pairs a torsion moves.** PR #1510 (WP-1814 chunk C1, open at
filing) writes `model.restraints._refuse_fixed_body_geometry`. A torsion
changes a set of atoms when it turns some of them, other than its own two
axis atoms, and not the others. For a pair that is the predicate this WP
needs, chained torsions included. Import it once #1510 merges; do not write
a second one. WP-1814's refinable Z-matrix internals (`fragments.zmatrix_reach`,
PR #1509, merged) move pairs too, and join this rule through the reach that
WP builds.

**Coordinate with WP-1814 (Mike's).** Cite it; do not edit its file. Its
Z-matrix bodies already carry their own construction graph, which is not the
bond graph (a dummy point may place a hydrogen). Whether a Z-matrix body's
bonds come from its `bonds=` argument only, as `from_zmatrix` does today, is
a question for Mike on #1507 before the first commit here.

**The same graph serves other work.** A declared bond list is what each of
these needs, and none should build its own:

- #1508: a ring in a Z-matrix body refines tree bonds only, so a free ring
  bond also moves the closing bond. Ring closure is a cycle in the bond graph.
- The torsion moved-set check: a declared `BodyTorsion.moves` can be checked
  against the side of the axis bond the graph puts each atom on (today it is
  declared and never checked, `structure.py:709`).
- #1510 (WP-1814 C1): which restraints a body holds fixed.
- WP-1814: which Z-matrix internals are bonds and which are construction
  references.
- Riding hydrogens (WP-1810): each H's parent is a bonded neighbour.
- The CIF writer's `_geom_bond` loop: today bonds are found by the
  covalent-radius rule (`GeometryTable.bonds`); a declared list can say which
  of those the model holds as bonds.
- GUI bonds: the structure viewer draws bonds by distance; a declared list
  draws the molecule as the user built it (WP-1548's ring perception, PR
  #1554, is a renderer's reading and does not feed the model).
- Rotatable-bond suggestions: a bond not in a ring, between two atoms each
  with another neighbour, is a torsion candidate.

**Practice** (`docs/practice.md` § Which pairs inside a molecule a contact
term checks, surveyed 2026-11-13). Every molecular code that checks contacts
inside a molecule picks the pairs from the bond graph. GROMACS excludes pairs
up to `nrexcl` bonds apart (3 in shipped force fields) and adds the 1-4 pairs
back scaled. CHARMM (`NBXMOD 5`), AMBER (`SCEE` 1.2, `SCNB` 2.0) and OPLS-AA
(0.5) exclude 1-2 and 1-3 and scale 1-4. Rosetta gives weight 0 up to three
bonds apart, 0.2 at four and 1 beyond, so that the torsion term is not
counted twice. Probe (MolProbity) excludes up to three bonds apart, and four
when one end is a hydrogen. MoveIt's Allowed Collision Matrix disables
adjacent links. DASH puts the torsion preference in a prior (Mogul
Distribution Bias); GALLOP's cost has no clash term. FOX selects anti-bump
pairs by scattering-power type with no bond filter seen. TOPAS was not
reached. The ruling's exclusion of one to three bonds apart is Rosetta's and
Probe's; the force fields' 1-4 scaling is declined for the reason the ruling
gives. Marks and sources: that section.

**Tier.** Excluding pairs one to three bonds apart is named practice (tier
2: Rosetta, Probe, GROMACS's `nrexcl` 3), cited above. "A rigid pair keeps
its distance" is physics. The minimum a pair is held to stays the caller's
(#677's rule): this WP chooses which pairs get a row, never a distance.
`exclude_same_body`'s default has no row in `_audit.DEFAULT_SEATS`; when its
meaning changes here, the default gets one (ambiguity: every competent
refiner would exclude bonded and angle pairs, so kind 1 for that half).

**Stored format.** A new optional field on `RigidBody` is a schema change:
`SCHEMA_VERSION` (`schemas/common.py`) moves, and a document without the
field must load as `bonds=None`. The `.rxt` text document and its parser
need the field too (WP-1812 owns the body's textdoc form; check its state
first). A stored-format change goes to Yue before merge (the user's standing
rule), with the field's name.

### Inherited

## Non-goals

- Perceiving bonds from distances (WP-1319's rule).
- Scaling 1-4 pairs, or any torsion prior (ruled out above; a torsion prior
  is its own WP if wanted).
- Choosing minimum distances for the caller (#677).
- Refinable Z-matrix internals themselves (WP-1814).
- The consumers listed above. Each takes the field when its own WP runs; this
  WP lands the field and the anti-bump rule.

## Tasks

- [ ] Ask Mike on #1507 for his view of the direction (the draft comment is
      in the WP-2144 runner's scratch), and fold his answer in here before
      the first code commit.
- [ ] `RigidBody.bonds: list[tuple[str, str]] | None = None`, by atom label,
      validated (both ends body atoms, no self-bond, no duplicate); schema
      version bump; an old document loads with `None`. `add_body` carries a
      `Fragment`'s bonds; `body_from_atoms` takes `bonds=`.
- [ ] `.rxt` and JSON round-trip of the field, if WP-1812 has not given the
      body a textdoc form yet, then JSON only and a note in WP-1812.
- [ ] The rule: with bonds, `anti_bump_restraints` keeps a row for an
      own-copy pair four or more bonds apart that a declared torsion moves
      (#1510's predicate); `stale_anti_bump_pairs` names such a pair the
      same way; one to three bonds apart stays skipped.
      `RESTRAINT_BODY_CONTACTS_UNCHECKED` then fires only for a body without
      bonds, so WP-2144's warning narrows to it.
- [ ] Tests: the chain fixture (N1–O6 gets a row; C2–C5, three bonds apart,
      does not); a pair no torsion moves keeps the skip; a body with
      `bonds=None` still warns; a positive control that fails with the rule
      reverted.
- [ ] Skill: the `RESTRAINT_BODY_CONTACTS_UNCHECKED` row says the warning
      means the body declared no bonds; `references/` row for declaring them.
- [ ] Manual: the theory chapter's anti-bump paragraph states the bond-count
      rule with its sources.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_one_sided_restraints.py tests/test_body_torsions.py tests/test_planarity_restraints.py -q
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_silence.py tests/test_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #1507 (anti-bump same-body skip), #1508 (ring closure), #677 (the
  caller-stated minimum), #759 (the Z-matrix proposal); PR #1510 (WP-1814
  C1).
- `docs/practice.md` § Which pairs inside a molecule a contact term checks.
- Alford, R. F. et al. (2017), *J. Chem. Theory Comput.* 13, 3031 (Rosetta's
  count-pair crossover).
- Cornell, W. D. et al. (1995), *J. Am. Chem. Soc.* 117, 5179 (AMBER).
- Jorgensen, W. L., Maxwell, D. S. & Tirado-Rives, J. (1996), *J. Am. Chem.
  Soc.* 118, 11225 (OPLS-AA).
- Kabova, E. A. et al. (2017), *J. Appl. Cryst.* 50, 1421 (DASH's Mogul
  Distribution Bias).

## Handover log

- **2026-11-13** — created by the WP-2144 runner from Yue's ruling of
  2026-11-13 on #1507. No open WP owns the bond list: WP-1814 (Mike's)
  refines Z-matrix internals and leaves the anti-bump skip alone, WP-1812 is
  the GUI, textdoc and manual form of a body, WP-1805 is the body's schema
  and is in flight on other follow-ups, so a fold into any of them would
  split this decision from its rule. The practice survey behind the ruling is
  in `docs/practice.md`; AMBER, OPLS-AA, DASH and the papers behind Probe
  were read only through secondary sources, and TOPAS was not reached. Next:
  Mike's view on #1507, then #1510's merge.
