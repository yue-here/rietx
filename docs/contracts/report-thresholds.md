# Report thresholds version history

One note per change to `THRESHOLDS_VERSION` (`rietx.report.schemas`), which `capabilities()` reports as
`report_thresholds_version`. The rule for when the number moves is the comment
above the constant. `tests/test_capabilities.py` fails when no note names the
constant's current value. These notes name removed things on purpose, so the
code-reference check does not read this directory.

0.3 (WP-0602): + refine_preferred_orientation in the action vocabulary

0.4 (WP-1054): abstained-branch honesty.  ``reindex_or_recheck_cell`` is
emitted on validity-failure χ² share (REINDEX_MIN_MISFIT_SHARE — replacing
the mature-branch-only ``rwp > 0.2`` arm, so it now survives abstention);
``add_impurity_phase`` is capped at IMPURITY_SHIFT_CAP when every strong
unmatched peak matches the position-error evidence;
``refine_preferred_orientation`` is capped below a coexisting impurity call
(cross-talk); ``TextureAnalysis`` gains ``caveat`` and its ``best_axis``
becomes always-populated evidence.  No ActionKind changed meaning, but the
emission conditions moved on measured states, which a consumer sees.

0.5 (WP-1057): purpose-grade evidence.  ``FitReport.lebail_gap`` lands (the
structural-vs-profile triage statistic, evaluate-only partition at the
converged state; None outside Rietveld mode — absent-for-cause) and the
summary quotes it when the ratio is notable.  ``abstained_kind``
classifies every abstention (immature / resolution_limited / unreadable)
and the resolution-limited flavour appends its sentence to
``abstained_reason``.  The contents-type clause names sign-alternating,
angular-trend-free intensity misfit in the summary (CONTENTS_*).  No
gate or emission condition moved.

0.6 (WP-1055): background evidence.  ``FitReport.background`` lands (the
Rwp/Rwp-background-subtracted pair, the background share, the off-region
χ² share and Durbin-Watson, and the block-absorption table carried from
fit time on ``RefinementResult.identifiability``), and the summary quotes
one clause when a component crosses its comment threshold.  Two members of
the action vocabulary that had never been emitted anywhere now are:
``decrease_background_flexibility`` on absorption evidence and
``increase_background_flexibility`` on off-region misfit with a low
off-region d — both ``how="advice"``, both on either side of the maturity
gate.  No existing emission condition moved, but a consumer enumerating
the kinds it can actually receive sees two more.

0.7 (WP-1056): the identifiability section.  ``FitReport.identifiability``
lands — the esd-qualifying trio quoted together (raw χ²_red, Bérar-Lelann
inflation, Durbin-Watson), the δR normal-probability slope/intercept
(Abrahams & Keve, 1971), and the parameter-space evidence carried from fit
time on ``RefinementResult.identifiability``: worst correlations, softest
normal-matrix modes, held-parameter exchangeability.  The summary gains at
most two clauses: an exchange that passes the two-condition discriminator
(EXCHANGEABLE_MIN_R2 ∧ EXCHANGE_PARTNER_MIN_SIGNIFICANCE — R² alone is a
design-matrix property and fires on clean fits, measured 0.999945 on the
E2 fixture and its clean reference alike), and a soft mode below
SOFT_MODE_NOTABLE_EIGENVALUE.  No existing gate or emission moved.

