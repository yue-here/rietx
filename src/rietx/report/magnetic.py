"""What the fit says about a moment, and what the powder could not see.

Three statements, per magnetic site, and each of them is a thing a moment
model can get wrong in a way Rwp does not show:

1. **The magnitude, with its esd.**  |m| is the refined modulus DOF, so it is
   a column of the least-squares problem and its esd comes from the same
   covariance every other parameter's does — Bérar-Lelann inflation included
   (``Statistics.esd_inflation`` divides it back out).  The crystal-axis
   components beside it are *derived*: they carry no esd, because the direction
   they encode is either undeterminable (in which case an esd would be a number
   about nothing) or determined, in which case the angle DOF carries it.

2. **The direction the powder cannot determine.**  A cubic collinear structure
   measures |m| and nothing about its direction; a uniaxial one measures the
   angle to the unique axis and nothing about the azimuth (Shirane, 1959,
   *Acta Cryst.* **12**, 282).  Those directions come back **held**, with the
   DOF named, rather than as a small number with a small esd.

3. **Which approximation is in force.**  f(s) = ⟨j₀⟩ for a spin-only 3d ion,
   f(s) = ⟨j₀⟩ + (2/g − 1)⟨j₂⟩ for a rare earth — the difference FullProf's
   table names apart as ``MHO3`` and ``JHO3`` for the same ion.  A report that
   does not say which one it used cannot be checked.

And the fourth statement, which is a refusal rather than a number: a moment
whose modulus sits at its floor is **unsupported**, not small.  |F_m|² ∝ m², so
the column vanishes with the moment; a paramagnetic pattern drives the modulus
to nothing and every direction flat with it, and the honest report of that is
"the data does not support a moment here", not "0.02(1) μ_B".
"""

from __future__ import annotations

import math

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.structure import MOMENT_FLOOR_MU_B
from .schemas import (
    MAGNETIC_WIDTH_MIN_REFLECTIONS,
    MAGNETIC_WIDTH_PURITY,
    MAGNETIC_WIDTH_SIGMA,
    MAGNETIC_WIDTH_TAIL_FWHM,
    MIN_COEF_SIGNIFICANCE,
    MOMENT_PAIR_RHO_MIN,
    MOMENT_SUPPORT_SIGMA,
    VALIDITY_RADIUS_FWHM,
    MomentEvidence,
)


def analyse_moments(model, values, structure=None, *,
                    held: list[str] | None = None,
                    esd: dict[str, float] | None = None,
                    correlations: list | None = None,
                    flat_axes: dict[str, list[float]] | None = None,
                    turned: list[str] | None = None,
                    ) -> list[MomentEvidence]:
    """One row per magnetic site of the compiled model, or an empty list.

    Empty is the honest state on three counts and none of them is "no moment
    was found": no compiled model was supplied, no phase declares one, or the
    histogram carries no magnetic term at all — an X-ray one, where it is
    identically zero and the moment was never observed.  The test is
    ``cp.magnetic``, the frozen block the compile attaches exactly when
    ``forward.magnetic_wanted`` says so, so this function needs no opinion
    about radiations of its own.

    **Nothing here reads the abscissa**: the
    modulus, its esd, the crystal-axis components, the approximation in force
    and the free and unmeasured directions are all functions of the moment
    DOFs, the cell and the operator list, and no field of a
    :class:`~rietx.report.schemas.MomentEvidence` names an angle or a flight
    time.  :func:`rietx.build_report` therefore calls this above its axis
    gate.

    ``correlations`` (Q5) is the fit's own worst-|ρ| list —
    ``RefinementResult.identifiability.top_correlations`` — the one place a
    completed fit's covariance survives past fit time (WP-1055/-1056; the raw
    Jacobian itself is never serialized).  Two rows whose ``dof0`` paths
    appear there with |ρ| >= :data:`~.schemas.MOMENT_PAIR_RHO_MIN` are a
    powder-degenerate pair (S2(a,b)-shaped: ``isotropy.determinable_amplitudes``
    would have called this the same rank deficiency, pre-fit, on the
    candidate's own amplitude Jacobian) — see :func:`_pair_degenerate_moments`.
    ``None`` (the default) leaves every row exactly as before Q5: a fit whose
    top-|ρ| list was not passed in, or that never measured one, reports each
    modulus on its own, which is the honest state when nothing said otherwise
    — never "these are not paired".

    ``flat_axes`` and ``turned`` are the last stage's
    ``StageResult.moment_flat_axes`` and ``.moment_turned`` (issue #599): the
    sites whose azimuth was held as a flat *combination* of two angles, with
    the axis, and which of them the fit turned onto that axis's meridian
    first.  The note for such a site is a projection of that record, so it
    says the moment was turned only where the fit says it turned it.
    ``None`` reads as "no such site", the state of every result stored
    before the fields.
    """
    if model is None:
        return []
    held_set = set(held or ())
    out: list[MomentEvidence] = []
    for ip, cp in enumerate(model.phases):
        msites = getattr(cp, "magnetic", None)
        if msites is None:
            continue
        phase_name = (structure.phases[ip].name if structure is not None
                      else f"phases.{ip}")
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        for j in range(msites.n_asym):
            if not msites.carries[j]:
                continue
            out.append(_row(model, values, ip, j, cp, msites, phase_name,
                            cell, held_set, structure, esd or {},
                            flat_axes or {}, set(turned or ())))
    if correlations:
        out = _pair_degenerate_moments(
            out, correlations, {r.path: float(values[r.path]) for r in out})
    return out


def _pair_degenerate_moments(rows: list[MomentEvidence], correlations: list,
                             signed: dict[str, float]) -> list[MomentEvidence]:
    """Q5: fold a powder-degenerate pair into one measured number.

    ``isotropy.analyse`` computes, pre-fit, how many of a candidate's free
    amplitudes a powder can determine at all (``determinable_amplitudes``'s
    SVD rank); when that count is short of the free count, two sites' moduli
    are not separately measured, only their combination is.  The signature of
    exactly that at *fit* time is |rho| -> 1 between the two ``dof0`` columns
    of the covariance — a rank-1 direction where 2 were free is what a
    correlation of 1 *is* — so ``correlations`` (the fit's own worst-|rho|
    list, the one place the covariance survives past fit time) is read
    instead of re-deriving the candidate.

    Only pairs (never a larger group: ``CorrelationPair`` is inherently
    two-wide, and "moment pair" is what WP-1327's own vocabulary for this
    names).  A row already claimed by an earlier, more strongly correlated
    pair is not claimed twice — the greedy match by |rho|, worst first, is
    what keeps this well-defined when more than one pair in a phase crosses
    the bar.

    ``signed`` is each row's **signed** modulus DOF, ``{path: dof0}``.  The
    esd is the linearised gᵀCg with g = ∂m/∂d = d/m, and ``rho`` is the
    correlation of the two *signed* columns, so g needs the signs too: two
    sites stated antiparallel (d_a = +2, d_b = −2) have their degenerate
    direction along (1, 1), ρ → +1, and a cross term of −σ² that cancels the
    diagonal.  ``MomentEvidence.magnitude`` is |dof0|, and building g from it
    flipped that cross term and reported √2·σ for a sum the data determines
    well (review of #433, finding 4).  Required rather than defaulted, so no
    caller can reach the unsigned form by leaving it out.
    """
    by_path = {r.path: i for i, r in enumerate(rows) if r.path}
    claimed: set[str] = set()
    updated = list(rows)
    ranked = sorted(
        (c for c in correlations
         if abs(getattr(c, "rho", 0.0)) >= MOMENT_PAIR_RHO_MIN
         and c.path_a in by_path and c.path_b in by_path),
        key=lambda c: -abs(c.rho))
    for c in ranked:
        if c.path_a in claimed or c.path_b in claimed:
            continue
        ia, ib = by_path[c.path_a], by_path[c.path_b]
        a, b = updated[ia], updated[ib]
        if a.magnitude_esd is None or b.magnitude_esd is None:
            continue
        d_a, d_b = signed[a.path], signed[b.path]
        m = math.sqrt(d_a ** 2 + d_b ** 2)
        if m <= 0.0:
            continue
        # rho belongs to (path_a, path_b); the rows are in that order here
        cov_ab = c.rho * a.magnitude_esd * b.magnitude_esd
        g_a, g_b = d_a / m, d_b / m
        var_m = (g_a ** 2 * a.magnitude_esd ** 2
                 + g_b ** 2 * b.magnitude_esd ** 2
                 + 2.0 * g_a * g_b * cov_ab)
        esd_m = math.sqrt(max(var_m, 0.0))
        note = (f"not separately determined: this modulus and {b.atom}'s "
                f"({b.path}) are correlated at rho={c.rho:.3f} — the powder "
                f"measures their quadrature sum, sqrt(m_a^2 + m_b^2) = "
                f"{m:.3f} +/- {esd_m:.3f}, and not each on its own "
                f"(MOMENT_PAIR_DEGENERATE)")
        note_b = (f"not separately determined: this modulus and {a.atom}'s "
                  f"({a.path}) are correlated at rho={c.rho:.3f} — the powder "
                  f"measures their quadrature sum, sqrt(m_a^2 + m_b^2) = "
                  f"{m:.3f} +/- {esd_m:.3f}, and not each on its own "
                  f"(MOMENT_PAIR_DEGENERATE)")
        updated[ia] = a.model_copy(update={
            "paired_with": [b.path], "paired_magnitude": m,
            "paired_magnitude_esd": esd_m, "note": note})
        updated[ib] = b.model_copy(update={
            "paired_with": [a.path], "paired_magnitude": m,
            "paired_magnitude_esd": esd_m, "note": note_b})
        claimed.add(c.path_a)
        claimed.add(c.path_b)
    return updated


