# WP-1991 — a site and its own image are one atom on every route

Milestone: unscheduled · Status: 🔄 2026-10-29 — merged from outside as PR #1014 (`b0019706`), closing #1007; the tasks to be checked against it and the WP closed
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-16 — a doubled composition with nothing firing, but only on a stored, hand-edited or code-built coordinate; a refined coordinate cannot drift there, and the CIF route already merges it

## Goal

A free atom within a fraction of an ångström of a special position counts
once in the cell on every route into a `Structure`, and says so, as a CIF
read already does.

## Context

Issue #1007 (mustachefeeling, 2026-10-16), found building #1005 (R6 of #561).

Reproduced at `138d55dc` with the issue's script (PbSO₄,
`tests/data/gsas2_pbso4.gpx`, Pnma; S2 on the mirror at y = ¼,
multiplicity 4; only S2's y moved; counted by
`rietx.optimize.qpa.phase_zmv`):

```
dy=0       S per cell = 4
dy=5e-05   S per cell = 4
dy=6e-05   S per cell = 8
dy=0.0001  S per cell = 8
```

Mechanism, from the issue and the code: `site_orbit`
(`crystallography/symmetry.py:867`) tests |R·x + t − x| against
`SITE_TOL = 1e-4` (line 766). A mirror's displacement is 2δy, so the
effective tolerance there is `SITE_TOL`/2. Past it the atom is general and
its image sits 2δy·b away (0.0006 Å at δy = 1e-4). The two images overlap
within the profile's resolution, the scale and Biso absorb the doubled
atom, and building a `Refinement` emits nothing.

