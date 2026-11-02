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

import rietx as rx
from rietx.crystallography.magnetic import isotropy as I
from rietx.crystallography.magnetic.operators import parse_transform
from rietx.crystallography.representation import distortion as D
from rietx.crystallography.symmetry import get_spacegroup, resolve_group
from rietx.crystallography.wyckoff import (
    coordinate_basis,
    floating_origin_basis,
    stabilizer_rotations,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.structure import Structure
from tests.test_displacive_statement import (
    natao3_parent,
    neutron,
)
from tests.test_distortion_candidates import K_GAMMA, K_R
from tests.test_distortion_candidates import _perovskite as perovskite

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
