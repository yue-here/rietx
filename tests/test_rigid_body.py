"""Rigid bodies: schema, collector, anchored rotation, the body's own rows (WP-1805).

A body is a ``RigidBody`` over a phase's own atoms; its origin refines on the
site basis and its orientation as an anchored rotation increment, and its
atoms' coordinates are the rows of a derived block (WP-1804).  The positive
arms here are the ones WP-1803's record names: an orientation recovered from a
synthetic pattern started 3° and 10° off, with its esd covering the truth; a
stale anchor caught at the next build; a tie from a rotation increment refused.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography import rotation
from rietx.crystallography.bodies import (
    add_body,
    body_fractional,
    body_from_atoms,
    place_body_atoms,
)
from rietx.model.forward import compile_model
from rietx.params.vector import AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, RigidBody, Structure
from rietx.strategy.staged import RefinementPlan, Stage

INS = Instrument.debye_scherrer(wavelength=1.5406)
INS.profile.w.value = 8e-3
CELL = (7.21, 8.13, 9.47, 84.3, 97.6, 104.2)          # WP-1803's triclinic cell
BODY_GLOBS = ["phases.*.scale", "instrument.background.*",
              "phases.*.rigid_bodies.*.origin.dof.*",
              "phases.*.rigid_bodies.*.rotation.*"]


def c6br() -> np.ndarray:
    """WP-1803's body: ideal D6h ring (C–C 1.39 Å) and a C–Br of 1.90 Å."""
    ring = np.array([[1.39 * math.cos(k * math.pi / 3),
                      1.39 * math.sin(k * math.pi / 3), 0.0] for k in range(6)])
    return np.vstack([ring, ring[0] * (1.0 + 1.90 / 1.39)])


def _cell() -> Cell:
    P = Parameter
    return Cell(a=P(value=CELL[0]), b=P(value=CELL[1]), c=P(value=CELL[2]),
                alpha=P(value=CELL[3]), beta=P(value=CELL[4]), gamma=P(value=CELL[5]))


def body_structure(q, origin=(0.31, 0.42, 0.27), sg="P-1") -> Structure:
    seed = Atom(label="seed", species="C", x=Parameter(value=0.0),
                y=Parameter(value=0.0), z=Parameter(value=0.0))
    phase = Phase(name="c6br", space_group=sg, cell=_cell(), atoms=[seed],
                  scale=Parameter(value=1e-2, min=0.0, transform="softplus"))
    phase = add_body(phase, "c6br", [f"C{i}" for i in range(6)] + ["Br"],
                     ["C"] * 6 + ["Br"], c6br(), origin, orientation=q, biso=2.0)
    # the seed atom only lets the empty phase validate; the body is the phase
    phase = Phase.model_validate({**phase.model_dump(),
                                  "atoms": phase.model_dump()["atoms"][1:]})
    return Structure(phases=[phase])


def synthesize(structure: Structure, seed: int = 3) -> PatternData:
    tt = np.arange(8.0, 70.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, INS, blank, mode="rietveld")
    table = ParameterTable(structure, INS)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


Q_TRUE = rotation.canonical_quaternion(
    np.asarray(rotation.quaternion_from_vector(np.array([0.4, -0.7, 1.1]))))


def _turned(q, deg, axis=(0.3, 0.8, -0.5)):
    a = np.asarray(axis) / np.linalg.norm(axis)
    r = (np.asarray(rotation.matrix_from_vector(math.radians(deg) * a))
         @ np.asarray(rotation.matrix_from_quaternion(q)))
    return np.asarray(rotation.canonical_quaternion(rotation.quaternion_from_matrix(r)))


def _angle_deg(qa, qb) -> float:
    ra = np.asarray(rotation.matrix_from_quaternion(np.asarray(qa)))
    rb = np.asarray(rotation.matrix_from_quaternion(np.asarray(qb)))
    return math.degrees(float(np.linalg.norm(
        np.asarray(rotation.vector_from_matrix(ra @ rb.T)))))


# --------------------------------------------------------------- declaration
def test_a_body_over_placed_atoms_decodes_them_back():
    phase = Phase(name="t", space_group="P1", cell=_cell(), atoms=[
        Atom(label=f"A{i}", species="C", x=Parameter(value=0.1 + 0.07 * i),
             y=Parameter(value=0.2 + 0.03 * i * i), z=Parameter(value=0.5 - 0.05 * i))
        for i in range(5)])
    body = body_from_atoms(phase, [f"A{i}" for i in range(5)], "five")
    s = Structure(phases=[phase.model_copy(update={"rigid_bodies": [body]})])
    table = ParameterTable(s, INS)
    values = table.decode(table.x0())
    for j, atom in enumerate(phase.atoms):
        for c in "xyz":
            assert abs(values[f"phases.0.atoms.{j}.{c}"] - getattr(atom, c).value) < 1e-12
    paths = {e.path: e for e in table.entries}
    assert paths["phases.0.atoms.2.x"].locked
    assert "phases.0.atoms.2.dof.0" not in paths
    assert {f"phases.0.rigid_bodies.0.rotation.{k}" for k in range(3)} <= set(paths)
    assert {f"phases.0.rigid_bodies.0.origin.dof.{k}" for k in range(3)} <= set(paths)
    assert table.body_rows()["phases.0.atoms.4.z"] == "five"


def test_a_body_atom_refuses_vary_and_shared_membership():
    s = body_structure(Q_TRUE)
    s.phases[0].atoms[2].x.vary = True
    with pytest.raises(ValueError, match="placed by rigid body 'c6br'"):
        ParameterTable(s, INS)
    s = body_structure(Q_TRUE)
    phase = s.phases[0]
    twin = RigidBody(name="twin", atoms=["C0", "C1"], template=[(0, 0, 0), (1.39, 0, 0)],
                     origin=phase.rigid_bodies[0].origin)
    with pytest.raises(ValueError, match="RIGID_BODY_SHARED_ATOM"):
        Phase.model_validate({**phase.model_dump(),
                              "rigid_bodies": [*phase.model_dump()["rigid_bodies"],
                                               twin.model_dump()]})


def test_an_edited_body_atom_is_refused_as_drift_and_place_body_atoms_repairs():
    s = body_structure(Q_TRUE)
    s.phases[0].atoms[3].y.value += 0.01
    with pytest.raises(ValueError, match="RIGID_BODY_TEMPLATE_DRIFT"):
        ParameterTable(s, INS)
    fixed = Structure(phases=[place_body_atoms(s.phases[0])])
    ParameterTable(fixed, INS)


