# WP-2311 — A Pawley fit does not depend on the intensity units

Milestone: unscheduled · Status: 🔄 2026-11-26 — claimed by @yue-here (cloud session)
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-26 — the first of WP-2062's bug tasks, and the only one whose answer can reopen that WP's decision 0; every other site move there waits on it

## Goal

A Pawley fit of a pattern gives the same answer whether its intensity and σ are
in counts, in count rate or divided by their maximum. Either the cause of the
measured dependence is found and fixed, with a test that rescales a pattern and
asserts the answer does not move, or it is shown to belong to the Pawley method
in rietx's form. In the second case, decision 0 of WP-2062 (replace Le Bail with
Pawley rather than repair Le Bail) goes back to Yue.

## Context

**The measurement** (WP-2011 § Re-measured 2026-10-28, probe 9, run on
2026-10-28 on macOS arm64 with `[dev]`). Synthetic LaB6's true cell validates at
Rwp 0.164 on counts. With the intensity and σ both divided by the maximum count
(2721), it validates at 0.262. χ² is the same function in both cases, since σ
scales with the intensity. Le Bail reads 0.2339 and 0.2338, so it is invariant.
What else was measured:

- **Against an intensity factor *f*:** Rwp 0.164 for *f* ≥ 1, 0.171 at 0.1,
  0.266 at 0.01 and at 0.001. At 1e-4 the last stage ends at `max_iter` (Rwp
  0.200). So the failure gets worse as the numbers get small, not just
  different.
- **The widths diverge:** `u` 1e-5 against −4.3e-4, and `y` −1.9e-4 against
  −1.3e-3. The divergence starts in the zero-shift stage of the validation
  plan (`indexing.workflow.validation_plan`).
- **Ruled out, each by a rerun that read the same:**
  - the off-data floor `PAWLEY_OFF_DATA_SCALE_FLOOR`: this fit has no off-data
    reflection, and setting the floor to 1e-12 changes nothing;
  - the LM driver's curvature probe: disabled, same reading;
  - the re-picked peak list: the base list gives the same reading.
- **On real data:** across nine real true cells (SRM 660c, 11-BM NAC, FAP,
  corundum, brucite, zincite, zircon, fluorite, magnetite), no scaled reading
  moved by more than 2e-4. So the effect is measured on one synthetic pattern
  only, and is not yet known to reach a real one.

**Why it matters.** Pawley already runs for every `index_pattern` user (WP-2011
switched the candidate validation to it). WP-2062 will make it the
structure-free fit at four more sites. A fit whose answer depends on the units
of the file is wrong on count-rate and normalised exports, and nothing flags
it. WP-2062 decision 0 (2026-11-01, Yue) chose Pawley, with Pawley's known bugs
fixed first and this one first among them. Its brief named this finding as the
one that would favour route (b) instead: re-extracting the Le Bail intensities
once per least-squares iteration.

**Where to look.** These are suspects, none of them measured:

- Anything in the Pawley path that sits in *intensity* units, not in units of σ
  or of a column scale:
  - the equal-split restraint on overlap groups, `PAWLEY_OVERLAP_LAMBDA`
    (`CompiledModel.build_pawley_restraint`). Its λ is weighed against what?
  - the block's lower bound at zero, and how close the seed sits to it;
  - the seed itself: one Le Bail partition (`refine.PAWLEY_SEED_CYCLES` = 3);
  - LM's initial damping, and any absolute tolerance (`xtol`, `gtol`, a step
    floor) that is not relative to the column scale.
- Column scaling. `statistics.column_rescale` is the one place a column is
  squared (WP-1463). Check whether the intensity block passes through it, and
  whether the dense, sparse and projected-CG paths all scale the same way:
  WP-1953 and WP-2011's option (c) added the last two, and dispatch is
  `BVLS_MAX_COLUMNS` and `PAWLEY_SPARSE_DENSITY`. LaB6's true cell has few
  enough reflections to sit on the dense path.
- The background. The P-spline penalty's λ is weighed as √(λ·m)/σ̄, frozen at
  compile (WP-1454). Check that Chebyshev and P-spline seeding are
  scale-free too.

**Reproducing it.** The probe scripts are in `docs/wp/2011-probe/`.
`probe2_lebail_vs_pawley.lab6_data(seed)` builds the synthetic pattern from
`tests.test_indexing_consensus._true_models` (2θ 15-145° at 0.02°, Poisson
noise). `probe9_constants.py lab6` runs the shipped `validate_by_lebail` (now
Pawley) under the `scaled` variant. The tree has moved since 2026-10-28, so
rerun before believing the numbers: WP-2011's sparse and Cholesky paths
landed, and so did WP-1542's settled Le Bail partition.

