"""WP-0405 — the opt-in true-Voigt profile and its shared Faddeeva w(z).

Covers the algorithm accuracy (Weideman N=32 vs ``scipy.special.wofz``), the
unit-area normalization, the exact Gaussian (γ→0) and Lorentzian (σ→0) limits,
cross-backend agreement of w(z) *and* the forward model, the analytic
∂V/∂(σ,γ) partials vs finite differences, and — the integration that matters —
the full peak-chain analytic Jacobian and FCJ composition under ``shape =
"voigt"``.  Every claim is checked against an independent reference; the
end-to-end refinement writes obs/calc/diff PNGs to ``tests/output/``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.model.profiles.faddeeva import WEIDEMAN_N, faddeeva_w
from pxrdref.model.profiles.pseudovoigt import pseudo_voigt
from pxrdref.model.profiles.voigt import (
    GAUSS_FWHM_TO_SIGMA,
    fwhm_to_voigt_params,
    voigt,
    voigt_derivs,
)
from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
from pxrdref.params.vector import ParameterTable

OUT = Path(__file__).parent / "output"


def _wide_grid() -> np.ndarray:
    """A dense core plus far coarse tails, so the slowly-decaying Lorentzian
    wing is captured well enough to test the *analytic* unit-area constant to
    <1e-6 (a bare ±30·FWHM window truncates ~2 %, shared with the pV)."""
    core = np.linspace(-200.0, 200.0, 4_000_001)
    tail = np.linspace(200.0, 2e5, 2_000_001)
    return np.unique(np.concatenate([-tail[::-1], core, tail]))


# ----------------------------------------------------------------------
# w(z): the shared Faddeeva
# ----------------------------------------------------------------------
def test_faddeeva_matches_scipy_over_upper_half_plane():
    """Weideman N=32 reproduces the complex error function to ~fp64 over the
    upper half-plane (Im z ≥ 0 — the only region the Voigt argument visits)."""
    wofz = pytest.importorskip("scipy.special").wofz
    assert WEIDEMAN_N == 32
    rng = np.random.default_rng(0)
    z = rng.uniform(-60, 60, 40_000) + 1j * rng.uniform(0.0, 60.0, 40_000)
    err = np.abs(faddeeva_w(z) - wofz(z))
    assert err.max() < 1e-12
    # on and near the real axis (the γ→0 Gaussian edge) and far out (σ→0)
    edge = np.linspace(-15, 15, 4001) + 0j
    assert np.abs(faddeeva_w(edge) - wofz(edge)).max() < 1e-12
    far = np.linspace(-1e4, 1e4, 4001) + 1j * 50.0
    assert np.abs(faddeeva_w(far) - wofz(far)).max() < 1e-12


def test_faddeeva_cross_backend_identical():
    """numpy and jax evaluate the *same* w(z) to <1e-12 in fp64 — the whole
    reason WP-0405 refuses each backend's native ``wofz``."""
    pytest.importorskip("jax")
    import jax.numpy as jnp

    from pxrdref.backend.jax_backend import _enable_x64

    rng = np.random.default_rng(1)
    z = rng.uniform(-40, 40, 5_000) + 1j * rng.uniform(0.0, 40.0, 5_000)
    w_np = faddeeva_w(z)
    with _enable_x64():
        w_jax = np.asarray(faddeeva_w(jnp.asarray(z)))
    assert w_jax.dtype == np.complex128
    assert np.abs(w_np - w_jax).max() < 1e-12


# ----------------------------------------------------------------------
# the profile: normalization + exact limits
# ----------------------------------------------------------------------
@pytest.mark.parametrize("gam_g,gam_l", [(0.10, 0.0), (0.10, 0.05),
                                         (0.05, 0.10), (0.06, 0.04),
                                         (0.20, 0.20)])
def test_voigt_unit_area(gam_g, gam_l):
    sigma, gamma = (float(v) for v in fwhm_to_voigt_params(np.array(gam_g),
                                                           np.array(gam_l)))
    x = _wide_grid()
    area = np.trapezoid(voigt(x, sigma, gamma), x)
    assert abs(area - 1.0) < 1e-6


