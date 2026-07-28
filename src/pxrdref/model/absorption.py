"""Cylindrical (capillary) absorption for Debye-Scherrer geometry.

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
    design = np.column_stack([np.ones_like(s), s])
    resid = g - design @ np.linalg.lstsq(design, g, rcond=None)[0]
    scale = np.linalg.norm(g)
    return float(np.linalg.norm(resid) / scale) if scale > 0.0 else 0.0
