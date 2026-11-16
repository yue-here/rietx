# WP-1813 — fragment I/O: XYZ, Z-matrix write, SMILES behind an extra

Milestone: rigid-bodies · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Depends on: 1802
Priority: P4 2026-10-06 — a fragment can already be built by hand or from a Z-matrix

## Goal

A `Fragment` reads from XYZ, writes as a Z-matrix, and builds from SMILES when an
optional extra is installed. This is chunk R12 of issue #561, sized M.

## Context

- XYZ lands with WP-1319's structure interchange.
- Bonds are declared, never perceived from geometry (WP-1319's rule), so an XYZ read
  needs its bonds from somewhere else.
- **Licensing:** RDKit (BSD-3) only, never OpenBabel (GPL-2).
- It touches no v1.6 file.

### Inherited

- **2026-10-09, from [1319](1319-structure-interchange.md): the XYZ read is this
  WP's alone.** 1319 narrowed to #756's CIF writer chunks and gave up its XYZ half,
  so "XYZ lands with WP-1319" above no longer holds and 1319 left this file's
  `Depends on:` line. The landing type 1319 was to decide is 1802's `Fragment`.
  Three facts came with it. Bare XYZ carries element symbols and Cartesian
  coordinates and nothing else (no cell, no bond order, no aromaticity), so a
  coordinate-only file is untrusted for an aromatic or multiple-bond body. It
  carries no symmetry either, so any space group at placement is the caller's
  claim. And the `solution case 1` run (1510 has the source, 2026-09-28) built its
  ideal aromatic ring and its hydrogens by hand, which is this WP's use case. No
  XYZ structure reader exists, and molecular XYZ does not collide with the
  `xy`/`.xye` pattern reader.

## Non-goals

- Rebuilding a body from CIF flags (WP-1810's non-goal).

## Tasks

- [ ] XYZ read (with WP-1319)
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
