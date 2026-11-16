# WP-1813 — fragment I/O: XYZ, Z-matrix write, SMILES behind an extra

Milestone: rigid-bodies · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Depends on: 1802
Priority: P4 2026-10-06 — a fragment can already be built by hand or from a Z-matrix

## Goal

A `Fragment` reads from XYZ, writes as a Z-matrix, and builds from SMILES when an
optional extra is installed. This is chunk R12 of issue #561, sized M.

## Context

- **The XYZ read is this WP's alone** (folded from 1319's 2026-10-09 inherited
  note: 1319 narrowed to #756's CIF writer chunks and gave up its XYZ half). It
  lands on 1802's `Fragment` in `crystallography/fragments.py`, not in `io/`,
  whose readers are pattern readers; molecular XYZ does not collide with the
  `xy`/`.xye` pattern reader.
- Bare XYZ carries element symbols and Cartesian coordinates and nothing else (no
  cell, no bond order, no aromaticity, no symmetry), so a coordinate-only file is
  untrusted for an aromatic or multiple-bond body, and any space group at placement
  is the caller's claim. The `solution case 1` run (1510 has the source,
  2026-09-28) built its ideal aromatic ring and its hydrogens by hand, which is this
  WP's use case.
- Bonds are declared, never perceived from geometry (WP-1319's rule), so an XYZ read
  needs its bonds from somewhere else: the caller declares them.
- **Licensing:** RDKit (BSD-3) only, never OpenBabel (GPL-2). XYZ and the Z-matrix
  are built from their format definitions; no other program's source is opened.
- It touches no v1.6 file.
- The tier of each rule this WP adds: none is a physics threshold or an automatic
  action. The XYZ refusals are format facts. The Z-matrix writer's choice of
  reference atoms is a construction convention (the geometry it encodes is the
  same either way), and it writes an angle as exactly 0° or 180° where the atom
  sits on its reference line within `COLLINEAR_TOL`, the tolerance
  `from_zmatrix` already applies to the same question (its `_audit` row exists).

## Non-goals

- Rebuilding a body from CIF flags (WP-1810's non-goal).

## Tasks

- [x] XYZ read
- [ ] Z-matrix write
- [ ] SMILES behind an extra, with a refusal naming the extra when it is absent
- [ ] Tests (the acceptance below)
- [ ] Skill: a reference row for the new readers

## Acceptance

- Benzene built from SMILES has a planar template.
- An install without the extra refuses, naming the extra.

## References

- Issue #561; PR #596; WP-1319.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
