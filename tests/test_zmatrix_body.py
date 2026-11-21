"""Z-matrix bodies: refinable bond lengths, angles and dihedrals (WP-1814).

A ``RigidBody`` with a ``zmatrix`` builds its template as Z(ζ) − c₀, and each
line's ``r``, ``angle`` and ``dihedral`` refines as an absolute entry
``phases.i.rigid_bodies.b.zmatrix.k.{r,angle,dihedral}``.  The tests are the
design review's (``wp1814d``, § Acceptance): T1 the identity σ(geometry) =
σ(internal) through the real table, T3 the composed block against central
differences, T5 the round trip, T6 every stage-start refusal with its negative
control, T6b the propagated esd against Monte Carlo, T6c a synthetic recovery
with the three breaks it must catch.  T4 is ``test_cross_backend``'s
``bodies_zmatrix`` row; T2 is C2a's, in ``test_fragments``.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from rietx import Refinement
from rietx.crystallography.bodies import add_body, zmatrix_body_from_atoms
from rietx.crystallography.fragments import (
    ZMATRIX_ANGLE_EDGE,
    ZMATRIX_R_FLOOR,
    zmatrix_points,
)
from rietx.crystallography.riding import riding_parents, set_riding_lengths
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.model.forward import compile_model
from rietx.model.geometry import geometry_from_sites
from rietx.params import bodies as pbodies
from rietx.params import vector as pvector
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    Atom,
    BodyTorsion,
    Phase,
    RigidBody,
    Structure,
    ZLine,
    zmatrix_template,
)
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_rigid_body import INS, _cell, synthesize

P = Parameter
B0 = "phases.0.rigid_bodies.0"

# #759's 8-atom fragment (C2a's ``test_fragments._BRANCHED``): references that
# are not a chain, a 180° dihedral on an open angle, and a methyl pair
BRANCHED = [("C",), ("C", 0, 1.51), ("O", 1, 1.43, 0, 109.5),
            ("C", 1, 1.50, 0, 112.7, 2, 122.5), ("O", 0, 1.27, 1, 117.4, 2, 10.0),
            ("O", 0, 1.27, 1, 117.4, 4, 180.0), ("H", 3, 0.96, 1, 109.5, 0, 180.0),
            ("H", 3, 0.96, 1, 109.5, 0, -60.0)]


def zlines(lines, vary: bool = False, dummies=()) -> list[ZLine]:
    """Z-matrix tuples → ``ZLine``s labelled species + line index."""
    out = []
    for i, ln in enumerate(lines):
        refs = dict(zip("bcd", (int(k) for k in ln[1::2]), strict=False))
        vals = {n: P(value=float(v), vary=vary)
                for n, v in zip(("r", "angle", "dihedral"), ln[2::2], strict=False)}
        out.append(ZLine(atom=None if i in dummies else f"{ln[0]}{i}", **refs, **vals))
    return out


def zbody_structure(lines=BRANCHED, *, vary=False, torsions=(), dummies=(),
                    origin=(0.31, 0.42, 0.27), q=(0.9, 0.1, 0.2, 0.3),
                    sg="P-1") -> Structure:
    zm = zlines(lines, vary, dummies)
    keep = [i for i in range(len(lines)) if i not in dummies]
    seed = Atom(label="seed", species="C", x=P(value=0.0), y=P(value=0.0), z=P(value=0.0))
    phase = Phase(name="zb", space_group=sg, cell=_cell(), atoms=[seed],
                  scale=P(value=1e-2, min=0.0))
    phase = add_body(phase, "zb", [zm[i].atom for i in keep], [lines[i][0] for i in keep],
                     None, origin, orientation=q, biso=2.0, zmatrix=zm,
                     torsions=list(torsions))
    return Structure(phases=[Phase.model_validate(
        {**phase.model_dump(), "atoms": phase.model_dump()["atoms"][1:]})])


def _table(structure, globs) -> ParameterTable:
    table = ParameterTable(structure, INS)
    table.set_vary(["*"], False)
    for g in globs:
        assert table.set_vary([g], True), g
    return table


# ------------------------------------------------------------ schema, builders
def test_the_template_is_the_zmatrix_record_and_a_stale_one_is_refused():
    body = zbody_structure().phases[0].rigid_bodies[0]
    assert np.allclose(body.template, zmatrix_template(body.zmatrix, body.zmatrix_origin),
                       atol=1e-15)
    doc = body.model_dump()
    doc["zmatrix"][3]["r"]["value"] = 1.55
    with pytest.raises(ValueError, match="RIGID_BODY_TEMPLATE_DRIFT: rigid body 'zb'"):
        RigidBody.model_validate(doc)
    doc = body.model_dump()
    doc["zmatrix"][2]["d"] = 0
    with pytest.raises(ValueError, match="line 2 takes b, c and r, angle, and nothing else"):
        RigidBody.model_validate(doc)
    doc = body.model_dump()
    doc["zmatrix"][1]["atom"] = "elsewhere"
    with pytest.raises(ValueError, match="must be the body's atoms"):
        RigidBody.model_validate(doc)


def test_the_tree_builder_reproduces_the_atoms_and_roots_at_its_origin():
    """M32: placed atoms → a Z body whose map puts them back; with ``origin``
    the Z-matrix is rooted at that atom, which no internal moves (M3)."""
    s = zbody_structure()
    phase = s.phases[0]
    labels = [a.label for a in phase.atoms]
    tree = [("C0", "C1"), ("C1", "O2"), ("C1", "C3"), ("C0", "O4"), ("C0", "O5"),
            ("C3", "H6"), ("C3", "H7")]
    for origin in (None, "C1"):
        body = zmatrix_body_from_atoms(phase, labels, "tree", tree=tree, origin=origin)
        assert body.atoms[0] == (origin or "C0")
        new = Phase.model_validate({**phase.model_dump(),
                                    "rigid_bodies": [body.model_dump()]})
        table = ParameterTable(Structure(phases=[new]), INS)   # drift-checked
        values = table.decode(table.x0())
        index = {a.label: j for j, a in enumerate(new.atoms)}
        frac = np.array([[values[f"phases.0.atoms.{index[lab]}.{c}"] for c in "xyz"]
                         for lab in body.atoms])
        want = np.array([[a.x.value, a.y.value, a.z.value]
                         for a in (new.atoms[index[lab]] for lab in body.atoms)])
        assert np.abs(frac - want).max() < 1e-12
        if origin is not None:
            # the origin atom sits at line 0, so no internal reaches it
            block = table._bodies[0][2]
            assert all(0 not in r for r in block.zmatrix.reach())
    with pytest.raises(ValueError, match="spanning tree"):
        zmatrix_body_from_atoms(phase, labels, "tree", tree=tree[:-1])


def test_the_tree_builder_reads_a_linear_group_without_nan():
    """An exactly linear group (acetylene on an axis): the reference half-plane
    is undefined, so the dihedral reads 0 as ``zmatrix_points`` takes it,
    instead of the 0/0 that refused the body as "dihedral is not finite"."""
    x = [-1.66, -0.60, 0.60, 1.66]
    atoms = [Atom(label=f"{el}{i}", species=el, x=P(value=0.05 + v / 10.0),
                  y=P(value=0.2), z=P(value=0.3))
             for i, (el, v) in enumerate(zip("HCCH", x, strict=True))]
    phase = Phase(name="ac", space_group="P1", cell=_cell(), atoms=atoms,
                  scale=P(value=1e-2, min=0.0))
    with np.errstate(all="raise"):
        body = zmatrix_body_from_atoms(
            phase, [a.label for a in atoms], "ac",
            tree=[("H0", "C1"), ("C1", "C2"), ("C2", "H3")])
    assert all(math.isfinite(p.value) for z in body.zmatrix for _, p in z.internals())
    assert body.zmatrix[3].dihedral.value == 0.0
    assert abs(body.zmatrix[3].angle.value - 180.0) < 1e-6


def test_a_riding_h_rides_on_its_lines_b():
    """M13: on a Z body the parent is the H line's b, and the length is its r."""
    body = zbody_structure().phases[0].rigid_bodies[0]
    rode = set_riding_lengths(body, {"H6": "CH3", "H7": "CH3"}, "neutron")
    assert riding_parents(rode) == {"H6": "C3", "H7": "C3"}
    assert rode.zmatrix[6].r.value == rode.zmatrix[7].r.value == 1.059
    assert rode.zmatrix[6].angle.value == body.zmatrix[6].angle.value
    doc = rode.model_dump()
    doc["zmatrix"][3]["atom"] = None           # the parent line made a dummy
    doc["atoms"].remove("C3")
    doc["template"] = zmatrix_template([ZLine.model_validate(z) for z in doc["zmatrix"]],
                                       rode.zmatrix_origin)
    with pytest.raises(ValueError, match="riding H 'H6' is placed from line 3 \\(a dummy\\)"):
        RigidBody.model_validate(doc)


