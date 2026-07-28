"""Chunked forward-mode Jacobians on the torch backend (WP-0408).

The strategy differs from WP-0402's on purpose, and the difference is about
*where the win is*:

* On **CPU fp64** this module is a correctness instrument.  ``torch.func.jvp``
  over one-hot seeds gives a Jacobian that is independent of both the analytic
  peak chain and jax's jacfwd, so it is a third opinion in WP-0404's agreement
  matrix — that is what proves the torch implementation of the op set computes
  the same derivatives.
* On **Apple MPS** it is an accelerator.  The analytic columns are already exact
  and cheap, so what a GPU can add is forward throughput; and since no Apple GPU
  supports fp64 in any framework (docs/DESIGN.md, locked decisions), the device
  necessarily computes the whole peak chain in **fp32**.  That makes this the
  first *real-hardware* measurement of WP-0403's fp32-Jacobian-column policy:
  the CPU gate there round-trips fp64→fp32→fp64 and so captures fp32
  representation loss only, while an MPS pass accumulates error inside the
  forward evaluation as well.

Either way the host boundary is unchanged (architecture invariant 2): the
produced Jacobian is a plain fp64 numpy array in
``optimize.least_squares._make_jacobian``'s exact row/column layout, and the
residual used for cost/statistics plus the TRF solve stay numpy fp64.
``_jacobian_for`` applies WP-0403's ``cast_columns`` at the exit, so nothing
here needs a second precision hook.

Design notes shared with the jax backend, restated because they bind:

* **Frozen state closed over as constants.**  The residual closure reads the
  compiled model's numpy buffers (windows, design matrices, restraint rows, the
  Le Bail intensity snapshot) directly; only θ is traced.  The active backend is
  flipped to torch *only inside* the Jacobian call, so ``compile_model`` and the
  numpy residual never see a tensor — WP-0401 gotcha (1), which for a device
  backend would otherwise put non-fp64 arrays into frozen state.
* **Dense-C decode.**  ``ParameterTable`` promises p = C·θ_phys + d is a
  constant affine map during a solve; C is materialised dense here and the
  softplus/exp/logit transforms become elementwise torch ops, so ``decode`` is
  exact under autodiff.
"""

from __future__ import annotations

import numpy as np

from .api import get_backend, resolve_backend, set_backend
from .traced import make_traced_decode as _make_traced_decode
from .traced import make_traced_residual as _make_traced_residual

#: parameter-axis chunk for the vmapped one-hot tangent seeds (the jax backend's
#: DEFAULT_CHUNK, same reasoning: peak memory ≈ chunk × n_rows × 8 B per block)
DEFAULT_CHUNK = 32


#: the traced twins are shared with jax — see ``backend/traced.py`` for why the
#: bodies do not live here, and ``model/rows.py`` for the row layout they build
make_traced_decode = _make_traced_decode
make_traced_residual = _make_traced_residual


def make_torch_jacobian(model, table, *, chunk_size: int = DEFAULT_CHUNK,
                        device: str = "cpu"):
    """A drop-in replacement for ``_make_jacobian``'s callable, via ``jvp``.

    Chunks over the *parameter* axis: ``torch.func.vmap`` over blocks of
    ``chunk_size`` one-hot tangent seeds through ``torch.func.jvp``, the trailing
    block zero-padded to keep one shape (and hence one set of traced kernels).

    **No ``torch.compile``, and this is measured rather than assumed** (the first
    version of this docstring asserted it): on CPU the compiled residual runs
    13.5 ms against 5.4 ms eager — 2.5× *slower* — after a 38 s one-off compile,
    and on MPS it fails outright, dynamo hitting its recompile limit because
    ``i0, i1 = cp.win[il, k]`` and the ``arange(i0, i1)`` in ``window_add``
    specialise on each window's literal bounds, so it attempts one graph per
    reflection.  The per-reflection python loop defeats graph capture for the
    same reason it defeats the GPU; see ``examples/bench_torch_mps.py``.

    ``device="mps"`` runs the forward and the columns in fp32 on the Apple GPU;
    the returned array is fp64 on host either way.
    """
    xp = resolve_backend("torch" if device == "cpu" else f"torch-{device}")
    torch = xp._torch
    residual = make_traced_residual(model, table, xp)

    def jvp_block(theta, seeds):
        return torch.func.vmap(
            lambda s: torch.func.jvp(residual, (theta,), (s,))[1])(seeds)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        theta = np.asarray(theta, dtype=np.float64)
        n = theta.shape[0]
        prev = get_backend()
        set_backend(xp)
        try:
            t = xp.asarray(theta, dtype=np.float64)
            eye = np.eye(n, dtype=np.float64)
            blocks = []
            for a in range(0, n, chunk_size):
                seeds = eye[a:a + chunk_size]
                if seeds.shape[0] < chunk_size:
                    seeds = np.concatenate(
                        [seeds, np.zeros((chunk_size - seeds.shape[0], n))])
                block = jvp_block(t, xp.asarray(seeds, dtype=np.float64))
                # .cpu() here, fp64 widening at the linalg64 boundary: this is a
                # device→host transfer of one seed block, not a precision policy
                blocks.append(np.asarray(block.detach().cpu(), dtype=np.float64))
            J = np.concatenate(blocks, axis=0)[:n]
        finally:
            set_backend(prev)
        return np.ascontiguousarray(J.T)

    return jacobian