def moment_pair_diagnostics(rows: list[MomentEvidence]) -> list[Diagnostic]:
    """``MOMENT_PAIR_DEGENERATE`` (info), one per pair :func:`analyse_moments`
    folded (Q5) — never twice, and never for an ordinary row."""
    out: list[Diagnostic] = []
    seen: set[frozenset] = set()
    for r in rows:
        if not r.paired_with:
            continue
        pair = frozenset([r.path, *r.paired_with])
        if pair in seen or len(pair) != 2:
            continue
        seen.add(pair)
        other = next(p for p in r.paired_with)
        out.append(Diagnostic(
            level="info", code="MOMENT_PAIR_DEGENERATE",
            message=(f"{r.path} and {other} are a powder-degenerate moment "
                     f"pair. Only their quadrature sum is determined: "
                     f"sqrt(m_a^2 + m_b^2) = {r.paired_magnitude:.3f} +/- "
                     f"{r.paired_magnitude_esd:.3f}."),
            where=[r.path, other], value=r.paired_magnitude))
    return out


#: Why an interval side has no end, in the words the finding prints
#: (:data:`~rietx.schemas.interval.IntervalStop`).
_STOP_WORDS = {
    "period": "still inside the threshold half a turn away, so not determined",
    "refits": "its refit budget ran out",
    "error": "a refit failed",
}


def flagged_moduli(paths) -> list[str]:
    """The modulus of each site with an angle among ``paths``, in their order.

    A moment block's DOFs are ``…moment.dof0`` (the modulus) and
    ``…moment.dof1``/``dof2`` (the angles).  The one list the stationary
    finding and :func:`~rietx.strategy.parameter_interval.attach_stationary_intervals`
    read, so the moduli profiled are the moduli quoted (WP-2060).
    """
    return list(dict.fromkeys(_modulus_of(p) for p in paths))


def _modulus_of(path: str) -> str:
    """The modulus DOF of the moment block ``path`` belongs to."""
    return path.rsplit(".dof", 1)[0] + ".dof0"


def _missing_ends(interval) -> list[str]:
    """Each side of ``interval`` with no end, in the words the finding prints."""
    return [f"no {side} end ({_STOP_WORDS.get(stop, stop)})"
            for side, end, stop in (
                ("lower", interval.lower, interval.lower_stop),
                ("upper", interval.upper, interval.upper_stop)) if end is None]


def modulus_profile_withheld(interval) -> bool:
    """Whether a flagged site's modulus profile is withheld (WP-2060).

    Ruled by Mike on #1075 (2026-11-04, condition 2): a profile that found the
    data χ² below the fit is still quoted, unless the drop reaches the
    interval's own cut, ``delta_chi2_cut``.  Then the fit is not at its
    minimum, and an interval measured from it is not the modulus's
    uncertainty.  A drop under the cut changed little: such intervals covered
    the truth on 31 of 32 two-site fits.  Withheld, the reader gets the lowest
    point and the pointer to refit, never the esd (the 2026-11-05 amendment:
    near zero that esd covered 3 of 20).  A test of the magnetic path, never of
    :func:`~rietx.strategy.parameter_interval.profile_interval`, which every
    fit shares (condition 4).
    """
    return interval.chi2_fit - interval.chi2_lowest >= interval.delta_chi2_cut


def _lowest_point(interval):
    """The probe that reached ``interval.chi2_lowest``."""
    return min((p for p in interval.points if p.chi2 is not None),
               key=lambda p: p.chi2)


def _modulus_line(path: str, row, withheld) -> str | None:
    """A flagged site's modulus in the finding, or ``None`` without a profile.

    Quoted by its interval, withheld with the pointer to refit, and never by
    its esd, which assumes the angles sit on the direction (WP-2060).
    """
    if withheld is not None:
        low = _lowest_point(withheld)
        return (f" The profile of {path} found the data chi2 "
                f"{withheld.chi2_fit - withheld.chi2_lowest:.3g} below the fit, at "
                f"{low.value:.4g} μ_B, a full cut of {withheld.delta_chi2_cut:.3g} or "
                f"more. The fit did not reach its minimum, so no interval is quoted "
                f"for {path}, and its esd is not its uncertainty either. Refit with "
                f"it started at {low.value:.4g} μ_B before quoting it.")
    interval = row.interval if row is not None else None
    if interval is None:
        return None
    level = f"{100 * interval.level:g} %"
    if interval.lower is None or interval.upper is None:
        found = [f"its {side} end is {end:.4g} μ_B" for side, end in (
            ("lower", interval.lower), ("upper", interval.upper)) if end is not None]
        line = (f" {path} is {row.value:.4g} μ_B. Its {level} profile interval has "
                f"{' and '.join(_missing_ends(interval))}"
                + (f", and {found[0]}." if found else "."))
    else:
        # to three figures of the interval's width, so its ends read apart
        width = interval.upper - interval.lower
        places = max(0, 2 - math.floor(math.log10(width))) if width > 0.0 else 4
        line = (f" {path} is {row.value:.{places}f} μ_B, with the {level} profile "
                f"interval {interval.lower:.{places}f} to {interval.upper:.{places}f} μ_B.")
        # a modulus on 0 (or on a declared limit) is one-sided: that end is
        # the bound, not a measurement, so the other end reads as a limit
        bounded = [side for side, stop in (("lower", interval.lower_stop),
                                           ("upper", interval.upper_stop))
                   if stop == "bound"]
        if interval.one_sided and bounded:
            other = "upper" if bounded[0] == "lower" else "lower"
            line += (f" Its {bounded[0]} end is a bound, so the interval is "
                     f"one-sided: quote its {other} end as a limit.")
    if not interval.fit_is_minimum:
        line += (f" The profile found the data chi2 "
                 f"{interval.chi2_fit - interval.chi2_lowest:.3g} below the fit, under "
                 f"the cut of {interval.delta_chi2_cut:.3g}, so the interval is "
                 f"measured from the fit.")
    return line


