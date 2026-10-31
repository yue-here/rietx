# WP-2033 — a declared Z or density filters an extinction class's members

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1967 soft, closed: the `ExtinctionPrior` filter this extends; 2030 soft: the formula's Z check in the search)
Priority: P3 2026-10-23 — a workaround covers it: the user drops the groups by hand after the screen, as #935 describes

## Goal

A caller who knows the formula units per cell (Z), or a measured density that
fixes Z through the formula weight and the cell volume, can declare it to the
extinction screen. The screen then removes from each class the space groups
whose site multiplicities cannot hold that content, and names each one removed.
Nothing changes for a caller who declares nothing.

## Context

- **Source.** Issue #935 (2026-10-13) proposed one `restrict=` covering
  `sohncke`, `polar`, `centrosymmetric`, `z` and `density`. WP-1967 built the
  first three as `rx.ExtinctionPrior` through PR #940 (merged 2026-10-17,
  `c93c4213`). The maintainer's 2026-10-14 decision, recorded in 1967's
  Context, split Z and density off as a follow-up outside #940, because they
  need Wyckoff multiplicities, which gemmi does not ship. #935 stays open for
  this half.
- **What the tree has, at `12f459e`.** `ExtinctionPrior`
  (`schemas/indexing.py:2054`) holds three optional booleans, each read off
  the group's operators. Its contract is "a filter, never evidence". It is
  reported as `EXTINCTION_PRIOR_APPLIED` naming every removed group. It never
  enters a ΔBIC. Every class is still fitted, and a class it empties stays in
  the ranking. `crystallography/wyckoff.py` gives the multiplicity of a
  **given** position (`site_constraints(...).multiplicity`, read off
  `symmetry.site_orbit`), but no group's list of available orbit sizes.
  `indexing/diagnostics.py`'s `INDEX_Z_NOT_INTEGER` (WP-1510) already turns a
  formula and a volume into Z for the search, and WP-2030 owns its window.
- **Correction (2026-10-23, the build).** The tree already lists every orbit
  size of a group. `crystallography/site_classes.py` (WP-1997, provisional,
  not exported) derives every Wyckoff position of a group from its
  operators, with exact affine stabilisers on the 1/24 grid, checked against
  spglib on all 564 gemmi settings (`test_every_setting_matches_spglib`). It
  also counts a composition's placements, using a position with no free
  parameter once. This WP reuses it rather than deriving the orbits a second
  time. It adds `site_classes.holds`, which asks the existence question
  without the count, and the check against ITA on one group per crystal
  class.
- **The first decision is what "cannot hold" means.** Each element's count
  per cell, Z × its count in the formula, must be a sum of the group's orbit
  sizes. That test is exact for an ionic solid. A molecular crystal with
  Z′ < 1 needs a molecule on a special position whose site symmetry the
  molecule itself carries. #935's own case is a P2₁ organic salt at Z = 2,
  where P2₁/m would need the molecule on a mirror or an inversion centre. So
  decide between a hard exclusion and a reported, weaker statement for
  Z′ < 1, and record the reason here.

  Decided 2026-10-23: **a hard exclusion only where the atom count fails.**
  A group is removed when some element's atoms per cell, Z × its count in
  the formula, are no sum of the group's orbits. A Wyckoff position with no
  free parameter is one orbit and counts once; one with free parameters can
  be used any number of times. That is exact for an ordered model, and it is
  the only reading made. An element whose formula count is fractional
  (`Cu0.5Au0.5`) declares a shared site and is not counted. The test is per
  element, so it never removes a group an ordered structure can occupy.
  **A Z′ that is not whole is a statement, never an exclusion**: Z′ < 1, and
  also 3/2 and the like, wherever Z is not a whole multiple of a member's
  general multiplicity. The member stays, and
  `ExtinctionCandidate.special_positions` names the special positions a
  formula unit then needs, with their site symmetries. The reason: a
  molecule on a special position must carry that symmetry, and neither the
  molecule's symmetry nor whether the formula unit is one molecule is
  declared. The atom count cannot see either. #935's P2₁ salt at Z = 2
  therefore keeps P2₁/m, which needs each formula unit on −1 (2a–2d) or m
  (2e). A declared density fixes Z = ρ·V·N_A / M on the screened cell. It
  must lie within `Z_INTEGER_TOLERANCE` (8 %) of the declared `z`, or, with
  no `z`, of exactly one whole number. Otherwise Z filters nothing and
  `best_or_none` abstains. Proposed on #1129, for the maintainer's review.