**The tier of each rule this WP adds.** None, if it ends in a fix: scale
invariance is arithmetic, and the test is an exact identity (rescale y and σ by
*f*; the fitted intensities scale by *f*, and every other parameter and every
Rwp stays put to a tolerance stated by the solver's own `ftol`). A fix that adds
or changes a threshold names its tier under
[generality § The rule](../milestones/generality.md#the-rule).

## Non-goals

- WP-2062's other bug tasks (`compare_rivals` and the exchangeability scan in
  Pawley mode, cross-phase overlaps) and its site switches and rename. That WP
  keeps them.
- The picker's failure on a normalised pattern with no σ column, where the
  Poisson fallback puts every point under the noise and `screen.fwhm_at` raises
  on an empty peak list (WP-2011 § Found on the way). That is WP-1956's screen.
- Le Bail's zero clip on net counts (#1552), which WP-2062 inherits.

## Findings (2026-11-26, Linux x86-64, `[dev]`, tree `dd94fd32`)

Probes in `docs/wp/2311-probe/`. Each one is `.venv/bin/python docs/wp/2311-probe/<file>`
from the worktree root.

1. **The reading reproduces, but it is not a dependence on units**
   (`probe1_rerun.py`, `probe2_start_vs_units.py`). With intensity and σ scaled
   by *f* and the instrument left as declared, the true cell reads Rwp 0.1639,
   0.1713, 0.2660 and 0.2660 at *f* = 1, 0.1, 0.01 and 1e-3. At 1e-4 it reads
   0.1639, where on 2026-10-28 it ended at `max_iter`. Re-picking the peaks from
   the scaled pattern changes nothing. But `_true_models()` declares the f = 1
   background in counts, Chebyshev (30, −4, 1), so that fit *starts* with a
   background 1/f too high: the first stage's starting cost goes as 1/f² (5.3e3,
   8.0e6, 9.6e8, 9.8e10). With the declared background scaled as well, every *f*
   from 1 to 1e-4 reproduces the f = 1 fit, with the same cost at the start and
   end of every stage and the same widths to six figures. With f = 1 data and the
   declared background ×10 and ×100, probe 1's 0.1713 and 0.2660 come back
   exactly. **The Pawley fit is invariant under a change of units. It depends on
   where the background starts**, and the 2026-10-28 probe varied both at once.
   So the finding does not bear on WP-2062's decision 0 as filed.
2. **The cause is the equal-split restraint's floor** (`probe3_seed_state.py`,
   `probe4_restraint_scale.py`). The Pawley seed is one Le Bail partition of
   max(y_obs − bkg, 0). A background above the data partitions nothing, so the
   seed leaves reflections on `LEBAIL_INTENSITY_FLOOR` (1e-10): 6 of 28 at ×10,
   all 28 at ×100. `build_pawley_restraint` weights each overlap group's rows by
   √λ/s, with s = max(mean(I_group), 1e-10). That 1e-10 is an absolute intensity,
   unaudited and inline. An emptied group therefore gets weight 5e9, against 0.04
   to 0.06 on the true start. Every later stage rebuilds s from the group's
   stuck value, so the weight stays 5e9 to the last stage, and 2 (×10) or 10
   (×100) reflections end there. The rows sum to zero, so the group's sum is in
   their null space and is free in exact arithmetic. But column equilibration
   divides each member's column by a norm of ~5e9, so moving the sum takes a
   scaled step of order 1e10, and the trust region never gets there. Changing
   the group's scale alone, with the off-data ridge untouched, recovers the true
   start's answer exactly (cost 3415.253, same u, w, y) at ×10 and ×100: with
   the group rows dropped, with s floored at the phase's largest on-data
   intensity, and with s floored at ρ times it for every ρ from 1 down to 1e-8.
   At ρ = 1e-9 the lock returns (Rwp 0.1713 at ×10, 0.2634 at ×100). No variant
   moves the true start's fit.
   Suspects not reached: the off-data floor binds nowhere here (this fit has no
   off-data reflection, as on 2026-10-28). The LM damping and tolerances, column
   scaling paths and background seeding are behind the restraint, not beside it:
   fixing the restraint alone restores the answer.

## Tasks

- [x] Rerun the measurement on the current tree: synthetic LaB6's true cell,
      validation plan, *f* ∈ {1, 0.1, 0.01, 1e-4}. If the dependence is gone,
      bisect to the commit that removed it, record it, and close. *(2026-11-26:
      reproduces, but as a start dependence, Findings 1.)*
- [x] Find the cause: the first stage and quantity where the two fits part,
      with the suspects above checked one at a time and each result recorded.
      *(Findings 2: the group scale's 1e-10 floor.)*
- [ ] Fix it, or show it belongs to the method, and if so hand decision 0 back
      to Yue through WP-2062 (an `### Inherited` entry there).
- [ ] Test: a Pawley fit of one pattern at *f* = 1 and *f* = 1e-3 (intensity and
      σ both scaled) gives the same cell, widths and Rwp, and intensities in
      ratio *f*. Fast, synthetic, with `dispersion` declared explicitly.
- [ ] Re-measure the nine real true cells and the indexing acceptance suite, and
      say which pinned numbers moved.
- [ ] Tick WP-2062's unit-dependence task with a pointer here.
- [ ] Skill: none expected. A fix removes a trap and adds no rule an agent
      needs. If the result is "belongs to the method", the trap ("Pawley in
      rietx depends on intensity units") gets a row.

## Acceptance

The scale test passes, and so do the fast suite and the indexing acceptance
suite, with no ranking or class decision lost.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Pawley, G. S. (1981). *J. Appl. Cryst.* **14**, 357-361.
- van der Sluis, A. (1969). *Numer. Math.* **14**, 14-23 (column equilibration).
- WP-2011 § Re-measured 2026-10-28 and its probes 2, 5 and 9; WP-2062
  § Decisions, decision 0.

## Handover log

- **2026-11-26** — filed, split out of WP-2062. WP-2062 owned this as its first
  bug task. Yue asked for it as its own WP, because it is a self-contained
  debugging job and its answer can reopen WP-2062's decision 0. That WP now
  depends on this one. Nothing run. *Next:* rerun the measurement on the
  current tree.
