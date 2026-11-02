"""The stationary-angle test's angle block, built analytically (WP-2068).

``optimize.least_squares.stationary_angle_test`` drives a set of k moment
angles to where their Jacobian columns vanish, by Gauss-Newton on the columns,
and reads the curvature there.  It took the columns C = ∂r/∂α and the block
∂²r/∂α_a∂α_b by central differences of the whole residual, 2k² + 1
evaluations an iteration, so the test's share of a moment-only fit grew from
24 % at k = 2 to 93 % at k = 16 (issue #1207's table).  The block is now
analytic where the intensity is affine in p²⟨|F_⊥|²⟩: ∂²|F_⊥|² chained through
the first derivative's factors (``_analytic_angle_block``).

**The oracle is exact, never a difference.**  F is linear in each moment, the
moment is linear in (cos α, sin α) for each angle α, and with extinction
skipped y is affine in |F_⊥|², so r along any one angle, or any two, is a
trigonometric polynomial of degree two in each.  Eight equally spaced samples
over a period determine it exactly, and the derivatives at the start are the
DFT's coefficients times (i·n), with no truncation error at any order.  The
oracle checks its own premise: the harmonics it has no place for read zero.

The fixtures are ``test_magnetic_solve``'s Pnma parent with one to four
moment-carrying sites (two angles each), compiled at the start without a fit.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.structure import Moment

#: Mn sites: the parent's two inversion centres, then two general positions
#: carrying the same ion, so k = 8 needs no second structure
SITES = [(0.0, 0.0, 0.5), (0.0, 0.0, 0.0), (0.31, 0.04, 0.72), (0.12, 0.08, 0.33)]
N_SAMPLES = 8


def _solve():
    from tests import test_magnetic_solve as T

    return T


def _vec(mu: float, tilt: float, phi: float) -> tuple[float, float, float]:
    return (mu * math.cos(tilt) * math.cos(phi),
            mu * math.cos(tilt) * math.sin(phi), mu * math.sin(tilt))


def _phase(n_sites: int, *, offset: float, vary: bool):
    from tests.test_stationary_moment_angle import _magnetic

    T = _solve()
    atoms = [T._atom(f"Mn{i + 1}", "Mn", xyz, moment=Moment.from_values(
        _vec(3.0 - 0.4 * i + offset, 0.3 + 0.2 * i + offset, 0.2 * i + offset),
        "Mn3+", vary=vary)) for i, xyz in enumerate(SITES[:n_sites])]
    atoms += [T._atom("O1", "O", (0.48, 0.25, 0.07)),
              T._atom("O2", "O", (0.31, 0.04, 0.72) if n_sites < 3
                      else (0.21, 0.44, 0.61))]
    return rx.Phase(name="sites", space_group="P n m a", cell=T._cell(5.74, 7.70, 5.54),
                    atoms=atoms, magnetic_symmetry=_magnetic())


def _problem(n_sites: int, *, claim_moving: bool = True):
    """Model, table, residual, start and angle columns for ``n_sites`` sites.

    ``claim_moving=False`` compiles with no claim about what moves, so
    extinction is evaluated (``CompiledPhase.skip_extinction`` stays False)
    and the analytic block must decline.
    """
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import (
        _column_entries,
        _make_residual,
        _moment_angle_columns,
    )
    from rietx.params.vector import ParameterTable

    T = _solve()
    instrument = T.neutron()
    data = T.simulate(_phase(n_sites, offset=0.0, vary=False), instrument)
    structure = rx.Structure(phases=[_phase(n_sites, offset=0.03, vary=True)])
    table = ParameterTable(structure, instrument)
    table.set_vary(["phases.*.scale"], True)
    model = compile_model(structure, instrument, data,
                          moving_paths=(set(table.moving_paths)
                                        if claim_moving else None))
    n = len(table.free_paths)
    idx = [c for c, _, _ in _moment_angle_columns(
        _column_entries([table], [np.arange(n)], n))]
    assert len(idx) == 2 * n_sites
    return model, table, _make_residual(model, table), table.x0(), idx


def _trig_oracle(r, x, cols, n_data):
    """r's derivatives along ``cols`` (one or two θ columns) at ``x``, exact.

    Returns ``(derivatives, leftover)``: the first derivative for one column or
    the mixed second derivative for two, plus the largest harmonic of degree
    three or more over the largest harmonic, which is zero where r is the
    degree-two trigonometric polynomial the oracle assumes.
    """
    grid = 2.0 * np.pi * np.arange(N_SAMPLES) / N_SAMPLES
    n = np.fft.fftfreq(N_SAMPLES) * N_SAMPLES
    shape = (N_SAMPLES,) * len(cols)
    samples = np.empty((*shape, n_data))
    for pos in np.ndindex(*shape):
        th = x.copy()
        for c, p in zip(cols, pos, strict=True):
            th[c] += grid[p]
        samples[pos] = np.asarray(r(th), dtype=np.float64)[:n_data]
    axes = tuple(range(len(cols)))
    coef = np.fft.fftn(samples, axes=axes) / N_SAMPLES ** len(cols)
    high = np.abs(n) >= 3
    if len(cols) == 1:
        first = np.real((1j * n)[:, None] * coef).sum(axis=0)
        second = np.real((-n * n)[:, None] * coef).sum(axis=0)
        leftover = np.abs(coef[high]).max() / np.abs(coef).max()
        return (first, second), leftover
    mixed = np.real(-(n[:, None, None] * n[None, :, None]) * coef).sum(axis=(0, 1))
    leftover = (np.abs(coef[high]).max(initial=0.0)
                + np.abs(coef[:, high]).max(initial=0.0)) / np.abs(coef).max()
    return mixed, leftover


def test_the_moment_second_derivative_is_exact():
    """``d2_moment_d_dofs`` against the DFT of ``d_moment_d_dofs``, both frames."""
    from rietx.crystallography.magnetic.moments import (
        d2_moment_d_dofs,
        d_moment_d_dofs,
    )

    rng = np.random.default_rng(7)
    grid = 2.0 * np.pi * np.arange(N_SAMPLES) / N_SAMPLES
    n = np.fft.fftfreq(N_SAMPLES) * N_SAMPLES
    for size in (2, 3):
        frame = rng.normal(size=(size, 3))
        dofs = np.concatenate([[2.7], rng.uniform(-1.0, 1.0, size - 1)])
        exact = d2_moment_d_dofs(frame, dofs)
        assert exact.shape == (size, size, 3)
        assert np.array_equal(exact, exact.transpose(1, 0, 2))
        # the modulus enters linearly
        assert np.array_equal(exact[0, 0], np.zeros(3))
        for b in range(1, size):
            # ∂/∂α_b of every row of the first derivative: a trigonometric
            # polynomial of degree one in α_b, read off eight samples
            rows = []
            for t in grid:
                d = dofs.copy()
                d[b] += t
                rows.append(d_moment_d_dofs(frame, d))
            coef = np.fft.fft(np.array(rows), axis=0) / N_SAMPLES
            assert np.abs(coef[np.abs(n) >= 2]).max() < 1e-14 * np.abs(coef).max()
            oracle = np.real((1j * n)[:, None, None] * coef).sum(axis=0)
            assert np.abs(exact[:, b] - oracle).max() < 1e-13 * np.abs(oracle).max()


def test_the_block_is_the_exact_oracle():
    """Two sites, four angles: C and every entry of ∂²r/∂α∂α to round-off.

    Scaled by the largest entry of the oracle's own block, since a mixed
    entry between two sites can sit five orders under a site's own curvature
    (7.4e-3 against 3.4e3 here), where the oracle's round-off is that of the
    samples it differences.
    """
    from rietx.optimize.least_squares import _analytic_angle_block

    model, table, r, x, idx = _problem(2)
    n_data = len(model.tt)
    block = _analytic_angle_block(model, table)(idx)
    assert block is not None
    cols, curv = block(x)
    k = len(idx)
    assert cols.shape == (n_data, k) and curv.shape == (n_data, k, k)
    oracle_c = np.empty_like(cols)
    oracle_m = np.empty_like(curv)
    for a in range(k):
        (oracle_c[:, a], oracle_m[:, a, a]), leftover = _trig_oracle(
            r, x, [idx[a]], n_data)
        assert leftover < 1e-14
        for b in range(a + 1, k):
            oracle_m[:, a, b], leftover = _trig_oracle(r, x, [idx[a], idx[b]], n_data)
            oracle_m[:, b, a] = oracle_m[:, a, b]
            assert leftover < 1e-14
    assert np.abs(cols - oracle_c).max() < 1e-12 * np.abs(oracle_c).max()
    assert np.abs(curv - oracle_m).max() < 1e-12 * np.abs(oracle_m).max()


def test_extinction_evaluated_keeps_the_differences():
    """No claim about what moves leaves extinction evaluated, so the intensity
    is not affine in |F_⊥|² and the branch declines the whole set."""
    from rietx.optimize.least_squares import _analytic_angle_block

    model, table, _r, _x, idx = _problem(1, claim_moving=False)
    assert not model.phases[0].skip_extinction
    assert _analytic_angle_block(model, table)(idx) is None
    # and with the claim made, the same set is the branch's
    model, table, _r, _x, idx = _problem(1)
    assert _analytic_angle_block(model, table)(idx) is not None


def _run_test(model, table, r, x, idx, analytic: bool):
    from rietx.optimize.least_squares import (
        _analytic_angle_block,
        _column_entries,
        _make_jacobian,
        stationary_angle_test,
    )

    calls = [0]

    def counted(th):
        calls[0] += 1
        return r(th)

    n = len(table.free_paths)
    jac = _make_jacobian(model, table)(x)
    rounds, left_out = stationary_angle_test(
        counted, x, jac, len(model.tt), table.free_paths,
        _column_entries([table], [np.arange(n)], n), n,
        angle_block=_analytic_angle_block(model, table) if analytic else None)
    return rounds, left_out, calls[0]


@pytest.mark.parametrize("n_sites", [1, 2, 4])
def test_the_analytic_block_reaches_the_differences_verdict_for_a_tenth(n_sites):
    """k = 2, 4, 8: the same rounds and verdicts, at a tenth of the evaluations.

    The start sits 0.03 rad off the simulated angles, so every round has
    somewhere to drive.  The statistic and the stationary point carry the
    differences' O(h²) error, h = 1e-4, so they agree to a part in 1e6 and
    not to the bit.
    """
    model, table, r, x, idx = _problem(n_sites)
    fd_rounds, fd_out, fd_calls = _run_test(model, table, r, x, idx, analytic=False)
    an_rounds, an_out, an_calls = _run_test(model, table, r, x, idx, analytic=True)
    assert fd_out == an_out
    assert len(fd_rounds) == len(an_rounds)
    for fd, an in zip(fd_rounds, an_rounds, strict=True):
        assert (fd.paths, fd.reached, fd.zeroed, fd.cut) == (
            an.paths, an.reached, an.zeroed, an.cut)
        assert (fd.statistic is None) == (an.statistic is None)
        if fd.statistic is not None:
            assert an.statistic == pytest.approx(fd.statistic, rel=1e-6, abs=1e-6)
        assert set(fd.stationary_at) == set(an.stationary_at)
        for p, v in fd.stationary_at.items():
            assert an.stationary_at[p] == pytest.approx(v, abs=1e-6)
    k = len(idx)
    print(f"k={k}: {fd_calls} residual evaluations by differences, {an_calls} analytic")
    assert an_calls * (10 if k >= 8 else 2) <= fd_calls
