"""Model-free background estimation.

Implements arPLS (Baek, Park, Ahn & Choo, 2015, Analyst 140, 250) on the
Whittaker smoother (Eilers, 2003, Anal. Chem. 75, 3631), plus SNIP (Ryan et
al., 1988, Nucl. Instrum. Meth. B34, 396).  Independent implementations from
the papers; the pybaselines documentation (BSD-3, derb12) was used as an
algorithmic reference — see ATTRIBUTION.md.

The Whittaker system (W + λ DᵀD) z = W y with second-difference D is a banded
(pentadiagonal) linear solve, done here via ``scipy.linalg.solve_banded``.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import solve_banded


def _second_difference_penalty_banded(n: int, lam: float) -> np.ndarray:
    """λ·DᵀD for the (n−2, n) second-difference matrix D, as 5 diagonals in
    ``solve_banded`` layout (ab[u + i - j, j] = A[i, j], u = 2)."""
    ab = np.zeros((5, n), dtype=np.float64)
    # main diagonal of DᵀD: 1, 5, 6, 6, ..., 6, 5, 1
    main = np.full(n, 6.0)
    main[[0, -1]] = 1.0
    if n > 1:
        main[[1, -2]] = 5.0
    # first off-diagonal: -2, -4, -4, ..., -4, -2
    off1 = np.full(n - 1, -4.0)
    off1[[0, -1]] = -2.0
    # second off-diagonal: all 1
    off2 = np.full(n - 2, 1.0)
    ab[0, 2:] = lam * off2
    ab[1, 1:] = lam * off1
    ab[2, :] = lam * main
    ab[3, :-1] = lam * off1
    ab[4, :-2] = lam * off2
    return ab


def whittaker_solve(y: np.ndarray, weights: np.ndarray, lam: float) -> np.ndarray:
    """Solve (W + λ DᵀD) z = W y (Eilers 2003)."""
    n = len(y)
    ab = _second_difference_penalty_banded(n, lam)
    ab[2, :] += weights
    return solve_banded((2, 2), ab, weights * y)


def arpls(y: np.ndarray, lam: float = 1e7, *, max_iter: int = 50,
          tol: float = 1e-3) -> np.ndarray:
    """arPLS baseline (Baek et al. 2015).

    Iteratively reweighted Whittaker smoothing: points above the current
    baseline (Bragg peaks) get logistic weights → 0, points at/below keep
    weight → 1, so the smooth curve settles under the peaks.

    ``lam`` controls stiffness; larger = smoother.  For powder patterns with
    ~10⁴ points, λ of 1e6–1e9 is typical (choose with :func:`auto_lambda`).
    """
    y = np.asarray(y, dtype=np.float64)
    n = len(y)
    w = np.ones(n)
    z = y.copy()
    for _ in range(max_iter):
        z = whittaker_solve(y, w, lam)
        d = y - z
        dn = d[d < 0]
        if len(dn) < 2:
            break
        m, s = dn.mean(), dn.std()
        if s <= 0:
            break
        # Baek et al. eq. (14): logistic weighting from the negative-residual stats
        exponent = np.clip(2.0 * (d - (2.0 * s - m)) / s, -500, 500)
        w_new = 1.0 / (1.0 + np.exp(exponent))
        if np.linalg.norm(w - w_new) / max(np.linalg.norm(w), 1e-12) < tol:
            w = w_new
            break
        w = w_new
    return whittaker_solve(y, w, lam)


def snip(y: np.ndarray, max_half_window: int, *, decreasing: bool = True) -> np.ndarray:
    """SNIP baseline (Ryan et al. 1988) with LLS transform.

    ``max_half_window`` should be at least the half-width (in points) of the
    widest peak to suppress.
    """
    y = np.asarray(y, dtype=np.float64)
    # log-log-sqrt (LLS) transform compresses dynamic range (Ryan et al.)
    v = np.log(np.log(np.sqrt(np.maximum(y, 0.0) + 1.0) + 1.0) + 1.0)
    windows = range(max_half_window, 0, -1) if decreasing else range(1, max_half_window + 1)
    for m in windows:
        padded = np.pad(v, m, mode="edge")
        avg = 0.5 * (padded[: len(v)] + padded[2 * m:])
        v = np.minimum(v, avg)
    return (np.exp(np.exp(v) - 1.0) - 1.0) ** 2 - 1.0


def auto_lambda(y: np.ndarray, *, candidates: tuple[float, ...] = tuple(10.0 ** e for e in range(4, 11))
                ) -> float:
    """Pick the arPLS λ whose baseline is smooth but still follows the data.

    Heuristic criterion: largest λ for which the fraction of points where the
    baseline exceeds the data by more than 3σ_noise stays below 1%.  (σ_noise
    from the median absolute successive difference.)

    Deliberately a heuristic and still one: a synthetic-peak criterion (inject
    a known peak, pick the λ that recovers its area) would be better-founded but
    has never been the limiting factor, because the *order-selection* path
    (`background.select`, BIC + Durbin-Watson) and the
    ``BACKGROUND_ABSORPTION`` guard both sit downstream of it and catch an
    over-flexible baseline on their own terms.
    """
    y = np.asarray(y, dtype=np.float64)
    noise = np.median(np.abs(np.diff(y))) / 0.7979 + 1e-12  # E|N(0,σ)| = σ·0.798
    best = candidates[0]
    for lam in candidates:
        z = arpls(y, lam)
        overshoot = np.mean(z > y + 3.0 * noise)
        if overshoot < 0.01:
            best = lam
    return best