def test_the_internals_are_absolute_boxed_entries():
    """M7, M8: one entry per internal at its own path, r above 0 and the angle
    inside (0, 180) whatever the parameter declared, each stopping a floor and
    an edge short of what ``zmatrix_points`` refuses; the dihedral keeps its
    own box."""
    zm = zlines(BRANCHED)
    zm[3] = zm[3].model_copy(update={"angle": P(value=112.7, min=-5.0, max=200.0),
                                     "dihedral": P(value=122.5, min=100.0, max=140.0)})
    s = zbody_structure()
    body = s.phases[0].rigid_bodies[0].model_copy(update={"zmatrix": zm})
    s.phases[0].rigid_bodies[0] = body
    table = ParameterTable(s, INS)
    paths = [e.path for e in table.entries if ".zmatrix." in e.path]
    assert len(paths) == 18 and paths[:3] == [f"{B0}.zmatrix.1.r", f"{B0}.zmatrix.2.r",
                                              f"{B0}.zmatrix.2.angle"]
    e = {x.path: x for x in table.entries}
    assert (e[f"{B0}.zmatrix.1.r"].lo, e[f"{B0}.zmatrix.1.r"].hi) == (ZMATRIX_R_FLOOR, math.inf)
    assert (e[f"{B0}.zmatrix.3.angle"].lo, e[f"{B0}.zmatrix.3.angle"].hi) == (
        ZMATRIX_ANGLE_EDGE, 180.0 - ZMATRIX_ANGLE_EDGE)
    assert (e[f"{B0}.zmatrix.3.dihedral"].lo, e[f"{B0}.zmatrix.3.dihedral"].hi) == (100.0, 140.0)
    assert (e[f"{B0}.zmatrix.4.dihedral"].lo, e[f"{B0}.zmatrix.4.dihedral"].hi) == (-math.inf,
                                                                                   math.inf)
    assert set(paths) <= set(table.body_dofs())


