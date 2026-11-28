"""Peak detection — σ-normalised thresholds, instrument-derived separation, and
the seeds the profile fitter needs.

Three rules distinguish this from the one-line ``find_peaks`` census in
``background/diagnostics.py``, and each of the three is a measured failure of
the obvious alternative:

* **Thresholds are σ-normalised, never relative to the global maximum.**  A
  ``prominence = net.max()·0.01`` rule (the prototype indexer at tag
  ``guillemot-study``) couples unrelated parts of the pattern: on a pattern
  that is one enormous reflection plus a dozen weak lines it suppresses
  everything but the giant.
* **The separation floor comes from the instrument, not a channel count.**
  ``distance=3`` is a synchrotron-shaped constant; the same three channels are
  a fortieth of a FWHM on a 0.01°-step lab pattern.  It is derived here from
  the Caglioti/TCH width law at the instrument's own U,V,W,X,Y — which also
  supplies the fitter's width seeds, so detection and fitting cannot disagree
  about how wide a peak is.
* **The width census ranks first and measures second.**  A median FWHM over
  *all* detections above a prominence floor reads 0.071° on a noisy pattern
  whose real lines are 0.389° (WP-1028, measured on third-party lab data),
  because smoothing ripples survive the floor as weak maxima.  The median of
  the :data:`~rietx.schemas.indexing.PEAK_WIDTH_CENSUS_N` most prominent
  detections recovers 0.389°.

Grouping is not a new rule: it calls ``model.forward._overlap_groups``, so
"overlapped" means one thing package-wide.  The background is the λ-free rolling
low quantile (``background.background_envelope``) and is **held additively**,
never subtracted — the whole-pattern invariant (CLAUDE.md, Weights) applies to
a 200-point window too.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks, peak_widths, savgol_coeffs, savgol_filter
from scipy.special import ndtr, ndtri

from ..background import background_envelope
from ..model.forward import PAWLEY_OVERLAP_FWHM_FRAC, _overlap_groups
from ..model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from ..model.profiles.fcj import fcj_extent_deg, fcj_live
from ..model.profiles.pseudovoigt import tch_gamma_eta
from ..schemas.indexing import (
    PEAK_ALIAS_RATIO_RANGE,
    PEAK_ALIAS_TOL_FWHM_FRAC,
    PEAK_DETECT_SEPARATION_FWHM_FRAC,
    PEAK_FDR_Q,
    PEAK_MIN_HEIGHT_SIGMA,
    PEAK_MIN_PROMINENCE_SIGMA,
    PEAK_SHOULDER_MIN_SIGMA,
    PEAK_UNUSABLE_FLAGS,
    PEAK_WIDTH_CENSUS_N,
    PEAK_WIDTH_SCALE_BOUNDS,
    PEAK_WINDOW_FWHM_MULT,
    ObservedPeak,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData

_LN2_8 = 8.0 * np.log(2.0)

#: A window a caller *asked* for must land on enough channels to fit two
#: widths and one component; below this the position is on a gap or an
#: excluded region, not on a peak.  Detection never meets the case — its seeds
#: are channels that exist — so only :func:`group_at` tests it.
MIN_GROUP_POINTS = 8


@dataclass
class PeakGroup:
    """One frozen fitting window and the component seeds inside it.

    ``i0``/``i1`` slice the :class:`Detection` arrays (already masked and
    cropped), so a group is self-contained: the fitter never re-derives a
    window.  ``n`` is frozen before the fit and may only change between
    explicit re-seed passes — the frozen-per-stage invariant one level down.
    """

    i0: int
    i1: int
    seed_two_theta: np.ndarray      # ° 2θ, ascending
    seed_fwhm: float                # ° 2θ, shared by the group
    from_shoulder: np.ndarray       # bool per seed: curvature seed, not a maximum

    @property
    def n(self) -> int:
        return len(self.seed_two_theta)


@dataclass
class Detection:
    """Everything the fitter needs: the masked pattern, the frozen background
    level, the groups, and the two widths whose *ratio* calibrated the seeds.

    ``fwhm_measured`` and ``fwhm_predicted`` are kept separately rather than
    collapsed into the scale factor because their disagreement is diagnostic:
    a ratio near 13 is the ``ProfileTCHZ`` default (``W = 1e-3 deg²``, FWHM ≈
    0.03°, a *synchrotron* line) applied to lab data, and a caller should be
    told that rather than have it silently absorbed.
    """

    two_theta: np.ndarray
    intensity: np.ndarray
    sigma: np.ndarray
    envelope: np.ndarray
    groups: list[PeakGroup]
    fwhm_measured: float
    fwhm_predicted: float
    width_scale: float
    n_shoulder_seeds: int
    #: 2θ of candidates dropped as Kα2 aliases of a stronger line.  Reported,
    #: because in one pattern an alias and a genuine coincident line are
    #: indistinguishable (:data:`~rietx.schemas.indexing.PEAK_ALIAS_RATIO_RANGE`).
    alias_two_theta: np.ndarray
    #: The number of independent places a line could have been found:
    #: ∫ d2θ / FWHM(2θ) over the picked range, at the census-scaled width law the
    #: seeds were sized with.  The look-elsewhere count the false-discovery
    #: threshold divides by (:func:`fdr_screen`).  ``nan`` on a hand-built
    #: detection, where :func:`fdr_screen` falls back to the span over the
    #: census width.
    n_trials: float = float("nan")


@dataclass(frozen=True)
class FdrScreen:
    """The per-pattern false-discovery threshold and what it decided.

    ``z_threshold`` is the I/σ_I a component needed (the Benjamini–Hochberg
    cutoff, or the Bonferroni bar q/m when nothing cleared it);
    ``expected_false`` is q × ``n_kept``, the bound BH gives on the expected
    number of noise lines among those kept.  ``weak`` holds the indices (into the
    list the screen was given) of the tested components that failed.
    """

    q: float
    n_trials: float
    n_tested: int
    n_kept: int
    z_threshold: float
    expected_false: float
    weak: tuple[int, ...]


def predicted_fwhm(two_theta_deg: np.ndarray, instrument: Instrument) -> np.ndarray:
    """The instrument's own combined FWHM (° 2θ) at these positions.

    The TCH combined Γ of the Caglioti Gaussian and the Lorentzian law, exactly
    as ``compile_model`` sizes its evaluation windows with — including under
    ``shape="voigt"``, where Γ_TCH tracks the true Voigt FWHM to ~1 %.  Sample
    broadening is *not* in here (no phase exists yet); that is what the width
    census measures.
    """
    prof = instrument.profile
    theta = 0.5 * np.asarray(two_theta_deg, dtype=np.float64)
    g = gaussian_fwhm(theta, prof.u.value, prof.v.value, prof.w.value)
    lor = lorentzian_fwhm(theta, prof.x.value, prof.y.value)
    gamma, _eta = tch_gamma_eta(g, lor)
    return np.asarray(gamma, dtype=np.float64)


def window_indices(two_theta: np.ndarray, lo_seed: float, hi_seed: float,
                   fwhm: float, instrument: Instrument) -> tuple[int, int]:
    """The channel range ``[i0, i1)`` of a fitting window spanning these seeds.

    One arithmetic, three callers: :func:`detect_peaks` sizes every group it
    finds, and :func:`group_at` sizes a window around positions somebody named
    (WP-1027's peak editor, WP-1101's ``fit_peaks``).  They had drifted as two
    copies of the same four lines, which is one edit away from a GUI window
    that disagrees with the one the fitter would have chosen.

    The FCJ allowance is added on the **low** side only: the axial smear is
    one-sided and toward low angle below 90°, which is exactly where the lines
    indexing depends on most sit.  Width costs almost nothing here — the
    profile kernel is dispatch-bound, 11.8 µs at 25 points against 13.6 µs at
    194 (WP-1109) — so the window is sized for safety, and
    :data:`~rietx.schemas.indexing.PEAK_WINDOW_FWHM_MULT` explains why it is
    nevertheless not wider.
    """
    half = PEAK_WINDOW_FWHM_MULT * float(fwhm)
    sl = instrument.geometry.axial_sl.value
    hl = instrument.geometry.axial_hl.value
    extra = (float(fcj_extent_deg(np.array(float(lo_seed)), sl, hl))
             if fcj_live(sl, hl) else 0.0)
    i0 = int(np.searchsorted(two_theta, lo_seed - half - extra, side="left"))
    i1 = int(np.searchsorted(two_theta, hi_seed + half, side="right"))
    return i0, i1


def group_at(det: Detection, positions: np.ndarray,
             instrument: Instrument) -> PeakGroup:
    """A fresh window around positions a caller named, sized as detection is.

    Detection's seeds are channels that exist, so it needs no refusals; a
    *given* position may sit off the end of the pattern or in a gap, and both
    are refused by name rather than fitted into nonsense.  The seed width is
    the instrument's own FWHM at the position, scaled by the width census
    (``Detection.width_scale``) exactly as detection scales its own — the
    census is what makes a declared synchrotron profile usable on lab data.
    """
    pos = np.sort(np.asarray(positions, dtype=np.float64))
    if pos.ndim != 1 or len(pos) == 0:
        raise ValueError("group_at needs at least one position")
    tt = det.two_theta
    outside = pos[(pos < tt[0]) | (pos > tt[-1])]
    if len(outside):
        raise ValueError(
            f"2θ = {outside[0]:.4f}° is outside the picked range "
            f"{tt[0]:.4f}–{tt[-1]:.4f}°")
    # the census scales each width *before* the mean, as ``fwhm_seed_curve``
    # does, so a caller naming exactly detection's seeds gets bit-identical
    # widths rather than last-ulp ones
    fw = float(np.mean(det.width_scale * predicted_fwhm(pos, instrument)))
    i0, i1 = window_indices(tt, float(pos[0]), float(pos[-1]), fw, instrument)
    if i1 - i0 < MIN_GROUP_POINTS:
        # a cluster is refused as a span: naming only its first position hides
        # which of the caller's positions the window was supposed to cover
        where = (f"2θ = {pos[0]:.4f}°" if len(pos) == 1 else
                 f"2θ = {pos[0]:.4f}–{pos[-1]:.4f}°")
        raise ValueError(
            f"only {i1 - i0} channel(s) around {where}; that is a "
            "gap or an excluded region, not a place a peak can be fitted")
    return PeakGroup(i0=i0, i1=i1, seed_two_theta=pos, seed_fwhm=fw,
                     from_shoulder=np.zeros(len(pos), dtype=bool))


def _debiased_envelope(tt: np.ndarray, y: np.ndarray) -> np.ndarray:
    """``background_envelope`` with its known downward bias removed.

    The envelope is a rolling *low quantile* (10th), and being biased low is
    exactly what makes it peak-robust — but it means "net = 0" is not the
    background level.  For flat Poisson counts the 10th percentile of a window
    sits ≈1.28σ below the mean, so a nominal 5σ detection threshold behaves like
    ≈3.7σ, and over a few thousand channels that is the difference between no
    false positives and a handful.  Measured: one spurious line at 116.46° on a
    two-peak synthetic before this correction.

    The offset is recovered as the median of the residual, which is unbiased
    whenever background channels outnumber peak channels — always true for a
    powder pattern, and the same assumption ``background.peak_mask`` already
    rests on.  Correcting the *envelope* rather than only ``net`` matters
    because the envelope is also the fitter's additively-held background: left
    biased, it puts a constant ≈1.28σ pedestal under every window for the peak
    intensity and width to absorb.
    """
    env = background_envelope(tt, y)
    return env + float(np.median(y - env))


def _shoulder_seeds(tt: np.ndarray, net: np.ndarray, sigma: np.ndarray,
                    fwhm: np.ndarray, found: np.ndarray,
                    alias_positions: np.ndarray,
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Curvature seeds for peaks that never reach a local maximum.

    Returns ``(seeds, suppressed_as_alias)``: the second array is the seeds
    dropped because they sit at a claimed line's Bragg-predicted Kα2 position,
    reported for the same reason a dropped alias *maximum* is.

    A shoulder on a strong line has no maximum, so ``find_peaks`` cannot see
    it — but it does have a curvature minimum, and the amplitude that curvature
    implies follows from the Gaussian relation |y″| = 8ln2·h/Γ².

    **The threshold has to be the filter's own noise, not the channel's.**  A
    second derivative amplifies white noise by ~1/step², so on a 0.01°-step
    pattern the raw curvature of pure noise implies an apparent peak height an
    order of magnitude above any per-channel σ — a threshold written against
    ``sigma[i]`` passes essentially every noise dip, and the first version of
    this function did exactly that (measured: hundreds of spurious seeds on a
    three-peak synthetic pattern).  So the derivative is a Savitzky-Golay filter
    over a window of about one FWHM, and its noise is *propagated exactly*: the
    filter is linear with known coefficients c, so σ(y″) = ‖c‖₂·σ.  The test is
    then the same σ-normalised significance a detection had to clear, which is
    what makes a shoulder seed and a detection mean the same thing.

    These are **seeds only**.  Whether the component survives is decided by the
    group fit's ΔBIC test (:mod:`.peakfit`), not here: this function is allowed
    to be generous, and being generous is why that gate exists.
    """
    out: list[int] = []
    alias: list[int] = []
    empty = np.array([], dtype=np.int64)
    step = float(np.median(np.diff(tt)))
    if len(tt) < 9 or step <= 0.0:
        return empty, empty
    width = max(int(float(np.median(fwhm)) / step), 5)
    width = min(width | 1, (len(tt) - 1) | 1)   # odd, and inside the pattern
    poly = min(4, width - 1)
    if poly < 3:                                # deriv=2 needs order ≥ 3
        return empty, empty
    curv = savgol_filter(net, width, poly, deriv=2, delta=step, mode="interp")
    coef_norm = float(np.linalg.norm(
        savgol_coeffs(width, poly, deriv=2, delta=step)))
    dips, _ = find_peaks(-curv)
    for i in dips:
        scale = fwhm[i] ** 2 / _LN2_8
        h_implied = -curv[i] * scale
        h_sigma = coef_norm * sigma[i] * scale
        if h_implied <= PEAK_SHOULDER_MIN_SIGMA * h_sigma:
            continue
        # a curvature dip closer than half a FWHM to something already claimed
        # is not separable from it by construction (that is what
        # PAWLEY_OVERLAP_FWHM_FRAC means), so seeding it manufactures a
        # component the least squares cannot resolve — and, for a dropped Kα2
        # alias, one the parent's own doublet already models
        gap = PAWLEY_OVERLAP_FWHM_FRAC * fwhm[i]
        if len(found) and np.min(np.abs(tt[found] - tt[i])) < gap:
            continue
        # …and neither is a dip sitting on a claimed line's *predicted* Kα2
        # position, however far away that is: a marginally resolved doublet has
        # no second maximum for :func:`_drop_kalpha2_aliases` to catch, but it
        # does have a curvature shoulder — and the parent's own doublet already
        # models exactly that intensity.  Measured (WP-1018 σ pull calibration,
        # lab Cu Kα LaB6): the 110 line at 30.387° splits by 0.0775° against a
        # 0.082° FWHM, so the Kα2 shoulder cleared both the 5σ curvature test
        # and the half-FWHM gap above, formed a *singleton* group of its own,
        # and came back as a line at 30.46° with real intensity — which the
        # ΔBIC prune cannot refuse, because against "no peak at all" there
        # genuinely is intensity there.
        if len(alias_positions) and np.min(
                np.abs(alias_positions - tt[i])) < _alias_tolerance(fwhm[i],
                                                                    step):
            alias.append(int(i))
            continue
        out.append(int(i))
    return (np.array(sorted(out), dtype=np.int64),
            np.array(sorted(alias), dtype=np.int64))


