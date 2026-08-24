# Patterns, structures and instruments

Three objects describe a refinement: the measured pattern, the crystal
structure, and the instrument that recorded it. [](files.md) says where each one
comes from on disk. This chapter says what is inside them, so you can build one
by hand, check what a reader handed you, or change one field without guessing
what else moves.

Every number a fit can refine is a `Parameter`, and every `Parameter` has a
dot-path. [](model.md) is the table those paths address and how to read and edit
a row of it; [](concepts.md) groups the paths by what they do to the pattern and
explains which groups fight each other. This chapter is the objects those paths
are built from.

The schemas reject what they cannot interpret. Every one of them forbids unknown
fields, so a misspelled keyword is an error at construction rather than a
setting that silently did nothing, and bounds are checked when the object is
built rather than when the fit starts.

## Every refinable number is a `Parameter`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Parameter.value` | float | required | the current value, in `Parameter.unit` |
| `Parameter.vary` | bool | `False` | whether the least-squares problem is free in it |
| `Parameter.min` | float | `-inf` | inclusive lower bound |
| `Parameter.max` | float | `inf` | inclusive upper bound |
| `Parameter.unit` | str or None | `None` | a label, not a conversion: nothing rescales by it |
| `Parameter.stderr` | float or None | `None` | the esd, written by the fit |
| `Parameter.transform` | `"identity"`, `"softplus"`, `"exp"`, `"logit"` | `"identity"` | internal reparameterisation, {eq}`par-softplus` |
| `Parameter.expr` | None | `None` | reserved, not implemented, and must stay `None` |

`value` must lie within the bounds and `min` must not exceed `max`, both checked
on construction. Infinite bounds survive a JSON round-trip as `"Infinity"`,
which is why an unbounded parameter is a legal thing to save.

```python
from rietx import Parameter

a = Parameter(value=4.15689, min=4.0, max=4.3, vary=True, unit="A")
width = Parameter.positive(1e-3, vary=True, unit="deg^2")
assert width.transform == "softplus" and width.min == 0.0
```

`Parameter.positive` is the constructor for a quantity with no physical meaning
below zero: a peak width, a scale, an absorption coefficient. It sets
`min=0.0` and the softplus transform, which keeps the optimiser away from the
hard bound instead of letting it stall against it.

:::{warning}
Softplus does not promise a strictly positive value. The internal variable maps
to `log(1 + exp(u))`, which underflows to exactly `0.0` for `u` below about
−745, so a `min=0.0` softplus parameter can reach zero. That is harmless
wherever zero is the off state, which is nearly everywhere in this package: a
zero width is no broadening, a zero extinction coefficient is no extinction. It
is a bug wherever the physics divides by the value, and such a parameter carries
a real floor instead. `PreferredOrientation.r` is the one that does.
:::

`stderr` is the one field a fit writes back. It is `None` on a parameter that
was never free, and also on a free one whose esd could not be estimated;
[](results.md) explains what an absent esd means and how the fitted values are read
back.

## The pattern

`PatternData` is the measurement: two arrays of the same length, and what is
known about their uncertainty.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `PatternData.two_theta` | list[float] | required | 2θ in degrees, strictly increasing |
| `PatternData.intensity` | list[float] | required | measured intensity, same length |
| `PatternData.sigma` | list[float] or None | `None` | per-point esd from the file; `None` selects the Poisson fallback |
| `PatternData.excluded_regions` | list[tuple[float, float]] | `[]` | 2θ intervals to leave out of the fit |
| `PatternData.metadata` | dict[str, str] | `{}` | what the reader found in the file header |

Strictly increasing is enforced, not sorted for you. A file stored high to low
is reversed by the reader, which reports that it did; a file whose 2θ column is
not monotone at all is a refusal, because sorting it, concatenating it and
splitting it are three different measurements. [](files.md) has that rule and
the four other places a reader may repair a file.

Five methods read the pattern out. `PatternData.tt` and `PatternData.y` are
float64 numpy views of the two columns. `PatternData.sig` is the one that
matters:

```python
from rietx import PatternData

data = PatternData(two_theta=[10.0, 10.02, 10.04], intensity=[120.0, 480.0, 0.0])
assert list(data.sig().round(4)) == [10.9545, 21.9089, 1.0]
```

