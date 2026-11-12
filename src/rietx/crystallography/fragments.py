"""Molecular fragments: a rigid-body template, its declared bonds and its body frame.

A rigid body (WP-1802, the second rung of rigid-bodies; issue #561) refines a
*template* as a whole: a set of atoms at Cartesian positions in Å.  This module
holds the template and one way of making it, and nothing of the refinement: no
orientation, no schema, no parameter table.

**The template's frame is its own.**  Coordinates are Å in the fragment's own
Cartesian frame and nothing here refers to a cell.  How a body's frame sits in
a crystal's is the frame contract WP-1803 decides; this module assumes nothing
about it.

**Bonds are declared, never perceived** (WP-1319's rule).  A coordinate-only
source cannot tell an aromatic ring from a chain of the same shape, so no
function here infers a bond from a distance.  ``Fragment.bonds`` is what the
caller declared: ``None`` when nothing was declared, a tuple of index pairs
otherwise, possibly empty.  :func:`from_zmatrix` takes its bonds as an
argument too, because a Z-matrix line's distance reference is a construction
choice and is not always a bond (a hydrogen may be placed from a dummy point).

**The body frame** (:meth:`Fragment.body_frame`) is fragment-internal: its
origin is the centroid, the point the body rotates about, and its axes are the
template's own.  It carries the rotations that move the fragment.  A rotation
about the unit axis n moves the fragment iff nᵀ·I·n > 0, where
I = Σᵢ (|rᵢ|²·𝟙 − rᵢ·rᵢᵀ) is the inertia tensor about the centroid with unit
weights.  Any positive weights give the same null space, so masses are not
needed, and the number of rotational degrees of freedom is rank(I): none for
one atom, two for a linear fragment (rotation about its own axis moves
nothing), three otherwise.  A near-linear fragment is counted by
:data:`INERTIA_RANK_TOL`.

**The Z-matrix** (:func:`from_zmatrix`) puts the first atom at the origin and
the second on +z.  The third is placed in the **x–z plane, on the x ≥ 0
side**.  The convention has to be chosen because the TOPAS Technical Reference
states it two ways: the x–z plane in § 10.22.7 (Coelho 2015, *TOPAS-Academic
V6 Technical Reference*, printed p. 103) and the x–y plane at the ``z_matrix``
keyword (printed p. 139).  The x–y reading cannot hold in general: the plane
of the first three atoms contains the first two, which lie on the z axis, and
the x–y plane does not contain the second, so a third atom lies in it only
for particular distances and angles.  The x ≥ 0 side is this module's choice.
``tests/test_fragments.py`` pins both.

**The dihedral sign.**  For a line "A bonded to B, at an angle to C, at a
dihedral to D", A's half-plane about the line B–C is D's half-plane rotated by
+φ, right-handed about the direction C → B (the keyword's rule, printed
p. 139).  This is the usual A–B–C–D torsion sign: positive when, looking from
B to C, the bond B–A turns clockwise onto C–D.  ``tests/test_fragments.py``
pins it on a hand-worked point.

**Collinearity.**  A dihedral is undefined when the three reference atoms B,
C and D lie on a line, because D then defines no half-plane about B–C.
:func:`from_zmatrix` refuses such a line and names the three atoms.  A bond
angle of 0° or 180° (A on the line B–C) is not refused: A is placed uniquely
and only its dihedral is inert, so from the fourth line on a line with
an angle of exactly 0° or 180° skips the collinearity check and ignores its
dihedral (acetylene needs no dummy).  An angle near but not at 0° or 180°
still needs a non-collinear B, C, D.  A dummy point (species :data:`DUMMY`) off the
line resolves a collinear triple; dummies are placed and then removed from the
returned fragment.

**The placement and its tangent** (WP-1814).  :func:`from_zmatrix` places
through :func:`zmatrix_points`, which takes the references and the internal
coordinates apart and also returns ∂(positions)/∂(internals) exactly: each
placement's six partials in closed form (:func:`_place_partials`), chained
forward through the lines in order.  :func:`zmatrix_reach` reads off the
references which lines each line's internals can move.  Nothing here refines:
the parameters, their paths and their composition with a body's pose are the
rigid-body table's.

Internal: nothing here is exported from ``rietx.crystallography`` or
``rietx``.  Lengths are in Å and the Z-matrix's angles and dihedrals, which a
caller types, in degrees.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

#: The Z-matrix species of a dummy point: placed, used as a reference, then
#: removed (module docstring, "Collinearity").
DUMMY: str = "X"

#: Below this sine of the angle at C between C→B and C→D, a Z-matrix line's
#: reference triple B, C, D is collinear.  A 15-digit template leaves ~1e-15 of
#: rounding in the dihedral's reference direction; at a sine of 1e-6 that
#: direction is still good to ~1e-9 rad, and a real reference triple bent by
#: less than 2e-4° is a typing error, not a geometry.
COLLINEAR_TOL: float = 1e-6

#: An eigenvalue of the inertia tensor below this fraction of the largest is a
#: null rotation.  I's eigenvalues scale as the squared distance from an axis,
#: so 1e-6 counts a fragment as linear when its atoms sit within ~1e-3 of its
#: size from one line: a 4-decimal rounding of a linear molecule stays
#: linear, and a triatomic bent by 1° does not.
INERTIA_RANK_TOL: float = 1e-6

#: The largest eigenvalue (Å²) below which the atoms coincide: no rotation DOF.
_COINCIDENT_A2 = 1e-20


@dataclass(frozen=True, eq=False)
class BodyFrame:
    """A fragment's own frame: origin at the centroid, the template's axes.

    ``rotation_axes`` holds orthonormal rows spanning the rotations that move
    the fragment: shape (0, 3) for one atom, (2, 3) for a linear fragment
    (the plane perpendicular to its axis), and the identity for any other,
    since every axis then moves it.  Both arrays are read-only.
    """

    origin: np.ndarray         # (3,) Å, in the template's frame
    rotation_axes: np.ndarray  # (k, 3), orthonormal rows

    @property
    def rotation_dofs(self) -> int:
        """The number of rotational degrees of freedom: 0, 2 or 3."""
        return int(self.rotation_axes.shape[0])


@dataclass(frozen=True, eq=False)
class Fragment:
    """A rigid-body template: species, Cartesian positions in Å, declared bonds.

    ``xyz`` is in the fragment's own frame (module docstring) and is stored
    read-only.  ``bonds`` is ``None`` when none were declared, and a tuple of
    index pairs (i < j) otherwise, possibly empty; it is never inferred from
    the positions.
    """

    species: tuple[str, ...]
    xyz: np.ndarray  # (n, 3) float64, Å
    bonds: tuple[tuple[int, int], ...] | None = None

    def __post_init__(self):
        if isinstance(self.species, str):
            raise ValueError(f"species {self.species!r} is one string; pass a "
                             f"sequence with one species per atom")
        species = tuple(str(s) for s in self.species)
        # the shape is the caller's, read before anything is reshaped: a
        # transposed (3, n) array has 3n elements too
        xyz = np.array(self.xyz, dtype=np.float64)
        if not species and xyz.size == 0:
            xyz = np.zeros((0, 3))
        if xyz.shape != (len(species), 3):
            raise ValueError(f"xyz has shape {np.shape(self.xyz)}; expected "
                             f"({len(species)}, 3), one row per species")
        if not np.all(np.isfinite(xyz)):
            raise ValueError("xyz holds a non-finite coordinate")
        if any(not s for s in species):
            raise ValueError("a species is empty")
        xyz.setflags(write=False)
        bonds = self.bonds
        if bonds is not None:
            norm = []
            for pair in bonds:
                i, j = _bond_indices(pair)
                if i == j or not (0 <= i < len(species) and 0 <= j < len(species)):
                    raise ValueError(f"bond {tuple(pair)} does not join two "
                                     f"distinct atoms of {len(species)}")
                norm.append((min(i, j), max(i, j)))
            if len(set(norm)) != len(norm):
                raise ValueError("a bond is listed twice")
            bonds = tuple(norm)
        object.__setattr__(self, "species", species)
        object.__setattr__(self, "xyz", xyz)
        object.__setattr__(self, "bonds", bonds)

    def __len__(self) -> int:
        return len(self.species)

    def centroid(self) -> np.ndarray:
        """Unweighted mean position (Å)."""
        return self.xyz.mean(axis=0)

    def body_frame(self, *, tol: float = INERTIA_RANK_TOL) -> BodyFrame:
        """The fragment's body frame and its rotation DOFs (module docstring).

        The rotation axes are the eigenvectors of :func:`inertia_tensor` whose
        eigenvalue exceeds ``tol`` × the largest; where all three do, the
        template's own axes are returned instead of an eigenbasis, which is
        arbitrary within a degenerate eigenvalue.
        """
        origin = self.centroid() if len(self) else np.zeros(3)
        w, v = np.linalg.eigh(inertia_tensor(self.xyz))
        top = float(w[-1]) if len(self) else 0.0
        if top <= _COINCIDENT_A2:
            axes = np.zeros((0, 3))
        else:
            moving = w > tol * top
            axes = np.eye(3) if moving.all() else v[:, moving].T.copy()
        origin = np.array(origin, dtype=np.float64)
        origin.setflags(write=False)
        axes.setflags(write=False)
        return BodyFrame(origin, axes)


def _bond_indices(pair) -> tuple[int, int]:
    """A declared bond's two indices, refusing a non-integer (as a Z-matrix
    reference is refused) rather than truncating it."""
    pair = tuple(pair)
    if len(pair) != 2 or any(isinstance(k, bool) or int(k) != k for k in pair):
        raise ValueError(f"bond {pair} must be two integer atom indices")
    return int(pair[0]), int(pair[1])


def inertia_tensor(xyz) -> np.ndarray:
    """Σᵢ (|rᵢ|²·𝟙 − rᵢ·rᵢᵀ) about the centroid, unit weights (Å²)."""
    r = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
    if len(r) == 0:
        return np.zeros((3, 3))
    r = r - r.mean(axis=0)
    s = r.T @ r
    return np.trace(s) * np.eye(3) - s


def rotation_dof_count(fragment: Fragment, *, tol: float = INERTIA_RANK_TOL) -> int:
    """Rotational DOFs of a rigid ``fragment``: 0 (atom), 2 (linear) or 3.

    The rank of its inertia tensor (:meth:`Fragment.body_frame`); a body's
    origin adds three translations on a general position.
    """
    return fragment.body_frame(tol=tol).rotation_dofs


# --- Z-matrix → Cartesian ----------------------------------------------------


def _unit(v):
    return v / np.linalg.norm(v)


def _place(b, c, d, r, angle_deg, dihedral_deg):
    """A at distance r from B, angle A–B–C, dihedral A–B–C–D (module docstring).

    With û = (B − C)/|B − C| (the thumb, C → B) and p̂ the unit part of D − C
    perpendicular to û, the new atom is
    B + r·(−cos θ·û + sin θ·(cos φ·p̂ + sin φ·û × p̂)).
    """
    u = _unit(b - c)
    p = d - c
    p = _unit(p - (p @ u) * u)
    th = math.radians(angle_deg)
    ph = math.radians(dihedral_deg)
    return b + r * (-math.cos(th) * u
                    + math.sin(th) * (math.cos(ph) * p + math.sin(ph) * np.cross(u, p)))


def _place_partials(b, c, d, r, angle_deg, dihedral_deg):
    """The six partials of :func:`_place`, in closed form.

    Returns ∂A/∂B, ∂A/∂C, ∂A/∂D (3 × 3 each), then ∂A/∂r (per Å), ∂A/∂θ and
    ∂A/∂φ (3-vectors, **per degree**: θ and φ are typed in degrees, so each
    carries π/180).  With L = |B − C|, û = (B − C)/L, w = D − C,
    w⊥ = w − (w·û)û, p̂ = w⊥/|w⊥|, n̂ = û × p̂ and
    g = −cos θ·û + sin θ·(cos φ·p̂ + sin φ·n̂), so that A = B + r·g:

    * dû = (𝟙 − ûûᵀ)(dB − dC)/L;
    * dw⊥ = (𝟙 − ûûᵀ)·dw − (ûwᵀ + (w·û)𝟙)·dû, with dw = dD − dC;
    * dp̂ = (𝟙 − p̂p̂ᵀ)·dw⊥/|w⊥| and dn̂ = dû × p̂ + û × dp̂;
    * dA = dB + r·(−cos θ·dû + sin θ·(cos φ·dp̂ + sin φ·dn̂)) + g·dr
      + r·(sin θ·û + cos θ·(cos φ·p̂ + sin φ·n̂))·dθ
      + r·sin θ·(−sin φ·p̂ + cos φ·n̂)·dφ.
    """
    eye = np.eye(3)
    v = b - c
    length = float(np.linalg.norm(v))
    u = v / length
    w = d - c
    wp = w - (w @ u) * u
    wlen = float(np.linalg.norm(wp))
    p = wp / wlen
    n = np.cross(u, p)
    th = math.radians(angle_deg)
    ph = math.radians(dihedral_deg)
    ct, st, cp, sp = math.cos(th), math.sin(th), math.cos(ph), math.sin(ph)
    pu = eye - np.outer(u, u)
    pp = eye - np.outer(p, p)
    lift = (w @ u) * eye + np.outer(u, w)
    # dû/dB = Pu/L, dû/dC = −Pu/L, dû/dD = 0; dw/dB = 0, dw/dC = −1, dw/dD = 1
    du_db = pu / length
    out = []
    for du, dw in ((du_db, np.zeros((3, 3))), (-du_db, -eye), (np.zeros((3, 3)), eye)):
        dp = pp @ (pu @ dw - lift @ du) / wlen
        dn = np.cross(du.T, p).T + np.cross(u, dp.T).T
        out.append(r * (-ct * du + st * (cp * dp + sp * dn)))
    out[0] = out[0] + eye
    deg = math.radians(1.0)
    g = -ct * u + st * (cp * p + sp * n)
    d_r = g
    d_th = r * (st * u + ct * (cp * p + sp * n)) * deg
    d_ph = r * st * (-sp * p + cp * n) * deg
    return out[0], out[1], out[2], d_r, d_th, d_ph


def _collinear_sine(b, c, d) -> float:
    """sin of the angle at C between C→B and C→D; 0 when a length is 0."""
    cb, cd = b - c, d - c
    nb, nd = np.linalg.norm(cb), np.linalg.norm(cd)
    if nb == 0.0 or nd == 0.0:
        return 0.0
    return float(np.linalg.norm(np.cross(cb, cd)) / (nb * nd))


def zmatrix_points(refs: Sequence[Sequence[int]], values: Sequence[Sequence[float]],
                   *, tangents: bool = False, names: Sequence[str] | None = None):
    """Every Z-matrix line's position, and with ``tangents`` its exact tangent.

    ``refs[i]`` holds line i's earlier reference lines and ``values[i]`` its
    internal coordinates: ``()`` and ``()`` for line 0, ``(b,)`` and ``(r,)``
    for line 1, ``(b, c)`` and ``(r, angle)`` for line 2, and ``(b, c, d)``
    and ``(r, angle, dihedral)`` from line 3 on (:func:`from_zmatrix` for the
    convention; r in Å, angles in degrees).  Every line is placed, a dummy
    included: dropping dummies is the caller's.  ``names`` (one per line)
    only labels the refusals.

    Returns the positions, (n, 3) in Å.  With ``tangents=True`` it returns
    ``(positions, tangent)``, the tangent ∂(position)/∂ζ of shape (m, n, 3),
    the column-first layout of the rigid-body block's twist tangents.  ζ lists
    every line's internals in line order, r then angle then dihedral, so line
    1 owns column 0, line 2 columns 1–2, and line i ≥ 3 columns 3i − 6 to
    3i − 4; columns are per Å for r and **per degree** for an angle or a
    dihedral.  The tangent is propagated forward through the placement
    recursion with the closed-form partials of each placement
    (:func:`_place_partials`): a line's tangent is its own internals' column
    plus the chain through its reference lines' tangents.

    **At an angle of exactly 0° or 180°** (from line 3 on) the position is
    B − r·cos θ·û, whatever the dihedral, and the dihedral's column is zero.
    The angle sits at the edge of its domain [0, 180], so its column is the
    one-sided derivative inside it, which bends A into the half-plane the
    dihedral names; when B, C and D are collinear no angle other than the
    edge is admissible (any other is refused), and the angle's column is zero.

    Refusals (``ValueError``): a reference that is not an earlier line or
    names one line twice, r ≤ 0, an angle outside [0, 180], and a collinear
    reference triple B, C, D at an angle other than 0° or 180°
    (:data:`COLLINEAR_TOL`), named with its three lines.
    """
    if len(refs) != len(values):
        raise ValueError(f"{len(refs)} reference rows for {len(values)} value rows; "
                         f"pass one of each per Z-matrix line")
    n_lines = len(refs)
    if names is not None and len(names) != n_lines:
        raise ValueError(f"{len(names)} names for {n_lines} Z-matrix lines")

    def who(i):
        return f"Z-matrix line {i}" + ("" if names is None else f" ({names[i]})")

    def atom(k):
        return f"{k}" + ("" if names is None else f" ({names[k]})")

    m = sum(min(i, 3) for i in range(n_lines))
    pos = np.zeros((n_lines, 3))
    tan = np.zeros((m, n_lines, 3)) if tangents else None
    col = 0
    for i in range(n_lines):
        want = min(i, 3)
        ref = tuple(refs[i])
        val = tuple(values[i])
        if len(ref) != want or len(val) != want:
            raise ValueError(f"{who(i)} has {len(ref)} references and {len(val)} "
                             f"values; line {i} takes {want} of each")
        if any(isinstance(k, bool) or int(k) != k for k in ref):
            raise ValueError(f"{who(i)}: the atom references {list(ref)} must be "
                             f"integer line indices")
        ref = tuple(int(k) for k in ref)
        for k in ref:
            if not 0 <= k < i:
                raise ValueError(f"{who(i)} refers to atom {k}, which is not an "
                                 f"earlier line")
        if len(set(ref)) != len(ref):
            raise ValueError(f"{who(i)} names atom {list(ref)} more than once")
        if i >= 1:
            r = float(val[0])
            if not r > 0:
                raise ValueError(f"{who(i)}: distance {r} Å is not positive")
        if i >= 2:
            angle = float(val[1])
            if not 0.0 <= angle <= 180.0:
                raise ValueError(f"{who(i)}: angle {angle}° is outside [0, 180]")
        cols = range(col, col + want)
        col += want
        if i == 0:
            continue
        if i == 1:
            pos[1] = (0.0, 0.0, r)
            if tangents:
                tan[cols[0], 1, 2] = 1.0
            continue
        b, c = pos[ref[0]], pos[ref[1]]
        if i == 2:
            # the reference half-plane is x ≥ 0: a virtual D on +x from C,
            # which moves with C
            d = c + np.array([1.0, 0.0, 0.0])
            pos[2] = _place(b, c, d, r, angle, 0.0)
            if tangents:
                pb, pc, pd, d_r, d_th, _ = _place_partials(b, c, d, r, angle, 0.0)
                tan[:, 2] = tan[:, ref[0]] @ pb.T + tan[:, ref[1]] @ (pc + pd).T
                tan[cols[0], 2] += d_r
                tan[cols[1], 2] += d_th
            continue
        d = pos[ref[2]]
        dihedral = float(val[2])
        on_line = angle in (0.0, 180.0)
        open_triple = _collinear_sine(b, c, d) >= COLLINEAR_TOL
        if on_line:
            # A on the line B–C: the dihedral moves nothing, so D is not
            # needed and its collinearity is no refusal
            pos[i] = b - r * math.cos(math.radians(angle)) * _unit(b - c)
        elif not open_triple:
            names_ = ", ".join(atom(k) for k in ref)
            raise ValueError(
                f"{who(i)}: reference atoms {names_} are "
                f"collinear, so the dihedral about {ref[0]}–{ref[1]} is "
                f"undefined; insert a dummy atom (species {DUMMY!r}) off "
                f"the line")
        else:
            pos[i] = _place(b, c, d, r, angle, dihedral)
        if not tangents:
            continue
        if open_triple:
            pb, pc, pd, d_r, d_th, d_ph = _place_partials(b, c, d, r, angle, dihedral)
            if on_line:
                d_ph = np.zeros(3)
        else:
            # A = B − r·cos θ·û, with no admissible θ but this one
            v = b - c
            length = float(np.linalg.norm(v))
            u = v / length
            cos_t = math.cos(math.radians(angle))
            pc = r * cos_t * (np.eye(3) - np.outer(u, u)) / length
            pb = np.eye(3) - pc
            pd = np.zeros((3, 3))
            d_r, d_th, d_ph = -cos_t * u, np.zeros(3), np.zeros(3)
        tan[:, i] = (tan[:, ref[0]] @ pb.T + tan[:, ref[1]] @ pc.T
                     + tan[:, ref[2]] @ pd.T)
        tan[cols[0], i] += d_r
        tan[cols[1], i] += d_th
        tan[cols[2], i] += d_ph
    return (pos, tan) if tangents else pos


def zmatrix_reach(refs: Sequence[Sequence[int]]) -> tuple[frozenset[int], ...]:
    """The lines each line's own internal coordinates move, from the references.

    Entry i holds line i and, transitively, every later line that refers to a
    line already in it (as b, c or d); line 0 has no internals, so its entry
    is empty.  Line 2's virtual reference point moves with its c, so the
    references are the whole dependency graph, and an internal's tangent
    column (:func:`zmatrix_points`) is zero on every line outside its entry.
    The entry may hold lines the tangent leaves still (a line whose own
    geometry absorbs the motion), so it is a covering pattern, not a
    measurement; dummies are included, and dropping them is the caller's.
    """
    refs = [tuple(int(k) for k in ref) for ref in refs]
    out: list[frozenset[int]] = []
    for i in range(len(refs)):
        if i == 0:
            out.append(frozenset())
            continue
        reached = {i}
        for j in range(i + 1, len(refs)):
            if any(k in reached for k in refs[j]):
                reached.add(j)
        out.append(frozenset(reached))
    return tuple(out)


def from_zmatrix(lines: Sequence[Sequence], bonds=None) -> Fragment:
    """Cartesian fragment from a Z-matrix.

    Each line is ``(species,)`` for the first atom, ``(species, b, r)`` for
    the second, ``(species, b, r, c, angle)`` for the third, and
    ``(species, b, r, c, angle, d, dihedral)`` from the fourth on.  ``b``,
    ``c`` and ``d`` are 0-based indices of earlier lines, ``r`` is in Å,
    ``angle`` (A–B–C) and ``dihedral`` (A–B–C–D) in degrees.  First atom at
    the origin, second on +z, third in the x–z plane with x ≥ 0, and the
    dihedral right-handed about C → B (module docstring, with the page
    references for the convention).

    A line whose reference atoms b, c, d are collinear is refused, naming
    them, unless its angle is exactly 0° or 180° (its dihedral is then
    inert).  Lines with species :data:`DUMMY` are placed and then left out of
    the result; the remaining atoms keep their order.  ``bonds`` are declared
    as pairs of line indices and renumbered with the atoms; a bond to a dummy
    is refused.  With ``bonds=None`` the fragment declares none.
    """
    species: list[str] = []
    refs: list[tuple[int, ...]] = []
    values: list[tuple[float, ...]] = []
    for i, line in enumerate(lines):
        line = tuple(line)
        want = 1 if i == 0 else 3 if i == 1 else 5 if i == 2 else 7
        if len(line) != want:
            raise ValueError(f"Z-matrix line {i} ({line[0] if line else '?'}) has "
                             f"{len(line)} entries; line {i} takes {want}")
        sp = str(line[0])
        if any(isinstance(k, bool) or int(k) != k for k in line[1::2]):
            raise ValueError(f"Z-matrix line {i} ({sp}): the atom references "
                             f"{list(line[1::2])} must be integer line indices")
        species.append(sp)
        refs.append(tuple(int(k) for k in line[1::2]))
        values.append(tuple(float(v) for v in line[2::2]))
    pos = zmatrix_points(refs, values, names=species)
    keep = [i for i, s in enumerate(species) if s != DUMMY]
    index = {old: new for new, old in enumerate(keep)}
    declared = None
    if bonds is not None:
        declared = []
        for pair in bonds:
            i, j = _bond_indices(pair)
            for k in (i, j):
                if not 0 <= k < len(species):
                    raise ValueError(f"bond {tuple(pair)} names line {k}, which "
                                     f"is not in the Z-matrix")
                if species[k] == DUMMY:
                    raise ValueError(f"bond {tuple(pair)} joins dummy line {k}, "
                                     f"which is not in the fragment")
            declared.append((index[i], index[j]))
    xyz = np.array([pos[i] for i in keep]).reshape(-1, 3)
    return Fragment(tuple(species[i] for i in keep), xyz,
                    None if declared is None else tuple(declared))
