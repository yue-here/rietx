"""How badly-scaled and gradient-free columns reach a reported esd (WP-1110 §14).

The defect these guard against does not show up as a failure, a warning or a
missing number.  It shows up as an esd that is *small*: ``np.linalg.pinv``
discards every eigenvalue below ``rcond × |λ|max``, so one column with a large
gradient sets the cutoff for all of them, and a direction the data does not
constrain is returned with **zero** variance rather than infinite.  On the fit
this WP measured, ``phases.0.gauss_size`` came back 6.1e-14 ± 9.9e-11 — a
figure a reader would quote — where the equilibrated inverse says ± 4.3e+08.

The load-bearing test here is
``test_an_esd_does_not_depend_on_another_parameters_units``.  It needs no
dataset and no tolerance argument: if rescaling one column moves a *different*
column's esd, the inversion is wrong, and it moved by a factor of two.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.optimize.least_squares import covariance_estimates
from rietx.optimize.statistics import normal_covariance


def _problem(seed: int = 0, n: int = 400, p: int = 4):
    rng = np.random.default_rng(seed)
    jac = rng.normal(size=(n, p))
    jac[:, -1] *= 1e-7  # a column carrying almost no gradient
    return jac, rng.normal(size=n) * 0.01


def _esds(jac, resid):
    cov, _ = normal_covariance(jac, resid, jac.shape[1])
    return np.sqrt(np.maximum(np.diag(cov), 0.0))


def test_an_esd_does_not_depend_on_another_parameters_units():
    """Rescale one column; every *other* column's esd must not move.

    A parameter's units are the caller's choice — Biso in Å² or in 1e-4 Å²
    describes the same fit — so an esd that moves when a different parameter is
    respelled is reporting an artefact of the arithmetic.  Before WP-1110 the
    pseudo-inverse took its rcond cutoff from the largest eigenvalue of the
    whole normal matrix, which is exactly the coupling; measured here, the
    other three esds changed by a factor of 2.
    """
    jac, resid = _problem()
    base = _esds(jac, resid)

    rescaled = jac.copy()
    rescaled[:, 0] *= 1e6
    moved = _esds(rescaled, resid)
    moved[0] *= 1e6  # undo the reparameterisation on the column that had it

    assert np.allclose(moved, base, rtol=1e-9), moved / base


def test_a_gradient_free_column_is_undetermined_and_not_precise():
    """No gradient means infinite variance, never zero.

    Zero is the answer that reads as "measured perfectly" — the confident wrong
    singleton the package's own invariant forbids.  Its covariance *with*
    everything else is zero, which is the true statement: a direction the
    residual does not move cannot co-vary with one it does.
    """
    jac, resid = _problem()
    jac[:, -1] = 0.0
    cov, _ = normal_covariance(jac, resid, jac.shape[1])

    assert np.isinf(cov[-1, -1])
    assert np.all(cov[-1, :-1] == 0.0) and np.all(cov[:-1, -1] == 0.0)
    assert np.all(np.isfinite(np.diag(cov)[:-1]))


def test_the_correlation_matrix_survives_an_undetermined_column():
    """``corr`` stays a valid Pearson matrix with an infinity in the diagonal.

    The guard that reads it (``HIGH_CORRELATION``) must not see a NaN, and the
    undetermined column must not read as correlated with anything.
    """
    jac, resid = _problem()
    jac[:, -1] = 0.0
    stderr, corr = covariance_estimates(jac, resid, jac.shape[1])

    assert np.isinf(stderr[-1]) and np.all(np.isfinite(stderr[:-1]))
    assert np.all(np.isfinite(corr))
    assert np.allclose(np.diag(corr), 1.0)
    assert np.all(np.abs(corr) <= 1.0)
    assert np.all(corr[-1, :-1] == 0.0)


def test_a_well_determined_column_keeps_the_esd_it_had():
    """Equilibration is not allowed to move a number anyone was relying on.

    Against the closed form for an orthogonal design, where the covariance is
    ``chi2_red / n`` per column and the scaling has nothing to fix.
    """
    n, p = 512, 4
    jac = np.zeros((n, p))
    for k in range(p):  # orthogonal columns of differing, honest magnitudes
        jac[:, k] = np.cos((k + 1) * np.pi * np.arange(n) / n) * 10.0 ** k
    rng = np.random.default_rng(3)
    resid = rng.normal(size=n) * 0.01

    chi2_red = float(resid @ resid) / (n - p)
    expected = np.sqrt(chi2_red / np.sum(jac * jac, axis=0))
    assert np.allclose(_esds(jac, resid), expected, rtol=1e-10)


@pytest.mark.parametrize("scale", [1.0, 1e-8, 1e8])
def test_the_answer_is_the_same_however_the_whole_problem_is_scaled(scale):
    """Scaling *every* column together must scale every esd together.

    The companion to the units test: the first says the columns must not talk
    to each other, this one says the inversion still tracks an overall change.
    """
    jac, resid = _problem(seed=5)
    base = _esds(jac, resid)
    assert np.allclose(_esds(jac * scale, resid) * scale, base, rtol=1e-9)


# --- propagation: which rows an undetermined column is allowed to cost -------

def _table():
    """A cubic phase: ``cell.a`` free with ``cell.b``/``cell.c`` tied to it."""
    import rietx as rx
    from rietx.params.vector import ParameterTable

    structure = rx.Structure.from_cif("tests/data/cod_1000236.cif")
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)
    structure.phases[0].cell.a.vary = True
    structure.phases[0].scale.vary = True
    instrument.profile.w.vary = True
    return ParameterTable(structure, instrument)


def test_an_undetermined_column_costs_its_own_rows_and_no_others():
    """The rutile failure, at the size where it can be read.

    ``instrument.profile.w`` measured nothing; ``cell.a`` and the two lengths
    tied to it did.  The tied rows must still report — a symmetry tie carries
    its source's esd — and only the profile row goes absent.  Before the mask,
    the infinity in ``Cov_free`` met a zero coefficient in ``C @ cov`` and put
    a NaN on every row sharing a source with it; the rutile geometry table lost
    all six Ti-O bond esds to a parameter no bond depends on.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([1e-5, 1e-7, np.inf])  # profile.w undetermined
    corr = np.eye(3)

    esd = table.stderr_physical(theta, stderr, corr)
    assert "instrument.profile.w" not in esd
    for path in ("phases.0.cell.a", "phases.0.cell.b", "phases.0.cell.c",
                 "phases.0.scale"):
        assert path in esd and np.isfinite(esd[path]) and esd[path] > 0

    assert esd["phases.0.cell.b"] == pytest.approx(esd["phases.0.cell.a"])


