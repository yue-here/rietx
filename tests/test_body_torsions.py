"""Named-bond torsions inside a rigid body (WP-1808).

A torsion turns a declared atom subset about the line through two body atoms
(TOPAS's ``Rotate_about_points``, Technical Reference § 10.22.4).  It is an
anchored rotation like the body's own (WP-1805): the twist increment refines,
and every commit composes it into the torsion's ``angle`` and zeroes it.  Its
derivative is propagated forward through the torsions in order, so a torsion
whose axis rides on an earlier one's moved atoms is exact too; every claim is
checked against a central difference of the map itself, never of a formula
sharing code with the tangent.  The known answers: a dihedral ending on a
moved atom changes by exactly the twist (Klyne–Prelog sign); the Z-matrix
dihedral and the bond rotation agree on a tree-consistent fragment; a 30°
twist is recovered from a synthetic pattern within 1° with its esd covering.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography.bodies import add_body, body_fractional
from rietx.crystallography.fragments import from_zmatrix
from rietx.model.forward import compile_model
from rietx.params.bodies import RigidBodyBlock, apply_torsions, wrap_degrees
from rietx.params.vector import AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, BodyTorsion, Cell, Phase, RigidBody, Structure
from rietx.strategy.staged import RefinementPlan, Stage

INS = Instrument.debye_scherrer(wavelength=1.5406)
INS.profile.w.value = 8e-3
TWIST = "phases.0.rigid_bodies.0.torsions.0.twist"
POSE_GLOBS = ["phases.*.scale", "instrument.background.*",
              "phases.*.rigid_bodies.*.origin.dof.*",
              "phases.*.rigid_bodies.*.rotation.*"]


def dihedral(a, b, c, d) -> float:
    """Klyne–Prelog dihedral a–b–c–d (deg), the cif_core ``_geom_torsion`` sign."""
    b1, b2, b3 = b - a, c - b, d - c
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    return math.degrees(math.atan2(np.linalg.norm(b2) * (b1 @ n2), n1 @ n2))


def chain() -> np.ndarray:
    """A bent five-atom chain plus a side atom: generic, no symmetry."""
    return np.array([[0.0, 0.0, 0.0], [1.5, 0.1, 0.0], [2.1, 1.4, 0.2],
                     [3.6, 1.5, 0.6], [4.2, 2.8, 0.4], [2.0, 2.0, -1.2]])


# (axis_a, axis_b, moves); the second torsion's axis atom 3 is moved by the first
TORSIONS = [(1, 2, [3, 4]), (2, 3, [4]), (0, 1, [5])]
#: the anchors φ₀, off zero so the tangent is read away from the template
ANCHORS = np.array([11.0, -17.0, 4.0])


def _chain_block() -> RigidBodyBlock:
    return RigidBodyBlock(phase_base="p", body_base="b",
                          atom_bases=[f"a{i}" for i in range(6)], template=chain(),
                          q0=(1.0, 0.0, 0.0, 0.0), torsions=TORSIONS, angles=ANCHORS)


# ------------------------------------------------------------- the forward map
def test_tangents_equal_a_central_difference_of_the_torsions():
    """∂(points)/∂δφ by forward tangent propagation, including a chained axis,
    at anchors and increments both off zero (φ = φ₀ + δφ)."""
    twists = np.array([12.0, -24.0, 3.0])
    block = _chain_block()
    x = np.concatenate([[6.0, 7.0, 8.0, 90.0, 90.0, 90.0], [0.1, 0.2, 0.3],
                        [0.0, 0.0, 0.0], twists])
    tan = block.body_tangents(x)
    h = 1e-5
    for t in range(3):
        up, dn = ANCHORS + twists, ANCHORS + twists
        up, dn = up.copy(), dn.copy()
        up[t] += h
        dn[t] -= h
        fd = (apply_torsions(chain(), TORSIONS, up)
              - apply_torsions(chain(), TORSIONS, dn)) / (2 * h)
        assert np.abs(tan[t] - fd).max() < 1e-9, t
    # the chained torsion reaches atom 4 through torsion 0 *and* its own
    pattern = block.reach_pattern()
    assert pattern[3 * 4, 12] and pattern[3 * 4, 13]
    assert not pattern[3 * 5, 12] and pattern[3 * 5, 14]
    assert not pattern[3 * 0, 12]


def test_the_whole_block_jacobian_equals_a_central_difference():
    """WP-1808 acceptance: the block Jacobian agrees with central FD, every
    column — cell, origin, rotation and each twist — at a turned anchor."""
    block = RigidBodyBlock(phase_base="p", body_base="b",
                           atom_bases=[f"a{i}" for i in range(6)], template=chain(),
                           q0=(0.9, 0.1, 0.2, 0.3) / np.linalg.norm((0.9, 0.1, 0.2, 0.3)),
                           torsions=TORSIONS, angles=ANCHORS)
    x = np.concatenate([[7.21, 8.13, 9.47, 84.3, 97.6, 104.2], [0.31, 0.42, 0.27],
                        [0.07, -0.04, 0.05], [23.0, -41.0, 7.0]])
    jac = block.jacobian(x)
    assert jac.shape == (18, 15)
    for k in range(len(x)):
        h = 1e-6 * max(1.0, abs(x[k]))
        up, dn = x.copy(), x.copy()
        up[k] += h
        dn[k] -= h
        fd = (block.evaluate(up) - block.evaluate(dn)) / (2 * h)
        assert np.abs(jac[:, k] - fd).max() < 1e-8 * max(1.0, np.abs(fd).max()), k


def test_a_dihedral_ending_on_a_moved_atom_changes_by_the_twist():
    """Klyne–Prelog: a–b–c–d with d moved about b→c changes by +φ."""
    pts = chain()
    before = dihedral(*pts[[1, 2, 3, 4]])
    after_pts = apply_torsions(pts, [(2, 3, [4])], [30.0])
    after = dihedral(*after_pts[[1, 2, 3, 4]])
    assert ((after - before + 180.0) % 360.0 - 180.0) == pytest.approx(30.0, abs=1e-10)
    # nothing off the moved set moves, and bonds to the axis keep their length
    assert np.array_equal(after_pts[:4], pts[:4])
    assert np.linalg.norm(after_pts[4] - after_pts[3]) == pytest.approx(
        np.linalg.norm(pts[4] - pts[3]), abs=1e-12)


def test_zmatrix_dihedral_and_bond_rotation_agree_on_a_tree_fragment():
    """WP-1808 acceptance: the two conventions are one object when the
    reference graph is a tree — line 4's dihedral rotates only atom 4."""
    def frag(phi):
        return from_zmatrix([["C"], ["C", 0, 1.5], ["C", 1, 1.5, 0, 112.0],
                             ["C", 2, 1.5, 1, 111.0, 0, 60.0],
                             ["O", 3, 1.4, 2, 109.0, 1, phi]]).xyz
    base = frag(-70.0)
    twisted = apply_torsions(base, [(2, 3, [4])], [25.0])
    assert np.abs(twisted - frag(-45.0)).max() < 1e-12


