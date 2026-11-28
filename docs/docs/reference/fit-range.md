# The fit range record

This page gives `RefinementResult.fit_range`: the `FitRange` record, its `OutsideSpan` per cut stretch and the `ReflectionOutside` a span names.
The rest of the result is on [The refinement result](result.md).

A result holds only the channels it fitted, so on its own it cannot say that a cut happened or what the cut removed.
`RefinementResult.fit_range` is a `FitRange` record that says both.
`Refinement.fit` and `Refinement.run_stage` write it, because they are the calls that hold the whole pattern.
It is `None` on a joint fit, a replay, and a result saved before schema 0.62.
Each fact restates the limits and exclusions the fit was handed, and nothing in the package reads one to decide anything.

| Field | Is | Reads as |
|---|---|---|
| `FitRange.file_range`, `FitRange.n_file` | the file's first and last 2θ and its point count | what was measured |
| `FitRange.limits_requested` | the `two_theta_limits` handed to the fit, or `None` | what was asked for |
| `FitRange.limits_applied` | those limits clipped to the file | an upper limit past the scan's end lands on its last channel |
| `FitRange.excluded_declared` | the pattern's excluded regions | what was asked for |
| `FitRange.excluded_applied` | the regions that removed a channel the limits kept, clipped to the limits | a region outside the limits is declared and not applied |
| `FitRange.fitted_range`, `FitRange.n_fitted` | the first and last fitted channel, and the fitted count | `n_fitted` equals `len(result.two_theta)` |
| `FitRange.counts_file`, `FitRange.counts_fitted` | the summed observed intensity in the file and in the fitted channels | |
| `FitRange.count_share_outside` | the share of the file's counts the limits and excluded regions cut | |
| `FitRange.outside` | one `OutsideSpan` per stretch of channels the limits and excluded regions cut | empty when nothing was cut; a channel left out only for a σ of zero or below is in no span, and `RefinementResult.sigma_rule.n_nonpositive_excluded` counts it |
| `FitRange.cut_window_deg`, `FitRange.straddle_fwhm` | the two reporting widths the spans' facts were read with | `None` when nothing was cut |

`FitRange.line()` is the line `summary()` prints beside `excluded:` when the limits or an excluded region cut channels.
An uncut fit prints no such line, and neither does a fit whose only unfitted channels have a σ of zero or below.

An `OutsideSpan` is one stretch the caller's limits or excluded regions cut.
`OutsideSpan.kind` is `"below"` from the file's start, `"above"` to its end, or `"excluded"` with fitted channels on both sides.
`OutsideSpan.lo`, `OutsideSpan.hi` and `OutsideSpan.n_points` are its first and last channel and its count.
`OutsideSpan.count_share` is its share of the file's counts.
Each ratio below divides by the median observed intensity over the fitted channels.

| Field | Is |
|---|---|
| `OutsideSpan.level_ratio` | the span's median |
| `OutsideSpan.level_ratio_at_cut` | the median of the span's channels within `FitRange.cut_window_deg` of the cut, for a range end |
| `OutsideSpan.level_ratio_far` | the same at the span's other end |
| `OutsideSpan.slope_at_cut` | the slope over that window as a fraction of its mean per degree, positive when rising away from the fitted range |
| `OutsideSpan.background_slope_at_cut` | the fitted background's slope over the same width inside the fitted range, in the same units |
| `OutsideSpan.peak_two_theta`, `OutsideSpan.peak_sigma` | where the span's largest excess over the background envelope lies, and its size in σ |
| `OutsideSpan.reflections` | the reflections the model put in the span or within `FitRange.straddle_fwhm` FWHM of its edge, or `None` for a fit with no compiled model |
| `OutsideSpan.reflections_searched` | the part of the span the model's reflection list covers |

The excess is a location, not a detection.
The envelope sits under the background, and the largest of many channels reads several σ on a featureless span.
Compare it between spans, never against a fixed bar.
Past a range end the model generates reflections only a little beyond the fitted range, so an empty list there says nothing about reflections further out.

A `ReflectionOutside` names `ReflectionOutside.phase`, `ReflectionOutside.hkl` and `ReflectionOutside.line`, the emission line.
It gives the reflection's `ReflectionOutside.two_theta` and `ReflectionOutside.fwhm` at the answer.
`ReflectionOutside.fraction_outside` is the share of its profile area in the span, read off the symmetric pseudo-Voigt with no axial-divergence asymmetry.

