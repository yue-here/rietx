"""A restraint follows its atoms when an edit renumbers them (WP-2121).

A soft restraint names its atoms by position in ``Phase.atoms``
(``atom_i``/``atom_j``/``atom_k``, ``atoms``, or a ``ValueRestraint.path``).
``Refinement.edit`` already read the holds and ties it keeps into a new atom
numbering (#1264), but restraints live on the structure, so an edit that
swapped two atoms left a bond restraint on two other atoms with nothing said,
and one that removed a restrained atom was accepted and the next fit raised
``IndexError``.  On PbSO₄ (Pb1 S2 O3 O4 O5, ``tests/data/gsas2_pbso4.gpx``)
each kind is moved by a swap and by a removal ahead of it, and dropped, with a
warning, when its own atom goes.

The candidate is built the way a caller builds one: a deep copy of the
working structure changed in place.  Assigning a new ``atoms`` list re-runs
the phase validators (``validate_assignment``), so the silent routes were an
in-place swap or ``del``, which these tests use.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.gui import textdoc as td
from rietx.io.projects.gsas2 import read_gsas2_gpx, to_structure
from rietx.model.forward import compile_model
from rietx.schemas import PatternData, Structure
from rietx.schemas.structure import (
    AngleRestraint,
    AntiBumpRestraint,
    BondRestraint,
    PlanarityRestraint,
    TetherRestraint,
    TorsionRestraint,
    ValueRestraint,
)

DATA = Path(__file__).parent / "data"
INSTRUMENT = rx.Instrument.constant_wavelength_neutron(1.5)
LABELS = ["Pb1", "S2", "O3", "O4", "O5"]


@pytest.fixture(scope="module")
def pbso4() -> rx.Phase:
    return to_structure(read_gsas2_gpx(DATA / "gsas2_pbso4.gpx")).phases[0]


def _restraint(kind: str, on: list[str]):
    """A restraint of ``kind`` on the atoms labelled ``on``, numbered as PbSO₄ lists them."""
    j = [LABELS.index(label) for label in on]
    if kind == "bond":
        return BondRestraint(atom_i=j[0], atom_j=j[1], target=1.47, sigma=0.01)
    if kind == "tether":
        return TetherRestraint(atom_i=j[0], atom_j=j[1], max_distance=1.6, sigma=0.01)
    if kind == "anti-bump":
        return AntiBumpRestraint(atom_i=j[0], atom_j=j[1], min_distance=1.2, sigma=0.01)
    if kind == "angle":
        return AngleRestraint(atom_i=j[0], atom_j=j[1], atom_k=j[2], target_deg=109.5,
                              sigma=1.0)
    if kind == "planarity":
        return PlanarityRestraint(atoms=j, sigma=0.01)
    if kind == "torsion":
        return TorsionRestraint(atoms=j, target_deg=60.0, sigma=5.0)
    assert kind == "value"
    return ValueRestraint(path=f"phases.0.atoms.{j[0]}.biso", target=0.5, sigma=0.1)


#: each kind with the atoms it names; O3 is never one of them, so removing it
#: shifts every named atom after it, and O5 always is, so removing it drops it
KINDS = {
    "bond": ["S2", "O5"],
    "tether": ["S2", "O5"],
    "anti-bump": ["O4", "O5"],
    "angle": ["O4", "S2", "O5"],
    "planarity": ["Pb1", "S2", "O4", "O5"],
    "torsion": ["Pb1", "S2", "O4", "O5"],
    "value": ["O5"],
}


def _named(phase: rx.Phase, r) -> list[str]:
    """The labels of the atoms restraint ``r`` names in ``phase``."""
    labels = [a.label for a in phase.atoms]
    if isinstance(r, ValueRestraint):
        return [labels[int(r.path.split(".")[3])]]
    if isinstance(r, (PlanarityRestraint, TorsionRestraint)):
        return [labels[j] for j in r.atoms]
    if isinstance(r, AngleRestraint):
        return [labels[r.atom_i], labels[r.atom_j], labels[r.atom_k]]
    return [labels[r.atom_i], labels[r.atom_j]]


def _refinement(pbso4, *restraints) -> rx.Refinement:
    phase = pbso4.model_copy(deep=True)
    phase.restraints = list(restraints)
    return rx.Refinement(Structure(phases=[phase]), INSTRUMENT, history=False)


def _pattern(ref: rx.Refinement) -> PatternData:
    tt = np.arange(10.0, 120.0, 0.1)
    y = 100.0 + 1e3 * np.asarray(ref.predict(tt))
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                       sigma=np.sqrt(y).tolist())


def _swapped(ref: rx.Refinement, a: str, b: str) -> Structure:
    candidate = ref.structure.model_copy(deep=True)
    atoms = candidate.phases[0].atoms
    i, j = (LABELS.index(a), LABELS.index(b))
    atoms[i], atoms[j] = atoms[j], atoms[i]
    return candidate


def _removed(ref: rx.Refinement, label: str) -> Structure:
    candidate = ref.structure.model_copy(deep=True)
    del candidate.phases[0].atoms[[a.label for a in candidate.phases[0].atoms].index(label)]
    return candidate


def _edit_quietly(ref: rx.Refinement, structure: Structure) -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*no longer has.*")
        ref.edit(structure=structure)


@pytest.mark.parametrize("kind", KINDS)
def test_a_restraint_follows_its_atoms_through_a_swap(pbso4, kind):
    """O3 and O5 trade places.  Every kind names O5 and none names O3, so before
    WP-2121 each then named O3 where it had named O5 (a bond S2–O5 became S2–O3),
    and nothing said so."""
    ref = _refinement(pbso4, _restraint(kind, KINDS[kind]))
    _edit_quietly(ref, _swapped(ref, "O3", "O5"))
    phase = ref.structure.phases[0]
    assert [a.label for a in phase.atoms] == ["Pb1", "S2", "O5", "O4", "O3"]
    (r,) = phase.restraints
    assert _named(phase, r) == KINDS[kind]


@pytest.mark.parametrize("kind", KINDS)
def test_a_restraint_follows_its_atoms_when_one_ahead_of_them_goes(pbso4, kind):
    """Removing O3 moves O4 and O5 down one number.  Before WP-2121 a restraint on
    O5 (atom 4) was then out of range, and one on O4 named O5."""
    ref = _refinement(pbso4, _restraint(kind, KINDS[kind]))
    _edit_quietly(ref, _removed(ref, "O3"))
    phase = ref.structure.phases[0]
    (r,) = phase.restraints
    assert _named(phase, r) == KINDS[kind]
    compile_model(ref.structure, INSTRUMENT, _pattern(ref), mode="rietveld")


@pytest.mark.parametrize("kind", KINDS)
def test_a_restraint_on_a_removed_atom_is_dropped_and_named(pbso4, kind):
    """Every kind names O5.  Removing O5 was accepted and the next fit raised a
    bare ``IndexError``.  Now the restraint goes, the warning names it in the
    tie drop's words, and the model compiles."""
    keep = BondRestraint(atom_i=1, atom_j=3, target=1.47, sigma=0.01)     # S2-O4
    ref = _refinement(pbso4, keep, _restraint(kind, KINDS[kind]))
    with pytest.warns(UserWarning, match="no longer has") as caught:
        ref.edit(structure=_removed(ref, "O5"))
    (message,) = [str(w.message) for w in caught if "no longer has" in str(w.message)]
    assert message.startswith("1 restraint(s) named an atom this model no longer has "
                              "and were dropped: ")
    assert "O5" in message and kind.replace("-", "") in message.replace("-", "")
    phase = ref.structure.phases[0]
    assert phase.restraints == [keep]
    compile_model(ref.structure, INSTRUMENT, _pattern(ref), mode="rietveld")