**σ is a lookup, never a re-derivation.** `sig()` returns the file's `sigma`
where the file had one and √max(y, 1) where it did not, and every weighted
quantity in the package divides by the result: the objective
{eq}`est-obj`, every renderer's difference curve, both GUI windows. The Poisson
fallback is correct for raw counts and wrong by √t for anything already divided
by a counting time, which is why a reader that cannot establish the intensity
scale withholds σ rather than inventing it. Reported esds of zero are floored,
since a zero esd is an infinite weight on one channel.

`PatternData.in_range_mask` is the boolean mask that `excluded_regions` implies,
and `PatternData.crop` returns a new pattern over a 2θ interval. Cropping and
excluding are different acts: a cropped pattern has fewer points, an excluded
region leaves the points in place and out of the residual. Prefer excluding, so
the count that a statistic quotes still describes the file. A project records
its excluded regions in its own document rather than in the pattern, for a
reason [](files.md) gives.

Never subtract an estimated background from `intensity`. Hold it additively
with `BackgroundFixedPlusChebyshev` or co-refine it under the smoothness penalty
of `BackgroundPSpline`. Subtracting changes the counting statistics that
`sigma` describes while leaving `sigma` alone.

## The structure

`Structure` is a list of phases and nothing else. `Structure.phases` carries at
least one; `Structure.from_cif` reads one out of a CIF and `Structure.to_cif`
writes it back.

`Phase` is one crystalline phase. Its first four fields describe the crystal
and the rest describe what this specimen did to the peaks.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Phase.name` | str | required | a label, and the key an export writes |
| `Phase.space_group` | str | required | Hermann-Mauguin symbol or a number as a string, resolved by gemmi |
| `Phase.cell` | `Cell` | required | lengths and angles |
| `Phase.atoms` | list[`Atom`] | required | the asymmetric unit, at least one |
| `Phase.scale` | `Parameter` | 1.0, fixed, softplus | this phase's contribution to the total intensity |
| `Phase.lor_size` | `Parameter` | 0.0 deg, softplus | Lorentzian size broadening, 1/cos θ |
| `Phase.lor_strain` | `Parameter` | 0.0 deg, softplus | Lorentzian strain broadening, tan θ |
| `Phase.gauss_size` | `Parameter` | 0.0 deg², softplus | Gaussian size broadening, 1/cos²θ |
| `Phase.gauss_strain` | `Parameter` | 0.0 deg², softplus | Gaussian strain broadening, tan²θ |
| `Phase.extinction` | `Parameter` | 0.0, fixed, softplus | secondary extinction, {eq}`corr-sabine`; 0 is E ≡ 1 exactly |
| `Phase.preferred_orientation` | `PreferredOrientation` or None | `None` | single-axis March-Dollase, {eq}`corr-md` |
| `Phase.microstrain` | `StephensStrain` or None | `None` | anisotropic strain, width per hkl, {eq}`ms-sigma` |
| `Phase.particle_radius_um` | float or None | `None` | Brindley microabsorption input, {eq}`corr-brindley`; a plain float, never refined |
| `Phase.restraints` | list | `[]` | soft observational restraints, {eq}`par-restraint` |

The four broadening terms are the sample half of the instrument ⊕ sample split.
Gaussian *variances* add under convolution and Lorentzian *widths* add, which is
why the two pairs carry different units: deg² for the Gaussian pair and deg for
the Lorentzian one. Each term stacks on the instrument term with the same
θ-dependence, so one pattern cannot separate the two halves, and no shipped plan
frees both. `mccusker_default` frees the instrument widths and none of these
four; `lab_sample_refine` frees these four and none of the instrument's.

`particle_radius_um` cannot be obtained from the pattern at all, which is why it
is a plain float rather than a `Parameter`. Profile broadening measures the
coherent domain, which is smaller than and unrelated to the particle whose
absorption path Brindley's correction integrates over, and conflating the two is
a standing error. Supply it from a micrograph or a particle-size measurement, or
leave it `None`.

`Cell` holds six parameters and applies no symmetry itself.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Cell.a`, `Cell.b`, `Cell.c` | `Parameter` | required | axis lengths in Å |
| `Cell.alpha`, `Cell.beta`, `Cell.gamma` | `Parameter` | required | angles in degrees |

