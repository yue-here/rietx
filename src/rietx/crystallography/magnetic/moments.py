"""How a moment enters θ: a modulus and the angles the site symmetry leaves free.

A moment is stored as crystal-axis components (``Atom.moment``) and refined
through ``phases.i.atoms.j.moment.dof<k>``.  The DOFs are **not** the components
and not their coefficients on the allowed basis either, and the reason is the
one thing a powder cannot do.

**Why modulus and angles.**  After the Laue-orbit average a powder measures
|m| for a cubic collinear structure and nothing at all about its direction
(Shirane, G., 1959, *Acta Cryst.* **12**, 282); for a uniaxial structure it
measures |m| and the angle to the unique axis, and nothing about the azimuth.
Those are *flat directions of θ*, and the package already has one rule for a
flat direction: an equilibrated normal matrix, a gradient-free column named by
``ParameterTable.unmeasured_rows``, and an esd that is **absent** rather than
zero.  For that rule to fire, the undeterminable quantity has to *be a column*.
Parameterising by components — or by coefficients on the allowed basis — puts
the flat direction along a rotation that no single column owns, so every
component comes back unmeasured and the magnitude, which the data *does*
determine, comes back with no esd at all.  Modulus-and-angles splits them:
the modulus is a column with a gradient and an esd, the angles are columns
without one exactly when the powder cannot see them.

**When the pole is not the unique axis.**  "The azimuth is the flat column"
holds only when :func:`moment_frame`'s polar row lies along the axis the
powder is uniaxial about.  Gram–Schmidt puts it along **c** on tetragonal and
hexagonal axes, but on rhombohedral axes the unique axis is [111] and the
row is not, so the flat rotation is a *combination* of polar and azimuth
that neither column owns: measured on R-3m:R, each angle alone moves the
pattern at order 1 of the modulus, the rotation about [111] at 4.8e-16, and
the two angles came back with esds and ρ = +1.000 (issue #599).  The frame
is not re-oriented for it — it is built from the basis and the cell alone,
in two places that must agree.  Instead ``refine._flat_rotation_axis``
measures the flat axis from the rank of the angle block, the fit turns the
moment about it (a move the data cannot see) into the plane of that axis
and the pole, and there the azimuth *is* the flat rotation, so it is held
like any other flat column and the polar angle sweeps the angle to the axis.

**The frame.**  The allowed subspace is M-5's
:func:`~rietx.crystallography.magnetic.operators.allowed_moment_basis` — an
integer basis of crystal-axis directions, ∩ ker(ε·det(R)·R − I) over the site's
magnetic stabiliser.  It is *not* orthonormal, and the crystal-axis basis is
oblique whenever the cell is, so the frame here is Gram-Schmidt **in the
magCIF unit-vector metric** (ones on the diagonal, cos of the cell angles off
it).  That is what makes the modulus equal |m| in the sense the CIF defines it:
on hexagonal axes the moment (1, 1, 0) is 1 μ_B, not √2.

**The frame is frozen per stage.**  It depends on the cell through that metric,
and the cell refines; recomputing it inside the residual would make the DOF-to-
component map a function of θ.  So it is built once per stage from the cell
the stage starts at — the same freeze the symmetry-operation subsets take —
and the parameter table is its one authority: at each stage start
``ParameterTable.reframe_moments`` rebuilds the frame from the written-back
cell and re-seeds the DOFs so that they state the same crystal-axis
components in it, and the forward model is handed the table's frames rather
than building its own (issue #598).  A monoclinic β that moves during a stage
therefore changes the frame at the next stage start and never the moment; the
result's own compile, at the fitted cell, reads the DOFs in the last stage's
frame, and a table built afterwards from the written-back structure is seated
in that frame before it is evaluated on the result's model.  Before #598 the
table kept the first stage's frame for the whole fit while each compile built
a new one, and a 2° move in β put the written-back modulus 9σ from the
refined one.

**Dimension by dimension.**

===  ===================================  ==========================
n    DOFs                                 what the site allows
===  ===================================  ==========================
0    none                                 no moment at all
1    (μ,)                                 one direction, signed
2    (μ, φ)                               a plane
3    (μ, θ, φ)                            any direction
===  ===================================  ==========================

μ is signed for n = 1 — the sign is the only way to state that two independent
sites order antiparallel along the same axis, and there is no angle to carry it
— and unsigned by construction for n ≥ 2, where the antipode is an angle away.
Nothing bounds it either way; ``abs(μ)`` is the magnitude, and the floor that
decides whether the block is supported is on ``abs(μ)``
(:data:`~rietx.schemas.structure.MOMENT_FLOOR_MU_B`).

References
----------
* Shirane, G. (1959). *Acta Cryst.* **12**, 282 — what a powder average
  determines of a moment direction.
* COMCIFS ``magnetic_dic``, ``_atom_site_moment.crystalaxis_*`` — the unit-
  vector basis the metric below belongs to.
"""

