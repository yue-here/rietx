# WP-1989 — the rigid-body check's released arm keeps riding hydrogens riding

Milestone: unscheduled · Status: 🔄 2026-11-17 — claimed by @mustachefeeling (part 2: the stretched body fires, the deposited one does not, and the skill row; part 1 landed via #1280 as `f1187a062`)
Track: What fires, and what stays silent
Depends on: — (1806 soft: the public case it shows on, and its pdCIF reader task)
Priority: P2 2026-10-16 — a check that cannot fire on the commonest organic body, so a 0.3 Å bond error passes; a path few fits run, and the Hamilton p and ranked deviations are still printed

## Goal

`Refinement.check_rigid_bodies` fires `RIGID_BODY_MISFIT` on a wrongly
shaped body whose members include riding hydrogens, because its released
arm frees the heavy atoms and keeps each hydrogen on its riding rule.

## Context

Issue #1008 (mustachefeeling, 2026-10-16), found building the R4 test of
#561 (WP-1806's acridine case).

The check (WP-1922, closed, shipped in 1.8.0) fits two arms per body. The
body arm frees the pose. The released arm drops the body, restrains its
template bonds and angles, and frees `phases.{ip}.atoms.{j}.dof.*` for
every member `j` (`report/body_misfit.py`, the `_fit` call after
`released_phase`, checked at `138d55dc`). It fires on Hamilton's test
**and** ΔBIC > `bic_threshold`. Riding hydrogens are members, so they are
freed with the heavy atoms.

The issue's measurement (acridine form IX, COD 2242872, 14 heavy atoms + 9
aromatic H riding at 0.93 Å, C3 moved 0.3 Å along C2→C3 in the template):

```
chi2_body 36061.6   chi2_released 27806.0   n_effective 1198.5
n_free_body 20      n_added 63              p_value 3.6e-32   delta_bic -135.0   fires False
```

Hamilton rejects the template and the deviations rank C2–C3 first
(−12.0σ), but ΔBIC fails. A released arm with the H kept riding would add
14·3 − 6 = 36 parameters (penalty ≈ 255 against ≈ 447 for 63). The issue
estimates ΔBIC ≈ +300 for that arm from the two fits at equal parameter
count; **the 36-parameter arm was not run**, so that number is a target to
measure here, not a tolerance.

The issue's four options, none chosen: keep riding H riding in the released
arm; charge `n_added` with heavy-atom coordinates only; fire on Hamilton
plus a heavy-atom-count ΔBIC; add a direct Δχ² row field. The first is the
only one where the fit and the count describe the same model.

Reproducing needs #1006's `_pd_proc_intensity_net` reader (WP-1806's first
task, PR #1006 open) or another body with riding H on a pattern the tree
reads.

### Inherited

