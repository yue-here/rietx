"""The displacive candidates of a parent with their mode bases in Å (WP-1419).

:func:`~rietx.crystallography.magnetic.isotropy.distortion_candidates` wraps
``candidates(kind="displacive")`` and hands each child to
:func:`~rietx.crystallography.representation.distortion.distortion_basis`.
What is pinned, and against what:

* **The children.**  Howard & Stokes (1998), *Acta Cryst.* B54, 782: a cubic
  perovskite's R4+ tilt (a,0,0) → I4/mcm, (a,a,0) → Imma, (a,a,a) → R-3c, and
  Γ4− (a,0,0) → P4mm.  B cation at the origin, so the tilt is R4+ (Campbell
  et al. 2006 § 4.7); this package labels it S10 at R and Γ4− S9 at Γ.
* **(P, p).**  The child's own operations are symmetries of the parent's
  atoms displaced along its modes, in the child cell; an origin moved by half
  a parent cell is refused by C1's subgroup check (the positive arm).
* **Driving and rest.**  Σ n_modes is the child's free coordinates,
  counted from its Wyckoff positions, and a generic displacement allowed by
  the child's symmetry is reached completely (residual 1e-10), which a basis
  of the driving irrep alone does not do.
* **The unit and the LaMnO₃ match.**  The I4/mcm tilt's mode moves each O
  of the half cell by ½ Å per Å of amplitude (four movers per primitive cell),
  and the Imma candidate's R4+ mode, carried onto the shipped Pnma fixture,
  measures exactly the R4+ amplitude :func:`mode_amplitudes` gives there.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import gemmi
import numpy as np
import pytest
import spglib

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.magnetic import isotropy as I
from rietx.crystallography.representation import distortion as D
from rietx.crystallography.symmetry import resolve_group, site_orbit
from rietx.crystallography.wyckoff import (
    coordinate_basis,
    floating_origin_basis,
    stabilizer_rotations,
)

pytestmark = pytest.mark.xdist_group("distortion-candidates")  # module fixtures built once

DATA = Path(__file__).parent / "data"
P_ = rx.Parameter
K_R = (Fraction(1, 2),) * 3
K_GAMMA = (Fraction(0),) * 3
LAMNO3_P = [[1, 0, -1], [0, 2, 0], [1, 0, 1]]
LAMNO3_ORIGIN = [0.5, 0.0, 0.5]


def _atom(label, species, x, y, z):
    return rx.Atom(label=label, species=species, x=P_(value=x), y=P_(value=y), z=P_(value=z))


def _perovskite(a):
    return rx.Phase(name="cubic", space_group="P m -3 m", cell=rx.Cell.cubic(a), atoms=[
        _atom("Mn", "Mn", 0, 0, 0), _atom("La", "La", 0.5, 0.5, 0.5),
        _atom("O", "O", 0.5, 0, 0)])


@pytest.fixture(scope="module")
def lamno3():
    """The Pnma fixture decomposed by C1, and the cubic edge of its reference metric."""
    child = structure_from_cif(DATA / "gsas2_bt1_lamno3.cif").phases[0]
    dec = D.mode_amplitudes(_perovskite(3.9), child, (LAMNO3_P, LAMNO3_ORIGIN))
    big = np.array(LAMNO3_P, dtype=float)
    inv = np.linalg.inv(big)
    g_parent = inv.T @ dec.basis.metric @ inv
    return dec, float(np.sqrt(g_parent[0, 0]))


@pytest.fixture(scope="module")
def at_r(lamno3):
    """Every R-point candidate the O site carries, at LaMnO₃'s reference scale."""
    _, a = lamno3
    parent = _perovskite(a)
    return parent, I.distortion_candidates(parent, K_R, sites=["O"])


@pytest.fixture(scope="module")
def at_gamma():
    parent = _perovskite(3.9)
    return parent, I.distortion_candidates(parent, K_GAMMA, sites="Mn")


def _number(candidate) -> int:
    return gemmi.find_spacegroup_by_name(candidate.child_group).number


def _one(cands, irrep, number):
    hits = [c for c in cands if c.irrep == irrep and _number(c) == number]
    assert len(hits) == 1, [(c.label, c.child_group) for c in cands]
    return hits[0]


def _free_coordinates(phase) -> int:
    group = resolve_group(phase.space_group, phase.symmetry_operations)
    n = sum(len(coordinate_basis(stabilizer_rotations(
        group, np.array([a.x.value, a.y.value, a.z.value])))) for a in phase.atoms)
    return n - len(floating_origin_basis(group))