def moment_angle_stationary_diagnostics(stage, parameters=None, *,
                                        withheld=None) -> list[Diagnostic]:
    """``MOMENT_ANGLE_STATIONARY`` (info): the moment angles a stage's
    covariance left out at a direction the symmetry fixes (WP-1929).

    Built from ``stage.moment_angle_tests``, the solve's own record, and never
    re-derived: the test needs the residual closure and the solve's stop, and
    the record is what survives the fit.  ``stage`` is the answer-producing
    stage, whose covariance every reported esd is read off.  Silent where no
    round passed, including where no test ran.  ``value`` is the passing
    round's statistic, and ``where`` its angles.

    ``parameters`` is the result's rows.  Each left-out angle is quoted with
    its distance from the direction, the fitted value against the round's
    ``stationary_at``, and with its profile interval where its row carries one
    (``RefinedParameter.interval``, WP-2002): the ends, and whether they
    include the direction.  An angle with no interval on its row says so,
    since a joint fit, an internal trial and a cancelled run compute none.

    **Each of these sites' moduli is quoted by its interval** (WP-2060, ruled
    by Mike on #1075).  Its esd assumes the angles sit on the direction, and
    the modulus printed is the moment's length at the tilt where the fit
    stopped, so the finding no longer tells a reader to quote the moment
    along the direction.  ``withheld`` maps a modulus to the profile
    :func:`modulus_profile_withheld` held back, which the finding quotes by
    its lowest point and a pointer to refit, never by the esd.  An angle on a
    site whose modulus is unsupported (:func:`moment_supported`) is not read
    as a direction: with no moment, an angle points nowhere the data see.
    """
    from ..optimize.least_squares import STATIONARY_ANGLE_LEVEL

    tests = getattr(stage, "moment_angle_tests", None) or []
    passed = next((t for t in tests if t.zeroed), None)
    if passed is None:
        return []
    withheld = withheld or {}
    k = len(passed.paths)
    kept = [p for p in dict.fromkeys(q for t in tests for q in t.paths)
            if p not in passed.paths]
    message = (
        f"{', '.join(passed.paths)} {'sits' if k == 1 else 'sit'} at a "
        f"direction the site symmetry fixes. Moving {'it' if k == 1 else 'them'} "
        f"onto that direction, the other parameters refitted, changes the data "
        f"chi2 by {passed.statistic:.3g} x chi2_red x f^2, within the cut of "
        f"{passed.cut:.3g} for {k} one-sided "
        f"{'direction' if k == 1 else 'directions'} at "
        f"{100 * STATIONARY_ANGLE_LEVEL:g} %. "
        f"{'Its column' if k == 1 else 'Their columns'} left the covariance, "
        f"so {'it carries' if k == 1 else 'they carry'} no esd. "
        f"The values are kept.")
    rows = {r.path: r for r in (parameters or [])}
    moduli = [m for m in flagged_moduli(passed.paths) if m in rows or m in withheld]
    unsupported = {m for m in moduli if m in rows
                   and moment_supported(abs(rows[m].value), rows[m].stderr) is False}
    without = []
    for path in passed.paths:
        row, at = rows.get(path), passed.stationary_at.get(path)
        if row is None or at is None:
            without.append(path)
            continue
        distance = row.value - at
        line = (f" {path} is {_rad(abs(distance))} rad "
                f"({abs(math.degrees(distance)):.2f} deg) from the direction "
                f"at {_rad(at)}.")
        interval = row.interval
        if interval is None:
            without.append(path)
        elif interval.lower is None or interval.upper is None:
            line += (f" Its {100 * interval.level:g} % profile interval has "
                     f"{' and '.join(_missing_ends(interval))}.")
        elif _modulus_of(path) in unsupported:
            # condition 1: no moment, so no direction to include or exclude
            line += (f" Its {100 * interval.level:g} % profile interval is "
                     f"{_rad(interval.lower)} to {_rad(interval.upper)}.")
        else:
            inside = interval.lower <= at <= interval.upper
            line += (f" Its {100 * interval.level:g} % profile interval, "
                     f"{_rad(interval.lower)} to {_rad(interval.upper)}, "
                     f"{'includes' if inside else 'excludes'} the direction.")
        message += line
    if unsupported:
        names = ", ".join(m for m in moduli if m in unsupported)
        message += (f" The data do not support the moment of {names} "
                    f"(MOMENT_UNSUPPORTED), so its angles give no direction.")
    # the moduli beside them (WP-2060, ruled by Mike on #1075): their esds
    # are read with these angle columns out, so they hold only if the angles
    # sit on the direction, and a weak one covered 0.82 at a nominal 0.95
    quoted = False
    unprofiled = []
    for m in moduli:
        line = _modulus_line(m, rows.get(m), withheld.get(m))
        if line is None:
            if rows[m].stderr is not None:
                unprofiled.append(m)
                # a tied modulus has no profile of its own: profile_interval
                # refuses it, so the pointer below would send a reader to a
                # call that raises
                if rows[m].vary:
                    without.append(m)
            continue
        quoted = quoted or m not in withheld
        message += line
    if quoted:
        message += (" A modulus keeps its esd, which assumes the angles sit on "
                    "the direction. Its interval does not assume it.")
    if unprofiled:
        message += (f" The esd of {', '.join(unprofiled)} assumes the angles sit "
                    f"on the direction.")
    if without:
        message += (f" No profile interval was computed for "
                    f"{', '.join(without)}. On a single fit, "
                    f"Refinement.profile_interval(data, path) computes one.")
    if kept:
        message += (f" Tested and kept with an esd, as determined: "
                    f"{', '.join(kept)}.")
    return [Diagnostic(
        level="info", code="MOMENT_ANGLE_STATIONARY", where=list(passed.paths),
        value=passed.statistic, message=message,
        suggestion=("Quote each of these angles by its profile interval "
                    "(RefinedParameter.interval), not by an esd. Where the "
                    "interval includes the symmetry direction, the data cannot "
                    "tell the moment from one along it. One angle tested alone "
                    "nearly always lands here, because it passed the test below "
                    "the interval's cut. Where an interval excludes the "
                    "direction, the data measure that tilt, so quote the angle "
                    "with its interval. Quote each of these sites' moduli by "
                    "its interval too, not by its esd. Where the message "
                    "withholds a modulus's interval, refit from the value it "
                    "gives before quoting the modulus. A modulus with no "
                    "interval on a single fit gets one from "
                    "Refinement.profile_interval(data, path)."))]


def moment_supported(modulus: float, sigma: float | None) -> bool | None:
    """Whether the data support a moment of this modulus (WP-1327).

    ``False`` at :data:`~rietx.schemas.structure.MOMENT_FLOOR_MU_B` or under
    :data:`~rietx.report.schemas.MOMENT_SUPPORT_SIGMA` times the esd, ``None``
    without an esd.  The one authority for
    :attr:`~rietx.report.schemas.MomentEvidence.supported` and for
    ``MOMENT_UNSUPPORTED`` (WP-2060), so the report and the result cannot
    disagree about a site.
    """
    if sigma is None:
        return None
    return not (modulus <= MOMENT_FLOOR_MU_B or modulus <= MOMENT_SUPPORT_SIGMA * sigma)


def moment_unsupported_diagnostics(parameters) -> list[Diagnostic]:
    """``MOMENT_UNSUPPORTED`` (warning): the moduli the data do not support (WP-2060).

    The same verdict as the FitReport's moment rows (:func:`moment_supported`),
    on the result, where a caller reading only ``result.diagnostics`` sees it.
    The magnetic intensity goes as m², so the modulus's column vanishes at
    m = 0, and the linearisation an esd rests on fails near it (Hamilton,
    1965, Acta Cryst. 18, 502): issue #1075 measured value ± 1.96 esd
    covering a zero moment 74.5 % of the time at a nominal 95 %, and esds of
    1e4-1e6 μ_B on the fits that ended on m = 0.  ``where`` is the moduli,
    ``value`` the smallest |m|/esd among them.  Silent where every free
    modulus is supported, and where none has an esd.
    """
    rows = [r for r in parameters
            if r.path.endswith(".moment.dof0")
            and moment_supported(abs(r.value), r.stderr) is False]
    if not rows:
        return []
    parts = []
    for r in rows:
        modulus = abs(r.value)
        why = (f"at the floor of {MOMENT_FLOOR_MU_B:g} μ_B" if modulus <= MOMENT_FLOOR_MU_B
               else f"{modulus / r.stderr:.2g}× its esd")
        parts.append(f"{r.path} is {r.value:.3g} ± {r.stderr:.3g} μ_B, {why}")
    return [Diagnostic(
        level="warning", code="MOMENT_UNSUPPORTED", where=[r.path for r in rows],
        value=min((abs(r.value) / r.stderr for r in rows if r.stderr > 0.0), default=None),
        message=(f"{'; '.join(parts)}. The data do not support "
                 f"{'this moment' if len(rows) == 1 else 'these moments'}: under "
                 f"{MOMENT_SUPPORT_SIGMA:g} esd or at the floor. The magnetic "
                 f"intensity goes as m², so where the moment's sign changes no "
                 f"intensity its column vanishes at m = 0, and near it the esd "
                 f"is no interval."),
        suggestion=("Read the moment as unsupported, not as a small moment. For "
                    "a limit, Refinement.profile_interval(data, path) gives the "
                    "modulus's likelihood interval, which stays at m ≥ 0 where "
                    "the data cannot see the moment's sign."))]


