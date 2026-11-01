"""Acceptance: a refined wavelength on 11-BM Si SRM 640c, against XND.

The flagship validation of the single-histogram refinable wavelength (WP-1128
made it admissible when the cell is held, WP-1134 gave it the
``WAVELENGTH_CALIBRATION`` record).  The specimen is **NIST SRM 640c silicon**,
whose certified lattice parameter is the internal standard that licenses freeing
λ at all: a powder pattern measures d = λ/(2 sin θ), so λ and the cell are an
exactly flat direction — hold one and the other becomes a measurement.  Holding
a *certified* cell turns a refined λ into a measurement of the monochromator's
calibration error, which is the whole point.

**The data.**  ``11BM_Si640c.xy`` — APS 11-BM, run 4918, collected 25 Feb 2010
(the beamline's provided standard scan; header ``11bmb_4918.mda``, calibration
file ``11bmb_4917.calib``).  48 000 points, 1.996–49.995° 2θ at 0.001°, three
columns (2θ, I, propagated σ).  The σ column is real: 11-BM sums twelve analyser
crystals, so column 3 is not √I (median σ/√I = 0.9675 over the range), and
``read_pattern`` uses it.  The header states ``Calibrated wavelength =
0.412359`` — that is the number this suite refines *away from*.

**Two references, and they answer different questions.**

* **Certificate (NIST SRM 640c).**  a = 5.4311946 ± 0.0000092 Å at 22.5 °C
  (the certificate's stated uncertainty).  This is **held**, not measured — it
  is the anchor of the protocol, asserted as an identity
  (:func:`test_the_held_cell_is_the_certificate`).  The certificate's median
  laser-scattering particle size (4.9 µm) is of **agglomerates** and is *not*
  used for broadening.  Its Information Values from NIST's own
  fundamental-parameters analysis are a Lorentzian sample-broadening FWHM
  (°2θ) = 0.0065(5)/cos θ + 0.0086(6)·tan θ — a ~1.4 µm crystallite size and a
  microstrain term ~0.02° on (533).  Those map unit-for-unit onto rietx's
  ``lor_size`` (the 1/cos θ coefficient) and ``lor_strain`` (the tan θ one), but
  **no equality is asserted** (:func:`test_the_sample_broadening_is_positive_
  and_finite`): NIST's split is FPA-based and taken at its **Cu Kα** instrument,
  not at 11-BM, so any coefficient comparison is convention- and
  instrument-dependent.

* **Cross-code (XND 1.42, Bérar & Baldinozzi).**  The same ``.xy`` was refined
  in XND — the files ship beside the data on the owner's archive.  XND is the
  same Bérar as the Bérar–Lelann esd inflation rietx implements, so the esds are
  comparable.  XND's converged fit (``Si640c.new``/``.lst``), cell **held** at
  5.4311948 Å, refined:

  =====================  ====================================
  λ                      0.412376076 ± 0.000000379 Å  (+41.4 ppm)
  zero                   −0.00048302 ± 0.00001424 °
  Biso(Si)               0.438984 ± 0.001711 Å²
  scale                  0.000295467(252)
  Rwp / Rp / GoF         0.0961 / 0.0691 / 1.49  (Rexp 0.065)
  observations / params  47 980 / 19
  background             11 point-wise values, interpolated
  asymmetry              A_T2 = 0.039595  (odd-power tan expansion)
  =====================  ====================================

  XND's printed correlations above 0.6: λ~zero −0.897, zero~asym +0.941,
  λ~asym −0.738, scale~Biso +0.691 — high but not 1, so its λ is determined.

**What rietx does differently, stated rather than hidden.**  Two things, and
each is declared where the cross-code tier requires it: the background is a
co-refined penalized **P-spline** (rietx's own smooth background, physically
unable to absorb Bragg intensity) rather than XND's eleven interpolated points,
and the low-angle asymmetry is **Finger–Cox–Jephcoat axial divergence**
(``axial_sl``/``axial_hl``, tied equal) rather than XND's empirical A_T2.  The
first was measured not to matter (background choice moves the refined λ by
< 0.1 ppm — Si is far above its K edge, so dispersion does not enter either).
**The second is the whole story of the headline.**

**The headline, honestly.**  The refined λ is a point on the λ~zero ridge, and
*which* point is pinned by the low-angle peak-position model — where the two
codes' asymmetry conventions differ.  Measured here (2026-08-25, held cell,
single phase Fd-3m):

============================  =========  ==========  ============  ==========
protocol                      Rwp        GoF         λ vs nominal  λ vs XND
============================  =========  ==========  ============  ==========
full range 2–50°, FCJ         0.0826     1.36        +30.4 ppm     −11.0 ppm
symmetric window ≥ 8°, no FCJ 0.0736     1.17        +41.0 ppm     −0.4 ppm
============================  =========  ==========  ============  ==========

The full-range fit adopts XND's own range and reports λ +30 ppm, 11 ppm short of
XND — and that 11 ppm **is** the FCJ-vs-A_T2 convention: the two models disagree
on the low-angle centroids, and λ trades the difference against zero.  Remove the
region where they disagree — the symmetric ≥ 8° peaks — and the disagreement
collapses to −0.4 ppm (:func:`test_the_symmetric_window_recovers_xnd_to_sub_ppm`).
So the sub-ppm agreement lives where the two codes model the same physics, and
the residual is named rather than tuned away.  Either way the refined λ moves
+30 to +41 ppm off the beamline's stated 0.412359 at many σ — the calibration
error is detected, which is the feature working.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import (
    HUMP_FWHM_MIN,
    BackgroundChebyshev,
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    HumpComponent,
)
from rietx.schemas.structure import Atom, Cell, Phase, Structure

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
PATTERN = DATA / "11BM_Si640c.xy"
#: The same capillary with the specimen taken out: 11-BM run 4736, 11 Feb 2010,
#: the container this pattern's low-angle hump belongs to.  Provenance and the
#: out-of-package fit that identifies it: `tests/data/README.md`.
BLANK = DATA / "11BM_Kapton.xy"

#: The header's ``Calibrated wavelength`` — the value λ is seeded at and refines
#: away from.  The whole measurement is how far this was wrong for this scan.
LAM_NOMINAL = 0.412359
#: NIST SRM 640c certificate: a = 5.4311946 ± 0.0000092 Å at 22.5 °C.  **HELD** —
#: this is what makes a refined λ a calibration measurement rather than half of a
#: flat direction.
A_CERT = 5.4311946
A_CERT_SD = 0.0000092

#: XND 1.42's converged values on this exact ``.xy`` (``Si640c.lst``), cell held
#: at 5.4311948 Å — 0.4 ppm above the certificate this suite holds, negligible
#: against every band below and stated so it is not a silent gap.
XND = {
    "lam": 0.412376076, "lam_sd": 0.000000379,   # +41.4 ppm off nominal
    "zero": -0.00048302, "zero_sd": 0.00001424,
    "biso": 0.438984, "biso_sd": 0.001711,
    "rwp": 0.0961, "rexp": 0.065, "gof": 1.49,
    "rho_lam_zero": -0.897,                        # its top λ correlation
}
XND_PPM = 1e6 * (XND["lam"] - LAM_NOMINAL) / LAM_NOMINAL   # +41.4

#: XND fitted 47 999 channels (1.997–49.995°); rietx matches that grid.
FULL_LIMITS = (1.997, 49.996)
#: The symmetric window drops the low-angle peaks whose asymmetry the two codes
#: model differently — below the (111) at 7.54°.  This is *not* XND's range, and
#: that is the point of the row that uses it.
SYMMETRIC_LIMITS = (8.0, 49.996)

#: rietx's HIGH_CORRELATION guard default; XND's λ~zero of −0.897 sits below it.
CORRELATION_GUARD = 0.98

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("si640c")]


def _structure() -> Structure:
    """Silicon, Fd-3m:2, Si on 8a (⅛,⅛,⅛) — a special position with **no free
    coordinate**, so the whole structural content of the fit is one Biso."""
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2",
        cell=Cell(a=P(value=A_CERT), b=P(value=A_CERT), c=P(value=A_CERT),
                  alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        scale=P(value=3e-4, min=0.0, transform="softplus"),
        atoms=[Atom(label="Si", species="Si",
                    x=P(value=0.125), y=P(value=0.125), z=P(value=0.125),
                    biso=P(value=0.44, min=0.0, max=3.0))])])


def _instrument(limits: tuple[float, float]) -> rx.Instrument:
    """11-BM as a Debye-Scherrer capillary, seeded sharp (FWHM ~0.005° at low θ).

    The Gaussian Caglioti terms carry the (near-resolution-limited) instrument
    profile; the phase's ``lor_size``/``lor_strain`` carry the specimen's
    Lorentzian broadening, which is the physical split and the one the SRM 640c
    Information Values are quoted in.  ``profile.x`` (instrument ``lor_size``) is
    left at zero so the Lorentzian belongs to the sample.
    """
    ins = rx.Instrument.debye_scherrer(wavelength=LAM_NOMINAL)
    ins.profile.u.value = 1.1e-4
    ins.profile.v.value = -1.3e-5
    ins.profile.w.value = 6.0e-6
    ins.profile.x.value = 0.0
    # Declared, not inherited (tests/test_validation_matrix.py): dispersion is
    # OFF.  Si's K edge is 1.84 keV and this is 30 keV, so f'/f" is inert here —
    # measured to move the refined λ by < 0.1 ppm — and the one claim this suite
    # makes is about a wavelength, so the correction that is a function of λ is
    # named rather than left to a moving default.
    ins.source.dispersion = None
    ins.background = BackgroundPSpline.for_range(
        limits[0], limits[1], knot_step_deg=4.0)
    # Declared, not inherited, for the same reason: every number this suite
    # quotes was measured with λ in intensity units, the only kind there was
    # before WP-1454 (λ·σ̄²/m ≈ 0.03 in the new units at this count level).
    ins.background.lambda_units = "intensity"
    return ins


def _plan(*, asymmetric: bool) -> rx.RefinementPlan:
    """Cell **held** throughout (never freed — that is what licenses free λ).

    The order mirrors a hand refinement: scale+background, then the Gaussian
    resolution, then the sample Lorentzian, (then FCJ asymmetry), then zero, then
    λ and Biso together because λ trades against both zero and the intensity.
    """
    stages = [
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("gauss", ["instrument.profile.w", "instrument.profile.u",
                           "instrument.profile.v"]),
        rx.Stage("lorentz", ["phases.0.lor_size", "phases.0.lor_strain"]),
    ]
    if asymmetric:
        stages.append(rx.Stage(
            "axial", ["instrument.geometry.axial_sl",
                      "instrument.geometry.axial_hl"]))
    stages += [
        rx.Stage("zero", ["instrument.zero_shift"]),
        rx.Stage("lam", ["instrument.source.lines.0.wavelength",
                         "phases.*.atoms.*.biso"]),
    ]
    plan = rx.RefinementPlan(stages=stages)
    # WP-1123's shipped schedule, named rather than inherited: every stage but
    # the last stops at 1e-6 and the last at the solver's 1e-9, which is what a
    # user's own run does.  ``None`` would converge every stage and move the
    # numbers in the module docstring.
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    return plan


def _fit(*, limits, asymmetric, free_wavelength=True):
    data = rx.read_pattern(PATTERN)
    ref = rx.Refinement(_structure(), _instrument(limits), history=False)
    if asymmetric:
        # S/L and H/L enter the FCJ aberration nearly symmetrically and are
        # exactly degenerate on one histogram (ρ → −1); tie them equal, which is
        # standard practice and what keeps this fit identifiable.
        ref.tie_equal(["instrument.geometry.axial_sl",
                       "instrument.geometry.axial_hl"])
    plan = _plan(asymmetric=asymmetric)
    if not free_wavelength:
        plan.stages[-1] = rx.Stage(
            "zero_biso", ["instrument.zero_shift", "phases.*.atoms.*.biso"])
    return ref.fit(data, plan=plan, two_theta_limits=limits)


@pytest.fixture(scope="module")
def full():
    """The XND-range fit: 2–50°, FCJ asymmetry, λ free.  The cross-code row."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit(limits=FULL_LIMITS, asymmetric=True)


