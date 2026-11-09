"""WP-2075 — the result records its fit range, and what lies outside it.

:func:`fit_range_record` restates the caller's own act: the file's range, the
2θ limits asked for and applied, the excluded regions declared and applied,
and the counts on each side, as :class:`~rietx.schemas.results.FitRange`.
It also builds one :class:`~rietx.schemas.results.OutsideSpan` per stretch of
channels the fit left out, with the stretch's share of the file's counts.

It runs in ``Refinement.fit``, the one place the whole
:class:`~rietx.schemas.pattern.PatternData` is at hand: a result carries only
the fitted channels, and ``report()`` holds no pattern (issue #1219).  The
channels fitted are :func:`rietx.project.fitted_mask`'s, the authority
``compile_model`` is pinned to (WP-1033), so the record cannot disagree with
the residual about what was in it.
"""

from __future__ import annotations

import numpy as np

from ..schemas.pattern import PatternData
from ..schemas.results import FitRange, OutsideSpan


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """``(first, last)`` channel index of every run of ``True`` in ``mask``."""
    out: list[tuple[int, int]] = []
    start = None
    for i, on in enumerate([*mask.tolist(), False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def _share(part: float, whole: float) -> float:
    """``part / whole``, or 0 for a file whose counts sum to zero."""
    return float(part / whole) if whole != 0.0 else 0.0


def fit_range_record(data: PatternData,
                     two_theta_limits: tuple[float, float] | None
                     ) -> FitRange:
    """The :class:`~rietx.schemas.results.FitRange` of a fit of ``data``
    under ``two_theta_limits``.

    ``excluded_applied`` keeps a declared region only where it removed a
    channel the limits had kept, clipped to the limits, so a region lying
    wholly outside them is declared and not applied.  ``outside`` is built
    from the unfitted runs of the fitted mask: a range end and an excluded
    region that touch are one stretch of channels, and one span.
    """
    from ..project import fitted_mask

    tt = data.tt()
    y = data.y()
    mask = fitted_mask(data, two_theta_limits)
    if not mask.any():
        raise ValueError("no channel is fitted under these limits and exclusions")
    n = tt.size
    file_lo, file_hi = float(tt[0]), float(tt[-1])

    limits_applied = None
    kept = np.ones(n, dtype=bool)
    if two_theta_limits is not None:
        lo, hi = (float(v) for v in two_theta_limits)
        limits_applied = (max(lo, file_lo), min(hi, file_hi))
        kept = (tt >= lo) & (tt <= hi)
    window = limits_applied or (file_lo, file_hi)

    applied: list[tuple[float, float]] = []
    for lo, hi in data.excluded_regions:
        if np.any(kept & (tt >= lo) & (tt <= hi)):
            applied.append((max(float(lo), window[0]), min(float(hi), window[1])))

    total = float(y.sum())
    outside: list[OutsideSpan] = []
    for i0, i1 in _runs(~mask):
        kind = "below" if i0 == 0 else "above" if i1 == n - 1 else "excluded"
        outside.append(OutsideSpan(
            kind=kind, lo=float(tt[i0]), hi=float(tt[i1]),
            n_points=i1 - i0 + 1,
            count_share=_share(float(y[i0:i1 + 1].sum()), total)))

    fitted = tt[mask]
    return FitRange(
        file_range=(file_lo, file_hi), n_file=int(n),
        limits_requested=(None if two_theta_limits is None
                          else (float(two_theta_limits[0]),
                                float(two_theta_limits[1]))),
        limits_applied=limits_applied,
        excluded_declared=[(float(lo), float(hi))
                           for lo, hi in data.excluded_regions],
        excluded_applied=applied,
        fitted_range=(float(fitted[0]), float(fitted[-1])),
        n_fitted=int(mask.sum()),
        counts_file=total, counts_fitted=float(y[mask].sum()),
        outside=outside)