def _rad(x: float) -> str:
    """An angle in radians to four decimals, with no negative zero."""
    return f"{round(x, 4) + 0.0:.4f}"


def _row(model, values, ip, j, cp, msites, phase_name, cell, held_set,
         structure, esd, flat_axes, turned) -> MomentEvidence:
    from ..crystallography.magnetic.moments import (
        DOF_NAMES,
        moment_from_dofs,
        unit_metric,
    )
    from ..crystallography.magnetic.operators import moment_magnitude

    site = f"phases.{ip}.atoms.{j}"
    base = f"{site}.moment"
    n = msites.n_dofs(j)
    dofs = np.array([values[f"{base}.dof{k}"] for k in range(n)])
    components = moment_from_dofs(msites.frames[j], dofs)
    modulus = abs(float(dofs[0])) if n else 0.0
    names = DOF_NAMES[n]
    unmeasured = [names[k] for k in range(1, n) if f"{base}.dof{k}" in held_set]
    label = (structure.phases[ip].atoms[j].label if structure is not None
             else f"atoms.{j}")
    sigma = esd.get(f"{base}.dof0")
    at_floor = modulus <= MOMENT_FLOOR_MU_B
    # ``None`` where there is no esd: the modulus was stated and held, or it
    # left the covariance as unmeasured, and in neither case did anything test
    # it — the honest empty state, which a defaulted ``True`` read as an
    # answer (review of #433, finding 5; WP-1076's first shape)
    supported = moment_supported(modulus, sigma)
    note = ""
    if supported is None:
        note = ("the modulus has no esd — it was stated and held, or the fit "
                "left it out of the covariance as unmeasured — so whether the "
                "data supports a moment here was not tested")
    elif not supported:
        # the reason is quoted, because the two are different readings: a
        # modulus driven to the floor is a fit that removed the magnetic
        # intensity outright, while one that is merely inside its own esd is
        # a fit that could not tell it from none.  Both are "unsupported";
        # only the second has a ratio worth printing.
        why = (f"is at its floor ({MOMENT_FLOOR_MU_B:g} μ_B)" if at_floor
               else f"is {modulus:.3g} μ_B, only {modulus / sigma:.2g}× its "
                    f"own esd of {sigma:.3g}")
        note = (f"the modulus {why}: |F_m|² is proportional to m², so a "
                f"moment the data cannot see is a flat direction of the "
                f"least-squares problem and the fit leaves it at nothing. "
                f"Read this as unsupported, not as a small moment")
    elif unmeasured and f"{base}.dof2" in held_set and site in flat_axes:
        # #599: the flat rotation was a combination of the two angles.  Read
        # off the stage's own record (review of #624, item 2), never probed
        # again here: whether the moment was turned is a fact about the fit,
        # and only the turned case makes the polar esd an esd of the angle
        # to the axis.
        u = np.asarray(flat_axes[site], dtype=np.float64)
        shown = u / float(u[int(np.argmax(np.abs(u)))])
        g = unit_metric(cell)
        m = np.asarray(components, dtype=np.float64)
        denom = math.sqrt(max(float(u @ g @ u) * float(m @ g @ m), 0.0))
        psi = (math.degrees(math.acos(min(abs(float(u @ g @ m)) / denom, 1.0)))
               if denom > 0.0 else float("nan"))
        axis_text = (f"the rotation of the moment about "
                     f"[{', '.join(f'{c:.3g}' for c in shown)}] (crystal "
                     f"axes) on this site, which this frame splits across "
                     f"polar and azimuth")
        if site in turned:
            note = (f"the powder average does not determine {axis_text}; the "
                    f"moment was turned about that axis — a move the data "
                    f"cannot see — until the rotation is the azimuth, which "
                    f"is held; the polar angle now moves the moment straight "
                    f"towards or away from the axis, so its esd is the esd of "
                    f"the angle to it ({psi:.2f}°), and the direction "
                    f"reported is one of a cone of equally good ones")
        else:
            note = (f"the powder average does not determine {axis_text}; the "
                    f"azimuth is held where the stage found it, because "
                    f"turning the moment about the axis did not reproduce the "
                    f"pattern to the flat-direction floor, so the polar "
                    f"angle's esd is *not* the esd of the angle to the axis "
                    f"({psi:.2f}° at the answer)")
    elif unmeasured:
        note = (f"the powder average does not determine "
                f"{', '.join(unmeasured)} on this site; "
                f"{'it is' if len(unmeasured) == 1 else 'they are'} held, and "
                f"the direction reported is the one it was stated with")
    return MomentEvidence(
        phase=phase_name, atom=label, ion=msites.ions[j] or "",
        path=f"{base}.dof0",
        magnitude=modulus, magnitude_esd=sigma,
        magnitude_from_components=float(moment_magnitude(components, cell)),
        crystalaxis=[float(c) for c in components],
        approximation=msites.approximations[j] or "",
        free_directions=list(names[1:]),
        unmeasured_directions=unmeasured,
        supported=supported,
        note=note,
    )


# ---------------------------------------------------------------------------
# WP-1343 — the magnetic peaks are broader and nothing said so
# ---------------------------------------------------------------------------
def _magnetic_fraction(model, values, ip: int):
    """(⟨|F_N|²⟩, p²⟨|F_⊥|²⟩, magnetic fraction) per reflection of phase ``ip``.

    The fraction is p²⟨|F_⊥|²⟩ / (⟨|F_N|²⟩ + p²⟨|F_⊥|²⟩), 0 where both vanish;
    :func:`_classified_reflections` says why it, and not
    ``CompiledPhase.nuclear_mask``, is what classifies a reflection.
    """
    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = np.asarray(cp.reflections.d, dtype=np.float64)
    f_nuc = np.asarray(model._nuclear_f2(ip, d, values, cell), dtype=np.float64)
    f_mag = np.asarray(model._magnetic_f2(ip, d, values, cell), dtype=np.float64)
    total = f_nuc + f_mag
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(total > 0.0, f_mag / total, 0.0)
    return f_nuc, f_mag, frac


