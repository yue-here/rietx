"""A joint fit has the verbs a single fit has (WP-2103).

``MultiHistogramRefinement`` gains ``hold``/``unhold``, ``tie``/``tie_equal``/
``untie`` (linear and ``expression=``), ``add_variable``, ``set_values`` and
``refit``.  Rows are named as ``parameters()`` prints them: a shared row bare,
a row per pattern ``hist.<h>.``-scoped.  Each test runs the cheap two-pattern
LaB6 pair of ``test_multi_histogram`` (about 0.1-0.3 s a fit, macOS arm64).
"""

from __future__ import annotations

import pytest

import rietx as rx
from rietx import MultiHistogramRefinement, RefinementResult
from rietx.params.multi import SharingMap
from rietx.schemas.parametric import CoordinateTable, ParametricEquation
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_multi_histogram import _cheap_joint_plan, perturbed_inputs, synthesize


@pytest.fixture(scope="module")
def pair():
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


def _plan() -> RefinementPlan:
    return RefinementPlan(stages=[*_cheap_joint_plan().stages,
                                  Stage("adp", ["phases.*.atoms.*.biso"], max_iter=8)])


def _ref(**kw) -> MultiHistogramRefinement:
    structure, instruments = perturbed_inputs()
    return MultiHistogramRefinement(structure, instruments, **kw)


def _rows(ref) -> dict:
    return {r.path: r for r in ref.parameters()}


# --- hold / unhold ----------------------------------------------------------

def test_a_held_row_stays_put_and_the_blocked_glob_is_said(pair):
    """A plan that frees ``instrument.zero_shift`` leaves pattern 0's at its
    held value, records the block on the stage, and says it once."""
    ref = _ref()
    assert ref.hold("hist.0.instrument.zero_shift") == ["hist.0.instrument.zero_shift"]
    assert ref.hold("hist.0.instrument.zero_shift") == []
    result = ref.fit(pair, plan=_plan(), telemetry=False)
    assert ref.fitted_instruments[0].zero_shift.value == 0.0
    assert ref.fitted_instruments[1].zero_shift.value != 0.0
    cell = next(s for s in result.stages if s.name == "cell")
    assert cell.blocked_by_hold == ["hist.0.instrument.zero_shift"]
    (said,) = [d for d in result.diagnostics if d.code == "HOLD_BLOCKED_PLAN"]
    assert said.where == ["hist.0.instrument.zero_shift"]
    assert _rows(ref)["hist.0.instrument.zero_shift"].held is True
    assert ref.unhold("hist.0.*") == ["hist.0.instrument.zero_shift"]
    assert _rows(ref)["hist.0.instrument.zero_shift"].held is False


def test_a_bare_hold_holds_every_pattern_and_refusals_name_their_fix():
    ref = _ref()
    assert ref.hold("instrument.zero_shift") == [
        "hist.0.instrument.zero_shift", "hist.1.instrument.zero_shift"]
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.hold("instrument.zero_shfit")
    with pytest.raises(ValueError, match="not held by this refinement"):
        ref.unhold("phases.0.cell.a")


# --- tie / tie_equal / untie --------------------------------------------------

def test_tie_equal_ties_each_pattern_to_its_own_source(pair):
    """WP-1325's WO₃ protocol on LaB6: each site's B a row per pattern, the
    sites tied together in each pattern, so one refined B per pattern."""
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    assert ref.tie_equal("phases.0.atoms.*.biso") == ["phases.0.atoms.1.biso"]
    rows = _rows(ref)
    for h in (0, 1):
        tie = rows[f"hist.{h}.phases.0.atoms.1.biso"].tie
        assert tie.user is True
        assert tie.terms == [(f"hist.{h}.phases.0.atoms.0.biso", 1.0)]
    result = ref.fit(pair, plan=_plan(), telemetry=False)
    assert result.status == "converged"
    got = {p.path: p.value for p in result.parameters}
    for h in (0, 1):
        assert got[f"hist.{h}.phases.0.atoms.1.biso"] == got[f"hist.{h}.phases.0.atoms.0.biso"]
    assert got["hist.0.phases.0.atoms.0.biso"] != got["hist.1.phases.0.atoms.0.biso"]
    assert ref.untie("phases.0.atoms.*") == ["phases.0.atoms.1.biso"]
    assert _rows(ref)["hist.0.phases.0.atoms.1.biso"].tie is None


