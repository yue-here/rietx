# Parametric refinement

This page gives how a parameter is declared as an equation of each pattern's coordinates and refined across every pattern at once: the coordinate table and the declaration, the reference and scale, what is refused before a fit, the coefficients a fit reports, the test of the declared form, and the equation evaluated at any coordinate.

A chain measures a parameter once per pattern ([Sequential refinement](series.md)), and a joint fit shares it as one number ([Joint refinement](joint.md)).
Between the two is a parameter that differs from pattern to pattern by an equation you can write down: a cell edge linear in temperature down a ramp, or a cell edge that follows the composition across a combinatorial library.
Declaring the equation puts every pattern in one residual with the equation's coefficients as the refined parameters, which is parametric refinement {cite}`stinton2007`.
Pattern k's value of the target is p<sub>k</sub> = Σ<sub>j</sub> Φ<sub>k,j</sub> c<sub>j</sub>, with Φ built from each pattern's coordinates ({ref}`par-parametric-section`), and each coefficient comes back with an esd from the joint covariance.
[How to refine a cell edge as a function of temperature](../guides/equation.md) runs one from start to finish.

A declaration is a joint fit, so [Joint refinement](joint.md) applies unchanged: Rietveld mode only, one `MultiHistogramRefinement` or `refine_multi` call, an `Instrument` per pattern, and a `SharingMap` deciding what else is shared.
The declaration adds two keywords to both: `coordinates`, a `CoordinateTable`, and `parametric`, a list of `ParametricEquation`.
`coordinates` with no `parametric` is ignored.

## Precision of the coefficients

These figures come from synthetic LaB6 ramps of ten patterns at 300-1200 K, each built with a known a(T) and fitted over twenty noise seeds.

- While each pattern pins the parameter on its own, the joint slope is the straight line through the chain's trajectory, weighted by each pattern's information. It came back a mean 0.0012 esd from that line, with an esd within 2 % of the line's. In this regime the declaration gives the coefficient and its esd in one result, and no extra precision.
- Sharing the instrument across the patterns does add precision. With the zero shift and the profile shared, the slope's esd fell 2.6 times and its scatter over the seeds 2.8 times. A joint fit with every pattern's cell left free got the same gain to within 0.001 esd, so the gain comes from the sharing and not from the declaration. It holds only while nothing about the mount moves between patterns, which a heating stage can break.
- Where one pattern cannot see the parameter on its own, the declaration adds precision itself. A minor phase that dissolved on heating was held in the chain's last five patterns ([A phase that appears part-way](series.md#a-phase-that-appears-part-way)). Against a line through the points the chain kept, the declared line's slope scattered 0.72 times as much over the seeds, about two standard errors from no gain at twenty seeds, and its error at the held patterns was 6.8 × 10⁻⁴ Å against 10.1 × 10⁻⁴ Å. The joint fit uses the little each faint pattern carries, which the chain discards.
- The esd is conditional on the declared form being right. Fitted as a line to a cell that in truth curved, the true value at the held patterns lay within two esds of the declared curve in 3 % of cases. Declare the terms the physics needs, and draw the declared curve over the chain's `SeriesResult.trajectory` before quoting a coefficient.

There is no soft form: no smoothness penalty and no kernel over the coordinates.
In the weak-phase regime, a kernel whose settings were estimated from the chain's trajectory extrapolated into the held patterns worse than the straight line.
One at hand-set good settings gave intervals that covered the truth more often, at no gain in accuracy.

## Coordinate table

`CoordinateTable` holds one row per pattern, in the order the patterns are passed.
The coordinates live beside the patterns rather than inside each declaration, because several declarations can share one table.
They do not live in `PatternData.metadata`, which holds strings.

| Member | Holds |
|---|---|
| `CoordinateTable.columns` | each coordinate's name, mapped to its value in every pattern; `None` is a pattern with no value for it |
| `CoordinateTable.units` | a column's unit, from which a coefficient's unit is built |
| `CoordinateTable.n_patterns` | how many patterns the table describes |

A name must be a single identifier, so that a term can name it, and every column needs one value per pattern.
The coordinates need not be compositions or temperatures: a position on the substrate, a time, a pressure or a field are columns like any other.

## Declaration

`ParametricEquation` declares one target.

