"""Bound-constrained conjugate gradient solve of the normal equations.

Coelho, A. A. (2005). *J. Appl. Cryst.* **38**, 455-461 — "A bound constrained
conjugate gradient solution method as applied to crystallographic refinement
problems".  Independent implementation from the paper; TOPAS is closed source
and none of it was consulted (ATTRIBUTION.md, DESIGN.md "Locked decisions").

Solves ``A x = b`` for symmetric positive semi-definite ``A`` — here the
Gauss-Newton normal matrix JᵀJ (+λ on the diagonal) — by conjugate gradients
(Hestenes & Stiefel 1952; Polak 1971 form) with four modifications, all of
which exist to *terminate the CG loop early on ill-conditioned systems* rather
than to converge harder:

1. **Box bounds inside the loop.**  A parameter that would violate a bound is
   clamped to it and removed from the CG loop for the rest of *this* solve —
   never from the least-squares process, and reinstated on the next call.  This
   is the modification that changes answers rather than timings: the paper's
   Pawley case reaches Rwp 3.901 in 16 iterations with in-loop clamping against
   4.351 in 84 when the same bounds are applied *after* an unconstrained solve.
2. **Early-iteration step damping**, their equation (1) — printed as
   ``α = Max[(k+1)/N_k, 1]·s_k/(p·q)``, and the one place where the paper's
   formula and its own prose disagree.  See ``_alpha``: the reading is a
   selectable option here because it was *measured* rather than argued.
3. **Small-contribution removal**, their equation (2): a parameter with
   ``200·r_i²·N_k < s_0`` for six consecutive iterations leaves the loop.  On a
   block-diagonal system this lets converged blocks drop out and the rest carry
   on — the measured 3.30 s → 1.31 s on their Pawley refinement, at identical
   Rwp.
4. **Termination** at ``k_max`` = (k of the last removal) + N_k, or when
   ``s_k < 1e-4·s_0`` three iterations running.

With no active bounds and ``removal=False`` this reduces to textbook CG, and so
must reproduce a direct solve — the anchor
``tests/test_bccg.py::test_unconstrained_matches_direct_solve``.

**The LM driver no longer takes this step** (WP-1953).  Above
:data:`.lm.BVLS_MAX_COLUMNS` it took it until then, and on the Pawley blocks
that cross that cut it was wrong in sign: its model value was positive at most
λ > 0 on FAP.XRA's 343 columns, up to 6e6 times the size of the best value,
because a variable clamped mid-loop moves *less* than the CG step assumed while
the residual is updated as if it had not.  The stage then spent its budget
raising λ.  The driver's step there is :func:`projected_cg` below, which
stops at a bound instead of projecting past it.  Its projected search
(WP-2011) projects only a finished CG direction, and keeps the point only
where the model has fallen, so the defect above cannot recur there.
:func:`solve` stays as the paper's method, with the readings the tests pin.

The system is diagonally pre-conditioned to A_ii = 1 before any of this, which
is also what makes the Levenberg-Marquardt λ of :mod:`.lm` dimensionless.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import sparse
from scipy.linalg import LinAlgError, cho_factor, cho_solve
from scipy.sparse.linalg import spilu

#: their equation (2) constant — a parameter contributing less than
#: ``s_0 / (200·N_k)`` to the residual is a candidate for removal …
_SMALL_FACTOR = 200.0
#: … once it has met that condition this many iterations running.
_SMALL_RUNS = 6
#: their §2 termination: s_k below this fraction of s_0 for three iterations.
#: Note what this buys — s is a *squared* residual norm, so 1e-4 stops once
#: ‖Ax−b‖ has fallen 100×, which on a cond ≈ 1e3 system leaves ~1e-3 relative
#: error in x.  That is deliberate: the linear solve is inexact and the outer
#: Levenberg-Marquardt loop re-measures the real cost at the trial point, so
#: paying for a machine-precision step is wasted work.  The paper is explicit
#: that "the minimization of |Ax − b| for all parameters is not adhered to".
_CONVERGED_FRACTION = 1e-4
_CONVERGED_RUNS = 3


@dataclass
class BCCGResult:
    """Solution plus the loop diagnostics the paper reports (its Figs. 5-7)."""

    x: np.ndarray
    n_iterations: int
    #: parameters clamped to a bound inside the loop (their N_k,lim)
    n_clamped: int = 0
    #: parameters dropped by the small-contribution rule (their N_k,small)
    n_dropped: int = 0
    #: why the loop stopped — "converged" | "k_max" | "exhausted"
    status: str = "converged"
    #: average number of parameters still in the loop, over the iterations run
    #: (their N_k,avg — the statistic that shows why BCCG is cheap)
    n_active_avg: float = 0.0
    #: indices whose value was clamped to a bound (the caller may want to know
    #: which directions the box is holding; ``lm`` reports them as bound hits)
    clamped: list[int] = field(default_factory=list)


#: Readings of Coelho (2005) equation (1), ``α = f[(k+1)/N_k, 1]·s_k/(p·q)``.
#:
#: The paper prints ``f = Max``; its text says the factor "reduces the original
#: α in the early iterations … allow[ing] for small changes in parameters that
#: would otherwise be removed [by] violation of the bounding constraints",
#: which describes ``Min``.  Neither is obviously the transcription error, and
#: neither survives measurement:
#:
#: * ``"min"`` matches the prose and is a *hard* damper — at N = 1325 (their
#:   largest system) it scales the first step by 1/1325, which cannot be
#:   reconciled with their reported "around ten CG iterations regardless of N".
#:   Measured, it captures 0.003-0.72 of the available decrease in the
#:   quadratic model where the undamped step captures ~1.
#: * ``"max"`` is the printed formula.  It is exactly a no-op while k+1 ≤ N_k
#:   — which is *most* of the loop, since the k_max rule stops at
#:   (last removal) + N_k.  Where it is not a no-op it is harmful: once the
#:   removal schemes shed parameters, k+1 > N_k *amplifies* α past the exact
#:   line minimiser, and the captured decrease falls from 1.000 to 0.62
#:   (dense, N = 40) and 0.87 (block-diagonal).  Unchecked — with the k_max
#:   rule lifted — it diverges outright.
#:
#: So the shipped default is ``"off"``: identical to the printed formula
#: everywhere the printed formula is safe, and free of its one active failure
#: mode.  Both readings stay available, and `tests/test_bccg.py` pins the
#: numbers above, because "we picked the other word" is not something to
#: discover later from a bad fit.
_DAMPINGS = ("max", "min", "off")


def _alpha(k: int, n_active: int, s_k: float, pq: float, damping: str) -> float:
    """Step length of their equation (1) under the chosen reading."""
    ratio = (k + 1) / max(n_active, 1)
    if damping == "min":
        factor = min(ratio, 1.0)
    elif damping == "max":
        factor = max(ratio, 1.0)
    else:
        factor = 1.0
    return factor * s_k / pq


def solve(A: np.ndarray, b: np.ndarray, *,
          x0: np.ndarray | None = None,
          lo: np.ndarray | None = None,
          hi: np.ndarray | None = None,
          removal: bool = True,
          damping: str = "off",
          tol: float = _CONVERGED_FRACTION,
          k_max_rule: bool = True,
          max_iter: int | None = None) -> BCCGResult:
    """BCCG solve of ``A x = b`` with optional per-element bounds on ``x``.

    ``A`` must be symmetric positive semi-definite and is used only through
    matrix-vector products.  ``lo``/``hi`` bound the *solution vector* — in
    :mod:`.lm` that is the parameter step's landing point mapped back to a step
    bound, since the paper bounds parameters and CG solves for the step.

    The diagonal pre-conditioner (A_ii = 1) is applied here rather than by the
    caller: a zero diagonal entry (a parameter with an identically zero
    Jacobian column — a dead gradient, a locked direction) would divide
    by zero, so those entries keep scale 1 and, with b_i = 0, simply never move.

    ``tol`` and ``k_max_rule`` expose the two published stopping rules so a test
    can separate "the CG core is exact" from "the published termination is
    deliberately cheap"; both defaults are Coelho's and neither should be
    changed by ordinary callers.
    """
    if damping not in _DAMPINGS:
        raise ValueError(f"damping must be one of {_DAMPINGS}, got {damping!r}")
    A = np.asarray(A, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    n = len(b)
    if n == 0:
        return BCCGResult(np.zeros(0), 0)

    # --- diagonal pre-conditioner: solve for y = D·x with (D⁻¹AD⁻¹)y = D⁻¹b
    d = np.sqrt(np.maximum(np.diag(A), 0.0))
    d = np.where(d > 0.0, d, 1.0)
    As = A / np.outer(d, d)
    bs = b / d
    lo_s = None if lo is None else np.asarray(lo, dtype=np.float64) * d
    hi_s = None if hi is None else np.asarray(hi, dtype=np.float64) * d

    x = np.zeros(n) if x0 is None else np.asarray(x0, dtype=np.float64) * d
    # r = b − Ax; with the x = 0 start this is the paper's ``r = b``
    r = bs - As @ x if x0 is not None else bs.copy()
    p = r.copy()
    s_prev = 0.0
    s_0 = float(r @ r)
    if s_0 == 0.0:
        return BCCGResult(x / d, 0)

    active = np.ones(n, dtype=bool)
    small_runs = np.zeros(n, dtype=int)
    clamped: list[int] = []
    n_dropped = 0
    converged_runs = 0
    last_removal = 0
    active_counts: list[int] = []
    status = "exhausted"
    hard_cap = n * 4 + 20 if max_iter is None else max_iter

    k = 0
    while k < hard_cap:
        n_active = int(active.sum())
        if n_active == 0:
            status = "converged"
            break
        active_counts.append(n_active)
        s_k = float(r[active] @ r[active])
        if s_k <= 0.0:
            status = "converged"
            break
        # 2) Polak update, restricted to the parameters still in the loop
        if k > 0 and s_prev > 0.0:
            p = np.where(active, r + (s_k / s_prev) * p, 0.0)
        else:
            p = np.where(active, r, 0.0)
        # 3) q = Ap  4) α
        q = As @ p
        pq = float(p @ q)
        if pq <= 0.0:
            # A is singular (or numerically so) along p: no useful step left
            status = "converged"
            break
        alpha = _alpha(k, n_active, s_k, pq, damping)

        # 5) x = x + αp, with the bounds enforced *in* the loop
        x_new = np.where(active, x + alpha * p, x)
        if lo_s is not None or hi_s is not None:
            below = np.zeros(n, dtype=bool) if lo_s is None else (x_new < lo_s) & active
            above = np.zeros(n, dtype=bool) if hi_s is None else (x_new > hi_s) & active
            if below.any() or above.any():
                if lo_s is not None:
                    x_new = np.where(below, lo_s, x_new)
                if hi_s is not None:
                    x_new = np.where(above, hi_s, x_new)
                hit = below | above
                active &= ~hit
                clamped.extend(np.flatnonzero(hit).tolist())
                last_removal = k
        x = x_new

        # 7) r = r − αq, then the small-contribution removal of equation (2)
        r = np.where(active, r - alpha * q, 0.0)
        if removal:
            n_now = max(int(active.sum()), 1)
            small = active & (_SMALL_FACTOR * r * r * n_now < s_0)
            small_runs = np.where(small, small_runs + 1, 0)
            drop = small_runs >= _SMALL_RUNS
            if drop.any():
                active &= ~drop
                r = np.where(active, r, 0.0)
                n_dropped += int(drop.sum())
                last_removal = k

        s_prev = s_k
        k += 1

        # termination: s_k below 1e-4·s_0 three times running, or k_max
        s_now = float(r[active] @ r[active]) if active.any() else 0.0
        converged_runs = converged_runs + 1 if s_now < tol * s_0 else 0
        if converged_runs >= _CONVERGED_RUNS or s_now == 0.0:
            status = "converged"
            break
        if k_max_rule and k > last_removal + max(int(active.sum()), 1):
            status = "k_max"
            break

    return BCCGResult(
        x=x / d, n_iterations=k, n_clamped=len(clamped), n_dropped=n_dropped,
        status=status,
        n_active_avg=float(np.mean(active_counts)) if active_counts else 0.0,
        clamped=sorted(set(clamped)),
    )


#: :func:`projected_cg` stops on a face once the free gradient falls to this
#: fraction of the starting gradient's norm.  Far tighter than BCCG's own stop
#: (``_CONVERGED_FRACTION`` on the *squared* residual, 1e-2 on its norm): run
#: with that stop instead, FAP's ``profile`` stage needed 341 evaluations
#: against 20 (WP-1953).
_PCG_TOL = 1e-10
#: Hessian products one :func:`projected_cg` solve may spend, per variable.
#: Measured on 24 systems of 11-BM NAC's Pawley fit (1 493-1 499 columns):
#: unbudgeted, a solve at λ = 0 took up to 11 s, and 2n held every one under
#: 0.64 s.  The whole fit still converges every stage, at Rwp 0.12620721
#: (0.12620514 unbudgeted), in 71 s on macOS arm64 (WP-1953).
_PCG_BUDGET_PER_VARIABLE = 2
#: Armijo fraction and halving cap of the Cauchy point's projected search
_CAUCHY_ARMIJO = 1e-4
_CAUCHY_HALVINGS = 60


def _model(H: np.ndarray, g: np.ndarray, y: np.ndarray) -> float:
    return 0.5 * float(y @ (H @ y)) - float(g @ y)


def _cauchy_point(H: np.ndarray, g: np.ndarray, lo: np.ndarray,
                  hi: np.ndarray) -> np.ndarray:
    """The projected steepest-descent point: start at the unconstrained
    minimiser along ``g``, project onto the box, and halve the step until the
    model falls by the Armijo fraction of its first-order prediction
    (Moré, J. J. & Toraldo, G. (1991). *SIAM J. Optim.* **1**, 93-113, the
    projected search)."""
    curvature = float(g @ (H @ g))
    if curvature <= 0.0 or not np.any(g):
        return np.zeros_like(g)
    t = float(g @ g) / curvature
    for _ in range(_CAUCHY_HALVINGS):
        y = np.clip(t * g, lo, hi)
        if _model(H, g, y) <= -_CAUCHY_ARMIJO * float(g @ y):
            return y
        t *= 0.5
    return np.zeros_like(g)


def projected_cg(H, g: np.ndarray, lo: np.ndarray, hi: np.ndarray, *,
                 budget: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Minimise ``½yᵀHy − gᵀy`` over ``lo ≤ y ≤ hi`` by projected conjugate
    gradients, the step :mod:`.lm` takes above its BVLS cut (WP-1953).

    ``H``, dense or ``scipy.sparse``, is symmetric positive semi-definite and
    ``lo ≤ 0 ≤ hi``, so y = 0 is feasible.  The method is the subspace step of
    Lin, C.-J. & Moré, J. J. (1999). *SIAM J. Optim.* **9**, 1100-1127,
    started from the Cauchy point:

    1. **The Cauchy point** (:func:`_cauchy_point`) fixes the variables a
       steepest-descent step already pushes onto a bound.
    2. **CG on the free variables**, from a residual recomputed at the current
       point.  Where the free block's preconditioner is a dense Cholesky
       factor, CG runs on the face ignoring the bounds, which is the face's
       Newton step, and a **projected search** along it
       (:func:`_projected_search`, Lin & Moré §4) puts every variable it
       carries past a bound on that bound at once.  Otherwise a CG step that
       would leave the box is cut at the first bound it meets, that variable
       is put *on* the bound and fixed, and CG restarts.
    3. **Release.**  Once CG converges on a face, a fixed variable whose
       gradient points into the box is freed, and step 2 runs again; with none
       to free the face's minimiser is the box's.

    Every CG segment lowers the model, the cut one included, and so does
    every accepted search point, so the step always descends, which is what
    BCCG's projection past a bound could not promise.  The search projects a
    *finished* direction and keeps a point only if the model falls by the
    Armijo fraction; BCCG projected inside the recurrence and kept updating
    the residual as if it had not.  ``budget`` caps the Hessian products
    (default :data:`_PCG_BUDGET_PER_VARIABLE` per variable), a search trial
    included; a solve that spends it returns the best point so far, still a
    descent step.

    **A sparse H is preconditioned** (WP-2011), as Lin & Moré precondition
    their subspace step with an incomplete Cholesky factor: step 2 runs CG on
    the free block H_ff preconditioned by its incomplete LU (Saad, Y. (2003).
    *Iterative Methods for Sparse Linear Systems*, 2nd ed., ch. 10.
    Philadelphia: SIAM), ``scipy.sparse.linalg.spilu`` at scipy's own drop
    tolerance and fill factor.  The factor is rebuilt whenever the free set
    differs from the one it was built on.  The step length is
    ``(r·z)/(pᵀHp)`` with ``z = M⁻¹r``, which is the exact line minimiser
    along p because ``p·r = r·z`` holds for any preconditioner, so every
    segment still lowers the model.  A factorisation that fails, or a
    direction with ``r·z ≤ 0``, takes the unpreconditioned direction r, and a
    switch between the two restarts the recurrence (β = 0).  **A dense H is
    preconditioned by the exact Cholesky factor of its free block**, rebuilt
    on the same rule: a direction is then the face's Newton step, so CG on a
    face ends in one product.  A block that is not numerically positive
    definite has its diagonal raised until it factors (:func:`_factor`, as
    Lin & Moré's ICFS does): at λ = 0 a pseudo-symmetric Pawley block is
    singular, and the worst systems of two such candidates had 23-54
    eigenvalues within 2e-15 of zero, some negative.  Unshifted, 260 of 893
    and 234 of 835 factorisations failed on two such validations, and the
    face step there was unpreconditioned CG.

    **The projected search stays off the sparse path**, measured: with an
    incomplete LU on a singular face, the face's CG did not converge within
    the budget, and the search then took one long unconverged step.  FAP's
    monoclinic C test candidate (944 columns) went from Rwp 0.07715 to
    0.07755 that way.  The measurement is :func:`.lm._solve_step`'s.

    Returns the step and which bound each variable was fixed on (−1 lower,
    +1 upper, 0 neither), the convention :func:`.lm._solve_step` lands
    variables exactly on.
    """
    n = len(g)
    budget = _PCG_BUDGET_PER_VARIABLE * n if budget is None else budget
    y = _cauchy_point(H, g, lo, hi)
    floor = _PCG_TOL * _PCG_TOL * max(float(g @ g), np.finfo(np.float64).tiny)
    fixed = (y <= lo) | (y >= hi)
    spent = 0
    # the free set the preconditioner was built on, and the factor (None
    # where it failed, and the direction is then r)
    factored, ilu = None, None
    while spent < budget:
        grad = H @ y - g
        spent += 1
        r = np.where(fixed, 0.0, -grad)
        rr = float(r @ r)
        if rr <= floor:
            release = fixed & (((y <= lo) & (grad < 0.0)) | ((y >= hi) & (grad > 0.0)))
            if not np.any(release):
                break
            fixed &= ~release
            continue
        free = ~fixed
        if _PRECONDITION_DENSE or sparse.issparse(H):
            if factored is None or not np.array_equal(free, factored):
                factored, ilu = free, _factor(H, free)
        if isinstance(ilu, _Cholesky):
            # the face's Newton step, then a projected search along it
            w, used, stalled = _face_cg(H, r, rr, ilu, free, floor, budget - spent)
            spent += used
            if not np.any(w):
                break
            y, hit, used = _projected_search(H, grad, y, w, lo, hi, budget - spent)
            spent += used
            fixed |= hit
            if stalled:
                break
            continue
        z, rz = _preconditioned(ilu, r, rr, free)
        plain = z is r      # this direction took no preconditioner
        p = z
        stalled = False
        while spent < budget:
            q = H @ p
            spent += 1
            pq = float(p @ q)
            if pq <= 0.0:
                stalled = True      # flat along p: no CG step left to take
                break
            alpha = rz / pq
            with np.errstate(divide="ignore", invalid="ignore"):
                reach = np.where(p > 0.0, (hi - y) / p,
                                 np.where(p < 0.0, (lo - y) / p, np.inf))
            reach = np.where(fixed, np.inf, reach)
            tau = float(np.min(reach)) if n else np.inf
            if tau < alpha:
                hit = reach <= tau
                y = y + tau * p
                y = np.where(hit & (p > 0.0), hi, np.where(hit & (p < 0.0), lo, y))
                fixed |= hit
                break
            y = y + alpha * p
            r = np.where(fixed, 0.0, r - alpha * q)
            rr_next = float(r @ r)
            if rr_next <= floor:
                break
            z, rz_next = _preconditioned(ilu, r, rr_next, free)
            # a direction that fell back to r (or came back from it) restarts
            # the recurrence: β would divide one preconditioner's r·z by the
            # other's.  p·r = r·z still holds, so the step stays a descent
            beta = rz_next / rz if (z is r) == plain else 0.0
            plain = z is r
            p = z + beta * p
            rz = rz_next
        if stalled:
            break
    side = np.zeros(n, dtype=np.int8)
    side[fixed & (y <= lo)] = -1
    side[fixed & (y >= hi)] = 1
    return y, side


