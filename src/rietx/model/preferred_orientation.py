"""March-Dollase single-axis preferred orientation.

A powder whose crystallites are not randomly oriented has reflection intensities
biased by the non-uniform pole distribution.  The March (1932) distribution
models a single preferred axis; Dollase (1986) folded it into Rietveld
refinement as a per-reflection intensity multiplier

    P_hkl = (1/M) Σ_{m∈orbit}  [ r²·cos²α_m + sin²α_m / r ]^(−3/2)

where the sum runs over the reflection's symmetry-equivalent orbit (M its
multiplicity), α_m is the angle between the fixed preferred-orientation axis
and the scattering vector of equivalent m, and r > 0 is the refinable March
coefficient.  Both the axis and the scattering vectors are **reciprocal-lattice
directions** (integer hkl), so the angle is taken with the reciprocal metric
tensor G*:

    cos α = (h_m · G* · a) / √[(h_m · G* · h_m)(a · G* · a)],   a = axis hkl.

At **r = 1** every bracket is r²cos²α + sin²α/r = cos²α + sin²α = 1, so
P_hkl ≡ 1 exactly — the correction is the identity when off, for every
reflection and cell.  Averaging over the orbit is what makes P depend on the
*direction* of hkl relative to the axis rather than on any single equivalent;
Friedel mates (±h) give identical brackets (cos²α is even in h), so including
them in the orbit leaves P unchanged.

Convention — documented by physics, not by the sign of r
--------------------------------------------------------
``r`` is dimensionless and the March axis is the crystallographic direction the
crystallites preferentially align.  For a reflection whose scattering vector is
**parallel** to the axis (α = 0) the bracket is r², so P = r^(−3): r < 1
*enhances* those reflections and r > 1 *suppresses* them.  Mapping that onto
crystal habit depends on the diffraction geometry, because the axis's mean
orientation relative to the scattering vector differs between the two:

* **Bragg-Brentano reflection geometry** — platy crystallites lie flat, so a
  plate normal points preferentially along the scattering vector (⊥ to the
  holder).  Take the axis = plate normal: **r < 1 ⇒ platy** habit (the axial
  reflections are enhanced).  Needle/rod crystallites lie in the surface plane,
  so with the axis = needle direction, **r > 1 ⇒ acicular** habit.
* **Transmission (Debye-Scherrer / capillary) geometry** — the preferred axis
  sits preferentially *perpendicular* to the scattering vector, so the sense of
  r reverses: **r > 1 ⇒ platy**, **r < 1 ⇒ needle**, for the same axis choice.

The correction itself is geometry-agnostic (it only ever sees the angle to the
scattering vector); it is the *interpretation of r* that flips.  Codes disagree
on the sign convention, so this docstring — not the letter r — is the contract.

This is the single-axis approximation.  The general one, spherical-harmonics
texture (Von Dreele 1997, WP-1960), sits at the end of this module: its
crystal half is ``crystallography.spherical_harmonics`` and its sample half
the ψ table below.  March-Dollase stays beside it, one refinable parameter
against that model's 2-44, and better conditioned for a single fibre texture.

Spherical-harmonics texture
---------------------------
    P_h = 1 + Σ_t w_t·C_t·K_t(h),   w_t = (4π/(2l+1))·k_l(ψ) = √(4π/(2l+1))·P_l(cos ψ)

(Von Dreele 1997, eq. 3, with cylindrical sample symmetry, so only the n = 0
sample harmonic k_l = √((2l+1)/4π)·P_l survives).  ψ is the angle between the
scattering vector and the specimen's symmetry axis.  In every geometry here
it is one angle for every reflection, so each w_t is a constant of the stage.
P is affine in C, and C = 0 gives exactly 1.

References
----------
* March, A. (1932). *Z. Kristallogr.* 81, 285 — the original crystallite
  orientation distribution.
* Dollase, W. A. (1986). *J. Appl. Cryst.* 19, 267 — the March model as a
  Rietveld intensity correction, averaged over the reflection multiplicity.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend


def cos2_alpha(members: np.ndarray, axis: np.ndarray, gstar: np.ndarray
               ) -> np.ndarray:
    """cos²α between each reflection ``members`` (N,3) and ``axis`` in G*-space.

    α is the angle between two reciprocal-lattice vectors, so it is taken with
    the reciprocal metric tensor (International Tables B).  ``axis`` need not be
    normalised — cos²α is scale-invariant in it.  Guards a zero denominator
    (only 000, which never appears in a reflection list) to cos²α = 1.
    """
    xp = get_backend()
    h = xp.asarray(members, dtype=np.float64)
    a = xp.asarray(axis, dtype=np.float64)
    ga = gstar @ a
    haa = h @ ga                                   # h · G* · a          (N,)
    hh = xp.einsum("mi,ij,mj->m", h, gstar, h)     # h · G* · h          (N,)
    # xp.matmul, not `a @ ga`: a 1-D·1-D matmul lowers to aten::dot, which MPS
    # cannot batch — the backend expands that one shape (backend/api.py)
    aa = xp.matmul(a, ga)                          # a · G* · a          0-d scalar
    denom = hh * aa
    return xp.where(denom > 0.0, haa * haa / xp.where(denom > 0.0, denom, 1.0), 1.0)


def march_term(cos2: np.ndarray, r: float) -> np.ndarray:
    """Per-equivalent March factor (r²·cos²α + sin²α/r)^(−3/2)."""
    xp = get_backend()
    c = xp.asarray(cos2, dtype=np.float64)
    bracket = r * r * c + (1.0 - c) / r
    return bracket ** (-1.5)


def march_term_and_dr(cos2: np.ndarray, r: float) -> tuple[np.ndarray, np.ndarray]:
    """(term, ∂term/∂r) for the per-equivalent March factor.

    With A = r²·cos²α + sin²α/r, term = A^(−3/2) and

        ∂A/∂r = 2r·cos²α − sin²α/r²,
        ∂term/∂r = −3/2 · A^(−5/2) · ∂A/∂r.

    At r = 1, A ≡ 1 and ∂A/∂r = 2cos²α − sin²α = 3cos²α − 1, so the first-order
    intensity response to switching PO on is ∂term/∂r|₁ = −3/2·(3cos²α − 1) —
    the signature the Layer-1 axis diagnostic regresses against.
    """
    xp = get_backend()
    c = xp.asarray(cos2, dtype=np.float64)
    s = 1.0 - c
    A = r * r * c + s / r
    dA = 2.0 * r * c - s / (r * r)
    term = A ** (-1.5)
    return term, -1.5 * A ** (-2.5) * dA


def _segment_mean(values: np.ndarray, seg: np.ndarray, counts: np.ndarray
                  ) -> np.ndarray:
    """Mean of ``values`` within each reflection's orbit segment.

    ``seg`` maps each stacked equivalent to its reflection index; ``counts`` is
    the per-reflection orbit size (the multiplicity).
    """
    xp = get_backend()
    total = xp.segment_sum(values, seg, len(counts))
    return total / xp.asarray(counts, dtype=np.float64)


def march_dollase_factors(members: np.ndarray, seg: np.ndarray, counts: np.ndarray,
                          axis: np.ndarray, gstar: np.ndarray, r: float
                          ) -> np.ndarray:
    """Orbit-averaged P_hkl (N,) for the flattened orbit layout.

    ``members`` (M_total, 3) stacks every reflection's equivalents; ``seg``
    (M_total,) and ``counts`` (N,) segment them — the frozen layout built once
    per stage (:func:`orbit_layout`).  ``gstar`` and ``r`` are the only
    per-evaluation inputs, so P follows the cell and r smoothly.
    """
    return _segment_mean(march_term(cos2_alpha(members, axis, gstar), r), seg, counts)


def march_dollase_and_dr(members: np.ndarray, seg: np.ndarray, counts: np.ndarray,
                         axis: np.ndarray, gstar: np.ndarray, r: float
                         ) -> tuple[np.ndarray, np.ndarray]:
    """(P_hkl, ∂P_hkl/∂r), each (N,) — the analytic-Jacobian path."""
    term, dterm = march_term_and_dr(cos2_alpha(members, axis, gstar), r)
    return _segment_mean(term, seg, counts), _segment_mean(dterm, seg, counts)


def orbit_layout(orbits: list[np.ndarray]
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flatten per-reflection orbits into (members, seg, counts).

    ``members`` (M_total, 3) concatenates the equivalents of every reflection,
    ``seg`` (M_total,) holds each equivalent's reflection index, and ``counts``
    (N,) the orbit sizes.  This is the discrete object frozen at stage compile;
    only the metric-dependent angles change during a least-squares run.
    """
    # ``intp``, not int64: ``repeat`` casts its counts to the index type under
    # the 'safe' rule, which refuses int64 where that type is 32 bits (wasm32,
    # WP-1966).  The two are one type on every 64-bit platform.
    counts = np.array([len(o) for o in orbits], dtype=np.intp)
    if len(orbits) == 0:
        return np.zeros((0, 3), dtype=np.int64), np.zeros(0, dtype=np.int64), counts
    members = np.vstack(orbits).astype(np.int64)
    seg = np.repeat(np.arange(len(orbits), dtype=np.int64), counts)
    return members, seg, counts