| Field | Holds |
|---|---|
| `ParametricEquation.name` | the declaration's name, a single identifier; its coefficients are named variables, `vars.<name>_0`, `vars.<name>_1`, one per term |
| `ParametricEquation.target` | one bare dot-path under `phases.` or `instrument.`, with no glob and no `hist.` scope |
| `ParametricEquation.basis` | `"constant"`, `"polynomial"` or `"design"` |
| `ParametricEquation.terms` | a polynomial's terms, each a list of coordinate names: `[]` is the intercept, and a repeated name is a power |
| `ParametricEquation.design` | a design basis's rows, one per pattern of the subset, in subset order |
| `ParametricEquation.patterns` | the subset the equation holds over, by index into the patterns as passed; `None` is every pattern |
| `ParametricEquation.reference`, `ParametricEquation.scale` | per coordinate, the point a polynomial is centred on and the length it is scaled by |

`ParametricEquation.coefficient_paths` lists the coefficients' dot-paths, `ParametricEquation.n_coefficients` counts them, and `ParametricEquation.coordinates_used` names the coordinates the terms use.

The three bases cover different cases.
`"constant"` is one coefficient, the same in every pattern of the subset: a parameter shared over part of the fit.
Over every pattern it reproduces a plain shared parameter bit for bit, including its esd.
`"polynomial"` is a sum of monomials in the coordinates.
`"design"` is your own matrix, for a spline, a mixture form or anything else linear in its coefficients.
Its columns are in units only you know, so its coefficients are reported as you defined them, with no unit.

The subset keeps an equation inside a phase field.
A property varies smoothly within a field and not across its boundary, so name the patterns the equation holds over.
Outside the subset the target is each pattern's own parameter, refined wherever a stage frees it.
Two fields with an equation each are two declarations on one target with disjoint subsets, each with its own name and its own reference.
A pattern both subsets hold is refused.

A thermal-expansion line down a ramp, declared and resolved without a fit:

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
)])
temperatures = [300.0, 450.0, 600.0, 750.0, 900.0]
instruments = [rx.Instrument.debye_scherrer(wavelength=0.4139) for _ in temperatures]

coordinates = rx.CoordinateTable(columns={"T": temperatures}, units={"T": "K"})
expansion = rx.ParametricEquation(name="a", target="phases.0.cell.a",
                                  basis="polynomial", terms=[[], ["T"]])
joint = rx.MultiHistogramRefinement(lab6, instruments, coordinates=coordinates,
                                    parametric=[expansion])

(resolved,) = joint.parametric
assert resolved.reference == {"T": 600.0} and resolved.scale == {"T": 300.0}
assert resolved.coefficient_paths() == ["vars.a_0", "vars.a_1"]
```

A library is the same declaration over more columns.
Here a cell edge over two independent substitution fractions is linear in each, carries their product, and curves in the first:

```python
import rietx as rx

library = rx.CoordinateTable(columns={
    "x": [0.0, 0.0, 0.1, 0.1, 0.2, 0.2, 0.3, 0.3],
    "y": [0.0, 0.2, 0.0, 0.2, 0.1, 0.3, 0.1, 0.3],
})
surface = rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="polynomial",
                                terms=[[], ["x"], ["y"], ["x", "y"], ["x", "x"]])
