# Stage tolerances

This page gives the termination tolerance each stage of a plan runs at, the three rules that choose it, what the looser schedule costs, and how to make every stage converge.
It belongs with [The refinement](refinement.md), which gives the plan and stage objects and the `StageResult` these rules write into.

## Tolerance by stage

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
2. The last declared stage runs at the solver's default of 1e-9, shown as `None`, because it produces the answer. A closing stage after it runs at 1e-9 too.
3. Every other stage runs at `RefinementPlan.intermediate_ftol`.

A one-stage plan is therefore all last stage, and nothing is loosened.
`StageResult.ftol` records the tolerance each stage ran at, so a result says which schedule produced it.
`PlanSpec.intermediate_ftol` carries the setting into a project file and a history header, and the GUI's text document writes it as the `tolerance` line ([The GUI as a text document and a wire](gui-power.md)).

## Cost of the loose schedule

Each stage frees its parameters on top of everything already free.
A parameter an early stage left short of convergence keeps refining in every later stage, and the last stage converges all of them together at 1e-9.
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

## Converging every stage

Set `intermediate_ftol` to `None`:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.intermediate_ftol = None
assert plan.stage_ftols() == [None] * len(plan.run_stages())
```

Every stage then stops at the solver's default, as every fit before 1.1 did, to the bit.
Use it for a number going into a paper, for a number reproduced from an earlier release, and in a test that pins a value.
