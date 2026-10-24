"""A site whose own images coincide is one atom at every boundary that can say so (#1007).

``site_orbit`` snaps a site within ``SITE_TOL`` (1e-4, fractional) of a special
position, and on a mirror that is 5e-5 of the coordinate, because the test
compares the 2δ displacement.  PbSO₄'s S2 (``tests/data/gsas2_pbso4.gpx``, Pnma
4c on the mirror at y = ¼) moved 6e-5 off it is a general position: two images
0.0006 Å apart, 8 S in a cell of 4.  #765 merged such twins for a CIF read; the
same rule (``symmetry.site_twin_merge``, 5e-4 fractional per coordinate) now runs at the boundaries that
can report it, through ``twins.merge_site_twins``: the project readers,
``RefinementTree.load`` and the ``Refinement`` verbs that take a structure in.
``Phase`` validation stays strict and moves nothing.  ``phase_zmv`` and the
FullProf reader's ``Occ × M_general/M_site`` ratio count raw coordinates before
any ``Phase`` exists, and use the rule directly.

Each test checks what is independent of the code under test: the multiplicity
International Tables gives the Wyckoff position, the composition the published
structure has, and the prediction of the same structure stated on its special
position.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.symmetry import (
    TWIN_COORD_TOL,
    resolve_group,
    site_orbit,
    site_twin_merge,
)
from rietx.crystallography.twins import merge_site_twins
from rietx.history.tree import RefinementTree
from rietx.io.projects.gsas2 import read_gsas2_gpx, to_structure
from rietx.optimize.qpa import phase_zmv
from rietx.refine import Stage, replay
from rietx.schemas import Atom, Cell, Parameter, PatternData, Phase, Structure

DATA = Path(__file__).parent / "data"
INSTRUMENT = rx.Instrument.constant_wavelength_neutron(1.5)


@pytest.fixture(scope="module")
def pbso4() -> Phase:
    return to_structure(read_gsas2_gpx(DATA / "gsas2_pbso4.gpx")).phases[0]


def _moved(phase: Phase, label: str, **shift) -> Phase:
    """``phase`` rebuilt with one atom's coordinates shifted, as a document edit is."""
    doc = phase.model_dump()
    for atom in doc["atoms"]:
        if atom["label"] == label:
            for axis, d in shift.items():
                atom[axis]["value"] += d
    return Phase.model_validate(doc)


def _counts(phase: Phase) -> dict[str, float]:
    atoms = [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
             for a in phase.atoms]
    return phase_zmv(phase.space_group, phase.cell.lengths_angles(),
                     atoms).element_counts


def _multiplicity(phase: Phase, label: str) -> int:
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    (a,) = [a for a in phase.atoms if a.label == label]
    return site_orbit(sg, np.array([a.x.value, a.y.value, a.z.value])).multiplicity


def _y(structure: Structure, label: str = "S2") -> float:
    (a,) = [a for a in structure.phases[0].atoms if a.label == label]
    return a.y.value


def _merge(structure: Structure) -> tuple[Structure, list]:
    found: list = []
    return merge_site_twins(structure, diagnostics=found), found


def _pattern(structure: Structure) -> PatternData:
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    tt = np.arange(10.0, 120.0, 0.05)
    y = 100.0 + 1e3 * np.asarray(ref.predict(tt))
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                       sigma=np.sqrt(y).tolist())


@pytest.mark.parametrize("dy", [6e-5, 1e-4, 4e-4])
def test_issue_reproducer_counts_four_sulfur(pbso4, dy):
    """#1007's reproducer, verbatim in its core: raw coordinates into ``phase_zmv``."""
    atoms = [(a.species, a.x.value, a.y.value + (dy if a.label == "S2" else 0),
              a.z.value, a.occ.value) for a in pbso4.atoms]
    c = phase_zmv(pbso4.space_group, pbso4.cell.lengths_angles(), atoms).element_counts
    assert (c["Pb"], c["S"], c["O"]) == (4, 4, 16)      # PbSO₄, Z = 4


@pytest.mark.parametrize("dy", [6e-5, 1e-4, 4e-4])
def test_the_merge_puts_the_site_on_the_mirror_and_says_so(pbso4, dy):
    structure = Structure(phases=[_moved(pbso4, "S2", y=dy)])
    merged, found = _merge(structure)
    assert merged is not structure and _y(structure) == pytest.approx(0.25 + dy)
    assert _y(merged) == pytest.approx(0.25, abs=1e-12)
    assert _multiplicity(merged.phases[0], "S2") == 4          # Pnma 4c
    assert _counts(merged.phases[0])["S"] == 4
    (d,) = found
    assert (d.code, d.level) == ("SITE_TWINS_MERGED", "warning")
    # the two images are 2·dy·b apart, which is what ``value`` says
    assert d.value == pytest.approx(2 * dy * pbso4.cell.b.value, rel=1e-6)
    assert d.where == [f"phases.0.atoms.{[a.label for a in pbso4.atoms].index('S2')}"]
    assert "puts 8 positions" in d.message and "4 positions" in d.message
    # fully occupied: the content line, and no split-pair reading (#1088)
    assert "8 × 1 = 8 → 4 × 1 = 4." in d.message
    assert "split pair" not in d.message + d.suggestion


def test_phase_validation_is_strict_and_moves_nothing(pbso4):
    """The schema has no diagnostics channel, so it holds the coordinate as stated."""
    phase = _moved(pbso4, "S2", y=1e-4)
    assert _y(Structure(phases=[phase])) == pytest.approx(0.25 + 1e-4, abs=1e-15)
    assert _multiplicity(phase, "S2") == 8
    again = Phase.model_validate_json(phase.model_dump_json())
    assert again.model_dump() == phase.model_dump()


@pytest.mark.parametrize("dy", [1e-3, 4e-3, 1e-2])
def test_a_coordinate_further_than_the_reach_from_the_position_stays_general(pbso4, dy):
    """The negative arm: y = 0.251 at its own precision excludes 0.25 (and 0.2540, 0.26 more so)."""
    assert dy > TWIN_COORD_TOL
    structure = Structure(phases=[_moved(pbso4, "S2", y=dy)])
    merged, found = _merge(structure)
    assert merged is structure and not found
    assert _counts(merged.phases[0])["S"] == 8


