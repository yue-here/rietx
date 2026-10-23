"""Parametric series: a parameter as a declared function of each pattern's
coordinates, refined in one joint residual (WP-1325).

What is checked here, and on what:

* the declaration (``CoordinateTable``, ``ParametricEquation``) as data — its JSON
  round-trip, its shape refusals, and its resolution against the patterns:
  the reference and scale frozen once, the term labels, and every refusal
  of the WP's § The shape item 3, each by its message, before any solve;
* the joint table's wiring — per-pattern starting structures, the coupling
  that lets a plan's glob on a target free its coefficients, and the
  absent-phase hold reading what a coefficient's column *moves* (WP-1342);
* the claim that a ``constant`` declaration **is** ``refine_multi`` with the
  target shared, bit for bit, on the two-wavelength LaB6 pair of
  ``test_multi_histogram``;
* (slow) a ten-pattern LaB6 ramp with a known a(T), whose parametric
  slope must land within one esd of the truth with an esd no larger than the
  weighted trajectory line's;
* the form test: its blocked gain against dense least squares, each
  pattern's target column read off the coefficients against an untied
  table's, and that ramp's line equation kept on its own truth and rejected when
  the truth bends;
* the blocked joint Jacobian (``optimize/blocked.py``) against the dense one:
  the matrix entry for entry, the LM step to WP-1125's 6.6e-7 relative with
  no bound active (both step solvers), the converged answer within 0.01 esd,
  the Schur covariance against the dense pseudo-inverse (equilibration,
  gradient-free and far-scaled columns, discarded directions), the moment
  test's refit, and the layout rule;
* and (slow) a synthetic library with a known 2-D surface a(x, y) over 120
  patterns, solved through the blocked path the size rule picks.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.multi import (
    MultiHistogramRefinement,
    _equation_rows,
    _joint_fixed_literals,
    _parametric_range_diagnostics,
    _unsupported_paths_multi,
    refine_multi,
)
from rietx.optimize import blocked, lm
from rietx.optimize.blocked import BlockJacobian
from rietx.optimize.least_squares import (
    _multi_closures,
    _refitted_increase,
    _residual_cosine,
    covariance_estimates,
    rechart_outcome,
    run_multi_least_squares,
)
from rietx.optimize.statistics import column_norms, column_rescale, discarded_directions
from rietx.params.multi import MultiParameterTable, SharingMap
from rietx.params.parametric import (
    ResolvedParametric,
    coefficient_rows,
    form_tests,
    parametric_equation,
    resolve_parametric,
    target_columns,
    term_label,
)
from rietx.params.vector import AffineTie
from rietx.schemas.parametric import (
    CoordinateTable,
    ParametricCoefficient,
    ParametricEquation,
)
from rietx.strategy.staged import Stage
from tests.test_multi_histogram import perturbed_inputs, synthesize

OUT = Path(__file__).parent / "output"


def _equation(**kw) -> ParametricEquation:
    base = dict(name="a", target="phases.0.cell.a", basis="polynomial",
                terms=[[], ["T"]])
    base.update(kw)
    return ParametricEquation(**base)


def _coords(*temps: float | None, **more) -> CoordinateTable:
    cols = {"T": list(temps), **more}
    return CoordinateTable(columns=cols, units={"T": "K"})


def _lab6_instruments(n: int) -> list[rx.Instrument]:
    out = []
    for _ in range(n):
        ins = rx.Instrument.debye_scherrer(wavelength=0.41390)
        ins.background = rx.schemas.instrument.BackgroundChebyshev.with_terms(3)
        out.append(ins)
    return out


# -- the declaration as data -------------------------------------------------

def test_the_declarations_round_trip_through_json():
    coords = CoordinateTable(columns={"T": [300.0, None, 500.0], "x": [0.1, 0.2, 0.3]},
                             units={"T": "K"})
    ties = [
        _equation(patterns=[0, 2], reference={"T": 400.0}, scale={"T": 100.0}),
        ParametricEquation(name="c", target="instrument.background.c2", basis="constant"),
        ParametricEquation(name="d", target="phases.0.atoms.0.biso", basis="design",
                           design=[[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]]),
    ]
    row = ParametricCoefficient(equation="a", target="phases.0.cell.a", term="T",
                                path="vars.a_1", value=2.1e-5, esd=None, vary=True,
                                unit=None, reference={"T": 400.0})
    for obj in (coords, *ties, row):
        text = obj.model_dump_json()
        assert type(obj).model_validate_json(text) == obj
        assert type(obj).model_validate(json.loads(text)) == obj


def test_a_1_9_coefficient_row_opens_with_its_tie_key_read_as_equation():
    """1.9.0 (schema 0.55) wrote ``tie``; the key is now ``equation``, and only
    ``equation`` is written back."""
    row = dict(target="phases.0.cell.a", term="T", path="vars.a_1", value=2.1e-5,
               esd=None, vary=True, unit=None, reference={"T": 400.0})
    old = ParametricCoefficient.model_validate({"tie": "a", **row})
    new = ParametricCoefficient(equation="a", **row)
    assert old == new and old.equation == "a"
    dumped = json.loads(old.model_dump_json())
    assert dumped["equation"] == "a" and "tie" not in dumped
    assert ParametricCoefficient.model_validate_json(json.dumps({"tie": "a", **row})) == new


@pytest.mark.parametrize("kw, fragment", [
    (dict(name="a.b"), "single identifier"),
    (dict(target="phases.*.cell.a"), "not a glob"),
    (dict(target="hist.0.phases.0.cell.a"), "model parameter"),
    (dict(target="vars.x"), "model parameter"),
    (dict(basis="constant"), "takes no terms"),
    (dict(terms=[]), "needs terms"),
    (dict(terms=[["T"], ["T"]]), "appears twice"),
    (dict(terms=[["T", "x"], ["x", "T"]]), "appears twice"),
    (dict(scale={"T": 0.0}), "must be positive"),
    (dict(reference={"x": 1.0}), "no term uses"),
    (dict(patterns=[0, 0]), "appears twice in the subset"),
    (dict(patterns=[]), "selects nothing"),
    (dict(basis="design", terms=None, design=[[1.0], [1.0, 2.0]]), "same number"),
    (dict(basis="design", terms=None, design=[[1.0]], patterns=[0, 1]), "one row per"),
])
def test_a_malformed_declaration_is_refused_by_its_shape(kw, fragment):
    with pytest.raises(ValidationError, match=fragment):
        _equation(**kw)


@pytest.mark.parametrize("columns, units, fragment", [
    ({"T": [1.0, 2.0], "x": [1.0]}, {}, "lengths differ"),
    ({"T": [1.0, float("nan")]}, {}, "must be finite"),
    ({"T": [1.0]}, {"x": "K"}, "does not have"),
    ({"2T": [1.0]}, {}, "single identifier"),
])
def test_a_malformed_coordinate_table_is_refused(columns, units, fragment):
    with pytest.raises(ValidationError, match=fragment):
        CoordinateTable(columns=columns, units=units)


# -- resolution: the reference and scale, once ------------------------------

def test_resolution_freezes_the_reference_and_scale_and_a_refit_keeps_them():
    r = resolve_parametric(_equation(), _coords(300.0, 375.0, 600.0), 3, target_unit="A")
    assert r.equation.reference == {"T": 450.0} and r.equation.scale == {"T": 150.0}
    assert r.labels == ["1", "T"]
    np.testing.assert_array_equal(r.phi[:, 1], [-1.0, -0.5, 1.0])
    assert r.units == ["A", "A/K"]
    # the campaign grows past the old range: the resolved declaration keeps
    # its reference and scale, so the old patterns' rows are unchanged and a
    # coefficient means what it meant
    grown = resolve_parametric(r.equation, _coords(300.0, 375.0, 600.0, 900.0), 4)
    assert grown.equation.reference == {"T": 450.0} and grown.equation.scale == {"T": 150.0}
    np.testing.assert_array_equal(grown.phi[:3], r.phi)
    # left unresolved, the same growth would have moved both
    fresh = resolve_parametric(_equation(), _coords(300.0, 375.0, 600.0, 900.0), 4)
    assert fresh.equation.reference == {"T": 600.0} and fresh.equation.scale == {"T": 300.0}


def test_term_labels_and_units_name_each_monomial():
    assert [term_label(t) for t in ([], ["T"], ["x", "y"], ["T", "T"],
                                    ["x", "y", "x"])] == ["1", "T", "x*y", "T^2", "x^2*y"]
    coords = CoordinateTable(columns={"x": [0.0, 1.0, 2.0, 3.0], "y": [0.0, 2.0, 1.0, 3.0]},
                             units={"x": "at%"})
    r = resolve_parametric(_equation(terms=[[], ["x"], ["y"], ["x", "x"]]), coords, 4,
                           target_unit="A")
    # y has no recorded unit, so no unit is claimed for its term
    assert r.units == ["A", "A/at%", None, "A/at%^2"]
    assert r.divisors.tolist() == [1.0, 1.5, 1.5, 2.25]


# -- refusals before any solve: from the declaration and the coordinates ----

@pytest.mark.parametrize("equation, coords, n, fragment", [
    (_equation(patterns=[0, 3]), _coords(1.0, 2.0, 3.0), 3, "out of range"),
    (_equation(), None, 3, "needs a CoordinateTable"),
    (_equation(), _coords(1.0, 2.0), 3, "2 rows for 3 patterns"),
    (_equation(terms=[[], ["x"]]), _coords(1.0, 2.0, 3.0), 3, "does not have"),
    (_equation(), _coords(1.0, None, 3.0), 3, "pattern 1 has no value"),
    (_equation(), _coords(2.0, 2.0, 2.0), 3, "takes one value"),
    (_equation(terms=[[], ["T"], ["T", "T"]]), _coords(1.0, 2.0), 2, "3 coefficients"),
    (ParametricEquation(name="d", target="phases.0.cell.a", basis="design",
                        design=[[1.0], [2.0]]), None, 3, "2 design rows"),
    (ParametricEquation(name="d", target="phases.0.cell.a", basis="design",
                        design=[[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]]), None, 3,
     "d1 is a combination of"),
    (ParametricEquation(name="d", target="phases.0.cell.a", basis="design",
                        design=[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), None, 3, "zero in every"),
])
def test_each_resolution_refusal_names_its_fix(equation, coords, n, fragment):
    with pytest.raises(ValueError, match=fragment):
        resolve_parametric(equation, coords, n)


def test_a_ternary_with_an_intercept_is_refused_with_the_scheffe_fix():
    """x_A + x_B + x_C = 1 on every pattern: the intercept is their sum."""
    xa = [0.6, 0.2, 0.2, 0.4, 0.3]
    xb = [0.2, 0.6, 0.2, 0.3, 0.3]
    xc = [1.0 - a - b for a, b in zip(xa, xb, strict=True)]
    coords = CoordinateTable(columns={"xa": xa, "xb": xb, "xc": xc})
    equation = _equation(terms=[[], ["xa"], ["xb"], ["xc"]])
    with pytest.raises(ValueError, match=r"rank 3 for 4.*Scheffé.*reference="):
        resolve_parametric(equation, coords, 5)
    # without the intercept the basis is full rank, but centred fractions would
    # make each coefficient a blend of pure-component values: refused until the
    # reading is stated
    scheffe = [["xa"], ["xb"], ["xc"]]
    with pytest.raises(ValueError, match=r"mixture fractions.*Scheffé form"):
        resolve_parametric(_equation(terms=scheffe), coords, 5)
    # stated: the Scheffé form resolves, uncentred
    zero, one = dict.fromkeys(coords.columns, 0.0), dict.fromkeys(coords.columns, 1.0)
    ok = resolve_parametric(_equation(terms=scheffe, reference=zero, scale=one), coords, 5)
    assert ok.labels == ["xa", "xb", "xc"]
    assert np.array_equal(ok.phi, np.column_stack([xa, xb, xc]))


# -- refusals before any solve: what the tables can carry -------------------

@pytest.mark.parametrize("equation, fragment", [
    (_equation(target="phases.0.cell.q", basis="constant", terms=None), "not a parameter"),
    (_equation(target="phases.0.cell.b", basis="constant", terms=None),
     "is tied: = 1·phases.0.cell.a.*declare the equation on phases.0.cell.a"),
    (_equation(target="phases.0.atoms.0.x", basis="constant", terms=None), "locked"),
])
def test_a_target_no_equation_can_drive_is_refused_naming_why(equation, fragment):
    s, _ = perturbed_inputs()
    with pytest.raises(ValueError, match=fragment):
        MultiParameterTable(s, _lab6_instruments(2), parametric=[equation])


def test_a_held_target_is_refused():
    """The floating origin's hold (WP-1912) is the joint table's one hold."""
    from tests.test_floating_origin import _zno

    phase = _zno()
    phase.floating_origin = "hold"
    s = rx.Structure(phases=[phase])
    equation = _equation(target="phases.0.atoms.0.dof.0", basis="constant", terms=None)
    with pytest.raises(ValueError, match="is held"):
        MultiParameterTable(s, [rx.Instrument.bragg_brentano(radiation="CuKa")] * 2,
                            parametric=[equation])


def test_two_declarations_may_share_neither_a_name_nor_a_pattern_of_one_target():
    s, _ = perturbed_inputs()
    one = _equation(basis="constant", terms=None)
    with pytest.raises(ValueError, match="both drive phases.0.cell.a on patterns 0, 1"):
        MultiParameterTable(s, _lab6_instruments(2),
                            parametric=[one, one.model_copy(update={"name": "b"})])
    with pytest.raises(ValueError, match="both drive phases.0.cell.a on pattern 1:"):
        MultiParameterTable(s, _lab6_instruments(3), parametric=[
            one.model_copy(update={"patterns": [0, 1]}),
            one.model_copy(update={"name": "b", "patterns": [1, 2]})])
    with pytest.raises(ValueError, match="two parametric equations are named 'a'"):
        MultiParameterTable(s, _lab6_instruments(2), parametric=[
            one, one.model_copy(update={"target": "phases.0.atoms.0.biso"})])


def test_two_phase_fields_take_an_equation_each_on_one_target():
    """Disjoint subsets: one equation per field, each pattern tied by its own."""
    s, _ = perturbed_inputs()
    lo = _equation(name="lo", basis="constant", terms=None, patterns=[0, 1])
    hi = _equation(name="hi", basis="constant", terms=None, patterns=[2, 3])
    mt = MultiParameterTable(s, _lab6_instruments(4), parametric=[lo, hi])
    sources = [mt.tables[h].entries[mt.tables[h]._paths["phases.0.cell.a"]].tie.terms
               for h in range(4)]
    assert [src for (src, _), in sources] == ["vars.lo_0", "vars.lo_0",
                                             "vars.hi_0", "vars.hi_0"]
    freed = mt.set_vary(["phases.*.cell.*"], True)
    assert {"vars.lo_0", "vars.hi_0"} <= set(freed)


def test_each_row_an_equation_sets_names_it_and_no_other_row_does():
    """``RefinedParameter.equations``' writer, read off C before anything is freed,
    so a held coefficient counts.  Two phase fields on one target: in each
    subset pattern the cubic cell's three edges name that field's equation, each
    coefficient row names its own, and the pattern in neither subset names
    none."""
    s, _ = perturbed_inputs()
    lo = _equation(name="lo", basis="constant", terms=None, patterns=[0, 1])
    hi = _equation(name="hi", basis="constant", terms=None, patterns=[2, 3])
    mt = MultiParameterTable(s, _lab6_instruments(5), parametric=[lo, hi])
    want = {"vars.lo_0": ["lo"], "vars.hi_0": ["hi"]}
    for h, equation in [(0, "lo"), (1, "lo"), (2, "hi"), (3, "hi")]:
        want.update({f"hist.{h}.phases.0.cell.{k}": [equation] for k in "abc"})
    assert _equation_rows(mt) == want


def test_a_size_target_across_wavelengths_is_refused():
    """A size coefficient goes as λ (WP-1131): shared, it carries the factor
    into each histogram; a parametric target is per-histogram and would not."""
    s, ins = perturbed_inputs()                  # 0.41390 and 0.71070 Å
    equation = _equation(name="L", target="phases.0.lor_size", basis="constant", terms=None)
    with pytest.raises(ValueError, match=r"crystallite-size.*0\.4139, 0\.7107 Å"):
        MultiParameterTable(s, ins, parametric=[equation])
    # one wavelength: nothing to convert, so the declaration stands
    mt = MultiParameterTable(s, _lab6_instruments(2), parametric=[equation])
    assert [r.target for r in mt.parametric] == ["phases.0.lor_size"]


def test_a_sharing_map_that_splits_a_coefficient_is_refused():
    s, _ = perturbed_inputs()
    with pytest.raises(ValueError, match="makes vars.a_0 per-histogram"):
        MultiParameterTable(s, _lab6_instruments(2),
                            sharing=SharingMap(per_histogram=["vars.*"]),
                            parametric=[_equation(basis="constant", terms=None)])


# -- the joint table's wiring ------------------------------------------------

def _ramp_table(n: int = 3, **kw) -> MultiParameterTable:
    s, _ = perturbed_inputs()
    return MultiParameterTable(
        s, _lab6_instruments(n), coordinates=_coords(*[300.0 + 100 * k for k in range(n)]),
        parametric=[_equation()], **kw)


def test_the_target_follows_the_declared_line_in_every_table():
    mt = _ramp_table()
    assert [r.target for r in mt.parametric] == ["phases.0.cell.a"]
    # the target and what follows it are per-histogram; the coefficients shared
    assert not mt.sharing.is_shared("phases.0.cell.c")
    assert all(mt.sharing.is_shared(p) for p in ("vars.a_0", "vars.a_1"))
    for t in mt.tables:
        t.entries[t._paths["vars.a_1"]].value = 0.01
        t.refresh_ties()
    for h, t in enumerate(mt.tables):
        want = 4.1606 + 0.01 * (h - 1)
        for k in "abc":
            assert t.entries[t._paths[f"phases.0.cell.{k}"]].value == pytest.approx(want, abs=1e-12)


def test_a_glob_on_the_target_frees_its_coefficients_and_names_them():
    mt = _ramp_table()
    mt.set_vary(["*"], False)
    assert mt.set_vary(["phases.*.cell.*"], True) == ["vars.a_0", "vars.a_1"]
    assert mt.shared_paths == ["vars.a_0", "vars.a_1"]
    assert mt.set_vary(["phases.0.cell.a"], False) == ["vars.a_0", "vars.a_1"]
    # scoped to a subset histogram, the glob still reaches the declaration
    assert mt.set_vary(["hist.2.phases.0.cell.a"], True) == ["vars.a_0", "vars.a_1"]
    # a plan's literal on the target is not "a tied row the stage cannot free"
    assert _joint_fixed_literals([Stage(name="cell", turn_on=["phases.0.cell.a"])],
                                 mt) == []


def test_a_column_is_held_only_when_every_phase_it_moves_is_unseen():
    """WP-1342 on the joint path: columns, never names, and all, never any."""
    s, _ = perturbed_inputs()
    nacl = rx.Phase(
        name="nacl", space_group="F m -3 m", cell=rx.Cell.cubic(5.64),
        atoms=[rx.Atom(label="Na", species="Na", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
               rx.Atom(label="Cl", species="Cl", x=rx.Parameter(value=0.5),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))])
    s.phases.append(nacl)
    equation = _equation(name="b", target="phases.1.cell.a", basis="constant", terms=None)
    mt = MultiParameterTable(s, _lab6_instruments(2), parametric=[equation])
    mt.set_vary(["*"], False)
    mt.set_vary(["phases.*.cell.*"], True)
    assert "vars.b_0" in mt.free_paths
    # by name the coefficient carries no phase; by reach it is phase 1's cell
    assert _unsupported_paths_multi(mt, [{1}, {1}]) == ["vars.b_0"]
    assert _unsupported_paths_multi(mt, [{0}, {0}]) == ["phases.0.cell.a"]
    # it drives phase 1's cell in both histograms, so one that sees the phase
    # gives it gradient
    assert _unsupported_paths_multi(mt, [{1}, set()]) == []
    # the same coefficient made to drive phase 0's cell too: one visible
    # phase gives it gradient, so it is held only when both are unseen
    for t in mt.tables:
        t.set_tie("phases.0.cell.a", AffineTie.identity("vars.b_0"))
        t.refresh_ties()
    mt._rebuild_columns()
    assert _unsupported_paths_multi(mt, [{1}, {1}]) == []
    assert _unsupported_paths_multi(mt, [{0}, {0}]) == []
    assert _unsupported_paths_multi(mt, [{0, 1}, {0, 1}]) == ["vars.b_0"]


def test_per_pattern_starting_structures_differ_only_where_a_path_is_per_histogram():
    def start(a: float, biso: float = 0.5, sg: str = "P m -3 m") -> rx.Structure:
        s, _ = perturbed_inputs()
        s.phases[0].space_group = sg
        for k in "abc":
            getattr(s.phases[0].cell, k).value = a
        s.phases[0].atoms[0].biso.value = biso
        return s

    coords = _coords(300.0, 400.0)
    # the cell differs, but it is the parametric target: accepted, and the
    # line through the starts is the coefficients' start
    mt = MultiParameterTable([start(4.15), start(4.17)], _lab6_instruments(2),
                             coordinates=coords, parametric=[_equation()])
    t0 = mt.tables[0]
    assert t0.entries[t0._paths["vars.a_0"]].value == pytest.approx(4.16, abs=1e-12)
    assert t0.entries[t0._paths["vars.a_1"]].value == pytest.approx(0.01, abs=1e-12)
    # a per-histogram scale may differ too
    other = start(4.15)
    other.phases[0].scale.value = 7.0
    MultiParameterTable([start(4.15), other], _lab6_instruments(2))
    # a shared value may not, and the refusal names the path and the histogram
    with pytest.raises(ValueError, match=r"disagree on phases.0.atoms.0.biso.*histogram 1"):
        MultiParameterTable([start(4.15), start(4.15, biso=0.7)], _lab6_instruments(2))
    with pytest.raises(ValueError, match="disagree on phases.0.cell.a"):
        MultiParameterTable([start(4.15), start(4.17)], _lab6_instruments(2))
    with pytest.raises(ValueError, match="space group"):
        MultiParameterTable([start(4.15), start(4.15, sg="P 4/m m m")],
                            _lab6_instruments(2))
    with pytest.raises(ValueError, match="3 starting structures for 2"):
        MultiParameterTable([start(4.15)] * 3, _lab6_instruments(2))


def test_a_dependent_the_coefficients_put_out_of_range_is_named():
    s, _ = perturbed_inputs()
    equation = _equation(name="w", target="instrument.profile.w")
    mt = MultiParameterTable(s, _lab6_instruments(3), coordinates=_coords(300.0, 400.0, 500.0),
                             parametric=[equation])
    assert _parametric_range_diagnostics(mt) == []
    for t in mt.tables:      # w = 1e-3 - 2e-3·u: negative at the top of the ramp
        t.entries[t._paths["vars.w_1"]].value = -2e-3
        t.refresh_ties()
    (d,) = _parametric_range_diagnostics(mt)
    assert d.code == "PARAMETRIC_OUT_OF_RANGE" and d.level == "warning"
    assert d.where == ["hist.2.instrument.profile.w"] and d.value == 1.0
    assert "histogram 2" in d.message


def test_coefficients_are_reported_per_unit_of_the_coordinates_at_the_reference():
    r = resolve_parametric(_equation(terms=[[], ["T"], ["T", "T"]]),
                           _coords(300.0, 500.0, 700.0), 3, target_unit="A")
    assert isinstance(r, ResolvedParametric) and r.equation.scale == {"T": 200.0}
    rows = coefficient_rows(
        r, {"vars.a_0": 4.0, "vars.a_1": 0.02, "vars.a_2": 0.004},
        {"vars.a_0": 1e-5, "vars.a_1": 2e-5},           # a_2: marked unmeasured
        {"vars.a_0": True, "vars.a_1": True, "vars.a_2": True})
    assert [(c.term, c.unit) for c in rows] == [("1", "A"), ("T", "A/K"), ("T^2", "A/K^2")]
    assert rows[0].value == 4.0 and rows[0].esd == 1e-5
    assert rows[1].value == pytest.approx(1e-4) and rows[1].esd == pytest.approx(1e-7)
    assert rows[2].value == pytest.approx(1e-7) and rows[2].esd is None
    assert rows[1].reference == {"T": 500.0}
    # a coefficient that was never free has no esd, whatever the map holds
    fixed = coefficient_rows(r, {p: 1.0 for p in r.paths}, {"vars.a_0": 1e-5}, {})
    assert all(c.esd is None and not c.vary for c in fixed)


def test_an_equation_evaluates_in_user_units_with_the_covariance_its_esds_came_from():
    """``parametric_equation`` and ``RefinedParametricEquation.evaluate`` without a fit: the
    table-unit equation Φ(u)·c at a coordinate is the user-unit one, and its esd is
    √(Φ Σ_table Φᵀ) from the correlation the esds were paired by."""
    r = resolve_parametric(_equation(terms=[[], ["T"], ["T", "T"]]),
                           _coords(300.0, 500.0, 700.0), 3, target_unit="A")
    assert (r.unit, r.span) == ("A", {"T": (300.0, 700.0)})
    table = np.array([4.0, 0.02, 0.004])
    s = np.array([1e-5, 2e-5, 3e-5])
    corr = np.array([[1.0, 0.3, -0.6], [0.3, 1.0, 0.1], [-0.6, 0.1, 1.0]])
    rows = coefficient_rows(r, dict(zip(r.paths, table, strict=True)),
                            dict(zip(r.paths, s, strict=True)),
                            dict.fromkeys(r.paths, True))
    equation = parametric_equation(r, rows, [0, 1, 2], corr)
    assert [equation.covariance[j][j] for j in range(3)] == [c.esd ** 2 for c in rows]
    for temp in (300.0, 640.0, 900.0):
        u = (temp - 500.0) / 200.0
        phi = np.array([1.0, u, u * u])
        v = equation.evaluate(rows, coordinates={"T": temp})
        assert v.value == pytest.approx(phi @ table, rel=1e-14)
        cov = corr * np.outer(s, s)
        assert v.esd == pytest.approx(np.sqrt(phi @ cov @ phi), rel=1e-12)
        assert v.outside == ([] if temp <= 700.0 else ["T"])
        assert v.form_rejected is None and v.unit == "A"
        assert (v.provisional_on, v.joint_rejected) == ([], None)
    # each refusal names what the basis takes
    with pytest.raises(ValueError, match=r"missing \['T'\]"):
        equation.evaluate(rows, coordinates={})
    with pytest.raises(ValueError, match="never a design row"):
        equation.evaluate(rows, coordinates={"T": 1.0}, row=[1.0, 0.0, 0.0])
    # one coefficient without an esd leaves the equation with no covariance
    rows[2] = rows[2].model_copy(update={"esd": None})
    blind = parametric_equation(r, rows, [0, 1, 2], corr)
    assert blind.covariance is None
    assert blind.evaluate(rows, coordinates={"T": 500.0}).esd is None
    # a design equation takes its own row, and a single coefficient needs no correlation
    d = resolve_parametric(_equation(basis="design", terms=None, design=[[1.0], [2.0]]),
                           None, 2)
    (dc,) = coefficient_rows(d, {"vars.a_0": 3.0}, {"vars.a_0": 0.5}, {"vars.a_0": True})
    design_eq = parametric_equation(d, [dc], [None], None)
    assert design_eq.covariance is None              # not free in θ: no column to pair
    design_eq = parametric_equation(d, [dc], [0], None)
    v = design_eq.evaluate([dc], row=[4.0])
    assert (v.value, v.esd, v.outside, v.row) == (12.0, 2.0, None, [4.0])
    with pytest.raises(ValueError, match="evaluated at a design row"):
        design_eq.evaluate([dc], coordinates={"T": 1.0})


# -- the joint fit: a constant declaration is refine_multi -------------------

@pytest.fixture(scope="module")
def lab6_pair() -> list[rx.PatternData]:
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


@pytest.mark.xdist_group("parametric-series")
@pytest.mark.parametrize("target, follows, compiled_path", [
    ("phases.0.cell.a", ["phases.0.cell.b", "phases.0.cell.c"], False),
    ("phases.0.cell.a", ["phases.0.cell.b", "phases.0.cell.c"], True),
    ("instrument.profile.w", [], True),
], ids=["cell-numpy", "cell-compiled", "width-compiled"])
def test_a_constant_declaration_is_refine_multi_bit_for_bit(lab6_pair, target, follows,
                                                            compiled_path):
    """The WP's equivalence bar, met exactly rather than to a tolerance.

    A ``constant`` equation makes the target per-histogram and ties it in each
    table to one shared coefficient at coefficient 1, against a plain joint
    fit that shares the target (the cell by default, the width by
    ``SharingMap.shared``).  The coefficient takes the column the shared target
    had (``_rebuild_columns``), starts from its exact value
    (``least_squares_start``), carries its declared box and unit (so the
    width's floor and FD step are its own), and dispatches to the target's
    analytic branch (``_column_identities`` reads a variable as what it
    drives) — so every θ, esd and statistic is the plain fit's, to the bit.
    """
    was = compiled.set_enabled(compiled_path)
    try:
        s, ins = perturbed_inputs()
        plain = refine_multi(lab6_pair, s, ins, plan="mccusker_default",
                             sharing=SharingMap(shared=[target]))
        s, ins = perturbed_inputs()
        ref = MultiHistogramRefinement(
            s, ins, parametric=[ParametricEquation(name="t", target=target, basis="constant")])
        tied = ref.fit(lab6_pair, plan="mccusker_default")
    finally:
        compiled.set_enabled(was)
    OUT.mkdir(exist_ok=True)
    tied.for_histogram(1).plot(OUT / f"parametric_constant_h1_{target}_{compiled_path}.png")
    a = {p.path: p for p in plain.parameters}
    b = {p.path: p for p in tied.parameters}
    shared = a.pop(target)
    assert (b["vars.t_0"].value, b["vars.t_0"].stderr) == (shared.value, shared.stderr)
    for path, row in a.items():
        if path in follows:
            continue          # follow the target, per histogram now
        assert (b[path].value, b[path].stderr) == (row.value, row.stderr), path
    for h in range(2):
        for path in (target, *follows):
            assert b[f"hist.{h}.{path}"].value == shared.value
    assert tied.statistics == plain.statistics
    for hp, ht in zip(plain.histograms, tied.histograms, strict=True):
        assert ht.statistics == hp.statistics
        assert ht.y_calc == hp.y_calc
    (coef,) = tied.parametric
    assert (coef.value, coef.esd, coef.term, coef.vary) == (
        shared.value, shared.stderr, "1", True)
    assert plain.parametric is None
    # the equation's rows name it, every other row and every plain row nothing
    equation_set = {"vars.t_0"} | {f"hist.{h}.{p}" for h in range(2) for p in (target, *follows)}
    assert {p for p, row in b.items() if row.equations} == equation_set
    assert all(b[p].equations == ["t"] for p in equation_set)
    assert not any(row.equations for row in plain.parameters)
    assert tied.for_histogram(1).parameter(target).equations == ["t"]
    v = tied.parametric_value("t")
    assert (v.value, v.esd, v.outside) == (shared.value, shared.stderr, [])
    assert not any(d.code == "PARAMETRIC_TARGET_UNSEEN" for d in tied.diagnostics)
    # the stage that freed the target freed the coefficient in its place
    stage = next(st for st in plain.stages if target in st.freed)
    assert [p.replace(target, "vars.t_0") for p in stage.freed] == next(
        st.freed for st in tied.stages if st.name == stage.name)
    assert ref.parametric == [ParametricEquation(name="t", target=target, basis="constant")]


def _with_an_unseen_phase() -> rx.Structure:
    """The LaB6 pair's start plus a NaCl phase neither pattern contains."""
    s, _ = perturbed_inputs()
    s.phases.append(rx.Phase(
        name="nacl", space_group="F m -3 m", cell=rx.Cell.cubic(5.64),
        scale=rx.Parameter(value=1e-12, min=0.0),
        atoms=[rx.Atom(label="Na", species="Na", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
               rx.Atom(label="Cl", species="Cl", x=rx.Parameter(value=0.5),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))]))
    return s


@pytest.mark.xdist_group("parametric-series")
def test_a_joint_fit_holds_a_coefficient_whose_phase_no_pattern_sees(lab6_pair):
    """The latent WP-1342 bug: a name prefix would never hold ``vars.b_0``,
    and would release it at once if it had.

    Measured on this fixture: the NaCl scale fits noise to 1.6e-8 in
    histogram 0 by the cell stage, so the cell refines there, and the support
    hold takes it from ``profile_w`` on.  The parametric fit decides exactly
    as the plain one does, stage by stage, and lands on the same cell.
    """
    _, ins = perturbed_inputs()
    plain = refine_multi(lab6_pair, _with_an_unseen_phase(), ins,
                         plan="mccusker_default")
    _, ins = perturbed_inputs()
    equation = ParametricEquation(name="b", target="phases.1.cell.a", basis="constant")
    result = refine_multi(lab6_pair, _with_an_unseen_phase(), ins, parametric=[equation],
                          plan="mccusker_default")
    OUT.mkdir(exist_ok=True)
    result.for_histogram(0).plot(OUT / "parametric_unseen_phase_h0.png")
    rename = {"phases.1.cell.a": "vars.b_0"}
    assert ([[rename.get(p, p) for p in st.held] for st in plain.stages]
            == [st.held for st in result.stages])
    held = [st for st in result.stages if "vars.b_0" in st.held]
    assert held and held[-1] is result.stages[-1]       # never released by its name
    for st in held:
        assert "vars.b_0" not in st.freed
        assert set(st.held_reach["vars.b_0"]) == {
            f"hist.{h}.phases.1.cell.{k}" for h in range(2) for k in "abc"}
    (coef,) = result.parametric
    assert coef.vary is False and coef.esd is None
    assert coef.value == plain.parameter("phases.1.cell.b").value
    unseen = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert unseen and "vars.b_0" in unseen[0].where
    assert result.statistics == plain.statistics
    # neither pattern sees NaCl, so the equation sets its cell in both and says so
    (blind,) = [d for d in result.diagnostics if d.code == "PARAMETRIC_TARGET_UNSEEN"]
    assert blind.level == "warning" and blind.value == 2.0
    assert blind.where == ["hist.0.phases.1.cell.a", "hist.1.phases.1.cell.a"]
    for h in range(2):
        for k in "abc":
            assert result.parameter(f"hist.{h}.phases.1.cell.{k}").equations == ["b"]
    (form,) = result.parametric_form
    assert (form.n_patterns, form.n_subset, form.tied, form.rejected) == (0, 2, None, None)


# -- the synthetic ramp (slow): a measured a₁ with its esd ------------------

@pytest.mark.slow
def test_a_parametric_slope_recovers_a_known_expansion_within_its_esd():
    """Ten LaB6 patterns, T = 300…1200 K, a(T) on a known line.

    One diffractometer, so its zero and profile are shared across the ramp —
    the regime where § Measured found the joint esd 2.6× under the weighted
    trajectory line's (R3).  Seed and protocol are ``synthetic_ramp.py``'s.
    """
    from tests.test_sequential import A0, RAMP, _simulate, _start_models

    temps = [300.0 + 100.0 * k for k in range(10)]
    patterns = [_simulate(A0 * (1.0 + RAMP * (t - 300.0) / 100.0), seed=k)
                for k, t in enumerate(temps)]
    truth = A0 * RAMP / 100.0
    structure, ins = _start_models()
    result = refine_multi(
        patterns, structure, [ins] * len(temps), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="polynomial", terms=[[], ["T"]])])
    OUT.mkdir(exist_ok=True)
    for h in (0, len(temps) - 1):
        result.for_histogram(h).plot(OUT / f"parametric_ramp_h{h}.png")
    assert result.status == "converged"
    intercept, slope = result.parametric
    assert (intercept.term, slope.term) == ("1", "T")
    assert slope.reference == {"T": 750.0}
    # Two esds: one noise draw.  Over five sets of seeds the slope lands
    # -1.04, +0.15, -0.44, +0.32 and -0.14 esd from the truth (WP-2002, the
    # closing windows), so a one-esd bar fails a third of correct fits.
    assert abs(slope.value - truth) < 2 * slope.esd, (slope.value, slope.esd, truth)
    a_ref = A0 * (1.0 + RAMP * (750.0 - 300.0) / 100.0)
    assert abs(intercept.value - a_ref) < 3 * intercept.esd

    structure, ins = _start_models()
    series = rx.refine_sequential(patterns, structure, ins, x=temps,
                                  plan="mccusker_default")
    traj = series.trajectory("phases.0.cell.a")
    a = np.array(traj.value)
    w = 1.0 / np.array(traj.stderr, dtype=float) ** 2
    x = np.column_stack([np.ones(len(temps)), np.array(temps) - 750.0])
    line_cov = np.linalg.inv(x.T @ (w[:, None] * x))
    assert slope.esd <= np.sqrt(line_cov[1, 1]), (slope.esd, np.sqrt(line_cov[1, 1]))
    assert abs(float((line_cov @ x.T @ (w * a))[1]) - truth) < 3 * np.sqrt(line_cov[1, 1])
    # the truth is the declared line, so its form stands
    (form,) = result.parametric_form
    assert (form.n_patterns, form.tied.dof, form.rejected) == (10, 8, False), form
    assert "REJECTED" not in series.summary(deliverable="series", parametric=result)