from __future__ import annotations

import re

import numpy as np

from ..lattice import direct_metric_tensor

#: ``phases.i.atoms.j.moment.dof<k>``, the moment block's own DOF paths
#: (``ParameterTable._collect_atom_moment`` names them).  ``dof0`` is the
#: modulus and every higher one an angle.  It lives here because two layers
#: read it: the runners that hold a flat direction (``refine``) and the
#: solver's stationary-angle test (``optimize.least_squares``), which may not
#: import ``refine``.
MOMENT_DOF_PATH = re.compile(r"^phases\.\d+\.atoms\.\d+\.moment\.dof\d+$")

#: A moment direction whose calculated-pattern response is this far below the
#: modulus's measures nothing (WP-1327).  Two tests read it, and they ask two
#: different questions.
#:
#: **The hold** (``refine._flat_moment_scan``) asks whether a direction is
#: flat everywhere.  It turns the moment by ``refine.MOMENT_PROBE_ANGLE_RAD``
#: each way and holds an angle only when neither turn moves the pattern by
#: more than this fraction of what the same tip displacement of the modulus
#: does.  A held angle leaves the stage.
#:
#: **The stationary-angle test** (``optimize.least_squares``, WP-1929) asks
#: whether the first derivative vanishes where the fit stopped.  At a direction
#: the symmetry fixes, the pattern is even in the angle.  The angle's column is
#: zero there while its curvature is not.  The test moves the free angles, with
#: everything else fixed, until every angle column is below this fraction of
#: its sites' largest modulus column, and then decides by Δχ² whether the fit
#: stopped at that direction.  An angle that passes stays free and keeps its value.
#: Only its column leaves the covariance.
#:
#: **Measured, not chosen.**  On the cubic collinear test structure the
#: orbit-averaged intensity is provably independent of the moment direction.
#: There the two angle DOFs respond at ~1e-15 of the modulus's response to the
#: finite rotation, which is roundoff.  On Cr₂WO₆ at 4 K under BNS 58.395 the
#: in-plane angle *is* determined, and the same probe reads ~1e0.  The floor
#: sits in the middle of the fifteen orders between the two.  The joint Newton
#: step of the stationary test reaches 1.3e-12 or less at every stop of the
#: two-site Pnma set, six orders inside it.
#:
#: Both tests exist because the package's other "measured nothing" mechanism
#: (:meth:`ParameterTable.unmeasured_free`, through
#: ``optimize.statistics.normal_covariance``) fires only on a column with **no
#: gradient at all** (``d > 0.0``), and an analytically flat direction is not
#: bitwise flat.  Widening that test to a relative one would change the esd of
#: every fit in the package.  The stationary test is that widening restricted
#: to the one parameterisation whose columns vanish by symmetry at a point the
#: data determine.  It acts only on a fit with a free moment angle, and there
#: it moves every esd correlated with that angle.  The hold changes only which
#: angles a stage frees.
MOMENT_DIRECTION_SUPPORT = 1e-6

#: Parameter names of the moment DOFs, by subspace dimension.  Data rather
#: than a formula because the *report* reads it: "the angle a powder cannot
#: determine" has to have a name a person recognises.
DOF_NAMES: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("modulus",),
    2: ("modulus", "azimuth"),
    3: ("modulus", "polar", "azimuth"),
}

#: Units of those DOFs, in the same order.
DOF_UNITS: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("mu_B",),
    2: ("mu_B", "rad"),
    3: ("mu_B", "rad", "rad"),
}


def unit_metric(cell) -> np.ndarray:
    """G of the magCIF ``crystalaxis`` basis: ones on the diagonal, cosines off.

    The direct metric tensor with each row and column divided by its axis
    length, which is what "a right-handed basis of unit vectors parallel to the
    unit-cell basis vectors" means as a metric.  |m|² = mᵀ·G·m.
    """
    a, b, c = float(cell[0]), float(cell[1]), float(cell[2])
    return direct_metric_tensor(*cell) / np.outer([a, b, c], [a, b, c])


