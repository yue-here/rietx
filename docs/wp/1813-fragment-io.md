# WP-1813 — fragment I/O: XYZ, Z-matrix write, SMILES behind an extra

Milestone: rigid-bodies · Status: 🔄 2026-11-16 — XYZ read and Z-matrix write landed (#1610); SMILES waits on a dependency ruling (#1617)
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
  same either way, though WP-1814 makes it matter: see its `### Inherited`), and it
  writes an angle as exactly 0° or 180° where the atom sits on its reference line
  within `COLLINEAR_TOL`, moving it by at most r·1e-6 Å. That constant's row is still
  `unaudited`, and `from_zmatrix` asks it of a different triple (B, C, D) and refuses
  rather than moves, so this is a second use, handed to WP-2006 to tier. The XYZ
  element spelling and token grammar are format facts (tier 1).

## Non-goals

- Rebuilding a body from CIF flags (WP-1810's non-goal).

## Tasks

- [x] XYZ read
- [x] Z-matrix write
- [ ] SMILES behind an extra, with a refusal naming the extra when it is absent
- [ ] Tests (the acceptance below)
- [ ] Skill: a reference row for the new readers

## Acceptance

- Benzene built from SMILES has a planar template.
- An install without the extra refuses, naming the extra.

## References

- Issue #561; PR #596; WP-1319.

## Handover log

- **2026-11-16** — A rigid-body template can now be read from a bare XYZ file, with
  its bonds declared by the caller, and written back out as a Z-matrix that rebuilds
  it exactly, mirror image excluded. The SMILES route is not started: it adds RDKit as
  an optional extra, a dependency decision that is the maintainer's, and the WP's
  acceptance and its skill row hang on it or on an export that does not exist yet.
  PR #1610; the leftovers are issue #1617.
  - *Done.* `fragments.from_xyz` / `read_xyz` (one bare frame; elements as symbols in
    any case or atomic numbers, stored in standard spelling; plain decimals only;
    refusals by file and line; CRLF and BOM read). `fragments.to_zmatrix` (lines in
    `from_zmatrix`'s form; references the caller's or chosen: b bonded-then-nearest,
    (c, d) the best-conditioned pair; on-line atoms written at exactly 0°/180°).
    Inherited pruned into Context (1319 gave up its XYZ half; the read lands beside
    `Fragment`, not in `io/`). Premise checked against main bc77a934e: no XYZ structure
    reader and no Z-matrix writer existed.
  - *Not done, and why.* SMILES (dependency ruling); "Tests (the acceptance)" (both
    acceptance lines are SMILES; the XYZ and Z-matrix tests landed with their code);
    "Skill row" (nothing in `fragments` or `bodies` is exported, and the skill's API
    pages are generated from `rx.`). All three in #1617.
  - *Measured.* `tests/test_fragments.py` 56 passed, 31 more than main's 25 (worktree
    `.venv` `[dev]`, macOS arm64). Workstation canary (5 files, `-n 4`): admitted
    `running=1`, commit and tree `rietx.__file__` printed, 151 passed, 69 s, 435 MB,
    154 % on 4 cores. Workstation fast run on 374da3acc (`-n 4 --dist loadgroup -m "not slow"`, the workstation's
    `rietx-py312` venv with the tree on `PYTHONPATH`, Linux x86_64, beside other jobs):
    14881 passed, 280 skipped, 32 xfailed, 0 failed in 1604 s, 6.1 GB, 391 % on 4
    cores; the `-n 8` try was never admitted (co-tenant CPU cap) and was stopped. The
    added tests cost 0.15 s in all (junit, `tests.added_test_times`). No main control
    run: the change moves no measured number. `python -m tests.reader_output`:
    exit 0, unchanged. Positive control: flipping the writer's dihedral sign fails 3
    tests.
  - *Review* (read-only agent, high effort). One narrow bug fixed: the first
    acceptable dihedral reference could be a triple barely off its line, which a
    0°/180° write's ~1e-6 Å move turned by O(1), 0.22 Å in the distances; the
    chooser now takes the best-conditioned pair (regression test added). XYZ
    hardening taken: labels and `X` refused, `nan`/`inf`/`1_0`/`1.0D0` refused,
    ASCII-only digits, `\n` line ends, `utf-8-sig`, a `None` reference a
    `ValueError`. Nothing declined.
  - *Generality* (judge, unedited verdicts in brief): XYZ element spelling **holds**;
    `_DIGITS`/`_DECIMAL` **hold**; the reference chooser **weak** (prospective: once
    WP-1814 refines internals the choice decides which torsion an esd is about;
    author's answer: written into 1814's `### Inherited` as that WP's question); the
    0°/180° write **weak** (its ground was wrong: `COLLINEAR_TOL` is still
    `unaudited`, and this is a second use; author's answer: Context corrected, handed
    to WP-2006's `### Inherited` to tier).
  - *Gotchas.* `str.splitlines` splits on `\f`, `\v` and `\x85`, which can sit in an
    XYZ comment line; the reader splits on `\n`. Python's `float` reads `nan`, `inf`
    and `1_0`, hence the decimal grammar.
  - *Next:* the maintainer rules on RDKit as an extra (#1617). If yes, add the extra,
    `from_smiles` with the refusal naming it, and the two acceptance tests; then the
    skill row lands with whatever WP exports the rigid-body API.
- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
