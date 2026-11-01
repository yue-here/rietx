# Joint refinement

This page gives `MultiHistogramRefinement` and `refine_multi`, which refine one structure against several patterns at once: their arguments, which parameters the patterns share, two radiations in one fit, a refinable wavelength, the joint result and its per-pattern half, the events and cancellation of a joint fit, and a report per pattern.

The patterns are stacked into one residual {cite}`vondreele1997`.
GSAS-II calls this a combined refinement, and calls each pattern a histogram, as rietx does.
Shared structural parameters draw information from every pattern, while each pattern keeps its own `Instrument` for its wavelength, geometry, resolution and background.
A series of patterns of a changing specimen is a chain instead ([Sequential refinement](series.md)), and a parameter that follows an equation of each pattern's coordinates is declared on a joint fit ([Parametric refinement](parametric.md)).
[How to fit an X-ray and a neutron pattern together](../guides/joint.md) runs a joint fit from start to finish.

## Entry points

<!-- api-doc: no-exec — it refines the reader's own patterns -->
```python
import rietx as rx

joint = rx.MultiHistogramRefinement(structure, [instrument_a, instrument_b])
result = joint.fit([pattern_a, pattern_b], plan="mccusker_default")

result = rx.refine_multi([pattern_a, pattern_b], structure, [instrument_a, instrument_b])
```

