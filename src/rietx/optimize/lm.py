"""Bounded Levenberg-Marquardt driver, the default since WP-1938.

Gauss-Newton normal equations with the adaptive Marquardt constant of Coelho,
A. A. (2018). *J. Appl. Cryst.* **51**, 428-435 ("Optimum Levenberg-Marquardt
constant determination for nonlinear least-squares"), each damped step solved
exactly inside the parameter box by bounded-variable least squares (Stark, P.
B. & Parker, R. L. (1995). *Comput. Statist.* **10**, 129-141; WP-1937).  The
paper pairs the schedule with the bound-constrained conjugate gradient of
:mod:`.bccg` (Coelho 2005), which this driver used for every step until
WP-1937 and above :data:`BVLS_MAX_COLUMNS` until WP-1953.  Above that cut,
where only a Pawley block reaches, the step is now projected conjugate
gradients (:func:`.bccg.projected_cg`), because BCCG's was measured wrong in
sign there.  A Pawley stage whose windows are narrow hands the driver its
normal matrix sparse there (``normal_equations``, WP-2011), and the CG is then
preconditioned by an incomplete LU of the free block: on 11-BM NAC's
2224-reflection monoclinic candidate the fit fell from 376 s to 34-38 s at the
same Rwp to four decimals.
Independent implementation from the papers; TOPAS is closed source and none of
it was consulted.

It is the default driver since WP-1938, which made every parameter refine in
its own units.  There a width or scale whose minimum sits on its floor is a
box bound, and the exact bounded step lands it there, where TRF's strictly
feasible iterates crawl towards it (:data:`.least_squares.DEFAULT_SOLVER`
carries the grid that decided it).  scipy's TRF stays selectable as
``solver="trf"``, and every acceptance number before WP-1938 was measured
with it.

Why a driver of our own beside scipy's: **constraint vocabulary**.
``scipy.optimize.least_squares`` speaks only boxes on individual parameters.
This driver adds

* boxes enforced *inside* the linear solve rather than after it, and
* **linear inequalities on functionals of θ** — rows ``T·θ + c ≥ 0`` — which
  is the shape of the Stephens anisotropic-strain positivity cone and of the
  floor Γ_G² ≥ ε on the Gaussian width at every reflection (WP-1938 D7), and
  which no box can express (see :class:`LinearInequality`).

The inequalities are held inside the step too (WP-1938 D8).  A step that
satisfies every row is the box-only step, untouched.  A step that crosses a
row is replaced by the exact minimiser of the same damped model over the box
and the rows together (:func:`_solve_constrained_step`, Lawson & Hanson
1974, ch. 23).  Until D8 the box-only step was projected and truncated
against the rows instead, and where the optimum sits on a row's face that
stalled.  Brucite + Stephens stopped ``exhausted_fp64`` with its S_HKL spread
7e-5 relative over five starts.  Under D7's Γ_G² rows, two LaB₆ fits and
BT-1's X-ray fit stopped short of the rows' face.

**Speed comes from the evaluation count, not the solve.**  The
normal-equation solve is a minority of this package's runtime —
``derivative_bases`` costs ~2× the forward evaluation, and Coelho's own
N = 1325 case drops the *solve* from 484 s to 2.86 s while the whole
refinement only drops 2441 s → 1785 s — so a faster solve alone would buy
≈1.25×.  Measured with ``examples/bench_solver.py`` (macOS arm64, ``[dev]``,
rietx-kernels 1.2.0, three runs, WP-1938): 1.19-1.30× on SRM 660c and 11-BM
NAC, where both drivers converge (78 against 83 and 35 against 51 residual
evaluations).  On corundum and the cpd-2 QPA protocol TRF stops on
``max_iter`` after 906 and 3865 evaluations and LM converges in 116 and 224,
11.6-14.5× and 34.1-35.3× faster.

Conventions, which must match :mod:`.least_squares` exactly or λ is meaningless:

* the residual is ``r = √w·(y_obs − y_calc)`` and ``J = ∂r/∂θ``, so the paper's
  objective ``S = rᵀr`` is our χ² and ``LSQOutcome.cost_*`` is scipy's ½·rᵀr;
* ``A = JᵀJ``, ``b = −Jᵀr`` — exactly Coelho's equation (6), whose ``b`` is
  ``−½∇S``;
* λ is added after the diagonal pre-conditioner, which is what makes it
  dimensionless and lets the published constants transfer.  The
  pre-conditioner is each column's largest norm this stage (:func:`minimize`),
  so ``A_ii = 1`` for a column at its largest and under 1 for one that has
  shrunk since (WP-1953).

**The sign of ΔS_t.**  The paper's equation (9) defines ``r_u = ΔS_t/ΔS`` with
``ΔS_t = Δpᵀb``.  Taken literally with its own ``b`` that is positive for a
descent step while ΔS < 0, so every good step would report ``r_u < 0`` — which
contradicts its Table 1 (``r_u ≈ 1.003`` on a near-quadratic step), its §1.2
claim that ``S_t(p+Δp) = S(p+Δp)`` for quadratic S, and its Fig. 10
distribution ("almost all of the iterations have r_u < 1").  The
self-consistent reading is

    ΔS_t = −Δθᵀb

for which an exactly linear model gives ``r_u ≡ 1``: with ``r(θ+Δ) = r + JΔ``,
``S(θ+Δ) = S − 2Δᵀb + ΔᵀAΔ``, and at the exact Gauss-Newton step ``Δ = A⁻¹b``
this is ``S − Δᵀb``, so ``ΔS = −Δᵀb = ΔS_t``.  That identity is the calibration
test (``tests/test_lm_solver.py::test_ru_is_one_on_a_linear_model``) and the
only way to know the schedule is being fed the quantity its constants were
tuned for.

**Where the two drivers can part company on the answer** (WP-1113): on a
protocol whose width stages walk a degenerate valley into a stage that opens
a *new* basin — the QPA cpd-2 protocol, where per-phase size/strain × U,V,W,
X,Y are near-degenerate and the texture stage's March-Dollase basin is only
downhill from some points of that valley — the two drivers stop at different,
locally equivalent valley points.  In the softplus coordinates before
WP-1938, the LM's was one from which the texture basin is unreachable (Rwp
0.245 against TRF's 0.133, brucite 76 against 38 wt %), and a TRF polish from
its exact state stayed at Rwp 0.244: a *genuine local minimum*, not a driver
defect.  In physical coordinates LM reaches the basin (Rwp 0.13260) and TRF
stops on ``max_iter`` at 0.13297.  Basin selection on a shared degeneracy is
path luck, not driver quality, so re-validate a texture-bearing staged answer
from a second start (the case lives in ``examples/bench_solver.py``).

**The cost is always a fresh fp64 residual evaluation**, never an extrapolation
from the same reduced-precision quantities that built the columns.  That is
what lets a backend compute Jacobian columns in fp32 and still land on the
fp64 answer (WP-0403/0408: an all-fp32-column Apple-GPU refinement lands
3.5e-8 Å from numpy fp64 *because the driver re-measures each step against an
fp64 cost*).  ``require_fp64`` guards the normal-equation assembly, where
cond(JᵀJ) = cond(J)² makes reduced precision unrecoverable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy import sparse
from scipy.optimize import lsq_linear, nnls

from ..backend.linalg64 import require_fp64, to_host_fp64
from . import bccg, lapack
from .blocked import BlockJacobian

#: λ schedule constants, Coelho (2018) equation (9).  λ starts at 0 (pure
#: Gauss-Newton) and is dimensionless because the system is pre-conditioned.
_LAMBDA_FAIL_FLOOR = 0.1     # failed step → λ ← 10·max(λ, 0.1)
_LAMBDA_FAIL_FACTOR = 10.0
_M_LO, _M_HI = 0.4, 10.0     # m_u = Limit(r_u, 0.4, 10)
_Q_WINDOW = 10               # Q_u sums the last ten overshoot signs …
_Q_TRIGGER = 5               # … and λ/10 fires only above this

#: inner (Levenberg-Marquardt) iterations per outer iteration before giving up.
#: A failure sets λ ← 10·max(λ, 0.1), so from λ = 0 the 18th trial would run
#: at λ = 1e16, far into steepest-descent territory, though at λ ≥ 100 the
#: curvature gate can reset λ to its start-of-iteration value, so 18 trials
#: need not reach it.  A cap that fires reads as convergence (``no_descent``).  On nine acceptance configurations an iteration that took
#: a step tried at most 6 trials, and a stage's last iteration up to 9 (WP-2002,
#: tests/test_budget_and_tolerance_invariance.py).
_INNER_MAX = 18
#: The default ``ftol``: the relative decrease in S under which an iteration
#: counts towards convergence, here and in both of
#: :mod:`~rietx.optimize.least_squares`' drivers.  It is the final stage's
#: tolerance, the plan's earlier stages taking ``INTERMEDIATE_FTOL`` (WP-1123).
#: One decade under SciPy's own 1e-8; no stated source.
FTOL = 1e-9
#: consecutive outer iterations below ``ftol`` that count as converged.  One
#: small step is a small step; three running is convergence (Coelho's rule).
_CONVERGED_RUNS = 3
#: relative floor on the *predicted* decrease −Δθᵀb.  Below this the step
#: cannot be measured against S in fp64 (S is a sum of ~10⁴ squares, so its
#: own resolution is ~1e-16·S), and a "failed" step is then a measurement
#: artefact rather than information about the objective.  Without this floor a
#: stall costs the full inner budget — measured on the SRM 660c protocol, λ
#: ramping to 3.6e27 while every trial step underflowed the cost difference.
_PREDICTED_FLOOR = 1e-12
#: λ at which a rejected trial sends the driver to measure the curvature of the
#: coordinate it moved furthest (:func:`minimize`, WP-1953).  Three rejections
#: in a row from λ ≤ 0.1 reach it.  Measured on the fast suite, 3762 of 3831
#: LM solves never raise λ past 10, and the crawls this catches pass 1e8.
_CURVATURE_GATE = 100.0
#: the second difference's step in :func:`_measured_curvature`, relative to the
#: coordinate's size: ε^¼, where its truncation and rounding errors balance
_CURVATURE_STEP = float(np.finfo(np.float64).eps) ** 0.25

#: a row whose slack is under 0 by less than this fraction of its block's
#: largest |slack|, floored at 1 in the row's units, is on its face, not
#: violated (:meth:`LinearInequality.violated`): the guards' own tolerance
#: (``strategy.staged.STEPHENS_CONE_TOL``, ``RESOLUTION_CONE_TOL``), read the
#: same way, against the largest value or 1.
_ON_FACE = 1e-9
#: relative amount by which the box-only step may cross a linear-inequality row
#: and still be taken, measured against the row's own scale
#: ``|T|·|θ| + |c|``.  A crossing that small is the rounding of the row's
#: evaluation, as when a row coincides with a box face the step lands on
#: (W's floor and the Γ_G² row at U = V = 0).  Anything larger takes the exact
#: constrained step.  Seven decades under the guards' own tolerance
#: (``strategy.staged.STEPHENS_CONE_TOL``, ``RESOLUTION_CONE_TOL``, 1e-9).
_ROW_ROUNDING = 1e-12
#: curvature, as a fraction of the largest eigenvalue, given to the directions
#: the eigenvalue cut discards when the step must also hold inequality rows.
#: The model is flat there, so any curvature is a tie-break, and the box-only
#: step's is minimum norm.  The least-distance problem divides by the square
#: root of each curvature, so a curvature at the cut itself loses most of its
#: digits.  On the 1000 random problems below, a curvature at the cut left
#: three rank-deficient steps on the unpolished least-distance point and one
#: with no step at all, and √ε left none.
_NULL_CURVATURE = float(np.sqrt(np.finfo(np.float64).eps))
#: the polished constrained step (:func:`_equality_step`) is kept when it holds
#: every row to this fraction of the row's scale and its gradient is a
#: non-negative combination of the active rows to ``_POLISH_STATIONARY`` of
#: the gradient's scale.  Otherwise the least-distance point stands.  Measured
#: on 1000 random problems (2-11 parameters, column scales 1e-3 to 1e3, up to
#: 29 rows, a fifth rank-deficient, λ of 0, 1e-3 and 1), 898 of which crossed
#: a row: the polish passed on all 898.  On the full-rank ones its worst row
#: sat at -7e-13 of its scale and its worst stationarity residual at 4e-10,
#: and the unpolished least-distance point's worst row sat at -1.4e-7.
_POLISH_FEASIBLE = 1e-10
_POLISH_STATIONARY = 1e-8
#: eigenvalues of the equilibrated normal matrix below this × (number of
#: residual rows) × λmax are discarded from the step: the scale of the
#: rounding error in one entry of JᵀJ (see :func:`_solve_step`).
_EIGEN_CUT_PER_ROW = float(np.finfo(np.float64).eps)
#: Largest system the step solves exactly by BVLS; above it the step is
#: projected CG's (:func:`_solve_step`, WP-1953).  Measured on Pawley-shaped
#: systems (one banded column per reflection plus 13 dense ones, macOS arm64,
#: WP-1937): a BVLS solve costs 2-34 ms at 128 columns, 0.13-0.8 s at 400,
#: 1.5-11 s at 1000 and 10-177 s at 2000, the range spanning few to most
#: intensities on their floor.  On real Pawley systems (WP-1953) it cost
#: 0.04-0.25 s at 343 columns and 0.66-3.1 s at 1 493-1 495, where the
#: projected CG took 0.002-0.04 s and at most 0.64 s.  Every table-only stage
#: in the acceptance fits is far below the cut, so only a Pawley block
#: crosses it.
BVLS_MAX_COLUMNS = 128


@dataclass(frozen=True)
class LinearInequality:
    """Rows ``T·θ + c ≥ 0`` the solver must keep satisfied.

    This is the piece published BCCG explicitly cannot do: its §4 states that a
    constraint which is a function of several parameters "cannot be handled in
    the loop — a restraint which modifies the A matrix is necessary".  Rather
    than turn the constraint into a soft restraint, which would let it be
    violated whenever the data pull hard enough, the step holds the rows
    exactly, so *every* iterate is feasible.

    A box is the special case ``T = ±I``, and the step solves boxes and rows
    in one problem when a row binds (:func:`_solve_constrained_step`).  Bounds
    inside the solve rather than applied after it is the gap Coelho (2005)
    measured (Pawley, Rwp 3.901 in 16 iterations against 4.351 in 84), and
    WP-1938 D8 closed it for the rows a box cannot express.

    Four builders make them, all in :mod:`.least_squares`:
    ``strain_cone_inequalities``, ``texture_positivity_inequalities``,
    ``gaussian_width_inequalities`` and ``lorentzian_width_inequalities``.  A
    row the starting point violates is left out by each, since the step keeps
    feasibility and cannot restore it: at an iterate a row's slack is never
    asked to grow, only not to fall below ``min(slack, 0)``.

    ``T`` is (n_rows, n_free) and frozen for the whole least-squares run — the
    same frozen-per-stage discipline the hkl list and window ranges follow.
    """

    T: np.ndarray
    c: np.ndarray
    #: what the rows mean, for diagnostics: ``"phases.0.microstrain"`` for the
    #: cone, ``"instrument.profile (phases.0)"`` for the Γ_G² floor
    label: str = ""

    def violated(self, theta: np.ndarray) -> np.ndarray:
        """Rows below their face by more than :data:`_ON_FACE` of the
        block's largest |slack| or of 1, whichever is larger: the guards' own
        reading of "on the face" (``check_resolution_positive``,
        ``check_stephens_positive``).

        A row an exact step left on its face reads a rounding either side of
        it, and a strict test would call half of those violated.  The
        builders drop a block or row the start violates, so a stage that
        ended on the cone handed the next stage no cone at all: brucite +
        Stephens left it at −1.5e-11 against a largest σ²(M) of 6.3e6, and
        the stages after it took 19 of 43 reflections out of the cone.

        The floor of 1 is for a block whose *every* row is on its face, where
        the largest |slack| is itself a rounding and the test was strict
        again.  Γ_L = X/cosθ + Y·tanθ is that block once X sits on its floor
        at 0 and Y follows to 0: a stage left them at 4e-22 and −4e-21, every
        row read violated, and the next stage, built with no row, walked Y to
        −0.0137 with Γ_L negative at every reflection.  On the planted
        cooling ramp under ``reseed=False`` with no first-rung bound, the 40
        patterns warm-started from there each converged at Rwp 0.433 against
        0.042 (WP-2003, X16).
        """
        slack = self.slack(theta)
        scale = max(float(np.max(np.abs(slack), initial=0.0)), 1.0)
        return slack < -_ON_FACE * scale

    def slack(self, theta: np.ndarray) -> np.ndarray:
        return self.T @ theta + self.c

    def crossed(self, theta: np.ndarray, step: np.ndarray) -> bool:
        """Whether ``step`` from ``theta`` takes a row below ``min(slack, 0)``
        by more than the rounding of its evaluation (:data:`_ROW_ROUNDING`)."""
        end = theta + step
        floor = np.minimum(self.slack(theta), 0.0)
        scale = np.abs(self.T) @ np.abs(end) + np.abs(self.c)
        return bool(np.any(self.slack(end) < floor - _ROW_ROUNDING * scale))

    def max_feasible_fraction(self, theta: np.ndarray, step: np.ndarray) -> float:
        """Largest τ ∈ [0, 1] with ``T·(θ + τ·step) + c ≥ min(slack, 0)``.

        Only :func:`minimize`'s fallback reads it, when the constrained solve
        fails.  Rows the step moves *away* from the surface, or along it,
        never bind, so only negative ``T·step`` entries can shorten it.
        """
        g0 = self.slack(theta)
        dg = self.T @ step
        closing = dg < 0.0
        if not np.any(closing):
            return 1.0
        with np.errstate(divide="ignore", invalid="ignore"):
            tau = np.where(closing, -np.maximum(g0, 0.0) / dg, np.inf)
        return min(1.0, float(np.min(tau)))


@dataclass
class LMOutcome:
    """What :func:`minimize` returns — deliberately scipy-``OptimizeResult``-shaped
    so :func:`.least_squares.run_least_squares` can consume either driver."""

    x: np.ndarray
    fun: np.ndarray            # residual at x (fp64, freshly evaluated)
    jac: np.ndarray            # Jacobian at x (a BlockJacobian if the closure returns one)
    cost: float                # ½·rᵀr, scipy's convention
    #: residual evaluations, the initial one included — scipy's ``nfev``, and
    #: the unit both drivers' budget is in (WP-1937)
    nfev: int
    njev: int
    n_outer: int
    #: >0 converged, 0 budget spent.  Never negative: like scipy's TRF, which
    #: returns −1 only from MINPACK's ``method="lm"``, this driver accepts only
    #: steps that lower S, so a run that found nothing downhill stopped at a
    #: point it could not improve rather than diverging from one (WP-1937)
    status: int
    lambda_final: float = 0.0
    n_bound_hits: int = 0
    #: trial steps a linear-inequality row shaped: the box-only step crossed a
    #: row, and the constrained step replaced it (WP-1938 D8).  The name is
    #: from before D8, when such a step was truncated instead.
    n_truncated: int = 0
    #: ``n_truncated`` by the :attr:`LinearInequality.label` of each block the
    #: box-only step crossed, so a step crossing two blocks counts once in each
    #: (WP-1938 D7: the Stephens cone and the Γ_G² floor, and a diagnostic
    #: names which pressed)
    truncated_by: dict[str, int] = field(default_factory=dict)
    #: inner iterations burned on a point where the linearised model promised
    #: descent the true objective did not deliver (a corner, not a minimum)
    n_stalled: int = 0
    #: which criterion ended the run (WP-1113), the LM half of
    #: :data:`~.least_squares._TRF_TERMINATION`'s vocabulary:
    #: ``ftol_runs`` (relative decrease under ftol for three consecutive outer
    #: iterations — Coelho's rule), ``exhausted_fp64`` (every remaining step
    #: promises less than fp64 can measure against S, a zero step included:
    #: the bounded model's minimum is the current point), ``no_descent`` (the
    #: inner loop found nothing downhill even at large λ), ``max_nfev`` (the
    #: evaluation budget, TRF's token for the same stop).
    termination: str = "max_nfev"
    #: the bounds that hold the returned point, scipy's ``active_mask``
    #: convention (−1 lower, +1 upper, 0 neither) and exact: the variable sits
    #: *on* the bound, the step having landed it there, and the gradient at
    #: the returned point pushes it outward, so its multiplier is positive
    #: (WP-1937).  Exact up to :data:`BVLS_MAX_COLUMNS`.  Above it the step
    #: is projected CG's, which lands a variable exactly on a bound too, but
    #: a solve that spends its budget can stop before a variable reaches the
    #: bound the exact minimiser would put it on, which then stays out of
    #: this set.  scipy's TRF reports the same field within ``xtol`` of a
    #: bound whatever the gradient, its iterates being strictly feasible.
    active_mask: np.ndarray | None = None


def _clip_to_bounds(x: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return np.clip(x, lo, hi)


def _next_lambda(lam: float, r_u: float | None, q: float) -> float:
    """Coelho (2018) equation (9).

    ``r_u is None`` marks a failed step (ΔS ≥ 0), condition (i).  The three
    remaining branches all apply to steps that *lowered* S, and the novelty is
    condition (iv): damping although S dropped, because a step that overshoots
    the minimum still lowers S while wasting most of its length.
    """
    if r_u is None:                                     # (i) ΔS ≥ 0
        return _LAMBDA_FAIL_FACTOR * max(lam, _LAMBDA_FAIL_FLOOR)
    if q > _Q_TRIGGER:                                  # (ii) rare: mostly overshoots
        return lam / _LAMBDA_FAIL_FACTOR
    m_u = min(max(r_u, _M_LO), _M_HI)
    if m_u <= 1.0:                                      # (iii) at or under prediction
        return 0.5 * m_u * lam
    return m_u * (lam + 0.5) - 0.5                      # (iv) overshoot → damp


def minimize(residual: Callable[[np.ndarray], np.ndarray],
             jacobian: Callable[[np.ndarray], np.ndarray],
             x0: np.ndarray, *,
             lo: np.ndarray, hi: np.ndarray,
             max_nfev: int = 400,
             ftol: float = FTOL,
             inequalities: list[LinearInequality] | None = None,
             callback: Callable[[np.ndarray, float], None] | None = None,
             on_trial: Callable[[np.ndarray, float, bool, float, float],
                                None] | None = None,
             normal_equations: Callable[[np.ndarray, np.ndarray],
                                        tuple] | None = None,
             ) -> LMOutcome:
    """Minimise ``S(θ) = r(θ)ᵀr(θ)`` subject to ``lo ≤ θ ≤ hi`` (and ``T·θ+c ≥ 0``).

    Two nested loops, exactly Coelho (2018) Fig. 1: the outer one recomputes A
    and b at an accepted point; the inner one raises λ until a step lowers S.
    ``max_nfev`` caps residual evaluations, the initial one included, which is
    what scipy's ``max_nfev`` caps, so one budget means one thing on both
    drivers (WP-1937).  A budget under one evaluation raises ``ValueError``,
    as it does under scipy.  The inner loop is also bounded on its own, so a
    point with nothing downhill cannot spin.

    Termination: relative decrease in S below ``ftol`` for three consecutive
    outer iterations (Coelho's own criterion — a single small step is not
    convergence, it is a small step), or an inner loop that cannot find any
    downhill step even at large λ.  Both are convergence, including at the
    first outer iteration: a stage that starts at its minimum has nothing
    downhill to find.

    **Each column keeps the largest norm it has had this stage** as its
    scale (Moré, J. J. (1978). *Lecture Notes in Mathematics* **630**,
    105-116, the scaling MINPACK calls ``mode=1``).  Scaled afresh at every
    iteration instead, a column that shrinks towards a stationary point, such
    as a moment angle at a direction the symmetry fixes, took the largest
    step, and λ grew to hold it until every parameter crawled.  Three tiny
    decreases then ended the stage on ``ftol_runs`` far from a minimum
    (χ²_red 11.03 at λ ≈ 1e11 on a one-site moment fit, WP-1938 D12; 35.5
    from the same start on the tag v1.8.0), or the
    budget ran out (``test_e8``'s axial stage, 400 evaluations at λ ≈ 1e3,
    WP-1953).  With the scale held, both converge, the second in 22
    evaluations.  The scale resets with each call, so a stage starts from its
    own columns.

    **A column that is small from a stage's first iteration** has no larger
    norm to keep.  Its Gauss-Newton curvature ‖J_i‖² can sit orders of
    magnitude under the curvature of S, so the model's step along it is far
    too long, and λ climbs to hold it.  A moment angle 3e-8 rad from the
    direction the symmetry fixes carried ‖J_i‖² = 2.2e-5 where ½∂²S/∂θ_i² was
    3.4e5, and a profile refit started there stopped at λ ≈ 1e10 without
    moving (WP-1953).  So when a rejected trial leaves λ at
    :data:`_CURVATURE_GATE` or above, the driver measures ½∂²S/∂θ_i²
    (:func:`_measured_curvature`) along the coordinate that trial moved
    furthest for its size (:func:`_furthest_moved`).  Where that curvature is
    positive and exceeds what the damped model gives the coordinate,
    ``A_ii + λ·d_i²``, it becomes the coordinate's diagonal for the rest of the
    stage, and λ restarts from its value at the start of the iteration.  A
    crawl measures each coordinate at most once a stage.  A negative curvature
    is not taken, since the model must stay positive semidefinite, and
    Gauss-Newton's long steps are what leave a maximum.  So at a would-be stop
    each held curvature is measured again, and one that has turned negative is
    dropped, with the scale it lent its column and the λ that climbed against
    it, and the stage goes on.  Held there, it made a maximum read as a
    minimum: the first pattern of ``test_moment_angle_chart``'s series stopped
    with the azimuth on −a at χ²_red 0.994003, where the twin minimum beside
    it reads 0.992763.  A measurement's two evaluations are
    derivative information, like scipy's finite-difference Jacobian calls, so
    ``max_nfev`` does not count them.

    Each step solves the damped model over the box (:func:`_solve_step`).
    When that step crosses a row of ``inequalities``, the step is solved again
    over the box and every row together (:func:`_solve_constrained_step`), so
    a step that crosses nothing is the box-only step bit for bit (WP-1938 D8).

    ``callback(x, cost)`` fires on each *accepted* point; ``on_trial(x_try,
    cost, accepted, lam, step_norm)`` fires once per trial the residual
    actually measured (WP-1113), with ``cost = ½·rᵀr`` at the trial, the λ
    that produced the step, and the norm of the *taken* step, after the box
    clamp.  A trial the linear model discards unevaluated (no descent
    promised, or a promise under the fp64 floor) never reaches the residual
    and never fires it.

    ``normal_equations(J, r)`` returns ``(A, b) = (JᵀJ, −Jᵀr)`` in place of
    :func:`_normal_equations`.  It may return A as a ``scipy.sparse`` matrix,
    which a caller does only above :data:`BVLS_MAX_COLUMNS`, where the step is
    projected CG's and a sparse A is what lets it precondition
    (:func:`_solve_step`).  A Pawley stage passes one that knows each
    intensity column's rows (``least_squares._pawley_normal_equations``).
    """
    if max_nfev < 1:
        # scipy's TRF refuses the same budget in the same words.  Run on, it
        # was one evaluation that moved nothing, reported as ``max_iter``
        # (#890's triage).  WP-1947 owns a refusal that names ``max_iter``.
        raise ValueError("`max_nfev` must be None or positive integer.")
    x = _clip_to_bounds(np.asarray(x0, dtype=np.float64).copy(), lo, hi)
    ineqs = list(inequalities or [])
    build = _normal_equations if normal_equations is None else normal_equations

    r = residual(x)
    require_fp64(r, "least-squares residual")
    if not np.all(np.isfinite(r)):
        # scipy's TRF refuses the same start in the same words.  Run on, every
        # trial compares against S = nan and is rejected, which now reads as
        # convergence rather than the first-iteration "diverged" it was.
        raise ValueError("Residuals are not finite in the initial point.")
    s = float(r @ r)
    n_fev, n_jev = 1, 0
    lam = 0.0
    signs: list[int] = []
    small_runs = 0
    n_truncated = 0
    truncated_by: dict[str, int] = {}
    n_stalled = 0
    status = 0
    n_outer = 0
    termination = "max_nfev"
    scale = None
    # the largest norm each column of J has had this stage, apart from any
    # curvature held for it, so a dropped curvature leaves its scale too
    col_max = None
    # ½∂²S/∂θ_i² measured this stage where Gauss-Newton under-reads it, and
    # which coordinates have been measured (each at most once)
    curvature = np.zeros(len(x))
    measured = np.zeros(len(x), dtype=bool)

    while n_fev < max_nfev:
        n_outer += 1
        J = jacobian(x)
        n_jev += 1
        A, b = build(J, r)
        # each column keeps the largest norm it has had this stage (Moré
        # 1978, MINPACK's ``mode=1``): a column that shrinks towards a
        # stationary point keeps the damping its scale earned, rather than
        # taking the largest step and dragging λ up for every parameter.  A
        # curvature measured this stage stays its column's diagonal where it
        # is the larger.
        col = np.sqrt(np.maximum(_diagonal(A), 0.0))
        col_max = col if col_max is None else np.maximum(col_max, col)
        if np.any(curvature > 0.0):
            A = _with_diagonal(A, np.maximum(_diagonal(A), curvature))
        scale = np.maximum(col_max, np.sqrt(curvature))
        lam_start = lam

        accepted = False
        exhausted = False
        spent = False
        for _inner in range(_INNER_MAX):
            step, side = _solve_step(A, b, lam, x, lo, hi, n_rows=len(r), scale=scale)
            crossed = [iq.label for iq in ineqs if iq.crossed(x, step)]
            if crossed:
                # the box-only step leaves the feasible set: solve the same
                # model over the box and the rows together (WP-1938 D8)
                n_truncated += 1
                for label in crossed:
                    truncated_by[label] = truncated_by.get(label, 0) + 1
                try:
                    step, side = _solve_constrained_step(A, b, lam, x, lo, hi, ineqs,
                                                         n_rows=len(r), scale=scale)
                except _NoConstrainedStep:
                    # nnls ran out of iterations: shorten the box-only step to
                    # the first row it reaches, the pre-D8 rule without the
                    # projection
                    tau = min(iq.max_feasible_fraction(x, step) for iq in ineqs)
                    step, side = tau * step, np.zeros_like(side)
            if not np.any(step):
                # the model's minimum over the box and the rows is where we
                # stand
                exhausted = True
                break
            floor = -_PREDICTED_FLOOR * max(abs(s), 1.0)
            x_try = _clip_to_bounds(x + step, lo, hi)
            # a variable the solve put on a bound lands on it exactly:
            # (lo − x)·d/d need not round back to lo − x, and the active set is
            # read as x == bound
            x_try = np.where(side < 0, lo, np.where(side > 0, hi, x_try))
            step = x_try - x            # the *taken* step, after every clamp
            promise = -float(step @ b)
            if promise >= 0.0:
                # Not a descent direction *for the model* — which is a
                # statement about the model, not the objective.  Neither exact
                # solve can return one, since Δ = 0 is feasible and its model
                # value is zero, short of rounding.  BCCG's truncated CG
                # could before WP-1937 (measured on brucite: ‖Δ‖ ≈ 2e10
                # promising +1.7e5).  Either is what λ exists for: damp and
                # retry.
                lam = _next_lambda(lam, None, 0.0)
                continue
            if promise > floor:
                # a genuine descent direction, but promising less than fp64 can
                # measure against S: trying it would sample rounding noise, and
                # every further λ increase promises less still
                exhausted = True
                break
            if n_fev >= max_nfev:
                spent = True
                break
            r_try = residual(x_try)
            n_fev += 1
            s_try = float(r_try @ r_try)
            ds = s_try - s
            if on_trial is not None:
                on_trial(x_try, 0.5 * s_try, bool(ds < 0.0), float(lam),
                         float(np.linalg.norm(step)))
            if ds < 0.0:
                # ΔS_t = −Δθᵀb (see module docstring — the paper drops this sign)
                ds_t = -float(step @ b)
                r_u = ds_t / ds
                signs.append(1 if r_u > 1.0 else -1)
                q = min(max(sum(signs[-_Q_WINDOW:]), 0), 10)
                lam = _next_lambda(lam, r_u, q)
                rel = -ds / max(abs(s), 1e-300)
                x, r, s = x_try, r_try, s_try
                accepted = True
                if callback is not None:
                    callback(x, 0.5 * s)
                small_runs = small_runs + 1 if rel < ftol else 0
                break
            lam = _next_lambda(lam, None, 0.0)
            if lam >= _CURVATURE_GATE:
                # a crawl has begun: the coordinate the rejected trial moved
                # furthest may be one Gauss-Newton cannot see curve
                i = _furthest_moved(step, x, measured)
                if i is not None:
                    measured[i] = True
                    c = _measured_curvature(residual, x, s, i, lo, hi, ineqs)
                    if c is not None and c > A[i, i] + lam * scale[i] ** 2:
                        curvature[i] = c
                        diag = _diagonal(A).copy()
                        diag[i] = c
                        A = _with_diagonal(A, diag)
                        scale[i] = max(scale[i], np.sqrt(c))
                        lam = lam_start
        if spent:
            break
        if (not accepted or small_runs >= _CONVERGED_RUNS) and np.any(curvature > 0.0):
            # a would-be stop: a held curvature that has turned negative made
            # a maximum read as a minimum, so it is dropped and the stage goes on
            turned = [i for i in np.flatnonzero(curvature > 0.0)
                      if (c := _measured_curvature(residual, x, s, int(i), lo, hi, ineqs))
                      is not None and c < 0.0]
            if turned:
                # λ climbed against the dropped diagonal: left there, the
                # next iteration's first trial is too short to measure and
                # the stage stops where it would have
                curvature[turned] = 0.0
                small_runs = 0
                lam = min(lam, lam_start)
                continue
        if not accepted:
            # No downhill step exists that the cost can resolve.  That is
            # convergence, on the first outer iteration as on any later one,
            # since a stage can start at its minimum (WP-1937; it reported
            # "diverged" before, and a series quarantines on that word) — and
            # *not* always because a minimum was reached: an objective with a
            # corner (the FCJ profile at S/L = H/L is one, and the default
            # instrument starts both apertures equal) presents a linearised
            # model that promises descent in a direction the true function
            # climbs.  ``n_stalled`` records it; the correlation guard reports
            # the degeneracy.  TRF says ``xtol`` at the same point.
            n_stalled = _INNER_MAX if not exhausted else 0
            status = 1
            termination = "exhausted_fp64" if exhausted else "no_descent"
            break
        if small_runs >= _CONVERGED_RUNS:
            status = 1
            termination = "ftol_runs"
            break

    # J must be the Jacobian *at the returned point* — covariance_estimates
    # reads it together with ``fun``, and a stale one silently mis-scales
    # every esd.  Re-evaluating at an already-visited θ is nearly free: the
    # FCJ node memo (WP-0605) keys on exact input equality.
    J = jacobian(x)
    n_jev += 1
    at_bounds = (np.isclose(x, lo) & np.isfinite(lo)) | (np.isclose(x, hi) & np.isfinite(hi))
    n_bound_hits = int(np.count_nonzero(at_bounds))
    # ½∇S = Jᵀr: positive means S falls as the variable decreases
    half_grad = J.rmatvec(r) if isinstance(J, BlockJacobian) else to_host_fp64(J).T @ r
    active = np.zeros(len(x), dtype=np.int8)
    active[(x == lo) & (half_grad > 0.0)] = -1
    active[(x == hi) & (half_grad < 0.0)] = 1
    return LMOutcome(x=x, fun=r, jac=J, cost=0.5 * s, nfev=n_fev, njev=n_jev,
                     n_outer=n_outer, status=status, lambda_final=lam,
                     n_bound_hits=n_bound_hits, n_truncated=n_truncated,
                     truncated_by=truncated_by,
                     n_stalled=n_stalled, termination=termination,
                     active_mask=active)


def _normal_equations(J, r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(A, b) = (JᵀJ, −Jᵀr)``, the two quantities every outer iteration forms.

    A joint fit's :class:`~.blocked.BlockJacobian` scatters them block by block
    into a dense A (WP-1325, the WP's route (i)): everything after this point
    is the dense driver's, so the step is BVLS's or projected CG's on the same
    model, and the box is held as it always was.
    """
    if isinstance(J, BlockJacobian):
        return J.normal_equations(r)
    # invariant 2: cond(JᵀJ) = cond(J)², so the normal equations are the one
    # step that can never run below fp64 whatever built the columns
    Jh = to_host_fp64(J)
    return Jh.T @ Jh, -(Jh.T @ r)


