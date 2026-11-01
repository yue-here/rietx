"""Bounded Levenberg-Marquardt driver (WP-0601, Coelho 2018 + 2005).

The load-bearing test here is :func:`test_ru_is_one_on_a_linear_model`: the
λ schedule is fed ``r_u = ΔS_t/ΔS``, and the paper's printed ``ΔS_t = Δpᵀb``
has a sign that makes ``r_u < 0`` for every descent step.  The identity
``r_u ≡ 1`` on an exactly linear model is the only way to know the schedule is
receiving the quantity its constants (0.4, 1, 10) were tuned against.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import least_squares as scipy_lsq

from rietx.optimize import lm


# ----------------------------------------------------------------------
# problems
# ----------------------------------------------------------------------
def _linear_problem(n_data=40, n_par=4, seed=0):
    """r(θ) = Xθ − y — exactly quadratic S, so the GN step is exact."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_data, n_par))
    y = rng.standard_normal(n_data)

    def residual(theta):
        return X @ theta - y

    def jacobian(theta):
        return X

    return residual, jacobian, np.linalg.lstsq(X, y, rcond=None)[0]


def _rosenbrock():
    """Classic non-quadratic pair; S = 100(x₂−x₁²)² + (1−x₁)², minimum (1, 1)."""
    def residual(t):
        return np.array([10.0 * (t[1] - t[0] ** 2), 1.0 - t[0]])

    def jacobian(t):
        return np.array([[-20.0 * t[0], 10.0], [-1.0, 0.0]])

    return residual, jacobian, np.array([1.0, 1.0])


