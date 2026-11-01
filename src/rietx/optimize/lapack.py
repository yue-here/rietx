"""The decompositions a fit makes, with a second LAPACK driver where the first does not converge.

numpy's ``eigh``, ``eigvalsh``, ``svd``, ``pinv``, ``lstsq`` and ``cond`` call LAPACK's
divide-and-conquer drivers (``syevd``, ``gesdd``, ``gelsd``), and so does
SciPy's Trust Region Reflective solver for its step.  Those drivers iterate,
and one can stop without converging on a finite matrix, raising
``LinAlgError`` (Anderson et al. 1999, *LAPACK Users' Guide*, 3rd ed., SIAM,
the SVD and symmetric eigenproblem driver routines).  Each has a QR-iteration
twin computing the same decomposition by another route (``syev``, ``gesvd``,
``gelss``).  The functions here call numpy exactly as a bare call would, so a
decomposition that converges is bit-identical, and repeat a failed one with
the twin.  TenPy's ``svd_robust`` does the same for the SVD, and MATLAB and
Octave call ``gesvd`` by default (SciPy's ``scipy.linalg.svd`` docstring).

Three failures were met.  macOS's system LAPACK (Accelerate) ``gesdd`` did not
converge on a 7279 × 28 TRF step matrix of condition 7.9e10 on CPD brucite,
20 times in 20, while OpenBLAS's ``gesdd`` decomposed the same matrix with
singular values equal to ``gesvd``'s to the last bit (WP-2002, 2026-10-22).
Accelerate's ``gelsd`` did not converge on a 22 003 × 102 strain-screen design
that ``gelss`` solved (WP-2002).  And issue #225 met ``Eigenvalues did not
converge`` out of the covariance's ``eigh`` at a converged fit.

Every decomposition on the fit path goes through here, which
``tests/test_lapack_fallback.py`` holds: ``optimize/``, ``model/``,
``params/``, ``report/``, ``background/``, ``solve/``, ``refine.py``,
``multi.py`` and ``sequential.py``.
Every fallback is counted on the calling thread (:func:`retries`).  A stage
records those its solve and its esds took (``StageResult.n_lapack_fallbacks``);
one taken elsewhere on the fit path (a table build, the scale-B hold, a
report) is counted and recorded nowhere, its answer being the twin's.  A failure of
the twin as well raises as before, where ``_guarded_covariance``'s rule
(#225) still applies.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator

import numpy as np
import scipy.linalg

_local = threading.local()
_install_lock = threading.Lock()


def retries() -> int:
    """Fallbacks taken on this thread since it started, for a caller to difference."""
    return getattr(_local, "n", 0)


def _note(*arrays) -> None:
    """Count a fallback, or re-raise the first driver's error where an input
    is not finite.  numpy reports a NaN or an infinity as non-convergence, and
    SciPy's ``check_finite`` would turn that into a ``ValueError`` that no
    ``except LinAlgError`` (``_guarded_covariance``'s rule, #225) catches."""
    if not all(np.isfinite(x).all() for x in arrays):
        raise
    _local.n = retries() + 1


def eigh(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``np.linalg.eigh(a)``, with ``syev`` where ``syevd`` does not converge."""
    try:
        return np.linalg.eigh(a)
    except np.linalg.LinAlgError:
        a = np.asarray(a)
        _note(a)
        if a.ndim == 2:
            return scipy.linalg.eigh(a, driver="ev")
        flat = a.reshape(-1, *a.shape[-2:])
        parts = [scipy.linalg.eigh(m, driver="ev") for m in flat]
        w = np.stack([p[0] for p in parts]).reshape(a.shape[:-1])
        v = np.stack([p[1] for p in parts]).reshape(a.shape)
        return w, v


def eigvalsh(a: np.ndarray) -> np.ndarray:
    """``np.linalg.eigvalsh(a)``, with ``syev`` where ``syevd`` does not converge."""
    try:
        return np.linalg.eigvalsh(a)
    except np.linalg.LinAlgError:
        a = np.asarray(a)
        _note(a)
        if a.ndim == 2:
            return scipy.linalg.eigh(a, eigvals_only=True, driver="ev")
        flat = a.reshape(-1, *a.shape[-2:])
        return np.stack([scipy.linalg.eigh(m, eigvals_only=True, driver="ev")
                         for m in flat]).reshape(a.shape[:-1])


def svd(a: np.ndarray, full_matrices: bool = True, compute_uv: bool = True):
    """``np.linalg.svd``, with ``gesvd`` where ``gesdd`` does not converge."""
    try:
        return np.linalg.svd(a, full_matrices=full_matrices, compute_uv=compute_uv)
    except np.linalg.LinAlgError:
        _note(np.asarray(a))
        return scipy.linalg.svd(a, full_matrices=full_matrices, compute_uv=compute_uv,
                                lapack_driver="gesvd")


def pinv(a: np.ndarray, rcond: float = 1e-15) -> np.ndarray:
    """``np.linalg.pinv(a, rcond)``, from a ``gesvd`` SVD where ``gesdd`` does
    not converge.  1e-15 is numpy's own default cut, relative to the largest
    singular value."""
    try:
        return np.linalg.pinv(a, rcond=rcond)
    except np.linalg.LinAlgError:
        _note(np.asarray(a))
        u, s, vt = scipy.linalg.svd(np.asarray(a), full_matrices=False,
                                    lapack_driver="gesvd")
        keep = s > rcond * (s.max() if s.size else 0.0)
        return (vt[keep].T / s[keep]) @ u[:, keep].T


def lstsq(a: np.ndarray, b: np.ndarray, rcond: float | None = None):
    """``np.linalg.lstsq``, with ``gelss`` where ``gelsd`` does not converge.

    ``rcond=None`` is numpy's cut, machine epsilon × max(M, N), passed to
    SciPy's ``cond`` explicitly because SciPy's own default is epsilon alone.
    """
    try:
        return np.linalg.lstsq(a, b, rcond=rcond)
    except np.linalg.LinAlgError:
        a = np.asarray(a)
        _note(a, np.asarray(b))
        cut = (np.finfo(np.float64).eps * max(a.shape) if rcond is None else rcond)
        return scipy.linalg.lstsq(a, b, cond=cut, lapack_driver="gelss")


def cond(a: np.ndarray) -> float:
    """``np.linalg.cond(a)``, the 2-norm condition number, from a ``gesvd``
    SVD where ``gesdd`` does not converge."""
    try:
        return np.linalg.cond(a)
    except np.linalg.LinAlgError:
        a = np.asarray(a)
        _note(a)
        s = scipy.linalg.svd(a, compute_uv=False, lapack_driver="gesvd")
        with np.errstate(divide="ignore", invalid="ignore"):
            r = s[0] / s[-1]
        return np.inf if np.isnan(r) else r


# SciPy's TRF imports ``svd`` into its own module and offers no driver
# setting, so its step is reached by replacing that one name.  The
# replacement passes every call through unchanged, and retries a failure only
# on a thread inside :func:`scipy_trf`, so any other caller of SciPy's TRF in
# the process keeps SciPy's behaviour, raise included.
_trf_svd_original = None


def _trf_svd(a, *args, **kwargs):
    try:
        return _trf_svd_original(a, *args, **kwargs)
    except np.linalg.LinAlgError:
        if not getattr(_local, "trf", False) or kwargs.get("lapack_driver", "gesdd") != "gesdd":
            raise
        _note()
        return _trf_svd_original(a, *args, **{**kwargs, "lapack_driver": "gesvd"})


def _install_trf_svd() -> bool:
    """Put :func:`_trf_svd` in TRF's module once; ``False`` where TRF no longer
    calls ``scipy.linalg.svd`` by that name, which leaves it untouched."""
    global _trf_svd_original
    from scipy.optimize._lsq import trf

    with _install_lock:
        current = getattr(trf, "svd", None)
        if current is _trf_svd:
            return True
        if current is not scipy.linalg.svd:
            return False
        _trf_svd_original = current
        trf.svd = _trf_svd
        return True


@contextlib.contextmanager
def scipy_trf() -> Iterator[None]:
    """Inside, SciPy's TRF repeats a step SVD that ``gesdd`` failed with ``gesvd``."""
    _install_trf_svd()
    outer = getattr(_local, "trf", False)
    _local.trf = True
    try:
        yield
    finally:
        _local.trf = outer
