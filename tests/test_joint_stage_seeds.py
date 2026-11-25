"""A joint stage seeds a Stephens block and holds its cone as a single fit does
(WP-2239, issue #1663).

Three rules the single runner already kept, asked of the joint one:
``Stage.strain_seed`` puts an all-zero block on the isotropic ray and writes
``StageResult.seeded``; the default LM step holds the strain cone; and it holds
the texture positivity rows beside it.  Before WP-2239 the joint stage seeded
nothing (``seeded == {}``) and its LM step carried only the width and
tied-bound rows.
"""
from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
import rietx.joint as multi_mod
import rietx.optimize.least_squares as ls
from rietx.crystallography.stephens import S_NAMES, isotropic_coefficients
from rietx.model.forward import compile_model
from rietx.params.multi import MultiParameterTable, SharingMap
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import BackgroundChebyshev

p = rx.Parameter
_DOFS = "phases.*.microstrain.dof.*"


def _cell(a: float = 4.0) -> rx.Cell:
    return rx.Cell(a=p(value=a, min=0.1), b=p(value=a, min=0.1), c=p(value=a, min=0.1),
                   alpha=p(value=90.0), beta=p(value=90.0), gamma=p(value=90.0))


def _structure(block: rx.StephensStrain, a: float = 4.0) -> rx.Structure:
    """One cubic ``P m -3 m`` phase, whose block has two DOFs."""
    return rx.Structure(phases=[rx.Phase(
        name="c", space_group="P m -3 m", cell=_cell(a),
        atoms=[rx.Atom(label="A", species="Si", x=p(value=0.0), y=p(value=0.0),
                       z=p(value=0.0))],
        scale=p(value=1.0), microstrain=block)])


def _zero() -> rx.StephensStrain:
    return rx.StephensStrain.from_values([0.0] * 15)


def _instrument(wavelength: float) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=wavelength)
    ins.background = BackgroundChebyshev(coefficients=[p(value=10.0)])
    return ins


def _pattern(ins: rx.Instrument, lo: float, hi: float, block) -> rx.PatternData:
    """``compile_model(...).evaluate`` of ``block``'s structure plus a flat 10."""
    tt = np.arange(lo, hi, 0.02)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    structure = _structure(block)
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    return rx.PatternData(two_theta=model.tt.tolist(),
                          intensity=(np.maximum(y, 1.0) + 10.0).tolist())


def _seed_plan(max_iter: int) -> rx.RefinementPlan:
    return rx.RefinementPlan(stages=[rx.Stage(
        name="strain", turn_on=["phases.*.scale", _DOFS], strain_seed=1000.0,
        max_iter=max_iter)], closing_window_tol=None)


def _block(table: ParameterTable) -> np.ndarray:
    values = table.decode(table.x0())
    return np.array([values[f"phases.0.microstrain.{n}"] for n in S_NAMES])


# ------------------------------------------------------------------ the seed
def test_a_one_histogram_joint_stage_records_the_single_fits_seed():
    """The same stage through both runners writes the same ``seeded`` mapping:
    each DOF of the block at the value the isotropic ray gives it."""
    truth = rx.StephensStrain.isotropic(800.0, _cell())
    data = _pattern(_instrument(1.5406), 15.0, 80.0, truth)
    single = rx.Refinement(_structure(_zero()), _instrument(1.5406),
                           history=False).fit(data, plan=_seed_plan(1))
    joint = rx.JointRefinement(
        _structure(_zero()), [_instrument(1.5406)]).fit([data], plan=_seed_plan(1))
    want = single.stages[0].seeded
    assert sorted(want) == ["phases.0.microstrain.dof.0", "phases.0.microstrain.dof.1"]
    assert all(v != 0.0 for v in want.values())
    assert joint.stages[0].seeded == want


