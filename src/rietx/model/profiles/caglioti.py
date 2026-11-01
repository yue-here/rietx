"""Angular dependence of profile widths — instrument ⊕ sample split.

Gaussian *variance* (variances add under convolution):

    Γ_G²(θ) = (U + Us)·tan²θ + V·tanθ + W + P/cos²θ     [deg² 2θ]

U, V, W are the instrument resolution function (Caglioti, Paoletti & Ricci,
1958, Nucl. Instrum. 3, 223); the sample adds a Gaussian microstrain term
Us·tan²θ and a Gaussian size term P/cos²θ (the GSAS ``P``; Larson & Von
Dreele, 2004, GSAS manual; Thompson, Cox & Hastings, 1987, J. Appl. Cryst.
20, 79).

Lorentzian FWHM (Lorentzian convolution adds FWHMs):

    Γ_L(θ) = (X + Xs)/cosθ + (Y + Ys)·tanθ              [deg 2θ]

The 1/cosθ (and 1/cos²θ variance) terms carry Scherrer crystallite-size
broadening and the tanθ (tan²θ) terms microstrain broadening.  Note the
letter conventions differ between codes (GSAS: X=size, Y=strain; FullProf
swaps them) — this module documents the *physics* via argument names.

Reading a width as a size
-------------------------
The width laws above are in deg 2θ, which is the unit the pattern arrives in
and the wrong unit to *judge* a width in: the same 1.0 deg FWHM is a 8.2 nm
crystallite on Cu Kα and a 2.2 nm one on 11-BM's 0.4139 Å (computed below,
pinned in ``tests/test_profile_size.py``).  A number of degrees is therefore
not transferable between instruments, while the crystallite size it implies is
— which is the same statement as working in Q, since Scherrer broadening is
*constant* in Q:

    Q = 4π·sinθ/λ,  so  dQ/d(2θ) = 2π·cosθ/λ,  and with
    2w(2θ) = K·λ/(L·cosθ)                                    [Scherrer, rad]
    ΔQ = (2π·cosθ/λ)·2w = 2π·K/L                              [Å⁻¹]     (3)

independent of both λ and θ.  Hence :func:`apparent_size`, and the exact
consequence that makes it cheap: because the size law *is* 1/cosθ, the cosθ of
(3) cancels the cosθ of the law and a size **coefficient** maps to one size
with no reference angle at all —

    L = (180/π)·K·λ / x_size                                             (4)

for the Lorentzian ``x_size``, and the same with √``gauss_size`` for the
Gaussian variance coefficient.  :func:`apparent_size_from_size_coefficient` is
(4) and :func:`size_coefficient_for_size` is its inverse, which is what seeds a
width from a known specimen.

Reading a width as a strain
---------------------------
The strain law inverts the same way and needs *less*: microstrain broadens by a
fixed fraction of every d-spacing, Δ2θ = 2·(Δd/d)·tanθ in radians, so

    Δd/d = (π/180)·y_strain / 2                                            (5)

with **no wavelength and no shape constant** — :func:`microstrain_from_strain_coefficient`
and its inverse :func:`strain_coefficient_for_microstrain`.  That asymmetry is
the whole content of WP-1131: two of the six sample-broadening quantities depend
on λ and they are exactly the two named "size", so one specimen measured at two
wavelengths shares a strain coefficient and does **not** share a size one.

**Which parameters this reaches**, since it is the point of reading a width as
a size at all: exactly the two size coefficients of the laws above, and no
others.  ``x_size`` is ``instrument.profile.x + phases.N.lor_size``,
``gauss_size`` is ``phases.N.gauss_size``, and their declared bounds are where
the deg-versus-Å question bites:

* ``instrument.profile.x`` carries ``max = 1.0`` deg — 79.4 Å on Cu Kα against
  21.3 Å on 11-BM.  One cap, a 3.7× spread in the physics it admits.
* ``Phase.lor_size`` and ``Phase.gauss_size`` carry ``min = 0.0`` and **no max
  at all**, so on the sample side an unbounded specimen width is not capped
  badly — it is not capped.

The Caglioti ``u`` and ``w`` are **not** size terms and have no size to read:
``w`` is constant in θ and ``u`` goes as tan²θ, neither of them 1/cosθ.  A
number of degrees taken off either is a number at one chosen angle, which is
the reference angle this module exists to remove.  Report in degrees by all
means; decide in size.
"""

from __future__ import annotations

import math

import numpy as np

from ...backend import get_backend

