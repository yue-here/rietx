# Diagnostic codes

This page lists every diagnostic code rietx can raise, with its name and the page that explains it.

A `Diagnostic` carries a `level` of `info`, `warning` or `error`, a `code`, a `message` and a `suggestion`.
The message says what one case found, with its numbers.
The suggestion says what to do about it.
The explanation is the same for every case, so the package looks it up by code: `Diagnostic.explanation` returns the text the linked page shows.

The codes are filed by the part of the package that raises them:

- [Refinement](diagnostics-refinement.md): the guards and the report.
- [Stages and plans](diagnostics-stages.md): how a stage or a plan ran, and why one stopped.
- [Corrections](diagnostics-corrections.md): absorption, roughness, extinction, dispersion, harmonics, texture and declared peaks.
- [Series and joint fits](diagnostics-series.md): a chain of fits, or one fit over several patterns.
- [Background selection](diagnostics-background.md): the scans that choose a background's flexibility.
- [Time-of-flight banks](diagnostics-tof.md): what a fit on a neutron time-of-flight bank applied, and the checks that did not run on one.
- [Peaks and indexing](diagnostics-indexing.md): peak picking, the indexing search and the extinction screen.
- [Reading files](diagnostics-files.md): patterns, instrument files and recipes.
- [Other programs' projects](diagnostics-projects.md): GSAS-II, GSAS, FullProf and TOPAS files.
- [Structures and magnetism](diagnostics-structures.md): structures, symmetry and magnetic structures.

```{toctree}
:hidden:

diagnostics-refinement
diagnostics-stages
diagnostics-corrections
diagnostics-series
diagnostics-background
diagnostics-tof
diagnostics-indexing
diagnostics-files
diagnostics-projects
diagnostics-structures
```

```{include} ../_generated/diagnostics.md
```
