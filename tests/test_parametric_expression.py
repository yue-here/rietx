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
  expression agree to 0.01 esd;
* an equation feeding an equation: an intermediate (``target=None``) as data,
  each refusal of a cycle or an ambiguous name, the wiring at nonzero
  calibration coefficients, one intermediate feeding two targets, and a
  temperature calibration recovered by a joint fit.
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
        "path-exists", "unbound", "coordinate-hole", "tied-target",
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
    # the rows the equation sets name it: its variables, and each pattern's
    # target with the b and c that follow it (§ Inherited, the third reader)
    for path in ("vars.zero_a", "vars.grad",
                 *(f"hist.{h}.phases.0.cell.{k}" for h in range(len(temps)) for k in "abc")):
        if path in rows:
            assert rows[path].equations == ["a"], path
    assert rows["hist.0.phases.0.cell.a"].equations == ["a"]
    # the variables are the equation's rows in result.parametric, θ held
    by_term = {c.term: c for c in result.parametric}
    assert list(by_term) == ["zero_a", "grad", "theta"]
    for term in ("zero_a", "grad"):
        c = by_term[term]
        assert (c.equation, c.target, c.path) == ("a", "phases.0.cell.a", f"vars.{term}")
        assert c.vary and c.value == rows[c.path].value and c.esd == rows[c.path].stderr
        assert c.reference is None
    assert not by_term["theta"].vary and by_term["theta"].esd is None
    assert by_term["theta"].value == theta
    # evaluated anywhere through its gradient: at a pattern, the row's value
    # and esd; between two, inside the span; past the last, extrapolating
    (eq,) = result.parametric_equations
    for h, temp in enumerate(temps):
        v = eq.evaluate(result.parametric, coordinates={"T": temp})
        row = rows[f"hist.{h}.phases.0.cell.a"]
        assert v.value == pytest.approx(row.value, rel=1e-13)
        assert v.esd == pytest.approx(row.stderr, rel=1e-6), h
        assert v.outside == [] and v.unit == "Å"
    assert eq.evaluate(result.parametric, coordinates={"T": 1500.0}).outside == ["T"]
    printed = str(result)
    assert "[grad]" in printed and "[theta] 400 (not free at the answer)" in printed
    named ={p.path for p in result.parameters if p.equations}
    assert named == {p.path for p in result.parameters
                     if p.path.startswith("vars.") or ".phases.0.cell." in p.path}
    # the form test reads the expression through its gradient (§ Inherited,
    # the second reader): the right form passes in every pattern, and an
    # evaluated value carries the verdict
    (form,) = result.parametric_form
    assert (form.equation, form.n_patterns, form.n_subset) == ("a", 5, 5)
    assert form.tied.dof == 3 and form.rejected is False
    v = eq.evaluate(result.parametric, form, coordinates={"T": 600.0})
    assert v.form_rejected is False


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
    # one model, one form test: the gradient reading of the expression and the
    # Φ reading of the polynomial agree.  Measured (macOS arm64): 6.8e-11
    # relative on the statistic, where a wrong target column is off by O(1)
    (fp,), (fe,) = by_poly.parametric_form, by_expr.parametric_form
    assert (fe.n_patterns, fe.tied.dof) == (fp.n_patterns, fp.tied.dof) == (5, 3)
    assert fe.tied.statistic == pytest.approx(fp.tied.statistic, rel=1e-6)
    assert fe.rejected is fp.rejected is False


@pytest.mark.xdist_group("parametric-expression")
def test_a_line_written_over_an_einstein_cell_is_rejected_by_the_form_test():
    """The Einstein ramp of the test above, declared as ``c0 + c1*T``.  The
    form test frees the cell in each pattern and finds the bend.  Measured
    (macOS arm64): 17222 times χ²_red for 3 directions, against the cut 7.8,
    where the Einstein expression itself reads 1.2."""
    from tests.test_sequential import A0, _start_models

    temps = [300.0, 525.0, 750.0, 975.0, 1200.0]
    patterns = _ramp([A0 + 0.02 / np.expm1(400.0 / t) for t in temps], seed=20)
    structure, ins = _start_models()
    result = refine_multi(
        patterns, structure, [ins] * len(temps), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        variables={"c0": rx.Parameter(value=A0, vary=True),
                   "c1": rx.Parameter(value=0.0, vary=True)},
        parametric=[_expression(expression="c0 + c1*T")])
    _plot(result, "parametric_expression_wrong_form", (0, len(temps) - 1))
    (form,) = result.parametric_form
    assert form.rejected is True and form.n_patterns == 5
    assert form.tied.statistic > 100 * form.tied.cut
    (d,) = [d for d in result.diagnostics if d.code == "PARAMETRIC_FORM_REJECTED"]
    assert d.where == ["vars.c0", "vars.c1"]
    assert d.suggestion.startswith("Revise the expression")