def _phase(group: str, cell, xyz, *, occ: float = 1.0) -> Phase:
    return Phase(
        name="p", space_group=group,
        cell=Cell(**{k: Parameter(value=v) for k, v in
                     zip(("a", "b", "c", "alpha", "beta", "gamma"), cell, strict=True)}),
        atoms=[Atom(label="X", species="Fe", x=Parameter(value=xyz[0]),
                    y=Parameter(value=xyz[1]), z=Parameter(value=xyz[2]),
                    occ=Parameter(value=occ), biso=Parameter(value=0.5))])


# group, cell, the Wyckoff position (ITA vol. A) and its multiplicity, a point
# 1e-4 off it that SITE_TOL leaves general, and the point it is
@pytest.mark.parametrize("group, cell, stated, special, mult, general", [
    # 2-fold axis: C2/c 4e (0, y, ¼)
    ("C 1 2/c 1", (10.0, 8.0, 9.0, 90, 105, 90),
     (1e-4, 0.3, 0.25 - 1e-4), (0.0, 0.3, 0.25), 4, 8),
    # 3-fold axis: Pa-3 8c (x, x, x)
    ("P a -3", (6.0, 6.0, 6.0, 90, 90, 90),
     (0.1, 0.1 + 1e-4, 0.1 - 1e-4), (0.1, 0.1, 0.1), 8, 24),
    # inversion centre: P-1 1a (0, 0, 0)
    ("P -1", (5.0, 6.0, 7.0, 80, 85, 95),
     (1e-4, -1e-4, 2e-4), (0.0, 0.0, 0.0), 1, 2),
])
def test_a_site_near_an_axis_or_a_centre_lands_on_its_wyckoff_position(
        group, cell, stated, special, mult, general):
    sg = resolve_group(group, None)
    assert site_orbit(sg, np.array(stated)).multiplicity == general  # beyond SITE_TOL
    merged, found = _merge(Structure(phases=[_phase(group, cell, stated)]))
    a = merged.phases[0].atoms[0]
    d = np.array([a.x.value, a.y.value, a.z.value]) - np.array(special)
    assert np.max(np.abs(d - np.round(d))) < 1e-12
    assert _multiplicity(merged.phases[0], "X") == mult
    assert len(found) == 1 and f"{general} positions" in found[0].message


def test_a_split_site_is_left_split():
    """Images 0.2 Å apart at half occupancy are a split site, never twins."""
    dy = 0.1 / 8.0                                         # 2·dy·b = 0.2 Å
    structure = Structure(phases=[_phase(
        "P n m a", (7.0, 8.0, 6.0, 90, 90, 90), (0.1, 0.25 + dy, 0.3), occ=0.5)])
    merged, found = _merge(structure)
    assert merged is structure and not found


# Pnma, b = 8 Å: a general site 1e-4 off the mirror at y = ¼ (images 0.0016 Å
# apart, 8c in ITA vol. A) collapses onto 4c.  The merge keeps the occupancy, so
# at occupancy ½ the site goes from 8 × ½ = 4 to 4 × ½ = 2 atoms per cell: the
# split-pair reading of #1088, which the message must name (C2 of the split-site
# scoping, 2026-10-20).
_PNMA = ("P n m a", (7.0, 8.0, 6.0, 90, 90, 90))
_OFF, _ON = (0.1, 0.25 + 1e-4, 0.3), (0.1, 0.25, 0.3)


def _atoms_per_cell(xyz, occ: float) -> float:
    """Multiplicity from ``site_orbit`` (ITA vol. A) × occupancy, no merge applied."""
    return site_orbit(resolve_group(_PNMA[0], None), np.array(xyz)).multiplicity * occ


def test_a_half_occupied_site_is_kept_with_both_readings():
    """The gate is one at every boundary, readers included (ruling 1, round 5):
    8 × ½ = 4 → 4 × ½ = 2 would lose content if the site were a split pair, so
    the site stays as stated and both readings are said."""
    assert (_atoms_per_cell(_OFF, 0.5), _atoms_per_cell(_ON, 0.5)) == (4.0, 2.0)
    structure = Structure(phases=[_phase(*_PNMA, _OFF, occ=0.5)])
    merged, found = _merge(structure)
    assert merged is structure
    (d,) = found
    assert d.code == "SITE_TWINS_KEPT" and d.value < 0.01
    assert "or at occupancy 1 if it is a split pair" in d.suggestion
    # the stated site holds the 4 atoms per cell it was stated with
    assert _counts(merged.phases[0])["Fe"] == 4


def test_the_cif_route_keeps_a_half_occupied_site_and_says_both_readings(tmp_path):
    """The CIF reader meets the same gate on its own channel."""
    path = tmp_path / "half.cif"
    path.write_text(
        "data_half\n_cell_length_a 7.0\n_cell_length_b 8.0\n_cell_length_c 6.0\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
        "_symmetry_space_group_name_H-M 'P n m a'\nloop_\n_atom_site_label\n"
        "_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n"
        "_atom_site_fract_z\n_atom_site_occupancy\nFe1 Fe 0.1 0.2501 0.3 0.5\n",
        encoding="utf-8")
    found: list = []
    structure = structure_from_cif(path, diagnostics=found)
    assert [d.code for d in found if "TWINS" in d.code] == ["SITE_TWINS_KEPT"]
    assert structure.phases[0].atoms[0].y.value == 0.2501
    (d,) = [d for d in found if d.code == "SITE_TWINS_KEPT"]
    assert d.where == ["phases.0.atoms.0"] and str(path) in d.message


def test_the_cif_route_merges_where_the_site_would_overfill(tmp_path):
    """The positive arm: at occupancy 1 the unmerged model puts two atoms at one place."""
    path = tmp_path / "full.cif"
    path.write_text(
        "data_full\n_cell_length_a 7.0\n_cell_length_b 8.0\n_cell_length_c 6.0\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
        "_symmetry_space_group_name_H-M 'P n m a'\nloop_\n_atom_site_label\n"
        "_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n"
        "_atom_site_fract_z\n_atom_site_occupancy\nFe1 Fe 0.1 0.2501 0.3 1.0\n",
        encoding="utf-8")
    found: list = []
    structure = structure_from_cif(path, diagnostics=found)
    (d,) = [d for d in found if d.code == "CIF_SITE_TWINS_MERGED"]
    assert "8 × 1 = 8 → 4 × 1 = 4." in d.message
    assert structure.phases[0].atoms[0].y.value == 0.25


def test_a_fully_occupied_site_names_no_split_pair():
    """The negative arm: at occupancy 1 the content line is there and the
    split-pair sentence is not — a pair of whole atoms 0.0016 Å apart is not a
    reading anyone holds."""
    _, found = _merge(Structure(phases=[_phase(*_PNMA, _OFF, occ=1.0)]))
    (d,) = found
    assert "8 × 1 = 8 → 4 × 1 = 4." in d.message
    assert "split pair" not in d.message + d.suggestion
    assert "more than 0.0005 (fractional) from the special position" in d.suggestion


