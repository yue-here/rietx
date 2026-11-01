"""Reduced cells, Bravais determination, and the cell-equality test dedup needs.

**Nothing here is hand-written that a dependency already does exactly.**  Niggli
and Delaunay (Selling) reduction are ``gemmi.GruberVector``; the lattice point
group is ``gemmi.find_lattice_symmetry`` (Le Page 1982, via
``find_lattice_2fold_ops``); ``spglib.get_symmetry_dataset`` gives an independent
opinion on the same question.  Both are hard dependencies already, MPL-2.0 and
BSD-3, neither on the licensing fence.

**Two independent opinions on Bravais, and their tolerances are not the same
kind of number.**  gemmi's is a Le Page **obliquity in degrees**; spglib's is a
distance **``symprec`` in Å**.  They parameterise the same question differently,
so both are run and the tolerance is *swept* — and the reported answer is the
highest symmetry **stable across the sweep**.  Symmetry that appears only at the
loosest tolerance is :data:`INDEX_BRAVAIS_AMBIGUOUS`, not an answer.  The device
is ``sequential.py``'s ``direction="both"`` and the cross-backend Jacobian matrix
one rank up: agreement between two independent methods is the confidence, and
disagreement is reported rather than averaged.

Monotonicity is what makes "stable" cheap to compute: loosening a tolerance can
only *add* symmetry, so the stable answer is the tightest tolerance's answer and
the ambiguity is whether the loosest one says something higher.  It is asserted
rather than assumed (``tests/test_indexing_reduce.py``).

**Both opinions must be asked about the same lattice, and that is easy to get
wrong in exactly one place.**  Niggli reduction of a *centred* cell returns the
reduced **primitive** cell — the centring is consumed by the reduction — so
:attr:`ReducedCell.centring` is provenance about the input and must not be handed
back to anything that applies a centring.  Doing so (WP-1020, fixed in WP-1024)
made gemmi report a cubic I lattice as **trigonal**, six lattice rotations instead
of twenty-four, so the two methods disagreed on every centred candidate and the
disagreement — which is supposed to mean pseudosymmetry — meant "one of us was
asked the wrong question".

**Dedup is a χ² test, not a percentage.**  Two candidates are the same lattice
when their Niggli-reduced A..F vectors agree under χ² = ΔᵀΣ⁻¹Δ against χ²₆(0.99),
using their joint covariance.  A fixed percentage merges distinct synchrotron
cells (whose esds are 100× smaller than the bound) and splits noisy lab ones —
per-line σ doing work again.  The relative fallback exists only for candidates
that arrive with no covariance at all.

**The difference and the covariance are taken in one frame** (WP-1518).  An
engine's covariance is in the setting it refined in, and the reduction permutes
and mixes A..F: a b-unique monoclinic cell's E lands in the F slot, and a c < a
cell's C lands in the A slot.  So :func:`reduction` returns the linear map beside
the reduced vector, and each covariance is carried through its own map.  Weighed
in the engine's frame instead, the difference met other components' variances.
Two b-unique cells 0.1° apart in β merged at χ² 1.3, and 41 % of pairs drawn
from one tetragonal lattice's covariance were split.

**And the comparison does not stop at a reduction boundary** (WP-1932).  Niggli
reduction is a canonical form with decision boundaries, so two descriptions of
one lattice either side of one reduce to different sides, and comparing the two
reduced vectors called them two lattices: 4 784 comparisons on the bethanechol
benchmark and 8 on the LaB6 acceptance searches (#834), at χ² up to 81 000.  A
pair the χ² calls distinct is asked again of b's other descriptions in Selling's
form (:func:`_equal_across_boundaries`), the reduced cell staying the dedup key.
Selling's reduction is written here although ``gemmi.GruberVector.selling`` exists,
because that keeps neither the four vectors nor a step through a boundary, and
the search needs both.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from ..optimize.statistics import _psd_pinv

#: How spglib declines a cell it cannot solve, in **both** of its error modes.
#: It returns ``None`` under ``spglib.error.OLD_ERROR_HANDLING = True``, which
#: is spglib's own (deprecated) default, and **raises** ``SpglibError`` under
#: ``False``.  The flag is process-global and a third-party import can flip it:
#: ``spgrep/__init__.py`` (0.7.0) sets it ``False`` and never puts it back, so
#: every ``if data is None`` fallback in this module became unreachable the
#: moment anything in the process imported spgrep — measured in Yue's review of
#: #389, where ``conventional_cell((1e-4,) * 3 + (90, 90, 90))`` returned its
#: documented ``((1e-4, …), "P", "")`` before the import and raised
#: ``SpglibCppError: spacegroup search failed`` after it.  A caller that wants
#: the fallback catches this **as well as** reading the ``None``.
SPGLIB_REFUSALS: tuple[type[BaseException], ...] = ()
try:  # pragma: no cover - present in every spglib this package supports
    from spglib.error import SpglibError as _SpglibError

    SPGLIB_REFUSALS = (_SpglibError,)
except ImportError:  # pragma: no cover - a spglib without the error module
    pass

#: χ²₆ at 99 % — the equality bound for two 6-vectors of A..F.  Six because the
#: comparison is always made on the *reduced primitive* form, which has all six
#: components free whatever system the candidates were found in.
CELL_EQUALITY_CHI2 = 16.8119
#: Relative bound used only when a candidate carries no covariance.  Deliberately
#: an order looser than a synchrotron cell's precision, so it never *tightens* a
#: comparison the χ² test would have made.
CELL_EQUALITY_RELATIVE = 5e-3
#: **Relative** tolerance for every floating-point comparison inside the Niggli
#: reduction, as ε = ``NIGGLI_EPS_RELATIVE`` · V^(1/3) — Grosse-Kunstleve, Sauter
#: & Adams (2004), *Acta Cryst.* **A60**, 1-6, eq. (3), and their value.
#:
#: **The Křivý-Gruber reduction is not stable in floating point without one**, and
#: gemmi's default is an *absolute* 1e-9.  That paper's Test 3 — reduce a Niggli
#: cell, re-set it by a unimodular matrix with large elements, reduce again, demand
#: the same cell — is exactly ``test_niggli_reduction_is_unimodular_invariant``
#: here, and it reports that test failing at ε_relative = 1e-10 and passing at
#: 1e-5.  Measured here, on the case hypothesis found: the reduced cell of
#: (3, 3, 3, 66°, 110°, 65°) has **b = c exactly**, so Křivý-Gruber step A2 must
#: break the tie on |η| ≤ |ζ| — and at gemmi's default the two settings came back
#: with β and γ *swapped* (106.877/108.054 against 108.054/106.877), the second of
#: which violates A2 while gemmi's own ``is_niggli`` called both True.  At this
#: value they agree.  The same ε must be used for the reduction *and* for the
#: predicate, which is the paper's Goal 2.
NIGGLI_EPS_RELATIVE = 1e-5
#: Le Page obliquities (degrees) swept by :func:`bravais_screen`.
BRAVAIS_OBLIQUITIES: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)
#: Multiples of the cell's own esd used as spglib ``symprec`` values.  Tying the
#: sweep to the *measured* precision rather than to a fixed distance is the
#: per-line-σ rule again: 1e-3 Å is generous on a synchrotron cell and tight on a
#: lab one, and a fixed value would make the two opinions incomparable.
BRAVAIS_SYMPREC_SIGMAS: tuple[float, ...] = (1.0, 3.0, 10.0)

#: Space-group number ranges → crystal system, the standard division.  Used to
#: read spglib's answer in the same vocabulary gemmi's operation count gives.
_SYSTEM_BY_NUMBER: tuple[tuple[int, str], ...] = (
    (2, "triclinic"), (15, "monoclinic"), (74, "orthorhombic"),
    (142, "tetragonal"), (167, "trigonal"), (194, "hexagonal"),
    (230, "cubic"))
#: Rotation count of each holohedral lattice group (gemmi's ``sym_ops``, i.e. the
#: Laue order halved) → system.  A *lattice* group is always holohedral, so this
#: map is exhaustive: -1, 2/m, mmm, 4/mmm, -3m, 6/mmm, m-3m.
_SYSTEM_BY_SYM_OPS: dict[int, str] = {
    1: "triclinic", 2: "monoclinic", 4: "orthorhombic", 6: "trigonal",
    8: "tetragonal", 12: "hexagonal", 24: "cubic"}
#: Rank for "higher symmetry": the **order of the lattice point group**, which is
#: `_SYSTEM_BY_SYM_OPS` read backwards.  A total order, unlike anything derived
#: from ``METRIC_DOF``: cubic and hexagonal have 1 and 2 metric degrees of freedom
#: but so do cubic and *tetragonal*-vs-*trigonal*, so a DOF-based rank ties pairs
#: of systems, and an inverse lookup through a tied rank silently returns the
#: wrong system — it returned "hexagonal" for a cubic cell, first time.  Note what
#: this order does *not* mean: a higher rank is not a supergroup relation
#: (tetragonal at 8 is not a supergroup of trigonal at 6), so it is only ever used
#: to pick the more conservative of two answers to the same question.
SYSTEM_RANK: dict[str, int] = {v: k for k, v in _SYSTEM_BY_SYM_OPS.items()}


@dataclass
class ReducedCell:
    """A reduced cell and the change of basis that produced it."""

    cell: tuple[float, float, float, float, float, float]
    change_of_basis: str            # gemmi triplet, e.g. "y,z,x"
    #: centring of the **input** cell, kept for provenance.  :attr:`cell` itself is
    #: always **primitive**: ``gemmi.GruberVector(uc, centring)`` reduces the
    #: primitive cell of the centred lattice, so the centring has already been
    #: consumed by the reduction (measured: the reduced form of a cubic I cell with
    #: a = 5.8783 Å is (5.0908, 5.0908, 5.0908, 109.4712°, …) at exactly half the
    #: conventional volume, and the change of basis is the I → P transformation).
    #: **Do not pass this back to a routine that applies a centring** — see
    #: :func:`bravais_screen`, where doing so was a live bug.
    centring: str
    kind: str                       # "niggli" or "delaunay"
    #: gemmi's own ``is_niggli`` / ``is_buerger`` predicate, evaluated on the
    #: *input*.  Informational, and **not** a reliable "reduction changed nothing"
    #: signal on floating-point input: measured, a rhombohedral cell
    #: (3, 3, 3, 65°, 65°, 65°) whose reduction is a fixed point to 1e-15 reports
    #: ``already_reduced = False`` on the second pass, because the reduced
    #: parameters carry fp noise the predicate's own tolerance does not absorb.
    #: Idempotence is asserted on the cell parameters instead
    #: (``tests/test_indexing_reduce.py``).
    already_reduced: bool


@dataclass
class BravaisScreen:
    """What the two opinions say about the lattice symmetry, tolerance by
    tolerance, and what survives all of it."""

    reduced: ReducedCell
    by_obliquity: dict[float, str] = field(default_factory=dict)
    by_symprec: dict[float, str] = field(default_factory=dict)
    spglib_symbols: dict[float, str] = field(default_factory=dict)
    #: the more conservative of the two methods' *tightest*-tolerance answers —
    #: the symmetry that survives the whole sweep
    system: str = "triclinic"
    #: highest symmetry any tolerance of either method reported
    system_loosest: str = "triclinic"
    ambiguous: bool = False
    #: each method's tightest-tolerance answer, kept separately: their tolerances
    #: are different *kinds* of number (degrees of obliquity against Å), so a
    #: disagreement is information about the cell, not a bug in either
    system_gemmi: str = "triclinic"
    system_spglib: str = "triclinic"
    methods_disagree: bool = False


def lattice_vectors(cell: tuple[float, ...]) -> np.ndarray:
    """Row-vector lattice (3, 3) in a Cartesian frame, for spglib.

    The Cholesky factor of the direct metric: L·Lᵀ = G, so the rows of L are
    lattice vectors realising exactly that metric — the same construction
    ``wyckoff._compatible_lattice`` uses, and it works in any setting.
    """
    from ..crystallography.lattice import direct_metric_tensor
    return np.linalg.cholesky(np.asarray(direct_metric_tensor(*cell)))


def reduce_cell(cell: tuple[float, ...], centring: str = "P", *,
                kind: str = "niggli") -> ReducedCell:
    """Niggli (default) or Delaunay reduction, with the change of basis kept.

    **The reduced cell is the exact image of the input under that change of
    basis** (WP-1923, WP-2035): it is built from M·G·Mᵀ, never read off
    gemmi's G6 vector.  Inside ε a reduction step treats a near-zero ξ, η or ζ
    as zero and may hand it either sign, and gemmi records no basis change for
    it.  Flipping one sign is not a change of basis, so gemmi's vector then
    sat one ε from the input's image.  Measured on the cell of issue #797,
    (3, 11, 14.1972, 65°, 65°, 65°): η = −1.753e-5 out of ``niggli_reduce``
    against +1.753e-5 in M·G·Mᵀ.  A sign check alone does not catch every
    such case (WP-2035): on the F-centred cell (3.2, 16.0, 23.6025 Å, 81°,
    66°, 65°) a normalisation flipped ζ and kept η = −1.26e-5, a Křivý-Gruber
    step then moved ξ by that wrongly signed η, and a second normalisation put
    η's sign back.  Every sign agreed at the end, and ξ was 2|η| = 2.5e-5 off
    the image (1.1e-7 of max|G|).  The image differs from gemmi's vector by
    under ε, which is all the reduction promised.
    """
    import gemmi

    uc = gemmi.UnitCell(*cell)
    eps = NIGGLI_EPS_RELATIVE * uc.volume ** (1.0 / 3.0)
    gv = gemmi.GruberVector(uc, centring, track_change_of_basis=True)
    already = gv.is_niggli(eps) if kind == "niggli" else gv.is_buerger()
    if kind == "niggli":
        gv.niggli_reduce(epsilon=eps)
    elif kind == "delaunay":
        gv.selling()
    else:
        raise ValueError(f"kind must be 'niggli' or 'delaunay', not {kind!r}")
    gv.normalize(epsilon=eps)
    triplet = gv.change_of_basis.triplet()
    return ReducedCell(
        cell=_cell_from_metric(_metric_image(cell, triplet)),
        change_of_basis=triplet, centring=centring, kind=kind,
        already_reduced=already)


def _metric_image(cell: tuple[float, ...], triplet: str) -> np.ndarray:
    """M·G·Mᵀ, the input's direct metric under the reduction's change of basis."""
    from ..crystallography.lattice import direct_metric_tensor
    m = _basis_change(triplet)
    return m @ np.asarray(direct_metric_tensor(*cell), dtype=np.float64) @ m.T


def _cell_from_metric(g: np.ndarray
                      ) -> tuple[float, float, float, float, float, float]:
    """Cell parameters from a direct metric tensor."""
    a, b, c = (float(np.sqrt(g[i, i])) for i in range(3))
    ang = [float(np.degrees(np.arccos(np.clip(g[m, n] / (l1 * l2), -1.0, 1.0))))
           for (m, n), (l1, l2) in (((1, 2), (b, c)), ((0, 2), (a, c)),
                                    ((0, 1), (a, b)))]
    return a, b, c, ang[0], ang[1], ang[2]


def _system_from_number(number: int) -> str:
    for limit, system in _SYSTEM_BY_NUMBER:
        if number <= limit:
            return system
    raise ValueError(f"space-group number {number} out of range")


def bravais_screen(cell: tuple[float, ...], centring: str = "P", *,
                   cell_esd: np.ndarray | float = 1e-3,
                   obliquities: tuple[float, ...] = BRAVAIS_OBLIQUITIES,
                   symprec_sigmas: tuple[float, ...] = BRAVAIS_SYMPREC_SIGMAS,
                   ) -> BravaisScreen:
    """Lattice symmetry from gemmi and spglib, over a tolerance sweep.

    ``cell_esd`` scales the spglib ``symprec`` sweep, so the tolerance is a
    multiple of the *measured* precision rather than a fixed distance.
    """
    import gemmi
    import spglib

    # checked before anything runs, because the floor below cannot catch it:
    # ``max(nan, 1e-6)`` is nan, and spglib 2.8 answers ``symprec=nan`` with a
    # segmentation fault, which kills the process instead of raising an error
    # :func:`~rietx.indexing.consensus.bravais_opinion` can decline
    esd = float(np.max(np.atleast_1d(np.asarray(cell_esd, dtype=np.float64))[:3]))
    if not np.isfinite(esd):
        raise ValueError(f"cell_esd must be finite to scale the symprec sweep; "
                         f"got {cell_esd!r}")
    reduced = reduce_cell(cell, centring)
    uc = gemmi.UnitCell(*reduced.cell)
    by_obliquity = {}
    for tol in obliquities:
        # "P", not ``reduced.centring``: the reduction already consumed the
        # centring and returned the *primitive* cell, so passing the input
        # centring back centres it a second time.  Measured, that is not a
        # subtlety — a cubic I cell came back **trigonal** from gemmi (6 lattice
        # rotations instead of 24) while spglib, which is handed the bare lattice,
        # correctly said Im-3m.  The two then "disagreed" on every centred
        # candidate, which set ``methods_disagree`` and ``ambiguous`` and so
        # capped every centred lattice's confidence at medium for good — about
        # half of all real structures.
        ops = gemmi.find_lattice_symmetry(uc, "P", tol)
        by_obliquity[tol] = _SYSTEM_BY_SYM_OPS.get(len(ops.sym_ops), "triclinic")

    esd = max(esd, 1e-6)
    lat = lattice_vectors(reduced.cell)
    by_symprec, symbols = {}, {}
    for k in symprec_sigmas:
        try:
            data = spglib.get_symmetry_dataset((lat.tolist(), [[0.0, 0.0, 0.0]], [1]),
                                               symprec=k * esd)
        except SPGLIB_REFUSALS:       # the same refusal, the other error mode
            data = None
        if data is None:
            by_symprec[k], symbols[k] = "triclinic", ""
            continue
        by_symprec[k] = _system_from_number(int(data.number))
        symbols[k] = str(data.international)

    # loosening a tolerance can only *add* symmetry (asserted in
    # tests/test_indexing_reduce.py), so "stable across the sweep" is exactly the
    # tightest tolerance's answer, and the ambiguity is whether a looser one says
    # something higher
    gemmi_tight = by_obliquity[min(obliquities)]
    spglib_tight = by_symprec[min(symprec_sigmas)]
    inverse = {v: k for k, v in SYSTEM_RANK.items()}
    tightest = min(SYSTEM_RANK[gemmi_tight], SYSTEM_RANK[spglib_tight])
    loosest = max(max(SYSTEM_RANK[s] for s in by_obliquity.values()),
                  max(SYSTEM_RANK[s] for s in by_symprec.values()))
    return BravaisScreen(
        reduced=reduced, by_obliquity=by_obliquity, by_symprec=by_symprec,
        spglib_symbols=symbols, system=inverse[tightest],
        system_loosest=inverse[loosest], ambiguous=loosest != tightest,
        system_gemmi=gemmi_tight, system_spglib=spglib_tight,
        methods_disagree=gemmi_tight != spglib_tight)


def cell_from_vectors(lattice: np.ndarray
                      ) -> tuple[float, float, float, float, float, float]:
    """Cell parameters from row-vector lattice vectors — spglib's output form."""
    lat = np.asarray(lattice, dtype=np.float64)
    return _cell_from_metric(lat @ lat.T)


