# WP-2225 — A held instrument width stops a staged fit short of its own plan's point

Milestone: generality · Status: ✅ 2026-11-20 — option 3, ruled by the maintainer 2026-11-20: `WIDTH_TWIN_HELD` reports the held width twins; PR #1722
Track: The audits
Depends on: 2002 (the width twin hold); 2017 soft (its row R measures the same hold); 2224 soft (a one-stage re-fit hides this)

## Goal

A staged fit whose plan frees an instrument width and its specimen twin ends where a staged
re-fit of it moves no reported parameter by more than 0.1 esd. If that cannot be had, the
result says which instrument widths were held at a value no later stage re-solved.

## Context

### What happens

The width twin hold (WP-2002, the maintainer's decision 1 of 2026-10-23) fixes an instrument
width for a stage whenever a specimen width with the same angular shape is free beside it. The
pairs are U with `gauss_strain` and `gauss_size`, X with `lor_size`, and Y with `lor_strain`.
Without the hold the pair is exactly flat and walks: with it switched off, corundum's first fit
ends at Rwp 0.848 and brucite's staged re-fit at 0.865, against 0.146 and 0.469 with it on.

The comparison standards' QPA plan (`viz.compare.qpa_plan`, which mirrors
`tests/test_acceptance_qpa_roundrobin`) is cumulative. Stage 5 (`profile`) frees U, V, X and Y
with no specimen width free, at the intermediate tolerance. Stage 6 (`sample_broadening`) frees
the four specimen widths, and from there to the end the hold keeps U, X and Y at the values
stage 5 left. On the four standards that run this plan, the Gaussian specimen widths, and on
zincite and brucite the Lorentzian strain too, then end on their floor of 0. A specimen width
on its floor can only widen the line. So the stage has no free parameter that can narrow the
held part of the width, and the fit stops at the best point with U, X and Y fixed at stage 5's
values. Those values were fitted before the axial divergence, the Kα2 ratio and the Biso were
free.

A staged re-fit runs stage 5 again from the converged values of everything else. It re-solves
U, X and Y there, and the later stages hold them at the new values. Each re-fit is one more
round of alternating between the two halves of the pair. On zincite five rounds settle, at
Rwp 0.10928 (closing stage off). A one-stage re-fit applies the hold at its start and moves
nothing.

The held values are left out of `RefinementResult.parameters` (held paths are not
measurements, WP-1999), so they carry no esd. `StageResult.width_twins_held` and `.held` are the
only record of the hold, and no diagnostic reports it (WP-2002's gotchas).

### Measured

macOS arm64, worktree venv `[dev]`, compiled tier on, telemetry off, tree `e6b6e9b5c`. Scripts
and summaries: [`2225-batch/`](2225-batch/README.md). "Closing stage off" sets
`closing_window_tol=None`; "shipped" is today's default, with the closing stage on (WP-2222
would turn it off). Shifts are in esds of the earlier fit.

Reproduced on zincite, closing stage off: first fit Rwp 0.110169. A staged re-fit gives 0.109423
and moves V +2.05 esd, `axial_sl` +1.22, `sample_displacement` −0.59 and `zero_shift` −0.49.
A one-stage re-fit gives 0.110169 and moves nothing by more than 0.03 esd.

**The mechanism, one change at a time (zincite; fluorite the same where run).**

| Hypothesis | The one change | Result | Verdict |
|---|---|---|---|
| (a) stopping tolerance | first fit with every intermediate stage at ftol 1e-9 and the last at 1e-12 | first fit Rwp 0.110169, unchanged; a staged re-fit still moves V +2.07 esd (fluorite +0.81) | ruled out |
| (b) frozen windows | one-stage re-fit, which recompiles at the first fit's answer; the shipped closing stage, which recompiles at 0.1 % windows | the one-stage re-fit stays within 0.03 esd; with the closing stage on, the re-fit still moves V +2.32 esd | ruled out |
| (c) `Stage.seed` | staged re-fit with every stage's seed 0 | V +2.05 esd, the same as with the seed | ruled out |
| (d) two local minima | width twin hold switched off | first fit Rwp 0.109274; a staged and a one-stage re-fit of it stay within 0.10 esd; chained re-fits with the hold on approach the same point (0.109284) | ruled out: one basin |
| (e) an active inequality row | the solve's Γ_G² ≥ ε and Γ_L ≥ 0 rows at the end | smallest slack 0.0047 deg² and 0.058°, no row active | ruled out |
| (f) a wrong Jacobian column | analytic columns against central differences at the first fit's end | relative error at most 1.6e-4 on every column, with the gradients agreeing in sign and size on the width columns | ruled out |
| the hold | `_hold_width_twins` returning nothing | the first fit lands at 0.109274, below every staged re-fit with the hold on | **the mechanism** |

The point that settles it: from the first fit's end, the one-stage re-fit runs pure Gauss-Newton
(λ = 0) and stops on `exhausted_fp64`, so the point is stationary over its 21 free columns. The
re-fit's stage 5 frees 16 columns, U, X and Y among them, and lowers the cost from 9511.50 to
9417.02 in 7 evaluations. The all-free stage lacks U, X and Y: they are held.

**All eight standards** (`eight_summary.txt`). Chained staged re-fits, closing stage off, run
until Rwp moves less than 1e-7; then one re-fit of the shipped default.