def test_a_body_on_a_special_position_is_refused_for_now():
    s = body_structure(Q_TRUE, origin=(0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="RIGID_BODY_NOT_INVARIANT"):
        ParameterTable(s, INS)


def _sulfate_on_the_pnma_mirror() -> Structure:
    """PbSO₄'s SO₄, Hill (1992) *J. Appl. Cryst.* 25, 589, Table 7: S, O1, O2
    on the 4c mirror and O3 general, so the body's centroid is general."""
    P = Parameter
    cell = Cell(a=P(value=8.482), b=P(value=5.398), c=P(value=6.959),
                alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))
    atoms = [Atom(label=lab, species=sp, x=P(value=x), y=P(value=y), z=P(value=z))
             for lab, sp, x, y, z in [("Pb", "Pb", 0.1879, 0.25, 0.1667),
                                      ("S", "S", 0.0633, 0.25, 0.6842),
                                      ("O1", "O", 0.908, 0.25, 0.596),
                                      ("O2", "O", 0.194, 0.25, 0.543),
                                      ("O3", "O", 0.082, 0.026, 0.809)]]
    phase = Phase(name="pbso4", space_group="P n m a", cell=cell, atoms=atoms)
    body = body_from_atoms(phase, ["S", "O1", "O2", "O3"], "SO4",
                           rotation_vary=True, origin_vary=True)
    return Structure(phases=[Phase.model_validate(
        {**phase.model_dump(), "rigid_bodies": [body.model_dump()]})])


def _bromine_on_the_p1bar_centre() -> Structure:
    """A three-atom body with Br on the ½,½,½ centre and its centroid general."""
    P = Parameter
    atoms = [Atom(label=lab, species=sp, x=P(value=x), y=P(value=y), z=P(value=z))
             for lab, sp, x, y, z in [("Br", "Br", 0.5, 0.5, 0.5),
                                      ("Ca", "C", 0.69, 0.5, 0.5),
                                      ("Cb", "C", 0.55, 0.68, 0.5)]]
    phase = Phase(name="tri", space_group="P-1", cell=_cell(), atoms=atoms)
    body = body_from_atoms(phase, ["Br", "Ca", "Cb"], "tri", rotation_vary=True)
    return Structure(phases=[Phase.model_validate(
        {**phase.model_dump(), "rigid_bodies": [body.model_dump()]})])


@pytest.mark.parametrize(("build", "atom", "order"), [
    (_sulfate_on_the_pnma_mirror, "S", 2), (_bromine_on_the_p1bar_centre, "Br", 2)])
def test_a_body_atom_on_a_special_position_is_refused_naming_it(build, atom, order):
    """The origin check alone let a body over mirror atoms build: a turn moved S,
    O1, O2 off the mirror inside the stage, and the next stage's compile counted
    8 S and 24 O in a cell of 4 and 16, converged at Rwp 25 % against 3.5 %
    with no diagnostic.  The refusal names the first atom a site fixes."""
    s = build()
    phase = s.phases[0]
    body = phase.rigid_bodies[0]
    # the origin is general in both cases, so only the atom check can refuse
    from rietx.crystallography.symmetry import resolve_group
    from rietx.crystallography.wyckoff import stabilizer_rotations
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    assert len(stabilizer_rotations(sg, np.array(body.origin.values()))) == 1
    with pytest.raises(ValueError, match=(
            rf"RIGID_BODY_NOT_INVARIANT: rigid body {body.name!r} has its atom "
            rf"{atom!r} .* \(site symmetry of order {order}\)")):
        ParameterTable(s, INS)


def test_parameter_rows_say_which_body_holds_a_coordinate():
    ref = Refinement(body_structure(Q_TRUE), INS, history=False)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.0.x"].body == "c6br"
    assert "rigid body 'c6br'" in rows["phases.0.atoms.0.x"].held_because
    assert rows["phases.0.rigid_bodies.0.rotation.0"].refinable


# ------------------------------------------------------------ the esd chain
def test_body_esds_equal_the_central_fd_chain():
    s = body_structure(Q_TRUE)
    for p in ("a", "b", "c", "alpha", "beta", "gamma"):
        getattr(s.phases[0].cell, p).vary = True
    table = ParameterTable(s, INS)
    table.set_vary(BODY_GLOBS, True)
    theta = table.x0()
    for k, v in enumerate((0.05, -0.03, 0.02)):
        theta[table.free_paths.index(f"phases.0.rigid_bodies.0.rotation.{k}")] = v
    rng = np.random.default_rng(5)
    a = rng.normal(size=(len(theta), len(theta)))
    cov = a @ a.T + len(theta) * np.eye(len(theta))
    s_int = np.sqrt(np.diag(cov)) * 1e-3
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    esd = table.stderr_physical(theta, s_int, corr)
    h = 1e-6
    rows = [f"phases.0.atoms.{j}.{c}" for j in range(7) for c in "xyz"]
    jac = np.zeros((len(rows), len(theta)))
    for col in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[col] += h
        tm[col] -= h
        vp, vm = table.decode(tp), table.decode(tm)
        jac[:, col] = [(vp[p] - vm[p]) / (2 * h) for p in rows]
    # the scale is softplus: chain its internal esd the way the table does
    from rietx.params.transforms import dphys_dinternal
    sc = table.free_paths.index("phases.0.scale")
    s_phys = s_int.copy()
    s_phys[sc] *= abs(dphys_dinternal(float(theta[sc]), "softplus"))
    var = np.einsum("ij,jk,ik->i", jac, corr * np.outer(s_phys, s_phys), jac)
    # the FD Jacobian is of θ, so the scale's column carries dφ/du already;
    # the scale reaches no body row, which makes the chain factor moot there
    for r, p in enumerate(rows):
        assert esd[p] == pytest.approx(math.sqrt(var[r]), rel=1e-9), p


