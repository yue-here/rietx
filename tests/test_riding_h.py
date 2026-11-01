"""Riding hydrogens on a body, their lengths by radiation, and the CIF flags (WP-1810).

The checks that can fail: an H moved to its class's length keeps every angle
about its parent; the X-ray and neutron templates differ by exactly the
tabulated offset; a joint X-ray + neutron fit takes the neutron lengths; a
class with no tabulated neutron length is refused, not guessed; and the CIF
marks body atoms ``G``, riding H ``R``/``calc`` and free atoms ``.``, while a
phase without a body writes no flag column at all.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument
from rietx.crystallography.bodies import add_body
from rietx.crystallography.riding import (
    RIDING_LENGTHS,
    riding_length,
    riding_radiation,
    set_riding_lengths,
)
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure


def _methanol_phase() -> Phase:
    """C–O with three methyl H at X-ray 0.96 Å and a hydroxyl H at 0.82 Å."""
    tet = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) / np.sqrt(3)
    c = np.zeros(3)
    o = tet[0] * 1.43
    hs = [c + tet[k] * 0.96 for k in (1, 2, 3)]
    ho = o + np.array([0.5, -0.6, 0.1]) / np.linalg.norm([0.5, -0.6, 0.1]) * 0.82
    pts = np.vstack([c, o, *hs, ho])
    seed = Atom(label="Li", species="Li", x=Parameter(value=0.6),
                y=Parameter(value=0.6), z=Parameter(value=0.6))
    phase = Phase(name="m", space_group="P1", cell=Cell.cubic(8.0), atoms=[seed])
    return add_body(phase, "meoh", ["C1", "O1", "H1", "H2", "H3", "HO"],
                    ["C", "O", "H", "H", "H", "H"], pts, (0.3, 0.3, 0.3))


CLASSES = {"H1": "CH3", "H2": "CH3", "H3": "CH3", "HO": "OH"}


def _len(body, a, b):
    t = np.asarray(body.template)
    return float(np.linalg.norm(t[body.atoms.index(a)] - t[body.atoms.index(b)]))


def test_neutron_and_xray_templates_differ_by_the_tabulated_offset():
    body = _methanol_phase().rigid_bodies[0]
    xr = set_riding_lengths(body, CLASSES, "xray")
    nu = set_riding_lengths(body, CLASSES, "neutron")
    assert _len(xr, "C1", "H1") == pytest.approx(0.96, abs=1e-12)
    assert _len(nu, "C1", "H1") == pytest.approx(1.059, abs=1e-12)
    assert _len(nu, "O1", "HO") - _len(xr, "O1", "HO") == pytest.approx(
        RIDING_LENGTHS["neutron"]["OH"] - RIDING_LENGTHS["xray"]["OH"], abs=1e-12)
    # only the length moved: the direction from the parent, hence every angle, is kept
    t0, t1 = np.asarray(body.template), np.asarray(nu.template)
    for h, p in (("H1", "C1"), ("HO", "O1")):
        i, j = body.atoms.index(h), body.atoms.index(p)
        u0 = (t0[i] - t0[j]) / np.linalg.norm(t0[i] - t0[j])
        u1 = (t1[i] - t1[j]) / np.linalg.norm(t1[i] - t1[j])
        assert np.abs(u0 - u1).max() < 1e-12
    assert nu.riding == ["H1", "H2", "H3", "HO"]
    # heavy atoms untouched
    assert _len(nu, "C1", "O1") == pytest.approx(_len(body, "C1", "O1"), abs=1e-14)


def test_a_joint_fit_takes_the_neutron_lengths():
    xray = Instrument.debye_scherrer(wavelength=1.5406)
    neutron = Instrument.model_validate({**xray.model_dump(),
                                         "source": {"kind": "neutron_cw", "wavelength": 1.54}})
    assert riding_radiation(xray) == "xray"
    assert riding_radiation(neutron) == "neutron"
    assert riding_radiation([xray, neutron]) == "neutron"


def test_n_h_has_a_neutron_length_from_the_h_n3_row():
    # Allen et al. (2006) Table 9.5.1.1, X2-N-H: 1.009 Å, neutron data only
    assert riding_length("NH", "neutron") == 1.009
    assert riding_length("NH", "xray") == 0.86


def test_every_class_has_a_length_for_both_radiations():
    """The table's comment says no entry is ``None`` today; this keeps it true
    when a row is added to one column and not the other."""
    assert set(RIDING_LENGTHS["xray"]) == set(RIDING_LENGTHS["neutron"])
    for radiation, column in RIDING_LENGTHS.items():
        missing = sorted(k for k, v in column.items() if v is None)
        assert not missing, (radiation, missing)


def test_a_class_with_no_tabulated_length_is_refused(monkeypatch):
    monkeypatch.setitem(RIDING_LENGTHS["neutron"], "NH", None)
    with pytest.raises(ValueError, match="no tabulated neutron length"):
        riding_length("NH", "neutron")
    with pytest.raises(ValueError, match="no riding-H length"):
        riding_length("SH", "xray")


def test_an_unknown_label_and_an_h_on_its_parent_are_refused_by_name():
    body = _methanol_phase().rigid_bodies[0]
    with pytest.raises(ValueError, match="no atoms \\['H9'\\]"):
        set_riding_lengths(body, {"H9": "CH3"}, "xray")
    pts = [list(p) for p in body.template]
    pts[body.atoms.index("HO")] = list(pts[body.atoms.index("O1")])
    on_parent = body.model_copy(update={"template": [tuple(p) for p in pts]})
    with pytest.raises(ValueError, match="'HO' sits on its parent 'O1'"):
        set_riding_lengths(on_parent, CLASSES, "xray")


def test_a_second_call_never_takes_a_riding_h_as_a_parent():
    body = _methanol_phase().rigid_bodies[0]
    once = set_riding_lengths(body, {"H1": "CH3"}, "neutron")
    twice = set_riding_lengths(once, {"HO": "OH"}, "neutron")
    assert twice.riding == ["H1", "HO"]
    assert _len(twice, "O1", "HO") == pytest.approx(0.967, abs=1e-12)
    assert _len(twice, "C1", "H1") == pytest.approx(1.059, abs=1e-12)


def test_cif_flags_body_atoms_riding_h_and_free_atoms(tmp_path):
    import gemmi

    from rietx.crystallography.cif import write_structure_block

    phase = _methanol_phase()
    body = set_riding_lengths(phase.rigid_bodies[0], CLASSES, "xray")
    from rietx.crystallography.bodies import place_body_atoms
    phase = place_body_atoms(phase.model_copy(update={"rigid_bodies": [body]}))
    doc = gemmi.cif.Document()
    block = doc.add_new_block("m")
    write_structure_block(block, phase)
    doc_m = gemmi.cif.Document()
    write_structure_block(doc_m.add_new_block("m"), phase)
    labels = list(block.find_values("_atom_site_label"))
    flags = dict(zip(labels, block.find_values("_atom_site_refinement_flags_posn"),
                     strict=True))
    calc = dict(zip(labels, block.find_values("_atom_site_calc_flag"), strict=True))
    assert flags == {"Li": ".", "C1": "G", "O1": "G", "H1": "R", "H2": "R",
                     "H3": "R", "HO": "R"}
    assert calc["HO"] == "calc" and calc["C1"] == "d" and calc["Li"] == "d"
    # a phase without a body writes neither column
    plain = Phase(name="p", space_group="P1", cell=Cell.cubic(5.0), atoms=[
        Atom(label="Na", species="Na", x=Parameter(value=0.0), y=Parameter(value=0.0),
             z=Parameter(value=0.0))])
    block2 = doc.add_new_block("p")
    write_structure_block(block2, plain)
    assert not list(block2.find_values("_atom_site_refinement_flags_posn"))
    # the file still reads back
    path = tmp_path / "m.cif"
    doc_m.write_file(str(path))
    from rietx.crystallography.cif import structure_from_cif
    s = structure_from_cif(str(path))
    assert isinstance(s, Structure) and len(s.phases[0].atoms) == 7
