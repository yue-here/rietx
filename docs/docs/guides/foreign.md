(guide-foreign)=
# How to open a GSAS, TOPAS or FullProf refinement and write one back

Open the other program's input file with `rx.read_project_model`, build the structure with `to_structure`, and after the fit write the result back with that program's writer.

`read_project_model` reads a GSAS `.EXP`, a GSAS-II `.gpx`, a TOPAS `.inp` and a FullProf `.pcr`, and recognises each by its content rather than its extension.
It returns the structure and what the file states about its run.
You build the instrument and read the pattern yourself, from what the file states.

## Open the file

This opens GSAS's refinement of the fluorapatite pattern, which ships with rietx as `FAP.EXP`:

```{literalinclude} ../../../examples/guides/foreign.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/foreign.py -->
```text
gsas_exp | data fap.xra | wavelengths (1.5405, 1.5443)
stated Rwp 0.1005
GSAS_EXP_BACKGROUND_NOT_CARRIED
```

`model.stated` holds what the file says about its own run: the wavelengths, the data file it fitted, its R factors and which parameters it refined.
The `diagnostics=` list gets one entry for each thing the reader read but could not carry over.
Here GSAS fitted a background function rietx does not have, so you choose a rietx background instead.

A construct the reader cannot carry without changing the model, such as a rigid body in TOPAS or an anisotropic displacement block in FullProf, is refused with its name.

## Build the models and refine

```{literalinclude} ../../../examples/guides/foreign.py
:language: python
:start-after: "# guide: refine start"
:end-before: "# guide: refine end"
```

<!-- output of examples/guides/foreign.py -->
```text
rietx Rwp 0.0953
```

The wavelengths come from the file, so a cell compared with GSAS's is not shifted by a difference in the declared wavelength.
This Rwp is not comparable with GSAS's stated 0.1005, because the background and peak-shape models differ.
To compare the two programs, mirror the other program's protocol as well, as each comparison in [Validation against other codes](../switching/validation.md) does.

## Write the result for another program

```{literalinclude} ../../../examples/guides/foreign.py
:language: python
:start-after: "# guide: write start"
:end-before: "# guide: write end"
```

<!-- output of examples/guides/foreign.py -->
```text
fap.inp topas_inp
fap.pcr fullprof_pcr
```

- `rx.write_topas_inp` writes an input TOPAS runs as it stands, with the data beside it as `fap.xye`. `free=ref` makes the file refine the parameters the fit refined, with its ties.
- `rx.write_fullprof_pcr` writes a `.pcr`. It refuses a non-zero zero shift unless `write_zero_shift=True`, and refuses any other position correction, because the file would put every peak somewhere else. It also refuses extinction, preferred orientation, texture, absorption and surface roughness away from their off states, because it writes none of them. The fit here can be written because its extinction ended at 0.
- `rx.write_gsas2_phase_cif` writes a CIF that GSAS-II's phase import reads, and `rx.write_gsas2_instprm` writes the instrument as a GSAS-II `.instprm`. rietx has no writer for a `.gpx`.

`rx.identify_project_format` says which format a file is without reading the model.
A writer refuses on the way out what its reader would refuse on the way in, so a file it writes reads back.

## See also

- [Coming from GSAS-II](../switching/gsas2.md), [Coming from TOPAS](../switching/topas.md) and [Coming from FullProf](../switching/fullprof.md) list what each reader and writer carries and refuses.
- [Names in other programs](../reference/foreign-names.md) maps each rietx parameter to its name and unit in the other programs.
- [Refinement files from other programs](../reference/foreign-files.md), [Files written for other programs](../reference/foreign-writers.md) and [Models of other programs' files](../reference/foreign-models.md) give each reader, writer and model field by field.
