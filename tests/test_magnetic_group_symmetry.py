"""A magnetic group must be a symmetry of the structure it decorates (issue #597).

Three documented inputs used to compile a different structure from the one the
declared group describes, with no diagnostic: a type-IV group beside the
nuclear group of its unprimed operations, a BNS number beside a nuclear group
in another origin choice, and a TOPAS file whose nuclear ``space_group`` is in
a setting the magnetic number's operators are not a symmetry of.  ``Phase`` now
refuses each by name (``scattering.check_group_is_structure_symmetry``: the
lattice metric RᵀGR = G for every operation, and invariance of the compiled
(species, position, moment) set).  The positive arm is every consistent route
the same comparison was measured on: the operator list including the
anti-translation, explicit copies, the matching origin choice, partial
occupancy, a disordered site, and the supercell builder's own output under both
``nuclear_group`` values, magnetic and displacive.

Expected values: spglib's identification of the compiled structure and the
issue's independent P1 expansion (``checks`` scripts of the audit), not rietx.
"""

from __future__ import annotations

from fractions import Fraction

import gemmi
import numpy as np
import pytest

from rietx.crystallography.magnetic import operators as O
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.operators import format_transform
from rietx.crystallography.magnetic.scattering import (
    check_group_is_structure_symmetry,
    compile_magnetic_sites,
)
from rietx.crystallography.magnetic.supercell import magnetic_supercell
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.io.projects.topas import TopasInpError, read_topas_inp, to_structure
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment
from rietx.schemas.structure import Phase as _Phase

REFUSED = "not a symmetry of the structure it decorates"


def Phase(**kw) -> _Phase:
    """A phase *as stated*: built, then judged where a statement is judged.

    The check is not a schema validator (a refined phase has to validate), so
    the tests ask it the way ``Refinement`` and the readers do.
    """
    phase = _Phase(**kw)
    check_group_is_structure_symmetry(phase)
    return phase


def _cell(a, b, c, al=90.0, be=90.0, ga=90.0) -> Cell:
    return Cell(a=P(value=a), b=P(value=b), c=P(value=c), alpha=P(value=al),
                beta=P(value=be), gamma=P(value=ga))


def _atom(label, species, xyz, moment=None, ion=None, occ=1.0) -> Atom:
    return Atom(label=label, species=species, x=P(value=xyz[0]),
                y=P(value=xyz[1]), z=P(value=xyz[2]), occ=P(value=occ),
                biso=P(value=0.0),
                moment=None if moment is None else Moment.from_values(moment, ion))


# ------------------------------------------------- reach 1: a type-IV group
P4MMM = [o.triplet() for o in
         gemmi.find_spacegroup_by_name("P 4/m m m").operations().sym_ops]


def _eps(triplet: str) -> int:
    r = np.array(gemmi.Op(triplet).rot) / gemmi.Op.DEN
    return int(round(np.linalg.det(r) * r[2, 2]))


#: P4/mmm's operations with m ∥ c's time-reversal signs, plus the
#: anti-centring {1 | 0,0,½}′: a type-IV group in a c-doubled cell
CHAIN = MagneticSymmetry(
    operations=[t + (",+1" if _eps(t) > 0 else ",-1") for t in P4MMM],
    centerings=["x,y,z,+1", "x,y,z+1/2,-1"])
WITH_TRANSLATION = P4MMM + [gemmi.Op(t).combine(gemmi.Op("x,y,z+1/2")).triplet()
                            for t in P4MMM]
C8 = dict(cell=_cell(4.0, 4.0, 8.0), magnetic_symmetry=CHAIN)


def _mn(label="Mn", xyz=(0, 0, 0), m=(0, 0, 3), occ=1.0) -> Atom:
    return _atom(label, "Mn", xyz, m, "Mn2+", occ=occ)


def test_a_type_iv_group_beside_its_unprimed_symbol_is_refused():
    """The anti-translated Mn at (0,0,½) the group implies does not exist.

    Compiled on main: nuclear |F|² ×0.25 on the true nuclear rows and non-zero
    on the purely magnetic ones; spglib names that structure 123.345, not the
    124.360 of the consistent route below.
    """
    with pytest.raises(ValueError, match=REFUSED) as err:
        Phase(name="c", space_group="P 4/m m m", atoms=[_mn()], **C8)
    message = str(err.value)
    assert "no such atom" in message
    assert "Phase.symmetry_operations" in message


