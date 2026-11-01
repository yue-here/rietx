"""Bound-constrained conjugate gradient solver (WP-0601, Coelho 2005).

The anchor the paper itself supplies: with bounds inactive and the removal
scheme off, BCCG must reproduce the unconstrained solution.  Everything else
here pins the three modifications that make it *not* textbook CG — including
the one place where the paper's printed formula and its prose disagree.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.optimize import bccg


def _spd(n: int, cond: float, seed: int = 0) -> np.ndarray:
    """A symmetric positive-definite matrix with a prescribed condition number."""
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.standard_normal((n, n)))
    eig = np.logspace(0.0, -np.log10(cond), n)
    return q @ np.diag(eig) @ q.T


def _rel_error(x: np.ndarray, x_ref: np.ndarray) -> float:
    return float(np.linalg.norm(x - x_ref) / max(np.linalg.norm(x_ref), 1e-300))


def _system(n: int, cond: float, seed: int = 7):
    A = _spd(n, cond=cond, seed=seed)
    b = np.random.default_rng(seed + 1).standard_normal(n)
    return A, b, np.linalg.solve(A, b)


@pytest.mark.parametrize(("n", "cond"), [(1, 1.0), (5, 1e2), (40, 1e3), (60, 1e6)])
def test_cg_core_matches_direct_solve(n, cond):
    """Coelho's sanity anchor: no bounds, no removal ⇒ the exact solution.

    Run with the two published *stopping* rules relaxed, because they are what
    makes the shipped solve deliberately inexact (see the next test); this
    isolates the conjugate-gradient core itself.
    """
    A, b, ref = _system(n, cond)
    out = bccg.solve(A, b, removal=False, damping="off",
                     tol=1e-24, k_max_rule=False, max_iter=40 * n + 40)
    assert _rel_error(out.x, ref) < 1e-9
    assert out.n_clamped == 0 and out.n_dropped == 0


def _decrease_captured(A: np.ndarray, b: np.ndarray, x: np.ndarray,
                       x_star: np.ndarray) -> float:
    """Fraction of the available decrease in φ(x) = ½xᵀAx − bᵀx that ``x`` takes.

    This, not ‖x − x*‖, is what an LM inner solve owes its caller: the outer
    loop re-measures the true cost at the trial point, so a step that captures
    most of the modelled decrease is a good step even when it is far from the
    exact solution in parameter space.
    """
    def phi(v):
        return 0.5 * float(v @ A @ v) - float(b @ v)
    return (phi(np.zeros_like(x)) - phi(x)) / (phi(np.zeros_like(x)) - phi(x_star))


def test_published_termination_is_deliberately_inexact():
    """The shipped defaults stop ~1e-3 short in x while taking ~all of φ.

    s is a *squared* residual norm, so ``s_k < 1e-4·s_0`` means ‖Ax−b‖ fell
    100×.  The outer LM loop re-measures the true cost at the trial point, so
    a machine-precision inner solve would be wasted work — the paper says as
    much ("the minimization of |Ax − b| … is not adhered to").
    """
    A, b, ref = _system(40, 1e3)
    cheap = bccg.solve(A, b, removal=False)
    exact = bccg.solve(A, b, removal=False, damping="off",
                       tol=1e-24, k_max_rule=False, max_iter=2000)
    assert 1e-6 < _rel_error(cheap.x, ref) < 1e-2   # close, nowhere near exact
    assert cheap.n_iterations < exact.n_iterations
    assert _decrease_captured(A, b, cheap.x, ref) > 0.999


def test_damping_readings_under_the_published_rules():
    """Which reading of their equation (1) actually solves the system.

    The paper prints ``Max`` and describes ``Min``; this is the measurement
    that settles it for us rather than an argument from the prose.  With no
    removals, ``Max`` is *bit-identical* to no damping at all — the
    amplification branch needs k+1 > N_k, which the k_max rule then forbids —
    while the prose reading stalls two orders of magnitude short.
    """
    A, b, ref = _system(60, 1e2)
    errs = {d: _rel_error(bccg.solve(A, b, removal=False, damping=d).x, ref)
            for d in bccg._DAMPINGS}
    assert errs["max"] == pytest.approx(errs["off"], rel=1e-12)
    assert errs["min"] > 100 * errs["off"]


def test_printed_damping_hurts_once_removal_shrinks_the_loop():
    """Why the shipped default is ``"off"`` rather than the printed formula.

    Removal is what makes k+1 > N_k reachable inside k_max, and that is where
    the printed ``Max`` stops being a no-op and starts amplifying α past the
    exact line minimiser.  Measured on a dense N = 40 system: 1.000 → 0.62 of
    the available decrease.  ``"off"`` matches the printed formula everywhere
    the printed formula is safe, without that failure mode.
    """
    A, b, ref = _system(40, 1e3)
    amplified = bccg.solve(A, b, removal=True, damping="max")
    plain = bccg.solve(A, b, removal=True, damping="off")
    assert amplified.n_dropped > 0
    assert _decrease_captured(A, b, plain.x, ref) > 0.99
    assert _decrease_captured(A, b, amplified.x, ref) < 0.9


def test_printed_damping_is_safe_only_because_of_the_k_max_rule():
    """``Max`` amplifies α once k+1 > N_k, and unchecked that diverges.

    Measured: with the k_max rule lifted, the printed formula leaves the
    solution *further* from the truth than the zero vector, while the prose
    reading merely converges slowly.  So the two published stopping rules are
    not an optimisation on top of the step rule — they are what makes it safe,
    and neither may be relaxed without the other.
    """
    A, b, ref = _system(60, 1e2)
    loose = dict(removal=False, tol=1e-24, k_max_rule=False, max_iter=1200)
    amplified = bccg.solve(A, b, damping="max", **loose)
    damped = bccg.solve(A, b, damping="min", **loose)
    undamped = bccg.solve(A, b, damping="off", **loose)

    assert _rel_error(amplified.x, ref) > 1e-2
    assert _rel_error(damped.x, ref) < 1e-4
    assert _rel_error(undamped.x, ref) < 1e-9


def test_removal_scheme_is_cheap_and_harmless():
    """Equation (2) drops converged directions; the answer must survive it.

    A block-diagonal system is the case the paper singles out: the easy block
    converges and leaves the loop while the hard block carries on.

    Measured cost of the scheme on this system: it drops ‖x − x*‖ accuracy by
    ~30× (3.5e-3 → 1.1e-1) while still capturing >99 % of the modelled
    decrease.  That is the paper's own trade — "increases the number of
    refinement iterations in a marginal sense, while speeding up the solution
    of the normal equations" — and it is only sound because the outer loop
    re-measures the true cost.
    """
    easy = _spd(20, cond=1.5, seed=1)
    hard = _spd(20, cond=1e4, seed=2)
    A = np.block([[easy, np.zeros((20, 20))], [np.zeros((20, 20)), hard]])
    b = np.random.default_rng(11).standard_normal(40)
    ref = np.linalg.solve(A, b)

    with_removal = bccg.solve(A, b, removal=True)
    without = bccg.solve(A, b, removal=False)

    assert with_removal.n_dropped > 0
    assert with_removal.n_active_avg < without.n_active_avg
    assert _decrease_captured(A, b, with_removal.x, ref) > 0.99
    assert _rel_error(with_removal.x, ref) > _rel_error(without.x, ref)


def test_bounds_are_enforced_and_reported():
    """A bound the unconstrained solution violates is respected exactly."""
    A, b, free = _system(10, 1e3, seed=5)

    # bound the three largest components at half their free value
    lo = np.full(10, -np.inf)
    hi = np.full(10, np.inf)
    for i in np.argsort(-np.abs(free))[:3]:
        if free[i] > 0:
            hi[i] = 0.5 * free[i]
        else:
            lo[i] = 0.5 * free[i]

    out = bccg.solve(A, b, lo=lo, hi=hi)
    assert np.all(out.x >= lo - 1e-12)
    assert np.all(out.x <= hi + 1e-12)
    assert out.n_clamped > 0
    assert set(out.clamped) <= set(range(10))


def test_inactive_bounds_change_nothing():
    """Bounds the solution never reaches must not perturb it."""
    A, b, _ = _system(15, 1e4, seed=9)
    ref = bccg.solve(A, b, removal=False).x
    wide = bccg.solve(A, b, lo=np.full(15, -1e6), hi=np.full(15, 1e6),
                      removal=False)
    assert wide.n_clamped == 0
    assert _rel_error(wide.x, ref) < 1e-12


def test_zero_diagonal_column_is_survivable():
    """A parameter with an identically zero Jacobian column must not divide by 0.

    This is the dead-softplus-gradient case (WP-0310): the column is zero, so
    A_ii = 0 and b_i = 0, and the parameter simply never moves.
    """
    A = _spd(6, cond=1e3, seed=4)
    A[2, :] = 0.0
    A[:, 2] = 0.0
    b = np.array([1.0, -0.5, 0.0, 2.0, 0.3, -1.2])
    out = bccg.solve(A, b)
    assert np.isfinite(out.x).all()
    assert out.x[2] == 0.0


def test_empty_system():
    out = bccg.solve(np.zeros((0, 0)), np.zeros(0))
    assert out.x.shape == (0,)
    assert out.n_iterations == 0


def test_rejects_unknown_damping():
    with pytest.raises(ValueError, match="damping"):
        bccg.solve(np.eye(2), np.ones(2), damping="sometimes")


# ---------------------------------------------------------------------------
# projected CG, the LM driver's step above its BVLS cut since WP-1953
# ---------------------------------------------------------------------------

def _model(H, g, y):
    return 0.5 * float(y @ H @ y) - float(g @ y)


def test_a_clamp_past_a_bound_raises_the_model_and_projected_cg_does_not():
    """WP-1953: BCCG's first CG step here runs along the weak eigenvector to
    (−300, 300).  It clamps the first variable at −0.1 and keeps the second at
    300, so the step ends at model value +44 070, worse than not moving.  On
    FAP.XRA's Pawley fit that was most steps at λ > 0.  Projected CG stops at
    the bound, restarts, and lands on the exact minimiser."""
    H = np.array([[1.0, 0.99], [0.99, 1.0]])
    g = np.array([-3.0, 3.0])
    lo, hi = np.full(2, -0.1), np.full(2, np.inf)
    coelho = bccg.solve(H, g, lo=lo, hi=hi).x
    assert _model(H, g, coelho) == pytest.approx(44070.005, rel=1e-9)
    y, side = bccg.projected_cg(H, g, lo, hi)
    np.testing.assert_allclose(y, [-0.1, 3.099], rtol=1e-12)
    assert y[0] == -0.1 and side.tolist() == [-1, 0]
    assert _model(H, g, y) < 0.0


@pytest.mark.parametrize("seed", range(6))
def test_projected_cg_reaches_the_box_minimiser(seed):
    """On well-conditioned bounded problems the projected CG is exact: its
    point satisfies the KKT conditions and matches a dense active-set solve."""
    from scipy.optimize import lsq_linear

    rng = np.random.default_rng(seed)
    n = 12
    J = rng.standard_normal((3 * n, n))
    H, g = J.T @ J, J.T @ rng.standard_normal(3 * n)
    lo = -rng.uniform(0.0, 0.3, n)
    hi = rng.uniform(0.0, 0.3, n)
    y, side = bccg.projected_cg(H, g, lo, hi, budget=50 * n)
    w, V = np.linalg.eigh(H)
    R = np.sqrt(w)[:, None] * V.T
    exact = lsq_linear(R, (V.T @ g) / np.sqrt(w), bounds=(lo, hi), method="bvls").x
    np.testing.assert_allclose(y, exact, atol=1e-9)
    assert np.all(y[side < 0] == lo[side < 0]) and np.all(y[side > 0] == hi[side > 0])
    assert np.all((lo <= y) & (y <= hi))


def test_a_spent_budget_still_returns_a_descent_step():
    rng = np.random.default_rng(3)
    n = 40
    J = rng.standard_normal((n, n)) @ np.diag(np.logspace(0, -4, n))
    H, g = J.T @ J, J.T @ rng.standard_normal(n)
    lo, hi = np.full(n, -0.05), np.full(n, 0.05)
    y, _ = bccg.projected_cg(H, g, lo, hi, budget=3)
    assert np.all((lo <= y) & (y <= hi))
    assert _model(H, g, y) < 0.0


def _banded_box_qp(n: int = 300, seed: int = 4):
    """A Pawley-shaped bounded model: each column of J a window of 20 rows
    overlapping its neighbours', so H = JᵀJ is banded, with a floor at 0 that
    about a third of the variables would cross unbounded."""
    from scipy import sparse

    rng = np.random.default_rng(seed)
    m = 4 * n + 20
    rows = np.concatenate([np.arange(4 * j, 4 * j + 20) for j in range(n)])
    cols = np.repeat(np.arange(n), 20)
    J = sparse.csc_matrix((rng.uniform(0.2, 1.0, len(rows)), (rows, cols)),
                          shape=(m, n))
    g = J.T @ (J @ rng.uniform(-0.5, 1.0, n))
    return (J.T @ J).tocsr(), g, np.zeros(n), np.full(n, np.inf)


def test_a_sparse_h_is_preconditioned_to_the_dense_minimiser():
    """WP-2011: a sparse H takes CG preconditioned by the free block's
    incomplete LU.  It must land on the minimiser the dense, unpreconditioned
    solve reaches, put the same variables on their floor and lower the
    model."""
    H, g, lo, hi = _banded_box_qp()
    n = len(g)
    y_dense, side_dense = bccg.projected_cg(H.toarray(), g, lo, hi, budget=200 * n)
    y, side = bccg.projected_cg(H, g, lo, hi, budget=200 * n)
    np.testing.assert_allclose(y, y_dense, rtol=0.0,
                               atol=1e-8 * float(np.max(np.abs(y_dense))))
    assert np.array_equal(side, side_dense) and np.count_nonzero(side) > n // 10
    assert np.all(y[side < 0] == 0.0)
    assert _model(H.toarray(), g, y) < 0.0


def test_a_failed_factorisation_falls_back_to_plain_cg(monkeypatch):
    """A factor that cannot be built leaves the CG unpreconditioned, and the
    solve still reaches the same minimiser."""
    H, g, lo, hi = _banded_box_qp(n=150, seed=2)
    n = len(g)
    y_dense, _ = bccg.projected_cg(H.toarray(), g, lo, hi, budget=200 * n)

    def singular(_):
        raise RuntimeError("Factor is exactly singular")

    monkeypatch.setattr(bccg, "spilu", singular)
    y, _ = bccg.projected_cg(H, g, lo, hi, budget=200 * n)
    np.testing.assert_allclose(y, y_dense, rtol=0.0,
                               atol=1e-8 * float(np.max(np.abs(y_dense))))


class _Counting(np.ndarray):
    """A dense H that counts its products, the cost :func:`bccg.projected_cg`
    budgets."""

    products = 0

    def __matmul__(self, v):
        type(self).products += 1
        return np.asarray(self) @ v


def _paired_box_qp(n_pairs: int = 100, seed: int = 1):
    """A pseudo-symmetric Pawley block: reflections in pairs a fraction of a
    width apart, the data pulling one of each pair below its floor at 0."""
    rng = np.random.default_rng(seed)
    m = 8 * n_pairs + 50
    x = np.arange(m, dtype=float)
    cols = [np.exp(-0.5 * ((x - 8 * j - 15 - off) / 3.0) ** 2)
            for j in range(n_pairs) for off in (0.0, 2.0)]
    J = np.array(cols).T
    truth = np.zeros(2 * n_pairs)
    truth[0::2] = rng.uniform(0.5, 1.5, n_pairs)
    obs = J @ truth - 0.3 * J[:, 1::2].sum(axis=1) + 0.01 * rng.standard_normal(m)
    n = 2 * n_pairs
    return J, obs, J.T @ J, J.T @ obs, np.zeros(n), np.full(n, np.inf)


def test_a_projected_search_activates_many_bounds_at_once():
    """WP-2011: the subspace step's projected search (Lin & Moré 1999) puts
    many variables on their floor in one step.  Cutting the CG step at the
    first bound puts one there per restart, at least two Hessian products
    each, so the 99 floors here cost that path over 2·99 (measured: 203
    against 24, n = 200).  The search reaches the box minimiser the dense
    active-set solve finds."""
    from scipy.optimize import lsq_linear

    J, obs, H, g, lo, hi = _paired_box_qp()
    n = len(g)
    exact = lsq_linear(J, obs, bounds=(lo, hi), method="bvls").x
    _Counting.products = 0
    y, side = bccg.projected_cg(H.view(_Counting), g, lo, hi)
    np.testing.assert_allclose(y, exact, rtol=0.0,
                               atol=1e-6 * float(np.max(np.abs(exact))))
    on_floor = int(np.count_nonzero(side < 0))
    assert np.all(y[side < 0] == 0.0) and on_floor > n // 4
    assert _Counting.products < on_floor


def test_a_singular_dense_block_is_factored_shifted(monkeypatch):
    """WP-2011: at λ = 0 a Pawley block whose reflections coincide is
    singular.  The worst systems of probe 17's zircon and FAP candidates had
    23-54 eigenvalues within 2e-15 of zero, some of them negative, so the
    Cholesky factorisation of the free block failed and the face step was
    unpreconditioned CG.  The block's diagonal is raised until the
    factorisation succeeds, as Lin & Moré's ICFS does, and the solve reaches
    the box minimiser's model value within its default budget."""
    from scipy.optimize import lsq_linear

    J, obs, _, _, lo, hi = _paired_box_qp(n_pairs=60, seed=3)
    J = np.column_stack([J, J[:, 0]])   # one reflection twice
    H, g = J.T @ J, J.T @ obs
    n = len(g)
    lo, hi = np.zeros(n), np.full(n, np.inf)
    # the null direction's eigenvalue at -1e-15 of the diagonal, as measured
    v = np.zeros(n)
    v[0], v[-1] = 1.0, -1.0
    H -= 0.5e-15 * float(H[0, 0]) * np.outer(v, v)
    with pytest.raises(np.linalg.LinAlgError):
        np.linalg.cholesky(H)
    free = np.ones(n, dtype=bool)
    assert isinstance(bccg._factor(H, free), bccg._Cholesky)
    exact = lsq_linear(J, obs, bounds=(lo, hi), method="bvls").x
    _Counting.products = 0
    y, _ = bccg.projected_cg(H.view(_Counting), g, lo, hi)
    assert np.all((lo <= y) & (y <= hi))
    assert _model(H, g, y) == pytest.approx(_model(H, g, exact), rel=1e-9)
    # measured: 29 products shifted, 169 unpreconditioned, of 242 budgeted
    assert _Counting.products < n // 2
    monkeypatch.setattr(bccg, "_CHOLESKY_SHIFTS", 1)
    assert bccg._factor(H, free) is None
