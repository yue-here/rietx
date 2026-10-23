"""``PEAK_*`` and ``INDEX_*`` diagnostics — a peak list's flags and a
data-quality verdict translated into the package's one structured-message
grammar.

Same shape as ``refine._guard_diagnostics``: the fitter records *facts* on each
line (``at_bound``, ``asymmetry_t``, a flag) and this module alone decides what
level they are and what to suggest.  Keeping the two apart is what lets a
threshold move without touching the fitter, and what stops a level being
implied by where the code happens to live.

The two translators stay separate (:func:`peak_diagnostics`,
:func:`quality_diagnostics`) because a peak list's flags and a verdict on whether
the list can be indexed are different statements about the same lines: an agent
that re-picks peaks in response to the first would be answering the wrong
question for the second.

Every message names a concrete call in its ``suggestion``, and ``where`` carries
the 2θ the statement is about — a peak list has no dot-paths (peak parameters
deliberately never enter a history node's ``free_paths``), so 2θ is the only
address a consumer can act on.
"""

from __future__ import annotations

import math

import numpy as np

from ..crystallography.atomic_volume import VOLUME_SCATTER, formula_unit_volume
from ..model.profiles.fcj import fcj_live
from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    MAX_RELATIVE_SIGMA_Q,
    PEAK_MIN_USABLE_LINES,
    PEAK_WIDTH_CENSUS_N,
    DataQualityReport,
    PeakList,
)
from ..schemas.instrument import Instrument, ProfileTCHZ
from .peaks import Detection, fdr_screen

#: Physical cause of each shift template, for the messages.  The template names
#: themselves come from ``report/layer2.py``'s ``_POSITION_ACTIONS`` — one
#: physical cause, one name, package-wide.
SHIFT_CAUSE: dict[str, str] = {
    "constant": "a detector zero-point error (instrument.zero_shift)",
    "cos_theta": ("specimen displacement from the focusing circle "
                  "(instrument.geometry.sample_displacement)"),
    "sin_2theta": ("specimen transparency, where the beam penetrates a weakly "
                   "absorbing specimen (instrument.geometry.sample_transparency)"),
}

#: Ratio of measured to instrument-predicted FWHM above which the declared
#: instrument is reported as inconsistent with the data rather than merely
#: broadened by the sample.  3 is loose on purpose: real sample broadening of
#: 2-3× is ordinary, whereas the case worth shouting about is the ``ProfileTCHZ``
#: default (``W = 1e-3 deg²``, FWHM ≈ 0.03°, a *synchrotron* line) left on lab
#: data, which lands near 13.
WIDTH_MISMATCH_RATIO = 3.0


def peak_diagnostics(peaks: PeakList, detection: Detection | None = None,
                     ) -> list[Diagnostic]:
    """Translate a peak list's flags and a detection's width census.

    Public and separate from :func:`rietx.indexing.pick_peaks` because a list
    that arrives from outside — ``PeakList.from_positions``, i.e. the form the
    bethanechol benchmark comes in — needs the same translation without any
    detection to go with it.
    """
    out: list[Diagnostic] = []
    usable = peaks.usable()

    if len(usable) < PEAK_MIN_USABLE_LINES:
        out.append(Diagnostic(
            level="warning", code="PEAK_LIST_TOO_SHORT",
            message=(f"The list has {len(usable)} usable lines, below the "
                     f"{PEAK_MIN_USABLE_LINES} that the classical figures of "
                     "merit (M20, F_N) and Smith's volume envelope are scored "
                     "on, so this list can be searched but not scored."),
            where=[f"2θ {peaks.two_theta_min:.2f}-{peaks.two_theta_max:.2f}°"],
            suggestion=("Extend the 2θ range, count for longer or lower "
                        f"PEAK_MIN_HEIGHT_SIGMA until {PEAK_MIN_USABLE_LINES} "
                        "lines are usable.")))

    if peaks.source == "positions":
        out.append(Diagnostic(
            level="warning", code="PEAK_SIGMA_ASSUMED",
            message=("Every σ(2θ) in this list is an assumed value, so any "
                     "per-line weighting downstream weights every line equally."),
            where=[f"{len(peaks.peaks)} lines"],
            suggestion=("Run rietx.indexing.pick_peaks(data, instrument) on the "
                        "pattern, if you have it, to replace them with fitted "
                        "values.")))

    shoulders = [p for p in peaks.peaks if "unresolved_shoulder" in p.flags]
    if shoulders:
        out.append(Diagnostic(
            level="info", code="PEAK_UNRESOLVED_SHOULDER",
            message=(f"{len(shoulders)} line(s) never separated from a "
                     "neighbour by half a FWHM."),
            where=[f"{p.two_theta:.4f}°" for p in shoulders],
            suggestion=("Keep them, since their σ already carries the penalty. "
                        "Quote neither line of a pair as an independent "
                        "line.")))

    repair = [p for p in peaks.peaks if "not_separable" in p.flags]
    if repair:
        out.append(Diagnostic(
            level="warning", code="PEAK_NOT_SEPARABLE",
            message=(f"{len(repair)} component(s) were added by a re-seed pass "
                     "inside a much stronger neighbour's own profile, in a "
                     "group whose fit is still refuted."),
            where=[f"{p.two_theta:.4f}°" for p in repair],
            suggestion=("Leave them in the model, because removing one "
                        "displaces the real line it sits on. If many fire, "
                        "check the declared instrument profile, since "
                        "undeclared axial divergence reproduces this.")))

    split = [p for p in peaks.peaks if "unresolved_split" in p.flags]
    if split:
        out.append(Diagnostic(
            level="info", code="PEAK_UNRESOLVED_SPLIT",
            message=(f"{len(split)} component(s) lie within Sparrow's limit of "
                     "a comparable group-mate, so each pair is reported as one "
                     "line whose σ(2θ) reaches both."),
            where=[f"{p.two_theta:.4f}°" for p in split],
            suggestion=("Collect with a finer step, or declare the instrument "
                        "profile, to resolve real close pairs. If many appear, "
                        "suspect flat-topped or other non-pseudo-Voigt "
                        "lines.")))

    capped = [p for p in peaks.peaks if "width_capped" in p.flags]
    if capped:
        out.append(Diagnostic(
            level="info", code="PEAK_WIDTH_CAPPED",
            message=(f"{len(capped)} component(s) ran into the width bound of "
                     "five times the pattern's own width law at their angle, "
                     "and are excluded from usable()."),
            where=[f"{p.two_theta:.4f}°" for p in capped],
            suggestion=("On a steep or structured background, check whether "
                        "the background envelope followed it. For a broad "
                        "second phase, pick it separately at its own "
                        "width.")))

    tails = [p for p in peaks.peaks if "axial_tail" in p.flags]
    if tails:
        out.append(Diagnostic(
            level="info", code="PEAK_AXIAL_TAIL",
            message=(f"{len(tails)} weak component(s) sit on the "
                     "axial-divergence tail side of a much stronger "
                     "group-mate."),
            where=[f"{p.two_theta:.4f}°" for p in tails],
            suggestion=("Check each group's fit, then exclude the flagged "
                        "components with use_for_indexing=False on a "
                        "well-aligned Bragg-Brentano pattern. On SRM 660c, "
                        "five such components carried 125 ppm of cell "
                        "bias.")))

    residuals = [p for p in peaks.peaks if "kalpha2_residual" in p.flags]
    if residuals:
        out.append(Diagnostic(
            level="info", code="PEAK_KALPHA2_RESIDUAL",
            message=(f"{len(residuals)} weak component(s) sit at a strong "
                     "group-mate's predicted Kα2 maximum, at a few per cent of "
                     "its area."),
            where=[f"{p.two_theta:.4f}°" for p in residuals],
            suggestion=("Exclude them before indexing, unless the pattern "
                        "gives you a reason to believe a genuine reflection "
                        "hides under the doublet.")))

    ghosts = [p for p in peaks.peaks
              if {"ghost_kbeta", "ghost_tungsten"} & set(p.flags)]
    if ghosts:
        out.append(Diagnostic(
            level="info", code="PEAK_CONTAMINATION_LINE",
            message=(f"{len(ghosts)} line(s) sit at the Kβ or W Lα position of "
                     "a strong reflection and are excluded from usable()."),
            where=[f"{p.two_theta:.4f}°" for p in ghosts],
            suggestion=("Install a monochromator or filter on the "
                        "diffractometer to remove the line at source.")))

    asym = [p for p in peaks.peaks if "asymmetry_unmodelled" in p.flags]
    if asym:
        out.append(Diagnostic(
            level="warning", code="PEAK_ASYMMETRY_UNMODELLED",
            message=(f"{len(asym)} line(s) leave a significant odd residual "
                     "after fitting."),
            where=[f"{p.two_theta:.4f}°" for p in asym],
            suggestion=("Set instrument.geometry.axial_sl and axial_hl to the "
                        "real aperture ratios, then re-pick.")))

    if detection is not None and peaks.source == "fitted":
        out.append(_false_line_diagnostic(peaks, detection))
        out.extend(_width_diagnostics(detection))
    elif detection is not None:
        out.extend(_width_diagnostics(detection))
    return out


