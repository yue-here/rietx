"""Backend op shim — the small array-op vocabulary the hot path speaks.

The forward model, structure factor, lattice and profile code call ``xp.*``
(``xp = get_backend()``) instead of bare ``np.*``, so that an autodiff backend
(jax, WP-0402; torch, WP-0408) can be swapped in without per-call branching.
Design record: docs/DESIGN.md ("locked decisions" — backend namespace object,
one autodiff backend at a time; "risks" — backend drift is contained by keeping
this vocabulary minimal and cross-testing every backend against numpy).

Discipline
----------
* **Every op added here is a per-backend maintenance liability.**  Add one only
  when hot-path code genuinely needs it; compile-time code (window edges,
  quadrature node placement, design matrices, the TRF driver, statistics)
  stays plain numpy and must not acquire ``xp`` calls.
* The numpy backend's attributes *are* the numpy functions — zero overhead, so
  the numpy path cannot regress.  Hot-loop code binds ``xp = get_backend()``
  once per compiled-model call, never per op.
* Python operators (``+ * / @ **``) and array methods (``.sum()``, ``.real``)
  are backend-polymorphic **when the traced value is the left operand**, and
  are NOT part of the vocabulary.  The qualifier is torch's (WP-0408):
  ``ndarray * tensor``, ``ndarray - tensor`` and ``ndarray + tensor`` all raise
  ``TypeError`` — numpy's ufunc machinery and torch's reflected operators both
  decline — while ``ndarray / tensor`` happens to work, which makes the failure
  look arbitrary.  jax has no such asymmetry.  So the rule for hot-path code is:
  **a frozen numpy constant may not sit on the left of an operator against a
  θ-derived value**.  Where one did, it now goes through ``xp.matmul`` (frozen
  design matrices, symmetry rotations) or is lifted with ``xp.asarray`` (the
  quadrature nodes, the fit grid, form-factor coefficients) — both no-ops on
  numpy, where ``asarray`` of an fp64 array returns that same array.
* ``einsum`` must support the five signatures the model uses:
  ``"nk,mkc->mnc"`` (transposed-rotation indices), ``"mnc,cd,mnd->mn"``
  (anisotropic Debye-Waller), ``"ni,ij,nj->n"`` (d-spacings),
  ``"mi,ij,mj->m"`` (March-Dollase angles), ``"i,in->n"`` (form factors).
* Complex is first-class: ``exp`` must accept complex128, and ``conj``/
  ``real``/``imag`` exist for the structure factor.  complex128 on host; a
  reduced-precision policy is WP-0403's business, not this module's.
* No ``scipy.special``: the hot path has none today; the WP-0405 Faddeeva
  profile is built *on* this op set, not into it.

Scatter primitives
------------------
``window_add(y, i0, i1, vals)`` is THE scatter op.  The residual only ever
accumulates onto *contiguous frozen windows* whose bounds ``(i0, i1)`` are
python ints fixed at stage compile — legal static slice bounds under tracing.
Deliberately NOT a general index-array scatter: data-dependent indices are
exactly what the frozen-per-stage discreteness invariant exists to forbid.
The signature is functional — callers must thread the return value
(``y = xp.window_add(y, i0, i1, vals)``); the numpy implementation mutates
``y`` in place and returns it, immutable-array backends return a new array.

``segment_sum(vals, seg_ids, n)`` sums ``vals`` into ``n`` buckets keyed by the
frozen integer map ``seg_ids`` (the March-Dollase orbit average).  numpy:
``bincount(weights=...)``; jax: ``segment_sum``; torch: ``index_add``.
"""

from __future__ import annotations

import functools
from contextlib import nullcontext
from typing import Any, Protocol

import numpy as np
from scipy.special import expit