def _exponential_problem(seed=3):
    """y = a·exp(b·x) + c — the shape a peak-height/width pair really has."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 3.0, 60)
    truth = np.array([2.5, -0.8, 0.4])
    y = truth[0] * np.exp(truth[1] * x) + truth[2]
    y = y + 0.01 * rng.standard_normal(len(x))

    def residual(t):
        return t[0] * np.exp(t[1] * x) + t[2] - y

    def jacobian(t):
        e = np.exp(t[1] * x)
        return np.column_stack([e, t[0] * x * e, np.ones_like(x)])

    return residual, jacobian, truth


_UNBOUNDED = (np.full(4, -np.inf), np.full(4, np.inf))


# ----------------------------------------------------------------------
# the sign calibration
# ----------------------------------------------------------------------
def test_ru_is_one_on_a_linear_model(monkeypatch):
    """ΔS_t = −Δθᵀb, verified against the exact-quadratic identity r_u ≡ 1.

    With r(θ+Δ) = r + JΔ: S(θ+Δ) = S − 2Δᵀb + ΔᵀAΔ, and at the exact
    Gauss-Newton step Δ = A⁻¹b that is S − Δᵀb.  So ΔS = −Δᵀb = ΔS_t exactly,
    and any other sign or factor shows up here immediately.  The paper's
    printed ``ΔS_t = Δpᵀb`` would give −1.
    """
    seen: list[float] = []
    real = lm._next_lambda

    def spy(lam, r_u, q):
        if r_u is not None:
            seen.append(r_u)
        return real(lam, r_u, q)

    monkeypatch.setattr(lm, "_next_lambda", spy)

    residual, jacobian, ref = _linear_problem()
    out = lm.minimize(residual, jacobian, np.zeros(4),
                      lo=_UNBOUNDED[0], hi=_UNBOUNDED[1])

    assert np.allclose(out.x, ref, atol=1e-9)
    assert seen, "no accepted step was scored"
    # the first step is taken at λ = 0, i.e. the exact GN step on an exactly
    # quadratic S — the identity has to hold to round-off there
    assert seen[0] == pytest.approx(1.0, abs=1e-9)


def test_lambda_schedule_branches():
    """Coelho (2018) equation (9), branch by branch."""
    # (i) failed step: 10·max(λ, 0.1)
    assert lm._next_lambda(0.0, None, 0.0) == pytest.approx(1.0)
    assert lm._next_lambda(5.0, None, 0.0) == pytest.approx(50.0)
    # (iii) good step at or under the quadratic prediction: m_u·λ/2
    assert lm._next_lambda(2.0, 1.0, 0.0) == pytest.approx(1.0)
    assert lm._next_lambda(2.0, 0.1, 0.0) == pytest.approx(0.4)   # m_u floored at 0.4
    # (iv) good step that overshoots: m_u(λ + ½) − ½ — damping although S fell
    assert lm._next_lambda(0.0, 2.0, 0.0) == pytest.approx(0.5)
    assert lm._next_lambda(1.0, 3.0, 0.0) == pytest.approx(4.0)
    # m_u capped at 10
    assert lm._next_lambda(0.0, 1e6, 0.0) == pytest.approx(4.5)
    # (ii) the rare Q_u > 5 branch: λ/10 even though the step was good
    assert lm._next_lambda(20.0, 3.0, 6.0) == pytest.approx(2.0)


def test_overshoot_damps_even_though_the_step_lowered_s():
    """The whole novelty of λ_new: λ rises after a *successful* step.

    Condition (iv) fires when r_u > 1, i.e. the linear prediction promised more
    than the step delivered — the step went too far.  λ_std would only ever cut
    λ here, so the shorter step it needs never happens.
    """
    assert lm._next_lambda(0.0, 5.0, 0.0) > 0.0


# ----------------------------------------------------------------------
# it actually minimises
# ----------------------------------------------------------------------
def test_linear_problem_converges_in_one_step():
    residual, jacobian, ref = _linear_problem()
    out = lm.minimize(residual, jacobian, np.zeros(4),
                      lo=_UNBOUNDED[0], hi=_UNBOUNDED[1])
    assert np.allclose(out.x, ref, atol=1e-10)
    assert out.status > 0


def test_a_start_at_the_minimum_is_converged():
    """Nothing downhill on the first outer iteration is convergence, as on any
    later one (WP-1937; it was ``status = -1``, read as "diverged")."""
    residual, jacobian, ref = _linear_problem()
    out = lm.minimize(residual, jacobian, ref.copy(),
                      lo=_UNBOUNDED[0], hi=_UNBOUNDED[1])
    assert out.status > 0
    assert out.termination in {"exhausted_fp64", "no_descent"}


def test_a_non_finite_start_is_refused_not_converged():
    """With first-iteration "diverged" gone, a nan cost would reject every
    trial and read as convergence; the start is refused instead, as TRF does."""
    def residual(t):
        return np.array([t[0] - 1.0, np.nan])

    def jacobian(t):
        return np.array([[1.0], [0.0]])

    with pytest.raises(ValueError, match="not finite"):
        lm.minimize(residual, jacobian, np.zeros(1),
                    lo=np.full(1, -np.inf), hi=np.full(1, np.inf))


def test_the_budget_is_in_residual_evaluations():
    """``max_nfev`` caps what scipy's ``max_nfev`` caps: residual evaluations,
    the initial one included."""
    residual, jacobian, _ = _rosenbrock()
    calls = []

    def counting(t):
        calls.append(t)
        return residual(t)

    out = lm.minimize(counting, jacobian, np.array([-1.2, 1.0]),
                      lo=np.full(2, -np.inf), hi=np.full(2, np.inf), max_nfev=7)
    assert out.nfev == len(calls) == 7
    assert out.status == 0
    assert out.termination == "max_nfev"


@pytest.mark.parametrize("start", [[-1.2, 1.0], [2.0, 2.0], [0.0, 0.0]])
def test_rosenbrock(start):
    residual, jacobian, ref = _rosenbrock()
    out = lm.minimize(residual, jacobian, np.array(start, dtype=float),
                      lo=np.full(2, -np.inf), hi=np.full(2, np.inf),
                      max_nfev=1600)
    assert np.allclose(out.x, ref, atol=1e-5)


def test_matches_scipy_trf_on_a_nonlinear_fit():
    """Same minimum as the reference driver, from the same start."""
    residual, jacobian, truth = _exponential_problem()
    x0 = np.array([1.0, -0.3, 0.0])
    lo, hi = np.full(3, -np.inf), np.full(3, np.inf)

    ours = lm.minimize(residual, jacobian, x0.copy(), lo=lo, hi=hi, max_nfev=800)
    theirs = scipy_lsq(residual, x0.copy(), jac=jacobian, method="trf",
                       ftol=1e-12, xtol=1e-12, gtol=1e-12)

    assert ours.cost == pytest.approx(theirs.cost, rel=1e-6)
    assert np.allclose(ours.x, theirs.x, rtol=1e-4, atol=1e-6)
    assert np.allclose(ours.x, truth, rtol=0.05)


def test_returns_jacobian_and_residual_at_the_returned_point():
    """``covariance_estimates`` reads both; a stale one mis-scales every esd."""
    residual, jacobian, _ = _exponential_problem()
    out = lm.minimize(residual, jacobian, np.array([1.0, -0.3, 0.0]),
                      lo=np.full(3, -np.inf), hi=np.full(3, np.inf))
    assert np.allclose(out.fun, residual(out.x))
    assert np.allclose(out.jac, jacobian(out.x))
    assert out.cost == pytest.approx(0.5 * float(out.fun @ out.fun))


# ----------------------------------------------------------------------
# constraints
# ----------------------------------------------------------------------
def test_bounds_are_never_violated():
    residual, jacobian, free = _linear_problem(seed=2)
    lo = np.full(4, -np.inf)
    hi = np.full(4, np.inf)
    # bind the two largest components well inside their free values
    for i in np.argsort(-np.abs(free))[:2]:
        if free[i] > 0:
            hi[i] = 0.5 * free[i]
        else:
            lo[i] = 0.5 * free[i]

    out = lm.minimize(residual, jacobian, np.zeros(4), lo=lo, hi=hi, max_nfev=800)
    assert np.all(out.x >= lo - 1e-12)
    assert np.all(out.x <= hi + 1e-12)
    assert out.n_bound_hits > 0
    # and the constrained optimum is worse than the free one, as it must be
    assert out.cost > 0.5 * float(residual(free) @ residual(free)) - 1e-12


def test_linear_inequality_keeps_every_iterate_feasible():
    """T·θ + c ≥ 0 on a functional of θ — what a box cannot express.

    Constrain θ₀ + θ₁ ≥ 0 on a problem whose unconstrained solution violates
    it, and check the returned point is feasible and sits on the boundary.
    """
    residual, jacobian, free = _linear_problem(seed=4)
    T = np.zeros((1, 4))
    T[0, 0] = T[0, 1] = 1.0
    offset = -(free[0] + free[1]) / 2.0    # the free solution violates it
    cone = lm.LinearInequality(T=T, c=np.array([offset]), label="test")
    assert cone.violated(free)[0]

    out = lm.minimize(residual, jacobian, np.zeros(4),
                      lo=np.full(4, -np.inf), hi=np.full(4, np.inf),
                      inequalities=[cone], max_nfev=1200)

    slack = float((T @ out.x + cone.c)[0])
    assert out.n_truncated > 0
    assert out.truncated_by == {"test": out.n_truncated}
    # the step solves the rows exactly, so the answer is on the surface to
    # rounding, where truncation left it 0.5 % short of each step's crossing
    assert abs(slack) < 1e-12 * (np.abs(T) @ np.abs(out.x) + abs(offset))


def test_a_row_left_on_its_face_by_rounding_is_not_violated():
    """The builders drop a block or row the stage's start violates.  An exact
    step leaves a row on its face to rounding, either side of zero, and a
    strict test handed the next stage no cone: brucite + Stephens left a row
    at −1.5e-11 against a largest σ²(M) of 6.3e6, and the stages after took 19
    of 43 reflections out of the cone (``test_acceptance_stephens``)."""
    rows = lm.LinearInequality(T=np.array([[1.0, -1.0], [1.0, 1.0]]), c=np.zeros(2))
    on_face = np.array([1.0, 1.0 + 4.0 * np.finfo(float).eps])
    assert rows.slack(on_face)[0] < 0.0
    assert not rows.violated(on_face).any()
    assert rows.violated(np.array([1.0, 1.1])).tolist() == [True, False]


def test_a_block_whose_every_row_is_on_its_face_is_not_violated():
    """With every row on its face the largest |slack| is itself a rounding,
    so a test against it alone is strict again.  The Lorentzian width block
    at X = Y = 0 is that block: a stage left them at 4e-22 and −4e-21, and the
    next one was built with no row (WP-2003, X16).  The guards floor their
    scale at 1 in the row's units, and so does this test."""
    th = np.radians(np.linspace(1.5, 10.0, 10))
    rows = lm.LinearInequality(T=np.column_stack([1.0 / np.cos(th), np.tan(th)]),
                               c=np.zeros(th.size))
    on_face = np.array([4e-22, -4e-21])
    assert (rows.slack(on_face) < 0.0).any()
    assert not rows.violated(on_face).any()
    # a genuine violation of a few millidegrees still reads as one
    assert rows.violated(np.array([0.0, -0.0137])).all()