def _false_line_diagnostic(peaks: PeakList, det: Detection) -> Diagnostic:
    """``PEAK_EXPECTED_FALSE_LINES``: the threshold the pattern set, how many
    components it rejected, and how many of the kept lines are expected to be
    noise (``value``).  Always emitted for a detected list, because a peak list
    that never states its null is the defect (F2 § 3, G4); a line-free pattern
    reads 0 here, which is the answer, not an absence."""
    screen = fdr_screen(peaks.peaks, det)
    weak = [peaks.peaks[k] for k in screen.weak]
    message = (f"{screen.n_kept} of {screen.n_tested} fitted component(s) clear "
               f"the pattern's false-discovery bar (I/σ_I ≥ "
               f"{screen.z_threshold:.2f}, Benjamini–Hochberg at q = "
               f"{screen.q:g} over {screen.n_trials:.0f} resolution elements). "
               f"The expected number of noise lines among those kept is at "
               f"least {screen.expected_false:.2f}.")
    if weak:
        message += (f" {len(weak)} weaker component(s) are flagged "
                    "weak_line.")
    return Diagnostic(
        level="info", code="PEAK_EXPECTED_FALSE_LINES", message=message,
        where=[f"{p.two_theta:.4f}°" for p in weak],
        suggestion=("Keep weak_line components unless the list is known to "
                    "carry flank or tail junk. Count longer to tell weak "
                    "lines from noise."),
        value=screen.expected_false)


def _width_diagnostics(det: Detection) -> list[Diagnostic]:
    """The width census against the instrument's own law."""
    out: list[Diagnostic] = []
    if det.fwhm_predicted <= 0.0:
        return out
    ratio = det.fwhm_measured / det.fwhm_predicted
    if ratio >= WIDTH_MISMATCH_RATIO or ratio <= 1.0 / WIDTH_MISMATCH_RATIO:
        out.append(Diagnostic(
            level="warning", code="PEAK_WIDTH_LAW_MISMATCH",
            message=(f"The measured FWHM of {det.fwhm_measured:.4f}° differs "
                     f"by a factor of {ratio:.1f} from the "
                     f"{det.fwhm_predicted:.4f}° that the instrument's U, V, "
                     f"W, X and Y predict. Seeds and windows were scaled by "
                     f"{det.width_scale:.2f} to match the data."),
            where=[f"median of the {PEAK_WIDTH_CENSUS_N} most prominent lines"],
            suggestion=("Run lab_calibrate on a standard, or set U, V, W, X "
                        "and Y from one. A factor near 13 means the "
                        "ProfileTCHZ default (W = 1e-3 deg²), a synchrotron "
                        "line, is still in place.")))
    if len(det.alias_two_theta):
        out.append(Diagnostic(
            level="info", code="PEAK_KALPHA2_ALIAS",
            message=(f"{len(det.alias_two_theta)} candidate(s) were dropped as "
                     "the Kα2 maximum of a stronger line, so each reported "
                     "position is a Kα1 position."),
            where=[f"{t:.4f}°" for t in det.alias_two_theta],
            suggestion=("Confirm with an incident-side monochromator "
                        "(Instrument.bragg_brentano with Kα1-only radiation) "
                        "if one of these lines matters.")))
    if det.n_shoulder_seeds:
        out.append(Diagnostic(
            level="info", code="PEAK_SHOULDER_SEEDED",
            message=(f"{det.n_shoulder_seeds} curvature seed(s) were offered "
                     "for components with no local maximum, and ΔBIC decided "
                     "which survived."),
            where=[f"{len(det.groups)} groups"],
            suggestion=("Pass shoulders=False to pick_peaks to see the list "
                        "without them.")))
    return out


