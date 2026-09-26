"""The FitReport: agent-native fit assessment in three gated layers.

``build_report(result)`` alone gives Layer 0 (model-free, always
trustworthy).  Pass the compiled model — most easily via
``Refinement.report()`` — to add Layer 1 (gated linear misfit attribution)
and Layer 2 (typed suggested actions).  See :mod:`.schemas` for the contract
and the pinned thresholds, and docs/DESIGN.md for the design rationale.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import RefinementResult
from .apply import RECIPES, Recipe, describe_action, recipe, stage_for
from .background import assess_background
from .identifiability import (
    assess_identifiability,
    identifiability_clause,
    is_exchangeable,
)
from .layer0 import (
    background_clause,
    build_layer0,
    lebail_gap,
    residual_peak_indices,
    too_flexible,
    too_stiff,
)
from .layer1 import (
    abstention_flavour,
    analyse_trends,
    attribute_regions,
    contents_signature,
    maturity_gate,
)
from .layer2 import (
    apply_strategy_veto,
    background_actions,
    cap_texture_crosstalk,
    compare_rivals,
    delta_bic,
    estimate_delta_chi2,
    hamilton_justified,
    layer0_actions,
    note_background_crosstalk,
    predict_then_verify,
    reindex_action,
    resolution_limited_action,
    suggest_actions,
    texture_actions,
)
from .magnetic import analyse_moments
from .satellites import analyse_satellites
from .schemas import (
    LEBAIL_GAP_NOTABLE,
    RIVAL_DECISIVE_MIN_CHI2_RATIO,
    THRESHOLDS_VERSION,
    TRAJECTORY_MAX_ACTIONS,
    BackgroundEvidence,
    BasisCoefficient,
    ExchangeFinding,
    FitReport,
    GateFailure,
    IdentifiabilityEvidence,
    LeBailGap,
    Region,
    RegionAttribution,
    RivalComparison,
    RivalFit,
    SatelliteCandidate,
    SatelliteEvidence,
    StageReport,
    StrainAnalysis,
    SuggestedAction,
    TextureAnalysis,
    TrendAnalysis,
    TrendTemplate,
    UnmatchedPeak,
    VerificationOutcome,
)
from .strain import analyse_strain
from .texture import analyse_texture

__all__ = [
    "RECIPES",
    "RIVAL_DECISIVE_MIN_CHI2_RATIO",
    "THRESHOLDS_VERSION",
    "TRAJECTORY_MAX_ACTIONS",
    "BackgroundEvidence",
    "BasisCoefficient",
    "ExchangeFinding",
    "FitReport",
    "GateFailure",
    "IdentifiabilityEvidence",
    "LeBailGap",
    "Recipe",
    "Region",
    "RegionAttribution",
    "RivalComparison",
    "RivalFit",
    "SatelliteCandidate",
    "SatelliteEvidence",
    "StageReport",
    "StrainAnalysis",
    "SuggestedAction",
    "TextureAnalysis",
    "TrendAnalysis",
    "TrendTemplate",
    "UnmatchedPeak",
    "VerificationOutcome",
    "abstention_flavour",
    "analyse_moments",
    "analyse_satellites",
    "analyse_strain",
    "analyse_texture",
    "analyse_trends",
    "apply_strategy_veto",
    "assess_background",
    "assess_identifiability",
    "attribute_regions",
    "background_actions",
    "background_clause",
    "build_layer0",
    "build_report",
    "cap_texture_crosstalk",
    "compare_rivals",
    "contents_signature",
    "delta_bic",
    "describe_action",
    "estimate_delta_chi2",
    "hamilton_justified",
    "identifiability_clause",
    "is_exchangeable",
    "layer0_actions",
    "lebail_gap",
    "maturity_gate",
    "note_background_crosstalk",
    "predict_then_verify",
    "recipe",
    "reindex_action",
    "residual_peak_indices",
    "resolution_limited_action",
    "stage_for",
    "suggest_actions",
    "texture_actions",
    "too_flexible",
    "too_stiff",
]


def _stamped(actions: list[SuggestedAction]) -> list[SuggestedAction]:
    """Sort by confidence and stamp each action's ``execution`` class.

    ``execution`` is quoted from ``RECIPES`` — ``report/apply.py`` stays the
    one authority for how a kind is carried out; the stamp only makes the
    classification travel on the action itself, where before WP-1106 it
    reached the GUI's apply arms and no JSON consumer.
    """
    for action in actions:
        action.execution = RECIPES[action.kind].how
    actions.sort(key=lambda a: -a.confidence)
    return actions


def _attach_separability(report: FitReport) -> None:
    """Copy the width trend's separability verdict onto every phase block.

    One statistic (``TrendAnalysis.separable`` and its
    ``max_template_collinearity``), two readers: the Layer-2 action already
    caps its confidence on it, and a reported domain size now carries it.
    Per *report* rather than per phase because the trend is fitted across
    regions and is not resolved by phase — which is itself worth knowing, and
    is why the field is a caveat rather than a per-phase measurement.

    Leaves ``separable`` at ``None`` when there is no width trend to read: no
    claim made, the ``freeze_cell_windows`` convention.
    """
    width = next((t for t in report.trends if t.observable == "width"), None)
    if width is None:
        return
    for block in report.microstructure:
        block.separable = width.separable
        block.size_strain_collinearity = width.max_template_collinearity


def _resid_norm(result: RefinementResult) -> np.ndarray:
    """(y_obs − y_calc)/σ on the fitted grid — Layer 0's own residual."""
    return ((np.asarray(result.y_obs) - np.asarray(result.y_calc))
            / result.sig())


