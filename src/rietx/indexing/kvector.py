"""The k-grid and its scores: machinery for a propagation-vector search (WP-1418 M-8, K1a).

A phase that orders with a propagation vector **k** puts intensity at
Q = H + m·k for every vector H of its reciprocal lattice L*.  When the parent
is known, a satellite list is a set of *positions*, and asking whether a list
of unexplained peaks is the satellite set of some k is a position hypothesis
against a known lattice (issue #795).  This module gives each step of that
question as a public call an agent composes by hand:

* :func:`kgrid_strata` enumerates the rational k on a grid of step 1/n, one
  representative per class of positions, sorted into strata by the order of
  the little group;
* :func:`kgrid_positions` builds the satellite positions of every k on such a
  grid once, through the existing exact generator
  (:func:`~rietx.crystallography.satellites.satellite_d_spacings`), so that
  several scorings share one build;
* :func:`score_kvector` scores one k the caller names against the peaks;
* :func:`score_kgrid` scores every k of the strata it is given;
* :func:`kgrid_null` measures, for one pattern, the grid maximum of the score
  under shuffles of the peak positions, and reports the whole sample;
* :func:`kvector_equivalents` lists what the positions cannot separate from a
  k: the arms of its star, −k, and the images of k under the metric's
  near-symmetries.

**Nothing here ranks, chooses, warns on a threshold or bounds the search by a
default.**  No call sorts by score, returns a single best row, or compares a
score with the null.  The match radius, the grid's denominator, the strata, the
band, the null's exclusion windows, its shuffle count, its percentile and its
seed are all required arguments.  The ranking, ``best_or_none()`` and the
warnings that read a margin are the heuristic's (issue #795, K1b).

**What a grid record claims, and what it does not** (the maintainer's
condition on issue #795, 2026-11-11).  The grid holds rational k whose
components are multiples of 1/n, n ≤
:data:`~rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR`.  At
n = 64 neighbouring points are 1/64 ≈ 0.016 apart, while a 0.12° match radius
on a CW-neutron pattern resolves a line k to about ±0.004 (measured on the
synthetic patterns this module's tests are built from), so a general k between
grid points can score near chance on every grid point.  Every grid-level record
(:class:`KGridScores`, :class:`KNull`) therefore carries the grid step as a
number, the strata it searched and the strata a budget left, and states in its
``coverage`` field that it makes **no claim about any k off the grid**.

**Every class of k is reduced modulo the phase's own reciprocal lattice,
centring included** (#1071): on F m m m, (1, 0, 0) and (0, 1, 1) are one k, and
the three X points are three stars.

Clean room: the design follows the literature and our own spikes (issue #795):
de Wolff (1968) for the chance rate, Mighell & Santoro (1975) for the
geometrical ambiguity.  No other program's source was read.
"""

from __future__ import annotations

import math
import operator
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import lru_cache
from typing import Literal

import gemmi
import numpy as np

from ..crystallography.lattice import direct_metric_tensor
from ..crystallography.representation.irreps import (
    K_MAX_DENOMINATOR,
    KVector,
    as_kvector,
    canonical_kvector,
    equivalent_kvectors,
    primitive_basis,
    star,
)
from ..crystallography.satellites import (
    format_kvector,
    lattice_two_theta,
    reciprocal_lattice_mask,
    satellite_d_spacings,
)
from ..crystallography.symmetry import get_spacegroup
from ..crystallography.wyckoff import _nullspace_int
from ..schemas.common import Diagnostic
from .ambiguity import lattice_point_group
from .reduce import reduce_cell

__all__ = [
    "KParent",
    "KPeaks",
    "KStratum",
    "KGridPositions",
    "KScore",
    "KGridRow",
    "KGridScores",
    "KNull",
    "KEquivalent",
    "KEquivalents",
    "as_kpeaks",
    "kgrid_strata",
    "kgrid_positions",
    "score_kvector",
    "score_kgrid",
    "kgrid_null",
    "kvector_equivalents",
]

StratumKind = Literal["point", "line", "plane", "general"]
_KINDS: tuple[StratumKind, ...] = ("point", "line", "plane", "general")

# Positions of different k are laid end to end on one axis, each block shifted
# by this many degrees, so one ``searchsorted`` locates a peak in every k's own
# window list at once.  It only has to exceed the 2θ axis plus the pad below.
_BLOCK = 2000.0
# Where an unused slot of a padded window row sits, inside its block and past
# any 2θ, so no peak ever locates it.
_PAD = 900.0
# Rows scored per vectorised block: bounds the working memory, not the answer.
_CHUNK = 2048


# --------------------------------------------------------------------------
# the inputs
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class KParent:
    """The known parent a k is a hypothesis against.

    ``space_group`` is any symbol gemmi resolves (stored as its extended
    Hermann-Mauguin symbol), ``cell`` the six conventional constants in Å and
    degrees, ``wavelength`` in Å, and ``two_theta_min``/``two_theta_max`` the
    measured range in degrees.  Nothing is defaulted: the range is the
    pattern's own and bounds every chance rate below.
    """

    space_group: str
    cell: tuple[float, float, float, float, float, float]
    wavelength: float
    two_theta_min: float
    two_theta_max: float

    def __post_init__(self) -> None:
        sg = get_spacegroup(str(self.space_group))
        object.__setattr__(self, "space_group", sg.xhm())
        cell = tuple(float(c) for c in self.cell)
        if len(cell) != 6:
            raise ValueError(f"a cell has six constants, got {len(cell)}")
        object.__setattr__(self, "cell", cell)
        object.__setattr__(self, "wavelength", float(self.wavelength))
        lo, hi = float(self.two_theta_min), float(self.two_theta_max)
        if not 0.0 <= lo < hi <= 180.0:
            raise ValueError(f"2θ range [{lo}, {hi}] is not inside (0, 180]")
        object.__setattr__(self, "two_theta_min", lo)
        object.__setattr__(self, "two_theta_max", hi)

    @property
    def group(self) -> gemmi.SpaceGroup:
        return get_spacegroup(self.space_group)


@dataclass(frozen=True)
class KPeaks:
    """The unexplained peaks a k is scored against, in ° 2θ.

    Which peaks are "unexplained" is the caller's choice (the report arm's
    sort, a residual census, a paired pattern), never this module's.
    ``fwhm`` and ``tags`` are carried on every record for the reader and are
    **not used by any score**; a tag is a provenance label such as
    ``"persists_above"`` (issue #795, F1).
    """

    two_theta: tuple[float, ...]
    fwhm: tuple[float | None, ...] | None = None
    tags: tuple[str | None, ...] | None = None

    def __post_init__(self) -> None:
        tt = tuple(float(x) for x in self.two_theta)
        object.__setattr__(self, "two_theta", tt)
        for name in ("fwhm", "tags"):
            value = getattr(self, name)
            if value is not None:
                value = tuple(value)
                if len(value) != len(tt):
                    raise ValueError(f"{name} has {len(value)} entries for {len(tt)} peaks")
                object.__setattr__(self, name, value)

    def __len__(self) -> int:
        return len(self.two_theta)