def conventional_cell(cell: tuple[float, ...], *, symprec: float = 1e-3
                      ) -> tuple[tuple[float, ...], str, str]:
    """The conventional (standardised) cell of a lattice, its centring and symbol.

    spglib's ``std_lattice`` is the standardisation, and it is the piece that
    cannot be got from a reduced cell alone: metric symmetry higher than the
    reduced primitive cell's shows up here as a *centred* conventional cell — a
    primitive bcc cell comes back as ``Im-3m`` with a cubic conventional lattice,
    which is the answer an engine that found the primitive cell needs to report.
    """
    import spglib

    lat = lattice_vectors(cell)
    try:
        data = spglib.get_symmetry_dataset((lat.tolist(), [[0.0, 0.0, 0.0]], [1]),
                                           symprec=symprec)
    except SPGLIB_REFUSALS:           # the same refusal, the other error mode
        data = None
    if data is None:
        return tuple(cell), "P", ""
    symbol = str(data.international)
    return cell_from_vectors(np.asarray(data.std_lattice)), symbol[0], symbol


def reduced_af(af: np.ndarray) -> np.ndarray:
    """(A..F) of the Niggli-reduced form of this metric.

    Split out of :func:`same_lattice` because the reduction is the expensive half
    (a gemmi call) and a dedup pass compares every candidate against every kept
    one: reducing inside the comparison makes it O(N²) reductions where O(N) will
    do.  Measured on a monoclinic search that accepted ~5 000 raw candidates, that
    was the single largest cost in the engine.  It builds no covariance map:
    :func:`reduction` does, for a caller that has a covariance to carry.
    """
    from .qspace import af_from_cell, cell_from_af
    return af_from_cell(reduce_cell(cell_from_af(af)).cell)


