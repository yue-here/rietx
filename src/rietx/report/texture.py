"""Layer-1 March-Dollase preferred-orientation diagnostic.

Per-region shape attribution (:mod:`.layer1`) sees *where* the intensities are
wrong; it cannot see the *hkl-direction* pattern that betrays texture, because a
March-Dollase bias is not a smooth function of 2θ — it depends on the angle
between each reflection and a preferred axis, which hops around with hkl.  This
module supplies that missing view: it extracts a per-reflection multiplicative
intensity correction from the residual (a Le Bail-style partition that
deconvolves overlaps by calculated share), then asks which single axis and
March coefficient r best reproduce those corrections.

The score is the fraction of the intensity-misfit "energy" that a March-Dollase
model on a given axis explains,

    R² = 1 − Σ_k w_k (f_k − P_k(r; a))² / Σ_k w_k (f_k − 1)²,

with f_k the extracted correction (f_k = 1 for a perfect fit), w_k the
reflection's calculated area (importance), and P_k(r; a) the orbit-averaged
March factor (:mod:`rietx.model.preferred_orientation`).  The denominator is
the misfit with **no** correction (r = 1 ⇒ P ≡ 1), so R² is exactly "how much of
what the intensities are getting wrong is explained by texture on this axis".

Deliberately independent of the maturity gate: strong uncorrected texture is a
*common cause* of an immature fit, so this diagnostic must still speak when
Layer 1 otherwise abstains.  It reports the axis; acting on it (freeing r on
that axis) is the strategy engine's decision.

Reference: Dollase (1986) J. Appl. Cryst. 19, 267.
"""

from __future__ import annotations

import numpy as np

from ..crystallography.lattice import reciprocal_metric_tensor
from ..crystallography.symmetry import reflection_orbits, resolve_group
from ..model.forward import CompiledModel
from ..model.preferred_orientation import cos2_alpha, march_term, orbit_layout
from .schemas import (
    TEXTURE_MIN_R2,
    TEXTURE_MIN_REFLECTIONS,
    TEXTURE_MIN_STRENGTH,
    TextureAnalysis,
)

#: r grid (log-spaced) searched per candidate axis.  Wide enough for severe
#: platy/needle habits; the R² score is flat near the optimum so a grid this
#: dense is as good as a solver and stays deterministic.
_R_GRID = np.geomspace(0.25, 4.0, 121)

#: orbit members × r values evaluated in one block by :func:`_score_axis`:
#: 2²¹ elements, 16 MB per array of that shape (a block holds a few), which
#: holds the whole grid for a pattern of up to ~17 000 orbit members
_BLOCK_ELEMENTS = 1 << 21