Store all six and let the space group decide which are independent.
`ParameterTable` ties them from the space-group **setting**, which is not the
same as the crystal system: an R lattice on rhombohedral axes needs a = b = c
with the angles free, and monoclinic has three unique-axis choices. A
symmetry-fixed angle that disagrees with its symmetry is refused rather than
snapped, because the table has no channel in which to report a correction. The
reader has one, so a small deviation is repaired at read and recorded; see
[](files.md).

`Cell.cubic` builds all six from one length, and `Cell.lengths_angles` returns
the six values as a tuple.

`Atom` is one site in the asymmetric unit.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Atom.label` | str | required | the site label, as a CIF spells it |
| `Atom.species` | str | required | the scattering species: `"La"`, `"B"`, `"Fe3+"` |
| `Atom.x`, `Atom.y`, `Atom.z` | `Parameter` | required | fractional coordinates |
| `Atom.occ` | `Parameter` | 1.0, in [0, 1.5] | site occupancy |
| `Atom.biso` | `Parameter` | 0.5 Å², in [0, 25] | isotropic displacement, B = 8π²·U |
| `Atom.aniso` | `AnisoU` or None | `None` | anisotropic displacement, CIF U^ij, {eq}`int-dw-aniso` |

`species` is validated when the model compiles rather than when the object is
built, so an unknown symbol fails with a crystallographic message instead of a
schema error. Coordinates do not refine as x, y and z: the table wires one
degree of freedom per direction the site symmetry allows and ties the three
coordinates to those, so a fully fixed special position contributes no free
entries at all and `vary=True` on such a coordinate raises. [](model.md) has the
paths and what a tied row looks like.

An atom has one displacement model. Set `aniso` and `biso` becomes an inert
record of the starting estimate; asking to refine both raises rather than
leaving a dead parameter in the vector.

```python
from rietx import Atom, Cell, Parameter, Phase, Structure

lab6 = Structure(phases=[Phase(
    name="LaB6",
    space_group="P m -3 m",
    cell=Cell.cubic(4.15689, vary=True),
    atoms=[
        Atom(label="La", species="La", x=Parameter(value=0.0),
             y=Parameter(value=0.0), z=Parameter(value=0.0)),
        Atom(label="B", species="B", x=Parameter(value=0.19964),
             y=Parameter(value=0.5), z=Parameter(value=0.5)),
    ],
)])
assert lab6.phases[0].cell.lengths_angles()[:3] == (4.15689, 4.15689, 4.15689)
```

### The optional blocks

Three fields take a block that is absent by default. Each is opt-in for the same
reason: declaring one changes which parameters a plan will free, and reading a
file must not do that silently.

`AnisoU` stores the six CIF U^ij components in Å², the numbers a
`_atom_site_aniso_U_ij` loop carries. `AnisoU.u11`, `AnisoU.u22` and
`AnisoU.u33` are required and `AnisoU.u12`, `AnisoU.u13`, `AnisoU.u23` default
to zero. `AnisoU.isotropic` builds the tensor equivalent to a given U_iso for a
cell, which is *not* U_iso on the diagonal unless the reciprocal axes are
orthogonal; `AnisoU.from_values` takes the six numbers in order and
`AnisoU.values` returns them. Components refine through the site-symmetry
patterns rather than one at a time, so `min` and `max` on a component are inert
and a tensor outside the allowed subspace raises.

`StephensStrain` is anisotropic strain broadening. Fifteen coefficients, each
named for the monomial h^H k^K l^L it multiplies, in units of 10⁻¹² Å⁻⁴:

| H+K+L = 4, by shape | Fields |
|---|---|
| one index | `StephensStrain.s400`, `StephensStrain.s040`, `StephensStrain.s004` |
| three and one | `StephensStrain.s310`, `StephensStrain.s301`, `StephensStrain.s130`, `StephensStrain.s031`, `StephensStrain.s103`, `StephensStrain.s013` |
| two and two | `StephensStrain.s220`, `StephensStrain.s202`, `StephensStrain.s022` |
| two and one and one | `StephensStrain.s211`, `StephensStrain.s121`, `StephensStrain.s112` |

They multiply the literal monomials, where some other codes fold the symmetry
multiplicities in, so a coefficient copied from another program has to be matched
by the width it produces rather than by its name. Symmetry decides which are
independent, and the space group's own operators derive that set.
`StephensStrain.isotropic` seeds the block from one strain in ppm of ΔM/M and a
cell, and it is the only legal starting point, because the width goes as a square
root whose slope is unbounded at zero. `StephensStrain.from_values` and
`StephensStrain.values` are the tuple interface. Declaring the block locks
`Phase.lor_strain`, whose column is identically the isotropic direction of the
subspace.

`PreferredOrientation` is the March-Dollase correction: `PreferredOrientation.axis`
is a fixed integer hkl and `PreferredOrientation.r` is the one refinable number,
with r = 1 the identity.

## The instrument

`Instrument` is everything about the measurement except the sample.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Instrument.source` | `Source` or `NeutronSource` | required | the radiation, discriminated on `kind` |
| `Instrument.geometry` | `Geometry` | capillary, no aberrations | how the specimen sits in the beam |
| `Instrument.zero_shift` | `Parameter` | 0.0 deg, in [−0.5, 0.5] | a constant 2θ offset, the one position error every geometry has |
| `Instrument.profile` | `ProfileTCHZ` | see below | the instrumental width function |
| `Instrument.background` | one of three | `BackgroundChebyshev` | the pedestal under the peaks |