def _alias_tolerance(fwhm: float, step: float) -> float:
    """How far a candidate may sit from a predicted Kα2 position and still be it.

    ``PEAK_ALIAS_TOL_FWHM_FRAC`` of a FWHM, **plus one sampling step**.  Both
    ends of the comparison are channel positions — the candidate is a channel
    maximum, and the predicted position is Bragg's law applied to the parent's
    channel maximum — so each is off its true maximum by up to half a step and
    their difference by up to a whole one, whatever the profile.  A tolerance in
    FWHM alone is smaller than that wherever a FWHM spans fewer than 1/0.3 ≈ 3.3
    channels.  Measured (#878): Cu Kα rock salt on the preset's own
    0.032° FWHM at a 0.02° step, the 400 and 331 aliases sat 0.0116° and 0.0145°
    from their predicted positions against a 0.0114° tolerance, came back as two
    lines of their own, and the true cF cell indexed 7 of 9 lines —
    ``indexed_fraction_low`` on a clean pattern.
    """
    return PEAK_ALIAS_TOL_FWHM_FRAC * float(fwhm) + max(float(step), 0.0)


def _secondary_line_two_theta(tt_primary: np.ndarray, instrument: Instrument
                              ) -> np.ndarray:
    """Where every non-primary emission line of ``tt_primary`` would sit.

    Same d, different λ — Bragg's law, which is literally the ghost transform in
    ``background.diagnostics``: sin θ_l = (λ_l/λ₀)·sin θ₀.  Shape
    ``(len(source.lines) - 1, len(tt_primary))``, so a caller that needs the
    line's ``weight`` keeps the pairing; **NaN** past the sphere limit rather
    than clipped, because a clipped alias position is a real position that is
    wrong, and a NaN one compares false in every test here.
    """
    lines = instrument.source.lines
    tt0 = np.asarray(tt_primary, dtype=np.float64).ravel()
    if len(lines) < 2 or not len(tt0):
        return np.zeros((max(len(lines) - 1, 0), len(tt0)))
    ratios = np.array([ln.wavelength.value / lines[0].wavelength.value
                       for ln in lines[1:]], dtype=np.float64)
    s = ratios[:, None] * np.sin(np.radians(0.5 * tt0))[None, :]
    return 2.0 * np.degrees(np.arcsin(np.where(np.abs(s) <= 1.0, s, np.nan)))