#: ψ in degrees, the angle between the scattering vector and the specimen's
#: symmetry axis, per ``Geometry.kind`` (WP-1960 D2).  Symmetric reflection
#: puts the scattering vector on the plate normal.  Symmetric transmission and
#: a spinning capillary put it perpendicular to the axis (Järvinen, 1993,
#: J. Appl. Cryst. 26, 525, Table I; Ahtee et al., 1989, J. Appl. Cryst. 22,
#: 261).  GSAS-II's ``Bragg`` uses 90° instead, so its coefficients differ by
#: P_l(0) (WP-1960 § Pinned by Task 1).  ``tests/test_texture.py`` holds the
#: keys equal to ``Geometry.kind``'s members.
TEXTURE_SAMPLE_PSI_DEG = {
    "bragg_brentano": 0.0,
    "flat_plate_transmission": 90.0,
    "debye_scherrer": 90.0,
}


def texture_term_weights(degrees, psi_deg: float) -> np.ndarray:
    """w_t = √(4π/(2l+1))·P_l(cos ψ) for each term's degree l.

    Frozen per stage.  cos ψ is snapped to zero at 90°, where floating point
    leaves 6e-17, so a transmission weight is P_l(0) to the bit.
    """
    c = float(np.cos(np.radians(psi_deg)))
    c = 0.0 if abs(c) < 1e-12 else c
    return np.array([np.sqrt(4.0 * np.pi / (2 * degree + 1))
                     * np.polynomial.legendre.Legendre.basis(degree)(c)
                     for degree in degrees], dtype=np.float64)


