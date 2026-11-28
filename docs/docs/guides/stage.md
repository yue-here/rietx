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
cell       converged  Rwp 0.4920
profile    converged  Rwp 0.0940
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
scale_bkg  Rwp 0.6063
zero       Rwp 0.4926
cell       Rwp 0.4923
profile_w  Rwp 0.1944
profile    Rwp 0.0939
```

The preset's `profile` stage reaches Rwp 0.0939, and the hand-run `profile` stage 0.0940.
The preset ends there, because a plan runs a closing stage only when it asks for one ([The closing stage](../reference/refinement.md#the-closing-stage)).
The preset's earlier stages read a little higher than the hand-run ones.
A stage that a later stage refits computes each peak over a narrower window, and a stage's Rwp is measured on its own windows.
A stage fixes its peak windows at the values it starts from.
Both `profile` stages started from narrower peaks than they ended with, so the peaks outgrew their windows.
The hand-run stage's windows dropped 4.4 % of the intensity at its first answer, and the preset's 3.4 %.
Each stage then solved once more on windows sized at its answer, and `StageResult.window_refit_loss` records the first figure.
One more hand-run stage that frees nothing new ends at 0.0940 too.
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
