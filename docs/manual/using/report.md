# The fit report

A converged fit gives you Rwp. The report gives you where the model and the data
disagree, what kind of error would explain it, and, separately, how much of that
the package is willing to stand behind.

:::{admonition} For agents
:class: agent
The `FitReport` is built for a program to read: numbers rather than pixels, so
a caller can close a refinement loop without looking at a plot. That is why the
sections below read as field lists.

A person gets more out of it than out of Rwp too, and `FitReport.summary` is a
paragraph of prose written for exactly that reader.

This chapter is the object model: what a `FitReport` carries, field by field,
and how to get one. The judgement (what to believe, in what order, when
to disbelieve Rwp, and how to act on an abstention) is
{doc}`the agent skill <skill>`
§4 to §6, and this chapter does not restate a line of it.
:::

The three layers answer three different questions, and each one can decline to
answer:

```{mermaid}
graph TD
  R["RefinementResult"] --> L0["<b>Layer 0</b><br/>Rwp, GoF, misfit regions,<br/>unmatched peaks<br/><i>independent of the model</i>"]
  L0 --> M{"is the fit mature<br/>enough to linearise?"}
  M -- no --> AB["<b>abstain</b><br/>FitReport.abstained_kind<br/><i>the next move is a better<br/>starting model</i>"]
  M -- yes --> L1["<b>Layer 1</b><br/>project the residual onto the<br/>shape-derivative basis"]
  L1 --> G{"do all four<br/>gates pass?"}
  G -- no --> NP["<b>reported as not passing</b><br/>RegionAttribution.gate_failures<br/><i>with the numbers</i>"]
  G -- yes --> L2["<b>Layer 2</b><br/>FitReport.suggested_actions<br/><i>advisory, never applied</i>"]
```

## Building a report

`build_report` takes a `RefinementResult`. `Refinement.report` is the same thing
from the session, and it is the form to use, because it passes the compiled
model along. Without the model there is no Layer 1 at all.

Every report stamps `FitReport.thresholds_version`, the version of the gate
thresholds it was built under ({{ THRESHOLDS_VERSION }} at this release). Store
that with any report you store: the thresholds are a versioned contract, and a
number compared across two versions compares two different questions.

The whole object is one flat map of sections, each of which is either populated
or absent for a stated reason:

| Field | Is | Section |
|---|---|---|
| `FitReport.thresholds_version` | the contract version above | n/a |
| `FitReport.rwp`, `FitReport.gof` | the two headline statistics | Layer 0 |
| `FitReport.regions`, `FitReport.n_regions_total` | the misfit clustered in 2θ | Layer 0 |
| `FitReport.unmatched` | peaks on one side only | Layer 0 |
| `FitReport.cumulative_chi2_breakpoints` | where the running χ² jumps | Layer 0 |
| `FitReport.summary` | one paragraph of prose over all of it | Layer 0 |
| `FitReport.background` | `BackgroundEvidence`, or null with no fit-time measurement | evidence |
| `FitReport.identifiability` | `IdentifiabilityEvidence`, or null | evidence |
| `FitReport.lebail_gap` | `LeBailGap`, or null outside Rietveld mode | evidence |
| `FitReport.restraints` | `RestraintReport`, or null with no restraints declared | evidence |
| `FitReport.geometry` | `GeometryTable`, or null outside a Rietveld fit | evidence |
| `FitReport.attribution` | one `RegionAttribution` per region | Layer 1 |
| `FitReport.trends` | one `TrendAnalysis` per observable | Layer 1 |
| `FitReport.texture`, `FitReport.strain` | one entry per phase, always | Layer 1 |
| `FitReport.satellites` | one `SatelliteEvidence` per phase whenever the model is available | evidence |
| `FitReport.magnetic` | one `MomentEvidence` per magnetic site whenever the model is available | evidence |
| `FitReport.layer1_available` | whether Layer 1 ran at all | Layer 1 |
| `FitReport.abstained_reason`, `FitReport.abstained_kind` | why it declined, and which kind | Layer 1 |
| `FitReport.suggested_actions` | the advisory list | Layer 2 |

Two accessors sit on top. `FitReport.action` looks a suggestion up by kind and
raises `KeyError` when there is none, so branch on the list or catch it.
`FitReport.for_stage` projects the report onto one trajectory rung, which the
last section covers.

Reports are not small. Measured on the 11-BM NAC walkthrough
([](quickstart.md)), the Le Bail report serializes to 36 kB and the two-phase
Rietveld report to 81 kB.

## Layer 0: statistics independent of the model

Nothing here depends on the model being right, so nothing here can be wrong
about the data.

- `FitReport.rwp` and `FitReport.gof`, the two headline statistics.
- `FitReport.regions`, the misfit clustered into 2θ regions, worst first.
  `FitReport.n_regions_total` says how many there were before the list was
  truncated: on the NAC Rietveld fit, 15 regions are reported of 53 found, and
  they carry 74 % of χ².
- `FitReport.unmatched`, one `UnmatchedPeak` per observed peak the model does
  not account for, and per calculated peak with no observed intensity. This is
  how an impurity phase announces itself.
- `FitReport.cumulative_chi2_breakpoints`, where along 2θ the running χ² jumps,
  which localises a problem that a per-region view spreads thin.
- `FitReport.summary`, one paragraph of prose assembled from the above.

### One misfit region

| Field | Is | Reads as |
|---|---|---|
| `Region.two_theta_lo`, `Region.two_theta_hi` | the region's edges, in degrees | cut from the peak clusters, so a region is a group of overlapping peaks and not a fixed window |
| `Region.local_rwp` | Rwp computed over those channels alone | comparable with the headline number, and usually far worse |
| `Region.chi2_share` | its share of the total χ² | the field that says whether a region matters: a terrible local Rwp on 0.1 % of χ² is not where the fit is failing |
| `Region.max_abs_delta_over_sigma` | the largest \|Δ\|/σ inside it | how bad the worst single channel is, in units the data supplied |
| `Region.n_reflections` | reflections whose centres fall inside | zero means the misfit is not on a peak this model has, which is the impurity signature |

