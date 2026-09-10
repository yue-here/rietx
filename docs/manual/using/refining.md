# Running a refinement

[](model.md) is the table of parameters a fit can move. This chapter is the
run itself: which call to make, what the intensities are allowed to do, how the
stages are chosen and settled, and how to watch a run or stop one that is going
nowhere.

[](concepts.md) explains *why* a refinement is staged and what order the
presets encode. Nothing here repeats that argument. What follows is the
machinery around it: the settings a caller chooses, and the record a run leaves
behind.

## Two entry points, and where the settings live

`refine` runs one refinement and returns a `RefinementResult`:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
import rietx as rx

result = rx.refine(data, structure, instrument, plan="mccusker_default")
```

`Refinement` is the same machinery kept open, so the model survives the fit and
can be edited, inspected and re-fitted:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
ref = rx.Refinement(structure, instrument)
result = ref.fit(data)
```

The two take different arguments, and what goes where follows one rule. A
setting that decides how every fit in the object is computed belongs to the
constructor; a question asked of one pattern belongs to the call.

| Setting | Where it goes | Why there |
|---|---|---|
| `backend`, `solver` | the `Refinement` constructor (and `refine`) | they decide how every residual and Jacobian in that object is computed, so they belong to the object rather than to one fit |
| `history` | the `Refinement` constructor (and `refine`) | a tree spans many fits ([](history.md)) |
| `mode`, `plan`, `two_theta_limits` | `Refinement.fit` | one question asked of one pattern |
| `events`, `cancel` | `Refinement.fit` | they belong to a single run in flight |

So `Refinement.fit` takes no `backend=` or `solver=`. Choose those when you
build the object:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument, backend="numpy", solver="trf")
```

`backend` selects how the arrays are computed and `solver` selects the
least-squares driver. `numpy` and `trf` are the defaults and the answer for
almost every caller; [](install.md) covers what the optional backends buy and
what they cost, and `Capabilities.backends` and `Capabilities.solvers` report
what the build in front of you actually has.

`Refinement.result_` holds the most recent result, so a caller that fitted in
one place can read it in another without threading the return value through:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
ref.fit(data)
print(ref.result_.statistics.rwp)
```

## Modes: what the intensities are allowed to do

`mode` decides where a reflection's intensity comes from.

| Mode | Intensities | Use it when |
|---|---|---|
| `"rietveld"` | computed from the structure | you have a structural model and want to refine it |
| `"lebail"` | extracted from the data, iteratively | you want the best profile fit a cell and symmetry can give, with no structure |
| `"pawley"` | refined, one per reflection | as Le Bail, but with the intensities as real parameters carrying esds |

The mode is not a detail of the plan; it changes which rows of the parameter
table can move at all. Le Bail and Pawley force-fix every atom parameter, every
phase scale and every emission-line intensity, because in those modes the data
does not constrain them. [](model.md) shows that as the `mode_fixed` hold
reason, and explains why it is kept distinct from a lock.

`RefinementResult.mode` echoes the mode a result was produced under, so a
stored result cannot be misread later:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
result = ref.fit(data, mode="lebail")
assert result.mode == "lebail"
```

`Capabilities.modes` lists them, for a program that offers the choice.

## Choosing a plan at run time

[](concepts.md) introduces the seven presets and the order they encode. What
that section does not give a *program* is a way to offer the choice without
hard-coding a list that will rot the next time a preset lands.

`PLAN_PRESETS` maps each preset name to the function that builds it, and
`PLAN_INFO` maps the same names to a `PlanInfo` describing what the preset is
for. The entry is the builder rather than the plan: call it, then edit what
comes back. Each call returns a fresh `RefinementPlan`, so one caller's edit never
reaches another:

```python
import rietx as rx

assert set(rx.PLAN_INFO) == set(rx.PLAN_PRESETS)

info = rx.PLAN_INFO["lab_calibrate"]
print(info.title, info.description, info.modes, info.when_to_use)
```

| Field | Holds |
|---|---|
| `PlanInfo.title` | a short label, for a menu |
| `PlanInfo.description` | what the stages do, in order |
| `PlanInfo.modes` | the modes the plan is meaningful in |
| `PlanInfo.when_to_use` | the condition that should select it |

`PlanInfo.modes` is a tuple rather than a single mode because a plan can be
meaningful in more than one: `profile_only` is both the Le Bail plan and the
way to fit a profile in Rietveld mode without touching the structure.

The two registries are held in bijection by a meta-test, so a preset added
without a `PlanInfo` fails the suite rather than shipping as a preset nobody
can be told when to use. `Capabilities.plans` carries the same four facts
through the JSON surface as `PlanCapability`, keyed by `PlanCapability.name`;
[](agents.md) reads that side.

A plan also carries two settings of its own. `RefinementPlan.correlation_guard`
is the |ρ| above which a stage reports a correlated pair, default 0.98:

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_default()
assert plan.correlation_guard == 0.98

strict = rx.RefinementPlan(stages=plan.stages, correlation_guard=0.9)
```