def _classified_reflections(model, values):
    """Per phase, the magnetic-only and nuclear-only reflections (WP-1343).

    Yields ``(ip, magnetic_rows, nuclear_rows, positions, fwhm)`` for every
    phase carrying a magnetic component, with the row index sets over that
    phase's merged reflection list and the positions and widths read off
    :meth:`~rietx.model.forward.CompiledModel.phase_peaks` — **the width the
    fit actually drew**, at the primary emission line, exactly as the
    satellite arm reads it.

    Both classes are **purity cuts** (:data:`MAGNETIC_WIDTH_PURITY`) on the
    magnetic fraction p²⟨|F_⊥|²⟩ / (⟨|F_N|²⟩ + p²⟨|F_⊥|²⟩), and that is a
    correction to the obvious reading of ``CompiledPhase.nuclear_mask``.  The
    mask is exact where it applies — a k = 0 magnetic space group drops the
    parent's glide and screw operations, and the rows ``magnetic_reflections``
    adds for that carry an identically zero nuclear structure factor — but it
    marks only *those* rows.  On a **k ≠ 0 supercell** the strong magnetic
    reflections are in the child group's own reflection list with the mask set
    to 1.0, and their nuclear |F|² is zero because the nuclear atoms still
    carry the parent's translation: measured on a Pnma → P2₁/m
    ``2a,b,a+c`` supercell, 3 rows have ``nuclear_mask == 0`` while the twelve
    strongest magnetic reflections — (1 0 ±1), (1 2 ±1), (1 2 3), … all with
    ⟨|F_N|²⟩ exactly 0 — do not.  A classifier reading the mask would have
    measured the statistic on the wrong three reflections in the very case the
    term exists for.  The fraction covers both: it is exactly 1.0 on a masked
    row and on a supercell-extinct one alike.

    A reflection that is *half* magnetic belongs to neither set, which is what
    the cut is for on the nuclear side.
    """
    for ip, cp in enumerate(model.phases):
        if cp.magnetic is None:
            continue
        f_nuc, f_mag, frac = _magnetic_fraction(model, values, ip)
        peaks = model.phase_peaks(ip, values)
        pos = np.asarray(peaks[0][0], dtype=np.float64)
        fwhm = np.asarray(model.peak_fwhm(peaks[0][1], peaks[0][2]),
                          dtype=np.float64)
        live = np.isfinite(pos) & (cp.win[0, :, 1] > cp.win[0, :, 0])
        mag_rows = np.nonzero(live & (frac >= 1.0 - MAGNETIC_WIDTH_PURITY)
                              & (f_mag > 0.0))[0]
        nuc_rows = np.nonzero(live & (frac <= MAGNETIC_WIDTH_PURITY)
                              & (f_nuc > 0.0))[0]
        yield ip, mag_rows, nuc_rows, pos, fwhm


def _sign_split(r: np.ndarray, tt: np.ndarray, rows, pos, fwhm,
                exclude) -> tuple[float, float, int, int, list[int]]:
    """(Σr_centre, Σr_tails, n_centre, n_tails, rows used) for one set.

    The centre is ``|2θ − pos| ≤`` :data:`~.schemas.VALIDITY_RADIUS_FWHM`
    ``· FWHM`` — the report's own linearisation radius, reused rather than
    chosen again — and the tails the ring out to
    :data:`MAGNETIC_WIDTH_TAIL_FWHM` ``· FWHM``.  A reflection whose ring
    reaches a reflection of the *other* class is dropped (``exclude``): the
    whole safety of the statistic is that the two sets are read on disjoint
    channels, and an overlapped pair would put one set's misfit into the
    other's control.
    """
    c_sum = t_sum = 0.0
    c_n = t_n = 0
    used: list[int] = []
    for k in rows:
        p, w = float(pos[k]), float(fwhm[k])
        if not np.isfinite(w) or w <= 0.0:
            continue
        outer = MAGNETIC_WIDTH_TAIL_FWHM * w
        if exclude.size and np.min(np.abs(exclude - p)) <= outer:
            continue
        off = np.abs(tt - p)
        centre = off <= VALIDITY_RADIUS_FWHM * w
        tails = (off > VALIDITY_RADIUS_FWHM * w) & (off <= outer)
        if not centre.any() or not tails.any():
            continue
        c_sum += float(np.sum(r[centre]))
        t_sum += float(np.sum(r[tails]))
        c_n += int(centre.sum())
        t_n += int(tails.sum())
        used.append(int(k))
    return c_sum, t_sum, c_n, t_n, used


#: A magnetic width at or below this (deg 2θ) is on its zero floor, so a
#: column dropped as gradient-free with the value this small is put down to
#: the floor.  Before WP-1938 the slope there was ≈ the value itself.
_MAGNETIC_WIDTH_FLOOR_DEG = 1e-12


def _magnetic_intensity(model, ip: int, values) -> float:
    """Σ p²⟨|F_⊥|²⟩ over phase ``ip``'s reflections — zero exactly when the
    magnetic component has nothing for a width to broaden (WP-1343)."""
    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = np.asarray(cp.reflections.d, dtype=np.float64)
    return float(np.sum(np.asarray(model._magnetic_f2(ip, d, values, cell),
                                   dtype=np.float64)))


def _width_support_findings(model, values, esds, free,
                            moved=()) -> list[Diagnostic]:
    """``MAGNETIC_WIDTH_UNMEASURED`` — the freed width the data cannot see.

    The three identifiability regimes of WP-1343 are not a choice the arm
    makes; they are what the normal matrix says.  The two width terms enter
    the *magnetic* component alone, so they are identifiable exactly to the
    extent that the magnetic/nuclear intensity ratio **differs across
    reflections**: a k ≠ 0 structure with magnetic-only satellites measures
    them, a k = 0 collinear structure whose magnetic and nuclear intensities
    track each other does not, and a paramagnetic pattern has no magnetic
    component for them to broaden at all.

    **No new threshold**: "supported" is the same |value| ≥
    :data:`~rietx.report.schemas.MOMENT_SUPPORT_SIGMA` × esd ratio WP-1327
    uses for a moment's modulus, so the report cannot say a width is measured
    and a moment of the same size is not.

    ``moved`` is the set of paths a ``MAGNETIC_WIDTH_MOVED_MOMENT`` already
    named in this fit, and it changes what this row is allowed to say. The two
    codes answer different questions — support versus shift — and they can
    disagree: a width that is 1.3 esd (so "unmeasured") can still move the
    moment by more than the moment's own esd when it is released.  Left in its
    plain wording this row would then read as licence to drop a term that is
    carrying part of the answer, so where the other code fired this one **says
    so and withholds that licence** rather than repeating the ratio as if it
    settled the matter.

    And a correction to the WP's own expectation, measured rather than
    assumed.  It expects an unmeasurable width back as an **absent** esd and a
    named ``ParameterTable.unmeasured_rows`` entry.  That is not what happens,
    for the reason WP-1327 already recorded one rank down: ``unmeasured_rows``
    fires on an **exactly zero** column, and a magnetic width's column is not
    zero on a k = 0 structure — the magnetic component really is broadened,
    the pattern really does change, and what fails is only the *separation*
    from everything else that broadens a peak there.  So on a k = 0 structure
    the term comes back with an esd larger than its value, no held row and no
    zero column (``tests/test_magnetic_width.py`` asserts it on MnF₂).  The
    honest report is a **ratio**, exactly as WP-1327's "unsupported" is, and this
    diagnostic is what names the path instead of leaving a reader to divide.
    """
    out: list[Diagnostic] = []
    if not esds:
        return out
    for ip, cp in enumerate(model.phases):
        if cp.magnetic is None:
            continue
        for name in ("magnetic_lor_size", "magnetic_lor_strain"):
            path = f"phases.{ip}.{name}"
            if path not in free:
                continue
            val = float(values.get(path, 0.0))
            esd = esds.get(path)
            if esd is None:
                # freed, and back with no esd at all: the covariance dropped
                # its column as gradient-free.  Two causes do that and they
                # need different advice, so each is **checked** before it is
                # named (WP-1118): the component the term broadens carrying no
                # intensity (a zero moment zeroes the column at any width),
                # and the width sitting on its floor.  Neither checked
                # true, the message names no cause rather than guess one
                if _magnetic_intensity(model, ip, values) <= 0.0:
                    cause = ("The magnetic component carries no intensity "
                             "here, so the width broadens nothing at any "
                             "value.")
                    advice = (f"Report {path} as not measured. Refine the "
                              f"moment first (plan=\"magnetic_width\"), since "
                              f"a width needs a nonzero moment to broaden.")
                elif val <= _MAGNETIC_WIDTH_FLOOR_DEG:
                    cause = "This term sits on its zero floor."
                    advice = (f"Report {path} as not measured. Hold it at "
                              f"zero if the partner term carries the "
                              f"broadening.")
                else:
                    cause = ("The magnetic component carries intensity and "
                             "the value is off its floor, so the data is "
                             "flat in this direction for a reason this "
                             "report has not identified.")
                    advice = f"Report {path} as not measured."
                out.append(Diagnostic(
                    level="info", code="MAGNETIC_WIDTH_UNMEASURED",
                    where=[path], value=None,
                    message=(
                        f"{path} was free and came back at {val:.3g} deg with "
                        f"no esd, because its column carried no gradient at "
                        f"the answer. {cause} The width is not measured, and "
                        f"that does not make it zero."),
                    suggestion=advice))
                continue
            if esd <= 0.0 or val >= MOMENT_SUPPORT_SIGMA * esd:
                continue
            head = (f"{path} refined to {val:.4g} deg with an esd of "
                    f"{esd:.4g}. That is {val / esd:.2f}x its own uncertainty, "
                    f"below the {MOMENT_SUPPORT_SIGMA:g}-sigma bar this "
                    f"package uses for a moment. ")
            if path in moved:
                tail = (
                    "MAGNETIC_WIDTH_MOVED_MOMENT fired on it in this same "
                    "fit: releasing it moved the moment by more than the "
                    "moment's own error bar. This is not licence to drop the "
                    "term. Unmeasured here means correlated with the moment, "
                    "and setting it to zero puts the moment back where the "
                    "off-state stage had it.")
                suggestion = (
                    f"Keep {path} free, quote the moment from the stage that "
                    f"freed it, and report the width as an upper bound "
                    f"(value + esd). See MAGNETIC_WIDTH_MOVED_MOMENT for the "
                    f"shift.")
            else:
                tail = ("The number above is where the solver stopped in a "
                        "direction the data is flat in.")
                suggestion = (
                    f"Hold {path} at zero and quote the moment from that fit, "
                    f"or measure the width on a pattern that carries "
                    f"magnetic-only reflections.")
            out.append(Diagnostic(
                level="info", code="MAGNETIC_WIDTH_UNMEASURED",
                where=[path], value=float(val / esd),
                message=head + tail, suggestion=suggestion))
    return out


