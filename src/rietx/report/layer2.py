"""FitReport Layer 2: typed suggested actions — **advisory only**.

Layer 1 says *what* is wrong in physical terms (peaks 0.01° low, 5 % weak).
Layer 2 maps that onto a closed, versioned vocabulary of things a refinement
can actually do, each with a confidence, the alternatives it could not rule
out, and a predicted Δχ².  Three rules keep it honest:

1. **The strategy engine holds the veto.**  :func:`apply_strategy_veto` marks
   any action the staged plan already performs (or a guard forbids); a vetoed
   action stays in the report — silently dropping it would hide the reasoning
   — but ``active`` is False and an agent must not execute it.
2. **Ambiguity is reported, never resolved by fiat.**  Over a short 2θ range
   the position templates (zero / displacement / cell) and the width templates
   (size / strain — the Williamson-Hall problem) are collinear.  When Layer 1
   says the templates are not separable, the competing actions all appear in
   ``alternatives`` and confidence is capped.
3. **Predict, then verify.**  ``expected_delta_chi2`` comes from a linear
   model and is optimistic by construction; :func:`predict_then_verify`
   actually runs the stage and rolls back when the measured improvement does
   not materialise, so a wrong suggestion costs time, not correctness.

The actions carry no statistical test of their own.  Whether a freed
parameter paid for itself is :func:`compare_freed`, which prices two fits'
χ² with :func:`delta_bic` at N/f² and puts each freed parameter's t-ratio
beside it (WP-1417).  :func:`hamilton_justified` and :func:`delta_bic` are
the free functions under it; their default N is the raw count, right only
where N counts independent points (the indexing callers).  Until WP-1417
this paragraph said the actions were gated by both tests, and no call in
this module made either.
"""

from __future__ import annotations

import math

import numpy as np

from ..model.profiles.caglioti import SCHERRER_K, apparent_size_from_size_coefficient
from ..schemas.results import RefinementResult
from .schemas import (
    BACKGROUND_ABSORPTION_NOTABLE,
    COLLECT_DATA_CONFIDENCE,
    IMPURITY_SHIFT_CAP,
    MIN_COEF_SIGNIFICANCE,
    REINDEX_MIN_FAR_FRACTION,
    REINDEX_MIN_FAR_REGIONS,
    SHIFT_PAIR_WINDOW_DEG,
    SHIFT_TICK_PROXIMITY_FWHM,
    TEXTURE_IMPURITY_MARGIN,
    VALIDITY_RADIUS_FWHM,
    ActionKind,
    ExchangeFinding,
    FreedComparison,
    FreedParameter,
    RegionAttribution,
    RivalComparison,
    RivalFit,
    SuggestedAction,
    TrendAnalysis,
    UnmatchedPeak,
    VerificationOutcome,
)

#: template name → (action, parameter path) for position trends, **per
#: geometry**: one shape can have different causes on different instruments,
#: and a cause a geometry does not have must not be suggested there.
#: ``sin_2theta`` is the case that forces the keying — flat-plate transparency
#: on one side of it, the capillary's along-beam displacement (McCusker eq 4)
#: on the other — and the capillary's ``cos_theta`` row is the one that had to
#: go: before WP-1073 it named ``sample_displacement``, which ``ParameterTable``
#: force-fixes outside ``bragg_brentano``, so the suggestion could not be
#: taken.  Keyed by the same geometry names as
#: :data:`~rietx.report.layer1.POSITION_TEMPLATES`, which decides what can
#: reach here at all; the two are checked against each other by test.
#:
#: ``flat_plate_transmission`` maps only the two templates whose parameters
#: its table can free (WP-1003, ratifying 1073): that geometry models no
#: displacement or transparency at all, so ``ParameterTable`` force-fixes
#: both aberration parameters there — the capillary defect class again — and
#: a ``cos_theta``/``sin_2theta`` trend is *reported as a shape with no
#: action* rather than as a suggestion that answers 409.  The templates stay
#: in layer 1 because the diagnosis is right (a flat specimen off the axis);
#: only the advice was wrong.
_POSITION_ACTIONS_BY_GEOMETRY: dict[str, dict[str, tuple[ActionKind, str]]] = {
    "bragg_brentano": {
        "constant": ("refine_zero_shift", "instrument.zero_shift"),
        "cos_theta": ("refine_sample_displacement",
                      "instrument.geometry.sample_displacement"),
        "sin_2theta": ("refine_sample_transparency",
                       "instrument.geometry.sample_transparency"),
        "tan_theta": ("refine_cell", "phases.*.cell.*"),
    },
    "debye_scherrer": {
        "constant": ("refine_zero_shift", "instrument.zero_shift"),
        "sin_2theta": ("refine_capillary_offset_along_beam",
                       "instrument.geometry.capillary_offset_along_beam"),
        "cos_2theta": ("refine_capillary_offset_across_beam",
                       "instrument.geometry.capillary_offset_across_beam"),
        "tan_theta": ("refine_cell", "phases.*.cell.*"),
    },
    "flat_plate_transmission": {
        "constant": ("refine_zero_shift", "instrument.zero_shift"),
        "tan_theta": ("refine_cell", "phases.*.cell.*"),
    },
}

#: the map a caller with no geometry in hand gets — the Bragg-Brentano one,
#: which is what every caller got before the keying existed
_POSITION_ACTIONS = _POSITION_ACTIONS_BY_GEOMETRY["bragg_brentano"]
_WIDTH_ACTIONS: dict[str, tuple[ActionKind, str]] = {
    "inv_cos_theta": ("refine_sample_size_broadening", "phases.*.lor_size"),
    "tan_theta": ("refine_sample_strain_broadening", "phases.*.lor_strain"),
}

#: what ``refine_profile_widths`` frees: the instrument's **Gaussian**
#: polynomial only, and that is physics rather than caution.  Instrument and
#: sample Lorentzian FWHMs add, so a Lorentzian instrument width error is
#: column-degenerate with ``phases.*.lor_size``/``…lor_strain`` and the sample
#: actions absorb it exactly; a Gaussian variance deficit is what they
#: provably cannot reach (measured on E3, ``tests/test_report_loop.py``: the
#: accepted sample proxy took χ²_red 15.1 → 4.3 and stalled with the width
#: trend still standing at 7σ).
_INSTRUMENT_WIDTH_PATHS = ["instrument.profile.u", "instrument.profile.v",
                           "instrument.profile.w"]

#: an unmatched observed peak this strong is worth proposing a phase for
IMPURITY_SIGMA = 8.0


