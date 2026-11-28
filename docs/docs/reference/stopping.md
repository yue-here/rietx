# Stage tolerances

This page gives when each stage of a plan stops: the tolerance on the fall in cost, and the shift test that ends the last stage.

`RefinementPlan.stage_ftols` gives the termination tolerance each stage runs at.
The tolerance is the relative decrease in cost below which the solver stops.

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
assert plan.intermediate_ftol == 1e-6

ftols = plan.stage_ftols()
assert len(ftols) == len(plan.run_stages())
assert set(ftols[:-1]) == {1e-6} and ftols[-1] is None
```

The list is parallel to `RefinementPlan.run_stages`: the declared stages, then the closing stage when the plan asks for one ([The closing stage](refinement.md#the-closing-stage)).
Three rules decide a stage's tolerance, in this order.

1. A stage that declares `Stage.ftol` runs at it.
2. The last declared stage runs at the solver's default of 1e-9, shown as `None`, because it produces the answer. A closing stage after it runs at 1e-9 too. Both also stop on the shift test, usually first ([The shift test](#the-shift-test)).
3. Every other stage runs at `RefinementPlan.intermediate_ftol`.

A one-stage plan is therefore all last stage, and nothing is loosened.
`StageResult.ftol` records the tolerance each stage ran at, so a result says which schedule produced it.
`PlanSpec.intermediate_ftol` carries the setting into a project file and a history header, and the GUI's text document writes it as the `tolerance` line ([The GUI as a text document and a wire](gui-power.md)).

## Cost of the loose schedule

Each stage frees its parameters on top of everything already free.
A parameter an early stage left short of convergence keeps refining in every later stage, and the last stage converges all of them together.
So stopping the earlier stages sooner moves the answer little, on any plan.

Measured on five single fits from the acceptance suites against the same plans with `intermediate_ftol=None`, the closing stage in both, three interleaved rounds each, on macOS arm64 with the `[dev]` install, 2026-11-02:

| Fit | Evaluations | Wall clock in s | Largest shift |
|---|---|---|---|
| fluorapatite | 52 → 49 (1.06×) | 1.34-1.62 → 1.30-1.35 | 0.000 esd |
| 11-BM NAC | 51 → 46 (1.11×) | 0.52-0.55 → 0.50-0.60 | 0.000 esd |
| cpd-1a | 277 → 175 (1.58×) | 2.18-2.28 → 1.89-1.97 | 0.0004 esd |
| SRM 660c LaB6 | 116 → 90 (1.29×) | 0.55-0.57 → 0.48-1.26 | 8.82 esd, between two minima |
| cpd-1a, absent zircon | 1221 → 311 (3.93×) | 21.5-22.4 → 9.6-11.0 | 0.0092 esd |

Rwp agreed to 1e-6 in every case.
LaB6's 1.26 s was the process's first fit.
The 8.82 esd is `Geometry.axial_sl` against `Geometry.axial_hl`.
The two ratios can trade places for an equally good fit, and each schedule lands in a different one.
The absent zircon phase has nothing to fit, and at 1e-9 two of its stages run to their limit of 400 evaluations.

A series is the case to measure rather than assume.
Each warm start begins from its predecessor's answer, so a small difference in one answer can change how many recovery rungs the next pattern needs.
The per-fit bound above therefore does not carry over to a chain, and the difference can go either way.
A chain on this schedule has not been measured.

## The shift test

The last declared stage, and the closing stage, stop as soon as the next undamped step would move no free parameter by `RefinementPlan.shift_over_esd_tol` of its esd.
The default 0.1 is the test McCusker et al. (1999, §7) give for a converged refinement, and the level above which checkCIF raises an alert.
`RefinementPlan.stage_shift_tols` gives the test each stage runs, parallel to `RefinementPlan.stage_ftols`:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
assert plan.shift_over_esd_tol == 0.1
shifts = plan.stage_shift_tols()
assert shifts[-1] == 0.1 and set(shifts[:-1]) == {None}
```

An intermediate stage, and a stage that declares its own `Stage.ftol`, run no shift test.
A stage the test ended reads `shift_over_esd` in `StageResult.termination`, and `StageResult.shift_over_esd_tol` records the value it ran.
The step is the undamped one because a damped step shrinks as the damping grows, so a slow solve would pass the test far from its minimum.
The esd the test divides by scales with χ²_red only up to 1, since far from the data χ²_red is the misfit and would widen every esd.
A fit at χ²_red above 1 therefore stops once every shift is under 0.1/√χ²_red of its reported esd, or on the 1e-9 stop.
[Convergence](../theory/convergence.md) gives the equation.

Measured against the same plans with `shift_over_esd_tol=None`, on macOS arm64 with the `[dev]` install, 2026-11-28:

| Fit | Evaluations | Largest departure from the 1e-9 answer |
|---|---|---|
| SRM 660c LaB6 | 71 → 67 | 0.003 esd |
| fluorapatite | 40 → 35 | 0.016 esd |
| 11-BM NAC | 49 → 44 | 0.004 esd |
| cpd-1a | 165 → 145 | 0.030 esd |
| CuCr₂O₄ ramp, 17 patterns | 1 326 → 848 | 0.68 esd, the cell of a 1 wt% phase |
| cpd-1 chain, 8 patterns | 504 → 453 | 0.13 esd, `instrument.geometry.axial_sl` |

Rwp agreed to 4e-6 on every single fit.
Every weight fraction stayed within 0.071 esd.
A series runs the test on every pattern.
Along both chains the departure did not grow from one pattern to the next, since each pattern is refitted to its own stop.

Three protocols keep the 1e-9 stop, because there an error in one answer carries into every later one.
`RefinementPlan.lab_calibrate` sets `shift_over_esd_tol` to `None`, since the instrument it calibrates is held through every later fit.
A series carrying Pawley intensities from pattern to pattern does the same.
So do the guides whose pages quote numbers.
To reproduce a number from before 1.13, set it to `None` too:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.shift_over_esd_tol = None
assert plan.stage_shift_tols() == [None] * len(plan.run_stages())
```

`Refinement.run_stage` takes the same keyword, 0.1 by default.
`PlanSpec.shift_over_esd_tol` carries the setting into a project file, and the GUI's text document writes it as the `shift` line when it is not 0.1.

## Converging every stage

Set `intermediate_ftol` to `None`:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.intermediate_ftol = None
assert plan.stage_ftols() == [None] * len(plan.run_stages())
```

Every stage then stops at the solver's default.
With `shift_over_esd_tol` set to `None` as well, a fit stops as every fit before 1.1 did, to the bit.
Use it for a number going into a paper, for a number reproduced from an earlier release, and in a test that pins a value.
