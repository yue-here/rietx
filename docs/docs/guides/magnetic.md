(guide-magnetic)=
# How to refine a magnetic moment on a known magnetic structure

Declare the magnetic space group on the phase and a starting moment on the magnetic site, refine against a constant-wavelength neutron pattern, and read the moment from `FitReport.magnetic`.
This assumes you know the magnetic structure, from the literature or from an earlier analysis.
If you do not, [`solve_magnetic`](../reference/magnetic.md#solve_magnetic) ranks the candidate groups, and [How to refit the nuclear model with the moment present](moment.md) runs it on a worked example.

The example is LaMnO₃ at 50 K, below its ordering temperature, from the [GSAS-II *Magnetic-I* tutorial](https://github.com/AdvancedPhotonSource/GSAS-II-tutorials), stored in `tests/data/`.
Every line indexes on the nuclear P n m a cell, so the propagation vector is zero and the magnetic structure is a magnetic space group on that cell.
The tutorial's answer is Pn′ma′, BNS number 62.448.
`_lamno3.py`, beside the script, reads the pattern, the tutorial's structure file and its instrument file, and builds a six-stage nuclear plan.
The patterns are not in the wheel, so the script runs from a checkout of the repository.

## Fit the nuclear model

```{literalinclude} ../../../examples/guides/magnetic.py
:language: python
:start-after: "# guide: nuclear start"
:end-before: "# guide: nuclear end"
```

<!-- output of examples/guides/magnetic.py -->
```text
nuclear only: Rwp 0.138
```

The fit range, 6-156° 2θ, and the excluded line at 15.7° are the tutorial's.
No phase explains that line.
The nuclear model gives no intensity to the strong first line, (010), because P n m a forbids it.
That line is magnetic.

## State the moment

```{literalinclude} ../../../examples/guides/magnetic.py
:language: python
:start-after: "# guide: moment start"
:end-before: "# guide: moment end"
```

`Phase.magnetic_symmetry` takes the BNS number and resolves it to the group's operator list.
The group has to map the nuclear structure onto itself in the phase's own setting, and one that does not is refused by name ([Magnetic space group](../reference/magnetic.md#magnetic-space-group)).
`Moment.from_values` takes the components along a, b and c in μ<sub>B</sub>, the ion whose magnetic form factor applies, and whether to refine.
The seed (1, 0, 1) is the tutorial's.
A free moment of exactly zero is refused, because the magnetic intensity goes as the square of the moment and has no slope at zero.

## Refine the moment

```{literalinclude} ../../../examples/guides/magnetic.py
:language: python
:start-after: "# guide: fit start"
:end-before: "# guide: fit end"
```

<!-- output of examples/guides/magnetic.py -->
```text
with the moment: Rwp 0.063
```

The moment refines as a modulus in μ<sub>B</sub>, `moment.dof0`, and up to two angles inside the directions the site symmetry allows ([Moment components](../reference/magnetic.md#moment-components)).
On this site every direction is allowed, and the angles are measured from the cell axes.
`dof1` is the angle from c, and `dof2` is the azimuth about c, measured from a.
The plan frees the modulus and the angle from c, and leaves the azimuth at its seed of 0.
That keeps the component along b at zero, as the tutorial does.
The first stage frees the moment with the scale and background only, and the second frees every nuclear term with it.

## Read the moment

```{literalinclude} ../../../examples/guides/magnetic.py
:language: python
:start-after: "# guide: read start"
:end-before: "# guide: read end"
```

<!-- output of examples/guides/magnetic.py -->
```text
Mn2 (Mn3+): |m| = 3.56 ± 0.04 μB, supported
polar angle: esd None, 95 % interval includes 90°: True
['MOMENT_ANGLE_STATIONARY']
```

The modulus is 3.56 ± 0.04 μ<sub>B</sub>.
That is below the spin-only moment of Mn³⁺, 4 μ<sub>B</sub>, by more than three esds.
`supported` means the modulus is above three of its own esds ([Moment evidence](../reference/magnetic.md#moment-evidence)).
A moment refined on a pattern with no magnetic order fails that test.

The angle from c ends about 5° short of 90°, so the moment lies close to a.
At 90° the pattern is even in that angle, so its slope is zero there and an esd read from it would depend on where the solver stopped.
The fit tests whether moving the angle onto 90° costs more than the noise allows.
Here it does not, so the angle carries no esd.
In its place the fit computes the angle's 95 % profile interval, which runs about 10° either side of 90°.
[`MOMENT_ANGLE_STATIONARY`](../reference/diagnostics-structures.md#moment_angle_stationary) reports both, and its message gives the angle's distance from 90° and the interval's ends.

The interval includes 90°, so the data cannot tell this moment from one along a.
Quote it as 3.56(4) μ<sub>B</sub> along a.
The modulus esd assumes the angle sits at 90°, which the message also says.

The full script is `examples/guides/magnetic.py`.

## See also

- [Magnetic refinement](../reference/magnetic.md) lists what a moment declaration may hold, what it refuses, and every field of `MomentEvidence`.
- [How to refit the nuclear model with the moment present](moment.md) covers the nuclear model's share of the magnetic intensity, which can make a moment come out low.
- [How to quote a parameter that ended on its bound](interval.md) explains the profile interval the angle carries.
