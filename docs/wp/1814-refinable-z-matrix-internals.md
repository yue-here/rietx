# WP-1814 — refinable internal geometry: Z-matrix lengths, angles and dihedrals

Milestone: rigid-bodies · Status: 🔄 2026-11-18 — Z-matrix bodies refine, with every stage-start refusal; C1's restraint warning (#1510) is merged and leaves Z bodies alone; acceptance on acridine and the skill row remain
Depends on: 1815 (the derived-geometry table its esds are reported through); 1805
Priority: P3 2026-10-16 — TOPAS users expect it, and a refined bond with its esd is what a paper reports; nothing is wrong without it

## Goal

A rigid body built from a Z-matrix can refine its bond lengths, bond
angles and dihedral angles as ordinary parameters, each with an esd.

## Context

Issue #759 (mustachefeeling, 2026-10-06), section 1, chunk "1814" in its
provisional numbering, kept here. A Z-matrix places each atom of a molecule
from three earlier ones by a bond length r, a bond angle θ and a dihedral
φ. TOPAS refines them (Coelho, *TOPAS-Academic V6 Technical Reference*,
2015, § 10.22.1).

Checked at `138d55dc`: `from_zmatrix` (`crystallography/fragments.py:252`)
takes constant lengths, angles and dihedrals.