def test_targets_sharing_a_variable_are_recovered_together():
    """``expression_target_columns`` on a Jacobian built as J_V = T·G: two
    targets reading one shared ``th``, so neither's column is any one
    variable's.  T comes back to rounding.  A pattern ``usable`` refuses, or
    whose G has fewer directions than targets (the two intercepts held), gives
    no column, and an equation with no free variable gives ``None``."""
    from rietx.optimize.blocked import BlockJacobian
    from rietx.params.expression import Expression
    from rietx.params.multi import ResolvedExpression
    from rietx.params.parametric import expression_target_columns

    def resolved(name, text, variables):
        return ResolvedExpression(
            equation=ParametricEquation(name=name, target=f"phases.0.{name}", basis="expression",
                                        expression=text),
            patterns=[0, 1], expression=Expression(text), variables=variables,
            coordinates=["T"], constants={0: {"T": 300.0}, 1: {"T": 900.0}})

    exprs = [resolved("a", "a0 + exp(-th/T)", ["a0", "th"]),
             resolved("b", "b0 + 2*th*T", ["b0", "th"])]
    values = {"vars.a0": 1.0, "vars.b0": 2.0, "vars.th": 150.0}
    rng = np.random.default_rng(7)
    free = ["vars.a0", "vars.b0", "vars.th"]
    blocks, truth = [], []
    for temp in (300.0, 900.0):
        g = np.array([[1.0, 0.0, -np.exp(-150.0 / temp) / temp],
                      [0.0, 1.0, 2.0 * temp]])
        t = rng.standard_normal((40, 2))
        blocks.append(t @ g)
        truth.append(t)
    bj = BlockJacobian(blocks, [[0, 1, 2], [0, 1, 2]], [40, 40], [0, 0], 3)
    cols = expression_target_columns(exprs, bj, free, values, [True, True], {})
    for i in range(2):
        for h in range(2):
            assert np.max(np.abs(cols[i][h][:, 0] - truth[h][:, i])) < 1e-12
    cols = expression_target_columns(exprs, bj, free, values, [True, False],
                                     {"b": frozenset({0})})
    assert cols[0][1] is None and cols[1][1] is None and cols[1][0] is None
    assert cols[0][0] is not None
    # with a0 and b0 held, G's rows are both multiples of th's: one direction
    held = BlockJacobian([b[:, 2:] for b in blocks], [[0], [0]], [40, 40], [0, 0], 1)
    cols = expression_target_columns(exprs, held, ["vars.th"], values, [True, True], {})
    assert cols == [[None, None], [None, None]]
    assert expression_target_columns(exprs[:1], held, ["vars.b0"], values,
                                     [True, True], {}) == [None]
    # a G row of ~1e-174 (exp(-th/T) at th/T = 400) squares to a zero norm;
    # the cut is still made and the target still recovered
    cold = [ResolvedExpression(
        equation=exprs[0].equation, patterns=[0], expression=exprs[0].expression,
        variables=["a0", "th"], coordinates=["T"], constants={0: {"T": 0.375}})]
    g = -np.exp(-400.0) / 0.375
    t = rng.standard_normal(40)
    tiny = BlockJacobian([(t * g)[:, None]], [[0]], [40], [0], 1)
    cols = expression_target_columns(cold, tiny, ["vars.th"], values, [True], {})
    assert np.max(np.abs(cols[0][0][:, 0] - t)) < 1e-12


# -- intervals and minima (task 9) --------------------------------------------
#
# Two synthetic ramps with a known truth, the order parameter through T_c and
# an Avrami fraction against time.  Over 100 seeds each the 2-esd interval's
# coverage is measured by ``docs/wp/1964-measure/coverage.py``; these rows pin
# one seed each, so a change to the machinery that moves the answer shows.

ORDER = "a0 + k*(T - 300) + A*if(T < Tc, (1 - T/Tc)^(2*beta), 0)"
AVRAMI = "S*(1 - exp(-(kr*t)^n))"


def _exact_start():
    """The starting model with Biso at the simulation's 0.4, so the model is
    exact and a variable's error is the noise's alone."""
    from tests.test_sequential import _start_models

    structure, ins = _start_models()
    for atom in structure.phases[0].atoms:
        atom.biso.value = 0.4
    return structure, ins