def _displaced(child, rng, scale=0.01):
    """The child with every atom moved generically inside its own site symmetry."""
    group = resolve_group(child.space_group, child.symmetry_operations)
    atoms = []
    for atom in child.atoms:
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        for vector in coordinate_basis(stabilizer_rotations(group, xyz)):
            xyz = xyz + scale * rng.standard_normal() * np.asarray(vector, float)
        atoms.append(atom.model_copy(update={
            "x": P_(value=float(xyz[0])), "y": P_(value=float(xyz[1])),
            "z": P_(value=float(xyz[2]))}))
    return child.model_copy(update={"atoms": atoms})


# --------------------------------------------------------------------------
# the children
# --------------------------------------------------------------------------

def test_the_perovskite_children_are_howard_and_stokes(at_r, at_gamma):
    """R4+ (S10): I4/mcm, R-3c, Imma; Γ4− (S9): P4mm, R3m, Amm2 (Howard & Stokes 1998)."""
    _, r = at_r
    _, g = at_gamma
    tilt = {_number(c) for c in r if c.irrep == "S10" and "rank 1" in c.direction}
    assert tilt == {140, 167, 74}
    polar = {_number(c) for c in g if c.irrep == "S9" and "rank 1" in c.direction}
    assert polar == {99, 160, 38}
    for c in (*r, *g):
        assert c.driving.isotropy_group.endswith(f"({_number(c)})"), c.label
        assert c.basis.child_group == c.child_group
        assert c.candidate.kind == "displacive"


def test_each_basis_is_complete(at_r, at_gamma):
    """Σ n_modes equals the child's free coordinates, from its Wyckoff positions."""
    for _, cands in (at_r, at_gamma):
        for c in cands:
            assert c.basis.n_modes == _free_coordinates(c.child), c.label
            big, _ = c.transform
            assert len(c.basis.positions) == round(5 * abs(np.linalg.det(big))), c.label
            assert sum(len(site_orbit(resolve_group(c.child_group, None), np.array(
                [a.x.value, a.y.value, a.z.value])).images) for a in c.child.atoms) == len(
                c.basis.positions), c.label


def test_the_rest_of_the_irreps_are_returned(at_r):
    """R4+ (a,a,0) → Imma carries R5+ (S8, two modes) as one of its `rest`, per Table 13."""
    _, r = at_r
    imma = _one(r, "S10", 74)
    assert imma.driving.irrep == "S10" and imma.driving.n_modes == 1
    assert [(s.irrep, s.n_modes, s.isotropy_group) for s in imma.rest] == [
        ("S8", 2, "Imma (74)")]
    i4mcm = _one(r, "S10", 140)
    assert i4mcm.rest == ()


def test_a_generic_child_displacement_is_reached_completely(at_r, at_gamma):
    """Every candidate's basis spans its child: a symmetry-allowed field leaves 1e-10.

    The positive arm: the same field projected on the driving irrep alone
    leaves a residual wherever the child has further irreps.
    """
    rng = np.random.default_rng(7)
    with_secondary = 0
    for parent, cands in (at_r, at_gamma):
        for c in cands:
            moved = _displaced(c.child, rng)
            dec = D.mode_amplitudes(parent, moved, c.transform)
            assert [r.irrep for r in dec.rows] == [x.irrep for x in c.basis.components]
            assert dec.residual < 1e-10 * max(dec.total, 1.0), c.label
            assert sum(r.amplitude ** 2 for r in dec.rows) == pytest.approx(
                dec.total ** 2, rel=1e-10)
            primary = dec.rows[c._driving_index].amplitude
            if c.rest:
                with_secondary += 1
                assert dec.total ** 2 - primary ** 2 > 1e-8, c.label
    assert with_secondary >= 5


# --------------------------------------------------------------------------
# (P, p)
# --------------------------------------------------------------------------

def test_the_child_group_is_the_symmetry_of_the_displaced_child(at_r, at_gamma):
    """spglib reads exactly the stated group off the displaced child, in its own cell."""
    rng = np.random.default_rng(11)
    for _, cands in (at_r, at_gamma):
        for c in cands:
            moved = _displaced(c.child, rng)
            group = resolve_group(moved.space_group, None)
            positions, types = [], []
            for n, atom in enumerate(moved.atoms):
                xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
                for image in site_orbit(group, xyz).images:
                    positions.append(np.asarray(image, float) % 1.0)
                    types.append(n)
            lattice = np.linalg.cholesky(c.basis.metric)
            data = spglib.get_symmetry_dataset((lattice, positions, types), symprec=1e-4)
            assert data.number == _number(c), c.label
            assert len(data.rotations) == len(list(gemmi.find_spacegroup_by_name(
                c.child_group).operations())), c.label