Four constructors build a plausible instrument, and the difference between them
is which aberrations exist at all rather than which are switched on.

| Constructor | Geometry | Radiation | Declares |
|---|---|---|---|
| `Instrument.debye_scherrer` | capillary | one wavelength you pass | `polarization=0.99`, optional capillary radius and µR |
| `Instrument.bragg_brentano` | flat plate, reflection | an anode name, Kα1 + Kα2 | goniometer radius 217.5 mm, `ka2_ratio=0.5`, optional monochromator angle |
| `Instrument.flat_plate_transmission` | flat plate, transmission | an anode name, Kα1 by default | optional µt and thickness |
| `Instrument.constant_wavelength_neutron` | capillary | one wavelength, nuclear scattering | K pinned at 1, no dispersion, optional `fwhm_deg` width seed |

```python
from rietx import Instrument

synchrotron = Instrument.debye_scherrer(wavelength=0.4139090)
lab = Instrument.bragg_brentano(radiation="CuKa", monochromator_two_theta=26.6)
assert [line.wavelength.value for line in lab.source.lines] == [1.5405929,
                                                                1.5444274]
assert round(lab.source.polarization.value, 4) == 0.5557
```

That 26.6° is a Cu number rather than a property of graphite. The same crystal
sits near 12.1° at Mo Kα, where K is 0.511 rather than 0.556, so compute it for
the anode in use instead of copying the example.

Ask `capabilities()` for the anode names rather than trusting a list in prose.

### The source

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Source.lines` | list[`EmissionLine`] | required | one entry per emission line, at least one |
| `Source.polarization` | `Parameter` | 0.5 | the fraction K of {eq}`corr-lp`; 0.5 is an unpolarised beam |
| `Source.dispersion` | `Dispersion` or None | on | anomalous scattering, {eq}`int-friedel` |
| `Source.kind` | `"xray_cw"` | `"xray_cw"` | constant-wavelength X-rays |

`Source.primary_wavelength` is the first line's wavelength **as a float**,
which is the one every d-spacing is quoted against.
`Source.wavelength_parameters` is the list of live wavelength `Parameter`
objects, one per line, and is what code that needs to *write* a wavelength
uses — `NeutronSource.lines` builds a fresh object per access, so a write
through `lines[i].wavelength` lands on a throwaway there.

`EmissionLine.wavelength` is a `Parameter` in Å, defaulting to `vary=False`,
and `EmissionLine.weight` is a refinable intensity relative to line 0. Line 0's
weight is structurally locked at 1, since it is degenerate with the phase
scales. Each line diffracts at its own Bragg angle, so a doublet's splitting
grows with tan θ ({eq}`pos-doublet`) and is never a fixed 2θ offset.

A bare number is still accepted where a wavelength `Parameter` is wanted, so
`EmissionLine(wavelength=1.5406)` builds a fixed one and every instrument
document written before this became a `Parameter` validates unchanged.

(a-refinable-wavelength)=
#### A refinable wavelength

`EmissionLine.wavelength` and `NeutronSource.wavelength` default to
`vary=False`, and for a **single** histogram that default is a fence rather
than a convention. Bragg's law is {eq}`pos-bragg`, so the pattern measures
λ/(2 sin θ) and fixes only the *product* of λ with a reciprocal cell — a free λ
beside a free cell is an exactly flat direction, and freeing one is refused
naming the degeneracy:

```python
from rietx import Instrument
from rietx.params.vector import check_wavelength_freedom

