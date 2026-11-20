(guide-cell)=
# How to quote lattice parameters with their esds

Read each lattice parameter's row with `RefinementResult.parameter`, the volume from `RefinementResult.cell_volumes`, and write each as value(esd) with `rx.format_su`.

The esd measures how precisely the pattern fixes a parameter within the model you fitted.
How close the cell is to the true one depends on the wavelength and the position corrections you declared, which the esd does not include.

## Read the cell and its volume

This runs `mccusker_structural` on the fluorapatite pattern that ships with rietx, a hexagonal cell:

```{literalinclude} ../../../examples/guides/cell.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/cell.py -->
```text
phases.0.cell.a  9.370962(82)  free True
phases.0.cell.b  9.370962(82)  free False
phases.0.cell.c  6.885326(79)  free True
V = 523.629(12) Å³
```

In a hexagonal cell b is tied to a, so its row has `vary` set to `False` and carries a's esd.
The angles are fixed by symmetry, so they have no rows in the result and no esds to quote.
`rx.format_su` gives the esd two significant figures and rounds the value to match.

The volume's esd is propagated through the full covariance of the cell parameters, so the correlation between a and c is included.
`CellVolume.stderr_diagonal` is the same esd with that correlation left out, 0.011 Å³ here.
Quote `stderr`.

## Quote the esd as it is

`result.statistics.esd_inflation` is the factor already applied to every esd:

```{literalinclude} ../../../examples/guides/cell.py
:language: python
:start-after: "# guide: inflation start"
:end-before: "# guide: inflation end"
```

<!-- output of examples/guides/cell.py -->
```text
Bérar-Lelann factor 2.15
```

Neighbouring points of a step scan have correlated residuals, so they carry less independent information than their number suggests.
The Bérar-Lelann factor widens the esds to account for it.
The esds above already include it, so do not multiply them by it, or by the goodness of fit, again.
GSAS's esds do not include it, so compare them with `stderr_uncorrected`, the same esd without the factor.
[Estimation](../theory/estimation.md#esds-and-the-bérar-lelann-inflation) gives the formula.

## Check what the esd leaves out

A lattice parameter scales with the wavelength you declare.
rietx's Cu Kα₁ is 1.5405929 Å, and the GSAS tutorial this pattern comes from declares 1.5405 Å, 60 ppm shorter.
Refining again with only the tutorial's wavelengths:

```{literalinclude} ../../../examples/guides/cell.py
:language: python
:start-after: "# guide: wavelength start"
:end-before: "# guide: wavelength end"
```

<!-- output of examples/guides/cell.py -->
```text
a with rietx's Cu Ka      9.370962(82)
a with the tutorial's     9.370341(82)
difference 66 ppm, 7.6 esd
```

A 60 ppm change in the declared wavelength moves a by 7.6 esd, and the esd itself does not change.
GSAS's own refinement of this pattern, at the tutorial's wavelengths and with its own peak-position model, gives a = 9.371724(36) Å, 148 ppm above the second fit.

To quote an accurate cell, state the wavelength you used.
On a laboratory instrument, measure a certified standard such as NIST SRM 660c LaB₆ on the same setup, and check that its refined cell matches the certificate before you trust a sample's.
At a synchrotron, use the wavelength the beamline calibrated for your run.

## See also

- [How to quote a parameter that ended on its bound](interval.md) gives an interval for a row the esd cannot describe.
- [About correlations and esds](../concepts/correlations.md) explains why a parameter's esd depends on what else is free.
