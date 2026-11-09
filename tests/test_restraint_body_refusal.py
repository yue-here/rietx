"""Restrained or refined, never both by accident (WP-1814, chunk C1).

A bond, angle, torsion or planarity restraint whose atoms all sit in one copy
of one rigid body, with no declared torsion of the body able to change the
quantity, is a constant row: the body places those atoms from its template,
so no parameter moves it.  ``model.restraints.resolve_phase_restraints``
refuses it at compile with ``RESTRAINT_ON_FIXED_BODY_GEOMETRY``.

The rule is a set rule per torsion: the quantity changes unless the
restraint's atoms other than the torsion's two axis atoms all lie in
``moves`` or all lie outside it.  The first test is its verification against
the geometry itself: on a generic body with a chained torsion, for every bond,
bond angle and torsion of its atoms, the rule refuses exactly the quantities
that stay put when every torsion twists and the pose and cell move.  The rest
check the seat (compile, before any fit) and each accepting arm.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography.bodies import add_body, body_fractional
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.model.forward import compile_model
from rietx.model.restraints import RestraintRefused, _refuse_fixed_body_geometry
from rietx.params.derived import cartesian_frame
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    AngleRestraint,
    Atom,
    BodyTorsion,
    BondRestraint,
    Cell,
    Phase,
    PlanarityRestraint,
    Structure,
    TetherRestraint,
    TorsionRestraint,
)

CODE = "RESTRAINT_ON_FIXED_BODY_GEOMETRY"
INS = Instrument.debye_scherrer(wavelength=1.5406)
CELL = (8.1, 9.3, 10.2, 86.0, 95.0, 101.0)

#: a bent chain with a side atom and a branch: generic, no symmetry, no atom
#: on any torsion axis
CHAIN = np.array([[0.0, 0.0, 0.0], [1.5, 0.1, 0.0], [2.1, 1.4, 0.2],
                  [3.6, 1.5, 0.6], [4.2, 2.8, 0.4], [2.0, 2.0, -1.2],
                  [-0.6, -1.1, 0.7]])
CHAIN_LABELS = [f"K{i}" for i in range(7)]
#: (axis_a, axis_b, moves); the second torsion's axis atom K3 is moved by the
#: first, so the chain-of-isometries argument is exercised
CHAIN_TORSIONS = [("K1", "K2", ["K3", "K4"]), ("K2", "K3", ["K4"]),
                  ("K0", "K1", ["K5"])]

#: a second body: a bent three-atom unit with no torsion
TRIAD = np.array([[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [1.6, 1.1, 0.0]])
TRIAD_LABELS = ["T0", "T1", "T2"]


def _phase(restraints=(), *, torsions=CHAIN_TORSIONS) -> Phase:
    """One free atom (index 0), the chain body (1-7), the triad body (8-10)."""
    P = Parameter
    phase = Phase(name="p", space_group="P-1", atoms=[
        Atom(label="Li", species="Li", x=P(value=0.71), y=P(value=0.12), z=P(value=0.63))],
        cell=Cell(**{k: P(value=v) for k, v in zip(
            ("a", "b", "c", "alpha", "beta", "gamma"), CELL, strict=True)}),
        scale=P(value=1e-2, min=0.0, transform="softplus"))
    phase = add_body(phase, "chain", CHAIN_LABELS, ["C"] * 7, CHAIN, (0.3, 0.4, 0.25),
                     orientation=(0.9, 0.1, 0.2, 0.3),
                     torsions=[BodyTorsion(name=f"t{i}", axis=(a, b), moves=m)
                               for i, (a, b, m) in enumerate(torsions)])
    phase = add_body(phase, "triad", TRIAD_LABELS, ["O", "C", "O"], TRIAD,
                     (0.7, 0.2, 0.8))
    return phase.model_copy(update={"restraints": list(restraints)})


def _compile(phase: Phase):
    tt = np.arange(10.0, 40.0, 0.05)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    return compile_model(Structure(phases=[phase]), INS, blank, mode="rietveld")


def _index(label: str) -> int:
    return ["Li", *CHAIN_LABELS, *TRIAD_LABELS].index(label)


# ------------------------------------------------ the rule against the geometry
def _cartesian(phase: Phase, *, angles, orientation, origin, cell) -> np.ndarray:
    """The chain body's atoms (Å) with its torsions, pose and cell replaced."""
    body = phase.rigid_bodies[0]
    body = body.model_copy(update={
        "torsions": [t.model_copy(update={"angle": a})
                     for t, a in zip(body.torsions, angles, strict=True)],
        "orientation": orientation,
        "origin": body.origin.model_copy(update={
            c: Parameter(value=v) for c, v in zip("xyz", origin, strict=True)})})
    frac = body_fractional(body, cell)
    return frac @ np.asarray(cartesian_frame(cell), dtype=np.float64).T