def _place_at(lines, k, name, value, *, tangents=False):
    """``zmatrix_points`` with line ``k``'s ``name`` set to ``value`` (numpy)."""
    zm = zlines(lines)
    vals = [tuple(p.value for _, p in z.internals()) for z in zm]
    col = ("r", "angle", "dihedral").index(name)
    vals[k] = tuple(value if j == col else v for j, v in enumerate(vals[k]))
    return zmatrix_points([z.refs() for z in zm], vals, tangents=tangents)


CHAIN = [("C",), ("C", 0, 1.5), ("C", 1, 1.5, 0, 110.0), ("C", 2, 1.5, 1, 110.0, 0, 60.0),
         ("C", 3, 1.5, 2, 110.0, 1, 60.0), ("C", 4, 1.5, 3, 110.0, 2, 60.0)]


def test_an_internal_on_the_edge_of_its_box_still_places_every_line():
    """The box stops short of what ``zmatrix_points`` refuses, because the
    default LM driver lands a value exactly on its bound (WP-1938): a length at
    0 raises "not positive", and an angle at 180° makes a later line's
    reference triple collinear.  Every internal on either edge of its box
    places every line, tangents included; the old edge (the control) raises."""
    s = zbody_structure(CHAIN)
    table = ParameterTable(s, INS)
    entries = {e.path: e for e in table.entries if ".zmatrix." in e.path}
    n_edges = 0
    for k in range(1, len(CHAIN)):
        for name in ("r", "angle", "dihedral")[:min(k, 3)]:
            if name == "dihedral":
                continue                    # the dihedral places at any value
            e = entries[f"{B0}.zmatrix.{k}.{name}"]
            for edge in (e.lo, e.hi):
                if not math.isfinite(edge):
                    continue
                pts, tan = _place_at(CHAIN, k, name, edge, tangents=True)
                assert np.isfinite(pts).all() and np.isfinite(tan).all(), (k, name, edge)
                n_edges += 1
    assert n_edges == 5 + 4 * 2             # five lengths, four angles at both edges
    # positive arm: the values the box used to allow are refused mid-solve
    with pytest.raises(ValueError, match="not positive"):
        _place_at(CHAIN, 1, "r", 0.0)
    with pytest.raises(ValueError, match="collinear"):
        _place_at(CHAIN, 2, "angle", 180.0)


def test_a_pattern_computes_with_an_angle_and_a_length_on_their_bounds():
    """The solve's own path (``table.decode`` into the compiled model) with
    line 2's angle on the box's far edge, where line 3 takes its triple: the
    pattern is finite.  Before the box stopped short, 180° raised here."""
    s = zbody_structure(CHAIN)
    pattern = synthesize(s)
    model = compile_model(s, INS, pattern, mode="rietveld")
    for name, k, edge in (("angle", 2, "hi"), ("angle", 3, "lo"), ("r", 1, "lo")):
        path = f"{B0}.zmatrix.{k}.{name}"
        table = _table(s, [path])
        e = table.entries[[x.path for x in table.entries].index(path)]
        theta = np.array([e.hi if edge == "hi" else e.lo], dtype=float)
        assert theta.shape == np.asarray(table.x0()).shape, path
        assert np.isfinite(model.evaluate(table.decode(theta))).all(), path