Lowering it reports more pairs. It does not change the fit: the guard measures
the fit rather than constraining it.

(strategy-harmonics)=
### Checking for monochromator harmonic contamination

No shipped preset frees an emission-line weight, so a declared λ/n harmonic
([](data.md), {eq}`pos-harmonic-d`) needs a stage of your own. Where to put it
is a strategy question rather than a detail:

```python
import rietx as rx

base = rx.RefinementPlan.mccusker_structural()
plan = rx.RefinementPlan(stages=[
    *base.stages,
    rx.Stage("harmonic", ["instrument.source.lines.*.weight"]),
])
assert plan.stages[-1].name == "harmonic"
```

**Check for it whenever a monochromator's order is not filtered.** The
signature is extra intensity at 2θ *below* the fundamental's peaks — the
harmonic diffracts the same hkl from a smaller d — together with a **GoF worse
than a clean histogram of the same specimen**, while Rwp may well look better.
That asymmetry is the whole diagnosis: Rwp is dominated by the strong peaks, and
the harmonic's are weak peaks sitting where the model has nothing, so GoF
measures the misfit against σ and Rwp mostly does not. A fit whose Rwp is
respectable and whose GoF is far from 1 is the case to suspect.

**Free the weight last.** It is a small fraction, it correlates with the
background, and both the scale and the displacement parameters can imitate part
of it. Freed early it takes intensity that belongs to the profile, and the
record does not show that it did. Freed after the profile and the scale have
settled, it has only the intensity nothing else claimed.

**Read the fitted fraction as a property of the beam, or not at all.** The
`HARMONIC_FRACTION` diagnostic reports it as a per cent of the fundamental with
its esd, because that is the number worth judging. A value far from a few per
cent is evidence that the model is absorbing something else through the line —
an unindexed impurity, a magnetic contribution, a background too stiff to
follow — rather than a measurement of the monochromator, and past 15 % the
diagnostic says so at `warning` level. A fraction that refines to nothing is a
result too: `HARMONIC_ABSENT` means the beam carries no measurable order-n
component, which is what a monochromator whose nth order is extinct must give,
and the declaration can then be dropped for one parameter fewer. A weight that
was never freed reports `HARMONIC_HELD` and must not be quoted at all.

Two related checks are **model-free and run before any fit**, and neither
substitutes for this one: `diagnose(data)` looks for a weak peak at the Kβ or
W Lα position of a strong one and returns `ContaminationFlag`s, needing no
structure, answering "does something here look like a known contaminant?". This
one needs a converged model and answers "how much intensity did the model
attribute to the harmonic once everything else had its chance?" — which is the
only way to see a contamination whose peaks overlap the fundamental's too
closely for a peak search to separate.

## How hard each stage is converged

`RefinementPlan.intermediate_ftol` is the termination tolerance every stage but
the last is solved at, and it defaults to `1e-6` against the solver's own
`1e-9`. `RefinementPlan.stage_ftols` is where that becomes a per-stage answer:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
assert plan.intermediate_ftol == 1e-6

