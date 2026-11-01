"""The incident-spectrum vocabulary a time-of-flight instrument file declares.

GSAS normalises a TOF histogram as ``I_o = I′_o/(W·I_i)`` (Larson & Von Dreele
2004, LAUR 86-748, GSAS Technical Manual p. 127) and fits the incident spectrum
``I_i`` with one of five functions selected by ``ITYP`` (p. 128-129), whose
coefficients an instrument-parameter file writes in its ``ICOFF`` records.
**Their argument is the flight time in milliseconds** (p. 128-129, and again
p. 223 for the file), which is why :class:`rietx.schemas.instrument.IncidentSpectrum`
converts the fitted window to µs on the way in and keeps the coefficients as
written.

With T in ms and P₁…P_N the coefficients:

=====  ====================================================================  =====
ITYP   I_i                                                                    N
=====  ====================================================================  =====
0      1.0, no coefficients (p. 129)                                           0
1      P₁ + P₂e^{−P₃T} + P₄e^{−P₅T²} + P₆e^{−P₇T³} + P₈e^{−P₉T⁴}, P₁₀, P₁₁    11
2      as 1 with the second term (P₂/T⁵)e^{−P₃/T²}                            11
3      Σ_{j=1}^{12} P_j·T_{j−1}(X),  X = 2/T − 1  (Chebyshev, first kind)      12
4      P₁ + (P₂/T⁵)e^{−P₃/T²} + Σ_{j=4}^{12} P_j·T_{j−3}(X),  X = 2/T − 1      12
5      as 3 with X = T/10                                                     12
10     a point-by-point measured spectrum in a second file — refused            —
=====  ====================================================================  =====

The manual prints ITYP 1 and 2 with an ellipsis after the second pair; the
third and fourth pairs (powers T³, T⁴) are Von Dreele, Jorgensen & Windsor
(1982), *J. Appl. Cryst.* **15**, 581, eqs. (4) and (5), p. 583.  The fifth
pair's law is not printed anywhere, which is why the strict reader refuses a
non-zero one (:mod:`rietx.io.instrument_tof`).

**This module is the vocabulary, not the evaluator.**  This build reads a
spectrum losslessly and evaluates none: no time-of-flight forward model exists
here yet (yue-here/rietx issue #193), so what a file declares is carried on
the instrument and checked for consistency — a type the manual defines, and
exactly as many coefficients as it uses — and nothing more.
"""

from __future__ import annotations

#: The ITYP functions the manual defines (p. 128-129).
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
