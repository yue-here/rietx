"""A displacive statement from a candidate, with the derived cell (WP-1419 C3b).

``displacive_statement(parent, candidate=…)`` states a
``distortion_candidates`` entry as its parent plus absolute mode amplitudes,
seeded in the driving irrep, and every displacive statement now carries
``Phase.parent_cell``: the parent's cell plus the Γ strains the child's group
allows, held.  What is pinned, and against what:

* **Howard & Stokes's six perovskite children** (Howard & Stokes 1998, *Acta
  Cryst.* B54, 782; #996's test set): R4+ (a,0,0) I4/mcm, (a,a,a) R-3c,
  (a,a,0) Imma, Γ4− (a,0,0) P4mm, (a,a,a) R3m, (a,a,0) Amm2.  Each seed's
  stabiliser in the parent group is the candidate's group, and the block
  reaches every free coordinate of the child (a span test both ways).
* **NaTaO₃ P4/mbm at 843 K** through the candidate route (Kennedy,
  Prodjosantoso & Howard 1999, *J. Phys.: Condens. Matter* 11, 6319,
  doi:10.1088/0953-8984/11/33/302, Table 1: a = 5.5503, c = 3.9335 Å, O2 at
  (¼+u, ¾+u, 0), u = 0.0241, Wyckoff 4g): the amplitude and the tetragonal
  strain both come back from the parent.
* **The five Pnma children C2 unblocked** (``test_parent_cell.REFUSED_FIVE``):
  each builds with modes, and with every amplitude zero draws |det P|² times
  the parent's pattern.
* **Strains at the parent**: zero is stationary for every strain, and the
  pattern is even only in a strain a parent operation flips; the all-zero
  refusal covers a freed strain-only block, and a held strain narrows it.
* **Row D over candidates**: every stated candidate's statement passes its
  per-mode check.

The patterns are rietx's own with Poisson noise: the question is whether the
statement recovers a planted structure, not whether the forward model is right.
"""

from __future__ import annotations

