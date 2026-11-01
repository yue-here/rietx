# Sequential refinement

This page gives the calls that fit a series of patterns one after another, the arguments of a series, what crosses from one pattern to the next, the `SeriesResult` they return with its trajectories, the checks against a trend the chain made, and the events and cancellation of a series.

A series is N separate refinements in order, each starting from the answer of the one before.
A joint fit is one refinement whose residual stacks several patterns, and the patterns share the parameters that describe the specimen ([Joint refinement](joint.md)).

|  | Series | Joint fit |
|---|---|---|
| Residual | N of them, solved one at a time | one, with every pattern's points in it |
| What crosses a pattern | the starting values | the shared parameters themselves |
| Answer | a trajectory, such as a(T) or w(t) | one set of numbers, informed by every pattern |
| Used for | an in-situ ramp, a parametric sweep, a tray of specimens | one specimen measured twice, at two wavelengths or on two instruments |
| Entry point | `SequentialRefinement`, `refine_sequential` | `MultiHistogramRefinement`, `refine_multi` |
| Modes | any | Rietveld only |

The question that separates them is whether the specimen changed.
Eight mixtures with different compositions are eight specimens, so their cells are eight measurements and a series is the right shape.
One powder measured at two wavelengths is one specimen, so its cell is one number and a joint fit is the right shape.

Fitting a(T) to a functional form of T across every pattern at once is parametric refinement {cite}`stinton2007`.
It puts every pattern in one residual, so it is a joint fit ([Parametric refinement](parametric.md)).
A chain cannot do it, and a line drawn through a sequential trajectory afterwards is a different measurement.
[How to fit a temperature series](../guides/series.md) runs a series from start to finish.

## Entry points

`SequentialRefinement` takes the starting models once and the patterns at `SequentialRefinement.fit`.
`refine_sequential` is the same run as one call.

<!-- api-doc: no-exec — it refines the reader's own series of patterns -->
```python
import rietx as rx

series = rx.SequentialRefinement(structure, instrument)
result = series.fit(patterns, x=temperatures, x_label="T (K)")

result = rx.refine_sequential(patterns, structure, instrument,
                              x=temperatures, x_label="T (K)")
```

Both return a `SeriesResult`.
The runner keeps more after a fit:

| Attribute | Holds |
|---|---|
| `SequentialRefinement.results_` | each pattern's full `RefinementResult`, with its curves |
| `SequentialRefinement.trees_` | each pattern's history tree |
| `SequentialRefinement.result_` | the `SeriesResult` that was returned |
| `SequentialRefinement.forward_` | under `direction="both"`, the forward chain's `SeriesResult`, set before the backward chain starts; `None` on a one-direction run |
| `SequentialRefinement.backward_` | the backward chain's `SeriesResult`, when one ran |
| `SequentialRefinement.failures_` | the patterns on which every attempt raised, as `SeriesFailure` rows |
| `SequentialRefinement.fitted_structures`, `SequentialRefinement.fitted_instruments` | each entry's refined models, in series order; a pattern that failed has none, so these can be shorter than the patterns |
| `SequentialRefinement.structure`, `SequentialRefinement.instrument` | the package's own deep copies of the models you passed, so a fit does not move your originals |

`SequentialRefinement.forward_` lets an `events=` callback judge the forward trajectory when the first event stamped `series_pass="backward"` arrives.
It carries every diagnostic of the forward chain and none from the comparison of the two chains, and it is not rewritten when the run finishes.

