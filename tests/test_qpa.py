"""Quantitative phase analysis (Hill & Howard ZMV weight fractions).

Reference masses (IUPAC standard atomic weights, via gemmi):
La 138.905, B 10.811, Ca 40.078, F 18.998 g/mol.
"""

import math

import numpy as np
import pytest

from pxrdref import Atom, Cell, Parameter, Phase
from pxrdref.optimize.qpa import atomic_weight, phase_zmv, weight_fractions

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
