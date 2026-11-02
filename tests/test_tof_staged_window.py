"""A staged Lorentzian window tolerance on a time-of-flight bank.

The rung beside ``RefinementPlan.stage_ftols``: a plan loosens the one window
component that is expensive — the Lorentzian tail of the type-3 profile, ~η/(π·tol)
FWHM long — in every declared stage but the last, and the last and the closing
stage compile at ``forward_tof.TOF_WINDOW_AREA_TOL``.  What is pinned here is the
rule, that the Gaussian branch and every other window component cannot move,
that the closing stage never inherits a coarse override, and that a fit and its
history say which stages were coarse.  The measurement behind the number
(``INTERMEDIATE_LORENTZ_WINDOW_TOL``'s comment) is not repeated: it takes an hour.

**Every fixture is synthetic**, the bank of ``test_tof_refine`` on a shorter
grid so a pseudo-Voigt fit runs in seconds.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.special import erfc

import rietx as rx
from rietx.model.forward import window_fwhm_mult
from rietx.model.forward_tof import (
    TOF_WINDOW_AREA_TOL,
    compile_tof_model,
    window_fwhm_mult_split,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.pattern import PatternData
from rietx.schemas.plan import INTERMEDIATE_LORENTZ_WINDOW_TOL, PlanSpec, StageSpec
from tests.test_tof_refine import A_GEN, TZERO_GEN, bank, silicon

#: 15000-30000 µs in 10 µs channels: d = 1.25-2.5 Å on the 12000 µs/Å bank, a
#: dozen reflections, so the 1e-4 windows cost a few ms an evaluation.
GRID = np.arange(15000.0, 30000.0 + 5.0, 10.0)
GAM1 = 5.0


def _blank() -> PatternData:
    return PatternData(tof=GRID.tolist(), intensity=[1.0] * len(GRID))


def _curve(structure, instrument, **kw) -> tuple[np.ndarray, object]:
    model = compile_tof_model(structure, instrument, _blank(), **kw)
    table = ParameterTable(structure, instrument)
    return np.asarray(model.evaluate(table.decode(table.x0()))), model


def _plan() -> rx.RefinementPlan:
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("calibration", ["instrument.source.tzero"]),
        rx.Stage("cell", ["phases.*.cell.a"]),
        rx.Stage("profile", ["instrument.source.profile_tof.alpha1",
                             "instrument.source.profile_tof.sig1",
                             "instrument.source.profile_tof.gam1"]),
        rx.Stage("displacement", ["phases.*.atoms.*.biso"]),
    ])


# ----------------------------------------------------------------------
# 1. the schedule
# ----------------------------------------------------------------------
def test_the_last_stage_runs_at_the_answer_tolerance():
    """Five declared stages and the closing one: ``stage_ftols``' endpoints,
    the last declared stage and the closing stage, both take ``None``."""
    plan = _plan()
    assert plan.intermediate_lorentz_window_tol == INTERMEDIATE_LORENTZ_WINDOW_TOL
    assert len(plan.run_stages()) == len(plan.stages) + 1
    assert plan.stage_lorentz_window_tols() == (
        [INTERMEDIATE_LORENTZ_WINDOW_TOL] * 4 + [None, None])
    assert len(plan.stage_lorentz_window_tols()) == len(plan.stage_ftols())
    # without a closing stage the rule is the declared stages' alone
    plan.closing_window_tol = None
    assert plan.stage_lorentz_window_tols() == [INTERMEDIATE_LORENTZ_WINDOW_TOL] * 4 + [None]


def test_a_stage_override_wins_and_none_is_the_way_back():
    plan = _plan()
    plan.stages[1].lorentz_window_tol = 1e-3
    plan.stages[4].lorentz_window_tol = 2e-4
    assert plan.stage_lorentz_window_tols() == [1e-2, 1e-3, 1e-2, 1e-2, 2e-4, None]
    plan = _plan()
    plan.intermediate_lorentz_window_tol = None
    assert plan.stage_lorentz_window_tols() == [None] * 6


def test_a_one_stage_plan_is_all_endpoint():
    plan = rx.RefinementPlan(stages=[rx.Stage("only", ["phases.*.scale"])])
    assert plan.stage_lorentz_window_tols() == [None, None]
    plan.closing_window_tol = None
    assert plan.stage_lorentz_window_tols() == [None]


def test_the_closing_stage_does_not_copy_a_coarse_override():
    """The closing stage takes the last declared stage's discrete settings, but
    never its Lorentzian window tolerance: it exists to compute the answer at
    tight windows, so a coarse last stage cannot make the answer coarse."""
    plan = _plan()
    plan.stages[-1].lorentz_window_tol = 1e-2
    plan.stages[-1].window_slack_deg = 2.5
    closing = plan.closing_stage()
    assert closing is not None
    assert closing.window_slack_deg == 2.5, "the other settings are still copied"
    assert closing.lorentz_window_tol is None
    assert plan.stage_lorentz_window_tols()[-2:] == [1e-2, None]


def test_both_mirrors_carry_the_schedule():
    plan = _plan()
    plan.intermediate_lorentz_window_tol = 3e-3
    plan.stages[0].lorentz_window_tol = 5e-3
    spec = PlanSpec.from_plan(plan)
    assert spec.intermediate_lorentz_window_tol == 3e-3
    assert spec.stages[0].lorentz_window_tol == 5e-3
    back = PlanSpec.model_validate_json(spec.model_dump_json()).to_plan()
    assert back.stage_lorentz_window_tols() == plan.stage_lorentz_window_tols()
    assert PlanSpec().intermediate_lorentz_window_tol == INTERMEDIATE_LORENTZ_WINDOW_TOL
    with pytest.raises(ValueError):
        StageSpec(name="x", lorentz_window_tol=0.7)


# ----------------------------------------------------------------------
# 2. the split rule
# ----------------------------------------------------------------------
@pytest.mark.parametrize("tol_l", [1e-4, 1e-3, 1e-2])
def test_the_split_holds_each_component_to_its_own_bar(tol_l):
    """Each tail mass beyond ±k·Γ is at most its own tolerance, and the
    binding one is met with equality — a root, not merely a bound."""
    tol_g = 2.0 * TOF_WINDOW_AREA_TOL
    eta = np.array([0.0, 1e-3, 0.05, 0.27, 0.6, 1.0])
    k = window_fwhm_mult_split(eta, tol_g, tol_l)
    gauss = (1.0 - eta) * erfc(2.0 * math.sqrt(math.log(2.0)) * k)
    lor = eta * (2.0 / math.pi) * np.arctan(1.0 / (2.0 * np.maximum(k, 1e-300)))
    assert np.all(gauss <= tol_g * (1 + 1e-9))
    assert np.all(lor <= tol_l * (1 + 1e-9))
    binding = np.maximum(gauss / tol_g, lor / tol_l)
    assert np.allclose(binding[eta > tol_l], 1.0, rtol=1e-9)


def test_the_split_is_the_one_rule_on_a_pure_gaussian():
    assert np.isclose(window_fwhm_mult_split(np.array([0.0]), 2e-4, 2e-2)[0],
                      window_fwhm_mult(np.array([0.0]), tol=2e-4)[0], rtol=1e-12)


# ----------------------------------------------------------------------
# 3. what the compiler does with it
# ----------------------------------------------------------------------
def test_a_gaussian_bank_compiles_the_same_windows_bit_for_bit():
    """Every real bank obtainable declares γ = 0: the schedule must not reach it."""
    y0, m0 = _curve(silicon(), bank())
    y1, m1 = _curve(silicon(), bank(), lorentz_window_tol=1e-2)
    assert m0.profile_kind == m1.profile_kind == "gaussian"
    assert np.array_equal(m0.flat_windows[0][0], m1.flat_windows[0][0])
    assert np.array_equal(y0, y1)
    assert m0.lorentz_window_tol is None and m1.lorentz_window_tol is None


def test_a_pseudovoigt_bank_is_coarse_in_its_lorentzian_tail_only():
    s, ins = silicon(), bank(gam1=GAM1)
    fine, m_fine = _curve(s, ins)
    coarse, m_coarse = _curve(s, ins, lorentz_window_tol=1e-2)
    ref, _ = _curve(s, ins, lorentz_window_tol=1e-9)
    assert m_fine.lorentz_window_tol == TOF_WINDOW_AREA_TOL
    assert m_coarse.lorentz_window_tol == 1e-2
    # fewer points, never more, per reflection
    w_fine = np.diff(m_fine.phases[0].win[0], axis=1).ravel()
    w_coarse = np.diff(m_coarse.phases[0].win[0], axis=1).ravel()
    assert np.all(w_coarse <= w_fine) and w_coarse.sum() < 0.5 * w_fine.sum()
    # the discard it states, and no more: at most 2·(1e-4 + 1e-2) of each
    # peak's area per side, so at most ~4 % of the Bragg total
    lost = (ref.sum() - coarse.sum()) / ref.sum()
    assert 0.0 < lost < 4.0 * (TOF_WINDOW_AREA_TOL + 1e-2)
    assert abs(ref.sum() - fine.sum()) / ref.sum() < 4.0 * TOF_WINDOW_AREA_TOL


def test_a_tolerance_outside_its_range_is_refused_by_name():
    with pytest.raises(ValueError, match="lorentz_window_tol"):
        compile_tof_model(silicon(), bank(gam1=GAM1), _blank(), lorentz_window_tol=0.5)


# ----------------------------------------------------------------------
# 4. through the engine
# ----------------------------------------------------------------------
def _data(seed: int = 20260929) -> PatternData:
    ins = bank(gam1=GAM1)
    ins.background.coefficients[0].value = 40.0
    s = silicon()
    s.phases[0].scale.value = 12.0
    y, _ = _curve(s, ins, lorentz_window_tol=1e-9)
    noisy = np.random.default_rng(seed).poisson(np.maximum(y, 0.0)).astype(float)
    return PatternData(tof=GRID.tolist(), intensity=noisy.tolist())


def _fit(intermediate, *, history: bool = False):
    s = silicon(a=A_GEN * 1.002)
    s.phases[0].scale.value = 6.0
    ins = bank(tzero=TZERO_GEN - 10.0, gam1=0.7 * GAM1)
    ins.background.coefficients[0].value = 40.0
    plan = _plan()
    plan.intermediate_lorentz_window_tol = intermediate
    ref = rx.Refinement(s, ins, history=history)
    return ref.fit(_data(), plan=plan), ref


@pytest.fixture(scope="module")
def staged_pair():
    """The staged fit, recorded, and the unscheduled one; the staged fit's
    ``Refinement`` rides beside them for the history tests."""
    staged, ref = _fit(INTERMEDIATE_LORENTZ_WINDOW_TOL, history=True)
    flat, _ = _fit(None)
    return staged, flat, ref


def test_a_fit_records_which_stages_were_coarse(staged_pair):
    """Four coarse declared stages, then the last declared stage and the
    closing stage at the answer tolerance, read off the models they ran on."""
    staged, flat, _ = staged_pair
    assert [st.name for st in staged.stages][-1] == "closing"
    assert [st.lorentz_window_tol for st in staged.stages] == [1e-2] * 4 + [1e-4, 1e-4]
    assert [st.lorentz_window_tol for st in flat.stages] == [1e-4] * 6


def test_a_coarse_node_records_its_input_and_a_cherry_pick_compiles_it(staged_pair):
    """``NodeAction.lorentz_window_tol`` is the input the schedule handed each
    stage, ``None`` at the answer tolerance, so ``api_call`` names it on a
    coarse node only and a cherry-pick of that node compiles its windows."""
    _, _, ref = staged_pair
    tree = ref.history
    nodes = [n for n in tree.lineage(tree.head) if n.action.kind == "stage"][-6:]
    assert [n.action.lorentz_window_tol for n in nodes] == [1e-2] * 4 + [None, None]
    assert "lorentz_window_tol=0.01" in nodes[0].action.api_call()
    assert "lorentz_window_tol" not in nodes[-1].action.api_call()
    picked = ref.cherry_pick(nodes[0].id, _data())
    assert picked.stages[-1].lorentz_window_tol == 1e-2


def test_the_answer_is_the_answer_tolerances(staged_pair):
    """The brief's bar, on the fixture this file can afford: every refined
    value within 0.1 of the unscheduled fit's own esd."""
    staged, flat, _ = staged_pair
    assert staged.status == flat.status == "converged"
    assert len(staged.stages) == len(flat.stages)
    ref = {p.path: p for p in flat.parameters}
    for p in staged.parameters:
        want = ref[p.path]
        if want.stderr:
            assert abs(p.value - want.value) <= 0.1 * want.stderr, p.path


def test_a_constant_wavelength_stage_records_no_lorentzian_window():
    """The schedule is a bank's; a 2θ fit under the same default plan records
    ``None`` on every stage, the closing one included, never the scheduled
    number it did not run at."""
    from rietx.model.forward import compile_model

    structure = silicon()
    instrument = rx.Instrument.constant_wavelength_neutron(wavelength=1.5401)
    two_theta = np.arange(20.0, 100.0, 0.05)
    blank = PatternData(two_theta=two_theta.tolist(),
                        intensity=[1.0] * len(two_theta))
    model = compile_model(structure, instrument, blank)
    table = ParameterTable(structure, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    data = PatternData(two_theta=two_theta.tolist(),
                       intensity=(1e3 * np.maximum(y, 0.0) + 10.0).tolist())
    result = rx.Refinement(structure, instrument, history=False).fit(
        data, plan=rx.RefinementPlan(stages=[
            rx.Stage("scale", ["phases.*.scale"]),
            rx.Stage("cell", ["phases.*.cell.a"])]))
    assert [st.lorentz_window_tol for st in result.stages] == [None, None, None]
