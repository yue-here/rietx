# WP-2101 — the parametric surface as it stands, in the manual

Milestone: parametric · Status: 🔄 2026-11-17 — second slice in review (#1632), the Durham inventory stacked on it; two rulings owed
Depends on: —
Priority: P2 2026-11-04 — a feature the open milestone was opened for, and it needs no machinery

## Goal

Someone arriving from TOPAS or GSAS-II can find out, from the pages they read first,
what rietx's parametric refinement does today, how to spell it, and what it cannot
do yet. An agent can port an input that does not import directly from those pages and
the skill alone, as the maintainer ruled on 2026-11-04.

## Context

The maintainer opened the [parametric](../milestones/parametric.md) milestone on
2026-11-04. Its reader is an experienced user who builds their own refinements.
Measured on 2026-11-03, on a seven-pattern synthetic LaB₆ ramp and by reading the tree:

- `docs/docs/switching/topas.md` and `switching/gsas2.md` never mention parametric
  refinement. `guides/equation.md` and `reference/parametric.md` do cover it, but a
  reader starting from the Switching tab has no way to them.
  *Superseded in part, 2026-11-15:* WP-1964 added a parametric section to both
  Switching pages (`switching/topas.md` § A parametric equation is a formula,
  `switching/gsas2.md` § A parametric equation is fitted with the patterns), each
  linking `reference/parametric.md`.
- Every kind of target an expert asks for is accepted today: cell, scale, a coordinate
  DOF, Biso, occupancy, `instrument.zero_shift`, a profile `w` and a background
  coefficient. Nothing says so in one place.
  *Re-measured 2026-11-15:* a declaration also accepts a size or strain term, axial
  divergence, a wavelength and the specimen displacement (locked on a capillary). A
  target that no plan stage reaches refines nothing, and nothing says so:
  `mccusker_default` left the coefficients of a coordinate, B, occupancy, size,
  strain, axial and wavelength equation at their starts, absent from
  `result.parameters`, with no diagnostic naming them. That is the held-slope trap's
  sibling.
- Freeing only `vars.a_0` holds the slope at its start of 0. Rwp went from 0.49 to 0.86
  on the ramp and nothing was reported. This is undocumented.
- Equations nonlinear in one scalar already work by scanning that scalar through
  `design` rows. Holding θ at 200, 400 and 800 K gave χ² of 150.1, 150.5 and 155.7, at
  about 0.4 s a fit. The scan gives no esd on θ. That example is not in the manual.
  *Superseded in part, 2026-11-15:* WP-1964's formula equations refine θ directly,
  with an esd (`guides/formula.md`: θ = 500.17 ± 0.61 K on a synthetic rutile ramp).
  So the scan task below may now be moot; the next session decides.
- The refusal for an unknown target points at the private
  `mtable.tables[h].entries`, where `.parameters()` is the public answer.

### Inherited

- 2026-11-09, from [1325](1325-parametric-series.md): `reference/parametric.md`
  § Range and visibility warnings describes `PARAMETRIC_OUT_OF_RANGE` as a warning
  after the fit. In a real fit it never fires. A target past its own bound makes the
  write-back after the solve raise `ValueError`, naming the target and the equation,
  before any result exists. Under the default LM driver a linear equation's target is
  now held inside its bounds at every step, so the raise is left to TRF and to an
  `"expression"` equation. 1325's handover entry asks the maintainer whether the
  warning stays, goes, or replaces the raise. Rewrite that section once they rule.
  Done in 1325's PR #1497 (2026-11-09): the warning replaces the raise, settled by
  Claude, and that section and `help.py`'s entry now say a TRF or expression fit
  finishes with it. Nothing is left here.

## Non-goals

- Anything WP-1964 adds. Its Manual task extends these pages with the grammar and a
  line-by-line translation of each program's spelling.
- A guide to the fit itself. `guides/equation.md` owns that.

## Tasks

- [x] `switching/topas.md`: a section mapping TOPAS's parametric vocabulary to rietx's
  (`prm`, `local`, `#list`, an equation on a `prm`, `!` for fixed). Say what is
  expressible now and what waits on 1964, by that name. *Done 2026-11-15:* WP-1964 had
  written the core table; this slice added the constructs the two Durham inputs use and
  a list of the four with no spelling yet. 1964 is closed, so the list names the
  missing pieces, not WPs.
- [x] The inventory, moved from the parked 2105. Every parametric construct in the two
  Durham inputs, each with its rietx spelling, its WP or a named non-goal, and each
  input's free-parameter and channel counts. The milestone's agent row is judged against
  it. *Done 2026-11-17:* § Inventory below, with four rows added to `switching/topas.md`
  for the constructs that had none.
- [x] `switching/topas.md` § Porting what does not read: the recipe an agent follows.
  *Done 2026-11-17* as § Porting an input that does not read, five steps, under
  § Moving a file across.
  Try `read_project_model`. A parametric input usually raises `TopasInpError` naming the
  first construct it cannot read, and `parametric_05.inp` and ZrP₂O₇'s input both do, so
  there is no list to work from. A simple input returns a model and a
  `TOPAS_FEATURES_NOT_IMPORTED` list. Either way, port from the input's text with the
  keyword table, then compare a stated value such as a cell or an Rwp with the input's
  own. Include how to expand `#list` and `#define` by hand and
  where `topas.log` holds the expansion.
- [x] Skill: decide whether porting is a task shape of its own (a `references/` file behind
  a situation row) or a row in the foreign-inputs line, under the skill's placement rule.
  *Done 2026-11-17:* a sentence in `api-io.md`'s projects paragraph (authored in
  `docs/skill/make_api_index.py`), keyed by `TopasInpError` and `read_project_model`,
  which the agent already holds when porting starts. No new shape file.