def reduction(af: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    """(A..F) of the Niggli-reduced form, and the 6×6 map T that took ``af`` there.

    red = T·af, so a covariance of ``af`` is T·cov·Tᵀ in the reduced frame
    (:func:`reduced_covariance`).  T is ``None`` when the change of basis is
    the identity, which is what keeps a pair already in its reduced setting
    bit-identical to the test before WP-1518.

    **T is the whole map** because :func:`reduce_cell` returns the exact image
    of its input under the triplet (WP-1923), so T·af equals red to rounding.
    Until then the reduction could give a near-zero D, E or F the sign of a
    value it treats as zero, and this function flipped those rows of T to
    agree.  Flipping one sign is not a change of basis: the 797 cell's red sat
    1.2e-5 off T·af in E and 4e-8 in A..C, one ε from the input's metric.
    """
    from .qspace import af_from_cell, cell_from_af
    reduced = reduce_cell(cell_from_af(af))
    return af_from_cell(reduced.cell), _af_map(reduced.change_of_basis)


def _basis_change(triplet: str) -> np.ndarray:
    """M with (reduced basis rows) = M · (input basis rows), from
    :attr:`ReducedCell.change_of_basis`.

    gemmi's triplet is the transpose of that matrix — checked on P, C, I and R
    cells by ``transform_cell(cell, M)`` reproducing the reduced cell.
    """
    import gemmi

    op = gemmi.Op(triplet)
    return np.asarray(op.rot, dtype=np.float64).T / gemmi.Op.DEN


#: sized past the distinct triplets a triclinic harvest reaches (840 in 3000
#: random triclinic reductions), so a pass does not rebuild the map it just built
@lru_cache(maxsize=4096)
def _af_map(change_of_basis: str) -> np.ndarray | None:
    """The linear map on A..F of a primitive change of basis, a gemmi triplet.

    With M from :func:`_basis_change`, the direct metric goes to M·G·Mᵀ, so the
    reciprocal metric goes to M⁻ᵀ·G*·M⁻¹.  That convention was measured, since
    the inverse and the transpose are each a plausible reading.  Over 28
    reductions of cubic to triclinic cells in five centrings, M⁻ᵀ matched the
    reduced metric to ≤ 1e-15 relative every time.  M, Mᵀ and M⁻¹ each missed
    some by 0.3 or more, and a permutation, where Mᵀ = M⁻¹, hides the
    difference.  A..F is linear in G*
    (:func:`~.qspace.gstar_from_af`), so column p of T is that congruence
    applied to the p-th unit vector.  M of a primitive reduction is
    unimodular, and rounding its inverse makes T exact.
    """
    if change_of_basis == "x,y,z":
        return None
    return _af_map_of_inverse(np.rint(np.linalg.inv(
        _basis_change(change_of_basis))).T)


def _af_map_of_inverse(m: np.ndarray) -> np.ndarray:
    """T from M⁻ᵀ: column p is M⁻ᵀ·G*(e_p)·M⁻¹ read back as A..F."""
    from .qspace import af_from_gstar, gstar_from_af
    t = np.column_stack([af_from_gstar(m @ gstar_from_af(e) @ m.T)
                         for e in np.eye(6)])
    t.setflags(write=False)
    return t


@lru_cache(maxsize=256)
def _af_map_of_rows(rows: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    return _af_map_of_inverse(np.rint(np.linalg.inv(
        np.asarray(rows, dtype=np.float64))).T)


def af_map(change: Sequence[Sequence[int]]) -> np.ndarray:
    """The linear map on A..F of an integer change of basis.

    ``change`` is M with (new basis rows) = M · (old basis rows), unimodular,
    the convention of :func:`_basis_change` and of
    :attr:`~rietx.schemas.indexing.CellCandidate.change_of_basis`.  The new
    A..F is T·af, and a covariance goes to T·cov·Tᵀ, exactly as for
    :func:`reduction`'s map.
    """
    return _af_map_of_rows(tuple(tuple(int(v) for v in row) for row in change))


#: Gauss steps a monoclinic re-set may take before it is declared stuck.  One
#: step at least halves |a·c| or shortens a vector, so a cell needing more
#: than this is not a metric any engine returns.
_SETTING_STEPS = 200

#: Relative size below which a·c, or a² − c², is rounding rather than a
#: choice: a right angle or an a = c tie re-set on its last bit flips a and b
#: (or swaps a and c) and records a change of basis nothing asked for, and
#: the re-set is then not idempotent.
_SETTING_TIE = 1e-12


def _gauss_step(ratio: float) -> int:
    """The nearest integer to ``ratio``, and 0 on a ±½ tie within
    :data:`_SETTING_TIE`: both sides of a tie are reduced, and rounding must
    not be what picks one."""
    if abs(ratio) <= 0.5 + _SETTING_TIE:
        return 0
    return int(np.rint(ratio))


def conventional_setting(af: np.ndarray, system: str, centring: str = "P"
                         ) -> tuple[tuple[int, int, int], ...] | None:
    """The change of basis to the conventional setting, or ``None`` if none is
    needed (WP-1923).

    Only a **monoclinic** lattice has a setting to choose here: every other
    system's metric subspace fixes its axes up to labels, and a triclinic
    cell is reported as found (the reduced form is :func:`reduce_cell`'s).
    An engine's monoclinic metric is always b-unique (``qspace.metric_basis``),
    so the choice is a basis (a, c) of the net perpendicular to b, and the
    IUCr one (*ITA* A § 9.3; Mighell & Santoro 1975 for why it is needed) is
    taken: the two shortest translations, β non-acute.

    * **P**: a Lagrange-Gauss reduction of (a, c), then a ≤ c.
    * **C**: the centring (a + b)/2 must survive, so a' = p·a + q·c needs q
      even, and a and c cannot be swapped.  The same alternation runs inside
      that group: c reduced against a, a against 2c.

    Then β is made obtuse by a → −a, and b → ±b keeps the basis
    right-handed.  Both rules reproduce spglib's ``std_lattice``
    (:func:`conventional_cell`) on the cells ``tests/test_indexing_reduce.py``
    draws.  Returns M with (new basis rows) = M · (old basis rows).
    ``None`` too where ``af`` is not a lattice's metric (non-finite or not
    positive definite): there is no setting to choose, and a caller reporting
    a candidate must not be stopped by one.
    """
    if system != "monoclinic" or centring not in ("P", "C"):
        return None
    from .qspace import gstar_from_af
    af = np.asarray(af, dtype=np.float64)
    if not np.all(np.isfinite(af)):
        return None
    gstar = gstar_from_af(af)
    if np.linalg.eigvalsh(gstar)[0] <= 0.0:
        return None                                  # not a lattice
    g = np.linalg.inv(gstar)
    scale = float(np.max(np.abs(np.diag(g))))
    if abs(g[0, 1]) > 1e-9 * scale or abs(g[1, 2]) > 1e-9 * scale:
        return None                                  # not b-unique: leave it
    plane = np.array([[g[0, 0], g[0, 2]], [g[0, 2], g[2, 2]]])
    n = np.eye(2, dtype=np.int64)

    def apply(step: np.ndarray) -> None:
        nonlocal n, plane
        n = step @ n
        plane = step @ plane @ step.T

    for _ in range(_SETTING_STEPS):
        k = _gauss_step(plane[0, 1] / plane[0, 0])
        if k:
            apply(np.array([[1, 0], [-k, 1]]))       # c ← c − k·a
        if centring == "P":
            if plane[1, 1] < plane[0, 0] * (1.0 - _SETTING_TIE):
                apply(np.array([[0, 1], [1, 0]]))    # swap a and c
                continue
        else:
            m = _gauss_step(plane[0, 1] / (2.0 * plane[1, 1]))
            if m:
                apply(np.array([[1, -2 * m], [0, 1]]))   # a ← a − 2m·c
                continue
        if not k:
            break
    else:
        raise RuntimeError(f"no monoclinic setting reached for af = "
                           f"{np.asarray(af).tolist()} in {_SETTING_STEPS} steps")
    if plane[0, 1] > _SETTING_TIE * np.sqrt(plane[0, 0] * plane[1, 1]):  # β acute
        apply(np.array([[-1, 0], [0, 1]]))
    sb = int(round(np.linalg.det(n)))
    rows = ((int(n[0, 0]), 0, int(n[0, 1])), (0, sb, 0),
            (int(n[1, 0]), 0, int(n[1, 1])))
    return None if rows == ((1, 0, 0), (0, 1, 0), (0, 0, 1)) else rows


def reduced_covariance(cov: np.ndarray | None, t: np.ndarray | None
                       ) -> np.ndarray | None:
    """A covariance of A..F carried into the frame :func:`reduction`'s T maps to."""
    if cov is None or t is None:
        return cov
    return t @ np.asarray(cov, dtype=np.float64) @ t.T


#: The cut :func:`equal_reduced` hands the pseudo-inverse of Σ: numpy's own
#: ``pinv`` default, which it used until WP-1930.  The inverse is
#: :func:`~rietx.optimize.statistics._psd_pinv`, because Σ is a sum of
#: rank-deficient covariances, and a flat direction's rounding-level
#: eigenvalue taken with its sign makes χ² negative and merges two cells.
CELL_PINV_RCOND = 1e-15


def equal_reduced(red_a: np.ndarray, red_b: np.ndarray, *,
                  cov_a: np.ndarray | None = None,
                  cov_b: np.ndarray | None = None) -> tuple[bool, float]:
    """The equality test on **already reduced** A..F vectors.  Returns
    (verdict, χ²), the χ² NaN without covariances.

    The covariances must be in the reduced frame too.  An engine's ``cov_af`` is
    in the setting it refined in, so carry it with :func:`reduced_covariance`.

    **First the two reduced vectors as they are**: χ² = ΔᵀΣ⁺Δ against
    :data:`CELL_EQUALITY_CHI2`, or every component within
    :data:`CELL_EQUALITY_RELATIVE` without covariances.  A pair this joins is
    joined exactly as before WP-1932, χ² and all.

    **Then, only for a pair it calls distinct, b's other descriptions across
    the reduction's boundaries** (WP-1932, :func:`_equal_across_boundaries`).
    Niggli reduction is a canonical form with decision boundaries, and two
    descriptions of one lattice either side of one reduce to different sides:
    measured on the bethanechol benchmark (#834), 4 784 comparisons split one
    lattice so, at χ² up to 81 000.  The same χ² is then asked of each exact
    image of b that the Selling form (Andrews, Bernstein & Sauter 2019, *Acta
    Cryst.* A75, 115 and 593) puts within the pair's error of a, and the
    returned χ² is that image's when one passes.
    """
    same, chi2 = _equal_as_given(red_a, red_b, cov_a, cov_b)
    if same:
        return same, chi2
    across = _equal_across_boundaries(red_a, red_b, cov_a, cov_b)
    return (same, chi2) if across is None else across


def _equal_as_given(red_a, red_b, cov_a, cov_b) -> tuple[bool, float]:
    """:func:`equal_reduced`'s test on the two vectors as given (before WP-1932,
    the whole of it)."""
    delta = np.asarray(red_a) - np.asarray(red_b)
    if cov_a is None or cov_b is None:
        # a component that is zero by symmetry (a monoclinic D, E) comes out of
        # M·G·Mᵀ as rounding noise of either sign, ~1e-16 of the metric's scale
        # (WP-2035); relative to *itself* two such noises are never equal, so the
        # scale has a floor at the vector's own rounding level (1e-12 of its
        # largest component, ~1e4 times double epsilon)
        scale = np.maximum(np.abs(red_a), np.abs(red_b))
        scale = np.maximum(scale, 1e-12 * float(scale.max()))
        ok = bool(np.all(np.abs(delta) <= CELL_EQUALITY_RELATIVE * scale))
        return ok, float("nan")
    sigma = np.asarray(cov_a) + np.asarray(cov_b)
    chi2 = float(delta @ _psd_pinv(sigma, CELL_PINV_RCOND) @ delta)
    return chi2 <= CELL_EQUALITY_CHI2, chi2


def equal_reduced_many(red_a: np.ndarray, reds_b: Sequence[np.ndarray], *,
                       cov_a: np.ndarray, covs_b: Sequence[np.ndarray],
                       gates: tuple | None = None,
                       ) -> list[tuple[bool, float]]:
    """:func:`equal_reduced` of one vector against many, the pseudo-inverses in
    one stacked solve (WP-1519).  Covariances are required on both sides.

    Each pair's Δ, Σ and final product are :func:`equal_reduced`'s own
    expressions, and only the pseudo-inverse runs over the (k, 6, 6) stack, so each
    answer is the pair's own **where** :func:`stacked_pinv_exact` **says so**.
    A caller asks it first.  One Σ that makes the stack raise raises for all
    of them, so a caller that catches it re-asks the pairs one at a time.
    A pair the stack calls distinct is then asked across the reduction's
    boundaries by the very function :func:`equal_reduced` asks (WP-1932), so
    that half of the answer is the pair's own by construction.

    ``gates`` is (a's, [each b's]) Selling gate inputs as :func:`_gate_inputs`
    returns them, for a caller that already holds them: dedup asks each kept
    group hundreds of times, and looking them up again was half of what the
    boundary search added to its wall clock.  The answers are the same either way.
    """
    if not len(reds_b):
        return []
    red_a, cov_a = np.asarray(red_a), np.asarray(cov_a)
    deltas = [red_a - np.asarray(red_b) for red_b in reds_b]
    sigmas = np.stack([cov_a + np.asarray(cov_b) for cov_b in covs_b])
    out = []
    for delta, inverse in zip(deltas, _psd_pinv(sigmas, CELL_PINV_RCOND)):
        chi2 = float(delta @ inverse @ delta)
        out.append((chi2 <= CELL_EQUALITY_CHI2, chi2))
    distinct = [k for k, (same, _chi2) in enumerate(out) if not same]
    if distinct:
        # the gate over the whole batch at once, element for element the
        # arithmetic the pair's own call does (_selling_gate), so the
        # survivors, and so the answers, are the pair's own
        if gates is None:
            mine = _gate_inputs(red_a, cov_a)
            theirs = [_gate_inputs(np.asarray(reds_b[k]), np.asarray(covs_b[k]))
                      for k in distinct]
        else:
            mine = gates[0]
            theirs = [gates[1][k] for k in distinct]
        live = [k for k, t in zip(distinct, theirs) if t is not None]
        if mine is not None and live:
            passed = _selling_gate(mine, np.array([t for t in theirs if t is not None]))
            for k in (k for k, ok in zip(live, passed) if ok):
                across = _equal_across_boundaries(red_a, reds_b[k], cov_a, covs_b[k],
                                                  gated=True)
                if across is not None:
                    out[k] = across
    return out


# ----------------------------------------------------------------------------
# WP-1932: the comparison across the reduction's boundaries, in Selling's form
# ----------------------------------------------------------------------------
#: Multiples of a Selling scalar's own esd inside which the boundary-free test
#: looks for b's other descriptions (WP-1932).  Where a pair passes the χ² test
#: at :data:`CELL_EQUALITY_CHI2`, every linear function of its difference lies
#: within √χ² of that function's own esd (Cauchy-Schwarz under the metric Σ⁺),
#: to first order; a quarter more leaves room for the second.  Measured on two
#: bethanechol dedup calls of 1 906 and 16 198 candidates: the groups are the
#: same at 1.1, 1.25 and 2 times √χ², and 2 cost 3.3 and 1.6 times 1.25's wall
#: clock.  A gate and a selector, never a verdict: the χ² on the image decides.
SELLING_GATE_SIGMAS = 1.25 * float(np.sqrt(CELL_EQUALITY_CHI2))
#: The same gate for a pair without covariances, as a fraction of the larger
#: metric trace.  Ten times :data:`CELL_EQUALITY_RELATIVE`, because the gate
#: reads the direct metric and the rule reads A..F: generous, and still only a
#: gate, since the componentwise rule on the image decides.
SELLING_GATE_RELATIVE = 0.05
#: Boundaries crossed on a's side and on b's: one and two.  On the 608 split
#: comparisons sampled from #834's count, one each side joined 604, and the
#: other four (two right angles plus an obtuse α, Ba/manual) needed two steps
#: on one side.
_SELLING_DEPTH = (1, 2)
#: Selling's six scalars s1..s6 = b·c, a·c, a·b, a·d, b·d, c·d of the four
#: vectors a, b, c, d = −(a + b + c) (Andrews, Bernstein & Sauter 2019, A75,
#: 115, § 2), as index pairs into the four.
_SELLING_PAIRS = ((1, 2), (0, 2), (0, 1), (0, 3), (1, 3), (2, 3))
_SELLING_ROWS = np.array([i for i, _ in _SELLING_PAIRS])
_SELLING_COLS = np.array([j for _, j in _SELLING_PAIRS])
_SELLING_START = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [-1, -1, -1]],
                          dtype=np.int64)
