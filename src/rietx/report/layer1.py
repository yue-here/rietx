"""FitReport Layer 1: gated linear misfit attribution.

For each region the residual Δ = y_obs − y_calc is projected onto a
**shape-derivative basis** built analytically from the profile itself — not
from the parameter Jacobian, so the answer is "the peaks here are 0.01° low
and 5 % too weak", independent of which parameters happen to be free:

    Δ(2θ) ≈ a_I·Σ_k I_k Ω_k        (relative intensity error)
          + a_p·Σ_k I_k ∂Ω_k/∂pos  (Δ2θ, degrees)
          + a_w·Σ_k I_k ∂Ω_k/∂Γ    (ΔΓ, degrees)
          + a_η·Σ_k I_k ∂Ω_k/∂η    (Δη)
          + a_S·Σ_k I_k ∂Ω_k/∂(S/L)(axial asymmetry)

The five columns are **not orthogonal**, so they are fitted in one joint
weighted solve and the Gram matrix's condition number is reported alongside;
independent dot-products would cross-contaminate (a width error partly reads
as an intensity error and vice versa).

Nothing here is trustworthy unconditionally, hence the gates
(:mod:`.schemas` pins the thresholds):

* **local R²** — does this basis explain the region's misfit at all?
* **validity radius** — a linearised shift is meaningful only well inside the
  peak.  A peak 5 FWHM away must produce "re-detect, don't linearise", never a
  confident small-offset reading.
* **resolvability** — Gram condition number and per-coefficient significance.
* **global maturity** — if the fit is immature the whole layer *abstains*
  rather than attributing structure to what is really a bad starting model.

On top of the per-region view, :func:`analyse_trends` regresses the region
coefficients against the angular templates that per-region views structurally
miss (position vs constant / cosθ / sin2θ / tanθ, width vs 1/cosθ and tanθ,
intensity vs sin²θ/λ² — the ADP signature), reporting the inter-template
collinearity *over the range actually sampled* so an unseparable pair is
declared unseparable instead of resolved into a confident wrong singleton.
"""

from __future__ import annotations

import numpy as np

from ..model.forward import CompiledModel, DerivativeBases
from ..optimize import lapack
from .schemas import (
    CONTENTS_MAX_TEMPLATE_R2,
    CONTENTS_MIN_INTENSITY_SHARE,
    CONTENTS_MIN_REGIONS,
    CONTENTS_MIN_SIGN_MINORITY,
    MATURITY_MAX_RWP,
    MATURITY_MIN_EXPLAINED_FRACTION,
    MATURITY_MIN_MISFIT_SHARE,
    MAX_GRAM_CONDITION,
    MIN_COEF_SIGNIFICANCE,
    MIN_REGION_CHI2_RED,
    MIN_REGION_R2,
    REINDEX_MIN_FAR_FRACTION,
    REINDEX_MIN_FAR_REGIONS,
    RESOLUTION_LIMITED_MIN_FRACTION,
    RESOLUTION_LIMITED_MIN_R2,
    RESOLUTION_LIMITED_MIN_REGIONS,
    SEPARABILITY_MIN_SS_RATIO,
    VALIDITY_RADIUS_FWHM,
    BasisCoefficient,
    GateFailure,
    Region,
    RegionAttribution,
    TrendAnalysis,
    TrendTemplate,
)

_KINDS = ("intensity", "position", "width", "mixing", "asymmetry")


