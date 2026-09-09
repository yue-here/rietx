# Reading the numbers

A finished fit hands back a `RefinementResult`. This chapter is what is on it,
and how to read each part: the agreement indices, the two structure R-factors,
the distances and angles, what any restraints did, and the two counts that say
whether the pattern could support the model at all. The refined parameter values
themselves are the one part covered elsewhere, in [](model.md), because they are
a view of the parameter table rather than a statistic about the fit.

The guidelines rank that evidence, and the ranking is not the one a table of R
values suggests. The two most important criteria for judging a refinement are
the fit of the calculated pattern to the observed one and *the chemical sense of
the structure* {cite}`mccusker1999`. Rwp is half of the first.

Where a section here names a formula, Part 2 carries it as a numbered equation
and this chapter links to it rather than restating it.

## Fit statistics

`RefinementResult.statistics` is a `Statistics` object. The definitions follow
Toby {cite}`toby2006`, and Part 2 gives them as equation
{eq}`est-indices`.

| Field | Is | Reads as |
|---|---|---|
| `Statistics.rwp` | the weighted profile R-factor | how well the calculated pattern matches the measured one, weighted by the counting statistics. A **fraction**: 0.0933 is 9.3 %. |
| `Statistics.rp` | the unweighted profile R-factor | the same comparison with every point weighted equally, so strong peaks dominate it. |
| `Statistics.rexp` | the expected R-factor | the Rwp that perfect counting statistics alone would produce. It is a property of the data and the parameter count, not of the model. |
| `Statistics.chi2` | the **reduced** χ², Σw δ²/(N − P) | how far the fit is from statistical perfection. 1.0 means the residual is the size of the noise. |
| `Statistics.gof` | Rwp / Rexp | the square root of `Statistics.chi2`. Also called S or χ. |
| `Statistics.rwp_background_subtracted` | Rwp with the background removed from both patterns | the more meaningful figure when the background carries most of the raw intensity. |
| `Statistics.durbin_watson` | the serial-correlation statistic | ≈ 2 means neighbouring residuals are independent. Far from 2 means the misfit is structured, whatever Rwp says. |
| `Statistics.esd_inflation` | the Bérar-Lelann factor | the amount the reported esds were multiplied by to account for that serial correlation. It has **already been applied**. |
| `Statistics.n_points` , `Statistics.n_free_parameters` | N and P | what makes the rest interpretable. |
| `Statistics.max_shift_over_esd` | max \|Δθ\|/esd over the last accepted step, external units both sides | the convergence quantity (McCusker 1999 §7: converged when ≤ 0.1, a band quoted and never tuned). A converged fit satisfies it a fortiori; on a stage that stopped on its iteration budget it says **how far** the solve was still moving. `None` when it cannot be measured: no accepted step, no esds, a replay, or a joint multi-pattern fit. |
| `Statistics.identifiability_clause` | the report's identifiability sentence, verbatim: the exchange finding with the swap experiment and its license, and/or the softest notable mode | the same sentence the report's summary carries, delivered beside the numbers so a consumer that reads only the statistics block still gets it. The evidence behind it is `FitReport.identifiability` ([](report.md)). Written by `build_report`, never by the fit: `None` until a report is built, and `None` when nothing crossed a comment threshold, and neither is a verdict about the fit. |

`Statistics.chi2` is the reduced χ², not Σw δ². The two differ by a factor of
N − P, which on a real pattern is several thousand.

The literature is not consistent about which of the two is called χ². The IUCr
guidelines {cite}`mccusker1999` write χ² = Rwp/Rexp and say it should approach 1;
that quantity is `Statistics.gof` here, and `Statistics.chi2` is its square. Both
conventions say the same thing about a fit, and the naming here follows Toby
{cite}`toby2006`, but a number copied from a paper needs the convention copied
with it.

`Statistics.esd_inflation` is conservative by construction. Perfectly white
residuals still land near 1.51, because same-sign runs happen by chance, and lab
data with unmodelled profile detail typically lands at 2 to 4. Treat it as an
upper bound on the serial-correlation damage rather than as a measurement of it.

(structure-agreement-indices)=
## Structure agreement indices

Every field above measures the *pattern*. Two more measure the **structure**, and
a journal will ask for at least one of them {cite}`mccusker1999`. They live on
`RefinementResult.phase_agreement`, one `PhaseAgreement` row per phase, keyed by
`PhaseAgreement.name`, the same name the phase carries everywhere else. Part 2
defines both as equation {eq}`est-structure-r`.

| Field | Is | Reads as |
|---|---|---|
| `PhaseAgreement.r_bragg` | R_B, the Bragg-intensity R-factor | how well the model reproduces the *integrated intensities* I = m·F² with m the multiplicity, rather than the profile. Written to a CIF as `_refine_ls_R_I_factor`. |
| `PhaseAgreement.r_f` | R_F, the structure-factor R-factor | the same comparison on the amplitude rather than the intensity, so it is the number a single-crystal R is directly comparable with. Written as `_refine_ls_R_factor_all`. |
| `PhaseAgreement.n_reflections` | how many reflections were summed | smaller than the phase's reflection list whenever one falls off the Ewald sphere. |

A joint multi-histogram fit reports them per histogram, on
`HistogramResult.phase_agreement`: the partition is of one pattern's counts, so
there is no pooled value.

Both are biased towards the model you are testing. A powder pattern does not
measure individual reflection intensities, because overlapped peaks share their
counts, so the "observed" intensity of each reflection is the observed pattern
*partitioned in proportion to the calculated one*. A wrong model therefore
receives the intensity it predicted, and both indices flatter it. That is the
paper's own warning, and it fixes what they are for: watching an R_B fall as you
improve a model, not judging a model in isolation.

A trace phase's R_B is not comparable with the major phase's. Neither index is
weighted (the sums count every reflection alike, whatever its counting
statistics), so a reflection the fit barely constrains weighs as much as one
that dominates it, and a minor phase's windows sit under
the major phase's peaks, where the counts the major phase failed to describe are
handed out too. Measured on the 11-BM NAC pattern with its 1.35 wt % CaF₂
impurity: NAC reads R_B 0.052 and the impurity 0.385, with the whole of the
impurity's misfit in four reflections at I(obs)/I(calc) ≈ 2.2, every one of
them under a strong NAC peak with a large positive residual. Read R_B beside the
phase's weight fraction, and treat a trace phase's value as a question rather
than a measurement.