def test_voigt_gaussian_limit_is_exact_gaussian():
    """γ_L → 0: the Voigt collapses to the unit Gaussian of the same FWHM —
    identical to the pseudo-Voigt's Gaussian component."""
    gam_g = 0.1
    sigma = gam_g / GAUSS_FWHM_TO_SIGMA
    x = np.linspace(-1.0, 1.0, 2001)
    v = voigt(x, sigma, 0.0)
    gauss = pseudo_voigt(x, gam_g, 0.0)   # η = 0 → pure Gaussian, FWHM γ_G
    assert np.abs(v - gauss).max() < 1e-8
    # and it is a true FWHM: half-max at ±γ_G/2
    peak = float(voigt(np.array([0.0]), sigma, 0.0)[0])
    half = float(voigt(np.array([gam_g / 2.0]), sigma, 0.0)[0])
    assert half / peak == pytest.approx(0.5, rel=1e-9)


def test_voigt_lorentzian_limit_is_exact_lorentzian():
    """σ → 0: the Voigt collapses to the unit Lorentzian of FWHM Γ_L = 2γ."""
    gam_l = 0.1
    gamma = gam_l / 2.0
    sigma = 1e-6                        # σ ≪ γ; error is O(σ)
    x = np.linspace(-1.0, 1.0, 2001)
    v = voigt(x, sigma, gamma)
    lorentz = (1.0 / np.pi) * gamma / (x**2 + gamma**2)
    assert np.abs(v - lorentz).max() < 1e-8


# ----------------------------------------------------------------------
# analytic derivatives
# ----------------------------------------------------------------------
def test_voigt_analytic_derivs_match_fd():
    """∂V/∂x, ∂V/∂σ, ∂V/∂γ from the w'(z) identity vs central differences."""
    sigma, gamma = 0.07, 0.04
    x = np.linspace(-0.6, 0.6, 41)
    v, d_dx, d_dsigma, d_dgamma = voigt_derivs(x, sigma, gamma)
    np.testing.assert_allclose(v, voigt(x, sigma, gamma), rtol=0, atol=1e-14)

    h = 1e-7
    fd_x = (voigt(x + h, sigma, gamma) - voigt(x - h, sigma, gamma)) / (2 * h)
    fd_s = (voigt(x, sigma + h, gamma) - voigt(x, sigma - h, gamma)) / (2 * h)
    fd_g = (voigt(x, sigma, gamma + h) - voigt(x, sigma, gamma - h)) / (2 * h)
    for name, an, fd in [("x", d_dx, fd_x), ("sigma", d_dsigma, fd_s),
                         ("gamma", d_dgamma, fd_g)]:
        err = np.linalg.norm(an - fd) / np.linalg.norm(fd)
        assert err < 5e-3, f"dV/d{name}: rel-L2 {err:.2e}"


# ----------------------------------------------------------------------
# forward-model integration: the peak-chain Jacobian and FCJ under Voigt
# ----------------------------------------------------------------------
def test_shape_defaults_to_tchz_and_threads_to_compiled_model():
    from tests.test_lab_instrument import _lab6_phase, _lab_instrument
    ins = _lab_instrument()
    assert ins.profile.shape == "tchz_pv"        # default
    structure = pr.Structure(phases=[_lab6_phase()])
    pattern = pr.PatternData(two_theta=np.arange(20.0, 90.0, 0.05).tolist(),
                             intensity=[50.0] * len(np.arange(20.0, 90.0, 0.05)))
    assert compile_model(structure, ins, pattern).shape == "tchz_pv"
    ins.profile.shape = "voigt"
    assert compile_model(structure, ins, pattern).shape == "voigt"


def test_voigt_shape_rejects_unknown_value():
    from tests.test_lab_instrument import _lab_instrument
    with pytest.raises(Exception):
        _lab_instrument().profile.__class__(shape="pearson_vii")


def test_voigt_forward_analytic_jacobian_matches_fd():
    """The peak-chain analytic Jacobian must match plain forward differences
    under ``shape="voigt"`` for every column family — same bar as the TCHZ
    ``test_analytic_jacobian_matches_fd`` (widths now chain through σ,γ; FCJ,
    positions and intensities are unchanged)."""
    from tests.test_v02_core import ANALYTIC_FAMILIES, _lab_state
    structure, ins, pattern = _lab_state()
    ins.profile.shape = "voigt"
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ANALYTIC_FAMILIES:
        assert table.set_vary([path], True), path
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    assert model.shape == "voigt"

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        col_an = J[:, c]
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column — test state is degenerate"
        err = np.linalg.norm(col_an - col_fd) / scale
        assert err < 5e-3, f"{path}: analytic vs FD mismatch ({err:.2e})"
        cos = float(col_an @ col_fd) / (np.linalg.norm(col_an) * scale)
        assert cos > 0.99999, f"{path}: direction off (cos={cos:.6f})"