### One unmatched peak

| Field | Is | Reads as |
|---|---|---|
| `UnmatchedPeak.two_theta` | its position | where to look |
| `UnmatchedPeak.height_over_sigma` | its height in units of the local noise | how strong the evidence is |
| `UnmatchedPeak.kind` | `"unmatched_obs"` or `"unmatched_calc"` | which side is missing: an observed peak the model lacks, or a predicted line with no intensity under it |

The list is per channel rather than per peak, so one strong impurity line
contributes a run of neighbouring entries. The length of the list is therefore a
measure of extent, and never of how many peaks or phases are missing. Measured on
the NAC Rietveld fit: 138 entries, of which 85 are `unmatched_calc` and 53
`unmatched_obs`, and those 53 sit in four clusters. Forty-eight of them lie
across 4.87 to 5.30°, and the rest are one or two entries each at 12.03°, 12.20°
and 12.44°. Cluster the positions before counting anything.

`unmatched_calc` is a Rietveld reading. It is a strong negative residual under a
tick, and Le Bail or Pawley extraction assigns a reflection with nothing under
it almost nothing, so most of the residual the detector looks for is gone. What
survives does not separate a right cell from a wrong one. Measured on a
synthetic LaB₆ pattern, it fired on 17 of the certified cell's own 28
reflections and on 94 of a doubled cell's 153, which is 61 % either way. The
count that does separate them is `LeBailValidation.predicted_but_absent`
([](indexing.md)). The blind direction is the one de Wolff's M₂₀ has, and
Oishi-Tomiyasu's reversed figure of merit exists to close it
{cite}`oishitomiyasu2013`.

## Layer 1: attributing the misfit

Layer 1 answers a different question. What kind of error is this?

The residual in each region is projected onto a shape-derivative basis built
from the profile itself (intensity, position, width, mixing, axial asymmetry),
so the answer reads "the peaks here are 0.01° low and 5 % too weak", whichever
parameters happen to be free. The five columns are not orthogonal, so they are
fitted in one joint weighted solve rather than by independent dot products,
which would cross-contaminate.

`FitReport.attribution` holds one `RegionAttribution` per region, and
`RegionAttribution.coefficients` (each a `BasisCoefficient`) is the reading.

`FitReport.layer1_available` says whether the layer ran at all.

### What one attribution carries

| Field | Is | Reads as |
|---|---|---|
| `RegionAttribution.two_theta_lo`, `RegionAttribution.two_theta_hi` | the region it read | the same edges as the matching `Region` |
| `RegionAttribution.n_reflections` | reflections inside | the columns are built from these; with none there is nothing to differentiate |
| `RegionAttribution.chi2_share` | its share of total χ² | the weight to give this statement |
| `RegionAttribution.mean_two_theta` | the reflection-weighted centre | the abscissa the trend fit below regresses against |
| `RegionAttribution.mean_fwhm` | the mean calculated width, in degrees | the scale the validity radius is measured in |
| `RegionAttribution.coefficients` | the `BasisCoefficient` list | the reading itself |
| `RegionAttribution.r2` | fraction of the local residual the basis explains | the explanatory-power gate |
| `RegionAttribution.gram_condition` | condition number of the scale-normalised Gram matrix | the resolvability gate: how far the five columns can be told apart *here* |
| `RegionAttribution.chi2_reduced` | local χ²/ν | the significance gate's statistic |
| `RegionAttribution.has_significant_misfit` | whether there is anything to attribute | false is a legitimate answer, not a failure |
| `RegionAttribution.gates_passed` | the verdict | the only field to branch on |
| `RegionAttribution.gate_failures` | one `GateFailure` per refusal | why, with the numbers |

### One basis coefficient

| Field | Is | Reads as |
|---|---|---|
| `BasisCoefficient.kind` | `intensity`, `position`, `width`, `mixing` or `asymmetry` | which shape derivative |
| `BasisCoefficient.value` | the fitted amplitude, in that kind's own units | intensity is relative (0.05 = the calculated peaks here are 5 % too weak), position is Δ2θ in degrees (positive = observed sits higher than calculated), width is ΔΓ in degrees, mixing is Δη, asymmetry is Δ(S/L) |
| `BasisCoefficient.stderr` | its standard error from the same solve | value over stderr is the significance |
| `BasisCoefficient.significant` | whether it clears that test | a coefficient below it is noise, whatever its size |
| `BasisCoefficient.share` | its share of the region's explained misfit | which of the five is doing the work |

`value` and `share` answer different questions, and reading one for the other is
the common mistake. Measured on the NAC Rietveld fit at 12.30°: the width
coefficient is +0.0010° against a mixing coefficient of +0.28, so mixing is the
larger number, while their shares are 0.45 and 0.39, which makes the width what
the region's misfit is mostly made of.

### The four gates

None of Layer 1 is trustworthy unconditionally, and the gates are the answer to
that. There are four, and every statement passes all four or the region is
reported as not passing:

| Gate | `GateFailure.code` | What it rejects, and what it reads |
|---|---|---|
| local significance | `no_significant_misfit` | a region whose "misfit" is noise, from `RegionAttribution.chi2_reduced` and `RegionAttribution.has_significant_misfit` |
| explanatory power | `local_r2` | a residual this basis does not explain at all, from `RegionAttribution.r2` |
| resolvability | `gram_condition` | columns too collinear here to be told apart, from `RegionAttribution.gram_condition` |
| validity radius | `outside_validity_radius` | a peak more than {{ VALIDITY_RADIUS_FWHM }}·FWHM from where the position coefficient would put it, so that linearising it is meaningless. The answer must be "re-detect this peak", never a confident small offset |

`RegionAttribution.gates_passed` is the verdict, and
`RegionAttribution.gate_failures` names each failure, so a rejected reading
tells you why it was rejected. Each is a `GateFailure` whose
`GateFailure.code` is one of the four above (branch on it) and whose
`GateFailure.message` carries the measured numbers.