def as_kpeaks(peaks) -> KPeaks:
    """A :class:`KPeaks` from one, from a ``PeakList``, or from 2θ positions.

    A :class:`~rietx.schemas.indexing.PeakList` contributes each peak's
    ``two_theta`` and ``fwhm``; an array-like is read as positions in ° 2θ.
    """
    if isinstance(peaks, KPeaks):
        return peaks
    rows = getattr(peaks, "peaks", None)
    if rows is not None:
        return KPeaks(two_theta=tuple(p.two_theta for p in rows),
                      fwhm=tuple(getattr(p, "fwhm", None) for p in rows))
    arr = np.asarray(peaks, dtype=np.float64).ravel()
    return KPeaks(two_theta=tuple(arr.tolist()))


def _peak_array(peaks: KPeaks, parent: KParent) -> np.ndarray:
    tt = np.asarray(peaks.two_theta, dtype=np.float64)
    out = (tt < parent.two_theta_min) | (tt > parent.two_theta_max) | ~np.isfinite(tt)
    if out.any():
        raise ValueError(
            f"{int(out.sum())} peak(s) lie outside the parent's 2θ range "
            f"[{parent.two_theta_min}, {parent.two_theta_max}] (first: "
            f"{float(tt[out][0])}); a chance rate is defined on the measured "
            "range only, so pass only peaks inside it")
    return tt


def _positive(value, name: str) -> float:
    v = float(value)
    if not (v > 0.0 and math.isfinite(v)):
        raise ValueError(f"{name} must be a positive number, got {value!r}")
    return v


def _harmonics(harmonics) -> tuple[int, ...]:
    out = tuple(operator.index(m) for m in harmonics)
    if not out or any(m < 1 for m in out) or len(set(out)) != len(out):
        raise ValueError(
            f"harmonics must be distinct positive orders, got {harmonics!r}: "
            "order m covers both satellites H ± m·k")
    return out


# --------------------------------------------------------------------------
# the lattice, in integers
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Lattice:
    """L* and the point group, as the integer arithmetic below needs them.

    ``a`` is N·M with M the rows of :func:`primitive_basis` and N their common
    denominator, so two k = j/n and j'/n are one k exactly when
    a·(j − j') ≡ 0 modulo n·N (M maps conventional reciprocal coordinates to
    primitive ones, where L* is the integer grid).  ``e`` is the smallest
    integer with e·Z³ ⊂ L*, and ``shifts`` the vectors of L* inside [−e, e]³.
    ``rt`` holds Rᵀ for every coset representative R of the group, in the
    order gemmi lists them (the order :func:`little_group` uses), and ``laue``
    the distinct ±Rᵀ.
    """

    a: np.ndarray
    nm: int
    e: int
    shifts: np.ndarray
    rt: np.ndarray
    laue: np.ndarray
    triplets: tuple[str, ...]


@lru_cache(maxsize=64)
def _lattice(xhm: str) -> _Lattice:
    sg = get_spacegroup(xhm)
    m = primitive_basis(sg)
    nm = 1
    for row in m:
        for c in row:
            nm = nm * c.denominator // math.gcd(nm, c.denominator)
    a = np.array([[int(c * nm) for c in row] for row in m], dtype=np.int64)
    e = next(e for e in range(1, 7)
             if reciprocal_lattice_mask(sg, e * np.eye(3, dtype=np.int64)).all())
    span = np.arange(-e, e + 1)
    box = np.array(np.meshgrid(span, span, span, indexing="ij")).reshape(3, -1).T
    shifts = box[reciprocal_lattice_mask(sg, box)].astype(np.int64)
    den = gemmi.Op.DEN
    rots, triplets = [], []
    for op in sg.operations().sym_ops:
        r = np.asarray(op.rot, dtype=np.int64) // den
        rots.append(r)
        bare = gemmi.Op("x,y,z")
        bare.rot = op.rot
        triplets.append(bare.triplet())
    rt = np.transpose(np.array(rots, dtype=np.int64), (0, 2, 1))
    laue = np.unique(np.concatenate([rt, -rt]).reshape(-1, 9), axis=0).reshape(-1, 3, 3)
    return _Lattice(a=a, nm=nm, e=e, shifts=shifts, rt=rt, laue=laue,
                    triplets=tuple(triplets))


def _class_codes(lat: _Lattice, j: np.ndarray, n: int, ops: np.ndarray) -> np.ndarray:
    """The smallest canonical code of j/n over ``ops`` images, per row.

    The code of one image is its primitive coordinates modulo L*, read as one
    integer, so two rows share a code exactly when they are one class.
    """
    mod = n * lat.nm
    best = None
    for op in ops:
        p = ((j @ op.T) @ lat.a.T) % mod
        code = (p[:, 0] * mod + p[:, 1]) * mod + p[:, 2]
        best = code if best is None else np.minimum(best, code)
    return best