Both are absent, an empty list, for a Le Bail or Pawley fit. There the
intensities *are* the fit, so the partition would be compared against itself.

## The bonding geometry

The other thing a journal asks for is the distances and angles, and the
guidelines rank them above every R value: the two most important criteria for
judging a refinement are the profile fit and *the chemical sense of the
structure* {cite}`mccusker1999`. `RefinementResult.geometry` is a
`GeometryTable` carrying them.

| Field | Is | Reads as |
|---|---|---|
| `GeometryTable.distances` | one `GeometryDistance` per neighbour | every asymmetric-unit atom's **whole** environment, so the number of rows naming an atom is its coordination number. A bond between two sites is therefore in the list twice, once from each end. |
| `GeometryTable.bonds` , `GeometryTable.contacts` | the two halves of that list | split by `GeometryDistance.bonded`: at most the two covalent radii plus `GeometryTable.bond_slack`, or beyond it out to `GeometryTable.contact_max`. The guidelines ask for both: "interatomic distances (both bonding and nonbonding) should be reasonable". |
| `GeometryTable.angles` | one `GeometryAngle` per pair of bonded neighbours | at every vertex, over that vertex's complete bonded environment. Contacts are not arms. |
| `GeometryTable.notes` | where coverage stopped | a per-atom contact cap or a phase too large to search. Empty means nothing was bounded. |

A row's value is `GeometryDistance.distance` in ångströms, or
`GeometryAngle.angle` in degrees. Each names its atoms twice. Once by the labels
the structure carries, as `GeometryDistance.atom_1` and
`GeometryDistance.atom_2`, with `GeometryAngle.atom_1`, `GeometryAngle.atom_2`
and `GeometryAngle.atom_3` putting the vertex in the middle. Once by index, as
`GeometryDistance.atom_index_1`, `GeometryDistance.atom_index_2`,
`GeometryAngle.atom_index_1`, `GeometryAngle.atom_index_2` and
`GeometryAngle.atom_index_3`, which index `Phase.atoms` directly.
`GeometryDistance.phase_index` and `GeometryAngle.phase_index` say which phase,
in a multi-phase fit.

`GeometryDistance.symmetry_2` is the CIF `n_klm` code of the image the second
atom sits at, and resolves against the operation list the exported CIF writes
beside it. `GeometryDistance.symmetry_1` is always `.`, the published position;
so is `GeometryAngle.symmetry_2`, the vertex, while `GeometryAngle.symmetry_1`
and `GeometryAngle.symmetry_3` code the two arms.

### The esd is the point

`GeometryDistance.stderr` is propagated through the **whole** parameter
covariance, which is what the guidelines require of any derived quantity: "the
whole correlation matrix, not just the diagonal elements, should be included in
the calculation" {cite}`mccusker1999`. Part 2 gives the propagation as equation
{eq}`est-derived`. `GeometryDistance.stderr_diagonal` is the same propagation
with the refined parameters' correlations zeroed, the number a reader combining
the printed parameter esds in quadrature would get. It is carried so the
difference is visible rather than asserted, and it is never the answer.
`GeometryAngle.stderr` and `GeometryAngle.stderr_diagonal` are the same pair, in
degrees.

```{image} figures/geometry-esd-light.png
:class: only-light
:alt: Diagonal-only esd divided by the full-covariance esd for each NAC distance, scattered from 0.86 to 1.41 on both sides of a dotted line at one
```

```{image} figures/geometry-esd-dark.png
:class: only-dark
:alt: Diagonal-only esd divided by the full-covariance esd for each NAC distance, scattered from 0.86 to 1.41 on both sides of a dotted line at one
```

Dropping the correlations is not a conservative approximation, and that is the
whole reason both numbers are reported. The figure is the 88 distances of an
11-BM NAC refinement under `mccusker_structural` (Rwp 0.0819), each plotted as
its diagonal-only esd over its full one: the ratio runs from 0.86 to 1.41, on
both sides of equality, so the cheap number is sometimes too small and
sometimes 40 % too large, with nothing in the row to say which.

The spread appears only once the *coordinates* refine. Under a plan that frees
the cell and nothing structural, a cubic phase's distances depend on one free
parameter, the quadratic form has one term, and the two esds agree to the last
digit. Correlation between coordinates is what the guideline is about, which is
also why a table quoted from a profile-only refinement has nothing to say here.

An esd is `None` when it cannot be measured, which is absence rather than
σ = 0. Four routes lead there, and they mean the same thing. A result with no
covariance behind it (any evaluate-only pass, a replay of a history node
included) has distances and no esds at all. So does a row nothing free
reaches. A row whose value is fixed by symmetry has no variance to report: a
fluorite Ca–F distance with the cell held, or a rutile O–Ti–O angle, which stays
at exactly 90° however the one free coordinate degree of freedom moves. And an
angle at 0° or 180° is a stationary point, where the linearisation behind
{eq}`est-derived` does not hold at all. The distance or angle itself is exact in
every one of the four; it is the uncertainty that is withheld.

Geometry is Rietveld-only. `RefinementResult.geometry` is `None` in Le Bail and
Pawley mode, where the dummy atom the mode requires is not a structure to
measure, and it is computed at the close of the fit rather than on demand: the
covariance it needs is read off the final Jacobian, which is never stored.

## The size and the strain, in physical units

A refined profile width is a number of degrees, and a number of degrees is not
transferable: the same 0.09° of 1/cosθ broadening is a 400 Å coherent domain on
Mo Kα and a 233 Å one on Cu Kα. `RefinementResult.microstructure` is one
`PhaseMicrostructure` per phase, in phase order, carrying the four sample
coefficients read as the two quantities behind them. Part 2 states the two
conversions as equations {eq}`ms-size-coefficient` and {eq}`ms-strain-coefficient`.

