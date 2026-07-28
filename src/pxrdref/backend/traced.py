"""The traced residual — written once, for every autodiff backend.

``ParameterTable.decode`` and ``optimize.least_squares._make_residual`` are the
numpy reference, and neither is traceable: ``decode`` runs
``to_physical(float(t))`` per element, and the ``float()`` coercions collapse a
tracer to a constant.  So an autodiff backend needs a *twin* of each — and
until this module existed, jax and torch each carried their own copy of both.

Two copies of a pure function is two chances to drift, and WP-0408 measured the
cost of that: when WP-0406's soft-restraint rows landed, they had to be added to
the torch twin by hand, after the fact, because nothing structural tied the
copies together.  Here the twin is written once and parameterised by ``xp``:

* the **transform application** goes through ``xp.logaddexp`` / ``xp.exp`` /
  ``xp.sigmoid``, which every backend provides in its overflow-safe form, so
  the traced decode reproduces ``params.transforms.to_physical`` rather than
  approximating it;
* the **row layout** is not written here at all — :mod:`pxrdref.model.rows`
  owns it, and the numpy reference builds from the same assembler.

A new backend therefore inherits both for free, and
``tests/test_backend_conformance.py`` holds every registered backend to the
numpy residual on every golden state.

Two rules the shared implementation has to get right, both learned the hard way:

* **Lift every frozen numpy constant onto the backend** before it can appear on
  the left of an operator against a traced value — ``ndarray * tensor`` raises
  on torch, and ``tensor * ndarray`` routes through numpy's deprecated
  ``__array_wrap__`` and then fails under a functorch transform (CLAUDE.md →
  Conventions).
* **Lift them inside the traced call, not at build time.**  jax's fp64 is
  *scoped* (``jax.enable_x64`` around the trace/execute site), so a constant
  materialised when the closure is built — outside that scope — silently
  becomes float32 and quietly halves the precision of everything downstream.
  Inside the call it is traced under the scope and baked into the jitted graph
  as a constant, so this costs nothing per iteration.  This is exactly the
  regression the shared implementation hit first: the Pawley aux columns, which
  are exactly linear and agreed to 6.7e-14, drifted to 1e-7.
"""

from __future__ import annotations

from contextlib import contextmanager

import numpy as np

from ..model import rows
from .api import get_backend, set_backend


@contextmanager
def active(xp):
    """The context a traced residual must be *evaluated* in.

    Two things have to hold at once, and both were previously the caller's
    problem:

    * ``xp`` is the **globally active** backend, because the forward model
      binds ``get_backend()`` internally — evaluate a torch-traced residual
      with numpy active and the first ``xp.stack`` over device scalars tries to
      convert them to numpy and raises;
    * the backend's precision scope is open (``full_precision``), which on jax
      is what makes fp64 fp64.

    :func:`make_traced_residual` wraps its own body in this, so every caller —
    the Jacobian builders, tests, and anything a future backend adds — is
    correct by construction rather than by remembering.
    """
    prev = get_backend()
    set_backend(xp)
    try:
        with xp.full_precision():
            yield
    finally:
        set_backend(prev)


def make_traced_decode(table, xp):
    """Traceable twin of :meth:`ParameterTable.decode` (θ → value dict).

    Builds the same map from frozen constants: elementwise transform
    application (grouped by kind into *static* masks) followed by the dense
    constant matmul p = C·θ_phys + d.  Values come back as 0-d traced scalars
    keyed by dot-path — exactly the dict shape the forward model consumes.

    The masks are static python/numpy booleans, and both branches of every
    ``where`` are smooth everywhere, so the discarded branch cannot poison the
    selected tangent (a NaN or an inf there would propagate through the
    derivative even where it is not selected).
    """
    C, d = table.constraint_block()
    # kept as host fp64 and lifted *inside* the call — see the module docstring
    C_host = np.asarray(C.toarray(), dtype=np.float64)
    d_host = np.asarray(d, dtype=np.float64)
    paths = [e.path for e in table.entries]
    transforms = [table.entries[i].transform for i in table._free_idx]
    masks = {kind: np.array([t == kind for t in transforms])
             for kind in set(transforms) if kind != "identity"}
    apply = {"softplus": lambda u: xp.logaddexp(xp.zeros_like(u), u),
             "exp": xp.exp,
             "logit": xp.sigmoid}
    unknown = set(masks) - set(apply)
    if unknown:   # a new transform kind must land here as well as in transforms.py
        raise NotImplementedError(
            f"traced decode has no rule for transform kind(s) {sorted(unknown)}; "
            "add it here and to params.transforms.to_physical together")

    def decode(theta):
        p = theta
        for kind, mask in masks.items():
            p = xp.where(mask, apply[kind](theta), p)
        full = xp.matmul(xp.asarray(C_host), p) + xp.asarray(d_host)
        # scalarize: these 0-d values come from *indexing*, not from an op, so
        # a backend's own result guard has not seen them (identity everywhere
        # except torch-MPS — see backend.api.scalar_tensor_class)
        return {path: xp.scalarize(full[i]) for i, path in enumerate(paths)}

    return decode


def make_traced_residual(model, table, xp):
    """The weighted residual as a pure traceable function of the combined θ.

    Mirrors ``optimize.least_squares._make_residual`` by *construction*, not by
    inspection: both call :func:`pxrdref.model.rows.assemble`, so the block
    order — [data | background-penalty | Pawley-restraint | soft-restraint] —
    exists in one place for every backend.  The Le Bail intensity snapshot and
    every weight/design constant are closed over as constants of the trace,
    exactly as they are constants of the numpy closure.

    The soft-restraint rows (bond/angle/value) are one differentiable function
    of the decoded coordinates and cell, so a forward-mode transform
    differentiates them with no extra wiring.
    """
    decode = make_traced_decode(table, xp)
    n_table = len(table.free_paths)
    sqrt_w_host = np.asarray(1.0 / model.sigma, dtype=np.float64)
    y_obs_host = np.asarray(model.y_obs, dtype=np.float64)
    # Le Bail extraction runs *between* solves; the snapshot is a constant of
    # the trace exactly as it is a constant of the numpy closure
    fixed_host = ([np.asarray(cp.hkl_intensity, dtype=np.float64)
                   for cp in model.phases] if model.mode == "lebail" else None)
    empty_host = np.zeros(0, dtype=np.float64)

    def residual(theta):
        # constants are lifted *here*, not above: fp64 is scoped on jax, and
        # the scope is only open inside ``active`` (module docstring)
        with active(xp):
            # θ is lifted *inside* the scope too: a caller who converted it
            # first, outside, would have handed jax a float32 vector and got a
            # float32 answer from an fp64 model without any error at all
            theta = xp.asarray(theta)
            if model.pawley is not None:
                aux = theta[n_table:]
                intens = model.split_pawley_intensities(aux)
                values = decode(theta[:n_table])
            else:
                aux = xp.asarray(empty_host)
                intens = (None if fixed_host is None
                          else [xp.asarray(v) for v in fixed_host])
                values = decode(theta)
            return rows.assemble(model, rows.ResidualInputs(
                values=values, intens=intens, theta_aux=aux,
                sqrt_w=xp.asarray(sqrt_w_host), y_obs=xp.asarray(y_obs_host),
                xp=xp))

    return residual