@pytest.fixture(scope="module")
def symmetric():
    """≥ 8°, no asymmetry: the region where the two codes' position models
    agree, so their λ determinations can be compared without a convention gap."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit(limits=SYMMETRIC_LIMITS, asymmetric=False)


@pytest.fixture(scope="module")
def held():
    """The pre-feature fit: λ held.  Its only job is to show the diagnostic is
    silent when nothing was refined."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit(limits=FULL_LIMITS, asymmetric=True, free_wavelength=False)


def _wavelength(result):
    row = result.parameter("instrument.source.lines.0.wavelength")
    return row.value, row.stderr


def _ppm(lam, ref):
    return 1e6 * (lam - ref) / ref


# ----------------------------------------------------------------- protocol ---
def test_the_protocol_is_sane_and_states_what_differs_from_xnd(full):
    """Rexp and the channel count, before any refined number is compared.

    Unlike a same-code comparison this cannot match Rexp to floating point —
    XND counts 19 parameters over 47 980 effective observations and rietx's free
    set and effective-N differ — so the check is that Rexp lands in the right
    neighbourhood (both codes ~0.06–0.07 on this counting-statistics-limited
    pattern) on the same channels.  What *is* exact is the grid: 47 999 points,
    XND's own ``SIZE``.  The two protocol differences this suite carries — a
    P-spline background and FCJ asymmetry, against XND's interpolated points and
    A_T2 — are declared in the module docstring, which is the cross-code tier's
    requirement (adopt the protocol or say where you did not).
    """
    assert full.status == "converged"
    assert len(full.two_theta) == 47999
    assert 0.05 < full.statistics.rexp < 0.075   # XND 0.065
    assert full.statistics.gof < 2.0