- [x] `switching/gsas2.md`: the same for GSAS-II's sequential refinement and its
  parametric fit afterwards. Read that program's docs before writing. *Done
  2026-11-17:* § A sequential refinement is a chain, written from GSAS-II 5.8.4's
  `GSASIIscriptable.set_Controls` docstring, its Controls tab labels and
  `GSASIIstrMain.SeqRefine`. The parametric fit afterwards was already WP-1964's
  § A parametric equation is fitted with the patterns.
- [x] `reference/parametric.md`: one table of the target kinds accepted. *Done
  2026-11-15:* § Targets, with an executing block asserting every kind and five
  refusals.
- [x] Document the held-slope trap where a reader meets it, in `guides/equation.md`.
  *Done 2026-11-17:* § Check that every coefficient refined, with the plan-reach
  sibling beside it, both executed by `examples/guides/equation.py`.
- [ ] Decide whether the two traps earn a diagnostic, under Rule 1 of DESIGN.md. A new
  diagnostic changes what a fit prints, so the maintainer rules first (handover entry
  2026-11-17 has the brief).
- [x] A worked `design` scan over a held scalar, in `examples/`, included into
  `guides/equation.md`, with its missing esd stated. *Withdrawn 2026-11-17:* a formula
  equation now refines the nonlinear scalar itself, with an esd (`guides/formula.md`,
  θ = 500.17 ± 0.61 K), so the scan is a weaker spelling of a fit the manual already
  shows.
- [ ] The refusal message names `.parameters()`.
- [x] Skill: the series reference's parametric row, or "none" and why. *Done
  2026-11-17:* the existing row in `series.md` carries the plan-reach rule, tightened to
  stay inside the file's budget, and `diagnostics.md`'s `PARAMETRIC_FORM_REJECTED` row
  carries the held variable, since that code is the name an agent holds there.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_examples.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- `docs/practice.md` § A parameter set by an equation the user writes.
- WP-1325 (the surface), WP-1964 (what comes next), WP-1996 (the Switching tab says
  only what its tests show).

## Inventory

The two Durham inputs the milestone's port rows name, both public downloads registered in
`tests/local_data.py` and held in the local data root: WO₃'s `parametric_06.inp` (inside
`parametric_06.zip`, tutorials 9.3 and 9.4) and ZrP₂O₇'s `d8_02999_35_annotate_04.inp`
(tutorial 9.5). "Row" means a row of the table in `switching/topas.md` § A parametric
equation is a formula. "List" means the list of constructs with no spelling under that
table.

### Counts

