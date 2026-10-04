"""The width profile behind :meth:`rietx.refine.Refinement.profile_fraction`.

A weight fraction rides on its phase's scale, W_p = S_p·ZMV_p / Σ S_q·ZMV_q
(Hill & Howard, 1987, J. Appl. Cryst. 20, 467), and its esd is the curvature
of χ² at the converged point propagated through that ratio.  That curvature
describes one basin.  A trace phase's scale trades against its width: broaden
it far enough and its peaks become a hump the background shares, after which
the scale can grow at almost no χ² cost.  The surface along that ridge can
hold several basins at one χ², each with ordinary curvature and a tight esd,
and no converged-point quantity can see past the one the fit reached (issue
#203; ``tests/test_qpa_multimodal.py`` builds the synthetic twin).

**The axis is the phase's width, never its scale** (WP-1320's decision).
Profiling the scale directly is the textbook object, and #203's own design
proposed it, but a refit at a pinned scale reaches the hump basin only by
broadening the phase until it is no longer significant by
``PHASE_SUPPORT_SIGMA``, which is exactly when WP-1301's collapse rule restores
and holds the phase's structure: measured on the fixture under the
pre-WP-1523 strongest-point test, the width was held at 4× and 8× the fitted
scale and χ² ran away.  At a pinned width the rest of
the problem is close to linear in the scale, the refit has one answer, and
the ridge is traversed rather than jumped.  So every free isotropic width term
of the phase is an axis, each pinned in turn on its own branch.

**Admissibility is the profile-likelihood cut, calibrated as the esds are**:
Δχ² ≤ :data:`~rietx.schemas.fraction.FRACTION_PROFILE_DCHI2` × χ²_red × f²
against the lowest χ² found, f the fit's Bérar-Lelann factor (Bérar &
Lelann, 1991, J. Appl. Cryst. 24, 1;
:func:`~rietx.optimize.statistics.berar_lelann_factor`).  A pinned refit is
the constrained hypothesis of Hamilton's test with one constraint (Hamilton,
1965, Acta Cryst. 18, 502), whose statistic is asymptotically χ²₁, and 3.84
is that distribution's 95 % point; the manual's eq. ``est-profile``.  Every admissible
point's fraction lies in the 95 % profile set for W, so the range is an inner
bound on it.  The χ² is the data's own Σ w·Δ², the quantity that calibration
is about; penalty rows (a P-spline's, restraints) are not in it.

**Read-only by construction**: every refit runs on a branch (or on a copy of
the models where the caller disabled history), with ``telemetry=False``
because the package discards these fits and a caller reads only the profile
(root CLAUDE.md, "an internal trial passes ``telemetry=False``").
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.fraction import (
    FRACTION_PROFILE_DCHI2,
    FRACTION_PROFILE_EXCESS,
    FRACTION_PROFILE_FWHM_MIN,
    FRACTION_PROFILE_N_FWHM,
    FractionProfile,
    FractionProfilePoint,
)
from .staged import Stage

#: The phase's isotropic width terms, in the order a default profile scans
#: them.  A Stephens block (``microstrain.dof.*``) is not an axis: it locks
#: ``lor_strain`` and has up to fifteen directions, so pinning one of them
#: pins no width.
WIDTH_TERMS = ("lor_strain", "lor_size", "gauss_strain", "gauss_size")


def width_value(term: str, fwhm: float, theta_deg: float) -> float:
    """The value of width term ``term`` contributing ``fwhm`` (deg 2θ) at θ.

    Inverts ``model.profiles.caglioti``: the Lorentzian terms add FWHM
    (``lor_size/cosθ``, ``lor_strain·tanθ``), the Gaussian ones add FWHM²
    (``gauss_size/cos²θ``, ``gauss_strain·tan²θ``).  ``theta_deg`` is θ, not
    2θ.  The laws are Scherrer size ∝ 1/cosθ and strain ∝ tanθ in the
    Thompson-Cox-Hastings split (Thompson, Cox & Hastings, 1987, J. Appl.
    Cryst. 20, 79), the Gaussian size term GSAS's ``P`` (Larson & Von Dreele,
    2004, GSAS manual).
    """
    th = math.radians(theta_deg)
    if term == "lor_strain":
        return fwhm / math.tan(th)
    if term == "lor_size":
        return fwhm * math.cos(th)
    if term == "gauss_strain":
        return (fwhm / math.tan(th)) ** 2
    if term == "gauss_size":
        return (fwhm * math.cos(th)) ** 2
    raise ValueError(f"{term!r} is not a width term; axes are {WIDTH_TERMS}")


def default_fwhm_grid(span_deg: float) -> list[float]:
    """0, then log-spaced from the grid minimum to half the fitted span."""
    top = 0.5 * span_deg
    if top <= FRACTION_PROFILE_FWHM_MIN:
        raise ValueError(f"a fitted range of {span_deg:g}° leaves no room for a "
                         "width profile")
    return [0.0, *(float(v) for v in np.geomspace(
        FRACTION_PROFILE_FWHM_MIN, top, FRACTION_PROFILE_N_FWHM))]


def data_chi2(statistics) -> float:
    """Σ w·Δ² over the data rows — ``Statistics.chi2`` is reduced."""
    return statistics.chi2 * max(statistics.n_points - statistics.n_free_parameters, 1)


def _phase_index(structure, phase: int | str) -> int:
    names = [p.name for p in structure.phases]
    if isinstance(phase, str):
        if phase not in names:
            raise ValueError(f"no phase named {phase!r}; the phases are {names}")
        return names.index(phase)
    if not 0 <= phase < len(names):
        raise ValueError(f"phase index {phase} is out of range for {len(names)} "
                         "phases")
    return int(phase)


def _default_axes(refinement, index: int) -> list[str]:
    free = set(refinement._free_paths)
    axes = [f"phases.{index}.{t}" for t in WIDTH_TERMS
            if f"phases.{index}.{t}" in free]
    if not axes:
        name = refinement.structure.phases[index].name
        raise ValueError(
            f"no width term of {name!r} is free in the last fit, so there is no "
            "scale-width ridge for the fit to have wandered along; name one with "
            f"axes= (e.g. 'phases.{index}.lor_strain') to profile it anyway")
    return axes


def profile_fraction(refinement, data, phase: int | str, *,
                     axes: Sequence[str] | None = None,
                     fwhm: Sequence[float] | None = None) -> FractionProfile:
    """Pin each width axis of ``phase`` on a grid, refit warm, read W and χ².

    See :meth:`rietx.refine.Refinement.profile_fraction`, which is this.
    """
    result = refinement.result_
    if result is None:
        raise RuntimeError("run a fit before profiling a fraction")
    if result.mode != "rietveld":
        raise ValueError(f"a weight fraction needs refined scales, and a "
                         f"{result.mode!r} fit has none")
    if result.qpa is None or len(result.qpa.phases) < 2:
        raise ValueError("a fraction needs two phases: one phase is 100 % by "
                         "definition, and a result without QPA has none to profile")
    index = _phase_index(refinement.structure, phase)
    if axes is None:
        axes = _default_axes(refinement, index)
    else:
        axes = list(axes)
        prefix = f"phases.{index}."
        for axis in axes:
            if not axis.startswith(prefix) or axis[len(prefix):] not in WIDTH_TERMS:
                raise ValueError(f"{axis!r} is not a width term of phase {index}; "
                                 f"axes are {prefix}{{{', '.join(WIDTH_TERMS)}}}")
    # an axis ``set_values`` would refuse at every grid point is refused here:
    # caught per point, it left no point measured and the profile read as a
    # silent confirmation of the esd
    entries = {e.path: e for e in refinement._working_table().entries}
    for axis in axes:
        e = entries.get(axis)
        if e is not None and (e.locked or e.tie is not None):
            why = ("structurally fixed (a Stephens block owns lor_strain, or "
                   "symmetry)" if e.locked else "tied to another parameter")
            raise ValueError(f"{axis!r} is {why}, so it cannot be pinned on a "
                             "grid; profile a width term the phase owns")

    tt = np.asarray(result.two_theta, dtype=np.float64)
    if not tt.size:
        raise ValueError("the last result carries no fitted 2θ grid, so there is "
                         "no range to place a width grid on")
    lo, hi = float(tt.min()), float(tt.max())
    theta_mid = 0.25 * (lo + hi)
    grid = default_fwhm_grid(hi - lo) if fwhm is None else [float(f) for f in fwhm]
    if not grid:
        raise ValueError("an empty FWHM grid measures nothing")
    if any(not (math.isfinite(f) and f >= 0.0) for f in grid):
        raise ValueError("a FWHM grid is finite and non-negative")
    grid = sorted(grid)      # ascending: each refit warm from a narrower width

    row = result.qpa.phases[index]
    stats = result.statistics
    inflation = stats.esd_inflation if stats.esd_inflation is not None else 1.0
    cut = FRACTION_PROFILE_DCHI2 * stats.chi2 * inflation ** 2
    chi2_fit = data_chi2(stats)

    # a branch shares the caller's tree, and every node it commits advances the
    # tree's HEAD — which a project reopens at as its working state — so the
    # head the caller stood on is put back however the scan ends
    tree = refinement.history
    head = tree.head if tree is not None else None
    points: list[FractionProfilePoint] = []
    try:
        for axis in axes:
            term = axis.rsplit(".", 1)[1]
            trial = refinement._trial()
            trial.set_vary([axis], False)
            for f in grid:
                value = width_value(term, f, theta_mid)
                point = dict(axis=axis, value=value, fwhm=f, admissible=False)
                try:
                    trial.set_values({axis: value})
                    r = trial.run_stage(data, Stage(f"profile:{axis}", []),
                                        telemetry=False)
                except Exception as exc:  # an unmeasurable point, not a crash
                    points.append(FractionProfilePoint(**point, error=str(exc)))
                    continue
                w = r.qpa.phases[index].weight_fraction if r.qpa is not None else None
                points.append(FractionProfilePoint(
                    **point, weight_fraction=w, chi2=data_chi2(r.statistics),
                    rwp=r.statistics.rwp,
                    error=None if w is not None else "no QPA at this point: the "
                    "refit left the scales unable to form fractions",
                    status=r.stages[-1].status if r.stages else r.status,
                    node_id=r.node_id))
    finally:
        if tree is not None and head is not None and tree.head != head:
            tree.set_head(head)

    measured = [p for p in points if p.chi2 is not None and p.weight_fraction is not None]
    if not measured:
        # nothing measured is no evidence either way; a range of the fit alone
        # would read as a profile that confirmed the esd
        errors = sorted({p.error for p in points if p.error})
        raise RuntimeError("no grid point of the width profile could be "
                           f"measured: {'; '.join(errors) or 'no fraction at any point'}")
    best = min([chi2_fit, *(p.chi2 for p in measured)])
    for p in measured:
        p.delta_chi2 = p.chi2 - best
        p.admissible = p.delta_chi2 <= cut
    fit_admissible = chi2_fit - best <= cut
    fractions = [p.weight_fraction for p in measured if p.admissible]
    if fit_admissible:
        fractions.append(row.weight_fraction)
    sigma = row.weight_fraction_stderr
    excess = None
    if sigma:
        half = math.sqrt(FRACTION_PROFILE_DCHI2) * sigma
        excess = max(abs(w - row.weight_fraction) for w in fractions) / half

    profile = FractionProfile(
        phase=row.name, phase_index=index, axes=list(axes),
        weight_fraction=row.weight_fraction, weight_fraction_stderr=sigma,
        chi2_fit=chi2_fit, chi2_best=best, delta_chi2_cut=cut,
        fit_admissible=fit_admissible, points=points,
        range_low=min(fractions), range_high=max(fractions), excess=excess)
    profile.diagnostics = fraction_diagnostics(profile)
    return profile


def fraction_diagnostics(profile: FractionProfile) -> list[Diagnostic]:
    """``QPA_FRACTION_UNDETERMINED`` when an admissible fraction is far outside the esd.

    Silent when ``excess`` is ``None``: without an esd the fit made no
    confident claim for the profile to contradict, and the range on the
    profile is the whole answer.
    """
    if profile.excess is None or profile.excess <= FRACTION_PROFILE_EXCESS:
        return []
    widths = sorted({p.fwhm for p in profile.points if p.admissible})
    ends = (f"{widths[0]:.3g}°" if len(widths) == 1
            else f"{widths[0]:.3g}° to {widths[-1]:.3g}°") if widths else "none"
    fit = ("" if profile.fit_admissible else
           f"; a pinned refit found χ² lower than the fit's by "
           f"{profile.chi2_fit - profile.chi2_best:.3g}, so the fit did not reach "
           "the lowest basin along this ridge")
    return [Diagnostic(
        level="warning", code="QPA_FRACTION_UNDETERMINED",
        where=[f"phases.{profile.phase_index}.scale", *profile.axes],
        value=profile.excess,
        message=(
            f"{profile.phase}'s weight fraction "
            f"{100 * profile.weight_fraction:.3g} % ± "
            f"{100 * profile.weight_fraction_stderr:.2g} % describes one basin: "
            f"pinning {', '.join(profile.axes)} and refitting admits fractions "
            f"from {100 * profile.range_low:.3g} % to "
            f"{100 * profile.range_high:.3g} % within Δχ² "
            f"{profile.delta_chi2_cut:.3g} of the lowest χ² (95 %, scaled by "
            f"χ²_red and the Bérar-Lelann factor), at FWHM {ends}; the farthest "
            f"is {profile.excess:.3g} times the esd's 95 % half-width{fit}"),
        suggestion=(
            "quote the range and the widths that produced it, never the point. "
            "Only information the fit lacks separates the basins: a width held "
            "at a value the specimen justifies, a background able to take the "
            "hump itself, or more counts on the phase's strongest lines"),
    )]
