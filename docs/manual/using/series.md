# Refining many patterns

There are two ways to have more than one pattern, and they are not variants of
each other. A series is N separate refinements, ordered, each starting from the
one before it. A joint fit is one refinement whose residual is several patterns
stacked together, sharing the parameters that describe the specimen.

|  | Series | Joint fit |
|---|---|---|
| Residual | N of them, solved one at a time | one, with every pattern's points in it |
| What crosses a pattern | the starting values | the shared parameters themselves |
| Answers | a trajectory: a(T), w(t) | one set of numbers, informed by every pattern |
| Use it for | an in-situ ramp, a parametric sweep, a tray of specimens | one specimen measured twice, at two wavelengths or on two instruments |
| Entry point | `SequentialRefinement`, `refine_sequential` | `MultiHistogramRefinement`, `refine_multi` |
| Modes | any | Rietveld only |

The question that separates them is whether the specimen changed. Eight
mixtures with different compositions are eight specimens, so their cells are
eight measurements and a series is the right shape. One powder measured at two
wavelengths is one specimen, so its cell is one number and a joint fit is.

## A series is N refinements, chained

`SequentialRefinement` takes the starting models once and the patterns at
`SequentialRefinement.fit`.

<!-- api-doc: no-exec — builds an eight-pattern chained refinement, minutes of solver time -->
```python
import rietx as rx

series = rx.SequentialRefinement(structure, instrument)
result = series.fit(patterns, x=temperatures, x_label="T (K)")
```

`refine_sequential` is the same run as one call, and it is what most code
wants:

<!-- api-doc: no-exec — same eight-pattern chain as above -->
```python
result = rx.refine_sequential(patterns, structure, instrument,
                              x=temperatures, x_label="T (K)")
```

### Where `x` comes from

`x` is the series coordinate: the quantity the experiment varied, and on an
in-situ run the point of the experiment. A vendor file records it where its
format has a field for it, and the reader puts it in the pattern's own
metadata:

<!-- api-doc: no-exec — reads a vendor reel that is not committed to this repo -->
```python
import rietx as rx

patterns = [rx.read_pattern("ramp.raw", scan=i) for i in range(68)]
temperatures = [float(p.metadata["temperature_k"]) for p in patterns]
```

`PatternData.metadata` holds strings, so the conversion is yours. Read the key
with `dict.get` and refuse rather than substitute when it is missing. An absent
key is a file that recorded nothing, and not a specimen at ambient. Today the
Bruker `.raw` v3 range header is the one format here with such a field; the
others record no specimen temperature, and a reader will not guess one from an
axis named for something else.

`rietx.io.readers.list_scans` answers the same question without reading the
patterns. It returns one `rietx.io.formats.base.ScanInfo` per scan, each
carrying `index`, `n_points`, the stepped range, and the temperature where the
file gave one, which is also what its `label` says, since the scans of a reel
are otherwise indistinguishable from each other.

Both return a `SeriesResult`. The class keeps more: after a fit,
`SequentialRefinement.results_` holds each pattern's full `RefinementResult`
with its curves, `SequentialRefinement.trees_` holds the per-pattern histories,
`SequentialRefinement.result_` is the `SeriesResult` that was returned, and
`SequentialRefinement.backward_` is the backward chain when one was run.
`SequentialRefinement.fitted_structures` and
`SequentialRefinement.fitted_instruments` are each pattern's refined models in
series order, one per pattern, because nothing here is shared.
`SequentialRefinement.structure` and `SequentialRefinement.instrument` are the
package's own deep copies of the models you passed, so your originals are not
moved by the fit.

Four settings are constructor arguments, because they describe the chain rather
than a run of it: `backend`, `solver`, `history`, and
`SequentialRefinement.carry`. [](refining.md) has the full table of which
setting goes where.

`history` behaves as it does for a single refinement ([](history.md)) with one
addition: given a directory, each pattern's tree is written to
`<dir>/<label>.jsonl`. There is one tree per pattern and never one for the
series, because a tree is pinned to its pattern by a data fingerprint, and that
pin is what stops a node being replayed against the wrong data. The chain is
recorded instead as annotation notes on each tree's root node. The default is
`False`: a long series makes a lot of trees.

### What `fit` takes

| Argument | Does |
|---|---|
| `patterns` | the series, in order. Each keeps its own σ; patterns are never pooled |
| `x`, `x_label` | the series coordinate and its name. Without one the pattern index is the axis |
| `labels` | a name per pattern, used in messages, tables and history filenames |
| `mode` | as for a single fit: `"rietveld"`, `"lebail"`, `"pawley"` |
| `plan` | the plan run on the first pattern and on any reseeded one |
| `refit` | `"single"` (default) collapses the plan into one stage for warm-started patterns; `"stages"` re-walks it |
| `two_theta_limits` | applied to every pattern |
| `direction` | `"forward"`, `"backward"`, or `"both"` |
| `reseed`, `reseed_factor` | the fence that rejects a bad warm start, and how far above the median Rwp it fires |
| `first_rung_factor` | how much the first rung may spend before the ladder gives up on it, as a multiple of the most expensive first rung this chain has converged. `None` removes the bound |
| `prepare` | `(index, data, structure, instrument) -> None`, called on the warmed models before each fit |
| `constrain` | `(index, ref) -> None`, called on each pattern's `Refinement` before its fit, where a tie, a named variable or a hold is declared |
| `on_result` | `(index, result) -> None`, called with each pattern's full result as it finishes |
| `on_error` | what a pattern on which every rung raised does to the chain: `"carry"` (default) warm-starts its successor from the last accepted pattern, `"skip"` starts it cold, `"raise"` ends the chain in the exception |
| `events`, `cancel` | as on `Refinement.fit`, per pattern |

`refit` sets the ladder's first rung, which is not the only plan a pattern can
be fitted with. The staged order exists to keep early stages well conditioned
from a poor starting model, and a converged neighbour is not one, so the default
collapses it. When the neighbour turns out not to be a good starting point
either, the fence below catches the pattern whose Rwp jumps past the median.
It does not catch a collapse every pattern shares, because the median rises with
it. With a plan that frees U, V and W, `"single"` settled 1.04-1.29 times above
`"stages"` in Rwp on every round-robin mixture after the first, and nothing was
reseeded. What named it was `SEQUENTIAL_PERSISTENT_FINDING` on
`RESOLUTION_UNCONSTRAINED` for U, V and W, in six or seven of the eight
patterns and in none under `"stages"`.

### What crosses a pattern boundary

`SequentialRefinement.carry` is a list of dot-path globs (fnmatch, the
`Refinement.set_vary` convention) naming which parameters are carried forward.
The default is `["*"]`, meaning everything. A parameter excluded from it
restarts from the initial model on every pattern, and not from its neighbour.

A refined atomic coordinate crosses as its site's displacement. The degree of
freedom a plan frees (`phases.*.atoms.*.dof.*`) is rebuilt at zero for every
fit, so what the chain carries is where the fit moved the atom. A glob naming
either the coordinate or its degree of freedom moves every coordinate the site
ties to it, and the atom stays on its special position. The degree of
freedom's value is measured from where its fit began, which in a chain is the
previous pattern's answer, so its trajectory is each pattern's step. Chart the
coordinate rows instead: they carry the same esd, and they are what the
discontinuity and path-dependence checks judge (WP-1333).

A Le Bail or Pawley pattern's per-$hkl$ intensities are not parameters, so no
glob reaches them. `SequentialRefinement.carry_hkl_intensities` decides whether
they cross the boundary. The default is `True`, which seeds each warm pattern
from its predecessor's intensities, matched by $hkl$. With `False`, every
pattern's extraction starts afresh, the way the first pattern's does. On a
synthetic 10-pattern fluorapatite ramp, the carried and fresh Pawley chains
agree to five digits of Rwp on every pattern. The carried Le Bail chain ends
lower, at 3.95 % against 4.29 % (WP-1459).