Free parameters are counted from each input's text by TOPAS's naming rules. A value after
`@` is one anonymous parameter. A named value without `!` is refined, and a name is one
parameter wherever it recurs. `local` gives each pattern its own. An `= ...;` is an
equation and refines nothing. Channels are the points of each `range` inside
`start_X`..`finish_X`, read with `rx.read_pattern(path, scan=range - 1)`. No point lies on
either limit, so inclusive and exclusive counts agree. Neither input excludes a region.

| | WO₃ `parametric_06.inp` | ZrP₂O₇ `d8_02999_35_annotate_04.inp` |
| --- | --- | --- |
| patterns | 100 (ranges 1-100 of `d9_02592.raw`) | 37 (ranges 1, 26, ..., 871 of `d8_02999.raw`, from the 37 `#define use_t_*` lines) |
| fitted 2θ | 20-80° | 15-90° (the file ends at 89.99°) |
| channels | 5844 a pattern, 584 400 in all | 4409 a pattern, 163 133 in all |
| shared free parameters | 63 | 20 |
| free parameters a pattern | 11 | 31 |
| free parameters in all | 1163 | 1167 |
| check | the input's header states 1163 for 100 data sets and 184 for 11; the count gives 184 for 11 | none in the input. Stinton & Evans (2007), Example 2, count 53 a pattern for independent fits, and 53 less 3 cells, 18 profile terms and 1 asymmetry is 31 |

WO₃'s 63 shared: 34 cell coefficients (9 `zero_*`, 9 `grad_*`, `theta_ma`, and 15 angle
coefficients), 23 W coordinates (6 in P2₁/n, 12 in P-1, 5 in Pc, where `xW31` is held), and
6 strains (`Strain_G` and `Strain_L` per phase). Its 11 a pattern: `height`,
`individual_b`, six `bkg` terms and three phase scales. Every one has a rietx spelling, so
a port that mirrors the protocol frees 1163.

ZrP₂O₇'s 20 shared: `step_error` and `square`, the two refined coefficients of the 2θ
curve in `Xo`, and 18 `TCHZ_Peak_Type` terms (six per phase). Its 31 a pattern: 18 `bkg`
terms, three scales, the ZrP₂O₇ cell, one height, the P coordinate and seven B. A port
today spells 1159 of the 1167. The 2θ curve's 2 and each phase's own TCHZ V and W (6) wait
on 2107. The Al₂O₃ coordinates count nothing: the `B1`-`B3` macros drop their `param`
argument, so the file's `!` on them is inert and the values are fixed either way. Every
temperature-calibration and cell coefficient carries `!`, so the 1167 frees none of them.

### WO₃ `parametric_06.inp`