def test_the_mask_names_the_columns_and_the_rows_they_reach():
    """``unmeasured_free`` is over columns, ``unmeasured_rows`` over entries.

    The second is the first pushed through ``C``, which is what makes a *tied*
    row inherit its source's blindness — a tie whose source measured nothing
    measured nothing — without a second rule saying so.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([np.inf, 1e-7, 1e-6])  # cell.a undetermined

    assert list(table.unmeasured_free(theta, stderr)) == [True, False, False]
    blind = table.unmeasured_rows(theta, stderr)
    named = {e.path for e, b in zip(table.entries, blind, strict=True) if b}
    assert named == {"phases.0.cell.a", "phases.0.cell.b", "phases.0.cell.c"}

    esd = table.stderr_physical(theta, stderr, np.eye(3))
    assert not (named & set(esd))
    assert "phases.0.scale" in esd


def test_nothing_changes_when_every_column_measured_something():
    """The mask is inert on an ordinary fit, and inert exactly.

    Both branches of ``stderr_physical`` — with and without a correlation
    matrix — go through the same construction now, so this also pins that the
    refactor did not move the uncorrelated answer.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([1e-5, 1e-7, 1e-6])

    assert not table.unmeasured_free(theta, stderr).any()
    assert not table.unmeasured_rows(theta, stderr).any()

    diag_only = table.stderr_physical(theta, stderr, None)
    correlated = table.stderr_physical(theta, stderr, np.eye(3))
    assert diag_only.keys() == correlated.keys()
    for path, value in diag_only.items():
        assert correlated[path] == pytest.approx(value, rel=1e-12)


