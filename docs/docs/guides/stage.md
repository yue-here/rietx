(guide-stage)=
# How to run a plan one stage at a time

Call `Refinement.run_stage` with one `Stage` at a time, and look at each result before you choose the next stage.

Each call refines the stage's parameters, records a history node and leaves the model at the values it reached.
The next call starts from there, as the next stage of a plan would.

## Run the stages

This runs three stages by hand on the GSAS-II tutorial fluorapatite pattern that ships with rietx:

```{literalinclude} ../../../examples/guides/stage.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/stage.py -->
```text
scale_bkg  converged  Rwp 0.6050
cell       converged  Rwp 0.4919
profile    converged  Rwp 0.0970
```

Each call returns a full `RefinementResult` for the stage it ran, with the statistics, the parameters and their esds, and the diagnostics.
Parameters freed in an earlier call stay free, so the `profile` stage refines the scale, background, zero shift and lattice parameters too.

`run_stage` takes `two_theta_limits`, `mode`, `events`, `cancel` and `label` as `fit` does.
It also takes its own `correlation_guard`, the correlation above which the fit reports a pair of parameters (0.98 by default), and its own `phase_support_sigma`, the number of esds a phase's scale must sit from zero for the stage to treat the phase as seen (3 by default, `None` for no significance hold; a phase with no line in range is still held), because no plan supplies them.

## Decide between stages

The pause between two calls is where you choose what comes next.
Read the last result, or call `Refinement.suggest` with the same pattern for a ranked list of the parameters the data would most reward freeing.
If a stage made things worse, `Refinement.checkout` returns the model to an earlier history node, and the next `run_stage` starts from there.

## Compare with the preset

The `profile` stage above frees all five width terms together.
`mccusker_default` frees `w` alone first and then `u`, `v`, `x` and `y`, and on this pattern it ends lower.
To see where the preset pulls ahead, ask it for a report at each stage:

```{literalinclude} ../../../examples/guides/stage.py
:language: python
:start-after: "# guide: reports start"
:end-before: "# guide: reports end"
```

<!-- output of examples/guides/stage.py -->
```text
scale_bkg  Rwp 0.6050
zero       Rwp 0.4921
cell       Rwp 0.4920
profile_w  Rwp 0.1932
profile    Rwp 0.0988
closing    Rwp 0.0945
```

The preset's `profile` stage reaches Rwp 0.0988.
The preset then runs its closing stage, which refines the same parameters with wider peak windows and ends at 0.0945 ([The closing stage](../reference/refinement.md#the-closing-stage)).
`run_stage` runs no closing stage, so by default it runs at the closing stage's wider windows.
The hand-run `profile` stage therefore refines the same parameters at the same windows as the closing stage, and ends at 0.0970.
The difference comes from where each stage fixed its peak windows.
A stage fixes them at the values it starts from.
The hand-run stage fixed them at the default widths, and its result carries `FROZEN_COMPILE_STALE`.
The closing stage fixed them at the widths the preset's `profile` stage had fitted.
One more hand-run stage that frees nothing new starts from the fitted widths too, and it ends at 0.0945.
The full script is `examples/guides/stage.py`.

## Read a report at every stage

`fit(..., stage_reports=True)` stores a `StageReport` for each stage in `Refinement.stage_reports_`.
Each holds the stage's name, its Rwp and goodness of fit, and the report's summary and suggested actions at that point.
It is off by default, and asking for it leaves every fitted value unchanged.

Ask for it when a fit ends badly.
A plan's last stage often shows the least, because by then the free parameters have absorbed an error the plan could not fix.
An earlier stage, where the error was still visible, often names its cause.

## See also

- [How to add a stage to a refinement plan](plan.md) builds the stages you would pass here.
- [About a fit](../concepts/fit.md) follows one stage from freeing its parameters to recording its history node.
