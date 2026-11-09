"""An equation fitted to one parameter's trajectory across a series (WP-2106).

After a sequential refinement a user often wants a(T), or a strain against a
load, as an equation with coefficients and esds.  GSAS-II works this way: its
equation is a python-syntax string fitted to the sequential results table
after the refinement, never inside a joint residual (``docs/practice.md``
§ A parameter set by an equation the user writes).  :func:`fit_trajectory` is
that fit, over an equation written in the grammar of
:mod:`rietx.params.expression`.

**It is a fit to a trajectory, and the result says so.**  Each point's esd is
conditional on the rest of its own pattern's fit, and a chain's values depend
on the direction it walked (root CLAUDE.md § Series), so the result names the
chain it read.  A joint fit, :func:`rietx.refine_multi` with a
``ParametricEquation``, fits the same equation to the patterns themselves and
is the stronger form (``guides/equation.md``).

**The arithmetic is weighted least squares over one equation.**  Each point
enters as (value − f)/esd, the grammar gives f and its exact derivative in
each variable, and scipy's trust-region solver honours the variables' own
``min`` and ``max``.  The covariance is the package's one normal-matrix solve
(:func:`~rietx.optimize.statistics.normal_factors`), so a direction the
trajectory does not move has no esd rather than a small one.  Two esds are
reported and neither is chosen for the caller: the package's convention,
scaled by χ²/ν, and the unscaled one a caller who trusts each pattern's esd
would quote (:class:`~rietx.schemas.sequential.TrajectoryVariable`).

**Two kinds of point are left out, and each is named.**  A quarantined
pattern (``schemas.sequential._rejected``, the test that keeps it out of the
chain's median) and a point with no positive, finite esd, which has no weight.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal

import numpy as np

from ._nearmiss import did_you_mean
from .params.expression import RESERVED, Expression
from .schemas.common import Parameter
from .schemas.parametric import CoordinateTable
from .schemas.sequential import (
    SeriesResult,
    TrajectoryFit,
    TrajectorySkip,
    TrajectoryVariable,
    _rejected,
)

#: the name the series axis takes in an equation when no coordinate table is passed
SERIES_AXIS_NAME = "x"


def fit_trajectory(series: SeriesResult, path: str, expression: str,
                   variables: Mapping[str, Parameter], *,
                   coordinates: CoordinateTable | None = None,
                   chain: Literal["forward", "backward"] | None = None,
                   ) -> TrajectoryFit:
    """Fit ``expression`` to the trajectory of ``path``, weighted by its esds.

    ``expression`` is text in the expression grammar (``reference/expressions.md``)
    for the value of ``path`` at each pattern.  Its free names are the
    ``variables``, each an :class:`~rietx.schemas.common.Parameter` whose
    ``value`` is the start, ``vary`` whether it is fitted, and ``min``/``max``
    its bounds, and the columns of ``coordinates``.  The table is the one
    :func:`rietx.refine_multi` takes: one row per pattern of the series, in
    the order passed.  Without it the series axis is the one coordinate, named
    ``x`` (:attr:`SeriesResult.x`, the given coordinate or the pattern index).

    ``chain`` picks the trajectory under ``direction="both"``: the forward
    chain by default, or ``"backward"``.  A one-way series has the one chain
    it ran, and asking for the other raises.  ``path`` is any name
    :meth:`SeriesResult.resolve_trajectory` takes, ``qpa.<phase>`` included.

    Raises ``ValueError`` naming the cause: an unknown name in the
    expression, a variable that shadows a column or is never used, no free
    variable, fewer usable points than free variables, a pattern with no
    value for a coordinate the expression uses, or an equation that is not
    finite at its start.  A malformed expression raises
    :class:`~rietx.params.expression.ExpressionError`.
    """
    if not isinstance(series, SeriesResult):
        raise TypeError(f"fit_trajectory takes a SeriesResult, got {type(series).__name__}")
    read, which = _chain(series, chain)
    expr = Expression(expression)
    columns = _columns(read, coordinates)
    variables = dict(variables)
    _check_names(expr, variables, columns)

    traj = read.resolve_trajectory(path)
    if not traj.value:
        hint = did_you_mean(path, read.paths())
        raise ValueError(
            f"{path!r} has no point in the {which} chain's trajectory"
            + (f"; {hint}" if hint else "; list the paths with series.paths()"))
    points: list[tuple[int, float, float]] = []
    skipped: list[TrajectorySkip] = []
    for value, esd, pos, label in zip(traj.value, traj.stderr, traj.positions,
                                      traj.labels, strict=True):
        if _rejected(read.entries[pos]):
            skipped.append(TrajectorySkip(position=pos, label=label, reason="quarantined"))
        elif esd is None or not math.isfinite(esd) or esd <= 0.0 or not math.isfinite(value):
            skipped.append(TrajectorySkip(position=pos, label=label, reason="no_esd"))
        else:
            points.append((pos, value, esd))

    varied = [name for name, p in variables.items() if p.vary]
    if not varied:
        raise ValueError(
            "no variable is free: set vary=True on the ones to fit, as in "
            "rx.Parameter(value=..., vary=True)")
    if len(points) < len(varied):
        raise ValueError(
            f"{len(points)} usable point(s) of {path!r} for {len(varied)} free "
            f"variable(s) ({len(skipped)} left out: quarantined or with no esd); "
            "free fewer variables")

    positions = [pos for pos, _, _ in points]
    y = np.array([v for _, v, _ in points], dtype=np.float64)
    sig = np.array([s for _, _, s in points], dtype=np.float64)
    bindings: dict[str, object] = {}
    for name in expr.names:
        if name in columns:
            bindings[name] = _column_values(name, columns[name], positions, read)
        elif not variables[name].vary:
            bindings[name] = float(variables[name].value)

    x0 = np.array([float(variables[n].value) for n in varied])
    lo = np.array([float(variables[n].min) for n in varied])
    hi = np.array([float(variables[n].max) for n in varied])

    def evaluate(theta: np.ndarray) -> tuple[dict[str, object], np.ndarray]:
        env = {**bindings, **{n: float(t) for n, t in zip(varied, theta, strict=True)}}
        return env, np.broadcast_to(np.asarray(expr.evaluate(env), dtype=np.float64),
                                    y.shape)

    def residual(theta: np.ndarray) -> np.ndarray:
        return (evaluate(theta)[1] - y) / sig

    def jacobian(theta: np.ndarray) -> np.ndarray:
        env, _ = evaluate(theta)
        _, partials = expr.gradient(env, varied)
        return np.column_stack([np.broadcast_to(d, y.shape) for d in partials]) / sig[:, None]

    start = residual(x0)
    if not np.all(np.isfinite(start)):
        bad = positions[int(np.flatnonzero(~np.isfinite(start))[0])]
        raise ValueError(
            f"{expression!r} is not finite at its start at pattern {bad} "
            f"({read.entries[bad].label!r}); start the variables where it is")

    from scipy.optimize import least_squares

    solution = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi),
                             method="trf", x_scale="jac")
    theta = np.asarray(solution.x, dtype=np.float64)
    resid = residual(theta)
    jac = jacobian(theta)
    chi2 = float(resid @ resid)
    dof = len(points) - len(varied)
    reduced = chi2 / dof if dof > 0 else None

    from .optimize.statistics import covariance_from_factors, normal_factors

    # A residual whose χ²/ν is exactly 1, so the factor `normal_factors`
    # applies is 1 and its K is the unscaled inverse of the equilibrated
    # normal matrix; the scaled reading is that times the fit's own χ²/ν.
    unit = np.zeros(len(points))
    unit[0] = math.sqrt(max(dof, 1))
    k, inv_d, _ = normal_factors(jac, unit, len(varied),
                                 what="trajectory fit's covariance residual")
    raw = [float(d * math.sqrt(max(k[i, i], 0.0))) if d > 0.0 else None
           for i, d in enumerate(inv_d)]
    factor = math.sqrt(reduced) if reduced is not None else None
    covariance = (None if reduced is None else
                  (covariance_from_factors(k, inv_d) * reduced).tolist())

    at_bound = np.asarray(solution.active_mask) != 0
    fitted: dict[str, TrajectoryVariable] = {}
    for i, name in enumerate(varied):
        fitted[name] = TrajectoryVariable(
            name=name, value=float(theta[i]), vary=True,
            esd=None if raw[i] is None or factor is None else raw[i] * factor,
            esd_unscaled=raw[i], at_bound=bool(at_bound[i]))
    out = [fitted.get(name) or TrajectoryVariable(
        name=name, value=float(p.value), vary=False, at_bound=False)
        for name, p in variables.items()]

    return TrajectoryFit(
        path=path, expression=expression, chain=which,
        series_direction=series.direction, variables=out, covariance=covariance,
        chi2=chi2, dof=dof, reduced_chi2=reduced, positions=positions,
        fitted=[float(v) for v in evaluate(theta)[1]], skipped=skipped,
        converged=bool(solution.status > 0), message=str(solution.message))


def _chain(series: SeriesResult, chain: str | None) -> tuple[SeriesResult, str]:
    """The chain to read and its name, refusing one the series did not run."""
    direction = series.direction
    if chain is None:
        return series, "backward" if direction == "backward" else "forward"
    if chain not in ("forward", "backward"):
        raise ValueError(f"chain must be 'forward' or 'backward', got {chain!r}")
    if direction == "both":
        if chain == "forward":
            return series, "forward"
        if series.backward is None:
            raise ValueError("this series ran both ways but carries no backward "
                             "chain (series.backward is None)")
        return series.backward, "backward"
    if chain != direction:
        raise ValueError(
            f"this series ran {direction} only, so it has no {chain} chain; "
            "refine_sequential(direction='both') runs both")
    return series, chain


def _columns(read: SeriesResult, coordinates: CoordinateTable | None
             ) -> dict[str, list[float | None]]:
    """Each coordinate a name can bind, as one value per pattern of the series."""
    n = len(read.entries) + len(read.failures)
    if coordinates is None:
        axis: list[float | None] = [None] * max(
            [n, *(e.index + 1 for e in read.entries)])
        for e, x in zip(read.entries, read.x, strict=True):
            axis[e.index] = x
        return {SERIES_AXIS_NAME: axis}
    if not isinstance(coordinates, CoordinateTable):
        raise TypeError(f"coordinates must be an rx.CoordinateTable, got "
                        f"{type(coordinates).__name__}")
    if coordinates.n_patterns != n:
        raise ValueError(
            f"the coordinate table has {coordinates.n_patterns} rows for a series "
            f"of {n} patterns: one row per pattern, in the order passed")
    return dict(coordinates.columns)


def _check_names(expr: Expression, variables: dict[str, Parameter],
                 columns: dict[str, list[float | None]]) -> None:
    """Refuse a name the expression cannot bind, or a variable it cannot use."""
    for name, param in variables.items():
        if not isinstance(param, Parameter):
            raise ValueError(f"variable {name!r} is a {type(param).__name__}: declare "
                             "it as rx.Parameter(value=..., vary=True)")
        if not name.isidentifier() or name in RESERVED:
            raise ValueError(f"variable name {name!r} is not an identifier the "
                             "expression grammar can name; rename it")
        if name in columns:
            raise ValueError(
                f"variable {name!r} is also a coordinate column, so an expression "
                "naming it would be ambiguous; rename one of the two")
    for name in expr.names:
        if name not in variables and name not in columns:
            hint = did_you_mean(name, [*variables, *columns])
            raise ValueError(
                f"the expression {expr.text!r} names {name!r}, which is neither a "
                f"variable (variables=...) nor a coordinate ({', '.join(columns)})"
                + (f"; {hint}" if hint else ""))
    unused = [v for v in variables if v not in expr.names]
    if unused:
        raise ValueError(
            f"variable {unused[0]!r} is declared but the expression does not name "
            "it, so nothing would fit it; leave it out of variables=")


def _column_values(name: str, column: list[float | None], positions: list[int],
                   read: SeriesResult) -> np.ndarray:
    """One coordinate at each fitted point, refusing a point with no value."""
    out = np.empty(len(positions))
    for k, pos in enumerate(positions):
        entry = read.entries[pos]
        v = column[entry.index] if entry.index < len(column) else None
        if v is None:
            raise ValueError(
                f"pattern {entry.index} ({entry.label!r}) has no value for "
                f"coordinate {name!r}, which the expression uses; give it one")
        out[k] = float(v)
    return out
