# The refinement

This page gives the calls that run a refinement, where each setting goes, the fit modes, the plan and stage objects and their storage, what each stage records, the guard findings, the event stream, cancellation, and what a result records about the run.

[About a fit](../concepts/fit.md) follows one stage from freeing its parameters to committing its history node.
[Plan presets](plans.md) draws each preset's stages, and [Stage settings, flags and options](settings.md#stage-settings) gives each stage setting with its meaning.

## Entry points

`refine` runs one refinement and returns a `RefinementResult`.
`Refinement` is the same machinery kept open, so the model survives the fit and can be edited, inspected and fitted again.

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
import rietx as rx

result = rx.refine(data, structure, instrument, plan="mccusker_default")

ref = rx.Refinement(structure, instrument)
result = ref.fit(data)
```

`Refinement.fit` runs a whole plan from the current values, and the plan's stages decide what is free.
`Refinement.run_stage` runs one `Stage` from the current values and stops ([How to run a plan one stage at a time](../guides/stage.md)).
A plan with no stages is refused, because it frees nothing.
`Refinement.predict` evaluates the model without refining it.

A setting that decides how every fit in the object is computed belongs to the constructor.
A setting about one pattern, or one run in flight, belongs to the call.

| Setting | Taken by | Default |
|---|---|---|
| `backend`, `solver` | `Refinement(...)` and `refine` | `"numpy"` and `"lm"` |
| `history` | `Refinement(...)` and `refine` | on for `Refinement`, off for `refine`, which discards the tree with the object ([The refinement history](history.md)) |
| `mode`, `two_theta_limits` | `Refinement.fit`, `Refinement.run_stage` and `refine` | `"rietveld"` and the whole pattern; `run_stage` reuses the last call's when given `None` |
| `plan` | `Refinement.fit` and `refine` | `"mccusker_default"` |
| `events`, `cancel`, `telemetry`, `label` | `Refinement.fit`, `Refinement.run_stage` and `refine` | none; a run records itself unless told not to ([How to watch or stop a running fit](../guides/watch.md)) |
| `stage_reports`, `progress` | `Refinement.fit` | off ([Reports at every stage](report.md#reports-at-every-stage), [Progress lines](result.md#progress-lines)) |
| `correlation_guard`, `phase_support_sigma` | `Refinement.run_stage` | 0.98 and 3, since no plan supplies them; `Project.run_stage` passes the `phase_support_sigma` of the plan the project stores |

`Refinement.fit` therefore takes no `backend=` or `solver=`.
Choose them when you build the object:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument, backend="numpy", solver="trf")
```