# ------------------------------------------------------------------- T1, T3
def _proxy_covariance(n, seed=7):
    a = np.random.default_rng(seed).normal(size=(n, n))
    cov = a @ a.T / n + 0.1 * np.eye(n)
    sd = np.sqrt(np.diag(cov))
    return sd * 1e-2, cov / np.outer(sd, sd)


def test_an_internal_and_its_own_geometry_carry_one_esd():
    """T1: for every line, the bond, angle and torsion it sets equal its
    internal in value (1e-12) and in esd (1e-9 relative) through the real
    table's covariance, with the pose free beside the internals."""
    s = zbody_structure(vary=True)
    table = _table(s, [f"{B0}.origin.dof.*", f"{B0}.rotation.*", f"{B0}.zmatrix.*",
                       "phases.0.scale"])
    theta = table.x0()
    s_int, corr = _proxy_covariance(len(theta))
    esd = table.stderr_physical(theta, s_int, corr)
    geo = geometry_from_sites([compile_phase_sites(s.phases[0])], table, theta, s,
                              stderr_internal=s_int, correlation=corr)
    body = s.phases[0].rigid_bodies[0]
    lab = [z.atom for z in body.zmatrix]
    seen: dict[str, set] = {"r": set(), "angle": set(), "dihedral": set()}
    for k, z in enumerate(body.zmatrix):
        for name, p in z.internals():
            want_v, want_s = p.value, esd[f"{B0}.zmatrix.{k}.{name}"]
            ends = (lab[k], *(lab[i] for i in z.refs()[:("r", "angle", "dihedral")
                                                       .index(name) + 1]))
            if name == "r":
                rows = [(g.distance, g.stderr) for g in geo.distances
                        if {g.atom_1, g.atom_2} == set(ends) and g.symmetry_2 == "."]
            elif name == "angle":
                rows = [(g.angle, g.stderr) for g in geo.angles
                        if g.atom_2 == ends[1] and {g.atom_1, g.atom_3} == {ends[0], ends[2]}
                        and g.symmetry_1 == g.symmetry_3 == "."]
            else:
                rows = [(g.angle, g.stderr) for g in geo.torsions
                        if (g.atom_1, g.atom_2, g.atom_3, g.atom_4) in (ends, ends[::-1])
                        and {g.symmetry_1, g.symmetry_2, g.symmetry_3, g.symmetry_4} == {"."}]
            for value, sigma in rows:
                assert abs(pbodies.wrap_degrees(value - want_v)) < 1e-12 or \
                    abs(value - want_v) < 1e-12, (k, name, value, want_v)
                assert sigma == pytest.approx(want_s, rel=1e-9), (k, name)
                seen[name].add(k)
    # every line's bond and angle is a bonded row; dihedrals where the chain is
    assert (len(seen["r"]), len(seen["angle"])) == (7, 6) and len(seen["dihedral"]) >= 2, seen


def test_the_composed_block_matches_central_differences_and_its_reach():
    """T3: anchor turned, twist and ζ off zero, two chained torsions (the
    second's axis on an atom the first moves and internals move), triclinic:
    every column against central differences, and the reach pattern covers
    every nonzero at 20 states."""
    tors = [BodyTorsion(name="t0", axis=("C1", "C3"), moves=["H6", "H7"], angle=12.0),
            BodyTorsion(name="t1", axis=("C3", "H6"), moves=["H7"], angle=-7.0)]
    s = zbody_structure(vary=True, torsions=tors)
    table = ParameterTable(s, INS)
    block = table._bodies[0][2]
    x0 = np.array([table.entries[table._paths[q]].value for q in block.inputs])
    rng = np.random.default_rng(11)
    pattern = block.reach_pattern()
    n_tail = len(x0) - 9
    for state in range(20):
        x = x0.copy()
        x[9:12] = rng.normal(scale=0.1, size=3)
        tail = rng.normal(scale=1.0, size=n_tail - 3)
        tail[:2] *= 6.0                                   # twists, degrees
        x[12:] += tail * np.where(np.char.endswith(np.array(block.inputs[12:]), ".r"),
                                  0.03, 1.0)
        jac = block.jacobian(x)
        assert not (np.abs(jac) > 0.0)[~pattern].any(), state
        if state < 3:
            h, fd = 1e-5, np.zeros_like(jac)
            for c in range(len(x)):
                xp, xm = x.copy(), x.copy()
                xp[c] += h
                xm[c] -= h
                fd[:, c] = (block.evaluate(xp) - block.evaluate(xm)) / (2 * h)
            assert np.abs(jac - fd).max() < 1e-9, (state, np.abs(jac - fd).max())