| Field | Is | Reads as |
|---|---|---|
| `PhaseMicrostructure.phase_index` , `PhaseMicrostructure.phase_name` | which phase this block is about | the index into `Structure.phases` and that phase's `Phase.name`, so a block reads on its own in a multi-phase fit. |
| `PhaseMicrostructure.terms` | one `MicrostructureTerm` per sample coefficient the phase carries | four rows — `lor_size`, `gauss_size`, `lor_strain`, `gauss_strain` — whether or not any of them refined. `PhaseMicrostructure.term("lor_size")` fetches one by coefficient name. |
| `MicrostructureTerm.kind` | `"size"` or `"strain"` | which conversion produced `MicrostructureTerm.value`: a **coherent domain size** in ångströms, or a dimensionless Δd/d. |
| `MicrostructureTerm.coefficient` | the refined coefficient itself | in its stored units, deg 2θ for the Lorentzian pair and deg² for the Gaussian variances, so a row can be checked against `RefinementResult.parameters` without converting anything. |
| `MicrostructureTerm.value` , `MicrostructureTerm.esd` | the reading and its uncertainty | `None` for cause; `MicrostructureTerm.unavailable` says which cause. |
| `MicrostructureTerm.path` | the parameter path it came from | `phases.0.lor_size` and so on, so the row joins to `RefinementResult.parameters` and to any diagnostic's `where`. |
| `PhaseMicrostructure.wavelength` , `PhaseMicrostructure.scherrer_k` | the two constants the size reading used | the source's longest declared line, and the Scherrer *K*. Carried so a size can be rescaled to another convention without knowing which build produced it. |
| `PhaseMicrostructure.size_agreement` , `PhaseMicrostructure.strain_agreement` | the Gaussian reading divided by the Lorentzian one | 1 means the two independent columns describe one specimen. `None` when either reading is absent. |
| `PhaseMicrostructure.separable` , `PhaseMicrostructure.size_strain_collinearity` | whether size and strain are distinguishable over the range measured | read below before quoting either number. `None` means the report did not assess it. |

`FitReport.microstructure` is the same list, carried onto the report so a
reader working from `Refinement.report()` need not go back to the result — with
the separability caveat below filled in, which is the one part the report adds.

A coherent domain size is the length over which the lattice diffracts in phase.
It is **not** a particle size and must not be reported as one: `Phase.particle_radius_um`
is a different quantity for a different correction, the absorption path through
a grain, and a particle is an aggregate of domains. Nor is a domain size a
two-figure number. *K* moves 10–20 % with crystallite shape, so
`SCHERRER_K = 0.9` is one convention among several — GSAS-II reads its size off
the same FWHM with *K* = 1, FullProf off the integral breadth, which for a pure
Lorentzian is 1.571× rietx's answer. Quote the size as an order of magnitude,
with the *K* the row carries.

### Why size and strain are quoted with a caveat

Over a short 2θ range 1/cosθ and tanθ are nearly the same curve, so a fit can
trade a size against a strain with no cost in Rwp. That is the Williamson–Hall
problem, and it is the reason a size is reported with `PhaseMicrostructure.separable`
attached rather than on its own. The verdict is the width trend's own
(`TrendAnalysis.separable` on the `"width"` observable, with
`PhaseMicrostructure.size_strain_collinearity` carrying the correlation it was
decided on), so the report holds one opinion about it, not two. It is `None` —
no claim made — when Layer 1 abstained or no width trend was fitted.

Where it says `False`, quote neither number alone. Refining one of the pair and
holding the other is not a workaround: the answer then depends on which one was
held. Measuring over a wider range is.

### The esds, and the four absences

Each reading is a function of exactly one refined coefficient, so its esd is
that coefficient's scaled by the derivative and nothing is dropped: a size's
relative esd equals its coefficient's, and so does a strain's. A *combined*
Gaussian-plus-Lorentzian size would be a function of two correlated columns and
is deliberately not reported — the two are read separately and compared through
`PhaseMicrostructure.size_agreement` instead.

`MicrostructureTerm.unavailable` names why a number is missing, and the four
answers mean different things.

| `unavailable` | What happened |
|---|---|
| `"at_zero"` | the coefficient is at its off state, where a size is infinite and a strain is a perfect lattice. True, and not a number to report. This is what a phase whose widths were never refined says, in all four rows. |
| `"no_wavelength"` | the source declares no emission line, so no size can be read. Never reaches a strain, which has no wavelength in it. |
| `"not_measured"` | the coefficient carries no esd, so `MicrostructureTerm.value` stands and `MicrostructureTerm.esd` does not: the parameter was never freed, its column measured nothing, or the result came from `rietx.replay`. |
| `None` | nothing is missing. |

### A joint fit shares the size, not the degrees

In a multi-histogram fit `MultiHistogramRefinement` normalises the size
coefficients by wavelength, because a size coefficient is proportional to λ
while a strain coefficient is not. The shared column is the coefficient at the
first histogram's wavelength and every histogram's own structure copy carries
the one it needs, so the crystallite behind them is a single number and the
`SIZE_NORMALISED_ACROSS_WAVELENGTHS` diagnostic says so. Read a shared
`phases.*.lor_size` as histogram 0's coefficient, never as the number your
second pattern shows.

## How many observations there are

`Statistics.n_points` is the N the least-squares algorithm uses, and it is not
the number of observations the pattern holds. Only the integrated intensities of
individual reflections are unique observations {cite}`mccusker1999`; the profile
steps across one peak are repeated measurements of the same number. The
consequence is that the algorithm will refine far more parameters than the data
support, without complaining, because its N runs into the thousands.

`RefinementResult.data_support` is a `DataSupport` object carrying the count
that answers this. Part 2 states the correction it applies as equation
{eq}`est-mind`.

