"""WP-2050 — a correlation against a direction the Jacobian cannot resolve is
not a measurement.

Brucite's Gaussian size, Gaussian strain and W are one exactly flat direction,
kept by the covariance at an eigenvalue rounding sets (2.7e-15 to 4.9e-14 of
the largest under 1e-14 start nudges).  Every ρ against one of them, and
``lor_size ~ lor_strain`` beside them, then moved across the 0.98 guard as the
nudge moved, so the warning count was rounding.
"""

from __future__ import annotations

import numpy as np

from rietx.optimize.identifiability import top_correlations
from rietx.optimize.least_squares import FD_STEP
from rietx.optimize.statistics import normal_covariance, resolved_correlation


def _rho(cov):
    s = np.sqrt(np.diag(cov))
    return cov / np.outer(s, s)


def _jac(noise_seed=None, n=400):
    """Columns 0-3 independent; 4 = 0 + 1 to within a forward difference's
    error, and 3 leans weakly on 4, as brucite's Lorentzian terms do on its
    Gaussian triple."""
    rng = np.random.default_rng(0)
    j = rng.standard_normal((n, 5))
    j[:, 3] += 0.3 * j[:, 0]
    j[:, 4] = j[:, 0] + j[:, 1]
    if noise_seed is not None:
        j[:, 4] += 0.1 * FD_STEP * np.random.default_rng(noise_seed).standard_normal(n)
    return j


def _full(j):
    cov, _ = normal_covariance(j, np.ones(j.shape[0]), j.shape[1])
    return _rho(cov)


def test_independent_columns_pass_through_unchanged():
    j = np.random.default_rng(1).standard_normal((300, 4))
    corr = _full(j)
    rho, unresolved = resolved_correlation(corr, j)
    assert not unresolved.any()
    assert rho is corr or np.array_equal(rho, corr)


def test_the_members_of_an_unresolved_direction_are_named():
    j = _jac(noise_seed=1)
    rho, unresolved = resolved_correlation(_full(j), j)
    assert list(np.flatnonzero(unresolved)) == [0, 1, 4]
    assert np.isnan(rho[0, 2]) and np.isnan(rho[2, 4]) and np.isnan(rho[3, 1])


def test_a_member_pair_keeps_the_full_matrix_value():
    """The FLAT_DIRECTION reading: ρ = ±1 to rounding, at every nudge."""
    j = _jac(noise_seed=1)
    corr = _full(j)
    rho, _ = resolved_correlation(corr, j)
    assert rho[0, 4] == corr[0, 4]
    assert abs(abs(rho[0, 4]) - 1.0) < 1e-6


def test_a_resolved_pair_is_the_same_whatever_the_rounding():
    """The full matrix's ρ between the resolved columns 2 and 3 moves with the
    noise in column 4; the projected one does not."""
    a, b = _jac(noise_seed=1), _jac(noise_seed=2)
    ra, _ = resolved_correlation(_full(a), a)
    rb, _ = resolved_correlation(_full(b), b)
    assert abs(ra[2, 3] - rb[2, 3]) < 1e-9
    assert np.allclose(np.diag(ra), 1.0) and np.allclose(np.diag(rb), 1.0)


def test_a_full_matrix_member_rho_is_rounding():
    """The premise, on the synthetic case: the same two Jacobians give
    member-against-nonmember ρ that disagree well past the message's three
    decimals."""
    fa, fb = _full(_jac(noise_seed=1)), _full(_jac(noise_seed=2))
    assert np.max(np.abs(fa[np.ix_([0, 1, 4], [2, 3])]
                         - fb[np.ix_([0, 1, 4], [2, 3])])) > 5e-4


def test_a_resolved_direction_is_not_projected():
    """At 1e3 x the forward-difference error the direction is measured: the
    cut is the Jacobian's accuracy, not GSAS-II's looser 1e-6."""
    j = _jac()
    j[:, 4] += 1e3 * FD_STEP * np.random.default_rng(3).standard_normal(j.shape[0])
    corr = _full(j)
    rho, unresolved = resolved_correlation(corr, j)
    assert not unresolved.any()
    assert np.array_equal(rho, corr)


def test_the_members_do_not_depend_on_a_columns_units():
    j = _jac(noise_seed=1)
    k = j * np.array([1.0, 1e6, 1.0, 1e-4, 1.0])
    _, ua = resolved_correlation(_full(j), j)
    _, ub = resolved_correlation(_full(k), k)
    assert np.array_equal(ua, ub)


def test_top_correlations_quotes_no_undetermined_pair():
    j = _jac(noise_seed=1)
    rho, _ = resolved_correlation(_full(j), j)
    names = ["a", "b", "c", "d", "e"]
    quoted = top_correlations(rho, names, k=10)
    assert all(np.isfinite(p.rho) for p in quoted)
    assert {(p.path_a, p.path_b) for p in quoted} == {
        ("a", "b"), ("a", "e"), ("b", "e"), ("c", "d")}


def test_a_flat_pair_in_an_unresolved_direction_says_what_was_left_out():
    from rietx.strategy.staged import GuardFinding

    plain = GuardFinding.flat_direction("a", "b", -1.0)
    noted = GuardFinding.flat_direction("a", "b", -1.0, unresolved=True)
    assert str(plain) == "a ~ b (ρ=-1.000; the data does not separate them)"
    assert str(noted) == ("a ~ b (ρ=-1.000; the data does not separate them; "
                          "ρ against either is not determined and is not reported)")