def test_a_site_too_full_to_be_a_split_pair_names_none():
    """At occupancy 0.6 a pair 0.0016 Å apart would put 1.2 atoms in one place,
    so the content line is given and the split-pair sentence is not."""
    _, found = _merge(Structure(phases=[_phase(*_PNMA, _OFF, occ=0.6)]))
    (d,) = found
    assert "8 × 0.6 = 4.8 → 4 × 0.6 = 2.4." in d.message
    assert "split pair" not in d.message + d.suggestion


def test_the_reach_is_fractional_whatever_the_cell():
    """b = 20 Å and b = 5 Å take the same offset: 4e-4 merges, 6e-4 does not."""
    for b in (5.0, 20.0):
        for dy, expect in ((4e-4, True), (6e-4, False)):
            structure = Structure(phases=[_phase(
                "P n m a", (5.0, b, 6.0, 90, 90, 90), (0.1, 0.25 + dy, 0.3))])
            assert (_merge(structure)[0] is not structure) is expect, (b, dy)


def test_every_pair_the_merge_collapses_is_tested_not_only_the_closest():
    """Yue's case (#1014, round 4): Pmmm, a = b = 4 Å, c = 40 Å, (2e-4, 0.3, 0.0024).

    The images split by 0.0016 Å along x and 0.192 Å along z.  Collapsing the z pair
    would move z by 0.096 Å for the sake of the x pair, and the old rule did: it
    measured the nearest pair and merged the whole orbit.  Now only the pair within
    the reach is collapsed: x goes onto the plane, z stays as stated, and the 0.192 Å
    pair is left split.  The same site with z within the reach merges both."""
    cell = (4.0, 4.0, 40.0, 90, 90, 90)
    sg = resolve_group("P m m m", None)
    part = site_twin_merge(sg, cell, (2e-4, 0.3, 0.0024))
    assert part is not None and (part.before, part.after) == (8, 4)   # ITA: 4 images stay
    assert np.allclose(part.position, (0.0, 0.3, 0.0024), atol=1e-12)
    assert part.gap == pytest.approx(0.0016)
    merged = site_twin_merge(sg, cell, (2e-4, 0.3, 4e-4))
    assert merged is not None and (merged.before, merged.after) == (8, 2)
    assert np.allclose(merged.position, (0.0, 0.3, 0.0), atol=1e-12)
    assert merged.gap == pytest.approx(2 * 4e-4 * 40.0, rel=2e-3)   # the widest pair, not the x one


def test_a_rigid_body_atom_is_left_to_the_body(pbso4):
    """A body owns its atoms' positions; the merge never moves one."""
    from rietx.crystallography.bodies import body_from_atoms

    off = pbso4.model_copy(deep=True)
    (s2,) = [a for a in off.atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4
    body = body_from_atoms(off, ["S2", "O5", "O4"], "frag")
    doc = off.model_dump()
    doc["rigid_bodies"] = [body.model_dump()]
    structure = Structure(phases=[Phase.model_validate(doc)])
    merged, found = _merge(structure)
    assert merged is structure and not found


def test_site_twin_merge_takes_a_six_tuple_or_a_gemmi_cell():
    import gemmi

    sg = resolve_group("P n m a", None)
    xyz = (0.1, 0.25 + 1e-4, 0.3)
    a = site_twin_merge(sg, (7.0, 8.0, 6.0, 90, 90, 90), xyz)
    b = site_twin_merge(sg, gemmi.UnitCell(7.0, 8.0, 6.0, 90, 90, 90), xyz)
    assert a is not None and b is not None
    assert a.gap == pytest.approx(2e-4 * 8.0) and a.gap == b.gap
    assert np.array_equal(a.position, b.position)


# --------------------------------------------------------------- the readers


def test_the_cif_route_reports_on_its_own_channel_only(tmp_path):
    """A CIF read merges and says ``CIF_SITE_TWINS_MERGED``; nothing is left to move."""
    path = tmp_path / "hex.cif"
    path.write_text("""data_hex
_cell_length_a 5.0
_cell_length_b 5.0
_cell_length_c 8.0
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 120
_symmetry_space_group_name_H-M 'P 63/m m c'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Co1 Co 0.828 0.657 0.25 1
""", encoding="utf-8")
    diagnostics: list = []
    structure = structure_from_cif(path, diagnostics=diagnostics)
    assert [d.code for d in diagnostics].count("CIF_SITE_TWINS_MERGED") == 1
    merged, found = _merge(structure)
    assert merged is structure and not found


def _s2_off_the_mirror(text: str, y: str) -> str:
    """A written project file with only S2's y edited, as a hand edit would."""
    out = text.replace("0.0651619194267896 0.25 ", f"0.0651619194267896 {y} ", 1)
    out = out.replace("x @ 0.0651619194267896 y @ 0.25 ",
                      f"x @ 0.0651619194267896 y @ {y} ", 1)
    assert out != text
    return out


def test_a_fullprof_file_with_the_site_off_the_mirror_reads_four_sulfur(pbso4, tmp_path):
    """``Occ`` is m/M: S2's 0.5 is a 4c site, and the reader's ratio must say so."""
    from rietx.io.projects.fullprof import (
        read_fullprof_pcr,
        write_fullprof_pcr,
    )
    from rietx.io.projects.fullprof import to_structure as pcr_to_structure

    written = tmp_path / "on.pcr"
    write_fullprof_pcr(Structure(phases=[pbso4]), written)
    edited = tmp_path / "off.pcr"
    edited.write_text(_s2_off_the_mirror(written.read_text(encoding="utf-8"),
                                         "0.2501"), encoding="utf-8")
    found: list = []
    phase = pcr_to_structure(read_fullprof_pcr(edited), diagnostics=found).phases[0]
    assert [a.occ.value for a in phase.atoms] == [1.0] * 5
    assert _counts(phase)["S"] == 4 and _y(Structure(phases=[phase])) == 0.25
    (d,) = [d for d in found if d.code == "SITE_TWINS_MERGED"]
    assert str(edited) in d.message


def test_a_topas_file_with_the_site_off_the_mirror_reads_four_sulfur(pbso4, tmp_path):
    from rietx.io.projects import topas

    path = tmp_path / "off.inp"
    path.write_text(_s2_off_the_mirror(topas.from_structure(Structure(phases=[pbso4])),
                                       "0.2501"), encoding="utf-8")
    found: list = []
    phase = topas.to_structure(topas.read_topas_inp(path), diagnostics=found).phases[0]
    assert _counts(phase) == {"Pb": 4, "S": 4, "O": 16}
    assert [d.code for d in found].count("SITE_TWINS_MERGED") == 1
    # with no channel the same file still reads on the special position
    assert topas.to_structure(topas.read_topas_inp(path)).phases[0].atoms[1].y.value \
        == phase.atoms[1].y.value


def test_a_gsas2_project_with_the_site_off_the_mirror_reads_four_sulfur():
    import dataclasses

    model = read_gsas2_gpx(DATA / "gsas2_pbso4.gpx")
    phase = model.phases[0]
    atoms = tuple(dataclasses.replace(a, y=a.y + 1e-4) if a.label == "S2" else a
                  for a in phase.atoms)
    model = dataclasses.replace(
        model, phases=(dataclasses.replace(phase, atoms=atoms),) + model.phases[1:])
    found: list = []
    structure = to_structure(model, diagnostics=found)
    assert _counts(structure.phases[0])["S"] == 4 and _y(structure) == 0.25
    assert [d.code for d in found].count("SITE_TWINS_MERGED") == 1


# ------------------------------------------------------------- stored history


def _tree_with_s2_stored_off_the_mirror(tmp_path, pbso4, data) -> Path:
    """A history log whose nodes all store S2 at y = 0.2501, as a script or an old release left it."""
    path = tmp_path / "h.jsonl"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=path)
    ref.run_stage(data, Stage("scale", ["phases.*.scale"]))
    ref.run_stage(data, Stage("scale2", ["phases.*.scale"]))
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        node = doc.get("node")
        if node is not None:
            for atom in node["state"]["structure"]["phases"][0]["atoms"]:
                if atom["label"] == "S2":
                    atom["y"]["value"] = 0.2501
        lines.append(json.dumps(doc))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def pattern(pbso4) -> PatternData:
    return _pattern(Structure(phases=[pbso4]))


