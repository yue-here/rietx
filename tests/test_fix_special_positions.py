"""``Refinement.fix_special_positions()``: the opt-in of #728 item 4."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.bodies import body_from_atoms
from rietx.crystallography.cif import structure_from_cif

P = rx.Parameter


def _phase(vary_all: bool) -> rx.Phase:
    def atom(label, species, x, y, z):
        return rx.Atom(label=label, species=species, x=P(value=x, vary=vary_all),
                       y=P(value=y, vary=vary_all), z=P(value=z, vary=vary_all),
                       biso=P(value=0.5))

    # P n m a: Mn on an inversion centre (no positional freedom) beside La on
    # the mirror (x, z free) and a general O
    return rx.Phase(
        name="p", space_group="P n m a",
        cell=rx.Cell(a=P(value=5.74), b=P(value=7.69), c=P(value=5.54),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[atom("La", "La", 0.0505, 0.25, 0.9945),
               atom("Mn", "Mn", 0.0, 0.0, 0.5),
               atom("O2", "O", 0.2837, 0.0368, 0.7155)])


def _ref():
    return rx.Refinement(rx.Structure(phases=[_phase(True)]),
                         rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.5),
                         history=False)


def test_a_fully_fixed_site_with_vary_true_is_refused_at_the_first_listing():
    with pytest.raises(ValueError, match="fully fixed special position"):
        _ref().parameters()


def test_fix_special_positions_clears_exactly_those_coordinates_and_the_model_builds():
    ref = _ref()
    cleared = ref.fix_special_positions()
    assert cleared == ["phases.0.atoms.1.x", "phases.0.atoms.1.y",
                       "phases.0.atoms.1.z"]
    rows = ref.parameters()            # no longer refused
    assert rows
    atoms = ref.structure.phases[0].atoms
    assert [a.x.vary for a in atoms] == [True, False, True]
    # the free sites keep their flags: La on its mirror and the general O
    assert atoms[0].z.vary and atoms[2].y.vary
    assert ref.fix_special_positions() == []          # nothing left to fix


def test_the_structure_it_fixes_refines():
    ref = _ref()
    ref.fix_special_positions()
    grid = np.arange(10.0, 150.0, 0.1)
    truth = rx.Refinement(rx.Structure(phases=[_phase(False)]),
                          rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.5),
                          history=False)
    y = np.asarray(truth.predict(grid)) + 40.0
    data = rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("xyz", ["phases.*.scale", "phases.*.atoms.*.dof.*"])]),
        telemetry=False)
    assert result.status in ("converged", "max_iter")


def _nacl(vary_na: bool, vary_cl: bool) -> rx.Structure:
    def atom(label, x, vary):
        return rx.Atom(label=label, species=label, x=P(value=x, vary=vary),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.5))

    return rx.Structure(phases=[rx.Phase(
        name="NaCl", space_group="F m -3 m",
        cell=rx.Cell(a=P(value=5.64), b=P(value=5.64), c=P(value=5.64),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[atom("Na", 0.0, vary_na), atom("Cl", 0.5, vary_cl)])])


def _nacl_ref(vary_na: bool, vary_cl: bool) -> rx.Refinement:
    return rx.Refinement(_nacl(vary_na, vary_cl),
                         rx.Instrument.debye_scherrer(wavelength=1.5406),
                         history=False)


def test_the_refusal_names_every_fixed_site_at_once():
    """WP-1913 (#728 item 4): NaCl with both x free, as the benchmark agent had
    it.  The refusal named Na only, so a caller fixed one site per attempt and
    an agent wrote a retry loop; it now names both, in walk order."""
    with pytest.raises(ValueError) as caught:
        _nacl_ref(True, True).parameters()
    assert str(caught.value).startswith(
        "phases.0.atoms.0 and phases.0.atoms.1 sit on fully fixed special "
        "positions; their site symmetry allows no positional freedom")
    assert "Refinement.fix_special_positions()" in str(caught.value)


def test_one_fixed_site_keeps_its_sentence_byte_for_byte():
    with pytest.raises(ValueError) as caught:
        _nacl_ref(False, True).parameters()
    assert str(caught.value) == (
        "phases.0.atoms.1 sits on a fully fixed special position; its site "
        "symmetry allows no positional freedom — set vary=False "
        "(Refinement.fix_special_positions() does it for every such site)")


def test_a_rigid_body_origin_on_a_fixed_site_is_fixed_too():
    """A body's origin refines like an atom's coordinates (WP-1805), so the
    table refuses a free one on the 2a centre of P2₁/n by the same sentence.
    ``fix_special_positions`` walked atoms only, returned ``[]`` and left the
    model unfittable while its message promised to fix every such site."""
    phase = structure_from_cif(
        str(Path(__file__).parent / "data" / "cod_1550439.cif")).phases[0]
    dumped = phase.model_dump()
    for a in dumped["atoms"]:
        for c in "xyz":
            a[c]["vary"] = False
    phase = rx.Phase.model_validate(dumped)
    body = body_from_atoms(phase, [a.label for a in phase.atoms], "C16H26",
                           origin=(0.0, 0.0, 0.0), origin_vary=True)
    ref = rx.Refinement(
        rx.Structure(phases=[rx.Phase.model_validate(
            {**phase.model_dump(), "rigid_bodies": [body.model_dump()]})]),
        rx.Instrument.debye_scherrer(wavelength=1.5406), history=False)
    with pytest.raises(ValueError, match=r"^phases\.0\.rigid_bodies\.0\.origin sits on"):
        ref.parameters()
    assert ref.fix_special_positions() == [
        f"phases.0.rigid_bodies.0.origin.{c}" for c in "xyz"]
    assert ref.parameters()