def test_a_type_iv_bns_number_beside_its_unprimed_symbol_is_refused():
    """The same reach by number: 124.360 (P_c4/mcc-type) on P4/mmm, c = 8."""
    with pytest.raises(ValueError, match=REFUSED):
        Phase(name="c", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 8.0),
              magnetic_symmetry="124.360", atoms=[_mn()])


@pytest.mark.parametrize("occ, m2", [(0.5, (0, 0, -3)), (1.0, (0, 0, 3))])
def test_explicit_copies_the_group_does_not_relate_are_refused(occ, m2):
    """Copies at (0,0,½) with another occupancy, or with the moment not reversed."""
    with pytest.raises(ValueError, match=REFUSED):
        Phase(name="c", space_group="P 4/m m m",
              atoms=[_mn("Mn1"), _mn("Mn2", (0, 0, 0.5), m2, occ=occ)], **C8)


def test_the_consistent_type_iv_routes_pass():
    """The nuclear list with the translation, and two antiparallel copies."""
    Phase(name="c", space_group="[P 4/m m m]",
          symmetry_operations=WITH_TRANSLATION, atoms=[_mn()], **C8)
    Phase(name="c", space_group="P 4/m m m",
          atoms=[_mn("Mn1"), _mn("Mn2", (0, 0, 0.5), (0, 0, -3))], **C8)


# ------------------------------------------ reach 2: the other origin choice
SITE, MOMENT = (0.25, 0.25, 0.0), (1.0, 2.0, 0.0)


def _choice2_48_259() -> MagneticSymmetry:
    uni = O._resolve_uni("48.259")
    alt, = [s for s in O.database_settings(uni) if not s.is_default]
    ops, cen = O.magnetic_group(uni, hall_number=alt.hall_number).xyz_strings()
    return MagneticSymmetry(operations=list(ops), centerings=list(cen))


@pytest.mark.parametrize("with_oxygen", [False, True])
def test_a_bns_number_in_the_other_origin_choice_is_refused(with_oxygen):
    """P n n n:2 + '48.259' (spglib's default, origin choice 1).

    On main the image at (¼,¼,½) compiled (−1,−2,0) where 48.259 in choice 2
    gives (1,−2,0); spglib named the compiled structure 13.69.
    """
    atoms = [_atom("Mn", "Mn", SITE, MOMENT, "Mn2+")]
    if with_oxygen:
        atoms.append(_atom("O", "O", (0.11, 0.23, 0.37)))
    with pytest.raises(ValueError, match=REFUSED) as err:
        Phase(name="p", space_group="P n n n:2", cell=_cell(5.5, 6.5, 7.5),
              magnetic_symmetry="48.259", atoms=atoms)
    assert "database_settings" in str(err.value)


def test_the_matching_origin_choice_passes():
    Phase(name="p", space_group="P n n n:2", cell=_cell(5.5, 6.5, 7.5),
          magnetic_symmetry=_choice2_48_259(),
          atoms=[_atom("Mn", "Mn", SITE, MOMENT, "Mn2+"),
                 _atom("O", "O", (0.11, 0.23, 0.37))])


MNF2 = dict(space_group="P 42/m n m", cell=_cell(4.8734, 4.8734, 3.3099))


def test_mnf2_with_its_group_at_a_shifted_origin_is_refused():
    """136.499 shifted by (¼,¼,¼) compiled ferromagnetic on main (spglib: 136.501)."""
    ops, cen = O.magnetic_group("136.499").transformed(
        "a,b,c;1/4,1/4,1/4").xyz_strings()
    with pytest.raises(ValueError, match=REFUSED):
        Phase(name="m", **MNF2,
              magnetic_symmetry=MagneticSymmetry(operations=list(ops),
                                                 centerings=list(cen)),
              atoms=[_atom("Mn", "Mn", (0, 0, 0), (0, 0, 1), "Mn2+"),
                     _atom("F", "F", (0.305, 0.305, 0))])


@pytest.mark.parametrize("atoms", [
    pytest.param(lambda: [_mn(m=(0, 0, 4.6))], id="standard"),
    pytest.param(lambda: [_mn(m=(0, 0, 4.6), occ=0.5)], id="Mn-occ-half"),
    pytest.param(lambda: [_mn(m=(0, 0, 4.6), occ=0.5),
                          _atom("Fe", "Fe", (0, 0, 0), (0, 0, 4.0), "Fe3+", occ=0.5)],
                 id="Mn-Fe-both-moments"),
    pytest.param(lambda: [_mn(m=(0, 0, 4.6), occ=0.5),
                          _atom("Zn", "Zn", (0, 0, 0), occ=0.5)],
                 id="Mn-Zn-one-moment"),
])
def test_partial_occupancy_and_disorder_are_not_refused(atoms):
    Phase(name="m", **MNF2, magnetic_symmetry="136.499",
          atoms=atoms() + [_atom("F", "F", (0.305, 0.305, 0))])