@pytest.mark.xdist_group("parametric-expression")
def test_an_order_parameter_through_its_transition_recovers_tc_and_beta():
    """Twelve patterns, 300-1070 K, a(T) = a0 + k·(T - 300) + A·(1 - T/T_c)^(2β)
    below T_c and the line above, with T_c = 830 K between the patterns at 790
    and 860 K.  All five variables free, T_c started above the truth.
    Measured (macOS arm64), seed 0: 2 s, every variable within 0.75 esd,
    T_c = 829.79(38) K and β = 0.2998(7)."""
    from tests.test_sequential import A0, _simulate

    temps = [300.0 + 70.0 * i for i in range(12)]
    truth = {"a0": A0, "k": A0 * 5e-6, "A": 0.004, "Tc": 830.0, "beta": 0.3}

    def cell(t):
        q = truth["A"] * (1 - t / truth["Tc"]) ** (2 * truth["beta"]) if t < truth["Tc"] else 0
        return truth["a0"] + truth["k"] * (t - 300) + q

    patterns = [_simulate(cell(t), seed=k) for k, t in enumerate(temps)]
    structure, ins = _exact_start()
    result = refine_multi(
        patterns, structure, [ins] * len(temps), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        variables={"a0": rx.Parameter(value=A0 * 1.0005, vary=True),
                   "k": rx.Parameter(value=A0 * 4e-6, vary=True),
                   "A": rx.Parameter(value=0.003, vary=True, min=0.0, max=0.05),
                   "Tc": rx.Parameter(value=870.0, vary=True, min=500.0, max=1100.0),
                   "beta": rx.Parameter(value=0.35, vary=True, min=0.05, max=1.0)},
        parametric=[_expression(expression=ORDER)])
    _plot(result, "parametric_expression_order", (0, 7, len(temps) - 1))
    assert result.status == "converged"
    rows = {p.path: p for p in result.parameters}
    for name, value in truth.items():
        row = rows[f"vars.{name}"]
        assert abs(row.value - value) < 2 * row.stderr, (name, row.value, row.stderr)


@pytest.mark.xdist_group("parametric-expression")
def test_an_avrami_fraction_recovers_its_rate_and_exponent():
    """Twelve patterns, t = 200-1300 s, the phase's scale S·(1 - exp(-(k·t)^n))
    with k = 1/600 s⁻¹ and n = 2, from 10 % to 99 % of S.  Measured (macOS
    arm64), seed 0: 2 s, every variable within 0.35 esd."""
    from tests.test_sequential import A0, TRUE_SCALE, _simulate

    times = [200.0 + 100.0 * i for i in range(12)]
    truth = {"S": TRUE_SCALE, "kr": 1.0 / 600.0, "n": 2.0}
    patterns = [_simulate(A0, scale=truth["S"] * (1 - np.exp(-(truth["kr"] * t) ** truth["n"])),
                          seed=k) for k, t in enumerate(times)]
    structure, ins = _exact_start()
    for name in "abc":
        getattr(structure.phases[0].cell, name).value = A0
    result = refine_multi(
        patterns, structure, [ins] * len(times), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"t": times}, units={"t": "s"}),
        variables={"S": rx.Parameter(value=TRUE_SCALE * 1.2, vary=True, min=0.0),
                   "kr": rx.Parameter(value=1.0 / 500.0, vary=True, min=1e-5, max=1.0),
                   "n": rx.Parameter(value=1.6, vary=True, min=0.5, max=4.0)},
        parametric=[_expression(target="phases.0.scale", expression=AVRAMI)])
    _plot(result, "parametric_expression_avrami", (0, len(times) - 1))
    assert result.status == "converged"
    rows = {p.path: p for p in result.parameters}
    for name, value in truth.items():
        row = rows[f"vars.{name}"]
        assert abs(row.value - value) < 2 * row.stderr, (name, row.value, row.stderr)


# -- an equation feeding an equation -----------------------------------------
#
# ZrP2O7's temperature calibration: the sample's true temperature is the
# setpoint corrected, T_true = T + c0 + c1*T, and the cell follows T_true.  The
# calibration coefficients are nonzero throughout, because a feed that never
# reached the downstream equation gives the right cell at c0 = c1 = 0.

CALIBRATION = "T + c0 + c1*T"
C0, C1 = 12.5, 0.03