A region that fails still reports its coefficients. They are there for
transparency rather than for reading as causes.

### Trends across regions

Above the per-region view, `FitReport.trends` regresses the region coefficients
against the angular templates a per-region view structurally cannot see: width
against 1/cos θ and tan θ, intensity against sin²θ/λ² (the
displacement-parameter signature), and position against the shapes its own
geometry has. A Bragg-Brentano fit is tested against constant, cos θ, sin 2θ
and tan θ; a capillary against constant, sin 2θ, cos 2θ and tan θ, because a
specimen displacement in the flat-plate sense is not an error a capillary can
make. Fitting the union would name aberrations the instrument does not have,
and the parameters behind them are force-fixed in that geometry anyway.

Each template is fitted alone, through the origin, and never jointly with the
others. The templates are correlated by construction, and a joint fit of
collinear ones returns physically absurd amplitudes. Measured, a 0.02°
zero-point error came back as a 1.8° `constant` cancelled by a −1.8°
`cos_theta`. So the templates are compared rather than combined, and the
ambiguity is reported as how close the runner-up came.

| Field | Is | Reads as |
|---|---|---|
| `TrendAnalysis.observable` | `position`, `width` or `intensity` | which family of coefficients was regressed |
| `TrendAnalysis.n_regions_used` | regions that passed their local gates and carried a coefficient of this kind | a coefficient the gates rejected is not evidence, and below three points no trend is fitted at all |
| `TrendAnalysis.templates` | one `TrendTemplate` per candidate shape | each fitted alone, so they are rivals rather than terms |
| `TrendAnalysis.max_template_collinearity` | largest \|correlation\| between two templates over the range actually sampled | near 1 means the range cannot separate them |
| `TrendAnalysis.separability_ratio` | the runner-up's unexplained variance over the winner's | how much more the second-best template leaves behind. 1.0 is an exact tie, and large is a clean win |
| `TrendAnalysis.separable` | the verdict from that ratio | the field to branch on |
| `TrendAnalysis.misfit_share` | share of total χ² the regressed regions carry | the weight to give the whole statement |

| Field | Is | Reads as |
|---|---|---|
| `TrendTemplate.name` | the template's physics | position: `constant` → zero shift, `tan_theta` → cell error, `cos_theta` → specimen displacement and `sin_2theta` → transparency on a flat plate, `sin_2theta` → along-beam and `cos_2theta` → across-beam offset on a capillary. Width: `inv_cos_theta` → size, `tan_theta` → strain. Intensity: `sin2_over_lambda2` → displacement parameters |
| `TrendTemplate.coefficient` | the fitted amplitude | in the observable's units |
| `TrendTemplate.stderr` | its standard error | |
| `TrendTemplate.r2` | how much of the observed trend this one physical cause accounts for | measured against the uncentred total, because the fit goes through the origin. Compare the templates against each other rather than against an absolute bar |

`TrendAnalysis.max_template_collinearity` and `TrendAnalysis.separable` are the
load-bearing pair. Over a limited angular range two templates can be
indistinguishable, and an inseparable pair is declared inseparable rather than
resolved into a confident wrong singleton. The NAC walkthrough is the
worked case: over 2–24° on a capillary, the position trend comes back
`separable=False` at a collinearity of 1.0000 and a separability ratio of 1.000,
with `constant`, `sin_2theta`, `cos_2theta` and `tan_theta` all fitted and none
preferred. Over that range on that geometry the four are the same shape, and the
report says so rather than picking one.

### Texture and directional strain

`FitReport.texture` and `FitReport.strain` give preferred orientation and
anisotropic strain the same treatment: one `TextureAnalysis` and one
`StrainAnalysis` per phase. Both are populated whenever the compiled model is
available, Layer 1's abstention included, because each is a common cause of an
immature fit and would be least available exactly when it is most needed.

| Field | Is | Reads as |
|---|---|---|
| `TextureAnalysis.phase_index` | which phase | position in `Structure.phases` |
| `TextureAnalysis.detected` | the verdict | the only field to branch on |
| `TextureAnalysis.best_axis` | the best-scoring direction, integer hkl | evidence rather than a verdict: it is filled whenever enough reflections informed the fit, so a sub-threshold `TextureAnalysis.r2` still tells you which axis got that score |
| `TextureAnalysis.march_coefficient` | the fitted March-Dollase r on that axis | below or above 1 for platy or needle habit, the sense depending on geometry |
| `TextureAnalysis.r2` | the share of the intensity misfit the model explains | |
| `TextureAnalysis.n_reflections_used` | reflections the fit had | a phase with a handful of lines cannot support this |
| `TextureAnalysis.runner_up_axis`, `TextureAnalysis.runner_up_r2` | the best non-equivalent alternative and its score | close to `TextureAnalysis.r2` means the axis is not cleanly resolved |
| `TextureAnalysis.caveat` | evidence elsewhere in the report that manufactures this signature | currently strong unmatched observed peaks: un-modelled intensity leaks into the per-reflection extraction, so an impurity can read as texture. A detection carrying a caveat measures the residual, not the specimen |

Measured on NAC: both phases report `detected=False` while carrying a best axis,
(2 1 0) at r² 0.12 for the major phase and (2 0 1) at 0.35 for the impurity. The
runners-up score 0.11 and 0.34, so neither axis is distinguishable from its
alternative, which is the state the field exists to report.

