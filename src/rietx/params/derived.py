"""Derived blocks: nonlinear maps applied after the affine constraint block.

The parameter table's one affine block, p = C·p_free + d, cannot carry a rigid
body: a body atom's fractional coordinates x = o + M⁻¹·Exp(δω)·R₀·r are not
affine in the rotation increment δω.  WP-1803 measured the two candidate seams
and recorded the decision in ``docs/DESIGN.md`` § Parameter system ("Rigid
bodies: a typed ``derived`` block"): the exact map is applied in ``decode``
*after* the affine matmul, and every reader of C that has to know what a
derived row depends on reads the block's **local Jacobian at θ** (esds, the
restraint block) or its **declared reach** (the pattern readers), never C's
anchor rows (WP-1804).

A block is a closed-form map from declared *input* entries (physical values,
in table units: Å, degrees, radians for an increment) to declared *output*
entries.  The outputs are locked entries of the table: they have no row in C
and no free column, so ``set_vary`` can never free one, and the block alone
writes them.  Four things a block owes the table, each stated so a new kind
of block cannot leave one out:

* :meth:`DerivedBlock.evaluate` — the map on the numpy path (``decode``,
  ``commit``, every esd reader);
* :meth:`DerivedBlock.jacobian` — ∂outputs/∂inputs at the current inputs,
  **exact**, never a finite difference of :meth:`evaluate` (the table chains
  it through C and through any earlier block to get ∂p/∂p_free);
* :meth:`DerivedBlock.evaluate_traced` — the same map in ``xp`` ops, so the
  traced twin of ``decode`` (``backend.traced.make_traced_decode``) applies it
  after its dense matmul and an autodiff backend differentiates it;
* :meth:`DerivedBlock.reach_pattern` — which output depends on which input,
  **declared** from the map's structure rather than read off the Jacobian's
  numbers.  An instantaneous zero is not independence: on WP-1803's planar
  test body one rotation column's numeric reach was 28 rows where its declared
  reach is 42, and a freeze resting on the numeric reading would be wrong the
  moment the body turned.

Blocks are applied **in declaration order**, so a later block may read an
earlier block's outputs (a hydrogen riding on a body atom); the table refuses
a block that reads an output declared after it.

The Cartesian frame every body map uses is the closed form below, in ``xp``
ops, because the traced twin cannot call ``numpy.linalg.cholesky``
(``backend/traced.py``).  It is the frame :func:`rietx.crystallography.adp.
cartesian_basis` returns (x ∥ a, y in the a–b plane, z ∥ a × b — the Cholesky
factor of G with a positive diagonal is unique), pinned by
``tests/test_derived_block.py`` over 2000 random cells.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np

from ..backend import get_backend

#: degrees → radians, the factor every angle derivative below carries
_DEG = math.pi / 180.0


def cartesian_frame(cell):
    """M with x_cart = M·x_frac: the lattice vectors as columns (Å).

    M = [[a, b cos γ, c cos β],
         [0, b sin γ, c (cos α − cos β cos γ)/sin γ],
         [0, 0, V/(a b sin γ)]],

    the frame of TOPAS, FullProf and ``adp.cartesian_basis`` (x ∥ a, y in the
    a–b plane, z ∥ a × b), with V/(a b sin γ) written as c·S/sin γ,
    S² = 1 − cos²α − cos²β − cos²γ + 2 cos α cos β cos γ (Giacovazzo et al.
    2011, *Fundamentals of Crystallography*, 3rd ed., § 2.2, the volume of the
    cell).  Angles in degrees.  ``xp`` ops throughout, so the traced twin and
    an autodiff backend use the same frame as the numpy path.
    """
    xp = get_backend()
    a, b, c, al, be, ga = cell
    ca, cb, cg = xp.cos(xp.radians(al)), xp.cos(xp.radians(be)), xp.cos(xp.radians(ga))
    sg = xp.sin(xp.radians(ga))
    s = xp.sqrt(1.0 - ca * ca - cb * cb - cg * cg + 2.0 * ca * cb * cg)
    zero = 0.0 * a
    return xp.stack([xp.stack([a, b * cg, c * cb]),
                     xp.stack([zero, b * sg, c * (ca - cb * cg) / sg]),
                     xp.stack([zero, zero, c * s / sg])])


def fractional_frame(cell):
    """M⁻¹ (x_frac = M⁻¹·x_cart), the closed-form inverse of an upper-triangular M.

    Written out rather than solved, so it is ``xp`` ops on every backend.
    """
    xp = get_backend()
    m = cartesian_frame(cell)
    m00, m01, m02 = m[0, 0], m[0, 1], m[0, 2]
    m11, m12, m22 = m[1, 1], m[1, 2], m[2, 2]
    zero = 0.0 * m00
    return xp.stack([
        xp.stack([1.0 / m00, -m01 / (m00 * m11),
                  (m01 * m12 - m02 * m11) / (m00 * m11 * m22)]),
        xp.stack([zero, 1.0 / m11, -m12 / (m11 * m22)]),
        xp.stack([zero, zero, 1.0 / m22]),
    ])


def d_cartesian_frame_d_cell(cell) -> np.ndarray:
    """∂M/∂(a, b, c, α, β, γ), shape (6, 3, 3), angles per **degree**.

    Term by term from :func:`cartesian_frame`; numpy only (a Jacobian, never
    traced).  With S as there, ∂S/∂α = sin α (cos α − cos β cos γ)/S·π/180 and
    its two cyclic partners.
    """
    a, b, c, al, be, ga = (float(v) for v in cell)
    ca, cb, cg = (math.cos(math.radians(t)) for t in (al, be, ga))
    sa, sb, sg = (math.sin(math.radians(t)) for t in (al, be, ga))
    s = math.sqrt(1.0 - ca * ca - cb * cb - cg * cg + 2.0 * ca * cb * cg)
    ds_al = sa * _DEG * (ca - cb * cg) / s
    ds_be = sb * _DEG * (cb - ca * cg) / s
    ds_ga = sg * _DEG * (cg - ca * cb) / s
    d = np.zeros((6, 3, 3), dtype=np.float64)
    d[0, 0, 0] = 1.0                                    # ∂/∂a
    d[1, 0, 1] = cg                                     # ∂/∂b
    d[1, 1, 1] = sg
    d[2, 0, 2] = cb                                     # ∂/∂c
    d[2, 1, 2] = (ca - cb * cg) / sg
    d[2, 2, 2] = s / sg
    d[3, 1, 2] = -c * sa * _DEG / sg                    # ∂/∂α
    d[3, 2, 2] = c * ds_al / sg
    d[4, 0, 2] = -c * sb * _DEG                         # ∂/∂β
    d[4, 1, 2] = c * sb * _DEG * cg / sg
    d[4, 2, 2] = c * ds_be / sg
    d[5, 0, 1] = -b * sg * _DEG                         # ∂/∂γ
    d[5, 1, 1] = b * cg * _DEG
    d[5, 1, 2] = c * _DEG * (cb - ca * cg) / (sg * sg)
    d[5, 2, 2] = c * (ds_ga * sg - s * cg * _DEG) / (sg * sg)
    return d


class DerivedBlock(ABC):
    """A closed-form map from declared input entries to declared output entries.

    Subclasses set :attr:`inputs` and :attr:`outputs` (entry dot-paths, in the
    order the arrays below use) and implement the four methods.  See the module
    docstring for what each is owed and why the reach is declared.
    """

    #: entry paths read, in the order of the ``x`` argument below
    inputs: tuple[str, ...]
    #: entry paths written, in the order of :meth:`evaluate`'s result
    outputs: tuple[str, ...]
    #: the inputs the map reads as the **frame** it places its outputs in,
    #: not as a freedom of what it places: a rigid body reads its phase's cell
    #: only to turn Å into fractions.  A subset of :attr:`inputs`; none by
    #: default.  Read by the data-support count (WP-2067), which counts a
    #: column that reaches an atom through a block only through the block's
    #: other inputs, since the cell is paid for by peak positions whatever rows
    #: it also moves (McCusker et al. 1999, §9)
    frame_inputs: tuple[str, ...] = ()

    @abstractmethod
    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """Outputs (n_out,) from the physical inputs ``x`` (n_in,), numpy."""

    @abstractmethod
    def jacobian(self, x: np.ndarray) -> np.ndarray:
        """∂outputs/∂inputs at ``x``, shape (n_out, n_in), exact."""

    @abstractmethod
    def evaluate_traced(self, x: Sequence) -> list:
        """The map in ``xp`` ops (``get_backend()``): a list of n_out scalars."""

    @abstractmethod
    def reach_pattern(self) -> np.ndarray:
        """Declared dependence, bool (n_out, n_in): True where an output can
        move with an input anywhere in the map's domain."""
