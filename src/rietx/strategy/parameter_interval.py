"""The profile interval behind :meth:`rietx.refine.Refinement.profile_interval`.

A refined parameter's esd is the curvature of χ² at the converged point, and
read as an interval it is symmetric by construction.  On a bound it is no
interval at all: the estimate has no symmetric sampling distribution on the
boundary of the parameter space, and the likelihood-ratio statistic there is
the mixture ½χ²₀ + ½χ²₁ (Self & Liang, 1987, J. Am. Statist. Assoc. 82,
605).  WP-1929 kept such a row's value and marginal esd and flagged
it (``RefinedParameter.at_bound``, ``FLOOR_HIT``); this is the number a caller
who needs one asks for.

**The profile interval** (Venzon & Moolgavkar, 1988, Appl. Statist. 37, 87):
pin the parameter at v, refit everything else, and read the data's χ² there.
The interval is every v whose Δχ² from the fit stays under a threshold.  Each
pinned refit is the constrained hypothesis of Hamilton's test with one
constraint (Hamilton, 1965, Acta Cryst. 18, 502), so the threshold is a χ²₁
quantile c, scaled by the fit's χ²_red and the square of its Bérar-Lelann
factor f (Bérar & Lelann, 1991, J. Appl. Cryst. 24, 1) exactly as
``fraction_profile`` scales it and as every reported esd is.  On a quadratic
profile the two-sided interval is then the fitted value ± √c esd.

- **Interior row**: two-sided, c = χ²₁ quantile at ``level`` (3.84 at 95 %),
  one end on each side.
- **Row on its bound**: one-sided.  The bound is one end.  The other is where
  Δχ² reaches c = χ²₁ quantile at 2·``level`` − 1 (2.71 at 95 %), because
  under Self & Liang's mixture P(T > c) = ½·P(χ²₁ > c).

**The ends are found by bracketing and Brent's method on the profile itself**
(Brent, 1973, *Algorithms for Minimization without Derivatives*, ch. 4;
``scipy.optimize.brentq``) rather than by Venzon & Moolgavkar's Newton
iteration on the augmented system, which needs second derivatives of the
whole model.  Each side steps outward from the fitted value by 1, 2, 4, …
esd until Δχ² passes the threshold or the step reaches the parameter's own
limit, which is reported as that side's end.  Each refit starts where the
previous one on its side finished.  ``max_refits`` caps each side, and a side
that runs out, or whose refit raises, has no end and says why.  A first probe
already past the threshold steps back in instead (:func:`_walk`, WP-2060),
and every refit keeps the fit's own free set: what the fit held stays held.

**A moment's modulus keeps its sign where the data cannot see it**
(:func:`_sign_is_unseen`, WP-2060).  The intensity goes as m², so there the
profile is even about 0, and 0 is a bound: a modulus on it gets a one-sided
interval, like any bounded row.

**A pinned value is refitted until its χ² settles.**  A stage sizes its peak
windows at compile, from where it starts, and keeps them (root CLAUDE.md,
frozen-per-stage discreteness).  Pin BT-1's Lorentzian ``x`` one esd below
the fit and ``y`` leaves its floor of 0 inside the refit, on windows sized for
``y`` = 0: Δχ² 28.3 after one refit, 16.9 after a second at the same value,
against a threshold of 30.3 (WP-1929, macOS arm64).  So a probe refits again
while χ² falls, and keeps the lowest it reached.  The windows also make the
profile a function with steps in it: on that fit some pinned values
alternate between two compiles 0.2-3 χ² apart, about a tenth of the
threshold, and that sets how precise an end is there whatever ``xtol`` says.

**Read-only by construction**, as ``fraction_profile`` is: every refit runs on
a branch (or on a copy of the models where the caller disabled history), with
``telemetry=False``, and the history's HEAD is put back.

**A moment angle the stationary-angle test left out gets its interval
unasked** (WP-2002, B2).  Such an angle has no esd, and the interval is the
number it carries instead (:func:`attach_stationary_intervals`).  That run is
the package's, never the caller's, so its refits go on a copy of the models
and leave the caller's history exactly as a plain fit leaves it.
"""

from __future__ import annotations

import math
import re

