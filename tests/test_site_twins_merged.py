"""A site whose own images coincide is one atom at every boundary that can say so (#1007).

``site_orbit`` snaps a site within ``SITE_TOL`` (1e-4, fractional) of a special
position, and on a mirror that is 5e-5 of the coordinate, because the test
compares the 2δ displacement.  PbSO₄'s S2 (``tests/data/gsas2_pbso4.gpx``, Pnma
4c on the mirror at y = ¼) moved 6e-5 off it is a general position: two images
0.0006 Å apart, 8 S in a cell of 4.  #765 merged such twins for a CIF read; the
same rule (``symmetry.site_twin_merge``, 0.02 Å) now runs at the boundaries that
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
    TWIN_DISTANCE,
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


@pytest.mark.parametrize("dy", [6e-5, 1e-4, 1e-3])
def test_issue_reproducer_counts_four_sulfur(pbso4, dy):
    """#1007's reproducer, verbatim in its core: raw coordinates into ``phase_zmv``."""
    atoms = [(a.species, a.x.value, a.y.value + (dy if a.label == "S2" else 0),
              a.z.value, a.occ.value) for a in pbso4.atoms]
    c = phase_zmv(pbso4.space_group, pbso4.cell.lengths_angles(), atoms).element_counts
    assert (c["Pb"], c["S"], c["O"]) == (4, 4, 16)      # PbSO₄, Z = 4


@pytest.mark.parametrize("dy", [6e-5, 1e-4, 1e-3])
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
    assert "puts 8 atoms" in d.message and d.message.endswith("4 atoms")


def test_phase_validation_is_strict_and_moves_nothing(pbso4):
    """The schema has no diagnostics channel, so it holds the coordinate as stated."""
    phase = _moved(pbso4, "S2", y=1e-4)
    assert _y(Structure(phases=[phase])) == pytest.approx(0.25 + 1e-4, abs=1e-15)
    assert _multiplicity(phase, "S2") == 8
    again = Phase.model_validate_json(phase.model_dump_json())
    assert again.model_dump() == phase.model_dump()


@pytest.mark.parametrize("dy", [4e-3, 1e-2])
def test_images_further_apart_than_the_twin_distance_stay_general(pbso4, dy):
    """The negative arm: 2·dy·b = 0.043 Å and 0.108 Å are real offsets."""
    assert 2 * dy * pbso4.cell.b.value > TWIN_DISTANCE
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
    assert len(found) == 1 and f"{general} atoms" in found[0].message


def test_a_split_site_is_left_split():
    """Images 0.2 Å apart at half occupancy are a split site, never twins."""
    dy = 0.1 / 8.0                                         # 2·dy·b = 0.2 Å
    structure = Structure(phases=[_phase(
        "P n m a", (7.0, 8.0, 6.0, 90, 90, 90), (0.1, 0.25 + dy, 0.3), occ=0.5)])
    merged, found = _merge(structure)
    assert merged is structure and not found


def test_the_distance_decides_not_the_fractional_reach():
    """b = 20 Å, a = 5 Å: 2·dy = 0.003 is inside the 0.02/5 reach, 2·dy·b = 0.06 Å is not."""
    dy = 1.5e-3
    assert 2 * dy < TWIN_DISTANCE / 5.0 and 2 * dy * 20.0 > TWIN_DISTANCE
    structure = Structure(phases=[_phase(
        "P n m a", (5.0, 20.0, 6.0, 90, 90, 90), (0.1, 0.25 + dy, 0.3))])
    assert _merge(structure)[0] is structure


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
