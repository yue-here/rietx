# WP-2060 — the likelihood interval where an esd cannot be read as one

Milestone: unscheduled · Status: 🔄 2026-11-07 — claimed by ghostshift (task 8, the build of Mike's ruling); tasks 2-7 built in PR #1322
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-07 — a wrong statement with nothing fired: a weak modulus beside a zeroed angle covers 0.82 at a nominal 0.95, on the magnetic path few fits run; the dead-column half shipped in PR #1322, and Mike's ruling leaves only the build

## Goal

A modulus whose site's angles left the covariance, and a modulus sitting on its dead column at m = 0, each carry a likelihood interval that covers, and `profile_interval` never returns a zero-width interval for a parameter the data barely constrain. Whether the interval runs by default on bound rows of the kinds people quote as limits (phase scale, occupancy, moment modulus) is ruled and, if yes, done.

## Context

**Where it came from.** Issue #1075 (2026-10-20, an outside contributor): a coverage study on simulated data (known truth, Poisson noise, N = 200-500 replicates per cell, main `afce00a4`, macOS arm64, numpy, LM). Its repro 1 (the FCJ apertures) went to WP-1955; this WP carries the rest.

**What exists.** `Refinement.profile_interval(data, path)` (`strategy/parameter_interval.py`) pins a value, refits everything else (`trial.run_stage(..., Stage("interval:…", []), **trial._plan_settings)`), and walks each side outward by 1, 2, 4, … esd until Δχ² passes the χ²₁ cut scaled by χ²_red·f², then solves the end to a thousandth of an esd. WP-2002's B2 ruling (option 2, 2026-10-19, `docs/wp/2002-batch/rulings.md:86-95`) runs it automatically on the answer stage for each moment angle the stationary-angle test zeroes, and keeps that test's effect on the other esds. `RefinedParameter.interval` carries the result. `_auto_intervals` (refine.py:2343) is the switch a trial clears.

**The reporter's coverage (nominal 95 %), as measured on `afce00a4`:**

| row | truths | Wald (value ± 1.96 esd) | profile | flat-prior posterior |
|---|---|---|---|---|
| interior control (cell a) | — | 0.978 | 0.978 | 0.978 |
| minor-phase scale, `min=0` | 0, 1σ, 2σ | 0.99, 0.99, 0.99 | 0.99, 0.975, 0.99 | 0.935, 0.975, 0.98 |
| O occupancy, `max=1` | 1.00, 0.97 | 0.985, 0.98 | 0.985, 0.98 | 0.985, 0.98 |
| one magnetic site, m = 0 | — | **0.745** on the 98 fits with a usable esd | none (zero-width) | 0.975 |
| width `profile.y`, W 30 % too large | at 1σ | 1.00 | **0.74** | 1.00 |

Moduli beside zeroed stationary angles (`test_stationary_moment_angle`'s two-site set, N = 400): the weak site (Mn2, 0.7 μ_B) covers **0.830 [0.790, 0.866]** with the conditional esd and 0.973 with the profile; 67 of 68 misses have the estimate above the truth, along the m·cos φ valley. The full covariance (zeroing off) covers by being 100-500× wider.

What it says: where the flag fires and the model is right, every rule covers, so a default interval on scale or occupancy adds information and fixes no coverage. On a width at a floor under a misspecified model the profile is the one that misleads (0.74), which is why widths, FCJ apertures and Biso keep the flag alone. The two cells that fail are moment cells.

**Re-measured in the 2026-10-26 triage on `c0e32ab29`** (the reporter's repro 2, unchanged but for the current API): seeds 3, 4 and 8 each end `converged` with m = −4.9e-7 ± 1.24e5, −5.9e-7 ± 1.74e4, −4.2e-7 ± 1.52e4 μ_B, `at_bound` False, no diagnostic in `result.diagnostics`, and `profile_interval` returns [v, v] with `fit_is_minimum=True` after 10 refits. `FitReport.magnetic` does say `supported=False` (|m| under 3 esd). The mechanism: intensity goes as m², so the modulus column vanishes at m = 0 and the esd-scaled walk cannot find the end. The same zero-width answer appears on the FCJ axial ratio at 0 (#1075's repro 1, WP-1955): `profile_interval("instrument.geometry.axial_sl")` returns [0.0, 0.0] with `fit_is_minimum=True` while one TRF stage drops χ² by ~1 200 χ²_red·f². So the step fix here is the class, and WP-1955's column fix does not make it unnecessary.

**Phase scale's profile changes its free set.** `profile_interval`'s pinned refits are stages, and a stage re-decides WP-1301's hold of a phase the data cannot see from the pinned values. Pinning a weak phase's scale higher makes it look supported, so its cell is freed. The reporter measured `fit_is_minimum=False` on 5-19 % of such fits with the lowest point 1.2-2.7 (up to 6.4) χ²_red·f² below the fit, while a TRF refit from the fit moves nothing. Read from the code at `c0e32ab29` (`parameter_interval.py:209-236`): each refit is `trial.run_stage`, so the hold is re-measured per point; not re-run.

**The tier of each rule this WP adds** (2026-11-02). `MOMENT_UNSUPPORTED`: tier 1, kind 1 (physics: the column vanishes at m = 0, so the esd is no interval; the 3σ cut is `MOMENT_SUPPORT_SIGMA`'s own row). The modulus sign kept in `profile_interval` (`_sign_is_unseen`): tier 1, an identity of the model (one moment block, or free angles reaching −m), with the one-sided cut from Self & Liang in m² ≥ 0. The step back in and the frozen free set: arithmetic and the fit's own record, no threshold; the stop when stepping back does not lower Δχ² reuses `PARAMETER_INTERVAL_CHI2_TOL`.

**Tier.** A default interval on a bound row is a new automatic action (DESIGN § Rules 1 and 4), and its trigger is new judgement: name the families. The moduli-beside-zeroed-angles rule follows from B2's own ruling (its effect on the other esds), so it re-opens B2's consequence and needs the maintainer. A modulus flag for "esd orders above the value" is tier 1 if stated as a fact (the column is dead at m = 0, Hamilton 1965's linearisation does not hold there).

### Inherited

## Non-goals

- The FCJ aperture stall (#1075's repro 1): WP-1955.
- Intervals on widths, FCJ apertures and Biso by default: the reporter's own measurement says the profile misleads there under a misspecified model.
- Posterior sampling: fenced (ROADMAP § v2+, Estimation).
- The two-site cant exchange (#1075 § 4): an identifiability question for WP-1418.

## Tasks

- [x] Rule with the maintainer: default intervals on bound rows of phase scale, occupancy and moment modulus (yes / no / modulus only), and whether a modulus beside a zeroed angle takes the interval by default or `MOMENT_ANGLE_STATIONARY` says its modulus is conditional and points at `profile_interval`. — *2026-11-02: scale and occupancy settled by Claude as **no** under the reporter's measurement (every rule covers there, so a default interval fixes no coverage). The modulus half is built as the pointer (no interval unasked; `MOMENT_UNSUPPORTED` and `MOMENT_ANGLE_STATIONARY` name `profile_interval`) and goes to the maintainer at the PR, under the reader-output rule: a modulus profile measured 7-58 s on 1-8 s two-site fits.* *Ruled by Mike on #1075 (2026-11-04, amended 2026-11-05), under the magnetic-path split he accepted that day: option 2, the interval computed unasked on flagged sites, with four conditions. Handover entry of 2026-11-07.*
- [ ] Build Mike's ruling (handover entry of 2026-11-07): a modulus profile unasked on each site `MOMENT_ANGLE_STATIONARY` flags, through `attach_stationary_intervals`, with conditions 1-4 and the 2026-11-05 amendment; tests for each condition; the stationary message, help, skill row and audit rows it moves. Bring Yue's three parts (below) to Yue at the PR.
- [x] `profile_interval` holds the fit's own free set along its path: a pinned refit freezes WP-1301's held paths as the fit held them.
- [x] `profile_interval`'s first step from the profile's curvature when the esd is orders above the value, and a modulus profile kept at m ≥ 0; never a zero-width interval where the walk found no end.
- [x] A modulus on its dead column says so in `result.diagnostics` (or the existing `supported=False` verdict reaches the result), with its `_audit` row. — *`MOMENT_UNSUPPORTED` (warning), the report's verdict through `report.magnetic.moment_supported`; tier 1.*
- [x] Whatever the ruling turns on, with its `_audit` rows. — *for the option built: `MOMENT_ANGLE_STATIONARY`'s message names the moduli of its sites and its suggestion points at `profile_interval`; the suggestion row's site count is unchanged.*
- [x] Tests (unit/property; acceptance if this WP carries it) + obs/calc/diff PNGs to `tests/output/`: repro 2's three seeds give a non-degenerate interval containing 0; the two-site weak modulus covers on a small replicate set; a phase-scale profile keeps the held cell held. — *`tests/test_modulus_interval.py` (seed 4 fast, 3 and 8 slow; the weak modulus as the pinned seed 14 where the esd misses, slow), `tests/test_held_phase.py::test_a_scale_profile_keeps_the_held_cell_held`.*
- [x] Skill: a reference row keyed by `RefinedParameter.interval` and the modulus code in `references/magnetic.md`; no body rule.

## Acceptance

Repro 2's seeds 3, 4 and 8 give intervals of non-zero width that contain m = 0; a phase-scale profile over a held phase reports `fit_is_minimum=True` where a TRF refit from the fit moves nothing; every shipped fixture with no moment is bit-identical.

```sh
.venv/bin/python -m pytest tests/test_parameter_interval.py tests/test_magnetic.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Hamilton, W. C. (1965). *Acta Cryst.* **18**, 502–510.
- Issue #1075 and its two repro scripts; WP-1929 (the stationary-angle test); WP-2002 B2 (`docs/wp/2002-batch/rulings.md`).

## Handover log

- **2026-11-07** (rulings, PR #1455) — task 1's modulus half is ruled, by Mike rather than Yue. On
  2026-11-04 Mike accepted the design decisions on the magnetic path (issue #1075, 05:08Z): "the
  physics, defaults, diagnostics, names, reader output and magCIF reading". Anything that reaches a
  non-magnetic fit stays with Yue, as do releases, stored formats and deletions. His rulings are headed
  "Ruled by Mike". He ruled option 2: a moment's modulus beside an angle the stationary test zeroed
  gets its likelihood interval computed unasked. A reader of a weak moment then gets a range that
  covers the truth about 94 % of the time, where today's esd covers 82 %. Nothing is built yet. Task 8
  builds it.

  **Ruled by Mike, 2026-11-04 (05:02Z, #1075): option 2 confirmed after review, with four conditions.**
  Quoted from the comment:
  > For a moment's modulus on a site whose angles the stationary test zeroed
  > (`MOMENT_ANGLE_STATIONARY`), rietx computes `profile_interval` unasked, on those sites only. It
  > runs through the hook the angles already use under B2 (`attach_stationary_intervals`): the answer
  > fit, and the attempt a sequential series keeps, never a trial or a rung.
  >
  > 1. **A site with `MOMENT_UNSUPPORTED` is one of these sites.** Its modulus gets #1322's one-sided
  >    interval from 0, and the message does not read that site's angle intervals as a direction.
  > 2. **A profile that finds χ² below the fit is still quoted, unless the drop reaches the interval's
  >    own cut.** `fit_is_minimum=False` fired on 32 of 80 of these two-site profiles (8 of 20 in
  >    #1322), by 0.07–2.2 χ²_red·f², and those intervals still covered the truth on 31 of the 32. So
  >    the finding gives the drop and says the interval is measured from the fit. Where the lowest
  >    point lies a full cut or more below the fit (7 of 400 fits on a refit with the angles on the
  >    direction), the fit is not at its minimum. Then the interval is not quoted as the modulus's
  >    uncertainty, and the finding gives the lowest point. A side with no end says why, as the angle
  >    intervals already do.
  > 3. **`MOMENT_ANGLE_STATIONARY` no longer tells readers to "quote the moment along that
  >    direction".** The modulus it prints is the moment's length at the tilt where the fit stopped
  >    (the angle values are kept), which is never shorter than the moment along the direction. It
  >    quotes the modulus's interval instead.
  > 4. **The guards live in the magnetic path** (`attach_stationary_intervals` and the diagnostic),
  >    not in `profile_interval`, which non-magnetic fits share.

  His measurement, on main `dd55ec4f5`, two-site set, N = 400: the weak site's esd covers 0.823
  [0.781, 0.859]. Centred on the moment's component along **a**, the same esd covers 0.970, so the
  misses come from the value. The profile covers 0.925 and 0.975 in the two cells it was run on
  (N = 40 each). A modulus profile takes a median of 5.1-5.4 s (range 2.5-11.8 s) on two-site fits
  of about 0.6 s, so about 10 s for both moduli, and 9.4 s on an 8.8 s fit of the LaMnO₃ BT-1
  tutorial data. The flag fired on 400 of 400 of these fits. A sequential series pays the cost once
  per pattern. His first ruling of that day (03:57Z) asked for a hold until 17:00 CET for a review.
  The 05:02Z comment ends the hold: "The build can go ahead now on the text above."

  **Ruled by Mike, 2026-11-04 (07:17Z, #1075): a pointer.** "The WP-2060 task 1 ruling above stands
  for today's code." One condition for turning on #1403's analytic angle columns now sits on #1404:
  "whichever escape it picks must also reach the refits of the modulus profile this ruling runs
  unasked, and a fit started exactly on a symmetry-fixed direction." That condition binds #1403's
  work, and this WP's build need not wait for it.

  **Ruled by Mike, 2026-11-05 (07:29Z, #1075): block D result and one amendment.** On main
  `da5e7aa36`, weak moduli of 0.05-0.2 μ_B at ×1 and ×0.1 counts, N = 400 a cell. The number a reader
  received covered 0.875 (D1, 0.05 μ_B) and 0.897 (D2, 0.1 μ_B), under the 0.90 bar he set on 11-04.
  The profile alone covered at least 0.917 in every cell. The shortfall came only from fits where the
  profile was withheld and the esd was given instead, and near zero that esd covers 3 of 20 (D1) and
  4 of 18 (D2). Quoted:
  > **The amendment.** On a site the stationary test flagged, when the profile is withheld, the
  > reader gets the pointer (the fit did not reach its minimum; refit), not the esd. Everything else
  > in the 4 Nov ruling and its four conditions stands.
  >
  > **For the build:** one change to the 4 Nov text. On a flagged site whose profile is withheld
  > (condition 2's case, where the finding gives the lowest point), the reader gets the pointer to
  > refit, not the esd. The other three conditions and everything else stand.

  Rerun on fresh seeds after the amendment was chosen (1000-1399, same commit, bar fixed before
  launch): D1 0.938 [0.909, 0.960] and D2 0.943 [0.915, 0.964], with the pointer on 13 and 14 of
  400. Sides with no end: 5 and 3 of 400. Every miss lay above the truth. Not covered by his runs:
  tilted weak moments at ×1 counts, and a profile of the strong site.

  **Yue's, and not decided by this ruling.** The 05:02Z comment names three parts on Yue's side.
  (1) `RefinedParameter.interval` is a stored field (schema 0.59) whose docstring names moment angles
  and one writer. Writing it on moduli widens that meaning, and no new field is needed. (2) Each
  stored interval carries its refit points (15-38 per modulus), so a flagged two-site result grows by
  two such lists. (3) magCIF keeps `magnitude` as the length at the kept tilt and `magnitude_su` as
  the conditional esd. Whether the exchange file carries anything else is a stored-format question.
  The release note is Yue's too.

  *Next* (task 8, for a runner):
  1. Build the ruling in the magnetic path: `attach_stationary_intervals` runs `profile_interval` on
     the modulus of each flagged site, on the answer fit and on the attempt a series keeps, never on
     a trial or a rung. A `MOMENT_UNSUPPORTED` site is flagged too, with #1322's one-sided interval.
  2. Condition 2 with the amendment: a drop below the fit under the cut is quoted with the drop
     named. A drop of a full cut or more withholds the interval, and the reader gets the lowest point
     and the pointer to refit, never the esd.
  3. Condition 3: rewrite `MOMENT_ANGLE_STATIONARY`'s message to quote the modulus's interval. Then
     update the help entry, the skill row in `references/magnetic.md` and the audit rows it moves.
  4. Tests for each condition, revert-checked, on the two-site set in
     `tests/test_stationary_moment_angle.py`. Run `tests.reader_output`.
  5. At the PR, bring Yue's three parts above and the release note to Yue. Then close.
  Optional, unchanged from the 2026-11-02 entry: `MOMENT_UNSUPPORTED` for joint fits.

- **2026-11-02** — tasks 2-7, PR #1322. A moment refined to zero now gets an honest uncertainty. Before, the fit reported m ≈ 0 with an error of 10 000-200 000 μ_B and no warning, and asking for the likelihood interval returned a zero-width answer. Now the result carries a warning that the data do not support the moment, and the interval runs from 0 to about 0.06 μ_B. The interval also stopped refitting a model larger than the fit: a weak phase's held cell stays held while its scale is profiled. The maintainer still has one choice: whether a modulus beside an angle the stationary test zeroed should get its interval computed unasked. This branch only points at the call, because each such interval costs 7-58 s on a fit of 1-8 s.
  *Done.* `profile_interval` (`strategy/parameter_interval.py`): every refit freezes the answer stage's `StageResult.held`; a first probe already past the threshold steps back in, each step from a fresh trial at the fit, then solves the end in log distance; a step back that does not lower Δχ² stops the side on `"error"` with a message; a modulus whose sign the data cannot see (`_sign_is_unseen`: one moment block in the phase, or free angles) keeps its sign, so 0 is a bound and a modulus within 0.01 esd of it is one-sided. `MOMENT_UNSUPPORTED` (warning) on `result.diagnostics`, from `report.magnetic.moment_supported`, the same function behind `MomentEvidence.supported`. `MOMENT_ANGLE_STATIONARY` names its sites' moduli as conditional and points at `profile_interval`. Audit rows (tier 1), help entry, skill rows, theory and guide paragraphs. Task 1: scale and occupancy settled by Claude as no default interval, under the reporter's measurement that every rule covers there.
  *Measured* (macOS arm64, `[dev]`). Repro 2 on the base tree `816fe35ea`: seeds 3, 4, 8 at m = 6e-9, −8.5e-8, 8.6e-8 ± 2.4e5, 1.7e4, 1.5e4 μ_B, interval [v, v], 10-14 refits. On this branch: [0, 0.0646], [0, 0.0595], [0, 0.0522] μ_B, one-sided at cut 3.72, 4.07, 3.26, `fit_is_minimum=True`, 16-21 refits. Held-phase fixture at level 0.9999: on the base tree the refits at 4 esd of scale freed the held cell and moved it 5.2 → 5.19904 Å; here it stays at 5.2. Two-site Pnma weak site (Mn2, 0.7 μ_B, `_fit(0.0, seed=s)`, s = 0-19): esd covered 19 of 20, profile 18 of 20 (seed 15 no end, seed 19 lower end 0.7001); 17 of 20 estimates above the truth, so the bias #1075 measured is there, but N = 20 cannot show its 0.83. A modulus profile cost 6.8-58.3 s, 24-38 refits, on fits of 1.1-8.4 s. `python -m tests.reader_output`: unchanged (its standard fit has no moment). Fast selection on `18ca19476` (this branch with main merged; macOS arm64, `[dev]`, through the shift's suite lock, 8:51): 13288 passed, 310 skipped, 32 xfailed, 4 failed. Three were this branch's and are fixed in `849969c48`, each re-run alone green: `MOMENT_UNSUPPORTED` had no silence pair, the committed GUI help-key fixture was stale, and the interval guide's extinction end moved 0.749 → 0.748 µm² (its first 1-esd probe overshoots, so it now steps back in and solves to 1e-3 of the distance rather than of the esd; guide and page updated). The fourth, `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`, fails alone too, on the Jupyter kernel spec pointing at a deleted venv: the machine's, not the branch's. Added to the fast selection: 5 tests (3 in `test_modulus_interval.py`, 1 in `test_held_phase.py`, 1 silence pair); 3 slow. The full selection did not run.
  *Gotchas.* On seed 15 the refits at the fitted modulus end 5.1 χ² above the fit (cut 5.0), and on 8 of 20 seeds a refit finds χ² below it: a refit of a fit whose angles the test zeroed does not reproduce that fit's χ². Not diagnosed, and open here. Probes are in the maintainer-local `~/.cache/ghostshift/rietx/wp-2060/probe/` (`coverage.py`, `seed15.py`). Before this branch a step-back from an absurd probe started from that probe's state and stayed there (Δχ² 839 144 at the fitted value); the fresh trial per restart is the fix, and `set_values` of the fitted rows cannot be, since a coordinate DOF is rederived to zero.
  *Review.* `/code-review high --fix` applied six: the fresh-trial restart, "on a single fit" in the stationary suggestion, one table build, the seed-4 fit cached, two style. Declined: `MOMENT_UNSUPPORTED` in `multi.py` (a joint fit has no `profile_interval`, so it needs its own suggestion, and it changes what a joint fit returns); `lower = 0.0` above a value of −5e-8 on the floor, and a user-tied second modulus counted as a block (both conservative); quoting the constants in the help text. The generality review's fixes landed: the dead-column reason and "m ≥ 0" now say "where the moment's sign is unseen", and a message line with no writer went. *Generality*: see the PR body; it rated `MOMENT_UNSUPPORTED` and its suggestion weak (the 3σ cut is the unaudited `MOMENT_SUPPORT_SIGMA`'s, one family, and 2-3σ moments are published), `_sign_is_unseen` and the frozen set hold, the step back holds (reusing three tier-3 constants), and the stationary message weak (it builds the pointer option of an open choice). Author: the cut is the FitReport's existing verdict, carried to the result unchanged; auditing `MOMENT_SUPPORT_SIGMA` is its own row's work.
  *Forward.* WP-1955: the step fix should change repro 1's [0.0, 0.0], not re-run. WP-2068 closes in PR #1326, so the seed-15 χ² mismatch above stays in this WP rather than in its Inherited. That PR's analytic angle block should lower the 7-58 s profile cost; not re-measured here.
  *Next.* The maintainer rules task 1's modulus half at the PR: pointer (built) or the interval computed unasked. Then, if pointer stands, close the WP. Optional: `MOMENT_UNSUPPORTED` for joint fits with a joint-fit suggestion.
- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1075). Checked against the tree at c0e32ab29: repro 2 reproduces on seeds 3, 4 and 8 (m ≈ −5e-7 ± 1.5e4 to 1.2e5 μ_B, `converged`, no diagnostic, `profile_interval` [v, v]); `FitReport.magnetic` says `supported=False`; `profile_interval`'s refits are `run_stage` calls that re-decide WP-1301's hold. No open WP owns it: WP-2002 (B2's intervals) and WP-1929 (the stationary test) are closed, WP-1955 owns only the FCJ column, and WP-2004 tiers `report/` codes and does not touch `profile_interval`. *Next:* the ruling.
