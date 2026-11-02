"""What a time-of-flight bank's fit reports, and what did not run on one.

The diagnostics only a ``neutron_tof`` histogram raises, kept beside each
other because they answer one question — what a reader of a bank's result
must know that the numbers do not say — and because the manual files a code
by the module that raises it (``docs/reference_pages.DIAGNOSTIC_GROUPS``), so
a bank's codes have one page of their own rather than a corner of the
refinement page.  Two kinds:

* **What the flight-time model applied.**  Specimen absorption evaluated per
  reflection along the bank (``SPECIMEN_ABSORPTION_TOF``, with the
  ``ABSORPTION_MU_R_OUT_OF_RANGE`` warning past the Rouse domain), and GSAS's
  channel width W(T) — applied (``TOF_CHANNEL_WIDTH_APPLIED``) or, where
  nothing declared the intensity basis, assumed away
  (``TOF_INTENSITY_BASIS_ASSUMED``).
* **"Did not run here" lines.**  :func:`_tof_skip` builds the info-level
  statement that a constant-wavelength check abstained on a bank, so an unrun
  check never reads as a clean one; ``BACKGROUND_PEAK_WIDTH_UNAVAILABLE`` is
  raised here, and ``refine._capillary_offset_diagnostics`` calls the same
  builder for its own code.

Called from ``refine._build_result``; ``refine._is_tof`` stays the one test of
which arm a compiled model is, imported where it is used because ``refine``
imports this module.
"""

from __future__ import annotations

from ..model.absorption import CYLINDER_MU_R_MAX
from ..schemas.common import Diagnostic
from ..schemas.pattern import TOF_NOT_EVALUATED


def _tof_skip(code: str, what: str, why: str,
              where: list[str] | None = None) -> Diagnostic:
    """One "this did not run, and here is why" diagnostic, at info level.

    Info rather than warning: nothing is wrong with the fit — a bank simply has
    no 2θ aberration to attribute, no scalar wavelength to build a Scherrer
    size from, and no per-reflection profile partition yet.  Saying so is the
    point.  A silent ``return []`` here would be indistinguishable from the
    check running and passing, which is the failure mode
    ``CAPILLARY_OFFSET_UNAVAILABLE`` exists to prevent one arm over: a held
    aberration reads as a measured zero, and an unrun check reads as a clean
    one.
    """
    return Diagnostic(
        level="info", code=code, where=list(where or []),
        message=f"{what} is {TOF_NOT_EVALUATED}: {why}",
        suggestion=("the flight-time arm's own diagnostics are the ones to "
                    "read — Rwp, chi-squared, the per-stage records and the "
                    "refined calibration; this line says the check did not run "
                    "rather than that it ran and found nothing"))


def _tof_background_peak_diagnostics(model) -> list[Diagnostic]:
    """The hump-width guard, and that it did not run on a bank.

    ``strategy.staged.check_hump_width`` compares a declared hump's FWHM
    against the *instrument* resolution at its position, and both halves are
    deg 2θ on this package's constant-wavelength arm.  A bank has no Caglioti
    term to evaluate and its hump is in microseconds, so the guard abstains
    there — and an abstention nobody reports is indistinguishable from a guard
    that ran and found nothing, which is the whole reason :func:`_tof_skip`
    exists.

    Silent unless there is something to say: no declared hump, or a
    constant-wavelength histogram, where the guard did run.
    """
    from ..refine import _is_tof  # refine imports this module

    if not _is_tof(model) or not getattr(model, "component_paths", ()):
        return []
    return [_tof_skip(
        "BACKGROUND_PEAK_WIDTH_UNAVAILABLE",
        "the hump-width guard",
        "it asks whether a declared hump is narrower than a real reflection "
        "can be at its position, and the resolution it compares against is the "
        "Caglioti FWHM in deg 2θ; this bank's resolution is "
        "instrument.source.profile_tof's sigma(d) and gamma(d) and its hump is "
        "in microseconds, so the two have no common unit",
        [paths[2] for paths in model.component_paths])]