Carrying everything is cheap even when it looks reckless. Measured on the eight
IUCr round-robin sample-1 mixtures (three phases, one goniometer, 7251 points
each over 5–150°, and a composition that swings from 1.8 to 94.2 wt % across the
set), the chain took 816 least-squares iterations against 2789 for the same
eight patterns fitted independently, a factor of 3.4, and every pattern
converged on its first rung.

`prepare` is for what a `carry` glob cannot express: a parameter that must be
re-estimated from this pattern rather than either carried or left at its initial
value. Excluding the phase scales from `carry` on that round-robin series would
only fall back to the first mixture's guess, which is not the same thing as
estimating them afresh.

### Declaring a constraint on every pattern

A tie, a named variable and a hold ([](constraints.md)) live on the
`Refinement` and in no model, so no `carry` glob reaches them and `prepare`
runs before that `Refinement` exists. `constrain` is where they go:

<!-- api-doc: no-exec — runs the chain above -->
```python
def constrain(index, ref):
    ref.add_variable("B_site", 0.5, min=0.0, max=5.0)
    ref.tie_equal(["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"],
                  source="vars.B_site")
    ref.hold("phases.0.cell.*")

result = series.fit(patterns, constrain=constrain)
```

Each pattern has its own parameter table, and `tie_equal` resolves its globs
against the live one. Re-declaring per pattern is what makes the constraint
mean the same thing on all of them. The hook therefore runs once per *fit*, and
a pattern can be fitted several times: every rung of the escalation ladder gets
it, and so does the cold refit `verify_discontinuities` performs. A raise inside
it ends the series, as a raise in `prepare` does.

A held path drops out of that pattern's `entry.parameters` and out of the
trajectory, because a held value is what you handed in rather than something
the pattern measured. Measured on a two-pattern synthetic chain: the
trajectory for a held cell edge comes back empty, against two points and
their esds without the hold.

`vars.B_site` is an ordinary dot-path, so `carry` governs it like any other
parameter, and the variable warm-starts from the last accepted pattern. On a
seven-pattern synthetic whose tied `biso` walks from 0.4 to 3.4 Å² that saves
about 5 % of the chain's iterations, 176 against 186, and moves no fitted value
beyond the fourth decimal. Keep it for the declaration: a caller who writes
`carry=["phases.*.cell.*", "vars.*"]` gets what that glob says, and only the
chain knows which pattern was *accepted*, so a quarantined one seeds no
successor here either.

A coordinate's degree of freedom tied to a variable is where the two carries
meet. The carried coordinate already holds the variable's fitted displacement,
so the chain rebases it before warming the variable, and the pattern starts
where its predecessor left the atom rather than one displacement further on:
0.1996 on a synthetic LaB6 ramp, against the 0.2092 that warming it naively
gave. Leave `vars.*` out of `carry` and the coordinate restarts with its
variable.

## What comes back

`SeriesResult` is the serializable answer. It stores summaries rather than
curves: nine patterns' worth of `y_obs`/`y_calc`/`y_background`/`sigma` is
about 2 MB of JSON that is already on disk as the input files, while the
refined values, their
esds, the agreement indices and the diagnostics are what a series is for and are
a few kB. The curves stay reachable on `SequentialRefinement.results_`.

| Member | Holds |
|---|---|
| `SeriesResult.entries` | one `SeriesEntry` per pattern, in series order |
| `SeriesResult.mode` | the mode the series was fitted in |
| `SeriesResult.direction` | `"forward"`, `"backward"` or `"both"` |
| `SeriesResult.backward` | the reverse chain's own `SeriesResult` under `"both"`, else None |
| `SeriesResult.x_label` | the axis name |
| `SeriesResult.diagnostics` | the series-level fences below |
| `SeriesResult.discontinuities` | one `SeriesStep` per `SEQUENTIAL_DISCONTINUITY`, in the same order: the pair the diagnostic names in prose. `None` in a document written before the field existed |
| `SeriesResult.provenance` | package version, timestamp and settings, as for a single fit |
| `SeriesResult.x` | the axis: the coordinate given, or the pattern index |
| `SeriesResult.labels` | one label per entry |
| `SeriesResult.rwp` | one Rwp per entry |
| `SeriesResult.n_iterations` | least-squares iterations summed over the entries: the reported chain, not the run |

It iterates, indexes and has a length, so `for entry in result` walks the
patterns in order.

### One pattern's entry

`SeriesEntry` is that pattern's place in the series and how its fit went.

| Field | Holds |
|---|---|
| `SeriesEntry.index` | position in the series |
| `SeriesEntry.label` | its name |
| `SeriesEntry.x` | its coordinate, or `None` when none was given |
| `SeriesEntry.status` | `"converged"`, `"max_iter"` or `"diverged"` |
| `SeriesEntry.statistics` | that pattern's own `Statistics` |
| `SeriesEntry.parameters` | the `RefinedParameter` rows the fit determined |
| `SeriesEntry.qpa` | the phase quantities, when the fit produced them |
| `SeriesEntry.phase_agreement` | per-phase `PhaseAgreement` (R_Bragg, R_F), empty outside Rietveld mode |
| `SeriesEntry.diagnostics` | that pattern's own diagnostics |
| `SeriesEntry.n_iterations` | iterations over every attempt on this pattern |
| `SeriesEntry.reseeded` | the warm start was rejected and the pattern was refitted cold |
| `SeriesEntry.rwp_warm` | Rwp the first, warm attempt reached, set whenever the ladder escalated |
| `SeriesEntry.rung` | which attempt produced these values: `"warm"`, `"warm_staged"` or `"cold"` |
| `SeriesEntry.rungs_tried` | every rung attempted, in ladder order |
| `SeriesEntry.rungs_raised` | the rungs among those whose fit raised rather than returned, each with `repr` of the exception |
| `SeriesEntry.rwp_fence` | the Rwp limit the fence set at this pattern: `reseed_factor` times the median Rwp of the patterns accepted before it. `None` on the first pattern walked |
| `SeriesEntry.above_fence` | the kept attempt is still above `rwp_fence`, so `SEQUENTIAL_RWP_OUTLIER` names it |
| `SeriesEntry.node_id`, `SeriesEntry.tree_id` | where this pattern's history lives |

`SeriesEntry.value` and `SeriesEntry.stderr` look a path up in that entry's
parameters and return `None` when it is not there.

`SeriesEntry.phase_agreement` is not the test of whether a minor phase is real,
and the temptation to read it as one is why it needs a paragraph. Both indices
are biased towards the model being tested, and a trace phase's is not comparable
with the major phase's at all; {ref}`structure-agreement-indices` has the
mechanism and the in-repo measurement. What the field is for here is the
trajectory. One pattern's R_B is a value, sixty of them are a shape, and
watching a phase's R_B walk across a ramp is a use a single fit cannot make of
it.

The question it looks like it answers has its own channel.
`PHASE_UNCONSTRAINED` measures each phase scale's significance, its value over
its esd against the counting noise, which is whether the data can see this phase
at all. It
reaches an entry through `SeriesEntry.diagnostics`, and aggregates over the
chain as `SEQUENTIAL_PERSISTENT_FINDING`, which says the thing no per-pattern
diagnostic can: 42 of 68. Read R_B beside that and beside the weight with its
esd.

### A phase that appears part-way through

This is the ordinary shape of an in-situ series: a product phase is in the
model from the first pattern and in the specimen only from some point on. Below
that point the fit holds its structural parameters, because they cannot be
measured against a phase the data cannot see, and the entries say so three ways
at once:

* `SeriesEntry.parameters` does not list them. A held parameter was not in the
  free vector, has no esd and did not move, so it is absent rather than present
  with a number beside it.