def hamilton_justified(chi2_restricted: float, chi2_full: float,
                       n_points: int, n_free_restricted: int,
                       n_added: int, *, alpha: float = 0.05,
                       n_effective: float | None = None) -> bool:
    """Hamilton's R-factor ratio test for adding ``n_added`` parameters.

    Hamilton (1965), Acta Cryst. 18, 502: under the null hypothesis that the
    added parameters are unnecessary, ℛ = √(χ²_restricted/χ²_full) follows
    the ℛ-distribution, equivalent to the F test

        F = [(χ²_r − χ²_f)/n_added] / [χ²_f/(N − P_f)]

    compared against F(n_added, N − P_f) at ``alpha``.  Returns True when the
    improvement justifies the parameters.

    ``n_effective`` is the independent-observation count to test at in place
    of ``n_points`` — :func:`~rietx.optimize.statistics.effective_sample_size`
    of the fit's ``esd_inflation`` (#270).  The statistic is then evaluated
    as if the χ² had come from N_eff independent points (degrees of freedom
    N_eff − P_f, so F ≈ t²/f² for one parameter), which is the same count
    :func:`delta_bic` takes, so the two verdicts are read off one N.
    ``None``, the default, is the raw-channel test it has always been.
    """
    n = float(n_points) if n_effective is None else float(n_effective)
    dof = n - n_free_restricted - n_added
    if n_added <= 0 or dof <= 0 or chi2_full <= 0:
        return False
    # with N_eff the χ²s are read as N_eff independent points' worth: both
    # scale by N_eff/N and cancel in the ratio, leaving the dof to carry it,
    # so F ≈ t²/f² — the parameter's t at its inflated esd, squared
    f = ((chi2_restricted - chi2_full) / n_added) / (chi2_full / dof)
    if f <= 0:
        return False
    from scipy.stats import f as f_dist

    return bool(f > f_dist.ppf(1.0 - alpha, n_added, dof))


def delta_bic(chi2_restricted: float, chi2_full: float,
              n_points: int, n_added: int, *,
              n_effective: float | None = None) -> float:
    """BIC difference (restricted − full); positive favours the fuller model.

    ΔBIC = N·ln(χ²_r/χ²_f) − n_added·ln(N)  (Schwarz 1978, Gaussian errors).

    Schwarz's N is a count of **independent** observations.  ``n_effective``
    replaces it in both terms — pass
    :func:`~rietx.optimize.statistics.effective_sample_size` of the fit's
    ``esd_inflation`` — because on a powder pattern the residual is serially
    correlated and raw N lets any χ² improvement outvote the ln N penalty:
    the reporter's four ~49 500-channel synchrotron fits gave ΔBIC +36 to
    +211 for an occupancy each fit's own esd put within 0.76-1.89σ of zero,
    and N_eff = N/f² turned all four negative (#270).  ``None``, the default,
    is the raw-N form, kept for the callers whose N *is* a count of
    independent points (a peak list, a reflection set).
    """
    if chi2_full <= 0 or chi2_restricted <= 0:
        return 0.0
    n = float(n_points) if n_effective is None else float(n_effective)
    return n * math.log(chi2_restricted / chi2_full) - n_added * math.log(max(n, 2.0))


def compare_freed(restricted, full) -> FreedComparison:
    """ΔBIC of the parameters ``full`` frees beyond ``restricted``, each one's t beside it.

    Both arguments are :class:`~rietx.Refinement` objects the caller has
    already fitted, on the same pattern and in the same mode, with ``full``
    freeing everything ``restricted`` frees and more.  A branch that ran one
    more stage is the usual shape.  No fit runs here.

    ΔBIC is :func:`delta_bic` at N/f², with f the restricted fit's
    ``esd_inflation`` (:func:`~rietx.optimize.statistics.effective_sample_size`),
    and the raw-N figure rides beside it.  Each freed parameter's t-ratio is
    measured from the value ``restricted`` held it at, which is why the
    arguments are refinements and not results: a result lists only what
    varied, so the held value is in the working table and nowhere else.  The
    table stands where the fit left it, because every verb that moves a value
    drops ``result_``.

    A coordinate DOF is a step from where its own fit began
    (:attr:`~rietx.params.vector.ParameterTable.anchored_dof_paths`), so its
    held value is read through a coordinate row it alone drives, which is
    absolute in both fits.  The t-ratio is then right whichever model each
    fit started from.

    Issue #270 is why the pair travels together.  On four ~49 500-channel
    fits of one occupancy, raw-N ΔBIC read +36 to +211 while each fit's own
    esd put the occupancy within 0.76-1.89σ of zero.

    Raises :class:`ValueError` when the two fits are not nested: different
    channel counts or modes, a path ``restricted`` frees that ``full`` does
    not, or nothing added.
    """
    for name, ref in (("restricted", restricted), ("full", full)):
        if ref.result_ is None:
            raise RuntimeError(f"run a fit on the {name} refinement before comparing")
    held = {row.path: row.value for row in restricted.parameters()}
    return _freed_comparison(restricted.result_, held, full)


def _freed_comparison(restricted: RefinementResult, held: dict[str, float],
                      full) -> FreedComparison:
    """:func:`compare_freed` on the restricted result, its table's values, and
    the fuller :class:`~rietx.Refinement`."""
    from ..optimize.statistics import effective_sample_size
    from ..params.vector import ParameterTable

    fr = full.result_
    rs, fs = restricted.statistics, fr.statistics
    if rs.n_points != fs.n_points:
        raise ValueError(
            f"the fits saw {rs.n_points} and {fs.n_points} channels; ΔBIC "
            "compares two models of one pattern")
    if restricted.mode != fr.mode:
        raise ValueError(
            f"the fits ran in {restricted.mode!r} and {fr.mode!r} mode, so "
            "neither model is the other with parameters added")
    free_r = {p.path for p in restricted.parameters if p.vary}
    added = [p for p in fr.parameters if p.vary and p.path not in free_r]
    dropped = sorted(free_r - {p.path for p in fr.parameters if p.vary})
    if dropped:
        raise ValueError(
            f"not nested: the restricted fit frees {dropped[0]!r}"
            + (f" and {len(dropped) - 1} more" if len(dropped) > 1 else "")
            + " and the fuller one does not")
    # the solver's own count, as compare_rivals takes it: ``parameters`` also
    # carries tied rows, which are not free columns
    n_added = fs.n_free_parameters - rs.n_free_parameters
    if n_added <= 0 or not added:
        raise ValueError(
            f"the fuller fit frees {fs.n_free_parameters} parameters against "
            f"{rs.n_free_parameters}, so there is nothing added to compare")

    relative = ParameterTable(full.structure, full.instrument).anchored_dof_paths
    # a coordinate row x = anchor + b·dof, keyed by the one DOF it follows
    through = {}
    if any(p.path in relative for p in added):
        for row in full.parameters():
            if row.tie is not None and len(row.tie.terms) == 1:
                through.setdefault(row.tie.terms[0][0], (row.path, row.tie.terms[0][1]))
    values = {p.path: p.value for p in fr.parameters}

    def held_at(p) -> float | None:
        if p.path not in relative:
            return held.get(p.path)
        row, b = through.get(p.path, (None, 0.0))
        if row is None or b == 0.0 or row not in held or row not in values:
            return None
        return p.value - (values[row] - held[row]) / b

    freed = []
    for p in added:
        start = held_at(p)
        t = (None if start is None or not p.stderr
             else (p.value - start) / p.stderr)
        freed.append(FreedParameter(path=p.path, held_at=start, value=p.value,
                                    esd=p.stderr, t_ratio=t))
    n_eff = effective_sample_size(rs.n_points, rs.esd_inflation)
    return FreedComparison(
        freed=freed, n_added=n_added, n_points=rs.n_points,
        chi2_restricted=rs.chi2, chi2_full=fs.chi2,
        esd_inflation=rs.esd_inflation, n_effective=n_eff,
        delta_bic=delta_bic(rs.chi2, fs.chi2, rs.n_points, n_added,
                            n_effective=n_eff),
        delta_bic_raw_n=delta_bic(rs.chi2, fs.chi2, rs.n_points, n_added))