| Field | Is | Reads as |
|---|---|---|
| `DataSupport.n_unique_reflections` | reflections this pattern measured, summed over phases | one symmetry orbit is one reflection, and a Kα doublet's second line is the same reflection measured again, not a second observation. A reflection counts when a fitted channel lies within half its own FWHM of its position, so an excluded region removes what sits under it and a peak half-measured at a range end still counts. |
| `DataSupport.n_effective_observations` | the same count corrected for overlap | each reflection contributes the fraction of its own area on which no overlapping reflection stands higher, so an isolated line is worth 1 and an exactly coincident pair is worth 1 between the two of them. A **float**, because a partly resolved pair is worth more than one and less than two. |
| `DataSupport.n_structural_parameters` | the free parameters the ratio is about | the atomic ones: coordinate DOFs, occupancies, Biso, ADP components. The cell, zero, profile, background, scale, preferred orientation and extinction are excluded, because peak positions and shape determine those rather than the intensities being counted. |
| `DataSupport.observations_per_parameter` | the raw count divided by the parameters | the upper bound on the ratio. `None` when no structural parameter is free, which is a profile-only stage, a Le Bail fit or a Pawley fit. |
| `DataSupport.effective_observations_per_parameter` | the effective count divided by the parameters | **the number the guideline is about**: at least three and preferably five {cite}`mccusker1999`. `None` on the same terms as the row above. |

The complement of `DataSupport.n_structural_parameters` is
`Statistics.n_free_parameters` minus it: the profile, background and cell
parameters, which the same fit refined against the same pattern but which the
peak *positions* pay for.

`DataSupport.n_unique_reflections` over-counts, on purpose. Two reflections at
the same 2θ are one observation, and both are counted here. In a cubic cell that
pair is common: (300) and (221) coincide exactly. The raw count is therefore an
upper bound on the information, and the ratio built from it is optimistic.
`DataSupport.n_effective_observations` is the corrected number, by the method of
Altomare *et al.* {cite}`altomare1995`, and the gap between the two is the
pattern's overlap.

```{image} figures/effective-observations-light.png
:class: only-light
:alt: Reflection count flat at 26 while the effective observation count falls from 22 to 4 as the peaks broaden
```

```{image} figures/effective-observations-dark.png
:class: only-dark
:alt: Reflection count flat at 26 while the effective observation count falls from 22 to 4 as the peaks broaden
```

The figure is one Cu Kα LaB6 pattern over 15-140°, holding the cell and the
reflection list fixed and widening the peaks with Lorentzian size broadening
alone, so the overlap is the only thing that moves. Twenty-six reflections
throughout; 22.0 effective observations while the lines are sharp, and 3.7 by
the time the pattern is one hump. The raw count cannot see any of that, which
is what makes it the wrong denominator for a parameter ratio.

The estimate is not a theorem. The paper says so, and the IUCr guidelines
repeat it: the approach "may not have a rigorous basis", and what it gives is a
reasonable estimate of how many parameters the data will support. Two numbers a
reader should have with it: the interval each reflection is judged over is
±2 FWHM, and the paper's own check at ±4 FWHM lands 6.5 % lower on average, so
the reported figure is a little generous.

Nothing here refuses anything. The number is evidence, read beside the fit
rather than as a gate on it, and a ratio below three is a reason to hold
parameters rather than a reason the fit is wrong. The sharper question, *which*
parameter is unsupported rather than how many the pattern can carry, is the
next section. A ratio below five raises the `DATA_SUPPORT_LOW` diagnostic, as a
warning below three and as information between three and five.

## Which parameters the data could not separate

`RefinementResult.identifiability` is an `Identifiability`, and it exists because
these statistics cannot be recovered afterwards. They are read off the **final
Jacobian**, an N × P array nothing serializes (a history node stores state, not
curves), so they are screened at fit time or lost. Rwp and the residual, which
any consumer can recompute from the arrays already on the result, are the
contrast.

| Field | Is | Reads as |
|---|---|---|
| `Identifiability.background_absorption` | dot-path → the block projection R² of that structural column onto the background column span | how much of a parameter the background could imitate. Every screened path is here, not only the ones over the guard threshold: a fired/not-fired bit is a verdict, 0.46 against 0.08 is evidence, and these are the *same* numbers the `BACKGROUND_ABSORPTION` diagnostic decided on rather than a second measurement |
| `Identifiability.top_correlations` | the worst-\|ρ\| pairs, each a `CorrelationPair`, worst first | which two refined parameters moved together |
| `Identifiability.soft_modes` | the softest directions of the scale-normalised normal matrix, each a `SoftMode` | the same problem where it involves three parameters or more, which no pairwise list can show |
| `Identifiability.exchangeability` | one `ExchangeRow` per held parameter screened | whether a parameter you held could have been absorbed by the ones you refined |

| Field | Is |
|---|---|
| `CorrelationPair.path_a`, `CorrelationPair.path_b` | the two dot-paths |
| `CorrelationPair.rho` | their signed correlation, from the same final Jacobian the `HIGH_CORRELATION` guard read, so the two can never disagree |
| `SoftMode.eigenvalue` | of ĴᵀĴ with every column normalised to unit length, so it is dimensionless: for a single pair with correlation ρ it is 1 − \|ρ\|, and 0 is exact degeneracy |
| `SoftMode.loadings` | dot-path → component of the unit eigenvector, kept above 0.1 and signed so the largest is positive |
| `ExchangeRow.held` | the held parameter's dot-path |
| `ExchangeRow.r2` | the block projection R² of its column onto the span of the free ones, evaluated at the converged values with the candidate freed on a *copy* of the vary set, never refined |
| `ExchangeRow.partners` | dot-path → signed loading of the reconstruction, kept above 0.05: which fitted values absorb the held parameter's signature |

The softest modes are carried whatever their eigenvalues, because the number is
the evidence and deciding where comment starts is the report's job. Read
`ExchangeRow.r2` alone with care: it is a property of the design matrix over the
sampled range and fires on clean fits too, measured at 0.999945 on both a
degenerate fixture and its clean reference. The discriminating half, whether
anything significant is riding the exchange, is in [the report](report.md), whose
`ExchangeFinding` carries the fitted partner's value and esd beside the same R².
That chapter's `FitReport.identifiability` is a different type from this one, and
the warning there says how they differ.

