(guide-next)=
# How to choose the next parameter to free

Call `Refinement.suggest` after a stage, free its top group if the group is resolved, its `delta_bic` is positive and the parameter is not on a bound, then measure the move with `rietx.report.compare_freed` against a re-solved copy of the fit.

`suggest` changes nothing.
It scores copies of the model and records no history node.

## Ask after a stage

This runs two stages by hand on the GSAS-II tutorial fluorapatite pattern that ships with rietx, then asks which held parameter to free:

```{literalinclude} ../../../examples/guides/next.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/next.py -->
```text
noise floor 693 | best: None
instrument.profile.x, phases.0.lor_size       gain   322283  dBIC   +795  resolved False
instrument.profile.y, phases.0.lor_strain     gain   189147  dBIC   +333  resolved False
instrument.profile.w                          gain   156429  dBIC   +264  resolved True
phases.0.gauss_size, instrument.profile.v     gain   129119  dBIC   +201  resolved False
instrument.profile.u, phases.0.gauss_strain   gain    39436  dBIC    +45  resolved False
```

Each group's `gain` is the fall in χ² that freeing the group would give, predicted from the derivatives at the current values.
Read each group in this order:

1. `gain` against `noise_floor`.
   Only groups above the floor are listed.
   The floor is {{ SUGGEST_MIN_GAIN }} times χ²/ν, or {{ SUGGEST_MIN_GAIN }} when χ²/ν is below 1: the 3σ point for one parameter.
2. `resolved`.
   A group of two holds parameters whose effects on the pattern the data cannot tell apart.
   Here each instrument width pairs with the sample width of the same shape, Lorentzian with Lorentzian and Gaussian with Gaussian.
   `best_or_none()` returns `None` when the top group is such a tie.
3. `delta_bic`, the change in the Bayesian information criterion.
   It weighs the gain against one more parameter at this pattern's effective number of observations, and a positive value favours freeing.
   The [theory chapter](../theory/estimation.md#which-parameter-to-free-next) derives it.

The data cannot settle a tie, so settle it by protocol.
Without a calibration on a standard, the widths belong to the instrument.
With an instrument profile loaded from a standard, free the sample's widths instead.

## Free the group and ask again

This frees the instrument widths and asks again:

```{literalinclude} ../../../examples/guides/next.py
:language: python
:start-after: "# guide: profile start"
:end-before: "# guide: profile end"
```

<!-- output of examples/guides/next.py -->
```text
instrument.source.lines.1.weight    gain  474  dBIC +21.0
phases.0.atoms.2.occ                gain  218  dBIC  +5.8
phases.0.atoms.6.occ                gain  201  dBIC  +4.8
```

The gain says how far a parameter can move χ², and nothing about whether it should move.
Toby makes the same point about ranking by derivatives, with an example where the largest derivative is an instrument width and the broadening belongs to the sample {cite}`toby2024`.
`instrument.source.lines.1.weight` is the intensity of the Cu Kα2 line relative to Kα1, held at 0.5.
The two occupancies are of sites that are full in fluorapatite.

## Narrow the question

`include` and `exclude` take dot-path patterns, so `suggest` scores only the parameters you would consider freeing:

```{literalinclude} ../../../examples/guides/next.py
:language: python
:start-after: "# guide: narrow start"
:end-before: "# guide: narrow end"
```

<!-- output of examples/guides/next.py -->
```text
free phases.0.extinction next: predicted Δχ² 96.1, ΔBIC -1.3; ΔBIC refuses it — the predicted gain does not pay for 1 parameter(s) at N_eff=1001 (5751 rows over the squared esd inflation) (24 candidate(s) evaluated, 4 non-separable from the free set, 0 without leverage; noise floor 26.98)
```

Extinction clears the noise floor, and ΔBIC refuses it.
`best_or_none()` still returns it, because it checks the floor and the tie and does not check ΔBIC.
Read `delta_bic` before you free what `best_or_none()` names.

A positive `delta_bic` is not enough either.
Asked again on the re-solved fit of the next section, the same query gives extinction a ΔBIC of +0.4.
Extinction sits on its lower bound of 0, and the data push it below 0, so freeing it moves nothing.
`suggest` predicts each gain as if the parameter could move both ways.
Before you free a candidate, check that it is not on a bound, or measure it as the next section does.

The four non-separable candidates are the sample widths, which the free instrument widths already cover.

## Measure the move

Measure on two branches of one history node: one solves again with nothing new free, and the other also frees the candidate.
First, the re-solve:

```{literalinclude} ../../../examples/guides/next.py
:language: python
:start-after: "# guide: again start"
:end-before: "# guide: again end"
```

<!-- output of examples/guides/next.py -->
```text
Rwp before 0.0970, after re-solving 0.0945
```

A stage that frees nothing new still moves the fit here.
Each stage fixes its peak windows at the values it starts from, and the `profile` stage started from much wider peaks than it ended with.
Giving that stage wider windows (`Stage.window_slack_deg=1.0`) ends it at Rwp 0.0952 instead.

Then free the Kα2 weight on a branch of the re-solved fit, and compare:

```{literalinclude} ../../../examples/guides/next.py
:language: python
:start-after: "# guide: compare start"
:end-before: "# guide: compare end"
```

<!-- output of examples/guides/next.py -->
```text
instrument.source.lines.1.weight: 0.5 -> 0.465(6), t = -5.8
dBIC +29.2 at N_eff 1269 (raw N: +156)
```

`t_ratio` is how far the parameter moved from where it was held, in its own esds.
`delta_bic` is the measured counterpart of the prediction, positive here.
The raw-N figure counts every channel as an independent observation and overstates the evidence, because neighbouring residuals in a powder pattern are correlated.

Whether to keep the parameter is still your decision.
The data ask for a Kα2 line 7 % weaker than the nominal half.
A line weight can also absorb a peak asymmetry the model lacks, and the two axial-divergence parameters were among the candidates `suggest` could not separate from the free set.

```{warning}
Compare against the re-solved branch, never against the fit as the stage left it.
Freed on a branch of the fit before the re-solve, extinction stayed on its floor at 0 and still scored ΔBIC +46, all of it the re-solve's gain.
On a branch of the re-solved fit it scored −7.
```

The full script is `examples/guides/next.py`.

## The same answer elsewhere

`Refinement.summary()` prints the top group on its `next:` line, with its predicted ΔBIC.
Pass `report=ref.report()` to `suggest` to mark each candidate with the Layer 2 action that names the same parameters, in `ParameterCandidate.action_kind`.
Layer 2 reads the shape of the residual, so the two agreeing is stronger evidence than either alone.

## See also

- [How to run a plan one stage at a time](stage.md) runs the stages this guide pauses between.
- [How to keep a parameter fixed whatever the plan frees](hold.md) keeps a refused candidate out of later stages.
- [About the report](../concepts/report.md) describes the three layers.