# ------------------------------------------------------------------------ T5
def test_the_round_trip_keeps_the_body_and_wraps_only_an_unboxed_dihedral():
    """T5: a commit past ±180° wraps an unboxed dihedral and leaves a boxed
    one as written; the write-back stores the internals, their esds and
    template = Z − c₀; JSON and a rebuild put every atom back to 1e-12 Å."""
    zm = zlines(BRANCHED, vary=True)
    zm[5] = zm[5].model_copy(update={"dihedral": P(value=180.0, vary=True,
                                                   min=-200.0, max=200.0)})
    s = zbody_structure()
    s.phases[0].rigid_bodies[0] = s.phases[0].rigid_bodies[0].model_copy(
        update={"zmatrix": zm})
    table = _table(s, [f"{B0}.zmatrix.*"])
    theta = table.x0()
    free = table.free_paths
    theta[free.index(f"{B0}.zmatrix.4.dihedral")] = 190.0      # unboxed
    theta[free.index(f"{B0}.zmatrix.5.dihedral")] = 190.0      # boxed to ±200
    theta[free.index(f"{B0}.zmatrix.3.r")] = 1.56
    placed = table.decode(theta)
    chart = table.commit(theta)
    assert chart is not None and np.all(chart == 1.0)           # a translation
    values = table.decode(table.x0())
    assert values[f"{B0}.zmatrix.4.dihedral"] == pytest.approx(-170.0, abs=1e-12)
    assert values[f"{B0}.zmatrix.5.dihedral"] == 190.0
    esd = {q: 1e-3 for q in table.free_paths}
    out = s.model_copy(deep=True)
    table.apply_to_models(out, INS.model_copy(deep=True), esd)
    body = out.phases[0].rigid_bodies[0]
    assert body.zmatrix[3].r.value == 1.56 and body.zmatrix[3].r.stderr == 1e-3
    assert np.allclose(body.template, zmatrix_template(body.zmatrix, body.zmatrix_origin),
                       atol=0.0)
    back = Structure.model_validate(json.loads(out.model_dump_json()))
    rebuilt = ParameterTable(back, INS).decode(ParameterTable(back, INS).x0())
    atoms = [q for q in placed if q.startswith("phases.0.atoms.") and q[-1] in "xyz"]
    from rietx.params.derived import cartesian_frame
    m = np.asarray(cartesian_frame(back.phases[0].cell.lengths_angles()))
    gap = (np.array([rebuilt[q] for q in atoms]) - np.array([placed[q] for q in atoms]))
    assert np.abs(gap.reshape(-1, 3) @ m.T).max() < 1e-12


# ------------------------------------------------------------------------ T6
def _refusal(structure, globs):
    table = _table(structure, globs)
    table.refuse_free_internals()


def test_a_free_dihedral_beside_a_free_torsion_on_its_bond_is_refused():
    """M12: refused whatever the reaches, equal included (the adjudicator's
    case: |cos| 0.9939 for the same moved set); one of the two held is fine."""
    same = BodyTorsion(name="t", axis=("C1", "C3"), moves=["H6", "H7"])
    s = zbody_structure(torsions=[same])
    tw = f"{B0}.torsions.0.twist"
    with pytest.raises(ValueError, match=r"^RIGID_BODY_TORSION_REACH: rigid body 'zb': "
                       r"Z-matrix line 6 \(H6\)'s dihedral .* They reach different atoms"):
        _refusal(s, [f"{B0}.zmatrix.6.dihedral", tw])
    # equal reach: line 7's dihedral moves H7 alone, as a torsion moving H7 does
    s = zbody_structure(torsions=[same.model_copy(update={"moves": ["H7"]})])
    with pytest.raises(ValueError, match="They reach the same atoms, but a dihedral"):
        _refusal(s, [f"{B0}.zmatrix.7.dihedral", tw])
    _refusal(s, [f"{B0}.zmatrix.7.dihedral"])                # torsion held
    _refusal(s, [tw, f"{B0}.zmatrix.7.r"])                   # dihedral held


