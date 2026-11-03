(guide-moment)=
# How to refit the nuclear model with the moment present

Take the nuclear model from a pattern that has no moment in it, or refit every nuclear term in a fit that carries the moment, and only then read the moment.
A nuclear model fitted to the ordered pattern with no moment in it can absorb some of the magnetic intensity, and the moment that follows can come out low.
On the one specimen below it did, by about two esds.

[`solve_magnetic`](../reference/magnetic.md#solve_magnetic) does neither for you.
It refits its own nuclear reference under the stages you give it, so the nuclear model it starts from is the one you hand it, and it never goes back to refit that model with the moment present.
Both routes below do that by hand with the shipped API.

## Why the order matters

On a k = 0 structure the magnetic reflections sit on the nuclear ones.
A nuclear fit to that pattern has to explain the magnetic intensity too, and it does so with the terms that scale intensity: the scale factor, the displacement parameters, extinction.
A moment fitted afterwards, with those terms held at the values that absorbed it, finds less intensity left to explain.

The FullProf magnetic-structure tutorial avoids this by refining the nuclear model on a pattern above the ordering temperature.
It then fixes the structural parameters below it and holds the scale factor ([Rodríguez-Carvajal, magnetic structure tutorial](https://neutrons2.ornl.gov/conf/2014/magstr/docs/Tutorial_Magnetic_Structures.pdf)).

## Route 1: a pattern above the ordering temperature exists

Fit that pattern first.
Take its model into the ordered pattern and hold every nuclear term that temperature does not move.
Free the background and the terms it does move, which are the zero and the lattice parameters.
Then hand `solve_magnetic` a plan whose stages free the moment and those terms, and nothing else.

This uses the Cr₂WO₆ patterns from the GSAS-II *Magnetic-II* tutorial, stored in `tests/data/`: 4 K, below the ordering temperature, and 150 K, above it.
`_cr2wo6_pair.py`, beside the script, reads them and builds the starting model, the ideal trirutile positions, and the six-stage nuclear plan.
The patterns are not in the wheel, so the script runs from a checkout of the repository.

```{literalinclude} ../../../examples/guides/moment.py
:language: python
:start-after: "# guide: reference start"
:end-before: "# guide: reference end"
```

<!-- output of examples/guides/moment.py -->
```text
solved 58.395
|m| = 2.09 ± 0.03 μB
```

The scale factor, the coordinates, the displacement parameters and the profile stay at the 150 K values, because no stage frees them.
The solver refits its nuclear reference under the same stages minus the moment paths, so ΔBIC still compares two models that free the same terms.

Free the zero and the lattice.
Held at their 150 K values as well, the nuclear model does not describe the 4 K pattern: the magnetic fit ends at Rwp 0.23 against 0.115, though the moment barely moves (2.07 μ<sub>B</sub>).
The profile can be freed too: Rwp falls to 0.107 and the moment is 2.10 ± 0.03 μ<sub>B</sub>.
This guide holds it, because the instrument is the same at both temperatures.

## Route 2: no pattern above the ordering temperature

Fit the nuclear model to the ordered pattern, solve, then refit every nuclear term in a fit that carries the moment.
Repeat until the moment stops moving.

The first half is the blind answer.

```{literalinclude} ../../../examples/guides/moment.py
:language: python
:start-after: "# guide: blind start"
:end-before: "# guide: blind end"
```

<!-- output of examples/guides/moment.py -->
```text
solved 58.395
|m| = 2.0 μB
Biso of Cr1 = -1.4 Å²
```

The Cr displacement parameter is negative, which is not a physical value.
It is where the nuclear fit put the magnetic intensity.

The second half takes the winning class back as a structure that carries its moment.
`MagneticSolution.write_magcifs` writes one magCIF per class, and `Structure.from_cif` reads the winner's file.
The magCIF does not carry the scale factor, so the script copies it from the blind fit.
One stage then frees the moment and every nuclear term.

```{literalinclude} ../../../examples/guides/moment.py
:language: python
:start-after: "# guide: alternate start"
:end-before: "# guide: alternate end"
```

<!-- output of examples/guides/moment.py -->
```text
round 1: |m| = 2.1 μB, Rwp 0.105
round 2: |m| = 2.1 μB, Rwp 0.105
scale moved less than its esd
```

The loop stops when the moment moves by less than its own esd between two rounds, and after five rounds whatever it has done.
Both are choices of this script, not settings of rietx.
Here round 1 moves the moment by 0.07 to 0.09 μ<sub>B</sub> (the last digit depends on the platform), more than its esd of 0.04.
Round 2 moves it by less than its esd, so the loop stops there.
How far round 2 moves it depends on the platform too, because it starts from wherever round 1 stopped.

## Read the result

On this pattern the three answers are 2.02 to 2.04 ± 0.05 μ<sub>B</sub> blind (the last digit depends on the platform), 2.09 ± 0.03 with the reference and 2.12 ± 0.04 with the moment present.
The blind moment is 0.05 to 0.07 and 0.09 to 0.11 μ<sub>B</sub> below the other two, about one and two esds, and those two agree within their esds.
This is one specimen with a k = 0 collinear moment, so it shows the effect and does not size it.

The two printed checks say where the intensity went.
The nuclear scale factor moved by about half its esd between the blind fit and the last round, so on this pattern it did not carry the exchange.
A scale that moves by more than its own esd is where to look first.
The displacement parameters carried it: Cr went from −1.4 Å<sup>2</sup> to about 0.4 Å<sup>2</sup>.

A route 2 answer is an estimate until the rounds agree.
If the moment is still moving at the round cap, or the scale has moved by several esds, report both the blind and the last-round moment.

The full script is `examples/guides/moment.py`.

## See also

- [`solve_magnetic`](../reference/magnetic.md#solve_magnetic) refits its own nuclear reference under the stages you give it, which is the step both routes here build on.
- `plan="magnetic_structural"` stages route 2's refit: the moment moduli, then every moment degree of freedom, then the nuclear terms in the standard order, with the moments free to the end ([Plans](../concepts/plans.md)). A plan that frees no moment says so with [`PLAN_FREES_NO_MOMENT`](../reference/diagnostics-refinement.md#plan_frees_no_moment).
- [How to keep a parameter fixed whatever the plan frees](hold.md) is the other way to keep a nuclear term at its reference value: `Refinement.hold` pins it against every stage of every plan, where route 1 leaves it out of the stages.
