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

from dataclasses import dataclass

import numpy as np

from ..crystallography.lattice import reciprocal_metric_tensor
from ..crystallography.symmetry import reflection_orbits, resolve_group
from ..model.forward import CompiledModel
from ..model.preferred_orientation import cos2_alpha, march_term, orbit_layout
from ..optimize import lapack
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
    if model.mode != "rietveld":
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


# ------------------------------------------------------------ the order screen
# WP-1974 tasks 1-2: the spherical-harmonics order the misfit needs, scored on
# the same f_k and w_k as the axis.  A measurement hook: nothing in the report
# calls it yet, so no default output moves.  Which numbers would make it
# suggest an order is the gated Layer-2 action of the WP's task 3.


#: A design column counts towards the order screen's rank when its singular
#: value, on weight-centred columns scaled to the unit norm of their
#: *unpartitioned* values, is above this (absolute, since the scaling already
#: makes it a surviving fraction for a column orthogonal to the rest;
#: collinearity among visible terms also makes small ones).  ``tests/test_texture.py`` records the gap it
#: sits in over six Laue classes and a short-range P -1 phase at orders 2-8:
#: dropped columns at roundoff, kept ones at least 2e-4, so any value from
#: 1e-14 to 1e-4 gives the same ranks there.  With no gap the tolerance decides.
_ORDER_RANK_TOL = 1e-8


@dataclass(frozen=True)
class _OrderFit:
    """One order's weighted linear solve on a phase's extracted corrections."""

    order: int
    n_terms: int
    rank: int                       # terms the partition leaves resolvable
    r2: float                       # same baseline as the axis score's
    names: tuple[str, ...]
    visibility: tuple[float, ...]   # ‖M·K_t‖_w / ‖K_t‖_w, centred
    coefficients: tuple[float, ...]  # C_t, in the block's own units; NaN when a = 0
    rms_p: float                    # weighted rms of P − 1 at the reflections
    min_kept_sv: float              # the rank gap, each side of _ORDER_RANK_TOL
    max_dropped_sv: float


@dataclass(frozen=True)
class _OrderStep:
    """The nested comparison of one order against the order below it.

    ``p_value`` is not calibrated: w_k are calculated areas, inverse variances
    only under counting noise, and the residual is mostly systematic.  NaN
    wherever a number was not measured.
    """

    order: int
    added_rank: int
    delta_r2: float
    f_stat: float
    p_value: float
    delta_bic: float                # n·ln(SS_hi/SS_lo) + Δp·ln n; < 0 favours hi
    delta_bic_vs_axis: float        # against the best axis; NaN when none was scored


@dataclass(frozen=True)
class _OrderScreen:
    phase_index: int
    n_reflections_used: int
    n_effective: float              # Kish: (Σw)²/Σw², beside the n the BIC charges
    axis: tuple[int, int, int] | None
    axis_r: float | None            # r polished on the best axis, not the grid's
    axis_r2: float | None           # at axis_r; the steps' ΔBIC vs axis reads this
    fits: tuple[_OrderFit, ...]
    steps: tuple[_OrderStep, ...]


def _partitioned(model: CompiledModel, values: dict[str, float], ip: int,
                 multipliers: np.ndarray) -> np.ndarray:
    """Phase ip's extraction applied to a pattern of its own peaks times g.

    ``multipliers`` is (n_reflections, m).  Column j of the answer is what
    :func:`_extracted_corrections` would read off a net intensity built from
    phase ip's calculated peaks, reflection k scaled by g_kj, partitioned over
    every phase's calculated pattern as the extraction does.  The extraction is
    linear in the net, so this is M·g, M the partition operator: a texture term
    whose values the partition averages away (hkl and khl at one position with
    opposite signs) comes back near zero here.
    """
    bases = model.derivative_bases(values)
    y_bragg = np.zeros_like(model.tt)
    for jp in range(len(bases.planes)):
        for rows, peaks in bases.component_entries(jp):
            for (il, k, i0, i1, omega, *_rest) in rows:
                y_bragg[i0:i1] += peaks[il][3][k] * omega
    g = np.asarray(multipliers, dtype=np.float64)
    net = np.zeros((len(model.tt), g.shape[1]))
    for rows, peaks in bases.component_entries(ip):
        for (il, k, i0, i1, omega, *_rest) in rows:
            net[i0:i1] += (peaks[il][3][k] * omega)[:, None] * g[k][None, :]
    num = np.zeros_like(g)
    den = np.zeros(g.shape[0])
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
            num[k] += share @ net[i0:i1][good]
            den[k] += intensity * float(omega.sum())
    return np.where(den[:, None] > 0.0, num / np.where(den > 0.0, den, 1.0)[:, None], 0.0)


