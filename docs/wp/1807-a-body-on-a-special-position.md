# WP-1807 — a body on a special position

Milestone: rigid-bodies · Status: ✅ 2026-10-31 — R6 merged from outside as PRs #1005 and #1226 (in 1.11)
Depends on: 1805

## Goal

An invariant body on a special position refines with only the DOFs its site allows. This
is chunk R6 of issue #561, sized S.

## Context

- The rotation DOFs take the axial-vector invariant subspace of the site stabiliser,
  `allowed_moment_basis(ops, use_time_reversal=False)`. The origin takes its site basis.
- A non-invariant fragment is refused, naming the atom. WP-1805's
  `RIGID_BODY_NOT_INVARIANT` already fires on diacetylene (an outside branch, 2026-10-06).
- A disordered body is stored at occupancy 1/|G_s| with `Atom.disorder_group`.

## Non-goals

- Torsions (WP-1808).

## Tasks

- [x] Rotation and origin bases from the site stabiliser; the refusal by name (PRs #841, #1005)
- [x] The diacetylene case and a monoclinic case + obs/calc/diff PNGs to `tests/output/` (`tests/test_rigid_body_special.py`, PR #1005)
- [x] Skill: a row in `references/abstention.md` for `RIGID_BODY_NOT_INVARIANT` and `RIGID_BODY_IMAGE_OVERLAP` (PR #1005)

## Acceptance

- Diacetylene at 5 K (COD 1577467, CC0; Wombat, 2.413 Å) on the Pnma mirror gets 2
  origin DOFs and 1 rotation DOF. Origin x and z lie within the deposited esds, and the
  orientation stays in the mirror to 1e-12.
- A monoclinic case passes.
- A non-invariant fragment is refused, naming the atom.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-31** (close, ghostshift batch, PR #1287) — closed. A rigid body on a special position refines with only the rotations and origin shifts its site allows, and a body that straddles a symmetry element is refused instead of doubling the composition in silence (#876, closed). Diacetylene on the Pnma mirror builds with two origin DOFs and one rotation DOF, and a body on the C2/c two-fold stays on its axis as the cell moves.
  *Done*: the three tasks landed in PRs #841, #1005 (`8e871e93`) and the follow-ups #1226 (`8b9c0a3a`). This session ticked them against the tree and closed: ✅, `Priority:` deleted, the consumed `### Inherited` section deleted (the #876 asks, built by #1005; the 0-1-3 turn-direction pin is `test_the_axial_basis_is_the_moment_law_on_every_point_group_subgroup`), and the narrative moved to the v1.11 record.
  *Checked against the tree and `gh`*: the PNG task is done. `tests/test_rigid_body_special.py` draws `diacetylene_5K_site_body`, `diacetylene_displaced_site_body` and the perhydropyrene and sulfate rows to `tests/output/` through `_draw`. The monoclinic case is `test_a_body_on_the_c2c_two_fold_stays_on_its_axis_as_the_cell_moves`. The refusal naming an atom is `test_an_atom_on_an_element_its_origin_is_not_on_is_refused_naming_both`. *Skill* (the third task asked why): not none. `references/abstention.md` carries a row for `RIGID_BODY_NOT_INVARIANT` and `RIGID_BODY_IMAGE_OVERLAP`, from #1005. Issue #876 and PR #1226 are closed and merged. `tests/test_rigid_body_special.py` ran with the batch's 200 passed, 2 warnings (`-m "not slow"`, macOS arm64, `[dev]`, Python 3.12, alone).
  *What it does not do*: the overlap check is O(live² · |G|) in Python, unmeasured on a realistic body (the 2026-10-29 entry). It was a follow-up for the contributor and is not owed here.
  *Release*: this WP was P2 for a wrong-answer case (a doubled composition with nothing firing). Its fix merged on 2026-10-29 and 2026-10-31 and is staged in `docs/releases/1.11.0.md`, so it ships with the next cut.

- **2026-10-31** (`/pr-review`) — #1005's follow-ups merged from outside as PR #1226 (`8b9c0a3a`) after two rounds. They are the three items round 2 of #1005 listed. (1) The cross-backend config `bodies_site_fixed` in `tests/test_cross_backend.py` is HKUST-1's BTC linker (COD 4002052) on the .3m site of Fm-3m: no rotation input, the origin's one site DOF along [1, −1, 1], the cell and Cu's site DOF, over 10 to 22° (33 reflections). Every row passes on numpy-FD, jax and torch (macOS arm64). With the k = 0 branch removed, jax and torch error on the empty stack. With a constant turn put into the branch, both fail at `cell.a` at rel-L2 2.7e-2 against the 0.005 bar. (2) The `4.0 * SITE_TOL` is now `params.vector._BODY_SITE_MISS_FACTOR`, at tier 1 by arithmetic, and round 1 moved it from 4 to 8. The first derivation held only for operations `site_orbit`'s step 1 admitted, each residual at most `SITE_TOL` per component. An operation the snap added can carry 3× per position, so two positions can miss by 6×, and a factor of 4 could refuse a body on its sites. Any factor from 6 to 1/`SITE_TOL` − 6 refuses the same far-element inputs, and 8 keeps the factor-of-two margin over 6. The test asserts 6 < factor < 1/`SITE_TOL` − 6 and fails with the factor at 4. The attained corner (origin and atom typed `SITE_TOL`/2 off the P n m a mirror on opposite sides) builds at 8 and is refused at 1.9, and the same element a lattice vector away is refused. The step-1 miss measured on 25 site pairs in 17 groups reaches 2 × `SITE_TOL` and never more, and that hill-climb is not a committed test. `SITE_TOL` stays `unaudited`, and its row now names both rigid-body uses. (3) The diacetylene Wombat fit stays in the fast tier. CI took 1.19 s (py3.11) and 1.76 s (py3.14), rank 504 and 337 of about 12 200 cases, where the 50th slowest takes 13 to 14 s. The PR also recorded a disagreement it did not fix. The linear-body axis test (`RigidBodyBlock._increment_basis`) compares a tilt in radians with a fractional tolerance, so it disagrees with the site check for a short body. For a CO₂-like body (C-O 1.16 Å) in the P n m a mirror, an O typed 4e-5 off the mirror passes the site check and is refused at "90°" at b = 6 Å, and at b = 20 Å the axis test refuses from 2e-5. The contributor proposes (a) bounding the tilt by `SITE_TOL` × the longest cell edge ÷ the shortest nonzero body radius (tier 1 by the same arithmetic) as a separate PR, or (b) snapping the direction to the site first. The review left the choice unanswered. The review also noted that a case with a snap-added operation fixing both the atom and its origin would strengthen the factor's row, and that the merge does not need it. `tests.audit_delta` reports 1 added and 1 changed (`SITE_TOL`, evidence only), 0 new at `unaudited`, no tier-3 row. No task is ticked. Open: the PNG task, the close, the axis-test mismatch above, and the overlap check's cost (O(live² · |G|) in Python, unmeasured on a realistic body, from the 2026-10-29 entry). Gate (the six PRs of this round merged together onto main `766c3505d`; macOS arm64, `[dev,jax]`, Python 3.12): fast 12 884 passed, 223 skipped, 32 xfailed; slow 435 passed, 18 skipped, 16 xfailed, with one GUI-boot socket timeout under load that passed alone in 5 s; ruff and the `-W` manual build clean.

- **2026-10-29** (`/pr-review`) — R6 merged from outside as PR #1005 (`8e871e93`), closing #876. A rigid body on a special position takes its rotation and origin bases from the site stabiliser. The image-overlap refusal sums the occupancy of every image in one place, so a place of any order is held to one atom, and centring uses the centroid's projection onto the site's fixed space so the typed-precision bound holds on 2-, 3- and 6-fold sites. Left as follow-ups: the overlap check is now O(live² · |G|) in Python, unmeasured on a realistic body; and a body listing an atom and its mirror image explicitly at ¼ each counts ¾ in the place, as the pairwise rule did.

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
- **2026-10-08** — the refusal half of the first task landed from outside. PR #841
  (head `6b8e9ec2`, closing #840) merged as `7881b8b3`.
  *Done.* `ParameterTable._collect_body` now refuses a body when any member atom
  has a site stabiliser of order > 1, not only when its origin does. The message
  names the body, the atom, its position and the stabiliser's order. It reads
  `wyckoff.stabilizer_rotations`, the stabiliser the forward model takes its frozen
  multiplicity from. Before it, a body over PbSO₄'s mirror atoms (Hill 1992) built
  with a general centroid, turned off the mirror inside the stage, and fitted at
  Rwp 25 % against 3.5 % with 8 S and 24 O counted in a cell of 4 and 16
  (numbers in #840). This meets the Acceptance line "a non-invariant fragment is
  refused, naming the atom".
  *Not done.* The first task stays unticked: the rotation and origin bases from the
  stabiliser are not attempted, nor disorder. Until they land, every body touching
  a special position is refused at table build, origin or atom.
  *Gotchas.* The check runs at every table build, so a `.rex` history holding such
  a body now refuses at open where it opened before. The origin check already had
  that property. `RIGID_BODY_NOT_INVARIANT` has no agent-skill row for either
  case, and the third task ("Skill: none expected") should say whether this
  refusal's message is enough.
  *Gate:* stacked with #839 on `main` `63af9e1b` as `5c82b0c2`, macOS arm64,
  `[dev,jax]`: fast 8944 passed, 109 skipped, 1 xfailed, 1 failed (the
  `test_indexing_reduce` reduction-map row, failing on `main` alone); `-m slow`
  290 passed, 14 skipped. `main` then moved only by #845's handover entry, and
  after both merges it equals the gated tree plus that entry.