def refinement_width_diagnostics(measured: float,
                                 modelled: dict[int, tuple[str, float]],
                                 ) -> list[Diagnostic]:
    """``PEAK_WIDTH_LAW_MISMATCH`` on a refinement: the census against the
    fitted model's own widths (WP-1336, issue #249).

    ``measured`` is :func:`~rietx.indexing.peaks.width_census`'s median FWHM;
    ``modelled`` maps a phase index to its name and the median FWHM the
    *returned* parameters give that phase at the census lines — instrument
    U,V,W,X,Y plus the phase's isotropic size and strain terms.  It fires when
    no phase comes within :data:`WIDTH_MISMATCH_RATIO` of the data, either
    way, and reports the phase that came closest.

    **Why the census is wired into the fit rather than shipped as a
    precondition call** (issue #249 asked which).  The siloing was real — the
    census sat inside :func:`~rietx.indexing.peaks.detect_peaks`, and a
    refinement builds no :class:`~rietx.indexing.peaks.Detection` — but only
    the census half of a detection is needed, and it needs no groups.  Three
    reasons decide it the other way:

    * a ``check_instrument_against(data)`` call says nothing to the caller who
      does not know to make it, and #249's caller had no reason to, with a
      correctly transcribed profile;
    * a precondition can only compare against the *declared* instrument, which
      is the wrong comparator for a refinement: every sample whose size or
      strain the plan refines would trip it, and so would every fit whose
      refined U,V,W cured the mismatch — a warning true of the start and false
      of the answer.  The fit is the one place the reported widths exist;
    * cost: one ``find_peaks`` pass and twelve ``peak_widths`` on channels the
      fit already holds — measured at 1–3 ms on the three ``examples/`` fits
      (5 332–22 003 channels), against fits of seconds.

    The code and its row are the indexing path's, unchanged, because the
    statement is the same — the data's widths disagree with the widths the
    package was told to expect — and the help entry's fork (a broadened
    specimen is a finding, a wrong instrument a setup error) is the reading
    both paths need.  The *comparator* differs, and the message says which.
    """
    if not modelled or not measured > 0.0:
        return []
    ratios = {ip: measured / fw for ip, (_name, fw) in modelled.items() if fw > 0.0}
    if not ratios:
        return []
    ip = min(ratios, key=lambda k: abs(np.log(ratios[k])))
    ratio = ratios[ip]
    if 1.0 / WIDTH_MISMATCH_RATIO < ratio < WIDTH_MISMATCH_RATIO:
        return []
    name, fw = modelled[ip]
    others = "" if len(modelled) == 1 else ", the closest of the model's phases"
    if ratio >= WIDTH_MISMATCH_RATIO:
        suggestion = ("Free the phase's lor_size and lor_strain if the "
                      "specimen is broadened, or calibrate on a standard and "
                      "load the profile if instrument.profile is too narrow "
                      "for this diffractometer. Do not quote intensities, "
                      "occupancies or ADPs until the widths agree.")
    else:
        suggestion = ("Read SIZE_UNUSUALLY_SMALL, STRAIN_UNUSUALLY_LARGE and "
                      "BOUND_HIT for a width term that ran away, then check "
                      "that instrument.profile is not broader than this "
                      "diffractometer.")
    return [Diagnostic(
        level="warning", code="PEAK_WIDTH_LAW_MISMATCH",
        message=(f"The measured FWHM of {measured:.4f}° (median of the "
                 f"{PEAK_WIDTH_CENSUS_N} most prominent lines) differs by a "
                 f"factor of {ratio:.1f} from the {fw:.4f}° that the fitted "
                 f"widths of phase {ip} ({name}{others}) give."),
        where=[f"phases.{ip}", "instrument.profile"],
        suggestion=suggestion, value=ratio)]


def lab_source(instrument: Instrument) -> bool:
    """Does ``instrument`` declare a laboratory X-ray tube?

    Read off the declared source, never guessed from the pattern (WP-2030): a
    constant-wavelength X-ray source carrying a Kα doublet, or whose one line is
    an anode's Kα1 exactly as :meth:`~rietx.schemas.instrument.Instrument.
    bragg_brentano`'s ``radiation=`` writes it.  A synchrotron or neutron
    source is not one, and nor is a single line typed by hand (``1.5406``): it
    states no anode, so this answers ``False`` and nothing is said that the
    declaration does not support.
    """
    from ..schemas.instrument import _KA_DOUBLETS

    source = instrument.source
    if source.kind != "xray_cw":
        return False
    if len(source.lines) >= 2:
        return True
    kalpha1 = {pair[0] for pair in _KA_DOUBLETS.values()}
    return source.lines[0].wavelength.value in kalpha1


def undeclared_instrument(instrument: Instrument) -> dict[str, str]:
    """What the instrument a peak list was picked with still leaves at default,
    keyed by the block that holds it, on a laboratory source (:func:`lab_source`).

    The picker holds both and applies them (:func:`~rietx.indexing.pick_peaks`),
    so a default stands in for a measurement.  Axial divergence at S/L = H/L = 0
    leaves a lab line's low-angle asymmetry to the position, and the default
    ``ProfileTCHZ`` (W = 1e-3 deg²) is a synchrotron line, so the width seeds
    and the separation floor are a lab pattern's several times over.  Measured
    on one lab capillary pattern (WP-1510, ``solution case 1``): declaring both
    took median σ(Q)/Q from 1.05e-3 to 6.9e-4 and the gate passed.

    On any other source it is empty: a correctly declared synchrotron
    instrument has zero axial apertures and a narrow profile too, so the same
    two tests would name a correct declaration as missing (WP-2030).
    """
    out: dict[str, str] = {}
    if not lab_source(instrument):
        return out
    geo = instrument.geometry
    if not fcj_live(geo.axial_sl.value, geo.axial_hl.value):
        out["instrument.geometry"] = (
            "geometry.axial_sl and geometry.axial_hl are 0, so no axial "
            "divergence is modelled")
    default = ProfileTCHZ()
    if all(getattr(instrument.profile, k).value == getattr(default, k).value
           for k in "uvwxy"):
        out["instrument.profile"] = (
            "instrument.profile is the default ProfileTCHZ, a synchrotron line "
            f"(W = {default.w.value:g} deg²)")
    return out