def _region_columns(model: CompiledModel, bases: DerivativeBases,
                    lo: float, hi: float
                    ) -> tuple[np.ndarray, np.ndarray, float, float, int]:
    """Assemble the (5, n_points_in_region) basis for one region.

    Every peak whose *centre* lies in the region contributes; its full frozen
    window is used, clipped to the region, so a peak's tail outside the region
    is simply not scored (regions are cut between peaks).
    """
    m = (model.tt >= lo) & (model.tt <= hi)
    idx = np.nonzero(m)[0]
    if len(idx) == 0:
        return np.zeros((5, 0)), idx, 0.0, 0.0, 0
    i_start, i_stop = int(idx[0]), int(idx[-1]) + 1
    cols = np.zeros((5, i_stop - i_start), dtype=np.float64)

    n_refl = 0
    tt_sum = fwhm_sum = weight_sum = 0.0
    # every drawn component: on a phase whose magnetic peaks have their own
    # width (WP-1343) the nuclear rows alone give a magnetic-only reflection
    # zero amplitude here, and its misfit would be attributed elsewhere
    counted: set[tuple[int, int, int]] = set()
    for ip in range(len(bases.planes)):
        for rows, peaks in bases.component_entries(ip):
            for (il, k, w0, w1, omega, d_pos, d_gamma, d_eta, d_sl,
                 _d_hl) in rows:
                pos, gamma, _eta, intensity = peaks[il]
                centre = pos[k]
                if not (lo <= centre <= hi):
                    continue
                if (ip, il, k) not in counted:   # one reflection, not one draw
                    counted.add((ip, il, k))
                    n_refl += 1
                weight = abs(float(intensity[k]))
                tt_sum += weight * float(centre)
                fwhm_sum += weight * float(gamma[k])
                weight_sum += weight
                a, b = max(w0, i_start), min(w1, i_stop)
                if b <= a:
                    continue
                sl_a, sl_b = a - w0, b - w0
                dst_a, dst_b = a - i_start, b - i_start
                amp = float(intensity[k])
                cols[0, dst_a:dst_b] += amp * omega[sl_a:sl_b]
                cols[1, dst_a:dst_b] += amp * d_pos[sl_a:sl_b]
                cols[2, dst_a:dst_b] += amp * d_gamma[sl_a:sl_b]
                cols[3, dst_a:dst_b] += amp * d_eta[sl_a:sl_b]
                if d_sl is not None:
                    cols[4, dst_a:dst_b] += amp * d_sl[sl_a:sl_b]

    mean_tt = tt_sum / weight_sum if weight_sum > 0 else 0.5 * (lo + hi)
    mean_fwhm = fwhm_sum / weight_sum if weight_sum > 0 else 0.0
    return cols, np.arange(i_start, i_stop), mean_tt, mean_fwhm, n_refl


def attribute_region(model: CompiledModel, bases: DerivativeBases,
                     region: Region, delta: np.ndarray, sqrt_w: np.ndarray
                     ) -> RegionAttribution | None:
    """Joint weighted solve of one region's residual against the shape basis."""
    cols, idx, mean_tt, mean_fwhm, n_refl = _region_columns(
        model, bases, region.two_theta_lo, region.two_theta_hi)
    if len(idx) == 0 or n_refl == 0:
        return None

    sw = sqrt_w[idx]
    a = (cols * sw).T                       # (n_points, 5)
    b = delta[idx] * sw
    live = np.nonzero(np.linalg.norm(a, axis=0) > 0.0)[0]
    if len(live) == 0 or len(idx) <= len(live):
        return None
    a = a[:, live]

    gram = a.T @ a
    # Resolvability is about the *angles* between the basis columns, not their
    # units: ∂Ω/∂pos is ~1/FWHM times larger than Ω, which alone puts cond(G)
    # near 10⁴ in every region.  Condition the scale-normalised Gram (a
    # correlation matrix, cf. Belsley-Kuh-Welsch) so the number means
    # collinearity — measured range 17 … 6×10⁴ on the same data where the raw
    # number sat at 7×10³ … 1×10⁶ regardless of separability.
    scale = np.linalg.norm(a, axis=0)
    normed = a / scale
    cond = float(lapack.cond(normed.T @ normed))
    coef, *_ = lapack.lstsq(a, b, rcond=None)
    resid = b - a @ coef
    ss_tot = float(b @ b)
    r2 = float(1.0 - (resid @ resid) / ss_tot) if ss_tot > 0 else 0.0

    # Gram covariance, scaled by the region's own residual variance
    dof = max(len(idx) - len(live), 1)
    sigma2 = float(resid @ resid) / dof
    cov = lapack.pinv(gram) * sigma2
    err = np.sqrt(np.maximum(np.diag(cov), 0.0))

    # relative importance of each term: how much signal its fitted amplitude
    # actually puts into the region, not merely whether it is nonzero
    contribution = (np.abs(coef) * scale) ** 2
    total_contribution = float(contribution.sum())

    coefficients: list[BasisCoefficient] = []
    for slot, c, e, contrib in zip(live, coef, err, contribution, strict=True):
        coefficients.append(BasisCoefficient(
            kind=_KINDS[slot], value=float(c), stderr=float(e),
            significant=bool(abs(c) > MIN_COEF_SIGNIFICANCE * e) if e > 0 else False,
            share=float(contrib / total_contribution) if total_contribution > 0 else 0.0))

    # is there anything to attribute?  On a region already fitted to the
    # counting noise the basis legitimately explains nothing (R² ≈ 0), which
    # must not be reported as a failed gate.
    chi2_red = ss_tot / max(len(idx), 1)
    has_misfit = chi2_red > MIN_REGION_CHI2_RED

    failures: list[GateFailure] = []
    if not has_misfit:
        failures.append(GateFailure(
            code="no_significant_misfit",
            message=f"no_significant_misfit(χ²_red={chi2_red:.2f})"))
    else:
        if r2 < MIN_REGION_R2:
            failures.append(GateFailure(
                code="local_r2", message=f"local_r2={r2:.2f}<{MIN_REGION_R2}"))
        if cond > MAX_GRAM_CONDITION:
            failures.append(GateFailure(
                code="gram_condition",
                message=f"gram_condition={cond:.1e}>{MAX_GRAM_CONDITION:.0e}"))
        shift = next((c.value for c in coefficients if c.kind == "position"), 0.0)
        if mean_fwhm > 0 and abs(shift) > VALIDITY_RADIUS_FWHM * mean_fwhm:
            failures.append(GateFailure(
                code="outside_validity_radius",
                message=(
                    f"outside_validity_radius(|Δ2θ|={abs(shift):.3f}°>"
                    f"{VALIDITY_RADIUS_FWHM}·FWHM"
                    f"={VALIDITY_RADIUS_FWHM * mean_fwhm:.3f}°)"
                    " — re-detect the peak rather than linearising")))

    return RegionAttribution(
        two_theta_lo=region.two_theta_lo, two_theta_hi=region.two_theta_hi,
        n_reflections=n_refl, chi2_share=region.chi2_share,
        mean_two_theta=mean_tt, mean_fwhm=mean_fwhm,
        coefficients=coefficients, r2=r2, gram_condition=cond,
        chi2_reduced=float(chi2_red), has_significant_misfit=bool(has_misfit),
        gates_passed=not failures, gate_failures=failures,
    )