instrument = Instrument.debye_scherrer(wavelength=0.4139090)
instrument.source.lines[0].wavelength.vary = True
try:
    check_wavelength_freedom(["instrument.source.lines.0.wavelength"],
                             n_wavelengths=1, n_histograms=1)
except ValueError as exc:
    assert "single-histogram" in str(exc)
```

Across several histograms of one specimen the degeneracy breaks, because they
share one cell. The rule is stated in full — and enforced — in
{ref}`a-refinable-wavelength-jointly`; the short version is **hold one
wavelength, free at most N − 1**, and hold the one belonging to the histogram
that determines the cell.

This is `EmissionLine.weight`'s convention one rank up. In both cases one
member of a set is pinned to fix a scale the data cannot set and the rest are
free; what differs is where the set lives. A line weight's scale lives inside
one source, so line 0 is locked in the parameter table. A wavelength's scale
lives in the *cell*, which is shared across instruments, so no single
instrument can count the set and the check sits where the joint problem is
assembled.

Only **line 0**'s wavelength is ever refinable. Within one source the lines'
wavelength *ratio* is atomic physics — the tabulated Kα1/Kα2 pair traces to one
NIST column for exactly this reason, and is known to about 20 ppm — so a
secondary line's wavelength is structurally locked, the way line 0's *weight*
is. The two locks are the same argument pointed in opposite directions: a weight
is relative to something inside the source, a wavelength is relative to
something outside it.

A consequence worth stating: a monochromator's second-order λ/2 harmonic cannot
be modelled *alongside* a refining wavelength. Adding a second `EmissionLine` at
λ/2 with its own weight models the harmonic at a fixed λ, but its wavelength
would not follow line 0's as that refines. Nothing here does that.

`Dispersion` is on by default. `Dispersion.table` names the tabulation and
`Dispersion.overrides` takes measured f′, f″ pairs per element, which is what
you need near an absorption edge, where the table is wrong in principle rather
than merely coarse. Setting `dispersion=None` declines the correction and
reproduces the pre-v1.0 numbers exactly, and the fit says so with a diagnostic.
It is the only correction in the package that needs no information a caller
lacks, since the species and the wavelength are enough.

(a-neutron-source)=
### A neutron source

`NeutronSource` is the other arm of `Instrument.source`. It is a separate class
rather than a flag on `Source` because almost every field of an X-ray source is
meaningless for neutrons, and a class that has to explain which of its own
fields are inert is worse than two classes.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `NeutronSource.wavelength` | `Parameter` | required | Å, `vary=False` — see {ref}`a-refinable-wavelength` |
| `NeutronSource.kind` | `"neutron_cw"` | `"neutron_cw"` | constant wavelength, the discriminator you write |

Three read-only properties let code written for an X-ray source keep working.
`NeutronSource.lines` is the single line, weight structurally 1 — with one line
there is nothing for a relative weight to be relative to.
`NeutronSource.primary_wavelength` is that wavelength as a float, and
`NeutronSource.wavelength_parameters` is the live `Parameter` behind it, in a
one-element list so a caller need not know which arm of the union it holds.
That property is the one authority for writing a refined wavelength back:
`lines` is a *property* here and a stored field on `Source`, so writing through
`lines[0].wavelength` would land on a fresh object and the refined value would
vanish at the next recompile.
`NeutronSource.polarization` is 1.0 and refuses to be anything else, and
`NeutronSource.dispersion` is always `None`.

Both of those last two are physics, not simplifications:

- **K = 1** is why no new correction code exists. Neutrons are not polarised by
  a monochromator the way the Thomson cross-section polarises X-rays, so the
  Lorentz-polarisation factor {eq}`corr-lp` collapses to the bare Lorentz
  factor 1/(sin²θ·cosθ) — which is geometry, and radiation-independent. K is
  *force-fixed*, so `set_vary` cannot free it; a free K would not be a dead
  column, it would let the fit buy Rwp from a term the physics already knows.
- **No anomalous dispersion.** f′/f″ is an X-ray core-level effect. The neutron
  analogue is a complex, wavelength-dependent b near a nuclear resonance, which
  belongs to a handful of nuclides rather than to the source, so there is no
  field to set and `DISPERSION_NEGLECTED` stays quiet.

What actually changes in the calculation is the scattering amplitude, and only
that. An X-ray form factor f(Q) falls off with angle because the electron cloud
has spatial extent; a nucleus is a point scatterer on this scale, so **b is
independent of Q** — one number per species, not a five-Gaussian expansion, and
it may be **negative**. Part 2 has the amplitude and its source.

`Instrument.constant_wavelength_neutron` is the constructor. It builds a
capillary geometry, because that is what a CW neutron diffractometer is — a can
of powder in a beam with detectors on a circle — so the cylindrical absorption
correction and the capillary offsets apply unchanged.

```python
from rietx import Instrument

