"""Intensity corrections a time-of-flight bank needs: incident spectrum, Lorentz,
extinction, and the neutron µ(λ) its absorption correction is built from.

Each reflection's contribution is ``∝ K·F²·H(T − T_ph)`` with
``K = E·A·O·M·L/V`` (Larson & Von Dreele 2004, LAUR 86-748, GSAS Technical
Manual p. 133).  Three of those factors vary with wavelength inside one
histogram, which is what this module is for.

The incident spectrum — the one unit change in the track
---------------------------------------------------------
GSAS normalises a TOF histogram as ``I_o = I′_o/(W·I_i)`` (manual p. 127) and
fits ``I_i`` with one of five functions selected by ``ITYP`` (p. 128-129).
**Their argument is the flight time in milliseconds**, stated three times by
the manual (ITYP 1 and 2 on p. 128, ITYP 4 on p. 129) and again by the file
format (the ``ICOFF`` coefficients "are expressed in terms of TOF in
milliseconds", p. 223).  So the public door takes µs like every other function
in the track and **divides by 1000 exactly once**, at the top of
:func:`incident_intensity`; nothing else here sees a microsecond.

With T in ms and P₁…P_N the coefficients:

=====  ====================================================================  =====
ITYP   I_i                                                                    N
=====  ====================================================================  =====
0      1.0, no coefficients (p. 129)                                           0
1      P₁ + P₂e^{−P₃T} + P₄e^{−P₅T²} + P₆e^{−P₇T³} + P₈e^{−P₉T⁴} + P₁₀e^{−P₁₁T⁵}  11
2      as 1 with the second term (P₂/T⁵)e^{−P₃/T²}                            11
3      Σ_{j=1}^{12} P_j·T_{j−1}(X),  X = 2/T − 1  (Chebyshev, first kind)      12
4      P₁ + (P₂/T⁵)e^{−P₃/T²} + Σ_{j=4}^{12} P_j·T_{j−3}(X),  X = 2/T − 1      12
5      as 3 with X = T/10                                                     12
10     a point-by-point measured spectrum in a second file — refused            —
=====  ====================================================================  =====

The manual prints ITYP 1 and 2 with an ellipsis after the second pair; the
third and fourth pairs (powers T³, T⁴) are Von Dreele, Jorgensen & Windsor
(1982), *J. Appl. Cryst.* **15**, 581, eqs. (4) and (5), p. 583, whose
nine-coefficient series the GSAS forms extend.  The **fifth pair, P₁₀ and
P₁₁, is ``P₁₀·exp(−P₁₁·T⁵)``, established by conformance rather than read**:
the printed series (the manual's p. 128 with VD82's eqs. 4-5) is a ladder of
exponents 1, 2, 3, 4 for the second to fifth terms and stops there, so the
sixth term's exponent was measured — 5.000000 (rms 2e-13, the rms doubling at
Δk ≈ 1.5e-15) against the incident spectrum GSAS-II 5.8.2 computes, run as a
black box on 2026-09-23 on synthetic coefficient sets (P₁₁ = 1e-5, 1e-3, 0.1;
ITYP 1 and 2).  No source was read: the oracle's output is the only evidence,
and the law it pins is the next rung of the printed ladder.  The strict
``.iparm`` reader still refuses a non-zero fifth pair, because the manual it
holds to prints no exponent (:mod:`rietx.io.instrument_tof`).  ITYP 4's Chebyshev part is
"part of the Chebyschev polynomial used for TYPE 3" (p. 128), i.e. the same
X = 2/T − 1.  The Chebyshev basis is the three-term recurrence
T₀ = 1, T₁ = X, T_{n+1} = 2X·T_n − T_{n−1} (Abramowitz & Stegun ch. 22, which
the manual cites for its Table 22.3 coefficients).

The Lorentz factor and Sabine extinction
----------------------------------------
``L = d⁴·sin Θ`` for TOF neutrons (manual p. 140): Θ is the bank's fixed
Bragg angle, so only d⁴ varies across a histogram, and there is no
polarisation factor for neutrons.  Sabine's primary-extinction formalism as
tested on TOF data by Sabine, Von Dreele & Jørgensen (1988), *Acta Cryst.*
**A44**, 374-379, eqs. (1)-(7), p. 375, with the refinable parameter the
manual's ``E_x`` in µm² (p. 133), which is (K·D)² for a block of edge D.

µ(λ) for the absorption correction
----------------------------------
``µ(λ) = Σ nᵢ[σ_abs,i·λ/λ₀ + σ_coh,i + σ_inc,i] / V`` — absorption follows the
1/v law and scattering does not, so µ is affine in λ.  λ₀ = 1.798 Å, the
2200 m/s wavelength at which Sears (1992), *Neutron News* **3**(3), 26-37,
tabulates σ_abs.  With σ in barn and V in Å³ the ratio is cm⁻¹ directly.
"""