def _shortest_spellings(lat: _Lattice, reps: np.ndarray, n: int) -> np.ndarray:
    """The shortest spelling of each class: least |k|₁, fewest minus signs,
    then the smallest tuple (``satellites._shortest_spelling_key``'s order).

    Searched over every Laue image of the class and every shift by L*: a
    component past n·e/2 can be shortened by n·e·eᵢ ∈ n·L* without touching
    the others, so the shortest spelling lies in [−n·e/2, n·e/2]³ and is
    reached from an image reduced into that box by a shift in n·(L* ∩ [−e, e]³).
    """
    ne = n * lat.e
    big = 2 * ne
    base = 2 * big + 1
    shifts = n * lat.shifts
    out = np.empty_like(reps)
    for lo in range(0, len(reps), 512):
        block = reps[lo:lo + 512]
        img = np.einsum("lab,mb->mla", lat.laue, block)
        img = img % ne
        img = np.where(img > ne // 2, img - ne, img)
        cand = (img[:, :, None, :] + shifts[None, None, :, :]).reshape(len(block), -1, 3)
        l1 = np.abs(cand).sum(axis=2)
        neg = (cand < 0).sum(axis=2)
        lex = ((cand[..., 0] + big) * base + (cand[..., 1] + big)) * base + (cand[..., 2] + big)
        key = (l1 * 4 + neg) * base ** 3 + lex
        pick = np.argmin(key, axis=1)
        out[lo:lo + 512] = cand[np.arange(len(block)), pick]
    return out


def _cogroup_masks(lat: _Lattice, reps: np.ndarray, n: int) -> np.ndarray:
    """Bit i set when Rᵢᵀk ≡ k modulo L*: the little co-group, per row."""
    mod = n * lat.nm
    mask = np.zeros(len(reps), dtype=np.int64)
    for i, op in enumerate(lat.rt):
        diff = reps @ op.T - reps
        fixed = np.all((diff @ lat.a.T) % mod == 0, axis=1)
        mask |= fixed.astype(np.int64) << i
    return mask


# --------------------------------------------------------------------------
# 1. the grid, by stratum
# --------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class KStratum:
    """The grid points that share one little co-group.

    ``little_group_order`` is |P_k|, the order
    :func:`~rietx.crystallography.representation.irreps.little_group` reports
    at every member; ``operations`` are the rotation parts of P_k as
    ``x,y,z`` triplets and ``operation_indices`` their positions in the
    parent's operation list, which is what identifies the stratum.
    ``n_free`` is the dimension of the subspace P_k leaves fixed, so 0 at a
    point, 1 on a line, 2 on a plane and 3 for a general k; ``free_directions``
    is an integer basis of it, and ``fixed_components`` says which conventional
    components the stratum's symmetry fixes (those stay exactly rational for
    any k on the locus; the others are the free parameters a real k would
    refine).  ``kvectors`` are the representatives in their stated order,
    exact.  ``denominator`` is the grid's n and ``grid_step`` = 1/n, in
    conventional reciprocal coordinates.

    A stratum lists grid points only: it says nothing about the k off the grid
    that lie on the same locus.
    """

    name: str
    kind: StratumKind
    space_group: str
    little_group_order: int
    operations: tuple[str, ...]
    operation_indices: tuple[int, ...]
    n_free: int
    free_directions: tuple[tuple[int, int, int], ...]
    fixed_components: tuple[bool, bool, bool]
    kvectors: tuple[KVector, ...]
    n_points: int
    denominator: int
    grid_step: float

    def __repr__(self) -> str:
        return (f"KStratum({self.name!r}, {self.kind}, |P_k|={self.little_group_order}, "
                f"{self.n_points} k at step 1/{self.denominator})")


def kgrid_strata(space_group, *, denominator: int) -> tuple[KStratum, ...]:
    """The rational k of step 1/``denominator``, one per class, by stratum.

    **The grid** is every k whose conventional components are multiples of
    1/n, n = ``denominator`` (so it holds the rationals whose denominators
    divide n: 1/3 is on the 1/48 grid and not on the 1/64 one), minus k ≡ 0.
    n is required and refused above
    :data:`~rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR`.

    **One representative per class.**  Two k are one class when they give the
    same satellite positions for every parent of this group: k′ ≡ ±Rᵀk modulo
    L* for some operation R, which is the star, −k and G − k at once, with L*
    the reciprocal lattice of the group's *own*, centred lattice (#1071).  The
    representative is the class's shortest spelling: least |k|₁ in
    conventional components, then fewest negative components, then the
    smallest tuple (the convention
    :func:`~rietx.crystallography.satellites.zone_boundary_candidates` uses).
    On a P lattice of point group mmm that is the wedge [0, ½]³.

    **Strata are derived, never tabulated**: a stratum is the set of
    representatives sharing one little co-group P_k = {R : Rᵀk ≡ k mod L*},
    computed at the representative.  Its order is |P_k| and its number of free
    components the dimension of the subspace P_k fixes.

    **Order, a stated listing convention and not a search order**: strata by
    number of free components (points first), then by decreasing |P_k|, then
    by the bit set of their operation indices; within a stratum, k by their
    exact tuples.  The order a search visits strata in is the caller's
    (:func:`score_kgrid` keeps the order it is handed).

    Cost: the classes are found in integer arithmetic over one cell of e·Z³
    ⊂ L* ((n·e)³ points), so a centred lattice costs (e³/N)× a primitive one.

    What this does **not** do: it does not rank, does not choose, and makes no
    statement about any k off the grid.
    """
    n = operator.index(denominator)
    if n < 1:
        raise ValueError(f"denominator must be a positive integer, got {denominator!r}")
    if n > K_MAX_DENOMINATOR:
        raise ValueError(
            f"denominator {n} exceeds K_MAX_DENOMINATOR = {K_MAX_DENOMINATOR}, the "
            "largest a commensurate k is read with; a finer search is a real-k search")
    sg = space_group if isinstance(space_group, gemmi.SpaceGroup) else get_spacegroup(str(space_group))
    return _kgrid_strata(sg.xhm(), n)


@lru_cache(maxsize=16)
def _kgrid_strata(xhm: str, n: int, *, centred: bool = True,
                  minus_k: bool = True) -> tuple[KStratum, ...]:
    """:func:`kgrid_strata`'s body.  ``centred=False`` and ``minus_k=False``
    exist for the negative controls alone: they reduce modulo Z³ instead of
    L*, or over +Rᵀ only, and the brute-force check must then fail."""
    lat = _lattice(xhm)
    if not centred:
        lat = _Lattice(a=np.eye(3, dtype=np.int64), nm=1, e=1,
                       shifts=np.array(np.meshgrid(*[np.arange(-1, 2)] * 3, indexing="ij")
                                       ).reshape(3, -1).T.astype(np.int64),
                       rt=lat.rt, laue=lat.laue, triplets=lat.triplets)
    if not minus_k:
        lat = _Lattice(a=lat.a, nm=lat.nm, e=lat.e, shifts=lat.shifts, rt=lat.rt,
                       laue=np.unique(lat.rt.reshape(-1, 9), axis=0).reshape(-1, 3, 3),
                       triplets=lat.triplets)
    side = n * lat.e
    span = np.arange(side, dtype=np.int64)
    cube = np.array(np.meshgrid(span, span, span, indexing="ij")).reshape(3, -1).T
    codes = np.concatenate([_class_codes(lat, cube[i:i + 65536], n, lat.laue)
                            for i in range(0, len(cube), 65536)])
    keys, first = np.unique(codes, return_index=True)
    reps = cube[first[keys != 0]]
    reps = _shortest_spellings(lat, reps, n)
    masks = _cogroup_masks(lat, reps, n)

    strata = []
    for mask in np.unique(masks):
        idx = tuple(i for i in range(len(lat.rt)) if (int(mask) >> i) & 1)
        rows = [[Fraction(int(x)) for x in (lat.rt[i] - np.eye(3, dtype=np.int64))[r]]
                for i in idx for r in range(3)]
        basis = _nullspace_int(rows, 3)
        free = tuple(tuple(int(x) for x in v) for v in basis)
        n_free = len(free)
        fixed = tuple(all(v[c] == 0 for v in free) for c in range(3))
        members = reps[masks == mask]
        order = np.lexsort((members[:, 2], members[:, 1], members[:, 0]))
        ks = tuple((Fraction(int(a), n), Fraction(int(b), n), Fraction(int(c), n))
                   for a, b, c in members[order])
        kind = _KINDS[n_free]
        strata.append(KStratum(
            name=f"{kind}-{len(idx)}-{int(mask):x}", kind=kind, space_group=xhm,
            little_group_order=len(idx), operations=tuple(lat.triplets[i] for i in idx),
            operation_indices=idx, n_free=n_free, free_directions=free,
            fixed_components=fixed, kvectors=ks, n_points=len(ks),
            denominator=n, grid_step=1.0 / n))
    strata.sort(key=lambda s: (s.n_free, -s.little_group_order,
                               sum(1 << i for i in s.operation_indices)))
    return tuple(strata)


# --------------------------------------------------------------------------
# positions and windows
# --------------------------------------------------------------------------

def _reduced(lat: _Lattice, k: KVector) -> KVector:
    """k shifted by e·Z³ ⊂ L* into (−e/2, e/2]³: the same positions, and the
    parent grid of ``satellite_d_spacings`` then reaches every satellite."""
    e = lat.e
    out = []
    for c in k:
        r = c - e * math.floor(c / e)
        if r > Fraction(e, 2):
            r -= e
        out.append(r)
    return tuple(out)  # type: ignore[return-value]


def _two_theta(d: np.ndarray, wavelength: float) -> np.ndarray:
    s = wavelength / (2.0 * d)
    return np.degrees(2.0 * np.arcsin(np.clip(s, -1.0, 1.0)))


def _positions(parent: KParent, ks: Sequence[KVector],
               harmonics: tuple[int, ...]) -> list[np.ndarray]:
    """Sorted distinct 2θ in range of the satellites of each k, every order m
    in ``harmonics`` (H ± m·k).  An order whose m·k ≡ 0 puts its satellites on
    the reciprocal-lattice points, which are taken from
    :func:`~rietx.crystallography.satellites.lattice_two_theta`."""
    sg = parent.group
    lat = _lattice(parent.space_group)
    lo, hi = parent.two_theta_min, parent.two_theta_max
    per_k: list[list[np.ndarray]] = [[] for _ in ks]
    lattice_pts = None
    for m in harmonics:
        mk = [_reduced(lat, tuple(m * c for c in k)) for k in ks]  # type: ignore[misc]
        zero = [equivalent_kvectors(sg, v, (0, 0, 0)) for v in mk]
        live = [i for i, z in enumerate(zero) if not z]
        if live:
            ds = satellite_d_spacings(sg, parent.cell, parent.wavelength, hi,
                                      [mk[i] for i in live], lo)
            for i, d in zip(live, ds):
                per_k[i].append(_two_theta(d, parent.wavelength))
        if any(zero):
            if lattice_pts is None:
                lattice_pts = lattice_two_theta(sg, parent.cell, parent.wavelength, hi, lo)
            for i, z in enumerate(zero):
                if z:
                    per_k[i].append(lattice_pts)
    out = []
    for parts in per_k:
        tt = np.unique(np.concatenate(parts)) if parts else np.zeros(0)
        out.append(tt[(tt >= lo) & (tt <= hi)])
    return out


def _windows(pos: Sequence[np.ndarray], radius: float, lo: float, hi: float):
    """Padded (rows, W) arrays of the merged ±radius windows of each row:
    starts, ends, and the exclusive running sum of their lengths.  Unused
    slots start at ``_PAD`` with zero length, so no peak locates them."""
    counts = []
    starts_l, ends_l = [], []
    for x in pos:
        if len(x) == 0:
            starts_l.append(np.zeros(0))
            ends_l.append(np.zeros(0))
            counts.append(0)
            continue
        brk = np.flatnonzero(np.diff(x) > 2.0 * radius)
        first = np.concatenate([[0], brk + 1])
        last = np.concatenate([brk, [len(x) - 1]])
        starts_l.append(np.maximum(x[first] - radius, lo))
        ends_l.append(np.minimum(x[last] + radius, hi))
        counts.append(len(first))
    w = max(max(counts, default=0), 1)
    s = np.full((len(pos), w), _PAD)
    e = np.full((len(pos), w), _PAD)
    for i, (a, b) in enumerate(zip(starts_l, ends_l)):
        s[i, :len(a)] = a
        e[i, :len(b)] = b
    cumex = np.zeros_like(s)
    cumex[:, 1:] = np.cumsum(e - s, axis=1)[:, :-1]
    return s, e, cumex


def _locate(s: np.ndarray, x: np.ndarray) -> np.ndarray:
    """(rows, len(x)) index of the last window starting at or before each x,
    in each row's own list; −1 where there is none."""
    rows, w = s.shape
    flat = (s + (np.arange(rows) * _BLOCK)[:, None]).ravel()
    q = x[None, :] + (np.arange(rows) * _BLOCK)[:, None]
    j = np.searchsorted(flat, q.ravel(), side="right").reshape(rows, len(x)) - 1
    return j - (np.arange(rows) * w)[:, None]


def _covered_to(s, e, cumex, j, x) -> np.ndarray:
    """The windows' covered length from the range start up to each x."""
    rows = np.arange(s.shape[0])[:, None]
    jj = np.maximum(j, 0)
    part = np.clip(x[None, :] - s[rows, jj], 0.0, e[rows, jj] - s[rows, jj])
    return np.where(j >= 0, cumex[rows, jj] + part, 0.0)


def _poisson_binomial_tail(p: np.ndarray, n: np.ndarray) -> np.ndarray:
    """P(X ≥ nᵣ) for X a sum of independent Bernoulli(p_rᵢ), one per row.

    The exact distribution by the convolution recursion, then the tail summed
    from its far end, so no term is lost to cancellation.
    """
    rows, big_n = p.shape
    dist = np.zeros((rows, big_n + 1))
    dist[:, 0] = 1.0
    for i in range(big_n):
        pi = p[:, i:i + 1]
        new = dist * (1.0 - pi)
        new[:, 1:] += dist[:, :-1] * pi
        dist = new
    tail = np.cumsum(dist[:, ::-1], axis=1)[:, ::-1]
    return tail[np.arange(rows), np.clip(n, 0, big_n)]


def _score_rows(windows, tt: np.ndarray, lo: float, hi: float, band: float):
    """matched (rows, N) bool, p (rows, N), n (rows,), P (rows,), score (rows,)."""
    s, e, cumex = windows
    rows = np.arange(s.shape[0])[:, None]
    if len(tt) == 0:
        z = np.zeros((s.shape[0], 0))
        ones = np.ones(s.shape[0])
        return z.astype(bool), z, np.zeros(s.shape[0], dtype=np.int64), ones, 0.0 * ones
    j = _locate(s, tt)
    jj = np.maximum(j, 0)
    matched = (j >= 0) & (tt[None, :] <= e[rows, jj])
    a = np.maximum(lo, tt - band)
    b = np.minimum(hi, tt + band)
    covered = (_covered_to(s, e, cumex, _locate(s, b), b)
               - _covered_to(s, e, cumex, _locate(s, a), a))
    p = np.clip(covered / (b - a)[None, :], 0.0, 1.0)
    n = matched.sum(axis=1)
    big_p = _poisson_binomial_tail(p, n)
    with np.errstate(divide="ignore"):
        score = -np.log10(big_p)
    return matched, p, n, big_p, score


# --------------------------------------------------------------------------
# 2. the score of one k
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class KScore:
    """One k scored against one peak list (:func:`score_kvector`).

    ``n_matched`` (n) of ``n_peaks`` (N) peaks lie within ``radius`` of a
    satellite of the orders in ``harmonics``; ``matched``/``unmatched`` are
    their indices into ``peaks``.  ``p`` holds every pᵢ, the share of the
    ±``band_deg`` band about peak i (clipped to the parent's range) that the
    satellites' ±radius windows cover, and ``p_value`` is P(X ≥ n) for X the
    Poisson-binomial sum over those pᵢ; ``score`` is −log₁₀ P.
    ``offsets_deg`` is each peak's signed distance to its nearest satellite
    (peak minus satellite, NaN with no satellite in range), and
    ``n_positions`` the number of distinct satellite positions in range.

    A single-hypothesis P: it is not corrected for having looked at other k,
    which is what :func:`kgrid_null` measures.
    """

    k: KVector
    harmonics: tuple[int, ...]
    radius: float
    band_deg: float
    n_peaks: int
    n_matched: int
    p: tuple[float, ...]
    p_value: float
    score: float
    matched: tuple[int, ...]
    unmatched: tuple[int, ...]
    offsets_deg: tuple[float, ...]
    n_positions: int
    peaks: KPeaks
    parent: KParent


def score_kvector(peaks, parent: KParent, k, *, radius: float, band_deg: float,
                  harmonics: Sequence[int] = (1,)) -> KScore:
    """The local chance score of the k the caller names (issue #795, D3).

    Positions come from the existing exact generator,
    :func:`~rietx.crystallography.satellites.satellite_d_spacings`, over the
    parent's reciprocal lattice (centring applied, glide and screw absences
    not).  A peak is matched when it lies within ``radius`` (° 2θ) of a
    satellite.  For each peak i, pᵢ is the share of a ±``band_deg`` band about
    it that the satellites' ±radius windows cover, overlaps counted once:
    :func:`~rietx.indexing.ambiguity.chance_rate`'s covered-measure form, taken
    per band.  The score is −log₁₀ P(X ≥ n) for X the Poisson-binomial sum of
    Bernoulli(pᵢ), n the matched count.

    The idea is de Wolff's: a match is worth what the density of possible lines
    makes it worth (de Wolff, P. M. (1968), *J. Appl. Cryst.* **1**, 108-113,
    N_poss up to Q_N).  The local band, the covered measure in place of a line
    count and the Poisson-binomial tail are ours (issue #795).  The band
    half-width has no default: 5° is the value measured on synthetic CW-neutron
    patterns (Pnma, λ 2.41 Å), untested beyond them.

    ``harmonics`` names the satellite orders the hypothesis includes; ``(1,)``
    is the definition of a first-order hypothesis.  ``(2,)`` or ``(3,)``
    scores 2k or 3k alone, as its own hypothesis.  Whether a 2k or 3k residue
    is present is a test this module does not make.

    What this does **not** do: it does not rank, does not choose a k, and does
    not score absent lines: a k predicting satellites where no peak is
    observed is not penalised, only charged through the coverage of the bands
    the observed peaks sit in.
    """
    parent_ = parent
    kp = as_kpeaks(peaks)
    tt = _peak_array(kp, parent_)
    r = _positive(radius, "radius")
    band = _positive(band_deg, "band_deg")
    orders = _harmonics(harmonics)
    kk = as_kvector(k)
    sg = parent_.group
    if equivalent_kvectors(sg, kk, (0, 0, 0)):
        raise ValueError(f"k = {format_kvector(kk)} is a reciprocal-lattice vector "
                         "(k = 0): its satellites are the nuclear lines")
    lo, hi = parent_.two_theta_min, parent_.two_theta_max
    pos = _positions(parent_, [kk], orders)[0]
    matched, p, n, big_p, score = _score_rows(_windows([pos], r, lo, hi), tt, lo, hi, band)
    if len(pos) and len(tt):
        j = np.clip(np.searchsorted(pos, tt), 1, max(len(pos) - 1, 1))
        left = pos[np.clip(j - 1, 0, len(pos) - 1)]
        right = pos[np.clip(j, 0, len(pos) - 1)]
        off = np.where(np.abs(tt - left) <= np.abs(tt - right), tt - left, tt - right)
    else:
        off = np.full(len(tt), np.nan)
    m = matched[0] if len(tt) else np.zeros(0, dtype=bool)
    return KScore(
        k=kk, harmonics=orders, radius=r, band_deg=band, n_peaks=len(tt),
        n_matched=int(n[0]), p=tuple(float(x) for x in (p[0] if len(tt) else ())),
        p_value=float(big_p[0]), score=float(score[0]),
        matched=tuple(int(i) for i in np.flatnonzero(m)),
        unmatched=tuple(int(i) for i in np.flatnonzero(~m)),
        offsets_deg=tuple(float(x) for x in off), n_positions=len(pos),
        peaks=kp, parent=parent_)


# --------------------------------------------------------------------------
# positions of a grid, built once
# --------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class KGridPositions:
    """The satellite positions of every k in some strata, for one parent.

    Built by :func:`kgrid_positions`; pass it to :func:`score_kgrid` or
    :func:`kgrid_null` in place of the strata to score several peak lists, or
    run a null, without rebuilding the positions.  ``positions[i][j]`` is the
    sorted distinct 2θ in range of ``strata[i].kvectors[j]``.  The radius is
    not here: it is a scoring argument.
    """

    parent: KParent
    strata: tuple[KStratum, ...]
    harmonics: tuple[int, ...]
    positions: tuple[tuple[np.ndarray, ...], ...]
    build_seconds: float

    def __repr__(self) -> str:
        n = sum(s.n_points for s in self.strata)
        return (f"KGridPositions({self.parent.space_group!r}, {len(self.strata)} strata, "
                f"{n} k, harmonics={self.harmonics}, built in {self.build_seconds:.1f} s)")


def kgrid_positions(parent: KParent, strata: Sequence[KStratum], *,
                    harmonics: Sequence[int] = (1,)) -> KGridPositions:
    """Build the positions of every k of ``strata`` once (see :class:`KGridPositions`).

    One parent grid serves every k (``satellite_d_spacings``); the cost is
    linear in the number of k (about 0.4 ms each on Pnma at λ 2.41 Å to 140°,
    one Mac core).
    """
    t0 = time.perf_counter()
    orders = _harmonics(harmonics)
    strata = _check_strata(strata, parent)
    pos = tuple(tuple(_positions(parent, s.kvectors, orders)) for s in strata)
    return KGridPositions(parent=parent, strata=strata, harmonics=orders,
                          positions=pos, build_seconds=time.perf_counter() - t0)


def _check_strata(strata, parent: KParent) -> tuple[KStratum, ...]:
    out = tuple(strata)
    if not out:
        raise ValueError("no strata given: pass the strata to search, in the order "
                         "to search them")
    for s in out:
        if not isinstance(s, KStratum):
            raise TypeError(f"strata must be KStratum records, got {type(s).__name__}")
        if s.space_group != parent.space_group:
            raise ValueError(f"stratum {s.name} is of {s.space_group!r}, the parent "
                             f"of {parent.space_group!r}")
    names = [(s.name, s.denominator) for s in out]
    if len(set(names)) != len(names):
        raise ValueError("a stratum is listed twice")
    return out


def _grid_source(parent: KParent, strata, harmonics) -> tuple[tuple[KStratum, ...], tuple[int, ...], KGridPositions | None]:
    orders = _harmonics(harmonics)
    if isinstance(strata, KGridPositions):
        if strata.parent != parent:
            raise ValueError("the KGridPositions were built for another parent")
        if strata.harmonics != orders:
            raise ValueError(f"the KGridPositions were built for harmonics "
                             f"{strata.harmonics}, not {orders}")
        return strata.strata, orders, strata
    return _check_strata(strata, parent), orders, None


def _coverage(strata: Sequence[KStratum], searched: Sequence[str], left: Sequence[str]) -> str:
    dens = sorted({s.denominator for s in strata})
    grid = " and ".join(f"1/{d}" for d in dens)
    step = max(1.0 / d for d in dens)
    return (f"rational k on the {grid} grid (step {step:.4g} in conventional reciprocal "
            f"coordinates) in {len(searched)} stratum(s) searched; {len(left)} stratum(s) "
            "left unsearched. No claim is made about any k off this grid: a general or "
            "incommensurate k between grid points was not searched.")


def _expired(budget) -> bool:
    return budget is not None and bool(budget.expired())


# --------------------------------------------------------------------------
# 3. the scores of a grid
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class KGridRow:
    """One grid k scored (a row of :class:`KGridScores`).

    ``equivalents`` lists the structural class of ``k``: every ±Rᵀk reduced
    modulo L* (:func:`~rietx.crystallography.representation.irreps.canonical_kvector`'s
    spelling), so the arms of the star, −k and G − k.  The metric's
    near-symmetric partners need a tolerance and are
    :func:`kvector_equivalents`'s.
    """

    k: KVector
    stratum: str
    score: float
    p_value: float
    n_matched: int
    matched: tuple[int, ...]
    unmatched: tuple[int, ...]
    n_positions: int
    space_group: str = field(repr=False)

    @property
    def equivalents(self) -> tuple[KVector, ...]:
        return _structural_class(self.space_group, self.k)


@lru_cache(maxsize=4096)
def _structural_class(xhm: str, k: KVector) -> tuple[KVector, ...]:
    sg = get_spacegroup(xhm)
    arms = set(star(sg, k)) | set(star(sg, tuple(-c for c in k)))
    return tuple(sorted(canonical_kvector(sg, a) for a in arms))


@dataclass(frozen=True, repr=False)
class KGridScores:
    """The scores of every k in the strata searched (:func:`score_kgrid`).

    ``rows`` come in the order of the strata argument and, within a stratum,
    in its own order: **never sorted by score**.  There is no best row, no
    ``k`` and no accessor for one; ``scores`` and ``n_matched`` are the
    columns in row order.

    The grid-level facts (issue #795, the maintainer's condition):
    ``grid_step`` is the coarsest step of the strata searched (1/n, in
    conventional reciprocal coordinates; ``denominators`` per stratum),
    ``strata_searched`` and ``strata_left`` name what was and was not scored
    (a budget stops at a stratum boundary), and ``coverage`` says in words that
    **nothing is claimed about any k off the grid**: a general k between grid
    points can score near chance at every grid point.
    """

    parent: KParent
    peaks: KPeaks
    radius: float
    band_deg: float
    harmonics: tuple[int, ...]
    rows: tuple[KGridRow, ...]
    grid_step: float
    denominators: tuple[int, ...]
    strata_searched: tuple[str, ...]
    strata_left: tuple[str, ...]
    coverage: str
    budget_seconds: float | None
    budget_expired: bool
    elapsed_seconds: float

    @property
    def scores(self) -> np.ndarray:
        return np.array([r.score for r in self.rows])

    @property
    def n_matched(self) -> np.ndarray:
        return np.array([r.n_matched for r in self.rows], dtype=np.int64)

    def __repr__(self) -> str:
        return (f"KGridScores({len(self.rows)} rows over {len(self.strata_searched)} strata, "
                f"{len(self.strata_left)} left; grid step {self.grid_step:.4g}; "
                f"{self.coverage})")


def _stratum_positions(parent, stratum, orders, built, i):
    if built is not None:
        return built.positions[i]
    return _positions(parent, stratum.kvectors, orders)


def score_kgrid(peaks, parent: KParent, strata, *, radius: float, band_deg: float,
                harmonics: Sequence[int] = (1,), budget=None) -> KGridScores:
    """:func:`score_kvector` for every k of ``strata``, in the caller's order.

    ``strata`` is a sequence of :class:`KStratum` (from :func:`kgrid_strata`,
    in the order to search them) or a :class:`KGridPositions` built from them.
    Every row equals what :func:`score_kvector` returns for its k.

    ``budget`` is an :class:`~rietx.indexing.engines.Budget` or
    :class:`~rietx.indexing.engines.Deadline` read between strata; ``None``
    sets no cap.  A budget that expires stops the search at the next stratum
    boundary, and ``strata_left`` names every stratum not scored, as
    ``INDEX_BUDGET_EXHAUSTED`` does for a cell search.

    What this does **not** do: it does not sort, rank, pick or threshold; it
    does not score absent lines; and it claims nothing about k off the grid
    (``coverage``).
    """
    t0 = time.perf_counter()
    kp = as_kpeaks(peaks)
    tt = _peak_array(kp, parent)
    r = _positive(radius, "radius")
    band = _positive(band_deg, "band_deg")
    strata_, orders, built = _grid_source(parent, strata, harmonics)
    lo, hi = parent.two_theta_min, parent.two_theta_max
    rows: list[KGridRow] = []
    searched, left = [], []
    for i, st in enumerate(strata_):
        if _expired(budget):
            left.extend(s.name for s in strata_[i:])
            break
        pos = _stratum_positions(parent, st, orders, built, i)
        for c in range(0, st.n_points, _CHUNK):
            block = pos[c:c + _CHUNK]
            matched, _p, n, big_p, score = _score_rows(_windows(block, r, lo, hi), tt, lo, hi, band)
            for t, kk in enumerate(st.kvectors[c:c + _CHUNK]):
                m = matched[t] if len(tt) else np.zeros(0, dtype=bool)
                rows.append(KGridRow(
                    k=kk, stratum=st.name, score=float(score[t]), p_value=float(big_p[t]),
                    n_matched=int(n[t]), matched=tuple(int(x) for x in np.flatnonzero(m)),
                    unmatched=tuple(int(x) for x in np.flatnonzero(~m)),
                    n_positions=len(block[t]), space_group=parent.space_group))
        searched.append(st.name)
    done = [s for s in strata_ if s.name in set(searched)] or list(strata_)
    return KGridScores(
        parent=parent, peaks=kp, radius=r, band_deg=band, harmonics=orders,
        rows=tuple(rows), grid_step=max(s.grid_step for s in done),
        denominators=tuple(s.denominator for s in strata_ if s.name in set(searched)),
        strata_searched=tuple(searched), strata_left=tuple(left),
        coverage=_coverage(strata_, searched, left),
        budget_seconds=None if budget is None else float(budget.seconds),
        budget_expired=bool(left), elapsed_seconds=time.perf_counter() - t0)


# --------------------------------------------------------------------------
# 4. the null, as a reported number
# --------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class KNull:
    """The per-pattern null of a grid search (:func:`kgrid_null`).

    ``sample[s]`` is the maximum score over every k searched for shuffle s,
    whose positions are ``shuffles[s]``; ``matched_at_max[s]`` is the matched
    count of the k that reached it (the first such k in row order) and
    ``max_matched[s]`` the largest matched count anywhere on the grid, which is
    how a bare count saturates.  ``threshold`` is the ``percentile``-th
    percentile of ``sample`` (numpy's linear interpolation); any other quantile
    is read off the sample.  Nothing here compares a candidate with the
    threshold.

    The grid-level facts are :class:`KGridScores`'s: ``grid_step``,
    ``denominators``, ``strata_searched``, ``strata_left`` and ``coverage``
    (no claim about any k off the grid).  A budget that stops the null stops
    every shuffle at the same stratum, so every sample member is a maximum over
    the same strata.
    """

    parent: KParent
    n_peaks: int
    radius: float
    band_deg: float
    harmonics: tuple[int, ...]
    exclude: tuple[tuple[float, float], ...]
    seed: int
    n_shuffles: int
    percentile: float
    threshold: float
    sample: tuple[float, ...]
    matched_at_max: tuple[int, ...]
    max_matched: tuple[int, ...]
    shuffles: tuple[tuple[float, ...], ...]
    grid_step: float
    denominators: tuple[int, ...]
    strata_searched: tuple[str, ...]
    strata_left: tuple[str, ...]
    coverage: str
    budget_seconds: float | None
    budget_expired: bool
    elapsed_seconds: float

    def __repr__(self) -> str:
        return (f"KNull(N={self.n_peaks}, {self.n_shuffles} shuffles, seed={self.seed}, "
                f"{self.percentile:g}th percentile {self.threshold:.3f}; "
                f"{len(self.strata_searched)} strata searched, {len(self.strata_left)} left; "
                f"grid step {self.grid_step:.4g}; {self.coverage})")


def _exclude_windows(exclude, lo: float, hi: float) -> tuple[tuple[tuple[float, float], ...], np.ndarray]:
    """The exclusion windows as (centre, half-width) pairs, and the allowed
    intervals of [lo, hi] they leave, as an (m, 2) array."""
    arr = np.asarray(exclude, dtype=np.float64)
    if arr.size == 0:
        arr = arr.reshape(0, 2)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError("exclude must be (centre, half_width) pairs in ° 2θ")
    if (arr[:, 1] < 0).any():
        raise ValueError("an exclusion half-width is negative")
    pairs = tuple((float(c), float(h)) for c, h in arr)
    ivs = sorted((c - h, c + h) for c, h in pairs)
    allowed, cur = [], lo
    for a, b in ivs:
        if a > cur:
            allowed.append((cur, min(a, hi)))
        cur = max(cur, b)
        if cur >= hi:
            break
    if cur < hi:
        allowed.append((cur, hi))
    allowed = [(a, b) for a, b in allowed if b > a]
    if not allowed:
        raise ValueError("the exclusion windows cover the whole 2θ range")
    return pairs, np.array(allowed)


def _draw(allowed: np.ndarray, rng: np.random.Generator, shape) -> np.ndarray:
    """Uniform positions on the union of ``allowed`` intervals."""
    lengths = allowed[:, 1] - allowed[:, 0]
    cum = np.concatenate([[0.0], np.cumsum(lengths)])
    u = rng.uniform(0.0, cum[-1], size=shape)
    i = np.clip(np.searchsorted(cum, u, side="right") - 1, 0, len(lengths) - 1)
    return np.sort(allowed[i, 0] + (u - cum[i]), axis=-1)


def kgrid_null(peaks, parent: KParent, strata, *, radius: float, band_deg: float,
               exclude, n_shuffles: int, percentile: float, seed: int,
               harmonics: Sequence[int] = (1,), budget=None) -> KNull:
    """The grid maximum of the score under shuffles of this pattern's peaks.

    Each shuffle draws as many positions as ``peaks`` holds, uniformly over the
    parent's 2θ range **outside** the ``exclude`` windows, which are the
    caller's (centre, half-width) pairs in ° 2θ: the nuclear lines and their
    match windows, since the real unexplained peaks were sorted off them and a
    fair control must be too (WP-1442's condition for its fake-λ control).
    Every shuffle is scored over the same strata with the same radius, band and
    harmonics as :func:`score_kgrid`, and its maximum over the grid is kept.
    ``seed`` makes the sample reproducible: the same seed gives the identical
    sample.

    The look-elsewhere effect is the reason: a grid of 10⁴-10⁵ k reaches a
    single-hypothesis P of 10⁻⁴ or less on random positions (issue #795, the
    measured null), so a P that would mean something for one named k does not
    for the best of a grid.  The shuffle is the per-pattern measurement of that
    effect; its count and percentile have no default (100 and 99 are the
    values the design measured, on synthetic CW-neutron patterns only).

    What this does **not** do: no margin, no comparison of any candidate with
    the threshold, no verdict.  It claims nothing about k off the grid.
    """
    t0 = time.perf_counter()
    kp = as_kpeaks(peaks)
    big_n = len(_peak_array(kp, parent))
    r = _positive(radius, "radius")
    band = _positive(band_deg, "band_deg")
    n_sh = operator.index(n_shuffles)
    if n_sh < 1:
        raise ValueError(f"n_shuffles must be at least 1, got {n_shuffles!r}")
    pct = float(percentile)
    if not 0.0 <= pct <= 100.0:
        raise ValueError(f"percentile must lie in [0, 100], got {percentile!r}")
    seed_ = operator.index(seed)
    strata_, orders, built = _grid_source(parent, strata, harmonics)
    lo, hi = parent.two_theta_min, parent.two_theta_max
    pairs, allowed = _exclude_windows(exclude, lo, hi)
    draws = _draw(allowed, np.random.default_rng(seed_), (n_sh, big_n))

    best = np.full(n_sh, -np.inf)
    at_best = np.zeros(n_sh, dtype=np.int64)
    most = np.zeros(n_sh, dtype=np.int64)
    searched, left = [], []
    for i, st in enumerate(strata_):
        if _expired(budget):
            left.extend(s.name for s in strata_[i:])
            break
        pos = _stratum_positions(parent, st, orders, built, i)
        for c in range(0, st.n_points, _CHUNK):
            win = _windows(pos[c:c + _CHUNK], r, lo, hi)
            for s_ in range(n_sh):
                _m, _p, n, _bp, score = _score_rows(win, draws[s_], lo, hi, band)
                t = int(np.argmax(score))
                if score[t] > best[s_]:
                    best[s_], at_best[s_] = score[t], n[t]
                most[s_] = max(most[s_], int(n.max()) if len(n) else 0)
        searched.append(st.name)
    if searched:
        threshold = float(np.percentile(best, pct))
        sample = tuple(float(x) for x in best)
    else:
        threshold = float("nan")
        sample = tuple(float("nan") for _ in best)
    done = [s for s in strata_ if s.name in set(searched)] or list(strata_)
    return KNull(
        parent=parent, n_peaks=big_n, radius=r, band_deg=band, harmonics=orders,
        exclude=pairs, seed=seed_, n_shuffles=n_sh, percentile=pct, threshold=threshold,
        sample=sample, matched_at_max=tuple(int(x) for x in at_best),
        max_matched=tuple(int(x) for x in most),
        shuffles=tuple(tuple(float(x) for x in row) for row in draws),
        grid_step=max(s.grid_step for s in done),
        denominators=tuple(s.denominator for s in strata_ if s.name in set(searched)),
        strata_searched=tuple(searched), strata_left=tuple(left),
        coverage=_coverage(strata_, searched, left),
        budget_seconds=None if budget is None else float(budget.seconds),
        budget_expired=bool(left), elapsed_seconds=time.perf_counter() - t0)


# --------------------------------------------------------------------------
# 5. the equivalents and the metric partner
# --------------------------------------------------------------------------

Relation = Literal["k", "star", "-k", "partner"]


@dataclass(frozen=True)
class KEquivalent:
    """One vector the positions cannot separate from k.

    ``relation``: ``"k"`` for k itself, ``"star"`` for another arm Rᵀk of its
    star, ``"-k"`` for an arm of −k's star that is not in k's (a group without
    inversion), ``"partner"`` for an image of k under a near-symmetry of the
    metric that is none of those.  ``k`` is reduced modulo L*
    (``canonical_kvector``), so −k and G − k are one row.  A partner carries
    ``operation``, the map on conventional reciprocal components that takes k
    to it (exact), and ``metric_deviation``, the largest relative change of
    the reduced metric under it (0 for an exact lattice symmetry); structural
    rows carry ``None`` for both.
    """

    k: KVector
    relation: Relation
    operation: tuple[tuple[Fraction, Fraction, Fraction], ...] | None = None
    metric_deviation: float | None = None


@dataclass(frozen=True)
class KEquivalents:
    """What the positions cannot separate from k (:func:`kvector_equivalents`).

    ``rows`` holds k, then the rest of its star, then the arms of −k's star
    outside it, then the metric partners, each group in exact-tuple order.
    ``minus_k_is_k`` is True when 2k is a vector of L*.  ``diagnostics``
    carries one ``K_SEARCH_PARTNER`` per partner row.
    """

    parent: KParent
    k: KVector
    tol: float
    minus_k_is_k: bool
    rows: tuple[KEquivalent, ...]
    diagnostics: tuple[Diagnostic, ...]


def _frac_matrix(m: np.ndarray) -> tuple[tuple[Fraction, ...], ...]:
    """A basis change from ``reduce``'s gemmi triplet: exact 24ths."""
    den = gemmi.Op.DEN
    return tuple(tuple(Fraction(int(round(float(x) * den)), den) for x in row) for row in m)


def _matmul(a, b):
    return tuple(tuple(sum(a[i][t] * b[t][j] for t in range(3)) for j in range(3))
                 for i in range(3))


def _inv(a):
    """Exact inverse of a rational 3 × 3 matrix, by the adjugate."""
    def minor(i, j):
        r = [x for x in range(3) if x != i]
        c = [y for y in range(3) if y != j]
        return a[r[0]][c[0]] * a[r[1]][c[1]] - a[r[0]][c[1]] * a[r[1]][c[0]]

    det = sum((-1) ** j * a[0][j] * minor(0, j) for j in range(3))
    if det == 0:
        raise ValueError("singular basis change")
    # inverse = adjugate / det, the adjugate being the transposed cofactors
    return tuple(tuple(Fraction((-1) ** (i + j) * minor(j, i)) / det for j in range(3))
                 for i in range(3))


def _to_first(sg, op, k: KVector, target: KVector):
    """``op`` composed with the structural map that takes op·k to ``target``,
    so the stored operation sends k onto the row's own spelling (mod L*)."""
    img = tuple(sum(op[i][j] * k[j] for j in range(3)) for i in range(3))
    for r in _lattice(sg.xhm()).laue:
        rf = tuple(tuple(Fraction(int(x)) for x in row) for row in r)
        moved = tuple(sum(rf[i][j] * img[j] for j in range(3)) for i in range(3))
        if canonical_kvector(sg, moved) == target:
            return _matmul(rf, op)
    raise RuntimeError("the partner's class does not hold its own image")  # pragma: no cover


def kvector_equivalents(parent: KParent, k, *, tol: float) -> KEquivalents:
    """The vectors whose satellite positions cannot be told from k's.

    **Structural, exact, no code:** the arms Rᵀk of the star, −k, and G − k,
    every one reduced modulo the phase's own reciprocal lattice (#1071).  They
    give identical positions by construction.

    **The metric's partners:** the images of k under every near-symmetry of
    the cell's metric, :func:`~rietx.indexing.ambiguity.lattice_point_group`
    at relative tolerance ``tol`` (required: what counts as near is the
    caller's call), that are no structural equivalent, one row per class of
    such images.  The metric is unchanged by the map to within ``tol``, so the
    satellites of k and of vectors near its image can agree within a match
    radius: on a pseudo-tetragonal Pnma cell (a = 5.74, c = 5.54 Å) a k near
    the x ↔ z image of a general k matched every planted peak at a 0.12°
    radius (issue #795, on a 0.01 grid).  The exact image need not be the
    best-matching vector, since the map is only near a symmetry; score its
    neighbourhood.  Each partner fires ``K_SEARCH_PARTNER``, which states the
    fact and never says which k is right.  This is the geometrical ambiguity of Mighell, A. D. & Santoro,
    A. (1975), *J. Appl. Cryst.* **8**, 372-374, carried one rank over, from a
    cell to a vector against a known cell.

    On this rational grid every k is commensurate, so the near-rational partner
    p/q of a refined k is not listed here.

    What this does **not** do: it does not rank the rows or choose among them.
    """
    kk = as_kvector(k)
    t = _positive(tol, "tol")
    sg = parent.group
    if equivalent_kvectors(sg, kk, (0, 0, 0)):
        raise ValueError(f"k = {format_kvector(kk)} is a reciprocal-lattice vector (k = 0)")
    neg = tuple(-c for c in kk)
    own = {canonical_kvector(sg, a) for a in star(sg, kk)}
    minus = {canonical_kvector(sg, a) for a in star(sg, neg)} - own
    ck = canonical_kvector(sg, kk)
    rows = [KEquivalent(k=ck, relation="k")]
    rows += [KEquivalent(k=a, relation="star") for a in sorted(own - {ck})]
    rows += [KEquivalent(k=a, relation="-k") for a in sorted(minus)]
    structural = own | minus

    centring = sg.xhm()[0]
    w_ops, m = lattice_point_group(parent.cell, centring, rtol=t)
    reduced = reduce_cell(parent.cell, centring)
    g = np.asarray(direct_metric_tensor(*reduced.cell), dtype=np.float64)
    d = np.sqrt(np.diag(g))
    mf = _frac_matrix(m)
    mf_inv = _inv(mf)
    partners: dict[KVector, tuple[float, tuple]] = {}
    for w in w_ops:
        dev = float(np.max(np.abs(w @ g @ w.T - g) / np.outer(d, d)))
        wf = tuple(tuple(Fraction(int(x)) for x in row) for row in w)
        op = _matmul(_matmul(mf_inv, _inv(wf)), mf)
        img = tuple(sum(op[i][j] * kk[j] for j in range(3)) for i in range(3))
        if canonical_kvector(sg, img) in structural:
            continue
        cls = _structural_class(parent.space_group, canonical_kvector(sg, img))
        c = cls[0]
        held = partners.get(c)
        if held is None or dev < held[0]:
            partners[c] = (dev, op if canonical_kvector(sg, img) == c else
                           _to_first(sg, op, kk, c))
    diags = []
    for c in sorted(partners):
        dev, op = partners[c]
        rows.append(KEquivalent(k=c, relation="partner", operation=op, metric_deviation=dev))
        diags.append(Diagnostic(
            level="info", code="K_SEARCH_PARTNER",
            message=(f"The cell's metric is unchanged to {dev:.3g} relative, inside "
                     f"tol = {t:g}, by a map taking k = {format_kvector(ck)} to "
                     f"{format_kvector(c)}, which is no symmetry equivalent of k: satellites "
                     "of k and of vectors near that image can agree within a match radius."),
            where=[f"k = {format_kvector(ck)}", f"partner = {format_kvector(c)}"],
            suggestion=("Score the partner and its neighbourhood (score_kvector, "
                        "score_kgrid) beside k and keep every k that matches as a "
                        "hypothesis; intensities (a moment or modulation model) or a "
                        "sharper instrument separate them."),
            value=dev))
    return KEquivalents(parent=parent, k=ck, tol=t,
                        minus_k_is_k=equivalent_kvectors(sg, neg, kk),
                        rows=tuple(rows), diagnostics=tuple(diags))