def test_a_shared_block_starts_on_the_isotropic_ray_in_every_histogram():
    mt = MultiParameterTable(_structure(_zero()),
                             [_instrument(1.5406), _instrument(0.7107)])
    freed = mt.set_vary([_DOFS], True)
    # one shared column per DOF, so the joint names are bare
    assert freed == ["phases.0.microstrain.dof.0", "phases.0.microstrain.dof.1"]
    assert mt.seed_floored(freed, 1e-3) == []
    assert mt.seed_stephens(freed, 1200.0) == freed
    for table in mt.tables:
        assert np.allclose(_block(table),
                           isotropic_coefficients(_cell().lengths_angles(), 1200.0),
                           rtol=1e-9)
    # the column carries one value, which every pattern's copy agrees on
    x0 = mt.x0()
    for h, table in enumerate(mt.tables):
        assert np.array_equal(x0[mt.col_map(h)], table.x0())


def test_a_shared_block_over_per_histogram_cells_takes_histogram_0s_ray():
    """Each cell has its own ray, and one shared column can hold only one value:
    the block takes pattern 0's, which is inside every pattern's cone."""
    mt = MultiParameterTable(
        [_structure(_zero(), 4.0), _structure(_zero(), 4.1)],
        [_instrument(1.5406), _instrument(0.7107)],
        sharing=SharingMap(per_histogram=["phases.*.cell.*"]))
    freed = mt.set_vary([_DOFS], True)
    assert mt.seed_stephens(freed, 1000.0) == freed
    ray0 = isotropic_coefficients(_cell(4.0).lengths_angles(), 1000.0)
    for table in mt.tables:
        assert np.allclose(_block(table), ray0, rtol=1e-9)
    assert not np.allclose(ray0, isotropic_coefficients(_cell(4.1).lengths_angles(),
                                                        1000.0), rtol=1e-3)


def test_a_per_histogram_block_takes_each_histograms_own_ray():
    mt = MultiParameterTable(
        [_structure(_zero(), 4.0), _structure(_zero(), 4.1)],
        [_instrument(1.5406), _instrument(0.7107)],
        sharing=SharingMap(per_histogram=["phases.*.cell.*",
                                          "phases.*.microstrain.*"]))
    freed = mt.set_vary([_DOFS], True)
    assert sorted(mt.seed_stephens(freed, 1000.0)) == sorted(freed)
    for table, a in zip(mt.tables, (4.0, 4.1), strict=True):
        assert np.allclose(_block(table),
                           isotropic_coefficients(_cell(a).lengths_angles(), 1000.0),
                           rtol=1e-9)


def test_a_partly_shared_block_takes_histogram_0s_ray():
    """One DOF shared and one per pattern, over per-pattern cells: the
    shared column holds one value, so the whole block takes pattern 0's ray
    rather than each pattern writing its own and the last write winning."""
    mt = MultiParameterTable(
        [_structure(_zero(), 4.0), _structure(_zero(), 4.1)],
        [_instrument(1.5406), _instrument(0.7107)],
        sharing=SharingMap(per_histogram=["phases.*.cell.*",
                                          "phases.*.microstrain.dof.1"]))
    freed = mt.set_vary([_DOFS], True)
    assert sorted(mt.seed_stephens(freed, 1000.0)) == sorted(freed)
    ray0 = isotropic_coefficients(_cell(4.0).lengths_angles(), 1000.0)
    x0 = mt.x0()
    for h, table in enumerate(mt.tables):
        assert np.allclose(_block(table), ray0, rtol=1e-9)
        assert np.array_equal(x0[mt.col_map(h)], table.x0())


def test_a_deliberate_shared_start_is_never_overwritten():
    start = rx.StephensStrain.isotropic(300.0, _cell())
    mt = MultiParameterTable(_structure(start),
                             [_instrument(1.5406), _instrument(0.7107)])
    freed = mt.set_vary([_DOFS], True)
    before = [_block(t) for t in mt.tables]
    assert mt.seed_stephens(freed, 5000.0) == []
    for table, was in zip(mt.tables, before, strict=True):
        assert np.array_equal(_block(table), was)