def quality_diagnostics(report: DataQualityReport, peaks: PeakList,
                        instrument: Instrument | None = None,
                        ) -> list[Diagnostic]:
    """Translate a :class:`DataQualityReport` into the ``INDEX_*`` messages.

    Separate from :func:`peak_diagnostics` on purpose: a peak list's flags and a
    data-quality *verdict* are different statements about the same lines, and an
    agent that re-picks peaks in response to the first would be answering the
    wrong question for the second.  The peak-level messages are not repeated
    here — a caller that wants both calls both.
    """
    out: list[Diagnostic] = []
    where_range = [f"2θ {report.two_theta_min:.2f}-{report.two_theta_max:.2f}°"]

    if report.abstained_reason is not None:
        suggestion = ("Extend the 2θ range, count for longer or re-pick with "
                      "a lower PEAK_MIN_HEIGHT_SIGMA.")
        # the instrument is named first because it is the cheapest of the
        # remedies: a re-pick, where the others are a new measurement
        # only a fitted list was picked with an instrument; a position list
        # has no picker to re-run.  What the list recorded at its pick is the
        # instrument it was picked with, so it outranks one handed in beside
        # it; a list from before the record falls back to that one (WP-2030)
        if peaks.source != "fitted":
            missing = {}
        elif peaks.instrument_undeclared is not None:
            missing = dict(peaks.instrument_undeclared)
        else:
            missing = ({} if instrument is None
                       else undeclared_instrument(instrument))
        if missing:
            suggestion = ("Declare the instrument before re-picking, because "
                          "a default widens each position's esd: "
                          + "; ".join(missing.values()) + ". Otherwise "
                          + suggestion[0].lower() + suggestion[1:])
        out.append(Diagnostic(
            level="error", code="INDEX_DATA_INSUFFICIENT",
            message=report.abstained_reason,
            where=where_range + list(missing),
            suggestion=suggestion))
    elif report.fom_undefined:
        absent = "; ".join(f"{name}: {why}"
                           for name, why in sorted(report.fom_undefined.items()))
        out.append(Diagnostic(
            level="warning", code="INDEX_PANEL_REDUCED",
            message=(f"The list has {report.n_usable} usable lines, below the "
                     f"{PEAK_MIN_USABLE_LINES} that the classical figures of "
                     "merit are defined on. The search runs over "
                     f"{', '.join(report.systems_supported) or 'no system'} "
                     f"and the ranking panel omits: {absent}."),
            where=where_range,
            suggestion=("Read quality.fom_undefined for the reason each "
                        "figure is absent, or add lines to restore the full "
                        "panel.")))

    if np.isfinite(report.relative_sigma_q_median):
        level = ("warning" if report.relative_sigma_q_median
                 > 0.3 * MAX_RELATIVE_SIGMA_Q else "info")
        out.append(Diagnostic(
            level=level, code="PEAK_POSITION_PRECISION",
            message=(f"The median σ(2θ) is {report.sigma_two_theta_median:.4f}° "
                     f"and the worst is {report.sigma_two_theta_worst:.4f}°. "
                     f"The median σ(Q)/Q is {report.relative_sigma_q_median:.2e} "
                     f"and σ(Q) is {report.sigma_over_spacing:.3f} of the mean "
                     "line spacing."
                     + (" All σ values were assumed."
                        if report.source == "positions" else "")),
            where=where_range,
            suggestion=("Re-pick from the pattern with rietx.pick_peaks to "
                        "replace the assumed σ with a fitted one."
                        if report.source == "positions" else None)))

    shift = report.shift
    if shift is not None and shift.source == "measured" and shift.best:
        best = next(t for t in shift.templates if t.name == shift.best)
        if shift.separable:
            out.append(Diagnostic(
                level="warning", code="INDEX_SHIFT_DETECTED",
                message=(f"A systematic 2θ shift of {best.coefficient:+.4f}° "
                         f"± {best.stderr:.4f} follows the {shift.best} "
                         "template, the signature of "
                         f"{SHIFT_CAUSE.get(shift.best, shift.best)}. "
                         f"The runner-up leaves "
                         f"{shift.separability_ratio:.1f}× more unexplained."),
                where=where_range,
                suggestion=(f"Carry the {shift.best} template into the "
                            "candidate refinement and correct the matching "
                            "instrument parameter.")))
        else:
            out.append(Diagnostic(
                level="warning", code="INDEX_SHIFT_MODEL_AMBIGUOUS",
                message=(f"A shift is present ({shift.best} fits at "
                         f"{best.coefficient:+.4f}°), but the templates are "
                         "not separable over this range. The runner-up leaves "
                         f"only {shift.separability_ratio:.2f}× more "
                         "unexplained, the largest template collinearity is "
                         f"{shift.max_collinearity:.3f}, and the templates "
                         "that fit comparably disagree by up to "
                         f"{shift.prediction_spread_deg:.4f}° over the angles "
                         "sampled."),
                where=where_range,
                suggestion=("Extend the 2θ range to high angle, where cos θ "
                            "and sin 2θ separate from a constant. Carry "
                            f"{shift.prediction_spread_deg:.4f}° as a "
                            "systematic on every position, and correct no "
                            "instrument fault from these data.")))

    return out


# ----------------------------------------------------------------------
# The answer's diagnostics (WP-1024)
# ----------------------------------------------------------------------
#: Cell systematic a Bragg-Brentano geometry carries that no esd reports, in ppm.
#: Measured (tag ``guillemot-study``, ``audit_tools.py`` check A): sweeping
#: ``Geometry.goniometer_radius_mm`` over 180-320 mm moves Rwp by 0.029 points —
#: i.e. **the data cannot identify R** — while specimen displacement absorbs the
#: change 4.6× and ≈ ±85 ppm lands on the lattice parameters, larger than the
#: fit's own 1σ.  It bites hardest here of anywhere in the package, because
#: indexing *produces* a cell from lab data with nothing to compare it against.
BRAGG_BRENTANO_CELL_PPM = 85.0

