# WP-2311 — A Pawley fit does not depend on the intensity units

Milestone: unscheduled · Status: ✅ 2026-11-26 — a start dependence, not one on units; the overlap restraint's scale is floored relative to its phase (PR #1857), and the off-data ridge's floor goes to Yue through WP-2062
Track: What fires, and what stays silent
Depends on: —

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
3. **On the nine real true cells** (`probe5_real_truths.py`, the shipped validation,
   peak-list path, the f = 1 peak list handed to every variant). Columns:
   Rwp with the old floor and with the fix, on counts (`base`), and with
   intensity, σ and the declared background divided by the maximum count
   (`units`); `bound` is the number of groups the new floor raised, per stage.

   | true cell | base, old | base, fix | units, old | units, fix | bound |
   |---|---|---|---|---|---|
   | SRM 660c | 0.092695 | 0.092695 | 0.092695 | 0.092695 | 0 |
   | 11-BM NAC | 0.126143 | 0.125965 | 0.125965 | 0.125965 | 13 to 14 from stage 2 |
   | GSAS-II FAP | 0.078541 | 0.078539 | 0.078541 | 0.078539 | 1 |
   | corundum | 0.139386 | 0.139386 | 0.139386 | 0.139386 | 1 to 2 |
   | brucite | 0.166897 | 0.166897 | 0.166897 | 0.166897 | 1 |
   | zincite | 0.104809 | 0.104809 | 0.104809 | 0.104809 | no group |
   | zircon | 0.147447 | 0.147446 | 0.147441 | 0.147441 | 1 |
   | fluorite | 0.178806 | 0.178806 | 0.178806 | 0.178806 | 0 |
   | magnetite | 0.180152 | 0.17952 | 0.180051 | 0.17952 | 6 from stage 2 |

   No unmatched count moved and no status moved; every fit converged. So
   **the lock reached real data too, by a second route**. No real seed emptied
   a group (the first stage's `bound` is 0 everywhere). On NAC, FAP, corundum,
   brucite, zircon and magnetite, though, a group ended the first stage under
   1e-4 of its phase's strongest reflection. From the second stage on, the old
   floor weighed it by the reciprocal of its own near-zero mean, or by 1e10
   where the mean sat under 1e-10 counts: a weight that depends on the
   units. Where that moved the answer
   (NAC, FAP, magnetite, zircon), it is the unit dependence WP-2011 measured
   on real data: at most 2e-4 then, and here NAC 1.8e-4 and magnetite 1.0e-4
   with the old floor, counts against units. With the fix, NAC, FAP and
   magnetite read the same in both units. That invariance is the evidence;
   that the fixed Rwp is also the lower is a fact, and it is not the evidence.
   Zircon alone keeps a 5e-6 gap, Finding 4.
   The `absent` count does move between variants (NAC 17 against 3, zircon 19
   against 0). That is the probe's artefact: the line screen adds the peak
   list's areas to the data's envelope (`indexing/screen.py`,
   `PatternScreen._add_pattern`), and the probe handed scaled data a peak list
   in counts. Zircon re-picked in the scaled units reads 19 in both (78 peaks
   picked against 79, the picker's own concern, WP-1956).
4. **What remains: the off-data ridge's floor** (`probe6_ridge_floor.py`).
   `PAWLEY_OFF_DATA_SCALE_FLOOR` = 1.0 is in counts. Scaled to a maximum of 1,
   the phase's largest on-data intensity falls to 0.09 to 0.18 on zircon and
   corundum, so the floor binds. With it at 1e-10, both read the same on counts
   and in the scaled units to seven figures (zircon 0.1474465, corundum
   0.1393856). With it at 1.0, the gap is 5.7e-6 and 7e-7. Not changed here.
   The constant is tier 3 at 1.0 by WP-2011 ruling 3 (2026-10-28), and it also
   guards a phase whose every on-data intensity sits on the floor, where no
   intensity offers a relative anchor. Handed to Yue at handover.
5. **A phase the seed emptied entirely** (`probe7_one_stage.py`; the handover's
   review found it). When every on-data intensity of a phase sits on the floor,
   the relative floor has nothing to stand on, so the group rows still weighed
   5e9 in the first stage. The staged plans above recover because the second
   stage rebuilds the rows, but a one-stage plan has no rebuild. On the
   overlapped Cu-LaB6 fixture, background ×100, one stage freeing background,
   cell, w and the shift: Rwp 0.2365 with two reflections at zero after 52
   iterations, against 0.1620 from the true start. Fixed by building no group
   rows for such a phase in that stage, so its splits are flat directions for
   the stage. The same plan then reads 0.162014 from either start, in 66
   iterations from the high one.
6. **A start the restraint does not explain** (`probe7_one_stage.py`,
   `probe8_one_stage_70.py`, after the generality review asked for factors
   between ×10 and ×100). The same one-stage plan reads 0.162014 at ×1, ×12,
   ×15, ×20, ×30 and ×50, and 0.449137 at ×70. The restraint is not the cause
   there. With the group rows dropped, ×70 reads 0.449137 too, and the
   largest row weight is 505, not 5e9: the seed left 19 of 20 reflections on
   the floor, and the relative floor held. So the one-stage solve itself lands
   in another basin when the background starts 70× high and almost every
   intensity starts at zero. Every staged plan measured here refines the
   background first and recovers. Not fixed here, since it is the seed and
   solve, not this WP's restraint. Forwarded to WP-2062, whose bug list owns
   the Pawley seed.

## Tasks

- [x] Rerun the measurement on the current tree: synthetic LaB6's true cell,
      validation plan, *f* ∈ {1, 0.1, 0.01, 1e-4}. If the dependence is gone,
      bisect to the commit that removed it, record it, and close. *(2026-11-26:
      reproduces, but as a start dependence, Findings 1.)*
- [x] Find the cause: the first stage and quantity where the two fits part,
      with the suspects above checked one at a time and each result recorded.
      *(Findings 2: the group scale's 1e-10 floor.)*
- [x] Fix it, or show it belongs to the method, and if so hand decision 0 back
      to Yue through WP-2062 (an `### Inherited` entry there). *(Fixed:
      `PAWLEY_GROUP_SCALE_FLOOR_REL` = 1e-4 floors a group's scale at that
      fraction of its phase's largest on-data intensity; the absolute 1e-10
      survives only as the guard for a phase nothing has measured. Audit row
      tier 1, numerical floor, for the judge at handover. The equation is the
      Theory tab's `fm-pawley-split`. Decision 0 is not handed back: Findings 1.)*
- [x] Test: a Pawley fit of one pattern at *f* = 1 and *f* = 1e-3 (intensity and
      σ both scaled) gives the same cell, widths and Rwp, and intensities in
      ratio *f*. Fast, synthetic, with `dispersion` declared explicitly.
      *(`test_pawley.py::test_a_pawley_fit_depends_neither_on_the_units_nor_on_a_high_background_start`,
      ~3 s: units ×1e-3 with the declared background scaled too, and a start
      ×100 high. Agreement is under 1e-6 esd and 1e-14 in Rwp, against
      tolerances of 1e-3 esd and 1e-6. With the floor set to 0 it fails on the
      start case, Rwp 0.214 against 0.162.)*
- [x] Re-measure the nine real true cells and the indexing acceptance suite, and
      say which pinned numbers moved. *(Findings 3: the validation's Rwp
      moves on NAC (−1.8e-4), magnetite (−6.3e-4), FAP (−2e-6) and zircon
      (−1e-6); no unmatched count and no status moves. No pinned number
      failed: the fast suite reads 15795 passed, 465 skipped, 30 xfailed
      (2026-11-26, Linux x86-64, `[dev]`, alone), and
      `tests/test_acceptance_indexing.py` 45 passed, 0 skipped,
      2026-11-26, Linux x86-64, `[dev]`, alone, so no ranking or class
      decision was lost.)*
- [x] Tick WP-2062's unit-dependence task with a pointer here.
- [x] Skill: none expected. A fix removes a trap and adds no rule an agent
      needs. If the result is "belongs to the method", the trap ("Pawley in
      rietx depends on intensity units") gets a row. *(None: the result is a
      fix.)*

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

### 2026-11-26 (2nd session) — closed: a start dependence, and the overlap restraint's floor

Rietx's Pawley fit never depended on the units of the data. The 2026-10-28 probe rescaled the
pattern but left the declared background in counts, so the fit started from a background up to
100× above the data, and that start was what moved the answer. Scaled together, data and
background give the identical fit at every factor from 1 to 1e-4. What made the start matter
was a fixed tiny number in the restraint on overlapped reflections. A group the seed or the
first stage left empty got a near-infinite weight and stayed empty. On real data that weight
also depended on the units, which is the 2e-4 drift WP-2011 saw. The weight is now relative to
the phase, so counts and scaled units agree on eight of nine real true cells. WP-2062's
decision 0 (Pawley everywhere) stands. Left open: the off-data ridge's floor (the ninth cell,
5.7e-6), and a one-stage fit from a 70× background, which fails for a reason the restraint does
not explain.

- **Done.** Findings 1-6 and probes 1-8 (`docs/wp/2311-probe/`). The fix is in
  `CompiledModel.build_pawley_restraint`. A group's scale is now
  max(mean, `PAWLEY_GROUP_SCALE_FLOOR_REL` × the phase's largest on-data intensity), with
  ρ = 1e-4. A phase whose every on-data intensity sits on `LEBAIL_INTENSITY_FLOOR` gets no
  group rows for the stage. The audit row is entered at tier 1. Theory tab: `fm-pawley-split`
  plus a paragraph, with ρ injected through `sphinx_shared.py`. Tests:
  `test_a_pawley_fit_depends_neither_on_the_units_nor_on_a_high_background_start`, covering
  units ×1e-3 and a start ×100 under the default plan, and
  `test_a_one_stage_pawley_fit_from_a_seed_that_partitioned_nothing_is_not_locked`. Each was
  made to fail on purpose, with the floor at 0 and with the skip off: Rwp 0.214 and 0.2365
  against 0.162. WP-2062's unit-dependence task is ticked, and its priority re-rated.
- **Measured** (Linux x86-64, Python 3.12, `[dev]`, 4 CPUs, each suite run alone, final tree
  `02a99373`, which equals merged main because `origin/main` had not moved past `dd94fd32`):
  - Fast suite: 15796 passed, 465 skipped, 30 xfailed, ~43 min. The pre-review run read
    15795 / 465 / 30. Passed+skipped moved by +1, the one test added between the runs, and the
    branch adds two tests in all. The base's count was not measured locally; that is CI's job.
  - `tests/test_acceptance_indexing.py`: 45 passed, 0 skipped, ~20 min. The pre-review run
    also read 45 passed.
  - Added tests' cost, local junit, one run on this machine: 0.95 s and 0.36 s (1.31 s, both
    in `test_pawley.py`), not near the slow tail.
  - Real cells: Findings 3's table. The validation's Rwp moved on NAC (−1.8e-4), magnetite
    (−6.3e-4), FAP (−2e-6) and zircon (−1e-6). No unmatched count and no status moved.
  - Full suite: not run. The WP's acceptance names the fast and indexing-acceptance suites. On
    this 4-CPU container the fast suite alone took 43 min, so the full selection, which carries
    the Pawley-using acceptance suites (NAC, FAP), is left to the nightly `full` job. Read
    tonight's log for `test_acceptance_nac.py` and `test_acceptance_fap.py` before releasing.
- **Review** (`/code-review high --fix`): it applied three fixes. It corrected the 5e9
  comment's arithmetic, changed the split-esd text where the floor binds (constant comment,
  docstring, manual), and added the scale test's path-set and None-esd asserts. It skipped
  five findings. One of the five was real: a phase the seed empties entirely still locked a
  one-stage plan (0.2365). It is fixed here as the unmeasured-phase skip, with its own test.
  Of the other four: `PAWLEY_OFF_DATA_SCALE_FLOOR` goes to Yue (below), and the 1e-10 in
  `_pawley_unresolved_diagnostics` goes to WP-2062, unmeasured. The tier question is below
  under Generality. The cross-platform spread of the scale test's tolerance was not measured.
  It is Linux only, and the docstring now says so. The measured agreement (1e-14 in Rwp,
  under 1e-6 esd) sits three or more decades inside the bars.
- **Generality** (the `generality-review` judge, sections pasted unedited, its two headings demoted to `####` to sit inside this entry):

  #### `rietx.model.forward.PAWLEY_GROUP_SCALE_FLOOR_REL` (constant, 1e-4, entered at tier 1)

  **Verdict: `weak`, and the tier is 3, not 1.** The evidence for having a floor that scales with the phase is strong. The evidence for the value 1e-4 comes from one synthetic family, and the committed probe does not reproduce the edges of the window. A tier-3 constant judged anything but `holds` goes to the maintainer. By my reading this is not his trigger area: the constant sets how strongly an always-on restraint holds a split, not the level at which a warning or an action fires. It does feed the esd that `PAWLEY_OVERLAP_UNRESOLVED` (an info-level code, not a warning) tests against `PAWLEY_UNRESOLVED_REL`.

  Terms used below. A Pawley fit gives each reflection its own free intensity. An overlap group is reflections closer than 0.5 FWHM. The equal-split restraint is soft rows pulling a group's split toward equal, weighted √λ/s. The seed is one Le Bail partition of max(y_obs − background, 0), floored at `LEBAIL_INTENSITY_FLOOR` = 1e-10. ρ is this constant.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "an overlap group's restraint scale is never under this fraction of its phase's largest on-data intensity" (`_audit.py:4583-4592`) | It decides how wide the prior on a weak group's split is. Any group whose mean is under 1e-4 of the phase's strongest reflection is held more loosely than "esd ≈ its own intensity". The split values, their esds and so the `PAWLEY_OVERLAP_UNRESOLVED` test all depend on it. It binds on real data: on 6 of the 9 real cells, 13-14 groups per stage on 11-BM NAC (WP file, Findings 3 table). | Stated correctly, but understated: it shapes reported esds, not only conditioning |
  | 2. Kind of ambiguity | No `ambiguity` field; a constant row needs none. Implicitly kind 1: "numerical floor" | Arithmetic does settle the *relative form*: a floor in counts is a unit dependence, and Findings 1-3 show it. Arithmetic does not settle the *value*. On the one family swept, every ρ from 1 to 1e-8 gives the same fit, so the data are indifferent there and 1e-4 is picked inside the window. The constant's own tag says so: "*(Chosen: WP-2311, 2026-11-26 — four decades inside that window either side…)*" (`forward.py:739-740`). | Kind 1 holds for the form, not the value |
  | 3. Case against acting | Comment: "below it a group is weaker than any line a pattern resolves" (`forward.py:739-740`) | (a) That sentence carries no measurement. A group under 1e-4 of the strongest line is a real intensity on high-dynamic-range data, and the floor binds on 11-BM NAC. Whether those are lines the pattern resolves is not shown. (b) Other competent choices exist. No group rows at all is what GSAS-II (ties only exact overlaps, \|Δd\|/d < 1e-4), TOPAS, BGMN and MAUD do by default for near-overlaps (`docs/practice.md:640-645`, checked in this repo). Probe 4's `no_groups` variant gave the same LaB6 answer. ρ = 1 also gave it. RIETAN-FP's hybrid step instead sets a group's members exactly equal (`practice.md:643`). (c) The anchor (the phase's largest *seeded* intensity) is itself read off the seed. That contradicts "never read off a seed the partition emptied" (`_audit.py:4586`). If a seed partitions almost nothing, ρ·top is tiny and the rows weigh ~5e9 again. This is from reading the code, not measured. Background factors between ×10 and ×100 were not swept (`probe4_restraint_scale.py:93`, g ∈ {1, 10, 100}). | Moderate: the value has live alternatives and an unmeasured rationale |
  | 4. Case for acting | "it replaced an absolute 1e-10 that weighed an emptied group's rows at 5e9 and left its sum where the seed put it" (`_audit.py:4587-4588`); Findings 2 (WP file, lines 117-139) | Measured cost of the old absolute floor: on synthetic LaB6, Rwp 0.1713 at ×10 and 0.2634-0.2660 at ×100 against 0.1639 from the true start. On real data the old floor gave counts and units different answers: NAC 1.8e-4 and magnetite 1.0e-4 in Rwp. With the fix, NAC, FAP and magnetite read the same in both units (Findings 3). The author explicitly declines to use the lower Rwp as evidence ("that the fixed Rwp is also the lower is a fact, and it is not the evidence", WP line 170). | Strong, for having a relative floor |
  | 5. Tier and source | "tier=1 … numerical floor" (`_audit.py:4583-4584`) | Tier 1 takes a numerical floor such as `rcond`, or a numerical setting "once a test shows its error stays under a stated bar over every input it claims to handle" (`generality.md:56-61`). This floor does neither. It binds on meaningful intensities, not rounding-level ones (compare `LEBAIL_INTENSITY_FLOOR`, "ten orders under one count", `_audit.py:4560-4563`). The test pins one fixture at the shipped value and sweeps nothing. The value is chosen inside a window rietx measured, which is tier 3 ("measured on NAC or a WP number", `generality.md:82`). Tier 2 is unavailable: none of the seven programs has an equal-split restraint with such a floor (`practice.md:637-646`, checked here). At tier 3 the row lacks `grounds` and `approved`, which the `Row` docstring requires (`_audit.py:112-113`). Not `invariant`: no test asserts a margin over ρ. | Tier 3; the row as written does not meet tier 1 |
  | 6. Dataset families and references | "Synthetic LaB6, declared background 1x, 10x and 100x … every value from 1 to 1e-8 gives the true start's fit (cost 3415.253…), 1e-9 locks again" (`_audit.py:4588-4591`) | **The window rests on one family.** Probe 4's LaB6 and the test's Cu-LaB6 fixture are both synthetic LaB6, and both are development data, since the value was chosen on them. The reference is the fit from the true start, the package's own result, so this verifies and does not validate. The committed `probe4_restraint_scale.py:80-81` runs only ρ = 1, 1e-2 and 1e-4. The quoted 1e-6, 1e-8 and 1e-9 readings cannot be reproduced from it. The real cells come from four sources: SRM 660c, 11-BM NAC, GSAS-II FAP (lab Cu, `tests/data/README.md:35`) and the CPD round robin. They are all development data (WP-2011 probes 5 and 9) and ran at ρ ∈ {0, 1e-4} only (`probe5_real_truths.py:79`). Their reference is the same pattern in other units, which shows any relative floor is unit-invariant. That is an identity check (verification), and it says nothing about 1e-4 against another value. The edge on which it fails is stated: 1e-9 on synthetic LaB6. Unmeasured: where that edge moves with counting statistics or a phase's dynamic range, which are the things this row depends on. | Fails the three-family ground for the value |
  | 7. Record that it fired | none given | No field or code says a group's scale was floored. Probe 5 counted it through a monkeypatch (`bound`). Its effect on the answer reaches the reader only through the split esd that `PAWLEY_OVERLAP_UNRESOLVED` quotes. | Finding: nothing records it |

  Would change the verdict: a ρ sweep (1, 1e-2, 1e-4, 1e-6, 1e-8) on at least three real families where the floor binds (11-BM NAC, GSAS-II FAP, a CPD phase such as magnetite or zircon), reporting the validation readings, the split esds and the `PAWLEY_OVERLAP_UNRESOLVED` count against each family's reference; and probe 4 committed with the 1e-6 to 1e-9 variants it is quoted for.

  #### Inline fallback in `CompiledModel.build_pawley_restraint`: a phase with every on-data intensity `<= LEBAIL_INTENSITY_FLOOR` gets no group rows for the stage

  **Verdict: `weak`.** The evidence for acting is stronger: the measured lock is real, and dropping the rows puts the fit where four of the seven programs always are. But nothing records that the fallback fired, the claim about the esd is untested, and its trigger only catches a seed that is exactly empty. It is not a table row, so it goes to the maintainer whatever the verdict. Its threshold is `LEBAIL_INTENSITY_FLOOR`, now also the trigger of an automatic action, which is his named trigger area.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "Where every on-data intensity of a phase sits on `LEBAIL_INTENSITY_FLOOR` … there is no intensity to floor against … Its splits are then flat directions for the stage" (`forward.py`, `build_pawley_restraint` docstring, ~4129-4137) | For one stage it switches off an always-on correction (the equal-split restraint) for that phase. It touches the final answer only when that stage is the last one: a one-stage plan with `closing_window_tol=None`, as in the test. Every later stage, including the default closing stage, rebuilds the rows (`refine.py:5373`; `multi.py:3185` for a joint fit). It fires only on the seeded path (`refine.py:4820`, `if not carried`). | Clear |
  | 2. Kind of ambiguity | Not stated; implicitly arithmetic ("any scale written here would be a number of counts") | Kind 1 is reasonable. But the premise is too strong: the observed pattern still scales with the units (for example the net counts times a profile area), so the intensity block is not the only thing a scale could be relative to. That option was not tried. | Kind 1, premise overstated |
  | 3. Case against acting | none given | (a) RIETAN-FP's hybrid step sets near-overlapped intensities exactly equal (`practice.md:643`). A refiner following it would keep the split held, not free. A hard equal constraint would hold the split without the lock. (b) The trigger is `<=` the partition floor, so a phase where one on-data reflection holds even a sliver above 1e-10 escapes the fallback. Its groups then get s = max(mean ≈ 1e-10, 1e-4·top). That is ~5e9 again whenever top is under ~1e-6 counts. This is from reading the code, not measured. The probe swept background factors 1, 10 and 100 only, and the case lies between 10 and 100. | Weak to moderate |
  | 4. Case for acting | "Rwp 0.2365 with two reflections at zero after 52 iterations, against 0.1620 from the true start … The same plan then reads 0.162014 from either start, in 66 iterations" (WP Findings 5, lines 187-197); `test_a_one_stage_pawley_fit_from_a_seed_that_partitioned_nothing_is_not_locked` | The measured cost of keeping the old rows is the lock above. Leaving a near-overlap split unrestrained is the default of GSAS-II, TOPAS, BGMN and MAUD (`practice.md:640-645`, checked here). Each member starts on the same floor, so the split starts equal. The test checks Rwp to rel 1e-6, cell a within 1e-3 esd, and that no intensity is below 1e-6. | Strong |
  | 5. Tier and source | none given (not a table row) | It behaves as tier 1 (arithmetic) only if the "no relative anchor" premise holds, and (row 2) it does not fully. No program default to cite; this is rietx's own restraint. The `LEBAIL_INTENSITY_FLOOR` row (`_audit.py:4560-4563`, tier 1) describes only the partition's positivity floor, not this second use as a "nothing measured" signal. A retune of that constant would reopen its row without naming this fallback. | Tier 3 behaviour resting on a tier-1 constant whose row does not know |
  | 6. Dataset families and references | Findings 5; the test above | One family: synthetic Cu-LaB6 with the background injected at ×100. The reference is the true start's own fit, so this verifies. It is an injected case, which the record allows for a guard no ordinary fit reaches (`generality.md:150-159`). It fired on none of the 9 real cells ("No real seed emptied a group", Findings 3, WP line 160). | Acceptable for a guard; one family |
  | 7. Record that it fired | Docstring: "the covariance reports as unmeasured rather than tight" (`forward.py` ~4133) | No record field and no diagnostic says a phase's group rows were skipped. A kept action must leave a record field (`generality.md:114-116`; DESIGN-RULES Rule 4, "records that it fired"). The claim about the esd is untested: the new test checks Rwp, the cell and zero intensities, not the stderr or `PAWLEY_OVERLAP_UNRESOLVED`. | Fails |

  Would change the verdict: a record (a `StageResult` field or a diagnostic naming the phase and the stage) whenever rows are skipped; a test that the one-stage answer's split esds are absent or large and the group is flagged; and a one-stage sweep of background factors between ×10 and ×100 showing that a nearly-empty seed does not lock.

  *Author's answers.* On the floor's tier: I entered tier 1 on the conditioning argument
  (`rcond`'s class). The judge's reading, a value chosen inside a measured window, is the
  stronger one, and tier 3 needs your approval, so the tier is your call. Probe 4 now
  reproduces the window: identical answers from 1 to 1e-8, and the lock back at 1e-9. The sweep
  on three real families the judge asks for was not run. On the fallback's record (row 7,
  fails): it is a numerical treatment inside one stage, and every later stage rebuilds the
  rows. A record would need a new diagnostic code, so whether it earns one is yours. The
  ×10-×100 sweep it asked for ran (Finding 6). Every factor up to ×50 recovers. At ×70 the
  answer is wrong whether or not the rows are present, and the row weight there is 505, not
  5e9. The sliver case therefore did not lock, and the ×70 failure is the seed's, forwarded
  to WP-2062.
- **For Yue.** (1) `PAWLEY_OFF_DATA_SCALE_FLOOR` (tier 3, 1.0 in counts, your WP-2011 ruling 3)
  is the last measured unit dependence: 5.7e-6 Rwp on zircon. A relative form needs an anchor
  for a phase with no measured on-data intensity. It sits in WP-2062's `### Inherited`.
  (2) Tier 1 or tier 3 for `PAWLEY_GROUP_SCALE_FLOOR_REL`, above. (3) Whether the
  unmeasured-phase skip owes a diagnostic.
- **Gotchas.** A probe that rescales a pattern must hand the line screen a peak list picked
  from the rescaled pattern. The screen adds the list's areas to the data's envelope, so a
  list in counts on scaled data moves `predicted_but_absent` (Findings 3). The picker found
  78 lines on zircon in counts and 79 scaled. No follow-up was filed for one line in 78.
- *Next:* none in this WP. WP-2062 is unblocked. It starts from its `### Inherited`: the
  ridge floor's ruling, the diagnostic's 1e-10, and the one-stage seed at ×70. Then come its
  remaining bug tasks. Read the nightly `full` job's Pawley acceptance rows before the next
  release.

- **2026-11-26** — filed, split out of WP-2062. WP-2062 owned this as its first
  bug task. Yue asked for it as its own WP, because it is a self-contained
  debugging job and its answer can reopen WP-2062's decision 0. That WP now
  depends on this one. Nothing run. *Next:* rerun the measurement on the
  current tree.
