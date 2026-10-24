(guide-series)=
# How to fit a temperature series

Pass the patterns in temperature order to `rietx.refine_sequential` with the temperatures as `x`, read `SeriesResult.diagnostics`, then read each parameter's path across the series with `SeriesResult.trajectory`.

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
  diagnostics: 2 rows, 0 errors; no deliverable given, so none is printed in full
    SEQUENTIAL_PERSISTENT_FINDING: warning under every purpose
    SEQUENTIAL_PERSISTENT_FINDING at instrument.geometry.goniometer_radius_mm: info
    pass deliverable= to summary() for the rows that decide your purpose; every row is in result.diagnostics
  trajectory (T (K)):
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

`SEQUENTIAL_PERSISTENT_FINDING` reports a per-pattern diagnostic that fired on more than half the patterns, in a series of five patterns or more.
Such a finding describes the model, so fix it once for the series.
Given no deliverable, the summary prints each finding on one line; `SeriesResult.summary(deliverable="series")` prints the warning in full, and its message names the code it counts.
Both findings here come from the synthetic setup:

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

## See also

- [How to check a series for path dependence](path.md) runs the chain both ways and refits a suspicious step on its own.