def attribute_regions(model: CompiledModel, values: dict[str, float],
                      regions: list[Region], *,
                      shapes: CompiledModel | None = None) -> list[RegionAttribution]:
    """Layer-1 attribution for every region (gates evaluated per region).

    The misfit is read off ``model`` and the shape basis off ``shapes``
    (``model`` when not given), which must share its grid: the report hands in
    a model at the closing precision and one at the declared stages' precision
    (``report._reading_models``).
    """
    y_calc = model.evaluate(values)
    delta = model.y_obs - y_calc
    sqrt_w = 1.0 / model.sigma
    bases = (model if shapes is None else shapes).derivative_bases(values)
    out = []
    for region in regions:
        att = attribute_region(model, bases, region, delta, sqrt_w)
        if att is not None:
            out.append(att)
    return out


def maturity_gate(rwp: float, attributions: list[RegionAttribution]
                  ) -> str | None:
    """Global abstention check.  Returns a reason, or None when Layer 1 may speak.

    Attributing a *bad model* to specific small parameter errors is the
    failure mode this prevents: with Rwp of 50 % the residual is dominated by
    something the shape basis cannot represent at all, and any coefficient it
    returns is an artefact of projecting onto the wrong space.

    A fit with **no** significantly-misfitting region does not abstain: there
    is simply nothing to attribute, which is a legitimate (and common) answer
    that Layer 1 should be able to give.  Abstention is only for the case
    where real misfit exists but cannot be read reliably.
    """
    if rwp > MATURITY_MAX_RWP:
        return (f"The fit is immature (Rwp={rwp:.3f} > {MATURITY_MAX_RWP}). "
                "Fix the model and starting values first.")

    misfitting = [a for a in attributions if a.has_significant_misfit]
    misfit_share = sum(a.chi2_share for a in misfitting)
    if misfit_share <= MATURITY_MIN_MISFIT_SHARE:
        return None            # nothing substantial to attribute

    usable_share = sum(a.chi2_share for a in misfitting if a.gates_passed)
    if usable_share < MATURITY_MIN_EXPLAINED_FRACTION * misfit_share:
        return (f"Misfitting regions carry {misfit_share:.0%} of χ², but only "
                f"{usable_share / misfit_share:.0%} of that sits in regions "
                f"the local gates accept. "
                f"Layer 1 needs {MATURITY_MIN_EXPLAINED_FRACTION:.0%}.")
    return None