@pytest.mark.parametrize(("target", "source", "fragment"), [
    ("phases.0.atoms.1.biso", "hist.1.phases.0.atoms.0.biso", "one pattern's row"),
    ("hist.0.phases.0.atoms.1.biso", "hist.1.phases.0.atoms.0.biso", "different patterns"),
    ("phases.0.cell.a", "phases.0.atoms.0.biso", "row per pattern too"),
    ("phases.0.cell.b", "phases.0.cell.a", "symmetry"),
    ("hist.0.phases.0.cell.a", "phases.0.atoms.0.biso", "name it bare"),
])
def test_a_tie_across_patterns_is_refused_naming_sharing(target, source, fragment):
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.0.biso",
                                                 "phases.0.atoms.1.biso"]))
    with pytest.raises(ValueError, match=fragment):
        ref.tie(target, source)
    assert ref.mtable.user_ties == {}


def test_a_variable_carries_a_tied_group_and_a_glob_on_the_group_frees_it(pair):
    ref = _ref()
    assert ref.add_variable("B", 0.5, min=0.0) == "vars.B"
    ref.tie_equal("phases.0.atoms.*.biso", source="vars.B")
    result = ref.fit(pair, plan=_plan(), telemetry=False)
    assert "vars.B" in result.stages[-1].freed
    got = {p.path: p for p in result.parameters}
    assert got["vars.B"].stderr > 0
    assert got["phases.0.atoms.0.biso"].value == got["vars.B"].value
    with pytest.raises(ValueError, match="already exists"):
        ref.add_variable("B", 1.0)


def test_a_fixed_variable_stays_where_it_was_put(pair):
    ref = _ref()
    ref.add_variable("B", 0.45, vary=False, min=0.0)
    ref.tie_equal("phases.0.atoms.*.biso", source="vars.B")
    result = ref.fit(pair, plan=_plan(), telemetry=False)
    assert "vars.B" not in result.stages[-1].freed
    assert _rows(ref)["vars.B"].value == 0.45


def test_an_expression_tie_runs_once_per_pattern_and_keeps_the_refusals(pair):
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    ref.add_variable("b", 0.4, min=0.0)
    assert ref.tie("phases.0.atoms.1.biso", expression="b + 0.1") == "phases.0.atoms.1.biso"
    rows = _rows(ref)
    for h in (0, 1):
        assert rows[f"hist.{h}.phases.0.atoms.1.biso"].value == pytest.approx(0.5)
        assert rows[f"hist.{h}.phases.0.atoms.1.biso"].tie.expression == "b + 0.1"
    result = ref.fit(pair, plan=_plan(), telemetry=False)
    got = {p.path: p.value for p in result.parameters}
    assert got["hist.1.phases.0.atoms.1.biso"] == pytest.approx(got["vars.b"] + 0.1)
    with pytest.raises(ValueError, match="not a declared variable"):
        ref.tie("phases.0.atoms.0.biso", expression="nope + 1")
    with pytest.raises(ValueError, match="reads no variable"):
        ref.tie("phases.0.atoms.0.biso", expression="0.3")
    with pytest.raises(ValueError, match="cannot take back"):
        ref.untie("phases.0.atoms.1.biso")
    with pytest.raises(TypeError, match="not both"):
        ref.tie("phases.0.atoms.0.biso", "vars.b", expression="b")


# --- set_values -------------------------------------------------------------

def test_set_values_writes_by_row_name_and_refuses_before_any_write():
    ref = _ref()
    ref.set_values({"phases.0.cell.a": 4.157, "hist.1.instrument.zero_shift": 0.002})
    rows = _rows(ref)
    assert rows["phases.0.cell.a"].value == 4.157
    assert rows["phases.0.cell.b"].value == 4.157          # the dependent follows
    assert rows["hist.1.instrument.zero_shift"].value == 0.002
    assert ref.mtable.structures[1].phases[0].cell.a.value == 4.157
    for values, fragment in (({"instrument.zero_shift": 0.0}, "name one"),
                             ({"hist.0.phases.0.cell.a": 4.0}, "name it bare"),
                             ({"phases.0.cell.b": 4.0}, "affine tie"),
                             ({"phases.0.cell.a": 4.1, "nope": 1.0}, "unknown")):
        with pytest.raises(ValueError, match=fragment):
            ref.set_values(values)
        assert _rows(ref)["phases.0.cell.a"].value == 4.157


# --- refit ------------------------------------------------------------------