* `SeriesEntry.diagnostics` carries `PHASE_UNCONSTRAINED`, naming the phase and
  the stages that held it.
* the fitted model keeps the value you supplied. Read it as your own input,
  never as a measurement that happens to agree with it.

Above that point nothing is held and the parameters refine normally, including
in the pattern where the phase first appears, which is the one an operator
reads. If it appears while a stage is still solving, that stage lifts the hold
and solves again rather than deferring to the next pattern.

A trajectory follows from that. `SeriesResult.trajectory` reads the entries'
parameter lists, so a held pattern contributes no point at all. `Trajectory.x`
begins at the onset, and its length is the number of patterns that measured the
parameter rather than the number in the series. Before that, the same trajectory
ran the whole way with a stretch of values that were never measurements.

`SeriesEntry.rung` and `SeriesEntry.reseeded` answer different questions. `rung`
says where the numbers came from, and the first pattern of a chain is always
`"cold"` because it has no predecessor. `reseeded` says whether the chain was
broken here, and only that has a fence. The middle rung does not set it:
`"warm_staged"` is still a warm start, so the chain is unbroken there.

### The trajectory

`SeriesResult.trajectory` returns one parameter's path across the series as a
`Trajectory`.

| Member | Holds |
|---|---|
| `Trajectory.path` | the dot-path |
| `Trajectory.x`, `Trajectory.x_label` | the axis and its name |
| `Trajectory.value` | the value at each point |
| `Trajectory.stderr` | its esd, `None` wherever that pattern estimated none |
| `Trajectory.labels` | the pattern label at each point |
| `Trajectory.positions` | which entry of `SeriesResult.entries` each point came from |
| `Trajectory.arrays` | `(x, value, stderr)` as float arrays, missing esds as NaN |

Patterns where the path is absent are skipped rather than filled. A gap in a
trajectory is a real thing, a phase that was not in the model yet or a stage
that did not run, and inventing a value for it would be the confident wrong
singleton the whole package gates against. `len(trajectory)` is therefore the
number of points that have a value, and not the number of patterns.

`SeriesResult.qpa_trajectory` does the same for a phase's weight fraction,
converted to a percentage, and `SeriesResult.agreement_trajectory` for a phase's
structure agreement index. That takes `metric="r_bragg"` (the default) or
`"r_f"`, the two McCusker indices, with `SeriesResult.agreement_phases` listing
the phases that carry one. A phase can appear there without appearing in the
QPA, because a weight fraction needs Z and a molar mass and a structure R does
not.

```{admonition} An empty esd column is a fact rather than a gap
:class: note

For the other two trajectories a `None` esd means this pattern did not estimate
one. For an agreement index every entry is `None`, always. R_Bragg is a residual
rather than a fitted parameter, so there is no covariance entry to propagate
from. `arrays()` turns them into the NaNs an errorbar ignores, so a plotting
caller needs no special case.

Read a trend rather than a value. A single R_B is not comparable between phases
and a low one is consistent with a self-fulfilling partition. One phase's index
moving across a ramp is a statement about that phase.
```

Outside Rietveld mode the trajectory is empty rather than zero. In Le Bail the
partition is the fit and in Pawley the intensities are refined, so the index
does not exist there and a zero would read as a perfect fit.

`SeriesResult.resolve_trajectory` is the single entry point behind all three.
Hand it a display path and it returns the right curve, dispatching on the
`qpa.` / `r_bragg.` / `r_f.` prefix and falling through to `trajectory` for an
ordinary parameter dot-path. Prefer it to a hand-written conditional: the
plotting and GUI layers each carried their own copy of that conditional until it
became one authority. `SeriesResult.is_derived_path` answers the yes/no behind
that dispatch, which is whether a display path names a derived curve (a QPA or
an agreement index) rather than a refined parameter. A caller that must skip the
forward/backward comparison a residual has no σ for asks it.

`SeriesResult.paths` lists every parameter path
present anywhere in the series in first-seen order. Its `varied_only` argument
drops the tied paths; the default keeps them, because a hexagonal `cell.b` is
not free but is every bit as measured as `cell.a`. On the round-robin series
that is 49 paths, 41 of them varied.

`SeriesResult.to_table` returns `(header, rows)` in the wide form, one row per
pattern with a value and an esd per parameter, and `SeriesResult.write_csv`
writes it, inferring a tab delimiter from a `.tsv` or `.tab` suffix and a comma
otherwise. The columns are `index, label, x, status, rung, rwp, gof`, then each
path followed by its esd. `rung` travels beside `status` because it is the other
half of "how much should I trust this point". A rescued point is a good fit
whose starting values did not come from its neighbour, and a table that hides
that reads as a continuous trajectory.

`paths` takes the derived kinds too. `to_table(paths=["qpa.LaB6"])` exports the
weight-fraction curve, and `r_bragg.` and `r_f.` export the agreement indices,
all three resolved by `SeriesResult.resolve_trajectory`, the same call the plots
and the GUI use. Two consequences. A path no pattern in the series carries
raises, naming it and listing what does exist, rather than returning a column of
blanks. And a kind with no esd by construction gets no `_esd` column at all: an
agreement index is a residual, so its esd column would be empty in every row of
every series. A kind that does have esds keeps its column even where this series
estimated none, because there a blank says that this pattern did not estimate
one.

Where a trajectory skips a pattern, the table still has a row for it and leaves
the cell empty. `Trajectory.positions` is what keeps the two aligned, since a
trajectory is a subsequence of the series and neither `x` nor `label` identifies
an entry on its own.

The axis column takes `SeriesResult.x_label`, unless that name is already one
of the fixed columns, in which case it is `x`. That is what the default hits:
`x_label` is a human label and defaults to `"index"`, which reads correctly as
an axis title for a series with no coordinate but would be the header's second
`index`. The column count, order and meaning do not change either way.

`SeriesResult.plot` plots one or more trajectories against the series axis.

### A moment through an ordering transition

An ordering transition is the series a neutron user runs: one specimen through
T_N, the moment growing from nothing. The magnetic model is stated once
(`Atom.moment` and `Phase.magnetic_symmetry`, {doc}`data`) and the chain
refines it on every pattern. A moment is, however, the one parameter whose
number is not the answer. `|F_m|²` is proportional to `m²`, so a moment the
data cannot see is a flat direction of the least-squares problem and the fit
leaves it at nothing. The honest report of that is "the data does not support
a moment here", never "0.02(1) μ_B".

So each entry carries the evidence, not just the value. `SeriesEntry.magnetic`
is one `MomentEvidence` row per magnetic site, the same rows a single-pattern
`FitReport.magnetic` carries. `SeriesEntry.moment` fetches one of them by its
`MomentEvidence.path` (the modulus dot-path, `phases.*.atoms.*.moment.dof0`)
or by its atom label. Naming nothing takes the only site and refuses when
there are two, because "the moment" is not a well-defined quantity on a
two-sublattice structure.

`SeriesResult.magnetic_trajectory` is |m| against the axis for one site, and
`SeriesResult.magnetic_sites` lists the sites that carry one. What comes back is
a `MagneticTrajectory`. It is a `Trajectory`, so it exports and plots through
exactly the same code, and it adds a few columns and one derived answer:

| Member | Holds |
|---|---|
| `MagneticTrajectory.x`, `MagneticTrajectory.x_label` | the axis and its name |
| `MagneticTrajectory.value` | \|m\| in μ_B at each point, from that pattern's own fit |
| `MagneticTrajectory.stderr` | its esd, which is `None` on every unsupported point |
| `MagneticTrajectory.supported` | per point, whether \|m\| cleared three of its own esds |
| `MagneticTrajectory.held` | the complement, spelled the way the hold rule does |
| `MagneticTrajectory.measured` | per point, whether the pattern gave a verdict at all: False where the modulus has no esd (it was stated and held, or the pattern could not see the phase) or the fit diverged |
| `MagneticTrajectory.status` | that pattern's fit status, because `supported` is a ratio against a covariance |
| `MagneticTrajectory.labels`, `MagneticTrajectory.positions` | the pattern label at each point, and its index in the series |
| `MagneticTrajectory.atom`, `MagneticTrajectory.ion` | the site and its form-factor key |
| `MagneticTrajectory.path` | the modulus dot-path |
| `MagneticTrajectory.onset` | where the moment stops being supported, as a `MagneticOnset` |

```{admonition} A held point keeps its value and loses its esd
:class: important

Both halves are deliberate. The value is the modulus the fit reached, and it is
the numerator of the ratio that called the point unsupported. Deleting it
would delete the evidence, and replacing it with zero would claim a
measurement of zero that no fit made. The esd is withheld because an error bar
on a number the data does not support reads as a small measured moment,
which is the single misreading this whole arm exists to prevent.
`Trajectory.arrays` therefore hands a plotter NaN there and an errorbar draws
nothing; `series.plot("magnetic.Mn")` draws those points hollow, draws a
pattern with no verdict as a cross, and shades the onset bracket.
```

The onset is read off the verdicts, never off the values. A warm-started
chain produces a smooth |m| column straight through the transition, which is
what a warm start is for. A threshold on the numbers therefore locates wherever
the chain relaxed, while the first pattern whose block is held locates where
the data stops carrying a moment.

| Member | Holds |
|---|---|
| `MagneticOnset.x`, `MagneticOnset.x_esd` | the midpoint of the bracket and half its width |
| `MagneticOnset.bracket`, `MagneticOnset.bracket_labels` | the last released pattern and the first held one |
| `MagneticOnset.sense` | `"falls"` (supported at low x), `"rises"`, or `"none"` |
| `MagneticOnset.monotone`, `MagneticOnset.boundaries` | whether there is one boundary, and every switch if not |
| `MagneticOnset.n_supported`, `MagneticOnset.n_held`, `MagneticOnset.n_unconverged` | the counts over the patterns that gave a verdict |
| `MagneticOnset.n_unmeasured`, `MagneticOnset.unmeasured_labels` | the patterns that gave none, left out of the bracket |
| `MagneticOnset.bracket_verdicts_final` | whether either bracket pattern owes a *supported* verdict to a fit that stopped early; `None` where there is no bracket, so ask `is False` |
| `MagneticOnset.path`, `MagneticOnset.atom` | which site it is about |
| `MagneticOnset.note` | the reading in words, including why it is not quotable when it is not |

A pattern that gives no verdict is left out of the bracket rather than read as
held. A closed-shutter frame is the plain case: the phase is invisible, so its
structural paths are held for the stage and the modulus comes back with no esd.
Counted as held, such a frame just below T_N would end the bracket at itself, a
confident onset one pattern early. Left out, the bracket spans it and is wider,
and `MagneticOnset.note` names it.

`MagneticOnset.x_esd` is the spacing of your measurements, not a fitted
uncertainty: a ramp with 50 K steps cannot locate T_N better than ±25 K however
good each fit is. Nothing here fits `m ∝ (1 − T/T_N)^β`. That form is
nonlinear in its coefficients and is a different question; the trajectory is
the deliverable and the exponent is yours to fit to it.

Two diagnostics ride with it, and they are in the fences table below:
`SEQUENTIAL_MOMENT_HOLD` counts the patterns whose moment came back
unsupported, and `SEQUENTIAL_MOMENT_ONSET` gives the bracket.

<!-- api-doc: no-exec — needs a magnetic model and a ramp through an ordering transition -->
```python
import rietx as rx

series = rx.refine_sequential(patterns, magnetic_structure, instrument,
                              plan=plan, x=temperatures, x_label="T (K)",
                              direction="both")
traj = series.magnetic_trajectory()          # the only site
print(traj)                                  # |m| per pattern, held marked
print(traj.onset)                            # the bracket and its ±
series.plot("magnetic." + traj.atom, path="moment_vs_T.png")
```

A modulus a pattern did not support is reseeded to its floor before it becomes
the next pattern's starting point, rather than warm-started from the value
before it. That is what crosses a pattern boundary for a moment. The pattern's
own entry keeps what the fit reached; only the successor's starting point
moves, and the site's direction is preserved. The modulus is never fixed: it
has to stay free, because it is the one direction that is not flat and it is
how a moment climbs back out on a cooling ramp. A modulus with no verdict is
not reseeded, so the next pattern starts from the last value a fit judged.

```{admonition} What that rule does not do
:class: warning

It cannot protect the first pattern *above* the transition, which is
necessarily warm-started from a supported neighbour: whether that pattern comes
back unsupported is a measurement, not a mechanism. Two things check it, and
you have to ask for both. `direction="both"` refines the chain each way and
`SEQUENTIAL_MOMENT_ONSET` then carries the other chain's bracket and says
whether the two overlap, and a bracket only one chain found is a `warning` row
even where the other chain wrote none — as is one chain supporting every
pattern the other holds, where neither has a bracket at all. A moment carried across the transition by one chain's
warm start and not the other's is exactly what a single pass cannot see.
`MagneticOnset.bracket_verdicts_final` catches the other half: a *supported*
verdict from a fit that stopped at its iteration cap may just be a modulus that
had not finished falling. On a synthetic ramp starved to `max_iter=1`, the
moment above the transition came back supported and the onset moved to a
confident, wrong bracket, with Rwp fine and no other fence firing.
```

## The series fences

A sequential fit is path-dependent by construction. Every pattern's answer
depends on its neighbour's, so the method can imprint a trend the data do not
carry: one bad pattern's error is inherited by all its successors, and the
result is a smooth-looking curve. Ten diagnostics fence that, and none of them
alters a fitted value.

| Code | Says |
|---|---|
| `SEQUENTIAL_RESEED` | the warm start was rejected and the pattern was refitted cold, so the chain was not poisoned silently |
| `SEQUENTIAL_UNRECOVERED` | the pattern diverged and stayed diverged after every rung; it seeded no successor and joined no median |
| `SEQUENTIAL_RWP_OUTLIER` | every rung the chain tried left the pattern above the Rwp fence (with `reseed=False` only the first, and the message says so), so the fit kept is not like its neighbours'; the message quotes its GoF and Rexp against the last pattern inside the fence, which say why |
| `SEQUENTIAL_DISCONTINUITY` | a step much larger than the local trend: the science, or a chain failure, and the diagnostic says both |
| `SEQUENTIAL_PATH_DEPENDENT` | with `direction="both"`, forward and backward disagree by more than their esds allow |
| `SEQUENTIAL_PATH_CHECK_INCOMPLETE` | with `direction="both"`, the comparison did not run, or ran on fewer patterns or paths than the series has |
| `SEQUENTIAL_WIDTH_GROWTH` | a phase width reached 3× the first value the series measured while GoF reached 2× its own at the same pattern: the phase is standing in for something the model lacks. A width that grows at a flat GoF is a real broadening and fires nothing |
| `SEQUENTIAL_MOMENT_HOLD` | on how many patterns the moment came back unsupported, and on which successors its modulus was therefore reseeded to its floor |
| `SEQUENTIAL_MOMENT_ONSET` | where along the axis the moment stops being supported, as a bracket; under `direction="both"` it carries both chains' brackets and says whether they overlap |
| `SEQUENTIAL_PERSISTENT_FINDING` | one of the per-pattern codes fired in more than half the patterns, so it is about the model rather than about a pattern; a code about how a pattern was *measured* (`FROZEN_COMPILE_STALE`, listed in `sequential.NOT_A_SERIES_FINDING`) is never counted |

