"""A bare element label on a moment (the magnetic-path owner's ruling on #1806, 2026-11-24).

A bare label (``"Fe"``) states no charge.  On the magnetic path it is read as the element's most common oxidation
state in one ICSD census (Ding, Kumagai, Oba & Burton 2020, *J. Phys. Chem. Lett.* 11, 8264, SI Table 1;
``form_factor.read_bare_label``), and the reading is a ``MAGNETIC_ION_ASSUMED`` warning, since the moment depends on
it.  A label whose census ion carries no moment is refused before any work.  On an X-ray pattern the same site's
scattering factor stays the neutral atom's, recorded as the ``info`` row ``MAGNETIC_SITE_CHARGE_NOT_STATED``, read
for moment sites only.  These tests pin

* the fit-level warning for ``Moment(ion="Fe")`` built in Python, once per site, and its silence for a stated ion;
* the form factor the fit computes for a bare label is the census ion's, and ``"Fe0"`` the neutral atom's;
* the refusal of a d⁰ bare label when the phase is built, naming the ions to state;
* the X-ray ``info`` row: on a moment site with a bare species only, never on neutron data or a charged species.

The CIF reader's and ``solve_magnetic``'s routes are in ``tests/test_magcif.py`` and ``tests/test_magnetic_solve.py``.
"""
from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.crystallography.magnetic import form_factor as ff
from rietx.refine import _bare_magnetic_ion_diagnostics, _charge_not_stated_diagnostics
from tests.test_magnetic_form_factor_range import FEF2_CELL, _atom, _fit, _pattern, _rutile


def test_a_bare_moment_ion_is_read_as_the_census_ion_and_warned_once_per_site():
    """FeF₂ built with ``Moment(ion="Fe")``: the phase builds, the fit runs on Fe³⁺'s form factor, and the result
    carries one ``MAGNETIC_ION_ASSUMED`` warning on the site's ion, naming Fe³⁺, its share and Fe²⁺ (the right ion
    for FeF₂, which is why the reader is warned)."""
    phase = _rutile("Fe", "Fe", FEF2_CELL)
    assert phase.atoms[0].moment.ion == "Fe"
    data = _pattern(_rutile("Fe", "Fe3+", FEF2_CELL), 2.4)
    _ref, result = _fit(phase, 2.4, data)
    hits = [d for d in result.diagnostics if d.code == "MAGNETIC_ION_ASSUMED"]
    assert len(hits) == 1
    (hit,) = hits
    assert hit.level == "warning"
    assert hit.where == ["phases.0.atoms.0.moment.ion"]
    assert "Fe3+, the most common Fe oxidation state in the ICSD (57% of Fe cation reports; Fe2+ 42%" in hit.message
    assert "'Fe3+'" in hit.suggestion and "'Fe0'" in hit.suggestion
    assert hit.explanation is not None


def test_a_stated_ion_or_the_stated_neutral_atom_carries_no_warning():
    for ion in ("Fe2+", "Fe0"):
        structure = rx.Structure(phases=[_rutile("Fe", ion, FEF2_CELL)])
        assert _bare_magnetic_ion_diagnostics(structure) == []


def test_the_forward_model_uses_the_census_ion_for_a_bare_label():
    """The compiled pattern of a bare ``Fe`` moment is bit-identical to one stated ``Fe3+``, and differs from the
    neutral ``Fe0``: the reading is the one every evaluator uses, not a label in a message."""
    bare = np.asarray(_pattern(_rutile("Fe", "Fe", FEF2_CELL), 1.2).intensity)
    fe3 = np.asarray(_pattern(_rutile("Fe", "Fe3+", FEF2_CELL), 1.2).intensity)
    fe0 = np.asarray(_pattern(_rutile("Fe", "Fe0", FEF2_CELL), 1.2).intensity)
    assert np.array_equal(bare, fe3)
    assert np.max(np.abs(bare - fe0)) > 1e-3 * np.max(bare)


@pytest.mark.parametrize("element, ion, alternative", [
    ("Ti", "Ti4+", "Ti3+"), ("Nb", "Nb5+", "Nb4+"), ("Eu", "Eu3+", "Eu2+"), ("U", "U6+", "U4+"),
])
def test_a_bare_label_whose_census_ion_has_no_moment_is_refused_when_the_phase_is_built(element, ion, alternative):
    """The #1806 ruling (2026-11-24), Rule 4's literal refusal: a moment on a bare d⁰/f⁰/J = 0 label cannot be honoured, so the phase is
    refused before any work, with the census ion and the moment-carrying ions to state."""
    with pytest.raises(ValidationError) as err:
        _rutile(element, element, FEF2_CELL)
    text = str(err.value)
    assert ion in text and alternative in text and "carries no moment" in text, text
    assert float(ff.j0(alternative, 0.0)) == pytest.approx(1.0, abs=2e-2)  # the stated ion is served


def _xray():
    return rx.Instrument.bragg_brentano(radiation="CuKa")


def test_the_xray_info_row_fires_on_a_moment_site_with_a_bare_species_only():
    """The #1806 ruling (2026-11-24): on an X-ray histogram a moment site's bare species keeps the neutral X-ray scattering factor and the
    fit records it as ``info``; a charged species, a site with no moment, and a neutron histogram are silent.  Read
    for moment sites only, so a bare ``F`` on the same phase never fires (WP-2037, "Attention is a cost", clause 1)."""
    bare = rx.Structure(phases=[_rutile("Fe", "Fe3+", FEF2_CELL)])
    (hit,) = _charge_not_stated_diagnostics(bare, _xray())
    assert hit.code == "MAGNETIC_SITE_CHARGE_NOT_STATED" and hit.level == "info"
    assert hit.where == ["phases.0.atoms.0.species"]
    assert "'Fe' (Fe)" in hit.message and "neutral atom" in hit.message
    assert _charge_not_stated_diagnostics(bare, rx.Instrument.constant_wavelength_neutron(2.4)) == []
    charged = bare.model_copy(update={"phases": [bare.phases[0].model_copy(update={"atoms": [
        bare.phases[0].atoms[0].model_copy(update={"species": "Fe3+"}), bare.phases[0].atoms[1]]})]})
    assert _charge_not_stated_diagnostics(charged, _xray()) == []
    no_moment = rx.Structure(phases=[bare.phases[0].model_copy(update={
        "atoms": [_atom("Fe", "Fe", (0.0, 0.0, 0.0)), _atom("F", "F", (0.3050, 0.3050, 0.0))],
        "magnetic_symmetry": None})])
    assert _charge_not_stated_diagnostics(no_moment, _xray()) == []


def test_every_census_count_is_the_sources_and_every_covered_element_has_a_row():
    """The census table covers exactly the elements the form-factor table carries a row of, and its picks are the
    largest counts; the Fe, Mn and U rows are pinned to the source's SI Table 1 numbers."""
    rows = {ff._element(k)[0] for k in set(ff._J0) | set(ff._TABLE_KEY)}
    assert set(ff._ICSD_REPORTS) == rows
    assert ff._ICSD_REPORTS["Fe"] == {1: 119, 2: 10580, 3: 14439, 4: 222, 5: 6, 6: 8}
    assert ff._ICSD_REPORTS["Mn"] == {1: 95, 2: 9504, 3: 3188, 4: 1399, 5: 53, 6: 15, 7: 89}
    assert ff._ICSD_REPORTS["U"] == {1: 1, 2: 66, 3: 325, 4: 1002, 5: 160, 6: 4382}
    assert "Ding, Kumagai, Oba & Burton (2020)" in ff.CENSUS