def _drop_kalpha2_aliases(tt: np.ndarray, idx: np.ndarray, height: np.ndarray,
                          fwhm: np.ndarray, instrument: Instrument,
                          ) -> tuple[np.ndarray, np.ndarray]:
    """Split candidates into (real lines, Kα2 aliases of stronger candidates).

    Once the doublet resolves, the Kα2 maximum is a detection in its own right
    and — since every group is fitted independently, each with its *own* full
    doublet — it comes back as a line with real intensity.  So it has to be
    recognised here.  Same d-spacing, different λ, exactly the ghost transform:
    sin θ_alias = (λ_l/λ₀)·sin θ_parent, checked against the candidate's height
    ratio to the parent.

    The parent must be *stronger*, which is what keeps the relation
    antisymmetric and stops a pair annihilating each other; ties are broken by
    the lower 2θ, since the alias of a Kα1 line is always above it.
    """
    lines = instrument.source.lines
    if len(lines) < 2 or not len(idx):
        return idx, np.array([], dtype=np.int64)
    lo_r, hi_r = PEAK_ALIAS_RATIO_RANGE
    step = float(np.median(np.diff(tt))) if len(tt) > 1 else 0.0
    alias: set[int] = set()
    predicted_all = _secondary_line_two_theta(tt[idx], instrument)
    order = np.argsort(height)[::-1]            # strongest parent first
    for a in order:
        if int(idx[a]) in alias:
            continue                            # an alias cannot parent one
        for il in range(1, len(lines)):
            predicted = float(predicted_all[il - 1, a])
            if not np.isfinite(predicted):
                continue
            w = lines[il].weight.value
            for b in range(len(idx)):
                if b == a or int(idx[b]) in alias:
                    continue
                if height[b] >= height[a]:
                    continue
                if abs(tt[idx[b]] - predicted) > _alias_tolerance(
                        fwhm[idx[b]], step):
                    continue
                r = height[b] / max(height[a], 1e-12)
                if lo_r * w <= r <= hi_r * w:
                    alias.add(int(idx[b]))
    keep = np.array([i for i in idx if int(i) not in alias], dtype=np.int64)
    dropped = np.array(sorted(alias), dtype=np.int64)
    return keep, dropped