import dataclasses
import functools
import math
from fractions import Fraction

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.crystallography import metric
from rietx.crystallography.magnetic import isotropy as I
from rietx.crystallography.magnetic.operators import parse_transform
from rietx.crystallography.representation import distortion as D
from rietx.crystallography.symmetry import cell_constraints, get_spacegroup, resolve_group
from rietx.crystallography.wyckoff import (
    coordinate_basis,
    floating_origin_basis,
    stabilizer_rotations,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.structure import Structure
from tests.test_displacive_statement import (
    NATAO3_A_TAU,
    NATAO3_T,
    natao3_child,
    natao3_parent,
    neutron,
    simulate,
)
from tests.test_distortion_candidates import K_GAMMA, K_R
from tests.test_distortion_candidates import _perovskite as perovskite
from tests.test_parent_cell import REFUSED_FIVE, _lamno3
from tests.test_parent_cell import _child as supercell_child

pytestmark = pytest.mark.xdist_group("displacive-candidate")  # module fixtures built once

P_ = rx.Parameter
K_M = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
AMPS = "phases.0.distortion_modes.modes.*.amplitude"
STRAINS = "phases.0.parent_cell.strain.*"
TT = np.arange(10.0, 120.0, 0.02)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

@functools.cache
def _candidates(name):
    """The perovskite candidates #996 pins, built once per process."""
    if name == "r":
        return perovskite(3.9), I.distortion_candidates(perovskite(3.9), K_R, sites=["O"])
    if name == "gamma":
        return perovskite(3.9), I.distortion_candidates(perovskite(3.9), K_GAMMA, sites="Mn")
    if name == "m":
        return perovskite(3.9), I.distortion_candidates(perovskite(3.9), K_M)
    if name == "natao3":
        return natao3_parent(), I.distortion_candidates(natao3_parent(), K_M)
    raise KeyError(name)


#: (candidate set, irrep, Howard & Stokes's child, its IT number)
HOWARD_STOKES = (("r", "S10", "I4/mcm", 140), ("r", "S10", "R-3c", 167),
                 ("r", "S10", "Imma", 74), ("gamma", "S9", "P4mm", 99),
                 ("gamma", "S9", "R3m", 160), ("gamma", "S9", "Amm2", 38))


def _howard_stokes(name, irrep, number):
    parent, cands = _candidates(name)
    (hit,) = [c for c in cands if c.irrep == irrep and "rank 1" in c.direction
              and get_spacegroup(c.child_group).number == number]
    return parent, hit


def _fields(parent, statement, driving):
    """The statement's mode fields over the child cell, in its record's order.

    Rebuilt from the basis the way the statement orders them (the candidate's
    driving irrep first, then the primary irreps), independently of its own
    seed check, with the parent group's actions on the child cell.
    """
    basis = statement.basis
    big, small = basis.transform
    ref = D._reference(parent, big, small)
    labels = [a.label for a in parent.atoms]
    lead = next(i for i, c in enumerate(basis.components) if c is driving)
    order = sorted(range(len(basis.components)),
                   key=lambda i: (i != lead, basis.components[i].primary is not True))
    fields = np.array([v for i in order for _, v in D._site_modes(
        basis.components[i], ref, labels, D._whitener(basis))])
    assert len(fields) == len(statement.phase.distortion_modes.modes)
    return fields, D._parent_actions(parent, ref, big, small)


def _reaches_every_free_coordinate(phase, drop: int | None = None) -> bool:
    """Do the modes, with the floating origin, span exactly the child's free coordinates?

    Both ways, never a count: the mode vectors on the listed atoms (child
    fractions), plus one uniform shift per floating direction of the group,
    span the same space as every atom's site-symmetry coordinate basis.
    ``drop`` leaves one mode out, the positive arm.
    """
    group = resolve_group(phase.space_group, phase.symmetry_operations)
    record = phase.distortion_modes
    n = len(phase.atoms)
    modes = [np.asarray(m.vectors, dtype=float).reshape(-1)
             for i, m in enumerate(record.modes) if i != drop]
    sites = []
    for j, base in enumerate(record.base):
        for v in coordinate_basis(stabilizer_rotations(group, np.asarray(base, dtype=float))):
            col = np.zeros(3 * n)
            col[3 * j:3 * j + 3] = np.asarray(v, dtype=float)
            sites.append(col)
    origin = [np.tile(np.asarray(f, dtype=float), n) for f in floating_origin_basis(group)]

    def rank(cols) -> int:
        return int(np.linalg.matrix_rank(np.array(cols).T, tol=1e-9)) if cols else 0

    reached = modes + origin
    return (rank(modes) == len(modes)
            and rank(reached) == rank(sites) == rank(reached + sites))


def _floats(transform: str):
    big, small = parse_transform(transform)
    return (np.array([[float(v) for v in row] for row in big]),
            np.array([float(v) for v in small]))


def _predict(phase, instrument=None) -> np.ndarray:
    ref = rx.Refinement(Structure(phases=[phase]), instrument or neutron(), history=False)
    return np.asarray(ref.predict(TT))


# --------------------------------------------------------------------------
# B1: the candidate route
# --------------------------------------------------------------------------

@pytest.mark.parametrize("case", HOWARD_STOKES, ids=[c[2] for c in HOWARD_STOKES])
def test_each_howard_stokes_child_states_from_its_candidate(case):
    """The seed's stabiliser is the candidate's group, and the block is complete.

    The seed lies in the driving irrep alone (its isotropy group is the child's
    by definition), so the secondary modes Imma and Amm2 carry start at zero;
    every mode of the record is keyed to the candidate's basis, the driving
    irrep first.  The cell is the parent's, every strain zero and held, and the
    site map is the basis's ``parent_atoms``.
    """
    name, irrep, _, number = case
    parent, cand = _howard_stokes(name, irrep, number)
    statement = D.displacive_statement(parent, candidate=cand)
    phase = statement.phase
    record = phase.distortion_modes
    n_driving = cand.driving.n_modes
    assert all(m.irrep == irrep for m in record.modes[:n_driving])
    assert all(m.irrep != irrep for m in record.modes[n_driving:])
    assert set(statement.seed) == {f"phases.0.distortion_modes.modes.{i}.amplitude"
                                   for i in range(n_driving)}
    amps = [m.amplitude.value for m in record.modes]
    assert math.hypot(*amps[:n_driving]) == pytest.approx(D.DISTORTION_SEED, rel=1e-12)
    assert amps[0] > 0.0 and amps[n_driving:] == [0.0] * (len(amps) - n_driving)

    fields, actions = _fields(parent, statement, cand.driving)
    n_h = len(D._operations(D._group(cand.child))[0])
    assert D._stabiliser_order(np.tensordot(amps, fields, axes=1), actions) == n_h

    assert _reaches_every_free_coordinate(phase)
    assert not _reaches_every_free_coordinate(phase, drop=len(record.modes) - 1)

    pc = phase.parent_cell
    assert pc is not None and pc.space_group == parent.space_group
    assert pc.transform == record.transform
    assert all(s.value == 0.0 and not s.vary for s in pc.strain)
    assert statement.biso_ties == D.parent_site_ties(statement.site_map)
    assert set(statement.site_map) <= {int(i) for i in cand.basis.parent_atoms}
    for atom, s in zip(phase.atoms, statement.site_map, strict=True):
        assert atom.species == parent.atoms[s].species
    ParameterTable(Structure(phases=[phase]), neutron())


def test_a_seed_along_one_mode_of_a_rank_two_direction_keeps_more_than_the_child():
    """The stabiliser check's positive arm on the candidate route.

    At M the (a,b) direction of the O site's polar irrep has a P 1 2/m 1 child
    and six driving modes; a field along any one of them sits on a
    higher-symmetry sub-direction for at least one of them, so the comparison
    with the child's order can fail, and the generic seed is what passes it.
    """
    parent, cands = _candidates("m")
    (cand,) = [c for c in cands if c.label == "S9(a,b)"]
    statement = D.displacive_statement(parent, candidate=cand)
    fields, actions = _fields(parent, statement, cand.driving)
    n_h = len(D._operations(D._group(cand.child))[0])
    singles = [D._stabiliser_order(f, actions) for f in fields[:cand.driving.n_modes]]
    assert max(singles) > n_h
    seed = [m.amplitude.value for m in statement.phase.distortion_modes.modes]
    assert D._stabiliser_order(np.tensordot(seed, fields, axes=1), actions) == n_h


def test_a_refused_or_unverified_candidate_is_refused_by_name():
    """A candidate with no child, or one that failed verification, states nothing.

    Positive arm: the same candidate, unmodified, states.  The two spellings
    cannot be mixed, a candidate's basis is the ``"average"`` reference's, and
    a candidate built from another parent is refused.
    """
    parent, cand = _howard_stokes("r", "S10", 140)
    D.displacive_statement(parent, candidate=cand)
    refused = dataclasses.replace(cand, child=None, transform=None, basis=None,
                                  refusal=I.DistortionRefusal(
                                      code="DISTORTION_CHILD_LARGER",
                                      message="DISTORTION_CHILD_LARGER: the draws", draws=(8,),
                                      operations=4))
    with pytest.raises(ValueError, match="has no child to state: DISTORTION_CHILD_LARGER"):
        D.displacive_statement(parent, candidate=refused)
    unverified = dataclasses.replace(cand, candidate=dataclasses.replace(
        cand.candidate, verified=False, verification_reason="outside the allowed span"))
    with pytest.raises(ValueError, match=r"failed verification \(outside the allowed span\)"):
        D.displacive_statement(parent, candidate=unverified)
    with pytest.raises(ValueError, match="not both"):
        D.displacive_statement(parent, cand.child, cand.transform, candidate=cand)
    with pytest.raises(ValueError, match="needs child and transform"):
        D.displacive_statement(parent)
    with pytest.raises(ValueError, match="'average' reference"):
        D.displacive_statement(parent, candidate=cand, reference="parent")
    other = parent.model_copy(update={"atoms": [
        a.model_copy(update={"species": "Ti" if a.species == "Mn" else a.species})
        for a in parent.atoms]})
    with pytest.raises(ValueError, match="was not built from this parent"):
        D.displacive_statement(other, candidate=cand)


# --------------------------------------------------------------------------
# B2: the derived cell on every statement
# --------------------------------------------------------------------------

def test_a_stated_child_keeps_its_own_cell_as_the_parents_plus_held_strain():
    """Kennedy's tetragonal cell: the cubic parent's edge plus one held strain.

    The parent's cell is the parent-symmetric part of the child's metric and
    the strain the rest, so the stated cell comes back to round-off.  Positive
    arm: a child cell its group forbids (a ≠ b under P4/mbm) is not a parent
    metric plus an allowed strain, and is refused.
    """
    statement = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T)
    phase = statement.phase
    want = natao3_child(0.0).cell.lengths_angles()
    assert phase.cell.lengths_angles() == pytest.approx(want, abs=1e-12)
    pc = phase.parent_cell
    assert pc.cell.a.value == pc.cell.b.value == pc.cell.c.value
    a_avg = math.sqrt((2 * (5.5503 / math.sqrt(2)) ** 2 + 3.9335 ** 2) / 3)
    assert pc.cell.a.value == pytest.approx(a_avg, rel=1e-14)
    (strain,) = pc.strain
    assert strain.value < 0.0 and not strain.vary  # c longer: E = diag(1, 1, -2)/√6
    table = ParameterTable(Structure(phases=[phase]), neutron())
    assert table.derived_paths() == {f"phases.0.cell.{n}" for n in
                                     ("a", "b", "c", "alpha", "beta", "gamma")}

    skewed = natao3_child(0.0).model_copy(update={"cell": rx.Cell(
        a=P_(value=5.5503), b=P_(value=5.56), c=P_(value=3.9335), alpha=P_(value=90.0),
        beta=P_(value=90.0), gamma=P_(value=90.0))})
    with pytest.raises(ValueError, match="does not have the symmetry its group states"):
        D.displacive_statement(natao3_parent(), skewed, NATAO3_T)


