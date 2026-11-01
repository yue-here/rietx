# Exports and derived tables

This page gives the three export writers, the calculated pattern and tick positions a result carries, the reflection list behind them, the items a refinement CIF holds, and the value(esd) notation every writer uses.

[How to export the refined structure as a CIF and the reflection list as a table](../guides/export.md) gives the procedure and reads both files back.
[Files written for other programs](foreign-writers.md) gives the TOPAS, FullProf, GSAS and GSAS-II files.
[Figures and structure pictures](figures.md) gives the fit figure's options and `render_structure`.

## Writers

| Call | Writes |
|---|---|
| `write_refinement_cif` | the refined structure, the fit and the pattern, as a CIF |
| `write_reflection_table` | one row per emission line and reflection: hkl, d, 2θ, \|F\|² and intensity |
| `write_qpa_table` | the quantitative phase analysis |

`Refinement.write_cif`, `Refinement.write_reflection_table` and `Refinement.write_qpa_table` write the same files from the last fit.
`Refinement.write_cif` also writes the reflection loop, which only a fit's compiled model can build.
`write_refinement_cif` takes the result, the structure and the instrument, so take `structure` from `Refinement.fitted_structure`, which holds the refined values and their esds.
A table's suffix `.tsv` or `.tab` makes it tab-separated.

`rietx.viz.html.write_html` writes the interactive page, and `RefinementResult.plot` writes the static figure.
Both work on a base install.

## The calculated pattern

`RefinementResult` carries the curves of the fit: `RefinementResult.y_obs`, `RefinementResult.y_calc` and `RefinementResult.y_background` on `RefinementResult.two_theta`.
Three more fields belong with them.

| Field | Holds |
|---|---|
| `RefinementResult.sigma` | the σ of each point, as the fit weighted it |
| `RefinementResult.ticks` | each phase's reflection positions, in degrees 2θ |
| `RefinementResult.tick_hkl` | which reflection each of those positions is |

### Point weights

