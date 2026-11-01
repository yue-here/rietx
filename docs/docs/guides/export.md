(guide-export)=
# How to export the refined structure as a CIF and the reflection list as a table

After a fit, call `Refinement.write_cif` for a CIF of the structure, the fit and the pattern, and `Refinement.write_reflection_table` for a CSV of every reflection.

## Write the two files

This refines the fluorapatite pattern that ships with rietx and writes both files into a new temporary directory:

```{literalinclude} ../../../examples/guides/export.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

Both methods write what the last fit left, and raise if no fit has run.
A suffix of `.tsv` or `.tab` makes the reflection table tab-separated.

In a project, the GUI's export commands write the same files into the project's `exports/` directory ([About a project](../concepts/project.md)).

## Read the CIF

```{literalinclude} ../../../examples/guides/export.py
:language: python
:start-after: "# guide: cif start"
:end-before: "# guide: cif end"
```

<!-- output of examples/guides/export.py -->
```text
data_fluorapatite
_cell_length_a 9.370962(83)
_cell_length_b 9.370962(83)
_cell_length_c 6.885324(80)
_cell_volume 523.629(12)
_space_group_name_H-M_alt 'P 63/m'
10 loops
```

Every refined value carries its esd in value(esd) form, and the volume's esd includes the correlation between a and c.
The ten loops hold the dictionaries the file conforms to, the symmetry operations, the atom types, the atom sites, the bond distances, contacts and angles with their esds, the wavelengths, every point of the pattern with its observed, calculated and background intensity, and the reflections.
The R factors, the profile function and the background are single items in the same block.

The pattern loop holds every point of the pattern the fit was given.
A point the fit did not use, outside `two_theta_limits` or in an excluded region, has a weight of 0.

Check the file with the IUCr's checkCIF service before you submit it.

## Read the reflection table

```{literalinclude} ../../../examples/guides/export.py
:language: python
:start-after: "# guide: hkl start"
:end-before: "# guide: hkl end"
```

<!-- output of examples/guides/export.py -->
```text
phase,line,wavelength,h,k,l,d,two_theta,multiplicity,f_squared,intensity,satellite_order,component
fluorapatite,0,1.5405929,1,0,1,5.2502971,16.821207,12,129.37451,64.568913,0,total
fluorapatite,0,1.5405929,2,-1,0,4.6854811,18.872864,6,151.2127,29.807452,0,total
658 rows
```

There is one row per reflection per emission line, so the Cu Kα doublet gives 329 reflections twice.
Filter on `line == 0` for one row per reflection.

`two_theta` is where the model places the peak, with the zero shift and the geometry's position corrections included, so it matches the tick marks on the plot.
`intensity` is the reflection's whole modelled integrated intensity: the scale, multiplicity, |F|², preferred orientation, line weight, Lorentz-polarisation factor and the specimen corrections multiplied together.
`f_squared` is |F|² alone, averaged over the reflection and its Friedel mate, and empty after a Le Bail or Pawley fit, where no structure computes it.

`Refinement.reflection_table` returns the same rows as `ReflectionRow` objects, without writing a file.

## Read the files back

The CIF reads back with rietx's own readers, as a structure and as a pattern:

```{literalinclude} ../../../examples/guides/export.py
:language: python
:start-after: "# guide: read start"
:end-before: "# guide: read end"
```

<!-- output of examples/guides/export.py -->
```text
9.370962 5753
```

This holds for a single phase.
With several phases the CIF has one block per phase, each of which reads back as a structure, while the pattern and the R factors are in the first block only.

## Write a CIF without the `Refinement`

`rx.write_refinement_cif(result, structure, instrument, path, pattern=data)` writes the same CIF from a result, the refined structure and instrument, and the pattern.
It has no compiled model to build reflections from, so the file has no reflection loop.
Use it when you hold a result and its models but not the `Refinement` that produced them.

## See also

- [How to quote lattice parameters with their esds](cell.md) shows what the cell's esds measure.
- [About a project](../concepts/project.md) describes the `exports/` directory.
- [Exports and derived tables](../reference/exports.md) gives every item the refinement CIF writes.
