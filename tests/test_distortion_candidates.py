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


# --------------------------------------------------------------------------
# review round 2 (#996): the probe's tolerance, scale and seed decide no child
# --------------------------------------------------------------------------

K_X = (Fraction(0), Fraction(0), Fraction(1, 2))
K_M = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
#: Seeds whose *first* draw keeps an accidental operation of S6(a,b) at R on
#: the O site (4 of seeds 0-199 do; at Γ on Mn none): a single-draw probe
#: refused that child as ``DISTORTION_CHILD_LARGER``.
UNLUCKY_SEEDS = (142, 194)
#: The one seed of 0-79 whose first draw keeps an accidental operation at X
#: or M (S10(a,b) at M, all sites; review round 3).
UNLUCKY_SEED_AT_M = 41


def _setting(cands):
    """What the probe decides, per candidate: the child's group, (P, p) and its atoms.

    A refused candidate reads as its refusal's code, so a refusal fails a
    comparison with a stated child.
    """
    return [(c.label, c.refusal.code) if c.refusal is not None else
            (c.label, c.child_group, np.asarray(c.transform[0]).tolist(),
             np.asarray(c.transform[1]).tolist(),
             [(a.label, a.x.value, a.y.value, a.z.value) for a in c.child.atoms])
            for c in cands]


@pytest.fixture(scope="module")
def at_x_and_m():
    parent = _perovskite(3.9)
    return parent, {k: I.distortion_candidates(parent, k) for k in (K_X, K_M)}


def _every_call(at_r, at_gamma, at_x_and_m):
    """The suite's calls, Γ, R, X and M, each with the answer at the shipped probe."""
    (r_parent, r), (g_parent, g), (xm_parent, xm) = at_r, at_gamma, at_x_and_m
    return [(r_parent, K_R, ["O"], r), (g_parent, K_GAMMA, "Mn", g),
            *((xm_parent, k, None, cands) for k, cands in xm.items())]


@pytest.mark.parametrize("probe", [
    {"_PROBE_SYMPREC": 1e-6}, {"_PROBE_RMS": 0.01}, {"_PROBE_RMS": 0.2},
], ids=["symprec-1e-6", "rms-0.01", "rms-0.2"])
def test_the_probe_tolerance_and_scale_decide_no_child(at_r, at_gamma, at_x_and_m,
                                                       monkeypatch, probe):
    """A tolerance 1000× tighter, or a field 5× smaller or 4× larger: the same children.

    The bound on ``_PROBE_SYMPREC`` and ``_PROBE_RMS``: the operation check fixes
    an answered child's group, and this pins the refusal path, a false
    ``DISTORTION_CHILD_LARGER`` (any refusal or raise fails the test) on every call.
    """
    for name, value in probe.items():
        monkeypatch.setattr(I, name, value)
    for parent, k, sites, expected in _every_call(at_r, at_gamma, at_x_and_m):
        assert _setting(I.distortion_candidates(parent, k, sites=sites)) == _setting(expected)


def test_a_tolerance_at_the_probe_scale_finds_extra_operations(at_gamma, monkeypatch):
    """The positive arm: past the field's rms, spglib keeps the parent's 48 operations.

    The three low-symmetry children (Cm twice and P1, 2, 2 and 1 operations)
    keep more on every draw, some draw keeping all 48, so each is refused as
    ``DISTORTION_CHILD_LARGER``; it is still returned, beside the three
    children (P4mm, R3m, Amm2) a later draw states.
    """
    parent, expected = at_gamma
    monkeypatch.setattr(I, "_PROBE_SYMPREC", 4 * I._PROBE_RMS)
    cands = I.distortion_candidates(parent, K_GAMMA, sites="Mn")
    assert [c.label for c in cands] == [c.label for c in expected]
    refused = [c for c in cands if c.refusal is not None]
    assert sorted(c.refusal.operations for c in refused) == [1, 2, 2]
    for c in refused:
        assert c.refusal.code == "DISTORTION_CHILD_LARGER", c.refusal.message
        assert len(c.refusal.draws) == I._PROBE_DRAWS and 48 in c.refusal.draws
        assert all(n > c.refusal.operations for n in c.refusal.draws), c.refusal.draws
        assert "cannot realise" in c.refusal.message
    assert sorted(_number(c) for c in cands if c.refusal is None) == [38, 99, 160]


