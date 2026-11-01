"""Every Wyckoff class of a space group, and the placements of a composition on them.

A structure solution cannot start from free atoms on the general position: in
rutile, spinel, perovskite and pyrochlore **every** atom sits on a special
position, and many inorganic structures have no atom on a general one.  This
module is what a solver enumerates before it moves an atom: the site classes
of the group, and the ways a composition (atoms per cell, by species) fills
them exactly.

**Site classes** are derived from the group's own operations, with no table
read from any program.  A Wyckoff position is the set of points whose
site-symmetry groups are conjugate in G (International Tables for
Crystallography Vol. A, Hahn ed., 2005, sect. 8.3.2).  Three steps:

1. **Exact stabilisers on a grid.** Every point of the 1/24 grid of the cell is
   tested in integer arithmetic for the operations (R, t) with
   R·p + t = p + n, *with* the lattice translation n each needs, so the
   stabiliser is the exact affine one, not a tolerance test.  1/24 is the least
   common multiple of the denominators of the representative coordinates in
   International Tables A (quarters, eighths, thirds, sixths), and it is
   gemmi's own ``Op.DEN``, so every translation gemmi can represent lies on it.
   An off-grid translation is still refused by name (``SITE_CLASSES_GRID``)
   rather than rounded.  Translations on the grid do not put every special
   position on it: ``-x+1/24`` fixes x = 1/48, and a 3-fold ``-y+t, x-y, z``
   fixes (2t/3, t/3), off both the 1/24 and the 1/48 grid for t = 1/24, 1/12
   or 1/3.  A tabulated setting is certified (all 564 gemmi settings are
   checked against spglib).  An :class:`~.symmetry.OperatorGroup`, whose
   operations no table vouches for, is checked two ways, and refused by the
   same name: **(a)** every operation that has fixed points at all (decided
   exactly, over the integers, by :func:`_has_fixed_point`) must fix a point
   of the 1/24 grid; **(b)** a scan of the 1/48 grid must find no stabiliser
   the 1/24 grid missed, which catches a common fixed point of several
   operations that none of them has alone.  (a) is exact per operation; (b)
   is a grid, not every rational point.
2. **One fixed subspace per stabiliser.** The points one stabiliser S fixes form
   an affine subspace p + span(B), with B = :func:`~.wyckoff.coordinate_basis`
   of S's rotations — the free-parameter basis the rest of the package already
   uses for a site.
3. **Conjugate subspaces are one class.** Every grid point of that subspace is
   mapped by every operation; each image with a stabiliser of the same order
   lies on a subspace of the same Wyckoff position (its stabiliser is gS g⁻¹),
   so the classes are read off the images, with no conjugation algebra.

Each class is then checked against the package's existing site handling:
:func:`~.symmetry.site_orbit` at the representative must return the same
stabiliser order and multiplicity |G|/|S|, and :func:`~.wyckoff.site_constraints`
supplies the Wyckoff letter and oriented site-symmetry symbol (spglib's, for a
group spglib names; empty for an :class:`~.symmetry.OperatorGroup`, as there).

**Composition → assignments.** A class with no free parameter is one orbit, so
it holds one species at most, and only once in the whole structure: this is
an ordered model, with no shared sites.  A class with free parameters holds
infinitely many orbits and may be used any number of times, by any species.
The number of assignments is counted exactly first, by dynamic programming,
and an enumeration above :data:`MAX_SITE_ASSIGNMENTS` is refused with that
count (``SITE_ASSIGNMENTS_EXCEED_CAP``) rather than truncated.  Assignments come
**heavy atoms first**: species in descending atomic number, and the list
ordered by the heavy species' placement.  A search can then race the placements
of the dominant scatterers first.  The race itself is not here.

Provisional (WP-1997, structure solution), and not exported from :mod:`rietx`.
"""

from __future__ import annotations

import itertools
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field

import gemmi
import numpy as np

from .species import element_symbol
from .symmetry import (
    OperatorGroup,
    _group_arrays,
    as_group,
    group_key,
    site_orbit,
)
from .wyckoff import coordinate_basis, site_constraints

#: The grid the stabilisers are measured on, in fractions of each cell edge.
GRID = 24

