"""``structure_from_cif`` names the fault in a malformed file.

gemmi stops on a malformed CIF with ``file:line:col: parse error`` and no
cause, and reads a number it cannot parse as NaN, which then reached the
schema as "value nan lies outside bounds" with no file, tag or value.  The
2026-10-06 MAGNDATA sweep found 70 files stopped by a bare parse error and 3 by
the NaN; every one was malformed, and each kind below is one of them,
reproduced on a hand-written file.  Each test states the edit that fixes the
file, so the message is checked for naming *that*, and the file is checked to
read once the edit is made (the positive arm: the fault named is the fault).
"""

from __future__ import annotations

import pytest

from rietx.crystallography.cif import structure_from_cif

_BASE = b"""data_rocksalt
_cell_length_a 4.2
_cell_length_b 4.2
_cell_length_c 4.2
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'F m -3 m'
_journal_name_full 'none'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Ni1 Ni 0 0 0 1
O1 O 0.5 0.5 0.5 1
"""
_GOOD = b"_journal_name_full 'none'"


@pytest.mark.parametrize("bad, named", [
    # a MacRoman en dash in an unquoted value, in a file headed CIF 2.0
    (b"_citation_journal_volume 12\xd013", "byte 0xD0 is not UTF-8"),
    ("_chemical_formula_sum “Ni O”".encode(), "typographic quotes"),
    (b"_citation_year 2010\x02", "control character (U+0002)"),
    (b"_journal_name_full 'J. Phys", "not closed on this line"),
    (b"_chemical_formula_sum Ni O", "holds whitespace and is not quoted"),
    (b"journal_name_full 'none'", "lost its underscore"),
])
def test_a_syntax_fault_is_named(tmp_path, bad, named):
    path = tmp_path / "bad.cif"
    path.write_bytes(b"#\\#CIF_2.0\n" + _BASE.replace(_GOOD, bad))
    with pytest.raises(ValueError, match="could not be read") as info:
        structure_from_cif(path)
    assert named in str(info.value)
    assert "line 10" in str(info.value)      # the line the fault is on


def test_a_fault_named_is_the_fault(tmp_path):
    """The positive arm: the same file with the named edit made reads."""
    path = tmp_path / "good.cif"
    path.write_bytes(b"#\\#CIF_2.0\n" + _BASE.replace(
        _GOOD, b"_citation_journal_volume 12-13"))
    assert len(structure_from_cif(path).phases[0].atoms) == 2


@pytest.mark.parametrize("old, new, named", [
    (b"_cell_length_c 4.2", b"_cell_length_c 4.2l(3)",
     "_cell_length_c is '4.2l(3)'"),
    (b"O1 O 0.5 0.5 0.5 1", b"O1 O 0.5(2 0.5 0.5 1",
     "_atom_site_fract_x for site 'O1' is '0.5(2'"),
])
def test_a_malformed_number_is_named(tmp_path, old, new, named):
    path = tmp_path / "bad.cif"
    path.write_bytes(_BASE.replace(old, new))
    with pytest.raises(ValueError, match="not a CIF number") as info:
        structure_from_cif(path)
    assert named in str(info.value)


@pytest.mark.parametrize("new, tag, meaning", [
    (b"O1 O . 0.5 0.5 1", "_atom_site_fract_x", "inapplicable"),
    (b"O1 O 0.5 ? 0.5 1", "_atom_site_fract_y", "unknown"),
    (b"O1 O 0.5 0.5 . 1", "_atom_site_fract_z", "inapplicable"),
])
def test_a_null_coordinate_is_refused_by_name(tmp_path, new, tag, meaning):
    """A coordinate written ``.`` or ``?`` is refused naming the file, the site
    and the tag (#913, item 1).  CIF reads ``?`` as unknown and ``.`` as
    inapplicable, never as zero; gemmi reads both as NaN, which reached the
    schema as an anonymous "value nan lies outside bounds"."""
    path = tmp_path / "null.cif"
    path.write_bytes(_BASE.replace(b"O1 O 0.5 0.5 0.5 1", new))
    with pytest.raises(ValueError, match="not as a number") as info:
        structure_from_cif(path)
    message = str(info.value)
    assert str(path) in message
    assert f"{tag} for site 'O1'" in message
    assert meaning in message


@pytest.mark.parametrize("null", [b"?", b"."])
def test_a_null_occupancy_reads_by_the_core_default(tmp_path, null):
    """An occupancy written ``.`` or ``?`` reads as 1.0, the
    ``_enumeration_default`` of ``_atom_site_occupancy`` in the IUCr core
    dictionary 2.4.5, as an absent column does (#913, item 1)."""
    path = tmp_path / "occ.cif"
    path.write_bytes(_BASE.replace(b"O1 O 0.5 0.5 0.5 1",
                                   b"O1 O 0.5 0.5 0.5 " + null))
    atoms = structure_from_cif(path).phases[0].atoms
    assert [a.occ.value for a in atoms] == [1.0, 1.0]