| Field | Is | Reads as |
|---|---|---|
| `StrainAnalysis.phase_index` | which phase | |
| `StrainAnalysis.detected` | the verdict | the widths are directional, a function of hkl rather than of 2θ, and a Stephens block is the model for it |
| `StrainAnalysis.anisotropy` | the fitted broadest/narrowest Λ ratio | reads as "widths along (0 0 l) are 3.4× those along (h k 0)". Its ceiling value means the fit wants zero strain along the narrowest direction, so the ratio is unbounded rather than measured |
| `StrainAnalysis.broadest_hkl`, `StrainAnalysis.narrowest_hkl` | the two directions | null when no two reflections contrast enough to name them |
| `StrainAnalysis.r2` | measured against an isotropic-strain baseline | so it answers "how much of the width variation is directional", never "how much of it is strain". A uniformly over-broad specimen scores near zero here and belongs to `instrument.profile.y` and the phase's `lor_strain` instead |
| `StrainAnalysis.n_reflections_used` | reflections the fit had | |
| `StrainAnalysis.n_patterns` | the Laue class's number of independent S_HKL | what a declared block would refine |
| `StrainAnalysis.gram_condition` | conditioning of those patterns over the sampled reflections | |
| `StrainAnalysis.separable` | whether the patterns are individually resolved | false leaves the ratio and the directions standing while the per-pattern breakdown does not: refine the block and read the fit, do not quote coefficients |

`StrainAnalysis.detected` measures the specimen rather than the residual.
Refining a `Phase.microstrain` block does not turn it False. It makes the two
agree, because the anisotropy is still there and is now modelled. Suppressing
the matching suggestion once the parameters are free is the Layer 2 veto's job
and not this field's.

### Is the unexplained intensity magnetic?

`FitReport.satellites` carries one `SatelliteEvidence` per phase and is
populated on the same terms as texture and strain, for the same reason:
intensity the model puts nowhere is a *cause* of an immature fit, so the arm has
to speak when the rest of Layer 1 abstains. It sorts the positive residual peaks
into three (on a calculated line, on a reciprocal-lattice point the nuclear
structure factor forbids, or neither) and ranks an enumerated set of candidate
propagation vectors against the third by how many fall inside the report's own
validity radius of a satellite at Q = H ± k, using no moment and no magnetic
symmetry at all. [](refining.md) documents the fields, the k = 0 signature the
second bucket carries, and the two cases where the ranking means nothing and
the arm says so.

### When Layer 1 abstains

If the fit is too immature to linearise, Layer 1 does not guess. It abstains,
says so in `FitReport.abstained_reason`, and classifies the abstention in
`FitReport.abstained_kind`:

| `FitReport.abstained_kind` | Means | The next move |
|---|---|---|
| `immature` | Rwp is high enough that the residual is dominated by something the shape basis cannot represent at all | a better starting model. Attributing structure to this residual would attribute it to the starting model |
| `resolution_limited` | the basis explains the misfit but its edit directions are indistinguishable on merged peaks | often nothing. On broad-peak data this is a legitimate stopping point, and the misfit stays readable in aggregate through Rwp and the Le Bail gap |
| `unreadable` | real misfit the local gates refuse to read, including widespread validity failure | re-detect the peaks, or re-check the cell, using the position-family evidence the reindex action carries |

An abstention is information. It says the next move is a better starting model
rather than a better interpretation. Do not convert it into a number.

It is also not monotone in Rwp. The gate is share-based: it asks what fraction
of the misfitting χ² sits in regions the local gates accept, and that share can
fall while the fit improves. Measured across the NAC Le Bail plan's five stages,
Rwp falls 3.18 → 1.04 → 0.168 → 0.159 → 0.144, and over the last three the
accepted share falls with it, 32 % → 27 % → 16 %:

```text
regions carrying 53% of χ² misfit, but only 16% of that sits in regions
the local gates accept (need 40%); Layer 1 abstains
```

Reading that as a regression is the mistake. What changed is that the profile
stages removed the misfit the gates could read, leaving the impurity behind.

## Supporting evidence

Five sections carry measurements that are not attributions. Each is there
because a fit statistic is blind to it.

### What the background is doing

`FitReport.background` is a `BackgroundEvidence`, and it exists because the two
background failure modes are both invisible in every other statistic, and they
fail in *opposite* directions.

Too flexible: the background imitates the peaks, biasing displacement parameters
up and scales (hence phase fractions) down, while Rwp improves. It is the one
failure mode that makes every number an agent reads look better, so it is
measured directly rather than inferred.

Too stiff: smooth misfit between the peaks, which Layer 0 is structurally blind
to. Its regions are peak clusters, so misfit landing between them lands in no
region and no attribution can reach it.

| Field | Is | Reads as |
|---|---|---|
| `BackgroundEvidence.absorption` | per structural parameter, the block projection R² of its Jacobian column onto the background column span | the too-flexible detector. A pairwise ρ cannot see it: measured ~0.2 per coefficient while the block absorbed ~46 %. Every screened parameter is reported, not only the notable ones, because the number is the evidence. Null rather than empty when the fit carried no Jacobian-time measurement |
| `BackgroundEvidence.worst_absorption` | the largest of those | one number to threshold |
| `BackgroundEvidence.worst_absorption_path` | which parameter | null when nothing was measured |
| `BackgroundEvidence.n_peaks` | explicit `HumpComponent` terms the fit declared | how much of the background's flexibility was localised humps rather than a smooth curve. A projection of `RefinementResult.n_background_components` and never a second count, its null included, which means nothing counted, against 0, which means none was declared. It reads that field rather than `n_extra_components`, which also counts declared sharp peaks: those are not background flexibility, and the absorption column beside this one excludes them for the same reason |
| `BackgroundEvidence.off_region_chi2_share` | share of χ² lying outside every region | the too-stiff remainder, made explicit |
| `BackgroundEvidence.off_region_chi2_reduced` | χ²/ν over those channels | above 1 there is real structure out there |
| `BackgroundEvidence.off_region_durbin_watson` | serial correlation of the same residuals | d ≈ 2 is uncorrelated noise; d ≪ 2 is a run of same-sign residuals, the background shape fighting the data {cite}`hillflack1987`. Pooled over contiguous runs only, never across a cut-out peak region |
| `BackgroundEvidence.off_region_points` | how many channels that was | the sample size behind the two numbers above |
| `BackgroundEvidence.rwp` | the headline Rwp again | context |
| `BackgroundEvidence.rwp_background_subtracted` | Rwp with the background out of the denominator {cite}`toby2006` | how much of the headline number is background rather than fit |
| `BackgroundEvidence.background_share` | Σy_bkg / Σy_obs | the same question asked of the data |