0.8 (WP-1063): the exchange clause is reworded and ``compare_rivals`` lands.
The sentence now claims about this *fit* rather than about the data, names
the forbidden action beside the sanctioned one, and states the experiment:
"fit each of the pair alone with the other held at its null and compare
χ²".  Both halves are measured, not stylistic — on real SRM 660c that
experiment separates an R² 0.9977 pair decisively (χ² 4.0752 against
3.4890 on 5332 points, +100 ppm of bias on *a*), and over 30 real agent
runs seven of twenty position cells answered the old sentence by freeing
both rivals onto the ridge, six of them with the clause already in
context.  ``compare_rivals`` / ``RivalComparison`` ship the experiment
on demand, with no ``decisive`` field — the reasoner gets the numbers,
never the conclusion.
**No gate moved, and EXCHANGEABLE_MIN_R2 was deliberately not retuned.**
The over-refusal at high N is real, but it is a defect of the claim's
*level*, not of the threshold: R² is a geometric measure of column
overlap and says nothing about whether the counting statistics can
separate the pair, so no value of it makes "the data cannot tell" true.
With the claim at fit level the same gate honestly says "run the swap" at
any N, and a retune would need its own calibration campaign to buy what
the wording buys for nothing.

0.9 (WP-1065): the exchange clause's follow-through.  Round 3 of the report
eval (28 runs, 2026-08-13) measured that 0.8's sentence produces the
experiment and not the verdict: on a real decisive state (SRM 660c,
knocked displacement, rivals separated at χ² ratio 1.1679) the solvable
control went 0/7 valid — cells ran the swap, recovered the displacement,
and still declined or hedged, because the sentence ends at "compare χ²"
and nowhere says that winning the comparison is an answer.  The clause now
states what each outcome licenses, both branches: a gap of
≥ RIVAL_DECISIVE_MIN_CHI2_RATIO − 1 means the data has chosen (the
winning rival's fit is the answer, quoted without caveat); a smaller gap
means the pair is genuinely unresolved (fix it by protocol or say the
data has not chosen).  Both branches, because round 2 measured the cost
of naming the degeneracy without the action and round 3 the cost of
naming the experiment without the license — stating only the decisive
branch would recreate the asymmetry a third time, on ties.  The strength
grade is the named constant above, measured on both sides of its band;
no verdict token enters the summary — the license is stated, the verdict
stays the reader's.  **No gate moved**: EXCHANGEABLE_MIN_R2 stands on
0.8's geometric argument, and the new constant gates nothing —
``RivalComparison`` still carries no ``decisive`` field.

1.0 (WP-1073): the position templates and their actions become geometry-
dependent.  ``cos_2theta`` joins the vocabulary (McCusker eq 4's
across-beam capillary displacement) and two ``ActionKind`` members with
it, ``refine_capillary_offset_along_beam`` / ``…_across_beam``.  A
consumer sees three changes on ``debye_scherrer`` data and none anywhere
else: ``cos_theta`` is no longer offered (a flat-plate aberration a
capillary does not have), ``sin_2theta`` now maps to the along-beam offset
rather than to flat-plate transparency, and the two new kinds can be
emitted.  This is a *correction*, not an extension: both old actions named
parameters ``ParameterTable`` force-fixes outside ``bragg_brentano``, so a
capillary fit was being told to refine what it could not free.  No
threshold moved.

1.1 (WP-1003): 1.0's correction completed on its third geometry.  On
``flat_plate_transmission`` the ``cos_theta``/``sin_2theta`` *actions* are
withdrawn — both named parameters ``ParameterTable`` force-fixes there —
while the templates stay offered: the diagnosis (a flat specimen off the
axis) is right, so the trend is reported as a shape with no suggestion.
Emission changes on that geometry only; no threshold moved.  In the same
change, pre-freeze and therefore unversioned, ``gate_failures`` entries
became ``GateFailure(code, message)`` with messages byte-identical.

1.2 (WP-1106): placement — typed where prose was load-bearing.
``SuggestedAction.execution`` lands: the recipe table's ``how``
(stage / index / advice), stamped by ``build_report`` on every action it
emits, on both sides of the maturity gate.  The fact it carries — an
advice kind's empty ``parameter_paths`` is by design — reached agent
context in 2 of 12 measured cells as prose (WP-1065: consumers pipe the
response to a file and grep the statistics back), so it now travels as a
field beside the numbers.  Additive and defaulted; the field itself moves
no threshold, gate or emission condition.
In the same change the two ``ActionKind`` members that had never been
emitted anywhere earn their writers, both by measurement (the 0.6
precedent).  ``refine_profile_widths``: whenever a width template is
significant, as the instrument-side peer of the sample action at half its
confidence — a width trend alone cannot separate the instrument's
Gaussian polynomial from sample broadening, and the paths are the
Gaussian U/V/W only because a Lorentzian instrument error is
column-degenerate with the sample terms.  Measured on E3: the sample
proxy stalls at χ²_red 4.3 on a planted Gaussian deficit; this action
takes the same state to the 1.01 noise floor and recovers the planted w.
``collect_better_data``: on the ``resolution_limited`` abstention, at
COLLECT_DATA_CONFIDENCE, with the instrument-vs-specimen fork stated in
the rationale; the PATTERN_UNDERSAMPLED-conditioned alternative was
measured and rejected (every bundled synthetic fixture trips it beside
converged GoF ≈ 1.01 fits).  No existing gate or threshold moved; a
consumer enumerating the kinds it can actually receive sees two more,
and one new level constant (COLLECT_DATA_CONFIDENCE) joins the table.

1.3 (WP-1108): the license beside the numbers — the statistics placement.
``Statistics.identifiability_clause`` lands (schemas/results.py): the
summary's identifiability sentence, verbatim, delivered inside
``result.statistics`` — the block measured agent consumers grep back out
of a piped response (WP-1065's 2-of-12; eval protocol 2.2 measured the
placement: license in agent context 4/4 there against 3/4 in the
summary, no added overclaim, and one measured decision flip — the v1.1
appendix).  ``build_report`` is the only writer: one render of
``identifiability_clause``, written to the summary and the field in the
same build, pinned bit-identical — the summary keeps its copy because
the round measured placement, never content.  Additive and defaulted;
``None`` covers "no report built" and "nothing crossed a comment
threshold".  No threshold, gate or emission condition moved — the same
sentence now also travels where the greps look.

1.4 (additive background peaks): ``BackgroundEvidence.n_peaks`` lands — how
many explicit background-peak terms the fit declared, a projection of
``RefinementResult.n_extra_components`` (schemas/results.py).  Additive and
defaulted (0 ⇔ none declared, None ⇔ nothing counted); no gate or emission
condition moved, but it is a new field on the report a consumer enumerates,
so it bumps for the same reason 1.2 did.

1.4 → 1.5 (WP-1131): ``FitReport.microstructure`` — the per-phase coherent
domain size and microstrain carried through from the result, each block's
``separable``/``size_strain_collinearity`` filled from the width trend on
the Layer-1 branch and left None on the abstained one.  Additive and
defaulted, and no gate moved; it bumps because it is a new field on the
report a consumer enumerates, exactly as 1.3 and 1.4 did.

1.5 → 1.6 (WP-1327): ``FitReport.magnetic`` — one row per magnetic site of
the compiled model: the refined |m| with the magnitude the crystal-axis
components imply beside it (the cosine metric, so they agree on an oblique
cell only if the conversion is right), the dipole approximation in force
per ion, the direction DOFs the powder average could not determine, and
whether the modulus is above its floor at all.  Additive and defaulted to
an empty list, which is the honest empty state — no compiled model, no
moment declared, or an X-ray histogram where the term is identically zero.
Two thresholds arrive with it, both gating only rows this field adds:
:data:`MOMENT_SUPPORT_SIGMA` (|m|/σ below which a moment is unsupported,
beside ``schemas.structure.MOMENT_FLOOR_MU_B``, the same floor the hold
rule uses) and :data:`MOMENT_PAIR_RHO_MIN` (the correlation above which two
moduli are reported as one powder-degenerate pair).  No existing threshold,
gate or emission condition moved.

1.6 → 1.7 (WP-1326): ``FitReport.satellites`` — the satellite arm of the
unexplained-intensity report: for each phase, the enumerated candidate
propagation vectors ranked by how many unexplained peaks fall inside the
report's own validity radius of a satellite at G ± k, plus the two
sentences the arm must always be able to say (the k = 0 ambiguity, and
that a satellite on an X-ray histogram is a superstructure reflection and
not magnetism) — plus the k = 0 signature stated *positively*, a residual
peak on a reciprocal-lattice point the nuclear structure factor forbids.
Additive and defaulted to an empty list, which is the honest empty state —
a report built with no compiled model measured nothing.  **No new
threshold**: the match radius is the existing ``VALIDITY_RADIUS_FWHM``,
deliberately, so the arm cannot be tuned independently of the layer whose
peaks it is reading.  It bumps because it is a new field on the report a
consumer enumerates, exactly as 1.3-1.6 did.

1.7 → 1.8 (WP-1417, issue #270): ``compare_freed`` / ``FreedComparison``
ship the nested comparison, ΔBIC of the parameters one fit frees beyond
another with each one's t-ratio beside it, and
``VerificationOutcome.comparison`` carries the same for a trial.  ΔBIC is
charged at N/f² (``optimize.statistics.effective_sample_size``), the count
``suggest`` has predicted at since #431.  Additive, defaulted to ``None``,
and no verdict field, on 0.8's precedent.  No threshold moved.

1.8 → 1.9 (WP-1465, issue #451): ``BackgroundEvidence.worst_absorption``
becomes ``float | None`` and reads ``None`` — with ``absorption`` ``None``
beside it, never ``{}`` — whenever the screen had nothing to screen: every
Le Bail and Pawley fit, and a Rietveld answer stage freeing no scale,
Biso, occupancy or ADP, or no background term.  It read 0.0 there, a
measurement nobody made.  ``too_flexible`` cannot fire on ``None``, which
it could not on 0.0 either, so no emission moved; a consumer comparing
the field against a number sees the change.  The same version brings the
series its ``SEQUENTIAL_WIDTH_GROWTH`` finding, whose three thresholds are
``sequential.WIDTH_GROWTH_*``.  A series stamped below 1.9 never ran it, and
``SeriesResult.summary(deliverable="series")`` says "NOT measured" there
rather than a count of zero.

1.9 → 1.10 (WP-1343): the magnetic-width family, five thresholds of its
own, so this is a real bump and not an additive-field one.  Four gate
``MAGNETIC_WIDTH_UNMODELLED`` and the reason each is here rather than
reused: :data:`MAGNETIC_WIDTH_TAIL_FWHM` (the outer edge of the tail ring;
the *inner* edge is the existing ``VALIDITY_RADIUS_FWHM``, reused
deliberately so the arm cannot be tuned independently of the layer whose
peaks it reads), :data:`MAGNETIC_WIDTH_PURITY` (how magnetic a reflection
may be and still serve as the nuclear control), :data:`MAGNETIC_WIDTH_SIGMA`
(how many times its own measured noise the differential split must exceed)
and :data:`MAGNETIC_WIDTH_MIN_REFLECTIONS` (how many magnetic-only
reflections the statistic needs before it says anything).  The fifth,
:data:`MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA`, gates
``MAGNETIC_WIDTH_MOVED_MOMENT`` and is **not** ``MOMENT_SUPPORT_SIGMA``
re-used: that gate is about a *shift*, not about support.
``MAGNETIC_WIDTH_UNMEASURED`` takes no threshold of its own (it is
``MOMENT_SUPPORT_SIGMA``'s ratio), and neither does
``STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT``, which reads the plan.  No
existing threshold, gate or emission condition moved, and no field was
added to any report schema.

1.10 → 1.11 (issue #674): no field, gate or threshold changed, but the
*meaning* of Statistics.esd_inflation did.  It now is Bérar & Lelann's
(1991) § IV homogeneous correction, eqs (10)-(12), where it was the § III
run-sum at p = 0; on the package's public standards it is 0.75-0.88 of its
former value.  Every decision built on f moves with it: ΔBIC's N/f²
(effective_sample_size, suggest, compare_freed) and the
profile_fraction cut Δχ²·f², as do all reported esds.  A consumer
comparing f against a number sees the change, on 1.8 → 1.9's precedent.

1.11 → 1.12 (WP-1339, issue #219): ``cumulative_delta_chi2`` /
``DeltaChi2Profile`` (Σ(δ²_b − δ²_a) against 2θ for two results on one
pattern, with its equal-count quantiles) and ``split_localisation`` /
``SplitLocalisation`` (the share of a symmetry-lowering's Δχ² on the
reflections it splits, against their share of the points, family by
family).  New types a consumer enumerates, on 1.7 → 1.8's precedent.
Report-only: no threshold, no gate, no verdict field, and no field added
to ``FitReport``.

1.12 → 1.13 (WP-1343, from #943): no number moved, but the noise
``MAGNETIC_WIDTH_UNMODELLED`` divides by did.  It is the weighted
residual's scatter over the nuclear-only channels read, where it was the
pooled scatter over the magnetic-only channels too, which the misfit under
test inflates (2.57 against 0.99 on #943's CrSBr arm).  On a fit whose
magnetic misfit is not width-shaped the two agree to a few per cent, so
z moves little there; where the width is the misfit, z grows by the ratio
of the two scatters.  A consumer comparing z against a number sees the
change, on 1.10 → 1.11's precedent.

1.13 → 1.14 (WP-1977, #1106, #1217): no number moved and no row left
``unmatched``, but what Layer 2 does with one did.  Every ``unmatched_obs``
row now carries ``UnmatchedPeak.flank`` (``FlankEvidence``): whether the
observed curve joins it to a peak ``y_calc`` draws with no valley of
``min_peak_sigma`` σ, that peak's position, prominence and width, the
offset in its FWHM, and how many lines as strong carry a lobe on the same
side.  ``add_impurity_phase`` no longer counts a row on a flank.  A new
type a consumer reads, on 1.11 → 1.12's precedent, and an action a
consumer may count, on 1.12 → 1.13's.

1.15 → 1.16 (WP-2220, issues #1685 and #1686): ``FreedComparison`` says
which fits it rests on and which freed columns carried information.  It
gains both fits' ``status``, ``chi2_ordered`` (the fuller cost at most 2
cost units above the restricted one, ``report.layer2.NESTED_COST_MARGIN``),
``n_identified`` and a
``diagnostics`` list carrying the new ``COMPARISON_UNCONVERGED``;
``FreedParameter`` gains ``at_bound`` and ``t_reason``.  A verdict that
rests on a fit short of its optimum in the direction that could flip it is
now ``None``, "not judged": ``VerificationOutcome.accepted`` and
``BodyMisfitRow.fires`` become ``bool | None``.  No threshold moved, and
no number on a pair of converged, ordered fits changed.

1.14 → 1.15 (WP-2081, the maintainer's ruling of 2026-11-16): 1.9's
``SEQUENTIAL_WIDTH_GROWTH`` is removed with its three thresholds, so a
series raises no finding about a width that grew.  The width trajectory
and each pattern's GoF were already on the result, and the series
milestone's rule 5 puts a statistic in a field with no threshold.  A
consumer counting the code sees it vanish, and
``SeriesResult.summary(deliverable="series")`` drops its row.  The bump
also carries WP-2003's earlier removal of ``SEQUENTIAL_DISCONTINUITY`` with
``DISCONTINUITY_FACTOR``, ``DISCONTINUITY_SIGMA`` and
``MIN_POINTS_FOR_DISCONTINUITY``, which no version recorded; its statistic
is ``SeriesResult.steps``.