@pytest.mark.parametrize("bow, rejected", [(0.0, False), (0.01, True)],
                         ids=["line", "bowed"])
def test_a_line_equation_is_rejected_by_a_ramp_that_bends(bow, rejected):
    """The form test on the slow test's ten-pattern LaB6 ramp, its truth the
    line or the line bowed by 1 % of its half-excursion at mid-ramp.  The
    line reads 7.6 against the cut 15.5 for 8 directions, and the bow 4 461
    (macOS arm64), so either verdict has a margin of two or more.  Fast,
    at 1.5 s a joint fit serially and 3 s under ``-n auto``, because the
    bowed row is the only fit-level check that a wrong form is caught and
    says so."""
    from tests.test_sequential import A0, RAMP, _simulate, _start_models

    temps = np.array([300.0 + 100.0 * k for k in range(10)])
    u = (temps - 750.0) / 450.0
    a = A0 * (1.0 + RAMP * (temps - 300.0) / 100.0) + bow * A0 * RAMP * 4.5 * (u * u - 1.0)
    patterns = [_simulate(float(a[k]), seed=k) for k in range(10)]
    structure, ins = _start_models()
    result = refine_multi(
        patterns, structure, [ins] * 10, plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps.tolist()}, units={"T": "K"}),
        parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="polynomial", terms=[[], ["T"]])])
    (form,) = result.parametric_form
    tied = form.tied
    assert (form.equation, form.target, form.n_patterns, form.n_subset, tied.dof) == (
        "a", "phases.0.cell.a", 10, 10, 8)
    assert tied.cut == pytest.approx(15.507, abs=1e-3)
    assert form.rejected is tied.rejected is rejected, form
    assert form.others_freed is None              # one equation: one reading
    assert result.parametric_form_joint is None   # and no joint one
    from scipy.stats import chi2
    assert tied.p_value == chi2.sf(tied.statistic, tied.dof)
    assert (tied.p_value < 0.05) is rejected
    found = [d for d in result.diagnostics if d.code == "PARAMETRIC_FORM_REJECTED"]
    text = str(result)
    p = "p < 0.001" if rejected else f"p = {tied.p_value:.2g}"
    assert f"({p}) for 8 directions over 10 of 10 patterns" in text
    # every pattern's cell and both coefficients are the equation's, in the joint
    # rows, in a histogram's view and in the notebook table
    assert {p.path for p in result.parameters if p.equations} == (
        {"vars.a_0", "vars.a_1"}
        | {f"hist.{h}.phases.0.cell.{k}" for h in range(10) for k in "abc"})
    assert result.for_histogram(3).parameter("phases.0.cell.a").equations == ["a"]
    assert ["path", "value", "at_bound", "equations"] in [
        line.split() for line in result._repr_html_().splitlines()]
    # the equation's covariance: its diagonal is each esd squared, bit for bit, and
    # at each pattern's coordinate the equation is that pattern's row
    (equation,) = result.parametric_equations
    intercept, slope = result.parametric
    assert equation.equation == ParametricEquation(name="a", target="phases.0.cell.a", basis="polynomial",
                                    terms=[[], ["T"]], reference={"T": 750.0},
                                    scale={"T": 450.0})
    assert equation.span == {"T": (300.0, 1200.0)}
    assert [equation.covariance[j][j] for j in range(2)] == [intercept.esd ** 2, slope.esd ** 2]
    assert equation.covariance[0][1] == equation.covariance[1][0] != 0.0
    for h in (0, 4, 9):
        v = result.parametric_value("a", {"T": float(temps[h])})
        row = result.parameter(f"hist.{h}.phases.0.cell.a")
        assert v.value == pytest.approx(row.value, rel=1e-13, abs=0.0)
        assert v.esd == pytest.approx(row.stderr, rel=1e-9)
        assert (v.outside, v.form_rejected, v.unit) == ([], rejected, "Å")
    at_ref = result.parametric_value("a", {"T": 750.0})
    assert (at_ref.value, at_ref.esd) == (intercept.value, intercept.esd)
    room = result.parametric_value("a", {"T": 293.0})
    assert room.outside == ["T"] and room.esd > at_ref.esd
    assert "extrapolating in T" in str(room)
    assert rx.RefinementResult.model_validate_json(
        result.model_dump_json()).parametric_equations == result.parametric_equations
    if not rejected:
        # a single fit records that no equation set its rows; a row from before the
        # field reads unrecorded, never "no equation"
        single = rx.refine(patterns[0], *_start_models(), plan="mccusker_default")
        assert single.parameters and all(p.equations == [] for p in single.parameters)
        assert ["path", "value", "at_bound"] in [
            line.split() for line in single._repr_html_().splitlines()]
        old = single.parameters[0].model_dump(mode="json", exclude={"equations"})
        assert type(single.parameters[0]).model_validate(old).equations is None
    if rejected:
        (d,) = found
        assert d.level == "warning" and d.where == ["vars.a_0", "vars.a_1"]
        assert d.value == tied.statistic
        assert "form REJECTED" in text
    else:
        assert not found and "form not rejected" in text