bt1 = Instrument.constant_wavelength_neutron(wavelength=2.0780, fwhm_deg=0.3)
assert bt1.source.kind == "neutron_cw"
assert bt1.source.polarization.value == 1.0
assert bt1.source.dispersion is None
```

Pass `fwhm_deg` unless you have a reason not to. It seeds the Caglioti terms
from an observed peak width, and it matters more here than on a lab X-ray: a
neutron instrument's lines are typically 0.2–0.5° where the `ProfileTCHZ`
default is a synchrotron line of about 0.03°, and the per-stage evaluation
windows are sized from the seed, so a 0.3° line started from the default is not
found at all. The width *function* needs no neutron-specific code — the
Caglioti law U·tan²θ + V·tanθ + W is the neutron resolution function, and the
X-ray path is the borrower.

Two corrections are refused rather than ignored. `surface_roughness` is an
X-ray effect: both models depress the low-angle intensity of a beam that
penetrates microns, while a thermal neutron beam penetrates centimetres, so the
correction has no regime here rather than a small coefficient. And a species
this build has no tabulated scattering length for raises at compile naming the
species, rather than contributing zero — a substituted zero would delete a site
from the structure factor without changing the shape of anything.

:::{admonition} Time-of-flight is not this
:class: note
Everything here is *constant* wavelength. A time-of-flight instrument spans a
range of wavelengths across several detector banks, which changes the profile
function, the intensity corrections and the number of histograms at once, and
the thermal scattering-length table cannot give b(λ) for a resonant absorber.
`capabilities().radiations` is the list of what this build actually accepts.
:::

### The geometry

`Geometry.kind` selects one of `"debye_scherrer"`, `"bragg_brentano"` and
`"flat_plate_transmission"`, and it decides which of the other fields are
meaningful. A field that belongs to another geometry is refused rather than
ignored.

Every geometry:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Geometry.kind` | literal | `"debye_scherrer"` | which of the three geometries |
| `Geometry.goniometer_radius_mm` | float or None | `None` | R in mm; required for `bragg_brentano`, and what {eq}`pos-capillary` divides by |
| `Geometry.axial_sl`, `Geometry.axial_hl` | `Parameter` | 0.0 | Finger-Cox-Jephcoat axial divergence: sample and detector half-lengths over R |
| `Geometry.packing_fraction` | float | 0.6 | solid fraction of the specimen, an absorption estimator input |

