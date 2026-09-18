"""Decomposition and basis vectors: the measured Pnma arms, and the sweeps.

Four tiers, in the order they were built:

1. **The measured positive arms.**  Bertaut's (1968) Pnma decomposition and its
   basis vectors, reproduced from this package's own irreps with no oracle in
   the loop: the 4b site at k = 0 gives multiplicity 3 on each of the four
   inversion-even irreps and its twelve basis vectors are exactly the textbook
   F/G/C/A modes along x, y and z; the 4c site brings the odd irreps in; the
   zone-boundary k = (0,0,½) gives two two-dimensional irreps with multiplicity
   3 each.  The multiplicities are the 2026-09-03 spgrep/spglib measurement in
   an independent representation-analysis run.

2. **A published worked example at k ≠ 0** — Davies & Wills (2016),
   *arXiv*:1610.00472, a preprint by SARAh's author.  I 4₁ 32 at
   k = (½,½,½) with an atom at the origin: the site's stabiliser is a 3-fold
   about (1,1,1), the little group splits the orbit into two sets of four, each
   set decomposes as 2Γ¹ + 2Γ² + 2Γ³ with every irrep two-dimensional, and
   projecting the three Cartesian trial vectors at one atom over-generates —
   three vectors spanning a two-dimensional row space.  What is compared is the
   decomposition, the orbit and the *ranks*: a basis vector is fixed only up to
   the intertwiner, so components are not comparable across codes and the
   paper's own table is not reproduced componentwise here.

3. **Structure that must hold everywhere**: the factor system of Γ_perm ⊗ Γ_vec
   equals the irreps module's, Σ n_ν·d_ν = 3N, the basis vectors of all irreps
   span C^{3N} orthonormally in the cell metric, and the equivariance relation
   Γ(g)ψ_i = Σ_m D(g)_{mi}ψ_m holds — swept over all 230 groups at Γ and over
   the zone-boundary k set for the non-symmorphic ones.

4. **The negative controls**, each with the interpretation written down first:
   the polar action flips the inversion parity of every mode; conjugating the
   return-vector phase is invisible at k = 0 and fatal at k ≠ 0; and dropping
   det(R) from the axial action is caught by **neither** Σ n·d = 3N **nor** the
   equivariance test, which is asserted rather than assumed so that nobody
   deletes the parity comparison as redundant.

The F/G/C/A conventions this file compares against, spelled out because the
labels are meaningless without them (Bertaut, 1968; Wollan & Koehler, 1955):
the atom order is International Tables' own 4b listing for P n m a —
(0,0,½), (½,0,0), (0,½,½), (½,½,0) — and over that order

    F = S₁+S₂+S₃+S₄   G = S₁−S₂+S₃−S₄   C = S₁+S₂−S₃−S₄   A = S₁−S₂−S₃+S₄.

``site_orbit`` lists the same four positions in a different order, so the test
permutes into the International Tables one before naming a mode, and the
permutation is derived from the positions rather than written down.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from fractions import Fraction

import gemmi
import numpy as np
import pytest

from rietx.crystallography.magnetic import modes
from rietx.crystallography.magnetic.irreps import (
    inversion_parity,
    little_group,
    small_irreps,
)
from rietx.crystallography.symmetry import get_spacegroup
from rietx.crystallography.wyckoff import site_constraints

HALF = Fraction(1, 2)

PNMA = "P n m a"
#: The 4b site of P n m a — a site with inversion, which is what makes the
#: axial/polar parity control below discriminate.
PNMA_4B = (0.0, 0.0, 0.5)
#: The 4c site (x, ¼, z), whose site symmetry has no inversion.
PNMA_4C = (0.2, 0.25, 0.6)

#: International Tables' order for the 4b positions of P n m a.  Every F/G/C/A
#: name in this file is relative to this order and to nothing else.
ITA_4B = ((0.0, 0.0, 0.5), (0.5, 0.0, 0.0), (0.0, 0.5, 0.5), (0.5, 0.5, 0.0))

#: The Bertaut modes as sign patterns over :data:`ITA_4B`.
BERTAUT_MODES = {
    "F": (1, 1, 1, 1),
    "G": (1, -1, 1, -1),
    "C": (1, 1, -1, -1),
    "A": (1, -1, -1, 1),
}
AXES = "xyz"

#: The four mode triples the four inversion-even irreps of P n m a carry on a
#: four-atom orbit — Bertaut (1968), as reproduced for P n m a (rather than the
#: P b n m setting Bertaut himself used) throughout the orthoperovskite
#: literature, e.g. Sasani, Iñiguez & Bousquet (2021), *Phys. Rev. B* **104**,
#: 064431.  Compared as a **set**: which of the four goes with which positional
#: irrep label depends on the irrep numbering, which is this package's own and
#: is not CDML's.
BERTAUT_PNMA_QUARTET = frozenset({
    ("Ax", "Gy", "Cz"),
    ("Fx", "Cy", "Gz"),
    ("Cx", "Fy", "Az"),
    ("Gx", "Ay", "Fz"),
})

#: Γ plus every zone-boundary point with all coordinates in {0, ½}, the set on
#: which the factor system is projective.
ZONE_BOUNDARY_SET = tuple(
    tuple(map(Fraction, c)) for c in itertools.product([0, HALF], repeat=3)
)

#: A general position no space group makes special, and the origin, which every
#: group has and which is special in most of them.  One of each is what the
#: sweeps below run per group.
GENERAL_SITE = (0.1234, 0.5678, 0.9137)
SPECIAL_SITE = (0.0, 0.0, 0.0)

#: Settings covering all seven crystal systems, every centring letter and both
#: symmorphic and non-symmorphic groups.  The fast tier sweeps these; the slow
#: tier sweeps all 230.
REPRESENTATIVE_SETTINGS = (
    "P 1", "P -1", "P 2/m", "C 2/m", "P 21/c", "C 2/c",
    "P m m m", "P n m a", "C m c m", "I b a m", "F d d d", "A e m 2",
    "P 4/m m m", "I 41/a m d", "P 42/n n m",
    "P -3 m 1", "R -3 c:H", "R -3 c:R", "P 31 2 1",
    "P 6/m m m", "P 63/m m c",
    "P m -3 m", "F m -3 m", "I a -3 d", "F d -3 m:2", "P a -3", "I 41 3 2",
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _all_settings() -> tuple[str, ...]:
    """One setting per space-group number, 1…230, in gemmi's own order."""
    seen: dict[int, str] = {}
    for entry in gemmi.spacegroup_table():
        seen.setdefault(entry.number, entry.xhm())
    return tuple(seen[n] for n in range(1, 231))


