"""Flat-plate absorption, ITC Vol. C Table 6.3.3.1 cases (2) and (3a) — WP-0508.

The validation strategy is WP-0501's lesson applied where it is cheap: an
absorption expression is checked against **the integral it comes from**, spanning
*both* its arguments, never against another code's transcription.  WP-0501's b₂
coefficient was printed with two digits transposed in the available scan of the
source, and that error was invisible against a constant-θ slice of the paper's
own table.  Here the two expressions are closed-form integrals rather than fits,
so a direct quadrature of the defining path-length integral is an independent
check with no shared constants at all.
"""

import numpy as np
import pytest

from pxrdref.model.absorption import (
    cylinder_absorption,
    equivalent_delta_biso,
    equivalent_delta_biso_from_transmission,
    flat_plate_reflection_absorption,
    flat_plate_transmission_absorption,
    mu_t_identifiable_fraction,
    optimal_transmission_thickness_mm,
)

TWO_THETA = np.linspace(5.0, 140.0, 271)


def _quadrature_reflection(two_theta_deg: np.ndarray, mu_t: float) -> np.ndarray:
    """ITC (2) by adaptive quadrature of the volume integral, normalised.

    A beam of unit cross-section meets the surface at grazing angle θ: the
    illuminated area is 1/sin θ and an element at depth z has total in+out path
    2z/sin θ.  Integrating exp(−µ·T) over the illuminated volume and dividing by
    the thick-specimen limit 1/2µ is the whole derivation, and it shares no
    constant with the implementation.  Written with µ = 1, so z runs over µt.

    ``quad`` rather than a fixed grid on purpose: at low θ the integrand decays
    over a depth ~sin θ/2, so a uniform rule needs absurd resolution to reach
    the 1e-9 this test wants — a trapezoid at 2e5 points is only good to 1e-7
    and, being convex-side, reports A > 1, which would look like a bug in the
    implementation rather than in the check.
    """
    from scipy.integrate import quad
    theta = np.radians(0.5 * np.asarray(two_theta_deg, dtype=np.float64))
    out = np.empty_like(theta)
    for i, th in enumerate(theta):
        val, _err = quad(lambda z, s=np.sin(th): np.exp(-2.0 * z / s) / s,
                         0.0, mu_t, epsabs=1e-14, epsrel=1e-14, limit=200)
        out[i] = val / 0.5                              # ÷ thick limit 1/2µ
    return out


def _quadrature_transmission(two_theta_deg: np.ndarray, mu_t: float) -> np.ndarray:
    """ITC (3a) by adaptive quadrature, normalised at θ = 0.

    The plate normal bisects the beams, so an element at depth z has incident
    path z/cos θ and diffracted path (t − z)/cos θ — a total independent of z —
    over a footprint 1/cos θ.  The z-integral is therefore trivial, which is the
    point: it is a *different* computation from the closed form even though it
    lands on the same number.
    """
    from scipy.integrate import quad
    theta = np.radians(0.5 * np.asarray(two_theta_deg, dtype=np.float64))
    out = np.empty_like(theta)
    for i, th in enumerate(theta):
        c = np.cos(th)
        val, _err = quad(lambda z, c=c: np.exp(-(z + (mu_t - z)) / c) / c,
                         0.0, mu_t, epsabs=1e-13, epsrel=1e-13, limit=200)
        out[i] = val
    return out / (mu_t * np.exp(-mu_t))                 # ÷ the θ = 0 value


@pytest.mark.parametrize("mu_t", [0.05, 0.2, 0.5, 1.0, 2.0, 5.0])
def test_reflection_matches_the_defining_integral(mu_t):
    got = np.asarray(flat_plate_reflection_absorption(TWO_THETA, mu_t))
    want = _quadrature_reflection(TWO_THETA, mu_t)
    assert np.max(np.abs(got - want)) < 1e-9, np.max(np.abs(got - want))


@pytest.mark.parametrize("mu_t", [0.2, 1.0, 3.0])
def test_transmission_matches_the_defining_integral(mu_t):
    got = np.asarray(flat_plate_transmission_absorption(TWO_THETA, mu_t))
    want = _quadrature_transmission(TWO_THETA, mu_t)
    assert np.max(np.abs(got - want)) < 1e-9, np.max(np.abs(got - want))


def test_reflection_is_the_identity_in_the_thick_limit():
    """(2) → 1 as µt → ∞: the continuity check with the case this package
    already assumes (ITC (1a), A = 1/2µ, no θ)."""
    for mu_t, tol in [(3.0, 1e-2), (5.0, 1e-4), (10.0, 1e-8), (25.0, 1e-20)]:
        a = np.asarray(flat_plate_reflection_absorption(TWO_THETA, mu_t))
        assert np.all(a <= 1.0)
        assert np.max(1.0 - a) < tol, (mu_t, np.max(1.0 - a))


