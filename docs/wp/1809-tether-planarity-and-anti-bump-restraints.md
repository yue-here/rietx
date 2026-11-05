# WP-1809 — Tether, planarity and anti-bump restraints, pairs frozen per plan

Milestone: rigid-bodies · Status: ✅ 2026-11-01 — planarity and RESTRAINT_PAIRS_STALE merged from outside as PR #995, their follow-ups as PR #1222; the radii question is ruled (caller-stated minimum stays)
Depends on: —

## Goal

Three restraint kinds join `Bond`/`Angle`/`Value`: a one-sided maximum distance (the
tether), a planarity term, and anti-bump over a candidate pair list. This is chunk R8 of
issue #561, sized M. It needs no body.

## Context

- It builds on the shipped restraint seam (WP-0406, WP-1074) and on nothing in this
  milestone.
- The `Restraint` union grows, so SCHEMA bumps.
- **The anti-bump pair list is frozen at plan compile**, from pairs within r₀ + a
  margin (the record, [`docs/DESIGN.md` § Parameter system](../DESIGN.md#parameter-system)).
  Its rows exist for the whole plan, zero inside the one-sided term. A per-stage rebuild
  would move the restraint row count that `rows.layout`, WP-1074's per-stage c_w and the
  stage-boundary Jacobian test assume constant. A plan-end `RESTRAINT_PAIRS_STALE`
  diagnostic names pairs that entered r₀ from outside the list.
- An outside branch (`3b333db0`, on #561, 2026-10-06) has the caller build the list
  into explicit rows instead of the engine freezing it at plan compile. That departs
  from the record. If it is kept, ask the maintainer first. It was kept: the
  2026-10-12 handover entry records the decision, and it supersedes the bullet above.
- The pair-list builder uses the minimum-image shift from PR #778 (merged), so the list
  does not depend on which cell an atom is stored in.
- It may land as two PRs: tether and anti-bump first, then planarity and the stale-pairs
  diagnostic.


## Non-goals

- Restraints across a body under the live cell, beyond what these tests cover.

## Tasks

- [x] Tether and anti-bump rows; the pair-list builder (built by the caller, #888)
- [x] Planarity rows; `RESTRAINT_PAIRS_STALE` at plan end (PRs #995, #1222)
- [x] Manual Part 2 equations for the new kinds (`docs/docs/theory/parameterisation.md`, § Soft restraints)
- [x] Tests (the acceptance below) (`tests/test_one_sided_restraints.py`, `tests/test_planarity_restraints.py`)
- [x] Skill: a reference row for `RESTRAINT_PAIRS_STALE` (`references/diagnostics.md`, brought up to date 2026-10-31)

## Acceptance

- The tether row is zero inside and has slope 1/σ outside.
- Analytic against FD < 5e-3 for each kind, tested *at the kink* and on both sides.
- Rwp is bit-identical to the no-row statistics.
- The restraint row count is constant across a plan's stages.
- The pair list is complete against an exhaustive search and independent of the stored
  cell.
- A pair that enters r₀ from outside the list is named.

## References

- Issue #561; PR #596; issue #777 and PR #778 (the minimum-image shift).

## Handover log

- **2026-11-01** (close, ghostshift batch, PR #1287) — closed. Tether, anti-bump and planarity restraints are all in, and a contact that comes inside its minimum from outside the pair list is named at the end of a plan (`RESTRAINT_PAIRS_STALE`). Ruled by the maintainer 2026-11-01: the anti-bump builder keeps the caller-stated minimum as the settled design; a radii-backed default stays a later convenience, whose home is WP-1515 (which already names these radii for its clash floor). One line pointing at this ruling is in WP-1515's `### Inherited`; no session holds it.
  *Done*: every task was ticked on 2026-10-31 (PRs #888, #995, #1222; the skill row and its three copies brought up to date that day, and the 42 passed there are the acceptance run). This session closed the bookkeeping: ✅, `Priority:` and the consumed `### Inherited` section deleted, narrative moved to the v1.11 record. The other Inherited notes were answered earlier: `api-bodies.md` was not created, the restraint kinds' verbs are left to WP-1812's index, the planarity form is the distance-to-plane form, and an atom in two bodies is refused by name.
  *What it does not do*: `test_planarity_rows_leave_the_data_statistics_bit_identical` still does not declare the compiled path, a #1222 review nit that was not asked to block. It asserts bit-identity between two builds in one process, so the path cannot differ between its two sides.
  *Release*: none owed (P3).

- **2026-10-31** (ghostshift close-batch, PR #1287, not closed) — every task is done and ticked, and the skill row that PR #1222's review left open is brought up to date. One decision inherited from the issue triage is still the maintainer's, so the WP stays open. The question: should the anti-bump pair-list builder read minimum distances from the radii tables now on main (Shannon, Pyykkö and Pauling, in `crystallography/radii.py`, landed through PR #1016), and say which pairs got no row? Today `anti_bump_restraints` takes the caller's number, a species-pair mapping or a callable, and a pair with no stated minimum gets no row. The 2026-10-12 entry called reading the radii "still this WP's decision" and nothing since answers it.
  *Done* (each checked against the tree): planarity rows and `RESTRAINT_PAIRS_STALE` (PRs #995, #1222; `tests/test_planarity_restraints.py`); the Theory-tab equations (`docs/docs/theory/parameterisation.md`, § Soft restraints); the tests. `tests/test_one_sided_restraints.py` and `tests/test_planarity_restraints.py`: 42 passed, 2 warnings (`-m "not slow"`, macOS arm64, worktree `.venv` `[dev]`, Python 3.12, alone). The skill row: `references/diagnostics.md` now says the level drops to `info` under `summary(deliverable=…)` of `cell`, `phase_id`, `microstructure` or `calibration` (the `scope` of `("qpa", "structure", "magnetic")` in `_audit.py`, applied by `schemas.results.level_under`), and gives both remedies the code's suggestion gives, rebuild the list or lower a real contact's minimum. The three committed copies were re-synced with `rietx skill --install . --copy`.
  *Resolved from Inherited*: the 2026-10-11 note that this WP's PR may create `api-bodies.md` was answered the other way. `docs/skill/make_api_index.py` elides the three restraint kinds from the everyday index and leaves their verbs to WP-1812's own index, with no raised cap. The planarity form (#759 § 3 (a)) is built as the distance-to-plane form. Amendment (c), an atom in two bodies refused by name, is built (`RIGID_BODY_SHARED_ATOM`).
  *Left*: (1) the radii decision above. (2) `test_planarity_rows_leave_the_data_statistics_bit_identical` does not declare the compiled path (`compiled.set_enabled`), a review nit from #1222 that was not asked to block. It asserts bit-identity between two builds in one process, so the path cannot differ between its two sides.
  *Next*: the maintainer rules on the radii question. Two readings: (a) close with the caller's own minimum as the settled design, and record that radii stay a later convenience; (b) add a radii-backed default to the builder first. The first needs one sentence in this WP, then the close (the v1.11 record's narrative, ✅, delete `Priority:` and `### Inherited`).

- **2026-10-30** (`/pr-review`) — #995's follow-ups merged from outside as PR #1222 (`6bb24b77`), five `WP-1809:` commits. The contributor sorted the round 1 and 2 items: seven built, five already on main, one declined with a measured alternative. Built: a torch-mps test of the planarity columns (on the device, rms 1.228004e-3 Å out of plane against numpy's 1.228009e-3 Å); one `RESTRAINT_TENSION` finding per plane; `eigh` named on `Backend.linalg`; a `scope` of `("qpa", "structure", "magnetic")` on `RESTRAINT_PAIRS_STALE`, so it reads `info` under the cell, phase-id, microstructure and calibration purposes; r₀ stated in its audit evidence; the restrain guide's centroid rule for planes. Declined: skipping the stale search on `telemetry=False`, because a user passes that to leave a fit unrecorded and would lose a correctness warning. The search runs instead only where a coordinate or cell parameter moved. On a 20-atom body with 29 contact rows that costs about 46 ms at the end of a 0.81 s fit, and a fit that moves nothing pays 0.5 ms. The ring test's bound holds on Linux (rms 1.228009e-3 Å, the same to seven digits across 28 perturbed starts). Open: the skill row for `RESTRAINT_PAIRS_STALE` (`references/diagnostics.md`, three copies) still gives one remedy and says "warning, plan end", and needs one clause each to stay true. `test_planarity_rows_leave_the_data_statistics_bit_identical` does not yet declare the compiled path. No task is ticked. Gate (a stack of eleven PRs on main `b40bc994`, tree `307eff83`; macOS arm64, `[dev,jax]`, Python 3.12): 13 217 passed, 216 skipped, 48 xfailed, 0 failed, with ruff, the `-W` manual build and the GUI ladder green.

- **2026-10-29** (`/pr-review`) — R8b merged from outside as PR #995 (`737963bc`): planarity restraint rows (the plane normal as the scatter matrix's smallest-eigenvalue eigenvector, Schomaker et al. 1959; `PLANE_DEGENERATE_REL`), and `RESTRAINT_PAIRS_STALE` at plan end, whose suggestion names both remedies (rebuild the list, or lower a real contact's species-pair minimum) and picks neither. Gated with seven other PRs on `bab2839c`: fast 12 213 passed, slow 417 passed. Left with the contributor, not blocking: a `scope` if a stale contact should not warn a QPA-only reader; the stale search's cost on a realistic molecular phase (it runs twice a fit); a sentence making r₀ (the strictest `min_distance` for the pair) visible in the audit row; and `rms[True] < 3e-3`'s margin on Linux.

- **2026-10-12** — tether and anti-bump, the first half of R8, built by
  @mustachefeeling in PR #888 (seven `WP-1809:` commits) and merged by the
  `/pr-review` run as `edad5b5a`. Planarity and `RESTRAINT_PAIRS_STALE` are
  still open.

  **The caller builds the pair list.** This replaces the engine-frozen list
  that the Context records. The PR asked, and the round-1 review answered on
  2026-10-11. Explicit rows keep the restraint row count fixed for every stage
  by construction. They survive JSON and history checkout, and they need no
  new state in `RefinementState`. The cost is that a pair drifting inside r₀
  from outside the list gets no restraint. `RESTRAINT_PAIRS_STALE` is where
  that gets named: it will search the phase at plan end. An engine-built list
  can come later as a convenience that calls this builder.

  *Done:*
  - `TetherRestraint` gives the row √w·max(0, d − d_max)/σ. TOPAS calls it
    `Distance_Restrain_Keep_Within`. `AntiBumpRestraint` gives
    √w·min(0, d − d_min)/σ, TOPAS's `Distance_Restrain_Keep_Out` and
    `AI_Anti_Bump`. Both join the `Restraint` union, and
    `RestraintRow.kind` gains `"tether"` and `"anti_bump"`.
    `SCHEMA_VERSION` went 0.49 → 0.50.
  - Both reuse the bond row's image resolution and partials through one
    `side` field on the compiled `_Bond`. On the flat side the row and its
    partials are zero. At the kink the slope is taken as zero.
  - `model.restraints.anti_bump_restraints` returns explicit rows. A species
    pair with no stated minimum gets no row (#677's rule). A body's own pairs
    are skipped in the body's own copy only. The image shell is centred on
    the nearest lattice vector and sized by the cut, so the list does not
    depend on the stored cell.
  - The two row equations are in manual Part 2 (`parameterisation.md`). Both
    kinds are deferred in `tests/api_surface_deferred.txt` until WP-1812, and
    `api.md` is unchanged. The `api-bodies.md` index the WP-1920 inheritance
    allowed was not created.
  - `tests/test_one_sided_restraints.py`, whose staged fit writes
    `tests/output/one_sided_restraints_li_o.png`.

  *Measured* (the contributor's figures, from #888):
  - Each row agrees with a central difference to 1e-5 relative, 6e-4 Å from
    the kink on both sides. The kink itself is untested. There the one-sided
    slopes are 0 and 1/σ, and a central difference returns their mean.
  - The pair list equals an exhaustive 11³-cell search at a 10 Å cut. A P2₁
    contact survives five whole-lattice shifts of the stored coordinates.
  - A two-stage fit from Li–O 1.7 Å reached 2.298 Å against a 2.3 Å truth, at
    GoF 1.02, with both rows in the report at deviation 0.

  *Gate* (this run, main `4a8c6d08` + #888 as `0c4108d2`, macOS arm64,
  Python 3.12.10, `[dev,jax]`): ruff clean. The fast suite gave 9331 passed,
  113 skipped and 2 xfailed in 346 s. Another session's fast suite overlapped
  its last three minutes. The manual built clean under `-W`. The slow suite
  gave 308 passed and 12 skipped in 1531 s. Main had not moved, so the merge
  left it identical to the gated tree.

  *Inherited, still open.* #759 § 3 (a) sets R8b's planarity form, the
  distance sum to a least-squares plane. #759 § 3 (b) and PR #675 concern the
  builder's `min_distance`. Today it takes the caller's number, species-pair
  mapping or callable. Reading #675's radii there, and saying
  which pairs got no row, is still this WP's decision.

  Next: R8b, the planarity rows and `RESTRAINT_PAIRS_STALE` at plan end, with
  its skill row.

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