#: A reduction that has not finished in this many steps is not a lattice any
#: engine returns; the pair keeps the answer of the vectors as given.
_SELLING_STEPS = 1000


def _four_permutations() -> tuple[np.ndarray, np.ndarray]:
    """The 24 relabellings of a, b, c, d and where each sends the six scalars.

    Relabelling the four vectors by σ gives s'_(ij) = s_(σi σj): every one of
    the 24 is the same lattice, and in the six coordinates a permutation, so an
    isometry (2019, A75, 115, § 3; A75, 593, § 2)."""
    from itertools import permutations
    index = {frozenset(p): k for k, p in enumerate(_SELLING_PAIRS)}
    perms = np.array(list(permutations(range(4))), dtype=np.int64)
    moved = np.array([[index[frozenset((int(sg[i]), int(sg[j])))]
                       for i, j in _SELLING_PAIRS] for sg in perms])
    return perms, moved


_FOUR_PERMUTATIONS, _PERMUTED_SCALARS = _four_permutations()


def _selling_scalars(v4: np.ndarray, g: np.ndarray) -> np.ndarray:
    """The six scalars of four vectors (integer rows) under direct metric g."""
    return (v4 @ g @ v4.T)[_SELLING_ROWS, _SELLING_COLS]


def _selling_step(v4: np.ndarray, p: int) -> np.ndarray:
    """Selling's step on the pair p = (i, j): v_i → −v_i, v_j kept, and the
    other two each gain v_i, so the four still sum to zero.

    On s1 > 0 it gives (−s1, s2 + s1, s5 + s1, s4 − s1, s3 + s1, s6 + s1),
    which is the first form Andrews, Bernstein & Sauter (2019), A75, 115, § 4
    print.  Applied while a scalar is positive it is the reduction; applied at
    a scalar near zero it is the boundary the reduction turns on, where its
    only effect is to exchange two of the other scalars."""
    i, j = _SELLING_PAIRS[p]
    k, m = (q for q in range(4) if q not in (i, j))
    out = v4.copy()
    out[i] = -v4[i]
    out[k] = v4[k] + v4[i]
    out[m] = v4[m] + v4[i]
    return out