def test_an_internal_of_a_riding_h_is_refused_and_its_parents_is_not():
    s = zbody_structure()
    s.phases[0].rigid_bodies[0] = set_riding_lengths(
        s.phases[0].rigid_bodies[0], {"H6": "CH3"}, "xray")
    with pytest.raises(ValueError, match=r"^RIGID_BODY_RIDING_INTERNAL: .* line 6 \(H6\)"
                       r"'s angle .* riding H 'H6'"):
        _refusal(s, [f"{B0}.zmatrix.6.angle"])
    _refusal(s, [f"{B0}.zmatrix.3.r", f"{B0}.zmatrix.7.angle"])


# a bent body with a collinear stretch: line 4 sits on the C3–C0 line (its
# reference triple C3, C0, C1 is collinear, so its angle is 180° for good)
BENT = [("C",), ("C", 0, 1.4), ("O", 1, 1.3, 0, 120.0), ("C", 0, 1.2, 1, 180.0, 2, 0.0),
        ("H", 3, 1.06, 0, 180.0, 1, 0.0), ("O", 1, 1.25, 0, 118.0, 2, 180.0)]


def test_an_inert_dihedral_and_a_pinned_angle_are_refused():
    """M16: a free dihedral on a line at exactly 180°; and a free angle over a
    collinear reference triple, which no other angle places.  Line 5's
    dihedral (angle 118°) is fine."""
    s = zbody_structure(BENT)
    with pytest.raises(ValueError, match=r"^RIGID_BODY_INERT_DIHEDRAL: .* line 4 \(H4\)"
                       r"'s dihedral .* exactly 180°"):
        _refusal(s, [f"{B0}.zmatrix.4.dihedral"])
    with pytest.raises(ValueError, match=r"^RIGID_BODY_COLLINEAR_ANGLE: .* line 4 \(H4\)'s "
                       r"angle .* are collinear"):
        _refusal(s, [f"{B0}.zmatrix.4.angle"])
    _refusal(s, [f"{B0}.zmatrix.5.dihedral", f"{B0}.zmatrix.4.r", f"{B0}.zmatrix.3.angle"])


def test_a_linear_body_refines_its_lengths_and_refuses_a_bend():
    """M15: CO₂ (inertia rank 2)."""
    s = zbody_structure([("O",), ("C", 0, 1.16), ("O", 1, 1.16, 0, 180.0)])
    with pytest.raises(ValueError, match=r"^RIGID_BODY_LINEAR_BEND: .* line 2 \(O2\)'s angle"):
        _refusal(s, [f"{B0}.zmatrix.2.angle"])
    _refusal(s, [f"{B0}.zmatrix.*.r"])


def test_an_internal_that_moves_only_dummies_is_refused():
    """M17: a last dummy line, which no later line refers to."""
    s = zbody_structure([*BRANCHED, ("X", 0, 1.0, 1, 90.0, 2, 30.0)], dummies=(8,))
    with pytest.raises(ValueError, match=r"^RIGID_BODY_INERT_INTERNAL: .* line 8 \(dummy\)'s r .* "
                       r"moves nothing"):
        _refusal(s, [f"{B0}.zmatrix.8.r"])
    _refusal(s, [f"{B0}.zmatrix.7.*"])


def test_a_site_body_may_not_move_an_atom_on_its_site():
    """M14 (1807's torsion rule): PbSO₄'s SO₄ on the Pnma mirror, rooted at S2.
    O3 is on the mirror; O5 is general and its image is the space group's."""
    from tests.test_rigid_body_special import _pbso4, _with_body

    phase = _pbso4()
    body = zmatrix_body_from_atoms(phase, ["S2", "O3", "O4", "O5"], "SO4", origin="S2",
                                   tree=[("S2", "O3"), ("S2", "O4"), ("S2", "O5")])
    s = _with_body(phase, body)
    line = {z.atom: k for k, z in enumerate(body.zmatrix)}
    with pytest.raises(ValueError, match=r"^RIGID_BODY_NOT_INVARIANT: .* moves 'O3'"):
        _refusal(s, [f"{B0}.zmatrix.{line['O3']}.r"])
    _refusal(s, [f"{B0}.zmatrix.{line['O5']}.r", f"{B0}.zmatrix.{line['O5']}.angle"])


def test_the_refusals_run_at_stage_start_for_a_glob():
    """M18: a plan glob frees the internals by name only inside ``_run_stage``,
    so a build-time check of ``vary`` would never see it."""
    s = zbody_structure()
    s.phases[0].rigid_bodies[0] = set_riding_lengths(
        s.phases[0].rigid_bodies[0], {"H7": "CH3"}, "xray")
    pattern = synthesize(s)
    ref = Refinement(s, INS, history=False)
    with pytest.raises(ValueError, match="RIGID_BODY_RIDING_INTERNAL"):
        ref.fit(pattern, plan=RefinementPlan(stages=[
            Stage("z", ["phases.*.scale", f"{B0}.zmatrix.*"], max_iter=5)]))