_MIN_GAMMA_G2 = 1e-8  # deg²; keeps Γ_G real when U,V,W make the quadratic dip

#: Scherrer constant for a **FWHM** and roughly isotropic crystallites
#: (Scherrer, 1918, Nachr. Ges. Wiss. Göttingen, Math.-Phys. Kl. 1918, 98-100 —
#: the primary record's volume is the year, not the "26" the constant is usually
#: quoted with; Langford & Wilson, 1978, J. Appl. Cryst. 11, 102-113 tabulate K
#: by crystallite shape *and* by which width measure is used — 0.89 for the FWHM
#: of a sphere against 1.0747 for its integral breadth).  Shape moves it by
#: ~10-20 %, so an apparent size is an order-of-magnitude statement and never a
#: quotable two-figure one; K is an argument everywhere below so a caller with a
#: known morphology can say so.
SCHERRER_K = 0.9

# `not x > 0.0` rather than `x <= 0.0` throughout, because it is also the nan
# test: nan fails every comparison, so `nan <= 0.0` is False and would let a nan
# through to be returned as a nan size.  Refusing by name is the whole point of
# these guards, and a nan is the input least likely to be noticed downstream.


def delta_q_fwhm(fwhm_deg: float, two_theta_deg: float,
                 wavelength_a: float) -> float:
    """The width ``fwhm_deg`` (deg 2θ FWHM) as a Q width, Å⁻¹.

    ``dQ/d(2θ) = 2π·cosθ/λ`` — the local Jacobian of Q = 4π·sinθ/λ, so this is
    a *linearisation* and is the honest conversion only while the width is
    small against the angle it sits at.  It is exact in the limit and within a
    percent for anything a Rietveld profile calls a peak.

    A scalar helper for reporting and diagnostics, not a hot-path function: it
    is plain python float arithmetic and does not route through the backend.

    Refuses a non-positive width or wavelength and a 2θ outside (0, 180) by
    name.  This is the **one** place those three are checked: it is public, so a
    direct caller is as exposed as :func:`apparent_size`'s — and unguarded it
    returns a *negative* Q width on a negative λ or on 2θ > 180, which is not a
    quantity at all.
    """
    if not fwhm_deg > 0.0:
        raise ValueError(f"fwhm_deg must be positive, got {fwhm_deg!r}")
    if not wavelength_a > 0.0:
        raise ValueError(f"wavelength_a must be positive, got {wavelength_a!r}")
    if not 0.0 < two_theta_deg < 180.0:
        raise ValueError(f"two_theta_deg must lie in (0, 180), got {two_theta_deg!r}")
    theta = math.radians(two_theta_deg / 2.0)
    return 2.0 * math.pi * math.cos(theta) * math.radians(fwhm_deg) / wavelength_a


def apparent_size(fwhm_deg: float, two_theta_deg: float, wavelength_a: float,
                  k: float = SCHERRER_K) -> float:
    """Scherrer crystallite size, Å, from a FWHM at one angle.

    ``L = K·λ / (2w·cosθ)`` with 2w the FWHM in radians of 2θ (Scherrer, 1918;
    the K convention is :data:`SCHERRER_K`'s, and 2w rather than β is Langford &
    Wilson's symbol for a FWHM — their β is the integral breadth).
    Equivalently ``L = 2π·K/ΔQ`` with ΔQ from :func:`delta_q_fwhm` — the
    module docstring's (3), and the reason this is the instrument-independent
    way to read a width.

    This is the **whole** width, so the size it returns is a lower bound on the
    crystallite size unless the instrumental contribution has already been
    taken out: strain, the instrument function and the specimen all broaden,
    and Scherrer attributes everything it is handed to size.  Use it to ask
    "could size *alone* explain this width?", never to report a size from a
    total width.

    Raises ``ValueError`` on a non-positive width, angle, wavelength or K — a
    zero width is an infinite size, which is true and not a number a caller can
    do anything with, and a zero or negative K is *less* usable than that: it
    returns a zero or negative length that no downstream check would question.
    The width, angle and wavelength are refused by :func:`delta_q_fwhm`, which
    this goes through anyway — one place per check, and the same message.
    """
    if not k > 0.0:
        raise ValueError(f"k must be positive, got {k!r}")
    return 2.0 * math.pi * k / delta_q_fwhm(fwhm_deg, two_theta_deg, wavelength_a)