class Backend(Protocol):
    """Structural type of a backend namespace (attributes are array ops)."""

    name: str
    pi: float
    linalg: Any  # .inv and .det on stacks of small (3×3) matrices

    # elementwise (exp complex-capable)
    exp: Any
    sqrt: Any
    log: Any
    sin: Any
    cos: Any
    tan: Any
    arcsin: Any
    arccos: Any
    radians: Any
    degrees: Any
    abs: Any
    sign: Any
    power: Any
    clip: Any
    maximum: Any
    minimum: Any
    where: Any
    isfinite: Any
    # parameter transforms, in their overflow-safe forms — the traced decode
    # (backend/traced.py) is written once against these, so every backend
    # reproduces ``params.transforms.to_physical`` rather than approximating it
    logaddexp: Any
    sigmoid: Any
    # reductions / linear algebra
    einsum: Any
    matmul: Any
    sum: Any
    cumsum: Any
    diff: Any
    # construction
    asarray: Any
    zeros: Any
    zeros_like: Any
    full_like: Any
    concatenate: Any
    stack: Any
    # complex support
    conj: Any
    real: Any
    imag: Any

    def window_add(self, y: Any, i0: int, i1: int, vals: Any) -> Any:
        """Return ``y`` with ``vals`` added on the static window ``[i0, i1)``."""
        ...

    def segment_sum(self, vals: Any, seg_ids: Any, n: int) -> Any:
        """Sum ``vals`` into ``n`` buckets keyed by the frozen ``seg_ids``."""
        ...

    def scalarize(self, x: Any) -> Any:
        """``x`` made safe to combine with a python literal.

        The identity everywhere except torch-MPS, where 0-d results need the
        subclass guard (:func:`scalar_tensor_class`).  Backend-agnostic code
        that pulls a 0-d value out by *indexing* — which no op has seen — calls
        this rather than special-casing the device.
        """
        ...

    def full_precision(self) -> Any:
        """Context manager every trace/evaluate site must run inside.

        A no-op on numpy and torch, whose dtypes are properties of the arrays
        themselves — but **not** optional on jax, whose fp64 is a *scoped* flag:
        outside ``jax.enable_x64`` every constant materialises as float32 and
        the whole computation quietly halves its precision.  Exposing it as a
        backend method is what keeps that knowledge with the backend instead of
        in each caller (which is how it was missed once already).
        """
        ...


class NumpyBackend:
    """The reference backend: attributes *are* numpy functions (fp64 host)."""

    name = "numpy"
    pi = np.pi
    linalg = np.linalg

    exp = staticmethod(np.exp)
    sqrt = staticmethod(np.sqrt)
    log = staticmethod(np.log)
    sin = staticmethod(np.sin)
    cos = staticmethod(np.cos)
    tan = staticmethod(np.tan)
    arcsin = staticmethod(np.arcsin)
    arccos = staticmethod(np.arccos)
    radians = staticmethod(np.radians)
    degrees = staticmethod(np.degrees)
    abs = staticmethod(np.abs)
    sign = staticmethod(np.sign)
    power = staticmethod(np.power)
    clip = staticmethod(np.clip)
    maximum = staticmethod(np.maximum)
    minimum = staticmethod(np.minimum)
    where = staticmethod(np.where)
    isfinite = staticmethod(np.isfinite)

    logaddexp = staticmethod(np.logaddexp)
    sigmoid = staticmethod(expit)   # scipy's, i.e. the branch-free safe form

    einsum = staticmethod(np.einsum)
    matmul = staticmethod(np.matmul)
    sum = staticmethod(np.sum)
    cumsum = staticmethod(np.cumsum)
    diff = staticmethod(np.diff)

    asarray = staticmethod(np.asarray)
    zeros = staticmethod(np.zeros)
    zeros_like = staticmethod(np.zeros_like)
    full_like = staticmethod(np.full_like)
    concatenate = staticmethod(np.concatenate)
    stack = staticmethod(np.stack)

    conj = staticmethod(np.conj)
    real = staticmethod(np.real)
    imag = staticmethod(np.imag)

    @staticmethod
    def window_add(y: np.ndarray, i0: int, i1: int, vals: np.ndarray) -> np.ndarray:
        # in-place is safe here: callers own y (freshly created accumulation
        # buffer) and thread the return value per the functional contract
        y[i0:i1] += vals
        return y

    @staticmethod
    def segment_sum(vals: np.ndarray, seg_ids: np.ndarray, n: int) -> np.ndarray:
        return np.bincount(seg_ids, weights=vals, minlength=n)

    @staticmethod
    def scalarize(x: Any) -> Any:
        """The identity — no numpy value needs the MPS 0-d guard."""
        return x

    @staticmethod
    def full_precision():
        """No-op: numpy arrays carry their own dtype."""
        return nullcontext()