def _calibration(**kw) -> ParametricEquation:
    base = dict(name="T_true", basis="expression", expression=CALIBRATION)
    base.update(kw)
    return ParametricEquation(**base)


def _fed(**kw) -> ParametricEquation:
    base = dict(name="a", target="phases.0.cell.a", basis="expression",
                expression="a0 + k*T_true")
    base.update(kw)
    return ParametricEquation(**base)


def _fed_variables(**more) -> dict[str, rx.Parameter]:
    out = {"a0": rx.Parameter(value=4.15, vary=True),
           "k": rx.Parameter(value=2e-5, vary=True),
           "c0": rx.Parameter(value=C0, vary=True),
           "c1": rx.Parameter(value=C1, vary=True)}
    out.update(more)
    return out


def _fed_table(n: int = 3, *, parametric=None, variables=None, coordinates=None
               ) -> MultiParameterTable:
    return _table(n, parametric=[_calibration(), _fed()] if parametric is None else parametric,
                  variables=_fed_variables() if variables is None else variables,
                  coordinates=coordinates)


def test_an_intermediate_round_trips_and_only_an_expression_can_be_one():
    equation = _calibration()
    assert equation.target is None
    text = equation.model_dump_json()
    assert ParametricEquation.model_validate_json(text) == equation
    assert ParametricEquation.model_validate(json.loads(text)) == equation
    with pytest.raises(ValidationError, match="a polynomial basis needs a target"):
        ParametricEquation(name="w", basis="polynomial", terms=[[], ["T"]])
    with pytest.raises(ValidationError, match="a constant basis needs a target"):
        ParametricEquation(name="w", basis="constant")
    with pytest.raises(ValidationError, match="is an intermediate .* takes no patterns"):
        _calibration(patterns=[0, 1])


@pytest.mark.parametrize("parametric, variables, fragment", [
    ([_calibration(expression="T + c0 + c1*T_true"), _fed()], None,
     r"'T_true': its expression .* names 'T_true', the equation itself; "
     "an equation cannot use itself"),
    ([_fed(), _calibration()], None,
     r"'a': its expression names 'T_true', which is declared after 'a'; "
     "declare it first"),
    ([_calibration(expression="T + c0 + c1*T + 0*a"), _fed()], None,
     r"names 'a', which is declared after 'T_true'"),
    ([ParametricEquation(name="w0", target="instrument.profile.w", basis="constant"),
      _calibration(expression="T + c0 + c1*T + 0*w0"), _fed()], None,
     "names 'w0', a parametric equation with a linear basis; only expression "
     "equations can be named"),
    ([_calibration(name="c1"), _fed(expression="a0 + k*c1")], None,
     "parametric equation 'c1' has the name of a variable"),
    ([_calibration(name="T"), _fed(expression="a0 + k*T")], None,
     "parametric equation 'T' has the name of a coordinate column"),
    ([_calibration(name="sqrt"), _fed(expression="a0 + k*T")], None,
     "parametric equation name 'sqrt' is a reserved word"),
    ([_calibration(), _fed(expression="a0 + k*T")], None,
     "'T_true' has no target and no later expression equation names it"),
    ([_calibration(), _fed(expression="a0 + k*T_ture")], None,
     r"names 'T_ture', which is neither a variable.*did you mean 'T_true'"),
    # each passes alone (51 and 16 levels); written in, the tree is 69 deep
    ([_calibration(expression="T + " + " + ".join(["c0"] * 50)),
      _fed(expression="a0" + " + k*T_true" * 15)], None,
     r"parametric equation 'a': with \['T_true'\] written in, its formula is too "
     "(deep|long)"),
], ids=["itself", "later", "later-target", "linear", "variable-name", "coordinate-name",
        "reserved-name", "idle", "near-miss", "inlined-too-deep"])
def test_each_refusal_of_an_equation_feeding_another_names_its_fix(parametric, variables,
                                                                   fragment):
    with pytest.raises(ValueError, match=fragment):
        _fed_table(parametric=parametric, variables=variables)


def test_a_coordinate_an_intermediate_uses_is_checked_at_the_patterns_it_feeds():
    holes = CoordinateTable(columns={"T": [300.0, None, 600.0]}, units={"T": "K"})
    with pytest.raises(ValueError, match="pattern 1 has no value for coordinate 'T', "
                                         "which the expression uses through 'T_true'"):
        _fed_table(coordinates=holes)
    # the downstream subset leaves the hole out, so the intermediate needs no T there
    mt = _fed_table(coordinates=holes, parametric=[_calibration(), _fed(patterns=[0, 2])])
    assert [r.patterns for r in mt.expressions] == [[0, 2]]