def apparent_size_from_size_coefficient(coefficient_deg: float,
                                        wavelength_a: float,
                                        k: float = SCHERRER_K) -> float:
    """Scherrer size, Å, from a **1/cosθ size coefficient** — no angle needed.

    The module docstring's (4).  ``coefficient_deg`` is the Lorentzian
    ``x_size`` — ``instrument.profile.x + phases.N.lor_size`` — directly, or
    ``sqrt(phases.N.gauss_size)`` for the Gaussian variance coefficient, both in
    the deg-2θ FWHM units :func:`lorentzian_fwhm` and :func:`gaussian_fwhm` use.
    Those are the only two parameters this inverts exactly; the Caglioti ``u``
    and ``w`` are tan²θ and constant terms and have no size to read.

    Angle-free because the law and Scherrer are the *same* 1/cosθ: this is
    :func:`apparent_size` evaluated at any 2θ whatever, and
    ``tests/test_profile_size.py`` asserts that identity across the pattern
    range rather than trusting the cancellation on paper.  That is the whole
    argument for judging a width as a size — there is no reference angle to
    choose and therefore none to get wrong.
    """
    if not coefficient_deg > 0.0:
        raise ValueError(f"coefficient_deg must be positive, got {coefficient_deg!r}")
    if not wavelength_a > 0.0:
        raise ValueError(f"wavelength_a must be positive, got {wavelength_a!r}")
    if not k > 0.0:
        raise ValueError(f"k must be positive, got {k!r}")
    return math.degrees(k * wavelength_a / coefficient_deg)


def size_coefficient_for_size(size_a: float, wavelength_a: float,
                              k: float = SCHERRER_K) -> float:
    """Inverse of :func:`apparent_size_from_size_coefficient`: deg 2θ per Å.

    What seeds a width from a specimen one already knows something about — a
    micrograph, a synthesis, a previous refinement — rather than from the
    package's synchrotron-linewidth default, which a lab pattern's frozen
    windows cannot recover from.

    Seeds ``instrument.profile.x`` or ``phases.N.lor_size`` directly, and
    ``phases.N.gauss_size`` as the square of what it returns.
    """
    if not size_a > 0.0:
        raise ValueError(f"size_a must be positive, got {size_a!r}")
    if not wavelength_a > 0.0:
        raise ValueError(f"wavelength_a must be positive, got {wavelength_a!r}")
    if not k > 0.0:
        raise ValueError(f"k must be positive, got {k!r}")
    return math.degrees(k * wavelength_a / size_a)


def microstrain_from_strain_coefficient(coefficient_deg: float) -> float:
    """Δd/d (dimensionless) from a **tanθ strain coefficient** — no λ, no angle.

    The size reading three functions up needs a wavelength and a Scherrer
    constant; this one needs neither, and that asymmetry *is* the physics this
    WP-1131 turns on.  Strain broadens by a fixed *fraction* of every d-spacing,

        Δ2θ = 2·(Δd/d)·tanθ                                    [radians]  (5)

    which is Bragg's law differentiated (λ = 2d sinθ ⇒ Δd/d = −cotθ·Δθ) and is
    the strain-broadening relation of Stokes & Wilson, 1944, Proc. Phys. Soc.
    **56**, 174-181; Von Dreele's ``M = 180·μ·tanΘ/π`` is the same line with
    μ = 2Δd/d.  So a coefficient in deg 2θ inverts to

        Δd/d = (π/180)·``coefficient_deg`` / 2                            (6)

    with no wavelength in it at all — the same specimen shows the *same* number
    of degrees of strain broadening on every instrument, where it shows a
    λ-proportional number of degrees of size broadening.

    ``coefficient_deg`` is the Lorentzian ``y_strain`` —
    ``instrument.profile.y + phases.N.lor_strain`` — directly, or
    ``sqrt(phases.N.gauss_strain)`` for the Gaussian variance coefficient, the
    same pairing :func:`apparent_size_from_size_coefficient` takes.

    **The convention, stated because the neighbours disagree.**  The returned
    number is Δd/d read as a **FWHM** of the d-spacing distribution, which is
    what rietx's coefficients are: (5) is a relation between two FWHMs, so no
    peak-shape assumption enters and no second constant is needed.  GSAS-II
    reports ``mustrain`` μ = 2·Δd/d in units of 10⁻⁶ off the same FWHM, i.e.
    twice this.  FullProf reports an *apparent strain* ``½·β*·d`` off the
    **integral breadth** of the size-only pseudo-Voigt — half of this before the
    breadth-vs-FWHM factor, which is π/2 for a pure Lorentzian and 1.0645 for a
    pure Gaussian.  Quote the number with the convention or do not quote it.

    Refuses a non-positive coefficient by name, for
    :func:`apparent_size_from_size_coefficient`'s reason: zero strain is a
    perfect lattice, which is true and is not a measurement.
    """
    if not coefficient_deg > 0.0:
        raise ValueError(f"coefficient_deg must be positive, got {coefficient_deg!r}")
    return math.radians(coefficient_deg) / 2.0


