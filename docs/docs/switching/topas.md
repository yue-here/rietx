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
rietx has three calls for the same jobs, `tie` taking either a source or an expression:

| TOPAS | rietx |
| --- | --- |
| one name on several sites: `beq O5_biso` | `Refinement.tie_equal` |
| an equation: `b = 2*a + 1;` | `Refinement.tie(path, source, scale=2, offset=1)` |
| a nonlinear equation in named parameters: `beq = B0 * Exp(-k/T);` | `Refinement.tie(path, expression="B0 * exp(-k/T)")`, with `B0` and `k` from `add_variable` and `T` a number |
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

### A parametric equation is a formula

TOPAS refines a series of files in one input by giving them a shared `prm` and writing each cell edge as an equation in it.
rietx writes the same thing as a joint fit with a formula equation ([Parametric refinement](../reference/parametric.md#formula-equations)).
The formula's text follows [Expressions](../reference/expressions.md), which takes python's lowercase function names.
Each line of a TOPAS parametric input has its rietx spelling:

| TOPAS | rietx |
| --- | --- |
| `#list Files T_val` and one `xdd` per file | one pattern per file, and `rx.CoordinateTable(columns={"T": [...]})` in the same order |
| `prm zero_a 4.1566` | `variables={"zero_a": rx.Parameter(value=4.1566, vary=True)}` |
| `prm !theta 125.37` | `rx.Parameter(value=125.37)`, which `vary=False` holds |
| `prm !theta_b = theta_a;` | the name `theta_a` in both formulas, which is one refined number |
| `a = zero_a + grad_a/(Exp(theta_a/T) - 1);` | `rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="expression", expression="zero_a + grad_a/(exp(theta_a/T) - 1)")` |
| `Exp`, `Ln`, `Sqrt`, `ArcTan` | `exp`, `log`, `sqrt`, `atan` |
| `local dT 0` read by each phase's cell equation | `variables={"dT": rx.Parameter(value=0.0, vary=True)}` with `rx.SharingMap(per_histogram=["vars.dT"])` |
| `prm !calib = T + b*(T - 738)/369;` read by the cell equations | `rx.ParametricEquation(name="calib", target=None, basis="expression", expression="T + b*(T - 738)/369")`, declared before the formulas that name `calib` |
| `min` and `max` on a `prm` | `rx.Parameter(min=..., max=...)` |
| `for xdds { ... }`, with `existing_prm i += 1;` and `#T_val(i)` | a python loop over the files, with each file's `T` at the same row of the coordinate table |
| `#define`, `#ifdef` and `macro` | no equivalent: write out what they expand to, or a python function that builds the repeated part |
| `fn cell_fT(a0, grad, theta, te) = a0 + grad/(Exp(theta/te) - 1);` | no equivalent: write the body into each formula with the arguments substituted, or build the text with a python function |
| a phase's parameter under one name in every `xdd`, such as its `Strain_L` term or a coordinate | nothing: every pattern shares a phase's parameters unless `SharingMap.per_histogram` names them |
| `TCHZ_Peak_Type` on a phase | the phase's `gauss_strain` for the Gaussian tan²θ term U, `gauss_size` for the Gaussian 1/cos²θ term Z, `lor_strain` for the Lorentzian tanθ term X and `lor_size` for the Lorentzian 1/cosθ term Y. A phase's own V and W have no spelling, because rietx's V and W belong to the instrument. |
| `local height` and `th2_offset = -2 57.2957795 (height) Cos(Th) / Rs;` | `instrument.geometry.sample_displacement`, in mm with the same sign, one per pattern. This is TOPAS's `Specimen_Displacement` written out, and the instrument's `goniometer_radius_mm` takes the place of `Rs`. |
| `local` on a phase's parameter, such as each temperature's `beq` | `rx.SharingMap(per_histogram=["phases.0.atoms.0.biso"])` |
| `local` on a scale, a `bkg` term, `th2_offset` or a specimen height | nothing: each phase scale, and every parameter under `instrument.`, is one per pattern already |
| an instrument term under one name in every `xdd` | `rx.SharingMap(shared=["instrument.zero_shift"])` |
| `Specimen_Displacement(h_si, =h_zrp2o7;)`, one height for every phase of a pattern | nothing: every phase of a pattern reads its `instrument.geometry.sample_displacement` |
| `!` on a coordinate the site symmetry leaves free, such as `x !x_O1 0.3064` | a `PlanSpec` stage with `turn_off=["phases.2.atoms.1.dof.*"]` (below) |
| one B per pattern for every site: `local b` and `scale_pks = Exp(-2*b/(2 D_spacing)^2);` | a formula on each site's `biso` adding a per-pattern variable `b` (below) |
| `be = b0*(1 + b1*1e-6*te + b2*1e-9*te^2);` on a monoclinic cell | a formula on `phases.0.cell.beta`, in degrees |
| `a0 (1 + ax1 (T - 273))`, a product written with a space | `a0*(1 + ax1*(T - 273))`: a name before a parenthesis reads as a function call, and the formula is refused as an unknown function |
| `range 3` of a multi-range RAW file | `rx.read_pattern(path, scan=2)`, since `scan` counts from 0 |
| `Get(r_wp)`, `Out(Get(a), ...)` and `MVW(...)` | `result.histograms[h].statistics`, the rows of `result.parameters` (a per-pattern row is `hist.<h>.<path>`), and `result.histograms[h].qpa` |
| `val_on_continue = Val*Rand(0.99, 1.01);` | no equivalent: rietx refines once from its starting values, so a python loop over starting values repeats the fit |
| `load_save_locals` or `use_stored_values`, which start each value from the last run's | no equivalent: a joint fit starts from the values its models carry |

A formula is evaluated in radians, and `pi` is the constant.
`MultiHistogramRefinement.preview_equations` evaluates every formula at its starting values before any fit.
Comparing that with the cells a TOPAS input stores checks a port line by line.

TOPAS's `scale_pks` factor exp(−2b/(2d)²) is the Debye-Waller factor on the intensity, exp(−2bs²) with s = 1/(2d).
Adding `b` to every site's B gives each reflection the same factor.
A joint fit has no `hold` yet, so a stage's `turn_off` keeps a parameter fixed.
A plan frees an equation's coefficients only where one of its stages reaches the target.
`mccusker_default` frees no coordinate and no B, so a port that refines them names them in its own stages:

```python
import rietx as rx
from rietx.schemas.plan import PlanSpec, StageSpec

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0), y=rx.Parameter(value=0.0),
                   z=rx.Parameter(value=0.0), biso=rx.Parameter(value=0.25)),
           rx.Atom(label="B", species="B", x=rx.Parameter(value=0.1975), y=rx.Parameter(value=0.5),
                   z=rx.Parameter(value=0.5), biso=rx.Parameter(value=0.40))],
)])
temperatures = [300.0, 450.0, 600.0, 750.0, 900.0]
instruments = [rx.Instrument.debye_scherrer(wavelength=0.4139) for _ in temperatures]

overall_b = [
    rx.ParametricEquation(name="b_la", target="phases.0.atoms.0.biso", basis="expression",
                          expression="0.25 + b"),
    rx.ParametricEquation(name="b_b", target="phases.0.atoms.1.biso", basis="expression",
                          expression="0.40 + b"),
]
joint = rx.MultiHistogramRefinement(
    lab6, instruments, coordinates=rx.CoordinateTable(columns={"T": temperatures}),
    variables={"b": rx.Parameter(value=0.0, vary=True, min=-1.0, max=10.0)},
    parametric=overall_b, sharing=rx.SharingMap(per_histogram=["vars.b"]))
plan = PlanSpec(stages=[
    StageSpec(name="scale_bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
    StageSpec(name="cell", turn_on=["phases.*.cell.*", "instrument.zero_shift"]),
    StageSpec(name="atoms", turn_on=["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso"],
              turn_off=["phases.0.atoms.1.dof.*"]),
])
print([row.path for row in joint.parameters() if row.path.endswith("vars.b")])
```

```text
['hist.0.vars.b', 'hist.1.vars.b', 'hist.2.vars.b', 'hist.3.vars.b', 'hist.4.vars.b']
```

`joint.fit(patterns, plan=plan)` then refines one `b` per pattern and keeps the boron coordinate where it started.

Four things a TOPAS input does have no rietx spelling yet:

- A command that holds, ties or sets a joint fit's parameters. `hold`, `tie` and `set_values` take a single refinement only. The `turn_off` stage above holds, and one formula variable read by several targets ties them.
- A restraint or a `penalty` in a joint fit, which refuses soft restraints.
- An equation over a reflection or a point: `th2_offset` written in `Xo`, a phase's own TCHZ V and W, or a width, position or intensity written in `Th` or `D_spacing`. An overall B and a height written in `Cos(Th)` are the exceptions, through the rows above.
- `fit_obj`, a term added to the calculated pattern.

### Coordinates are refined along the symmetry directions

TOPAS flags each of `x`, `y` and `z`.
rietx refines one `dof` for each direction the site symmetry allows, and the coordinates follow from them.
Fluorapatite's O7 is on a general position, so it has three, as `phases.0.atoms.6.dof.0` to `phases.0.atoms.6.dof.2`.
Flagging `z` on its own frees all three.
An atom on a mirror plane has two directions, and one on a three-fold axis has one.
The [parameterisation chapter](../theory/parameterisation.md#site-symmetry-degrees-of-freedom) derives the directions.

### A Z-matrix body refines its internals

TOPAS refines every `z_matrix` parameter of a rigid body.
In rietx a body built from a Z-matrix does too: `RigidBody.zmatrix` lists one `ZLine` per atom, and each line's `r` (Å), `angle` and `dihedral` (degrees) is a parameter with an esd.
Build one with `rietx.crystallography.bodies.add_body` and its `zmatrix` keyword, or over atoms already placed with `rietx.crystallography.bodies.zmatrix_body_from_atoms`, whose spanning tree you declare.
The template is measured from a point frozen when the body is declared, so a stretched bond moves only the atoms it reaches.
In a ring, a free tree bond also moves the bond that closes the ring.
A dihedral is kept in (−180°, 180°], and a series compares the ones in `SeriesResult.dihedral_paths` modulo 360°.

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
TOPAS's `Strain_L(e)` adds a Lorentzian FWHM e·tanθ, so `lor_strain` is e.
Its `Strain_G(e)` adds a Gaussian FWHM e·tanθ, and rietx states the Gaussian FWHM², so `gauss_strain` is e².

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
['phases.0.cell.a', 'phases.0.cell.c', 'phases.0.scale', 'phases.0.atoms.0.dof.0']
```

The reader builds a `Structure` alone.
The wavelength, the emission lines, the background terms and the data file it finds are on `model.stated`, so you can build the `Instrument` to match.
Both calls that read a file take a `diagnostics=` list, and the reader says what it did not carry:

```text
TOPAS_FEATURES_NOT_IMPORTED | refined.inp: this import is partial. The file states peak profile (Finger_et_al, peak_type, pv_fwhm, pv_lor) [fluorapatite], and none of it reaches the built structure.
```

A construct the reader cannot carry without misrepresenting the file is refused by name.
A rigid body, `occ_merge`, a stacking-fault phase and a time-of-flight dataset are refused, because the numbers read back fine and the model would be wrong.
[Names in other programs](../reference/foreign-names.md) maps each rietx parameter to its TOPAS name and gives the unit conversions.

### Porting an input that does not read

A parametric input usually does not read.
`read_project_model` raises `rietx.io.projects.topas.TopasInpError`, a `ValueError`, naming the first construct it cannot place.
In the Durham TOPAS tutorials, both parametric inputs of the WO₃ ramp stop at their `for xdds` loop.
The ZrP₂O₇ ramp's input stops at a site whose coordinates are written as macro calls, `B1(!xAl1,0.0000,0.0000)`.
The error names one construct and stops there, so it does not list what else the file uses.

These steps port such an input:

1. Call `rx.read_project_model(path, diagnostics=[])`.
   If it returns, the `TOPAS_FEATURES_NOT_IMPORTED` diagnostics and `model.coverage` list what the import left out.
   The ZrMo₂O₈ ramp's input reads this way, as the first of its 68 runs, and `TOPAS_FIRST_RUN_READ` says so.
2. If it raises, port from the input's text.
   Expand the macros and the loops first.
   `#list`, `#define`, `#ifdef` and `macro` act on the text, and `for xdds` repeats its body.
   TOPAS writes the input with every macro expanded to `TOPAS.LOG` when it runs, so read that file where TOPAS is at hand.
   By hand, each `#list` row is one pattern and one row of the `rx.CoordinateTable`.
   A `#define` decides which `#ifdef` branch is live, and a macro call is its body with the arguments substituted.
   `for xdds { ... }` is its body once per `xdd`.
3. Translate each line with the table in [A parametric equation is a formula](#a-parametric-equation-is-a-formula) and with [Names in other programs](../reference/foreign-names.md).
   A construct in the list under that table has no rietx spelling yet.
4. Call `MultiHistogramRefinement.preview_equations` before fitting.
   It evaluates every formula at its starting values, so compare its cells with the ones the input states.
5. Fit, and compare a refined value the input states, such as a lattice parameter, with rietx's in ppm, with both esds beside it.
   Two programs can differ by more than either esd.
   Rwp is a weaker check, because the two programs' peak shapes differ ([The peak shape is the instrument plus the sample](#the-peak-shape-is-the-instrument-plus-the-sample)).

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