from ..optimize.cancel import RefinementCancelled
from ..schemas.interval import (
    PARAMETER_INTERVAL_BRACKET_GROWTH,
    PARAMETER_INTERVAL_CHI2_TOL,
    PARAMETER_INTERVAL_LEVEL,
    PARAMETER_INTERVAL_MAX_REFITS,
    PARAMETER_INTERVAL_SETTLE_RUNS,
    PARAMETER_INTERVAL_XTOL,
    IntervalStop,
    ParameterInterval,
    ParameterIntervalPoint,
)
from .fraction_profile import data_chi2, head_restored
from .staged import BOUND_HIT_ESD_FRAC, Stage

#: A moment's two angle DOFs (polar, azimuth): the paths whose interval walk
#: stops at half a turn (:data:`~rietx.schemas.interval.IntervalStop`'s
#: ``"period"``).  The modulus, ``dof0``, is not periodic.
_MOMENT_ANGLE = re.compile(r"\.moment\.dof[12]$")

#: A moment's modulus, with its phase and its site (WP-2060).
_MOMENT_MODULUS = re.compile(r"^(phases\.\d+)\.atoms\.\d+\.moment\.dof0$")


def _sign_is_unseen(table, path: str, free: set[str]) -> bool:
    """Whether the data cannot tell this modulus from its negative (WP-2060).

    Two cases, each an identity of the model rather than a measurement.  A
    phase with one moment block flips every moment it has when the modulus
    changes sign, and an unpolarised pattern cannot see that: the magnetic
    intensity goes as |F_M⊥|², and it adds to the nuclear intensity with no
    cross term (Halpern & Johnson, 1939, Phys. Rev. 55, 898).  And a block
    with two or three DOFs reaches −μ by turning its angles, (−μ, φ) being
    (μ, φ + π) (``canonical_dofs``), so with its angles free the sign is a
    chart, not a structure.  Elsewhere the sign is a relative orientation the
    data can measure (a one-DOF modulus on one of two sites), and the profile
    keeps both signs.
    """
    match = _MOMENT_MODULUS.match(path)
    if match is None:
        return False
    phase, base = match.group(1) + ".", path[:-len(".dof0")]
    blocks = [e.path for e in table.entries
              if e.path.startswith(phase) and e.path.endswith(".moment.dof0")]
    if len(blocks) == 1:
        return True
    angles = [e.path for e in table.entries
              if e.path.startswith(base + ".dof") and e.path != path]
    return bool(angles) and all(a in free for a in angles)


def interval_quantile(level: float, one_sided: bool) -> float:
    """The χ²₁ quantile c a profile interval's Δχ² threshold is scaled from.

    Two-sided, c is χ²₁'s ``level`` point, the Δχ² a pinned refit is tested
    at (Hamilton, 1965, Acta Cryst. 18, 502).  One-sided, for an estimate on
    the boundary of the parameter space, the statistic is ½χ²₀ + ½χ²₁ (Self &
    Liang, 1987, J. Am. Statist. Assoc. 82, 605), so P(T > c) = 1 − level
    gives c at χ²₁'s 2·level − 1 point: 2.706 at 95 %, against 3.841.
    """
    from scipy.stats import chi2

    if not 0.0 < level < 1.0:
        raise ValueError(f"a confidence level lies strictly between 0 and 1, "
                         f"not {level!r}")
    q = 2.0 * level - 1.0 if one_sided else level
    if q <= 0.0:
        raise ValueError(
            f"a one-sided interval at level {level:g} is the bound alone: the "
            "statistic puts half its mass on the bound, so a level of 0.5 or "
            "below needs no refit at all")
    if one_sided:
        # the k = 1 member of the χ̄² family the stationary-angle test cuts at
        # (WP-1929), so the two cannot disagree about Self & Liang's mixture
        from ..optimize.statistics import chi_bar_squared_quantile

        return chi_bar_squared_quantile(level, 1)
    return float(chi2.ppf(q, 1))


def _stationary_half_width(result, path: str) -> float | None:
    """The step for a moment angle the answer stage's covariance left out.

    Such an angle sits at a direction the symmetry fixes, where its column
    vanishes, so it has no esd (WP-1929).  The pattern still determines it
    through curvature, and the passing round of
    ``StageResult.moment_angle_tests`` records the distance either side at
    which χ², everything else held, rises by χ²_red·f².  That distance is the
    profile's first step.  ``None`` where the path was not left out.
    """
    stage = result.stages[-1] if result.stages else None
    for test in (getattr(stage, "moment_angle_tests", None) or []):
        if test.zeroed and path in test.half_widths:
            width = float(test.half_widths[path])
            return width if math.isfinite(width) and width > 0.0 else None
    return None


