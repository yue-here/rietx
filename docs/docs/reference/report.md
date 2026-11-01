# The fit report

This page gives what a `FitReport` carries, field by field: how to build one, the misfit regions and unmatched peaks of Layer 0, the attribution, gates, trends and texture and strain readings of Layer 1, the suggested actions of Layer 2, and the report at each stage boundary.

[About the report](../concepts/report.md) explains what the three layers are for.
[Report evidence](report-evidence.md) gives the background, esd and Le Bail sections of the report.
[Model comparison](comparison.md) gives `Refinement.suggest` and the functions that compare two fits.

## Building a report

`Refinement.report` builds the report for the session's last fit.
It hands the compiled model, the structure and the instrument to `build_report`, and Layers 1 and 2 need that model.
Pass the plan you ran as `plan=`, either a plan or a preset name.
Layer 2 then marks each suggestion the plan already covers.
The session also passes its free parameters, so a suggestion to free one that is already free is marked too.

`rx.build_report(result)` builds a report from a `RefinementResult` alone.
Without the model it fills Layer 0 and the sections it reads from the result: `background`, `identifiability`, `restraints`, `geometry` and `microstructure`.
`FitReport.layer1_available` then stays false.

Three keywords set Layer 0, through either call:

| Keyword | Default | Sets |
|---|---|---|
| `top_n` | 15 | how many misfit regions the report keeps, worst first |
| `match_tol_deg` | {{ LAYER0_MATCH_TOL_DEG }} | how near a calculated position, in degrees 2θ, a residual peak must sit to count as matched |
| `min_peak_sigma` | {{ LAYER0_PEAK_SIGMA }} | how many esds a residual peak must stand from the calculated curve to be listed |

Every report stamps `FitReport.thresholds_version`, the version of the gate thresholds it was built under ({{ THRESHOLDS_VERSION }} at this release).
Store it with any report you store.
A number compared across two versions compares two different tests.

Reports are not small.
On the 11-BM NAC walkthrough, `examples/nac_11bm.py`, the Le Bail report is 38 kB of JSON and the two-phase Rietveld report 85 kB.

### What a report holds