def _is_symmorphic(symbol: str) -> bool:
    """True when the group's coset representatives have no intrinsic translation.

    In the standard setting International Tables gives a symmorphic group, the
    origin already sits on a point whose stabiliser is the whole point group,
    so every coset representative is a plain rotation.  That makes the test one
    line over gemmi's own standard settings, and the count it produces — 73
    symmorphic, 157 not — is asserted by its caller rather than assumed.
    """
    return all(all(t == 0 for t in op.tran)
               for op in get_spacegroup(symbol).operations().sym_ops)


def _ita_order(positions: np.ndarray, wanted=ITA_4B) -> list[int]:
    """Index into ``positions`` for each position of ``wanted``, matched mod 1."""
    order = []
    for target in wanted:
        delta = positions - np.asarray(target)
        match = np.flatnonzero(np.all(np.abs(delta - np.rint(delta)) < 1e-6, axis=1))
        assert match.size == 1, f"{target} matched {match.size} orbit atoms"
        order.append(int(match[0]))
    return order


def _mode_name(vector: np.ndarray, order: list[int], atol: float = 1e-9) -> str | None:
    """``"Gx"``-style name of a basis vector, or ``None`` if it is not a pure mode.

    A pure mode is non-zero along one crystal axis only and, along that axis,
    proportional to one of the four Bertaut sign patterns over
    :data:`ITA_4B`.
    """
    reordered = np.real_if_close(vector[order], tol=1e6)
    if np.iscomplexobj(reordered):
        return None
    for axis in range(3):
        column = reordered[:, axis]
        others = np.delete(reordered, axis, axis=1)
        if np.max(np.abs(others)) > atol or np.max(np.abs(column)) <= atol:
            continue
        unit = column / column[int(np.argmax(np.abs(column)))]
        for name, pattern in BERTAUT_MODES.items():
            signs = np.array(pattern, dtype=float)
            signs = signs / signs[int(np.argmax(np.abs(column)))]
            if np.max(np.abs(unit - signs)) <= atol:
                return f"{name}{AXES[axis]}"
    return None


def _conjugate_return_phases(rep: modes.SiteRepresentation) -> modes.SiteRepresentation:
    """The same representation with exp(−2πi k·a) replaced by exp(+2πi k·a).

    The sign of the return-vector phase is the convention this module and
    :mod:`.irreps` have to agree on, and it is invisible at k = 0 — every phase
    is 1 there — so a control for it has to be run at k ≠ 0.  Built by
    conjugating the finished phases rather than by editing the module, so the
    control cannot go stale against a refactor of how they are computed.
    """
    perm = rep.permutation
    phases = np.conj(perm.phases)
    matrices = np.zeros_like(perm.matrices)
    columns = np.arange(perm.n_atoms)
    for g in range(rep.little.order):
        matrices[g, perm.permutations[g], columns] = phases[g]
    flipped = replace(perm, phases=phases, matrices=matrices)
    return replace(
        rep,
        permutation=flipped,
        matrices=np.array([np.kron(matrices[g], rep.vector[g])
                           for g in range(rep.little.order)]),
    )