#: the shared op vocabulary, bound per backend (kept as one tuple so the two
#: autodiff backends cannot silently drift from the Protocol above)
_OP_NAMES = (
    "exp", "sqrt", "log", "sin", "cos", "tan", "arcsin", "arccos",
    "radians", "degrees", "abs", "sign", "power", "clip",
    "maximum", "minimum", "where", "isfinite", "logaddexp", "sigmoid",
    "einsum", "matmul", "sum", "cumsum", "diff",
    "asarray", "zeros", "zeros_like", "full_like", "concatenate", "stack",
    "conj", "real", "imag",
)


class JaxBackend:
    """jax.numpy-backed namespace (WP-0402) — CPU fp64 via *scoped* x64.

    ``import jax`` happens in ``__init__``, never at module import, so a
    numpy-only process is unaffected (resolve via ``set_backend("jax")`` /
    ``resolve_backend``).  fp64 comes from the ``enable_x64`` scope wrapped
    around the jacfwd/jit call sites in ``backend/jax_backend.py`` — this
    class never touches jax's global x64 flag.
    """

    name = "jax"

    def __init__(self) -> None:
        import jax
        import jax.numpy as jnp

        self._jax = jax
        self.pi = jnp.pi
        self.linalg = jnp.linalg
        # every op is jnp's by name, except the few jax puts elsewhere
        aliases = {"sigmoid": jax.nn.sigmoid}
        for op in _OP_NAMES:
            setattr(self, op, aliases.get(op) or getattr(jnp, op))

    @staticmethod
    def scalarize(x: Any) -> Any:
        """The identity — jax has no 0-d scalar guard to apply."""
        return x

    def full_precision(self):
        """``jax.enable_x64`` — **not** optional (see the Protocol's docstring).

        Top-level since jax 0.11, ``jax.experimental`` before it; this class
        never touches the global flag, only the scope.
        """
        try:
            return self._jax.enable_x64()
        except AttributeError:  # pragma: no cover - depends on installed jax
            from jax.experimental import enable_x64

            return enable_x64()

    def window_add(self, y: Any, i0: int, i1: int, vals: Any) -> Any:
        # functional scatter on the static window; (i0, i1) are frozen python
        # ints, so this is a legal static slice under tracing
        return y.at[i0:i1].add(vals)

    def segment_sum(self, vals: Any, seg_ids: Any, n: int) -> Any:
        return self._jax.ops.segment_sum(vals, seg_ids, num_segments=n)