# -- the blocked joint Jacobian (WP-1325's scalable solver) -------------------

#: the synthetic library's known surface: a(x, y) = A0·(1 + Σ p·term), the
#: terms of :data:`LIBRARY_TERMS`, x and y the position on a [0, 1]² wafer
LIBRARY_SURFACE = {"x": 2.0e-3, "y": 1.5e-3, "x*y": 1.0e-3}
LIBRARY_TERMS = [[], ["x"], ["y"], ["x", "y"]]
#: what ``mccusker_default`` frees, as one stage: each pattern's ten own
#: columns (scale, three background terms, zero, U, V, W, X, Y) beside the
#: four shared coefficients
LIBRARY_GLOBS = ["phases.*.scale", "instrument.background.*", "instrument.zero_shift",
                 "phases.*.cell.*", "instrument.profile.*"]


def library(n: int, *, seed: int = 0, tt_max: float = 18.0):
    """``n`` LaB6 patterns at random wafer positions, the cell on the known
    surface: ``(patterns, coordinates, equation)``.  ``tests/test_sequential``'s
    ``_simulate`` (λ = 0.4139 Å, Poisson noise), 3 000 points at the default
    ``tt_max``; ``docs/wp/1325-measure/scaling.py`` builds its libraries here.
    """
    from tests.test_sequential import A0, _simulate

    rng = np.random.default_rng(seed)
    x, y = rng.uniform(0.0, 1.0, size=(2, n))
    p = LIBRARY_SURFACE
    a = A0 * (1.0 + p["x"] * x + p["y"] * y + p["x*y"] * x * y)
    patterns = [_simulate(float(a[k]), seed=100_000 * seed + k, tt_max=tt_max)
                for k in range(n)]
    coords = CoordinateTable(columns={"x": x.tolist(), "y": y.tolist()})
    equation = ParametricEquation(name="a", target="phases.0.cell.a", basis="polynomial",
                        terms=LIBRARY_TERMS)
    return patterns, coords, equation


