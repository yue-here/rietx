"""Which data block ``structure_from_cif`` reads in a file of several (#1063, item 1).

The rule is the format's, not a guess: a block with no tags, or only the AUDIT
category's (how the block was made: ``cif_core.dic`` files AUDIT under
PUBLICATION), states no structure, so where every other block is such a one,
the one block with atom sites is the file's structure.  Anything else of
several blocks is refused, naming the blocks.  The magnetic arm's cases, from
the issue's Cr2WO6 files, are in ``test_magcif.py``; these are the ordinary
nuclear file, where the rule applies the same way, and the controls.
"""

from __future__ import annotations

import pytest

from rietx.crystallography.cif import structure_from_cif

_ROCKSALT = """\
data_rocksalt
_cell_length_a 4.2
_cell_length_b 4.2
_cell_length_c 4.2
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'F m -3 m'
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


def _read(tmp_path, text):
    path = tmp_path / "blocks.cif"
    path.write_text(text, encoding="utf-8")
    diagnostics: list = []
    phase = structure_from_cif(str(path), diagnostics=diagnostics).phases[0]
    return phase, [d for d in diagnostics if d.code == "CIF_EMPTY_BLOCK_SKIPPED"]


def _sites(phase):
    return [(a.label, a.species, a.x.value, a.y.value, a.z.value)
            for a in phase.atoms]


def test_a_single_block_reads_with_nothing_said(tmp_path):
    """The positive arm: the file alone reads as it always did."""
    phase, skipped = _read(tmp_path, _ROCKSALT)
    assert skipped == []
    assert _sites(phase) == [("Ni1", "Ni", 0.0, 0.0, 0.0),
                             ("O1", "O", 0.5, 0.5, 0.5)]


@pytest.mark.parametrize("before, after", [
    ("data_global\n\n", ""),
    ("", "\ndata_trailer\n_audit_conform_dict_name  cif_core.dic\n"),
], ids=["empty block first", "audit-only block last"])
def test_a_nuclear_structure_beside_blocks_stating_nothing_reads(
        tmp_path, before, after):
    """The rule is not the magnetic arm's: an ordinary structure beside an
    empty or audit-only block reads exactly as the file alone, wherever the
    other block sits, and the skipped block is named."""
    reference, _ = _read(tmp_path, _ROCKSALT)
    phase, (skipped,) = _read(tmp_path, before + _ROCKSALT + after)
    assert _sites(phase) == _sites(reference)
    assert phase.space_group == reference.space_group
    assert phase.name == "rocksalt"
    assert "read from data_rocksalt" in skipped.message


def test_a_publication_block_beside_the_structure_keeps_the_refusal(tmp_path):
    """The control on the rule's reach: a block stating anything beyond
    ``_audit_`` items (here a journal's) is not skipped, so the file is refused
    as before.  The message now names the blocks and what the other one
    states, where it used to say the file was not a CIF; it keeps gemmi's
    "single data block expected", which callers match on."""
    text = ("data_global\n_journal_name_full  'Synthetic'\n"
            "_publ_section_title  'two blocks'\n\n" + _ROCKSALT)
    path = tmp_path / "publication.cif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError) as refused:
        structure_from_cif(str(path))
    message = str(refused.value)
    assert "single data block expected, got 2" in message
    assert "the atom sites are in data_rocksalt" in message
    assert "data_global states _journal_name_full, _publ_section_title" in message
    assert "does not read as a CIF" not in message


def test_blocks_with_no_atom_sites_at_all_are_refused_naming_that(tmp_path):
    """Nothing to read: no block holds atom sites."""
    path = tmp_path / "none.cif"
    path.write_text("data_one\n_journal_name_full 'x'\n\ndata_two\n"
                    "_cell_length_a 4.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no block holds atom sites"):
        structure_from_cif(str(path))
