"""A user tie written as a formula: ``Refinement.tie(path, expression=...)`` (WP-2118).

The maintainer's rulings of 2026-11-07 set the shape these tests hold: a
formula reads named variables and numbers only (a model parameter is read by
tying it to a variable first); the spelling is a keyword on ``tie``; and a
formula always runs as a formula while ``tie``/``tie_equal`` with a source stay
on the constant matrix, so no linear tie moves.

The acceptance fit is the Debye model of an isotropic displacement parameter,
B = 6h²T/(m·k_B·θ_D²)·[D₁(θ_D/T) + θ_D/(4T)] (James 1962, *The Optical
Principles of the Diffraction of X-rays*, eq 5.33; Willis & Pryor 1975,
*Thermal Vibrations in Crystallography*, §6.2), with 6h²/(m_u·k_B) =
11 490.1 Å²·K per unit of molar mass.  At one temperature only θ_D is free, so
the fit has one variable to recover and the data can determine it.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.expression import debye
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.pattern import PatternData
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    perturbed_models,
)
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"

B_BISO = "phases.0.atoms.1.biso"
LA_BISO = "phases.0.atoms.0.biso"
#: 6h²/(m_u k_B) in Å²·K: h = 6.62607015e-34 J s, k_B = 1.380649e-23 J/K,
#: m_u = 1.66053907e-27 kg (CODATA 2018), so 2.634239e-66 / 2.292622e-50 m²K
DEBYE_CONST = 11490.1
M_BORON = 10.81
TRUE_THD = 1100.0


def debye_text(temperature: float, mass: float = M_BORON) -> str:
    """The Debye-model B as formula text, over the variable ``thD``."""
    return (f"{DEBYE_CONST} / {mass} * {temperature} / thD^2 "
            f"* (debye(thD / {temperature}) + thD / (4 * {temperature}))")


def debye_b(thd: float, temperature: float, mass: float = M_BORON) -> float:
    x = thd / temperature
    return float(DEBYE_CONST / mass * temperature / thd**2 * (debye(x) + x / 4.0))


def _plot(result, tag: str) -> None:
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"tie_expression_{tag}.png"))
    result.plot(path=str(OUT / f"tie_expression_{tag}_highangle.png"),
                two_theta_range=(14.0, 24.0))


def synthesize_at(temperature: float, seed: int) -> PatternData:
    """LaB6 with the boron B set by the Debye model at ``temperature``."""
    s = make_lab6()
    for name in ("a", "b", "c"):
        getattr(s.phases[0].cell, name).value = TRUE_A
    s.phases[0].scale.value = TRUE_SCALE
    s.phases[0].atoms[1].biso.value = debye_b(TRUE_THD, temperature)
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])
    tt = np.arange(3.0, 24.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, blank, mode="rietveld")
    y = model.evaluate(ParameterTable(s, ins).decode(ParameterTable(s, ins).x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


#: the default plan's first stages, then the formula's variable
PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("zero", ["instrument.zero_shift"]),
    rx.Stage("cell", ["phases.*.cell.*"]),
    rx.Stage("profile_w", ["instrument.profile.w"]),
    rx.Stage("debye", ["vars.*"])])


@pytest.fixture
def ref():
    return rx.Refinement(*perturbed_models())


def _rows(ref):
    return {r.path: r for r in ref.parameters()}


# ------------------------------------------------------------------ the verb
def test_a_formula_sets_its_target_and_its_row_reads_as_the_formula(ref):
    ref.add_variable("thD", 900.0, vary=True, min=100.0, max=3000.0)
    assert ref.tie(B_BISO, expression=debye_text(300.0)) == B_BISO
    row = _rows(ref)[B_BISO]
    assert row.value == pytest.approx(debye_b(900.0, 300.0), rel=1e-12)
    assert row.tie.expression == debye_text(300.0)
    assert row.tie.user and row.tie.sources == ["vars.thD"]
    assert not row.locked and not row.refinable
    assert row.held_because == f"tied: = {debye_text(300.0)}"
    # the model holds the value the formula gives, as a linear tie writes it
    assert ref.structure.phases[0].atoms[1].biso.value == row.value
    # and the target is no column of θ: its freedom is the variable's
    assert B_BISO not in ref._working_table().free_paths


def test_a_variable_the_formula_reads_moves_its_target(ref):
    ref.add_variable("thD", 900.0, min=100.0, max=3000.0)
    ref.tie(B_BISO, expression=debye_text(300.0))
    ref.set_values({"vars.thD": 1200.0})
    assert _rows(ref)[B_BISO].value == pytest.approx(debye_b(1200.0, 300.0),
                                                     rel=1e-12)


def test_a_model_parameter_is_read_through_a_variable(ref):
    """Ruling 1: tie the model parameter to a variable, name the variable."""
    ref.add_variable("B_La", 0.3, min=0.0, max=5.0)
    ref.tie(LA_BISO, "vars.B_La")                    # linear, the matrix
    ref.tie(B_BISO, expression="2 * B_La + 0.1")     # a formula, the tree
    ref.set_values({"vars.B_La": 0.45})
    rows = _rows(ref)
    assert rows[LA_BISO].value == 0.45
    assert rows[B_BISO].value == pytest.approx(1.0, rel=1e-15)
    assert rows[LA_BISO].tie.expression is None      # the linear tie stays linear


def test_a_formula_on_a_cubic_edge_carries_the_two_it_ties(ref):
    ref.add_variable("a0", 4.15, min=4.0, max=4.3)
    ref.add_variable("k", 1e-5, min=-1.0, max=1.0)
    ref.tie("phases.0.cell.a", expression="a0 + k * 300")
    rows = _rows(ref)
    for edge in ("b", "c"):
        row = rows[f"phases.0.cell.{edge}"]
        assert row.value == pytest.approx(4.153, rel=1e-14)
        assert row.tie.terms == [("phases.0.cell.a", 1.0)] and not row.tie.user
        assert not row.locked
    assert rows["phases.0.cell.alpha"].locked     # symmetry's own stays locked


# ------------------------------------------------------------------ refusals
@pytest.mark.parametrize(("call", "match"), [
    (lambda r: r.tie(B_BISO, expression="thD_typo * 2"),
     "not a declared variable.*add_variable"),
    (lambda r: r.tie(B_BISO, expression="0.5 * pi"), "reads no variable.*set_values"),
    (lambda r: r.tie(B_BISO, "vars.thD", expression="thD"), "not both"),
    (lambda r: r.tie(B_BISO, expression="thD", scale=2.0), "into the expression"),
    (lambda r: r.tie(B_BISO), "needs a source"),
    (lambda r: r.tie(B_BISO, expression="thD *"), "operand"),
    (lambda r: r.tie("phases.0.atoms.1.occ", expression="0 - thD / 1000"),
     "outside its bounds"),
    (lambda r: r.tie(B_BISO, expression="log(0 - thD)"), "nan"),
    (lambda r: r.tie("phases.0.cell.b", expression="thD / 200"),
     "symmetry outranks a user tie"),
    (lambda r: r.tie("phases.0.cell.alpha", expression="thD / 10"),
     "structurally fixed"),
    (lambda r: r.tie("phases.0.atoms.1.dof.0", expression="thD / 1e4"),
     "displacement from where the fit began"),
    (lambda r: r.tie("vars.thD", expression="thD + 1"), "own expression"),
])
def test_a_formula_is_refused_with_its_reason(ref, call, match):
    ref.add_variable("thD", 900.0, min=100.0, max=3000.0)
    before = dict(ref._ties)
    with pytest.raises((ValueError, TypeError), match=match):
        call(ref)
    assert ref._ties == before          # nothing half-declared


def test_a_formula_target_refuses_a_second_tie_and_a_value(ref):
    ref.add_variable("thD", 900.0, min=100.0, max=3000.0)
    ref.tie(B_BISO, expression=debye_text(300.0))
    with pytest.raises(ValueError, match="already follows .*untie it first"):
        ref.tie(B_BISO, "vars.thD", scale=1e-3)
    with pytest.raises(ValueError, match="carries no freedom"):
        ref.tie(LA_BISO, B_BISO)
    with pytest.raises(ValueError, match="set the variables it reads"):
        ref.set_values({B_BISO: 0.5})
    with pytest.raises(ValueError, match="still has 1 dependent"):
        ref.remove_variable("thD")


# ------------------------------------------------------------------ history
def test_untie_releases_a_formula_and_holds_its_last_value(ref):
    ref.add_variable("thD", 900.0, min=100.0, max=3000.0)
    ref.tie(B_BISO, expression=debye_text(300.0))
    value = _rows(ref)[B_BISO].value
    assert ref.untie(B_BISO) == [B_BISO]
    row = _rows(ref)[B_BISO]
    assert row.tie is None and row.refinable and not row.vary
    assert row.value == value
    ref.remove_variable("thD")          # nothing follows it any more


def test_checkout_restores_a_formula_and_the_node_renders_a_call_that_runs(
        ref, tmp_path):
    path = tmp_path / "formula.jsonl"
    ref = rx.Refinement(*perturbed_models(), history=str(path))
    ref.fit(synthesize_at(300.0, 3), plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=5)]))
    before = ref.history.head
    ref.add_variable("thD", 900.0, vary=True, min=100.0, max=3000.0)
    ref.tie(B_BISO, expression=debye_text(300.0))
    declared = ref.history.head
    n_free = len(ref._working_table().free_paths)

    ref.checkout(before)
    assert _rows(ref)[B_BISO].tie is None
    ref.checkout(declared)
    assert _rows(ref)[B_BISO].tie.expression == debye_text(300.0)
    assert len(ref._working_table().free_paths) == n_free

    state = rx.RefinementTree.load(path)[declared].state
    assert state.ties[B_BISO].expression == debye_text(300.0)
    call = ref.history[declared].action.api_call()
    assert call == f"ref.tie({B_BISO!r}, expression={debye_text(300.0)!r})"
    replay = rx.Refinement(*perturbed_models())
    replay.add_variable("thD", 900.0, vary=True, min=100.0, max=3000.0)
    eval(compile(call, "<api_call>", "eval"), {"ref": replay})
    assert _rows(replay)[B_BISO].value == _rows(ref)[B_BISO].value


def test_a_linear_tie_stored_before_the_field_opens_as_a_linear_tie():
    """Ruling 3: no stored tie moves.  A 0.60 tie has no ``expression`` key."""
    spec = rx.TieSpec.model_validate(
        {"terms": [["vars.B", 2.0]], "const": 0.1, "user": True})
    assert spec.expression is None
    assert spec.sources == ["vars.B"] and spec.describe() == "0.1 + 2·vars.B"


# ------------------------------------------------------------------ a formula against a linear tie
def test_a_linear_formula_meets_the_matrix_tie_to_rounding(ref):
    """The two routes give one answer where both apply, and stay two routes.

    ``2 * B_La + 0.1`` as text is a derived row; as ``scale=2, offset=0.1`` it
    is a row of C.  The values agree to rounding at every value of the
    variable, and the residual's Jacobian column on the variable agrees to
    the numpy column's own precision.
    """
    from rietx.optimize.least_squares import _jacobian_for

    pattern = synthesize_at(300.0, 5)
    arms = []
    for formula in (True, False):
        r = rx.Refinement(*perturbed_models())
        r.add_variable("B_La", 0.3, vary=True, min=0.0, max=5.0)
        if formula:
            r.tie(B_BISO, expression="2 * B_La + 0.1")
        else:
            r.tie(B_BISO, "vars.B_La", scale=2.0, offset=0.1)
        arms.append(r)
    rng = np.random.default_rng(11)
    for value in rng.uniform(0.0, 2.0, 5):
        got = []
        for r in arms:
            r.set_values({"vars.B_La": float(value)})
            got.append(_rows(r)[B_BISO].value)
        assert got[0] == pytest.approx(got[1], rel=4e-16, abs=0.0)
    cols = []
    for r in arms:
        table = r._working_table()
        table.set_vary(["*"], False)
        assert table.set_vary(["vars.B_La"], True) == ["vars.B_La"]
        model = compile_model(r.structure, r.instrument, pattern, mode="rietveld",
                              moving_paths=set(table.moving_paths))
        jac = _jacobian_for(model, table, "numpy")(table.x0())
        cols.append(np.asarray(jac.toarray() if hasattr(jac, "toarray") else jac)[:, 0])
    scale = np.max(np.abs(cols[1]))
    assert np.max(np.abs(cols[0] - cols[1])) <= 1e-10 * scale


# ------------------------------------------------------------------ the acceptance fit
def test_a_debye_formula_recovers_its_temperature_within_two_esd():
    """WP-2118's acceptance: a nonlinear formula's variable, recovered."""
    ref = rx.Refinement(*perturbed_models())
    ref.add_variable("thD", 800.0, vary=False, min=200.0, max=3000.0)
    ref.tie(B_BISO, expression=debye_text(300.0))
    result = ref.fit(synthesize_at(300.0, 7), plan=PLAN)
    _plot(result, "debye")
    assert result.status == "converged"
    rows = {p.path: p for p in result.parameters}
    thd = rows["vars.thD"]
    assert thd.stderr is not None and thd.stderr > 0.0
    assert abs(thd.value - TRUE_THD) < 2.0 * thd.stderr, (thd.value, thd.stderr)
    # the target is reported, at the formula's value, with an esd of its own
    target = rows[B_BISO]
    assert target.value == pytest.approx(debye_b(thd.value, 300.0), rel=1e-12)
    assert target.stderr is not None and target.stderr > 0.0
    assert math.isfinite(result.statistics.rwp) and result.statistics.gof < 2.0


def test_a_series_redeclares_the_formula_at_each_pattern_s_temperature():
    """Task 5: the ``constrain`` hook re-declares a formula as it does a tie.

    Each pattern's temperature enters as a number in the text, because a
    formula reads named variables and numbers; a variable would be carried
    pattern to pattern under ``carry=["*"]``.
    """
    temps = (300.0, 600.0)
    patterns = [synthesize_at(t, 20 + k) for k, t in enumerate(temps)]

    def constrain(index, r):
        r.add_variable("thD", 800.0, min=200.0, max=3000.0)
        r.tie(B_BISO, expression=debye_text(temps[index]))

    runner = rx.SequentialRefinement(*perturbed_models())
    series = runner.fit(patterns, plan=PLAN, constrain=constrain)
    assert len(series) == 2
    for k, (entry, t) in enumerate(zip(series.entries, temps, strict=True)):
        values = {p.path: p for p in entry.parameters}
        thd = values["vars.thD"]
        assert abs(thd.value - TRUE_THD) < 2.0 * thd.stderr, (t, thd.value, thd.stderr)
        assert values[B_BISO].value == pytest.approx(debye_b(thd.value, t), rel=1e-12)
        _plot(runner.results_[k], f"series_{int(t)}K")


def test_the_topas_writer_refuses_a_formula_rather_than_writing_zero(ref):
    """A formula tie has no terms, so read as a linear one it is the constant 0."""
    from rietx.io.projects.topas import from_structure

    ref.add_variable("thD", 900.0, min=100.0, max=3000.0)
    ref.tie(B_BISO, expression=debye_text(300.0))
    with pytest.raises(ValueError, match=f"{B_BISO} follows the formula"):
        from_structure(ref.structure, free=ref)