class _SideStopped(Exception):
    """One side of the interval stopped without an end, and why."""

    def __init__(self, stop: IntervalStop):
        super().__init__(stop)
        self.stop = stop


def _refined_row(refinement, result, path: str):
    """The last fit's row for ``path``, refusing a path that was not free in it.

    The reason is the one :attr:`ParameterRow.held_because` gives, so a tied
    row names its sources the way ``set_values`` does.
    """
    row = next((p for p in result.parameters if p.path == path), None)
    if row is not None and row.vary:
        return row
    rows = refinement.parameters()
    current = next((r for r in rows if r.path == path), None)
    if current is None:
        from ..refine import _path_hint  # lazy: refine imports strategy
        hint = _path_hint(path, [r.path for r in rows])
        raise ValueError(f"unknown parameter path {path!r}" + (f"; {hint}" if hint else ""))
    why = current.held_because
    if why:
        raise ValueError(f"{path!r} cannot be pinned and profiled on its own "
                         f"({why})")
    raise ValueError(f"{path!r} was not free in the last fit, so the fit is no "
                     "minimum along it to profile from; free it and fit again")


def _bounded_end(result, row, lo: float, hi: float) -> tuple[int, float]:
    """The side a flagged row's bound is on (−1 lower, +1 upper), and its end.

    Read off the finding that flagged the row, because the limit the stage
    solved against need not be the entry's declared one: a cell window, a
    strain or size cap and a tie window are frozen onto the stage's table and
    never reach ``Entry.lo``/``hi``.  ``FLOOR_HIT`` is a lower limit, and a
    ``BOUND_HIT``'s value is the residual cosine, positive where the solver
    still pushes the row down.  The end is the declared limit where the row
    sits on it, and the row's own value where the limit was the stage's.
    """
    side = None
    for d in result.diagnostics:
        if row.path not in (d.where or ()):
            continue
        if d.code == "FLOOR_HIT":
            side = -1
        elif d.code == "BOUND_HIT" and d.value:
            side = -1 if d.value > 0.0 else 1
        if side is not None:
            break
    if side is None:                    # an unsigned finding: the nearer limit
        side = 1 if hi - row.value < row.value - lo else -1
    declared = lo if side < 0 else hi
    on_it = (math.isfinite(declared)
             and abs(row.value - declared) <= BOUND_HIT_ESD_FRAC * row.stderr)
    return side, (declared if on_it else row.value)


