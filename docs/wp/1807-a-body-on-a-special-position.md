# WP-1807 — a body on a special position

Milestone: rigid-bodies · Status: 🔄 2026-10-29 — R6 (stabiliser bases and the image-overlap refusal) merged from outside as PR #1005 (`8e871e93`), closing #876; the PNG task and the close to check
Depends on: 1805
Priority: P2 2026-10-11 — was P3: #876, the origin refusal advises a move that builds a doubled composition with nothing firing

## Goal

An invariant body on a special position refines with only the DOFs its site allows. This
is chunk R6 of issue #561, sized S.

## Context

- The rotation DOFs take the axial-vector invariant subspace of the site stabiliser,
  `allowed_moment_basis(ops, use_time_reversal=False)`. The origin takes its site basis.
- A non-invariant fragment is refused, naming the atom. WP-1805's
  `RIGID_BODY_NOT_INVARIANT` already fires on diacetylene (an outside branch, 2026-10-06).
- A disordered body is stored at occupancy 1/|G_s| with `Atom.disorder_group`.

### Inherited

- **2026-10-16, from the issue triage (#876): PR #1005 (theirs, head
  `d43fd180`) builds R6 and both asks of #876.** It opened 2026-10-16 00:12
  and WP-1807 does not name it. It gives a body on a special position the DOFs
  its site allows (`wyckoff.axial_basis`), deletes the origin refusal and its
  "move the origin to a general position" text, and adds
  `RIGID_BODY_IMAGE_OVERLAP`: an image of a body atom within 0.7 x the
  covalent-radius sum of an atom of the same body, with the per-cell counts in
  the message. This is the "atom within a bond length of its own image" option
  the 2026-10-11 comment left to the WP-1807 session (no declared Z stored).
  Its PbSO4 check: the body 0.03 off the mirror is refused ("O 32, S 8 per
  cell"). `body_from_atoms(..., origin=)` takes a label or a point. Checked
  against the PR body at `d43fd180`, code not reviewed. Open: review and merge
  #1005; the PR body writes (#876) with no closing keyword, so #876 closes by
  hand.

- **2026-10-11, from the issue triage (issue #876): the origin branch's remedy
  is wrong, and following it doubles the composition in silence.** Both
  reproduced at `f11e22d3` on PbSO₄ from `tests/data/gsas2_pbso4.gpx`, with
  the whole SO₄ (S2, O3, O4, O5 and O5's mirror image) as one body
  (`scratchpad/t876/probe.py` in that session, restated here).
  (1) With the body's centroid on the Pnma mirror, `ParameterTable._collect_body`
  (`params/vector.py`, the origin check before the member loop) refuses with
  "move the origin to a general position". For a body that straddles a
  mirror that changes the chemistry. The member-atom branch #841 added gives
  the right advice ("refine that atom outside the body, or state the
  structure in a subgroup where its site is general"), and the origin branch
  should say the same. A sibling in the same message: the origin tuple prints
  `np.float64(0.0656...)` reprs, where the member branch converts with
  `float(v)`.
  (2) Following the advice, the body moved 0.03 off the mirror in y builds
  and predicts with no diagnostic. `phase_zmv(...).element_counts` reads
  Pb 4, S 8, O 32 per cell against the published Pb 4, S 4, O 16. The issue
  proposes comparing against the phase's declared composition or Z, and
  neither is stored. `structure_from_cif` sees `_chemical_formula_sum` and
  `_cell_formula_units_Z`, and `Phase` has no field for them. A signal that
  needs no declaration: a body atom within a bond length of a symmetry image
  of an atom of the same body means the body has landed across a symmetry
  element. The session working this chooses. Neither is built by this WP's
  bases alone, since a body started at a general position never reaches
  the special-position path.
  The route that worked for the filer: the t2 subgroup with the body
  general. P2₁2₁2₁ (origin z + ¼) reproduces the Pnma pattern to 2e-15
  relative, and Pn2₁a holding the floating y origin on Pb solved blind in 10
  of 180 random starts (filer's numbers, `bdaa7b62`, not reproduced here).

- **2026-10-08, from WP-1805 (answer c to #801): two free turn directions are
  refused.** A body's free turn directions must number 0, 1 or 3, since two turns
  combined produce the third and the re-chart cannot be exact on two. A site
  stabiliser's axial-vector invariant subspace always has dimension 0, 1 or 3 (a
  mirror or a 2-fold leaves one axis, two axes leave none), so a body on a special
  position never trips the refusal. A test that a stabiliser-derived basis passes it
  is cheap and pins that.

## Non-goals

- Torsions (WP-1808).

## Tasks

- [ ] Rotation and origin bases from the site stabiliser; the refusal by name
- [ ] The diacetylene case and a monoclinic case + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected; say why at handover

## Acceptance

- Diacetylene at 5 K (COD 1577467, CC0; Wombat, 2.413 Å) on the Pnma mirror gets 2
  origin DOFs and 1 rotation DOF. Origin x and z lie within the deposited esds, and the
  orientation stays in the mirror to 1e-12.
- A monoclinic case passes.
- A non-invariant fragment is refused, naming the atom.

## References

- Issue #561; PR #596.

## Handover log

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
