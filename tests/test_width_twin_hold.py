"""The width twin hold (WP-2002): an instrument width whose specimen twin is
free is held for the stage.

U and ``gauss_strain`` both multiply tan²θ in Γ_G², Y and ``lor_strain`` tanθ
in Γ_L, X and ``lor_size`` 1/cosθ in Γ_L, so a pattern sees each pair only as
a sum.  With both free the pair walks along a flat direction, which the U, V
and Y floors used to bound.  The test is a null space read off **C**
(``refine._width_twin_flats``), so the cases below are the ones where the
answer is not "both free, so hold": a second phase that pins the instrument, an
unseen phase that does not, a Stephens block, and a joint fit.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, Refinement
from rietx.multi import _hold_width_twins_multi
from rietx.params.multi import MultiParameterTable
from rietx.params.vector import AffineTie, ParameterTable
from rietx.refine import _hold_width_twins
from rietx.schemas.structure import StephensStrain, Structure
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_refine_synthetic import WAVELENGTH, perturbed_models, synthesize
from tests.test_schemas import make_lab6


def _two_phases() -> Structure:
    structure = make_lab6()
    second = structure.phases[0].model_copy(deep=True)
    second.name = "LaB6 b"
    structure.phases.append(second)
    return structure


def _table(structure: Structure, free: list[str]) -> ParameterTable:
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=WAVELENGTH))
    table.set_vary(free, True)
    return table


def test_each_instrument_width_is_held_against_its_own_twin():
    table = _table(make_lab6(), ["instrument.profile.*", "phases.*.gauss_strain",
                                 "phases.*.lor_strain", "phases.*.lor_size"])
    held, _, twins = _hold_width_twins(table, set())
    assert twins == {"instrument.profile.u": ["phases.0.gauss_strain"],
                     "instrument.profile.y": ["phases.0.lor_strain"],
                     "instrument.profile.x": ["phases.0.lor_size"]}
    assert set(held) == set(twins)
    # held means out of θ; V and W have no twin and stay free, and so does
    # every specimen width
    assert not set(held) & set(table.free_paths)
    for path in ("instrument.profile.v", "instrument.profile.w",
                 "phases.0.gauss_strain", "phases.0.lor_strain",
                 "phases.0.lor_size"):
        assert path in table.free_paths


def test_an_instrument_width_alone_is_not_held():
    table = _table(make_lab6(), ["instrument.profile.u", "phases.*.lor_strain"])
    assert _hold_width_twins(table, set()) == ([], {}, {})
    assert "instrument.profile.u" in table.free_paths


def test_one_phase_with_its_twin_fixed_pins_the_instrument_for_both():
    """Phase 1's peaks see U alone, so U is measured, and phase 0's
    ``gauss_strain`` is then measured against it: no flat direction."""
    table = _table(_two_phases(), ["instrument.profile.u", "phases.0.gauss_strain"])
    assert _hold_width_twins(table, set()) == ([], {}, {})


def test_two_phases_with_both_twins_free_hold_the_instrument():
    table = _table(_two_phases(), ["instrument.profile.u", "phases.*.gauss_strain"])
    held, _, twins = _hold_width_twins(table, set())
    assert held == ["instrument.profile.u"]
    assert twins == {"instrument.profile.u": ["phases.0.gauss_strain",
                                              "phases.1.gauss_strain"]}


def test_an_unseen_phase_pins_nothing():
    """Phase 1 is under the support threshold, so its fixed twin is no
    evidence about U, and phase 0's pair is flat again."""
    table = _table(_two_phases(), ["instrument.profile.u", "phases.0.gauss_strain"])
    held, _, twins = _hold_width_twins(table, {1})
    assert twins == {"instrument.profile.u": ["phases.0.gauss_strain"]}


def test_a_twin_tied_to_a_visible_parameter_is_pinned_by_it():
    """A column driving ``gauss_strain`` and a cell moves the cell too, so the
    move that keeps U + ``gauss_strain`` still is not flat."""
    structure = make_lab6()
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    table = ParameterTable(structure, ins)
    table.set_vary(["instrument.profile.u", "phases.0.cell.a"], True)
    table.set_tie("phases.0.gauss_strain",
                  AffineTie(terms=(("phases.0.cell.a", 1e-3),)))
    assert _hold_width_twins(table, set()) == ([], {}, {})


