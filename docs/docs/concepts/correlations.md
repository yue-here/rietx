# About correlations and esds

An esd in rietx describes how well the data fix a parameter, and a parameter the data do not move gets no esd at all.
rietx leaves that esd empty because the arithmetic would otherwise print a small one.

## Where an esd comes from

The esds come from the covariance matrix at the converged point, χ²<sub>red</sub> (JᵀJ)⁻¹, where J is the Jacobian of the weighted residuals.
They are taken from the last stage of the plan, where every freed parameter refines together.
Each esd is multiplied by the Bérar-Lelann factor, which accounts for neighbouring residuals that are correlated with each other and so carry less independent information.
GSAS-II, FullProf and TOPAS do not apply it to their esds.
`RefinedParameter.stderr_uncorrected` is each esd without the factor, so compare another program's esd with it.
The correlation matrix is not inflated, so a degenerate pair reads |ρ| ≈ 1.
The [esd section of the theory](../theory/estimation.md#esds-and-the-bérar-lelann-inflation) gives both formulas.

An esd describes the minimum the fit stopped in.
A trace phase whose scale trades against its peak width can have several minima at one χ², each with a tight esd.
`Refinement.profile_fraction` pins that phase's width at a series of values and reports every weight fraction the pattern admits.
For any one parameter, `Refinement.profile_interval` refits with one parameter pinned at a series of values, and reports the range over which χ² rises by less than the cut for the chosen confidence level.

## Why parameters correlate

Two parameters correlate when they change the calculated pattern in the same way.
Over a wide angular range most effects have different shapes, and over a short one they do not.
Between 20° and 40° 2θ, the constant, cos θ, tan θ and 1/cos θ curves are each a straight line to within 0.8 %.

| Correlated parameters | Shapes in 2θ | What goes wrong |
|---|---|---|
| zero shift, specimen displacement, cell | constant, cos θ, tan θ | Over a narrow range the three shapes are close to a constant and a slope, so the data fix two combinations of three parameters. A cell refined beside a free zero shift and specimen displacement on 20° of data is not measured. |
| zero shift and the two capillary offsets | constant, sin 2θ, cos 2θ | The same problem in a capillary's shapes. Separable over 5-160°, not over 5-25°. |
| crystallite size and microstrain | 1/cos θ and tan θ | The Williamson-Hall separation needs a wide range. |
| scale, displacement parameters, background, specimen absorption, surface roughness, extinction | all smooth in angle | Each raises or lowers intensity as a smooth function of angle, so each can take up part of another's effect. Specimen absorption is calculated from the specimen and never refined for this reason. |
| preferred orientation and occupancy | both rescale particular hkl | An occupancy refined against uncorrected texture measures the texture. |
| overlapped intensities in Le Bail and Pawley fits | identical | The data fix the sum, not the split. |

## What rietx reports

rietx reports a correlation at three strengths:

- `HIGH_CORRELATION`, for a pair above |ρ| = 0.98.
  The data fix the combination better than either parameter, and the two esds are not independent measurements.
- `FLAT_DIRECTION`, for a pair at |ρ| = 1.000 to three decimals.
  The data measure only one combination, and each esd holds only if the other parameter is right.
- `COVARIANCE_DIRECTION_DISCARDED`, for a combination of several parameters the data do not constrain.
  Every esd in the group is too small, by at least a factor of √2.

`FitReport.identifiability` lists the strongest correlations and the combinations the data fix least well.

## Why a direction the data do not move has no esd

The inverse of JᵀJ does not exist when the data cannot see some combination of parameters.
A pseudo-inverse is taken instead, which discards every direction weaker than {{ PINV_RCOND }} of the strongest.
A discarded direction comes back with zero variance, so the parameters along it look exactly known.
On a 25-50° Cu Kα scan of a four-phase mixture, bcc iron had one reflection in range.
Its displacement parameter walked to −150 Å², and its weight fraction was reported as 0.000 ± 0.000 wt%.

rietx prevents this in three ways:

- It scales every column of J to the same length before inverting.
  A parameter's esd then does not depend on the units of another.
- A parameter with no effect on the pattern at all is dropped from the inversion, and its esd is empty (`None`).
  Everything that depends on it has no esd either: a parameter tied to it, a bond length whose atoms it moves, and every weight fraction of the mixture.
- A phase whose reflections in range cannot separate its scale from its displacement parameters has those parameters fixed for the stage, and `SCALE_B_INSEPARABLE` reports it.

A combination the data move a little, but below that cutoff, is still discarded.
Its parameters keep esds, and those esds are too small, so `COVARIANCE_DIRECTION_DISCARDED` marks them.

The [scale-and-B section](../theory/estimation.md#a-scale-and-a-b-the-range-cannot-separate) derives the test.

## Derived quantities

A bond length, a bond angle or a weight fraction is a function of several refined parameters.
rietx propagates its esd through the whole covariance matrix, as the IUCr guidelines ask (McCusker et al. 1999).
Across 88 distances in a synchrotron structure refinement, the esd from the diagonal alone ranged from 0.86 to 1.41 times the full one.
So the diagonal-only esd is not a safe upper bound, and rietx reports both.

A derived esd is empty when linear propagation cannot give one.
That happens with no covariance (a replayed node), with no free parameter behind the quantity, at an angle the symmetry fixes, and at an angle within {{ ANGLE_LINEARISATION_LIMIT_DEG }}° of 0° or 180°.
The [derived-quantities section](../theory/estimation.md#esds-of-derived-quantities) lists the four cases.

## Parameters on a bound

A parameter that finishes on its `min` or `max` stays in the covariance, and `RefinedParameter.at_bound` is true.
Its esd is not an interval, since the value cannot go past the bound.
`Refinement.profile_interval` gives a one-sided interval with the bound as one end.
The [bound section](../theory/estimation.md#an-interval-for-a-parameter-on-its-bound) gives the quantile it uses.

## What to do about a correlation

A correlation can be handled in five ways:

- Hold one parameter at a value known from elsewhere, with `Refinement.hold`.
  Calibrating the instrument on a standard with a certified cell is this case.
- Free the two in different stages, so the fit approaches the answer one parameter at a time.
  The last stage still refines both, so its esds still show the correlation.
- Measure a wider angular range, where the shapes separate.
- Tie the two with `Refinement.tie_equal` or `Refinement.tie` where the chemistry says they are one quantity, such as the displacement parameters of three oxygens in one environment.
- Restrain a quantity you know, such as a bond length, with a target and an uncertainty.

[About parameters](parameters.md) says which groups each parameter belongs to.