class _TorchLinalg:
    """``inv``/``det`` on stacks of small matrices, with argument coercion.

    ``det`` on a 3×3 is the cofactor expansion rather than ``torch.linalg.det``.
    Not an optimisation: on MPS, ``linalg.det`` decomposes into
    ``solve_triangular``, whose batching rule then broadcasts the vmap batch
    against the matrix dimension and raises ("The size of tensor a (32) must
    match the size of tensor b (3)") for every seed-block size other than 3.
    ``linalg.inv`` batches correctly on the same device, so it is left alone —
    and the only matrices this vocabulary sees are the 3×3 metric tensors.
    """

    def __init__(self, backend: "TorchBackend") -> None:
        self._b = backend

    def inv(self, a: Any) -> Any:
        return self._b._torch.linalg.inv(self._b._t(a))

    def det(self, a: Any) -> Any:
        m = self._b._t(a)
        if m.shape[-2:] != (3, 3):
            return self._b.scalarize(self._b._torch.linalg.det(m))
        return self._b.scalarize(
            m[..., 0, 0] * (m[..., 1, 1] * m[..., 2, 2] - m[..., 1, 2] * m[..., 2, 1])
            - m[..., 0, 1] * (m[..., 1, 0] * m[..., 2, 2] - m[..., 1, 2] * m[..., 2, 0])
            + m[..., 0, 2] * (m[..., 1, 0] * m[..., 2, 1] - m[..., 1, 1] * m[..., 2, 0]))


@functools.lru_cache(maxsize=1)
def scalar_tensor_class():
    """A 0-d ``Tensor`` subclass that lifts python scalars before arithmetic.

    Workaround for a torch/MPS forward-AD bug, and the reason it is a *type*
    rather than a scatter of edits through the physics code.  On MPS, inside
    ``torch.func.jvp``, a **0-d** dual tensor and a python float cannot be
    combined by any of ``* / + -``::

        >>> jvp(lambda x: (x[0] * 2.0).reshape(1),
        ...     (torch.ones(4, device="mps"),), (torch.eye(4, device="mps")[0],))
        TypeError: unsupported operand type(s) for *: 'Tensor' and 'float'

    ``torch.result_type`` reports float32 for that pair, yet the dispatch tries
    to materialise an fp64 MPS tensor, which the framework does not support.  CPU
    fp32 and fp64 are both unaffected, and a 1-D tensor of any length is
    unaffected — it is 0-d duals specifically.

    Every scalar in this model is 0-d and meets python literals constantly
    (``0.5 * tt``, ``s/R``, ``2.0 * min(s, h)``, ``1j * gamma`` in the Voigt
    argument), so :class:`TorchBackend` guarantees instead that **every value it
    hands out on MPS is of this type**, which lifts the literal to a tensor on
    the operand's own device — promoting to complex when the literal is complex
    and the operand is not, since a real dtype cannot hold ``1j``.

    The wrapper rides on **arrays too**, and that is deliberate even though the
    bug is 0-d-only.  0-d values are not only produced by ops: they also fall out
    of *indexing* an array (``gamma[k]``, one reflection's width) and of array
    methods (``.sum()``), neither of which the backend's op wrappers see.  Shedding
    at the first array result left exactly those two holes — one of which reached
    the true-Voigt profile and only surfaced when WP-0405 and WP-0408 were
    integrated.  Propagating costs a ``__torch_function__`` hop per op on MPS,
    **measured at 1.8×** on the 11-BM NAC forward (199 → 359 ms).  Kept: this
    device is a correctness instrument, already dispatch-bound and ~100× off
    numpy for reasons a python hop does not change
    (``examples/bench_torch_mps.py``), and the alternative was a silently wrong
    Voigt profile.  The CPU fp64 instance — the agreement row — never constructs
    the class at all.
    """
    import torch

    def _lift(other, ref):
        if isinstance(other, bool) or not isinstance(other, int | float | complex):
            return other
        dtype = ref.dtype
        if isinstance(other, complex) and not ref.is_complex():
            # a complex literal against a real operand — ``1j * gamma`` in the
            # Voigt argument (WP-0405).  Lifting it at the operand's own real
            # dtype would refuse to hold it; promote to the complex type of the
            # same width, which is what torch's own promotion would have done.
            dtype = (torch.complex64 if ref.dtype == torch.float32
                     else torch.complex128)
        return torch.as_tensor(other, dtype=dtype, device=ref.device)

    class ScalarTensor(torch.Tensor):
        __doc__ = scalar_tensor_class.__doc__

        @classmethod
        def __torch_function__(cls, func, types, args=(), kwargs=None):
            # run the op as if this were a plain Tensor, then re-wrap: the
            # protection has to survive ``xp.minimum`` and friends *and* the
            # indexing/reduction that turns an array back into a 0-d scalar
            with torch._C.DisableTorchFunctionSubclass():
                out = func(*args, **(kwargs or {}))
            return out.as_subclass(cls) if isinstance(out, torch.Tensor) else out

    for _name in ("mul", "rmul", "truediv", "rtruediv", "add", "radd",
                  "sub", "rsub", "pow", "rpow"):
        def _method(self, other, _op=getattr(torch.Tensor, f"__{_name}__")):
            return _op(self, _lift(other, self))

        setattr(ScalarTensor, f"__{_name}__", _method)
    return ScalarTensor