#: Default cap on :func:`site_assignments`, by name.  rietx's own choice: five
#: times the largest case seen on one family (4 000 on our solve kits).  A
#: correct large cell can exceed it; the refusal carries the exact count and
#: ``max_assignments=`` overrides.
MAX_SITE_ASSIGNMENTS = 20_000

#: Grid points per chunk of the stabiliser scan, so a 192-operation group keeps
#: its working array near 8 MB.
_CHUNK = 1728


@dataclass(frozen=True, eq=False)
class SiteClass:
    """One Wyckoff position of a space group.

    Attributes
    ----------
    wyckoff : str — multiplicity + letter from
        :func:`~.wyckoff.site_constraints`, e.g. ``"8a"``; ``""`` for an
        :class:`~.symmetry.OperatorGroup`, which has no tabulated letters.
        The letter is spglib's, and spglib fixes letters only up to the
        group's Euclidean normaliser.  Classes a normaliser element exchanges
        (``8a``/``8b`` in ``Fd-3m``) have identical multiplicity, site symmetry
        and dof.  Which of them carries which letter at a given coordinate can
        differ from the International Tables coordinate list, as it appears to
        in the origin-2 settings of ``Fd-3m`` and ``Pn-3m``.  Nothing here
        depends on the letter.
    site_symmetry : str — the oriented site-symmetry symbol from the same call,
        e.g. ``".3m"``; ``""`` where ``wyckoff`` is.
    multiplicity : int — |G| / |S| in the conventional cell.
    point : (3,) float — a representative, an exact multiple of 1/24 in
        [0, 1), whose stabiliser is exactly S (no more special point).
    basis : (dof, 3) int — the free directions:
        x(u) = point + Σₖ uₖ·basis[k]; ``(0, 3)`` for a fixed position.
    stabilizer : (|S|, 3, 3) int — rotation parts of the operations fixing
        ``point``, as :func:`~.symmetry.site_orbit` returns them.
    coset_rot, coset_tran : (multiplicity, 3, 3), (multiplicity, 3) float — one
        operation per left coset of S, so :meth:`orbit` always returns
        ``multiplicity`` images for any u.
    """

    wyckoff: str
    site_symmetry: str
    multiplicity: int
    point: np.ndarray
    basis: np.ndarray
    stabilizer: np.ndarray
    coset_rot: np.ndarray = field(repr=False)
    coset_tran: np.ndarray = field(repr=False)

    @property
    def dof(self) -> int:
        """Number of free coordinates on this position."""
        return int(self.basis.shape[0])

    def position(self, u=()) -> np.ndarray:
        """The point x(u) = point + uᵀ·basis, wrapped into [0, 1)."""
        u = np.asarray(u, dtype=np.float64).reshape(-1)
        if u.size != self.dof:
            raise ValueError(f"{self.wyckoff or 'this class'} has {self.dof} free "
                             f"coordinates, got {u.size}")
        x = self.point + (u @ self.basis if self.dof else 0.0)
        return x % 1.0

    def orbit(self, u=()) -> np.ndarray:
        """All ``multiplicity`` images of x(u), shape (multiplicity, 3), in [0, 1).

        Images of the coset representatives of S, so the count stays
        ``multiplicity`` for every u: where u puts the point on a more special
        position (x on 32e reaching 8a at x = 1/8 in ``Fd-3m:2``), images
        coincide rather than disappear.  A search moving u keeps a constant atom
        count this way.  :func:`~.symmetry.site_orbit` is the call that returns
        the distinct images of one given point.
        """
        x = self.position(u)
        return (np.einsum("oij,j->oi", self.coset_rot, x) + self.coset_tran) % 1.0


def _integer_ops(sg) -> tuple[np.ndarray, np.ndarray]:
    """(R, 24·t) of every operation as integers; refuse a non-grid translation."""
    _, rot, tran = _group_arrays(group_key(sg))
    r = np.rint(rot).astype(np.int64)
    t = np.rint(tran * GRID).astype(np.int64)
    if not np.allclose(tran * GRID, t, atol=1e-9):  # pragma: no cover - Op.DEN is 24
        raise ValueError(
            f"SITE_CLASSES_GRID: a translation of {sg.xhm()!r} is not a multiple "
            f"of 1/{GRID}; the site classes are measured on the 1/{GRID} grid, "
            "which holds every tabulated setting — transform to one first")
    return r, t


