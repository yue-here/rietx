"""The FitReport: agent-native fit assessment in three gated layers.

``build_report(result)`` alone gives Layer 0 (model-free, always
trustworthy).  Pass the compiled model — most easily via
``Refinement.report()`` — to add Layer 1 (gated linear misfit attribution)
and Layer 2 (typed suggested actions).  See :mod:`.schemas` for the contract
and the pinned thresholds, and docs/DESIGN.md for the design rationale.
"""

from __future__ import annotations

from ..schemas.results import RefinementResult
from .layer0 import build_layer0
from .layer1 import analyse_trends, attribute_regions, maturity_gate
from .layer2 import (
    apply_strategy_veto,
    delta_bic,
    estimate_delta_chi2,
    hamilton_justified,
    layer0_actions,
    predict_then_verify,
    suggest_actions,
)
from .schemas import (
    THRESHOLDS_VERSION,
    BasisCoefficient,
    FitReport,
    Region,
    RegionAttribution,
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
    "THRESHOLDS_VERSION",
    "BasisCoefficient",
    "FitReport",
    "Region",
    "RegionAttribution",
    "StrainAnalysis",
    "SuggestedAction",
    "TextureAnalysis",
    "TrendAnalysis",
    "TrendTemplate",
    "UnmatchedPeak",
    "VerificationOutcome",
    "analyse_strain",
    "analyse_texture",
    "analyse_trends",
    "apply_strategy_veto",
    "attribute_regions",
    "build_layer0",
    "build_report",
    "delta_bic",
    "estimate_delta_chi2",
    "hamilton_justified",
    "layer0_actions",
    "maturity_gate",
    "predict_then_verify",
    "suggest_actions",
]


def build_report(result: RefinementResult, *, model=None, values=None,
                 plan=None, free_paths: list[str] | None = None,
                 top_n: int = 15, match_tol_deg: float = 0.08,
                 min_peak_sigma: float = 5.0) -> FitReport:
    """Build the report, going as deep as the inputs allow.

    Parameters
    ----------
    result:
        The refinement result (Layer 0 needs nothing else).
    model, values:
        A :class:`~pxrdref.model.forward.CompiledModel` and its parameter
        value dict.  Supplying both enables Layers 1-2; without them the
        report is Layer 0 and ``layer1_available`` stays False.
        ``Refinement.report()`` fills these in for you.
    plan, free_paths:
        Used by the Layer-2 strategy veto: actions the plan already performs,
        or parameters already free, are marked inactive.
    """
    report = build_layer0(result, top_n=top_n, match_tol_deg=match_tol_deg,
                          min_peak_sigma=min_peak_sigma)
    # Soft-restraint deviations are model-free (carried from the result), so they
    # surface even at Layer 0 — a restraint fighting the data is worth reporting
    # regardless of whether the fit is mature enough to linearise.
    report.restraints = result.restraints
    if model is None or values is None:
        return report

    attributions = attribute_regions(model, values, report.regions)
    report.attribution = attributions
    # March-Dollase texture and Stephens anisotropic strain are computed before
    # the maturity gate: an uncorrected intensity or width *direction* is a
    # common *cause* of an immature fit, so these must still speak when the rest
    # of Layer 1 abstains.
    report.texture = analyse_texture(model, values)
    report.strain = analyse_strain(model, values)

    reason = maturity_gate(result.statistics.rwp, attributions)
    if reason is not None:
        # Abstain from *parameter-level* statements: keep the per-region
        # evidence, publish no trends.  Model-free actions (an unindexed peak
        # is unindexed regardless of maturity — and is a common reason for it)
        # still stand, and the veto still applies to them.
        report.abstained_reason = reason
        actions = layer0_actions(report.unmatched, attributions)
        if plan is not None or free_paths is not None:
            actions = apply_strategy_veto(actions, plan, free_paths=free_paths)
        report.suggested_actions = actions
        report.summary += f"; Layer 1 abstained — {reason}"
        return report

    report.layer1_available = True
    report.trends = analyse_trends(attributions, model.wavelength)
    actions = suggest_actions(attributions, report.trends, report.unmatched,
                              rwp=result.statistics.rwp)
    predicted = estimate_delta_chi2(result, attributions)
    for action in actions:
        action.expected_delta_chi2 = predicted
    if plan is not None or free_paths is not None:
        actions = apply_strategy_veto(actions, plan, free_paths=free_paths)
    report.suggested_actions = actions

    n_active = sum(1 for a in actions if a.active)
    report.summary += (f"; Layer 1 on {len([a for a in attributions if a.gates_passed])}"
                       f"/{len(attributions)} regions, {n_active} active suggestion(s)")
    return report
