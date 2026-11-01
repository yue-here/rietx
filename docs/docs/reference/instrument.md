# The instrument

This page gives the fields of `Instrument` and of everything inside it: the radiation source, the geometry, the instrumental peak width, the background and declared extra peaks.

[Patterns and structures](data.md) gives the other two objects a refinement needs.
The [parameter map](parameters.md#instrument) gives the name, unit and typical range of each refinable instrument parameter.
[Instrument preset fields](settings.md#instrument-preset-fields) describes each constructor argument.

Every object on this page refuses a field it does not know, and checks its bounds when it is built.

## Instrument

`Instrument` is everything about the measurement except the sample.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Instrument.source` | `Source`, `NeutronSource` or `TOFSource` | required | the radiation, chosen by its `kind` |
| `Instrument.geometry` | `Geometry` | a capillary with no aberrations | how the specimen sits in the beam |
| `Instrument.zero_shift` | `Parameter` | 0.0 deg, unbounded | a constant 2θ offset, the one position error every geometry has |
| `Instrument.profile` | `ProfileTCHZ` | see [Peak width](#peak-width) | the instrument's contribution to every peak's width |
| `Instrument.background` | `BackgroundChebyshev`, `BackgroundPSpline` or `BackgroundFixedPlusChebyshev` | four Chebyshev terms, fixed at 0 | the curve under the peaks |
| `Instrument.extra_components` | list of `HumpComponent` and `PeakComponent` | `[]` | declared peaks added on top of the background |

A source and a correction derived for the other radiation are refused together.
`Geometry.surface_roughness` on a neutron source raises, because a thermal neutron beam penetrates centimetres of the specimen where an X-ray beam penetrates microns.

## Constructors

Five constructors build a plausible instrument.
They differ in which aberrations exist at all, and none of them frees anything.

| Constructor | Geometry | Radiation | Other arguments |
|---|---|---|---|
| `Instrument.debye_scherrer` | capillary | one wavelength you pass | `polarization` (default 0.99), goniometer and capillary radii, packing fraction, µR |
| `Instrument.bragg_brentano` | flat plate, reflection | an anode name (default `"CuKa"`), Kα1 and Kα2 | goniometer radius (default 217.5 mm), `ka2_ratio` (default 0.5), monochromator angle, µt, thickness |
| `Instrument.flat_plate_transmission` | flat plate, transmission | an anode name (default `"CuKa1"`, Kα1 alone) | µt, thickness, packing fraction, `ka2_ratio` |
| `Instrument.constant_wavelength_neutron` | capillary | one neutron wavelength | goniometer and capillary radii, µR, `fwhm_deg`, `harmonics` |
| `Instrument.tof_neutron_bank` | capillary | a time-of-flight bank's DIFC and angle | DIFA, TZERO, DIFB, flight paths, capillary radius, µR, a `ProfileTOF` |

```python
from rietx import Instrument

synchrotron = Instrument.debye_scherrer(wavelength=0.4139090)
lab = Instrument.bragg_brentano(radiation="CuKa", monochromator_two_theta=26.6)
assert [line.wavelength.value for line in lab.source.lines] == [1.5405929,
                                                                1.5444274]
assert round(lab.source.polarization.value, 4) == 0.5557
assert lab.source.kbeta == "monochromator"
```

`monochromator_two_theta` sets the polarisation fraction K to 1/(1 + cos²2θ<sub>m</sub>), and declares that Kβ is removed.
26.6° is graphite (002) at Cu Kα.
The same crystal sits near 12.1° at Mo Kα, where K is 0.511, so compute the angle for the anode in use.
Without a monochromator, K is 0.5.

The anode names are `AgKa`, `CoKa`, `CrKa`, `CuKa`, `FeKa` and `MoKa`, and each has a Kα1-only form such as `CuKa1`, for a beam monochromated before the sample.
`Capabilities.anodes` lists them for the version you run.

`Instrument.debye_scherrer` applies no capillary absorption until you give a capillary radius or µR.
Its capillary offsets can refine only once you give the goniometer radius.

## X-ray source

`Source` is a constant-wavelength X-ray source, `kind="xray_cw"`.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Source.lines` | `list[EmissionLine]` | required | one entry per emission line, at least one |
| `Source.polarization` | `Parameter` | 0.5, in [0, 1] | the fraction K of {eq}`corr-lp`; 0.5 is an unpolarised beam |
| `Source.kbeta` | `"filter"`, `"monochromator"`, `"mirror"` or `None` | `None` | what stands in the beam as far as Kβ goes |
| `Source.dispersion` | `Dispersion` or `None` | on | anomalous scattering, {eq}`int-friedel` |
| `Source.harmonics` | `list[Harmonic]` | `[]` | declared λ/n orders; refused on this radiation ([Monochromator harmonics](#monochromator-harmonics)) |
| `Source.kind` | `"xray_cw"` | `"xray_cw"` | the discriminator |

`Source.kbeta` decides whether the contamination screen looks for Kβ and tungsten Lα lines.
`None` means undeclared, and the screen runs.
`"monochromator"` skips both searches.
`"filter"` and `"mirror"` are recorded and change nothing, because the screen still finds an injected leak at 2 % of Kα behind either.
The screen reads the field where it is handed the source: `pick_peaks`, `diagnose(source=)` and `auto_background(source=)`.
The GUI's import wizard fills `kbeta` from the file's header.
A monochromator after the sample gives `"monochromator"`, otherwise a filter gives `"filter"` and a mirror `"mirror"`.
A file that lists a monochromator before the sample stays `None`.

`Source.primary_wavelength` is the first line's wavelength as a float, and every d-spacing is quoted against it.
`Source.wavelength_parameters` is the list of live wavelength `Parameter` objects, one per line, for code that writes a wavelength.

### Emission lines

| Field | Type | Default | Meaning |
|---|---|---|---|
| `EmissionLine.wavelength` | `Parameter` | required | λ in Å, positive |
| `EmissionLine.weight` | `Parameter` | 1.0, at or above 0 | intensity relative to line 0 |

A bare number is accepted for the wavelength, so `EmissionLine(wavelength=1.5406)` builds a fixed one, bounded below at 1e-3 Å.
Line 0's weight is locked at 1, because it is degenerate with the phase scales.
The presets give a Kα2 line a weight of `ka2_ratio`, in [0, 1].
Each line diffracts at its own Bragg angle, so a doublet's splitting grows with tan θ {eq}`pos-doublet` and is never a fixed 2θ offset.

### Wavelength refinement

`EmissionLine.wavelength` and `NeutronSource.wavelength` are fixed by default.
Bragg's law {eq}`pos-bragg` fixes only the product of λ with the reciprocal cell, so on one pattern a free λ beside a free cell is an exactly flat direction.
With the cell held, λ refines on one pattern.
That is how a beamline's wavelength is calibrated: a standard of certified cell, such as NIST SRM 640c silicon, holds the scale the cell would otherwise trade against λ.
A glob that would free λ beside a free cell skips λ, as a plan's stage does.
A solve that finds both free refuses, naming the degeneracy:

```python
from rietx import Instrument, Structure
from rietx.examples import examples_dir
from rietx.params.vector import ParameterTable

wavelength = "instrument.source.lines.0.wavelength"
structure = Structure.from_cif(examples_dir() / "fluorapatite.cif")

held = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
assert held.set_vary([wavelength], True) == [wavelength]   # the cell is held
held.check_wavelength_against_cell()                        # a solve accepts it

free = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
free.set_vary(["phases.0.cell.a"], True)
assert free.set_vary([wavelength], True) == []              # skipped beside a free cell

held.set_vary(["phases.0.cell.a"], True)
try:
    held.check_wavelength_against_cell()
except ValueError as exc:
    assert "cannot both be free" in str(exc)
else:
    raise AssertionError("a free λ beside a free cell was accepted")
```

Patterns of one specimen fitted together share one cell, and that breaks the degeneracy too.
Hold one wavelength and free at most N − 1 of N, holding the wavelength of the pattern that determines the cell best.
A free wavelength also needs its pattern's cell shared with a pattern whose wavelength is held.
[How to fit several patterns of one specimen together](../guides/joint.md) shows the procedure.

The rule has the same shape as the line weights.
One member of a set is pinned to fix a scale the data cannot set, and the rest are free.
A line weight's scale lives inside one source, so the table locks line 0.
A wavelength's scale lives in the cell.
Several instruments share the cell, so the check runs where the joint fit is assembled.

Only line 0's wavelength can refine.
The ratio between lines of one source is atomic physics: the Kα1/Kα2 pairs come from one column of the NIST tabulation, known to about 20 ppm.
A secondary line's wavelength is therefore locked, as line 0's weight is.

On an X-ray source, a λ/2 harmonic can only be a second `EmissionLine` at its own fixed wavelength.
That wavelength does not follow line 0 as it refines.
A `Harmonic` declared on a neutron source is derived from the fundamental and follows it.

### Anomalous dispersion

`Dispersion` is on by default.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Dispersion.table` | `"cromer_liberman"` | `"cromer_liberman"` | the tabulation f′ and f″ come from |
| `Dispersion.overrides` | `dict[str, tuple[float, float]]` | `{}` | measured (f′, f″) per element, such as `{"Zn": (-3.1, 0.5)}` |

f′ and f″ are constants of the element and the wavelength, looked up once when a stage compiles, and never refined.
An override key is a bare element symbol, because f′ and f″ are core-level effects.
Near an absorption edge the table is wrong in principle, since f″ there depends on the compound.
A wavelength inside an absorption-edge interval of the table raises, and an override lifts that refusal for its element.
`dispersion=None` declines the correction, reproduces the numbers of versions before 1.0 exactly, and reports [`DISPERSION_NEGLECTED`](diagnostics-refinement.md#dispersion_neglected).

## Neutron source

`NeutronSource` is a constant-wavelength neutron source, `kind="neutron_cw"`.
It is a class of its own because almost every field of an X-ray source has no meaning for neutrons.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `NeutronSource.wavelength` | `Parameter` | required | λ in Å, fixed ([Wavelength refinement](#wavelength-refinement)) |
| `NeutronSource.harmonics` | `list[Harmonic]` | `[]` | declared λ/n monochromator orders ([Monochromator harmonics](#monochromator-harmonics)) |
| `NeutronSource.kind` | `"neutron_cw"` | `"neutron_cw"` | the discriminator |

Read-only properties let code written for an X-ray source run unchanged.

| Property | Value |
|---|---|
| `NeutronSource.lines` | the fundamental, then one line per declared harmonic; the fundamental's weight is 1 |
| `NeutronSource.primary_wavelength` | the wavelength as a float |
| `NeutronSource.wavelength_parameters` | the live wavelength `Parameter`, in a one-element list |
| `NeutronSource.polarization` | 1.0, fixed |
| `NeutronSource.dispersion` | `None` |

`NeutronSource.lines` builds new objects at each access.
A write through `lines[0].wavelength` is lost, so write a refined wavelength through `wavelength_parameters`.

K = 1 because a monochromator does not polarise neutrons the way the Thomson cross-section polarises X-rays.
The Lorentz-polarisation factor {eq}`corr-lp` then reduces to the Lorentz factor 1/(sin²θ cos θ), and no separate correction code exists.
K is fixed by force, so `Refinement.set_vary` cannot free it.

There is no anomalous dispersion.
The neutron analogue is a complex scattering length near a nuclear resonance.
It belongs to a few nuclides rather than to the source, so there is no field to set, and `DISPERSION_NEGLECTED` stays quiet.

The scattering amplitude is the only part of the calculation that changes.
A nucleus is a point scatterer on this scale, so its scattering length b is one number per species, independent of Q, and it may be negative.
[The neutron scattering length](../theory/intensities.md#the-neutron-scattering-length) gives the amplitude and its source.
A species with no tabulated scattering length raises when the model compiles, naming the species.

`Instrument.constant_wavelength_neutron` builds a capillary geometry, so the cylindrical absorption correction and the capillary offsets apply unchanged.

```python
from rietx import Instrument

bt1 = Instrument.constant_wavelength_neutron(wavelength=2.0780, fwhm_deg=0.3)
assert bt1.source.kind == "neutron_cw"
assert bt1.source.polarization.value == 1.0
assert bt1.source.dispersion is None
```

Pass `fwhm_deg`.
It sets `ProfileTCHZ.w` to the square of the width you observed and leaves `x` at its default, so the starting profile is a Gaussian of that width at every angle.
A neutron instrument's lines are typically 0.2-0.5° wide, against about 0.03° for the default profile.
The evaluation windows of each stage are sized from the starting width, so a 0.3° line started from the default is not found.

The width bounds are an X-ray instrument's.
No width has a chosen ceiling. Each stops at the width of the 2θ axis, 180° for `x` and `y` and 180² deg² for `u`, `v` and `w`, which no peak reaches.
`u`, `v` and `y` have no chosen floor either, so a long-wavelength neutron line's model builds: on the ILL D1B Co₃O₄ set at λ = 2.52 Å the published model has V = −0.501.
The neutron constructor builds its profile with `ProfileTCHZ.coarse`, which builds all five widths from values.

```python
from rietx.schemas.instrument import ProfileTCHZ

try:
    ProfileTCHZ(u=1.576)
except ValueError as refusal:
    assert "ProfileTCHZ.coarse" in str(refusal)
else:
    raise AssertionError("a bare width is refused")
d1b = ProfileTCHZ.coarse(u=1.576, v=-0.501, w=0.475)
assert d1b.v.min == -(180.0 ** 2) and d1b.w.max == 180.0 ** 2
```

`Geometry.surface_roughness` is refused on a neutron source, because neither roughness model has a regime where the beam penetrates centimetres.

## Time-of-flight bank

`TOFSource` is one detector bank of a neutron time-of-flight diffractometer, `kind="neutron_tof"`.
The whole moderator spectrum reaches the specimen, and a bank at a fixed angle separates the reflections by arrival time.
The source has no wavelength.
A reflection's position comes from its d-spacing through the bank's calibration, {eq}`pos-tof`: TOF = DIFC·d + DIFA·d² + TZERO + DIFB/d.

This version reads a bank and refines none.
`Refinement.fit` and every other entry point that computes a pattern refuse a `neutron_tof` source by name.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `TOFSource.difc` | `Parameter` | required | the linear term in µs/Å, fixed, at least 1 |
| `TOFSource.difa` | `Parameter` | 0, fixed | the quadratic term in µs/Å², usually small and often negative |
| `TOFSource.tzero` | `Parameter` | 0, fixed | the constant offset in µs |
| `TOFSource.difb` | `Parameter` | 0, fixed | GSAS-II's 1/d term, in µs·Å |
| `TOFSource.two_theta_bank_deg` | `float` | required | the bank's fixed scattering angle, in (0, 180)° |
| `TOFSource.l1_m` | `float` or `None` | `None` | primary flight path in m, a record of the file |
| `TOFSource.l2_m` | `float` or `None` | `None` | secondary flight path in m, a record of the file |
| `TOFSource.profile_tof` | `ProfileTOF` | all zero | the GSAS type-3 peak-shape coefficients |
| `TOFSource.incident_spectrum` | `IncidentSpectrum` | `ITYP` 0, no spectrum | the moderator spectrum the bank's data still carries |
| `TOFSource.kind` | `"neutron_tof"` | `"neutron_tof"` | the discriminator |

A bare number is accepted for each of the four constants and becomes a fixed `Parameter`, because a constant read from an instrument-parameter file is a calibration.
The bank angle is a float and never refines, because it is already folded into the refined DIFC.

The GSAS manual writes the offset `ZERO`, GSAS-II writes `Zero`, and Mantid writes `TZERO`.
The field takes Mantid's spelling, because it is the only one that cannot be confused with `Instrument.zero_shift`.
That field is a 2θ offset in degrees.
The readers map all three.

DIFB is carried because dropping it would be silent.
Neither the GSAS manual nor Mantid documents a fourth term, and GSAS-II evaluates one.
A reader of the three-term relation would put the peaks of a GSAS-II project that sets `difB` in the wrong place, with nothing said.

| Member | Value |
|---|---|
| `TOFSource.polarization` | 1.0, fixed, as for `NeutronSource` |
| `TOFSource.dispersion` | `None` |
| `TOFSource.harmonics_supported` | `False`: there is no monochromator to pass an order |
| `TOFSource.continuous_spectrum` | `True`: `capabilities()` does not report this source as one wavelength |
| `TOFSource.tof_from_d` | the flight time in µs for a d-spacing in Å |
| `TOFSource.d_from_tof` | the d-spacing for a flight time |

With DIFA or DIFB non-zero the relation has no useful closed-form inverse.
`d_from_tof` iterates by successive substitution, and raises rather than return an unconverged value.
On a real calibration, with a small DIFA against a DIFC of thousands, it converges in a few iterations.

### Time-of-flight peak shape

`ProfileTOF` holds the GSAS type-3 coefficients: `ProfileTOF.alpha0`, `ProfileTOF.alpha1`, `ProfileTOF.beta0`, `ProfileTOF.beta1`, `ProfileTOF.sig0`, `ProfileTOF.sig1`, `ProfileTOF.sig2`, `ProfileTOF.gam0`, `ProfileTOF.gam1` and `ProfileTOF.gam2`.
Each is a term of a polynomial in the reflection's d-spacing, where `ProfileTCHZ` uses the angle:

$$
\alpha(d) = \alpha_0 + \alpha_1/d, \quad
\beta(d) = \beta_0 + \beta_1/d^4, \quad
\sigma^2(d) = \sigma_0^2 + \sigma_1^2 d^2 + \sigma_2^2 d^4, \quad
\gamma(d) = \gamma_0 + \gamma_1 d + \gamma_2 d^2 .
$$

All ten default to 0 and fixed, because an instrument-parameter file's profile is a calibration refined against a standard.
The three `sig` terms are variances and are bounded below at 0.
A bare number becomes a fixed `Parameter` with the field's unit and bounds.
In this version the coefficients are carried and listed in a bank's parameter table, and nothing evaluates them.

### Incident spectrum

`IncidentSpectrum` is the moderator spectrum a bank's data still carries, and whether it carries one is a fact about the file.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `IncidentSpectrum.itype` | `int` | 0 | the GSAS `ITYP` function number; 0 is no spectrum |
| `IncidentSpectrum.coefficients` | `list[Parameter]` | `[]` | the file's `ICOFF` block, fixed, with the file's esds on `stderr` |
| `IncidentSpectrum.tof_min_us` | `float` or `None` | `None` | start of the flight-time window the spectrum was fitted over, in µs |
| `IncidentSpectrum.tof_max_us` | `float` or `None` | `None` | end of that window, in µs |

The file gives the window in milliseconds, and the reader converts it.
A type the GSAS manual does not define is refused by number.
Types 1 and 2 take 11 coefficients and types 3 to 5 take 12, and a list of another length is refused rather than padded.
The default, type 0 with no coefficients, is what a reduction that already divided by a vanadium measurement leaves.
ISIS GEM, SNS NOMAD and POWGEN write it.
A LANSCE-style file writes `ITYP 1` with a full `ICOFF` block.
`read_gsas_tof_iparm` holds to the documented layout, and refuses a block whose fifth pair (P<sub>10</sub>, P<sub>11</sub>) is non-zero.
`rietx.io.legacy.read_lansce_iparm` carries such a block as written.
Nothing in this version evaluates a spectrum.

### Building a bank

`Instrument.tof_neutron_bank` is the constructor, with the same shape as `Instrument.constant_wavelength_neutron`.
A multi-bank experiment is several instruments, one per bank, because DIFC, the angle and the whole profile differ per bank.

A bank's parameter table carries its own rows: `instrument.source.difc`, `instrument.source.difa`, `instrument.source.tzero`, `instrument.source.difb`, `instrument.source.profile_tof.*` and `instrument.source.incident_spectrum.p*`.
It does not carry the constant-wavelength rows whose roles these play: `instrument.profile.*` (the widths), `instrument.zero_shift` (the zero) and the two specimen position aberrations.
A pattern naming one of those matches nothing on a bank, and `vary=True` written on one of them is refused by name.

```python
from rietx import Instrument

# a synthetic bank at 90°: DIFC ≈ 505.555·L·sin θ for a total path L in m
bank = Instrument.tof_neutron_bank(
    difc=12000.0, difa=-1.5, tzero=-5.0,
    two_theta_bank_deg=90.0, l1_m=30.0, l2_m=3.5)
assert bank.source.kind == "neutron_tof"
assert round(float(bank.source.d_from_tof(bank.source.tof_from_d(3.1355))), 4) == 3.1355
```

`read_gsas_tof_iparm` fills a bank in from a GSAS instrument-parameter file.

## Monochromator harmonics

A crystal monochromator set to pass λ also reflects the higher orders of the same planes.
The beam therefore carries a small λ/n component for every order that is not extinct, {eq}`pos-harmonic-mono`.
At a given 2θ that component diffracts from planes of spacing λ/(2n sin θ), so its peak from a given hkl sits at lower 2θ than the fundamental's, {eq}`pos-harmonic-d`.
Left out of the model, it is intensity where the model puts none.

Declare it with `Harmonic`, on the source or through the constructor, naming the orders the monochromator passes:

```python
from rietx import Instrument
from rietx.schemas.instrument import Harmonic

# NIST BT-1's Cu(311) passes λ/2
bt1 = Instrument.constant_wavelength_neutron(
    wavelength=1.54040, fwhm_deg=0.3, harmonics=[2])
assert [line.wavelength.value for line in bt1.source.lines] == [1.54040, 0.77020]
# a harmonic's λ is derived, so it is never free even when the fundamental is
assert [line.wavelength.vary for line in bt1.source.lines] == [False, False]

# general in n
thirds = Instrument.constant_wavelength_neutron(1.54040, harmonics=[2, 3])
assert len(thirds.source.lines) == 3
assert thirds.source.harmonics == [Harmonic(order=2), Harmonic(order=3)]
```

The order has no default, because which orders pass depends on the monochromator's crystal.
Cu(311) and graphite pass λ/2.
In the diamond structure of Si and Ge, a reflection on all-odd indices has its second order extinct, so Si(111), Ge(311) and Ge(733) pass λ/3 and no λ/2.
`harmonics=True` is refused with that message.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Harmonic.order` | `int`, ≥ 2 | none, required | n in λ/n |
| `Harmonic.weight` | `Parameter` | 0.01, fixed, at or above 0 | intensity relative to line 0, as for any emission line |
| `Harmonic.wavelength_factor` | `float` | derived | 1/n, the factor on the fundamental wavelength |

The weight starts at 1 %, below every value reported for a real beamline, so the fit has to move it to reach one.
A weight that refines far above a few per cent says the peaks it fills are not harmonic peaks, and [`HARMONIC_FRACTION`](diagnostics-refinement.md#harmonic_fraction) reports it at `warning` above 15 %.
Free the weights with `instrument.source.lines.*.weight` once the profile and the scale are settled, never in the first stage.
[`HARMONIC_FRACTION`](diagnostics-refinement.md#harmonic_fraction) reports the refined fraction.

`Source.harmonics_supported` and `NeutronSource.harmonics_supported` say whether a radiation accepts a declaration at all: `False` and `True`.
The refusal reads them, and so does `RadiationCapability.harmonic_contamination`, the answer `capabilities().radiations` gives.
Both classes have a `harmonics` field, so read support from the flag.

A harmonic is an emission line and not a phase.
The usual workaround is an extra phase with a doubled lattice parameter, which gets the positions right and the intensities wrong.
A cell 2a has d′ = 2d, so λ diffracts from it where λ/2 diffracts from the real d, but its structure factors belong to a cell that does not exist.
A line at λ/n diffracts the same hkl list with the same |F|², because |F|² depends on the reflection through sin θ/λ = 1/2d and not on the wavelength that reaches it.
So positions and intensities come out together, for one refinable number.

An empty list is off, and gives the spectrum the source always had, bit for bit.

Three declarations are refused.

- An `order` of 1. n = 1 is the fundamental, and a second copy of line 0 is degenerate with the phase scales.
- A repeated order. Two lines at one wavelength with two weights for one physical component are a flat direction.
- Any harmonic on an X-ray source. One f′ + if″ is shared across every emission line of a phase. That is exact only while f is real, and λ against λ/2 is a 100 % change in wavelength, usually with absorption edges between. On an X-ray source, declare the λ/n component as a plain `EmissionLine` with `dispersion=None`, where f = f₀ serves both lines. The refusal's message says so.

Whether a monochromator passes a harmonic at all is arithmetic on its reflection.
Cu(311) doubles to the allowed (622), so the second order passes.
A diamond-structure crystal cut on all-odd indices, such as Ge(733), cancels its own second order.
[Monochromator harmonics](../theory/peak-positions.md#monochromator-harmonics) has both.

## Geometry

`Geometry.kind` is one of `"debye_scherrer"`, `"bragg_brentano"` and `"flat_plate_transmission"`, and it decides which other fields apply.
A field that belongs to another geometry is refused.

Every geometry:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Geometry.kind` | one of three strings | `"debye_scherrer"` | which of the three geometries |
| `Geometry.goniometer_radius_mm` | `float` or `None` | `None` | R in mm; required for `bragg_brentano`, and what {eq}`pos-capillary` divides by |
| `Geometry.axial_sl`, `Geometry.axial_hl` | `Parameter` | 0.0, at or above 0 | Finger-Cox-Jephcoat axial divergence: the specimen and receiving-slit half-lengths over R |
| `Geometry.packing_fraction` | `float` | 0.6, in (0, 1] | the solid fraction of the specimen, used to estimate µR and µt |

A capillary, `kind="debye_scherrer"`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Geometry.capillary_offset_along_beam` | `Parameter` | 0.0 mm, unbounded | the sin 2θ half of {eq}`pos-capillary`, positive downstream |
| `Geometry.capillary_offset_across_beam` | `Parameter` | 0.0 mm, unbounded | the cos 2θ half, positive toward increasing 2θ |
| `Geometry.mu_r` | `float` or `None` | `None` | µR of the packed specimen, {eq}`corr-rouse`; 0 is off |
| `Geometry.capillary_radius_mm` | `float` or `None` | `None` | the bore radius in mm, used to estimate µR |

A flat plate, `kind="bragg_brentano"` or `kind="flat_plate_transmission"`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `Geometry.sample_displacement` | `Parameter` | 0.0 mm, unbounded | the specimen surface off the goniometer axis, as cos θ, {eq}`pos-displacement` |
| `Geometry.sample_transparency` | `Parameter` | 0.0, at or above 0 | penetration into the specimen, as sin 2θ, {eq}`pos-transparency` |
| `Geometry.mu_t` | `float` or `None` | `None` | µt of the specimen, {eq}`corr-fp2` and {eq}`corr-fp3a` |
| `Geometry.thickness_mm` | `float` or `None` | `None` | the specimen thickness in mm, used to estimate µt |
| `Geometry.surface_roughness` | `RoughnessSuortti`, `RoughnessPitschke` or `None` | `None` | low-angle intensity loss, {eq}`corr-suortti` or {eq}`corr-pitschke`; `bragg_brentano` and X-rays only |

A transmission plate has no displacement or transparency model: only `Instrument.zero_shift` moves its peaks.
No position correction carries a default bound, and the transparency and the axial ratios keep their floor of 0.
Before 1.10, `Instrument.zero_shift` was held to ±0.5°, a displacement and each capillary offset to ±1 mm, and the transparency to 0.05.
Where a scan cannot separate a position error from the cell, the fit reports [`FLAT_DIRECTION`](diagnostics-refinement.md#flat_direction) and the cell's esd grows to show it, with or without a bound.
On 11-BM NAC over 2-24° 2θ with the zero shift and both capillary offsets free, 1.9.0's bounded fit put the cell 1097 ppm from its reference with an esd of 2610 ppm.
The unbounded fit lets the offsets slide to +4.86 and +2.12 mm, puts the cell 5111 ppm away, and reports an esd of 2544 ppm.
Both fits reported the same two `FLAT_DIRECTION` findings.
The bound acted as a prior that the mount is aligned, which held on 11-BM, and it left the esd as wide as before.
That prior is a fact about your instrument, so state a bound yourself where you know the mount.

### Absorption

The absorption coefficients are plain floats rather than parameters, and their off states differ.
A capillary is off at µR = 0.
A flat plate in reflection is off at µt = ∞, and leaving `mu_t` unset states that.
A specimen thicker than the penetration depth needs no correction, because the correction is then exactly degenerate with the scale.
So `mu_t` unset differs from `mu_t = 0`, and `mu_t = 0` under `bragg_brentano` is a specimen of no thickness and raises.
Under transmission, `mu_t = 0` is legal and means a non-absorbing plate.
A transmission plate applies the sec θ growth of its illuminated volume whether or not `mu_t` is set.

µR cannot be refined because it is exactly a combination of the phase scale and the displacement parameters.
µt is ill-conditioned against the same parameters, and the specimen's thickness and composition give it.
[Capillary (cylindrical) absorption](../theory/corrections.md#capillary-cylindrical-absorption) and [flat-plate absorption](../theory/corrections.md#flat-plate-absorption) give the factors.

`estimate_mu_r` computes a starting µR from a structure's composition and the geometry.
An X-ray source reads the McMaster cross-sections.
A `NeutronSource` reads the Sears neutron cross-sections of {eq}`corr-mu-neutron`, which weigh hydrogen and the light elements very differently.
It returns `None` rather than raising when it cannot answer:

- the geometry is not a capillary, or has no capillary radius;
- an element is outside the tabulation, a wavelength straddles an absorption edge, or the energy is outside 2-120 keV;
- a neutron species is missing from the Sears table, or is a resonant absorber (Cd, Sm, Eu, Gd or Yb, refused at every wavelength);
- the source kind has no table, as for a time-of-flight bank.

A refinement does the same calculation when `mu_r` is left `None`, and estimates µt from `thickness_mm` the same way.
A declared `mu_r` or `mu_t` is used on every source.

### Capillary offsets

Both capillary offsets default to zero and fixed.
At a synchrotron with a crystal analyser the displacement error is eliminated, so freeing them is a deliberate act.
Setting or freeing either without `goniometer_radius_mm` is refused, because {eq}`pos-capillary` divides by R.

### Surface roughness

`RoughnessSuortti` and `RoughnessPitschke` model the low-angle intensity a rough flat specimen loses.
Each is exactly no correction at its default values.

| Field | Default | Bounds | Meaning |
|---|---|---|---|
| `RoughnessSuortti.a` | 0.5 | [0, 1] | the intensity fraction that survives at grazing incidence; 1 − a bounds the loss |
| `RoughnessSuortti.b` | 0.0 | [0, 5] | the depleted layer's optical depth; sets where in angle the loss falls |
| `RoughnessPitschke.c` | 0.0 | [0, 4] | the strength; 0 is no correction |
| `RoughnessPitschke.tau` | 0.05 | [0, 0.3] | the dimensionless roughness τ |

`RoughnessSuortti.b` gives the same loss at two values, one on each side of a peak, and past about 3 the correction does nothing.
[`ROUGHNESS_UNCONSTRAINED`](diagnostics-refinement.md#roughness_unconstrained) reports either dead branch.
[`ROUGHNESS_OUTSIDE_REGIME`](diagnostics-refinement.md#roughness_outside_regime) reports a τ above sin θ of the lowest fitted angle.
`RoughnessSuortti.kind` and `RoughnessPitschke.kind` name the model, so a saved instrument comes back as the model it was.

## Peak width

`ProfileTCHZ` is the instrument's contribution to every peak's width.
Its five widths are in degrees 2θ.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `ProfileTCHZ.u` | `Parameter` | 0.0 deg², in [−180², 180²] | Gaussian tan²θ term, {eq}`prof-caglioti-g` |
| `ProfileTCHZ.v` | `Parameter` | 0.0 deg², in [−180², 180²] | Gaussian tan θ term |
| `ProfileTCHZ.w` | `Parameter` | 1e-3 deg², in [1e-8, 180²] | Gaussian constant term |
| `ProfileTCHZ.x` | `Parameter` | 1e-3 deg, in [0, 180] | Lorentzian 1/cos θ term, {eq}`prof-caglioti-l` |
| `ProfileTCHZ.y` | `Parameter` | 0.0 deg, in [−180, 180] | Lorentzian tan θ term |
| `ProfileTCHZ.shape` | `"tchz_pv"` or `"voigt"` | `"tchz_pv"` | the pseudo-Voigt, or the exact convolution |

Match the physics and not the letters.
GSAS and FullProf swap the X and Y assignments, so match a value copied from another program by its angular dependence.
Size broadening goes as 1/cos θ and strain as tan θ.
Swapping them gives a different width function.

`x` is bounded below at 0, because as θ → 0 the Lorentzian width is `x` itself.
`w` stops at 1e-8 deg², the variance under which the Gaussian width is clamped and every width column is zero, {eq}`prof-caglioti-floor`.
A stored `w` bound below that is raised to it when the object is built.
`u`, `v` and `y` have no floor of their own, and each stops at the mirror image of its ceiling.
What has to stay positive is the total Γ<sub>G</sub>² and the total Γ<sub>L</sub> over the measured range, {eq}`prof-lorentzian-floor`.
The default solver holds both at every reflection, and under `solver="trf"` [`RESOLUTION_NOT_POSITIVE`](diagnostics-refinement.md#resolution_not_positive) reports where either fell below.
Read a negative `u`, `v` or `y` as a statement about the fitted resolution curve, and check the width it gives at both ends of the range.

A width is a `Parameter` carrying its own bounds, and a bare number for any width is refused by name.
The message names two ways out: `ProfileTCHZ.coarse(...)`, which builds all five widths from values, or an explicit `Parameter(value, min, max)`.
A `Parameter` that leaves its bounds out takes the default box, and a value outside it is refused.

`shape` is chosen when the model compiles and does not refine.
Both shapes use the same five widths, so switching shape never changes the parameter table.

## Background

Three models describe the curve under the peaks.
The choice is about what the background is allowed to imitate.
[Background](../concepts/parameters.md#background) explains why a background flexible enough to follow the peaks biases the displacement parameters and the scales.

`Instrument.background` is a union discriminated on `kind`.
`BackgroundChebyshev.kind`, `BackgroundPSpline.kind` and `BackgroundFixedPlusChebyshev.kind` make a saved instrument come back as the model it was.

### Chebyshev polynomial

`BackgroundChebyshev` is a shifted Chebyshev polynomial over the fitted range.
`BackgroundChebyshev.coefficients` is a list of parameters, four fixed zeros by default.
`BackgroundChebyshev.with_terms` builds n of them, free.
`rietx.background.select_chebyshev_order` chooses the number of terms for a pattern by BIC.

### P-spline

`BackgroundPSpline` is a cubic spline co-refined with the structure under the second-difference penalty of {eq}`bg-penalty`.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `BackgroundPSpline.breakpoints` | `list[float]` | required | the knots in 2θ, at least two, strictly increasing |
| `BackgroundPSpline.coefficients` | `list[Parameter]` | required | exactly `len(breakpoints) + 2` of them, for the clamped cubic basis |
| `BackgroundPSpline.lambda_smooth` | `float` | 1.0, ≥ 0 | the penalty weight, a pure number against the data's own weight per coefficient |
| `BackgroundPSpline.lambda_units` | `"dimensionless"` or `"intensity"` | `"dimensionless"` | `"intensity"` restores the rows of 1.5 and earlier, whose λ moved with the intensity unit |
| `BackgroundPSpline.air_scatter` | `Parameter` or `None` | `None` | the scale of an additive 1/2θ term for the low-angle air-scatter rise |

One `lambda_smooth` means the same stiffness in counts, in a normalised unit and at any step size.
It does not make the penalty's cost independent of the counts: on a well-counted pattern with a broad hump, the default of 1 can be stiffer than the data supports ([What the pure number leaves to the counts](../theory/background.md#what-the-pure-number-leaves-to-the-counts)).

The air term is absent unless you declare it, for example with `Parameter(value=1e-3, min=0.0)`, or `auto_background` does.
`auto_background` declares it only when the pattern diagnostics report the rise.
Absent, it has no parameter name, so no plan can free it.
A P-spline fit without it reports [`AIR_SCATTER_UNDECLARED`](diagnostics-refinement.md#air_scatter_undeclared) when its own residual says the term would have lowered χ².

`BackgroundPSpline.for_range` builds uniform knots over a 2θ range, about `knot_step_deg` apart (default 5°), with free coefficients and no air term.

```python
from rietx.schemas.instrument import BackgroundPSpline

bkg = BackgroundPSpline.for_range(2.0, 40.0, knot_step_deg=5.0)
assert len(bkg.coefficients) == len(bkg.breakpoints) + 2
```

`auto_background` sizes a model to a pattern.
It takes the knot spacing from the amorphous-hump score, and adds the air term only where the diagnostics ask for it.
With `kind="chebyshev"` it gives a polynomial whose order BIC chose.
It returns a `BackgroundChoice`, which carries the model and the scores each choice was made on.
Assign `BackgroundChoice.background` to `Instrument.background`, as in `ins.background = rx.auto_background(data).background`.
Before 1.10 the call returned the model alone.

| Field | Meaning |
|---|---|
| `BackgroundChoice.background` | the model, a P-spline or a Chebyshev |
| `BackgroundChoice.kind` | `"pspline"` or `"chebyshev"` |
| `BackgroundChoice.amorphous_hump_score`, `BackgroundChoice.hump_trigger` | the score the knot spacing was chosen on, and the trigger above which the knots are 3° apart rather than 8° |
| `BackgroundChoice.knot_step_deg` | the knot spacing chosen, in degrees 2θ |
| `BackgroundChoice.air_scatter_gain`, `BackgroundChoice.air_scatter_trigger` | the score the 1/(2θ) term was chosen on, and the trigger above which it is declared |
| `BackgroundChoice.air_scatter` | whether the model carries the 1/(2θ) term |
| `BackgroundChoice.selection` | the Chebyshev order scan: every order tried, with its BIC and Durbin-Watson d, and whether d reached the stop |
| `BackgroundChoice.seed_level` | the count every coefficient starts at under `seed=True` |

A field the kind made no choice on is `None`: the P-spline fields on a Chebyshev, `selection` on a P-spline, and `seed_level` without `seed=True`.

The order scan is a `BackgroundSelection`, the same object `rietx.background.select_chebyshev_order` returns.

| Field | Meaning |
|---|---|
| `BackgroundSelection.method` | `"chebyshev_order"`, or `"arpls_lambda"` from `rietx.background.select_arpls_lambda` |
| `BackgroundSelection.selected` | the order chosen, the minimum-BIC order of the scan |
| `BackgroundSelection.n_masked_channels` | the background channels the scan scored, after the peaks were masked |
| `BackgroundSelection.scores` | one `CandidateScore` per order tried: `CandidateScore.complexity` (the order), `CandidateScore.bic` and `CandidateScore.durbin_watson` |
| `BackgroundSelection.stopped_by_whiteness` | whether Durbin-Watson d reached the stop, 1.8, and ended the scan |
| `BackgroundSelection.diagnostics` | `BACKGROUND_ORDER_AT_CAP` when the order is the scan's cap rather than a choice |

### Fixed curve plus Chebyshev

`BackgroundFixedPlusChebyshev` holds a fixed curve in the model and refines a polynomial on top of it.
The curve is a measured blank or an estimated baseline.
Holding it in the model keeps the counting statistics intact, where subtracting it would not.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `BackgroundFixedPlusChebyshev.fixed_two_theta` | `list[float]` | required | the curve's 2θ values |
| `BackgroundFixedPlusChebyshev.fixed_intensity` | `list[float]` | required | the curve, one value per 2θ |
| `BackgroundFixedPlusChebyshev.fixed_sigma` | `list[float]` or `None` | `None` | the curve's own esds, non-negative; `None` claims nothing |
| `BackgroundFixedPlusChebyshev.fixed_source` | `str` or `None` | `None` | where the curve came from, free text |
| `BackgroundFixedPlusChebyshev.scale` | `Parameter` | 1.0, fixed, ≥ 0 | a multiplier on the curve as stored |
| `BackgroundFixedPlusChebyshev.chebyshev` | `BackgroundChebyshev` | four fixed terms | the refinable polynomial on top |

`BackgroundFixedPlusChebyshev.from_pattern` builds the model from a blank read with `read_pattern`.
It takes `n_terms` (default 4, free), `vary_scale` (default `False`), `scale` (default 1.0) and `source`.
It carries the blank's own σ where the file had one, and leaves out channels in the blank's own excluded regions.
[How to use a measured blank as the background](../guides/blank.md) is the procedure.

With `fixed_sigma` set, each channel's weight becomes σ² + s²·σ<sub>f</sub>², with s the scale, {eq}`bg-measured-weight`.
The weight then depends on the scale, so Rwp is not comparable between fits that declare different scales.
Compare a scan of scales under one σ.

`fixed_source` separates a measurement from an estimate for anything that reads the model back.
The CIF export calls the background measured only when it is set.

A scale at its floor of 0 comes back as [`FLOOR_HIT`](diagnostics-refinement.md#floor_hit).
A fitted channel outside the curve's 2θ range, by more than about one of its steps, is refused, naming both ranges.
Crop the fit range, or supply a curve that covers it.
A curve of fewer than two points, or one whose 2θ values decrease, is refused when the model compiles.

## Extra components

`Instrument.extra_components` is a list of declared peaks, each added on top of whichever background model is in use.
It composes with all three models and leaves their design matrix untouched.
The empty default is off.

The list's type is a union with two members, discriminated on `HumpComponent.kind` and `PeakComponent.kind`.

| Member | `kind` | For | Guide |
|---|---|---|---|
| `HumpComponent` | `"hump"` | a broad Gaussian, for scattering with no Bragg peaks behind it | [How to add a hump to the background](../guides/hump.md) |
| `PeakComponent` | `"peak"` | a sharp pseudo-Voigt that no phase explains, such as a sample holder's line | [How to fit a peak from the sample holder](../guides/holder.md) |

Ask a version which members it has:

```python
import rietx as rx

caps = rx.capabilities()
print(caps.features["extra_components"], caps.extra_component_kinds)
```

```text
True ['hump', 'peak']
```

`Capabilities.extra_component_kinds` is read from the union itself, so it cannot miss a member.

A component is a declaration and never code.
It is stored state, so it survives a save, a history checkout and a replay like any other field.
A member holding an expression over this package's own parameter names would fit the seam, because text serialises and both traced backends differentiate an expression tree.
A member holding a Python function would not fit, because it does not serialise, it does not trace, and it has no JSON form.
No expression member exists yet.

| Field | Default | Bounds | Meaning |
|---|---|---|---|
| `HumpComponent.position` | 0.0 deg | none | the hump's apparent 2θ |
| `HumpComponent.height` | 0.0 counts | ≥ 0 | its peak value; 0 is off |
| `HumpComponent.fwhm` | 5.0 deg | ≥ `HUMP_FWHM_MIN` (0.1°) | its width in 2θ |
| `HumpComponent.label` | `None` | | free text, never part of a parameter's name |
| `PeakComponent.center` | 0.0 deg | finite `min` and `max` required | the line's apparent 2θ for the primary emission line |
| `PeakComponent.area` | 0.0 counts·deg | ≥ 0 | the integrated intensity; 0 is off |
| `PeakComponent.fwhm` | 0.1 deg | [0.005, 0.5] by default; finite bounds required | the width in 2θ |
| `PeakComponent.eta` | 0.5 | [0, 1] | the Lorentzian fraction of the pseudo-Voigt |
| `PeakComponent.all_lines` | `True` | | place an image of the line at every emission line |
| `PeakComponent.label` | `None` | | free text, never part of a parameter's name |

A hump's position has no bound, because it is not a Bragg position and the fitted range belongs to the pattern rather than the instrument.
A peak's `center` and `fwhm` need finite bounds, because they size the window the peak is evaluated over, frozen when a stage compiles.
The window spans the centre's bounds and reaches out by a multiple of `fwhm.max` that grows with `eta.max`, about 16 at η = 1.
At the default `fwhm.max` of 0.5° that is about ±8°, so state the bounds you believe.
A window holding no fitted channel is refused, naming the peak.
With `all_lines` set, each emission line's image is scaled by that line's weight times the ratio of its Lorentz-polarisation factor to the primary line's, so `area` is the primary line's area.
A declared peak adds no reflections, so it leaves the observation count `effective_observations` unchanged.
A width bound at 0 is raised to the member's floor when the object is built, because each profile divides by its width.

Every refinable field defaults to fixed, so a declared component is inert until a stage frees it.
A height or area of 0 gives the same pattern as no component at all.
The parameters are named by place in the list, as `instrument.extra_components.0.position` is the first component's position, so a new label never moves a refined value.
Most presets free `instrument.background.*` in their first stage, and that pattern does not reach them.
`mccusker_structural` frees declared components in its `extra_components` stage, and nothing in the package adds one.
`save_instrument_profile` leaves them out, because a component belongs to the specimen and its holder.

A hump that refines narrower than {{ HUMP_MIN_WIDTH_MULT }} times the instrumental width at its position raises [`HUMP_TOO_NARROW`](diagnostics-refinement.md#hump_too_narrow).
At that width it is a reflection with no cell behind it, and its parameters cannot be quoted.

:::{note}
Before 1.4.0 the field was `background_peaks` and the class `BackgroundPeak`.
A project, history tree or `.rxt` written then still opens, and its saved plan still frees the hump it froze.
The stored parameter names are migrated on read as well as the values, because a value under a vanished name fails loudly while a pattern under one quietly stops matching.
Code that assigns the old attribute raises.
:::