def moment_frame(basis, cell) -> np.ndarray:
    """Orthonormal frame of the allowed subspace, ``(n, 3)`` crystal-axis rows.

    Gram-Schmidt on ``basis``'s rows in the unit-vector metric, so
    ``E @ G @ E.T`` is the identity and a vector's coefficients on the frame
    are ``E @ G @ m``.  Deterministic, because the input basis is M-5's
    deterministic smallest-integer one and the orthogonalisation walks it in
    order — two runs of the same stage give the same frame, which is what lets
    a DOF value be compared between them.

    Raises when a row is linearly dependent on its predecessors, which cannot
    happen for a basis and is therefore a corrupted one rather than a case to
    handle.
    """
    b = np.asarray(basis, dtype=np.float64).reshape(-1, 3)
    g = unit_metric(cell)
    rows: list[np.ndarray] = []
    for raw in b:
        v = raw.copy()
        for e in rows:
            v = v - float(e @ g @ raw) * e
        norm = float(np.sqrt(max(v @ g @ v, 0.0)))
        if norm <= 1e-9:
            raise ValueError(
                f"the allowed-moment basis {b.tolist()} is not a basis: row "
                f"{raw.tolist()} is a combination of the rows before it")
        rows.append(v / norm)
    return np.asarray(rows, dtype=np.float64).reshape(len(b), 3)


#: Fraction of the modulus placed on every :func:`moment_frame` row *beyond
#: the first* by :func:`tilted_seed`.  Breaks a stationary point WP-1418
#: stage (b) found on any candidate whose atom-level allowed-moment basis has
#: rank ≥ 2 (a multi-copy irrep merged across sites, or a genuinely
#: general/kernel order-parameter direction, both real and both enumerated by
#: :func:`~rietx.crystallography.magnetic.isotropy.candidates`): seeding
#: purely along row 0 starts every other DOF at exactly the point of pointing
#: along it, and for several of these groups that point is a fixed point of a
#: residual point-group element the candidate's own magnetic group still
#: carries (one negating the other frame rows while fixing the first) — the
#: identical shape ``displacive_statement``'s seed
#: (``representation.distortion.DISTORTION_SEED``) exists for on a whole-vector
#: A = 0 (|F|² even in the amplitude vector, WP-1419), here on one DOF rather
#: than the whole vector, and with the same fix: move it off the stationary
#: point before the stage that frees it.  Small and nonzero, never tuned
#: toward an answer.
#:
#: **Measured, not guessed** (WP-1418 stage (e), 2026-09-18): a 20-entry
#: exact-recovery control set was re-run once with this at 0.15 and once at
#: 0.02, everything else held fixed (same tree, same simulated noise). At
#: 0.15, two entries (bns 185.200, bns 4.12; MAGNDATA #0.655, #1.227)
#: regressed from an exact recovery to, respectively, a different class and a
#: total abstention — the same optimiser that a rank-1 flat seed reliably
#: converges reached a worse local minimum once nudged off it. At 0.02
#: (still strictly nonzero, so the stationary point is broken exactly the
#: same way in every unit test of :func:`tilted_seed` itself) both entries
#: recover exactly, identically to the untouched pre-fix code. 0.15 was the
#: number this stage started with by analogy to the fork's ``distortion_seed``
#: docstring examples (a field that never reached ``main``), not measured against this workflow's own multi-start
#: sweep before being shipped as a default — the mistake this note exists to
#: name for whoever tunes it next.
SEED_TILT = 0.02


def tilted_seed(basis, cell, magnitude: float, *, tilt: float = SEED_TILT
               ) -> np.ndarray:
    """A seed moment inside ``basis``'s span, of modulus ``magnitude``.

    The whole magnitude on :func:`moment_frame`'s first row when the basis is
    rank 1 (the ordinary case: one copy, one free real amplitude) — the prior,
    exact behaviour, unaffected by ``tilt``.  A small nonzero coefficient
    (``tilt``) on every row beyond the first when the basis has rank ≥ 2 (see
    :data:`SEED_TILT`), so no DOF starts at a stationary point.  Normalised so
    the combined vector still has modulus exactly ``magnitude``: the frame is
    metric-orthonormal, so a coefficient vector of unit Euclidean norm gives a
    unit modulus automatically.

    Returns the ``(3,)`` crystal-axis vector; the caller decides what to do
    with a rank-0 (empty) basis, since "no moment at all" and "seed nothing"
    read differently at each of this function's two call sites.
    """
    frame = moment_frame(basis, cell)
    n = frame.shape[0]
    if n == 1:
        coeffs = np.array([1.0])
    else:
        coeffs = np.concatenate([[1.0], np.full(n - 1, tilt)])
        coeffs = coeffs / float(np.sqrt(np.sum(coeffs ** 2)))
    return magnitude * (coeffs @ frame)