from __future__ import annotations

import math

import numpy as np

from ..backend import get_backend
from ..crystallography.neutron import properties

#: The ITYP functions the manual defines and this module evaluates (p. 128-129).
SPECTRUM_TYPES: dict[int, str] = {
    0: "none: I_i = 1.0 for all points",
    1: "a constant plus five exponentials in powers of T (ms)",
    2: "as ITYP 1 with a Maxwellian second term (P2/T^5)·exp(-P3/T^2)",
    3: "a 12-term Chebyshev series in X = 2/T - 1",
    4: "a constant, a Maxwellian, and a 9-term Chebyshev series in X = 2/T - 1",
    5: "a 12-term Chebyshev series in X = T/10",
}

#: How many coefficients each ITYP uses (manual p. 128-129: "a maximum of 11"
#: for 1 and 2, "a maximum of 12" for 3-5).  The file's ICOFF block always has
#: twelve slots; a type using eleven leaves the twelfth unread.
COEFFICIENT_COUNTS: dict[int, int] = {0: 0, 1: 11, 2: 11, 3: 12, 4: 12, 5: 12}

#: The ITYP that exists and is refused for its own reason (manual p. 129, 222).
POINT_BY_POINT_ITYP = 10

#: Å — the 2200 m/s thermal wavelength at which σ_abs is tabulated (Sears 1992).
THERMAL_WAVELENGTH = 1.798

#: µs per ms: the one conversion at the incident-spectrum door.
_US_PER_MS = 1000.0


def _coefficient_count(itype: int) -> int:
    """How many coefficients ITYP ``itype`` uses, or a refusal by number.

    The one place a type is validated, and both validators call it — the
    schema's (:class:`rietx.schemas.instrument.IncidentSpectrum`) and the
    ``.iparm`` reader's.  :data:`SPECTRUM_TYPES` decides whether the manual
    defines the function at all; :data:`COEFFICIENT_COUNTS` answers only how
    many numbers a defined one takes.  Asking the count table whether a type
    exists left ``SPECTRUM_TYPES`` read by nothing, the two tables free to
    drift apart with no test going red (WP-2032).
    """
    if itype not in SPECTRUM_TYPES:
        raise ValueError(_unknown_type_message(itype))
    return COEFFICIENT_COUNTS[itype]


def _unknown_type_message(itype: int) -> str:
    if itype == POINT_BY_POINT_ITYP:
        return (f"ITYP {POINT_BY_POINT_ITYP} is a point-by-point measured "
                f"incident spectrum read from the file the MFIL record names "
                f"(GSAS Technical Manual p. 129, 222): it has no coefficients, "
                f"and a point-by-point spectrum must be supplied as data on the "
                f"pattern's own channels, not as coefficients")
    defined = ", ".join(str(t) for t in sorted(SPECTRUM_TYPES))
    return (f"ITYP {itype} is not an incident-spectrum function the GSAS "
            f"Technical Manual defines (p. 128-129 define {defined}, and "
            f"{POINT_BY_POINT_ITYP} for a point-by-point file); refused by "
            f"number rather than read as 'no spectrum'")


def _type_zero_message(n: int) -> str:
    return (f"ITYP 0 takes no coefficients (I_i = 1.0, GSAS Technical Manual "
            f"p. 129); {n} were given")


def _count_message(itype: int, want: int, got: int) -> str:
    return (f"ITYP {itype} uses {want} coefficients and {got} were given; a "
            f"list of the wrong length is refused rather than padded or "
            f"truncated")


def _chebyshev_sum(x, coeffs):
    """Σ cₙ·Tₙ(x) by the three-term recurrence (A&S ch. 22)."""
    t_prev = x * 0.0 + 1.0
    total = coeffs[0] * t_prev
    if len(coeffs) == 1:
        return total
    t_cur = x
    total = total + coeffs[1] * t_cur
    for c in coeffs[2:]:
        t_prev, t_cur = t_cur, 2.0 * x * t_cur - t_prev
        total = total + c * t_cur
    return total


def _evaluate(itype: int, coeffs, tof_us):
    """I_i for a validated type and exactly its own coefficient count."""
    xp = get_backend()
    t = xp.asarray(tof_us, dtype=np.float64) / _US_PER_MS
    p = list(coeffs)
    if itype in (1, 2):
        if itype == 1:
            second = p[1] * xp.exp(-p[2] * t)
        else:
            second = p[1] / t ** 5 * xp.exp(-p[2] / t ** 2)
        rest = (p[3] * xp.exp(-p[4] * t ** 2) + p[5] * xp.exp(-p[6] * t ** 3)
                + p[7] * xp.exp(-p[8] * t ** 4) + p[9] * xp.exp(-p[10] * t ** 5))
        return p[0] + second + rest
    if itype == 3:
        return _chebyshev_sum(2.0 / t - 1.0, p)
    if itype == 4:
        maxwellian = p[1] / t ** 5 * xp.exp(-p[2] / t ** 2)
        return p[0] + maxwellian + _chebyshev_sum(2.0 / t - 1.0, [0.0] + p[3:])
    # itype == 5
    return _chebyshev_sum(t / 10.0, p)