assert library.n_patterns == 8
assert surface.n_coefficients == 5
assert surface.coordinates_used() == ["x", "y"]
```

## Reference and scale

A polynomial's terms are evaluated on (z − reference)/scale for each coordinate z.
Left out, the reference is the subset's mid-range and the scale its half-range.
They are computed once, when `MultiHistogramRefinement` resolves the declaration at construction, and stored in the resolved declaration that `MultiHistogramRefinement.parametric` returns.
Centring makes the intercept the target's value at the reference rather than an extrapolation to T = 0 K.
It also removes the correlation between intercept and slope that an off-centre coordinate creates.

Pass that resolved list back for a refit, or for a campaign that has grown.
Every coefficient then keeps its meaning, because Φ is rebuilt from the stored reference and scale.
Pass the original declaration instead, and a new pattern that widens the range moves the reference, so the intercept becomes the value at a different temperature.

### Mixture fractions

Fractions that sum to one are where the defaults mislead.
With an intercept the basis is rank-deficient, since the intercept is the sum of the fractions, and the refusal says so and names the Scheffé form, which drops the intercept.
In the Scheffé form give each fraction reference 0 and scale 1, so each coefficient is the target in the pure end member and the equation is Vegard's law between them.
Left centred, each fraction would be measured from its own mid-range, those points need not lie on the simplex, and the coefficients would lose that meaning.
So a basis with no intercept over fractions that sum to a constant is refused until its reference and scale are stated:

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
)])
instruments = [rx.Instrument.debye_scherrer(wavelength=0.4139) for _ in range(5)]
ternary = rx.CoordinateTable(columns={
    "xa": [0.6, 0.2, 0.2, 0.4, 0.3],
    "xb": [0.2, 0.6, 0.2, 0.3, 0.3],
    "xc": [0.2, 0.2, 0.6, 0.3, 0.4],
})

with_intercept = rx.ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="polynomial",
                                       terms=[[], ["xa"], ["xb"], ["xc"]])
try:
    rx.MultiHistogramRefinement(lab6, instruments, coordinates=ternary,
                                parametric=[with_intercept])
except ValueError as exc:
    assert "Scheffé" in str(exc)
else:
    raise AssertionError("the intercept is the sum of the fractions")

scheffe = rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="polynomial",
                                terms=[["xa"], ["xb"], ["xc"]],
                                reference={"xa": 0.0, "xb": 0.0, "xc": 0.0},
                                scale={"xa": 1.0, "xb": 1.0, "xc": 1.0})
joint = rx.MultiHistogramRefinement(lab6, instruments, coordinates=ternary,
                                    parametric=[scheffe])
assert joint.parametric[0].reference == {"xa": 0.0, "xb": 0.0, "xc": 0.0}
```

## Starting values per pattern

`structure` may be a list, one `Structure` per pattern, wherever the patterns should start from different values: a library whose cells span a few per cent, or a ramp whose first and last patterns are far apart.
The structures are one model with different values.
They must agree on phase count, space group, sites and every shared path, and may differ only where a path is per-histogram: the scales, anything under `instrument.`, a `SharingMap.per_histogram` override, or a parametric target.
The coefficients start from the least-squares fit of the declared form to the targets' starting values, so starting cells placed on the expected line start the coefficients on it.
A shared path whose starting values differ is refused, naming the path, the histograms and the three ways out.

## Refusals

Every refusal is a `ValueError`, raised when the declaration or the `MultiHistogramRefinement` is built, and most name their fix.
A malformed declaration is refused on its own: a name that is not an identifier, a target with a glob, a `hist.` scope or a root other than `phases.` or `instrument.`, an empty `terms` list, a repeated term (in any order of its names), an empty subset or a negative or repeated subset index, a non-positive scale, a `reference` or `scale` naming a coordinate no term uses, design rows of unequal length, a non-finite number, or a field the basis does not take (`terms` on a constant or design basis, `design` on a polynomial one).
The rest need the patterns:

| Refused | Fix |
|---|---|
| a polynomial with no `coordinates`, or a table whose length is not the pattern count | one row per pattern, in the order passed |
| a subset index past the last pattern, or design rows that do not match the subset size | indices of patterns passed, one design row per pattern of the subset |
| a term naming a column the table lacks, or a subset pattern with no value for a coordinate a term uses | give the value, or leave that pattern out of the subset |
| a coordinate taking one value across the subset, or a term that is zero in every subset pattern | drop the term, or give a `scale` if the subset will grow |
| fewer patterns in the subset than coefficients | drop terms or widen the subset |
| a basis whose rank is below its number of terms | drop one term of each collinear set the message names; for fractions summing to one, the Scheffé form |
| fractions summing to a constant in a basis with no intercept, without a stated `reference` and `scale` | state them: 0 and 1 per fraction for the Scheffé form |
| a target that is not a parameter of a subset pattern's model | a path the model has; the message says how to list them |
| a target tied to another path | declare the equation on the source the message names |
| a target locked by symmetry, held by the phase's floating origin, a rigid body's increment or a magnetic moment's degree of freedom | another target: none of these moves as one quantity across patterns |
| a crystallite-size coefficient over patterns at different wavelengths | a subset at one wavelength, or leave the size shared |
| a `"constant"` basis whose subset targets' own bounds have no value in common | bounds that overlap |
| a coordinate degree of freedom whose atom the starting structures place differently | start every pattern with the atom in one place |
| two declarations with one name, a coefficient path that already exists, or two declarations on one target with overlapping subsets | a name each, and disjoint `patterns` per target |
| a list of starting structures whose length is not the instrument count, or which differ in phases, space group or atoms | one `Structure`, or one per histogram of one model |
| starting structures that disagree on a shared path | one value, a per-histogram override, or a declaration on that path |
| a `SharingMap` that makes a coefficient per-histogram | keep `vars.*` shared |