# --------------------------------------------------------------- refusals
def test_a_torsion_that_moves_nothing_or_misses_the_body_is_refused():
    """WP-1808 acceptance: a torsion that moves nothing is refused — an empty
    moved set by the schema, a moved set lying on the axis line by the table
    (its column would be identically zero) — and so is one that misses the
    body."""
    common = dict(name="b", atoms=["A", "B", "C"],
                  template=[(0, 0, 0), (1.5, 0, 0), (2, 1.4, 0)],
                  origin={"x": {"value": 0.1}, "y": {"value": 0.2}, "z": {"value": 0.3}})
    with pytest.raises(ValueError, match="moves nothing"):
        RigidBody.model_validate({**common, "torsions": [
            {"name": "t", "axis": ("A", "B"), "moves": []}]})
    with pytest.raises(ValueError, match="axis"):
        RigidBody.model_validate({**common, "torsions": [
            {"name": "t", "axis": ("A", "Z"), "moves": ["C"]}]})
    with pytest.raises(ValueError, match="off the axis"):
        RigidBody.model_validate({**common, "torsions": [
            {"name": "t", "axis": ("A", "B"), "moves": ["B"]}]})
    with pytest.raises(ValueError, match="twice"):
        RigidBody.model_validate({**common, "torsions": [
            {"name": "t", "axis": ("A", "B"), "moves": ["C"]},
            {"name": "t", "axis": ("B", "C"), "moves": ["A"]}]})
    # C sits on the line through A and B: a turn about it moves nothing
    on_axis = [(0.0, 0.0, 0.0), (1.5, 0.0, 0.0), (3.0, 0.0, 0.0), (1.0, 1.3, 0.2)]
    torsion = BodyTorsion(name="t", axis=("A", "B"), moves=["C"])
    phase = _seeded_phase()
    phase = add_body(phase, "b", ["A", "B", "C", "D"], ["C"] * 4, on_axis,
                     (0.3, 0.4, 0.25), torsions=[torsion])
    with pytest.raises(ValueError, match="moves nothing"):
        ParameterTable(Structure(phases=[phase]), INS)
    # moved off the line by a hundredth of an ångström, it builds
    off_axis = [p if i != 2 else (3.0, 0.01, 0.0) for i, p in enumerate(on_axis)]
    phase = add_body(_seeded_phase(), "b", ["A", "B", "C", "D"], ["C"] * 4, off_axis,
                     (0.3, 0.4, 0.25), torsions=[torsion])
    ParameterTable(Structure(phases=[phase]), INS)