`backend` selects how the arrays are computed, and `solver` selects the least-squares driver.
`"numpy"` and `"lm"`, a bounded Levenberg-Marquardt, are the defaults.
`solver="trf"` selects scipy's Trust Region Reflective, the default before 1.8, which reproduces a number measured before then.
From a poor start it can stop in a basin the default driver leaves ([Solvers](../theory/estimation.md#solvers)).
An unknown solver raises `ValueError` and an unknown backend `NotImplementedError`.
A backend whose optional dependency is missing raises `ImportError` with the install command.
`Capabilities.backends` and `Capabilities.solvers` report what this installation has ([Backends](programs.md#backends)).

`Refinement.result_` holds the most recent result, and `Refinement.snapshot` returns a `RefinementState` without refining anything.

## Modes

`mode` decides where a reflection's intensity comes from.

| Mode | Intensities | For |
|---|---|---|
| `"rietveld"` | computed from the structure | refining a structural model |
| `"lebail"` | extracted from the data between solves | the best profile fit a cell and a space group can give, with no structure |
| `"pawley"` | refined, one parameter per reflection | as Le Bail, with the intensities as parameters that carry esds |

Le Bail and Pawley fix every atom parameter, every phase scale and every texture coefficient, because the data do not constrain them in those modes.
The emission-line weights and a wavelength refine in both modes: the doublet's ratio is a shape the per-reflection intensities cannot absorb.
A wavelength refines only against a held cell ([Held rows](parameter-table.md#held-rows)).
`ParameterRow.mode_fixed` marks those rows ([Parameter map](parameters.md)).
The preset name `"mccusker_default"` runs as `profile_only` in Le Bail mode and as `pawley_default` in Pawley mode.

`RefinementResult.mode` records the mode a result was produced under, and `Capabilities.modes` lists the three.

### Le Bail passes

Le Bail mode extracts the intensities before and after each stage's solve and holds them fixed during it.
One run of the plan therefore alternates between the intensities and the profile a fixed number of times, and running the plan again continues the alternation.
The alternation does not descend one objective.
From a good start Rwp falls to a fixed point, and from a poor one it can rise for as many passes as you allow.

`RefinementPlan.lebail_passes`, mirrored by `PlanSpec.lebail_passes`, caps the passes.
At 1, the default, `fit` runs the plan once.
Above 1 under `mode="lebail"`, `fit` runs the plan again from where it ended and stops at the first pass that does not lower Rwp.
A pass that lowers Rwp by less than 1e-4 of its value counts as a fixed point.
The fit then restores the pass with the lowest Rwp, and `LEBAIL_ALTERNATION_STOPPED` in `RefinementResult.diagnostics` gives the stop reason, the Rwp of every pass and the pass kept.
The setting does nothing in the other two modes.

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
import dataclasses

plan = dataclasses.replace(rx.PLAN_PRESETS["profile_only"](), lebail_passes=8)
result = ref.fit(data, mode="lebail", plan=plan)
stop = next(d for d in result.diagnostics if d.code == "LEBAIL_ALTERNATION_STOPPED")
print(stop.message)
```

On the 11-BM LaB<sub>6</sub> + cBN pattern, fitted from 5.1° to 25° 2θ with `profile_only` and a cap of 8, the cell start decides the shape:

| Lattice parameters at start | Rwp per pass (%) | Kept |
|---|---|---|
| exact | 13.952, 13.936, 13.937 | pass 2, a fixed point |
| 0.15 % short | 19.206, 14.214, 13.958, 13.938, 13.937 | pass 5, a fixed point |
| 0.36 % long | 13.918, 13.932 | pass 1 |
| 2 % long | 807.219, 188.584, 209.594 | pass 2 |

The answer depends on the start, so check the lattice parameters and the background before you read a kept pass.
Measured on macOS arm64 with the `[dev]` install, 2026-10-20; the compiled and numpy kernels gave the same figures.

Calibrating an instrument on a standard whose structure is known is one staged Rietveld fit, because the structure fixes the intensities and there is nothing to alternate.

## Plans

`PLAN_PRESETS` maps each preset name to the function that builds it.
Call the function to get a fresh `RefinementPlan`, so that an edit to one plan never reaches another.
`PLAN_INFO` maps the same names to a `PlanInfo` that says what the preset is for.
A test holds the two in step, so a preset cannot ship without its description.

```python
import rietx as rx

assert set(rx.PLAN_INFO) == set(rx.PLAN_PRESETS)

info = rx.PLAN_INFO["lab_calibrate"]
print(info.title)
print(info.modes)
```

```text
Lab: calibrate on a standard
('rietveld',)
```

| Field | Holds |
|---|---|
| `PlanInfo.title` | a short label, for a menu |
| `PlanInfo.description` | what the stages do, in order |
| `PlanInfo.modes` | the modes the plan is meaningful in |
| `PlanInfo.when_to_use` | the situation that should select it |

`PlanInfo.modes` is a tuple because `profile_only` is both the Le Bail plan and the way to fit a profile in Rietveld mode without touching the structure.
`pawley_default` is the only Pawley preset, and every preset but `profile_only` and `pawley_default` is Rietveld only.
`Capabilities.plans` carries the same four facts as `PlanCapability` rows ([Plans](programs.md#plans)).

A `RefinementPlan` holds its stages and five settings.

| Field | Default | Holds |
|---|---|---|
| `RefinementPlan.stages` | required | the `Stage` list, in order |
| `RefinementPlan.correlation_guard` | 0.98 | the \|ρ\| above which a stage reports a correlated pair |
| `RefinementPlan.intermediate_ftol` | 1e-6 | the tolerance every declared stage but the last stops at ([Stage tolerances](#stage-tolerances)) |
| `RefinementPlan.lebail_passes` | 1 | the cap on Le Bail passes ([Le Bail passes](#le-bail-passes)) |
| `RefinementPlan.phase_support_sigma` | 3 | the number of esds a phase's scale must sit from zero for the stage to treat the phase as seen; `None` skips the test ([Held parameters](#held-parameters)) |
| `RefinementPlan.closing_window_tol` | 1e-3 | the fraction of each peak's area the closing stage's windows may drop; `None` runs no closing stage ([The closing stage](#the-closing-stage)) |

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_default()
assert plan.correlation_guard == 0.98

strict = rx.RefinementPlan(stages=plan.stages, correlation_guard=0.9)
```

Lowering `correlation_guard` reports more pairs and leaves the fit unchanged, because the guard measures the fit and constrains nothing.

(strategy-harmonics)=
### Monochromator harmonic stage

No preset frees an emission-line weight, so a declared λ/n harmonic, {eq}`pos-harmonic-d`, needs a stage of your own ([Monochromator harmonics](instrument.md#monochromator-harmonics)).
Put it last:

```python
import rietx as rx

base = rx.RefinementPlan.mccusker_structural()
plan = rx.RefinementPlan(stages=[
    *base.stages,
    rx.Stage("harmonic", ["instrument.source.lines.*.weight"]),
])
assert plan.stages[-1].name == "harmonic"
```

Check for a harmonic whenever the monochromator does not filter its higher orders.
The harmonic diffracts the same hkl from a smaller d, so its peaks sit at lower 2θ than the fundamental's.
The signature is extra intensity there, with a goodness of fit worse than a clean pattern of the same specimen, while Rwp may look better.
Rwp is dominated by the strong peaks, and the harmonic's are weak peaks where the model has nothing.
The goodness of fit measures the misfit against σ, so a fit with a respectable Rwp and a goodness of fit far from 1 is the case to suspect.

The weight is a small fraction, it correlates with the background, and the scale and the displacement parameters can each imitate part of it.
Freed early, it takes intensity that belongs to the profile, and nothing in the result shows that it did.
Freed after the profile and the scale have settled, it gets only the intensity nothing else claimed.

Three diagnostics report the outcome.

- [`HARMONIC_FRACTION`](diagnostics-refinement.md#harmonic_fraction) gives the refined weight as a percentage of the fundamental with its esd. The fractions reported for real instruments are a few per cent. Above 15 % it is reported at `warning`, since a fraction that large usually means the line is absorbing something else: an unindexed impurity, a magnetic contribution or a background too stiff to follow.
- [`HARMONIC_ABSENT`](diagnostics-refinement.md#harmonic_absent) means the weight refined below 0.1 % of the fundamental. The beam carries no measurable order-n component, as a monochromator whose nth order is extinct must give, and the declaration can be dropped.
- [`HARMONIC_HELD`](diagnostics-refinement.md#harmonic_held) means the weight was never freed, so the reported fraction is the declared value and is not a result.

`diagnose(data)` runs a related check before any fit ([Contamination](pattern-diagnostics.md#contamination)).
It asks whether several strong reflections carry a Kβ or tungsten Lα line at one common ratio, and needs no structure.
It cannot see a contamination below about 10 % of the parent peak.
The harmonic stage needs a converged model, and it finds a contamination whose peaks overlap the fundamental's too closely for a peak search to separate.

## Stage tolerances

`RefinementPlan.stage_ftols` gives the termination tolerance each stage runs at.
The tolerance is the relative decrease in cost below which the solver stops.

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
assert plan.intermediate_ftol == 1e-6

ftols = plan.stage_ftols()
assert len(ftols) == len(plan.run_stages())
assert set(ftols[:-2]) == {1e-6} and ftols[-2:] == [None, None]
```

The list is parallel to `RefinementPlan.run_stages`: the declared stages, then the closing stage ([The closing stage](#the-closing-stage)).
Three rules decide a stage's tolerance, in this order.

1. A stage that declares `Stage.ftol` runs at it.
2. The last declared stage runs at the solver's default of 1e-9, shown as `None`, because it produces the answer. The closing stage after it runs at 1e-9 too.
3. Every other stage runs at `RefinementPlan.intermediate_ftol`.

A one-stage plan is therefore all last stage, and nothing is loosened.
`StageResult.ftol` records the tolerance each stage ran at, so a result says which schedule produced it.
`PlanSpec.intermediate_ftol` carries the setting into a project file and a history header, and the GUI's text document writes it as the `tolerance` line ([The GUI as a text document and a wire](gui-power.md)).

### Cost of the loose schedule

Each stage frees its parameters on top of everything already free.
A parameter an early stage left short of convergence keeps refining in every later stage, and the last stage converges all of them together at 1e-9.
So stopping the earlier stages sooner moves the answer little, on any plan.

Measured on the single-fit cases of `examples/bench_refinement.py` against the same plans with `intermediate_ftol=None`, three interleaved repeats each, on macOS arm64 with the `[dev]` install, 2026-10-20:

| Case | Evaluations | Wall clock in s | Largest shift | Largest phase-fraction change |
|---|---|---|---|---|
| `nac` | 44 → 39 (1.13×) | 0.36-0.38 → 0.35-0.36 | 0.000 esd | 0.0000 wt % |
| `cpd-1a` | 265 → 162 (1.64×) | 1.22-1.29 → 1.01-1.05 | 1.23 esd, inside a degenerate pair | 0.0055 wt % |
| `cpd-2` | 395 → 256 (1.54×) | 3.14-3.24 → 2.29-2.34 | 0.001 esd | 0.0003 wt % |
| `trigger` | 89 → 73 (1.22×) | 2.04-2.18 → 1.75-1.88 | 0.001 esd | 0.0000 wt % |

Rwp agreed to five decimal places or better in every case.
The 1.23 esd on `cpd-1a` is the instrument's Lorentzian `x` against the phases' `lor_size`.
Lorentzian widths add, and both terms widen peaks as 1/cos θ, so the data fix their sum and not the split.
`x` fell by 0.00286 while the `lor_size` of phases 1 and 2 each rose by 0.00286, so the width they add up to stayed put.
Every other parameter moved by less than 0.1 esd.

A series is the case to measure rather than assume.
Each warm start begins from its predecessor's answer, so a small difference in one answer can change how many recovery rungs the next pattern needs.
The per-fit bound above therefore does not carry over to a chain, and the difference can go either way.
On the ten-pattern simulated `trigger` series, the loose schedule took 201 evaluations against 213 (8.6-8.7 s against 8.7-8.8 s), with no pattern escalating.

### Converging every stage

Set `intermediate_ftol` to `None`:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.intermediate_ftol = None
assert plan.stage_ftols() == [None] * len(plan.run_stages())
```

Every stage then stops at the solver's default, as every fit before 1.1 did, to the bit.
Use it for a number going into a paper, for a number reproduced from an earlier release, and in a test that pins a value.

## The closing stage

Every plan ends with one more stage than it declares.
The closing stage compiles the model again at the answer, with peak windows that drop `RefinementPlan.closing_window_tol` of each peak's area, and solves once more with every pattern any declared stage freed.

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
assert plan.closing_window_tol == 1e-3

stages = plan.run_stages()
assert len(stages) == len(plan.stages) + 1
assert stages[-1].name == "closing"
assert plan.stage_window_tols()[-1] == 1e-3
```

`RefinementPlan.closing_stage` returns the closing stage, or `None` for a plan without one.
`RefinementPlan.stage_window_tols` lists the window fraction of each stage in `run_stages`, with `None` for a declared stage's 2 %.

A stage fixes its peak windows, its reflection list and its axial-divergence sample points at the values it starts from, and holds them while the solver runs ([The forward model](../theory/forward-model.md)).
Each window drops 2 % of its peak's area, and more once a peak widens during the stage.
Two errors reach the answer of a plan without a closing stage:

- The missing tails move refined values. Computed out to 5e-5 of the area, lab answers moved by up to 0.97 esd (the zincite scale on CPD cpd-1a, the Lorentzian size on the GSAS-II fluorapatite), and the background coefficients by 2 to 5 esd.
- The answer depends on the start. Biso started at 0.5 and at 1.5 Å² on every atom put the fluorapatite's Biso 0.12 esd apart, because each start stopped the early stages elsewhere.

The closing stage takes the last declared stage's iteration budget, Le Bail cycles, restraint weight, window slack and `Stage.ftol`, and seeds nothing.
It takes the solver's default tolerance, as the last declared stage does.
`RefinementResult.stages` ends with it under the name `closing`, and `StageResult.window_area_tol` and `NodeAction.window_area_tol` record the fraction.
A model rebuilt from `RefinementResult.parameters` reproduces the result's χ² when compiled at the default windows, which are the closing stage's: `compile_model` and `Refinement.predict` evaluate outside a fit at `CLOSING_WINDOW_TOL`.
A declared stage records `None`, the declared stages' 2 %, so a fit run without a closing stage is rebuilt with `window_area_tol=recorded_window_tol(result.stages[-1].window_area_tol)` (`rietx.model.forward.recorded_window_tol`).
At any window fraction under the declared stages' 2 %, the axial-divergence asymmetry is sampled at a finer node rule as well.
So a `closing_window_tol` loosened past 1e-3 for speed loosens the windows alone.

Measured on SRM 660c LaB6, the fluorapatite, cpd-1a and 11-BM NAC, each under its acceptance protocol (macOS arm64, `[dev]`; times from 2026-10-21):

| | Fluorapatite | cpd-1a | NAC | LaB6 |
|---|---|---|---|---|
| Two Biso starts, largest difference in plain esd, without → with | 0.119 → 0.000 | 15.3 → 15.7 | 0.008 → 0.000 | 0.20 → 1.16 |
| Fit time with the closing stage | 2.20-2.33× | 1.60-1.62× | 1.2× | 1.42-1.44× |

cpd-1a's starts differ on fluorite's Lorentzian strain, through the X and Y split its plan holds (`StageResult.width_twins_held`).
`tests/test_window_domain.py` holds the closing answer within 0.1 plain esd of the answer with converged tails on the fluorapatite, cpd-1a and NAC (0.008 to 0.019 esd).
LaB6 misses it by 0.9 esd on `instrument.profile.u`.
Its highest-angle reflections end with a Gaussian variance under the floor the width is clamped to, and there a recompile moves `u` by an esd at any window.

BGMN ends its refinements the same way, with every parameter free and restarted from the previous answer (Doebelin and Kleeberg 2015).
RIETAN-FP's automatic mode ends with everything refining together, and moves its windows at every evaluation.
1e-3 drops less of a Lorentzian peak than TOPAS (2.0 %), MAUD (2.1 %), RIETAN-FP and FullProf, and more than GSAS-II (0.5 %), BGMN and EasyDiffraction, which compute the whole peak.

Set `closing_window_tol` to `None` to run the declared stages alone, for speed:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.closing_window_tol = None
assert plan.run_stages() == plan.stages
```

The answer is then that of every fit before the setting, to the bit.
On the four patterns above it lands 0.15 to 0.96 plain esd from the closing stage's answer.
In physical units, cpd-1a's phase fractions move by up to 0.12 wt%, the fluorapatite's Lorentzian size by 2.5 % and its strain by 3 %, LaB6's widths by 1-2 %, and NAC's values by under 0.4 %.
A long series or a large batch is the case for it: each pattern pays the closing stage's cost.
Its FitReport still reads the misfit at the closing precision ([Region attribution](report.md#region-attribution)).
On the fluorapatite and cpd-1a, a reading at the fit's own 2 % printed the same report.
`PlanSpec.closing_window_tol` carries the setting into a project file, and the GUI's text document writes it as the `closing` line.
`Refinement.run_stage` runs no closing stage, so its `window_area_tol` defaults to the closing stage's fraction; pass `rietx.model.forward.WINDOW_AREA_TOL` for the declared stages' faster windows.

## Stage fields

A `Stage` is `Stage.name`, a list of patterns in `Stage.turn_on`, and seven settings that decide how the stage is solved.
`Stage.name` is a label, carried to `StageResult.name` and the event stream.
`Stage.turn_on` holds the parameter names the stage frees, matched with `fnmatch` against the names in the [parameter map](parameters.md).
[Stage settings](settings.md#stage-settings) gives each setting with its default.

```python
import rietx as rx

stage = rx.Stage("widths", ["instrument.profile.*"], max_iter=200)
assert stage.max_iter == 200
assert stage.seed == 0.0 and stage.strain_seed == 0.0
assert stage.lebail_cycles == 3
```

`Stage.max_iter` bounds the solver's work.
Both drivers count residual evaluations, so the bound is four evaluations per iteration, the measured worst case.
A stage that reaches it ends with status `max_iter` and reports [`STAGE_MAX_ITER`](diagnostics-refinement.md#stage_max_iter), a result to read and not an exception.

`Stage.ftol` overrides the plan's schedule for one stage: an early stage whose answer the next is unusually sensitive to, or a one-stage fit that must converge as hard as a last stage.

`Stage.seed` and `Stage.strain_seed` both start a parameter away from an exact zero, and they are not interchangeable.

- `Stage.seed` lifts each parameter the stage frees that sits exactly on a lower bound of 0 or above to the given value. A value already above its bound starts where it is, and a parameter that can go negative, such as Caglioti `U` and `V` or the zero shift, is never seeded. The surface-roughness stage seeds at 0.3, because Suortti roughness has no effect at b = 0 and the data see it best near b = 0.2 to 0.5. It is the only shipped stage that seeds. Extinction and the two magnetic widths are freed from 0 with no seed, since each one's column at 0 is its physical one. `StageResult.seeded` lists every row a stage lifted.
- `Stage.strain_seed` puts a freed, all-zero Stephens block on a small isotropic microstrain, in ppm of ΔM/M. Those coefficients can go negative, so `Stage.seed` does not reach them, and at zero the square root in their width law has unbounded slope.

`Stage.lebail_cycles` is the number of intensity-partitioning cycles run before and after each solve in Le Bail mode.
In Pawley mode it sets the Le Bail partition that seeds the intensities when none were carried in, and Rietveld mode ignores it.
`Stage.restraint_weight_scale` weights the restraints against the data for the stage ([How to restrain a bond length or an angle](../guides/restrain.md)).
`Stage.window_slack_deg` replaces the default capture margin in °2θ around each reflection's evaluation window.
The indexing Le Bail validation sets it, because it holds a candidate cell fixed and a wrong candidate displaces peaks by whole degrees.
Leave it unset in ordinary plans.

## Stored plans

`RefinementPlan` and `Stage` are plain Python classes, convenient to edit in code, and they do not convert to JSON.
`PlanSpec` and `StageSpec` are their mirrors, which convert to JSON.

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_default()

spec = rx.PlanSpec.from_plan(plan)
restored = spec.to_plan()

assert [s.name for s in restored.stages] == [s.name for s in plan.stages]
assert spec.correlation_guard == plan.correlation_guard
```

`PlanSpec.from_plan` and `PlanSpec.to_plan` convert a plan, and `StageSpec.from_stage` and `StageSpec.to_stage` a stage.
`PlanSpec.stages` is a list of `StageSpec`.
A `StageSpec` carries every `Stage` field under the same name: `StageSpec.name`, `StageSpec.turn_on`, `StageSpec.max_iter`, `StageSpec.ftol`, `StageSpec.lebail_cycles`, `StageSpec.seed`, `StageSpec.strain_seed`, `StageSpec.restraint_weight_scale` and `StageSpec.window_slack_deg`.
`PlanSpec.correlation_guard`, `PlanSpec.intermediate_ftol`, `PlanSpec.lebail_passes` and `PlanSpec.phase_support_sigma` carry the plan's four settings.

Anything that takes one of the pair takes the other.
`fit` accepts a `PlanSpec` read back from a project or a history header, and validating a `RefinementPlan` as a `PlanSpec` converts it:

```python
import rietx as rx

plan = rx.PLAN_PRESETS["mccusker_default"]()

assert rx.PlanSpec.model_validate(plan) == rx.PlanSpec.from_plan(plan)
```

Neither class has a `model_dump`, and asking for one raises an `AttributeError` that names `PlanSpec.from_plan`.

A project file and a history tree store the expanded plan, every stage in full, because that is what runs.
No field records which preset a plan came from, since such a field could disagree with the stages beside it.
`PlanSpec.preset_name` answers by comparison instead, returning the preset the plan equals, or `None` once it has been edited:

```python
import rietx as rx

spec = rx.PlanSpec.from_plan(rx.RefinementPlan.mccusker_default())
assert spec.preset_name() == "mccusker_default"

spec.stages.pop()
assert spec.preset_name() is None
```

The GUI's plan editor labels its menu this way, and the text document prints `plan mccusker_default` in place of five stage lines.

## Stage results

`RefinementResult.stages` is a list of `StageResult`, one per stage, in the order they ran.

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
for stage in result.stages:
    print(stage.name, stage.status, stage.n_iterations,
          stage.cost_initial, stage.cost_final)
```

| Field | Holds |
|---|---|
| `StageResult.name` | the stage's name, as the plan gave it |
| `StageResult.status` | `converged` or `max_iter` |
| `StageResult.n_iterations` | residual evaluations the solve made, the start included |
| `StageResult.cost_initial`, `StageResult.cost_final` | the cost the stage started from and the cost it reached |
| `StageResult.freed` | the parameters this stage's patterns freed, less any the stage held |
| `StageResult.ftol` | the tolerance it ran at; `None` is the solver default |
| `StageResult.n_constraint_truncations` | steps the `lm` driver held on a linear inequality |
| `StageResult.n_degenerate_cell_probes` | trial cells the residual refused for zero or negative volume |
| `StageResult.n_lapack_fallbacks` | LAPACK calls repeated with a second driver after the first failed to converge, the same answer by another route |
| `StageResult.held` | parameters the plan freed that this stage held because the data cannot determine them |
| `StageResult.held_reach` | per held parameter, the tied parameters it also stopped |
| `StageResult.released` | parameters held at the start and freed again within the stage |
| `StageResult.scale_b_held` | per phase whose displacement parameters this stage held as inseparable from its scale over the fitted range, the measured separation; `{}` when it held nothing |
| `StageResult.width_twins_held` | per instrument width held beside its free specimen twin, that twin |
| `StageResult.blocked_by_hold` | parameters the patterns matched and a `Refinement.hold` kept fixed ([How to keep a parameter fixed whatever the plan frees](../guides/hold.md)) |
| `StageResult.unknown_paths` | literal names in `turn_on` naming no parameter of this model, or under a retired spelling |
| `StageResult.unreached_histograms` | joint fits: per histogram, the patterns that freed parameters of another histogram and matched none of this one; `{}` on a single histogram |
| `StageResult.seeded` | each parameter this stage lifted before solving, with the value it started from, `Stage.strain_seed`'s Stephens DOFs included |
| `StageResult.cell_reset` | the free cell parameters this stage put back at their starting values because their phase's cell left the safety window ([`CELL_RUNAWAY`](diagnostics-refinement.md#cell_runaway) says more) |
| `StageResult.collapsed` | the parameters in `held` put back at their starting values because the stage's first solve found them flat ([Held parameters](#held-parameters)) |
| `StageResult.moment_flat_axes`, `StageResult.moment_turned` | magnetic sites whose moment direction the stage held about a flat axis ([Magnetic refinement](magnetic.md#directions-a-powder-cannot-see)) |
| `StageResult.moment_angle_tests` | each round of the stationary-angle test, one `MomentAngleTest` per round; `None` when no test ran ([Magnetic refinement](magnetic.md#an-angle-at-a-symmetry-direction)) |

`StageResult.scale_b_held`, `unknown_paths`, `unreached_histograms`, `seeded`, `cell_reset`, `collapsed` and `width_twins_held` are `None` on a result stored before the field existed, meaning that nothing looked.
The status type also admits `diverged`, which neither driver produces today.
Both drivers accept a step only when it lowers the cost, so `cost_final` never exceeds `cost_initial`.

### Names that free nothing

`StageResult.freed` is the field to read when a stage did nothing.
A pattern that matches no parameter is not an error, because that is how the shipped plans reach a component your model may not declare.
`lab_sample_refine` frees `phases.*.microstrain.dof.*` whether or not a phase carries a Stephens block.

A literal name, with no `*`, `?` or `[`, names one parameter.
If the model has no such parameter the plan is wrong, through a typo or a renamed path.
`StageResult.unknown_paths` lists it, and [`STAGE_PATH_UNKNOWN`](diagnostics-refinement.md#stage_path_unknown) reports it at `warning` with the nearest real name: `instrument.source.lines.0.wavelength` for a stage that names the wavelength without its line index.
It is a diagnostic and not an exception, because one plan runs every pattern of a series.
A wrongly spelt family name inside a pattern looks like one that correctly matched nothing, so no rule can report it, and `freed` is the place to look.

A pattern under a spelling a release retired is reported too.
A saved project, history tree or `.rxt` file is migrated as it is read, but a plan built in code is not.
A pattern under the instrument's `background_peaks`, the name up to v1.2, matches nothing and leaves a declared hump at its start value.
`STAGE_PATH_UNKNOWN` gives its current spelling, `instrument.extra_components.*`.

A literal phase name can also name a parameter the model will not free.
An atom's coordinates refine along the directions its site symmetry allows, as `phases.0.atoms.2.dof.*`, and its `x`, `y` and `z` are each fixed or follow those directions.
A cubic cell's `b` follows `a`.
A stage naming such a parameter frees nothing for it, so [`STAGE_PATH_NOT_FREE`](diagnostics-refinement.md#stage_path_not_free) reports it at `warning` before the first stage runs, with the names that would free it.
For an oxygen on 16h in I4<sub>1</sub>/amd, `phases.0.atoms.2.x` is fixed at 0, and `y` and `z` follow `dof.0` and `dof.1`.
A name you tied yourself is not reported, and neither is an instrument name: the shipped plans name `instrument.geometry.sample_displacement`, which a capillary geometry locks.
A pattern can reach too far the other way: `phases.0.atoms.2.*` frees the site's `occ` and `biso` beside its directions, so write `phases.0.atoms.2.dof.*` for the position alone.

A joint fit has one more way to do nothing, which is to do it on one histogram only ([How to fit an X-ray and a neutron pattern together](../guides/joint.md)).
A pattern written for one instrument's parameter names reaches only the histograms that have them.
A stage whose patterns freed parameters of histogram 0 and matched none of histogram 1 records `StageResult.unreached_histograms == {1: [the patterns]}`, and [`STAGE_FREED_NOTHING`](diagnostics-series.md#stage_freed_nothing) reports it at `info`, once per histogram.
A pattern scoped to one histogram, `hist.0.…`, is not reported, and neither is a parameter that exists and is fixed.

### Held parameters

`StageResult.held` is the field to read when a parameter did nothing.
A stage holds four kinds of parameter at the values it starts from.

- The structural parameters of a phase the data cannot see. A phase reaches the pattern only through scale × \|F\|² × profile, so one whose scale is at its floor or not significant has no measurable structural parameter. Its `scale` is not held on significance, so a phase can appear; with no reflection in range it is held whole. [`PHASE_UNCONSTRAINED`](diagnostics-refinement.md#phase_unconstrained) names the phase and the stages that held it, and its parameters, which nothing measured, are absent from `RefinementResult.parameters`.
- A moment direction the powder average cannot determine ([Magnetic refinement](magnetic.md#directions-a-powder-cannot-see)).
- A phase's displacement parameters when the fitted range cannot separate them from the phase's scale. `StageResult.scale_b_held` gives the measured separation, and [`SCALE_B_INSEPARABLE`](diagnostics-refinement.md#scale_b_inseparable) reports it.
- An instrument width whose specimen twin is free: U with `gauss_strain`, Y with `lor_strain`, X with `lor_size`. The data see only each pair's sum.

A stage holds whichever parameter carries the freedom.
Tie a phase's lattice parameter to a variable of your own, and the variable is what stops moving, so `StageResult.held` names `vars.A`.
`StageResult.held_reach` maps each held parameter to the tied parameters it drove: a held cubic `a` lists the `b` and `c` that follow it, and a held `vars.A` lists the cell it drove.
`held` and `held_reach` together are every value the stage froze.
A variable driving two phases is held only while the data can see neither of them, because one visible phase gives it a gradient.

A hold on an invisible phase is decided per stage.
Each stage of a plan after the first also reads the previous stage's answer, and holds again from the start a phase that answer could not see.
`Refinement.run_stage`, `Refinement.cherry_pick` and the GUI's stage-by-stage path have no previous answer, so they decide from the screen alone.
If the phase appears while a stage solves, the stage lifts the hold, solves a second time, and lists the parameters in `StageResult.released`.
It never solves a third time.
`n_iterations` counts both solves, and `cost_initial` is still the cost the stage started at.
A displacement hold is never lifted within a stage, because a phase with one d-spacing in range keeps it whatever the solve does.

Both lists are empty on every fit whose phases are all visible.

The line between seen and unseen is `RefinementPlan.phase_support_sigma`, mirrored by `PlanSpec.phase_support_sigma`.
A phase counts as seen when its scale sits at least that many esds from zero, the esd taken against the counting noise.
The default is {{ PHASE_SUPPORT_SIGMA }}.
A higher number holds more phases, and `None` skips the significance test:

```python
import dataclasses

import rietx as rx

plan = rx.RefinementPlan.mccusker_default()
assert plan.phase_support_sigma == 3.0

no_test = dataclasses.replace(plan, phase_support_sigma=None)
```

With `None`, no stage holds, releases or restores a phase for weakness, and no cell takes the unseen window; a phase with no line in range is still held whole.
`PHASE_UNCONSTRAINED` still reports a phase under {{ PHASE_SUPPORT_SIGMA }}σ, and names the parameters that refined without signal.
Zero, a negative number, an infinity and a NaN are refused.

A raised threshold has one known cost.
A weak phase whose cell starts more than a peak width from its true value puts its peaks in the wrong place.
It then reads weaker than it is and can stay held at the wrong cell.
On a synthetic in-situ pattern whose CaF<sub>2</sub> cell started 1.2 % off, the default released the cell and refined it.
At 50σ the phase read 3.7σ at the answer, and the cell stayed where it started.

### Solver counts

`StageResult.n_constraint_truncations` counts the steps the default `lm` driver held on a linear inequality.
Each such step crossed an inequality when solved for the bounds alone, and was solved again over the bounds and the inequalities together.
Three constraints are inequalities: the Stephens strain cone, the positivity of a spherical-harmonics texture, and the floor on the Gaussian width at every reflection.
The count is 0 under `solver="trf"`, which has no inequalities, and in a joint fit.
Nonzero in the last stage, it also raises [`CONSTRAINT_ACTIVE`](diagnostics-refinement.md#constraint_active), because the answer sits on or near a constraint.

`StageResult.n_degenerate_cell_probes` counts trials, never the answer.
`Cell` declares no bounds, so a poorly determined cell stage can reach a zero- or negative-volume metric while searching.
Each such trial is pushed back and counted rather than crashing the stage or returning a silent NaN.
A nonzero count is the ordinary outcome on a poorly determined cell, and [`CELL_DEGENERATE_PROBE`](diagnostics-refinement.md#cell_degenerate_probe) sums it over the stages that ran.

## Guards

A guard is a measurement taken after a stage converges.
It changes nothing in the fit, and reports what the fit statistics cannot show.
Each hit is a `GuardFinding`, which carries the finding as data:

```python
import rietx as rx

finding = rx.GuardFinding.correlation("instrument.zero_shift",
                                      "instrument.geometry.sample_displacement",
                                      -0.997)
assert finding.code == "HIGH_CORRELATION"
assert finding.paths == ("instrument.zero_shift",
                         "instrument.geometry.sample_displacement")
assert finding.value == -0.997
print(finding.message)
```

```text
instrument.zero_shift ~ instrument.geometry.sample_displacement (ρ=-0.997)
```

| Field | Holds |
|---|---|
| `GuardFinding.code` | the diagnostic code the finding becomes |
| `GuardFinding.paths` | the parameters it is about |
| `GuardFinding.value` | the headline number, or `None` |
| `GuardFinding.message` | the rendered finding; `str(finding)` returns it |
| `GuardFinding.detail` | a clause a bound finding adds to its diagnostic, empty on every other kind |
| `GuardFinding.limit` | the bound that held the parameter, such as `("lower", 0.0)`, on a bound finding only |

A program reads `paths` to offer a link and `value` to sort, so nothing has to take a string apart.
Each kind has one constructor, so each format string is written once:

| Constructor | Code | Fires when | `value` |
|---|---|---|---|
| `GuardFinding.correlation` | `HIGH_CORRELATION` | two free parameters correlate above the plan's `correlation_guard` | ρ |
| `GuardFinding.flat_direction` | `FLAT_DIRECTION` | a correlated pair reaches \|ρ\| = 1.000 to the three decimals the message prints, so the data do not separate them | ρ |
| `GuardFinding.discarded_direction` | `COVARIANCE_DIRECTION_DISCARDED` | three or more parameters share a direction the covariance solve discards, which no pairwise correlation shows, so each esd is at least √2 too small | the number of directions |
| `GuardFinding.at_bound` | `BOUND_HIT`, or `FLOOR_HIT` on a lower bound at 0 | a bound carried load at the answer | the residual's cosine with the column, or `None` where no solve stood behind the test |
| `GuardFinding.background_absorption` | `BACKGROUND_ABSORPTION` | the background could largely reproduce a structural parameter's column | the block R² |
| `GuardFinding.roughness_absorption` | `ROUGHNESS_ABSORPTION` | the surface-roughness correction could | the block R² |
| `GuardFinding.nonpositive_adp` | `ADP_NOT_POSITIVE_DEFINITE` | an anisotropic displacement tensor is not positive definite | the smallest eigenvalue |
| `GuardFinding.nonpositive_strain` | `STEPHENS_STRAIN_NOT_POSITIVE` | a Stephens block gives a negative σ²(M) for some reflection | the worst σ²(M) |
| `GuardFinding.nonpositive_texture` | `TEXTURE_NOT_POSITIVE` | a spherical-harmonics texture gives a negative pole density somewhere on the sphere | the lowest value on the sphere |
| `GuardFinding.nonpositive_resolution` | `RESOLUTION_NOT_POSITIVE` | an instrument width, Γ<sub>G</sub>² or Γ<sub>L</sub>, goes below zero in the fitted range; the model clamps Γ<sub>G</sub> to a floor | the worst Γ<sub>G</sub>² or Γ<sub>L</sub> |
| `GuardFinding.unsupported_resolution` | `RESOLUTION_UNCONSTRAINED` | the Gaussian resolution terms were refined on a pattern whose peaks are mostly Lorentzian | the Gaussian share of the width |
| `GuardFinding.narrow_hump` | `HUMP_TOO_NARROW` | a declared hump has narrowed below four times the instrumental width, where it is a reflection rather than a background feature | its width over the instrumental width |
| `GuardFinding.large_biso` | `BISO_UNUSUALLY_LARGE` | an isotropic displacement parameter is past the Lindemann melting bound computed from its phase's cell | B |
| `GuardFinding.negative_biso` | `BISO_NEGATIVE` | an isotropic displacement parameter is below zero; `Atom.biso` has no default bound | B |

`GuardFinding.code` is an open vocabulary of strings, and it is the same vocabulary as `Diagnostic.code`, so a guard maps to its diagnostic as data ([Diagnostics](result.md#diagnostics)).

Read a guard as evidence about what the data could support, and not as a verdict on the model.
A `nonpositive_strain` finding means those coefficients are not quotable, and it is no measurement of anisotropy.

## Events

`events=` streams every stage boundary and residual evaluation to a destination you choose, beside the run directory the fit writes for itself ([How to watch or stop a running fit](../guides/watch.md)).
A path appends each event to that file as one line of JSON.
A function is called with each event as a dictionary:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
def show(event):
    print(event["kind"], event["data"])

result = ref.fit(data, events=show)
```

Each event carries `record` (always `"event"`), `v` (the event schema version), `t` (a Unix time), `kind` and an open `data` dictionary.
A fit emits five kinds: `fit_start` and `fit_end` for the run, `stage_start` and `stage_end` for each stage, and `eval` for each residual evaluation.
An indexing search adds `index_start` and `index_end`.
A five-stage fit of the fluorapatite tutorial pattern emitted 1 `fit_start`, 5 `stage_start`, 102 `eval`, 5 `stage_end` and 1 `fit_end`.

| Kind | `data` keys in this version |
|---|---|
| `fit_start` | `mode`, `stages`, `n_points`, `n_fitted` |
| `stage_start` | `stage`, `index`, `n_stages`, `turn_on`, `freed`, `n_free`, `free_paths`, `held`, `unknown_paths`, `n_points` |
| `eval` | `stage`, `n_eval`, `cost`, `accepted`, `lam`, `step_norm`, `values` |
| `stage_end` | `stage`, `status`, `termination`, `n_iterations`, `cost_initial`, `cost_final`, `rwp`, `held`, `released` |
| `fit_end` | `status`, `rwp`, `gof`, `node_id` |

Read `data` with `.get`, because a version may add keys to a kind without a version change.
A cancelled run's `fit_end` has `status` `"cancelled"`, the abandoned `stage`, the `completed` stage names and `node_id`, and no `rwp` or `gof`, because there is no fitted result.
Under `RefinementPlan.lebail_passes`, each pass's `fit_start` and `fit_end` also carry `lebail_pass` and `lebail_of`.
A run's state is not an event: it is in the run's `status.json`, because a fit killed outright emits no `fit_end`.

A path is opened for appending, so a second fit given the same path adds to the same file.
The first line each stream writes is a run header, `{"record": "run", "v": "3", "t": …, "run": <id>, "data": {"pid": …}}`, which is not an event and never reaches a function.
`rietx.history.events.read_events` returns the events and skips the headers, and `rietx events` prints a log run by run ([`rietx events`](cli.md#rietx-events)).
A reader that branches on `kind` checks first that `record` is `"event"`.

Your function runs outside the recorder's protection, so an exception it raises stops the fit.
`Capabilities.event_schema_version` reports the version this build emits ([Compatibility](compatibility.md)).

## Recording and run names

Every fit writes a run directory unless recording is off ([Run directories outside a project](project.md#run-directories-outside-a-project)).
Recording changes no number the fit produces.
Its cost is near constant per stage, so the shortest fit pays the largest share.
With `examples/bench_refinement.py`, five interleaved repeats on macOS arm64 with the `[dev]` install, 2026-10-20, recording took the median wall clock to these multiples of the same fit with recording off:

| Case | Fit without recording | With recording | Run directory |
|---|---|---|---|
| `nac`, 6 stages | 0.34 s | 1.21× | 356 kB, of which 331 kB is `snapshot.json` |
| `cpd-1a`, 8 stages | 1.00 s | 1.14× | 361 kB |
| `cpd-2`, 9 stages | 2.24 s | 1.07× | 464 kB |

`snapshot.json` is rewritten at each stage, so it does not grow with the run.
The event log does grow, by about 0.5 kB to 0.8 kB per event on these cases.

`label=` names the run in `rietx watch`'s list.
Without one, a run takes the name of its working directory or its project.
`Refinement.fit`, `Refinement.run_stage`, `refine`, `SequentialRefinement.fit`, `refine_sequential`, `Project.fit` and `Project.run_stage` all take it.
The name goes to the run's `meta.json` and reaches no history node and no result.

A series is one run directory however many patterns it walks, so `label=` names the whole series, and `labels=` names its patterns.
A sequence passed to `label=` raises `TypeError` rather than being written.

## Cancellation

`cancel=` takes a `CancelToken`, which another thread sets:

```python
import rietx as rx

token = rx.CancelToken()
assert not token.is_set()
token.cancel()
assert token.is_set()
token.reset()
```

`CancelToken.cancel` requests the stop and returns at once.
`CancelToken.reset` clears the token for the next run.

The fit reads the token between residual evaluations, so it never stops part-way through one.
The stage in flight is abandoned: it commits no history node, and the structure and instrument go back to the values that stage started from.
That restore matters for a seeding stage, which writes to the models before it solves.
The fit then raises `RefinementCancelled`, which carries what completed:

| Attribute | Holds |
|---|---|
| `RefinementCancelled.stage` | the name of the abandoned stage |
| `RefinementCancelled.completed_stages` | a `StageResult` for each stage that finished; empty if the first stage was cancelled |
| `RefinementCancelled.node_id` | the history node the working state stands at; `None` with history off, or when nothing completed |

A Le Bail fit cancelled during a later pass returns to the best pass so far, and `node_id` names that pass's node.

`rietx watch` can stop a run that passed no `cancel=` ([Stopping a fit](cli.md#stopping-a-fit)).
The fit raises the same `RefinementCancelled` in its own process, so code that catches it needs no change.
The run's `status.json` records `cancelled_by` when a request from the page caused the stop, and nothing when a `CancelToken` in the fitting code did.
The exception carries no such field.

## Provenance

`RefinementResult.provenance` is a `Provenance`, the record of how the result was computed.

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
print(result.provenance)
```

A 1.10 development build printed this:

```text
Provenance
  package_version:           '1.10.0.dev0'
  schema_version:            '0.59'
  backend:                   'numpy'
  dtype:                     'float64'
  solver:                    'lm'
  report_thresholds_version: '1.12'
  created_utc:               '2026-10-20T02:29:39Z'
```

| Field | Holds |
|---|---|
| `Provenance.package_version` | the rietx version that produced it |
| `Provenance.schema_version` | the version of the data contract the objects follow |
| `Provenance.backend` | the backend the arrays were computed on |
| `Provenance.dtype` | the precision: `"float64"`, or `"float64/jacobian:float32"` on the Apple-GPU backend |
| `Provenance.solver` | the least-squares driver |
| `Provenance.report_thresholds_version` | the version of the thresholds a report is judged against |
| `Provenance.created_utc` | when the result was assembled, in UTC |
| `Provenance.notes` | free-form string pairs; a refinement writes none, and an indexing answer records its search settings there |

Read `Provenance.backend`, `Provenance.dtype` and `Provenance.solver` back rather than assuming them, because the record survives the code that called the fit.
`Provenance.schema_version` and `Provenance.report_thresholds_version` are two of the contract versions `capabilities()` reports, and [Compatibility](compatibility.md) says what a change to one means.
