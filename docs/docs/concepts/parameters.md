# About parameters

rietx groups its parameters the way a crystallographer does: cell and structure, phase amount, microstructure, instrument and background.
The [parameter map](../reference/parameters.md) lists every parameter in each group with its unit, default and typical range.
This page says what each group is for, what it belongs to, and how the background differs from the rest.

## The groups

Each group belongs to one thing: an atom, a phase, the specimen, the instrument or this one measurement.
That scope decides what carries over to the next pattern.
A calibrated instrument carries over to every sample measured on it, and a background does not.

| Group | Belongs to | What it changes | How it varies with angle |
|---|---|---|---|
| [Cell](../reference/parameters.md#cell) | phase | where each reflection falls | through d, as tan θ |
| [Atoms](../reference/parameters.md#atoms) | atom | the relative intensities | per hkl, with no smooth angular form |
| [Phase amount and intensity corrections](../reference/parameters.md#phase-amount-and-intensity-corrections) | phase or specimen | how strong the phase is, and smooth or hkl-selective rescaling | smooth in Q, or per hkl for texture |
| [Microstructure](../reference/parameters.md#microstructure) | phase | the width the specimen adds | size as 1/cos θ, strain as tan θ |
| [Instrument peak positions](../reference/parameters.md#peak-positions) | instrument and specimen position | where every peak sits | constant, cos θ, sin 2θ or cos 2θ |
| [Instrument peak shape](../reference/parameters.md#peak-shape) | instrument | the instrument's own width and asymmetry | Gaussian FWHM² as U tan²θ + V tan θ + W |
| [Background](../reference/parameters.md#background) | this measurement | the intensity under the peaks | smooth in 2θ, plus any declared humps |
| [Named variables](../reference/parameters.md#named-variables) | the refinement | whatever is tied to them | none of their own |

Symmetry decides how many parameters a group has.
The space group ties the lattice parameters, and an atom refines only along the directions its site symmetry allows.
The [parameterisation chapter](../theory/parameterisation.md#site-symmetry-degrees-of-freedom) derives those directions.

The angular column decides which groups can be told apart.
Two parameters whose effects have the same shape over the measured range cannot be separated by the data.
[About correlations and esds](correlations.md) covers what rietx reports when that happens.

## Which parameters refine

`Refinement.parameters()` lists every parameter with its value, its bounds and whether a stage can free it.
`ParameterRow.held_because` says why one cannot.
These are the usual reasons:

- it is locked, like an angle the space group fixes or a coordinate on a fixed special position;
- it is tied, and follows another parameter;
- the mode fixes it, as a Le Bail or Pawley fit fixes the atoms;
- you hold it with `Refinement.hold`.

An atom placed by a rigid body is held too, and so is a wavelength while the cell is free, since d = λ/(2 sin θ) fixes only their ratio.

A named variable is a parameter you declare with `Refinement.add_variable`, outside the structure and instrument.
Model parameters follow it through ties, so three oxygens can share one displacement parameter that belongs to none of them.
TOPAS users know this as a named parameter.

## Instrument and specimen

The instrument's peak shape and the specimen's broadening add.
Gaussian variances add, so the phase's Gaussian size and strain terms add to Caglioti U, V and W.
Lorentzian widths add, so its Lorentzian terms add to X and Y.
The [profiles chapter](../theory/profiles.md#the-instrument--sample-width-split) gives the sum.

The split only means something when the instrument is known.
Calibrate it on a standard with a certified cell, and hold that cell while you do, so the cell cannot absorb the zero shift and the specimen displacement.
Then load the calibrated instrument for each sample, with its parameters fixed, and refine only the sample's broadening.
The `lab_calibrate` and `lab_sample_refine` [plan presets](../reference/plans.md) do the two halves.

Which position corrections exist depends on the geometry.
A flat plate has a specimen displacement, which goes as cos θ, and a transparency, which goes as sin 2θ.
A capillary off the centre of the diffractometer has two offsets instead, which go as sin 2θ and cos 2θ.
A correction the geometry does not have is fixed, and a stage cannot free it.
The [peak positions chapter](../theory/peak-positions.md#aberration-shifts) gives each law.

## Background

The background is part of the model.
rietx refines it with the structure and never subtracts an estimate from the counts first.
Three curves are available:

- `BackgroundChebyshev`, a Chebyshev polynomial;
- `BackgroundFixedPlusChebyshev`, an estimated baseline held fixed, with a Chebyshev polynomial refined on top;
- `BackgroundPSpline`, a spline whose coefficients refine under a smoothness penalty.

`rx.auto_background` chooses the polynomial order or the spline's knot spacing from the pattern.
The [background chapter](../theory/background.md#additive-background-models) gives each model and the penalty.

### How flexible a background should be

A background flexible enough to follow the peaks takes intensity from them.
The displacement parameters then refine too high, and the phase scales too low, while Rwp improves.
`FitReport.background.worst_absorption` measures this.
It is the fraction of a structural parameter's effect on the pattern that the background terms, taken together, can reproduce.
A comparison of one background term at a time misses it.

A background too stiff to follow the real one leaves a smooth residual between the peaks.
`FitReport.background` reports that side too, as the χ² and the serial correlation of the residual away from the peaks.
The [bias section](../theory/background.md#background-flexibility-and-bias) covers both.

### Humps

A hump is a broad Gaussian added to the background curve, for scattering that is not from a crystalline phase.
Amorphous content, a capillary, a can or a sample holder each give one.
Declare it in `Instrument.extra_components` as a `HumpComponent` with a position, a height and a width.
rietx never adds one by itself.

A hump is named apart from the background curve, as `instrument.extra_components.*`, so a stage that frees the background does not free the hump.
`mccusker_structural` frees declared humps in a stage of their own, after the peak positions are in place.

Declare a hump for a scatterer you can name, and check it against a measurement of that scatterer alone.
On a synchrotron pattern of silicon in a Kapton capillary, an empty capillary from the same beamtime shows a broad feature at 4.24° with a width of 6.2°.
One hump on a 3-term Chebyshev background describes it.
With the hump, the silicon displacement parameter stays within one esd of its value without it, and its esd falls sixfold.

:::{dropdown} The silicon and Kapton comparison
The pattern is APS 11-BM run 4918, NIST SRM 640c silicon in a Kapton capillary, 47 999 points over 2-50° 2θ.
The cell is held at the certificate value.

| Background | Free background terms | Rwp | B<sub>iso</sub>(Si) / Å² |
|---|---|---|---|
| Chebyshev, 3 terms | 3 | 0.120051 | 0.413(64) |
| Chebyshev, 3 terms, and one hump | 3 + 3 | 0.082134 | 0.421(10) |
| Chebyshev, 6 terms | 6 | 0.088232 | 0.422(25) |
| Chebyshev, 6 terms, and one hump | 6 + 3 | 0.076711 | 0.4234(64) |

Three hump parameters lower Rwp more than three extra Chebyshev terms do.
That shows only that the hump describes the curve more economically, and the empty capillary is the evidence for what it is.
The refined hump sits at 4.16°, below the capillary's 4.24°, because it also takes up the rise below 3° that a 3-term polynomial cannot follow.
Do not read a hump's position as a d-spacing.
:::

A hump must be broad.
One that refines narrower than {{ HUMP_MIN_WIDTH_MULT }} times the instrumental width at its position raises `HUMP_TOO_NARROW`.
At that width it is a peak with no cell behind it, and its parameters are not quotable.
An unindexed line needs a second phase, and the report's list of unmatched peaks shows where one is.
The [humps section](../theory/background.md#explicit-humps) gives the hump's form and the width condition.

:::{admonition} In other programs
:class: note

GSAS-II calls a hump a background peak, and TOPAS fits one as a peaks phase with no cell.
GSAS-II states the Gaussian width terms as a variance in centidegrees², and X and Y in centidegrees.
rietx states the Gaussian FWHM² in degrees² and X and Y in degrees.
[Names in other programs](../reference/foreign-names.md) maps every rietx parameter to its name in GSAS-II, GSAS, TOPAS and FullProf.
:::