def _seeded_phase() -> Phase:
    P = Parameter
    return Phase(name="p", space_group="P-1", atoms=[
        Atom(label="Li", species="Li", x=P(value=0.71), y=P(value=0.12), z=P(value=0.63))],
        cell=Cell(a=P(value=8.1), b=P(value=9.3), c=P(value=10.2),
                  alpha=P(value=86.0), beta=P(value=95.0), gamma=P(value=101.0)),
        scale=P(value=1e-2, min=0.0, transform="softplus"))


# ------------------------------------------------------------ the biphenyl
def biphenyl() -> np.ndarray:
    """Two ideal rings (C–C 1.39 Å) joined by a 1.49 Å bond along x, coplanar."""
    ring = np.array([[1.39 * math.cos(k * math.pi / 3), 1.39 * math.sin(k * math.pi / 3), 0.0]
                     for k in range(6)])
    left = ring - ring[0]                        # atom 0 at the origin, ring to −x
    right = -ring + ring[0]
    right = right + np.array([1.49, 0.0, 0.0])   # atom 6 bonded to atom 0
    return np.vstack([left, right])


LABELS = [f"C{i}" for i in range(12)]


def _structure(angle: float, *, vary: bool = False) -> Structure:
    seed = Atom(label="seed", species="C", x=Parameter(value=0.0),
                y=Parameter(value=0.0), z=Parameter(value=0.0))
    P = Parameter
    phase = Phase(name="bp", space_group="P-1", atoms=[seed],
                  cell=Cell(a=P(value=8.1), b=P(value=9.3), c=P(value=10.2),
                            alpha=P(value=86.0), beta=P(value=95.0), gamma=P(value=101.0)),
                  scale=P(value=1e-2, min=0.0, transform="softplus"))
    phase = add_body(phase, "bp", LABELS, ["C"] * 12, biphenyl(), (0.3, 0.4, 0.25),
                     orientation=(0.9, 0.1, 0.2, 0.3), biso=2.0,
                     torsions=[BodyTorsion(name="twist", axis=("C0", "C6"),
                                           moves=LABELS[7:], angle=angle, vary=vary)])
    return Structure(phases=[Phase.model_validate(
        {**phase.model_dump(), "atoms": phase.model_dump()["atoms"][1:]})])


def _synthesize(structure: Structure) -> PatternData:
    tt = np.arange(6.0, 60.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, INS, blank, mode="rietveld")
    table = ParameterTable(structure, INS)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(8).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _atoms(structure: Structure) -> np.ndarray:
    return np.array([[a.x.value, a.y.value, a.z.value] for a in structure.phases[0].atoms])