| Construct | What it does | rietx | Status |
| --- | --- | --- | --- |
| `#list Files T_val Range_val` and `Create_XDDs(#list_n T_val)` | one pattern per row | row `#list` | spelled |
| `#define param_cell`, `write_out`; `#ifdef refine_some ... #else` | pick the live text | row `#define` | spelled |
| `for xdds { ... }`, `prm i = 0;`, `existing_prm i += 1;`, `#Files(i)`, `#T_val(i)`, `#Range_val(i)` | the per-pattern body | row `for xdds` | spelled |
| `range = #Range_val(i);` | the scan inside the RAW file | row `range 3` | spelled |
| `local !te = #T_val(i);` | each pattern's temperature | the `T` column of the `CoordinateTable` | spelled |
| `fn cell_fT(...)`, `fn angle_fT(...)` | a user function | row `fn` (added by this slice) | spelled |
| `prm zero_ma 7.298...`` and the other 33 coefficients | refined shared coefficients | row `prm zero_a` | spelled |
| `prm !theta_mb = theta_ma;` (eight of them) | one θ for nine edges | row `prm !theta_b = theta_a;` | spelled |
| `a = cell_fT(zero_ma, grad_ma, theta_ma, te);` (nine edges) | an Einstein edge | row `a = zero_a + ...` | spelled |
| `be = angle_fT(...)`, and P-1's `al`, `be`, `ga` | a quadratic angle | row `be = b0*(1 + ...)`, on `cell.alpha`, `beta` or `gamma` | spelled |
| `local height`, `th2_offset = -2 57.2957795 (height) Cos(Th) / Rs;` | a height per pattern | row `local height` (added) | spelled |
| `local individual_b`, `scale_pks = Exp(-2*individual_b/(2 D_spacing)^2);` with `beq !bval 0` on every site | one B per pattern | row `scale_pks`, with `expression="b"` since every site's B is 0 | spelled |
| `local bkg0` ... `bkg5`, `bkg = bkg0; = bkg1; ...` | a background per pattern | row `local` on a `bkg` term | spelled |
| `macro Phase_Common(n, scv) { local sc scv min 1e-10; scale = sc; ... }` | a scale per phase per pattern | rows `#define` and `local` on a scale | spelled |
| `A1(xW1, ...)` and the other W coordinates, one name in every `xdd` | shared coordinates | row "a phase's parameter under one name" | spelled; their `min`/`max` window on a coordinate is not checked |
| `A1(!xO3, ...)` and every other O, and `!xW31` | held coordinates on general positions | row `!` on a coordinate | spelled |
| `Strain_G(strainG_p21n, ...)`, `Strain_L(...)`, per phase | shared strains | `gauss_strain` = e² and `lor_strain` = e, shared by default (§ The peak shape is the instrument plus the sample) | spelled |
| `val_on_continue = ...`, `vcstrain`, `continue_after_convergence` | restarts from perturbed values | row `val_on_continue` | no equivalent, by design |
| `load_save_locals` | starts each `local` from the last run | row `load_save_locals` (added) | a restart from a result: 2103 |
| `Zero_Error(!zero, 0)`, `Simple_Axial_Model(!axial, 5.74444)`, `LP_Factor(!th2_monochromator, 0)`, `CuKa2(0.0001)` | fixed instrument terms | single-fit vocabulary; `Simple_Axial_Model` has no equal, and FCJ (`axial_sl`, `axial_hl`) is the nearest | no parameter, not parametric |
| `x_calculation_step = Yobs_dx_at(Xo)`, `convolution_step 2`, `extra_X_right 2`, `iters`, `chi2_convergence_criteria` | numerics | nothing to write | not parametric |
| `Out(...)`, `Out_String`, `Get(r_wp)`, `out ... append`, `Backup_INP`, `system_before_save_OUT`, `#if (Run_Number == 0)`, `xdd_out` | output | row `Get(r_wp)` | output only |
| `weight_percent`, `Phase_Density_g_on_cm3`, `r_bragg`, `local plpvol = Get(cell_volume);` | reported values | row `Get(r_wp)` | output only |

### ZrP₂O₇ `d8_02999_35_annotate_04.inp`

