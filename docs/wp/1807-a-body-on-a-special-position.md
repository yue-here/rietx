# WP-1807 — a body on a special position

Milestone: rigid-bodies · Status: ✅ 2026-10-31 — R6 merged from outside as PRs #1005 and #1226 (in 1.11); the linear-body axis follow-up as #1551 (2026-11-19), and its no-reach default as #1702 (2026-11-20)
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

- **2026-11-20** (repair, ghostshift close-only, PR #1729) — #1551's review follow-up 2 merged from outside as PR #1702 (`68e19bbd2`, 2026-11-20). `RigidBodyBlock(site_reach=None)` is now the default and means the body's atoms were not typed on a site. With no reach the linear-body axis test is skipped, and the body takes the nearer case, one turn about the site's axis or none. The old default, 0.0, held the axis to the bit, so a direct caller's body typed exactly along or across the axis was refused at a rounding tilt (5.5e-17 rad on Linux, up to 5.9e-16 rad on macOS arm64). An explicit number, 0.0 included, keeps #1551's test and its refusal text. The table's one call site, `ParameterTable._collect_body`, always passes `site_reach(m)` where the site fixes a direction, so no structure's rigid bodies build differently. The review chose the skip over refusing the call, on the ground that the block already takes a non-linear body's pose on trust and leaves invariance to the table's two refusals. Left open: the release note and the `__init__` comment quote the Linux tilt ("~1e-17 rad"), which the 1.13.0 cut can correct. Checked on the merged tree (main `6c3a2db5e`; macOS arm64, Python 3.12, `[dev]`): every rigid-body test file, slow included, 708 passed, 194 skipped, 4 xfailed, 0 failed; `tests.audit_delta` no change; `tests.reader_output` unchanged; the new tests fail on main's `bodies.py`. The full suite was not run, as the change reaches only direct callers of the block. Next: nothing in this WP. This entry is a repair, and a correction to this WP's own record, written by a ghostshift runner: the PR's two `WP-1807 follow-up:` commits landed after the close. Status stays ✅.

- **2026-11-19** (repair, ghostshift close-only, PR #1699) — the axis-test mismatch the 2026-10-31 `/pr-review` entry left open is fixed. A short straight body, such as CO₂ on a mirror, could pass the site check for every atom and still be refused as off its site. The axis test compared the body's tilt, an angle, with a tolerance in cell fractions, so a short body in a long cell failed it from an atom typed 2e-5 off. Mike's PR #1551 (merged as `c19851fcb`, 2026-11-19) bounds the tilt by what atoms typed within the site tolerance can produce. Such a body now builds, and one tilted past the bound is refused with its tilt, the bound and the atom furthest off. This entry is a repair: the PR's three `WP-1807:` commits landed after the close, and the file had not recorded them. Status stays ✅.
  *Done* (read off `git log c19851fcb^1..c19851fcb^2` and the PR): `363e6e239` bounds the tilt in radians. `RigidBodyBlock._axis_tilt_bound` (`params/bodies.py`) gives the tilt's sine at most reach × Σ|sᵢ| / Σ sᵢ², with sᵢ each atom's offset along the body's axis. The reach is `params.bodies._SNAP_REACH` (`SITE_TOL` × (1 + `_SITE_TOL_SLACK`)) times the cell's longest body diagonal. `ParameterTable._collect_body` passes the reach and the atom labels when the site leaves fewer than three turn directions, so a body on a general position sees no change. `5f1c0c545` builds the polar-law test's block with the site's reach. At the default reach of 0 that test passed on macOS arm64 and failed on Linux at a tilt of 5.5e-17 rad. `a3c412811` says in `_SNAP_REACH`'s audit row that its tier follows `SITE_TOL`'s. The row is new at tier 1, and `SITE_TOL`'s evidence names this use. Five tests are new in `tests/test_rigid_body_special.py`. Yue accepted the derived bound, option (a) of #1386, and the new refusal text on 2026-11-17, in round 1 of the review. Issue #1386 closed at the merge.
  *Measured* (this shift's round-2 review of #1551, merged onto main `d98250f96`, macOS arm64, `.venv` `[dev,jax]`, Python 3.12): fast 15 004 passed, 255 skipped, 32 xfailed, 0 failed. Slow 961 passed, 17 skipped, 18 xfailed, 1 failed. The failure is `test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment`. It fails the same way on plain main `807df6fc7`. `tests.audit_delta` reported 1 added, 1 changed and 0 new at `unaudited`. `tests.reader_output` reported no change.
  *Follow-ups, Mike's*: neither is owed by a session on this WP, and this entry records them rather than asking for them. (1) `RigidBodyBlock(site_reach=0.0)` is a default that refuses an exactly typed body, because a tilt computed in floating point is rarely zero. No production caller reaches it. Mike's comment of 2026-11-18 on #1551 plans `site_reach=None`, meaning "not on a site", as its own PR off main. (2) The round-2 review suggests an optional release-note fragment in `docs/releases/unreleased/`: a linear body on a mirror or two-fold, typed within the site tolerance, now builds where 1.12.0 refused it. Without it, the 1.13.0 cut writes the line from the tag range.
  *Still open from earlier entries*: the overlap check's cost, O(live² · |G|) in Python and unmeasured on a realistic body (2026-10-29). It is the contributor's follow-up as well.
  *Release*: none owed at once. The defect refused a valid body with a message, so no fit gave a wrong answer, and the fix ships with 1.13.0.
  *Next*: nothing for this WP. When `SITE_TOL` is given a tier, `_SNAP_REACH`'s row moves with it in the same edit.

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