def test_a_planted_30_degree_twist_is_recovered():
    """WP-1808 acceptance: a 30° biphenyl twist is recovered from a synthetic
    pattern within 1°, and the esd covers it.  The twist composes at every
    commit, so the answer is the record, ``angle``, and the esd is the
    increment's, which composing leaves alone (a translation of its chart)."""
    pattern = _synthesize(_structure(30.0))
    ref = Refinement(_structure(0.0), INS, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("pose", POSE_GLOBS, max_iter=100),
        Stage("twist", ["phases.*.rigid_bodies.*.torsions.*.twist"], max_iter=200)]))
    par = result.parameter(TWIST)
    assert par.stderr is not None and par.stderr > 0
    # the last commit composed the twist, so the reported increment is zero
    assert par.value == 0.0
    stored = ref.fitted_structure.phases[0].rigid_bodies[0].torsions[0].angle
    assert -180.0 < stored <= 180.0
    err = wrap_degrees(stored - 30.0)
    assert abs(err) < 1.0, stored
    assert abs(err) < 3.0 * par.stderr + 1e-9, (err, par.stderr)
    _save_fit_png(result, "body_torsion_biphenyl_30deg")


OUT = __import__("pathlib").Path(__file__).parent / "output"


def _save_fit_png(result, name: str) -> None:
    """obs/calc/diff to ``tests/output/`` (WP-1808's task list)."""
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{name}.png"))
    plt.close("all")
    assert (OUT / f"{name}.png").stat().st_size > 0


# ------------------------------------------------------ composing at commit
def _twisted_theta(table: ParameterTable, twist: float) -> np.ndarray:
    theta = table.x0()
    theta[table.free_paths.index(TWIST)] = twist
    return theta


def test_the_commit_composes_the_twist_into_the_record():
    """WP-1808: φ₀ ← φ₀ + δφ and δφ ← 0 at commit, the atoms where the solve
    put them.  The commit's return carries the outcome's θ to the composed
    chart (all ones: a translation moves no column), the record written back
    is the composed angle, and a table rebuilt from it starts at δφ = 0 on the
    same atoms."""
    from rietx.optimize.least_squares import LSQOutcome, rechart_outcome

    s = _structure(20.0)
    table = ParameterTable(s, INS)
    table.set_vary(["phases.*.rigid_bodies.*.torsions.*.twist", "phases.*.scale"], True)
    theta = _twisted_theta(table, 25.0)
    answer = table.decode(theta)
    chart = table.commit(theta)
    assert chart is not None and np.array_equal(chart, np.ones(len(table.free_paths)))
    assert table.entries[table._paths[TWIST]].value == 0.0
    block = table.derived[0]
    assert block.phi0[0] == 45.0
    committed = table.decode(table.x0())
    assert max(abs(committed[p] - answer[p]) for p in table.derived_paths()) < 1e-12
    # the outcome takes the committed θ and keeps every other number
    n = len(table.free_paths)
    outcome = LSQOutcome(theta=theta, cost_initial=2.0, cost_final=1.0,
                         n_iterations=1, status="converged",
                         jac=np.arange(3.0 * n).reshape(3, n),
                         stderr_internal=np.ones(n), correlation=np.eye(n),
                         residual_cosine=np.zeros(n))
    moved = rechart_outcome(outcome, table.x0(), chart)
    assert np.array_equal(moved.theta, table.x0())
    assert np.array_equal(moved.jac, outcome.jac)
    assert np.array_equal(moved.correlation, outcome.correlation)
    # the record, and a fresh table on it
    table.apply_to_models(s, INS)
    assert s.phases[0].rigid_bodies[0].torsions[0].angle == 45.0
    fresh = ParameterTable(s, INS)
    assert fresh.entries[fresh._paths[TWIST]].value == 0.0
    again = fresh.decode(fresh.x0())
    assert max(abs(again[p] - answer[p]) for p in table.derived_paths()) < 1e-12