def library_truth(reference: dict[str, float]) -> dict[str, float]:
    """The surface's coefficients about ``reference``, per unit of x and y —
    the expansion of :data:`LIBRARY_SURFACE` in (x − x_r), (y − y_r), which is
    how ``RefinementResult.parametric`` reports them."""
    from tests.test_sequential import A0

    p, xr, yr = LIBRARY_SURFACE, reference["x"], reference["y"]
    return {"1": A0 * (1.0 + p["x"] * xr + p["y"] * yr + p["x*y"] * xr * yr),
            "x": A0 * (p["x"] + p["x*y"] * yr), "y": A0 * (p["y"] + p["x*y"] * xr),
            "x*y": A0 * p["x*y"]}


class _Probe(MultiHistogramRefinement):
    """Keeps the last stage's solver outcome, which the result does not carry."""

    def _build_result(self, models, outcome, *args, **kwargs):
        self.outcome_ = outcome
        return super()._build_result(models, outcome, *args, **kwargs)


_PROBLEMS: dict[int, tuple] = {}


def _library_problem(n: int):
    """A compiled ``n``-pattern library with every column of the last stage
    free: ``(mtable, models)``, 1 400 points a pattern, built once."""
    if n not in _PROBLEMS:
        from tests.test_sequential import _start_models

        patterns, coords, equation = library(n, tt_max=10.0)
        s, ins = _start_models()
        mt = MultiParameterTable(s, [ins] * n, coordinates=coords, parametric=[equation])
        mt.set_vary(["*"], False)
        mt.set_vary(LIBRARY_GLOBS, True)
        mt.apply_to_models()
        models = [compile_model(mt.structures[h], mt.instruments[h], patterns[h],
                                mode="rietveld") for h in range(n)]
        _PROBLEMS[n] = (mt, models)
    return _PROBLEMS[n]