| Standard | Twin held? | First → chain limit, Rwp (χ² change) | Largest shift at the chain limit | Shipped → re-fit, Rwp | Largest shift, shipped re-fit |
|---|---|---|---|---|---|
| zincite | U, X, Y | 0.110169 → 0.109284 (−1.60 %) | V +3.32; Zn Biso +0.51; cell c −0.41 | 0.106047 → 0.105443 | V +2.32; Zn Biso +0.45; c −0.29 |
| fluorite | U, X, Y | 0.181695 → 0.181303 (−0.43 %) | V +1.18; quoted values ≤ 0.05 | 0.176417 → 0.176155 | V +0.87; `lor_strain` +0.17 |
| corundum | U, X, Y | 0.145752 → 0.145746 (−0.01 %) | V +0.23 | 0.143596 → 0.143580 | `lor_size` +0.65; V +0.24 |
| brucite | U, X, Y | 0.469465 → 0.469361 (−0.04 %) | `lor_size` −0.10 | 0.469016 → 0.468923 | 0.03 |
| SRM 660c | none | unchanged | 0.03 | 0.087431 → 0.087326 | `u` −0.19 |
| FAP | none | unchanged | 0.02 | unchanged | 0.00 |
| NAC | none | unchanged | 0.00 | unchanged | 0.00 |
| LaB₆ capillary | none | unchanged | 0.01 | unchanged | 0.00 |

The effect is present exactly where a twin is held. On zincite it reaches quoted values at half
an esd. Everywhere else cell, Biso and scale move under 0.05 esd. The held values themselves
move far more than any reported parameter, with no esd to judge them by: zincite's W goes from
0.0097 to 0.0040 deg² and Y from 0.036 to 0.024; brucite's U from 0.0006 to −0.059 and Y from
0.165 to 0.085. SRM 660c's shipped re-fit moves `u` 0.19 esd with no twin held. That is a
separate effect of the closing stage. It exceeds this WP's 0.1 esd bar and was not looked at.

**The plots** (`plot_zincite.py`, `tests/output/zincite_*.png`, looked at). Zincite's two
shipped end points cannot be told apart by eye on the full pattern. The re-fit's χ² is 1.1 %
lower. The cumulative χ² difference puts that gain on the two strongest low-angle peaks (31.8°
and 36.3°) and above 133°. Both fits underfit the tops of those two peaks by about 13σ, so the
re-fit does not remove a visible misfit.

**A prototype of option 1** (`swap.py`, `swap_summary.txt`): at a stage's start, a pair whose
specimen twins all sit on their floor holds the twins and frees the instrument column.

| Standard | Closing off: one fit | its staged re-fit | Shipped: one fit | its staged re-fit | Today's shipped re-fit |
|---|---|---|---|---|---|
| zincite | 0.109572 | 0.109279 | 0.105300 | 0.105301 | 0.105443 |
| fluorite | 0.181309 | 0.181303 | 0.176108 | 0.176108 | 0.176155 |
| corundum | 0.145744 | 0.145746 | 0.143579 | 0.143580 | 0.143580 |
| brucite | 0.469457 | 0.469363 | 0.468923 | 0.468919 | 0.468923 |

