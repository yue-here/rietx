"""The joint Jacobian kept in blocks, never assembled dense (WP-1325).

A joint fit stacks N histograms' residuals over one free vector θ whose
columns are of two kinds (``MultiParameterTable._rebuild_columns``): the
**shared** ones every histogram's rows reach, and each histogram's **own**,
which no other histogram's rows reach.  So the stacked Jacobian is zero
wherever one histogram's rows meet another histogram's own columns, and its
normal matrix is block-diagonal with a border: the "arrow" of bundle
adjustment (Triggs, B., McLauchlan, P. F., Hartley, R. I. & Fitzgibbon, A. W.
(2000). Bundle adjustment — a modern synthesis. *Vision Algorithms: Theory and
Practice*, LNCS **1883**, 298-372, §6.1).  Assembled dense, the Jacobian of a
3 000-point library with 20 shared and ten own columns a pattern is 1.2 GB at
70 patterns and 22 GB at 300, where its blocks are 50 MB and 216 MB.

:class:`BlockJacobian` holds each histogram's weighted rows against its own
free columns only.  Its consumers read it three ways:

* **the step** (:mod:`.lm`): A = JᵀJ and b = −Jᵀr scattered block by block
  into a dense n × n A, after which the driver is unchanged — BVLS up to
  :data:`.lm.BVLS_MAX_COLUMNS`, projected CG above, which holds the box.  That
  is the WP's route (i).  Its step solve was 4 % of a 300-pattern fit's wall
  clock (1.7-1.9 s of 48 s), so route (ii), eliminating each histogram's own
  block from the step, would buy nothing measurable;
* **the covariance** (:func:`normal_factors`): the Schur complement of the
  equilibrated arrow, never a pseudo-inverse of the whole n × n matrix.  It
  comes back n × n all the same, since every reader of a joint covariance
  indexes it by θ's columns, and the blocks between two histograms' own
  columns cost one product of rank n_border;
* **everything else that read the final Jacobian** — the residual cosine,
  the column norms, the per-histogram slices a joint result reads, the
  discarded-direction guard and the moment-angle test's refit — per block.

So what the blocked path keeps dense is n × n, never rows × n: A, and the
covariance and correlation.  Each costs 8n² bytes (72 MB at n = 3 004), and a
300-pattern fit peaked at 0.78 GiB over its library, about eleven of them.  On
a 15.7 GiB machine these set the next limit, near n ≈ 1.4·10⁴ (≈ 1 400
patterns of ten own columns; extrapolated, not run).

Which layout a joint solve takes is :func:`choose_layout`'s: dense below
:data:`DENSE_JACOBIAN_MAX_BYTES`, so every joint fit that predates the blocked
path keeps its bits, and blocked above it; :func:`set_layout` forces either,
the seam tests and benchmarks run each side through.

**Where the blocked numbers differ from the dense ones.**  Every sum over rows
is taken per histogram and then across histograms, where the dense product
sums all rows in BLAS's order, so A, b, the column norms and the residual
cosine agree with the dense path to rounding, not to the bit.  The covariance
is exact algebra too (the inverse of a nonsingular arrow *is* its Schur form),
but its pseudo-inverse cut is applied per block — to each histogram's own
equilibrated block and to the Schur complement, at :data:`.statistics.PINV_RCOND`
of the whole matrix's largest eigenvalue — rather than to the eigenvalues of
the whole matrix, which the arrow never forms.  The two agree wherever no
direction sits near the cut (to 4e-12 on the esds of a 20-pattern library);
near it, the two can discard different directions.
"""

from __future__ import annotations

import warnings

import numpy as np

from ..backend.linalg64 import require_fp64, to_host_fp64
from . import lapack
from .statistics import COLUMN_SAFE_EXPONENT, PINV_RCOND

#: Size of the dense joint Jacobian, in bytes (8 per entry), above which
#: :func:`~.least_squares.run_multi_least_squares` keeps it in blocks.  Below
#: it the dense path runs, which is what every joint golden was measured on,
#: and so stays bit-identical.  It is not where the blocks start to pay: they
#: were already 1.7× faster at ten patterns, and 6.1× at 70
#: (``docs/wp/1325-measure/scaling_results.txt``).  It is a
#: margin over every joint fit that predates them: the largest the fast suite
#: runs is 3.6 MiB (279 solves in 22 files, measured), and the slow suite's
#: ten-pattern ramp is 16 MB.  A 3 000-point library with four shared and ten
#: own columns a pattern crosses it at 34 patterns, where forming JᵀJ dense
#: costs 2.4e10 flops an iteration against the blocks' 4e7.
DENSE_JACOBIAN_MAX_BYTES = 256 * 2**20