def test_inactive_inequality_changes_nothing():
    residual, jacobian, _ = _exponential_problem()
    x0 = np.array([1.0, -0.3, 0.0])
    lo, hi = np.full(3, -np.inf), np.full(3, np.inf)
    free = lm.minimize(residual, jacobian, x0.copy(), lo=lo, hi=hi, max_nfev=800)

    T = np.zeros((1, 3))
    T[0, 0] = 1.0
    slack = lm.LinearInequality(T=T, c=np.array([1e6]), label="slack")
    constrained = lm.minimize(residual, jacobian, x0.copy(), lo=lo, hi=hi,
                              inequalities=[slack], max_nfev=800)

    assert constrained.n_truncated == 0
    assert np.array_equal(constrained.x, free.x)
    assert (constrained.cost, constrained.nfev) == (free.cost, free.nfev)


def _collinear_pair():
    """Two columns 30 % apart in shape, an exactly linear residual and the
    unconstrained minimum at (1, 1)."""
    x = np.linspace(-1.0, 1.0, 50)
    X = np.column_stack([x, x + 0.3 * x * x])
    y = X @ np.ones(2)
    return (lambda t: X @ t - y), (lambda t: X), X, y


def _truncated_step(A, b, lam, x, lo, hi, inequalities, *, n_rows, scale=None):
    """The rule before WP-1938 D8, kept here as the counterfactual: the
    box-only step, projected off rows already on their face and shortened to
    99.5 % of the way to the first row it reaches."""
    step, _ = lm._solve_step(A, b, lam, x, lo, hi, n_rows=n_rows, scale=scale)
    for iq in inequalities:
        g0 = iq.slack(x)
        rows = iq.T[g0 <= 1e-9 * max(float(np.max(np.abs(g0))), 1.0)]
        rows = rows[rows @ step < 0.0]
        if len(rows):
            mu = np.linalg.lstsq(rows @ rows.T, rows @ step, rcond=None)[0]
            step = step - rows.T @ mu
    tau = min(iq.max_feasible_fraction(x, step) for iq in inequalities)
    return (0.995 * tau if tau < 1.0 else 1.0) * step, np.zeros(len(x), dtype=np.int8)


def test_the_step_reaches_a_face_where_truncation_stalls(monkeypatch):
    """WP-1938 D8's case in two parameters: the optimum on a row's face.

    The constrained optimum of an exactly linear residual has a closed form,
    θ* = θ_u + (β − aᵀθ_u)/(aᵀA⁻¹a)·A⁻¹a.  The exact step is the model's
    constrained minimiser, so one step lands there.  The truncated step runs
    along the Newton direction towards θ_u and stops at the face.  The next
    one points at θ_u again from almost the same line, so it meets the face
    at almost the same point.

    A change of 1e-15 in the start picks one of two ways of failing, and the
    platform picks too.  The fit stops ``exhausted_fp64`` after 7 evaluations,
    2.1 from θ* with S 70 % above its minimum, as brucite + Stephens stopped
    on the cone.  Or it crawls along the face to the 400-evaluation cap and
    stops 0.83 from θ* with S 11 % above, which Linux CI does from (3, 3).
    The three starts below take both on macOS arm64, and the test asserts
    what both share.
    """
    residual, jacobian, X, y = _collinear_pair()
    a = np.array([np.cos(0.7), np.sin(0.7)])
    beta = float(a @ np.ones(2)) + 0.5       # the free minimum violates aᵀθ ≥ β
    row = lm.LinearInequality(T=a[None, :], c=np.array([-beta]), label="face")
    A = X.T @ X
    free = np.linalg.solve(A, X.T @ y)
    A_inv_a = np.linalg.solve(A, a)
    star = free + (beta - a @ free) / (a @ A_inv_a) * A_inv_a
    s_star = float(residual(star) @ residual(star))
    inf = np.full(2, np.inf)
    x0 = np.array([3.0, 3.0])

    out = lm.minimize(residual, jacobian, x0, lo=-inf, hi=inf, inequalities=[row])
    assert out.status == 1 and out.nfev <= 3
    assert np.allclose(out.x, star, rtol=0.0, atol=1e-12)
    assert 2.0 * out.cost == pytest.approx(s_star, rel=1e-12)
    assert out.n_truncated >= 1

    monkeypatch.setattr(lm, "_solve_constrained_step", _truncated_step)
    for nudge in (0.0, 1e-15, -1e-14):
        start = x0 * np.array([1.0, 1.0 + nudge])
        stalled = lm.minimize(residual, jacobian, start, lo=-inf, hi=inf,
                              inequalities=[row])
        assert stalled.termination in ("exhausted_fp64", "max_nfev")
        assert np.linalg.norm(stalled.x - star) > 0.5
        assert 2.0 * stalled.cost > 1.05 * s_star