def test_fcj_composes_smoothly_under_voigt():
    """FCJ convolves whatever unit-area profile it is handed: the composite
    response to S/L must stay C¹ under the Voigt shape too (frozen-node design),
    or FD Jacobians would break.  Second differences scale O(h²)."""
    from pxrdref.model.profiles.fcj import fcj_offsets_weights
    x = np.array([21.80, 21.88, 21.95])       # low-angle tail below a 22° peak
    sigma, gamma = 0.07 / GAUSS_FWHM_TO_SIGMA, 0.02

    def composite(sl):
        phi, omega = fcj_offsets_weights(22.0, sl, 0.03, 24)
        return omega @ voigt(x[None, :] - phi[:, None], sigma, gamma)

    def second_diff_max(n):
        sls = np.linspace(0.0305, 0.045, n)   # strictly above hl: no s=h kink
        vals = np.array([composite(s) for s in sls])
        return np.abs(np.diff(vals, 2, axis=0)).max(axis=0)

    coarse, fine = second_diff_max(41), second_diff_max(81)
    assert np.all(fine < 0.4 * coarse)


def test_voigt_cross_backend_forward_residual():
    """The whole forward residual (not just w(z)) is backend-invariant under
    the Voigt shape: the jax-traced residual equals the numpy one."""
    pytest.importorskip("jax")
    from pxrdref.backend import set_backend
    from pxrdref.backend.jax_backend import _enable_x64, make_traced_residual
    from tests.test_v02_core import ANALYTIC_FAMILIES, _lab_state

    structure, ins, pattern = _lab_state()
    ins.profile.shape = "voigt"
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ANALYTIC_FAMILIES:
        table.set_vary([path], True)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    theta = table.x0()
    r_np = _make_residual(model, table)(theta)
    set_backend("jax")
    try:
        with _enable_x64():
            r_jax = np.asarray(make_traced_residual(model, table)(theta))
    finally:
        set_backend("numpy")
    np.testing.assert_allclose(r_jax, r_np, rtol=1e-9,
                               atol=1e-12 * float(np.abs(r_np).max()))


@pytest.mark.slow
def test_voigt_end_to_end_refines_and_plots():
    """A staged lab refinement under the Voigt shape converges and recovers the
    cell; writes obs/calc/diff PNGs (tests/output/, gitignored) for inspection."""
    from pxrdref.viz.plots import plot_result
    from tests.test_lab_instrument import _lab6_phase, _lab_instrument

    rng = np.random.default_rng(5)
    true_a = 4.1568
    structure = pr.Structure(phases=[_lab6_phase(true_a)])
    ins = _lab_instrument()
    ins.profile.shape = "voigt"
    ins.geometry.axial_sl.value = 0.03
    ins.geometry.axial_hl.value = 0.03
    tt = np.arange(18.0, 130.0, 0.02)
    pattern0 = pr.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, pattern0)
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 50.0
    y_noisy = rng.poisson(np.maximum(y, 1.0) * 20.0) / 20.0
    data = pr.PatternData(two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0) / 20.0).tolist())

    start_structure = pr.Structure(phases=[_lab6_phase(true_a + 0.002)])
    start = _lab_instrument()
    start.profile.shape = "voigt"
    start.geometry.axial_sl.value = 0.03
    start.geometry.axial_hl.value = 0.03
    ref = pr.Refinement(start_structure, start)
    result = ref.fit(data, plan="lab_bragg_brentano")

    assert result.status == "converged"
    assert result.statistics.rwp < 0.05
    a = ref.fitted_structure.phases[0].cell.a.value
    assert abs(a - true_a) < 5e-4

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "voigt_lab6_fit.png"))
    plot_result(result, path=str(OUT / "voigt_lab6_fit_lowangle.png"),
                two_theta_range=(20.6, 22.2))
    plot_result(result, path=str(OUT / "voigt_lab6_fit_highangle.png"),
                two_theta_range=(115.0, 125.0))
