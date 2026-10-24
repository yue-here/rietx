# Coming from GSAS-II

This page says how a GSAS-II refinement maps onto a rietx one, and how to move instrument files, phases and the older GSAS experiment files across.

## What is the same

GSAS-II and rietx fit the same model by least squares: a calculated pattern from the phases, the instrument and the background, weighted by the esds of the observed counts.
Both can run a Le Bail fit before the Rietveld fit.

The comparisons with GSAS-II are on [two cathode phases](validation.md#two-phases-against-topas-and-gsas-ii), where GSAS-II is one of two reference codes, and on [spherical-harmonic texture](validation.md#spherical-harmonic-texture-against-gsas-ii), where rietx's functions match GSAS-II 5.8.4's within 2×10<sup>−6</sup>.
The fluorapatite comparison uses `FAP.EXP`, which is GSAS's converged fit of the data from the GSAS-II `LabData` tutorial.
It is on the [validation page](validation.md#fluorapatite-against-gsas).

## Differences in concepts

### The plan sets the flags

In GSAS-II a refine flag stays as you set it, and a recipe such as `do_refinements` sets some and runs a refinement.
In rietx the plan decides which parameters refine in each stage.
A flag set by hand before `fit` is replaced by the plan's.
`Refinement.hold` keeps a parameter fixed through every stage, as a cleared flag does in GSAS-II.

This GSAS-II recipe frees the background and scale, then the cell and zero, then the profile, then the atoms.
It uses the keys of the `GSASIIscriptable` module in GSAS-II 5.8.4, and it has not been run for this page:

<!-- api-doc: no-exec — GSAS-II's own scripting API, which this build does not import -->
```python
gpx.do_refinements([
    {"set": {"Background": {"no. coeffs": 6, "refine": True},
             "Sample Parameters": ["Scale"]}},
    {"set": {"Cell": True, "Instrument Parameters": ["Zero"]}},
    {"set": {"Instrument Parameters": ["U", "V", "W", "X", "Y"]}},
    {"set": {"Atoms": {"all": "XU"}}},
])
```

The same four steps in rietx are a `RefinementPlan` of four `Stage` objects:

<!-- api-doc: no-exec — fits fluorapatite, so examples/switching.py runs it and asserts the output below -->
```python
import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.geometry.axial_sl.value = 0.02
instrument.geometry.axial_hl.value = 0.02
instrument.background = rx.BackgroundChebyshev.with_terms(6)
ref = rx.Refinement(structure, instrument)

plan = rx.RefinementPlan(stages=[
    rx.Stage("background", turn_on=["instrument.background.*", "phases.*.scale"]),
    rx.Stage("cell", turn_on=["instrument.zero_shift", "phases.*.cell.*"]),
    rx.Stage("profile", turn_on=["instrument.profile.*"]),
    rx.Stage("atoms", turn_on=["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso"]),
])
result = ref.fit(data, plan=plan, two_theta_limits=(15, 130))
```

```text
>>> result.status, round(result.statistics.rwp, 4)
('converged', 0.0898)
>>> [(s.name, len(s.freed)) for s in result.stages]
[('background', 7), ('cell', 3), ('profile', 5), ('atoms', 19), ('closing', 34)]
```

The two axial-divergence terms are set by hand, where an `.instprm` would supply `SH/L`.
This plan frees U, V and W, which the [validation protocol](validation.md#fluorapatite-against-gsas) holds at GSAS's values, so its Rwp differs from the one quoted there.

A name in `turn_on` is a parameter path, and `*` stands for any text at that place.
`phases.*.cell.*` is every lattice parameter of every phase.
Staging is cumulative, so the cell stays free in the profile and atom stages.
The fit ends with a closing stage, which frees all 34 parameters again with wider peak windows ([The closing stage](../reference/refinement.md#the-closing-stage)).
[About a fit](../concepts/fit.md#the-plan) describes the stages, and the [plan presets](../reference/plans.md) draw the ones rietx ships.

### A project is a directory

A GSAS-II project is one `.gpx` file, a Python pickle.
A rietx project is a `.rex` directory holding a settings file, the pattern as it was read, and a log of every stage as a node.
The log is appended to and never rewritten, so a crash leaves the history up to the last stage.
[About the project](../concepts/project.md) says what each file is for.

GSAS-II keeps phases, histograms and the pairing of each phase with each histogram in one tree.
rietx's `Refinement` holds the phases and one instrument, and fits one pattern at a time.
Several patterns of one specimen go in `MultiHistogramRefinement`, with the structure shared and each pattern keeping its own instrument, wavelength and background.
A joint fit shares the crystallite size and scales each pattern's width in degrees by its wavelength.
The [joint fit](validation.md#one-specimen-two-radiations) of a synchrotron and a neutron pattern agrees with the published refinement of the same data.

### The width coefficients have other units

GSAS-II states U, V and W as a Gaussian variance in centidegrees², and X and Y in centidegrees.
rietx states U, V and W as the Gaussian FWHM² in degrees², and X and Y in degrees.
rietx's U is GSAS-II's times 8 ln 2 × 10<sup>−4</sup>, and its X and Y are GSAS-II's divided by 100.
Writing the instrument from the four-stage fit above shows the conversion.
These are lines of the file, without its comment line and the lines after `Y`, with each number cut to six significant figures:

<!-- api-doc: no-exec — needs a fitted Refinement and writes a file; examples/switching.py runs it and asserts these lines -->
```python
rx.write_gsas2_instprm(ref.fitted_instrument, "refined.instprm")
```

```text
Type:PXC
Lam1:1.54059
Lam2:1.54443
Zero:-0.0365586
I(L2)/I(L1):0.5
Polariz.:0.5
U:-1.57826
V:2.76475
W:2.37759
X:2.68762
Y:4.11637
```

The `.instprm` states U = −1.57826 centidegrees², and rietx's own value is −0.000875173 degrees².
`rx.read_gsas2_instprm` reads the file back and converts.

GSAS-II states one axial divergence, `SH/L`, as the sum of the specimen and detector terms.
rietx has two, `axial_sl` and `axial_hl`.
Reading a file splits `SH/L` evenly between them, and writing sums them.
[Names in other programs](../reference/foreign-names.md) lists the rest, among them Uiso against B = 8π²·Uiso, and the GSAS-II polarisation against rietx's K.

### A hump is a declared component

GSAS-II calls a hump a background peak.
rietx keeps a hump in `Instrument.extra_components`, apart from the background curve, so that a stage freeing the background does not free the hump.
It never adds one on its own.
[About parameters](../concepts/parameters.md#humps) says how wide a hump may refine before it is a peak with no cell behind it.

### Le Bail is a mode

GSAS-II's `LeBail` flag on a phase and rietx's `fit(mode="lebail")` do the same job.
`mode="pawley"` refines each reflection's intensity as a parameter and fixes the atoms.
The atoms and the phase scale are fixed in both modes, and no other code was compared with these two.

### An esd carries a correlation factor

rietx multiplies every esd by the Bérar-Lelann factor for serially correlated residuals, and GSAS-II does not.
`RefinedParameter.stderr_uncorrected` is rietx's esd without the factor, so compare a GSAS-II esd with it.
On the fluorapatite pattern of the `LabData` tutorial the factor is 2.17, so `stderr` is about twice `stderr_uncorrected` there.
[Estimation](../theory/estimation.md#esds-and-the-bérar-lelann-inflation) says why rietx applies the factor and what each program reports.

## Moving files across

### An instrument file

`rx.read_gsas2_instprm` and `rx.write_gsas2_instprm` read and write a GSAS-II `.instprm`.
`rx.read_gsas_prm` and `rx.write_gsas_prm` do the same for the older GSAS `.prm`.

### A phase

`rx.read_project_model` opens a `.gpx` by its content, and `to_structure` builds the structure from the cell, the atoms and their displacement parameters.
The reader builds a `Structure` alone, so the instrument comes from the `.instprm`.
The reader refuses any name in the pickle that it does not recognise, and never runs one.
There is no writer for a `.gpx`.
`rx.write_gsas2_phase_cif` writes a phase as a CIF that GSAS-II's import reads, and refuses a phase with a magnetic moment or a propagation vector, because GSAS-II would drop it without a warning.

### A GSAS experiment file

GSAS's `.EXP` states a whole experiment, including which parameters the run freed.
`read_project_model` opens one:

<!-- api-doc: no-exec — reads FAP.EXP from the working directory; examples/switching.py reads the shipped copy and asserts the output -->
```python
model = rx.read_project_model("FAP.EXP")
ref = rx.Refinement(model.to_structure(), rx.Instrument.bragg_brentano(radiation="CuKa"))
free = [row.path for row in ref.parameters() if row.vary]
```

```text
>>> model.format.name, model.stated.rwp, model.stated.rp
('gsas_exp', 0.1005, 0.0766)
>>> model.stated.n_variables, model.stated.n_observations
(28, 5750)
>>> model.stated.profile().refined_names
('LX', 'LY', 'shft')
>>> len(free)
21
>>> for d in model.diagnostics: print(d.code, "|", d.message)
GSAS_EXP_BACKGROUND_NOT_CARRIED | FAP.EXP: histogram 1 fitted GSAS background function 5 (reciprocal expansion in Q², for low-angle air scatter) with 3 terms. The coefficients are on model.histograms[...].background.
```

The structure carries 21 of the 28 variables: 2 cell parameters, 12 coordinate directions and 7 displacement parameters.
The other seven are the histogram's scale, three background terms and three profile terms, which belong to the instrument and the pattern.
The read reports the background function it did not carry, with its terms, so that you can set an equivalent background.

GSAS's profile coefficients are in centidegrees, and `GsasProfileTerm.degrees` gives them in degrees.
Which names a profile has depends on its function, and a function the build cannot name is refused rather than read by position.