def abstention_flavour(rwp: float, attributions: list[RegionAttribution]
                       ) -> tuple[str, str | None]:
    """Classify an abstention :func:`maturity_gate` has already decided.

    Returns ``(kind, extra)``: ``kind`` is the
    :attr:`~rietx.report.schemas.FitReport.abstained_kind` value and
    ``extra``, when set, is the resolution-limited sentence appended to the
    reason.  Purely a *reading* of the per-region gate evidence — no
    threshold that decides abstention is consulted, so the abstain/speak
    boundary cannot move here (WP-1057).

    The order of the arms is the argument (measured grounds on the schema
    constants): widespread validity failure is position-family model error
    and must win even though a wrong cell fails the Gram gate widely too;
    only past it can Gram-dominance with high local R² be read as "the data's
    resolution limits attribution", the state broad-peak specimens
    (nanoparticles, MOFs) live in permanently.
    """
    if rwp > MATURITY_MAX_RWP:
        return "immature", None
    misfitting = [a for a in attributions if a.has_significant_misfit]
    failing = [a for a in misfitting if not a.gates_passed]
    far = [a for a in failing
           if any(f.code == "outside_validity_radius" for f in a.gate_failures)]
    if (len(far) >= REINDEX_MIN_FAR_REGIONS
            and len(far) >= REINDEX_MIN_FAR_FRACTION * len(misfitting)):
        return "unreadable", None    # reindex_action carries this story
    gram = [a for a in failing
            if any(f.code == "gram_condition" for f in a.gate_failures)]
    gram_only = [a for a in failing if a.gate_failures
                 and all(f.code == "gram_condition" for f in a.gate_failures)]
    if (failing and len(gram) >= RESOLUTION_LIMITED_MIN_FRACTION * len(failing)
            and len(gram_only) >= RESOLUTION_LIMITED_MIN_REGIONS):
        median_r2 = float(np.median([a.r2 for a in gram_only]))
        if median_r2 >= RESOLUTION_LIMITED_MIN_R2:
            extra = (
                f"This abstention is resolution-limited. "
                f"{len(gram)} of {len(failing)} gate-failing region(s) fail "
                f"the Gram condition. "
                f"The {len(gram_only)} failing nothing else carry median "
                f"local R²={median_r2:.2f}. "
                f"The shape basis explains the misfit, but its edit "
                f"directions are indistinguishable at this resolution. "
                f"That is not evidence the model is wrong. "
                f"The misfit is readable in aggregate (Rwp, the Le Bail gap) "
                f"but not attributable per kind. "
                f"On broad-peak data this can be a legitimate stopping point.")
            return "resolution_limited", extra
    return "unreadable", None


def contents_signature(trends: list[TrendAnalysis],
                       attributions: list[RegionAttribution]) -> str | None:
    """The incoherent-intensity summary clause, or None (WP-1057).

    Names the pattern the pore-proxy scenario measured and every angular
    analysis is structurally blind to: per-region intensity errors that are
    individually large, collectively dominant, and *alternating in sign* with
    no angular trend.  A scale error is single-sign, an ADP error trends with
    sin²θ/λ², texture follows an axis — sign alternation across reflections
    is structure-factor interference, which only a wrong scattering *content*
    (guest species, pore contents, wrong occupancy, missing/excess atom)
    produces.  The evidence stays where it already is — per-region
    coefficients in ``attribution``, template scores in ``trends`` — this
    merely states the inference those numbers support; thresholds and their
    measured grounds are pinned in :mod:`.schemas`.
    """
    intensity = next((t for t in trends if t.observable == "intensity"), None)
    if intensity is None or not intensity.templates:
        return None
    if intensity.misfit_share < CONTENTS_MIN_INTENSITY_SHARE:
        return None
    best_r2 = max(t.r2 for t in intensity.templates)
    if best_r2 >= CONTENTS_MAX_TEMPLATE_R2:
        return None
    sig = [c.value for a in attributions if a.gates_passed
           for c in a.coefficients if c.kind == "intensity" and c.significant]
    if len(sig) < CONTENTS_MIN_REGIONS:
        return None
    n_weak = sum(1 for v in sig if v > 0)     # calc too weak there
    n_strong = len(sig) - n_weak
    if min(n_weak, n_strong) < CONTENTS_MIN_SIGN_MINORITY * len(sig):
        return None
    lo = min(abs(v) for v in sig)
    hi = max(abs(v) for v in sig)
    return (f"Intensity misfit is incoherent: {intensity.misfit_share:.0%} of "
            f"χ² sits in {len(sig)} region(s) whose relative intensity errors "
            f"alternate in sign (calculated too weak in {n_weak}, too strong "
            f"in {n_strong}, |error| {lo:.0%}–{hi:.0%}).\n"
            f"No angular trend explains it (best template R²={best_r2:.2f}).\n"
            f"That is structure-factor interference, the signature of "
            f"un-modelled scattering contents (guest or pore species, wrong "
            f"occupancy) rather than a scale, ADP or texture error.")