# ----------------------------------------------------------- the recovery
@pytest.mark.parametrize("off_deg", [3.0, 10.0])
def test_orientation_recovered_from_a_synthetic_pattern(off_deg):
    """WP-1803's C₆Br body, Poisson noise, started off by 3° and 10° (and the
    origin 0.02 off): the orientation comes back within 0.1° with every
    increment component within 3σ of the truth, and the committed body is
    rigid to 1e-9 Å."""
    pattern = synthesize(body_structure(Q_TRUE))
    start = body_structure(_turned(Q_TRUE, off_deg), origin=(0.33, 0.41, 0.26))
    ref = Refinement(start, INS, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", BODY_GLOBS, max_iter=200)]))
    assert result.status == "converged"
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0]
    err = _angle_deg(fitted.orientation, Q_TRUE)
    assert err < 0.1, f"orientation {err:.4f}° off"
    # the commit composed the turn into the record, so the increment reads
    # zero and its esd is in the composed chart (WP-1805): the truth sits at
    # δω = Log(R_true·R_fittedᵀ), which each esd has to cover
    rf = np.asarray(rotation.matrix_from_quaternion(np.asarray(fitted.orientation)))
    rt = np.asarray(rotation.matrix_from_quaternion(Q_TRUE))
    w_true = np.asarray(rotation.vector_from_matrix(rt @ rf.T))
    for k in range(3):
        par = result.parameter(f"phases.0.rigid_bodies.0.rotation.{k}")
        assert par.value == 0.0
        assert par.stderr is not None and par.stderr > 0
        assert abs(w_true[k]) < 3 * par.stderr, (k, w_true[k], par.stderr)
    # every body atom carries an esd (through the block's local Jacobian),
    # and the body is rigid in the fitted cell
    phase = ref.fitted_structure.phases[0]
    assert all(getattr(a, c).stderr is not None and getattr(a, c).stderr > 0
               for a in phase.atoms for c in "xyz")
    frac = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    assert np.allclose(frac, body_fractional(fitted, phase.cell.lengths_angles()),
                       atol=1e-12)
    from rietx.params.derived import cartesian_frame
    cart = frac @ np.asarray(cartesian_frame(phase.cell.lengths_angles())).T
    d = np.linalg.norm(cart[:, None] - cart[None], axis=2)
    t = c6br() - c6br().mean(axis=0)
    d0 = np.linalg.norm(t[:, None] - t[None], axis=2)
    assert np.abs(d - d0).max() < 1e-9


def test_a_stale_anchor_is_caught_at_the_next_build():
    """The positive arm of the re-exponentiation: write a turned body back
    *without* composing its orientation and the next table refuses it."""
    s = body_structure(Q_TRUE)
    table = ParameterTable(s, INS)
    table.set_vary(BODY_GLOBS, True)
    theta = table.x0()
    theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.1")] = math.radians(3.0)
    chart = table.commit(theta)
    assert max(table.body_bond_errors().values()) < 1e-9
    # composed at commit: the increment is zero, the anchor turned, and the
    # outcome's chart matrix carries the rotation block
    assert all(table.decode(table.x0())[f"phases.0.rigid_bodies.0.rotation.{k}"] == 0.0
               for k in range(3))
    assert np.ndim(chart) == 2
    good = s.model_copy(deep=True)
    table.apply_to_models(good, INS)
    ParameterTable(good, INS)                        # composed: builds
    stale = good.model_copy(deep=True)
    stale.phases[0].rigid_bodies[0].orientation = tuple(Q_TRUE)
    with pytest.raises(ValueError, match="RIGID_BODY_TEMPLATE_DRIFT"):
        ParameterTable(stale, INS)


# ------------------------------------------------------------------ ties
def test_ties_onto_a_body_row_or_from_an_increment_are_refused():
    s = body_structure(Q_TRUE)
    table = ParameterTable(s, INS)
    with pytest.raises(ValueError, match="locked"):
        table.set_tie("phases.0.atoms.0.x",
                      AffineTie(terms=(("phases.0.scale", 1.0),)))
    with pytest.raises(ValueError, match="rotation.*restart"):
        table.set_tie("phases.0.atoms.0.occ",
                      AffineTie(terms=(("phases.0.rigid_bodies.0.rotation.0", 1.0),)))
    with pytest.raises(ValueError, match="restart"):
        table.set_tie("phases.0.rigid_bodies.0.rotation.0",
                      AffineTie(terms=(("phases.0.atoms.0.occ", 1.0),)))
    # one increment may follow another of its own kind
    table.set_tie("phases.0.rigid_bodies.0.rotation.1",
                  AffineTie(terms=(("phases.0.rigid_bodies.0.rotation.0", 1.0),)))


def test_le_bail_force_fixes_the_body():
    from rietx.refine import mode_fixed_column
    table = ParameterTable(body_structure(Q_TRUE), INS)
    table.set_vary(BODY_GLOBS, True)
    reach = table.column_reach()
    assert mode_fixed_column(reach["phases.0.rigid_bodies.0.rotation.0"], "lebail")
    assert not mode_fixed_column(reach["phases.0.rigid_bodies.0.rotation.0"], "rietveld")


def test_hold_on_a_body_dof_blocks_the_plan_stage():
    pattern = synthesize(body_structure(Q_TRUE))
    ref = Refinement(body_structure(_turned(Q_TRUE, 2.0)), INS, history=False)
    ref.hold("phases.0.rigid_bodies.0.rotation.*")
    result = ref.fit(pattern, plan=RefinementPlan(stages=[Stage("body", BODY_GLOBS)]))
    assert "HOLD_BLOCKED_PLAN" in {d.code for d in result.diagnostics}
    assert ref.fitted_structure.phases[0].rigid_bodies[0].orientation == pytest.approx(
        tuple(_turned(Q_TRUE, 2.0)), abs=1e-15)


def test_a_body_round_trips_through_json_and_checkout():
    s = body_structure(Q_TRUE)
    again = Structure.model_validate_json(s.model_dump_json())
    assert again == s
    pattern = synthesize(s)
    ref = Refinement(body_structure(_turned(Q_TRUE, 2.0)), INS)
    ref.fit(pattern, plan=RefinementPlan(stages=[Stage("body", BODY_GLOBS)]))
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0].orientation
    head = ref.history.head
    ref.set_values({"phases.0.scale": 1e-3})
    ref.checkout(head)
    assert ref.structure.phases[0].rigid_bodies[0].orientation == pytest.approx(fitted)


# ------------------------------------------------------- composing at commit
def _solve_body(off_deg: float):
    """One body stage solved at the table level: (model, table, outcome)."""
    from rietx.optimize.least_squares import run_least_squares

    pattern = synthesize(body_structure(Q_TRUE))
    start = body_structure(_turned(Q_TRUE, off_deg), origin=(0.33, 0.41, 0.26))
    model = compile_model(start, INS, pattern, mode="rietveld")
    table = ParameterTable(start, INS)
    table.set_vary(BODY_GLOBS, True)
    return start, model, table, run_least_squares(model, table, max_iter=200)