#: Where a per-candidate statement belongs.  Statements about **one** candidate go
#: on that candidate (``CellCandidate.diagnostics``); statements about the
#: **result** — that it abstained, what it did not search, that nothing validated
#: it — go on the result.  Not duplicated: ``INDEX_ABSTAINED`` names the top
#: candidates' caveats, which is the pointer from one level to the other, and
#: duplicating the text would let the two copies disagree.
_PER_CANDIDATE_CODES = ("INDEX_GEOMETRIC_AMBIGUITY", "INDEX_BRAVAIS_AMBIGUOUS",
                        "INDEX_PREDICTED_BUT_ABSENT", "INDEX_IMPURITY_LINES",
                        "INDEX_VOLUME_UNPHYSICAL", "INDEX_SUPERCELL_REFUTED",
                        "INDEX_Z_NOT_INTEGER")

#: How far a cell may sit from a whole number of formula units, as a fraction of
#: its volume, before ``INDEX_Z_NOT_INTEGER`` fires (WP-1510).  Twice the 4.00 %
#: scatter of one crystal about Hofmann's (2002) estimate
#: (:data:`~rietx.crystallography.atomic_volume.VOLUME_SCATTER`).  That scatter
#: is the method's uncertainty for one crystal.  The table's mean errors, about
#: 0.5 % for an organic, describe the average and would flag correct cells.
#: Three consequences.  Above Z = 6.25 every volume lies within 8 % of some
#: whole number, so the check is silent there by arithmetic.  Z = 2.8 sits 6.7 %
#: from 3 and does not fire, while Z = 8/3, a third of a Z = 8 cell, sits 11 %
#: from 3 and does.  And a correct cell can fire, since only 6049 of the 9112
#: structures in Hofmann's sample 1 lie within 5 % of his estimate (Table 1).
#: So the code is a warning that reports the number, and never a caveat.
Z_INTEGER_TOLERANCE = 2.0 * VOLUME_SCATTER


def candidate_diagnostics(cand, *, formula: str | None = None,
                          temperature: float = 298.0) -> list[Diagnostic]:
    """Everything to say about **one** candidate cell.

    Attached to the candidate rather than to the result, so a caller reading the
    third-ranked cell sees why it is third — and so a twelve-candidate answer does
    not bury its own abstention under thirty-six messages.

    ``formula`` (with ``temperature`` in K) adds the chemistry's check: the
    number of formula units the cell's volume implies, reported as
    ``INDEX_Z_NOT_INTEGER`` when it is far from a whole number
    (:data:`Z_INTEGER_TOLERANCE`).
    """
    out: list[Diagnostic] = []
    where = [f"{cand.system} {cand.centring}, "
             f"V = {cand.volume:.1f} Å³, cell {_cell_str(cand.cell)}"]
    if formula is not None:
        z_check = _z_not_integer(cand, formula, temperature, where)
        if z_check is not None:
            out.append(z_check)

    if cand.ambiguity:
        tt = [t for p in cand.ambiguity for t in p.discriminating_two_theta]
        out.append(Diagnostic(
            level="warning", code="INDEX_GEOMETRIC_AMBIGUITY",
            message=(f"{len(cand.ambiguity)} distinct lattice(s) explain these "
                     "line positions as well as this one does."),
            where=where,
            suggestion=("Collect to the 2θ in each partner's "
                        "discriminating_two_theta and look for the reflections "
                        "it names"
                        + (f" (nearest: {min(tt):.2f}°)" if tt else "")
                        + ".")))

    if cand.bravais is not None and (cand.bravais.ambiguous
                                     or cand.bravais.methods_disagree):
        b = cand.bravais
        detail = []
        if b.ambiguous:
            detail.append(f"{b.system_loosest} appears only at a loose tolerance "
                          f"while {b.system} survives the whole sweep")
        if b.methods_disagree:
            detail.append(f"gemmi says {b.system_gemmi} and spglib says "
                          f"{b.system_spglib} at their tightest tolerances")
        out.append(Diagnostic(
            level="warning", code="INDEX_BRAVAIS_AMBIGUOUS",
            message="The lattice symmetry is not settled: " + "; ".join(detail) + ".",
            where=where,
            suggestion=("Refine in the lower symmetry and test the higher "
                        "one.")))

    lebail = cand.lebail
    if lebail is not None and lebail.predicted_but_absent:
        tt = lebail.predicted_but_absent_two_theta
        out.append(Diagnostic(
            level="warning", code="INDEX_PREDICTED_BUT_ABSENT",
            message=(f"{lebail.predicted_but_absent} of {lebail.n_reflections} "
                     "reflections this lattice predicts have no net intensity "
                     "above the fitted background."),
            where=where + ([f"first at {tt[0]:.3f}°"] if tt else []),
            suggestion=("Compare the smaller cell that indexes the same lines, "
                        "and read this count beside lebail.rwp. Rwp moves "
                        "little on an oversized cell (0.379 against 0.216 for "
                        "the correct one).")))

    refuting = [c for c in cand.supercell_checks or [] if c.verdict == "refuted"]
    if refuting:
        # the checks run in the parents' rank order and the candidate sits
        # below the lowest-ranked parent that refutes it, which is the last
        check = refuting[-1]
        chance = check.p0 * check.n_extra
        others = (f" {len(refuting) - 1} other candidate(s) refute it the same "
                  "way." if len(refuting) > 1 else "")
        out.append(Diagnostic(
            level="warning", code="INDEX_SUPERCELL_REFUTED",
            message=(f"This lattice is an index-{check.index} superlattice of "
                     f"the {check.parent_system} {check.parent_centring} "
                     f"candidate {_cell_str(check.parent_cell)} and ranks "
                     f"below it. Of the {check.n_extra} extra line(s) it "
                     f"predicts that no extinction could remove, "
                     f"{check.n_seen} sit on an observed line, against "
                     f"{chance:.1f} expected by chance (p = "
                     f"{check.p_value:.2g})." + others),
            where=where + ([f"first missing extra at {check.absent_two_theta[0]:.3f}°"]
                           if check.absent_two_theta else []),
            suggestion=("Read the smaller cell as the lattice. If the "
                        "chemistry suggests a superstructure, look at the "
                        "pattern at absent_two_theta before you discard "
                        "this cell.")))

    if lebail is not None and lebail.unmatched_observed:
        tt = lebail.unmatched_observed_two_theta
        out.append(Diagnostic(
            level="warning", code="INDEX_IMPURITY_LINES",
            message=(f"{lebail.unmatched_observed} observed peak(s) have no "
                     "calculated reflection nearby after a whole-pattern Le Bail "
                     "fit of this cell."),
            where=where + ([f"strongest region near {tt[0]:.3f}°" ] if tt else []),
            suggestion=("If a handful of lines remain, subtract the solved "
                        "phase and index the remainder. If most of the "
                        "pattern is unmatched, treat the cell as wrong.")))

    if "volume_unphysical" in cand.confidence_caveats:
        out.append(Diagnostic(
            level="warning", code="INDEX_VOLUME_UNPHYSICAL",
            message=(f"The cell volume {cand.volume:.1f} Å³ is below a single "
                     "atom's exclusion volume or clear of Smith's (1977) "
                     "envelope for the number of lines observed."),
            where=where,
            suggestion=("Narrow max_volume to the envelope assess_peak_list "
                        "supplied, or measure more lines.")))
    return out


