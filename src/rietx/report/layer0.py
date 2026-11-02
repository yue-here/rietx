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
  (impurity / missing-phase candidates, each with where it sits against the
  peaks the model draws) and calculated reflections with no observed
  intensity.

All quantities are 1/σ²-weighted; both Δ and Δ/σ views are reported.
"""

from __future__ import annotations

import warnings

import numpy as np
from scipy.signal import find_peaks, peak_prominences, peak_widths

from ..schemas.results import RefinementResult
from .background import assess_background
from .schemas import (
    BACKGROUND_ABSORPTION_NOTABLE,
    LEBAIL_GAP_CYCLES,
    OFF_REGION_CHI2_RED_HIGH,
    OFF_REGION_DW_LOW,
    BackgroundEvidence,
    FitReport,
    FlankEvidence,
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


def _flank_walks(y_obs: np.ndarray, y_calc: np.ndarray, sigma: np.ndarray,
                 i: int, *, min_sigma: float) -> list[tuple[int, float, float]]:
    """The walks :func:`on_drawn_flank` makes from channel ``i``.

    One ``(apex, valley over σ, prominence)`` per uphill direction whose apex
    is a drawn peak the data can see; a walk ending at the pattern edge, or at
    an apex below ``min_sigma`` σ of prominence, is left out.
    """
    n = len(y_calc)
    uphill = [s for s in (-1, 1) if 0 <= i + s < n and y_calc[i + s] > y_calc[i]]
    walks = []
    for step in uphill or [0]:
        # no uphill neighbour: channel i is itself a drawn apex, the case of a
        # line no tick marks (a blank's, a declared extra peak's)
        path = [i]
        j = i + step
        # strictly uphill: a flat run of the curve (a held background, a
        # masked span) would otherwise carry the walk to a peak far away
        while step and 0 <= j < n and y_calc[j] > y_calc[path[-1]]:
            path.append(j)
            j += step
        apex = path[-1]
        if apex in (0, n - 1):
            continue
        with warnings.catch_warnings():
            # a flat channel's prominence is 0, which is the answer here
            warnings.filterwarnings(
                "ignore", message="some peaks have a prominence of 0")
            prominence = float(peak_prominences(y_calc, [apex])[0][0])
        if prominence < min_sigma * sigma[apex]:
            continue
        p = np.asarray(path)
        seen = np.maximum.accumulate(y_obs[p])
        walks.append((apex, float(np.max((seen - y_obs[p]) / sigma[p])),
                      prominence))
    return walks


def on_drawn_flank(y_obs: np.ndarray, y_calc: np.ndarray, sigma: np.ndarray,
                   i: int, *, min_sigma: float) -> bool:
    """Whether the data leave residual peak ``i`` unresolved from a peak the
    model draws (WP-1977).

    A misfit of a peak's shape, width or asymmetry leaves a positive lobe on
    its flank, often 1-3 FWHM from the apex: 0.15-0.19° below strong zincite
    lines on cpd-1c, and 0.1-0.34° below each LaB₆ line on SRM 660c with the
    axial apertures at 0 (#1106).  A fixed matching window cannot tell such a
    lobe from a foreign line.  The difference curve tells part of it, and a
    refiner reads it so (McCusker et al. 1999): a line standing on its own has
    a valley between it and its neighbour.  Where there is none the data do
    not decide.  A shape or asymmetry misfit, an unmodelled Kα2, a split of
    the line by lower symmetry and a foreign line all leave an unresolved
    shoulder.  So the answer is a measurement Layer 0 records on the row
    (:class:`~rietx.report.schemas.FlankEvidence`), and the row stays listed.

    From channel ``i`` it walks uphill along the calculated curve to the apex
    of the drawn peak it sits on.  Uphill can be either way at a valley of the
    curve, so both directions are tried, and a channel at an apex is its own.
    The answer is ``True`` when both hold:

    * the apex is a peak the data can see.  Its prominence in ``y_calc`` is at
      least ``min_sigma`` times σ at the apex.  This excludes a wiggle of a
      smooth background and a reflection the counting noise hides, and the
      pattern edge is never an apex;
    * the observed curve has no resolved valley on the way.  Along the path it
      never falls ``min_sigma`` σ below the highest point it has reached.

    The calculated curve is ``y_calc`` whole, so a line of a fixed background
    component (a measured blank, #1217) or of a declared extra peak counts as
    a drawn peak.  ``min_sigma`` is the level that made the residual a peak.
    How far "unresolved" reaches grows with the neighbour's height: a line
    8-12σ tall beside a Lorentzian of FWHM 0.1° stays unresolved out to 2 FWHM
    at 10³ counts, 3-4 at 10⁴ and 6 at 10⁵.
    """
    return any(valley < min_sigma for _, valley, _ in
               _flank_walks(y_obs, y_calc, sigma, i, min_sigma=min_sigma))


def _flank_evidence(rows: list[int], tt: np.ndarray, y_obs: np.ndarray,
                    y_calc: np.ndarray, sigma: np.ndarray, *,
                    min_sigma: float) -> dict[int, FlankEvidence]:
    """One :class:`FlankEvidence` per ``unmatched_obs`` channel in ``rows``.

    Each row takes the walk with the shallowest valley, so a residual at a
    valley of the drawn curve is read against the neighbour it joins.  The
    recurrence counts read every row at once, which is why this builds them
    together.
    """
    n = len(y_calc)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="some peaks have a prominence of 0")
        maxima, props = find_peaks(y_calc, prominence=(None, None))
    prominence_of = dict(zip(maxima.tolist(), props["prominences"].tolist()))
    chosen: dict[int, tuple[int, float, float] | None] = {}
    for i in rows:
        walks = _flank_walks(y_obs, y_calc, sigma, i, min_sigma=min_sigma)
        chosen[i] = min(walks, key=lambda w: w[1]) if walks else None
        if chosen[i] is not None:
            prominence_of.setdefault(chosen[i][0], chosen[i][2])
    lobes = {(w[0], int(np.sign(tt[i] - tt[w[0]])))
             for i, w in chosen.items()
             if w is not None and w[1] < min_sigma}

    out: dict[int, FlankEvidence] = {}
    channels = np.arange(n, dtype=float)
    for i, walk in chosen.items():
        if walk is None:
            out[i] = FlankEvidence(
                on_flank=False, peak_two_theta=None,
                peak_prominence_over_sigma=None, peak_fwhm_deg=None,
                offset_fwhm=None, valley_over_sigma=None,
                lines_as_strong=None, lines_with_lobe=None)
            continue
        apex, valley, prominence = walk
        _, _, left, right = peak_widths(y_calc, [apex], rel_height=0.5)
        fwhm = float(np.interp(right[0], channels, tt)
                     - np.interp(left[0], channels, tt))
        on_flank = valley < min_sigma
        as_strong = with_lobe = None
        if on_flank:
            side = int(np.sign(tt[i] - tt[apex]))
            strong = [a for a, p in prominence_of.items() if p >= prominence]
            as_strong = len(strong)
            with_lobe = sum(1 for a in strong if (a, side) in lobes)
        out[i] = FlankEvidence(
            on_flank=on_flank, peak_two_theta=float(tt[apex]),
            peak_prominence_over_sigma=prominence / float(sigma[apex]),
            peak_fwhm_deg=fwhm,
            offset_fwhm=float((tt[i] - tt[apex]) / fwhm) if fwhm > 0 else None,
            valley_over_sigma=valley,
            lines_as_strong=as_strong, lines_with_lobe=with_lobe)
    return out


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
    evidence says.  An unmeasured screen (``None``, WP-1465) says nothing
    either way, so it cannot fire.
    """
    return (bg.worst_absorption is not None
            and bg.worst_absorption >= BACKGROUND_ABSORPTION_NOTABLE)


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
    """The summary lines (one per failure mode), or None when neither fires.

    A threshold here decides whether the summary *comments*, never whether the
    section publishes: :class:`~rietx.report.schemas.BackgroundEvidence` is
    on the report either way, and the Rwp pair — which no threshold can make
    newsworthy without firing on every lab pattern — is published and never
    quoted here (the schema docstring has the measurement).
    """
    parts: list[str] = []
    if too_flexible(bg):
        parts.append(
            f"The background can reproduce {bg.worst_absorption:.0%} of "
            f"{bg.worst_absorption_path} (block projection R²).\n"
            f"ADPs, scales and any QPA fractions from this fit are biased, "
            f"and the bias lowers Rwp.")
    if too_stiff(bg):
        parts.append(
            f"Between the peak regions the residual is systematic "
            f"(χ²_red={bg.off_region_chi2_reduced:.1f} over "
            f"{bg.off_region_points} channels, Durbin-Watson "
            f"d={bg.off_region_durbin_watson:.2f} where 2 is uncorrelated).\n"
            f"No region entry covers this misfit.")
    return "\n".join(parts) if parts else None


#: How near a predicted position an observed peak must be to count as
#: *explained*, in deg 2theta.  One authority since WP-1103, because a second
#: consumer arrived: ``EXTRA_PEAK_ON_REFLECTION`` asks "is this declared
#: component sitting on a line the model already predicts", which is the same
#: question this answers and must not be answered with a different number — a
#: component inside Layer 0's tolerance is one Layer 0 would have matched.
#: WP-1977's flank test (:func:`on_drawn_flank`) moves neither consumer's
#: window: it measures a row this window has already listed.
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

    # --- unmatched peaks: no tick within the window.  Each carries where it
    # sits against the peaks the model draws (WP-1977): a measurement, never
    # a filter
    unmatched: list[UnmatchedPeak] = []
    rows = [int(i) for i in peaks_obs
            if not len(ticks) or np.min(np.abs(ticks - tt[i])) > match_tol_deg]
    flank = _flank_evidence(rows, tt, y_obs, y_calc, sigma,
                            min_sigma=min_peak_sigma)
    for i in rows:
        unmatched.append(UnmatchedPeak(
            two_theta=float(tt[i]), height_over_sigma=float(resid_norm[i]),
            kind="unmatched_obs", flank=flank[i]))
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
    # One sentence a line (WP-1985): a reader scans the lines, and the
    # statistics this used to open with are the report's own rwp and gof.
    summary = (f"{n_total} misfit regions. The top {len(kept)} carry "
               f"{sum(r.chi2_share for r in kept):.0%} of χ²")
    if rest:
        summary += (f" and the other {len(rest)} carry "
                    f"{sum(r.chi2_share for r in rest):.0%}")
    summary += (f".\n{len([u for u in unmatched if u.kind == 'unmatched_obs'])} "
                "observed peak(s) match no reflection.")

    # The background section takes the *full* segmentation, not the top-N kept
    # above: a channel outside the fifteen largest regions is in a small one,
    # not off-region, and the off-region share is the whole point.
    background = assess_background(result, regions_bounds)
    if background is not None:
        clause = background_clause(background)
        if clause is not None:
            summary += "\n" + clause

    return FitReport(
        rwp=stats.rwp, gof=stats.gof,
        cumulative_chi2_breakpoints=breakpoints,
        regions=kept, n_regions_total=n_total,
        unmatched=unmatched, background=background, summary=summary,
    )