The last pair is context and never a finding, so nothing triggers on it.
Measured on two converged LaB₆ controls, a sharp fit and one under 0.6° of extra
broadening both report Rwp 0.0137 while background-subtracted they read 0.0490
and 0.0766 at a background share of 0.89. Every background-dominated
pattern crosses any useful threshold, so a trigger would fire on every lab fit.
Read it wherever a raw Rwp is about to be quoted.

On the NAC Rietveld fit the pair reads 0.0933 against 0.1108 at a background
share of 0.25, and the stiff side is the live one: χ²_red 2.50 at d = 0.40 over
12 275 off-region channels, which is 11 % of χ² that no region entry covers.

### Whether the esds mean what they appear to

`FitReport.identifiability` is an `IdentifiabilityEvidence`.

:::{warning}
There are two identifiability blocks and they are different types.
`FitReport.identifiability` is the `IdentifiabilityEvidence` documented here, a
report-time reading with the esd-qualifying statistics attached.
`RefinementResult.identifiability` is an `Identifiability`, measured on the final
Jacobian at fit time and documented in [](results.md). They share
`CorrelationPair` and `SoftMode`, and they differ on the third member: the result
carries `ExchangeRow`, the report carries the richer `ExchangeFinding` below.
:::

| Field | Is | Reads as |
|---|---|---|
| `IdentifiabilityEvidence.chi2_reduced` | the fit's χ²/ν | the multiplier the esds were scaled by |
| `IdentifiabilityEvidence.esd_inflation` | how much the reported esds exceed the unscaled ones | large means the model does not describe the data, whatever the esds look like |
| `IdentifiabilityEvidence.durbin_watson` | serial correlation of the whole weighted residual | d ≪ 2 says neighbouring channels miss the same way, so σ understates the real uncertainty |
| `IdentifiabilityEvidence.delta_r_slope`, `IdentifiabilityEvidence.delta_r_intercept` | the linear fit of \|Δ\|/σ against 2θ | a slope means the misfit is worse at one end of the pattern than the other |
| `IdentifiabilityEvidence.top_correlations` | the worst-\|ρ\| pairs, each a `CorrelationPair` | which two parameters the data cannot separate |
| `IdentifiabilityEvidence.soft_modes` | the softest directions of the normal matrix, each a `SoftMode` | the same problem where it involves three parameters or more, which a pairwise view cannot show |
| `IdentifiabilityEvidence.exchanges` | one `ExchangeFinding` per held parameter screened | what a held parameter's effect could be hiding inside the refined ones |

| Field | Is |
|---|---|
| `CorrelationPair.path_a`, `CorrelationPair.path_b` | the two dot-paths |
| `CorrelationPair.rho` | their correlation coefficient, signed |
| `SoftMode.eigenvalue` | the eigenvalue of the scale-normalised normal matrix; small is soft |
| `SoftMode.loadings` | dot-path → component, so the mode reads as a combination |

Measured on the NAC Rietveld fit: esd inflation 9.3 at d = 0.18, and the softest
mode has eigenvalue 0.0032 loading +0.80 on `instrument.profile.v` against −0.43
and −0.41 on `instrument.profile.u` and `instrument.profile.w`. That is the
Caglioti trio, which the pairwise list can only show as three separate numbers,
−0.94, −0.94 and +0.80. The
third mode is `instrument.zero_shift` against `phases.0.cell.a` at 0.71 each,
which is [](concepts.md)'s standing degeneracy measured on a real fit.

An exchange asks a different question. Could this parameter I am holding be
absorbed by the ones I am refining, so that its value is not actually
constrained by this fit?

| Field | Is | Reads as |
|---|---|---|
| `ExchangeFinding.held` | the held parameter's dot-path | the subject |
| `ExchangeFinding.r2` | how well the free block reproduces its Jacobian column | high means its effect is available elsewhere |
| `ExchangeFinding.partners` | dot-path → loading over the free block | which refined parameters would absorb it |
| `ExchangeFinding.partner` | the largest of those | the single named counterpart, or null |
| `ExchangeFinding.partner_value`, `ExchangeFinding.partner_esd` | that partner's fitted value and esd | |
| `ExchangeFinding.partner_null` | the value the partner would take if the held parameter were right | |
| `ExchangeFinding.partner_significance` | the gap between them in units of the esd | |
| `ExchangeFinding.exchangeable` | the verdict | the field to branch on |

`ExchangeFinding.r2` and `ExchangeFinding.partner_significance` are both required
because R² alone is a property of the design matrix and fires on clean fits too.
A column being reproducible by the free block says nothing until the partner has
actually moved away from where it would sit if the held value were right.

### The Le Bail gap

`FitReport.lebail_gap` is the structural-versus-profile triage: how much of the
remaining misfit a free-intensity fit could remove.

| Field | Is | Reads as |
|---|---|---|
| `LeBailGap.rwp_rietveld` | the fit's own Rwp | |
| `LeBailGap.rwp_lebail` | Rwp after `n_cycles` of intensity partitioning at frozen θ | not a Le Bail fit: background, cell, zero and profile are all held and only the per-hkl intensities move, seeded flat. It is the cheapest description the positions and profile alone support |
| `LeBailGap.ratio` | the first over the second | the statistic. Neither Rwp is one on its own |
| `LeBailGap.n_cycles` | partitioning cycles run | the measurement's own setting |