def _diagonal(A) -> np.ndarray:
    """A's diagonal, dense or ``scipy.sparse`` (``normal_equations``)."""
    return A.diagonal() if sparse.issparse(A) else np.diag(A)


def _with_diagonal(A, values: np.ndarray):
    """A with its diagonal replaced by ``values``: in place for a dense A, as
    a new matrix for a sparse one, whose stored pattern need not hold every
    diagonal entry.  The old diagonal is subtracted out and ``values`` added
    to the zero left, so each entry is ``values`` exactly, as the dense write
    makes it: ``a + (v − a)`` need not round back to v."""
    if sparse.issparse(A):
        return (A - sparse.diags(A.diagonal()) + sparse.diags(values)).tocsr()
    A[np.diag_indices(len(values))] = values
    return A


def _furthest_moved(step: np.ndarray, x: np.ndarray,
                    measured: np.ndarray) -> int | None:
    """The coordinate a rejected step moved furthest for its size, among those
    not yet measured this stage.

    The size is ``max(|θ_i|, 1)``, the reading
    :func:`.least_squares.fd_step` gives a coordinate of typical size 1.
    Returns ``None`` when the step moved no unmeasured coordinate.
    """
    moved = np.abs(step) / np.maximum(np.abs(x), 1.0)
    moved[measured] = 0.0
    if not moved.size:
        return None
    i = int(np.argmax(moved))
    return i if moved[i] > 0.0 else None