def _weighted_fit(f: np.ndarray, w: np.ndarray, design: np.ndarray, scale: np.ndarray
                  ) -> tuple[float, int, np.ndarray, float, float, float]:
    """(SS, rank, b, a, min kept sv, max dropped sv) of f ≈ a + design·b, weights w.

    The columns are weight-centred, so a is the free scale, and divided by
    ``scale`` before the rank is read, so for a column orthogonal to the rest
    its singular value is its surviving fraction.
    """
    sw = np.sqrt(w)
    W = float(w.sum())
    fbar = float((w * f).sum() / W)
    y = sw * (f - fbar)
    nan = float("nan")
    if design.shape[1] == 0:
        return float(y @ y), 0, np.zeros(0), fbar, nan, nan
    centre = (w @ design) / W
    x = sw[:, None] * (design - centre[None, :]) / scale[None, :]
    u, sv, vt = lapack.svd(x, full_matrices=False)
    keep = sv > _ORDER_RANK_TOL
    coef = vt[keep].T @ ((u[:, keep].T @ y) / sv[keep])
    resid = y - x @ coef
    b = coef / scale
    # a design wider than tall has columns beyond the singular values: zero
    dropped = np.concatenate([sv[~keep], np.zeros(max(design.shape[1] - len(sv), 0))])
    return (float(resid @ resid), int(keep.sum()), b, fbar - float(centre @ b),
            float(sv[keep].min()) if keep.any() else nan,
            float(dropped.max()) if dropped.size else nan)


