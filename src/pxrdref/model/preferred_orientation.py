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

This is the single-axis approximation; multi-axis and spherical-harmonics
texture (Von Dreele 1997) are out of scope.

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
    counts = np.array([len(o) for o in orbits], dtype=np.int64)
    if len(orbits) == 0:
        return np.zeros((0, 3), dtype=np.int64), np.zeros(0, dtype=np.int64), counts
    members = np.vstack(orbits).astype(np.int64)
    seg = np.repeat(np.arange(len(orbits), dtype=np.int64), counts)
    return members, seg, counts