Read `LeBailGap.ratio` ≫ 1 as follows. The partition, free to reassign every
intensity, removes most of the misfit, so every line is indexed and the profile
is right, and the intensity model (structure, contents, occupancies) is what is
wrong. Phase identification is then safe at any absolute Rwp. Measured on a
pore-proxy fixture with a guest scatterer present in the data only, the ratio is
2.38 against ≤ 1.00 on every position and profile control: a wrong cell or zero
displaces the partition's peaks identically, so the gap stays flat and cannot be
confused with a position error. A ratio near 1 says intensities are not where the
remaining misfit lives, and it never says the fit is good.

It is null outside Rietveld mode, which is absence for cause: a Le Bail fit is
already the free-intensity answer. This is the IUCr guidelines' rule that a
structure-free fit's Rwp is the best profile fit the data allow, and a Rietveld
Rwp should approach it {cite}`mccusker1999`, measured rather than left to the
reader. On the NAC Rietveld fit it reads 0.0933 against 0.0806 over five cycles,
a ratio of 1.16.

### Restraints and geometry

`FitReport.restraints` carries what each soft restraint contributed, with
`RestraintReport.weight_scale` recording the c_w the stage ran at, so a deviation
can be read against the weight that was insisting on it.

`FitReport.geometry` is a `GeometryTable`, the distances and angles carried
through from the result. It is the one section here that measures the structure
rather than the fit, so it survives an abstention unchanged. "Are these
distances chemically sensible" is the question a reader asks first when the
profile evidence refuses to speak. Nothing scores it. See [](results.md) for
both objects' fields and for what the esds mean.

## Layer 2: suggested actions

`FitReport.suggested_actions` is a typed, advisory list.

| Field | Is | Reads as |
|---|---|---|
| `SuggestedAction.kind` | the action, from the closed vocabulary below | the field to branch on |
| `SuggestedAction.parameter_paths` | the dot-paths it would free | empty for the actions that are not parameter moves: adding a phase, changing the background model or re-collecting data are edits to the model or the experiment rather than to the table |
| `SuggestedAction.rationale` | a paragraph of prose | written to be read, and it names the competing readings where there are any |
| `SuggestedAction.confidence` | 0 to 1 | weights importance, the share of χ² at stake, rather than statistical significance alone |
| `SuggestedAction.alternatives` | other kinds explaining the same evidence | present exactly when the evidence does not separate them |
| `SuggestedAction.expected_delta_chi2` | the linear model's predicted Δχ², or null | see the two caveats below |
| `SuggestedAction.two_theta_range` | where the evidence is, in degrees | null when the evidence is the whole pattern |
| `SuggestedAction.vetoed_by` | where the strategy engine overruled it | set when the plan already refines the parameter, or a guard forbids it |
| `SuggestedAction.execution` | how the kind is carried out: `"stage"`, `"index"` or `"advice"` | quoted from the package's one recipe table; `"advice"` is what says empty `parameter_paths` is by design. Null only on an action built by hand, never in a report |
| `SuggestedAction.active` | true when nothing vetoed it | the predicate a trajectory filters on |

The vocabulary is closed. Thirteen actions free parameters
(`refine_zero_shift`, `refine_sample_displacement`, `refine_sample_transparency`,
`refine_capillary_offset_along_beam`, `refine_capillary_offset_across_beam`,
`refine_cell`, `refine_profile_widths`, `refine_sample_size_broadening`,
`refine_sample_strain_broadening`, `refine_axial_asymmetry`, `refine_biso`,
`refine_preferred_orientation` and `refine_scale`), and five ask for something
else: `add_impurity_phase`, `increase_background_flexibility`,
`decrease_background_flexibility`, `reindex_or_recheck_cell` and
`collect_better_data`. Only the first thirteen carry
`SuggestedAction.parameter_paths`, and `SuggestedAction.execution` states the
split on each action without this list: `"stage"` for the thirteen, `"index"`
for `reindex_or_recheck_cell`, `"advice"` for the other four.

`SuggestedAction.expected_delta_chi2` has two properties that matter to anything
rendering it. It is one number per report rather than per action, computed once
and stamped on every Layer-1-derived action, so it cannot rank or distinguish
suggestions, and the texture actions, whose evidence is per-reflection, carry
null instead. And it is no bound on what applying the action achieves. It bounds
the misfit the linear model attributes inside the gated regions, while a
refinement also moves regions that failed a gate and stretches no region entry
covers (measured: 16.19 predicted against 16.33 observed for `refine_cell`).

The action a position trend maps to is chosen by geometry, for the same reason
the templates are: `refine_sample_displacement` on a flat plate,
`refine_capillary_offset_along_beam` and `refine_capillary_offset_across_beam`
on a capillary. A suggestion naming a parameter the geometry force-fixes is one
a caller cannot act on, and this is where that is prevented rather than
apologised for afterwards. On `flat_plate_transmission`, which models neither
displacement nor transparency, a `cos_theta` or `sin_2theta` trend is
reported as a shape with no action. The diagnosis (a flat specimen off the axis)
is right, and there is no parameter a suggestion could legally free.

Advisory is the design rather than a limitation. The package never applies these
for you.

## Which parameter to free next

Layer 2 reads the residual's shape. `Refinement.suggest` asks the same question
from the other side: which held parameter has the most leverage on χ² at this
exact state. They are independent methods, and their agreement is stronger
evidence than either alone. Neither ranks by leverage alone, and the literature
states why not (Toby {cite}`toby2024`, §4): the largest-derivative parameter is
not always appropriate to vary, and his example frees an instrument width where
the broadening belongs to the sample. That is the reason leverage arrives as a
ranked list under the same strategy veto, never as an instruction.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
s = ref.suggest(data)
print(s.summary)
best = s.best_or_none()
if best is not None:
    ref.set_vary([best.path], True)