def _z_not_integer(cand, formula: str, temperature: float,
                   where: list[str]) -> Diagnostic | None:
    """``INDEX_Z_NOT_INTEGER``: the cell holds a fractional number of formula
    units, by Hofmann's (2002) volumes.  ``value`` is the implied Z."""
    v_fu, _ = formula_unit_volume(formula, temperature)
    z = cand.volume / v_fu
    below = max(1, math.floor(z))
    # the whole number nearest in *ratio*, since the tolerance is a fraction of
    # the volume
    n = min((below, below + 1), key=lambda k: abs(z / k - 1.0))
    off = z / n - 1.0
    if abs(off) <= Z_INTEGER_TOLERANCE:
        return None
    return Diagnostic(
        level="warning", code="INDEX_Z_NOT_INTEGER", value=z,
        message=(f"This cell holds {z:.2f} formula units of {formula} "
                 f"({cand.volume:.1f} Å³ over {v_fu:.1f} Å³ per unit at "
                 f"{temperature:g} K, Hofmann 2002). The nearest whole number, "
                 f"{n}, needs a formula unit {abs(off) * 100:.0f} % "
                 f"{'larger' if off > 0 else 'smaller'} than the estimate, "
                 f"past the {Z_INTEGER_TOLERANCE * 100:.0f} % tolerance."),
        where=where + [f"formula {formula}"],
        suggestion=("Check the formula for a missing solvent or counter-ion, "
                    "then weigh this beside the figures of merit."))


def index_diagnostics(result, instrument=None) -> list[Diagnostic]:
    """Result-level ``INDEX_*`` messages: abstention, coverage, validation.

    Separate from :func:`candidate_diagnostics` on the rule stated at
    :data:`_PER_CANDIDATE_CODES`, and separate from the engines' own diagnostics
    (which arrive already built on :attr:`IndexingResult.diagnostics`) for the same
    reason :func:`quality_diagnostics` is separate from :func:`peak_diagnostics`:
    "the search did not finish" and "the answer does not qualify" are different
    statements, and an agent acting on one would be answering the wrong question
    for the other.
    """
    from ..schemas.indexing import Confidence  # noqa: F401  (documented vocabulary)
    from .engines import SYSTEM_ORDER

    out: list[Diagnostic] = []
    high = [c for c in result.candidates if c.confidence == "high"]

    if len(high) > 1:
        out.append(Diagnostic(
            level="warning", code="INDEX_MULTIPLE_SOLUTIONS",
            message=(f"{len(high)} candidate lattices each satisfy the whole "
                     "confidence gate, so best_or_none() returns None."),
            where=[f"{c.system} {c.centring}, V = {c.volume:.1f} Å³"
                   for c in high],
            suggestion=("Compare their figure-of-merit panels and their "
                        "lebail.rwp, and extend the 2θ range to reach a "
                        "high-angle reflection that separates them.")))

    if result.best_or_none() is None:
        top = result.candidates[0] if result.candidates else None
        caveats = ", ".join(top.confidence_caveats) if top else "no candidates"
        out.append(Diagnostic(
            level="warning" if result.candidates else "error",
            code="INDEX_ABSTAINED",
            message=(("No cell reached the confidence gate. The best candidate "
                      f"({top.system} {top.centring}, V = {top.volume:.1f} Å³) "
                      f"has {top.confidence} confidence because of: {caveats}.")
                     if top else
                     "No candidate cell was found in the systems searched."),
            where=[f"searched: {', '.join(result.systems_searched) or 'nothing'}"],
            suggestion=(("Read each candidate's confidence_caveats and act on "
                         "the refuting ones first (geometric_ambiguity, "
                         "predicted_but_absent, fom_panel_disagrees, "
                         "indexed_fraction_low, volume_unphysical, "
                         "validation_failed, supercell_refuted). The others "
                         "cap confidence, and better data closes most of them.")
                        if top else
                        "Read search_complete before you treat the absence as "
                        "evidence.")))

    if not result.validated:
        out.append(Diagnostic(
            level="warning", code="INDEX_NOT_VALIDATED",
            message=("No pattern was supplied, so no candidate was tested "
                     "against the whole profile."),
            where=[f"{len(result.candidates)} candidate(s) from a peak list only"],
            suggestion="Pass data= and instrument= to index_pattern."))

    missing = [s for s in SYSTEM_ORDER if s not in result.systems_searched]
    if missing:
        out.append(Diagnostic(
            level="info", code="INDEX_SYSTEMS_NOT_COVERED",
            message=f"{len(missing)} crystal system(s) were not searched.",
            where=missing,
            suggestion=("Search the missing systems before you conclude "
                        "anything about the specimen.")))

    systematic = _cell_systematic(instrument, bool(result.candidates))
    if systematic is not None:
        out.append(systematic)
    return out