def _span_invariance(rep: modes.SiteRepresentation, vectors: np.ndarray) -> float:
    """How far Γ(g)·span{ψ} sits outside span{ψ}, worst over the little group.

    The vectors are orthonormal in the cell metric S, so the S-orthogonal
    projector onto their span is V·V†·S and the residual is
    ‖V·V†·S·Γ(g)·V − Γ(g)·V‖.  This is the span-level statement — the only one
    comparable between two codes, since a basis is fixed only up to the
    intertwiner and the ordering of the copies.
    """
    v = vectors.T                                              # (dim, M)
    moved = np.einsum("gab,bm->gam", rep.matrices, v)
    weighted = np.einsum("ab,gbm->gam", rep.inner_product, moved)
    coefficients = np.einsum("di,gdm->gim", np.conj(v), weighted)
    return float(np.max(np.abs(np.einsum("ai,gim->gam", v, coefficients) - moved)))


# --------------------------------------------------------------------------
# tier 1 — the measured positive arms
# --------------------------------------------------------------------------

def test_the_two_pnma_sites_this_file_uses_are_the_wyckoff_positions_it_names():
    """4b and 4c, from the Wyckoff machinery, not from the coordinates I typed."""
    assert site_constraints(PNMA, PNMA_4B).wyckoff == "4b"
    assert site_constraints(PNMA, PNMA_4B).site_symmetry == "-1"
    assert site_constraints(PNMA, PNMA_4C).wyckoff == "4c"
    assert "m" in site_constraints(PNMA, PNMA_4C).site_symmetry


def test_bertaut_pnma_4b_at_gamma_puts_three_modes_on_each_inversion_even_irrep():
    """Arm A: even 3,3,3,3 and odd 0,0,0,0, Σ n·dim = 12 (``ra_check.out``)."""
    rep = modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0))
    irreps = small_irreps(PNMA, (0, 0, 0))
    decomposition = modes.decompose(rep, irreps)

    assert rep.n_atoms == 4
    assert rep.dimension == 12
    even = [n for ir, n in zip(irreps, decomposition.multiplicities)
            if inversion_parity(ir) == 1]
    odd = [n for ir, n in zip(irreps, decomposition.multiplicities)
           if inversion_parity(ir) == -1]
    assert even == [3, 3, 3, 3]
    assert odd == [0, 0, 0, 0]
    assert decomposition.total == 12


def test_the_pnma_4b_basis_vectors_are_the_textbook_f_g_c_a_modes():
    """Arm A's basis vectors: twelve pure modes, one per (mode, axis) pair."""
    rep = modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0))
    table = modes.mode_table(rep, small_irreps(PNMA, (0, 0, 0)))
    order = _ita_order(rep.positions)

    per_irrep = {}
    for basis in table.bases:
        assert basis.irrep.dimension == 1
        assert basis.multiplicity == 3
        assert basis.real
        names = [_mode_name(basis.vectors[j, 0], order) for j in range(3)]
        assert None not in names, f"{basis.irrep.label} gave {names}, not pure modes"
        per_irrep[basis.irrep.label] = tuple(names)

    flat = [name for names in per_irrep.values() for name in names]
    assert len(flat) == 12
    assert set(flat) == {f"{m}{a}" for m in BERTAUT_MODES for a in AXES}, (
        "the twelve basis vectors must be each Bertaut mode along each axis exactly once")

    # each irrep carries one mode per axis, and the four triples are Bertaut's
    for names in per_irrep.values():
        assert sorted(n[1] for n in names) == list(AXES)
    triples = frozenset(tuple(sorted(names, key=lambda name: name[1]))
                        for names in per_irrep.values())
    assert triples == BERTAUT_PNMA_QUARTET, per_irrep


def test_pnma_4c_is_the_control_that_brings_the_odd_irreps_in():
    """Arm B: a site without inversion puts modes on the odd irreps too."""
    rep = modes.magnetic_representation(PNMA, PNMA_4C, (0, 0, 0))
    irreps = small_irreps(PNMA, (0, 0, 0))
    decomposition = modes.decompose(rep, irreps)

    even = sorted(n for ir, n in zip(irreps, decomposition.multiplicities)
                  if inversion_parity(ir) == 1)
    odd = sorted(n for ir, n in zip(irreps, decomposition.multiplicities)
                 if inversion_parity(ir) == -1)
    assert even == [1, 1, 2, 2]
    assert odd == [1, 1, 2, 2]
    assert decomposition.total == 12