def _max_move(before: RefinementResult, after: RefinementResult) -> float:
    esd = {p.path: p.stderr for p in before.parameters}
    assert [p.path for p in after.parameters] == list(esd)
    return max(abs(q.value - p.value) / esd[p.path]
               for p, q in zip(before.parameters, after.parameters, strict=True)
               if esd[p.path])


def test_a_converged_fit_restarted_stops_in_one_stage_and_moves_nothing(pair):
    """The WP's bar: one stage, nothing moved by more than 0.01 esd, in
    process and from a result saved to JSON and read into a new object.
    Measured (macOS arm64): one iteration, 0.0 esd both ways."""
    ref = _ref()
    first = ref.fit(pair, plan=_plan(), telemetry=False)
    again = ref.refit(pair, telemetry=False)
    assert [s.name for s in again.stages] == ["restart"]
    assert again.stages[0].window_area_tol == first.stages[-1].window_area_tol
    assert _max_move(first, again) < 0.01
    saved = RefinementResult.model_validate_json(first.model_dump_json())
    fresh = _ref()
    restarted = fresh.refit(pair, result=saved, telemetry=False)
    assert [s.name for s in restarted.stages] == ["restart"]
    assert _max_move(first, restarted) < 0.01


def test_a_restart_from_moved_values_comes_back(pair):
    """The positive arm: a restart that cannot move would pass the bar too."""
    ref = _ref()
    first = ref.fit(pair, plan=_cheap_joint_plan(), telemetry=False)
    a = first.parameter("phases.0.cell.a")
    ref.set_values({"phases.0.cell.a": a.value + 50 * a.stderr})
    again = ref.refit(pair, telemetry=False)
    assert again.stages[0].n_iterations > 1
    assert abs(again.parameter("phases.0.cell.a").value - a.value) < 0.01 * a.stderr


def test_refit_refuses_a_plan_and_a_missing_start(pair):
    with pytest.raises(ValueError, match="fit\\(\\) first"):
        _ref().refit(pair)
    with pytest.raises(TypeError, match="call fit"):
        _ref().refit(pair, plan="mccusker_default")


# --- the form test meets a tie onto a variable (WP-1964's inherited case) ----

@pytest.mark.xdist_group("parametric-expression")
def test_a_tie_onto_an_expression_variable_drops_that_pattern_from_the_form_test():
    """A formula's form test leaves out a pattern where a variable reaches a
    row no formula writes (``usable`` in ``multi._parametric_form_tests``).
    Tying pattern 4's background onto ``vars.c0`` makes that predicate False
    there.  Measured (macOS arm64): 5 patterns and 3 dof untied, 4 and 2 tied."""
    from tests.test_parametric_expression import _ramp
    from tests.test_sequential import A0, RAMP, _start_models

    temps = [300.0, 525.0, 750.0, 975.0, 1200.0]
    patterns = _ramp([A0 * (1.0 + RAMP * (t - 300.0) / 100.0) for t in temps], seed=40)
    forms = []
    for tie in (False, True):
        structure, ins = _start_models()
        start = structure.phases[0].cell.a.value
        ref = MultiHistogramRefinement(
            structure, [ins] * len(temps),
            sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
            coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
            variables={"c0": rx.Parameter(value=start, vary=True),
                       "c1": rx.Parameter(value=0.0, vary=True)},
            parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                           basis="expression",
                                           expression="c0 + c1*(T - 750)/450")])
        if tie:
            bg = _rows(ref)["hist.4.instrument.background.c0"].value
            ref.tie("hist.4.instrument.background.c0", "vars.c0", offset=bg - start)
        result = ref.fit(patterns, plan="mccusker_default", telemetry=False)
        assert result.status == "converged"
        (form,) = result.parametric_form
        forms.append((form.n_patterns, form.tied.dof))
    assert forms == [(5, 3), (4, 2)]


# --- review findings (2026-11-17) ---------------------------------------------

def test_a_tie_on_a_size_row_is_written_in_each_patterns_units():
    """A shared size coefficient is stored in each pattern's units (WP-1131):
    the tie must be too, or the two patterns describe two crystallites."""
    ref = _ref()
    mt = ref.mtable
    scales = [mt.value_scales[h].get("phases.0.lor_size", 1.0) for h in (0, 1)]
    assert scales[0] == 1.0 and scales[1] != 1.0       # two wavelengths
    ref.add_variable("L", 0.05, min=0.0)
    ref.tie("phases.0.lor_size", "vars.L", offset=0.01)
    for h in (0, 1):
        assert mt._entry(h, "phases.0.lor_size").value == pytest.approx(0.06 * scales[h])
    assert _rows(ref)["phases.0.lor_size"].value == pytest.approx(0.06)
    with pytest.raises(ValueError, match="each pattern's own units"):
        ref.tie("phases.0.gauss_size", expression="L * 2")


