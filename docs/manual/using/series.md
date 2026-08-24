# Refining many patterns

There are two ways to have more than one pattern, and they are not variants of
each other. A **series** is N separate refinements, ordered, each starting from
the one before it. A **joint fit** is one refinement whose residual is several
patterns stacked together, sharing the parameters that describe the specimen.

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
with `dict.get` and refuse rather than substitute when it is missing: an absent
key is a file that recorded nothing, not a specimen at ambient. Today the
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
package's own deep copies of the models you passed, which is why your originals
are not moved by the fit.

Four settings are constructor arguments, because they describe the chain rather
than a run of it: `backend`, `solver`, `history`, and
`SequentialRefinement.carry`. [](refining.md) has the full table of which
setting goes where.

`history` behaves as it does for a single refinement ([](history.md)) with one
addition: given a **directory**, each pattern's tree is written to
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
| `on_result` | `(index, result) -> None`, called with each pattern's full result as it finishes |
| `events`, `cancel` | as on `Refinement.fit`, per pattern |

`refit` sets the ladder's *first* rung, not the only plan a pattern can be
fitted with. The staged order exists to keep early stages well conditioned from
a poor starting model, and a converged neighbour is not one, so the default
collapses it. When the neighbour turns out not to be a good starting point
either, the fence below catches it.

### What crosses a pattern boundary

`SequentialRefinement.carry` is a list of dot-path globs (fnmatch, the
`Refinement.set_vary` convention) naming which parameters are carried forward.
The default is `["*"]`: everything. A parameter excluded from it restarts from
the **initial** model on every pattern, not from its neighbour.

Carrying everything is cheap even when it looks reckless. Measured on the eight
IUCr round-robin sample-1 mixtures (three phases, one goniometer, 7251 points
each over 5–150°, and a composition that swings from 1.8 to 94.2 wt % across the
set), the chain took **816** least-squares iterations against **2789** for the
same eight patterns fitted independently, a factor of 3.4, and every pattern
converged on its first rung.

`prepare` is for what a `carry` glob cannot express: a parameter that must be
re-estimated **from this pattern** rather than either carried or left at its
initial value. Excluding the phase scales from `carry` on that round-robin
series would only fall back to the *first* mixture's guess, which is not the
same thing as estimating them afresh.

## What comes back

`SeriesResult` is the serializable answer. It stores summaries, not curves: nine
patterns' worth of `y_obs`/`y_calc`/`y_background`/`sigma` is about 2 MB of JSON
that is already on disk as the input files, while the refined values, their
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
| `SeriesEntry.n_iterations` | iterations over **every** attempt on this pattern |
| `SeriesEntry.reseeded` | the warm start was rejected and the pattern was refitted cold |
| `SeriesEntry.rwp_warm` | Rwp the first, warm attempt reached, set whenever the ladder escalated |
| `SeriesEntry.rung` | which attempt produced these values: `"warm"`, `"warm_staged"` or `"cold"` |
| `SeriesEntry.rungs_tried` | every rung attempted, in ladder order |
| `SeriesEntry.node_id`, `SeriesEntry.tree_id` | where this pattern's history lives |

`SeriesEntry.value` and `SeriesEntry.stderr` look a path up in that entry's
parameters and return `None` when it is not there.

`SeriesEntry.phase_agreement` is **not** the test of whether a minor phase is
real, and the temptation to read it as one is why it needs a paragraph. Both
indices are biased towards the model being tested, and a trace phase's is not
comparable with the major phase's at all —
{ref}`structure-agreement-indices` has the mechanism and the
in-repo measurement. What the field is for here is the *trajectory*: one
pattern's R_B is a value, sixty of them are a shape, and watching a phase's
R_B walk across a ramp is a use a single fit cannot make of it.

The question it looks like it answers has its own channel. `PHASE_UNCONSTRAINED`
measures each phase's strongest modelled point in σ of the observation noise —
"can the data see this phase at all" — reaches an entry through
`SeriesEntry.diagnostics`, and aggregates over the chain as
`SEQUENTIAL_PERSISTENT_FINDING`, which says the thing no per-pattern diagnostic
can: *42 of 68*. Read R_B beside that and beside the weight with its esd.

`SeriesEntry.rung` and `SeriesEntry.reseeded` answer different questions.
`rung` says where the numbers came from; the first pattern of a chain is always
`"cold"` because it has no predecessor. `reseeded` says whether the chain was
**broken** here, and only that has a fence. The middle rung does not set it:
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
| `Trajectory.arrays` | `(x, value, stderr)` as float arrays, missing esds as NaN |