# ----------------------------------------------------------------------
# hkl-grouped angular trends
# ----------------------------------------------------------------------
#: Which position templates a geometry may be offered, in the *same* names
#: ``report/layer2.py``'s ``_POSITION_ACTIONS`` uses (and that
#: ``schemas/indexing.py``'s ``SHIFT_TEMPLATES`` narrows from).  A template is
#: a candidate *cause*, so offering one whose cause does not exist in this
#: geometry is the confident wrong singleton the report exists to prevent:
#: before WP-1073 a capillary fit whose peaks followed cos θ was told to refine
#: ``sample_displacement``, which ``ParameterTable`` force-fixes outside
#: ``bragg_brentano`` — a suggestion that cannot be taken.  ``cos_2theta`` is
#: eq (4)'s perpendicular half and exists only for a capillary; ``sin_2theta``
#: is shared but means different physics on either side (flat-plate
#: transparency, capillary along-beam offset), which is why the *action* map is
#: keyed the same way rather than this one alone.
#:
#: ``flat_plate_transmission`` keeps all four templates *as evidence*: the
#: geometry models no displacement at all (see :class:`~rietx.schemas.
#: instrument.Geometry`), but the diagnosis is the right one there — a flat
#: specimen off the axis — where for a capillary neither the shape nor the
#: parameter was.  WP-1003 settled the split 1073 left open: the shape stays
#: here, and layer 2's action map carries no entry for it, so the trend is
#: reported with no suggestion rather than naming a force-fixed parameter.
POSITION_TEMPLATES: dict[str, tuple[str, ...]] = {
    "bragg_brentano": ("constant", "cos_theta", "sin_2theta", "tan_theta"),
    "debye_scherrer": ("constant", "sin_2theta", "cos_2theta", "tan_theta"),
    "flat_plate_transmission": ("constant", "cos_theta", "sin_2theta",
                                "tan_theta"),
}


def _templates(observable: str, two_theta: np.ndarray, wavelength: float,
               geometry: str | None = None) -> dict[str, np.ndarray]:
    """The candidate shapes for one observable, narrowed to ``geometry``.

    ``geometry=None`` returns every position shape the package knows — the
    union, which is what a geometry-free caller narrows from
    (``indexing.quality.shift_template_basis``) and what the width and
    intensity observables always get, having no geometry dependence.
    """
    theta = np.radians(two_theta / 2.0)
    if observable == "position":
        shapes = {
            "constant": np.ones_like(theta),          # zero-point error
            "cos_theta": np.cos(theta),               # specimen displacement
            "sin_2theta": np.sin(2.0 * theta),        # transparency, or the
                                                      # capillary along-beam
                                                      # offset (eq 4)
            "cos_2theta": np.cos(2.0 * theta),        # capillary across-beam
                                                      # offset (eq 4)
            "tan_theta": np.tan(theta),               # cell (Δd/d)
        }
        if geometry is None:
            return shapes
        return {n: shapes[n] for n in POSITION_TEMPLATES[geometry]}
    if observable == "width":
        return {
            "inv_cos_theta": 1.0 / np.cos(theta),     # crystallite size
            "tan_theta": np.tan(theta),               # microstrain
        }
    # intensity: I_obs/I_calc ~ exp(−2ΔB·sin²θ/λ²) ⇒ relative error linear
    # in sin²θ/λ² near ΔB = 0
    return {
        "constant": np.ones_like(theta),
        "sin2_over_lambda2": (np.sin(theta) / wavelength) ** 2,
    }