def test_unhold_takes_back_a_bare_hold_of_rows_per_pattern():
    ref = _ref()
    ref.hold("instrument.zero_shift")
    assert ref.unhold("instrument.zero_shift") == [
        "hist.0.instrument.zero_shift", "hist.1.instrument.zero_shift"]
    assert ref.mtable.user_holds == set()


def test_a_refused_formula_leaves_no_table_holding_it():
    """``add_expression`` refuses a follower reading the target beside another
    source; asked in pattern 1 only, pattern 0 must not keep the formula."""
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    ref.add_variable("B", 0.5, min=0.0)
    ref.add_variable("b", 0.4, min=0.0)
    ref.tie("hist.1.phases.0.atoms.0.biso",
            [("hist.1.phases.0.atoms.1.biso", 1.0), ("vars.B", 1.0)], offset=-0.5)
    with pytest.raises(ValueError):
        ref.tie("phases.0.atoms.1.biso", expression="b + 0.1")
    entry = ref.mtable._entry(0, "phases.0.atoms.1.biso")
    assert not entry.locked and entry.tie is None
    assert list(ref.mtable.user_ties) == ["hist.1.phases.0.atoms.0.biso"]


# --- second review findings (2026-11-17) -------------------------------------

@pytest.mark.parametrize(("source", "expression", "value"), [
    ("vars.B", None, 0.5),
    (None, "B + 0.1", 0.6),
])
def test_a_held_row_tied_onto_a_variable_stays_put_and_the_block_is_said(
        pair, source, expression, value):
    """The adp glob reaches the held row; the variable under it must stay
    fixed, and the block is recorded as any held row's is."""
    ref = _ref()
    ref.add_variable("B", 0.5, min=0.0)
    if expression is None:
        ref.tie("phases.0.atoms.1.biso", source)
        ref.hold("phases.0.atoms.1.biso")
    else:
        ref.hold("phases.0.atoms.1.biso")
        ref.tie("phases.0.atoms.1.biso", expression=expression)
    result = ref.fit(pair, plan=_plan(), telemetry=False)
    adp = next(s for s in result.stages if s.name == "adp")
    assert not any("vars.B" in s.freed for s in result.stages)
    assert adp.blocked_by_hold == ["phases.0.atoms.1.biso"]
    (said,) = [d for d in result.diagnostics if d.code == "HOLD_BLOCKED_PLAN"]
    assert "phases.0.atoms.1.biso" in said.where
    row = _rows(ref)["phases.0.atoms.1.biso"]
    assert row.held is True
    assert row.value == pytest.approx(value, abs=1e-12)


def test_a_held_tied_row_follows_its_variable_freed_another_way(pair):
    """The documented limit: a glob naming the variable frees it, and the
    held row follows; no block is claimed for a row that moved."""
    ref = _ref()
    ref.add_variable("B", 0.5, min=0.0)
    ref.tie("phases.0.atoms.1.biso", "vars.B")
    ref.hold("phases.0.atoms.1.biso")
    plan = RefinementPlan(stages=[*_cheap_joint_plan().stages,
                                  Stage("adp", ["phases.*.atoms.*.biso", "vars.B"],
                                        max_iter=8)])
    result = ref.fit(pair, plan=plan, telemetry=False)
    adp = next(s for s in result.stages if s.name == "adp")
    assert "vars.B" in adp.freed
    assert adp.blocked_by_hold == []


def test_a_formula_on_a_tied_rows_source_is_refused_naming_the_follower():
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    ref.add_variable("b", 0.4, min=0.0)
    ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.biso")
    with pytest.raises(ValueError, match="'phases.0.atoms.1.biso' follows it"):
        ref.tie("phases.0.atoms.0.biso", expression="b + 0.1")
    assert list(ref.mtable.user_ties) == ["phases.0.atoms.1.biso"]
    for h in (0, 1):
        assert not ref.mtable._entry(h, "phases.0.atoms.0.biso").locked
    assert ref.untie("phases.0.atoms.1.biso") == ["phases.0.atoms.1.biso"]