**Patterns where the path is absent are skipped rather than filled.** A gap in a
trajectory is a real thing, a phase that was not in the model yet or a stage that
did not run, and inventing a value for it would be the confident wrong singleton
the whole package gates against. `len(trajectory)` is therefore the
number of points that have a value, not the number of patterns.

`SeriesResult.qpa_trajectory` does the same for a phase's weight fraction,
converted to a percentage, and `SeriesResult.paths` lists every parameter path
present anywhere in the series in first-seen order. Its `varied_only` argument
drops the tied paths; the default keeps them, because a hexagonal `cell.b` is
not free but is every bit as measured as `cell.a`. On the round-robin series
that is 49 paths, 41 of them varied.

`SeriesResult.to_table` returns `(header, rows)` in the wide form, one row per
pattern with a value and an esd per parameter, and `SeriesResult.write_csv`
writes it,
inferring a tab delimiter from a `.tsv` or `.tab` suffix and a comma otherwise.
The columns are `index, label, x, status, rung, rwp, gof`, then each path
followed by its esd. `rung` travels beside `status` because it is the other half
of "how much should I trust this point": a rescued point is a good fit whose
starting values did not come from its neighbour, and a table that hides that
reads as a continuous trajectory.

The axis column takes `SeriesResult.x_label`, unless that name is already one
of the fixed columns, in which case it is `x`. That is what the default hits:
`x_label` is a human label and defaults to `"index"`, which reads correctly as
an axis title for a series with no coordinate but would be the header's second
`index`. The column count, order and meaning do not change either way.

`SeriesResult.plot` plots one or more trajectories against the series axis.

## The four fences

A sequential fit is path-dependent by construction. Every pattern's answer
depends on its neighbour's, so the method can imprint a trend the data do not
carry: one bad pattern's error is inherited by all its successors, and the
result is a smooth-looking curve. Five diagnostics fence that, and **none of
them alters a fitted value**.

| Code | Says |
|---|---|
| `SEQUENTIAL_RESEED` | the warm start was rejected and the pattern was refitted cold, so the chain was not poisoned silently |
| `SEQUENTIAL_UNRECOVERED` | the pattern diverged and stayed diverged after every rung; it seeded no successor and joined no median |
| `SEQUENTIAL_DISCONTINUITY` | a step much larger than the local trend: the science, or a chain failure, and the diagnostic says both |
| `SEQUENTIAL_PATH_DEPENDENT` | with `direction="both"`, forward and backward disagree by more than their esds allow |
| `SEQUENTIAL_PERSISTENT_FINDING` | one of the *per-pattern* codes fired in more than half the patterns, so it is about the model rather than about a pattern |

The last one exists because of an arithmetic problem the others do not have. A
per-pattern diagnostic can only say "this pattern". In a run of 68 it therefore
cannot say **"42 of 68"**, and that is the sentence you act on, because one
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