The last one exists because of an arithmetic problem the others do not have. A
per-pattern diagnostic can only say "this pattern". In a run of 68 it therefore
cannot say "42 of 68", and that is the sentence you act on, because one
`BOUND_HIT` is a pattern that hit a bound while a `BOUND_HIT` in most of them is
a bound that is wrong. It counts each (code, parameter) pair over the entries
and states the fraction once, in `value`; the per-entry diagnostics still carry
every occurrence. The threshold is half the series, which is a change of subject
rather than a sensitivity: above it the finding describes the series, below it
the per-pattern diagnostics already say everything there is to say.

```{admonition} For agents
:class: agent

Read `SeriesResult.diagnostics` before any trajectory. A series is where a
single unread warning multiplies: in the episode this diagnostic comes from,
425 `BOUND_HIT`s went unread for two hours across a 68-pattern in-situ run, and
the parameters they named were quoted as a measured trajectory.
```

What to do about each is {doc}`the agent skill <skill>`'s
diagnostic table, which this chapter does not restate.

### Checking a step against two independent fits

`SEQUENTIAL_DISCONTINUITY` names both readings, the science or a chain failure,
and asks you to open that pattern's own fit before choosing one.
`verify_discontinuities=True` runs that check for you. Each flagged step's two
patterns are refitted cold and independently, with no warm start and no
neighbour, and what the pair reproduces goes on the diagnostic as `value`, the
cold step over the chain's:

<!-- api-doc: no-exec — it refines a whole series twice over -->
```python
series = rx.refine_sequential(patterns, structure, instrument, x=temperatures,
                              verify_discontinuities=True)
```

Near 1.0 the step is in the data. Near 0 the chain made it: the two patterns
agree when nothing carried an error between them. The ratio is signed, so a cold
pair that stepped the other way reads as about −1 rather than as a reproduction.
Nothing else changes. The refits are separate `Refinement` runs writing to their
own `<label>.verify` histories, and no fitted value, `rung` or median moves
because of one.

It is off by default because it is not free. A cold fit is the full staged
plan from the initial models, and a series flagging `s` steps pays up to `2s`
of them, once per pattern, since two paths flagged at the same step share a
refit. Measured on a 68-pattern thermal ramp flagging four steps over four
patterns: 11.6-12.0 s for the chain and 12.1-12.2 s with the check, `+5 %`.
The cost scales with the patterns flagged, not with the series length.

Which two patterns a step is between is a field, not only prose.
`SeriesResult.discontinuities` holds one `SeriesStep` per flagged step, in the
diagnostics' order, and `SeriesStep.path` is that diagnostic's `where[0]`.
`SeriesStep.labels` and `SeriesStep.indices` name the pair, earlier first, and
`SeriesStep.step` is the signed change, later minus earlier. The check refits
exactly this pair, and the trajectory plot shades it.

Each path carries at most one flag, the largest step that passes both tests.
A step into or out of a pattern the fence rejected, `SEQUENTIAL_UNRECOVERED` or
`SEQUENTIAL_RWP_OUTLIER`, is left out of that scan, because the pattern already
has its own code. Otherwise its step takes the flag. In a 24-pattern ramp with
one blank frame, the blank's cell was fitted to noise and stepped 33 times the
median. The check confirmed that step at 1.00, because two cold fits reproduce
the same noise, and the real step five patterns later went unreported. The
steps are dropped, never bridged: a bridge over several rejected patterns spans
that many of the series' steps, and on a clean ramp it read as an 8× jump.

### The ladder, and quarantine

A rejected warm fit escalates one rung at a time: the collapsed warm refit,
then the full staged plan from the warm state, then the full staged plan cold.
Each rung runs only when the fence still fires on the best attempt so far, and
the best attempt kept whichever rung produced it. `SeriesEntry.rungs_tried`
names them, so the escalation is auditable, and `SeriesEntry.n_iterations` is
the sum over exactly those.

The middle rung is the one that matters. Throwing a warm start away costs
roughly triple, and before it existed that was being paid for a starting point
that had not been shown to be the problem.

The first rung is bounded, because it is a guess rather than the answer. Its
budget is `first_rung_factor` times the most expensive first rung this chain has
already converged, and it applies only once a few of them have. A chain whose
collapsed refit always works stays well clear of the bound. A first rung
that spends its budget escalates rather than being kept, and the rung it
escalates to starts from the same warm state, so the values a bounded chain
reports are the values it would have reported without the bound. Measured on the
benchmark's ten-pattern series: 1603 solver evaluations without the bound and
1395 with it, both converging to Rwp 0.01943, with every accepted value
identical. On the eight-mixture round-robin series the two runs are identical to
the evaluation. Set `first_rung_factor=None` to reproduce a pre-1.1 run exactly.

A rung whose fit raises, rather than returning a result, has lost in the same
sense as a diverged one, and the ladder escalates past it the same way.
`SeriesEntry.rungs_raised` records what each such rung raised, and
`SeriesEntry.rwp_warm` is `None` when the warm rung was one of them, since it
reached no Rwp. The case that needs this is a neighbour that converged with a
cell far outside the physical range. Every warm rung inherits that cell, and the
reflection enumerator refuses it before the fit starts. The cold rung starts
from the initial models and never sees it. Only a pattern on which every rung
raised has no entry. It is recorded in `SeriesResult.failures` with a
`SERIES_PATTERN_FAILED` warning, and what the chain does next is the `on_error`
policy's choice. Each `SeriesFailure` carries the pattern's `SeriesFailure.index`
and `SeriesFailure.label`, and `SeriesFailure.exception` is the last rung's
exception as `repr`. `SeriesResult.n_failed` counts them, and
`SequentialRefinement.failures_` is the same list on the runner, which is where
to read it after catching an exception from `on_error="raise"`.

By the time a policy is consulted, the last rung tried was a cold fit, unless
`reseed=False` or the pattern was the first one walked. So under the default,
`"carry"`, the successor warm-starts from the last accepted pattern, because
what failed was this pattern and not the state its neighbour handed it. A
series is N separate refinements, and one that cannot be fitted is no reason to
discard the others. A chain that fitted no pattern at all still raises, whatever
the policy, because an empty `SeriesResult` is not an answer. The caller's own
`prepare` and `constrain` are never guarded: a raise there ends the series as
itself.

Quarantine is the other half, and it is about what the chain carries rather than
what it reports. A fit still `"diverged"` after the last rung is neither a
starting point nor a scale, so its successor warm-starts from the last accepted
pattern and the reseed median never sees the failure. Otherwise one failure
would seed its neighbour with rubbish and drag the median that decides every
later trigger, quietly raising the bar for the rest of the series.

A pattern that converged but stayed above the Rwp fence on every rung is
reported and not quarantined. `SEQUENTIAL_RWP_OUTLIER` names it, and it seeds its
successor and joins the median like any accepted pattern. Rwp cannot say why it
rose, and quarantine is the wrong answer for one of the reasons. Near a
converged fit Rwp is GoF times Rexp, and three measured causes divide between
the two factors:

- A blank frame has a GoF like its neighbours' (1.00 against 1.06) and an Rexp
  four times theirs, because it is background and noise, fitted perfectly.
- A correct model over counts that fell 4× also keeps its GoF and doubles its
  Rexp. It is a sound measurement.
- An unmodelled phase raises the GoF: 16.7 against 1.04.

Quarantined, a lasting change can never become the chain's new normal. On a
24-pattern ramp whose counts fell from pattern 6, every later pattern climbed
the ladder, costing 55 % more iterations, and all 18 were flagged rather than
7. With an unmodelled phase from pattern 6 the cost was 107 % more. On the blank
frame, quarantine saved 2-8 % of the chain, and the values were identical either
way. The message quotes the GoF and Rexp against the last pattern before it
inside the fence, which is the reading that tells the causes apart. The fence
follows the median, so a run of these that stops is a lasting change the median
caught up with, not one that went away.

