"""Specimen absorption: cylindrical (capillary) and flat-plate geometries.

A powder in a capillary attenuates the beam along a path that is longest in
forward scattering and shortest toward backscatter, so measured intensities are
depressed at low angle relative to high.  The transmission coefficient is the
volume average of that attenuation (*International Tables* Vol. C, eq. 6.3.3.1),

    A = (1/V)·∫ exp(−µT) dV                                          (ITC 6.3.3.1)

with T the sum of the incident and diffracted path lengths; for a cylinder in
the equatorial plane it reduces to the two-dimensional integral ITC eq. (6.3.3.4)
and depends only on the dimensionless product µR and the Bragg angle.

Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* **A26**, 682-691, eq. (2),
fit that integral over 0 ≤ µR ≤ 1 to better than 0.0035 with

    A(µR, θ) = exp{ −(a₁ + b₁·sin²θ)·µR − (a₂ + b₂·sin²θ)·µR² }

    a₁ = 1.7133   b₁ = −0.0368   a₂ = −0.0927   b₂ = −0.3750

which is what this module implements.  ``µR = 0`` gives exactly ``A ≡ 1.0``.

**Convention, by physics rather than by letter.** ``A`` here is the
**transmission** coefficient, ≤ 1, which the forward model *multiplies* into
the calculated intensity.  Most tabulations — including ITC Table 6.3.3.2 —
print the *absorption correction* ``A* = 1/A ≥ 1`` instead (ITC eq. 6.3.3.2).
The Rouse table is one of the exceptions: it tabulates A directly, with a
µR = 0 row of 1.0000.  Getting this backwards inverts the θ-dependence, and
``A(0) = A*(0) = 1`` means an identity test cannot detect it — the direction of
the θ-dependence is what does (A *increases* with 2θ, because the mean path
through a cylinder shortens toward backscatter).

**b₂ = −0.3750, and it is worth knowing why this is asserted so loudly.** The
scan WP-0501 was written from prints it as "−0·0375", a digit transposition.
That error is invisible against the sin²θ = 0 column of the paper's own table,
which constrains only a₁ and a₂, and is small at low µR — but it is 0.0821
wrong at µR = 1.  What settles it is a quadrature of ITC eq. (6.3.3.4): with
−0.3750 the maximum error over the whole domain is 0.0035, exactly the bound
the paper claims for its fit.  Never validate this expression on a
constant-θ slice.

**What the correction is worth, and what it is not.** The expression factors
*exactly* into

    A = K(µR)·exp( +c(µR)·sin²θ ),      c(µR) = −(b₁·µR + b₂·µR²) > 0

— a constant times a Debye-Waller shape.  So applying it to a model with a free
phase scale and free displacement parameters is an **exact reparameterisation**:
the residual, and hence Rwp, is unchanged to machine precision.  Its entire
physical content is that the reported Biso must shift by

    ΔB = c(µR)·λ²/2                                (:func:`equivalent_delta_biso`)

which is 0.13 Å² at µR = 0.5 and 0.49 Å² at µR = 1.0 for Cu Kα.  Neglecting
capillary absorption therefore biases Biso *low* by that much.  This is why
``Geometry.mu_r`` is a plain float and not a refinable ``Parameter``: a free µR
would be an exactly singular direction in the normal equations, not merely a
correlated one.

The true physics is not exactly separable — eq. (2) only fits it to 0.0035.
Measured against the ITC quadrature, the part of A that a free {scale, Biso}
pair cannot absorb runs from 0.03 % of intensity at µR = 0.1 to 1.56 % at
µR = 1.0.  Eq. (2) models none of that residue, which is the honest limit of
what this module delivers.

Sphere coefficients (1.5108, −0.0315, −0.0951, −0.2898; max error 0.0024) are
given in the same paper and are deliberately **not** implemented: the specimen
shape here is a capillary.

Flat plate (WP-0508)
--------------------

*International Tables* Vol. C Table 6.3.3.1 gives three flat-specimen cases.
All three follow from the same eq. (6.3.3.1) volume average, and — unlike the
cylinder — each integrates in closed form, so nothing here is a *fit* and there
are no tabulated coefficients to transcribe wrongly:

    (1a) reflection, specimen thicker than the penetration depth
         A = 1/2µ                                  — no θ at all
    (2)  reflection, finite thickness t, planes parallel to the surface
         A = {1 − exp(−2µt·cosec θ)} / 2µ
    (3a) transmission, plate of thickness t, symmetric (φ = 0)
         A = t·sec θ·exp(−µt·sec θ)

Case (1a) is *identical* to the phase scale, not merely correlated: a column of
zeros.  It is not implemented, and neither is it needed — it is what this
package has always assumed.  GSAS-II returns 1.0 for its ``'Bragg'`` case for
the same reason.

Both implemented cases are normalised, and they take **opposite** answers about
what "off" means:

* :func:`flat_plate_reflection_absorption` divides by the thick limit 1/2µ,
  giving ``A = 1 − exp(−2µt/sin θ)`` → 1 as µt → ∞.  The identity is therefore
  an **infinitely thick** specimen, not µt = 0 — a plate of zero thickness
  diffracts nothing.  This is the reverse of every other correction in this
  package, where 0 is the identity, and it is why the field is optional
  (absent ⇒ thick ⇒ nothing applied) rather than defaulted to zero.
* :func:`flat_plate_transmission_absorption` has no thick limit (A → 0), so it
  is normalised at θ = 0: ``A = sec θ·exp(−µt·(sec θ − 1))``.  µt = 0 leaves
  ``sec θ``, which is **physics, not a leftover**: the beam's footprint on the
  tilted plate, hence the diffracting volume, grows as sec θ.  Selecting the
  geometry is what switches it on.

Derivations, since they are three lines each and pin the sin/cos that a reader
will otherwise have to trust.  Take an incident beam of cross-section S.

*(2)* the beam meets the surface at grazing angle θ, so the illuminated area is
S/sin θ and an element at depth z has total path 2z/sin θ:

    ∫₀ᵗ exp(−2µz/sin θ)·(S/sin θ) dz = (S/2µ)·{1 − exp(−2µt/sin θ)}

— the sin θ of the footprint cancelling against the sin θ of the penetration
depth is exactly why the *thick* case has no θ-dependence at all.

*(3a)* the plate normal bisects the incident and diffracted beams, so an element
at depth z has incident path z/cos θ and diffracted path (t − z)/cos θ: the
total is t/cos θ **independent of z**, and the footprint is S/cos θ:

    ∫₀ᵗ exp(−µt/cos θ)·(S/cos θ) dz = S·(t/cos θ)·exp(−µt/cos θ)

Direction of the bias, which is the whole point of applying either:

* case (2) depresses the **high**-angle intensity (deeper penetration at high θ
  runs out of specimen), so a Biso refined without it comes back too **large** —
  the opposite sign to the capillary;
* case (3a) raises the high angle while µt is small (the sec θ footprint) and
  depresses it once µt is large, so the sign of its bias flips with thickness.

:func:`equivalent_delta_biso_from_transmission` reports either, by projecting
ln A onto span{1, sin²θ} over the *reflection* positions — WP-0502's lesson that
a correction is judged where peaks are, not on the fitted grid.  Neither
flat-plate expression is exactly of that form (the cylinder's is), so it also
returns the fraction of ln A that is **not** absorbed, which is the part a fit
could in principle distinguish from a scale and a Biso.  Measured over ranges a
plate is really scanned on, that fraction is 0.2-1.3 % for transmission and a
few per cent for finite-thickness reflection — so µt, like µR, is a plain float
computed from the specimen and never refined.

The optimal transmission thickness falls out of the *unnormalised* (3a):
d/dt [t·exp(−µt·sec θ)] = 0 at µt = cos θ, i.e. **t = 1/µ** at θ = 0, one
absorption length.  That is a specimen-preparation number, reported by
:func:`optimal_transmission_thickness_mm`, and deliberately not part of the
fitted model — the normalisation above has already absorbed the overall t into
the phase scale.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend

#: Upper limit of the Rouse et al. (1970) fit.  Above this the expression is an
#: extrapolation, not a fit, so :mod:`pxrdref.refine` warns rather than
#: silently continuing.  Not a clamp — the arithmetic stays smooth across it so
#: nothing in the residual becomes discontinuous.
CYLINDER_MU_R_MAX = 1.0

# Rouse, Cooper, York & Chakera (1970) Acta Cryst. A26, 682, eq. (2), cylinder.
_A1 = 1.7133
_B1 = -0.0368
_A2 = -0.0927
_B2 = -0.3750


def _sin2_theta(xp, two_theta_deg):
    return xp.sin(0.5 * xp.radians(xp.asarray(two_theta_deg, dtype=np.float64))) ** 2


def cylinder_absorption(two_theta_deg: np.ndarray, mu_r: float) -> np.ndarray:
    """Transmission factor A(µR, θ) ≤ 1 per reflection.

    Forward-only path used inside ``CompiledModel.phase_peaks``; the intensity
    is multiplied by this.  ``mu_r = 0`` returns exactly 1.0 — ``exp(−0.0)`` is
    ``1.0`` bit-for-bit, which is what keeps a non-capillary model numerically
    untouched rather than merely close.
    """
    xp = get_backend()
    s = _sin2_theta(xp, two_theta_deg)
    return xp.exp(-(_A1 + _B1 * s) * mu_r - (_A2 + _B2 * s) * mu_r ** 2)


def cylinder_absorption_and_dmur(two_theta_deg: np.ndarray, mu_r: float
                                 ) -> tuple[np.ndarray, np.ndarray]:
    """(A, ∂A/∂µR).

    µR is not a refined parameter, so nothing in the Jacobian needs this; it
    exists for :func:`mu_r_identifiable_fraction` and to give the golden tests
    a derivative to pin.
    """
    xp = get_backend()
    s = _sin2_theta(xp, two_theta_deg)
    a = xp.exp(-(_A1 + _B1 * s) * mu_r - (_A2 + _B2 * s) * mu_r ** 2)
    return a, a * (-(_A1 + _B1 * s) - 2.0 * (_A2 + _B2 * s) * mu_r)


def equivalent_delta_biso(mu_r: float, wavelength: float) -> float:
    """Biso bias, in Å², incurred by *omitting* the correction.

    A = K·exp(+c·sin²θ) with c = −(b₁µR + b₂µR²), and the Debye-Waller factor
    is exp(−2B·sin²θ/λ²), so a fit with no absorption term reproduces the same
    calculated pattern with

        B_fitted = B_true − c·λ²/2

    i.e. capillary absorption neglected reads as displacement parameters that
    are too *small*.  Returned positive: add it to a Biso refined without the
    correction to recover the unbiased value.
    """
    c = -(_B1 * mu_r + _B2 * mu_r ** 2)
    return c * wavelength ** 2 / 2.0


def flat_plate_reflection_absorption(two_theta_deg: np.ndarray, mu_t: float
                                     ) -> np.ndarray:
    """ITC (2): finite-thickness reflection, normalised by the thick limit.

        A = 1 − exp(−2·µt/sin θ)

    ``mu_t`` is µ times the *specimen thickness* (dimensionless).  A → 1 as
    µt → ∞, which is the thick-specimen case this package assumes when no
    thickness is declared; the off state is therefore µt = ∞ (field absent),
    **not** µt = 0, which would be a specimen of no thickness at all.
    """
    xp = get_backend()
    theta = xp.radians(0.5 * xp.asarray(two_theta_deg, dtype=np.float64))
    return 1.0 - xp.exp(-2.0 * mu_t / xp.sin(theta))


def flat_plate_transmission_absorption(two_theta_deg: np.ndarray, mu_t: float
                                       ) -> np.ndarray:
    """ITC (3a): symmetric transmission, normalised at θ = 0.

        A = sec θ · exp(−µt·(sec θ − 1))

    ``mu_t`` is µ times the *plate thickness*.  The sec θ prefactor survives at
    µt = 0 on purpose — it is the growth of the illuminated volume as the plate
    tilts, not a normalisation residue — so this correction has no "off" state
    short of leaving the geometry.
    """
    xp = get_backend()
    theta = xp.radians(0.5 * xp.asarray(two_theta_deg, dtype=np.float64))
    sec = 1.0 / xp.cos(theta)
    return sec * xp.exp(-mu_t * (sec - 1.0))


def optimal_transmission_thickness_mm(mu_cm: float) -> float:
    """Plate thickness (mm) maximising diffracted intensity: t = 1/µ.

    From the *unnormalised* ITC (3a): d/dt[t·exp(−µt·sec θ)] = 0 at µt = cos θ,
    so t = 1/µ at θ = 0 and slightly less at higher angles — the classic "one
    absorption length" rule.  A specimen-preparation number, not a model
    parameter: the fitted expression divides the overall t out into the phase
    scale, so a plate at 3× the optimum fits exactly as well and just measures
    a third of the counts.
    """
    if mu_cm <= 0.0:
        raise ValueError(f"linear attenuation must be positive, got {mu_cm}")
    return 10.0 / mu_cm


def transmission_intensity_fraction(mu_t: float) -> float:
    """Counts from a plate at ``mu_t``, as a fraction of the best possible.

    The optimum above is at µt = 1, so **µt is itself the plate's thickness in
    units of the optimal one** and the whole comparison needs no length: from
    the unnormalised ITC (3a) at θ = 0, I ∝ µt·exp(−µt), maximal at µt = 1, so

        I/I_max = µt·exp(1 − µt)

    1.0 at the optimum, 0.7 at µt = 0.4 or 2, 0.15 at µt = 0.05 or 5.  Reported
    rather than acted on: a badly chosen thickness costs counting statistics,
    not accuracy, and the fit is equally good either way.
    """
    return float(mu_t * np.exp(1.0 - mu_t))


def equivalent_delta_biso_from_transmission(
        two_theta_deg: np.ndarray, transmission: np.ndarray, wavelength: float
        ) -> tuple[float, float]:
    """(ΔBiso, unabsorbed fraction) for an arbitrary transmission factor.

    The general form of :func:`equivalent_delta_biso`.  A free phase scale and a
    free isotropic displacement parameter span exactly ``{1, sin²θ}`` in the
    log-intensity, so least-squares projecting ``ln A`` onto that basis splits
    any intensity correction into the part a fit silently re-absorbs and the
    part it cannot.  With ``ln A ≈ const + β·sin²θ``,

        B_fitted = B_true − β·λ²/2        ⇒  ΔB = +β·λ²/2

    Returned **signed**: add it to a Biso refined without the correction to
    recover the unbiased value.  Positive for the cylinder (absorption
    neglected reads as too little thermal motion), negative for
    finite-thickness reflection, either sign for transmission depending on
    whether the sec θ footprint or the exponential dominates.

    ``two_theta_deg`` should be the **reflection positions**, not the fitted
    grid: a correction is only ever applied where there are peaks, and a grid
    that starts far below the first reflection reports a depression no modelled
    peak ever saw (WP-0502 measured that on real data).

    The second return value is ‖residual‖/‖ln A − mean‖ — how much of the
    correction's angular shape is *not* reproducible by {scale, Biso}.  Zero to
    rounding means the correction is an exact reparameterisation and cannot
    change the fit; the cylinder is that exact case.

    **Read the two returns together: the second bounds how far to trust the
    first.**  This projection is *unweighted*, while a refinement finds a
    weighted least-squares compromise, and the two coincide only insofar as the
    correction really is a {scale, Biso} direction.  Measured against synthetic
    refits (``tests/test_flat_plate.py``), ΔB is a **lower bound** on the bias a
    fit actually absorbs, by a factor that tracks the residue:

    ====================  =====  =====  =====
    µt (ITC case 2)       0.15   0.3    0.6
    unabsorbed fraction   0.263  0.201  0.080
    actual / predicted    ~1.5   ~1.3   ~1.06
    ====================  =====  =====  =====

    For the cylinder the residue is zero and the prediction is exact — measured
    to seven decimals on real 11-BM data.  For a flat plate, quote ΔB as "at
    least this much", with the residue beside it.
    """
    s = np.asarray(_sin2_theta(get_backend(), two_theta_deg), dtype=np.float64)
    ln_a = np.log(np.asarray(transmission, dtype=np.float64))
    finite = np.isfinite(s) & np.isfinite(ln_a)
    s, ln_a = s[finite], ln_a[finite]
    if s.size < 2:
        return 0.0, 0.0
    design = np.column_stack([np.ones_like(s), s])
    coeffs, *_ = np.linalg.lstsq(design, ln_a, rcond=None)
    resid = ln_a - design @ coeffs
    spread = float(np.linalg.norm(ln_a - ln_a.mean()))
    unabsorbed = float(np.linalg.norm(resid) / spread) if spread > 0.0 else 0.0
    return float(coeffs[1]) * wavelength ** 2 / 2.0, unabsorbed


def mu_r_identifiable_fraction(two_theta_deg: np.ndarray, mu_r: float) -> float:
    """Fraction of ∂lnA/∂µR that a free {scale, Biso} pair cannot absorb.

    Projects ∂lnA/∂µR over the given 2θ range onto span{1, sin²θ} — exactly the
    subspace a free phase scale and a free isotropic displacement parameter
    span — and returns the normalised norm of what is left.

    For the Rouse expression this is **identically zero to rounding**, because
    ∂lnA/∂µR = −(a₁ + 2a₂µR) − (b₁ + 2b₂µR)·sin²θ lies in that span by
    construction.  That is the point: the number is not a diagnostic threshold
    but a standing proof, exercised by the test suite, that µR carries no
    independent information in this model and must not be refined.

    It is public rather than test-local because the question generalises.  Any
    intensity correction with a smooth, monotone θ-dependence — surface
    roughness is the next one due (WP-0502) — risks being a reparameterised
    scale and Biso rather than new physics, and this is the measurement that
    settles it before a parameter is made refinable.  Pass the fit's own 2θ
    range: how much of a correction is identifiable depends on how much of it
    the pattern actually spans.
    """
    xp = get_backend()
    s = np.asarray(_sin2_theta(xp, two_theta_deg), dtype=np.float64)
    a, da = cylinder_absorption_and_dmur(two_theta_deg, mu_r)
    g = np.asarray(da, dtype=np.float64) / np.asarray(a, dtype=np.float64)
    return _identifiable_fraction(s, g)


def mu_t_identifiable_fraction(two_theta_deg: np.ndarray, mu_t: float,
                               geometry_kind: str) -> float:
    """The same measurement for a flat plate, where the answer is *not* zero.

    ∂lnA/∂µt for the two implemented cases:

        (2)  reflection    2/sin θ · exp(−k)/(1 − exp(−k)),  k = 2µt/sin θ
        (3a) transmission  −(sec θ − 1)                      — no µt at all

    so transmission's shape is an amplitude, and its identifiable fraction does
    not depend on µt.  Both are measured against the **normalised** A this
    module implements, which matters: the two expressions differ from their ITC
    forms by a θ-independent factor, i.e. by a multiple of the phase-scale
    direction, and that changes the denominator of this ratio without changing
    the numerator.  Read the number as "how much of this correction's angular
    signature survives a free scale and a free Biso", not as an esd.

    Measured over ranges a flat plate is really scanned on, it runs from a few
    per cent (transmission, and reflection at the µt where the correction
    actually bites) to tens of per cent (reflection at µt ≥ 2, where A is within
    1 % of 1 everywhere and there is nothing to identify).  That is why
    ``Geometry.mu_t`` is a plain float computed from the specimen rather than a
    refinable :class:`~pxrdref.schemas.common.Parameter` — the same conclusion
    as µR but for a weaker reason, so it is stated as a design choice backed by
    a measurement rather than as an identity.
    """
    xp = get_backend()
    s = np.asarray(_sin2_theta(xp, two_theta_deg), dtype=np.float64)
    theta = np.radians(0.5 * np.asarray(two_theta_deg, dtype=np.float64))
    if geometry_kind == "flat_plate_transmission":
        g = -(1.0 / np.cos(theta) - 1.0)
    else:
        k = 2.0 * mu_t / np.sin(theta)
        g = (2.0 / np.sin(theta)) * np.exp(-k) / (1.0 - np.exp(-k))
    return _identifiable_fraction(s, g)


def _identifiable_fraction(s: np.ndarray, g: np.ndarray) -> float:
    """‖g − proj_{span{1, s}} g‖ / ‖g‖, the shared core of the two above."""
    design = np.column_stack([np.ones_like(s), s])
    resid = g - design @ np.linalg.lstsq(design, g, rcond=None)[0]
    scale = np.linalg.norm(g)
    return float(np.linalg.norm(resid) / scale) if scale > 0.0 else 0.0