def warm_seed(basis, cell, preferred, *, tilt: float = SEED_TILT) -> np.ndarray:
    """Like :func:`tilted_seed`, anchored on ``preferred`` rather than row 0.

    WP-1418 stage (c): the descent audit refits a candidate **subgroup** of
    the winner from the winner's own converged moment, not from a flat seed
    — the subgroup's allowed span is a superspace of the winner's own (fewer
    symmetry constraints, by construction, since it is a subgroup), so
    ``preferred`` (the winner's own crystal-axis moment at this atom)
    already lies in ``basis``'s span exactly.  The seed keeps that direction
    and gives every genuinely *new* direction the same small, deterministic,
    nonzero tilt :func:`tilted_seed` gives every row beyond the first — the
    identical stationary-point reason, just anchored where the fit already
    is instead of at the basis's own first row.

    ``preferred`` at (or extremely near) zero has no direction to anchor on
    — the winner's own moment at this atom was itself unsupported or absent
    — and falls back to :func:`tilted_seed`'s ordinary row-0 anchor at the
    same modulus as every other new direction (``tilt`` of a unit vector, not
    zero: an atom with nothing to warm-start from still needs a real seed).
    """
    g = unit_metric(cell)
    pref = np.asarray(preferred, dtype=np.float64)
    norm = float(np.sqrt(max(float(pref @ g @ pref), 0.0)))
    b = np.asarray(basis, dtype=np.float64).reshape(-1, 3)
    if norm <= 1e-9:
        return tilted_seed(b, cell, tilt, tilt=tilt)
    frame = [pref / norm]
    for raw in b:
        v = raw.copy()
        for e in frame:
            v = v - float(e @ g @ raw) * e
        vn = float(np.sqrt(max(float(v @ g @ v), 0.0)))
        if vn > 1e-9:
            frame.append(v / vn)
    stacked = np.asarray(frame, dtype=np.float64)
    n = stacked.shape[0]
    coeffs = (np.array([1.0]) if n == 1 else
             np.concatenate([[1.0], np.full(n - 1, tilt)]))
    coeffs = coeffs / float(np.sqrt(np.sum(coeffs ** 2)))
    return norm * (coeffs @ stacked)


def n_dofs(basis) -> int:
    """How many DOFs a site with this allowed basis contributes."""
    return len(np.asarray(basis, dtype=np.float64).reshape(-1, 3))


def moment_from_dofs(frame, dofs) -> np.ndarray:
    """Crystal-axis components (μ_B) from ``(μ, angles…)``.

    The inverse of :func:`dofs_from_moment` up to the branch cuts of ``atan2``
    and ``arccos``, which is all a parameterisation can promise: (μ, φ) and
    (−μ, φ + π) are the same moment and the fit may land on either.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    n = len(e)
    if n == 0:
        return np.zeros(3, dtype=np.float64)
    d = np.asarray(dofs, dtype=np.float64).reshape(-1)
    if len(d) != n:
        raise ValueError(f"a {n}-dimensional moment subspace takes {n} DOFs, "
                         f"got {len(d)}")
    return _coefficients(d) @ e


def _coefficients(d: np.ndarray) -> np.ndarray:
    """``(n,)`` coefficients on the frame from the ``(n,)`` DOF vector."""
    mu = d[0]
    if len(d) == 1:
        return np.array([mu])
    if len(d) == 2:
        phi = d[1]
        return mu * np.array([np.cos(phi), np.sin(phi)])
    theta, phi = d[1], d[2]
    st = np.sin(theta)
    return mu * np.array([st * np.cos(phi), st * np.sin(phi), np.cos(theta)])


def dofs_from_moment(frame, cell, moment) -> np.ndarray:
    """``(μ, angles…)`` from crystal-axis components — the seed at stage start.

    The moment is assumed to lie in the frame's span; the schema refuses one
    that does not (``Phase._moments_are_stateable``), so anything out of plane
    here is a corrupted table rather than a user error to symmetrise.  μ comes
    back **signed** for a one-dimensional subspace and non-negative otherwise.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    n = len(e)
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    g = unit_metric(cell)
    c = e @ g @ np.asarray(moment, dtype=np.float64).reshape(3)
    return _dofs_from_coefficients(c)