def _random_arrow(seed: int, *, n_blocks: int = 5, rows: int = 60, n_shared: int = 3,
                  n_own: int = 4, n_pen=(0, 2, 0, 1, 0)) -> BlockJacobian:
    """A random joint Jacobian in blocks, columns in units spanning six
    decades and each block's columns in a shuffled (table) order."""
    rng = np.random.default_rng(seed)
    n = n_shared + n_blocks * n_own
    units = 10.0 ** rng.uniform(-3.0, 3.0, size=n)
    blocks, maps = [], []
    for h in range(n_blocks):
        cm = np.concatenate([np.arange(n_shared), n_shared + h * n_own + np.arange(n_own)])
        cm = cm[rng.permutation(len(cm))]
        blocks.append(rng.standard_normal((rows + n_pen[h], len(cm))) * units[cm])
        maps.append(cm)
    return BlockJacobian(blocks, maps, [rows] * n_blocks, list(n_pen), n)


def _own(bj: BlockJacobian, h: int, n_shared: int = 3) -> np.ndarray:
    """Block ``h``'s own columns, as positions in that block."""
    return np.flatnonzero(bj.col_maps[h] >= n_shared)


def test_the_layout_follows_the_dense_size_unless_forced():
    rows = blocked.DENSE_JACOBIAN_MAX_BYTES // (8 * 100)
    assert blocked.choose_layout(rows, 100, "lm") == "dense"
    assert blocked.choose_layout(rows + 1, 100, "lm") == "blocked"
    # TRF factorises the dense matrix itself: past the size it says what it costs
    with pytest.warns(RuntimeWarning, match="has no blocked path"):
        assert blocked.choose_layout(rows + 1, 100, "trf") == "dense"
    was = blocked.set_layout("blocked")
    try:
        assert blocked.choose_layout(10, 3, "lm") == "blocked"
        with pytest.raises(ValueError, match="only by solver='lm'"):
            blocked.choose_layout(10, 3, "trf")
        assert blocked.set_layout("dense") == "blocked"
        assert blocked.choose_layout(rows + 1, 100, "lm") == "dense"
    finally:
        blocked.set_layout(was)
    with pytest.raises(ValueError, match="unknown Jacobian layout"):
        blocked.set_layout("sparse")
    with pytest.raises(ValueError, match="unknown Jacobian layout"):
        _multi_closures([], None, layout="sparse")


def test_a_block_jacobian_is_the_dense_one_entry_for_entry():
    """The same entries, never scattered: every reader of the blocks reads
    what it read off the dense matrix, to the bit where nothing is summed and
    to rounding where a sum over rows is taken per block."""
    mt, models = _library_problem(6)
    weights = [1.0 + 0.25 * h for h in range(6)]
    residual, dense, n_data = _multi_closures(models, mt, weights=weights)
    _, blocks, _ = _multi_closures(models, mt, weights=weights, layout="blocked")
    x = mt.x0()
    J, bj = dense(x), blocks(x)
    assert isinstance(bj, BlockJacobian) and bj.shape == J.shape
    assert np.array_equal(bj.toarray(), J)
    assert np.array_equal(bj.data_rows().toarray(), J[:n_data])
    off = np.concatenate([[0], np.cumsum([len(m.tt) for m in models])])
    for h in range(6):
        assert np.array_equal(bj.block(h), J[off[h]:off[h + 1]][:, mt.col_map(h)])
    r = residual(x)
    absj = np.abs(J)
    A, g = lm._normal_equations(bj, r)
    assert np.all(np.abs(A - J.T @ J) <= 1e-13 * (absj.T @ absj))
    assert np.all(np.abs(g + J.T @ r) <= 1e-13 * (absj.T @ np.abs(r)))
    assert np.all(np.abs(bj.rmatvec(r) - J.T @ r) <= 1e-13 * (absj.T @ np.abs(r)))
    assert column_rescale(bj) is None and column_rescale(J) is None
    np.testing.assert_allclose(column_norms(bj), np.linalg.norm(J, axis=0), rtol=1e-14)
    np.testing.assert_allclose(_residual_cosine(bj, r), _residual_cosine(J, r),
                               rtol=0, atol=1e-13)
    gone = [0, int(mt.col_map(2)[-1])]
    assert np.array_equal(bj.without_columns(gone).toarray(),
                          np.where(np.isin(np.arange(J.shape[1]), gone), 0.0, J))


