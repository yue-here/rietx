(guide-formula)=
# How to refine cell edges as Einstein functions of temperature

Write each cell edge as a formula with `rietx.ParametricEquation(basis="expression")`, declare the numbers it refines as variables, and fit every pattern at once with `rietx.MultiHistogramRefinement`.
A variable that two formulas name is one refined number, so the two edges below share one Einstein temperature θ.

A straight line in temperature is linear in its coefficients, and [How to refine a cell edge as a function of temperature](equation.md) fits one.
An Einstein function, a(T) = a₀ + g/(exp(θ/T) − 1), is nonlinear in θ, and needs a formula.

## Declare the formulas and preview them

The script makes seven synthetic rutile patterns from 100 K to 1000 K.
Their true cell edges follow a(T) with a₀ = 4.5870 Å and g = 0.0172 Å, and c(T) with c₀ = 2.9540 Å and g = 0.0141 Å, both with θ = 500 K.
The fit starts θ at 400 K and both g at 0.01 Å:

```{literalinclude} ../../../examples/guides/formula.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/formula.py -->
```text
a: 4.58719 to 4.60733 Å, reads ['vars.a0', 'vars.ga', 'vars.theta']
c: 2.95419 to 2.97433 Å, reads ['vars.c0', 'vars.gc', 'vars.theta']
```

`preview_equations` evaluates each formula at the starting values and fits nothing.
It lists the range of values the target takes across the patterns, and the variables the formula reads.
Both formulas read `vars.theta`, the one shared θ.
A starting value that gives a non-finite cell, such as θ = 0, is listed in `EquationPreview.nonfinite` before any fit.

Each variable is a `Parameter`, so it takes `vary`, bounds and a unit.
The bounds on θ keep it positive.
The formula's grammar is [Expressions](../reference/expressions.md): python's lowercase function names, with angles in radians.

## Fit and read the variables

```{literalinclude} ../../../examples/guides/formula.py
:language: python
:start-after: "# guide: fit start"
:end-before: "# guide: fit end"
```

<!-- output of examples/guides/formula.py -->
```text
a0 = 4.587 +/- 6.2e-06
ga = 0.01720567 +/- 2.6e-05
c0 = 2.954001 +/- 5.3e-06
gc = 0.01410529 +/- 2.1e-05
theta = 500.1692 +/- 0.61
[False, False]
```

Each variable is a row `vars.<name>` in `result.parameters`, in its own unit.
θ came back 500.17 ± 0.61 K, 0.3 esd from its truth, and every other variable lies within 2 esd of its own.
Each pattern's own cell edges are the rows `hist.<k>.phases.0.cell.a` and `hist.<k>.phases.0.cell.c`, with esds through the variables' covariance.
The last line is the form test of each formula.
`False` means freeing the cell edge in every pattern would not have improved the fit by more than chance.

The same variables are listed per formula in `result.parametric`, so θ appears there twice.
Count the free parameters from `result.parameters`.

## Evaluate a formula at any temperature

```{literalinclude} ../../../examples/guides/formula.py
:language: python
:start-after: "# guide: value start"
:end-before: "# guide: value end"
```

<!-- output of examples/guides/formula.py -->
```text
c: phases.0.cell.c at T=300 = 2.9572836(41) Å (form not rejected)
```

The esd comes from the formula's gradient in the variables and their covariance, so it includes the correlation between c₀, g and θ.

## A number per pattern

A formula can also read a variable that takes its own value in each pattern, such as a temperature offset of each pattern from its nominal temperature.
Name it in `SharingMap.per_histogram`, for example `rx.SharingMap(per_histogram=["vars.dT"])`.
[Parametric refinement](../reference/parametric.md#formula-equations) gives the details and a worked declaration.

The full script is `examples/guides/formula.py`.

## See also

- [Parametric refinement](../reference/parametric.md) is the reference for declarations, variables and the form test.
- [Coming from TOPAS](../switching/topas.md#a-parametric-equation-is-a-formula) translates a TOPAS parametric input line by line.
- {ref}`par-formula-section` in the Theory tab gives the formula's derivative and its esd.