# ----------------------------------------------------------------------
# A failed eigensolve is not a failed fit (WP-1333, issue #225)
# ----------------------------------------------------------------------
# The reporter met ``LinAlgError: Eigenvalues did not converge`` out of
# ``normal_covariance`` at a *converged* fit, and could not reduce it to a
# data-free case (columns at 1e-90 to 1e-200 pass without raising), so these
# tests inject the raise rather than construct it.  What they pin is the
# consequence, which needs no mechanism: the solver's answer survives, every
# esd is absent rather than raised over, and a diagnostic names the stage.

def _eigh_fails(*args, **kwargs):
    raise np.linalg.LinAlgError("Eigenvalues did not converge")


def test_a_failed_eigensolve_leaves_the_esds_absent_not_raised(monkeypatch):
    """Since WP-2002 the eigensolve is repeated with LAPACK's ``syev`` where
    numpy's ``syevd`` fails (``optimize.lapack``), so the esds are absent only
    when both drivers fail."""
    from rietx.optimize import lapack, least_squares, statistics

    jac, resid = _problem()
    ref = least_squares._guarded_covariance(jac, resid, 4, 400)
    assert ref[3] is None

    monkeypatch.setattr(statistics.np.linalg, "eigh", _eigh_fails)
    stderr, _, _, error = least_squares._guarded_covariance(jac, resid, 4, 400)
    assert error is None
    np.testing.assert_allclose(stderr, ref[0], rtol=1e-10)

    monkeypatch.setattr(lapack.scipy.linalg, "eigh", _eigh_fails)
    stderr, corr, factor, error = least_squares._guarded_covariance(
        jac, resid, 4, 400)
    assert stderr is None and corr is None and factor is None
    assert "Eigenvalues did not converge" in error


def test_only_an_eigensolver_failure_is_caught(monkeypatch):
    """Anything that is not ``LinAlgError`` is a defect, and stays loud."""
    from rietx.optimize import least_squares, statistics

    def broken(*args, **kwargs):
        raise TypeError("a bug, not a spectrum")

    monkeypatch.setattr(statistics.np.linalg, "eigh", broken)
    jac, resid = _problem()
    with pytest.raises(TypeError, match="a bug"):
        least_squares._guarded_covariance(jac, resid, 4, 400)


@pytest.fixture(scope="module")
def _lab6_pattern():
    from tests.test_refine_synthetic import synthesize

    return synthesize()


def _fit(pattern):
    from rietx import Refinement
    from tests.test_refine_synthetic import perturbed_models

    structure, ins = perturbed_models()
    return Refinement(structure, ins).fit(pattern, plan="mccusker_default")