What triggers the ladder is deliberately narrow: divergence, or an Rwp above
`reseed_factor` times the median of the accepted patterns. Two candidates were
considered and rejected, and the reasons are the rule a new trigger has to
satisfy. Guard findings such as `HIGH_CORRELATION` fire legitimately on
perfectly converged patterns, and no rung changes the model or the data that
produced them. A discontinuity is a property of the whole finished trajectory,
so making it a trigger would mean re-walking a finished chain. What the two
accepted triggers share: each is a property of this pattern's own fit, readable
the moment it finishes, and each is something a different starting
point could plausibly fix.

### Running the chain both ways

`direction="both"` runs the series forward and backward and compares the two
trajectories. The reported `SeriesResult.entries` are the forward ones; the
comparison arrives as `SEQUENTIAL_PATH_DEPENDENT` diagnostics, one per parameter
that disagrees.

It is the only check that separates a measured trajectory from an ordering
artefact, and on real data it is selective. On the round-robin series it flagged
nine parameters, and every one of them was a broadening term:
`phases.*.lor_size`, `gauss_size`, `gauss_strain`, `lor_strain`,
`instrument.profile.x` and `instrument.geometry.axial_sl`. No cell parameter and
no scale was flagged. The trajectories anyone would plot from that series were
order-independent, and the widths were not.

Two things to know before reading the σ multiples in those messages. They are
ratios to a fitted esd, so a parameter sitting near zero with an esd near zero
reports a spread of thousands of σ that is not a physical scale. Read the two
values the message quotes rather than the multiple. And the trajectory the
messages compare against is `SeriesResult.backward`, the reverse chain's own
`SeriesResult`, set whenever `direction="both"` completed, so a run made through
`refine_sequential` can read the second trajectory and not only the verdict
about it. Its own `backward` is `None`, which is one extra level rather than a
cycle, and `SequentialRefinement.backward_` is the same object.

Zero `SEQUENTIAL_PATH_DEPENDENT` findings is also what you get when the
comparison never happened, so a comparison that did not run says so. When the
forward chain was cancelled, the backward chain was cancelled, or the backward
chain raised, `SEQUENTIAL_PATH_CHECK_INCOMPLETE` fires at `warning`, naming the
chain and the pattern it stopped on. When it ran on less than the series, the
same code fires at `info`. In that case `where` names the patterns one chain
has no entry for, or the paths some chain measured that no pattern could judge,
because no pattern has an esd for them in both chains. So zero findings with
neither of these present means the comparison was made and found nothing. A
backward chain's own failures are on `result.backward.failures`. Its raise
under `on_error="raise"` no longer costs the forward chain, which is on
`SequentialRefinement.result_` and on the exception as `series_result`.

`SeriesResult.n_iterations` counts the chain the result reports, which under
`direction="both"` is the forward one. It is not what the run cost:
`result.backward.n_iterations` is the rest. On the round-robin series both
chains come to 816, against a wall clock of 33.7 s forward and 83.7 s for
`"both"`.

## Telemetry, history and cancellation

`events=` and `cancel=` are per pattern. Every event a pattern's fit emits
is forwarded with its place in the series stamped into the event's `data`:
`series_index`, `series_label`, `series_n` and `series_pass`, plus `series_rung`
and `series_cold` on a restart. Those are added fields on existing kinds, so no
`EventKind` is new and the event schema version does not move. A consumer reads
`data` with `.get` and "pattern k of N" is readable off `fit_start`.

Cancelling a series returns what completed rather than raising. That is the
cancellation rule applied one level up. A series is N separate refinements, so
the pattern in flight is abandoned by
`Refinement.fit` itself (no node, no commit, models restored) while the
patterns already walked are finished fits with committed nodes. Raising would
throw those away. `SEQUENTIAL_CANCELLED` says how many of how many were reached,
so a short `entries` list is never mistaken for a short series.

:::{admonition} For agents
:class: agent
A truncated series and a finished one are the same shape, and the only thing
that distinguishes them is `SEQUENTIAL_CANCELLED`. Check for it before reading
the last entry as the end of a ramp, or a slope over the entries as a slope over
the experiment.
:::

## Constraining a parameter across the series

Fitting a(T) to a functional form of T across every pattern at once, which is
parametric refinement {cite}`stinton2007`, is a joint fit over the series, and
it is deliberately not implemented. The fences above exist partly so
that a sequential trajectory is never mistaken for one.

## A joint fit shares parameters instead

`MultiHistogramRefinement` refines one `Structure` against several patterns at
once, each with its own `Instrument` for a different wavelength, geometry,
resolution or background. The histograms are stacked into one residual
{cite}`vondreele1997`: shared structural parameters draw information from
every pattern, while each pattern keeps its own scale, background, zero and
resolution.

<!-- api-doc: no-exec — a joint two-histogram refinement, tens of seconds of solver time -->
```python
joint = rx.MultiHistogramRefinement(structure, [instrument_a, instrument_b])
result = joint.fit([pattern_a, pattern_b], plan="mccusker_default")
```

`refine_multi` is the same run as one call. Both return an ordinary
`RefinementResult`, with the per-histogram half on `RefinementResult.histograms`.
`MultiHistogramRefinement.fit` takes the patterns in the same order as the
instruments given to the constructor, and the two lists must be the same length.

`MultiHistogramRefinement.n_histograms` is how many there are, and
`MultiHistogramRefinement.mtable` is the multi-histogram parameter table
underneath: one ordinary table per histogram, threaded by a column map that
folds the shared columns onto one. After a fit,
`MultiHistogramRefinement.fitted_structures` and
`MultiHistogramRefinement.fitted_instruments` hold the per-histogram refined
models and `MultiHistogramRefinement.result_` the result. The shared parameters
are identical across the fitted structures; scale, background, zero and
resolution differ.

A joint fit runs in Rietveld mode only. Le Bail and Pawley intensities are
per-pattern empirical extractions rather than shared quantities, so a
multi-histogram fit of them would be independent single fits, which misses the
joint-residual point of the module.

### Which parameters are shared

`SharingMap` decides. The default rule is instrument against sample: a path is
per-histogram if it starts with `instrument.` or ends with `.scale`, and shared
otherwise, on the reading that there is one specimen and one crystal.

```python
from rietx.params.multi import SharingMap

default = SharingMap()
assert default.is_shared("phases.0.cell.a")
assert default.is_shared("phases.0.atoms.0.biso")
assert not default.is_shared("phases.0.scale")
assert not default.is_shared("instrument.zero_shift")
```

`SharingMap.per_histogram` and `SharingMap.shared` are override glob lists,
checked in that order before the default, and `SharingMap.is_shared` is the
question they answer. Giving each histogram its own preferred-orientation axis
is one override:

```python
from rietx.params.multi import SharingMap

per_mount = SharingMap(per_histogram=["phases.*.preferred_orientation.*"])
assert not per_mount.is_shared("phases.0.preferred_orientation.r")
assert per_mount.is_shared("phases.0.cell.a")
```

`SharingSpec` is the serializable twin, carrying the same two override lists as
`SharingSpec.per_histogram` and `SharingSpec.shared`, with `SharingSpec.to_map`
to convert; it is what the JSON surface takes ([](agents.md)).

Per-histogram parameters are named with a `hist.{h}.` scope
(`hist.0.instrument.zero_shift`, `hist.1.phases.0.scale`) while shared ones keep
their bare path. A turn-on glob matches either form, so an existing
single-histogram plan frees every histogram's copy unchanged, and a scoped glob
targets one.

