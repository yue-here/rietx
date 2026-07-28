"""The fp64 host boundary, and the mixed-precision policy that lives on it.

This module is the *one* place where reduced precision is permitted to touch
anything, and the one place that casts back. DESIGN.md architecture invariant
2 (also in CLAUDE.md):

    The residual used for cost/statistics and the parameter solve/covariance
    are always fp64 on host.  GPU fp32 is restricted to Jacobian *columns*.

Why the asymmetry
-----------------
* **The residual cancels.**  r = √w·(y_obs − y_calc) subtracts two numbers of
  order 10⁵ counts to leave a difference of order 10².  fp32 carries ~7
  significant decimal digits, so y_calc — itself an accumulation over
  reflections, emission lines and quadrature nodes — arrives with an absolute
  error of order 10 counts, i.e. ~10 % of the very quantity being formed.
  χ², Rwp, GoF and the esds all read that difference.
* **The solve squares the conditioning.**  cond(JᵀJ) = cond(J)² (Higham 2002,
  *Accuracy and Stability of Numerical Algorithms*, 2nd ed., SIAM, ch. 20).
  A Rietveld normal matrix at cond(J) ~ 10⁴ — routine once cell, zero and
  displacement are free together — leaves cond(JᵀJ) ~ 10⁸, which fp32 cannot
  invert at all.
* **Jacobian columns are relative-accuracy tolerant.**  A column enters only
  through a descent direction and a curvature estimate.  Losing the bottom
  bits of ∂y/∂θ_c perturbs the *step*, which the trust region then re-measures
  against an fp64 cost; it does not perturb the answer the step converges to.
  This is why the fp64/fp32 boundary is drawn between J and everything else,
  rather than between host and device.

Simulating fp32 on the CPU
--------------------------
``MixedPrecisionPolicy(jacobian_dtype="fp32").cast_columns`` round-trips each
column ``col.astype(float32).astype(float64)``.  That reproduces the fp32
*representation* limit exactly — which is precisely what a device fp32 column
costs when it crosses this boundary — and it is deterministic, so the policy
is unit-testable with no GPU present.  It does **not** reproduce error
accumulated *inside* a device's fp32 forward pass; that is strictly larger,
and measuring it needs real hardware (WP-0408 torch-MPS, which consumes this
same policy object).  The tolerances below are therefore sized for the real
device case and the CPU simulation clears them with orders of magnitude to
spare — the CPU gate proves the *plumbing* (that reduced columns cannot leak
into the residual or the solve), not the device's numerics.

Nothing here is a user-facing default: ``jacobian_dtype`` is fp64 unless a
backend or a test explicitly opts in via :func:`precision_policy`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

#: reduced-precision Jacobian agreement bars, shared with WP-0404's
#: cross-backend CI: per-column relative L2 distance and cosine similarity
#: against the fp64 reference column
COLUMN_REL_L2_MAX = 2e-2
COLUMN_COSINE_MIN = 0.999

Precision = Literal["fp32", "fp64"]

_DTYPES: dict[str, Any] = {"fp32": np.float32, "fp64": np.float64}


@dataclass(frozen=True)
class MixedPrecisionPolicy:
    """Which parts of a least-squares step may run below fp64.

    Only ``jacobian_dtype`` is a field.  ``residual_dtype`` and ``solve_dtype``
    are read-only properties pinned to fp64: the invariant is code, not a
    setting, and there is deliberately no way to spell the configuration that
    would violate it.
    """

    jacobian_dtype: Precision = "fp64"

    def __post_init__(self) -> None:
        if self.jacobian_dtype not in _DTYPES:
            raise ValueError(
                f"jacobian_dtype must be one of {sorted(_DTYPES)}, "
                f"got {self.jacobian_dtype!r}")

    @property
    def residual_dtype(self) -> Any:
        """fp64, always — the residual cancels (see the module docstring)."""
        return np.float64

    @property
    def solve_dtype(self) -> Any:
        """fp64, always — JᵀJ squares the condition number."""
        return np.float64

    @property
    def reduced(self) -> bool:
        """True when Jacobian columns are to be computed below fp64."""
        return self.jacobian_dtype != "fp64"

    def cast_column(self, col: Any) -> np.ndarray:
        """One Jacobian column at the reduced precision, returned as fp64.

        The identity when the policy is fp64 — the numpy path must not pay for
        a policy nobody enabled.
        """
        col = to_host_fp64(col)
        if not self.reduced:
            return col
        return col.astype(_DTYPES[self.jacobian_dtype]).astype(np.float64)

    def cast_columns(self, J: Any) -> np.ndarray:
        """:meth:`cast_column` applied down every column of ``J``.

        Column-granular by construction.  For the numpy round-trip the cast is
        elementwise, so the loop is bit-identical to a whole-array cast — it is
        written this way because that is the *contract*: a device backend hands
        back one column (or one vmapped block) at a time, only columns are
        eligible for reduction, and a hook shaped like this structurally cannot
        reach the residual or the normal matrix.
        """
        J = to_host_fp64(J)
        if not self.reduced or J.size == 0:
            return J
        if J.ndim == 1:
            return self.cast_column(J)
        out = np.empty_like(J)
        for c in range(J.shape[1]):
            out[:, c] = self.cast_column(J[:, c])
        return out


#: the default — everything fp64, the numpy path exactly as it was
FP64 = MixedPrecisionPolicy()
#: opt-in: Jacobian columns at fp32, residual and solve still fp64
FP32_JACOBIAN = MixedPrecisionPolicy(jacobian_dtype="fp32")

_POLICY: MixedPrecisionPolicy = FP64


def get_precision_policy() -> MixedPrecisionPolicy:
    """The active policy (fp64 unless something opted in)."""
    return _POLICY


def set_precision_policy(policy: MixedPrecisionPolicy) -> None:
    """Install a policy globally.  Prefer :func:`precision_policy`, which
    restores the previous one; this mirrors ``backend.set_backend`` for the
    cases that genuinely need process-wide state."""
    global _POLICY
    if not isinstance(policy, MixedPrecisionPolicy):
        raise TypeError(f"expected a MixedPrecisionPolicy, got {type(policy)!r}")
    _POLICY = policy


@contextlib.contextmanager
def precision_policy(policy: MixedPrecisionPolicy) -> Iterator[MixedPrecisionPolicy]:
    """Scope a policy to a ``with`` block, restoring the previous one after."""
    previous = get_precision_policy()
    set_precision_policy(policy)
    try:
        yield policy
    finally:
        set_precision_policy(previous)


def to_host_fp64(a: Any) -> np.ndarray:
    """The single explicit fp64 host cast of an array crossing this boundary.

    Every backend's Jacobian goes through here before it reaches JᵀJ, so a
    device array that arrived as fp32 (or as a jax/torch handle) becomes a
    plain fp64 numpy array in exactly one place.

    An array living on an accelerator is brought back first: ``np.asarray`` on
    an MPS/CUDA tensor raises rather than transferring, so a backend whose
    results never touch host memory would otherwise have to open-code the
    transfer (and could open-code it *differently*).
    """
    if hasattr(a, "detach"):          # torch tensor, possibly on a device
        a = a.detach().cpu()
    return np.asarray(a, dtype=np.float64)


def require_fp64(a: Any, what: str) -> np.ndarray:
    """Assert ``a`` is already fp64 (never cast) — the invariant, as a check.

    Used on the residual and on the matrix entering the covariance solve.  A
    silent upcast there would hide the bug this exists to catch: something
    upstream having computed the quantity in reduced precision.
    """
    arr = np.asarray(a)
    if arr.dtype != np.float64:
        raise TypeError(
            f"{what} must be fp64 on host (architecture invariant 2), got "
            f"{arr.dtype}; reduced precision is permitted for Jacobian "
            f"columns only — see backend/linalg64.py")
    return arr


def column_agreement(J_ref: Any, J_test: Any) -> tuple[float, float]:
    """(worst relative-L2 distance, worst cosine similarity) over live columns.

    The metric behind :data:`COLUMN_REL_L2_MAX` / :data:`COLUMN_COSINE_MIN`.
    Columns whose fp64 norm is below 1e-12 of the largest are skipped: they are
    transform-floor noise (a softplus parameter parked at its zero floor), not
    derivatives, and their direction is meaningless to compare.
    """
    a64, b64 = to_host_fp64(J_ref), to_host_fp64(J_test)
    if a64.shape != b64.shape:
        raise ValueError(f"shape mismatch {a64.shape} vs {b64.shape}")
    norms = np.linalg.norm(a64, axis=0)
    scale = norms.max() if norms.size else 0.0
    worst_rel, worst_cos = 0.0, 1.0
    for c in range(a64.shape[1]):
        u, v = a64[:, c], b64[:, c]
        nu = norms[c]
        if nu < 1e-12 * scale:
            continue
        worst_rel = max(worst_rel, float(np.linalg.norm(v - u) / nu))
        nv = float(np.linalg.norm(v))
        if nv > 0.0:
            worst_cos = min(worst_cos, float(u @ v) / (nu * nv))
    return worst_rel, worst_cos