def _torch_matmul(torch):
    """``matmul`` with the 1-D·1-D case expanded.

    A vector-vector ``matmul`` lowers to ``aten::dot``, which on MPS asserts
    internally ("Placeholder tensor is empty!") when it runs under a functorch
    batching rule — i.e. exactly inside the vmapped one-hot seed batch this
    backend exists to serve.  Every other shape (matrix-vector, vector-matrix,
    matrix-matrix, batched) is fine, so the workaround is confined to the one
    that is not, and expressed as the identity it is: aᵢbᵢ summed.
    """

    def matmul(a, b):
        if a.ndim == 1 and b.ndim == 1:
            return (a * b).sum()
        return torch.matmul(a, b)

    return matmul


#: op → torch function name, for the ops that need only argument coercion
_TORCH_UNARY = {
    "exp": "exp", "sqrt": "sqrt", "log": "log", "sin": "sin", "cos": "cos",
    "tan": "tan", "arcsin": "arcsin", "arccos": "arccos",
    "radians": "deg2rad", "degrees": "rad2deg",
    "abs": "abs", "sign": "sign", "isfinite": "isfinite", "real": "real",
    # torch.sigmoid is the overflow-safe form, matching scipy's expit and
    # jax.nn.sigmoid — not a hand-rolled 1/(1+exp(-x))
    "sigmoid": "sigmoid",
}
#: …and the two-argument ones (torch rejects a bare python scalar for ``other``)
_TORCH_BINARY = {"power": "pow", "maximum": "maximum", "minimum": "minimum",
                 "logaddexp": "logaddexp"}


