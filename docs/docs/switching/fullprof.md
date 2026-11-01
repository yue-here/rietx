# Coming from FullProf

This page says how a FullProf refinement maps onto a rietx one, and how to move a `.pcr` file across.
rietx has not been compared with FullProf's refined numbers, and the last section says what the file readers were checked against instead.

## What is the same

FullProf and rietx fit a calculated pattern to the observed counts by least squares, and both state the refine flags of a run in the file or the plan that drives it.
Both give each phase its own size and strain broadening, and both treat X-ray and constant-wavelength neutron data.
A FullProf `.pcr` states a whole refinement, and `read_project_model` reads the phases, the cell, the atoms and which of them the file refined.

## Differences in concepts

### A codeword is a number, and a plan decides the rest

A FullProf codeword stays in the file as you set it.
rietx's plan decides which parameters refine in each stage, so a flag set by hand before `fit` is replaced.
`Refinement.hold` keeps a parameter fixed through every stage, as a codeword of 0 does.
[About a fit](../concepts/fit.md#the-plan) describes the plan.

FullProf marks a refined parameter with a codeword, a number on the line under the values.
Two values carrying the same number follow one refined parameter, and a minus sign reverses the sign, so `11.00` and `-11.00` on two magnetic atoms are an antiferromagnetic pair.
rietx's writer gives every free parameter its own number and never writes a shared one.
Here the fluorapatite structure is written with the lattice parameters a and c, the scale, one displacement parameter and one coordinate flagged.
The lines that carry no codeword are elided, and each number is cut to six significant figures:

<!-- api-doc: no-exec — needs a structure with refine flags set and writes a file; examples/switching.py runs it and asserts these lines -->
```python
rx.write_fullprof_pcr(structure, "flags.pcr")
```

```text
Ca1 CA 0.333333 0.666667 0.001913 0.479979 0.333333
0.0 0.0 0.0 11.0 0.0
...
O7 O 0.33951 0.258126 0.070641 0.530037 1.0
0.0 0.0 21.0 0.0 0.0
1.0 0.0 0.0 0.0 0.0 0.0 0
31.0 0.0 0.0 0.0 0.0 0.0
...
9.3717 9.3717 6.8859 90.0 90.0 120.0
41.0 0.0 51.0 0.0 0.0 0.0
```

Each atom's second line holds the codewords for its x, y, z, B and occupancy.
`11.0` frees the B of Ca1, `21.0` the z of O7, `31.0` the scale, and `41.0` and `51.0` the lattice parameters a and c.
The parameter b has no codeword.
FullProf applies the cell constraints of the Laue class itself.
Run on this file, FullProf 8.20 (February 2025) reports `Cell constraints according to Laue symmetry: 6/m` and gives b and γ the codeword of a.
Files written by hand often give a and b the same codeword, and the reader accepts both forms.
The reader maps the file back to the same free set:

<!-- api-doc: no-exec — reads the flags.pcr the previous block writes; examples/switching.py runs both and asserts the free set -->
```python
model = rx.read_project_model("flags.pcr")
ref = rx.Refinement(model.to_structure(), rx.Instrument.bragg_brentano(radiation="CuKa"))
```

```text
>>> [r.path for r in ref.parameters() if r.vary]
['phases.0.cell.a', 'phases.0.cell.c', 'phases.0.scale', 'phases.0.atoms.0.biso',
 'phases.0.atoms.6.dof.0', 'phases.0.atoms.6.dof.1', 'phases.0.atoms.6.dof.2']
```

rietx refines coordinates along the directions the site symmetry allows, one `dof` each.
O7 is on a general position, so flagging its z frees all three.

When a file shares one codeword across atoms, the reader drops the tie and reports it as `FULLPROF_TIE_DROPPED`.
The message names the `Refinement.tie_equal` or `Refinement.tie` call that restores it.
Where restoring it would mean choosing between two readings, the reader refuses the file by name.

### The width coefficients are in other places

FullProf's U, V and W are Gaussian FWHM² in degrees², the same as rietx's.
FullProf swaps the letters for the Lorentzian terms.
Its X multiplies tan θ, and its Y multiplies 1/cos θ.
rietx and GSAS-II have the reverse, so FullProf's X is rietx's `y` and FullProf's Y is rietx's `x`.

FullProf also states the sample's size and strain through a phase's own parameters.
FullProf's X is rietx's `y` plus the phase's `lor_strain`, and its Y is rietx's `x` plus `lor_size`.
rietx keeps the instrument's width apart from the sample's, so that a calibrated instrument can be loaded for each specimen.
The reader states the wavelengths, the zero and the background on the `FullProfModel` and builds only the `Structure`.
rietx's exporters write FullProf's profile names, and nothing reads them back.
[Names in other programs](../reference/foreign-names.md) gives each name.

### The scale is not comparable

FullProf folds the unit-cell content, the occupancy normalisation and its own profile normalisation into one scale.
rietx carries the file's scale through as a starting value and a refine flag, and it does not equal a rietx scale.
Reading a `.pcr` therefore gives a scale to refine from, and the value is no basis for a comparison.

### rietx's esds already carry SCOR

FullProf prints SCOR, the Bérar-Lelann factor for serially correlated residuals, and leaves its own esds without it.
rietx multiplies every esd by the same correction, and `RefinedParameter.stderr_uncorrected` holds each esd without it.
So compare a FullProf esd with `stderr_uncorrected`, or a FullProf esd times its SCOR with `stderr`.
On FullProf's fit of the PbSO<sub>4</sub> round-robin pattern, rietx's formula gives a factor 4 % above FullProf's SCOR.
[Estimation](../theory/estimation.md#esds-and-the-bérar-lelann-inflation) says why rietx applies the factor and what each program reports.

### The species follow the radiation

FullProf looks X-ray form factors and neutron scattering lengths up differently, and the writer follows each.
For X-rays it writes the element with its charge, so `Zr4+` becomes `ZR+4` and `O2-` becomes `O-2`.
For neutrons it writes the element alone, so `O2-` becomes `O`, because FullProf stops on `O-2` there.
An isotope is written only in a neutron file, as a user scattering length on line 12 (`7Li` as `Typ LI7` with `LI7 -0.222 0.0 0`).
An isotope in an X-ray file is refused by name, and so is one whose name does not fit in four characters.

### The setting has to be one FullProf can state

FullProf has no origin or axis suffix, so it can only state a setting its own bare symbol prefers.
rietx refuses a phase in another setting, and most often origin choice 1, rather than write it as the other.
A phase on rhombohedral axes is written on hexagonal ones, because FullProf reads `R -3 c` as hexagonal whatever the cell says.
The diagnostic `FULLPROF_RHOMBOHEDRAL_RESTATED` says so, and the restated cell and coordinates are held.

## Moving a file across

`rx.read_fullprof_pcr` returns a `FullProfModel` with the phases, the cell, the wavelengths, the zero and its codeword, the background, the excluded regions, the cycles, and the number of parameters the run refined.
`rx.identify_project_format` tells you which format claims a file without parsing it.
A `.pcr` is positional and has no keyword to find its place again from, so the reader checks every count the file declares against the lines it parsed.

The reader refuses these by name:

- an anisotropic displacement block, because the conversion needs a convention no file settles, and a wrong factor of 2 is a wrong Debye–Waller factor;
- an occupancy column that does not reduce;
- a refined value whose codeword is missing, because the file does not say whether FullProf refined it;
- a magnetic phase that does not map onto a nuclear one.

A magnetic phase that does map is read as the moments of its nuclear phase, and reported as `FULLPROF_MAGNETIC_PHASE_READ`.
`to_structure(nuclear_only=True)` declares that you want the nuclear phases alone.
`rx.write_fullprof_pcr` writes a nuclear structure back, and refuses an anisotropic site, a magnetic phase and a propagation vector.

## What the readers were checked against

No refinement in the validation matrix compares rietx's numbers with FullProf's.
The `.pcr` reader was written against six real files and checked against them by hand, and those files are not in the repository.
Its tests use short synthetic files, each quoting the lines of a named real file that it copies.
The writer is held to a round trip: write a file, read it back, and compare field by field.