def test_a_parent_stated_by_its_operations_leaves_the_child_its_own_cell():
    """``ParentCell`` names its parent by symbol, so an operator-list parent has none."""
    import gemmi

    parent = natao3_parent()
    ops = [op.triplet() for op in gemmi.SpaceGroup("P m -3 m").operations()]
    listed = parent.model_copy(update={"symmetry_operations": ops})
    statement = D.displacive_statement(listed, natao3_child(0.0), NATAO3_T)
    assert statement.phase.parent_cell is None
    assert statement.phase.cell == natao3_child(0.0).cell
    assert D.displacive_statement(parent, natao3_child(0.0), NATAO3_T).phase.parent_cell


def test_the_two_records_name_one_parent_and_one_transform():
    """``distortion_modes`` and ``parent_cell`` agree, or the phase is refused by name.

    By the ``Phase`` validator, and by the table for a copy that skipped it.
    Positive arm: another spelling of the parent's symbol and an origin one
    parent lattice vector away are the same statement, and are accepted.
    """
    phase = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T).phase
    data = phase.model_dump()
    pc = data["parent_cell"]
    assert pc["transform"] == data["distortion_modes"]["transform"] == "a-b,a+b,c;0,0,0"
    with pytest.raises(ValidationError, match=r"different \(P, p\)"):
        rx.Phase.model_validate({**data, "parent_cell": {**pc, "transform": "a,b,c;0,0,0"}})
    with pytest.raises(ValidationError, match="name different parents"):
        rx.Phase.model_validate({**data, "parent_cell": {**pc, "space_group": "P 4/m m m"}})
    rx.Phase.model_validate({**data, "parent_cell": {
        **pc, "space_group": "Pm-3m", "transform": "a-b,a+b,c;1,0,-1"}})

    copied = phase.model_copy(update={"parent_cell": phase.parent_cell.model_copy(
        update={"transform": "a,b,2c;0,0,0"})})
    with pytest.raises(ValueError, match=r"phases\.0: .*different \(P, p\)"):
        ParameterTable(Structure.model_construct(phases=[copied]), neutron())