def _stabiliser_keys(r: np.ndarray, t: np.ndarray, n: int) -> set[bytes]:
    """The distinct non-trivial stabilisers of the 1/n grid, as step 1 keys them.

    ``t`` is in 1/GRID units and ``n`` a multiple of GRID.  A key is the fixing
    operations with their lattice translations, which do not depend on ``n``.
    """
    tn = t * (n // GRID)
    axis = np.arange(n, dtype=np.int64)
    grid = np.array(list(itertools.product(axis, axis, axis)), dtype=np.int64)
    out: set[bytes] = set()
    for lo in range(0, len(grid), _CHUNK):
        pts = grid[lo:lo + _CHUNK]
        diff = np.einsum("oij,pj->poi", r, pts) + tn[None] - pts[:, None, :]
        fixes = np.all(diff % n == 0, axis=2)
        for i in np.flatnonzero(fixes.sum(axis=1) > 1):
            ops = np.flatnonzero(fixes[i])
            out.add(ops.tobytes() + (diff[i, ops] // n).tobytes())
    return out


def _has_fixed_point(r: np.ndarray, t24: np.ndarray) -> bool:
    """Whether the operation (R, t) fixes any point of space, grid or not.

    R·p + t = p + n has a rational solution p, with n an integer vector, exactly
    when yᵀt is an integer for every integer y with yᵀ(R − I) = 0 (the Smith
    argument: with U(R − I)V = D, only the zero rows of D constrain t).  The
    rows of U that U·(R − I) sends to zero are a basis of that integer left
    kernel, so one row-reduction of R − I over Z, tracking U, decides it.
    ``t24`` is 24·t, an integer vector.
    """
    a = [[int(v) for v in row] for row in (r - np.eye(3, dtype=np.int64))]
    u = [[int(i == j) for j in range(3)] for i in range(3)]
    top = 0
    for col in range(3):
        while True:  # Euclid down the column, below the pivot row
            rows = [i for i in range(top, 3) if a[i][col] != 0]
            if len(rows) <= 1:
                break
            piv = min(rows, key=lambda i: abs(a[i][col]))
            for i in rows:
                if i != piv:
                    q = a[i][col] // a[piv][col]
                    a[i] = [x - q * y for x, y in zip(a[i], a[piv])]
                    u[i] = [x - q * y for x, y in zip(u[i], u[piv])]
        rows = [i for i in range(top, 3) if a[i][col] != 0]
        if rows:
            a[top], a[rows[0]] = a[rows[0]], a[top]
            u[top], u[rows[0]] = u[rows[0]], u[top]
            top += 1
    return all(sum(u[i][j] * int(t24[j]) for j in range(3)) % GRID == 0
               for i in range(3) if not any(a[i]))


def _saturated(basis: np.ndarray) -> bool:
    """Whether ``basis`` spans span(B) ∩ Z³: the gcd of its maximal minors is 1."""
    if basis.shape[0] in (0, 3):
        return True
    minors = basis[0] if basis.shape[0] == 1 else np.cross(basis[0], basis[1])
    return int(np.gcd.reduce(np.abs(minors))) == 1


def _subspace_points(p: np.ndarray, basis: np.ndarray) -> np.ndarray:
    """Every grid point of p + span(basis), mod the lattice, in grid units.

    Integer steps of u reach every grid point of the subspace only when the
    basis spans span(B) ∩ Z³.  ``coordinate_basis`` rows are coprime, which
    settles one row.  For two rows it was measured, not assumed: all 564 gemmi
    settings give saturated bases (2026-09-30).  A future one that does not is
    refused rather than under-sampled.
    """
    if basis.shape[0] == 0:
        return p[None]
    if not _saturated(basis):
        raise AssertionError(  # pragma: no cover - measured on every gemmi setting
            f"SITE_CLASSES_BASIS: {basis.tolist()} does not span its lattice plane")
    us = np.array(list(itertools.product(range(GRID), repeat=basis.shape[0])),
                  dtype=np.int64)
    return np.unique((p[None] + us @ basis) % GRID, axis=0)


def _flat(v: np.ndarray) -> np.ndarray:
    return (v[..., 0] * GRID + v[..., 1]) * GRID + v[..., 2]


def site_classes(space_group) -> tuple[SiteClass, ...]:
    """Every Wyckoff position of ``space_group``, in International Tables order.

    ``space_group`` is anything :func:`~.symmetry.as_group` takes: a symbol with
    its setting (``"Fd-3m:1"``, ``"R-3m:H"``), a gemmi group, or an
    :class:`~.symmetry.OperatorGroup`.  Classes are ordered by Wyckoff letter
    when the group has letters, so the general position comes last; otherwise
    by (multiplicity, dof, representative).  Derived as the module docstring
    says (International Tables A, sect. 8.3.2) and cached per group.
    """
    sg = as_group(space_group)
    key = group_key(sg)
    with _CACHE_LOCK:
        if key not in _CACHE:
            if len(_CACHE) >= _CACHE_SIZE:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = _derive(sg)
        return _CACHE[key]


#: Derived classes per :func:`~.symmetry.group_key`, oldest dropped first; the
#: largest group costs about a second, and a solve asks for one group many times.
_CACHE: dict = {}
_CACHE_SIZE = 64
_CACHE_LOCK = threading.Lock()


def _derive(sg) -> tuple[SiteClass, ...]:
    r, t = _integer_ops(sg)
    order = len(r)
    fine = None
    if isinstance(sg, OperatorGroup):
        fine = _stabiliser_keys(r, t, 2 * GRID)
    axis = np.arange(GRID, dtype=np.int64)
    grid = np.array(list(itertools.product(axis, axis, axis)), dtype=np.int64)
    n_pts = len(grid)
    on_grid = np.zeros(order, dtype=bool)

    # 1. the exact affine stabiliser of every grid point, as a hashable key:
    #    which operations fix it, and with which lattice translation
    count = np.empty(n_pts, dtype=np.int64)
    key_of = np.full(n_pts, -1, dtype=np.int64)
    keys: dict[bytes, int] = {}
    members: list[list[int]] = []
    stabs: list[np.ndarray] = []
    for lo in range(0, n_pts, _CHUNK):
        pts = grid[lo:lo + _CHUNK]
        diff = np.einsum("oij,pj->poi", r, pts) + t[None] - pts[:, None, :]
        fixes = np.all(diff % GRID == 0, axis=2)
        on_grid |= fixes.any(axis=0)
        count[lo:lo + len(pts)] = fixes.sum(axis=1)
        for i in np.flatnonzero(count[lo:lo + len(pts)] > 1):
            ops = np.flatnonzero(fixes[i])
            k = ops.tobytes() + (diff[i, ops] // GRID).tobytes()
            kid = keys.setdefault(k, len(keys))
            if kid == len(members):
                members.append([])
                stabs.append(ops)
            members[kid].append(lo + i)
            key_of[lo + i] = kid

    # an operation with fixed points, none of them on the grid, has its special
    # positions where no scan looks: -x+t fixes x = t/2, and a 3-fold -y+t, x-y, z
    # fixes (2t/3, t/3), whatever the translations' own denominator
    off = [i for i in np.flatnonzero(~on_grid) if _has_fixed_point(r[i], t[i])]
    if off:
        raise ValueError(
            f"SITE_CLASSES_GRID: {sg.xhm()!r} has special positions off the "
            f"1/{GRID} grid: {len(off)} operation(s) (first: operation {off[0]}, "
            f"rotation {r[off[0]].tolist()}, translation {(t[off[0]] / GRID).tolist()}) "
            "fix points of space but none on it.  Every operation's fixed points "
            f"must include a multiple of 1/{GRID}, as they do when the list is a "
            "tabulated setting with its origin moved by a grid vector; use "
            "such an origin, or transform to a tabulated setting")
    if fine is not None and fine != set(keys):
        raise ValueError(
            f"SITE_CLASSES_GRID: {sg.xhm()!r} has special positions off the "
            f"1/{GRID} grid: its operations put {len(fine) - len(keys)} "
            f"stabiliser(s) on the 1/{2 * GRID} grid and none on the 1/{GRID} one "
            "(each operation has a fixed point on the grid, but a common one "
            "does not); use an origin on the grid, or transform to a "
            "tabulated setting")

    # 2–3. walk the stabiliser keys; each unassigned one opens a class, and its
    #      subspace's images claim every key of the same Wyckoff position
    owner = np.full(len(members), -1, dtype=np.int64)
    raw: list[tuple[np.ndarray, np.ndarray]] = []
    for kid in range(len(members)):
        if owner[kid] >= 0:
            continue
        cls = len(raw)
        p = grid[members[kid][0]]
        ops = stabs[kid]
        basis = coordinate_basis(list(r[ops])).astype(np.int64).reshape(-1, 3)
        sub = _subspace_points(p, basis)
        images = (np.einsum("oij,pj->opi", r, sub) + t[:, None, :]) % GRID
        reached = np.unique(_flat(images.reshape(-1, 3)))
        reached = reached[count[reached] == len(ops)]
        claimed = np.unique(key_of[reached])
        claimed = claimed[claimed >= 0]
        if np.any((owner[claimed] >= 0) & (owner[claimed] != cls)):
            raise AssertionError(  # pragma: no cover - conjugacy is an equivalence
                f"SITE_CLASSES_OVERLAP in {sg.xhm()!r}: one stabiliser key reached "
                "from two classes")
        owner[claimed] = cls
        raw.append((p, basis))
    general = grid[int(np.flatnonzero(count == 1)[0])]
    raw.append((general, np.eye(3, dtype=np.int64)))

    out = []
    for p, basis in raw:
        point = p.astype(np.float64) / GRID
        orbit = site_orbit(sg, point)
        if orbit.multiplicity * len(orbit.stabilizer) != order or not np.array_equal(
                coordinate_basis(list(orbit.stabilizer)).reshape(-1, 3), basis):
            raise AssertionError(  # pragma: no cover - same operations, two readings
                f"SITE_CLASSES_DISAGREE in {sg.xhm()!r} at {point}: site_orbit "
                f"gives multiplicity {orbit.multiplicity} and a different basis")
        # site_constraints already leaves both empty for an OperatorGroup
        sc = site_constraints(sg, point)
        if sc.multiplicity != orbit.multiplicity:
            raise AssertionError(  # pragma: no cover
                f"SITE_CLASSES_DISAGREE in {sg.xhm()!r}: site_constraints "
                f"multiplicity {sc.multiplicity} vs {orbit.multiplicity}")
        letter, symbol = sc.wyckoff, sc.site_symmetry
        for arr in (point, basis, orbit.stabilizer, orbit.rot, orbit.tran):
            arr.flags.writeable = False
        out.append(SiteClass(
            wyckoff=letter, site_symmetry=symbol, multiplicity=orbit.multiplicity,
            point=point, basis=basis, stabilizer=orbit.stabilizer,
            coset_rot=orbit.rot, coset_tran=orbit.tran))
    if all(c.wyckoff for c in out):
        out.sort(key=lambda c: _letter_rank(c.wyckoff))
    else:
        out.sort(key=lambda c: (c.multiplicity, c.dof, tuple(c.point)))
    return tuple(out)


_LETTERS = "abcdefghijklmnopqrstuvwxyzA"   # 'A' is spglib's α (Pmmm's 8α)


def _letter_rank(wyckoff: str) -> int:
    return _LETTERS.index(wyckoff.lstrip("0123456789"))


# --------------------------------------------------------------------------
# composition → site-class assignments


@dataclass(frozen=True)
class SiteAssignment:
    """One way to place a composition on the site classes.

    ``sites`` are ``(species, class index)`` pairs, heavy species first and each
    species' classes in index order; a free class may appear more than once
    (distinct orbits on one Wyckoff position).  ``dof`` is the number of free
    coordinates a search moves.
    """

    sites: tuple[tuple[str, int], ...]
    dof: int

    @property
    def n_sites(self) -> int:
        return len(self.sites)


class SiteAssignmentCapError(ValueError):
    """The assignments of a composition outnumber the cap; carries the exact count."""

    def __init__(self, count: int, cap: int, detail: str):
        self.count = count
        self.cap = cap
        super().__init__(
            f"SITE_ASSIGNMENTS_EXCEED_CAP: {count} site-class assignments exceed "
            f"max_assignments={cap} ({detail}); check the composition and Z, try a "
            "higher-symmetry group, or raise the cap knowingly")


def _atomic_number(species: str) -> int:
    return gemmi.Element(element_symbol(species)).atomic_number


def _heavy_first(composition: Mapping[str, int]) -> list[str]:
    return sorted(composition, key=lambda s: (-_atomic_number(s), s))


def _check(classes, composition: Mapping[str, int],
           max_sites_per_species: int | None = None) -> None:
    if not classes:
        raise ValueError("no site classes given")
    if not composition:
        raise ValueError("the composition has no species")
    if max_sites_per_species is not None and (
            int(max_sites_per_species) != max_sites_per_species
            or max_sites_per_species < 1):
        raise ValueError("max_sites_per_species must be a positive integer or None; "
                         f"got {max_sites_per_species!r}")
    for sp, n in composition.items():
        if int(n) != n or n < 1:
            raise ValueError(f"atoms per cell must be positive integers; {sp!r}: {n!r}")


def _free_ways(mults: list[int], n: int, kmax: int) -> list[list[int]]:
    """ways[r][k]: multisets of free classes with Σ multiplicity r and k sites."""
    ways = [[0] * (kmax + 1) for _ in range(n + 1)]
    ways[0][0] = 1
    for m in mults:                       # unbounded coin change, per class
        for r in range(m, n + 1):
            for k in range(1, kmax + 1):
                ways[r][k] += ways[r - m][k - 1]
    return ways


def count_site_assignments(classes, composition: Mapping[str, int], *,
                           max_sites_per_species: int | None = None) -> int:
    """Exact number of assignments :func:`site_assignments` would return.

    Dynamic programming over the fixed classes already taken, so the count is
    cheap even where the list would not fit in memory.  ``max_sites_per_species``
    limits how many sites one species may use; ``None`` allows any number.
    """
    _check(classes, composition, max_sites_per_species)
    fixed = [i for i, c in enumerate(classes) if c.dof == 0]
    free = [c.multiplicity for c in classes if c.dof > 0]
    states: dict[frozenset, int] = {frozenset(): 1}
    for sp in _heavy_first(composition):
        n = int(composition[sp])
        kmax = n if max_sites_per_species is None else max_sites_per_species
        ways = _free_ways(free, n, kmax)
        within = [[sum(row[:k + 1]) for k in range(kmax + 1)] for row in ways]
        new: dict[frozenset, int] = {}
        for used, ways_so_far in states.items():
            avail = [i for i in fixed if i not in used and classes[i].multiplicity <= n]
            for size in range(min(len(avail), kmax) + 1):
                for pick in itertools.combinations(avail, size):
                    rest = n - sum(classes[i].multiplicity for i in pick)
                    if rest < 0:
                        continue
                    w = within[rest][kmax - size]
                    if w:
                        key = used | frozenset(pick)
                        new[key] = new.get(key, 0) + ways_so_far * w
        states = new
    return sum(states.values())



def holds(classes, count: int) -> bool:
    """Can ``count`` atoms of one species sit on these classes, each orbit whole?

    The question :func:`count_site_assignments` answers for a one-species
    composition (``> 0``), without the count: a class with no free parameter
    is one orbit and is used at most once, a class with free parameters any
    number of times.  So ``count`` must be a sum of the fixed classes'
    multiplicities, each at most once, plus any multiples of the free ones'.
    Fixed classes first, as a subset sum; the free ones then as unbounded coin
    change over what that reaches.
    """
    if int(count) != count or count < 0:
        raise ValueError(f"an atom count must be a non-negative integer; got {count!r}")
    count = int(count)
    reach = [False] * (count + 1)
    reach[0] = True
    for c in classes:
        if c.dof == 0:
            for r in range(count, c.multiplicity - 1, -1):
                reach[r] = reach[r] or reach[r - c.multiplicity]
    for c in classes:
        if c.dof > 0:
            for r in range(c.multiplicity, count + 1):
                reach[r] = reach[r] or reach[r - c.multiplicity]
    return reach[count]

def site_assignments(classes, composition: Mapping[str, int], *,
                     max_assignments: int = MAX_SITE_ASSIGNMENTS,
                     max_sites_per_species: int | None = None,
                     ) -> tuple[SiteAssignment, ...]:
    """Every placement of ``composition`` (atoms per cell) on ``classes``.

    ``classes`` is what :func:`site_classes` returns; indices in the result
    refer to it.  Capacity: a class with no free parameter is one orbit and is
    used at most once in the whole structure (one species, one site); a class
    with free parameters may be used any number of times.  The count is taken
    first (:func:`count_site_assignments`), and a count above
    ``max_assignments`` raises :class:`SiteAssignmentCapError` carrying it.  An
    empty tuple means the composition has no placement in this group.

    Order: species heavy first (descending atomic number), and assignments
    sorted by the heavy species' placements, so that assignments sharing the
    dominant scatterers' placement are adjacent.
    """
    total = count_site_assignments(classes, composition,
                                   max_sites_per_species=max_sites_per_species)
    if total > max_assignments:
        per = ", ".join(f"{sp} {composition[sp]}" for sp in _heavy_first(composition))
        raise SiteAssignmentCapError(total, max_assignments, f"atoms per cell: {per}")
    fixed = {i for i, c in enumerate(classes) if c.dof == 0}
    order = _heavy_first(composition)
    mult = [c.multiplicity for c in classes]
    kmaxes = [int(composition[sp]) if max_sites_per_species is None
              else max_sites_per_species for sp in order]
    inf = 1 << 30

    def placements(n: int, kmax: int, used: frozenset):
        """Placements of n atoms on the classes not in ``used``, in index order.

        Every branch is pruned by the fewest sites that can still reach the
        remaining multiplicity (``mins``), so the walk never enters a dead end
        and its cost follows what it returns, not the size of the search space.
        """
        n_cls = len(classes)
        mins = [[inf] * (n + 1) for _ in range(n_cls + 1)]   # from class s on
        mins[n_cls][0] = 0
        for s in range(n_cls - 1, -1, -1):
            for r in range(n + 1):
                best = mins[s + 1][r]
                if mult[s] <= r and not (s in fixed and s in used):
                    again = mins[s + 1 if s in fixed else s][r - mult[s]] + 1
                    best = min(best, again)
                mins[s][r] = best

        def rec(rest, start, chosen):
            if rest == 0:
                yield tuple(chosen)
                return
            if mins[start][rest] > kmax - len(chosen):
                return
            for ci in range(start, n_cls):
                if mult[ci] <= rest and not (ci in fixed and ci in used):
                    yield from rec(rest - mult[ci], ci + 1 if ci in fixed else ci,
                                   chosen + [ci])
        return rec(n, 0, [])

    # a node of the combination is worth entering only if the species after it
    # can still be placed: that prune is what keeps an unplaceable composition
    # (a species no class fits) from enumerating the placements of the others
    reachable: dict[tuple[int, frozenset], bool] = {}

    def completes(i, used) -> bool:
        if i == len(order):
            return True
        if (i, used) not in reachable:
            reachable[i, used] = any(
                completes(i + 1, used | fixed.intersection(sol))
                for sol in placements(int(composition[order[i]]), kmaxes[i], used))
        return reachable[i, used]

    out: list[SiteAssignment] = []

    def combine(i, used, acc):
        if i == len(order):
            out.append(SiteAssignment(
                sites=tuple(acc), dof=sum(classes[ci].dof for _, ci in acc)))
            return
        for sol in placements(int(composition[order[i]]), kmaxes[i], used):
            taken = used | fixed.intersection(sol)
            if completes(i + 1, taken):
                combine(i + 1, taken, acc + [(order[i], ci) for ci in sol])
    if total:
        combine(0, frozenset(), [])
    if len(out) != total:
        raise AssertionError(  # pragma: no cover - two derivations of one number
            f"SITE_ASSIGNMENTS_COUNT: enumerated {len(out)}, counted {total}")
    return tuple(out)