def test_a_wrong_origin_is_refused(at_r):
    """The positive arm for p: half a parent cell off, C1's subgroup check refuses."""
    parent, r = at_r
    for c in (_one(r, "S10", 140), _one(r, "S10", 74), _one(r, "S10", 167)):
        big, small = c.transform
        dec = D.mode_amplitudes(parent, _displaced(c.child, np.random.default_rng(3)),
                                (big, small))
        assert dec.residual < 1e-10
        with pytest.raises(ValueError, match="CHILD_NOT_A_SUBGROUP|CHILD_ATOMS_UNPAIRED"):
            D.mode_amplitudes(parent, c.child, (big, small + np.array([0.5, 0, 0])))


# --------------------------------------------------------------------------
# the unit, and the match with C1 on LaMnO₃
# --------------------------------------------------------------------------

def test_the_i4mcm_tilt_is_normalised_over_half_its_cell(at_r, lamno3):
    """R4+ (a,0,0): each O that moves goes ½ Å per Å, eight per I-centred cell.

    Over the conventional cell the norm would be √2, so the movers would go
    1/√8 Å; and a planted amplitude comes back from C1's decomposition.
    """
    parent, r = at_r
    _, a = lamno3
    c = _one(r, "S10", 140)
    big, small = c.transform
    assert c.basis.lattice_points == 2
    assert abs(np.linalg.det(big)) == pytest.approx(4)
    (vector,) = c.driving.vectors
    lengths = np.sqrt(np.einsum("ni,ij,nj->n", vector, c.basis.metric, vector))
    moving = lengths > 1e-9
    assert moving.sum() == 8
    assert np.allclose(lengths[moving], 0.5, atol=1e-12)
    assert {c.basis.species[i] for i in np.flatnonzero(moving)} == {"O"}

    amplitude = 0.137
    moved = c.child.model_copy(deep=True)
    pos = {tuple(np.round(p, 9)): v for p, v in zip(c.basis.positions, vector)}
    atoms = []
    for atom in moved.atoms:
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        xyz = xyz + amplitude * pos[tuple(np.round(xyz % 1.0, 9))]
        atoms.append(atom.model_copy(update={
            "x": P_(value=float(xyz[0])), "y": P_(value=float(xyz[1])),
            "z": P_(value=float(xyz[2]))}))
    dec = D.mode_amplitudes(parent, moved.model_copy(update={"atoms": atoms}), c.transform)
    (row,) = dec.rows
    assert abs(row.amplitude) == pytest.approx(amplitude, abs=1e-12)


def _parent_field(basis, vectors):
    """Positions and displacements in parent fractions: r = P·x + p, u = P·v."""
    big, small = basis.transform
    return basis.positions @ big.T + small, vectors @ big.T


def test_the_imma_tilt_measures_the_pnma_fixtures_r4_amplitude(at_r, lamno3):
    """C1's Pnma R4+ (S10) row is 1.194 Å; the Imma candidate's mode gives it exactly.

    Pnma is not a single-k candidate (it needs R4+ and M3+ together), so the
    match is made on the irrep the two share.  The candidate's mode is carried
    onto the Pnma reference cell by each of the 48 parent operations (the
    domains); in the matching one it lies in Pnma's one-mode R4+ subspace, so
    its projection is that row's amplitude, and in the others it is smaller.
    The norm over the Pnma cell, twice the Imma primitive cell, is √2.
    """
    dec, _ = lamno3
    _, r = at_r
    imma = _one(r, "S10", 74)
    (row,) = [x for x in dec.rows if x.irrep == "S10" and x.k == ("1/2", "1/2", "1/2")]
    assert row.isotropy_group == "Imma (74)" and row.n_modes == 1

    pnma_r, pnma_u = _parent_field(dec.basis, dec.displacements)
    cand_r, (cand_v,) = _parent_field(imma.basis, imma.driving.vectors)
    big_c = imma.transform[0]
    inv_c = np.linalg.inv(big_c)
    p_inv = np.linalg.inv(np.array(LAMNO3_P, float))
    g_parent = p_inv.T @ dec.basis.metric @ p_inv
    projections = []
    for op in gemmi.SpaceGroup("P m -3 m").operations():
        rot = np.array(op.rot, float) / 24
        tran = np.array(op.tran, float) / 24
        w = np.zeros_like(pnma_u)
        for i, x in enumerate(pnma_r):
            source = np.linalg.solve(rot, x - tran)
            d = (source - cand_r) @ inv_c.T
            d -= np.rint(d)
            (j,) = np.flatnonzero(np.all(np.abs(d) < 1e-6, axis=1))
            w[i] = rot @ cand_v[j]
        norm2 = float(np.einsum("ni,ij,nj->", w, g_parent, w))
        assert norm2 == pytest.approx(2.0, abs=1e-10)
        projections.append(abs(float(np.einsum("ni,ij,nj->", pnma_u, g_parent, w)))
                           / np.sqrt(norm2))
    assert max(projections) == pytest.approx(row.amplitude, abs=1e-9)
    assert row.amplitude == pytest.approx(1.194, abs=5e-4)
    assert min(projections) < 0.9 * row.amplitude


