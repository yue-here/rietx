"""WP-1319 C-c — the structure block every CIF this build writes (issue #756 § 2.1).

The block states the resolved setting three ways (``_alt``, Hall, the
operation loop) and never the deprecated ``_symmetry_space_group_name_H-M``;
U rather than B; each site's multiplicity; what the cell holds (formula, Z,
weight, density, volume, the ``_atom_type`` loop); and what wrote it
(``_audit_*``).  G1-G3 of #756 § 2 close the file: gemmi parses it, its tags
are the registry's (``test_cif_registry.py`` holds the rest of G2), and
``Structure.from_cif`` returns every stored field.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx._about import DIST_NAME
from rietx.crystallography.cif import structure_from_cif, structure_to_cif
from rietx.crystallography.lattice import cell_volume
from rietx.crystallography.scattering import written_species
from rietx.crystallography.symmetry import get_spacegroup, resolve_group
from rietx.io.cif import blocks
from rietx.io.cif.registry import TAGS
from rietx.model.geometry import symmetry_operations
from tests.test_operator_list_phase import S3_CHILD_LABEL, S3_CHILD_OPS, _phase, _triplets

DATA = Path(__file__).parent / "data"
EIGHT_PI_SQ = 8.0 * math.pi ** 2


@pytest.fixture(autouse=True)
def _one_creation_date(monkeypatch):
    monkeypatch.setattr(blocks, "_today", lambda: "2026-10-09")


def _site(label, species, xyz, *, biso=0.5, occ=1.0):
    return rx.Atom(label=label, species=species, x=rx.Parameter(value=xyz[0]),
                   y=rx.Parameter(value=xyz[1]), z=rx.Parameter(value=xyz[2]),
                   occ=rx.Parameter(value=occ), biso=rx.Parameter(value=biso))


def _caf2() -> rx.Structure:
    return rx.Structure(phases=[rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(5.4631),
        atoms=[_site("Ca1", "Ca", (0.0, 0.0, 0.0)),
               _site("F1", "F", (0.25, 0.25, 0.25))])])


def _listed() -> rx.Structure:
    return rx.Structure(phases=[_phase(S3_CHILD_LABEL, list(S3_CHILD_OPS),
                                       (14.0, 6.0, 8.0, 90.0, 97.0, 90.0))])


def _read(name: str) -> rx.Structure:
    return rx.Structure.from_cif(str(DATA / name), aniso=True)


def _written(structure: rx.Structure, tmp_path: Path, name: str = "s.cif"):
    path = tmp_path / name
    structure.to_cif(path)
    return path, gemmi.cif.read(str(path))


def _loop(block, tag: str) -> list[str]:
    return [gemmi.cif.as_string(v) for v in block.find_loop(tag)]


def _value(block, tag: str) -> str | None:
    found = block.find_value(tag)
    return None if found is None else gemmi.cif.as_string(found)


# ---------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------

def test_the_file_opens_with_the_cif_1_1_magic_line(tmp_path):
    path, _doc = _written(_caf2(), tmp_path)
    assert path.read_text(encoding="utf-8").splitlines()[0] == "#\\#CIF_1.1"


def test_a_refinement_cif_opens_with_it_too(tmp_path):
    from tests.test_exporters import make_lab6
    ref = rx.Refinement(make_lab6(), rx.Instrument.debye_scherrer(wavelength=0.4139))
    tt = np.arange(10.0, 30.0, 0.02)
    data = rx.PatternData(two_theta=tt.tolist(),
                          intensity=(np.asarray(ref.predict(tt)) + 10.0).tolist())
    ref.fit(data, plan=rx.RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"])]))
    path = tmp_path / "r.cif"
    ref.write_cif(path)
    assert path.read_text(encoding="utf-8").splitlines()[0] == "#\\#CIF_1.1"
    block = gemmi.cif.read(str(path)).sole_block()
    assert _loop(block, "_audit_conform_dict_name") == ["cif_core.dic", "cif_pd.dic"]
    assert _loop(block, "_audit_conform_dict_version") == ["3.3.0", "2.5.0"]
    # one operation loop, the structure block's: the geometry codes index it
    loops = [item.loop for item in block if item.loop is not None
             and "_space_group_symop_operation_xyz" in item.loop.tags]
    assert len(loops) == 1
    assert _loop(block, "_atom_type_scat_source")[0].startswith("Waasmaier")


# ---------------------------------------------------------------------------
# symmetry: the resolved setting, three ways, and never the deprecated tag
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["cod_1000055.cif", "cod_1000236.cif",
                                  "fluorapatite.cif"])
def test_the_space_group_items_are_the_resolved_groups(tmp_path, name):
    structure = _read(name)
    phase = structure.phases[0]
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    sg = get_spacegroup(phase.space_group)
    assert _value(block, "_space_group_name_H-M_alt") == sg.xhm()
    assert _value(block, "_space_group_name_Hall") == sg.hall
    assert _value(block, "_space_group_IT_number") == str(sg.number)
    assert _value(block, "_space_group_crystal_system") == sg.crystal_system_str()
    assert block.find_value("_symmetry_space_group_name_H-M") is None
    ops = _loop(block, "_space_group_symop_operation_xyz")
    assert ops == symmetry_operations(resolve_group(phase.space_group, None))
    assert _loop(block, "_space_group_symop_id") == [str(i) for i in
                                                     range(1, len(ops) + 1)]


def test_a_bare_symbol_is_written_as_the_setting_it_resolves_to(tmp_path):
    """``Fd-3m`` stored bare is ``F d -3 m:1`` here, and the file says so: a
    bare symbol over origin-2 coordinates describes a different compound."""
    structure = rx.Structure(phases=[rx.Phase(
        name="spinel", space_group="Fd-3m", cell=rx.Cell.cubic(8.08),
        atoms=[_site("Mg1", "Mg", (0.0, 0.0, 0.0))])])
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert _value(block, "_space_group_name_H-M_alt") == "F d -3 m:1"
    assert _value(block, "_space_group_name_Hall") == "F 4d 2 3 -1d"


def test_an_operator_list_phase_states_only_what_its_list_identifies(tmp_path):
    """A list no tabulated setting has: its label, its point group's crystal
    system and the operations; no IT number or Hall symbol is invented."""
    structure = _listed()
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert _value(block, "_space_group_name_H-M_alt") == S3_CHILD_LABEL
    assert _value(block, "_space_group_crystal_system") == "monoclinic"
    assert block.find_value("_space_group_IT_number") is None
    assert block.find_value("_space_group_name_Hall") is None
    assert _loop(block, "_space_group_symop_operation_xyz") == list(S3_CHILD_OPS)


def test_a_list_that_is_a_tabulated_groups_names_its_type(tmp_path):
    """The same operations as ``P 1 21/c 1`` in another order: the type and
    the Hall symbol are the list's to state, the order the caller's."""
    ops = ["x,y,z", *reversed(_triplets("P 1 21/c 1")[1:])]
    structure = rx.Structure(phases=[_phase("P 1 21/c 1 [explicit]", ops,
                                            (7.0, 6.0, 8.0, 90.0, 97.0, 90.0))])
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert _value(block, "_space_group_IT_number") == "14"
    assert _value(block, "_space_group_name_Hall") == "-P 2ybc"
    assert _loop(block, "_space_group_symop_operation_xyz") == ops


# ---------------------------------------------------------------------------
# U, not B
# ---------------------------------------------------------------------------

def test_the_displacement_is_u_with_its_su(tmp_path):
    structure = _caf2()
    structure.phases[0].atoms[1].biso.stderr = 0.04
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert block.find_value("_atom_site_B_iso_or_equiv") is None
    assert _loop(block, "_atom_site_adp_type") == ["Uiso", "Uiso"]
    u = _loop(block, "_atom_site_U_iso_or_equiv")
    assert u[0] == repr(blocks.u_from_b(0.5))
    # 0.04 / 8π² = 0.000507, two figures of su
    assert u[1] == "0.00633(51)"


def test_an_anisotropic_site_writes_uani_and_its_tensor(tmp_path):
    _path, doc = _written(_read("cod_1000236.cif"), tmp_path)
    block = doc.sole_block()
    assert set(_loop(block, "_atom_site_adp_type")) == {"Uani"}
    assert _loop(block, "_atom_site_aniso_label") == _loop(block, "_atom_site_label")


def test_b_to_u_to_b_is_exact_where_a_u_reaches_b_and_one_ulp_elsewhere():
    """Measured on 400 000 values: 12.6 % have no U reading back exactly, and
    those are one ulp off.  A sample here, and the fixed point beside it."""
    rng = random.Random(3)
    values = [rng.uniform(0.0, 5.0) for _ in range(4000)]
    values += [round(rng.uniform(0.0, 5.0), 3) for _ in range(4000)]
    off = 0
    for b in values:
        u = float(repr(blocks.u_from_b(b)))
        back = blocks.b_from_u(u)
        assert abs(back - b) <= math.ulp(b)
        off += back != b
        # a second write writes the same U
        assert blocks.u_from_b(back) == u
    assert 0.05 < off / len(values) < 0.25
    # a file's U is written back as the file spelled it
    for u0 in (0.01385, 0.006079, 0.0122, 0.25):
        assert blocks.u_from_b(blocks.b_from_u(u0)) == u0


# ---------------------------------------------------------------------------
# multiplicity, the cell's contents and the atom types
# ---------------------------------------------------------------------------

def test_each_site_states_its_multiplicity(tmp_path):
    _path, doc = _written(_read("fluorapatite.cif"), tmp_path)
    block = doc.sole_block()
    assert _loop(block, "_atom_site_site_symmetry_multiplicity") == \
        ["4", "6", "6", "2", "6", "6", "12"]


@pytest.mark.parametrize("structure, formula, z", [
    (lambda: _read("cod_1000055.cif"), "B6 La", "1"),
    (lambda: _read("fluorapatite.cif"), "Ca5 F O12 P3", "2"),
    (lambda: _read("cod_1000236.cif"), "Al2 Ca3 F14 Na2", "4"),
    (_caf2, "Ca F2", "4"),
], ids=["LaB6", "fluorapatite", "NAC", "CaF2"])
def test_formula_z_weight_and_density_are_the_cells(tmp_path, structure, formula, z):
    """What checkCIF computed on the baseline (WP-1319), now stated."""
    built = structure()
    _path, doc = _written(built, tmp_path)
    block = doc.sole_block()
    assert _value(block, "_chemical_formula_sum") == formula
    assert _value(block, "_cell_formula_units_Z") == z
    weight = float(_value(block, "_chemical_formula_weight"))
    expected = sum(gemmi.Element(e).weight * (int(n) if n else 1)
                   for e, n in (re.fullmatch(r"([A-Z][a-z]?)(\d*)", part).groups()
                                for part in formula.split()))
    assert weight == pytest.approx(expected, rel=1e-12)
    volume = float(_value(block, "_cell_volume"))
    assert volume == pytest.approx(cell_volume(*built.phases[0].cell.lengths_angles()), rel=1e-12)
    density = float(_value(block, "_exptl_crystal_density_diffrn"))
    assert density == pytest.approx(weight * int(z) / (0.602214076 * volume), rel=1e-12)


def test_a_partial_occupancy_states_its_counts_and_z_of_one(tmp_path):
    structure = _caf2()
    structure.phases[0].atoms[1].occ.value = 0.9
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert _value(block, "_chemical_formula_sum") == "Ca4 F7.2"
    assert _value(block, "_cell_formula_units_Z") == "1"
    assert _loop(block, "_atom_type_number_in_cell") == ["4.0", "7.2"]


def test_the_atom_type_loop_names_what_the_sites_name(tmp_path):
    _path, doc = _written(_read("cod_1000236.cif"), tmp_path)
    block = doc.sole_block()
    types = _loop(block, "_atom_type_symbol")
    assert set(_loop(block, "_atom_site_type_symbol")) == set(types)
    assert dict(zip(types, _loop(block, "_atom_type_number_in_cell"),
                    strict=True)) == {"Ca2+": "12.0", "Al3+": "8.0",
                                      "Na1+": "8.0", "F1-": "56.0"}
    assert all("Waasmaier" in s and "Sears" in s
               for s in _loop(block, "_atom_type_scat_source"))


def test_every_scat_source_is_short_enough_for_checkcif():
    """checkCIF's PLATON computed nothing on a block whose scat source ran to
    113 characters, and everything at 40 (WP-1319's 2026-10-09 probes), so
    every value the writer can produce stays at or under that."""
    from rietx.crystallography.scattering import _ITC_IONS
    from rietx.io.cif import blocks

    ion = next(iter(_ITC_IONS))
    values = {blocks._scat_source(symbol, probe)
              for symbol in ("Ca", ion, "O2-") for probe in ("xray", "neutron", None)}
    assert max(len(v) for v in values) <= blocks.SCAT_SOURCE_MAX, values


def test_the_o2_row_is_not_credited_to_the_1995_paper():
    """The ``O2-`` row of the f0 file is Waasmaier & Kirfel's fit to Rez, Rez &
    Grant (1994), not a row of their 1995 paper (#1039); ``O1-`` and the
    neutral atom still are."""
    from rietx.io.cif import blocks

    assert blocks._scat_source("O2-", "xray") == "W&K, Rez et al. (1994)"
    assert blocks._scat_source("O2-", None).startswith("W&K, Rez")
    for symbol in ("O", "O1-"):
        assert blocks._scat_source(symbol, "xray") == "Waasmaier & Kirfel (1995)"
    assert blocks._scat_source("O2-", "neutron") == "Sears (1992)"


def test_a_written_oxide_cif_carries_the_o2_credit(tmp_path):
    """The route a user reaches: an ``O2-`` site written through ``to_cif``
    names Rez et al. (1994) in its ``_atom_type_scat_source`` loop (#1039)."""
    structure = rx.Structure(phases=[rx.Phase(
        name="CaO", space_group="F m -3 m", cell=rx.Cell.cubic(4.81),
        atoms=[_site("Ca1", "Ca2+", (0.0, 0.0, 0.0)),
               _site("O1", "O2-", (0.5, 0.5, 0.5))])])
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    sources = _loop(block, "_atom_type_scat_source")
    assert [v for v in sources if "Rez et al. (1994)" in v] == [
        "W&K, Rez et al. (1994); Sears (1992)"]
    assert sum("Waasmaier & Kirfel (1995)" in v for v in sources) == 1


def test_a_digitless_ion_is_respelled_by_name(tmp_path):
    """``Cu+`` is the tabulated ``Cu1+``, and the dictionary's symbol grammar
    wants the digit."""
    structure = _caf2()
    structure.phases[0].atoms[0].species = "Cu+"
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert _loop(block, "_atom_site_type_symbol")[0] == "Cu1+"
    assert _loop(block, "_atom_type_symbol")[0] == "Cu1+"
    assert block.find_value("_atom_type_description") is None


def test_an_untabulated_ion_is_written_neutral_and_said_so(tmp_path):
    structure = _caf2()
    structure.phases[0].atoms[0].species = "Ca+"
    _path, doc = _written(structure, tmp_path)
    block = doc.sole_block()
    assert _loop(block, "_atom_site_type_symbol")[0] == "Ca"
    described = dict(zip(_loop(block, "_atom_type_symbol"),
                         block.find_loop("_atom_type_description"), strict=True))
    assert "written for Ca+" in gemmi.cif.as_string(described["Ca"])
    assert described["F"] == "."


# ---------------------------------------------------------------------------
# what wrote it
# ---------------------------------------------------------------------------

def test_the_audit_items_name_the_writer_and_the_dictionaries(tmp_path, monkeypatch):
    monkeypatch.undo()
    _path, doc = _written(_caf2(), tmp_path)
    block = doc.sole_block()
    assert _value(block, "_audit_creation_date") == blocks._today()
    assert _value(block, "_audit_creation_method") == f"{DIST_NAME} {rx.__version__}"
    assert _loop(block, "_audit_conform_dict_name") == ["cif_core.dic"]
    assert _loop(block, "_audit_conform_dict_version") == ["3.3.0"]
    assert block.find_value("_audit_conform_dict_location") is None


def test_a_magnetic_block_conforms_to_the_magnetic_dictionary_too(tmp_path):
    from tests.test_magcif import _read as read_magcif
    structure = read_magcif(tmp_path, "LaMnO3")
    _path, doc = _written(structure, tmp_path, "m.cif")
    assert _loop(doc.sole_block(), "_audit_conform_dict_name") == \
        ["cif_core.dic", "cif_mag.dic"]


# ---------------------------------------------------------------------------
# refused or respelled by name
# ---------------------------------------------------------------------------

def test_two_phase_names_one_block_name_get_two_blocks(tmp_path):
    """``ph 1`` and ``ph-1`` are both ``ph_1`` as a block name, and gemmi
    answered with a bare RuntimeError; the second takes its phase index, as the
    GSAS-II phase CIF already did.  A case-only difference is a duplicate too."""
    phases = []
    for name in ("ph 1", "ph-1", "PH_1"):
        phase = _caf2().phases[0]
        phase.name = name
        phases.append(phase)
    _path, doc = _written(rx.Structure(phases=phases), tmp_path)
    assert [b.name for b in doc] == ["ph_1", "ph_1_1", "PH_1_2"]


def test_a_non_ascii_phase_name_gives_an_ascii_block_the_reader_takes(tmp_path):
    """A CIF 1.1 block name is ASCII, and ``data_α_Fe`` behind the magic line
    was a file the package's own reader refused."""
    structure = _caf2()
    structure.phases[0].name = "α-CaF₂"
    path, doc = _written(structure, tmp_path)
    assert doc.sole_block().name == "_CaF_"
    assert rx.Structure.from_cif(str(path)).phases[0].name == "_CaF_"


def test_a_label_with_a_space_is_refused_by_name_and_nothing_is_written(tmp_path):
    structure = _caf2()
    structure.phases[0].atoms[0].label = "Ca 1"
    path = tmp_path / "space.cif"
    with pytest.raises(ValueError, match=r"_atom_site_label .*'Ca 1'"):
        structure.to_cif(path)
    assert not path.exists()


# ---------------------------------------------------------------------------
# G1-G3 (#756 § 2) on LaB6, NAC, fluorapatite and an operator-list phase
# ---------------------------------------------------------------------------

def _g_structures():
    disordered = _read("fluorapatite.cif")
    disordered.phases[0].atoms[0].disorder_assembly = "A"
    disordered.phases[0].atoms[0].disorder_group = "1"
    return {"LaB6": _read("cod_1000055.cif"), "NAC": _read("cod_1000236.cif"),
            "fluorapatite": disordered, "operator-list": _listed()}


@pytest.mark.parametrize("key", ["LaB6", "NAC", "fluorapatite", "operator-list"])
def test_g1_to_g3_the_file_parses_carries_registry_tags_and_reads_back(tmp_path, key):
    structure = _g_structures()[key]
    path = tmp_path / "g.cif"
    structure_to_cif(structure, path)
    doc = gemmi.cif.read(str(path))                                   # G1
    tags = {t for block in doc for item in block
            for t in ([item.pair[0]] if item.pair else
                      item.loop.tags if item.loop else [])}
    assert tags <= set(TAGS)                                          # G2
    assert "_symmetry_space_group_name_H-M" not in tags

    a = structure.phases[0]
    b = structure_from_cif(str(path), aniso=True).phases[0]          # G3
    assert b.space_group == a.space_group
    assert b.symmetry_operations == a.symmetry_operations
    assert b.cell.lengths_angles() == a.cell.lengths_angles()
    assert [x.label for x in b.atoms] == [x.label for x in a.atoms]
    assert [x.species for x in b.atoms] == [written_species(x.species)[0]
                                            for x in a.atoms]
    for was, now in zip(a.atoms, b.atoms, strict=True):
        assert (now.x.value, now.y.value, now.z.value, now.occ.value) == \
            (was.x.value, was.y.value, was.z.value, was.occ.value)
        assert (now.disorder_assembly, now.disorder_group) == \
            (was.disorder_assembly, was.disorder_group)
        if was.aniso is None:
            assert abs(now.biso.value - was.biso.value) <= math.ulp(was.biso.value)
            assert now.aniso is None
        else:
            assert now.aniso.values() == was.aniso.values()
    # and a second write is the first, byte for byte
    again = tmp_path / "again.cif"
    structure_to_cif(structure_from_cif(str(path), aniso=True), again)
    assert again.read_bytes() == path.read_bytes()