def test_the_recharted_outcome_matches_a_fresh_solve_at_zero_increment():
    """WP-1805: after the commit composes R₀ ← Exp(δω)·R₀, the outcome's
    Jacobian and correlations describe the composed chart — the ones a solve
    started at δω = 0 on the committed values measures.  Without the re-chart
    (θ replaced, nothing else) the rotation block disagrees, which is what
    makes this a test of the re-chart rather than of the solve."""
    from dataclasses import replace

    from rietx.optimize.least_squares import rechart_outcome, run_least_squares

    start, model, table, outcome = _solve_body(10.0)
    rot = [table.free_paths.index(f"phases.0.rigid_bodies.0.rotation.{k}")
           for k in range(3)]
    assert np.linalg.norm(outcome.theta[rot]) > math.radians(5.0)
    chart = table.commit(outcome.theta)
    recharted = rechart_outcome(outcome, table.x0(), chart)
    naive = replace(outcome, theta=table.x0())
    s = start.model_copy(deep=True)
    table.apply_to_models(s, INS)
    fresh_table = ParameterTable(s, INS)
    fresh_table.set_vary(BODY_GLOBS, True)
    assert fresh_table.free_paths == table.free_paths
    # the same model: the origin DOFs differ only by where each table anchors
    # them (a coordinate DOF is a step from its build), the rotation not at all
    a, b = table.decode(table.x0()), fresh_table.decode(fresh_table.x0())
    assert max(abs(a[p] - b[p]) for p in table.derived_paths()) < 1e-12
    assert all(fresh_table.x0()[c] == 0.0 for c in rot)
    fresh = run_least_squares(model, fresh_table, max_iter=200)
    # the fresh solve starts on the answer and stays there
    assert np.abs(fresh.theta[rot]).max() < 1e-6
    # measured: 1.1e-6 and 5.5e-7 here, against 0.087 and 0.136 un-recharted
    np.testing.assert_allclose(recharted.correlation, fresh.correlation, atol=2e-5)
    np.testing.assert_allclose(recharted.stderr_internal, fresh.stderr_internal,
                               rtol=2e-5)
    np.testing.assert_allclose(recharted.jac[:, rot], fresh.jac[:, rot],
                               rtol=1e-4, atol=1e-6 * np.abs(fresh.jac[:, rot]).max())
    # columns the chart leaves alone keep their numbers bit for bit
    other = [c for c in range(len(table.free_paths)) if c not in rot]
    assert np.array_equal(recharted.jac[:, other], outcome.jac[:, other])
    gap = np.abs(naive.correlation - fresh.correlation)[np.ix_(rot, rot)].max()
    assert gap > 1e-2, gap


def test_a_commit_that_skips_the_re_exponentiation_is_refused(monkeypatch):
    """The commit-time guard (WP-1805): a body committed rigid to 1e-9 Å and
    where the solve put it.  Two ways to skip the re-exponentiation, each
    caught: compose to first order, (I + [δω]×)·R₀, and the body stops being
    rigid; zero δω without composing, and it snaps back to R₀."""
    from rietx.params import bodies

    def first_order(omega, r0):
        return (np.eye(3) + np.asarray(rotation.skew(omega))) @ r0

    for broken, match in ((first_order, "not rigid"),
                          (lambda omega, r0: r0, "left the solver's answer")):
        table = ParameterTable(body_structure(Q_TRUE), INS)
        table.set_vary(BODY_GLOBS, True)
        theta = table.x0()
        theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.1")] = \
            math.radians(3.0)
        before = table.decode(table.x0())
        r0 = table._bodies[0][2].r0
        monkeypatch.setattr(bodies, "compose_rotation", broken)
        # a refusal, not an internal assert, and the table as it was (#801)
        with pytest.raises(ValueError, match=match):
            table.commit(theta)
        monkeypatch.undo()
        assert table.decode(table.x0()) == before
        assert table._bodies[0][2].r0 is r0
    table = ParameterTable(body_structure(Q_TRUE), INS)
    table.set_vary(BODY_GLOBS, True)
    theta = table.x0()
    theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.1")] = math.radians(3.0)
    table.commit(theta)
    assert max(table.body_bond_errors().values()) < 1e-9


def test_a_joint_commit_one_histogram_refuses_leaves_every_table_as_it_was(
        monkeypatch):
    """``MultiParameterTable.commit`` is one commit, not one per histogram: a
    table that refuses (#801's guard) puts back every table committed before
    it — entries, rotation anchor, and the anchor a later restore steps back
    to — so the histograms never disagree on a shared column."""
    from rietx.params.multi import MultiParameterTable

    ins2 = Instrument.debye_scherrer(wavelength=0.7107)
    mt = MultiParameterTable(body_structure(Q_TRUE), [INS, ins2])
    mt.set_vary(BODY_GLOBS, True)
    rot = mt.free_paths.index("phases.0.rigid_bodies.0.rotation.1")

    def state():
        return [([e.value for e in t.entries],
                 [(b.q0.copy(), b.r0.copy(), b.axes.copy()) for _, _, b in t._bodies],
                 {k: tuple(np.copy(a) for a in v)
                  for k, v in t._precommit_anchor.items()})
                for t in mt.tables]

    def same(a, b):
        for (va, anc_a, pre_a), (vb, anc_b, pre_b) in zip(a, b, strict=True):
            assert va == vb
            for x, y in zip(anc_a, anc_b, strict=True):
                assert all(np.array_equal(u, v) for u, v in zip(x, y, strict=True))
            assert pre_a.keys() == pre_b.keys()
            assert all(np.array_equal(u, v) for k in pre_a
                       for u, v in zip(pre_a[k], pre_b[k], strict=True))

    # a commit that goes through, so there is an anchor to step back to
    theta = mt.x0()
    theta[rot] = math.radians(3.0)
    mt.commit(theta)
    mt._rebuild_columns()
    before = state()
    decoded = [t.decode(t.x0()) for t in mt.tables]

    theta = mt.x0()
    theta[rot] = math.radians(2.0)
    theta[mt.free_paths.index("phases.0.rigid_bodies.0.origin.dof.0")] += 1e-3

    def refuse(answer):
        raise ValueError("RIGID_BODY_TEMPLATE_DRIFT at commit: forced")

    monkeypatch.setattr(mt.tables[1], "_check_committed_bodies", refuse)
    with pytest.raises(ValueError, match="forced"):
        mt.commit(theta)
    same(state(), before)
    assert [t.decode(t.x0()) for t in mt.tables] == decoded
    # positive arm: the same θ, unrefused, does move both tables
    monkeypatch.undo()
    mt.commit(theta)
    after = state()
    for (va, anc_a, _), (vb, anc_b, _) in zip(before, after, strict=True):
        assert va != vb
        assert not np.array_equal(anc_a[0][1], anc_b[0][1])


