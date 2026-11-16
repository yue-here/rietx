"""An operator loop that generates a different group from the H-M symbol is refused.

Issue #913, item (3), ruled "minimum" by the maintainer on 2026-11-02 (WP-1933).
gemmi takes a tabulated loop's group over the symbol, so a loop that lost the
C-centring of C2/m built P2/m, and a P6₁ loop under ``P 61 2 2`` built P6₁,
each with half the atoms and no diagnostic.  The reader now names both groups
and stops.  A loop that is the symbol's group in another setting or origin
reads as before, and so does a loop that is no group at all (the declined
half of the issue): both are the controls here.  The files are the issue's own
synthetic cases, A to L.
"""

from __future__ import annotations

import re

import gemmi
import pytest

from rietx.crystallography.cif import structure_from_cif

_HEX = (5, 5, 12, 90, 90, 120)
_MONO = (10, 6, 7, 90, 100, 90)


def _ops(name):
    return [op.triplet() for op in gemmi.find_spacegroup_by_name(name).operations()]


def _cif(op_list, hm, cell=_HEX, mult="?"):
    head = "data_toy\n" + "".join(
        f"_cell_{k} {v}\n" for k, v in zip(
            ("length_a", "length_b", "length_c", "angle_alpha", "angle_beta",
             "angle_gamma"), cell))
    return (head + f"_space_group_name_H-M_alt '{hm}'\nloop_\n"
            "_space_group_symop_operation_xyz\n"
            + "".join(f"'{o}'\n" for o in op_list)
            + "loop_\n_atom_site_label\n_atom_site_type_symbol\n"
              "_atom_site_symmetry_multiplicity\n_atom_site_fract_x\n"
              "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_occupancy\n"
              "_atom_site_U_iso_or_equiv\n"
            + f"Cu1 Cu {mult} 0.1234 0.3456 0.0789 1 0.01\n")


#: B 1 21 1 as one database export writes it: the screw axis with the wrong
#: sign on y, a closed list that is a B-centred P-1 (the issue's row L)
_EXPORT_B21 = ["x,y,z", "-x,-y+1/2,-z", "x+1/2,y,z+1/2", "-x+1/2,-y+1/2,-z+1/2"]

REFUSED = {
    # the loop a proper subgroup of the symbol's group
    "C subgroup": (_cif(_ops("P 61"), "P 61 2 2"), "P 61 2 2 (No. 178", "P 61 (No. 169"),
    "C' subgroup, stated multiplicity": (
        _cif(_ops("P 61"), "P 61 2 2", mult=12), "P 61 2 2 (No. 178", "P 61 (No. 169"),
    # the C-centring lost
    "F lost centring, stated multiplicity": (
        _cif(_ops("P 1 2/m 1"), "C 1 2/m 1", cell=_MONO, mult=8),
        "C 1 2/m 1 (No. 12", "P 1 2/m 1 (No. 10"),
    "H lost centring": (_cif(_ops("P 1 2/m 1"), "C 1 2/m 1", cell=_MONO),
                        "C 1 2/m 1 (No. 12", "P 1 2/m 1 (No. 10"),
    # a closed list of another type: tabulated (K) and at an untabulated origin
    # (J, L), where gemmi fell back on the symbol and built it by luck
    "K inversion at the origin": (_cif(["x,y,z", "-x,-y,-z"], "P 1 21 1", cell=_MONO),
                                  "P 1 21 1 (No. 4", "P -1 (No. 2"),
    "J inversion off the origin": (_cif(["x,y,z", "-x,-y+1/2,-z"], "P 1 21 1", cell=_MONO),
                                   "P 1 21 1 (No. 4", "P -1 (No. 2"),
    "L the export's B 1 21 1": (_cif(_EXPORT_B21, "B 1 21 1", cell=_MONO),
                                "B 1 21 1 (No. 4", "P -1 (No. 2"),
}

READ = {
    "A control": (_cif(_ops("P 61 2 2"), "P 61 2 2"), "P 61 2 2"),
    "G control": (_cif(_ops("C 1 2/m 1"), "C 1 2/m 1", cell=_MONO, mult=8), "C 1 2/m 1"),
    "I control": (_cif(["x,y,z", "-x,y+1/2,-z"], "P 1 21 1", cell=_MONO), "P 1 21 1"),
    # another origin of the same group: the loop's setting is taken, as before
    "origin choice 2 under a bare symbol": (
        _cif(_ops("F d -3 m:2"), "F d -3 m", cell=(8, 8, 8, 90, 90, 90)), "F d -3 m:2"),
    # the loop is no group (the 1/6 and 5/6 translations dropped): declined by
    # the ruling, so the symbol is read and nothing is said, as before
    "B not a group": (
        _cif([re.sub(r"\+[15]/6", "", t) for t in _ops("P 61 2 2")], "P 61 2 2"),
        "P 61 2 2"),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_a_loop_of_another_group_is_refused_naming_both(tmp_path, name):
    text, symbol_group, loop_group = REFUSED[name]
    path = tmp_path / "toy.cif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="a different group") as info:
        structure_from_cif(path)
    message = str(info.value)
    assert str(path) in message
    assert symbol_group in message
    assert loop_group in message
    assert "_space_group_symop_operation_xyz" in message


@pytest.mark.parametrize("name", sorted(READ))
def test_a_loop_of_the_same_group_or_no_group_reads_as_before(tmp_path, name):
    text, group = READ[name]
    path = tmp_path / "toy.cif"
    path.write_text(text, encoding="utf-8")
    diagnostics = []
    phase = structure_from_cif(path, diagnostics=diagnostics).phases[0]
    assert phase.space_group == group
    assert diagnostics == []


def test_the_legacy_loop_tag_is_named(tmp_path):
    """A CIF 1 file's ``_symmetry_equiv_pos_as_xyz`` loop is checked the same
    way, and the refusal names the tag the file used."""
    text = (_cif(_ops("P 1 2/m 1"), "C 1 2/m 1", cell=_MONO)
            .replace("_space_group_symop_operation_xyz", "_symmetry_equiv_pos_as_xyz"))
    path = tmp_path / "legacy.cif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="_symmetry_equiv_pos_as_xyz loop"):
        structure_from_cif(path)