The other half of "how flexible was the background" is not in that table, and the
distinction is worth the sentence. The absorption column says what the background
*could imitate*; `RefinementResult.n_background_peaks` says with how many
explicit [background peaks](data.md) it was allowed to
do it — N peaks are 3N parameters with unconstrained positions, which a reader
comparing two Rwp values has to be able to see. It sits on the result rather than
in the table above because it is **declared, not measured**: the four fields
above are read off the final Jacobian and exist only where a solve measured them,
while this is a count of what the instrument carried, so it is there on a
`replay`ed node too, where `identifiability` is `None`. `0` means none was
declared, exactly off; `None` means nothing counted, which is a joint
multi-histogram fit (one count per histogram) or a result recorded before the
field existed.

## How finely the peaks were sampled

The other half of the question is about the experiment rather than the model.
There should be at least five steps across the top of each peak, and generally
not more than ten {cite}`mccusker1999`. Below five, the integrated intensity of
that reflection was never measured, and no refinement afterwards recovers it.

`PatternDiagnostics.steps_per_fwhm` is that number: the median, over the
pattern's resolved peaks, of how many channels span the peak's half-height
width. `PatternDiagnostics.n_peaks_measured` says how many peaks the median was
taken over. Both come from `diagnose(data)`, which needs no model, so this is a
question to ask of a file **before** refining it, and the answer does not change
afterwards:

<!-- api-doc: no-exec — it needs the reader's own pattern -->
```python
d = rx.diagnose(data)
print(d.steps_per_fwhm, "steps per FWHM over", d.n_peaks_measured, "peaks")
```

A refinement reports the same measurement on its fitted channels, as the
`PATTERN_UNDERSAMPLED` diagnostic, and only when it falls below five. There is
no code for the upper end of the band: oversampling costs beam time, not
validity.

### Everything else `diagnose` measures

The object that call returns is a `PatternDiagnostics`, and the two sampling
fields above are two of its seventeen. The rest describe the pattern itself, with
no model involved, and they are what the background chapter's defaults are chosen
from.

| Field | Is | Reads as |
|---|---|---|
| `PatternDiagnostics.n_points` | channels in the file | |
| `PatternDiagnostics.two_theta_min`, `PatternDiagnostics.two_theta_max` | the range, in degrees | |
| `PatternDiagnostics.noise_sigma_median` | the median channel noise | the scale a peak height is significant against |
| `PatternDiagnostics.peak_fraction` | share of channels more than 3σ above the background envelope | how much of the pattern is peak rather than background |
| `PatternDiagnostics.n_peaks` | resolved peaks found | |
| `PatternDiagnostics.peak_density_per_deg` | those per degree 2θ | above roughly 2/deg the pattern is dense, which favours a stiff baseline and a low background order |
| `PatternDiagnostics.signal_to_background` | near-maximum net signal over the median background level | |
| `PatternDiagnostics.air_scatter_gain` | how much of the envelope's cubic-fit residual variance a 1/(2θ) column explains | a nested-model test for the low-angle air-scatter rise; a high value is what turns the 1/x background term on |
| `PatternDiagnostics.amorphous_hump_score` | RMS of the envelope residual after *both* the cubic and the 1/x term, over the median level | what is left is genuinely broad non-polynomial structure (amorphous content, capillary glass), and calls for a more flexible background |
| `PatternDiagnostics.baseline_lambda` | the arPLS stiffness the whiteness rule picked for this pattern | |
| `PatternDiagnostics.steps_per_fwhm`, `PatternDiagnostics.n_peaks_measured` | the sampling pair above | null when no peak was measurable |
| `PatternDiagnostics.contamination` | Kβ and W Lα ghost candidates, each a `ContaminationFlag` | see the warning below |
| `PatternDiagnostics.coverage_plateau` | the bulk pattern's σ²/max(y, 1), median over the middle half of the range | 1.0 is pure Poisson counting; anything else says the file's σ is something else (merged detectors, a monitor normalisation). Null means σ was not measured, so nothing was checked |
| `PatternDiagnostics.coverage_regions` | stretches whose σ carries more variance per count than that plateau, each a `CoverageRegion` | the pattern's statistical weight is not uniform across its range; see below |
| `PatternDiagnostics.signal_cutoffs` | ends of the range where the level collapsed and stayed down, each a `SignalCutoff` | read this one **first**; see below |

| Field | Is |
|---|---|
| `ContaminationFlag.kind` | which ghost line it is consistent with |
| `ContaminationFlag.two_theta` | the weak peak's position |
| `ContaminationFlag.parent_two_theta` | the strong peak it would be a ghost of |
| `ContaminationFlag.intensity_ratio` | the weak peak's height over the parent's |

:::{warning}
An empty `PatternDiagnostics.contamination` means "nothing was flagged **or**
nothing was checked". The Kβ position is anode-specific, so the screen needs
`wavelength=`, and a wavelength matching no tabulated Kα1 is skipped silently.
Measured on the 11-BM pattern, `diagnose(data)` and
`diagnose(data, wavelength=0.4139090)` both return an empty list: the first
because nothing was asked, the second because a synchrotron wavelength has no
anode. On the round-robin corundum pattern at Cu Kα the same call returns three
flags, two Kβ ghosts and one tungsten Lα.
:::

### The region below the first reflection

`air_scatter_gain` above tests the envelope's *shape* over the whole fitted
range, so a beam/air-scatter tail a few tens of channels wide out of several
hundred barely moves it — measured on a real pattern, 0.019 against the 0.3
trigger, because the tail carried 0.3 % of the whole-range residual the nested
cubic-vs-cubic+1/x fit compares. A fitted result carries a second, narrower
check for exactly that case: `LOW_ANGLE_UNMODELLED` reads the fit's own
residual over `[two_theta_min, first_tick − 2·FWHM)` — every phase, every
emission line, so a peak's own low-angle flank is never counted — and fires
when that region's mean weighted-squared residual exceeds three times the
whole-pattern reduced χ² (`Diagnostic.value`). Silent when the region holds
fewer than ten channels: no reflections at all, or the first one sits at or
near the low edge. The message reports the ratio and does not choose between
its two remedies — raising the pattern's lower limit to where the residual
falls under 2σ, or adding the background's air-scatter term — because only
whoever is looking at the pattern can tell whether the region is genuinely
outside the beam or the background model is locally wrong there.