def test_an_intermediate_feeds_the_cell_at_each_patterns_coordinate():
    """``T_true = T + c0 + c1*T`` feeding ``a = a0 + k*T_true`` at c0 = 12.5 K and
    c1 = 0.03.  Each pattern's cell edge is the hand evaluation, and its row of
    the local Jacobian carries ∂a/∂c1 = k·T exactly: the feed reaches."""
    mt = _fed_table()
    assert [r.name for r in mt.intermediates] == ["T_true"]
    assert [r.name for r in mt.expressions] == ["a"]
    assert [e.name for e in mt.declared] == ["T_true", "a"]
    assert mt.declared[0] == _calibration()          # as written, not inlined
    # the downstream tree names variables and coordinates alone
    assert set(mt.expressions[0].expression.names) == {"a0", "k", "T", "c0", "c1"}
    assert mt.expressions[0].paths == ["vars.a0", "vars.k", "vars.c0", "vars.c1"]
    # a glob on the cell frees the variables only the intermediate names, too
    mt.set_vary(["*"], False)
    assert sorted(mt.set_vary(["phases.*.cell.*"], True)) == [
        "vars.a0", "vars.c0", "vars.c1", "vars.k"]
    for h, t in enumerate(mt.tables):
        temp = 300.0 + 150.0 * h
        want = 4.15 + 2e-5 * (temp + C0 + C1 * temp)
        theta = t.x0()
        values = t.decode(theta)
        for edge in "abc":
            assert values[f"phases.0.cell.{edge}"] == pytest.approx(want, rel=1e-12)
        jac = t.local_jacobian(theta).toarray()
        row = jac[t._paths["phases.0.cell.a"]]
        d_c1 = row[t.free_paths.index("vars.c1")]
        assert d_c1 != 0.0
        assert d_c1 == pytest.approx(2e-5 * temp, rel=1e-12)
        assert row[t.free_paths.index("vars.c0")] == pytest.approx(2e-5, rel=1e-12)


def test_one_intermediate_feeds_two_equations():
    """One calibration feeds a cell edge and a Biso, so one c1 column reaches
    both targets in every pattern."""
    biso = ParametricEquation(name="b", target="phases.0.atoms.0.biso", basis="expression",
                              expression="b0 + b1*T_true")
    mt = _fed_table(parametric=[_calibration(), _fed(), biso],
                    variables=_fed_variables(b0=rx.Parameter(value=0.3, vary=True),
                                             b1=rx.Parameter(value=2e-4, vary=False)))
    assert [r.name for r in mt.expressions] == ["a", "b"]
    # the Biso's glob frees the calibration with it, bar b1, declared vary=False
    mt.set_vary(["*"], False)
    assert sorted(mt.set_vary(["phases.0.atoms.0.biso"], True)) == [
        "vars.b0", "vars.c0", "vars.c1"]
    for h, t in enumerate(mt.tables):
        temp = 300.0 + 150.0 * h
        t_true = temp + C0 + C1 * temp
        values = t.decode(t.x0())
        assert values["phases.0.cell.a"] == pytest.approx(4.15 + 2e-5 * t_true, rel=1e-12)
        assert values["phases.0.atoms.0.biso"] == pytest.approx(0.3 + 2e-4 * t_true,
                                                                rel=1e-12)
        reach = set(t.column_reach()["vars.c1"])
        assert {"phases.0.cell.a", "phases.0.atoms.0.biso"} <= reach


def test_the_refinement_lists_an_intermediate_in_its_place():
    s, _ = perturbed_inputs()
    ref = MultiHistogramRefinement(s, _lab6_instruments(3), coordinates=_coords(3),
                                   parametric=[_calibration(), _fed()],
                                   variables=_fed_variables())
    assert ref.parametric == [_calibration(), _fed()]