def texture_factors(harmonics, weights: np.ndarray, coefficients):
    """P_h = 1 + Σ_t w_t·C_t·K_t(h), shape (N,).

    ``harmonics`` is K, (N, n_terms), at the current cell; ``coefficients`` is
    C in the same order.  The weights are lifted onto the backend, so no
    frozen numpy array meets a traced value in a python operator.  C = 0 gives
    a zero product and exactly 1.
    """
    xp = get_backend()
    w = xp.asarray(weights, dtype=np.float64)
    return 1.0 + xp.matmul(harmonics, w * coefficients)


#: Below this, P counts as negative.  P is dimensionless with the random
#: powder at 1, and the bounded-LM driver can leave a reflection's P on the
#: face P = 0 to roundoff, which is a legal pole density.
TEXTURE_POSITIVITY_TOL = 1e-9

#: Directions sampled over the sphere for the minimum of P between
#: reflections.  The terms run to l = 8 or so, whose features span about
#: 180°/l; 2000 points sit about 4.5° apart.  The samples only find the dips:
#: the minimum is polished locally from the lowest of them
#: (:data:`TEXTURE_POLISH_STARTS`), because a sampled minimum sits 2.0e-3 to
#: 7.9e-3 of the random powder above the true one at orders 2-8 against a bar
#: of 1e-3 (``tests/test_texture.py``; WP-2002, the seventh round's Q2).
TEXTURE_SPHERE_SAMPLES = 2000
#: How many of the lowest sampled directions the minimum is polished from, as
#: the domain test's reference does.
TEXTURE_POLISH_STARTS = 5
#: The polish: this many patches of 11 × 11 directions in the tangent plane
#: of each start, each patch 0.3 of the last across and centred on the last
#: one's lowest point.  The first spans one sample spacing either side, the
#: last a step of about 1e-5 rad.
TEXTURE_POLISH_LEVELS = 6


def sphere_minimum(p_of, directions: np.ndarray, starts: int = TEXTURE_POLISH_STARTS,
                   levels: int = TEXTURE_POLISH_LEVELS) -> float:
    """The lowest value of ``p_of`` over the unit sphere.

    ``p_of`` maps (M, 3) unit vectors to (M,) values, numpy only.  It is
    sampled at ``directions``, then refined around the ``starts`` lowest
    samples by ``levels`` shrinking patches, every start's patch in one call.
    Each patch is a grid in the plane tangent to its centre, projected back
    onto the sphere, so no start sits at a coordinate pole.  The result never
    lies above the sampled minimum.
    """
    values = np.asarray(p_of(directions), dtype=np.float64)
    lowest = float(values.min())
    centres = directions[np.argsort(values)[:starts]]
    half = float(np.sqrt(4.0 * np.pi / len(directions)))
    offsets = np.linspace(-1.0, 1.0, 11)
    a, b = (g.ravel() for g in np.meshgrid(offsets, offsets))
    for _ in range(levels if len(centres) else 0):
        seed = np.where(np.abs(centres[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]])
        e1 = np.cross(centres, seed)
        e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
        e2 = np.cross(centres, e1)
        u = (centres[:, None, :] + half * (a[None, :, None] * e1[:, None, :]
                                           + b[None, :, None] * e2[:, None, :]))
        u /= np.linalg.norm(u, axis=2, keepdims=True)
        v = np.asarray(p_of(u.reshape(-1, 3)), dtype=np.float64).reshape(len(centres), -1)
        best = np.argmin(v, axis=1)
        centres = u[np.arange(len(centres)), best]
        lowest = min(lowest, float(v.min()))
        half *= 0.3
    return lowest


def texture_index(degrees, coefficients) -> float:
    """J = 1 + Σ C²/(2l+1) (Von Dreele 1997, eq. 16; Bunge 1982, 14.135).

    Exact for orthonormal harmonics, which these are.  The odd orders are not
    measured and the series stops at the declared order, so this is a lower
    bound on the specimen's texture index.  J = 1 is a random powder.
    """
    return 1.0 + float(sum(c * c / (2 * degree + 1)
                           for degree, c in zip(degrees, coefficients, strict=True)))