ftols = plan.stage_ftols()
assert set(ftols[:-1]) == {1e-6} and ftols[-1] is None
```

Three sources decide a stage's tolerance, in this order. A stage that declares
its own `Stage.ftol` is solved at it. The last stage takes `None`, meaning the
solver default, because it is the one that produces the answer. Every other
stage takes `intermediate_ftol`. A one-stage plan is therefore all endpoint and
nothing is loosened, which is what a warm series pattern collapsed to a single
stage and the indexing validation fit both want.

`StageResult.ftol` reports what each stage was actually solved at, so a result
says which schedule produced it without the plan beside it.

### What the loosened schedule costs

Stages are cumulative: each one frees its globs on top of everything already
free, so a parameter an early stage stopped short on keeps refining in every
later stage, and the last stage, at `1e-9`, polishes all of them together.
That is why stopping intermediate stages early moves the answer so little, and
it holds for any plan this runner runs, not only for the presets.

Measured on the benchmark cases of `examples/bench_refinement.py` (`[dev]`
venv, darwin/arm64, 2026-08-22, best of three runs on an idle machine), against
the same plans with `intermediate_ftol = None`:

| case | evaluations | wall clock | largest shift | QPA |
|---|---|---|---|---|
| nac | 47 → 39 (1.21×) | 0.38 → 0.34–0.35 s | not measured | single phase |
| cpd-1a | 408 → 270 (1.51×) | 2.02–2.04 → 1.52 s | 0.027 esd, a width term | within 0.0014 wt % |
| cpd-2 | 533 → 329 (1.62×) | 3.37–3.43 → 2.27–2.28 s | 0.001 esd, a background coefficient | within 0.0003 wt % |
| trigger | 360 → 232 (1.55×) | 8.63–8.65 → 5.67–5.70 s | 0.001 esd, outside one degeneracy | within 0.0001 wt % |

Rwp agrees to five decimals or better in every case.

The degeneracy is the trigger case's instrument `x` against every phase's
`lor_size`, which moves 1.4 esd. Those parameters are exactly degenerate
(Lorentzian FWHMs add, and both terms are size-like in θ), and the measurement
shows it: `x` gained 0.0013165 while all four `lor_size` values lost
0.0012897–0.0013300 each. What moved is the split, not the width they sum to.

A chained series is the case to measure rather than assume. Ten warm-started
patterns took 1603 evaluations against 1792 fully converged (57.2–57.6 s against
60.4–60.7 s), but the same comparison one commit earlier went the other way,
1705 against 1634. Each pattern starts from its
predecessor's answer, and a small change in one seed changes how many recovery
rungs the next pattern needs, so the chain turns a bounded per-fit difference
into an unbounded one whose sign is not fixed. A single cold fit has no such
amplifier: that one was faster in both trees.

### Converging every stage

Set `intermediate_ftol` to `None`:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.intermediate_ftol = None
assert plan.stage_ftols() == [None] * len(plan.stages)
```

Every stage then stops where the solver's own default says, which is what every
fit before 1.1 did, to the bit. Reach for it when a number is going into a
paper and you want the plan's own converged answer rather than one within a few
hundredths of an esd of it, when you are reproducing a number from an earlier
release, and in a test that pins a value: a suite whose numbers move when a
default moves is not pinning anything.

`PlanSpec.intermediate_ftol` carries the setting through JSON, so a project
file, a history header and an agent request all record which schedule ran. In
the GUI's text document it is the `tolerance` line, whose value is a number or
the word `none`.

## What a stage carries

A `Stage` is `Stage.name`, a list of globs in `Stage.turn_on`, and seven
numbers that decide how that stage is solved. `Stage.name` is a label, carried
through to `StageResult.name` and to the event stream; `Stage.turn_on` is what
the stage frees, matched with `fnmatch` against the dot-paths of [](model.md).

[](concepts.md) covers `Stage.restraint_weight_scale`, the restraint schedule,
in full; the other six are here.

```python
import rietx as rx

stage = rx.Stage("widths", ["instrument.profile.*"], max_iter=200)
assert stage.max_iter == 200
assert stage.seed == 0.0 and stage.strain_seed == 0.0
assert stage.lebail_cycles == 3
```

`Stage.max_iter` caps the least-squares iterations for that stage. A stage that
reaches it is reported with status `max_iter` rather than `converged`, which is
a result to read rather than an error to catch.

`Stage.ftol` is this stage's own termination tolerance (the relative cost
decrease below which the solver stops), and it overrides the plan's schedule
above. Unset (`None`), the stage takes whatever `RefinementPlan.stage_ftols`
gives it. Set it to say that one stage is different: an early stage whose seed
the next one is unusually sensitive to, or a single-stage fit that has to
converge as hard as an endpoint.

`Stage.seed` and `Stage.strain_seed` both exist to lift a parameter off an
exact zero that the solver cannot move away from, and they are not
interchangeable, because the two pathologies are opposite.

- `Stage.seed` lifts any **softplus-bounded** parameter the stage frees to the
  given value. The softplus map's slope at zero is itself near zero, so a
  coefficient starting at exactly zero has no gradient and never moves. The
  extinction and surface-roughness stages use it.
- `Stage.strain_seed` puts a freed but all-zero Stephens block on a small
  microstrain, in ppm of ΔM/M. Those coefficients are identity-transformed, so
  `Stage.seed` cannot reach them, and their problem at zero is the *exploding*
  gradient of a square root rather than a dead one.

