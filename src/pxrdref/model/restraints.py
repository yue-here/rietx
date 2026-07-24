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
from ..schemas.structure import AngleRestraint, BondRestraint

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
class CompiledRestraints:
    """The frozen restraint rows of a compiled model, in schema order."""

    items: list

    @property
    def n_rows(self) -> int:
        return len(self.items)


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
        if isinstance(r, BondRestraint):
            x_i = _atom_xyz(phase, r.atom_i)
            x_j = _atom_xyz(phase, r.atom_j)
            rot, tr, n = _resolve_image(sites, r.atom_j, x_i, x_j,
                                        r.op_index, r.translation, g)
            out.append(_Bond(ip, r.atom_i, r.atom_j, rot, tr, n,
                             r.target, r.sigma, r.weight))
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
        else:  # ValueRestraint
            out.append(_Value(r.path, r.target, r.sigma, r.weight, ip))
    return out


def _atom_xyz(phase, j: int) -> np.ndarray:
    a = phase.atoms[j]
    return np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64)


def _resolve_image(sites, j, reference, base_xyz, op_index, translation, g):
    """Freeze (R, t, n) for the image of atom ``j`` relative to ``reference``.

    With ``op_index`` given, that orbit op and the explicit ``translation`` are
    used verbatim.  Otherwise the minimum-image search enumerates the atom's
    frozen orbit ops × the ``{−1,0,1}³`` lattice shell and keeps the closest
    (non-coincident) image, measured with the compile-time metric ``g``.
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
        for na in shell:
            for nb in shell:
                for nc in shell:
                    n = np.array([na, nb, nc], dtype=np.float64)
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
    """√w·(computed − target)/σ rows, one per compiled restraint (traceable)."""
    xp = get_backend()
    rows = []
    for it in compiled.items:
        if isinstance(it, _Bond):
            computed, target = _bond_distance(it, values), it.target
        elif isinstance(it, _Angle):
            computed, target = _angle_deg(it, values), it.target_deg
        else:  # _Value
            computed, target = values[it.path], it.target
        rows.append((computed - target) * (math.sqrt(it.weight) / it.sigma))
    return xp.stack(rows)


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
    r_phys = np.zeros((len(compiled.items), len(table.entries)), dtype=np.float64)
    for row, it in enumerate(compiled.items):
        pref = math.sqrt(it.weight) / it.sigma
        if isinstance(it, _Bond):
            _bond_row_partials(r_phys, row, it, values, idx, pref)
        elif isinstance(it, _Angle):
            _angle_row_partials(r_phys, row, it, values, idx, pref)
        else:  # _Value: ∂row/∂path = √w/σ
            r_phys[row, idx[it.path]] += pref
    return r_phys


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
def summarise_restraints(compiled: CompiledRestraints | None, values: dict):
    """A :class:`RestraintReport` of computed-vs-target deviations, or None.

    Deviations in units of σ are the headline — an over-tight restraint
    fighting the data shows up as a large ``deviation_over_sigma`` here and,
    past a threshold, a ``RESTRAINT_TENSION`` diagnostic (never hide a bad
    sub-fit).  ``restraint_chi2`` = Σ weight·(dev/σ)² is the pooled penalty.
    """
    if compiled is None:
        return None
    from ..schemas.results import RestraintReport, RestraintRow

    rows = []
    chi2 = 0.0
    for it in compiled.items:
        if isinstance(it, _Bond):
            computed, target = _bond_value_np(it, values), it.target
            kind, atoms, path, ph = "bond", [it.i, it.j], None, it.phase
        elif isinstance(it, _Angle):
            computed, target = _angle_value_np(it, values), it.target_deg
            kind, atoms, path, ph = "angle", [it.i, it.j, it.k], None, it.phase
        else:  # _Value
            computed, target = float(values[it.path]), it.target
            kind, atoms, path, ph = "value", None, it.path, it.phase
        dev = computed - target
        dev_sig = dev / it.sigma
        chi2 += it.weight * dev_sig * dev_sig
        rows.append(RestraintRow(
            phase_index=ph, kind=kind, atoms=atoms, path=path,
            computed=computed, target=target, sigma=it.sigma, weight=it.weight,
            deviation=dev, deviation_over_sigma=dev_sig))
    return RestraintReport(rows=rows, restraint_chi2=chi2, n_restraints=len(rows))