def test_reflection_depresses_the_high_angle_and_transmission_the_low():
    """The two cases lean opposite ways, which is what makes their Biso biases
    opposite in sign.  Getting either backwards (the A vs A* = 1/A trap) would
    invert the θ-dependence, and an identity test cannot see that."""
    a_refl = np.asarray(flat_plate_reflection_absorption(TWO_THETA, 0.3))
    assert np.all(np.diff(a_refl) < 0.0), "finite-thickness reflection must fall with 2θ"

    a_trans = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 0.1))
    assert np.all(np.diff(a_trans) > 0.0), "a thin transmission plate must rise with 2θ"
    # …and turn over once absorption beats the sec θ footprint growth
    thick = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 3.0))
    assert np.all(np.diff(thick) < 0.0)


def test_transmission_is_pure_footprint_at_zero_absorption():
    """µt = 0 leaves sec θ, and that is physics: the beam's footprint on a
    tilted plate grows as sec θ, so the diffracting volume does too."""
    a = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 0.0))
    theta = np.radians(0.5 * TWO_THETA)
    assert np.allclose(a, 1.0 / np.cos(theta), rtol=0.0, atol=1e-15)


def test_optimal_thickness_maximises_the_unnormalised_intensity():
    """t = 1/µ, checked by brute force on the ITC (3a) expression itself."""
    mu_cm = 250.0
    t_opt = optimal_transmission_thickness_mm(mu_cm)
    assert t_opt == pytest.approx(10.0 / mu_cm)
    grid = np.linspace(0.1 * t_opt, 4.0 * t_opt, 20_001)          # mm
    intensity = grid * np.exp(-mu_cm / 10.0 * grid)               # θ = 0, sec = 1
    assert grid[int(np.argmax(intensity))] == pytest.approx(t_opt, rel=1e-3)


def test_projected_delta_biso_reproduces_the_cylinder_closed_form():
    """The general projection and WP-0501's closed form must agree exactly.

    ln A for the Rouse cylinder is *exactly* affine in sin²θ, so the
    least-squares projection has zero residual and its slope is the analytic c.
    This is the test that ties the flat-plate ΔBiso — which has no closed form —
    to a case whose answer is known independently.
    """
    for mu_r in (0.1, 0.5, 1.0):
        a = np.asarray(cylinder_absorption(TWO_THETA, mu_r))
        delta, unabsorbed = equivalent_delta_biso_from_transmission(
            TWO_THETA, a, 1.5406)
        assert delta == pytest.approx(equivalent_delta_biso(mu_r, 1.5406), rel=1e-12)
        assert unabsorbed < 1e-12, "the cylinder must be exactly reparameterisable"


def test_flat_plate_delta_biso_has_the_right_sign_and_is_large():
    """Both biases, and the fact that they are an order of magnitude larger than
    the capillary's — which is what makes flat-plate absorption worth having
    even though its geometry is the one people call 'thick'."""
    for mu_t in (0.2, 0.5):
        a = np.asarray(flat_plate_reflection_absorption(TWO_THETA, mu_t))
        delta, unabsorbed = equivalent_delta_biso_from_transmission(
            TWO_THETA, a, 1.5406)
        # a thin plate loses high-angle intensity ⇒ Biso refined without the
        # correction comes back too *large* ⇒ the recovery is negative
        assert delta < 0.0
        assert abs(delta) > 0.5, f"µt={mu_t} bias {delta:.3f} Å² unexpectedly small"
        # unlike the cylinder, part of it is genuinely not a scale × Biso
        assert unabsorbed > 0.01

    a = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 0.2))
    delta, _ = equivalent_delta_biso_from_transmission(TWO_THETA, a, 1.5406)
    assert delta > 0.0, "a thin transmission plate biases Biso the other way"


def test_mu_t_identifiability_is_small_but_not_zero():
    """The measurement behind ``Geometry.mu_t`` being a plain float.

    Unlike µR — whose derivative lies *identically* in span{1, sin²θ}, so
    refining it would be an exactly singular direction — a flat-plate µt keeps a
    few per cent to tens of per cent of its signature.  The design choice is
    therefore backed by a measurement plus the argument that µt is knowable from
    the specimen, not by an identity; this test pins the measurement so a future
    session revisiting the choice starts from numbers.
    """
    tt = np.linspace(10.0, 90.0, 400)
    transmission = mu_t_identifiable_fraction(tt, 0.3, "flat_plate_transmission")
    assert 0.01 < transmission < 0.15, transmission
    # transmission's ∂lnA/∂µt is an amplitude: the fraction cannot depend on µt
    assert mu_t_identifiable_fraction(tt, 3.0, "flat_plate_transmission") == \
        pytest.approx(transmission, rel=1e-12)

    for mu_t in (0.1, 0.3, 1.0):
        assert 0.01 < mu_t_identifiable_fraction(tt, mu_t, "bragg_brentano") < 0.4

    # and the µR comparison that motivates the whole distinction
    from pxrdref.model.absorption import mu_r_identifiable_fraction
    assert mu_r_identifiable_fraction(tt, 0.5) < 1e-12