def _walk(refinement, data, path: str, start: float, sign: int, limit: float,
          step: float, cut: float, chi2_fit: float, budget: int,
          points: list[ParameterIntervalPoint], *, record: bool = True,
          cancel=None, limit_stop: IntervalStop = "bound",
          frozen: tuple[str, ...] = ()
          ) -> tuple[float | None, IntervalStop]:
    """One side: bracket the root by doubling steps, then solve it with Brent.

    ``record`` is :meth:`~rietx.refine.Refinement._trial`'s: ``False`` refits
    on a copy of the models, so the caller's history gains no node.
    ``cancel`` reaches every refit, and a cancelled one raises
    :class:`~rietx.optimize.cancel.RefinementCancelled` out of the walk
    rather than ending the side as an error.  ``limit_stop`` is what reaching
    ``limit`` means: ``"bound"``, the parameter's own limit and so the end, or
    ``"period"``, half a turn of a moment angle and so no end.  ``frozen`` is
    what the fit's answer stage held, kept fixed in every refit.

    **A first probe already past the threshold steps back in** (WP-2060).
    The step is the esd, and an esd measures the curvature at the fit, which
    can be orders too small: a moment's modulus at m = 0 has a dead column,
    since the intensity goes as m², so its esd read 1.5e4 μ_B against an end
    near 0.06.  Brent's tolerance is a thousandth of the step, so it returned
    the fit itself as the end, a zero-width interval.  So each probe past the
    threshold is replaced by one at the distance a quadratic through it puts
    the end, divided by the growth factor, until a probe lands inside.  On a
    quadratic profile that probe lands at half the end's distance.  On the
    quartic one of a dead column it lands further in, so the end is then
    solved in the logarithm of the distance, where any power law is a
    straight line and the tolerance is relative.  The bracket's inner end is
    then a measured probe and never the fit, so the end lies strictly away
    from the value.  A probe nearer the fit whose Δχ² did not fall is a
    profile that does not return to the fit's χ² at its value, and the side
    stops on ``"error"`` with that probe saying so.
    """
    from scipy.optimize import brentq

    if start == limit:
        return limit, "bound"            # already on this side's limit
    def fresh():
        # The fit's own free set, along the whole path.  Each refit is a
        # stage, and a stage re-decides WP-1301's hold from the values it
        # starts at: a weak phase's scale pinned above the support threshold
        # would free the cell the fit held, and the profile would then measure
        # a different model from the fit it is quoted for (#1075).  A refit
        # may still hold more, since a lower pinned scale can hide a phase the
        # fit saw.
        t = refinement._trial(record=record)
        t.set_vary([path, *frozen], False)
        return t

    trial = fresh()
    measured = {start: 0.0}             # the fit itself, by definition
    settled = PARAMETER_INTERVAL_CHI2_TOL * cut
    spent = 0

    def delta(v: float, restart: bool = False) -> float:
        nonlocal spent, trial
        if v in measured:
            return measured[v]
        if spent >= budget:
            raise _SideStopped("refits")
        if restart:
            # start the refit from the fit rather than from the previous
            # probe, which past the threshold can be a state no refit finds
            # its way back from.  A new trial and never a set_values of the
            # fitted rows: a coordinate DOF is a displacement rederived to
            # zero on every build, so writing its fitted value back would
            # leave the atom where the last probe moved it.
            trial = fresh()
        try:
            trial.set_values({path: v})
        except Exception as exc:  # a value the model refuses ends the side too
            points.append(ParameterIntervalPoint(value=v, runs=0, error=str(exc)))
            raise _SideStopped("error") from exc
        best, last, runs, error = None, None, 0, None
        # refit until χ² stops falling: a refit ends on the peak windows its
        # start compiled (PARAMETER_INTERVAL_SETTLE_RUNS has the measurement)
        while runs < PARAMETER_INTERVAL_SETTLE_RUNS and spent < budget:
            spent += 1
            runs += 1
            try:
                # under the plan settings the caller's fit ran with
                # (``Refinement._plan_settings``, WP-2002 B1)
                r = trial.run_stage(data, Stage(f"interval:{path}", []),
                                    telemetry=False, cancel=cancel,
                                    **trial._plan_settings)
            except RefinementCancelled:
                raise                 # the caller's stop, not this point's
            except Exception as exc:  # an unmeasurable point ends the side
                error = str(exc)
                break
            chi2 = data_chi2(r.statistics)
            if best is None or chi2 < best[0]:
                best = (chi2, r)
            if last is not None and last - chi2 <= settled:
                break
            last = chi2
        if best is None:
            points.append(ParameterIntervalPoint(value=v, runs=runs, error=error))
            raise _SideStopped("error")
        chi2, r = best
        points.append(ParameterIntervalPoint(
            value=v, runs=runs, chi2=chi2, delta_chi2=chi2 - chi2_fit,
            status=r.stages[-1].status if r.stages else r.status,
            error=error, node_id=r.node_id))
        if error is not None:
            raise _SideStopped("error")
        measured[v] = chi2 - chi2_fit
        return measured[v]

    try:
        inner, k = start, 0
        while True:
            v = start + sign * PARAMETER_INTERVAL_BRACKET_GROWTH ** k * step
            reached = v <= limit if sign < 0 else v >= limit
            if reached:
                v = limit
            if delta(v) >= cut:
                break
            if reached:
                return (limit, "bound") if limit_stop == "bound" else (None, limit_stop)
            inner, k = v, k + 1
        if inner == start:
            # the first probe passed the threshold: step back in until one
            # does not, then solve in log distance (the docstring has why)
            outer = v
            while True:
                distance = (abs(outer - start) * math.sqrt(cut / measured[outer])
                            / PARAMETER_INTERVAL_BRACKET_GROWTH)
                v = start + sign * distance
                if v == start:
                    raise _SideStopped("error")   # no distance left to probe
                if delta(v, restart=True) < cut:
                    break
                if measured[v] > measured[outer] - settled:
                    # nearer the fit and no lower: the refits do not come back
                    # to the fit's χ² near its value, so there is no end to find
                    points[-1] = points[-1].model_copy(update={"error": (
                        f"the refits do not return to the fit's chi2 near its "
                        f"value: {measured[v]:.4g} above it at {abs(v - start):.3g} "
                        f"from the value, {measured[outer]:.4g} at "
                        f"{abs(outer - start):.3g}")})
                    raise _SideStopped("error")
                outer = v
            floor = PARAMETER_INTERVAL_CHI2_TOL * cut
            # the bracket's two ends are probes already measured, so they map
            # back to those values exactly rather than through exp(log(·))
            ends = {math.log(distance): v, math.log(abs(outer - start)): outer}

            def value_at(x: float) -> float:
                return ends.get(x, start + sign * math.exp(x))

            def log_excess(x: float) -> float:
                return math.log(max(delta(value_at(x), restart=True), floor) / cut)

            root = value_at(brentq(log_excess, *ends, xtol=PARAMETER_INTERVAL_XTOL))
            delta(root)
            return root, "threshold"
        a, b = sorted((inner, v))
        root = float(brentq(lambda x: delta(x) - cut, a, b,
                            xtol=PARAMETER_INTERVAL_XTOL * step))
        # brentq returns a point it evaluated, so this is a lookup: the end is
        # always one of ``points``, and its Δχ² can be read there
        delta(root)
        return root, "threshold"
    except _SideStopped as stopped:
        return None, stopped.stop