def test_pnma_4b_at_the_zone_boundary_gives_two_two_dimensional_irreps():
    """Arm C: k = (0,0,½), two 2-D irreps with multiplicity 3, Σ n·dim = 12."""
    k = (0, 0, HALF)
    rep = modes.magnetic_representation(PNMA, PNMA_4B, k)
    irreps = small_irreps(PNMA, k)
    decomposition = modes.decompose(rep, irreps)

    assert [ir.dimension for ir in irreps] == [2, 2]
    assert decomposition.multiplicities == (3, 3)
    assert decomposition.total == 12
    # no inversion parity exists at this k: M-6(a) measured chi(-1) = 0 exactly
    assert [inversion_parity(ir) for ir in irreps] == [None, None]


def test_the_zone_boundary_basis_vectors_are_real_because_two_k_is_a_lattice_vector():
    """Arm C's vectors: real, and needing no k/−k pairing.

    The brief for this rung expected complex vectors here.  They are not, and
    the reason is measured rather than asserted: 2k = (0,0,1) *is* a reciprocal
    lattice vector of a P lattice, so −k ≡ k, the small irreps are real
    (Frobenius–Schur +1), the return phases are all ±1 and Γ itself is a real
    matrix.  A moment built on a complex basis vector would then have to equal
    its own conjugate, so the physical content is real, and this module returns
    it that way.  The k/−k pairing belongs to a k with 2k ≢ 0 — see the
    I 4₁ 32 test below, which has one.
    """
    k = (0, 0, HALF)
    rep = modes.magnetic_representation(PNMA, PNMA_4B, k)
    irreps = small_irreps(PNMA, k)

    assert little_group(PNMA, k).has_minus_k
    assert float(np.max(np.abs(rep.matrices.imag))) == 0.0
    total_amplitudes = 0
    for irrep in irreps:
        basis = modes.basis_vectors(rep, irrep)
        assert irrep.frobenius_schur == 1
        assert basis.real, "a real irrep in a real representation must give real vectors"
        assert basis.reality == "real"
        assert basis.free_real_amplitudes == 6
        assert float(np.max(np.abs(basis.vectors.imag))) == 0.0
        total_amplitudes += basis.free_real_amplitudes
    assert total_amplitudes == rep.dimension == 12


@pytest.mark.parametrize("site, k", [
    (PNMA_4B, (0, 0, 0)),
    (PNMA_4C, (0, 0, 0)),
    (PNMA_4B, (0, 0, HALF)),
    (PNMA_4C, (HALF, 0, HALF)),
])
def test_the_basis_vectors_of_all_irreps_span_the_whole_space_orthonormally(site, k):
    """Completeness: rank 3N, and an identity Gram matrix in the cell metric."""
    rep = modes.magnetic_representation(PNMA, site, k)
    table = modes.mode_table(rep, small_irreps(PNMA, k))
    stacked = np.concatenate([b.vectors.reshape(-1, rep.dimension) for b in table.bases])

    assert stacked.shape[0] == rep.dimension
    assert np.linalg.matrix_rank(stacked, tol=1e-10) == rep.dimension
    gram = stacked.conj() @ rep.inner_product @ stacked.T
    assert float(np.max(np.abs(gram - np.eye(rep.dimension)))) < 1e-12


# --------------------------------------------------------------------------
# tier 2 — the published k != 0 worked example
# --------------------------------------------------------------------------

I4132 = "I 41 3 2"
I4132_K = (HALF, HALF, HALF)
#: Davies & Wills (2016), arXiv:1610.00472, worked example: the four positions
#: their basis-vector tables are written for.  ``site_orbit`` reaches the same
#: four atoms of the primitive cell, but two of them through the body-centring
#: translation, so the comparison is made modulo the I centring.
DAVIES_WILLS_ORBIT = ((0, 0, 0), (0.5, 0.5, 0), (0, 0.5, 0.5), (0.5, 0, 0.5))


def test_the_davies_wills_i4132_example_has_the_orbit_and_stabiliser_it_prints():
    """Their setup: a 3-fold stabiliser about (1,1,1), and two G_k orbits of four."""
    constraints = site_constraints(I4132, (0, 0, 0))
    assert constraints.wyckoff == "16e"
    assert constraints.site_symmetry == ".3."          # "the group of C3 rotations"

    rep = modes.magnetic_representation(I4132, (0, 0, 0), I4132_K)
    assert rep.n_atoms == 8                            # one primitive cell
    assert rep.little.order == 12
    assert [len(o) for o in rep.orbits] == [4, 4]      # "split into two orbits"

    positions = rep.positions[list(rep.orbits[0])]
    for target in DAVIES_WILLS_ORBIT:
        delta = positions - np.asarray(target)
        centred = delta - np.array([0.5, 0.5, 0.5])
        near = np.all(np.abs(delta - np.rint(delta)) < 1e-6, axis=1)
        near |= np.all(np.abs(centred - np.rint(centred)) < 1e-6, axis=1)
        assert near.sum() == 1, f"{target} is not one atom of the first G_k orbit"


