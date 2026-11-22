(guide-peak-equation)=
# How to write a peak's width or position as an equation

Declare each term as a `rietx.PeakEquation` on `Phase.peak_equations` or `Instrument.peak_equations`, and free its coefficients in a stage by path.

A peak equation adds a term to each reflection's Lorentzian or Gaussian width or to its position, or multiplies its intensity.
It reads the reflection's indices, multiplicity, d-spacing and angle, so it can carry a width on a family of reflections or a 2θ calibration curve {cite}`stinton2007`.
Its coefficients are ordinary parameters, with bounds, holds, ties and esds.

## Declare the equations and fit

This fits a synthetic brucite pattern made with three equations.
The Lorentzian width is a tan θ term whose coefficient differs between the hk0 reflections and the rest.
The reflections with l ≠ 0 carry an intensity factor p.
The instrument's 2θ scale bends along a calibration curve about 60°, which moves every phase's peaks:

```{literalinclude} ../../../examples/guides/peak_equation.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/peak_equation.py -->
```text
phases.0.peak_equations.0.w0      0.1529 +/- 0.0055
phases.0.peak_equations.0.w1      0.0593 +/- 0.0011
phases.0.peak_equations.1.p       0.7039 +/- 0.0129
instrument.peak_equations.0.sq    2.4389 +/- 0.0394
instrument.peak_equations.0.ln   -1.4911 +/- 0.0150
GoF 1.02
```

The pattern was made with w0 = 0.15, w1 = 0.06, p = 0.7, sq = 2.4 and ln = −1.5.
Each refined value lies within 1.0 esd of its truth.
The fit started with all five coefficients wrong.

A coefficient is a parameter under its equation's path, such as `phases.0.peak_equations.0.w` for a coefficient `w`, or `instrument.peak_equations.0.sq`.
The second index counts the equations in their list, and the last part is the coefficient's name.
No preset plan frees one, so a stage names the path, as `phases.*.peak_equations.*` does here.
The calibration curve writes its coefficients scaled by 10⁻⁵ and 10⁻³, so each refines near 1.
A coefficient of 2.4 × 10⁻⁵ in its own units works too, but its esd is then a small number on a large scale.

## Choose the target

| Target | Unit | What the value does |
|---|---|---|
| `lor_fwhm` | degrees 2θ | adds to the Lorentzian FWHM, as `lor_size` and `lor_strain` do |
| `gauss_fwhm` | degrees 2θ | adds to the Gaussian FWHM in quadrature |
| `gauss_fwhm_squared` | deg² | adds to Γ<sub>G</sub>² beside U, V and W, and may be negative |
| `shift` | degrees 2θ | adds to the peak position |
| `intensity_factor` | 1 | multiplies the reflection's intensity |

The expression reads `h`, `k`, `l`, `m` (the multiplicity), `d` in Å, `theta` (the Bragg angle in radians), `two_theta` in degrees and `wavelength` in Å.
`wavelength` is the emission line the peak is drawn at, so a Kα2 image reads its own λ.
`tan(theta)` is therefore the strain law, and `1/cos(theta)` the size law.
An equation on the instrument takes `shift` alone and reads only `theta` and `two_theta`.
[Peak equations](../reference/data.md#peak-equations) lists the refusals, and [Switching from TOPAS](../switching/topas.md#peak-equations) maps TOPAS's keywords onto these targets.

A condition inside `if` reads `h`, `k`, `l` and `m` only.
They cannot change during a solve, so no reflection switches branch mid-fit.

## Write an equation every image of a reflection agrees on

rietx keeps one reflection for each set of symmetry-equivalent ones, and a powder peak holds all of them.
So an equation must give every image the same value.
In a cubic group (2, 0, 0) and (0, 0, 2) are one peak, and `l == 0` is true for one and false for the other.
The fit refuses such an equation before it starts:

```{literalinclude} ../../../examples/guides/peak_equation.py
:language: python
:start-after: "# guide: orbit start"
:end-before: "# guide: orbit end"
```

<!-- output of examples/guides/peak_equation.py -->
```text
phases.0.peak_equations.0 (lor_fwhm): 'if(l == 0, w0, w1)*tan(theta)' is not single-valued over the orbit of reflection (2, 0, 0): it gives 0.0141977 there and 0.0085186 on its symmetry image (0, 0, -2). A powder peak holds every image, so the equation must give them one value. Write it symmetrically, or average it with orbit_mean(...)
```

There are three ways out.
Write the family symmetrically: in a cubic group `h*k*l == 0` picks the reflections with a zero index, whichever index it is.
Average over the images with `orbit_mean(...)`, which gives each peak the mean of its images' values.
Or use `harmonic(l, n)`, a symmetrised spherical harmonic of the reflection's direction, which the Laue class keeps the same on every image.
The check runs at the stored coefficients and at random trial ones, so `if(l == 0, a, b)` is refused even while a and b are equal.

## Share a coefficient across patterns

In a joint fit a phase's coefficient is shared by default, and an instrument's is per pattern.
To make a coefficient follow a pattern's coordinate, declare a `ParametricEquation` whose target is the coefficient's path, such as `phases.0.peak_equations.0.w`.
[How to refine a cell edge as a function of temperature](equation.md) shows the declaration.

A shared coefficient is one number in degrees for every pattern.
Across patterns at different wavelengths, the right value in degrees can differ.
A size-like term, such as `x/cos(theta)`, scales with λ.
A strain-like term, such as `w*tan(theta)`, does not.
There are two ways to write a wavelength-dependent term.
Give each pattern its own coefficient with `SharingMap(per_histogram=["phases.0.peak_equations.0.w"])`.
Or write the λ into the expression, as `y*wavelength/cos(theta)`, and keep `y` shared.
`y` is then in degrees per Å, one number for one crystallite size at every wavelength.
TOPAS does the same two ways: a term per pattern, or `Lam` in the expression.
The fit still warns about a shared coefficient in an equation that reads `wavelength`, since such an equation can carry a term that does not scale with λ.

## Read what the fit says

Three diagnostics are specific to peak equations.
`PEAK_WIDTH_NOT_POSITIVE` fires where a width equation takes Γ<sub>G</sub>² or Γ<sub>L</sub> below zero at a fitted reflection.
A negative term is legal, but the total width is not.
`PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS` fires in a joint fit where a width or shift coefficient is shared across patterns of different wavelengths.
`QPA_INTENSITY_FACTOR` fires on a mixture whose phase carries an intensity factor.
The fraction is computed from the phase's scale, which absorbs the factor.
A factor that averages 0.83 makes the fraction about 1/0.83 = 1.2× too high relative to the other phases.