def test_the_twist_column_is_the_same_in_both_charts():
    """After the commit the twist column a fresh solve at δφ = 0 measures is
    the column the solve ended on: ∂θ_old/∂θ_new is the identity there, which
    is why the re-chart has nothing to move.  With the rotation composed in
    the same commit, the chart matrix keeps the twist row and column a unit
    vector: the two compositions do not mix."""
    s = _structure(-35.0)
    table = ParameterTable(s, INS)
    table.set_vary(["phases.*.rigid_bodies.*.torsions.*.twist",
                    "phases.*.rigid_bodies.*.rotation.*"], True)
    block = table.derived[0]
    paths = list(block.inputs)
    theta = _twisted_theta(table, 17.0)
    for k, v in enumerate((0.05, -0.03, 0.04)):
        theta[table.free_paths.index(f"phases.0.rigid_bodies.0.rotation.{k}")] = v
    before = table.decode(theta)
    x_old = np.array([before[p] for p in paths])
    col_old = block.jacobian(x_old)[:, paths.index(TWIST)]
    chart = table.commit(theta)
    after = table.decode(table.x0())
    x_new = np.array([after[p] for p in paths])
    col_new = block.jacobian(x_new)[:, paths.index(TWIST)]
    assert np.abs(col_new - col_old).max() < 1e-12 * np.abs(col_old).max()
    c = table.free_paths.index(TWIST)
    unit = np.zeros(len(table.free_paths))
    unit[c] = 1.0
    assert chart.ndim == 2
    assert np.array_equal(chart[c], unit) and np.array_equal(chart[:, c], unit)


def test_a_commit_that_skips_the_composition_is_refused(monkeypatch):
    """The commit-time guard (WP-1805) covers the torsion: zero δφ without
    composing it and the moved ring snaps back to φ₀, which leaves the
    solver's answer, and the commit raises rather than writes."""
    table = ParameterTable(_structure(10.0), INS)
    table.set_vary(["phases.*.rigid_bodies.*.torsions.*.twist"], True)
    monkeypatch.setattr(RigidBodyBlock, "commit_torsions",
                        lambda self, twists: bool(np.any(twists)))
    with pytest.raises(ValueError, match="left the solver's answer"):
        table.commit(_twisted_theta(table, 6.0))


def test_a_refused_commit_puts_the_torsion_anchor_back(monkeypatch):
    """#801's rollback covers the torsion: a commit the guard refuses leaves
    φ₀, the rotation anchor and every entry as they were before the call, and
    the anchors a later ``restore_body_anchors`` reads are still those of the
    last commit that went through.  Forced on a real composition, so φ₀ has
    moved (16 → 21) before the guard runs."""
    table = ParameterTable(_structure(10.0), INS)
    table.set_vary(["phases.*.rigid_bodies.*.torsions.*.twist",
                    "phases.*.rigid_bodies.*.rotation.*"], True)
    block = table.derived[0]
    table.commit(_twisted_theta(table, 6.0))
    assert block.phi0[0] == 16.0
    values = [e.value for e in table.entries]
    anchor = (block.q0.copy(), block.r0.copy(), block.axes.copy())

    def refuse(self, answer):
        raise ValueError("forced")

    monkeypatch.setattr(ParameterTable, "_check_committed_bodies", refuse)
    theta = _twisted_theta(table, 5.0)
    theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.0")] = 0.05
    with pytest.raises(ValueError, match="forced"):
        table.commit(theta)
    assert block.phi0[0] == 16.0
    assert [e.value for e in table.entries] == values
    for now, then in zip((block.q0, block.r0, block.axes), anchor, strict=True):
        assert np.array_equal(now, then)
    # the restore still steps back over the commit that went through
    assert table.restore_body_anchors([TWIST]) == ["phases.0.rigid_bodies.0"]
    assert block.phi0[0] == 10.0