def test_the_davies_wills_i4132_example_decomposes_the_way_sarah_printed_it():
    """Γ_Mag = 2Γ¹ + 2Γ² + 2Γ³ per G_k orbit, every irrep two-dimensional."""
    rep = modes.magnetic_representation(I4132, (0, 0, 0), I4132_K)
    irreps = small_irreps(I4132, I4132_K)
    assert [ir.dimension for ir in irreps] == [2, 2, 2]

    for orbit in rep.orbits:
        block = rep.restrict(orbit)
        decomposition = modes.decompose(block, irreps)
        assert decomposition.multiplicities == (2, 2, 2)
        assert decomposition.total == 12 == block.dimension


def test_the_davies_wills_i4132_example_pairs_k_with_minus_k():
    """2k is not a reciprocal lattice vector of an I lattice, so the irreps pair.

    (1,1,1)·(½,½,½) = 3/2 is not an integer, so the body-centred lattice's
    reciprocal does not contain 2k and D* lives at −k.  This is the branch the
    Pnma zone-boundary arm does *not* exercise, and the amplitude count doubles
    because of it.
    """
    rep = modes.magnetic_representation(I4132, (0, 0, 0), I4132_K)
    irreps = small_irreps(I4132, I4132_K)
    assert not rep.little.has_minus_k

    total = 0
    for irrep in irreps:
        basis = modes.basis_vectors(rep, irrep)
        assert not basis.real
        assert "-k" in basis.pairing
        assert basis.free_real_amplitudes == 2 * basis.multiplicity * irrep.dimension
        total += basis.multiplicity * irrep.dimension
    assert total == rep.dimension == 24


def test_the_davies_wills_i4132_example_projects_four_vectors_not_six():
    """Their over-generation: three trial vectors span a two-dimensional row space.

    "Projection using the standard trial functions generates six apparently
    distinct BVs, rather than the four required by the reduction formula."  The
    four are what this module returns — n_ν·d_ν = 2·2 — and the surplus is
    visible as the rank of W^ν_{11} applied to the three Cartesian trial
    vectors at one atom, which is 2 and not 3.
    """
    rep = modes.magnetic_representation(I4132, (0, 0, 0), I4132_K)
    block = rep.restrict(rep.orbits[0])
    irreps = small_irreps(I4132, I4132_K)

    for irrep in irreps:
        basis = modes.basis_vectors(block, irrep)
        assert basis.multiplicity * irrep.dimension == 4
        assert basis.vectors.shape == (2, 2, 4, 3)

        row_projector = (np.einsum("g,gab->ab", np.conj(basis.irrep_matrices[:, 0, 0]),
                                   block.matrices)
                         * irrep.dimension / block.little.order)
        trial = row_projector[:, :3]        # atom 1 along a, b and c
        assert np.linalg.matrix_rank(trial, tol=1e-9) == 2, (
            "three trial vectors at one atom must over-generate a two-dimensional "
            "row-1 space — Davies & Wills (2016) section 4")


# --------------------------------------------------------------------------
# tier 3 — structure that must hold everywhere
# --------------------------------------------------------------------------

def test_the_polar_and_axial_actions_are_r_and_det_r_times_r():
    """The two vector representations, and that they differ only on improper ops."""
    little = little_group(PNMA, (0, 0, 0))
    polar = modes.vector_representation(little.rotations, "polar")
    axial = modes.vector_representation(little.rotations, "axial")
    dets = np.linalg.det(little.rotations.astype(float))

    assert np.allclose(polar, little.rotations.astype(float))
    assert np.allclose(axial, dets[:, None, None] * polar)
    assert np.any(dets < 0), "P n m a has improper operations; the control needs them"
    assert not np.allclose(polar, axial)


def test_the_axial_action_on_fractional_components_matches_the_cartesian_one():
    """D-3's conversion, as a round trip rather than as a claim.

    A moment stored as crystal-axis components m has Cartesian components
    Aᵀ·m with A the row-vector cell matrix.  Rotating in Cartesian —
    det(R_cart)·R_cart with R_cart = A·R·A⁻¹ — and coming back must equal
    det(R)·R applied to m directly, for every operation and every cell the
    group admits.  A hexagonal setting is in the list because its fractional
    rotations are the ones that are not orthogonal.
    """
    for symbol in ("P n m a", "P 63/m m c", "R -3 c:R", "P 21/c"):
        rotations = little_group(symbol, (0, 0, 0)).rotations.astype(float)
        cell = np.linalg.cholesky(modes.crystal_metric(symbol))   # rows are a, b, c
        moment = np.array([0.31, -0.72, 0.45])
        for kind, sign in (("axial", 1), ("polar", 0)):
            fractional = modes.vector_representation(rotations, kind)
            for rot, frac_action in zip(rotations, fractional):
                cartesian = cell.T @ rot @ np.linalg.inv(cell.T)
                factor = np.linalg.det(cartesian) ** sign
                direct = cell.T @ (frac_action @ moment)
                through_cartesian = factor * cartesian @ (cell.T @ moment)
                assert np.allclose(direct, through_cartesian, atol=1e-12), (symbol, kind)