def _selling_vectors(g: np.ndarray) -> np.ndarray | None:
    """The four Selling-reduced vectors (integer rows in the input basis):
    each step takes the largest positive scalar until none is, zero counting
    as negative.  Each step lowers −Σs by 2s, so it terminates."""
    v4 = _SELLING_START
    tiny = 1e-12 * float(np.trace(g))
    for _ in range(_SELLING_STEPS):
        s = _selling_scalars(v4, g)
        p = int(np.argmax(s))
        if s[p] <= tiny:
            return v4
        v4 = _selling_step(v4, p)
    return None


@dataclass(frozen=True)
class _SellingForm:
    g: np.ndarray        # direct metric of the reduced A..F
    dg: np.ndarray       # (6, 3, 3): dG/d(A..F), from dG = −G·dG*·G
    v4: np.ndarray       # the Selling-reduced four vectors
    s: np.ndarray        # their six scalars
    order: np.ndarray    # argsort of s
    jac: np.ndarray      # (6, 6): ds/d(A..F)
    scale: float         # trace of g


@lru_cache(maxsize=16384)
def _selling_form(red: bytes) -> _SellingForm | None:
    """The Selling form of a reduced A..F vector, or ``None`` for a metric
    that is no lattice.  Keyed by the vector's bytes: dedup asks it of each
    kept group over and over."""
    from .qspace import gstar_from_af
    gstar = gstar_from_af(np.frombuffer(red, dtype=np.float64))
    if not np.all(np.isfinite(gstar)) or not np.all(np.linalg.eigvalsh(gstar) > 0.0):
        return None
    g = np.linalg.inv(gstar)
    v4 = _selling_vectors(g)
    if v4 is None:
        return None
    dg = np.stack([-g @ gstar_from_af(e) @ g for e in np.eye(6)])
    s = _selling_scalars(v4, g)
    jac = np.column_stack([_selling_scalars(v4, d) for d in dg])
    return _SellingForm(g, dg, v4, s, np.argsort(s, kind="stable"), jac,
                        float(np.trace(g)))