def test_untie_of_several_names_releases_all_or_none():
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    ref.add_variable("B", 0.5, min=0.0)
    ref.add_variable("C", 0.5, min=0.0)
    ref.tie("phases.0.atoms.0.biso", "vars.B")
    ref.tie("phases.0.atoms.1.biso", "vars.C")
    # a row the tables fixed since: untie cannot release it
    ref.mtable._entry(1, "phases.0.atoms.1.biso").locked = True
    with pytest.raises(ValueError, match="nothing was released"):
        ref.untie(["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"])
    assert list(ref.mtable.user_ties) == ["phases.0.atoms.0.biso",
                                          "phases.0.atoms.1.biso"]
    assert ref.mtable._entry(0, "phases.0.atoms.0.biso").tie is not None


def test_untie_takes_back_a_tie_by_either_spelling_as_unhold_does():
    """A bare tie released in one pattern leaves the other's declared; a tie
    declared per pattern is released by its bare path."""
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.biso")
    assert ref.untie("hist.0.phases.0.atoms.1.biso") == ["hist.0.phases.0.atoms.1.biso"]
    rows = _rows(ref)
    assert rows["hist.0.phases.0.atoms.1.biso"].tie is None
    assert rows["hist.1.phases.0.atoms.1.biso"].tie.user is True
    assert list(ref.mtable.user_ties) == ["hist.1.phases.0.atoms.1.biso"]
    ref.tie("hist.0.phases.0.atoms.1.biso", "phases.0.atoms.0.biso")
    assert ref.untie("phases.0.atoms.1.biso") == [
        "hist.1.phases.0.atoms.1.biso", "hist.0.phases.0.atoms.1.biso"]
    assert ref.mtable.user_ties == {}
    with pytest.raises(ValueError, match="not tied by this refinement"):
        ref.untie("hist.0.phases.0.atoms.1.biso")


def test_a_scoped_name_of_a_bare_tie_gets_the_tie_reasons():
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    ref.add_variable("b", 0.4, min=0.0)
    ref.tie("phases.0.atoms.1.biso", expression="b + 0.1")
    with pytest.raises(ValueError, match=r"follows b \+ 0.1 \(a user tie\); set the variables"):
        ref.set_values({"hist.0.phases.0.atoms.1.biso": 0.9})
    with pytest.raises(ValueError, match=r"already follows b \+ 0.1 \(a user tie\)"):
        ref.tie("hist.0.phases.0.atoms.1.biso", "phases.0.atoms.0.biso")


def test_a_row_tied_to_itself_in_two_spellings_is_refused_as_a_self_tie():
    ref = _ref(sharing=SharingMap(per_histogram=["phases.0.atoms.*.biso"]))
    with pytest.raises(ValueError, match="cannot be tied to itself"):
        ref.tie("hist.0.phases.0.atoms.0.biso", "phases.0.atoms.0.biso")
    assert ref.mtable.user_ties == {}


def test_tie_equal_names_the_pattern_spelling_for_a_bad_scope():
    with pytest.raises(ValueError, match=r"hist\.<h>\."):
        _ref().tie_equal("hist.x.phases.0.atoms.*.biso")


def test_a_held_coefficient_is_not_named_as_one_no_stage_freed(pair):
    """WP-2101's follow-up, owed once the joint fit had ``hold``: as in the single
    fit, ``VARIABLE_NOT_FREED`` leaves out a coefficient the caller holds (read off
    the tables, ``MultiParameterTable.held_by``) and still names one nobody freed
    or held.  The cheap plan reaches no Biso, so neither line's coefficients are
    freed; ``b``'s are held and ``c``'s are not."""
    def ref():
        return _ref(coordinates=CoordinateTable(columns={"T": [300.0, 600.0]},
                                                units={"T": "K"}),
                    parametric=[ParametricEquation(
                        name=n, target=f"phases.0.atoms.{j}.biso",
                        basis="polynomial", terms=[[], ["T"]]) for j, n in enumerate("bc")])

    def idle(held):
        r = ref()
        assert r.hold(held)
        fit = r.fit(pair, plan=_cheap_joint_plan(), telemetry=False)
        return {tuple(d.where): d for d in fit.diagnostics
                if d.code == "VARIABLE_NOT_FREED"}

    whole = idle("vars.b_*")
    assert list(whole) == [("vars.c_0", "vars.c_1")]
    part = idle("vars.b_0")
    assert list(part) == [("vars.b_1",), ("vars.c_0", "vars.c_1")]
    assert part[("vars.b_1",)].message == (
        "Parametric equation 'b' sets phases.0.atoms.0.biso, and no stage freed "
        "vars.b_1, and the caller holds the other. It kept the starting value (0), "
        "so the equation is the one declared and the data did not measure it.")
