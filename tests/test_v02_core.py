"""v0.2 core-numerics tests: Bérar-Lelann inflation, σ threading,
arbitrary-grid prediction, analytic Jacobian agreement, profile split."""

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import (
    _make_jacobian,
    _make_residual,
    covariance_estimates,
    run_least_squares,
)
from rietx.optimize.statistics import berar_lelann_factor
from rietx.params.vector import ParameterTable
from tests.test_refine_synthetic import perturbed_models, synthesize
from tests.test_schemas import make_lab6


@pytest.fixture(scope="module")
def synthetic_pattern():
    return synthesize()


# ----------------------------------------------------------------------
# Bérar-Lelann
# ----------------------------------------------------------------------
def test_berar_lelann_alternating_is_one():
    # perfectly alternating signs → no serial correlation → factor 1
    d = np.array([1.0, -1.0] * 50)
    assert berar_lelann_factor(d) == pytest.approx(1.0)


def _z_from_chi2_densities(x):
    """Bérar & Lelann (1991) p. 4: z from "the relative values of the
    distribution functions of the χ² distributions for one and two degrees of
    freedom", f₂/(f₁ + f₂) at x = aᵢ² + aᵢ₋₁² — taken from scipy, not from the
    closed form the function uses."""
    from scipy.stats import chi2
    f1, f2 = chi2.pdf(x, 1), chi2.pdf(x, 2)
    return f2 / (f1 + f2)


def test_berar_lelann_hand_computed_case():
    """Eqs (10)-(12) by hand on five residuals (#674).

    a = (1, 2, 3, −1, −2): z₂ = z(1 + 4), z₃ = z(4 + 9), z₄ = 0 (sign change),
    z₅ = z(1 + 4).  Runs of z > 0 are {2, 3} and {5}; a one-point run adds
    nothing, so S'' − S = 2·z₂·z₃·a₂·a₃ and S = 19.  The run-sum this replaced
    gave √(45/19) = 1.5390 here."""
    z2, z3 = _z_from_chi2_densities(5.0), _z_from_chi2_densities(13.0)
    assert z2 == pytest.approx(np.sqrt(10 * np.pi) / (2 + np.sqrt(10 * np.pi)), rel=1e-12)
    expected = np.sqrt((19.0 + 2.0 * z2 * z3 * 2.0 * 3.0) / 19.0)
    assert expected == pytest.approx(1.1752188815774838, rel=1e-14)
    d = np.array([1.0, 2.0, 3.0, -1.0, -2.0])
    assert berar_lelann_factor(d) == pytest.approx(expected, rel=1e-14)
    # the factor reads the residuals' sign pattern, not their direction
    assert berar_lelann_factor(-d) == pytest.approx(expected, rel=1e-14)


def test_berar_lelann_runs_inflate():
    # three ten-point same-sign stretches of |a| = 1: every pair has x = 2, so
    # nine points per stretch carry z = z(2), and S'' − S = 3·[(9z)² − 9z²]
    d = np.concatenate([np.ones(10), -np.ones(10), np.ones(10)])
    z = _z_from_chi2_densities(2.0)
    assert berar_lelann_factor(d) == pytest.approx(np.sqrt((30.0 + 3 * 72 * z * z) / 30.0), rel=1e-12)


def test_berar_lelann_white_noise_expectation():
    """iid N(0, 1) residuals do not give 1: eqs (10)-(12) expect
    E[S'']/E[S] = 1.269409 as N → ∞ (by quadrature over the run structure,
    independent of the implementation), a factor of 1.12668.  Two hundred
    draws of N = 200 000 average 1.12674 with a spread of 0.0014, so ± 0.006
    is a 4σ bar.  The run-sum this replaced sits at 1.508, far outside it."""
    rng = np.random.default_rng(0)
    d = rng.standard_normal(200_000)
    assert berar_lelann_factor(d) == pytest.approx(np.sqrt(1.2694088892), abs=0.006)