class TorchBackend:
    """torch namespace (WP-0408) — fp64 on CPU, fp32 on Apple MPS.

    ``import torch`` happens in ``__init__``, never at module import, so a
    numpy-only process is unaffected (resolve via ``set_backend("torch")`` /
    ``resolve_backend``).

    Three things differ from numpy and jax, and all three are settled here rather
    than in the hot path:

    * **torch ops take tensors only** — ``torch.exp(ndarray)`` raises — so every
      op coerces its array arguments.  The coercion is one ``as_tensor`` over an
      already-contiguous buffer, negligible against the kernel it feeds.  The
      complementary half of the problem (a numpy constant meeting a traced value
      through a bare python operator) is *not* solvable here and is handled at
      the call sites; see the module docstring.
    * **A few ops need their numpy semantics restored or a torch quirk routed
      around**: ``imag`` of a real array, ``full_like`` with a traced fill,
      ``conj``'s lazy view, a 1-D·1-D ``matmul``, a 3×3 determinant, and — on
      MPS under forward-AD — 0-d scalars meeting python literals
      (:func:`scalar_tensor_class`).  Each carries its own note below.
    * **No Apple GPU supports fp64 in any framework**
      (docs/DESIGN.md, locked decisions), so an ``mps`` instance is
      fp32/complex64 throughout and a ``cpu`` instance fp64/complex128.  A
      hot-path ``dtype=np.float64`` request is therefore honoured *by kind, not
      by width*: on MPS it lands as fp32, which is the entire point of the
      device.  Nothing else branches on device — dtype is bound once, in this
      constructor, as WP-0401 requires.

    Reduced precision stops at the Jacobian columns either way: they cross
    ``backend/linalg64.py``'s fp64 host boundary before the residual and the
    solve, which stay numpy fp64 (architecture invariant 2).
    """

    name = "torch"

    def __init__(self, device: str = "cpu") -> None:
        import torch

        self._torch = torch
        self.device = torch.device(device)
        if self.device.type == "mps":
            if not torch.backends.mps.is_available():
                raise RuntimeError(
                    'backend "torch-mps" needs an Apple GPU with a working MPS '
                    "build of torch; torch.backends.mps.is_available() is False")
            self.real_dtype, self.complex_dtype = torch.float32, torch.complex64
        else:
            self.real_dtype, self.complex_dtype = torch.float64, torch.complex128
        self.name = f"torch-{self.device.type}" if self.device.type != "cpu" else "torch"
        self.pi = np.pi
        self.linalg = _TorchLinalg(self)
        for op, fn in _TORCH_UNARY.items():
            setattr(self, op, self._unary(getattr(torch, fn)))
        for op, fn in _TORCH_BINARY.items():
            setattr(self, op, self._binary(getattr(torch, fn)))
        self.matmul = self._binary(_torch_matmul(torch))
        # MPS only: guarantee that every 0-d value leaving this backend can be
        # multiplied by a python literal (see scalar_tensor_class).  The CPU fp64
        # instance — the agreement row — carries none of this machinery.
        self._scalar = scalar_tensor_class() if self.device.type == "mps" else None
        if self._scalar is not None:
            for op in _OP_NAMES:
                setattr(self, op, self._guarded(getattr(self, op)))

    # -- coercion ------------------------------------------------------
    def _dtype(self, dtype: Any) -> Any:
        """A numpy dtype mapped to this instance's torch dtype, by *kind*."""
        kind = np.dtype(dtype).kind
        if kind == "c":
            return self.complex_dtype
        if kind == "b":
            return self._torch.bool
        if kind in "iu":
            return self._torch.int64
        return self.real_dtype

    def _t(self, x: Any) -> Any:
        """``x`` as a tensor on this device — the identity on tensors.

        Tensors are returned untouched (never ``.to()``-ed): they are either
        already ours or a functorch dual carrying a tangent, and a dtype cast
        would be both wasteful and, mid-trace, a place to lose one.
        """
        if isinstance(x, self._torch.Tensor):
            return x
        if isinstance(x, np.ndarray):
            return self._torch.as_tensor(x, dtype=self._dtype(x.dtype),
                                         device=self.device)
        if isinstance(x, bool):
            return self._torch.as_tensor(x, dtype=self._torch.bool,
                                         device=self.device)
        if isinstance(x, complex):
            return self._torch.as_tensor(x, dtype=self.complex_dtype, device=self.device)
        if isinstance(x, int | float | np.generic):
            # python/numpy numeric scalars are *values* in this vocabulary
            # (never indices), so they take the real dtype
            return self._torch.as_tensor(float(x), dtype=self.real_dtype,
                                         device=self.device)
        return self._torch.as_tensor(np.asarray(x), device=self.device)

    def _unary(self, fn):
        return lambda x: fn(self._t(x))

    def _binary(self, fn):
        return lambda a, b: fn(self._t(a), self._t(b))

    def scalarize(self, x: Any) -> Any:
        """A result made safe to combine with a python literal (MPS only).

        The identity on every other backend — see :func:`scalar_tensor_class`
        for what this is working around, and why it is not restricted to the
        0-d values that are the ones actually at risk.
        """
        if self._scalar is not None and isinstance(x, self._torch.Tensor):
            return x.as_subclass(self._scalar)
        return x

    def _guarded(self, fn):
        return lambda *a, **kw: self.scalarize(fn(*a, **kw))

    # -- ops needing more than coercion --------------------------------
    def imag(self, x: Any) -> Any:
        """numpy semantics: zeros for a real input (torch's ``imag`` raises)."""
        t = self._t(x)
        return self._torch.imag(t) if t.is_complex() else self._torch.zeros_like(t)

    def conj(self, x: Any) -> Any:
        """The lazy conjugate view, resolved.

        ``torch.conj`` only flips a bit, and the ``mul``/``real`` that follow it
        in the structure factor are conj-aware — but ``resolve_conj`` costs
        nothing on a real tensor and keeps a conj *view* from reaching an op that
        is not.  ``conj_physical`` would be the obvious spelling and is the wrong
        one: it has no vmap batching rule, so under the one-hot seed batch torch
        falls back to a per-sample python loop over the whole structure factor.
        """
        return self._torch.conj(self._t(x)).resolve_conj()

    def clip(self, x: Any, lo: Any, hi: Any) -> Any:
        return self._torch.clamp(self._t(x), self._t(lo), self._t(hi))

    def where(self, cond: Any, a: Any, b: Any) -> Any:
        return self._torch.where(self._t(cond), self._t(a), self._t(b))

    def einsum(self, subscripts: str, *operands: Any) -> Any:
        return self._torch.einsum(subscripts, *(self._t(o) for o in operands))

    def sum(self, x: Any, axis: Any = None) -> Any:
        t = self._t(x)
        return t.sum() if axis is None else t.sum(dim=axis)

    def cumsum(self, x: Any, axis: Any = None) -> Any:
        t = self._t(x)
        return t.reshape(-1).cumsum(0) if axis is None else t.cumsum(axis)

    def diff(self, x: Any, n: int = 1, axis: int = -1) -> Any:
        return self._torch.diff(self._t(x), n=n, dim=axis)

    def asarray(self, x: Any, dtype: Any = None) -> Any:
        t = self._t(x)
        return t if dtype is None else t.to(self._dtype(dtype))

    def zeros(self, shape: Any, dtype: Any = None) -> Any:
        return self._torch.zeros(shape, device=self.device,
                                 dtype=self.real_dtype if dtype is None
                                 else self._dtype(dtype))

    def zeros_like(self, x: Any) -> Any:
        return self._torch.zeros_like(self._t(x))

    def full_like(self, x: Any, fill: Any) -> Any:
        """``torch.full_like`` takes only a python number for ``fill``, but the
        callers pass a θ-derived scalar whose tangent must survive — so this is
        a broadcast multiply, not a fill."""
        t = self._t(x)
        return self._torch.ones_like(t) * self._t(fill)

    def concatenate(self, arrays: Any, axis: int = 0) -> Any:
        return self._torch.cat([self._t(a) for a in arrays], dim=axis)

    def stack(self, arrays: Any, axis: int = 0) -> Any:
        return self._torch.stack([self._t(a) for a in arrays], dim=axis)

    def window_add(self, y: Any, i0: int, i1: int, vals: Any) -> Any:
        # out-of-place index_add on the frozen window: functional, and (unlike a
        # general index scatter) the indices are compile-time constants
        t = self._t(y)
        idx = self._torch.arange(i0, i1, device=t.device)
        return t.index_add(0, idx, self._t(vals).to(t.dtype))

    def segment_sum(self, vals: Any, seg_ids: Any, n: int) -> Any:
        v = self._t(vals)
        seg = self._torch.as_tensor(np.asarray(seg_ids, dtype=np.int64),
                                    device=v.device)
        return self._torch.zeros(n, dtype=v.dtype, device=v.device).index_add(0, seg, v)

    @staticmethod
    def full_precision():
        """No-op: this instance's dtype was fixed at construction (fp64 on CPU,
        fp32 on MPS, which no scope can change — no Apple GPU has fp64)."""
        return nullcontext()


