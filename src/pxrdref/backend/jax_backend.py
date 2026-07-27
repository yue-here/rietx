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

#: parameter-axis chunk for the vmapped one-hot tangent seeds; peak memory is
#: ≈ chunk × n_rows × 8 B per block (≈ 1.3 MB at 5·10³ points), overridable
#: per call
DEFAULT_CHUNK = 32


def _enable_x64():
    """The scoped-x64 context manager across jax versions (≥ 0.11: top-level;
    older: ``jax.experimental``)."""
    import jax

    try:
        return jax.enable_x64()
    except AttributeError:  # pragma: no cover - depends on installed jax
        from jax.experimental import enable_x64

        return enable_x64()


def make_traced_decode(table):
    """Traceable twin of :meth:`ParameterTable.decode` (θ → value dict).

    The numpy ``decode`` runs ``to_physical(float(t))`` per element — the
    ``float()`` coercions make it untraceable.  This builds the same map from
    frozen constants: elementwise transform application (grouped by kind into
    static masks) followed by the dense constant matmul p = C·θ_phys + d.
    Values come back as 0-d traced scalars keyed by dot-path, exactly the
    dict shape the forward model consumes.
    """
    import jax
    import jax.numpy as jnp

    C, d = table.constraint_block()
    C_dense = np.asarray(C.toarray(), dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    paths = [e.path for e in table.entries]
    transforms = [table.entries[i].transform for i in table._free_idx]
    masks = {kind: np.array([t == kind for t in transforms])
             for kind in set(transforms) if kind != "identity"}
    apply = {"softplus": lambda u: jnp.logaddexp(0.0, u),
             "exp": jnp.exp,
             "logit": jax.nn.sigmoid}

    def decode(theta):
        p = theta
        for kind, mask in masks.items():
            # static mask; both branches are smooth everywhere, so the
            # discarded branch cannot poison the selected tangent
            p = jnp.where(mask, apply[kind](theta), p)
        full = C_dense @ p + d
        return {path: full[i] for i, path in enumerate(paths)}

    return decode


def make_traced_residual(model, table):
    """The weighted residual as a pure traceable function of the combined θ.

    Mirrors ``optimize.least_squares._make_residual`` row for row — [data |
    background-penalty | Pawley-restraint | soft-restraint] — with the Le Bail
    intensity snapshot and every weight/design constant closed over.  The
    soft-restraint rows (bond/angle/value) are one differentiable function of
    the decoded coordinates and cell, so jacfwd differentiates them
    automatically.  Any drift between the two is caught by the jax-vs-numpy
    column tests in ``tests/test_backend_jax.py``.
    """
    import jax.numpy as jnp

    decode = make_traced_decode(table)
    n_table = len(table.free_paths)
    sqrt_w = np.asarray(1.0 / model.sigma, dtype=np.float64)
    y_obs = np.asarray(model.y_obs, dtype=np.float64)
    # Le Bail extraction runs *between* solves; the snapshot is a constant of
    # the trace exactly as it is a constant of the numpy closure
    fixed_intens = ([np.asarray(cp.hkl_intensity, dtype=np.float64)
                     for cp in model.phases] if model.mode == "lebail" else None)

    def residual(theta):
        if model.pawley is not None:
            intens = model.split_pawley_intensities(theta[n_table:])
            values = decode(theta[:n_table])
        else:
            intens = fixed_intens
            values = decode(theta)
        r = sqrt_w * (y_obs - model.evaluate(values, intens))
        parts = [r]
        pen = model.penalty_residual(values)
        if pen is not None:
            parts.append(pen)
        if model.pawley is not None:
            rpen = model.pawley_restraint_residual(theta[n_table:])
            if rpen is not None:
                parts.append(rpen)
        rr = model.restraint_residual(values)
        if rr is not None:
            parts.append(rr)
        return parts[0] if len(parts) == 1 else jnp.concatenate(parts)

    return residual


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