def magnetic_width_findings(model, values, *, esds=None, free=(),
                            moved=()) -> list[Diagnostic]:
    """``MAGNETIC_WIDTH_UNMODELLED`` — the residual's *shape*, not a width.

    Issue #277 asks for observed FWHM ÷ calculated FWHM per reflection.  This
    package cannot compute the numerator: there is no observed-peak-width
    measurement in it, and the one that is coming is v1.4's ``fit_peaks``
    (WP-1101), which this arm deliberately neither waits on nor duplicates.

    The signature is available without it.  A calculated peak that is too
    narrow under a broad observed one leaves a **sign-structured** residual:
    negative in the middle, positive in both tails.  The low moment the fit
    has already taken does not erase that, it only moves where the two cross
    — least squares trades centre against tails and cannot make both zero
    with the wrong width.  So the statistic is the centre-versus-tails split
    of the *weighted* residual, and it is read off the converged residual the
    report already holds rather than from a trial solve.

    **Differencing the two sets is what makes it safe.**  The split is
    evaluated at the magnetic-only reflections and at the nuclear-only ones,
    and only the difference is judged: a wrong instrument profile, a wrong
    ``lor_size``, a wrong background and an unmodelled specimen aberration all
    move the two sets together and cancel, and only a *component-specific*
    width difference survives.  Its noise is the sample s.d. of the weighted
    residual over the **nuclear-only** channels read, so a fit whose GoF is 3
    is judged against its own scatter and not against an assumed unit
    variance.  The magnetic channels are left out of that scatter because the
    misfit under test lives there: on the synthetic CrSBr arm of
    ``tests/test_magnetic_width_k_half.py`` a held width put the scatter over
    all channels read at 2.57 against 0.99 over the nuclear-only ones, so the
    statistic was divided by its own evidence and stayed at z = 2.99 with the
    moment 25 % low.  The rule is the F test's: the error variance comes from
    residuals the tested effect does not enter (Hamilton, W. C. (1965). *Acta
    Cryst.* 18, 502, eq. (20), where it is the unrestricted model's
    G₀/(n − m)).  The width terms enter the magnetic component alone, and
    under the null the two sets differ in nothing component-specific, the
    assumption the differencing already rests on.

    Fires only where **both magnetic width terms are held at zero** — which
    the compiled model states structurally: the second frozen family exists
    exactly when they can differ from the nuclear widths
    (:meth:`~rietx.model.forward.CompiledModel.mag_split`), so a stage that
    freed the term is a stage this arm has nothing to say about.  The evidence
    for a freed term is the trajectory instead — the stage that freed it is a
    rung on ``stage_reports_`` and the moment before and after is a record the
    plan already produces (WP-1058, WP-1073).

    It never quotes an Rwp comparison as its evidence (root ``CLAUDE.md``),
    and it says which way the moment would move: **up**, because |F_m|² ∝ m²
    and the only way a too-narrow calculated peak can match a broad observed
    one's height is by taking the moment down.
    """
    out: list[Diagnostic] = []
    if getattr(model, "phases", None) is None or getattr(model, "tt", None) is None:
        return out
    # every result build calls this, so a fit with no magnetic component must
    # not pay the forward evaluation below for an arm with nothing to read
    if not any(cp.magnetic is not None for cp in model.phases):
        return out
    out.extend(_width_support_findings(model, values, esds or {}, set(free),
                                       set(moved)))
    tt = np.asarray(model.tt, dtype=np.float64)
    r = ((np.asarray(model.y_obs, dtype=np.float64)
          - np.asarray(model.evaluate(values), dtype=np.float64))
         / np.asarray(model.sigma, dtype=np.float64))
    for ip, mag_rows, nuc_rows, pos, fwhm in _classified_reflections(model, values):
        if model.mag_split(ip):
            continue  # the term is free this stage; the trajectory is the evidence
        if len(mag_rows) < MAGNETIC_WIDTH_MIN_REFLECTIONS or not len(nuc_rows):
            continue
        c_m, t_m, n_cm, n_tm, used_m = _sign_split(
            r, tt, mag_rows, pos, fwhm, pos[nuc_rows])
        c_n, t_n, n_cn, n_tn, used_n = _sign_split(
            r, tt, nuc_rows, pos, fwhm, pos[mag_rows])
        if (len(used_m) < MAGNETIC_WIDTH_MIN_REFLECTIONS or not used_n
                or min(n_cm, n_tm, n_cn, n_tn) < 2):
            continue
        split_m = t_m / n_tm - c_m / n_cm
        split_n = t_n / n_tn - c_n / n_cn
        # the scatter of the nuclear-only channels that were read: measured,
        # not assumed, and on channels the misfit under test cannot inflate
        chan = np.zeros(len(tt), dtype=bool)
        for k in used_n:
            chan |= np.abs(tt - pos[k]) <= MAGNETIC_WIDTH_TAIL_FWHM * fwhm[k]
        s = float(np.std(r[chan], ddof=1)) if int(chan.sum()) > 2 else 0.0
        noise = s * float(np.sqrt(1.0 / n_tm + 1.0 / n_cm
                                  + 1.0 / n_tn + 1.0 / n_cn))
        if noise <= 0.0:
            continue
        z = (split_m - split_n) / noise
        if z <= MAGNETIC_WIDTH_SIGMA:
            continue
        cp = model.phases[ip]
        names = ", ".join(
            f"({' '.join(str(int(h)) for h in cp.reflections.hkl[k])})"
            f" at {float(pos[k]):.2f} deg" for k in used_m[:6])
        more = "" if len(used_m) <= 6 else f" and {len(used_m) - 6} more"
        out.append(Diagnostic(
            level="warning", code="MAGNETIC_WIDTH_UNMODELLED",
            where=[f"phases.{ip}.magnetic_lor_size",
                   f"phases.{ip}.magnetic_lor_strain"],
            value=float(z),
            message=(
                f"The magnetic reflections of phase {ip} are fitted by "
                f"peaks that are too narrow, so the refined moment is biased "
                f"low. "
                f"The weighted residual under {names}{more} is negative at "
                f"the centre and positive in both tails "
                f"(centre-vs-tails split {split_m:+.3f}), while the same "
                f"statistic at this phase's {len(used_n)} nuclear-only "
                f"reflection(s) is {split_n:+.3f}. The difference is "
                f"{z:.1f}x its noise, measured as the residual's scatter at "
                f"the nuclear-only reflections."),
            suggestion=(
                f"Run fit(data, plan=\"magnetic_width\"). It frees "
                f"phases.{ip}.magnetic_lor_size from its zero floor after the "
                f"moment has converged."),
        ))
    return out


