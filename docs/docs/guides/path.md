(guide-path)=
# How to check a series for path dependence

Fit the series with `direction="both"` and read `series.direction_gaps`, and pass `verify_steps=k` so that the k largest steps in `series.steps` are refitted from cold on their two patterns alone.

Each fit in a series starts from its neighbour's answer.
An error in one pattern can therefore pass to every pattern after it and still draw a smooth curve.
These two checks separate a trend in the data from one the chain made.

## Run the chain both ways

This fits the seven synthetic LaB6 patterns of [How to fit a temperature series](series.md) from 300 K up to 900 K and again from 900 K down:

```{literalinclude} ../../../examples/guides/path.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/path.py -->
```text
[]
91 gaps, the largest 0.00 esd
cell.a at p004: 4.16491 vs 4.16491 (warm/warm)
```

`series.backward` is the downward chain's own `SeriesResult`, and the entries of `series` are the upward one's.
`series.direction_gaps` lists every parameter's gap at every pattern, largest first.
Each row holds the two values, the gap in combined esds and the attempt each chain kept, here at 700 K.
rietx calls no gap a verdict, because how many esds is far depends on the parameter.
Read the two values beside the multiple of σ, because a parameter near zero with an esd near zero can show thousands of σ with no physical size.

Here the largest gap is under 0.01 esd, so the two directions agree on every parameter.
No `SEQUENTIAL_PATH_CHECK_NOT_RUN` or `SEQUENTIAL_PATH_CHECK_INCOMPLETE` fired, so the comparison ran on every pattern.
`direction_gaps` is `None` when the downward chain was stopped or raised before it finished.

A large gap means the data alone do not fix that parameter, and the order of the chain decides it.
Hold the parameter, restrain it, or quote the spread between the two directions as its uncertainty.
A gap whose two chains kept different attempts measures the restart ladder as well as the order.

The downward chain repeats the work of the upward one, so `direction="both"` takes about twice as long.

## Check a step against two independent fits

`series.steps` lists every parameter's step between consecutive patterns, in esds of the later fit, largest first.
It calls no step a jump, because a large one may be a transition, a sample shift, a beam dump or a wrong model, and only the sample's history can say which.
A step is either in the data or made by the chain, and the size cannot tell which.
`verify_steps=k` refits the two patterns of each of the k largest steps from your starting model, each on its own, and reports the step they give.
This replaces the 700 K pattern with one whose cell is 1.5 % larger:

```{literalinclude} ../../../examples/guides/path.py
:language: python
:start-after: "# guide: jump start"
:end-before: "# guide: jump end"
```

<!-- output of examples/guides/path.py -->
```text
phases.0.cell.a p003->p004  +0.06454  15,810 esd  cold pair 1.00x
phases.0.cell.b p003->p004  +0.06454  15,810 esd  cold pair 1.00x
phases.0.cell.c p003->p004  +0.06454  15,810 esd  cold pair 1.00x
phases.0.cell.a p004->p005  -0.06040  -14,062 esd  not refitted
p000  cold
p001  warm
p002  warm
p003  warm
p004  warm
p005  warm
p006  warm
```

`SeriesStep.cold_ratio` is the cold step over the chain's.
Near 1 the step is in the data, as here.
Near 0 the chain made it, because the two patterns agree when nothing passes an error between them.
Near −1 the cold pair stepped the other way.
A step the check did not reach keeps `cold_ratio` at `None`, as the step back down at 800 K does here.
Every step of this synthetic ramp is hundreds of esds, because its esds are tiny, so read the order of the list rather than a size.

The check costs up to two full fits per step, and nothing else in the result changes.
Here `cell.b` and `cell.c` step with `cell.a`, because the cubic cell ties them to it, so the three largest steps share one pair of refits.

## Read where each fit started

`entry.rung` says which attempt each fit kept.
Here every warm start held, on both sides of the step: the 700 K fit started from the 600 K answer and the 800 K fit from the 700 K answer, and each reached 0.04.
A warm start that diverged or carried an `error` diagnostic would have been fitted again, with the whole plan and then from your starting model, and `entry.rwp_warm` would keep the Rwp its first attempt reached.
A `cold` entry's values do not continue the chain, so read them as a separate measurement.

The full script is `examples/guides/path.py`.

## See also

- [How to fit a temperature series](series.md) runs the chain these checks test.
