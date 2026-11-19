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
from rietx.multi import MultiHistogramRefinement, _hold_width_twins_multi
from rietx.params.multi import MultiParameterTable, SharingMap
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


def test_the_gaussian_triple_holds_w():
    """W, ``gauss_size`` and ``gauss_strain`` free with U fixed:
    (δW, δsize, δstrain) = (1, −1, 1) changes no width at any angle, and U is
    not free to take it, so W is held (WP-2219)."""
    table = _table(make_lab6(), ["instrument.profile.w", "phases.*.gauss_size",
                                 "phases.*.gauss_strain"])
    held, _, twins = _hold_width_twins(table, set())
    assert held == ["instrument.profile.w"]
    assert twins == {"instrument.profile.w": ["phases.0.gauss_size",
                                              "phases.0.gauss_strain"]}
    assert {"phases.0.gauss_size", "phases.0.gauss_strain"} <= set(table.free_paths)


def test_the_triple_with_u_free_holds_u_and_w():
    """With U free as well the null space is two-dimensional: U pairs with the
    strain, and the triple survives U's hold, so both instrument terms go."""
    table = _table(make_lab6(), ["instrument.profile.u", "instrument.profile.w",
                                 "phases.*.gauss_size", "phases.*.gauss_strain"])
    held, _, twins = _hold_width_twins(table, set())
    assert sorted(held) == ["instrument.profile.u", "instrument.profile.w"]
    assert {"phases.0.gauss_size", "phases.0.gauss_strain"} <= set(table.free_paths)


def test_w_with_one_specimen_term_is_not_held():
    for free in (["instrument.profile.w", "phases.*.gauss_size"],
                 ["instrument.profile.w", "phases.*.gauss_strain"]):
        table = _table(make_lab6(), free)
        assert _hold_width_twins(table, set()) == ([], {}, {})


def test_two_wavelengths_separate_the_triple():
    """``gauss_size`` goes as λ² and ``gauss_strain`` does not (WP-1131), so
    two histograms at different wavelengths see the size and the strain apart
    and the triple is not flat in a joint fit: nothing is held."""
    mt = _joint(["instrument.profile.w", "phases.*.gauss_size",
                 "phases.*.gauss_strain"])
    assert _hold_width_twins_multi(mt, [set(), set()]) == ([], {})


def test_a_shared_w_beside_each_patterns_widths_is_held():
    """WP-2028's series shape: one wavelength, W shared, each pattern's own
    ``gauss_size`` and ``gauss_strain``.  Every pattern carries the triple, and
    the shared W is the one column that takes it."""
    instruments = [Instrument.debye_scherrer(wavelength=WAVELENGTH) for _ in range(3)]
    mt = MultiParameterTable(make_lab6(), instruments, sharing=SharingMap(
        shared=["instrument.profile.w"], per_histogram=["phases.*.gauss_*"]))
    mt.set_vary(["instrument.profile.w", "phases.*.gauss_size",
                 "phases.*.gauss_strain"], True)
    held, twins = _hold_width_twins_multi(mt, [set(), set(), set()])
    assert held == ["instrument.profile.w"]
    assert len(twins["instrument.profile.w"]) == 6


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


_TRIPLE = ["instrument.profile.w", "phases.*.gauss_size", "phases.*.gauss_strain"]


def _triple_plan() -> RefinementPlan:
    return RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*", "instrument.zero_shift"]),
        Stage(name="widths", turn_on=_TRIPLE, seed=1e-4),
    ])


@pytest.mark.parametrize("w_start", [5e-4, 1.5e-4])
def test_the_lab6_triple_is_held_from_either_start(w_start):
    """WP-2028's case: synthetic LaB6 with W, ``gauss_size`` and
    ``gauss_strain`` free.  Unheld, two starts landed 140 esd apart in W, each
    quoting ± 6.3e-7.  Held, W stays where the stage found it, the specimen
    widths keep their esds, and no direction is discarded."""
    structure, ins = perturbed_models()
    ins.profile.w.value = w_start
    ref = Refinement(structure, ins)
    result = ref.fit(synthesize(), plan=_triple_plan())
    widths = result.stages[2]
    assert widths.width_twins_held == {"instrument.profile.w": [
        "phases.0.gauss_size", "phases.0.gauss_strain"]}
    rows = {p.path: p for p in result.parameters}
    assert rows["phases.0.gauss_size"].stderr > 0.0
    assert rows["phases.0.gauss_strain"].stderr > 0.0
    assert not [d for d in result.diagnostics
                if d.code == "COVARIANCE_DIRECTION_DISCARDED"]


def test_the_lab6_triple_is_held_in_a_joint_fit():
    """Three patterns at one wavelength, W shared and each pattern's own
    Gaussian widths: the shared W takes every pattern's triple."""
    structure, ins = perturbed_models()
    data = [synthesize(noise_seed=s) for s in (7, 8, 9)]
    mr = MultiHistogramRefinement(
        structure, [ins.model_copy(deep=True) for _ in data],
        sharing=SharingMap(shared=["instrument.profile.w"],
                           per_histogram=["phases.*.gauss_*"]))
    result = mr.fit(data, plan=_triple_plan())
    assert "instrument.profile.w" in result.stages[2].held
    rows = {p.path: p for p in result.parameters}
    for h in range(3):
        assert rows[f"hist.{h}.phases.0.gauss_size"].stderr > 0.0
    assert not [d for d in result.diagnostics
                if d.code == "COVARIANCE_DIRECTION_DISCARDED"]
