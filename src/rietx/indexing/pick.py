"""``pick_peaks`` — the public entry point: pattern in, :class:`PeakList` out.

Detection (:mod:`.peaks`), per-group profile fitting (:mod:`.peakfit`) and flag
translation (:mod:`.diagnostics`) are separate modules; this one is the order
they run in and the flags that come out of running them.

Nothing here decides physics.  The two rules it *does* own are both about what a
peak list must not silently drop:

* ghost lines are **flagged and excluded from** :meth:`PeakList.usable`, **never
  subtracted** — they stay in ``peaks`` so a report can say why a line went;
* a component whose fitted position never separated from its neighbour by half a
  FWHM is kept, flagged ``unresolved_shoulder``, rather than merged away.  Its σ
  already carries the correlation, and deleting it would hide a line the pattern
  genuinely contains.
"""

from __future__ import annotations

import numpy as np

from ..background import contamination_flags_from_peaks
from ..model.forward import PAWLEY_OVERLAP_FWHM_FRAC
from ..schemas.indexing import (
    PEAK_ASYMMETRY_MIN_SIGMA,
    PEAK_AXIAL_TAIL_MAX_FWHM,
    PEAK_REFUTED_SIGMA,
    PEAK_SATELLITE_MAX_RATIO,
    PEAK_SATELLITE_NEAR_FWHM,
    ObservedPeak,
    PeakFlag,
    PeakList,
    q_esd_of_two_theta,
    q_of_two_theta,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData
from ..strategy.staged import BOUND_HIT_RTOL
from .diagnostics import peak_diagnostics
from .peakfit import GroupFit, fit_group
from .peaks import Detection, detect_peaks


def pick_peaks(data: PatternData, instrument: Instrument, *,
               two_theta_range: tuple[float, float] | None = None,
               shoulders: bool = True,
               flag_contamination: bool = True,
               ) -> PeakList:
    """Every resolvable line in ``data``, with a fitted position and its esd.

    ``instrument`` is used for four things, none of them refined here: the
    primary wavelength and the emission-line set (positions and the doublet
    constraint), the U,V,W,X,Y width law (the separation floor and the width
    seeds), ``profile.shape`` (so the peak list and the refinement that follows
    share one peak shape), and the axial apertures (FCJ, applied and held).

    Returns a :class:`PeakList`; abstention is a *result*, so an unindexably
    short list comes back as a list carrying ``PEAK_LIST_TOO_SHORT`` rather than
    as an exception.
    """
    return pick_peaks_with_state(data, instrument,
                                 two_theta_range=two_theta_range,
                                 shoulders=shoulders,
                                 flag_contamination=flag_contamination)[0]


def pick_peaks_with_state(data: PatternData, instrument: Instrument, *,
                          two_theta_range: tuple[float, float] | None = None,
                          shoulders: bool = True,
                          flag_contamination: bool = True,
                          ) -> tuple[PeakList, Detection, list[GroupFit]]:
    """:func:`pick_peaks` plus the state it was derived from.

    The :class:`Detection` and per-group :class:`GroupFit` are what an *editor*
    needs and a consumer of the list does not: WP-1027's peak panel redraws each
    group's fitted profile (:func:`~rietx.indexing.peakfit.group_profile`) and
    refits a single group when a human corrects it, both of which want the frozen
    windows and the fitted width pairs rather than the flattened list.
    """
    det = detect_peaks(data, instrument, two_theta_range=two_theta_range,
                       shoulders=shoulders)
    lam0 = instrument.source.lines[0].wavelength.value

    fits = [fit_group(det, g, instrument) for g in det.groups]
    peaks = _peaks_from_fits(fits, lam0)
    if flag_contamination and peaks:
        flag_ghosts(peaks, lam0, det)
    if peaks:
        flag_kalpha2_residuals(peaks, instrument.source.lines)
    _flag_extrapolated_background(peaks, det.two_theta)

    pl = PeakList(
        peaks=peaks, wavelength=lam0,
        two_theta_min=float(det.two_theta[0]),
        two_theta_max=float(det.two_theta[-1]),
        source="fitted")
    return pl.model_copy(update={
        "diagnostics": peak_diagnostics(pl, det)}), det, fits


def _flag_extrapolated_background(peaks: list[ObservedPeak],
                                  two_theta: np.ndarray) -> None:
    """Flag lines standing where the background envelope was extrapolated.

    The envelope's knots sit at window *centres*, so the outermost half-window
    at each end of the pattern has no measured background under it — the level
    there comes from extending the two nearest knots (WP-1028 §(i)).  A line's
    prominence is measured against that level, so a line inside the
    extrapolated span is standing on a background nobody observed.

    **Reported, not refused**: these are real intensity, just not necessarily
    lines, and the consumer that can weigh that should be given the chance
    (the same rule the indexing gate follows).  The flag is therefore absent
    from :data:`~rietx.schemas.indexing.PEAK_UNUSABLE_FLAGS`.
    """
    from ..background.diagnostics import envelope_measured_span

    if not peaks or len(two_theta) < 3:
        return
    lo, hi = envelope_measured_span(two_theta)
    for peak in peaks:
        if (peak.two_theta < lo or peak.two_theta > hi) and \
                "background_extrapolated" not in peak.flags:
            peak.flags = [*peak.flags, "background_extrapolated"]


def _peaks_from_fits(fits: list[GroupFit], wavelength: float
                     ) -> list[ObservedPeak]:
    """Flatten the group fits into one 2θ-ordered list of lines."""
    out: list[ObservedPeak] = []
    for gi, fit in enumerate(fits):
        out.extend(peaks_of_group(fit, gi, wavelength))
    out.sort(key=lambda p: p.two_theta)
    return out


def peaks_of_group(fit: GroupFit, group_index: int, wavelength: float
                   ) -> list[ObservedPeak]:
    """One group's components as :class:`ObservedPeak`\\ s, flags translated.

    The per-group half of :func:`pick_peaks`, public because WP-1027's editor
    refits *one* group and splices the result into a stored list — the flag
    translation must be this one and not a second reading of it.

    **A component sitting at its zero intensity bound is flagged
    ``no_intensity`` and is unusable** (WP-1110 item 14).  A peak reaches its
    window only through ``intensity × profile``, so one that refined to no
    intensity contributes nothing and its own position stops being
    identifiable — item 13's rule about a phase the data cannot see, one rank
    down.  "At its bound" is the same test the refinement's ``BOUND_HIT`` uses,
    and the constant is imported rather than restated because there is one
    answer to that question.

    Flagged rather than dropped, for ``not_separable``'s reason and one more: a
    report must be able to say why a line went, and a component a **human**
    placed through the peak editor is theirs to see and remove — dropping it
    made the GUI's add verb silently do nothing.  ``_prune`` cannot catch these
    either, since it tests only *shoulder* seeds by deliberate asymmetry, so a
    **maximum**-detected component that clears detection and then refines to
    nothing is never reconsidered.

    It took equilibrating the covariance to see them at all.  On the certified
    corundum pattern two components refine to intensities of **2.1e-49** and
    **5.5e-19**; their position esds are ~1e+17 and ~1e+49 degrees, which the
    pre-WP-1110 pseudo-inverse truncated to 0.06°, so both were published as
    ordinary measured lines.  ``_max_index`` built from them reached a trial
    index of **3.1e+25** and the search died there.
    """
    return [ObservedPeak(
        two_theta=(tt := float(fit.two_theta[j])),
        two_theta_esd=(esd := float(fit.two_theta_esd[j])),
        intensity=float(fit.intensity[j]),
        intensity_esd=float(fit.intensity_esd[j]),
        q=float(q_of_two_theta(np.array(tt), wavelength)),
        q_esd=float(q_esd_of_two_theta(np.array(tt), np.array(esd), wavelength)),
        fwhm=fit.fwhm, eta=fit.eta, group=group_index, n_in_group=fit.n,
        chi2_red=fit.chi2_red, flags=_flags_for(fit, j))
        for j in range(fit.n)]


def _flags_for(fit: GroupFit, j: int) -> list[PeakFlag]:
    """Flags implied by one component's converged state."""
    flags: list[PeakFlag] = []
    if not fit.converged:
        flags.append("fit_failed")
    if bool(fit.at_bound[j]):
        flags.append("position_at_bound")
    if _unresolved(fit, j):
        flags.append("unresolved_shoulder")
    if _not_separable(fit, j):
        flags.append("not_separable")
    if _axial_tail(fit, j):
        flags.append("axial_tail")
    if float(fit.intensity[j]) <= BOUND_HIT_RTOL:
        flags.append("no_intensity")
    t = fit.asymmetry_t[j]
    if np.isfinite(t) and abs(t) >= PEAK_ASYMMETRY_MIN_SIGMA:
        flags.append("asymmetry_unmodelled")
    return flags


def _axial_tail(fit: GroupFit, j: int) -> bool:
    """Does component ``j`` sit on the axial-divergence **tail side** of a much
    stronger group-mate?

    The aberration's signature is the *sign*: axial divergence throws a peak's
    tail toward low 2θ below 90° and toward high 2θ above it, and nothing else
    in a powder pattern flips at 90° — WP-1028's census proved the side on
    every escaped component, and WP-1043 turned that proof into this screen.
    One-sided by construction (the same offset on the anti-tail side is never
    flagged), which is what separates it from widening
    ``PEAK_SATELLITE_NEAR_FWHM`` — the knob the census ruled out.  Weakness
    reuses ``PEAK_SATELLITE_MAX_RATIO``; the reach is
    ``PEAK_AXIAL_TAIL_MAX_FWHM``, spanning the census's measured 0.8-3.0 FWHM.

    **Reported, not refused** — the flag is absent from
    ``PEAK_UNUSABLE_FLAGS``: the side test is evidence, not proof, and a real
    weak line can sit there too (measured, the screen reaches 11 unverified
    usable components across the six other real lab patterns).  Measured on
    SRM 660c it catches exactly the five tails, worth 125 ppm of
    certified-cell bias, and excluding the flagged components is what took the
    gate to ``high`` at −2 ppm.
    """
    if fit.n < 2:
        return False
    strongest = int(np.argmax(fit.intensity))
    if strongest == j or fit.intensity[strongest] <= 0.0:
        return False
    if fit.intensity[j] >= PEAK_SATELLITE_MAX_RATIO * fit.intensity[strongest]:
        return False
    sep = float(fit.two_theta[j] - fit.two_theta[strongest])
    tail_side = -1.0 if fit.two_theta[strongest] < 90.0 else 1.0
    return bool(np.sign(sep) == tail_side
                and abs(sep) < PEAK_AXIAL_TAIL_MAX_FWHM * fit.fwhm)


def _not_separable(fit: GroupFit, j: int) -> bool:
    """Is component ``j`` a *shape* the fit believes in and a *line* it does not?

    Three conditions, and all three are needed because each alone is ordinary:

    1. **a re-seed pass put it there** — detection proposed the group's other
       components against a σ-normalised height test on the data, this one was
       proposed by a residual;
    2. **it is a satellite** — inside a group-mate's own profile
       (:data:`~rietx.schemas.indexing.PEAK_SATELLITE_NEAR_FWHM`) and small
       enough relative to it
       (:data:`~rietx.schemas.indexing.PEAK_SATELLITE_MAX_RATIO`) that the
       neighbour's shape error could account for it;
    3. **the group's fit is still refuted with it in** — χ²_red more than
       :data:`~rietx.schemas.indexing.PEAK_REFUTED_SIGMA` of its own σ(χ²_red)
       above 1 — so the ΔBIC gain that bought it cannot be attributed to a new
       line rather than to the shape of the old one.

    The third is the load-bearing one and the reason this is not simply a tighter
    ΔBIC.  ΔBIC asks whether the data prefer n+1 components to n; that is the
    same question as "is there a line here" only while the n-component model is
    capable of fitting.  Against a refuted model *any* extra component wins, and
    on real laboratory data the model is refuted at every strong peak — measured
    on qarr corundum, χ²_red 17.4 at n = 1 and 4.6 at n = 2 on the 104 line, with
    the component bought landing 1 FWHM below it at 10 % of its area.

    Note what this does **not** do: the component stays in the model and in
    ``peaks``.  It earns its place as shape — removing it would push the real
    line's fitted position (measured: 0.010° on that same line) — and it is only
    barred from ``usable()``, i.e. from being offered as evidence of a lattice.
    """
    if fit.n < 2 or not bool(fit.reseeded()[j]):
        return False
    # ν = points − (two shared widths + two parameters per component)
    dof = max(fit.n_points - 2 - 2 * fit.n, 1)
    refuted = 1.0 + PEAK_REFUTED_SIGMA * np.sqrt(2.0 / dof)
    if not (np.isfinite(fit.chi2_red) and fit.chi2_red > refuted):
        return False
    near = np.abs(fit.two_theta - fit.two_theta[j]) < PEAK_SATELLITE_NEAR_FWHM * fit.fwhm
    near[j] = False
    if not near.any():
        return False
    strongest = float(np.max(fit.intensity[near]))
    if strongest <= 0.0:
        return False
    return bool(fit.intensity[j] < PEAK_SATELLITE_MAX_RATIO * strongest)


def _unresolved(fit: GroupFit, j: int) -> bool:
    """Did component ``j`` end within half a FWHM of a group-mate?

    The test is on the *fitted* positions, not the seeds: grouping used the same
    criterion on seeds to decide what to fit together, and the interesting
    question afterwards is whether the fit managed to pull them apart.
    ``PAWLEY_OVERLAP_FWHM_FRAC`` is imported so "overlapped" keeps meaning one
    thing package-wide.
    """
    if fit.n < 2:
        return False
    gap = PAWLEY_OVERLAP_FWHM_FRAC * fit.fwhm
    others = np.delete(fit.two_theta, j)
    return bool(np.min(np.abs(others - fit.two_theta[j])) < gap)


def flag_kalpha2_residuals(peaks: list[ObservedPeak], lines, *,
                           only: set[int] | None = None) -> None:
    """Mark components sitting at a strong group-mate's **Kα2 maximum**.

    ``detect_peaks`` drops Kα2 *candidates* before any fit
    (``PEAK_KALPHA2_ALIAS``), but a wide group can re-create one afterwards:
    measured on SRM 660c (WP-1028's census, acted on by WP-1043), a re-seed
    pass landed a component on its mate's Kα2 position at 3 % of its area —
    the residual of a *modelled* doublet, not an unmodelled line — and escaped
    every screen because it was neither a detection (the alias screen never
    saw it) nor refuted (its group fits well).  The position here is
    **predicted** from the declared doublet splitting, not found by a distance
    knob: δ(2θ) = 2·(λ₂/λ₁ − 1)·tanθ at the mate's angle, within the mate's
    own FWHM.

    **Reported, not refused** — absent from ``PEAK_UNUSABLE_FLAGS`` for the
    same reason as ``axial_tail``: a real line can coincide with an alias
    position in one pattern, and the consumer that can weigh it decides.
    ``only`` restricts marking exactly as :func:`flag_ghosts`' does, for the
    same one-group-refit reason.  No-op on a single-line source: there is no
    doublet to leave a residual.
    """
    if len(lines) < 2:
        return
    ratio = lines[1].wavelength.value / lines[0].wavelength.value
    by_group: dict[int, list[int]] = {}
    for k, p in enumerate(peaks):
        by_group.setdefault(p.group, []).append(k)
    for members in by_group.values():
        if len(members) < 2:
            continue
        strongest = max(members, key=lambda k: peaks[k].intensity)
        strong = peaks[strongest]
        if strong.intensity <= 0.0:
            continue
        theta = np.radians(strong.two_theta / 2.0)
        alias = strong.two_theta + np.degrees(
            2.0 * (ratio - 1.0) * np.tan(theta))
        for k in members:
            p = peaks[k]
            if (k == strongest
                    or p.intensity >= PEAK_SATELLITE_MAX_RATIO * strong.intensity
                    or abs(p.two_theta - alias) >= strong.fwhm
                    or (only is not None and k not in only)
                    or "kalpha2_residual" in p.flags):
                continue
            p.flags = [*p.flags, "kalpha2_residual"]


def flag_ghosts(peaks: list[ObservedPeak], wavelength: float,
                det: Detection, *, only: set[int] | None = None) -> None:
    """Mark Kβ / W Lα ghosts in place, using the shared background rule.

    Matching is on *integrated* intensity and on the fitted σ(2θ) — the two
    things a fitted list has and the raw channel census does not — via the one
    implementation in ``background.contamination_flags_from_peaks``.

    ``only`` restricts which peaks may be *marked* (matching always sees the
    whole list — a ghost's parent can be anywhere).  WP-1027's editor passes the
    indices of the one group it refitted, so recomputing ghosts for the edited
    components cannot resurrect a mark a user cleared on an untouched one.
    """
    tt = np.array([p.two_theta for p in peaks])
    inten = np.array([p.intensity for p in peaks])
    esd = np.array([p.two_theta_esd for p in peaks])
    flags = contamination_flags_from_peaks(
        tt, inten, esd, wavelength,
        tt_range=(float(det.two_theta[0]), float(det.two_theta[-1])))
    by_kind = {"kbeta": "ghost_kbeta", "tungsten_la": "ghost_tungsten"}
    for f in flags:
        k = int(np.argmin(np.abs(tt - f.two_theta)))
        if only is not None and k not in only:
            continue
        name = by_kind[f.kind]
        if name not in peaks[k].flags:
            peaks[k].flags = [*peaks[k].flags, name]


__all__ = ["flag_ghosts", "flag_kalpha2_residuals", "peaks_of_group",
           "pick_peaks", "pick_peaks_with_state"]
