"""A parametric equation the user writes, with shared variables, on a joint fit
(WP-1964, the task "Variables on a joint fit").

What is checked here, and on what:

* the declaration as data: ``basis="expression"`` round-trips through JSON,
  its text is parsed at construction, and the fields of the linear bases are
  refused beside it;
* every refusal ``MultiParameterTable`` makes of a variable or an expression,
  each by its message, before any solve;
* the wiring without a fit: one shared column per variable however many
  equations name it, each pattern's target set at its own coordinate, and a
  plan's glob on a target freeing the variables it names, bar one declared
  ``vary=False``;
* a five-pattern LaB6 ramp on an Einstein cell edge with θ held at its true
  value, whose two free variables come back within 2 esd of the truth;
* the WP's acceptance row: a ``polynomial`` and the same form written as an
  expression agree to 0.01 esd.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.multi import MultiHistogramRefinement, _joint_fixed_literals, refine_multi
from rietx.params.multi import MultiParameterTable, SharingMap
from rietx.schemas.parametric import CoordinateTable, ParametricEquation
from rietx.strategy.staged import Stage
from rietx.viz.plots import plot_result
from tests.test_multi_histogram import perturbed_inputs
from tests.test_parametric_series import _lab6_instruments

OUT = Path(__file__).parent / "output"
EINSTEIN = "zero_a + grad/(exp(theta/T) - 1)"


def _expression(**kw) -> ParametricEquation:
    base = dict(name="a", target="phases.0.cell.a", basis="expression", expression=EINSTEIN)
    base.update(kw)
    return ParametricEquation(**base)


def _variables(**more) -> dict[str, rx.Parameter]:
    out = {"zero_a": rx.Parameter(value=4.15, vary=True),
           "grad": rx.Parameter(value=0.02, vary=True),
           "theta": rx.Parameter(value=400.0, vary=False, min=20.0, max=1000.0)}
    out.update(more)
    return out


def _coords(n: int, **more) -> CoordinateTable:
    return CoordinateTable(columns={"T": [300.0 + 150.0 * k for k in range(n)], **more},
                           units={"T": "K"})


def _table(n: int = 3, *, parametric=None, variables=None, coordinates=None,
           **kw) -> MultiParameterTable:
    s, _ = perturbed_inputs()
    return MultiParameterTable(
        s, _lab6_instruments(n), coordinates=_coords(n) if coordinates is None else coordinates,
        parametric=[_expression()] if parametric is None else parametric,
        variables=_variables() if variables is None else variables, **kw)


def _plot(result: rx.RefinementResult, name: str, histograms: tuple[int, ...]) -> None:
    OUT.mkdir(exist_ok=True)
    for h in histograms:
        plot_result(result.for_histogram(h), path=str(OUT / f"{name}_h{h}_fit.png"))


# -- the declaration as data -------------------------------------------------

def test_an_expression_equation_round_trips_through_json():
    equation = _expression(patterns=[0, 2])
    text = equation.model_dump_json()
    assert ParametricEquation.model_validate_json(text) == equation
    assert ParametricEquation.model_validate(json.loads(text)) == equation
    # its freedom is the variables it names, so it has no coefficients
    assert (equation.n_coefficients, equation.coefficient_paths()) == (0, [])


@pytest.mark.parametrize("kw, fragment", [
    (dict(expression="zero_a + ("), "ends where an operand is expected"),
    (dict(expression="zero_a + grad*"), "operand"),
    (dict(expression=None), "needs expression"),
    (dict(terms=[[], ["T"]]), "expression basis takes no terms"),
    (dict(design=[[1.0]]), "expression basis takes no design"),
    (dict(reference={"T": 1.0}), "takes no reference"),
    (dict(basis="polynomial", terms=[[], ["T"]]), "polynomial basis takes no expression"),
    (dict(basis="constant"), "constant basis takes no expression"),
])
def test_a_malformed_expression_equation_is_refused_at_construction(kw, fragment):
    with pytest.raises(ValidationError, match=fragment):
        _expression(**kw)


# -- refusals before any solve -----------------------------------------------

@pytest.mark.parametrize("build, fragment", [
    (lambda: _table(variables=_variables(exp=rx.Parameter(value=1.0))),
     "'exp' is a reserved word"),
    (lambda: _table(variables=_variables(**{"2x": rx.Parameter(value=1.0)})),
     "must be a single identifier"),
    (lambda: _table(variables=_variables(T=rx.Parameter(value=1.0))),
     "a coordinate may not shadow a variable"),
    (lambda: _table(variables=_variables(spare=rx.Parameter(value=1.0))),
     "'spare' is declared but no expression equation names it"),
    (lambda: _table(parametric=[], variables=_variables()),
     "'zero_a' is declared but no expression equation names it"),
    (lambda: _table(variables=_variables(grad=0.02)),
     "declare it as rx.Parameter"),
    (lambda: _table(parametric=[
        _expression(expression=EINSTEIN + " + 0*z_0"),
        ParametricEquation(name="z", target="instrument.profile.w", basis="constant")],
        variables=_variables(z_0=rx.Parameter(value=1.0))),
     r"vars.z_0 already exists"),
    (lambda: _table(parametric=[_expression(expression="zero_a + grd/(exp(theta/T) - 1)")]),
     r"names 'grd', which is neither a variable.*did you mean 'grad'"),
    (lambda: _table(coordinates=CoordinateTable(columns={"T": [300.0, None, 500.0]})),
     "pattern 1 has no value for coordinate 'T'"),
    (lambda: _table(sharing=SharingMap(per_histogram=["vars.*"])),
     "makes vars.zero_a per-histogram"),
    (lambda: _table(parametric=[_expression(target="phases.0.cell.b")]),
     r"is tied: = 1·phases.0.cell.a"),
    (lambda: _table(parametric=[_expression(target="phases.0.cell.q")]),
     "is not a parameter of histogram 0"),
    (lambda: _table(parametric=[_expression(target="phases.0.atoms.0.x")]), "locked"),
    (lambda: _table(parametric=[_expression(patterns=[0, 5])]), "out of range"),
    (lambda: _table(coordinates=_coords(2)), "2 rows for 3 patterns"),
    (lambda: _table(parametric=[_expression(), ParametricEquation(
        name="b", target="phases.0.cell.a", basis="constant", patterns=[2])]),
     "both drive phases.0.cell.a on pattern 2"),
], ids=["reserved", "identifier", "shadow", "unused", "no-equation", "not-parameter",
        "path-exists", "unbound", "coordinate-hole", "sharing", "tied-target",
        "unknown-target", "locked-target", "subset-range", "table-length", "clash"])
def test_each_refusal_of_a_variable_or_an_expression_names_its_fix(build, fragment):
    with pytest.raises(ValueError, match=fragment):
        build()


def test_a_size_target_across_wavelengths_is_refused_for_an_expression():
    s, ins = perturbed_inputs()                  # 0.41390 and 0.71070 Å
    with pytest.raises(ValueError, match=r"crystallite-size.*0\.4139, 0\.7107 Å"):
        MultiParameterTable(s, ins, coordinates=_coords(2), variables=_variables(),
                            parametric=[_expression(target="phases.0.lor_size")])


# -- the wiring, without a fit -----------------------------------------------

def test_each_pattern_reads_its_own_coordinate_and_the_followers_go_with_it():
    mt = _table()
    assert mt.parametric == [] and [r.name for r in mt.expressions] == ["a"]
    assert all(mt.sharing.is_shared(p) for p in ("vars.zero_a", "vars.grad", "vars.theta"))
    assert not any(mt.sharing.is_shared(f"phases.0.cell.{k}") for k in "abc")
    for h, t in enumerate(mt.tables):
        temp = 300.0 + 150.0 * h
        want = 4.15 + 0.02 / np.expm1(400.0 / temp)
        values = t.decode(t.x0())
        for k in "abc":
            assert values[f"phases.0.cell.{k}"] == pytest.approx(want, rel=1e-14)


def test_one_variable_named_by_two_equations_is_one_column():
    biso = ParametricEquation(name="b", target="phases.0.atoms.0.biso", basis="expression",
                              expression="b1*debye(theta/T)")
    mt = _table(parametric=[_expression(), biso],
                variables=_variables(theta=rx.Parameter(value=400.0, vary=True),
                                     b1=rx.Parameter(value=0.5, vary=True)))
    mt.set_vary(["*"], False)
    freed = mt.set_vary(["phases.*.cell.*", "phases.0.atoms.0.biso"], True)
    assert sorted(freed) == ["vars.b1", "vars.grad", "vars.theta", "vars.zero_a"]
    assert mt.shared_paths.count("vars.theta") == 1
    assert len(mt.free_paths) == 4
    # each table's θ column reaches both targets: the cell edge and the Biso
    for t in mt.tables:
        reach = t.column_reach()["vars.theta"]
        assert {"phases.0.cell.a", "phases.0.atoms.0.biso"} <= set(reach)


def test_a_glob_on_the_target_frees_the_variables_bar_a_fixed_one():
    mt = _table()
    mt.set_vary(["*"], False)
    assert mt.set_vary(["phases.*.cell.*"], True) == ["vars.zero_a", "vars.grad"]
    assert mt.free_paths == ["vars.zero_a", "vars.grad"]
    mt.set_vary(["*"], False)
    # scoped to one histogram, the glob still reaches the equation
    assert mt.set_vary(["hist.1.phases.0.cell.a"], True) == ["vars.zero_a", "vars.grad"]
    # a glob naming the fixed variable itself frees it
    assert mt.set_vary(["vars.theta"], True) == ["vars.theta"]
    # a plan's literal on the target is not "a row the stage cannot free"
    assert _joint_fixed_literals([Stage(name="cell", turn_on=["phases.0.cell.a"])], mt) == []


def test_the_refinement_lists_an_expression_equation_in_the_order_declared():
    s, _ = perturbed_inputs()
    line = ParametricEquation(name="w", target="instrument.profile.w", basis="polynomial",
                              terms=[[], ["T"]])
    ref = MultiHistogramRefinement(s, _lab6_instruments(3), coordinates=_coords(3),
                                   parametric=[_expression(), line], variables=_variables())
    a, w = ref.parametric
    assert a == _expression()
    assert w.name == "w" and w.reference == {"T": 450.0}


# -- joint fits on a synthetic LaB6 ramp -------------------------------------

def _ramp(cells: list[float], seed: int):
    from tests.test_sequential import _simulate

    return [_simulate(float(a), seed=seed + k) for k, a in enumerate(cells)]


@pytest.mark.xdist_group("parametric-expression")
def test_an_einstein_cell_with_theta_held_recovers_its_two_variables():
    """Five patterns, 300-1200 K, a(T) = zero_a + grad/(exp(θ/T) - 1) with
    θ = 400 K held at its truth.  Measured (macOS arm64): 0.5 s, zero_a 0.002
    esd and grad 0.9 esd from the truth."""
    from tests.test_sequential import A0, _start_models

    temps = [300.0, 525.0, 750.0, 975.0, 1200.0]
    zero_a, grad, theta = A0, 0.02, 400.0
    patterns = _ramp([zero_a + grad / np.expm1(theta / t) for t in temps], seed=20)
    structure, ins = _start_models()
    variables = {"zero_a": rx.Parameter(value=A0 * 1.001, vary=True),
                 "grad": rx.Parameter(value=0.01, vary=True),
                 "theta": rx.Parameter(value=theta, vary=False, min=20.0, max=1000.0)}
    ref = MultiHistogramRefinement(
        structure, [ins] * len(temps),
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        variables=variables, parametric=[_expression()])
    result = ref.fit(patterns, plan="mccusker_default")
    _plot(result, "parametric_expression_einstein", (0, len(temps) - 1))
    assert result.status == "converged"
    rows = {p.path: p for p in result.parameters}
    for path, truth in (("vars.zero_a", zero_a), ("vars.grad", grad)):
        row = rows[path]
        assert row.stderr is not None and row.stderr > 0.0, path
        assert abs(row.value - truth) < 2 * row.stderr, (path, row.value, row.stderr, truth)
    # θ was never free, so it stays at its declared value and is not a row
    assert "vars.theta" not in rows
    t0 = ref.mtable.tables[0]
    assert t0.entries[t0._paths["vars.theta"]].value == theta
    cell = next(st for st in result.stages if st.name == "cell")
    assert cell.freed == ["vars.zero_a", "vars.grad"]
    # each pattern's cell edge is the equation at its own temperature
    for h, temp in enumerate(temps):
        a = rows[f"hist.{h}.phases.0.cell.a"].value
        assert a == pytest.approx(rows["vars.zero_a"].value
                                  + rows["vars.grad"].value / np.expm1(theta / temp),
                                  rel=1e-13)


@pytest.mark.xdist_group("parametric-expression")
def test_a_polynomial_and_the_same_form_as_an_expression_agree_to_a_hundredth_esd():
    """The WP's acceptance row.  A line in T on a five-pattern ramp, declared
    once as ``polynomial`` [[], ["T"]] and once as ``c0 + c1*(T - ref)/scale``
    with the polynomial's resolved reference and scale: one model in two
    spellings, so both coefficients and every pattern's cell agree to 0.01 of
    their esd.  Measured (macOS arm64): 8e-10 esd at most, and the esds agree
    to 1.3e-10 relative."""
    from tests.test_sequential import A0, RAMP, _start_models

    temps = [300.0, 525.0, 750.0, 975.0, 1200.0]
    patterns = _ramp([A0 * (1.0 + RAMP * (t - 300.0) / 100.0) for t in temps], seed=40)
    coords = CoordinateTable(columns={"T": temps}, units={"T": "K"})
    sharing = SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"])

    structure, ins = _start_models()
    poly = MultiHistogramRefinement(
        structure, [ins] * len(temps), sharing=sharing, coordinates=coords,
        parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="polynomial", terms=[[], ["T"]])])
    (resolved,) = poly.parametric
    ref, scale = resolved.reference["T"], resolved.scale["T"]
    assert (ref, scale) == (750.0, 450.0)
    by_poly = poly.fit(patterns, plan="mccusker_default")

    structure, ins = _start_models()
    start = structure.phases[0].cell.a.value
    # the § Goal spelling: refine_multi takes variables= beside coordinates=
    by_expr = refine_multi(
        patterns, structure, [ins] * len(temps), plan="mccusker_default",
        sharing=SharingMap(shared=list(sharing.shared)), coordinates=coords,
        variables={"c0": rx.Parameter(value=start, vary=True),
                   "c1": rx.Parameter(value=0.0, vary=True)},
        parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="expression",
                                       expression=f"c0 + c1*(T - {ref:g})/{scale:g}")])
    _plot(by_expr, "parametric_expression_line", (0, len(temps) - 1))
    assert by_poly.status == by_expr.status == "converged"

    p = {r.path: r for r in by_poly.parameters}
    e = {r.path: r for r in by_expr.parameters}
    for mine, theirs in (("vars.c0", "vars.a_0"), ("vars.c1", "vars.a_1")):
        esd = p[theirs].stderr
        assert abs(e[mine].value - p[theirs].value) < 0.01 * esd, (mine, e[mine], p[theirs])
        assert e[mine].stderr == pytest.approx(esd, rel=0.01)
    for h in range(len(temps)):
        path = f"hist.{h}.phases.0.cell.a"
        assert abs(e[path].value - p[path].value) < 0.01 * p[path].stderr, path