def test_a_history_stored_off_the_mirror_reports_the_move_once_on_load(
        tmp_path, pbso4, pattern):
    path = _tree_with_s2_stored_off_the_mirror(tmp_path, pbso4, pattern)
    found: list = []
    tree = RefinementTree.load(path, diagnostics=found)
    assert len(tree) >= 3
    (d,) = [d for d in found if d.code == "SITE_TWINS_MERGED"]
    assert f"stored in {len(tree)} nodes" in d.message
    for node_id in tree.order:
        assert _y(tree[node_id].state.structure) == pytest.approx(0.25, abs=1e-12)
    # the move is in the tree now: a second look at the loaded states finds nothing
    assert not _merge(tree[tree.order[-1]].state.structure)[1]


# ---------------------------------------------------------------- the verbs


def test_a_coordinate_assigned_after_construction_is_merged_and_reported_on_run_stage(
        pbso4, pattern):
    structure = Structure(phases=[pbso4.model_copy(deep=True)])
    (s2,) = [a for a in structure.phases[0].atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4                       # after the Structure was built
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    assert _y(ref.structure) == 0.25 and s2.y.value == 0.25 + 1e-4  # caller's object untouched
    result = ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_MERGED") == 1
    # said once: the next result carries nothing new
    again = ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    assert "SITE_TWINS_MERGED" not in [d.code for d in again.diagnostics]


def test_a_coordinate_assigned_after_construction_is_reported_on_fit(pbso4, pattern):
    structure = Structure(phases=[pbso4.model_copy(deep=True)])
    (s2,) = [a for a in structure.phases[0].atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        Stage("scale", ["phases.*.scale"], max_iter=5)]))
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_MERGED") == 1


def test_edit_merges_the_proposed_structure_and_reports_it(pbso4, pattern):
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT)
    ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    ref.edit(structure=Structure(phases=[_moved(pbso4, "S2", y=1e-4)]))
    assert _y(ref.structure) == 0.25
    assert _y(ref.history[ref.history.head].state.structure) == 0.25
    result = ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_MERGED") == 1


def test_set_values_next_to_the_mirror_merges_and_reports(pbso4, pattern):
    """A general oxygen (O5) whose DOF puts y at 0.2501 (Pnma 8d → 4c) counts as one atom.

    A coordinate is tied to its Wyckoff DOF, so ``set_values`` reaches it
    through ``dof.1``; the verb moves the site and the next result says so.
    """
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT)
    j = [a.label for a in ref.structure.phases[0].atoms].index("O5")
    assert _multiplicity(ref.structure.phases[0], "O5") == 8
    y0 = _y(ref.structure, "O5")
    ref.set_values({f"phases.0.atoms.{j}.dof.1": 0.2501 - y0})
    assert _y(ref.structure, "O5") == 0.25
    assert _multiplicity(ref.structure.phases[0], "O5") == 4
    result = ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_MERGED") == 1


