# WP-2085 — A phase in its standardized description: the Parthé–Gelato Γ rule and the standardized CIF

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: #1332 (S0, the setting and the cell)
Priority: P3 2026-11-03 — a workaround covers it (STRUCTURE TIDY or spglib outside the package), and no fit's number depends on it; the public name waits on the maintainer

## Goal

One call takes a `Phase` to the description Parthé & Gelato (1984) define:
the ITA standard setting, a reduced cell, each site at its first-printed form
with the smallest Γ over the Euclidean normaliser, and the atoms in Wyckoff
order. The CIF writer writes that phase with the transform that produced it.

## Context

Issue #1330 (mustachefeeling, 2026-11-02) proposes standardization in four
chunks. This WP takes S1 and S2.

- **S0, the setting and the cell**, is the contributor's open PR #1332:
  `crystallography/setting.py` with `change_basis(phase, P, p)` and
  `standard_setting(phase) → StandardSetting`. It covers the 1984 rules 1 to
  3, the enantiomorph rule and the 1985 monoclinic rule. `_standardise` in
  `representation/subgroups.py` gains the target's Hall number, so origin
  choice 2 is passed explicitly. Its review belongs to `/pr-review`. This WP
  starts from what that PR lands.
- **S1, Γ standardization** (this WP). The first-printed-triplet forms, Γ and
  σ_Γ, and the call itself.
- **S2, the standardized CIF** (this WP). The structure block of the standard
  phase, written through WP-1319's registry and writer, with the change of
  basis recorded.
- **S3, the identity key and `compare(a, b)`**, is folded into
  [1921](1921-the-users-own-structure-database-indexed.md)'s `analogues()`.

**The rules, as printed** (Parthé & Gelato 1984, *Acta Cryst.* A40, 169,
pp. 172–174). Rule 4 is the part S0 does not cover. Each site is moved to the
representative of ITA's first printed triplet form with the smallest
(x² + y² + z²)^½. Among the descriptions the Euclidean normaliser relates,
the one with the smallest Γ = Σ over sites of that distance is chosen. Atoms
are then ordered by Wyckoff letter. STRUCTURE TIDY (Gelato & Parthé 1987,
*J. Appl. Cryst.* 20, 139) adds a 0.25 % listing window and σ_Γ. Γ-minimal
coordinates are discontinuous in the structure (1984, Tables 7–8). Equality
of standardized coordinates therefore never proves two entries the same. That
test is S3's, by comparison with a tolerance.

**Checked against the tree at 62724a30f.** The issue lists the Euclidean
normaliser as new. It is on `main` already.
- `rietx.solve.cluster.equivalences(group, g, *, enantiomers=True)` returns the
  Euclidean normaliser of a group on a metric, modulo the group
  (`Equivalence.elements`, one (P, p) per coset, and `.floating`, the polar
  shifts). It searches unimodular P with entries in {−1, 0, 1} that are
  isometries of the cell, and origin shifts on the 1/24 grid. Its index is
  [N(G) : G] on that metric: 8 for P2₁/c and 16 for P2₁2₁2₁ on a general
  metric, as ITA Part 15 tabulates. It raises `NotImplementedError` where a
  floating direction is not a cell axis (a polar group on rhombohedral axes).
  S0 puts every R group on hexagonal axes first, so S1 should never meet that
  case. Assert it rather than assume it.
- `superspace.generation._normaliser` builds the affine normaliser's
  generators for superspace groups. It is a second implementation of the same
  idea. Reuse `equivalences` for S1, and say in the docstring why the
  superspace one stays separate, or merge them.
- `crystallography/site_classes.py` (the `wyckoff` attribute docstring) records
  that spglib fixes Wyckoff letters only up to the normaliser. Its letter
  for a coordinate appears to differ from the ITA coordinate list in the
  origin-2 settings of `Fd-3m` and `Pn-3m`. The issue's third check of the
  first-triplet table runs against spglib's letters. A disagreement on those
  groups is then expected, so the check must classify it before counting it a
  transcription error.
- Present as the issue states: `indexing.reduce.reduce_cell` and
  `conventional_setting` (WP-1923), `superspace.generation.standard_setting`,
  `representation.subgroups._standardise` and `wyckoff_positions` (#1239),
  `wyckoff.floating_origin_basis`, and the CIF registry under `rietx/io/cif/`
  (WP-1319).

**The first-printed-triplet table.** The form of each Wyckoff position's first
printed triplet is an ITA convention. The group's algebra does not give it.
Im3̄m 6b prints (0, ½, ½), and P4₁32 8c has two triplets of the form x, x, x.
The issue proposes one line per Wyckoff position, transcribed from ITA (2002)
under a transcribe-then-check protocol. It is checked three ways: against the
positions `wyckoff_positions` computes, against the forms a licensed
database's standardized entries use (aggregate counts only), and against
spglib's letters. Whether that table may ship in the wheel is open (Tasks,
second decision).

**Tier.** Rules 1 to 4 are named practice, tier 2, citing the 1984 paper. The
issue proposes one caller argument beyond the paper: hydrogen left out of Γ,
off by default, until TYPIX (Parthé et al. 1993/94) has been read. If TYPIX
states a rule, the default follows it with that citation. Aligning an entry
with its structure type is a judgement and stays out (Non-goals).

