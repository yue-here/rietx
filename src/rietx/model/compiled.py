"""Fused, threaded twins of the batched numpy planes (WP-1115, WP-1940).

This is an **accelerator of the numpy path, not a fourth backend**.  jax and
torch keep the traced twin (``backend/traced.py``); what lives here loads five
compiled kernels that compute exactly what ``model/forward.py`` computes with
numpy, in one pass over the grid instead of a dozen, and on more than one core.
The kernels are Rust, shipped as the ``rietx-kernels`` wheel and built from
``kernels/`` in this repository; numba compiled them until WP-1940.  Nothing
above this module may branch on whether they ran.

Why a compiled tier at all
--------------------------
WP-1112 and WP-1120 removed the two costs a numpy-level loop is usually blamed
for: per-call dispatch (the surviving kernel calls are 200-400 µs on ~10⁵
element planes) and ragged axes (``BatchLayout`` buckets by node count, so only
the window axis pads, at an evaluation-weighted 1.11×).  What they could not
remove is **fusion** and **threading**.  ``pseudo_voigt`` materialises about a
dozen full-size temporaries per call and ``pseudo_voigt_derivs`` more, each one
a write and a read of a (rows, nodes, window) plane that numpy cannot keep in
registers; and the GIL denies a numpy-level python loop any core but one.
Measured on the WP-1111 trigger case: 2.1-2.4× on the forward, 3.2-3.4× serial
and ~12× threaded on the derivative bases, 6.9-7.1× on the column scatter.

The three rules this module is held to
--------------------------------------
1. **The fallback is not optional.**  Every entry point declines rather than
   raising — the wheel missing or of another interface, the tier switched off,
   a ``shape="voigt"`` model, an arity it was not written for — and the caller
   runs the numpy expression it already had.  ``rietx-kernels`` is a hard
   dependency with no platform markers, and the crate publishes no sdist, so
   pip fails loudly on a platform with no wheel.  The import stays soft all
   the same, for ``--no-deps``, a distro package or an interface mismatch.
   Such an install runs the numpy path, warns once a process and says why in
   ``capabilities()`` (:func:`unavailable`).  Before WP-1940 it ran numpy in
   silence, which was WP-1521's failure in a new place.
   :data:`~rietx._about.COMPILED_ENV` remains the runtime switch: it needs no
   reinstall, and it is what keeps the numpy path exercised on the default
   install.
2. **Each kernel declares which spelling of Ω it reproduces.**  ``pseudo_voigt``
   (the forward) and ``_components`` (the derivative bases) are 1-2 ulp apart on
   purpose, and the difference is a single association: the forward computes
   ``-4ln2 · (x/Γ)²`` while the bases compute ``((-4ln2)·u)·u``.  Borrowing one
   for the other would move every converged fit in its last digits (WP-1120), so
   :data:`SPELL_FORWARD` and :data:`SPELL_BASIS` are a kernel argument and not an
   implementation detail.
3. **The equivalence bar is stated per kernel, and tested.**  The column scatter
   is **bit-identical** — multiplies and adds in the order ``np.bincount``
   performs them, with no library function in it, so the bar is the bit and
   ``tests/test_compiled_kernels.py`` asserts it.  The profile kernels call
   ``exp``, and **whose ``exp`` decides the last bit**: Rust's ``f64::exp``
   calls the platform C library's, as numba did, and numpy uses its own
   vectorised routine.  Measured, they agree bit for bit on darwin/arm64
   against numpy 2.5.2 and miss by ~3e-17 relative on Linux — so the contract
   is the rounding bar (≤ 1e-15, WP-1112's bar for FCJ rows) and the bit is
   asserted only where it was measured.  The wheel matched numba bit for bit
   on all five platforms it ships for (WP-1940), so these bars are the ones
   numba was held to.  The numpy builder stays the oracle for bit-identity
   against the per-reflection loop (``tests/test_batched_forward.py``), which
   is why it has to remain a live, exercised path and not merely dead fallback
   code — and why every test in that file declares the numpy path rather than
   inheriting the default.

Loading
-------
Importing the wheel *is* the build, so :func:`available` says whether the
import succeeded.  numba needed two answers there, whether the compiler
imports and whether the kernels then built (WP-1521), and a background compile
to hide its warm-up.  Both are gone.  The wheel reports its interface number,
and a load checks it against :data:`KERNEL_ABI`.  The ``pyproject`` pin
``rietx-kernels>=N,<N+1`` with N = :data:`KERNEL_ABI` makes pip refuse a
mismatch first, so the check here catches an install that bypassed the
resolver.  A wheel lacking one of :data:`KERNEL_NAMES` declines the same way.
A decline warns once a process, from the first :func:`enabled`, unless
:data:`~rietx._about.COMPILED_ENV` chose the numpy path.

Threading
---------
Every kernel is serial over a row range and releases the GIL itself (PyO3's
``Python::detach``), and the parallelism is a shared ``ThreadPoolExecutor``
over disjoint row ranges.  numba's ``prange`` was measured slower than this
pool, and refused to cache besides (WP-1115).  The pool is shared because
building one per call costs more than half the win (6.0 ms against 2.8 ms,
measured).

**A call engages the pool on its estimated work, never on its row count**
(:func:`_splits`, WP-1940).  An FCJ row carries 8-40 quadrature nodes across
its window and costs 3-10 µs; a symmetric row costs a fraction of one.  So
the 512-row floor this replaced was wrong both ways: the pool never ran in the
trigger fit, whose largest FCJ call had 494 rows, and it split symmetric calls
too small to pay.  Splitting lost under 80 µs of serial work and won over it
on every kernel measured, and the trigger fit's large FCJ calls ran 2.6-4.3×
faster at 8 workers on darwin/arm64.
Whether a call splits cannot change its output, so the threshold is a speed
setting and never a numerical one.

The scatter is the exception and stays single-threaded: its rows write into
overlapping windows, so splitting it by rows is a data race, and the order the
additions arrive in is the whole of its bit-identity claim.
"""