def test_checkout_of_a_node_stored_off_the_mirror_merges_and_reports(pbso4, pattern):
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT)
    ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    state = ref.snapshot()
    (s2,) = [a for a in state.structure.phases[0].atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4
    node = ref.history.add(parents=[ref.history.head],
                           action=rx.schemas.history.NodeAction(kind="edit_model"),
                           state=state)
    ref.checkout(node.id)
    assert _y(ref.structure) == 0.25
    result = ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_MERGED") == 1


def test_replay_of_a_node_stored_off_the_mirror_merges_and_reports(pbso4, pattern):
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT)
    ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    state = ref.snapshot()
    (s2,) = [a for a in state.structure.phases[0].atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4
    node = ref.history.add(parents=[ref.history.head],
                           action=rx.schemas.history.NodeAction(kind="edit_model"),
                           state=state)
    result = replay(ref.history, node.id, pattern)
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_MERGED") == 1


def test_a_joint_fit_merges_its_structure_and_reports_it(pbso4):
    structure = Structure(phases=[pbso4.model_copy(deep=True)])
    (s2,) = [a for a in structure.phases[0].atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4
    joint = rx.MultiHistogramRefinement(structure, [INSTRUMENT, INSTRUMENT])
    assert all(_y(s) == 0.25 for s in joint.fitted_structures)
    assert [d.code for d in joint._twin_findings] == ["SITE_TWINS_MERGED"]


def _predict(structure: Structure) -> np.ndarray:
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    return np.asarray(ref.predict(np.arange(10.0, 120.0, 0.05)))


def test_predict_on_the_merged_site_equals_the_site_stated_on_the_mirror(pbso4):
    on = Structure(phases=[pbso4])
    off = Structure(phases=[_moved(pbso4, "S2", y=1e-4)])
    a, b = _predict(on), _predict(off)
    assert np.max(np.abs(a - b)) / np.max(a) < 1e-12


# ------------------------------------------------ round 3: the ruling on #1014
#
# Where occupancy × (images before / images after) is at most 1, a model-side
# boundary (``RefinementTree.load``, a ``Refinement`` verb) leaves the site as
# stored and says ``SITE_TWINS_KEPT``; above 1 it merges; a file reader merges
# at any occupancy.  Expected counts below come from ``site_orbit`` (ITA vol. A),
# never from the merge.


def _half_pnma() -> Structure:
    return Structure(phases=[_phase(*_PNMA, _OFF, occ=0.5)])


def _half_pnma_pattern() -> PatternData:
    return _pattern(Structure(phases=[_phase(*_PNMA, _ON, occ=0.5)]))


def test_a_refinement_leaves_a_half_occupied_site_and_names_both_readings():
    ref = rx.Refinement(_half_pnma(), INSTRUMENT, history=False)
    assert _y(ref.structure, "X") == _OFF[1]                       # nothing moved
    assert _multiplicity(ref.structure.phases[0], "X") == 8
    result = ref.run_stage(_half_pnma_pattern(), Stage("scale", ["phases.*.scale"]))
    codes = [d.code for d in result.diagnostics]
    assert codes.count("SITE_TWINS_KEPT") == 1 and "SITE_TWINS_MERGED" not in codes
    (d,) = [d for d in result.diagnostics if d.code == "SITE_TWINS_KEPT"]
    assert d.level == "warning" and d.where == ["phases.0.atoms.0"]
    assert d.value == pytest.approx(2e-4 * 8.0)
    assert "nothing was moved" in d.message
    # one atom off its position: 4 × 0.5 = 2 there; a split pair: 8 × 0.5 = 4 as stored
    assert _atoms_per_cell(_ON, 0.5) == 2.0 and _atoms_per_cell(_OFF, 0.5) == 4.0
    assert "4 × 0.5 = 2" in d.message and "8 × 0.5 = 4" in d.message
    assert "4 × 1 = 4" in d.message
    assert "occupancy 0.5 if it is one atom" in d.suggestion
    assert "occupancy 1 if it is a split pair" in d.suggestion
    # said once: the next result carries nothing new
    again = ref.run_stage(_half_pnma_pattern(), Stage("scale", ["phases.*.scale"]))
    assert "SITE_TWINS_KEPT" not in [d.code for d in again.diagnostics]


def test_edit_leaves_a_half_occupied_site_and_checkout_says_it_once():
    ref = rx.Refinement(Structure(phases=[_phase(*_PNMA, _ON, occ=0.5)]),
                        INSTRUMENT)
    ref.edit(structure=_half_pnma())
    ref.edit(structure=_half_pnma())                       # a second verb, same site
    assert _y(ref.structure, "X") == _OFF[1]
    result = ref.run_stage(_half_pnma_pattern(), Stage("scale", ["phases.*.scale"]))
    assert [d.code for d in result.diagnostics].count("SITE_TWINS_KEPT") == 1


def test_a_refinement_still_merges_where_the_site_would_overfill():
    """The positive control: at occupancy 0.6, 8 × 0.6 on a mirror puts 1.2 atoms in one place."""
    structure = Structure(phases=[_phase(*_PNMA, _OFF, occ=0.6)])
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    assert _y(ref.structure, "X") == 0.25
    assert [d.code for d in ref._twin_findings] == ["SITE_TWINS_MERGED"]


def test_a_file_reader_keeps_a_half_occupied_site():
    merged, found = _merge(_half_pnma())
    assert _y(merged, "X") == _OFF[1]
    assert [d.code for d in found] == ["SITE_TWINS_KEPT"]


def test_a_history_stored_with_a_half_occupied_site_keeps_it_and_says_so_once(tmp_path):
    path = tmp_path / "half.jsonl"
    ref = rx.Refinement(Structure(phases=[_phase(*_PNMA, _ON, occ=0.5)]),
                        INSTRUMENT, history=path)
    data = _half_pnma_pattern()
    ref.run_stage(data, Stage("scale", ["phases.*.scale"]))
    ref.run_stage(data, Stage("scale2", ["phases.*.scale"]))
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        if doc.get("node") is not None:
            doc["node"]["state"]["structure"]["phases"][0]["atoms"][0]["y"]["value"] = _OFF[1]
        lines.append(json.dumps(doc))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    found: list = []
    tree = RefinementTree.load(path, diagnostics=found)
    assert [d.code for d in found] == ["SITE_TWINS_KEPT"]
    assert f"stored in {len(tree)} nodes" in found[0].message
    for node_id in tree.order:
        assert _y(tree[node_id].state.structure, "X") == _OFF[1]


def test_the_load_warning_is_one_per_site_when_every_node_stores_another_coordinate(
        tmp_path, pbso4, pattern):
    """A refined log differs in the coordinate node by node; the finding is still one."""
    path = tmp_path / "refined.jsonl"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=path)
    ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    ref.run_stage(pattern, Stage("scale2", ["phases.*.scale"]))
    lines, k = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        if doc.get("node") is not None:
            k += 1
            for atom in doc["node"]["state"]["structure"]["phases"][0]["atoms"]:
                if atom["label"] == "S2":
                    atom["y"]["value"] = 0.25 + 1e-4 + 1e-5 * k  # another one each node
        lines.append(json.dumps(doc))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    found: list = []
    tree = RefinementTree.load(path, diagnostics=found)
    (d,) = [d for d in found if d.code == "SITE_TWINS_MERGED"]
    assert k == len(tree) >= 3 and f"stored in {k} nodes" in d.message


# a coordinate the merge fixes must not stop the model opening (Yue, #1014 item 2)


def test_a_merged_centre_loses_vary_and_its_table_builds():
    """P-1 1a: ``fix_special_positions`` would clear ``vary``; so does the merge."""
    from rietx.params.vector import ParameterTable
    phase = _phase("P -1", (5.0, 6.0, 7.0, 80, 85, 95), (3e-4, -3e-4, 4e-4))
    for atom in phase.atoms:
        for axis in "xyz":
            getattr(atom, axis).vary = True
    structure = Structure(phases=[phase])
    merged, found = _merge(structure)
    (a,) = merged.phases[0].atoms
    assert not any(getattr(a, axis).vary for axis in "xyz")
    assert all(getattr(structure.phases[0].atoms[0], axis).vary for axis in "xyz")
    (d,) = found
    assert "vary=False" in d.message
    ParameterTable(merged, INSTRUMENT)                     # no "fully fixed special position"


def test_a_merged_mirror_site_keeps_the_vary_of_its_free_coordinates():
    """The negative arm: Pnma 4c still moves in x and z, so nothing is cleared."""
    phase = _phase(*_PNMA, _OFF)
    for axis in "xyz":
        getattr(phase.atoms[0], axis).vary = True
    merged, found = _merge(Structure(phases=[phase]))
    (a,) = merged.phases[0].atoms
    assert a.x.vary and a.y.vary and a.z.vary
    assert "vary=False" not in found[0].message


def test_a_merged_site_with_an_anisotropic_tensor_is_projected_and_its_table_builds():
    """Pnma 4c allows U11, U22, U33, U13 only; U12 and U23 were free at 8c."""
    from rietx.params.vector import ParameterTable
    from rietx.schemas import AnisoU
    phase = _phase(*_PNMA, _OFF)
    u = dict(u11=0.010, u22=0.012, u33=0.011, u12=3e-4, u13=1e-3, u23=2e-4)
    phase.atoms[0].aniso = AnisoU(**{k: Parameter(value=v, vary=True) for k, v in u.items()})
    structure = Structure(phases=[phase])
    merged, found = _merge(structure)
    t = merged.phases[0].atoms[0].aniso
    assert (t.u12.value, t.u23.value) == (0.0, 0.0)
    assert (t.u11.value, t.u22.value, t.u33.value, t.u13.value) == (0.010, 0.012, 0.011, 1e-3)
    assert structure.phases[0].atoms[0].aniso.u12.value == 3e-4      # caller's untouched
    assert "projected" in found[0].message
    ParameterTable(merged, INSTRUMENT)


def test_a_tensor_already_allowed_is_not_touched_nor_mentioned():
    from rietx.schemas import AnisoU
    phase = _phase(*_PNMA, _OFF)
    phase.atoms[0].aniso = AnisoU(
        u11=Parameter(value=0.01), u22=Parameter(value=0.012), u33=Parameter(value=0.011))
    _, found = _merge(Structure(phases=[phase]))
    assert "projected" not in found[0].message


def test_the_suggestions_read_the_reach_constant(monkeypatch):
    """A retune cannot leave the advice stale: the figure comes from the constant."""
    import rietx.crystallography.twins as twins
    monkeypatch.setattr(twins, "TWIN_COORD_TOL", 0.0003)
    _, merged = _merge(Structure(phases=[_phase(*_PNMA, _OFF, occ=1.0)]))
    assert "0.0003 (fractional)" in merged[0].suggestion and "0.0005" not in merged[0].suggestion
    kept: list = []
    merge_site_twins(_half_pnma(), diagnostics=kept)
    assert "0.0003 (fractional)" in kept[0].suggestion and "0.0005" not in kept[0].suggestion


# ------------------------------------------------ round 4: Yue's review at e18006a7


def _o5(pbso4) -> int:
    return [a.label for a in pbso4.atoms].index("O5")


def test_a_hold_follows_its_direction_through_the_dof_renumbering(pbso4):
    """O5 (Pnma 8d → 4c on y = ¼): DOFs x, y, z become x, z.  Held y is dropped and
    said; held z follows to ``dof.1`` instead of freezing z by accident of its number."""
    j = _o5(pbso4)
    site = f"phases.0.atoms.{j}"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=False)
    ref.hold([f"{site}.dof.1", f"{site}.dof.2"])         # y and z on the general position
    ref.set_values({f"{site}.dof.1": 0.2501 - pbso4.atoms[j].y.value})   # y → 0.2501
    assert _y(ref.structure, "O5") == 0.25
    assert ref._user_holds == {f"{site}.dof.1"}          # was dof.2: z
    rows = {r.path: r for r in ref.parameters()}
    assert rows[f"{site}.dof.1"].held_because and not rows[f"{site}.dof.0"].held_because
    (d,) = [d for d in ref._twin_findings if d.code == "SITE_TWINS_MERGED"]
    assert f"the hold on {site}.dof.1 was dropped" in d.message
    assert f"the hold on {site}.dof.2 now reads {site}.dof.1" in d.message


