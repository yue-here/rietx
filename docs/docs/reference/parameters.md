# Parameter map

This page lists every parameter rietx can refine, grouped by what it does to the pattern, except the time-of-flight ones, which have [their own page](parameters-tof.md).

Every parameter has a name made of parts joined by dots.
`phases.0.cell.a` is lattice parameter a of the first phase, counting from 0, and `instrument.zero_shift` is the instrument's zero shift.
A `*` in a name matches any run of characters, dots included, so `phases.*.cell.a` is lattice parameter a of every phase and `phases.0.*` is every parameter of the first phase.
The tables write names this way, and a refinement plan uses the same names to say which parameters to refine.

Each row gives the parameter's unit, its default and a typical range to check a refined value against.
A parameter with no default takes its value from the structure or instrument you load.

```{toctree}
:hidden:

parameters-tof
```

```{include} ../_generated/parameters.md
```
