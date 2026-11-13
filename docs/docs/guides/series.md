(guide-series)=
# How to fit a temperature series

Pass the patterns in temperature order to `rietx.refine_sequential` with the temperatures as `x`, read `SeriesResult.diagnostics` and `SeriesResult.code_counts`, then read each parameter's path across the series with `SeriesResult.trajectory`.

Each pattern gets its own refinement, and each fit starts from the answer of the pattern before it.

## Fit the series

This fits seven synthetic LaB6 patterns from 300 K to 900 K.
`_lab6_ramp.py`, beside the script, makes them from a known model with Poisson noise, and its cell edge grows by 0.05 % per 100 K.
The starting model has the cell 0.1 % too large and the peaks about 20 % too wide.

```{literalinclude} ../../../examples/guides/series.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/series.py -->
```text
SeriesResult: 7 pattern(s), rietveld, direction=forward
  diagnostics: none
  trajectory (T (K)):
    largest step phases.0.cell.a 504.8σ at p001→p002 (series.steps)
    most frequent per-pattern codes: CAPILLARY_OFFSET_UNAVAILABLE on instrument.geometry.goniometer_radius_mm 7 of 7, PATTERN_UNDERSAMPLED 7 of 7 (series.code_counts)
    [1/7] p000 x=300 converged Rwp=0.0409
    [2/7] p001 x=400 converged Rwp=0.0409
    [3/7] p002 x=500 converged Rwp=0.0399
    [4/7] p003 x=600 converged Rwp=0.0405
    [5/7] p004 x=700 converged Rwp=0.0406
    [6/7] p005 x=800 converged Rwp=0.0402
    [7/7] p006 x=900 converged Rwp=0.0404
```

`labels=` names the patterns, and without it they are `p000` to `p006`.
`two_theta_limits=` applies one fit range to every pattern.

## Read the diagnostics first

The series itself reports no finding here.
`SeriesResult.code_counts` counts each per-pattern diagnostic over the series, one row per code and parameter, largest count first.
The summary names the three largest.
A code that fired on most of the patterns describes the model, so fix it once for the series.
Both codes here fired on all seven patterns, and both come from the synthetic setup:

- `CAPILLARY_OFFSET_UNAVAILABLE` says the capillary offsets are held at zero, because the instrument declares no goniometer radius.
  An unmodelled offset moves every cell edge by the same fraction.
  Set `Geometry.goniometer_radius_mm` on the instrument when you know it.
- `PATTERN_UNDERSAMPLED` says the 2θ step is too coarse for quotable intensities.
  Only a new measurement fixes it.

Each pattern's own diagnostics are in `series[k].diagnostics`.

## Read a trajectory

`SeriesResult.trajectory` takes a parameter name and returns its value and esd at each pattern:

```{literalinclude} ../../../examples/guides/series.py
:language: python
:start-after: "# guide: trajectory start"
:end-before: "# guide: trajectory end"
```

<!-- output of examples/guides/series.py -->
```text
Trajectory: phases.0.cell.a, 7 point(s)
  label  T (K)  value
  p000   300    4.1565938(43)
  p001   400    4.1586732(43)
  p002   500    4.1607616(41)
  p003   600    4.1628387(42)
  p004   700    4.1649106(43)
  p005   800    4.1669853(43)
  p006   900    4.1690659(42)
```

Each value lies within 2 esd of the cell edge its pattern was made from.

A pattern that did not refine the parameter has no point in the trajectory, so `len(a)` can be shorter than the series.
`series.plot("phases.0.cell.a")` draws the trajectory with its esds, and `series.write_csv("ramp.csv")` writes every parameter, one row per pattern.

## Check where each fit started

```{literalinclude} ../../../examples/guides/series.py
:language: python
:start-after: "# guide: rungs start"
:end-before: "# guide: rungs end"
```

<!-- output of examples/guides/series.py -->
```text
p000  cold   38 evaluations
p001  warm   15 evaluations
p002  warm   15 evaluations
p003  warm   15 evaluations
p004  warm   15 evaluations
p005  warm   15 evaluations
p006  warm   15 evaluations
```

The first pattern runs the whole plan from your starting model.
Every later one starts from its neighbour's answer and runs the plan as a single stage, then the closing stage, about two-fifths of the work here.
When a warm fit diverges or its Rwp rises well above the series median, the pattern is fitted again from the neighbour's answer with the whole plan, and then from your starting model.
`entry.rung` says which of the three attempts gave its values: `warm`, `warm_staged` or `cold`.

`carry=` limits which parameters start from the neighbour's answer.
A parameter it leaves out restarts from your starting model on every pattern.

## Read the temperatures from your files

<!-- api-doc: no-exec — reads a multi-scan file that does not ship with rietx -->
```python
import rietx as rx

