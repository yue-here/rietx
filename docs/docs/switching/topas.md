# Coming from TOPAS

This page says how a TOPAS refinement maps onto a rietx one: what is the same, what works differently, and how to move a file across.

## What is the same

rietx fits the same model as TOPAS: a calculated pattern from the structure, the instrument and the background, refined by least squares against the observed counts.
A TOPAS `.inp` holds a structure, an instrument, a background and the refine flags.
rietx holds the same four things in a `Structure`, an `Instrument`, a background and the `vary` flag of each parameter.
The weights are the same too.
rietx uses the esd column of the pattern file when it has one, as `weighting = 1 / SigmaYobs^2;` does, and counting statistics (√y) when it does not.

The comparisons on [LaB6 and cBN](validation.md#lab6-and-cbn-against-topas) and on [two cathode phases](validation.md#two-phases-against-topas-and-gsas-ii) are against TOPAS.
The cBN cell agrees to 17 ppm, and the cathode's cells to within 96 ppm.
[Calculated patterns](validation.md#calculated-patterns-against-topas-6) compares rietx with the pattern TOPAS 6 calculated for seven inputs.

## Differences in concepts

### A name is the flag in TOPAS, and a stage is in rietx

TOPAS refines whatever carries a name or an `@`, all at once, until `chi2_convergence_criteria` is met.
rietx refines in stages.
A plan frees one group of parameters, converges, and then frees the next, in the order McCusker *et al.* (1999) recommend: background and scale, then cell and peak widths, then atoms.
`mccusker_structural` is one such plan.

A plan replaces the `vary` flags at each stage.
A parameter you set to `vary = False` is freed again by the first stage that names it.
`Refinement.hold` is the equivalent of TOPAS's `!`.
It keeps a parameter at its value through every stage.

:::{admonition} Differs from TOPAS
:class: warning
In TOPAS, `th2_offset ! 0` keeps the zero shift at 0.
In rietx, setting the value and `vary = False` does not, because a plan can free it.
Use `set_values` and then `hold`.
:::

```text
th2_offset ! 0
```

<!-- api-doc: no-exec — a fragment of a refinement that examples/switching.py runs, with its HOLD_BLOCKED_PLAN asserted -->
```python
ref.set_values({"instrument.zero_shift": 0.0})
ref.hold(["instrument.zero_shift"])
```

A stage that tried to free a held parameter reports it as `HOLD_BLOCKED_PLAN`, and the fit goes on.

### Shared names are ties

TOPAS ties parameters by giving them one name, or by writing an equation.
rietx has three calls for the same jobs:

| TOPAS | rietx |
| --- | --- |
| one name on several sites: `beq O5_biso` | `Refinement.tie_equal` |
| an equation: `b = 2*a + 1;` | `Refinement.tie(path, source, scale=2, offset=1)` |
| a named parameter: `prm w 0.1` | `Refinement.add_variable` |

The three oxygen sites of fluorapatite share one displacement parameter in TOPAS like this (lines from a file rietx wrote, with each number cut to six significant figures):

```text
site O5 x O5_x 0.32467 y O5_y 0.484898 z ! 0.25 occ O ! 1.0 beq O5_biso 0.366488
site O6 x O6_x 0.591092 y O6_y 0.469105 z ! 0.25 occ O ! 1.0 beq O5_biso 0.366488
site O7 x O7_x 0.339828 y O7_y 0.257684 z O7_z 0.0705402 occ O ! 1.0 beq O5_biso 0.366488
```

In rietx it is one call:

<!-- api-doc: no-exec — a fragment of a refinement that examples/switching.py runs and checks against the file it writes -->
```python
ref.tie_equal(["phases.0.atoms.4.biso", "phases.0.atoms.5.biso", "phases.0.atoms.6.biso"])
```

The space group ties the lattice parameters in both programs.
A tie you declare never overrides a tie the symmetry sets.

### Coordinates are refined along the symmetry directions

TOPAS flags each of `x`, `y` and `z`.
rietx refines one `dof` for each direction the site symmetry allows, and the coordinates follow from them.
Fluorapatite's O7 is on a general position, so it has three, as `phases.0.atoms.6.dof.0` to `phases.0.atoms.6.dof.2`.
Flagging `z` on its own frees all three.
An atom on a mirror plane has two directions, and one on a three-fold axis has one.
The [parameterisation chapter](../theory/parameterisation.md#site-symmetry-degrees-of-freedom) derives the directions.

### The peak shape is the instrument plus the sample

TOPAS offers many peak types and macros, and its fundamental-parameters approach builds the shape from the instrument's dimensions.
rietx offers a pseudo-Voigt (TCHZ) and a true Voigt, and it has neither a Pearson VII nor a fundamental-parameters shape.
On LaB6 at APS 11-BM, TOPAS's Pearson VII reached Rwp 0.0810 and rietx's pseudo-Voigt 0.1687.
The [validation page](validation.md#lab6-and-cbn-against-topas) gives the cause and what it did to the phase fractions.

rietx separates the instrument's width from the sample's.
The instrument carries Caglioti U, V and W and the Lorentzian X and Y.
Each phase carries its own size and strain terms, which add to the instrument's.
Calibrate the instrument on a standard with its certified cell held, save it, and load it for each sample.
The `lab_calibrate` and `lab_sample_refine` plans do the two halves.
[About parameters](../concepts/parameters.md#instrument-and-specimen) explains the split.

TOPAS's `CS_L` and `Strain_L` macros state a size and a strain.
rietx reads neither from a file, and says so when it meets one.
`gauss_size`, `lor_size`, `gauss_strain` and `lor_strain` are the terms to set by hand.

### The scale is not TOPAS's scale

A rietx phase scale and a TOPAS scale differ by a convention.
For X-rays TOPAS's value is rietx's times K, the polarisation constant, because `LP_Factor` states its own.
For constant-wavelength neutrons it is 100 times rietx's, because TOPAS states |F|² in barn and rietx in fm².
The neutron constant was measured against TOPAS 6.
`write_topas_inp(..., scale="topas")` and `to_structure(scale="rietx")` convert, and a file that states neither radiation is refused rather than guessed.

### An esd carries a correlation factor

rietx multiplies every esd by the Bérar-Lelann factor for serially correlated residuals.
The TOPAS Technical Reference (Version 9) describes no such factor for `do_errors` or `bootstrap_errors`.
So compare a TOPAS esd with `RefinedParameter.stderr_uncorrected`, which is rietx's esd without the factor.
[Estimation](../theory/estimation.md#esds-and-the-bérar-lelann-inflation) says why rietx applies it and how large it gets.

### Rwp is for looking, and the report is for judging

TOPAS reports `r_wp` and `gof` as the figures of merit.
rietx reports them too, as `result.statistics.rwp` and `result.statistics.gof`.
It does not use an Rwp comparison as evidence for a correction, because some corrections cannot move it and one moves it the wrong way when it is right.
The [report](../concepts/report.md) says where the pattern is misfit and what the misfit looks like, and the diagnostics name a parameter on a bound or two the data cannot separate.

## Moving a file across

### Reading an `.inp`

`read_project_model` opens a TOPAS `.inp` by its content, whatever its extension.
The structure comes with the file's refine flags and its constraints:

<!-- api-doc: no-exec — needs a refined.inp on disk; examples/switching.py writes one, runs this and asserts the output -->
```python
import rietx as rx
from rietx.io.projects.topas_ties import TopasConstraints, apply_ties

model = rx.read_project_model("refined.inp")
cons = TopasConstraints()
structure = model.to_structure(scale="rietx", constraints=cons)
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
ref = rx.Refinement(structure, instrument)
apply_ties(ref, cons)
```

```text
>>> model.format.name
'topas_inp'
>>> model.stated.data_files
['refined.xye']
>>> model.stated.background_terms, model.stated.background_refined
(6, True)
>>> [r.path for r in ref.parameters() if r.vary][:4]
['phases.0.cell.a', 'phases.0.cell.c', 'phases.0.scale', 'phases.0.extinction']
```

The reader builds a `Structure` alone.
The wavelength, the emission lines, the background terms and the data file it finds are on `model.stated`, so you can build the `Instrument` to match.
Both calls that read a file take a `diagnostics=` list, and the reader says what it did not carry:

```text
TOPAS_FEATURES_NOT_IMPORTED | refined.inp: this import is partial. The file states peak profile (Finger_et_al, peak_type, pv_fwhm, pv_lor) [fluorapatite]; phase scaling (scale_pks) [fluorapatite], and none of it reaches the built structure.
```

A construct the reader cannot carry without misrepresenting the file is refused by name.
A rigid body, `occ_merge`, a stacking-fault phase and a time-of-flight dataset are refused, because the numbers read back fine and the model would be wrong.
[Names in other programs](../reference/foreign-names.md) maps each rietx parameter to its TOPAS name and gives the unit conversions.

### Writing an `.inp`

`write_topas_inp` writes a file TOPAS runs as it stands.
After a fit, pass the refinement as `free=` so that the file states the refined set and the ties, since a plan leaves the structure's own flags as the input had them:

<!-- api-doc: no-exec — needs a fitted Refinement and writes a file; examples/switching.py runs it -->
```python
rx.write_topas_inp(ref.fitted_structure, "refined.inp", free=ref, scale="topas",
                   instrument=ref.fitted_instrument, pattern=data)
```

The file names each free parameter after its path, which in TOPAS is also its refine flag.
This file comes from the refinement above that held the zero shift at 0.
It holds the zero shift with `!`, and states the specimen displacement that took its place as an equation in `th2_offset`.
The held zero also moves the cell: the same fit with the zero free gives a = 9.37228 Å, 111 ppm lower.
These lines are an excerpt, with each number cut to six significant figures:

```text
xdd "refined.xye" xye_format
  weighting = 1 / SigmaYobs^2;
  bkg @ 152.446 -171.263 124.821 -73.5215 36.6909 -16.1333
  th2_offset ! 0
  th2_offset = -2*Rad*(0.0629551)*Cos(Th)/217.5;
str
  scale p0_scale 0.000469265 min 0
  a p0_cell_a 9.37332
  b p0_cell_a 9.37332
```

The data go beside it as `refined.xye`, with the esd rietx weights by.
rietx's calculated pattern matched TOPAS 6's to within 0.26 % of the largest intensity on four whole inputs.
TOPAS integrates whole Lorentzian tails and rietx's windows keep 98 % of a peak's area.

## Where the two codes name the same thing differently

| TOPAS | rietx |
| --- | --- |
| `xdd` | `rx.read_pattern` |
| `lam`, `la`, `lo`, `lh` | `instrument.source.lines.*` |
| `bkg` | `BackgroundChebyshev` |
| `th2_offset` | `instrument.zero_shift`, `instrument.geometry.sample_displacement` |
| `Finger_et_al` | `instrument.geometry.axial_sl`, `axial_hl` |
| `scale` | `phases.*.scale` |
| `beq` | `phases.*.atoms.*.biso` |
| `r_wp`, `gof` | `RefinementResult.statistics` |