With the closing stage on, one fit reaches today's re-fit point or below on all four, and a
re-fit then moves Rwp by at most 4e-6. With it off, zincite gets only part of the way. Its
Lorentzian strain lands on its floor in the last stage, after the last stage start the rule
looks at. WP-2002 measured the same swap as a whole-fit rule (its 9th session's *Measured*): on
cpd-1a, a multi-phase QPA sample, it gave Rwp 0.1619 from both starts but Y −0.181 against
−0.099 and zincite `lor_strain` 0.256 against 0.175. That is the per-phase near-collinearity of
1/cosθ and tanθ. Not adopted then.

### Practice

[`docs/practice.md` § Instrument and specimen widths refined
together](../practice.md#instrument-and-specimen-widths-refined-together), and its subsection on
one twin reaching its limit, added by this WP. No program floors an instrument width or holds a
twin pair automatically. Every program that separates instrument from specimen does it by
fixing the instrument from a standard: FullProf through its resolution file, BGMN by ray
tracing, RIETAN-FP by its advised protocol and GSAS-II through defaults that leave the sample
terms off. In GSAS-II a variable that crosses a user's limit is reset to it and frozen for later
refinements, with a printed warning, while its partner keeps refining. That is the shape of
option 1, on a limit the user set. TOPAS 5 keeps a parameter at its limit refined and appends
`_LIMIT_MIN_#` to its printed value at the end (Technical Reference §3.8, read 2026-11-20). That is
the shape of option 3, on a limit the user set. rietx's analogue is `FLOOR_HIT` on a floor of 0
and `BOUND_HIT` on any other limit.

### Interplay

- **WP-2224** (a re-fit of a converged model runs one stage, ruled "yes, by default"
  2026-11-19). Under it a second `fit` applies the hold again and moves nothing. The re-fit
  therefore stops showing this effect. The first fit's answer does not change.
- **WP-2222** (closing stage off by default). The effect is the same size with the closing stage
  on and off. Option 1's single-fit result depends on the closing stage, because the closing
  stage is the last stage start the rule sees.
- **WP-2017 row R** measures the hold's tier on real families. Its cases (cpd-1a, 11-BM LaB₆ +
  cBN, SRM 660c) are this WP's task 1 too, and a session working either reads the other.

### Options

Dropped: switching the hold off. Measured above, it walks the flat pair on corundum and on
brucite's re-fit.

0. **Do nothing.** The first fit stays where it is. Under WP-2224 a re-fit stays too. A user who
   wants separable widths calibrates on a standard first (`lab_calibrate`,
   `load_instrument_profile`), which no plan freeing a twin pair does today.
1. **Swap on the floor.** A pair whose specimen twins all sit on their floor holds the twins and
   frees the instrument. It follows GSAS-II's treatment of a parameter at its limit and closes
   the four single-phase standards in one shipped fit. WP-2002 measured it losing on cpd-1a.
   Undoable; moves the answers of every fit that frees a twin pair.
2. **Alternate inside the plan.** After the last stage, re-run the instrument-only stage and the
   last stage until the held values stop moving. Zincite needed five rounds of 26-41
   evaluations each. Reaches the hold-off point within 1e-5 in Rwp. No new rule about bounds, at
   up to five times a fit's cost on these plans.
3. **Report it.** A diagnostic code when a held instrument width's specimen twins all end on
   their floor. The test is exact, so it has no threshold. It changes what a fit prints and moves
   no number.
4. **Change the plan, not the package.** The comparison standards' and QPA acceptance's plan
   stops freeing a twin pair on an uncalibrated instrument. It moves those suites' goldens and
   leaves every caller's own plan as it is. It needs an instrument function for the CPD
   diffractometer from a standard (not checked whether the round robin supplies one).

Recommendation, to be confirmed by task 1: a lean toward 3 now and 1 if cpd-1a and LaB₆ + cBN
do not lose under it. 3 is cheap and true whichever fix follows. 1 matches the one program read
and makes one fit reach its plan's point. Its crux is whether the multi-phase cost WP-2002
measured comes from the swap or from cpd-1a's own per-phase collinearity, which the hold leaves
hidden. If the swap moves cpd-1a's quoted fractions away from the weighed composition, 2 wins.
A choice among 1, 2 and 4 changes fit answers and revisits the maintainer's decision 1 of
WP-2002, so it goes to the maintainer with task 1's numbers. Option 3 changes what a fit prints,
so it goes too.

*Superseded 2026-11-20 by task 1's numbers* (§ Task 1 below). Option 1 meets the bar on none of
the three families that miss it, and on LaB₆ + cBN it drops the specimen widths. Option 2 does
not converge in 8 rounds on the multi-phase families. The brief in the handover entry of
2026-11-20 carries the choice that is left.

### The axial-first reorder (2026-11-19), re-measured with staged re-fits

Folded from `### Inherited` (WP-2017, 2026-11-19). A side investigation traced the simulated
`trigger` bench case's Rwp rise (0.0200 on v1.9.0, 0.0276 on main) to this hold. Its `profile`
stage fitted U, X and Y with the axial ratio still wrong, and the hold froze the bias. The
maintainer kept a reorder (2026-11-19). `qpa_plan` in the tests, in `viz.compare` and in the
Stephens acceptance plan now runs the Kα2 ratio and S/L before the specimen widths, as
`lab_bragg_brentano` does.

*Superseded in part, 2026-11-20.* The entry went on to report that a staged re-fit then moved no
reported parameter by more than 0.1 esd on the four standards, so the acceptance bar was met
without a code change. That re-run (`eight_summary_axial_first.txt`) measured one-stage re-fits.
WP-2224 had already made a second `fit` run one stage (`warm_refit`), and `eight.py` passed no
`refit=`. Checked on zincite: the second and third fits print the single stage `warm_refit`, at Rwp
0.109670 and 0.109669. `eight.py` now passes `refit="stages"`. Re-run on the reordered tree
([`eight_summary_staged.txt`](2225-batch/eight_summary_staged.txt)), staged re-fits still move
zincite's V by 1.49 reported esd at the chain limit, and its Zn Biso by 0.59. One staged re-fit
with the closing stage on moves them by 1.23 and 0.54. With the closing stage on, corundum's
`lor_size` moves 0.65 and fluorite's `lor_strain` 0.21. Every other row on the eight standards stays
under 0.1, apart from SRM 660c's `u` (0.19, a non-goal). The reorder shrank the effect and did not
remove it, so the acceptance bar is not met.

### Task 1: options 1 and 2 on the multi-phase families (2026-11-20)

macOS arm64, worktree venv `[dev]`, compiled tier on, telemetry off, tree `6c3a2db5e`.
[`families.py`](2225-batch/families.py) runs each family four ways from its protocol's start:
today's hold, option 1 (`swap.swap_hold`), option 2 and the hold switched off. Option 2 is
today's fit followed by rounds of a two-stage plan until Rwp moves under 1e-7, capped at 8
rounds. The first stage of a round frees every glob the plan frees before the first stage that
held a twin. The second frees every glob the plan frees. Today's and option 1's fits are each
followed by one staged re-fit (`refit="stages"`) under the same rule, the WP's acceptance
reading. Shifts are in reported esds (Bérar-Lelann inflated, the unit of `shifts.py`), the larger
of the two fits', background rows apart. "Quoted" restricts them to cell, atom and scale rows.
Summaries: [`families_summary_multi.txt`](2225-batch/families_summary_multi.txt) and
[`families_summary_std.txt`](2225-batch/families_summary_std.txt). Each family runs at its
protocol's own closing-stage setting: on (1e-3) for cpd-1a, off for the rest.

**Does one fit reach its plan's point?**

| Family | Today: fit → staged re-fit, Rwp | Re-fit's largest shift (quoted) | Option 1 | Option 2 | Hold off |
|---|---|---|---|---|---|
| zincite | 0.109726 → 0.109282 | V 1.24 (Zn Biso 0.55) | never swaps; same as today | 4 rounds, 0.109278 | 0.109274 |
| fluorite | 0.181309 → 0.181303 | 0.01 | never swaps | 2 rounds | 0.181309 |
| corundum | 0.145745 → 0.145746 | 0.02 | 0.02 | 2 rounds | 0.848, walks |
| brucite | 0.469477 → 0.469367 | 0.02 | never swaps | 2 rounds, 0.469367 | 0.469378 |
| brucite + Stephens | 0.181235 → 0.180235 | V 1.40 (scale 0.26) | swaps U and X; 0.180453, re-fit still V 0.62 | 8 rounds, unconverged and not monotone, 0.179904 | U = −27 deg², walks |
| LaB₆ + cBN, X and Y freed with both phases' Lorentzian widths | 0.137906 → 0.129300 | La Biso 1.76 | swaps X and Y at the stage that frees the specimen widths; becomes `PLAN_SHARED` to six digits, 0.168656 | 8 rounds, unconverged, 0.129146 | 0.128941 |
| cpd-1a, Biso start 1.5 | 0.162214 → 0.162177 | fluorite `lor_strain` 0.21 (0.02) | never swaps | 8 rounds, unconverged, 0.162089 | 0.161872 |
| cpd-1a, Biso start 0.5 | 0.162572 → 0.162492 | fluorite `lor_strain` 0.38 (0.06) | never swaps | 8 rounds, unconverged, 0.162280 | 0.161872 |

Option 1 fires only where every specimen twin of a pair sits on its floor at a stage start. On
cpd-1a one phase's twin is always off its floor, so it never fires, and the same holds for zincite
with no closing stage. On LaB₆ + cBN it fires at once. The four specimen Lorentzian widths start at
0 with no stage seed, so the swap holds them there for the whole fit. The fit becomes the suite's
trusted `PLAN_SHARED` protocol, which frees the instrument widths alone. On brucite with a Stephens
block it halves the re-fit's shift and leaves 0.62 esd. It meets the 0.1 esd bar on none of the
three families that miss it today.

Option 2 reaches the hold-off point in 2-4 rounds on the single-phase standards. On the three
other families it was still moving after 8 rounds, by 4e-6 to 3e-5 in Rwp a round. On brucite
with a Stephens block Rwp rose again after round 6. Counted in solver iterations, the first fit
and its 8 rounds cost 1.8-3.7 times today's fit on those families, and 1.0-1.8 times on the
standards. The rounds are built as a warm re-fit collapses a plan (`strategy.refit._collapse`), a
review fix that left every Rwp above unchanged to six digits.

**Do the quoted answers depend on the start?** cpd-1a, Biso start 0.5 against 1.5 Å² on every
atom, the largest shift between the two answers.

| Arm | Every row, reported esd (plain) | Quoted rows | Fractions (corundum / zincite / fluorite, wt %), start 1.5 |
|---|---|---|---|
| weighed | | | 1.15 / 4.04 / 94.81 |
| today | 5.11 (17.13), fluorite `lor_strain` | 0.57, zincite Zn Biso | 1.65 / 3.45 / 94.90 |
| option 1 | identical to today | | |
| option 2 | 4.27 (14.33) | 0.33 | 1.68 / 3.47 / 94.85 |
| hold off | 0.01 (0.04) | 0.00 | 1.98 / 3.54 / 94.48 |

The hold off is start-independent on every row that keeps an esd. It reaches that by driving the
instrument widths negative: U = −0.138 deg² and Y = −0.198°, with `FLAT_DIRECTION` and
`COVARIANCE_DIRECTION_DISCARDED`. On corundum, brucite and brucite with a Stephens block it walks.
Every arm's fractions lie within the suite's tolerance of the weighed values (2 wt % for a trace
phase). The arms differ from each other by at most 0.33 wt %, under each fraction's esd of
0.21-0.69 wt %.

**LaB₆ + cBN against TOPAS** (LaB₆ 17.907-17.950 wt %, cBN a = 3.616463 Å):

| Arm | LaB₆, wt % | cBN a, ppm from TOPAS | Rwp |
|---|---|---|---|
| today | 16.79 ± 0.19, 5.8 esd below | +38 | 0.137906 |
| option 1 = `PLAN_SHARED` | 17.79 ± 0.32, 0.37 esd below | +16 | 0.168656 |
| option 2 | 16.79 ± 0.19 | +38 | 0.129146 |
| hold off | 16.85 ± 0.19 | +39 | 0.128941 |

Freeing the specimen Lorentzian widths beside X and Y costs 1 wt % of LaB₆ with the hold on or
off. The suite already records this plan as the control whose lowest Rwp is the worst answer
(`test_the_lowest_rwp_is_the_worst_answer`). Under option 1 that control stops controlling,
because the two plans become one fit.

**What the measurements say.** No rule inside one fit gives a plan that frees both halves of a twin
pair on an uncalibrated instrument a determined split. The hold makes the split depend on the
stage order and the start, and the data cannot say which split is right. Option 1 changes nothing
on the multi-phase sample and silently drops the specimen widths on the two-phase one. Option 2
converges on the single-phase standards and costs 1.8-3.7 times a fit's iterations elsewhere
without converging.
Switching the hold off removes the start dependence on cpd-1a and walks on three of the eight
families. No preset in `PLAN_PRESETS` frees both halves (checked against all nine). Only a
caller's own plan meets the case, including rietx's own comparison and acceptance plans.

The plots (`tests/output/wp2225_*.png`) were looked at for LaB₆ + cBN today and cpd-1a option 2.
Both fits underfit the tops of their strongest peaks (LaB₆ at 8°, 11.5° and 13°, fluorite 111 at
28.3°), and nothing in either picture separates the arms.

## Non-goals

- The closing stage's own re-fit movement on SRM 660c (`u` −0.19 esd, no twin held).
- What a re-fit runs by default (WP-2224).
- The hold's tier and families as a whole (WP-2017 row R).

## Tasks

- [x] Measure options 1 and 2 on the multi-phase families beside the four standards: cpd-1a from
      both starts, 11-BM LaB₆ + cBN and brucite with a Stephens block. Read cpd-1a's phase
      fractions against the weighed composition and LaB₆ + cBN's against TOPAS's interval, both
      references the acceptance suites already carry. Extend `2225-batch/swap.py`.
      *Done 2026-11-20: § Task 1, `families.py`.*
- [x] Brief the maintainer with those numbers: the choice among options 0-4.
      *Written 2026-11-20 in the handover entry; the choice waits on the maintainer.*
- [x] Build the chosen option, with its record field or code and its `_audit` row.
      *Done 2026-11-20: option 3, `WIDTH_TWIN_HELD` (`refine._width_twin_diagnostics`, single,
      `run_stage` and joint fits), its code and suggestion rows, help entry and silence pair.*
- [x] Tests: the four standards' staged re-fit of the shipped first fit moves no reported
      parameter by more than 0.1 esd (or, under option 3 alone, the code fires on all four and on
      none of the other four); obs/calc/diff PNGs to `tests/output/`.
      *Done 2026-11-20 under option 3: `tests/data/suite_alarms.json` re-pinned with the code on
      exactly zincite, fluorite, corundum and brucite, held by
      `test_suite_alarms.py`'s fast pin test and its slow measurement row; two fits in
      `test_width_twin_hold.py` (fires on the hold, silent without it). PNGs looked at.*
- [x] Skill: under option 3, the code's reference row; otherwise a line in §3's degeneracy table
      that a plan freeing an instrument width and its specimen twin on an uncalibrated instrument
      gives an answer that depends on the stage order.
      *Done 2026-11-20: `WIDTH_TWIN_HELD`'s row in `references/diagnostics.md`, beside
      `RESOLUTION_UNCONSTRAINED`, whose remedy it shares; copies re-synced.*

## Acceptance

Under option 3, as ruled by the maintainer on 2026-11-20:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_width_twin_hold.py tests/test_suite_alarms.py tests/test_silence.py tests/test_compare_ui.py
```

`WIDTH_TWIN_HELD` fires on exactly zincite, fluorite, corundum and brucite among the eight
comparison standards, and on none of the other four. The pin in `tests/data/suite_alarms.json`
says so, and the slow row `test_the_standards_fire_what_the_pin_says` holds the measurement to it.
The code fires on a synthetic fit whose last stage held U, and stays silent on the same plan with
no specimen width free. The earlier bar, a staged re-fit moving no reported parameter by more than
0.1 esd, belonged to options 1 and 2 and is dropped. Option 3 moves no number.
`2225-batch/eight.py` and `shifts.py` still measure that bar, for a follow-up such as option 4.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 428-435 (the LM driver and its stopping rule).
- GSAS-II 5.8.4, `GSASIIstrMain.py` (`dropOOBvars`), read in `rietx-bench/tools/gsas2`.
- IUCr CPD quantitative phase analysis round robin, `tests/data/qarr/` (`tests/data/README.md`).

## Handover log

- **2026-11-20, option 3 built** — a fit whose last stage held an instrument width beside its
  specimen twin now says so. The new warning `WIDTH_TWIN_HELD` names the held widths, their
  specimen twins and the stage whose values they keep. It says the specimen widths are what the
  plan's stage order left over, and suggests calibrating the instrument on a standard first. It
  moves no number. Of the eight comparison standards it fires on exactly the four whose plan
  frees a twin pair: zincite, fluorite, corundum and brucite. All five tasks are done and the WP
  closes on the maintainer's ruling of 2026-11-20 (option 3).

  *Done*: `refine._width_twin_diagnostics`, read off the last stage's
  `StageResult.width_twins_held` with no threshold, called by the single fit, `run_stage` and the
  joint fit (`multi.DIAGNOSTIC_SCOPES` row `FIT`). The shape follows the package's other holds:
  `PHASE_UNCONSTRAINED` reports the absent-phase hold and `HOLD_BLOCKED_PLAN` a caller's hold,
  and here `where` is the held instrument paths, then their twins. Level `warning`, which the
  purpose table makes a warning under microstructure and calibration (the `instrument.profile.*`
  and specimen-width globs) and info elsewhere. Audit rows: the code at tier 1 (exact read of the
  record, approved 2026-11-20 on the ruling), its suggestion at tier 2 (`docs/practice.md`
  § Instrument and specimen widths refined together). Help entry, silence pair, the GUI's
  help-key fixture regenerated, the skill's reference row beside `RESOLUTION_UNCONSTRAINED`
  (copies re-synced), a release-note fragment (`docs/releases/unreleased/1722.new.md`).
  `tests/data/suite_alarms.json` re-pinned, a fast test holding the pin's firing set to the four,
  and two fits in `test_width_twin_hold.py`. Acceptance rewritten to option 3's branch.
  The code was named `WIDTH_TWIN_HELD` after its record field, `width_twins_held`, in the
  `<THING>_HELD` form of `PARENT_STRAIN_HELD` and `HARMONIC_HELD`.

  *Measured*: macOS arm64, worktree venv `[dev]`, merged with `origin/main` at `20255ddfa`.
  Fast selection 14949 passed, 433 skipped, 32 xfailed in 466 s; this branch adds 5 tests (4 functions and the `WIDTH_TWIN_HELD` case of `test_silence.py`), no new skip, the added tests 0.32 s in all (local junit). Full suite on the tree at `277a764e7` (main merged in): 15909 passed, 444 skipped, 52 xfailed in 2577 s, shared with other sessions' runs. The pin's slow row passed (1 passed). The re-pin differs from PR #1723's pin
  (`wp2036-suite-alarms-closing-stage`, which re-pins main's moves from #1707) only by this
  code's four rows, its count of 4, and warnings per result under microstructure 9.0 → 9.5 and
  calibration 9.125 → 9.625. The other moves in the diff (fluorite's `FLOOR_HIT` gone and
  `COVARIANCE_DIRECTION_DISCARDED` added, zincite's `RESOLUTION_NOT_POSITIVE`, `CONSTRAINT_ACTIVE`
  1 → 3) are main's, and #1723 carries the same. **The two pins must be reconciled**: whichever PR
  merges second re-runs `python -m tests.suite_alarms --write`. `python -m tests.reader_output` is
  unchanged (its standard fit frees no twin pair); on zincite `str(result)` gains one line,
  quoted in the PR body. Plots looked at: `tests/output/suite_alarms_{zincite,brucite}.png`
  (the known low-angle peak-top underfit and brucite's anisotropic widths, unchanged) and
  `wp2225_no_twin_held.png` (Rwp 0.042, GoF 1.04).

  *Review* (`/code-review high --fix`, 7 findings): fixed in `072b87275`, a width a stage seeded
  and then held now names that stage ("stage 'x' seeded"), and the help entry names the Stephens
  block as Y's twin. Declined, each for the maintainer if it matters: under `run_stage` the
  message names the start rather than the node an earlier `run_stage` left (true for that call,
  and naming the node means reading history); a `vars.` column driving U is called an
  "instrument width"; `summary(deliverable="microstructure")` gains no "not quotable" line for
  this code as it does for `RESOLUTION_UNCONSTRAINED`, since that is a further change to what a
  fit prints; the pin's other moves are main's (above).

  *Generality* (the `generality-review` judge, unedited):

  **`WIDTH_TWIN_HELD`** (code, tier 1, ambiguity 1, warning). **Holds.** The case for acting
  is stronger. The code reports an exact fact, a hold the package made itself, and the cost of
  saying nothing was measured. The case against is a single unmeasured edge case, and it narrows
  only the wording of the advice.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | It reports the hold and tells the reader "quote no specimen size or strain width named in where as a measurement" (`_audit.py:1712-1715`). | It decides no number. It adds a warning-level verdict on fits whose last stage held a twin (`refine.py:8729-8734`). | ok |
  | 2. Kind | ambiguity=1 (`_audit.py:1710`) | Kind 1 is right. The trigger is the package's own record. The verdict rests on an exact degeneracy (Caglioti, Paoletti & Ricci 1958, cited at `refine.py:8707`). | agrees |
  | 3. Case against | None given. | One case found by reasoning, not measured. Suppose a caller loads a calibrated instrument profile, then runs their own plan that frees U only in stages where its twin is also free. The hold then keeps U at the calibrated start, which is exactly the calibrated route. The message correctly says "the one the fit started from" (`refine.py:8746`). The advice still says the specimen widths are not a measurement. A competent refiner in that situation would quote them. A user hold (`hold`) on U never fires the code, because the hold reads only free paths (`refine.py:1174`). | weak case |
  | 4. Case for | Two starts on cpd-1a (a round-robin QPA mixture) put fluorite `lor_strain` 5.11 reported esds apart (`_audit.py:1722-1723`; WP:253). The held values print nowhere else (`refine.py:8712-8714`). | Confirmed in the WP, whose 17.13 is the same shift in plain, uninflated esds. Practice reports the analogous cases: GSAS-II warns on a parameter frozen at a limit, and TOPAS 5 prints `_LIMIT_MIN_#` (`practice.md:246-247`). GSAS-II also prints a singularity warning when both twins are free (`_audit.py:1827-1828`). The cost of silence is specimen widths with small esds that are not determined. | strong |
  | 5. Tier | Tier 1, arithmetic: it fires exactly on a non-empty `StageResult.width_twins_held`, with no threshold (`_audit.py:1716-1719`). | Correct. Tests: `tests/test_width_twin_hold.py::test_the_answer_says_which_widths_the_hold_kept_and_whose_values` (line 194, fires), `::test_a_fit_whose_last_stage_held_no_twin_says_nothing` (line 228, silent), `::test_a_width_seeded_then_held_names_the_seed_and_not_an_earlier_stage` (line 210). The pin `tests/data/suite_alarms.json:74` says it fires on 4 of the 8 standards. | holds |
  | 6. Families | No threshold. It fires on zincite, fluorite, corundum and brucite, the four whose plan frees a twin pair (`_audit.py:1724-1725`). | No threshold exists, so no family count is owed. The firing set is exact by construction. The 5.11-esd figure is one family, cpd-1a, which is development data. It supports the advice, not a trigger. | n/a |
  | 7. Record | The code itself, read off `StageResult.width_twins_held` (`_audit.py:1717`). | `where` lists the held instrument widths and their specimen twins. `value` is the count of held widths (`refine.py:8760-8762`). | ok |

  Evidence that would change the verdict: a fit with a loaded instrument profile where the code
  fires and the specimen widths are in fact calibrated. If one occurs, the "fit started from"
  case should get softer wording.

  **`WIDTH_TWIN_HELD.suggestion`** (suggestion, tier 2, ambiguity 1, value 1). **Holds.** The
  case for is stronger. Established practice is to fix the instrument from a standard, and the
  survey in this repository shows that. The suggestion is also phrased conditionally: it starts
  "To measure the specimen widths".

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | It names the calibrated route: `lab_calibrate`, `load_instrument_profile`, then a sample-only plan (`_audit.py:6018-6019`; `refine.py:8770-8774`). | It is advice only. All the verbs and presets it names exist (`strategy/staged.py:862-863`; `io/instrument_profile.py:107,157`). | ok |
  | 2. Kind | ambiguity=1 (`_audit.py:6013`) | Kind 1 holds. The text is conditional on wanting the specimen widths, so a caller who wants only the phase fractions is not told to act. | agrees |
  | 3. Case against | None given. | A caller with no standard measured on the same instrument cannot take this route, and no alternative is named. One alternative is a plan freeing only the instrument widths. The round robin is that case: the WP did not check whether it supplies a standard (WP:165, 413-414). BGMN instead computes the instrument from the geometry (`practice.md:221`). rietx has no such route, because the fundamental-parameters approach sits behind the v2 fence. | weak |
  | 4. Case for | Every program that separates instrument from specimen broadening fixes the instrument from a standard (`_audit.py:6014-6018`). | `practice.md:225-229` confirms this for FullProf, BGMN, RIETAN-FP and GSAS-II, each cited to source or manual. It is also the package's own documented workflow, `lab_calibrate` with the certified cell held fixed (CLAUDE.md § Conventions, instrument ⊕ sample split). | strong |
  | 5. Tier | Tier 2, on `docs/practice.md` § Instrument and specimen widths refined together. | I checked this in the repository, not from memory (`practice.md:215-229`). TOPAS's row records nothing on separation, MAUD's says to free U, V and W by hand, and EasyDiffraction has no constant-wavelength sample term. None of the three separates the widths by another route, so none dissents from the suggestion. | holds |
  | 6. Families | n/a: it has no threshold. | n/a | n/a |
  | 7. Record | `suggestion=` on the `WIDTH_TWIN_HELD` diagnostic, at one site (value=1). | One site, at `refine.py:8770`. | ok |

  Evidence that would change the verdict: a program's documented default that separates the two
  widths by a route other than a standard, which rietx could offer. Alternatively, a measured case
  where a caller with no standard is left with no usable next call.

  Author's answer to the two weak cases: both concern the advice's wording, not whether the code
  fires. Neither was observed, and each is recorded here for the maintainer.

  *Gotchas*: the specimen widths' esds are unchanged; they are conditional on the held values, and
  whether they should say so is WP-2219's (#1718). No note went into WP-2219's file because #1718
  rewrites it. WP-2017's `### Inherited` gains the ruling.

  *Next*: none in this WP. A possible follow-up, not filed: rietx's own comparison and acceptance
  plans calibrate the instrument first (the brief's option 4), which first needs a standard for
  the round robin's diffractometer.

- **2026-11-20, decision** — ruled by the maintainer 2026-11-20: option 3. Given in chat to the
  shift lead. A diagnostic fires on every fit whose last stage held a width twin. It names the
  held instrument widths and the stage whose values they keep. It says the specimen widths are
  the remainder of a split the plan's order chose. Its suggestion is the calibrated route:
  `lab_calibrate` on a standard, `load_instrument_profile`, then a sample-only plan. Not option 0,
  and not option 4, which stays a possible follow-up and is not built here. The code follows the
  precedent of the package's other holds: `PHASE_UNCONSTRAINED` reports the absent-phase hold
  recorded in `StageResult.held`, and `HOLD_BLOCKED_PLAN` reports a user hold that blocked a
  glob. Here the record is `StageResult.width_twins_held`, the code says what was done, and the
  held paths go in `where`. The specimen widths' esds do not change; that question belongs to
  WP-2219 (#1718).

- **2026-11-20** — task 1 measured, and the brief below waits on the maintainer (PR #1722).
  Neither fix inside one fit works on the families that matter. Option 1 (free the instrument
  width when its specimen twins sit on their floor) never fires on cpd-1a. On LaB₆ + cBN it
  quietly stops the specimen widths from refining at all. Option 2 (repeat the instrument stage
  and the last stage) settles the single-phase standards in 2-4 rounds. On the three multi-phase
  or Stephens families it was still moving after 8 rounds, having spent 1.8-3.7 times a fit's solver iterations. The
  2026-11-19 note that the axial-first reorder had met the acceptance bar was wrong. It measured
  one-stage re-fits, which WP-2224 had made the default. A staged re-fit still moves zincite's V
  by 1.49 reported esd. What is left is a choice about what such a fit should say, set out below.

  **The decision.** What a fit should do when its plan frees an instrument width and the specimen
  width with the same angular shape on an uncalibrated instrument. The choices are to say
  nothing (0), print a diagnostic (3), or change rietx's own comparison and acceptance plans (4).
  It goes to the maintainer for three reasons. It revisits decision 1 of WP-2002. Option 3 changes
  what a fit prints. And its crux is a value judgement.

  **Why it matters.** Instrument and specimen broadening add up in each peak's width. For three
  pairs the two have exactly the same angular shape (U with the Gaussian strain, X with the
  Lorentzian size, Y with the Lorentzian strain), so the data fix only their sum. Since WP-2002
  the package holds the instrument half of such a pair for the stage, at whatever value the
  stage before left it. Without the hold the pair drifts: corundum ends at Rwp 0.85 instead of
  0.146. With it, the split between instrument and specimen is set by the plan's order and by
  where the fit started. A user who frees both gets specimen widths with small esds that two
  starts disagree on by 5 of those esds (cpd-1a's fluorite Lorentzian strain, Biso starting at 0.5
  against 1.5 Å²). Quoted values move less: up to 0.57 esd on a Biso between starts, and 0.55 on
  zincite's Zn Biso between a fit and its staged re-fit. The held instrument values are not in the
  result's parameter list, and nothing printed says they were held. No preset frees both halves,
  so only a caller's own plan meets this, including rietx's comparison standards
  (`rietx compare`) and the round-robin QPA acceptance. Importance: moderate.

  **Aim.** Honest numbers for a user who writes a plan freeing both halves, and for the readers of
  rietx's own comparison standards. The reported specimen widths are not a measurement in that
  case, and the fit should not present them as one. How often users write such a plan is not
  observed.

  **Options.** Dropped on task 1's numbers: option 1 meets the bar on none of the three families
  that miss it and turns LaB₆ + cBN into a different plan; option 2 does not converge on the
  multi-phase families after 8 rounds at 1.8-3.7 times a fit's iterations; switching the hold off walks on three of
  eight families.
  0. *Do nothing, plus one line in the skill's degeneracy table* (task 5's second branch). Fits
     print as today. An agent learns the rule only if it reads that row. Free, undoable.
  3. *A diagnostic on every fit whose last stage held a twin.* It names the held instrument
     widths and the stage whose values they keep, and says the specimen widths are the
     remainder of a split the plan's order chose. Its suggestion is the calibrated route:
     `lab_calibrate` on a standard, `load_instrument_profile`, then a sample-only plan. The test
     is exact (the record `StageResult.width_twins_held` already exists), so it has no
     threshold. Measured on the eight standards it would fire on zincite, fluorite, corundum and
     brucite and on none of the other four, plus LaB₆ + cBN's twin plan, brucite with a Stephens
     block and cpd-1a. It moves no number. Cost: a code, its `_audit` row, a skill row, a test.
     Undoable.
  4. *Change rietx's own plans to calibrate first.* The comparison standards and the QPA
     acceptance stop freeing both halves. Their goldens move and the `rietx compare` rows
     change. A caller's own plan is untouched. It needs an instrument function for the round
     robin's diffractometer, and whether the round robin supplies a standard for one is not
     checked.

  **Practice** (`docs/practice.md` § Instrument and specimen widths refined together, and
  § When one twin reaches its limit; read from source and manuals). No program holds a twin pair
  automatically, so none has this case in rietx's form. Every program that separates the two
  fixes the instrument from a standard: FullProf by its resolution file, BGMN by ray tracing,
  RIETAN-FP by its advised protocol, GSAS-II by defaults that leave the sample terms off. On a
  user's limit, GSAS-II freezes the offending parameter with a printed warning, and TOPAS 5 keeps
  it refined and prints `_LIMIT_MIN_#` beside its value. Both tell the user in the output. That
  is option 3's shape. Option 4 is the practice itself, applied to rietx's own test plans.
  rietx's convention for where agent guidance goes points the same way: the package's own output
  first, the skill body last (root CLAUDE.md § skill, WP-1338).

  **Recommendation: 3, a lean.** The crux is whether a fit should print that its specimen widths
  are a split the plan chose. That is a value judgement. It falls toward printing, because the
  widths come back with esds that look determined while two starts disagree by five of them.
  The FitReport rule against a confident wrong singleton covers exactly that, and the held values
  print nowhere else. Option 0 loses there: the skill row reaches an agent only if it reads it,
  and a person not at all. Option 4 is worth doing for rietx's own plans but needs the
  calibration standard checked first, so it is a follow-up rather than this choice. What would
  flip it: if the maintainer reads the existing record field as enough (DESIGN Rule 1, "act and
  record it in a field"), option 0 with the skill row wins. The 2026-11-04 ruling that findability
  is documentation leans that way, though it concerned a warning built on a residual rather
  than on an exact fact.

  *Done*: `families.py` and `families_summary.py` (task 1); `swap.py` made importable;
  `eight.py` and `swap.py` pass `refit="stages"` and set the closing stage on for a "shipped" row;
  `eight_summary_staged.txt` re-measures the reorder; § The axial-first reorder replaces
  `### Inherited` with a dated "superseded in part" note; § Task 1 holds the tables; practice.md
  gains TOPAS 5's limit behaviour. The review (`/code-review high --fix`) found ten defects in the
  probe scripts and the practice wording, and nine were fixed in `31e1ca8a5`. The tenth (the hold
  monkeypatch left installed if a fit raises) was declined, since a one-shot script exits anyway.
  The fix that changed numbers rebuilt option 2's rounds the way a warm re-fit collapses a plan
  and made its iteration count total every round. Option 2 was re-run after it, and the tables
  carry the re-run. Docs and probe scripts only: no test added, no suite run.
  *Gotchas*: since WP-2224 a second `fit` runs one stage unless it gets `refit="stages"`, so a
  probe measuring a staged re-fit must ask for one. `eight_summary_axial_first.txt` is such a
  one-stage run. Option 1 holds a specimen width that starts at 0 with no stage seed at once and
  for good.
  *Next*: the maintainer's choice among 0, 3 and 4 (the brief above). Then task 3 builds it,
  task 4 tests it and task 5 writes the skill row. Under option 3 the acceptance's first branch
  (re-fit under 0.1 esd) is replaced by the code firing on exactly the twin-holding families.

- **2026-11-19** — created. A staged first fit on zincite and fluorite stops short of the point a
  staged re-fit reaches, and the cause is the width twin hold. Converged stopping tolerances,
  fresh windows, zero seeds, inequality rows and the Jacobian were each ruled out by one change.
  Switching the hold off makes the first fit land at the re-fit's point. The effect appears only
  on the four standards whose plan holds a twin, and reaches a quoted value only on zincite (half
  an esd). Filed new because no open WP owns the hold's behaviour at a bound: WP-2017 row R
  measures the hold's tier, and WP-2002, which built it, is closed. *Measured*: § Context.
  *Done at handover*: forward references into WP-2017's and WP-2224's `### Inherited`; the
  review (`/code-review high --fix`) found five defects in the probe scripts, all fixed in
  `8a4c79625` (the `passes` arm printed `None` for held widths, the spy's per-solve records were
  zipped onto stages, the output path broke outside the repo root, the swap prototype recorded
  the wrong half as held, an unused import). No summary file changes, since `eight.py`,
  `shifts.py` and `swap.py`'s printed columns were not affected. Docs only: no test added, no
  full suite run. *Next*: task 1, the multi-phase measurement, then the brief.