What exists to reuse: #764/#765's twin merge in `structure_from_cif`
(`crystallography/cif.py:353`, `TWIN_DISTANCE = 0.02` Å at line 320). A
site whose own images lie closer than that is put on the special position
its orbit collapses to, with `CIF_SITE_TWINS_MERGED`. The gap is every other
route: a project file, a hand edit, a structure built in code. #1005 refuses
the rigid-body analogue (`RIGID_BODY_IMAGE_OVERLAP`, WP-1807, #876).

The reporter's comment proposes the fourth of their options: apply the twin
merge wherever an orbit is expanded, at the same distance, under a code
renamed off the `CIF_` prefix. A reader and a hand-built structure then
agree. They have said a PR follows.

Two constraints. `SITE_TOL` stays tight (#215: five-decimal files), so the
answer is the merge at a distance, never a looser snap. And the merge must
happen where a diagnostics channel exists: `ParameterTable` has none (root
CLAUDE.md, "a silent correction is a reader's to make").

### Inherited

- 2026-10-26 issue triage: #1088 shows this WP's Priority premise "a refined coordinate cannot drift there" holds only for a site already special. A general atom at occupancy ½ refined onto a mirror is snapped by the next stage compile, and the default plan's closing stage then returns 10 O per cell for 12 (10 of 16 noise draws). The mid-fit case is WP-2052's, outside this WP and PR #1014. Checked against the tree at c0e32ab29.

## Non-goals

- Changing `SITE_TOL`.
- The rigid-body case (WP-1807).

## Tasks

- [ ] Find every route that expands an orbit without the CIF reader's merge,
  and the one place a merge with a diagnostic can sit for all of them.
- [ ] Apply the twin merge there, renaming the code off `CIF_` (keep the old
  code readable for stored results, or record the break).
- [ ] Tests: the issue's δy sweep reads 4 S at every step, and the warning
  fires from δy = 6e-5 to the 0.02 Å boundary
- [ ] Skill: the reference row for the renamed code

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cif_sites_coincide.py -q   # plus the file this WP adds
.venv/bin/python -m ruff check src tests examples
```

## References

- International Tables for Crystallography Vol. A (site multiplicity).
- Issues #1007, #765, #876, #215.

## Handover log

- **2026-10-31** (`/pr-review`) — #1014's follow-ups merged from outside as PR #1223 (`e93378da`), two `WP-1991:` commits, after two rounds. They are the four items round 6 of #1014 listed. (1) A hold on x was dropped where the position couples x and y, as (x, 2x, z) does in P 6₃/mmc. The site merged 24 → 12, `_user_holds` emptied, and x refined. `twins._linked` now pairs each old DOF with every new DOF it shares a direction with. A hold follows every paired new DOF. A free path follows only where every coordinate the new direction moves was free. A tie needs a single direction and is still dropped, with a message naming the coupling. Tests cover P 6₃/mmc 12k, P m-3m 24m (x, x, z) and R-3m:H 18h (x, −x, z), each with holds on x, y, z and x+z. (2) `RefinementTree.load` carries every path-bearing action field (`turn_on`, `turn_off`, `values`, `held`, `unheld`, `ties`, `untied`) through `twins.carry_action_constraints`, in the parent state's numbering, and what moved joins the site's one `Constraints:` note. (3) A series `constrain=` hook runs against the declared structure's numbering (`sequential._constrain_in_declared_numbering`). On main a hold on `dof.2` raised `unknown parameter path` and ended the series. (4) `carry_constraints` uses the full form θₜ' = (sₜ·c/sᵢ)·θᵢ' + sₜ·k. Every s is 1 today, pinned by a sweep of 17 site templates in each of the 230 groups with the scale set exactly {1.0}. Round 1 found that the re-anchor read the carried displacement in the declared numbering while the hook's ties land in the built one. On O5 declared on the y = ¼ mirror and warmed off it, the hook's tie to `vars.dz` was missed, and pattern 2 started z at 0.8620 against pattern 1's fitted 0.8403. `_displaced_as_built` now maps it through `numbering_moves`, and a new test fails on the old code. `DofMove`'s docstring names `_dof_moves` as the one writer and says the empty defaults mean "not computed". The PR adds 20 tests, of which 17 fail on main's `src` and 3 are hold-on-z controls that pass there. `tests.audit_delta` reports 1 changed (`SITE_DOFS_RENUMBERED`'s evidence, still tier 1), 0 new at `unaudited`. The skill row's three copies, `help.py`, `reference/structure-files.md` and the 1.11.0 note carry the new wording. Left open. Anisotropic ADP DOFs (`phases.i.atoms.j.adp.k`, numbered by `wyckoff.adp_basis`) are not renumbered by `numbering_moves`, so a hold or tie on `adp.k` of a site that merges is not carried. The contributor read this off the code, did not probe it, and asked whether it belongs here or in its own WP. The review left that unanswered. An atom shifting index because the merge removed one ahead of it, for a site whose own DOFs did not renumber, is uncovered. The review said it is worth an issue of its own. No task is ticked, and the Status line still reads to be checked against #1014. Gate (the six PRs of this round merged together onto main `766c3505d`; macOS arm64, `[dev,jax]`, Python 3.12): fast 12 884 passed, 223 skipped, 32 xfailed; slow 435 passed, 18 skipped, 16 xfailed, with one GUI-boot socket timeout under load that passed alone in 5 s; ruff and the `-W` manual build clean.

- **2026-10-29** (`/pr-review`) — merged from outside as PR #1014 (`b0019706`) after nine rounds, closing #1007. A site whose images coincide is merged onto its special position on every route, not only CIF reads, under one F-independent gate (`TWIN_COORD_TOL`), with `SITE_TWINS_MERGED`/`SITE_TWINS_KEPT` and `SITE_DOFS_RENUMBERED`. Where several subgroups of one order have a fixed point in reach, the nearest wins (round 8). `TWIN_DISTANCE` moved to `symmetry.py` and stays on `UNAUDITED_BASELINE`. One note for later: the tie-break measures in fractional max-norm, as the reach does, so on a cell with unequal axes the Cartesian nearest can differ.

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #1007).
  Checked against the tree at `138d55dc`: reproduced, S doubles from
  δy = 6e-5. No open WP owns it: WP-1807 owns a body on a special position,
  and WP-1324 and WP-1319, which touched site handling, are closed. The
  reporter has said a PR follows on option four. Next: review that PR
  against this file.