@pytest.mark.xdist_group("parametric-expression")
def test_a_temperature_calibration_feeding_the_cell_recovers_its_coefficients():
    """Five patterns, 300-1200 K, simulated at a = a0 + k·T_true with
    T_true = T + c0 + c1·T, c0 = 15 K and c1 = 0.02.

    k is held at its truth, as a calibration against a known expansion
    coefficient does.  a0 is held too: a = (a0 + k·c0) + k·(1 + c1)·T is a
    line in T, so the patterns measure its intercept and slope, and a0 and c0
    enter the intercept only as a0 + k·c0, one direction no data separates.
    With a0 and k held, c0 is the intercept and c1 the slope, both
    identifiable.  Both start at zero, so the fit has to move them through
    the feed.  Measured (macOS arm64): 0.5 s, c0 = 15.10(15) K at 0.7 esd and
    c1 = 0.01989(13) at 0.9 esd from the truth."""
    from tests.test_sequential import A0, _start_models

    temps = [300.0, 525.0, 750.0, 975.0, 1200.0]
    k = A0 * 5e-6                                  # the ramp's 5e-4 per 100 K
    a0, c0, c1 = A0 - k * 300.0, 15.0, 0.02
    patterns = _ramp([a0 + k * (t + c0 + c1 * t) for t in temps], seed=60)
    structure, ins = _start_models()
    variables = {"a0": rx.Parameter(value=a0, vary=False),
                 "k": rx.Parameter(value=k, vary=False),
                 "c0": rx.Parameter(value=0.0, vary=True),
                 "c1": rx.Parameter(value=0.0, vary=True)}
    ref = MultiHistogramRefinement(
        structure, [ins] * len(temps),
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        variables=variables, parametric=[_calibration(), _fed()])
    result = ref.fit(patterns, plan="mccusker_default")
    _plot(result, "parametric_expression_calibration", (0, len(temps) - 1))
    assert result.status == "converged"
    rows = {p.path: p for p in result.parameters}
    for path, truth in (("vars.c0", c0), ("vars.c1", c1)):
        row = rows[path]
        assert row.stderr is not None and row.stderr > 0.0, path
        assert abs(row.value - truth) < 2 * row.stderr, (path, row.value, row.stderr, truth)
    assert "vars.a0" not in rows and "vars.k" not in rows
    cell = next(st for st in result.stages if st.name == "cell")
    assert sorted(cell.freed) == ["vars.c0", "vars.c1"]
    got0, got1 = rows["vars.c0"].value, rows["vars.c1"].value
    for h, temp in enumerate(temps):
        a = rows[f"hist.{h}.phases.0.cell.a"].value
        assert a == pytest.approx(a0 + k * (temp + got0 + got1 * temp), rel=1e-13)
    # evaluated from the result alone, the intermediate passed as a definition
    # (task 10); its own entry reads over its two variables
    by_name = {e.equation.name: e for e in result.parametric_equations}
    assert list(by_name) == ["T_true", "a"]
    mine = [c for c in result.parametric if c.equation == "a"]
    for h, temp in enumerate(temps):
        v = by_name["a"].evaluate(mine, coordinates={"T": temp},
                                  definitions=[by_name["T_true"]])
        row = rows[f"hist.{h}.phases.0.cell.a"]
        assert v.value == pytest.approx(row.value, rel=1e-13)
        assert v.esd == pytest.approx(row.stderr, rel=1e-6), h
    with pytest.raises(ValueError, match="T_true"):
        by_name["a"].evaluate(mine, coordinates={"T": temps[0]})


# -- a preview without a fit (task 8) ----------------------------------------

def test_a_preview_evaluates_each_equation_at_the_start_and_names_its_inputs():
    """Values, dependencies, and the two ways a start goes wrong, with no fit."""
    temps = [300.0, 450.0, 600.0]
    rows = {p.name: p for p in _fed_table().preview_equations()}
    assert list(rows) == ["a"]
    a = rows["a"]
    assert a.target == "phases.0.cell.a" and a.patterns == [0, 1, 2]
    assert a.variables == ["vars.a0", "vars.k", "vars.c0", "vars.c1"]
    assert a.coordinates == ["T"] and a.intermediates == ["T_true"]
    for v, temp in zip(a.values, temps, strict=True):
        assert v == pytest.approx(4.15 + 2e-5 * (temp + C0 + C1 * temp), rel=1e-13)
    assert a.span == (min(a.values), max(a.values))
    assert a.nonfinite == [] and a.out_of_bounds == []
    # theta = 0 divides by exp(0) - 1 = 0 at every pattern
    bad = _table(variables=_variables(theta=rx.Parameter(value=0.0, vary=False)))
    (row,) = bad.preview_equations()
    assert row.nonfinite == [0, 1, 2] and row.span is None
    # a cell the target's own bounds refuse
    s, _ = perturbed_inputs()
    s.phases[0].cell.a.max = 4.17
    far = MultiParameterTable(s, _lab6_instruments(3), coordinates=_coords(3),
                              parametric=[_expression()],
                              variables=_variables(zero_a=rx.Parameter(value=4.2, vary=True)))
    (row,) = far.preview_equations()
    assert row.out_of_bounds == [0, 1, 2]


