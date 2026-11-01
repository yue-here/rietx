(guide-interval)=
# How to quote a parameter that ended on its bound

Call `Refinement.profile_interval` with the pattern and the parameter's path, and quote the interval it returns instead of the value ± esd.

A value on its bound is not a measurement, and value ± esd reaches into values the bound forbids.
A profile interval is read off the data's χ² instead: it pins the parameter at a value, refits everything else the fit freed, and finds where χ² has risen by a threshold.

## Find the rows on a bound

This runs `mccusker_structural` on the fluorapatite pattern that ships with rietx.
Its extinction stage frees the Sabine extinction coefficient, in µm²:

```{literalinclude} ../../../examples/guides/interval.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/interval.py -->
```text
phases.0.extinction  0.000 ± 1.973  at_bound True
```

`RefinedParameter.at_bound` is `True` for a row the fit stopped against a bound with the data still pushing outward.
The same rows appear in the `FLOOR_HIT` diagnostic for a floor at 0, and in `BOUND_HIT` for any other bound.
`at_bound` is `None` on a tied row, which is never tested.

## Profile the row

```{literalinclude} ../../../examples/guides/interval.py
:language: python
:start-after: "# guide: interval start"
:end-before: "# guide: interval end"
```

<!-- output of examples/guides/interval.py -->
```text
one-sided True: 0.000 to 0.749
```

A row on its bound gets a one-sided interval: the bound is one end, and the other is where χ² has risen by 2.71 × χ²<sub>red</sub> × f², with f the fit's `Statistics.esd_inflation`.
At 95 %, read this one as "extinction is below 0.749 µm²", mosaic blocks no larger than about 0.9 µm.
A one-sided bound read from the esd would reach 1.645 × 1.973 = 3.2 µm², more than four times as far.
The data push extinction below 0, so χ² rises from the floor faster than the esd assumes.

`interval.lower_stop` and `interval.upper_stop` say why each end is where it is: `"bound"` for the parameter's own limit, `"threshold"` for the χ² rise.
A side that ran out of refits stops on `"refits"`, one whose refit failed on `"error"`, and either end is then `None` rather than a guess.

## Profile a row away from its bounds

The same call on a row inside its bounds gives a two-sided interval, at 3.84 × χ²<sub>red</sub> × f² on each side.
Here it is on the Biso of Ca1:

```{literalinclude} ../../../examples/guides/interval.py
:language: python
:start-after: "# guide: biso start"
:end-before: "# guide: biso end"
```

<!-- output of examples/guides/interval.py -->
```text
0.471 ± 0.061  one-sided False: 0.359 to 0.586
```

The ends are 1.84 esd below the value and 1.90 above.
Where χ² is a parabola in the parameter they would both be 1.96 esd, so here the esd is a fair summary and the interval adds little.
Profile a row away from its bounds when it is strongly correlated with a row that is on one: the bound can stop it on one side.

## Choose the level and the effort

`level` sets the confidence level, 0.95 by default, and moves both thresholds.
`max_refits` caps the refits on each side, {{ PARAMETER_INTERVAL_MAX_REFITS }} by default.
Each side steps outward by 1, 2, 4, … esd until χ² passes the threshold, then solves for the end to a thousandth of an esd.
`interval.n_refits` counts the refits, and `interval.points` holds each pinned value with its χ².

Every refit runs on a branch of the history.
The working models, `Refinement.result_` and the history's head are left as the fit left them.

The path must have been free in the last fit.
A tied, locked or fixed path is refused, and the message says which.

`interval.fit_is_minimum` is `False` when one of the refits found a lower χ² than the fit itself.
The fit then stopped short of its minimum along that parameter, and ends measured from it are too wide.
Run the last stage again and profile the new result.

## See also

- [Estimation](../theory/estimation.md) derives the esd and the Bérar-Lelann inflation f.
- [How to choose the next parameter to free](next.md) shows how a row on its floor can still score as a candidate.