def analyse_trends(attributions: list[RegionAttribution], wavelength: float,
                   geometry: str | None = None) -> list[TrendAnalysis]:
    """Fit the angular templates to the per-region coefficients.

    Only regions that passed their local gates contribute — a coefficient the
    gates rejected is not evidence.  Each template is fitted **alone**, as a
    through-origin nested model, and *not* jointly with the others: they are
    correlated by construction, and a joint fit of collinear templates returns
    physically absurd amplitudes (the inline comment below has the measured
    case).  The ambiguity is expressed instead by how close the runners-up
    come, and the collinearity actually present over the sampled angles
    decides ``separable``.

    ``geometry`` narrows the *position* candidates to the causes that exist on
    that instrument (:data:`POSITION_TEMPLATES`); ``None`` offers them all,
    which is the pre-WP-1073 behaviour and what a caller with no instrument in
    hand gets.
    """
    kind_for = {"position": "position", "width": "width", "intensity": "intensity"}
    out: list[TrendAnalysis] = []
    usable = [a for a in attributions if a.gates_passed]

    for observable, coef_kind in kind_for.items():
        pts = []
        shares = []
        for att in usable:
            c = next((c for c in att.coefficients
                      if c.kind == coef_kind and c.stderr > 0), None)
            if c is not None:
                pts.append((att.mean_two_theta, c.value, c.stderr))
                shares.append(att.chi2_share * c.share)
        if len(pts) < 3:
            out.append(TrendAnalysis(observable=observable, n_regions_used=len(pts)))
            continue

        tt = np.array([p[0] for p in pts])
        val = np.array([p[1] for p in pts])
        w = 1.0 / np.array([p[2] for p in pts])

        templates = _templates(observable, tt, wavelength, geometry)
        names = list(templates)
        design = np.vstack([templates[n] for n in names])
        if len(pts) <= 2:
            out.append(TrendAnalysis(observable=observable, n_regions_used=len(pts)))
            continue

        # Nested model comparison, one template at a time — NOT a joint fit.
        # Jointly fitting collinear templates is numerically ill-posed and
        # returns physically absurd amplitudes (measured: a 0.02° zero-point
        # error came back as a 1.8° "constant" cancelled by a −1.8° "cosθ").
        # Each template is therefore scored alone, and the ambiguity is
        # expressed by how close the runners-up come.
        b = val * w
        # through-origin fits (a template with no intercept), so R² is
        # measured against the uncentred total — "how much of the observed
        # trend does this single physical cause account for"
        ss_tot = float(b @ b)
        fitted: list[TrendTemplate] = []
        for name in names:
            col = (templates[name] * w)[:, None]
            coef, *_ = lapack.lstsq(col, b, rcond=None)
            resid = b - col @ coef
            r2 = float(1.0 - (resid @ resid) / ss_tot) if ss_tot > 0 else 0.0
            dof = max(len(pts) - 1, 1)
            var = float(resid @ resid) / dof / max(float(col.ravel() @ col.ravel()), 1e-300)
            fitted.append(TrendTemplate(name=name, coefficient=float(coef[0]),
                                        stderr=float(np.sqrt(max(var, 0.0))),
                                        r2=r2))

        # collinearity between templates over the angles actually sampled
        norm = design / np.maximum(np.linalg.norm(design, axis=1, keepdims=True), 1e-300)
        gram = np.abs(norm @ norm.T)
        np.fill_diagonal(gram, 0.0)
        collinearity = float(gram.max()) if len(names) > 1 else 0.0

        ranked = sorted(fitted, key=lambda t: -t.r2)
        if len(ranked) > 1:
            # residual-SS ratio: how much more the runner-up leaves unexplained
            best_ss = max(1.0 - ranked[0].r2, 1e-12)
            ratio = (1.0 - ranked[1].r2) / best_ss
        else:
            ratio = np.inf
        out.append(TrendAnalysis(
            observable=observable, n_regions_used=len(pts),
            templates=fitted,
            max_template_collinearity=collinearity,
            separability_ratio=float(min(ratio, 1e6)),
            separable=bool(ratio > SEPARABILITY_MIN_SS_RATIO),
            misfit_share=float(sum(shares)),
        ))
    return out