# ------------------------------------------------------------ series carry
def test_the_series_carry_sets_the_increment_by_log_not_by_subtraction():
    """WP-1805: ``displace_anchored_dofs`` sets a body's increment from the
    record, δω = Log(R_target·R₀ᵀ), and the series carry hands it the record.
    Carried onto a model 3° and 0.02 off, the body lands on the source to
    1e-12 — the orientation and every atom.  The subtraction rule (the
    difference of the two records' rotation vectors) misses by 0.0147° at 3°
    (WP-1803's record); not carrying the orientation at all misses by 3°."""
    from rietx.sequential import _carry_into

    source = body_structure(Q_TRUE)
    start = body_structure(_turned(Q_TRUE, 3.0), origin=(0.33, 0.41, 0.26))
    target = start.model_copy(deep=True)
    ins = INS.model_copy(deep=True)
    displaced = _carry_into(target, ins, (source, INS), ["*"])
    assert {f"phases.0.rigid_bodies.0.rotation.{k}" for k in range(3)} <= set(displaced)
    got = target.phases[0].rigid_bodies[0]
    assert _angle_deg(got.orientation, Q_TRUE) < 1e-9
    for a, b in zip(target.phases[0].atoms, source.phases[0].atoms, strict=True):
        for c in "xyz":
            assert abs(getattr(a, c).value - getattr(b, c).value) < 1e-12
    ParameterTable(target, INS)                    # and it builds: no drift
    # what the subtraction rule would have set, for scale
    w_src = np.asarray(rotation.vector_from_quaternion(np.asarray(Q_TRUE)))
    w_start = np.asarray(rotation.vector_from_quaternion(
        np.asarray(start.phases[0].rigid_bodies[0].orientation)))
    r_sub = (np.asarray(rotation.matrix_from_vector(w_src - w_start))
             @ np.asarray(rotation.matrix_from_quaternion(
                 np.asarray(start.phases[0].rigid_bodies[0].orientation))))
    q_sub = rotation.canonical_quaternion(rotation.quaternion_from_matrix(r_sub))
    assert _angle_deg(q_sub, Q_TRUE) > 1e-3


def test_the_series_fences_skip_the_rotation_increment():
    from rietx.sequential import _relative_paths

    rel = _relative_paths(body_structure(Q_TRUE), INS)
    assert {f"phases.0.rigid_bodies.0.rotation.{k}" for k in range(3)} <= rel
    assert "phases.0.atoms.0.x" not in rel


# ------------------------------------------- the #773 follow-ups, in a body
def test_a_variable_driving_a_body_phase_cell_takes_an_exact_column():
    """``_column_identities`` reads the declared reach (WP-1805, the #773
    follow-up).  A named variable driving ``cell.a`` of a phase with a body
    moves every body atom (the cell is a live input), which no C row says:
    read off C the column was named ``cell.a`` with no extras, a claim about
    its reach that is false.  The column itself agreed with a central FD of
    the residual either way on this tree (measured), since a cell column
    takes the peak chain; the FD check stays as the guard on the dispatch."""
    from rietx.optimize.least_squares import (
        _column_extras,
        _column_identities,
        _make_jacobian,
        _make_residual,
    )

    s = body_structure(Q_TRUE)
    s.phases[0].space_group = "P1"
    pattern = synthesize(s)
    table = ParameterTable(s, INS)
    table.set_vary(["*"], False)
    table.add_parameter("vars.a", CELL[0], vary=True)
    table.set_tie("phases.0.cell.a", AffineTie(terms=(("vars.a", 1.0),)))
    table.set_vary(["phases.0.scale"], True)
    col = table.free_paths.index("vars.a")
    path, extras, _ = _column_identities(table, _column_extras(table))[col]
    assert path == "phases.0.cell.a"
    assert "phases.0.atoms.3.y" in extras
    model = compile_model(s, INS, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)[:, col]
    resid = _make_residual(model, table)
    h = 1e-6 * abs(theta[col])
    tp, tm = theta.copy(), theta.copy()
    tp[col] += h
    tm[col] -= h
    fd = (resid(tp) - resid(tm)) / (2 * h)
    assert np.abs(jac - fd).max() < 1e-4 * np.abs(fd).max()


def test_a_seeded_cell_length_moves_the_body_atoms_with_it():
    """Every value writer ends in a rebuild, and the rebuild refreshes the
    derived rows (WP-1805, the #773 follow-up): ``seed_softplus`` on a
    softplus cell length moves a body's fractional coordinates, as a cell-only
    stage does, and leaves them where the block puts them."""
    s = body_structure(Q_TRUE)
    s.phases[0].cell.a = Parameter(value=CELL[0], min=0.0, transform="softplus")
    table = ParameterTable(s, INS)
    before = table.decode(table.x0())["phases.0.atoms.0.x"]
    assert table.seed_softplus(["phases.0.cell.a"], CELL[0] + 0.5)
    stored = {e.path: e.value for e in table.entries}
    block = table.derived[0]
    placed = block.evaluate(np.array([stored[q] for q in block.inputs]))
    assert np.array_equal(np.array([stored[q] for q in block.outputs]), placed)
    assert stored["phases.0.atoms.0.x"] != before


def test_add_derived_checks_the_reach_shape_before_registering():
    from rietx.params.bodies import RigidBodyBlock

    s = body_structure(Q_TRUE)
    table = ParameterTable(s, INS)
    good = table.derived[0]

    class Short(RigidBodyBlock):
        def reach_pattern(self):
            return super().reach_pattern()[:, :-1]

    bad = Short.__new__(Short)
    bad.__dict__.update(good.__dict__)
    bad.outputs = tuple(q.replace("atoms.", "atoms.") for q in good.outputs)
    table.derived.clear()
    table._rebuild()
    n = len(table.derived)
    with pytest.raises(ValueError, match="reach_pattern"):
        table.add_derived(bad)
    assert len(table.derived) == n