# --------------------------------------------------- the wavelength headline ---
def test_the_refined_wavelength_recovers_xnds_calibration_error(full):
    """The cross-code headline, on XND's own 2–50° range.

    Two things are asserted.  First, λ moved a long way off the beamline's
    stated 0.412359 — the +41 ppm calibration error is real physics, and here it
    is detected at many times its own esd, in the same sign and order XND found.
    Second, the refined value agrees with XND's within the band the one modelled
    difference allows: rietx's FCJ axial divergence and XND's A_T2 disagree on
    the low-angle centroids, so λ (which trades against zero along a ρ = −0.9
    ridge) lands ~11 ppm short of XND.  That 11 ppm is *named* — the next test
    removes the region the two conventions disagree on and the gap collapses to
    sub-ppm.  The band here (18 ppm) is the measured convention difference with
    headroom, not a truth claim.
    """
    lam, esd = _wavelength(full)
    assert esd is not None
    move_ppm = _ppm(lam, LAM_NOMINAL)
    # a large, resolved move off the nominal — the calibration error detected
    assert 20.0 < move_ppm < 40.0, f"lambda moved {move_ppm:+.1f} ppm off nominal"
    assert abs(lam - LAM_NOMINAL) > 4.0 * esd, "the move is not resolved"
    # …in XND's direction and size, within the asymmetry-convention band
    xnd_ppm = _ppm(lam, XND["lam"])
    assert move_ppm > 0 and XND_PPM > 0, "sign disagrees with XND"
    assert abs(xnd_ppm) < 18.0, (
        f"lambda = {lam:.9f} A, {move_ppm:+.1f} ppm off nominal, "
        f"{xnd_ppm:+.1f} ppm from XND's {XND['lam']:.9f}")


def test_the_symmetric_window_recovers_xnd_to_sub_ppm(symmetric):
    """The prediction, written before the fit: remove the disagreement, recover
    the number.

    If the full-range gap to XND is the FCJ-vs-A_T2 convention and nothing else,
    then a fit restricted to the *symmetric* peaks — where neither code applies
    an asymmetry correction of consequence — must agree with XND to well inside
    the ridge scatter.  It does: dropping everything below the (111) at 7.54°
    lands λ at +41 ppm off nominal, within 1 ppm of XND's +41.4, and now
    resolved at > 15σ because the low-angle region was the whole source of the
    λ~zero indeterminacy.  This is the sub-5-ppm agreement, and it is honest
    about being the asymmetry-model-free determination rather than XND's exact
    protocol.
    """
    lam, esd = _wavelength(symmetric)
    move_ppm = _ppm(lam, LAM_NOMINAL)
    xnd_ppm = _ppm(lam, XND["lam"])
    assert 38.0 < move_ppm < 44.0, f"lambda moved {move_ppm:+.1f} ppm off nominal"
    assert abs(xnd_ppm) < 3.0, (
        f"lambda = {lam:.9f} A, {xnd_ppm:+.1f} ppm from XND — the symmetric "
        "window was supposed to remove the convention gap")
    assert abs(lam - LAM_NOMINAL) > 15.0 * esd


# ------------------------------------------------------ the evidence channel ---
def test_the_wavelength_calibration_diagnostic_fires_once_and_reports_the_ppm(
        full, held):
    """The record field this feature ships with (root CLAUDE.md's rule).

    ``WAVELENGTH_CALIBRATION`` fires exactly once, points at the scoped path,
    carries the ppm as ``Diagnostic.value`` so a client never parses the message,
    and is silent on the fit that held λ — silence being the absence of a
    refinement, not a clean bill of health.
    """
    diags = [d for d in full.diagnostics if d.code == "WAVELENGTH_CALIBRATION"]
    assert len(diags) == 1
    diag = diags[0]
    assert diag.level == "info"
    assert diag.where == ["instrument.source.lines.0.wavelength"]
    lam, _ = _wavelength(full)
    assert diag.value == pytest.approx(_ppm(lam, LAM_NOMINAL), rel=1e-9)
    # the fit that refined nothing says nothing
    assert not [d for d in held.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]


def test_biso_is_positive_and_agrees_with_xnd(full):
    """The one structural parameter, against XND's — same esd philosophy.

    Both codes carry Bérar–Lelann inflated esds, so the comparison is a genuine
    σ-distance rather than an apples-to-oranges one.  Biso comes back positive
    (the prior bad-intensity-model attempt drove it negative) and within a
    fraction of a combined σ of XND's 0.4390 Å².
    """
    b = full.parameter("phases.0.atoms.0.biso")
    assert b.value > 0.0
    comb_sd = math.hypot(b.stderr, XND["biso_sd"])
    sigma_dist = abs(b.value - XND["biso"]) / comb_sd
    assert sigma_dist < 2.0, (
        f"Biso {b.value:.4f}({b.stderr:.4f}) vs XND {XND['biso']}"
        f"({XND['biso_sd']}): {sigma_dist:.2f} combined sigma")


