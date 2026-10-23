# Pattern diagnostics

This page gives every field `diagnose` measures on a pattern before a fit, and the two low-angle checks a fit adds afterwards.

`diagnose(data)` returns a `PatternDiagnostics`.
It needs no model, so it is a question to ask of a file before refining it, and the answer does not change afterwards.
[How to check a pattern before fitting](../guides/check.md) is the procedure, and it shows the call on the fluorapatite tutorial pattern.

`diagnose` takes three keyword arguments.
`wavelength=` lets the contamination screen place a Kβ or tungsten Lα line.
`source=` is the declared beam, which can switch that screen off ([Contamination](#contamination)).
`baseline_lambda=` fixes the baseline stiffness instead of choosing it.
Every number is measured over the channels the pattern keeps after its `excluded_regions`.
A time-of-flight pattern is refused, because every field is an angle or derived through one.

## Fields

`PatternDiagnostics` has nineteen fields.
`print(d)` puts the range in its first line and the other fields under three headings.
The first holds the rows checked on every pattern, the second the rows that matter on some instruments, and the third rietx's own measurements.
Each number prints to three significant figures.
An empty finding prints as `none`, and a check that could not run prints as `not checked`.
`auto_background` reads two of them to choose its defaults: `amorphous_hump_score` and `air_scatter_gain`.

| Field | Is | Reads as |
|---|---|---|
| `PatternDiagnostics.n_points` | the channels measured, less any excluded region | |
| `PatternDiagnostics.two_theta_min`, `PatternDiagnostics.two_theta_max` | the range, in degrees | |
| `PatternDiagnostics.signal_cutoffs` | ends of the range where the level collapsed and stayed down, each a `SignalCutoff` | read this one first ([Signal cutoffs](#signal-cutoffs)) |
| `PatternDiagnostics.dead_channels` | short runs that measure nothing and outvote the pattern while doing it, each a `DeadChannelRun` | an empty list also means the check could not run, because it needs the file's own σ ([Dead channels](#dead-channels)) |
| `PatternDiagnostics.coverage_plateau` | the bulk pattern's σ²/max(y, 1), the median over the middle half of the range | 1.0 is pure Poisson counting; any other value says the file's σ is something else, such as merged detectors or a monitor normalisation; `None` means σ was not measured, so nothing was checked |
| `PatternDiagnostics.coverage_regions` | stretches whose σ carries more variance per count than that plateau, each a `CoverageRegion` | the pattern's statistical weight is not uniform across its range ([Counting coverage](#counting-coverage)) |
| `PatternDiagnostics.steps_per_fwhm` | the median, over the resolved peaks, of how many channels span a peak's FWHM | [Peak sampling](#peak-sampling); `None` when no peak was measurable |
| `PatternDiagnostics.n_peaks_measured` | how many peaks that median was taken over | |
| `PatternDiagnostics.contamination` | the lines of a Kβ or tungsten Lα contamination finding, each a `ContaminationFlag` | an empty list is the usual answer ([Contamination](#contamination)) |
| `PatternDiagnostics.contamination_searches` | the ghost searches the contamination screen ran, `"kbeta"` and `"tungsten_la"` | an empty list means the screen ran none, so an empty `contamination` was not checked; `None` on an object written before the field existed |
| `PatternDiagnostics.air_scatter_gain` | how much of the envelope's cubic-fit residual variance a 1/(2θ) column explains | a nested-model test for the low-angle air-scatter rise; above 0.3, `auto_background` turns the 1/(2θ) background term on |
| `PatternDiagnostics.amorphous_hump_score` | the RMS of the envelope residual after both the cubic and the 1/(2θ) term, over the median level | what is left is broad non-polynomial structure, such as amorphous content or capillary glass; above about 0.05 it calls for a more flexible background |
| `PatternDiagnostics.baseline_lambda` | the arPLS stiffness the whiteness rule picked for this pattern | |
| `PatternDiagnostics.signal_to_background` | the near-maximum net signal (99.9th percentile) over the median background level | |
| `PatternDiagnostics.noise_sigma_median` | the median channel noise | the scale a peak height is significant against |
| `PatternDiagnostics.peak_fraction` | the share of channels more than 3σ above the background envelope | a statement in units of σ: a file whose σ is smaller than √y raises it with the pattern unchanged, so it does not measure how much of the pattern is peak |
| `PatternDiagnostics.n_peaks` | maxima above a height floor, with no prominence bar | an over-count by design, because a strong peak's noisy top carries several maxima and a synthetic 13-line pattern counts 27; `n_peaks_measured` is the count of peaks that were measured |
| `PatternDiagnostics.peak_density_per_deg` | `n_peaks` per degree 2θ | the same over-count per degree; nothing in rietx reads it |

## Signal cutoffs

`PatternDiagnostics.signal_cutoffs` is the field to read before the others.
Each entry is a `SignalCutoff`: an end of the range where the level collapsed to a small fraction of the interior level and stayed there.
The cause can be a detector's active area running out, a beamstop or sample-environment shielding.
Whichever it is, those channels carry no diffraction information and belong outside the fit range.

| Field | Is |
|---|---|
| `SignalCutoff.edge` | `"low"` or `"high"`: which end of the range |
| `SignalCutoff.two_theta` | the boundary, where the collapse began rather than where it reached its floor, because a fit range should stop at the onset; still a live channel, so a trim keeps it |
| `SignalCutoff.floor_fraction` | the region's median level over the interior level: how dead it is |
| `SignalCutoff.n_channels` | the channels outside the boundary, which is exactly what a trim there would drop |
| `SignalCutoff.relative_error_ratio` | the implied precision penalty, the region's median σ/y over the interior's; `None` when σ was not measured |

The two ends of a range fail differently.
Measured on a private constant-wavelength neutron PSD scan (σ from the file), the trailing end is a cliff.
The level falls from the interior level to a floor of a few per cent within a couple of degrees, then stays flat for the rest of the range.
Past it there is nothing at all.
The leading end degrades in grades: a direct-beam shoulder, a shadowed floor of a few per cent, a broad bump at a modest fraction of the interior level, then a climb that reaches the interior level only tens of degrees in.
The bump sits at d ≈ 30 Å, so it is not sample diffraction.
That structure is a beamstop halo and air scatter rather than the specimen.
Fitting a background through it describes non-specimen structure at several times the interior's fractional error.
`signal_cutoffs` reports a boundary at each end.
The leading one is within half a degree of the window the data owner's own TOPAS refinements of that file declare, and the trailing one a little further out.

:::{warning}
`diagnose` trims nothing and re-measures nothing.
It reports the cutoffs and stops, because a fit range is a protocol decision and the numbers do not settle it on their own.

Every other field of a `PatternDiagnostics` is measured over the whole range it was handed.
On that same file, the full range against the data owner's TOPAS window inflates `amorphous_hump_score` nearly twofold.
It understates `air_scatter_gain` by more than an order of magnitude, hiding the real low-angle rise entirely, and it moves `baseline_lambda` by two decades.
If you trim, call `diagnose` again on the trimmed pattern.
The first answer described the range you gave it.
:::

`SignalCutoff.relative_error_ratio` is derived rather than a second observation.
Where σ²/y is constant, as it is across that whole pattern through both transitions, σ/y is 1/√y up to a constant.
The ratio is then 1/√`floor_fraction` and says nothing the level did not.
It is reported because it is the number an experimenter reads.
That σ²/y stays flat also separates a cutoff from a coverage region: the file's σ is honest there, and the channels are empty rather than thinly covered.

## Dead channels

`PatternDiagnostics.dead_channels` lists runs shorter than a cutoff, judged wherever they sit, in the interior or touching either end of the range.
A run spanning the whole pattern is not judged, because it has no live neighbour to be weighed against.
A dead or masked detector cell, a gap between banks or a channel the electronics dropped has its intensity fall to nothing, and its esd falls with it.
Weights are 1/σ², so such a channel does more than contribute nothing.
It outvotes its neighbours, and the background model is pulled down to meet it.

| Field | Is |
|---|---|
| `DeadChannelRun.two_theta_min`, `DeadChannelRun.two_theta_max` | the interval to exclude |
| `DeadChannelRun.n_channels` | how many channels it spans |
| `DeadChannelRun.level_fraction` | the run's median intensity over the local background level |
| `DeadChannelRun.weight_ratio` | (local σ / the run's σ)², how many live channels one of these outvotes; always present, because the census needs a measured σ |

Measured on an ILL D1B constant-wavelength neutron scan of Co₃O₄ (λ = 2.52 Å), two cells read 3 and 5 counts at σ = 1.000 and 1.414, beside live channels at 36 503 counts and σ = 55.1.
Each therefore carries about 3 000 times the weight of a live channel.
Fitted with those two channels inside the range, a 12-term Chebyshev background is dragged through zero to reach them, and Rwp comes back at 0.087.
With them excluded, the same refinement gives 0.0074.
The fit with them in emits fourteen bound hits, a `BACKGROUND_ABSORPTION` for every phase and a `DATA_SUPPORT_LOW`.
None of those is the cause.

:::{warning}
This check needs the file's own σ column and answers nothing without it.
Under the Poisson fallback σ = √max(y, 1), a dead cell and a channel that honestly counted zero are the same two numbers, so there is nothing to tell apart.
An empty list on a pattern whose `coverage_plateau` is `None` means not checked.
That is a different answer from checked and clean.
`print(d)` shows it as `not checked (no measured σ)`.

Nothing is excluded for you.
A fit range is declared in `excluded_regions` on the pattern or the project ([How to limit the fit range or leave out a region](../guides/range.md)), and it is a protocol decision.
:::

## Counting coverage

`PatternDiagnostics.coverage_regions` is the one measurement here that reads the σ column rather than the intensities.
The statistic is the variance inflation σ²/max(y, 1).
It is 1 for pure Poisson counting, and proportional to 1/n<sub>eff</sub> for a channel averaged over n<sub>eff</sub> independent observations.
A region is a run of channels carrying more of it than the bulk of the scan does (`rietx.background.counting_coverage`).

On an instrument with a bank of detectors on a circle, the number of detectors contributing to a given 2θ falls off at both ends of the range, and this counts them.
Measured on two NIST BT-1 constant-wavelength neutron patterns (3.00-166.25° at 0.05°, σ from the file), both show the same ladder.
The inflation is about 5× below 8°, 2.2-2.6× out to 15°, and tapers to 1× by 55°.
It then steps back to 2.2× inside a single channel at 161.30° and holds to the end of the scan.
The levels come in steps because detectors are counted in whole numbers, so the ends read as steps rather than as a gradual falloff.

| Field | Is |
|---|---|
| `CoverageRegion.two_theta_min`, `CoverageRegion.two_theta_max` | where the region runs, in degrees |
| `CoverageRegion.inflation` | the median σ²/max(y, 1) over the region, divided by the plateau: how many times the bulk's variance per count it carries; a median over the whole span, so any bridged channels below the threshold are in it |
| `CoverageRegion.n_channels` | the region's width in channels; runs closer together than the smoothing window are merged into one, so this is the region's span, dips back below the threshold included |
| `CoverageRegion.edge` | `"low"`, `"high"` or `"interior"`: whether it sits at an end of the scanned range or inside it |

:::{warning}
A coverage region is descriptive, and it triggers nothing.
If the file's σ is right, weighted least squares already gives those channels the weight they deserve, so a region is no argument for trimming the range.
It says the pattern's statistical weight is not uniform across the range.
That is a fact about how many detectors saw each angle and not about the specimen.
Where it disagrees with a hand-chosen fit range, it is information about the range, in either direction and with no recommendation attached.

Read `CoverageRegion.edge` as a location rather than a diagnosis.
It says whether the run reached an end of the range or sat inside it, and no more.
An end region can be a detector bank's coverage running out in steps, or a synchrotron analyser bank tapering out smoothly at high angle.
An interior one can be a dead or excluded detector, two scans stitched together, a variable counting-time or slit schedule, or threshold-crossing chatter a channel or two wide.
:::

Three bundled patterns with a measured σ fire, and none of them is the plain detector falloff of the BT-1 patterns:

| Pattern | Fires | Reading |
|---|---|---|
| `11BM_NAC.fxye` | high 46.0-60.0°, 2.80× | a synchrotron analyser bank tapering out: the ratio rises smoothly across the last third, where a detector count would make a step |
| `11BM_LaB6_660a.fxye` | high 53.0-67.0°, 2.82× | the same taper |
| `nist_srm660c_100a.cif` | low 20.3-62.5°, 5.50×; interior 66.7-75.0°, 2.74×; interior 140.5-147.5°, 1.58× | a ladder that is not monotonic in either direction, which reads as a variable counting-time or slit schedule rather than a detector count; the two interior regions are threshold-crossing chatter |

It is silent on the one other bundled pattern with σ (`panalytical_attenuator.xrdml`), and returns `None` on the two with no σ column.
The σ column is structured on all three that fire, so `edge` locates the structure and this table names its cause.

The test does settle one thing: a σ column that shows this structure was measured.
The Poisson fallback σ = √max(y, 1) makes the ratio identically 1.
A pattern without a σ column therefore reports `None` and an empty list, meaning the check could not run, which differs from an empty list beside a plateau.
The same ratio also rises wherever the counts collapse to nothing while σ stays finite, a different phenomenon behind the same statistic ([Signal cutoffs](#signal-cutoffs)).

## Peak sampling

There should be at least five steps across the top of each peak, and generally no more than ten {cite}`mccusker1999`.
Below five, the integrated intensity of that reflection was never measured, and no refinement afterwards recovers it.

`PatternDiagnostics.steps_per_fwhm` is that number: the median, over the pattern's resolved peaks, of how many channels span the peak's half-height width.
`PatternDiagnostics.n_peaks_measured` says how many peaks the median was taken over.

<!-- api-doc: no-exec — it needs the reader's own pattern -->
```python
d = rx.diagnose(data)
print(d.steps_per_fwhm, "steps per FWHM over", d.n_peaks_measured, "peaks")
```

A refinement reports the same measurement on its fitted channels, as the [`PATTERN_UNDERSAMPLED`](diagnostics-refinement.md#pattern_undersampled) diagnostic, and only when it falls below five.
No code covers the upper end of the band, because oversampling costs beam time and does not bias the answer.

## Contamination

A contamination is one finding, and each `ContaminationFlag` is one line of it.
The first four fields below belong to the line and the last three to the finding.
The last three repeat across every flag of one finding.

| Field | Is |
|---|---|
| `ContaminationFlag.kind` | which ghost line the finding is of, `"kbeta"` or `"tungsten_la"` |
| `ContaminationFlag.two_theta` | this weak peak's position |
| `ContaminationFlag.parent_two_theta` | the strong peak it is a ghost of |
| `ContaminationFlag.intensity_ratio` | this peak's intensity over that parent's |
| `ContaminationFlag.leak_ratio` | the ratio fitted across every supporting parent |
| `ContaminationFlag.n_parents` | strong parents that supported the finding |
| `ContaminationFlag.n_parents_searched` | strong parents whose predicted ghost position fell inside the range |

Whether Kβ reaches the detector is a property of the optics.
So a leak puts a line at the predicted position of every strong reflection, all at one ratio.
Read one match at a time, a leak could not be told apart from a coincidence, and a coincidence is much the commoner event.
Five of the eight strongest parents must carry a candidate at a common ratio before anything is reported at all.
Read `leak_ratio` to decide whether the beam is contaminated, and `intensity_ratio` only to see how one line contributed.

:::{warning}
An empty `PatternDiagnostics.contamination` means nothing was flagged, or nothing was checked.
The Kβ position depends on the anode, so the screen needs `wavelength=`, and a wavelength matching no tabulated Kα1 is skipped without a message.
Measured on the 11-BM pattern, `diagnose(data)` and `diagnose(data, wavelength=0.4139090)` both return an empty list.
The first asked nothing, and the second has a synchrotron wavelength, which has no anode.
`diagnose(source=)` skips the screen for a neutron source and for one whose `Source.kbeta` is `"monochromator"` ([X-ray source](instrument.md#x-ray-source)).
`PatternDiagnostics.contamination_searches` tells the two answers apart.
It lists the searches that ran, and it is empty in each case above, so `print(d)` reads `not checked`.

The joint test gives up some sensitivity on purpose.
A Kβ image injected into six round-robin patterns is found on every one of them from about 10 % of its parent upwards.
Below that it depends on how many peaks the pattern has.
Zincite is caught at 1 %, and magnetite, which yields 22 usable peaks, not until 10 %.
An unfiltered tube sits at 14 % (Hölzer et al. 1997), which is the case the screen is for.
A residual leak past a working filter is below the floor and comes back as nothing.
:::

## Low-angle checks after a fit

A fitted result carries two checks on the low-angle end that `air_scatter_gain` cannot make.
`air_scatter_gain` tests the envelope's shape over the whole range, so a beam or air-scatter tail a few tens of channels wide out of several hundred barely moves it.
Measured on a real pattern it reads 0.019 against the 0.3 trigger, because the tail carried 0.3 % of the whole-range residual the nested fit compares.

### Residual below the first reflection

[`LOW_ANGLE_UNMODELLED`](diagnostics-refinement.md#low_angle_unmodelled) reads the fit's own residual over [`two_theta_min`, first tick − 2·FWHM).
The first tick is taken over every phase, every emission line and every declared peak, so a peak's own low-angle flank is never counted.
It fires when that region's mean weighted squared residual exceeds three times the whole-pattern reduced χ², and `Diagnostic.value` carries the ratio.

The first tick is the lowest one with intensity behind it.
A reflection counts when the norm of its calculated window, in units of σ, reaches {{ PHASE_SUPPORT_SIGMA }} on some emission line.
That is the threshold `PHASE_UNCONSTRAINED` applies to a phase, applied reflection by reflection.
A Kα2 or λ/2 image of a reflection the data sees therefore keeps its place however weak it is on its own.
A tick with nothing behind it does not move the boundary: a phase held at a vanishing scale, a declared peak at zero area, or a reflection whose structure factor is zero.
The FWHM is the instrumental width alone, from the Caglioti U, V, W and the Lorentzian X, Y.
The check is silent when the region holds fewer than ten channels: no reflection carries intensity at all, or the first one sits at or near the low edge.

The message reports the ratio and leaves the remedy open.
Raising the pattern's lower limit to where the residual falls under 2σ and adding the background's air-scatter term are both available.
Only someone looking at the pattern can tell whether the region is outside the beam or the background model is locally wrong there.

### Undeclared air-scatter term

`auto_background` declares the P-spline's 1/(2θ) term only when `air_scatter_gain` crosses 0.3, and a declined term is absent, so no plan can free it.
On a line-dense synchrotron capillary pattern with a broad hump, that envelope test is blind.
Its 3° windows miss a rise confined to the first few degrees, and they sit far above the true background where the lines crowd.
On the synthetic NAC pattern of `tests/test_air_scatter_undeclared.py` (λ = 0.4133 Å, 0.5-50°, 0.005° steps) it reads 0.0042 with a strong rise and 0.044 without one.

[`AIR_SCATTER_UNDECLARED`](diagnostics-refinement.md#air_scatter_undeclared) asks the fit instead.
It fires on a P-spline with no air term when refitting the background with a 1/(2θ) column, the Bragg model held, would remove at least 0.5 % of χ² and at least 25 times the reduced χ².
`Diagnostic.value` is the fraction.
It is the one-column score test on the fit's own residual, so it needs no refit.
It is one-sided, because the term is bounded at zero and cannot follow a residual leaning the other way.

On that pattern it reads 0.13 with the rise, where declaring the term cuts χ² by 24 %, and it is silent on the control, where declaring the term cuts nothing.
A weaker rise that `LOW_ANGLE_UNMODELLED` misses, because the rise runs on under the first lines, still reads 0.012.
Where the spline can draw 1/(2θ) on its own, the projected column is small and the code is silent.
The suggestion gives the remedy: declare the term and refit.