Both default to `0.0`, meaning no seed.

`Stage.lebail_cycles` is the number of intensity-partitioning refreshes the
stage performs, and it applies in Le Bail mode only.

`Stage.window_slack_deg` (and its mirror `StageSpec.window_slack_deg`) is the
absolute capture slack, in °2θ, added to every evaluation-window half-width
the stage compiles. The default (`None`) uses the package constant, sized for a
fit whose starting positions are roughly right. A fit that must *measure* a
hypothesis it is forbidden to walk toward declares the wider capture range its
verdict needs instead of borrowing tail margin: the indexing Le Bail validation
holds its candidate cell fixed, and a wrong candidate displaces peaks by whole
degrees. Leave it unset in ordinary plans.

## Persisting a plan

`RefinementPlan` and `Stage` are plain dataclasses, which is what makes them
pleasant to edit and useless to store. `PlanSpec` and `StageSpec` are their
serializable mirrors, and the conversions are explicit in both directions:

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_default()

spec = rx.PlanSpec.from_plan(plan)
restored = spec.to_plan()

assert [s.name for s in restored.stages] == [s.name for s in plan.stages]
assert spec.correlation_guard == plan.correlation_guard
```

`PlanSpec.from_plan` and `PlanSpec.to_plan` are the two directions.
`PlanSpec.stages` is a list of `StageSpec`, with `StageSpec.from_stage` and
`StageSpec.to_stage` doing the same job one level down.

You do not have to call them at a boundary. Anything that takes a `PlanSpec`
also takes a `RefinementPlan`, and anything that takes a `RefinementPlan` also
takes a `PlanSpec`: a preset goes straight into an agent request, and a plan
read back off a project or a history header goes straight into `fit`:

```python
import rietx as rx

plan = rx.PLAN_PRESETS["mccusker_default"]()

assert rx.PlanSpec.model_validate(plan) == rx.PlanSpec.from_plan(plan)
```

The conversion happens in the two places that own the mirror, so no call site
carries a copy of it. Write it out yourself when you want the JSON: the
dataclasses have no `model_dump`, and asking one for it says which mirror
to use. A `StageSpec` mirrors `Stage` field for field (`StageSpec.name`,
`StageSpec.turn_on`, `StageSpec.max_iter`, `StageSpec.ftol`,
`StageSpec.lebail_cycles`, `StageSpec.seed`, `StageSpec.strain_seed`,
`StageSpec.restraint_weight_scale` and `StageSpec.window_slack_deg`), and
`PlanSpec.correlation_guard` mirrors the plan's.

What is stored is the **expanded** plan: every stage in full, because that is
what will run. There is deliberately no field recording which preset it came
from, since such a field could disagree with the stages beside it.

`PlanSpec.preset_name` is therefore a method rather than a field, and it
answers the question by comparison: the registered preset this plan *equals*,
or `None` if it was edited:

```python
import rietx as rx

spec = rx.PlanSpec.from_plan(rx.RefinementPlan.mccusker_default())
assert spec.preset_name() == "mccusker_default"

spec.stages.pop()
assert spec.preset_name() is None
```

That is what lets a plan editor label a menu, and the text document print
`plan mccusker_default` instead of eight stage lines, without either of them
trusting a stored label.

This is the form a plan takes in a history tree and in a `.rex` project, so the
round trip is what makes a stored plan a record of what was actually done.

## Running one stage at a time

`Refinement.fit` runs a whole plan. `Refinement.run_stage` runs exactly one
stage against the current model and stops:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument)
ref.run_stage(data, rx.Stage("scale_bkg", ["phases.*.scale"]))
ref.run_stage(data, rx.Stage("cell", ["phases.*.cell.*"]))
```

Each call refines, commits a history node and leaves the model at the values it
reached, so the next call starts from there. This is the same sequence a plan
performs; running it by hand is how a caller interleaves its own decisions
between stages. `Refinement.suggest` is built for exactly that moment, and
[](history.md) is how to go back a stage when the decision was wrong.

`run_stage` takes its own `correlation_guard` rather than reading one from a
plan, because there is no plan involved.

`Refinement.snapshot` returns a `RefinementState`: the full state needed to
reconstruct the refinement exactly, taken without refining anything.
`Refinement.stage_reports_` holds the per-stage reports from the last `fit`,
when it was asked for them. Each is a `StageReport`, which carries its own
statistics rather than a `Statistics` object:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
ref.fit(data, stage_reports=True)
for rung in ref.stage_reports_:
    print(rung.stage, rung.rwp, rung.gof)