def profile_interval(refinement, data, path: str, *,
                     level: float = PARAMETER_INTERVAL_LEVEL,
                     max_refits: int = PARAMETER_INTERVAL_MAX_REFITS,
                     record: bool = True, cancel=None) -> ParameterInterval:
    """Pin ``path`` outward from the fit on each open side, refit, solve for the ends.

    See :meth:`rietx.refine.Refinement.profile_interval`, which is this with
    ``record`` and ``cancel`` at their defaults.  ``record=False`` and a token
    are :func:`attach_stationary_intervals`' (:func:`_walk` says what each does).
    """
    result = refinement.result_
    if result is None:
        raise RuntimeError("run a fit before profiling a parameter")
    if isinstance(max_refits, bool) or not isinstance(max_refits, int) or max_refits < 1:
        raise ValueError(f"max_refits is a whole number of refits per side, at "
                         f"least 1, not {max_refits!r}")
    row = _refined_row(refinement, result, path)
    step = row.stderr
    if step is None or not (math.isfinite(step) and step > 0.0):
        # a moment angle the stationary test left out of the covariance has
        # no esd and is still determined, by curvature: its record carries
        # the scale to step in (WP-1929)
        step = _stationary_half_width(result, path)
    if step is None:
        raise ValueError(
            f"{path!r} has no esd from the last fit, so there is no scale to step "
            "the profile in: the residual does not move along it, and a "
            "direction the data does not see has no interval")
    table = refinement._working_table()
    entry = next((e for e in table.entries if e.path == path), None)
    if entry is None:
        raise ValueError(f"{path!r} was in the last fit and is not in the model "
                         "now; fit again before profiling it")
    lo, hi = float(entry.lo), float(entry.hi)
    # A moment angle repeats every 2π, so half a turn either side covers every
    # direction it can point in.  A side still under the threshold there has
    # no end, and walking on only doubles out to absurd angles (measured: a
    # moment the data no longer saw walked to ±1e12 rad, 120 refits an angle).
    half_turn: set[int] = set()
    if _MOMENT_ANGLE.search(path):
        if row.value - math.pi > lo:
            lo = row.value - math.pi
            half_turn.add(-1)
        if row.value + math.pi < hi:
            hi = row.value + math.pi
            half_turn.add(1)

    # A modulus whose sign the data cannot see keeps its sign (WP-2060).  The
    # profile is then even about 0, so it never crosses it: 0 is the bound
    # on the side toward it.  A modulus within a hundredth of an esd of 0 sits
    # on that bound, the test ``at_bound`` applies to a declared limit
    # (``BOUND_HIT_ESD_FRAC``), and its interval is one-sided like any bounded
    # row's: Self & Liang's mixture holds in m² ≥ 0, where the intensity is
    # linear, and a likelihood ratio does not depend on the parameterisation.
    # On a floor, the open side is m > 0, the principal chart's
    # (``canonical_dofs``).
    on_floor = False
    if row.at_bound is not True and _sign_is_unseen(
            table, path, {p.path for p in result.parameters if p.vary}):
        on_floor = abs(row.value) <= BOUND_HIT_ESD_FRAC * row.stderr
        if on_floor or row.value > 0.0:
            lo = max(lo, 0.0)
        else:
            hi = min(hi, 0.0)

    one_sided = row.at_bound is True or on_floor
    quantile = interval_quantile(level, one_sided)
    stats = result.statistics
    inflation = stats.esd_inflation if stats.esd_inflation is not None else 1.0
    cut = quantile * stats.chi2 * inflation ** 2
    chi2_fit = data_chi2(stats)

    points: list[ParameterIntervalPoint] = []
    ends: dict[int, tuple[float | None, IntervalStop]] = {}
    if on_floor:
        ends[-1] = (0.0, "bound")
    elif one_sided:
        side, end = _bounded_end(result, row, lo, hi)
        ends[side] = (end, "bound")
    # what the fit's answer stage held, kept held by every refit
    frozen = tuple(p for p in (result.stages[-1].held if result.stages else ())
                   if p != path)
    with head_restored(refinement):
        for sign, limit in ((-1, lo), (1, hi)):
            if sign in ends:
                continue
            ends[sign] = _walk(refinement, data, path, row.value, sign, limit,
                               step, cut, chi2_fit, max_refits, points,
                               record=record, cancel=cancel,
                               limit_stop="period" if sign in half_turn else "bound",
                               frozen=frozen)

    lowest = min([chi2_fit, *(p.chi2 for p in points if p.chi2 is not None)])
    (lower, lower_stop), (upper, upper_stop) = ends[-1], ends[1]
    return ParameterInterval(
        path=path, value=row.value, stderr=row.stderr, at_bound=row.at_bound,
        level=level, one_sided=one_sided, quantile=quantile,
        delta_chi2_cut=cut, lower=lower, upper=upper,
        lower_stop=lower_stop, upper_stop=upper_stop,
        chi2_fit=chi2_fit, chi2_lowest=lowest,
        fit_is_minimum=chi2_fit - lowest <= PARAMETER_INTERVAL_CHI2_TOL * cut,
        points=points, n_refits=sum(p.runs for p in points))