# ------------------------------------------------------------------ the rows
def _spy_outcomes(monkeypatch) -> list:
    outcomes: list = []
    real = multi_mod.run_multi_least_squares

    def spy(*args, **kwargs):
        out = real(*args, **kwargs)
        outcomes.append(out)
        return out

    monkeypatch.setattr(multi_mod, "run_multi_least_squares", spy)
    return outcomes


def test_a_joint_lm_step_holds_the_strain_cone_in_every_histogram(monkeypatch):
    """A specimen with no strain, fitted from the seeded ray: the fit drives
    σ²(M) toward zero, and the box-only step crosses the cone in each
    pattern, so each pattern's cone block is counted."""
    patterns = [_pattern(_instrument(1.5406), 15.0, 80.0, _zero()),
                _pattern(_instrument(0.7107), 7.0, 36.0, _zero())]
    outcomes = _spy_outcomes(monkeypatch)
    result = rx.JointRefinement(
        _structure(_zero()), [_instrument(1.5406), _instrument(0.7107)]
    ).fit(patterns, plan=_seed_plan(60))
    outcome = outcomes[0]               # the solve from the seeded ray
    assert outcome.truncated_by.get("pattern.0 phases.0.microstrain", 0) >= 1
    assert outcome.truncated_by.get("pattern.1 phases.0.microstrain", 0) >= 1
    assert result.stages[0].n_constraint_truncations >= 1


def test_a_joint_lm_step_holds_texture_positivity(monkeypatch):
    """``test_texture``'s platy specimen at order 2 wants P < 0 on (hk0); the
    joint LM step stops at the face, as the single fit's does."""
    from rietx.schemas.structure import PreferredOrientation, SphericalHarmonicTexture
    from tests.test_texture import _RECOVERY, _recovery_phase

    space_group, cell, _ = _RECOVERY["6/mmm"]
    ins = rx.Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    platy = _recovery_phase(space_group, cell, {}, vary=False).model_copy(update={
        "texture": None,
        "preferred_orientation": PreferredOrientation(axis=(0, 0, 1), r=p(value=0.4))})
    y = np.asarray(rx.Refinement(rx.Structure(phases=[platy]), ins).predict(grid))
    data = rx.PatternData(two_theta=grid.tolist(), intensity=(y + 50.0).tolist())
    start = _recovery_phase(space_group, cell, {}, vary=False).model_copy(update={
        "texture": SphericalHarmonicTexture(order=2, coefficients={
            "c2_0": p(value=0.0, vary=True)})})
    outcomes = _spy_outcomes(monkeypatch)
    rx.JointRefinement(rx.Structure(phases=[start]), [ins.model_copy(deep=True)]
                                ).fit([data], plan=rx.RefinementPlan(stages=[
                                    rx.Stage("texture", ["phases.*.scale",
                                                         "instrument.background.c*",
                                                         "phases.*.texture.*"])],
                                    closing_window_tol=None))
    assert any(o.truncated_by.get("pattern.0 phases.0.texture", 0) >= 1 for o in outcomes)


def test_the_joint_rows_are_the_single_fits_rows_on_the_joint_columns():
    """One pattern's joint rows are its single-fit rows, column for column."""
    truth = rx.StephensStrain.isotropic(800.0, _cell())
    ins = _instrument(1.5406)
    data = _pattern(ins, 15.0, 80.0, truth)
    mt = MultiParameterTable(_structure(truth), [ins])
    mt.set_vary([_DOFS], True)
    table = mt.tables[0]
    model = compile_model(mt.structures[0], mt.instruments[0], data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    x0 = mt.x0()
    (joint,) = ls._joint_positivity_inequalities([model], mt, x0)
    (single,) = ls.strain_cone_inequalities(model, table, table.x0())
    assert joint.label == "pattern.0 phases.0.microstrain"
    assert np.array_equal(joint.T[:, mt.col_map(0)], single.T)
    assert np.array_equal(joint.c, single.c)
    assert joint.T @ x0 + joint.c == pytest.approx(single.T @ table.x0() + single.c)
