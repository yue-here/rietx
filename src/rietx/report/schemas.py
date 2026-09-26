"""FitReport schemas — the agent-facing contract, versioned by
``FitReport.thresholds_version``.

Three gated layers (docs/DESIGN.md, "Outputs & fit assessment"):

* **Layer 0** — model-free, always trustworthy (:mod:`.layer0`);
* **Layer 1** — gated linear misfit attribution (:mod:`.layer1`), present only
  when the report is built with the compiled model *and* the fit is mature
  enough to linearise;
* **Layer 2** — typed, advisory suggested actions (:mod:`.layer2`), subject to
  the staged-strategy engine's veto.

Thresholds are pinned here (and echoed in ``Provenance``) so agent behaviour
is reproducible across versions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..schemas.common import Base
from ..schemas.results import (
    CorrelationPair,
    GeometryTable,
    PhaseMicrostructure,
    RestraintReport,
    SoftMode,
)
from ..strategy.staged import BACKGROUND_ABSORPTION_GUARD

# Any change a consumer could observe bumps the last component by one, and
# the comment says what changed — no classification, no digest (WP-1117).
# 0.3 (WP-0602): + refine_preferred_orientation in the action vocabulary
# 0.4 (WP-1054): abstained-branch honesty.  ``reindex_or_recheck_cell`` is
#   emitted on validity-failure χ² share (REINDEX_MIN_MISFIT_SHARE — replacing
#   the mature-branch-only ``rwp > 0.2`` arm, so it now survives abstention);
#   ``add_impurity_phase`` is capped at IMPURITY_SHIFT_CAP when every strong
#   unmatched peak matches the position-error evidence;
#   ``refine_preferred_orientation`` is capped below a coexisting impurity call
#   (cross-talk); ``TextureAnalysis`` gains ``caveat`` and its ``best_axis``
#   becomes always-populated evidence.  No ActionKind changed meaning, but the
#   emission conditions moved on measured states, which a consumer sees.
# 0.5 (WP-1057): purpose-grade evidence.  ``FitReport.lebail_gap`` lands (the
#   structural-vs-profile triage statistic, evaluate-only partition at the
#   converged state; None outside Rietveld mode — absent-for-cause) and the
#   summary quotes it when the ratio is notable.  ``abstained_kind``
#   classifies every abstention (immature / resolution_limited / unreadable)
#   and the resolution-limited flavour appends its sentence to
#   ``abstained_reason``.  The contents-type clause names sign-alternating,
#   angular-trend-free intensity misfit in the summary (CONTENTS_*).  No
#   gate or emission condition moved.
# 0.6 (WP-1055): background evidence.  ``FitReport.background`` lands (the
#   Rwp/Rwp-background-subtracted pair, the background share, the off-region
#   χ² share and Durbin-Watson, and the block-absorption table carried from
#   fit time on ``RefinementResult.identifiability``), and the summary quotes
#   one clause when a component crosses its comment threshold.  Two members of
#   the action vocabulary that had never been emitted anywhere now are:
#   ``decrease_background_flexibility`` on absorption evidence and
#   ``increase_background_flexibility`` on off-region misfit with a low
#   off-region d — both ``how="advice"``, both on either side of the maturity
#   gate.  No existing emission condition moved, but a consumer enumerating
#   the kinds it can actually receive sees two more.
# 0.7 (WP-1056): the identifiability section.  ``FitReport.identifiability``
#   lands — the esd-qualifying trio quoted together (raw χ²_red, Bérar-Lelann
#   inflation, Durbin-Watson), the δR normal-probability slope/intercept
#   (Abrahams & Keve, 1971), and the parameter-space evidence carried from fit
#   time on ``RefinementResult.identifiability``: worst correlations, softest
#   normal-matrix modes, held-parameter exchangeability.  The summary gains at
#   most two clauses: an exchange that passes the two-condition discriminator
#   (EXCHANGEABLE_MIN_R2 ∧ EXCHANGE_PARTNER_MIN_SIGNIFICANCE — R² alone is a
#   design-matrix property and fires on clean fits, measured 0.999945 on the
#   E2 fixture and its clean reference alike), and a soft mode below
#   SOFT_MODE_NOTABLE_EIGENVALUE.  No existing gate or emission moved.
# 0.8 (WP-1063): the exchange clause is reworded and ``compare_rivals`` lands.
#   The sentence now claims about this *fit* rather than about the data, names
#   the forbidden action beside the sanctioned one, and states the experiment:
#   "fit each of the pair alone with the other held at its null and compare
#   χ²".  Both halves are measured, not stylistic — on real SRM 660c that
#   experiment separates an R² 0.9977 pair decisively (χ² 4.0752 against
#   3.4890 on 5332 points, +100 ppm of bias on *a*), and over 30 real agent
#   runs seven of twenty position cells answered the old sentence by freeing
#   both rivals onto the ridge, six of them with the clause already in
#   context.  ``compare_rivals`` / ``RivalComparison`` ship the experiment
#   on demand, with no ``decisive`` field — the reasoner gets the numbers,
#   never the conclusion.
#   **No gate moved, and EXCHANGEABLE_MIN_R2 was deliberately not retuned.**
#   The over-refusal at high N is real, but it is a defect of the claim's
#   *level*, not of the threshold: R² is a geometric measure of column
#   overlap and says nothing about whether the counting statistics can
#   separate the pair, so no value of it makes "the data cannot tell" true.
#   With the claim at fit level the same gate honestly says "run the swap" at
#   any N, and a retune would need its own calibration campaign to buy what
#   the wording buys for nothing.
# 0.9 (WP-1065): the exchange clause's follow-through.  Round 3 of the report
#   eval (28 runs, 2026-08-13) measured that 0.8's sentence produces the
#   experiment and not the verdict: on a real decisive state (SRM 660c,
#   knocked displacement, rivals separated at χ² ratio 1.1679) the solvable
#   control went 0/7 valid — cells ran the swap, recovered the displacement,
#   and still declined or hedged, because the sentence ends at "compare χ²"
#   and nowhere says that winning the comparison is an answer.  The clause now
#   states what each outcome licenses, both branches: a gap of
#   ≥ RIVAL_DECISIVE_MIN_CHI2_RATIO − 1 means the data has chosen (the
#   winning rival's fit is the answer, quoted without caveat); a smaller gap
#   means the pair is genuinely unresolved (fix it by protocol or say the
#   data has not chosen).  Both branches, because round 2 measured the cost
#   of naming the degeneracy without the action and round 3 the cost of
#   naming the experiment without the license — stating only the decisive
#   branch would recreate the asymmetry a third time, on ties.  The strength
#   grade is the named constant above, measured on both sides of its band;
#   no verdict token enters the summary — the license is stated, the verdict
#   stays the reader's.  **No gate moved**: EXCHANGEABLE_MIN_R2 stands on
#   0.8's geometric argument, and the new constant gates nothing —
#   ``RivalComparison`` still carries no ``decisive`` field.
# 1.0 (WP-1073): the position templates and their actions become geometry-
#   dependent.  ``cos_2theta`` joins the vocabulary (McCusker eq 4's
#   across-beam capillary displacement) and two ``ActionKind`` members with
#   it, ``refine_capillary_offset_along_beam`` / ``…_across_beam``.  A
#   consumer sees three changes on ``debye_scherrer`` data and none anywhere
#   else: ``cos_theta`` is no longer offered (a flat-plate aberration a
#   capillary does not have), ``sin_2theta`` now maps to the along-beam offset
#   rather than to flat-plate transparency, and the two new kinds can be
#   emitted.  This is a *correction*, not an extension: both old actions named
#   parameters ``ParameterTable`` force-fixes outside ``bragg_brentano``, so a
#   capillary fit was being told to refine what it could not free.  No
#   threshold moved.
# 1.1 (WP-1003): 1.0's correction completed on its third geometry.  On
#   ``flat_plate_transmission`` the ``cos_theta``/``sin_2theta`` *actions* are
#   withdrawn — both named parameters ``ParameterTable`` force-fixes there —
#   while the templates stay offered: the diagnosis (a flat specimen off the
#   axis) is right, so the trend is reported as a shape with no suggestion.
#   Emission changes on that geometry only; no threshold moved.  In the same
#   change, pre-freeze and therefore unversioned, ``gate_failures`` entries
#   became ``GateFailure(code, message)`` with messages byte-identical.
# 1.2 (WP-1106): placement — typed where prose was load-bearing.
#   ``SuggestedAction.execution`` lands: the recipe table's ``how``
#   (stage / index / advice), stamped by ``build_report`` on every action it
#   emits, on both sides of the maturity gate.  The fact it carries — an
#   advice kind's empty ``parameter_paths`` is by design — reached agent
#   context in 2 of 12 measured cells as prose (WP-1065: consumers pipe the
#   response to a file and grep the statistics back), so it now travels as a
#   field beside the numbers.  Additive and defaulted; the field itself moves
#   no threshold, gate or emission condition.
#   In the same change the two ``ActionKind`` members that had never been
#   emitted anywhere earn their writers, both by measurement (the 0.6
#   precedent).  ``refine_profile_widths``: whenever a width template is
#   significant, as the instrument-side peer of the sample action at half its
#   confidence — a width trend alone cannot separate the instrument's
#   Gaussian polynomial from sample broadening, and the paths are the
#   Gaussian U/V/W only because a Lorentzian instrument error is
#   column-degenerate with the sample terms.  Measured on E3: the sample
#   proxy stalls at χ²_red 4.3 on a planted Gaussian deficit; this action
#   takes the same state to the 1.01 noise floor and recovers the planted w.
#   ``collect_better_data``: on the ``resolution_limited`` abstention, at
#   COLLECT_DATA_CONFIDENCE, with the instrument-vs-specimen fork stated in
#   the rationale; the PATTERN_UNDERSAMPLED-conditioned alternative was
#   measured and rejected (every bundled synthetic fixture trips it beside
#   converged GoF ≈ 1.01 fits).  No existing gate or threshold moved; a
#   consumer enumerating the kinds it can actually receive sees two more,
#   and one new level constant (COLLECT_DATA_CONFIDENCE) joins the table.
# 1.3 (WP-1108): the license beside the numbers — the statistics placement.
#   ``Statistics.identifiability_clause`` lands (schemas/results.py): the
#   summary's identifiability sentence, verbatim, delivered inside
#   ``result.statistics`` — the block measured agent consumers grep back out
#   of a piped response (WP-1065's 2-of-12; eval protocol 2.2 measured the
#   placement: license in agent context 4/4 there against 3/4 in the
#   summary, no added overclaim, and one measured decision flip — the v1.1
#   appendix).  ``build_report`` is the only writer: one render of
#   ``identifiability_clause``, written to the summary and the field in the
#   same build, pinned bit-identical — the summary keeps its copy because
#   the round measured placement, never content.  Additive and defaulted;
#   ``None`` covers "no report built" and "nothing crossed a comment
#   threshold".  No threshold, gate or emission condition moved — the same
#   sentence now also travels where the greps look.
# 1.4 (additive background peaks): ``BackgroundEvidence.n_peaks`` lands — how
#   many explicit background-peak terms the fit declared, a projection of
#   ``RefinementResult.n_extra_components`` (schemas/results.py).  Additive and
#   defaulted (0 ⇔ none declared, None ⇔ nothing counted); no gate or emission
#   condition moved, but it is a new field on the report a consumer enumerates,
#   so it bumps for the same reason 1.2 did.
# 1.4 → 1.5 (WP-1131): ``FitReport.microstructure`` — the per-phase coherent
#   domain size and microstrain carried through from the result, each block's
#   ``separable``/``size_strain_collinearity`` filled from the width trend on
#   the Layer-1 branch and left None on the abstained one.  Additive and
#   defaulted, and no gate moved; it bumps because it is a new field on the
#   report a consumer enumerates, exactly as 1.3 and 1.4 did.
# 1.5 → 1.6 (WP-1327): ``FitReport.magnetic`` — one row per magnetic site of
#   the compiled model: the refined |m| with the magnitude the crystal-axis
#   components imply beside it (the cosine metric, so they agree on an oblique
#   cell only if the conversion is right), the dipole approximation in force
#   per ion, the direction DOFs the powder average could not determine, and
#   whether the modulus is above its floor at all.  Additive and defaulted to
#   an empty list, which is the honest empty state — no compiled model, no
#   moment declared, or an X-ray histogram where the term is identically zero.
#   Two thresholds arrive with it, both gating only rows this field adds:
#   :data:`MOMENT_SUPPORT_SIGMA` (|m|/σ below which a moment is unsupported,
#   beside ``schemas.structure.MOMENT_FLOOR_MU_B``, the same floor the hold
#   rule uses) and :data:`MOMENT_PAIR_RHO_MIN` (the correlation above which two
#   moduli are reported as one powder-degenerate pair).  No existing threshold,
#   gate or emission condition moved.
# 1.6 → 1.7 (WP-1326): ``FitReport.satellites`` — the satellite arm of the
#   unexplained-intensity report: for each phase, the enumerated candidate
#   propagation vectors ranked by how many unexplained peaks fall inside the
#   report's own validity radius of a satellite at G ± k, plus the two
#   sentences the arm must always be able to say (the k = 0 ambiguity, and
#   that a satellite on an X-ray histogram is a superstructure reflection and
#   not magnetism) — plus the k = 0 signature stated *positively*, a residual
#   peak on a reciprocal-lattice point the nuclear structure factor forbids.
#   Additive and defaulted to an empty list, which is the honest empty state —
#   a report built with no compiled model measured nothing.  **No new
#   threshold**: the match radius is the existing ``VALIDITY_RADIUS_FWHM``,
#   deliberately, so the arm cannot be tuned independently of the layer whose
#   peaks it is reading.  It bumps because it is a new field on the report a
#   consumer enumerates, exactly as 1.3-1.6 did.
# 1.7 → 1.8 (WP-1417, issue #270): ``compare_freed`` / ``FreedComparison``
#   ship the nested comparison, ΔBIC of the parameters one fit frees beyond
#   another with each one's t-ratio beside it, and
#   ``VerificationOutcome.comparison`` carries the same for a trial.  ΔBIC is
#   charged at N/f² (``optimize.statistics.effective_sample_size``), the count
#   ``suggest`` has predicted at since #431.  Additive, defaulted to ``None``,
#   and no verdict field, on 0.8's precedent.  No threshold moved.
THRESHOLDS_VERSION = "1.8"

#: linearisation is only meaningful for peak shifts well inside the peak; past
#: this fraction of FWHM the answer is "re-detect the peak", not "shift it"
VALIDITY_RADIUS_FWHM = 0.4
#: below this local R² the five-term shape basis does not explain the region's
#: misfit, so its coefficients are not reported as causes
MIN_REGION_R2 = 0.5
#: local reduced χ² below which a region is simply fitted — there is no misfit
#: to attribute, and the R² gate (which would legitimately read ~0 on pure
#: noise) is not applied
MIN_REGION_CHI2_RED = 1.5
#: condition number of the **scale-normalised** Gram matrix above which the
#: region's basis is too collinear for the individual coefficients to be
#: separable.  Normalising matters: the raw Gram's condition is dominated by
#: the units of ∂Ω/∂pos vs Ω and says nothing about resolvability.
MAX_GRAM_CONDITION = 1e4
#: |coef|/esd needed before a coefficient is called nonzero
MIN_COEF_SIGNIFICANCE = 3.0
#: how many times more unexplained variance the runner-up template must leave
#: before the best one is called distinguishable.  Compared on *residual* sums
#: of squares, not on R² differences: every template scores R² ≈ 0.99 against
#: a clean trend, so absolute R² gaps are ~10⁻³ and meaningless, while the
#: residual ratio spans 1.0 (indistinguishable) to 10 (decisive) on the same
#: data.
SEPARABILITY_MIN_SS_RATIO = 2.0

#: March-Dollase texture diagnostic (:mod:`.texture`).  ``TEXTURE_MIN_R2`` is the
#: fraction of the intensity misfit a single-axis March model must explain before
#: texture is *detected*; ``TEXTURE_MIN_STRENGTH`` the departure of the fitted r
#: from 1 (r ≈ 1 is no texture however good the "fit"); ``TEXTURE_MIN_REFLECTIONS``
#: the number of intensity-bearing reflections below which the pattern is not
#: enough to point at an axis.
TEXTURE_MIN_R2 = 0.5
TEXTURE_MIN_STRENGTH = 0.03
TEXTURE_MIN_REFLECTIONS = 4

#: Stephens anisotropic-strain diagnostic (:mod:`.strain`).  ``STRAIN_MIN_R2``
#: is the fraction of the width misfit a Laue-allowed Stephens model must
#: explain *beyond an isotropic strain* before anisotropy is called;
#: ``STRAIN_MIN_ANISOTROPY`` the broadest/narrowest Λ ratio below which the
#: answer is "isotropic" however good the fit (the texture diagnostic's r ≈ 1
#: escape, one model down); ``STRAIN_MIN_REFLECTIONS`` the floor on
#: intensity-bearing reflections — the effective floor is one more than the
#: Laue class's pattern count, so a triclinic phase needs sixteen.
#: ``STRAIN_MAX_GRAM_CONDITION`` is the scale-normalised Gram condition beyond
#: which the individual patterns are reported unresolved: the headline
#: "directional by N×" survives that, the per-pattern breakdown does not.
STRAIN_MIN_R2 = 0.5
STRAIN_MIN_ANISOTROPY = 1.3
STRAIN_MIN_REFLECTIONS = 6
STRAIN_MAX_GRAM_CONDITION = 1e3

#: Abstained-branch honesty (WP-1054) — all four measured on the LaB₆ misfit-
#: injection fixtures (tests/test_fitreport_layers.py), 2026-08-12.
#:
#: ``reindex_or_recheck_cell`` is emitted when at least
#: ``REINDEX_MIN_FAR_FRACTION`` of the *misfitting* regions (with an absolute
#: floor of ``REINDEX_MIN_FAR_REGIONS``) fail the validity radius — the
#: position failure must be *widespread*, which is what separates a wrong
#: cell/gross calibration from a couple of locally-bad regions.  A count
#: fraction, deliberately not a χ² share: shares proved unstable under a
#: background refit (the +0.4 % cell state measures far-region share 0.192
#: unrefined but 0.049 after one background stage — indistinguishable from
#: the 0.043 of a state whose failures are saturated-fit artefacts), while
#: the count fraction reads 0.60/0.73 on those same two wrong-cell states,
#: 0.60 on a mature broad-peak gross zero (Rwp 0.14 — the old ``rwp > 0.2``
#: arm missed it), 0.71 on a gross zero beside a real impurity, against 0.33
#: on the artefact state and 0.00 on every control (all 2026-08-12, the LaB₆
#: misfit-injection fixtures).
REINDEX_MIN_FAR_FRACTION = 0.5
REINDEX_MIN_FAR_REGIONS = 3
#: A strong unmatched observed peak with an ``unmatched_calc`` partner within
#: this window is a *displaced pair* (the model's line beside the observed one),
#: not an impurity candidate — consulted only when validity-radius failures
#: exist.  Measured pair distances on the +0.4 % cell state: 0.12–0.82°;
#: a genuinely foreign line sat 1.05–1.18° from any partner.
SHIFT_PAIR_WINDOW_DEG = 1.0
#: An unmatched observed peak within this many (pattern-median) FWHM of a
#: calculated position is shape/position misfit of that reflection, not a new
#: line — the broad-peak regime, where the fixed 0.08° matching tolerance is
#: far smaller than the peak itself.  Measured: residual lobes at 0.1–0.5 FWHM
#: from their tick on broad data; a genuine impurity at 12–14 FWHM.
SHIFT_TICK_PROXIMITY_FWHM = 1.0
#: ``add_impurity_phase`` confidence when *every* strong unmatched peak matches
#: the position-error evidence — deliberately below the reindex action's 0.4,
#: because on that evidence the phase is the less likely explanation.
IMPURITY_SHIFT_CAP = 0.3
#: how far below a coexisting ``add_impurity_phase`` call the texture action is
#: capped: an un-modelled foreign peak leaks into the per-reflection extraction
#: and can manufacture the texture signature (measured: a pure impurity
#: injection scored a phantom (1,0,1) axis at R²=0.66, outranking the impurity
#: call at 0.40), so the detection must never outrank its likely cause.
TEXTURE_IMPURITY_MARGIN = 0.05
#: ``collect_better_data`` on a resolution-limited abstention (WP-1106).  A
#: level, not a measurement: the abstention evidence cannot separate
#: instrumental breadth (better data exists — finer optics, longer counting)
#: from specimen breadth (no re-measurement sharpens nanocrystalline
#: broadening), so the confidence says "the data, not the model, is this
#: report's limit" without pretending to know which side of that fork the
#: specimen is on.  Above :data:`IMPURITY_SHIFT_CAP`, because on this state
#: the data-quality reading must outrank a phantom phase.
COLLECT_DATA_CONFIDENCE = 0.5

#: Le Bail gap (WP-1057) — the structural-vs-profile triage statistic.
#: ``LEBAIL_GAP_CYCLES`` partition cycles at the frozen converged state: the
#: fixed point is reached by cycle 2-3 on the LaB₆ pore-proxy fixture
#: (Rwp_lebail 0.01713 after one cycle, 0.01700 from two onward, 2026-08-12),
#: so 5 is margin, not tuning.  ``LEBAIL_GAP_NOTABLE`` is the ratio above
#: which the summary quotes the gap; measured separation on the same fixtures:
#: 2.38 on the pore proxy (guest scatterer in truth only — intensity model
#: wrong) against ≤ 1.00 on every position/profile control (+0.4 % cell 1.00,
#: broad+0.05° zero 1.00, broad clean 1.00, sharp+0.008° zero 0.96) and 0.79
#: on the converged clean fit — the partition is *not* a noise-floor
#: estimator (its net = max(y_obs − bkg, 0) clip and profile-share weighting
#: put its own floor above a converged least-squares fit), which is why the
#: notable test is on the ratio, never on rwp_lebail alone.
LEBAIL_GAP_CYCLES = 5
LEBAIL_GAP_NOTABLE = 1.5

#: Resolution-limited abstention flavour (WP-1057) — classification of an
#: abstention *already decided* by the maturity gate; nothing here moves any
#: threshold that decides one.  The classifier defers to the position-family
#: evidence first: when validity failures are widespread (the same counts the
#: reindex action fires on, ``REINDEX_MIN_FAR_*``), the abstention reads as
#: model error however collinear the rest — necessary, because a wrong cell
#: fails the Gram gate widely too (measured: the +0.4 % cell state fails gram
#: in 8 of its 10 failing regions).  Past that, resolution-limited requires
#: the failures to be collinearity and nothing else: gram failures in at least
#: ``RESOLUTION_LIMITED_MIN_FRACTION`` of the failing regions, at least
#: ``RESOLUTION_LIMITED_MIN_REGIONS`` regions failing *only* gram, and those
#: carrying median local R² ≥ ``RESOLUTION_LIMITED_MIN_R2`` — the basis
#: *explains* the misfit; its edit directions are indistinguishable on merged
#: peaks.  Measured (LaB₆ fixtures, 2026-08-12): broad peaks + 0.05° zero —
#: gram 12 of 12 failing, 5 gram-only at median R² 0.957 → resolution-limited;
#: the +0.4 % cell control abstains on the immature-Rwp arm (0.72) and past it
#: would offer 1 gram-only region, failing both floors.
RESOLUTION_LIMITED_MIN_FRACTION = 0.5
RESOLUTION_LIMITED_MIN_REGIONS = 3
RESOLUTION_LIMITED_MIN_R2 = 0.9

#: Contents-type intensity signature (WP-1057) — the summary clause naming
#: incoherent intensity misfit.  Fires when intensity carries at least
#: ``CONTENTS_MIN_INTENSITY_SHARE`` of the misfit, *no* angular template
#: explains it (best template R² < ``CONTENTS_MAX_TEMPLATE_R2`` — scale and
#: ADP errors are angular trends, this is their negation), and the per-region
#: relative intensity errors alternate in sign (at least
#: ``CONTENTS_MIN_REGIONS`` significant coefficients with the minority sign
#: at least ``CONTENTS_MIN_SIGN_MINORITY`` of them) — structure-factor
#: interference, the signature of an un-modelled scatterer, which a scale or
#: displacement error cannot produce.  Measured (LaB₆ pore proxy — guest O at
#: the 1b site in truth only, 2026-08-12): share 0.83, best template R²
#: 0.011, 8 significant coefficients split 5+/3−; every position/profile
#: control measures share 0.00, and the +0.4 % cell state's 4 significant
#: coefficients are single-sign.
CONTENTS_MIN_INTENSITY_SHARE = 0.5
CONTENTS_MAX_TEMPLATE_R2 = 0.3
CONTENTS_MIN_REGIONS = 4
CONTENTS_MIN_SIGN_MINORITY = 0.25

#: Background evidence (WP-1055) — the comment thresholds of
#: :class:`BackgroundEvidence`.  They decide where the *summary* starts
#: talking and where an action may be emitted; the section publishes every
#: number either way, because a threshold here is context and not a
#: publish/withhold switch.  The two failure modes are measurably orthogonal
#: (LaB₆ fixtures, `tests/test_background_auto.py`, 2026-08-12): a 1°-knot
#: unpenalized spline absorbs R² 0.46 at off-region d 2.03, a hump fitted with
#: a 2-term Chebyshev leaves off-region χ²_red 12.6 at d 0.19 and absorbs
#: 0.02, and a converged clean fit reads 0.02 / 0.97 / 2.00 — so neither gate
#: can fire on the other's failure and the clean control fires neither.
#:
#: ``BACKGROUND_ABSORPTION_NOTABLE`` is deliberately
#: :data:`~rietx.strategy.staged.BACKGROUND_ABSORPTION_GUARD` itself rather
#: than a second number: the report and the ``BACKGROUND_ABSORPTION``
#: diagnostic describe one measurement, and a report recommending a stiffer
#: background while the guard stays silent would be two verdicts on it.
#:
#: The stiff/wavy direction needs **both** of the other two, and the pairing
#: is the point.  ``OFF_REGION_CHI2_RED_HIGH`` says there is misfit between
#: the peaks at all — the same number and the same question as
#: :data:`MIN_REGION_CHI2_RED` one region-type over — but it is a σ-scaled
#: quantity, so a file with pessimistic esds would sit under it and one with
#: optimistic esds over it for no physical reason.  ``OFF_REGION_DW_LOW``
#: is scale-free (a ratio of sums of the same residuals), so it cannot be
#: moved by mis-scaled esds, and requiring it too is what stops the magnitude
#: gate from reading a weighting error as a background error.  Measured
#: d: 0.18-0.44 across three under-flexible backgrounds against 1.99-2.04 on
#: every converged control.
BACKGROUND_ABSORPTION_NOTABLE = BACKGROUND_ABSORPTION_GUARD
OFF_REGION_CHI2_RED_HIGH = 1.5
OFF_REGION_DW_LOW = 1.0

#: Identifiability section (WP-1056) — all three measured on the LaB₆
#: fixtures (tests/test_fitreport_layers.py, 2026-08-12; the spike table is
#: in the WP handover).
#:
#: The exchange discriminator is deliberately two conditions, because the
#: measured fact is that either alone is noise.  Projection R² of a held
#: column onto the fitted span is a property of the design matrix over the
#: sampled range: the E2 fixture (planted −0.02 mm displacement absorbed by a
#: compensating zero at 128 σ) and its clean reference (zero at 1.6 σ) both
#: measure R² = 0.999945, identical to six decimals.  And a significant
#: partner with a *low* R² is just a fitted parameter — nothing to exchange
#: with.  ``EXCHANGEABLE_MIN_R2`` sits between the exchangeable aberrations
#: (held displacement 0.9999, held transparency 0.9729 on the full window)
#: and the partially-absorbed Biso rows (0.65-0.76, whose loadings name no
#: nulled partner anyway), and equals Prince's "worthwhile at |ρ| > 0.95"
#: read as a pair R² (0.95² ≈ 0.90).
#: ``EXCHANGE_PARTNER_MIN_SIGNIFICANCE`` sits between the compensating
#: partner (127.7 σ from its null on E2) and every converged control
#: (1.2-1.6 σ); the esd already carries the Bérar-Lelann inflation, which
#: makes the ratio conservative.
EXCHANGEABLE_MIN_R2 = 0.90
EXCHANGE_PARTNER_MIN_SIGNIFICANCE = 5.0
#: What a swap outcome *licenses* — a reading aid the exchange clause quotes,
#: gating nothing (the :data:`TRAJECTORY_MAX_ACTIONS` precedent).  Read
#: against :class:`RivalComparison`.chi2_ratio orientation-neutrally — the
#: losing rival's χ² over the winning rival's, i.e. max(r, 1/r): at or above
#: this the data has chosen and the winning rival's fit is the answer, quoted
#: without caveat; below it the pair is genuinely unresolved and the honest
#: moves are protocol (a calibrant-fixed zero, a wider window) or the declared
#: stand-off.  The value is the report eval's registered decision band
#: (tests/eval_report_agent/PROTOCOL.md § Decision bands), measured on both
#: sides: real SRM 660c with a knocked displacement separates at 1.1679
#: (decisive), while the two tie states measure 1.0075 and 1.0001 (inside the
#: [0.99, 1.01] tie band).  Deliberately not a field on
#: :class:`RivalComparison` — the package states the reading rule and never
#: applies it (WP-1063's no-``decisive`` fence).
RIVAL_DECISIVE_MIN_CHI2_RATIO = 1.10
#: A soft mode earns a summary sentence only below this eigenvalue of the
#: unit-column Gram (for a pair, 1 − |ρ|).  Prince's |ρ| > 0.95 (eigenvalue
#: 0.05) is the citable "worthwhile" line, but it cannot be the *comment*
#: threshold: the TCHZ u/v/w family is collinear on every finite window —
#: measured, the clean full-range control's softest mode is the u/v/w
#: combination at 1.21e-02 (its worst *pair* only 0.9465 — Watkin's point
#: that the combination is worse than any pair shows), against 6.68e-04 for
#: the same mode on a 20-56° window.  The threshold sits between those two;
#: the carrier keeps the softest modes whatever their eigenvalues, so
#: nothing below comment level is lost.
SOFT_MODE_NOTABLE_EIGENVALUE = 3e-3

#: a fit worse than this is "immature": Layer 1 abstains from parameter-level
#: statements entirely
MATURITY_MAX_RWP = 0.35
#: total χ² share carried by misfitting regions below which there is nothing
#: worth attributing (a converged fit always has a region or two over the
#: noise threshold by chance — that is not grounds to abstain)
MATURITY_MIN_MISFIT_SHARE = 0.2
#: fraction of the *misfitting* χ² that must sit in gate-passing regions;
#: below it, most of what is wrong cannot be read reliably ⇒ abstain
MATURITY_MIN_EXPLAINED_FRACTION = 0.4


# ----------------------------------------------------------------------
# Layer 0
# ----------------------------------------------------------------------
class Region(Base):
    two_theta_lo: float
    two_theta_hi: float
    local_rwp: float
    chi2_share: float          # fraction of total Σw·Δ² inside this region
    max_abs_delta_over_sigma: float
    n_reflections: int


class UnmatchedPeak(Base):
    """One Layer-0 peak-accounting row; the list is ``FitReport.unmatched``,
    and its counts alone (no positions) ride on
    :class:`StageReport` as ``n_unmatched_obs``/``n_unmatched_calc``.
    """

    two_theta: float
    height_over_sigma: float
    kind: str  # "unmatched_obs" (no calc tick nearby) | "unmatched_calc"


class SatelliteCandidate(Base):
    """One candidate propagation vector, scored against the unexplained peaks.

    ``matched`` is how many of the report's unexplained observed peaks fall
    within :data:`VALIDITY_RADIUS_FWHM` of a satellite position generated from
    this k — the *report's own* radius, not a second one, so the arm cannot be
    tuned independently of the layer whose peaks it reads.

    **This is a ranking and never a singleton** (the indexing rule, root
    ``CLAUDE.md``): the whole list is published in order, and a k at the top of
    it is a hypothesis worth testing rather than an answer.  ``matched`` is a
    count of *positions*, which is the only thing this rung measures — no
    intensity is computed anywhere, because computing one would need a moment.

    ``cdml`` is the CDML k-label a user would cross-check against MAGNDATA or
    ISODISTORT, and is ``None`` until those tables are sourced
    (``crystallography.satellites.cdml_label``); ``vector`` — the plain
    spelling — is always there.
    """

    k: list[str]                 # three exact rationals, e.g. ["0", "0", "1/2"]
    name: str                    # positional, deterministic within a generator
    vector: str                  # "(0, 0, 1/2)"
    cdml: str | None = None
    #: how many satellite positions this k puts inside the fitted range
    n_satellites: int = 0
    #: arms of the star of k — how many distinct directions the powder averages
    star_size: int = 1
    #: False when 2k is a reciprocal-lattice vector, i.e. −k ≡ k (the FullProf
    #: manual's ±k rule, which is centring-aware)
    minus_k_distinct: bool = True
    matched: int = 0
    #: ``matched`` over the number of unexplained peaks; 0.0 when there are none
    matched_fraction: float = 0.0
    #: the largest |Δ2θ| among the matched peaks, in degrees; None when none
    #: matched
    worst_offset_deg: float | None = None


class SatelliteEvidence(Base):
    """Does the unexplained intensity index as satellites of a small set of k?

    The arm WP-1326 adds to the unexplained-intensity report, and the whole of
    what this rung can say: **a satellite is a position**.  No moment, no
    magnetic form factor and no magnetic symmetry enters, which is exactly why
    a user can run it before deciding whether the hypothesis is worth the model.

    Two statements it must always be able to make, because both are cases where
    the ranking below means nothing:

    * ``excess_on_nuclear_lines`` — the residual peaks sit *on* calculated
      reflections.  With k = 0 the satellites coincide with the nuclear lines,
      so a Le Bail extraction absorbs the magnetic intensity into the nuclear
      intensities: a k = 0 structure and a nuclear misfit look alike here and
      this route cannot separate them.  What does is a pattern of the same
      specimen above its ordering temperature (WP-1329 makes that a series).
    * ``excess_on_absent_lattice_lines`` — they sit on reciprocal-lattice
      points a glide or screw absence of the *assumed* space group forbids.
      The fitted model cannot put intensity there, but four causes can and
      this arm separates none of them: a true nuclear group lacking the
      operation (the assumed group is too high), λ/2 contamination, an
      impurity line on the point, and — on neutrons only — a k = 0 magnetic
      structure, whose axial structure factor can obey the complementary
      absence rule (Gallego et al. 2012, *J. Appl. Cryst.* **45**, 1236).
      What the count does settle is that these peaks need no k, so they are
      not scored.  Measured on the Cr₂WO₆ 4 K pattern, whose two strongest
      residual peaks are the absent (0 0 1) and (1 0 2).
    * ``radiation`` — on an X-ray histogram a satellite is a **superstructure**
      reflection, not magnetism.  The positions are the same and the inference
      is not.

    ``candidates`` is empty when there was nothing to score, and that is not a
    result about the specimen.  A good pattern can also score nothing because
    the candidate set is *enumerated*: an incommensurate k is outside it by
    construction, and so is every commensurate k the generator does not list.
    """

    phase_index: int
    #: ``"neutron"`` or ``"xray"`` — read off the compiled phase's amplitude
    #: (a bound coherent scattering length means neutrons), never assumed
    radiation: str
    #: positive residual peaks the arm sorted, before any of them was scored
    n_residual_peaks: int = 0
    #: peaks at neither of the two below — the ones the ranking was scored
    #: against, because they are the only ones that need a satellite
    n_unexplained: int = 0
    #: positive residual peaks that sit on a **calculated reflection** — a
    #: nuclear misfit, or a k = 0 structure, and this route cannot tell them
    #: apart
    excess_on_nuclear_lines: int = 0
    #: positive residual peaks that sit on a **reciprocal-lattice point the
    #: assumed space group forbids** — a group set too high, λ/2, an impurity
    #: line, or (neutrons) a k = 0 magnetic structure; the note names the
    #: causes this arm cannot separate, and none of them needs a k
    excess_on_absent_lattice_lines: int = 0
    #: the k this phase already declares, if any; the arm still scores, because
    #: "does another k explain the rest" is a question a declared one does not
    #: answer
    declared_k: list[str] | None = None
    #: which generator produced the candidate set (issue #257 A1)
    generator: str = ""
    candidates: list[SatelliteCandidate] = Field(default_factory=list)
    #: the sentences above, rendered — always non-empty
    note: str = ""


class BackgroundEvidence(Base):
    """What the background is doing to the numbers a consumer reads (WP-1055).

    Model-free Layer-0 evidence, with one number carried from fit time.  The
    section exists because the two background failure modes are both invisible
    in everything else the report says, and they fail in *opposite* directions:

    **Too flexible** — the background imitates the peaks, biasing ADPs up and
    scales (hence QPA fractions) down **while Rwp improves**.  The one failure
    mode that makes every statistic an agent reads look better.
    ``absorption`` is the detecting statistic: per structural parameter, the
    block projection R² of its Jacobian column onto the background column span
    (:class:`~rietx.schemas.results.Identifiability`).  Pairwise ρ cannot see
    it — measured ~0.2 per coefficient while the block absorbed ~46 %.  Every
    screened pair is reported, not just the ones over
    :data:`BACKGROUND_ABSORPTION_NOTABLE`, because the number is the evidence
    and the threshold is only where the comment starts.  ``None`` (rather than
    empty) when the result carried no Jacobian-time measurement at all.

    **Too stiff** — smooth between-peak misfit, which Layer 0 is *structurally*
    blind to: its regions are peak clusters cut from ticks ∪ residual peaks, so
    misfit that lands between them lands in no region.  ``off_region_chi2_share``
    makes that remainder explicit and ``off_region_durbin_watson`` says whether
    it is systematic: d ≈ 2 is uncorrelated noise, d ≪ 2 is a run of same-sign
    residuals — the background shape fighting the data (Hill & Flack, 1987,
    J. Appl. Cryst. 20, 356).  It is pooled over the *contiguous* runs of
    off-region channels, never across the peak regions cut out between them: a
    difference taken over a gap is not a serial difference.

    **The pair, which is context and never a finding.**  ``rwp`` against
    ``rwp_background_subtracted`` (Toby, 2006, Powder Diffr. 21, 67 — his
    recommended variant) is how much of the headline number is background
    rather than fit; ``background_share`` is Σy_bkg/Σy_obs.  Measured, the
    honest number is the one that carries the information: a sharp LaB₆ fit
    and one under 0.6° of broadening both report Rwp **0.0137**, while
    background-subtracted they read 0.0490 and 0.0766 (background share 0.89
    in both, 2026-08-12).  The pair is therefore published unconditionally and
    is deliberately **not** a summary trigger — every background-dominated
    pattern crosses any useful threshold on it (ratio 3.6 and 5.6 on those two
    *converged* controls), so a trigger would be a sentence on every lab fit.
    Read it wherever a raw Rwp is about to be quoted; the agent skill §4 says
    where in the order.
    """

    rwp: float
    #: Toby's background-subtracted variant; None when the result carried no
    #: background curve to subtract
    rwp_background_subtracted: float | None = None
    #: Σ y_background / Σ y_obs over the fitted channels
    background_share: float = 0.0
    #: share of total χ² sitting in channels no Layer-0 region covers.
    #: Published because the WP asked for the remainder to be explicit, and
    #: **not** a detector: measured, it tracks the off-region *channel count*
    #: rather than the misfit (0.89 on a converged clean fit, 0.24 on the
    #: worst too-stiff background, where the peaks are misfitted too).  The
    #: magnitude question is ``off_region_chi2_reduced``.
    off_region_chi2_share: float = 0.0
    #: mean (Δ/σ)² over those channels — ≈1 when they are fitted to the noise.
    #: Measured 0.97/1.02 on converged controls against 4.6-12.6 on
    #: under-flexible backgrounds
    off_region_chi2_reduced: float = 0.0
    #: Durbin-Watson d over those channels, pooled within contiguous runs;
    #: None when too few of them are adjacent to difference
    off_region_durbin_watson: float | None = None
    off_region_points: int = 0
    #: path → block-projection R² for every screened structural parameter;
    #: None when nothing measured it (see the class docstring)
    absorption: dict[str, float] | None = None
    #: the largest ``absorption`` entry and whose it is — the headline, so a
    #: consumer need not sort the table to branch on it
    worst_absorption: float = 0.0
    worst_absorption_path: str | None = None
    #: explicit :class:`~rietx.schemas.instrument.HumpComponent` terms this fit
    #: declared — a **projection** of
    #: :attr:`~rietx.schemas.results.RefinementResult.n_background_components`,
    #: never a second count, so the section and the result cannot disagree.
    #: That field and not ``n_extra_components``, which counts *every* declared
    #: component: since WP-1103 the seam also admits a
    #: :class:`~rietx.schemas.instrument.PeakComponent`, which is a declared
    #: sharp reflection and grants no background flexibility at all.  Stated
    #: here because it is the other half of "how flexible was the background":
    #: the absorption table says what it could imitate, this says with how many
    #: free peaks (3N parameters, positions unconstrained).  Its ``None`` is the
    #: result's own and means the same thing — nothing counted, as against 0,
    #: which means none was declared.  ``absorption`` above carries the
    #: identical distinction one field over, and for the identical reason.
    n_peaks: int | None = None


class ExchangeFinding(Base):
    """One held parameter's exchange assessment (WP-1056).

    The carrier row (``held``/``r2``/``partners``, measured at fit time —
    :class:`~rietx.schemas.results.ExchangeRow`) plus the report's half of
    the two-condition discriminator: ``partner`` is the most-loaded fitted
    partner with a *defined null* (the aberration corrections, identity at
    zero — :data:`~rietx.optimize.identifiability.NULL_IDENTITY`), and
    ``partner_significance`` is |value − null| / esd from the stored result.
    A row whose loadings name no nulled partner carries ``partner = None``
    and can never be ``exchangeable`` — a cell edge or a scale has no null
    the data could be accused of failing to distinguish, so asserting an
    exchange there would be a confident statement with no significance half.

    ``exchangeable`` is the verdict the summary clause and the agent skill's
    reading share (:func:`~rietx.report.identifiability.is_exchangeable`):
    the fitted partner is significantly away from its null *and* the held
    parameter's column is reproducible in the fitted span, so the data
    cannot say which of the two is the physical cause — the verdict this
    licenses is ``ambiguous``, never a confident singleton.
    """

    held: str
    r2: float
    partners: dict[str, float] = Field(default_factory=dict)
    partner: str | None = None
    partner_null: float | None = None
    partner_value: float | None = None
    partner_esd: float | None = None
    partner_significance: float | None = None
    exchangeable: bool = False


class IdentifiabilityEvidence(Base):
    """Parameter-space evidence beside the esd-qualifying statistics (WP-1056).

    The esd trio is quoted **together and raw** on Schwarzenbach et al.'s
    (1989, Acta Cryst. A45, 63) Recommendation 8 grounds: scaling variances
    by GoF² is "highly questionable", so the package reports the ingredients
    — raw χ²_red, the Bérar-Lelann inflation the quoted esds already carry
    (dividable back out), and Durbin-Watson — and lets the consumer decide
    what the esds mean.  ``delta_r_slope``/``delta_r_intercept`` compress the
    δR normal-probability plot (Abrahams & Keve, 1971, Acta Cryst. A27, 157;
    "a more powerful descriptor than R" per Schwarzenbach) to two numbers:
    sorted Δ/σ against normal quantiles reads slope ≈ 1 and intercept ≈ 0
    when the residuals are Gaussian on the stated σ (measured 1.004/−0.0004
    on the clean control), slope > 1 when σ is underestimated, and a bent
    tail shows up as the fit's |slope − 1|.

    ``top_correlations``/``soft_modes`` are carried from fit time
    (:class:`~rietx.schemas.results.Identifiability`); ``None`` here means
    *not measured* — a replay or a pre-WP-1056 result — never "well
    conditioned".  ``exchanges`` assesses every carried exchange row; the
    summary speaks only for rows where ``exchangeable`` is true.
    """

    chi2_reduced: float
    esd_inflation: float | None = None
    durbin_watson: float | None = None
    delta_r_slope: float | None = None
    delta_r_intercept: float | None = None
    top_correlations: list[CorrelationPair] | None = None
    soft_modes: list[SoftMode] | None = None
    exchanges: list[ExchangeFinding] | None = None


class LeBailGap(Base):
    """Structural-vs-profile triage: the Rietveld Rwp against an evaluate-only
    Le Bail partition of the *same* converged state (WP-1057; the Layer-0
    inventory item of DESIGN.md § Outputs).

    **Convention.**  ``rwp_lebail`` is measured by running
    :meth:`~rietx.model.forward.CompiledModel.lebail_update` for
    ``n_cycles`` with θ frozen at the converged values — background, cell,
    zero, profile all held; only the per-hkl intensities move, seeded flat.
    No refinement runs, so this is the cheapest description the *positions
    and profile* alone support, not a Le Bail fit (a fit would also relax
    the background and cell).  The partition is not a noise-floor estimator
    either: its ``max(y_obs − bkg, 0)`` clip and profile-share weighting
    leave it above a converged least-squares fit (measured 0.0172 against a
    converged Rwp of 0.0137 on clean LaB₆ data), which is why ``ratio`` — not
    ``rwp_lebail`` — is the statistic.

    **Reading it.**  ``ratio`` ≫ 1 means the partition, free to reassign
    every intensity, removes most of the misfit: every line is indexed and
    the profile is right — the *intensity model* (structure, contents,
    occupancies) is what is wrong, and phase ID is safe at any absolute Rwp.
    Measured on the LaB₆ pore-proxy fixture (guest scatterer in the data
    only): 2.38, against ≤ 1.00 on every position/profile control — a wrong
    cell or zero displaces the partition's peaks identically, so the gap
    stays flat and cannot be confused with position error.  ``ratio`` ≲ 1
    says intensities are not where the remaining misfit lives — it never
    says the fit is good (both Rwp may be terrible together).
    """

    rwp_rietveld: float
    rwp_lebail: float
    #: rwp_rietveld / rwp_lebail — the triage number (see class docstring)
    ratio: float
    n_cycles: int


# ----------------------------------------------------------------------
# Layer 1
# ----------------------------------------------------------------------
#: the shape-derivative basis, in physical units per unit coefficient
BasisKind = Literal["intensity", "position", "width", "mixing", "asymmetry"]


class BasisCoefficient(Base):
    """One fitted shape-derivative amplitude, with its meaning spelled out.

    ``value`` units by kind: ``intensity`` is a *relative* intensity error
    (0.05 = the region's calculated peaks are 5 % too weak), ``position`` is
    Δ2θ in degrees (positive = observed sits at higher 2θ than calculated),
    ``width`` is ΔΓ in degrees, ``mixing`` is Δη (dimensionless), and
    ``asymmetry`` is Δ(S/L).
    """

    kind: BasisKind
    value: float
    stderr: float
    significant: bool          # |value| > MIN_COEF_SIGNIFICANCE · stderr
    #: this term's share of the region's *explained* misfit,
    #: (|aⱼ|·‖colⱼ‖)² normalised over the basis.  Statistical significance
    #: alone is not importance: at high counting statistics the second-order
    #: leakage of a peak shift into the width column (y(x−δ) ≈ y − δy′ + ½δ²y″)
    #: is significant but carries a per-cent-level share, and confidence must
    #: reflect that.
    share: float = 0.0


#: the per-region gates, closed: significance, explanatory power,
#: resolvability, linearisation validity.  The global maturity gate abstains
#: the whole layer and so has no per-region entry.  Adding a gate is a minor
#: event in ``THRESHOLDS_VERSION`` (the gates/vocabulary contract).
GateCode = Literal["no_significant_misfit", "local_r2",
                   "gram_condition", "outside_validity_radius"]


class GateFailure(Base):
    """One refused per-region gate: a stable code beside the formatted evidence.

    ``code`` is what a consumer branches or groups on; ``message`` carries the
    measured numbers and is display-only.  Until WP-1003 the entries were the
    formatted strings alone, and every consumer that needed the gate's *name*
    — the package's own abstention reader included — recovered it by parsing
    the prefix back out (``Diagnostic.where``'s gap, one layer down).
    """

    code: GateCode
    message: str


class RegionAttribution(Base):
    """What a locally-linear model says is wrong in one region.

    ``gates_passed`` is the *only* field a consumer should branch on: when it
    is False the coefficients are reported for transparency but must not be
    read as causes.  ``gate_failures`` names which gate(s) refused.
    """

    two_theta_lo: float
    two_theta_hi: float
    n_reflections: int
    chi2_share: float
    mean_two_theta: float
    mean_fwhm: float
    coefficients: list[BasisCoefficient] = Field(default_factory=list)
    r2: float                            # misfit variance explained
    gram_condition: float
    #: local reduced χ²; ≤ MIN_REGION_CHI2_RED means this region is already
    #: fitted to the noise, so there is nothing to attribute (which is *not*
    #: the same as "the basis failed to explain it")
    chi2_reduced: float = 0.0
    has_significant_misfit: bool = True
    gates_passed: bool
    gate_failures: list[GateFailure] = Field(default_factory=list)


class TrendTemplate(Base):
    """One angular-dependence template fitted across regions.

    ``name`` identifies the physics, and for **position** the physics depends
    on the geometry, so which names can appear does too
    (:data:`~rietx.report.layer1.POSITION_TEMPLATES`): ``constant``→zero shift
    and ``tan_theta``→cell error everywhere; ``cos_theta``→specimen
    displacement and ``sin_2theta``→transparency on a flat plate;
    ``sin_2theta``→along-beam and ``cos_2theta``→across-beam capillary
    displacement (McCusker eq 4) on ``debye_scherrer``.  Width:
    ``inv_cos_theta``→size, ``tan_theta``→strain.  Intensity:
    ``sin2_over_lambda2``→ADP.
    """

    name: str
    coefficient: float
    stderr: float
    r2: float


class TrendAnalysis(Base):
    """hkl-grouped angular trends that per-region views structurally miss.

    ``max_template_collinearity`` is the largest |correlation| between any two
    templates *over the angular range actually sampled*.  Near 1 the templates
    are not separable there (the Williamson-Hall problem for size/strain, and
    zero/displacement/cell over a short 2θ range) — the report says so instead
    of returning a confident singleton.
    """

    observable: Literal["position", "width", "intensity"]
    n_regions_used: int
    templates: list[TrendTemplate] = Field(default_factory=list)
    max_template_collinearity: float = 0.0
    #: residual sum-of-squares of the runner-up template over that of the
    #: best one; > SEPARABILITY_MIN_SS_RATIO ⇒ the best template is genuinely
    #: distinguishable on this data
    separability_ratio: float = 0.0
    separable: bool = True
    #: share of the pattern's total χ² this observable accounts for, summed
    #: over regions.  Drives how confident the derived actions may be: a term
    #: explaining 2 % of the misfit is not a headline no matter how many σ
    #: it stands at.
    misfit_share: float = 0.0


class TextureAnalysis(Base):
    """Single-axis March-Dollase preferred-orientation diagnostic, per phase.

    ``detected`` is the *only* field to branch on.  ``best_axis`` is evidence,
    not a verdict (WP-1054): it always carries the best-scoring crystallographic
    direction (integer hkl) whenever enough reflections informed the fit, so a
    consumer reading a sub-threshold ``r2`` can still see *which* axis got that
    score.  ``march_coefficient`` is the fitted r on that axis (< 1 or > 1 →
    platy or needle, the sense depending on geometry — see
    :mod:`rietx.model.preferred_orientation`).  ``r2`` is the fraction of
    the intensity misfit that model explains.  ``runner_up_axis`` is the best
    *non-equivalent* alternative — when its ``runner_up_r2`` is close to ``r2``
    the axis is not cleanly resolved (distinct habits happen to fit similarly).
    ``caveat``, when set, names evidence elsewhere in the report that can
    manufacture this signature (currently: strong unmatched observed peaks —
    un-modelled intensity leaks into the per-reflection extraction, so an
    impurity can read as texture); a detection carrying a caveat is still a
    measurement of the residual, but not of the specimen.
    """

    phase_index: int
    best_axis: tuple[int, int, int] | None = None
    march_coefficient: float = 1.0
    r2: float = 0.0
    n_reflections_used: int = 0
    detected: bool = False
    runner_up_axis: tuple[int, int, int] | None = None
    runner_up_r2: float = 0.0
    caveat: str | None = None


class StrainAnalysis(Base):
    """Stephens anisotropic-strain (directional width) diagnostic, per phase.

    ``detected`` is the field to branch on: when True the phase's widths are
    *directional* — not a function of 2θ, which is what the size/strain trend
    templates already cover, but of hkl — and a Stephens block on it is worth
    declaring.  ``anisotropy`` is the fitted broadest/narrowest Λ ratio with
    ``broadest_hkl``/``narrowest_hkl`` naming the directions, so the finding
    reads as "widths along (00l) are 3.4× those along (hk0)".  Its ceiling
    value (10⁶) means the fit wants *zero* strain along ``narrowest_hkl``, so
    the ratio is unbounded rather than measured; the hkl fields are ``None``
    when no two reflections carry enough leverage to contrast at all.

    The measurement is of the **specimen**, not of the residual: refining a
    ``microstrain`` block does not make ``detected`` go False, it makes the two
    agree (the anisotropy is still there — it is now modelled).  Suppressing a
    suggestion once the parameters are free is the Layer-2 strategy veto's job,
    not this field's.

    ``r2`` is measured against an **isotropic-strain** baseline, so it answers
    "how much of the width variation is directional", not "how much of it is
    strain" — a specimen that is uniformly too broad scores ~0 here and belongs
    to ``lor_strain`` instead.  ``n_patterns`` is the Laue class's number of
    independent S_HKL, and ``separable`` says whether those patterns are
    individually resolved over the sampled reflections: when it is False the
    ratio and the directions still stand but the per-pattern breakdown does
    not, so refine the block and read the fit, do not quote coefficients.
    """

    phase_index: int
    n_reflections_used: int = 0
    r2: float = 0.0
    anisotropy: float = 1.0
    broadest_hkl: tuple[int, int, int] | None = None
    narrowest_hkl: tuple[int, int, int] | None = None
    n_patterns: int = 0
    gram_condition: float = 0.0
    separable: bool = False
    detected: bool = False


# ----------------------------------------------------------------------
# Layer 2
# ----------------------------------------------------------------------
#: Closed, versioned action vocabulary.  Adding a member is a minor-version
#: change; changing a member's meaning is a breaking change.
ActionKind = Literal[
    "refine_zero_shift",
    "refine_sample_displacement",
    "refine_sample_transparency",
    "refine_capillary_offset_along_beam",
    "refine_capillary_offset_across_beam",
    "refine_cell",
    "refine_profile_widths",
    "refine_sample_size_broadening",
    "refine_sample_strain_broadening",
    "refine_axial_asymmetry",
    "refine_biso",
    "refine_preferred_orientation",
    "refine_scale",
    "add_impurity_phase",
    "increase_background_flexibility",
    "decrease_background_flexibility",
    "reindex_or_recheck_cell",
    "collect_better_data",
]

#: How a kind is carried out.  ``stage`` — one ``run_stage`` over the action's
#: globs.  ``index`` — a long-running search, not a stage, and the only kind
#: whose availability is a build feature.  ``advice`` — no verb; the note says
#: what to do instead.  The kind→``How`` mapping lives in ``report/apply.py``
#: (``RECIPES``, the one authority); this module only names the vocabulary so
#: :class:`SuggestedAction` can carry it typed.
How = Literal["stage", "index", "advice"]


class SuggestedAction(Base):
    """An advisory, typed suggestion.  **The strategy engine holds the veto.**

    ``expected_delta_chi2`` is the *predicted* χ² reduction from the linear model,
    and two things about it are load-bearing for anyone rendering it (measured in
    ``tests/test_report_apply.py``, WP-1012).  It is **one number per report, not
    per action**: :func:`~rietx.report.build_report` computes
    :func:`.layer2.estimate_delta_chi2` once and stamps it on every
    Layer-1-derived action, so it cannot rank or distinguish suggestions — the
    texture actions, whose evidence is per-reflection, carry ``None`` instead.
    And it is **not a bound on what applying the action achieves**: it bounds the
    misfit the linear model attributes inside the *gated* regions, while the
    refinement also moves regions that failed a gate and stretches no region entry
    covers (measured: 16.19 predicted against 16.33 observed for ``refine_cell``).
    ``predict_then_verify`` in :mod:`.layer2` measures the real one and rolls back
    if it disagrees.  ``vetoed_by`` is set when the staged plan already refines the
    parameter, or when a guard forbids it.

    ``execution`` is the recipe table's ``how`` (``report/apply.py``), stamped
    by :func:`~rietx.report.build_report` on every action it emits — the fact
    that separates an advice kind's ``parameter_paths: []`` *by design* from a
    bug.  It is a typed field beside the numbers because the same fact stated
    in prose reached agent context in 2 of 12 measured cells (WP-1065: agents
    pipe the response to a file and grep statistics back).  ``None`` marks an
    action that never went through ``build_report``.
    """

    kind: ActionKind
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    parameter_paths: list[str] = Field(default_factory=list)
    expected_delta_chi2: float | None = None
    alternatives: list[ActionKind] = Field(default_factory=list)
    two_theta_range: tuple[float, float] | None = None
    vetoed_by: str | None = None
    execution: How | None = None

    @property
    def active(self) -> bool:
        return self.vetoed_by is None


class FreedParameter(Base):
    """One parameter the fuller fit frees and the restricted fit held.

    ``t_ratio`` is (``value`` − ``held_at``)/``esd``: how far the parameter
    moved from where the restricted fit held it, in its own esd.  The esd is
    the fuller fit's, already Bérar-Lelann inflated.  ``held_at`` is ``None``
    where the restricted model has no such entry (a phase the fuller model
    adds), and for a coordinate DOF no coordinate row follows alone.
    ``t_ratio`` is ``None`` then and wherever the esd is.
    """

    path: str
    held_at: float | None = None
    value: float
    esd: float | None = None
    t_ratio: float | None = None


class FreedComparison(Base):
    """What freeing parameters bought, as ΔBIC with each one's t-ratio beside it.

    Built by :func:`~rietx.report.compare_freed` from two fits the caller ran
    (WP-1417, issue #270).  ``delta_bic`` is charged at ``n_effective`` =
    N/f², with f the **restricted** fit's ``esd_inflation``, which is the
    count :meth:`~rietx.Refinement.suggest` predicts at, so a prediction and
    its refit compare.  ``delta_bic_raw_n`` is the same at the channel count.
    Positive favours the fuller model.

    The pair is the point.  For one added parameter ΔBIC at N_eff is close to
    t² − ln N_eff, so the two agree when the residual's correlation has not
    moved between the fits.  At raw N a serially correlated residual lets
    ΔBIC bless a parameter its own esd puts within 1σ of zero: the issue's
    four fits gave +36 to +211 at t = 0.76-1.89.  **There is deliberately no
    verdict field**, on :class:`RivalComparison`'s precedent.
    """

    freed: list[FreedParameter]
    n_added: int
    n_points: int
    #: the unreduced Σw·Δ² :func:`~rietx.report.delta_bic` takes, which is
    #: each fit's ``Statistics.chi2`` times its own N − P
    chi2_restricted: float
    chi2_full: float
    esd_inflation: float | None = None
    n_effective: float
    delta_bic: float
    delta_bic_raw_n: float


class VerificationOutcome(Base):
    """Result of actually trying an action (predict-then-verify with rollback).

    ``accepted`` is the fractional χ² rule and nothing else.  ``comparison``
    rides beside it (WP-1417): the trial's ΔBIC at N_eff and each newly freed
    parameter's t-ratio, written by :func:`~rietx.report.predict_then_verify`
    alone.  ``None`` when there was no trial fit, when the action freed
    nothing that was not already free, or when a stage hold made the two fits
    stop being nested.
    """

    kind: ActionKind
    predicted_delta_chi2: float | None
    observed_delta_chi2: float
    accepted: bool
    reason: str
    comparison: FreedComparison | None = None


class RivalFit(Base):
    """One half of the swap: this parameter freed, its rival held at its null.

    ``held_at`` is the null identity, not the rival's fitted or knocked value,
    and that is the whole design.  The lazy converged state of the WP-1059 R1
    episode — zero free, displacement sitting at the −0.02 mm it was knocked
    to — is **neither** rival (its Rwp 0.09127 differs from the zero-only
    0.09361), so a comparison run against it answers a question nobody asked.

    ``n_free`` is here so the fairness claim can be checked rather than
    believed: the two fits differ by which member of the pair is free, never
    by how many parameters are, which is what lets the raw χ² be compared
    without an information criterion.
    """

    freed_path: str
    held_path: str
    held_at: float
    chi2: float
    rwp: float
    n_points: int
    n_free: int
    freed_value: float | None = None
    freed_esd: float | None = None
    #: the branch node this fit landed on, or None when history is disabled
    node_id: str | None = None


class RivalComparison(Base):
    """The swap the exchange clause names, measured (WP-1063).

    Two fits, each freeing one member of an exchangeable pair with the other
    held at its null.  **There is deliberately no ``decisive`` field.**  The
    numbers are the answer; whether a χ² ratio of 0.86 on 5332 points settles
    a question is the caller's judgement, and a report that made it for them
    would be the autopilot this package does not ship (the agent skill §1 —
    report and suggest inform, never drive).

    ``rivals`` is ordered: index 0 frees the finding's **held** candidate (the
    one the fit did *not* use), index 1 frees its fitted **partner**.
    ``chi2_ratio`` follows that order — ``rivals[0].chi2 / rivals[1].chi2`` —
    so a value below 1 says the parameter the fit held explains the pattern
    better than the one it refined.  Measured on real SRM 660c: 0.856
    (χ² 3.4890 freeing the displacement against 4.0752 freeing the zero), and
    the zero-only model biases *a* by +100 ppm.
    """

    rivals: list[RivalFit]
    chi2_ratio: float


#: which *kind* of abstention, for a consumer that branches (WP-1057).  One
#: alias, two users — :class:`FitReport` and its :class:`StageReport`
#: projection — because a second copy of a closed vocabulary is how the two
#: drift apart.
AbstentionKind = Literal["immature", "resolution_limited", "unreadable"]

#: active suggestions carried per trajectory rung.  A cap, not a filter: what
#: it drops is counted in ``n_actions_omitted``, because a silent cap reads as
#: "that was everything".  Five is above every count measured on the WP-1052
#: episode states (max 4 active) and on real 11-BM data (2).
TRAJECTORY_MAX_ACTIONS = 5


class StageReport(Base):
    """The report at one stage boundary, projected for delivery (WP-1058).

    :class:`FitReport` is what a *consumer that reads one state* needs; this is
    what a consumer reading **five** needs, and the difference is not detail —
    it is payload.  Measured at WP-1058 on the WP-1053 episode fixtures and
    real 11-BM data, a full FitReport serialized to 26–40 kB, so a five-stage
    trajectory of them was 130–190 kB against the 26 kB single report it
    accompanies, at 0.9–2.6 kB a rung for this projection (+26 % on that
    report).  Re-measured 2026-08-19 on the 4200-channel synthetic LaB₆
    fixture the gap is wider still: the full report is 111 kB — 89 kB of it
    the WP-1072 geometry table, which no rung carries — against 0.6–0.8 kB a
    rung, 3.5 kB for the whole five-rung trajectory, ~3 % of the report it
    ships beside.  It carries the numbers
    the agent skill §4 judges a fit on, the summary sentence every section's
    headline clause already lands in (by construction — see
    :func:`~rietx.report.build_report`), and the active suggestions
    themselves.

    Three things it deliberately does **not** do.  It does not re-type an
    action: ``actions`` holds :class:`SuggestedAction` verbatim, so there is
    one authority for what a suggestion is and the trajectory cannot describe
    one differently from the final report.  It does not carry curves, regions
    or per-region attribution — those are the *evidence* for statements the
    summary and the actions already make, and a rung is a pointer to a state
    worth asking about, not a substitute for asking.  And it does not drop
    anything silently: the two counts say what the cap and the strategy veto
    removed.

    ``actions`` is **active only**.  A vetoed suggestion at a stage boundary is
    the plan's own next stage answering it — the least informative thing a
    trajectory can repeat five times — while ``n_actions_vetoed`` still says
    how many there were.
    """

    #: the stage whose *end* this describes, by name (``StageResult.name``)
    stage: str
    rwp: float
    gof: float
    #: the FitReport's own summary, verbatim: the one string every section's
    #: headline clause lands in (identifiability exchange, Le Bail gap,
    #: contents signature, background comment, abstention reason)
    summary: str = ""
    abstained_reason: str | None = None
    abstained_kind: AbstentionKind | None = None
    #: active suggestions, ranked as the report ranked them, capped at
    #: :data:`TRAJECTORY_MAX_ACTIONS`
    actions: list[SuggestedAction] = Field(default_factory=list)
    #: active suggestions past the cap (0 whenever nothing was dropped)
    n_actions_omitted: int = 0
    #: suggestions the strategy veto marked inactive — what the plan you are
    #: running already covers
    n_actions_vetoed: int = 0
    #: Layer-0 peak accounting: observed peaks no tick explains (the impurity
    #: signature) and predicted ticks with no intensity under them.  Counts,
    #: not positions — ``actions[].two_theta_range`` carries the where
    n_unmatched_obs: int = 0
    n_unmatched_calc: int = 0
    #: ``lebail_gap.ratio`` — structural-vs-profile triage (None outside
    #: Rietveld mode, absent for cause)
    lebail_gap_ratio: float | None = None
    #: the two background triggers (WP-1055), and only those two: the
    #: too-stiff detector and the too-flexible one.  The Rwp /
    #: Rwp-background-subtracted pair is deliberately absent — measured, every
    #: background-dominated pattern crosses any useful threshold on it,
    #: converged ones included, so per rung it would be a sentence on every
    #: lab fit.  It is published unconditionally on the final FitReport, where
    #: a consumer reads it beside the raw Rwp it qualifies.
    off_region_chi2_reduced: float | None = None
    worst_absorption: float | None = None
    worst_absorption_path: str | None = None


#: How many of its own esds a moment must be before the report calls it
#: supported (WP-1327).  Three, and the choice is measured rather than
#: conventional: on the Cr₂WO₆ tutorial data the shipped acceptance protocol
#: (``tests/test_acceptance_magnetic.py``) gives |m|/σ = 0.07 at 150 K, above
#: the ordering temperature, and 35 at 4 K (an earlier stage list: 0.17 and
#: 44), so anything from about 1 to 10 separates them with room on both
#: sides, and 3 sits inside that range.  rietx's esds
#: are Bérar-Lelann-inflated, which makes this test *conservative* — the
#: factor is reported as ``Statistics.esd_inflation`` for a reader who wants
#: to divide it back out.
MOMENT_SUPPORT_SIGMA = 3.0

#: |rho| above which two magnetic sites' modulus DOFs (``moment.dof0``) are
#: read as a powder-degenerate pair (Q4/Q5 follow-up to WP-1327) rather than
#: two independently measured moduli.  0.95 is Prince's "worthwhile"
#: correlation bar (*Mathematical Techniques* 3rd ed. ch. 8, already quoted
#: beside :class:`~rietx.schemas.results.SoftMode`) — at or above it the two
#: parameters are, for practical purposes, one direction of the least-squares
#: problem, which is exactly ``isotropy.determinable_amplitudes``'s pre-fit
#: SVD-rank deficiency read off the *actual fitted* covariance instead: a
#: rank of 1 where 2 amplitudes were free is |rho| -> 1 between them, not a
#: separate criterion.
MOMENT_PAIR_RHO_MIN = 0.95


class MomentEvidence(Base):
    """What the fit measured of one site's magnetic moment (WP-1327).

    ``magnitude`` is the refined modulus DOF — the parameter that carries the
    esd, which is read from ``RefinementResult.parameters`` at
    ``phases.i.atoms.j.moment.dof0`` rather than duplicated here (WP-1076: one
    writer per number).  ``magnitude_from_components`` is |m| recomputed from
    the crystal-axis components with the magCIF *cosine* metric; the two agree
    to roundoff when the conversion is right and disagree by up to 41 % on a
    hexagonal cell when someone reaches for the Euclidean norm, which is why
    both are here.

    ``unmeasured_directions`` names the DOFs the powder average could not
    determine — ``"polar"``, ``"azimuth"`` — and they are *held*, so they carry
    no esd at all.

    ``supported`` is the WP's null test, and it is a **ratio, not a floor**.
    Measured on the Cr₂WO₆ tutorial data (GSAS-II *Magnetic-II*, HB-2A):
    refined against the 150 K pattern, above the ordering temperature, the
    modulus need not go to zero — the shipped acceptance protocol
    (``tests/test_acceptance_magnetic.py``) leaves it at 0.067 μ_B with an esd
    of 1.02, fifteen times larger, while the same stages from the tutorial's
    own starting structure drive it to the floor with an esd three orders of
    magnitude above it.  An absolute floor calls the first supported; the
    honest reading of both is that the moment is not distinguishable from
    none, and the number that says so is |m|/σ.  So ``supported`` is False whenever the modulus is below
    :data:`~rietx.schemas.structure.MOMENT_FLOOR_MU_B` **or** below
    :data:`MOMENT_SUPPORT_SIGMA` times its own esd.  At 4 K the same protocol
    gives 2.12 ± 0.06 — a ratio of 35 — and the answer flips.  With no esd
    there is no ratio to take, and ``supported`` is ``None``.
    """

    phase: str
    atom: str
    #: the magnetic form-factor key, e.g. ``"Cr3+"`` — not ``Atom.species``
    ion: str
    #: The dot-path of the **modulus** DOF this row is about —
    #: ``phases.i.atoms.j.moment.dof0``.  ``phase`` and ``atom`` are *labels*,
    #: chosen for a reader, and two phases may legitimately carry the same
    #: atom label; the path is the key, and it is the one thing a caller needs
    #: to reach the same number in ``RefinementResult.parameters`` or to seed
    #: it on the next pattern of a series (WP-1329's carry rule).  Empty only
    #: on a row built before this field existed.
    path: str = ""
    magnitude: float
    #: the modulus's esd, **copied** from ``RefinementResult.parameters`` and
    #: never recomputed here; ``None`` when the block did not refine.  It is
    #: carried because ``supported`` is a ratio and the reader needs both
    #: halves of it, and it is Bérar-Lelann-inflated like every other esd this
    #: package quotes (``Statistics.esd_inflation`` divides the factor back
    #: out).
    magnitude_esd: float | None = None
    magnitude_from_components: float = 0.0
    crystalaxis: list[float]
    #: the dipole approximation in force for this ion, named
    approximation: str
    #: every direction DOF the site symmetry leaves free, in DOF order
    free_directions: list[str] = Field(default_factory=list)
    #: those of them the powder average does not determine
    unmeasured_directions: list[str] = Field(default_factory=list)
    #: paths of the other ``MomentEvidence`` rows this modulus is powder-
    #: degenerate with (Q5) -- empty for an ordinary, separately determined
    #: row.  ``magnitude``/``magnitude_esd`` above stay this row's own refined
    #: DOF and its esd (still what a magCIF writes per atom); the number the
    #: powder actually measures for the pair is :attr:`paired_magnitude`.
    paired_with: list[str] = Field(default_factory=list)
    #: the powder-determinable combination this row belongs to when
    #: :attr:`paired_with` is non-empty: the quadrature sum sqrt(Sigma m^2)
    #: over the paired rows, with its esd propagated from their *measured*
    #: covariance (``rho x sigma_i x sigma_j``, not the independent
    #: approximation) -- ``MOMENT_PAIR_DEGENERATE`` names this pair.  ``None``
    #: for an ordinary row.
    paired_magnitude: float | None = None
    paired_magnitude_esd: float | None = None
    #: the null test: ``True`` or ``False`` where the modulus carries an esd
    #: to test against, ``None`` where it does not (stated and held, or left
    #: out of the covariance as unmeasured) — "not tested", which a defaulted
    #: ``True`` used to read as an answer
    supported: bool | None = None
    note: str = ""


# ----------------------------------------------------------------------
class FitReport(Base):
    """All three layers.  Layer 1/2 fields stay empty when not computed."""

    thresholds_version: str = THRESHOLDS_VERSION

    # -- Layer 0
    rwp: float
    gof: float
    cumulative_chi2_breakpoints: list[float] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    n_regions_total: int = 0
    unmatched: list[UnmatchedPeak] = Field(default_factory=list)
    #: the satellite arm (WP-1326): per phase, whether the unexplained
    #: intensity indexes as satellites of an enumerated candidate set of
    #: propagation vectors.  Empty when no compiled model was supplied — the
    #: arm needs the cell, the symmetry and the radiation — which is absence
    #: for cause and never "no candidate scored".
    satellites: list[SatelliteEvidence] = Field(default_factory=list)
    #: the moment arm (WP-1327): one row per magnetic site, with the magnitude
    #: the fit measured, the dipole approximation in force, the direction the
    #: powder average could not determine, and whether the modulus is above
    #: its floor at all.  Empty when no compiled model was supplied, when no
    #: phase declares a moment, or on an X-ray histogram — absence for cause
    #: in all three, never "no moment was found".
    magnetic: list[MomentEvidence] = Field(default_factory=list)
    #: structural-vs-profile triage (Layer-0 in trustworthiness, though it
    #: needs the compiled model to run).  Absent for cause: None when the fit
    #: is already Le Bail/Pawley (the mode *is* an intensity-free description,
    #: so there is no intensity model to triage) and on model-free reports.
    lebail_gap: LeBailGap | None = None
    #: what the background is doing to the numbers above (WP-1055) — the two
    #: failure modes nothing else in the report can show.  Absent for cause:
    #: None when the result carries no background curve (a pre-v0.2 result,
    #: or an evaluate-only view built without one), never as "the background
    #: is fine".
    background: BackgroundEvidence | None = None
    #: the esd-qualifying statistics quoted beside each other, the δR plot's
    #: two numbers, and the parameter-space evidence carried from fit time
    #: (WP-1056).  Absent for cause: None when the result has no fitted
    #: channels to read residuals from — its carrier-derived fields are
    #: individually None when the fit did not measure them.
    identifiability: IdentifiabilityEvidence | None = None
    summary: str = ""

    # -- Layer 1
    attribution: list[RegionAttribution] = Field(default_factory=list)
    trends: list[TrendAnalysis] = Field(default_factory=list)
    #: per-phase March-Dollase texture diagnostic; populated whenever the
    #: compiled model is supplied, independent of the maturity gate (texture is
    #: a common *cause* of an immature fit, so it must still be reported)
    texture: list[TextureAnalysis] = Field(default_factory=list)
    #: per-phase Stephens anisotropic-strain diagnostic; populated on the same
    #: terms as ``texture`` and for the same reason — a directional width error
    #: no model accounts for is a common cause of an immature fit, so it must
    #: still be reported when Layer 1 abstains
    strain: list[StrainAnalysis] = Field(default_factory=list)
    #: soft-restraint summary (bond/angle/value deviations, pooled restraint χ²),
    #: carried through from the result whenever restraints were declared; a
    #: deviation ≫ σ here is a restraint fighting the data (see RESTRAINT_TENSION)
    restraints: RestraintReport | None = None
    #: bonding geometry with esds through the full covariance (WP-1072),
    #: carried through from the result whenever a Rietveld fit produced one.
    #: Evidence, never a verdict: McCusker §11's "chemical sense of the
    #: structural model" is the reader's judgement, and nothing here scores it
    geometry: GeometryTable | None = None
    #: per-phase coherent domain size and microstrain with esds (WP-1131),
    #: carried through from the result.  Model-free like ``geometry`` — a
    #: width is a width whether or not the fit is mature enough to linearise —
    #: so it speaks on the abstention branch too; the *separability* caveat on
    #: each block is the part that needs Layer 1, and stays ``None`` (no claim
    #: made) when Layer 1 abstained
    microstructure: list[PhaseMicrostructure] = Field(default_factory=list)
    layer1_available: bool = False
    #: set when the global maturity gate refused Layer 1 (the report abstains)
    abstained_reason: str | None = None
    #: which *kind* of abstention (WP-1057), for a consumer that branches:
    #: ``"immature"`` — the Rwp arm, fix the model/starting values first;
    #: ``"resolution_limited"`` — the shape basis explains the misfit but its
    #: edit directions are indistinguishable on merged peaks, so the misfit is
    #: readable in aggregate (Rwp, the Le Bail gap) and not attributable per
    #: kind — **not** evidence the model is wrong, and often a legitimate
    #: stopping point on broad data; ``"unreadable"`` — real misfit the local
    #: gates refuse to read, including widespread validity failure (the
    #: position-family evidence the reindex action carries).  None whenever
    #: Layer 1 spoke.
    abstained_kind: AbstentionKind | None = None

    # -- Layer 2
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)

    def action(self, kind: str) -> SuggestedAction:
        for a in self.suggested_actions:
            if a.kind == kind:
                return a
        raise KeyError(kind)

    def for_stage(self, stage: str, *,
                  max_actions: int = TRAJECTORY_MAX_ACTIONS) -> StageReport:
        """Project this report onto one trajectory rung (WP-1058).

        A projection computed *from* the report, never beside it — the
        :meth:`~rietx.schemas.indexing.IndexingResult.evidence` pattern one
        contract over — so the rung and the report it came from cannot
        disagree about what the fit said at that state.
        """
        active = [a for a in self.suggested_actions if a.active]
        bg = self.background
        return StageReport(
            stage=stage,
            rwp=self.rwp,
            gof=self.gof,
            summary=self.summary,
            abstained_reason=self.abstained_reason,
            abstained_kind=self.abstained_kind,
            actions=active[:max_actions],
            n_actions_omitted=max(0, len(active) - max_actions),
            n_actions_vetoed=len(self.suggested_actions) - len(active),
            n_unmatched_obs=sum(1 for u in self.unmatched
                                if u.kind == "unmatched_obs"),
            n_unmatched_calc=sum(1 for u in self.unmatched
                                 if u.kind == "unmatched_calc"),
            lebail_gap_ratio=None if self.lebail_gap is None
            else self.lebail_gap.ratio,
            off_region_chi2_reduced=None if bg is None
            else bg.off_region_chi2_reduced,
            worst_absorption=None if bg is None else bg.worst_absorption,
            worst_absorption_path=None if bg is None
            else bg.worst_absorption_path,
        )