# ----------------------------------------------------------- T6b, M24, M30
def test_the_propagated_esd_matches_monte_carlo():
    """T6b: J·Cov·Jᵀ against 4000 draws (5 %) for an intra-body distance two
    internals move and for a torsion (its difference taken on the circle);
    a bond no free internal moves has su None, the pose being free."""
    s = zbody_structure(vary=True)
    table = _table(s, [f"{B0}.origin.dof.*", f"{B0}.rotation.*",
                       f"{B0}.zmatrix.3.*", f"{B0}.zmatrix.6.*"])
    theta = table.x0()
    s_int, corr = _proxy_covariance(len(theta), seed=3)
    geo = geometry_from_sites([compile_phase_sites(s.phases[0])], table, theta, s,
                              stderr_internal=s_int, correlation=corr)
    pick = {(g.atom_1, g.atom_2): g for g in geo.distances if g.symmetry_2 == "."}
    d_h6 = pick.get(("C1", "H6")) or pick[("H6", "C1")]
    fixed = pick.get(("C0", "C1")) or pick[("C1", "C0")]
    assert fixed.stderr is None                                # nothing moves it
    tor = next(g for g in geo.torsions if {g.atom_1, g.atom_4} == {"H6", "O2"}
               and {g.symmetry_1, g.symmetry_2, g.symmetry_3, g.symmetry_4} == {"."})
    cov = corr * np.outer(s_int, s_int)
    draws = np.random.default_rng(5).multivariate_normal(theta, cov, size=4000)
    from rietx.params.derived import cartesian_frame
    m = np.asarray(cartesian_frame(s.phases[0].cell.lengths_angles()))
    index = {a.label: j for j, a in enumerate(s.phases[0].atoms)}

    def xyz(v, lab):
        return m @ np.array([v[f"phases.0.atoms.{index[lab]}.{c}"] for c in "xyz"])

    def dihedral(a, b, c, d):
        b0, b1, b2 = b - a, c - b, d - c
        n1, n2 = np.cross(b0, b1), np.cross(b1, b2)
        return math.degrees(math.atan2(np.dot(np.cross(n1, n2), b1 / np.linalg.norm(b1)),
                                       np.dot(n1, n2)))

    dist, tors = [], []
    for th in draws:
        v = table.decode(th)
        dist.append(np.linalg.norm(xyz(v, d_h6.atom_1) - xyz(v, d_h6.atom_2)))
        tors.append(dihedral(*(xyz(v, x) for x in (tor.atom_1, tor.atom_2,
                                                     tor.atom_3, tor.atom_4))))
    tors = np.array(tors)
    circ = pbodies.wrap_degrees  # the circular difference about the mean
    spread = np.array([circ(t - tor.angle) for t in tors])
    assert np.std(dist) == pytest.approx(d_h6.stderr, rel=0.05)
    assert np.std(spread) == pytest.approx(tor.stderr, rel=0.05)


def test_an_expression_on_an_internal_is_refused_by_name():
    """M24: a tie by expression on an internal is a derived block writing an
    input of the body's block, declared after it, so ``add_derived`` refuses it
    by name (measured: refused, not applied)."""
    s = zbody_structure(vary=True)
    ref = Refinement(s, INS, history=False)
    ref.add_variable("rch", 0.97, vary=True)
    with pytest.raises(ValueError, match=r"zmatrix\.7\.r' is an input of an earlier "
                       r"derived block.*declaration order"):
        ref.tie(f"{B0}.zmatrix.7.r", expression="rch")
        ref.parameters()


def test_the_misfit_body_arm_frees_the_internals_the_model_frees(monkeypatch):
    """M30: the body arm's globs gain each internal whose ``vary`` is set."""
    from rietx.report import body_misfit

    s = zbody_structure()
    s.phases[0].rigid_bodies[0].zmatrix[3].r.vary = True
    pattern = synthesize(s)
    ref = Refinement(s, INS, history=False)
    ref.fit(pattern, plan=RefinementPlan(stages=[Stage("scale", ["phases.*.scale"],
                                                       max_iter=3)]))
    seen = []

    class Stop(Exception):
        pass

    def spy(ref_, structure, data, globs, max_iter, **kw):
        seen.append(list(globs))
        raise Stop

    monkeypatch.setattr(body_misfit, "_fit", spy)
    with pytest.raises(Stop):
        body_misfit.rigid_body_misfit(ref, pattern)
    assert f"{B0}.zmatrix.3.r" in seen[0] and f"{B0}.zmatrix.4.r" not in seen[0]