def test_the_lambda_zero_correlation_is_high_but_below_the_guard(full):
    """λ~zero is the physics being detected, and the fit reports it honestly.

    d = λ/(2 sin θ) makes λ and a constant zero-shift trade along a ridge, so a
    strong λ~zero correlation is expected and correct — XND printed −0.897.  The
    assertions: it appears in ``top_correlations`` at ρ ≈ −0.9 (near XND's), the
    fit raises **no** HIGH_CORRELATION (the ridge is steep but not degenerate,
    ρ below the 0.98 guard), and — because the FCJ pair was tied equal — nothing
    sits at |ρ| → 1.  A user who never saw XND is still told which two numbers
    are entangled.
    """
    pairs = full.identifiability.top_correlations
    assert pairs, "the fit reported no correlations at all"
    assert all(abs(cp.rho) < CORRELATION_GUARD for cp in pairs), (
        "a correlation reached the guard; the FCJ tie was supposed to remove "
        "the only degenerate pair")
    assert not [d for d in full.diagnostics if d.code == "HIGH_CORRELATION"]

    def is_lam_zero(cp):
        joined = cp.path_a + cp.path_b
        return "wavelength" in joined and "zero_shift" in joined

    lam_zero = [cp for cp in pairs if is_lam_zero(cp)]
    assert lam_zero, "lambda~zero is not among the top correlations"
    rho = lam_zero[0].rho
    assert -0.98 < rho < -0.80, (
        f"lambda~zero rho = {rho:+.3f}; XND printed {XND['rho_lam_zero']}")


def test_the_held_cell_is_the_certificate(full):
    """The anchor of the whole protocol, asserted as the identity it is.

    Nothing about the cell is *measured* here — it is held, and holding a
    certified cell is exactly what turns a refined λ into a calibration
    measurement.  The cubic ties (b ← a, c ← a) carry the source's value, so
    reading them shows the held length is the certificate to the bit, and their
    absent esd shows it was never refined.
    """
    for axis in ("b", "c"):
        row = full.parameter(f"phases.0.cell.{axis}")
        assert row.value == A_CERT, (
            f"held cell.{axis} = {row.value!r}, not the certificate {A_CERT}")
        assert row.stderr is None, "the held cell came back with an esd"


def test_the_sample_broadening_is_positive_and_finite(full):
    """If the Lorentzian sample broadening refines, it must be physical — and it
    is **not** compared to NIST's coefficients.

    ``lor_size`` (the 1/cos θ term) and ``lor_strain`` (the tan θ term) map onto
    the SRM 640c Information Values 0.0065(5)/cos θ + 0.0086(6)·tan θ *by
    convention only*: NIST's split is a fundamental-parameters analysis at its
    own Cu Kα instrument, so the instrument/sample division differs from this
    Caglioti-plus-Lorentzian model at 11-BM.  So the claim is the weak, true
    one — both terms come back positive and finite — with the NIST numbers as a
    NOTE (measured lor_size ≈ 0.0023, lor_strain ≈ 0.015 °2θ; the same order,
    the split apportioned differently), never as a bar.
    """
    for name in ("lor_size", "lor_strain"):
        row = full.parameter(f"phases.0.{name}")
        assert row.value > 0.0, f"{name} refined to {row.value}, not positive"
        assert math.isfinite(row.value)
        assert row.stderr is not None and math.isfinite(row.stderr)


def test_the_fit_renders(full, symmetric, held):
    """obs/calc/diff exists for **every** refinement here, so each can be looked
    at and not only summarised — `tests/CLAUDE.md`: Rwp hides locally-bad fits.

    `symmetric` earns a low-angle zoom as well, and it is not decoration.  The
    suite's headline is a *pair*: −11.0 ppm against XND over the full range and
    −0.4 ppm once the range starts at 8°, with the difference attributed to the
    two codes spelling axial asymmetry differently (FCJ against A_T2).  That is
    a claim about peak **shape** in the first few reflections, and a full-range
    plot cannot resolve it at that scale — the zoom is where a reader checks
    whether the residual really is a shape difference and not a position error
    the wavelength has absorbed.  `test_acceptance_capillary.py` plots its own
    load-bearing fixture the same way (full plus two zooms, lines 205-209).
    """
    from rietx.viz.plots import plot_result
    OUT.mkdir(exist_ok=True)

    written = []
    for res, name in ((full, "si640c_full"), (symmetric, "si640c_symmetric"),
                      (held, "si640c_held")):
        path = OUT / f"{name}.png"
        res.plot(path=str(path))
        written.append(path)

    # The region the pair's argument lives in.  Framed on the first five
    # *fitted* reflections (12.33, 14.47, 15.11, 17.47, 19.05°) rather than on
    # the 8° cut: the window has to hold several peaks or the tallest one takes
    # the whole y-scale and no shape is readable — the first attempt at this
    # zoom showed one reflection and was useless for the purpose.
    zoom = OUT / "si640c_symmetric_lowangle.png"
    plot_result(symmetric, path=str(zoom), two_theta_range=(11.5, 20.0))
    written.append(zoom)

    assert all(p.exists() for p in written), (
        f"missing: {[p.name for p in written if not p.exists()]}")


# ------------------------------------------- the background-peak worked example ---
# The manual's hump comparison (docs/docs/concepts/parameters.md § Humps)
# rests its headline on this pattern, and this is where that headline is
# executable.  Same data, same protocol, one thing changed: the background is a
# low-order Chebyshev rather than the P-spline above, which is the point — the
# specimen is in a **Kapton capillary**, the container's amorphous halo is a
# real feature near 5° 2θ, and a 3-term polynomial cannot describe it.
#
# Provenance of the identification (the blank capillary scan, the air-scatter
# control, the envelope reading) is in ``tests/data/README.md``.  None of those
# files is committed and none is read here: what this test pins is the *rietx*
# side, the two numbers the manual quotes as its comparison.

#: The manual's table, to 6 dp.  Bands below are ±0.002 in Rwp — wide enough to
#: survive a solver tolerance change, narrow enough that the *comparison*
#: (a peak beats three more polynomial terms, by a lot) cannot silently invert.
MANUAL_RWP = {"cheb3": 0.120051, "cheb3_peak": 0.082134, "cheb6": 0.088232,
              "cheb6_peak": 0.076711}


class _ChebFit(NamedTuple):
    """A Chebyshev-background fit, carrying the authority its width is judged by.

    ``model`` and ``values`` are here so a test that asks "how wide is this peak
    against the instrument?" calls :meth:`CompiledModel.instrument_fwhm_deg` —
    the same function ``check_hump_width`` uses — rather than
    re-deriving the Gaussian-only ``√(U·tan²θ + V·tanθ + W)``, which is equal to
    it only while this protocol holds ``profile.x``/``profile.y`` at zero.
    ``values`` carries the full converged instrument profile (U,V,W and the
    Lorentzian X,Y), so freeing X or Y in a later revision moves both the guard
    and this assertion together instead of silently diverging.
    """

    result: object  # RefinementResult
    model: object  # CompiledModel — evaluate-only, for instrument_fwhm_deg
    values: dict  # instrument.profile.{u,v,w,x,y}, converged