```

It is read-only in the literal sense: the probe table is applied to deep copies
of the models, no history node is recorded, and the working state is untouched.
Considering freeing a parameter is not a refinement move.

| Field | Is | Reads as |
|---|---|---|
| `SuggestionResult.groups` | the ranked answer, each a `CandidateGroup` | descending gain, and carrying only candidates above the noise floor. A converged fit therefore has an empty list, which is the correct suggestion |
| `SuggestionResult.non_separable` | candidates the absorption gate refused | their own `ParameterCandidate.absorption` says why. Reported rather than dropped |
| `SuggestionResult.skipped` | dot-paths whose columns have zero norm at this state | no leverage either way, usually a correction the geometry does not have |
| `SuggestionResult.n_evaluated` | how many candidates were scored in total | what makes "no suggestion" distinguishable from "nothing was looked at" |
| `SuggestionResult.chi2_red` | the current state's χ²/ν, seeded candidates excluded | the scale the floor is set from |
| `SuggestionResult.noise_floor` | the gain gate that was applied | {{ SUGGEST_MIN_GAIN }} × the larger of that χ²/ν and 1, so a fit already at χ²/ν ≤ 1 does not get a gate below the constant. Stored, so the serialized result explains its own gate |
| `SuggestionResult.summary` | one sentence of prose | the whole answer for a reader |
| `SuggestionResult.n_effective` | the observation count every `CandidateGroup.delta_bic` was charged at | the probe's residual rows over the square of their Bérar-Lelann factor, `optimize.statistics.effective_sample_size`. Null only where no factor was measured |
| `SuggestionResult.best_or_none` | the one defensible winner, or null | null rather than a defended tie |

| Field | Is | Reads as |
|---|---|---|
| `CandidateGroup.members` | one or more `ParameterCandidate` | |
| `CandidateGroup.gain` | the joint gain of freeing the whole group | what the data measures; the members' own gains are near-equal by construction |
| `CandidateGroup.resolved` | false exactly when there is more than one member | a tie the data cannot split, merged by pairwise collinearity rather than reported as a winner |
| `CandidateGroup.delta_bic` | the same gain read as a model-selection answer | Schwarz's ΔBIC (`report.layer2.delta_bic`, the form the whole package uses) at the Gauss-Newton prediction of what freeing the group reaches, charged at `SuggestionResult.n_effective`. Positive favours freeing, so a full refit's ΔBIC computed the same way, with `n_effective=` from the restricted fit's `Statistics.esd_inflation` (the residual `suggest` measures f on), is directly comparable |
| `CandidateGroup.delta_bic_raw_n` | the same ΔBIC at the raw residual row count | the pre-1.6 figure, an upper bound on the evidence. Where it is positive and `delta_bic` is not, the leverage is real and the serial correlation says it is not independent evidence |

The two numbers answer different questions and can disagree, and both are there
for that reason. `gain` ranks, being the leverage the parameter has on χ² at
this state. `delta_bic` decides: it charges `ln N` per parameter, so it asks whether
the leverage pays for what it costs at this pattern's channel count. Its N is
the *effective* count, the rows over the squared esd inflation, because a
powder residual is serially correlated and at raw N any improvement pays
(issue #270 measured ΔBIC +36 to +211 for a parameter within 1σ of zero; the
theory chapter has the derivation). A group can
clear the noise floor, the 3σ point of χ²₁ and the same whatever the pattern,
and still be refused by ΔBIC on a long pattern. "This parameter has leverage,
and the leverage does not pay for it" is then the honest reading. It is what a
measured pair of nested refits would tell you, available before you run them,
and `Refinement.summary`'s `next:` line is exactly this number.

| Field | Is | Reads as |
|---|---|---|
| `ParameterCandidate.path` | the dot-path | what `Refinement.set_vary` would take |
| `ParameterCandidate.gain` | the exact Gauss-Newton one-parameter predicted Δχ² | weighted SSR units and unreduced: compare it against `SuggestionResult.noise_floor` and nothing else |
| `ParameterCandidate.gradient` | ∂χ²/∂p in the parameter's physical units, sign included | which way the parameter wants to move |
| `ParameterCandidate.absorption` | R² of this column on the span of the currently-free block | 0.0 when nothing is free; near 1 is what `SuggestionResult.non_separable` collects |
| `ParameterCandidate.seeded` | whether the score was measured somewhere other than the stored value | true for a candidate sitting on a transform floor where its column is dead: softplus at 0, a Stephens block at S ≡ 0 |
| `ParameterCandidate.seed_value` | where, when it was | an assumed probe point must never look like a measured state |
| `ParameterCandidate.action_kind` | the matching `SuggestedAction.kind`, when the paths agree | the cross-reference: two independent methods naming the same move |

Measured on the NAC Rietveld fit, `ref.suggest(data)` scores 29 candidates in
0.3 s against a noise floor of 112 and returns five groups, all resolved. The
two refusals are the informative part. `phases.1.atoms.0.occ` is held back at an
absorption of 0.973 with a gain of 7529, which is the impurity's two-site
occupancy pair summing to one, and `instrument.polarization` is refused at an
absorption of exactly 1.000. Two more are skipped for zero column norm,
`instrument.geometry.axial_sl` and `instrument.geometry.axial_hl`, which is a
synchrotron capillary having no axial divergence to refine.

### After freeing it

`report.compare_freed(restricted, full)` measures what `suggest` predicted.
It takes two refinements you have already fitted on one pattern, the second
freeing everything the first frees and more. A branch that ran one more stage is
the usual pair. It runs no fit.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
from rietx.report import compare_freed

trial = ref.branch()
trial.run_stage(data, rx.Stage("occupancy", ["phases.0.atoms.2.occ"]))
c = compare_freed(ref, trial)
for p in c.freed:
    print(p.path, p.t_ratio)
print(c.delta_bic, c.delta_bic_raw_n)
```

Each freed parameter comes back with its t-ratio beside the ΔBIC of adding the
set. For one parameter the two agree, ΔBIC being close to t² − ln N_eff, so a
parameter within 1σ of where the restricted fit held it cannot be decisive. At
raw N it can. On a LaB6 fit whose model lacks the data's Lorentzian width
(21 400 channels, Durbin-Watson 0.10, f = 6.07), freeing the boron Biso gave
t = +1.58, raw-N ΔBIC +86 and ΔBIC −3.8 at N_eff 580.

