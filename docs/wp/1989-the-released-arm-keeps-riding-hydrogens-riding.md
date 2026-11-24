# WP-1989 — the rigid-body check's released arm keeps riding hydrogens riding

Milestone: unscheduled · Status: ✅ 2026-11-17 — the stretched acridine body fires and the deposited one does not, on the synthetic and the deposited pattern; skill row names the riding arm (part 1 #1280, part 2 PR #1655)
Track: What fires, and what stays silent
Depends on: — (1806 soft: the public case it shows on, and its pdCIF reader task)

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

## Non-goals

- The "right body does not fire" arm, which the issue says is unaffected.
- Riding-H construction itself (WP-1810).

## Tasks

- [x] Reproduce on a pattern the tree reads (synthetic riding-H body if #1006 has not merged).
- [x] The released arm frees the heavy-atom members and keeps each hydrogen on its riding rule; measure ΔBIC on the issue's case.
- [x] Tests: the stretched body fires, the deposited body does not
- [x] Skill: the `RIGID_BODY_MISFIT` reference row, if its reading changes

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k "rigid_bod or body_misfit or acridine_ix" -m "slow or not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Stephens et al. (2019), *Acta Cryst.* E75, 489 (COD 2242872).
- Hamilton (1965), *Acta Cryst.* 18, 502.
- Issues #1008, #775, #561.

## Handover log

- **2026-11-17 (a ghostshift runner, part 2; closes the WP)** — The rigid-body
  check now demonstrably catches #1008's wrong molecule. Acridine form IX
  with one C–C bond 0.3 Å too long, fitted to its own deposited synchrotron
  pattern, raises `RIGID_BODY_MISFIT` and names that bond first, while the
  deposited molecule stays silent. The same holds on a synthetic pattern at
  0.2 Å, in the fast tier. Both checks would fail had the check gone on
  freeing the hydrogens, so they test part 1's riding arm and not only the
  thresholds. No threshold, verdict or code moved; the WP is done, and
  #1008 closes with PR #1655.

  *Done (PR #1655):* `tests/test_body_misfit.py` gains three fast tests on
  the synthetic acridine pattern: the body with C2–C3 stretched 0.2 Å (H3
  moved with C3) fires on both tests, names C2–C3 first and raises one
  warning; the same fits with every member freed (63 parameters, the arm
  1.11.0 fitted, by hand through `released_arm(freed=...)`) stay under
  `MISFIT_BIC`; the deposited body does not fire. Helper `_stretch_c2c3`.
  `tests/test_acceptance_acridine_ix.py` gains two slow tests on the
  deposited pattern under WP-1806's plan (`_fit`): #1008's 0.3 Å stretch
  fires and names C2–C3 first, and its all-freed control stays under the
  threshold; the deposited body (the `real_deposited` fixture, which the
  check does not mutate) does not fire. Task 1 is ticked on that test. The
  skill's `RIGID_BODY_MISFIT` row (`references/abstention.md`, both copies
  synced) now says the riding H stay on their parents and names
  `ref.released_arm(name)` as the builder of that arm, to fit by hand. Two
  `tests/validation_matrix.py` rows (characterisation) record the slow
  tests, and `docs/VALIDATION.md` is regenerated. The WP's Acceptance
  command now selects the tests this WP added (`-k rigid_bod` matched none
  of them) and drops its `-q`.

  *Measured* (macOS arm64, Python 3.12, `[dev]` venv, branch on
  `662d0b712`). Synthetic, 0.2 Å, fixture seed 1989: χ² 3111.8 → 1951.8,
  36 added, N_eff 691.7, p 5.6e-45, C2–C3 1.605 → 1.449 Å (−7.8σ). Over seeds 1989, 7, 11, 23 the riding
  arm's ΔBIC was +87.2, +77.2, +95.5, +81.9 and the all-freed arm's −85.3,
  −99.7, −78.8, −93.9. At 0.3 Å the all-freed arm gave +25.2 (seed 1989)
  and +9.5 (seed 7), so 0.3 Å on the synthetic pattern cannot tell the two
  arms apart; that is why the fast test stretches 0.2 Å. Deposited body
  over seeds 1989, 7, 11: p 0.80, 0.67, 0.98; ΔBIC −236.0, −234.1, −243.2.
  Deposited pattern, WP-1806's plan: stretched body χ² 36852.7 → 28483.3,
  N_eff 1191.5, Hamilton p 9.3e-43, ΔBIC +52.0, C2–C3 1.705 → 1.463 Å
  (−12.1σ); all-freed χ² 27822.4, ΔBIC −111.3; the perturbed start reaches
  the same χ² to 1e-9 relative. Deposited body p 0.40, ΔBIC −233.1. Part
  1's +20.8 came from #1008's own script, whose body fit ends at χ²
  36079.1; this plan ends at 36852.7, so the two ΔBIC are not one number.
  Revert (default `freed` = every member): both stretched tests and the
  deposited fast test fail, on the count first. Fast selection:
  on the tree before the review fixes and matrix rows, 14697 passed / 432 skipped / 32 xfailed / 1 failed (`test_every_acceptance_test_has_a_matrix_row`, fixed by `d9aee3252`); on the final tree (`cd61e2ed5`), 14708 passed / 432 skipped / 32 xfailed / 0 failed in 573 s, 13 items more than main (3 tests, and 5 matrix checks for each of the 2 new rows); nothing new is skipped. The added fast tests cost 5.1 s, 3.1 s and 0.0 s on that run (8.2 s over `tests/test_body_misfit.py`; local, one run). Vale (`rietx_vale.sh`): 0 errors. The two slow tests, after the review fixes: 2 passed in 85 s. `tests.reader_output`:
  exit 0, unchanged.

  *Review:* a read-only Opus reviewer in this worktree (no
  `/code-review`, which edits the main checkout) found no bug. Applied: the
  all-freed controls assert convergence and a χ² under the body's, so a
  stalled hand fit cannot pass for the wrong reason; each stretched test
  pins its template C2–C3; the stretched body is called the positive arm;
  `_by_hand` says it carries none of the caller's ties, holds or limits (the
  reviewer measured `_by_hand` and the check's own `_fit` equal to every
  digit on both patterns); the skill row's wording; the Acceptance command.
  Declined: building the control through the private `_fit`, since the
  public route is what the manual documents and gave the same χ².

  *Generality:* not dispatched. The branch does not touch `_audit.py`, and
  it adds no heuristic: tests, and a skill row that is API vocabulary.

  *Next:* nothing in this WP. Nothing was left over for an issue.

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