def _measured_curvature(residual: Callable[[np.ndarray], np.ndarray],
                        x: np.ndarray, s: float, i: int,
                        lo: np.ndarray, hi: np.ndarray,
                        inequalities: list[LinearInequality] | None = None
                        ) -> float | None:
    """½∂²S/∂θ_i² at ``x``, by a central second difference of ``S = rᵀr``.

    The step is ``h = ε^¼·max(|θ_i|, 1)``.  The difference's truncation error
    is ``h²·S⁗/12`` and its rounding error about ``4u·S/h²`` (u = ε/2), so
    their sum is least for h near ``u^¼`` in the coordinate's own size.
    Returns ``None`` when either point leaves the box or crosses a row of
    ``inequalities``, where the model is clamped, or when the difference
    is under what fp64 resolves against S (:data:`_PREDICTED_FLOOR`), or not
    finite.  It may be negative.
    """
    h = _CURVATURE_STEP * max(abs(float(x[i])), 1.0)
    if x[i] - h < lo[i] or x[i] + h > hi[i]:
        return None
    e = np.zeros_like(x)
    e[i] = h
    if any(iq.crossed(x, e) or iq.crossed(x, -e) for iq in inequalities or ()):
        return None
    r_plus, r_minus = residual(x + e), residual(x - e)
    diff = float(r_plus @ r_plus) + float(r_minus @ r_minus) - 2.0 * s
    if not np.isfinite(diff) or abs(diff) <= _PREDICTED_FLOOR * max(abs(s), 1.0):
        return None
    return 0.5 * diff / h**2