@pytest.mark.parametrize("seed", [1, 2026, *UNLUCKY_SEEDS, UNLUCKY_SEED_AT_M])
def test_the_probe_seed_decides_no_child(at_r, at_gamma, at_x_and_m, monkeypatch, seed):
    """Other seeds, three whose first draw is unlucky: the same children, P, p, atoms at Γ, R, X, M."""
    monkeypatch.setattr(I, "_PROBE_SEED", seed)
    for parent, k, sites, expected in _every_call(at_r, at_gamma, at_x_and_m):
        assert _setting(I.distortion_candidates(parent, k, sites=sites)) == _setting(expected)


@pytest.mark.parametrize(("parent_from", "k", "sites", "seed", "label"), [
    ("at_r", K_R, ["O"], UNLUCKY_SEEDS[0], "S6(a,b)"),
    ("at_x_and_m", K_M, None, UNLUCKY_SEED_AT_M, "S10(a,b)"),
], ids=["R", "M"])
def test_one_unlucky_draw_does_not_refuse_a_child(request, monkeypatch, parent_from, k, sites,
                                                  seed, label):
    """The positive arm of the seed test: with a single draw, an unlucky seed refuses a child."""
    parent, _ = request.getfixturevalue(parent_from)
    monkeypatch.setattr(I, "_PROBE_SEED", seed)
    monkeypatch.setattr(I, "_PROBE_DRAWS", 1)
    refused = _refused(I.distortion_candidates(parent, k, sites=sites))
    assert [(name, code) for name, code, _ in refused] == [(label, "DISTORTION_CHILD_LARGER")]


# --------------------------------------------------------------------------
# #996 follow-ups (review rounds 1-3): the refusal's code, and one refusal
# no longer costs the call its other candidates
# --------------------------------------------------------------------------

def _parent_group(parent):
    return resolve_group(parent.space_group, parent.symmetry_operations)


def _refused(cands):
    return [(c.label, c.refusal.code, c.refusal.draws) for c in cands if c.refusal is not None]


def test_a_stated_child_carries_no_refusal(at_r, at_gamma, at_x_and_m):
    """The positive arm of the refusal record: every child the suite states has none."""
    for _parent, _k, _sites, cands in _every_call(at_r, at_gamma, at_x_and_m):
        assert cands and all(c.refusal is None and c.child is not None for c in cands)


def test_fewer_operations_than_the_group_is_not_reported_as_more(at_gamma, monkeypatch):
    """A draw keeping fewer operations than the isotropy group is a tolerance miss.

    The probe's lattice is the parent's metric averaged over the parent's point
    group.  Skipping the average on a parent whose c is 1.3 % longer than a
    hands spglib a tetragonal lattice for the R3m child at Γ, which the field
    (rms 0.05 Å, 50× the tolerance) cannot hide: spglib keeps fewer than the
    group's 6 operations on every draw.  On main this read as
    ``DISTORTION_CHILD_LARGER`` ("these atoms cannot realise the direction's
    group"), which points the user the wrong way (review round 1).
    """
    parent, cands = at_gamma
    rhombohedral = [c for c in cands if _number(c) == 160]  # R3m, Γ4− (a,a,a)
    assert len(rhombohedral) == 1, [(c.label, c.child_group) for c in cands]
    strained = parent.model_copy(deep=True)
    strained.cell.c.value = 1.013 * parent.cell.a.value

    def unaveraged(phase, _rotations):
        a, b, c, al, be, ga = phase.cell.lengths_angles()
        assert al == be == ga == 90.0
        return np.diag([a * a, b * b, c * c])

    monkeypatch.setattr(I, "_parent_metric_symmetric", unaveraged)
    with pytest.raises(ValueError) as info:
        I._standard_child(strained, _parent_group(strained), rhombohedral[0].candidate)
    message = str(info.value)
    assert message.startswith("DISTORTION_CHILD_SMALLER: "), message
    assert "cannot realise" not in message
    refusal = info.value.refusal
    assert refusal.code == "DISTORTION_CHILD_SMALLER" and refusal.operations == 6
    assert len(refusal.draws) == I._PROBE_DRAWS
    assert all(n is not None and n < 6 for n in refusal.draws), refusal.draws