**Licensing.** STRUCTURE TIDY and TYPIX are read as papers. spglib and moyopy
run as black-box oracles on results. No library's internal tables are read.
A licensed database contributes aggregate counts only. Nothing from it enters
the repository (CLAUDE.md § Licensing, and the unpublished-data rule).

### Inherited

- **2026-11-03, from the 2026-11-03 issue triage (issue #1330).** PR #1332
  (mustachefeeling, open, not draft) builds S0. Read its final diff before the
  first task here, since its review may move names. Its body reports the
  standard setting's operations and cell matching a licensed database's
  standardized entry on 99.37 % of 139 243 pairs, with every miss classed. That
  figure is the contributor's local run on data this repo cannot hold. Treat it
  as evidence for the PR's review, never as a tolerance here.

## Non-goals

- The setting and the cell (S0): PR #1332.
- Deciding that two entries are the same entry, and the invariant key (S3):
  [1921](1921-the-users-own-structure-database-indexed.md).
- Aligning a structure with its structure type, or choosing a type. Neither
  is machinery.
- The refinement CIF and checkCIF:
  [1933](1933-the-cif-module-beyond-the-structure-block.md). S2 writes a
  structure block that the existing writer already validates.

## Tasks

- [ ] **Decision (maintainer): the public name.** Trigger: it names something
      on the main user surface. The issue proposes `standardize(phase)`. Two
      questions. (a) Does it join the top-level `rx.` namespace, or stay at
      `rietx.crystallography.setting` beside S0's `standard_setting`? (b)
      Which spelling and word? The field's term is Parthé & Gelato's
      "standardization of crystal structure data". spglib calls its
      equivalent `standardize_cell` and pymatgen
      `get_conventional_standard_structure` (both recall, not checked). The
      package's own identifiers mix the two spellings: `normalize_species`
      and `summarize_events` beside `subgroups._standardise` and
      `superspace.generation.standardised`. The top-level namespace has no
      word ending in -ise or -ize yet. Ask before the first commit names it.
- [ ] **Decision (maintainer): whether the first-printed-triplet table may ship
      in the wheel.** Trigger: its crux is a licensing judgement nothing
      written settles. CLAUDE.md § Licensing requires a wheel file to state
      its status where it ships. It does not say whether a table of facts
      transcribed from ITA may ship. The issue cites Bilbao and spglib as
      shipping equivalents (spglib's Wyckoff database, BSD-3; recall, not
      checked). The alternative is to derive the forms at run time from
      `wyckoff_positions` plus a short list of the cases the algebra cannot
      fix. Measure that list's length first, because a short one may make the
      question moot.
- [ ] S1a: the first-triplet forms, as data or as rules per the decision
      above, checked against `wyckoff_positions` on all 230 groups.
- [ ] S1b: Γ and σ_Γ over `solve.cluster.equivalences`, with the hydrogen
      argument, and the call itself under the decided name. Wyckoff order last.
- [ ] S2: the standardized structure block through `rietx/io/cif/`, with the
      change of basis from the input recorded (a `_space_group` transform tag
      if cif_core has one, a comment line if not; check the dictionary).
- [ ] Tests: exact operator sets; |F(hkl)|² invariant under each transform;
      idempotence; Parthé & Gelato's Table 1 (CeCu₂, KHg₂); Gelato & Parthé's
      Nd₂Fe₁₄B set; ITA ch. 3.5's normaliser indices against
      `Equivalence.index`.
- [ ] `_audit` rows for each default (the hydrogen argument; the listing
      window), tier 2 with their citations.
- [ ] Manual: the rule 4 equation in `theory/subgroups.md` beside S0's, with
      its `*Source:*` line.
- [ ] Skill: a reference row for comparing a fit with a database entry
      ("standardize both, then compare under the normaliser"), or "none" if
      S3 carries it.

## Acceptance

Parthé & Gelato's Table 1 and Gelato & Parthé's Nd₂Fe₁₄B set reproduce their
printed standardized coordinates. Standardizing a standardized phase changes
nothing.

```sh
.venv/bin/python -m pytest tests/test_crystallography_setting.py -q
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_manual.py tests/test_audit_table.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Parthé, E.; Gelato, L. M. The standardization of inorganic crystal-structure
  data. *Acta Cryst.* **A40**, 169–183 (1984).
- Parthé, E.; Gelato, L. M. The best unit cell for monoclinic structures
  consistent with b axis unique and cell choice 1 of International Tables for
  Crystallography (1983). *Acta Cryst.* **A41**, 142–151 (1985).
- Gelato, L. M.; Parthé, E. STRUCTURE TIDY: a computer program to standardize
  crystal structure data. *J. Appl. Cryst.* **20**, 139–143 (1987).
- *International Tables for Crystallography* Vol. A (2002), Wyckoff position
  tables; Part 15 (2005) for the Euclidean normalisers.

## Handover log

- **2026-11-03** — created, from the 2026-11-03 issue triage (issue #1330).
  Checked against the tree at 62724a30f: the Euclidean normaliser the issue
  calls new exists as `solve.cluster.equivalences`, and spglib's letters are
  recorded as normaliser-ambiguous in `site_classes.py`. No open WP owns S1 or
  S2: 1933 owns the refinement CIF and checkCIF, and 1921 owns identity across
  sources (S3 folded there). S1 and S2 are one WP because S2 writes what S1
  produces and shares its fixtures. Next: the two maintainer decisions in
  Tasks, then S1a once #1332 has merged.