#: whether a dense H takes the Cholesky-preconditioned face step; a switch for
#: the WP-2011 probes (``docs/wp/2011-probe/probe17``, ``probe22``) to measure
#: the unpreconditioned path against, never set by the package
_PRECONDITION_DENSE = True
#: The first diagonal shift tried on a dense free block whose Cholesky
#: factorisation fails, as a fraction of each diagonal entry, doubled until
#: the factorisation succeeds: α_S of Lin, C.-J. & Moré, J. J. (1999).
#: *SIAM J. Sci. Comput.* **21**, 24-45, the incomplete Cholesky
#: preconditioner of their TRON.
_CHOLESKY_SHIFT = 1e-3
#: factorisations tried before the block is left unpreconditioned: one
#: unshifted, then that shift and its doublings
_CHOLESKY_SHIFTS = 40


def _face_cg(H, r: np.ndarray, rr: float, ilu, free: np.ndarray, floor: float,
             budget: int) -> tuple[np.ndarray, int, bool]:
    """Preconditioned CG on the free face from w = 0, ignoring the bounds: the
    direction of Lin & Moré's subspace step.  It runs until the face's
    residual falls to ``floor``, ``budget`` products are spent, or H is flat
    along a direction.  Returns w, the products spent, and whether it
    stopped on a flat direction."""
    w = np.zeros_like(r)
    z, rz = _preconditioned(ilu, r, rr, free)
    plain = z is r
    p = z
    spent = 0
    while spent < budget:
        q = H @ p
        spent += 1
        pq = float(p @ q)
        if pq <= 0.0:
            return w, spent, True
        alpha = rz / pq
        w = w + alpha * p
        r = np.where(free, r - alpha * q, 0.0)
        rr_next = float(r @ r)
        if rr_next <= floor:
            break
        z, rz_next = _preconditioned(ilu, r, rr_next, free)
        beta = rz_next / rz if (z is r) == plain else 0.0
        plain = z is r
        p = z + beta * p
        rz = rz_next
    return w, spent, False


