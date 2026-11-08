# Restart ladder and quarantine

This page says when a series refits a pattern with a different start, which attempt it keeps, and what it does with a pattern no attempt could fit.
It belongs with [Sequential refinement](series.md), which gives the calls and the `SeriesResult` these rules write into.

## Restart ladder

A rejected warm fit escalates one attempt at a time: the collapsed warm refit, then the full staged plan from the warm state, then the full staged plan from the starting models.
Under `refit="stages"` the first attempt already is the staged warm fit, so the ladder has two attempts, `"warm_staged"` and `"cold"`, and `"warm"` never appears.
Each attempt runs only when the trigger still fires on the best attempt so far, and the entry keeps the best.
Best is an accepted attempt over a rejected one, then one that finished over one the bound cut, then the lower least-squares cost.
`SeriesEntry.rungs_tried` names the attempts, and `SeriesEntry.n_iterations` sums those that returned a fit.
The middle attempt matters most, because throwing a warm start away roughly triples the work.

What triggers the ladder is a warm attempt that raised or was rejected: it diverged, or carries an `error` diagnostic such as `MODEL_FAR_FROM_DATA`.
A `max_iter` attempt is not rejected.
Each trigger is a property of this pattern's own fit, readable once it finishes, that a different start could fix.
An Rwp comparison is not a default trigger.
`reseed_factor` sets one if you want it: a warm attempt above that multiple of the median Rwp of the accepted patterns climbs the ladder.
The 1.25 fence that was the default before 1.11 escalated 116 patterns across eight measured series and moved no value by more than 7.2e-4 of its esd.
On a series where an unmodelled phase appears part-way, it refitted every later pattern for 4.1 times the evaluations.
A guard finding such as `HIGH_CORRELATION` is neither, since it fires on converged patterns and no attempt changes the model or data behind it.

One more trigger reaches the middle attempt only: the GoF step.
A collapsed warm fit can converge with no `error` code and still stop in a wrong minimum.
On a two-phase synthetic chain it kept the minor phase's c axis 0.34 Å off, at a GoF of 2.05 where the pattern it started from reached 1.02, while the staged plan from the same start found the truth.
So a first attempt whose GoF is more than 1.25 times the GoF of the pattern its warm start came from climbs to `"warm_staged"`, and the better of the two fits is kept.
`SeriesEntry.warm_gof_over_seed` records that ratio on every warm pattern, and `SeriesEntry.escalated_on_gof` says when the step alone sent a pattern up.
The step never sends a pattern to the cold attempt and never quarantines one, so it never sets `reseeded` and the chain stays unbroken there.
It compares GoF, which divides the misfit by the pattern's own noise, and not Rwp, which moves with the counts.
GoF moves with the counts too once a systematic misfit dominates, so a pattern counted much longer than its seed can climb with no wrong minimum, at the cost of one fit.
It compares against the seed and not a median of the accepted patterns, because on a series where an unmodelled phase appears part-way a median of GoFs fired on 115 of 247 patterns, and the seed on one.
Over the 537 warm fits of nine measured series it fired 3 times, and the largest ratio kept without need was 1.126.
`reseed=False` turns it off with the rest of the ladder, and under `refit="stages"` it has nothing to climb to.

The first attempt is unbounded unless you pass `first_rung_factor`.
Each stage of it, the closing one included, may then spend that multiple of the dearest stage of the first attempts this chain has converged, once three have.
An attempt with any stage stopped there escalates, even if its closing stage converged.
The bound does nothing under `refit="stages"` or `reseed=False`.
It is not the default because it can move an answer: at 3.0 on the planted ramp it cut a winning first attempt, 9.8 times the dearest before it, moving a zero shift 6.06 esd, to save 49 evaluations of 13 083.

An attempt whose fit raises has lost in the same sense as a diverged one, and the ladder escalates past it the same way.
`SeriesEntry.rungs_raised` records what each such attempt raised, and `SeriesEntry.rwp_warm` is `None` when the warm attempt was one of them.
The case that needs this is a neighbour that converged with a cell far outside the physical range.
Every warm attempt inherits that cell, and the reflection enumerator refuses it before the fit starts, while the cold attempt starts from the starting models.

A pattern on which every attempt raised has no entry.
It is recorded in `SeriesResult.failures` with a [`SERIES_PATTERN_FAILED`](diagnostics-series.md#series_pattern_failed) warning, and the `on_error` policy decides what the chain does next.
Each `SeriesFailure` carries the pattern's `SeriesFailure.index` and `SeriesFailure.label`, and `SeriesFailure.exception` is the last attempt's exception as `repr`.
`SeriesResult.n_failed` counts them, and `SequentialRefinement.failures_` is the same list on the runner, where to read it after catching the exception `on_error="raise"` lets through.
Under the default, `"carry"`, the successor warm-starts from the last accepted pattern, because what failed was this pattern and not the state its neighbour handed it.
A chain that fitted no pattern at all still raises, whatever the policy.
Your own `prepare` and `constrain` are never guarded: a raise there ends the series.

## Quarantine

A fit still rejected after the last attempt is quarantined, and [`SEQUENTIAL_UNRECOVERED`](diagnostics-series.md#sequential_unrecovered) names it and its `error` code.
Its successor warm-starts from the last accepted pattern, and the accepted median never sees the failure.
Otherwise one failure would seed its neighbour with a bad start and drag the median that `rwp_over_median` and your `reseed_factor` read.

A pattern that converged at a high Rwp with no `error` code is not quarantined, and nothing calls it an outlier.
`SeriesEntry.rwp_over_median` records how far its Rwp sits above the median of the patterns accepted before it, and it seeds its successor and joins the median like any accepted pattern.
Rwp cannot say why it rose.
Near a converged fit Rwp is GoF times R<sub>exp</sub>, and three measured causes divide between the two factors:

- A blank frame has a GoF like its neighbours' (1.00 against 1.06) and an R<sub>exp</sub> four times theirs (0.159 against 0.040), because it is background and noise, fitted perfectly.
- A correct model over counts that fell 4× also keeps its GoF and doubles its R<sub>exp</sub>. It is a sound measurement.
- An unmodelled phase raises the GoF: 16.7 against 1.04.

So compare a high ratio's GoF and R<sub>exp</sub> with an accepted neighbour's before reading its values.
The first patterns walked are compared against a median of only one or two values.

Quarantined, a lasting change could never become the chain's new normal.
On a 24-pattern ramp whose counts fell from pattern 6, quarantining the patterns over a 1.25× fence made every later pattern climb the ladder, with 55 % more iterations.
With an unmodelled phase from pattern 6 the extra was 107 %.
On the blank frame, quarantine saved 2-8 % of the chain, and the values were identical either way.
