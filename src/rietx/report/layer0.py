"""FitReport Layer 0: model-free, agent-native fit diagnostics.

Everything here is computed without linearising the model, so it stays
trustworthy even when the refinement is far from converged — which is exactly
what the gated linear misfit attribution of :mod:`rietx.report.layer1`
cannot claim, and why that layer abstains rather than guessing:

* global agreement indices;
* the cumulative-χ² curve vs 2θ, whose steps localise the regions where the
  model fails (David, 2004, J. Res. NIST 109);
* per-region local Rwp / χ² share over peak-cluster regions segmented from the
  union of calculated tick positions and observed/residual peaks (so an
  unindexed impurity peak still gets a region);
* unmatched-peak lists: residual peaks with no calculated reflection nearby
  (impurity / missing-phase candidates) and calculated reflections with no
  observed intensity.

All quantities are 1/σ²-weighted; both Δ and Δ/σ views are reported.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from ..schemas.results import RefinementResult
from .background import assess_background
from .schemas import (
    BACKGROUND_ABSORPTION_NOTABLE,
    LEBAIL_GAP_CYCLES,
    OFF_REGION_CHI2_RED_HIGH,
    OFF_REGION_DW_LOW,
    BackgroundEvidence,
    FitReport,
    LeBailGap,
    Region,
    UnmatchedPeak,
)


def _segment_regions(tt: np.ndarray, positions: np.ndarray, gap_deg: float) -> list[tuple[float, float]]:
    """Merge peak positions closer than ``gap_deg`` into cluster regions."""
    if len(positions) == 0:
        return []
    pos = np.sort(positions)
    regions: list[tuple[float, float]] = []
    lo = hi = pos[0]
    for p in pos[1:]:
        if p - hi <= gap_deg:
            hi = p
        else:
            regions.append((lo - gap_deg / 2, hi + gap_deg / 2))
            lo = hi = p
    regions.append((lo - gap_deg / 2, hi + gap_deg / 2))
    return regions


def residual_peak_indices(resid_norm: np.ndarray, *,
                          min_peak_sigma: float) -> np.ndarray:
    """Indices of the positive residual peaks — one definition, two readers.

    :func:`build_layer0` keeps the ones with no calculated tick within
    ``match_tol_deg`` as ``unmatched_obs`` and drops the rest; the satellite
    arm (:mod:`rietx.report.satellites`) needs the **whole** list, because a
    residual peak sitting on a nuclear line, or on a reciprocal-lattice point
    the nuclear structure factor forbids, is the k = 0 evidence — and it sorts
    them by its own radius rather than by ``match_tol_deg`` (that module's
    docstring says why).  Factored out rather than repeated so the two cannot
    disagree about what a peak is.
    """
    peaks, _ = find_peaks(resid_norm, height=min_peak_sigma, distance=5)
    return peaks


def lebail_gap(model, values: dict[str, float], *, rwp_rietveld: float,
               n_cycles: int = LEBAIL_GAP_CYCLES) -> LeBailGap | None:
    """Evaluate-only Le Bail partition at the converged state → the gap.

    The one Layer-0 inventory item that takes the compiled model: like the
    rest of the layer it is a measured whole-profile statistic, never a
    linearisation, so it stays trustworthy on an abstained report.  The
    convention (and how to read the ratio) is the
    :class:`~rietx.report.schemas.LeBailGap` docstring.

    ``None`` outside Rietveld mode — a Le Bail/Pawley fit already *is* the
    intensity-free description, so the gap has nothing to triage there
    (absent for cause, not a failure).

    The model's mode and per-hkl buffers are flipped for the partition and
    restored before returning; θ is never touched, no least-squares runs, and
    every frozen structure (windows, reflection lists, FCJ node counts) is
    reused as compiled, so frozen-per-stage discreteness is untouched.
    """
    if model.mode != "rietveld":
        return None
    saved = [cp.hkl_intensity for cp in model.phases]
    try:
        model.mode = "lebail"
        seed = max(float(np.median(model.y_obs)), 1.0)
        for cp in model.phases:
            cp.hkl_intensity = np.full(len(cp.reflections), seed)
        model.lebail_update(values, n_cycles=n_cycles)
        y_calc = model.evaluate(values)
    finally:
        model.mode = "rietveld"
        for cp, buf in zip(model.phases, saved, strict=True):
            cp.hkl_intensity = buf
    w = 1.0 / model.sigma**2
    delta = model.y_obs - y_calc
    denom = float((w * model.y_obs**2).sum())
    rwp_lb = float(np.sqrt((w * delta * delta).sum() / denom)) if denom > 0 else 0.0
    return LeBailGap(
        rwp_rietveld=rwp_rietveld, rwp_lebail=rwp_lb,
        ratio=float(rwp_rietveld / max(rwp_lb, 1e-12)), n_cycles=n_cycles)


def too_flexible(bg: BackgroundEvidence) -> bool:
    """The background can imitate a structural parameter (WP-1055).

    One predicate, consulted by the summary clause here and by the Layer-2
    emitter, so the sentence and the action cannot disagree about what the
    evidence says.
    """
    return bg.worst_absorption >= BACKGROUND_ABSORPTION_NOTABLE


def too_stiff(bg: BackgroundEvidence) -> bool:
    """Systematic misfit between the peak regions — magnitude **and** shape.

    Both halves are required and the schema comment says why: the magnitude is
    σ-scaled and the Durbin-Watson d is not, so a pattern whose esds are
    merely mis-scaled cannot fire this on its own.
    """
    return (bg.off_region_chi2_reduced >= OFF_REGION_CHI2_RED_HIGH
            and bg.off_region_durbin_watson is not None
            and bg.off_region_durbin_watson < OFF_REGION_DW_LOW)


def background_clause(bg: BackgroundEvidence) -> str | None:
    """The one summary sentence, or None when neither failure mode fires.

    A threshold here decides whether the summary *comments*, never whether the
    section publishes: :class:`~rietx.report.schemas.BackgroundEvidence` is
    on the report either way, and the Rwp pair — which no threshold can make
    newsworthy without firing on every lab pattern — is published and never
    quoted here (the schema docstring has the measurement).
    """
    parts: list[str] = []
    if too_flexible(bg):
        parts.append(
            f"the background can reproduce {bg.worst_absorption:.0%} of "
            f"{bg.worst_absorption_path} (block projection R², which a "
            f"pairwise ρ cannot see) — ADPs, scales and any QPA fractions "
            f"from this fit are biased, in the one direction Rwp improves in")
    if too_stiff(bg):
        parts.append(
            f"between the peak regions the residual is systematic, not noise "
            f"— χ²_red={bg.off_region_chi2_reduced:.1f} over "
            f"{bg.off_region_points} channels at Durbin-Watson "
            f"d={bg.off_region_durbin_watson:.2f} (2 = uncorrelated), misfit "
            f"no region entry covers")
    return "; ".join(parts) if parts else None


#: How near a predicted position an observed peak must be to count as
#: *explained*, in deg 2theta.  One authority since WP-1103, because a second
#: consumer arrived: ``EXTRA_PEAK_ON_REFLECTION`` asks "is this declared
#: component sitting on a line the model already predicts", which is the same
#: question this answers and must not be answered with a different number — a
#: component inside Layer 0's tolerance is one Layer 0 would have matched.
LAYER0_MATCH_TOL_DEG = 0.08


def build_layer0(result: RefinementResult, *, top_n: int = 15,
                 match_tol_deg: float = LAYER0_MATCH_TOL_DEG,
                 min_peak_sigma: float = 5.0) -> FitReport:
    """Layer 0 only.  :func:`rietx.build_report` adds Layers 1-2 on top."""
    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    if len(tt) == 0:
        raise ValueError("result carries no pattern arrays")
    sigma = result.sig()   # esds, or the pre-v0.2 Poisson fallback

    w = 1.0 / sigma**2
    delta = y_obs - y_calc
    wd2 = w * delta * delta

    # --- cumulative χ² breakpoints (David 2004): flag jumps > 5% of total
    cum = np.cumsum(wd2)
    total = float(cum[-1]) if cum[-1] > 0 else 1.0
    step = np.diff(cum) / total
    jump_idx = np.nonzero(step > 0.05)[0]
    breakpoints = [float(tt[i]) for i in jump_idx]

    # --- region segmentation from calc ticks ∪ residual peaks
    ticks = np.concatenate([np.asarray(v) for v in result.ticks.values()]) if result.ticks else np.array([])
    resid_norm = delta / sigma
    peaks_obs = residual_peak_indices(resid_norm, min_peak_sigma=min_peak_sigma)
    all_pos = np.concatenate([ticks, tt[peaks_obs]]) if len(peaks_obs) else ticks
    median_step = float(np.median(np.diff(tt)))
    regions_bounds = _segment_regions(tt, all_pos, gap_deg=max(20 * median_step, 0.15))

    total_wd2 = float(wd2.sum())
    regions: list[Region] = []
    for lo, hi in regions_bounds:
        m = (tt >= lo) & (tt <= hi)
        if not np.any(m):
            continue
        denom = float((w[m] * y_obs[m] ** 2).sum())
        local_rwp = float(np.sqrt(wd2[m].sum() / denom)) if denom > 0 else 0.0
        regions.append(Region(
            two_theta_lo=float(lo), two_theta_hi=float(hi),
            local_rwp=local_rwp,
            chi2_share=float(wd2[m].sum() / total_wd2) if total_wd2 > 0 else 0.0,
            max_abs_delta_over_sigma=float(np.abs(resid_norm[m]).max()),
            n_reflections=int(np.sum((ticks >= lo) & (ticks <= hi))) if len(ticks) else 0,
        ))
    regions.sort(key=lambda r: -r.chi2_share)

    # --- unmatched peaks
    unmatched: list[UnmatchedPeak] = []
    for i in peaks_obs:
        if len(ticks) == 0 or np.min(np.abs(ticks - tt[i])) > match_tol_deg:
            unmatched.append(UnmatchedPeak(
                two_theta=float(tt[i]), height_over_sigma=float(resid_norm[i]),
                kind="unmatched_obs"))
    # calc reflections with no observed intensity: strong negative residual peak
    peaks_neg, _ = find_peaks(-resid_norm, height=min_peak_sigma, distance=5)
    for i in peaks_neg:
        if len(ticks) and np.min(np.abs(ticks - tt[i])) <= match_tol_deg:
            unmatched.append(UnmatchedPeak(
                two_theta=float(tt[i]), height_over_sigma=float(-resid_norm[i]),
                kind="unmatched_calc"))

    stats = result.statistics
    n_total = len(regions)
    kept = regions[:top_n]
    rest = regions[top_n:]
    summary = (
        f"Rwp={stats.rwp:.4f} GoF={stats.gof:.2f}; {n_total} regions, "
        f"top {len(kept)} shown ({sum(r.chi2_share for r in kept):.0%} of χ²); "
        f"{len([u for u in unmatched if u.kind == 'unmatched_obs'])} unmatched observed peak(s)"
    )
    if rest:
        summary += (f"; remaining {len(rest)} regions carry "
                    f"{sum(r.chi2_share for r in rest):.0%} of χ²")

    # The background section takes the *full* segmentation, not the top-N kept
    # above: a channel outside the fifteen largest regions is in a small one,
    # not off-region, and the off-region share is the whole point.
    background = assess_background(result, regions_bounds)
    if background is not None:
        clause = background_clause(background)
        if clause is not None:
            summary += "; " + clause

    return FitReport(
        rwp=stats.rwp, gof=stats.gof,
        cumulative_chi2_breakpoints=breakpoints,
        regions=kept, n_regions_total=n_total,
        unmatched=unmatched, background=background, summary=summary,
    )