- 2026-10-31, from the issue triage (issue #1008): the reporter (2026-10-30)
  proposes splitting this WP in two and offers to build the first part. Part 1
  is the arm: the released arm frees the heavy-atom members and each riding H
  follows its parent, through `Refinement.tie(..., offset=)` at a held cell if
  a check shows that suffices; Δk is read off the fit (36 on acridine IX, 14 ×
  3 − 6); the arm is built by a public function that `check_rigid_bodies`
  calls, so a caller can fit it by hand and choose which members are freed;
  verified by the parameter count, each H–parent vector kept after the fit,
  and the public arm's χ² equal to the same arm assembled by hand; the ΔBIC on
  the stretched body measured and reported, not asserted. Part 2 is the
  verdict: the stretched body fires, the deposited body does not, and the
  skill row. Part 1 changes no `MISFIT_ALPHA`, `MISFIT_BIC` or `fires`. If
  riding on a free atom (#759) is needed instead of ties, they will stop and
  say so first. Checked against the tree at d87c8cc91: `Refinement.tie` takes
  `scale` and `offset` (`refine.py:3429`); the released arm is still assembled
  inside `report/body_misfit.rigid_body_misfit` (`released_phase`, line 256),
  with no public builder. The public arm builder is a new public name.

- 2026-11-12, from WP-1806 part 2 (PR #1545): the tie half of the proposal
  above works on the real acridine pattern, measured. The free-atom control
  in `tests/test_acceptance_acridine_ix.py` (`_fit` with the body removed)
  frees the 14 heavy atoms' `dof.*` and ties each H's `dof.k` to its
  carrier's, with no offset and the cell free. The H then takes its
  carrier's shift and keeps its fractional C–H vector. It converges unrestrained (Rwp
  0.05780 against the body's 0.05842), and two starts land 0.0002 Å apart.
  The body's own H leave their carrier's shift by at most 0.0015 Å. So a
  shift tie keeps riding H riding to that size, at a free cell, without
  #759's riding-on-a-free-atom. The soft dependency on WP-1806 is
  discharged: the public case and its pdCIF reader are on main.

## Non-goals

- The "right body does not fire" arm, which the issue says is unaffected.
- Riding-H construction itself (WP-1810).

## Tasks

- [ ] Reproduce on a pattern the tree reads (synthetic riding-H body if #1006 has not merged).
- [x] The released arm frees the heavy-atom members and keeps each hydrogen on its riding rule; measure ΔBIC on the issue's case.
- [ ] Tests: the stretched body fires, the deposited body does not
- [ ] Skill: the `RIGID_BODY_MISFIT` reference row, if its reading changes

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k rigid_bod -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Stephens et al. (2019), *Acta Cryst.* E75, 489 (COD 2242872).
- Hamilton (1965), *Acta Cryst.* 18, 502.
- Issues #1008, #775, #561.

## Handover log

- **2026-11-17** — Part 1 is on main. Mike's PR #1280 merged as `f1187a062`.
  The rigid-body check's released arm now frees the 14 heavy atoms of
  acridine form IX and keeps its 9 riding hydrogens on their parents. It adds
  36 parameters where 1.10.0 added 63. On #1008's case with a C2–C3 bond
  stretched by 0.3 Å, ΔBIC is +20.8 under the riding arm, against −137.1 with
  every member freed. The arm is also public, as `Refinement.released_arm`.
  Whether the stretched body fires is part 2's to test. No threshold or
  verdict changed. Entry by a ghostshift close-only runner (PR #1648).

  *Done (PR #1280, Mike):* `report/body_misfit.released_arm` builds one
  body's arm and `rigid_body_misfit` calls it. Each rider's coordinate DOFs
  are tied to its parent's with offset 0, so the parent–H vector holds exactly
  at a held cell and follows the cell as a fractional offset at a refined one.
  `crystallography.riding.riding_parents` names each H's parent. Six tests in
  `tests/test_body_misfit.py` on `tests/data/cod_2242872.cif` over a synthetic
  Cu pattern; each fails on revert.

  *Measured (PR #1280 body, deposited pattern COD 2242872, #1008's protocol;
  ΔBIC at N/f²):* stretched body, riding arm: χ² 36079.1 → 28648.5,
  n_added 36, N_eff 1196.7, Hamilton p 4.8e-37, ΔBIC +20.8. Stretched, all
  freed: 63 added, ΔBIC −137.1 (#1008 had −135.0 on `d3a641e6`). Deposited
  body, riding arm: p 0.41, ΔBIC −233.2. #1008's estimate of ≈ +300 compared
  the stretched body with the right one at equal count, which the released
  arm does not recover. The stretched body's deviations rank C2–C3 first, at
  −11.3σ (1.705 → 1.479 Å). Review bench (2026-11-16, macOS arm64, Python
  3.12, `[dev]`, stack of main + #1584 + #1580 + #1340 + #1280): fast
  selection 14 694 passed / 433 skipped / 32 xfailed / 0 failed; released-arm
  PNG flat residual, GoF 0.99. Full suite on main + #1340 + #1280: 15 643
  passed, 1 failed (`test_pair_diagnostic_class`, a magnetic test that fails
  identically on plain main on that Mac).

  *Next:* part 2, after #1280. Test that the stretched body fires and the
  deposited body does not (task 3), then the `RIGID_BODY_MISFIT` skill row if
  its reading changes (task 4). Issue #1008 stays open for it. Task 1 stays
  unticked because the review verdict ticked only task 2. The PR body's table
  reproduces #1008 on the deposited pattern but no test asserts it, so part 2
  decides whether that run counts.

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #1008).
  Checked against the tree at `138d55dc`: the released arm frees
  `atoms.{j}.dof.*` for every body member, riding H included. Not run: the
  case needs #1006's reader. No open WP owns it: WP-1922 shipped the check
  and is closed, WP-1810 (riding H) has all tasks landed and awaits closure,
  and WP-1806 fences hydrogens out. Next: reproduce, then the riding arm.