def test_a_tie_on_a_renumbered_dof_follows_it_or_is_dropped(pbso4):
    j = _o5(pbso4)
    site = f"phases.0.atoms.{j}"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=False)
    ref.tie(f"{site}.dof.2", f"{site}.dof.0")            # z follows x
    ref.set_values({f"{site}.dof.1": 0.2501 - pbso4.atoms[j].y.value})
    assert list(ref._ties) == [f"{site}.dof.1"]          # the tie on z, renumbered
    assert ref._ties[f"{site}.dof.1"].sources == [f"{site}.dof.0"]
    rows = {r.path: r for r in ref.parameters()}
    assert rows[f"{site}.dof.1"].tie is not None


def test_a_tie_on_the_direction_the_position_fixes_is_dropped_and_said(pbso4):
    j = _o5(pbso4)
    site = f"phases.0.atoms.{j}"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=False)
    ref.tie(f"{site}.dof.2", f"{site}.dof.1")            # z follows y
    ref.set_values({f"{site}.dof.1": 0.2501 - pbso4.atoms[j].y.value})
    assert not ref._ties
    (d,) = [d for d in ref._twin_findings if d.code == "SITE_TWINS_MERGED"]
    assert f"the tie on {site}.dof.2 was dropped" in d.message


def test_a_stored_history_carries_its_holds_through_the_merge(tmp_path, pbso4, pattern):
    """The load route: a node recorded with a hold on z, its site stored off the mirror."""
    j = _o5(pbso4)
    site = f"phases.0.atoms.{j}"
    path = tmp_path / "held.jsonl"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=path)
    ref.hold([f"{site}.dof.2"])
    ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        if doc.get("node") is not None:
            doc["node"]["state"]["structure"]["phases"][0]["atoms"][j]["y"]["value"] = 0.2501
        lines.append(json.dumps(doc))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tree = RefinementTree.load(path)
    holds = {h for nid in tree.order for h in tree[nid].state.holds}
    assert holds == {f"{site}.dof.1"}


def _shared_site(occ_fe: float, occ_mn: float) -> Structure:
    phase = _phase(*_PNMA, _OFF, occ=occ_fe)
    twin = phase.atoms[0].model_copy(deep=True)
    twin.label, twin.species = "Y", "Mn"
    twin.occ = Parameter(value=occ_mn)
    return Structure(phases=[phase.model_copy(update={"atoms": [phase.atoms[0], twin]})])