def detect_peaks(data: PatternData, instrument: Instrument, *,
                 two_theta_limits: tuple[float, float] | None = None,
                 shoulders: bool = True) -> Detection:
    """Detect every candidate line and group them into frozen fit windows.

    ``two_theta_limits`` crops on top of ``data.excluded_regions``; the
    excluded channels are removed rather than masked, because a window that
    straddles a gap has no meaningful frozen background.
    """
    from ..schemas.pattern import require_two_theta

    require_two_theta(data, "detect_peaks()", instrument=instrument)
    mask = data.in_range_mask()
    tt_all, y_all, sig_all = data.tt(), data.y(), data.sig()
    if two_theta_limits is not None:
        lo, hi = two_theta_limits
        mask = mask & (tt_all >= lo) & (tt_all <= hi)
    tt, y, sigma = tt_all[mask], y_all[mask], sig_all[mask]
    if len(tt) < 16:
        raise ValueError(
            f"only {len(tt)} points survive the mask and 2θ range; peak "
            "picking needs a pattern, not a window")

    fwhm_pred = predicted_fwhm(tt, instrument)
    env, net, step, idx, props = _candidates(tt, y, sigma, fwhm_pred)

    # width census: rank by prominence, then measure — never the reverse
    fwhm_meas = float(np.median(fwhm_pred))
    scale = 1.0
    if len(idx):
        rank, fwhm_meas = _census(net, idx, props, step)
        ref = float(np.median(fwhm_pred[idx[rank]]))
        if ref > 0.0 and fwhm_meas > 0.0:
            scale = float(np.clip(fwhm_meas / ref, *PEAK_WIDTH_SCALE_BOUNDS))
    fwhm_seed_curve = scale * fwhm_pred
    n_trials = _resolution_elements(tt, fwhm_seed_curve)

    # the Kα2 maximum of a resolved doublet is not a line — drop it before it
    # can become a group of its own with its own doublet
    idx, alias_idx = _drop_kalpha2_aliases(
        tt, idx, net[idx], fwhm_seed_curve, instrument)

    # a dropped alias is a strong real maximum, so it must be forbidden to the
    # curvature seeder too — otherwise it comes straight back as a "shoulder".
    # The *predicted* alias positions of every claimed maximum are forbidden as
    # well, which is the unresolved half of the same defect: see
    # :func:`_shoulder_seeds`.
    claimed = np.concatenate([idx, alias_idx]).astype(np.int64)
    if shoulders:
        pred = _secondary_line_two_theta(tt[idx], instrument).ravel()
        shoulder_idx, shoulder_alias = _shoulder_seeds(
            tt, net, sigma, fwhm_seed_curve, claimed, pred[np.isfinite(pred)])
        alias_idx = np.array(sorted(set(alias_idx.tolist())
                                    | set(shoulder_alias.tolist())),
                             dtype=np.int64)
    else:
        shoulder_idx = np.array([], dtype=np.int64)
    all_idx = np.concatenate([idx, shoulder_idx]).astype(np.int64)
    if not len(all_idx):
        return Detection(tt, y, sigma, env, [], fwhm_meas,
                         float(np.median(fwhm_pred)), scale, 0,
                         tt[alias_idx], n_trials)
    order = np.argsort(tt[all_idx])
    all_idx = all_idx[order]
    is_shoulder = np.isin(all_idx, shoulder_idx)

    groups = _group_indices(tt[all_idx], fwhm_seed_curve[all_idx])
    out: list[PeakGroup] = []
    for members in groups:
        seeds = tt[all_idx[members]]
        fw = float(np.mean(fwhm_seed_curve[all_idx[members]]))
        i0, i1 = window_indices(tt, seeds.min(), seeds.max(), fw, instrument)
        out.append(PeakGroup(i0=i0, i1=i1, seed_two_theta=seeds, seed_fwhm=fw,
                             from_shoulder=is_shoulder[members]))
    return Detection(tt, y, sigma, env, out, fwhm_meas,
                     float(np.median(fwhm_pred)), scale, int(len(shoulder_idx)),
                     tt[alias_idx], n_trials)