def test_a_step_that_crosses_no_row_is_the_box_step_bit_for_bit(monkeypatch):
    """WP-1938 D8 changes a step only where a row binds.  Every trial of a fit
    whose rows never bind is the bounded solve's step landed on its bounds,
    to the bit, with no inequality block and with one that never binds."""
    residual, jacobian, free = _linear_problem(seed=2)
    lo, hi = np.full(4, -np.inf), np.full(4, np.inf)
    i = int(np.argmax(np.abs(free)))
    lo[i], hi[i] = (-np.inf, 0.5 * free[i]) if free[i] > 0 else (0.5 * free[i], np.inf)
    far = lm.LinearInequality(T=np.ones((1, 4)), c=np.array([1e6]), label="far")

    def refused(*args, **kwargs):
        raise AssertionError("the constrained solve ran where no row binds")

    monkeypatch.setattr(lm, "_solve_constrained_step", refused)
    real = lm._solve_step
    for blocks in ([], [far]):
        steps, trials = [], []

        def spy(A, b, lam, x, lo_, hi_, *, n_rows, scale=None):
            step, side = real(A, b, lam, x, lo_, hi_, n_rows=n_rows, scale=scale)
            landed = np.where(side < 0, lo_, np.where(side > 0, hi_,
                                                      np.clip(x + step, lo_, hi_)))
            steps.append(landed)
            return step, side

        monkeypatch.setattr(lm, "_solve_step", spy)
        out = lm.minimize(residual, jacobian, np.zeros(4), lo=lo, hi=hi,
                          inequalities=blocks, max_nfev=200,
                          on_trial=lambda x, *rest: trials.append(x.copy()))
        assert out.n_bound_hits == 1 and out.n_truncated == 0 and trials
        assert all(np.array_equal(t, s) for t, s in zip(trials, steps))


def _kkt_rows(H, g, step, G, h):
    """Largest breach, relative, of ``min ½sᵀHs − gᵀs`` s.t. ``Gs ≥ h``:
    (most negative row slack, stationarity residual).  The multipliers are
    the non-negative combination of near-active rows closest to the
    gradient."""
    from scipy.optimize import nnls

    scale = np.linalg.norm(G, axis=1) * np.linalg.norm(step) + np.abs(h)
    slack = (G @ step - h) / scale
    near = slack <= 1e-9
    grad = H @ step - g
    _, res = nnls(G[near].T, grad) if near.any() else (None, np.linalg.norm(grad))
    return float(slack.min()), res / np.linalg.norm(g)


def _crossing_problem(seed):
    """A box, twelve rows and a model whose box-only step crosses a row."""
    rng = np.random.default_rng(seed)
    n = 6
    J = rng.standard_normal((80, n)) @ np.diag(10.0 ** rng.uniform(-3, 3, n))
    if seed >= 4:
        J[:, -1] = 2.0 * J[:, 0]
    A = J.T @ J
    d = np.sqrt(np.diag(A))
    b = J.T @ rng.standard_normal(80) * 100.0
    x = rng.standard_normal(n)
    lo = x - np.where(rng.random(n) < 0.5, 0.05 / d, np.inf)
    hi = x + np.where(rng.random(n) < 0.3, 0.05 / d, np.inf)
    T = rng.standard_normal((12, n)) / d
    rows = lm.LinearInequality(T=T, c=-T @ x + rng.uniform(0.0, 0.05, 12))
    lam = 0.0 if seed % 2 == 0 else 1e-3
    box, _ = lm._solve_step(A, b, lam, x, lo, hi, n_rows=80)
    assert rows.crossed(x, box), "the case was meant to bind a row"
    # the problem in the equilibrated variable s = d·Δ, where it is O(1)
    H = A / np.outer(d, d) + lam * np.eye(n)
    eye = np.eye(n)
    has_lo, has_hi = np.isfinite(lo), np.isfinite(hi)
    G = np.vstack([eye[has_lo], -eye[has_hi], T / d])
    h = np.concatenate([((lo - x) * d)[has_lo], -((hi - x) * d)[has_hi],
                        -rows.slack(x)])
    return A, b, lam, x, lo, hi, rows, box, d, H, G, h