@lru_cache(maxsize=16384)
def _selling_variance(red: bytes, cov: bytes) -> np.ndarray:
    """The six Selling scalars' variances, linearly propagated from cov."""
    form = _selling_form(red)
    c = np.frombuffer(cov, dtype=np.float64).reshape(6, 6)
    return np.clip(np.einsum("ki,ij,kj->k", form.jac, c, form.jac), 0.0, None)


def _option_variance(form: _SellingForm, v4: np.ndarray,
                     cov: np.ndarray | None) -> np.ndarray | None:
    if cov is None:
        return None
    # ds_p/d(A..F)_e = v_i·dG_e·v_j for each Selling pair p = (i, j)
    jac = np.einsum("ai,eij,bj->abe", v4, form.dg, v4)[_SELLING_ROWS, _SELLING_COLS]
    return np.clip(np.einsum("ki,ij,kj->k", jac, cov, jac), 0.0, None)


def _selling_options(form: _SellingForm, near: float, depth: int
                     ) -> list[np.ndarray]:
    """The reduced four vectors and their images through every boundary whose
    scalar lies within ``near`` of zero, to ``depth`` steps, without repeats
    (one set of four up to order and overall sign is one description)."""
    out, frontier, seen = [], [form.v4], set()
    for level in range(depth + 1):
        nxt = []
        for v4 in frontier:
            key = min(tuple(sorted(map(tuple, v4.tolist()))),
                      tuple(sorted(map(tuple, (-v4).tolist()))))
            if key in seen:
                continue
            seen.add(key)
            out.append(v4)
            if level < depth:
                s = _selling_scalars(v4, form.g)
                nxt += [_selling_step(v4, p) for p in range(6) if abs(s[p]) <= near]
        frontier = nxt
    return out