def _fit_chebyshev(nterm: int, *, with_peak: bool = False,
                   blank_scale: float | None = None, free_scale: bool = False,
                   blank_sigma: bool = True) -> _ChebFit:
    """The ``full`` protocol with a Chebyshev background, optionally + one peak.

    The peak is freed twice: once immediately after ``scale_bkg``, so the rest
    of the schedule sees a background that already has the hump in it, and once
    at the end jointly with the polynomial, because the two share curvature and
    a peak polished alone against a stale polynomial is not converged.  Seeded
    at 5.0° — the envelope maximum, i.e. where the *blank* says the halo is —
    and not at the value it converges to.

    ``blank_scale`` replaces the bare polynomial with the **measured** blank
    (run 4736) plus the same polynomial, held at that scale or — with
    ``free_scale`` — refined from it.  ``blank_sigma=False`` drops the blank's
    own esd column, which is issue #171's weighting: it measured this scan
    before ``fixed_sigma`` existed, so its Rwp column and this package's are not
    the same statistic (:func:`test_the_blank_widens_the_weight_it_is_judged_by`).
    """
    ins = _instrument(FULL_LIMITS)
    bkg_paths = ["instrument.background.c*"]
    if blank_scale is None:
        ins.background = BackgroundChebyshev.with_terms(nterm)
    else:
        blank = rx.read_pattern(BLANK)
        if not blank_sigma:
            blank = blank.model_copy(update={"sigma": None})
        ins.background = BackgroundFixedPlusChebyshev.from_pattern(
            blank, n_terms=nterm, vary_scale=free_scale, scale=blank_scale,
            source="APS 11-BM run 4736, empty Kapton capillary")
        if free_scale:
            bkg_paths.append("instrument.background.scale")
    if with_peak:
        ins.extra_components = [HumpComponent(
            label="Kapton halo",
            position=P(value=5.0, unit="deg"),
            height=P(value=50.0, min=0.0, unit="counts", transform="softplus"),
            fwhm=P(value=2.0, min=HUMP_FWHM_MIN, unit="deg",
                   transform="softplus"))]

    stages = [rx.Stage("scale_bkg", ["phases.*.scale", *bkg_paths])]
    if with_peak:
        stages.append(rx.Stage("extra_components",
                               ["instrument.extra_components.*"]))
    stages += [
        rx.Stage("gauss", ["instrument.profile.w", "instrument.profile.u",
                           "instrument.profile.v"]),
        rx.Stage("lorentz", ["phases.0.lor_size", "phases.0.lor_strain"]),
        rx.Stage("axial", ["instrument.geometry.axial_sl",
                           "instrument.geometry.axial_hl"]),
        rx.Stage("zero", ["instrument.zero_shift"]),
        rx.Stage("lam", ["instrument.source.lines.0.wavelength",
                         "phases.*.atoms.*.biso"]),
    ]
    if with_peak:
        stages.append(rx.Stage("extra_components2",
                               ["instrument.extra_components.*",
                                "instrument.background.c*"]))
    plan = rx.RefinementPlan(stages=stages)
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited

    data = rx.read_pattern(PATTERN)
    ref = rx.Refinement(_structure(), ins, history=False)
    ref.tie_equal(["instrument.geometry.axial_sl",
                   "instrument.geometry.axial_hl"])
    res = ref.fit(data, plan=plan, two_theta_limits=FULL_LIMITS)
    # The compiled model and the converged instrument profile, so a test can ask
    # instrument_fwhm_deg the same question the width guard does.  X and Y are
    # read from the converged instrument (0 under this protocol) rather than
    # assumed, so the assertion follows the fit if a later revision frees them.
    prof = ref.instrument.profile
    values = {f"instrument.profile.{k}": getattr(prof, k).value
              for k in ("u", "v", "w", "x", "y")}
    return _ChebFit(result=res, model=ref._model, values=values)


@pytest.fixture(scope="module")
def cheb3():
    """Chebyshev-3, no peak: the background that cannot describe the halo."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit_chebyshev(3, with_peak=False)


@pytest.fixture(scope="module")
def cheb3_peak():
    """Chebyshev-3 + one background peak — three parameters more than `cheb3`."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit_chebyshev(3, with_peak=True)


