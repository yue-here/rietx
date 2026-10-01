"""FitReport background evidence — the two failure modes nothing else shows.

Layer-0 in trustworthiness: everything here is measured on the arrays the
result already carries, plus the one number that could not be (the block
projection R², screened at fit time onto
:class:`~rietx.schemas.results.Identifiability` because the Jacobian is
never serialized).  Nothing is linearised, so the section speaks on an
abstained report too — and it must, since an over-flexible background is a
*cause* of a bad fit at least as often as a symptom.

The contract, the reading and the citations are the
:class:`~rietx.report.schemas.BackgroundEvidence` docstring; this module is
how the numbers are computed and where their measured separations are
recorded.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import RefinementResult
from .schemas import BackgroundEvidence


def _pooled_durbin_watson(delta: np.ndarray, mask: np.ndarray
                          ) -> tuple[float | None, int]:
    """Durbin-Watson d over ``mask``'s channels, pooled within contiguous runs.

    Returns ``(d, n_pairs)``.  The numerator sums (δᵢ − δᵢ₋₁)² only over pairs
    where **both** channels are in the mask and adjacent in the pattern; the
    denominator is Σδ² over the mask.  Differencing across an excised peak
    region would manufacture a large jump out of two unrelated channels and
    push d up towards "uncorrelated" exactly where the statistic is being
    asked its question — so those pairs are dropped rather than bridged.

    ``None`` when fewer than two adjacent in-mask channels exist to difference,
    which is the honest answer for a pattern whose peaks leave no gaps.
    """
    if delta.size < 2 or not mask.any():
        return None, 0
    pair = mask[1:] & mask[:-1]
    n_pairs = int(pair.sum())
    denom = float(delta[mask] @ delta[mask])
    if n_pairs < 1 or denom <= 0.0:
        return None, n_pairs
    diff = np.diff(delta)[pair]
    return float((diff @ diff) / denom), n_pairs


def assess_background(result: RefinementResult,
                      region_bounds: list[tuple[float, float]]
                      ) -> BackgroundEvidence | None:
    """Assemble :class:`~rietx.report.schemas.BackgroundEvidence`.

    ``region_bounds`` are the Layer-0 peak-cluster regions **before** the
    top-N truncation, because the complement is the point: a channel outside
    the fifteen largest regions is not off-region, it is in a small one.
    :func:`~rietx.report.layer0.build_layer0` therefore calls this with the
    full segmentation it computed, not with ``report.regions``.

    Returns ``None`` when the result carries no background curve — there is
    then no pair to quote and no share to compute, and inventing zeros would
    read as "no background" rather than "not recorded".

    **Measured** (LaB₆ fixtures, 2026-08-12; the thresholds these sit between
    are in :mod:`~rietx.report.schemas`, the fixtures in
    ``tests/test_background_auto.py``):

    ==========================  =======  =======  ====  =====
    background                  worst R²  χ²_red   d     share
    ==========================  =======  =======  ====  =====
    1°-knot spline, λ=0            0.46     1.02  2.03   0.92
    Chebyshev-6 (correct)          0.01     0.97  2.00   0.93
    Chebyshev-2 over a hump        0.02    12.55  0.19   0.73
    Chebyshev-3 over a hump        0.02    12.16  0.18   0.76
    Chebyshev-8 over a hump        0.02     4.56  0.44   0.92
    ==========================  =======  =======  ====  =====

    (χ²_red and d are the off-region ones; ``share`` is the background's share
    of observed intensity.)  The two failure directions do not overlap: the
    absorbing background is indistinguishable from the correct one on the
    residual statistics, and the stiff ones are indistinguishable from it on
    the projection — which is why both halves of this section exist.
    """
    if not result.y_background:
        return None
    # The result's own abscissa.  Every number this function computes is a
    # residual statistic or a ratio of sums over channels, so the *quantity* on
    # the axis never enters — only the region bounds have to be quoted in it,
    # and the caller supplies those from the same array.  Nothing this section
    # reports carries an axis, which is why it speaks on a flight-time fit
    # while the region and unmatched-peak sections cannot.
    tt = result.x()
    y_obs = np.asarray(result.y_obs, dtype=np.float64)
    y_bkg = np.asarray(result.y_background, dtype=np.float64)
    if tt.size == 0 or y_bkg.size != tt.size:
        return None
    sigma = result.sig()
    delta = (y_obs - np.asarray(result.y_calc, dtype=np.float64)) / sigma
    wd2 = delta * delta

    off = np.ones(tt.size, dtype=bool)
    for lo, hi in region_bounds:
        off &= ~((tt >= lo) & (tt <= hi))
    total = float(wd2.sum())
    off_share = float(wd2[off].sum() / total) if total > 0 else 0.0
    off_red = float(wd2[off].mean()) if off.any() else 0.0
    dw, _ = _pooled_durbin_watson(delta, off)

    obs_sum = float(np.abs(y_obs).sum())
    share = float(y_bkg.sum() / obs_sum) if obs_sum > 0 else 0.0

    # An empty table is "nothing was screened", never "nothing absorbs"
    # (WP-1465): Le Bail and Pawley force-fix every target the screen asks
    # about, and a Rietveld answer stage freeing no scale, Biso, occupancy or
    # ADP — or no background term — leaves it the same ``{}``.  Its headline
    # was 0.0 there, which every reader took for a measurement.
    absorption = (dict(result.identifiability.background_absorption) or None
                  if result.identifiability is not None else None)
    worst_path, worst = None, None
    if absorption:
        worst_path, worst = max(absorption.items(), key=lambda kv: kv[1])
        worst = float(worst)

    return BackgroundEvidence(
        rwp=result.statistics.rwp,
        rwp_background_subtracted=result.statistics.rwp_background_subtracted,
        background_share=share,
        off_region_chi2_share=off_share,
        off_region_chi2_reduced=off_red,
        off_region_durbin_watson=dw,
        off_region_points=int(off.sum()),
        absorption=absorption,
        worst_absorption=worst,
        worst_absorption_path=worst_path,
        # Carried verbatim, including its None: the result is the one
        # authority for every declared count and this section never recounts
        # one.  Which count changed with the seam's second member (WP-1103) —
        # this section's question is how much *background* flexibility was
        # granted, so it reads the background-landing subset.  A declared sharp
        # peak is not background flexibility, and counting it here would
        # overstate the very thing the absorption table beside it measures.
        n_peaks=result.n_background_components,
    )