Five settings are constructor arguments, because they describe the whole chain: `backend`, `solver`, `history`, `SequentialRefinement.carry` and `SequentialRefinement.carry_hkl_intensities`.
[Entry points](refinement.md#entry-points) gives where each setting of a single fit goes.

`history` behaves as it does for a single refinement ([The history setting](history.md#the-history-setting)), with one addition.
Given a directory, each pattern's first attempt is written to `<dir>/<label>.jsonl`.
A later attempt on the same pattern writes `<label>.warm_staged.jsonl` or `<label>.cold.jsonl`, and the backward chain of `direction="both"` adds `.backward` before that suffix.
So the tree a refitted pattern's `SeriesEntry.node_id` points into is in the suffixed file.
There is one tree per fit and none for the series.
A tree is pinned to its pattern by a data fingerprint, and that pin stops a node being replayed against the wrong data.
The chain is recorded instead as annotation notes on each tree's root node ([Tags and annotations](history.md#tags-and-annotations)).
The default is `False`, because a long series makes many trees.

### Series coordinate

`x` is the series coordinate: the quantity the experiment varied, or on an in-situ run the point of the experiment.
A vendor file records it where its format has a field for it, and the reader puts it in the pattern's own metadata.

<!-- api-doc: no-exec — reads a multi-scan file that does not ship with rietx -->
```python
import rietx as rx

patterns = [rx.read_pattern("ramp.raw", scan=i) for i in range(68)]
temperatures = [float(p.metadata["temperature_k"]) for p in patterns]
```

`PatternData.metadata` holds strings, so the conversion is yours.
Read the key with `dict.get` and refuse to go on when it is missing.
An absent key is a file that recorded nothing, and not a specimen at ambient temperature.
As of rietx 1.10, the Bruker `.raw` version 3 range header is the only format here with such a field.
A reader does not guess a temperature from an axis named for something else.

`rietx.io.readers.list_scans` answers the same question without reading the patterns.
It returns one `rietx.io.formats.base.ScanInfo` per scan, each carrying its `index`, `n_points`, the stepped range and the temperature where the file gave one.
The temperature also appears in its `label`, since the scans of a reel are otherwise indistinguishable.

### Arguments of `fit`

`SequentialRefinement.fit` and `refine_sequential` take these.

| Argument | Default | Does |
|---|---|---|
| `patterns` | required | the series, in order; each pattern keeps its own σ, and patterns are never pooled |
| `x`, `x_label` | `None`, `"index"` | the series coordinate and its name; without `x` the pattern index is the axis, and with `x` but no `x_label` the name is `"x"` |
| `labels` | `p000`, `p001`, … | a name per pattern, used in messages, tables and history filenames |
| `mode` | `"rietveld"` | as for a single fit: `"rietveld"`, `"lebail"` or `"pawley"` |
| `plan` | `"mccusker_default"` | the plan run on the first pattern and on any pattern refitted from the starting models |
| `refit` | `"single"` | `"single"` collapses the plan into one stage for a warm-started pattern; `"stages"` walks it again |
| `two_theta_limits` | `None` | one fit range, applied to every pattern |
| `direction` | `"forward"` | `"forward"`, `"backward"` or `"both"` ([Forward and backward chains](#forward-and-backward-chains)) |
| `reseed`, `reseed_factor` | `True`, 1.25 | the fence that rejects a bad warm start, and how far above the median Rwp it fires ([Restart ladder](#restart-ladder)) |
| `first_rung_factor` | 3.0 | how much the first attempt may spend, as a multiple of the dearest first attempt this chain has converged; `None` removes the bound |
| `verify_steps` | 0 | how many of the largest steps to re-measure, each by refitting its two patterns cold and independently ([Steps between patterns](#steps-between-patterns)) |
| `prepare` | `None` | `(index, data, structure, instrument) -> None`, called on the warmed models before each pattern's fit |
| `constrain` | `None` | `(index, ref) -> None`, called on each pattern's `Refinement` before its fit, where a tie, a named variable or a hold is declared |
| `on_result` | `None` | `(index, result) -> None`, called with each pattern's full result as it finishes |
| `on_error` | `"carry"` | what a pattern on which every attempt raised does to the chain: `"carry"` warm-starts its successor from the last accepted pattern, `"skip"` starts it cold, `"raise"` ends the chain in the exception |
| `events`, `cancel`, `telemetry`, `label`, `progress` | `None` | as on `Refinement.fit`, per pattern ([Events, history and cancellation](#events-history-and-cancellation)) |

`refit` sets the first attempt on each warm-started pattern, and the ladder may use the full plan later ([Restart ladder](#restart-ladder)).
The staged order keeps early stages well conditioned from a poor starting model, and a converged neighbour is not a poor starting model, so the default collapses the plan.
When the neighbour is not a good start either, the fence catches the pattern whose Rwp jumps past the median.
It does not catch a collapse every pattern shares, because the median rises with it.
With a plan that frees U, V and W, `"single"` settled 1.04-1.29 times above `"stages"` in Rwp on every round-robin mixture after the first, and no pattern was refitted.
What named it was [`SEQUENTIAL_PERSISTENT_FINDING`](diagnostics-series.md#sequential_persistent_finding) on `RESOLUTION_UNCONSTRAINED` for U, V and W, in six or seven of the eight patterns and in none under `"stages"`.

## Carried parameters

`SequentialRefinement.carry` is a list of dot-path globs, matched as `Refinement.set_vary` matches them, naming the parameters carried from one pattern to the next.
The default is `["*"]`, every parameter.
A parameter it leaves out restarts from the starting model on every pattern.

A refined atomic coordinate crosses as its site's displacement.
The degree of freedom a plan frees (`phases.*.atoms.*.dof.*`) is rebuilt at zero for every fit, so the chain carries where the fit moved the atom.
A glob naming either the coordinate or its degree of freedom moves every coordinate the site ties to it, and the atom stays on its special position.
The degree of freedom's value is measured from where its fit began, which in a chain is the previous pattern's answer, so its trajectory is each pattern's step.
Chart the coordinate rows instead.
They carry the same esd, `SeriesResult.steps` lists their steps, and the path-dependence check judges them.

A Le Bail or Pawley pattern's per-hkl intensities are not parameters, so no glob reaches them.
`SequentialRefinement.carry_hkl_intensities` decides whether they cross.
The default, `True`, seeds each warm pattern from its predecessor's intensities, matched by hkl.
With `False`, every pattern's extraction starts afresh, as the first pattern's does.
On a synthetic ten-pattern fluorapatite ramp, the carried and fresh Pawley chains agree to five digits of Rwp on every pattern, and the carried Le Bail chain ends lower, at 3.95 % against 4.29 %.

Carrying everything is cheap.
The eight IUCr round-robin sample-1 mixtures share three phases and one goniometer, while their composition swings from about 1 to 94 wt % across the set.
On rietx 1.9.0 the chain took 365 least-squares iterations against 1214 for the same patterns fitted independently, 3.0 times fewer, at the same weight fractions.

`prepare` is for a parameter estimated afresh from each pattern, which no `carry` glob can express.
Excluding the phase scales from `carry` on that round-robin series would fall back to the first mixture's guess.

### Constraints on every pattern

A tie, a named variable and a hold live on the `Refinement` and in no model.
No `carry` glob reaches them, and `prepare` runs before that `Refinement` exists.
`constrain` is where they go ([How to tie parameters together](../guides/tie.md), [How to keep a parameter fixed whatever the plan frees](../guides/hold.md)).

<!-- api-doc: no-exec — it refines the reader's own series of patterns -->
```python
def constrain(index, ref):
    ref.add_variable("B_site", 0.5, min=0.0, max=5.0)
    ref.tie_equal(["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"],
                  source="vars.B_site")
    ref.hold("phases.0.cell.*")

result = series.fit(patterns, constrain=constrain)
```

Each pattern has its own parameter table, and `tie_equal` resolves its globs against the live one.
Declaring the constraint again on each pattern makes it mean the same thing on all of them.
So the function runs once per fit, and a pattern can be fitted several times: every attempt of the restart ladder calls it, and so does each cold refit `verify_steps` runs.
A raise inside it ends the series, as a raise in `prepare` does.

A held path drops out of that pattern's `SeriesEntry.parameters` and out of the trajectory, because a held value is your input and not a measurement.
On a two-pattern synthetic chain, the trajectory of a held cell edge comes back empty, against two points with esds without the hold.

`vars.B_site` is an ordinary dot-path, so `carry` governs it like any other parameter, and the variable warm-starts from the last accepted pattern.
On a seven-pattern synthetic whose tied `biso` walks from 0.4 to 3.4 Å², that saves about 5 % of the chain's iterations, 176 against 186, and moves no fitted value beyond the fourth decimal.
`carry=["phases.*.cell.*", "vars.*"]` carries exactly what that glob says.
Only the chain knows which pattern was accepted, so a quarantined pattern seeds no successor here either.

A coordinate's degree of freedom tied to a variable is where the two carries meet.
The carried coordinate already holds the variable's fitted displacement.
The chain therefore takes that displacement back out before warming the variable, and the pattern starts where its predecessor left the atom rather than one displacement further on.
On a synthetic LaB6 ramp that start was 0.1996, against the 0.2092 that warming it naively gave.
Leave `vars.*` out of `carry` and the coordinate restarts with its variable.

## Series result

`SeriesResult` is the serialisable answer, a few kB of refined values, esds, agreement indices and diagnostics.
It stores no curves, which for nine patterns come to about 2 MB of JSON already on disk as the input files.
The curves stay on `SequentialRefinement.results_`.

| Member | Holds |
|---|---|
| `SeriesResult.entries` | one `SeriesEntry` per pattern, in series order |
| `SeriesResult.mode` | the mode the series was fitted in |
| `SeriesResult.direction` | `"forward"`, `"backward"` or `"both"` |
| `SeriesResult.backward` | under `"both"`, the reverse chain's own `SeriesResult`; else `None` |
| `SeriesResult.x_label` | the axis name |
| `SeriesResult.diagnostics` | the series diagnostics ([Series diagnostics](#series-diagnostics)) |
| `SeriesResult.steps` | one `SeriesStep` per step of every refined path between consecutive patterns, largest in esds first ([Steps between patterns](#steps-between-patterns)); `None` in a document written before the field existed |
| `SeriesResult.relative_paths`, `SeriesResult.angle_paths` | the paths whose value is a step from where each fit began, and the angle paths ([Paths to plot](#paths-to-plot)) |
| `SeriesResult.failures`, `SeriesResult.n_failed` | the patterns on which every attempt raised, and how many ([Restart ladder](#restart-ladder)) |
| `SeriesResult.provenance` | package version, timestamp and settings, as for a single fit |
| `SeriesResult.x` | the axis: the coordinate given, or the pattern index |
| `SeriesResult.labels` | one label per entry |
| `SeriesResult.rwp` | one Rwp per entry |
| `SeriesResult.n_iterations` | residual evaluations summed over the entries: the reported chain, not the whole run |
| `SeriesResult.summary` | the printed view, which `str(result)` returns ([Printing a result](result.md#printing-a-result)) |

It iterates, indexes and has a length, so `for entry in result` walks the patterns in order.
`SeriesResult.diagnostics` is the place to start reading a series.
A series is where one unread warning multiplies: in the in-situ run this diagnostic comes from, 425 `BOUND_HIT` findings went unread across 68 patterns, and the parameters they named were quoted as a measured trajectory.

### Series entry

`SeriesEntry` is one pattern's place in the series and how its fit went.

| Field | Holds |
|---|---|
| `SeriesEntry.index` | position in the series |
| `SeriesEntry.label` | its name |
| `SeriesEntry.x` | its coordinate, or `None` when none was given |
| `SeriesEntry.status` | `"converged"`, `"max_iter"` or `"diverged"` |
| `SeriesEntry.statistics` | that pattern's own `Statistics` |
| `SeriesEntry.parameters` | the `RefinedParameter` rows the fit determined |
| `SeriesEntry.qpa` | the phase quantities, when the fit produced them |
| `SeriesEntry.phase_agreement` | per-phase `PhaseAgreement` (R<sub>Bragg</sub>, R<sub>F</sub>), empty outside Rietveld mode |
| `SeriesEntry.magnetic` | one `MomentEvidence` per magnetic site ([Magnetic moment across a transition](#magnetic-moment-across-a-transition)) |
| `SeriesEntry.diagnostics` | that pattern's own diagnostics |
| `SeriesEntry.n_iterations` | residual evaluations over every attempt on this pattern that returned a fit |
| `SeriesEntry.reseeded` | the warm start was rejected and the pattern was refitted cold |
| `SeriesEntry.rwp_warm` | the Rwp the first, warm attempt reached, set whenever the ladder escalated |
| `SeriesEntry.rung` | which attempt produced these values: `"warm"`, `"warm_staged"` or `"cold"` |
| `SeriesEntry.rungs_tried` | every attempt made, in ladder order |
| `SeriesEntry.rungs_raised` | the attempts among those whose fit raised, each with `repr` of the exception |
| `SeriesEntry.rwp_fence` | the Rwp limit the fence set at this pattern: `reseed_factor` times the median Rwp of the patterns accepted before it; `None` where no median existed, on the first pattern walked or after every earlier pattern was quarantined |
| `SeriesEntry.above_fence` | the kept attempt is still above `rwp_fence`, so `SEQUENTIAL_RWP_OUTLIER` names it |
| `SeriesEntry.seeded_from` | the index of the pattern whose fitted state seeded this pattern's warm rungs: the last one accepted before it in the walk, which skips a quarantined pattern; `None` where there was no warm start |
| `SeriesEntry.floored` | the moment modulus paths that reached the kept attempt at their floor, because the pattern it warm-started from did not support them; empty when the kept attempt started cold |
| `SeriesEntry.node_id`, `SeriesEntry.tree_id` | where this pattern's history lives |

`SeriesEntry.value` and `SeriesEntry.stderr` look a path up in the entry's parameters and return `None` when it is absent.

`SeriesEntry.rung` and `SeriesEntry.reseeded` answer different questions.
`rung` says where the numbers came from, and the first pattern of a chain is always `"cold"` because it has no predecessor.
`reseeded` says whether the chain was broken here, and only that has a fence.
`"warm_staged"` does not set it, because it is still a warm start.

`SeriesEntry.phase_agreement` does not test whether a minor phase is real.
Both indices are biased towards the model being tested, and a trace phase's index is not comparable with the major phase's ([Structure agreement indices](result.md#structure-agreement-indices)).
In a series the field serves the trajectory: one pattern's R<sub>Bragg</sub> is a value, and sixty of them are a shape.
Whether the data can see a phase at all is measured by [`PHASE_UNCONSTRAINED`](diagnostics-refinement.md#phase_unconstrained), from each phase scale's value over its counting-noise esd.
It reaches an entry through `SeriesEntry.diagnostics`, and aggregates over the chain as `SEQUENTIAL_PERSISTENT_FINDING`, which says what no per-pattern diagnostic can: 42 of 68.
Read R<sub>Bragg</sub> beside that, and beside the weight fraction with its esd.

### A phase that appears part-way

In an in-situ series a product phase is often in the model from the first pattern and in the specimen only from some point on.
Below that point the fit holds the phase's structural parameters, because the data cannot see the phase.
The entries say so three ways:

- `SeriesEntry.parameters` does not list them, because a held parameter was not free, has no esd and did not move.
- `SeriesEntry.diagnostics` carries `PHASE_UNCONSTRAINED`, naming the phase and the stages that held it.
- The fitted model keeps the value you supplied. Read it as your own input.

Above that point nothing is held, including in the pattern where the phase first appears.
If the phase appears while a stage is still solving, that stage lifts the hold and solves again rather than deferring to the next pattern.

`SeriesResult.trajectory` reads the entries' parameter lists, so a held pattern contributes no point.
`Trajectory.x` begins at the onset, and its length is the number of patterns that measured the parameter.

## Trajectories

`SeriesResult.trajectory` returns one parameter's path across the series as a `Trajectory`.

| Member | Holds |
|---|---|
| `Trajectory.path` | the dot-path |
| `Trajectory.x`, `Trajectory.x_label` | the axis and its name |
| `Trajectory.value` | the value at each point |
| `Trajectory.stderr` | its esd, `None` wherever that pattern estimated none |
| `Trajectory.labels` | the pattern label at each point |
| `Trajectory.positions` | which entry of `SeriesResult.entries` each point came from |
| `Trajectory.arrays` | `(x, value, stderr)` as float arrays, a missing esd as NaN |

A pattern where the path is absent has no point.
The gap is a real thing, such as a phase not yet in the model or a stage that did not run.
`len(trajectory)` is therefore the number of points with a value, and not the number of patterns.

`SeriesResult.qpa_trajectory` gives a phase's weight fraction as a percentage, as a `QPATrajectory`.
Its `QPATrajectory.path`, `QPATrajectory.x`, `QPATrajectory.x_label`, `QPATrajectory.value`, `QPATrajectory.stderr`, `QPATrajectory.labels` and `QPATrajectory.positions` read as a `Trajectory`'s.
`QPATrajectory.unmeasured` lists, per point, the phases that pattern quoted no fraction for, and `QPATrajectory.basis_changes` says whether the points are fractions of different sets of phases, as when a reflection crosses the range edge part-way through the series (WP-1958).
`SeriesResult.agreement_trajectory` gives a phase's structure agreement index, with `metric="r_bragg"` (the default) or `"r_f"`.
`SeriesResult.agreement_phases` lists the phases that carry one.
A phase can carry an agreement index without a weight fraction, because a weight fraction needs Z and a molar mass and an R index does not.
Every esd of an agreement index is `None`, because R<sub>Bragg</sub> is a residual and has no covariance entry to propagate from.
`arrays()` turns them into NaN, for which a plot draws no error bar.
Outside Rietveld mode the agreement trajectory is empty.
In Le Bail mode the partition is the fit, and in Pawley mode the intensities are refined, so a zero would read as a perfect fit.

`SeriesResult.resolve_trajectory` is the one call behind these and the moment's trajectory ([Magnetic moment across a transition](#magnetic-moment-across-a-transition)).
It dispatches on a display path's `qpa.`, `r_bragg.`, `r_f.` or `magnetic.` prefix, and passes any other dot-path to `trajectory`.
The plots and the GUI call it.
`SeriesResult.is_derived_path` says whether a display path names one of those four derived curves.

`SeriesResult.plot` plots one or more trajectories against the series axis, and `style="dark"` draws it for a dark page.
It rings a point refitted from the starting models, crosses a `SEQUENTIAL_UNRECOVERED` point, boxes a `SEQUENTIAL_RWP_OUTLIER` point, shades the pair of each step re-measured cold, and tags the title of a path-dependent trajectory.

### Paths to plot

`SeriesResult.paths` lists every parameter path present anywhere in the series, in first-seen order.
`varied_only=True` drops the tied paths.
The default keeps them, because a hexagonal `cell.b` is not free but is as measured as `cell.a`.
On the round-robin series that is 49 paths, 41 of them varied.

`SeriesResult.moved_paths` returns at most `n` display paths (default 6), largest movement first.
Movement is a path's peak-to-peak spread divided by the median of its own esds, so a cell edge does not outrank a weight fraction for being larger in its units.
Only paths that moved at least `min_sigma` esds (default 3) are returned.
The list goes straight to `SeriesResult.plot`:

<!-- api-doc: no-exec — it reads a series the reader has fitted -->
```python
result.plot(result.moved_paths(), path="moved.png")
```

The spread is taken over measured points: a point with an esd, on a pattern that did not diverge.
Three kinds of path are never ranked.
A path with no esd, which includes every agreement index, has no scale to rank on.
A path whose value is a step from where each fit began, a coordinate degree of freedom or a rigid body's rotation, gives way to the coordinate rows it drives.
A tied path that repeats an earlier candidate's values exactly, such as a cubic `cell.b`, is the same curve.
An angle path is spread over the shortest arc that covers its values.
Only the run knows which paths are steps and which are angles, so it records them in `SeriesResult.relative_paths` and `SeriesResult.angle_paths`.
Both are `None` in a document written before they existed, and `moved_paths` then treats no path as either.

### Tables and CSV files

`SeriesResult.to_table` returns `(header, rows)` in wide form, one row per pattern with a value and an esd per parameter.
`SeriesResult.write_csv` writes it, with a tab delimiter for a `.tsv` or `.tab` suffix and a comma otherwise.
The columns are `index`, `label`, the axis, `status`, `rung`, `rwp` and `gof`, then each path followed by its `_esd` column.
`rung` travels beside `status`, because a point refitted from the starting models is a good fit whose start did not come from its neighbour.

`paths=` takes the derived kinds too.
`to_table(paths=["qpa.LaB6"])` exports the weight-fraction curve, and `r_bragg.` and `r_f.` export the agreement indices, all resolved by `SeriesResult.resolve_trajectory`.
A path no pattern carries raises, naming it and listing what does exist.
A kind with no esd by construction, an agreement index, gets no `_esd` column.
A kind that has esds keeps its column even where this series estimated none, because there a blank says that the pattern did not estimate one.

Where a trajectory skips a pattern, the table still has a row for it and leaves the cell empty.
`Trajectory.positions` keeps the two aligned, since neither `x` nor `label` identifies an entry on its own.

The axis column takes `SeriesResult.x_label`, unless that name is already one of the fixed columns, in which case it is `x`.
A series with no coordinate has the `x_label` `"index"`, which is such a name.

## Magnetic moment across a transition

A neutron ramp through T<sub>N</sub> grows a moment from nothing.
The magnetic model is stated once (`Atom.moment` and `Phase.magnetic_symmetry`, [Moments](magnetic.md#moments)), and the chain refines it on every pattern.
The magnetic intensity |F<sub>m</sub>|² is proportional to m², so a moment the data cannot see is a flat direction of the least-squares problem and the fit leaves it near zero.
The report of that is "the data does not support a moment here", and never a small measured moment such as 0.02(1) μ<sub>B</sub>.

Each entry carries the evidence beside the value.
`SeriesEntry.magnetic` is one `MomentEvidence` row per magnetic site, the same rows a single pattern's `FitReport.magnetic` carries ([Moment evidence](magnetic.md#moment-evidence)).
`SeriesEntry.moment` fetches one of them by its `MomentEvidence.path`, the modulus dot-path `phases.*.atoms.*.moment.dof0`, or by its atom label.
Naming nothing takes the only site, and refuses when there are two, because "the moment" is not one quantity on a two-sublattice structure.

`SeriesResult.magnetic_trajectory` is |m| against the axis for one site, and `SeriesResult.magnetic_sites` lists the sites that carry one.
It returns a `MagneticTrajectory`, which is a `Trajectory` with more columns, so it exports and plots through the same code.

| Member | Holds |
|---|---|
| `MagneticTrajectory.x`, `MagneticTrajectory.x_label` | the axis and its name |
| `MagneticTrajectory.value` | \|m\| in μ<sub>B</sub> at each point, from that pattern's own fit |
| `MagneticTrajectory.stderr` | its esd, `None` on every unsupported point |
| `MagneticTrajectory.supported` | per point, whether \|m\| cleared three of its own esds |
| `MagneticTrajectory.held` | the complement of `supported` |
| `MagneticTrajectory.measured` | per point, whether the pattern gave a verdict at all; `False` where the modulus has no esd (it was stated and held, or the pattern could not see the phase) or the fit diverged |
| `MagneticTrajectory.status` | that pattern's fit status, because `supported` is a ratio against a covariance |
| `MagneticTrajectory.labels`, `MagneticTrajectory.positions` | the pattern label at each point, and its index in the series |
| `MagneticTrajectory.atom`, `MagneticTrajectory.ion` | the site and its form-factor key |
| `MagneticTrajectory.path` | the modulus dot-path |
| `MagneticTrajectory.onset` | where the moment stops being supported, as a `MagneticOnset` |

A held point keeps its value and loses its esd.
The value is the modulus the fit reached, and the numerator of the ratio that called the point unsupported.
Deleting it would delete the evidence, and zero would claim a measurement no fit made.
The esd is withheld because an error bar on an unsupported number reads as a small measured moment.
`Trajectory.arrays` hands a plotter NaN there, so no error bar is drawn.
`result.plot("magnetic.Mn")` draws held points hollow and a pattern with no verdict as a cross, and shades the onset bracket.

The onset is read off the verdicts, and never off the values.
A warm-started chain carries a smooth |m| column straight through the transition, so a threshold on the numbers finds wherever the chain relaxed.
The first pattern whose moment is held finds where the data stops carrying one.

| Member | Holds |
|---|---|
| `MagneticOnset.x`, `MagneticOnset.x_esd` | the midpoint of the bracket and half its width |
| `MagneticOnset.bracket`, `MagneticOnset.bracket_labels` | the last released pattern and the first held one |
| `MagneticOnset.sense` | `"falls"` (supported at low x), `"rises"` or `"none"` |
| `MagneticOnset.monotone`, `MagneticOnset.boundaries` | whether there is one boundary, and each boundary as the pair of x values either side of it |
| `MagneticOnset.n_supported`, `MagneticOnset.n_held`, `MagneticOnset.n_unconverged` | the counts over the patterns that gave a verdict |
| `MagneticOnset.n_unmeasured`, `MagneticOnset.unmeasured_labels` | the patterns that gave none, left out of the bracket |
| `MagneticOnset.bracket_verdicts_final` | whether neither bracket pattern owes a supported verdict to a fit that stopped early; `None` where there is no bracket, so ask `is False` |
| `MagneticOnset.path`, `MagneticOnset.atom` | which site it is about |
| `MagneticOnset.note` | the reading in words, including why it is not quotable when it is not |

A pattern that gives no verdict is left out of the bracket rather than read as held.
A closed-shutter frame is the plain case: the phase is invisible, its structural paths are held for the stage, and the modulus comes back with no esd.
Counted as held, such a frame one step below T<sub>N</sub> would end the bracket at itself, a confident onset one pattern early.
Left out, the bracket spans it and is wider, and `MagneticOnset.note` names it.

`MagneticOnset.x_esd` is the spacing of the measurements, not a fitted uncertainty.
A ramp in 50 K steps cannot place T<sub>N</sub> better than ±25 K however good each fit is.
Nothing here fits m ∝ (1 − T/T<sub>N</sub>)<sup>β</sup>.
That form is nonlinear in its coefficients, and the exponent is yours to fit to the trajectory.
[`SEQUENTIAL_MOMENT_HOLD`](diagnostics-series.md#sequential_moment_hold) counts the patterns whose moment came back unsupported, and [`SEQUENTIAL_MOMENT_ONSET`](diagnostics-series.md#sequential_moment_onset) gives the bracket.

<!-- api-doc: no-exec — it needs a magnetic model and a ramp through an ordering transition -->
```python
import rietx as rx

result = rx.refine_sequential(patterns, magnetic_structure, instrument,
                              plan=plan, x=temperatures, x_label="T (K)",
                              direction="both")
traj = result.magnetic_trajectory()          # the only site
print(traj)                                  # |m| per pattern, held marked
print(traj.onset)                            # the bracket and its half-width
result.plot("magnetic." + traj.atom, path="moment_vs_T.png")
```

A modulus a pattern did not support is reseeded to its floor before it becomes the next pattern's start.
The pattern's own entry keeps what the fit reached, and the site's direction is preserved.
The modulus stays free, because it is the one direction that is not flat, and a moment climbs back out through it on a cooling ramp.
A modulus with no verdict is not reseeded, so the next pattern starts from the last value a fit judged.

```{warning}
The reseed cannot protect the first pattern above the transition, which is warm-started from a supported neighbour.
Whether that pattern comes back unsupported is a measurement.
Two checks cover it, and you have to ask for both.
Under `direction="both"`, `SEQUENTIAL_MOMENT_ONSET` carries the other chain's bracket and says whether the two agree.
They agree when the brackets overlap, both chains read the same `sense`, and neither bracket owes a verdict to a fit that stopped early.
A bracket only one chain found is a `warning`, and so is one chain supporting every pattern the other holds.
`MagneticOnset.bracket_verdicts_final` catches a supported verdict from a fit that stopped at its iteration cap.
On a synthetic ramp starved to `max_iter=1`, the moment above the transition came back supported and the onset moved to a confident, wrong bracket, with Rwp fine and no other fence firing.
```

## Series diagnostics

A sequential fit is path-dependent by construction.
Every pattern's answer depends on its neighbour's, so one bad pattern's error passes to every successor and still draws a smooth curve.
These diagnostics fence that, and none of them alters a fitted value.
[Series and joint fits](diagnostics-series.md) gives each code's full entry.

| Code | Says |
|---|---|
| `SEQUENTIAL_RESEED` | the warm start was rejected and the pattern was refitted cold |
| `SEQUENTIAL_UNRECOVERED` | the pattern diverged on every attempt; it seeded no successor and joined no median |
| `SEQUENTIAL_RWP_OUTLIER` | every attempt left the pattern above the Rwp fence (with `reseed=False`, only the first, and the message says so); the message quotes its GoF and R<sub>exp</sub> against the last pattern inside the fence |
| `SEQUENTIAL_PATH_DEPENDENT` | under `direction="both"`, forward and backward disagree by more than their esds allow |
| `SEQUENTIAL_PATH_CHECK_INCOMPLETE` | under `direction="both"`, the comparison did not run, or ran on fewer patterns or paths than the series has |
| `SEQUENTIAL_WIDTH_GROWTH` | a phase width reached 3× the first value the series measured above three esds, by more than three combined esds, while GoF reached 2× its own at the same pattern; a width that grows at a flat GoF is real broadening and fires nothing |
| `SEQUENTIAL_MOMENT_HOLD` | how many patterns' moment came back unsupported, and which successors' modulus was reseeded to its floor |
| `SEQUENTIAL_MOMENT_ONSET` | where along the axis the moment stops being supported, as a bracket |
| `SEQUENTIAL_PERSISTENT_FINDING` | a per-pattern code fired in more than half the patterns, so it describes the model |
| `SEQUENTIAL_CANCELLED` | the series stopped before its last pattern ([Events, history and cancellation](#events-history-and-cancellation)) |
| `SERIES_PATTERN_FAILED` | every attempt on a pattern raised ([Restart ladder](#restart-ladder)) |

A per-pattern diagnostic can only say "this pattern", so in a run of 68 it cannot say "42 of 68".
One `BOUND_HIT` is a pattern that hit a bound, while a `BOUND_HIT` in most patterns is a bound that is wrong.
`SEQUENTIAL_PERSISTENT_FINDING` counts each pair of code and parameter over the entries and states the fraction once, in `value`, while the entries still carry every occurrence.
Its threshold is half the series: above it the finding describes the series, and below it the per-pattern diagnostics say everything there is.
It needs a series of `rietx.sequential.MIN_POINTS_FOR_PERSISTENCE` patterns, five, and takes the worst level among the occurrences it counts.
A code about how a pattern was measured, listed in `rietx.sequential.NOT_A_SERIES_FINDING`, is never counted.

### Steps between patterns

`SeriesResult.steps` lists every refined path's change between consecutive patterns, one `SeriesStep` each.
`SeriesStep.path` names the parameter, `SeriesStep.labels` and `SeriesStep.indices` name the pair, earlier first, and `SeriesStep.step` is the signed change, later minus earlier.
`SeriesStep.size_esd` is that step over the later pattern's esd, and `None` where the later fit measured none.
The list is sorted by the size's magnitude, largest first, with the `None` rows last.
The summary prints the first row in its trajectory block.

No step is called a jump, and no diagnostic fires on one.
A step may be a phase transition, a sample shift, a beam dump or a wrong model, and only the sample's history can say which.
A symmetry-mode refinement across the step is what separates a transition from the rest.
Until 1.11 the `SEQUENTIAL_DISCONTINUITY` diagnostic flagged a step over five times the path's median and three combined esds; no measurement set either number, so the list replaced it.

`verify_steps=k` re-measures the k largest steps.
Each step's two patterns are refitted cold and independently, with no warm start and no neighbour, and `SeriesStep.cold_ratio` is the cold step over the chain's ([How to check a series for path dependence](../guides/path.md)).

<!-- api-doc: no-exec — it refines a whole series and then refits the largest steps -->
```python
result = rx.refine_sequential(patterns, structure, instrument, x=temperatures,
                              verify_steps=3)
```

Near 1 the step is in the data.
Near 0 the chain made it, because the two patterns agree when nothing carried an error between them.
The ratio is signed, so a cold pair that stepped the other way reads about −1.
`cold_ratio` stays `None` on a step the check did not reach, and on one whose cold pair raised or did not determine the path.
The refits are separate `Refinement` runs writing their own `<label>.verify` histories, and no fitted value, `rung` or median moves because of one.
`verify_steps` takes a count; `True` is refused, and so is a negative number.

It is off by default.
A cold fit runs the full staged plan from the starting models, and k steps run up to 2k of them, once per pattern, since two paths stepping between the same pair share a refit.
On a 68-pattern thermal ramp with four steps over four patterns, the chain took 11.6-12.0 s and the chain with the check 12.1-12.2 s, 5 % more.
The time scales with the patterns refitted, not with the series length.

A step into or out of a pattern the fence rejected, `SEQUENTIAL_UNRECOVERED` or `SEQUENTIAL_RWP_OUTLIER`, is left out of the list, because the pattern already has its own code.
In a 24-pattern ramp with one blank frame, the blank's cell was fitted to noise and stepped 33 times the median, and a cold refit confirmed that step at 1.00, because two cold fits reproduce the same noise.
The steps are dropped, never bridged, because a bridge over several rejected patterns spans that many steps.
A path whose value is a step from where its fit began, in `SeriesResult.relative_paths`, has no rows, and a moment angle's step is taken modulo a turn.

### Restart ladder

A rejected warm fit escalates one attempt at a time: the collapsed warm refit, then the full staged plan from the warm state, then the full staged plan from the starting models.
Under `refit="stages"` the first attempt already is the staged warm fit, so the ladder has two attempts, `"warm_staged"` and `"cold"`, and `"warm"` never appears.
Each attempt runs only when the fence still fires on the best attempt so far, and the entry keeps the best.
`SeriesEntry.rungs_tried` names the attempts, and `SeriesEntry.n_iterations` sums those that returned a fit.
The middle attempt matters most.
Throwing a warm start away roughly triples the work, and before the middle attempt existed that work went on a start not shown to be the problem.

What triggers the ladder is divergence, or an Rwp above `reseed_factor` times the median of the accepted patterns.
Each trigger is a property of this pattern's own fit, readable the moment it finishes, and something a different start could plausibly fix.
A guard finding such as `HIGH_CORRELATION` is neither, since it fires on converged patterns and no attempt changes the model or data behind it.
A step's size is a property of the finished trajectory, so making it a trigger would mean walking a finished chain again.

The first attempt is bounded, because it is a bet rather than the answer.
Its budget is `first_rung_factor` times the dearest first attempt this chain has already converged, and it applies once three have.
Under `refit="stages"` the bound does nothing.
A first attempt that spends its budget escalates, and the next attempt starts from the same warm state, so a bounded chain reports the values it would have reported without the bound.
On the benchmark's ten-pattern series, the solver made 1603 evaluations without the bound and 1395 with it, both converging to Rwp 0.01943 with every accepted value identical.
On the eight-mixture round-robin series the two runs are identical to the evaluation.
`first_rung_factor=None` reproduces a pre-1.1 run.

An attempt whose fit raises has lost in the same sense as a diverged one, and the ladder escalates past it the same way.
`SeriesEntry.rungs_raised` records what each such attempt raised, and `SeriesEntry.rwp_warm` is `None` when the warm attempt was one of them.
The case that needs this is a neighbour that converged with a cell far outside the physical range.
Every warm attempt inherits that cell, and the reflection enumerator refuses it before the fit starts, while the cold attempt starts from the starting models.

A pattern on which every attempt raised has no entry.
It is recorded in `SeriesResult.failures` with a [`SERIES_PATTERN_FAILED`](diagnostics-series.md#series_pattern_failed) warning, and the `on_error` policy decides what the chain does next.
Each `SeriesFailure` carries the pattern's `SeriesFailure.index` and `SeriesFailure.label`, and `SeriesFailure.exception` is the last attempt's exception as `repr`.
`SeriesResult.n_failed` counts them, and `SequentialRefinement.failures_` is the same list on the runner, where to read it after catching the exception `on_error="raise"` lets through.
Under the default, `"carry"`, the successor warm-starts from the last accepted pattern, because what failed was this pattern and not the state its neighbour handed it.
A chain that fitted no pattern at all still raises, whatever the policy.
Your own `prepare` and `constrain` are never guarded: a raise there ends the series.

### Quarantine

A fit still `"diverged"` after the last attempt is quarantined, and [`SEQUENTIAL_UNRECOVERED`](diagnostics-series.md#sequential_unrecovered) names it.
Its successor warm-starts from the last accepted pattern, and the reseed median never sees the failure.
Otherwise one failure would seed its neighbour with a bad start and drag the median that decides every later trigger.

A pattern that converged but stayed above the Rwp fence on every attempt is reported and not quarantined.
[`SEQUENTIAL_RWP_OUTLIER`](diagnostics-series.md#sequential_rwp_outlier) names it, and it seeds its successor and joins the median like any accepted pattern.
Rwp cannot say why it rose.
Near a converged fit Rwp is GoF times R<sub>exp</sub>, and three measured causes divide between the two factors:

- A blank frame has a GoF like its neighbours' (1.00 against 1.06) and an R<sub>exp</sub> four times theirs, because it is background and noise, fitted perfectly.
- A correct model over counts that fell 4× also keeps its GoF and doubles its R<sub>exp</sub>. It is a sound measurement.
- An unmodelled phase raises the GoF: 16.7 against 1.04.

Quarantined, a lasting change could never become the chain's new normal.
On a 24-pattern ramp whose counts fell from pattern 6, quarantine made every later pattern climb the ladder, with 55 % more iterations, and flagged all 18 rather than 7.
With an unmodelled phase from pattern 6 the extra was 107 %.
On the blank frame, quarantine saved 2-8 % of the chain, and the values were identical either way.
The message's GoF and R<sub>exp</sub> against the last pattern inside the fence tell the causes apart.
The fence follows the median, so a run of outliers that stops is a lasting change the median caught up with.

### Forward and backward chains

`direction="both"` runs the series forward and backward and compares the two trajectories.
`SeriesResult.entries` are the forward ones, and the comparison arrives as [`SEQUENTIAL_PATH_DEPENDENT`](diagnostics-series.md#sequential_path_dependent) diagnostics, one per parameter that disagrees ([How to check a series for path dependence](../guides/path.md)).

It is the only check that separates a measured trajectory from an ordering artefact, and on real data it is selective.
On the round-robin series it flagged nine parameters, every one a peak-shape term: `phases.*.lor_size`, `gauss_size`, `gauss_strain`, `lor_strain`, `instrument.profile.x` and `instrument.geometry.axial_sl`.
It flagged no cell parameter and no scale.

The σ multiples in those messages are ratios to a fitted esd.
A parameter near zero with an esd near zero reports a spread of thousands of σ with no physical size, so read the two values the message quotes.
The trajectory the messages compare against is `SeriesResult.backward`, the reverse chain's own `SeriesResult`, and `SequentialRefinement.backward_` is the same object.
Its own `backward` and `provenance` are `None`, its `steps` are its own and never re-measured cold, and its `diagnostics` hold only the moment diagnostics.
The comparison and every other series diagnostic are on the forward result.

No `SEQUENTIAL_PATH_DEPENDENT` finding is also what a comparison that never happened would give, so a comparison that did not run says so.
When the forward chain was cancelled, or the backward chain was cancelled or raised, [`SEQUENTIAL_PATH_CHECK_INCOMPLETE`](diagnostics-series.md#sequential_path_check_incomplete) fires at `warning`, naming the chain and the pattern it stopped on.
When the comparison ran on less than the series, the same code fires at `info`, and `where` names the patterns one chain has no entry for, or the paths no pattern has an esd for in both chains.
So no finding with neither of these present means the comparison was made and found nothing.
A backward chain's own failures are on `result.backward.failures`.
Its raise under `on_error="raise"` keeps the forward chain, which is on `SequentialRefinement.result_` and on the exception as `series_result`.

`SeriesResult.n_iterations` counts the chain the result reports, the forward one under `direction="both"`.
The backward chain is a second complete set of fits, and `result.backward.n_iterations` counts it.

## Events, history and cancellation

`events=` and `cancel=` act per pattern.
Every event a pattern's fit emits is forwarded with its place in the series stamped into the event's `data`: `series_index`, `series_label`, `series_n` and `series_pass`, plus `series_rung` and `series_cold` on a restart.
`series_pass` is `"forward"`, `"backward"` or `"verify"`, the last for the refits `verify_steps` runs.
These are added fields on existing kinds, so no event kind is new and the event schema version does not move ([Events](refinement.md#events)).
Read `data` with `.get`, and "pattern k of N" off `fit_start`.
`progress=` stamps each line with the pattern's place ([Progress lines](result.md#progress-lines)), and `label=` names the whole series' run directory ([Recording and run names](refinement.md#recording-and-run-names)).

Cancelling a series returns what completed rather than raising ([Cancellation](refinement.md#cancellation)).
The pattern in flight is abandoned by `Refinement.fit` itself, with no node, no commit and its models restored.
The patterns already walked are finished fits with committed nodes, and raising would throw them away.
[`SEQUENTIAL_CANCELLED`](diagnostics-series.md#sequential_cancelled) says how many of how many patterns were reached.
A truncated series and a finished one are the same shape, so check for it before reading the last entry as the end of a ramp, or a slope over the entries as a slope over the experiment.