def test_unknown_sites_are_refused(at_gamma):
    parent, _ = at_gamma
    with pytest.raises(ValueError, match="not atoms"):
        I.distortion_candidates(parent, K_GAMMA, sites=["Fe"])


def test_each_direction_is_listed_once_with_every_site_that_carries_it():
    """Γ4− (S9) lives on all three sites; it is one candidate per direction, not three."""
    parent = _perovskite(3.9)
    cands = I.distortion_candidates(parent, K_GAMMA)
    labels = [c.label for c in cands]
    assert len(labels) == len(set(labels))
    polar = [c for c in cands if c.irrep == "S9"]
    assert len(polar) == 6
    assert all(c.sites == ("Mn", "La", "O") for c in polar)
    assert {c.sites for c in cands if c.irrep == "S7"} == {("O",)}


# --------------------------------------------------------------------------
# review round 1 (#996): spellings of k, shared sites, the merge, the names
# --------------------------------------------------------------------------

@pytest.mark.parametrize("spelling", [
    (Fraction(-1, 2),) * 3,
    (Fraction(3, 2), Fraction(1, 2), Fraction(1, 2)),
], ids=["minus-R", "three-halves"])
def test_an_equivalent_spelling_of_k_gives_the_same_candidates(at_r, spelling):
    """(−½,−½,−½) and (3/2,½,½) are the R point: same list, and each driving irrep found."""
    _, expected = at_r
    cands = I.distortion_candidates(_perovskite(3.9), spelling, sites=["O"])
    assert [c.label.split(" ", 1)[0] for c in cands] == [
        c.label.split(" ", 1)[0] for c in expected]
    assert [c.child_group for c in cands] == [c.child_group for c in expected]
    assert all(c.driving.irrep == c.irrep for c in cands)


def test_a_shared_site_gets_the_documented_refusal():
    """La and Sr on one site: the refusal that exists for it, not "this is a bug"."""
    parent = rx.Phase(name="mixed", space_group="P m -3 m", cell=rx.Cell.cubic(3.9), atoms=[
        _atom("La", "La", 0.5, 0.5, 0.5), _atom("Sr", "Sr", 0.5, 0.5, 0.5),
        _atom("Mn", "Mn", 0, 0, 0), _atom("O", "O", 0.5, 0, 0)])
    with pytest.raises(ValueError, match="share one site"):
        I.distortion_candidates(parent, K_R, sites=["O"])
    # the positive arm: the same atoms on distinct sites are accepted
    separate = parent.model_copy(update={"atoms": [parent.atoms[0], *parent.atoms[2:]]})
    assert I.distortion_candidates(separate, K_GAMMA, sites=["Mn"])


def test_sites_merged_under_one_label_must_carry_one_group(monkeypatch):
    """Γ4− on three sites is one candidate per direction; a label with two groups raises."""
    parent = _perovskite(3.9)
    assert I.distortion_candidates(parent, K_GAMMA, sites=["Mn", "La"])
    counter = iter(range(10 ** 6))
    monkeypatch.setattr(I, "_group_signature", lambda candidate: next(counter))
    with pytest.raises(RuntimeError, match="one direction label but different isotropy"):
        I.distortion_candidates(parent, K_GAMMA, sites=["Mn", "La"])


def test_driving_is_the_built_from_irrep_and_primary_is_the_isotropy_test(at_r):
    """Imma's S8 is in `rest` although its own isotropy group is the child's (`primary`)."""
    _, r = at_r
    imma = _one(r, "S10", 74)
    (other,) = imma.rest
    assert other.irrep == "S8" and other.isotropy_group == "Imma (74)"
    assert other.primary is True
    assert imma.driving.irrep == imma.irrep == "S10"
    assert not hasattr(imma, "primary") and not hasattr(imma, "secondary")