from __future__ import annotations

import os
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .._about import COMPILED_ENV, COMPILED_THREADS_ENV

#: The kernel interface this rietx calls.  It is the ``rietx-kernels`` wheel's
#: major version and the N of ``pyproject``'s ``rietx-kernels>=N,<N+1`` pin, so
#: a new kernel is a minor release of the wheel and a changed signature a major
#: one (``docs/RELEASING.md`` § The kernel wheel).  A wheel reporting another
#: number is declined.
KERNEL_ABI = 1

#: The kernels the wheel must export, under the names ``_KERNELS`` keys them
#: by.  A wheel lacking one is declined like a wrong :data:`KERNEL_ABI`.
KERNEL_NAMES = ("accum", "omega_sym", "omega_fcj", "bases_sym", "bases_fcj")

#: Ω spelled as :func:`~rietx.model.profiles.pseudovoigt.pseudo_voigt` — the
#: forward model's own arithmetic.
SPELL_FORWARD = 0
#: Ω spelled as ``pseudovoigt._components`` — the derivative bases' arithmetic,
#: which is deliberately not the forward's.
SPELL_BASIS = 1

#: The scatter takes at most this many (coefficient, plane) terms per part;
#: ``_peak_chain_column`` builds four (intensity, position, width, mixing) and
#: every other column builds one.  A caller with more is declined, not
#: mis-served.
MAX_TERMS = 4

#: Serial nanoseconds per element of each kernel's work, an element being one
#: window point of one row for one quadrature node (a symmetric row has one).
#: Measured on darwin/arm64 inside the trigger, nac and cpd-1a fits (WP-1940);
#: the bases carry three to five partials beside Ω, hence ~2.4× the forward.
_NS_PER_ELEMENT = {"omega_sym": 1.8, "omega_fcj": 2.7,
                   "bases_sym": 5.5, "bases_fcj": 6.5}

#: A call splits across the pool once its estimated serial time reaches this.
#: Splitting lost under 80 µs and won over it on every kernel (the pool's
#: dispatch is ~30 µs a call), so this sits just above the crossover.
_THREAD_MIN_NS = 100_000.0

_EMPTY_1D = np.zeros(0)
_EMPTY_2D = np.zeros((0, 0))

_LOCK = threading.Lock()
_POOL_LOCK = threading.Lock()
_KERNELS: dict | None = None
#: why the load was declined, once one has been tried; ``None`` before that
#: and after a load that succeeded
_UNAVAILABLE: str | None = None
_ENABLED: bool | None = None
_WARNED = False
_POOL: ThreadPoolExecutor | None = None
#: worker count the pool was actually built with — read once, from the
#: environment, and the number ``_spread`` splits by thereafter
_POOL_WORKERS = 0


def _off_by_env() -> bool:
    """Is the tier switched off in the environment?"""
    return os.environ.get(COMPILED_ENV, "").strip().lower() in {
        "0", "off", "no", "false"}