@pytest.fixture(scope="module")
def cheb6():
    """Chebyshev-6, no peak — also three parameters more than `cheb3`, and the
    fair comparison the whole argument turns on."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit_chebyshev(6, with_peak=False)


@pytest.fixture(scope="module")
def cheb6_peak():
    """Chebyshev-6 + one background peak — the fourth table row.

    Quoted in the manual (`concepts/parameters.md` § Humps), the ``HumpComponent`` docstring and
    this module's `MANUAL_RWP`, and the arm the "relaxes to 5.245(41)°" caveat
    turns on; a fixture so all three are pinned to a refinement rather than to a
    number a solver change can silently move.
    """
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit_chebyshev(6, with_peak=True)


def test_one_hump_beats_three_more_polynomial_terms(
        cheb3, cheb3_peak, cheb6, cheb6_peak):
    """The manual's headline, and the reason it is a *comparison* and not a ΔRwp.

    A free position, height and width will lower any Rwp — that is exactly the
    evidence this package refuses.  What makes the number mean something is that
    the two improved arms cost the **same three parameters**, so the peak has to
    beat the polynomial on equal terms.  It does, by a wide margin: 31 %
    relative against 26 %, and the assertion is on the *ordering* rather than on
    either figure alone.

    The loop pins **all four** table rows to their fits — ``cheb6_peak`` too,
    the row the manual, the docstring and `MANUAL_RWP` all carry and nothing
    used to hold — so the prose cannot say a number no refinement produces.
    """
    for name, fit in (("cheb3", cheb3), ("cheb3_peak", cheb3_peak),
                      ("cheb6", cheb6), ("cheb6_peak", cheb6_peak)):
        res = fit.result
        assert res.status == "converged", f"{name} did not converge"
        assert len(res.two_theta) == 47999
        assert abs(res.statistics.rwp - MANUAL_RWP[name]) < 0.002, (
            f"{name} Rwp {res.statistics.rwp:.6f}, manual says "
            f"{MANUAL_RWP[name]:.6f}")

    gain_peak = cheb3.result.statistics.rwp - cheb3_peak.result.statistics.rwp
    gain_poly = cheb3.result.statistics.rwp - cheb6.result.statistics.rwp
    assert gain_peak > 0.03, f"the peak bought only {gain_peak:.5f} in Rwp"
    assert gain_peak > 1.15 * gain_poly, (
        f"one peak ({gain_peak:.5f}) no longer beats three more Chebyshev "
        f"terms ({gain_poly:.5f}) by a clear margin")
    # and it is not bought by wrecking the identifiability
    assert not [d for d in cheb3_peak.result.diagnostics
                if d.code == "HIGH_CORRELATION"]


def test_the_peak_is_diffuse_by_three_orders_and_frees_the_structural_esd(
        cheb3, cheb3_peak):
    """Two claims the manual makes about the *peak*, not about Rwp.

    **It is a background term.**  Its width is 5.57(27)° where this
    synchrotron's Gaussian FWHM at the same angle is 0.0035°, so the ratio is in
    the thousands — three orders clear of ``HUMP_MIN_WIDTH_MULT``,
    and ``HUMP_TOO_NARROW`` is silent.

    **It gives back precision rather than moving the answer.**  Biso(Si) stays
    put to well inside one esd; what changes is the esd, by ~6×, and the same
    for λ.  A background the model cannot describe blurs this fit rather than
    biasing it, which is the reading the manual carries.
    """
    res = cheb3_peak.result
    fwhm = res.parameter("instrument.extra_components.0.fwhm")
    pos = res.parameter("instrument.extra_components.0.position")
    assert fwhm.stderr is not None and pos.stderr is not None
    assert 5.0 < fwhm.value < 6.2, f"hump FWHM {fwhm.value:.3f}°"
    assert 3.5 < pos.value < 5.5, f"hump position {pos.value:.3f}°"

    # The instrumental FWHM at the hump, from the *same* authority the width
    # guard measures against — CompiledModel.instrument_fwhm_deg (Γ_G ⊕ Γ_L via
    # TCH) — rather than re-deriving the Gaussian-only √(U·tan²θ + V·tanθ + W),
    # which equals it only while profile.x/profile.y are held at zero.
    inst = float(cheb3_peak.model.instrument_fwhm_deg(pos.value,
                                                      cheb3_peak.values))
    assert fwhm.value / inst > 1000.0, (
        f"hump is only {fwhm.value / inst:.0f}× the instrumental FWHM")
    assert not [d for d in res.diagnostics
                if d.code == "HUMP_TOO_NARROW"]

    for path, floor in (("phases.0.atoms.0.biso", 4.0),
                        ("instrument.source.lines.0.wavelength", 4.0)):
        wide, tight = cheb3.result.parameter(path), res.parameter(path)
        assert wide.stderr is not None and tight.stderr is not None
        assert wide.stderr / tight.stderr > floor, (
            f"{path}: esd only fell {wide.stderr / tight.stderr:.1f}×")
        # the value itself does not move: well inside the *wider* esd
        assert abs(wide.value - tight.value) < 0.5 * wide.stderr, (
            f"{path} moved {abs(wide.value - tight.value):.3g}, more than half "
            f"the peak-free esd {wide.stderr:.3g}")


def test_the_chebyshev6_arm_relaxes_the_peak_onto_the_envelope(
        cheb3_peak, cheb6_peak):
    """The manual's standing rule, from the numbers it rests on.

    "Declare a peak *instead of* extra polynomial terms, never on top of them"
    is argued from what the peak does between the two arms: with only three
    Chebyshev terms it sits low and wide (4.18(9)°, 5.57(22)°), absorbing the
    residual direct-beam rise the short polynomial cannot; give the polynomial
    three more terms and the peak relaxes onto the envelope (5.245(32)°) and
    narrows by nearly three (1.94(8)°) while Rwp barely moves.  That is the
    "5.245(41)°" caveat the manual and the docstring both quote, held here to a
    refinement rather than to prose.
    """
    p3 = cheb3_peak.result.parameter("instrument.extra_components.0.position")
    w3 = cheb3_peak.result.parameter("instrument.extra_components.0.fwhm")
    p6 = cheb6_peak.result.parameter("instrument.extra_components.0.position")
    w6 = cheb6_peak.result.parameter("instrument.extra_components.0.fwhm")

    # the Chebyshev-6 arm moves onto the envelope and narrows
    assert 5.1 < p6.value < 5.4, f"relaxed position {p6.value:.3f}°"
    assert 1.7 < w6.value < 2.2, f"relaxed FWHM {w6.value:.3f}°"
    # and it is a genuine move relative to the three-term arm, not a re-quote
    assert p6.value - p3.value > 0.8, "the peak did not move onto the envelope"
    assert w3.value / w6.value > 2.0, "the peak did not narrow between arms"
    # still a background width, and still identifiable
    assert not [d for d in cheb6_peak.result.diagnostics
                if d.code in ("HUMP_TOO_NARROW", "HIGH_CORRELATION")]


# ------------------------------------------------- the measured blank (1309) ---
# The section above fits the container's halo with three free parameters.  This
# one *measures* it: the same capillary, the same beamtime, the specimen taken
# out.  WP-1309 built the machinery on a synthetic fixture because run 4736 was
# not fetchable; it arrived on 2026-09-17, and this is where issue #171's own
# numbers are finally checked against a refinement rather than corroborated by
# construction.
#
# The blank is a *declared* curve, so the arms differ in what they declare and
# not in how many parameters they fit: `blank_held` declares it whole (the only
# thing pre-1309 code could express), `blank_free` declares its shape and
# refines the one multiplier that says how much of it reached this scan.

#: Measured here on the committed blank, `[dev]` venv, darwin (WP-1309).
#: Bands below are ±0.002 in Rwp, as `MANUAL_RWP`'s are.
BLANK_RWP = {"held": 0.074012, "free": 0.073749}
#: Issue #171's hand-set scan found its interior minimum at s ≈ 0.85.  This is
#: what the refined scale is measured against, and it is the *reason* the field
#: exists: 1.0 was the only value the code could express.
S_ISSUE = 0.85


def _rwp_under(res, sigma) -> float:
    """``res``'s own residual, weighted by somebody else's σ.

    Rwp is a weighted sum, and a measured background with esds moves the weight
    (σ² = σ_y² + s²·σ_f²).  So two arms that declare different scales are not
    scored on the same statistic, and comparing them means picking one σ and
    using it for both — here the specimen's own, which is what every arm above
    this section is already weighted by.

    The length check is the point of failure this is worth guarding: two arms
    fitted over different channels would broadcast rather than raise, and the
    number that came out would look like a comparison.
    """
    w = 1.0 / np.asarray(sigma) ** 2
    y, y_calc = np.asarray(res.y_obs), np.asarray(res.y_calc)
    assert w.shape == y.shape, (
        f"σ covers {w.size} channels and this residual {y.size} — the two arms "
        "are not fitted over the same channels, so neither is a common weight")
    return float(np.sqrt((w * (y - y_calc) ** 2).sum() / (w * y * y).sum()))


def _require_the_pair() -> None:
    """Both halves or nothing: a blank arm needs the specimen *and* the blank."""
    for path in (PATTERN, BLANK):
        if not path.exists():
            pytest.skip(f"{path.name} not present")


@pytest.fixture(scope="module")
def blank_held():
    """The blank declared whole — scale 1.0, nothing refined about it."""
    _require_the_pair()
    return _fit_chebyshev(3, blank_scale=1.0)


@pytest.fixture(scope="module")
def blank_free():
    """The same curve with its multiplier refined: one parameter, seeded at the
    value the held arm is stuck with."""
    _require_the_pair()
    return _fit_chebyshev(3, blank_scale=1.0, free_scale=True)


@pytest.fixture(scope="module")
def blank_free_cheb6():
    """The same, on six Chebyshev terms — the arm that shows what a flexible
    polynomial does to a measured scale."""
    _require_the_pair()
    return _fit_chebyshev(6, blank_scale=1.0, free_scale=True)


@pytest.fixture(scope="module")
def blank_scan():
    """Three hand-set scales in **issue #171's** weighting — the blank's esd
    column dropped, because the issue measured its scan before `fixed_sigma`
    existed and its Rwp column is therefore not this package's."""
    _require_the_pair()
    return {s: _fit_chebyshev(3, blank_scale=s, blank_sigma=False)
            for s in (0.75, S_ISSUE, 1.00)}