def _solve_step(A: np.ndarray, b: np.ndarray, lam: float, x: np.ndarray,
                lo: np.ndarray, hi: np.ndarray, *, n_rows: int,
                scale: np.ndarray | None = None
                ) -> tuple[np.ndarray, np.ndarray]:
    """One damped Gauss-Newton step, solved exactly inside the box (WP-1937).

    Minimises the model ``½ΔᵀA_λΔ − bᵀΔ`` subject to ``lo − x ≤ Δ ≤ hi − x``.
    λ rides on the *pre-conditioned* diagonal (A_ii = 1), so adding ``lam`` to
    a copy of A scaled to unit diagonal is the same thing as Marquardt's
    multiplicative form and keeps the published constants meaningful.

    The bounded quadratic is handed to bounded-variable least squares (Stark &
    Parker 1995, ``scipy.optimize.lsq_linear(method="bvls")``) as the square
    system ``R = Λ^½Vᵀ``, ``c = Λ^-½Vᵀb`` from the eigendecomposition of the
    equilibrated A, for which ``‖RΔ − c‖² = ΔᵀAΔ − 2bᵀΔ + const``.  BVLS is an
    active-set method: a variable it holds is *on* its bound, never near it,
    and its solve is exact rather than the truncated CG of :mod:`.bccg`.  That
    is the case scipy's TRF cannot handle — several widths pressed on zero
    together, where its interior scaling crawls (WP-1929's grid).

    **The eigenvalue cut** (:data:`_EIGEN_CUT_PER_ROW`): A is formed as JᵀJ,
    so each equilibrated entry is an inner product over m = ``n_rows`` terms
    of two unit-norm columns, and carries a rounding error up to
    γₘ = m·u/(1 − m·u) with u = ε/2 (Higham 2002, §3.1).  An eigenvalue below
    ``m·ε·λmax`` is at that error's scale, so its direction is discarded and
    the step there is zero, BVLS solving the remaining rank-deficient system
    to minimum norm.  The cut binds only near λ = 0: a damped system has every
    eigenvalue at or above λ.

    **Above** :data:`BVLS_MAX_COLUMNS` the step is projected conjugate
    gradients (:func:`.bccg.projected_cg`, WP-1953) on the same scaled model
    and box.  scipy's BVLS refactors the free set from scratch at each
    active-set change, so its cost grows as n³ times the number of changes,
    and a Pawley block appends one column per reflection: 0.7-3.1 s a solve at
    1 500 columns, where the projected CG takes under 0.64 s.  Its step always
    lowers the model, which BCCG's, the step here until WP-1953, did not.  It
    makes no eigenvalue cut, and on FAP.XRA's Pawley fit that is the
    difference between BVLS's Rwp 0.0803 and TRF's 0.0782, which it reaches.

    **A sparse A** (``minimize``'s ``normal_equations``, WP-2011) is scaled
    and damped sparse, and the projected CG then preconditions on the free
    block's incomplete LU.  Unpreconditioned, a pseudo-symmetric Pawley
    candidate's solves spent nearly their whole budget: on 11-BM NAC's
    monoclinic candidate of 2224 reflections (59 498 points, macOS arm64,
    ``[dev]``) the fit took 376 s, 65 % of it in the CG and 22 % forming the
    dense JᵀJ.  The sparse A alone took it to 163 s, and the preconditioner to
    34-38 s: ~120 Hessian products a solve against ~4000, the last stage 13
    iterations against 89, Rwp 0.12592 against 0.12591.  On 15 other
    validation cells (30-849 columns) and two NAC candidates of 1223-1241
    reflections, Rwp to four decimals and every other reading were unchanged;
    those two ran 10.5 s and 8.9 s against 11.1 s and 12.0 s dense.
    FAP.XRA's Pawley fit, well conditioned, ran 1.3-1.4 s against 1.1 s, at
    the same Rwp to seven decimals, its profile stage taking 12 iterations
    against 9.
    A sparse A at or under the cut is densified, since BVLS needs the
    eigendecomposition.

    **A dense A** past the cut takes the face's Newton step through the free
    block's Cholesky factor, shifted where the block is singular, and a
    projected search along it (WP-2011).  Pseudo-symmetric Pawley candidates
    built from lab patterns put one reflection of most pairs on its zero
    floor.  Cutting CG at the first bound did that one bound per restart,
    and the largest solve spent its whole budget.  On zircon's candidate
    (601 columns) the largest solve now takes 157 products against 1204, the
    validation 1 274 against 16 851, and its step solves 0.18 s against
    0.77 s.  On corundum's (576 columns) the figures are 128 against 1154,
    787 against 12 654, and 0.14 s against 0.65 s.  Rwp, unmatched and absent
    lines are unchanged on both, and FAP.XRA's Pawley fit is unchanged to
    seven decimals with the same iterations per stage (macOS arm64,
    ``[dev]``).

    Returns the step and which bound each variable was solved onto (−1 lower,
    +1 upper, 0 neither), so the caller can land those variables *exactly* on
    the bound the solve chose.
    """
    n = len(b)
    if sparse.issparse(A) and n <= BVLS_MAX_COLUMNS:
        A = A.toarray()
    d = np.sqrt(np.maximum(_diagonal(A), 0.0)) if scale is None else scale
    d = np.where(d > 0.0, d, 1.0)
    inv_d = 1.0 / d
    if sparse.issparse(A):
        D = sparse.diags(inv_d)
        A_s = (D @ A @ D + lam * sparse.identity(n)).tocsr()
    else:
        A_s = A * np.outer(inv_d, inv_d)
        A_s[np.diag_indices(n)] += lam
    b_s = b * inv_d
    if n > BVLS_MAX_COLUMNS:
        y, side = bccg.projected_cg(A_s, b_s, (lo - x) * d, (hi - x) * d)
        return y * inv_d, side
    w, V = lapack.eigh(A_s)
    w_max = float(w[-1]) if n else 0.0
    keep = w > _EIGEN_CUT_PER_ROW * max(n_rows, n) * w_max
    side = np.zeros(n, dtype=np.int8)
    if w_max <= 0.0 or not np.any(keep):
        return np.zeros(n), side
    root = np.sqrt(w[keep])
    Vk = V[:, keep]
    R = root[:, None] * Vk.T
    c = (Vk.T @ b_s) / root
    lb, ub = (lo - x) * d, (hi - x) * d
    out = lsq_linear(R, c, bounds=(lb, ub), method="bvls")
    side[out.active_mask < 0] = -1
    side[out.active_mask > 0] = 1
    return out.x * inv_d, side