#: A step this many times the median channel step is a gap — an excluded
#: region the picker removed rather than masked — not a place it searched.
TRIAL_GAP_STEPS = 3.0


def _resolution_elements(tt: np.ndarray, fwhm: np.ndarray) -> float:
    """∫ d2θ / FWHM(2θ) over the channels detection actually searched.

    Excluded channels are removed from tt, so a step spanning one is much
    larger than the channel step; it is skipped rather than counted, since a
    line was never looked for there and counting it would raise the
    false-discovery bar for every line that was."""
    d = np.diff(tt)
    if not len(d):
        return 0.0
    searched = d <= TRIAL_GAP_STEPS * float(np.median(d))
    return float(np.sum(d[searched] / fwhm[:-1][searched]))


def _candidates(tt: np.ndarray, y: np.ndarray, sigma: np.ndarray,
                fwhm_pred: np.ndarray):
    """The σ-normalised maxima detection starts from, and what found them:
    ``(envelope, net, step, indices, find_peaks properties)``.  Shared by
    :func:`detect_peaks` and :func:`width_census`, so the census a refinement
    takes is the one indexing takes, line for line."""
    env = _debiased_envelope(tt, y)
    net = y - env
    z = np.where(net > 0.0, net, 0.0) / sigma
    step = float(np.median(np.diff(tt)))
    dist = max(int(PEAK_DETECT_SEPARATION_FWHM_FRAC
                   * float(fwhm_pred.min()) / max(step, 1e-12)), 1)
    idx, props = find_peaks(z, height=PEAK_MIN_HEIGHT_SIGMA,
                            prominence=PEAK_MIN_PROMINENCE_SIGMA,
                            distance=dist)
    return env, net, step, idx, props