def test_a_measured_blank_beats_the_polynomial_and_the_fitted_hump(
        cheb3, cheb3_peak, blank_held):
    """The case for measuring a blank at all, on one common weight.

    ``blank_held`` refines **nothing** about the background beyond the same
    three Chebyshev terms the other two arms carry: the container's shape is
    declared, not fitted.  It still beats both — the bare polynomial by a third,
    and the three-parameter hump of the section above.  Three numbers somebody
    measured with the sample out beat three numbers this fit invented.

    Scored under the specimen's own σ for all three arms, because the blank's
    esds move the weight and `test_the_blank_widens_the_weight_it_is_judged_by`
    is where that is measured.  This test applies the rule that one states.
    """
    sigma_y = cheb3.result.sigma
    declared = _rwp_under(blank_held.result, sigma_y)
    fitted = cheb3_peak.result.statistics.rwp
    plain = cheb3.result.statistics.rwp

    assert blank_held.result.status == "converged"
    assert declared < fitted, (
        f"the declared curve ({declared:.6f}) no longer beats the fitted hump "
        f"({fitted:.6f})")
    assert plain - declared > 0.03, (
        f"the declared curve bought only {plain - declared:.5f} in Rwp")
    # and it is free of the identifiability cost a flexible background carries
    assert not [d for d in blank_held.result.diagnostics
                if d.code == "HIGH_CORRELATION"]


def test_the_refined_scale_rejects_the_only_value_the_code_could_express(
        cheb3, blank_held, blank_free):
    """WP-1309's headline, and the one number issue #171 asked for.

    The blank was scanned on a different monitor normalisation, and the specimen
    absorbs what the container scatters, so the fraction of the blank that
    reached run 4918 is not 1.0 — and 1.0 was the only value this package could
    express before the ``scale`` field existed.  Freed, it comes back at
    0.8413(107): issue #171's hand-set interior minimum of ≈ 0.85 sits 0.8
    esd away, and unity is rejected at more than ten (0.8374(113) and 1.1 esd
    on 1.9.0).

    The synthetic fixture in `test_background_measured.py` recovered 0.8315(58)
    against a truth of 0.85 and named the mechanism — a noisy blank biases its
    own scale low, by regression dilution.  This blank's σ/I runs 8-17 % over
    the range, so the same bias is expected here and the band is set for it
    rather than centred on 0.85.
    """
    row = blank_free.result.parameter("instrument.background.scale")
    assert row.stderr is not None, "the refined scale came back with no esd"
    assert 0.78 < row.value < 0.90, f"scale {row.value:.4f}"
    assert abs(row.value - S_ISSUE) < 2.0 * row.stderr, (
        f"scale {row.value:.4f}({row.stderr:.4f}) is more than 2 esd from the "
        f"issue's hand-set minimum {S_ISSUE}")
    assert (1.0 - row.value) / row.stderr > 5.0, (
        f"unity is only {(1.0 - row.value) / row.stderr:.1f} esd away — this "
        f"fit no longer distinguishes the measured scale from the declared one")

    # The acceptance bar: Rwp falls, and not because the weight moved.  The
    # second row is the one that carries the claim — the first compares each
    # arm under *its own* σ, which is two weights and therefore the comparison
    # `test_the_blank_widens_the_weight_it_is_judged_by` says is not a ranking.
    # It is here as a regression pin on the two recorded numbers, not as
    # evidence.  The common weight is the specimen's own σ, the same one every
    # other cross-arm comparison in this section uses, so the pair asserted
    # here is the pair the validation matrix records (0.078843 → 0.076946;
    # 0.079311 → 0.077328 on 1.9.0).
    sigma_y = cheb3.result.sigma
    for label, (free, held) in (
            ("each arm's own σ", (blank_free.result.statistics.rwp,
                                  blank_held.result.statistics.rwp)),
            ("the specimen's σ", (_rwp_under(blank_free.result, sigma_y),
                                  _rwp_under(blank_held.result, sigma_y)))):
        assert free < held, f"freeing the scale raised Rwp under {label}"
    for name, fit in (("held", blank_held), ("free", blank_free)):
        assert abs(fit.result.statistics.rwp - BLANK_RWP[name]) < 0.002, (
            f"{name} Rwp {fit.result.statistics.rwp:.6f}, measured "
            f"{BLANK_RWP[name]:.6f}")


