import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rietx.background.estimators import arpls, snip, whittaker_solve
from rietx.background.models import chebyshev_background, chebyshev_design_matrix
from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from rietx.model.profiles.pseudovoigt import pseudo_voigt, tch_gamma_eta


@given(gg=st.floats(1e-3, 0.5), gl=st.floats(1e-6, 0.5))
@settings(max_examples=200, deadline=None)
def test_tch_eta_bounded_and_gamma_between(gg, gl):
    gamma, eta = tch_gamma_eta(np.array([gg]), np.array([gl]))
    assert 0.0 <= eta[0] <= 1.0001
    assert max(gg, gl) - 1e-12 <= gamma[0] <= gg + gl + 1e-12


@pytest.mark.parametrize("gg,gl", [(0.05, 0.0), (0.0, 0.05), (0.03, 0.02)])
def test_pseudo_voigt_normalized(gg, gl):
    gamma, eta = tch_gamma_eta(np.array([max(gg, 1e-9)]), np.array([gl]))
    x = np.linspace(-60 * gamma[0], 60 * gamma[0], 200001)
    area = np.trapezoid(pseudo_voigt(x, gamma[0], eta[0]), x)
    # Lorentzian tails converge slowly: 1% tolerance at ±60Γ is expected
    assert area == pytest.approx(1.0, abs=0.02)


def test_pure_gaussian_limit_fwhm():
    gamma, eta = tch_gamma_eta(np.array([0.1]), np.array([0.0]))
    assert eta[0] == pytest.approx(0.0, abs=1e-12)
    half = pseudo_voigt(np.array([0.05]), gamma[0], eta[0])
    peak = pseudo_voigt(np.array([0.0]), gamma[0], eta[0])
    assert half[0] / peak[0] == pytest.approx(0.5, rel=1e-9)  # FWHM definition


def test_caglioti_forms():
    theta = np.array([15.0])
    t = np.tan(np.radians(15.0))
    assert gaussian_fwhm(theta, 0.01, 0.002, 0.003)[0] == pytest.approx(
        np.sqrt(0.01 * t * t + 0.002 * t + 0.003))
    assert lorentzian_fwhm(theta, 0.01, 0.02)[0] == pytest.approx(
        0.01 / np.cos(np.radians(15.0)) + 0.02 * t)


def test_chebyshev_linearity_and_recursion():
    tt = np.linspace(5.0, 40.0, 300)
    T = chebyshev_design_matrix(tt, 5, tt[0], tt[-1])
    x = 2 * (tt - tt[0]) / (tt[-1] - tt[0]) - 1
    np.testing.assert_allclose(T[3], np.cos(3 * np.arccos(x)), atol=1e-10)
    c = np.array([10.0, -2.0, 0.7, 0.1, -0.05])
    y = chebyshev_background(tt, c, tt[0], tt[-1])
    np.testing.assert_allclose(y, c @ T, rtol=1e-14)


def test_whittaker_smooths():
    rng = np.random.default_rng(1)
    y = np.sin(np.linspace(0, 3, 500)) + rng.normal(0, 0.1, 500)
    z = whittaker_solve(y, np.ones(500), lam=1e4)
    assert np.std(np.diff(z, 2)) < np.std(np.diff(y, 2)) / 10


def test_the_whittaker_baseline_solves_its_defining_system():
    """Eilers (2003): z solves (W + λ DᵀD) z = W y, D the second difference.

    The banded solve against the dense system built from its definition, with
    unequal weights so W is not the identity.  The positive arm: the same z
    fails the system at λ moved by 1 %, so the bar can see a wrong penalty.
    """
    rng = np.random.default_rng(7)
    n = 200
    y = 100.0 + 20.0 * np.sin(np.linspace(0, 4, n)) + rng.normal(0, 2, n)
    w = rng.uniform(0.2, 1.0, n)
    lam = 3e3
    d2 = np.diff(np.eye(n), 2, axis=0)
    z = whittaker_solve(y, w, lam)

    def residual(lam_):
        a = np.diag(w) + lam_ * d2.T @ d2
        return np.max(np.abs(a @ z - w * y)) / np.max(np.abs(w * y))

    assert residual(lam) < 1e-9
    assert residual(lam * 1.01) > 1e-4


def test_arpls_recovers_baseline_under_peaks():
    tt = np.linspace(5, 45, 2000)
    true_bkg = 100.0 + 2.0 * tt - 0.02 * tt ** 2
    y = true_bkg.copy()
    for pos in (12.0, 21.0, 33.0):  # sharp peaks on top
        y += 5000.0 * np.exp(-0.5 * ((tt - pos) / 0.05) ** 2)
    est = arpls(y, lam=1e7)
    inter_peak = (np.abs(tt - 12) > 1) & (np.abs(tt - 21) > 1) & (np.abs(tt - 33) > 1)
    err = np.abs(est - true_bkg)[inter_peak]
    assert np.median(err) < 2.0  # within 2 counts of a ~140-count baseline
    # and the estimate must NOT ride up onto the peaks
    assert est[np.argmin(np.abs(tt - 21.0))] < true_bkg[np.argmin(np.abs(tt - 21.0))] + 50


def test_snip_stays_below_peaks():
    tt = np.linspace(5, 45, 2000)
    y = 50.0 + 3000.0 * np.exp(-0.5 * ((tt - 20) / 0.08) ** 2)
    est = snip(y, max_half_window=40)
    assert est[np.argmin(np.abs(tt - 20.0))] < 500.0
