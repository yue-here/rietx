# An equation fitted to a trajectory

This page gives `rietx.fit_trajectory`, which fits an equation to one parameter's trajectory after a series: what it takes, which chain it reads, the points it leaves out and the result it returns. A declaration refined across the patterns at once is on [Parametric refinement](parametric.md).

`rietx.fit_trajectory(series, path, expression, variables)` fits an equation to one parameter's trajectory, weighted by its esds, and returns a `TrajectoryFit`.
It is GSAS-II's fit to the sequential table: the equation is fitted after the series, to the points the series kept ([the equation guide](../guides/equation.md#fit-the-equation-to-the-series-trajectory)).

`expression` is text in the [expression grammar](expressions.md) for the value of `path` at each pattern.
Its free names are the keys of `variables`, each an `rx.Parameter` whose `value` is the start, `vary` whether it is fitted and `min` and `max` its bounds, and the coordinates.
`coordinates=` takes the `rx.CoordinateTable` that `refine_multi` takes, one row per pattern of the series.
Without it the series axis, `SeriesResult.x`, is the one coordinate, and the expression calls it `x`.
`path` is any name `SeriesResult.resolve_trajectory` takes, `qpa.<phase>` included.
A step path (`SeriesResult.relative_paths`) is refused, since its values are displacements from where each fit began, and so is an angle path (`SeriesResult.angle_paths`), whose values wrap at a turn.

Under `direction="both"` you name the chain: `chain="forward"`, or `chain="backward"` for `SeriesResult.backward`.
The gap between the two is path dependence, which `SeriesResult.direction_gaps` reports and nothing resolves, so the fit does not pick one.
A one-way series has only the chain it ran, and asking for the other raises.

Two kinds of point are left out, and `TrajectoryFit.skipped` names each as a `TrajectorySkip`, with `TrajectorySkip.position`, `TrajectorySkip.label` and `TrajectorySkip.reason`.
The reason `"quarantined"` is a pattern the chain [quarantined](series.md#quarantine), which joins no median either.
The reason `"no_value"` is a point whose value is not finite, and `"no_esd"` a point with no positive, finite esd, which has no weight.

| Field | Meaning |
| --- | --- |
| `TrajectoryFit.path`, `TrajectoryFit.expression` | what was fitted, as given |
| `TrajectoryFit.chain` | the chain read, `"forward"` or `"backward"` |
| `TrajectoryFit.series_direction` | the series' own `direction` |
| `TrajectoryFit.variables` | one `TrajectoryVariable` per variable, in the order given |
| `TrajectoryFit.covariance` | over the varied variables, scaled as `TrajectoryVariable.esd` is; `None` with no degree of freedom, or where a direction is undetermined |
| `TrajectoryFit.chi2`, `TrajectoryFit.dof`, `TrajectoryFit.reduced_chi2` | Σ((value − fitted)/esd)², the points less the varied variables, and their ratio (`None` at no degree of freedom) |
| `TrajectoryFit.positions`, `TrajectoryFit.n_points` | which entries of the chain were fitted, by position, and how many |
| `TrajectoryFit.fitted` | the equation at each of those points |
| `TrajectoryFit.converged`, `TrajectoryFit.message` | whether the solver converged, and why it stopped |

A `TrajectoryVariable` carries `TrajectoryVariable.name`, `TrajectoryVariable.value` and `TrajectoryVariable.vary`.
`TrajectoryVariable.esd` is √(χ²/ν · (JᵀWJ)⁻¹), scaled as a refined esd is, so a scatter wider than the points' own esds widens it.
Bérar and Lelann's factor, which each pattern's own esds carry for its correlated residuals, is not applied, since the points are separate fits.
`TrajectoryVariable.esd_unscaled` is √((JᵀWJ)⁻¹), the reading of someone who trusts each pattern's esd as it stands.
They differ by √(χ²/ν), and neither is chosen for you.
Both are `None` on a held variable, and on one the trajectory does not move, alone or only together with another, as `a` and `b` in `a + b + k*T`.
`TrajectoryVariable.at_bound` says the solver ended with the value on the variable's own `min` or `max`; its esds are then marginal, as a refined parameter's are.
It is `None` on a held variable.

The result is a fit to the trajectory, not to the patterns.
Each point's esd is conditional on the rest of its own pattern's fit, and a chain's values depend on the direction it walked, which is why the result names the chain.
`print(fit)` leads with both.