`RefinementResult.sigma` is copied from the model the last stage compiled.
It is the pattern's own σ, from the file's esd column or from counting statistics, with one exception.
A background holding a measured curve with `BackgroundFixedPlusChebyshev.fixed_sigma` adds the curve's counting statistics at compile, so σ there is wider than the pattern's ([Fixed curve plus Chebyshev](instrument.md#fixed-curve-plus-chebyshev)).

`RefinementResult.sig` returns the σ to divide by.
Every weighted residual in the package goes through it: the static figure, the interactive page, the report's Layer 0 and the GUI's windows.
It conditions the array in two ways.
A result recorded before v0.2 carries no σ, and gets the √max(y, 1) fallback the fit itself would have used.
A non-positive entry is floored, so a zero esd becomes a small σ and the residual stays finite.

`RefinementResult.sig` does not say where σ came from, since a file's esds and a counting-statistics estimate are the same array of floats once a result exists.
`DataRef.has_sigma` records which it was, and a figure's residual axis and the GUI's text document are labelled from it ([The pattern reference](project.md#the-pattern-reference)).

### Ticks

`RefinementResult.ticks` maps a phase name to its reflection positions in degrees 2θ.
Each sits where the calculated curve draws its peak, so the zero shift and the geometry's own position correction (sample displacement, transparency or capillary offset) are in it.
It covers every emission line, the Kα₂ positions included.
The calculated pattern has a peak at each of them, and a list without them made the report flag every Kα₂ peak as an unindexed impurity.
Declared extra peaks have their positions under the key `"(extra)"`.

`RefinementResult.tick_hkl` gives each tick's reflection as `[h, k, l]`, paired with `ticks` by index.
One reflection appears once per emission line, so a peak and its Kα₂ image carry the same Miller index.
The three browser pages show it when the pointer is over a tick.
A phase with nothing to say is absent from the mapping rather than present and empty.
The `"(extra)"` key is absent for that reason: a peak declared by its centre has no Miller index.

A satellite of a phase with a propagation vector is `[h, k, l, m]`: its parent reciprocal-lattice vector H and its order m.
H alone does not identify it, because the satellite of (0 0 0) is not the origin, and a nuclear row and a satellite can share a parent.
The browser pages label three-index rows only, so they show a satellite tick unlabelled.

Two reflections can land at the same 2θ to every printed decimal, so a position is not a key into this mapping.
Pair a tick with its reflection by index.

### Evaluating the model

`Refinement.predict` evaluates the calculated pattern at the parameters as they stand.
Given a grid, it compiles a fresh model on it, so it extrapolates beyond the fitted range or resamples inside it.
The grid is a `PatternData` or an array of 2θ values.
With no argument it uses the grid the last fit ran on.

<!-- api-doc: no-exec — needs a structure and an instrument -->
```python
import numpy as np

fine = np.arange(10.0, 90.0, 0.001)
y = refinement.predict(fine)

y_here = refinement.predict(data)   # the pattern's own grid
```

Evaluating a model needs no fit.
The values come off the structure and instrument, whether a fit put them there, `Refinement.set_values` did, or you typed them.
A plan with no stages refines nothing and is refused, so `Refinement.predict` is the call that draws the curve a set of parameters implies.
Two cases need a fit first.
`predict()` with no argument has no grid until a fit has run.
In Le Bail and Pawley mode the per-reflection intensities are extracted by a fit, so a new grid carries them over from the fitted model and there is nothing to carry before one has run.

The two forms are not bit-identical on the same grid.
`predict()` reuses the model compiled for the last stage, whose per-reflection evaluation windows were sized at the values that stage started from.
A grid argument sizes them at the values the stage ended on.
On a synthetic five-stage fit that changes 36 of 4200 channels, by at most 8×10⁻⁶ of the peak height, all of them in peak tails at a window edge.
`RefinementResult.y_calc` is the first of the two: the curve the fit minimised.

## The reflection list

`Refinement.reflection_table` returns one row per emission line and reflection of every phase, after a fit.
`reflection_table` is the same table as a function.
It takes the compiled model, the decoded parameter values and the structure, for a program that holds those instead of a `Refinement`.
`Refinement.write_reflection_table` writes it to a file, with every column below but `phase_index`.

| Field | Holds |
|---|---|
| `ReflectionRow.phase` | the phase name |
| `ReflectionRow.line` | which emission line, counted from 0 |
| `ReflectionRow.wavelength` | that line's λ in Å |
| `ReflectionRow.h`, `ReflectionRow.k`, `ReflectionRow.l` | the Miller indices |
| `ReflectionRow.d` | the d-spacing in Å |
| `ReflectionRow.two_theta` | the position the model draws the peak at, in degrees |
| `ReflectionRow.multiplicity` | the Laue-group multiplicity of the orbit |
| `ReflectionRow.f_squared` | \|F\|², or `None` in Le Bail and Pawley mode; read the paragraphs below on a phase with moments |
| `ReflectionRow.intensity` | the modelled integrated intensity of this row |
| `ReflectionRow.satellite_order` | the m of Q = H + m·k, with k the propagation vector; 0 on every nuclear reflection |
| `ReflectionRow.component` | `"total"`, or `"nuclear"` and `"magnetic"` where a magnetic peak width is active |
| `ReflectionRow.phase_index` | the phase's index in the structure, which holds where two phases share a name |

`ReflectionRow.two_theta` is the Bragg angle plus the zero shift plus the geometry's own position correction, so it matches `RefinementResult.ticks` rather than the ideal Bragg angle.
A reflection whose 2θ is non-physical at one line's wavelength (sin θ > 1) is dropped for that line only, so a row missing from one line may be present in another.

`ReflectionRow.intensity` is the whole modelled contribution under the tick.
In Rietveld mode it is scale × multiplicity × \|F\|² × preferred orientation × line weight × Lp × extinction × absorption × roughness.

`ReflectionRow.satellite_order` is 0 on every row of a phase that declares no `Phase.propagation_vector`.
On a satellite row `ReflectionRow.h`, `ReflectionRow.k` and `ReflectionRow.l` stay the parent vector H, and the row reads as H and m together, the (3+1)-index spelling.
`ReflectionRow.d` is the satellite's own d-spacing.
`ReflectionRow.f_squared` on a satellite row is 0 in Rietveld mode, since a satellite carries no nuclear structure factor.

`ReflectionRow.component` is `"total"` on every row unless a phase's magnetic contribution is drawn with its own width: `Phase.magnetic_lor_size` or `Phase.magnetic_lor_strain` non-zero, or free in the stage that compiled the model ([Magnetic peak width](magnetic.md#magnetic-peak-width)).
Such a phase gets two rows per line and reflection, one `"nuclear"` and one `"magnetic"`, because the two are drawn on different profiles.
Their `ReflectionRow.intensity` values add to the reflection's total.
`ReflectionRow.f_squared` is each component's own: ⟨\|F<sub>N</sub>\|²⟩ on the nuclear row, and p²⟨\|F<sub>⊥</sub>\|²⟩ on the magnetic one.
Here F<sub>⊥</sub> is the part of the magnetic structure factor perpendicular to the scattering vector, and p is the magnetic scattering length of one Bohr magneton, 2.695 fm ([Intensities](../theory/intensities.md)).

On a `"total"` row of a phase carrying moments, `ReflectionRow.f_squared` is the nuclear ⟨\|F<sub>N</sub>\|²⟩ alone, while `ReflectionRow.intensity` is built from ⟨\|F<sub>N</sub>\|²⟩ + p²⟨\|F<sub>⊥</sub>\|²⟩.
A magnetic-only reflection therefore has `f_squared` 0 beside an intensity that can be among the largest in the pattern.
MnF₂'s (1 0 0) under magnetic space group 136.499 is one: a nuclear absence the magnetic group allows.
Read the magnetic share from `ReflectionRow.intensity`.

Anomalous scattering is on by default, and with it `ReflectionRow.f_squared` is the Friedel average ⟨\|F\|²⟩ = ½(\|F(h)\|² + \|F(−h)\|²).
The two terms differ in a non-centrosymmetric group, both land in the same powder peak, and only the average is observable in a powder.

## The refinement CIF

The CIF is the one a journal asks for, so it carries more than the coordinates.
Per phase it writes the agreement indices of [The refinement result](result.md): `_refine_ls_R_I_factor` (R<sub>B</sub>), `_refine_ls_R_factor_all` (R<sub>F</sub>) and `_refine_ls_number_reflns`.
It writes the bond distances, contacts and angles as `_geom_bond_`, `_geom_contact_` and `_geom_angle_` loops, with esds in value(esd) form.
The loops list each bond once, where `GeometryTable` lists it from each end so that the rows naming an atom count its neighbours ([Derived quantities](derived.md#bonding-geometry)).

Each `_geom_*_site_symmetry_*` code indexes the `_space_group_symop_` loop written into the same block.
A code that pointed at whatever order the reader's own library generated would name a different atom.

With `pattern=` the profile loop holds every measured point, and a weight of 0 marks each point the fit did not use.
Without it the loop holds only the fitted points.
A single-phase file reads back through `Structure.from_cif` and `read_pdcif`.
A multi-phase file has one block per phase, each of which reads back as a structure, while the pattern loop and the refinement items are in the first block only.

## The structure block

Every CIF this package writes, `Structure.to_cif` included, opens each phase with the same structure block.

It names the setting three ways.
The resolved Hermann-Mauguin symbol goes under `_space_group_name_H-M_alt`, beside the Hall symbol, the IT number and the crystal system.
The full `_space_group_symop_` loop follows, which is the loop the geometry codes index.
An H-M symbol cannot fix the origin, and the Hall symbol and the operations can, so a bare `F d -3 m` never reaches the file.
The deprecated `_symmetry_space_group_name_H-M` is not written.
The GSAS-II phase CIF is the one exception, since GSAS-II reads that tag first ([Files written for other programs](foreign-writers.md#gsas-ii-phase-cif)).

Displacements are U (`_atom_site_U_iso_or_equiv`, with `_atom_site_adp_type` `Uiso` or `Uani`), with each site's multiplicity beside it.
The block also states the formula in Hill order, Z, M<sub>r</sub>, the calculated density and the cell volume, an `_atom_type` loop, and the dictionaries it conforms to: `cif_core.dic` 3.3.0, plus `cif_pd.dic` 2.5.0 in a refinement CIF and `cif_mag.dic` 0.9.9 for a magnetic phase.
A type symbol is the species rietx computes, so `Cu+` is written `Cu1+`, and an ion rietx's table lacks is written as the neutral atom with `_atom_type_description` saying so.

A value with an esd is written in value(esd) form.
A value without one is written as the shortest text that reads back as the same number, so a β of 90.00004 survives a round trip.
Two phases whose names collapse to one block name, such as `ph 1` and `ph-1`, get distinct blocks.
A label with whitespace and a non-finite number are refused by name before the file is written.

Run through IUCr checkCIF, a structure-only file reports the same volume, symmetry, formula, M<sub>r</sub>, density and Z that checkCIF computes.
Its remaining alerts ask for single-crystal and instrument items a powder structure does not have.

## Numbers with uncertainties

`format_su` writes a value and its esd in the crystallographic value(esd) notation {cite}`schwarzenbach1989`.
The esd carries two significant figures, and the value is quoted to the same last decimal.

```python
from rietx.io.exporters import format_su

assert format_su(4.593700, 2.5e-4) == "4.59370(25)"
assert format_su(123.4, 2.5) == "123.4(25)"
assert format_su(12345.0, 250.0) == "12340(250)"
```

An esd of 2.5 × 10⁻⁴ says the sixth decimal is not known, so the esd sets the number of decimals.
The `decimals` argument applies only to a value with no esd, and the CIF writers do not use it.
A CIF writer writes a value with no esd as the shortest text that reads back as the same number, because a fixed number of decimals loses what it does not print.

The function handles three cases a format string does not.
An esd such as 0.0999 rounds up to 100 at two figures, so it is written as 0.10, with one fewer decimal on the value.
An esd of 1 or more takes decimals off the value and keeps its own trailing zeros, so 12345 ± 250 is `12340(250)`.
With no esd it writes the plain number and implies no uncertainty.
An esd of `None`, a non-positive esd and a non-finite one all count as none, as on a fixed parameter or one the fit could not estimate.

```python
from rietx.io.exporters import format_su

assert format_su(1.234567, 0.0999) == "1.23(10)"
assert format_su(4.5937, None) == "4.593700"
```