class _NoConstrainedStep(RuntimeError):
    """The least-distance solve did not return a step (nnls hit its iteration
    cap, or reported the rows inconsistent where Δ = 0 satisfies them)."""


def _solve_constrained_step(A: np.ndarray, b: np.ndarray, lam: float, x: np.ndarray,
                            lo: np.ndarray, hi: np.ndarray,
                            inequalities: list[LinearInequality], *, n_rows: int,
                            scale: np.ndarray | None = None
                            ) -> tuple[np.ndarray, np.ndarray]:
    """The damped step over the box *and* the linear-inequality rows (WP-1938 D8).

    Minimises :func:`_solve_step`'s model ``½ΔᵀA_λΔ − bᵀΔ`` subject to
    ``lo − x ≤ Δ ≤ hi − x`` and ``T·(x + Δ) + c ≥ min(T·x + c, 0)`` for every
    row of every block.  Δ = 0 satisfies all of them, so the problem always
    has a solution.  It is a least-squares problem with linear inequality
    constraints (LSI), solved exactly by the route of Lawson, C. L. & Hanson,
    R. J. (1974). *Solving Least Squares Problems*, ch. 23. Englewood Cliffs:
    Prentice-Hall:

    1. **LSI.**  In the equilibrated variable s = d·Δ the model is
       ``½sᵀHs − gᵀs`` with ``H = VΛVᵀ``, which is ``½‖Es − f‖²`` up to a
       constant for ``E = Λ^½Vᵀ`` and ``f = Λ^-½Vᵀg``.  The box limits join
       the rows as ``±s_i ≥ …``, giving ``Gs ≥ h``.
    2. **LSI → LDP.**  E is a scaled rotation, so ``z = Es − f`` inverts as
       ``s = s₀ + E⁻¹z``, with ``s₀ = H⁻¹g`` the unconstrained minimiser.  The
       model is then ``½‖z‖²``, and the step is the least-distance problem
       ``min ‖z‖`` subject to ``(GE⁻¹)z ≥ h − Gs₀``.
    3. **LDP → NNLS.**  :func:`_least_distance`, by ``scipy.optimize.nnls``,
       Lawson & Hanson's own algorithm.

    Two numerical steps sit on top of the textbook route.  The directions the
    eigenvalue cut discards get curvature :data:`_NULL_CURVATURE`·λmax, the
    tie-break that keeps E invertible.  And ``s = s₀ + E⁻¹z`` cancels when the
    unconstrained minimiser lies far outside the rows, so the rows active at
    z, those with ``u > 0``, are then solved as equalities
    (:func:`_equality_step`), which never forms s₀.  That polished point is
    kept when it satisfies the problem's optimality conditions
    (:data:`_POLISH_FEASIBLE`), and the least-distance point otherwise.

    Returns the step and which bound each variable was solved onto, as
    :func:`_solve_step` does: −1 for an active lower box row, +1 for an
    active upper one.  The caller lands those variables exactly on the bound.
    A sparse A is densified: the route is an eigendecomposition.
    """
    if sparse.issparse(A):
        A = A.toarray()
    n = len(b)
    eps = float(np.finfo(np.float64).eps)
    d = np.sqrt(np.maximum(np.diag(A), 0.0)) if scale is None else scale
    d = np.where(d > 0.0, d, 1.0)
    inv_d = 1.0 / d
    H = A * np.outer(inv_d, inv_d)
    H[np.diag_indices(n)] += lam
    g = b * inv_d
    w, V = lapack.eigh(H)
    w_max = float(w[-1]) if n else 0.0
    side = np.zeros(n, dtype=np.int8)
    if w_max <= 0.0:
        return np.zeros(n), side
    keep = w > _EIGEN_CUT_PER_ROW * max(n_rows, n) * w_max
    w = np.where(keep, w, _NULL_CURVATURE * w_max)
    root = np.sqrt(w)
    f = np.where(keep, (V.T @ g) / root, 0.0)
    E_inv = V / root
    s0 = E_inv @ f
    H = (V * w) @ V.T                       # the model the rows are solved over

    lb, ub = (lo - x) * d, (hi - x) * d
    has_lo, has_hi = np.isfinite(lb), np.isfinite(ub)
    eye = np.eye(n)
    T = np.vstack([iq.T for iq in inequalities]) * inv_d
    slack = np.concatenate([iq.slack(x) for iq in inequalities])
    G = np.vstack([eye[has_lo], -eye[has_hi], T])
    h = np.concatenate([lb[has_lo], -ub[has_hi], -np.maximum(slack, 0.0)])
    # which variable and bound each box row is, for ``side``
    var = np.concatenate([np.flatnonzero(has_lo), np.flatnonzero(has_hi),
                          np.full(len(T), -1)])
    sign = np.concatenate([np.full(int(has_lo.sum()), -1), np.full(int(has_hi.sum()), 1),
                           np.zeros(len(T), dtype=int)])

    G_z = G @ E_inv
    h_z = h - G @ s0
    norm = np.linalg.norm(G_z, axis=1)
    live = norm > 0.0
    G, h, var, sign = G[live], h[live], var[live], sign[live]
    G_z, h_z = G_z[live] / norm[live, None], h_z[live] / norm[live]
    if not np.any(h_z > 0.0):
        return s0 * inv_d, side            # the unconstrained minimiser is feasible
    z, u = _least_distance(G_z, h_z)
    s = s0 + E_inv @ z
    active = u > 0.0
    polished = _equality_step(H, g, G[active], h[active], eps)
    row_scale = np.linalg.norm(G, axis=1) * np.linalg.norm(polished) + np.abs(h)
    if np.all(G @ polished - h >= -_POLISH_FEASIBLE * row_scale):
        try:
            _, stationary = nnls(G[active].T, H @ polished - g)
        except RuntimeError:
            # nnls's iteration cap: the polish is unverified, so the
            # least-distance point stands
            stationary = np.inf
        if stationary <= _POLISH_STATIONARY * max(np.linalg.norm(g),
                                                  np.linalg.norm(H @ polished)):
            s = polished
    on_box = active & (var >= 0)
    side[var[on_box]] = sign[on_box]
    return s * inv_d, side


