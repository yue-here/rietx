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

import math
from dataclasses import dataclass

import numpy as np

from ..schemas.pattern import PatternData
from ..schemas.results import FitRange, OutsideSpan, ReflectionOutside

#: The width (° 2θ) of the window beside a cut that ``level_ratio_at_cut``,
#: ``level_ratio_far``, ``slope_at_cut`` and ``background_slope_at_cut`` are
#: read over (WP-2075, issue #1219).  A reporting window, gating nothing:
#: chosen on the issue's two synthetic families and read on SRM 1976a and
#: 11-BM LaB6 660a; untested beyond them.  Tier 3, awaiting the maintainer.
CUT_WINDOW_DEG = 1.0

#: How near a cut, in units of a reflection's own FWHM, a reflection centred
#: on the fitted side is listed with the share of its profile past the cut
#: (WP-2075).  A reporting window like :data:`CUT_WINDOW_DEG`, with the same
#: provenance; at three FWHM a pseudo-Voigt's share past the cut is under
#: 6 % for a pure Lorentzian and nil for a Gaussian.  Tier 3, awaiting the
#: maintainer.
STRADDLE_FWHM = 3.0


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


# -- chunk 2: what lies outside each cut ------------------------------------


@dataclass(frozen=True)
class _Reflection:
    """One (line, reflection) of the fitted model, at the answer."""

    phase: str
    hkl: list[int]
    line: int
    two_theta: float
    fwhm: float
    eta: float


def model_reflections(model, values: dict[str, float],
                      phase_names: list[str]) -> list[_Reflection]:
    """Every (line, reflection) the compiled ``model`` generated, at
    ``values``: position from :meth:`phase_peaks`, the same walk the ticks
    take, and (Γ, η) from :meth:`peak_gamma_eta`, the shape-agnostic reading
    of the width pair."""
    from ..crystallography.symmetry import reflection_label_row

    out: list[_Reflection] = []
    for ip, name in enumerate(phase_names):
        hklm = model.phases[ip].reflections.hklm
        for il, (pos, w1, w2, _inten) in enumerate(model.phase_peaks(ip, values)):
            gamma, eta = model.peak_gamma_eta(np.asarray(w1), np.asarray(w2))
            pos = np.asarray(pos, dtype=np.float64)
            gamma = np.broadcast_to(np.asarray(gamma, dtype=np.float64), pos.shape)
            eta = np.broadcast_to(np.asarray(eta, dtype=np.float64), pos.shape)
            for k in range(pos.size):
                if not (np.isfinite(pos[k]) and np.isfinite(gamma[k])
                        and gamma[k] > 0.0):
                    continue
                out.append(_Reflection(name, reflection_label_row(hklm[k]), il,
                                       float(pos[k]), float(gamma[k]),
                                       float(eta[k])))
    return out


def _pv_cdf(x: float, pos: float, fwhm: float, eta: float) -> float:
    """The TCH pseudo-Voigt's area below ``x``: η of a Lorentzian and 1 − η
    of a Gaussian, both of FWHM Γ (Thompson, Cox & Hastings 1987, J. Appl.
    Cryst. 20, 79)."""
    if math.isinf(x):
        return 0.0 if x < 0 else 1.0
    u = x - pos
    sigma = fwhm / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    gauss = 0.5 * (1.0 + math.erf(u / (sigma * math.sqrt(2.0))))
    lor = 0.5 + math.atan(2.0 * u / fwhm) / math.pi
    return eta * lor + (1.0 - eta) * gauss


def _slope(x: np.ndarray, y: np.ndarray) -> float | None:
    """The least-squares slope of ``y`` on ``x``, as a fraction of ``y``'s
    mean per unit ``x``; ``None`` under two distinct abscissae or a mean
    that is not positive."""
    if x.size < 2 or float(np.ptp(x)) == 0.0:
        return None
    mean = float(np.mean(y))
    if mean <= 0.0:
        return None
    return float(np.polyfit(x, y, 1)[0] / mean)


def _ratio(values: np.ndarray, ref: float) -> float | None:
    """The median of ``values`` over ``ref``; ``None`` with no values or a
    reference that is not positive (background-subtracted data), where a
    ratio would flip sign or blow up."""
    return (float(np.median(values) / ref)
            if values.size and ref > 0.0 else None)