def _cell_systematic(instrument, have_candidates: bool) -> Diagnostic | None:
    """``INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`` — the cell's esd is not its accuracy.

    **The trigger the plan named is unreachable, and the reachable one is
    stronger.**  WP-1024 asked for this to fire "on Bragg-Brentano data when no
    radius was supplied"; ``Geometry._bb_needs_radius`` *raises* on exactly that,
    so no such instrument exists.  The real gap is that a **declared** radius is
    not identifiable from the data either — Rwp moves 0.029 points across
    180-320 mm — so the systematic is present whatever the caller declared, and it
    is unquantified because the fit cannot measure it.
    """
    if not have_candidates:
        return None
    if instrument is None:
        return Diagnostic(
            level="info", code="INDEX_CELL_SYSTEMATIC_UNQUANTIFIED",
            message=("No instrument was supplied, so the geometry that sets "
                     "the cell's systematic error is unknown. The reported "
                     "cell_esd is a precision from the line positions and says "
                     "nothing about accuracy."),
            where=["geometry unknown"],
            suggestion=("Pass instrument= to index_pattern. On a "
                        "Bragg-Brentano diffractometer the goniometer radius "
                        f"alone carries about ±{BRAGG_BRENTANO_CELL_PPM:.0f} "
                        "ppm onto the cell."))
    if instrument.geometry.kind != "bragg_brentano":
        return None
    return Diagnostic(
        level="info", code="INDEX_CELL_SYSTEMATIC_UNQUANTIFIED",
        message=(f"A Bragg-Brentano cell carries about ±{BRAGG_BRENTANO_CELL_PPM:.0f} "
                 "ppm that no esd reports. Sweeping the goniometer radius over "
                 "180-320 mm moves Rwp by only 0.029 points, and specimen "
                 "displacement absorbs the change 4.6×."),
        where=[f"R = {instrument.geometry.goniometer_radius_mm:g} mm (declared, "
               "not measured by the fit)"],
        suggestion=("Quote the cell to no better than this level, or calibrate "
                    "against a certified standard (lab_calibrate with the "
                    "certified cell held fixed) and carry the correction."))


# ----------------------------------------------------------------------
# WP-1025 — the extinction screen
# ----------------------------------------------------------------------
def extinction_class_diagnostics(cand) -> list[Diagnostic]:
    """Everything to say about **one** extinction class.

    Same split as :data:`_PER_CANDIDATE_CODES` one level up: a refutation belongs
    to the class it refutes, while "your answer is not one space group" is a
    statement about the answer and lives on the screen.
    """
    out: list[Diagnostic] = []
    where = [f"{cand.symbol} (fitted as {cand.representative})"]
    if cand.refuted and cand.forbidden_hkl:
        pairs = ", ".join(f"{tuple(h)} at {t:.3f}°" for h, t in
                          zip(cand.forbidden_hkl[:4],
                              cand.forbidden_two_theta[:4]))
        out.append(Diagnostic(
            level="warning", code="EXTINCTION_FORBIDDEN_INTENSITY",
            message=(f"{cand.n_present} of the {cand.n_testable} forbidden "
                     "position(s) this class could be tested at carry intensity "
                     "its own Le Bail fit cannot account for."),
            where=where + [pairs],
            suggestion=("Check those 2θ positions against IndexingResult's "
                        "unmatched_observed for an impurity line before you "
                        "drop the class. Declare an excess about a degree wide "
                        "as a HumpComponent in the Le Bail pre-fit.")))
    if cand.n_absent and cand.n_testable == 0:
        out.append(Diagnostic(
            level="info", code="EXTINCTION_SYMBOL_AMBIGUOUS",
            message=(f"None of the {cand.n_absent} line(s) this class forbids "
                     "can be tested by these data: each lies outside the "
                     "fitted range, coincides with a line the class still "
                     "allows, or sits in a neighbour's tail."),
            where=where,
            suggestion=("Extend the range or resolve the overlap to separate "
                        "this class from a less restrictive one. The nested "
                        "comparison counts only testable lines, so an absence "
                        "nobody could see earns this class no preference.")))
    if not cand.conditions_complete:
        out.append(Diagnostic(
            level="info", code="EXTINCTION_CONDITIONS_PARTIAL",
            message=("The reflection conditions printed for this class do not "
                     "name every absence in it."),
            where=where + [f"conditions: {'; '.join(cand.conditions) or 'none'}"],
            suggestion="Use space_groups as the reliable statement."))
    return out