`refine_multi` is the same run as one call, with the patterns first.
Both return an ordinary `RefinementResult`, with the per-pattern half on `RefinementResult.histograms` ([Joint result](#joint-result)).
`MultiHistogramRefinement.fit` takes the patterns in the order of the instruments given to the constructor, and the two lists must be the same length.

| Argument | Taken by | Default | Does |
|---|---|---|---|
| `structure` | constructor, `refine_multi` | required | one `Structure`, or a list of one per pattern with different starting values ([Starting values per pattern](parametric.md#starting-values-per-pattern)) |
| `instruments` | constructor, `refine_multi` | required | one `Instrument` per pattern |
| `sharing` | constructor, `refine_multi` | `None`, the default `SharingMap` | which parameters the patterns share ([Shared parameters](#shared-parameters)) |
| `coordinates`, `parametric` | constructor, `refine_multi` | `None` | a parameter declared as an equation of each pattern's coordinates ([Parametric refinement](parametric.md)) |
| `backend`, `solver` | constructor, `refine_multi` | `"numpy"`, `"lm"` | as for a single fit ([Entry points](refinement.md#entry-points)) |
| `plan` | `fit`, `refine_multi` | `"mccusker_default"` | a preset name or a `RefinementPlan` |
| `mode` | `fit` | `"rietveld"` | any other mode raises `NotImplementedError` |
| `two_theta_limits` | `fit`, `refine_multi` | `None` | one `(low, high)` for every pattern, or one per pattern |
| `weights` | `fit`, `refine_multi` | `None`, 1.0 each | one positive relative weight per pattern's residual block |
| `events`, `cancel`, `telemetry`, `label`, `progress` | `fit`, `refine_multi` | `None` | as on `Refinement.fit` ([Events and cancellation](#events-and-cancellation)) |

| Attribute | Holds |
|---|---|
| `MultiHistogramRefinement.n_histograms` | how many patterns there are |
| `MultiHistogramRefinement.mtable` | the multi-histogram parameter table: one ordinary table per pattern, threaded by a column map that folds the shared columns onto one |
| `MultiHistogramRefinement.parametric` | the parametric declarations as resolved at construction ([Reference and scale](parametric.md#reference-and-scale)) |
| `MultiHistogramRefinement.fitted_structures`, `MultiHistogramRefinement.fitted_instruments` | after a fit, each pattern's refined models; the shared parameters are identical across the structures |
| `MultiHistogramRefinement.result_` | after a fit, the result |
| `MultiHistogramRefinement.report` | the `FitReport` for one pattern ([Report per pattern](#report-per-pattern)) |

A joint fit runs in Rietveld mode only.
Le Bail and Pawley intensities are per-pattern extractions rather than shared quantities, so a joint fit of them would be independent single fits.

## Shared parameters

`SharingMap` decides which parameters the patterns share.
The default rule is instrument against sample: a path is per-pattern if it starts with `instrument.` or ends with `.scale`, and shared otherwise, on the reading that there is one specimen and one crystal.

```python
from rietx.params.multi import SharingMap

default = SharingMap()
assert default.is_shared("phases.0.cell.a")
assert default.is_shared("phases.0.atoms.0.biso")
assert not default.is_shared("phases.0.scale")
assert not default.is_shared("instrument.zero_shift")
```

`SharingMap.per_histogram` and `SharingMap.shared` are lists of globs that override the default, checked in that order, and `SharingMap.is_shared` answers for one path.
Giving each pattern its own preferred-orientation axis is one override, passed as `sharing=`:

```python
from rietx.params.multi import SharingMap

per_mount = SharingMap(per_histogram=["phases.*.preferred_orientation.*"])
assert not per_mount.is_shared("phases.0.preferred_orientation.r")
assert per_mount.is_shared("phases.0.cell.a")
```

A per-pattern parameter is named with a `hist.{h}.` scope (`hist.0.instrument.zero_shift`, `hist.1.phases.0.scale`), and a shared one keeps its bare path.
A stage glob matches either form, so an existing single-pattern plan frees every pattern's copy unchanged, and a scoped glob frees one pattern's.

The cell is the one entry in that rule that is a judgement.
The structure is shared because it is one structure: space group, coordinates, ADPs and occupancies together.
The scale, background and peak widths are per-pattern, because they belong to the instrument.
Whether the cell is one number or several is a claim about the specimens: one number if the patterns are one material state, separate numbers if they differ.
That choice decides whether a wavelength can refine ([Wavelength refinement](#wavelength-refinement)).

## Two radiations

A joint fit may mix radiations.
An X-ray pattern and a constant-wavelength neutron pattern of one specimen refine one structure, the combined refinement {cite}`vondreele1997` was written for.
There is nothing extra to declare: each `Instrument` carries its own source, and every correction that depends on the radiation reads the source of the pattern it is computing.

```python
import rietx as rx

xray = rx.Instrument.debye_scherrer(wavelength=0.4132950)
neutron = rx.Instrument.constant_wavelength_neutron(1.54040, fwhm_deg=0.30)
assert (xray.source.kind, neutron.source.kind) == ("xray_cw", "neutron_cw")
assert xray.source.dispersion is not None and neutron.source.dispersion is None
```

The split between shared and per-pattern parameters has nothing radiation-specific in it.
The specimen's parameters are shared: the cell, the coordinates, the occupancies, the displacement parameters and a magnetic moment.
Each pattern keeps its own scale, background, zero shift, peak width and wavelength.

What the second radiation adds is a different weighting of the same structure factor.
X-rays scatter from electrons, so the heavier atoms dominate the form factor f, while a nucleus's scattering length b follows no such order.
Corundum ranks its two sites oppositely: f(0) is 13 electrons for Al and 8 for O, while b is 3.449 fm for Al and 5.803 fm for O (Sears's table, which `b_Sears.dat` holds).
On synthetic corundum patterns with a known answer, the X-ray pattern alone determined z(Al) about 3 times better than the neutron pattern alone, and x(O) about as well.
Refined jointly, the esd of z(Al) stayed close to the X-ray pattern's own, and the esd of x(O) fell to about two thirds of it: 0.62-0.68 across the builds tested.
The neutron pattern added the oxygen and left the aluminium to the X-rays.
In the same fits the two scales, 3.5 times apart, and two zero shifts of opposite sign each came back on their own pattern's value.

| Correction | On an X-ray pattern (`xray_cw`) | On a neutron pattern (`neutron_cw`) |
|---|---|---|
| Scattering amplitude | the form factor f₀ of the species, falling with s = sin θ/λ, plus f′ + i·f″ | b of the species, one number at every s |
| Anomalous dispersion | `Source.dispersion`, on by default | none: `NeutronSource.dispersion` is always `None` |
| Polarisation, `instrument.polarization` | refinable | pinned at K = 1 and locked |
| Magnetic structure factor | never built | built for a phase that declares a moment |
| µR estimated from composition | when the geometry declares a capillary radius, from X-ray attenuation | when the geometry declares a capillary radius, from neutron cross-sections (Sears 1992) |

A magnetic moment is shared like any other structural parameter, so the X-ray pattern carries its column and adds no gradient to it.
The magnetic term is never built there: `rietx.model.forward.magnetic_wanted` decides, from `rietx.crystallography.magnetic.scattering.MAGNETIC_SOURCE_KINDS`.
The moment is measured by the neutron pattern alone, against a structure both patterns constrain.
Three shared size coefficients, `lor_size`, `gauss_size` and `magnetic_lor_size`, are a different number per pattern.
That is a matter of wavelength rather than radiation ([Size in a joint fit](derived.md#size-in-a-joint-fit), `rietx.params.multi.SIZE_LAMBDA_POWER`).

The three diagnostics that key on the radiation, `DISPERSION_NEGLECTED`, `NEUTRON_RESONANT_ABSORBER` and `SPECIES_FALLBACK_NEUTRAL`, land on the pattern whose radiation raised them, never at the top level ([Diagnostic placement](#diagnostic-placement)).
`HistogramResult.radiation` records each pattern's source `kind` and each line's λ at the answer.
`MultiHistogramRefinement.fitted_instruments` holds each pattern's whole refined instrument.

The real-data joint fit this package is tested against is one Nd₂Ru₂O₇ specimen measured on the APS 11-BM synchrotron and the NCNR BT-1 constant-wavelength neutron diffractometer, with the neutron wavelength refined.

## Wavelength refinement

In a single fit a wavelength and the cell trade exactly.
Bragg's law {eq}`pos-bragg` gives the pattern access to λ/(2 sin θ), so only the product of λ with the reciprocal cell is measurable.
A free λ beside a free cell is therefore refused, and a free λ beside a held cell, a certified standard's, is how a wavelength is calibrated ([Wavelength refinement](instrument.md#wavelength-refinement)).

Several patterns of one specimen share one cell, and that breaks the degeneracy with the cell free.
Holding one wavelength pins the cell's scale.
The remaining N − 1 are then over-determined by the shared cell and measurable, each against the same lattice.
Holding all of them forces every monochromator's calibration error into the shared cell, and freeing all of them puts the flat direction back.
So a free wavelength requires its pattern's cell to be shared with at least one pattern whose wavelength is held.

"Exactly one held, at most N − 1 free" is that rule when every pattern shares one cell, which is the `SharingMap` default.
Un-share the cell and the single-pattern degeneracy is back, per pattern, inside a joint fit where it looks solved, so that combination is refused too.
Each refusal names its cause and states the count: "2 of 2 wavelengths are free; hold one".

Hold the wavelength of the pattern that determines the cell.
On a synchrotron-plus-neutron pair that is the synchrotron.
Its wavelength calibration is the better known, and its angular resolution makes its cell the better determined.
What the neutron data supplies is the structural content, meaning oxygen positions, site occupancies and displacement parameters, through scattering-length contrast X-rays do not have.
The neutron wavelengths then refine against a cell the X-ray pattern has pinned, which is the only way their monochromator calibrations can be measured with the cell free.

A wavelength is per-pattern under the default sharing rule, so a scoped glob frees it.
The bare path would free every pattern's copy and be refused:

<!-- api-doc: no-exec — it refines the reader's own pair of patterns -->
```python
import rietx as rx
from rietx.strategy.staged import PLAN_PRESETS, Stage

plan = PLAN_PRESETS["mccusker_structural"]()
# pattern 0 is the synchrotron and keeps its declared λ; pattern 1's neutron λ
# refines against the cell pattern 0 has pinned.  The cell and the coordinates
# refine with it, because λ trades against both.
plan.stages.append(Stage("wavelength",
                         ["hist.1.instrument.source.lines.0.wavelength",
                          "phases.*.cell.*", "phases.*.atoms.*.dof.*"]))
result = rx.refine_multi([xray, neutron], structure, [ins_x, ins_n], plan=plan)
```

The number to read is the [`WAVELENGTH_CALIBRATION`](diagnostics-refinement.md#wavelength_calibration) diagnostic on that pattern.
It reports how far λ moved from its declared value in ppm, the unit a calibration error is quoted in, and how that compares with its own esd.
A refined λ inside its own esd measured nothing, and the diagnostic says so.

Only line 0's wavelength refines, because the ratio between lines of one source is atomic physics.
A known ratio such as a λ/2 harmonic is a `Refinement.tie` with `scale=0.5` in a single fit, and a neutron `Harmonic` follows its fundamental.
The reflection list, evaluation windows and quadrature node counts are frozen from the declared λ at each stage compile.
So a free λ moves peaks inside their frozen windows, as a free cell does.
That holds while the motion is small against the window, and a few hundred ppm is: 250 ppm of λ moves a peak at 2θ = 150° by 0.11°, against a 0.30° FWHM.

All of this is constant wavelength.
The same rule carries to a time-of-flight multi-bank fit, where each bank carries its own DIFC calibration and one of them has to be held to pin the cell.
Nothing here implements it.

## Profile scan

A joint fit often has one parameter that is weakly determined for a physical reason: an antisite fraction between two elements whose scattering lengths barely differ, a site occupancy, a small strain.
Freeing it with everything else has two failure modes.
The solver can land in a local minimum, and its esd comes from a linearised curvature the data does not have.

A profile scan holds the parameter on a grid, refines everything else at each point, and reads the value off the minimum of χ² and the interval off its width.
It measures the curvature from which `rietx.optimize.statistics.normal_covariance` builds an esd, and `ParameterTable.unmeasured_rows` names what a direction the data does not move reached.
There is no scan verb.
On a single `Refinement` the scan composes verbs that exist:

| Step | Verb |
|---|---|
| fork a fresh line of work per grid point | `Refinement.branch`, `Refinement.checkout` |
| pin the scanned parameter at the grid value | `Refinement.set_values`, then `Refinement.hold` so no stage frees it |
| refine the rest | `Refinement.fit` or `Refinement.run_stage` |
| read the curve | `RefinementResult.statistics` for χ² and Rwp; `RefinementResult.phase_agreement` for that phase's R<sub>Bragg</sub> |

`set_values` and `hold` commit history nodes, so the whole scan is recoverable.
Branching per grid point keeps one point from seeding the next.

`MultiHistogramRefinement` keeps no history and has no `set_values` or `hold` verb.
Scan a joint fit with one fit per grid point, each from a structure carrying the grid value, under a plan whose stages do not free the scanned path, and read each result's `RefinementResult.statistics`.
Set the value on the shared model.
`SharingMap` decides whether the scanned path is shared, and scanning a per-pattern path pins it in one pattern only, a different experiment.

The minimum gives the value, and the interval where χ² rises by 1 above the minimum is the 1σ range for one parameter.
A scan measures only the surface it searched.
A coarse grid can step over a narrow minimum, and the interval is only as good as the grid spacing, so refine the grid near the minimum before quoting a number.

## Joint result

`RefinementResult.histograms` is a list of `HistogramResult`, one per pattern.
An empty list means an ordinary single-pattern fit.

| Field | Holds |
|---|---|
| `HistogramResult.label` | that pattern's name |
| `HistogramResult.weight` | the relative weight applied to its residual block |
| `HistogramResult.statistics` | its own agreement indices |
| `HistogramResult.two_theta`, `HistogramResult.y_obs`, `HistogramResult.y_calc`, `HistogramResult.y_background` | its curves |
| `HistogramResult.sigma` | its per-point σ |
| `HistogramResult.ticks` | its reflection positions, by phase |
| `HistogramResult.tick_hkl` | which reflection each of those is, paired by index |
| `HistogramResult.radiation` | its source kind and line wavelengths, which its figure names |
| `HistogramResult.qpa` | its phase quantities |
| `HistogramResult.restraints` | always `None`: a joint fit refuses soft restraints |
| `HistogramResult.phase_agreement` | its R<sub>Bragg</sub> and R<sub>F</sub>, per phase |
| `HistogramResult.diagnostics` | what that pattern reported |

A pooled Rwp is never quoted alone.
A single pooled number can hide a badly fitting pattern, so each pattern reports its own.
On two synthetic LaB6 patterns of one crystal, at λ = 0.41390 Å (4200 points) and λ = 0.71070 Å (8000 points), the pooled Rwp was 0.0514 while the two patterns were at 0.0411 and 0.0613.
The pooled figure describes neither.

`HistogramResult.weight` is 1.0 at unit weight, where each point's own esd governs.
`Provenance.notes` records the weighting under `histogram_weights`, as `unit (each point's esd governs)` or as each pattern's weight, so a non-unit weighting is never silent.
`RefinementResult.data_support` is `None` for a joint fit ([Diagnostic placement](#diagnostic-placement)).

`RefinementResult.for_histogram` returns a single-pattern view of one pattern.
Its curves, statistics, ticks, radiation, phase quantities and diagnostics move to the top level and `histograms` is cleared, so `result.for_histogram(0).plot()` and a report built from it work per pattern.
The view's `parameters` keep the shared rows and that pattern's own rows.
Its own rows lose their `hist.<h>.` prefix, so they are spelled as a single fit spells them.
Every other pattern's rows are dropped.
The view carries that pattern's `tick_hkl` and `phase_agreement`, and the joint result's own `tick_hkl` mirrors pattern 0's beside its `ticks`.
The view's `diagnostics` are that pattern's own, followed by the top-level findings a reader of that pattern needs, each once.
These are a finding whose `where` names one of its `hist.<h>.` rows, a `STAGE_FREED_NOTHING` whose `value` is its index, and the fit-wide `SCALE_B_INSEPARABLE`, `PARAMETRIC_OUT_OF_RANGE`, `PARAMETRIC_FORM_REJECTED` and `STAGE_PATH_UNKNOWN`.
`RefinementResult.statistics` carries the joint solve's `Statistics.max_shift_over_esd`, one shift per column of the joint parameter vector against its esd, and every view carries the same figure.
On the two LaB6 patterns a converged fit reads between 5 × 10⁻⁷ and 2.2 × 10⁻³ across both solvers, and a stage starved to one iteration reads 4.0 under LM and 17.9 under TRF.

### Diagnostic placement

A joint fit reports each diagnostic in one of two places, and the place follows from what the diagnostic is about.
A finding about one pattern goes on that pattern's `HistogramResult.diagnostics`, once per pattern: its radiation, its instrument, its counts, or how well the model fits it.
A finding about the shared structure, the joint solve or the plan goes once on `RefinementResult.diagnostics`.
So a mixed X-ray and neutron fit whose X-ray source declines anomalous dispersion raises `DISPERSION_NEGLECTED` on the X-ray pattern only.
The same holds for `SPECIES_FALLBACK_NEUTRAL`, and `NEUTRON_RESONANT_ABSORBER` goes on the neutron pattern only.
`STAGE_MAX_ITER` and `SPACE_GROUP_SETTING_ASSUMED` appear at the top level, once each.

A structural path can belong to one pattern (`SharingMap(per_histogram=...)`, or a parametric target).
So the structure's guards, `ADP_NOT_POSITIVE_DEFINITE`, `BISO_NEGATIVE`, `BISO_UNUSUALLY_LARGE` and `OCCUPANCY_ABOVE_ONE`, read every pattern's values.
A shared path is named once, bare, and a per-pattern one by its `hist.<h>.` path in each pattern that holds the value.
`CELL_RUNAWAY` names a cell that a free `vars.` coefficient drives out of its window, with the coefficient, as a single fit does.
`PHASE_HELD_IN_PATTERNS` (info) names a phase whose per-pattern structure or scale the last stage held in the patterns that cannot see it, with their count.
A scale held in one pattern is named here and nowhere else while another pattern sees the phase, because `PHASE_UNCONSTRAINED` is a joint statement that stays silent then.
`PHASE_UNCONSTRAINED` names a phase that no pattern sees, and `PHASE_HELD_IN_PATTERNS` is not raised for a phase held in every pattern.

`BACKGROUND_ABSORPTION` is the one finding on both lists.
It is raised on its pattern's list and repeated once on `RefinementResult.diagnostics`, where it keeps its `hist.<h>.` path.
Each copy is the same finding about one pattern, so count it once.

The rule is written as data.
`rietx.multi.DIAGNOSTIC_SCOPES` places the output of each function that writes diagnostics, and `rietx.multi.GUARD_SCOPES` each field of a `GuardReport`, each row with its reason.
Six rows are marked absent, for diagnostics a joint fit does not compute: the two Pawley ones (a joint fit is Rietveld-only), `HOLD_BLOCKED_PLAN` (a joint fit has no hold verb), `RESTRAINT_TENSION` (restraints are refused), and the two magnetic-width checks, `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` and `MAGNETIC_WIDTH_MOVED_MOMENT`.
The magnetic-width checks read the single-pattern plan, so a joint fit's width-before-moment ordering is unchecked.
`DATA_SUPPORT_LOW` is withheld on purpose.
Its ratio of observations to parameters has no agreed definition across patterns, and one pattern's reflections counted against the shared columns would warn about a fit the other patterns support.
Its two sibling checks, `PATTERN_UNDERSAMPLED` and `PATTERN_DEAD_CHANNELS`, are about one measurement, so each pattern gets them.

## Events and cancellation

`MultiHistogramRefinement.fit` takes `events=`, `cancel=`, `telemetry=`, `label=` and `progress=`, and each means what it means on `Refinement.fit` ([Events](refinement.md#events), [Progress lines](result.md#progress-lines)).
The fit records itself into one run directory however many patterns it holds.

<!-- api-doc: no-exec — it refines the reader's own patterns -->
```python
joint = rx.MultiHistogramRefinement(structure, [instrument_a, instrument_b])
result = joint.fit([pattern_a, pattern_b], events="joint.jsonl")
```

The joint solve is one solve, so each event kind is emitted once per fit, stage or evaluation.
On the two LaB6 patterns the log held one `fit_start`, five `stage_start`, 40 `eval`, five `stage_end` and one `fit_end`.
An `eval` measures the stacked residual.
Its `values` line up with the `free_paths` of the latest `stage_start`, where a row that belongs to one pattern is spelled `hist.<h>.` and a shared row is bare.

A fact about one pattern rides in a `histograms` list on `fit_start`, `stage_start`, `stage_end` and `fit_end`, one row per pattern, each stamped with its `histogram_index`.
Every one of those events also carries `n_histograms`.
A `fit_start` row holds `n_points` and `n_fitted`, and a `stage_start` row holds `n_points`.
A `stage_end` row holds that pattern's Rwp at the end of the stage, beside the pooled `rwp`: on the last stage of that fit, 0.0411 and 0.0613 against 0.0514, the numbers the result reports.
A `stage_start` row holds `unreached`, the globs that matched rows of another pattern and none of this one.

A cancelled stage is abandoned.
The parameter table and every pattern's models go back to where the stage found them, and the stage still ends on a `stage_end` with `status="cancelled"`.
`RefinementCancelled.completed_stages` names the stages that finished, and its `node_id` is `None`, because a joint fit keeps no history ([Cancellation](refinement.md#cancellation)).

A joint run writes no `snapshot.json`, so `rietx watch` lists it and follows its status with no picture.
The live view draws one pattern, and a joint fit has several.

`MultiHistogramRefinement.fit` takes no `stage_reports=`.
A report at each stage would be one report per pattern per stage, and a report build takes about 0.36 s however fast the fit is.
Until that changes, a joint fit's stage trajectory is its event log, with each pattern's Rwp on every `stage_end`.

## Report per pattern

`MultiHistogramRefinement.report` builds the `FitReport` for one pattern of the last fit, at Layers 0 to 2 ([The fit report](report.md)).
Its other keywords go to `build_report`.
It raises `RuntimeError` before a fit, and `IndexError` for a pattern that does not exist.

<!-- api-doc: no-exec — it reads a joint fit of the reader's patterns -->
```python
report = joint.report(1, plan="mccusker_default")
```

Each report reads that pattern's curves and statistics through `RefinementResult.for_histogram`, and that pattern's compiled model for Layers 1 and 2.
The background section reads that pattern's own absorption screen, which the joint result keeps in `Identifiability.background_absorption` under `hist.<h>.` keys.
The joint path runs no correlation, soft-mode or extra-peak screen and no screen for exchangeable parameters, so those tables are empty.

The specimen has one crystallite size, so every pattern's report carries the joint result's microstructure block, read off the shared column at pattern 0's wavelength.
On a two-wavelength pair in `tests/test_joint_report.py` both reports quote 408.82(4.86) Å, and the two patterns refined alone give 408.71(8.05) Å and 409.20(6.43) Å.
The separability caveat beside the size is each report's own, from that pattern's 2θ range.

A joint result's curves come from a compile at its answer, as a single fit's do.
The last stage solved on windows sized at the values it started from.
If it broadened the peaks, their tails stop at those windows, and a report read off that compile counts the cut as unmatched peaks.
On that size pair with the closing stage switched off, that compile gives 38 and 28 unmatched peaks, and the compile at the answer gives none.
The two compiles' χ² are compared pattern by pattern. When any pattern's differ by more than 1 %, the result carries one [`FROZEN_COMPILE_STALE`](diagnostics-refinement.md#frozen_compile_stale) naming the pattern that moved most.

## Precision of a joint fit

On the two LaB6 patterns, the shared cell came back identical in both entries of `MultiHistogramRefinement.fitted_structures`: a = 4.156597 Å, against the 4.15660 Å the patterns were built from, 0.6 ppm out.
The per-pattern zero shifts separated, at 0.005997° and −0.010008° against the 0.006° and −0.010° that went in.
The cell's esd was 2.43 × 10⁻⁶ Å, against 4.70 × 10⁻⁶ Å and 2.83 × 10⁻⁶ Å from the two patterns refined alone: 1.94 and 1.17 times smaller than either.

Those numbers come from synthetic patterns with known answers.
Real data has no truth to check against, so watch the per-pattern Rwp spread instead.