def incident_spectrum(itype: int, coefficients, tof_us):
    """I_i at flight times ``tof_us`` (µs) for ITYP ``itype`` — the caller's door.

    ``coefficients`` holds exactly :data:`COEFFICIENT_COUNTS` ``[itype]``
    values, P₁ first; a different count is refused, never padded.  ITYP 0
    returns ``1.0`` and refuses any coefficient; ITYP 10 and any type the
    manual does not define are refused by name.  The ms conversion happens
    here, once.  See the module docstring for the functions.
    """
    want = _coefficient_count(int(itype))
    coeffs = list(coefficients)
    if want == 0:
        if coeffs:
            raise ValueError(_type_zero_message(len(coeffs)))
        return 1.0
    if len(coeffs) != want:
        raise ValueError(_count_message(itype, want, len(coeffs)))
    return _evaluate(int(itype), coeffs, tof_us)


def incident_intensity(tof_us, ityp: int, coeffs):
    """I_i at ``tof_us`` (µs) from a GSAS ``ICOFF`` coefficient block.

    ``coeffs`` is the block as a file holds it — up to twelve values, P₁
    first; slots the type does not use must be zero (trailing zeros allowed,
    a non-zero unused slot refused).  ``ityp = 0`` returns exactly ``1.0``;
    ``ityp = 10`` is refused by name (a point-by-point spectrum is data, not
    coefficients); a value outside the documented set is refused by value.
    Flight time is divided by 1000 exactly once, so 1000 µs is T = 1 ms.
    """
    want = _coefficient_count(int(ityp))
    block = list(coeffs)
    if len(block) > 12:
        raise ValueError(f"an ICOFF block has twelve slots (GSAS Technical "
                         f"Manual p. 223); {len(block)} were given")
    for k in range(want, len(block)):
        c = block[k]
        if isinstance(c, (int, float, np.generic)) and float(c) != 0.0:
            raise ValueError(
                f"ITYP {ityp} uses {want} coefficients, and slot P{k + 1} = "
                f"{float(c)!r} is non-zero: a number in a slot the declared "
                f"function does not read is refused")
    if want == 0:
        return 1.0
    if len(block) < want:
        raise ValueError(_count_message(ityp, want, len(block)))
    return _evaluate(int(ityp), block[:want], tof_us)


def moderator_temperature(p3, difc, two_theta_deg):
    """The manual's effective moderator temperature ``2.374e-4·C²/(P₃·sin 2Θ)``.

    GSAS Technical Manual p. 128, for ITYP 2 and 4, with C = DIFC and 2Θ the
    bank's scattering angle in degrees.  A diagnostic, not part of the forward
    model: "usually 10-20K higher than the real temperature when the intensity
    data has not been corrected for absorption or detector efficiency".
    """
    return 2.374e-4 * difc * difc / (p3 * math.sin(math.radians(two_theta_deg)))