patterns = [rx.read_pattern("ramp.raw", scan=i) for i in range(68)]
temperatures = [float(p.metadata["temperature_k"]) for p in patterns]
```

As of rietx 1.10, the Bruker `.raw` version 3 reader is the only one that records a specimen temperature, in `PatternData.metadata["temperature_k"]`.
`rietx.io.readers.list_scans` lists a file's scans, with the temperature of each, without reading the patterns.
For any other format, read the temperatures from your own log.

## Keep a parameter fixed or tied on every pattern

A hold, a tie or a named variable belongs to one pattern's refinement, so declare it in a `constrain=` function that the series calls before each fit.
[How to keep a parameter fixed whatever the plan frees](hold.md) and [How to tie parameters together](tie.md) show the function.

## Start a subgroup off its parent's cell

A distortion product is often modelled as a subgroup of the parent phase, started at the group–subgroup identity point: for a face-centred cubic parent and its body-centred tetragonal subgroup, a<sub>t</sub> = a<sub>c</sub>/√2 and c<sub>t</sub> = a<sub>c</sub>.
At that point every subgroup line sits under a parent line, so the data cannot judge the subgroup on its own.
Its scale is collinear with the parent's, so whether it counts as seen, and is held, depends on where along that ridge the fit stands rather than on whether the specimen contains it.
In one of the series below it was refined in patterns where it was absent, with no [`PHASE_UNCONSTRAINED`](../reference/diagnostics-refinement.md#phase_unconstrained).
What named it there was `HIGH_CORRELATION` and `FLAT_DIRECTION` on the two scales, at ρ = −1.000.

A fit started at the identity point has to leave it in one direction or the other, and on the series below it chose the wrong direction every time.
The series is synthetic: a Cu parent, and its `I 4/m m m` subgroup present from the fifth of eight patterns with c/(a√2) − 1 = +6.0 × 10<sup>−3</sup>, at 0.15, 0.25 and 0.40 of the parent's scale, over seven noise draws.
A single fit of a pattern with the subgroup present, started at the identity point, ended on the wrong side in 42 of 42 fits.
With the distortion's sign reversed in the data, it ended on the wrong side in 42 of 42 again, so the data pulled the fit away from the truth rather than leaving the choice to chance.
The chain ended on the wrong side in 17 of 21 forward chains and 21 of 21 backward ones.
In 17 of the 21 series both directions agreed on the wrong side, so [`SEQUENTIAL_PATH_DEPENDENT`](../reference/diagnostics-series.md#sequential_path_dependent) named nothing on the subgroup's cell.
The subgroup was not held in any pattern where it was present, so the hold played no part in the failure.

Choose the side by fitting, not by chaining:

1. Take one pattern where the subgroup is present, and fit it twice, starting each fit a few parts per thousand off the identity point, one on each side.
2. Keep the fit with the lower Rwp. On the series above it was the true side in 84 of 84 pairs, 42 for each sign of the distortion. The wrong side's Rwp was 2–3 %, 5–8 % and 14–17 % higher at the three fractions.
3. Chain outward from that pattern, carrying the kept fit's cell.

A start off the identity point given to the chain's first pattern need not survive the patterns where the subgroup is absent, because its cell can drift there.
Two forward chains, one from each side, kept both sides in 10 of the 21 series, and the lower Rwp of the pair was the true side in 13 of 21.

This was measured on one parent–subgroup pair, with one distortion size, one instrument and one start offset (c/(a√2) − 1 = ±3 × 10<sup>−3</sup>), and it is untested beyond that.
It applies to a distortion with one symmetry-breaking direction whose two sides are different structures.
Where the two sides are the same structure, such as a and b exchanging in an orthorhombic subgroup of a tetragonal parent, both starts give the same Rwp and there is nothing to choose.

## See also

- [How to check a series for path dependence](path.md) runs the chain both ways and refits a suspicious step on its own.