def _significant(templates, name: str) -> tuple[float, float] | None:
    for t in templates:
        if t.name == name and t.stderr > 0 and abs(t.coefficient) > MIN_COEF_SIGNIFICANCE * t.stderr:
            return t.coefficient, t.stderr
    return None


#: the one template whose fitted coefficient *is* a 1/cosθ size coefficient in
#: deg 2θ — the same quantity as ``instrument.profile.x + phases.N.lor_size``,
#: and therefore the one this module can read as a crystallite size with no
#: reference angle (``model/profiles/caglioti`` (4)).  ``tan_theta`` is strain
#: and ``constant``/``cos_theta``/… are positions: none of them has a size.
_SIZE_TEMPLATE = "inv_cos_theta"


def _size_clause(name: str, coefficient: float, wavelength: float | None) -> str:
    """The 1/cosθ width deficit as an apparent crystallite size, or ``""``.

    Empty in three cases, each of them "no claim" rather than "no size": a
    template that is not the size term, a caller who passed no wavelength, and
    a **negative** coefficient.  The last is the one worth naming — a negative
    ΔΓ means the model's peaks are too *broad*, and Scherrer read backwards
    would name the size of a crystallite the specimen does not have.  The
    action is still emitted; only this clause is withheld.

    Why the clause exists at all: the coefficient is in degrees, which is not
    transferable between instruments — 0.5 deg is a 15 nm crystallite on Cu and
    a 4 nm one on 11-BM — so the number the reader can act on is the size.
    """
    if name != _SIZE_TEMPLATE or wavelength is None or not coefficient > 0.0:
        return ""
    size_a = apparent_size_from_size_coefficient(coefficient, wavelength)
    return (f"; the coefficient is the 1/cosθ size term, so across the whole "
            f"pattern it reads as the size that would account for the missing "
            f"width — L ≈ {size_a:.0f} Å at λ = {wavelength:.4f} Å (Scherrer, K = "
            f"{SCHERRER_K}, an order-of-magnitude statement: shape moves K by "
            f"10-20 %). Degrees are not transferable between instruments; this "
            f"is the same width in the unit a specimen can be judged in")


def _trend_actions(trend: TrendAnalysis,
                   mapping: dict[str, tuple[ActionKind, str]],
                   unit: str, *, wavelength: float | None = None
                   ) -> list[SuggestedAction]:
    """Turn one trend analysis into actions, capping confidence on ambiguity.

    ``wavelength`` is used only to add :func:`_size_clause` to the width
    observable's size template; ``None`` (the default, and what a caller with no
    instrument in hand gets) leaves every rationale exactly as it was.
    """
    hits = []
    for name, (kind, path) in mapping.items():
        sig = _significant(trend.templates, name)
        if sig is not None:
            hits.append((name, kind, path, sig[0], sig[1]))
    if not hits:
        return []

    quality = max(0.0, min(1.0, max((t.r2 for t in trend.templates), default=0.0)))
    best = max(trend.templates, key=lambda t: t.r2).name
    # importance, not just significance: an observable carrying 2 % of the
    # misfit cannot be a high-confidence call however many σ it stands at
    importance = min(1.0, trend.misfit_share / 0.25)
    peers: list[ActionKind] = [h[1] for h in hits]
    actions: list[SuggestedAction] = []
    for name, kind, path, coef, err in hits:
        alternatives = [k for k in peers if k != kind]
        confidence = (quality * importance
                      * min(1.0, abs(coef) / (MIN_COEF_SIGNIFICANCE * err) / 2.0))
        if name != best:
            confidence *= 0.5      # a runner-up template is not the headline
        rationale = (f"{trend.observable} error follows the {name} template "
                     f"({coef:+.4g} ± {err:.2g} {unit}, R²={quality:.2f}, "
                     f"{trend.misfit_share:.0%} of χ², "
                     f"{trend.n_regions_used} regions)")
        rationale += _size_clause(name, coef, wavelength)
        if not trend.separable:
            # collinear over this range: keep every candidate, trust none
            confidence = min(confidence, 0.3)
            alternatives = [k for k in peers if k != kind]
            rationale += ("; templates are collinear over the 2θ range measured "
                          f"(|r|={trend.max_template_collinearity:.3f}) — this "
                          "attribution is NOT separable from its alternatives")
        actions.append(SuggestedAction(
            kind=kind, confidence=round(float(confidence), 3), rationale=rationale,
            parameter_paths=[path], alternatives=alternatives))
    return actions


