"""A phase whose group no tabulated setting names still gets its report and CIF.

WP-2221, issue #1688.  ``magnetic_supercell`` can return a child whose
``space_group`` is an operation list that no gemmi setting has with the child
cell's axes: NiO on rhombohedral axes at k = (½ ½ ½), BNS 2.7, and the
WP-1419 displacive children of a Pnma parent.  The fit ran, and then
``report()`` and the nuclear CIF writer raised because they asked the table for
the crystal system.  The crystal system is a property of the point group, so it
is now read from the operators (``symmetry.crystal_system_of``), and only the
setting-bound keys still need a tabulated setting.

Every structure here is synthetic and stated inline; no data file is read.
"""

from __future__ import annotations

import functools
from fractions import Fraction
from pathlib import Path

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import symmetry as sym
from rietx.crystallography.magnetic import isotropy
from rietx.crystallography.magnetic.supercell import magnetic_supercell
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure

OUT = Path(__file__).parent / "output"
TWO_THETA = np.arange(10.0, 110.0, 0.02)
NEUTRON = 1.886


def _p(value: float, **kw) -> Parameter:
    return Parameter(value=value, **kw)


def _atom(label: str, species: str, xyz) -> Atom:
    return Atom(label=label, species=species, x=_p(xyz[0]), y=_p(xyz[1]),
                z=_p(xyz[2]), occ=_p(1.0), biso=_p(0.3, unit="A^2"))


@functools.lru_cache(maxsize=1)
def _nio_child() -> Phase:
    """Issue #1688's child: NiO on R -3 m:R at k = (½ ½ ½), BNS 2.7."""
    ar = 4.177 / 2 ** 0.5
    cell = Cell(a=_p(ar), b=_p(ar), c=_p(ar),
                alpha=_p(60.0), beta=_p(60.0), gamma=_p(60.0))
    parent = Phase(name="NiO", space_group="R -3 m:R", cell=cell,
                   atoms=[_atom("Ni", "Ni", (0, 0, 0)),
                          _atom("O", "O", (0.5, 0.5, 0.5))])
    h = Fraction(1, 2)
    cand = next(c for c in isotropy.candidates(parent.space_group, (0, 0, 0),
                                               (h, h, h)).candidates
                if c.bns_number == "2.7")
    return magnetic_supercell(parent, cand, magnetic_species="Ni", ion="Ni2+",
                              magnitude=2.0).phase


@functools.lru_cache(maxsize=1)
def _pnma_child() -> Phase:
    """A WP-1419 displacive child: a Pnma perovskite's S1 (rank 2)#3 at k = (½ ½ ½)."""
    cell = Cell(a=_p(5.74), b=_p(7.70), c=_p(5.53),
                alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0))
    parent = Phase(name="ABO3", space_group="P n m a", cell=cell, atoms=[
        _atom("La", "La", (0.05, 0.25, 0.99)), _atom("Mn", "Mn", (0.0, 0.0, 0.5)),
        _atom("O1", "O", (0.49, 0.25, 0.07)), _atom("O2", "O", (0.30, 0.04, 0.72))])
    la = parent.atoms[0]
    cand = next(c for c in isotropy.candidates(
        parent.space_group, (la.x.value, la.y.value, la.z.value), (0.5, 0.5, 0.5),
        kind="displacive").candidates
        if c.irrep_label == "S1" and c.direction.label == "(rank 2)#3")
    return magnetic_supercell(parent, cand, nuclear_group="magnetic").phase


#: (builder, the label it carries, its crystal system read from the operators)
CHILDREN = (
    (_nio_child, "R-3m [unnamed in 2a,a+b,a+c]", "trigonal"),
    (_pnma_child, "Cm [unnamed in 2a,a+b,a+c]", "monoclinic"),
)
IDS = ("nio-bns2.7", "pnma-s1")


def _group(phase: Phase):
    return sym.resolve_group(phase.space_group, phase.symmetry_operations)


