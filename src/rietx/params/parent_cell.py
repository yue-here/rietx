"""A child's cell derived from its parent's cell and the Γ strains (WP-1419).

The map is ``crystallography.metric``'s, G′ = Pᵀ·(G_parent + 2·L·E·L)·P with
E = Σⱼ sⱼ·Eⱼ, read off as (a′, b′, c′, α′, β′, γ′); this module is its
:class:`~rietx.params.derived.DerivedBlock`, the second kind after the rigid
body (WP-1804).  Its inputs are the parent's six cell entries (tied and fixed
as the parent's own group says) and the strain amplitudes; its outputs are the
child's six cell entries, locked, so no glob frees them and the block is their
only writer.  A freed parent edge moves every child edge it reaches; a held
strain keeps the child exactly at its parent's metric carried through P, and
with every strain at zero the numpy map is bit-for-bit
``magnetic_supercell``'s own child cell (``metric.child_metric``).

The Jacobian is exact and term by term (∂G_parent/∂cell, the length scaling of
the strain, then ∂(a′ … γ′)/∂G′), and its esds reach the child's cell through
``ParameterTable.local_jacobian`` like a body atom's.  The traced twin leaves
out the cosine snap (``metric.cell_from_metric``): that snap moves a cosine by
at most 1e-12 and is a step, which an autodiff backend should not see.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from ..backend import get_backend
from ..crystallography.metric import cell_from_metric, child_metric
from .derived import DerivedBlock

_DEG = math.pi / 180.0
_CELL = ("a", "b", "c", "alpha", "beta", "gamma")
#: which G′ components each output reads: lengths their diagonal, an angle the
#: two diagonals and the off-diagonal between them
_READS = ({(0, 0)}, {(1, 1)}, {(2, 2)},
          {(1, 1), (2, 2), (1, 2)}, {(0, 0), (2, 2), (0, 2)},
          {(0, 0), (1, 1), (0, 1)})


class ParentCellBlock(DerivedBlock):
    """Parent cell + strain amplitudes → the child's (a, b, c, α, β, γ).

    ``parent`` and ``child`` are the two phases' cell path prefixes
    (``phases.0.parent_cell.cell`` and ``phases.0.cell``), ``strains`` the
    strain entry paths in :func:`~rietx.crystallography.metric.strain_basis`
    order, ``p_matrix`` P (columns: the child's axes in the parent's basis)
    and ``basis`` the (n, 3, 3) strain matrices Eⱼ.
    """

    def __init__(self, parent: str, child: str, strains: Sequence[str],
                 p_matrix, basis) -> None:
        self.inputs = (*(f"{parent}.{n}" for n in _CELL), *strains)
        self.outputs = tuple(f"{child}.{n}" for n in _CELL)
        self.p = np.asarray(p_matrix, dtype=np.float64)
        self.basis = np.asarray(basis, dtype=np.float64).reshape(len(strains), 3, 3)

    # -- the map -------------------------------------------------------
    def _metric(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        return child_metric(x[:6], self.p, x[6:], self.basis)

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(cell_from_metric(self._metric(x)), dtype=np.float64)

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        a, b, c, al, be, ga = (float(v) for v in x[:6])
        ca, cb, cg = (math.cos(math.radians(t)) for t in (al, be, ga))
        sa, sb, sg = (math.sin(math.radians(t)) for t in (al, be, ga))
        lengths = np.array([a, b, c])
        e = np.tensordot(x[6:], self.basis, axes=1) if len(self.basis) else np.zeros((3, 3))
        # ∂(G_parent + Δ)/∂input, one 3×3 per input
        d = np.zeros((len(self.inputs), 3, 3))
        d[0][0, 0] = 2 * a
        d[0][0, 1] = d[0][1, 0] = b * cg
        d[0][0, 2] = d[0][2, 0] = c * cb
        d[1][1, 1] = 2 * b
        d[1][0, 1] = d[1][1, 0] = a * cg
        d[1][1, 2] = d[1][2, 1] = c * ca
        d[2][2, 2] = 2 * c
        d[2][0, 2] = d[2][2, 0] = a * cb
        d[2][1, 2] = d[2][2, 1] = b * ca
        d[3][1, 2] = d[3][2, 1] = -b * c * sa * _DEG
        d[4][0, 2] = d[4][2, 0] = -a * c * sb * _DEG
        d[5][0, 1] = d[5][1, 0] = -a * b * sg * _DEG
        ll = np.outer(lengths, lengths)
        for m in range(3):
            unit = np.zeros(3)
            unit[m] = 1.0
            # Δ_ik = 2·ℓ_i·ℓ_k·E_ik, so ∂Δ_ik/∂ℓ_m = 2·E_ik·(δ_im·ℓ_k + ℓ_i·δ_km)
            d[m] += 2.0 * e * (np.outer(unit, lengths) + np.outer(lengths, unit))
        for j in range(len(self.basis)):
            d[6 + j] = 2.0 * ll * self.basis[j]
        dg = np.einsum("ki,nkl,lj->nij", self.p, d, self.p)
        g = self._metric(x)
        out = np.zeros((6, len(self.inputs)))
        n = np.sqrt(np.diag(g))
        for i in range(3):
            out[i] = dg[:, i, i] / (2.0 * n[i])
        for o, (i, j) in zip((3, 4, 5), ((1, 2), (0, 2), (0, 1)), strict=True):
            cosine = g[i, j] / (n[i] * n[j])
            dcos = (dg[:, i, j] / (n[i] * n[j])
                    - cosine * (dg[:, i, i] / (2.0 * g[i, i])
                                + dg[:, j, j] / (2.0 * g[j, j])))
            out[o] = -dcos / (math.sqrt(1.0 - cosine * cosine) * _DEG)
        return out

    def evaluate_traced(self, x: Sequence) -> list:
        from ..crystallography.lattice import direct_metric_tensor

        xp = get_backend()
        g = direct_metric_tensor(x[0], x[1], x[2], x[3], x[4], x[5])
        rows = [[g[i, k] for k in range(3)] for i in range(3)]
        for j in range(len(self.basis)):
            s = x[6 + j]
            for i in range(3):
                for k in range(3):
                    coeff = float(2.0 * self.basis[j][i, k])
                    if coeff != 0.0:
                        rows[i][k] = rows[i][k] + coeff * s * x[i] * x[k]
        gp = [[None] * 3 for _ in range(3)]
        for i in range(3):
            for k in range(3):
                total = 0.0 * x[0]
                for u in range(3):
                    for v in range(3):
                        coeff = float(self.p[u, i] * self.p[v, k])
                        if coeff != 0.0:
                            total = total + coeff * rows[u][v]
                gp[i][k] = total
        n = [xp.sqrt(gp[i][i]) for i in range(3)]
        out = list(n)
        for i, j in ((1, 2), (0, 2), (0, 1)):
            out.append(xp.degrees(xp.arccos(gp[i][j] / (n[i] * n[j]))))
        return out

    def reach_pattern(self) -> np.ndarray:
        """Which child entry each input can move, from where the map writes.

        Read off the structure: the G_parent entries each parent parameter
        enters (a length its row and column, an angle its one off-diagonal),
        the support of each strain Eⱼ, then carried through P's
        nonzero pattern and onto the G′ components each output reads.  Never
        off the Jacobian's numbers (``params.derived``'s rule).
        """
        touch = []
        for m in range(3):
            # an edge reaches its row and column of G_parent, and the strain's
            # Δ_ik = 2·ℓ_i·ℓ_k·E_ik only there too
            t = np.zeros((3, 3), dtype=bool)
            t[m, :] = t[:, m] = True
            touch.append(t)
        for i, j in ((1, 2), (0, 2), (0, 1)):
            t = np.zeros((3, 3), dtype=bool)
            t[i, j] = t[j, i] = True
            touch.append(t)
        for j in range(len(self.basis)):
            touch.append(np.abs(self.basis[j]) > 0)
        nz = np.abs(self.p) > 0
        pattern = np.zeros((6, len(self.inputs)), dtype=bool)
        for q, t in enumerate(touch):
            # (Pᵀ·T·P)_ij is reachable when some P_ui·T_uv·P_vj path is nonzero
            reached = (nz.T.astype(int) @ t.astype(int) @ nz.astype(int)) > 0
            for o, reads in enumerate(_READS):
                pattern[o, q] = any(reached[i, j] for i, j in reads)
        return pattern