# ------------------------------------------------------- the rows WP-1805 owes
OUT = __import__("pathlib").Path(__file__).parent / "output"


def _save_fit_png(result, name: str) -> None:
    """obs/calc/diff to ``tests/output/`` (WP-1805's task list)."""
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{name}.png"))
    plt.close("all")


def test_fit_pngs_for_the_three_and_ten_degree_starts():
    pattern = synthesize(body_structure(Q_TRUE))
    for off in (3.0, 10.0):
        ref = Refinement(body_structure(_turned(Q_TRUE, off), origin=(0.33, 0.41, 0.26)),
                         INS, history=False)
        result = ref.fit(pattern, plan=RefinementPlan(stages=[
            Stage("body", BODY_GLOBS, max_iter=200)]))
        _save_fit_png(result, f"rigid_body_c6br_{int(off)}deg")
        assert (OUT / f"rigid_body_c6br_{int(off)}deg.png").stat().st_size > 0


def dibromoacetylene() -> np.ndarray:
    """Br–C≡C–Br on a line: C≡C 1.20 Å, C–Br 1.79 Å (a linear template)."""
    return np.array([[0.0, 0.0, z] for z in (-2.39, -0.60, 0.60, 2.39)])


def linear_structure(q, origin=(0.31, 0.42, 0.27)) -> Structure:
    seed = Atom(label="seed", species="C", x=Parameter(value=0.0),
                y=Parameter(value=0.0), z=Parameter(value=0.0))
    phase = Phase(name="c2br2", space_group="P-1", cell=_cell(), atoms=[seed],
                  scale=Parameter(value=1e-2, min=0.0, transform="softplus"))
    phase = add_body(phase, "c2br2", ["Br1", "C1", "C2", "Br2"],
                     ["Br", "C", "C", "Br"], dibromoacetylene(), origin,
                     orientation=q, biso=2.0)
    phase = Phase.model_validate({**phase.model_dump(),
                                  "atoms": phase.model_dump()["atoms"][1:]})
    return Structure(phases=[phase])


def _axis(q) -> np.ndarray:
    return np.asarray(rotation.matrix_from_quaternion(np.asarray(q))) @ np.array([0, 0, 1.0])


def test_a_linear_body_gets_two_rotation_dofs_and_recovers_its_axis():
    """The inertia rank (WP-1805, ``Fragment``'s DOF count): a linear body has
    two rotation DOFs, since a turn about its axis moves nothing and a third
    would be a flat direction blinding every atom's esd.  Started 5° off, the
    axis comes back within 0.1° with finite esds on every atom; and the
    re-charted outcome of the linear chart matches a fresh solve too."""
    from rietx.optimize.least_squares import rechart_outcome, run_least_squares

    truth = linear_structure(Q_TRUE)
    table = ParameterTable(truth, INS)
    rot = sorted(p for p in table.anchored_rotation_paths)
    assert rot == ["phases.0.rigid_bodies.0.rotation.0",
                   "phases.0.rigid_bodies.0.rotation.1"]
    pattern = synthesize(truth)
    start = linear_structure(_turned(Q_TRUE, 5.0), origin=(0.32, 0.41, 0.26))
    ref = Refinement(start, INS, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", BODY_GLOBS, max_iter=200)]))
    assert result.status == "converged"
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0].orientation
    cos = float(np.clip(_axis(fitted) @ _axis(Q_TRUE), -1.0, 1.0))
    assert math.degrees(math.acos(abs(cos))) < 0.1
    for a in ref.fitted_structure.phases[0].atoms:
        for c in "xyz":
            assert getattr(a, c).stderr is not None and 0 < getattr(a, c).stderr < 0.01
    assert "RIGID_BODY_UNSUPPORTED" not in {d.code for d in result.diagnostics}
    _save_fit_png(result, "rigid_body_linear_5deg")
    # the linear chart's re-chart, against a fresh solve on the committed values
    model = compile_model(start, INS, pattern, mode="rietveld")
    table = ParameterTable(start, INS)
    table.set_vary(BODY_GLOBS, True)
    outcome = run_least_squares(model, table, max_iter=200)
    cols = [table.free_paths.index(p) for p in rot]
    chart = table.commit(outcome.theta)
    recharted = rechart_outcome(outcome, table.x0(), chart)
    s = start.model_copy(deep=True)
    table.apply_to_models(s, INS)
    fresh_table = ParameterTable(s, INS)
    fresh_table.set_vary(BODY_GLOBS, True)
    fresh = run_least_squares(model, fresh_table, max_iter=200)
    np.testing.assert_allclose(recharted.correlation, fresh.correlation, atol=2e-5)
    np.testing.assert_allclose(recharted.stderr_internal[cols],
                               fresh.stderr_internal[cols], rtol=2e-5)


def test_a_dof_the_pattern_cannot_see_is_named_rigid_body_unsupported():
    """``RIGID_BODY_UNSUPPORTED`` (WP-1805): a body whose turn moves only
    zero-occupancy atoms — a heavy atom at its origin, two empty sites on a
    line through it — refines its origin and measures nothing in rotation.
    The finding names the two rotation DOFs, and only them."""
    P = Parameter
    atoms = [Atom(label="Fe", species="Fe", x=P(value=0.30), y=P(value=0.40),
                  z=P(value=0.20)),
             Atom(label="X1", species="O", x=P(value=0.38), y=P(value=0.40),
                  z=P(value=0.20), occ=P(value=0.0)),
             Atom(label="X2", species="O", x=P(value=0.22), y=P(value=0.40),
                  z=P(value=0.20), occ=P(value=0.0)),
             Atom(label="Na", species="Na", x=P(value=0.71), y=P(value=0.13),
                  z=P(value=0.62))]
    phase = Phase(name="t", space_group="P1", cell=_cell(), atoms=atoms,
                  scale=P(value=1e-2, min=0.0, transform="softplus"))
    body = body_from_atoms(phase, ["X1", "Fe", "X2"], "blind")
    s = Structure(phases=[phase.model_copy(update={"rigid_bodies": [body]})])
    pattern = synthesize(s)
    s.phases[0].rigid_bodies[0].origin.x.value += 0.004
    s = Structure(phases=[place_body_atoms(s.phases[0])])
    ref = Refinement(s, INS, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[Stage("body", BODY_GLOBS)]))
    found = [d for d in result.diagnostics if d.code == "RIGID_BODY_UNSUPPORTED"]
    assert len(found) == 1
    assert found[0].where == ["phases.0.rigid_bodies.0.rotation.0",
                              "phases.0.rigid_bodies.0.rotation.1"]
    assert result.parameter("phases.0.rigid_bodies.0.origin.dof.0").stderr is not None