def describe_outside(record: FitRange, data: PatternData,
                     two_theta_limits: tuple[float, float] | None,
                     y_background: list[float],
                     reflections: list[_Reflection] | None,
                     searched: tuple[float, float] | None) -> FitRange:
    """``record`` with every :class:`OutsideSpan` given its facts (WP-2075's
    chunk 2): levels and slopes against the fitted channels' median, the
    largest excess over the background envelope, and the reflections the
    model put in or near the span.

    ``y_background`` is the fitted background on the fitted channels
    (``RefinementResult.y_background``); ``reflections`` and ``searched``
    (the 2θ the model's reflection list was generated over) are ``None`` for
    a fit with no compiled model behind it, which leaves those facts out.
    Every fact is arithmetic on the data and the answer: none has a null or a
    threshold, and nothing reads one to decide anything.
    """
    from ..background.diagnostics import background_envelope
    from ..project import fitted_mask

    if not record.outside:
        return record
    tt, y = data.tt(), data.y()
    sig = data.sig()
    mask = fitted_mask(data, two_theta_limits)
    fit_idx = np.flatnonzero(mask)
    med_fit = float(np.median(y[mask]))
    bkg = np.full(tt.size, np.nan)
    if len(y_background) == fit_idx.size:
        bkg[fit_idx] = np.asarray(y_background, dtype=np.float64)
    z = (y - background_envelope(tt, y)) / sig
    w = CUT_WINDOW_DEG

    spans = []
    for span in record.outside:
        i0 = int(np.searchsorted(tt, span.lo))
        i1 = int(np.searchsorted(tt, span.hi))
        idx = np.arange(i0, i1 + 1)
        facts: dict = {"level_ratio": _ratio(y[idx], med_fit)}
        k = int(np.argmax(z[idx]))
        facts["peak_two_theta"] = float(tt[idx[k]])
        facts["peak_sigma"] = float(z[idx[k]])
        if span.kind != "excluded":
            # the cut is the span's end beside the fitted range; distance is
            # measured away from the fitted range, so a positive slope rises
            # outward on either side
            below = span.kind == "below"
            cut = tt[i1] if below else tt[i0]
            far = tt[i0] if below else tt[i1]
            away = (cut - tt) if below else (tt - cut)
            near = idx[away[idx] <= w]
            facts["level_ratio_at_cut"] = _ratio(y[near], med_fit)
            facts["slope_at_cut"] = _slope(away[near], y[near])
            far_win = idx[np.abs(tt[idx] - far) <= w]
            facts["level_ratio_far"] = _ratio(y[far_win], med_fit)
            edge = tt[fit_idx[0]] if below else tt[fit_idx[-1]]
            inside = fit_idx[np.abs(tt[fit_idx] - edge) <= w]
            facts["background_slope_at_cut"] = (
                _slope(away[inside], bkg[inside])
                if np.all(np.isfinite(bkg[inside])) else None)
        if reflections is not None:
            # the unfitted span's bounds, half a step past its first and last
            # channel; open where it runs to the file's end
            a = -math.inf if i0 == 0 else 0.5 * (tt[i0 - 1] + tt[i0])
            b = math.inf if i1 == tt.size - 1 else 0.5 * (tt[i1] + tt[i1 + 1])
            rows = []
            for r in reflections:
                inside_span = a <= r.two_theta <= b
                near_cut = min(abs(r.two_theta - e) for e in (a, b)
                               ) <= STRADDLE_FWHM * r.fwhm
                if not (inside_span or near_cut):
                    continue
                frac = (_pv_cdf(b, r.two_theta, r.fwhm, r.eta)
                        - _pv_cdf(a, r.two_theta, r.fwhm, r.eta))
                rows.append(ReflectionOutside(
                    phase=r.phase, hkl=r.hkl, line=r.line,
                    two_theta=r.two_theta, fwhm=r.fwhm,
                    fraction_outside=float(frac)))
            facts["reflections"] = sorted(rows, key=lambda r: r.two_theta)
            if searched is not None:
                lo, hi = max(span.lo, searched[0]), min(span.hi, searched[1])
                facts["reflections_searched"] = ((float(lo), float(hi)) if lo <= hi
                                                 else None)
        spans.append(span.model_copy(update=facts))
    return record.model_copy(update={
        "outside": spans, "cut_window_deg": CUT_WINDOW_DEG,
        "straddle_fwhm": STRADDLE_FWHM if reflections is not None else None})
