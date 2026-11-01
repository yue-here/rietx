"""Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67-70.

    R_p   = Σ|y_o − y_c| / Σ y_o
    R_wp  = √[ Σ w (y_o − y_c)² / Σ w y_o² ]
    R_exp = √[ (N − P) / Σ w y_o² ]
    χ²    = Σ w (y_o − y_c)² / (N − P)        (reduced)
    GoF   = √χ² = R_wp / R_exp

``rwp_background_subtracted`` recomputes R_wp with the background removed from
both numerator-model and denominator-observed, the variant Toby recommends
when the background carries much of the raw intensity.  The Durbin-Watson
statistic d = Σ(Δᵢ−Δᵢ₋₁)²/ΣΔᵢ² on weighted residuals (Hill & Flack, 1987,
J. Appl. Cryst. 20, 356) flags serial correlation (d ≈ 2 ⇒ uncorrelated).

When residuals *are* serially correlated the χ²·(JᵀJ)⁻¹ esds are too small:
neighbouring points do not carry independent information.  Bérar & Lelann's
homogeneous correction (1991, J. Appl. Cryst. 24, 1, § IV eqs 10-12) adds a
same-sign neighbour linearly in proportion to its probability of being
correlated with its predecessor, S'' ≥ S, and multiplies every esd by √(S''/S)
— the inflation factor reported here and applied to the esds
(:func:`berar_lelann_factor`).
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

import numpy as np

from ..backend.linalg64 import require_fp64, to_host_fp64
from ..schemas.results import DataSupport, Statistics
from . import lapack

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..model.forward import CompiledModel
    from ..params.vector import ParameterTable

#: Which **entries** are atomic: the test :func:`structural_free_paths` reads
#: what a free column reaches against, never the free path itself (WP-2067).
#: fnmatch, so ``*`` crosses dots — the glob reaches every atom entry
#: (``…dof.k``, ``…x``, ``…occ``, ``…biso``, ``…adp.k``) and nothing else,
#: since ``atoms.`` appears in no other path.  See
#: :class:`~rietx.schemas.results.DataSupport` for why the cell, profile,
#: background and scale are outside it.
STRUCTURAL_PARAMETER_GLOB = "phases.*.atoms.*"

#: The relative cut :func:`normal_factors` hands :func:`_psd_pinv`: every
#: eigenvalue of the equilibrated normal matrix whose magnitude is at most
#: ``PINV_RCOND × |λ|max`` is discarded, and the direction it spans comes back
#: at **zero** variance.  numpy's own ``pinv`` default; named because a second
#: consumer derives a threshold from it — the scale–B hold's
#: ``refine.SCALE_B_SEPARATION_FLOOR`` is the column separation below which a
#: phase's scale and displacement pair falls under this cut (WP-1534), so the
#: hold fires exactly where the esd would otherwise be a confident zero.
PINV_RCOND = 1e-15

#: A Jacobian column whose largest entry has a binary exponent beyond ±this is
#: rescaled by :func:`column_rescale` before anything squares it.  Inside the
#: window the arithmetic is left exactly as it was, so an ordinary fit is
#: bit-identical; outside it, 2⁻⁴⁰⁰ ≈ 4e-121 squared is still a normal double,
#: and 1/d² stays below 1e+241 (WP-1463).
COLUMN_SAFE_EXPONENT = 400


def _is_blocked(jac) -> bool:
    """Whether ``jac`` is a joint fit's :class:`~.blocked.BlockJacobian`, read
    without importing it here (it imports this module)."""
    from .blocked import BlockJacobian

    return isinstance(jac, BlockJacobian)


def column_rescale(jac: np.ndarray) -> np.ndarray | None:
    """Exact power-of-two factors bringing out-of-range columns back, or ``None``.

    A column can sit at the edge of the double range: before WP-1938 a phase
    scale at 1e-170 had one of 1e-170, its solver coordinate's slope (WP-1463).
    Squared, its entries underflow, so a norm reads it as zero and a variance
    as infinite, although the physical esd is an ordinary number.  Every
    quantity read off a normalised column is unchanged by rescaling it, and a
    power of two is the rescaling that rounds nothing: it moves the exponent
    and leaves the significand alone.

    Returns ``None`` when every column is inside
    :data:`COLUMN_SAFE_EXPONENT`, so a caller keeps its original arithmetic
    and its bits.  Otherwise the factor is 1 for the in-range columns and
    brings each far one's largest entry to [0.5, 1), capped at 2¹⁰²³ so that a
    subnormal column is lifted rather than sent to ``inf``.  A zero column has
    no scale to fix and keeps 1.

    A joint fit's :class:`~.blocked.BlockJacobian` takes the same factors,
    read block by block (WP-1325).
    """
    if _is_blocked(jac):
        from .blocked import column_rescale as blocked_rescale

        return blocked_rescale(jac)
    jac = np.asarray(jac)
    if jac.shape[0] == 0:
        return None
    # two reductions rather than ``abs``, which would copy the whole Jacobian
    # on every call (each stage's residual cosine and covariance reach here)
    m = np.maximum(np.max(jac, axis=0), -np.min(jac, axis=0))
    _, e = np.frexp(m)  # m = f·2**e with 0.5 <= f < 1; e = 0 where m = 0
    far = (m > 0.0) & (np.abs(e) > COLUMN_SAFE_EXPONENT)
    if not far.any():
        return None
    s = np.ones(len(m), dtype=np.float64)
    s[far] = np.ldexp(1.0, np.clip(-e[far], -1023, 1023))
    return s


def column_norms(jac: np.ndarray) -> np.ndarray:
    """``np.linalg.norm(jac, axis=0)`` that a column of 1e-170 does not zero.

    Bit-identical to the plain norm whenever :func:`column_rescale` has nothing
    to do.  Otherwise each far column is normed after its power-of-two rescale
    and divided back, which is exact.  Block by block for a joint fit's
    :class:`~.blocked.BlockJacobian` (WP-1325).
    """
    if _is_blocked(jac):
        from .blocked import column_norms as blocked_norms

        return blocked_norms(jac)
    s = column_rescale(jac)
    if s is None:
        return np.linalg.norm(jac, axis=0)
    return np.linalg.norm(jac * s, axis=0) / s


def _column_in_range(col: np.ndarray) -> np.ndarray:
    """One column after :func:`column_rescale`, for a scale-free statistic."""
    s = column_rescale(col[:, None])
    return col if s is None else col * s[0]


def normal_factors(jac: np.ndarray, resid: np.ndarray, n_free: int, *,
                   chi2_floor: bool = False,
                   what: str = "residual entering the covariance solve",
                   ) -> tuple[np.ndarray, np.ndarray, float]:
    """The equilibrated inverse ``K`` and the column scales ``1/d``.

    ``Cov = K · outer(1/d, 1/d)``, and :func:`normal_covariance` is exactly
    that product.  It is returned in two factors because the product can
    overflow where each factor does not (WP-1463): a live column of 1e-160
    has ``1/d ≈ 1e+160``, a variance of 1e+320 and an esd of 1e+160, so a
    caller wanting the esd forms ``(1/d)·√K`` and never the variance.
    ``1/d`` is 0 on a gradient-free column, and ``chi2_red`` is the raw
    Σr²/(N−P).  See :func:`normal_covariance` for everything else.

    A joint fit's :class:`~.blocked.BlockJacobian` takes the same contract
    through the Schur complement of its arrow (:func:`.blocked.normal_factors`,
    WP-1325), never one pseudo-inverse of the whole matrix.
    """
    if _is_blocked(jac):
        from .blocked import normal_factors as blocked_factors

        return blocked_factors(jac, resid, n_free, chi2_floor=chi2_floor, what=what)
    require_fp64(resid, what)
    jac = to_host_fp64(jac)
    s = column_rescale(jac)
    if s is not None:
        # exact, and only on the far columns: E = D·JᵀJ·D is unchanged by a
        # column scale, so only the returned 1/d carries it back
        jac = jac * s
    JTJ = jac.T @ jac
    JTJ = 0.5 * (JTJ + JTJ.T)  # kill the fp asymmetry before the eigensolve
    chi2_red = float(resid @ resid) / max(len(resid) - n_free, 1)
    scale = max(chi2_red, 1.0) if chi2_floor else chi2_red

    d = np.sqrt(np.diag(JTJ))
    live = d > 0.0
    inv_d = np.where(live, 1.0 / np.where(live, d, 1.0), 0.0)
    k = _psd_pinv(JTJ * np.outer(inv_d, inv_d), PINV_RCOND) * scale
    if s is not None:
        inv_d = inv_d * s
    return k, inv_d, chi2_red


def _psd_pinv(a: np.ndarray, rcond: float) -> np.ndarray:
    """``np.linalg.pinv(a, rcond=rcond, hermitian=True)`` with every kept
    eigenvalue inverted by its magnitude, so the inverse is PSD (WP-1930).

    A normal matrix or a covariance is PSD, but ``eigh`` returns an exactly
    flat direction at a rounding-level eigenvalue of either sign: measured at
    −3.5e-15 to +3.7e-15 of the largest on the LaB₆ + cBN fit whose six
    Lorentzian widths are one quantity, against a cut of :data:`PINV_RCOND`.
    ``pinv`` keeps any of them above the cut and inverts it with its sign.  A
    positive one gives the flat direction a huge variance and ρ = ±1, which is
    the honest answer.  A negative one gives every column on it a negative
    variance, which :func:`~rietx.optimize.least_squares.covariance_estimates`
    floors to an esd of exactly 0 and a correlation of 0: six undetermined
    widths read "± 0.000" and ``HIGH_CORRELATION`` fell silent.  In a χ² the
    same eigenvalue makes the quadratic form negative.  Which of the two
    happened was decided by rounding, so it split by platform.  Inverting the
    magnitude gives the negative case the positive case's answer.

    numpy's own steps are kept, stack axes included, with only the sign left
    out: numpy multiplies ``u`` by sign(λ) to form ``vt``, and a PSD matrix
    has none to move.  The result is bit-identical to ``pinv`` whenever no
    kept eigenvalue is negative, a stacked ``(k, n, n)`` input and an empty
    matrix included (``tests/test_covariance_scaling.py``).
    """
    a = np.asarray(a)
    if a.size == 0:
        m, n = a.shape[-2:]
        return np.empty(a.shape[:-2] + (n, m), dtype=a.dtype)
    lam, u = lapack.eigh(a)
    s = np.abs(lam)
    order = np.argsort(s)[..., ::-1]
    s = np.take_along_axis(s, order, axis=-1)
    u = np.take_along_axis(u, order[..., None, :], axis=-1)
    cutoff = rcond * np.amax(s, axis=-1, keepdims=True)
    large = s > cutoff
    s = np.divide(1, s, where=large, out=s)
    s[~large] = 0
    uh = np.swapaxes(u, -1, -2)
    if np.iscomplexobj(uh):    # Hermitian: u·s·uᴴ, as numpy's own pinv
        uh = uh.conj()
    return np.matmul(u, np.multiply(s[..., None], uh))


def discarded_directions(jac: np.ndarray) -> tuple[int, np.ndarray]:
    """How many directions of the equilibrated normal matrix ``_psd_pinv`` discards
    beyond dead columns, and which columns they *touch* (WP-1535).

    One touched column is enough: a discarded direction needs two loaded
    columns to exist, but only the columns that pass the test below are named.

    :func:`normal_factors` hands :func:`_psd_pinv` a cut, and a direction under it comes
    back at **zero** variance: every parameter loading on it reports only the
    variance of the directions the data did measure.  A column with no gradient
    is handled (infinite variance, ``_cov_free``) and so is a pair whose
    |ρ| ≈ 1 (``FLAT_DIRECTION``); a combination of three or more columns has
    neither.  Returns ``(n_discarded, touched)``, ``touched`` the indices into
    the columns of ``jac``, empty when nothing live is discarded.

    **Touched is derived, not chosen.**  A discarded eigenvalue is at most
    ``PINV_RCOND·|λ|max``, so the discarded subspace adds *at least*
    ``Σ_gone v_i²/cut`` to column *i*'s equilibrated variance.  Column *i* is
    touched when that is at least the variance the solve reports,
    ``Σ_kept v_i²/|λ|``: its esd is then at least √2 short.  The sum over the
    subspace, never one eigenvector, because two discarded directions are
    defined only up to a rotation inside it and the projector is not.  Jacobi
    scaling is shared with :func:`normal_factors`, so a column's units do not
    enter.  The matrix is rebuilt here, not returned by :func:`normal_factors`,
    whose signature and bits stay as they were: one more ``eigh``.  A joint
    fit's :class:`~.blocked.BlockJacobian` is read on its blocked covariance's
    own discards (:func:`.blocked.discarded_directions`, WP-1325).
    """
    if _is_blocked(jac):
        from .blocked import discarded_directions as blocked_discarded

        return blocked_discarded(jac)
    jac = to_host_fp64(jac)
    s = column_rescale(jac)
    if s is not None:
        jac = jac * s
    JTJ = jac.T @ jac
    JTJ = 0.5 * (JTJ + JTJ.T)
    d = np.sqrt(np.diag(JTJ))
    live = d > 0.0
    none = (0, np.zeros(0, dtype=np.intp))
    if live.sum() < 2:
        return none
    inv_d = np.where(live, 1.0 / np.where(live, d, 1.0), 0.0)
    lam, vec = lapack.eigh(JTJ * np.outer(inv_d, inv_d))
    cut = PINV_RCOND * np.abs(lam).max()
    gone = np.abs(lam) <= cut
    # a dead column is its own eigenvector at zero, and not this function's
    n_gone = int(gone.sum()) - int((~live).sum())
    if n_gone < 1:
        return none
    # by magnitude, as :func:`_psd_pinv` inverts a kept eigenvalue
    kept_var = (vec[:, ~gone] ** 2 / np.abs(lam[~gone])).sum(axis=1)
    lost_var = (vec[:, gone] ** 2).sum(axis=1) / cut
    touched = np.flatnonzero(live & (lost_var >= kept_var))
    return (n_gone, touched) if len(touched) >= 1 else none


def resolved_correlation(corr: np.ndarray, jac: np.ndarray
                         ) -> tuple[np.ndarray, np.ndarray]:
    """The correlation matrix with every direction the Jacobian cannot resolve
    projected out, and the columns those directions dominate (WP-2050).

    Returns ``(rho, unresolved)``.  ``rho`` is ``corr`` where nothing is
    unresolved.  Otherwise a pair of resolved columns carries the correlation
    of the covariance with the unresolved subspace removed, a pair with one
    unresolved column is ``nan`` (its ρ is not determined), and a pair of
    unresolved columns keeps ``corr``'s value, which is ±1 to rounding.
    ``unresolved`` is a boolean mask over the columns of ``jac``.

    **The cut is the Jacobian's own accuracy, not a tolerance.**  The forward
    differences of the peak chain carry a relative error of order
    :data:`~rietx.optimize.least_squares.FD_STEP` per column (5e-7 measured
    against jax on lab brucite, :func:`~.least_squares._fd_typicals`).  With
    every column scaled to unit norm, an error of at most ``FD_STEP`` in each
    of *n* columns has a spectral norm of at most ``√n·FD_STEP`` (it is bounded
    by the Frobenius norm), and by Weyl's inequality a singular value moves by
    no more.  So an eigenvalue of the unit-diagonal normal matrix at or below
    ``n·FD_STEP²`` is a direction the data has not been shown to move.  The
    covariance still inverts it, and rounding then sets it: on brucite's
    Gaussian-size, Gaussian-strain and W triple it sat between 2.7e-15 and
    4.9e-14 of |λ|max under 1e-14 nudges to one start value, while the next
    direction stayed at 1.3-1.4e-10.  On corundum the same triple reached
    1.2-1.9e-12 of |λ|max in its later stages, above ``FD_STEP²·|λ|max`` and
    still under ``n·FD_STEP²``.  Every column carries a rounding-level
    loading on such a direction, divided by that eigenvalue, so a ρ against
    one of its members, and between two columns that load on it weakly, is
    rounding too: ``lor_size ~ lor_strain`` read −0.995 or −0.9975 or fell
    under the guard as the nudge moved, and −0.896 ± 0.003 projected.

    GSAS-II computes its correlations off a pseudo-inverse truncated the same
    way, at a relative cut of 1e-6 on the normal matrix's singular values
    (``SVDtol``, ``GSASIImath.setHcorr``).  That cut would also remove
    brucite's 1.4e-10 zero-shift/displacement direction, whose correlations
    hold to 2e-5 under the same nudges and which a refiner wants reported.

    **Which columns it dominates** is :func:`discarded_directions`' *touched*
    test with this cut: the subspace adds at least ``Σ_gone v_i²/cut`` to
    column *i*'s equilibrated variance, and the column is unresolved when that
    is at least the variance the resolved directions give it.  A dead column
    and a joint fit's :class:`~.blocked.BlockJacobian` are left as they are.

    **Limits, measured or by construction.**  The error premise holds for the
    width columns it was measured on; ``FD_STEP``'s audit row records other
    columns up to 2.5e-4 from a Richardson oracle, and a direction set by such
    an error sits above this cut and is left alone, as it was before.  The cut
    grows with *n*: at 60 free columns it is 6e-11, 12× under brucite's
    zero-shift/displacement direction.  On brucite's seventh stage the triple
    reached 2.3× the cut under one nudge, so that stage reads it as resolved.
    Two unresolved directions leave a ρ between members of different ones set
    by two rounding eigenvalues.  A member with no ±1.000 partner has its
    pairs withheld without a ``FLAT_DIRECTION`` clause to say so.
    """
    from .least_squares import FD_STEP

    corr = np.asarray(corr, dtype=float)
    n = corr.shape[0]
    unresolved = np.zeros(n, dtype=bool)
    if _is_blocked(jac):
        return corr, unresolved
    jac = to_host_fp64(jac)
    if jac.ndim != 2 or jac.shape[1] != n:
        return corr, unresolved
    s = column_rescale(jac)
    if s is not None:
        jac = jac * s
    JTJ = jac.T @ jac
    JTJ = 0.5 * (JTJ + JTJ.T)
    d = np.sqrt(np.diag(JTJ))
    live = np.flatnonzero(d > 0.0)
    if len(live) < 2:
        return corr, unresolved
    sub = JTJ[np.ix_(live, live)] / np.outer(d[live], d[live])
    lam, vec = lapack.eigh(sub)
    cut = len(live) * FD_STEP ** 2
    gone = np.abs(lam) <= cut
    if not gone.any():
        return corr, unresolved
    kept_var = (vec[:, ~gone] ** 2 / np.abs(lam[~gone])).sum(axis=1)
    lost_var = (vec[:, gone] ** 2).sum(axis=1) / cut
    member = lost_var >= kept_var
    unresolved[live[member]] = True
    k = (vec[:, ~gone] / np.abs(lam[~gone])) @ vec[:, ~gone].T
    sd = np.sqrt(np.diag(k))
    rho = np.array(corr, copy=True)
    res = live[~member]
    rho[np.ix_(res, res)] = (k / np.outer(sd, sd))[np.ix_(~member, ~member)]
    un = live[member]
    rho[np.ix_(un, res)] = np.nan
    rho[np.ix_(res, un)] = np.nan
    rho[res, res] = 1.0
    return rho, unresolved


def normal_covariance(jac: np.ndarray, resid: np.ndarray, n_free: int, *,
                      chi2_floor: bool = False,
                      what: str = "residual entering the covariance solve",
                      ) -> tuple[np.ndarray, float]:
    """``Cov = χ²_red · pinv(JᵀJ)`` — the one guarded normal-matrix solve.

    Returns ``(cov, chi2_red)`` with ``chi2_red`` always the *raw*
    Σr²/(N−P), even when ``chi2_floor`` has floored the factor applied to
    ``cov``: the raw value is what a caller reports, the floored one is what it
    should trust.  ``chi2_floor=True`` replaces the factor with
    ``max(χ²_red, 1)``, for a fit whose model is known to be inexact and whose
    esds must not be *deflated* by a locally-good χ² (peak profiles over a
    single line); the whole-pattern fit leaves it off, because there χ²_red < 1
    means the file's esds are pessimistic and shrinking is correct.

    **The pseudo-inverse is taken on the symmetrised matrix with
    ``hermitian=True``, and this is a correctness requirement, not a
    micro-optimisation.**  JᵀJ is positive semi-definite, so its Moore-Penrose
    inverse is too and every |ρ| ≤ 1 exactly.  But the *general* SVD path
    ``pinv`` takes by default treats the matrix as unstructured, and on a
    cond ≈ 10²⁰ normal matrix (routine here — the scale/axial/background block
    of a real fit) it returns a visibly non-symmetric, non-PSD result: measured
    |ρ| up to 1.6 × 10³ on synthetic ill-conditioning, and +2.75 for
    ``scale ~ axial_sl`` on the WP-0502 fluorite fit, which is what made that WP
    log "the correlation guard is undermined wherever conditioning is poor".
    ``hermitian=True`` routes through ``eigh``, which cannot break the symmetry,
    and caps the same cases at 1 + 4 ulp.

    Symmetric is not PSD, though.  An exactly flat direction comes back at a
    rounding-level eigenvalue of either sign, and ``pinv`` inverts a kept
    negative one with its sign, giving negative variances.  So the solve is
    :func:`_psd_pinv`, which is ``pinv`` with each kept eigenvalue inverted by
    its magnitude (WP-1930).  Where no kept eigenvalue is negative, it returns
    ``pinv``'s bits.

    The solve is fp64 unconditionally (architecture invariant 2): cond(JᵀJ) =
    cond(J)², so forming and inverting the normal matrix is the step reduced
    precision can never take.  ``to_host_fp64`` is that boundary — a Jacobian
    whose columns were computed at fp32 is upcast here before JᵀJ, while the
    residual is *required* to have been fp64 all along.

    **The matrix is equilibrated to unit diagonal before the pseudo-inverse,
    and this is the difference between an esd and a number** (WP-1110 item 14).
    ``pinv`` discards every eigenvalue below ``rcond × |λ|max``, so the cutoff
    is set by the *largest* column and applied to all of them.  On a real
    refinement the column 2-norms span thirteen orders of magnitude — 4.8e-06
    to 8.5e+06 on the NAC fit that WP measured — so four of seventeen
    directions were discarded, and a discarded direction reports **zero**
    variance for a parameter about which the data said nothing at all.  Not
    ``None``, not a large esd: a small one.  Measured there,
    ``phases.0.gauss_size`` came back 6.1e-14 ± 9.9e-11, a figure a caller
    would quote, where the equilibrated inverse says ± 4.3e+08 — undetermined,
    which is what it is.

    Jacobi scaling is the fix and it is not a tuning choice: van der Sluis
    (1969), Numer. Math. 14, 14-23, gives that scaling a symmetric positive
    definite matrix to unit diagonal comes within a factor of its order of the
    best possible diagonal conditioning.  The property it restores is the one
    whose absence proves the old form wrong: **an esd must not depend on
    another parameter's units.**  Rescaling one column by 1e6 moved the other
    columns' esds by a factor of 2 before and by 4e-16 after (both measured on
    a synthetic 400×4 problem).  Well-determined parameters are untouched —
    cell, scale and every background term agree to four figures across the
    change; only the directions that were being silently zeroed move.

    A column with **no gradient at all** has a zero diagonal, so it cannot be
    equilibrated and is not merely ill-conditioned: nothing in the data
    constrains it.  Its variance comes back as ``inf`` rather than 0, because
    zero is the confident wrong answer and the caller turns ``inf`` into the
    absent esd WP-1072 requires.  Its off-diagonal covariances are zero, which
    is correct — a direction the residual does not move is uncorrelated with
    everything.

    A column that is **tiny but not zero** is live, and before WP-1463 the
    arithmetic said otherwise.  A phase scale at 1e-166, in the solver
    coordinates of the time, had a column of 1e-158: its variance K·(1/d)² overflowed to ``inf`` and read as
    unmeasured, and below about 1e-170 its d² underflowed to zero and read as
    gradient-free.  Its physical esd was 7.66e-9 at every value in between.
    :func:`column_rescale` removes the underflow, exactly and only where it
    acts.  The overflow is the variance's own, since 1e+330 has no double, so
    this function still returns ``inf`` there.  A caller that wants the esd
    takes :func:`normal_factors` and never forms the variance, as
    :func:`~rietx.optimize.least_squares.covariance_estimates` does.

    **A row on its bound stays in the matrix** (WP-1929).  Since WP-1938 a
    floor is an ordinary bound of 0, and a width or scale resting on it has a
    live column, so its own esd and every neighbour's are *marginal*.  That is
    TOPAS's reading, and the row is tagged instead
    (:attr:`~rietx.schemas.results.RefinedParameter.at_bound`).  The other
    reading conditions on the row: it leaves the matrix, and each correlated
    neighbour's esd shrinks by √(1 − ρ²).  A caller wanting it refits with
    the row held (BT-1: ``profile.x`` 0.0032202 held against 0.0098437
    marginal, ρ = −0.945 with ``profile.y`` on 0; the held fit also counts
    one free parameter fewer in χ²_red).  Two things decided it.  The marginal
    esd is the larger, and it moves continuously as a row approaches its
    bound, while the conditional one jumps when the at-bound test fires.
    Self & Liang (1987, *J. Am. Stat. Assoc.* **82**, 605) put the sampling
    distribution of a neighbour between the two.  Before WP-1938 the choice
    looked like one between a number that depended on where the solver
    stopped and one that did not.  It was neither: the floor row's column was
    differenced below rounding, and the column taken in physical units gives
    one marginal esd at every stopping point (BT-1's ``profile.x``, 0.0098437
    at internal coordinates −25.5 and −514).

    No floor makes a column dead after WP-1938.  What ``1/d = 0`` and
    :meth:`~rietx.params.vector.ParameterTable.unmeasured_rows` still catch
    is a column the model is exactly flat in.  The cases named in the package
    are a zero upstream (a phase scale of 0 empties its phase's structural
    columns, a moment of 0 its angles and widths), a clamp (every Gaussian
    width column under ``caglioti._MIN_GAMMA_G2``), and a body turned about an
    axis its template is symmetric under.

    This lives here, rather than inside :func:`covariance_estimates`, because
    two surfaces now need it — the whole-pattern fit and the per-peak profile
    fits of :mod:`rietx.indexing.peakfit` — and they must not be able to
    disagree about the pinv guarding.
    """
    k, inv_d, chi2_red = normal_factors(jac, resid, n_free,
                                        chi2_floor=chi2_floor, what=what)
    return covariance_from_factors(k, inv_d), chi2_red


def covariance_from_factors(k: np.ndarray, inv_d: np.ndarray) -> np.ndarray:
    """``K · outer(1/d, 1/d)``, the product :func:`normal_factors` defers.

    The one assembly both :func:`normal_covariance` and
    :func:`~rietx.optimize.least_squares.covariance_estimates` use.  An entry
    past the double range is ``inf``, silently (WP-1463).
    """
    live = inv_d > 0.0
    with np.errstate(over="ignore", invalid="ignore"):
        cov = k * np.outer(inv_d, inv_d)
    if not live.all():
        # a gradient-free column: unmeasured, so infinite variance and no
        # correlation with anything.  `cov` already holds zeros in its row and
        # column, which is the right off-diagonal answer and the wrong diagonal
        # one, so only the diagonal is overwritten.
        cov[np.flatnonzero(~live), np.flatnonzero(~live)] = np.inf
    return cov


def berar_lelann_factor(delta: np.ndarray) -> float:
    """Esd inflation factor for serial correlation, √(S''/S).

    Bérar & Lelann (1991), *J. Appl. Cryst.* **24**, 1-5, § IV, the
    "homogeneous correction" (p. 4, eqs 10-12).  On the weighted residuals
    aᵢ = √wᵢ·Δᵢ, each point carries the probability zᵢ that it is correlated
    with its predecessor,

        zᵢ = √(2π xᵢ) / (2 + √(2π xᵢ)),  xᵢ = aᵢ² + aᵢ₋₁²,  if aᵢ·aᵢ₋₁ > 0,
        zᵢ = 0                                            otherwise,

    and is added quadratically with weight 1 − zᵢ² and linearly with weight
    zᵢ (eq 10):

        S'' = Σᵢ (1 − zᵢ²) aᵢ² + Σ_runs (Σ_{i∈run} zᵢ aᵢ)²,

    a run being a maximal stretch of consecutive zᵢ > 0 (the m-summation of
    eq 8, "performed while t is non zero").  The first point of a same-sign
    stretch has z = 0 and is quadratic only.  Esds are multiplied by √(S''/S)
    (eq 11; the Appendix's ``SCOR``).  Within a run every aᵢ shares a sign, so
    S'' − S is a sum of positive cross terms and the factor is ≥ 1.

    zᵢ is the paper's stated derivation (p. 4) — "the relative values of the
    distribution functions of the χ² distributions for one and two degrees of
    freedom" — read as densities at x: f₂/(f₁ + f₂) with f₁ = e^{−x/2}/√(2πx)
    and f₂ = e^{−x/2}/2, which is the expression above.  That is the 2π the
    paper's own Fortran carries (Appendix, ``SQRT(2*3.1416*COREL)``) and
    Andreev (1994, *J. Appl. Cryst.* **27**, 288, eq 3) prints; the typeset
    eq (12) has 2 where both have 2π.  The Fortran also pairs each zᵢ with
    the *earlier* point of its pair, the time reverse of eq (10), and seeds a
    run with the last point of the previous one (the inaccuracy Andreev's
    Appendix I corrects); this is eq (10) as printed.

    Two properties a reader needs.  zᵢ depends on aᵢ² itself, so the factor
    is not invariant to the residuals' scale: the paper's normalised
    differences are meant to grow with counting time (§ V).  And white
    residuals do not give 1: iid N(0, 1) residuals give E[S'']/E[S] =
    1.2694 (quadrature, N → ∞), a factor ≈ 1.127, so a value near that is
    no evidence of serial correlation.

    Before 1.6 (#674) this function summed every same-sign stretch
    coherently with weight 1, its first point included: the § III product
    test at level p = 0 (eqs 6-9, p. 3, "both points will be considered as
    correlated"), which the paper sets aside because "the correction proves
    to be strongly dependent" on the level.  It read ≈ 1.51 on white
    residuals.
    """
    d = np.asarray(delta, dtype=np.float64)
    if len(d) < 2:
        return 1.0
    chi2 = float(d @ d)
    if chi2 <= 0.0:
        return 1.0
    q = np.sqrt(2.0 * np.pi * (d[1:] * d[1:] + d[:-1] * d[:-1]))
    z = np.concatenate([[0.0], np.where(d[1:] * d[:-1] > 0.0, q / (2.0 + q), 0.0)])
    quad = float(((1.0 - z * z) * d * d).sum())
    # runs of consecutive z > 0, summed linearly by prefix-sum differences
    edges = np.flatnonzero(np.diff(np.concatenate([[0], (z > 0.0).astype(np.int8), [0]])))
    cs = np.concatenate([[0.0], np.cumsum(z * d)])
    lin = cs[edges[1::2]] - cs[edges[::2]]
    return max(float(np.sqrt((quad + lin @ lin) / chi2)), 1.0)


def chi_bar_squared_quantile(level: float, k: int) -> float:
    """The ``level`` point of the χ̄² mixture of ``k`` one-sided directions.

    A likelihood-ratio statistic for k parameters that each sit on the boundary
    of their range under the null follows Σⱼ C(k, j)/2ᵏ · χ²ⱼ, with χ²₀ the
    point mass at 0 (Self, S. G. & Liang, K.-Y., 1987, *J. Am. Statist. Assoc.*
    **82**, 605; the χ̄² family: Shapiro, A., 1985, *Biometrika* **72**, 133).
    The weights are binomial because the k directions are taken as
    independent.  Each half of a direction's sampling distribution lands on the
    boundary with probability ½.  Returns the c with P(T > c) = 1 − ``level``:
    2.706, 4.231 and 6.497 at 95 % for k = 1, 2 and 4.

    k = 1 is ½χ²₀ + ½χ²₁, whose point is χ²₁'s at 2·``level`` − 1, in closed
    form.  :func:`rietx.strategy.parameter_interval.interval_quantile` returns
    it for a row on its bound by calling this.  k > 1 is solved by Brent's
    method on the tail.  The tail is at most P(χ²ₖ > c) · (1 − 2⁻ᵏ), so χ²ₖ's
    own point brackets the root from above.
    """
    from math import comb

    from scipy.optimize import brentq
    from scipy.stats import chi2

    if isinstance(k, bool) or int(k) != k or k < 1:
        raise ValueError(f"the mixture needs at least one direction, not k={k!r}")
    k = int(k)
    if not 0.0 < level < 1.0:
        raise ValueError(f"a confidence level lies strictly between 0 and 1, "
                         f"not {level!r}")
    alpha = 1.0 - level
    # the point mass at 0 carries 2⁻ᵏ, so a level at or below it needs no cut
    if alpha >= 1.0 - 0.5 ** k:
        raise ValueError(
            f"at level {level:g} the mixture of {k} one-sided directions puts "
            f"its {0.5 ** k:g} point mass at 0 above the level, so no positive "
            "cut exists")
    if k == 1:
        return float(chi2.ppf(2.0 * level - 1.0, 1))
    weights = [comb(k, j) / 2.0 ** k for j in range(k + 1)]

    def excess(c: float) -> float:
        return sum(w * chi2.sf(c, j) for j, w in enumerate(weights) if j) - alpha

    return float(brentq(excess, 1e-12, float(chi2.isf(alpha, k)), xtol=1e-12))


def _chi2_absolute(stats) -> float:
    """The weighted residual sum of squares ``report.layer2.delta_bic`` wants.

    ``Statistics.chi2`` is the *reduced* χ² (Σwd²/(N−P)), and the two models being
    compared have different P, so dividing by their own dof first would fold a
    second, unwanted ratio into the comparison.  The inverse of
    :func:`compute_statistics`' own division, clamp included.
    """
    return float(stats.chi2) * max(stats.n_points - stats.n_free_parameters, 1)


def effective_sample_size(n_points: int, esd_inflation: float | None) -> float:
    """The channel count a model-selection penalty may charge, N/f² (#270).

    Schwarz's BIC (1978, *Ann. Statist.* **6**, 461) and Hamilton's test
    (1965, *Acta Cryst.* **18**, 502) both assume N **independent**
    observations.  A powder residual is serially correlated, and the fit
    already measures by how much: ``f`` is :func:`berar_lelann_factor`
    (Bérar & Lelann 1991, *J. Appl. Cryst.* **24**, 1), the factor every
    reported esd is inflated by.  Dividing N by f² is the count at which the
    two answers agree: for one added parameter the reward term N_eff·ln(χ²_r/χ²_f)
    is then the parameter's own t² at its *inflated* esd, so ΔBIC > 0 exactly
    when t² > ln N_eff, and a parameter the esd column puts within 1σ of zero
    can no longer be decisive.

    A heuristic, not a theorem, and conservative in the direction the esds
    are: white residuals still give f ≈ 1.13 (:func:`berar_lelann_factor`'s
    caveat), so N_eff ≈ N/1.27 there.  Not :func:`effective_observations`,
    which answers a resolution question (how many reflections the points
    resolve); this answers an independence one.  ``esd_inflation`` of
    ``None`` (a fit too short to measure it) returns N unchanged.

    Chosen over M_ind on a measurement (WP-1417 task 3; 27 last-freed
    parameters across the refining acceptance suites plus an 11-case
    synthetic single-occupancy fit at 50 000 correlated points): at N/f²
    every |t| < 2.3 is refused and every |t| ≥ 2.6 admitted, where charging
    M_ind refused 8 of the 12 cases at |t| ≥ 2.6 it has a value for (up to
    t = 6.8), admitted one at t = 0.81 where M_ind exceeds N/f², and has no
    value for a joint fit.  That measurement predates 1.6, whose factor reads
    12-21 % lower on real residuals (#674).
    """
    if esd_inflation is None or not esd_inflation > 1.0:
        return float(n_points)
    return float(n_points) / (esd_inflation * esd_inflation)


def _structural_targets(free_paths: list[str]) -> list[tuple[int, str]]:
    """The columns an absorption screen asks about: (index, path) pairs.

    **Anchored at ``phases.``, never left as a bare suffix.**  The screen asks
    what a *structural* parameter — a phase scale, a displacement parameter, an
    occupancy — loses to a block that is not structural, so a path outside the
    structure answers a different question or none.  A suffix alone was true
    only while ``phases.i.scale`` was the one path ending in ``.scale``, and it
    has stopped being: ``instrument.background.scale`` (WP-1309) is a *member of
    the background block*, so screening it against that block projects a column
    onto a span that contains it and reports R² = 1.00 about every fit that
    frees it.  ``mode_fixed_path`` anchored the same test for the same reason
    one release earlier (WP-1119, ``vars.scale``).

    One function rather than the two copies this replaced, because the two
    screens are the same question asked of different blocks, and a target list
    that drifts between them is a difference nobody declared.

    What it deliberately does not reach: a caller's own variable
    (``vars.scale``), whose column is structural or not depending on what it
    ties to, which this function cannot see.  Screening it on its spelling is
    what went wrong above.
    """
    return [(k, p) for k, p in enumerate(free_paths)
            if p.startswith("phases.")
            and (p.endswith((".biso", ".scale", ".occ")) or ".adp." in p)]


def background_absorption(jac: np.ndarray, free_paths: list[str],
                          peak_prefixes: frozenset[str]) -> dict[str, float]:
    """How much of each structural parameter the background could reproduce.

    For parameter i with Jacobian column jᵢ and the background columns
    spanning B, the multiple correlation

        R²ᵢ = 1 − ‖jᵢ − P_B jᵢ‖² / ‖jᵢ‖²          (P_B = orthogonal projector)

    is the fraction of jᵢ's effect the background can imitate.  R² → 1 means
    the two are degenerate: the background absorbs Bragg intensity, biasing
    ADPs up and scales (hence QPA fractions) down *while Rwp improves* — the
    documented failure mode of over-flexible backgrounds.  Anisotropic ADP
    DOFs (``…adp.k``) are screened alongside Biso: more displacement freedom
    means more of it available to soak up a background error.

    Pairwise ρ is the wrong statistic for this: with ~100 spline coefficients
    each individual |ρ| stays small (~0.2) while the block collectively
    absorbs ~50 % of the parameter (measured).  The projection sees the block.

    ``jac`` must be the **full** Jacobian including any P-spline penalty rows
    — those rows are what makes a stiff background unable to imitate a peak,
    and dropping them overstates the risk by ~5× (measured: R² 0.46 → 0.08 at
    λ = 10⁴).
    """
    # Background-landing extra components join the block.  The statistic asks
    # what the *whole declared background* can imitate, and an explicit broad
    # hump is the sharpest form of the failure it exists to catch — one narrow
    # enough to sit under a reflection eats Bragg intensity exactly as a
    # too-flexible spline does, and unlike the spline it can do it with three
    # parameters.  Leaving it out would make the number *less* true the more of
    # the background's flexibility lives in humps.
    #
    # **Peak-landing components do not join it** (WP-1103).  Since the seam
    # gained a second member, ``instrument.extra_components.`` no longer means
    # "background": a ``PeakComponent`` is a declared sharp peak, is not in
    # ``y_background``, and sweeping its columns in here would report a
    # perfectly stiff background as absorbing whatever a declared holder line
    # happens to be correlated with.  ``peak_prefixes`` carries the dot-path
    # prefixes of the components that are *not* background, and it is
    # **required** rather than defaulted: a caller who forgets would silently
    # get the pre-1103 answer, which is the defaulted-``False`` shape WP-1076
    # names.  ``model.peak_components`` is where a caller gets it.
    #
    # The nonlinearity is not an objection: every column here is a linearisation
    # at the converged θ, the ``.biso`` and ``.scale`` targets included, and the
    # esds and correlations the guard sits beside are built from the same one.
    # What *was* an objection is a zero column — a component at its off state
    # contributes several — and that is handled once, in ``_span_basis``,
    # because it is a fact about spans and not about components.
    bg = [k for k, p in enumerate(free_paths)
          if (p.startswith("instrument.background.")
              or (p.startswith("instrument.extra_components.")
                  and not p.startswith(tuple(peak_prefixes))))]
    return block_projection_r2(jac, bg, _structural_targets(free_paths))


def _span_basis(jac: np.ndarray, cols: list[int]) -> np.ndarray:
    """Orthonormal basis (thin QR) for the span of the selected columns.

    The one QR both :func:`block_projection_r2` and
    :func:`one_parameter_gains` build their projections from — extracted so
    the two statistics cannot disagree about how a span is orthogonalised.

    **An exactly-zero column is dropped, because it is not in the span.**
    LAPACK's Householder QR returns a Q with orthonormal columns whatever the
    rank of A, so a zero column of A does not give a zero column of Q — it gives
    an *arbitrary* direction orthogonal to the rest, and ``q qᵀ`` then projects
    onto a space strictly larger than span(A).  Measured: a 3-column block with
    two zero columns reports R² = 1.00 for **every** target, which is a
    saturated guard on a block that can produce nothing.

    **Exactly** zero is the operative word, and it is why this filter changes
    no number that shipped before it.  No design row is ever zero (checked: the
    Chebyshev rows, the clamped-cubic B-spline rows and the 1/2θ air row all
    carry signal), and a parameter at its own off state does *not* produce
    one either — ``BackgroundPSpline.air_scatter`` at value 0 has its 1/2θ row
    as its column.  What does produce one is a **product**: an additive background
    peak at zero height has ∂y/∂2θ₀ = ∂y/∂Γ = h·(…) = 0 to the bit, so a
    declared peak freed at its default height hands this function two of them.

    All columns zero leaves an ``(n, 0)`` basis, whose projector is zero, i.e.
    "this block imitates nothing" — which is true.

    **A non-finite column is not dropped, and the caller owns that.**  A zero
    column demonstrably spans nothing; a NaN column spans something *unknown*,
    so dropping it would quietly narrow the span and understate every number
    built on it — the direction that silences a guard rather than tripping it.
    A caller that *fires* on a threshold withholds instead:
    :func:`block_projection_r2` returns ``{}`` on a non-finite block or
    nuisance set (WP-1130).  The two callers that only *rank*
    (:func:`one_parameter_gains`, ``strategy.suggest``) make no such check, so
    read this as a property of that one caller and not of this function's
    every consumer.
    """
    cols = [c for c in cols if np.any(jac[:, c])]
    q, _ = np.linalg.qr(jac[:, cols])
    return q


def _off_span(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``v`` minus its projection onto the orthonormal columns of ``q``.

    Works for a vector or a whole matrix of columns; ``q`` must come from
    :func:`_span_basis` (orthonormal), so the projector is ``q qᵀ``.
    """
    return v - q @ (q.T @ v)


def extra_peak_absorption(jac: np.ndarray, free_paths: list[str],
                          peak_prefixes: frozenset[str]) -> dict[str, float]:
    """How much of each structural parameter a declared sharp peak could imitate.

    :func:`background_absorption`'s question asked of the *other* member of the
    component seam, and it is a different question with the same statistic: a
    declared peak sitting on a reflection is free to take that reflection's
    intensity, which is the shortcut a caller reaches for when they mean
    "ignore this bit" and declare a component instead of excluding a region.

    Reported and **not thresholded**.  The 0.25 that fires
    ``BACKGROUND_ABSORPTION`` was measured for background blocks — 0.01-0.03 for
    a stiff background against 0.46 for a flexible one — and nothing has
    measured what separates a healthy declared peak from a parasitic one.  A
    threshold copied across would be a number wearing evidence it does not have,
    so this ships as a number a reader judges, and the WP records the separation
    it measured either way (root CLAUDE.md: a new correction ships with a record
    field, never an Rwp comparison).

    ``peak_prefixes`` is the same set :func:`background_absorption` excludes, so
    the two statistics partition the declared components between them rather
    than both claiming some.
    """
    block = [k for k, p in enumerate(free_paths)
             if p.startswith(tuple(peak_prefixes))] if peak_prefixes else []
    if not block:
        return {}
    return block_projection_r2(jac, block, _structural_targets(free_paths))


def block_projection_r2(jac: np.ndarray, block: list[int],
                        targets: list[tuple[int, str]],
                        nuisance: list[int] | None = None) -> dict[str, float]:
    """R²ᵢ of each target column on the span of ``block``, keyed by path.

    The shared core of :func:`background_absorption` and
    :func:`roughness_absorption`: a thin QR of the block gives an orthonormal
    basis, and each target column is projected onto it.  Extracted rather than
    copied because the *statistic* is the reusable idea — "can this group of
    parameters, acting together, imitate that one?" — and a second hand-rolled
    copy would be free to drift from this one's clipping and degenerate-column
    handling.

    ``nuisance`` columns, when given, are projected out of the **whole**
    Jacobian first, making the result a *partial* R²: how much of the target
    the block can still explain once those parameters have taken whatever they
    can.  That matters whenever the nuisance directions are free anyway, and it
    is what makes the roughness number mean something (see
    :func:`roughness_absorption`).

    ``block``, ``nuisance`` and the indices in ``targets`` index columns of
    ``jac``.  A zero-norm target column is skipped rather than reported as 0 or
    1: it carries no information either way.

    **A non-finite column withholds rather than reports.**  One NaN entry
    anywhere in the block poisons the whole QR and every target comes back
    ``nan``; ``nan > threshold`` is ``False``, so the guard goes *silent* on
    the fit most likely to need it and
    ``FitReport.background.worst_absorption`` carries ``nan`` rather than a
    number (measured, WP-1130 — and ``np.any`` does not catch it, NaN being
    truthy).  So a non-finite **block** or **nuisance** column withholds the
    whole table, since the span it was part of is unknowable, and a non-finite
    **target** column is skipped like a zero-norm one.  Absence is a state
    every consumer already handles; ``nan`` is a number that compares
    ``False`` against everything.
    """
    if not block or not targets:
        return {}
    jac = np.asarray(jac)
    if not np.all(np.isfinite(jac[:, block + list(nuisance or ())])):
        return {}
    if nuisance:
        jac = _off_span(_span_basis(jac, nuisance), jac)
    q = _span_basis(jac, block)
    out: dict[str, float] = {}
    for k, path in targets:
        # R² is scale-free, and a column of 1e-170 squares to zero (WP-1463)
        j = _column_in_range(jac[:, k])
        denom = float(j @ j)
        if not (denom > 0.0 and np.isfinite(denom)):
            continue
        resid = _off_span(q, j)
        out[path] = float(np.clip(1.0 - float(resid @ resid) / denom, 0.0, 1.0))
    return out


def one_parameter_gains(jac: np.ndarray, resid: np.ndarray, block: list[int],
                        targets: list[tuple[int | list[int], str]],
                        ) -> dict[str, float]:
    """Predicted Δχ² from freeing each target at the current point, keyed.

    The Rao score test (Rao, 1948, Proc. Camb. Phil. Soc. 44, 50) applied to
    the Gauss-Newton linearisation: with the currently-free columns ``F``
    projected out of both the candidate column and the residual
    (Frisch & Waugh, 1933, Econometrica 1, 387; Lovell, 1963,
    J. Am. Statist. Assoc. 58, 993),

        j̃ = (I − P_F) J_j,   r̃ = (I − P_F) r,
        Δχ²_j = (j̃ᵀ r̃)² / (j̃ᵀ j̃)

    is exactly the drop in Σr² that one linearised solve of ``[F | j]`` would
    achieve over ``F`` alone — the property test asserts that identity against
    an explicit lstsq.  It is scale-invariant (rescaling the column by any
    dp/du cancels), so no per-parameter finite-difference step heuristics are
    needed (contrast Toby, 2024, J. Appl. Cryst. 57, 175, which probes ±δ
    because GSAS-II's analytic derivatives are locked inside Hessian
    assembly), and at a converged minimum jᵀr ≈ 0 makes every gain ≈ 0, so no
    sign-consistency test is needed either.  Under H₀ (the parameter's true
    gain is zero) the statistic is ~χ²₁·χ²_red, which is what makes a noise
    floor of a few times χ²_red meaningful.

    A target's first element may be a *list* of column indices: the joint
    gain ‖P_{span(J̃_G)} r̃‖² of freeing the whole group at once (~χ²_k·χ²_red
    under H₀), computed by least squares so a rank-deficient group — the
    usual reason it *is* a group — never overcounts.

    ``jac`` and ``resid`` are the solver's weighted rows — penalty and
    restraint rows included, for the same reason :func:`background_absorption`
    demands the full layout.  ``block`` indexes the currently-free columns;
    empty means nothing is projected out.  A zero-norm single column is
    skipped rather than scored (no leverage at this state, same convention as
    :func:`block_projection_r2`).  A column absorbed by span(F) *to within
    projection rounding* (‖j̃‖ ≤ √m·ε·‖j‖) scores exactly 0.0: past that
    floor j̃ is noise, and (j̃ᵀr̃)²/(j̃ᵀj̃) on noise returns a number of order
    ‖r̃‖² that looks like a measured gain (measured: 0.19 on a σ ≈ 1 synthetic
    residual, against a true 0).  The floor is fp diagnosis, not policy — the
    caller's absorption gate handles merely ill-separated columns.
    """
    jac = np.asarray(jac)
    r = np.asarray(resid, dtype=np.float64)
    q = _span_basis(jac, block) if block else None
    if q is not None:
        r = _off_span(q, r)
    noise2 = len(jac) * np.finfo(np.float64).eps ** 2

    out: dict[str, float] = {}
    for cols, key in targets:
        if isinstance(cols, (int, np.integer)):
            # the gain is scale-free, and a column of 1e-170 squares to zero
            j = _column_in_range(jac[:, cols])
            raw = float(j @ j)
            if raw <= 0.0:
                continue
            jt = _off_span(q, j) if q is not None else j
            denom = float(jt @ jt)
            if denom <= noise2 * raw:
                out[key] = 0.0
                continue
            num = float(jt @ r)
            out[key] = num * num / denom
        else:
            jg = jac[:, list(cols)]
            # scale-free too: a tiny member squares to zero and would be
            # dropped below as dead (WP-1463)
            s = column_rescale(jg)
            if s is not None:
                jg = jg * s
            raw = np.einsum("ij,ij->j", jg, jg)
            if q is not None:
                jg = _off_span(q, jg)
            proj = np.einsum("ij,ij->j", jg, jg)
            jg = jg[:, proj > noise2 * raw]  # drop absorbed/dead members
            if jg.shape[1] == 0:
                out[key] = 0.0
                continue
            beta, *_ = lapack.lstsq(jg, r, rcond=None)
            fitted = jg @ beta
            out[key] = float(fitted @ fitted)
    return out


def _displacement_like(path: str) -> bool:
    """Displacement freedom a low-angle intensity depression can hide in."""
    return path.endswith(".biso") or ".adp." in path


def _roughness_nuisance(path: str, peak_prefixes: frozenset[str]) -> bool:
    """Directions that are free anyway and would swamp the comparison.

    Roughness is a *multiplicative* correction, so it is trivially "scale-like":
    projected onto a block containing the phase scale it scores R² ≈ 0.95
    whatever the data (measured), which says nothing except that both rescale
    the pattern.  The scale and the background refine in every plan regardless,
    so the question worth asking is what is left of roughness *after* they have
    taken whatever they can — a partial R².

    A **background-landing** extra component is a background direction on the
    same footing (:func:`background_absorption` folds it into the *same* block,
    one function up): a declared hump is background flexibility the caller
    granted, so it is a nuisance to project out here too — three columns per
    hump left in the comparison would swamp the roughness/ADP partial R²
    exactly as the scale does.

    A **peak-landing** one is not (WP-1103).  ``peak_prefixes`` is the same set
    :func:`background_absorption` excludes and :func:`extra_peak_absorption`
    takes, so all three read one partition of the declared components: a
    declared sharp peak is not background flexibility, and projecting its
    columns out here would quietly shrink the very partial R² this guard is
    read from.  Required rather than defaulted, for the reason stated one
    function up.
    """
    return (path.endswith(".scale")
            or path.startswith("instrument.background.")
            or (path.startswith("instrument.extra_components.")
                and not path.startswith(tuple(peak_prefixes))))


def roughness_absorption(jac: np.ndarray, free_paths: list[str],
                         peak_prefixes: frozenset[str]) -> dict[str, float]:
    """Two-way degeneracy between surface roughness and the ADPs (WP-0502).

    Surface roughness depresses low-angle intensity, which is exactly the
    signature an inflated Biso/ADP can reproduce.  Pitschke, Hermann & Mattern
    (1993) Table III is the canonical demonstration of the consequence:
    uncorrected, YBa₂Cu₃O₇ refines to Biso = −1.9 … −2.5 Å², and only the
    correction brings it back to 0.28–0.45 Å².  The degeneracy is real physics,
    so the answer is to *measure* it, not to hide it behind a good-looking Rwp.

    The phase scale and the background are treated as **nuisance** directions
    and projected out of everything first (see :func:`_roughness_nuisance`);
    without that step every number here saturates near 0.96 and the guard is
    blind.  Both remaining directions are reported, because they answer
    different questions:

    * ``instrument.geometry.surface_roughness.*`` keys — how much of the
      roughness column the displacement block can still reproduce.  High ⇒
      *roughness is not identifiable from this data* and whatever it refined to
      is arbitrary.
    * ``…biso`` / ``…adp.k`` keys — how much of that parameter the roughness
      block can reproduce.  High ⇒ *the displacement parameter is hiding in
      roughness*, so its esd understates its true uncertainty.

    Measured on a synthetic large-cell lab pattern with scale, background, both
    Biso and both Suortti parameters free, varying only the low-angle cutoff:

    ======================  =====  =====  =====  =====  =====
    lowest fitted 2θ          7°    15°    20°    30°    45°
    reflections below 40°     20     18     16     10      0
    R²(roughness b)         0.06   0.62   0.91   0.93   0.95
    ======================  =====  =====  =====  =====  =====

    i.e. the statistic tracks the thing that actually determines
    identifiability — how many *reflections* fall in the range where the
    depression has a lever arm — rather than the nominal 2θ limit.

    As for :func:`background_absorption`, pairwise ρ is the wrong statistic (a
    block of many coefficients absorbs collectively while every individual |ρ|
    stays small) and ``jac`` must be the **full** Jacobian including any
    P-spline penalty rows.
    """
    rough = [k for k, p in enumerate(free_paths)
             if p.startswith("instrument.geometry.surface_roughness.")]
    disp = [(k, p) for k, p in enumerate(free_paths) if _displacement_like(p)]
    if not rough or not disp:
        return {}
    nuisance = [k for k, p in enumerate(free_paths)
                if _roughness_nuisance(p, peak_prefixes)]
    out = block_projection_r2(jac, [k for k, _ in disp],
                              [(k, free_paths[k]) for k in rough], nuisance)
    out.update(block_projection_r2(jac, rough, disp, nuisance))
    return out


def compute_statistics(y_obs: np.ndarray, y_calc: np.ndarray, sigma: np.ndarray,
                       n_free: int, y_background: np.ndarray | None = None) -> Statistics:
    y_obs = np.asarray(y_obs, dtype=np.float64)
    y_calc = np.asarray(y_calc, dtype=np.float64)
    w = 1.0 / np.asarray(sigma, dtype=np.float64) ** 2
    n = len(y_obs)
    diff = y_obs - y_calc

    swyo2 = float(w @ (y_obs * y_obs))
    swd2 = float(w @ (diff * diff))
    rp = float(np.abs(diff).sum() / np.abs(y_obs).sum())
    rwp = float(np.sqrt(swd2 / swyo2))
    rexp = float(np.sqrt(max(n - n_free, 1) / swyo2))
    chi2 = swd2 / max(n - n_free, 1)

    rwp_bs = None
    if y_background is not None:
        net = y_obs - y_background
        denom = float(w @ (net * net))
        if denom > 0:
            rwp_bs = float(np.sqrt(swd2 / denom))

    delta = np.sqrt(w) * diff
    dw = float(np.sum(np.diff(delta) ** 2) / np.sum(delta ** 2)) if n > 2 else None

    return Statistics(
        rwp=rwp, rp=rp, rexp=rexp, chi2=chi2, gof=rwp / rexp,
        rwp_background_subtracted=rwp_bs, durbin_watson=dw,
        esd_inflation=berar_lelann_factor(delta) if n > 2 else None,
        n_points=n, n_free_parameters=n_free,
    )


def structure_r_factors(i_obs: np.ndarray, i_calc: np.ndarray,
                        multiplicity: np.ndarray
                        ) -> tuple[float | None, float | None, int]:
    """(R_Bragg, R_F, n) from partitioned integrated intensities.

    McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**,
    36-50, §11:

        R_B = Σ_hkl |I(obs) − I(calc)| / Σ_hkl |I(obs)|            (14)
        R_F = Σ_hkl ||F(obs)| − |F(calc)|| / Σ_hkl |F(obs)|        (13)

    with I_hkl = m·F²_hkl, m the multiplicity — so this takes the intensities
    in exactly those units (see
    :meth:`~rietx.model.forward.CompiledModel.structure_intensity_partition`,
    which produces them) and recovers |F| = √(I/m) per reflection.  The two
    tags they carry in a CIF are ``_refine_ls_R_I_factor`` (the dictionary's
    own definition names it "R_B or R_Bragg") and ``_refine_ls_R_factor_all``.

    Both indices are **biased towards the structural model** — I(obs) is the
    observed pattern partitioned in proportion to I(calc), so a wrong model
    both predicts and receives the intensity it expects.  The paper says so
    where it defines them ("this is, of course, biased towards the structural
    model, but it gives an indication of the reliability of the structure") and
    is equally clear on what they are for: monitoring the *improvement* of a
    structural model, never judging one in isolation.

    Both are also **unweighted** — eq (14) carries no w — which is what makes a
    trace phase's value incomparable with the major phase's: a reflection the
    weighted fit barely constrains counts as much as one that dominates it, and
    a minor phase's windows sit under the major phase's peaks, so the counts the
    major phase failed to describe are handed out too.  Measured on 11-BM NAC
    with its 1.34 wt % CaF₂ (WP-1069, re-measured on the 1.7.0 tree): 0.048
    against 0.377, the whole of the impurity's misfit in four reflections at
    I(obs)/I(calc) of 2.2 to 2.3, every
    one of them under a strong NAC peak.  The weighted variant that answers this
    (Cox & Papoular, 1996, *Mater. Sci. Forum* **228-231**, 233) is not computed
    here.

    Reflections whose intensity could not be partitioned arrive as NaN and are
    dropped; ``n`` reports how many were summed.  Both values are ``None`` when
    no reflection survives or the denominator is zero — a fit with no
    scattering power to compare, not a perfect one.
    """
    i_obs = np.asarray(i_obs, dtype=np.float64)
    i_calc = np.asarray(i_calc, dtype=np.float64)
    mult = np.asarray(multiplicity, dtype=np.float64)
    keep = np.isfinite(i_obs) & np.isfinite(i_calc) & (mult > 0)
    if not np.any(keep):
        return None, None, 0
    io, ic, m = i_obs[keep], i_calc[keep], mult[keep]
    n = int(keep.sum())

    den_b = float(np.abs(io).sum())
    r_b = float(np.abs(io - ic).sum() / den_b) if den_b > 0 else None

    # |F| = √(I/m).  The partition clips the net counts at zero, so I(obs) ≥ 0
    # and the root is always real; I(calc) = m|F|² is non-negative by
    # construction.
    f_obs = np.sqrt(np.maximum(io, 0.0) / m)
    f_calc = np.sqrt(np.maximum(ic, 0.0) / m)
    den_f = float(f_obs.sum())
    r_f = float(np.abs(f_obs - f_calc).sum() / den_f) if den_f > 0 else None
    return r_b, r_f, n


def measured_mask(tt: np.ndarray, position: np.ndarray, fwhm: np.ndarray
                  ) -> np.ndarray:
    """Which peaks the fitted grid actually measured (WP-1071).

    True where a **fitted** channel lies within half the peak's own FWHM of
    its centre.  One criterion answers the two questions the range ends answer
    badly on their own: a peak whose top falls inside an excluded region was
    not observed however far inside ``tt_min``/``tt_max`` it sits (``tt`` is
    the fitted grid, so an excluded region is a hole in it — WP-1033's
    fitted-mask rule one rank down), and a peak just past an edge with half
    its area still on the detector was.

    Half a FWHM is the width at which the *top* of the peak — the part §2
    counts steps across, and the part an integrated intensity is actually
    determined by — is still on the grid.  A non-finite position (a reflection
    off the Ewald sphere) is False, never an error.
    """
    tt = np.asarray(tt, dtype=np.float64)
    pos = np.asarray(position, dtype=np.float64)
    width = np.abs(np.asarray(fwhm, dtype=np.float64))
    valid = np.isfinite(pos) & np.isfinite(width)
    if not len(tt):
        return np.zeros(pos.shape, dtype=bool)
    probe = np.where(valid, pos, tt[0])
    j = np.searchsorted(tt, probe)
    left = tt[np.clip(j - 1, 0, len(tt) - 1)]
    right = tt[np.clip(j, 0, len(tt) - 1)]
    nearest = np.minimum(np.abs(probe - left), np.abs(probe - right))
    return valid & (nearest <= 0.5 * width)


def count_unique_reflections(model: "CompiledModel",
                             values: dict[str, float]) -> int:
    """Unique reflections this pattern measured, summed over phases (WP-1071).

    The observation count of McCusker et al. (1999) §9 — "only the integrated
    intensities of the individual reflections can be considered unique
    observations".  One orbit representative is one reflection
    (``generate_reflections`` merges the Laue orbit already), and a reflection
    counts **once** however many emission lines put a peak on the grid: the
    Kα2 companion is the same reflection measured a second time, not a second
    observation.  It counts if *any* line was measured
    (:func:`measured_mask`) — the ``RefinementResult.ticks`` lesson, since a
    reflection whose Kα1 sits below the first fitted channel can still have
    its Kα2 on the grid.

    Positions and widths come from :meth:`~rietx.model.forward.CompiledModel.phase_peaks`
    at the values given, so this census can never disagree with the profile
    the fit drew.  Evaluate-only: nothing is written and nothing recompiles.

    This is the **raw** count and it over-counts, deliberately: two reflections
    at one 2θ are one observation and both are counted here.
    """
    return len(_reflection_peaks(model, values))


#: The observation/parameter band of McCusker, Von Dreele, Cox, Louër &
#: Scardi (1999) §9: "the observation/parameter ratio should be at least three
#: and preferably five".  Quoted, never tuned — these are the paper's numbers
#: and the only thing this package does with them is say which side of them a
#: fit landed on.
OBS_PER_PARAMETER_MIN = 3.0
OBS_PER_PARAMETER_PREFERRED = 5.0

#: The convergence band of McCusker et al. (1999) §7: a refinement has
#: converged when the maximum shift/esd in the final cycle is ≤ 0.1.  Quoted,
#: never tuned, and it gates nothing — it sets the level of one report
#: sentence, and on a fit that stopped on its iteration budget the measured
#: quantity (``Statistics.max_shift_over_esd``) says *how far* the solve was
#: still moving in esd units.
MAX_SHIFT_CONVERGED = 0.1

#: Half-width of a reflection's interval, in its own FWHMs — Altomare et al.
#: (1995) §2(b), where α = 2 is the default and the paper's own α = 4 check
#: lands 6.5 % lower on average (max 13.3 %), so α = 2 "provides a value of
#: M_ind a little bit larger than the correct value".  Their reason for the
#: smaller value was compute time; ours is that their tabulated M_ind, the only
#: numbers anyone can compare against, were measured at it.
EFFECTIVE_OBS_ALPHA = 2.0


def _reflection_peaks(model: "CompiledModel", values: dict[str, float]):
    """Per measured reflection: its interval, and the peaks inside it.

    One entry per reflection over every phase — ``(lo, hi, [(pos, w1, w2,
    intensity), …])``, the list running over emission lines.  A reflection the
    grid did not measure (:func:`measured_mask`) is left out entirely, so this
    census and :func:`count_unique_reflections` are the same set of
    reflections by construction.

    The interval is Altomare et al. (1995) §2(b), ``2θ_k ± α·FWHM_k``,
    **widened to cover every line**: a Kα doublet's second lobe is part of the
    same reflection's intensity, and an interval around the primary line alone
    would cut it off.  With one emission line this is exactly the paper's
    interval.
    """
    out = []
    alpha = EFFECTIVE_OBS_ALPHA
    for ip in range(len(model.phases)):
        if not len(model.phases[ip].reflections):
            # defensive: a phase with no reflection in the fit range never
            # reaches here today, because ``compile_model`` computes positions
            # for the same empty list and raises first.  Answered rather than
            # propagated, so a census is never the thing that fails.
            continue
        lines = model.phase_peaks(ip, values)
        if model.mag_split(ip):
            # WP-1343: a phase whose magnetic component has its own frozen
            # family carries two images of each reflection at one position,
            # nuclear and magnetic, with their own widths; the component-0
            # peaks alone would give a magnetic-only reflection no intensity.
            # They join as further images, exactly as an emission line does.
            lines = [*lines, *model.phase_peaks(ip, values, component=1)]
        seen: np.ndarray | None = None
        cooked = []
        for pos, w1, w2, intensity in lines:
            pos = np.asarray(pos, dtype=np.float64)
            fwhm = model.peak_fwhm(w1, w2)
            ok = measured_mask(model.tt, pos, fwhm)
            seen = ok if seen is None else (seen | ok)
            cooked.append((pos, np.asarray(w1, dtype=np.float64),
                           np.asarray(w2, dtype=np.float64),
                           np.asarray(intensity, dtype=np.float64), fwhm))
        if seen is None:
            continue
        for k in np.flatnonzero(seen):
            peaks, edges = [], []
            for p, a, b, i, f in cooked:
                if not (np.isfinite(p[k]) and np.isfinite(f[k])):
                    continue
                peaks.append((float(p[k]), float(a[k]), float(b[k]),
                              float(i[k])))
                edges.append((float(p[k]) - alpha * float(f[k]),
                              float(p[k]) + alpha * float(f[k])))
            if not peaks:
                continue
            out.append((min(e[0] for e in edges), max(e[1] for e in edges),
                        peaks))
    return out


def effective_observations(model: "CompiledModel", values: dict[str, float]
                           ) -> float | None:
    """M_ind — Altomare, Cascarano, Giacovazzo, Guagliardi, Moliterni, Burla &
    Polidori (1995), *J. Appl. Cryst.* **28**, 738-744.

    The count of §9 corrected for overlap.  Two reflections at one 2θ are one
    observation; two that partly overlap are somewhere between one and two,
    because the profile shape still says how to split them.  The paper turns
    that into a number per reflection: over its own interval
    (:data:`EFFECTIVE_OBS_ALPHA`), the **fraction of its area on which it is
    the strongest** of the reflections overlapping it,

        M_ind = Σ_k I'_k / I_k ,   I'_k = I_k − ∫_{χ_k} |F_k|²G(Δθ_k) d(2θ),

    where χ_k is the part of k's interval where some overlapping reflection l
    stands higher.  A reflection standing alone contributes 1; the weaker of an
    exactly coincident pair contributes 0, so the pair is one observation — the
    paper's Fig. 1.

    Three things a reader has to know before quoting it:

    * **The paper's own caveat, which McCusker et al. (1999) §9 repeats: this
      "may not have a rigorous basis".**  It is an estimate of how much
      information a pattern holds, not a theorem about it.
    * **An exact tie contributes 2, not 1.**  The comparison is strict, so two
      reflections whose scaled profiles agree to the last bit are each the
      maximum and neither is dominated.  It takes identical multiplicity·|F|²
      as well as identical 2θ, which is why the coincident pairs of a real
      cubic cell — (300)/(221) at multiplicity 6 against 24 — do not hit it.
    * **The integral runs over the fitted channels**, so an excluded region
      removes area from I_k the way it removes a reflection from the count, and
      the shape function is the **symmetric** profile
      (:meth:`~rietx.model.forward.CompiledModel.profile_at`) — the object a
      full-pattern decomposition program reports, and what the paper's G is.
      The FCJ axial convolution is not applied; it moves area within roughly
      the same interval rather than changing which reflection stands higher.

    **One deviation from §2(d), taken on a measurement.**  The paper compares k
    against every reflection whose interval intersects k's, evaluated wherever k
    is; this compares k against the pointwise maximum of the reflections whose
    **own** interval reaches that channel.  A competitor is then dropped in the
    far tail past its own ±α·FWHM, where a pseudo-Voigt is a few per cent of its
    height — so this can only run *high*, and the pairwise form is O(pairs ×
    channels) where this is linear in the channels covered.  Measured across
    eight configurations (LaB6/Cu Kα and a 235-reflection cubic cell, each swept
    over Lorentzian size broadening from none to total): **+0.00 % to +0.74 %**,
    against the estimator's own α = 2 → α = 4 spread of 6.5 % average and 13.3 %
    maximum, which the paper reports for the same quantity.  The cost it buys is
    923 ms → 14 ms on the worst of those eight, and quadratic → linear as the
    pattern gets denser.  The tie semantics survive it exactly: the maximum
    includes k itself, so ``p_k < max`` is true only where *another* reflection
    stands strictly higher.

    ``None`` when no reflection was measured at all.
    """
    return _effective_from_census(model, _reflection_peaks(model, values))


def _effective_from_census(model: "CompiledModel", census) -> float | None:
    """:func:`effective_observations` on a census already taken — so
    :func:`data_support` pays for one pass rather than two."""
    tt = np.asarray(model.tt, dtype=np.float64)
    if not census or not len(tt):
        return None

    profiles: list[tuple[int, int, np.ndarray]] = []
    top = np.full(len(tt), -np.inf)
    for lo, hi, peaks in census:
        i0 = int(np.searchsorted(tt, lo, side="left"))
        i1 = int(np.searchsorted(tt, hi, side="right"))
        if i1 - i0 < 2:
            # fewer than two fitted channels in the interval: no area to
            # integrate, and no basis to call it dominated either
            profiles.append((i0, i1, np.zeros(0)))
            continue
        own = _peak_sum(model, tt[i0:i1], peaks)
        profiles.append((i0, i1, own))
        np.maximum(top[i0:i1], own, out=top[i0:i1])

    total = 0.0
    for i0, i1, own in profiles:
        if len(own) < 2:
            total += 1.0
            continue
        x = tt[i0:i1]
        area = float(np.trapezoid(own, x))
        if area <= 0.0:
            total += 1.0
            continue
        dominated = np.where(own < top[i0:i1], own, 0.0)
        total += 1.0 - float(np.trapezoid(dominated, x)) / area
    return float(total)


def _peak_sum(model: "CompiledModel", x: np.ndarray, peaks) -> np.ndarray:
    """One reflection's own profile on ``x`` — every emission line summed.

    The lines are summed because they are one reflection: the Kα2 lobe is the
    same |F|² measured again, and it competes with a neighbour's Kα1 exactly as
    the primary lobe does.
    """
    out = np.zeros(x.shape, dtype=np.float64)
    for pos, w1, w2, intensity in peaks:
        out = out + intensity * np.asarray(
            model.profile_at(x - pos, w1, w2), dtype=np.float64)
    return out


def structural_free_paths(table: "ParameterTable") -> list[str]:
    """The free columns McCusker §9's count is about: each one that moves an atom.

    McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**,
    36-50, §9, count the structural parameters, the ones the integrated
    intensities pay for.  A column is one when it **is** an atom entry or
    **reaches** one, whatever its own name (WP-2067, issue #1250): a mode
    amplitude (``…distortion_modes.modes.K.amplitude``) reaches x, y, z through
    affine rows of C; a named variable ``vars.X`` reaches the coordinate DOF or
    Biso it is tied to, which is then not free itself; a rigid body's origin,
    rotation and twists reach its atoms through the derived block that writes
    them.  A test on the free path's *name* saw none of the three — the rule
    "a freeze resting on flatness needs the other reading of C" (WP-1342)
    applied to a count.

    The reach is :meth:`~rietx.params.vector.ParameterTable.column_reach`, one
    read of the constraint map that already carries each derived row's
    declared reach.  What that read cannot say is *which input* of a block
    carried it, and a block's :attr:`~rietx.params.derived.DerivedBlock.
    frame_inputs` are the exception: a body reads its phase's cell only to
    turn Å into fractions, so through C the cell reaches every body atom, while
    §9 excludes it because peak positions pay for it.  So an atom row a block
    writes is not tested directly; a column reaches it through the block's
    other inputs instead, each counted where the block's
    :meth:`~rietx.params.derived.DerivedBlock.reach_pattern` says it moves an
    atom.  Blocks are walked last to first, since a later block may read an
    earlier one's output (a rider on a body atom).

    **A superset of the name test**: every free atom entry reaches itself, so a
    fit with no tie onto an atom, no variable and no block counts exactly what
    the glob counted.  In :attr:`~rietx.params.vector.ParameterTable.
    free_paths` order.
    """
    written = table.derived_paths()
    moves_atom = {e.path for e in table.entries
                  if fnmatch.fnmatch(e.path, STRUCTURAL_PARAMETER_GLOB)
                  and e.path not in written}
    for block in reversed(table.derived):
        pattern = np.asarray(block.reach_pattern(), dtype=bool)
        frame = set(block.frame_inputs)
        out_moves = np.array(
            [q in moves_atom or fnmatch.fnmatch(q, STRUCTURAL_PARAMETER_GLOB)
             for q in block.outputs], dtype=bool)
        for k, q in enumerate(block.inputs):
            if q not in frame and bool((pattern[:, k] & out_moves).any()):
                moves_atom.add(q)
    reach = table.column_reach()
    return [p for p in table.free_paths
            if any(q in moves_atom for q in reach[p])]


def data_support(model: "CompiledModel", values: dict[str, float],
                 table: "ParameterTable") -> DataSupport:
    """Assemble :class:`~rietx.schemas.results.DataSupport` for a finished fit.

    Evidence, not a gate: nothing here refuses anything, and the band it is
    read against (three, preferably five — McCusker et al. 1999 §9) lives in
    the report rather than in this function.  The structural count is
    :func:`structural_free_paths` of ``table``, the fit's own table, since
    what a column moves is a fact about the constraint map and not about its
    name (WP-2067).
    """
    census = _reflection_peaks(model, values)
    n_refl = len(census)
    m_ind = _effective_from_census(model, census)
    n_struct = len(structural_free_paths(table))
    return DataSupport(
        n_unique_reflections=n_refl,
        n_effective_observations=m_ind,
        n_structural_parameters=n_struct,
        observations_per_parameter=(float(n_refl / n_struct) if n_struct
                                    else None),
        effective_observations_per_parameter=(
            float(m_ind / n_struct) if (n_struct and m_ind is not None)
            else None),
    )