| Field | Is | Reads as |
|---|---|---|
| `FreedComparison.freed` | one `FreedParameter` per path the fuller fit frees | in table order |
| `FreedParameter.held_at` | where the restricted fit held the parameter | read off its working table. For a coordinate DOF it is read through the coordinate row the DOF drives, because a DOF is a step from where its own fit began. Null where the restricted model has no such entry, a phase the fuller model adds |
| `FreedParameter.value` | the fuller fit's value | |
| `FreedParameter.esd` | the fuller fit's esd | already inflated by that fit's Bérar-Lelann factor |
| `FreedParameter.t_ratio` | (value − held_at)/esd | how far the parameter moved, in its own esd. Null where either is |
| `FreedComparison.n_added` | the free-parameter count difference | the solver's count, so a tied row adds nothing |
| `FreedComparison.n_points` | the channel count both fits saw | a comparison across two different counts is refused |
| `FreedComparison.chi2_restricted` | the restricted fit's χ² | |
| `FreedComparison.chi2_full` | the fuller fit's χ² | |
| `FreedComparison.esd_inflation` | the restricted fit's Bérar-Lelann factor f | the residual `suggest` measures f on, so a prediction and its refit are charged alike |
| `FreedComparison.n_effective` | N/f² | `optimize.statistics.effective_sample_size` |
| `FreedComparison.delta_bic` | ΔBIC charged at `n_effective` | positive favours the fuller model |
| `FreedComparison.delta_bic_raw_n` | the same at the channel count | an upper bound on the evidence, kept so the gap is visible |

There is no verdict field. A pair that is not nested raises `ValueError`: a
different channel count or mode, a path the restricted fit frees and the fuller
one does not, or nothing added. `report.predict_then_verify` fills
`VerificationOutcome.comparison` with the same record for its trial, beside the
χ² rule its `VerificationOutcome.accepted` applies.

## Reports at every stage

A converged report is routinely the least informative one in the run. A plan
absorbs an error it cannot free into whatever it can, and arrives converged with
nothing to suggest, while its own first stage named the cause out loud. So the
report exists at every stage boundary, not only at the end:

<!-- api-doc: no-exec — it refines; the executed version of this is examples/nac_11bm.py -->
```python
result = ref.fit(data, stage_reports=True)
for rung in ref.stage_reports_:
    print(rung.stage, rung.rwp, rung.summary)
```

The flag is off by default in the library, because `fit` is called in loops. The
rungs are read off states the plan already visits, so the answer is
bit-identical to the run without them.

A rung is a projection rather than a second report. It carries the numbers a fit
is judged on, the summary sentence, and the active suggestions themselves. It
deliberately carries no curves, regions or per-region attribution, because those
are the evidence for statements the summary already makes, and a rung is a
pointer to a state you can then ask about rather than a substitute for asking. It
costs what that implies: measured on the NAC Le Bail plan, the five rungs are
2.5 to 2.6 kB each against 36 kB for the full report.

| Field | Is | Reads as |
|---|---|---|
| `StageReport.stage` | the stage's name | |
| `StageReport.rwp`, `StageReport.gof` | the two headline statistics at that boundary | |
| `StageReport.summary` | the same prose paragraph `FitReport.summary` carries | by construction, so a rung and a report cannot describe the same state differently |
| `StageReport.abstained_reason`, `StageReport.abstained_kind` | the abstention at that rung | this is where the non-monotone reading above is visible |
| `StageReport.actions` | `SuggestedAction` verbatim, active ones only | not re-typed, so there is one authority for what a suggestion is. A vetoed suggestion at a stage boundary is the plan's own next stage answering it, the least informative thing a trajectory can repeat five times |
| `StageReport.n_actions_omitted` | how many the cap dropped | nothing is dropped silently |
| `StageReport.n_actions_vetoed` | how many the strategy veto removed | so the count survives even though the actions do not |
| `StageReport.n_unmatched_obs`, `StageReport.n_unmatched_calc` | the two Layer 0 counts | a phase arriving or leaving shows here first |
| `StageReport.lebail_gap_ratio` | the Le Bail gap's ratio at that rung, or null | the triage statistic, carried forward |
| `StageReport.off_region_chi2_reduced` | the between-peak χ²/ν at that rung, or null | the too-stiff background signal |
| `StageReport.worst_absorption`, `StageReport.worst_absorption_path` | the background-absorption pair, or null | the too-flexible one |

`FitReport.for_stage` builds one of these from a report. Note what it does. It
projects this report, the state it was built from, and stamps the name you pass
on the result. It does not look a past stage up, and passing the name of an
earlier stage does not recover that stage's numbers. Use `Refinement.stage_reports_`
for the trajectory, and `FitReport.for_stage` to put a single report into rung
shape.

A `StageReport` is the report at a stage boundary. The stage's own arithmetic
(what it freed, how many iterations it took, whether it converged) is a
`StageResult`, in [](refining.md).

## Comparing settings with `rietx compare`

"Did that correction help?" is not a question ΔRwp answers. Some corrections
provably cannot move Rwp (capillary absorption is an exact reparameterisation of
the scale and the displacement parameters), and others improve it by absorbing
physics that belongs elsewhere.

`rietx.viz.compare` runs a bundled standard under several settings and renders
the comparison that does settle it:

<!-- api-doc: no-exec — each call runs a full refinement of a bundled standard -->
```python
from rietx.viz import compare

record = compare.run("srm660c", "roughness_suortti")
```

Read the cumulative Δχ²-against-the-reference panel rather than the Rwp. It
localises where along 2θ the change acted, which separates a correction doing
its job from one absorbing someone else's error.
`compare.STANDARDS` and `compare.VARIANTS` are the registries, and
`rietx compare --open` is the same thing with a UI.

The house rule behind all of this: a new correction ships with a record field or
a diagnostic that states what it changed, never with an Rwp comparison as its
evidence.
