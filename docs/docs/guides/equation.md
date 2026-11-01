(guide-equation)=
# How to refine a cell edge as a function of temperature

Declare the equation with `rietx.ParametricEquation`, give each pattern's temperature in a `rietx.CoordinateTable`, and pass both to `rietx.refine_multi`, which refines the equation's coefficients against every pattern at once.

This is parametric refinement {cite}`stinton2007`.
All the patterns share one residual, as in a joint fit, and the refined parameters are the coefficients of the equation.

## Declare the equation and fit

This fits a straight line a(T) = a₀ + a₁(T − T<sub>ref</sub>) to the seven synthetic LaB6 patterns of [How to fit a temperature series](series.md), whose true cell edge grows by 0.05 % per 100 K:

```{literalinclude} ../../../examples/guides/equation.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/equation.py -->
```text
[1] 4.1628327119 +/- 1.6e-06 Å
[T] 0.0000207819 +/- 8.0e-09 Å/K
form rejected: False (statistic 9.3, cut 11.1)
```

Each term in `terms` is a list of coordinate names: `[]` is the intercept, `["T"]` is linear in T, and `["T", "T"]` would add T².
rietx centres each coordinate on the middle of its range, here 600 K.
So `[1]` is a at 600 K, and the correlation between the intercept and the slope is 0.001.
The true slope is 2.0783 × 10⁻⁵ Å/K, 0.1 esd from the fitted one.

Read the coefficients from `result.parametric`.
The coefficient rows in `result.parameters` are per unit of the centred and scaled temperature, so their numbers differ.
Each pattern's own value of the cell edge is in `result.parameters` as `hist.<k>.phases.0.cell.a`, with an esd propagated from the coefficients.

`refine_multi` takes one instrument per pattern.
By default each pattern keeps its own zero shift, peak widths, background and scale.
If nothing about the mount changed between patterns, share those parameters by passing `sharing=rx.SharingMap(shared=[...])`.
On a ten-pattern synthetic ramp, sharing the zero shift and the profile reduced the slope's esd 2.6 times.

## Check the declared form

The esds assume the equation is the right shape.
After the fit, rietx tests the declared form against freeing the cell edge in every pattern, which costs one Jacobian evaluation and no refit.
`form.tied.statistic` is the fall in χ² the freed cell edges would give, in units of χ²/ν, and `form.tied.cut` is the 95 % point of χ² for that many extra parameters.

To show a rejection, the script fits a second ramp whose true cell edge bows 9.4 × 10⁻⁵ Å below the line at 600 K:

```{literalinclude} ../../../examples/guides/equation.py
:language: python
:start-after: "# guide: bowed start"
:end-before: "# guide: bowed end"
```

<!-- output of examples/guides/equation.py -->
```text
form rejected: True (statistic 501.5, cut 11.1)
['PARAMETRIC_FORM_REJECTED']
```

When the form is rejected, do not quote the coefficients or their esds.
Add the next term (`["T", "T"]`) and fit again, or narrow the equation to the patterns where it holds with `patterns=`.
Fit the same patterns as a series too, and plot the declared line over its trajectory, because the series shows where the data bend.

The test sees the form only where each pattern measures the target.
A pattern that cannot see the phase adds nothing to the statistic, and `PARAMETRIC_TARGET_UNSEEN` names it.

## Evaluate the equation at any temperature

`result.parametric_value` evaluates the equation at any coordinate, with an esd from the coefficients' covariance:

```{literalinclude} ../../../examples/guides/equation.py
:language: python
:start-after: "# guide: value start"
:end-before: "# guide: value end"
```

<!-- output of examples/guides/equation.py -->
```text
a: phases.0.cell.a at T=293 = 4.1564527(29) Å (extrapolating in T; form not rejected)
```

293 K lies below the fitted range of 300-900 K, so the line says it is extrapolating.

## When to declare an equation instead of fitting a series

The figures in this section come from synthetic LaB6 ramps of ten patterns at 300-1200 K, each fitted over twenty noise seeds.

- When every pattern measures the parameter well on its own, the declared line and a straight line through the series' trajectory agree to 0.0012 esd, with esds within 2 %.
  The declaration then gives the coefficients and their esds from one fit, and no extra precision.
- When a phase fades out and the series holds its cell on the faint patterns, the declared line still uses what those patterns carry.
  Its slope scattered 0.72 times as much over the seeds as a line through the points the series kept, about two standard errors from no gain at twenty seeds.
- When the true form is not the declared one, the esds are wrong.
  Fitted as a line to a cell that in truth curved, the truth lay within two esds of the line in 3 % of cases at the faint patterns.

The full script is `examples/guides/equation.py`.

## See also

- [How to fit a temperature series](series.md) gives the trajectory to plot the equation over.
- {ref}`par-parametric-section` in the Theory tab gives the equation and the form test's statistic.