def test_a_chart_moves_a_block_jacobian_as_it_moves_the_dense_one():
    from rietx.optimize.least_squares import LSQOutcome

    bj = _random_arrow(11)
    J = bj.toarray()
    signs = np.where(np.arange(bj.n_cols) % 3 == 0, -1.0, 1.0)
    assert np.array_equal(bj.scaled_columns(signs).toarray(), J * signs)
    t = np.eye(bj.n_cols)
    t[0, 1], t[2, 0] = 0.3, -0.2                 # shared columns among themselves
    own = bj.col_maps[1][_own(bj, 1)]
    t[own[0], own[1]] = 0.5                      # one block's own among themselves
    np.testing.assert_allclose(bj.matmul_chart(t).toarray(), J @ t,
                               rtol=0, atol=1e-13 * np.abs(J).max())
    t[own[0], bj.col_maps[2][_own(bj, 2)][0]] = 1.0
    with pytest.raises(ValueError, match="no block form"):
        bj.matmul_chart(t)
    theta = np.zeros(bj.n_cols)
    out = rechart_outcome(
        LSQOutcome(theta, 0.0, 0.0, 0, "converged", bj, None, None,
                   residual_cosine=np.full(bj.n_cols, 0.1)), theta, signs)
    assert np.array_equal(out.jac.toarray(), J * signs)


@pytest.mark.parametrize("n", [6, 14], ids=["bvls", "projected-cg"])
def test_the_blocked_step_is_the_dense_step(n):
    """WP-1125's 6.6e-7 relative, on the first accepted points of a real
    joint fit, with no bound active and on both step solvers: BVLS at 64
    columns, projected CG at 144 (above ``BVLS_MAX_COLUMNS``).  Measured
    2e-12 and 7.2e-8: the projected CG stops at 1e-10 of its gradient, so its
    step carries that tolerance times the conditioning, not A's rounding."""
    mt, models = _library_problem(n)
    residual, dense, _ = _multi_closures(models, mt)
    _, blocks, _ = _multi_closures(models, mt, layout="blocked")
    assert (len(mt.free_paths) > lm.BVLS_MAX_COLUMNS) == (n == 14)
    lo, hi = mt.bounds()
    points: list[np.ndarray] = []
    lm.minimize(residual, dense, mt.x0(), lo=lo, hi=hi, max_nfev=6,
                callback=lambda x, cost: points.append(x.copy()))
    assert len(points) >= 2
    free = np.full(len(mt.free_paths), np.inf)
    worst = 0.0
    for x in [mt.x0(), *points[:3]]:
        r = residual(x)
        A_d, b_d = lm._normal_equations(dense(x), r)
        A_b, b_b = lm._normal_equations(blocks(x), r)
        for lam in (0.0, 1e-3, 1.0):
            step_d, side_d = lm._solve_step(A_d, b_d, lam, x, -free, free, n_rows=len(r))
            step_b, side_b = lm._solve_step(A_b, b_b, lam, x, -free, free, n_rows=len(r))
            assert not side_d.any() and not side_b.any()
            worst = max(worst, float(np.linalg.norm(step_b - step_d)
                                     / np.linalg.norm(step_d)))
    assert worst <= 6.6e-7, worst


@pytest.mark.xdist_group("parametric-series")
@pytest.mark.parametrize("n", [6, 14], ids=["bvls", "projected-cg"])
def test_a_blocked_fit_lands_on_the_dense_answer(n):
    """The item's bar: every free parameter within 0.01 esd of the dense
    path's answer, forced each way (measured ≤ 6.4e-6 esd at 6-20 patterns).
    The esds to 1e-3 relative: the two answers are two stopping points, and
    the esd read at each moved up to 3.8e-5 between them (14 patterns), where
    at one point the two covariances agree to 4e-12 (the tests below)."""
    from tests.test_sequential import _start_models

    patterns, coords, equation = library(n, tt_max=10.0)
    results, layouts = {}, {}
    for layout in blocked.LAYOUTS:
        was = blocked.set_layout(layout)
        try:
            s, ins = _start_models()
            ref = _Probe(s, [ins] * n, coordinates=coords, parametric=[equation])
            results[layout] = ref.fit(patterns, plan="mccusker_default")
        finally:
            blocked.set_layout(was)
        layouts[layout] = ref.outcome_.jacobian_layout
    assert layouts == {"dense": "dense", "blocked": "blocked"}
    dense, block = results["dense"], results["blocked"]
    assert dense.status == block.status == "converged"
    rows = {p.path: p for p in block.parameters}
    measured = [p for p in dense.parameters if p.stderr]
    assert {p.path for p in measured} == {p.path for p in block.parameters if p.stderr}
    for p in measured:
        q = rows[p.path]
        assert abs(q.value - p.value) <= 0.01 * p.stderr, p.path
        assert q.stderr == pytest.approx(p.stderr, rel=1e-3), p.path
    for a, b in zip(dense.parametric, block.parametric, strict=True):
        assert abs(a.value - b.value) <= 0.01 * a.esd
    assert {d.code for d in block.diagnostics} == {d.code for d in dense.diagnostics}
    assert block.statistics.rwp == pytest.approx(dense.statistics.rwp, rel=1e-9)


@pytest.mark.parametrize("case", ["plain", "gradient-free", "far-scaled"])
def test_the_schur_covariance_is_the_dense_pseudo_inverse(case):
    """Equilibrated first, then the Schur form; a gradient-free column comes
    back at infinite variance and no correlation, a column at 1e-170 at the
    esd its rescale (WP-1463) gives the dense path, and the esds and
    correlations agree to 1e-10."""
    bj = _random_arrow(3)
    if case == "gradient-free":
        bj = bj.without_columns([1, int(bj.col_maps[3][_own(bj, 3)][0])])
    elif case == "far-scaled":
        f = np.ones(bj.n_cols)
        f[[2, 9]] = 1e-170
        bj = bj.scaled_columns(f)
        np.testing.assert_array_equal(column_rescale(bj), column_rescale(bj.toarray()))
    r = np.random.default_rng(4).standard_normal(bj.shape[0])
    n_data = sum(bj.n_data)
    esd_b, corr_b = covariance_estimates(bj, r, bj.n_cols, n_data=n_data)
    esd_d, corr_d = covariance_estimates(bj.toarray(), r, bj.n_cols, n_data=n_data)
    finite = np.isfinite(esd_d)
    assert np.array_equal(finite, np.isfinite(esd_b))
    assert finite.sum() == bj.n_cols - (2 if case == "gradient-free" else 0)
    np.testing.assert_allclose(esd_b[finite], esd_d[finite], rtol=1e-10)
    np.testing.assert_allclose(corr_b, corr_d, rtol=0, atol=1e-10)


def test_a_joint_covariance_at_a_real_point_is_the_dense_one():
    """The same at the start of a real library fit, χ² and the Bérar-Lelann
    factor included."""
    mt, models = _library_problem(6)
    residual, dense, n_data = _multi_closures(models, mt)
    _, blocks, _ = _multi_closures(models, mt, layout="blocked")
    x = mt.x0()
    r = residual(x)
    esd_b, corr_b = covariance_estimates(blocks(x), r, len(x), n_data=n_data)
    esd_d, corr_d = covariance_estimates(dense(x), r, len(x), n_data=n_data)
    np.testing.assert_allclose(esd_b, esd_d, rtol=1e-10)
    np.testing.assert_allclose(corr_b, corr_d, rtol=0, atol=1e-10)


@pytest.mark.parametrize("case", ["random", "library"])
def test_the_eigenvalue_switch_moves_only_the_cut(case, monkeypatch):
    """``_DENSE_EIGEN_MAX`` (64 live columns) switches |λ|max of the
    equilibrated arrow from a dense eigensolve to ARPACK Lanczos at 1e-6
    relative (WP-2002, B10).  |λ|max does one thing, place the
    pseudo-inverse cut at ``PINV_RCOND`` of it, so the switch is
    answer-invariant wherever no eigenvalue lies within that tolerance of the
    cut: the same directions are discarded, and the covariance does not read
    |λ|max otherwise.  So the claim is a tolerance on |λ|max and bit-identity
    on the esds, correlations and discarded directions.

    Measured on 2026-10-21: the two agree to 4e-16-1.4e-14 relative on 83- and
    84-column cases (3.7e-14 at 204 columns), and the nearest eigenvalue sits
    2.4e10 times the cut away or more.  Made to fail once by scaling scipy's ``eigsh``
    result by 1.01: the |λ|max assertion fired, and the covariance stayed
    bit-identical, which is why the tolerance is asserted on its own.
    """
    if case == "random":
        bj = _random_arrow(3, n_blocks=20, n_pen=((0, 2, 0, 1) * 5))
        r = np.random.default_rng(4).standard_normal(bj.shape[0])
        n_free, n_data = bj.n_cols, sum(bj.n_data)
    else:
        mt, models = _library_problem(8)
        residual, _dense, n_data = _multi_closures(models, mt)
        _, blocks, _ = _multi_closures(models, mt, layout="blocked")
        x = mt.x0()
        bj, r, n_free = blocks(x), residual(x), len(x)
    arrow = blocked._Arrow(bj)
    m = len(arrow.order())
    assert m > blocked._DENSE_EIGEN_MAX, "the case does not cross the switch"
    lanczos = arrow.largest_eigenvalue()
    got = (covariance_estimates(bj, r, n_free, n_data=n_data), discarded_directions(bj))
    monkeypatch.setattr(blocked, "_DENSE_EIGEN_MAX", m)
    dense = arrow.largest_eigenvalue()
    want = (covariance_estimates(bj, r, n_free, n_data=n_data), discarded_directions(bj))
    assert abs(lanczos - dense) <= 1e-6 * dense
    cut = blocked.PINV_RCOND * dense
    lam = np.abs(np.linalg.eigvalsh(arrow.dense()))
    assert np.min(np.abs(lam - cut)) > 1e-6 * cut, "an eigenvalue sits at the cut"
    (esd_l, corr_l), (n_l, touched_l) = got
    (esd_d, corr_d), (n_d, touched_d) = want
    assert np.array_equal(esd_l, esd_d, equal_nan=True)
    assert np.array_equal(corr_l, corr_d, equal_nan=True)
    assert n_l == n_d and np.array_equal(touched_l, touched_d)