| Construct | What it does | rietx | Status |
| --- | --- | --- | --- |
| `#define use_t_0303 prm !set_t_0303 303 macro r_t_0303 { 1 }` (37 lines) | a flag, a set temperature and a range per pattern | row `#define`, and the `T` column | spelled |
| `#ifdef use_t_0303 ... #endif` (37 blocks) and `RAW(d8_02999)` | one written-out block per pattern | row `#define` | spelled |
| `range r_t_0303` | the scan | row `range 3` | spelled |
| `macro information { ... }` | text shared by every block | row `#define` | spelled |
| `th2_offset = (Xo-data_middle)^2*(square/1000) + (Xo-data_middle) (step_error/1000) + zero;` | a 2θ curve, two shared coefficients | list, "`th2_offset` written in `Xo`" | 2107 |
| `prm !T_calibration_b` ... `_d`, `prm !T_calibration_a = 0 - (...);` | a cubic calibration, its constant set by the others | row `prm !calib = ...`, `target=None` | spelled |
| `prm !delta_t_0303 = ...;`, `prm !t_0303 = set_t_0303 + delta_t_0303;` | each pattern's temperature through the calibration | row `prm !calib`, one equation feeding the cell formulas | spelled |
| `prm lpa_si_t_0303 = Exp(Ln(a0) + ...);` and `Cubic(=lpa_si_t_0303;)` | Si's three Einstein terms | row `a = zero_a + ...`, written in `T` | spelled |
| `prm !lpa_al2o3_t_0303 = a_al2o3_offset + a0_al2o3 (1 + ax1_al2o3 (t_0303-273) + ...);`, and `c` | Al₂O₃'s polynomial cell | rows `a0 (1 + ax1 (T - 273))` and `a = ...` | spelled |
| `scale scale_zrp2o7_t_0303 ...`, `Cubic(lpa_zrp2o7_t_0303 ...)`, `xp1_t_0303`, `bvalue*_t_0303`, one name per block | per-pattern parameters by name | row `local` on a phase's parameter (`per_histogram`) | spelled |
| `Specimen_Displacement(height_zrp2o7_t_0303, ...)`, and `=height_zrp2o7_t_0303;` in the other two phases | one height per pattern | row `Specimen_Displacement` | spelled |
| `TCHZ_Peak_Type(pku_zrpo7, ...)`, one name per phase in every block | a phase's six width terms, shared | row `TCHZ_Peak_Type` (added) | U, Z, X, Y spelled; V and W 2107 |
| `B1(!xAl1, 0.0000, 0.0000)` ... `B3(...)` | fixed Al₂O₃ coordinates | nothing to write | the coordinates are fixed |
| `bkg @` with 18 values in each block | a background per pattern | row `local` on a `bkg` term | spelled |
| `MVW(...)`, `Out(...)`, `out "temp.res" append`, `prm !correction_at_30_deg2th = ...;`, `prm !calc_delta_t_0300 = ...;` | reported values | row `Get(r_wp)` | output only |
| `Simple_Axial_Model(!axial, =ax_overall;)`, `LP_Factor(!th2_monochromator, 27.26)`, `CuKa1(0.001)` | fixed instrument terms | single-fit vocabulary | no parameter, not parametric |
| `chi2_convergence_criteria`, `iters`, `seed`, `Rietveld_Plot` | numerics and output | nothing to write | not parametric |

## Handover log