# ---------------------------------------------------------------------------
# Lorentz factor and extinction
# ---------------------------------------------------------------------------
def tof_lorentz(d, theta_deg):
    """The TOF-neutron Lorentz factor ``d⁴·sin Θ`` (GSAS Technical Manual p. 140).

    ``theta_deg`` is the bank's Bragg angle Θ (half the scattering angle) in
    **degrees**, like every angle in the package — a per-bank constant, so
    only d⁴ varies with reflection.  No polarisation factor: neutrons have
    none.  (The specification, § 10, wrote this signature in radians; degrees
    is a deliberate departure to keep the package's one angle convention.)
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    th = xp.asarray(theta_deg, dtype=np.float64) * (math.pi / 180.0)
    return dd ** 4 * xp.sin(th)


#: E_L at x = 1 from each side (S88 eqs. 3 and 4), for the record: the
#: published formulas step there by ~2.2 %, and it is not smoothed here.
SABINE_LAUE_SERIES_AT_1 = 1.0 - 0.5 + 0.25 - 5.0 / 48.0 + 7.0 / 192.0
SABINE_LAUE_ASYMPTOTE_AT_1 = math.sqrt(2.0 / math.pi) * (
    1.0 - 1.0 / 8.0 - 3.0 / 128.0 - 15.0 / 1024.0)


def sabine_extinction(x, theta_deg):
    """Sabine's extinction factor ``E = E_L·cos²θ + E_B·sin²θ`` (S88 eqs. 2-5).

    Sabine, Von Dreele & Jørgensen (1988), *Acta Cryst.* **A44**, 374-379,
    p. 375:

        E_L = 1 − x/2 + x²/4 − 5x³/48 + 7x⁴/192                       x ≤ 1
        E_L = (2/(πx))^{1/2}·[1 − 1/(8x) − 3/(128x²) − 15/(1024x³)]    x > 1
        E_B = (1 + x)^{−1/2}

    ``theta_deg`` is the Bragg angle θ in **degrees** (2θ the scattering
    angle), like every angle in the package; the specification (§ 10) wrote
    radians, and degrees is a deliberate departure from it.
    The Laue branch is discontinuous at x = 1 by ~2.2 % (0.68229 against
    0.66774) — in the published formulas, kept as published; a refinement
    that wanders across x = 1 will see the step.  Both branches are evaluated
    on clamped arguments before the ``where``.
    """
    xp = get_backend()
    xv = xp.asarray(x, dtype=np.float64)
    x1 = xp.minimum(xv, 1.0)
    laue_series = (1.0 - x1 / 2.0 + x1 ** 2 / 4.0 - 5.0 * x1 ** 3 / 48.0
                   + 7.0 * x1 ** 4 / 192.0)
    r = 1.0 / xp.maximum(xv, 1.0)          # in powers of 1/x: nothing overflows
    laue_asym = xp.sqrt((2.0 / math.pi) * r) * (
        1.0 - r / 8.0 - 3.0 * r * r / 128.0 - 15.0 * r * r * r / 1024.0)
    e_l = xp.where(xv <= 1.0, laue_series, laue_asym)
    e_b = 1.0 / xp.sqrt(1.0 + xp.maximum(xv, 0.0))
    th = xp.asarray(theta_deg, dtype=np.float64) * (math.pi / 180.0)
    return e_l * xp.cos(th) ** 2 + e_b * xp.sin(th) ** 2


def sabine_x(ext_um2, lam, fcalc, volume):
    """Sabine's extinction variable ``x = E_x·(λF/V)²`` (manual p. 133; S88 eq. 6).

    S88's ``x = (K·N_c·λ·F·D)²`` with N_c = 1/V is the manual's form with
    ``E_x = (K·D)²``, the refinable parameter, in µm².  x is dimensionless
    once every length is in one unit; here ``ext_um2`` is in µm², ``lam`` in
    Å, ``fcalc`` the structure factor per cell as a **length in fm** (neutron
    scattering lengths are tabulated in fm) and ``volume`` in Å³, so
    ``x = ext_um2·10⁸ · (lam·fcalc·10⁻⁵/volume)²``.
    """
    return ext_um2 * 1.0e8 * (lam * fcalc * 1.0e-5 / volume) ** 2


# ---------------------------------------------------------------------------
# µ(λ) for the specimen absorption correction
# ---------------------------------------------------------------------------
def neutron_attenuation_terms(counts: dict[str, float], volume: float
                              ) -> tuple[float, float]:
    """``(a, b)`` in cm⁻¹·Å⁻¹ and cm⁻¹ with **µ(λ) = a·λ + b** for one phase.

    ``counts`` maps a species label to its number per cell (occupancy ×
    multiplicity), ``volume`` is the cell volume in Å³.  Isotopes keep their
    own rows (``crystallography.neutron.properties``).
    ``a = Σ n·σ_abs/(λ₀·V)``, ``b = Σ n·(σ_coh + σ_inc)/V`` with σ in barn,
    λ₀ = :data:`THERMAL_WAVELENGTH` (Sears 1992).  A species the table lacks,
    or whose cross-section it records as missing, raises :class:`KeyError`
    naming it.
    """
    if not volume > 0.0:
        raise ValueError(f"neutron_attenuation_terms(): the cell volume must "
                         f"be positive, got {volume}")
    absorb = 0.0
    scatter = 0.0
    for species, n in counts.items():
        row = properties(species)
        xs = (row["xs_abs_barn"], row["xs_coh_barn"], row["xs_inc_barn"])
        if not all(np.isfinite(v) for v in xs):
            raise KeyError(f"a neutron cross-section for {species!r} is not "
                           f"tabulated in Sears (1992)")
        absorb += n * xs[0]
        scatter += n * (xs[1] + xs[2])
    return absorb / (THERMAL_WAVELENGTH * volume), scatter / volume


def neutron_linear_attenuation(counts: dict[str, float], volume: float,
                               wavelength):
    """µ(λ) in cm⁻¹ at ``wavelength`` (Å): :func:`neutron_attenuation_terms`' line."""
    a, b = neutron_attenuation_terms(counts, volume)
    return a * wavelength + b