### How many observations stand behind each channel

`PatternDiagnostics.coverage_regions` is the one measurement here that reads the
σ **column** rather than the intensities. The statistic is the variance
inflation σ²/max(y, 1), which is 1 for pure Poisson counting and proportional to
1/n_eff for a channel averaged over n_eff independent observations; a region is a
run of channels carrying more of it than the bulk of the scan does
(`rietx.background.counting_coverage`).

On an instrument with a bank of detectors on a circle, the number contributing to
a given 2θ falls off at both ends of the range, and this counts them. Measured on
two NIST BT-1 constant-wavelength neutron patterns (3.00–166.25° at 0.05°, σ from
the file), both show the same ladder: about 5× below 8°, 2.2–2.6× out to 15°,
tapering to 1× by 55°, then a step back to 2.2× inside a single channel at
161.30° and held to the end of the scan. The levels are quantised because
detectors are integers, which is why the ends read as steps rather than as a
gradual falloff.

| Field | Is |
|---|---|
| `CoverageRegion.two_theta_min`, `CoverageRegion.two_theta_max` | where the region runs, in degrees |
| `CoverageRegion.inflation` | the median σ²/max(y, 1) over the region, divided by the plateau — how many times the bulk's variance per count it carries. A median over the whole span, so any bridged sub-threshold channels (below) are in it |
| `CoverageRegion.n_channels` | the region's width in channels. Runs closer together than the smoothing window are merged into one, so this is the region's **span** — bridged in-region dips back below the threshold included — not a count of channels each individually over it |
| `CoverageRegion.edge` | `"low"`, `"high"` or `"interior"` — whether it sits at an end of the scanned range or inside it |

:::{warning}
This is descriptive, and it triggers nothing. If the file's σ is right then
weighted least squares already gives those channels the weight they deserve —
that is what σ is for — so a region is **not** an argument for trimming the
range. What it tells you is that the pattern's statistical weight is not uniform
across it, which is a fact about how many detectors saw each angle and not about
the specimen. Where it disagrees with a hand-chosen fit range, that is
information about the range, in either direction and with no recommendation
attached.

Read `CoverageRegion.edge` as a location, not a diagnosis. It says whether the
run reached an end of the range or sat inside it, and no more — the causes it
does *not* separate are several. An end region can be a detector bank's coverage
running out (a quantised falloff), or a synchrotron analyser bank tapering out
smoothly at high angle; an interior one can be a dead or excluded detector, two
scans stitched together, a variable counting-time or slit schedule, or
threshold-crossing chatter a channel or two wide. The table below is where those
readings live.

On the bundled patterns, three with a measured σ fire — none of them the plain
detector falloff the BT-1 provenance shows:

| pattern | fires | how to read it |
|---|---|---|
| `11BM_NAC.fxye` | high 46.0–60.0°, 2.80× | a synchrotron analyser bank tapering out — the ratio rises *smoothly* across the last third, not the quantised step a detector count makes |
| `11BM_LaB6_660a.fxye` | high 53.0–67.0°, 2.82× | the same taper |
| `nist_srm660c_100a.cif` | low 20.3–62.5°, 5.50×; interior 66.7–75.0°, 2.74×; interior 140.5–147.5°, 1.58× | a ladder non-monotonic in both directions, which reads as a variable counting-time or slit schedule rather than a detector count; the two interior regions are threshold-crossing chatter |

It is silent on the one other σ-bearing bundled pattern
(`panalytical_attenuator.xrdml`) and returns `null` on the two with no σ column.
The point is not that any of these is wrong — the σ column *is* structured on all
three — but that `edge` locates the structure and this table names its cause.

One thing it genuinely settles: a σ column that shows this structure was
measured. The Poisson fallback σ = √max(y, 1) makes the ratio identically 1, so
a pattern without a σ column reports `null` and an empty list — *not checkable*,
which is a different answer from an empty list beside a plateau. And v also rises
wherever the counts collapse to nothing with σ staying finite, which is a
different phenomenon wearing the same statistic.
:::

### Where the instrument stopped seeing the sample

`PatternDiagnostics.signal_cutoffs` is the phenomenon that last paragraph names,
measured from the intensities where it belongs, and it is the one field here to
read **before** the others. Each entry is a `SignalCutoff`: an end of the range
where the level collapsed to a small fraction of the interior level and stayed
there. A detector's active area running out, a beamstop, sample-environment
shielding — whatever the cause, those channels carry no diffraction information
and belong outside the fit range rather than inside it.

| Field | Is |
|---|---|
| `SignalCutoff.edge` | `"low"` or `"high"` — which end of the range |
| `SignalCutoff.two_theta` | the boundary: where the collapse *began*, not where it reached its floor, because that is what a fit range should stop at. Still a live channel, so a trim keeps it |
| `SignalCutoff.floor_fraction` | the region's median level over the interior level — how dead it is |
| `SignalCutoff.n_channels` | channels outside the boundary, i.e. exactly what a trim there would drop |
| `SignalCutoff.relative_error_ratio` | the implied precision penalty: the region's median σ/y over the interior's. Null when σ was not measured |

Measured on an ILL D20 constant-wavelength neutron scan of in-situ SrFeO₃
(λ = 2.422 Å, 1540 points over 0.034–153.934°, σ from the file), the two ends are
different shapes and carry different arguments. The trailing end is a cliff: 91 %
of the interior level at 142.83°, 24 % at 144.03°, then flat at 2–3 % for the
remaining 8.7° — a factor of 45 in 2.3°, and past it nothing at all. The leading
end is a graded degradation: a direct-beam shoulder, a shadowed floor near 5 %, a
broad bump peaking around 4.6° at 14 % — at that wavelength d ≈ 30 Å, so it is
not sample diffraction — then a climb that reaches the interior level only around
28°. There *is* structure at the low end; it is a beamstop halo and air scatter
rather than the specimen, and fitting a background through it means describing
non-specimen structure at 3× the interior's fractional error. `signal_cutoffs`
reports the pair at 7.63° and 143.03°; TOPAS's own refinements of that file
declare `start_X 8 finish_X 142`.