@functools.cache
def _natao3_route():
    """The P4/mbm candidate that carries Kennedy's distortion, and the planted values.

    Two candidates at M have the group P4/mbm (the octahedral tilt and the
    in-plane O shift both do), so the group alone does not name it: the one
    taken is the candidate whose irrep carries the published structure's
    decomposition.  The planted strain is the statement of Kennedy's own cell.
    """
    parent, cands = _candidates("natao3")
    tetragonal = [c for c in cands if c.refusal is None
                  and get_spacegroup(c.child_group).number == 127]
    (row,) = [r for r in D.mode_amplitudes(parent, natao3_child(), NATAO3_T).rows
              if r.amplitude > 0.0]
    (cand,) = [c for c in tetragonal if c.irrep == row.irrep]
    kennedy = D.displacive_statement(parent, natao3_child(), NATAO3_T).phase.parent_cell
    return parent, cand, len(tetragonal), kennedy.strain[0].value


@functools.cache
def _natao3_fits():
    parent, cand, _, _ = _natao3_route()
    data = simulate(natao3_child(), seed=7)
    plan = rx.RefinementPlan.mccusker_structural()
    plan = dataclasses.replace(plan, stages=[
        dataclasses.replace(s, turn_on=[*s.turn_on, STRAINS]) if s.name == "cell" else s
        for s in plan.stages])
    out = {}
    for start in (0.0, 1e-3, -1e-3):
        statement = D.displacive_statement(parent, candidate=cand)
        ref = rx.Refinement(Structure(phases=[statement.phase]), neutron(), history=False)
        if start:
            ref.set_values({"phases.0.parent_cell.strain.0": start})
        result = ref.fit(data, plan=plan, telemetry=False)
        out[start] = (statement, ref, result)
    return out