@pytest.mark.parametrize("where", ["own", "shared"])
def test_a_flat_direction_is_discarded_where_the_dense_solve_discards_it(where):
    """Two columns made one, inside one block's own columns or across the
    border in every block: one discarded direction, touching the same two
    columns, read on the blocks as on the dense matrix (WP-1535)."""
    bj = _random_arrow(5)
    assert discarded_directions(bj)[0] == discarded_directions(bj.toarray())[0] == 0
    blocks = [b.copy() for b in bj.blocks]
    if where == "own":
        a, b = _own(bj, 2)[:2]
        blocks[2][:, b] = 2.0 * blocks[2][:, a]
        pair = {int(bj.col_maps[2][a]), int(bj.col_maps[2][b])}
    else:
        for h, blk in enumerate(blocks):
            cm = list(bj.col_maps[h])
            blk[:, cm.index(1)] = -3.0 * blk[:, cm.index(0)]
        pair = {0, 1}
    flat = BlockJacobian(blocks, bj.col_maps, bj.n_data, bj.n_pen, bj.n_cols)
    n_d, touched_d = discarded_directions(flat.toarray())
    n_b, touched_b = discarded_directions(flat)
    assert n_b == n_d == 1
    assert set(touched_b.tolist()) == set(touched_d.tolist()) == pair


def test_the_moment_tests_refit_is_the_dense_refit():
    """``_refitted_increase`` by eliminating each block's own columns."""
    bj = _random_arrow(7).data_rows()
    rng = np.random.default_rng(8)
    r_stop, r_point = rng.standard_normal((2, bj.shape[0]))
    for angles in ([0], [2, int(bj.col_maps[1][_own(bj, 1)][0])]):
        want = _refitted_increase(bj.toarray(), angles, r_stop, r_point)
        assert _refitted_increase(bj, angles, r_stop, r_point) == pytest.approx(
            want, rel=1e-9)


def _resid_after(m: np.ndarray, r: np.ndarray) -> np.ndarray:
    """``r`` less its least-squares projection on ``m``'s columns, each
    scaled to unit norm first, as the blocked arrow equilibrates them."""
    m = m / np.linalg.norm(m, axis=0)
    return r - m @ np.linalg.lstsq(m, r, rcond=None)[0]


def test_the_form_tests_gain_is_the_dense_least_squares_gain():
    """``added_columns_gain`` on blocks: min‖r − Jβ‖² with ``hold`` left out,
    less the same with ``drop`` left out as well and each block's own extra
    columns in, as dense least squares reads it, penalty rows included."""
    bj = _random_arrow(9)
    rng = np.random.default_rng(10)
    r = rng.standard_normal(bj.shape[0])
    n_rows = [b.shape[0] for b in bj.blocks]
    extra = [rng.standard_normal((n, 1)) if h % 2 == 0 else None
             for h, n in enumerate(n_rows)]
    # the extra columns stacked as the residual is: a block of their own
    e_dense = BlockJacobian(
        [np.zeros((n, 0)) if e is None else e for n, e in zip(n_rows, extra)],
        [np.zeros(0, dtype=int) if e is None else np.array([j]) for j, e in
         enumerate(extra)], bj.n_data, bj.n_pen, len(extra)).toarray()
    e_dense = e_dense[:, np.any(e_dense != 0.0, axis=0)]
    dense = bj.toarray()
    hold = [int(bj.col_maps[2][_own(bj, 2)][0])]
    drop = [1]
    kept = np.setdiff1d(np.arange(bj.n_cols), hold)
    alt = np.hstack([dense[:, np.setdiff1d(kept, drop)], e_dense])
    want = (_resid_after(dense[:, kept], r) @ _resid_after(dense[:, kept], r)
            - _resid_after(alt, r) @ _resid_after(alt, r))
    gain, rank = blocked.added_columns_gain(bj, r, extra, drop, hold)
    assert rank == e_dense.shape[1] - len(drop) == 2
    assert gain == pytest.approx(want, rel=1e-9)


def test_an_equation_with_the_others_freed_is_the_difference_of_two_dense_gains():
    """``ParametricFormTest.others_freed``: two ``constant`` equations on the
    border's first two columns, each one's per-pattern copies its targets.
    With B freed too, A's gain is the χ² both swaps remove less what B's swap
    alone removes, as dense least squares reads them, and so are its
    directions.  The verdict is that reading's, and the joint reading is the
    χ² both swaps remove; a fit with one equation gets neither."""
    bj = _random_arrow(11)
    rng = np.random.default_rng(12)
    r = rng.standard_normal(bj.shape[0])
    n, n_data = bj.n_blocks, int(sum(bj.n_data))
    names = ["vars.A_0", "vars.B_0"] + [f"own{j}" for j in range(2, bj.n_cols)]

    def equation(name: str) -> ResolvedParametric:
        return ResolvedParametric(
            equation=ParametricEquation(name=name, target="phases.0.cell.a", basis="constant"),
            patterns=list(range(n)), phi=np.ones((n, 1)), labels=["1"],
            divisors=np.ones(1), units=[None])

    (a, b), joint = form_tests([equation("A"), equation("B")], bj, r, n_data, names, {}, [])
    dense = bj.toarray()

    def copies(col: int) -> np.ndarray:
        """Column ``col`` split into one column per block's rows, stacked as
        the residual is."""
        own = [blk[:, list(cm).index(col)][:, None]
               for blk, cm in zip(bj.blocks, bj.col_maps, strict=True)]
        return BlockJacobian(own, [np.array([h]) for h in range(n)], bj.n_data,
                             bj.n_pen, n).toarray()

    def left(cols: list[int], extra: list[np.ndarray]) -> float:
        m = np.hstack([dense[:, np.setdiff1d(np.arange(bj.n_cols), cols)], *extra])
        res = _resid_after(m, r)
        return float(res @ res)

    only_b, both = left([1], [copies(1)]), left([0, 1], [copies(0), copies(1)])
    only_a = left([0], [copies(0)])
    held = left([], [])
    assert (a.tied.dof, a.others_freed.dof) == (n - 1, n - 1)
    assert a.others_freed.statistic / a.tied.statistic == pytest.approx(
        (only_b - both) / (held - only_a), rel=1e-8)
    assert b.others_freed.statistic / b.tied.statistic == pytest.approx(
        (only_a - both) / (held - only_b), rel=1e-8)
    for eq_test, other in ((a, b), (b, a)):
        assert eq_test.rejected is eq_test.others_freed.rejected
        assert eq_test.provisional_on == ([other.equation] if other.rejected else [])
    assert joint.dof == 2 * (n - 1)
    assert joint.statistic / a.tied.statistic == pytest.approx(
        (held - both) / (held - only_a), rel=1e-8)
    (alone,), none = form_tests([equation("A")], bj, r, n_data, names, {}, [])
    assert alone.others_freed is None and alone.tied == a.tied and none is None
    assert alone.rejected is alone.tied.rejected


def _two_readings(tied_stat: float, tied_p: float, freed_stat: float, freed_p: float,
                  cut: float = 44.985, dof: int = 31):
    """Two ``ParametricFormReading``s at one cut, each rejecting past it."""
    from rietx.schemas.parametric import ParametricFormReading

    return tuple(ParametricFormReading(dof=dof, statistic=x, cut=cut, rejected=x > cut,
                                       p_value=p)
                 for x, p in ((tied_stat, tied_p), (freed_stat, freed_p)))


def test_an_equation_the_freed_reading_rejects_is_printed_and_warned_as_such():
    """An equation that passes with the other equations tied and is rejected with them
    freed, as the ZrMo₂O₈ cubic equation read over the earlier χ²_red·f².  The
    freed reading is the verdict and prints first, and the warning quotes it
    and says what the tied one read."""
    from types import SimpleNamespace

    from rietx.multi import _parametric_form_diagnostics
    from rietx.schemas.parametric import ParametricFormTest
    from rietx.schemas.results import _form_line

    tied, freed = _two_readings(42.8, 0.0771, 48.6, 0.0232)
    t = ParametricFormTest(equation="cubic_a", target="phases.1.cell.a", n_patterns=33,
                           n_subset=33, rejected=True, tied=tied, others_freed=freed,
                           provisional_on=[])
    assert _form_line(t).splitlines() == [
        "      form REJECTED over 33 of 33 patterns:",
        "        with the other equations freed, REJECTED: 48.6 past the cut 45.0 "
        "(p = 0.023) for 31 directions",
        "        with the other equations tied, not rejected: 42.8 within the cut 45.0 "
        "(p = 0.077) for 31 directions"]
    mt = SimpleNamespace(parametric=[SimpleNamespace(name="cubic_a",
                                                     paths=["vars.cubic_a_0",
                                                            "vars.cubic_a_1"])])
    (d,) = _parametric_form_diagnostics(mt, [t])
    assert d.value == 48.6 and d.where == ["vars.cubic_a_0", "vars.cubic_a_1"]
    assert "with the other equations' targets freed (with them tied it read 42.8" in d.message


def test_equations_the_joint_reading_alone_rejects_are_warned_together_naming_none():
    """Two equations that each pass with the other freed, while freeing both
    removes more χ² than the cut for their directions together: one warning,
    ``where`` both equations' coefficients, saying no equation's own reading rejects.
    An equation rejected on its own reading takes the warning instead, and the
    printed block closes on the joint reading either way."""
    from types import SimpleNamespace

    from rietx.multi import _parametric_form_diagnostics
    from rietx.schemas.parametric import (
        ParametricCoefficient,
        ParametricFormReading,
        ParametricFormTest,
    )
    from rietx.schemas.results import _parametric_lines

    mt = SimpleNamespace(parametric=[SimpleNamespace(name=n, paths=[f"vars.{n}_0"])
                                     for n in ("A", "B")])

    def equation(name: str, freed_stat: float) -> ParametricFormTest:
        tied, freed = _two_readings(30.0, 0.5, freed_stat, 0.1)
        return ParametricFormTest(equation=name, target=f"phases.0.cell.{name.lower()}",
                                  n_patterns=33, n_subset=33, rejected=freed.rejected,
                                  tied=tied, others_freed=freed, provisional_on=[])

    joint = ParametricFormReading(dof=62, statistic=90.0, cut=81.381, rejected=True,
                                  p_value=0.012)
    passing = [equation("A", 40.0), equation("B", 41.0)]
    (d,) = _parametric_form_diagnostics(mt, passing, joint)
    assert (d.code, d.value, d.where) == (
        "PARAMETRIC_FORM_REJECTED", 90.0, ["vars.A_0", "vars.B_0"])
    assert "Parametric equations 'A', 'B' together" in d.message
    assert "No equation's own reading rejects it" in d.message
    (d,) = _parametric_form_diagnostics(mt, [equation("A", 50.0), equation("B", 41.0)], joint)
    assert d.where == ["vars.A_0"]
    assert _parametric_form_diagnostics(mt, passing, joint.model_copy(
        update={"statistic": 70.0, "rejected": False})) == []
    rows = [ParametricCoefficient(equation=n, target=t.target, term="1", path=f"vars.{n}_0",
                                  value=1.0, esd=0.1, vary=True, unit=None,
                                  reference=None)
            for n, t in zip("AB", passing, strict=True)]
    assert _parametric_lines(rows, passing, joint)[-1] == (
        "    the 2 tested equations together: form REJECTED: 90.0 past the cut 81.4 "
        "(p = 0.012) for 62 directions")