@pytest.mark.parametrize("seed", range(6))
def test_the_constrained_step_is_the_exact_minimiser(seed):
    """The step over the box and the rows satisfies the problem's optimality
    conditions to rounding: every row held, and the gradient a non-negative
    combination of the active ones.  Seeds 4 and 5 are rank-deficient at
    λ = 0, where the eigenvalue cut binds."""
    A, b, lam, x, lo, hi, rows, box, d, H, G, h = _crossing_problem(seed)
    step, side = lm._solve_constrained_step(A, b, lam, x, lo, hi, [rows], n_rows=80)
    worst_row, stationarity = _kkt_rows(H, b / d, step * d, G, h)
    assert worst_row > -1e-11
    if seed < 4:                      # exact only where the model is not flat
        assert stationarity < 1e-8
    # a variable it puts on a bound is reported there, for the exact landing
    for k in np.flatnonzero(side):
        bound = lo[k] if side[k] < 0 else hi[k]
        assert x[k] + step[k] == pytest.approx(bound, rel=1e-12, abs=1e-12 / d[k])
    # and it is never worse for the model than the box step cut to the rows
    tau = rows.max_feasible_fraction(x, box)

    def model(D):
        return 0.5 * D @ (A + lam * np.diag(d * d)) @ D - b @ D

    assert model(step) <= model(tau * box) + 1e-12 * abs(model(tau * box))


def test_a_capped_optimality_check_keeps_the_least_distance_point(monkeypatch):
    """The polish is kept only once an nnls call shows the gradient a
    non-negative combination of its rows, and that call has a cap too.
    Capped, the polish is unverified and the least-distance point is the step,
    where the uncaught RuntimeError ended the whole fit."""
    A, b, lam, x, lo, hi, rows, box, d, H, G, h = _crossing_problem(0)
    real = lm.nnls
    checks = []

    def capped_check(E, f, maxiter=None):
        if maxiter is None:                 # only the optimality check passes none
            checks.append(1)
            raise RuntimeError("Maximum number of iterations reached.")
        return real(E, f, maxiter=maxiter)

    monkeypatch.setattr(lm, "nnls", capped_check)
    step, _ = lm._solve_constrained_step(A, b, lam, x, lo, hi, [rows], n_rows=80)
    assert checks == [1]
    worst_row, _ = _kkt_rows(H, b / d, step * d, G, h)
    assert worst_row > -1e-9


def test_a_failed_constrained_solve_falls_back_to_the_first_row(monkeypatch):
    """nnls can stop at its iteration cap.  The step is then the box-only
    step shortened to the first row it reaches, and the fit stays feasible."""
    residual, jacobian, X, y = _collinear_pair()
    a = np.array([np.cos(0.7), np.sin(0.7)])
    row = lm.LinearInequality(T=a[None, :], c=np.array([-(a @ np.ones(2) + 0.5)]))

    def capped(*args, **kwargs):
        raise RuntimeError("Maximum number of iterations reached.")

    monkeypatch.setattr(lm, "nnls", capped)
    inf = np.full(2, np.inf)
    out = lm.minimize(residual, jacobian, np.array([3.0, 3.0]), lo=-inf, hi=inf,
                      inequalities=[row])
    assert out.n_truncated >= 1
    assert float(row.slack(out.x)[0]) >= 0.0


def test_empty_parameter_vector():
    def residual(theta):
        return np.array([1.0, 2.0])

    def jacobian(theta):
        return np.zeros((2, 0))

    out = lm.minimize(residual, jacobian, np.zeros(0),
                      lo=np.zeros(0), hi=np.zeros(0))
    assert out.x.shape == (0,)
    assert out.cost == pytest.approx(2.5)


def test_residual_must_be_fp64():
    """Invariant 2 at the driver boundary: a reduced-precision residual raises."""
    def residual(theta):
        return np.zeros(3, dtype=np.float32)

    def jacobian(theta):
        return np.zeros((3, 2))

    with pytest.raises(TypeError, match="fp64"):
        lm.minimize(residual, jacobian, np.zeros(2),
                    lo=np.full(2, -np.inf), hi=np.full(2, np.inf))


def test_callback_sees_every_accepted_point():
    seen = []
    residual, jacobian, _ = _exponential_problem()
    lm.minimize(residual, jacobian, np.array([1.0, -0.3, 0.0]),
                lo=np.full(3, -np.inf), hi=np.full(3, np.inf),
                callback=lambda x, cost: seen.append(cost))
    assert len(seen) >= 2
    assert seen == sorted(seen, reverse=True)   # accepted steps only ⇒ monotone


# ----------------------------------------------------------------------
# the bounded step (WP-1937): exact, and on its bound rather than near it
# ----------------------------------------------------------------------
def _kkt_violation(A, b, step, lo, hi):
    """Largest breach of the bounded quadratic's optimality conditions.

    The model is ½ΔᵀAΔ − bᵀΔ, so its gradient is g = AΔ − b: zero on a free
    variable, ≥ 0 on one held at its lower bound, ≤ 0 at its upper.
    """
    g = A @ step - b
    at_lo = np.isclose(step, lo, rtol=0.0, atol=1e-12)
    at_hi = np.isclose(step, hi, rtol=0.0, atol=1e-12)
    free = ~(at_lo | at_hi)
    return max(np.max(np.abs(g[free]), initial=0.0),
               np.max(-g[at_lo], initial=0.0),
               np.max(g[at_hi], initial=0.0))