def test_the_swapped_bond_restrains_the_distance_it_was_written_for(pbso4):
    """The issue's case end to end: the restraint row the next fit builds reads
    S2 and O5, not S2 and O3 as it did before."""
    ref = _refinement(pbso4, _restraint("bond", ["S2", "O5"]))
    _edit_quietly(ref, _swapped(ref, "O3", "O5"))
    model = compile_model(ref.structure, INSTRUMENT, _pattern(ref), mode="rietveld")
    (bond,) = model.restraints.items
    labels = [a.label for a in ref.structure.phases[0].atoms]
    assert (labels[bond.i], labels[bond.j]) == ("S2", "O5")


def test_a_restraint_written_for_the_new_numbering_is_taken_as_written(pbso4):
    """A restraint the old phase did not hold was written against the new atom
    list, so it is read as written while the carried one beside it moves."""
    carried = _restraint("bond", ["S2", "O5"])
    ref = _refinement(pbso4, carried)
    candidate = _swapped(ref, "O3", "O5")
    fresh = BondRestraint(atom_i=1, atom_j=4, target=1.48, sigma=0.01)     # S2-O3, new list
    candidate.phases[0].restraints.append(fresh)
    _edit_quietly(ref, candidate)
    phase = ref.structure.phases[0]
    assert [_named(phase, r) for r in phase.restraints] == [["S2", "O5"], ["S2", "O3"]]