def test_a_hold_on_a_body_atom_row_raises_and_on_a_body_dof_holds():
    ref = Refinement(body_structure(Q_TRUE), INS, history=False)
    with pytest.raises(ValueError, match="placed by rigid body 'c6br'"):
        ref.hold("phases.0.atoms.2.x")
    with pytest.raises(ValueError, match="hold the body's own"):
        ref.hold("phases.0.atoms.*.y")
    # a twist is a body DOF too (WP-1808): the refusal names its glob
    with pytest.raises(ValueError, match=r"rigid_bodies\.\*\.torsions\.\*\.twist"):
        ref.hold("phases.0.atoms.*.y")
    assert ref.hold("phases.0.rigid_bodies.0.origin.dof.*")


def test_the_public_tie_verb_refuses_a_body_row_and_a_rotation_source():
    ref = Refinement(body_structure(Q_TRUE), INS, history=False)
    with pytest.raises(ValueError, match="phases.0.atoms.0.x"):
        ref.tie("phases.0.atoms.0.x", "phases.0.scale")
    with pytest.raises(ValueError, match="phases.0.rigid_bodies.0.rotation.0"):
        ref.tie("phases.0.atoms.0.occ", "phases.0.rigid_bodies.0.rotation.0")


def test_replay_reproduces_the_body():
    from rietx.refine import replay

    pattern = synthesize(body_structure(Q_TRUE))
    ref = Refinement(body_structure(_turned(Q_TRUE, 3.0)), INS)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[Stage("body", BODY_GLOBS)]))
    again = replay(ref.history, ref.history.head, pattern)
    for j in range(7):
        for c in "xyz":
            p = f"phases.0.atoms.{j}.{c}"
            assert again.parameter(p).value == pytest.approx(
                result.parameter(p).value, abs=1e-12)
    assert again.statistics.rwp == pytest.approx(result.statistics.rwp, rel=1e-6)


def test_the_textdoc_round_trip_reproduces_the_body(tmp_path):
    """Render, parse, diff is a fixed point with a body declared; an edit of
    the origin DOF and of a rotation DOF in the text moves the body as one,
    rigidly, and the re-render is a fixed point again (WP-1805; the body's own
    block in the document is WP-1812's)."""
    import rietx as rx
    from rietx.gui import textdoc as td
    from tests.test_project import _write_xye

    s = body_structure(Q_TRUE)
    path = _write_xye(tmp_path / "body.xye", synthesize(s))
    project = rx.Project.create(tmp_path / "body.rex", pattern=path, structure=s,
                                instrument=INS, plan="mccusker_default")
    text = td.render(project)
    parsed = td.parse(text)
    assert parsed.errors == []
    delta, errors = td.changes(parsed, project)
    assert errors == [] and delta.is_empty(), delta.as_dict()
    edited = []
    for line in text.splitlines():
        head = line.split("#")[0].split()
        if head[:1] in (["rigid_bodies.0.origin.dof.0"], ["rigid_bodies.0.rotation.2"]):
            k = 2 if head[1] == "@" else 1
            value = (float(head[k]) + 0.01 if head[0].endswith("dof.0") else 0.05)
            line = "  " + " ".join([*head[:k], repr(value), *head[k + 1:]])
        edited.append(line)
    delta, errors = td.changes(td.parse("\n".join(edited) + "\n"), project)
    assert errors == []
    td.apply(project, delta)
    moved = project.refinement.structure.phases[0]
    body = moved.rigid_bodies[0]
    assert body.origin.x.value == pytest.approx(0.31 + 0.01, abs=1e-12)
    assert _angle_deg(body.orientation, Q_TRUE) == pytest.approx(math.degrees(0.05),
                                                                 rel=1e-9)
    frac = np.array([[a.x.value, a.y.value, a.z.value] for a in moved.atoms])
    assert np.allclose(frac, body_fractional(body, moved.cell.lengths_angles()),
                       atol=1e-12)
    again = td.render(project)
    delta, errors = td.changes(td.parse(again), project)
    assert errors == [] and delta.is_empty()


# ------------------------------------------------------- review round 1 (#801)
def _pspline_ins() -> Instrument:
    from rietx.schemas.instrument import BackgroundPSpline

    ins = INS.model_copy(deep=True)
    bp = list(np.linspace(8.0, 70.0, 8))
    ins.background = BackgroundPSpline(
        breakpoints=bp, lambda_smooth=5.0,
        coefficients=[Parameter(value=30.0 + 3.0 * k) for k in range(len(bp) + 2)])
    return ins


@pytest.mark.parametrize("target", ["phases.0.scale", "instrument.background.c3"])
@pytest.mark.parametrize("c", [1.0, 0.5, -2.0])
def test_a_variable_at_a_non_unit_coefficient_takes_an_exact_column(target, c):
    """A variable reaching one path at c ≠ 1 is not that path's column (#801).
    Read off ``reach_block`` every coefficient was 1.0 once a body existed,
    and with ``extra`` empty the closed-form scale branch took the column
    anyway — jac/fd = 1/c, measured 2.0 and −0.5, and on ``main`` without a
    body too.  A background coefficient is closed-form at any c, penalty
    rows included (the FD fallback writes none).  Measured after: 1.7e-10
    and 2.0e-11 of the column's scale."""
    from rietx.optimize.least_squares import _make_jacobian, _make_residual

    ins = _pspline_ins()
    s = body_structure(Q_TRUE)
    s.phases[0].space_group = "P1"
    blank = PatternData(two_theta=np.arange(8.0, 70.0, 0.02).tolist(),
                        intensity=np.zeros(3100).tolist())
    model = compile_model(s, ins, blank, mode="rietveld")
    base = ParameterTable(s, ins)
    y = model.evaluate(base.decode(base.x0()))
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())
    table = ParameterTable(s, ins)
    assert table.derived                          # a body is present
    table.set_vary(["*"], False)
    v0 = table.decode(table.x0())[target]
    table.add_parameter("vars.b", v0 / c, vary=True)
    table.set_tie(target, AffineTie(terms=(("vars.b", c),)))
    table.set_vary(["phases.0.atoms.0.biso"], True)
    col = table.free_paths.index("vars.b")
    model = compile_model(s, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)[:, col]
    resid = _make_residual(model, table)
    h = 1e-5 * abs(theta[col])
    tp, tm = theta.copy(), theta.copy()
    tp[col] += h
    tm[col] -= h
    fd = (resid(tp) - resid(tm)) / (2 * h)
    assert np.abs(jac - fd).max() < 1e-6 * np.abs(fd).max()