# ------------------------------------- reach 3: TOPAS, a non-standard setting
INP = """str
   phase_name "E4"
   space_group "P 1 1 21/b"
   mag_space_group 14.79
   scale ! 1.0
   a ! 5.2
   b ! 6.9
   c ! 8.4
   al ! 90.0
   be ! 90.0
   ga ! 115.0
   site M1 x ! 0.0 y ! 0.0 z ! 0.0 occ Mn+2 ! 1.0 beq ! 0.0 mlx ! 0.3 mly ! -0.25 mlz ! 0.35
"""
#: P 1 1 2₁′/b′, the c-unique group the file's author meant
C_UNIQUE = ["x,y,z,+1", "-x,-y+1/2,z+1/2,-1", "-x,-y,-z,+1", "x,y+1/2,-z+1/2,-1"]


def test_the_topas_reader_refuses_a_b_unique_number_on_a_c_unique_cell(tmp_path):
    """Mn alone on the inversion centre: the metric predicate alone catches it.

    On main the second Mn got (1.56, +1.725, 2.94) where the c-unique group
    gives (1.56, −1.725, −2.94); |F_M|² at (1 −1 0) 34.3 against 199.6.
    """
    f = tmp_path / "e4.inp"
    f.write_text(INP, encoding="utf-8")
    with pytest.raises(TopasInpError, match="does not map the cell"):
        to_structure(read_topas_inp(f))
    ph = to_structure(read_topas_inp(f),
                      magnetic_symmetry={"E4": {"operations": C_UNIQUE}}).phases[0]
    assert ph.magnetic_symmetry is not None


def test_a_b_unique_group_on_a_c_unique_cell_is_refused_with_any_atoms():
    with pytest.raises(ValueError, match="does not map the cell"):
        Phase(name="e", space_group="P 1 1 21/b",
              cell=_cell(5.0, 6.0, 7.0, 90.0, 90.0, 115.0), magnetic_symmetry="14.79",
              atoms=[_atom("Mn", "Mn", (0, 0, 0), (1.56, -1.725, 2.94), "Mn2+"),
                     _atom("O", "O", (0.21, 0.13, 0.37))])
    Phase(name="e", space_group="P 1 21/c 1",
          cell=_cell(5.0, 6.0, 7.0, 90.0, 115.0, 90.0), magnetic_symmetry="14.79",
          atoms=[_atom("Mn", "Mn", (0, 0, 0), (1.56, -1.725, 2.94), "Mn2+"),
                 _atom("O", "O", (0.21, 0.13, 0.37))])


# ------------------------------------------------ the supercell builder's output
def _parent() -> Phase:
    return Phase(name="p4", space_group="P 4/m m m", cell=_cell(3.8, 3.8, 4.1),
                 atoms=[_atom("Mn", "Mn", (0, 0, 0)), _atom("O", "O", (0.5, 0, 0))])


def _builder_cases():
    for kind in ("magnetic", "displacive"):
        for cand in candidates("P 4/m m m", (0, 0, 0), (0, 0, Fraction(1, 2)),
                               kind=kind).candidates:
            for ng in ("parent", "magnetic"):
                yield pytest.param(kind, cand, ng, id=f"{kind}-{cand.bns_number}-{ng}")


@pytest.mark.parametrize("kind, cand, nuclear_group", _builder_cases())
def test_the_builder_output_is_not_refused(kind, cand, nuclear_group):
    """Every statement the builder makes passes; colourless ⊆ nuclear would fail 8 of 8.

    Two of these (63.466 and 38.188 under ``"magnetic"``) the builder refuses
    for its own, older reason; that refusal is not this check's.
    """
    kw = dict(nuclear_group=nuclear_group)
    if kind == "magnetic":
        kw.update(magnetic_species="Mn", ion="Mn2+", magnitude=2.0)
    try:
        magnetic_supercell(_parent(), cand, **kw)
    except ValueError as exc:
        assert REFUSED not in str(exc)
        assert "child cell" in str(exc)