#: The two layouts a joint solve can take, the vocabulary of
#: :attr:`~.least_squares.LSQOutcome.jacobian_layout`.
LAYOUTS = ("dense", "blocked")

_FORCED: str | None = None


def set_layout(layout: str | None) -> str | None:
    """Force every joint solve in this process onto ``"dense"`` or
    ``"blocked"``; ``None`` restores the size rule (:func:`choose_layout`).
    Returns the previous setting, so a caller can restore it — the
    ``compiled.set_enabled`` seam, for the tests and the scaling measurement.
    """
    global _FORCED
    if layout is not None and layout not in LAYOUTS:
        raise ValueError(f"unknown Jacobian layout {layout!r}; "
                         f"available: {', '.join(LAYOUTS)}, or None for the size rule")
    was, _FORCED = _FORCED, layout
    return was


def dense_jacobian_bytes(n_rows: int, n_cols: int) -> int:
    """Bytes the stacked joint Jacobian takes assembled dense, fp64."""
    return 8 * int(n_rows) * int(n_cols)


def choose_layout(n_rows: int, n_cols: int, solver: str) -> str:
    """``"dense"`` or ``"blocked"`` for a joint solve of this size.

    Forced by :func:`set_layout` when set, else blocked exactly when the dense
    Jacobian would exceed :data:`DENSE_JACOBIAN_MAX_BYTES`.  Only the ``lm``
    driver takes a :class:`BlockJacobian`: scipy's TRF factorises the dense
    matrix itself.  So a forced ``"blocked"`` under TRF is refused, and a
    size that would choose it falls back to dense with a warning naming what
    that costs, which is the behaviour every TRF joint fit had before.
    """
    if _FORCED is not None:
        if _FORCED == "blocked" and solver != "lm":
            raise ValueError(
                f"the blocked joint Jacobian is solved only by solver='lm'; "
                f"solver={solver!r} factorises the dense matrix itself. Use "
                "solver='lm', or set_layout(None) for the size rule")
        return _FORCED
    size = dense_jacobian_bytes(n_rows, n_cols)
    if size <= DENSE_JACOBIAN_MAX_BYTES:
        return "dense"
    if solver != "lm":
        warnings.warn(
            f"this joint fit's Jacobian is {size / 2**30:.2f} GiB assembled dense "
            f"({n_rows} rows x {n_cols} columns), past the "
            f"{DENSE_JACOBIAN_MAX_BYTES / 2**20:.0f} MiB at which solver='lm' keeps "
            f"it in blocks; solver={solver!r} has no blocked path, so it is "
            "assembled dense", RuntimeWarning, stacklevel=3)
        return "dense"
    return "blocked"