@pytest.mark.parametrize("seed", range(5))
def test_step_is_the_exact_minimiser_of_the_bounded_model(seed):
    """The step satisfies the bounded quadratic's KKT conditions to round-off,
    where BCCG stopped once ‖AΔ − b‖² had fallen 10⁴-fold."""
    rng = np.random.default_rng(seed)
    J = rng.standard_normal((60, 6)) @ np.diag([1e3, 1.0, 1.0, 1e-2, 5.0, 1.0])
    A = J.T @ J
    b = rng.standard_normal(6) * np.sqrt(np.diag(A))
    x = np.zeros(6)
    lo = np.array([-np.inf, -0.1, 0.0, -np.inf, -1e-3, 0.0])
    hi = np.array([np.inf, 0.1, np.inf, 1e-3, np.inf, 0.0 + 1e-9])
    step, side = lm._solve_step(A, b, 0.0, x, lo, hi, n_rows=60)
    assert np.all(step >= lo - 1e-15) and np.all(step <= hi + 1e-15)
    scale = np.max(np.abs(b))
    assert _kkt_violation(A, b, step, lo, hi) < 1e-9 * scale
    assert np.any(side != 0), "the case was meant to bind at least one bound"


def test_a_rank_deficient_system_gets_a_finite_minimum_norm_step():
    """Two identical columns: A is singular at λ = 0, and the cut discards the
    null direction rather than stepping along it without limit."""
    rng = np.random.default_rng(7)
    J = rng.standard_normal((40, 3))
    J = np.column_stack([J, J[:, 0]])
    A, b = J.T @ J, J.T @ rng.standard_normal(40)
    inf = np.full(4, np.inf)
    step, _ = lm._solve_step(A, b, 0.0, np.zeros(4), -inf, inf, n_rows=40)
    assert np.all(np.isfinite(step))
    assert step[0] == pytest.approx(step[3], rel=1e-9)
    assert np.allclose(A @ step, b, atol=1e-9 * np.max(np.abs(b)))


def test_widths_pressed_on_zero_together_reach_the_bound_exactly():
    """Several non-negative terms whose free optimum is negative, coupled
    through near-collinear columns — WP-1929's QARR shape in miniature.  The
    driver lands each on 0.0 exactly, and the residual's descent direction
    points out of the box there."""
    rng = np.random.default_rng(11)
    x_axis = np.linspace(-3.0, 3.0, 200)
    basis = np.column_stack([np.exp(-(x_axis / w) ** 2) for w in (1.0, 1.05, 1.1, 1.15)])
    basis = np.column_stack([basis, np.ones_like(x_axis)])
    truth = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
    y = basis @ truth - 0.05 * basis[:, 1] + 0.001 * rng.standard_normal(len(x_axis))
    # floors at awkward values, so that x + (lo − x) computed through the
    # step's scaling need not round back to lo
    floor = np.array([0.1, 1.0 / 3.0, 0.7, 2.0 / 7.0])

    def residual(t):
        return basis @ np.concatenate([t[:4] - floor, t[4:]]) - y

    def jacobian(t):
        return basis

    lo = np.concatenate([floor, [-np.inf]])
    hi = np.full(5, np.inf)
    out = lm.minimize(residual, jacobian, np.array([0.9, 0.9, 0.9, 0.9, 0.5]),
                      lo=lo, hi=hi, max_nfev=200)
    assert out.status > 0
    pinned = out.x[:4] == floor
    assert pinned.sum() >= 2
    grad = basis.T @ residual(out.x)       # ½∇S
    assert np.all(grad[:4][pinned] > 0.0)  # S would fall only below the bound
    # and nothing is left a rounding error above its floor
    assert np.all(pinned | (out.x[:4] - floor > 1e-9))
    # the active set is exactly the pinned floors
    assert out.active_mask.tolist() == [-1 if p else 0 for p in pinned] + [0]