def _projected_search(H, grad: np.ndarray, y: np.ndarray, w: np.ndarray,
                      lo: np.ndarray, hi: np.ndarray,
                      budget: int) -> tuple[np.ndarray, np.ndarray, int]:
    """The point P[y + β·w] for the first β = 1, ½, ¼, … at which the model
    falls by the Armijo fraction of its first-order prediction (Moré &
    Toraldo 1991; Lin & Moré 1999 §4).  A trial costs one H product, since
    m(y + s) − m(y) = ∇m·s + ½sᵀHs.

    Once β reaches the first breakpoint τ, where w first meets a bound, the
    search takes β = τ without a trial.  w is a CG iterate from y, so it is
    the exact minimiser along its own line, and the model falls
    monotonically on β ∈ [0, 1]: the cut at τ lowers it.  Returns the point,
    the variables it put on a bound, and the products spent."""
    with np.errstate(divide="ignore", invalid="ignore"):
        reach = np.where(w > 0.0, (hi - y) / w,
                         np.where(w < 0.0, (lo - y) / w, np.inf))
    tau = float(np.min(reach)) if len(w) else np.inf
    spent, beta = 0, 1.0
    while beta > tau and spent < budget and spent < _CAUCHY_HALVINGS:
        trial = np.clip(y + beta * w, lo, hi)
        s = trial - y
        gs = float(grad @ s)
        spent += 1
        if gs + 0.5 * float(s @ (H @ s)) <= _CAUCHY_ARMIJO * gs:
            return trial, (w != 0.0) & ((trial <= lo) | (trial >= hi)), spent
        beta *= 0.5
    beta = min(tau, 1.0)
    hit = reach <= beta
    y = y + beta * w
    y = np.where(hit & (w > 0.0), hi, np.where(hit & (w < 0.0), lo, y))
    return y, hit, spent


