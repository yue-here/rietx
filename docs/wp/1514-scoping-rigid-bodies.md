# WP-1514 — Scoping rigid bodies: the milestone that makes the parameter map nonlinear

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1319 soft, the fragment file; 1515 and 1516 soft, the sibling scopings it is placed against)
Priority: P2 2026-09-28 — a scoping WP: the structure-solution milestone 1515 scopes waits on the decision this one takes

## Goal

A queued milestone draft for rigid bodies and Z-matrices (#195): WP files,
a ROADMAP section, and a DESIGN.md entry if a locked decision moves. The
draft answers one question before any other: where the nonlinear map from a
body's parameters to its atoms' coordinates lives, and how coordinate esds
come back out of it. It is sized, ordered, and placed against v1.6, v1.7
and the two sibling scopings (1515, 1516). This WP builds nothing.

## Context

**Unfenced 2026-09-28.** "Z-matrices and rigid bodies (#195)" sat in
ROADMAP § v2+. The grounds for moving it are in DESIGN.md § Locked
decisions, *Structure fence revised*. The same day this WP was re-scoped
from an implementation WP to a scoping one, because the measurement below
put the work at milestone size.

**Why it is milestone-sized** (measured on `c1bd21dd`).

- **It breaks a stated design property.** The parameter table is "an
  affine constraint block **p_phys = C·p_free + d** (sparse C, rebuilt at
  every stage boundary, constant during a least-squares run — a constant
  matmul stays exact under the future autodiff backends)"
  (`src/rietx/params/vector.py:8`). A rotation cannot be written as a
  constant C.
- **Many readers depend on C's fixed structure.** `moving_paths` has 36
  references in 6 files, `column_reach` 14 in 3, `unmeasured_rows` 9 in 7,
  and `rebase_anchored_dofs` 7 in 2. `stderr_physical` computes
  σ² = diag(C·Cov·Cᵀ). `decode` has 52 call sites in 18 files. The traced
  twin (`backend/traced.py`) rebuilds the same map for jax and torch.
- **The one precedent does not transfer.** v1.6's magnetic moment is the
  only non-affine parameterisation in the package (`vector.py:1203`). Its
  DOFs are a modulus and angles. The components are locked entries,
  refreshed at commit, and "a component has no `C` row, so it has no esd".
  That was right for a direction a powder cannot determine. A rigid body's
  atom coordinates carry esds that bond lengths, the geometry propagation
  in `model/geometry.py`, and the CIF all need.
- **The work reaches past the core.** Restraint partials
  (`model/restraints.py`, whose second consumer is the geometry esds), the
  analytic Jacobian's declared reach (`_column_extras`), the cross-backend
  rows, riding hydrogens, the CIF writer, the GUI's structure table and 3D
  viewer, history serialization, `help.py` and manual Part 2.
- **For scale:** v1.6, the magnetic structure, is 7 WPs over one non-affine
  parameterisation.

**What the source run needed.** `solution case 1` (private corpus map § 5;
WP-1510 has the source) has two metal sites and two rigid aromatic ligands
in the asymmetric unit.
- At about 2.4 effective observations per parameter, free atoms let the
  rings buckle to chase intensity.
- The agent built an 18-DOF body outside rietx: per ligand an anchor atom,
  an axis and a twist, as a Rodrigues rotation of an ideal template. It
  pushed coordinates in through `set_values`.
- The Rietveld handoff held ring shape with `BondRestraint` on the 1-2, 1-3
  and 1-4 distances at `restraint_weight_scale=100`.
- Two disorder copies of each ligand were tethered by a penalty in a raw
  scipy loop, because rietx's restraints (`Bond`, `Angle` and `Value`,
  `schemas/structure.py:623-676`) are all equalities.
- Hydrogens were placed by hand for the CIFs.

**Rigid bodies are useful without a solver.** Any molecular crystal or MOF
refinement wants them. So the first rung stands alone, and 1515's milestone
builds on it.

### Inherited