def test_an_edit_that_moves_no_atom_leaves_the_restraints_alone(pbso4):
    """The common case: a value edit.  The list is the same object's equal, and the
    restraints the caller edited in place are kept as the caller left them."""
    ref = _refinement(pbso4, _restraint("bond", ["S2", "O5"]))
    candidate = ref.structure.model_copy(deep=True)
    candidate.phases[0].restraints[0] = _restraint("bond", ["S2", "O4"])
    _edit_quietly(ref, candidate)
    phase = ref.structure.phases[0]
    assert [_named(phase, r) for r in phase.restraints] == [["S2", "O4"]]


def test_a_new_restraint_out_of_range_refuses_the_edit(pbso4):
    """A restraint the caller wrote for the new structure, naming an atom it lacks,
    is the caller's mistake to see now, not a dropped line or a later ``IndexError``."""
    ref = _refinement(pbso4)
    candidate = _removed(ref, "O5")
    candidate.phases[0].restraints.append(BondRestraint(atom_i=1, atom_j=4, target=1.47,
                                                        sigma=0.01))
    with pytest.raises(ValueError, match="refused rather than recorded.*atom_j=4"):
        ref.edit(structure=candidate)
    assert len(ref.structure.phases[0].atoms) == 5                     # untouched


def test_a_value_restraint_off_any_atom_passes_unchanged(pbso4):
    ref = _refinement(pbso4, ValueRestraint(path="phases.0.scale", target=1.0, sigma=0.1))
    _edit_quietly(ref, _removed(ref, "O3"))
    assert ref.structure.phases[0].restraints[0].path == "phases.0.scale"


def test_a_value_restraint_follows_its_phase_when_a_phase_is_inserted_ahead(pbso4):
    """A value restraint's path is a whole-model path.  A second phase put ahead of
    PbSO₄ makes it phase 1, matched by name, and the path moves with it, while the
    bond restraint's atom indices, local to the phase, stay as they were."""
    value = ValueRestraint(path="phases.0.atoms.4.biso", target=0.5, sigma=0.1)
    ref = _refinement(pbso4, value, _restraint("bond", ["S2", "O5"]))
    other = pbso4.model_copy(update={"name": "PBSO4-B", "restraints": []}, deep=True)
    candidate = ref.structure.model_copy(deep=True)
    candidate.phases.insert(0, other)
    _edit_quietly(ref, candidate)
    moved = ref.structure.phases[1]
    assert moved.name == pbso4.name
    assert moved.restraints[0].path == "phases.1.atoms.4.biso"
    assert _named(moved, moved.restraints[1]) == ["S2", "O5"]
    assert ref.structure.phases[0].restraints == []


@pytest.mark.parametrize("kind", ["tether", "anti-bump"])
def test_a_one_sided_restraint_out_of_range_is_refused_when_built(pbso4, kind):
    """``Phase`` checked bond, angle, planarity and torsion indices, and not these two."""
    phase = pbso4.model_copy(deep=True)
    r = _restraint(kind, ["S2", "O5"]).model_copy(update={"atom_j": 7})
    with pytest.raises(ValueError, match="atom_j=7"):
        rx.Phase.model_validate({**phase.model_dump(), "restraints": [r.model_dump()]})


def test_a_value_restraint_on_an_atom_the_phase_lacks_is_refused_when_built(pbso4):
    phase = pbso4.model_copy(deep=True)
    with pytest.raises(ValueError, match="phases.0.atoms.9.biso"):
        Structure(phases=[phase.model_copy(update={"restraints": [
            ValueRestraint(path="phases.0.atoms.9.biso", target=0.5, sigma=0.1)]})])


# ------------------------------------------------------------ the other atom-indexed records


def test_distortion_mode_rows_follow_their_atoms_through_a_swap():
    """``DistortionModes.base`` and each mode's ``vectors`` hold one row per atom in
    order (WP-1419).  Before WP-2121 a swap gave each atom the other's base and
    displacement, and the table refused the edit for a coordinate drift the edit
    never made.  The rows now follow their atoms, and the mode still moves O2."""
    from tests.test_distortion_block import _instrument, _phase
    phase = _phase()
    ref = rx.Refinement(Structure(phases=[phase]), _instrument(), history=False)
    before = {a.label: (a.x.value, a.y.value, a.z.value) for a in ref.structure.phases[0].atoms}
    candidate = ref.structure.model_copy(deep=True)
    atoms = candidate.phases[0].atoms
    atoms[0], atoms[3] = atoms[3], atoms[0]                           # Ta <-> O2
    _edit_quietly(ref, candidate)
    moved = ref.structure.phases[0]
    modes = moved.distortion_modes
    assert [a.label for a in moved.atoms] == ["O2", "Na", "O1", "Ta"]
    assert modes.base[0] == phase.distortion_modes.base[3]
    assert modes.modes[0].vectors[0] != (0.0, 0.0, 0.0)
    assert modes.modes[0].vectors[3] == (0.0, 0.0, 0.0)
    rx.Refinement(ref.structure, _instrument(), history=False).parameters()
    after = {a.label: (a.x.value, a.y.value, a.z.value) for a in moved.atoms}
    assert after == pytest.approx(before)