- **2026-11-17 (inventory)** — Task 2, by a ghostshift runner, in PR (pending), stacked on
  #1632. The milestone's agent-port row now has numbers to judge against. WO₃'s input fits
  584 400 channels with 1163 free parameters, and ZrP₂O₇'s fits 163 133 with 1167. Every
  WO₃ parameter has a rietx spelling. Eight of ZrP₂O₇'s wait on 2107: the two
  coefficients of its 2θ curve in `Xo`, and each phase's own TCHZ V and W.

  *Done.* § Inventory: a counts table and one construct table per input. In
  `switching/topas.md`, four rows for constructs that had none (`fn`, a phase's
  `TCHZ_Peak_Type`, a height written in `Cos(Th)`, `load_save_locals`), the list's
  reflection bullet naming a phase's V and W, and the `Strain_G`/`Strain_L` conversion
  under § The peak shape. The old row "a phase's parameter under one name ..., such as its
  `TCHZ_Peak_Type` terms" was wrong: rietx has no per-phase V or W, so its example is now
  a strain or a coordinate.

  *Measured* (runner's scratch scripts, `[dev]` venv, macOS arm64, not in the repo).
  Channels from `rx.read_pattern(..., scan=range - 1)`: 5844 a pattern in 20-80° on
  `d9_02592.raw`, 4409 a pattern in 15-90° on `d8_02999.raw`, with no point on a limit.
  Free parameters from each input's text by TOPAS's naming rules. The WO₃ count gives 1163
  for 100 data sets and 184 for 11, the two figures its header states. ZrP₂O₇'s input
  states none, and its 31 a pattern equals Stinton & Evans's (2007) 53 for an
  independent fit less the 22 terms the input shares or fixes. The TCHZ and `Strain_G`
  forms were read from the TOPAS 5 Technical Reference.

  *Gotchas.* The Al₂O₃ `B1`-`B3` macros drop their `param` argument, so those
  coordinates are fixed whatever the `!` says. WO₃'s input states no `Rs`, so a port
  sets `goniometer_radius_mm` to TOPAS's default. ZrP₂O₇'s count includes no
  temperature-calibration coefficient, because the input holds all of them. The
  milestone's run that frees them is a different protocol.

  *Settled by Claude 2026-11-17:* the inventory lives in this WP file, because the
  milestone's row names "2101's inventory"; the alternative was a manual page, which would
  publish a judge's answer key. *Settled by Claude 2026-11-17:* a phase's TCHZ V and W and
  the `Xo` curve are marked 2107, under the milestone's ZrP₂O₇ row ("join the protocol
  once 2107 lands"); the alternative was a non-goal. *Settled by Claude 2026-11-17:* the
  four missing rows went into `switching/topas.md` in this slice, under the milestone's
  agent row (a line per construct or a named non-goal); the alternative was listing the
  gaps here for a later slice.

  *Gates* (on this branch, `[dev]` venv, macOS arm64). `tests/test_docs_consistency.py
  tests/test_manual.py tests/test_manual_api.py`: 110 passed. Sphinx `-W`: clean. CI's lint
  steps from the top level: ruff check and the tutorials' format check clean; Vale 0 errors,
  and its one warning on `topas.md` is on line 82, which this slice did not write. No code
  changed, so no other suite ran.

  Next: the maintainer's two rulings in the entry below, then task 9.

- **2026-11-17** — Second slice, by a ghostshift runner, in PR #1632. A TOPAS user whose
  parametric input does not read now has a five-step route from the reader's error to a
  fit checked against the input's own numbers. A GSAS-II user finds each sequential
  control's rietx argument. The equation guide now shows the two ways a coefficient stays
  at its start: a formula variable left at `vary=False`, and a target no plan stage frees.
  The second still prints nothing. The first prints a form rejection that blames the
  formula. Whether either earns a diagnostic is the maintainer's call (below).

  *Done.* Task 3: `switching/topas.md` § Porting an input that does not read. Task 4:
  porting is one sentence in the skill's `api-io.md` (authored in
  `docs/skill/make_api_index.py`), keyed by `TopasInpError` and `read_project_model`, the
  names an agent holds when porting starts; no new task-shape file. Task 5:
  `switching/gsas2.md` § A sequential refinement is a chain, written from GSAS-II 5.8.4's
  `set_Controls` docstring, its Controls tab and `SeqRefine`. Task 7, documentation half:
  `guides/equation.md` § Check that every coefficient refined, both cases executed and
  asserted by `examples/guides/equation.py`. Task 8 withdrawn (formula equations refine
  the scalar with an esd). Task 10: `series.md`'s parametric row carries the plan-reach
  rule, and `diagnostics.md`'s `PARAMETRIC_FORM_REJECTED` row says to check each
  variable's `vary` before revising. *Superseded in part:* the Context bullet "freeing only
  `vars.a_0` ... nothing was reported" no longer holds. The held slope now fires
  `PARAMETRIC_FORM_REJECTED`; the plan-reach case still reports nothing.

  *Measured* (session probes in the runner's scratch, `[dev]` venv, macOS arm64, not in
  the repo unless named). LaB₆ ramp, formula `a0 + a1*(T - 600)`: with `a1` free, Rwp
  0.040 and no code; with `a1` held at 0, Rwp 0.568, per-pattern Rwp 0.04-0.80,
  `PARAMETRIC_FORM_REJECTED` (statistic 14 606 against a cut of 12.6) whose `where` names
  both variables and whose suggestion says to revise the expression (asserted in
  `equation.py`). A polynomial line on La's B under `mccusker_default`: coefficients 0.4
  and 0 with esd `None`, `vary` False, no `PARAMETRIC_*` code, no B row in
  `result.parameters` (asserted). `read_project_model` on the Durham inputs: both WO₃
  parametric inputs raise `TopasInpError` at `for xdds`, the ZrP₂O₇ input at a
  `B1(!xAl1, ...)` site, the WO₃ `wo3_t0000_04.inp` at `#ifdef !fit_all_v6`; the ZrMo₂O₈
  VT input reads as run 0 of 68 with `TOPAS_FIRST_RUN_READ` and two
  `TOPAS_FEATURES_NOT_IMPORTED`. Three LaB₆ ramp patterns through `refine_sequential`:
  `carry=[]` with `refit="stages"` took 107 iterations against the default's 68, same
  cell edges to 1e-6 Å (quoted in `gsas2.md`; no script holds it).

  *Review.* `/code-review high --fix` found ten. Fixed: the guide reads `vary`, since an
  esd of `None` also marks a freed coefficient the data cannot see; the skill row asks to
  check each variable `where` names; `for xdds` is a loop and not text substitution;
  the reach block's numbers are asserted; the suggestion is the `suggestion` field;
  GSAS-II with Copy2Next unticked reuses a histogram's stored sequential result. Declined:
  the skill's `/docs/stable/` link reaches the new section only after 1.12 is cut, as the
  other skill link does; the series row's routing cue "(a(T), a written expression, a
  library's cell)" was cut to stay inside the file's budget; the 107/68 figure is recorded
  here rather than given a script.

  *Generality* (judge's verdicts, condensed; full sections in the runner's report).
  Item 1, the `PARAMETRIC_FORM_REJECTED` row: holds, tier 1; the package's own suggestion
  is the cheaper home, which changes what a fit prints. Item 2, the series row: weak as
  first written (named `esd=None` and "widths"); fixed to name `vary` False and U-Y.
  Item 3, the porting sentence: weak on "usually" (one family) and on comparing "in esds",
  which departs from DESIGN.md Rule 2; fixed to "often" and to ppm with both esds beside
  it, in the skill and in the manual's step 5.

  *Decision for the maintainer* (task 7's second half and task 9; both change what a fit
  prints). (1) Should a coefficient that never refined get a diagnostic? A target no plan
  stage frees is silent today: the reader sees only `vary` False and esd `None`. A held
  formula variable fires `PARAMETRIC_FORM_REJECTED`, whose suggestion sends the reader to
  rewrite a correct formula. Options: docs only (as now); a new code naming each
  equation whose coefficients no stage freed; or the rejection's suggestion naming any
  variable in `where` at `vary=False`. (2) Should the refusal of an unknown target point
  at `.parameters()` rather than the private `mtable.tables[h].entries`?

  *Settled by Claude 2026-11-17:* porting goes in `api-io.md` as a sentence, under the
  skill's placement rule (WP-1338: the cheapest place keyed by a name the agent holds);
  the alternative was a `references/porting.md` shape file behind a `SKILL.md` row, which
  #1630's edits to `SKILL.md` also argued against. *Settled by Claude 2026-11-17:* task 8
  withdrawn on the formula guide's θ = 500.17 ± 0.61 K; the alternative was the scan
  example as filed. *Settled by Claude 2026-11-17:* the held-slope trap is documented in
  `equation.md` beside the plan-reach case, though the trap lives in formula equations
  (`formula.md`), because the task named that page and a straight line is where a porter
  writes one first.

  *Gates* (on this branch with `origin/main` 2026-11-17 merged in, `[dev]` venv, macOS
  arm64). `tests/test_manual.py tests/test_manual_api.py tests/test_skill.py
  tests/test_skill_cli.py tests/test_docs_consistency.py tests/test_examples.py -k "not nac
  and not srm660c"`: 329 passed. Sphinx `-W`: clean. Vale: no error, and no warning on an
  added line. Ruff check and the tutorials' format check: clean. `tests.skill_caps`:
  `series.md` 3 B under its budget. `tests.reader_output`: exit 0, output unchanged. No
  test was added, and no change could move a measured number, so the full suite did not
  run.

  Next: the maintainer's two rulings above, then task 2 (the inventory of the Durham
  inputs' parametric constructs, with each input's free-parameter and channel counts).
  Count free parameters from `TOPAS.LOG` or by hand from the expanded text, and channels
  from each `.raw`'s ranges with `rx.io.readers.list_scans`.