A capillary, `kind="debye_scherrer"`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Geometry.capillary_offset_along_beam` | `Parameter` | 0.0 mm | the sin 2θ half of {eq}`pos-capillary`, positive downstream |
| `Geometry.capillary_offset_across_beam` | `Parameter` | 0.0 mm | the cos 2θ half, positive toward increasing 2θ |
| `Geometry.mu_r` | float or None | `None` | µ·R of the packed specimen, {eq}`corr-rouse`; 0.0 is off exactly |
| `Geometry.capillary_radius_mm` | float or None | `None` | bore radius in mm, an estimator input for µR |

A flat plate, `kind="bragg_brentano"` or `kind="flat_plate_transmission"`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Geometry.sample_displacement` | `Parameter` | 0.0 mm | specimen surface off the goniometer axis, cos θ, {eq}`pos-displacement` |
| `Geometry.sample_transparency` | `Parameter` | 0.0 | penetration into the specimen, {eq}`pos-transparency` |
| `Geometry.mu_t` | float or None | `None` | µ·t of the specimen, {eq}`corr-fp2` and {eq}`corr-fp3a` |
| `Geometry.thickness_mm` | float or None | `None` | specimen thickness in mm, an estimator input for µt |
| `Geometry.surface_roughness` | `RoughnessSuortti`, `RoughnessPitschke` or None | `None` | low-angle intensity loss, {eq}`corr-suortti` or {eq}`corr-pitschke`; reflection only |

Two things here catch people out.

The absorption coefficients are plain floats rather than parameters, and their
off states disagree. A capillary is off at µR = 0, and a flat plate in reflection
is off at µt = ∞, which is what leaving `mu_t` unset means: a specimen thicker
than the penetration depth needs no correction, since it is exactly degenerate
with the scale. So `mu_t` absent is not `mu_t = 0`, and `mu_t = 0` under
`bragg_brentano` is a specimen of no thickness and raises. Under transmission
zero is legal and means a non-absorbing plate. [](concepts.md) explains why neither
coefficient is refinable.

**The capillary offsets need a radius.** Both default to zero and fixed, because
at a synchrotron with a crystal analyser the displacement error is eliminated
and freeing them is a deliberate act. Setting or freeing either without
`goniometer_radius_mm` is refused rather than defaulted, since {eq}`pos-capillary`
divides by R.

`estimate_mu_r` computes a starting µR from a structure's composition and the
geometry, and returns `None` rather than raising when it cannot: an element
outside the tabulation, a wavelength straddling an edge, or no capillary radius.
A refinement does the same calculation itself when `mu_r` is left `None`.

`RoughnessSuortti` carries `RoughnessSuortti.a` and `RoughnessSuortti.b`;
`RoughnessPitschke` carries `RoughnessPitschke.c` and `RoughnessPitschke.tau`.
Both are `bragg_brentano` only. `RoughnessSuortti.kind` and
`RoughnessPitschke.kind` name the model, which is how a saved instrument comes
back as the one it was rather than as the union's first member.

### The width function

`ProfileTCHZ` is the instrument's contribution to every peak's width. Five
parameters, in degrees 2θ throughout.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `ProfileTCHZ.u` | `Parameter` | 0.0 deg², in [−0.05, 1] | Gaussian tan²θ term, {eq}`prof-caglioti-g` |
| `ProfileTCHZ.v` | `Parameter` | 0.0 deg², in [−0.5, 0.5] | Gaussian tan θ term |
| `ProfileTCHZ.w` | `Parameter` | 1e-3 deg², softplus | Gaussian constant term |
| `ProfileTCHZ.x` | `Parameter` | 1e-3 deg, softplus | Lorentzian 1/cos θ term, {eq}`prof-caglioti-l` |
| `ProfileTCHZ.y` | `Parameter` | 0.0 deg, softplus | Lorentzian tan θ term |
| `ProfileTCHZ.shape` | `"tchz_pv"` or `"voigt"` | `"tchz_pv"` | pseudo-Voigt or the exact convolution |

Match the physics, not the letters. GSAS and FullProf swap the X and Y
assignments, so a value copied from another code has to be matched by its
θ-dependence: size broadening goes as 1/cos θ and strain as tan θ. Getting this
backwards is not a labelling slip, it is a different width function, and this
manual has made the mistake itself.

`w`, `x` and `y` are softplus-positive; `u` and `v` carry negative lower bounds,
so the Gaussian polynomial can bend downward. The quantity that has to stay
positive is the total Γ_G² across the measured range rather than each term, so
read a negative `u` or `v` as a statement about the fitted resolution curve and
check the width it produces at both ends of the range.