def test_esd_inflation_in_result(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    assert result.statistics.esd_inflation is not None
    assert result.statistics.esd_inflation >= 1.0
    # near-perfect synthetic fit → residuals ≈ white → near the white-noise
    # expectation of ≈ 1.13, not above it
    assert result.statistics.esd_inflation < 1.3


# ----------------------------------------------------------------------
# WP-0407: BL lives on the esd diagonal; the correlation is a true Pearson
# matrix (unit diagonal), which keeps the high-correlation guard alive
# ----------------------------------------------------------------------
def test_covariance_correlation_is_unit_diagonal_and_esd_carries_bl():
    """covariance_estimates returns esds ×BL and a *true* Pearson correlation
    (unit diagonal).  The pre-WP-0407 placement bug normalised the correlation
    by the inflated diagonal, leaving it with a 1/BL² diagonal — which cancelled
    BL in the reported physical esds and deflated the correlation guard by BL²."""
    rng = np.random.default_rng(0)
    n = 400
    c1 = rng.standard_normal(n)
    c2 = c1 + 0.01 * rng.standard_normal(n)      # ρ(c1, c2) ≈ 0.9999
    jac = np.column_stack([c1, c2, rng.standard_normal(n)])
    resid = np.cumsum(rng.standard_normal(n))    # serially correlated ⇒ BL ≫ 1
    resid -= resid.mean()

    esd, corr = covariance_estimates(jac, resid, 3, n_data=n)
    bl = berar_lelann_factor(resid)
    assert bl > 3.0                              # strong inflation, to expose the bug

    # true Pearson matrix: unit diagonal, |ρ| ≤ 1, and the collinear pair reads so
    assert np.allclose(np.diag(corr), 1.0)
    assert np.all(np.abs(corr) <= 1.0 + 1e-9)
    assert abs(corr[0, 1]) > 0.98

    # the returned esd is the raw √diag(cov) scaled by BL exactly
    cov = np.linalg.pinv(jac.T @ jac) * (resid @ resid) / (n - 3)
    assert np.allclose(esd, np.sqrt(np.diag(cov)) * bl)


def test_correlation_stays_a_valid_pearson_matrix_under_extreme_conditioning():
    """A badly conditioned JᵀJ must not produce |ρ| > 1.

    JᵀJ is PSD, so its Moore-Penrose inverse is PSD and every |ρ| ≤ 1 —
    mathematically.  ``np.linalg.pinv`` *without* ``hermitian=True`` takes the
    general SVD path, which on cond ≈ 10²⁰ normal matrices returns a
    non-symmetric, non-PSD result; WP-0502 saw ρ = +2.75 for
    ``scale ~ axial_sl`` on the fluorite fit and logged it as an unfixed bug
    undermining the 0.98 correlation guard.  The columns below reproduce that
    regime deterministically: six columns spanning twelve decades of scale with
    three exact linear dependencies among them.
    """
    rng = np.random.default_rng(11)
    n = 400
    base = rng.standard_normal((n, 3))
    scales = 10.0 ** np.linspace(-6.0, 6.0, 6)
    jac = np.column_stack([
        base[:, 0],
        base[:, 0] * (1.0 + 1e-11 * rng.standard_normal(n)),  # near-duplicate
        base[:, 1],
        base[:, 1] + base[:, 2],                              # exact dependency
        base[:, 2],
        base[:, 0] + base[:, 1],                              # exact dependency
    ]) * scales
    resid = 1e-2 * rng.standard_normal(n)

    esd, corr = covariance_estimates(jac, resid, 6, n_data=n)
    assert np.all(np.abs(corr) <= 1.0)
    assert np.allclose(np.diag(corr), 1.0)
    assert np.allclose(corr, corr.T)
    assert np.all(np.isfinite(esd)) and np.all(esd >= 0.0)
    # the near-duplicate pair is the degeneracy the guard exists to catch
    assert abs(corr[0, 1]) > 0.98


def test_collinear_zero_displacement_trips_the_correlation_guard():
    """Zero-shift and Bragg-Brentano sample displacement both shift the peaks,
    so freeing them together is a textbook degeneracy (ρ ≈ 1).  On the true
    Pearson matrix the default 0.98 high-correlation guard fires; before WP-0407
    every off-diagonal was ÷BL² so the guard was dead."""
    from rietx.strategy.staged import check_guards

    structure = make_lab6()
    structure.phases[0].scale.value = 5e-3
    ins = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 4e-3
    ins.geometry.sample_displacement.value = 0.08
    tt = np.arange(20.0, 40.0, 0.01)
    seed = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    m0 = compile_model(structure, ins, seed, mode="rietveld")
    t0 = ParameterTable(structure, ins)
    y = m0.evaluate(t0.decode(t0.x0())) + 40.0
    rng = np.random.default_rng(5)
    pattern = PatternData(two_theta=m0.tt.tolist(),
                          intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["instrument.zero_shift",
                    "instrument.geometry.sample_displacement"], True)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    outcome = run_least_squares(model, table, max_iter=80)

    corr = np.asarray(outcome.correlation)
    assert np.allclose(np.diag(corr), 1.0)       # regression: not 1/BL²
    assert abs(corr[0, 1]) > 0.98

    guard = check_guards(table, outcome, threshold=0.98)   # the default threshold
    assert any({"instrument.zero_shift",
                "instrument.geometry.sample_displacement"} == set(c.paths)
               for c in guard.high_correlations), guard.high_correlations


# ----------------------------------------------------------------------
# σ threading + prediction
# ----------------------------------------------------------------------
def test_sigma_threaded_through_result(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    assert len(result.sigma) == len(result.two_theta)
    np.testing.assert_allclose(
        result.sigma, np.sqrt(np.maximum(np.asarray(result.y_obs), 1.0)))


def test_predict_arbitrary_grid(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern)

    y_fit_grid = ref.predict()
    tt = np.asarray(synthetic_pattern.two_theta)
    y_same = ref.predict(tt)
    # the fresh compile freezes windows at the *final* values while the fit
    # model froze them at stage start — identical except at window edges
    # (the documented compile-staleness effect, cf. refine.replay)
    assert np.median(np.abs(y_same - y_fit_grid)) < 1e-9
    assert np.max(np.abs(y_same - y_fit_grid)) < 1e-2 * np.max(y_fit_grid)

    # denser grid: values at shared points must agree
    dense = np.arange(5.0, 20.0, 0.002)
    y_dense = ref.predict(dense)
    assert len(y_dense) == len(dense)
    assert np.all(np.isfinite(y_dense))


# ----------------------------------------------------------------------
# analytic Jacobian agreement
# ----------------------------------------------------------------------
def _lab_state():
    """A lab Bragg-Brentano state exercising every analytic column family:
    Kα doublet, FCJ smearing, displacement + transparency, all widths."""
    structure = make_lab6()
    structure.phases[0].scale.value = 2e-4
    structure.phases[0].lor_size.value = 2e-3
    structure.phases[0].lor_strain.value = 1e-3
    ins = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.zero_shift.value = 0.01
    ins.geometry.sample_displacement.value = -0.05
    ins.geometry.sample_transparency.value = 1e-3
    ins.geometry.axial_sl.value = 0.03
    ins.geometry.axial_hl.value = 0.02
    ins.profile.u.value = 5e-3
    ins.profile.v.value = -1e-3
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 6e-3
    ins.profile.y.value = 2e-3

    tt = np.arange(18.0, 120.0, 0.02)
    rng = np.random.default_rng(3)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=(50.0 + 10.0 * rng.random(len(tt))).tolist())
    return structure, ins, pattern


# ----------------------------------------------------------------------
# instrument ⊕ sample profile split: calibrate → freeze → refine-sample
# ----------------------------------------------------------------------
def _synthesize(structure, ins, lo=18.0, hi=120.0, step=0.02, seed=11):
    tt = np.arange(lo, hi, step)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 60.0
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * 10.0) / 10.0
    return PatternData(two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
                       sigma=np.sqrt(np.maximum(y, 1.0) / 10.0).tolist())