def test_the_misfit_body_arm_frees_a_torsion_only_where_the_model_does(monkeypatch):
    """A held torsion beside a varied Z dihedral about its bond: freeing both
    makes the stage refuse (RIGID_BODY_TORSION_REACH) in a model that fits."""
    from rietx.report import body_misfit

    tw = f"{B0}.torsions.0.twist"
    for vary_torsion in (False, True):
        torsion = BodyTorsion(name="t", axis=("C1", "C3"), moves=["H7"],
                              vary=vary_torsion)
        s = zbody_structure(torsions=[torsion])
        s.phases[0].rigid_bodies[0].zmatrix[7].dihedral.vary = True
        pattern = synthesize(s)
        ref = Refinement(s, INS, history=False)
        ref.fit(pattern, plan=RefinementPlan(stages=[Stage(
            "scale", ["phases.*.scale"], max_iter=3)]))
        seen = []

        class Stop(Exception):
            pass

        def spy(ref_, structure, data, globs, max_iter, **kw):
            seen.append(list(globs))
            raise Stop

        monkeypatch.setattr(body_misfit, "_fit", spy)
        with pytest.raises(Stop):
            body_misfit.rigid_body_misfit(ref, pattern)
        assert f"{B0}.zmatrix.7.dihedral" in seen[0]
        assert (tw in seen[0]) is vary_torsion


# ----------------------------------------------------------------------- T6c
def _recovery(monkeypatch, brk: str | None) -> list[str]:
    """Plant r(C1–C3) 1.51 → 1.56 and dihedral(line 4) 178 → −178 (across the
    cut) on the 8-atom fragment, start at the template, fit: returns the
    checks that failed (empty when the recovery holds)."""
    truth_lines = [list(ln) for ln in BRANCHED]
    truth_lines[3][2] = 1.56
    truth_lines[4][6] = -178.0
    start_lines = [list(ln) for ln in BRANCHED]
    start_lines[3][2] = 1.51
    start_lines[4][6] = 178.0
    truth = zbody_structure([tuple(x) for x in truth_lines])
    pattern = synthesize(truth)
    start = zbody_structure([tuple(x) for x in start_lines])
    if brk == "tangents":
        real = pbodies.ZMatrixMap.points

        def flat(self, zeta, *, tangents=False):
            out = real(self, zeta, tangents=tangents)
            return (out[0], 0.0 * out[1]) if tangents else out
        monkeypatch.setattr(pbodies.ZMatrixMap, "points", flat)
    elif brk == "template":
        monkeypatch.setattr(pvector, "zmatrix_template",
                            lambda zm, c0: list(start.phases[0].rigid_bodies[0].template))
    elif brk == "wrap":
        monkeypatch.setattr(pvector.ParameterTable, "_wrap_dihedrals", lambda self: False)
    ref = Refinement(start, INS, history=False)
    failed = []
    try:
        res = ref.fit(pattern, plan=RefinementPlan(stages=[Stage(
            "z", ["phases.*.scale", f"{B0}.zmatrix.3.r", f"{B0}.zmatrix.4.dihedral"],
            max_iter=60)], closing_window_tol=None))
        body = ref.fitted_structure.phases[0].rigid_bodies[0]
    except ValueError as exc:
        return [f"raised: {str(exc)[:80]}"]
    r = res.parameter(f"{B0}.zmatrix.3.r")
    # the planted offset is 0.05 Å; the data put it back within a fifth of it
    if not abs(r.value - 1.56) < 0.01:
        failed.append(f"r {r.value}")
    # the body's atoms carry esds only through the internals' tangents here
    # (the pose is held), so a zeroed tangent leaves them without one
    c3 = ref.fitted_structure.phases[0].atoms[3]
    if not (c3.x.stderr or 0.0) > 0.0:
        failed.append("C3 esd")
    phi = body.zmatrix[4].dihedral.value
    if not (-180.0 < phi <= 180.0 and abs(phi + 178.0) < 0.5):
        failed.append(f"dihedral {phi}")
    if np.abs(np.array(body.template) - np.array(
            zmatrix_template(body.zmatrix, body.zmatrix_origin))).max() > 1e-9:
        failed.append("template")
    return failed


@pytest.mark.parametrize("brk", [None, "tangents", "template", "wrap"])
def test_a_planted_length_and_dihedral_are_recovered_and_each_break_is_caught(
        monkeypatch, brk):
    """T6c: the recovery holds, and fails with the tangents zeroed, the
    template write-back skipped, or the commit's wrap skipped."""
    failed = _recovery(monkeypatch, brk)
    assert (not failed) if brk is None else bool(failed), failed
