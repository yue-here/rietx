(guide-path)=
# How to check a series for path dependence

Fit the series with `direction="both"` and look for `SEQUENTIAL_PATH_DEPENDENT`, and pass `verify_steps=k` so that the k largest steps in `series.steps` are refitted from cold on their two patterns alone.

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
['SEQUENTIAL_PERSISTENT_FINDING', 'SEQUENTIAL_PERSISTENT_FINDING']
largest forward-backward gap: 0.00 esd
```

`series.backward` is the downward chain's own `SeriesResult`, and the entries of `series` are the upward one's.
A `SEQUENTIAL_PATH_DEPENDENT` diagnostic names each parameter whose two values differ by more than their esds allow, and its message quotes both values.
Read the two values rather than the multiple of σ, because a parameter near zero with an esd near zero can report a gap of thousands of σ that has no physical size.

No such diagnostic fired here, and the largest gap in the cell edge is under 0.01 esd.
`SEQUENTIAL_PATH_CHECK_INCOMPLETE` is absent too, so the comparison ran on every pattern.
The two checks together mean the comparison was made and found nothing.
Without the second, an empty list can also mean the downward chain was stopped or raised before it finished.

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
phases.0.cell.a p003->p004  +0.06454  15,790 esd  cold pair 1.00x
phases.0.cell.b p003->p004  +0.06454  15,790 esd  cold pair 1.00x
phases.0.cell.c p003->p004  +0.06454  15,790 esd  cold pair 1.00x
phases.0.cell.a p004->p005  -0.06040  -14,110 esd  not refitted
p000  cold
p001  warm
p002  warm
p003  warm
p004  warm_staged
p005  cold
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

The jump also broke two warm starts, one on each side of the step.
The 700 K fit, started from the 600 K answer, was rejected and fitted again with the whole plan, still from the 600 K answer, and reached 0.04.
The 800 K fit, started from the 700 K answer, met the step back down and reached an Rwp over 0.9 on both warm attempts.
`entry.rwp_warm` keeps the Rwp the first attempt reached.

The 800 K entry is `cold`: no warm start could be rescued, so the pattern was fitted from your starting model, and it reached 0.04 too.
Its values do not continue the chain, so read them as a separate measurement.

The full script is `examples/guides/path.py`.

## See also

- [How to fit a temperature series](series.md) runs the chain these checks test.