:::{warning}
Nothing is trimmed for you and nothing else is re-measured. `diagnose` reports
these and stops, because a fit range is a protocol decision and the numbers above
do not settle it on their own.

That is also why the ordering matters: every other field of a
`PatternDiagnostics` is measured over the whole range it was handed. On that same
file, full range against the 8–142° window, `amorphous_hump_score` reads 0.2549
against 0.1380 — inflated 1.85× by the dead tail — `air_scatter_gain` 0.0027
against 0.1433, so the real low-angle rise is **hidden entirely**, and
`baseline_lambda` moves two decades, 10⁴ against 10⁶. If you decide to trim, call
`diagnose` again on the trimmed pattern; the first answer described the range you
gave it.

`SignalCutoff.relative_error_ratio` is derived, not a second observation. Where
σ²/y is constant — as it is across that whole pattern, at about 20 000 straight
through both transitions — σ/y is 1/√y up to a constant, so the ratio is
1/√`floor_fraction` and says nothing the level did not. It is reported because it
is the number an experimenter reads. That σ²/y stays flat is also what separates
this from `PatternDiagnostics.coverage_regions`: the file's σ there is honest, and
those channels are not thinly covered, they are empty.
:::

## What the restraints did

If the fit carried soft restraints, `RefinementResult.restraints` is a
`RestraintReport`, and on a restrained refinement it is the first thing to read,
before Rwp. [](concepts.md) covers declaring them and scheduling their weight;
this is the object that comes back.

| Field | Is | Reads as |
|---|---|---|
| `RestraintReport.rows` | one `RestraintRow` per restraint | `RestraintRow.computed` against `RestraintRow.target`, with `RestraintRow.deviation` and `RestraintRow.deviation_over_sigma` the two ways of reading the gap, the second measured against the `RestraintRow.sigma` you declared, and `RestraintRow.weight` beside it. `RestraintRow.kind`, `RestraintRow.atoms`, `RestraintRow.path` and `RestraintRow.phase_index` say which restraint it was. |
| `RestraintReport.restraint_chi2` | Σ weight·(deviation/σ)² | the penalty term S_G of {eq}`par-restraint-weight`, at unit weight scale. |
| `RestraintReport.weight_scale` | the c_w the stage ran at | so the penalty the fit actually minimised is `RestraintReport.weight_scale` × `RestraintReport.restraint_chi2`. |
| `RestraintReport.n_restraints` | how many rows there were | the rows are in the covariance but out of Rwp, so this is not part of N. |

The deviations themselves are always reported unscaled, because "is this
restraint satisfied?" is a question about the geometry and c_w is a choice about
how hard to insist on the answer. A row past three σ raises `RESTRAINT_TENSION`:
the restraint and the data are pulling against each other, and one of them is
wrong. A joint fit reports the same object per histogram on
`HistogramResult.restraints`.

## What the statistics cannot tell you

They measure agreement, not correctness. A background flexible enough to imitate
the peaks biases displacement parameters up and phase fractions down *while Rwp
improves*. Of the eight corrections shipped in v0.5, two provably cannot move
Rwp, one moves it the wrong way when it is right, and the two largest accuracy
wins are invisible in it.

That is what [the report](report.md) is for, and why a correction in this
package ships with a record field or a diagnostic saying what it changed, rather
than with an Rwp comparison as its evidence.

## What the absorption correction did

`RefinementResult.absorption` is the worked example of that rule.
Specimen absorption is one seam with three geometries behind it, and one of them
provably cannot move Rwp: the capillary factor is exactly a constant times
exp(c·sin²θ), so applying it is an exact reparameterisation of the phase scale
and the displacement parameters. A comparison of fits would show nothing. The
`AbsorptionCorrection` record is where the correction says what it changed.

It is present only for a Rietveld fit that carried a specimen dimension, and
`None` otherwise, including for a fit that declared none, which is not the same
as a specimen of no thickness. [](data.md) covers declaring it.

| Field | Is | Reads as |
|---|---|---|
| `AbsorptionCorrection.method` | `rouse_cylinder`, `flat_plate_reflection` or `flat_plate_transmission` | which geometry's expression ran |
| `AbsorptionCorrection.mu_r` | the dimensionless µ·(length) | the capillary radius for the cylinder, the specimen thickness for the two plates |
| `AbsorptionCorrection.mu_r_source` | `given` or `estimated` | estimated means composition × packing × that length, so it inherits their uncertainty |
| `AbsorptionCorrection.wavelength` | the λ it was computed at | µ is wavelength-dependent, so the number is not portable between sources |
| `AbsorptionCorrection.equivalent_delta_biso` | the Biso bias, in Å², that refining **without** this correction would have absorbed | positive means add this to recover the unbiased value. For the cylinder this is the entire content of the correction |
| `AbsorptionCorrection.unabsorbed_fraction` | the share of ln A that a free scale and a free Biso cannot reproduce | zero for the cylinder to rounding, a few to tens of per cent for a plate, and hence how far to trust the ΔBiso above |
| `AbsorptionCorrection.identifiable_fraction` | the same measure applied to ∂lnA/∂µt | the number behind the decision not to make the thickness refinable |
| `AbsorptionCorrection.intensity_fraction_of_optimal` | µt·exp(1 − µt), transmission only | the counts this specimen delivered as a fraction of the best it could have. A specimen-preparation number no fit statistic can express: a badly chosen thickness costs counting statistics, not accuracy |
| `AbsorptionCorrection.out_of_range` | whether µR left the expression's validated range | |
| `AbsorptionCorrection.skipped` | why no correction ran, or null | absence with a reason attached |

The flat-plate cases are **not** exactly reparameterisable, which makes their
`AbsorptionCorrection.equivalent_delta_biso` a lower bound rather than the
answer: the projection behind it is unweighted while a refinement finds a
weighted compromise, and measured against synthetic refits the bias a fit really
absorbs runs 1.06 to 1.5× the predicted one, tracking
`AbsorptionCorrection.unabsorbed_fraction`.

