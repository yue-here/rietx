"""Planarity rows and ``RESTRAINT_PAIRS_STALE`` (WP-1809, the second half).

A planarity restraint gives one row per atom, √w·dₖ/σ, dₖ the signed distance
to the least-squares plane through the set (Schomaker et al. 1959, *Acta
Cryst.* 12, 600; TOPAS's ``Flatten``/``AI_Flatten``).  Each check is placed
where it can fail: known out-of-plane distances on a set whose plane is known;
the eigenvector derivative against a central difference, cell included and
through a symmetry image; a line refused by name; and a fit in which the
restraint flattens a ring the data hold buckled, beside the same fit without
it.  The stale-pair search is checked on a torsion that carries an atom
inside an anti-bump minimum from outside the list, against a torsion that
does not, and at the end of a plan.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography.bodies import add_body, place_body_atoms
from rietx.model.forward import compile_model
from rietx.model.restraints import (
    anti_bump_contact_keys,
    anti_bump_restraints,
    stale_anti_bump_pairs,
    summarise_restraints,
)
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    Atom,
    BodyTorsion,
    Cell,
    Phase,
    PlanarityRestraint,
    Structure,
)
from tests.test_one_sided_restraints import _save_fit_png

P = Parameter
LAB = Instrument.debye_scherrer(wavelength=1.5406)


def _cell(a, b, c, al=90.0, be=90.0, ga=90.0, vary=False) -> Cell:
    return Cell(**{k: P(value=v, vary=vary) for k, v in
                   zip(("a", "b", "c", "alpha", "beta", "gamma"),
                       (a, b, c, al, be, ga), strict=True)})


def _phase(xyz, restraint, *, cell=None, sg="P1", vary=False) -> Phase:
    return Phase(name="p", space_group=sg, cell=cell or _cell(10.0, 10.0, 10.0),
                 atoms=[Atom(label=f"C{k}", species="C", x=P(value=x, vary=vary),
                             y=P(value=y, vary=vary), z=P(value=z, vary=vary))
                        for k, (x, y, z) in enumerate(xyz)],
                 scale=P(value=1e-3), restraints=[restraint])


def _compiled(phase):
    s = Structure(phases=[phase])
    table = ParameterTable(s, LAB)
    tt = np.arange(20.0, 40.0, 0.1)
    model = compile_model(s, LAB, PatternData(two_theta=tt.tolist(),
                                              intensity=np.ones_like(tt).tolist()),
                          mode="rietveld", moving_paths=set(table.moving_paths))
    return model, table


def test_a_known_plane_gives_its_out_of_plane_distances():
    """A square in z = 5 Å with its corners alternately ±0.3 Å out of it: the
    least-squares plane is z = 5 Å, so the rows are ±0.3/σ in atom order."""
    e = 0.03
    xyz = [(0.4, 0.4, 0.5 + e), (0.6, 0.4, 0.5 - e), (0.6, 0.6, 0.5 + e),
           (0.4, 0.6, 0.5 - e)]
    model, table = _compiled(_phase(xyz, PlanarityRestraint(atoms=[0, 1, 2, 3],
                                                            sigma=0.01)))
    assert model.restraints.n_rows == 4
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    got = [r.computed for r in rep.rows]
    sign = math.copysign(1.0, got[0])
    assert got == pytest.approx([0.3 * sign, -0.3 * sign, 0.3 * sign, -0.3 * sign],
                                abs=1e-12)
    assert [r.kind for r in rep.rows] == ["planarity"] * 4
    assert rep.rows[2].atoms == [2, 0, 1, 3]       # the row's atom first
    assert rep.restraint_chi2 == pytest.approx(4 * 30.0 ** 2, rel=1e-12)
    # the residual rows are the same numbers the report gives
    n_data = len(model.tt)
    rows = _make_residual(model, table)(table.x0())[n_data:]
    assert rows == pytest.approx([g / 0.01 for g in got], abs=1e-9)


def test_a_flat_set_has_zero_rows():
    xyz = [(0.4, 0.4, 0.5), (0.6, 0.41, 0.5), (0.62, 0.6, 0.5), (0.4, 0.63, 0.5),
           (0.5, 0.7, 0.5)]
    model, table = _compiled(_phase(xyz, PlanarityRestraint(atoms=list(range(5)),
                                                            sigma=0.01)))
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    assert max(abs(r.computed) for r in rep.rows) < 1e-12


def _fd_check(phase):
    model, table = _compiled(phase)
    n_data = len(model.tt)
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    assert jac.shape[0] - n_data == model.restraints.n_rows
    h = 1e-6
    for c in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        fd = (residual(tp)[n_data:] - residual(tm)[n_data:]) / (2 * h)
        assert jac[n_data:, c] == pytest.approx(fd, rel=5e-5, abs=1e-5), c


def test_the_eigenvector_derivative_matches_a_central_difference():
    """Every coordinate and all six cell parameters of a triclinic cell, on a
    buckled six-ring: the exact eigenvector derivative (Magnus 1985)."""
    xyz = [(0.10, 0.20, 0.30), (0.25, 0.22, 0.31), (0.30, 0.35, 0.28),
           (0.20, 0.45, 0.33), (0.07, 0.38, 0.27), (0.02, 0.27, 0.35)]
    _fd_check(_phase(xyz, PlanarityRestraint(atoms=list(range(6)), sigma=0.02),
                     cell=_cell(7.1, 8.3, 9.2, 81.0, 97.0, 104.0, vary=True),
                     vary=True))


def test_the_derivative_holds_through_a_symmetry_image():
    """A ring across an inversion centre: three atoms and their −x images
    (op 1 of P-1), so each atom enters two rows through R = −I."""
    xyz = [(0.62, 0.45, 0.52), (0.58, 0.60, 0.47), (0.44, 0.63, 0.53)]
    restraint = PlanarityRestraint(atoms=[0, 1, 2, 0, 1, 2], sigma=0.02,
                                   op_indices=[0, 0, 0, 1, 1, 1],
                                   translations=[(0, 0, 0)] * 3 + [(1, 1, 1)] * 3)
    phase = _phase(xyz, restraint, sg="P-1", vary=True,
                   cell=_cell(7.1, 8.3, 9.2, 81.0, 97.0, 104.0, vary=True))
    model, table = _compiled(phase)
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    # centrosymmetric about (½,½,½): the plane passes through the centre and
    # each atom's image sits at minus its distance
    d = [r.computed for r in rep.rows]
    assert d[3:] == pytest.approx([-v for v in d[:3]], abs=1e-12)
    assert max(abs(v) for v in d) > 0.05
    _fd_check(phase)


def test_a_line_is_refused_by_name():
    xyz = [(0.1, 0.1, 0.1), (0.2, 0.2, 0.2), (0.3, 0.3, 0.3), (0.45, 0.45, 0.45)]
    with pytest.raises(ValueError, match="lie on a line"):
        _compiled(_phase(xyz, PlanarityRestraint(atoms=[0, 1, 2, 3], sigma=0.01)))


def test_three_atoms_and_a_short_image_list_are_refused():
    with pytest.raises(ValueError):
        PlanarityRestraint(atoms=[0, 1, 2], sigma=0.01)
    with pytest.raises(ValueError, match="one per atom"):
        PlanarityRestraint(atoms=[0, 1, 2, 3], sigma=0.01, op_indices=[0, 0])


# ---------------------------------------------------------- the positive arm
def _ring(buckle: float, restrained: bool) -> Structure:
    """A C₆ ring buckled ±``buckle`` Å (chair-like alternation) and a Br."""
    atoms = []
    for k in range(6):
        ang = 2 * math.pi * k / 6
        z = buckle if k % 2 else -buckle
        atoms.append(Atom(label=f"C{k}", species="C",
                          x=P(value=0.5 + 1.39 * math.cos(ang) / 7.0),
                          y=P(value=0.5 + 1.39 * math.sin(ang) / 8.0),
                          z=P(value=0.5 + z / 9.0)))
    atoms.append(Atom(label="Br1", species="Br", x=P(value=0.10),
                      y=P(value=0.15), z=P(value=0.20)))
    restraints = ([PlanarityRestraint(atoms=list(range(6)), sigma=0.001)]
                  if restrained else [])
    return Structure(phases=[Phase(name="r", space_group="P1",
                                   cell=_cell(7.0, 8.0, 9.0), atoms=atoms,
                                   scale=P(value=1e-3, min=0.0),
                                   restraints=restraints)])


def _rms_out_of_plane(phase) -> float:
    x = np.array([[a.x.value * 7.0, a.y.value * 8.0, a.z.value * 9.0]
                  for a in phase.atoms[:6]])
    d = x - x.mean(axis=0)
    return math.sqrt(np.linalg.eigvalsh(d.T @ d)[0] / 6)


def test_the_restraint_flattens_a_ring_the_data_hold_buckled():
    """Positive arm and its control, from one pattern simulated off the
    buckled ring (±0.15 Å): free coordinates and no restraint end buckled
    (0.148 Å rms measured), the same fit with the rows ends flat to its σ
    (1.2e-3 Å measured at σ = 1e-3 Å)."""
    from rietx import Refinement
    from rietx.strategy.staged import RefinementPlan, Stage

    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    truth = _ring(0.15, False)
    tt = np.arange(8.0, 100.0, 0.01)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(5).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())
    plan = RefinementPlan(stages=[
        Stage("scale", ["phases.*.scale", "instrument.background.*"], max_iter=50),
        Stage("xyz", ["phases.*.scale", "instrument.background.*",
                      "phases.*.atoms.[0-5].dof.*"], max_iter=200)])
    rms = {}
    for restrained in (False, True):
        ref = Refinement(_ring(0.15, restrained), ins, history=False)
        result = ref.fit(pattern, plan=plan)
        rms[restrained] = _rms_out_of_plane(ref.structure.phases[0])
        if restrained:
            rep = result.restraints
            assert rep.n_restraints == 6
            assert [r.kind for r in rep.rows] == ["planarity"] * 6
    assert rms[False] > 0.1, rms
    assert rms[True] < 3e-3, rms
    _save_fit_png(result, "planarity_restraints_ring")


# ------------------------------------------------- RESTRAINT_PAIRS_STALE
def _torsion_phase(angle: float) -> Phase:
    """Li and O3 free, a C1–C2–O1–O2 body whose torsion about C1–C2 swings
    O2 (on C1) through 180° towards the Li.  The anti-bump list is built at
    0°, where only the Li–O3 contact (2.4 Å) is inside r₀ + margin."""
    # the Li 1.8 Å beyond where O2 lands at 180°, along −y
    o2_far = np.array([0.5 - 0.7 / 12, 0.5 - 1.0 / 12, 0.5])
    li = o2_far + np.array([0.0, -1.8 / 12, 0.0])
    o3 = li + np.array([-2.4 / 12, 0.0, 0.0])
    seed = Phase(name="p", space_group="P1", cell=_cell(12.0, 12.0, 12.0), atoms=[
        Atom(label="Li1", species="Li", x=P(value=li[0]), y=P(value=li[1]),
             z=P(value=li[2])),
        Atom(label="O3", species="O", x=P(value=o3[0]), y=P(value=o3[1]),
             z=P(value=o3[2]))])
    tmpl = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [2.2, 1.0, 0.0],
                     [-0.7, 1.0, 0.0]])
    torsion = BodyTorsion(name="t", axis=("C1", "C2"), moves=["O2"], angle=0.0)
    phase = add_body(seed, "frag", ["C1", "C2", "O1", "O2"], ["C", "C", "O", "O"],
                     tmpl, (0.5, 0.5, 0.5), centre=False, torsions=[torsion])
    rows = anti_bump_restraints(phase, {("Li", "O"): 2.0}, margin=0.5)
    phase = phase.model_copy(update={"restraints": rows})
    body = phase.rigid_bodies[0]
    turned = body.model_copy(update={"torsions": [
        body.torsions[0].model_copy(update={"angle": angle})]})
    return place_body_atoms(phase.model_copy(update={"rigid_bodies": [turned]}))


def test_a_torsion_that_carries_an_atom_inside_r0_is_named():
    start = _torsion_phase(0.0)
    labels = [a.label for a in start.atoms]
    listed = {(labels[r.atom_i], labels[r.atom_j]) for r in start.restraints}
    assert listed == {("Li1", "O3")}             # the list holds one contact
    assert stale_anti_bump_pairs(start) == []
    turned = _torsion_phase(180.0)
    stale = stale_anti_bump_pairs(turned)
    assert len(stale) == 1
    i, j, d, r0 = stale[0]
    assert {labels[i], labels[j]} == {"Li1", "O2"}
    assert d == pytest.approx(1.8, abs=1e-9) and r0 == 2.0


def test_a_torsion_that_stays_outside_r0_is_not_named():
    """The control: 60° moves O2 but keeps it 3 Å or more from the Li."""
    assert stale_anti_bump_pairs(_torsion_phase(60.0)) == []


def test_no_anti_bump_row_means_no_search():
    phase = _torsion_phase(180.0).model_copy(update={"restraints": []})
    assert stale_anti_bump_pairs(phase) == []


def _li_o_o(d_lio2: float, listed_o2: bool) -> Structure:
    """Li, O1 2.6 Å along b and O2 ``d_lio2`` Å along a, in a P1 cubic 6 Å cell;
    an anti-bump list (r₀ 2.0 Å) built at Li–O2 3.0 Å, holding Li–O2 only when
    ``listed_o2`` (margin 1.5 rather than 0.7)."""
    def build(d):
        return Phase(name="p", space_group="P1", cell=Cell.cubic(6.0), atoms=[
            Atom(label="Li1", species="Li", x=P(value=0.20), y=P(value=0.30),
                 z=P(value=0.40)),
            Atom(label="O1", species="O", x=P(value=0.20), y=P(value=0.30 + 2.6 / 6),
                 z=P(value=0.40)),
            Atom(label="O2", species="O", x=P(value=0.20 + d / 6), y=P(value=0.30),
                 z=P(value=0.40)),
            Atom(label="Br1", species="Br", x=P(value=0.70), y=P(value=0.75),
                 z=P(value=0.85))],
            scale=P(value=1e-3, min=0.0))
    rows = anti_bump_restraints(build(3.0), {("Li", "O"): 2.0}, sigma=0.5,
                                margin=1.5 if listed_o2 else 0.7)
    return Structure(phases=[build(d_lio2).model_copy(update={"restraints": rows})])


@pytest.mark.parametrize("listed_o2", [False, True])
def test_the_plan_end_names_a_pair_that_entered_from_outside_the_list(listed_o2):
    """The truth has Li–O2 at 1.8 Å; the fit starts at 2.3 Å and frees O2.
    Built without that pair, the list cannot hold it back, and the plan end
    names it; built with it (a loose σ, so the data still win), no contact is
    unlisted and the code stays silent."""
    from rietx import Refinement
    from rietx.strategy.staged import RefinementPlan, Stage

    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    truth = _li_o_o(1.8, listed_o2)
    tt = np.arange(10.0, 90.0, 0.01)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    ref = Refinement(_li_o_o(2.3, listed_o2), ins, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("scale", ["phases.*.scale", "instrument.background.*"], max_iter=50),
        Stage("xyz", ["phases.*.scale", "instrument.background.*",
                      "phases.*.atoms.2.dof.0"], max_iter=100)]))
    li_o2 = abs(ref.structure.phases[0].atoms[2].x.value - 0.20) * 6.0
    assert li_o2 < 2.0, li_o2                     # the pair did enter r₀
    _save_fit_png(result, f"planarity_restraints_stale_{int(listed_o2)}")
    stale = [d for d in result.diagnostics if d.code == "RESTRAINT_PAIRS_STALE"]
    if listed_o2:
        assert stale == []
    else:
        assert len(stale) == 1
        assert stale[0].where == ["p Li1", "p O2"]
        assert stale[0].value == 1.0
        assert "Li1–O2" in stale[0].message


def test_a_symmetry_copy_of_a_listed_contact_is_not_named():
    """P-1 doubles every contact through the centre; the builder lists both
    images of a short Li–O contact and the search must not call either one
    unlisted, nor the copy a second contact."""
    ph = Phase(name="p", space_group="P-1", cell=Cell.cubic(6.0), atoms=[
        Atom(label="Li1", species="Li", x=P(value=0.10), y=P(value=0.10),
             z=P(value=0.10)),
        Atom(label="O1", species="O", x=P(value=0.10 + 1.9 / 6), y=P(value=0.10),
             z=P(value=0.10))])
    rows = anti_bump_restraints(ph, {("Li", "O"): 2.0}, margin=0.0)
    assert rows
    assert stale_anti_bump_pairs(ph.model_copy(update={"restraints": rows})) == []
    # one row kept: the other images of the same contact are not stale either
    assert stale_anti_bump_pairs(ph.model_copy(update={"restraints": rows[:1]})) == []


def test_restraint_rows_survive_a_json_round_trip():
    r = PlanarityRestraint(atoms=[0, 1, 2, 0], sigma=0.01, op_indices=[None, 0, 0, 1],
                           translations=[(0, 0, 0)] * 3 + [(1, 0, 0)])
    ph = _phase([(0.1, 0.2, 0.3)] * 3, r)
    assert Phase.model_validate_json(ph.model_dump_json()).restraints[0] == r


# ------------------------------------- review round 1 (yue-here, #995)
def _pattern_of(structure: Structure, ins, seed: int) -> PatternData:
    tt = np.arange(10.0, 90.0, 0.01)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _bonded_c(listed_bond: bool) -> Structure:
    """Five carbons in a 12 Å cell: C1–C2 bonded at 1.5 Å, C3–C4 3.0 Å apart,
    C5 4.0 Å from C3 (past r₀ + margin, so unlisted).  A 3.3 Å C–C rule; the list drops the bonded pair unless ``listed_bond``."""
    ang = [(0.30, 0.30, 0.30), (0.30 + 1.5 / 12, 0.30, 0.30),
           (0.70, 0.70, 0.70), (0.70 + 3.0 / 12, 0.70, 0.70),
           (0.70, 0.70 + 4.0 / 12, 0.70)]
    ph = Phase(name="p", space_group="P1", cell=_cell(12.0, 12.0, 12.0),
               atoms=[Atom(label=f"C{k + 1}", species="C", x=P(value=x),
                           y=P(value=y), z=P(value=z))
                      for k, (x, y, z) in enumerate(ang)],
               scale=P(value=1e-3, min=0.0))
    rows = anti_bump_restraints(ph, {("C", "C"): 3.3}, margin=0.5)
    if not listed_bond:
        rows = [r for r in rows if {r.atom_i, r.atom_j} != {0, 1}]
    assert any({r.atom_i, r.atom_j} == {2, 3} for r in rows)
    return Structure(phases=[ph.model_copy(update={"restraints": rows})])


def test_a_pair_left_out_on_purpose_is_not_named_but_a_drifted_one_is():
    """The bond C1–C2 (1.5 Å, inside the 3.3 Å rule) was dropped from the list
    by the caller; without ``since`` the search names it, with the contacts of
    the starting coordinates it does not.  C5 walking in from 4 Å to 2.5 Å of C3
    is named either way."""
    ph = _bonded_c(False).phases[0]
    assert [(i, j) for i, j, _, _ in stale_anti_bump_pairs(ph)] == [(0, 1)]
    since = anti_bump_contact_keys(ph)
    assert stale_anti_bump_pairs(ph, since=since) == []
    moved = ph.model_copy(update={"atoms": [
        *ph.atoms[:4],
        ph.atoms[4].model_copy(update={"y": P(value=0.70 + 2.5 / 12)})]})
    stale = stale_anti_bump_pairs(moved, since=since)
    assert [(i, j) for i, j, _, _ in stale] == [(2, 4)]
    assert stale[0][2] == pytest.approx(2.5)


def test_a_bond_left_out_of_the_list_raises_no_warning_through_a_fit():
    from rietx import Refinement
    from rietx.strategy.staged import RefinementPlan, Stage

    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    s = _bonded_c(False)
    pattern = _pattern_of(s, ins, 11)
    ref = Refinement(s, ins, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("scale", ["phases.*.scale", "instrument.background.*"],
              max_iter=30)]))
    assert [d for d in result.diagnostics if d.code == "RESTRAINT_PAIRS_STALE"] == []
    _save_fit_png(result, "planarity_restraints_bond_left_out")


def test_run_stage_names_a_pair_that_entered_from_outside_the_list():
    """The ``fit`` test's fixture, driven one stage at a time: the warning
    comes from ``run_stage`` too."""
    from rietx import Refinement
    from rietx.strategy.staged import Stage

    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    pattern = _pattern_of(_li_o_o(1.8, False), ins, 3)
    ref = Refinement(_li_o_o(2.3, False), ins, history=False)
    result = ref.run_stage(pattern, Stage(
        "xyz", ["phases.*.scale", "instrument.background.*",
                "phases.*.atoms.2.dof.0"], max_iter=100))
    stale = [d for d in result.diagnostics if d.code == "RESTRAINT_PAIRS_STALE"]
    assert len(stale) == 1 and stale[0].where == ["p Li1", "p O2"]
    _save_fit_png(result, "planarity_restraints_run_stage")


def _ten_ring_beside_its_image() -> Phase:
    """Ten C on a 2 Å circle in the b–c plane about (0.09, 0, 0), under P-1 in
    a 20 Å cell: the inversion image of the ring is a parallel ring 3.6 Å
    away, so atom 5's copy there sits 3.6 Å from atom 0 and atom 5 itself
    4.0 Å from it."""
    atoms = []
    for k in range(10):
        t = 2 * math.pi * k / 10
        atoms.append(Atom(label=f"C{k}", species="C", x=P(value=0.09),
                          y=P(value=2.0 * math.cos(t) / 20.0),
                          z=P(value=2.0 * math.sin(t) / 20.0)))
    return Phase(name="p", space_group="P-1", cell=_cell(20.0, 20.0, 20.0),
                 atoms=atoms, scale=P(value=1e-3),
                 restraints=[PlanarityRestraint(atoms=list(range(10)), sigma=0.01)])


def test_a_big_plane_stays_in_one_molecule_beside_a_close_neighbour():
    model, table = _compiled(_ten_ring_beside_its_image())
    plane = model.restraints.items[0]
    assert all(np.array_equal(R, np.eye(3)) for R in plane.R)
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    assert max(abs(r.computed) for r in rep.rows) < 1e-12


def test_planarity_indices_are_range_checked_like_bond_indices():
    for bad in (-1, 4):
        with pytest.raises(ValueError, match="atoms\\[3\\]"):
            _phase([(0.1, 0.2, 0.3), (0.2, 0.3, 0.4), (0.3, 0.1, 0.2),
                    (0.4, 0.4, 0.1)],
                   PlanarityRestraint(atoms=[0, 1, 2, bad], sigma=0.01))


def test_a_translation_with_no_operation_is_refused_rather_than_ignored():
    with pytest.raises(ValueError, match="no op_index"):
        PlanarityRestraint(atoms=[0, 1, 2, 3], sigma=0.01,
                           translations=[(0, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0)])
    # the first entry's translation is honoured, so it stays legal
    PlanarityRestraint(atoms=[0, 1, 2, 3], sigma=0.01,
                       translations=[(1, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)])


def test_a_normal_perpendicular_to_the_frozen_one_keeps_its_rows():
    """``xp.sign(0)`` was 0, so a plane whose current normal is perpendicular
    to the compile-time one lost every row; the host path takes +1 there.  The
    frozen normal is turned a quarter turn by hand: the rows must still be the
    distances to the plane, whose sum of squares is the smallest scatter
    eigenvalue."""
    from rietx.model.restraints import _plane_distances

    xyz = np.array([(0.4, 0.4, 0.53), (0.6, 0.4, 0.47), (0.6, 0.6, 0.53),
                    (0.4, 0.6, 0.47)])      # the scatter is diagonal: normal = ±z
    model, table = _compiled(_phase(
        [tuple(v) for v in xyz], PlanarityRestraint(atoms=[0, 1, 2, 3], sigma=0.01)))
    plane = model.restraints.items[0]
    plane.normal = np.array([1.0, 0.0, 0.0])        # the true normal is ~z
    d = np.asarray(_plane_distances(plane, table.decode(table.x0())), dtype=float)
    cart = xyz * 10.0
    cart -= cart.mean(axis=0)
    assert np.sum(d * d) == pytest.approx(np.linalg.eigvalsh(cart.T @ cart)[0],
                                          rel=1e-9)
