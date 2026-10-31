# WP-1919 — maximal subgroups, their conjugacy classes, (P, p) and Wyckoff splittings, generated from the group's own operators

Milestone: unscheduled · Status: 🔄 2026-10-30 — PR 1 of 2 (the generator) merged from outside as PR #1189 (`20e33524`); Wyckoff positions and `wyckoff_splitting` (PR 2) are open
Track: Data and metadata in, a structure out
Depends on: — (1419 soft: the symmetry package its front half creates)
Priority: P3 2026-10-08 — a workaround covers it: MAXSUB and WYCKSPLIT by hand; its three consumers (1515, 1418, 1419) are queued or have a narrower stand-in

## Goal

`subgroups.maximal(group, ...)` returns every maximal t- and k-subgroup of a
space group up to index 4, and any isomorphic subgroup on demand, each with
its conjugacy class, its (P, p) to the standard setting verified exactly, and
`subgroups.wyckoff_splitting(group, sub)`. Nothing is read from a printed or
online table.

## Context

From issue #806 (mustachefeeling, 2026-10-07), with a working prototype on
the reporter's side. Three open threads need the group-subgroup step:

- #677 step 7 (folded into WP-1515): each maximal subgroup of the leading
  group is warm-started from the leader's solution, the pattern of the
  magnetic descent audit.
- #390 (WP-1418): that audit, `strategy/magnetic.py:1106`
  `_maximal_subgroups`, is maximal only among the other classes enumerated at
  the winner's own k. Its docstring says so.
- #418 (WP-1419's front half): a child group with its (P, p) for a
  displacive candidate.

Users building Bärnighausen trees go to Bilbao's MAXSUB and WYCKSPLIT by
hand today. The ITA A1 tables (2011) are not redistributable, and the
servers are not for automated use.

**The method**, all from ITA A1 ch. 1.2-1.7, 2.1 and 3.1, restated because it
decides the tests:

- Maximal subgroups are t or k (Hermann's theorem, A1 Lemma 1.2.8.1.3).
- t-subgroups correspond to maximal subgroups of the point group, since
  H/T ≤ G/T ≅ P. Conjugacy in G acts on G/T as conjugation in P.
- k-subgroups keep the point group on a P-invariant sublattice L' < L. H is
  maximal exactly when L/L' is an irreducible F_p[P]-module, so pL ⊆ L' and
  the index is p, p² or p³ (A1 Lemma 1.2.8.2.1). For each prime, the maximal
  P-invariant subspaces of F_p³ give L' = pL + U. The subgroups on one L' are
  the complements of L/L' in G/L', whose translation shifts solve a linear
  system over F_p. Every solution is one subgroup, so the list is complete
  by construction.
- Conjugacy classes: closure under G's generators and lattice translations.
- (P, p): spglib (BSD-3) identifies a probe structure's type and returns a
  transformation, then P⁻¹HP is checked exactly against the Hall-database
  group. A1 fixes one (P, p) of the set the affine normaliser relates; the
  proposal documents its own choice rule.
- Wyckoff positions from operators alone, as stabiliser-conjugacy classes
  (1731 over the 230 groups, ITA's total). A splitting decomposes the
  G-orbit of a generic point into H-orbits, mapped by (P, p). Letters come
  from spglib, as `wyckoff.site_constraints` (`crystallography/wyckoff.py:199`)
  does. A1 3.1.1.6.5 warns that another (P, p) permutes labels within a
  Wyckoff set, so the labels are stated as belonging to the chosen (P, p).
- Index ≤ 4 eagerly, which covers every non-isomorphic maximal subgroup
  (A1 Lemma 1.2.8.2.2). Isomorphic subgroups are infinite in number
  (A1 2.1.5) and come on demand, for an index, a prime or a supercell.

**The prototype's validation**, the reporter's: index ≤ 9 over all 230 types,
about 9300 maximal subgroups, each standardised exactly onto its Hall-database
group; closed-form isomorphic-series counts for P1 (p² + p + 1), P-1, P2,
P2/m, P4, P4/m, P3, P-3, P-6, P222 and Pmmm; every generated subgroup
re-derived from its (standard group, P, p) and checked as a subgroup and as
maximal, with the maximality test held to known non-maximal cases (P4 with
2a, 2b; P4 with 5a, 5b); multiplicity conservation Σ m_H = m_G·|det P| on
every splitting row; identical subgroup multisets across origin choices,
unique axes, cell choices, hexagonal and rhombohedral axes, and Cmce against
Ccmb. Cost: exact `Fraction` arithmetic, 13 CPU-minutes for all 230 groups
at index ≤ 9, at most 23 s for one group.

**Rules that apply.** The Rᵀ trap (root CLAUDE.md § Invariants): a
transposed rotation set is a group too, so every count passes under the
wrong action. The tests here assert that a named subgroup is present with
its (P, p), never only how many there are. Settings follow the space-group
setting, never the crystal system (`cell_constraints`'s rule).

**Licensing.** Concepts from ITA A1's text; no table is transcribed. spglib
is BSD-3 and already a dependency. Bilbao's servers are neither a source nor
an automated oracle; a published A1 entry may be quoted in a test as a
literature value. moyo (#426, WP-1452) would replace only the
identification call.

### Inherited

- **2026-10-31, from [WP-2065](2065-a-hung-fast-job-names-its-test.md) (issue
  #1249): a full k-series at P −1 costs p(p² + p + 1) subgroups, so its
  P −1 rows are now `slow`.** `maximal("P -1", index=53, kind="k")` returns
  151 739 subgroups, and with the test's `is_maximal` per result it took
  629-812 s of a CI runner. Alone it could outrun the fast job's 40-min cap,
  and it did, 8 times between 30 and 31 Oct. `2c2e23666` (PR #1254) marked
  both P −1 rows `slow`; the hexagonal p = 29 rows keep the bound covered per
  push, raising in seconds under the old floor of 48. A new row asking a
  per-subgroup question at a large p uses `supercell=`, p subgroups rather than
  p³. Measured and declined: `_maximal_invariant`'s pairwise row reductions
  cost 1.45 s at p = 29, so a faster exact rule (a line is maximal unless an
  invariant plane holds it) buys about 1 s there.

- **2026-10-11, from the issue triage (#806): the placement question has a
  partial answer.** PR #842 (WP-1419 C0a, merged 2026-10-08) created
  `crystallography/representation/` with `irreps.py` and `modes.py`, and
  WP-1419's handover says C0b and this WP's generator land beside them. So
  the "symmetry package WP-1419 creates" is `representation`. Checked against
  the tree at 7d9be3cb: no subgroup code there; the only maximal-subgroup code
  is `strategy/magnetic.py:1106` `_maximal_subgroups`, maximal among the
  classes at the winner's k.
- **2026-10-26, from the issue triage (#806): the reporter proposed answers to
  the three decisions and offered to build the WP from the prototype.** Their
  last comment (13:59) supersedes the two before it, which are one text posted
  twice. (1) Placement: `crystallography/representation/subgroups.py`. (2) The
  (P, p) rule: the one `distortion_candidates` already uses, so one group never
  gets two (P, p) in the package: r_parent = P·r_child + p, the standard setting
  spglib returns, each operation checked against the group. Tests compare up to
  the affine normaliser, and Wyckoff labels are stated as belonging to that
  (P, p). (3) Exact `Fraction` arithmetic first, with the 230-group sweep as a
  `slow` test. A fourth consumer: the active-modes work on #286 wants to rank a
  parent's subgroups down to the child cell, which means walking down from the
  maximal ones. Checked against the tree at `6eb010a0f`. `representation/` holds
  `distortion.py` (#950), `irreps.py`, `modes.py` and `order_parameter.py`, and
  no subgroup code. The (P, p) rule is `magnetic/isotropy.py`'s
  `_standard_child`, which `distortion_candidates` calls, not a function in
  `representation/`. Its operation check is in floats: P and p are
  rationalised with `limit_denominator(48)` and compared to 1e-6. It is not
  the exact check this WP's Goal names. `Fraction` is the arithmetic of
  `wyckoff._nullspace_int` and of `magnetic/isotropy.py`. The prototype's
  13 CPU-minutes and 23 s are the reporter's and were not re-run. The decisions
  stay open until the maintainer answers. Read against `docs/DESIGN.md`
  § Rules, the proposals leave three gaps. Rule 4 (a new output) wants the
  splitting result to carry the (P, p) its labels belong to, and the sketch's
  `{"4a": ["2a", "2d"]}` drops it. Rule 2 wants the method and its source
  stated: the (P, p) is spglib's standardisation and can move with spglib or
  moyo. Rule 4 (a new topic) wants the reference named before the code: the
  Tests task's "stated set of named maximal subgroups" is not yet stated.

## Non-goals

- Magnetic subgroups (time reversal): M-7's isotropy subgroups, WP-1418.
  A magnetic descent may consume this list through its nuclear part.
- Minimal supergroups and the upward direction of #677's audit.
- Moving `irreps.py`, `modes.py` and `isotropy.py` into a symmetry package:
  WP-1419's front half (#418, decided 2026-09-23).
- The spglib-to-moyo migration: WP-1452.

## Tasks

- [x] **Decision (maintainer):** placement. Under the symmetry package
      WP-1419 creates, or under `crystallography/` now (#806 question 1).
      Decided 2026-10-26: `crystallography/representation/subgroups.py`.
- [x] **Decision (maintainer):** the (P, p) choice rule. A1-identical where
      it can be reproduced, or a documented canonical choice (#806
      question 2). Decided 2026-10-26: the rule `distortion_candidates`
      uses (r_parent = P·r_child + p, spglib's standard setting), with three
      conditions. The operation check is exact, and `_standard_child` later
      calls it, so the package keeps one standardiser. The splitting result
      carries the (P, p) its labels belong to (a typed result, never a bare
      dict). The docs say the (P, p) is spglib's and can move with spglib or
      moyo. Tests compare up to the affine normaliser.
- [x] **Decision (maintainer):** exact `Fraction` arithmetic as the prototype
      has it, or an integer implementation the reporter estimates at about
      10× faster (#806 question 4). Decided 2026-10-26: exact `Fraction`. The
      `slow` test is the index ≤ 4 acceptance sweep, parametrised per group;
      the index ≤ 9 sweep is a benchmark script outside the suite. Before the
      code, the PR names the reference set the Tests task calls "stated":
      the groups, the published entries and the tolerance (DESIGN Rule 4).
- [x] t-subgroups from the point group's maximal subgroups, with conjugacy
- [x] k-subgroups: maximal P-invariant sublattices per prime, complements
      over F_p, conjugacy classes
- [x] (P, p) to the standard setting, verified exactly against the
      Hall-database group
- [ ] Wyckoff positions from operators, and `wyckoff_splitting`
- [x] Isomorphic subgroups on demand (`index=`, `supercell=`)
- [ ] Tests: the closed-form series counts; a stated set of named maximal
      subgroups each present with its (P, p); the non-maximal controls;
      multiplicity conservation; the setting-invariance multisets; the 1731
      total. The full 230-group index ≤ 9 sweep as a `slow` test or a
      benchmark, as its cost decides
- [x] Manual Part 2: the t/k construction and the F_p reduction with
      *Source* lines (ITA A1)
- [ ] Skill: none at first, since no fit reaches it until a consumer WP
      calls it; a row in the consumer's reference file when one does

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_subgroups.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

- Every maximal subgroup of index ≤ 4 of all 230 types standardises exactly
  onto its Hall-database group.
- The isomorphic-series counts match their closed forms for the listed
  groups and primes up to a stated bound.
- P4 with 2a, 2b and P4 with 5a, 5b are reported non-maximal.
- Σ m_H = m_G·|det P| holds on every splitting row.
- Two settings of one type give the same subgroup multiset.

## References

- Issue #806; #677 (WP-1515), #390 (WP-1418), #418 (WP-1419), #426 (WP-1452).
- *International Tables for Crystallography* Vol. A1, 2nd ed. (2011), ed.
  Wondratschek & Müller: ch. 1.2-1.7, 2.1, 3.1.
- Togo, A. et al., spglib (BSD-3).

## Handover log

- **2026-10-31** (`/pr-review`) — the `_standard_child` switch merged from outside as PR #1248 (`e28c8c52`) after one round. It is the item the 2026-10-30 entry listed as open for PR 2, and the third condition of the 2026-10-26 ruling on the (P, p) rule ("`_standard_child` later calls it, so the package keeps one standardiser"). `_standard_child` in `magnetic/isotropy.py` now takes the candidate's colourless operator list in the magnetic cell as H and reads its setting through `subgroups._exact_setting`, the body `_standardise` had, moved out. `_from_pairs` is the exact builder `_from_operations` now delegates to. The `limit_denominator(48)` and the 1e-6 float element check are gone. The parent-atom probe, its three draws, its refusals and the spglib call stay in `_standard_child`. This is a unification. No input was found where the two routes disagree. On the suite's cases, 1 728 calls give identical symbols and (P, p). Over the 230 types with one k per star, 4 940 calls reach the same outcome, 1 318 raising identically, and the 3 622 stated children have the same rationals, with 60 differing in the last bit of p. Main computes p as `float(Fraction) % 1.0` and the exact route reduces the `Fraction` first, so p reads 0.3333333333333333 where main gave 0.33333333333333337. The maximal subgroups of index ≤ 4 (3 767) and 177 073 isomorphic-series cases give the same subgroup. `maximal()` over the 230 types has an identical sha256 of every `repr`. One behaviour change is never reached: a P under which some W of H is not integral raises the same `RuntimeError` in place of `_NotIntegral`. `test_every_child_is_the_subgroup_mains_float_route_named` holds all 43 children the suite states against main's results captured from a pristine tree, with the I4/mcm tilt at an origin half a cell off as the positive arm. `test_the_child_setting_is_read_by_the_subgroups_standardiser` spies on `_exact_setting` for the 12 children at M and refuses an origin moved by a quarter of a. With main's `isotropy.py` restored the second fails. `_standard_child` costs ×1.30 per call on the suite's cases (7.81 s to 10.19 s) and ×1.16 on the 230-type sweep (26.2 s to 30.5 s). No audit row changed. `_PROBE_DENOMINATOR_FLOOR` holds at the new call site, where the bound is max(48, 12·index) and 48 binds only at index ≤ 4. Follow-up, not blocking: that row names the t-subgroup case only, and one clause naming the isotropy call site and its test would let a reader find both uses. Found while searching, not changed here: `distortion_candidates` raises "a candidate operation does not map the parent's atoms onto themselves in the magnetic cell; this is a bug" for every centred parent, 1 318 of 1 318 calls on I, F, C, A and R parents (rocksalt `F m -3m` at Γ and L, for one). The probe lists a centred parent's positions in duplicate, and with the duplicates removed both routes state every child identically. Fixing it changes what the function returns, so it is not part of the unification. The contributor said an issue follows. No task is ticked, since the switch has no line of its own in the list. Open for the WP: Wyckoff positions and `wyckoff_splitting` (PR #1239, open, which `git merge-tree` shows merging with #1248 without a conflict in either order), the rest of the Tests task and the skill line. Gate (the six PRs of this round merged together onto main `766c3505d`; macOS arm64, `[dev,jax]`, Python 3.12): fast 12 884 passed, 223 skipped, 32 xfailed; slow 435 passed, 18 skipped, 16 xfailed, with one GUI-boot socket timeout under load that passed alone in 5 s; ruff and the `-W` manual build clean.

- **2026-10-30** (`/pr-review`) — PR 1 of 2, the generator, merged from outside as PR #1189 (`20e33524`) after three rounds. `crystallography/representation/subgroups.py` gives `maximal(group, kind, max_index=MAX_INDEX, *, index, supercell)` and `is_maximal(group, symbol, transform)`. Each `MaximalSubgroup` carries its (P, p) checked in exact `Fraction` arithmetic, its class and its class size. The reference set the ruling asked for is 17 ITA A1 entries read off the page, each compared up to the affine normaliser and found exactly once. The negative arm is Pnma → P2₁2₁2₁ with its origin shift dropped, which `is_maximal` refuses. The review re-ran the reproductions on the final head: p subgroups of `P -1` at p = 5, 13, 29 and 31, and 841 for `P 6/m m m` at 29a × 29b. The per-group index ≤ 4 sweep (3767 subgroups, about 20 CPU-s) stayed in the fast suite, which departs from the ruling that it be `slow`: it takes about 11 s at `-n 4`, and one decorator moves it. The index ≤ 9 sweep is `tests/subgroups_benchmark.py` (9291 subgroups, 45 CPU-s). `_PROBE_DENOMINATOR_PER_INDEX` = 12 is recorded as `invariant`, and the judge reads it as a sufficiency bound that tier 1 would fit as well. Two-origin types come out in spglib's origin choice 1 where A1 uses choice 2, so the tests compare up to the normaliser. Ticked: t- and k-subgroups, (P, p), isomorphic subgroups, Manual Part 2. Open for PR 2: Wyckoff positions and `wyckoff_splitting`, multiplicity conservation and the 1731 total (the rest of the Tests task), and switching `_standard_child` to the exact check. Gate (a stack of eleven PRs on main `b40bc994`, tree `307eff83`; macOS arm64, `[dev,jax]`, Python 3.12): 13 217 passed, 216 skipped, 48 xfailed, 0 failed, with ruff, the `-W` manual build and the GUI ladder green.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #806).
  Checked against the tree at `5d1f5f67`: no maximal-subgroup enumeration
  exists in `src/`; `_maximal_subgroups` (`strategy/magnetic.py:1106`) is
  maximal only among the classes found at the winner's k, as its docstring
  says; `wyckoff.site_constraints` takes letters from spglib; no symmetry
  package exists yet, since WP-1419 has not started. The prototype's counts
  are the reporter's and were not re-run. No open WP owns it: WP-1419 owns
  the package move and `distortion_candidates`, which take a child group from
  an irrep direction rather than enumerating subgroups; WP-1418's audit and
  WP-1515's #677 step 7 consume the list and do not build it.