# ---------------------------------------------------------------------------
# WP-2056 — the lowest lines are magnetic, so no nuclear line checks the
# low-angle asymmetry
# ---------------------------------------------------------------------------
#: The central-difference step for a line's position derivative, as a
#: fraction of its drawn FWHM.  Small enough that the truncation error is far
#: below the counting noise, large enough to stay clear of round-off; the
#: shift it feeds is a report, so the step moves no fitted value.
_SHIFT_STEP_FWHM = 1e-4


def _line_profile(model, cp, comps, rows, sl: float, hl: float,
                  shift: float = 0.0):
    """``(i0, y)``: the drawn counts of the reflections ``rows`` together,
    every component, on the union of their frozen windows (primary line).

    ``shift`` moves every position by that many degrees with the windows
    held, which is what the position derivative below needs.  ``None`` when
    no row has a window.
    """
    spans = []
    for component, peaks in comps:
        pos, gamma, eta, inten = peaks[0]
        win = cp.win if component == 0 else cp.win_mag
        for k in rows:
            if not (np.isfinite(pos[k]) and inten[k] > 0.0):
                continue
            prof = model._reflection_profile(
                cp, 0, k, float(pos[k]) + shift, gamma[k], eta[k], sl, hl,
                component=component)
            if prof is None:
                continue
            spans.append((int(win[0, k, 0]),
                          float(inten[k]) * np.asarray(prof, dtype=np.float64)))
    if not spans:
        return None
    i0 = min(a for a, _ in spans)
    y = np.zeros(max(a + len(p) for a, p in spans) - i0)
    for a, p in spans:
        y[a - i0:a - i0 + len(p)] += p
    return i0, y