def layer0_actions(unmatched: list[UnmatchedPeak],
                   attributions: list[RegionAttribution] | None = None,
                   *, ticks: list[float] | None = None
                   ) -> list[SuggestedAction]:
    """Actions justified by **model-free** evidence alone.

    These survive a Layer-1 abstention: an unindexed peak is an unindexed
    peak whether or not the rest of the model is mature enough to linearise
    — indeed a missing phase is a common *reason* for immaturity.

    One correction, in three regimes (WP-1054): a peak-position error also
    produces residual peaks with no tick on top of them (the model's peak sits
    beside the observed one), which masquerade as an impurity — and a real
    model consumed exactly that invitation (WP-1053, E7).  A strong unmatched
    observed peak is therefore attributed to the *shift* rather than to a new
    phase when

    * it falls inside a region whose fitted position offset is significant,
      padded by ~1 FWHM (small shifts, the pre-1054 test — these are dropped
      silently, as ever: the position trend actions already name the cause);
    * it lies within :data:`SHIFT_TICK_PROXIMITY_FWHM` pattern-median FWHM of
      a calculated position (broad peaks, where the 0.08° matching tolerance
      is far smaller than the peak itself and every shape-misfit lobe reads
      as "unmatched"); or
    * validity-radius failures exist and an ``unmatched_calc`` partner sits
      within :data:`SHIFT_PAIR_WINDOW_DEG` — a *displaced pair*: the observed
      line and the calculated line it walked away from (large shifts, where
      the saturated linear fit cannot measure the offset but the pairing is
      plain in the model-free lists).

    When such shift-matched peaks exist alongside genuinely foreign ones, the
    call is made on the foreign count and both counts are reported.  When
    *every* strong peak matches the shift evidence the action is still
    emitted — the evidence stays visible — but capped at
    :data:`IMPURITY_SHIFT_CAP` with ``reindex_or_recheck_cell`` first among
    the alternatives: on that evidence a phantom phase is the less likely
    reading (the confident-wrong-singleton rule applied to impurity calls).
    """
    atts = attributions or []
    shifted_regions = [
        a for a in atts
        if any(c.kind == "position" and c.significant for c in a.coefficients)
    ]
    far_regions = [a for a in atts
                   if any(f.code == "outside_validity_radius"
                          for f in a.gate_failures)]
    fwhms = [a.mean_fwhm for a in atts if a.mean_fwhm > 0]
    fwhm_ref = float(np.median(fwhms)) if fwhms else 0.0
    tick_arr = np.sort(np.asarray(ticks, dtype=float)) if ticks else None
    ucalc = np.sort([u.two_theta for u in unmatched
                     if u.kind == "unmatched_calc"])

    def explained_by_shift(u: UnmatchedPeak) -> bool:
        # a mispositioned peak leaves a derivative-shaped residual whose lobes
        # sit up to ~1 FWHM outside the region, so the region is padded before
        # the containment test
        for a in shifted_regions:
            pad = max(a.mean_fwhm, 0.05)
            if a.two_theta_lo - pad <= u.two_theta <= a.two_theta_hi + pad:
                return True
        return False

    def matches_shift_evidence(u: UnmatchedPeak) -> bool:
        if tick_arr is not None and fwhm_ref > 0 and (
                np.min(np.abs(tick_arr - u.two_theta))
                <= SHIFT_TICK_PROXIMITY_FWHM * fwhm_ref):
            return True
        return bool(far_regions and len(ucalc) and (
            np.min(np.abs(ucalc - u.two_theta)) <= SHIFT_PAIR_WINDOW_DEG))

    strong = [u for u in unmatched
              if u.kind == "unmatched_obs"
              and u.height_over_sigma > IMPURITY_SIGMA
              and not explained_by_shift(u)]
    if not strong:
        return []
    foreign = [u for u in strong if not matches_shift_evidence(u)]
    n_matched = len(strong) - len(foreign)

    if foreign:
        worst = max(foreign, key=lambda u: u.height_over_sigma)
        rationale = (f"{len(foreign)} observed peak(s) have no calculated "
                     f"reflection nearby and are not accounted for by the "
                     f"peak-position evidence, the strongest at "
                     f"{worst.two_theta:.3f}° at {worst.height_over_sigma:.0f}σ.")
        if n_matched:
            rationale += (f"  ({n_matched} further unmatched peak(s) lie where "
                          f"the position-error evidence puts them and are "
                          f"attributed to the shift, not counted here.)")
        rationale += (
            "  If the extra lines are an unknown phase rather than a wrong "
            "cell, index_pattern finds its lattice — but one phase at a time: "
            "subtract or model the solved phase first (WP-1028 measured that "
            "a Le Bail partition of two phases inflates both without bound)")
        return [SuggestedAction(
            kind="add_impurity_phase",
            confidence=min(0.9, 0.3 + 0.1 * len(foreign)),
            rationale=rationale,
            alternatives=["reindex_or_recheck_cell"],
            two_theta_range=(worst.two_theta, worst.two_theta))]

    worst = max(strong, key=lambda u: u.height_over_sigma)
    n_paired = sum(
        1 for u in strong
        if far_regions and len(ucalc)
        and np.min(np.abs(ucalc - u.two_theta)) <= SHIFT_PAIR_WINDOW_DEG)
    return [SuggestedAction(
        kind="add_impurity_phase",
        confidence=IMPURITY_SHIFT_CAP,
        rationale=(f"all {len(strong)} unmatched observed peak(s), 0 apart "
                   f"from the position-error evidence: {n_paired} are paired "
                   f"with a missing calculated line within "
                   f"{SHIFT_PAIR_WINDOW_DEG:g}°, the rest sit within "
                   f"~{SHIFT_TICK_PROXIMITY_FWHM:g} FWHM of a calculated "
                   f"position (strongest at {worst.two_theta:.3f}° at "
                   f"{worst.height_over_sigma:.0f}σ).  A wrong cell or a gross "
                   f"zero/displacement error displaces every line and "
                   f"manufactures exactly this signature, so re-check the "
                   f"cell before adding a phase"),
        alternatives=["reindex_or_recheck_cell", "refine_zero_shift",
                      "refine_sample_displacement"],
        two_theta_range=(worst.two_theta, worst.two_theta))]


#: a runner-up axis explaining at least this fraction of the best axis's R²
#: means the axis is not cleanly resolved — the action is still worth taking
#: (the *presence* of texture is established) but its confidence is capped and
#: both axes are named, per the never-a-confident-wrong-singleton rule
TEXTURE_AXIS_AMBIGUITY = 0.8


def texture_actions(texture) -> list[SuggestedAction]:
    """Actions from the March-Dollase texture diagnostic (the WP-0307 orphan,
    claimed by WP-0602).

    Emitted from :attr:`FitReport.texture` entries with ``detected=True`` —
    in the abstained branch too, because uncorrected texture is a common
    *cause* of an immature fit (the same reasoning that computes the analysis
    before the maturity gate).  ``parameter_paths`` names the phase's March
    coefficient whether or not a ``preferred_orientation`` block is declared:
    the strategy veto marks the declared-and-planned case, and on an
    undeclared phase ``predict_then_verify`` frees nothing and rolls back —
    the rationale carries the axis and r so the agent knows what block to
    declare first.  No ``expected_delta_chi2``: the estimate comes from the
    gated region attribution, and this analysis is per-reflection, not
    per-region.
    """
    out: list[SuggestedAction] = []
    for t in texture or []:
        if not t.detected or t.best_axis is None:
            continue
        axis = tuple(int(v) for v in t.best_axis)
        ambiguous = (t.runner_up_axis is not None
                     and t.runner_up_r2 >= TEXTURE_AXIS_AMBIGUITY * t.r2)
        confidence = min(0.85, float(t.r2))
        rationale = (f"per-reflection intensity corrections of phase "
                     f"{t.phase_index} follow a March-Dollase model along "
                     f"{axis} (r={t.march_coefficient:.3f}, R²={t.r2:.2f}, "
                     f"{t.n_reflections_used} reflections)")
        if ambiguous:
            confidence = min(confidence, 0.4)
            runner = tuple(int(v) for v in t.runner_up_axis)
            rationale += (f"; the axis is not cleanly resolved — {runner} "
                          f"fits R²={t.runner_up_r2:.2f}, so refine r but do "
                          "not report the axis as measured")
        rationale += ("; if the phase declares no preferred_orientation block, "
                      "add one with this axis before freeing r")
        out.append(SuggestedAction(
            kind="refine_preferred_orientation",
            confidence=round(confidence, 3), rationale=rationale,
            parameter_paths=[f"phases.{t.phase_index}.preferred_orientation.r"]))
    return out


#: ``increase_background_flexibility`` is capped here however strong the
#: evidence.  The same off-region signature is produced by a background that
#: is too stiff, by an amorphous hump, and by an un-modelled broad crystalline
#: phase — and bending the background over either of the last two *hides* it
#: while improving every statistic.  The evidence cannot separate them, so
#: this direction is never a confident call (the never-a-confident-wrong-
#: singleton rule; ``add_impurity_phase`` rides in ``alternatives``).
BACKGROUND_INCREASE_CAP = 0.6