def test_the_occupancy_gate_sums_the_atoms_sharing_a_site():
    """Fe 0.5 + Mn 0.5 on one site, 8 → 4: each passes the gate alone (0.5 × 2 = 1),
    but the position holds (0.5 + 0.5) × 2 = 2 atoms, so both merge."""
    ref = rx.Refinement(_shared_site(0.5, 0.5), INSTRUMENT, history=False)
    assert [d.code for d in ref._twin_findings] == ["SITE_TWINS_MERGED"] * 2
    assert {a.y.value for a in ref.structure.phases[0].atoms} == {0.25}


def test_a_shared_site_that_still_fits_is_kept_as_stored():
    """The negative arm: 0.25 + 0.25 gives (0.5) × 2 = 1, a split pair is possible."""
    ref = rx.Refinement(_shared_site(0.25, 0.25), INSTRUMENT, history=False)
    assert [d.code for d in ref._twin_findings] == ["SITE_TWINS_KEPT"] * 2
    assert {a.y.value for a in ref.structure.phases[0].atoms} == {_OFF[1]}


def test_the_adp_projection_of_a_merge_is_positive_definite_and_allowed():
    """P6/mmm 6j, (x, 0, 0) stated 3e-4 off: the merge's group average of a
    positive-definite tensor stays positive definite for every tensor (a
    least-squares projection in the six components failed 1.3 % of them) and
    lies in the allowed subspace, so the table builds."""
    from rietx.crystallography.adp import is_positive_definite
    from rietx.params.vector import ParameterTable
    from rietx.schemas import AnisoU

    rng = np.random.default_rng(1014)
    bad = 0
    for k in range(1500):
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        w = np.exp(rng.uniform(0.0, np.log(20.0), size=3)) * 0.01
        u = q @ np.diag(w) @ q.T
        u6 = dict(u11=u[0, 0], u22=u[1, 1], u33=u[2, 2], u12=u[0, 1], u13=u[0, 2], u23=u[1, 2])
        phase = _phase("P 6/m m m", (5.0, 5.0, 8.0, 90, 90, 120),
                       (0.3, 3e-4, -2e-4))
        phase.atoms[0].aniso = AnisoU(**{n: Parameter(value=float(v)) for n, v in u6.items()})
        merged, found = _merge(Structure(phases=[phase]))
        assert found, k
        t = merged.phases[0].atoms[0].aniso
        vals = [t.u11.value, t.u22.value, t.u33.value, t.u12.value, t.u13.value, t.u23.value]
        bad += not is_positive_definite(vals)
        if k < 20:
            ParameterTable(merged, INSTRUMENT)
    assert bad == 0


# ------------------------------------------------ round 5: Yue's review at 7b9a18b4


@pytest.mark.parametrize("z, after", [
    (5.0e-4, 2), (6.0e-4, 4), (7.0e-4, 4), (8.0e-4, 4), (2.4e-3, 4)])
def test_the_partial_merge_does_not_switch_off_when_a_second_coordinate_is_further_out(z, after):
    """P m m m, c = 40 Å, (2e-4, 0.3, z): x is within reach throughout, z only up
    to 5e-4.  Past it the z operation is dropped and x still merges (8 → 4)."""
    sg = resolve_group("P m m m", None)
    merge = site_twin_merge(sg, (4.0, 4.0, 40.0, 90, 90, 90), np.array([2e-4, 0.3, z]))
    assert merge is not None and (merge.before, merge.after) == (8, after)
    assert merge.position[0] == pytest.approx(0.0, abs=1e-12)
    assert merge.position[2] == pytest.approx(0.0 if after == 2 else z, abs=1e-12)


def test_a_group_that_cannot_close_on_the_kept_operations_merges_nothing():
    """The negative arm: both coordinates beyond the reach leave the site alone."""
    sg = resolve_group("P m m m", None)
    assert site_twin_merge(sg, (4.0, 4.0, 40.0, 90, 90, 90),
                           np.array([6e-4, 0.3, 7e-4])) is None


def test_every_rotation_in_gemmis_settings_has_row_sums_of_at_most_two():
    """Pins ``_TWIN_SEARCH_FACTOR``: |(R − I)d| ≤ 3|d| because |row sum of R| ≤ 2."""
    import gemmi
    worst = 0
    for sg in gemmi.spacegroup_table():
        for op in resolve_group(sg.xhm(), None).operations():
            rot = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
            worst = max(worst, np.abs(rot).sum(axis=1).max())
    assert worst <= 2.0 + 1e-12


def _o5_state(pbso4):
    j = _o5(pbso4)
    site = f"phases.0.atoms.{j}"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=False)
    return ref, j, site


def _z_dofs(ref, j) -> list[int]:
    """Indices of the DOFs of atom j whose direction is z, in the model as it is now."""
    sg = resolve_group(ref.structure.phases[0].space_group, None)
    a = ref.structure.phases[0].atoms[j]
    from rietx.crystallography.wyckoff import coordinate_basis, stabilizer_rotations
    basis = coordinate_basis(stabilizer_rotations(
        sg, np.array([a.x.value, a.y.value, a.z.value])))
    return [k for k, v in enumerate(basis) if np.allclose(np.abs(v), (0, 0, 1))]


def _drift_y(ref, j, y):
    """A coordinate written as a stage writes it back: into the model, merging nothing."""
    ref.structure.phases[0].atoms[j].y.value = y


def test_a_branch_and_a_trial_carry_the_constraints_through_their_own_merge(pbso4):
    ref, j, site = _o5_state(pbso4)
    ref.hold([f"{site}.dof.1"])                          # y
    ref.tie(f"{site}.dof.2", f"{site}.dof.0")            # z follows x
    _drift_y(ref, j, 0.2502)
    for make in (lambda r: r._trial(record=False), lambda r: r._trial()):
        other = make(ref)
        assert _y(other.structure, "O5") == 0.25
        assert other._user_holds == set()                # y is fixed on the mirror
        assert list(other._ties) == [f"{site}.dof.1"]    # z is dof.1 there
        assert other._ties[f"{site}.dof.1"].sources == [f"{site}.dof.0"]
        assert _z_dofs(other, j) == [1]