def test_removing_an_atom_a_mode_record_covers_refuses_the_edit():
    """A mode record states every atom; one fewer atom is a different child, and
    the record cannot be cut down to it without changing what each mode means."""
    from tests.test_distortion_block import _instrument, _phase
    ref = rx.Refinement(Structure(phases=[_phase()]), _instrument(), history=False)
    candidate = ref.structure.model_copy(deep=True)
    del candidate.phases[0].atoms[1]
    with pytest.raises(ValueError, match="refused rather than recorded.*base positions"):
        ref.edit(structure=candidate)


def test_a_rigid_body_follows_a_swap_by_label_and_refuses_losing_an_atom(pbso4):
    """A body names its atoms by label, so a swap leaves it right.  Removing one of
    its atoms in place was accepted before WP-2121; the phase's own body check
    now runs at the edit."""
    from rietx.crystallography.bodies import body_from_atoms
    phase = pbso4.model_copy(deep=True)
    for atom in phase.atoms[1:]:
        for c in (atom.x, atom.y, atom.z):
            c.vary = False                                            # the body's
    phase.rigid_bodies = [body_from_atoms(phase, ["S2", "O3", "O4", "O5"], "SO4", origin="S2")]
    ref = rx.Refinement(Structure(phases=[phase]), INSTRUMENT, history=False)
    _edit_quietly(ref, _swapped(ref, "Pb1", "O4"))
    assert ref.structure.phases[0].rigid_bodies[0].atoms == ["S2", "O3", "O4", "O5"]
    with pytest.raises(ValueError, match="refused rather than recorded.*'O4'"):
        ref.edit(structure=_removed(ref, "O4"))


# ------------------------------------------------------------ the series' prepare hook


def test_a_series_prepare_that_removes_an_atom_moves_the_restraints_with_it(pbso4):
    """``prepare`` edits each pattern's copy of the declared structure, and a hook
    that drops O3 shifted every restraint after it, as ``edit`` did."""
    from rietx.sequential import SequentialRefinement
    from rietx.strategy.staged import RefinementPlan
    ref = _refinement(pbso4, _restraint("bond", ["S2", "O5"]))
    data = _pattern(ref)
    seen: list[list[str]] = []

    def prepare(index, data, structure, instrument):
        del structure.phases[0].atoms[2]                              # O3

    def constrain(index, built):
        phase = built.structure.phases[0]
        seen.append(_named(phase, phase.restraints[0]))

    chain = SequentialRefinement(ref.structure, INSTRUMENT)
    plan = RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"], max_iter=3)])
    chain.fit([data], plan=plan, prepare=prepare, constrain=constrain)
    assert seen and all(s == ["S2", "O5"] for s in seen)


# ------------------------------------------------------------ the text document's tie refusal


def test_the_tie_refusal_names_where_each_tie_comes_from(tmp_path):
    """The read-only reason said every tie came from the crystal system or the
    site symmetry, which sends the author of a user tie looking in the wrong place.
    A user tie now names the verbs that change it; a symmetry tie keeps its reason."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize
    from tests.test_textdoc import _edit, _project
    project = _project(tmp_path / "doc.rex", _write_xye(tmp_path / "p.xye", synthesize()))
    project.refinement.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0,
                           offset=1.0)
    text = td.render(project)

    def refusal(path: str, line: str) -> str:
        _, errors = td.changes(td.parse(_edit(text, path, line)), project)
        (message,) = [e.message for e in errors if e.message.startswith("tie on")]
        return message

    user = refusal("atoms.1.occ", "  atoms.1.occ  0  min 0  = 1·phases.0.atoms.0.occ")
    assert "ref.untie" in user and "crystal system" not in user
    symmetry = refusal("cell.b", "  cell.b  4.1606  = 2·phases.0.cell.a")
    assert "crystal system" in symmetry and "ref.untie" not in symmetry