_NUMPY_BACKEND = NumpyBackend()
_JAX_BACKEND: Backend | None = None
_TORCH_BACKENDS: dict[str, Backend] = {}
_BACKEND: Backend = _NUMPY_BACKEND

#: backend name → torch device.  Two names rather than one plus a device flag:
#: MPS *is* fp32 (no Apple GPU has fp64), so "torch-mps at fp64" must not be
#: spellable — the same discipline MixedPrecisionPolicy applies to the residual.
TORCH_DEVICES = {"torch": "cpu", "torch-mps": "mps"}

#: Every backend name ``resolve_backend`` accepts.  This tuple is the registry
#: the conformance suite iterates (``tests/test_backend_conformance.py``), so a
#: backend added here without its test rows fails the suite rather than
#: shipping unvalidated — see that file's meta-test.
BACKEND_NAMES = ("numpy", "jax", *TORCH_DEVICES)

#: name → the optional distribution it needs (absent ⇒ always available), used
#: by tests to ``importorskip`` generically instead of naming packages one by one
BACKEND_REQUIRES = {"jax": "jax", **{n: "torch" for n in TORCH_DEVICES}}

#: Backends kept for *validation and future work*, not for production
#: refinements: torch is an order of magnitude slower than the analytic numpy
#: path and MPS is two, so its value is being an independent opinion in the
#: agreement matrix and a route to the ecosystem (see DESIGN.md, "What the
#: differentiable core unlocks").  Never installed by default.
EXPERIMENTAL_BACKENDS = frozenset(TORCH_DEVICES)