## Diagnostics

`RefinementResult.diagnostics` is the channel for "your answer is wrong although
Rwp is fine". Each entry is a `Diagnostic` with a `Diagnostic.code`, a
`Diagnostic.level`, a human-readable `Diagnostic.message`, a
`Diagnostic.suggestion`, `Diagnostic.where` naming the parameter paths
involved, and `Diagnostic.value` carrying the headline number where the
diagnostic has one (a correlation's ρ, an absorption's block R²). `None`
means "no single number", not zero.

The codes are an open vocabulary, deliberately: a new correction ships with the
diagnostic that states what it changed. Read them before the statistics, every
time.

A persistently correlated pair is deduplicated across a plan's stages (the
worst |ρ| kept, every stage it fired in named in the message) and the whole
list is capped at ten `HIGH_CORRELATION` findings, worst first — a
`HIGH_CORRELATION_OMITTED` entry past the cap gives the omitted count and
points at `result.identifiability` for the rest, never a silently truncated
list.

(printing-a-result)=

## Printing a result

`print(result)` — `str(result)` — is the view a bare `RefinementResult` can
answer on its own: per-stage status and the last stage's convergence number
(McCusker et al. 1999 §7's max|Δθ|/esd), every diagnostic, provenance, and
the agreement indices last. It needs no compiled model, so it works on a
result read back from a project or handed across a process boundary, and it
stays under 80 lines on a five-stage fit.

`Refinement.summary()` — after `fit()`, on the session that ran it — prints
more, because a session holds the compiled model: the same per-stage and
diagnostics rows, then the Layer 0/1 misfit summary (the worst regions by χ²
share, the unmatched-peak count, the serial correlation read out as
Durbin-Watson with the esd inflation it costs), the next parameter worth
freeing, the protocol actually run (the plan, every held path grouped by why,
the excluded ranges, N points against N reflections, the σ source), and
finally the agreement indices and a named visual check:

<!-- api-doc: no-exec — continues the earlier session, needs a completed fit -->
```python
print(ref.summary())
```

The `next:` line is a `Refinement.suggest` probe on the channels the fit ran
on, read as **ΔBIC** rather than as the Δχ² that ranks — `next: free
instrument.profile.w, predicted ΔBIC +48.2 (Δχ² 1.2e+03)`, or `next: nothing
ΔBIC admits` when the leading candidate's gain does not pay for its parameter
at this channel count. It costs one Jacobian build and no solve; [](report.md)
has the field and the two questions it separates.

`deliverable=` adds the rows one purpose actually decides on — `"phase_id"`
(unmatched observed peaks, the Le Bail gap ratio), `"qpa"`
(`background.absorption`'s worst entry, the weight fractions with esds),
`"structure"` (`identifiability.exchangeability`) — because the report will
not infer your purpose for you ([](qpa.md), and "Structure agreement
indices" above, say what each row means):

<!-- api-doc: no-exec — continues the earlier session, needs a completed fit -->
```python
print(ref.summary(deliverable="qpa"))
```

`plot=` writes `plot_for_vlm` to that path and names it on the last line —
the same regions the text names, with their numbers in the panel titles, so
the picture confirms the text rather than standing in for it:

<!-- api-doc: no-exec — continues the earlier session, needs a completed fit -->
```python
print(ref.summary(plot="fit.png"))
```

`report=` takes the `FitReport` that `ref.report()` already built, so a
caller that wants the text and the structured report builds one report, not
two — the report is the expensive half of the call, and in a batch the
doubling is the dominant cost. Pass the report or `plan=`, never both: a
report was built under its own plan.

<!-- api-doc: no-exec — continues the earlier session, needs a completed fit -->
```python
report = ref.report()
print(ref.summary(deliverable="qpa", report=report))
```

A series prints its own view: `SeriesResult.summary()` — `str(series_result)`
— is the trajectory table (first and last few entries, with the count
between them), the `SEQUENTIAL_*` series-level diagnostics, and each shown
entry's status and Rwp. See [](series.md) for what the series-level
diagnostics mean.

The fourth deliverable is the series' own, because no single pattern carries a
`SEQUENTIAL_*` row: `series.summary(deliverable="series")` adds the rows that
decide a parameter measured against the series axis — whether the ordering was
checked at all (`direction="both"`, or a plain statement that it was not), the
persistent findings, each step with what an independent cold pair reproduced,
the phases held for want of support, and the two things no diagnostic can
supply, a stated 2θ-scale anchor and the precision/accuracy split. The other
three purposes are refused there by name, and `Refinement.summary
(deliverable="series")` answers with where they live:

<!-- api-doc: no-exec — needs a completed series -->
```python
print(series.summary(deliverable="series"))
```

(progress-lines)=

## Progress

A staged fit or a long series can take longer than a caller wants to wait on
silently. `progress=` — a text stream or a path, on `fit()` and on
`refine_sequential()`/`SequentialRefinement.fit()` — writes one line per
stage boundary (one per pattern under a series, each stamped with its place
in it):

<!-- api-doc: no-exec — illustrates the stream it writes, not a runnable step -->
```python
result = ref.fit(data, progress=sys.stdout)
# stage scale_bkg converged Rwp 0.0933 2s
# stage zero converged Rwp 0.0894 1s
# ...
```

<!-- api-doc: no-exec — illustrates the stream it writes, not a runnable step -->
```python
series = rx.refine_sequential(patterns, structure, instrument,
                              labels=["250C", "300C"], progress="run.log")
# [series 1/2] 250C stage scale_bkg converged Rwp 0.0812 3s
# [series 2/2] 300C stage warm_refit converged Rwp 0.0805 1s
```

It is implemented as an `events=` consumer, never a second telemetry
channel — every number on the line is read straight off the same event
`rietx watch` tails, so the two never disagree about what happened. Pass
both freely: `progress=` adds a subscriber, it does not replace a callback or
path already given as `events=`.