def dofs_in_frame(frame, moment) -> np.ndarray:
    """:func:`dofs_from_moment` for a frame whose cell is not to hand (#598).

    The coefficients are solved from the frame's rows directly rather than
    projected through a metric, so the answer is right whichever cell the
    frame was orthonormalised in — which is what re-seeding a table into a
    compiled model's frames needs, the model having been built at a cell the
    table no longer holds.  Exact for a moment in the frame's span, which the
    schema guarantees.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    if len(e) == 0:
        return np.zeros(0, dtype=np.float64)
    c, *_ = np.linalg.lstsq(e.T, np.asarray(moment, dtype=np.float64).reshape(3),
                            rcond=None)
    return _dofs_from_coefficients(c)


def _dofs_from_coefficients(c: np.ndarray) -> np.ndarray:
    """``(μ, angles…)`` from ``(n,)`` coefficients on an orthonormal frame."""
    n = len(c)
    if n == 1:
        return np.array([c[0]])
    mu = float(np.linalg.norm(c))
    phi = float(np.arctan2(c[1], c[0]))
    if n == 2:
        return np.array([mu, phi])
    theta = 0.0 if mu == 0.0 else float(np.arccos(np.clip(c[2] / mu, -1.0, 1.0)))
    return np.array([mu, theta, phi])


def wrap_angle(phi: float) -> float:
    """``phi`` moved by whole turns into (−π, π], the ``atan2`` range.

    An angle already there comes back bit-for-bit, so a fit that stayed in the
    chart is not touched by rounding.
    """
    if -np.pi < phi <= np.pi:
        return float(phi)
    return float(np.pi - np.mod(np.pi - phi, 2.0 * np.pi))


def canonical_dofs(dofs) -> tuple[np.ndarray, np.ndarray]:
    """The same moment's DOFs in the principal chart, and the sign of each move.

    The principal chart is the one :func:`dofs_from_moment` seeds every stage
    with: μ ≥ 0 for n ≥ 2, the polar angle in [0, π] and the azimuth in
    (−π, π].  The solver does not stay in it, because nothing bounds the DOFs
    (the reason is in :meth:`ParameterTable._collect_atom_moment`): it can end
    a fit at φ + 2πk, at (−μ, φ + π), or at (μ, −θ, φ + π), all of them the
    moment it started from.  Issue #604: a series read those re-wraps as
    jumps in the specimen, and a report printed a polar angle of 50.96 rad.

    Every move here is an identity on the moment (checked by
    :func:`moment_from_dofs` to rounding) and has a **diagonal ±1 Jacobian**,
    so it changes no esd — a whole turn is a shift, and each reflection
    negates one or two DOFs and shifts the rest.  The second return value is
    that diagonal, so a caller holding a covariance or a Jacobian in the old
    chart can carry it across: ``jac[:, k] *= s[k]`` and
    ``corr *= outer(s, s)``.  n = 1 is returned unchanged: its μ is signed by
    design and it has no angle.
    """
    d = np.array(dofs, dtype=np.float64).reshape(-1)
    s = np.ones(len(d), dtype=np.float64)
    n = len(d)
    if n < 2:
        return d, s
    if n == 3:
        # polar first, into (−π, π]; a negative one is the reflection
        # (μ, θ, φ) → (μ, −θ, φ + π)
        d[1] = wrap_angle(d[1])
        if d[1] < 0.0:
            d[1], d[2] = -d[1], d[2] + np.pi
            s[1] = -s[1]
    if d[0] < 0.0:
        # the antipode: (μ, φ) → (−μ, φ + π), and (μ, θ, φ) → (−μ, π − θ, φ + π),
        # which keeps θ in [0, π]
        d[0] = -d[0]
        s[0] = -s[0]
        if n == 3:
            d[1] = np.pi - d[1]
            s[1] = -s[1]
        d[-1] = d[-1] + np.pi
    d[-1] = wrap_angle(d[-1])
    return d, s


def d_moment_d_dofs(frame, dofs) -> np.ndarray:
    """``(n, 3)`` — ∂(crystal-axis components)/∂DOF, analytic.

    The one authority for this chain rule: the analytic moment column
    (``scattering.d_magnetic_f2_d_dofs``, WP-1327) reads it, and so does the
    check that holds it against finite differences.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    n = len(e)
    d = np.asarray(dofs, dtype=np.float64).reshape(-1)
    if n == 0:
        return np.zeros((0, 3), dtype=np.float64)
    mu = d[0]
    if n == 1:
        dc = np.array([[1.0]])
    elif n == 2:
        phi = d[1]
        dc = np.array([[np.cos(phi), np.sin(phi)],
                       [-mu * np.sin(phi), mu * np.cos(phi)]])
    else:
        theta, phi = d[1], d[2]
        st, ct, sp, cp = np.sin(theta), np.cos(theta), np.sin(phi), np.cos(phi)
        dc = np.array([
            [st * cp, st * sp, ct],
            [mu * ct * cp, mu * ct * sp, -mu * st],
            [-mu * st * sp, mu * st * cp, 0.0],
        ])
    return dc @ e