def _order_screen(model: CompiledModel, values: dict[str, float], *,
                  orders: tuple[int, ...] = (2, 4, 6, 8), max_index: int = 2,
                  min_weight_frac: float = 1e-3) -> list[_OrderScreen]:
    """The per-order solve and the nested comparison, per phase (WP-1974).

    For each even order L the extracted corrections are fitted as
    f_k ≈ a + Σ_t b_t·(M·w_l K_t)_k, every term of the Laue class from l = 2
    to L, M the extraction's own partition (:func:`_partitioned`) and w_l the
    geometry's term weight; C_t = b_t/a.  Linear, so one solve per order, and
    its R² has the axis score's baseline (the weighted mean), so the two
    compare directly.  Each order is compared with the one below by the F
    statistic and ΔBIC on the rank it adds, and with the best March-Dollase
    axis by ΔBIC at one shape parameter.  The basis is the symmetrised
    spherical-harmonics expansion of the orientation distribution, one term
    per Laue-allowed harmonic (Von Dreele 1997, J. Appl. Cryst. 30, 517) and
    ΔBIC = n·ln(SS_hi/SS_lo) + Δp·ln n (negative favours the higher order), the
    Bayesian information criterion of Schwarz (1978, Ann. Statist. 6, 461).
    The axis's r is polished off the
    axis screen's grid (a bounded solve in ln r between the grid's neighbours
    of its best r), since the order solve is exact and the grid's step would
    otherwise charge the axis its quantisation: on a −3m1 specimen built with
    r = 0.8 the grid made order 4 win by ΔBIC −16.7 (PR #1604 review).  The
    search over axes is not charged, which leans towards the axis; the axis
    screen's own r and R² (:func:`analyse_texture`) are not changed.  Measures,
    decides nothing.

    Three limits a consumer inherits.  The p-values are not calibrated
    (:class:`_OrderStep`).  The BIC charges n, the live reflection count, which
    can sit well above the Kish count beside it.  And the constant a stands for
    the other phases' share of an overlapped reflection, 1 − (M·1)_k, which
    holds where they fit and a = 1: on overlapped peaks of a multi-phase
    pattern whose scale absorbed the mean texture the screen carries a bias of
    (a − 1)(M·1 − 1), as does the axis score.  ``max_index`` and
    ``min_weight_frac`` are the axis screen's, so both read the same
    reflections against the same axes.
    """
    from scipy.optimize import minimize_scalar
    from scipy.stats import f as f_dist

    from ..crystallography.spherical_harmonics import texture_basis
    from ..model.preferred_orientation import (
        TEXTURE_SAMPLE_PSI_DEG,
        texture_term_weights,
    )

    orders = tuple(orders)
    if not orders or list(orders) != sorted(set(orders)) or any(
            o < 2 or o % 2 for o in orders):
        raise ValueError(f"orders {orders}: even, at least 2, strictly ascending")
    if model.mode != "rietveld":
        return []
    nan = float("nan")
    axes = {r.phase_index: r for r in analyse_texture(
        model, values, max_index=max_index, min_weight_frac=min_weight_frac)}
    corrections = _extracted_corrections(model, values)
    psi = TEXTURE_SAMPLE_PSI_DEG[model.geometry_kind]
    out: list[_OrderScreen] = []
    for ip, (f, w) in enumerate(corrections):
        live = w > min_weight_frac * (w.max() if w.size and w.max() > 0 else 1.0)
        n = int(live.sum())
        tex = axes.get(ip)
        scored = tex is not None and tex.best_axis is not None
        if n < 2:
            out.append(_OrderScreen(phase_index=ip, n_reflections_used=n, n_effective=0.0,
                                    axis=None, axis_r=None, axis_r2=None, fits=(),
                                    steps=()))
            continue
        refl = model.phases[ip].reflections
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        group = resolve_group(refl.spacegroup, refl.operations)
        wl = w[live]
        fl = f[live]
        W = float(wl.sum())
        base = float((wl * (fl - (wl * fl).sum() / W) ** 2).sum())
        # The highest order's terms hold every lower order's as a prefix
        # (``texture_basis`` builds l = 2 up), so one partition serves all.
        top = texture_basis(group, orders[-1], cell)
        top_w = texture_term_weights([t.degree for t in top.terms], psi)
        raw_all = (top.at_reflections(refl.hkl, cell) * top_w[None, :]
                   if top.names else np.zeros((len(f), 0)))
        part_all = _partitioned(model, values, ip, raw_all)[live]
        rawl_all = raw_all[live]
        fits: list[_OrderFit] = []
        ss: dict[int, tuple[float, int]] = {}
        for order in orders:
            names = texture_basis(group, order, cell).names
            m = len(names)
            assert names == top.names[:m], (names, top.names)
            rawl, part = rawl_all[:, :m], part_all[:, :m]
            centred = rawl - ((wl @ rawl) / W)[None, :]
            norm = np.sqrt(wl @ centred ** 2)
            norm = np.where(norm > 0.0, norm, 1.0)
            pc = part - ((wl @ part) / W)[None, :]
            vis = np.sqrt(wl @ pc ** 2) / norm
            s, rank, b, a, kept, dropped = _weighted_fit(fl, wl, part, norm)
            c = b / a if a else np.full_like(b, nan)
            dp_k = rawl @ c if c.size else np.zeros(len(fl))
            ss[order] = (s, rank)
            fits.append(_OrderFit(
                order=order, n_terms=m, rank=rank,
                r2=(1.0 - s / base) if base > 0 else 0.0, names=names,
                visibility=tuple(float(v) for v in vis),
                coefficients=tuple(float(v) for v in c),
                rms_p=float(np.sqrt((wl * dp_k ** 2).sum() / W)),
                min_kept_sv=kept, max_dropped_sv=dropped))
        axis_r = axis_r2 = None
        ss_axis = nan
        if scored and base > 0:
            members, seg, counts = orbit_layout(reflection_orbits(group, refl.hkl))
            cos2 = cos2_alpha(members, np.array(tex.best_axis, dtype=np.int64),
                              reciprocal_metric_tensor(*cell))
            w_live = np.where(live, w, 0.0)

            def axis_ss(log_r: float) -> float:
                # _score_axis's free-scale SS at one r, a negative scale inadmissible
                p = np.bincount(seg, weights=march_term(cos2, float(np.exp(log_r))),
                                minlength=len(counts)) / counts
                denom = float((w_live * p * p).sum())
                scale = float((w_live * f * p).sum()) / denom if denom > 0.0 else 0.0
                if scale <= 0.0:
                    return base
                return min(float((w_live * (f - scale * p) ** 2).sum()), base)

            step = float(np.log(_R_GRID[1] / _R_GRID[0]))
            lo_r = float(np.log(tex.march_coefficient))
            bounds = (max(lo_r - step, float(np.log(_R_GRID[0]))),
                      min(lo_r + step, float(np.log(_R_GRID[-1]))))
            polished = minimize_scalar(axis_ss, bounds=bounds, method="bounded",
                                       options={"xatol": 1e-10})
            ss_axis, log_r = min((axis_ss(lo_r), lo_r),
                                 (float(polished.fun), float(polished.x)))
            axis_r, axis_r2 = float(np.exp(log_r)), 1.0 - ss_axis / base
        steps: list[_OrderStep] = []
        lo_ss, lo_rank = base, 0
        log_n = float(np.log(n))
        for order in orders:
            hi_ss, hi_rank = ss[order]
            dp = hi_rank - lo_rank
            dof = n - 1 - hi_rank
            if dp > 0 and dof > 0 and hi_ss > 0:
                fs = ((lo_ss - hi_ss) / dp) / (hi_ss / dof)
                pv = float(f_dist.sf(fs, dp, dof))
            else:
                fs, pv = nan, nan
            dbic = (n * float(np.log(hi_ss / lo_ss)) + dp * log_n
                    if hi_ss > 0 and lo_ss > 0 else nan)
            dbic_axis = (n * float(np.log(hi_ss / ss_axis)) + (hi_rank - 1) * log_n
                         if hi_ss > 0 and ss_axis > 0 else nan)
            steps.append(_OrderStep(
                order=order, added_rank=dp,
                delta_r2=(lo_ss - hi_ss) / base if base > 0 else 0.0,
                f_stat=float(fs), p_value=pv, delta_bic=dbic,
                delta_bic_vs_axis=dbic_axis))
            lo_ss, lo_rank = hi_ss, hi_rank
        out.append(_OrderScreen(
            phase_index=ip, n_reflections_used=n,
            n_effective=W * W / float((wl * wl).sum()),
            axis=tex.best_axis if scored else None, axis_r=axis_r, axis_r2=axis_r2,
            fits=tuple(fits), steps=tuple(steps)))
    return out