_BACKEND_NAMES = BACKEND_NAMES   # internal alias, kept for existing call sites


def resolve_backend(name: str) -> Backend:
    """A (cached) backend instance by name; jax/torch are imported lazily here."""
    global _JAX_BACKEND
    if name == "numpy":
        return _NUMPY_BACKEND
    if name == "jax":
        if _JAX_BACKEND is None:
            try:
                _JAX_BACKEND = JaxBackend()
            except ImportError as exc:
                raise ImportError(
                    'backend "jax" needs the optional jax dependency: '
                    'install with  uv pip install -e ".[dev,jax]"  '
                    "(or  pip install pxrd-refine[jax])") from exc
        return _JAX_BACKEND
    if name in TORCH_DEVICES:
        if name not in _TORCH_BACKENDS:
            try:
                _TORCH_BACKENDS[name] = TorchBackend(TORCH_DEVICES[name])
            except ImportError as exc:
                raise ImportError(
                    f'backend {name!r} is experimental and needs the optional '
                    'torch dependency: install with  uv pip install -e '
                    '".[dev,torch]"  (or  pip install pxrd-refine[torch]).  It '
                    "is not installed by default and is not the faster path — "
                    "see docs/milestones/v0.4.md") from exc
        return _TORCH_BACKENDS[name]
    raise ValueError(f"unknown backend {name!r}; "
                     f"available: {', '.join(_BACKEND_NAMES)}")


def backend_dtype_note(name: str) -> str:
    """The precision a backend computes at, for ``Provenance.dtype``.

    Everything is fp64 except an Apple-GPU backend, where the Jacobian *columns*
    are fp32 by hardware necessity — the residual used for cost/statistics and
    the solve stay fp64 on host either way (architecture invariant 2), which is
    why this is one string and not a dtype per stage of the computation.
    """
    return ("float64/jacobian:float32" if TORCH_DEVICES.get(name) == "mps"
            else "float64")


def get_backend() -> Backend:
    """The active backend namespace (bind once per compiled-model call)."""
    return _BACKEND


def set_backend(backend: Backend | str) -> None:
    """Install a backend namespace globally (one backend at a time — see
    docs/DESIGN.md).  Accepts a name (``"numpy"``, ``"jax"``, ``"torch"``,
    ``"torch-mps"``; resolved lazily) or an instance.  The solver flips this per
    Jacobian call; user code should not need to call it directly."""
    global _BACKEND
    _BACKEND = resolve_backend(backend) if isinstance(backend, str) else backend