def test_gaussian_sample_terms_add_as_variances():
    from rietx.model.profiles.caglioti import gaussian_fwhm
    theta = np.array([10.0, 25.0, 40.0])
    base = gaussian_fwhm(theta, 5e-3, -1e-3, 3e-3)
    with_strain = gaussian_fwhm(theta, 5e-3, -1e-3, 3e-3, gauss_strain=2e-3)
    t2 = np.tan(np.radians(theta)) ** 2
    np.testing.assert_allclose(with_strain**2 - base**2, 2e-3 * t2, rtol=1e-12)
    with_size = gaussian_fwhm(theta, 5e-3, -1e-3, 3e-3, gauss_size=2e-3)
    c2 = np.cos(np.radians(theta)) ** 2
    np.testing.assert_allclose(with_size**2 - base**2, 2e-3 / c2, rtol=1e-12)


@pytest.mark.slow
def test_calibrate_freeze_refine_sample_workflow(tmp_path):
    import rietx as rx

    # --- truth: one instrument, used for both measurements
    true_u, true_w, true_x = 6e-3, 3e-3, 5e-3
    def true_instrument():
        ins = Instrument.bragg_brentano(monochromator_two_theta=26.6, ka2_ratio=0.48)
        ins.zero_shift.value = 0.012
        ins.profile.u.value = true_u
        ins.profile.w.value = true_w
        ins.profile.x.value = true_x
        ins.geometry.axial_sl.value = 0.03
        ins.geometry.axial_hl.value = 0.03
        return ins

    # --- 1. calibrate on an unbroadened standard
    standard = rx.Structure(phases=[make_lab6().phases[0]])
    standard.phases[0].scale.value = 2e-4
    cal_data = _synthesize(standard, true_instrument(), hi=140.0)

    start = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    start.profile.w.value = 1.5e-3
    start.profile.x.value = 2e-3
    start.geometry.axial_sl.value = 0.03
    start.geometry.axial_hl.value = 0.03
    # calibration holds the *certified* standard cell fixed (lab_calibrate) —
    # that pins the dispersion axis and decorrelates zero from displacement
    cal_structure = rx.Structure(phases=[make_lab6().phases[0]])
    cal_structure.phases[0].scale.value = 1e-4
    ref = Refinement(cal_structure, start, history=False)
    cal = ref.fit(cal_data, plan="lab_calibrate")
    assert cal.status == "converged"
    assert cal.statistics.rwp < 0.05
    assert ref.fitted_instrument.zero_shift.value == pytest.approx(0.012, abs=3e-3)
    assert ref.fitted_instrument.geometry.sample_displacement.value == pytest.approx(0.0, abs=0.02)

    # --- 2. freeze: export + reload
    path = tmp_path / "lab.instprof.json"
    rx.save_instrument_profile(ref.fitted_instrument, path)
    frozen = rx.load_instrument_profile(path)
    assert frozen.profile.w.value == pytest.approx(
        ref.fitted_instrument.profile.w.value)
    assert not frozen.profile.w.vary
    assert frozen.geometry.sample_displacement.value == 0.0

    # --- 3. sample measurement: same instrument, broadened sample, new cell
    true_lor_size, true_gauss_strain = 1.2e-2, 6e-3
    sample_truth = rx.Structure(phases=[make_lab6().phases[0]])
    sample_truth.phases[0].cell = rx.Cell.cubic(4.1620)
    sample_truth.phases[0].scale.value = 2e-4
    sample_truth.phases[0].lor_size.value = true_lor_size
    sample_truth.phases[0].gauss_strain.value = true_gauss_strain
    sam_ins = true_instrument()
    sam_ins.geometry.sample_displacement.value = -0.06
    sam_data = _synthesize(sample_truth, sam_ins, seed=13)

    sample_start = rx.Structure(phases=[make_lab6().phases[0]])
    sample_start.phases[0].cell = rx.Cell.cubic(4.1615)
    sample_start.phases[0].scale.value = 1e-4
    ref2 = Refinement(sample_start, frozen, history=False)
    res2 = ref2.fit(sam_data, plan="lab_sample_refine")
    assert res2.status == "converged"
    assert res2.statistics.rwp < 0.06

    # instrument stayed frozen at calibration values …
    fitted_ins = ref2.fitted_instrument
    for name in ("u", "v", "w", "x", "y"):
        assert getattr(fitted_ins.profile, name).value == pytest.approx(
            getattr(frozen.profile, name).value, abs=0.0), name
    assert fitted_ins.zero_shift.value == frozen.zero_shift.value
    # … while the sample terms picked up the broadening
    ph = ref2.fitted_structure.phases[0]
    assert ph.cell.a.value == pytest.approx(4.1620, abs=3e-4)
    # Direction and rough magnitude only: lor_size, gauss_strain and the
    # frozen instrument X sit in a strongly correlated triple — that
    # degeneracy is the entire reason the profile is split into instrument ⊕
    # sample terms — so a synthetic round trip recovers the *sum* far better
    # than the split.  Measured both ways by WP-1001: this recovers lor_size
    # 27 % low with dispersion off and 39 % low with it on (the default since
    # v1.0), and gauss_strain low in both.  The bar is set from the measured
    # spread rather than from what one configuration happened to reach; a
    # tighter one would be pinning which side of a degenerate direction the
    # solver landed on.  Since WP-2002 removed the Y floor (2026-10-23) the
    # calibration trades X against Y on the standard: Y -0.0059 and X 0.0079
    # against a truth of 0 and 0.005, at Rwp 0.039442 against 0.039451, with
    # HIGH_CORRELATION and FLAT_DIRECTION raised, and the too-wide frozen X
    # leaves lor_size 55 % low.  The truth sits on the old floor, which is why
    # the floor looked accurate here; a constant instrument Lorentzian is
    # written with Y < 0 (the ProfileTCHZ:y audit row), so the floor went.
    assert ph.lor_size.value == pytest.approx(true_lor_size, rel=0.6)
    assert ph.gauss_strain.value == pytest.approx(true_gauss_strain, rel=0.5)
    assert fitted_ins.geometry.sample_displacement.value == pytest.approx(-0.06, abs=0.02)


ANALYTIC_FAMILIES = [
    "phases.0.cell.a", "phases.0.scale", "phases.0.lor_size", "phases.0.lor_strain",
    "phases.0.atoms.0.occ", "phases.0.atoms.0.biso",
    "instrument.zero_shift", "instrument.polarization",
    "instrument.geometry.sample_displacement", "instrument.geometry.sample_transparency",
    "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
    "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
    "instrument.profile.x", "instrument.profile.y",
    "instrument.source.lines.1.weight",
]


def test_analytic_jacobian_matches_fd():
    structure, ins, pattern = _lab_state()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ANALYTIC_FAMILIES:
        assert table.set_vary([path], True), path
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)

    # reference: plain forward differences of the residual, same step rule
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
        assert err < 5e-3, f"{path}: analytic vs FD column mismatch ({err:.2e})"
        cos = float(col_an @ col_fd) / (np.linalg.norm(col_an) * scale)
        assert cos > 0.99999, f"{path}: column direction off (cos={cos:.6f})"
