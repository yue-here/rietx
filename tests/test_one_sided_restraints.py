"""Tether and anti-bump: one-sided distance restraints (WP-1809).

A tether row is √w·max(0, d − d_max)/σ and an anti-bump row
√w·min(0, d − d_min)/σ (TOPAS's ``Distance_Restrain_Keep_Within`` /
``_Keep_Out``, Coelho, *TOPAS-Academic V6 Technical Reference*, 2016,
p. 159).  Each is checked where it can fail: zero on its flat side, slope
1/σ on the other, the analytic row Jacobian against a finite difference of the
residual on both sides of the kink, the data statistics untouched by the rows,
both rows kept through a staged fit whichever side they end on, and a pair
list that is complete, excludes a body's own pairs and states no minimum
nobody gave.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography.bodies import add_body
from rietx.model.forward import compile_model
from rietx.model.restraints import anti_bump_restraints, summarise_restraints
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    AntiBumpRestraint,
    Atom,
    Cell,
    Phase,
    Structure,
    TetherRestraint,
)

LAB = Instrument.debye_scherrer(wavelength=1.5406)


def _pair(dx: float, restraint) -> tuple[Structure, ParameterTable]:
    """Two atoms in a P1 cubic 6 Å cell, ``dx`` (fractional) apart along a."""
    P = Parameter
    s = Structure(phases=[Phase(
        name="p", space_group="P1", cell=Cell.cubic(6.0),
        atoms=[Atom(label="A", species="Li", x=P(value=0.2, vary=True),
                    y=P(value=0.3, vary=True), z=P(value=0.4, vary=True)),
               Atom(label="B", species="O", x=P(value=0.2 + dx, vary=True),
                    y=P(value=0.3, vary=True), z=P(value=0.4, vary=True))],
        scale=P(value=1e-3), restraints=[restraint])])
    return s, ParameterTable(s, LAB)


def _rows(s, table):
    tt = np.arange(20.0, 60.0, 0.1)
    model = compile_model(s, LAB, PatternData(two_theta=tt.tolist(),
                                              intensity=np.ones_like(tt).tolist()),
                          mode="rietveld", moving_paths=set(table.moving_paths))
    return model


@pytest.mark.parametrize("dx, expect", [(0.30, 0.0), (0.40, (2.4 - 2.0) / 0.05)])
def test_tether_is_zero_inside_and_linear_outside(dx, expect):
    s, table = _pair(dx, TetherRestraint(atom_i=0, atom_j=1, max_distance=2.0,
                                         sigma=0.05, op_index=0))
    model = _rows(s, table)
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    assert rep.rows[0].kind == "tether"
    assert rep.rows[0].deviation_over_sigma == pytest.approx(expect, abs=1e-9)


@pytest.mark.parametrize("dx, expect", [(0.40, 0.0), (0.30, (1.8 - 2.0) / 0.05)])
def test_anti_bump_is_zero_outside_and_linear_inside(dx, expect):
    s, table = _pair(dx, AntiBumpRestraint(atom_i=0, atom_j=1, min_distance=2.0,
                                           sigma=0.05, op_index=0))
    model = _rows(s, table)
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    assert rep.rows[0].kind == "anti_bump"
    assert rep.rows[0].deviation_over_sigma == pytest.approx(expect, abs=1e-9)


@pytest.mark.parametrize("cls, dx", [
    (TetherRestraint, 0.40), (TetherRestraint, 0.30), (TetherRestraint, 1/3 + 1e-4),
    (AntiBumpRestraint, 0.30), (AntiBumpRestraint, 0.40), (AntiBumpRestraint, 1/3 - 1e-4)])
def test_analytic_row_matches_a_central_difference_either_side_of_the_kink(cls, dx):
    key = "max_distance" if cls is TetherRestraint else "min_distance"
    s, table = _pair(dx, cls(atom_i=0, atom_j=1, sigma=0.05, op_index=0, **{key: 2.0}))
    model = _rows(s, table)
    n_data = len(model.tt)
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    h = 1e-7
    for c in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        fd = (residual(tp)[n_data] - residual(tm)[n_data]) / (2 * h)
        assert jac[n_data, c] == pytest.approx(fd, rel=1e-5, abs=1e-6), (cls, dx, c)


def test_one_sided_rows_leave_the_data_statistics_alone():
    s, table = _pair(0.30, AntiBumpRestraint(atom_i=0, atom_j=1, min_distance=2.0,
                                             sigma=0.05, op_index=0))
    model = _rows(s, table)
    bare = s.model_copy(deep=True)
    bare.phases[0].restraints = []
    model0 = _rows(bare, ParameterTable(bare, LAB))
    values = table.decode(table.x0())
    assert np.array_equal(model.evaluate(values), model0.evaluate(values))
    assert len(_make_residual(model, table)(table.x0())) == len(model.tt) + 1


def _body_phase() -> Phase:
    P = Parameter
    seed = Atom(label="Li", species="Li", x=P(value=0.50), y=P(value=0.50), z=P(value=0.50))
    phase = Phase(name="p", space_group="P-1", cell=Cell.cubic(7.0), atoms=[seed])
    tmpl = np.array([[0.0, 0.0, 0.0], [1.25, 0.0, 0.0], [-0.6, 1.1, 0.0]])
    return add_body(phase, "co2", ["C1", "O1", "O2"], ["C", "O", "O"], tmpl,
                    (0.31, 0.42, 0.27))


def test_the_pair_list_is_complete_and_states_no_unasked_minimum():
    phase = _body_phase()
    rows = anti_bump_restraints(phase, {("Li", "O"): 1.9, ("O", "O"): 2.6},
                                margin=10.0)
    # no row inside the body, none for a pair nobody gave a minimum for
    sp = [a.species for a in phase.atoms]
    for r in rows:
        assert {sp[r.atom_i], sp[r.atom_j]} in ({"Li", "O"}, {"O"})
        # never the body's own copy of an intra-body pair
        assert not ({r.atom_i, r.atom_j} <= {1, 2, 3} and r.op_index == 0
                    and r.translation == (0, 0, 0))
    # completeness against a brute-force count of images under the cut
    from rietx.crystallography.structure_factor import compile_phase_sites
    from rietx.model.restraints import _metric_g
    sites = compile_phase_sites(phase)
    g = _metric_g(phase.cell.lengths_angles())
    xyz = [np.array([a.x.value, a.y.value, a.z.value]) for a in phase.atoms]
    expected = 0
    for i in range(4):
        for j in range(i, 4):
            body_pair = {i, j} <= {1, 2, 3}
            key = tuple(sorted((sp[i], sp[j])))
            r0 = {("Li", "O"): 1.9, ("O", "O"): 2.6}.get(key)
            if r0 is None:
                continue
            for k, (R, t) in enumerate(zip(*sites.ops[j], strict=True)):
                for n in np.ndindex(11, 11, 11):     # exhaustive for a 10 Å cut
                    shift = np.array(n) - 5
                    if body_pair and k == 0 and not shift.any():
                        continue          # op 0 of P-1 is the identity
                    dx = np.asarray(R) @ xyz[j] + np.asarray(t) + shift - xyz[i]
                    d = float(np.sqrt(dx @ g @ dx))
                    if 1e-3 < d < r0 + 10.0:
                        expected += 1
    assert len(rows) == expected > 0
    assert anti_bump_restraints(phase, 1.0, exclude_same_body=False, margin=0.4)


def test_the_pair_list_does_not_depend_on_the_stored_cell():
    """Shifting an atom by whole lattice vectors is the same structure, so the
    pair list keeps the same contact: P2₁ toy, Li and the 2₁ image of an O
    2.0 Å apart.  The shell about n = 0 lost it once the stored coordinates
    sat two cells apart (a body placed about any origin, a free atom anywhere)."""
    from rietx.schemas.structure import Atom, Cell, Phase
    cell = Cell(a=Parameter(value=5.0), b=Parameter(value=6.0), c=Parameter(value=7.0),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))
    for shift in ([0, 0, 0], [1, 0, 0], [2, 0, 0], [-3, 2, 1], [0, 0, 5]):
        li = np.array([0.10, 0.10, 0.10]) + shift
        o = np.array([-0.10, -0.40, -0.10 + 2.0 / 7.0])
        ph = Phase(name="t", space_group="P 1 21 1", cell=cell, atoms=[
            Atom(label="Li1", species="Li", x=Parameter(value=li[0]),
                 y=Parameter(value=li[1]), z=Parameter(value=li[2])),
            Atom(label="O1", species="O", x=Parameter(value=o[0]),
                 y=Parameter(value=o[1]), z=Parameter(value=o[2]))])
        rows = anti_bump_restraints(ph, {("Li", "O"): 2.5}, margin=0.0)
        assert len(rows) == 1, shift
        r = rows[0]
        img = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]]) @ o + [0, 0.5, 0] + r.translation
        d = (img - li) * [5.0, 6.0, 7.0]
        assert float(np.linalg.norm(d)) == pytest.approx(2.0, abs=1e-9), shift


# ------------------------------------------------------------ inside a staged fit
def _three_atoms(d_lio: float) -> Structure:
    """Li, O and a heavy Br in a P1 cubic 6 Å cell, Li–O ``d_lio`` Å apart
    along a; an anti-bump at 2.0 Å and a tether at 3.0 Å on that pair."""
    P = Parameter
    return Structure(phases=[Phase(
        name="p", space_group="P1", cell=Cell.cubic(6.0),
        atoms=[Atom(label="Li1", species="Li", x=P(value=0.20), y=P(value=0.30),
                    z=P(value=0.40)),
               Atom(label="O1", species="O", x=P(value=0.20 + d_lio / 6.0),
                    y=P(value=0.30), z=P(value=0.40)),
               Atom(label="Br1", species="Br", x=P(value=0.70), y=P(value=0.75),
                    z=P(value=0.85))],
        scale=P(value=1e-3, min=0.0, transform="softplus"),
        restraints=[AntiBumpRestraint(atom_i=0, atom_j=1, min_distance=2.0,
                                      sigma=0.05, op_index=0),
                    TetherRestraint(atom_i=0, atom_j=1, max_distance=3.0,
                                    sigma=0.05, op_index=0)])])


def test_the_rows_stay_in_a_staged_fit_whichever_side_they_end_on():
    """The rows are explicit, so a plan carries both for every stage: here the
    anti-bump starts active (Li–O 1.7 Å) and the fit moves the pair to the
    truth (2.3 Å), where both rows are flat; the report still lists both, at
    zero, and the data statistics are those of the data rows alone."""
    from rietx import Refinement
    from rietx.strategy.staged import RefinementPlan, Stage

    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    truth = _three_atoms(2.3)
    tt = np.arange(10.0, 90.0, 0.01)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    start = _three_atoms(1.7)
    t0 = ParameterTable(start, ins)
    rows0 = summarise_restraints(_rows(start, t0).restraints, t0.decode(t0.x0())).rows
    assert rows0[0].deviation < 0            # the anti-bump is active at the start
    ref = Refinement(start, ins, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("scale", ["phases.*.scale", "instrument.background.*"], max_iter=50),
        Stage("xyz", ["phases.*.scale", "instrument.background.*",
                      "phases.*.atoms.1.dof.0"], max_iter=100)]))
    rep = result.restraints
    assert rep is not None and rep.n_restraints == 2
    assert [r.kind for r in rep.rows] == ["anti_bump", "tether"]
    assert all(r.deviation == 0.0 for r in rep.rows), rep.rows
    assert rep.rows[0].computed == pytest.approx(2.3, abs=0.02)
    _save_fit_png(result, "one_sided_restraints_li_o")


OUT = __import__("pathlib").Path(__file__).parent / "output"


def _save_fit_png(result, name: str) -> None:
    """obs/calc/diff to ``tests/output/`` (tests/CLAUDE.md § Running)."""
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{name}.png"))
    plt.close("all")
    assert (OUT / f"{name}.png").stat().st_size > 0


# ------------------------------------- a torsion inside a body (WP-2144, #1507)
CHAIN_LABELS = ["N1", "C2", "C3", "C4", "C5", "O6"]
CHAIN_RULE = {("N", "O"): 3.0, ("Li", "O"): 1.0}
#: wide enough to list N1 against O6 in the next cell along −a, a neighbouring
#: molecule, so the phase carries anti-bump rows and none inside one copy
CHAIN_MARGIN = 16.0


def _chain_phase(t1: float, t2: float, *, torsions: bool = True) -> Phase:
    """A planar zigzag N1–C2–C3–C4–C5–O6 (bonds 1.5 Å) as one body in a 20 Å
    P1 cell, with torsions about C2–C3 (moving C4, C5, O6) and C4–C5 (moving
    O6) at twists ``t1`` and ``t2``.  At (0, 0) N1···O6 is 4.50 Å; at
    (−120, −120) it is 1.50 Å, half the stated 3.0 Å minimum (#1507)."""
    from rietx.schemas.structure import BodyTorsion

    c, s = 1.5 * np.cos(np.radians(54.75)), 1.5 * np.sin(np.radians(54.75))
    template = np.array([[k * c, (k % 2) * s, 0.0] for k in range(6)])
    P = Parameter
    seed = Atom(label="Li", species="Li", x=P(value=0.9), y=P(value=0.9), z=P(value=0.9))
    phase = Phase(name="p", space_group="P1", cell=Cell.cubic(20.0), atoms=[seed])
    tors = ([BodyTorsion(name="t1", axis=("C2", "C3"), moves=["C4", "C5", "O6"], angle=t1),
             BodyTorsion(name="t2", axis=("C4", "C5"), moves=["O6"], angle=t2)]
            if torsions else [])
    return add_body(phase, "chain", CHAIN_LABELS, ["N", "C", "C", "C", "C", "O"],
                    template, (0.5, 0.5, 0.5), torsions=tors)


def _chain_run(t1: float, t2: float, **build) -> tuple[Structure, list]:
    """The chain listed at (0, 0) and answered at (t1, t2): the run's answer,
    and the phase as the run started, as ``refine`` hands them over."""
    start = _chain_phase(0.0, 0.0)
    start.restraints = anti_bump_restraints(start, CHAIN_RULE, margin=CHAIN_MARGIN,
                                            **build)
    answer = _chain_phase(t1, t2)
    answer.restraints = list(start.restraints)
    return Structure(phases=[answer]), [start]


def _n1_o6(phase: Phase) -> float:
    x = {a.label: np.array([a.x.value, a.y.value, a.z.value]) * 20.0 for a in phase.atoms}
    return float(np.linalg.norm(x["N1"] - x["O6"]))


def test_a_torsion_that_folds_a_body_warns_that_its_contacts_are_unchecked():
    """The folded pair gets no row and no stale report, as #1507 found; the
    new warning names the body and the torsions that turned."""
    from rietx.model.restraints import stale_anti_bump_pairs
    from rietx.refine import _body_contacts_unchecked_diagnostics

    structure, since = _chain_run(-120.0, -120.0)
    phase = structure.phases[0]
    assert _n1_o6(since[0]) == pytest.approx(4.499, abs=1e-3)
    assert _n1_o6(phase) == pytest.approx(1.498, abs=1e-3)
    n1, o6 = (CHAIN_LABELS.index(k) + 1 for k in ("N1", "O6"))
    assert phase.restraints                         # neighbouring molecules are listed
    assert all(r.translation != (0, 0, 0) for r in phase.restraints
               if {r.atom_i, r.atom_j} == {n1, o6})
    assert stale_anti_bump_pairs(phase) == []
    (d,) = _body_contacts_unchecked_diagnostics(structure, since)
    assert d.code == "RESTRAINT_BODY_CONTACTS_UNCHECKED" and d.level == "warning"
    assert d.where == [f"p {k}" for k in CHAIN_LABELS]
    assert d.value == 2.0
    assert "contacts inside the molecule are not checked" in d.message
    assert "t1 0.0° → -120.0°" in d.message and "'chain'" in d.message


def test_rows_inside_the_body_are_counted_and_do_not_silence_it():
    """A list built with ``exclude_same_body=False`` holds rows inside the
    body, and a hand row covers one pair; neither makes the end-of-run search
    look inside the body, so the warning still fires and counts them."""
    from rietx.model.restraints import body_own_rows
    from rietx.refine import _body_contacts_unchecked_diagnostics

    kept = _chain_run(-120.0, -120.0, exclude_same_body=False)
    rows = body_own_rows(kept[0].phases[0])
    assert list(rows) == ["chain"] and rows["chain"] > 0
    (d,) = _body_contacts_unchecked_diagnostics(*kept)
    assert f"holds {rows['chain']} row(s) inside one copy" in d.message
    assert "contacts inside the molecule are not checked" in d.message


def test_an_unturned_torsion_or_a_rigid_body_stays_silent():
    """Silent where the torsions did not move, for a body with no torsion,
    and for a phase the run did not search (no anti-bump row at the start)."""
    from rietx.model.restraints import body_own_rows
    from rietx.refine import _body_contacts_unchecked_diagnostics

    assert _body_contacts_unchecked_diagnostics(*_chain_run(0.0, 0.0)) == []
    # declared at −180, written back wrapped to 180 with nothing turned
    unturned, since = _chain_run(0.0, 0.0)
    since[0] = _chain_phase(-180.0, 0.0).model_copy(
        update={"restraints": since[0].restraints})
    unturned = Structure(phases=[_chain_phase(180.0, 0.0).model_copy(
        update={"restraints": since[0].restraints})])
    assert _body_contacts_unchecked_diagnostics(unturned, since) == []
    rigid = _chain_phase(0.0, 0.0, torsions=False)
    rigid.restraints = anti_bump_restraints(rigid, CHAIN_RULE, margin=CHAIN_MARGIN)
    assert body_own_rows(rigid) == {}
    folded = _chain_phase(-120.0, -120.0)
    assert body_own_rows(folded) == {}                         # no anti-bump row
    folded.restraints = anti_bump_restraints(folded, CHAIN_RULE, margin=CHAIN_MARGIN)
    assert body_own_rows(folded) == {"chain": 0}
    assert _body_contacts_unchecked_diagnostics(
        Structure(phases=[folded]), [None]) == []              # nothing searched