def background_actions(background) -> list[SuggestedAction]:
    """The two background-flexibility hypotheses, finally emitted (WP-1055).

    Both kinds have been in ``ActionKind`` since v0.2 and were emitted
    **nowhere**: they existed only as :data:`~rietx.report.apply.RECIPES`
    advice and as an ``alternatives`` member on ``refine_biso``.  The recipe
    notes were already the right words — they name the ADP/QPA-bias trap and
    the statistic to read — and had no action to travel on.

    Emitted from :attr:`FitReport.background`, on both sides of the maturity
    gate: the evidence is model-free (plus one fit-time projection), and a
    background failure is a common *cause* of an immature fit, the same
    reasoning that puts texture and strain before the gate.

    Both stay ``how="advice"``.  Changing what a background can absorb is not
    a stage over parameters, and — the reason that matters — the cost of
    getting it wrong is invisible in the evidence that proposes it, so a
    one-click version would be a button whose own report cannot see what it
    did.  ``parameter_paths`` is therefore **empty** rather than
    ``instrument.background.*``: that glob would read as "free the background"
    (which every plan already does, so the strategy veto would grey out the
    suggestion for the wrong reason) when the edit being proposed is to the
    background's *shape*, not to its free set.

    Confidence follows the Layer-2 importance × quality shape, with the
    directions weighted differently because their evidence differs in kind.
    For the decrease direction there is no χ²-share importance term **by
    construction** — the whole signature of an over-flexible background is
    that it does not show up in χ² — so the projection R² carries both roles:
    how much of the parameter the background can reproduce *is* how much of it
    is at risk.  For the increase direction the misfit is real χ², so the
    off-region share is a genuine importance weight (it is a poor *detector*,
    tracking channel count, but a sound measure of how much of the misfit the
    edit would address), and the quality term is how far the off-region
    Durbin-Watson sits below 2.
    """
    if background is None:
        return []
    from .layer0 import too_flexible, too_stiff

    out: list[SuggestedAction] = []
    if too_flexible(background):
        over = sum(1 for r2 in (background.absorption or {}).values()
                   if r2 >= BACKGROUND_ABSORPTION_NOTABLE)
        out.append(SuggestedAction(
            kind="decrease_background_flexibility",
            confidence=round(min(0.85, float(background.worst_absorption)), 3),
            rationale=(
                f"the background column span reproduces "
                f"{background.worst_absorption:.0%} of "
                f"{background.worst_absorption_path} "
                f"({over} of {len(background.absorption or {})} screened "
                f"structural parameters over "
                f"{BACKGROUND_ABSORPTION_NOTABLE:.0%}), so that parameter is "
                f"substitutable with the background rather than measured "
                f"against it.  This is the failure mode that improves every "
                f"statistic while it biases: ADPs up, scales and hence QPA "
                f"fractions down, Rwp down.  Expect Rwp to get *worse* when "
                f"you stiffen it — that is the cost, and an unbiased ADP is "
                f"what it buys"),
            alternatives=[]))
    if too_stiff(background):
        d = float(background.off_region_durbin_watson)
        quality = float(np.clip(1.0 - d / 2.0, 0.0, 1.0))
        importance = min(1.0, background.off_region_chi2_share / 0.25)
        out.append(SuggestedAction(
            kind="increase_background_flexibility",
            confidence=round(min(BACKGROUND_INCREASE_CAP,
                                 quality * importance), 3),
            rationale=(
                f"between the peak regions the residual is systematic rather "
                f"than noise: χ²_red={background.off_region_chi2_reduced:.1f} "
                f"over {background.off_region_points} channels "
                f"({background.off_region_chi2_share:.0%} of total χ²) at "
                f"Durbin-Watson d={d:.2f} (2 = uncorrelated).  Layer 0's "
                f"regions are peak clusters, so this misfit sits in no region "
                f"entry and no attribution can reach it.  An amorphous hump "
                f"or an un-modelled broad crystalline phase produces exactly "
                f"this signature, and a background bent over either *hides* "
                f"it while improving every statistic — so check the "
                f"between-peak shape before adding flexibility, and if you "
                f"add it anyway, read any QPA from the result as fractions of "
                f"the crystalline content you did model"),
            alternatives=["add_impurity_phase"]))
    return out


def resolution_limited_action(abstained_kind: str | None
                              ) -> list[SuggestedAction]:
    """``collect_better_data``: the one state whose remedy is not a parameter.

    Emitted exactly when the abstention classifier read the fit as
    **resolution-limited** (WP-1106): Gram-dominated gate failures at high
    local R², the state where alternative models are indistinguishable *in
    this pattern* — so the data, not the model, is what the report ran out
    of.  The evidence tally is already composed in ``abstained_reason``
    (one authority); the rationale carries the fork that evidence cannot
    resolve: instrumental breadth means better data exists, specimen breadth
    (nanocrystalline broadening) means no re-measurement sharpens it and the
    remedy is fewer free parameters and restraints.  Separating the two
    takes a standard's instrument profile, which this report does not have —
    hence :data:`~rietx.report.schemas.COLLECT_DATA_CONFIDENCE` rather than
    a number pretending to know which side the specimen is on.

    ``PATTERN_UNDERSAMPLED`` was measured for this role and **rejected**:
    every bundled synthetic fixture trips it beside converged GoF ≈ 1.01
    fits (2026-08-19, both the report-loop truth and the round-trip
    fixture), so conditioning on it would stamp this action onto reports
    whose data supported the whole refinement — and the diagnostic already
    carries the re-collect advice with the step-size number.  The E2 loop
    test's ``suggested_actions == []`` on a converged undersampled fixture
    is the standing pin.
    """
    if abstained_kind != "resolution_limited":
        return []
    return [SuggestedAction(
        kind="collect_better_data", confidence=COLLECT_DATA_CONFIDENCE,
        rationale=(
            "the report abstained because the data's resolution, not the "
            "model, is the limit: the gate failures are collinearity on "
            "merged peaks, with the shape basis explaining the misfit it can "
            "reach (abstained_reason has the tally). One fork this pattern "
            "cannot resolve: if the breadth is instrumental, better data "
            "exists — a narrower receiving slit, finer optics, longer "
            "counting; if it is the specimen's (nanocrystalline size "
            "broadening), no re-measurement sharpens it, and the remedy is "
            "fewer free parameters and restraints. A standard's instrument "
            "profile (lab_calibrate) is what separates the two"),
        parameter_paths=[])]


def note_background_crosstalk(actions: list[SuggestedAction], background
                              ) -> list[SuggestedAction]:
    """Name the background as a rival explanation for unmatched peaks.

    Measured on the too-stiff fixture (a Gaussian hump fitted with a 2-term
    Chebyshev): the residual runs 12σ over hundreds of channels, noise on top
    of it clears the 5σ peak-detection floor in 146 places, and
    ``add_impurity_phase`` is emitted at 0.90 — above the background call at
    0.60 — on a specimen with no impurity in it.

    Deliberately **not** a confidence cap, unlike
    :func:`cap_texture_crosstalk`.  There the impurity was the plausible
    *cause* of the texture signature, measured on the same reflections.  Here
    the two findings are about disjoint channels by construction — Layer 0
    segments a region around every residual peak, so an unmatched peak is
    never off-region — and both statements can be true at once.  What the
    evidence does not support is treating them as unrelated, so the rival
    rides in ``alternatives`` and the ranking is left alone (rule 2 of this
    module: ambiguity is reported, never resolved by fiat).
    """
    from .layer0 import too_stiff

    if background is None or not too_stiff(background):
        return actions
    for action in actions:
        if (action.kind == "add_impurity_phase"
                and "increase_background_flexibility" not in action.alternatives):
            action.alternatives = list(action.alternatives) + [
                "increase_background_flexibility"]
            action.rationale += (
                f"; note the background is also under-flexible here "
                f"(off-region χ²_red="
                f"{background.off_region_chi2_reduced:.1f} at d="
                f"{background.off_region_durbin_watson:.2f}), and a residual "
                f"riding that high clears the peak-detection floor on noise "
                f"alone — check the between-peak shape before naming a phase")
    return actions


