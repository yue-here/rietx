"""Where an improvement lives: the cumulative Δχ² between two fits, and its
share on the reflections a symmetry-lowering splits (WP-1339, issue #219).

Two functions, both over **two results on one pattern**, both evidence and
neither a verdict:

* :func:`cumulative_delta_chi2` — Σ_{2θ′ ≤ 2θ}(δ²_b − δ²_a) against 2θ, with
  its breakdown over equal-count 2θ quantiles.  The statistic ``rietx
  compare`` draws as its Δχ² panel; the per-fit half, :func:`cumulative_chi2`,
  is what :func:`rietx.viz.compare.run` stores on each record, so the page
  and this function share one authority.
* :func:`split_localisation` — for a nested pair, a higher-symmetry fit and a
  lower-symmetry one, which of the higher model's reflections the lower one
  **splits**, and what share of the total Δχ² lands on them against what
  share of the points they cover.

The principle is ``viz.compare``'s: a correction that improves Rwp by rising
sharply somewhere and falling elsewhere is absorbing something, not
modelling it.  A real distortion concentrates its advantage on the split
reflections, because that is the only place the added degree of freedom acts
on the profile directly.  Issue #219 (a laboratory pattern fitted cubic and rhombohedral, the richer
model winning every global statistic) is the case that made it a function: no
global statistic sees where the gain landed.

**No threshold and no** ``Diagnostic`` (decided 2026-09-03, WP-1339).  How
concentrated is concentrated enough depends on the profile, the range and the
counting statistics; the package reports the share and the reflections behind
it, and the reader judges.  The coexistence case (a second phase on the
parent, the 2026-09-04 comment on #219) transfers weakly, by degree and not by
sign, and is not what this measures.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import RefinementResult
from .schemas import DeltaChi2Profile, DeltaChi2Quantile, SplitFamily, SplitLocalisation

#: Two child reflections closer than this in 2θ (degrees) are one position:
#: the family is not split.  Far below any resolvable splitting and far above
#: the float noise in two ticks computed from one cell.
SPLIT_TOLERANCE_DEG = 1e-6


def weighted_residual(result: RefinementResult) -> np.ndarray:
    """(y_obs − y_calc)/σ on the fitted channels, σ from :meth:`RefinementResult.sig`."""
    return ((np.asarray(result.y_obs, dtype=np.float64)
             - np.asarray(result.y_calc, dtype=np.float64)) / result.sig())


def cumulative_chi2(result: RefinementResult) -> np.ndarray:
    """Σ_{2θ′ ≤ 2θ} δ² over the fitted channels, every channel, no decimation.

    One fit's half of :func:`cumulative_delta_chi2`, and what
    :class:`rietx.viz.compare.RunRecord` stores, so the page can re-reference
    by subtraction without a round trip.
    """
    return np.cumsum(weighted_residual(result) ** 2)


def _same_pattern(a: RefinementResult, b: RefinementResult) -> None:
    """Refuse two results that are not two models of one pattern's channels.

    Same grid, same intensities **and the same σ**: each δ is divided by its
    own fit's :meth:`~RefinementResult.sig`, which depends on the declared
    model (a measured background widens it at compile, WP-1309).
    """
    if not a.two_theta:
        raise ValueError("the results carry no curves")
    if len(a.two_theta) != len(b.two_theta) or not np.array_equal(
            np.asarray(a.two_theta), np.asarray(b.two_theta)):
        raise ValueError(
            f"the fits saw {len(a.two_theta)} and {len(b.two_theta)} channels "
            "on different 2θ grids; a Δχ² by channel needs one pattern fitted "
            "over the same limits and exclusions")
    if not np.array_equal(np.asarray(a.y_obs), np.asarray(b.y_obs)):
        raise ValueError(
            "the fits saw different intensities; a Δχ² by channel compares two "
            "models of one pattern")
    if not np.array_equal(np.asarray(a.sig()), np.asarray(b.sig())):
        raise ValueError(
            "the fits weight the channels differently (σ depends on the declared "
            "model, a measured background widening it at compile); a Δχ² by "
            "channel would then carry 1/σ_b² − 1/σ_a² no model change produced")


def cumulative_delta_chi2(result_a: RefinementResult, result_b: RefinementResult,
                          *, n_quantiles: int = 10) -> DeltaChi2Profile:
    """Where ``result_b`` gains or loses against ``result_a``, channel by channel.

    ``cumulative`` is Σ_{2θ′ ≤ 2θ}(δ²_b − δ²_a), δ = (y_obs − y_calc)/σ with
    each fit's own σ, so a *falling* stretch is ``b`` fitting better there, a
    rising one ``b`` fitting worse, a flat one neither — the convention of
    ``rietx compare``'s panel, whose curve is this with ``a`` the reference.
    ``quantiles`` cuts the channels into ``n_quantiles`` runs of equal count
    in 2θ order and gives each run's Δχ² and its share of the total.

    The share is a ratio of two sums of one sign convention, so a positive
    share is a run moving the same way as the whole and a negative share is a
    run moving against it.  When the total is near zero the shares are not
    informative; ``total`` rides beside them for that reason.

    Raises :class:`ValueError` unless both results hold the same channels
    and the same intensities: fit both over the same limits and exclusions.
    """
    _same_pattern(result_a, result_b)
    if n_quantiles < 1:
        raise ValueError("n_quantiles must be at least 1")
    tt = np.asarray(result_a.two_theta, dtype=np.float64)
    step = weighted_residual(result_b) ** 2 - weighted_residual(result_a) ** 2
    cumulative = np.cumsum(step)
    total = float(cumulative[-1])
    rows = []
    for chunk in np.array_split(np.arange(len(tt)), min(n_quantiles, len(tt))):
        d = float(step[chunk].sum())
        rows.append(DeltaChi2Quantile(
            two_theta_min=float(tt[chunk[0]]), two_theta_max=float(tt[chunk[-1]]),
            n_points=len(chunk), delta_chi2=d,
            share=d / total if total != 0.0 else None))
    return DeltaChi2Profile(two_theta=tt.tolist(), cumulative=cumulative.tolist(),
                            total=total, n_points=len(tt), quantiles=rows)


def _phase_key(result: RefinementResult, phase: str | None, which: str) -> str:
    """The ticks key of the phase to read, or a refusal naming the choices."""
    keys = [k for k in result.tick_hkl if result.ticks.get(k)]
    if phase is not None:
        if phase not in keys:
            raise ValueError(f"the {which} result has no indexed ticks for "
                             f"phase {phase!r}; it has {keys}")
        return phase
    if len(keys) != 1:
        raise ValueError(f"the {which} result has indexed ticks for {keys}; "
                         f"name the phase to compare with {which}_phase=")
    return keys[0]


def _local_fwhm(tt: np.ndarray, bragg: np.ndarray, at: float) -> float | None:
    """The full width at half maximum of ``bragg`` about the channel nearest ``at``.

    Walks out each side to the half-maximum crossing, stopping early at a
    local minimum so a neighbouring peak cannot widen it.  ``None`` when the
    curve carries nothing there.
    """
    i = int(np.clip(np.searchsorted(tt, at), 0, len(tt) - 1))
    if i > 0 and abs(tt[i - 1] - at) < abs(tt[i] - at):
        i -= 1
    top = bragg[i]
    if not np.isfinite(top) or top <= 0.0:
        return None
    lo = i
    while lo > 0 and bragg[lo - 1] > top / 2.0 and bragg[lo - 1] <= bragg[lo] * (1 + 1e-12):
        lo -= 1
    hi = i
    while (hi < len(tt) - 1 and bragg[hi + 1] > top / 2.0
           and bragg[hi + 1] <= bragg[hi] * (1 + 1e-12)):
        hi += 1
    width = float(tt[min(hi + 1, len(tt) - 1)] - tt[max(lo - 1, 0)])
    return width if width > 0.0 else None


def _emission_rank(hkl: list[list[int]]) -> list[int]:
    """Which emission line each tick is, as its rank among the ticks of one hkl.

    ``ticks`` holds every emission line's image of a reflection, sorted by
    position, and ``tick_hkl`` names the same orbit representative once per
    line, so the *k*-th tick of one hkl in position order is the *k*-th
    shortest wavelength's image of it (a longer wavelength diffracts at a
    higher 2θ).  Two fits of one pattern share their emission lines, so
    the rank is the line's identity across them.  A single line gives all
    zeros.  A line whose image falls off the 2θ axis for one reflection
    shifts the ranks of that reflection's later lines, which is the one case
    this cannot see.
    """
    seen: dict[tuple[int, ...], int] = {}
    out = []
    for h in hkl:
        key = tuple(h)
        out.append(seen.get(key, 0))
        seen[key] = out[-1] + 1
    return out


def _position_groups(tt: np.ndarray, line: list[int]) -> list[list[int]]:
    """Indices of ticks sharing one emission line and one 2θ, one group per position.

    A position is not a key (333 and 511 of a cubic parent coincide), so
    coincident reflections form one group rather than the first of them
    claiming every child tick.
    """
    groups: list[list[int]] = []
    for ln in sorted(set(line)):
        idx = [i for i in np.argsort(tt, kind="stable") if line[i] == ln]
        for i in idx:
            if groups and line[groups[-1][0]] == ln and (
                    tt[i] - tt[groups[-1][0]] <= SPLIT_TOLERANCE_DEG):
                groups[-1].append(int(i))
            else:
                groups.append([int(i)])
    return groups


def split_localisation(higher: RefinementResult, lower: RefinementResult, *,
                       higher_phase: str | None = None,
                       lower_phase: str | None = None,
                       half_width: float | None = None) -> SplitLocalisation:
    """Share of the Δχ² on the reflections ``lower`` splits, against their share of points.

    ``higher`` and ``lower`` are two fits of one pattern, the second a
    symmetry-lowering of the first (cubic and rhombohedral, say), each given
    the same treatment otherwise.  Each of ``lower``'s reflection ticks is
    assigned to the nearest of ``higher``'s (same line), so the pair needs no
    transformation matrix and the two may be in different settings.  A
    ``higher`` reflection is **split** when the ticks assigned to it sit at
    more than one position (:data:`SPLIT_TOLERANCE_DEG`) at ``lower``'s
    refined cell.  This is the pseudo-symmetric case the question is about:
    the distortion moves a reflection by less than the gap to its neighbour.
    A ``lower`` tick farther than two local widths from every ``higher``
    one has no parent here (a superstructure reflection) and is counted in
    ``n_unmatched``, not windowed.  A family straddling an end of the range
    is reported whichever side its parent falls.  Its split is read off every
    child, and its window is anchored on the children inside the range (on
    the parent when none is), so it always covers data; a padded window may
    still reach past the range, and ``n_points`` counts only channels in it.

    Each family's window runs from its lowest assigned tick to its highest,
    widened by ``half_width`` degrees each side, or, by default, by the full
    width at half maximum of ``higher``'s own Bragg curve (y_calc − y_bkg)
    at that reflection.  Points in any split family's window are **split**,
    the rest of the windowed points **unsplit**, and the remainder
    **elsewhere**.  Each class gets Δχ² = Σ(δ²_lower − δ²_higher) and its
    share of the total, so the shares sum to one; a split share well above
    the split point share is an improvement that lives where the distortion
    acts, and a split share at or below zero while the total favours
    ``lower`` is the absorption issue #219 measured.

    Matching is **within one emission line** (the *k*-th line's children to
    the *k*-th line's parents, :func:`_emission_rank`), and reflections of
    ``higher`` at one 2θ (333 and 511 of a cubic parent) share **one family**
    carrying every hkl there, so no reflection is reported as unsplit for want
    of a child nobody could assign to it.  One family row per position and
    emission line, so a doublet's reflection appears once per line.

    Raises :class:`ValueError` when the two results are not one pattern
    (:func:`cumulative_delta_chi2`'s rule) or a phase is ambiguous.
    """
    _same_pattern(higher, lower)
    kh = _phase_key(higher, higher_phase, "higher")
    kl = _phase_key(lower, lower_phase, "lower")
    tt = np.asarray(higher.two_theta, dtype=np.float64)
    step = weighted_residual(lower) ** 2 - weighted_residual(higher) ** 2
    total = float(step.sum())
    bragg = (np.asarray(higher.y_calc, dtype=np.float64)
             - np.asarray(higher.y_background, dtype=np.float64)
             if higher.y_background else np.asarray(higher.y_calc, dtype=np.float64))

    parent_tt = np.asarray(higher.ticks[kh], dtype=np.float64)
    child_tt = np.asarray(lower.ticks[kl], dtype=np.float64)
    parent_line = _emission_rank(higher.tick_hkl[kh])
    child_line = _emission_rank(lower.tick_hkl[kl])
    groups = _position_groups(parent_tt, parent_line)
    g_tt = np.array([parent_tt[g[0]] for g in groups], dtype=np.float64)
    g_line = np.array([parent_line[g[0]] for g in groups], dtype=int)
    inside = (g_tt >= tt[0]) & (g_tt <= tt[-1])
    widths = np.array([(_local_fwhm(tt, bragg, p) if ok else None) or np.nan
                       for p, ok in zip(g_tt, inside)], dtype=np.float64)
    fallback = float(np.nanmedian(widths)) if np.isfinite(widths).any() else 0.0
    widths = np.where(np.isfinite(widths), widths, fallback)

    def in_data(x: float) -> bool:
        return bool(tt[0] <= x <= tt[-1])

    assigned: dict[int, list[float]] = {}
    n_unmatched = 0
    for c, line in zip(child_tt, child_line):
        # every child is assigned, in range or not, because a split is a fact
        # about the two models: a family straddling an end of the range keeps
        # both its children; only an in-range one anchors its window
        in_range = in_data(c)
        # one emission line against the same line: a Kα2 child belongs to a
        # Kα2 parent, never to the Kα1 tick 0.1° away
        same = np.flatnonzero(g_line == line)
        if not len(same):
            n_unmatched += in_range
            continue
        j = int(same[np.argmin(np.abs(g_tt[same] - c))])
        if abs(c - g_tt[j]) > 2.0 * max(widths[j], SPLIT_TOLERANCE_DEG):
            n_unmatched += in_range
            continue
        assigned.setdefault(j, []).append(float(c))

    split_mask = np.zeros(len(tt), dtype=bool)
    unsplit_mask = np.zeros(len(tt), dtype=bool)
    families = []
    for j in np.argsort(g_tt, kind="stable"):
        kids = sorted(assigned.get(int(j), []))
        seen = [k for k in kids if in_data(k)]
        # a parent just past an end of the range still owns its in-range
        # children; skipping it counted them nowhere (#904's review)
        if not inside[j] and not seen:
            continue
        spread = (kids[-1] - kids[0]) if kids else 0.0
        splits = spread > SPLIT_TOLERANCE_DEG
        pad = widths[j] if half_width is None else float(half_width)
        # anchored on what the data can show: the in-range children, else the
        # parent, so no family is windowed wholly past the range
        anchors = seen or [float(g_tt[j])]
        lo = anchors[0] - pad
        hi = anchors[-1] + pad
        w = (tt >= lo) & (tt <= hi)
        (split_mask if splits else unsplit_mask)[w] = True
        d = float(step[w].sum())
        families.append(SplitFamily(
            hkls=[list(higher.tick_hkl[kh][i]) for i in groups[j]],
            emission_line=int(g_line[j]), two_theta=float(g_tt[j]),
            n_assigned=len(kids), spread=float(spread), splits=bool(splits),
            window=(float(lo), float(hi)), n_points=int(w.sum()), delta_chi2=d,
            share=d / total if total != 0.0 else None))
    unsplit_mask &= ~split_mask
    elsewhere = ~(split_mask | unsplit_mask)

    def share(mask):
        return (float(step[mask].sum()) / total) if total != 0.0 else None

    n = len(tt)
    return SplitLocalisation(
        higher_phase=kh, lower_phase=kl, n_points=n, total=total,
        n_split_families=sum(f.splits for f in families),
        split_delta_chi2=float(step[split_mask].sum()),
        split_share=share(split_mask) if split_mask.any() else None,
        split_point_share=float(split_mask.mean()),
        unsplit_share=share(unsplit_mask),
        unsplit_point_share=float(unsplit_mask.mean()),
        elsewhere_share=share(elsewhere),
        elsewhere_point_share=float(elsewhere.mean()),
        n_unmatched=n_unmatched, families=families)
