"""An equation fitted to a series trajectory (WP-2106).

What is checked here, and on what:

* the fit's arithmetic on synthetic trajectories built as data, with no
  refinement: a line against the closed-form weighted least squares, both
  esds against (AᵀWA)⁻¹ and its χ²/ν scaling, a nonlinear equation recovering
  its own truth, a held variable, a bound, and the JSON round-trip;
* every refusal by its message, before any solve;
* which points are read: a quarantined pattern and a point with no esd left
  out and named, and which chain of a ``direction="both"`` series is read.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.common import Diagnostic
from rietx.schemas.results import RefinedParameter
from rietx.schemas.sequential import SeriesEntry, SeriesResult, TrajectoryFit

PATH = "phases.0.cell.a"
TEMPS = [300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]
#: a trajectory that scatters about a line, with uneven esds
VALUES = [4.15660, 4.15871, 4.16074, 4.16290, 4.16488, 4.16702, 4.16905]
ESDS = [4e-5, 5e-5, 3e-5, 4e-5, 6e-5, 4e-5, 5e-5]


def _series(values=VALUES, esds=ESDS, x=TEMPS, *, status=None, direction="forward",
            backward=None) -> SeriesResult:
    status = status or {}
    return SeriesResult(direction=direction, backward=backward, entries=[
        SeriesEntry(index=k, label=f"p{k}", x=t, status=status.get(k, "converged"),
                    parameters=[RefinedParameter(path=PATH, value=v, stderr=s)])
        for k, (v, s, t) in enumerate(zip(values, esds, x, strict=True))])


def _free(value: float, **kw) -> rx.Parameter:
    return rx.Parameter(value=value, vary=True, **kw)


def _weighted_line(x, y, s):
    """The closed form: coefficients, (AᵀWA)⁻¹ and χ² for y = a0 + k·(x − 600)."""
    a = np.column_stack([np.ones(len(x)), np.asarray(x) - 600.0])
    w = 1.0 / np.asarray(s) ** 2
    n = a.T @ (a * w[:, None])
    cov = np.linalg.inv(n)
    coef = cov @ (a.T @ (w * np.asarray(y)))
    r = (np.asarray(y) - a @ coef) / np.asarray(s)
    return coef, cov, float(r @ r)


# ------------------------------------------------------------------ the fit

def test_a_line_is_the_closed_form_weighted_least_squares():
    """Coefficients, both esds and χ² equal the closed form to rounding."""
    fit = rx.fit_trajectory(_series(), PATH, "a0 + k*(x - 600)",
                            {"a0": _free(4.16), "k": _free(0.0)})
    coef, cov, chi2 = _weighted_line(TEMPS, VALUES, ESDS)
    a0, k = fit.variables
    assert (a0.name, k.name) == ("a0", "k")
    assert a0.value == pytest.approx(coef[0], rel=1e-12, abs=1e-12)
    assert k.value == pytest.approx(coef[1], rel=1e-8)
    assert fit.chi2 == pytest.approx(chi2, rel=1e-8)
    assert fit.dof == 5 and fit.reduced_chi2 == pytest.approx(chi2 / 5, rel=1e-8)
    for var, i in ((a0, 0), (k, 1)):
        assert var.esd_unscaled == pytest.approx(math.sqrt(cov[i, i]), rel=1e-8)
        assert var.esd == pytest.approx(math.sqrt(cov[i, i] * chi2 / 5), rel=1e-8)
        assert var.vary and not var.at_bound
    assert np.allclose(fit.covariance, cov * chi2 / 5, rtol=1e-8, atol=0.0)
    assert fit.positions == list(range(7)) and fit.n_points == 7
    assert fit.fitted == pytest.approx([coef[0] + coef[1] * (t - 600) for t in TEMPS])
    assert fit.converged and fit.skipped == []
    assert (fit.chain, fit.series_direction) == ("forward", "forward")


def test_a_nonlinear_equation_recovers_its_own_truth():
    """An Einstein-like term, nonlinear in θ, from values it generated exactly."""
    truth = {"a0": 4.15, "g": 2e-3, "theta": 350.0}
    values = [truth["a0"] + truth["g"] / (math.exp(truth["theta"] / t) - 1) for t in TEMPS]
    fit = rx.fit_trajectory(
        _series(values=values), PATH, "a0 + g/(exp(theta/x) - 1)",
        {"a0": _free(4.16), "g": _free(1e-3), "theta": _free(300.0, min=1.0)})
    got = {v.name: v.value for v in fit.variables}
    for name, want in truth.items():
        assert got[name] == pytest.approx(want, rel=1e-6)
    assert fit.chi2 < 1e-12 and fit.converged


def test_a_held_variable_stays_and_carries_no_esd():
    fit = rx.fit_trajectory(_series(), PATH, "a0 + k*(x - x0)",
                            {"a0": _free(4.16), "k": _free(0.0),
                             "x0": rx.Parameter(value=600.0)})
    held = fit.variables[2]
    assert (held.name, held.value, held.vary) == ("x0", 600.0, False)
    assert held.esd is None and held.esd_unscaled is None
    coef, _, _ = _weighted_line(TEMPS, VALUES, ESDS)
    assert fit.variables[0].value == pytest.approx(coef[0], rel=1e-12)
    assert fit.dof == 5


def test_a_coordinate_table_binds_by_name_in_series_order():
    coords = rx.CoordinateTable(columns={"T": TEMPS, "P": [1.0] * 7}, units={"T": "K"})
    fit = rx.fit_trajectory(_series(x=[float(k) for k in range(7)]), PATH,
                            "a0 + k*(T - 600)*P", {"a0": _free(4.16), "k": _free(0.0)},
                            coordinates=coords)
    coef, _, _ = _weighted_line(TEMPS, VALUES, ESDS)
    assert [v.value for v in fit.variables] == pytest.approx(list(coef), rel=1e-8)


def test_a_variable_on_its_bound_is_named_and_keeps_a_marginal_esd():
    fit = rx.fit_trajectory(_series(), PATH, "a0 + k*(x - 600)",
                            {"a0": _free(4.16), "k": _free(1e-5, max=1e-5)})
    k = fit.variables[1]
    assert k.at_bound and k.value == pytest.approx(1e-5)
    assert k.esd_unscaled is not None and not fit.variables[0].at_bound


def test_no_degree_of_freedom_leaves_the_unscaled_esd_alone():
    fit = rx.fit_trajectory(_series(VALUES[:2], ESDS[:2], TEMPS[:2]), PATH,
                            "a0 + k*(x - 600)", {"a0": _free(4.16), "k": _free(0.0)})
    assert fit.dof == 0 and fit.reduced_chi2 is None and fit.covariance is None
    assert all(v.esd is None and v.esd_unscaled > 0 for v in fit.variables)


def test_the_fit_round_trips_through_json_and_prints_its_chain():
    fit = rx.fit_trajectory(_series(), PATH, "a0 + k*(x - 600)",
                            {"a0": _free(4.16), "k": _free(0.0)})
    assert TrajectoryFit.model_validate_json(fit.model_dump_json()) == fit
    text = str(fit)
    assert "fitted to the forward chain's trajectory (7 points)" in text
    assert "unscaled ±" in text


@pytest.mark.parametrize("expression, variables, kw, fragment", [
    ("a0 + k*T", {"a0": _free(4.0), "k": _free(0.0)}, {},
     "names 'T', which is neither a variable"),
    ("a0 + k*x", {"a0": _free(4.0), "k": _free(0.0), "c": _free(1.0)}, {},
     "'c' is declared but the expression does not name it"),
    ("a0 + x", {"a0": _free(4.0), "x": _free(0.0)}, {}, "also a coordinate column"),
    ("a0 + k*x", {"a0": rx.Parameter(value=4.0), "k": rx.Parameter(value=0.0)}, {},
     "no variable is free"),
    ("a0 + k*x", {"a0": _free(4.0), "k": 0.0}, {}, "declare it as rx.Parameter"),
    ("a0 + log(k*x)", {"a0": _free(4.0), "k": _free(-1.0)}, {}, "not finite at its start"),
    ("a0 + k*T", {"a0": _free(4.0), "k": _free(0.0)},
     {"coordinates": rx.CoordinateTable(columns={"T": TEMPS[:3]})}, "3 rows for a series of 7"),
    ("a0 + k*T", {"a0": _free(4.0), "k": _free(0.0)},
     {"coordinates": rx.CoordinateTable(columns={"T": [*TEMPS[:6], None]})},
     "pattern 6 ('p6') has no value for coordinate 'T'"),
    ("a0 + k*x", {"a0": _free(4.0), "k": _free(0.0)}, {"chain": "sideways"},
     "chain must be 'forward' or 'backward'"),
])
def test_each_refusal_names_its_cause(expression, variables, kw, fragment):
    with pytest.raises(ValueError, match=fragment.replace("(", r"\(").replace(")", r"\)")):
        rx.fit_trajectory(_series(), PATH, expression, variables, **kw)


def test_an_unknown_path_is_refused_with_the_near_miss():
    with pytest.raises(ValueError, match="phases.0.cell.a"):
        rx.fit_trajectory(_series(), "phases.0.cell.aa", "a0 + k*x",
                          {"a0": _free(4.0), "k": _free(0.0)})


def test_more_free_variables_than_points_is_refused():
    with pytest.raises(ValueError, match="2 usable point"):
        rx.fit_trajectory(_series(VALUES[:2], ESDS[:2], TEMPS[:2]), PATH,
                          "a0 + k*x + c*x^2",
                          {"a0": _free(4.0), "k": _free(0.0), "c": _free(0.0)})


# ------------------------------------------------------- which points, which chain

def test_a_quarantined_pattern_and_a_point_with_no_esd_are_left_out_and_named():
    """Both stay out of the fit, as a quarantined pattern stays out of a median.

    Pattern 2 diverged; pattern 4 carries an ``error``-level code (the chain's
    other quarantine trigger); pattern 5 estimated no esd.  The fit equals the
    closed form over the other four.
    """
    series = _series(status={2: "diverged"})
    series.entries[4].diagnostics.append(
        Diagnostic(code="SOME_ERROR", level="error", message="unusable"))
    series.entries[5].parameters[0].stderr = None
    fit = rx.fit_trajectory(series, PATH, "a0 + k*(x - 600)",
                            {"a0": _free(4.16), "k": _free(0.0)})
    assert [(s.position, s.label, s.reason) for s in fit.skipped] == [
        (2, "p2", "quarantined"), (4, "p4", "quarantined"), (5, "p5", "no_esd")]
    keep = [0, 1, 3, 6]
    assert fit.positions == keep
    coef, _, chi2 = _weighted_line([TEMPS[i] for i in keep], [VALUES[i] for i in keep],
                                   [ESDS[i] for i in keep])
    assert [v.value for v in fit.variables] == pytest.approx(list(coef), rel=1e-8)
    assert fit.chi2 == pytest.approx(chi2, rel=1e-8) and fit.dof == 2
    assert "4 points, 3 left out (no_esd, quarantined)" in str(fit)


def test_a_two_way_series_reads_the_forward_chain_unless_asked():
    back = _series(values=[v + 1e-4 for v in VALUES], direction="backward")
    both = _series(direction="both", backward=back)
    expr, start = "a0 + k*(x - 600)", {"a0": _free(4.16), "k": _free(0.0)}
    forward = rx.fit_trajectory(both, PATH, expr, start)
    backward = rx.fit_trajectory(both, PATH, expr, start, chain="backward")
    assert (forward.chain, forward.series_direction) == ("forward", "both")
    assert (backward.chain, backward.series_direction) == ("backward", "both")
    assert backward.variables[0].value - forward.variables[0].value == pytest.approx(1e-4)
    assert rx.fit_trajectory(both, PATH, expr, start, chain="forward") == forward
    assert "backward chain's trajectory" in str(backward)


def test_a_one_way_series_has_only_the_chain_it_ran():
    expr, start = "a0 + k*(x - 600)", {"a0": _free(4.16), "k": _free(0.0)}
    only_back = _series(direction="backward")
    assert rx.fit_trajectory(only_back, PATH, expr, start).chain == "backward"
    with pytest.raises(ValueError, match="ran forward only, so it has no backward chain"):
        rx.fit_trajectory(_series(), PATH, expr, start, chain="backward")
    with pytest.raises(ValueError, match="carries no backward chain"):
        rx.fit_trajectory(_series(direction="both"), PATH, expr, start, chain="backward")


def test_a_coordinate_row_is_the_patterns_index_not_its_position():
    """A pattern that failed on every rung has no entry, so positions and
    pattern indices part: the table's rows follow the patterns as passed."""
    from rietx.schemas.sequential import SeriesFailure

    series = _series()
    del series.entries[3]
    series.failures.append(SeriesFailure(index=3, label="p3", exception="raised"))
    coords = rx.CoordinateTable(columns={"T": TEMPS})
    fit = rx.fit_trajectory(series, PATH, "a0 + k*(T - 600)",
                            {"a0": _free(4.16), "k": _free(0.0)}, coordinates=coords)
    keep = [0, 1, 2, 4, 5, 6]
    assert fit.positions == [0, 1, 2, 3, 4, 5]
    coef, _, _ = _weighted_line([TEMPS[i] for i in keep], [VALUES[i] for i in keep],
                                [ESDS[i] for i in keep])
    assert [v.value for v in fit.variables] == pytest.approx(list(coef), rel=1e-8)
