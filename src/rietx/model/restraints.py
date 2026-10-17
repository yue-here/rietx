"""Soft observational restraints as extra residual rows (WP-0406).

A restraint contributes a single row  √weight·(computed − target)/σ  to the
residual vector, appended *after* the data (and background-penalty / Pawley-
restraint) rows — the same penalty-row seam the P-spline background and Pawley
equal-split already use, so the rows land in the covariance (JᵀJ) but are
excluded from Rwp/Durbin-Watson/Bérar-Lelann (soft observations, not data;
Waser, 1963, Acta Cryst. 16, 1091; Watkin, 1994, Acta Cryst. A50, 411).

Unlike those two precedents the rows are **nonlinear** in the parameters: a
bond length d = √(Δxᵀ·G·Δx) and a bond angle both depend on the refined
fractional coordinates *and* the cell, so their rows and Jacobian are
recomputed per-θ.  The geometry is expressed twice:

* :func:`restraint_residual` — the traceable value (``xp`` ops), so the whole
  residual stays one differentiable function for the autodiff backends;
* :func:`restraint_partials` / :func:`summarise_restraints` — host-side numpy,
  the exact analytic ∂row/∂p that :func:`optimize.least_squares._make_jacobian`
  chains through the affine constraint block (Jacobian *support*, never
  traced — the same split as ``structure_factor.d_f2_d_xyz`` vs the forward
  ``structure_factors_squared``).

Periodic boundary conditions: the neighbour atom is taken at a symmetry image
``R·x + t + n``.  ``(R, t, n)`` are **frozen per stage** (the exact analogue of
the frozen hkl list / orbit-op subsets); either named explicitly on the
restraint (``op_index``/``translation``) or resolved to the minimum image at
the stage's compile-time coordinates.  Positions still move smoothly inside a
stage — only the discrete image choice is fixed — so the residual stays smooth
for the FD/autodiff Jacobians.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..backend import get_backend
from ..crystallography.lattice import direct_metric_tensor
from ..params.derived import cartesian_frame
from ..schemas.structure import (
    AngleRestraint,
    AntiBumpRestraint,
    BondRestraint,
    PlanarityRestraint,
    TetherRestraint,
)

_CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")
_XYZ = ("x", "y", "z")
#: one shell of neighbouring cells for the minimum-image search — n ∈ {−1,0,1}³.
#: One shell suffices for near-orthogonal cells; a strongly oblique cell
#: (γ far from 90°) may need two, but powder restraints name a specific image
#: (``op_index``) in that regime rather than trusting the auto-search.
MIN_IMAGE_SHELL = 1
#: cos θ is clamped just inside [−1, 1] before ``arccos``: the angle derivative
#: ∝ 1/sin θ blows up at 0°/180°, which are not supported restraint targets.
_COS_CLAMP = 1.0 - 1e-9
#: a minimum-image candidate closer than this (Å²) is treated as a coincident
#: self-image and skipped (matters only for same-atom M–M restraints).
_COINCIDENT_D2 = 1e-6
#: a planarity set is refused when its two smallest scatter eigenvalues lie
#: within this fraction of the largest: the points are on a line (or
#: coincident) and no plane, so no normal, is defined (WP-1809, #759 § 3a).
PLANE_DEGENERATE_REL = 1e-6


# ----------------------------------------------------------------------
# compiled, frozen-per-stage restraint objects
# ----------------------------------------------------------------------
@dataclass
class _Bond:
    phase: int
    i: int
    j: int
    R: np.ndarray  # (3,3) frozen rotation for the atom_j image
    t: np.ndarray  # (3,) frozen op translation
    n: np.ndarray  # (3,) frozen lattice shift
    target: float
    sigma: float
    weight: float
    #: ``None`` two-sided; ``"max"`` a tether (row only past the target),
    #: ``"min"`` an anti-bump (row only inside it) — WP-1809
    side: str | None = None


@dataclass
class _Angle:
    phase: int
    i: int
    j: int  # vertex
    k: int
    Ri: np.ndarray
    ti: np.ndarray
    ni: np.ndarray
    Rk: np.ndarray
    tk: np.ndarray
    nk: np.ndarray
    target_deg: float
    sigma: float
    weight: float


@dataclass
class _Value:
    path: str
    target: float
    sigma: float
    weight: float
    phase: int | None = None


@dataclass
class _Plane:
    """A planarity restraint: one row per entry, its distance to the LS plane.

    Each entry ``m`` is atom ``atoms[m]`` at its frozen image
    ``R[m]·x + t[m] + n[m]``.  ``normal`` is the plane normal (Cartesian, in
    :func:`~rietx.params.derived.cartesian_frame`'s frame) at compile, frozen only as
    the sign reference for the eigenvector: an eigensolver's sign is
    arbitrary, and the rows are signed.
    """

    phase: int
    atoms: list
    R: list
    t: list
    n: list
    sigma: float
    weight: float
    normal: np.ndarray

    @property
    def n_rows(self) -> int:
        return len(self.atoms)


def _item_rows(it) -> int:
    return it.n_rows if isinstance(it, _Plane) else 1


@dataclass
class CompiledRestraints:
    """The frozen restraint rows of a compiled model, in schema order.

    One row per item, except a planarity item, which has one per atom.
    """

    items: list

    @property
    def n_rows(self) -> int:
        return sum(_item_rows(it) for it in self.items)


# ----------------------------------------------------------------------
# compile-time resolution (minimum-image freeze)
# ----------------------------------------------------------------------
def resolve_phase_restraints(phase, ip: int, sites, cell) -> list:
    """Freeze the PBC image of every restraint of ``phase`` at its coordinates.

    ``sites`` is the phase's :class:`PhaseSites` (frozen orbit-op subsets);
    ``cell`` its compile-time (a, b, c, α, β, γ).  Returns the ordered list of
    compiled restraint objects (empty if the phase declares none).
    """
    g = _metric_g(cell)
    out: list = []
    for r in phase.restraints:
        if isinstance(r, (BondRestraint, TetherRestraint, AntiBumpRestraint)):
            x_i = _atom_xyz(phase, r.atom_i)
            x_j = _atom_xyz(phase, r.atom_j)
            rot, tr, n = _resolve_image(sites, r.atom_j, x_i, x_j,
                                        r.op_index, r.translation, g)
            if isinstance(r, TetherRestraint):
                target, side = r.max_distance, "max"
            elif isinstance(r, AntiBumpRestraint):
                target, side = r.min_distance, "min"
            else:
                target, side = r.target, None
            out.append(_Bond(ip, r.atom_i, r.atom_j, rot, tr, n,
                             target, r.sigma, r.weight, side))
        elif isinstance(r, AngleRestraint):
            x_i = _atom_xyz(phase, r.atom_i)
            x_j = _atom_xyz(phase, r.atom_j)
            x_k = _atom_xyz(phase, r.atom_k)
            ri, ti, ni = _resolve_image(sites, r.atom_i, x_j, x_i,
                                        r.op_index_i, r.translation_i, g)
            rk, tk, nk = _resolve_image(sites, r.atom_k, x_j, x_k,
                                        r.op_index_k, r.translation_k, g)
            out.append(_Angle(ip, r.atom_i, r.atom_j, r.atom_k,
                             ri, ti, ni, rk, tk, nk,
                             r.target_deg, r.sigma, r.weight))
        elif isinstance(r, PlanarityRestraint):
            out.append(_resolve_plane(phase, ip, sites, cell, g, r))
        else:  # ValueRestraint
            out.append(_Value(r.path, r.target, r.sigma, r.weight, ip))
    return out


def _resolve_plane(phase, ip, sites, cell, g, r) -> _Plane:
    """Freeze each entry's image and the normal's sign; refuse a line.

    The first entry sits where it is stored unless an image is named; every
    other entry left ``None`` takes the image nearest the centroid of the
    entries resolved so far, so a plane of eight or ten atoms stays inside
    one molecule where a symmetry copy of a neighbour sits closer to the
    first atom than the far side of the ring does.
    """
    ops = r.op_indices or [None] * len(r.atoms)
    trs = r.translations or [(0, 0, 0)] * len(r.atoms)
    eye, zero = np.eye(3), np.zeros(3)
    placed: list[np.ndarray] = []
    Rs, ts, ns = [], [], []
    for m, (j, op, tr) in enumerate(zip(r.atoms, ops, trs, strict=True)):
        if m == 0 and op is None:
            rot, t, n = eye, zero, np.asarray(tr, dtype=np.float64)
        else:
            rot, t, n = _resolve_image(sites, j, np.mean(placed, axis=0),
                                       _atom_xyz(phase, j), op, tr, g)
        Rs.append(rot)
        ts.append(t)
        ns.append(n)
        placed.append(rot @ _atom_xyz(phase, j) + t + n)
    pts = np.array([rot @ _atom_xyz(phase, j) + t + n for j, rot, t, n
                    in zip(r.atoms, Rs, ts, ns, strict=True)])
    cart = pts @ np.asarray(cartesian_frame(cell), dtype=np.float64).T
    d = cart - cart.mean(axis=0)
    lam, vec = np.linalg.eigh(d.T @ d)
    if lam[1] - lam[0] <= PLANE_DEGENERATE_REL * max(lam[2], 1e-300):
        labels = [phase.atoms[j].label for j in r.atoms]
        raise ValueError(
            f"planarity restraint on {phase.name!r} atoms {labels}: the points "
            f"lie on a line (scatter eigenvalues {lam[0]:.3g}, {lam[1]:.3g}, "
            f"{lam[2]:.3g} Å²), so no plane is defined; restrain a set that "
            "spans two directions, or use bond and angle restraints")
    return _Plane(ip, list(r.atoms), Rs, ts, ns, r.sigma, r.weight,
                  vec[:, 0].copy())


def _atom_xyz(phase, j: int) -> np.ndarray:
    a = phase.atoms[j]
    return np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64)


def _resolve_image(sites, j, reference, base_xyz, op_index, translation, g):
    """Freeze (R, t, n) for the image of atom ``j`` relative to ``reference``.

    With ``op_index`` given, that orbit op and the explicit ``translation`` are
    used verbatim.  Otherwise the minimum-image search enumerates the atom's
    frozen orbit ops × the ``{−1,0,1}³`` lattice shell and keeps the closest
    (non-coincident) image, measured with the compile-time metric ``g``.

    The shell is centred, per op, on the lattice vector that brings the image
    nearest ``reference`` (``round(reference − R·x − t)``), so the search does
    not depend on which unit cell a coordinate happens to be stored in.  A
    shell around n = 0 missed the image whenever the two stored coordinates
    differed by more than about one cell after the operation — an atom at
    x = 1.05 and its partner's ``−x`` image at x = −1.1 — and then froze a
    distant image as "nearest".  Coordinates outside [0, 1) are ordinary: CIFs
    store a molecule whole across a cell edge, and a rigid body places its
    atoms about an origin anywhere.
    """
    ops_r, ops_t = sites.ops[j]
    m = len(ops_r)
    if op_index is not None:
        if not 0 <= op_index < m:
            raise ValueError(
                f"restraint op_index {op_index} is out of range for atom {j} "
                f"(orbit has {m} operation(s), indices 0..{m - 1})")
        return (np.asarray(ops_r[op_index], dtype=np.float64),
                np.asarray(ops_t[op_index], dtype=np.float64),
                np.asarray(translation, dtype=np.float64))
    shell = range(-MIN_IMAGE_SHELL, MIN_IMAGE_SHELL + 1)
    best: tuple[float, int, np.ndarray] | None = None
    for mi in range(m):
        img0 = ops_r[mi] @ base_xyz + ops_t[mi]
        centre = np.round(reference - img0)
        for na in shell:
            for nb in shell:
                for nc in shell:
                    n = centre + np.array([na, nb, nc], dtype=np.float64)
                    dx = img0 + n - reference
                    d2 = float(dx @ (g @ dx))
                    if d2 < _COINCIDENT_D2:
                        continue
                    if best is None or d2 < best[0]:
                        best = (d2, mi, n)
    if best is None:  # every image coincident (a self-restraint at the origin)
        return (np.asarray(ops_r[0], dtype=np.float64),
                np.asarray(ops_t[0], dtype=np.float64),
                np.zeros(3, dtype=np.float64))
    _, mi, n = best
    return (np.asarray(ops_r[mi], dtype=np.float64),
            np.asarray(ops_t[mi], dtype=np.float64), n)


# ----------------------------------------------------------------------
# traceable residual value (xp ops — one differentiable function)
# ----------------------------------------------------------------------
def restraint_residual(compiled: CompiledRestraints, values: dict):
    """√w·(computed − target)/σ rows, traceable: one per compiled restraint, and
    one per listed atom for a planarity item."""
    xp = get_backend()
    rows = []
    for it in compiled.items:
        if isinstance(it, _Plane):
            pref = math.sqrt(it.weight) / it.sigma
            rows.extend(d * pref for d in _plane_distances(it, values))
            continue
        if isinstance(it, _Bond):
            computed, target = _bond_distance(it, values), it.target
        elif isinstance(it, _Angle):
            computed, target = _angle_deg(it, values), it.target_deg
        else:  # _Value
            computed, target = values[it.path], it.target
        dev = computed - target
        side = getattr(it, "side", None)
        if side == "max":          # a tether: nothing inside its range
            dev = xp.maximum(dev, 0.0 * dev)
        elif side == "min":        # an anti-bump: nothing beyond its range
            dev = xp.minimum(dev, 0.0 * dev)
        rows.append(dev * (math.sqrt(it.weight) / it.sigma))
    return xp.stack(rows)


def _plane_distances(it: "_Plane", values: dict):
    """The signed distances (Å) of a planarity item's entries to their LS plane.

    Traceable: the normal is ``xp.linalg.eigh``'s eigenvector of the smallest
    eigenvalue of the Cartesian scatter matrix, signed against the frozen
    compile-time normal (the sign has zero derivative, and +1 where the two
    are perpendicular).
    """
    xp = get_backend()
    ip = it.phase
    amat = cartesian_frame(_cell_tuple(values, ip))
    pts = xp.stack([
        xp.matmul(amat, xp.asarray(R) @ _xyz_traced(values, ip, j, xp)
                  + xp.asarray(t) + xp.asarray(n))
        for j, R, t, n in zip(it.atoms, it.R, it.t, it.n, strict=True)])
    d = pts - xp.sum(pts, axis=0) / len(it.atoms)
    scatter = xp.einsum("ki,kj->ij", d, d)
    _, vec = xp.linalg.eigh(scatter)
    normal = vec[:, 0]
    # sign(0) = 0 would zero the whole plane where the normal turns
    # perpendicular to the frozen one; the numpy twin takes +1 there
    dot = xp.sum(normal * xp.asarray(it.normal))
    normal = normal * xp.where(dot >= 0.0, 1.0 + 0.0 * dot, -1.0 + 0.0 * dot)
    dist = xp.matmul(d, normal)
    return [dist[m] for m in range(len(it.atoms))]


def _cell_tuple(values: dict, ip: int) -> tuple:
    return tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_NAMES)


def _xyz_traced(values: dict, ip: int, j: int, xp):
    return xp.stack([values[f"phases.{ip}.atoms.{j}.{c}"] for c in _XYZ])


def _bond_distance(it: _Bond, values: dict):
    xp = get_backend()
    ip = it.phase
    x_i = _xyz_traced(values, ip, it.i, xp)
    x_j = _xyz_traced(values, ip, it.j, xp)
    dx = xp.asarray(it.R) @ x_j + xp.asarray(it.t) + xp.asarray(it.n) - x_i
    g = direct_metric_tensor(*_cell_tuple(values, ip))
    return xp.sqrt(dx @ (g @ dx))


def _angle_deg(it: _Angle, values: dict):
    xp = get_backend()
    ip = it.phase
    x_i = _xyz_traced(values, ip, it.i, xp)
    x_j = _xyz_traced(values, ip, it.j, xp)
    x_k = _xyz_traced(values, ip, it.k, xp)
    u = xp.asarray(it.Ri) @ x_i + xp.asarray(it.ti) + xp.asarray(it.ni) - x_j
    v = xp.asarray(it.Rk) @ x_k + xp.asarray(it.tk) + xp.asarray(it.nk) - x_j
    g = direct_metric_tensor(*_cell_tuple(values, ip))
    cos = (u @ (g @ v)) / xp.sqrt((u @ (g @ u)) * (v @ (g @ v)))
    cos = xp.clip(cos, -_COS_CLAMP, _COS_CLAMP)
    return xp.degrees(xp.arccos(cos))


# ----------------------------------------------------------------------
# host-numpy geometry + analytic partials (Jacobian support, never traced)
# ----------------------------------------------------------------------
_DEG = math.pi / 180.0


def _metric_g(cell) -> np.ndarray:
    a, b, c, al, be, ga = (float(v) for v in cell)
    ca, cb, cg = np.cos(np.radians([al, be, ga]))
    return np.array([[a * a, a * b * cg, a * c * cb],
                     [a * b * cg, b * b, b * c * ca],
                     [a * c * cb, b * c * ca, c * c]], dtype=np.float64)


def _metric_g_derivs(cell) -> list[np.ndarray]:
    """The six exact ∂G/∂{a,b,c,α,β,γ} (angles in degrees, hence the π/180)."""
    a, b, c, al, be, ga = (float(v) for v in cell)
    ca, cb, cg = np.cos(np.radians([al, be, ga]))
    sa, sb, sg = np.sin(np.radians([al, be, ga]))
    z = 0.0
    dal, dbe, dga = -b * c * sa * _DEG, -a * c * sb * _DEG, -a * b * sg * _DEG
    return [
        np.array([[2 * a, b * cg, c * cb], [b * cg, z, z], [c * cb, z, z]]),
        np.array([[z, a * cg, z], [a * cg, 2 * b, c * ca], [z, c * ca, z]]),
        np.array([[z, z, a * cb], [z, z, b * ca], [a * cb, b * ca, 2 * c]]),
        np.array([[z, z, z], [z, z, dal], [z, dal, z]]),
        np.array([[z, z, dbe], [z, z, z], [dbe, z, z]]),
        np.array([[z, dga, z], [dga, z, z], [z, z, z]]),
    ]


def _xyz_np(values: dict, ip: int, j: int) -> np.ndarray:
    return np.array([values[f"phases.{ip}.atoms.{j}.{c}"] for c in _XYZ],
                    dtype=np.float64)


def _bond_value_np(it: _Bond, values: dict) -> float:
    ip = it.phase
    g = _metric_g(_cell_tuple(values, ip))
    dx = it.R @ _xyz_np(values, ip, it.j) + it.t + it.n - _xyz_np(values, ip, it.i)
    return math.sqrt(float(dx @ (g @ dx)))


def _angle_value_np(it: _Angle, values: dict) -> float:
    theta, _ = _angle_geometry_np(it, values)
    return theta


def _angle_geometry_np(it: _Angle, values: dict):
    ip = it.phase
    cell = _cell_tuple(values, ip)
    g = _metric_g(cell)
    u = it.Ri @ _xyz_np(values, ip, it.i) + it.ti + it.ni - _xyz_np(values, ip, it.j)
    v = it.Rk @ _xyz_np(values, ip, it.k) + it.tk + it.nk - _xyz_np(values, ip, it.j)
    gu, gv = g @ u, g @ v
    su, sv, p = float(u @ gu), float(v @ gv), float(u @ gv)
    root = math.sqrt(su * sv) if su > 0.0 and sv > 0.0 else 0.0
    cos = min(max(p / root, -_COS_CLAMP), _COS_CLAMP) if root > 0.0 else 0.0
    theta = math.degrees(math.acos(cos))
    return theta, dict(u=u, v=v, gu=gu, gv=gv, su=su, sv=sv, p=p,
                       root=root, cos=cos, g=g, cell=cell)


def restraint_partials(compiled: CompiledRestraints, values: dict, table
                       ) -> np.ndarray:
    """∂row_i/∂p_phys as (n_rows × n_entries), physical-parameter columns.

    The affine constraint chain ∂p_phys/∂θ = C·dφ/du is applied by the caller
    (``J[restr, :n_table] = (R_phys @ C.toarray()) · dpdu``), so this need only
    write each row's partials against the *entry* dot-paths it touches — atom
    x/y/z and the six cell parameters for bond/angle, the target path for a
    value restraint.  DOF chaining then falls out of the shared C the analytic
    structural columns use.
    """
    idx = table._paths
    r_phys = np.zeros((compiled.n_rows, len(table.entries)), dtype=np.float64)
    row = 0
    for it in compiled.items:
        pref = math.sqrt(it.weight) / it.sigma
        if isinstance(it, _Plane):
            _plane_row_partials(r_phys, row, it, values, idx, pref)
            row += it.n_rows
            continue
        if isinstance(it, _Bond):
            _bond_row_partials(r_phys, row, it, values, idx, pref)
        elif isinstance(it, _Angle):
            _angle_row_partials(r_phys, row, it, values, idx, pref)
        else:  # _Value: ∂row/∂path = √w/σ
            r_phys[row, idx[it.path]] += pref
        row += 1
    return r_phys


def _plane_geometry_np(it: _Plane, values: dict):
    """Host twin of :func:`_plane_distances`, with what the partials need."""
    ip = it.phase
    cell = _cell_tuple(values, ip)
    amat = np.asarray(cartesian_frame(cell), dtype=np.float64)
    frac = np.array([R @ _xyz_np(values, ip, j) + t + n for j, R, t, n
                     in zip(it.atoms, it.R, it.t, it.n, strict=True)])
    d = frac @ amat.T
    d = d - d.mean(axis=0)
    lam, vec = np.linalg.eigh(d.T @ d)
    normal = vec[:, 0] * (1.0 if float(vec[:, 0] @ it.normal) >= 0.0 else -1.0)
    return d @ normal, dict(cell=cell, amat=amat, frac=frac, d=d, lam=lam,
                            vec=vec, normal=normal)


def _plane_row_partials(r_phys, row0, it, values, idx, pref) -> None:
    """∂dₖ/∂p for every row of a planarity item (exact eigenvector derivative).

    With D_m the centred Cartesian points, M = Σ D_m D_mᵀ, n its unit
    eigenvector of the smallest eigenvalue λ and P = Σ_{i≠0} vᵢvᵢᵀ/(λᵢ − λ)
    the pseudo-inverse of M − λI, a move of point m gives
    dn = −P(dₘ I + D_m nᵀ)·dp_m (Magnus 1985, *Econometric Theory* 1, 179,
    Theorem 1), so ∂dₖ/∂p_m = n(δₖₘ − 1/N − D_mᵀPDₖ) − dₘPDₖ.  A fractional
    coordinate enters through p = A·(R·x + t + n); the cell through A, and
    since the distances depend on the points only through their inner
    products, dA = ½·A⁻ᵀ·∂G serves for every cell parameter.
    """
    dist, s = _plane_geometry_np(it, values)
    d, lam, vec, normal, amat = s["d"], s["lam"], s["vec"], s["normal"], s["amat"]
    n_pts = len(it.atoms)
    pinv = sum(np.outer(vec[:, i], vec[:, i]) / (lam[i] - lam[0]) for i in (1, 2))
    pd = d @ pinv                                  # row k: P·D_k
    a_inv_t = np.linalg.inv(amat).T
    dg = _metric_g_derivs(s["cell"])
    ip = it.phase
    for k in range(n_pts):
        row = row0 + k
        # g[m] = ∂d_k/∂p_m (Cartesian), for every point m
        coef = (np.arange(n_pts) == k) - 1.0 / n_pts - d @ pd[k]
        g = coef[:, None] * normal[None, :] - dist[:, None] * pd[k][None, :]
        for m, (j, R) in enumerate(zip(it.atoms, it.R, strict=True)):
            _scatter_xyz(r_phys, row, idx, ip, j, pref * (R.T @ (amat.T @ g[m])))
        cell_row = []
        for gq in dg:
            da = 0.5 * a_inv_t @ gq
            cell_row.append(pref * float(np.sum(g * (s["frac"] @ da.T))))
        _scatter_cell(r_phys, row, idx, ip, cell_row)


def _scatter_xyz(r_phys, row, idx, ip, j, vec3) -> None:
    for c, name in enumerate(_XYZ):
        r_phys[row, idx[f"phases.{ip}.atoms.{j}.{name}"]] += vec3[c]


def _scatter_cell(r_phys, row, idx, ip, vals6) -> None:
    for q, name in enumerate(_CELL_NAMES):
        r_phys[row, idx[f"phases.{ip}.cell.{name}"]] += vals6[q]


def _bond_row_partials(r_phys, row, it, values, idx, pref) -> None:
    ip = it.phase
    cell = _cell_tuple(values, ip)
    g = _metric_g(cell)
    dx = it.R @ _xyz_np(values, ip, it.j) + it.t + it.n - _xyz_np(values, ip, it.i)
    gdx = g @ dx
    d = math.sqrt(float(dx @ gdx))
    if d <= 0.0:  # coincident atoms: leave the row zero (dead but not a crash)
        return
    # a one-sided row (WP-1809) has zero slope on its flat side; at the kink
    # itself the slope is taken as zero, the side the row value is on
    if (it.side == "max" and d <= it.target) or (it.side == "min" and d >= it.target):
        return
    # ∂d/∂x_i = −(GΔx)/d ; ∂d/∂x_j = Rᵀ(GΔx)/d ; ∂d/∂cell_q = ΔxᵀG_q Δx / 2d
    _scatter_xyz(r_phys, row, idx, ip, it.i, pref * (-gdx / d))
    _scatter_xyz(r_phys, row, idx, ip, it.j, pref * (it.R.T @ gdx / d))
    _scatter_cell(r_phys, row, idx, ip,
                  [pref * float(dx @ (gq @ dx)) / (2.0 * d)
                   for gq in _metric_g_derivs(cell)])


def _angle_row_partials(r_phys, row, it, values, idx, pref) -> None:
    theta, s = _angle_geometry_np(it, values)
    su, sv, p, root, cos = s["su"], s["sv"], s["p"], s["root"], s["cos"]
    if root <= 0.0:
        return
    sin_t = math.sqrt(max(1.0 - cos * cos, 0.0))
    if sin_t <= 0.0:  # clamped to 0°/180° — ill-conditioned, leave zero
        return
    # θ (deg) = (180/π)·arccos(cos) ⇒ ∂θ/∂cos = −(180/π)/sinθ
    fac = -(180.0 / math.pi) / sin_t
    gu, gv, u, v = s["gu"], s["gv"], s["u"], s["v"]
    # ∂cosθ/∂u = (Gv − (p/su)Gu)/root ;  ∂cosθ/∂v = (Gu − (p/sv)Gv)/root
    dth_du = fac * (gv - (p / su) * gu) / root
    dth_dv = fac * (gu - (p / sv) * gv) / root
    ip = it.phase
    _scatter_xyz(r_phys, row, idx, ip, it.i, pref * (it.Ri.T @ dth_du))
    _scatter_xyz(r_phys, row, idx, ip, it.k, pref * (it.Rk.T @ dth_dv))
    _scatter_xyz(r_phys, row, idx, ip, it.j, pref * (-(dth_du + dth_dv)))
    cell_row = []
    for gq in _metric_g_derivs(s["cell"]):
        dp = float(u @ (gq @ v))
        dsu = float(u @ (gq @ u))
        dsv = float(v @ (gq @ v))
        dcos = (dp - (p / (2.0 * su * sv)) * (sv * dsu + su * dsv)) / root
        cell_row.append(pref * fac * dcos)
    _scatter_cell(r_phys, row, idx, ip, cell_row)


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------
def summarise_restraints(compiled: CompiledRestraints | None, values: dict,
                         weight_scale: float = 1.0):
    """A :class:`RestraintReport` of computed-vs-target deviations, or None.

    Deviations in units of σ are the headline — an over-tight restraint
    fighting the data shows up as a large ``deviation_over_sigma`` here and,
    past a threshold, a ``RESTRAINT_TENSION`` diagnostic (never hide a bad
    sub-fit).  ``restraint_chi2`` = Σ weight·(dev/σ)² is S_G at unit c_w.

    ``weight_scale`` is the stage's c_w (McCusker eq 7), recorded rather than
    applied: it is what turns the reported S_G into the penalty the fit
    actually minimised, and without it a reader of a result — which carries no
    plan — cannot tell a satisfied restraint from a barely-weighted one.
    """
    if compiled is None:
        return None
    from ..schemas.results import RestraintReport, RestraintRow

    rows = []
    chi2 = 0.0
    for it in compiled.items:
        if isinstance(it, _Plane):
            dist, _ = _plane_geometry_np(it, values)
            for k, dk in enumerate(dist):
                dev_sig = float(dk) / it.sigma
                chi2 += it.weight * dev_sig * dev_sig
                rows.append(RestraintRow(
                    phase_index=it.phase, kind="planarity",
                    atoms=[it.atoms[k]] + it.atoms[:k] + it.atoms[k + 1:],
                    computed=float(dk), target=0.0, sigma=it.sigma,
                    weight=it.weight, deviation=float(dk),
                    deviation_over_sigma=dev_sig))
            continue
        if isinstance(it, _Bond):
            computed, target = _bond_value_np(it, values), it.target
            kind = {"max": "tether", "min": "anti_bump"}.get(it.side, "bond")
            atoms, path, ph = [it.i, it.j], None, it.phase
        elif isinstance(it, _Angle):
            computed, target = _angle_value_np(it, values), it.target_deg
            kind, atoms, path, ph = "angle", [it.i, it.j, it.k], None, it.phase
        else:  # _Value
            computed, target = float(values[it.path]), it.target
            kind, atoms, path, ph = "value", None, it.path, it.phase
        dev = computed - target
        if getattr(it, "side", None) == "max":
            dev = max(dev, 0.0)
        elif getattr(it, "side", None) == "min":
            dev = min(dev, 0.0)
        dev_sig = dev / it.sigma
        chi2 += it.weight * dev_sig * dev_sig
        rows.append(RestraintRow(
            phase_index=ph, kind=kind, atoms=atoms, path=path,
            computed=computed, target=target, sigma=it.sigma, weight=it.weight,
            deviation=dev, deviation_over_sigma=dev_sig))
    return RestraintReport(rows=rows, restraint_chi2=chi2, n_restraints=len(rows),
                           weight_scale=float(weight_scale))


# ----------------------------------------------------------------------
# building an anti-bump pair list (WP-1809)
# ----------------------------------------------------------------------
def anti_bump_restraints(phase, min_distance, *, sigma: float = 0.05,
                         weight: float = 1.0, margin: float = 0.5,
                         atoms=None, exclude_same_body: bool = True) -> list:
    """Every atom pair (with its symmetry image) that could bump, as rows.

    The candidate list, built **once** from the phase's present coordinates
    by the caller, who appends the rows to ``Phase.restraints``; explicit rows
    are kept for every stage, so the restraint row count never moves between
    stages.  (WP-1803's record has the engine freeze the list at plan compile;
    this builder is the caller-side form of the same freeze.)  A pair enters
    when its image distance is under its minimum plus ``margin`` (Å); a pair
    that later comes closer from outside the list is not seen by the
    list, which is what the margin is for; :func:`stale_anti_bump_pairs` names
    it at the end of a fit.

    ``min_distance`` is a number (every pair), a mapping from an unordered
    species pair ``(a, b)`` to Å, or a callable ``(species_i, species_j) ->
    Å | None``; a pair with no minimum gets no row (never a default nobody
    stated — #677's rule).  ``atoms`` restricts the first atom of each pair
    to those indices; every atom is then a second atom, so a pair of two
    listed atoms comes back once per order.  Two atoms of one rigid body are skipped by default **in
    the same copy of the body** (identity operation, no lattice shift): their
    distance is the template's, and a row would only fight the body; every
    other image is a neighbouring molecule and keeps its row.

    Images: every operation of the second atom's orbit, times a lattice shell
    centred on the image's nearest lattice vector to the first atom and
    ⌈(r₀ + margin)·|a*ₖ|⌉ + 1 cells wide along each axis, so the list does not
    depend on which cell a coordinate is stored in.  A coincident image (an
    atom with itself, or on a special position with its own image) gets no
    row.  Rows
    come back as :class:`~rietx.schemas.structure.AntiBumpRestraint` with
    ``op_index``/``translation`` set, so the compiled image is the one
    measured here.
    """
    from ..crystallography.structure_factor import compile_phase_sites
    from ..schemas.structure import AntiBumpRestraint

    if callable(min_distance):
        rule = min_distance
    elif isinstance(min_distance, (int, float)):
        def rule(a, b, _r=float(min_distance)):
            return _r
    else:
        table = {tuple(sorted(k)): float(v) for k, v in min_distance.items()}

        def rule(a, b):
            return table.get(tuple(sorted((a, b))))
    sites = compile_phase_sites(phase)
    g = _metric_g(phase.cell.lengths_angles())
    body_of = {label: b.name for b in getattr(phase, "rigid_bodies", [])
               for label in b.atoms}
    first = range(len(phase.atoms)) if atoms is None else atoms
    astar = np.sqrt(np.diag(np.linalg.inv(g)))      # reciprocal axis lengths, 1/Å
    rows = []
    for i in first:
        ai = phase.atoms[i]
        x_i = _atom_xyz(phase, i)
        for j, aj in enumerate(phase.atoms):
            if atoms is None and j < i:
                continue
            same_body = (exclude_same_body and ai.label in body_of
                         and body_of.get(aj.label) == body_of[ai.label])
            r0 = rule(ai.species, aj.species)
            if r0 is None:
                continue
            ops_r, ops_t = sites.ops[j]
            x_j = _atom_xyz(phase, j)
            for mi in range(len(ops_r)):
                rot, tr = np.asarray(ops_r[mi]), np.asarray(ops_t[mi])
                img = rot @ x_j + tr
                identity = (np.array_equal(rot, np.eye(3))
                            and np.allclose(tr - np.round(tr), 0.0))
                # the shell is centred on the image's nearest lattice vector, so
                # the list does not depend on which cell a coordinate is stored
                # in (a body placed about any origin, a free atom anywhere)
                centre = np.round(x_i - img)
                # and wide enough for the cut: |Δx_k| ≤ (r0 + margin)·|a*_k|
                reach = [range(-m, m + 1) for m in
                         np.ceil((r0 + margin) * astar).astype(int) + 1]
                # every shift at once, in the order a, b, c nested loops give
                shifts = centre + np.stack(np.meshgrid(*reach, indexing="ij"),
                                           axis=-1).reshape(-1, 3)
                dx = img + shifts - x_i
                d2 = np.einsum("ki,ij,kj->k", dx, g, dx)
                hit = (d2 >= _COINCIDENT_D2) & (np.sqrt(d2) < r0 + margin)
                for n in shifts[hit]:
                    if (same_body and identity
                            and np.array_equal(n, -np.round(tr))):
                        # the body's own copy: its geometry is the
                        # template's; every other image is another
                        # molecule and is kept
                        continue
                    rows.append(AntiBumpRestraint(
                        atom_i=i, atom_j=j, min_distance=r0,
                        sigma=sigma, weight=weight, op_index=mi,
                        translation=tuple(int(v) for v in n)))
    return rows


#: two contacts of one atom pair are one contact when their distances agree to
#: this (Å): a symmetry copy of a listed contact is restrained by its row
_SAME_CONTACT_A = 1e-6


def _inside_contacts(phase, listed):
    """Every contact inside its r₀ at the phase's coordinates, listed or not.

    r₀ is read off the rows: per unordered species pair, the largest
    ``min_distance`` any row of that pair states; a species pair with no row
    is not searched (#677's rule: no minimum nobody gave).  Returns
    ``(key, distance, r0)`` with ``key = (atom_i, atom_j, op_index,
    translation)`` naming the contact itself, in the builder's own order.
    """
    from ..crystallography.structure_factor import compile_phase_sites

    sp = [a.species for a in phase.atoms]
    rule: dict[tuple[str, str], float] = {}
    for r in listed:
        key = tuple(sorted((sp[r.atom_i], sp[r.atom_j])))
        rule[key] = max(rule.get(key, 0.0), r.min_distance)
    sites = compile_phase_sites(phase)
    g = _metric_g(phase.cell.lengths_angles())
    out = []
    for c in anti_bump_restraints(phase, rule, margin=0.0):
        x_i = _atom_xyz(phase, c.atom_i)
        R, t = sites.ops[c.atom_j][0][c.op_index], sites.ops[c.atom_j][1][c.op_index]
        dx = (np.asarray(R) @ _atom_xyz(phase, c.atom_j) + np.asarray(t)
              + np.asarray(c.translation, dtype=np.float64) - x_i)
        d = math.sqrt(float(dx @ (g @ dx)))
        out.append(((c.atom_i, c.atom_j, c.op_index, tuple(c.translation)),
                    d, c.min_distance))
    return out


def anti_bump_contact_keys(phase) -> frozenset:
    """The contacts inside their r₀ right now, as keys for ``since=`` (WP-1809).

    Take it at the coordinates a fit *starts* from and hand it to
    :func:`stale_anti_bump_pairs` at the answer, which then reports only a
    contact that was not inside r₀ then.  Empty when the phase has no
    anti-bump row.
    """
    listed = [r for r in phase.restraints if isinstance(r, AntiBumpRestraint)]
    if not listed:
        return frozenset()
    return frozenset(k for k, _, _ in _inside_contacts(phase, listed))


def stale_anti_bump_pairs(phase, *, since=None) -> list[tuple[int, int, float, float]]:
    """Contacts inside their minimum that no anti-bump row restrains (WP-1809).

    The caller builds the pair list once (:func:`anti_bump_restraints`), so a
    pair that drifts inside r₀ from outside it gets no row.  This searches the
    phase at its present coordinates with the builder itself (no margin) and
    returns ``(atom_i, atom_j, distance, r0)`` for every contact closer than
    its r₀ that matches no row, sorted by how far inside r₀ it sits.

    **``since`` is what makes "entered from outside" true.**  The list does
    not remember the coordinates it was built from, so a pair the caller left
    out on purpose (a bonded C–C under a 3.3 Å rule) is indistinguishable
    from a drifted one by the answer alone.  ``since`` is
    :func:`anti_bump_contact_keys` taken at the coordinates the run started
    from: a contact inside r₀ there is the caller's own state and is never
    named.  Without it, every unlisted contact under r₀ is returned.

    r₀ is the strictest ``min_distance`` any row states for the contact's
    species pair, so a contact is held to a minimum a row of its *species*
    stated, not necessarily one for its atoms.  A contact is matched to a row
    of the same two atoms whose image sits at the same distance (to
    ``_SAME_CONTACT_A``), so a symmetry copy of a listed contact is not
    named.  A body's own pairs in its own copy are skipped, as the builder
    skips them.  Empty when the phase has no anti-bump row.
    """
    from ..crystallography.structure_factor import compile_phase_sites

    listed = [r for r in phase.restraints if isinstance(r, AntiBumpRestraint)]
    if not listed:
        return []
    sites = compile_phase_sites(phase)
    g = _metric_g(phase.cell.lengths_angles())
    known: dict[tuple[int, int], list[float]] = {}
    for r in listed:
        x_i = _atom_xyz(phase, r.atom_i)
        rot, tr, n = _resolve_image(sites, r.atom_j, x_i, _atom_xyz(phase, r.atom_j),
                                    r.op_index, r.translation, g)
        dx = rot @ _atom_xyz(phase, r.atom_j) + tr + n - x_i
        key = (min(r.atom_i, r.atom_j), max(r.atom_i, r.atom_j))
        known.setdefault(key, []).append(math.sqrt(float(dx @ (g @ dx))))
    out = []
    seen: set[tuple[int, int, float]] = set()
    for ck, d, r0 in _inside_contacts(phase, listed):
        if since is not None and ck in since:
            continue
        key = (min(ck[0], ck[1]), max(ck[0], ck[1]))
        if any(abs(d - k) <= _SAME_CONTACT_A for k in known.get(key, ())):
            continue
        tag = (*key, round(d, 6))
        if tag in seen:
            continue
        seen.add(tag)
        out.append((key[0], key[1], d, r0))
    return sorted(out, key=lambda p: p[2] - p[3])