@pytest.mark.parametrize("symbol", REPRESENTATIVE_SETTINGS)
def test_the_crystal_metric_is_invariant_under_every_rotation_of_the_group(symbol):
    """RᵀGR = G — what makes the fractional action orthogonal and the Gram real."""
    metric = modes.crystal_metric(symbol)
    assert np.all(np.linalg.eigvalsh(metric) > 0)
    for op in get_spacegroup(symbol).operations().sym_ops:
        rot = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        assert np.allclose(rot.T @ metric @ rot, metric, atol=1e-12), symbol


@pytest.mark.parametrize("symbol, site, conventional, primitive", [
    ("F m -3 m", (0, 0, 0), 4, 1),
    ("I m -3 m", (0, 0, 0), 2, 1),
    ("C 2/m", (0, 0, 0), 2, 1),
    ("R -3 c:H", (0, 0, 0), 6, 2),
    ("F d -3 m:2", (0.5, 0.5, 0.5), 16, 4),
    ("P n m a", PNMA_4B, 4, 4),
])
def test_a_centred_lattice_orbit_collapses_onto_one_primitive_cell(
        symbol, site, conventional, primitive):
    """The conventional multiplicity divided by the centring count, exactly.

    Leaving the centring copies in would multiply 3N — and every multiplicity
    with it — by the number of lattice points in the conventional cell, while
    Σ n·dim = 3N would still close, so the sum check cannot catch it and this
    test has to.
    """
    from rietx.crystallography.symmetry import site_orbit

    sg = get_spacegroup(symbol)
    assert site_orbit(sg, np.asarray(site, dtype=float)).multiplicity == conventional
    assert modes.orbit_positions(symbol, site).shape == (primitive, 3)


@pytest.mark.parametrize("symbol", REPRESENTATIVE_SETTINGS)
@pytest.mark.parametrize("kind", modes.VECTOR_KINDS)
def test_the_site_representation_carries_the_irreps_factor_system(symbol, kind):
    """Γ_perm ⊗ Γ_vec obeys D(i)D(j) = ω(i,j)D(ij) with the irreps module's ω.

    Checked at a zone-boundary k, where ω is not a coboundary for a
    non-symmorphic group and a translation-convention error is fatal rather
    than invisible.
    """
    k = (HALF, HALF, HALF)
    rep = modes.magnetic_representation(symbol, GENERAL_SITE, k, kind=kind)
    assert modes._factor_system_residual(rep) < 1e-12


def _equivariance_case(symbol, site, k, kind="axial"):
    """One (group, site, k) case: Σ n·dim = 3N, spans invariant, orthonormal.

    Returns the worst residual seen, so a sweep can report a number rather
    than only a pass.
    """
    rep = modes.magnetic_representation(symbol, site, k, kind=kind)
    irreps = small_irreps(symbol, k)
    table = modes.mode_table(rep, irreps)
    assert table.decomposition.total == rep.dimension

    worst = modes._factor_system_residual(rep)
    stacked = []
    for basis in table.bases:
        worst = max(worst, basis.equivariance_residual, basis.orthonormality_residual)
        vectors = basis.vectors.reshape(-1, rep.dimension)
        stacked.append(vectors)
        worst = max(worst, _span_invariance(rep, vectors))
    everything = np.concatenate(stacked)
    assert everything.shape[0] == rep.dimension
    assert np.linalg.matrix_rank(everything, tol=1e-9) == rep.dimension
    return worst


@pytest.mark.parametrize("symbol", REPRESENTATIVE_SETTINGS)
@pytest.mark.parametrize("site", [GENERAL_SITE, SPECIAL_SITE])
def test_equivariance_and_completeness_at_gamma(symbol, site):
    """The oracle-free check, on a representative setting per system and centring."""
    assert _equivariance_case(symbol, site, (0, 0, 0)) < 1e-10


@pytest.mark.slow
@pytest.mark.parametrize("site", [GENERAL_SITE, SPECIAL_SITE])
def test_equivariance_and_completeness_at_gamma_for_all_230_groups(site):
    """Every space group, one general and one special site, at k = 0."""
    worst, where = 0.0, None
    for symbol in _all_settings():
        residual = _equivariance_case(symbol, site, (0, 0, 0))
        if residual > worst:
            worst, where = residual, symbol
    assert worst < 1e-10, (worst, where)