def test_a_block_above_the_bvls_cut_takes_the_projected_cg_step(monkeypatch):
    """A Pawley-sized system is solved by projected CG inside the same box
    (WP-1953); BVLS's cost grows as n³ per active-set change
    (``BVLS_MAX_COLUMNS``).  On a well-conditioned system the two agree, and
    the variables the CG puts on a bound are reported, so the driver lands
    them exactly as it does BVLS's."""
    from rietx.optimize import bccg

    n = lm.BVLS_MAX_COLUMNS + 1
    rng = np.random.default_rng(5)
    J = rng.standard_normal((3 * n, n))
    A, b = J.T @ J, J.T @ rng.standard_normal(3 * n)
    lo, hi = np.zeros(n), np.full(n, np.inf)
    calls = []
    real = bccg.projected_cg
    monkeypatch.setattr(bccg, "projected_cg",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    step, side = lm._solve_step(A, b, 0.0, np.zeros(n), lo, hi, n_rows=3 * n)
    assert calls and side.any() and np.all(step[side < 0] == 0.0)
    assert np.all(step >= 0.0)
    monkeypatch.setattr(lm, "BVLS_MAX_COLUMNS", n)
    calls.clear()
    exact, exact_side = lm._solve_step(A, b, 0.0, np.zeros(n), lo, hi, n_rows=3 * n)
    assert not calls
    np.testing.assert_allclose(step, exact, atol=1e-9 * float(np.max(np.abs(exact))))
    assert np.array_equal(side, exact_side)


def test_a_sparse_normal_matrix_reaches_the_dense_answer():
    """WP-2011: ``normal_equations`` may hand the driver a sparse A above the
    BVLS cut, as a Pawley stage does, and the step is then the preconditioned
    projected CG's.  On a banded, mildly nonlinear fit with a floor that
    binds, both builds converge to the same point."""
    from scipy import sparse

    n = lm.BVLS_MAX_COLUMNS + 72
    rng = np.random.default_rng(8)
    m = 4 * n + 20
    rows = np.concatenate([np.arange(4 * j, 4 * j + 20) for j in range(n)])
    cols = np.repeat(np.arange(n), 20)
    B = sparse.csc_matrix((rng.uniform(0.2, 1.0, len(rows)), (rows, cols)),
                          shape=(m, n)).toarray()
    y = B @ rng.uniform(-0.5, 1.0, n) + 0.05 * rng.standard_normal(m)

    def residual(x):
        return y - B @ x - 0.1 * np.sin(B @ x)

    def jacobian(x):
        return -(B * (1.0 + 0.1 * np.cos(B @ x))[:, None])

    def sparse_normal(J, r):
        Js = sparse.csc_matrix(J)
        return (Js.T @ Js).tocsr(), -(Js.T @ r)

    lo, hi = np.zeros(n), np.full(n, np.inf)
    x0 = np.full(n, 0.5)
    dense = lm.minimize(residual, jacobian, x0, lo=lo, hi=hi)
    out = lm.minimize(residual, jacobian, x0, lo=lo, hi=hi,
                      normal_equations=sparse_normal)
    assert dense.status > 0 and out.status > 0
    assert np.count_nonzero(out.active_mask) > n // 10
    np.testing.assert_allclose(out.x, dense.x, rtol=0.0,
                               atol=1e-8 * float(np.max(np.abs(dense.x))))
    assert out.cost == pytest.approx(dense.cost, rel=1e-10)


def test_a_sparse_normal_matrix_takes_every_dense_operation():
    """The curvature the driver holds rewrites A's diagonal, and a sparse A
    at or under the cut is solved by BVLS on its dense copy, bit for bit."""
    from scipy import sparse

    rng = np.random.default_rng(2)
    J = rng.standard_normal((30, 10))
    A, b = J.T @ J, J.T @ rng.standard_normal(30)
    A[0, 9] = A[9, 0] = 0.0
    values = np.diag(A) + rng.uniform(0.0, 1.0, 10)
    As = sparse.csr_matrix(A)
    np.testing.assert_array_equal(lm._with_diagonal(As, values).toarray(),
                                  lm._with_diagonal(A.copy(), values))
    # a curvature far above the diagonal it replaces: a + (v − a) misses v by
    # an ulp on ~0.4 % of such entries, so the write must not take that route
    a = rng.uniform(1.0, 2.0, 4000)
    v = a * rng.uniform(3.0, 1000.0, 4000)
    np.testing.assert_array_equal(
        lm._with_diagonal(sparse.diags(a).tocsr(), v).diagonal(), v)
    lo, hi = np.full(10, -0.1), np.full(10, 0.1)
    dense = lm._solve_step(A, b, 0.3, np.zeros(10), lo, hi, n_rows=30)
    out = lm._solve_step(As, b, 0.3, np.zeros(10), lo, hi, n_rows=30)
    np.testing.assert_array_equal(out[0], dense[0])
    np.testing.assert_array_equal(out[1], dense[1])


def _vanishing_column():
    """φ enters only as φ²·bump against data carrying the opposite bump, so
    φ = 0 is the minimum, its column 2φ·bump vanishes there, and χ² keeps a
    curvature Gauss-Newton cannot see: a moment angle at a direction the
    symmetry fixes, or FCJ's H/L beside zero on ``test_e8``."""
    t = np.linspace(0.0, 3.0, 60)
    bump = np.exp(-0.5 * ((t - 1.5) / 0.2) ** 2)
    y = 2.0 * np.exp(-0.7 * t) + 0.4 * bump

    def residual(th):
        return y - th[0] * np.exp(-th[1] * t) + 0.5 * th[2] ** 2 * bump

    def jacobian(th):
        e = np.exp(-th[1] * t)
        return np.stack([-e, th[0] * t * e, th[2] * bump], axis=1)

    return residual, jacobian


def test_a_column_that_vanishes_at_its_minimum_keeps_its_scale(monkeypatch):
    """WP-1953: each column is scaled by the largest norm it has had this
    stage (Moré 1978).  Re-scaled to unit norm at every iteration instead,
    φ's shrinking column took the largest step, λ climbed to 1.7e10 to hold
    it, and three tiny decreases ended the run on ``ftol_runs`` at χ² 1.891
    with a and k far from their answer.  Held, it converges to the minimum
    with φ at 0, χ² 0.744854 (scipy's TRF on a and k alone agrees)."""
    residual, jacobian = _vanishing_column()
    x0 = np.array([1.0, 0.2, 0.8])
    free = np.full(3, -np.inf), np.full(3, np.inf)
    held = lm.minimize(residual, jacobian, x0, lo=free[0], hi=free[1])
    assert held.termination == "ftol_runs" and held.lambda_final < 1.0
    assert 2.0 * held.cost == pytest.approx(0.7448542326231441, rel=1e-8)
    assert abs(held.x[2]) < 1e-4

    # the crawl itself, with the curvature measurement off as well: it would
    # catch this crawl too, by the other route
    real = lm._solve_step
    monkeypatch.setattr(lm, "_solve_step", lambda *a, scale=None, **k: real(*a, **k))
    monkeypatch.setattr(lm, "_CURVATURE_GATE", np.inf)
    fresh = lm.minimize(residual, jacobian, x0, lo=free[0], hi=free[1])
    assert fresh.termination == "ftol_runs" and fresh.lambda_final > 1e8
    assert 2.0 * fresh.cost > 2.0 * held.cost * 2.0


@pytest.mark.parametrize("phi0", [3e-8, 0.0])
def test_a_column_small_from_the_first_iteration_has_its_curvature_measured(
        monkeypatch, phi0):
    """WP-1953: φ starts a hair from its minimum, so its column is tiny from
    the first iteration and the held scale has no larger norm to keep.
    Gauss-Newton's curvature for φ is ‖φ·bump‖², while ½∂²S/∂φ² adds
    r·bump, which does not vanish with φ.  So the model's step along φ is
    long, and λ climbs.  Measured, the curvature takes the diagonal and the
    run converges in ten evaluations.  Unmeasured, λ climbs past 1e10 and the
    run stops short of the minimum 0.744854.  From φ = 3e-8 it stops where it
    started, χ² 9.571 with a and k unmoved.  From φ = 0 the column is exactly
    zero, so where the crawl stops is rounding's: χ² 0.746097 on macOS arm64
    from seven start nudges 1e-14 apart, and 0.744872 on a Linux x86-64 CI
    runner (#923's run 38322068261).  Only the climb is asserted there."""
    residual, jacobian = _vanishing_column()
    x0 = np.array([1.0, 0.2, phi0])
    free = np.full(3, -np.inf), np.full(3, np.inf)
    out = lm.minimize(residual, jacobian, x0, lo=free[0], hi=free[1])
    assert 2.0 * out.cost == pytest.approx(0.7448542326231441, rel=1e-8)
    assert out.nfev <= 12 and abs(out.x[2]) < 1e-6

    monkeypatch.setattr(lm, "_CURVATURE_GATE", np.inf)
    blind = lm.minimize(residual, jacobian, x0, lo=free[0], hi=free[1])
    assert blind.lambda_final > 1e10
    if phi0:
        assert 2.0 * blind.cost > 2.0 * out.cost + 1e-3


def test_a_run_that_never_crawls_never_measures_a_curvature(monkeypatch):
    """From φ = 0.8 λ never reaches the gate, so the run is bit-identical with
    the measurement switched off: it costs an ordinary fit nothing."""
    residual, jacobian = _vanishing_column()
    x0 = np.array([1.0, 0.2, 0.8])
    free = np.full(3, -np.inf), np.full(3, np.inf)
    on = lm.minimize(residual, jacobian, x0, lo=free[0], hi=free[1])
    monkeypatch.setattr(lm, "_CURVATURE_GATE", np.inf)
    off = lm.minimize(residual, jacobian, x0, lo=free[0], hi=free[1])
    assert on.nfev == off.nfev
    np.testing.assert_array_equal(on.x, off.x)


def test_the_measured_curvature_is_the_gauss_newton_one_on_a_linear_column():
    """½∂²S/∂θ² of a residual linear in θ is ‖J‖² exactly, the measurement
    reads it to the difference's rounding, and a point whose second difference
    would leave the box is not measured."""
    t = np.linspace(0.0, 1.0, 50)
    col = np.exp(-t)

    def residual(th):
        return 3.0 - th[0] * col

    x = np.array([2.0])
    s = float(residual(x) @ residual(x))
    inf = np.full(1, np.inf)
    c = lm._measured_curvature(residual, x, s, 0, -inf, inf)
    assert c == pytest.approx(float(col @ col), rel=1e-6)
    assert lm._measured_curvature(residual, x, s, 0, np.array([2.0]), inf) is None
    # nor one whose second difference would cross an inequality row (θ ≤ 2)
    row = lm.LinearInequality(T=np.array([[-1.0]]), c=np.array([2.0 + 1e-6]))
    assert lm._measured_curvature(residual, x, s, 0, -inf, inf, [row]) is None


def test_a_budget_under_one_evaluation_is_refused_as_trf_refuses_it():
    """``max_iter=0`` reached scipy as ``max_nfev=0`` and was refused, while
    LM ran it as one evaluation that moved nothing (#890's triage).  The
    default flip would have turned the refusal into a quiet ``max_iter``."""
    residual, jacobian, _, _ = _collinear_pair()
    inf = np.full(2, np.inf)
    for budget in (0, -4):
        with pytest.raises(ValueError, match="max_nfev"):
            scipy_lsq(residual, np.zeros(2), jac=jacobian, method="trf",
                      max_nfev=budget)
        with pytest.raises(ValueError, match="max_nfev"):
            lm.minimize(residual, jacobian, np.zeros(2), lo=-inf, hi=inf,
                        max_nfev=budget)


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_stage_with_max_iter_0_is_refused_on_either_driver(solver):
    import rietx as rx
    from tests.test_refine_synthetic import perturbed_models, synthesize

    structure, instrument = perturbed_models()
    plan = rx.RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"],
                                              max_iter=0)])
    ref = rx.Refinement(structure, instrument, history=False, solver=solver)
    with pytest.raises(ValueError, match="max_nfev"):
        ref.fit(synthesize(), plan=plan)


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_joint_stage_with_max_iter_0_is_refused_on_either_driver(solver):
    """The joint fit reaches ``lm.minimize`` through its own call site, so the
    refusal is checked there too rather than inferred from the single fit."""
    import rietx as rx
    from tests.test_joint_xray_neutron import _flat, _neutron, _xray, corundum

    plan = rx.RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"],
                                              max_iter=0)])
    with pytest.raises(ValueError, match="max_nfev"):
        rx.refine_multi([_flat(20.0, 80.0), _flat(20.0, 80.0)],
                        rx.Structure(phases=[corundum()]), [_xray(), _neutron()],
                        plan=plan, solver=solver)