def _phase_lines(model, values, ip: int, sigma: np.ndarray) -> list[dict]:
    """The lines of phase ``ip`` the data sees, each with its drawn profile
    and position derivative, before any shift is solved.

    A *line* is the reflections drawn within
    :data:`~.schemas.VALIDITY_RADIUS_FWHM` · FWHM of each other, which the
    data cannot tell apart (a k ≠ 0 supercell puts pairs such as (1 0 1) and
    (1 0 0) on one position).  Its width is the intensity-weighted FWHM of
    the components that draw it, so a magnetic-only line under a freed
    magnetic width is read at the width the fit drew.  It is **seen** when
    the t of its own scale against the counting noise, √Σ(P/σ)², reaches
    :data:`~.schemas.MIN_COEF_SIGNIFICANCE`, the standing bar, and only when
    its ± :data:`~.schemas.MAGNETIC_WIDTH_TAIL_FWHM` · FWHM window lies inside
    the fitted range: a line centred off the data is read by its tail alone.
    """
    cp = model.phases[ip]
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    comps = [(0, model.phase_peaks(ip, values, component=0))]
    if model.mag_split(ip):
        comps.append((1, model.phase_peaks(ip, values, component=1)))
    pos = np.asarray(comps[0][1][0][0], dtype=np.float64)
    n_refl = len(pos)
    inten = np.zeros(n_refl)
    width = np.zeros(n_refl)
    for _, peaks in comps:
        i_c = np.asarray(peaks[0][3], dtype=np.float64)
        w_c = np.asarray(model.peak_fwhm(peaks[0][1], peaks[0][2]),
                         dtype=np.float64)
        inten = inten + i_c
        width = width + np.where(i_c > 0.0, i_c * w_c, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        fwhm = np.where(inten > 0.0, width / inten, np.nan)
    frac = (_magnetic_fraction(model, values, ip)[2]
            if cp.magnetic is not None else np.zeros(n_refl))
    tt = np.asarray(model.tt, dtype=np.float64)
    lo, hi = float(tt[0]), float(tt[-1])
    live = [int(k) for k in np.argsort(pos)
            if np.isfinite(pos[k]) and np.isfinite(fwhm[k]) and fwhm[k] > 0.0
            and inten[k] > 0.0 and cp.win[0, k, 1] > cp.win[0, k, 0]]
    groups: list[list[int]] = []
    for k in live:
        if groups and (pos[k] - pos[groups[-1][0]]
                       <= VALIDITY_RADIUS_FWHM * fwhm[groups[-1][0]]):
            groups[-1].append(k)
        else:
            groups.append([k])
    lines = []
    for g in groups:
        w = float(np.average(fwhm[g], weights=inten[g]))
        centre = float(np.average(pos[g], weights=inten[g]))
        reach = MAGNETIC_WIDTH_TAIL_FWHM * w
        if centre - reach < lo or centre + reach > hi:
            continue
        drawn = _line_profile(model, cp, comps, g, sl, hl)
        if drawn is None:
            continue
        i0, y = drawn
        if np.sqrt(np.sum((y / sigma[i0:i0 + len(y)]) ** 2)) < MIN_COEF_SIGNIFICANCE:
            continue
        h = _SHIFT_STEP_FWHM * w
        # the windows are frozen, so both shifted profiles start at i0
        up = _line_profile(model, cp, comps, g, sl, hl, shift=h)[1]
        dn = _line_profile(model, cp, comps, g, sl, hl, shift=-h)[1]
        lines.append({"phase": ip, "pos": centre, "fwhm": w,
                      "frac": float(np.average(frac[g], weights=inten[g])),
                      "i0": i0, "y": y, "dy": (up - dn) / (2.0 * h),
                      "hkl": [tuple(int(x) for x in cp.reflections.hkl[k])
                              for k in g]})
    return lines


def _solve_shifts(tt: np.ndarray, r: np.ndarray, sigma: np.ndarray,
                  block: list[dict], lo: float, hi: float) -> list[tuple]:
    """``(line, shift, esd)`` for one block of overlapping lines.

    The residual on the channels ``lo``-``hi`` is regressed, under weights
    1/σ², on every line's ∂P/∂(2θ) **and** its own drawn profile P: the
    second column takes a line's intensity misfit, which an asymmetric drawn
    line would otherwise leak into its shift.  Only the shift coefficients
    are reported, each with its counting-noise esd and no serial-correlation
    factor, since that factor is measured on the residual holding the misfit
    under test.  A singular block is solved one line at a time.
    """
    chan = np.nonzero((tt >= lo) & (tt <= hi))[0]
    if not len(chan):
        return []
    c0, c1 = int(chan[0]), int(chan[-1]) + 1

    def column(ln, key):
        col = np.zeros(c1 - c0)
        a, v = ln["i0"], ln[key]
        s0, s1 = max(a, c0), min(a + len(v), c1)
        if s1 > s0:
            col[s0 - c0:s1 - c0] = v[s0 - a:s1 - a]
        return col / sigma[c0:c1]

    b = r[c0:c1] / sigma[c0:c1]

    def solve(lines):
        a = np.column_stack([column(ln, key) for ln in lines
                             for key in ("dy", "y")])
        cov = np.linalg.inv(a.T @ a)
        coef = cov @ (a.T @ b)
        return [(ln, float(coef[2 * i]), float(cov[2 * i, 2 * i]))
                for i, ln in enumerate(lines)]

    try:
        rows = solve(block)
    except np.linalg.LinAlgError:
        rows = []
        for ln in block:
            try:
                rows += solve([ln])
            except np.linalg.LinAlgError:
                continue
    return [(ln, c, math.sqrt(v)) for ln, c, v in rows
            if math.isfinite(c) and v > 0.0]


def _line_shifts(model, values, r: np.ndarray, sigma: np.ndarray):
    """Every seen line of every phase, with its centroid shift.

    Rows ``(phase, position, fwhm, magnetic fraction, shift, esd, hkl)``,
    sorted by position, shift and esd in degrees; negative means the observed
    line sits at lower angle than the drawn one.  Lines of all phases are
    pooled, so overlapping lines of two phases are solved together and the
    lowest line that could check the asymmetry is found in any phase
    (:func:`_phase_lines`, :func:`_solve_shifts`).
    """
    lines = sorted((ln for ip in range(len(model.phases))
                    for ln in _phase_lines(model, values, ip, sigma)),
                   key=lambda ln: ln["pos"])
    tt = np.asarray(model.tt, dtype=np.float64)
    out = []
    j = 0
    while j < len(lines):
        block = [lines[j]]
        lo = lines[j]["pos"] - MAGNETIC_WIDTH_TAIL_FWHM * lines[j]["fwhm"]
        reach = lines[j]["pos"] + MAGNETIC_WIDTH_TAIL_FWHM * lines[j]["fwhm"]
        j += 1
        while (j < len(lines) and lines[j]["pos"]
               - MAGNETIC_WIDTH_TAIL_FWHM * lines[j]["fwhm"] <= reach):
            block.append(lines[j])
            reach = max(reach, lines[j]["pos"]
                        + MAGNETIC_WIDTH_TAIL_FWHM * lines[j]["fwhm"])
            j += 1
        for ln, shift, esd in _solve_shifts(tt, r, sigma, block, lo, reach):
            out.append((ln["phase"], ln["pos"], ln["fwhm"], ln["frac"],
                        shift, esd, ln["hkl"]))
    return sorted(out, key=lambda row: row[1])


def _cot_through(lines):
    """``(A, esd)`` of the one-term shape shift = A·cot 2θ through ``lines``.

    Weighted least squares on the lines' own esds, with no intercept: the
    question is how a shift that is largest at the lowest line carries to
    the next one, and cot 2θ is the shape issue #1090 measured on Ba₂FeSbSe₅
    (about −50 mdeg at 9.35°, falling to a few mdeg by 21-22°).  It is a
    reporting shape, not a model of the instrument.
    """
    c = np.array([1.0 / math.tan(math.radians(ln[1])) for ln in lines])
    s = np.array([ln[4] for ln in lines])
    w = 1.0 / np.array([ln[5] for ln in lines]) ** 2
    info = float(np.sum(w * c * c))
    if not info > 0.0:
        return None
    return float(np.sum(w * c * s) / info), float(1.0 / math.sqrt(info))


def low_angle_asymmetry_findings(model, values, y_calc=None) -> list[Diagnostic]:
    """``LOW_ANGLE_ASYMMETRY_UNCALIBRATED`` — the lowest lines are magnetic.

    On a constant-wavelength pattern the axial-divergence asymmetry is
    largest at low angle, and the lines there are the ones that say how much
    of it the instrument has.  When every line the data sees below some angle
    is **magnetic-only**, nothing in this sample checks that number: a
    magnetic line's shape carries the moment's form factor and any magnetic
    broadening as well as the instrument, so an asymmetry refined against it
    (or left at a value that misses it) lands on the magnetic parameters
    unseen.  Issue #1090 has the two measured cases: Ba₂FeSbSe₅ on G4.1,
    where one tied ratio draws a tail the 9.35° line lacks, and LaMnO₃ on
    BT-1, where it matches the 11.5° line.  The same geometry needs opposite
    treatment, so this finding decides nothing and reports.

    **What fires it is geometry**: at least one seen magnetic-only line (a
    magnetic fraction at or above 1 − :data:`~.schemas.MAGNETIC_WIDTH_PURITY`)
    below the lowest seen nuclear-only line of any phase (a fraction at or
    below it: WP-1343's control side), or with no nuclear-only line seen at
    all.  A half-magnetic line neither fires it nor silences it.  **What it says is arithmetic**:
    each such line's centroid shift with its counting-noise esd
    (:func:`_line_shifts`), the shift at the first line that could check it,
    and what a cot 2θ shape through the magnetic-only lines predicts there
    (:func:`_cot_through`), so a reader sees whether that line follows them.
    No threshold is applied to any of the numbers.  ``y_calc`` is the drawn
    pattern where the caller already holds it.
    """
    out: list[Diagnostic] = []
    if getattr(model, "phases", None) is None or getattr(model, "tt", None) is None:
        return out
    if not any(cp.magnetic is not None for cp in model.phases):
        return out
    sigma = np.asarray(model.sigma, dtype=np.float64)
    if y_calc is None:
        y_calc = model.evaluate(values)
    r = (np.asarray(model.y_obs, dtype=np.float64)
         - np.asarray(y_calc, dtype=np.float64))
    lines = _line_shifts(model, values, r, sigma)
    # the anchor is a nuclear-only line (WP-1343's control side of the
    # cut); a half-magnetic line neither anchors nor is listed
    first = next((i for i, ln in enumerate(lines)
                  if ln[3] <= MAGNETIC_WIDTH_PURITY), len(lines))
    low = [ln for ln in lines[:first] if ln[3] >= 1.0 - MAGNETIC_WIDTH_PURITY]
    if not low:
        return out
    anchor = lines[first] if first < len(lines) else None
    sl = float(values["instrument.geometry.axial_sl"])
    hl = float(values["instrument.geometry.axial_hl"])
    phases = sorted({ln[0] for ln in low})

    def name(ln):
        return "/".join(f"({' '.join(str(x) for x in h)})" for h in ln[6][:2])

    one = len(low) == 1
    shown = ", ".join(
        f"{1e3 * ln[4]:+.1f}({1e3 * ln[5]:.1f}) mdeg at {ln[1]:.2f} deg "
        f"{name(ln)}" for ln in low[:4])
    more = "" if len(low) <= 4 else f" and {len(low) - 4} more"
    where_from = (f"below {anchor[1]:.2f} deg" if anchor is not None
                  else "in the fitted range")
    owner = (f"phase {phases[0]}" if len(phases) == 1
             else "phases " + ", ".join(str(p) for p in phases))
    message = (
        f"No nuclear line the data sees lies {where_from}, where "
        f"{len(low)} magnetic-only line{' of ' if one else 's of '}{owner} "
        f"{'does' if one else 'do'}, so the axial asymmetry is not "
        f"determinable from this sample's nuclear lines where it is largest. "
        f"{'Its centroid sits' if one else 'Their centroids sit'} "
        f"{shown}{more} from the drawn {'position' if one else 'positions'} "
        f"(negative: observed at lower angle).")
    if anchor is not None:
        message += (
            f" The first nuclear line, at {anchor[1]:.2f} "
            f"deg, sits {1e3 * anchor[4]:+.1f}({1e3 * anchor[5]:.1f}) mdeg.")
        shape = _cot_through(low)
        if shape is not None:
            cot = 1.0 / math.tan(math.radians(anchor[1]))
            message += (
                f" A cot 2theta shape through the magnetic-only line"
                f"{'' if one else 's'} (shift = A cot 2theta, A = "
                f"{1e3 * shape[0]:+.1f}({1e3 * shape[1]:.1f}) mdeg) predicts "
                f"{1e3 * shape[0] * cot:+.1f}({1e3 * shape[1] * cot:.1f}) mdeg "
                f"there.")
    state = ("held at 0" if sl == 0.0 and hl == 0.0
             else f"S/L {sl:.4g}, H/L {hl:.4g}")
    message += f" The axial apertures are {state}."
    out.append(Diagnostic(
        level="info", code="LOW_ANGLE_ASYMMETRY_UNCALIBRATED",
        where=["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"],
        value=float(low[0][4]),
        message=message,
        suggestion=(
            "Take the axial asymmetry from a standard measured on this "
            "instrument at this wavelength, in the same container and fill. "
            "Whatever the source, a standard, an instrument file or a value "
            "refined on these magnetic lines, compare the lowest line's "
            "drawn and observed shape under it before quoting the moment."),
    ))
    return out