@pytest.mark.slow
def test_equivariance_over_the_zone_boundary_k_set_for_the_non_symmorphic_groups():
    """The k set the projective factor system lives on, where a sign error shows.

    The brief for this rung said 74 non-symmorphic groups; there are 230 − 73
    symmorphic = 157, and the count is asserted here rather than taken on
    trust.
    """
    non_symmorphic = [s for s in _all_settings() if not _is_symmorphic(s)]
    assert len(non_symmorphic) == 157

    worst, where = 0.0, None
    for symbol in non_symmorphic:
        for k in ZONE_BOUNDARY_SET:
            for site in (GENERAL_SITE, SPECIAL_SITE):
                residual = _equivariance_case(symbol, site, k)
                if residual > worst:
                    worst, where = residual, (symbol, k, site)
    assert worst < 1e-10, (worst, where)


# --------------------------------------------------------------------------
# tier 4 — the negative controls
# --------------------------------------------------------------------------

def test_the_polar_representation_flips_the_inversion_parity_on_pnma_4b():
    """Control (i): a polar vector is odd under −1 at a site that has one.

    The axial modes of the 4b site are the four inversion-even irreps and the
    polar ones the four odd irreps, with the same multiplicity 3 — the same
    twelve degrees of freedom relabelled by the determinant.  This is the
    comparison that catches a missing det(R); the next test measures that
    nothing else does.
    """
    irreps = small_irreps(PNMA, (0, 0, 0))
    axial = modes.decompose(
        modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0), kind="axial"), irreps)
    polar = modes.decompose(
        modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0), kind="polar"), irreps)

    for irrep, axial_n, polar_n in zip(irreps, axial.multiplicities, polar.multiplicities):
        parity = inversion_parity(irrep)
        assert (axial_n, polar_n) == ((3, 0) if parity == 1 else (0, 3)), irrep.label
    assert axial.multiplicities != polar.multiplicities


def test_dropping_the_determinant_is_caught_by_neither_the_sum_nor_equivariance():
    """Control (ii), with its interpretation table written before the numbers.

    The brief for this rung expected ``Σ n·dim = 3N`` or the equivariance test
    to catch a missing det(R).  **Neither does, and neither can**: without the
    determinant the vector action is the polar one, which is an equally valid
    representation of the same group with the same factor system, so it
    decomposes exactly, spans exactly and is equivariant exactly.  What is
    asserted here is that both proposed detectors stay quiet, so that nobody
    later deletes the parity comparison above as redundant.
    """
    irreps = small_irreps(PNMA, (0, 0, 0))
    axial = modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0), kind="axial")
    broken = modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0), kind="polar")

    for rep in (axial, broken):
        assert modes.decompose(rep, irreps).total == rep.dimension == 12   # detector 1 quiet
        for basis in modes.mode_table(rep, irreps).bases:                  # detector 2 quiet
            assert basis.equivariance_residual < 1e-12
            assert basis.orthonormality_residual < 1e-12
        assert modes._factor_system_residual(rep) < 1e-12                  # and so is this

    assert (modes.decompose(axial, irreps).multiplicities
            != modes.decompose(broken, irreps).multiplicities)


def test_conjugating_the_return_phase_is_invisible_wherever_every_phase_is_real():
    """Control: the sign of exp(−2πi k·a), and exactly where it can be measured.

    The brief for this rung said the wrong sign "fails only at k ≠ 0" and that
    the decomposition would show it.  Both are weaker than that, and the
    difference decides which checks are worth having:

    * The sign is invisible wherever every return phase is **real** — the whole
      {0,½}³ zone-boundary set of a *primitive* lattice, where k·a is a
      half-integer and exp(−2πi k·a) = ±1 = its own conjugate.  Measured: the
      residual is 0.0 and the multiplicities are unchanged at both k = 0 and
      k = (0,0,½) in P n m a.
    * Where the phases *are* complex — a k of denominator 3 or more, or a
      centred lattice whose left-over lattice vectors are half-integral — the
      **decomposition still does not notice**: at P n m a k = (0,0,¼) and at
      I 4₁ 32 k = (½,½,½) the conjugated representation gives exactly the same
      multiplicities, because the character set is closed under conjugation.
      What catches it is the factor-system identity (residual 2.0 against 0)
      and the equivariance of the projected vectors (0.5 and 0.34 against
      1e-16).  Those two are therefore not decoration.
    """
    for symbol, site, k in ((PNMA, PNMA_4B, (0, 0, 0)), (PNMA, PNMA_4B, (0, 0, HALF))):
        rep = modes.magnetic_representation(symbol, site, k)
        flipped = _conjugate_return_phases(rep)
        irreps = small_irreps(symbol, k)
        assert float(np.max(np.abs(rep.permutation.phases.imag))) == 0.0
        assert modes._factor_system_residual(flipped) == 0.0
        assert (modes.decompose(flipped, irreps).multiplicities
                == modes.decompose(rep, irreps).multiplicities)

    for symbol, site, k in ((PNMA, PNMA_4B, (0, 0, Fraction(1, 4))),
                            (I4132, (0, 0, 0), I4132_K)):
        rep = modes.magnetic_representation(symbol, site, k)
        flipped = _conjugate_return_phases(rep)
        irreps = small_irreps(symbol, k)
        assert float(np.max(np.abs(rep.permutation.phases.imag))) > 0.5

        # the detector the brief expected stays quiet, and says so out loud
        assert (modes.decompose(flipped, irreps).multiplicities
                == modes.decompose(rep, irreps).multiplicities)
        # the two that fire
        assert modes._factor_system_residual(rep) < 1e-12
        assert modes._factor_system_residual(flipped) > 1.0
        with pytest.raises(RuntimeError, match="break equivariance"):
            modes.basis_vectors(flipped, irreps[0])


