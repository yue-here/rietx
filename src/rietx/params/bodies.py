"""The rigid-body derived block (WP-1805): a body's atoms from its pose.

One :class:`~rietx.params.derived.DerivedBlock` per ``RigidBody``.  Inputs, in
this order: the phase's six cell entries (live, WP-1803's record), the body's
origin x, y, z (fractional; themselves anchored rows on the origin's site
basis), the k rotation DOFs θ (rad), and one twist increment δφ_t (degrees)
per named-bond torsion (WP-1808).  Outputs: x, y, z of every member atom, in
template order.  The map is

    x_i = o + M⁻¹(cell) · Exp(E·θ) · R₀ · T_i(φ₀ + δφ),

with T(φ) the template after its torsions (:func:`apply_torsions`).

with δω = E·θ the rotation increment in the Cartesian frame.  **k is the
template's inertia rank** (``fragments.Fragment.body_frame``): three, with
E = I, for any body that is not linear; two for a linear one, with E's columns
the two lab directions perpendicular to its axis R₀·u, since a rotation about
the axis moves nothing and a third DOF would be a flat direction that blinds
every atom's esd.

Its Jacobian is closed-form, block by block (the design report's § 2.2):

* ∂x_i/∂o = I;
* ∂x_i/∂θ_j = Σ_k M⁻¹ · ∂R/∂δω_k · T_i · E_kj, with ∂R/∂δω_k from
  ``rotation.d_matrix_d_vector`` (Solà et al. 2018, eqs. 72, 145);
* ∂x_i/∂cell_q = −M⁻¹ · ∂M/∂cell_q · (x_i − o), from
  ``derived.d_cartesian_frame_d_cell``;
* ∂x_i/∂δφ_t = M⁻¹ · Exp(E·θ) · R₀ · ∂T_i/∂φ_t, the body-frame tangent
  propagated forward through the torsions in order
  (:meth:`RigidBodyBlock.body_tangents`).

**The increment composes at commit** (:meth:`RigidBodyBlock.commit_rotation`,
the record in ``docs/DESIGN.md``): R₀ ← Exp(δω)·R₀ and θ ← 0, so every stage
starts at the identity of the exponential map, where its Jacobian is never
singular (Triggs, McLauchlan, Hartley & Fitzgibbon 2000, *Bundle adjustment —
a modern synthesis*, LNCS 1883, § 2.2).  The same call returns the k × k
matrix ∂θ_old/∂θ_new that carries a solver outcome into the composed chart.
**A torsion is an anchored rotation too** (WP-1808), composed by the same
commit (:meth:`RigidBodyBlock.commit_torsions`): φ₀ ← φ₀ + δφ, δφ ← 0.  About
one axis composing is addition, so its chart moves by a translation and
∂θ_old/∂θ_new is the identity on its columns; nothing about it needs
re-charting but the value.

TOPAS states the same chain for a body's esds (Coelho, *TOPAS-Academic V6
Technical Reference*, § 10.22.8): every body atom's coordinate is a function of
the body's parameters and its esd comes through them.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend
from ..crystallography import rotation
from ..crystallography.fragments import Fragment
from .derived import DerivedBlock, d_cartesian_frame_d_cell, fractional_frame

CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")
_DEG = np.pi / 180.0
#: a moved atom nearer its torsion's axis line than this (Å) does not move
TORSION_STILL_TOL = 1e-6


def wrap_degrees(angle: float) -> float:
    """``angle`` (degrees) taken into (−180, 180], the ``_geom_torsion`` range.

    An angle already inside is returned bit for bit: the arithmetic of the
    wrap rounds (180 − (180 − 0.1) is 0.09999999999999432), and a record that
    moved at every commit would drift with nothing turning it.
    """
    angle = float(angle)
    if -180.0 < angle <= 180.0:
        return angle
    return 180.0 - (180.0 - angle) % 360.0


def _rodrigues(d, u, c, s):
    """R·d for the right-handed rotation by (cos, sin) = (c, s) about unit u.

    Rodrigues (1840, *J. Math. Pures Appl.* 5, 380):
    R·d = d cos φ + (u × d) sin φ + u (u·d)(1 − cos φ).
    ``d`` is one point (3,) or a stack (m, 3).
    """
    cross = np.cross(u, d)
    if d.ndim == 2:
        return d * c + cross * s + np.outer(d @ u, u) * (1.0 - c)
    return d * c + cross * s + u * (d @ u) * (1.0 - c)


def apply_torsions(points: np.ndarray, torsions, angles_deg) -> np.ndarray:
    """The body-frame points after each named-bond torsion, in order (WP-1808).

    ``torsions`` is a sequence of ``(axis_a, axis_b, moves)`` index triples
    into ``points``; torsion t turns ``moves`` by ``angles_deg[t]`` about the
    line from point ``axis_a`` to point ``axis_b`` (TOPAS's
    ``Rotate_about_points``, Coelho 2018, *J. Appl. Cryst.* 51, 210;
    *TOPAS-Academic V6 Technical Reference*, § 10.22.4), with the axis read
    off the points **as earlier torsions left them**.
    """
    pts = np.array(points, dtype=np.float64)
    for (ia, ib, moves), ang in zip(torsions, angles_deg, strict=True):
        a = pts[ia]
        v = pts[ib] - a
        u = v / np.linalg.norm(v)
        phi = float(ang) * _DEG
        pts[moves] = a + _rodrigues(pts[moves] - a, u, np.cos(phi), np.sin(phi))
    return pts


def compose_rotation(omega: np.ndarray, r0: np.ndarray) -> np.ndarray:
    """Exp(ω)·R₀, the re-exponentiation a commit performs (numpy).

    A module function so that a test can replace it with what skipping the
    re-exponentiation would do — (I + [ω]×)·R₀, or R₀ unchanged — and see the
    commit-time guard refuse the result.
    """
    return np.asarray(rotation.matrix_from_vector(np.asarray(omega, dtype=np.float64)),
                      dtype=np.float64) @ r0


def rotation_axes(template: np.ndarray) -> np.ndarray:
    """The template-frame rotation axes that move the body, (3, k) columns.

    The rows of ``Fragment.body_frame().rotation_axes`` (WP-1802): the
    identity for any body that is not linear (k = 3), the plane perpendicular
    to the axis for a linear one (k = 2).  A template whose points coincide has
    no rotation at all and is refused, naming why.
    """
    pts = np.asarray(template, dtype=np.float64)
    axes = Fragment(species=("X",) * len(pts), xyz=pts).body_frame().rotation_axes
    if axes.shape[0] < 2:
        raise ValueError(
            "a rigid body whose template points coincide has no orientation "
            "to refine; give its atoms distinct template positions")
    return np.array(axes.T, dtype=np.float64)


class RigidBodyBlock(DerivedBlock):
    """x_i = o + M⁻¹·Exp(δω)·R₀·T_i for one body; see the module docstring."""

    #: inputs before the body's own: the six cell entries
    N_CELL = 6

    def __init__(self, *, phase_base: str, body_base: str, atom_bases: list[str],
                 template: np.ndarray, q0, torsions=(), angles=(), names=()):
        self.template = np.asarray(template, dtype=np.float64)
        #: the template-frame axes the rotation DOFs turn about, (3, k)
        self.body_axes = rotation_axes(self.template)
        self._set_anchor(np.asarray(q0, dtype=np.float64))
        #: (axis_a, axis_b, moves) index triples into the template (WP-1808)
        self.torsions = [(int(a), int(b), np.asarray(m, dtype=np.intp))
                         for a, b, m in torsions]
        #: φ₀, each torsion's anchor (degrees): its record, composed at commit
        self.phi0 = np.array(angles, dtype=np.float64).reshape(len(self.torsions))
        #: each torsion's declared name, for the refusals that name it
        self.names = [str(n) for n in names] or [str(t) for t in range(len(self.torsions))]
        self._refuse_still_torsions()
        self.inputs = (
            *(f"{phase_base}.cell.{n}" for n in CELL_NAMES),
            *(f"{body_base}.origin.{c}" for c in "xyz"),
            *self.rotation_paths(body_base),
            *self.twist_paths(body_base),
        )
        self.outputs = tuple(f"{a}.{c}" for a in atom_bases for c in "xyz")

    def _refuse_still_torsions(self) -> None:
        """A torsion whose moved atoms all lie on its axis line moves nothing.

        Read at the anchor, with the earlier torsions applied, since that is
        the geometry the torsion turns.  Its column would be identically zero:
        a parameter the data can never see, refused rather than reported.  An
        axis shorter than ``TORSION_STILL_TOL`` is refused too, before it is
        divided by: two coincident template points, or an earlier torsion that
        carried one axis atom onto the other, would otherwise put NaN on every
        atom of the body with no error.
        """
        pts = np.array(self.template, dtype=np.float64)
        for t, (ia, ib, moves) in enumerate(self.torsions):
            a = pts[ia]
            length = float(np.linalg.norm(pts[ib] - a))
            if not length >= TORSION_STILL_TOL:
                raise ValueError(
                    f"torsion {self.names[t]!r} has a zero-length axis: its two "
                    f"axis atoms are {length:.3g} Å apart (read at the anchor, "
                    "with the earlier torsions applied), so the axis direction "
                    "is undefined")
            u = (pts[ib] - a) / length
            d = pts[moves] - a
            off = np.linalg.norm(d - np.outer(d @ u, u), axis=1)
            if off.max() < TORSION_STILL_TOL:
                raise ValueError(
                    f"torsion {self.names[t]!r} moves nothing: every atom it moves lies on its "
                    "axis line, so its twist has no effect on the structure")
            phi = self.phi0[t] * _DEG
            pts[moves] = a + _rodrigues(d, u, np.cos(phi), np.sin(phi))

    def twist_paths(self, body_base: str) -> tuple[str, ...]:
        return tuple(f"{body_base}.torsions.{t}.twist" for t in range(len(self.torsions)))

    @property
    def n_rot(self) -> int:
        """The number of rotation DOFs: the template's inertia rank, 2 or 3."""
        return int(self.body_axes.shape[1])

    def rotation_paths(self, body_base: str) -> tuple[str, ...]:
        return tuple(f"{body_base}.rotation.{k}" for k in range(self.n_rot))

    def _set_anchor(self, q0: np.ndarray, r0: np.ndarray | None = None) -> None:
        """R₀ from its record, and the lab-frame increment basis E it implies.

        ``q0`` is the canonical unit quaternion the model stores; ``r0`` the
        matrix when it is already in hand.  E = I for k = 3, so the increment's
        components are the Cartesian frame's; for a linear body E = R₀·A, the
        template-frame perpendicular axes A carried into the lab, so E moves
        with every composition and stays perpendicular to the axis.
        """
        self.q0 = q0
        self.r0 = (np.asarray(rotation.matrix_from_quaternion(q0), dtype=np.float64)
                   if r0 is None else r0)
        self.axes = np.eye(3) if self.n_rot == 3 else self.r0 @ self.body_axes

    def omega(self, theta_rot) -> np.ndarray:
        """δω = E·θ (rad, Cartesian) from the k rotation DOFs."""
        return self.axes @ np.asarray(theta_rot, dtype=np.float64)

    # -- the template after its torsions (WP-1808) ------------------------
    def _angles(self, x: np.ndarray) -> np.ndarray:
        """φ₀ + δφ (degrees), the torsions' angles at inputs ``x``."""
        return self.phi0 + np.asarray(x, dtype=np.float64)[9 + self.n_rot:]

    def body_points(self, x: np.ndarray) -> np.ndarray:
        """The template in the body frame, before the pose (n, 3), numpy."""
        if not self.torsions:
            return self.template
        return apply_torsions(self.template, self.torsions, self._angles(x))

    def body_tangents(self, x: np.ndarray) -> np.ndarray:
        """∂(body points)/∂(twist, per degree), (n_torsion, n, 3).

        Forward-mode tangent propagation through the torsions in order: each
        carries every tangent through its own rotation, including the motion of
        its axis when an earlier torsion moved an axis atom.  For torsion j,
        moved point p' = a + R(d), d = p − a, u = (b − a)/|b − a|, and

            dp' = da + R(dd) + (du × d) sin φ + du (u·d)(1 − cos φ)
                  + u (du·d)(1 − cos φ) + δ_jk (−d sin φ + (u × d) cos φ
                  + u (u·d) sin φ)·π/180,
            du = (I − u uᵀ)(db − da)/|b − a|.

        The last term is ∂(Rd)/∂φ = u × (Rd) per radian.  φ = φ₀ + δφ, so the
        tangent is the same per degree of twist as per degree of angle.
        """
        k = len(self.torsions)
        pts = np.array(self.template, dtype=np.float64)
        tan = np.zeros((k, len(pts), 3), dtype=np.float64)
        for j, ((ia, ib, moves), ang) in enumerate(
                zip(self.torsions, self._angles(x), strict=True)):
            a, b = pts[ia].copy(), pts[ib].copy()
            v = b - a
            length = float(np.linalg.norm(v))
            u = v / length
            phi = float(ang) * _DEG
            c, s = np.cos(phi), np.sin(phi)
            d = pts[moves] - a                                   # (m, 3)
            ud = d @ u                                           # (m,)
            for t in range(k):
                da, db = tan[t, ia].copy(), tan[t, ib].copy()
                du = (db - da - u * ((db - da) @ u)) / length
                dd = tan[t, moves] - da
                term = (np.cross(du, d) * s + np.outer(ud, du) * (1.0 - c)
                        + np.outer(d @ du, u) * (1.0 - c))
                new = da + _rodrigues(dd, u, c, s) + term
                if t == j:
                    new = new + (-d * s + np.cross(u, d) * c
                                 + np.outer(ud, u) * s) * _DEG
                tan[t, moves] = new
            pts[moves] = a + _rodrigues(d, u, c, s)
        return tan

    def body_points_traced(self, x):
        xp = get_backend()
        pts = [xp.asarray(t) for t in self.template]
        twists = list(x)[9 + self.n_rot:]
        for (ia, ib, moves), phi0, dphi in zip(self.torsions, self.phi0, twists,
                                               strict=True):
            a = pts[ia]
            v = pts[ib] - a
            u = v / xp.sqrt(xp.sum(v * v))
            phi = xp.radians(dphi + float(phi0))
            c, s = xp.cos(phi), xp.sin(phi)
            for m in moves:
                d = pts[int(m)] - a
                cross = xp.stack([u[1] * d[2] - u[2] * d[1],
                                  u[2] * d[0] - u[0] * d[2],
                                  u[0] * d[1] - u[1] * d[0]])
                pts[int(m)] = a + d * c + cross * s + u * (xp.sum(u * d) * (1.0 - c))
        return pts

    # -- the map ---------------------------------------------------------
    def _pose(self, x: np.ndarray):
        cell = tuple(float(v) for v in x[:6])
        o, w = x[6:9], self.omega(x[9:9 + self.n_rot])
        minv = np.asarray(fractional_frame(cell), dtype=np.float64)
        rot = np.asarray(rotation.matrix_from_vector(np.asarray(w)),
                         dtype=np.float64) @ self.r0
        return cell, o, w, minv, rot

    def evaluate(self, x):
        x = np.asarray(x, dtype=np.float64)
        _, o, _, minv, rot = self._pose(x)
        pts = self.body_points(x)
        return (o + pts @ (minv @ rot).T).ravel()

    def jacobian(self, x):
        x = np.asarray(x, dtype=np.float64)
        cell, o, w, minv, rot = self._pose(x)
        pts = self.body_points(x)
        n = len(pts)
        jac = np.zeros((3 * n, len(self.inputs)), dtype=np.float64)
        rel = pts @ (minv @ rot).T                        # x_i − o, fractional
        dm = d_cartesian_frame_d_cell(cell)
        for q in range(6):
            jac[:, q] = -(rel @ (minv @ dm[q]).T).ravel()
        for c in range(3):
            jac[c::3, 6 + c] = 1.0
        dr = np.asarray(rotation.d_matrix_d_vector(np.asarray(w), self.r0),
                        dtype=np.float64)
        # d_matrix_d_vector includes R₀; the body points are pre-R₀ coordinates
        k = self.n_rot
        dw = np.stack([(pts @ (minv @ dr[c]).T).ravel() for c in range(3)], axis=1)
        jac[:, 9:9 + k] = dw @ self.axes
        tangents = self.body_tangents(x)
        for t in range(len(tangents)):
            jac[:, 9 + k + t] = (tangents[t] @ (minv @ rot).T).ravel()
        return jac

    def evaluate_traced(self, x):
        xp = get_backend()
        cell = tuple(x[:6])
        o = xp.stack(list(x[6:9]))
        w = xp.matmul(xp.asarray(self.axes, dtype=np.float64),
                      xp.stack(list(x[9:9 + self.n_rot])))
        minv = fractional_frame(cell)
        frame = xp.matmul(minv, xp.matmul(rotation.matrix_from_vector(w),
                                          xp.asarray(self.r0)))
        out = []
        for p in self.body_points_traced(x):
            v = o + xp.matmul(frame, p)
            out.extend([v[0], v[1], v[2]])
        return out

    def reach_pattern(self):
        """Pose and cell reach every atom; a torsion reaches what it moves,
        and what any later torsion whose axis it moved moves in turn."""
        pattern = np.zeros((len(self.outputs), len(self.inputs)), dtype=bool)
        k = 9 + self.n_rot
        pattern[:, :k] = True
        dep = np.zeros((len(self.torsions), len(self.template)), dtype=bool)
        for j, (ia, ib, moves) in enumerate(self.torsions):
            dep[j, moves] = True
            for t in range(j):
                if dep[t, ia] or dep[t, ib]:
                    dep[t, moves] = True
        for t in range(len(self.torsions)):
            for i in np.flatnonzero(dep[t]):
                pattern[3 * i:3 * i + 3, k + t] = True
        return pattern

    # -- the record --------------------------------------------------------
    def orientation(self, theta_rot) -> np.ndarray:
        """The pose's quaternion, canonical, at rotation DOFs ``theta_rot``.

        Exactly the record R₀ came from where θ = 0, which is every value a
        commit leaves; elsewhere (a value set by hand and not yet committed)
        the pose Exp(E·θ)·R₀ it describes.
        """
        w = self.omega(theta_rot)
        if not w.any():
            return self.q0
        return np.asarray(rotation.canonical_quaternion(
            rotation.quaternion_from_matrix(compose_rotation(w, self.r0))),
            dtype=np.float64)

    def commit_rotation(self, theta_rot) -> np.ndarray | None:
        """Compose the increment into the anchor: R₀ ← Exp(E·θ)·R₀, θ ← 0.

        Returns ∂θ_old/∂θ_new at the committed pose (k × k), the matrix that
        restates a solver outcome in the new chart, or ``None`` when θ = 0 and
        nothing moved.  Derivation (Solà et al. 2018, eq. 72): the old chart
        reaches R = Exp(ω_old)·R₀ and the new one R = Exp(ω_new)·R*, with
        R* = Exp(ω*)·R₀; near the pose Exp(ω* + δ)·R₀ = Exp(J_l(ω*)·δ)·R*, so
        δω_old = J_l(ω*)⁻¹·δω_new.  For k = 3 that is the answer.  For a linear
        body ω lives on E's plane, and J_l⁻¹·E_new·δθ_new leaves it by a
        component along n = J_l(ω*)⁻¹·R*·u, the old chart's null direction
        (a turn about the axis moves no atom), so the matrix is the E_old part
        of the solve [E_old | n]·[c; d] = J_l⁻¹·E_new.

        The new anchor is left as the raw product, not yet canonicalised, so
        the caller's rigidity guard reads the very rotation the atoms will be
        written from; :meth:`settle_anchor` turns it into the record.
        """
        theta_rot = np.asarray(theta_rot, dtype=np.float64)
        if not theta_rot.any():
            return None
        w = self.omega(theta_rot)
        axes_old = self.axes
        r_new = compose_rotation(w, self.r0)
        jl_inv = np.linalg.inv(np.asarray(rotation.left_jacobian(w), dtype=np.float64))
        self.r0 = r_new
        self.axes = np.eye(3) if self.n_rot == 3 else r_new @ self.body_axes
        if self.n_rot == 3:
            return jl_inv
        axis = r_new @ np.cross(self.body_axes[:, 0], self.body_axes[:, 1])
        basis = np.column_stack([axes_old, jl_inv @ axis])
        return np.linalg.solve(basis, jl_inv @ self.axes)[:2]

    def settle_anchor(self) -> None:
        """Store the committed R₀ as its canonical quaternion record.

        R₀ is re-read from that quaternion, so a table rebuilt from the
        written-back model anchors on the identical matrix.
        """
        q = np.asarray(rotation.canonical_quaternion(
            rotation.quaternion_from_matrix(self.r0)), dtype=np.float64)
        self._set_anchor(q)

    def restore_anchor(self, q0, r0, axes) -> None:
        """Put back an anchor a commit replaced (a collapsed phase's restore)."""
        self.q0, self.r0, self.axes = q0, r0, axes

    def angles(self, twists) -> np.ndarray:
        """The torsions' record (degrees, in (−180, 180]) at increments ``twists``.

        Exactly φ₀ where δφ = 0, which is every value a commit leaves;
        elsewhere (a twist set by hand and not committed) the angle it
        describes.
        """
        return np.array([wrap_degrees(v) for v in self.phi0 + np.asarray(
            twists, dtype=np.float64)], dtype=np.float64).reshape(len(self.torsions))

    def commit_torsions(self, twists) -> bool:
        """Compose each twist into its anchor: φ₀ ← φ₀ + δφ, δφ ← 0 (WP-1808).

        The new anchor is wrapped into (−180, 180], a whole turn away at most,
        which moves no atom beyond rounding.  Returns whether any torsion
        turned.  No chart matrix: about one axis Rot(φ₀ + δφ_old) =
        Rot(φ₀' + δφ_new) with φ₀' = φ₀ + δφ*, so δφ_old = δφ_new + δφ* and
        ∂θ_old/∂θ_new is the identity on the twist columns.
        """
        twists = np.asarray(twists, dtype=np.float64)
        if not twists.any():
            return False
        self.phi0 = self.angles(twists)
        return True

    def restore_torsions(self, phi0) -> None:
        """Put back the torsion anchors a commit replaced."""
        self.phi0 = np.array(phi0, dtype=np.float64)