def strain_coefficient_for_microstrain(microstrain: float) -> float:
    """Inverse of :func:`microstrain_from_strain_coefficient`: deg 2θ per Δd/d.

    ``(360/π)·microstrain``.  What seeds a width from a strain one already knows
    — the seeding direction :func:`size_coefficient_for_size` serves on the size
    side.  Seeds ``instrument.profile.y`` or ``phases.N.lor_strain`` directly,
    and ``phases.N.gauss_strain`` as the square of what it returns.
    """
    if not microstrain > 0.0:
        raise ValueError(f"microstrain must be positive, got {microstrain!r}")
    return math.degrees(2.0 * microstrain)


#: Γ² = 8 ln 2 · σ²: what turns a coefficient of a Gaussian *variance* into
#: one of the Gaussian FWHM² :func:`gaussian_fwhm` takes.  GSAS-I's ``GU GV
#: GW`` and GSAS-II's ``U V W`` are variances (Larson & Von Dreele 2004, CW
#: profile function 3), so every reader and writer of either crosses this one
#: factor; ``tests/test_gsas2_instprm.py`` pins it against GSAS-II's drawn
#: LaB6 peaks (WP-1543).
GAUSSIAN_VARIANCE_TO_FWHM_SQUARED = 8.0 * math.log(2.0)


def gaussian_fwhm(theta_deg: np.ndarray, u: float, v: float, w: float,
                  gauss_size: float = 0.0, gauss_strain: float = 0.0) -> np.ndarray:
    """Γ_G(θ) from the Caglioti law + sample Gaussian size/strain variances;
    input θ (NOT 2θ) in degrees."""
    xp = get_backend()
    th = xp.radians(theta_deg)
    t = xp.tan(th)
    g2 = (u + gauss_strain) * t * t + v * t + w
    # unconditional (purity (b)): gauss_size = 0 adds an exact ±0, and the
    # variance floor below absorbs any −0.0 sign flip
    c = xp.cos(th)
    g2 = g2 + gauss_size / (c * c)
    return xp.sqrt(xp.maximum(g2, _MIN_GAMMA_G2))


def lorentzian_negative_above(x_size: float, y_strain: float) -> float:
    """The 2θ (degrees) above which Γ_L = X/cosθ + Y·tanθ is negative.

    ``inf`` where it stays at or above zero below 2θ = 180°, and 0 where it is
    negative from the start.  X < 0 with Y > 0 also returns 0, although the
    width there is negative only *below* sinθ = −X/Y: a caller reads 0 as
    "refuse", which is right for a width negative anywhere on the axis.
    Γ_L·cosθ = X + Y·sinθ, and cosθ > 0 there, so
    with Y < 0 the width crosses zero at sinθ = −X/Y (Thompson, Cox &
    Hastings, 1987, J. Appl. Cryst. 20, 79, for the law).  For a reader
    checking a stated (X, Y) against the range it will be fitted on, since
    neither coefficient has to be non-negative on its own (WP-2002).
    """
    if y_strain >= 0.0:
        return math.inf if x_size >= 0.0 else 0.0
    if x_size <= 0.0:
        return 0.0
    s = -x_size / y_strain
    return math.inf if s >= 1.0 else 2.0 * math.degrees(math.asin(s))


def lorentzian_fwhm(theta_deg: np.ndarray, x_size: float, y_strain: float,
                    aniso_strain=0.0) -> np.ndarray:
    """Γ_L(θ) = x_size/cosθ + (y_strain + aniso_strain)·tanθ; θ in degrees.

    ``aniso_strain`` is Λ(hkl) from the Stephens anisotropic-strain model
    (:mod:`rietx.crystallography.stephens`) — a **per-reflection** array in
    the same deg-2θ FWHM units as ``y_strain``, which is why it enters the same
    tanθ slot rather than getting a law of its own.  It defaults to an exact
    ±0, so a phase without a microstrain block is bit-identical.
    """
    xp = get_backend()
    th = xp.radians(theta_deg)
    return x_size / xp.cos(th) + (y_strain + aniso_strain) * xp.tan(th)