def build_report(result: RefinementResult, *, model=None, values=None,
                 plan=None, free_paths: list[str] | None = None,
                 structure=None, held: list[str] | None = None,
                 top_n: int = 15, match_tol_deg: float = 0.08,
                 min_peak_sigma: float = 5.0) -> FitReport:
    """Build the report, going as deep as the inputs allow.

    Parameters
    ----------
    result:
        The refinement result (Layer 0 needs nothing else).
    model, values:
        A :class:`~rietx.model.forward.CompiledModel` and its parameter
        value dict.  Supplying both enables Layers 1-2; without them the
        report is Layer 0 and ``layer1_available`` stays False.
        ``Refinement.report()`` fills these in for you.
    plan, free_paths:
        Used by the Layer-2 strategy veto: actions the plan already performs,
        or parameters already free, are marked inactive.
    structure:
        The :class:`~rietx.schemas.structure.Structure` the model was compiled
        from.  Optional, and it buys two things the compiled model does not
        carry: the moment arm (WP-1327) labels each row with the atom's own
        label rather than its index, and the satellite arm (WP-1326) reports
        which propagation vector each phase already *declares*.
    held:
        The last stage's hold list (``StageResult.held``), so the moment arm's
        "unmeasured" directions are the refinement's answer rather than a
        second opinion about it.
    """
    report = build_layer0(result, top_n=top_n, match_tol_deg=match_tol_deg,
                          min_peak_sigma=min_peak_sigma)
    # Soft-restraint deviations are model-free (carried from the result), so they
    # surface even at Layer 0 — a restraint fighting the data is worth reporting
    # regardless of whether the fit is mature enough to linearise.
    report.restraints = result.restraints
    # Bonding geometry rides through on the same terms and for the same reason
    # (WP-1072): it is measured against the structure, not against the fit's
    # maturity, and "are these distances chemically sensible" is exactly the
    # question a reader asks first when Layer 1 abstains.
    report.geometry = result.geometry
    # The microstructure block rides through on exactly those terms (WP-1131):
    # a width is a width whether or not the fit is mature enough to linearise,
    # and "how big are the domains" is the question a reader asks of a broad
    # pattern first.  Its separability caveat is the part that needs Layer 1
    # and is attached below, so a block read from the abstained branch says
    # ``separable=None`` — no claim made — rather than claiming separability
    # nothing measured.
    # Copied, not aliased: ``_attach_separability`` writes into these blocks,
    # and a shared instance would leave the *result* carrying a verdict it
    # never computed — and would let a second, abstaining report inherit the
    # first one's ``separable`` instead of the ``None`` it promises.
    report.microstructure = [b.model_copy(deep=True)
                             for b in result.microstructure]
    # The identifiability section (WP-1056) is likewise read from the stored
    # result plus what the fit screened at Jacobian time, never linearised —
    # and an exchangeable held parameter is exactly the evidence a *converged*
    # report must not withhold, so it speaks on every branch, abstention
    # included.
    report.identifiability = assess_identifiability(result)
    clause = identifiability_clause(report.identifiability)
    # One render, two writes (WP-1108): the summary keeps the sentence for
    # its readers, and the statistics block — the one place measured agent
    # consumers grep back out of a piped response — carries the same string
    # verbatim.  This is Statistics' declared cross-document write, and it is
    # unconditional so the field is always the renderer's current answer.
    result.statistics.identifiability_clause = clause
    if clause is not None:
        report.summary += "; " + clause
    if model is None or values is None:
        return report
    # The moment arm (WP-1327) is computed **above** the Layer-1 gate, because
    # it is axis-free in the strong sense: every number in a
    # :class:`~rietx.report.schemas.MomentEvidence` row — the modulus, its esd,
    # the crystal-axis components, the form-factor approximation, the free and
    # unmeasured directions — is a function of the moment DOFs, the cell and
    # the magnetic operator list, and not one of them is a function of the
    # abscissa.  No field of the row names an angle.  It needs no regions, no
    # regression template and no analytic derivative bases, so it speaks
    # wherever Layer 1 abstains: a moment is the *deliverable* of a magnetic
    # refinement rather than a diagnostic that something is wrong, and a fit
    # that measured one and then declined to print it would be the silent drop
    # this whole arm is written against.  ``held`` is the stage's own hold
    # list, so "unmeasured" here is the refinement's answer rather than a
    # second opinion about it.
    report.magnetic = analyse_moments(
        model, values, structure, held=held,
        # the esds the fit measured, copied rather than recomputed (WP-1076:
        # one writer per number) — ``supported`` is a ratio against them
        esd={p.path: p.stderr for p in result.parameters
             if p.stderr is not None},
        # Q5: the fit's own worst-|rho| list, the one place the covariance
        # survives past fit time — folds a powder-degenerate moment pair into
        # one quadrature number instead of two independently-quoted moduli.
        correlations=(result.identifiability.top_correlations
                     if result.identifiability is not None else None))
    attributions = attribute_regions(model, values, report.regions)
    report.attribution = attributions
    # March-Dollase texture and Stephens anisotropic strain are computed before
    # the maturity gate: an uncorrected intensity or width *direction* is a
    # common *cause* of an immature fit, so these must still speak when the rest
    # of Layer 1 abstains.
    report.texture = analyse_texture(model, values)
    report.strain = analyse_strain(model, values)
    # The satellite arm (WP-1326) is computed here, on the same terms and for
    # the same reason as texture and strain: intensity the model puts nowhere
    # is a *cause* of an immature fit, so the arm must still speak when the
    # rest of Layer 1 abstains — and "might this be magnetic?" is precisely
    # the question a reader asks of a neutron pattern with unindexed low-angle
    # peaks.  It is model-free in the same sense they are: positions only.
    sat_ticks = np.asarray([t for positions in result.ticks.values()
                            for t in positions], dtype=np.float64)
    # every positive residual peak, not Layer 0's ``unmatched_obs`` subset: the
    # arm sorts them itself so one radius decides both the tick test and the
    # satellite test (``report/satellites.py``'s docstring has the measurement)
    tt_res = np.asarray(result.two_theta)
    residual_peaks = tt_res[residual_peak_indices(
        _resid_norm(result), min_peak_sigma=min_peak_sigma)]
    report.satellites = analyse_satellites(
        model, values, residual_two_theta=residual_peaks, ticks=sat_ticks,
        structure=structure)
    # The Le Bail gap is measured, never linearised, so it too speaks on both
    # branches (None outside Rietveld mode — absent for cause).  The summary
    # quotes it only when notable: a converged fit reads ratio ≲ 1 and saying
    # so every time would be noise.
    report.lebail_gap = lebail_gap(model, values,
                                   rwp_rietveld=result.statistics.rwp)
    gap = report.lebail_gap
    if gap is not None and gap.ratio >= LEBAIL_GAP_NOTABLE:
        report.summary += (
            f"; a Le Bail partition at the frozen converged state reaches "
            f"Rwp={gap.rwp_lebail:.4f} against the Rietveld "
            f"Rwp={gap.rwp_rietveld:.4f} (×{gap.ratio:.1f}): positions and "
            f"profile account for the pattern — the intensity model carries "
            f"the misfit, and phase ID does not rest on it")

    ticks = [t for positions in result.ticks.values() for t in positions]
    reason = maturity_gate(result.statistics.rwp, attributions)
    if reason is not None:
        # Abstain from *parameter-level* statements: keep the per-region
        # evidence, publish no trends.  Model-free actions (an unindexed peak
        # is unindexed regardless of maturity — and is a common reason for it)
        # still stand, and the veto still applies to them.  Since WP-1054 the
        # position-family pointer stands here too: validity-radius failures
        # are exactly the evidence abstention rests on, and before it the one
        # state that most needed reindex_or_recheck_cell was the one state
        # that could not receive it.
        kind, extra = abstention_flavour(result.statistics.rwp, attributions)
        if extra is not None:
            reason += " — " + extra
        report.abstained_reason = reason
        report.abstained_kind = kind
        actions = layer0_actions(report.unmatched, attributions, ticks=ticks)
        reindex = reindex_action(attributions)
        if reindex is not None:
            actions.append(reindex)
        # the one action whose remedy is the beamline, emitted exactly on the
        # abstention flavour that names the data as the limit (WP-1106)
        actions += resolution_limited_action(report.abstained_kind)
        actions += texture_actions(report.texture)
        # the background hypotheses stand here for the same reason texture
        # does: their evidence never linearised anything, and an over-flexible
        # or over-stiff background is a *cause* of an immature fit
        actions += background_actions(report.background)
        actions = cap_texture_crosstalk(actions, report.texture,
                                        report.unmatched)
        actions = note_background_crosstalk(actions, report.background)
        if plan is not None or free_paths is not None:
            actions = apply_strategy_veto(actions, plan, free_paths=free_paths)
        report.suggested_actions = _stamped(actions)
        report.summary += f"; Layer 1 abstained — {reason}"
        return report

    report.layer1_available = True
    report.trends = analyse_trends(attributions, model.wavelength,
                                   model.geometry_kind)
    # The size/strain separability caveat, carried **beside the number**
    # (WP-1131): over a narrow 2θ range 1/cosθ and tanθ are collinear, and a
    # domain size quoted without saying so is the confident wrong singleton
    # this report exists to refuse.  Read off the width trend's own verdict
    # rather than recomputed — one statistic, two readers.
    _attach_separability(report)
    # The contents-type clause (WP-1057): sign-alternating intensity misfit
    # with no angular trend is the one signature the trend templates are
    # structurally blind to, and the honest zero-action report it produces
    # left the expert inference unstated.  Evidence stays in attribution and
    # trends; this names what they support, and points at the gap that
    # decides it.
    clause = contents_signature(report.trends, attributions)
    if clause is not None:
        if report.lebail_gap is not None:
            clause += (f"; the Le Bail gap (×{report.lebail_gap.ratio:.1f}) "
                       f"is the deciding statistic")
        report.summary += "; " + clause
    actions = suggest_actions(attributions, report.trends, report.unmatched,
                              rwp=result.statistics.rwp, ticks=ticks,
                              geometry=model.geometry_kind,
                              wavelength=model.wavelength)
    predicted = estimate_delta_chi2(result, attributions)
    for action in actions:
        action.expected_delta_chi2 = predicted
    # texture and background actions join after the Δχ² stamp: their evidence
    # is per-reflection or whole-pattern, not the gated region attribution the
    # estimate covers — and off-region misfit is by definition outside every
    # region the estimate sums over
    actions += texture_actions(report.texture)
    actions += background_actions(report.background)
    actions = cap_texture_crosstalk(actions, report.texture, report.unmatched)
    actions = note_background_crosstalk(actions, report.background)
    if plan is not None or free_paths is not None:
        actions = apply_strategy_veto(actions, plan, free_paths=free_paths)
    report.suggested_actions = _stamped(actions)

    n_active = sum(1 for a in actions if a.active)
    report.summary += (f"; Layer 1 on {len([a for a in attributions if a.gates_passed])}"
                       f"/{len(attributions)} regions, {n_active} active suggestion(s)")
    return report