def _quantity(x: np.ndarray, idx: tuple[int, ...]) -> float:
    if len(idx) == 2:
        return float(np.linalg.norm(x[idx[1]] - x[idx[0]]))
    if len(idx) == 3:
        u, v = x[idx[0]] - x[idx[1]], x[idx[2]] - x[idx[1]]
        return math.degrees(math.acos(u @ v / (np.linalg.norm(u) * np.linalg.norm(v))))
    a, b, c, d = (x[i] for i in idx)
    b1, b2, b3 = b - a, c - b, d - c
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    return math.degrees(math.atan2(np.linalg.norm(b2) * (b1 @ n2), n1 @ n2))


def _refused(phase: Phase, idx: tuple[int, ...]) -> bool:
    images = [(np.eye(3), np.zeros(3))] * len(idx)
    try:
        _refuse_fixed_body_geometry(phase, 0, "test", [i + 1 for i in idx], images)
    except RestraintRefused as err:
        assert err.diagnostic.code == CODE
        return True
    return False


def test_the_rule_refuses_exactly_what_the_body_holds_fixed():
    """Every bond, angle and torsion over the chain body's atoms: refused if and
    only if it stays put while every torsion twists and the pose and cell move.

    This is the positive control: with the rule removed nothing is refused, and
    each of the 45 fixed quantities fails the assertion (501 change)."""
    phase = _phase()
    rng = np.random.default_rng(1814)
    base = _cartesian(phase, angles=[0.0, 0.0, 0.0],
                      orientation=phase.rigid_bodies[0].orientation,
                      origin=phase.rigid_bodies[0].origin.values(), cell=CELL)
    q = rng.normal(size=4)
    q = q / np.linalg.norm(q) * (1 if q[0] >= 0 else -1)
    moved = _cartesian(phase, angles=rng.uniform(20.0, 70.0, size=3).tolist(),
                       orientation=tuple(q), origin=(0.11, 0.62, 0.43),
                       cell=(8.4, 9.0, 10.7, 88.0, 97.0, 99.0))
    counts = {"refused": 0, "accepted": 0}
    for n in (2, 3, 4):
        for idx in itertools.permutations(range(7), n):
            if n > 2 and idx[0] > idx[-1]:
                continue   # a reversed angle or torsion is the same quantity
            if n == 2 and idx[0] > idx[1]:
                continue
            delta = abs(_quantity(moved, idx) - _quantity(base, idx))
            if n == 4:
                delta = min(delta, 360.0 - delta)
            fixed = delta < 1e-9
            assert fixed or delta > 1e-3, (idx, delta)   # nothing in between
            assert _refused(phase, idx) == fixed, (idx, delta)
            counts["refused" if fixed else "accepted"] += 1
    # both arms are populated, or the check above certifies nothing
    assert counts == {"refused": 45, "accepted": 501}, counts


# ------------------------------------------------------- the seat: compile
@pytest.mark.parametrize("restraint, kind", [
    # K0 off every torsion's moved set but t2's axis; K1 an axis atom
    (BondRestraint(atom_i=_index("K0"), atom_j=_index("K1"), target=1.5, sigma=0.01),
     "bond"),
    # both moved by t0, neither by t1 (K3 is t1's axis) nor t2
    (BondRestraint(atom_i=_index("K3"), atom_j=_index("K4"), target=1.5, sigma=0.01),
     "bond"),
    (AngleRestraint(atom_i=_index("K0"), atom_j=_index("K1"), atom_k=_index("K2"),
                    target_deg=110.0, sigma=1.0), "angle"),
    (TorsionRestraint(atoms=[_index("K6"), _index("K0"), _index("K1"), _index("K2")],
                      target_deg=0.0, sigma=5.0), "torsion"),
    (PlanarityRestraint(atoms=[_index(k) for k in ("K0", "K1", "K2", "K6")],
                        sigma=0.02), "planarity"),
    # a body with no torsion
    (BondRestraint(atom_i=_index("T0"), atom_j=_index("T1"), target=1.2, sigma=0.01),
     "bond"),
])
def test_a_restraint_on_fixed_body_geometry_is_refused_at_compile(restraint, kind):
    with pytest.raises(RestraintRefused, match=CODE) as err:
        _compile(_phase([restraint]))
    d = err.value.diagnostic
    assert d.code == CODE and d.level == "error"
    assert f"The {kind} restraint 0 of phase 'p'" in d.message
    assert d.where and all(w.startswith("p ") for w in d.where)
    assert isinstance(err.value, ValueError)


