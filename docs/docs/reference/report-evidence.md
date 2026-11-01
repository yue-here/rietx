# Report evidence

This page gives the sections of a `FitReport` that measure the fit instead of attributing its misfit: what the background is doing, whether the esds mean what they appear to, and the Le Bail gap.

None of these sections rests on a linear approximation of the model, so each still reports when Layer 1 abstains.
[The fit report](report.md) gives the rest of the report.
[About the report](../concepts/report.md#evidence-beside-the-layers) says what each section is for.
The bond restraints, the bonding geometry and the size and strain readings are carried from the result unchanged: [Restraint report](result.md#restraint-report), [Bonding geometry](derived.md#bonding-geometry) and [Size and strain](derived.md#size-and-strain) give their fields.

## Background

`FitReport.background` is a `BackgroundEvidence`, or `None` when the result carries no background curve.
It measures the two ways a background fails, which no other statistic shows and which pull in opposite directions.

A background too flexible imitates the peaks.
It biases displacement parameters up and scales, and so phase fractions, down, while Rwp improves.
Every number a reader checks looks better, so the report measures the effect directly.

A background too stiff leaves smooth misfit between the peaks.
Layer 0's regions are peak clusters, so that misfit lands in no region and no attribution reaches it.

[How flexible a background should be](../concepts/parameters.md#how-flexible-a-background-should-be) explains the trade between the two.

| Field | Is | Reads as |
|---|---|---|
| `BackgroundEvidence.absorption` | dot-path → the block projection R² of that structural parameter's Jacobian column onto the span of the background columns, for every parameter screened | the detector for a background too flexible; a pairwise ρ cannot see it, measured at about 0.2 per coefficient while the block absorbed about 46 %; `None` when nothing was screened |
| `BackgroundEvidence.worst_absorption`, `BackgroundEvidence.worst_absorption_path` | the largest entry and its parameter | one number to compare; `None` exactly when `absorption` is, which means not measured and does not mean clean |
| `BackgroundEvidence.n_peaks` | the declared `HumpComponent` terms | `RefinementResult.n_background_components` carried over: `None` means nothing was counted, and 0 means none was declared |
| `BackgroundEvidence.off_region_chi2_share` | the share of χ² in channels outside every Layer 0 region | the misfit no region covers; it follows how many channels lie between the regions more than how much misfit lies there, so it is no detector |
| `BackgroundEvidence.off_region_chi2_reduced` | the mean (Δ/σ)² over those channels | about 1 when they are fitted to the noise |
| `BackgroundEvidence.off_region_durbin_watson` | the Durbin-Watson d of the residual over those channels | d ≈ 2 is uncorrelated noise, and d well below 2 a run of same-sign residuals, the background shape fighting the data {cite}`hillflack1987`; `None` when too few of the channels are adjacent |
| `BackgroundEvidence.off_region_points` | how many channels lie outside every region | the sample behind the two numbers above |
| `BackgroundEvidence.rwp` | the result's Rwp | context |
| `BackgroundEvidence.rwp_background_subtracted` | Rwp with the background removed from both curves {cite}`toby2006` | how much of the headline Rwp is background rather than fit; `None` when the result carries no background curve |
| `BackgroundEvidence.background_share` | Σy<sub>bkg</sub> / Σy<sub>obs</sub> over the fitted channels | the same question asked of the data |

`absorption` is `None` in three cases.
The fit carried no screen from its Jacobian, as on a replay.
Its last stage freed no scale, Biso, occupancy or ADP to screen.
Or it freed no background term to screen them against.
Every Le Bail and Pawley fit is the second case, since those modes fix every scale, Biso, occupancy and ADP.

`n_peaks` counts the background humps and not the declared sharp peaks, which add no background flexibility.
The absorption table leaves the sharp peaks out for the same reason.
[Background component counts](result.md#background-component-counts) gives both counts.

"Outside every region" means outside every region Layer 0 cut, including the ones past `top_n`.
The Durbin-Watson d is pooled within contiguous runs of those channels and never taken across a peak region.

The summary adds a line when the worst absorption, or the off-region pair of χ² and d, crosses its threshold in `rietx.report.schemas`.
The section is on the report either way.

The Rwp pair is context and never a finding, so nothing triggers on it.
On two converged synthetic LaB₆ fits, one sharp and one under 0.6° of extra broadening, both report Rwp 0.0137.
Background-subtracted they read 0.0490 and 0.0768, at a background share of 0.89.
Every pattern dominated by its background would cross any useful threshold on the pair, so a trigger would fire on every laboratory fit.
Read the pair wherever a raw Rwp is about to be quoted.

On the NAC Rietveld fit the pair reads 0.0933 against 0.1108, at a background share of 0.25.
The worst absorption is 0.014, on `phases.0.atoms.0.biso`.
The stiff side is the live one: χ²<sub>red</sub> 2.50 at d = 0.40 over 12 275 off-region channels, which carry 11 % of χ² that no region covers.

## Esds and identifiability

`FitReport.identifiability` is an `IdentifiabilityEvidence`, or `None` for a result with no channels.
It puts the statistics that qualify an esd beside the evidence of which parameters the data cannot separate.

:::{warning}
There are two identifiability blocks, and they are different types.
`FitReport.identifiability` is the `IdentifiabilityEvidence` on this page, read when the report is built.
`RefinementResult.identifiability` is an `Identifiability`, measured on the final Jacobian when the fit runs ([Identifiability](result.md#identifiability)).
They share `CorrelationPair` and `SoftMode`.
For the held parameters the result carries `ExchangeRow` and the report carries `ExchangeFinding`, which adds the partner's significance.
:::

| Field | Is | Reads as |
|---|---|---|
| `IdentifiabilityEvidence.chi2_reduced` | the fit's reduced χ², `Statistics.chi2` | the factor the covariance was scaled by |
| `IdentifiabilityEvidence.esd_inflation` | the Bérar-Lelann factor the quoted esds already carry, `Statistics.esd_inflation` | how far the serial correlation of the residual widened every esd; divide it out for the esd before inflation ([Esds and the Bérar-Lelann inflation](../theory/estimation.md#esds-and-the-bérar-lelann-inflation)) |
| `IdentifiabilityEvidence.durbin_watson` | the Durbin-Watson d of the whole weighted residual | d well below 2 says neighbouring channels miss the same way, so σ understates the real uncertainty |
| `IdentifiabilityEvidence.delta_r_slope`, `IdentifiabilityEvidence.delta_r_intercept` | the straight line through the normal probability plot of the residual, sorted Δ/σ against the value a normal distribution predicts at each rank | slope 1 and intercept 0 when the residuals are Gaussian on the stated σ; a slope above 1 says σ is underestimated; `None` with fewer than eight channels |
| `IdentifiabilityEvidence.top_correlations` | the pairs with the largest \|ρ\|, each a `CorrelationPair` | which two parameters the data cannot separate |
| `IdentifiabilityEvidence.soft_modes` | the softest directions of the scale-normalised normal matrix, each a `SoftMode` | the same problem among three or more parameters, which no pairwise list shows |
| `IdentifiabilityEvidence.exchanges` | one `ExchangeFinding` per held parameter the fit screened | whether a held parameter's effect could hide in the refined ones |

The last three are carried from the fit, and are `None` when the fit measured none of them.
`None` means not measured, as on a replay, and never "well conditioned".
[Identifiability](result.md#identifiability) gives the fields of `CorrelationPair` and `SoftMode`.

On the NAC Rietveld fit the esd inflation is 8.1 at d = 0.18, and the probability plot's slope is 2.8.
The softest mode has eigenvalue 0.0032, loading +0.80 on `instrument.profile.v` against −0.43 and −0.41 on `instrument.profile.u` and `instrument.profile.w`.
That is the Caglioti trio, which the pairwise list can only show as three separate numbers, −0.94, −0.94 and +0.80.
The third mode loads `instrument.zero_shift` against `phases.0.cell.a` at 0.71 and 0.70, the zero-and-cell degeneracy of [About correlations and esds](../concepts/correlations.md).

### Exchanges

An exchange asks whether a parameter you held could be absorbed by the ones you refined, so that its value is not constrained by this fit.

| Field | Is | Reads as |
|---|---|---|
| `ExchangeFinding.held` | the held parameter's dot-path | the subject |
| `ExchangeFinding.r2` | the block projection R² of its column onto the span of the free columns, measured at fit time | high means its effect is available elsewhere |
| `ExchangeFinding.partners` | dot-path → loading of that reconstruction over the free parameters | which refined parameters would absorb it |
| `ExchangeFinding.partner` | the most-loaded partner that has a null value | `None` when no partner has one, and the row can then never be exchangeable |
| `ExchangeFinding.partner_null` | that null value | where the partner does nothing: 0 for the zero shift, the specimen displacement, the transparency and the two capillary offsets |
| `ExchangeFinding.partner_value`, `ExchangeFinding.partner_esd` | the partner's fitted value and esd | |
| `ExchangeFinding.partner_significance` | \|value − null\| / esd | how far the partner moved from doing nothing, in its own esds |
| `ExchangeFinding.exchangeable` | true when `r2` and `partner_significance` both clear their thresholds in `rietx.report.schemas` | the field to branch on; the data cannot then say which of the two is the physical cause |

Both halves are required.
`ExchangeFinding.r2` alone is a property of the design matrix over the sampled range, and is high on clean fits too: 0.999945 on both a fixture with a planted displacement and its clean reference.
A reproducible column says nothing until the partner has moved significantly from its null.
The summary speaks only for the rows where `exchangeable` is true.

## The Le Bail gap

`FitReport.lebail_gap` is a `LeBailGap`: the Rietveld Rwp against that of a Le Bail partition of the same peaks.
It says how much of the remaining misfit free intensities could remove.
It is `None` outside Rietveld mode, because a Le Bail or Pawley fit already is the free-intensity description, and on a report built without the model.

| Field | Is | Reads as |
|---|---|---|
| `LeBailGap.rwp_rietveld` | the fit's own Rwp | |
| `LeBailGap.rwp_lebail` | Rwp after `n_cycles` of Le Bail intensity partitioning at the converged values | not a Le Bail fit: background, cell, zero and profile are all held, only the per-reflection intensities move, seeded flat, and no refinement runs; the description the positions and profile alone support |
| `LeBailGap.ratio` | `rwp_rietveld` over `rwp_lebail` | the statistic; neither Rwp is one on its own |
| `LeBailGap.n_cycles` | the partitioning cycles run, 5 | the measurement's own setting |

A ratio well above 1 means the partition, free to reassign every intensity, removes most of the misfit.
Every line is then indexed and the profile is right, and the intensity model is what is wrong: the structure, the contents or the occupancies.
Phase identification is then safe at any absolute Rwp.
On a synthetic LaB₆ fixture with a guest scatterer in the data and not in the model, the ratio is 2.89.
On the position and profile controls it is at most 1.00: 0.99 on the converged fit, and 1.00 with a 0.05° zero-point shift or with the cell 200 ppm off.
A wrong cell or zero displaces the partition's peaks as much as the model's, so the gap stays flat and cannot be mistaken for a position error.
A ratio near 1 says the intensities are not where the remaining misfit lives, and does not say the fit is good.

The summary quotes the gap when the ratio is notable.
The IUCr guidelines say a structure-free fit's Rwp is the best profile fit the data allow, and a Rietveld Rwp should approach it {cite}`mccusker1999`.
The gap measures that distance instead of leaving it to the reader.
On the NAC Rietveld fit it reads 0.0933 against 0.0806 over five cycles, a ratio of 1.16.