def test_a_preview_covers_a_linear_equation_too():
    from tests.test_parametric_series import _ramp_table

    (row,) = _ramp_table().preview_equations()
    assert row.target == "phases.0.cell.a"
    assert row.variables == ["vars.a_0", "vars.a_1"] and row.coordinates == ["T"]
    assert row.intermediates == [] and len(row.values) == 3


# -- a variable per pattern (task 11) ----------------------------------------

def test_a_per_histogram_glob_makes_a_variable_a_column_per_pattern():
    """``SharingMap.per_histogram`` naming ``vars.zero_a`` is an ordinary glob
    (the maintainer's ruling of 2026-11-05): the variable becomes one column
    per pattern that reads it, and a glob on the target frees it there only."""
    mt = _table(sharing=SharingMap(per_histogram=["vars.zero_a"]))
    mt.set_vary(["*"], False)
    freed = mt.set_vary(["phases.*.cell.*"], True)
    assert sorted(freed) == ["hist.0.vars.zero_a", "hist.1.vars.zero_a",
                             "hist.2.vars.zero_a", "vars.grad"]
    assert mt.shared_paths == ["vars.grad"]
    mt.set_vary(["*"], False)
    # scoped to one pattern, the glob frees that pattern's column and the shared one
    assert sorted(mt.set_vary(["hist.1.phases.0.cell.a"], True)) == [
        "hist.1.vars.zero_a", "vars.grad"]
    # a subset: only the patterns whose equation reads the variable carry it
    sub = _table(parametric=[_expression(patterns=[1, 2])],
                 sharing=SharingMap(per_histogram=["vars.*"]))
    assert ["vars.zero_a" in t._paths for t in sub.tables] == [False, True, True]
    (r,) = sub.expressions
    assert sub.variable_rows(r) == [f"hist.{h}.vars.{v}" for v in ("zero_a", "grad", "theta")
                                    for h in (1, 2)]


GS_STD, B0_SMP, GB_SMP = 3.0e-5, 4.40, 6.0e-5
TEMPS_SE = [300.0, 400.0, 500.0, 600.0, 700.0, 800.0]
DT_SE = [3.0, -5.0, 8.0, -2.0, 6.0, -4.0]


def _two_cells(a: float, b: float, scale: float) -> rx.Structure:
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    sample = structure.phases[0].model_copy(deep=True)
    sample.name = "sample"
    structure.phases.append(sample)
    for phase, edge in zip(structure.phases, (a, b), strict=True):
        for k in "abc":
            getattr(phase.cell, k).value = edge
        phase.scale.value = scale
    return structure