def reindex_action(attributions: list[RegionAttribution]
                   ) -> SuggestedAction | None:
    """The position-family pointer, emitted on widespread validity failure.

    One emitter for both branches (WP-1054): before it, the condition lived in
    :func:`suggest_actions` as ``far and rwp > 0.2``, which made the action
    structurally unreachable exactly when the cell is most wrong — an abstained
    report never ran that code, so the one state that most needs the indexing
    pointer surfaced only ``add_impurity_phase`` (and a real model quoted it as
    grounds for a phantom phase, WP-1053 E7).  The condition is now that the
    validity failures are *widespread* — a count fraction of the misfitting
    regions (:data:`REINDEX_MIN_FAR_FRACTION`, floored by
    :data:`REINDEX_MIN_FAR_REGIONS`; the schema comment holds the measured
    separation, including why a χ² share was rejected) — which also reaches
    mature fits the old Rwp arm missed (measured: Rwp 0.14 on broad-peak data
    with 60 % of misfitting regions beyond the radius).

    Two rules from the WP bound what this emitter may say.  The evidence
    consulted is the *gate failure* — its kind, its |Δ2θ|-vs-FWHM magnitude,
    its χ² share — never the failed coefficients as causes; and the offset is
    quoted as a lower bound, because a linearisation pushed past its radius
    saturates (measured: 0.03° fitted where the true displacement is 0.18°).
    And the same signature is produced by a wrong cell *and* by a gross
    zero/displacement error, so the action carries the whole family — the
    calibration candidates ride in ``alternatives`` and the rationale says the
    data has not chosen.  Re-indexing is still the safe *first* member:
    ``index_pattern`` searches under its own shift allowance
    (``INDEX_SHIFT_ALLOWANCE``), so a calibration offset does not poison it.
    """
    far = [a for a in attributions
           if any(f.code == "outside_validity_radius"
                  for f in a.gate_failures)]
    misfitting = [a for a in attributions if a.has_significant_misfit]
    if (len(far) < REINDEX_MIN_FAR_REGIONS
            or len(far) < REINDEX_MIN_FAR_FRACTION * len(misfitting)):
        return None
    share = sum(a.chi2_share for a in far)
    ratios = [abs(next((c.value for c in a.coefficients
                        if c.kind == "position"), 0.0)) / a.mean_fwhm
              for a in far if a.mean_fwhm > 0]
    worst_ratio = max(ratios, default=0.0)
    return SuggestedAction(
        kind="reindex_or_recheck_cell", confidence=0.4,
        rationale=(
            f"{len(far)} of {len(misfitting)} misfitting region(s), carrying "
            f"{share:.0%} of χ², have peak offsets beyond the linearisation "
            f"radius "
            f"({VALIDITY_RADIUS_FWHM:g}·FWHM; the worst measures "
            f"≥{worst_ratio:.1f}×FWHM — a lower bound, the saturated linear "
            f"fit cannot see further), so shift-based corrections do not "
            f"apply.  A wrong cell and a grossly wrong zero/displacement "
            f"calibration both produce this signature and these data have "
            f"not chosen between them; re-indexing is the safe first move "
            f"(index_pattern searches under its own shift allowance, so a "
            f"calibration offset does not poison it).  Re-determine the cell "
            f"from the data: pick_peaks(data, instrument) then "
            f"index_pattern(peaks, data=data, instrument=instrument), and "
            f"read best_or_none() — it returns None rather than a cell "
            f"whenever the evidence does not choose one (the agent skill §7d)"),
        parameter_paths=["phases.*.cell.*"],
        alternatives=["refine_zero_shift", "refine_sample_displacement"])


def cap_texture_crosstalk(actions: list[SuggestedAction],
                          texture, unmatched: list[UnmatchedPeak]
                          ) -> list[SuggestedAction]:
    """Impurity ↔ texture cross-talk (WP-1054, third sighting).

    The per-reflection extraction behind :func:`.texture.analyse_texture`
    partitions ``y_obs − background`` by *calculated* share, so a peak the
    model does not predict is partitioned onto its calculated neighbours — a
    pure impurity injection measurably manufactured a (1,0,1) detection at
    R²=0.66 that outranked the impurity call at 0.40.  When strong unmatched
    observed peaks coexist with a texture detection, the detection therefore
    cannot outrank the impurity action that likely feeds it: its confidence is
    capped :data:`TEXTURE_IMPURITY_MARGIN` below the impurity call, the
    mechanism is stated in the rationale, and the analysis itself is annotated
    (``TextureAnalysis.caveat``).  The evidence — axis, r, R² — is preserved
    untouched; only the verdict layer moves.
    """
    strong = [u for u in unmatched
              if u.kind == "unmatched_obs"
              and u.height_over_sigma > IMPURITY_SIGMA]
    impurity = next((a for a in actions if a.kind == "add_impurity_phase"),
                    None)
    detected = [t for t in (texture or []) if t.detected]
    if not strong or impurity is None or not detected:
        return actions
    worst = max(strong, key=lambda u: u.height_over_sigma)
    note = (f"{len(strong)} unmatched observed peak(s) (strongest "
            f"{worst.height_over_sigma:.0f}σ at {worst.two_theta:.3f}°) are "
            f"un-modelled intensity, and the per-reflection extraction "
            f"partitions a foreign peak onto its calculated neighbours — an "
            f"impurity can manufacture exactly this texture signature")
    for t in detected:
        t.caveat = note
    cap = round(max(impurity.confidence - TEXTURE_IMPURITY_MARGIN, 0.0), 3)
    for action in actions:
        if action.kind == "refine_preferred_orientation" and action.confidence > cap:
            action.confidence = cap
            action.rationale += ("; capped below add_impurity_phase — " + note)
            if "add_impurity_phase" not in action.alternatives:
                action.alternatives = (["add_impurity_phase"]
                                       + list(action.alternatives))
    return actions


def _instrument_width_action(trend: TrendAnalysis,
                             peers: list[SuggestedAction]
                             ) -> list[SuggestedAction]:
    """``refine_profile_widths``: the instrument-side reading of a width trend.

    Emitted as a peer alternative whenever a width template is significant
    (``peers`` non-empty), because the trend evidence cannot separate the two
    sides: the instrument's Gaussian polynomial U·tan²θ + V·tanθ + W spans the
    same shapes over any realistic 2θ range, and Toby (2024) §4's example of a
    misleading largest derivative is exactly an instrument width standing in
    for the sample term (the U/V/W case WP-1050 measured from the other side).
    The paths are :data:`_INSTRUMENT_WIDTH_PATHS` — the Gaussian half only,
    for the reason on that constant.

    Confidence is half the leading sample action's — the same runner-up
    discount ``_trend_actions`` applies — for a protocol reason: instrument
    widths belong to a calibration standard (``lab_calibrate``), so on an
    unknown the sample terms are the first reading, and this is the one to
    reach for when they leave the trend standing.
    """
    if not peers:
        return []
    top = max(peers, key=lambda a: a.confidence)
    for peer in peers:
        peer.alternatives = list(peer.alternatives) + ["refine_profile_widths"]
    return [SuggestedAction(
        kind="refine_profile_widths",
        confidence=round(0.5 * top.confidence, 3),
        rationale=(
            f"the same width trend read from the instrument side "
            f"({trend.misfit_share:.0%} of χ²): the Gaussian polynomial "
            "U·tan²θ + V·tanθ + W spans the sample templates' shapes over "
            "this range, so a width trend alone cannot separate instrument "
            "from sample broadening. Instrument widths belong to a "
            "calibration standard, so try the sample terms first — and free "
            "these when they leave the trend standing: a Lorentzian sample "
            "FWHM cannot reproduce a Gaussian variance deficit"),
        parameter_paths=list(_INSTRUMENT_WIDTH_PATHS),
        alternatives=[a.kind for a in peers])]