#: A..F slot → (row, column) of G*, and the factor 2 on D, E, F
_AF_ROW = np.array([0, 1, 2, 1, 0, 0])
_AF_COL = np.array([0, 1, 2, 2, 2, 1])
_AF_TWO = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 2.0])


def _af_maps(ns: np.ndarray) -> np.ndarray:
    """(k, 6, 6): :func:`af_map` of a stack of integer changes of basis.

    G*' = A·G*·Aᵀ with A = N⁻ᵀ, so slot q of the new A..F takes slot p of the
    old with weight (f_q / f_p)·(A_ik·A_jl + A_il·A_jk [k ≠ l]), (i, j) and
    (k, l) the G* entries of q and p.  Held equal to :func:`af_map` by test."""
    a = np.rint(np.linalg.inv(ns.astype(np.float64))).transpose(0, 2, 1)
    ai, aj = a[:, _AF_ROW, :], a[:, _AF_COL, :]
    t = ai[:, :, _AF_ROW] * aj[:, :, _AF_COL]
    t += (ai[:, :, _AF_COL] * aj[:, :, _AF_ROW]) * (_AF_ROW != _AF_COL)
    return t * (_AF_TWO[:, None] / _AF_TWO[None, :])


@lru_cache(maxsize=16384)
def _gate_inputs_of(red: bytes, cov: bytes | None) -> np.ndarray | None:
    form = _selling_form(red)
    if form is None:
        return None
    if cov is None:
        var = np.full(6, np.nan)
    else:
        var = _selling_variance(red, cov)[form.order]
    out = np.concatenate([form.s[form.order], var,
                          [form.scale, float(np.max(var)) if cov is not None else np.nan]])
    out.setflags(write=False)
    return out


def _gate_inputs(red, cov) -> np.ndarray | None:
    """One reduced vector's Selling gate inputs, packed so a batch stacks in one
    call: the six scalars sorted, their variances (NaN without a covariance), the
    metric's trace, and the largest variance.  ``None`` for a metric that is no
    lattice."""
    red = np.ascontiguousarray(red, dtype=np.float64).tobytes()
    if cov is None:
        return _gate_inputs_of(red, None)
    return _gate_inputs_of(red, np.ascontiguousarray(cov, dtype=np.float64).tobytes())


def _selling_gate(mine: np.ndarray, theirs: np.ndarray) -> np.ndarray:
    """Step 1 of :func:`_equal_across_boundaries`, for one pair (``theirs`` of
    shape (14,)) or a stack ((k, 14)): does each sorted Selling scalar agree
    within the gate?  Elementwise only, so a stack's answer is each pair's own."""
    big = np.maximum(mine[12], theirs[..., 12])[..., None]
    var = mine[6:12] + theirs[..., 6:12]
    with np.errstate(invalid="ignore"):
        tol = np.where(np.isnan(var), SELLING_GATE_RELATIVE * big,
                       SELLING_GATE_SIGMAS * np.sqrt(var) + 1e-9 * big)
    return np.all(np.abs(mine[:6] - theirs[..., :6]) <= tol, axis=-1)