def test_decompose_refuses_irreps_from_a_different_little_group():
    """The multiplicities of the wrong k are numbers, so they have to be refused."""
    rep = modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0))
    with pytest.raises(ValueError, match="belongs to the little group"):
        modes.decompose(rep, small_irreps(PNMA, (0, 0, HALF)))
    with pytest.raises(ValueError, match="belongs to the little group"):
        modes.decompose(rep, small_irreps("P b n m", (0, 0, 0)))


def test_an_unknown_vector_kind_is_refused_by_name():
    with pytest.raises(ValueError, match="kind must be one of"):
        modes.vector_representation(np.eye(3).reshape(1, 3, 3), "vector")
    with pytest.raises(ValueError, match="kind must be one of"):
        modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0), kind="spin")


def test_restrict_refuses_a_set_that_is_not_closed_under_the_little_group():
    rep = modes.magnetic_representation(I4132, (0, 0, 0), I4132_K)
    assert rep.restrict(rep.orbits[0]).n_atoms == 4
    assert rep.restrict(rep.orbits[0] + rep.orbits[1]).n_atoms == 8
    with pytest.raises(ValueError, match="closed under the little group"):
        rep.restrict([0, 1])
    with pytest.raises(ValueError, match="closed under the little group"):
        rep.restrict([])


def test_the_mode_table_prints_the_atom_ordering_beside_the_vectors():
    """A mode name without its atom order is not a statement about anything."""
    rep = modes.magnetic_representation(PNMA, PNMA_4B, (0, 0, 0))
    text = str(modes.mode_table(rep, small_irreps(PNMA, (0, 0, 0))))

    assert "Gamma_axial =" in text
    assert "atoms (conventional fractional, one primitive cell):" in text
    for position in rep.positions:
        assert f"{position[2]:8.5f}" in text
    assert "psi^" in text
    assert text.count("psi^") == 12


def test_the_lattice_shift_the_phase_was_built_from_is_exact_and_recoverable():
    """The phase is integer arithmetic on the shift, not a float dot product."""
    k = (0, 0, HALF)
    rep = modes.permutation_representation(PNMA, PNMA_4B, k)
    for g in range(rep.little.order):
        rot = rep.little.rotations[g].astype(float)
        tran = np.array([float(t) for t in rep.little.translations[g]])
        for j in range(rep.n_atoms):
            shift = rep.shift(g, j)
            image = rot @ rep.positions[j] + tran
            expected = rep.positions[int(rep.permutations[g, j])] + \
                np.array([float(c) for c in shift])
            assert np.allclose(image, expected, atol=1e-12)
            phase = np.exp(-2j * np.pi * float(sum(kc * ac for kc, ac
                                                   in zip(rep.little.k, shift))))
            assert abs(phase - rep.phases[g, j]) < 1e-12
            assert rep.phases[g, j].imag == 0.0     # exact +-1 at this k


def test_total_free_real_amplitudes_counts_a_conjugate_pair_once():
    """P4 at Γ with a general site: S2 and S3 are a complex-conjugate pair (M-7,
    2026-09-06).  Summing every irrep's realified amplitudes gives 18 against
    3N = 12; a conjugate pair is one physically irreducible representation and
    the total must close on 3N.
    """
    from rietx.crystallography.magnetic.irreps import small_irreps
    from rietx.crystallography.magnetic.modes import magnetic_representation, mode_table

    rep = magnetic_representation("P 4", (0.13, 0.27, 0.41), (0, 0, 0))
    table = mode_table(rep, small_irreps("P 4", (0, 0, 0)))
    naive = sum(b.free_real_amplitudes for b in table.bases)
    assert naive == 18, naive
    assert table.total_free_real_amplitudes == 3 * len(rep.positions) == 12