def test_an_instrument_edit_keeps_a_user_tie_on_a_site_a_fit_left_near_the_mirror(pbso4):
    ref, j, site = _o5_state(pbso4)
    ref.tie(f"{site}.dof.2", f"{site}.dof.0")
    _drift_y(ref, j, 0.2502)
    ref.edit(instrument=ref.instrument.model_copy(deep=True))
    assert ref._ties, "the tie fell off in an edit that touched only the instrument"
    rows = {r.path: r for r in ref.parameters()}
    assert any(r.tie is not None for p, r in rows.items() if p.startswith(site))


def test_an_edit_reads_the_old_numbering_off_the_current_model_not_the_candidate(pbso4):
    """O5 on the mirror: DOFs x, z; a hold on ``dof.1`` is z.  An edit moving it to
    y = 0.2502 merges it back onto the mirror, so z stays held and nothing is dropped."""
    ref, j, site = _o5_state(pbso4)
    ref.set_values({f"{site}.dof.1": 0.25 - pbso4.atoms[j].y.value})   # y onto the mirror
    assert _z_dofs(ref, j) == [1]
    ref.hold([f"{site}.dof.1"])
    candidate = ref.structure.model_copy(deep=True)
    candidate.phases[0].atoms[j].y.value = 0.2502
    ref.edit(structure=candidate)
    assert ref._user_holds == {f"{site}.dof.1"}
    assert not any("dropped" in d.message for d in ref._twin_findings)


@pytest.mark.parametrize("y", [0.25004, 0.2501])
def test_a_site_that_becomes_special_without_a_merge_carries_its_constraints(pbso4, y):
    """5e-5 of the mirror ``site_orbit`` already counts the site as special, so no
    merge fires, but the DOFs still renumber."""
    ref, j, site = _o5_state(pbso4)
    ref.hold([f"{site}.dof.1", f"{site}.dof.2"])
    ref.set_values({f"{site}.dof.1": y - pbso4.atoms[j].y.value})
    assert ref._user_holds == {f"{site}.dof.1"}          # z, renumbered; y's hold dropped
    assert _z_dofs(ref, j) == [1]
    said = [d for d in ref._twin_findings
            if d.code in ("SITE_TWINS_MERGED", "SITE_DOFS_RENUMBERED")]
    assert said and any("dropped" in d.message for d in said)


def test_a_loaded_history_keeps_the_constraints_note_when_only_later_nodes_hold_it(
        tmp_path, pbso4, pattern):
    j = _o5(pbso4)
    site = f"phases.0.atoms.{j}"
    path = tmp_path / "held.jsonl"
    ref = rx.Refinement(Structure(phases=[pbso4]), INSTRUMENT, history=path)
    ref.run_stage(pattern, Stage("scale", ["phases.*.scale"]))
    ref.hold([f"{site}.dof.1"])                          # y, held after the first stage
    ref.run_stage(pattern, Stage("scale2", ["phases.*.scale"]))
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        if doc.get("node") is not None:
            doc["node"]["state"]["structure"]["phases"][0]["atoms"][j]["y"]["value"] = 0.2501
        lines.append(json.dumps(doc))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    found: list = []
    RefinementTree.load(path, diagnostics=found)
    (d,) = [d for d in found if d.code == "SITE_TWINS_MERGED" and d.where == [site]]
    assert f"Constraints: the hold on {site}.dof.1 was dropped" in d.message
    assert d.message.count("Constraints:") == 1


@pytest.mark.parametrize("dx", [0.0, 1e-5, 2e-4])
def test_co_occupants_are_grouped_at_the_merges_own_reach(dx):
    """Fe and Mn at 0.5 each, the second ``dx`` along x: one place to within the reach."""
    structure = _shared_site(0.5, 0.5)
    atoms = list(structure.phases[0].atoms)
    atoms[1] = atoms[1].model_copy(update={"x": Parameter(value=_OFF[0] + dx)})
    structure = Structure(phases=[structure.phases[0].model_copy(update={"atoms": atoms})])
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    assert [d.code for d in ref._twin_findings] == ["SITE_TWINS_MERGED"] * 2
    assert {a.y.value for a in ref.structure.phases[0].atoms} == {0.25}


def test_co_occupants_further_apart_than_the_reach_are_not_one_place():
    structure = _shared_site(0.5, 0.5)
    atoms = list(structure.phases[0].atoms)
    atoms[1] = atoms[1].model_copy(update={"x": Parameter(value=_OFF[0] + 2e-3)})
    structure = Structure(phases=[structure.phases[0].model_copy(update={"atoms": atoms})])
    _, found = _merge(structure)
    assert [d.code for d in found] == ["SITE_TWINS_KEPT"] * 2


def _route_set_values(ref, j, site, y0):
    ref.set_values({f"{site}.dof.1": 0.25004 - y0})
    return ref


def _route_set_values_merge(ref, j, site, y0):
    ref.set_values({f"{site}.dof.1": 0.2501 - y0})
    return ref


def _route_write_back(ref, j, site, y0):
    table = ref._working_table()
    {e.path: e for e in table.entries}[f"{site}.dof.1"].value = 0.25004 - y0
    table.refresh_ties()
    ref._write_back(table)
    return ref


def _route_edit_structure(ref, j, site, y0):
    candidate = ref.structure.model_copy(deep=True)
    candidate.phases[0].atoms[j].y.value = 0.2502
    ref.edit(structure=candidate)
    return ref


def _route_edit_instrument(ref, j, site, y0):
    _drift_y(ref, j, 0.2502)
    ref.edit(instrument=ref.instrument.model_copy(deep=True))
    return ref


def _route_branch(ref, j, site, y0):
    _drift_y(ref, j, 0.2502)
    return ref._trial()


def _route_trial(ref, j, site, y0):
    _drift_y(ref, j, 0.2502)
    return ref._trial(record=False)


@pytest.mark.parametrize("route", [
    _route_set_values, _route_set_values_merge, _route_write_back,
    _route_edit_structure, _route_edit_instrument, _route_branch, _route_trial])
def test_every_route_keeps_a_hold_on_z_and_a_tie_to_it_on_z(pbso4, route):
    """The class pin (round 5, items 2-6): a hold on z and a tie from x to z on a
    near-special site, through every route that can move the site — z stays held
    and the tie's source is still z."""
    ref, j, site = _o5_state(pbso4)
    ref.hold([f"{site}.dof.2"])                          # z on the general position
    ref.tie(f"{site}.dof.0", f"{site}.dof.2")            # x follows z
    out = route(ref, j, site, pbso4.atoms[j].y.value)
    (k,) = _z_dofs(out, j)
    assert out._user_holds == {f"{site}.dof.{k}"}
    assert [s for s, _ in out._ties[f"{site}.dof.0"].terms] == [f"{site}.dof.{k}"]
