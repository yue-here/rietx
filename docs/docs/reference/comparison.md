# Model comparison

This page gives the objects that compare two models of one pattern: `Refinement.suggest`'s ranking of which held parameter to free, `compare_freed`'s measurement once it is freed, where along 2θ an improvement lives, and the check of a rigid body against free atoms.

[How to choose the next parameter to free](../guides/next.md) uses `Refinement.suggest` and `rietx.report.compare_freed` step by step.
[Which parameter to free next](../theory/estimation.md#which-parameter-to-free-next) derives the gain and the ΔBIC.
[`rietx compare`](cli.md#rietx-compare) runs a bundled standard under several settings and draws the cumulative Δχ² against a reference.

## Which parameter to free next

`Refinement.suggest(data)` asks which held parameter has the most leverage on χ² at the current state.
Layer 2 of the report reads the shape of the residual, and `suggest` reads the Jacobian.
The two methods are independent, so their agreement is stronger evidence than either alone.
Neither ranks by leverage alone.
Toby gives the reason: the parameter with the largest derivative is not always the right one to vary, and his example frees an instrument width where the broadening belongs to the sample {cite}`toby2024`.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
s = ref.suggest(data)
print(s.summary)
best = s.best_or_none()
if best is not None:
    ref.set_vary([best.path], True)
```

`suggest` changes nothing.
It scores deep copies of the models, records no history node and leaves the working state alone.
Its keywords are `top_n` (5 groups by default), `include` and `exclude` (dot-path patterns that narrow the candidates), `mode`, `two_theta_limits`, and `report`, a `FitReport` whose suggestions it cross-references.

| Field | Is | Reads as |
|---|---|---|
| `SuggestionResult.groups` | the ranked answer, at most `top_n` `CandidateGroup` entries | descending gain, and only candidates above the noise floor; a converged fit has an empty list, which is the right suggestion |
| `SuggestionResult.non_separable` | the candidates the absorption gate refused | each one's `ParameterCandidate.absorption` says why; reported, not dropped |
| `SuggestionResult.skipped` | dot-paths whose columns are zero at this state | no leverage either way |
| `SuggestionResult.n_evaluated` | how many candidates were scored | what tells "no suggestion" from "nothing was looked at" |
| `SuggestionResult.chi2_red` | the current state's reduced χ², seeded candidates excluded | the scale the floor is set from |
| `SuggestionResult.noise_floor` | the gain a group must exceed to be listed | {{ SUGGEST_MIN_GAIN }} × the larger of `chi2_red` and 1, stored so a serialised result explains its own gate |
| `SuggestionResult.n_effective` | the observation count every `CandidateGroup.delta_bic` was charged at | the probe's residual rows over the square of their Bérar-Lelann factor (`rietx.optimize.statistics.effective_sample_size`); `None` where no factor was measured, and the ΔBIC is then at the raw count |
| `SuggestionResult.summary` | one sentence | the whole answer for a reader |
| `SuggestionResult.best_or_none` | the top group's parameter, or `None` | `None` when no group clears the floor or the top group is a tie; it does not check `delta_bic` |

| Field | Is | Reads as |
|---|---|---|
| `CandidateGroup.members` | one or more `ParameterCandidate` | |
| `CandidateGroup.gain` | the predicted fall in χ² from freeing the whole group | the joint gain the data measures; the members' own gains are near-equal by construction |
| `CandidateGroup.resolved` | false exactly when the group has more than one member | a tie the data cannot split, merged by pairwise collinearity instead of being reported as a winner |
| `CandidateGroup.delta_bic` | the gain read as a model-selection answer, ΔBIC at `SuggestionResult.n_effective` | Schwarz's ΔBIC {cite}`schwarz1978` at the Gauss-Newton prediction of what freeing the group reaches; positive favours freeing |
| `CandidateGroup.delta_bic_raw_n` | the same ΔBIC at the raw residual row count | an upper bound on the evidence; where it is positive and `delta_bic` is not, the leverage is real and the serial correlation says it is not independent evidence |

`gain` ranks: it is the leverage the parameter has on χ² at this state.
`delta_bic` decides whether that leverage is worth a parameter.
It charges ln N for each one, with N the effective count, the rows over the squared esd inflation, because a powder residual is serially correlated.
At raw N almost any improvement wins.
Four synchrotron fits of about 49 500 channels each gave raw-N ΔBIC of +36 to +211 for an occupancy within 2σ of zero, and the ΔBIC at N/f² was negative for all four.
A group can clear the noise floor, the 3σ point of χ²₁ on every pattern, and still be refused by ΔBIC on a long pattern.
The reading is then "this parameter has leverage, and the leverage does not justify it".
That is what a pair of nested refits would measure, available before you run them.
`Refinement.summary` prints the same number on its `next:` line.

| Field | Is | Reads as |
|---|---|---|
| `ParameterCandidate.path` | the dot-path | what `Refinement.set_vary` takes |
| `ParameterCandidate.gain` | the exact Gauss-Newton predicted fall in χ² from freeing this parameter alone | in units of Σw·Δ², not divided by N − P; compare it with `SuggestionResult.noise_floor` and nothing else |
| `ParameterCandidate.gradient` | ∂χ²/∂p in the parameter's physical units, sign included | which way the parameter wants to move |
| `ParameterCandidate.absorption` | the R² of this column on the span of the free columns | 0.0 when nothing is free; near 1 puts the candidate in `SuggestionResult.non_separable` |
| `ParameterCandidate.seeded` | whether the score was measured away from the stored value | true for surface roughness at 0 and a Stephens block at S ≡ 0, scored where their stage would start the solve; a width at 0 is scored at 0 and never seeded |
| `ParameterCandidate.seed_value` | where, when it was seeded | a probe point that was assumed must never look like a measured state |
| `ParameterCandidate.action_kind` | the matching `SuggestedAction.kind`, when `report=` was passed and the paths agree | two independent methods naming the same move |

On the NAC Rietveld fit, `ref.suggest(data)` scores 31 candidates against a noise floor of 112, at N<sub>eff</sub> 349.
It returns five groups, all resolved, led by the impurity's `phases.1.lor_strain` at a gain of 31 942 and ΔBIC +37.
Eight candidates are refused as non-separable.
Four are the major phase's sample widths, at absorption values of 0.986 to 0.991, which the free instrument widths already reproduce.
`phases.1.atoms.0.occ` is refused at 0.973 with a gain of 7529, and `instrument.polarization` at exactly 1.000.
`instrument.geometry.axial_sl` and `instrument.geometry.axial_hl` are refused at 0.957.
Nothing is skipped.

## Measuring a freed parameter

`rietx.report.compare_freed(restricted, full)` measures what `suggest` predicted.
It takes two `Refinement` objects you have already fitted on one pattern, the second freeing everything the first frees and more.
A branch that ran one more stage is the usual pair.
It runs no fit.
It takes refinements and not results because a result lists only what varied, and the value the restricted fit held is in its working table.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
from rietx.report import compare_freed

trial = ref.branch()
trial.run_stage(data, rx.Stage("occupancy", ["phases.0.atoms.2.occ"]))
c = compare_freed(ref, trial)
for p in c.freed:
    print(p.path, p.t_ratio)
print(c.delta_bic, c.delta_bic_raw_n)
```

Each freed parameter comes back with its t-ratio beside the ΔBIC of adding the set.
For one parameter the two agree, ΔBIC being close to t² − ln N<sub>eff</sub>, so a parameter within 1σ of where the restricted fit held it cannot be decisive.
At raw N it can.
On a synthetic LaB₆ fit whose model lacks the data's Lorentzian width (21 400 channels, Durbin-Watson 0.10, f = 5.77), freeing the boron Biso gave t = +1.67, raw-N ΔBIC +87 and ΔBIC −3.6 at N<sub>eff</sub> 642.

| Field | Is | Reads as |
|---|---|---|
| `FreedComparison.freed` | one `FreedParameter` per path the fuller fit frees beyond the restricted one | |
| `FreedComparison.n_added` | the difference in free-parameter count | the solver's count, so a tied row adds nothing |
| `FreedComparison.n_points` | the channel count both fits saw | |
| `FreedComparison.chi2_restricted`, `FreedComparison.chi2_full` | each fit's Σw·Δ², its `Statistics.chi2` times N − P | what ΔBIC takes |
| `FreedComparison.esd_inflation` | the restricted fit's Bérar-Lelann factor f | the residual `suggest` measures f on, so a prediction and its refit are charged alike |
| `FreedComparison.n_effective` | N/f² | `rietx.optimize.statistics.effective_sample_size` |
| `FreedComparison.delta_bic` | ΔBIC charged at `n_effective` | positive favours the fuller model |
| `FreedComparison.delta_bic_raw_n` | the same at the channel count | an upper bound on the evidence, kept so the gap is visible |

| Field | Is | Reads as |
|---|---|---|
| `FreedParameter.path` | the dot-path | |
| `FreedParameter.held_at` | where the restricted fit held the parameter | read off its working table; a coordinate DOF is read through the coordinate row it drives, because a DOF is a step from where its own fit began; `None` where the restricted model has no such entry, such as a phase the fuller model adds |
| `FreedParameter.value` | the fuller fit's value | |
| `FreedParameter.esd` | the fuller fit's esd | already inflated by that fit's Bérar-Lelann factor |
| `FreedParameter.t_ratio` | `(value - held_at) / esd` | how far the parameter moved, in its own esds; `None` where either is |

There is no verdict field.
A pair that is not nested raises `ValueError`: a different channel count, different intensities or a different mode, a path the restricted fit frees and the fuller one does not, nothing added, or a free count that moved by other than the added paths.
A refinement that has not been fitted raises `RuntimeError`.

### Trying a suggestion

`rietx.report.predict_then_verify(ref, data, action)` frees a `SuggestedAction`'s paths in one stage and measures the result.
It runs on a branch of the history, so a rejected action leaves the working state where it was.
With the history disabled it runs on the refinement itself.
It accepts the action when the reduced χ² falls by more than `min_improvement` of its value, 1 % by default.

| Field | Is |
|---|---|
| `VerificationOutcome.kind` | the action's kind |
| `VerificationOutcome.predicted_delta_chi2` | the action's `expected_delta_chi2` |
| `VerificationOutcome.observed_delta_chi2` | the fall in the reduced χ² the stage achieved |
| `VerificationOutcome.accepted` | whether that fall passed the `min_improvement` rule, and nothing else |
| `VerificationOutcome.reason` | the χ² before and after, as a sentence |
| `VerificationOutcome.comparison` | the trial's `FreedComparison`; `None` when no trial fit ran, when the action freed nothing new, or when a hold in the stage broke the nesting |

An action with no parameter paths, and a trial whose fit fails, come back rejected with the reason.
On a synthetic LaB₆ fit with the cell 0.0005 Å off, verifying `refine_cell` predicted 16.16 and observed 16.31, with the reason `χ² 16.93 → 0.6239 (+96.31%); accepted`.

## Where the improvement lives

ΔBIC says whether a richer model paid off, not where along 2θ it did.
Two functions in `rietx.report` answer that from two results on one pattern, fitted over the same limits and exclusions.
Neither runs a fit, and neither has a threshold or a verdict field.

<!-- api-doc: no-exec — it needs two results that have run -->
```python
from rietx.report import cumulative_delta_chi2, split_localisation

prof = cumulative_delta_chi2(cubic_result, tetragonal_result)
print(prof.total, [(q.two_theta_min, q.share) for q in prof.quantiles])

loc = split_localisation(cubic_result, tetragonal_result)
print(loc.split_share, loc.split_point_share)
for f in loc.families:
    print(f.hkls, f.splits, f.delta_chi2)
```

`cumulative_delta_chi2(a, b)` is Σ(δ²<sub>b</sub> − δ²<sub>a</sub>) up to each channel, with δ = Δ/σ on each fit's own σ.
It is the curve `rietx compare` draws with `a` as its reference, so a falling stretch is `b` fitting better there.
`n_quantiles=` (default 10) sets how many equal-count runs of channels it sums.
`rietx.report.cumulative_chi2` is one fit's half, and it is what each `rietx compare` record stores.

| Field | Is | Reads as |
|---|---|---|
| `DeltaChi2Profile.two_theta`, `DeltaChi2Profile.cumulative` | the fitted channels, and Σ(δ²<sub>b</sub> − δ²<sub>a</sub>) up to each | negative-going where `b` fits better |
| `DeltaChi2Profile.total` | the last value of the curve, the raw χ² difference | the shares are not informative when it is near zero |
| `DeltaChi2Profile.n_points` | the channel count | |
| `DeltaChi2Profile.quantiles` | one `DeltaChi2Quantile` per equal-count run of channels, in 2θ order | where the difference accumulates |
| `DeltaChi2Quantile.two_theta_min`, `DeltaChi2Quantile.two_theta_max`, `DeltaChi2Quantile.n_points` | the run's range and size | |
| `DeltaChi2Quantile.delta_chi2`, `DeltaChi2Quantile.share` | the run's Δχ² and its share of `total` | a negative share moves against the total; `None` when the total is 0 |

`split_localisation(higher, lower)` takes a fit and a symmetry-lowering of it.
It assigns each of `lower`'s reflection ticks to the nearest of `higher`'s, within the same emission line.
The two fits may therefore be in different settings and need no transformation matrix.
Reflections of `higher` at one 2θ, such as 333 and 511 of a cubic parent, form one family carrying every hkl there.
A family is split when its assigned ticks sit at more than one position.
Each family is windowed from its lowest assigned tick to its highest, widened on each side by the FWHM of `higher`'s calculated peak there, or by `half_width=` degrees.
The Δχ² is then shared among the windows of split families, the windows of the other families and the rest of the pattern.

| Field | Is | Reads as |
|---|---|---|
| `SplitLocalisation.higher_phase`, `SplitLocalisation.lower_phase` | the phases compared | |
| `SplitLocalisation.total` | Σ(δ²<sub>lower</sub> − δ²<sub>higher</sub>) over the pattern | negative where the lower symmetry fits better |
| `SplitLocalisation.n_points`, `SplitLocalisation.n_split_families` | the channel count, and how many families `lower` splits | |
| `SplitLocalisation.split_delta_chi2` | the Δχ² in the split windows | |
| `SplitLocalisation.split_share` | the split windows' share of `total` | `None` when `lower` splits nothing in range |
| `SplitLocalisation.split_point_share` | the fraction of channels in a split window | what `split_share` is read against |
| `SplitLocalisation.unsplit_share`, `SplitLocalisation.unsplit_point_share` | the same for the windows of families that do not split | |
| `SplitLocalisation.elsewhere_share`, `SplitLocalisation.elsewhere_point_share` | the same for the channels in no window | the three shares sum to one |
| `SplitLocalisation.n_unmatched` | `lower` ticks with no `higher` reflection within two widths | superstructure reflections, counted and not windowed |
| `SplitLocalisation.families` | one `SplitFamily` per `higher` position and emission line | |
| `SplitFamily.hkls`, `SplitFamily.emission_line`, `SplitFamily.two_theta` | the reflections at that position, which line's image, and the position | emission line 0 is the shortest wavelength |
| `SplitFamily.n_assigned`, `SplitFamily.spread`, `SplitFamily.splits` | how many of `lower`'s ticks were assigned, their spread in degrees, and whether they split | |
| `SplitFamily.window`, `SplitFamily.n_points` | the 2θ interval its Δχ² is summed over, and its channel count | |
| `SplitFamily.delta_chi2`, `SplitFamily.share` | the window's Δχ² and its share of `total` | |

A distortion the data hold puts its gain where it splits reflections, so `split_share` runs well above `split_point_share`.
The function exists because of a laboratory pattern where the lower-symmetry model won every global statistic and the reflections it splits carried none of the gain.
The synthetic pairs of `tests/test_localisation.py` reproduce the contrast, with `compare_freed`'s `delta_bic` positive when the tetragonal model wins.
On a tetragonal Cu pattern, ΔBIC is +190 at N/f², and the split reflections carry +68 % of the gain on 3.2 % of the points.
On a cubic pattern with a peak shift that depends on the reflection, ΔBIC is still +25 at N/f², and the split reflections carry −30 % on 4.9 % of the points.

Two results on different grids, intensities or σ raise `ValueError`, from either function.
A measured background widens σ, so two fits that declare different backgrounds can differ there.
A result with more than one indexed phase raises too, unless `higher_phase=` or `lower_phase=` names the phase.
The coexistence case, a second phase beside the parent, transfers weakly and is not what `split_localisation` measures.

## Rigid bodies against the data

A rigid body can converge to a good pose with the wrong shape, and nothing in the report names the body.
`Refinement.check_rigid_bodies(data)` refits each body twice from the fitted state: as the body, and as free atoms held near the template by soft restraints on every template bond and bonded angle.
Both refits run under the refinement's own 2θ limits, ties, holds, backend and solver.
It compares them on the data χ² with Hamilton's R-factor ratio test {cite}`hamilton1965` and with ΔBIC {cite}`schwarz1978`, both at the effective observation count.
It warns ([`RIGID_BODY_MISFIT`](diagnostics-refinement.md#rigid_body_misfit)) only when both prefer the released atoms.
It costs two refinements per body and is not part of `fit`.

<!-- api-doc: no-exec — it needs a refinement of a rigid-body phase that has run -->
```python
out = ref.check_rigid_bodies(pattern)
for row in out.rows:
    print(row.body, row.fires, row.delta_bic, row.deviations[:3], row.dropped)
```

Its keywords, with their defaults: `free` (`phases.*.scale` and `instrument.background.*`), the non-body parameters both refits refine; `alpha` (0.001), the Hamilton test's significance; `bic_threshold` (10), the ΔBIC the released atoms must beat; `bond_sigma` (0.02 Å) and `angle_sigma` (2°), the restraint widths of the released refit; and `max_iter` (200).
It returns a `rietx.report.body_misfit.BodyMisfitResult`, whose `rows` hold one `rietx.report.body_misfit.BodyMisfitRow` per body and whose `diagnostics` hold the warnings.

| Field | Is |
|---|---|
| `BodyMisfitRow.phase_index`, `BodyMisfitRow.body` | which phase, and the body's name |
| `BodyMisfitRow.chi2_body`, `BodyMisfitRow.chi2_released` | the data χ² of each refit, restraint rows excluded |
| `BodyMisfitRow.n_points`, `BodyMisfitRow.n_effective` | the channel count and the effective count both tests used |
| `BodyMisfitRow.n_free_body`, `BodyMisfitRow.n_added` | the free parameters of the body refit, and how many the released refit adds |
| `BodyMisfitRow.f_statistic`, `BodyMisfitRow.p_value` | Hamilton's test |
| `BodyMisfitRow.delta_bic` | ΔBIC, positive favouring the released atoms |
| `BodyMisfitRow.fires` | whether both tests prefer the released atoms |
| `BodyMisfitRow.deviations` | (label, template value, released value, Δ/σ) for each template bond and angle, largest first |
| `BodyMisfitRow.dropped` | your ties and holds that could not follow into the released refit |

The warnings are on the returned object, not on the fit's `RefinementResult.diagnostics`.
Each message names the three template bonds or angles the released refit moved furthest, in units of their restraint σ.
[`RIGID_BODY_MISFIT`](diagnostics-refinement.md#rigid_body_misfit) gives the explanation the package attaches to the code.

A template bond wrong by more than the bonding criterion's slack is not found as a bond, so the check cannot see it.
A tie or hold on the released body, or on a later body of its phase whose index the release shifts, is dropped from the released refit and listed in `dropped`.