def _tof_absorption_diagnostics(model) -> list[Diagnostic]:
    """What the flight-time specimen absorption did, and over what µR range.

    ``refine._absorption_record`` returns ``None`` on this arm and always will:
    :class:`~rietx.schemas.results.AbsorptionCorrection` carries **one** µR and
    **one** wavelength, and a bank has neither.  Without these two lines the
    correction would be applied and the result would say nothing at all about
    it, which is the one outcome worse than not applying it.

    Two diagnostics, and the split matters.  The info line always fires when
    the correction ran, because a µR of 0.02 is worth knowing about too — it is
    the evidence that the number was *computed* rather than defaulted.  The
    warning fires only past the Rouse domain, at the same threshold and with
    the same code the constant-wavelength path uses, so a reader who knows one
    knows the other.  What is new is the *pair*: µ rises with λ, so a specimen
    can sit inside the domain at the short-wavelength end of a bank and outside
    it at the long one, and only two numbers can say so.
    """
    span = getattr(model, "mu_r_range", None)
    if span is None:
        return []
    lo, hi = span
    where = ["instrument.geometry.capillary_radius_mm"]
    out = [Diagnostic(
        level="info", code="SPECIMEN_ABSORPTION_TOF", where=where,
        message=(f"specimen absorption was applied per reflection at its own "
                 f"wavelength: µR runs {lo:.3f} to {hi:.3f} across the fitted "
                 f"window, computed from the refined composition and the "
                 f"declared capillary radius (mu = sum n_i [sigma_abs_i "
                 f"lambda/1.798 + sigma_coh_i + sigma_inc_i]/V, Sears 1992). "
                 f"It is not a refinable parameter here and must not become "
                 f"one — GSAS's own warning is that the correction is "
                 f"indistinguishable from thermal motion"),
        suggestion=("nothing to do; quote a displacement parameter from this "
                    "fit knowing the correction was in the model, and check "
                    "geometry.capillary_radius_mm and packing_fraction against "
                    "the specimen if it matters at this size"))]
    if hi > CYLINDER_MU_R_MAX:
        out.append(Diagnostic(
            level="warning", code="ABSORPTION_MU_R_OUT_OF_RANGE", where=where,
            message=(f"µR reaches {hi:.2f} at the long-wavelength end of this "
                     f"bank, outside the Rouse et al. (1970) fit's range "
                     f"(µR <= {CYLINDER_MU_R_MAX:g}); the transmission factor "
                     f"is an extrapolation there. On a flight-time bank this "
                     f"can be true at one end and false at the other — µ "
                     f"follows the 1/v law, and here it is {lo:.2f} at the "
                     f"short-wavelength end"),
            suggestion=("dilute the specimen or use a narrower capillary; "
                        "shortening the fitted window at the long-flight-time "
                        "end also brings the correction back inside its "
                        "domain, at the cost of the reflections there")))
    return out


def _tof_intensity_basis_diagnostics(model) -> list[Diagnostic]:
    """What the flight-time model did about GSAS's channel width W.

    Three states and three different things to say, which is why this is a
    function and not a boolean:

    * ``"counts"`` — the calculated Bragg sum was multiplied by W, measured
      from the pattern's own abscissa.  An **info** line, and it always fires,
      for :func:`_tof_absorption_diagnostics`'s reason: nothing else in the
      result would say that a factor with a shape in flight time was in the
      model, and the number it moves most is a displacement parameter.
    * ``"density"`` — the caller declared the histogram already divided, so
      nothing was applied.  Silent: a declared state that produced the
      declared behaviour is not news.
    * ``None`` — nothing established it, and the model **proceeded as a
      density**.  A warning, and it names the field and both values, because
      the only thing wrong with this state is that nobody has said which of
      two answers is right.
    """
    basis = getattr(model, "intensity_basis", "density")
    if basis == "density":
        return []
    where = ["intensity_basis"]
    if basis == "counts":
        w = model.channel_width_factor()
        lo, hi = (float(w[0]), float(w[-1])) if w is not None else (0.0, 0.0)
        return [Diagnostic(
            level="info", code="TOF_CHANNEL_WIDTH_APPLIED", where=where,
            message=(f"this histogram declares intensity_basis='counts', so "
                     f"the calculated Bragg sum was multiplied by the channel "
                     f"width W(T) — GSAS's I_o = I'_o/(W·I_i) (LAUR 86-748, "
                     f"Technical Manual p. 127). W was measured from the "
                     f"pattern's own abscissa and runs {lo:.3f} to {hi:.3f} µs "
                     f"across the fitted window, a factor of "
                     f"{(hi / lo if lo > 0 else float('nan')):.2f}. It is a "
                     f"slope in flight time and not a scale, so leaving it out "
                     f"would have been paid for by the displacement "
                     f"parameters rather than by the phase scale"),
            suggestion=("nothing to do; if this bank's export already divided "
                        "by the bin width, say so with "
                        "intensity_basis='density' — applying W twice biases "
                        "Biso the other way by the same amount"))]
    return [Diagnostic(
        level="warning", code="TOF_INTENSITY_BASIS_ASSUMED", where=where,
        message=("nothing established whether one channel of this histogram "
                 "holds the counts it recorded or those counts already divided "
                 "by the channel width, so pattern.intensity_basis is None and "
                 "this fit proceeded as 'density' — no channel-width factor, "
                 "which is what every flight-time fit before this option did. "
                 "If the histogram is in counts (Mantid's SaveGSS multiplies Y "
                 "by the bin widths by default), the missing factor of W(T) is "
                 "a smooth rise across the bank and a refined Biso is what "
                 "absorbs it, with a worse Rwp beside it"),
        suggestion=("set pattern.intensity_basis to 'counts' or 'density' from "
                    "how the bank was reduced. The readers set it themselves "
                    "where the file declares it — a GSAS STD/ESD layout or "
                    "TIME_MAP bintype, a SaveGSS header stating the bin-width "
                    "multiplication, or a stated .xye Y-axis unit"))]