def suggest_actions(attributions: list[RegionAttribution],
                    trends: list[TrendAnalysis],
                    unmatched: list[UnmatchedPeak],
                    *, rwp: float,
                    ticks: list[float] | None = None,
                    geometry: str | None = None,
                    wavelength: float | None = None) -> list[SuggestedAction]:
    """Build the typed action list from Layers 0-1.

    ``geometry`` picks the position-action map (:data:`_POSITION_ACTIONS_BY_
    GEOMETRY`); ``None`` keeps the Bragg-Brentano one every caller got before
    the map was keyed.  A template the chosen map has no entry for yields no
    action.  For a capillary such a template cannot even be offered
    (``POSITION_TEMPLATES``); on ``flat_plate_transmission`` it *is* offered
    and deliberately maps to nothing — the trend reports the shape, and there
    is no parameter the suggestion could legally free (WP-1003).

    ``wavelength`` lets the width size template's rationale quote the width as
    an apparent crystallite size (:func:`_size_clause`); ``None`` is *no claim*
    and leaves the text as it was, which is what a caller with no instrument in
    hand gets.
    """
    actions: list[SuggestedAction] = []
    by_obs = {t.observable: t for t in trends}
    position_actions = _POSITION_ACTIONS_BY_GEOMETRY.get(geometry or "",
                                                         _POSITION_ACTIONS)

    if "position" in by_obs:
        actions += _trend_actions(by_obs["position"], position_actions, "deg")
    if "width" in by_obs:
        width_actions = _trend_actions(by_obs["width"], _WIDTH_ACTIONS, "deg",
                                       wavelength=wavelength)
        actions += width_actions
        actions += _instrument_width_action(by_obs["width"], width_actions)

    # intensity trend vs sin²θ/λ² is the ADP signature; its constant term is
    # a scale error
    intensity = by_obs.get("intensity")
    if intensity is not None and intensity.templates:
        importance = min(1.0, intensity.misfit_share / 0.25)
        best = max(intensity.templates, key=lambda t: t.r2).name
        quality = max(0.0, min(1.0, max(t.r2 for t in intensity.templates)))

        def _conf(name: str) -> float:
            c = quality * importance
            return round(float(c if name == best else 0.5 * c), 3)

        adp = _significant(intensity.templates, "sin2_over_lambda2")
        if adp is not None:
            actions.append(SuggestedAction(
                kind="refine_biso", confidence=_conf("sin2_over_lambda2"),
                rationale=(f"relative intensity error trends with sin²θ/λ² "
                           f"({adp[0]:+.3g} ± {adp[1]:.2g} Å⁻²·rel, "
                           f"{intensity.misfit_share:.0%} of χ²) — the atomic "
                           "displacement-parameter signature"),
                parameter_paths=["phases.*.atoms.*.biso"],
                alternatives=["increase_background_flexibility", "refine_scale"]))
        const = _significant(intensity.templates, "constant")
        if const is not None:
            actions.append(SuggestedAction(
                kind="refine_scale", confidence=_conf("constant"),
                rationale=(f"intensities are uniformly {const[0]:+.1%} off across "
                           f"the pattern ({intensity.misfit_share:.0%} of χ²) — "
                           "an angle-independent scale error"),
                parameter_paths=["phases.*.scale"],
                alternatives=["refine_biso"]))

    # asymmetry: a significant coefficient in the low-angle regions
    low = [a for a in attributions if a.gates_passed and a.mean_two_theta < 40.0]
    asym = [c for a in low for c in a.coefficients
            if c.kind == "asymmetry" and c.significant]
    if asym:
        actions.append(SuggestedAction(
            kind="refine_axial_asymmetry", confidence=0.5,
            rationale=(f"axial-divergence shape term is significant in "
                       f"{len(asym)} low-angle region(s)"),
            parameter_paths=["instrument.geometry.axial_sl",
                             "instrument.geometry.axial_hl"],
            two_theta_range=(min(a.two_theta_lo for a in low),
                             max(a.two_theta_hi for a in low))))

    actions += layer0_actions(unmatched, attributions, ticks=ticks)

    # regions that failed the validity radius: the model is far enough off that
    # linearising is wrong — say so instead of proposing a small correction.
    # One emitter with the abstained branch (WP-1054; the shared condition and
    # its history are in reindex_action's docstring).
    reindex = reindex_action(attributions)
    if reindex is not None:
        actions.append(reindex)

    actions.sort(key=lambda a: -a.confidence)
    return actions


def apply_strategy_veto(actions: list[SuggestedAction], plan, *,
                        free_paths: list[str] | None = None
                        ) -> list[SuggestedAction]:
    """Mark actions the staged plan already covers.  **The engine wins.**

    An action whose parameters the plan refines (in any stage) is redundant;
    one whose parameters are already free in the current fit is likewise not
    news.  Both are annotated rather than removed, so the report still shows
    *why* the engine thinks the misfit is explained.
    """
    import fnmatch

    planned: set[str] = set()
    for stage in getattr(plan, "stages", []):
        planned.update(stage.turn_on)
    free = set(free_paths or [])

    for action in actions:
        for path in action.parameter_paths:
            if any(fnmatch.fnmatchcase(g, path) or fnmatch.fnmatchcase(path, g)
                   for g in planned):
                action.vetoed_by = f"already refined by the staged plan ({path})"
                break
            if any(fnmatch.fnmatchcase(f, path) for f in free):
                action.vetoed_by = f"already free in this refinement ({path})"
                break
    return actions


def predict_then_verify(refinement, data, action: SuggestedAction, *,
                        min_improvement: float = 0.01) -> VerificationOutcome:
    """Try an action on a branch, keep it only if χ² actually improves.

    Runs on a *branch* of the refinement history when one is available, so a
    rejected action leaves no trace in the working state — the rollback is
    structural, not a manual undo.  ``min_improvement`` is the fractional χ²
    reduction required to accept.
    """
    from ..strategy.staged import Stage

    if refinement.result_ is None:
        raise RuntimeError("run a fit before verifying an action")
    before = refinement.result_.statistics.chi2
    if not action.parameter_paths:
        return VerificationOutcome(
            kind=action.kind, predicted_delta_chi2=action.expected_delta_chi2,
            observed_delta_chi2=0.0, accepted=False,
            reason="action carries no refinable parameter paths")

    # read before the trial: without a history it runs in place, and the
    # values the restricted fit held are then gone
    restricted = refinement.result_
    held = {row.path: row.value for row in refinement.parameters()}
    trial = refinement.branch() if refinement.history is not None else refinement
    stage = Stage(f"verify:{action.kind}", list(action.parameter_paths))
    try:
        # ``telemetry=False``: this is a trial the *package* runs, one per
        # candidate action, and a recorder here writes a run directory for each
        # — the same "sixty directories for one job" a series declines
        # (WP-1403).  The run the caller asked about is the fit they started.
        result = trial.run_stage(data, stage, telemetry=False)
    except Exception as exc:  # a failed trial is a rejection, not a crash
        return VerificationOutcome(
            kind=action.kind, predicted_delta_chi2=action.expected_delta_chi2,
            observed_delta_chi2=0.0, accepted=False,
            reason=f"trial refinement failed: {exc}")

    after = result.statistics.chi2
    observed = before - after
    accepted = observed > min_improvement * abs(before)
    try:
        comparison = _freed_comparison(restricted, held, trial)
    except ValueError:      # nothing newly freed, or a stage hold moved
        comparison = None
    return VerificationOutcome(
        kind=action.kind, predicted_delta_chi2=action.expected_delta_chi2,
        observed_delta_chi2=float(observed), accepted=bool(accepted),
        reason=(f"χ² {before:.4g} → {after:.4g} "
                f"({observed / abs(before):+.2%}); "
                f"{'accepted' if accepted else 'rolled back'}"),
        comparison=comparison)


