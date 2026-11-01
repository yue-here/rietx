"""``Structure.to_cif`` states the crystal, not the specimen: what that drops, pinned.

The manual (``reference/data.md``) and ``Structure.to_cif``'s docstring say a CIF
carries the cell, positions, occupancies and displacement parameters, and that
the phase scale and the sample-broadening, extinction and preferred-orientation
fields come back at their defaults.  A magnetic width was dropped the same way
and no document said so (``magnetic_lor_strain`` 0.4 → 0 in an exporter
benchmark), so this holds the sentence true: when a writer starts carrying one of
these, this test goes red and the manual changes with it.
"""

from __future__ import annotations

import pytest

import rietx as rx
from tests.test_magnetic import _mnf2

SPECIMEN_FIELDS = ("lor_size", "lor_strain", "gauss_size", "gauss_strain",
                   "magnetic_lor_size", "magnetic_lor_strain", "extinction")


@pytest.mark.parametrize("field", SPECIMEN_FIELDS)
def test_a_specimen_field_does_not_survive_a_cif_round_trip(tmp_path, field):
    phase = _mnf2()
    getattr(phase, field).value = 0.37
    default = getattr(_mnf2(), field).value
    rx.Structure(phases=[phase]).to_cif(tmp_path / "m.cif")
    back = rx.Structure.from_cif(tmp_path / "m.cif").phases[0]
    assert getattr(back, field).value == default != 0.37


def test_the_crystal_does_survive_it(tmp_path):
    """The negative arm: the cell, a site and the moment come back."""
    phase = _mnf2()
    rx.Structure(phases=[phase]).to_cif(tmp_path / "m.cif")
    back = rx.Structure.from_cif(tmp_path / "m.cif").phases[0]
    assert back.cell.a.value == pytest.approx(phase.cell.a.value)
    assert [a.label for a in back.atoms] == [a.label for a in phase.atoms]
    assert back.atoms[0].moment.values() == pytest.approx(
        phase.atoms[0].moment.values())
