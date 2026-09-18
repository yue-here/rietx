"""Small irreps of the little group of k: the measured Pnma arm, and the oracle.

Three tiers, in the order they were built:

1. **The measured positive arm.**  Bertaut's (1968) decomposition of the
   magnetic representation of a Pnma site orbit, reproduced from this module's
   irreps with no oracle involved: the 4b site at k = 0 gives multiplicity 3 on
   each of the four inversion-even one-dimensional irreps and nothing on the
   odd ones, the 4c site (no inversion in its site symmetry) brings the odd
   ones in, and the zone-boundary k = (0, 0, 1/2) gives two two-dimensional
   irreps with multiplicity 3 each.  Σ n·dim = 12 = 4 atoms × 3 components in
   all three.  The reference numbers are the 2026-09-03 spgrep/spglib
   measurement recorded from an independent representation-analysis run.

2. **Structure that must hold everywhere**: Σ dim² = |G_k/T| over the twisted
   group algebra (Burnside), character orthonormality, the defining relation
   D(i)D(j) = ω(i,j)D(ij), the transposed-rotation action, and the reduction of
   a conventional k modulo the *true* reciprocal lattice on a centred lattice.

3. **The oracle**, spgrep (Shinohara; BSD-3), a dev-only dependency: every test
   using it carries ``_oracle`` in its name and ``importorskip``.  Irreps agree
   with an oracle only up to a unitary intertwiner, so what is compared is the
   character table — which is intertwiner-invariant — plus the dimensions and
   the Frobenius–Schur classes.

The magnetic-representation character used by tier 1 is written here rather
than imported: the decomposition rung owns the shipped version, and a test that
imported it would be checking the two halves against each other.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import gemmi
import numpy as np
import pytest

from rietx.crystallography.magnetic.irreps import (
    LittleGroup,
    as_kvector,
    canonical_kvector,
    equivalent_kvectors,
    factor_system,
    factor_system_exponents,
    inversion_character,
    inversion_parity,
    little_group,
    little_group_from_operations,
    primitive_basis,
    primitive_kvector,
    primitive_operations,
    small_irreps,
    small_irreps_of,
    star,
)

HALF = Fraction(1, 2)

#: Γ plus every zone-boundary point with all coordinates in {0, 1/2} — the set
#: the projective factor system lives on, in conventional coordinates.
ZONE_BOUNDARY_SET = tuple(
    tuple(map(Fraction, c)) for c in itertools.product([0, HALF], repeat=3)
)

#: k with denominators 3, 4 and 6, where the factor system is a higher root of
#: unity and −k need not be equivalent to k.
FRACTIONAL_K_SET = (
    (Fraction(1, 3), Fraction(1, 3), Fraction(0)),
    (Fraction(0), Fraction(0), Fraction(1, 3)),
    (Fraction(0), Fraction(0), Fraction(1, 4)),
    (Fraction(1, 4), Fraction(1, 4), Fraction(1, 4)),
    (Fraction(1, 2), Fraction(1, 4), Fraction(0)),
    (Fraction(1, 3), Fraction(0), HALF),
    (Fraction(1, 6), Fraction(1, 6), Fraction(0)),
)

#: The (space group, k) pairs spgrep 0.7.0 cannot answer, so the sweep can say
#: that the oracle declined rather than that the two disagreed.  Both are the
#: bcc P point of a group whose little co-group is 222 with a factor system of
#: order 4: the single two-dimensional projective irrep is what
#: ``test_a_bcc_p_point_has_one_two_dimensional_projective_irrep``
#: checks directly, without the oracle.
ORACLE_CANNOT_DO = frozenset({("I 21 21 21", (HALF, HALF, HALF)),
                              ("I b c a", (HALF, HALF, HALF))})

ALL_SETTINGS = tuple(gemmi.find_spacegroup_by_number(n).xhm() for n in range(1, 231))


# --------------------------------------------------------------------------
# the magnetic representation, for the positive arm only
# --------------------------------------------------------------------------

def site_orbit(rotations, translations, x0) -> list[tuple[Fraction, ...]]:
    """Exact orbit of a site under a coset-representative operation list."""
    pts: list[tuple[Fraction, ...]] = []
    for r, t in zip(rotations, translations):
        p = tuple(
            (sum(Fraction(int(r[a][b])) * x0[b] for b in range(3)) + t[a]) % 1 for a in range(3)
        )
        if p not in pts:
            pts.append(p)
    return pts


def magnetic_character(little: LittleGroup, atoms) -> np.ndarray:
    """χ of Γ_perm ⊗ Γ_axial on a site orbit (Bertaut, 1968, Acta Cryst. A24, 217).

    Only atoms an operation maps onto themselves contribute; each contributes
    det(R)·tr(R) — the axial-vector trace — times the return-vector phase
    exp(−2πi k·a), which is the same sign convention the irreps carry.
    """
    out = []
    for r, t in zip(little.rotations, little.translations):
        total = 0j
        det, trace = int(round(float(np.linalg.det(r)))), int(np.trace(r))
        for x in atoms:
            y = tuple(sum(Fraction(int(r[a][b])) * x[b] for b in range(3)) + t[a] for a in range(3))
            shift = tuple(y[a] - x[a] for a in range(3))
            if all(c.denominator == 1 for c in shift):
                phase = float(sum(kc * sc for kc, sc in zip(little.k, shift)))
                total += det * trace * np.exp(-2j * np.pi * phase)
        out.append(total)
    return np.array(out)


def multiplicities(little: LittleGroup, irreps, atoms) -> list[int]:
    """n_α = ⟨χ_α, χ_mag⟩ / |G_k/T|, as exact integers."""
    chi = magnetic_character(little, atoms)
    out = []
    for irrep in irreps:
        n = np.vdot(irrep.characters, chi) / little.order
        assert abs(n.imag) < 1e-9, f"multiplicity {n!r} is not real"
        assert abs(n.real - round(n.real)) < 1e-9, f"multiplicity {n!r} is not an integer"
        out.append(int(round(n.real)))
    return out


def pnma_case(site, k):
    """(little group, irreps, multiplicities, Σ n·dim) for a Pnma site orbit."""
    rots, trans = primitive_operations("P n m a")  # P lattice: the conventional ops
    atoms = site_orbit(rots, trans, tuple(map(Fraction, site)))
    little = little_group("P n m a", k)
    irreps = small_irreps_of(little)
    mult = multiplicities(little, irreps, atoms)
    total = sum(n * irrep.dimension for n, irrep in zip(mult, irreps))
    return little, irreps, mult, total, len(atoms)


# --------------------------------------------------------------------------
# 1. the measured positive arm
# --------------------------------------------------------------------------

def test_pnma_gamma_has_eight_one_dimensional_irreps_four_of_them_inversion_even():
    irreps = small_irreps("P n m a", (0, 0, 0))
    assert [x.dimension for x in irreps] == [1] * 8
    parities = [inversion_parity(x) for x in irreps]
    assert sorted(parities) == [-1] * 4 + [1] * 4


def test_bertaut_pnma_4b_at_gamma_gives_multiplicity_three_on_the_even_irreps():
    # ra_check.out, 2026-09-03: four even irreps at multiplicity 3, four odd at 0.
    _, irreps, mult, total, n_atoms = pnma_case((0, 0, HALF), (0, 0, 0))
    even = sorted(n for n, x in zip(mult, irreps) if inversion_parity(x) == 1)
    odd = sorted(n for n, x in zip(mult, irreps) if inversion_parity(x) == -1)
    assert even == [3, 3, 3, 3]
    assert odd == [0, 0, 0, 0]
    assert total == 3 * n_atoms == 12


def test_pnma_4c_at_gamma_is_the_control_that_brings_the_odd_irreps_in():
    # 4c is (x, 1/4, z): its site symmetry has no inversion, so the axial-vector
    # argument that empties the odd irreps on 4b does not apply.
    _, irreps, mult, total, n_atoms = pnma_case((Fraction(3, 100), Fraction(1, 4),
                                                 Fraction(99, 100)), (0, 0, 0))
    even = sorted(n for n, x in zip(mult, irreps) if inversion_parity(x) == 1)
    odd = sorted(n for n, x in zip(mult, irreps) if inversion_parity(x) == -1)
    assert even == [1, 1, 2, 2]
    assert odd == [1, 1, 2, 2]
    assert total == 3 * n_atoms == 12


def test_pnma_4b_at_the_zone_boundary_gives_two_two_dimensional_irreps():
    little, irreps, mult, total, n_atoms = pnma_case((0, 0, HALF), (0, 0, HALF))
    assert little.order == 8
    assert [x.dimension for x in irreps] == [2, 2]
    assert mult == [3, 3]
    assert total == 3 * n_atoms == 12


def test_the_zone_boundary_irreps_of_pnma_have_no_inversion_parity_at_all():
    """χ(−1) = 0 there, so "even" and "odd" are both wrong — see the report.

    ``ra_check.out`` records these two irreps as "odd under -1".  That line is a
    floating-point artefact: it was produced by ``chi.real > 0`` on a character
    whose true value is exactly zero, and a zero that lands at −3.9e-16 reads as
    negative.  The zero is forced, not accidental — with k = (0, 0, 1/2) the
    factor system gives ω(−1, g)/ω(g, −1) = −1 for g = ``-x+1/2,-y,z+1/2``, so
    D(−1) anticommutes with D(g) and its trace must vanish.  The axial-vector
    parity argument therefore has nothing to select on at this k.
    """
    little = little_group("P n m a", (0, 0, HALF))
    inv = little.inversion_index
    assert inv is not None and little.triplets[inv] == "-x,-y,-z"
    for irrep in small_irreps_of(little):
        assert abs(inversion_character(irrep)) < 1e-12
        assert inversion_parity(irrep) is None


# --------------------------------------------------------------------------
# 2. structure that must hold everywhere
# --------------------------------------------------------------------------

@pytest.mark.parametrize("k_set", [ZONE_BOUNDARY_SET, FRACTIONAL_K_SET],
                         ids=["zone-boundary", "denominators-3-4-6"])
def test_burnside_and_character_orthonormality_over_all_230_space_groups(k_set):
    """Σ dim² = |G_k/T| and ⟨χ_α, χ_β⟩ = |G_k/T|·δ_αβ, for every group and k.

    Both are properties of the ω-twisted group algebra and hold whatever the
    factor system is — which is exactly why they cannot replace the negative
    control below: a *wrong* factor system satisfies them too.
    """
    worst = 0.0
    pairs = 0
    for symbol in ALL_SETTINGS:
        for k in k_set:
            little = little_group(symbol, k)
            irreps = small_irreps_of(little)
            pairs += 1
            assert sum(x.dimension ** 2 for x in irreps) == little.order, (symbol, k)
            chars = np.array([x.characters for x in irreps])
            gram = chars.conj() @ chars.T / little.order
            worst = max(worst, float(np.max(np.abs(gram - np.eye(len(irreps))))))
    assert pairs == 230 * len(k_set)
    assert worst < 1e-10, f"character orthonormality off by {worst:.2e}"


def test_the_matrices_obey_the_factor_system_they_were_built_from():
    for symbol in ("P n m a", "P 6_3/m m c", "F d -3 m", "I a -3 d", "R -3 c"):
        for k in ZONE_BOUNDARY_SET:
            little = little_group(symbol, k)
            omega = factor_system(little)
            table = little.multiplication_table
            for irrep in small_irreps_of(little):
                d = irrep.matrices
                left = np.einsum("iab,jbc->ijac", d, d)
                right = omega[:, :, None, None] * d[table]
                assert np.allclose(left, right, atol=1e-8), (symbol, k, irrep.label)


def test_the_reciprocal_space_action_is_the_transposed_rotation():
    """Rᵀk ≡ k, not Rk ≡ k — and assert *which* operations, never how many.

    Two shapes of the same error.  P 3 at k = (1/3, 1/3, 0) changes the little
    group's *order* (3 under Rᵀ, 1 under R), which any count would catch.  P 3 1 2
    at k = (0, 1/2, 0) does not: both actions give order 2 and one-dimensional
    irreps either way, and only the identity of the second operation differs —
    ``-x+y,y,-z`` under Rᵀ against ``-y,-x,-z`` under R.  That is the case a
    dimension test passes and a decomposition gets wrong.
    """
    assert little_group("P 3", (Fraction(1, 3), Fraction(1, 3), 0)).order == 3
    little = little_group("P 3 1 2", (0, HALF, 0))
    assert little.triplets == ("x,y,z", "-x+y,y,-z")
    assert little.indices == (0, 4)


def test_a_centred_lattice_reduces_k_modulo_the_true_reciprocal_lattice():
    """F m -3 m at conventional (0, 0, 1) is X, not Γ.

    The reciprocal lattice of an F direct lattice is the body-centred
    sublattice of the integer hkl grid — all-even or all-odd — so (0, 0, 1) is
    not a reciprocal lattice vector and reducing it componentwise modulo 1
    would turn the X point into Γ: little group 48 instead of 16, star 1
    instead of 3, ten irreps of the wrong dimensions.
    """
    assert not equivalent_kvectors("F m -3 m", (0, 0, 1), (0, 0, 0))
    assert canonical_kvector("F m -3 m", (0, 0, 1)) == as_kvector((0, 0, 1))
    assert canonical_kvector("F m -3 m", (0, 0, 2)) == as_kvector((0, 0, 0))
    assert little_group("F m -3 m", (0, 0, 0)).order == 48
    assert little_group("F m -3 m", (0, 0, 1)).order == 16
    assert len(star("F m -3 m", (0, 0, 1))) == 3
    assert sorted(x.dimension for x in small_irreps("F m -3 m", (0, 0, 1))) == \
        [1, 1, 1, 1, 1, 1, 1, 1, 2, 2]
    # a P lattice has the whole integer grid, so there the same k *is* Γ
    assert equivalent_kvectors("P n m a", (0, 0, 1), (0, 0, 0))


@pytest.mark.parametrize("symbol", ["P n m a", "F m -3 m", "I 4/m m m", "R -3 c",
                                    "C 2/c", "A e m 2", "P 6_3/m m c"])
def test_star_size_times_little_group_order_is_the_point_group_order(symbol):
    n_point_group = len(gemmi.find_spacegroup_by_name(symbol).operations().sym_ops)
    for k in ZONE_BOUNDARY_SET + FRACTIONAL_K_SET:
        little = little_group(symbol, k)
        assert len(star(symbol, k)) * little.order == n_point_group, (symbol, k)


@pytest.mark.parametrize("symbol", ["P n m a", "F m -3 m", "I 4/m m m", "R -3 c", "C 2/c"])
def test_the_primitive_setting_describes_the_same_little_group(symbol):
    """The conventional and primitive doors answer the same question.

    ``primitive_operations`` plus k in the primitive reciprocal basis must give
    the same little-group order and the same irrep dimensions as the
    conventional entry point, or one of the two bases is being read wrong.
    """
    rotations, translations = primitive_operations(symbol)
    for k in ZONE_BOUNDARY_SET:
        conventional = little_group(symbol, k)
        primitive = little_group_from_operations(
            rotations, translations, primitive_kvector(symbol, k), centrings=())
        assert primitive.order == conventional.order, (symbol, k)
        assert primitive.indices == conventional.indices, (symbol, k)
        assert sorted(x.dimension for x in small_irreps_of(primitive)) == \
            sorted(x.dimension for x in small_irreps_of(conventional)), (symbol, k)


@pytest.mark.parametrize("symbol,n_lattice_points", [
    ("P n m a", 1), ("C 2/c", 2), ("I 4/m m m", 2), ("F m -3 m", 4),
    ("A e m 2", 2), ("R -3 c", 3),
])
def test_the_primitive_basis_has_the_determinant_the_centring_implies(symbol, n_lattice_points):
    """det M = 1/(lattice points per conventional cell), and its rows are in L.

    Both halves matter: a basis of the right determinant whose rows are not
    lattice vectors describes a different lattice, and rows in L with too large
    a determinant describe a sublattice.  Together they pin the primitive cell.
    """
    basis = primitive_basis(symbol)
    centrings = gemmi.find_spacegroup_by_name(symbol).operations().cen_ops
    assert len(centrings) == n_lattice_points
    matrix = np.array([[float(c) for c in row] for row in basis])
    assert np.isclose(np.linalg.det(matrix), 1.0 / n_lattice_points)
    lattice = [tuple(Fraction(int(c), gemmi.Op.DEN) for c in cen) for cen in centrings]
    for row in basis:
        assert any(all((x - c).denominator == 1 for x, c in zip(row, cen)) for cen in lattice)


def test_an_incommensurate_k_is_refused_by_name():
    with pytest.raises(ValueError, match="incommensurate"):
        as_kvector((0.3123, 0.0, 0.0))
    # a float that *is* a small rational is read exactly
    assert as_kvector((1 / 3, 0.5, 0)) == (Fraction(1, 3), HALF, Fraction(0))


# --------------------------------------------------------------------------
# 2b. the negative control on the factor system
# --------------------------------------------------------------------------

def test_dropping_the_factor_system_changes_the_irreps_at_a_zone_boundary():
    """The projective and the ordinary (linear) answers must differ, measurably.

    P n m a is non-symmorphic and k = (0, 0, 1/2) is on the zone boundary, so
    the factor system is not a coboundary: the little co-group mmm has eight
    one-dimensional *ordinary* irreps and exactly two two-dimensional
    *projective* ones.  This is the assertion that fails if someone
    "simplifies" ω away — and note the last two lines: Burnside's Σ dim² = 8
    holds for **both**, so the structural test above cannot catch it and this
    control is not redundant.
    """
    little = little_group("P n m a", (0, 0, HALF))
    exponents = factor_system_exponents(little)
    assert any(e != 0 for e in exponents.ravel()), "the factor system is trivial"
    assert set(exponents.ravel()) == {Fraction(0), HALF}

    projective = small_irreps_of(little)
    linear = small_irreps_of(little, factor=np.ones((little.order, little.order)))
    assert [x.dimension for x in projective] == [2, 2]
    assert [x.dimension for x in linear] == [1] * 8
    assert len(projective) != len(linear)
    assert sum(x.dimension ** 2 for x in projective) == little.order
    assert sum(x.dimension ** 2 for x in linear) == little.order


def test_the_factor_system_is_trivial_at_gamma():
    for symbol in ("P n m a", "F d -3 m", "P 6_3/m m c", "I a -3 d"):
        little = little_group(symbol, (0, 0, 0))
        assert np.allclose(factor_system(little), 1.0)


def test_a_bcc_p_point_has_one_two_dimensional_projective_irrep():
    """I 2_1 2_1 2_1 and I b c a at the bcc P point, checked without spgrep.

    The little co-group is 222 with a factor system that is not a coboundary,
    so the four ordinary one-dimensional irreps collapse into a single
    two-dimensional projective one with χ = (2, 0, 0, 0) and Σ dim² = 4 =
    |G_k/T| (Bradley & Cracknell, 1972, ch. 4; the central extension is the
    quaternion group in the primitive gauge).  These are also the only two
    cases spgrep 0.7.0 raises on, so this is the arm that keeps them covered —
    if a later spgrep answers them, ``ORACLE_CANNOT_DO`` shrinks and the sweep
    below says so.

    The factor-system *exponents* are gauge-dependent — {0, 1/2} on gemmi's
    conventional coset representatives, {0, 1/4, 3/4} on the primitive ones —
    so what is asserted is the gauge-invariant answer, in both settings.
    """
    for symbol in ("I 21 21 21", "I b c a"):
        conventional = little_group(symbol, (HALF, HALF, HALF))
        primitive = little_group_from_operations(
            *primitive_operations(symbol),
            primitive_kvector(symbol, (HALF, HALF, HALF)), centrings=())
        for little in (conventional, primitive):
            assert little.order == 4
            assert any(e != 0 for e in factor_system_exponents(little).ravel())
            irreps = small_irreps_of(little)
            assert [x.dimension for x in irreps] == [2]
            assert np.allclose(irreps[0].characters, [2, 0, 0, 0], atol=1e-8)
            assert sum(x.dimension ** 2 for x in irreps) == little.order
            # the ordinary representations of the same point group are four 1-D
            linear = small_irreps_of(little, factor=np.ones((little.order,) * 2))
            assert [x.dimension for x in linear] == [1, 1, 1, 1]
            # 2k is not a vector of the I lattice's reciprocal lattice, so −k is
            # not equivalent to k and the small irrep cannot be real
            assert not little.has_minus_k
            assert irreps[0].reality == "complex"


def test_the_frobenius_schur_class_agrees_with_the_character_it_implies():
    """A real or pseudoreal irrep has a real character; a complex one need not.

    Self-consistency of the indicator against the definition it comes from,
    over every group at the zone-boundary set.  The cross-check against an
    independent construction is the physically-irreducible oracle test below.
    """
    seen = set()
    for symbol in ALL_SETTINGS:
        for k in ZONE_BOUNDARY_SET:
            little = little_group(symbol, k)
            for irrep in small_irreps_of(little):
                seen.add(irrep.reality)
                if irrep.reality in ("real", "pseudoreal"):
                    assert little.has_minus_k
                    assert np.max(np.abs(irrep.characters.imag)) < 1e-8
                    assert irrep.frobenius_schur == (1 if irrep.reality == "real" else -1)
                else:
                    assert irrep.frobenius_schur == 0
    assert seen == {"real", "pseudoreal", "complex"}


# --------------------------------------------------------------------------
# 3. the spgrep oracle (dev-only; every name carries _oracle)
# --------------------------------------------------------------------------

def oracle_irreps(symbol, k):
    """spgrep's small irreps and this module's, on the *same* operation list."""
    spgrep_core = pytest.importorskip("spgrep")
    rotations, translations = primitive_operations(symbol)
    k_primitive = primitive_kvector(symbol, k)
    little = little_group_from_operations(rotations, translations, k_primitive, centrings=())
    theirs, mapping = spgrep_core.get_spacegroup_irreps_from_primitive_symmetry(
        rotations,
        np.array([[float(c) for c in t] for t in translations]),
        np.array([float(c) for c in k_primitive]),
    )
    assert list(mapping) == list(little.indices), (symbol, k)
    return little, small_irreps_of(little), theirs


def character_table(characters):
    """A character table as a sorted tuple of rows, for order-free comparison."""
    return tuple(sorted(tuple(np.round(c, 6) + 0.0 for c in row) for row in characters))


def tables_agree(mine, theirs, atol=1e-6):
    a = character_table([x.characters for x in mine])
    b = character_table([np.einsum("gii->g", d) for d in theirs])
    return len(a) == len(b) and all(
        np.allclose(np.array(u), np.array(v), atol=atol) for u, v in zip(a, b))


def test_the_spgrep_oracle_uses_the_same_translation_convention_oracle():
    """spgrep's own matrices must satisfy *this module's* factor system.

    The oracle is only an oracle if the two agree on D({E|a}) = exp(−2πi k·a)
    and on which coset representative each matrix belongs to.  Both are settled
    here rather than assumed: a sign flip in the exponent, or a different gauge,
    would break this identity while leaving every dimension count intact.
    """
    for symbol, k in [("P n m a", (0, 0, HALF)), ("P 6_3/m m c", (0, 0, HALF)),
                      ("F d -3 m", (0, 0, 1)), ("R -3 c", (0, 0, HALF))]:
        little, _, theirs = oracle_irreps(symbol, k)
        omega = factor_system(little)
        table = little.multiplication_table
        for d in theirs:
            left = np.einsum("iab,jbc->ijac", d, d)
            right = omega[:, :, None, None] * d[table]
            assert np.allclose(left, right, atol=1e-8), (symbol, k)


@pytest.mark.parametrize("k", [(0, 0, 0), (0, 0, HALF)], ids=["gamma", "zone-boundary"])
def test_pnma_characters_agree_with_the_spgrep_oracle(k):
    little, mine, theirs = oracle_irreps("P n m a", k)
    assert tables_agree(mine, theirs)
    assert sorted(x.dimension for x in mine) == sorted(d.shape[1] for d in theirs)


@pytest.mark.parametrize("symbol", ["F m -3 m", "F d -3 m", "I 4/m m m", "R -3 c",
                                    "C 2/c", "A e m 2", "I a -3 d"])
def test_centred_lattices_agree_with_the_spgrep_oracle(symbol):
    """The centred half of "what would make this wrong", against the oracle.

    k is handed in conventional coordinates and converted here; spgrep sees the
    primitive operations and the primitive k.  A confusion of the two bases
    changes the little group, so agreement on the *order* is as load-bearing as
    agreement on the characters.
    """
    for k in ZONE_BOUNDARY_SET + ((0, 0, 1),):
        little, mine, theirs = oracle_irreps(symbol, k)
        assert little.order == len(theirs[0]), (symbol, k)
        assert tables_agree(mine, theirs), (symbol, k)


def test_character_tables_agree_with_the_spgrep_oracle_for_all_230_groups():
    """The sweep: 230 settings × the {0, 1/2}³ k set, characters compared exactly.

    Counts are asserted, not just the absence of a failure, so a silently
    shrinking sweep fails.  ``ORACLE_CANNOT_DO`` names the pairs spgrep 0.7.0
    raises on; those are asserted to still raise, so the day the oracle grows
    they are noticed rather than skipped forever.
    """
    spgrep_core = pytest.importorskip("spgrep")
    checked = agreed = declined = 0
    for symbol in ALL_SETTINGS:
        for k in ZONE_BOUNDARY_SET:
            if (symbol, k) in ORACLE_CANNOT_DO:
                with pytest.raises(ValueError):
                    oracle_irreps(symbol, k)
                declined += 1
                continue
            _, mine, theirs = oracle_irreps(symbol, k)
            checked += 1
            agreed += bool(tables_agree(mine, theirs))
    assert (checked, agreed, declined) == (1838, 1838, 2)
    assert spgrep_core.__name__ == "spgrep"


@pytest.mark.slow
def test_character_tables_agree_with_the_spgrep_oracle_at_higher_denominators():
    """The same sweep at k with denominators 3, 4 and 6 — 1610 more pairs."""
    pytest.importorskip("spgrep")
    checked = agreed = 0
    for symbol in ALL_SETTINGS:
        for k in FRACTIONAL_K_SET:
            _, mine, theirs = oracle_irreps(symbol, k)
            checked += 1
            agreed += bool(tables_agree(mine, theirs))
    assert (checked, agreed) == (1610, 1610)


@pytest.mark.slow
def test_physically_irreducible_dimensions_agree_with_the_spgrep_oracle():
    """The Frobenius–Schur classes, checked against an independent construction.

    A real small irrep stays dimension d over the reals; a pseudoreal one
    doubles; a complex one pairs with its conjugate and the *pair* gives one
    real representation of dimension 2d.  spgrep's ``real=True`` builds those
    directly, so comparing dimensions tests the indicator without ever asking
    spgrep for it.  Restricted to 2k ≡ 0, where the pairing stays inside G_k;
    spgrep declines a further set of cases on its own, which are counted.
    """
    spgrep_core = pytest.importorskip("spgrep")
    checked = agreed = declined = 0
    for symbol in ALL_SETTINGS:
        rotations, translations = primitive_operations(symbol)
        floats = np.array([[float(c) for c in t] for t in translations])
        for k in ZONE_BOUNDARY_SET:
            k_primitive = primitive_kvector(symbol, k)
            little = little_group_from_operations(
                rotations, translations, k_primitive, centrings=())
            if not little.has_minus_k:
                continue
            try:
                mine = small_irreps_of(little)
                real, _ = spgrep_core.get_spacegroup_irreps_from_primitive_symmetry(
                    rotations, floats, np.array([float(c) for c in k_primitive]), real=True)
            except (AssertionError, ValueError):
                declined += 1
                continue
            checked += 1
            agreed += bool(sorted(d.shape[1] for d in real) == _real_dimensions(mine))
    assert (checked, agreed) == (1363, 1363)
    assert declined == 114


def _real_dimensions(irreps) -> list[int]:
    """Dimensions of the physically irreducible reps implied by the FS classes."""
    remaining = list(irreps)
    out: list[int] = []
    while remaining:
        irrep = remaining.pop(0)
        if irrep.reality == "real":
            out.append(irrep.dimension)
            continue
        if irrep.reality == "complex":  # consume the conjugate partner
            for j, other in enumerate(remaining):
                if other.dimension == irrep.dimension and np.allclose(
                        other.characters, irrep.characters.conj(), atol=1e-6):
                    remaining.pop(j)
                    break
        out.append(2 * irrep.dimension)
    return sorted(out)