def test_one_shared_non_identity_image_is_still_one_copy():
    """Every entry at the inversion image: the same copy turned over, refused;
    one entry moved to another image is a contact between two copies, accepted."""
    phase = _phase()
    ops_r, _ = compile_phase_sites(phase).ops[_index("K0")]
    inv = next(k for k, r in enumerate(ops_r) if np.allclose(r, -np.eye(3)))
    chain = [_index(k) for k in ("K6", "K0", "K1", "K2")]
    same = TorsionRestraint(atoms=chain, target_deg=0.0, sigma=5.0,
                            op_indices=[inv] * 4, translations=[(1, 0, 0)] * 4)
    with pytest.raises(RestraintRefused, match=CODE):
        _compile(_phase([same]))
    split = TorsionRestraint(atoms=chain, target_deg=0.0, sigma=5.0,
                             op_indices=[inv] * 3 + [0], translations=[(1, 0, 0)] * 4)
    _compile(_phase([split]))


@pytest.mark.parametrize("restraint", [
    # t0 turns K3 and not K0
    BondRestraint(atom_i=_index("K0"), atom_j=_index("K3"), target=3.0, sigma=0.01),
    AngleRestraint(atom_i=_index("K0"), atom_j=_index("K1"), atom_k=_index("K3"),
                   target_deg=100.0, sigma=1.0),
    TorsionRestraint(atoms=[_index(k) for k in ("K0", "K1", "K2", "K3")],
                     target_deg=0.0, sigma=5.0),
    PlanarityRestraint(atoms=[_index(k) for k in ("K0", "K1", "K2", "K3")], sigma=0.02),
    # a free atom, and two bodies
    BondRestraint(atom_i=_index("Li"), atom_j=_index("K0"), target=3.0, sigma=0.1),
    BondRestraint(atom_i=_index("K0"), atom_j=_index("T0"), target=3.0, sigma=0.1),
    # two copies of the body: the second atom a cell along a
    BondRestraint(atom_i=_index("K0"), atom_j=_index("K1"), target=8.0, sigma=0.1,
                  op_index=0, translation=(1, 0, 0)),
    # one-sided rows are not checked
    TetherRestraint(atom_i=_index("K0"), atom_j=_index("K1"), max_distance=2.0, sigma=0.1),
], ids=["bond", "angle", "torsion", "planarity", "free-atom", "two-bodies",
        "two-copies", "tether"])
def test_a_restraint_something_can_move_is_accepted(restraint):
    model = _compile(_phase([restraint]))
    assert model.restraints is not None and model.restraints.n_rows >= 1


def test_the_declaration_decides_not_vary():
    """A held torsion still lets its restraint through: the rule reads what the
    body declares, so a stage that holds the twist keeps a constant row, as it
    keeps any row of a held parameter.  Without the torsion the same restraint
    is refused."""
    bond = BondRestraint(atom_i=_index("K0"), atom_j=_index("K3"), target=3.0, sigma=0.01)
    phase = _phase([bond])
    assert not any(t.vary for t in phase.rigid_bodies[0].torsions)
    _compile(phase)
    with pytest.raises(RestraintRefused, match=CODE):
        _compile(_phase([bond], torsions=CHAIN_TORSIONS[1:]))


def test_a_fit_stops_before_the_first_stage_and_says_why():
    bond = BondRestraint(atom_i=_index("K0"), atom_j=_index("K1"), target=1.5, sigma=0.01)
    tt = np.arange(10.0, 40.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(), intensity=(100.0 + 0.0 * tt).tolist())
    ref = Refinement(Structure(phases=[_phase([bond])]), INS, history=False)
    with pytest.raises(RestraintRefused, match=CODE) as err:
        ref.fit(pattern)
    assert "Drop the restraint" in str(err.value)