def test_a_free_stephens_block_is_ys_twin():
    """The block locks ``lor_strain`` and takes its place: its isotropic
    direction is Y's at the seed, and an isotropic fit and its Stephens rival
    must refine the same instrument parameters to be compared."""
    structure = make_lab6()
    structure.phases[0].microstrain = StephensStrain.from_values([0.0] * 15)
    table = _table(structure, ["instrument.profile.y", "phases.*.microstrain.dof.*"])
    assert "phases.0.lor_strain" not in table.free_paths
    held, _, twins = _hold_width_twins(table, set())
    assert held == ["instrument.profile.y"]
    assert twins["instrument.profile.y"] == sorted(
        p for p in table.free_paths if ".microstrain.dof." in p)


def test_a_gaussian_size_holds_u_and_never_w():
    """1/cos²θ = 1 + tan²θ, so with U and W free beside ``gauss_size``,
    (δU, δW, δsize) = (−1, −1, 1) is flat.  Holding U alone removes it, and W,
    the constant width every fit needs, stays free (the generality judge)."""
    table = _table(make_lab6(), ["instrument.profile.u", "instrument.profile.w",
                                 "phases.*.gauss_size"])
    held, _, twins = _hold_width_twins(table, set())
    assert held == ["instrument.profile.u"]
    assert twins == {"instrument.profile.u": ["phases.0.gauss_size"]}
    assert "instrument.profile.w" in table.free_paths


def test_a_held_w_pins_the_gaussian_size():
    """W's total is a row of the test: with W held the constant term pins the
    size, the tan²θ term then pins U, and nothing is held."""
    table = _table(make_lab6(), ["instrument.profile.u", "phases.*.gauss_size"])
    assert _hold_width_twins(table, set()) == ([], {}, {})


def test_a_held_stephens_block_pins_y():
    structure = make_lab6()
    structure.phases[0].microstrain = StephensStrain.from_values([0.0] * 15)
    table = _table(structure, ["instrument.profile.y"])
    assert _hold_width_twins(table, set()) == ([], {}, {})


def _joint(free: list[str]) -> MultiParameterTable:
    instruments = [Instrument.debye_scherrer(wavelength=lam)
                   for lam in (0.41390, 0.71070)]
    mt = MultiParameterTable(make_lab6(), instruments)
    mt.set_vary(free, True)
    return mt


def test_a_joint_size_is_flat_with_every_histograms_x_despite_the_lambda_factor():
    """``lor_size`` is shared and scaled by λ_h/λ₀ (WP-1131), so X₀, X₁ and the
    size are three columns behind two sums: still one flat direction."""
    mt = _joint(["instrument.profile.x", "phases.*.lor_size"])
    held, twins = _hold_width_twins_multi(mt, [set(), set()])
    assert sorted(held) == ["hist.0.instrument.profile.x",
                            "hist.1.instrument.profile.x"]
    assert all(t == ["phases.0.lor_size"] for t in twins.values())


def test_one_histograms_held_x_pins_the_other():
    mt = _joint(["hist.0.instrument.profile.x", "phases.*.lor_size"])
    assert _hold_width_twins_multi(mt, [set(), set()]) == ([], {})


@pytest.fixture(scope="module")
def twin_fit():
    data = synthesize()
    structure, ins = perturbed_models()
    ins.profile.u.value = 2e-3
    plan = RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*", "instrument.zero_shift"]),
        Stage(name="widths", turn_on=["instrument.profile.u", "instrument.profile.w",
                                      "phases.*.gauss_strain"], seed=1e-4),
    ])
    ref = Refinement(structure, ins)
    return ref, ref.fit(data, plan=plan)


def test_the_stage_record_names_the_hold_and_the_value_stays(twin_fit):
    ref, result = twin_fit
    widths = result.stages[2]
    assert widths.width_twins_held == {
        "instrument.profile.u": ["phases.0.gauss_strain"]}
    assert "instrument.profile.u" in widths.held
    assert "instrument.profile.u" not in widths.freed
    assert ref.instrument.profile.u.value == 2e-3
    # the earlier stages freed no twin, and said so with an empty mapping
    assert result.stages[0].width_twins_held == {}
    # held for the stage, never for good: the declared free set keeps it
    assert "instrument.profile.u" in ref._free_paths
    assert np.isfinite(result.statistics.rwp)
