# About a fit

A fit is one call, `Refinement.fit`, which refines a structure and an instrument against a pattern in stages and records each stage in a history.

```{mermaid}
flowchart LR
  P["Pattern"] --> R
  S["Structure"] --> R
  I["Instrument"] --> R
  R["Refinement"] --> L
  subgraph L ["Each stage of the plan"]
    direction TB
    F["Free the stage's parameters"] --> C["Compile the model"]
    C --> H["Fix what the data cannot see"]
    H --> V["Solve"]
    V --> G["Check"]
    G --> N["Commit a history node"]
  end
  L --> O["RefinementResult"]
  O --> Q["FitReport"]
```

## Inputs

The pattern is a `PatternData`, which `rx.read_pattern` builds from a file.
The weights come from the file's esd column when it has one, and from counting statistics (√y) when it does not, which assumes the file holds counts.
rietx never subtracts a background from the counts.
The [weighting section of the theory](../theory/estimation.md#objective-and-weights) gives the objective function.

The structure is a `Structure` holding one or more phases, each with its cell, space group and atoms.
`rx.Structure.from_cif` reads one from a CIF.

The instrument is an `Instrument` holding the source, the geometry, the peak profile and the background.
`rx.Instrument.bragg_brentano(radiation="CuKa")` builds a laboratory diffractometer.

`rx.Refinement(structure, instrument)` holds both models.
Their current values are the working state, and every stage of a fit moves them.
The pattern goes in at the fit, as `fit(data, plan=...)`, so one refinement can be fitted to several patterns in turn.

rietx fits X-ray and constant-wavelength neutron patterns, singly or several of one specimen together.
[Data rietx fits](../switching/at-a-glance.md#data-rietx-fits) lists the instrument presets, and says what is not covered, such as neutron time of flight.

A fit runs in one of three modes, set by `fit(mode=...)`.
`"rietveld"`, the default, calculates intensities from the structure.
`"lebail"` and `"pawley"` refine each reflection's intensity as its own number, and fix the atoms and the phase scale.

## The plan

A plan is a list of stages, and each stage names the parameters it frees.
Staging is cumulative.
A parameter freed in one stage stays free in every later stage, so the last stage refines everything together.
`fit` runs `mccusker_default` unless you pass another, by name or as a `RefinementPlan`.
`mccusker_default` frees the scale and background, then the zero shift, then the cell, then the peak widths, and never the atoms.
The [plan presets](../reference/plans.md) page draws every stage of every preset.
To free something no preset frees, such as an occupancy, append a `Stage` to a preset's `RefinementPlan.stages` list.

A plan sets the refine flags afresh.
A flag you set by hand before the fit is replaced by the plan's.
To keep a parameter fixed whatever the plan says, use `Refinement.hold`.

:::{admonition} Coming from GSAS-II, TOPAS or FullProf
:class: note

In GSAS-II a refine flag stays as you set it, and in FullProf a codeword does.
In TOPAS a parameter marked to refine refines from the first iteration.
In rietx the plan decides which parameters refine in each stage, so `Refinement.set_vary` before a fit has no lasting effect.
`Refinement.hold` keeps a parameter fixed through every stage, as a cleared refine flag does in GSAS-II.
:::

## One stage

Every stage runs the same six steps in this order.

### Freeing the stage's parameters

The stage's names select the parameters it frees.
Some parameters stay fixed whatever the stage names: a parameter you hold, one the space group ties to another, and the atoms in a Le Bail or Pawley fit.
A name the hold refused is recorded in `StageResult.blocked_by_hold`.

### Compiling the model

rietx builds the reflection list, the range of points each peak spans, and the number of points used to integrate axial divergence.
These stay fixed while the stage solves and are rebuilt before the next stage.
A reflection entering the list mid-solve would make the residual jump, and fixing the list keeps it smooth.
The [forward model](../theory/forward-model.md#discreteness-frozen-per-stage) states the rule.

### Fixing what the data cannot see

Before it solves, the stage compares each phase's scale with its esd.
A phase whose scale is under {{ PHASE_SUPPORT_SIGMA }} esds is too weak for the data to fix its cell and atoms, so the stage fixes them and tests the phase again at its answer.
A magnetic moment direction the powder average cannot determine is fixed the same way.
So is a phase's displacement parameter when its reflections in range cannot separate it from the scale.
`StageResult.held` lists what was fixed.
The diagnostic `PHASE_UNCONSTRAINED` reports a held phase, and `SCALE_B_INSEPARABLE` a held displacement parameter.
This is separate from `Refinement.hold`, which you set and which lasts until you lift it.

### Solving

The default solver is a bounded Levenberg-Marquardt with an analytic Jacobian, in double precision.
Each parameter refines in its own units, and its `min` and `max` are hard bounds.
Every stage but the last stops at a looser tolerance, since the parameters it frees keep refining in every later stage.
The [solvers](../theory/estimation.md#solvers) and [convergence](../theory/estimation.md#convergence) sections give the details.

### Checking the answer

After each stage rietx checks for pairs of parameters correlated above 0.98, for a bound the answer rests on, and for values outside their physical range, such as an anisotropic displacement tensor that is not positive definite.
Each finding becomes a diagnostic with a code, such as `HIGH_CORRELATION` or `BOUND_HIT`.

### Committing a node

The refined values are written back into the structure and instrument, and the stage becomes a node in the history.

## Outputs

`fit` returns a `RefinementResult`.
It holds the status (`converged`, `max_iter` or `diverged`), the agreement statistics, every refined parameter with its esd, a record of each stage, the diagnostics, and the observed, calculated and background curves.
The esds come from the last stage, where every freed parameter refines together.
[About correlations and esds](correlations.md) explains what an esd here does and does not measure.

`Refinement.report()` builds a `FitReport` from the last fit.
It reads the misfit and says what it can attribute, and with what confidence.
[About the report](report.md) describes its three layers.

## The history

Every stage of a fit, and every edit to the models, commits an immutable node.
The edits include `set_vary`, `set_values`, `tie` and `hold`.
A node stores the parameter values and settings, not the curves, at about 10 kB a node.
`Refinement.checkout` returns the models to any node, `Refinement.branch` starts a second line of work from one, and `rx.replay(tree, node_id, data)` recomputes a node's fit without refining.
`Refinement.history` is the tree of nodes.

A replayed node can differ slightly from the statistics recorded when it ran.
The recorded statistics come from a model compiled at the values the stage started from, and a replay compiles at the values it ended on.
A large difference means the stage moved the model far enough to change its reflection list or peak ranges.

In a project the history is the file `history.jsonl`, and its last node is the working state.
[About the project](project.md) describes the other files.