def test_an_anti_translated_image_compiles_the_reversed_moment():
    """The image match is modulo the lattice for every coordinate distance.

    ``_axial_matrices`` compared an unwrapped nuclear image with a wrapped
    magnetic one through min(δ, 1 − δ), which is negative for δ in (1, 2) and
    so "matched" the first operation it met.  On P n n n:2 at k = (½,0,0),
    stated at the child origin of transform 2a,b,c;½,0,0, the Fe image one
    anti-translation away compiled the untranslated moment on main (spglib:
    13.69, against 17.12 for the same statement at the zero origin).
    """
    parent = Phase(name="pnnn", space_group="P n n n:2",
                   cell=_cell(5.0, 6.0, 7.0),
                   atoms=[_atom("Fe", "Fe", (0.0, 0.0, 0.0)),
                          _atom("O", "O", (0.25, 0.25, 0.25))])
    cand = candidates(parent.space_group, (0.0, 0.0, 0.0),
                      (Fraction(1, 2), 0, 0)).candidates[0]
    base = magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+",
                              magnitude=2.0)
    group = base.group.transformed(format_transform(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]], (Fraction(-1, 4), 0, 0)))
    phase = magnetic_supercell(parent, group=group, transform="2a,b,c;1/2,0,0",
                               k=cand.cell.k, magnetic_species="Fe", ion="Fe3+",
                               magnitude=2.0).phase
    j = next(i for i, a in enumerate(phase.atoms) if a.moment is not None)
    sites = compile_phase_sites(phase, None, neutron=True)
    mag = compile_magnetic_sites(phase, sites.ops)
    atom = phase.atoms[j]
    xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
    m = np.array(atom.moment.values())
    rot, tran = sites.ops[j]
    images = (np.einsum("mij,j->mi", np.asarray(rot, float), xyz)
              + np.asarray(tran, float)) % 1.0
    moments = mag.mom_mat[j] @ m
    target = (xyz + np.array([0.5, 0.0, 0.0])) % 1.0
    k, = [i for i, p in enumerate(images) if np.allclose(p, target, atol=1e-9)]
    assert np.allclose(moments[k], -m, atol=1e-12)


def _drifted_supercell() -> _Phase:
    """The builder's output, then what a fit that frees B and z leaves behind."""
    cand = candidates("P 4/m m m", (0, 0, 0), (0, 0, Fraction(1, 2)),
                      kind="magnetic").candidates[0]
    phase = magnetic_supercell(_parent(), cand, magnetic_species="Mn",
                               ion="Mn2+", magnitude=2.0).phase
    check_group_is_structure_symmetry(phase)      # a clean statement first
    for n, atom in enumerate(phase.atoms):
        atom.biso.value += 0.03 * n               # copies the group relates
        atom.z.value += 2e-3 * n                  # no longer agree
    return phase


def test_a_refined_supercell_still_validates_and_reads_back(tmp_path):
    """The check is not on the schema, so refined values are never re-judged.

    Review of #620: the builder lists anti-translated copies as independent
    sites, so once B or the coordinates are freed they drift apart, and a
    validator on ``Phase`` refused the JSON round trip of the fit's own
    result ("the 'O_2' there has another occupancy or B").
    """
    import rietx as rx
    from rietx.history.store import read_records, write_records
    from rietx.schemas.history import (
        HistoryNode,
        HistoryRecord,
        NodeAction,
        RefinementState,
    )
    from rietx.schemas.structure import Structure

    structure = Structure(phases=[_drifted_supercell()])
    back = Structure.model_validate_json(structure.model_dump_json())
    assert back == structure
    node = HistoryNode(id="n1", action=NodeAction(kind="stage"),
                       state=RefinementState(
                           structure=structure,
                           instrument=rx.Instrument.constant_wavelength_neutron(2.4)))
    path = tmp_path / "history.jsonl"
    write_records(path, [HistoryRecord(record="node", node=node)])
    got, = list(read_records(path))
    assert got.node.state.structure == structure
    # positive arm: the same drift *is* what the check refuses when asked,
    # so the round trip passing is the check's absence from the schema
    with pytest.raises(ValueError, match=REFUSED):
        check_group_is_structure_symmetry(structure.phases[0])