- **Rules that bind the work** (from 1967): each fact is read off the group's
  operators, never a table. `INDEXING_THRESHOLDS_VERSION` bumps when an
  answer can move. A new diagnostic code needs its skill row and its
  `rietx._audit` row with a tier.

### Inherited

- 2026-10-26 issue triage: #1129 is the outside contributor's (mustachefeeling) claim on this WP, in PR #1140. Its plan proposes a hard exclusion only for the exact atom-count test, with the molecular Z′ < 1 case reported and left in. Checked against the tree at c0e32ab29: status ⬜, nothing merged.

## Non-goals

- The search's volume window and its Z check (WP-2030).
- Carrying the declaration on to `IndexingResult` or
  `structure_from_candidate` (1967's decision 3 holds).

## Tasks

- [x] Every Wyckoff orbit size of a group, derived from its operators (the
      site orbits of the special positions plus the general position), held
      against ITA's multiplicities on one group per crystal class.
- [x] Decide the Z′ < 1 rule (Context) and record it here as
      `Decided YYYY-MM-DD:`.
- [x] `ExtinctionPrior` gains `z` and `density` (with the formula `density`
      needs). They are validated against each other where both are given,
      filtered as the other three are, and reported under
      `EXTINCTION_PRIOR_APPLIED`.
- [x] Tests: #935's P2₁ case, an ionic case where Z excludes a group outright,
      and every extinction screen in the tree unchanged with nothing
      declared.
- [x] Skill and audit rows for any new code or field. The manual's extinction
      page names the two new fields.

## Acceptance

A declared Z removes only groups whose orbits cannot hold the declared
content, and names each one. A declaration the data contradict ends in an
abstention, never in the declared answer. With nothing declared, every
extinction screen answers as on `main`.

```sh
.venv/bin/python -m pytest tests/test_extinction_prior.py tests/test_extinction_symbol.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #935; PR #940; [WP-1967](1967-what-the-chemist-declares-reaches-the-extinction-screen.md).
- *International Tables for Crystallography* Vol. A, the Wyckoff positions
  (the multiplicities the derived orbits are checked against).

## Handover log

- **2026-10-23** — created by WP-1967's close, on the maintainer's decision to
  close 1967 and file this half on its own. No open WP owns a declared Z for
  the extinction screen. 2030 holds Z in the search, not the screen. 1910
  holds the screen at a small cell error.
- **2026-10-23** — built on `wp2033/declared-z-filter` by @mustachefeeling
  (claimed on #1129), one commit off `main`. All five tasks are done.
  `ExtinctionPrior` gains `z`, `density` and `formula`;
  `ExtinctionCandidate` gains `exclusion_reasons` and `special_positions`;
  `ExtinctionScreen` gains `z`, `z_from_density` and
  `density_contradicts_z()`. `indexing/extinction.py` gains
  `content_exclusion`, `special_site_note`, `declared_z` and
  `exclusion_reasons` (which `admits` now reads), and `crystallography`
  gains `site_classes.holds` and `atomic_volume.formula_counts`. One
  `_audit` row is added, `N_A_CM3_PER_A3` at tier 1. There is no new
  diagnostic code, and `INDEXING_THRESHOLDS_VERSION` stays at 1.12 with an
  "Also 1.12" note.
  *ITA*: 32 groups, one per crystal class, 247 positions. Letters,
  multiplicities and site symmetries all agree with the derivation, read
  from the held Vol. A 5th-ed. page images; the pages are cited in
  `tests/test_site_classes.py`.
  *Open for the maintainer*: a density-specific tolerance (8 % is borrowed
  from the Hofmann-volume check); the per-element test against the stronger
  joint one (`site_assignments`); and the disorder convention.
  *Gate*: fast suite on the final tree, on a Mac, `-n 4 --dist loadgroup`:
  11 333 passed, 265 skipped, 27 xfailed, 0 failed (`--junitxml`: 11 625
  tests, 292 skipped, 0 failures, 0 errors).
