# Theory

Theory states each equation rietx computes, the paper it comes from, and the code symbol that runs it.

Every displayed equation carries a source line naming that symbol, and the build fails when the name stops importing.

- [The forward model](forward-model.md) turns a structure, an instrument and a source into a calculated pattern.
- [Peak positions](peak-positions.md) places each reflection on the 2θ axis.
- [Peak profiles](profiles.md) gives the shape and width of one peak.
- [Intensities](intensities.md) gives the area under each peak.
- [Intensity corrections](corrections.md) gives each factor that multiplies a reflection's intensity.
- [Microstructure](microstructure.md) reads the width coefficients as a size and a strain.
- [Background](background.md) gives the background models and the bias a flexible one causes.
- [Estimation](estimation.md) states what the fit minimises and how each esd is computed.
- [Parameterisation and constraints](parameterisation.md) builds the parameter vector and ties its entries.
- [Representation analysis](representation-analysis.md) derives the magnetic structures a propagation vector allows.
- [Superspace groups](superspace.md) describes a crystal modulated along one direction.
- [Indexing](indexing.md) says what a list of line positions can tell about a lattice.
- [Search engines](engines.md) finds a cell from that list.
- [Reading a paper against its own numbers](method.md) shows how three misprinted equations were caught.
- [References](references.md) lists the works these pages cite.

<!-- The old manual's root page includes the text between these two markers, so it is written once (WP-1986). -->
<!-- theory-conventions-start -->

## Conventions

Theory states every convention by its physics rather than by its letter, because
Rietveld codes disagree on the letters. They swap the size and strain terms X
and Y (GSAS and FullProf), sign March-Dollase $r$ differently, normalise
Stephens $S_{HKL}$ in three independent ways, and print either a transmission
$A$ or its reciprocal $A^*$. Wherever a number could be transferred from the
literature or from another code, the convention warning sits beside the
equation. Match the θ-law, the limit and the sign of the effect, not the symbol.

## Scope

Constant-wavelength X-ray and neutron powder data. Fundamental-parameters
profiles and time-of-flight data are not implemented today. They are planned
for v2, behind seams the forward model already carries.
The one exception is {ref}`sec-tof-positions`: the calibration relation a
time-of-flight bank is read with, which puts a flight time on a d-spacing. No
time-of-flight pattern is refined. Spherical-harmonics texture,
{eq}`corr-sh`, assumes cylindrical sample symmetry: one histogram cannot see a
pole figure.

(sec-units)=
## Symbols and units

A quantity in Theory is in the unit rietx stores it in, and that is one of these
unless the equation says otherwise. Anything else is written in brackets at the
right of the equation that introduces it (`[rad]` on a derivation done in
radians, `[barn]`, `[fm]`), or stated in the sentence beside it.

| quantity | unit |
|---|---|
| every angle | degrees; `2θ` is the scattering angle and `θ` half of it |
| a position on the pattern axis | deg 2θ |
| a peak width | deg 2θ, as FWHM (never a standard deviation, never an integral breadth) |
| a Gaussian width *coefficient* | deg² 2θ, because it is a variance |
| a length | Å: cell edges, d-spacings, wavelengths, crystallite sizes |
| a reciprocal length | Å⁻¹: $s = \sin\theta/\lambda = 1/(2d)$, the reciprocal lattice vector length $1/d = 2s$, and the scattering-chapter $Q = 4\pi\sin\theta/\lambda$ |
| a reciprocal length squared | Å⁻²: the indexing-chapter $Q = 1/d^2$, which is the `ObservedPeak.q` field. $Q$ is the one symbol these pages use for two quantities, so read it from the chapter and never across chapters |
| a displacement parameter | Å², with $B_{\mathrm{iso}} = 8\pi^2 U_{\mathrm{iso}}$ |
| an observed or calculated intensity | counts |
| a reflection intensity | counts·deg 2θ, an area, because every profile here is normalised to unit area |
| a linear attenuation coefficient | cm⁻¹ |
| a distance in the diffractometer | mm: goniometer radius, specimen displacement, capillary offsets |
| a magnetic moment | $\mu_B$ |

Ratios of two of these are dimensionless and are not marked: a transmission
coefficient, a mixing fraction, a weight fraction, a scale, an occupancy, a
Miller index, a multiplicity.

<!-- theory-conventions-end -->

Theory names quantities by their physics. The unit, default and typical range
of a named parameter (what `phases.0.cell.a` or `instrument.profile.w` holds) is
in [the parameter reference](../reference/parameters.md), which is generated
from the package itself.

```{toctree}
:hidden:
:numbered:

forward-model
peak-positions
profiles
intensities
corrections
microstructure
background
estimation
parameterisation
representation-analysis
superspace
indexing
engines
method
```

```{toctree}
:hidden:

references
```