def attach_stationary_intervals(refinement, data, *, cancel=None) -> None:
    """Each moment angle the answer stage left out, its interval onto its row.

    The stationary-angle test (WP-1929) leaves an angle at a direction the
    symmetry fixes out of the answer stage's covariance, so the angle has no
    esd.  Under WP-2002's B2 ruling (2026-10-19) it carries its profile
    interval instead.  :func:`profile_interval` runs for each angle of the
    passing round that has a half-width to step from, at the default level,
    and the answer lands on ``RefinedParameter.interval``.  The
    ``MOMENT_ANGLE_STATIONARY`` finding is then rebuilt from the rows in
    place, so it quotes the intervals.

    The refits are the package's own, so they run on a copy of the models
    (``record=False``): the caller's history gains no node and its HEAD does
    not move.  Only a fit whose test passed pays.  Measured on the two-site
    Pnma fixtures (``tests/test_stationary_moment_angle.py``, macOS arm64),
    two to four angles cost 2.6-16.7 s on fits of 0.2-1.2 s, 20-32 refits an
    angle.  ``cancel`` is the fit's token: a stop ends the run between
    refits, and an angle it had not finished keeps ``None``.
    """
    from ..report.magnetic import moment_angle_stationary_diagnostics

    result = refinement.result_
    stage = result.stages[-1] if result is not None and result.stages else None
    tests = getattr(stage, "moment_angle_tests", None) or []
    passed = next((t for t in tests if t.zeroed), None)
    if passed is None:
        return
    rows = {r.path: r for r in result.parameters}
    for path in passed.paths:
        row = rows.get(path)
        # no half-width means no curvature either (``_half_widths``), and so
        # no scale to step the profile in
        if row is None or path not in passed.half_widths:
            continue
        try:
            row.interval = profile_interval(refinement, data, path,
                                            record=False, cancel=cancel)
        except RefinementCancelled:
            break
        except ValueError:
            # a precondition :func:`profile_interval` refuses (a row no longer
            # free, no step to walk in): the fit already returned its answer,
            # so this angle keeps ``None`` and the finding says none was
            # computed, rather than the finished fit raising
            continue
    (rebuilt,) = moment_angle_stationary_diagnostics(stage, result.parameters)
    diagnostics = list(result.diagnostics)
    at = next((i for i, d in enumerate(diagnostics)
               if d.code == "MOMENT_ANGLE_STATIONARY"), None)
    if at is None:
        diagnostics.append(rebuilt)
    else:
        diagnostics[at] = rebuilt
    result.diagnostics = diagnostics