The proposal (#759 § 1), taken as the plan on 2026-10-16:

- `RigidBody.zmatrix: list[ZLine]`, each line's `r`, `angle` and `dihedral`
  a `Parameter`; a `PointLine` for a Cartesian template point.
- The map x_i = o + M(cell)⁻¹·Exp(δω)·R₀·(T_i(ζ) − c₀), with **c₀ a constant
  body-frame point frozen at declaration**. Recomputing the centroid as a
  length changes would turn a bond stretch into a shift of every atom.
- ∂x/∂ζ by forward-mode tangent propagation through the placement
  recursion. The reporter checked it against central differences to 8e-11
  on a synthetic triclinic fragment.
- A Z-matrix dihedral is not WP-1808's named-bond torsion. The subtree rule
  is wrong for it in general (line 3's angle off by 0.065 Å per degree on
  the reporter's fragment). A body declaring both on one bond compares the
  two reaches and refuses on a difference.
- Restrained or refined, never both by accident: a restraint on a fixed
  template quantity is refused at compile; on a refined `r` it is that
  parameter's prior.

### Inherited

## Non-goals

- Named-bond torsions (WP-1808, shipped).
- TLS and the TOPAS rigid import (fenced 2026-10-16).

## Tasks

- [ ] `ZLine`/`PointLine` on `RigidBody`, the frozen c₀, and the dot-paths.
- [x] The tangent-propagation Jacobian; the six placement partials checked against complex step.
- [x] The restrain-or-refine refusals and the torsion-reach refusal.
- [ ] Tests: placement partials vs complex step < 1e-12; the map's Jacobian vs FD < 1e-9; a freed C–C on acridine IX (COD 2242872) within its published esd
- [ ] Skill: the routing row for refining a Z-matrix body
- [ ] Theory tab: the section for the Z(ζ) − c₀ equation, deferred from the refine chunk to the acceptance chunk (a WP that adds physics adds its equation there)

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k "zmatrix or rigid_bod" -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho (2015), *TOPAS-Academic V6 Technical Reference*, § 10.22 (papers-only fence).
- Von Dreele (2019), *Powder Diffr.* 34, S32.
- Issue #759.

## Handover log

### 2026-11-18 — a restraint on a Z-matrix body is not reported

C1 (#1510) merged with the maintainer's ruling, a warning that keeps the
row, so this chunk now meets it: `_fixed_body_findings` returns nothing for a
body with a Z-matrix, whose lines' lengths, angles and dihedrals can change
any quantity a restraint over its atoms measures (the design review's M20,
"Z bodies: no structural refusal"). The third task is complete with it.

- *Done*: the guard in `model.restraints._fixed_body_findings`; its
  docstring, the `help.py` entry, the audit row's evidence and the skill's
  diagnostics row say so; one line in the release-note fragment. C1's tests
  renamed from refuse to warn (the maintainer's #1510 round 2, follow-up 2):
  `tests/test_restraint_body_warning.py`, `_warned`,
  `test_the_rule_warns_on_exactly_what_the_body_holds_fixed`.
- *Measured*: a bond (line 1's r) and an angle (line 2's angle) restraint on
  #759's branched fragment as a Z body raise nothing; the same restraints on
  the same template with the Z-matrix dropped warn. With the guard removed
  both cases fail.
- *Next*: unchanged, the acceptance chunk (T7, T8) and the routing row.

### 2026-11-17 — Z-matrix bodies refine

A body built from a Z-matrix now refines its bond lengths, angles and
dihedrals as ordinary parameters with esds, and a stage refuses at its start
every free internal the construction cannot carry.

- *Done*: `ZLine` and `RigidBody.zmatrix`/`zmatrix_origin` (c₀, frozen at
  declaration; `template` is the record Z(ζ) − c₀, checked at construction);
  the paths `phases.i.rigid_bodies.b.zmatrix.k.{r,angle,dihedral}`, absolute
  entries boxed to r ≥ 0 and the angle in [0, 180]; the block reads the
  internals after the twists and seeds `zmatrix_points`' tangent into the
  torsion loop, with a traced twin; an unboxed dihedral wraps at commit; the
  write-back stores the internals, then the template.  Stage-start refusals
  (`ParameterTable.refuse_free_internals`, beside `refuse_partial_turns`):
  `RIGID_BODY_TORSION_REACH`, `RIGID_BODY_INERT_DIHEDRAL`,
  `RIGID_BODY_RIDING_INTERNAL`, `RIGID_BODY_LINEAR_BEND`,
  `RIGID_BODY_NOT_INVARIANT` for a site body, an angle over a collinear
  triple, and an internal that moves only dummies.  Builders:
  `add_body(zmatrix=)` and `zmatrix_body_from_atoms(..., tree=)`.  A riding
  H on a Z body rides on its line's b.  The misfit check's body arm frees the
  internals the model frees.  A series compares the dihedrals modulo 360°
  (`SeriesResult.dihedral_paths`).  Task 2's block half; task 1 lacks
  `PointLine`, which waits on the maintainer (the review asks to defer it).
- *Measured* (`tests/test_zmatrix_body.py`, numpy, arm64 macOS, a dev venv):
  σ of each line's own bond, angle and torsion equals σ of its internal to
  1e-9 relative through the real table; the composed block against central
  differences under 1e-9 at three states (two chained torsions, a turned
  anchor, triclinic), its reach covering every nonzero at 20; a planted
  r 1.51 → 1.56 Å and a dihedral across ±180° recovered on a simulated
  pattern.  An expression tie on an internal is refused by `add_derived`
  (declaration order).
- *Gotcha*: the numpy fit's columns come from `_peak_chain_column`, which
  decodes through the block, so a wrong Z tangent moves the esds and the
  geometry table, not the fit: test the esds, never only a recovery.
- *Next*: the acceptance chunk (T7 simulated acridine, T8 the real-data
  record against WP-1806 Part 2's free-atom control) and the skill's routing
  row; the restraint rule on bodies with no Z-matrix is #1510.

### 2026-11-19 — review round 1 (Yue on #1665)

- *Done*: the box of a refined internal stops short of what `zmatrix_points`
  refuses mid-solve (a length at 0 raises, and an angle at 0° or 180° makes a
  later line's reference triple collinear): `ZMATRIX_R_FLOOR` (1e-6 Å) and
  `ZMATRIX_ANGLE_EDGE` (the angle whose sine is twice `COLLINEAR_TOL`), an
  anchor already past one keeping its own value in the box; `zmatrix_body_from_atoms`
  reads 0° for the dihedral of an exactly linear group instead of 0/0; the
  misfit check's body arm frees a Z body's torsions only where `vary` is set,
  as it does the internals; the two stage-start refusals without a code
  now carry `RIGID_BODY_COLLINEAR_ANGLE` and `RIGID_BODY_INERT_INTERNAL`; the
  theory page's "a distance has no esd" qualified for a Z body.
- *Next*: unchanged, the acceptance chunk (T7, T8), the routing row and the
  Theory-tab section (Tasks).

### 2026-11-09 — the placement and its exact tangent

A Z-matrix can now be differentiated exactly: `fragments.zmatrix_points`
places every line, dummies included, and returns ∂(positions)/∂(internals)
in closed form, per Å and per degree, so a later chunk can hand those
columns to the rigid-body block without a finite difference anywhere.
`from_zmatrix` places through it with its signature and results unchanged.
Nothing refines yet: no schema, table, block or reader change.

- *Done*: `zmatrix_points(refs, values, *, tangents=False, names=None)`, the
  six placement partials in closed form (`_place_partials`) chained forward
  line by line into an (m, n, 3) tangent in the twist tangents' layout
  (columns line by line, r, angle, dihedral); `zmatrix_reach(refs)`, the
  lines each line's internals can move, read off the references (a covering
  pattern). Task 2's placement half; its block half (seeding the columns
  into `body_tangents` after the twists) is the table chunk's.
- *Measured* (`tests/test_fragments.py`, numpy, arm64 macOS, a dev
  venv): the six partials against complex step, worst 3.6e-15 on
  100 draws; the whole-template tangent against complex step, worst
  7.8e-16, 4.7e-16 and 1.9e-15 of max|J| on a branched 8-atom fragment, a
  dummy with two 180° lines and acridine (COD 2242872, 23 atoms, 63
  internals), each at the anchor and 50 random states; the tangent takes
  about 2 ms on acridine. Old against new `from_zmatrix`: bit-identical
  positions on 241 random Z-matrices and identical refusal text on 62.
- *Gotcha*: at an angle of exactly 0° or 180° the position ignores the
  dihedral, but the angle's column is the one-sided derivative into
  [0, 180], which needs an open reference triple; over a collinear one no
  other angle is admissible and the column is zero. A free angle that
  reaches 180° in a fit therefore keeps a nonzero column when its triple
  is open, and has none over a collinear one.
- *Next*: the table chunk (schema, paths, block, write-back, every
  stage-start refusal), after #1388 merges; the restraint refusal on bodies
  with no Z-matrix is its own chunk.

- **2026-11-09** — A restraint can no longer sit on geometry a rigid body
  holds fixed without anyone noticing. A bond, angle, torsion or planarity
  restraint whose atoms all lie in one copy of one body, where no declared
  torsion turns some of those atoms and not the others, used to compile into a
  constant row that restrained nothing; the compile now warns with
  `RESTRAINT_ON_FIXED_BODY_GEOMETRY` (first built as a refusal, ruled a warning, see below), naming the restraint, its atoms and the
  body. This is the first half of the third task (chunk C1 of the adjudicated
  design); the half for Z-matrix bodies and the torsion-reach refusal come
  with the Z-matrix itself.
  *Done*: the set rule in `model.restraints._fixed_body_findings`,
  called from `resolve_phase_restraints` per restraint after its images are
  frozen, returned as a warning `Diagnostic` on `CompiledRestraints.findings`
  and carried to `result.diagnostics` (built first as a `RestraintRefused`
  error, changed on the ruling below); `help.py` entry; `_audit` rows for the
  code (tier 1, ambiguity 3, response warning), its suggestion and
  `_SAME_IMAGE_TOL`.
  The rule reads the declared torsions, never `vary`: read off `vary` it
  would report every restraint in a stage that holds the internals. One
  copy means one frozen image (R, t + n) shared by every entry. Tether and
  anti-bump rows are not checked. *Measured*: over all 546 bonds, angles and
  torsions of a generic seven-atom body with a chained torsion, the rule
  reports the 45 that stay put (within 1e-13, Å or degrees) when every
  torsion twists and the pose and cell move, and no other; the other 501
  moved by at least 0.021.
  `tests/test_restraint_body_refusal.py`, 18 tests; with the rule removed
  10 fail, and with the torsion test loosened to "turns any of them" 2 fail.
  *Ruled by Yue 2026-11-13*: warn, keep the row. The refusal became
  `level="warning"` (audit row tier 1, ambiguity 3, response `warning`), the
  row stays in the fit and the finding reaches `result.diagnostics`; the one
  dissenter, a refiner keeping a restraint set across a with-body and a
  without-body comparison, is why. The scope is the structural reading (the
  declared torsions decide, on bodies with no Z-matrix, none on a Z-matrix
  body), settled on the held-parameter precedent: rietx accepts a constant row
  of a held parameter everywhere else. *Next*: chunk C2a (placement and tangents), then
  C2b (Z-matrix bodies) after C2a and #1388.

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #759),
  behind WP-1815 as the maintainer decided. Checked against the tree at
  `138d55dc`: `from_zmatrix` takes constants. No open WP owns it: WP-1808
  names it as a non-goal and is closed. Next: wait for WP-1815.
