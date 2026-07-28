"""Backend op shim (WP-0401): ``xp = get_backend()`` in the hot path.

WP-0402 adds the jax backend: ``resolve_backend("jax")`` / ``set_backend("jax")``
import jax lazily, and ``jax_backend.make_jax_jacobian`` builds the chunked
jacfwd Jacobian callable (imported lazily by the solver, never here).

WP-0403 adds ``linalg64``: the fp64 host boundary every backend's Jacobian
crosses, and the :class:`MixedPrecisionPolicy` that decides whether columns
(and *only* columns) may be computed below fp64.

WP-0408 adds the torch backend under two names — ``"torch"`` (CPU fp64, an
independent row of the cross-backend agreement matrix) and ``"torch-mps"``
(Apple GPU, necessarily fp32) — with ``torch_backend.make_torch_jacobian``
building the chunked ``torch.func.jvp`` Jacobian.
"""

from .api import (
    Backend,
    JaxBackend,
    NumpyBackend,
    TorchBackend,
    backend_dtype_note,
    get_backend,
    resolve_backend,
    set_backend,
)
from .linalg64 import (
    FP32_JACOBIAN,
    FP64,
    MixedPrecisionPolicy,
    get_precision_policy,
    precision_policy,
    require_fp64,
    set_precision_policy,
    to_host_fp64,
)

__all__ = ["Backend", "JaxBackend", "NumpyBackend", "TorchBackend",
           "backend_dtype_note", "get_backend",
           "resolve_backend", "set_backend",
           "FP32_JACOBIAN", "FP64", "MixedPrecisionPolicy",
           "get_precision_policy", "precision_policy", "require_fp64",
           "set_precision_policy", "to_host_fp64"]
