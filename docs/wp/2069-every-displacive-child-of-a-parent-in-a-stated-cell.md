# WP-2069 — Every displacive child of a parent in a stated cell, several irreps included

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1419 soft: `distortion_candidates`, `DistortionCandidate` and the consumer, chunk 4's ranking; 1919 soft: `subgroups.maximal`, the cross-check)
Priority: P3 2026-10-31 — a workaround covers it (ISODISTORT by hand); its consumers, WP-1419's chunk 4 and WP-1418's descent audit, are not built yet

## Goal

Given a parent and a stated child cell, rietx lists every distinct isotropy subgroup the parent can distort into within that cell, each with its group and verified (P, p), the irreps it activates with their mode counts, its free-mode count and its domain counts, so a "which child is it?" ranking has the candidates that need several irreps (Pnma perovskites) as well as the single-irrep ones `distortion_candidates` gives.

## Context

From issue #1225 (mustachefeeling, 2026-10-29), "Kind: machinery" in #1224's sense: it lists and states, never ranks.

**The gap.** `magnetic.isotropy.distortion_candidates(parent, k, sites=None)` (`crystallography/magnetic/isotropy.py:2421`, PR #996) gives the children of one irrep at one k. WP-1419's 2026-10-22 handover: multi-k children are out, because `candidates` intersects no isotropy groups across k. LaMnO₃, CaTiO₃ and GdFeO₃ are Pnma, which needs R4+ and M3+ together (X5+, R5+, M2+ secondary).

**The reporter's method** (all from the literature and rietx's own pieces):
1. L₀ = the largest sublattice of the child lattice the parent's point group keeps (2L at Γ, X, M, R of a cubic parent). Every child fitting the cell maps one-to-one to a subgroup of the finite group G/L₀ (order 384 for Pm-3m over 2L).
2. All subgroups of G/L₀ by cyclic extension (Neubüser 1960), complete because G/L₀ is solvable. Keep T(H) ⊇ child lattice; group into G-conjugacy classes; in-cell conjugates are domains.
3. Mode spaces from #950's `distortion_basis` of each H stated as a child.
4. Isotropy filter: keep H only if a generic displacement in its mode space has exactly H's symmetry (#996's probe, `_PROBE_DRAWS` draws), and equivalently no larger H′ has the same mode space. Both checks run and must agree.
5. Setting as #996: spglib's standard, (P, p) verified exactly.
6. Distinct fits depend on the cell's metric: report both the conjugacy-class count and the metric-distinct count.

**The reporter's spike numbers** (not re-measured here): Pm-3m over 2L has 7 082 subgroups in 1 427 classes, found in 0.2 s (≈ 19 s with mode spaces, both filters and names). 2×2×2, full 117-mode space: 6 546 isotropy subgroups in 1 254 classes. LaMnO₃'s √2×2×√2 (57 modes): 1 199 fit, 970 isotropy subgroups in 543 classes; 741 metric-distinct fits. A walk of maximal subgroups from Pm-3m (p = 2, index ≤ 8) reaches all 1 427 classes in 11 141 steps, none leaving the list. 64 single-irrep directions built only from the cell-keeping operations miss children that fit (R-3c a⁻a⁻a⁻ among them); step 2 finds them.