| Field | Is | Present |
|---|---|---|
| `FitReport.thresholds_version` | the version of the gate thresholds | always |
| `FitReport.rwp`, `FitReport.gof` | the result's Rwp and goodness of fit | always |
| `FitReport.regions`, `FitReport.n_regions_total` | the misfit clustered into 2θ regions, and how many regions there were before the cut | always |
| `FitReport.unmatched` | residual peaks no calculated reflection explains, and calculated reflections with too little intensity under them | always |
| `FitReport.cumulative_chi2_breakpoints` | where the running χ² jumps | always |
| `FitReport.summary` | the report as prose, one sentence a line | always |
| `FitReport.background` | a `BackgroundEvidence` ([Report evidence](report-evidence.md#background)) | `None` when the result carries no background curve |
| `FitReport.identifiability` | an `IdentifiabilityEvidence` ([Report evidence](report-evidence.md#esds-and-identifiability)) | `None` only for a result with no channels |
| `FitReport.restraints` | the result's `RestraintReport` ([Restraint report](result.md#restraint-report)) | `None` when the fit declared no restraints |
| `FitReport.geometry` | the result's `GeometryTable` ([Bonding geometry](derived.md#bonding-geometry)) | `None` wherever `RefinementResult.geometry` is |
| `FitReport.microstructure` | a copy of `RefinementResult.microstructure` ([Size and strain](derived.md#size-and-strain)) | as on the result; Layer 1 writes the width trend's separability onto the copy |
| `FitReport.lebail_gap` | a `LeBailGap` ([Report evidence](report-evidence.md#the-le-bail-gap)) | with the model, in Rietveld mode |
| `FitReport.texture`, `FitReport.strain` | one `TextureAnalysis` and one `StrainAnalysis` per phase | with the model, in Rietveld mode, whether or not Layer 1 abstains |
| `FitReport.satellites` | one `SatelliteEvidence` per phase | with the model |
| `FitReport.magnetic` | one `MomentEvidence` per magnetic site | with the model, on a neutron pattern whose phases declare a moment |
| `FitReport.attribution` | one `RegionAttribution` per kept region that holds a reflection | with the model |
| `FitReport.layer1_available` | whether Layer 1 read the regions | true with the model when the global gate passed |
| `FitReport.trends` | one `TrendAnalysis` per observable | when Layer 1 is available |
| `FitReport.abstained_reason`, `FitReport.abstained_kind` | why Layer 1 abstained, and which kind of abstention | when the global gate refused |
| `FitReport.suggested_actions` | the `SuggestedAction` list, highest confidence first | with the model |

`FitReport.action(kind)` returns the first suggestion of that kind and raises `KeyError` when there is none.
`FitReport.for_stage` puts the report into the shape of one stage's rung ([Reports at every stage](#reports-at-every-stage)).
`print(report)` shows Rwp, the goodness of fit, the summary and each active suggestion.

## Layer 0

Layer 0 reads the observed and calculated curves, the esds and the tick positions.
It needs no compiled model and makes no linear approximation.

### Misfit regions

The report cuts the pattern into regions around clusters of peak positions.
The positions are every calculated tick, of every emission line, and every positive residual peak, so an unindexed impurity peak still gets a region.
Positions closer than twenty channel steps, or 0.15° when that is wider, join one region.
The region then extends half that gap beyond its outermost positions.

`FitReport.regions` keeps the `top_n` regions with the largest share of χ², worst first.
`FitReport.n_regions_total` counts them all.
On the NAC Rietveld fit 15 of 53 regions are kept, and they carry 74 % of χ².

| Field | Is | Reads as |
|---|---|---|
| `Region.two_theta_lo`, `Region.two_theta_hi` | the region's edges, in degrees | cut around peak clusters, so a region is a group of overlapping peaks and not a fixed window |
| `Region.local_rwp` | Rwp over the region's channels alone | comparable with the headline Rwp, and usually much worse |
| `Region.chi2_share` | the region's share of the total Σw·Δ² | whether the region matters; a high local Rwp on 0.1 % of χ² is not where the fit is failing |
| `Region.max_abs_delta_over_sigma` | the largest \|Δ\|/σ inside it | the worst single channel, in units of its esd |
| `Region.n_reflections` | calculated ticks inside the edges, every emission line counted | zero means the misfit sits on no peak this model has, which is how an impurity shows |

### Unmatched peaks

`FitReport.unmatched` holds `UnmatchedPeak` entries of two kinds.
An `unmatched_obs` entry is a local maximum of Δ/σ at least {{ LAYER0_PEAK_SIGMA }} high, with no calculated tick within {{ LAYER0_MATCH_TOL_DEG }}°.
An `unmatched_calc` entry is a local minimum of Δ/σ at least {{ LAYER0_PEAK_SIGMA }} deep within {{ LAYER0_MATCH_TOL_DEG }}° of a tick: a predicted reflection with too little intensity under it.

| Field | Is | Reads as |
|---|---|---|
| `UnmatchedPeak.two_theta` | its position, in degrees | where to look |
| `UnmatchedPeak.height_over_sigma` | its height in units of the local esd | how strong the evidence is |
| `UnmatchedPeak.kind` | `"unmatched_obs"` or `"unmatched_calc"` | which side is missing: an observed peak the model lacks, or a predicted line with no intensity under it |

Each entry is one local peak or trough of the residual, at least five channels from the next.
A broad feature therefore gives a run of entries, and the length of the list measures extent, not the number of missing peaks or phases.
On the NAC Rietveld fit the list holds 138 entries: 85 `unmatched_calc` and 53 `unmatched_obs`.
Forty-eight of the 53 lie between 4.87° and 5.30°.
The other five sit near 12.03°, 12.2° and 12.45°.
Cluster the positions before counting anything.

`unmatched_calc` is a Rietveld reading.
Le Bail and Pawley extraction set each reflection's intensity from the observed counts above the background.
A reflection predicted where there is nothing then gets almost nothing, and leaves no negative residual to detect.
In those modes the count does not separate a right cell from a wrong one.
The indexing validation counts absent reflections directly instead, as `LeBailValidation.predicted_but_absent`.
The blind direction is the one de Wolff's M₂₀ has, and Oishi-Tomiyasu's reversed figure of merit exists to close it {cite}`oishitomiyasu2013`.

### Cumulative χ² and the summary

`FitReport.cumulative_chi2_breakpoints` lists the 2θ positions where the running Σw·Δ² rises by more than 5 % of its total in one channel.
A single channel carrying that much is rare, and the list is often empty.
It is empty on the NAC Rietveld fit.
`rietx.report.cumulative_chi2` returns the whole running curve of a result.

`FitReport.summary` is the report in prose, one sentence a line.
Layer 0 opens it, and the background, identifiability, Le Bail gap and Layer 1 sections each add their lines.
On the NAC Rietveld fit it reads:

```text
53 misfit regions. The top 15 carry 74% of χ² and the other 38 carry 15%.
53 observed peak(s) match no reflection.
Between the peak regions the residual is systematic (χ²_red=2.5 over 12275 channels, Durbin-Watson d=0.40 where 2 is uncorrelated).
No region entry covers this misfit.
Layer 1 read 9 of 14 regions.
2 suggestion(s) are active.
```

## Layer 1

Layer 1 describes each region's residual as a change in the peaks there.
It fits the residual with up to five columns in one weighted least-squares solve.
The columns are the derivatives of the region's calculated peaks with respect to their intensity, position, width (FWHM), Lorentzian fraction η and axial asymmetry S/L.
Every reflection whose centre lies in the region contributes, its window clipped to the region.
The columns are not orthogonal.
Five separate projections would read part of a width error as an intensity error, and the joint solve avoids that.
A column that is zero over the region is dropped, so a region can carry fewer than five coefficients.

The residual and the columns come from two compiles of the model.
The residual is read at the closing stage's precision ([The closing stage](refinement.md#the-closing-stage)), so it carries no error of the model's own.
The columns are built at the declared stages' precision, with windows that drop 2 % of each peak, so each column stays local to its region.
At the closing precision a lab Lorentzian's window spans about ±20°.
The closing rule also builds an asymmetry column for reflections whose asymmetry is under 2 % of their width.
Near 90° that column runs almost parallel to the position column, and it failed the resolvability gate, so a zero shift and a sample displacement could not be told apart.
A residual at the declared precision misreads too: its coarser asymmetry leaves up to 5.6e-3 of a peak's maximum, and a displaced specimen read that way ranked axial asymmetry first.
`Refinement.report` compiles whichever of the two the fit's model is not, at about 2 % of the report's time.
`build_report` does the same, and refuses `model=` without `structure=` and `instrument=` for any mode but Pawley, whose model is read as it is.
The texture screen shares a point's misfit over the same declared-precision windows.

`FitReport.attribution` holds one `RegionAttribution` for each kept region that contains at least one reflection centre.
A region with none has nothing to differentiate and is left out.
On the NAC Rietveld fit 14 of the 15 kept regions are attributed.

### Region attribution

| Field | Is | Reads as |
|---|---|---|
| `RegionAttribution.two_theta_lo`, `RegionAttribution.two_theta_hi` | the region it read | the same edges as the matching `Region` |
| `RegionAttribution.n_reflections` | reflections whose centre lies inside, each emission line's image counted | the peaks the columns are built from |
| `RegionAttribution.chi2_share` | the region's share of the total χ² | copied from the `Region`; the weight to give the reading |
| `RegionAttribution.mean_two_theta` | the intensity-weighted mean of the reflection positions | the abscissa the trend fits regress against |
| `RegionAttribution.mean_fwhm` | the intensity-weighted mean calculated FWHM, in degrees | the scale of the validity radius |
| `RegionAttribution.coefficients` | one `BasisCoefficient` per column | the reading itself |
| `RegionAttribution.r2` | the fraction of the region's weighted residual the columns explain | the explanatory-power gate's statistic |
| `RegionAttribution.gram_condition` | the condition number of the columns' Gram matrix, each column scaled to unit length | the resolvability gate's statistic: how collinear the columns are in this region |
| `RegionAttribution.chi2_reduced` | the mean (Δ/σ)² over the region's channels | the significance gate's statistic |
| `RegionAttribution.has_significant_misfit` | whether `chi2_reduced` exceeds {{ MIN_REGION_CHI2_RED }} | false is a legitimate answer: the region is already fitted to the noise |
| `RegionAttribution.gates_passed` | true when no gate refused | the field to branch on |
| `RegionAttribution.gate_failures` | one `GateFailure` per refusal | which gate refused, with the numbers |

### Basis coefficients

| Field | Is | Reads as |
|---|---|---|
| `BasisCoefficient.kind` | `intensity`, `position`, `width`, `mixing` or `asymmetry` | which derivative |
| `BasisCoefficient.value` | the fitted amplitude, in that kind's units | intensity is relative (0.05 means the calculated peaks here are 5 % too weak); position is Δ2θ in degrees, positive when the observed peak sits higher; width is the FWHM change in degrees; mixing is Δη; asymmetry is Δ(S/L) |
| `BasisCoefficient.stderr` | its standard error from the same solve, scaled by the region's residual variance | |
| `BasisCoefficient.significant` | whether \|value\| exceeds {{ MIN_COEF_SIGNIFICANCE }} × stderr | below it the coefficient is noise, whatever its size |
| `BasisCoefficient.share` | its share of the region's explained misfit | which column carries the misfit |

`value` and `share` answer different questions.
On the NAC Rietveld fit, in the region from 12.11° to 12.54°, the width coefficient is +0.0010° and the mixing coefficient +0.28.
Mixing is the larger number.
Their shares are 0.45 and 0.39, so the region's misfit is mostly a width error.

### Gates

Four gates act on each region, and a fifth acts on the whole layer.

| Gate | `GateFailure.code` | Refuses |
|---|---|---|
| significance | `no_significant_misfit` | a region whose `chi2_reduced` is at most {{ MIN_REGION_CHI2_RED }}, which is fitted to the noise; the other three gates are then not tested |
| explanatory power | `local_r2` | a region whose columns explain less than a fraction {{ MIN_REGION_R2 }} of its residual |
| resolvability | `gram_condition` | a region whose `gram_condition` exceeds {{ MAX_GRAM_CONDITION }}, where the columns cannot be told apart |
| validity radius | `outside_validity_radius` | a region whose position coefficient exceeds {{ VALIDITY_RADIUS_FWHM }} × `mean_fwhm`; a first-order description does not hold that far out, and the message says to re-detect the peak |

`GateFailure.code` is one of those four and is the field to branch on.
`GateFailure.message` carries the measured number beside the threshold it failed.
A region that fails a gate still reports its coefficients.
They are there for transparency, and are not to be read as causes.

The global gate decides whether Layer 1 speaks at all.
It refuses when Rwp exceeds {{ MATURITY_MAX_RWP }}.
It also refuses when the regions with significant misfit carry more than {{ MATURITY_MIN_MISFIT_PCT }} % of χ² and less than {{ MATURITY_MIN_EXPLAINED_PCT }} % of that sits in regions that pass their gates.
A fit whose regions carry less misfit than that does not abstain, because there is nothing to attribute.

### Abstention

When the global gate refuses, `FitReport.abstained_reason` says why in a sentence and `FitReport.abstained_kind` classifies the refusal:

| `abstained_kind` | Assigned when | The next move |
|---|---|---|
| `immature` | Rwp exceeds {{ MATURITY_MAX_RWP }} | a better starting model; attributing this residual would attribute the starting model's errors |
| `unreadable` | the validity radius fails in at least half of the misfitting regions, and in a minimum number of them; also any abstention the next row does not claim | re-detect the peaks or re-check the cell; the `reindex_or_recheck_cell` suggestion carries the position evidence |
| `resolution_limited` | at least half of the failing regions fail the Gram condition, a minimum number fail it and nothing else, and those regions have a high median local R² | often nothing: on broad-peak data this is a legitimate place to stop, and the misfit stays readable in aggregate through Rwp and the Le Bail gap |

The minimum counts and the R² bar are constants in `rietx.report.schemas`.
The abstention is information, and is not to be turned into a number.
The texture, strain, satellite and moment sections, the evidence sections and the model-free suggestions still report when Layer 1 abstains.

Abstention does not fall steadily as Rwp falls.
The gate asks what share of the misfitting χ² sits in regions it can read, and that share can fall while the fit improves.
Across the five stages of the NAC Le Bail plan, Rwp falls 3.18, 1.04, 0.168, 0.159 and 0.143.
The first two stages abstain as `immature`.
Over the last three the readable share falls with Rwp, from 32 % to 27 % to 16 %, and the last stage's reason reads:

```text
Misfitting regions carry 53% of χ², but only 16% of that sits in regions the local gates accept. Layer 1 needs 40%.
```

That is not a regression.
The profile stages removed the misfit the gates could read and left the impurity behind.

### Trends across regions

`FitReport.trends` holds one `TrendAnalysis` for each observable: position, width and intensity.
Each regresses one kind of coefficient, from the regions that passed their gates, against angular templates that a single region cannot show:

| Observable | Templates, and the cause each names |
|---|---|
| position | `constant` (zero shift) and `tan_theta` (cell) on every geometry; `cos_theta` (specimen displacement) and `sin_2theta` (transparency) on `bragg_brentano` and `flat_plate_transmission`; `sin_2theta` (offset along the beam) and `cos_2theta` (offset across the beam) on `debye_scherrer` |
| width | `inv_cos_theta` (crystallite size) and `tan_theta` (microstrain) |
| intensity | `constant` (scale) and `sin2_over_lambda2` (displacement parameters) |

The position templates follow the geometry because a specimen displacement in the flat-plate sense is not an error a capillary can make.

Each template is fitted alone, through the origin, and not jointly with the others.
The templates are correlated by construction, and a joint fit of collinear templates returns physically absurd amplitudes.
Measured, a 0.02° zero-point shift came back as a 1.8° `constant` cancelled by a −1.8° `cos_theta`.
So the templates are compared rather than combined, and the ambiguity is reported as how close the runner-up came.

| Field | Is | Reads as |
|---|---|---|
| `TrendAnalysis.observable` | `"position"`, `"width"` or `"intensity"` | which kind of coefficient was regressed |
| `TrendAnalysis.n_regions_used` | regions that passed their gates and carried a coefficient of this kind | below three, no template is fitted |
| `TrendAnalysis.templates` | one `TrendTemplate` per candidate shape | rivals, each fitted alone |
| `TrendAnalysis.max_template_collinearity` | the largest \|correlation\| between two templates over the angles sampled | near 1 means this range cannot separate them |
| `TrendAnalysis.separability_ratio` | the runner-up's unexplained sum of squares over the best template's | 1.0 is a tie, and a large value is a clean win |
| `TrendAnalysis.separable` | whether that ratio exceeds {{ SEPARABILITY_MIN_SS_RATIO }} | the field to branch on, once `templates` is non-empty |
| `TrendAnalysis.misfit_share` | the share of total χ² this observable explains, summed over the regions used | the weight to give the whole statement |

| Field | Is | Reads as |
|---|---|---|
| `TrendTemplate.name` | the template | the cause in the table above |
| `TrendTemplate.coefficient` | the fitted amplitude | in the observable's units |
| `TrendTemplate.stderr` | its standard error | |
| `TrendTemplate.r2` | how much of the observed trend this one cause accounts for | measured against the uncentred total, because the fit goes through the origin; compare templates with each other, not with a fixed bar |

With fewer than three regions `templates` is empty.
`separable` and `separability_ratio` then keep their defaults, `True` and 0.0, which are not a verdict.

Over a limited angular range two templates can be indistinguishable, and the report then says so.
On the NAC Rietveld fit, over 2° to 24° on a capillary, the position trend is `separable=False` at a collinearity of 1.0000 and a ratio of 1.000.
`constant`, `sin_2theta`, `cos_2theta` and `tan_theta` are all fitted and none is preferred.

### Texture

`FitReport.texture` holds one `TextureAnalysis` per phase.
It extracts a correction factor for each reflection's intensity from the residual.
It then asks which single March-Dollase axis, of the low-index directions up to index 2, and which r reproduce those factors best {cite}`dollase1986`.
It runs in Rietveld mode with the compiled model, before the global gate, because uncorrected texture is a common cause of an immature fit.

| Field | Is | Reads as |
|---|---|---|
| `TextureAnalysis.phase_index` | which phase | its position in `Structure.phases` |
| `TextureAnalysis.detected` | true when `r2`, the departure of r from 1 and the reflection count all clear the thresholds in `rietx.report.schemas` | the field to branch on |
| `TextureAnalysis.best_axis` | the best-scoring direction, integer hkl | filled whenever enough reflections informed the fit, so a score below the threshold still names its axis; `None` with too few |
| `TextureAnalysis.march_coefficient` | the fitted March-Dollase r on that axis | below or above 1 for platy or needle habit, the sense depending on the geometry |
| `TextureAnalysis.r2` | the share of the intensity misfit the model on that axis explains | |
| `TextureAnalysis.n_reflections_used` | reflections carrying enough calculated intensity to inform the fit | a phase with a handful of lines cannot support a texture reading |
| `TextureAnalysis.runner_up_axis`, `TextureAnalysis.runner_up_r2` | the best non-equivalent alternative and its score | close to `r2` means the axis is not resolved |
| `TextureAnalysis.caveat` | set on a detection when strong unmatched observed peaks and an impurity suggestion are present | un-modelled intensity leaks into the per-reflection extraction, so an impurity can read as texture; a detection with a caveat measures the residual and not the specimen |

On the NAC Rietveld fit both phases report `detected=False` with a best axis of (2 1 0).
The major phase scores r² 0.12, the impurity 0.35, and their runners-up 0.11 and 0.34.
Neither axis is distinguishable from its alternative, which is the state the field exists to report.

### Directional strain

`FitReport.strain` holds one `StrainAnalysis` per phase, on the same terms as texture.
It asks whether the peak widths depend on hkl rather than only on 2θ, which a Stephens block {cite}`stephens1999` models.
It runs whether or not the phase declares a `Phase.microstrain` block.

| Field | Is | Reads as |
|---|---|---|
| `StrainAnalysis.phase_index` | which phase | |
| `StrainAnalysis.detected` | true when `r2`, `anisotropy` and the reflection count all clear the thresholds in `rietx.report.schemas` | the widths are directional, and a Stephens block is the model for them |
| `StrainAnalysis.anisotropy` | the fitted ratio of the broadest to the narrowest strain width | reads as "widths along (0 0 l) are 3.4 times those along (h k 0)"; its ceiling, 10⁶, means the fit wants zero strain along the narrowest direction, so the ratio is unbounded rather than measured |
| `StrainAnalysis.broadest_hkl`, `StrainAnalysis.narrowest_hkl` | the two directions | `None` when fewer than two reflections carry enough leverage to contrast; a satellite informs the fit and is never named |
| `StrainAnalysis.r2` | the share of the width variation the block explains, against an isotropic-strain baseline | answers "how much of the width variation is directional", not "how much of it is strain"; a specimen uniformly too broad scores near zero, and belongs to `instrument.profile.y` and the phase's `lor_strain` |
| `StrainAnalysis.n_reflections_used` | reflections with leverage on the widths | |
| `StrainAnalysis.n_patterns` | the number of independent Stephens coefficients in the phase's Laue class | what a declared block would refine |
| `StrainAnalysis.gram_condition` | the conditioning of those patterns over the sampled reflections | |
| `StrainAnalysis.separable` | whether the patterns are individually resolved | false leaves the ratio and the directions standing while the per-pattern breakdown does not, so refine the block and read the fit, and do not quote coefficients |

`StrainAnalysis.detected` measures the specimen, not the residual.
Refining a `Phase.microstrain` block does not turn it false.
The block makes the model and the analysis agree, because the anisotropy is still there and is now modelled.
Suppressing the matching suggestion once the parameters are free is the job of Layer 2's veto.

### Satellites and moments

`FitReport.satellites` holds one `SatelliteEvidence` per phase.
It is filled whenever the model is supplied, in any mode, and whether or not Layer 1 abstains.
It sorts the positive residual peaks into three groups: on a calculated line, on a reciprocal-lattice point the assumed space group forbids, or neither.
It then ranks an enumerated set of candidate propagation vectors by how many peaks of the third group fall within {{ VALIDITY_RADIUS_FWHM }}·FWHM of a satellite at Q = H ± k.
It uses no moment and no magnetic symmetry.
On an X-ray pattern a satellite position is a superstructure reflection, and the note says so.

`FitReport.magnetic` holds one `MomentEvidence` per magnetic site: the moment the fit measured, its esd, the form-factor approximation, and the directions the powder average could not determine.
It is empty without the model, without a declared moment, and on an X-ray pattern.
[Magnetic refinement](magnetic.md) gives the fields of both.

## Layer 2

`FitReport.suggested_actions` is a list of `SuggestedAction`, highest confidence first.
The package does not apply them on its own.
`rietx.report.predict_then_verify` tries one on a branch when you ask ([Trying a suggestion](comparison.md#trying-a-suggestion)).

| Field | Is | Reads as |
|---|---|---|
| `SuggestedAction.kind` | the action, from the closed vocabulary below | the field to branch on |
| `SuggestedAction.parameter_paths` | the dot-paths the action would free | empty for an action that is not a parameter move: adding a phase, changing the background model or collecting new data edit the model or the experiment, not the free set |
| `SuggestedAction.rationale` | a paragraph of prose | written to be read, naming the competing readings where there are any |
| `SuggestedAction.confidence` | 0 to 1 | the list's order; each emitter weighs the share of χ² at stake with the strength of its evidence, and caps the value where the evidence is ambiguous |
| `SuggestedAction.alternatives` | other kinds the same evidence supports | empty when the evidence names one cause |
| `SuggestedAction.expected_delta_chi2` | the linear model's predicted fall in the reduced χ², or `None` | one number per report; read the paragraph below the table |
| `SuggestedAction.two_theta_range` | where the evidence is, in degrees | a single position for an impurity peak (both ends equal), and the span of the low-angle regions for axial asymmetry; `None` for the other kinds, whose evidence is a trend or the whole pattern |
| `SuggestedAction.vetoed_by` | why the suggestion is inactive, or `None` | "already refined by the staged plan" when a stage of `plan=` frees one of its paths, "already free in this refinement" when the fit already frees one |
| `SuggestedAction.execution` | how the kind is carried out: `"stage"`, `"index"` or `"advice"` | `"advice"` is what says an empty `parameter_paths` is by design; `None` only on an action built by hand |
| `SuggestedAction.active` | true when `vetoed_by` is `None` | the predicate a trajectory filters on |

The vocabulary is closed, with 18 kinds.
Thirteen free parameters in one stage and carry `execution="stage"`: `refine_zero_shift`, `refine_sample_displacement`, `refine_sample_transparency`, `refine_capillary_offset_along_beam`, `refine_capillary_offset_across_beam`, `refine_cell`, `refine_profile_widths`, `refine_sample_size_broadening`, `refine_sample_strain_broadening`, `refine_axial_asymmetry`, `refine_biso`, `refine_preferred_orientation` and `refine_scale`.
`reindex_or_recheck_cell` carries `"index"`.
Its paths name the cell, `phases.*.cell.*`, and the move it asks for is an indexing search.
Four are advice: `add_impurity_phase`, `increase_background_flexibility`, `decrease_background_flexibility` and `collect_better_data`.

`SuggestedAction.expected_delta_chi2` is one number for the whole report.
It is the χ² share of each region that passed its gates times that region's local R², summed, times the fit's reduced χ².
The report stamps it on every action except the texture and background ones, so it cannot rank or distinguish suggestions.
Texture and background actions carry `None`, as does every action on an abstained report.
It is not a bound on what applying an action achieves.
A refinement also moves regions that failed a gate and stretches no region covers.
On a synthetic LaB₆ fit with the cell 0.0005 Å off, it predicted 16.16 and freeing the cell gained 16.31.

The action a position trend maps to is chosen by geometry, as the templates are.
`refine_sample_displacement` and `refine_sample_transparency` belong to `bragg_brentano`, and the two capillary offsets to `debye_scherrer`.
A suggestion naming a parameter the geometry force-fixes would be one nobody can act on.
`flat_plate_transmission` models neither displacement nor transparency.
On that geometry a `cos_theta` or `sin_2theta` trend is reported as a shape with no action.
The diagnosis, a flat specimen off the axis, is right, and there is no parameter a suggestion could free.

When Layer 1 abstains, the model-free suggestions still stand: an impurity phase for strong unmatched peaks, `reindex_or_recheck_cell` for widespread validity failures, `collect_better_data` on a `resolution_limited` abstention, and the texture and background suggestions.
An impurity is suggested only for an unmatched observed peak above {{ IMPURITY_SIGMA }} esds.

## Reports at every stage

A plan's final report is often its least informative one.
A plan can absorb an error it cannot free into what it can, and converge with nothing to suggest, while its first stage named the cause.
`fit(..., stage_reports=True)` builds a report at the end of each stage and leaves a `StageReport` per stage in `Refinement.stage_reports_`.

<!-- api-doc: no-exec — it refines; the executed version of this is examples/nac_11bm.py -->
```python
result = ref.fit(data, stage_reports=True)
for rung in ref.stage_reports_:
    print(rung.stage, rung.rwp, rung.summary)
```

The flag is off by default, because `fit` is called in loops.
The rungs are read off states the plan already visits, so the fitted values are bit-identical to a run without them.
A cancelled run keeps the rungs of the stages that completed.
Each rung's veto reads the whole plan, so a rung answers "what will this plan still not fix?".

A rung is a projection of the report, not a second report.
It carries the numbers a fit is judged on, the summary, and the active suggestions.
It carries no curves, regions or per-region attribution.
On the NAC Le Bail plan the five rungs are 2.5 kB to 2.6 kB each, against 38 kB for the full report.

| Field | Is | Reads as |
|---|---|---|
| `StageReport.stage` | the name of the stage whose end this describes | |
| `StageReport.rwp`, `StageReport.gof` | Rwp and goodness of fit at that boundary | |
| `StageReport.summary` | the report's `FitReport.summary`, verbatim | a rung and a report cannot describe one state differently |
| `StageReport.abstained_reason`, `StageReport.abstained_kind` | the abstention at that rung | where the [abstention](#abstention) shows stage by stage |
| `StageReport.actions` | the active `SuggestedAction` entries, in the report's order, at most five (`rietx.report.TRAJECTORY_MAX_ACTIONS`) | not retyped, so there is one definition of a suggestion |
| `StageReport.n_actions_omitted` | active suggestions past the cap | nothing is dropped silently |
| `StageReport.n_actions_vetoed` | suggestions the veto marked inactive | what the plan already covers |
| `StageReport.n_unmatched_obs`, `StageReport.n_unmatched_calc` | the two Layer 0 counts | a phase arriving or leaving shows here first |
| `StageReport.lebail_gap_ratio` | `LeBailGap.ratio` at that rung, or `None` | the intensity triage, carried forward |
| `StageReport.off_region_chi2_reduced` | `BackgroundEvidence.off_region_chi2_reduced` at that rung, or `None` | the sign of a background too stiff |
| `StageReport.worst_absorption`, `StageReport.worst_absorption_path` | the background-absorption headline, or `None` | the sign of a background too flexible |

`FitReport.for_stage(name)` builds a `StageReport` from a report.
It projects the state the report was built from and stamps the name you pass.
It does not look a past stage up, so passing an earlier stage's name does not recover that stage's numbers.
Use `Refinement.stage_reports_` for the trajectory.

A `StageReport` is the report at a stage boundary.
The stage's own record, what it freed, how many iterations it took and whether it converged, is a `StageResult` on `RefinementResult.stages`.
[How to run a plan one stage at a time](../guides/stage.md) uses the rungs.