def test_the_operators_give_gemmis_crystal_system_on_every_tabulated_setting():
    """One route on a named group: the trace rule agrees with gemmi 564 of 564."""
    wrong = [sg.xhm() for sg in gemmi.spacegroup_table()
             if sym.crystal_system_of(tuple(op.triplet() for op in sg.operations()))
             != sg.crystal_system_str()]
    assert wrong == []


@pytest.mark.parametrize("build,label,system", CHILDREN, ids=IDS)
def test_an_unnamed_child_has_a_crystal_system_and_no_setting(build, label, system):
    """The basis-free answer is defined; the setting-bound ones still refuse."""
    phase = build()
    assert phase.space_group == label
    assert phase.parent_cell is not None  # its cell is stated through the parent
    sg = _group(phase)
    assert sg.crystal_system_str() == system
    with pytest.raises(ValueError, match=f"Its crystal system is '{system}'"):
        sg.closest_type
    # conventional ties in these axes would be wrong, so the table still refuses
    with pytest.raises(ValueError, match="no symmorphic space group"):
        sym.cell_constraints(sg)


def test_a_listed_named_group_keeps_its_cell_constraints():
    """An operation list with a closest type reads its ties exactly as before."""
    for symbol in ("P n m a", "R -3 m:R", "P 1 21/c 1", "P 63/m m c"):
        named = sym.get_spacegroup(symbol)
        listed = sym.OperatorGroup(label=symbol, xyz=tuple(
            op.triplet() for op in named.operations()))
        assert sym.cell_constraints(listed) == sym.cell_constraints(named)
        assert listed.crystal_system_str() == named.crystal_system_str()


@functools.lru_cache(maxsize=2)
def _fit(build):
    phase = build()
    inst = rx.Instrument.constant_wavelength_neutron(NEUTRON)
    truth = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                          inst.model_copy(deep=True), history=False)
    y = np.asarray(truth.predict(TWO_THETA))
    rng = np.random.default_rng(2221)
    pattern = rx.PatternData(
        two_theta=TWO_THETA.tolist(),
        intensity=rng.poisson(y / y.max() * 2e4 + 50.0).astype(float).tolist())
    ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                        inst.model_copy(deep=True), history=False)
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "scale", ["phases.*.scale", "instrument.background.c*"])])
    result = ref.fit(pattern, plan=plan, telemetry=False)
    return ref, result


@pytest.mark.parametrize("build,label,system", CHILDREN, ids=IDS)
def test_report_returns_with_every_section(build, label, system):
    """Issue #1688's acceptance: the fit completes and so does its report."""
    ref, result = _fit(build)
    report = ref.report()
    assert [s.phase_index for s in report.satellites] == [0]
    assert report.background is not None
    assert report.identifiability is not None
    assert report.abstained_reason is None
    if build is _nio_child:
        assert [m.phase for m in report.magnetic] == [build().name]
    assert str(report)
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    png = OUT / f"wp2221_{build.__name__.strip('_')}.png"
    plot_result(result, path=str(png))
    import matplotlib.pyplot as plt

    plt.close("all")
    assert png.exists()


@pytest.mark.parametrize("build,label,system", CHILDREN, ids=IDS)
def test_the_nuclear_cif_block_is_written(build, label, system):
    """The block states the system from the operators and claims no IT number."""
    from rietx.io.cif.blocks import write_structure_block

    phase = build()
    doc = gemmi.cif.Document()
    block = doc.add_new_block("child")
    write_structure_block(block, phase)
    assert gemmi.cif.as_string(block.find_value("_space_group_crystal_system")) == system
    assert block.find_value("_space_group_IT_number") is None
    assert gemmi.cif.as_string(block.find_value("_space_group_name_H-M_alt")) == label
    ops = block.find_loop("_space_group_symop_operation_xyz")
    assert len(ops) == len(phase.symmetry_operations)