def _candidate_axes(max_index: int) -> list[tuple[int, int, int]]:
    """Distinct low-index reciprocal directions (gcd-reduced, sign-canonical).

    Symmetry-equivalent axes give identical templates and therefore identical
    scores; they are not deduplicated here (the caller reports the best-scoring
    representative), only collinear duplicates are.
    """
    seen: set[tuple[int, int, int]] = set()
    axes: list[tuple[int, int, int]] = []
    for h in range(-max_index, max_index + 1):
        for k in range(-max_index, max_index + 1):
            for lidx in range(-max_index, max_index + 1):
                if h == 0 and k == 0 and lidx == 0:
                    continue
                g = np.gcd.reduce([abs(h), abs(k), abs(lidx)])
                red = (h // g, k // g, lidx // g)
                # canonical sign: first non-zero component positive
                for comp in red:
                    if comp != 0:
                        if comp < 0:
                            red = (-red[0], -red[1], -red[2])
                        break
                if red not in seen:
                    seen.add(red)
                    axes.append(red)
    return axes


def _extracted_corrections(model: CompiledModel, values: dict[str, float]
                           ) -> list[tuple[np.ndarray, np.ndarray]]:
    """Per-phase (f, weight) arrays over the reflection list.

    ``f_k`` is the multiplicative intensity correction reflection k would need
    (Le Bail partition of the residual by calculated share, summed over emission
    lines; f_k = 1 where the fit is already right), and ``weight_k`` is its total
    calculated area — the importance the R² score weights by.  Reflections that
    never enter the fit window get weight 0.
    """
    bases = model.derivative_bases(values)
    net = model.y_obs - model.background(values)
    # total calculated Bragg intensity at every point (all phases, all lines)
    # every drawn component (WP-1343): a split phase's magnetic peaks are
    # rows of their own, and reflection k's correction sums over both
    n_phases = len(bases.planes)
    y_bragg = np.zeros_like(model.tt)
    for ip in range(n_phases):
        for rows, peaks in bases.component_entries(ip):
            for (il, k, i0, i1, omega, *_rest) in rows:
                y_bragg[i0:i1] += peaks[il][3][k] * omega

    out: list[tuple[np.ndarray, np.ndarray]] = []
    for ip in range(n_phases):
        n = len(model.phases[ip].reflections)
        num = np.zeros(n)
        den = np.zeros(n)
        for rows, peaks in bases.component_entries(ip):
            for (il, k, i0, i1, omega, *_rest) in rows:
                intensity = peaks[il][3][k]
                if intensity == 0.0:
                    continue
                denom = y_bragg[i0:i1]
                good = denom > 1e-12
                if not np.any(good):
                    continue
                share = intensity * omega[good] / denom[good]
                num[k] += float((share * net[i0:i1][good]).sum())
                den[k] += intensity * float(omega.sum())
        f = np.where(den > 0.0, num / np.where(den > 0.0, den, 1.0), 1.0)
        out.append((f, den))
    return out


def _score_axis(f: np.ndarray, w: np.ndarray, cos2: np.ndarray,
                seg: np.ndarray, counts: np.ndarray) -> tuple[float, float]:
    """Best (r, R²) for one axis by a free-scale grid search over r.

    March-Dollase P is not normalised — its overall level is degenerate with the
    phase scale, which in an r=1 refinement has already absorbed the *mean*
    texture effect.  So the model fitted here is s·P_k(r; a) with s free, and the
    baseline is the weighted-mean model s=f̄ (no angular dependence): R² then
    measures how much of the reflection-to-reflection intensity *variation* —
    not its level — a single-axis March model on this axis explains.
    """
    W = float(w.sum())
    if W <= 0.0:
        return 1.0, 0.0
    fbar = float((w * f).sum() / W)
    base_ss = float((w * (f - fbar) ** 2).sum())
    if base_ss <= 0.0:
        return 1.0, 0.0
    best_r, best_ss = 1.0, base_ss
    n_bins = len(counts)
    # The grid is evaluated a block of r at a time, one row per r.  Every
    # element is the same arithmetic the one-r-at-a-time loop did, each bin
    # sums its members in the same order, and a row reduction is the same
    # pairwise sum as a 1-D one, so the scores are bit-identical to it; the
    # loop was 121 numpy calls per axis per phase, a third of a stage report
    # (WP-1335).  The block bounds the memory to _BLOCK_ELEMENTS doubles.
    # The March factor is evaluated once per *distinct* cos²α and indexed
    # back, which is the same number per member: an orbit repeats few angles
    # to an axis (a Friedel mate always repeats its partner's), and the
    # power is what the grid's cost is.
    distinct, member_of = np.unique(cos2, return_inverse=True)
    step = max(1, _BLOCK_ELEMENTS // max(len(cos2), 1))
    for lo in range(0, len(_R_GRID), step):
        rs = _R_GRID[lo:lo + step]
        term = march_term(distinct[None, :], rs[:, None])[:, member_of]
        bins = (seg[None, :] + n_bins * np.arange(len(rs))[:, None]).ravel()
        p = (np.bincount(bins, weights=term.ravel(), minlength=len(rs) * n_bins)
             .reshape(len(rs), n_bins) / counts)
        denom = (w * p * p).sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (w * f * p).sum(axis=1) / denom   # optimal free scale per r
            ss = (w * (f - s[:, None] * p) ** 2).sum(axis=1)
        for i, r in enumerate(rs):
            if denom[i] <= 0.0:
                continue
            if s[i] <= 0.0:
                # a negative scale would fit the anti-pattern (the wrong r's
                # mirror image) equally well — that is unphysical (the phase
                # scale is positive), so those r are not admissible fits
                continue
            if float(ss[i]) < best_ss:
                best_ss, best_r = float(ss[i]), float(r)
    return best_r, 1.0 - best_ss / base_ss


def analyse_texture(model: CompiledModel, values: dict[str, float], *,
                    max_index: int = 2, min_weight_frac: float = 1e-3
                    ) -> list[TextureAnalysis]:
    """Detect single-axis March-Dollase texture, one result per phase.

    For each phase the extracted per-reflection corrections are matched against
    every candidate axis (up to ``max_index``) at its best-fit r; the axis
    explaining the most intensity misfit wins.  ``detected`` requires the score,
    the departure of r from 1, and the reflection count all to clear the pinned
    thresholds — so a texture-free phase reports ``detected=False`` with r≈1
    (the best-scoring axis stays named as evidence, WP-1054).
    Rietveld mode only (Le Bail / Pawley intensities are empirical, so there is
    no calculated pattern to compare against): returns ``[]`` otherwise.
    """
    # Empty on a model whose grid is not an angle, the boundary check
    # ``report.strain`` carries for the same reason: March-Dollase averages
    # over a reflection's symmetry orbit at the *measured* angle, and on a
    # time-of-flight bank every reflection shares one — the correction has a
    # different form there, not a different value, and ``compile_tof_model``
    # refuses a declared block outright.
    if model.mode != "rietveld" or getattr(model, "axis", "two_theta") != "two_theta":
        return []
    corrections = _extracted_corrections(model, values)
    axes = _candidate_axes(max_index)
    results: list[TextureAnalysis] = []

    for ip, (f, w) in enumerate(corrections):
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        gstar = reciprocal_metric_tensor(*cell)
        refl = model.phases[ip].reflections
        # only reflections that carry appreciable calculated intensity inform
        # the fit; near-absent ones have noise-dominated corrections
        live = w > min_weight_frac * (w.max() if w.size and w.max() > 0 else 1.0)
        n_used = int(live.sum())
        if n_used < TEXTURE_MIN_REFLECTIONS:
            results.append(TextureAnalysis(phase_index=ip, n_reflections_used=n_used))
            continue

        # ``resolve_group``, not the bare ``spacegroup`` string: for a phase
        # carrying its own operation list that string is a *label* the tables
        # do not hold, and the list rides along on the frozen set for exactly
        # this (Q-17).  Found by the Ba₂FeSbSe₅ S3(a,b) acceptance fit, which
        # refined for 1268 s and then died in ``report()``.
        frozen = model.phases[ip].reflections
        members, seg, counts = orbit_layout(reflection_orbits(
            resolve_group(frozen.spacegroup or refl.spacegroup,
                          frozen.operations if frozen.spacegroup
                          else refl.operations), refl.hkl))
        # restrict the score to live reflections: zero their weight, keep the
        # orbit layout aligned with the full list
        w_live = np.where(live, w, 0.0)

        scored: list[tuple[tuple[int, int, int], float, float]] = []
        for a in axes:
            cos2 = cos2_alpha(members, np.array(a, dtype=np.int64), gstar)
            r, r2 = _score_axis(f, w_live, cos2, seg, counts)
            scored.append((a, r, r2))
        scored.sort(key=lambda t: -t[2])
        best_axis, best_r, best_r2 = scored[0]
        runner = next((s for s in scored[1:]
                       if not _equivalent(s[0], best_axis, gstar, members, seg, counts)),
                      None)

        detected = (best_r2 >= TEXTURE_MIN_R2
                    and abs(best_r - 1.0) >= TEXTURE_MIN_STRENGTH
                    and n_used >= TEXTURE_MIN_REFLECTIONS)
        # best_axis is evidence, not a verdict (WP-1054): it stays populated
        # when detection fails, so a consumer reading the sub-threshold r2 can
        # see which axis carried it.  ``detected`` is the branch field.
        results.append(TextureAnalysis(
            phase_index=ip,
            best_axis=best_axis,
            march_coefficient=best_r,
            r2=best_r2,
            n_reflections_used=n_used,
            detected=detected,
            runner_up_axis=(runner[0] if runner else None),
            runner_up_r2=(runner[2] if runner else 0.0),
        ))
    return results


#: reference r for the equivalence test — any r ≠ 1 distinguishes non-equivalent
#: axes (r = 1 makes every P ≡ 1); 0.5 gives a well-separated pattern.
_EQUIV_REF_R = 0.5


def _p_pattern(axis: tuple[int, int, int], gstar, members, seg, counts, r: float
               ) -> np.ndarray:
    term = march_term(cos2_alpha(members, np.array(axis), gstar), r)
    return np.bincount(seg, weights=term, minlength=len(counts)) / counts


def _equivalent(a: tuple[int, int, int], b: tuple[int, int, int], gstar,
                members, seg, counts, *, tol: float = 1e-9) -> bool:
    """Whether two axes give the same per-reflection March pattern.

    Compared by the *full* orbit-averaged P(r) pattern, not by ⟨cos²α⟩ — in a
    high-symmetry crystal ⟨cos²α⟩ is 1/3 for every reflection regardless of
    axis (the orbit samples all directions), yet the P patterns still differ
    because P averages a nonlinear function of the per-equivalent angle.
    Identical patterns are exactly what makes two axes indistinguishable here.
    """
    pa = _p_pattern(a, gstar, members, seg, counts, _EQUIV_REF_R)
    pb = _p_pattern(b, gstar, members, seg, counts, _EQUIV_REF_R)
    return bool(np.max(np.abs(pa - pb)) < tol)