def test_a_fit_whose_covariance_raises_returns_its_values(monkeypatch,
                                                         _lab6_pattern):
    """Every stage's esd computation raises; the fit still returns.

    The values are **bit-identical** to the same fit with a working
    eigensolver, because nothing in the solve reads an esd — they are
    computed after each stage's solver has returned — and that is the whole
    argument for the fallback: the answer was in hand when the raise
    discarded it.
    """
    reference = _fit(_lab6_pattern)

    from rietx.optimize import statistics

    # the esd path only: the report's own region fits call ``pinv`` too, and
    # a global patch would fail those for a reason this test is not about.
    # ``normal_factors`` since WP-1463, which both ``normal_covariance`` and
    # ``covariance_estimates`` reach
    monkeypatch.setattr(statistics, "normal_factors", _eigh_fails)
    result = _fit(_lab6_pattern)

    assert result.status == reference.status
    assert [(p.path, p.value) for p in result.parameters] == \
        [(p.path, p.value) for p in reference.parameters]
    assert all(p.stderr is None for p in result.parameters)
    assert any(p.stderr is not None for p in reference.parameters)

    fired = [d for d in result.diagnostics if d.code == "COVARIANCE_UNAVAILABLE"]
    stages = [s.name for s in result.stages]
    # one per stage, each naming its own, and the answer-producing one is the
    # one that says the result's esds are gone
    assert [d.where for d in fired] == [[name] for name in stages]
    assert all(d.level == "warning" for d in fired)
    assert "Every esd, correlation and derived uncertainty" in fired[-1].message
    assert all("intermediate stage" in d.message for d in fired[:-1])
    assert not any(d.code == "COVARIANCE_UNAVAILABLE"
                   for d in reference.diagnostics)


def test_the_soft_mode_screen_does_not_re_raise_the_same_failure(
        monkeypatch, _lab6_pattern):
    """``check_guards``' soft-mode screen eigensolves the unit-column Gram,
    which is the matrix the esd computation just failed on, so the #225 raise
    came straight back one call later and discarded the fit anyway (found by
    the WP-1333 review).  Where the covariance failed it is absorbed; where it
    formed, the same raise stays loud."""
    from rietx.optimize import identifiability, statistics

    monkeypatch.setattr(statistics, "normal_factors", _eigh_fails)
    monkeypatch.setattr(identifiability, "soft_modes", _eigh_fails)
    result = _fit(_lab6_pattern)
    assert any(d.code == "COVARIANCE_UNAVAILABLE" for d in result.diagnostics)

    monkeypatch.undo()
    monkeypatch.setattr(identifiability, "soft_modes", _eigh_fails)
    with pytest.raises(np.linalg.LinAlgError):
        _fit(_lab6_pattern)