The cell is the one entry in that table that is a judgement call. The structure
is shared because it is one structure, space group, coordinates, ADPs and
occupancies together. The scale, background and profile widths are
per-histogram, because they belong to the instrument rather than the specimen.
Whether the cell is one number or several is a claim about the specimens: one
number if the histograms are one material state, separate numbers if they
genuinely differ. That choice has a consequence for wavelengths, in
{ref}`a-refinable-wavelength-jointly`.

### Two radiations in one fit

A joint fit may mix radiations. An X-ray histogram and a constant-wavelength
neutron histogram of one specimen refine one structure, which is the combined
refinement {cite}`vondreele1997` was written for. There is nothing extra to
declare: each `Instrument` carries its own source, and every correction that
depends on the radiation reads the source of the histogram it is computing.

```python
import rietx as rx

xray = rx.Instrument.debye_scherrer(wavelength=0.4132950)
neutron = rx.Instrument.constant_wavelength_neutron(1.54040, fwhm_deg=0.30)
assert (xray.source.kind, neutron.source.kind) == ("xray_cw", "neutron_cw")
assert xray.source.dispersion is not None and neutron.source.dispersion is None
```

The split between shared and per-histogram parameters is the one above, with
nothing radiation-specific in it. The specimen's parameters are shared: the
cell, the coordinates, the occupancies, the displacement parameters and a
magnetic moment. Each histogram keeps its own scale, background, zero shift,
profile and wavelength.

What the second radiation adds is a different *weighting* of the same
structure factor. X-rays scatter off electrons, so the heavier atoms dominate
f(s), while a nucleus's scattering length b follows no such order. Corundum
ranks its two sites oppositely: f(0) is 13 electrons for Al and 8 for O, while
b is 3.449 fm for Al and 5.803 fm for O (Sears's table, which is what
`b_Sears.dat` holds). On synthetic corundum patterns with a known answer, the
X-ray pattern alone determined z(Al) about three times better than the neutron
pattern alone, and x(O) about as well. Refined jointly, the esd of z(Al) was
0.95 to 0.97 of the X-ray pattern's own, and the esd of x(O) 0.58 to 0.69 of it.
The neutron histogram bought the oxygen and left the aluminium to the X-rays.
In the same fits the two scales, 3.5 times apart, and two zero shifts of
opposite sign each came back on their own histogram's value.

| Correction | On an X-ray histogram (`xray_cw`) | On a neutron histogram (`neutron_cw`) |
|---|---|---|
| Scattering amplitude | f₀(s) of the species, plus f′ + i·f″ | b of the species, one number at every s |
| Anomalous dispersion | `Source.dispersion`, on by default | none: `NeutronSource.dispersion` is always `None` |
| Polarisation, `instrument.polarization` | refinable | pinned at K = 1 and locked |
| Magnetic structure factor | never built | built for a phase that declares a moment |
| µR estimated from composition | when the geometry declares a capillary radius | never: declare `Geometry.mu_r` yourself |

A magnetic moment is shared like any other structural parameter, so the X-ray
histogram carries its column and adds no gradient to it: the term is never
built there (`rietx.model.forward.magnetic_wanted` decides, from
`rietx.crystallography.magnetic.scattering.MAGNETIC_SOURCE_KINDS`). The moment
is measured by the neutron histogram alone, against a structure both
histograms constrain. A size coefficient is the one shared quantity that is a
different number per histogram, and that is a matter of wavelength rather
than radiation (`SIZE_NORMALISED_ACROSS_WAVELENGTHS`, and the size section of
[](results.md)).

The three diagnostics that key on the radiation, `DISPERSION_NEGLECTED`,
`NEUTRON_RESONANT_ABSORBER` and `SPECIES_FALLBACK_NEUTRAL`, land on the
histogram whose radiation raised them, never at the top level; the rule that
places them and every other diagnostic is in
{ref}`reading-a-joint-result`. What the result does not yet say is which
radiation each histogram was, because `HistogramResult` carries no instrument.
Read `MultiHistogramRefinement.fitted_instruments` instead, whose entry for
each histogram carries its `source.kind`.

The real-data joint fit this package is tested against is one Nd₂Ru₂O₇
specimen measured on an APS 11-BM synchrotron and an NCNR BT-1
constant-wavelength neutron diffractometer, refined in the next section.

(a-refinable-wavelength-jointly)=
### A refinable wavelength

A joint fit is the only place a wavelength can be refined, and it is worth being
precise about why, because the reason also tells you *which* one to hold.

For a single histogram λ and the cell are exactly degenerate: Bragg's law
{eq}`pos-bragg` gives the pattern access to λ/(2 sin θ), so only the product of
λ with a reciprocal cell is measurable and a free λ beside a free cell is a flat
direction. That is why `EmissionLine.wavelength` and `NeutronSource.wavelength`
default to `vary=False` and why freeing one in a single-histogram fit is refused
({ref}`a-refinable-wavelength`).

Several histograms of one specimen share one cell, and that is what breaks the
degeneracy. Holding one wavelength pins the cell's scale. The remaining N − 1
are then over-determined by that shared cell and genuinely measurable, each of
them against the same lattice. Holding all of them instead forces every
monochromator's calibration error into the shared cell, and freeing all of them
puts the flat direction back. So:

```{admonition} The rule
:class: important

A free wavelength requires its histogram's cell to be shared with at least one
histogram whose wavelength is held.
```

"Exactly one held, at most N − 1 free" is that statement's special case when
every histogram shares one cell, which is the `SharingMap` default. Un-share the
cell and the single-histogram degeneracy is back, per histogram, inside a joint
fit where it looks solved, so that combination is refused too. All the ways of
getting it wrong are refused naming their own cause, and the count is stated:
"2 of 2 wavelengths are free; hold one".

Which one to hold is not arbitrary. Hold the wavelength of the histogram that
determines the cell. On a synchrotron-plus-neutron pair that is the synchrotron.
Its wavelength calibration is the better known and its angular resolution makes
its cell the better determined, so the cell belongs to the X-ray data. What the
neutron data uniquely supplies is the structural content, meaning oxygen
positions, site occupancies and displacement parameters, through
scattering-length contrast X-rays do not have. The neutron wavelengths then
refine against a cell the X-ray histogram has pinned, which is the only way
their monochromator calibrations can be measured at all. The accuracy hierarchy
and the degeneracy argument are one argument: the histogram that owns the cell
is the histogram whose λ you hold.

A wavelength is per-histogram under the default sharing rule, so it is freed by
a scoped glob. That is what makes "all but one" expressible at all, since the
bare path would free every histogram's copy and be refused:

<!-- api-doc: no-exec — a joint two-histogram refinement, tens of seconds of solver time -->
```python
import rietx as rx
from rietx.strategy.staged import PLAN_PRESETS, Stage

plan = PLAN_PRESETS["mccusker_structural"]()
# histogram 0 is the synchrotron and keeps its declared λ; histogram 1's
# neutron λ refines against the cell histogram 0 has pinned.  The cell and the
# coordinates ride along, because λ trades against both.
plan.stages.append(Stage("wavelength",
                         ["hist.1.instrument.source.lines.0.wavelength",
                          "phases.*.cell.*", "phases.*.atoms.*.dof.*"]))
result = rx.refine_multi([xray, neutron], structure, [ins_x, ins_n], plan=plan)
```

The number to read is the `WAVELENGTH_CALIBRATION` diagnostic on that
histogram, which reports how far λ moved from its declared value in ppm and how
that compares with its own esd. ppm is the unit a calibration error is quoted
in, and it is deliberately the only evidence this feature is defended with,
never an Rwp comparison. A refined λ that comes back inside its own esd measured
nothing, which is a different outcome from one that measured a calibration
error, and the diagnostic says which.