def _rival_trial(refinement):
    """A private working tree for one rival fit — never the caller's own.

    ``branch()`` where there is a history to branch (the default once a fit has
    run), and a fresh :class:`~rietx.refine.Refinement` over copies of the
    same models where the caller disabled history.  :func:`predict_then_verify`
    can fall back to running in place because it runs *one* trial and judges it
    by χ²; two rivals run in place would start the second from the first's
    converged state and leave the caller standing on it.
    """
    from ..refine import Refinement

    if refinement.history is not None:
        return refinement.branch()
    trial = Refinement(refinement.structure, refinement.instrument,
                       backend=refinement._backend, solver=refinement._solver,
                       history=False)
    trial._mode = refinement._mode
    trial._two_theta_limits = refinement._two_theta_limits
    trial._free_paths = list(refinement._free_paths)
    return trial


def _rival_pair(finding) -> tuple[str, str]:
    """``(held, partner)`` from a finding or a bare pair of paths."""
    if isinstance(finding, ExchangeFinding):
        if finding.partner is None:
            raise ValueError(
                f"the exchange row for {finding.held!r} names no partner with "
                "a null identity, so there is no swap to run: its loadings "
                f"are {sorted(finding.partners)}")
        return finding.held, finding.partner
    held, partner = finding
    return str(held), str(partner)


def compare_rivals(refinement, data, finding: "ExchangeFinding | tuple[str, str]",
                   ) -> RivalComparison:
    """Fit each member of an exchangeable pair alone, the other at its null.

    This is the experiment the exchange clause names, run on demand — the
    on-branch, solve-bearing peer of :func:`predict_then_verify`, and like it
    a *pull*: nothing in :func:`~rietx.report.build_report` calls it, so
    building a report still performs no fits.

    Why it exists.  The report's exchange finding is built from an R², which is
    a **geometric** measure of how far a held parameter's column lies inside
    the fitted span — it says the two parameters are hard to tell apart in the
    design matrix, and nothing whatever about whether the counting statistics
    in hand can tell them apart.  On real SRM 660c they can: at R² = 0.9977 the
    zero-only fit lands at Rwp 0.09361 / χ² 4.0752 against the
    displacement-only 0.08661 / 3.4890 on 5332 points, and the zero-only model
    biases *a* by +100 ppm (4.157310 against the certified-protocol 4.156895).
    Two warm bounded fits cost seconds; the round that assumed the answer
    instead cost 1.7 M tokens (``tests/CLAUDE.md`` § "An eval's expected answer
    is a measurement").

    **The rest of the free set is unchanged in both fits**, so the two differ
    by *which* member of the pair is free and never by how many parameters are.
    That is what makes the raw χ² comparison fair without an information
    criterion, and ``RivalFit.n_free`` publishes it so the claim can be
    checked.

    Two refusals, both by name rather than by a quiet empty answer:

    - a pair member with **no null identity** — a cell edge or a scale has no
      value the data could be accused of failing to distinguish it from, so
      there is no "held at its null" to run.  Such a pair is resolved by
      protocol instead: fix the zero on a calibrant, widen the window, or
      measure a standard;
    - **Pawley mode**, mirroring :func:`.optimize.identifiability
      .exchangeability_scan`'s own fence — there the fitted span includes the
      per-hkl intensity block, and a rival measured against the wrong span is
      worse than no rival.

    The answer carries no verdict (:class:`RivalComparison`).
    """
    from ..optimize.identifiability import NULL_IDENTITY
    from ..strategy.staged import Stage

    if refinement.result_ is None:
        raise RuntimeError("run a fit before comparing rivals")
    if refinement.result_.mode == "pawley":
        raise ValueError(
            "compare_rivals is not defined in Pawley mode: the fitted span "
            "includes the per-hkl intensity block, so a rival fit is measured "
            "against a different span than the exchange it answers")
    pair = _rival_pair(finding)
    for path in pair:
        if path not in NULL_IDENTITY:
            raise ValueError(
                f"{path!r} has no null identity, so it has no 'held at its "
                "null' fit: this pair is resolved by protocol (fix the zero "
                "on a calibrant, widen the window, measure a standard), not "
                f"by a swap; nulls are defined for {sorted(NULL_IDENTITY)}")

    fits = []
    for freed, other in (pair, pair[::-1]):
        trial = _rival_trial(refinement)
        trial.set_vary([other], False)
        trial.set_values({other: NULL_IDENTITY[other]})
        trial.set_vary([freed], True)
        result = trial.run_stage(data, Stage(f"rival:{freed}", [freed]),
                                 telemetry=False)   # a trial, not a run
        row = next((p for p in result.parameters if p.path == freed), None)
        fits.append(RivalFit(
            freed_path=freed, held_path=other, held_at=NULL_IDENTITY[other],
            chi2=result.statistics.chi2, rwp=result.statistics.rwp,
            n_points=result.statistics.n_points,
            # the solver's own count: ``result.parameters`` also carries tied
            # entries, which are not free parameters
            n_free=result.statistics.n_free_parameters,
            freed_value=row.value if row else None,
            freed_esd=row.stderr if row else None,
            node_id=result.node_id))
    return RivalComparison(rivals=fits,
                           chi2_ratio=float(fits[0].chi2 / fits[1].chi2))


def estimate_delta_chi2(result: RefinementResult,
                        attributions: list[RegionAttribution]) -> float | None:
    """Optimistic χ² reduction if every gated region's misfit were removed.

    Optimistic *within the gated regions* — it assumes the linear model is exact
    and the corrections mutually compatible.  It is **not** a bound on what
    applying an action achieves: a refinement also improves regions that failed a
    gate and stretches of pattern no region entry covers, and WP-1012 measured the
    observed reduction exceeding this estimate by 0.8 % on a cell correction
    (16.19 predicted, 16.33 observed).  It is also one number for the whole
    report, which ``build_report`` stamps on every action, so it ranks nothing —
    see :class:`~rietx.report.schemas.SuggestedAction`.
    """
    usable = [a for a in attributions if a.gates_passed]
    if not usable:
        return None
    share = sum(a.chi2_share * max(min(a.r2, 1.0), 0.0) for a in usable)
    return float(share * result.statistics.chi2 * np.clip(result.statistics.n_points, 1, None)
                 / max(result.statistics.n_points, 1))