def _census(net: np.ndarray, idx: np.ndarray, props: dict, step: float
            ) -> tuple[np.ndarray, float]:
    """The :data:`~rietx.schemas.indexing.PEAK_WIDTH_CENSUS_N` most prominent
    maxima (positions into ``idx``) and their median FWHM in ° 2θ."""
    rank = np.argsort(props["prominences"])[::-1][:PEAK_WIDTH_CENSUS_N]
    widths, *_ = peak_widths(net, idx[rank], rel_height=0.5)
    return rank, float(np.median(widths)) * step


def width_census(tt: np.ndarray, y: np.ndarray, sigma: np.ndarray,
                 fwhm_pred: np.ndarray) -> tuple[np.ndarray, float] | None:
    """The width census alone, on arrays a caller already masked: the 2θ of
    the census lines and their median measured FWHM, or ``None`` when no line
    clears detection's thresholds (or there are too few points to look).

    ``fwhm_pred`` is the width law the separation floor is sized from, as in
    :func:`detect_peaks`; it does not enter the measurement.  No groups, no
    aliases and no shoulders: this is the half of a :class:`Detection` the
    refinement path needs (:func:`~rietx.indexing.diagnostics.\
refinement_width_diagnostics` says why it needs it at all).
    """
    if len(tt) < 16:
        return None
    _env, net, step, idx, props = _candidates(tt, y, sigma, fwhm_pred)
    if not len(idx):
        return None
    rank, fwhm_meas = _census(net, idx, props, step)
    return tt[idx[rank]], fwhm_meas