The coefficients are unbounded, unless the basis is `"constant"`, whose one coefficient carries the target's own bounds.
A sum of terms has no box that holds every pattern's target, so a target can leave its own range on some pattern.
That is read after the fit ([Range and visibility warnings](#range-and-visibility-warnings)).

## Fitting a declaration

<!-- api-doc: no-exec — it refines the reader's own patterns -->
```python
result = rx.refine_multi(patterns, lab6, instruments, plan="mccusker_default",
                         coordinates=coordinates, parametric=[expansion])
```

A plan frees the coefficients wherever a stage's glob reaches the target.
So `mccusker_default`'s cell stage, which frees `phases.*.cell.*`, refines `vars.a_0` and `vars.a_1` in the cell's place, and its `StageResult.freed` lists them.
The target is per-histogram in every pattern, so each pattern reports its own value as `hist.<h>.phases.0.cell.a`, with an esd propagated from the coefficients.
What the target drives follows it, such as a cubic cell's `b` and `c`.
Each of those rows names the declaration in `RefinedParameter.equations`, and so does each coefficient's `vars.` row.
A target row's value and esd are the equation's at that pattern's coordinates, and can be far tighter than the pattern measures on its own.
A coefficient that drives a phase no pattern can see is held like the cell it drives, and [`PHASE_UNCONSTRAINED`](diagnostics-refinement.md#phase_unconstrained) names the coefficient.

### Large libraries

Under the default `solver="lm"`, once the stacked Jacobian would pass 256 MiB (`rietx.optimize.blocked.DENSE_JACOBIAN_MAX_BYTES`), a joint fit keeps one block per pattern, against that pattern's own columns, and never builds the stacked matrix.
The step and the esds are unchanged in meaning, and `LSQOutcome.jacobian_layout` records `"dense"` or `"blocked"`.
On a synthetic library at 3000 points a pattern, 300 patterns refined in 1 GiB, where the stacked Jacobian alone would have needed 20 GiB.
`solver="trf"` has no blocked form, so past the threshold it warns and builds the dense matrix.

## Coefficients

`RefinementResult.parametric` holds one `ParametricCoefficient` per coefficient, and is `None` when nothing was declared.

| Field | Holds |
|---|---|
| `ParametricCoefficient.equation`, `ParametricCoefficient.target` | the declaration's name and its target |
| `ParametricCoefficient.term` | the term: `"1"` for the intercept, then `"T"`, `"x*y"`, `"T^2"`; a design column is `"d0"`, `"d1"`, one per column |
| `ParametricCoefficient.path` | the coefficient's dot-path, `vars.<name>_<j>` |
| `ParametricCoefficient.value`, `ParametricCoefficient.esd` | the coefficient per unit of the coordinates themselves, at the reference |
| `ParametricCoefficient.vary` | whether it was refined |
| `ParametricCoefficient.unit` | the target's unit over the term's coordinate units |
| `ParametricCoefficient.reference` | the reference point a polynomial was centred on, `None` for the other bases |

Read the coefficients here, and not off `RefinementResult.parameters`.
The `vars.` rows there are in the table's own units, per unit of the scaled coordinate.
On the seven-pattern synthetic ramp of [How to fit a temperature series](../guides/series.md), at 300-900 K, the slope's row read 0.0062323, in Å per 300 K, where its coefficient read 2.07744 × 10⁻⁵ Å/K, the same number divided by the scale.
A loop over `parameters` can tell those rows by their `RefinedParameter.equations` and their `vars.` path.

An esd of `None` has one of two causes, and `ParametricCoefficient.vary` says which.
Either the coefficient was not free in the last stage, or the joint covariance gave it none because no pattern of the subset carried gradient for it.
A unit of `None` means one of its parts was not recorded.
The target's unit is its family's on the [parameter map](parameters.md), so a cell coefficient over a temperature column in K reads `Å/K` and a `biso` one `Å²/K`.
A coordinate the table gives no unit, or a dimensionless target such as an occupancy, leaves the unit `None`.

### Printed coefficients

`str(result)` prints the coefficients after the stages and diagnostics, one declaration per heading and one term per line, each with its esd in parentheses.
A coefficient that was not free reads `(not free at the answer)`, and one with no esd reads `(no esd: unmeasured)`.
Each declaration closes on its form test ([Form test](#form-test)).
On the seven-pattern ramp:

```text
  parametric coefficients (user units, at each reference):
    a: phases.0.cell.a at T=600
      [1] 4.1628356(16) Å
      [T] 0.0000207744(80) Å/K
      form not rejected: 3.8 within the cut 11.1 (p = 0.58) for 5 directions over 7 of 7 patterns
```

A chain has no coefficients of its own.
`SeriesResult.summary` takes a joint result of the same patterns as `parametric=` and prints the same block after the trajectory.
Under `deliverable="series"` its functional-form row then reads "measured jointly", and adds the equations a form test rejected.
Without `parametric=` the row says the form was not measured.
A `parametric=` result that declared nothing is refused.

<!-- api-doc: no-exec — it reads a chain and a joint fit of the reader's patterns -->
```python
print(series.summary(deliverable="series", parametric=result))
```

### Range and visibility warnings

[`PARAMETRIC_OUT_OF_RANGE`](diagnostics-series.md#parametric_out_of_range) is a warning on `RefinementResult.diagnostics`, one per declaration, when the fitted coefficients put the target outside its own `min` or `max` on some pattern.
`where` names each such pattern's `hist.<h>.` path, and `value` counts them.
Do not quote the target there as a measurement.
Narrow the subset to where the equation holds, lower the polynomial's order, or declare a design basis that stays inside the range.

[`PARAMETRIC_TARGET_UNSEEN`](diagnostics-series.md#parametric_target_unseen) is a warning, one per declaration, when the equation sets its target in patterns that cannot see the target's phase.
A pattern cannot see a phase when its scale is under the support screen that holds a phase's structure in a stage.
There the target's value and esd come from the patterns that do see the phase, carried along the equation, and the form test leaves the pattern out.
`where` names each such pattern's `hist.<h>.` path, and `value` counts them.
Quote the equation's coefficients rather than the target in those patterns.
If the equation should hold only where the phase is measured, narrow the subset to those patterns.
When no subset pattern sees the phase, the warning says the equation itself is not measured, and its coefficients stay where they started.

## Form test

The coefficients' esds assume the declared form is right.
A joint fit tests each declaration at its answer against the alternative that frees the target in every pattern of the subset.
The test is one Jacobian evaluation and no refit: 0.7-0.8 s on 33 patterns of 4168 points, where the fit took 47-117 s.
`RefinementResult.parametric_form` holds one `ParametricFormTest` per declaration, and is `None` exactly when `RefinementResult.parametric` is.

| Field | Holds |
|---|---|
| `ParametricFormTest.equation`, `ParametricFormTest.target` | the declaration's name and its target |
| `ParametricFormTest.n_patterns` | the subset patterns whose own target entered the alternative; a pattern that cannot see the target, or where Φ is zero, is left out |
| `ParametricFormTest.n_subset` | the patterns the subset names; where it is larger than `n_patterns`, the equation sets the target in the rest unchecked |
| `ParametricFormTest.tied` | the reading with every other equation still tied, `None` when a coefficient was not free at the answer |
| `ParametricFormTest.others_freed` | the reading with every other tested equation's target freed too, `None` unless two or more equations were tested |
| `ParametricFormTest.rejected` | the verdict: the `others_freed` reading's where there is one, else the `tied` reading's |
| `ParametricFormTest.provisional_on` | the other tested equations whose verdict is a rejection; while it is not empty, this verdict is provisional |

Each reading is a `ParametricFormReading`:

| Field | Holds |
|---|---|
| `ParametricFormReading.dof` | the directions the alternative adds, `n_patterns` less the coefficients when nothing is degenerate; 0 when there was nothing to test |
| `ParametricFormReading.statistic` | the χ² the alternative would remove, over the answer's χ²<sub>red</sub> |
| `ParametricFormReading.cut` | the 95 % point of χ² for `dof` directions |
| `ParametricFormReading.rejected` | `statistic > cut` |
| `ParametricFormReading.p_value` | the upper tail of χ² for `dof` directions at `statistic`, so a near miss shows on either side of the cut |

The last four are `None` when `dof` is 0 or the answer's χ²<sub>red</sub> is not a positive finite number, and the printed line then reads `form not tested` with the reason.
`RefinementResult.parametric_form_joint` is one more `ParametricFormReading`, of every tested equation at once, and is `None` unless two or more equations were tested.

While the form holds, the statistic follows χ² with `dof` degrees of freedom ({ref}`par-parametric-section`).
`str(result)` closes each declaration with its verdict.
On the seven-pattern ramp with the truth bowed 9.4 × 10⁻⁵ Å below the line at mid-ramp, and a straight line declared:

```text
  parametric coefficients (user units, at each reference):
    a: phases.0.cell.a at T=600
      [1] 4.1627840(16) Å
      [T] 0.0000207735(82) Å/K
      form REJECTED: 591.0 past the cut 11.1 (p < 0.001) for 5 directions over 7 of 7 patterns
```

The same ramp on its true line read 3.8 within the same cut, at p = 0.58.
The line prints a p-value under 0.001 as `p < 0.001`.
A rejected form adds [`PARAMETRIC_FORM_REJECTED`](diagnostics-series.md#parametric_form_rejected), a warning on `RefinementResult.diagnostics` whose `where` names the coefficients and whose `value` is the verdict reading's statistic.
Do not quote those coefficients or their esds.
Add the next term to the basis and refit, or narrow the subset to where the form holds.
A chain over the same patterns shows where the trajectory bends.

### Several equations

A fit with several equations reads each equation twice.
The first reading keeps the other equations tied.
The second frees their targets too, so it does not assume their forms, and it gives the equation's verdict.
On the ZrMo₂O₈ ramp of the Durham TOPAS tutorials (33 patterns), a line on the cubic phase's cell beside lines on the trigonal phase's a and c read:

```text
    cubic_a: phases.1.cell.a at T=842.25
      [1] 9.11157(11) Å
      [T] -0.0000196(14) Å/K
      form REJECTED over 33 of 33 patterns:
        with the other equations freed, REJECTED: 305.6 past the cut 45.0 (p < 0.001) for 31 directions
        with the other equations tied, REJECTED: 269.3 past the cut 45.0 (p < 0.001) for 31 directions
        provisional: 'trig_a', 'trig_c' rejected too, and moved the answer this reading steps from; read it again after fixing and refitting
```

A refit holding only the cubic equation, with both trigonal cells free in every pattern, rejected it too.
The freed reading's gain in χ² was within 0.5 % of the 576.1 that refit removed.
The tied reading assumes the other equations are right, so it can pass an equation that hides behind another equation's misfit.

Two equations whose targets change the pattern alike can each pass with the other freed while both are wrong, because each equation's freed targets absorb the other's misfit.
So the fit is also read once with every tested equation's targets freed together, and that joint reading closes the block:

```text
    the 3 tested equations together: form REJECTED: 466.4 past the cut 116.5 (p < 0.001) for 93 directions
```

One wrong equation among several spreads its misfit over all their directions, so the joint reading adds to each equation's verdict and does not replace it.

Every reading is one linear step from the answer, and a rejected equation's misfit moves that answer.
Beside a badly wrong equation, the other equations' verdicts can then differ from their own refits.
On the ZrP₂O₇ ramp a silicon line was rejected beside an equation crossing a phase transition, while the silicon line's own refit kept it (p 0.92).
On the WO₃ ramp a bent angle passed beside rejected cell edges, while its own refit rejected it.
So a verdict beside a rejected equation names that equation in `ParametricFormTest.provisional_on`, and the printed block says so.
Fix the rejected equation, refit, and read the others again.

When the joint reading rejects and no equation's own verdict does, `PARAMETRIC_FORM_REJECTED` names every tested equation's coefficients.
The data cannot say which form is wrong.
Add the next term to one equation at a time and refit.

An equation can add no direction of its own once the others are freed.
That happens when the other equations' targets already move the pattern every way its own target could.
Its freed reading then has nothing to test, and its verdict is `None` even when its tied reading rejects, because the data cannot tell its misfit from the others'.
The joint warning names such an equation and quotes its tied reading.

### Limits of the form test

The test has two limits.

- It sees the form only where, and as well as, each pattern measures the target. A pattern that cannot see the target adds nothing to the statistic, so an equation carried through patterns where a phase has faded out is not checked there. The verdict line counts the patterns tested against the subset, and `PARAMETRIC_TARGET_UNSEEN` names the patterns left out. On two synthetic ramps, one with a minor phase that faded out and one with a minor phase broad and overlapped, a curved truth on its cell was not rejected in any of 20 seeds. A full untied refit rejected none of them either.
- Each verdict is a test at 95 %, and so is the joint reading. A fit with K equations therefore flags some right equation more often than one time in twenty: 1 − 0.95<sup>K</sup> of the time if the tests were independent, 14 % for three equations. No correction is applied.

## Equation at any coordinate

The coefficients' esds are not enough to evaluate the equation between the patterns or beyond them, because the coefficients are correlated.
`RefinementResult.parametric_equations` holds one `RefinedParametricEquation` per declaration, with the coefficients' covariance, and is `None` exactly when `RefinementResult.parametric` is.
`RefinementResult.parametric_value` evaluates an equation at any coordinate and returns a `ParametricValue`.
On the seven-pattern ramp, on its true line:

<!-- api-doc: no-exec — it reads a joint fit of the seven-pattern synthetic ramp -->
```python
print(result.parametric_value("a", {"T": 293.0}))
```

```text
a: phases.0.cell.a at T=293 = 4.1564579(29) Å (extrapolating in T; form not rejected)
```

| Field | Holds |
|---|---|
| `RefinedParametricEquation.equation` | the declaration as resolved, with its reference and scale filled in; pass it back to refit with the same coefficients |
| `RefinedParametricEquation.unit` | the target's unit, `None` where none is recorded |
| `RefinedParametricEquation.span` | per coordinate a polynomial uses, the lowest and highest value across the subset |
| `RefinedParametricEquation.covariance` | the coefficients' covariance in your units, in coefficient order; `None` when a coefficient has no esd, or when the solve kept no correlation between several coefficients |

The diagonal of `RefinedParametricEquation.covariance` is each `ParametricCoefficient.esd` squared, exactly.
At a pattern's own coordinates the value and esd are that pattern's `hist.<h>.` row.
`RefinedParametricEquation.evaluate` is the same computation, given the coefficients, the form test, the coordinates or design row, and the joint reading directly.
`RefinementResult.parametric_value` raises `KeyError` for a name no declaration has.

| Field | Holds |
|---|---|
| `ParametricValue.equation`, `ParametricValue.target` | the declaration's name and its target |
| `ParametricValue.coordinates` | where the equation was evaluated, empty for a `"constant"` equation and a design row |
| `ParametricValue.row` | the design row a `"design"` equation was evaluated at, `None` for the other bases |
| `ParametricValue.value`, `ParametricValue.esd`, `ParametricValue.unit` | the target there; the esd is `None` when the equation has no covariance |
| `ParametricValue.outside` | the coordinates whose value lies outside the subset's range, empty when none does; `None` for a design row |
| `ParametricValue.form_rejected` | the declaration's form test verdict, `None` where the form was not tested |
| `ParametricValue.provisional_on` | the other declarations the form test rejected, so this verdict is provisional; empty where none was |
| `ParametricValue.joint_rejected` | the joint reading's verdict, `None` where the declaration took part in none |

A `"design"` equation has no coordinates.
Evaluate it with `row=`, one number per coefficient in the units of its design matrix.
`ParametricValue.outside` checks each coordinate on its own.
Over two or more coordinates a point can lie inside each range and still be far from every pattern, and the field does not see that.
The esd assumes the declared form, so read `ParametricValue.form_rejected` beside it, with `provisional_on` and `joint_rejected`.
The printed value says when either applies.