- **2026-11-15** — First slice, by a ghostshift runner, in PR #1573. A TOPAS user reading
  the Switching tab now finds a rietx spelling for every parametric construct the two
  Durham inputs use, and the four that have none yet. The reference page now lists, in
  one table, the twelve kinds of parameter an equation can drive, checked by code the
  manual test runs. One trap came out of the measuring: an equation whose target no plan
  stage frees refines nothing, and nothing reports it. It is documented and has no
  diagnostic.

  *Done.* `switching/topas.md` § A parametric equation is a formula: 14 rows added to
  WP-1964's table (`for xdds`, `#define`/`macro`, shared and `local` names, `!` on a
  coordinate as a `turn_off` stage, an overall B per pattern, a monoclinic angle, implied
  multiplication, `range n` as `scan=n-1`, `Out`/`Get`/`MVW`, `val_on_continue`), an
  executing block for the overall B and the hold, and a list of the four constructs with
  no spelling: a joint fit's `hold`/`tie`/`set_values` (WP-2103), restraints and
  `penalty` in a joint fit (WP-1995), an equation over a reflection or a 2θ point
  (WP-2107), and `fit_obj` (a milestone non-goal). `reference/parametric.md` § Targets:
  the table, the refusals pointer, the plan-reach paragraph, and an executing check of
  14 accepted and 5 refused paths.

  *Measured* (session probes in the runner's scratch, `[dev]` venv, macOS arm64, not in
  the repo). On the LaB₆ ramp of `examples/guides/_lab6_ramp.py`, a linear-in-T equation
  on each kind, beside one on the cell, under a three-stage `PlanSpec` whose last stage
  names the target: every fit converged, and the slope of each target whose truth is
  constant came back within 1 esd of 0 (scale, coordinate, occupancy, zero shift, w, y,
  background c1, axial). B's slope sat at −4.5 esd and the wavelength's at −5.7 esd with
  `FLAT_DIRECTION`. The wavelength is degenerate with the cell; B is the pattern-0 issue
  below. Under `mccusker_default` the coordinate, B, occupancy, size, strain, axial and
  wavelength coefficients never left their starts and had no row in
  `result.parameters`. One B per pattern for every site, written as a formula on each
  site's `biso` with `vars.b` per pattern: patterns 1-6 returned b = 0.00-0.04 ± 0.10 Å²
  (truth 0). Pattern 0 stopped at b = 3.7 with its scale halved. A control with each
  site's B per pattern and no formula did the same (B = 4.0, same scale), so that is the
  probe's plan (scale before cell, with the start cell 0.1 % off) and not the formula. A
  `turn_off` stage on the boron coordinate left it at its start through a stage that
  freed every other atom parameter. A monoclinic β formula previews (90.54-90.86° over the
  ramp). `a0 (1 + ...)` is refused as an unknown function `a0`.

  *Gates.* `tests/test_manual.py tests/test_manual_api.py`: 84 passed. Sphinx `-W`:
  clean. Vale on both pages: no warning on an added line. No example changed, so
  `tests/test_examples.py` was not run. Docs-only branch, so `/code-review` was skipped.

  *Settled by Claude 2026-11-15:* the manual names what is missing and no WP numbers,
  under the manual's practice (a WP number appears in six places in the manual, two of
  them comments) and WP-1996 (the Switching tab says only what its tests show). The
  alternative was naming each WP, as the task text asked when 1964 was open. *Settled by
  Claude 2026-11-15:* the overall B is documented as spellable today, through formulas,
  under the 2026-11-04 ruling (docs plus an agent port what does not import) and the
  measurement above. The alternative was "waits on WP-2103's tie". Forwarded to WP-2103's
  Inherited. Not reached this slice: the held-slope diagnostic (task 7, DESIGN.md Rule 1)
  and the skill's placement (tasks 4 and 10). Nothing in this slice changes text the
  package prints.

  *Gotchas.* Many TOPAS parametric constructs are already handled by a joint fit's
  sharing defaults: say "nothing" in a row rather than inventing a call. A Durham input's
  site `!` often marks a coordinate the symmetry already fixes; check the site before
  porting a hold.

  Next, in order: task 2 (the inventory, with each input's free-parameter and channel
  counts; this slice's table rows are its vocabulary), task 3 (§ Porting what does not
  read), then task 7 with the plan-reach sibling, since one Rule 1 decision covers both.
  Task 8 may be moot (see Context). Task 9's refusal message needs the maintainer, as it
  changes what a reader receives. Tasks 4, 5 and 10 are untouched; task 10's row is where an agent meets the
  plan-reach rule, so it carries that rule too.

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned this: 1964's
  Manual task covers the new grammar and 1325's manual tasks are closed. The numbers
  above were measured by session scripts on 2026-11-03 and are not in the repo. Next:
  the TOPAS section.