What to do about each is [`AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)'s
diagnostic table, which this chapter does not restate.

### The ladder, and quarantine

A rejected warm fit escalates **one rung at a time**: the collapsed warm refit,
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

Quarantine is the other half, and it is about what the chain *carries* rather
than what it reports. A fit still `"diverged"` after the last rung is not a
starting point and not a scale, so its successor warm-starts from the last
**accepted** pattern and the reseed median never sees the failure. Otherwise one
failure would seed its neighbour with rubbish *and* drag the median that decides
every later trigger, quietly raising the bar for the rest of the series.

**What triggers the ladder is deliberately narrow**: divergence, or an Rwp above
`reseed_factor` times the median of the accepted patterns. Two candidates were
considered and rejected, and the reasons are the rule a new trigger has to
satisfy. Guard findings such as `HIGH_CORRELATION` fire legitimately on
perfectly converged patterns, and no rung changes the model or the data that
produced them. A discontinuity is a property of the whole finished trajectory,
so making it a trigger would mean re-walking a finished chain. What the two
accepted triggers share: each is a property of *this pattern's own fit*,
readable the moment it finishes, and each is something a different starting
point could plausibly fix.

### Running the chain both ways

`direction="both"` runs the series forward and backward and compares the two
trajectories. The reported `SeriesResult.entries` are the forward ones; the
comparison arrives as `SEQUENTIAL_PATH_DEPENDENT` diagnostics, one per parameter
that disagrees.

It is the only check that separates a measured trajectory from an ordering
artefact, and on real data it is selective. On the round-robin series it flagged
**nine** parameters, and every one of them was a broadening term:
`phases.*.lor_size`, `gauss_size`, `gauss_strain`, `lor_strain`,
`instrument.profile.x` and `instrument.geometry.axial_sl`. Not one cell
parameter and not one scale: the trajectories anyone would plot from that series
were order-independent, and the widths were not.

Two things to know before reading the σ multiples in those messages. They are
ratios to a *fitted* esd, so a parameter sitting near zero with an esd near zero
reports a spread of thousands of σ that is not a physical scale, so read the two
values the message quotes rather than the multiple. And the trajectory the
messages compare against is `SeriesResult.backward`, the reverse chain's own
`SeriesResult`, set whenever `direction="both"` completed, so a run made
through `refine_sequential` can read the second trajectory and not only the
verdict about it. Its own `backward` is `None`: one extra level, not a cycle,
and `SequentialRefinement.backward_` is the same object.

`SeriesResult.n_iterations` counts the chain the result *reports*, which under
`direction="both"` is the forward one. It is not what the run cost:
`result.backward.n_iterations` is the rest. On the round-robin series both
chains come to 816, against a wall clock of 33.7 s forward and 83.7 s for
`"both"`.

## Telemetry, history and cancellation

`events=` and `cancel=` are **per pattern**. Every event a pattern's fit emits
is forwarded with its place in the series stamped into the event's `data`:
`series_index`, `series_label`, `series_n` and `series_pass`, plus `series_rung`
and `series_cold` on a restart. Those are added fields on existing kinds, so no
`EventKind` is new and the event schema version does not move. A consumer reads
`data` with `.get` and "pattern k of N" is readable off `fit_start`.

Cancelling a series **returns** what completed rather than raising. That is not
an exception to the cancellation rule but the rule applied one level up: a
series is N separate refinements, so the pattern in flight is abandoned by
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
parametric refinement {cite}`stinton2007`, is a *joint* fit over the series, and
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

**Rietveld mode only.** Le Bail and Pawley intensities are per-pattern empirical
extractions rather than shared quantities, so a multi-histogram fit of them
would be independent single fits, which is not the joint-residual point of the
module.

### Which parameters are shared

`SharingMap` decides. The default rule is instrument-versus-sample: a path is
**per-histogram** if it starts with `instrument.` or ends with `.scale`, and
shared otherwise: one specimen, one crystal.

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

The cell is the one entry in that table that is a **judgement call**. The
structure — space group, coordinates, ADPs, occupancies — is shared because it
is one structure; the scale, background and profile widths are per-histogram
because they belong to the instrument rather than the specimen. Whether the cell
is one number or several is a claim about the specimens: one number if the
histograms are one material state, separate numbers if they genuinely differ.
That choice has a consequence for wavelengths, in the next section.

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

Several histograms of one specimen **share one cell**, and that is what breaks
the degeneracy. Holding one wavelength pins the cell's scale; the remaining
N − 1 are then over-determined by that shared cell and genuinely measurable —
each of them against the same lattice. Holding *all* of them instead forces every
monochromator's calibration error into the shared cell, and freeing all of them
puts the flat direction back. So:

```{admonition} The rule
:class: important

A free wavelength requires its histogram's cell to be **shared** with at least
one histogram whose wavelength is **held**.
```

"Exactly one held, at most N − 1 free" is that statement's special case when
every histogram shares one cell, which is the `SharingMap` default. Un-share the
cell and the single-histogram degeneracy is back, per histogram, inside a joint
fit where it looks solved — so that combination is refused too. All the ways of
getting it wrong are refused naming their own cause, and the count is stated:
*"2 of 2 wavelengths are free; hold one"*.

**Which one to hold is not arbitrary: hold the wavelength of the histogram that
determines the cell.** On a synchrotron-plus-neutron pair that is the
synchrotron. Its wavelength calibration is the better known and its angular
resolution makes its cell the better determined, so the cell belongs to the
X-ray data; what the neutron data uniquely supplies is the *structural* content
— oxygen positions, site occupancies, displacement parameters — through
scattering-length contrast X-rays do not have. The neutron wavelengths then
refine against a cell the X-ray histogram has pinned, which is the only way
their monochromator calibrations can be measured at all. The accuracy hierarchy
and the degeneracy argument are one argument: the histogram that owns the cell
is the histogram whose λ you hold.

A wavelength is per-histogram under the default sharing rule, so it is freed by
a **scoped** glob — which is what makes "all but one" expressible at all, since
the bare path would free every histogram's copy and be refused:

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
histogram, which reports how far λ moved from its declared value **in ppm** and
how that compares with its own esd. ppm is the unit a calibration error is
quoted in, and it is deliberately the only evidence this feature is defended
with — never an Rwp comparison. A refined λ that comes back inside its own esd
measured nothing, which is a different outcome from one that measured a
calibration error, and the diagnostic says which.

Two fences worth knowing. Within one source the emission lines' wavelength
*ratio* is atomic physics rather than something a pattern can measure, so only
line 0's wavelength is refinable and a known ratio — a λ/2 harmonic — is a
`Refinement.tie` with `scale=0.5`. And the reflection list, evaluation windows
and quadrature node counts are frozen from the *declared* λ at each stage
compile, so a free λ moves peaks inside their frozen windows exactly as a free
cell does: legitimate while the motion is small against the window, and a few
hundred ppm is (250 ppm of λ is 0.11° at 2θ = 150°, against a 0.30° FWHM).

**Constant wavelength only.** The same fence generalises verbatim to a
time-of-flight multi-bank fit, where each bank carries its own DIFC calibration
and exactly one of them has to be held to pin the cell. Nothing here implements
TOF.

(scanning-a-parameter)=
### Scanning a parameter the data barely constrains

A joint fit often has one parameter that is weakly determined for a physical
reason — an antisite fraction between two elements whose scattering lengths
barely differ, a site occupancy, a small strain. Freeing it alongside everything
else has two failure modes: the solver lands in a local minimum, and the esd it
reports comes from a linearised curvature the data does not really have.

The remedy is a **profile scan**: hold the parameter on a grid, refine
everything else at each point, and read the value off the minimum of the curve
and the interval off its width. It is the empirical version of a concern this
package already carries in its linear algebra —
`optimize.statistics.normal_covariance` equilibrates the normal matrix before
inverting it precisely because *a direction the data does not move has no esd
rather than a small one*, and `ParameterTable.unmeasured_rows` names what such a
direction reached. A scan measures that curvature instead of trusting it.

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
above the minimum is the 1σ range for one parameter. **A scan measures the
surface you searched.** A coarse grid can step over a narrow minimum entirely,
and the interval it gives is only ever as good as the grid spacing — so refine
the grid near the minimum before quoting a number from it.

In a joint fit, pin the parameter on the **shared** model. `SharingMap` decides
whether the path you are scanning is shared or per-histogram (occupancies and
coordinates are shared by default, scales and everything under `instrument.` are
not), and scanning a per-histogram path pins it in one histogram only, which is
a different experiment from the one you meant.

### Reading a joint result

`RefinementResult.histograms` is a list of `HistogramResult`, one per pattern.
An empty list means an ordinary single-histogram fit.

| Field | Holds |
|---|---|
| `HistogramResult.label` | that histogram's name |
| `HistogramResult.weight` | the inter-histogram relative weight applied to its residual block |
| `HistogramResult.statistics` | **its own** agreement indices |
| `HistogramResult.two_theta`, `HistogramResult.y_obs`, `HistogramResult.y_calc`, `HistogramResult.y_background` | its curves |
| `HistogramResult.sigma` | its per-point σ |
| `HistogramResult.ticks` | its reflection positions, by phase |
| `HistogramResult.qpa` | its phase quantities |
| `HistogramResult.restraints` | the restraint report for that histogram |
| `HistogramResult.phase_agreement` | its R_B and R_F, per phase |
| `HistogramResult.diagnostics` | what that histogram reported |

**A pooled Rwp is never quoted alone.** Stacking patterns into one residual
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
−0.010° that went in. Its esd was 3.26 × 10⁻⁶ Å, against 6.36 × 10⁻⁶ and
3.80 × 10⁻⁶ from the two patterns refined singly: 1.95× and 1.16× better than
either alone, which is the joint fit's whole argument.

Those numbers come from synthetic patterns with known answers, which is what
makes the comparison readable. On real data the same machinery has no truth to
be checked against, and the per-histogram Rwp spread above is what to watch
instead.
