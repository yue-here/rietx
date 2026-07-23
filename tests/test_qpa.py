"""Quantitative phase analysis (Hill & Howard ZMV weight fractions).

Reference masses (IUPAC standard atomic weights, via gemmi):
La 138.905, B 10.811, Ca 40.078, F 18.998 g/mol.
"""

import math

import numpy as np
import pytest

from pxrdref import Atom, Cell, Parameter, Phase
from pxrdref.optimize.qpa import atomic_weight, phase_zmv, weight_fractions
from pxrdref.schemas.common import Provenance
from pxrdref.schemas.results import (
    PhaseQuantity,
    QuantitativePhaseAnalysis,
    RefinementResult,
    Statistics,
)

from .test_schemas import make_lab6


def _caf2_phase() -> Phase:
    return Phase(
        name="CaF2", space_group="F m -3 m", cell=Cell.cubic(5.4631),
        atoms=[
            Atom(label="Ca", species="Ca2+", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="F", species="F1-", x=Parameter(value=0.25),
                 y=Parameter(value=0.25), z=Parameter(value=0.25)),
        ],
    )


def _atoms(phase: Phase):
    return [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
            for a in phase.atoms]


def test_atomic_weight_strips_charge():
    assert math.isclose(atomic_weight("La"), 138.905, abs_tol=0.1)
    assert math.isclose(atomic_weight("Ca2+"), 40.078, abs_tol=0.1)
    assert math.isclose(atomic_weight("F1-"), 18.998, abs_tol=0.1)
    with pytest.raises(ValueError):
        atomic_weight("Zz")


def test_zmv_lab6():
    phase = make_lab6().phases[0]
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    # LaB6: La on 1a (mult 1) + B on 6f (mult 6); one formula unit per cell.
    assert zmv.z == 1
    assert math.isclose(zmv.cell_mass, 138.905 + 6 * 10.811, abs_tol=0.5)
    assert math.isclose(zmv.molar_mass, zmv.cell_mass, rel_tol=1e-12)
    assert math.isclose(zmv.cell_volume, 4.1566 ** 3, rel_tol=1e-6)
    assert math.isclose(zmv.zmv, zmv.cell_mass * zmv.cell_volume, rel_tol=1e-12)


def test_zmv_caf2():
    phase = _caf2_phase()
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    # CaF2: Ca on 4a (mult 4) + F on 8c (mult 8); four formula units per cell.
    assert zmv.z == 4
    assert math.isclose(zmv.cell_mass, 4 * 40.078 + 8 * 18.998, abs_tol=0.5)
    assert math.isclose(zmv.molar_mass, 40.078 + 2 * 18.998, abs_tol=0.5)
    assert math.isclose(zmv.cell_volume, 5.4631 ** 3, rel_tol=1e-6)


def test_zmv_partial_occupancy_falls_back_to_one_formula_unit():
    phase = _caf2_phase()
    phase.atoms[1].occ.value = 0.3  # F count 0.3·8 = 2.4 → composition does not reduce
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    assert zmv.z == 1
    assert math.isclose(zmv.molar_mass, zmv.cell_mass, rel_tol=1e-12)
    assert math.isclose(zmv.cell_mass, 4 * 40.078 + 0.3 * 8 * 18.998, abs_tol=0.5)


def test_weight_fractions_no_covariance():
    # Two phases, equal Z·M·V, scales 3:1 → fractions 0.75/0.25.
    w, sc, si = weight_fractions([100.0, 100.0], [3.0, 1.0])
    assert np.allclose(w, [0.75, 0.25])
    assert sc is None and si is None


def test_weight_fractions_correlated_differs_from_independent():
    # Strongly (positively) correlated scales: the correlated ratio propagation
    # partly cancels, so σ_corr must differ from the naive independent σ.
    scale_cov = np.array([[4.0, 3.5], [3.5, 4.0]])
    w, sigma_corr, sigma_indep = weight_fractions([100.0, 100.0], [1.0, 1.0], scale_cov)
    assert np.allclose(w, [0.5, 0.5])
    assert not np.allclose(sigma_corr, sigma_indep)
    assert np.all(sigma_corr < sigma_indep)  # positive correlation shrinks σ(W)


def test_physical_covariance_block_diagonal_matches_stderr():
    from pxrdref import Instrument
    from pxrdref.params.vector import ParameterTable

    structure = make_lab6()
    structure.phases.append(_caf2_phase())
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["phases.*.scale"], True)
    theta = table.x0()
    free = table.free_paths
    i0, i1 = free.index("phases.0.scale"), free.index("phases.1.scale")
    corr = np.eye(len(theta))
    corr[i0, i1] = corr[i1, i0] = 0.7
    stderr_internal = np.full(len(theta), 0.3)

    esds = table.stderr_physical(theta, stderr_internal, corr)
    cov = table.physical_covariance(theta, stderr_internal, corr,
                                    ["phases.0.scale", "phases.1.scale"])
    # The block's diagonal is exactly the reported per-parameter esds squared,
    # so QPA σ(W) inherits the same conditioning by construction.
    assert math.isclose(math.sqrt(cov[0, 0]), esds["phases.0.scale"], rel_tol=1e-9)
    assert math.isclose(math.sqrt(cov[1, 1]), esds["phases.1.scale"], rel_tol=1e-9)
    assert cov[0, 1] != 0.0  # scales are correlated off the diagonal


def _qpa_fixture() -> QuantitativePhaseAnalysis:
    return QuantitativePhaseAnalysis(phases=[
        PhaseQuantity(name="LaB6", weight_fraction=0.6, weight_fraction_stderr=0.01,
                      scale=2.0, z=1, molar_mass=203.77, cell_mass=203.77,
                      cell_volume=71.82, zmv=14634.9),
        PhaseQuantity(name="CaF2", weight_fraction=0.4, weight_fraction_stderr=None,
                      scale=1.0, z=4, molar_mass=78.07, cell_mass=312.30,
                      cell_volume=163.05, zmv=50920.0),
    ])


def test_qpa_json_round_trip():
    qpa = _qpa_fixture()
    assert QuantitativePhaseAnalysis.model_validate_json(qpa.model_dump_json()) == qpa


def test_result_with_qpa_round_trip():
    stats = Statistics(rwp=0.05, rp=0.04, rexp=0.03, chi2=2.0, gof=1.4,
                       n_points=1000, n_free_parameters=8)
    result = RefinementResult(
        status="converged", mode="rietveld", parameters=[], statistics=stats,
        provenance=Provenance(package_version="test"), qpa=_qpa_fixture())
    assert RefinementResult.model_validate_json(result.model_dump_json()) == result
