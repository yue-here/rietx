# WP-2225 — A held instrument width stops a staged fit short of its own plan's point

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002 (the width twin hold); 2017 soft (its row R measures the same hold); 2224 soft (a one-stage re-fit hides this)
Priority: P2 2026-11-19 — a fit that frees an instrument width beside its specimen twin returns "converged" at a point its own plan lowers on the next run, and nothing flags it; few fits run such a plan, and calibrating the instrument on a standard is the workaround

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
option 1, on a limit the user set.

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

### Inherited

- **From WP-2017 (2026-11-19): the QPA plan now refines `lines_axial` before
  `sample_broadening`, and most of the effect above is gone.** A side investigation traced
  the simulated `trigger` bench case's Rwp rise (0.0200 on v1.9.0, 0.0276 on main) to this
  hold. Its `profile` stage fitted U, X and Y with the axial ratio still wrong, and the hold
  froze the bias. The maintainer kept a reorder (2026-11-19): `qpa_plan` in the tests, in
  `viz.compare` and in the Stephens acceptance plan now runs the Kα2 ratio and S/L before
  the specimen widths, as `lab_bragg_brentano` does. `eight.py` re-run on the merged tree
  (macOS arm64, worktree `[dev]`, compiled tier on, closing stage off, which merged main now
  ships by default): [`eight_summary_axial_first.txt`](2225-batch/eight_summary_axial_first.txt).

  | Standard | Re-fit's largest shift, before → after | First fit Rwp, before → after | Chain limit, after | Hold off |
  |---|---|---|---|---|
  | zincite | V +3.32 → +0.07 esd | 0.110169 → 0.109726 | 0.109669 | 0.109274 |
  | fluorite | V +1.18 → 0.01 | 0.181695 → 0.181309 | 0.181303 | 0.181309 |
  | corundum | V +0.23 → 0.04 | 0.145752 → 0.145745 | 0.145745 | 0.848 (walks) |
  | brucite | `lor_size` −0.10 → 0.02 | 0.469465 → 0.469477 | 0.469481 | 0.469378 |

  So a staged re-fit now moves no reported parameter by more than 0.1 esd on all four. This
  WP's acceptance bar is met without a code change (zincite's `shipped+1` reads V +0.10, at
  the bar). One thing is left. Zincite's chain now settles at Rwp 0.109669, 0.7 % in χ²
  above the hold-off point (0.109274). Before the reorder the chain reached that point. The
  hold still fixes a split the data do not determine, and the reorder only changed which
  split. That is the start dependence behind cpd-1a's Biso-start xfail (15.68 esd), which
  the reorder leaves as it was. Re-read options 0-4 with that in mind: the stopping-short
  defect is now small, and the open question is what a sample-only plan should report for
  a twin pair. The maintainer asked for that question to have a WP (2026-11-19). It is folded
  here because this WP already carries it.

## Non-goals

- The closing stage's own re-fit movement on SRM 660c (`u` −0.19 esd, no twin held).
- What a re-fit runs by default (WP-2224).
- The hold's tier and families as a whole (WP-2017 row R).

## Tasks

- [ ] Measure options 1 and 2 on the multi-phase families beside the four standards: cpd-1a from
      both starts, 11-BM LaB₆ + cBN and brucite with a Stephens block. Read cpd-1a's phase
      fractions against the weighed composition and LaB₆ + cBN's against TOPAS's interval, both
      references the acceptance suites already carry. Extend `2225-batch/swap.py`.
- [ ] Brief the maintainer with those numbers: the choice among options 0-4.
- [ ] Build the chosen option, with its record field or code and its `_audit` row.
- [ ] Tests: the four standards' staged re-fit of the shipped first fit moves no reported
      parameter by more than 0.1 esd (or, under option 3 alone, the code fires on all four and on
      none of the other four); obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: under option 3, the code's reference row; otherwise a line in §3's degeneracy table
      that a plan freeing an instrument width and its specimen twin on an uncalibrated instrument
      gives an answer that depends on the stage order.

## Acceptance

```sh
RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2225-batch/eight.py out.jsonl
.venv/bin/python docs/wp/2225-batch/shifts.py out.jsonl
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_width_twin_hold.py tests/test_compare_ui.py
```

The `shipped+1` rows of `shifts.py` stay under 0.1 esd on zincite, fluorite, corundum and brucite,
or the chosen code fires on exactly those four.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 428-435 (the LM driver and its stopping rule).
- GSAS-II 5.8.4, `GSASIIstrMain.py` (`dropOOBvars`), read in `rietx-bench/tools/gsas2`.
- IUCr CPD quantitative phase analysis round robin, `tests/data/qarr/` (`tests/data/README.md`).

## Handover log

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