Two fences worth knowing. Within one source the emission lines' wavelength ratio
is atomic physics rather than something a pattern can measure, so only line 0's
wavelength is refinable, and a known ratio such as a λ/2 harmonic is a
`Refinement.tie` with `scale=0.5`. And the reflection list, evaluation windows
and quadrature node counts are frozen from the *declared* λ at each stage
compile, so a free λ moves peaks inside their frozen windows exactly as a free
cell does: legitimate while the motion is small against the window, and a few
hundred ppm is (250 ppm of λ is 0.11° at 2θ = 150°, against a 0.30° FWHM).

All of this is constant wavelength. The same fence generalises verbatim to a
time-of-flight multi-bank fit, where each bank carries its own DIFC calibration
and exactly one of them has to be held to pin the cell. Nothing here implements
TOF.

(scanning-a-parameter)=
### Scanning a parameter the data barely constrains

A joint fit often has one parameter that is weakly determined for a physical
reason: an antisite fraction between two elements whose scattering lengths
barely differ, a site occupancy, a small strain. Freeing it alongside everything
else has two failure modes. The solver lands in a local minimum, and the esd it
reports comes from a linearised curvature the data does not really have.

The remedy is a profile scan. Hold the parameter on a grid, refine everything
else at each point, and read the value off the minimum of the curve and the
interval off its width. It is the empirical version of a concern this package
already carries in its linear algebra. `optimize.statistics.normal_covariance`
equilibrates the normal matrix before inverting it precisely because a direction
the data does not move has no esd rather than a small one, and
`ParameterTable.unmeasured_rows` names what such a direction reached. A scan
measures that curvature instead of trusting it.

There is no `scan` verb, because the recipe is a thin composition of verbs that
already exist and a new one would only hide which of them did what:

| Step | Verb |
|---|---|
| fork a fresh line of work per grid point | `Refinement.branch`, `Refinement.checkout` |
| pin the scanned parameter at the grid value | `Refinement.set_values`, then `Refinement.set_vary` with `vary=False` |
| refine the rest | `Refinement.fit` or `Refinement.run_stage` |
| read the curve | `RefinementResult.statistics` for χ² and Rwp; `HistogramResult.phase_agreement` for that phase's R_B |

Both `set_values` and `set_vary` auto-commit history nodes, so the whole scan is
recoverable and replayable; branching per grid point rather than walking the
grid in sequence is what keeps one point from seeding the next.

Reading it: the minimum gives the value, and the interval where χ² rises by 1
above the minimum is the 1σ range for one parameter. A scan measures the surface
you searched. A coarse grid can step over a narrow minimum entirely, and the
interval it gives is only ever as good as the grid spacing, so refine the grid
near the minimum before quoting a number from it.

In a joint fit, pin the parameter on the shared model. `SharingMap` decides
whether the path you are scanning is shared or per-histogram (occupancies and
coordinates are shared by default, scales and everything under `instrument.` are
not), and scanning a per-histogram path pins it in one histogram only, which is
a different experiment from the one you meant.

(reading-a-joint-result)=
### Reading a joint result

`RefinementResult.histograms` is a list of `HistogramResult`, one per pattern.
An empty list means an ordinary single-histogram fit.

| Field | Holds |
|---|---|
| `HistogramResult.label` | that histogram's name |
| `HistogramResult.weight` | the inter-histogram relative weight applied to its residual block |
| `HistogramResult.statistics` | its own agreement indices |
| `HistogramResult.two_theta`, `HistogramResult.y_obs`, `HistogramResult.y_calc`, `HistogramResult.y_background` | its curves |
| `HistogramResult.sigma` | its per-point σ |
| `HistogramResult.ticks` | its reflection positions, by phase |
| `HistogramResult.tick_hkl` | which reflection each of those is, paired by index |
| `HistogramResult.qpa` | its phase quantities |
| `HistogramResult.restraints` | the restraint report for that histogram |
| `HistogramResult.phase_agreement` | its R_B and R_F, per phase |
| `HistogramResult.diagnostics` | what that histogram reported |

A joint fit reports each diagnostic in one of two places, and the place follows
from what the diagnostic is about. A finding about one pattern goes on that
histogram's `HistogramResult.diagnostics`, once per histogram: its radiation,
its instrument, its counts, or how well the model fits it. A finding about the
shared structure, the joint solve or the plan goes once on
`RefinementResult.diagnostics`. So a mixed X-ray and neutron fit whose X-ray
source declines anomalous dispersion raises `DISPERSION_NEGLECTED` on the X-ray
histogram only. The same holds for `SPECIES_FALLBACK_NEUTRAL`, and
`NEUTRON_RESONANT_ABSORBER` goes on the neutron histogram only. None of the
three appears at the top level. `STAGE_MAX_ITER` and
`SPACE_GROUP_SETTING_ASSUMED` appear there, once each.

There is one exception, `BACKGROUND_ABSORPTION`, which is on both lists. It is
raised on its histogram's list and repeated once on
`RefinementResult.diagnostics`, where it keeps its `hist.<h>.` path, as the
top-level report carried it before the rule was written. Each copy is the same
finding about one histogram, so count it once.

The rule is written as data. `rietx.multi.DIAGNOSTIC_SCOPES` places each
diagnostic, and `rietx.multi.GUARD_SCOPES` places each guard. Each row gives
its reason, including the rows for diagnostics a joint fit does not compute.
There are six of those: the two Pawley ones (a joint fit is Rietveld-only),
`HOLD_BLOCKED_PLAN` (a joint fit has no hold verb), `RESTRAINT_TENSION`
(restraints are refused), and the two magnetic-width checks,
`STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` and `MAGNETIC_WIDTH_MOVED_MOMENT`
(WP-1343's ordering rule and moment shift are read by the single-pattern
plan, which a joint fit does not run). A joint fit carries the magnetic term
on its neutron histogram, so its width-before-moment ordering is unchecked.
One more is withheld on purpose: `DATA_SUPPORT_LOW`.
Its ratio of observations to parameters has no agreed definition across
histograms, and one pattern's reflections counted against the shared columns
would warn about a fit the other patterns support. Its two sibling checks,
`PATTERN_UNDERSAMPLED` and `PATTERN_DEAD_CHANNELS`, are about one measurement,
so each histogram gets them.

A pooled Rwp is never quoted alone. Stacking patterns into one residual
means a single pooled number can hide a badly fitting histogram, which is the
failure this package's reporting exists to prevent, so each histogram reports
its own. Measured on two LaB₆ patterns of the same crystal at λ = 0.41390 Å
(4200 points) and λ = 0.71070 Å (8000 points), the pooled Rwp was 0.0516 while
the two histograms were at 0.0414 and 0.0613. The pooled figure describes
neither.

`HistogramResult.weight` is 1.0 at unit weight, where each point's own esd
governs. A non-unit weighting is also recorded in `Provenance.notes`, so it is
never silent.

`RefinementResult.for_histogram` returns a single-histogram-shaped view of one
histogram: its curves and statistics moved to the top level and `histograms`
cleared, so `result.for_histogram(0).plot()` and a report built from it operate
per pattern. Reports are per-histogram for the same reason the statistics are.

### What the joint fit bought

On those two LaB₆ patterns the shared cell came back identical in both entries
of `MultiHistogramRefinement.fitted_structures`, a = 4.156604 Å against the
4.15660 Å the patterns were built from and +1.0 ppm out, while the per-histogram
zero
shifts separated correctly, 0.006019° and −0.009974° against the 0.006° and
−0.010° that went in. Its esd was 2.43 × 10⁻⁶ Å, against 4.70 × 10⁻⁶ and
2.83 × 10⁻⁶ from the two patterns refined singly: 1.94× and 1.17× better than
either alone, which is the joint fit's whole argument.

Those numbers come from synthetic patterns with known answers, so the comparison
is readable. On real data the same machinery has no truth to be checked against,
and the per-histogram Rwp spread above is what to watch instead.