def test_a_refinement_refuses_a_group_that_is_not_a_symmetry():
    """The statement is judged where it enters a fit, whatever built it."""
    import rietx as rx
    from rietx.schemas.structure import Structure

    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    bad = _Phase(name="c", space_group="P 4/m m m", atoms=[_mn()], **C8)
    with pytest.raises(ValueError, match=REFUSED):
        rx.Refinement(Structure(phases=[bad]), instrument)
    ok = _Phase(name="c", space_group="[P 4/m m m]",
                symmetry_operations=WITH_TRANSLATION, atoms=[_mn()], **C8)
    rx.Refinement(Structure(phases=[ok]), instrument)


# --------------------------------- refined state is never re-judged (review r2)
def _refined_ref():
    """(rx, instrument, a clean supercell Structure, the same with B and z drifted)."""
    import rietx as rx
    from rietx.schemas.structure import Structure

    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    cand = candidates("P 4/m m m", (0, 0, 0), (0, 0, Fraction(1, 2)),
                      kind="magnetic").candidates[0]
    fresh = Structure(phases=[magnetic_supercell(
        _parent(), cand, magnetic_species="Mn", ion="Mn2+", magnitude=2.0).phase])
    return rx, instrument, fresh, Structure(phases=[_drifted_supercell()])


def test_the_packages_own_constructions_do_not_rejudge_refined_state():
    """``branch``, ``_trial`` and ``from_node`` build a ``Refinement`` from a
    structure a fit already moved; none of them is a statement entering."""
    from rietx.history.tree import RefinementTree
    from rietx.schemas.history import NodeAction

    rx, instrument, fresh, drifted = _refined_ref()
    x = np.linspace(10.0, 90.0, 50)
    data = rx.PatternData(two_theta=x.tolist(), intensity=[100.0] * len(x))
    ref = rx.Refinement(fresh, instrument, history=RefinementTree.for_data(data))
    ref.structure = drifted.model_copy(deep=True)       # what a fit leaves
    assert ref.branch().structure == drifted
    assert ref._trial().structure == drifted
    node = ref.history.add(parents=[], action=NodeAction(kind="root"),
                           state=ref.snapshot())
    assert rx.Refinement.from_node(ref.history, node.id).structure == drifted
    # positive arm: the same drifted structure *is* refused when a caller
    # states it
    with pytest.raises(ValueError, match=REFUSED):
        rx.Refinement(drifted, instrument)


def test_edit_does_not_rejudge_a_refined_supercell_with_one_value_changed():
    """The GUI hands ``edit`` the refined structure with one field changed;
    that is refined state, not a statement entering."""
    rx, instrument, fresh, drifted = _refined_ref()
    ref = rx.Refinement(fresh, instrument)
    ref.structure = drifted.model_copy(deep=True)       # what a fit leaves
    edited = ref.structure.model_copy(deep=True)
    edited.phases[0].atoms[0].biso.value += 0.01
    ref.edit(structure=edited)
    assert ref.structure == edited
    # positive arm: a caller constructing a Refinement from the same drifted
    # values is still judged
    with pytest.raises(ValueError, match=REFUSED):
        rx.Refinement(drifted, instrument)


def test_a_multi_histogram_refinement_judges_the_statement():
    import rietx as rx
    from rietx.joint import JointRefinement
    from rietx.schemas.structure import Structure

    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    bad = _Phase(name="c", space_group="P 4/m m m", atoms=[_mn()], **C8)
    with pytest.raises(ValueError, match=REFUSED):
        JointRefinement(Structure(phases=[bad]), [instrument])
    _, _, fresh, _ = _refined_ref()
    JointRefinement(fresh, [instrument])       # positive arm


def test_a_series_judges_the_statement_once_and_not_each_patterns_carried_state():
    """``_fit_one`` builds pattern n's ``Refinement`` from values warmed off
    pattern n−1; a refined supercell must run through it."""
    import rietx as rx
    from rietx.schemas.structure import Structure
    from rietx.sequential import SequentialRefinement

    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    bad = _Phase(name="c", space_group="P 4/m m m", atoms=[_mn()], **C8)
    with pytest.raises(ValueError, match=REFUSED):
        SequentialRefinement(Structure(phases=[bad]), instrument)
    _, _, fresh, drifted = _refined_ref()
    x = np.linspace(10.0, 90.0, 400)
    data = rx.PatternData(two_theta=x.tolist(), intensity=[100.0] * len(x))
    series = SequentialRefinement(fresh, instrument)

    def drift(index, pattern, structure, ins):          # the carried state
        structure.phases[0] = drifted.phases[0].model_copy(deep=True)

    result = series.fit([data, data], prepare=drift)
    assert len(result.entries) == 2
