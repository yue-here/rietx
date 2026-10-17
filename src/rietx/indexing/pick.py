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
  genuinely contains.  The exception is a component of **comparable** area
  closer to its neighbour than Sparrow's limit for the fitted shape
  (:func:`~rietx.indexing.peakfit.unresolved_mates`): no dip can exist there,
  so the split is the model's and not the pattern's, and the pair is reported
  as one line with a σ that reaches both (``unresolved_split``, #934).  Even
  then nothing is deleted: the merged component stays in ``peaks``.
"""

from __future__ import annotations

import numpy as np

from ..background import contamination_flags_from_peaks
from ..model.forward import PAWLEY_OVERLAP_FWHM_FRAC
from ..schemas.indexing import (
    PEAK_ASYMMETRY_MIN_SIGMA,
    PEAK_AXIAL_TAIL_MAX_FWHM,
    PEAK_NO_INTENSITY_SIGMA,
    PEAK_POSITION_ESD_MAX_DEG,
    PEAK_REFUTED_SIGMA,
    PEAK_SATELLITE_MAX_RATIO,
    PEAK_SATELLITE_NEAR_FWHM,
    PEAK_UNUSABLE_FLAGS,
    ObservedPeak,
    PeakFlag,
    PeakList,
    q_esd_of_two_theta,
    q_of_two_theta,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData, require_two_theta
from ..strategy.staged import BOUND_HIT_RTOL
from .diagnostics import peak_diagnostics
from .peakfit import GroupFit, fit_group, fit_group_at, reseed_candidate
from .peaks import Detection, FdrScreen, PeakGroup, detect_peaks, fdr_screen, group_at


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
    require_two_theta(data, "pick_peaks()", instrument=instrument)
    det = detect_peaks(data, instrument, two_theta_range=two_theta_range,
                       shoulders=shoulders)
    lam0 = instrument.source.lines[0].wavelength.value

    fits = [fit_group(det, g, instrument) for g in det.groups]
    peaks = _peaks_from_fits(fits, lam0)
    if flag_contamination and peaks:
        flag_ghosts(peaks, lam0, det, source=instrument.source)
    if peaks:
        flag_kalpha2_residuals(peaks, instrument.source.lines)
    _flag_extrapolated_background(peaks, det.two_theta)
    flag_duplicate_lines(peaks)
    flag_weak_lines(peaks, det)

    pl = PeakList(
        peaks=peaks, wavelength=lam0,
        two_theta_min=float(det.two_theta[0]),
        two_theta_max=float(det.two_theta[-1]),
        source="fitted")
    return pl.model_copy(update={
        "diagnostics": peak_diagnostics(pl, det)}), det, fits


def fit_peaks(data: PatternData, instrument: Instrument,
              positions: np.ndarray | list[float], *,
              two_theta_range: tuple[float, float] | None = None,
              ) -> PeakList:
    """Profile-fit the peaks at ``positions`` and nothing else, with no structure,
    space group or refinement.

    The peer of :func:`pick_peaks` for the case where the caller already knows
    where the peaks are: a Williamson-Hall analysis over a chosen set of lines,
    a d-spacing lookup, a lab check on one reflection.  Detection still runs,
    for the background envelope and the window sizing, but it no longer decides
    *what* is fitted: in every window the components are the caller's positions
    and nothing else, which is
    :func:`~rietx.indexing.peakfit.fit_group_at`'s contract one level up.

    Positions inside a detected group's window reuse that frozen window;
    positions sharing a window are fitted **together**, as one simultaneous
    solve, since overlapping components fitted separately each bias the other.
    A position where detection found nothing gets a fresh window sized exactly
    as detection sizes its own (:func:`~rietx.indexing.peaks.group_at`), and a
    position off the end of the pattern or in a gap is refused by name rather
    than fitted into nonsense, as is the same position named twice — two
    components at one 2θ are exactly singular in their intensities.

    **Four things a caller must know about the answer.**  (1) Every line
    carries ``origin="manual"``: these positions are the caller's, not
    detection's proposals.  (2) A named position where there is no peak comes
    back *flagged* ``no_intensity`` and unusable — not dropped, and never
    quietly turned into a measurement.  Naming a position that turns out to be
    empty is a correct request, and dropping it is the version that made the
    GUI's add verb do nothing.  Such a component has no gradient on its own
    position, so what comes back is wherever the solve left it (measured: 40 m°
    from the seed, with an esd of 1e+16 degrees saying exactly that) — the flag
    is the answer, the number is not.
    (3) The two resolvability judgements of detection (``unresolved_split``,
    ``width_capped``) are **not** made: the components are the caller's, so a
    named pair closer than Sparrow's limit comes back as two lines.
    (4) Where the window holds a component the list did not name, its named
    lines are flagged ``unnamed_neighbour``: the unnamed intensity had nowhere
    to go but into them.  The question is asked of the caller's own fit, and
    answered the way :func:`fit_group` answers it for detection's seeds — the
    residual proposes a position and ΔBIC decides whether it pays
    (:func:`~rietx.indexing.peakfit.reseed_candidate`) — so it catches a
    component detection never seeded as well as one it did.

    Returns a :class:`PeakList` like :func:`pick_peaks`, so
    :meth:`PeakList.usable` is still the screened view and ``peaks`` still
    holds everything with its reasons attached.
    """
    require_two_theta(data, "fit_peaks()", instrument=instrument)
    pos = np.sort(np.asarray(positions, dtype=np.float64).ravel())
    if not len(pos):
        raise ValueError("fit_peaks needs at least one position to fit")
    # two components at one position are the same component twice: the solve is
    # exactly singular in their intensities, and what comes back is an
    # arbitrary split of one peak wearing two esds.  Refused by name, as a gap
    # is, rather than answered
    if len(pos) > 1:
        same = pos[:-1][np.diff(pos) == 0.0]
        if len(same):
            raise ValueError(
                f"2θ = {same[0]:.4f}° is named more than once; two components "
                "at one position cannot be told apart, so name it once")
    det = detect_peaks(data, instrument, two_theta_range=two_theta_range)
    lam0 = instrument.source.lines[0].wavelength.value

    groups = _windows_for(det, pos, instrument)

    peaks: list[ObservedPeak] = []
    for gi, group in enumerate(groups):
        fit = fit_group_at(det, group, instrument, group.seed_two_theta)
        crowded = reseed_candidate(det, group, instrument, fit) is not None
        for peak in peaks_of_group(fit, gi, lam0):
            peak.origin = "manual"
            if crowded:
                peak.flags = [*peak.flags, "unnamed_neighbour"]
            peaks.append(peak)
    peaks.sort(key=lambda p: p.two_theta)

    flag_ghosts(peaks, lam0, det, source=instrument.source)
    flag_kalpha2_residuals(peaks, instrument.source.lines)
    _flag_extrapolated_background(peaks, det.two_theta)

    pl = PeakList(
        peaks=peaks, wavelength=lam0,
        two_theta_min=float(det.two_theta[0]),
        two_theta_max=float(det.two_theta[-1]),
        source="fitted")
    # PEAK_LIST_TOO_SHORT is a statement about indexing a pattern, and
    # PEAK_EXPECTED_FALSE_LINES one about detecting in it; here the count and
    # the positions are the caller's own argument rather than anything the
    # pattern said
    diags = [d for d in peak_diagnostics(pl, det, windows=groups)
             if d.code not in ("PEAK_LIST_TOO_SHORT",
                               "PEAK_EXPECTED_FALSE_LINES")]
    return pl.model_copy(update={"diagnostics": diags})


def _windows_for(det: Detection, pos: np.ndarray,
                 instrument: Instrument) -> list[PeakGroup]:
    """The caller's positions, grouped into the windows they will be fitted in.

    A detected window is *reused* rather than re-sized: it is the window the
    background envelope and the seed width were measured over, and re-sizing it
    around a subset of its components would fit the same intensity against a
    different baseline.  Everything else gets a fresh window, and a position
    that falls inside one already being built joins it.
    """
    reuse: dict[int, list[float]] = {}
    fresh: list[float] = []
    for x in pos.tolist():
        hits = [k for k, g in enumerate(det.groups)
                if det.two_theta[g.i0] <= x <= det.two_theta[g.i1 - 1]]
        if hits:
            # windows overlap by their margins; the group whose components sit
            # closest is the one the caller meant (the peak editor's rule)
            k = min(hits, key=lambda k: float(
                np.min(np.abs(x - det.groups[k].seed_two_theta))))
            reuse.setdefault(k, []).append(x)
        else:
            fresh.append(x)

    out = [PeakGroup(i0=det.groups[k].i0, i1=det.groups[k].i1,
                     seed_two_theta=np.asarray(xs, dtype=np.float64),
                     seed_fwhm=det.groups[k].seed_fwhm,
                     from_shoulder=np.zeros(len(xs), dtype=bool))
           for k, xs in reuse.items()]

    i = 0
    while i < len(fresh):
        cluster = [fresh[i]]
        window = group_at(det, np.asarray(cluster), instrument)
        while (i + 1 < len(fresh)
               and fresh[i + 1] <= det.two_theta[window.i1 - 1]):
            cluster.append(fresh[i + 1])
            i += 1
            window = group_at(det, np.asarray(cluster), instrument)
        out.append(window)
        i += 1
    return sorted(out, key=lambda g: g.i0)


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

    **A component whose intensity is not distinguishable from none is flagged
    ``no_intensity`` and is unusable**: one under
    :data:`~rietx.schemas.indexing.PEAK_NO_INTENSITY_SIGMA` (1) of its own esd,
    which is how a "line" on a flank the background envelope under-tracks shows
    itself (the net cleared detection's 5σ, the fit's intensity is a third of its
    esd).  **And one sitting at its zero intensity bound** (WP-1110 item 14).  A peak reaches its
    window only through ``intensity × profile``, so one that refined to no
    intensity contributes nothing and its own position stops being
    identifiable — item 13's rule about a phase the data cannot see, one rank
    down.  "At its bound" is the distance the refinement's own bound test
    falls back on where no solve stands behind it (``bound_findings``; with
    one it reads the driver's exact active set or a conjunction, WP-1434 and
    WP-1929), and the constant is imported rather than restated so the two
    cannot drift apart.

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
    merged = (np.full(fit.n, -1, dtype=np.int64) if fit.merged_into is None
              else np.asarray(fit.merged_into, dtype=np.int64))
    return [ObservedPeak(
        two_theta=(tt := float(fit.two_theta[j])),
        two_theta_esd=(esd := _position_esd(fit, j, merged)),
        two_theta_esd_fit=(float(fit.two_theta_esd[j])
                           if bool(np.any(merged == j)) else None),
        intensity=float(fit.intensity[j]),
        intensity_esd=float(fit.intensity_esd[j]),
        q=float(q_of_two_theta(np.array(tt), wavelength)),
        q_esd=float(q_esd_of_two_theta(np.array(tt), np.array(esd), wavelength)),
        fwhm=fit.fwhm, eta=fit.eta, group=group_index, n_in_group=fit.n,
        chi2_red=fit.chi2_red, flags=_flags_for(fit, j, merged))
        for j in range(fit.n)]


def _position_esd(fit: GroupFit, j: int, merged: np.ndarray) -> float:
    """σ(2θ) of the line component ``j`` reports.

    A component that unresolved split components were merged into
    (``merged == j``, :func:`~rietx.indexing.peakfit.unresolved_mates`)
    reports the split as **one line**, at its own fitted position, with σ
    widened in quadrature by the farthest merged component's distance from it:
    a ±σ window then covers every position the split proposed, so the esd
    says what the list cannot resolve instead of quoting two precise positions
    the data do not support.  Position, area and width stay the component's
    own, which keeps the stored list redrawable as the fit it came from (the
    peak editor rebuilds a group from its members).  The fit's own σ rides
    beside it as ``two_theta_esd_fit``, because a **ranking** by measurement
    quality (:func:`flag_duplicate_lines`) must not move a line down for having
    absorbed a split.
    """
    own = float(fit.two_theta_esd[j])
    if merged[j] >= 0:
        return own
    mates = np.nonzero(merged == j)[0]
    if not len(mates):
        return own
    reach = float(np.max(np.abs(fit.two_theta[mates] - fit.two_theta[j])))
    return float(np.hypot(own, reach))


def _flags_for(fit: GroupFit, j: int,
               merged: np.ndarray | None = None) -> list[PeakFlag]:
    """Flags implied by one component's converged state."""
    if merged is None:
        merged = np.full(fit.n, -1, dtype=np.int64)
    flags: list[PeakFlag] = []
    if not fit.converged:
        flags.append("fit_failed")
    if bool(fit.at_bound[j]):
        flags.append("position_at_bound")
    if merged[j] >= 0:
        flags.append("unresolved_split")
    elif _unresolved(fit, j, merged):
        flags.append("unresolved_shoulder")
    if fit.width_at_bound:
        flags.append("width_capped")
    if _not_separable(fit, j):
        flags.append("not_separable")
    if _axial_tail(fit, j):
        flags.append("axial_tail")
    if (float(fit.intensity[j]) <= BOUND_HIT_RTOL
            or float(fit.intensity[j])
            < PEAK_NO_INTENSITY_SIGMA * float(fit.intensity_esd[j])):
        flags.append("no_intensity")
    if not (float(fit.two_theta_esd[j]) < PEAK_POSITION_ESD_MAX_DEG):
        flags.append("position_unmeasured")
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


def _unresolved(fit: GroupFit, j: int,
                merged: np.ndarray | None = None) -> bool:
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
    # a component merged into a line is that line, not a neighbour of it
    keep = np.ones(fit.n, dtype=bool) if merged is None else merged < 0
    keep[j] = False
    if not keep.any():
        return False
    others = fit.two_theta[keep]
    return bool(np.min(np.abs(others - fit.two_theta[j])) < gap)


def _rank_esd(p: ObservedPeak) -> float:
    """The esd that ranks a copy: the fit's own, never one widened by a merge."""
    return p.two_theta_esd if p.two_theta_esd_fit is None else p.two_theta_esd_fit


def flag_duplicate_lines(peaks: list[ObservedPeak], *,
                         only: set[int] | None = None) -> None:
    """Mark a line that another group has already fitted as ``duplicate_line``.

    Detection gives every seed to exactly one group, and groups are separated by
    :data:`~rietx.model.forward.PAWLEY_OVERLAP_FWHM_FRAC` of a FWHM (the
    package's one definition of "these overlap").  Two components of
    *different* groups closer than that are therefore one physical line, and
    the only way they meet is a re-seed pass: the window around a group holds a
    neighbour's maximum nothing models, the residual proposes it, and the
    ΔBIC gate pays for it.  Measured on the 16 IUCr round-robin lab patterns and
    11-BM NAC, a quarter to a third of the re-seeded components were such
    copies, 27 of the 116 on ``cpd-4``.

    The better-measured copy (smaller position esd, then lower group index; the
    fit's own esd, not one widened to reach merged splits) is
    the line and the other is flagged.  Components are judged best first, and
    only an unflagged one owns a line.  So in a chain of three copies, each
    within the tolerance of the next, the far end is not lost to a middle copy
    that was itself flagged.  A component already unusable neither
    owns a line nor needs marking: a zero-intensity copy has no position to
    duplicate anything with.  The copy is **kept in the list**, as
    ``not_separable``'s component is: it is the context that let the first
    window fit its own line, so deleting it would bias that line.  It is
    unusable, because offered as a second line it reads as an observed line no
    candidate cell explains.  ``only`` restricts which components can be marked,
    for the one-group refit of the peak editor, for the reason
    :func:`flag_ghosts`' does.
    """
    if len(peaks) < 2:
        return
    # unusable components are dropped before the sort: one may carry a NaN esd
    # (``position_unmeasured``), and a NaN key breaks the order of the rest
    usable = [k for k in range(len(peaks))
              if not set(peaks[k].flags) & PEAK_UNUSABLE_FLAGS]
    # a line that unresolved split components were merged into spans them
    # (``unresolved_split``): another group's copy of the same line may sit on
    # any of their positions, not only on the one the line reports
    lo_of = {k: peaks[k].two_theta for k in usable}
    hi_of = dict(lo_of)
    for s_ in range(len(peaks)):
        if "unresolved_split" not in peaks[s_].flags:
            continue
        mates = [k for k in usable if peaks[k].group == peaks[s_].group]
        if not mates:
            continue
        k = min(mates, key=lambda k: abs(peaks[k].two_theta - peaks[s_].two_theta))
        lo_of[k] = min(lo_of[k], peaks[s_].two_theta)
        hi_of[k] = max(hi_of[k], peaks[s_].two_theta)
    # owners: the unflagged usable components judged so far, as 2θ extents
    owners: list[tuple[float, float, int]] = []
    for k in sorted(usable, key=lambda k: (_rank_esd(peaks[k]), peaks[k].group)):
        p = peaks[k]
        tol = PAWLEY_OVERLAP_FWHM_FRAC * p.fwhm
        lo, hi = lo_of[k] - tol, hi_of[k] + tol
        if ((only is None or k in only)
                and any(g != p.group and a <= hi and b >= lo
                        for a, b, g in owners)):
            p.flags = [*p.flags, "duplicate_line"]
            continue
        owners.append((lo_of[k], hi_of[k], p.group))


def flag_weak_lines(peaks: list[ObservedPeak], det: Detection, *,
                    only: set[int] | None = None) -> FdrScreen:
    """Mark components the pattern's false-discovery threshold rejects as
    ``weak_line``, and return the screen.

    The threshold is :func:`~rietx.indexing.peaks.fdr_screen`'s:
    Benjamini–Hochberg at :data:`~rietx.schemas.indexing.PEAK_FDR_Q` on each
    component's I/σ_I over the pattern's resolution elements.  It is computed
    from the **whole** list every time — a false-discovery threshold is a
    property of the pattern, not of a line — so the flag is **set and cleared**
    on every component to follow it: an edit that moves the bar moves it for
    every line, and a flag the bar no longer supports must not outlive it.
    ``only`` restricts which components may be touched, as :func:`flag_ghosts`'
    does for its local flags; the peak editor does not pass it.

    **Reported, not refused** — the flag is absent from ``PEAK_UNUSABLE_FLAGS``,
    for ``axial_tail``'s reason: it is evidence, not proof.  Measured both ways:
    on synthetic silicon it marks the steep-flank and tail junk and no silicon
    line, while on the certified lab patterns a component under the bar is
    often a real weak line the certified cell indexes (refusing them moved five
    indexing-acceptance rows, corundum's truth from 45 indexed lines to 44).
    Whether a flagged component is a weak line or noise is a question a longer
    count answers.
    """
    screen = fdr_screen(peaks, det)
    weak = set(screen.weak)
    for k, p in enumerate(peaks):
        if only is not None and k not in only:
            continue
        if k in weak and "weak_line" not in p.flags:
            p.flags = [*p.flags, "weak_line"]
        elif k not in weak and "weak_line" in p.flags:
            p.flags = [f for f in p.flags if f != "weak_line"]
    return screen


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
                det: Detection, *, only: set[int] | None = None,
                source: object | None = None) -> None:
    """Mark Kβ / W Lα ghosts in place, using the shared background rule.

    Matching is on *integrated* intensity and on the fitted σ(2θ) — the two
    things a fitted list has and the raw channel census does not — via the one
    implementation in ``background.contamination_flags_from_peaks``.

    ``only`` restricts which peaks may be *marked* (matching always sees the
    whole list — a ghost's parent can be anywhere).  WP-1027's editor passes the
    indices of the one group it refitted, so recomputing ghosts for the edited
    components cannot resurrect a mark a user cleared on an untouched one.

    ``source`` is the instrument's declared beam: a neutron source, or an X-ray
    one behind a monochromator, skips the search (WP-1445).
    """
    tt = np.array([p.two_theta for p in peaks])
    inten = np.array([p.intensity for p in peaks])
    esd = np.array([p.two_theta_esd for p in peaks])
    flags = contamination_flags_from_peaks(
        tt, inten, esd, wavelength,
        tt_range=(float(det.two_theta[0]), float(det.two_theta[-1])),
        source=source)
    by_kind = {"kbeta": "ghost_kbeta", "tungsten_la": "ghost_tungsten"}
    for f in flags:
        k = int(np.argmin(np.abs(tt - f.two_theta)))
        if only is not None and k not in only:
            continue
        name = by_kind[f.kind]
        if name not in peaks[k].flags:
            peaks[k].flags = [*peaks[k].flags, name]


__all__ = ["fit_peaks", "flag_duplicate_lines", "flag_ghosts",
           "flag_kalpha2_residuals", "flag_weak_lines",
           "peaks_of_group", "pick_peaks", "pick_peaks_with_state"]