class _Cholesky:
    """A dense free block's Cholesky factor, behind ``spilu``'s ``solve``."""

    def __init__(self, factor):
        self.factor = factor

    def solve(self, r: np.ndarray) -> np.ndarray:
        return cho_solve(self.factor, r, check_finite=False)


def _factor(H, free: np.ndarray):
    """The preconditioner on H's free block, or ``None`` where it fails: a
    sparse H's incomplete LU at scipy's defaults (an exactly singular pivot
    fails it), a dense H's Cholesky factor.  A dense block that is not
    numerically positive definite is factored with its diagonal raised by
    :data:`_CHOLESKY_SHIFT`, doubled until the factorisation succeeds, as
    Lin & Moré's ICFS does."""
    idx = np.flatnonzero(free)
    if not idx.size:
        return None
    if sparse.issparse(H):
        try:
            return spilu(H.tocsr()[idx][:, idx].tocsc())
        except RuntimeError:
            return None
    block = np.asarray(H)[np.ix_(idx, idx)]
    diag = np.diag(block)
    raise_by = np.where(diag > 0.0, diag, 1.0)
    on_diag = np.diag_indices_from(block)
    alpha = 0.0
    for _ in range(_CHOLESKY_SHIFTS):
        # one working copy an attempt, factored in place: a failed attempt
        # leaves it partly overwritten, so the next starts from block again
        work = block.copy()
        if alpha:
            work[on_diag] += alpha * raise_by
        try:
            return _Cholesky(cho_factor(work, overwrite_a=True,
                                        check_finite=False))
        except LinAlgError:
            alpha = max(2.0 * alpha, _CHOLESKY_SHIFT)
    return None


def _preconditioned(ilu, r: np.ndarray, rr: float,
                    free: np.ndarray) -> tuple[np.ndarray, float]:
    """``z = M⁻¹r`` on the free variables, zero on the fixed ones, with
    ``r·z``.  Without a factor, or where ``r·z`` is not positive and finite,
    the direction is r itself with ``r·r``, unpreconditioned CG's."""
    if ilu is None:
        return r, rr
    z = np.zeros_like(r)
    z[free] = ilu.solve(r[free])
    rz = float(r @ z)
    if not (np.isfinite(rz) and rz > 0.0):
        return r, rr
    return z, rz