def test_a_verdict_beside_a_rejected_equation_is_marked_provisional():
    """Two equations rejected together: each verdict names the other in
    ``provisional_on``, the printed line says so, and each warning calls its
    verdict provisional and tells the reader to read the others again."""
    from types import SimpleNamespace

    from rietx.multi import _parametric_form_diagnostics
    from rietx.schemas.parametric import ParametricFormTest
    from rietx.schemas.results import _form_line

    tied, freed = _two_readings(3122.0, 0.0, 51.4, 0.036, cut=48.6, dof=34)
    tests = [ParametricFormTest(equation=n, target=f"phases.{k}.cell.a", n_patterns=37,
                                n_subset=37, rejected=True, tied=tied, others_freed=freed,
                                provisional_on=[m for m in ("zrp_a", "si_a") if m != n])
             for k, n in enumerate(("zrp_a", "si_a"))]
    assert _form_line(tests[1]).splitlines()[-1] == (
        "        provisional: 'zrp_a' rejected too, and moved the answer this reading "
        "steps from; read it again after fixing and refitting")
    mt = SimpleNamespace(parametric=[SimpleNamespace(name=n, paths=[f"vars.{n}_0"])
                                     for n in ("zrp_a", "si_a")])
    a, b = _parametric_form_diagnostics(mt, tests)
    assert "The verdict is provisional: 'si_a' rejected too" in a.message
    assert "The verdict is provisional: 'zrp_a' rejected too" in b.message
    assert "read them again after the refit" in a.suggestion


def test_an_equation_with_no_direction_beside_the_others_is_named_by_the_joint_warning():
    """An equation whose targets the others' already cover adds no direction
    freed, so its verdict is ``None`` even when its tied reading rejects: the
    data cannot tell its misfit from theirs.  The joint warning names it and
    quotes the tied reading, since no other warning carries it."""
    from types import SimpleNamespace

    from rietx.multi import _parametric_form_diagnostics
    from rietx.schemas.parametric import ParametricFormReading, ParametricFormTest

    mt = SimpleNamespace(parametric=[SimpleNamespace(name=n, paths=[f"vars.{n}_0"])
                                     for n in ("A", "B")])
    none = ParametricFormReading(dof=0, statistic=None, cut=None, rejected=None,
                                 p_value=None)
    tied_a, _ = _two_readings(60.0, 0.0006, 30.0, 0.5)
    tied_b, freed_b = _two_readings(30.0, 0.5, 40.0, 0.1)
    tests = [ParametricFormTest(equation="A", target="phases.0.cell.a", n_patterns=33,
                                n_subset=33, rejected=None, tied=tied_a, others_freed=none,
                                provisional_on=[]),
             ParametricFormTest(equation="B", target="phases.1.cell.a", n_patterns=33,
                                n_subset=33, rejected=False, tied=tied_b,
                                others_freed=freed_b, provisional_on=[])]
    joint = ParametricFormReading(dof=31, statistic=70.0, cut=45.0, rejected=True,
                                  p_value=1e-4)
    (d,) = _parametric_form_diagnostics(mt, tests, joint)
    assert d.where == ["vars.A_0", "vars.B_0"]
    assert ("'A' (tied 60.0 for 31 directions, past the cut 45.0) adds no direction "
            "beside the other equations' targets, so no reading of its own can test "
            "it") in d.message
    # every equation with a direction of its own: the clause is absent
    tests[0] = tests[0].model_copy(update={"others_freed": freed_b, "rejected": False})
    (d,) = _parametric_form_diagnostics(mt, tests, joint)
    assert "adds no direction" not in d.message


def test_a_value_carries_the_provisional_mark_and_the_joint_verdict():
    """``ParametricValue`` carries what its esd's assumption rests on beyond its
    own verdict: the other rejected equations, and the joint reading where the
    equation took part in one.  Its printed line says both."""
    from rietx.schemas.parametric import ParametricFormReading, ParametricFormTest

    r = resolve_parametric(_equation(terms=[[], ["T"]]), _coords(300.0, 500.0, 700.0), 3,
                           target_unit="A")
    rows = coefficient_rows(r, dict(zip(r.paths, [4.0, 0.02], strict=True)),
                            dict(zip(r.paths, [1e-5, 2e-5], strict=True)),
                            dict.fromkeys(r.paths, True))
    equation = parametric_equation(r, rows, [0, 1], np.eye(2))
    tied, freed = _two_readings(30.0, 0.5, 40.0, 0.1)
    form = ParametricFormTest(equation=r.name, target=r.target, n_patterns=3, n_subset=3,
                              rejected=False, tied=tied, others_freed=freed,
                              provisional_on=["b"])
    joint = ParametricFormReading(dof=62, statistic=90.0, cut=81.381, rejected=True,
                                  p_value=0.012)
    v = equation.evaluate(rows, form, {"T": 500.0}, joint=joint)
    assert (v.form_rejected, v.provisional_on, v.joint_rejected) == (False, ["b"], True)
    assert str(v).endswith("(form not rejected; provisional beside rejected 'b'; "
                           "the joint reading of every equation rejects the set)")
    # alone in its fit, an equation took part in no joint reading
    alone = form.model_copy(update={"others_freed": None, "provisional_on": []})
    v = equation.evaluate(rows, alone, {"T": 500.0}, joint=joint)
    assert (v.provisional_on, v.joint_rejected) == ([], None)
    assert str(v).endswith("(form not rejected)")


def test_a_patterns_own_target_column_is_read_off_the_coefficients():
    """``target_columns``: in pattern k, J_coef·Φ_kᵀ/‖Φ_k‖² is the target's
    own column, the one an untied table's ``hist.k.`` path carries; a
    skipped pattern has none, and an equation whose coefficient is not free has no
    columns at all."""
    from tests.test_sequential import _start_models

    mt, models = _library_problem(6)
    s, ins = _start_models()
    untied = MultiParameterTable(s, [ins] * 6,
                                 sharing=SharingMap(per_histogram=["phases.0.cell.*"]))
    untied.set_vary(["*"], False)
    untied.set_vary(LIBRARY_GLOBS, True)
    _, jac, _ = _multi_closures(models, mt, layout="blocked")
    cols = target_columns(mt.parametric[0], jac(mt.x0()), mt.free_paths)
    _, jac_u, _ = _multi_closures(models, untied, layout="blocked")
    bju = jac_u(untied.x0())
    for k in range(6):
        own = list(bju.col_maps[k]).index(
            untied.free_paths.index(f"hist.{k}.phases.0.cell.a"))
        want = bju.blocks[k][:, own]
        # the two are finite differences on different steps, the coefficient's
        # and the target's: 1.8e-7 to 8.1e-7 of the column measured (macOS
        # arm64), where a wrong column is off by its own size
        assert np.max(np.abs(cols[k][:, 0] - want)) <= 1e-5 * np.max(np.abs(want))
    bj = jac(mt.x0())
    assert target_columns(mt.parametric[0], bj, mt.free_paths, frozenset({2}))[2] is None
    free = [p for p in mt.free_paths if p != "vars.a_3"]
    assert target_columns(mt.parametric[0], bj, free) is None


def test_a_joint_solve_records_which_layout_it_took():
    """Dense below the size, by default, so every joint golden keeps its bits;
    forced blocked, the same stage on blocks."""
    mt, models = _library_problem(6)
    outcome = run_multi_least_squares(models, mt, max_iter=2)
    assert outcome.jacobian_layout == "dense" and isinstance(outcome.jac, np.ndarray)
    was = blocked.set_layout("blocked")
    try:
        outcome = run_multi_least_squares(models, mt, max_iter=2)
    finally:
        blocked.set_layout(was)
    assert outcome.jacobian_layout == "blocked"
    assert isinstance(outcome.jac, BlockJacobian) and outcome.jac.n_pen == [0] * 6


@pytest.mark.slow
def test_a_library_surface_over_a_hundred_patterns_through_the_blocked_solver():
    """120 patterns, a(x, y) on a known 2-D surface, ten own columns a pattern
    beside four shared coefficients.  Its dense Jacobian would be 2.9 GB, so
    the size rule takes the blocked path unasked."""
    from tests.test_sequential import _start_models

    n = 120
    patterns, coords, equation = library(n)
    s, ins = _start_models()
    ref = _Probe(s, [ins] * n, coordinates=coords, parametric=[equation])
    result = ref.fit(patterns, plan="mccusker_default")
    OUT.mkdir(exist_ok=True)
    for h in (0, n - 1):
        result.for_histogram(h).plot(OUT / f"parametric_library_h{h}.png")
    assert ref.outcome_.jacobian_layout == "blocked"
    assert blocked.dense_jacobian_bytes(3000 * n, 4 + 10 * n) > (
        blocked.DENSE_JACOBIAN_MAX_BYTES)
    assert result.status == "converged"
    assert [c.term for c in result.parametric] == ["1", "x", "y", "x*y"]
    truth = library_truth(result.parametric[0].reference)
    for c in result.parametric:
        assert abs(c.value - truth[c.term]) < 3.0 * c.esd, (c.term, c.value, c.esd,
                                                            truth[c.term])
