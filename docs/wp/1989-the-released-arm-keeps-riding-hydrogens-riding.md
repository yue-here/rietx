# WP-1989 — the rigid-body check's released arm keeps riding hydrogens riding

Milestone: unscheduled · Status: ⬜
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

## Non-goals

- The "right body does not fire" arm, which the issue says is unaffected.
- Riding-H construction itself (WP-1810).

## Tasks

- [ ] Reproduce on a pattern the tree reads (synthetic riding-H body if #1006 has not merged).
- [ ] The released arm frees the heavy-atom members and keeps each hydrogen on its riding rule; measure ΔBIC on the issue's case.
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

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #1008).
  Checked against the tree at `138d55dc`: the released arm frees
  `atoms.{j}.dof.*` for every body member, riding H included. Not run: the
  case needs #1006's reader. No open WP owns it: WP-1922 shipped the check
  and is closed, WP-1810 (riding H) has all tasks landed and awaits closure,
  and WP-1806 fences hydrogens out. Next: reproduce, then the riding arm.
