"""FitReport Layer 0: model-free, agent-native fit diagnostics.

Everything here is computed without linearising the model, so it stays
trustworthy even when the refinement is far from converged — which is exactly
what the gated linear misfit attribution of :mod:`pxrdref.report.layer1`
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
from .schemas import FitReport, Region, UnmatchedPeak


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


def build_layer0(result: RefinementResult, *, top_n: int = 15,
                 match_tol_deg: float = 0.08, min_peak_sigma: float = 5.0) -> FitReport:
    """Layer 0 only.  :func:`pxrdref.build_report` adds Layers 1-2 on top."""
    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    if len(tt) == 0:
        raise ValueError("result carries no pattern arrays")
    if result.sigma:
        sigma = np.asarray(result.sigma)
    else:  # results recorded before v0.2 carried no σ — Poisson fallback
        sigma = np.sqrt(np.maximum(y_obs, 1.0))

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
    peaks_obs, _ = find_peaks(resid_norm, height=min_peak_sigma, distance=5)
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

    return FitReport(
        rwp=stats.rwp, gof=stats.gof,
        cumulative_chi2_breakpoints=breakpoints,
        regions=kept, n_regions_total=n_total,
        unmatched=unmatched, summary=summary,
    )