def n_threads() -> int:
    """Worker threads the row-parallel kernels split across.

    Capped at 8 because the measured ladder is flat past it, and settable so a
    caller that is already parallel one rank up (a test suite under ``xdist``, a
    series fanned out across processes) can decline the second layer.
    """
    raw = os.environ.get(COMPILED_THREADS_ENV, "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return max(1, min(8, os.cpu_count() or 1))


def _load() -> tuple[dict | None, str | None]:
    """Import the wheel and check it: the kernels, or why they were declined.

    Each reason is one clause naming what was found, so it reads both alone
    (:func:`unavailable`) and inside the warning.
    """
    try:
        import rietx_kernels as wheel
    except Exception as exc:
        return None, (f"importing rietx_kernels raised {type(exc).__name__}"
                      f" ({exc})")
    version = getattr(wheel, "__version__", "of unknown version")
    abi = getattr(wheel, "KERNEL_ABI", None)
    if abi != KERNEL_ABI:
        return None, (f"rietx_kernels {version} has kernel interface {abi},"
                      f" and this rietx calls interface {KERNEL_ABI}")
    missing = [n for n in KERNEL_NAMES if not callable(getattr(wheel, n, None))]
    if missing:
        return None, (f"rietx_kernels {version} lacks the kernel"
                      f"{'s' if len(missing) > 1 else ''} {', '.join(missing)}")
    return {n: getattr(wheel, n) for n in KERNEL_NAMES}, None


def _kernels() -> dict | None:
    """The kernels, loaded on first use; ``None`` if the load was declined.

    Behind :data:`_LOCK` because several threads may ask at once, and one path
    per process is the rule: which path an evaluation took must never depend on
    which thread asked first.  A declined load is never retried.
    """
    global _KERNELS, _UNAVAILABLE
    if _KERNELS is not None:
        return _KERNELS
    if _UNAVAILABLE is not None:
        return None
    with _LOCK:
        if _KERNELS is None and _UNAVAILABLE is None:
            _KERNELS, _UNAVAILABLE = _load()
    return _KERNELS


def available() -> bool:
    """Did the compiled kernels load here?

    Does **not** say whether they are switched on (:func:`enabled`).  Importing
    the wheel is the whole build, so the first call costs an import and every
    later one a flag test.
    """
    return _kernels() is not None


def unavailable() -> str | None:
    """Why the compiled kernels did not load here; ``None`` when they did.

    ``capabilities()`` carries it as ``compiled_kernels_unavailable``, so a
    client asking why a build is slow gets the reason and not only the flag.
    """
    _kernels()
    return _UNAVAILABLE


def _warn_unavailable() -> None:
    """Warn, once a process, that the tier was wanted and did not load."""
    global _WARNED
    with _LOCK:
        if _WARNED:
            return
        _WARNED = True
    pin = f"rietx-kernels>={KERNEL_ABI},<{KERNEL_ABI + 1}"
    warnings.warn(
        f"rietx's compiled kernels did not load, because {_UNAVAILABLE}. Fits"
        f" run the numpy path, which is slower. Install the kernels with"
        f' pip install "{pin}", or set {COMPILED_ENV}=0 to choose the numpy'
        f" path and silence this warning.",
        RuntimeWarning, stacklevel=3)


def enabled() -> bool:
    """Is the compiled path what the next residual will take?

    Read once and remembered, because the answer is asked on the hot path — the
    Jacobian calls into the scatter thousands of times per iteration — and an
    ``os.environ`` lookup per call is not free at that rate.  Use
    :func:`set_enabled` to change it inside a process.

    The first evaluation is where a declined load warns, because the switch was
    on and the caller expected the tier.  Under
    :data:`~rietx._about.COMPILED_ENV` ``=0`` the numpy path was chosen, and
    nothing warns.
    """
    global _ENABLED
    if _ENABLED is None:
        if _off_by_env():
            _ENABLED = False
        else:
            _ENABLED = available()
            if not _ENABLED:
                _warn_unavailable()
    return _ENABLED


def set_enabled(flag: bool | None) -> bool | None:
    """Force the tier on or off for this process; ``None`` re-reads the
    environment.  Returns the previous setting, so a caller can restore it.

    This is the seam the suite runs the numpy path through — the fallback is
    only real if something exercises it — and the escape hatch for a caller who
    has hit a difference and wants to say which side it is on.  It never warns.
    Forcing the tier on where the wheel did not load leaves every entry point
    declining, as before the call.
    """
    global _ENABLED
    was, _ENABLED = _ENABLED, flag
    return was


def _pool() -> ThreadPoolExecutor:
    """The shared pool: one per process, built on first use, never shut down.

    Its threads are idle between residuals, and rebuilding it per call was
    measured to cost more than half the threading win.
    """
    global _POOL, _POOL_WORKERS
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL_WORKERS = n_threads()
                _POOL = ThreadPoolExecutor(
                    max_workers=_POOL_WORKERS,
                    thread_name_prefix="rietx-kernel")
    return _POOL


def _splits(kernel: str, rows: np.ndarray, width: np.ndarray, n_nodes: int,
            w_max: int) -> bool:
    """Is one call's estimated serial time enough to pay for the pool?

    The estimate is the call's elements (each row's window width, times its
    nodes) at :data:`_NS_PER_ELEMENT`.  It predicts a call's inline time to a
    log correlation of 0.999 on trigger's FCJ calls, where the row count alone
    reaches 0.98, because rows differ in their node count (8-40) and window
    width.  A row floor of 512 was what this replaced: no FCJ
    call in trigger reached it, so the pool never ran there, while a 512-row
    symmetric call over a narrow window is ~30 µs of work that splitting slows
    to 0.2-0.5×.

    The padded width bounds every row's from above, so a call it rules out
    costs nothing to rule out.  Only a call that might split pays for the sum.
    Which way this goes cannot change a bit of the output: rows are disjoint
    and each is computed whole inside one chunk.
    """
    per = _NS_PER_ELEMENT[kernel] * n_nodes
    if len(rows) * w_max * per < _THREAD_MIN_NS:
        return False
    return float(width[rows].sum()) * per >= _THREAD_MIN_NS


def _spread(fn, n_rows: int, split: bool) -> None:
    """Run ``fn(lo, hi)`` over ``n_rows`` rows, split across the pool when
    ``split`` (:func:`_splits`) says the call can pay for it.

    Row ranges are disjoint in the output planes, so no lock is needed; the
    kernels release the GIL for the duration of the call, which is what makes a
    python-level pool a real parallel loop here.

    The split reads the pool's own worker count rather than :func:`n_threads`,
    for two reasons: this runs thousands of times in a fit and an
    ``os.environ`` lookup per call is not free at that rate, and a split that
    disagreed with the pool it submits to would queue chunks behind each other
    for no reason.  The environment is therefore read once, when the pool is
    built.
    """
    if not split:
        fn(0, n_rows)
        return
    pool = _pool()
    if _POOL_WORKERS <= 1:
        fn(0, n_rows)
        return
    per = -(-n_rows // _POOL_WORKERS)
    futures = [pool.submit(fn, lo, min(n_rows, lo + per))
               for lo in range(0, n_rows, per)]
    for f in futures:
        f.result()


def _c(a: np.ndarray, dtype=np.float64) -> np.ndarray:
    """C-contiguous array of the declared dtype, free when it already is one.

    The wheel refuses any other dtype and any plane that is not C-contiguous,
    so every input passes through here on its way in.
    """
    return np.ascontiguousarray(a, dtype=dtype)


# --- entry points ---------------------------------------------------------
#
# Each declines (``None``/``False``) rather than raising, and every caller must
# have the numpy expression it already had to fall back to.


def accumulate(n_points: int, parts) -> np.ndarray | None:
    """Bit-identical fused twin of :func:`~rietx.model.forward.accumulate_planes`.

    ``np.bincount`` adds its input sequentially, so for one output point the
    additions from one part arrive in (row, term) order; the kernel walks that
    same sequence with the same two operations per contribution and no library
    call, which makes the equality exact rather than close.  The pad tail is
    skipped rather than added: the planes arrive pad-zeroed, so those
    contributions are ±0.0 and dropping them is bitwise neutral.

    Declines a part carrying more than :data:`MAX_TERMS` terms.
    """
    k = _kernels()
    if k is None:
        return None
    live = [(lay, terms) for lay, terms in parts if terms and len(lay.i0)]
    if any(len(terms) > MAX_TERMS for _lay, terms in live):
        return None
    y = np.zeros(n_points)
    for lay, terms in live:
        coefs = [_c(c) for c, _p in terms]
        planes = [_c(p) for _c0, p in terms]
        while len(coefs) < MAX_TERMS:
            coefs.append(_EMPTY_1D)
            planes.append(_EMPTY_2D)
        k["accum"](y, _c(lay.i0, np.int64), _c(lay.i1, np.int64),
                   coefs[0], planes[0], coefs[1], planes[1],
                   coefs[2], planes[2], coefs[3], planes[3], len(terms))
    return y


def omega_symmetric(out: np.ndarray, x: np.ndarray, rows: np.ndarray,
                    pos: np.ndarray, w1: np.ndarray, w2: np.ndarray,
                    width: np.ndarray, spell: int) -> bool:
    """Fill ``out[rows]`` with Ω on the symmetric rows.  ``False`` = declined."""
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    width = _c(width, np.int64)
    args = (out, _c(x), rows, _c(pos), _c(w1), _c(w2), width, spell)
    _spread(lambda lo, hi: k["omega_sym"](*args, lo, hi), len(rows),
            _splits("omega_sym", rows, width, 1, x.shape[1]))
    return True


def omega_fcj(out: np.ndarray, x: np.ndarray, rows: np.ndarray,
              w1: np.ndarray, w2: np.ndarray, width: np.ndarray,
              phi: np.ndarray, om: np.ndarray, spell: int) -> bool:
    """Fill ``out[rows]`` with the node-weighted Ω of one FCJ bucket.

    The node sum runs innermost, so the (rows, nodes, window) transient the
    numpy path materialises never exists — which is the whole of the win here,
    and also why this agrees with ``_node_mix``'s matmul to rounding rather than
    to the bit.
    """
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    width = _c(width, np.int64)
    args = (out, _c(x), rows, _c(w1), _c(w2), width, _c(phi), _c(om), spell)
    _spread(lambda lo, hi: k["omega_fcj"](*args, lo, hi), len(rows),
            _splits("omega_fcj", rows, width, phi.shape[1], x.shape[1]))
    return True


def bases_symmetric(omega: np.ndarray, d_pos: np.ndarray, d_gamma: np.ndarray,
                    d_eta: np.ndarray, x: np.ndarray, rows: np.ndarray,
                    pos: np.ndarray, w1: np.ndarray, w2: np.ndarray,
                    width: np.ndarray) -> bool:
    """Ω and its three partials on the symmetric rows, in one pass."""
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    width = _c(width, np.int64)
    args = (omega, d_pos, d_gamma, d_eta, _c(x), rows, _c(pos), _c(w1),
            _c(w2), width)
    _spread(lambda lo, hi: k["bases_sym"](*args, lo, hi), len(rows),
            _splits("bases_sym", rows, width, 1, x.shape[1]))
    return True


def bases_fcj(omega: np.ndarray, d_pos: np.ndarray, d_gamma: np.ndarray,
              d_eta: np.ndarray, d_sl: np.ndarray | None,
              d_hl: np.ndarray | None, x: np.ndarray, rows: np.ndarray,
              w1: np.ndarray, w2: np.ndarray, width: np.ndarray,
              phi: np.ndarray, om: np.ndarray, dphi: np.ndarray,
              dom: np.ndarray, ax: tuple | None) -> bool:
    """Ω and every partial for one FCJ bucket, in one pass over the nodes.

    ``dphi``/``dom`` are the node-FD position derivatives the numpy path builds
    from a shifted node generation; ``ax`` carries the same pair for S/L and
    H/L, or ``None`` when the axial columns are not being built.  All of them
    are (rows, nodes) — cheap beside the (rows, nodes, window) planes this
    avoids — and are differenced in numpy before the call, so the kernel sees
    exactly the numbers the numpy path multiplies.
    """
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    has_ax = ax is not None and d_sl is not None and d_hl is not None
    if has_ax:
        dphi_sl, dom_sl, dphi_hl, dom_hl = (_c(a) for a in ax)
        sl_out, hl_out = d_sl, d_hl
    else:
        dphi_sl = dom_sl = dphi_hl = dom_hl = _EMPTY_2D
        sl_out = hl_out = _EMPTY_2D
    width = _c(width, np.int64)
    args = (omega, d_pos, d_gamma, d_eta, sl_out, hl_out, _c(x), rows,
            _c(w1), _c(w2), width, _c(phi), _c(om), _c(dphi),
            _c(dom), dphi_sl, dom_sl, dphi_hl, dom_hl, has_ax)
    _spread(lambda lo, hi: k["bases_fcj"](*args, lo, hi), len(rows),
            _splits("bases_fcj", rows, width, phi.shape[1], x.shape[1]))
    return True