def _equal_across_boundaries(red_a, red_b, cov_a, cov_b, *, gated: bool = False
                             ) -> tuple[bool, float] | None:
    """Is some other description of b, across the reduction's boundaries, equal
    to a by :func:`equal_reduced`'s own test?  (True, its χ²) if so, else
    ``None``, and the caller keeps the answer of the vectors as given (WP-1932).

    The comparison is made in **Selling's form** rather than Niggli's
    (Andrews, Bernstein & Sauter 2019, *Acta Cryst.* A75, 115 and 593): its
    reduced region is bounded by six hyperplanes of one kind, s_ij = 0, and
    the 24 descriptions of one reduced lattice are permutations of the six
    scalars, where Niggli's cone has fifteen boundaries of five kinds with
    maps that stretch the space (Andrews & Bernstein 2014, *J. Appl. Cryst.*
    47, 346).  Measured on #834's splits, the S6 images joined 608 of 608 and
    an NCDIST-style set of Niggli boundary images 595.

    1. **Gate.**  The six scalars sorted are a lattice invariant continuous
       across every boundary: a relabelling permutes them, and the step at
       s_ij = 0 only exchanges two others.  Unless each sorted scalar agrees
       within :data:`SELLING_GATE_SIGMAS` of its esd (or
       :data:`SELLING_GATE_RELATIVE` of the trace without covariances), no
       description can pass, and the pair is not looked at again.
    2. **Images.**  a's Selling vectors and their steps through each scalar
       within the gate of zero (one step), against b's (two steps), under the
       24 relabellings; those whose six scalars agree slot by slot within the
       same gate are kept.  Each is an exact unimodular change of basis N of
       b's reduced basis, carried to A..F by :func:`af_map`'s map.
    3. **Verdict.**  :func:`equal_reduced`'s own test on (a, T·b) under
       Σa + T·Σb·Tᵀ.  Never the distance over its esd: projected on one
       direction, that merged pairs this χ² keeps apart (spike
       wp1932-build-20261013: 76 of 76 such merges on real distinct pairs
       were refused by an oracle that searches every basis).
    """
    try:
        red_a = np.ascontiguousarray(red_a, dtype=np.float64)
        red_b = np.ascontiguousarray(red_b, dtype=np.float64)
        fa, fb = _selling_form(red_a.tobytes()), _selling_form(red_b.tobytes())
        if fa is None or fb is None:
            return None
        floor = 1e-9 * max(fa.scale, fb.scale)
        with_cov = cov_a is not None and cov_b is not None
        mine = _gate_inputs(red_a, cov_a if with_cov else None)
        theirs = _gate_inputs(red_b, cov_b if with_cov else None)
        if not gated and not bool(_selling_gate(mine, theirs)):
            return None
        if with_cov:
            cov_a = np.ascontiguousarray(cov_a, dtype=np.float64)
            cov_b = np.ascontiguousarray(cov_b, dtype=np.float64)
            near = SELLING_GATE_SIGMAS * float(np.sqrt(mine[13] + theirs[13])) + floor
        else:
            near = SELLING_GATE_RELATIVE * max(fa.scale, fb.scale)
        ns = []
        options_b = [(v4, _selling_scalars(v4, fb.g),
                      _option_variance(fb, v4, cov_b if with_cov else None))
                     for v4 in _selling_options(fb, near, _SELLING_DEPTH[1])]
        for v4a in _selling_options(fa, near, _SELLING_DEPTH[0]):
            s_a = _selling_scalars(v4a, fa.g)
            v_a = _option_variance(fa, v4a, cov_a if with_cov else None)
            back = np.rint(np.linalg.inv(v4a[:3].astype(np.float64))).astype(np.int64)
            for v4b, s_b, v_b in options_b:
                gap = np.abs(s_a - s_b[_PERMUTED_SCALARS])
                lim = (SELLING_GATE_SIGMAS * np.sqrt(v_a + v_b[_PERMUTED_SCALARS])
                       + floor if with_cov else near)
                for k in np.flatnonzero(np.all(gap <= lim, axis=1)):
                    ns.append(back @ v4b[_FOUR_PERMUTATIONS[k]][:3])
        if not ns:
            return None
        ts = _af_maps(np.stack(ns))
        images = ts @ red_b
        deltas = red_a - images
        if not with_cov:
            # the same rounding-level floor as `_equal_as_given`, per image row:
            # a monoclinic image's D, E are noise against noise (WP-2035)
            scale = np.maximum(np.abs(red_a), np.abs(images))
            scale = np.maximum(scale, 1e-12 * scale.max(axis=1, keepdims=True))
            ok = np.all(np.abs(deltas) <= CELL_EQUALITY_RELATIVE * scale, axis=1)
            return (True, float("nan")) if bool(np.any(ok)) else None
        sigmas = cov_a + ts @ cov_b @ ts.transpose(0, 2, 1)
        chi2 = np.einsum("ki,kij,kj->k", deltas,
                         _psd_pinv(sigmas, CELL_PINV_RCOND), deltas)
        best = int(np.argmin(chi2))
        return (True, float(chi2[best])) if chi2[best] <= CELL_EQUALITY_CHI2 else None
    except (ValueError, np.linalg.LinAlgError):
        return None


_STACKED_PINV: bool | None = None


def stacked_pinv_exact() -> bool:
    """Does :func:`equal_reduced_many` give every pair :func:`equal_reduced`'s
    own χ², bit for bit, on this machine?  Asked once a process.

    It should.  numpy sends a stack through the same gufunc loop, one LAPACK
    ``syevd`` per matrix, and the rest of ``_psd_pinv`` is elementwise or one 6×6
    product per matrix.  Measured on OpenBLAS 0.3.34 (numpy 2.5.3, Linux
    x86-64), every one of the 573 605 χ² tests on corundum's tetragonal unit
    came back the same double, stacked per candidate (WP-1519).  But nothing promises this of every
    LAPACK and BLAS, and WP-1509 found numpy routing a (1, 6) product to a
    different kernel than its neighbours took (``engines.row_local_product``).
    So it is **measured here**, on witnesses shaped like dedup's own Σ: sums
    of two rank-deficient covariances of A..F, whose near-zero eigenvalues sit
    at ``pinv``'s cutoff, where a last-bit difference changes which directions
    survive.  A machine where any χ² differs keeps the per-pair loop, and the
    groups are exactly what they always were, only slower.
    """
    global _STACKED_PINV
    if _STACKED_PINV is None:
        rng = np.random.default_rng(1519)
        ok = True
        # dedup's own stack sizes among them: ``engines.DEDUP_STACK_FIRST``,
        # then four times the last, through 1024
        for size in (1, 2, 3, 5, 8, 16, 17, 64, 129, 256, 1024):
            red_a = rng.uniform(0.002, 0.05, 6)
            cov_a = _witness_covariance(rng)
            reds_b = [red_a + rng.normal(0.0, 1e-6, 6) for _ in range(size)]
            covs_b = [_witness_covariance(rng) for _ in range(size)]
            stacked = equal_reduced_many(red_a, reds_b, cov_a=cov_a,
                                         covs_b=covs_b)
            if stacked != [equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)
                           for red_b, cov_b in zip(reds_b, covs_b)]:
                ok = False
                break
        _STACKED_PINV = ok
    return _STACKED_PINV


def _witness_covariance(rng: np.random.Generator) -> np.ndarray:
    """A covariance of A..F of rank 1-6, as a tied or fixed metric leaves one."""
    g = rng.normal(0.0, 1e-6, (6, int(rng.integers(1, 7))))
    return g @ g.T


def same_lattice(af_a: np.ndarray, af_b: np.ndarray, *,
                 cov_a: np.ndarray | None = None,
                 cov_b: np.ndarray | None = None) -> tuple[bool, float]:
    """Are these two A..F vectors the same lattice?  Returns (verdict, χ²).

    Both are Niggli-reduced first, so a *setting* change is equality rather than
    ambiguity — which is the whole reason dedup and geometrical ambiguity
    (WP-1020's ``ambiguity.py``) are different questions.  With covariances the
    test is χ² = ΔᵀΣ⁻¹Δ against :data:`CELL_EQUALITY_CHI2`, each covariance
    given in its own vector's frame and carried through its own reduction;
    without, it falls back to :data:`CELL_EQUALITY_RELATIVE` on the reduced cell
    parameters and the returned χ² is NaN so a caller can see which test ran.
    """
    if cov_a is None or cov_b is None:
        return equal_reduced(reduced_af(af_a), reduced_af(af_b))
    red_a, t_a = reduction(af_a)
    red_b, t_b = reduction(af_b)
    return equal_reduced(red_a, red_b, cov_a=reduced_covariance(cov_a, t_a),
                         cov_b=reduced_covariance(cov_b, t_b))


__all__ = ["BRAVAIS_OBLIQUITIES", "BRAVAIS_SYMPREC_SIGMAS",
           "CELL_EQUALITY_CHI2", "CELL_EQUALITY_RELATIVE", "SELLING_GATE_RELATIVE",
           "SELLING_GATE_SIGMAS", "SYSTEM_RANK",
           "BravaisScreen", "ReducedCell", "af_map", "bravais_screen",
           "cell_from_vectors", "conventional_cell", "conventional_setting", "equal_reduced", "lattice_vectors",
           "reduce_cell", "reduced_af", "reduced_covariance", "reduction",
           "same_lattice"]