def test_natao3_through_its_candidate_returns_the_amplitude_and_the_strain():
    """The M-point candidate, seeded by the statement, with its tetragonal strain freed.

    Measured 2026-11-02 (macOS arm64): |A| = 0.378713(1447) Å for the
    planted 0.378621, s = −0.0018404(90) for the planted −0.0018395
    (−0.10 esd), c/a_p − 1 = 0.002255 for Kennedy's 0.002254, Rwp equal to 12
    digits from the strain freed at exactly zero beside the seeded amplitude
    and from either sign of a 1e-3 seed.  The strain's sign is not a domain
    here (no parent operation maps a tetragonal strain to its negative), so it
    is compared signed: from +1e-3 it crosses to the planted negative value.
    """
    _, _, n_tetragonal, planted = _natao3_route()
    assert n_tetragonal == 2
    fits = _natao3_fits()
    _, ref0, result0 = fits[0.0]
    for _start, (statement, ref, result) in fits.items():
        assert statement.seed == {"phases.0.distortion_modes.modes.0.amplitude":
                                  D.DISTORTION_SEED}
        assert result.status == "converged"
        rows = {p.path: p for p in result.parameters}
        amp = rows["phases.0.distortion_modes.modes.0.amplitude"]
        strain = rows["phases.0.parent_cell.strain.0"]
        assert abs(abs(amp.value) - NATAO3_A_TAU) < min(amp.stderr, 0.01)
        assert abs(strain.value - planted) < 2.0 * strain.stderr
        assert result.statistics.rwp == pytest.approx(result0.statistics.rwp, rel=1e-8)
        a, _, c, *_ = ref.structure.phases[0].cell.lengths_angles()
        assert c / (a / math.sqrt(2.0)) - 1.0 == pytest.approx(
            3.9335 / (5.5503 / math.sqrt(2.0)) - 1.0, abs=1e-4)