def test_a_joint_commit_one_histogram_refuses_puts_every_torsion_anchor_back(
        monkeypatch):
    """#825's joint rollback covers the torsion: when the second histogram's
    table refuses, the first table, which composed its twist (φ₀ 16 → 21)
    before the refusal, gets φ₀ and the anchors a later
    ``restore_body_anchors`` reads back, so the histograms never disagree on
    the torsion."""
    from rietx.params.multi import MultiParameterTable

    ins2 = Instrument.debye_scherrer(wavelength=0.7107)
    mt = MultiParameterTable(_structure(10.0), [INS, ins2])
    mt.set_vary(["phases.*.rigid_bodies.*.torsions.*.twist"], True)
    twist = mt.free_paths.index(TWIST)
    blocks = [t.derived[0] for t in mt.tables]
    theta = mt.x0()
    theta[twist] = 6.0
    mt.commit(theta)
    mt._rebuild_columns()
    assert [b.phi0[0] for b in blocks] == [16.0, 16.0]

    def refuse(answer):
        raise ValueError("forced")

    monkeypatch.setattr(mt.tables[1], "_check_committed_bodies", refuse)
    theta = mt.x0()
    theta[twist] = 5.0
    with pytest.raises(ValueError, match="forced"):
        mt.commit(theta)
    assert [b.phi0[0] for b in blocks] == [16.0, 16.0]
    # the restore still steps back over the commit that went through
    assert mt.tables[0].restore_body_anchors([TWIST]) == ["phases.0.rigid_bodies.0"]
    assert blocks[0].phi0[0] == 10.0
    # positive arm: the same θ, unrefused, composes the twist in both tables
    blocks[0].restore_torsions([16.0])
    monkeypatch.undo()
    mt.commit(theta)
    assert [b.phi0[0] for b in blocks] == [21.0, 21.0]


def test_a_collapsed_phase_restore_puts_the_torsion_anchor_back():
    """``restore_body_anchors`` (WP-1301's restore, WP-1805's anchor) puts a
    torsion's φ₀ back when its twist is among the restored paths, and only
    then: zeroing the restored twist alone would leave the turn in φ₀."""
    table = ParameterTable(_structure(10.0), INS)
    table.set_vary(["phases.*.rigid_bodies.*.torsions.*.twist"], True)
    table.commit(_twisted_theta(table, 6.0))
    block = table.derived[0]
    assert block.phi0[0] == 16.0
    assert table.restore_body_anchors(["phases.0.rigid_bodies.0.rotation.0"]) == []
    assert block.phi0[0] == 16.0
    assert table.restore_body_anchors([TWIST]) == ["phases.0.rigid_bodies.0"]
    assert block.phi0[0] == 10.0
    restored = table.decode(table.x0())
    original = ParameterTable(_structure(10.0), INS)
    first = original.decode(original.x0())
    assert max(abs(restored[p] - first[p]) for p in table.derived_paths()) < 1e-12


def test_a_twist_set_by_hand_is_written_as_the_angle_it_describes():
    """A value set and not committed (``set_values``, a textdoc edit) is the
    pose φ₀ + δφ, written into (−180, 180] — and an angle already inside is
    written bit for bit, so a record does not drift by rounding."""
    s = _structure(170.0)
    table = ParameterTable(s, INS)
    table.entries[table._paths[TWIST]].value = 25.0
    table.refresh_ties()
    table.apply_to_models(s, INS)
    assert s.phases[0].rigid_bodies[0].torsions[0].angle == -165.0
    ParameterTable(s, INS)                          # and it builds: no drift
    assert wrap_degrees(0.1) == 0.1 and wrap_degrees(-180.0) == 180.0
    assert wrap_degrees(540.0) == 180.0


def test_ties_from_a_twist_are_refused_and_twist_to_twist_is_allowed():
    """The twist is a third increment kind: it follows only another twist,
    and only another twist follows it (WP-1805's tie rule)."""
    s = _structure(10.0)
    phase = s.phases[0]
    body = phase.rigid_bodies[0]
    body = body.model_copy(update={"torsions": [*body.torsions, BodyTorsion(
        name="other", axis=("C0", "C1"), moves=["C2", "C3"])]})
    s = Structure(phases=[phase.model_copy(update={"rigid_bodies": [body]})])
    table = ParameterTable(s, INS)
    with pytest.raises(ValueError, match="restart"):
        table.set_tie("phases.0.atoms.0.occ", AffineTie(terms=((TWIST, 1.0),)))
    with pytest.raises(ValueError, match="restart"):
        table.set_tie(TWIST, AffineTie(terms=(("phases.0.rigid_bodies.0.rotation.0", 1.0),)))
    table.set_tie("phases.0.rigid_bodies.0.torsions.1.twist",
                  AffineTie(terms=((TWIST, 1.0),)))