- **2026-10-03, from [1433](1433-the-inp-grammar-still-refused.md), closed:
  four TOPAS files wait on rigid bodies.** PR #587 taught `read_topas_inp`
  `STR(sg)`, `STR(sg, name)` and `#if` over `#prm`, so four archive files
  that used to refuse at parse now read their phases and stop at
  `to_structure` on a rigid body. They are the corpus's first test of a
  rigid-body reader (the contributor's count over 462 of 606 archive files is
  in 1433's 2026-10-01 entry).

- **2026-09-30, from the issue triage (issue #561): the reporter's scoping
  proposal for this WP.** Thirteen independent chunks R0-R12 off `main`, each
  with a test that can fail; R0 (rotation mathematics) and R1 (`Fragment`)
  touch no v1.6 file. The design's one load-bearing move is a typed
  `derived: list[DerivedBlock]` beside the affine block in
  `params/vector.py`, with `decode`, `local_jacobian` and `reach_pattern()`
  surfaces, so body-atom coordinates get esds (TOPAS's rule, Coelho 2015
  § 10.22.8) while the moment keeps its "no C row, no esd" rule. Prior art is
  clean-room (manuals and papers; FOX is GPL, concepts only). Two public
  cases: acridine form IX (COD 2242872) and diacetylene at 5 K (COD 1577467).
  *Checked at `e3e6486a`*: the `vector.py` lines it quotes (`:8-10`, `:1132`,
  `:1218-1223`) are on `4de25284` and were not re-measured; a cost-only
  proposal, no code. Seven questions are open and are the maintainer's: where
  the map lives, orientation convention, the moment migrating later, the
  anti-bump pair list, whether R0/R1 may start before v1.6 closes, chunk
  numbering (the next unused number is 1527 here, and 1527 is now taken by
  the species WP, so 1528), and the skill file. **Decided 2026-09-30:** R0 and R1 start now as WP-1801 and WP-1802, in the new
  v1.8 block (18xx); 1803 is the seam spike that settles question 1 by
  measurement before any table change. **Adversarial review the same day**
  (against `e3e6486a`): the `vector.py` and `least_squares.py` line numbers in
  #561 are stale (`:1218-1223` is now `:1259-1260`, `:1132-1136` is `:1175-1178`,
  `:1252` is `:1292`, `_within_atom` is `least_squares.py:768`); the traced twin
  cannot use `adp.cartesian_basis` (it calls `np.linalg.cholesky`); the
  zero-rotation derivative is the failure a random test misses; an anchored
  rotation composes where `rebase_anchored_dofs` subtracts; `_structural_column`
  never sees a body column, so R5 buys speed and not correctness; the skill's
  `api.md` headroom is 402 B, not 39 B; DASH is MIT and FOX GPL-2 (this file's
  References say otherwise and are stale); open v1.6 PRs touching shared files
  are #522, #564 and #571, #524 having merged. Amended chunk list: R0 tests at
  zero, near π and the w = 0 tie-break; R1 unexported with declared bonds and
  ideal-D6h benzene; R2 split into the spike (1803) and the chosen seam, sized
  L; R3 sized L and carrying the anchored-rotation kind, tie refusals, `help.py`,
  `gui/src/lib/history.ts` PLACES and the `ParameterRow` field pin; R5 collides
  with WP-1327's analytic moment branch and WP-1419; R6 writes its own det(R)·R
  basis and adds a monoclinic case; R8 freezes the pair list per plan and tests
  at the kink; R11 needs `displace_anchored_dofs` for rotations. R2b onward is
  cut into WPs from 1803's record. **Decided 2026-09-30: v1.6 ships whole** (every rung, 1419 included), so
  every chunk after 1803 that edits `params/vector.py` waits for v1.6 to close. Its companion is #562, under WP-1515.

## What the scoping decides

1. **Where the map lives.** (a) A C that depends on θ, rebuilt from the
   body map's local Jacobian at each evaluation. Every reader of C is kept,
   and "constant during a run" is broken. (b) A nonlinear stage in the
   forward model after C, as the moment does, with coordinate esds
   propagated through the body map's own Jacobian. (c) Whatever the prior
   art does that neither of these is. Measure each against the readers
   above.
2. **The parameterisation.** Quaternion or Euler angles, the body's origin,
   torsions as a Z-matrix or as named rotatable bonds, and a body sitting on
   a special position.
3. **The restraints the milestone needs.** A tether (a maximum distance,
   so an inequality), and planarity for a ring that is not rigid.
4. **Hydrogens** riding on a body, written to the CIF.
5. **Where a fragment comes from.** An ideal template, a CIF fragment, or
   WP-1319's molecular XYZ. SMILES comes later, behind an optional
   dependency.
6. **The public acceptance corpus.** Molecular and MOF structures with
   public powder data and published models.
7. **Placement.** Before, beside or after v1.7, and its relation to 1515's
   milestone.

## Non-goals

- Building any of it. A throwaway spike to measure (1) is allowed, and
  nothing from it merges.
- Global search (1515).

## Tasks

- [ ] Prior art with licences, searching the maintainer-local paper corpus
      first (root CLAUDE.md § Roadmap; its location is in the
      maintainer's memory).
- [ ] Measure the placements in (1) against the readers of C: what each
      changes, and what it does to esd propagation.
- [ ] The public acceptance corpus, with provenance for
      `tests/data/README.md`.
- [ ] The smallest first rung that is useful alone.
- [ ] The milestone draft: WP files, a ROADMAP section with the rows'
      order, and a DESIGN.md entry if a locked decision moves. **Open the
      milestone's WPs in the next unused number block, checked against
      `origin/main` and the open PRs on the day you file.** A sibling
      scoping may be filing at the same time.
- [ ] The maintainer's decision recorded here. This WP closes on it.

## Acceptance

The draft's WP files exist and are self-contained, ROADMAP carries the
queued section, and the index is regenerated. The maintainer's decision on
where the map lives is recorded in this file.

```sh
python3 .claude/hooks/wp_index.py
.venv/bin/python -m pytest tests/test_docs_consistency.py -n auto --dist loadgroup
```

## References

- Coelho, A. A. (2000). *J. Appl. Cryst.* 33, 899–908. Rigid bodies and
  Z-matrices in whole-profile simulated annealing (TOPAS; papers only).
- Coelho, A. A. (2018). *J. Appl. Cryst.* 51, 210–218. TOPAS's
  computer-algebra layer, cited in the `ExtraComponent` contract. Verify the
  pages before quoting them.
- Favre-Nicolin, V. & Černý, R. (2002). *J. Appl. Cryst.* 35, 734–743. FOX
  (licence unverified; papers only until checked).
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544–549.
  GSAS-II (BSD-style; verify its LICENSE before reading code).
- David, W. I. F. et al. (2006). *J. Appl. Cryst.* 39, 910–915. DASH
  (commercial; papers only).

## Handover log

- **2026-09-28** — created as an implementation WP and re-scoped the same
  day into this scoping WP, after the measurement in Context put it at
  milestone size. Nothing started.