def extinction_diagnostics(screen) -> list[Diagnostic]:
    """Screen-level messages: what the answer is, and why it may not be one.

    ``EXTINCTION_GROUPS_NOT_SEPARABLE`` fires whenever the leading class holds
    more than one space group — **always**, not only when the data are weak.
    That is a statement about the physics: those groups differ by symmetry
    elements a powder pattern cannot carry, so no amount of counting time
    separates them, and a caller who needs one of them is using chemistry, not
    these data.
    """
    from ..schemas.indexing import ExtinctionScreen  # noqa: F401  (documented)
    from .extinction import DECISIVE_DELTA_BIC

    out: list[Diagnostic] = []
    alive = [c for c in screen.candidates if not c.refuted and c.screened]
    # the classes a declared prior leaves a member in; every class without one
    admissible = [c for c in alive if c.space_groups]
    unscreened = [c for c in screen.candidates if not c.refuted and not c.screened]
    if not screen.candidates:
        return [Diagnostic(
            level="warning", code="EXTINCTION_SYMBOL_AMBIGUOUS",
            message=("No extinction class could be screened: the lattice "
                     f"{screen.lattice_group} produced no fittable reflections in "
                     f"{screen.two_theta_range[0]:.1f}-"
                     f"{screen.two_theta_range[1]:.1f}° 2θ."),
            where=[f"{screen.system} {screen.centring}"],
            suggestion="Check the cell and the wavelength.")]

    top = (admissible[0] if admissible
           else alive[0] if alive else screen.candidates[0])
    if screen.prior is not None:
        out.append(_prior_diagnostic(screen, alive, top))
    if len(top.laue_classes) > 1:
        out.append(Diagnostic(
            level="info", code="LAUE_CLASS_NOT_SEPARABLE",
            message=(f"the groups {top.symbol} admits fall in "
                     f"{len(top.laue_classes)} Laue classes, which share every "
                     "position and absence and differ only in which reflections "
                     "are equivalent — the intensity partition inside overlapped "
                     "multiplets, which a powder pattern does not expose"),
            where=[f"{laue}: {', '.join(groups)}"
                   for laue, groups in top.laue_classes.items()],
            suggestion=("carry one structure solution per Laue class, not one "
                        "per group: the members of one Laue class differ only "
                        "in elements a solution can try cheaply, the Laue "
                        "classes in which intensities are equivalent")))
    if len(top.space_groups) > 1:
        out.append(Diagnostic(
            level="info", code="EXTINCTION_GROUPS_NOT_SEPARABLE",
            message=(f"Extinction symbol {top.symbol} is compatible with "
                     f"{len(top.space_groups)} space groups."),
            where=[", ".join(top.space_groups)],
            suggestion=("Choose between them with chemistry (an optically "
                        "active or polar compound cannot be centrosymmetric) "
                        "or a structure solution. Pass any of them to "
                        "structure_from_candidate for the next fit.")))

    reasons = []
    rivals = admissible if admissible else alive
    contradicting = [c for c in alive if not c.space_groups
                     and top.delta_bic - c.delta_bic >= DECISIVE_DELTA_BIC]
    if len(rivals) > 1 and rivals[1].delta_bic - top.delta_bic < DECISIVE_DELTA_BIC:
        reasons.append(f"{rivals[1].symbol} is within ΔBIC "
                       f"{rivals[1].delta_bic - top.delta_bic:.1f} of it "
                       f"(decisive is {DECISIVE_DELTA_BIC:g})")
    if contradicting:
        reasons.append(f"the data prefer {contradicting[0].symbol}, which the "
                       "declared prior excludes, by ΔBIC "
                       f"{top.delta_bic - contradicting[0].delta_bic:.1f}")
    if alive and not admissible:
        reasons.append("the declared prior leaves no member in any surviving "
                       "class")
    if top.n_absent and top.n_testable == 0:
        reasons.append("none of its absences is testable in this range")
    if unscreened:
        reasons.append(f"{len(unscreened)} class(es) were never fitted, so their "
                       "standing is unknown")
    if not alive:
        reasons.append("every class was refuted, including the absence-free "
                       "lattice, so the fit itself failed")
    if reasons:
        out.append(Diagnostic(
            level="warning", code="EXTINCTION_SYMBOL_AMBIGUOUS",
            message=("The extinction symbol is not settled by these data: "
                     + "; ".join(reasons) + "."),
            where=[f"leading: {top.symbol}"]
            + [f"then: {c.symbol} (ΔBIC {c.delta_bic:+.1f})"
               for c in rivals[1:3]]
            + [f"excluded by the prior: {c.symbol} (ΔBIC {c.delta_bic:+.1f})"
               for c in contradicting[:2]],
            suggestion=("Count longer at the forbidden positions where the "
                        "leading classes disagree, or extend the 2θ range.")))
    return out


def _prior_diagnostic(screen, alive, top) -> Diagnostic:
    """``EXTINCTION_PRIOR_APPLIED``: what the declared facts removed, by class.

    ``info`` when the declaration only narrowed the classes the data rank;
    ``warning`` when it emptied the class the data rank first, since that is
    either the declaration doing work the data could not, or the data
    contradicting it — and the reader must see which before acting.
    """
    declared = ", ".join(f"{k}={v}" for k, v in screen.prior.declared().items())
    removed = [c for c in screen.candidates if c.excluded_groups]
    emptied = [c.symbol for c in removed if not c.space_groups]
    first_emptied = bool(alive) and not alive[0].space_groups
    n_removed = sum(len(c.excluded_groups) for c in removed)
    message = (f"the declared prior ({declared}) removed {n_removed} space "
               f"group(s) from {len(removed)} class(es)")
    if emptied:
        message += f", emptying {', '.join(emptied)}"
    if first_emptied and top.space_groups:
        message += (f"; the data's leading class {alive[0].symbol} is among "
                    f"them, so the answer is read from {top.symbol}, the "
                    "first class the declaration admits")
    elif first_emptied:
        message += (f"; the data's leading class {alive[0].symbol} is among "
                    "them and the declaration admits no member of any "
                    "surviving class, so there is no admissible answer")
    return Diagnostic(
        level="warning" if first_emptied else "info",
        code="EXTINCTION_PRIOR_APPLIED",
        message=message + ".  A filter on the members, never evidence: no ΔBIC "
                          "moved and every class was fitted",
        where=[f"{c.symbol}: excluded {', '.join(c.excluded_groups)}"
               for c in removed],
        suggestion=("check the declaration before the answer: a class it "
                    "emptied that leads on the data is either chemistry doing "
                    "what a powder cannot, or a wrong declaration (a racemate "
                    "declared enantiopure, a polar sample measured as a "
                    "centrosymmetric twin).  best_or_none() abstains when the "
                    "data prefer an excluded class by the decisive margin"))


def _cell_str(cell) -> str:
    a, b, c, al, be, ga = cell
    return (f"{a:.4f} {b:.4f} {c:.4f} Å, {al:.3f} {be:.3f} {ga:.3f}°")


def significant(values: np.ndarray, threshold: float) -> np.ndarray:
    """``|values| >= threshold`` with non-finite entries counted as False.

    A NaN t-statistic means the projection had no norm (a zero-width or
    all-masked window), which is "not measured", not "significant".
    """
    v = np.asarray(values, dtype=np.float64)
    return np.isfinite(v) & (np.abs(v) >= threshold)


__all__ = ["BRAGG_BRENTANO_CELL_PPM", "SHIFT_CAUSE", "WIDTH_MISMATCH_RATIO",
           "Z_INTEGER_TOLERANCE", "candidate_diagnostics", "extinction_class_diagnostics",
           "extinction_diagnostics", "index_diagnostics", "peak_diagnostics",
           "quality_diagnostics", "significant"]