def test_the_hand_set_scan_puts_the_minimum_where_the_scale_landed(
        blank_scan, blank_free):
    """Issue #171's own experiment, rerun: the minimum is **interior**.

    The issue hand-set the scale because nothing could refine it, and found Rwp
    falling to s ≈ 0.85 and rising again by 1.0 — 2.2 % of Rwp between the two.
    Here the same scan, in the issue's weighting, gives 0.077949 / 0.077315 /
    0.079220 at 0.75 / 0.85 / 1.00: the minimum is interior, 2.5 % below unity,
    and it is where the refined scale independently landed.

    That is the whole argument for a refinable scale over a higher-order
    polynomial.  The polynomial is additive, so it can move the level of a fixed
    curve and never rescale its shape, and a scan like this is what a caller had
    to do by hand instead.
    """
    rwp = {s: fit.result.statistics.rwp for s, fit in blank_scan.items()}
    assert all(fit.result.status == "converged" for fit in blank_scan.values())
    assert rwp[S_ISSUE] < rwp[0.75], f"0.75 ({rwp[0.75]:.6f}) beat the minimum"
    assert rwp[S_ISSUE] < rwp[1.00], (
        f"unity ({rwp[1.00]:.6f}) beat s = {S_ISSUE} ({rwp[S_ISSUE]:.6f}) — the "
        f"minimum is no longer interior, which is the issue's whole finding")
    assert (rwp[1.00] - rwp[S_ISSUE]) / rwp[S_ISSUE] > 0.015, (
        "unity now costs less than 1.5 % of Rwp; the issue measured 2.2 %")
    # and the refined scale agrees with the scan it replaces
    s_free = blank_free.result.parameter("instrument.background.scale").value
    assert 0.75 < s_free < 1.00, "the refined scale left the scan's bracket"


def test_a_longer_polynomial_eats_the_measured_scale(
        cheb3, blank_free, blank_free_cheb6):
    """The identifiability warning, on real data and with Rwp on the wrong side.

    `test_background_measured.py` measured this on a synthetic blank: freeing
    more Chebyshev terms walks the recovered scale away from the truth (0.8315
    on two terms down to 0.6479 on six) while Rwp *improves* the whole way.  The
    polynomial is additive and the curve is a shape, so what the two share is
    the background's level, and the longer polynomial takes it.

    Here, on run 4736: 0.8413(107) on three terms and 0.6935(192) on six — the
    same walk, on data nobody constructed.  And the sting is which arm Rwp
    prefers.  Scored on one common weight the six-term arm is the *better* fit
    (0.075953 against 0.076946) while its scale is the one that disagrees with
    issue #171's hand-set minimum.  A lower Rwp does not make a scale more
    nearly measured, which is why the docs' rule is what it is: if the scale is
    a number you intend to quote, keep the polynomial as low-order as the fit
    tolerates.
    """
    s3 = blank_free.result.parameter("instrument.background.scale")
    s6 = blank_free_cheb6.result.parameter("instrument.background.scale")
    assert s3.stderr is not None and s6.stderr is not None, (
        "a free scale came back with no esd, so the two arms cannot be "
        "separated in esd units")
    assert s6.value < s3.value, "the longer polynomial no longer eats the scale"
    assert (s3.value - s6.value) / math.hypot(s3.stderr, s6.stderr) > 3.0, (
        f"the walk {s3.value:.4f} → {s6.value:.4f} is inside the esds, so this "
        f"test no longer distinguishes the two arms")
    assert abs(s6.value - S_ISSUE) > abs(s3.value - S_ISSUE), (
        "six terms moved the scale toward the hand-set minimum, not away")

    # and Rwp, on one weight, prefers the arm whose scale moved away
    sigma_y = cheb3.result.sigma
    assert (_rwp_under(blank_free_cheb6.result, sigma_y)
            < _rwp_under(blank_free.result, sigma_y)), (
        "Rwp no longer prefers the six-term arm — the warning this test carries "
        "rests on it doing so")


def test_the_blank_widens_the_weight_it_is_judged_by(cheb3, blank_held):
    """σ² = σ_y² + s²·σ_f², and what follows for reading Rwp.

    A measured background carries counting statistics of its own, and they enter
    the weight every renderer and every statistic divides by.  Two consequences
    reach anyone comparing arms, and neither is visible in an Rwp column.

    The weight is *looser*: this blank's own σ inflates the specimen's by up to
    ~14 % at the low-angle end where the container dominates.  So the same
    residual scores better — ``blank_held`` reads 0.073609 against its own σ and
    0.078843 against the specimen's alone, and 7 % of that number is weighting
    rather than fit.

    And the weight depends on **s**, so an Rwp column down a scan of scales is
    not a ranking: the σ-weighted minimum of the scan sits at 0.90 where the
    common-weight minimum is at 0.85, which is where the refined scale is.  This
    is why every cross-arm comparison in this section goes through
    :func:`_rwp_under`, and why the package's own rule — a correction ships with
    a record field, never an Rwp comparison as its evidence — has teeth here.
    """
    sigma_y = np.asarray(cheb3.result.sigma)
    sigma_b = np.asarray(blank_held.result.sigma)
    assert sigma_b.shape == sigma_y.shape
    assert np.all(sigma_b >= sigma_y - 1e-12), (
        "a measured background's esds made the weight tighter, not looser")
    assert sigma_b.max() / sigma_y.max() > 1.0, "σ did not widen at all"

    own = blank_held.result.statistics.rwp
    common = _rwp_under(blank_held.result, sigma_y)
    assert common > own, (
        "the widened weight no longer flatters Rwp, so the caveat this test "
        "carries has changed shape")
    assert (common - own) / own > 0.03, (
        f"weighting accounts for only {(common - own) / own:.1%} of Rwp here")


def test_the_blank_arms_render(blank_held, blank_free):
    """obs/calc/diff for both arms, plus the window the scale acts in.

    The rule the whole suite runs on (`tests/CLAUDE.md`): Rwp hides a locally
    bad fit, and this correction is local by construction — it is the container
    halo that a 3-term polynomial rides over.  The zoom stops at **7°, below the
    (111)**, and that is the whole reason it is readable: include one Bragg
    reflection and it takes the entire y-scale, which is what the module's other
    zoom records learning.  Framed here, the halo is the only thing in the
    picture and the held arm's calculated curve can be *seen* above the data.
    """
    from rietx.viz.plots import plot_result
    OUT.mkdir(exist_ok=True)

    written = []
    for fit, name in ((blank_held, "si640c_blank_held"),
                      (blank_free, "si640c_blank_free")):
        full_page = OUT / f"{name}.png"
        fit.result.plot(path=str(full_page))
        zoom = OUT / f"{name}_halo.png"
        plot_result(fit.result, path=str(zoom), two_theta_range=(2.0, 7.0))
        written += [full_page, zoom]

    assert all(p.exists() for p in written), (
        f"missing: {[p.name for p in written if not p.exists()]}")