def _group_indices(tt: np.ndarray, fwhm: np.ndarray) -> list[np.ndarray]:
    """Every seed's group, singletons included.

    ``_overlap_groups`` is the package's one definition of "these peaks
    overlap" (it returns multi-member runs only, since Pawley needs restraints
    for nothing else); the singletons it omits are filled back in here so every
    seed lands in exactly one fitting window.
    """
    multi = _overlap_groups(tt, fwhm)
    claimed = {k for g in multi for k in g}
    groups = [np.array(g, dtype=np.int64) for g in multi]
    groups += [np.array([k], dtype=np.int64)
               for k in range(len(tt)) if k not in claimed]
    groups.sort(key=lambda g: int(g[0]))
    return groups


def fdr_screen(peaks: list[ObservedPeak], det: Detection, *,
               q: float = PEAK_FDR_Q) -> FdrScreen:
    """Benjamini–Hochberg on each fitted component's I/σ_I, over the pattern.

    **Which components are tested.**  Every component not already unusable
    (``weak_line`` is not, so the screen is a pure function of the list and
    reads the same before and after it has flagged), and not placed by a human (``origin="manual"``: the position is the
    caller's claim, not detection's proposal).

    **The p-value** is one-sided, Φ̄(I/σ_I): a line has positive intensity, and
    under "no line here" a fitted intensity is centred on zero with the fit's
    own esd.  A component with no finite esd has p = 1.

    **The number of tests is the pattern's, not the list's.**  Detection looked
    for a line at every resolution element of the range, and kept a component
    only where it found an excess; dividing by the number of components it kept
    would forget every place it looked and found nothing, which is the
    look-elsewhere error one rank down.  So m = ``det.n_trials`` (∫ d2θ / FWHM),
    never less than the number tested; a hand-built detection without it uses
    the span over the census width.

    Then BH's step-up rule (Benjamini & Hochberg 1995, *J. R. Stat. Soc. B* 57,
    289): k* = max{k : p₍ₖ₎ ≤ k·q/m}, and the k* smallest p-values are
    discoveries.  The bound it gives — E[false / kept] ≤ q — is what
    ``expected_false`` reports as q·k*.
    """
    tested: list[int] = []
    pvals: list[float] = []
    for k, p in enumerate(peaks):
        if p.origin == "manual" or set(p.flags) & PEAK_UNUSABLE_FLAGS:
            continue
        esd = float(p.intensity_esd)
        z = float(p.intensity) / esd if np.isfinite(esd) and esd > 0.0 else -np.inf
        tested.append(k)
        pvals.append(float(ndtr(-z)) if np.isfinite(z) else 1.0)
    m = det.n_trials
    if not (np.isfinite(m) and m > 0.0):
        span = float(det.two_theta[-1] - det.two_theta[0])
        m = span / det.fwhm_measured if det.fwhm_measured > 0.0 else 1.0
    m = max(float(m), float(len(tested)), 1.0)
    p = np.asarray(pvals, dtype=np.float64)
    order = np.argsort(p, kind="stable")
    ranks = np.arange(1, len(p) + 1, dtype=np.float64)
    passing = np.nonzero(p[order] <= ranks * q / m)[0]
    n_kept = int(passing[-1]) + 1 if len(passing) else 0
    kept = set(order[:n_kept].tolist())
    weak = tuple(tested[i] for i in range(len(tested)) if i not in kept)
    cut = max(n_kept, 1) * q / m
    return FdrScreen(q=float(q), n_trials=float(m), n_tested=len(tested),
                     n_kept=n_kept, z_threshold=float(-ndtri(cut)),
                     expected_false=float(q * n_kept), weak=weak)


#: re-exported so a caller can see which constant set the grouping
__all__ = ["Detection", "FdrScreen", "MIN_GROUP_POINTS", "PeakGroup",
           "PAWLEY_OVERLAP_FWHM_FRAC", "detect_peaks", "fdr_screen", "group_at",
           "predicted_fwhm", "window_indices"]