def test_the_series_carry_sets_the_twist_from_the_record():
    """A series carries a body's record, never its increment (WP-1805): the
    twist on the next model is the source's angle less this model's anchor,
    and the body lands on the source's atoms.  Carrying the twist entry, which
    reads zero on a fitted model, would leave the ring where it started."""
    from rietx.sequential import _carry_into, _relative_paths

    source = _structure(40.0)
    target = _structure(-5.0)
    displaced = _carry_into(target, INS.model_copy(deep=True), (source, INS), ["*"])
    assert TWIST in displaced
    assert target.phases[0].rigid_bodies[0].torsions[0].angle == pytest.approx(40.0,
                                                                                abs=1e-12)
    assert np.abs(_atoms(target) - _atoms(source)).max() < 1e-12
    assert TWIST in _relative_paths(source, INS)


def test_a_body_with_a_torsion_round_trips_through_json_and_textdoc(tmp_path):
    """JSON keeps the torsion; render, parse, diff is a fixed point with one
    declared; a text edit of the twist turns the ring, composing into the
    record, and the re-render is a fixed point again."""
    import rietx as rx
    from rietx.gui import textdoc as td
    from tests.test_project import _write_xye

    s = _structure(30.0, vary=True)
    assert Structure.model_validate_json(s.model_dump_json()) == s
    path = _write_xye(tmp_path / "bp.xye", _synthesize(s))
    project = rx.Project.create(tmp_path / "bp.rex", pattern=path, structure=s,
                                instrument=INS, plan="mccusker_default")
    text = td.render(project)
    parsed = td.parse(text)
    assert parsed.errors == []
    delta, errors = td.changes(parsed, project)
    assert errors == [] and delta.is_empty(), delta.as_dict()
    edited, hit = [], False
    for line in text.splitlines():
        head = line.split("#")[0].split()
        if head[:1] == ["rigid_bodies.0.torsions.0.twist"]:
            k = 2 if head[1] == "@" else 1
            line = "  " + " ".join([*head[:k], "5.0", *head[k + 1:]])
            hit = True
        edited.append(line)
    assert hit, "the twist has a row in the document"
    delta, errors = td.changes(td.parse("\n".join(edited) + "\n"), project)
    assert errors == []
    td.apply(project, delta)
    moved = project.refinement.structure.phases[0]
    body = moved.rigid_bodies[0]
    assert body.torsions[0].angle == pytest.approx(35.0, abs=1e-12)
    frac = np.array([[a.x.value, a.y.value, a.z.value] for a in moved.atoms])
    assert np.allclose(frac, body_fractional(body, moved.cell.lengths_angles()),
                       atol=1e-12)
    delta, errors = td.changes(td.parse(td.render(project)), project)
    assert errors == [] and delta.is_empty()


def test_a_zero_length_axis_is_refused_by_the_torsions_name():
    """Two coincident axis points, or an earlier torsion that carries one axis
    atom onto the other, divided by |T_b − T_a| = 0 and put NaN on every atom
    of the body with no error (NaN < tol is False); both are refused, naming
    the torsion by its declared name."""
    def block(template, torsions, angles=(0.0, 0.0)):
        return RigidBodyBlock(phase_base="p", body_base="b", atom_bases=["a0", "a1", "a2", "a3"],
                              template=np.array(template, dtype=float),
                              q0=(1.0, 0.0, 0.0, 0.0), torsions=torsions,
                              angles=angles[:len(torsions)],
                              names=["hinge", "flap"][:len(torsions)])
    # coincident axis points in the template itself
    coincident = [(0, 0, 0), (1, 0, 0), (1, 0, 0), (0.5, 1.2, 0.3)]
    with pytest.raises(ValueError, match="'hinge' has a zero-length axis"):
        block(coincident, [(1, 2, [3])])
    # atoms 2 and 3 are 1.4 Å apart in the template, but the first torsion's
    # 90° turn about the x axis carries atom 2 onto atom 3
    chained = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 0, 1)]
    block(chained, [(0, 1, [2]), (2, 3, [0])], angles=(0.0, 0.0))       # builds at φ₀ = 0
    with pytest.raises(ValueError, match="'flap' has a zero-length axis"):
        block(chained, [(0, 1, [2]), (2, 3, [0])], angles=(90.0, 0.0))