def _least_distance(G: np.ndarray, h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lawson & Hanson (1974, ch. 23)'s problem LDP: the shortest z with Gz ≥ h.

    It is solved through non-negative least squares,
    ``min ‖Eu − f‖`` over ``u ≥ 0`` with ``E = [Gᵀ; hᵀ]`` and
    ``f = (0, …, 0, 1)``.  With ``ρ = Eu − f``, a zero ρ means the rows are
    inconsistent, and otherwise ``z = −ρ[:n]/ρ[n]``.  A row with ``u > 0`` is
    active at z, and u is its multiplier up to a common positive factor.

    The rows arrive at unit norm, and h is divided by its largest entry κ > 0
    before the solve and z multiplied by it after, which moves neither the
    solution nor the active set.  ρ shrinks as 1/‖z‖ while its rounding does
    not, so z is resolved best near unit length, and ‖z‖ ≥ max h.
    """
    n = G.shape[1]
    kappa = float(np.max(h))
    E = np.vstack([G.T, h / kappa])
    f = np.zeros(n + 1)
    f[-1] = 1.0
    try:
        u, _ = nnls(E, f, maxiter=10 * E.shape[1])
    except RuntimeError as exc:             # the iteration cap
        raise _NoConstrainedStep(str(exc)) from exc
    rho = E @ u - f
    if not rho[n] < 0.0:
        raise _NoConstrainedStep("nnls reports the rows inconsistent")
    return kappa * (-rho[:n] / rho[n]), u


def _equality_step(H: np.ndarray, g: np.ndarray, G: np.ndarray, h: np.ndarray,
                   eps: float) -> np.ndarray:
    """``min ½sᵀHs − gᵀs`` subject to ``Gs = h``, for H positive definite.

    The null-space method: the minimum-norm solution of ``Gs = h`` from the
    SVD of G, plus the minimiser along G's null space, where the reduced
    matrix ZᵀHZ is positive definite because H is.  The active rows of a
    degenerate vertex are dependent, and the SVD's rank absorbs them.  A
    rank-deficient G with slightly inconsistent h is met in the
    least-squares sense, and :func:`_solve_constrained_step` then checks the
    result against every row.
    """
    n = H.shape[0]
    if not len(G):
        return np.linalg.solve(H, g)
    U, sv, Wt = lapack.svd(G)
    rank = int(np.count_nonzero(sv > max(G.shape) * eps * sv[0]))
    s = Wt[:rank].T @ ((U[:, :rank].T @ h) / sv[:rank])
    Z = Wt[rank:].T
    if rank < n:
        s = s + Z @ np.linalg.solve(Z.T @ H @ Z, Z.T @ (g - H @ s))
    return s