@pytest.mark.parametrize("case,label,n_strain", REFUSED_FIVE,
                         ids=[f"{c[0]}{c[1]}{c[2]}".replace(" ", "") for c, _, _ in REFUSED_FIVE])
def test_the_five_pnma_children_build_with_modes(case, label, n_strain):
    """Each statement builds, predicts, and at A = 0 is |det P|² × the parent.

    The children ``magnetic_supercell`` states through the parent's cell (a
    C-centred type in a primitive doubled cell), now refined on their modes:
    the parent is the shipped Pnma LaMnO₃ itself, so seven of the modes are
    its own free coordinates (identity irrep) and the rest break its symmetry.
    """
    parent = _lamno3()
    supercell = supercell_child(*case)
    transform = _floats(supercell.transform)
    statement = D.displacive_statement(parent, supercell.phase, transform)
    phase = statement.phase
    assert phase.space_group == label
    assert len(phase.parent_cell.strain) == n_strain
    assert all(s.value == 0.0 for s in phase.parent_cell.strain)
    assert sum(m.parent_invariant for m in phase.distortion_modes.modes) == 7
    assert statement.seed and _reaches_every_free_coordinate(phase)
    ParameterTable(Structure(phases=[phase]), neutron())
    assert np.isfinite(_predict(phase)).all()

    at_zero = D.displacive_statement(parent, supercell.phase, transform, seed=0.0).phase
    biso = [parent.atoms[s].biso.value for s in statement.site_map]
    # at the parent's own scale (``magnetic_supercell`` divides it by |det P|²)
    at_zero = at_zero.model_copy(update={"scale": parent.scale, "atoms": [
        a.model_copy(update={"biso": P_(value=b)})
        for a, b in zip(at_zero.atoms, biso, strict=True)]})
    y_child, y_parent = _predict(at_zero), _predict(parent)
    det = round(abs(np.linalg.det(transform[0])))
    assert np.max(np.abs(y_child - det ** 2 * y_parent)) <= 1e-10 * np.max(y_child)


# --------------------------------------------------------------------------
# strains at the parent
# --------------------------------------------------------------------------

def _strain_flipped(parent, phase) -> list[bool]:
    """Per strain, whether some parent rotation maps it to its negative (Rᵀ·E·R = −E)."""
    sg = get_spacegroup(parent.space_group)
    big, _ = parse_transform(phase.parent_cell.transform)
    basis = metric.strain_basis(
        metric.rotations_of(sg), metric.in_parent_basis(big, metric.rotations_of(D._group(phase))),
        cell_constraints(sg).fixed_angles)
    return [any(np.allclose(r.T @ e @ r, -e) for r in metric.rotations_of(sg)) for e in basis]


def _y(phase, strain: float) -> np.ndarray:
    ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]), neutron(), history=False)
    ref.set_values({"phases.0.parent_cell.strain.0": strain})
    return np.asarray(ref.predict(TT))