class BlockJacobian:
    """The stacked joint Jacobian as one block per histogram.

    ``blocks[h]`` is histogram ``h``'s weighted rows — its data rows, then its
    background-penalty rows — against its own free columns, in its table's
    free order; ``col_maps[h]`` sends those columns to θ's
    (``MultiParameterTable.col_map``).  The row space is the dense stacked
    layout's: every histogram's data rows first, then every histogram's
    penalty rows, so :meth:`toarray` is ``_multi_closures``' dense matrix
    entry for entry and a residual vector indexes both alike.
    """

    __slots__ = ("blocks", "col_maps", "n_data", "n_pen", "n_cols",
                 "_data_off", "_pen_off")

    def __init__(self, blocks, col_maps, n_data, n_pen, n_cols: int):
        self.blocks = [to_host_fp64(b) for b in blocks]
        self.col_maps = [np.asarray(c, dtype=np.int64) for c in col_maps]
        self.n_data = [int(n) for n in n_data]
        self.n_pen = [int(n) for n in n_pen]
        self.n_cols = int(n_cols)
        for b, c, nd, npen in zip(self.blocks, self.col_maps, self.n_data, self.n_pen,
                                  strict=True):
            if b.shape != (nd + npen, len(c)):
                raise ValueError(f"a block of shape {b.shape} does not hold "
                                 f"{nd}+{npen} rows against {len(c)} columns")
        self._data_off = np.concatenate([[0], np.cumsum(self.n_data)]).astype(np.int64)
        self._pen_off = (int(self._data_off[-1])
                         + np.concatenate([[0], np.cumsum(self.n_pen)]).astype(np.int64))

    # -- shape and the dense twin -------------------------------------------
    @property
    def shape(self) -> tuple[int, int]:
        return int(self._pen_off[-1]), self.n_cols

    @property
    def n_blocks(self) -> int:
        return len(self.blocks)

    def toarray(self) -> np.ndarray:
        """The dense stacked matrix, entry for entry ``_multi_closures``'."""
        out = np.zeros(self.shape, dtype=np.float64)
        for h, (b, cm) in enumerate(zip(self.blocks, self.col_maps, strict=True)):
            do, nd = int(self._data_off[h]), self.n_data[h]
            out[do:do + nd, cm] = b[:nd]
            if self.n_pen[h]:
                po = int(self._pen_off[h])
                out[po:po + self.n_pen[h], cm] = b[nd:]
        return out

    def residual_part(self, r: np.ndarray, h: int) -> np.ndarray:
        """``r``'s rows for histogram ``h``, aligned with ``blocks[h]``."""
        do, nd = int(self._data_off[h]), self.n_data[h]
        if not self.n_pen[h]:
            return r[do:do + nd]
        po = int(self._pen_off[h])
        return np.concatenate([r[do:do + nd], r[po:po + self.n_pen[h]]])

    def block(self, h: int, *, data_only: bool = True) -> np.ndarray:
        """Histogram ``h``'s rows against its own columns (``col_maps[h]``
        order): the dense ``J[rows_h][:, col_map(h)]``, bit for bit."""
        b = self.blocks[h]
        return b[:self.n_data[h]] if data_only else b

    def data_rows(self) -> "BlockJacobian":
        """The data rows alone, the penalty rows dropped (``LSQOutcome.jac``)."""
        return BlockJacobian([b[:nd] for b, nd in zip(self.blocks, self.n_data, strict=True)],
                             self.col_maps, self.n_data, [0] * self.n_blocks, self.n_cols)

    # -- products -----------------------------------------------------------
    def rmatvec(self, r: np.ndarray) -> np.ndarray:
        """``Jᵀr``, summed block by block."""
        out = np.zeros(self.n_cols, dtype=np.float64)
        for h, (b, cm) in enumerate(zip(self.blocks, self.col_maps, strict=True)):
            out[cm] += b.T @ self.residual_part(r, h)
        return out

    def normal_equations(self, r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """``(A, b) = (JᵀJ, −Jᵀr)``, scattered block by block into a dense
        n × n A — :mod:`.lm`'s two quantities, formed as its dense path forms
        them (no column rescale: the driver's A is the plain product)."""
        require_fp64(r, "least-squares residual")
        A = np.zeros((self.n_cols, self.n_cols), dtype=np.float64)
        g = np.zeros(self.n_cols, dtype=np.float64)
        for h, (b, cm) in enumerate(zip(self.blocks, self.col_maps, strict=True)):
            A[np.ix_(cm, cm)] += b.T @ b
            g[cm] += b.T @ self.residual_part(r, h)
        return A, -g

    # -- columns ------------------------------------------------------------
    def column_max_abs(self) -> np.ndarray:
        """Each column's largest |entry| over every block, 0 for none."""
        m = np.zeros(self.n_cols, dtype=np.float64)
        for b, cm in zip(self.blocks, self.col_maps, strict=True):
            if b.shape[0]:
                m[cm] = np.maximum(m[cm], np.maximum(np.max(b, axis=0), -np.min(b, axis=0)))
        return m

    def column_sumsq(self, s: np.ndarray | None = None) -> np.ndarray:
        """Σ rows of (J·s)² per column, accumulated block by block."""
        out = np.zeros(self.n_cols, dtype=np.float64)
        for b, cm in zip(self.blocks, self.col_maps, strict=True):
            bs = b if s is None else b * s[cm]
            out[cm] += np.einsum("ij,ij->j", bs, bs)
        return out

    def scaled_columns(self, factors: np.ndarray) -> "BlockJacobian":
        """``J · diag(factors)``: a chart's sign flip (``rechart_outcome``)."""
        f = np.asarray(factors, dtype=np.float64)
        return BlockJacobian([b * f[cm] for b, cm in zip(self.blocks, self.col_maps,
                                                         strict=True)],
                             self.col_maps, self.n_data, self.n_pen, self.n_cols)

    def without_columns(self, columns) -> "BlockJacobian":
        """``J`` with ``columns`` zeroed in every block (``_without_columns``)."""
        cols = np.zeros(self.n_cols, dtype=bool)
        cols[list(columns)] = True
        blocks = []
        for b, cm in zip(self.blocks, self.col_maps, strict=True):
            hit = cols[cm]
            if hit.any():
                b = b.copy()
                b[:, hit] = 0.0
            blocks.append(b)
        return BlockJacobian(blocks, self.col_maps, self.n_data, self.n_pen, self.n_cols)

    def matmul_chart(self, t: np.ndarray) -> "BlockJacobian":
        """``J @ T`` for a square chart matrix that keeps each histogram's
        columns among themselves (a rigid body's rotation composed into its
        anchor, ``rechart_outcome``).  A ``T`` mixing one histogram's columns
        into another's has no block form, and is refused rather than cut."""
        t = np.asarray(t, dtype=np.float64)
        blocks = []
        for b, cm in zip(self.blocks, self.col_maps, strict=True):
            outside = np.ones(self.n_cols, dtype=bool)
            outside[cm] = False
            if np.any(t[np.ix_(cm, outside)]):
                raise ValueError("a chart matrix moving one histogram's columns into "
                                 "another's has no block form")
            blocks.append(b @ t[np.ix_(cm, cm)])
        return BlockJacobian(blocks, self.col_maps, self.n_data, self.n_pen, self.n_cols)

    def border(self) -> np.ndarray:
        """Columns more than one block reaches: the arrow's border, the shared
        columns of ``MultiParameterTable`` (every other column is one block's
        own, which no other block's rows reach)."""
        counts = np.bincount(np.concatenate(self.col_maps) if self.col_maps
                             else np.zeros(0, dtype=np.int64), minlength=self.n_cols)
        return counts > 1


# -- the column rescale and norms, on blocks ---------------------------------

def column_rescale(bj: BlockJacobian) -> np.ndarray | None:
    """:func:`.statistics.column_rescale` on blocks: the same factors from
    the same per-column largest |entry|, which the zero rows of other
    histograms cannot change."""
    if bj.shape[0] == 0:
        return None
    m = bj.column_max_abs()
    _, e = np.frexp(m)
    far = (m > 0.0) & (np.abs(e) > COLUMN_SAFE_EXPONENT)
    if not far.any():
        return None
    s = np.ones(len(m), dtype=np.float64)
    s[far] = np.ldexp(1.0, np.clip(-e[far], -1023, 1023))
    return s


def column_norms(bj: BlockJacobian) -> np.ndarray:
    """:func:`.statistics.column_norms` on blocks, rescale included."""
    s = column_rescale(bj)
    if s is None:
        return np.sqrt(bj.column_sumsq())
    return np.sqrt(bj.column_sumsq(s)) / s


# -- the equilibrated arrow and its Schur form -------------------------------

#: live columns up to which :meth:`_Arrow.largest_eigenvalue` assembles E and
#: takes every eigenvalue; Lanczos above, which took 1-8 ms at 100-700
#: columns where the dense eigensolve took 0.01-0.5 s (Linux x86_64, loaded)
_DENSE_EIGEN_MAX = 64


class _Arrow:
    """The equilibrated normal matrix E = D⁻¹(SJ)ᵀ(SJ)D⁻¹ in arrow form.

    ``S`` is :func:`column_rescale`'s exact power-of-two factor, ``D`` the
    column norms after it, so ``inv_d`` is 0 on a gradient-free column and
    such a column is in no block (``normal_factors``' "dead" columns).
    ``b_idx`` are the live border columns (θ's indices), ``p_idx[h]`` block
    ``h``'s live own columns; ``e_bb``, ``e_bp[h]`` and ``e_pp[h]`` the blocks
    of E between them.
    """

    def __init__(self, bj: BlockJacobian):
        s = column_rescale(bj)
        blocks = bj.blocks if s is None else [b * s[cm] for b, cm in
                                              zip(bj.blocks, bj.col_maps, strict=True)]
        n = bj.n_cols
        grams = [b.T @ b for b in blocks]
        diag = np.zeros(n, dtype=np.float64)
        for g, cm in zip(grams, bj.col_maps, strict=True):
            diag[cm] += np.diag(g)
        d = np.sqrt(diag)
        live = d > 0.0
        inv_d = np.where(live, 1.0 / np.where(live, d, 1.0), 0.0)
        reached = bj.border()
        border = reached & live
        self.n = n
        self.live = live
        self.inv_d_eq = inv_d                    # the equilibration, before S
        self.s = s
        self.b_idx = np.flatnonzero(border)
        pos_b = np.full(n, -1, dtype=np.int64)
        pos_b[self.b_idx] = np.arange(len(self.b_idx))
        nb = len(self.b_idx)
        h_bb = np.zeros((nb, nb), dtype=np.float64)
        self.p_idx: list[np.ndarray] = []
        self.e_bp: list[np.ndarray] = []
        self.e_pp: list[np.ndarray] = []
        for g, cm in zip(grams, bj.col_maps, strict=True):
            on_b = border[cm]
            own = live[cm] & ~reached[cm]
            lb, lp = np.flatnonzero(on_b), np.flatnonzero(own)
            gb, gp = cm[lb], cm[lp]
            if len(lb):
                h_bb[np.ix_(pos_b[gb], pos_b[gb])] += g[np.ix_(lb, lb)]
            e_bp = np.zeros((nb, len(lp)), dtype=np.float64)
            if len(lb) and len(lp):
                e_bp[pos_b[gb]] = g[np.ix_(lb, lp)] * np.outer(inv_d[gb], inv_d[gp])
            e_pp = g[np.ix_(lp, lp)] * np.outer(inv_d[gp], inv_d[gp])
            self.p_idx.append(gp)
            self.e_bp.append(e_bp)
            self.e_pp.append(0.5 * (e_pp + e_pp.T))
        e_bb = h_bb * np.outer(inv_d[self.b_idx], inv_d[self.b_idx])
        self.e_bb = 0.5 * (e_bb + e_bb.T)

    def matvec(self, v: np.ndarray) -> np.ndarray:
        """``E·v`` over the live columns, ordered [border, own₀, own₁, …]."""
        nb = len(self.b_idx)
        vb = v[:nb]
        out_b = self.e_bb @ vb
        parts = [out_b]
        k = nb
        for e_bp, e_pp in zip(self.e_bp, self.e_pp, strict=True):
            m = e_pp.shape[0]
            vp = v[k:k + m]
            out_b += e_bp @ vp
            parts.append(e_bp.T @ vb + e_pp @ vp)
            k += m
        return np.concatenate(parts)

    def order(self) -> np.ndarray:
        """θ's indices of the live columns, in :meth:`matvec`'s order."""
        return np.concatenate([self.b_idx, *self.p_idx]).astype(np.int64)

    def dense(self) -> np.ndarray:
        """E over the live columns, assembled, in :meth:`matvec`'s order."""
        m = len(self.order())
        out = np.zeros((m, m), dtype=np.float64)
        nb = len(self.b_idx)
        out[:nb, :nb] = self.e_bb
        k = nb
        for e_bp, e_pp in zip(self.e_bp, self.e_pp, strict=True):
            p = e_pp.shape[0]
            out[:nb, k:k + p] = e_bp
            out[k:k + p, :nb] = e_bp.T
            out[k:k + p, k:k + p] = e_pp
            k += p
        return out

    def largest_eigenvalue(self) -> float:
        """|λ|max of E, what :data:`.statistics.PINV_RCOND` is a fraction of.

        Dense up to :data:`_DENSE_EIGEN_MAX` live columns; above, Lanczos on
        :meth:`matvec` (ARPACK, from a fixed start so the bits repeat), to
        1e-6 relative, since it only places the cut."""
        m = len(self.order())
        if m == 0:
            return 0.0
        if m <= _DENSE_EIGEN_MAX:
            return float(np.abs(lapack.eigvalsh(self.dense())).max())
        from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigsh

        op = LinearOperator((m, m), matvec=self.matvec, dtype=np.float64)
        try:
            lam = eigsh(op, k=1, which="LM", v0=np.ones(m), tol=1e-6,
                        return_eigenvectors=False)
        except ArpackNoConvergence:
            # the dense eigensolve this method exists to avoid, rather than a
            # cut placed on a guess
            return float(np.abs(lapack.eigvalsh(self.dense())).max())
        return float(np.abs(lam).max())


class _Schur:
    """The pseudo-inverse of an :class:`_Arrow` through its Schur complement.

    Each own block is inverted on its own, Y_h = E_pp⁺·E_pb, and the border's
    complement S = E_bb − Σ E_bp·Y_h with it.  Then the full inverse is

        Σ_bb = S⁺,   Σ_pb = −Y_h·S⁺,   Σ_pp = E_pp⁺ + Y_h·S⁺·Y_kᵀ,

    the last carrying E_pp⁺ on its diagonal blocks only (the item's
    Σ_LL = H_LL⁻¹ + H_LL⁻¹·H_LG·S⁻¹·H_GL·H_LL⁻¹).  Every pseudo-inverse is
    :func:`.statistics._psd_pinv`'s: an eigenvalue at or under ``cut`` is
    discarded, a kept one inverted by its magnitude.  The discarded
    directions are kept for :func:`discarded_directions`.
    """

    def __init__(self, arrow: _Arrow, cut: float):
        self.arrow = arrow
        self.cut = cut
        self.pp_inv: list[np.ndarray] = []
        self.pp_gone: list[np.ndarray] = []
        self.y: list[np.ndarray] = []
        s = arrow.e_bb.copy()
        for e_bp, e_pp in zip(arrow.e_bp, arrow.e_pp, strict=True):
            inv, gone = _cut_pinv(e_pp, cut)
            self.pp_inv.append(inv)
            self.pp_gone.append(gone)
            y = inv @ e_bp.T
            self.y.append(y)
            s -= e_bp @ y
        s = 0.5 * (s + s.T)
        self.s_inv, self.s_gone = _cut_pinv(s, cut)

    def w(self) -> np.ndarray:
        """W = [I; −Y₀; −Y₁; …], so that the inverse is W·S⁺·Wᵀ plus the own
        blocks' E_pp⁺ on the diagonal, in :meth:`_Arrow.order`."""
        nb = len(self.arrow.b_idx)
        return np.vstack([np.eye(nb), *[-y for y in self.y]])

    def inverse(self) -> np.ndarray:
        """The full pseudo-inverse over the live columns, in
        :meth:`_Arrow.order` (dense; n² memory, n²·n_border flops)."""
        w = self.w()
        k = w @ self.s_inv @ w.T
        at = len(self.arrow.b_idx)
        for inv in self.pp_inv:
            m = inv.shape[0]
            k[at:at + m, at:at + m] += inv
            at += m
        return 0.5 * (k + k.T)

    def inverse_diagonal(self) -> np.ndarray:
        """The diagonal of :meth:`inverse`, without forming it."""
        w = self.w()
        diag = np.einsum("ij,jk,ik->i", w, self.s_inv, w)
        at = len(self.arrow.b_idx)
        for inv in self.pp_inv:
            m = inv.shape[0]
            diag[at:at + m] += np.diag(inv)
            at += m
        return diag


def _cut_pinv(a: np.ndarray, cut: float) -> tuple[np.ndarray, np.ndarray]:
    """``(pinv, gone)``: :func:`.statistics._psd_pinv` with an absolute cut,
    and the eigenvectors it discarded (columns)."""
    if a.size == 0:
        return np.zeros_like(a), np.zeros((a.shape[0], 0))
    lam, u = lapack.eigh(a)
    mag = np.abs(lam)
    keep = mag > cut
    inv = (u[:, keep] / mag[keep]) @ u[:, keep].T
    return 0.5 * (inv + inv.T), u[:, ~keep]


def _schur(bj: BlockJacobian) -> _Schur:
    arrow = _Arrow(bj)
    return _Schur(arrow, PINV_RCOND * arrow.largest_eigenvalue())


def normal_factors(bj: BlockJacobian, resid: np.ndarray, n_free: int, *,
                   chi2_floor: bool = False,
                   what: str = "residual entering the covariance solve",
                   ) -> tuple[np.ndarray, np.ndarray, float]:
    """:func:`.statistics.normal_factors` for a :class:`BlockJacobian`.

    The same contract — ``Cov = K · outer(1/d, 1/d)``, ``1/d`` = 0 on a
    gradient-free column, ``chi2_red`` the raw Σr²/(N−P) — and the same
    equilibration first (Jacobi scaling, van der Sluis 1969), but K is the
    Schur form of :class:`_Schur` rather than one pseudo-inverse of the whole
    matrix.  K comes back dense, n × n, since every consumer of a joint
    covariance indexes it by θ's columns; its cost is the border's,
    n²·n_border, never n³.
    """
    require_fp64(resid, what)
    chi2_red = float(resid @ resid) / max(len(resid) - n_free, 1)
    scale = max(chi2_red, 1.0) if chi2_floor else chi2_red
    sch = _schur(bj)
    arrow = sch.arrow
    order = arrow.order()
    k = np.zeros((bj.n_cols, bj.n_cols), dtype=np.float64)
    k[np.ix_(order, order)] = sch.inverse() * scale
    inv_d = arrow.inv_d_eq
    if arrow.s is not None:
        inv_d = inv_d * arrow.s
    return k, inv_d, chi2_red


def discarded_directions(bj: BlockJacobian) -> tuple[int, np.ndarray]:
    """:func:`.statistics.discarded_directions` for a :class:`BlockJacobian`.

    The directions are the ones the blocked covariance discards: an own
    block's eigenvectors under the cut, which reach that block's columns, and
    the Schur complement's, which reach the border directly and each own
    block's columns through −Y_h.  Touched is the dense test, read on that
    inverse: column i is touched when Σ_gone wᵢ²/cut is at least the variance
    the blocked solve reports for it.
    """
    none = (0, np.zeros(0, dtype=np.intp))
    sch = _schur(bj)
    arrow = sch.arrow
    if int(arrow.live.sum()) < 2 or sch.cut <= 0.0:
        return none
    n_gone = int(sch.s_gone.shape[1]) + sum(int(g.shape[1]) for g in sch.pp_gone)
    if n_gone < 1:
        return none
    kept = sch.inverse_diagonal()
    nb = len(arrow.b_idx)
    lost_parts = [(sch.s_gone ** 2).sum(axis=1)]
    for y, gone in zip(sch.y, sch.pp_gone, strict=True):
        through = (-y @ sch.s_gone) if nb else np.zeros((y.shape[0], 0))
        lost_parts.append((through ** 2).sum(axis=1) + (gone ** 2).sum(axis=1))
    lost = np.concatenate(lost_parts) / sch.cut
    order = arrow.order()
    touched = np.sort(order[lost >= kept])
    return (n_gone, touched) if len(touched) >= 1 else none


def refitted_increase(bj: BlockJacobian, angles: list[int], r_stop: np.ndarray,
                      r_point: np.ndarray) -> float:
    """``least_squares._refitted_increase`` for a data-rows :class:`BlockJacobian`.

    min_β ‖r + J_o β‖² for the two right-hand sides, J_o the columns other than
    ``angles`` scaled to unit norm, as the dense function solves it, but by
    elimination: each block's own columns are projected out of its rows (an
    SVD of that block, numpy ``lstsq``'s cut), and the border's least squares
    is solved on the stacked projected rows.  That is the same minimum —
    the own columns of one block reach no other block's rows — without the
    dense matrix.
    """
    rhs = np.column_stack([r_stop, r_point]).astype(np.float64)
    others = np.ones(bj.n_cols, dtype=bool)
    others[list(angles)] = False
    d = column_norms(bj)
    live = others & np.isfinite(d) & (d > 0.0)
    if live.any():
        reached = bj.border()
        border = reached & live
        b_idx = np.flatnonzero(border)
        pos_b = np.full(bj.n_cols, -1, dtype=np.int64)
        pos_b[b_idx] = np.arange(len(b_idx))
        eps = float(np.finfo(np.float64).eps)
        g_parts, r_parts = [], []
        for h, (b, cm) in enumerate(zip(bj.blocks, bj.col_maps, strict=True)):
            rows = slice(int(bj._data_off[h]), int(bj._data_off[h]) + bj.n_data[h])
            jb = b[:bj.n_data[h]]
            rh = rhs[rows]
            on_b = np.flatnonzero(border[cm])
            own = np.flatnonzero(live[cm] & ~reached[cm])
            g = np.zeros((jb.shape[0], len(b_idx)), dtype=np.float64)
            if len(on_b):
                g[:, pos_b[cm[on_b]]] = jb[:, on_b] / d[cm[on_b]]
            if len(own) and jb.shape[0]:
                p = jb[:, own] / d[cm[own]]
                u, sv, _ = lapack.svd(p, full_matrices=False)
                u = u[:, sv > eps * max(p.shape) * sv[0]]
                g = g - u @ (u.T @ g)
                rh = rh - u @ (u.T @ rh)
            g_parts.append(g)
            r_parts.append(rh)
        rhs = np.vstack(r_parts) if r_parts else rhs
        if len(b_idx):
            gs = np.vstack(g_parts)
            rhs = rhs - gs @ lapack.lstsq(gs, rhs, rcond=None)[0]
    return float(rhs[:, 1] @ rhs[:, 1] - rhs[:, 0] @ rhs[:, 0])


def _projection(bj: BlockJacobian, resid: np.ndarray) -> tuple[float, int]:
    """``(q, kept)`` for the linear least-squares step from here.

    q = g̃ᵀ·E⁺·g̃ is how much χ² that step removes, with g̃ = J̃ᵀr on the
    equilibrated columns J̃ = J·S·D⁻¹ and E⁺ :class:`_Schur`'s pseudo-inverse,
    cut where the covariance cuts.  ``kept`` counts the directions past the
    cut.
    """
    sch = _schur(bj)
    arrow = sch.arrow
    factor = arrow.inv_d_eq if arrow.s is None else arrow.inv_d_eq * arrow.s
    g = bj.rmatvec(resid) * factor
    gp = [g[p] for p in arrow.p_idx]
    w = g[arrow.b_idx].copy()
    for y, x in zip(sch.y, gp, strict=True):
        w -= y.T @ x
    zb = sch.s_inv @ w
    q = float(w @ zb)
    for inv, x in zip(sch.pp_inv, gp, strict=True):
        q += float(x @ inv @ x)
    kept = (int(arrow.live.sum()) - int(sch.s_gone.shape[1])
            - sum(int(gone.shape[1]) for gone in sch.pp_gone))
    return q, kept


def _edited(bj: BlockJacobian, remove: np.ndarray,
            extra: list[np.ndarray | None]) -> BlockJacobian:
    """``bj`` without the columns ``remove`` marks, with block ``h``'s
    ``extra[h]`` appended as new columns of its own."""
    n = bj.n_cols
    blocks, maps = [], []
    for b, cm, e in zip(bj.blocks, bj.col_maps, extra, strict=True):
        keep = ~remove[cm]
        b, cm = b[:, keep], cm[keep]
        if e is not None and e.shape[1]:
            b = np.hstack([b, to_host_fp64(e)])
            cm = np.concatenate([cm, np.arange(n, n + e.shape[1], dtype=np.int64)])
            n += e.shape[1]
        blocks.append(b)
        maps.append(cm)
    return BlockJacobian(blocks, maps, bj.n_data, bj.n_pen, n)


def held_projection(bj: BlockJacobian, resid: np.ndarray, hold=()) -> tuple[float, int]:
    """:func:`_projection` with the columns ``hold`` left out: the null side
    of :func:`added_columns_gain`, the same for every alternative tested
    from one point."""
    held = np.zeros(bj.n_cols, dtype=bool)
    held[list(hold)] = True
    return _projection(_edited(bj, held, [None] * bj.n_blocks), resid)


def added_columns_gain(bj: BlockJacobian, resid: np.ndarray,
                       extra: list[np.ndarray | None], drop=(), hold=(), *,
                       null: tuple[float, int] | None = None
                       ) -> tuple[float, int]:
    """The χ² one linear step gains if block ``h`` also had ``extra[h]``.

    ``extra[h]`` holds columns over block ``h``'s rows, data then penalty as
    ``blocks[h]``, which no other block reaches; ``None`` adds none.  The
    columns ``drop`` (θ's indices) leave the alternative, so new columns can
    stand in for old ones: each pattern's own target in place of the
    coefficients that tied it.  The columns ``hold`` leave both sides, as a
    column held on its bound would.  Both sides are a least-squares step from
    ``resid`` with every other column refitted (:func:`_projection`), so the
    gain is the score statistic for the alternative at this point.  ``null``
    is :func:`held_projection` of the same ``bj``, ``resid`` and ``hold``,
    passed in when several alternatives share it.

    Returns ``(gain, rank)``: the gain, and how many more directions than the
    held ``bj`` the alternative has past the cut.
    """
    gone = np.zeros(bj.n_cols, dtype=bool)
    gone[list(hold)] = True
    gone[list(drop)] = True
    q0, k0 = held_projection(bj, resid, hold) if null is None else null
    q1, k1 = _projection(_edited(bj, gone, extra), resid)
    return q1 - q0, k1 - k0