`shape` is a compile-time choice, not a refinable one, and both shapes consume
the same five widths, so switching never changes the parameter table.

### The background

Three models, and the choice is about what the background is allowed to imitate.

`BackgroundChebyshev` is a shifted-Chebyshev polynomial:
`BackgroundChebyshev.coefficients` is a list of parameters, four fixed zeros by
default, and `BackgroundChebyshev.with_terms` builds n of them free.

`BackgroundPSpline` is a penalised cubic spline, co-refined with the structure
under the second-difference penalty of {eq}`bg-penalty`.
`BackgroundPSpline.breakpoints` are the knots in 2θ,
`BackgroundPSpline.coefficients` has exactly `len(breakpoints) + 2` entries for
the clamped cubic basis, `BackgroundPSpline.lambda_smooth` is the penalty
weight, and `BackgroundPSpline.air_scatter` scales an additive 1/2θ term for the
low-angle air rise. `BackgroundPSpline.for_range` builds uniform knots over a 2θ
range.

`BackgroundFixedPlusChebyshev` holds a fixed estimated curve additively and
refines a polynomial on top of it: `BackgroundFixedPlusChebyshev.fixed_two_theta`
and `BackgroundFixedPlusChebyshev.fixed_intensity` are the curve, and
`BackgroundFixedPlusChebyshev.chebyshev` the refinable part. Use it when you
have a measured blank or an estimated baseline, since holding a curve additively
keeps the counting statistics intact where subtracting it would not.

```python
from rietx import PatternData
from rietx.schemas.instrument import BackgroundPSpline

bkg = BackgroundPSpline.for_range(2.0, 40.0, knot_step_deg=5.0)
assert len(bkg.coefficients) == len(bkg.breakpoints) + 2

data = PatternData(two_theta=[2.0, 21.0, 40.0], intensity=[900.0, 120.0, 90.0])
assert data.tt()[-1] == 40.0
```

`auto_background` sizes a model to a pattern instead: knot spacing from the
amorphous-hump score, the air term added only when the diagnostics ask for it,
or `kind="chebyshev"` for an order chosen by BIC.

`BackgroundChebyshev.kind`, `BackgroundPSpline.kind` and
`BackgroundFixedPlusChebyshev.kind` are the discriminators. The three models are
one JSON union, so the field is what makes a saved instrument come back as the
model it was.

A background flexible enough to imitate the peaks is a correctness problem
rather than a cosmetic one: it biases displacement parameters up and scales
down, and Rwp improves while it happens. That is measured once per fit and
reported; [](results.md) has the table.

## Calibrating an instrument once and reusing it

The instrument ⊕ sample split works only when the instrument half comes from
somewhere other than the sample you are measuring. The workflow is
three steps, and the middle one is a file.

1. **Calibrate** on a line-profile standard with its certified cell held fixed.
   That is what decorrelates the zero shift from the specimen displacement from
   the cell. The `lab_calibrate` plan frees the scale and background, then the
   zero shift and displacement, then the five width terms, then the
   emission-line weights and the axial ratios, then the displacement
   parameters. It never frees `phases.*.cell.*`, which is the whole point of
   using a standard.
2. **Freeze** with `save_instrument_profile`, which writes the calibrated state
   as JSON and strips what belongs to the measurement rather than the
   goniometer: the background, the specimen displacement and transparency, the
   surface roughness, and the specimen absorption.
3. **Refine the sample** from `load_instrument_profile`, which returns an
   `Instrument` with every stored parameter fixed. The `lab_sample_refine` plan
   frees the scale and background, the specimen displacement, the cell, the four
   sample broadening terms with the anisotropic strain block, the displacement
   parameters, and the surface roughness. It never frees the zero shift or the
   instrument widths, which arrived as data.

Step 2 strips those fields for a specific reason. Roughness is a property of how
one specimen was packed and pressed, and µt of how thick one mount is, so
carrying either into the next sample would pre-bias that sample's displacement
parameters, which is the bias these corrections exist to remove.

[](files.md) has the calls and the file. What matters here is what a loaded
profile means: the calibration is data, so it arrives fixed, and freeing it
again on a sample undoes the decorrelation the standard bought.