def test_one_refused_candidate_leaves_the_others(at_r, monkeypatch):
    """A refused child comes back as a refusal beside the others, not as an abort.

    One draw at seed 142 refuses S6(a,b) at R on O (review round 2's unlucky
    seed).  On main that raised, and the call lost its 15 other candidates.
    """
    parent, expected = at_r
    monkeypatch.setattr(I, "_PROBE_SEED", UNLUCKY_SEEDS[0])
    monkeypatch.setattr(I, "_PROBE_DRAWS", 1)
    cands = I.distortion_candidates(parent, K_R, sites=["O"])
    assert [c.label for c in cands] == [c.label for c in expected]
    ((label, code, draws),) = _refused(cands)
    assert (label, code) == ("S6(a,b)", "DISTORTION_CHILD_LARGER")
    (refused,) = [c for c in cands if c.refusal is not None]
    assert draws == (16,) and refused.refusal.operations == 8
    assert refused.child is None and refused.child_group is None and refused.basis is None
    assert refused.refusal.message.startswith("DISTORTION_CHILD_LARGER: ")
    with pytest.raises(ValueError, match="DISTORTION_CHILD_LARGER"):
        refused.driving  # noqa: B018 - a refused candidate has no basis to read
    stated = [c for c in cands if c.refusal is None]
    assert _setting(stated) == _setting([c for c in expected if c.label != "S6(a,b)"])


def _scripted_draws(monkeypatch, script):
    """spglib's answer to the probe's draws, draw by draw, from ``script``.

    The real path cannot be steered into a mixed sequence, so the probe's own
    call (and only that one: ``distortion_basis`` calls spglib too) is
    replaced: ``"more"`` and ``"fewer"`` answer the true dataset with twice
    the operations or one fewer, ``"none"`` raises spglib's own refusal.
    """
    import sys
    from types import SimpleNamespace

    from spglib.error import SpglibError

    real = spglib.get_symmetry_dataset
    calls = []

    def scripted(cell, *args, **kwargs):
        data = real(cell, *args, **kwargs)
        if sys._getframe(1).f_code.co_name != "_standard_child":
            return data
        outcome = script[len(calls) % len(script)]
        calls.append(outcome)
        n = len(data.rotations)
        if outcome == "none":
            raise SpglibError("scripted: no space group")
        return SimpleNamespace(rotations=np.zeros((2 * n if outcome == "more" else n - 1, 3, 3)))

    monkeypatch.setattr(spglib, "get_symmetry_dataset", scripted)
    return calls


@pytest.mark.parametrize(("script", "code"), [
    (("more", "none", "none"), "DISTORTION_CHILD_LARGER"),     # round 3's case
    (("none", "more", "none"), "DISTORTION_CHILD_LARGER"),
    (("fewer", "none", "none"), "DISTORTION_CHILD_SMALLER"),
    (("more", "fewer", "none"), "DISTORTION_CHILD_SMALLER"),
    (("fewer", "more", "more"), "DISTORTION_CHILD_SMALLER"),
    (("more", "more", "more"), "DISTORTION_CHILD_LARGER"),      # every draw agrees
    (("fewer", "fewer", "fewer"), "DISTORTION_CHILD_SMALLER"),
    (("none", "none", "none"), "DISTORTION_CHILD_UNIDENTIFIED"),
    (("none", "none", "more"), "DISTORTION_CHILD_LARGER"),      # the last draw, as on main
], ids=lambda v: "-".join(v) if isinstance(v, tuple) else None)
def test_the_code_comes_from_every_draw_not_the_last(at_gamma, monkeypatch, script, code):
    """When every draw fails, the code reads all of them, and the message names each.

    Review round 3: draw 1 keeping extra operations and draw 3 refused by
    spglib raised ``DISTORTION_CHILD_UNIDENTIFIED`` on main, from the last draw
    alone.  The scripted draws replace spglib's answer to the probe only.
    """
    parent, cands = at_gamma
    target = cands[0]
    calls = _scripted_draws(monkeypatch, script)
    with pytest.raises(ValueError) as info:
        I._standard_child(parent, _parent_group(parent), target.candidate)
    assert calls == list(script)
    message = str(info.value)
    assert message.startswith(f"{code}: "), message
    refusal = info.value.refusal
    assert refusal.code == code and len(refusal.draws) == 3
    for i, outcome in enumerate(script):
        n = refusal.draws[i]
        assert (n is None) == (outcome == "none")
        assert outcome == "none" or (n > refusal.operations) == (outcome == "more")
        assert f"draw {i + 1} " in message