def test_zero_strain_is_stationary_and_even_only_where_an_operation_flips_it():
    """y(+s) = y(−s) at A = 0 for the Cm child's shear; a tetragonal strain is only stationary.

    The shear of C2's Cm child (2a, a+b, c) of Pnma LaMnO₃ is mapped to its
    negative by a parent rotation, so ±s are orientation domains: measured
    2026-11-02, 1.5e-14 to 2.9e-14 of the top at |s| = 1e-3 to 4e-3.  The
    positive arm is NaTaO₃'s tetragonal strain of its cubic parent, which no
    parent rotation flips: the pattern is not even (1.3e-2 of the top at
    1e-3), but its odd part falls as s³ (×7.2 from 1e-3 to 5e-4), so the
    gradient at zero vanishes all the same, which is the all-zero refusal's
    ground for strains.
    """
    supercell = supercell_child((0.5, 0.5, 0), "S1", "(rank 2)#3")
    shear = D.displacive_statement(_lamno3(), supercell.phase, _floats(supercell.transform),
                                   seed=0.0).phase
    assert _strain_flipped(_lamno3(), shear) == [True]
    y0 = _y(shear, 0.0)
    for s in (1e-3, 4e-3):
        assert np.max(np.abs(_y(shear, s) - _y(shear, -s))) <= 1e-12 * y0.max()
        assert np.max(np.abs(_y(shear, s) - y0)) > 1e-2 * y0.max()

    parent, cand, _, _ = _natao3_route()
    tetragonal = D.displacive_statement(parent, candidate=cand, seed=0.0).phase
    assert _strain_flipped(parent, tetragonal) == [False]
    y0 = _y(tetragonal, 0.0)

    def odd(s: float) -> float:
        return float(np.max(np.abs(_y(tetragonal, s) - _y(tetragonal, -s))) / y0.max())

    assert odd(1e-3) > 1e-3
    assert odd(1e-3) / odd(5e-4) > 6.0  # s³; a first-order term would halve it


def _free(phase, globs, values=None):
    ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]), neutron(), history=False)
    if values:
        ref.set_values(values)
    return ParameterTable(ref.structure, neutron()).set_vary(globs, True)


def test_the_all_zero_refusal_covers_the_strains_and_a_held_strain_narrows_it():
    """A stage freeing the block at the parent is refused; off it, it runs.

    At A = 0 and every strain zero, a freed strain alone or a freed amplitude
    alone is refused.  Positive arms: the strain set off zero, or the
    statement's own seed on the amplitude, lets the strain free.  With a held
    non-zero strain (Kennedy's cell stated at its parent positions), an
    M-point amplitude is still refused (a lost parent translation flips it,
    whatever the metric) and the strain itself frees; a Γ amplitude beside a
    held strain is let through (the strain can couple to a Γ mode of its own
    irrep), and refused once the strain is zero.
    """
    parent, cand, _, _ = _natao3_route()
    at_zero = D.displacive_statement(parent, candidate=cand, seed=0.0).phase
    with pytest.raises(ValueError, match="and every strain is exactly zero"):
        _free(at_zero, [STRAINS])
    with pytest.raises(ValueError, match="and every strain is exactly zero"):
        _free(at_zero, [AMPS])
    assert _free(at_zero, [STRAINS], {"phases.0.parent_cell.strain.0": 1e-3}) == [
        "phases.0.parent_cell.strain.0"]
    seeded = D.displacive_statement(parent, candidate=cand).phase
    assert _free(seeded, [STRAINS]) == ["phases.0.parent_cell.strain.0"]

    strained = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T,
                                      seed=0.0).phase
    assert strained.parent_cell.strain[0].value != 0.0
    with pytest.raises(ValueError, match=r"the freed ones at k ≠ Γ"):
        _free(strained, [AMPS])
    assert _free(strained, [STRAINS]) == ["phases.0.parent_cell.strain.0"]

    gamma_parent, polar = _howard_stokes("gamma", "S9", 99)
    p4mm = D.displacive_statement(gamma_parent, candidate=polar, seed=0.0).phase
    with pytest.raises(ValueError, match="exactly zero"):
        _free(p4mm, [AMPS])
    assert len(_free(p4mm, [AMPS], {"phases.0.parent_cell.strain.0": 1e-3})) == 3
