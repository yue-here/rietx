(guide-joint)=
# How to fit an X-ray and a neutron pattern together

Give each pattern its own `Instrument`, fit one `Structure` to both with `rietx.MultiHistogramRefinement`, and free the wavelength of the less well calibrated pattern in a stage of its own.

X-rays scatter from electrons, so heavy atoms dominate an X-ray pattern.
Neutrons scatter from nuclei, and the scattering length b follows no such order, so a neutron pattern weights the same atoms differently.
Corundum ranks its two sites oppositely: f(0) is 13 electrons for Al and 8 for O, while b is 3.449 fm for Al and 5.803 fm for O.
A joint fit refines one structure against both patterns at once, in one residual {cite}`vondreele1997`.
GSAS-II calls this a combined refinement over several histograms.

## Compare the patterns' cells first

No pattern that rietx ships pairs two radiations on one specimen, so this guide uses a synthetic pair.
`examples/guides/_corundum_pair.py` computes a Cu Kα1 capillary pattern and a constant-wavelength neutron pattern of one corundum structure, and adds Poisson noise.
The neutron pattern was computed at a wavelength 300 ppm longer than its instrument declares, as a monochromator calibration error would give.

Fit each pattern alone and compare the cells:

```{literalinclude} ../../../examples/guides/joint.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/joint.py -->
```text
X-ray    a = 4.7588824(41) Å
neutron  a = 4.757487(31) Å
```

One specimen has one cell, but the neutron pattern's is 293 ppm short.
Through Bragg's law a single pattern measures only the cell in units of its wavelength, so a cell that disagrees by more than its esds points to a declared wavelength that is off.

## Fit both together and free the neutron wavelength

Hold the wavelength you trust and free the other.
Here that is the X-ray one: the Cu Kα1 wavelength is fixed by atomic physics, while a neutron monochromator's is calibrated.
The shared cell then carries the X-ray scale, and the neutron wavelength refines against it.

```{literalinclude} ../../../examples/guides/joint.py
:language: python
:start-after: "# guide: joint start"
:end-before: "# guide: joint end"
```

<!-- output of examples/guides/joint.py -->
```text
info[WAVELENGTH_CALIBRATION]: Histogram 1 line 0: wavelength refined from the declared 2.078000 A to 2.078618 A, +297.3 ppm, 58.8× its own esd (1.05e-05 A). The shift is taken against the cell pinned by the histogram whose wavelength is held.
  at: hist.1.instrument.source.lines.0.wavelength
  help: Compare it with the instrument's own calibration history before you quote the cell.
```

The refined wavelength lies within its esd, 5.1 ppm, of the one the pattern was made with, and the shared cell 1.4 esd from the true one.

`MultiHistogramRefinement` takes the instruments in the order `fit` takes the patterns.
A parameter that belongs to one pattern is named with a `hist.{h}.` scope, so `hist.1.instrument.source.lines.0.wavelength` is the neutron pattern's wavelength.
A glob without the scope frees the parameter on every pattern.
Freeing both wavelengths is refused, because the cell would then have no fixed length scale:

```text
2 of 2 wavelengths are free; hold one.
```

[`WAVELENGTH_CALIBRATION`](../reference/diagnostics-refinement.md#wavelength_calibration) reports the shift in ppm and against its own esd.
It sits in `result.histograms[1].diagnostics`, with the other findings that belong to one pattern.
A shift inside its esd means the wavelength was already right.

Held at its declared value instead, the 300 ppm error goes into the shared model.
The lattice parameter a then ends 2.6 esd from the true value, and the esds of both corundum coordinates come out larger than the X-ray pattern gives alone.
No diagnostic reports it.

## Read what each pattern added

Compare each coordinate's esd alone and jointly:

```{literalinclude} ../../../examples/guides/joint.py
:language: python
:start-after: "# guide: esd start"
:end-before: "# guide: esd end"
```

<!-- output of examples/guides/joint.py -->
```text
phases.0.atoms.0.z  X-ray 0.352121(40)  neutron 0.35190(15)  joint 0.352108(39)
phases.0.atoms.1.x  X-ray 0.30635(19)  neutron 0.30643(18)  joint 0.30634(13)
```

`phases.0.atoms.0.z` is the Al coordinate and `phases.0.atoms.1.x` the O coordinate.
Alone, the neutron pattern measures z(Al) 3.6 times less precisely than the X-ray pattern, and x(O) about as well.
Jointly, z(Al) keeps the X-ray pattern's esd, and x(O)'s esd falls to 0.67 of it.
The neutron pattern adds the oxygen, and the aluminium stays the X-ray pattern's.

## Choose which parameters are shared

By default a parameter is per-pattern if its name starts with `instrument.` or ends with `.scale`, and shared otherwise.
The structure is shared, and each pattern keeps its own scale, background, zero shift, peak widths and wavelength.
`SharingMap` overrides the rule with lists of globs:

```python
from rietx.params.multi import SharingMap

per_mount = SharingMap(per_histogram=["phases.*.preferred_orientation.*"])
assert not per_mount.is_shared("phases.0.preferred_orientation.r")
assert per_mount.is_shared("phases.0.cell.a")
```

Pass it as `MultiHistogramRefinement(structure, instruments, sharing=per_mount)`.
Give each pattern its own preferred orientation when the two specimens were mounted differently.
Keep the cell shared whenever a wavelength is free, because a cell of one pattern alone and a free wavelength cannot be told apart.

A joint fit runs in Rietveld mode only.

The full script is `examples/guides/joint.py`.

## See also

- [How to refine a cell edge as a function of temperature](equation.md) fits one equation across many patterns with `refine_multi`.
- [How to fit a temperature series](series.md) fits each pattern on its own, starting from the last.