def _simulate_two(a: float, b: float, seed: int) -> rx.PatternData:
    """One pattern of a standard (cell ``a``) beside a sample (cell ``b``),
    under :func:`tests.test_sequential._simulate`'s instrument and noise."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import BackgroundChebyshev
    from tests.test_sequential import TRUE_BKG, TRUE_SCALE, TRUE_W, TRUE_ZERO, WAVELENGTH

    structure = _two_cells(a, b, TRUE_SCALE)
    for phase in structure.phases:
        for atom in phase.atoms:
            atom.biso.value = 0.4
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[rx.Parameter(value=v) for v in TRUE_BKG])
    tt = np.arange(3.0, 24.0, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _stinton_evans(seed: int):
    """Stinton & Evans's (2007) first method on a synthetic ramp: a standard
    whose expansion is known and a sample whose is not, each cell an equation
    in T + ΔT, with ΔT one free number per pattern."""
    from rietx.schemas.instrument import BackgroundChebyshev
    from tests.test_sequential import A0, TRUE_SCALE, TRUE_W, WAVELENGTH

    patterns = [_simulate_two(A0 + GS_STD * (t + d - 300.0),
                              B0_SMP + GB_SMP * (t + d - 300.0), seed * 100 + k)
                for k, (t, d) in enumerate(zip(TEMPS_SE, DT_SE, strict=True))]
    structure = _two_cells(A0, B0_SMP * 1.0005, TRUE_SCALE * 1.5)
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = 0.0
    ins.profile.w.value = TRUE_W * 1.5
    ins.background = BackgroundChebyshev.with_terms(3)
    variables = {"as0": rx.Parameter(value=A0, vary=False),
                 "gs": rx.Parameter(value=GS_STD, vary=False),
                 "b0": rx.Parameter(value=B0_SMP * 1.0005, vary=True),
                 "gb": rx.Parameter(value=GB_SMP * 0.8, vary=True),
                 "dT": rx.Parameter(value=0.0, vary=True, min=-50.0, max=50.0)}
    equations = [
        ParametricEquation(name="std", target="phases.0.cell.a", basis="expression",
                           expression="as0 + gs*(T + dT - 300)"),
        ParametricEquation(name="smp", target="phases.1.cell.a", basis="expression",
                           expression="b0 + gb*(T + dT - 300)")]
    ref = MultiHistogramRefinement(
        structure, [ins] * len(TEMPS_SE),
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"],
                           per_histogram=["vars.dT"]),
        coordinates=CoordinateTable(columns={"T": TEMPS_SE}, units={"T": "K"}),
        variables=variables, parametric=equations)
    return ref.fit(patterns, plan="mccusker_default")


def _z_scores(result: rx.RefinementResult) -> dict[str, float]:
    rows = {p.path: p for p in result.parameters}
    truth = {**{f"hist.{k}.vars.dT": d for k, d in enumerate(DT_SE)},
             "vars.b0": B0_SMP, "vars.gb": GB_SMP}
    return {path: (rows[path].value - t) / rows[path].stderr for path, t in truth.items()}


@pytest.mark.xdist_group("parametric-expression")
def test_a_temperature_offset_per_pattern_feeds_two_cell_equations():
    """Six patterns, a ΔT per pattern read by both phases' cell equations.
    Measured (macOS arm64, ``[dev,jax,torch]``): 2.4-2.9 s, every ΔT and the
    sample's two coefficients within 0.9 esd of the truth on seed 0."""
    result = _stinton_evans(seed=0)
    _plot(result, "parametric_expression_delta_t", (0, len(TEMPS_SE) - 1))
    assert result.status == "converged"
    z = _z_scores(result)
    assert max(abs(v) for v in z.values()) < 2.0, z
    rows = {p.path: p for p in result.parameters}
    cell = next(st for st in result.stages if st.name == "cell")
    assert cell.freed == ["vars.b0", "vars.gb",
                          *(f"hist.{k}.vars.dT" for k in range(len(TEMPS_SE)))]
    # each pattern's cells are the two equations at its own T + ΔT
    for k, temp in enumerate(TEMPS_SE):
        dt = rows[f"hist.{k}.vars.dT"].value
        assert rows[f"hist.{k}.phases.1.cell.a"].value == pytest.approx(
            rows["vars.b0"].value + rows["vars.gb"].value * (temp + dt - 300.0), rel=1e-13)
        assert rows[f"hist.{k}.vars.dT"].equations == ["std", "smp"]
    # result.parametric: a per-pattern variable is a row per pattern of its equation
    smp = [c for c in result.parametric if c.equation == "smp"]
    assert [c.path for c in smp] == ["vars.b0", "vars.gb", *(
        f"hist.{k}.vars.dT" for k in range(len(TEMPS_SE)))]
    assert all(c.term == "dT" and c.esd == rows[c.path].stderr for c in smp[2:])
    # no value between patterns, so evaluate says where each pattern's is
    eq = next(e for e in result.parametric_equations if e.equation.name == "smp")
    assert eq.covariance is None
    with pytest.raises(ValueError, match="hist.h.phases.1.cell.a"):
        eq.evaluate(smp, coordinates={"T": 450.0})
    # with ΔT free in every pattern, neither equation alone has a direction to
    # test once the other's targets are freed; the joint reading tests the pair
    assert [f.rejected for f in result.parametric_form] == [None, None]
    assert result.parametric_form_joint.dof == 4
    assert result.parametric_form_joint.rejected is False


@pytest.mark.slow
@pytest.mark.xdist_group("parametric-expression")
def test_a_temperature_offset_per_pattern_is_unbiased_over_twelve_seeds():
    """The WP's acceptance bar: over 12 pinned seeds, each ΔT and each shared
    coefficient it feeds has a mean z-score under 0.5 in size.  Measured
    (macOS arm64): every mean within 0.13, every |z| under 2 in 96 of 96,
    the z spread 0.46-0.88 (the esds carry the Bérar-Lelann factor)."""
    zs = [_z_scores(_stinton_evans(seed)) for seed in range(12)]
    for path in zs[0]:
        mean = float(np.mean([z[path] for z in zs]))
        assert abs(mean) < 0.5, (path, mean)