```

That is off by default. Ask for it deliberately: a converged run's final report
is routinely its least informative, because a plan absorbs an error it cannot
free into whatever it can. [](report.md) has the argument and
what to read in a trajectory.

## What each stage reports

`RefinementResult.stages` is a list of `StageResult`, one per stage, in the
order they ran. It is the cheapest honest account of what a fit did:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
for stage in result.stages:
    print(stage.name, stage.status, stage.n_iterations,
          stage.cost_initial, stage.cost_final)
```

| Field | Holds |
|---|---|
| `StageResult.name` | the stage's name, as the plan gave it |
| `StageResult.status` | `converged`, `max_iter` or `diverged` |
| `StageResult.n_iterations` | least-squares iterations taken |
| `StageResult.cost_initial` | the cost the stage started from |
| `StageResult.cost_final` | the cost it reached |
| `StageResult.freed` | the paths this stage actually freed, after globbing |
| `StageResult.ftol` | the tolerance it was solved at; `None` = the solver default |
| `StageResult.n_constraint_truncations` | steps the bounded-LM driver shortened to stay inside a linear-inequality constraint |
| `StageResult.n_degenerate_cell_probes` | trial cells this stage's residual refused as degenerate (zero or negative volume) rather than warning about and returning NaN |
| `StageResult.held` | paths the plan freed that this stage held anyway, because the data could not see their phase |
| `StageResult.released` | the ones it held at the start and let go again, having seen the phase appear while it solved |

`StageResult.freed` is the field to read when a stage did nothing: a glob that
matches no path is not an error, so an empty list means the stage was a no-op
and the run continued past it in silence.

`StageResult.held` is the field to read when a *parameter* did nothing. A phase
reaches the pattern only through `scale × |F|² × profile`, so a phase whose
scale sits at its floor has no measurable structural parameter at all: freeing
its cell asks the solver to search a direction that does not change the
calculated pattern. Where that is the case at stage start, the stage holds
those parameters and refines the rest; the phase's own `scale` is never held,
which is how the phase can still appear. The values come back as the ones you
handed in rather than as a walk, `PHASE_UNCONSTRAINED` names the phase and the
stages that held it, and the parameters are absent from
`RefinementResult.parameters` because nothing measured them.

A hold is decided per stage, at the values that stage starts from, so a phase
that appears later refines normally from the stage where it appears. If it
appears *while* a stage solves, that stage lifts the hold and solves a second
time — once, never a third — and lists those paths in `StageResult.released`
instead. Both solves are counted in `n_iterations`; `cost_initial` is still the
cost the stage started at.

Both lists are empty for every fit whose phases are all visible, which is every
fit that is working.

A cost that rises from `StageResult.cost_initial` to `StageResult.cost_final`
is a diverged stage, and `StageResult.status` says so.

`StageResult.n_constraint_truncations` is `0` under the default `trf` solver,
which has no linear-inequality vocabulary at all. It counts only under
`solver="lm"`, and today the only such constraint is the Stephens strain cone.

`StageResult.n_degenerate_cell_probes` counts trials, never the answer: `Cell`
declares no bounds of its own, so an underdetermined cell stage can reach a
zero- or negative-volume metric while searching, and each such reach is pushed
back out and counted rather than crashing the stage or returning a silent
NaN. Nonzero is the ordinary outcome on a poorly-constrained cell, not a sign
that anything reported is wrong; the fit-level `CELL_DEGENERATE_PROBE`
diagnostic sums this across every stage that ran.

## Guards

A guard is a measurement taken after a stage converges. It never changes the
fit; it reports something about the fit that the fit statistics cannot show.

Every hit is a `GuardFinding`, which carries the finding as data rather than as
a sentence:

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

`GuardFinding.code`, `GuardFinding.paths`, `GuardFinding.value` and
`GuardFinding.message` are the four fields. A client reads `paths` to offer a
link and `value` to sort; nothing has to take a string apart. `str(finding)` is
`GuardFinding.message`.

There is one constructor per kind of finding, so each format string is written
once:

| Constructor | Fires when |
|---|---|
| `GuardFinding.correlation` | two free parameters correlate above the plan's `correlation_guard` |
| `GuardFinding.at_bound` | a parameter stopped against a bound |
| `GuardFinding.background_absorption` | the background could largely reproduce a structural parameter's column |
| `GuardFinding.roughness_absorption` | the roughness correction could |
| `GuardFinding.nonpositive_adp` | an anisotropic displacement tensor is not positive definite |
| `GuardFinding.nonpositive_strain` | a Stephens block gives a negative σ²(M) for some reflection |
| `GuardFinding.narrow_background_peak` | a declared background peak has narrowed towards the instrumental resolution, where it is a reflection rather than a background feature |

`GuardFinding.value` is the headline number for the kind: the correlation
coefficient, the block R², the minimum eigenvalue, the worst σ²(M). It is
`None` for `GuardFinding.at_bound`, which has no number to report.

`code` is an open vocabulary of strings and deliberately not a closed type: it
is the same vocabulary as `Diagnostic.code`, so the mapping from a guard to the
diagnostic a caller reads is data rather than a hand-written branch per kind.
[](results.md) reads diagnostics.

Read a guard as evidence about what the data could support, not as a verdict on
the model. A `nonpositive_strain` finding means those coefficients are not
quotable; it is not a measurement of anisotropy.

## Watching a run

`events` streams per-iteration telemetry out of a running fit. It accepts a
path, in which case each event is appended to that file as JSONL:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
result = ref.fit(data, events="run/events.jsonl")
```

or a callable, called with each event as a plain dict:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
def show(event):
    print(event["kind"], event["data"])

result = ref.fit(data, events=show)
```

Each event carries its kind, a Unix timestamp, and an open `data` dictionary.
The kinds are a closed set: `fit_start` and `fit_end` for the run,
`stage_start` and `stage_end` for each stage, and `eval` for each residual
evaluation. `rietx watch` renders a log as a live console.

Two rules matter to anyone consuming the stream. Read `data` with `.get` rather
than by unpacking a fixed shape, because fields are added to a kind without a
version bump. And a cancelled run's `fit_end` omits the statistics entirely,
because there is no fitted result to report.

`Capabilities.event_schema_version` reports the version a build emits;
[](compatibility.md) says what that version promises.

## Stopping a run

`cancel` takes a `CancelToken`, which another thread sets:

```python
import rietx as rx

token = rx.CancelToken()
assert not token.is_set()
token.cancel()
assert token.is_set()
token.reset()
```

Cancellation is cooperative. The token is read between residual evaluations,
never as an interrupt, which is what keeps the frozen-per-stage state of a
compiled model intact.

The stage in flight is **abandoned**: no history node, no commit, and the
models restored to the values they held before that stage began. That is not
tidiness: a seeding stage writes to the models before it solves, so leaving them
alone would leave a half-seeded model behind.

`RefinementCancelled` is then raised, carrying what did complete:

<!-- api-doc: no-exec — it needs a run cancelled from another thread -->
```python
try:
    ref.fit(data, cancel=token)
except rx.RefinementCancelled as cancelled:
    print(cancelled.stage)             # the abandoned stage's name
    print(cancelled.completed_stages)  # list[StageResult] for those that finished
    print(cancelled.node_id)           # the node the working state stands at
```

`RefinementCancelled.stage` is the abandoned one. `RefinementCancelled.completed_stages`
is empty when the first stage was cancelled. `RefinementCancelled.node_id` is
`None` with history disabled, or when nothing completed.

A cancelled run is therefore not a lost run: the working state is a real,
restorable node ([](history.md)), and the stages before it are reported in
full.

## What the result records about the run

`RefinementResult.provenance` is a `Provenance`, and it holds everything needed
to reproduce the result:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
p = result.provenance
print(p.package_version, p.backend, p.solver, p.dtype)
```

| Field | Holds |
|---|---|
| `Provenance.package_version` | the version of rietx that produced it |
| `Provenance.schema_version` | the data-contract version of the objects |
| `Provenance.backend` | the backend the arrays were computed on |
| `Provenance.dtype` | the precision they were computed in |
| `Provenance.solver` | the least-squares driver used |
| `Provenance.report_thresholds_version` | the thresholds any report was judged against |
| `Provenance.created_utc` | when the result was assembled, UTC |
| `Provenance.notes` | free-form string pairs a caller can add |

Read `Provenance.backend`, `Provenance.dtype` and `Provenance.solver` back
rather than assuming them. A result is only as reproducible as its record of how
it was computed, and that record is the only place the answer survives once the
calling code has moved on.

The four version fields are the same contracts `capabilities()` reports.
[](compatibility.md) says what a change to one means.