def test_an_intermediate_failure_leaves_the_answer_its_esds(monkeypatch,
                                                           _lab6_pattern):
    """Only the first stage's eigensolve fails: the result keeps every esd."""
    from rietx.optimize import statistics

    real = statistics.normal_factors
    calls = {"n": 0}

    def first_fails(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise np.linalg.LinAlgError("Eigenvalues did not converge")
        return real(*args, **kwargs)

    reference = _fit(_lab6_pattern)
    monkeypatch.setattr(statistics, "normal_factors", first_fails)
    result = _fit(_lab6_pattern)

    fired = [d for d in result.diagnostics if d.code == "COVARIANCE_UNAVAILABLE"]
    assert [d.where for d in fired] == [[result.stages[0].name]]
    assert "intermediate stage" in fired[0].message
    assert [(p.path, p.value, p.stderr) for p in result.parameters] == \
        [(p.path, p.value, p.stderr) for p in reference.parameters]


# ----------------------------------------------------------------------
# A tiny column is live (WP-1463)
# ----------------------------------------------------------------------
# A softplus scale at 1e-166 has a column of about 1e-158.  Before WP-1463 its
# variance K·(1/d)² overflowed and read as unmeasured, and below about 1e-170
# its d² underflowed and read as gradient-free, while its physical esd was an
# ordinary 7.66e-9 throughout.  Every test here asks one question: does a
# column's magnitude change anything a magnitude cannot change?

def _pre_1463(jac, resid):
    """The covariance_estimates arithmetic as it stood, for the bit-identity pin."""
    jtj = jac.T @ jac
    jtj = 0.5 * (jtj + jtj.T)
    chi2 = float(resid @ resid) / max(len(resid) - jac.shape[1], 1)
    d = np.sqrt(np.diag(jtj))
    live = d > 0.0
    inv_d = np.where(live, 1.0 / np.where(live, d, 1.0), 0.0)
    cov = np.linalg.pinv(jtj * np.outer(inv_d, inv_d), hermitian=True) * chi2
    cov = cov * np.outer(inv_d, inv_d)
    sqrt = np.sqrt(np.maximum(np.diag(cov), 0.0))
    corr = np.clip(np.where(np.outer(sqrt, sqrt) > 0,
                            cov / np.outer(sqrt, sqrt), 0.0), -1.0, 1.0)
    np.fill_diagonal(corr, np.where(sqrt > 0.0, 1.0, 0.0))
    return sqrt, corr


def test_an_ordinary_problem_keeps_every_bit():
    """No column outside the rescale window, so nothing may move at all.

    ``_problem`` carries a column at 1e-7 already, so the equilibration path
    is exercised; the rescale must be inert there to the last bit.
    """
    from rietx.optimize.statistics import berar_lelann_factor, column_rescale

    jac, resid = _problem(seed=11)
    assert column_rescale(jac) is None
    stderr, corr = covariance_estimates(jac, resid, jac.shape[1])
    sqrt, corr0 = _pre_1463(jac, resid)
    assert np.array_equal(stderr, sqrt * berar_lelann_factor(resid))
    assert np.array_equal(corr, corr0)


@pytest.mark.parametrize("factor", [2.0 ** -600, 1e-158, 1e-170, 1e-300])
def test_a_tiny_column_keeps_the_esd_its_physical_parameter_has(factor):
    """Scale one column down by ``factor``: its esd scales up by the same.

    ``2**-600`` is a pure exponent move, so the other columns' esds and
    correlations must not change by a bit.  The decimal factors round the
    column once, so they are held to 1e-12.  1e-158 sits in the band where
    only the variance overflowed, and 1e-170 and 1e-300 below the one where
    d² underflowed too.
    """
    jac, resid = _problem(seed=11)
    base_s, base_c = covariance_estimates(jac, resid, jac.shape[1])
    tiny = jac.copy()
    tiny[:, 1] *= factor
    s, c = covariance_estimates(tiny, resid, jac.shape[1])

    assert np.isfinite(s[1])
    assert s[1] * factor == pytest.approx(base_s[1], rel=1e-12)
    others = [0, 2, 3]
    if factor == 2.0 ** -600:
        assert np.array_equal(s[others], base_s[others])
        assert np.array_equal(c[np.ix_(others, others)],
                              base_c[np.ix_(others, others)])
    else:
        assert np.allclose(s[others], base_s[others], rtol=1e-12, atol=0)
    assert np.allclose(c, base_c, rtol=1e-12, atol=1e-14)


def test_two_tiny_columns_keep_their_correlation():
    """Where both columns are tiny, the product form divides inf by inf.

    Their correlation then comes from the scale-free inverse, and it must be
    the one the unscaled problem has, never a clipped 1.
    """
    jac, resid = _problem(seed=11)
    jac[:, 2] += 0.9 * jac[:, 1]  # a real correlation to preserve
    base_s, base_c = covariance_estimates(jac, resid, jac.shape[1])
    tiny = jac.copy()
    tiny[:, 1] *= 1e-170
    tiny[:, 2] *= 1e-165
    s, c = covariance_estimates(tiny, resid, jac.shape[1])
    assert abs(base_c[1, 2]) > 0.5
    assert c[1, 2] == pytest.approx(base_c[1, 2], rel=1e-12)
    assert s[1] * 1e-170 == pytest.approx(base_s[1], rel=1e-12)
    assert s[2] * 1e-165 == pytest.approx(base_s[2], rel=1e-12)


def test_a_zero_column_is_still_unmeasured():
    """The rescale leaves a zero column alone: that one really measured nothing."""
    from rietx.optimize.statistics import column_rescale

    jac, resid = _problem(seed=11)
    jac[:, 1] = 0.0
    jac[:, 2] *= 1e-170
    assert column_rescale(jac)[1] == 1.0
    stderr, corr = covariance_estimates(jac, resid, jac.shape[1])
    assert np.isinf(stderr[1]) and np.isfinite(stderr[2])
    assert np.all(corr[1, [0, 2, 3]] == 0.0)


@pytest.mark.parametrize("factor", [2.0 ** -600, 1e-170])
def test_every_scale_free_reading_of_a_column_ignores_its_magnitude(factor):
    """The squared-norm siblings: a cosine, a soft mode, an R², a score gain.

    Each is invariant under rescaling one column, and each read a column of
    1e-170 as zero before WP-1463 (the cosine fed ``at_bound``).
    """
    from rietx.optimize.identifiability import soft_modes
    from rietx.optimize.least_squares import _residual_cosine
    from rietx.optimize.statistics import (
        block_projection_r2,
        column_norms,
        one_parameter_gains,
    )

    jac, resid = _problem(seed=11)
    tiny = jac.copy()
    tiny[:, 1] *= factor
    paths = ["a", "b", "c", "d"]

    assert column_norms(tiny)[1] == pytest.approx(
        np.linalg.norm(jac[:, 1]) * factor, rel=1e-12)
    assert np.array_equal(column_norms(jac), np.linalg.norm(jac, axis=0))
    assert np.allclose(_residual_cosine(tiny, resid),
                       _residual_cosine(jac, resid), rtol=1e-12, atol=0)
    base_modes, modes = soft_modes(jac, paths), soft_modes(tiny, paths)
    assert [m.eigenvalue for m in modes] == pytest.approx(
        [m.eigenvalue for m in base_modes], rel=1e-10)
    for block, target in (([0, 2], 1), ([1, 3], 0)):
        r2 = block_projection_r2(tiny, block, [(target, "t")])
        assert r2["t"] == pytest.approx(
            block_projection_r2(jac, block, [(target, "t")])["t"], rel=1e-10)
    gains = one_parameter_gains(tiny, resid, [0, 2], [(1, "b")])
    assert gains["b"] == pytest.approx(
        one_parameter_gains(jac, resid, [0, 2], [(1, "b")])["b"], rel=1e-10)


def test_an_esd_whose_variance_has_no_double_is_absent_not_infinite():
    """The price of keeping a tiny column's esd is one more way to overflow.

    A free cell of a phase whose scale sits at 1e-160 has an internal esd near
    1e+160, and ``_cov_free`` squares the physical one.  Before the cap that
    row reported ``inf``; WP-1072 wants it absent, as it was before WP-1463.
    """
    table = _table()
    theta = table.x0()
    stderr = np.array([1e160, 1e-7, 1e-6])  # cell.a, scale, profile.w

    assert list(table.unmeasured_free(theta, stderr)) == [True, False, False]
    for corr in (None, np.eye(3)):
        esd = table.stderr_physical(theta, stderr, corr)
        assert not {"phases.0.cell.a", "phases.0.cell.b"} & set(esd)
        assert np.isfinite(esd["phases.0.scale"])


# ----------------------------------------------------------------------
# A flat direction's eigenvalue has either sign (WP-1930)
# ----------------------------------------------------------------------
# An exactly flat direction of the equilibrated normal matrix comes back from
# ``eigh`` at a rounding-level eigenvalue, and rounding picks its sign.  Above
# the ``PINV_RCOND`` cut, ``pinv`` inverted a negative one with its sign, so every
# column on that direction got a negative variance, floored to an esd of 0.
# These tests set the eigenvalue rather than hoping a platform rounds into it.

def _flat_pair(seed: int = 3, n: int = 300):
    """Four columns, the last two identical: one exactly flat direction."""
    rng = np.random.default_rng(seed)
    jac = rng.normal(size=(n, 4))
    jac[:, 3] = jac[:, 2]
    return jac, rng.normal(size=n) * 0.01


def _flat_eigenvalue_at(monkeypatch, value):
    """``eigh`` with its smallest eigenvalue set to ``value·|λ|max``."""
    from rietx.optimize import statistics

    real = np.linalg.eigh

    def eigh(a):
        lam, u = real(a)
        lam = lam.copy()
        lam[np.argmin(np.abs(lam))] = value * np.abs(lam).max()
        return lam, u

    monkeypatch.setattr(statistics.np.linalg, "eigh", eigh)


@pytest.mark.parametrize("value", [-3e-15, 3e-15])
def test_a_flat_pair_is_undetermined_whichever_sign_rounding_gives(
        monkeypatch, value):
    """Either sign gives the same huge esds and ρ = ±1, never an esd of 0.

    Before WP-1930 the negative case returned esds of exactly 0 and a
    correlation of 0 for the pair, which silenced ``HIGH_CORRELATION`` on the
    LaB₆ + cBN degenerate fit on Linux.
    """
    jac, resid = _flat_pair()
    _flat_eigenvalue_at(monkeypatch, value)
    stderr, corr = covariance_estimates(jac, resid, 4)
    monkeypatch.undo()
    _flat_eigenvalue_at(monkeypatch, abs(value))
    stderr_pos, corr_pos = covariance_estimates(jac, resid, 4)

    assert np.all(stderr > 0.0), stderr
    assert abs(corr[2, 3]) == pytest.approx(1.0, abs=1e-9)
    # the pair's esds are the flat direction's, ~1e7 of the measured ones
    assert min(stderr[2:]) > 1e5 * max(stderr[:2])
    assert np.array_equal(stderr, stderr_pos)
    assert np.array_equal(corr, corr_pos)


def _near_pair(seed: int, n: int = 300):
    """Four columns, the last two 3e-7 apart: a small eigenvalue that is kept."""
    rng = np.random.default_rng(seed)
    jac = rng.normal(size=(n, 4))
    jac[:, 3] = jac[:, 2] + 3e-7 * rng.normal(size=n)
    return jac, rng.normal(size=n) * 0.01


def test_a_psd_matrix_keeps_numpys_bits():
    """With no negative eigenvalue kept, ``_psd_pinv`` is ``pinv`` to the bit,
    so every fit whose normal matrix rounds positive is unchanged.  The three
    families cover a well-conditioned spectrum, a discarded direction and a
    small one above the cut."""
    from rietx.optimize.statistics import PINV_RCOND, _psd_pinv

    for empty in (np.zeros((0, 0)), np.zeros((3, 0, 0))):
        assert _psd_pinv(empty, PINV_RCOND).shape == np.linalg.pinv(empty).shape
    # a (k, n, n) stack, as indexing's dedup passes one (WP-1519)
    rng = np.random.default_rng(1519)
    stack = np.stack([g @ g.T for g in rng.normal(size=(8, 6, 4))])
    assert np.array_equal(_psd_pinv(stack, PINV_RCOND),
                          np.linalg.pinv(stack, rcond=PINV_RCOND, hermitian=True))
    for seed in range(30):
        jac, _ = (_problem, _flat_pair, _near_pair)[seed % 3](seed)
        e = jac.T @ jac
        e = 0.5 * (e + e.T)
        d = 1.0 / np.sqrt(np.diag(e))
        e = e * np.outer(d, d)
        # ``eigh``, not ``eigvalsh``: the two disagree in the last bits, and
        # this is a precondition on the eigenvalues ``_psd_pinv`` inverts
        lam = np.linalg.eigh(e)[0]
        assert not np.any((lam < 0) & (-lam > PINV_RCOND * np.abs(lam).max()))
        assert np.array_equal(_psd_pinv(e, PINV_RCOND),
                              np.linalg.pinv(e, rcond=PINV_RCOND, hermitian=True))