**What is on main at d87c8cc91.** `distortion_candidates` and `DistortionCandidate` (`isotropy.py:2136`); `representation/distortion.py`'s `distortion_basis`; `representation/subgroups.py`'s `maximal(group, kind, max_index)` (WP-1919's PR #1189), so the reporter's chunk D cross-check is no longer blocked. No multi-irrep enumeration.

**Practice** (recall, labelled as such; `docs/practice.md` has no survey of this): TOPAS, GSAS-II and FullProf enumerate no isotropy subgroups natively. Users take candidate lists from ISODISTORT (Campbell et al. 2006) or Bilbao's tools by hand; GSAS-II offers a route to Bilbao's k-SUBGROUPSMAG (not checked in its source here). Howard & Stokes (1998) list the perovskite tilt systems as isotropy subgroups of R4+ ⊕ M3+. Lewis et al. (2016) refined every candidate of an exhaustive search to choose a child. Licensing: nothing read from ISODISTORT, its output or Bilbao (the reporter says so); papers only.

**Rules to carry.** Every positive control names groups with their (P, p), never counts alone: root CLAUDE.md's Rᵀ trap (a transposed rotation set is a group too, so counts pass). Tier: physics and established method (isotropy subgroups, cyclic extension); `_PROBE_*` constants are #996's and already audited.

**Open questions the reporter leaves to the maintainer** (decide before the first PR):
1. Placement and name: beside `distortion_candidates` in `magnetic/isotropy.py`, or in `representation/`; the function's name (the issue suggests `cell_candidates(parent, cell, *, irreps=None, max_modes=None)`).
2. Return type: `DistortionCandidate` with an irrep list in place of `candidate`, or a sibling type.
3. A default cap: the reporter suggests none, with `max_modes` optional (LaMnO₃: 28 candidates ≤ 1 mode, 149 ≤ 3, 415 ≤ 7, 513 ≤ 10, 670 ≤ 16, 740 ≤ 34, P1 at 57).
4. Reach: displacive modes only first, Biso and occupancy ordering left out.

**Check before starting.** WP-1419's 2026-10-06 entry records that a collaborator is building an ISODISTORT equivalent and asks that the maintainer be consulted before work starts there, so it is not done twice. Confirm whether this proposal is that work.

## Non-goals

- Ranking candidates against each other (WP-1419 chunk 4, the consumer).
- Magnetic (time-reversal) subgroups across several irreps: WP-1418's M-7 owns magnetic isotropy.
- Incommensurate k and superspace (fenced, #258).
- Strain modes and ordering (Biso, occupancy) in the filter, until a consumer needs them.

## Tasks

- [ ] Decide, with the maintainer: placement, name, return type, cap (questions 1-4 above).
- [ ] Chunk A: subgroups of G/L₀ in a stated cell by cyclic extension, conjugacy classes, domains in the cell, verified (P, p).
- [ ] Chunk B: the mode space per class (`distortion_basis`), both isotropy checks agreeing, `irreps=`.
- [ ] Chunk C: Howard & Stokes's 15 tilt systems and the Pnma decomposition as tests; the manual's Theory equations with *Source* lines.
- [ ] Chunk D: every `subgroups.maximal` result fitting the cell appears in the list.
- [ ] Tests: invariants (Σ modes = child's free coordinates; same classes from every parent setting; two extension orders give one list); the negative control (L₀ = L gives `distortion_candidates`' Γ children plus the parent); cost stated for the perovskite cells and one low-symmetry parent.
- [ ] Skill: a row in `references/api-magnetic.md` via the generator; none in the body.

## Acceptance

- Every single-irrep child `distortion_candidates` gives at each k of the cell appears with the same group and mode count.
- `irreps=["R4+", "M3+"]` on Pm-3m in 2×2×2, mode space restricted to the six rigid-tilt components, gives 25 distinct isotropy subgroups (Howard & Stokes 1998, p. 784), of which the 15 with no axis carrying both a + and a − tilt are their Table 1, each named with its group number and (P, p).
- Pnma in √2×2×√2 appears with exactly R4+, M3+, X5+, R5+ and M2+.

```sh
.venv/bin/python -m pytest tests/test_distortion_candidates.py tests/test_subgroups.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Stokes, H. T. & Hatch, D. M. (1988), *Isotropy Subgroups of the 230 Crystallographic Space Groups*, World Scientific.
- Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006), *J. Appl. Cryst.* 39, 607–614, §4.
- Howard, C. J. & Stokes, H. T. (1998), *Acta Cryst.* B54, 782–789.
- Lewis, J. W., Payne, J. L., Evans, I. R., Stokes, H. T., Campbell, B. J. & Evans, J. S. O. (2016), *J. Am. Chem. Soc.* 138, 8031–8042.
- Neubüser, J. (1960), *Numer. Math.* 2, 280–292.
- Issues #1225, #996, #950, #806, #1224, #286, #390.

## Handover log

- **2026-10-31** — created, from the issue triage (issue #1225). No open WP owns it: WP-1419 owns single-irrep `distortion_candidates` and is the consumer, but its scope is refining a stated child on its amplitudes and its handover puts multi-k children out; WP-1919 owns maximal subgroups only, and is the cross-check; WP-1418 owns magnetic isotropy.