def _fake_outcome(theta, se, corr):
    from rietx.optimize.least_squares import LSQOutcome

    return LSQOutcome(theta=theta, cost_initial=1.0, cost_final=1.0, n_iterations=1,
                      status="converged", jac=None, stderr_internal=se,
                      correlation=corr)


def test_a_held_rotation_dof_beside_a_turn_is_recharted():
    """``rotation.2`` held, ω along x: the chart on the free (x, y) block is
    diag(1, 1 − c·|ω|²), nothing off the diagonal (#801).  Read as a sign
    flip, the y column's esd stayed 4.1104 against T⁻¹·Cov·T⁻ᵀ's 4.1415,
    and its correlation diagonal came out 0.985.  A column is touched
    wherever T differs from a signed identity, and the non-finite branch
    takes only the sign of a diagonal scale."""
    from rietx.optimize.least_squares import rechart_outcome

    table = ParameterTable(body_structure(Q_TRUE), INS)
    table.set_vary(["phases.*.scale", "phases.*.rigid_bodies.*.origin.dof.*",
                    "phases.0.rigid_bodies.0.rotation.0",
                    "phases.0.rigid_bodies.0.rotation.1"], True)
    free = table.free_paths
    x, y = (free.index(f"phases.0.rigid_bodies.0.rotation.{k}") for k in (0, 1))
    theta = table.x0()
    theta[x] = 0.3
    n = len(theta)
    a = np.random.default_rng(1).normal(size=(n, n))
    cov = a @ a.T + n * np.eye(n)
    se = np.sqrt(np.diag(cov))
    corr = cov / np.outer(se, se)
    t = table.commit(theta)
    assert t[y, y] != pytest.approx(1.0) and t[x, y] == t[y, x] == 0.0
    out = rechart_outcome(_fake_outcome(theta, se, corr), table.x0(), t)
    tinv = np.linalg.inv(t)
    new = tinv @ cov @ tinv.T
    se_true = np.sqrt(np.diag(new))
    np.testing.assert_allclose(out.stderr_internal, se_true, rtol=1e-12)
    np.testing.assert_allclose(out.correlation, new / np.outer(se_true, se_true),
                               atol=1e-12)
    for c in (out.correlation,
              rechart_outcome(_fake_outcome(theta, np.where(np.arange(n) == y, np.inf, se),
                                            corr), table.x0(), t).correlation):
        assert np.abs(np.diag(c) - 1.0).max() < 1e-12
        assert np.linalg.eigvalsh(c).min() > 0.0


def test_a_nan_orientation_is_refused():
    """``abs(norm − 1) > tol`` is False for NaN, so a NaN quaternion
    validated and every body atom decoded to NaN (#801)."""
    import json

    origin = {c: {"value": 0.1} for c in "xyz"}
    doc = {"name": "b", "atoms": ["A", "B"], "template": [[0, 0, 0], [1.4, 0, 0]],
           "origin": origin}
    with pytest.raises(ValueError, match="not a unit quaternion"):
        RigidBody.model_validate({**doc, "orientation": (math.nan, 0.0, 0.0, 0.0)})
    text = json.dumps(doc)[:-1] + ', "orientation": ["NaN", 0, 0, 0]}'
    with pytest.raises(ValueError, match="not a unit quaternion"):
        RigidBody.model_validate_json(text)


def test_add_body_refuses_a_label_the_phase_already_has():
    """``add_body`` validates what it returns (#801): ``model_copy`` skipped
    the phase's checks, so a duplicate label built two atoms of one name and
    raised only at the next JSON round trip."""
    phase = body_structure(Q_TRUE).phases[0]
    with pytest.raises(ValueError, match="'C0'"):
        add_body(phase, "dup", ["C0", "X1"], ["C", "C"],
                 [(0.0, 0.0, 0.0), (1.4, 0.0, 0.0)], (0.6, 0.6, 0.6))


def test_a_body_atom_under_le_bail_names_the_mode():
    """Under Le Bail the body's origin and rotation are force-fixed too, so
    "refine its origin and rotation instead" sent the caller to a refusal;
    the mode is the reason that would still hold (#801)."""
    ref = Refinement(body_structure(Q_TRUE), INS, history=False)
    for mode in ("lebail", "pawley"):
        row = {r.path: r for r in ref.parameters(mode=mode)}["phases.0.atoms.2.x"]
        assert row.held_because == "force-fixed by the intensity mode (lebail/pawley)"
    row = {r.path: r for r in ref.parameters(mode="rietveld")}["phases.0.atoms.2.x"]
    assert row.held_because.startswith("placed by rigid body 'c6br'")


def test_an_antiparallel_carry_turns_the_linear_body_half_way():
    """A linear body's carried axis flipped by 180° (#801).  Exactly, sin = 0
    read as parallel: δω = 0, the end atoms swapped.  Here, as built, sin is
    6e-17 of rounding, and the cross product's noise along the axis — which
    E's plane drops — shortened the half turn: 9.7e-6 off in a coordinate.
    Now the axis is projected normal to the body's, and every atom lands."""
    from rietx.sequential import _carry_into

    r = np.asarray(rotation.matrix_from_quaternion(np.asarray(Q_TRUE)))
    flip = r @ np.asarray(rotation.matrix_from_vector(np.array([math.pi, 0.0, 0.0])))
    q_flip = rotation.canonical_quaternion(rotation.quaternion_from_matrix(flip))
    source = linear_structure(Q_TRUE)
    target = linear_structure(q_flip)
    a0, b0 = target.phases[0].atoms[0], source.phases[0].atoms[0]
    assert abs(a0.x.value - b0.x.value) + abs(a0.y.value - b0.y.value) > 1e-2
    _carry_into(target, INS.model_copy(deep=True), (source, INS), ["*"])
    for a, b in zip(target.phases[0].atoms, source.phases[0].atoms, strict=True):
        for c in "xyz":
            assert abs(getattr(a, c).value - getattr(b, c).value) < 1e-12
