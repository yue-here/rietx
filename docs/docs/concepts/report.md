# About the report

A `FitReport` reads a finished fit in three layers: where the misfit is, what the misfit looks like, and what to change.
Each layer claims only what its evidence supports, and says so when that is nothing.

## Getting a report

`Refinement.report()` builds the report for the last fit.
Pass the plan you ran as `plan=`, so the report does not suggest freeing what the plan already frees.
`rx.build_report(result)` builds one from a `RefinementResult` alone.
Without the compiled model it can fill Layer 0 only, and its `layer1_available` is false.

Printing a report shows Rwp, the goodness of fit, a short summary, the sentence on numbers not yet validated (below) and each suggestion still active.
Rwp counts every point, background included, and `FitReport.background` also gives the background-subtracted Rwp.
R<sub>Bragg</sub> and R<sub>F</sub> are on the result, per phase, in `RefinementResult.phase_agreement`.
They are computed from intensities the model itself partitioned, so they favour the model and are not evidence that a change helped.
The report's thresholds carry a version, currently {{ THRESHOLDS_VERSION }}, in `FitReport.thresholds_version`.
A report stored under another version was judged against other thresholds.

The fit's diagnostics are on the result, in `RefinementResult.diagnostics`, and the report does not repeat them.
Each `Diagnostic` has a level, a code, a message with the numbers behind it, the parameter names it concerns, and a suggested next step.
[Diagnostic codes](../reference/diagnostics.md) lists every code.

## Layer 0: where the misfit is

Layer 0 makes no assumption about the model being right.
It gives the agreement indices and the cumulative χ² along the pattern, whose steep stretches show where the misfit lies (David 2004).
It cuts the pattern into regions around peak clusters and ranks them by their share of χ².
It lists observed peaks no calculated reflection accounts for, and calculated reflections with no observed peak.
An observed peak must stand {{ LAYER0_PEAK_SIGMA }} esds above the calculated curve to be listed.
Layer 2 suggests an impurity phase only for a peak above {{ IMPURITY_SIGMA }} esds.

Layer 0 can say where the misfit is and how much of χ² it carries.
It cannot say why.
Its unmatched-peak list has one entry per local maximum of the residual.
A broad unindexed feature can give several entries, so the length of the list is not a count of peaks.

## Layer 1: what the misfit looks like

Layer 1 describes each region's residual as a change in the peaks there.
It fits the residual with five shapes together: the derivatives of a peak with respect to its intensity, position, width, Lorentzian fraction and axial asymmetry.
The answer reads as "the peaks here sit 0.01° low and are 5 % too weak".
That statement holds whichever parameters the plan freed.

A region's reading is used only if it passes four checks:

- its local reduced χ² is above {{ MIN_REGION_CHI2_RED }}, so there is misfit to describe;
- the five shapes explain at least a fraction {{ MIN_REGION_R2 }} of the residual (R²);
- the five shapes are distinguishable over this region, measured by the condition number of their scale-normalised Gram matrix, at most {{ MAX_GRAM_CONDITION }};
- the position change is under {{ VALIDITY_RADIUS_FWHM }} times the peak's FWHM, where a first-order description holds.

A single coefficient counts only when it is more than {{ MIN_COEF_SIGNIFICANCE }} times its esd.

Layer 1 also judges the fit as a whole, and abstains when the fit is too far from right to read.
It abstains above an Rwp of {{ MATURITY_MAX_RWP }}.
It also abstains when the misfitting regions carry more than {{ MATURITY_MIN_MISFIT_PCT }} % of χ² and the regions that pass the checks hold less than {{ MATURITY_MIN_EXPLAINED_PCT }} % of that.
`FitReport.abstained_kind` says which case applies:

- `immature`, an Rwp above the limit;
- `unreadable`, most failing regions too far off for a first-order description;
- `resolution_limited`, most failing regions with shapes the data cannot tell apart, which is not evidence that the model is wrong.

### Trends across the pattern

A shift that varies with angle points at a cause.
A constant shift suggests the zero, cos θ a flat-plate specimen displacement, and tan θ the cell.
Layer 1 fits each such shape to the position shifts of all regions, one shape at a time, and reports the best.
When the runner-up leaves less than {{ SEPARABILITY_MIN_SS_RATIO }} times the best one's unexplained variance, it reports the trend as not separable.
Over a short angular range these shapes are close to proportional, and a joint fit of all of them would split one error into large cancelling parts.
The shapes on offer depend on the geometry, so a capillary fit is never offered a flat-plate correction.

## Layer 2: what to change

Layer 2 turns the readings into `SuggestedAction` objects.
Each has a kind, a confidence between 0 and 1, the reasoning, and the parameters it would free.
When the evidence fits more than one kind, the action lists the alternatives.
Most kinds free parameters in a new stage.
One asks for the cell to be re-indexed, and the rest are advice: add an impurity phase, make the background more flexible or less, or collect better data.

A suggestion changes nothing by itself.
`rietx.report.predict_then_verify` tries one on a branch of the refinement and accepts it if χ² falls by more than 1 %.
The working state stays where it was.

Whether a freed parameter is worth its place is a separate question.
rietx answers it with the change in the Bayesian information criterion (BIC), which weighs the fall in χ² against the extra parameter.
`Refinement.suggest` predicts it for each parameter the plan has not freed, and `rietx.report.compare_freed` measures it once a refit has freed one.
The [theory chapter](../theory/estimation.md#which-parameter-to-free-next) gives both.

## Evidence beside the layers

Some evidence does not fit the three layers and is reported beside them:

- `FitReport.background`, whether the background is too flexible or too stiff ([About parameters](parameters.md#how-flexible-a-background-should-be));
- `FitReport.identifiability`, the statistics that qualify an esd (reduced χ², the Bérar-Lelann inflation, the Durbin-Watson statistic) and the strongest correlations;
- `FitReport.lebail_gap`, the Rwp against that of a Le Bail partition of the same peaks, where a ratio well above 1 says the intensities are what is wrong;
- `FitReport.restraints`, `FitReport.geometry` and `FitReport.microstructure`, the bond restraints, the bond lengths and angles, and the size and strain readings.
- `FitReport.not_independently_measured`, one sentence naming each reported number from a feature that rietx has not yet compared with an independent measurement, such as a certified cell or a weighed composition. It states the package's own record, the same for every fit, and says nothing about this fit's quality.

These still report when Layer 1 abstains.

## Reports at every stage

A fit's final state is often the least informative one.
A plan can absorb an error it cannot free and converge without suggesting anything, while its first stage named the cause.
`fit(stage_reports=True)` builds a report at the end of each stage and leaves them on the refinement as `stage_reports_`.
The fit's answer is the same with them or without.

The [fit-to-report section](../theory/estimation.md#from-fit-to-report) of the theory states the layers formally.
