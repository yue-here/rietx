"""Chunked-jacfwd Jacobians on the jax backend (WP-0402).

The forward model was written differentiable from day one — frozen-per-stage
discreteness keeps every θ-dependent branch out of the graph (window bounds,
FCJ node counts and the hkl list are compile-time constants; the remaining
θ-dependent guards are ``where``-masks) — so the *whole* weighted residual
traces cleanly and forward-mode autodiff reproduces the analytic/FD Jacobian
exactly.  Cost is one tangent per column ≈ one forward evaluation each
(Nocedal & Wright, 2006, *Numerical Optimization*, ch. 8), the same order as
plain FD, but exact and jit-compiled.

Design (docs/wp/0402-jax-backend.md):

* **Scoped x64, never at import.**  Every trace/execute site sits inside the
  ``enable_x64`` context manager (re-entrant; the x64 state is part of the jit
  trace context, hence of the executable cache key), so a numpy-only user's
  process — or a jax user's fp32 world — never sees the global flag flipped.
* **Frozen state closed over as constants.**  The residual closure reads the
  compiled model's numpy buffers (windows, design matrices, restraint rows,
  Le Bail intensity snapshot) directly; only θ is traced.  ``jit`` embeds them
  once, and one XLA executable is reused across all seed chunks (the last
  chunk is zero-padded to keep the shape).
* **Dense-C decode.**  ``ParameterTable`` promises p = C·θ_phys + d is a
  constant affine map during a solve; the scipy.sparse C is materialised dense
  here and the softplus/exp/logit transforms become elementwise jnp ops, so
  ``decode`` is exact under autodiff.
* **Host boundary.**  The produced Jacobian is a plain fp64 numpy array in
  ``optimize.least_squares._make_jacobian``'s exact row/column layout
  ([data | background-penalty | Pawley-restraint] rows × [table θ | Pawley
  intensities] columns, sign folded in via r = √w·(y_obs − y_calc)); the TRF
  driver, cost/statistics and the solve all stay numpy fp64.
"""

from __future__ import annotations

import numpy as np

from .api import get_backend, resolve_backend, set_backend
from .traced import make_traced_decode as _make_traced_decode
from .traced import make_traced_residual as _make_traced_residual

#: parameter-axis chunk for the vmapped one-hot tangent seeds; peak memory is
#: ≈ chunk × n_rows × 8 B per block (≈ 1.3 MB at 5·10³ points), overridable
#: per call
DEFAULT_CHUNK = 32


def _enable_x64():
    """The scoped-x64 context manager — now :meth:`JaxBackend.full_precision`,
    kept as a module-level name because call sites and tests import it."""
    return resolve_backend("jax").full_precision()


def make_traced_decode(table):
    """jax's traced decode — :func:`backend.traced.make_traced_decode` bound to
    this backend.  Kept as a name here because callers and tests import it."""
    return _make_traced_decode(table, resolve_backend("jax"))


def make_traced_residual(model, table):
    """jax's traced residual — :func:`backend.traced.make_traced_residual`
    bound to this backend.

    The body lives in ``backend/traced.py`` so jax and torch cannot drift from
    each other, and the row layout lives in ``model/rows.py`` so neither can
    drift from the numpy reference.
    """
    return _make_traced_residual(model, table, resolve_backend("jax"))


def make_jax_jacobian(model, table, *, chunk_size: int = DEFAULT_CHUNK):
    """A drop-in replacement for ``_make_jacobian``'s callable, via jacfwd.

    Chunks over the *parameter* axis: ``vmap`` over blocks of ``chunk_size``
    one-hot tangent seeds through one jit-compiled jvp, reusing a single XLA
    executable for every block (the trailing block is zero-padded to shape).
    The active backend is flipped to jax only inside the call (and restored),
    so residual evaluations before/after stay on the numpy path.
    """
    import jax
    import jax.numpy as jnp

    xp_jax = resolve_backend("jax")
    residual = make_traced_residual(model, table)

    @jax.jit
    def jvp_block(theta, seeds):
        return jax.vmap(lambda s: jax.jvp(residual, (theta,), (s,))[1])(seeds)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        theta = np.asarray(theta, dtype=np.float64)
        n = theta.shape[0]
        prev = get_backend()
        set_backend(xp_jax)
        try:
            with _enable_x64():
                t = jnp.asarray(theta)
                eye = np.eye(n, dtype=np.float64)
                blocks = []
                for a in range(0, n, chunk_size):
                    seeds = eye[a:a + chunk_size]
                    if seeds.shape[0] < chunk_size:
                        seeds = np.concatenate(
                            [seeds, np.zeros((chunk_size - seeds.shape[0], n))])
                    blocks.append(np.asarray(jvp_block(t, jnp.asarray(seeds)),
                                             dtype=np.float64))
            J = np.concatenate(blocks, axis=0)[:n]
        finally:
            set_backend(prev)
        return np.ascontiguousarray(J.T)

    return jacobian
