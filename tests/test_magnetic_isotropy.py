"""Isotropy subgroups, candidate magnetic models, and the powder equivalence classes.

The module under test derives everything from the parent group, the site and k;
nothing here is a table lookup, so every fixture is either a *published* answer
(a magnetic space group somebody measured) or a *derived* one (a statement that
follows from the definitions and can be checked without any table).

Provenance of the published rows, and what it is worth
------------------------------------------------------
Each row of :data:`PUBLISHED` states a parent space group, a propagation vector,
a magnetic site and the magnetic space group the structure was published in.
The moment components are transcribed as numbers and cited to the paper that
measured them; the MAGNDATA entry (Gallego et al., 2016, *J. Appl. Cryst.* **49**,
1750) is named only as the record the transcription was checked against, never as
the source of a number.  Four rows — LaMnO₃, Mn₃O₄, NiO and Sr₂IrO₄, plus
YBa₂Cu₃O₆₊ₐ and Ca₃Co₂₋ₓMnₓO₆ — had their *parent group, k and site* read from
the MAGNDATA record on 2026-09-06 (the entry index is in the row); the rest are
the parent everybody states for that structure, and the test is what checks them:
a wrong parent or a wrong k does not produce the published magnetic space group,
so those rows fail loudly rather than passing quietly.

The magnetic space-group numbers of arm A are **derived**, not quoted.  What
they were checked against is written at the test.
"""

from fractions import Fraction

import numpy as np
import pytest

from rietx.crystallography.magnetic import irreps, isotropy, modes
from rietx.crystallography.magnetic.operators import (
    MagneticGroup,
    MagneticOperator,
    allowed_displacement_basis,
    allowed_moment_basis,
    identify,
    in_span,
)

GAMMA = (Fraction(0), Fraction(0), Fraction(0))
HALF = (Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def published_direction(space_group, cell, crystalaxis_moment):
    """A published magCIF ``crystalaxis`` moment as this module's components.

    magCIF states a moment on *unit* vectors along a, b and c (M-5, decision
    D-3); this module carries contravariant components on the cell vectors, so
    the conversion divides by the axis lengths and then carries the result into
    the magnetic cell with P⁻¹.  The axis lengths come from the group's own
    compatible cell, which ties together exactly the axes the setting ties
    together — so the *direction* is well defined without the real cell whenever
    the published components mix only symmetry-equivalent axes, which is the
    case for every row here.
    """
    lengths = np.linalg.norm(isotropy.compatible_cell(space_group), axis=1)
    return cell.to_magnetic(np.asarray(crystalaxis_moment, dtype=float) / lengths)


def atom_of_site(candidate, site):
    """Index of the magnetic-cell atom that is the given parent site itself."""
    target = candidate.cell.to_magnetic(np.asarray(site, dtype=float)) % 1.0
    delta = np.abs(candidate.positions - target)
    hits = np.flatnonzero(np.all(np.minimum(delta, 1.0 - delta) < 1e-4, axis=1))
    assert hits.size == 1, f"{hits.size} atoms match the site {site}"
    return int(hits[0])


def moment_in_family(candidate, atom, moment, atol=1e-5):
    """Whether the candidate's family can carry ``moment`` on that atom."""
    basis = np.array([configuration[atom] for configuration in candidate.configurations])
    return in_span(basis, moment, atol=atol)


def sign_pattern(positions, rules, tol=1e-6):
    """±1 per atom fixed by "atoms differing by v are (anti)parallel", or None.

    ``rules`` is a list of (lattice-fractional vector, ±1).  This is how the
    Wollan–Koehler perovskite *types* are defined — A-type is ferromagnetic
    sheets stacked antiferromagnetically, G-type is every nearest neighbour
    antiparallel — and stating them as neighbour relations rather than as a sign
    string over an atom list is what keeps the test free of the Bertaut
    mode-letter convention, whose atom numbering is a separate question (M-6(b),
    D-H).
    """
    signs: list[int | None] = [None] * len(positions)
    signs[0] = 1
    stack = [0]
    while stack:
        i = stack.pop()
        for vector, flip in rules:
            for direction in (1, -1):
                target = (positions[i] + direction * np.asarray(vector, float)) % 1.0
                delta = np.abs(positions - target)
                for j in np.flatnonzero(np.all(np.minimum(delta, 1.0 - delta) < tol, axis=1)):
                    if signs[j] is None:
                        signs[j] = flip * signs[i]
                        stack.append(int(j))
                    elif signs[j] != flip * signs[i]:
                        return None
    if any(s is None for s in signs):
        return None
    return np.array(signs, dtype=float)


def families_containing(candidate_set, configuration, atol=1e-6):
    """Which candidates can produce a given whole-cell moment pattern."""
    out = []
    for index, candidate in enumerate(candidate_set):
        rows = candidate.configurations.reshape(candidate.free_amplitudes, -1)
        flat = np.asarray(configuration, dtype=float).reshape(-1)
        coefficients, *_ = np.linalg.lstsq(rows.T, flat, rcond=None)
        if np.allclose(rows.T @ coefficients, flat, atol=atol):
            out.append(index)
    return out


# --------------------------------------------------------------------------
# A. LaMnO3 / Pnma at the zone centre
# --------------------------------------------------------------------------

#: The four magnetic space groups this module derives for Pnma at Γ.  They are
#: **derived**, and what they were checked against is:
#:
#: * 62.448 is the magnetic space group of LaMnO₃ (MAGNDATA #0.642, read
#:   2026-09-06: parent Pnma, k = (0,0,0), Mn1 at 4a (0,0,0), M = (3.7, 0, 0)
#:   μ_B, Elemans, van Laar, van der Veen & Loopstra, 1971, *J. Solid State
#:   Chem.* **3**, 238), and the test below shows the candidate carrying that
#:   number is the one whose family holds LaMnO₃'s A-type arrangement.
#: * 62.441 is the unprimed Pnma, and the candidate carrying it is the one whose
#:   family holds the G-type arrangement — which is the assignment stated for
#:   B-site G-type order in Pnma perovskites in the secondary literature.
#: * The remaining two are the other two inversion-even irreps' subgroups.
#:
#: The Bilbao MAXMAGN and MAGNEXT CGI endpoints were **not reachable** on
#: 2026-09-06 (404 and HTTP 500 on the URLs tried), so the four-number list is
#: not corroborated against a printed table; it is corroborated against one
#: published member, one secondary statement, and the internal consistency of
#: the whole engine (arm D).
PNMA_GAMMA_BNS = {"62.441", "62.446", "62.447", "62.448"}


@pytest.mark.parametrize("site", [(0.0, 0.0, 0.0), (0.0, 0.0, 0.5)])
def test_pnma_at_gamma_has_exactly_four_maximal_magnetic_subgroups(site):
    """One per inversion-even irrep, each one-dimensional, each of order 8."""
    found = isotropy.candidates("P n m a", site, GAMMA)
    assert len(found) == 4
    assert {candidate.bns_number for candidate in found} == PNMA_GAMMA_BNS
    for candidate in found:
        assert candidate.group.order == 8
        assert candidate.direction.rank == 1
        assert candidate.direction.conjugates == 1
        assert candidate.free_amplitudes == 3          # n_nu = 3 copies, d_nu = 1
        assert candidate.cell.transform == "a,b,c;0,0,0"
        assert not candidate.cell.doubled
        assert candidate.msg_type in (1, 3)            # never IV: k = 0


def test_only_the_inversion_even_irreps_of_pnma_carry_a_moment():
    """The axial-vector parity argument, on the group where it still works."""
    representation = modes.magnetic_representation("P n m a", (0, 0, 0), GAMMA)
    small = irreps.small_irreps("P n m a", GAMMA)
    active, inactive = [], []
    for irrep, multiplicity in zip(small, modes.decompose(representation, small).multiplicities):
        (active if multiplicity else inactive).append(irrep)
    assert len(active) == 4 and len(inactive) == 4
    assert all(irreps.inversion_parity(irrep) == 1 for irrep in active)
    assert all(irreps.inversion_parity(irrep) == -1 for irrep in inactive)


@pytest.mark.parametrize("site", [(0.0, 0.0, 0.0), (0.0, 0.0, 0.5)])
def test_the_a_type_arrangement_of_lamno3_is_the_62_448_candidate(site):
    """Ferromagnetic sheets perpendicular to b, moment along a — and only that one.

    LaMnO₃ orders A-type with the Mn moment along **a** of Pnma; MAGNDATA
    #0.642 records the magnetic space group as BNS 62.448 and the moment as
    (3.7, 0, 0) μ_B (Elemans et al., 1971, *J. Solid State Chem.* **3**, 238).
    The arrangement is built here from the orbit's own geometry — the sheets are
    defined by which lattice vector flips the sign — so no mode-letter
    convention enters.
    """
    found = isotropy.candidates("P n m a", site, GAMMA)
    positions = found.candidates[0].positions
    signs = sign_pattern(positions, [((0, 0.5, 0), -1), ((0.5, 0, 0.5), +1)])
    assert signs is not None
    configuration = signs[:, None] * np.array([1.0, 0.0, 0.0])
    members = families_containing(found, configuration)
    assert len(members) == 1
    assert found[members[0]].bns_number == "62.448"


@pytest.mark.parametrize("site", [(0.0, 0.0, 0.0), (0.0, 0.0, 0.5)])
def test_the_g_type_arrangement_is_the_unprimed_62_441_candidate(site):
    """Every pseudo-cubic neighbour antiparallel, moment along a."""
    found = isotropy.candidates("P n m a", site, GAMMA)
    positions = found.candidates[0].positions
    signs = sign_pattern(positions, [((0, 0.5, 0), -1), ((0.5, 0, 0.5), -1)])
    assert signs is not None
    configuration = signs[:, None] * np.array([1.0, 0.0, 0.0])
    members = families_containing(found, configuration)
    assert len(members) == 1
    assert found[members[0]].bns_number == "62.441"
    assert found[members[0]].msg_type == 1


def test_the_four_pnma_candidates_are_told_apart_by_a_powder():
    """Four irreps, four classes — the case where representation analysis is decisive."""
    found = isotropy.analyse(isotropy.candidates("P n m a", (0, 0, 0), GAMMA), d_min=1.5)
    assert len(found.classes) == 4
    assert len(set(found.absences)) == 4     # and they differ in their absences too


# --------------------------------------------------------------------------
# B. Ten published (parent, k) pairs
# --------------------------------------------------------------------------

#: (label, parent, site in the parent setting, k, published BNS number,
#:  published moment in magCIF crystalaxis components, citation, record).
PUBLISHED = [
    ("LaMnO3", "P n m a", (0, 0, 0), GAMMA, "62.448", (3.7, 0.0, 0.0),
     "Elemans, van Laar, van der Veen & Loopstra (1971), "
     "J. Solid State Chem. 3, 238-242", "MAGNDATA #0.642 (parent/k/site read 2026-09-06)"),
    ("MnF2", "P 4_2/m n m", (0, 0, 0), GAMMA, "136.499", (0.0, 0.0, 4.6),
     "Yamani, Tun & Ryan (2010), Can. J. Phys. 88, 771-797", "MAGNDATA #0.15"),
    ("Cr2O3", "R -3 c", (0, 0, 0.3476), GAMMA, "167.106", (0.0, 0.0, 2.48),
     "Brown, Forsyth, Lelievre-Berna & Tasset (2002), "
     "J. Phys.: Condens. Matter 14, 1957-1966", "MAGNDATA #0.59"),
    ("GdB4", "P 4/m b m", (0.31746, 0.81746, 0), GAMMA, "127.395", (5.05, 5.05, 0.0),
     "Blanco, Brown, Stunault, Katsumata, Iga & Michimura (2006), "
     "Phys. Rev. B 73, 212411", "MAGNDATA #0.9"),
    ("YMnO3", "P 6_3 c m", (0.32080, 0, 0), GAMMA, "185.197", (1.68, 3.36, 0.0),
     "Munoz, Alonso, Martinez-Lope, Casais, Martinez & Fernandez-Diaz (2000), "
     "Phys. Rev. B 62, 9498-9510", "MAGNDATA #0.6"),
    ("ScMnO3-P63cm", "P 6_3 c m", (0.33160, 0, 0), GAMMA, "185.201", (-3.03, 0.0, 0.0),
     "Munoz, Alonso, Martinez-Lope, Casais, Martinez & Fernandez-Diaz (2000), "
     "Phys. Rev. B 62, 9498-9510", "MAGNDATA #0.7"),
    ("ScMnO3-P63", "P 6_3", (0.33160, 0, 0), GAMMA, "173.129", (3.74, 3.31, 0.0),
     "Munoz, Alonso, Martinez-Lope, Casais, Martinez & Fernandez-Diaz (2000), "
     "Phys. Rev. B 62, 9498-9510", "MAGNDATA #0.8"),
    ("Cd2Os2O7", "F d -3 m:2", (0, 0, 0), GAMMA, "227.131", (0.6, 0.6, 0.6),
     "Yamaura, Ohgushi, Ohsumi, Hasegawa, Yamauchi, Sugimoto, Takeshita, "
     "Tokuda, Takata, Udagawa, Takigawa, Harima, Arima & Hiroi (2012), "
     "Phys. Rev. Lett. 108, 247205", "MAGNDATA #0.2"),
    ("Gd5Ge4", "P n m a", (0.2927, 0.25, 0.0022), GAMMA, "62.444", (0.0, 0.0, 1.0),
     "Tan, Kreyssig, Kim, Goldman, McQueeney, Wermeille, Sieve, Lograsso, "
     "Schlagel, Budko, Pecharsky & Gschneidner (2005), Phys. Rev. B 71, 214408",
     "MAGNDATA #0.14"),
    ("EuTiO3", "I 4/m c m", (0, 0.5, 0.25), GAMMA, "69.523", (-4.9, -4.9, 0.0),
     "Scagnoli, Allieta, Walker, Scavini, Katsufuji, Sagarna, Zaharko & "
     "Mazzoli (2012), Phys. Rev. B 86, 094432", "MAGNDATA #0.16"),
    # the four type IV rows: k != 0, 2k in the reciprocal lattice
    ("NiO", "F m -3 m", (0, 0, 0), HALF, "15.90", (1.0, 1.0, -2.0),
     "Ressouche, Kernavanois, Regnault & Henry (2006), Physica B 385-386, 394-397",
     "MAGNDATA #1.6 (parent/k/site read 2026-09-06)"),
    ("Mn3O4", "P b c m", (0.308, 0.114, 0.07), (Fraction(1, 2), Fraction(0), Fraction(0)),
     "62.452", (3.49, 0.0, 0.0),
     "Hirai, Sanchez-Benitez, Attfield et al. (2013), Phys. Rev. B 87, 014417",
     "MAGNDATA #1.1 (parent Pbcm, k = (1/2,0,0), read 2026-09-06)"),
    ("Sr2IrO4", "I 4_1/a c d", (0, 0.25, 0.375), (Fraction(1), Fraction(1), Fraction(1)),
     "54.352", (-0.24, 0.0, 0.0),
     "Lovesey, Khalyavin, Manuel, Chapon, Cao & Qi (2012), "
     "J. Phys.: Condens. Matter 24, 496003",
     "MAGNDATA #1.3 (parent I4_1/acd, k = (1,1,1), read 2026-09-06)"),
    ("YBa2Cu3O6+a", "P 4/m m m", (0, 0, 0.180515), HALF, "69.526", (0.47, 0.0, 0.0),
     "Shamoto, Sato, Tranquada, Sternlieb & Shirane (1993), "
     "Phys. Rev. B 48, 13817-13825",
     "MAGNDATA #1.5 (parent P4/mmm, k = (1/2,1/2,1/2), read 2026-09-06)"),
]

#: Rows whose parent is trigonal or hexagonal.  M-5 measured that R and Rᵀ give a
#: different allowed moment span **only** in space groups 149-194, so a fixture
#: set without these proves nothing about the symmetry action.
HEXAGONAL_ROWS = {"Cr2O3", "YMnO3", "ScMnO3-P63cm", "ScMnO3-P63"}


@pytest.mark.parametrize("row", PUBLISHED, ids=[row[0] for row in PUBLISHED])
def test_the_published_magnetic_group_is_in_the_candidate_list(row):
    """With an irrep label, and with the published moment inside its family."""
    label, group, site, k, bns, moment, _citation, _record = row
    found = isotropy.candidates(group, site, k)
    matches = [candidate for candidate in found if candidate.bns_number == bns]
    assert matches, (f"{label}: {bns} is not among {sorted({c.bns_number for c in found})}")
    direction = published_direction(group, found.cell, moment)
    carried = [candidate for candidate in matches
               if moment_in_family(candidate, atom_of_site(candidate, site), direction)]
    assert carried, (f"{label}: {bns} is a candidate but none of the "
                     f"{len(matches)} candidates carrying it can hold the published moment")
    assert all(candidate.irrep_label for candidate in carried)


def test_the_published_set_covers_what_it_has_to():
    """Ten pairs, two crystal systems that can catch a wrong axial action, type IV."""
    assert len(PUBLISHED) >= 10
    assert len(HEXAGONAL_ROWS) >= 2
    labels = {row[0] for row in PUBLISHED}
    assert HEXAGONAL_ROWS <= labels
    assert "Mn3O4" in labels                             # type IV, anti-translation
    assert sum(1 for row in PUBLISHED if row[3] != GAMMA) == 4


@pytest.mark.parametrize("row", [row for row in PUBLISHED if row[3] != GAMMA],
                         ids=[row[0] for row in PUBLISHED if row[3] != GAMMA])
def test_a_non_zero_k_gives_a_type_iv_group_with_an_anti_translation(row):
    """Derived, not quoted: 2k ∈ L* and k ≠ 0 forces exactly one anti-translation coset."""
    label, group, site, k, bns, *_ = row
    found = isotropy.candidates(group, site, k)
    assert found.cell.doubled
    assert sum(1 for _, eps in found.cell.translations if eps < 0) == 1
    for candidate in found:
        assert candidate.msg_type == 4, f"{label}: {candidate.label} is type {candidate.msg_type}"
        assert any(op.time_reversal < 0 for op in candidate.group.centerings)


@pytest.mark.parametrize("row", [row for row in PUBLISHED if row[3] == GAMMA],
                         ids=[row[0] for row in PUBLISHED if row[3] == GAMMA])
def test_k_zero_never_gives_a_type_iv_group(row):
    """The other half of the same statement: at k = 0 every translation is unprimed."""
    _label, group, site, k, *_ = row
    found = isotropy.candidates(group, site, k)
    assert not found.cell.doubled
    assert all(candidate.msg_type in (1, 3) for candidate in found)


def test_a_multi_irrep_structure_is_not_a_single_irrep_candidate():
    """Ca₃Co₂₋ₓMnₓO₆ is the intersection of two candidates, and that is the fence.

    MAGNDATA #0.13 (read 2026-09-06) records parent R-3c, k = (0,0,0), BNS
    161.69 (R3c), with Mn at (0,0,0) and Co at (0,0,¼) both ordered along c
    (Choi, Yi, Lee, Huang, Kiryukhin & Cheong, 2008, *Phys. Rev. Lett.* **100**,
    047601).  161.69 is **not** a single-irrep isotropy subgroup of R-3c at Γ on
    either site — it cannot be, because a one-dimensional irrep always admits one
    of the two time-reversal signs for every operation, so the operation is never
    simply absent.  It is the intersection of the two sites' candidates, which is
    what a coupled two-irrep structure means.  This test states the fence rather
    than pretending the entry is out of reach.
    """
    mn = isotropy.candidates("R -3 c", (0, 0, 0), GAMMA)
    co = isotropy.candidates("R -3 c", (0, 0, 0.25), GAMMA)
    assert "161.69" not in {candidate.bns_number for candidate in mn}
    assert "161.69" not in {candidate.bns_number for candidate in co}
    intersections = set()
    for first in mn:
        for second in co:
            common = set(first.group.all_operations()) & set(second.group.all_operations())
            try:
                merged = identify(MagneticGroup.from_operations(common), lattice=mn.lattice)
            except ValueError:
                continue
            intersections.add(merged.bns_number)
    assert "161.69" in intersections


# --------------------------------------------------------------------------
# C. Shirane's rule, and the uniaxial case where it stops
# --------------------------------------------------------------------------

def test_a_cubic_collinear_site_gives_one_powder_equivalence_class():
    """Shirane (1959) made mechanical: the moment direction is not measurable.

    F m -3 m, site 4a, k = 0: the axial vector representation is one
    three-dimensional irrep, its isotropy subgroups are the [100], [110], [111]
    families and the planes and the general direction, and a powder pattern
    cannot tell any of them apart.  The Jacobian rank says the same thing a
    second way: whatever the family's dimension, a powder determines exactly one
    amplitude — the magnitude.
    """
    found = isotropy.analyse(isotropy.candidates("F m -3 m", (0, 0, 0), GAMMA), d_min=2.0)
    assert {candidate.irrep_label for candidate in found} == {found[0].irrep_label}
    assert len(found.classes) == 1
    assert len(found.classes[0]) == len(found)
    assert sorted(candidate.free_amplitudes for candidate in found) == [1, 1, 1, 2, 2, 3]
    assert set(found.determinable) == {1}
    assert {candidate.bns_number for candidate in found} >= {"139.537", "166.101", "71.536"}
    # the certificates' negative arm: the six spans coincide to 1e-14, and a
    # certificate that fired on that round-off would split Shirane's case
    assert found.relations and not any(v.status == "proved-not" for v in found.relations)


def test_a_tetragonal_parent_splits_the_same_three_directions():
    """The negative arm: a uniaxial parent measures the angle to c."""
    found = isotropy.analyse(isotropy.candidates("P 4/m m m", (0, 0, 0), GAMMA), d_min=2.0)
    assert len(found.classes) >= 2
    along_c = [i for i, candidate in enumerate(found)
               if candidate.bns_number == "123.345"]
    assert len(along_c) == 1
    in_plane = [i for i, candidate in enumerate(found) if i not in along_c]
    assert in_plane
    assert all(found.class_of(i) != found.class_of(along_c[0]) for i in in_plane)


def test_the_cubic_and_tetragonal_arms_differ_for_the_reason_claimed():
    """Both arms, side by side, so a change that flattens one is visible."""
    cubic = isotropy.analyse(isotropy.candidates("F m -3 m", (0, 0, 0), GAMMA), d_min=2.0)
    tetragonal = isotropy.analyse(isotropy.candidates("P 4/m m m", (0, 0, 0), GAMMA),
                                  d_min=2.0)
    assert len(cubic.classes) == 1 and len(tetragonal.classes) >= 2


# --------------------------------------------------------------------------
# C′. The frame M⊥ is taken in, on the k ≠ 0 cells that are not axis-aligned
# --------------------------------------------------------------------------
# Every case above is at Γ or on an axis-aligned child cell, where the Cholesky
# frame of the cell parameters and the lattice's own frame coincide; issue #534
# was invisible there.  The MnO-type child cell of F m -3 m at (½, ½, ½) is
# rotated by 140° against the parent axes and the G-type P m -3 m one is
# left-handed, so these are the cases that see which frame ĥ and m share.

def _rotation(axis, angle):
    """Rodrigues' rotation matrix about ``axis`` by ``angle`` radians."""
    u = np.asarray(axis, dtype=np.float64) / np.linalg.norm(axis)
    k = np.array([[0.0, -u[2], u[1]], [u[2], 0.0, -u[0]], [-u[1], u[0], 0.0]])
    return np.eye(3) + np.sin(angle) * k + (1.0 - np.cos(angle)) * (k @ k)


#: One proper rotation and one improper map (the same rotation times a mirror),
#: so a left-handed re-expression of the same crystal is covered too.
RIGID_MAPS = {"rotation": _rotation((1, 2, 3), 0.7),
              "rotoreflection": _rotation((1, 2, 3), 0.7) @ np.diag([1.0, 1.0, -1.0])}


def _unit_intensity(candidate, refl):
    """Per-reflection Σ_dom |M⊥|² at every amplitude one."""
    f = isotropy.structure_factors(candidate, refl)
    total = np.tensordot(np.ones(candidate.free_amplitudes), f, axes=(0, 1))
    return np.sum(np.abs(total) ** 2, axis=(0, 2))


def _is_along(moments, direction):
    """Every non-zero Cartesian moment of the configuration is parallel to ``direction``."""
    u = np.asarray(direction, dtype=np.float64) / np.linalg.norm(direction)
    live = moments[np.linalg.norm(moments, axis=1) > 1e-9]
    return live.size > 0 and np.allclose(np.abs(live @ u), np.linalg.norm(live, axis=1))


def test_the_mno_type_cell_splits_the_111_moment_from_the_in_plane_ones():
    """Shirane's own example: MnO, F m -3 m 4a at k = (½, ½, ½), gives two classes.

    The configurational symmetry is rhombohedral, so the angle a collinear
    moment makes with [111] is measurable and its azimuth is not (Shirane,
    1959, *Acta Cryst.* **12**, 282, p. 285): the τ₃ candidate with m ∥ [111]
    is one class and the three in-plane candidates are the other.  And the
    (½ ½ ½) reflection, the magnetic cell's first, vanishes for m ∥ [111]
    because there M ∥ Q — the reflection Roth (1958, *Phys. Rev.* **110**,
    1333) used to put MnO's moments in the (111) planes.  On main before #534
    the moment and ĥ were in frames 140° apart and all four candidates came out
    one class, with 1.1e2 at (½ ½ ½) for the [111] one.
    """
    found = isotropy.candidates("F m -3 m", (0, 0, 0), HALF)
    lattice = np.asarray(found.lattice, dtype=np.float64)
    refl = isotropy.reflections(lattice, 1.5)
    along = [i for i, candidate in enumerate(found)
             if _is_along(isotropy.moment_cartesian(candidate.configurations[0], lattice),
                          (1, 1, 1))]
    assert len(along) == 1
    in_plane = tuple(i for i in range(len(found)) if i not in along)
    # restarts=4: every equivalent draw here reproduces on its first restart,
    # at the default cap too, so the cap is paid only by the three pairs that
    # are distinguishable, where it buys nothing (80-99 s on Linux CI at 32,
    # 8-21 s before the cap was raised)
    assert isotropy.equivalence_classes(found, refl, restarts=4) == \
        ((along[0],), in_plane)
    first = list(refl.shells[0])
    assert refl.d[first[0]] == pytest.approx(5.0 * np.sqrt(3.0) / 1.5, rel=1e-12)
    for i, candidate in enumerate(found):
        intensity = _unit_intensity(candidate, refl)
        at_first = float(np.sum(intensity[first]))
        if i == along[0]:
            assert at_first <= 1e-20 * float(np.max(intensity))
        else:
            assert at_first > 1e-3 * float(np.max(intensity))


def test_the_type_i_fcc_cell_splits_the_moment_along_c_from_the_in_plane_ones():
    """F m -3 m 4a at k = (0, 0, 1): two classes, m ∥ c against m ⊥ c.

    One arm picks out an axis, so the configurational symmetry is tetragonal
    and Shirane's rule makes the angle to c measurable (Shirane, 1959, p. 284).
    The child cell is rotated by 45°.
    """
    found = isotropy.candidates("F m -3 m", (0, 0, 0), (0, 0, 1))
    lattice = np.asarray(found.lattice, dtype=np.float64)
    along = [i for i, candidate in enumerate(found)
             if _is_along(isotropy.moment_cartesian(candidate.configurations[0], lattice),
                          (0, 0, 1))]
    assert len(along) == 1
    in_plane = tuple(i for i in range(len(found)) if i not in along)
    classes = isotropy.equivalence_classes(found, isotropy.reflections(lattice, 1.5))
    assert classes == ((along[0],), in_plane)


@pytest.mark.slow
def test_the_g_type_perovskite_cell_is_one_class():
    """P m -3 m 1a at k = (½, ½, ½): one class, every moment direction.

    The ± arrangement of a G-type antiferromagnet has cubic configurational
    symmetry, so the powder intensity does not depend on the moment direction
    at all (Shirane, 1959, p. 284).  The child cell is left-handed, which is
    why it is here.  About 6-8 s, most of it the six candidates' construction,
    so it is marked slow.
    """
    found = isotropy.candidates("P m -3 m", (0, 0, 0), HALF)
    lattice = np.asarray(found.lattice, dtype=np.float64)
    assert np.linalg.det(lattice) < 0
    classes = isotropy.equivalence_classes(found, isotropy.reflections(lattice, 2.0))
    assert classes == (tuple(range(len(found))),)


@pytest.mark.parametrize("name", sorted(RIGID_MAPS))
def test_the_same_crystal_in_a_rotated_frame_gives_the_same_intensities_and_classes(name):
    """The frame is a choice, and nothing a powder measures may depend on it.

    The MnO-type candidates, with the reflection set built on the same lattice
    re-expressed in a rigidly rotated (or rotated and mirrored) Cartesian
    frame: every shell's intensity and every class must come back unchanged.
    This is the test that would have caught #534, where the moment was rebuilt
    from the cell parameters in a fixed frame and ĥ followed the lattice.
    The classes are compared at ``restarts=4``: the claim is that the two
    frames agree, and the MnO test's note on the cap holds in both frames.
    """
    q = RIGID_MAPS[name]
    found = isotropy.candidates("F m -3 m", (0, 0, 0), HALF)
    lattice = np.asarray(found.lattice, dtype=np.float64)
    here = isotropy.reflections(lattice, 1.5)
    there = isotropy.reflections(lattice @ q.T, 1.5)
    assert np.allclose(here.shell_d, there.shell_d, rtol=1e-12)
    rng = np.random.default_rng(534)
    for candidate in found:
        amplitudes = rng.normal(size=candidate.free_amplitudes)
        a = isotropy.powder_intensities(candidate, amplitudes, here)
        b = isotropy.powder_intensities(candidate, amplitudes, there)
        assert np.allclose(a, b, rtol=1e-10, atol=1e-10 * float(np.max(a)))
    assert isotropy.equivalence_classes(found, here, restarts=4) == \
        isotropy.equivalence_classes(found, there, restarts=4)


@pytest.mark.parametrize("case", [("F m -3 m", HALF), ("P m -3 m", HALF)],
                         ids=["MnO-type rotated", "G-type left-handed"])
def test_the_refinements_m_perp_agrees_with_the_isotropy_rung_on_a_rotated_cell(case):
    """WP-1327's forward model against M-7's, reflection by reflection.

    ``scattering.magnetic_f2`` builds Q and the moment from the cell
    *parameters*, both in the Cholesky frame, so it never had #534's defect;
    this pins that the fixed :func:`isotropy.structure_factors` now agrees with
    it on a cell that is rotated (MnO type) and one that is left-handed (G
    type).  Each candidate's first configuration is put on every atom of the
    magnetic cell in P1 with a unit form factor (s = 0), so the two must give
    p²·|M⊥|² and |M⊥|² for the same reflections.
    """
    from rietx.crystallography.magnetic import scattering
    from rietx.crystallography.magnetic.moments import dofs_from_moment, moment_frame

    group, k = case
    found = isotropy.candidates(group, (0, 0, 0), k)
    lattice = np.asarray(found.lattice, dtype=np.float64)
    lengths = np.linalg.norm(lattice, axis=1)
    angles = [float(np.degrees(np.arccos(lattice[i] @ lattice[j]
                                         / (lengths[i] * lengths[j]))))
              for i, j in ((1, 2), (0, 2), (0, 1))]
    cell = (*lengths.tolist(), *angles)
    refl = isotropy.reflections(lattice, 2.0)
    frame = moment_frame(np.eye(3), cell)                          # a free moment
    for candidate in found:
        n = len(candidate.positions)
        sites = scattering.MagneticSites(
            mom_mat=[np.eye(3)[None]] * n,
            ops=[(np.eye(3)[None], np.zeros((1, 3)))] * n,
            frames=[frame] * n, ions=["Mn2+"] * n, g_factors=[2.0] * n,
            approximations=[None] * n)
        crystal_axis = candidate.configurations[0] * lengths      # magCIF unit axes
        dofs = [dofs_from_moment(frame, cell, m) for m in crystal_axis]
        stol = np.zeros(len(refl))
        refined = scattering.magnetic_f2(
            refl.hkl, np.arange(len(refl)), np.ones(len(refl)), stol, sites, cell,
            candidate.positions, np.ones(n), np.zeros(n), dofs)
        f0 = float(scattering._form_factor(sites, 0, np.zeros(1))[0])
        refined = refined / (scattering.P_MAGNETIC_FM * f0) ** 2
        f = isotropy.structure_factors(candidate, refl, domains=False)
        isotropic = np.sum(np.abs(f[0, 0]) ** 2, axis=1)
        assert np.allclose(refined, isotropic, rtol=1e-10,
                           atol=1e-10 * float(np.max(isotropic))), candidate.label


# --------------------------------------------------------------------------
# D. The two halves of the engine agreeing
# --------------------------------------------------------------------------

ENGINE_CASES = [
    ("P n m a", (0, 0, 0), GAMMA),
    ("P n m a", (0, 0, 0.5), GAMMA),
    ("F m -3 m", (0, 0, 0), GAMMA),
    ("P 4/m m m", (0, 0, 0), GAMMA),
    ("P 6_3 c m", (0.32080, 0, 0), GAMMA),
    ("R -3 c", (0, 0, 0.3476), GAMMA),
    ("F m -3 m", (0, 0, 0), HALF),
    ("P b c m", (0.308, 0.114, 0.07), (Fraction(1, 2), Fraction(0), Fraction(0))),
    ("I 4_1/a c d", (0, 0.25, 0.375), (Fraction(1), Fraction(1), Fraction(1))),
]


@pytest.mark.parametrize("case", ENGINE_CASES, ids=[f"{c[0]}@{c[2][0]}" for c in ENGINE_CASES])
def test_every_candidate_configuration_lies_in_its_own_groups_allowed_span(case):
    """The strongest oracle-free test in the magnetic engine, and not optional.

    :mod:`.modes` builds the moment pattern from the irrep's basis vectors;
    :mod:`.isotropy` derives the operator list from the stabiliser; M-5 derives
    the allowed moment subspace back from that operator list.  Three independent
    routes, and the pattern has to sit in the subspace.  A wrong axial action, a
    wrong return-vector phase and a missing anti-translation each break it while
    leaving every dimension count intact.
    """
    group, site, k = case
    for candidate in isotropy.candidates(group, site, k, verify=False):
        assert candidate.in_allowed_span(), candidate.label


def test_the_sweep_over_the_230_settings_at_gamma():
    """Every standard setting, one special site, every candidate consistent.

    Measured 2026-09-06 on spglib 2.7.0 / gemmi 0.7.5: **1199 candidates over
    the 230 standard settings**, every one identified, every configuration
    inside its own group's allowed span, and **not one of type IV** — which is
    the derived statement that a zero propagation vector cannot produce an
    anti-translation.  About 15 s, so not marked slow.
    """
    import gemmi

    settings, seen = [], set()
    for entry in gemmi.spacegroup_table_itb():
        if entry.number in seen:
            continue
        seen.add(entry.number)
        settings.append(entry.xhm())
    assert len(settings) == 230

    total, types = 0, {}
    for setting in settings:
        found = isotropy.candidates(setting, (0, 0, 0), GAMMA)   # verify=True inside
        total += len(found)
        for candidate in found:
            assert candidate.identification is not None, f"{setting} {candidate.label}"
            types[candidate.msg_type] = types.get(candidate.msg_type, 0) + 1
    assert total == 1199
    assert types == {1: 305, 3: 894}


def test_the_real_amplitude_count_closes_at_three_n():
    """Σ over the kept irreps of the free real amplitudes is 3N, at every setting.

    It closes only because a genuinely complex irrep and its conjugate are one
    physically irreducible representation and only one of the pair is kept; with
    both, P4 at Γ on a general site gives 3 + 6 + 6 + 3 = 18 against 3N = 12.
    """
    import gemmi

    seen, mismatches = set(), []
    for entry in gemmi.spacegroup_table_itb():
        if entry.number in seen:
            continue
        seen.add(entry.number)
        for site in ((0, 0, 0), (0.11, 0.13, 0.17)):
            representation = modes.magnetic_representation(entry.xhm(), site, GAMMA)
            kept, total = [], 0
            for irrep in irreps.small_irreps(entry.xhm(), GAMMA):
                if isotropy._is_conjugate_of_a_kept_irrep(irrep, kept):
                    continue
                basis = modes.basis_vectors(representation, irrep)
                if basis.multiplicity == 0:
                    continue
                kept.append(irrep)
                total += basis.free_real_amplitudes
            if total != 3 * representation.n_atoms:
                mismatches.append((entry.xhm(), site, total, 3 * representation.n_atoms))
    assert mismatches == []


def test_p4_at_gamma_is_the_case_that_needs_the_conjugate_pair_dropped():
    """The measurement behind the rule, written down where it can fail."""
    representation = modes.magnetic_representation("P 4", (0.11, 0.13, 0.17), GAMMA)
    counts = []
    for irrep in irreps.small_irreps("P 4", GAMMA):
        basis = modes.basis_vectors(representation, irrep)
        if basis.multiplicity:
            counts.append(basis.free_real_amplitudes)
    assert sorted(counts) == [3, 3, 6, 6]
    assert sum(counts) == 18 != 3 * representation.n_atoms
    # one of the conjugate pair is dropped, so three irreps give three candidates
    # (each of these is one-dimensional over the *real* order-parameter space of
    # its own irrep, so one direction each) and 3 + 6 + 3 = 12 = 3N
    found = isotropy.candidates("P 4", (0.11, 0.13, 0.17), GAMMA)
    assert len(found) == 3
    assert sum(candidate.free_amplitudes for candidate in found) == 12
    assert 3 * representation.n_atoms == 12


# --------------------------------------------------------------------------
# E. Negative controls
# --------------------------------------------------------------------------

def test_dropping_the_anti_translation_changes_the_group_and_its_absences():
    """Control (i): a type IV group without its anti-translation is a different model."""
    found = isotropy.candidates("P b c m", (0.308, 0.114, 0.07),
                                (Fraction(1, 2), Fraction(0), Fraction(0)))
    candidate = next(c for c in found if c.bns_number == "62.452")
    reflections = isotropy.reflections(found.lattice, 2.5)
    full = isotropy.group_absences(candidate.group, reflections)

    # the same candidate built as if the coset that carries ε = −1 carried +1:
    # the operator *set* is unchanged, only the anti-translation stops being one
    plain = isotropy.MagneticCell(
        k=found.cell.k, basis=found.cell.basis,
        translations=tuple((shift, 1) for shift, _ in found.cell.translations),
        spacegroup=found.cell.spacegroup)
    little = irreps.little_group("P b c m", found.cell.k)
    stripped = isotropy._candidate_group(little, plain, candidate.direction.stabilizer)
    assert stripped.order == candidate.group.order
    assert not any(op.time_reversal < 0 for op in stripped.centerings)
    assert identify(stripped, lattice=found.lattice).bns_number != "62.452"
    assert identify(stripped, lattice=found.lattice).msg_type != 4
    assert int(full.sum()) > 0
    without = isotropy.group_absences(stripped, reflections)
    assert not np.array_equal(without, full)
    # the type IV rule "h·t an integer is absent" is gone: the anti-translation
    # was the only thing forbidding those reflections
    anti = next(op for op in candidate.group.centerings if op.time_reversal < 0)
    shift = np.array([float(v) for v in anti.translation])
    products = reflections.hkl @ shift
    rule = np.abs(products - np.round(products)) < 1e-9
    assert np.all(rule <= full)
    assert not np.all(rule <= without)


def test_the_displacive_time_reversal_rule_greys_a_magnetic_order_parameter():
    """Control (ii): +1 on a moment gives grey stabilisers, which forbid every moment.

    Re-pinned for the displacive isotropy-group fix: the displacive groups are
    built by ``_candidate_group(..., kind="displacive")``, which emits both
    time-reversal signs of every operation that fixes the displacement.  The
    expected value (grey, forbidding every moment, a different BNS set from the
    magnetic one) is unchanged at k = 0; what changed is that the call now has
    to say ``kind``, since the displacive rule is no longer the magnetic one
    with a different sign.
    """
    representation = modes.magnetic_representation("P n m a", (0, 0, 0.5), GAMMA)
    little = irreps.little_group("P n m a", GAMMA)
    cell = isotropy.magnetic_cell("P n m a", GAMMA)
    magnetic, displacive = [], []
    for irrep in irreps.small_irreps("P n m a", GAMMA):
        basis = modes.basis_vectors(representation, irrep)
        if basis.multiplicity == 0:
            continue
        for kind, sink in (("magnetic", magnetic), ("displacive", displacive)):
            space = isotropy.order_parameter_space(basis, kind=kind)
            for direction in isotropy.isotropy_directions(space):
                sink.append(isotropy._candidate_group(little, cell, direction.stabilizer,
                                                      kind=kind))
    assert len(magnetic) == len(displacive) == 4
    assert not any(group.is_grey for group in magnetic)
    assert all(group.is_grey for group in displacive)
    for group in displacive:
        assert allowed_moment_basis(group.site_stabilizer((0, 0, 0.5))).shape[0] == 0
    assert ({identify(group).bns_number for group in magnetic}
            != {identify(group).bns_number for group in displacive})


#: Site and k of the bug this regression guards: a real Sb position in a
#: non-special Pnma perovskite-like setting, at the doubling-along-a-and-c
#: propagation vector that makes 2k a reciprocal lattice vector (so the
#: candidates are in scope) while the k itself is not Γ or a symmetry point —
#: unlike every displacive fixture above.  Under the pre-fix code every one of
#: these four candidates raised ``RuntimeError`` from
#: ``MagneticCandidate.in_allowed_span``, because that check tested the
#: **axial** span (``allowed_moment_basis``) regardless of ``kind``, and a
#: displacement is a polar vector, not an axial one.
PNMA_SB_SITE = (0.02806, 0.25, 0.01240)
PNMA_SB_K = (Fraction(1, 2), Fraction(0), Fraction(1, 2))
#: Re-pinned: the pre-fix set {4.8, 11.51, 6.19, 2.5} was the groups of the
#: *parent* lattice, which carried the anti-translation as a pure translation
#: (a symmetry of no distorted structure at k != 0).  The child types spglib
#: names on the distorted structure (independent oracle, black box) are P2_1/m
#: (11.51) for S2/S3 and P2_1/c (14.76) for S1/S4.
PNMA_SB_DISPLACIVE_BNS = {"11.51", "14.76"}


def test_pnma_sb_displacive_candidates_verify_true():
    """Regression: the four Type-II displacive candidates, checked by their own rule.

    Re-pinned for the displacive isotropy-group fix (see the constant above):
    the four candidates are unchanged, their groups are not.  P2_1 / Pm / P-1
    were the parent-lattice groups; the stabiliser of each field is P2_1/m
    (S2, S3) or P2_1/c (S1, S4).  The prose below describes the pre-fix
    verification bug and its numbers are the pre-fix ones.

    Before the fix, ``candidates(..., kind="displacive")`` raised under the
    default ``verify=True`` for this site and k — and for every other site and
    k tried, 100% of the time — because ``in_allowed_span`` always checked the
    axial span even for a displacive candidate.  With the fix it verifies
    cleanly and returns exactly the four candidates ``verify=False`` already
    found: P2₁ (BNS 4.8), P2₁/m (11.51), Pm (6.19) and P-1 (2.5), each a
    Type-II (grey) magnetic group — expected here, not a defect, because a
    displacement does not care about time reversal at all (every stabiliser
    contains 1' when it fixes the site polarly).
    """
    found = isotropy.candidates("P n m a", PNMA_SB_SITE, PNMA_SB_K, kind="displacive")
    assert len(found) == 4
    assert {c.bns_number for c in found} == PNMA_SB_DISPLACIVE_BNS
    assert all(c.msg_type == 2 for c in found)
    for candidate in found:
        assert candidate.in_allowed_span()


def test_a_pnma_mirror_allows_in_plane_displacement_forbids_in_plane_moment():
    """The discriminating case: a mirror's polar and axial spans are complementary.

    In the P2₁/m child (BNS 11.51) of the case above, the Sb site's magnetic-
    cell stabiliser contains the mirror ``-x+1/2,y,z,+1`` (rotation
    diag(-1,1,-1), det = -1, no time reversal).  A **displacement** transforms
    as R alone, so its eigenvalue-+1 (allowed) directions are y and z, the
    directions *in* the mirror plane — a point in the plane can move within it.
    A **moment** transforms as det(R)·R = -R (Halpern & Johnson, 1939), so the
    eigenvalue-+1 direction flips to x, the direction *normal* to the plane —
    the textbook rule that a magnetic moment survives a mirror only
    perpendicular to it, the opposite of a polar vector. Using the axial
    helper (``allowed_moment_basis``) to check a displacive candidate, as the
    pre-fix ``in_allowed_span`` did, gets exactly this case backwards.
    """
    found = isotropy.candidates("P n m a", PNMA_SB_SITE, PNMA_SB_K, kind="displacive")
    candidate = next(c for c in found if c.bns_number == "11.51")
    atom = 0
    stabilizer = candidate.group.site_stabilizer(candidate.positions[atom])
    mirror = next(op for op in stabilizer
                  if op.determinant == -1 and op.time_reversal > 0)
    assert mirror.xyz() == "-x+1/2,y,z,+1"

    displacement_basis = allowed_displacement_basis([mirror])
    moment_basis = allowed_moment_basis([mirror])
    # in-plane of the mirror (y, z): allowed for a displacement, forbidden for a moment
    assert in_span(displacement_basis, (0, 1, 1))
    assert not in_span(moment_basis, (0, 1, 1))
    # normal to the mirror (x): the opposite way round
    assert in_span(moment_basis, (1, 0, 0))
    assert not in_span(displacement_basis, (1, 0, 0))

    # the candidate's own configuration on this atom is exactly such an
    # in-plane pattern: it lies in the polar span (in_allowed_span dispatches
    # on kind="displacive" and passes) but not in the full stabiliser's axial
    # span, so checking it against the wrong helper is what used to raise
    pattern = candidate.configurations[0][atom]
    assert not np.allclose(pattern, 0)
    assert candidate.in_allowed_span()
    axial_basis = allowed_moment_basis(stabilizer)
    assert not in_span(axial_basis, pattern)


#: The exact case Q21 diagnosed and Q22 fixes: a Pnma y = 1/4 mirror site at
#: k = (1/2,1/2,0), little-group element index 7 (rotation diag(1,-1,1),
#: translation (0,1/2,0)), whose atom-specific return-vector phase (Q21
#: measured ``SiteRepresentation.permutation.phases[7, atom] == -1`` directly)
#: is what ``allowed_displacement_basis`` had no way to see before Q22.
Q22_SITE = (0.1, 0.25, 0.15)
Q22_K = ("1/2", "1/2", "0")
Q22_ROTATION = ((1, 0, 0), (0, -1, 0), (0, 0, 1))
Q22_TRANSLATION = (Fraction(0), Fraction(1, 2), Fraction(0))
Q22_LITTLE_INDEX = 7
#: Re-pinned for the displacive isotropy-group fix.  The candidate Q21 diagnosed
#: was selected as BNS 6.19, a group of the parent lattice that is no symmetry of
#: its own field; at the correct group the same case (little-group index 7 with a
#: -1 return phase on parent atom 1, where the pre-Q22 rule rejects the
#: candidate's own pattern) is the rank-2 direction whose child group is BNS 8.33,
#: with a stabiliser of order 2 (the identity and element 7).
#: The gauge-free selector for Q21's candidate: the BNS number of its isotropy
#: subgroup.  The ``S1(rank 2)#3`` label is not one — ``isotropy.py``'s direction
#: sort numbers the ties *after* sorting, and the tie-break is the gauge.
Q22_BNS = "8.33"


def test_the_return_vector_phase_flips_which_eigenspace_a_displacement_needs():
    """The derived rule itself, on the exact case Q21 diagnosed and left unfixed.

    Q21's own diagnosis (``checks/Q21_CANDIDATES_VERIFY.md``, half A, steps
    2-5): little-group index 7 (rotation diag(1,-1,1), translation (0,1/2,0))
    returns this atom with a phase of -1
    (``SiteRepresentation.permutation.phases[7, atom] == -1``), so the
    *magnetic-cell-conjugated* rotation R' must satisfy R'·d = -d, not the +1
    eigenspace ``allowed_displacement_basis`` could ever return before Q22
    (no ``phases`` argument to carry that -1) — the +1 eigenspace is what a
    caller who only had the old rule available would be forced to accept.

    **Nothing here may be selected or pinned by a gauge-dependent quantity**
    (Yue's review of #389 §5-6, where CI was red on Linux and green on
    darwin/arm64 for exactly that reason).  ``isotropy.py``'s own docstring at
    the direction sort says the ``#n`` suffix exists *because* a gauge that is
    not axis-aligned gives several directions the same fallback label, so the
    candidate is chosen by its BNS number — a property of the isotropy subgroup
    and not of any basis inside it — and the configuration by the span of the
    atom's own displacements across the whole rank-2 family.  Which basis vector
    of that family carries which share of it is the gauge; the line they lie on
    is not, and ``in_span`` is a question about the line.
    """
    found = isotropy.candidates("P n m a", Q22_SITE, Q22_K, kind="displacive", verify=False)
    # BNS 8.33 is unique in this set, and the ``#n`` numbering of the rank-2
    # directions is the gauge
    matching = [c for c in found if c.bns_number == Q22_BNS]
    assert len(matching) == 1, [c.bns_number for c in found]
    candidate = matching[0]
    assert candidate.direction.rank == 2 and len(candidate.direction.stabilizer) == 2
    little = candidate.permutation.little
    assert little.rotations[Q22_LITTLE_INDEX].tolist() == [list(r) for r in Q22_ROTATION]
    assert little.translations[Q22_LITTLE_INDEX] == Q22_TRANSLATION

    # atom 2 is parent atom 1, whose own return-vector phase under index 7 is -1
    atom = 2
    assert int(candidate.parent_atoms[atom]) == 1
    phase = candidate.permutation.phases[Q22_LITTLE_INDEX, 1]
    assert phase == -1 + 0j

    inverse = isotropy._exact_inverse(candidate.cell.basis)
    forward = [[isotropy._frac(v) for v in row] for row in candidate.cell.basis]
    rotation_magnetic = isotropy._rotation_in_cell(Q22_ROTATION, inverse, forward)
    op = MagneticOperator.build(rotation_magnetic, (Fraction(0),) * 3, 1)

    # Atom 2's displacements across the whole family span one line — rank 1,
    # singular values (0.909, 0, 0) — and *which* configurations carry it is the
    # gauge: darwin/arm64 puts it all in configuration 2, Linux splits the same
    # quadrature sum between 2 and 3.  Every non-zero one of them is a
    # displacement this atom is allowed, so every one of them is asserted.
    block = candidate.configurations[:, atom, :]
    assert np.linalg.matrix_rank(block, tol=1e-9) == 1
    patterns = [row for row in block if float(np.linalg.norm(row)) > 1e-9]
    assert patterns, "atom 2 has no displacement in this family at all"

    old_rule = allowed_displacement_basis([op])         # no phases: the pre-Q22 rule
    new_rule = allowed_displacement_basis([op], phases=[-1])   # Q22's fix

    for pattern in patterns:
        assert in_span(new_rule, pattern)
        assert not in_span(old_rule, pattern), (
            "the pre-Q22 rule must reject this candidate's own pattern, or this "
            "is not a test of the fix")
    assert candidate.in_allowed_span()


def test_a_stale_phases_length_is_refused_by_name():
    """``phases`` must be one entry per operation — a caller error, not a tolerance."""
    op = MagneticOperator.build(((1, 0, 0), (0, 1, 0), (0, 0, 1)), (Fraction(0),) * 3, 1)
    with pytest.raises(ValueError, match="one phase per operation"):
        allowed_displacement_basis([op], phases=[1, -1])
    with pytest.raises(ValueError, match="one phase per operation"):
        allowed_moment_basis([op], phases=[])


def test_the_equivalence_test_does_not_merge_different_absence_sets():
    """Control (iii): a difference a powder can see must survive the class merge."""
    found = isotropy.analyse(isotropy.candidates("P n m a", (0, 0, 0), GAMMA), d_min=1.5)
    reflections = isotropy.reflections(found.lattice, 1.5)
    absent = [set(map(tuple, isotropy.systematic_absences(c, reflections).hkl.tolist()))
              for c in found]
    for i in range(len(found)):
        for j in range(i + 1, len(found)):
            if absent[i] != absent[j]:
                assert found.class_of(i) != found.class_of(j)


def test_a_k_outside_the_scope_is_refused_by_name():
    """The fence, said out loud rather than answered wrongly."""
    with pytest.raises(ValueError, match="reciprocal lattice"):
        isotropy.candidates("P 3", (0.11, 0.13, 0.17),
                            (Fraction(1, 3), Fraction(1, 3), Fraction(0)))
    with pytest.raises(ValueError, match="M-8"):
        isotropy.candidates("I 41 3 2", (0, 0, 0), HALF)
    with pytest.raises(ValueError, match="reciprocal lattice"):
        isotropy.magnetic_cell("P n m a", (Fraction(1, 4), Fraction(0), Fraction(0)))


def test_an_unknown_order_parameter_kind_is_refused():
    with pytest.raises(ValueError, match="kind must be one of"):
        isotropy.candidates("P n m a", (0, 0, 0), GAMMA, kind="axial")


# --------------------------------------------------------------------------
# F. The mechanics: the cell, the transform, the conventions
# --------------------------------------------------------------------------

CELL_CASES = [
    ("P n m a", GAMMA), ("P n m a", (Fraction(1, 2), Fraction(0), Fraction(0))),
    ("F m -3 m", HALF), ("I 4_1/a c d", (Fraction(1), Fraction(1), Fraction(1))),
    ("P 4/m m m", HALF), ("R -3 c", GAMMA), ("P b c m", (Fraction(1, 2), 0, 0)),
    ("I 4/m c m", GAMMA), ("F d -3 m:2", GAMMA),
    ("P 6_3 c m", (Fraction(0), Fraction(0), Fraction(1, 2))),
]


@pytest.mark.parametrize("case", CELL_CASES, ids=[f"{c[0]}" for c in CELL_CASES])
def test_the_supercell_agrees_with_m5s_own_lattice_completion(case):
    """Two routes to the grey little group in the magnetic cell, operation for operation.

    One builds it directly from the little group and the lattice cosets; the
    other assembles it in the parent's cell and hands it to
    ``MagneticGroup.transformed``, whose lattice completion and order guard are
    M-5's.  A supercell is exactly where a candidate list goes quietly wrong, so
    the two are compared as **sets of operations**, never as counts.
    """
    group, k = case
    cell = isotropy.magnetic_cell(group, k)
    little = irreps.little_group(group, cell.k)
    direct = isotropy._candidate_group(
        little, cell, tuple((i, eps) for i in range(little.order) for eps in (1, -1)))
    carried = isotropy.grey_little_group(group, cell.k, cell)
    assert set(direct.all_operations()) == set(carried.all_operations())
    assert direct.is_grey


@pytest.mark.parametrize("case", CELL_CASES, ids=[f"{c[0]}" for c in CELL_CASES])
def test_the_magnetic_cell_has_the_right_lattice_cosets(case):
    group, k = case
    cell = isotropy.magnetic_cell(group, k)
    sg = irreps._resolve(group)
    if irreps.equivalent_kvectors(sg, cell.k, GAMMA):
        assert cell.transform == "a,b,c;0,0,0"
        assert not cell.doubled
        assert len(cell.translations) == len(irreps._centrings(sg))
    else:
        assert cell.doubled
        assert len(cell.translations) == 2
        assert [eps for _, eps in cell.translations] == [1, -1]


def test_moment_cartesian_is_the_row_vector_lattice_transpose():
    """The convention pin: contravariant fractional components times Aᵀ, in A's frame.

    On a lattice that is **not** in the standard orientation — the hexagonal
    compatible cell rigidly rotated — since on a standard one the Cholesky
    frame of M-5's ``moment_to_cartesian`` and the lattice's own coincide and
    the pin cannot tell them apart (issue #534).  The magnitude is M-5's
    either way: |Aᵀ·m| equals :func:`~.operators.moment_magnitude` of the same
    moment in magCIF's unit-vector ``crystalaxis`` basis, which is the
    statement that the two conventions were reconciled and not merely both used.
    """
    from rietx.crystallography.magnetic.operators import moment_magnitude

    standard = np.asarray(isotropy.compatible_cell("P 6_3 c m"), dtype=np.float64)
    lengths = np.linalg.norm(standard, axis=1)
    cell = (*lengths.tolist(), 90.0, 90.0, 120.0)
    moments = np.array([[0.3, -0.7, 1.1], [1.0, 1.0, 0.0]])
    for q in RIGID_MAPS.values():
        lattice = standard @ q.T
        got = isotropy.moment_cartesian(moments, lattice)
        assert np.allclose(got, moments @ lattice)
        assert np.allclose(np.linalg.norm(got, axis=1),
                           [moment_magnitude(m * lengths, cell) for m in moments])


def test_the_reflection_shells_are_complete_to_d_min():
    """Every reflection of the lattice at a shell's d is in that shell."""
    lattice = isotropy.compatible_cell("P n m a")
    found = isotropy.reflections(lattice, 1.6)
    assert len(found) == sum(len(shell) for shell in found.shells)
    assert np.all(found.d >= 1.6 - 1e-9)
    wider = isotropy.reflections(lattice, 1.5)
    inside = {tuple(h) for h in wider.hkl.tolist() if 1.0 / np.linalg.norm(
        np.linalg.inv(lattice) @ np.array(h, float)) >= 1.6 - 1e-9}
    assert inside == {tuple(h) for h in found.hkl.tolist()}
    # Friedel mates are both present, so a shell size is a multiplicity
    for shell in found.shells:
        for index in shell:
            assert any(np.array_equal(found.hkl[other], -found.hkl[index])
                       for other in shell)


DOMAIN_CASES = [
    ("P n m a", (0, 0, 0), GAMMA, 1.8),
    ("P 4/m m m", (0, 0, 0), GAMMA, 2.0),
    ("P b c m", (0.308, 0.114, 0.07), (Fraction(1, 2), Fraction(0), Fraction(0)), 2.5),
]


@pytest.mark.parametrize("case", DOMAIN_CASES, ids=[c[0] for c in DOMAIN_CASES])
def test_the_domain_average_is_a_constant_factor_over_a_complete_shell(case):
    """Measured, not assumed: each domain is an isometry of the shell.

    The module builds the domains explicitly, which is the safe thing to do; the
    claim in its docstring — that summing over a **complete** shell makes the
    domain sum a constant multiple of one domain's — is checked here, and it is
    the reason the arms of the star need not be built as well.
    """
    group, site, k, d_min = case
    found = isotropy.candidates(group, site, k)
    reflections = isotropy.reflections(found.lattice, d_min)
    rng = np.random.default_rng(7)
    for candidate in found:
        amplitudes = rng.normal(size=candidate.free_amplitudes)
        many = isotropy.powder_intensities(candidate, amplitudes, reflections, domains=True)
        one = isotropy.powder_intensities(candidate, amplitudes, reflections, domains=False)
        scale = float(np.max(many)) or 1.0
        ratios = many[one > 1e-12 * scale] / one[one > 1e-12 * scale]
        assert ratios.size
        assert np.allclose(ratios, ratios[0], rtol=1e-9)
        assert np.allclose(many[one <= 1e-12 * scale], 0.0, atol=1e-9 * scale)


def test_the_type_iv_absence_rule_is_the_one_derived_by_hand():
    """h·t an integer is magnetically absent, for the anti-translation t.

    Derived, because the printed rule could not be reached: the Bilbao MAGNEXT
    endpoint returned HTTP 500 on 2026-09-06.  With an anti-translation t the
    moment at r + t is −m(r), so
    M(h) = Σ_j m_j·e^{2πi h·r_j}·(1 − e^{2πi h·t}) and every reflection with
    h·t ∈ ℤ vanishes.  Three routes are compared: this rule, the group-only
    MAGNEXT computation :func:`isotropy.group_absences`, and the candidate's own
    configuration family.
    """
    found = isotropy.candidates("P b c m", (0.308, 0.114, 0.07),
                                (Fraction(1, 2), Fraction(0), Fraction(0)))
    reflections = isotropy.reflections(found.lattice, 2.5)
    for candidate in found:
        anti = next(op for op in candidate.group.centerings if op.time_reversal < 0)
        shift = np.array([float(v) for v in anti.translation])
        products = reflections.hkl @ shift
        rule = np.abs(products - np.round(products)) < 1e-9
        assert rule.sum() > 0
        by_group = isotropy.group_absences(candidate.group, reflections)
        assert np.all(rule <= by_group)          # the anti-translation is one rule of several
        report = isotropy.systematic_absences(candidate, reflections, perpendicular=False)
        by_family = {tuple(h) for h in report.hkl.tolist()}
        assert {tuple(h) for h, absent in zip(reflections.hkl.tolist(), rule)
                if absent} <= by_family
        assert "anti-translation" in report.rule
        if candidate.bns_number == "62.452":
            # measured: for the maximal candidates the anti-translation is the
            # *only* rule, and all three routes give the same 40 of 92
            assert np.array_equal(rule, by_group)
            assert by_family == {tuple(h) for h, absent
                                 in zip(reflections.hkl.tolist(), rule) if absent}
            assert int(rule.sum()) == 40 and len(reflections) == 92


@pytest.mark.parametrize("case", DOMAIN_CASES, ids=[c[0] for c in DOMAIN_CASES])
def test_a_groups_absences_are_a_subset_of_a_candidates(case):
    """A symmetry-only rule cannot forbid more than a specific model does."""
    group, site, k, d_min = case
    found = isotropy.candidates(group, site, k)
    reflections = isotropy.reflections(found.lattice, d_min)
    for candidate in found:
        by_group = isotropy.group_absences(candidate.group, reflections)
        report = isotropy.systematic_absences(candidate, reflections, perpendicular=False)
        by_family = {tuple(h) for h in report.hkl.tolist()}
        assert {tuple(h) for h, absent in zip(reflections.hkl.tolist(), by_group)
                if absent} <= by_family


def test_a_one_dimensional_irrep_has_exactly_one_direction():
    """The trivial half of the enumeration, where it can still be got wrong."""
    representation = modes.magnetic_representation("P n m a", (0, 0, 0), GAMMA)
    for irrep in irreps.small_irreps("P n m a", GAMMA):
        basis = modes.basis_vectors(representation, irrep)
        if basis.multiplicity == 0:
            continue
        space = isotropy.order_parameter_space(basis)
        assert space.dimension == 1
        directions = isotropy.isotropy_directions(space)
        assert len(directions) == 1
        assert directions[0].rank == 1
        assert len(directions[0].stabilizer) == space.little.order


def test_conjugate_directions_are_collapsed_and_counted():
    """[100], [010] and [001] are one candidate with three domains, not three candidates."""
    representation = modes.magnetic_representation("F m -3 m", (0, 0, 0), GAMMA)
    irrep = next(ir for ir in irreps.small_irreps("F m -3 m", GAMMA)
                 if modes.basis_vectors(representation, ir).multiplicity)
    space = isotropy.order_parameter_space(modes.basis_vectors(representation, irrep))
    assert space.dimension == 3
    collapsed = isotropy.isotropy_directions(space)
    every = isotropy.isotropy_directions(space, conjugacy=False)
    assert len(collapsed) == 6
    assert len(every) == sum(direction.conjugates for direction in collapsed)
    assert sorted(direction.conjugates for direction in collapsed) == [1, 3, 3, 4, 6, 6]


def test_the_candidate_set_prints_the_classic_table():
    found = isotropy.analyse(isotropy.candidates("P n m a", (0, 0, 0), GAMMA), d_min=1.8)
    text = str(found)
    assert "irrep" in text and "BNS" in text and "determinable" in text and "class" in text
    assert "62.448" in text
    assert text.count("\n") >= 6


@pytest.mark.parametrize("case", ENGINE_CASES, ids=[f"{c[0]}@{c[2][0]}" for c in ENGINE_CASES])
def test_every_configuration_is_invariant_under_its_own_group(case):
    """Stronger than the per-site span: the whole pattern is fixed, operation by operation.

    The family is *defined* as the configurations the isotropy subgroup fixes, so
    every basis configuration must come back unchanged under every operation of
    the candidate's own group — positions permuted, moments carried by
    ε·det(R)·R.  The per-site span test (arm D) is the weaker statement that each
    atom's moment is allowed; this one also pins the relative **signs** between
    atoms, which is where a wrong return-vector phase would show.
    """
    group, site, k = case
    for candidate in isotropy.candidates(group, site, k, verify=False):
        for operation in candidate.group.all_operations():
            moved = isotropy._apply_domain(operation, candidate.positions,
                                           candidate.configurations)
            assert np.allclose(moved, candidate.configurations, atol=1e-8), \
                f"{candidate.label} is not fixed by {operation.xyz()!r}"


def _field_stabiliser(operations, positions, field, kind, tol=1e-6):
    """The operations of ``operations`` that map the (position, vector) set onto itself.

    The independent oracle for a candidate's declared group: it never reads the
    isotropy machinery, only the field the candidate produces.  A displacement
    transforms as R, a moment as ε·det(R)·R (Halpern & Johnson 1939); positions
    are matched modulo the lattice.
    """
    kept = []
    for op in operations:
        rotation = op.matrix.astype(float)
        shift = np.array([float(v) for v in op.translation])
        action = (op.time_reversal * op.determinant * rotation
                  if kind == "magnetic" else rotation)
        moved = (positions @ rotation.T + shift) % 1.0
        carried = field @ action.T
        for j in range(len(positions)):
            d = np.abs(positions - moved[j])
            hit = np.flatnonzero(np.all(np.minimum(d, 1 - d) < tol, axis=1))
            if hit.size != 1 or not np.allclose(field[hit[0]], carried[j], atol=1e-6):
                break
        else:
            kept.append(op)
    return kept


def _assert_declared_group_is_the_field_stabiliser(group, site, k, kind):
    found = isotropy.candidates(group, site, k, kind=kind, verify=False)
    assert len(found) > 0
    grey = isotropy.grey_little_group(group, k, found.cell).all_operations()
    rng = np.random.default_rng(7)
    for candidate in found:
        field = candidate.moments(rng.normal(size=candidate.free_amplitudes))
        stabiliser = {(o.rotation, tuple(o.translation), o.time_reversal)
                      for o in _field_stabiliser(grey, candidate.positions, field, kind)}
        declared = {(o.rotation, tuple(o.translation), o.time_reversal)
                    for o in candidate.group.all_operations()}
        assert declared == stabiliser, (group, k, kind, candidate.label)


#: (group, site, k): a k = 0 case that was always right (the control), and k != 0
#: cases that were wrong before the fix — the perovskite R point, the Pnma
#: (1/2, 0, 1/2) Sb site and a doubling in I4_1/amd (all public settings).
STABILISER_FAST_CASES = [
    ("P 4", (0.1, 0.2, 0.3), GAMMA),
    ("P m -3 m", (Fraction(1, 2), 0, 0), (Fraction(1, 2),) * 3),
    ("P n m a", PNMA_SB_SITE, PNMA_SB_K),
]


@pytest.mark.parametrize("kind", ["displacive", "magnetic"])
@pytest.mark.parametrize("case", STABILISER_FAST_CASES,
                         ids=[f"{c[0]}@{c[2][0]}" for c in STABILISER_FAST_CASES])
def test_every_candidates_declared_group_is_the_stabiliser_of_its_own_field(case, kind):
    """The declared group is the set of operations that fix the candidate's own field.

    Added with the displacive isotropy-group fix.  Before it, ``kind="displacive"``
    carried the parent translation as a pure translation and lacked the operations
    needing the anti-translation at every k != 0 (206 of 209 candidates on a
    34-case sweep, failing at P m -3 m / R and Pnma / (1/2, 0, 1/2) below), and
    ``verified`` could not see it because it never reads the translation lattice.
    The oracle is independent of the isotropy machinery: it applies the grey
    little group to a random field and keeps what leaves it unchanged.
    """
    group, site, k = case
    _assert_declared_group_is_the_field_stabiliser(group, site, k, kind)


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["displacive", "magnetic"])
@pytest.mark.parametrize("case", ENGINE_CASES, ids=[f"{c[0]}@{c[2][0]}" for c in ENGINE_CASES])
def test_the_declared_group_is_the_field_stabiliser_across_the_engine_cases(case, kind):
    """The sweep form of the test above over every engine case, both kinds."""
    group, site, k = case
    _assert_declared_group_is_the_field_stabiliser(group, site, k, kind)


def test_the_perovskite_tilt_irrep_gives_howard_and_stokes_six_subgroups():
    """Known answer (Howard & Stokes 1998, Acta Cryst. B54, 782): the R-point tilt irrep.

    (a,0,0) I4/mcm, (a,a,a) R-3c, (a,a,0) Imma, (a,b,0) C2/m, (a,a,b) C2/c and
    (a,b,c) P-1, as grey-group BNS numbers 140.542, 167.104, 74.555, 12.59,
    15.86 and 2.5.  Before the fix the enumeration used +D only and listed four
    directions (rank 1 x3 and (a,b,c)), none of them with the right lattice.
    """
    found = isotropy.candidates("P m -3 m", (Fraction(1, 2), 0, 0),
                                (Fraction(1, 2),) * 3, kind="displacive")
    tilt = sorted(c.bns_number for c in found if c.label.startswith("S10("))
    assert tilt == sorted(["140.542", "167.104", "74.555", "12.59", "15.86", "2.5"])


def test_random_amplitude_draws_find_the_same_absences_as_the_exact_test():
    """The brief's random-draw definition, against the linear-algebra one.

    :func:`isotropy.systematic_absences` asks whether the *map* from amplitudes
    to M⊥ is zero, which is exact; drawing amplitudes at random and looking for
    an exact zero is the same statement with a probability attached.  They agree
    here, which is what says the exact version is not accidentally stricter.
    """
    found = isotropy.candidates("P b c m", (0.308, 0.114, 0.07),
                                (Fraction(1, 2), Fraction(0), Fraction(0)))
    reflections = isotropy.reflections(found.lattice, 2.5)
    rng = np.random.default_rng(11)
    for candidate in found:
        factors = isotropy.structure_factors(candidate, reflections, domains=False)
        seen = np.zeros(len(reflections))
        for _ in range(5):
            amplitudes = rng.normal(size=candidate.free_amplitudes)
            total = np.tensordot(amplitudes, factors, axes=(0, 1))[0]
            seen = np.maximum(seen, np.max(np.abs(total), axis=1))
        scale = float(np.max(seen))
        by_draw = {tuple(h) for h, value in zip(reflections.hkl.tolist(), seen)
                   if value <= 1e-9 * scale}
        report = isotropy.systematic_absences(candidate, reflections)
        assert by_draw == {tuple(h) for h in report.hkl.tolist()}


def test_a_candidate_is_powder_equivalent_to_itself():
    """The fitter has to be able to hit an exact answer before a merge means anything."""
    found = isotropy.candidates("P n m a", (0, 0, 0), GAMMA)
    reflections = isotropy.reflections(found.lattice, 1.8)
    for candidate in found:
        assert isotropy.powder_equivalent(candidate, candidate, reflections)


def test_an_empty_reflection_set_is_shaped_and_refused_by_name():
    """A ``d_min`` past the cell admits nothing, and both halves must say so (#389 §4).

    ``reflections`` built ``np.array([], dtype=np.int64)``, whose shape is
    ``(0,)``, so the next consumer died inside numpy — ``matmul: Input operand 1
    has a mismatch in its core dimension 0 … (size 3 is different from 0)`` —
    naming nothing a caller could act on.  Two fixes, and neither replaces the
    other: the empty set is now shaped ``(0, 3)``, and ``analyse`` refuses it
    quoting the ``d_min`` and the cell that made it empty.
    """
    found = isotropy.candidates("P n m a", (0, 0, Fraction(1, 2)), GAMMA)
    empty = isotropy.reflections(found.lattice, 6.5)
    assert empty.hkl.shape == (0, 3)
    assert empty.q.shape == (0, 3)
    assert empty.d.shape == (0,)
    assert empty.shells == ()
    assert len(empty) == 0
    # the longest edge of the magnetic cell is 6 Å, so 6.5 admits nothing
    assert float(np.max(np.linalg.norm(found.lattice, axis=1))) < 6.5
    with pytest.raises(ValueError, match=r"6\.5"):
        isotropy.analyse(found, d_min=6.5)


def test_a_domain_transforms_a_displacement_by_r_and_a_moment_by_the_axial_matrix():
    """The two actions differ by det(R)·ε, and a domain must use the right one (#389 §3).

    A moment is an **axial** vector — ε·det(R)·R, Halpern & Johnson (1939) — and
    a displacement a **polar** one, plain R: no determinant, and no
    time-reversal sign, because time reversal does not move an atom.
    ``_apply_domain`` read ``moment_matrix()`` whatever ``candidate.kind``
    said, so on a displacive ``P n m a`` (0, 0, ½) candidate the inversion
    ``-x,-y,-z,+1`` acted as diag(+1, +1, +1) where a displacement needs
    diag(−1, −1, −1), while the *proper* domain operation was unaffected — the
    two images stopped carrying consistent relative signs, which is the whole
    content of a domain average.

    The assertion is exact rather than approximate: the two actions are the same
    integer matrix times det(R)·ε, so the two images must be exactly that
    multiple of each other, operation by operation, and the inversion is the one
    where the factor is −1.
    """
    found = isotropy.candidates("P n m a", (0, 0, Fraction(1, 2)), GAMMA,
                                kind="displacive")
    little = irreps.little_group(found.space_group, found.k)
    # Selected by the property the test is about — a domain set containing the
    # inversion, the operation where the polar and axial actions differ — not
    # by position.  All four candidates of this set qualify, so `found[1]` was
    # right by accident and would follow the candidate order if it moved
    # (review of #389 round 3, follow-ups).
    with_inversion = [c for c in found
                      if any(op.xyz() == "-x,-y,-z,+1"
                             for op in isotropy._domain_operations(c, little))]
    assert with_inversion, "no candidate of this set has the inversion as a domain operation"
    candidate = with_inversion[0]
    domains = isotropy._domain_operations(candidate, little)
    improper = [op for op in domains if op.determinant * op.time_reversal < 0]
    assert improper, "this set is supposed to contain an improper domain operation"
    for op in domains:
        polar = isotropy._apply_domain(op, candidate.positions,
                                       candidate.configurations, kind="displacive")
        axial = isotropy._apply_domain(op, candidate.positions,
                                       candidate.configurations, kind="magnetic")
        factor = op.determinant * op.time_reversal
        assert np.array_equal(axial, factor * polar), op.xyz()
        if op.xyz() == "-x,-y,-z,+1":
            assert np.array_equal(np.diag(op.matrix.astype(np.float64)),
                                  [-1.0, -1.0, -1.0])
            assert factor == -1


def test_the_magnetic_intensity_entry_points_refuse_a_displacive_set_by_name():
    """What ``analyse`` computes is magnetic, so it must not accept the other kind (#389 §3).

    ``structure_factors`` takes the moments to Cartesian μ_B and applies
    Halpern & Johnson's perpendicular projection; a displacement reaches a
    nuclear reflection through the scalar h·u instead, so every column
    ``analyse`` fills would be a plausible number that means nothing.  Before
    this fix ``analyse()`` accepted a displacive set without a word and returned
    a four-candidate table.
    """
    found = isotropy.candidates("P n m a", (0, 0, Fraction(1, 2)), GAMMA,
                                kind="displacive")
    reflections = isotropy.reflections(found.lattice, 2.0)
    with pytest.raises(ValueError, match="displacive"):
        isotropy.structure_factors(found[0], reflections)
    with pytest.raises(ValueError, match="displacive"):
        isotropy.analyse(found, d_min=2.0)


def test_a_candidate_is_powder_equivalent_to_itself_at_a_coarse_d_min():
    """A coarse ``d_min`` must not make everything look separable (#389 §1).

    Two distinct causes, both found by Yue's review on 2026-09-18 and both
    reproduced here before the fix, made ``powder_equivalent(c, c, refl)``
    return ``False`` for ``candidates("P n m a", (0, 0, 0.5), (0, 0, 0))`` at
    ``d_min = 5.2``, where the set has 4 reflections in 2 shells:

    * ``_fit_residual`` ran under ``method="lm"``, which *refuses* a problem
      with fewer residuals than variables (2 shells against 3 free
      amplitudes) — ``ValueError: Method 'lm' doesn't work when the number of
      residuals is less than the number of variables``.  A bare
      ``except Exception: continue`` turned that refusal into ``best = inf``,
      i.e. into "distinguishable".
    * candidate ``S4(a)`` has ``|M⊥|max = 6.1e-16`` over all four
      reflections — every shell is a systematic absence — so the draws were
      fitting round-off, and the ``<= 0.0`` guard written for exactly that
      case does not fire on 1e-32.

    The failure direction is the costly one: this module exists to say what a
    powder average *cannot* separate, so a false "distinguishable" splits
    models that are the same object.  Reflexivity is the weakest property the
    relation has and is asserted at both limits; nothing here claims the
    classes at 5.2 are coarser than at 1.5, which is not guaranteed physics.
    """
    found = isotropy.candidates("P n m a", (0, 0, 0.5), GAMMA)
    # the preconditions the two causes are stated over, asserted rather than
    # described (review of #389 round 3, follow-ups): if the cell or the index
    # bound moves, the instrument stops being aimed at the case above and this
    # test says so instead of quietly testing something else
    assert len(found) == 4, [c.label for c in found]
    expected = {5.2: (4, 2), 1.5: (208, 44)}
    for d_min in (5.2, 1.5):
        reflections = isotropy.reflections(found.lattice, d_min)
        assert (len(reflections), len(reflections.shells)) == expected[d_min], \
            f"d_min={d_min}: {len(reflections)} reflections in {len(reflections.shells)} shells"
        for candidate in found:
            assert isotropy.powder_equivalent(candidate, candidate, reflections), \
                f"{candidate.label} is not powder-equivalent to itself at d_min={d_min}"


def test_the_jacobian_deficit_is_the_undeterminable_direction():
    """A cubic ferromagnet has two free amplitudes a powder cannot see, and says so."""
    found = isotropy.candidates("F m -3 m", (0, 0, 0), GAMMA)
    reflections = isotropy.reflections(found.lattice, 2.0)
    general = max(found.candidates, key=lambda c: c.free_amplitudes)
    assert general.free_amplitudes == 3
    assert isotropy.determinable_amplitudes(general, reflections) == 1


# --------------------------------------------------------------------------
# The Gram stack: I_s(b) = bᵀ G_s b, contracted once per candidate
# --------------------------------------------------------------------------

#: Two with real structure factors (sites on inversion-related positions at
#: k = 0) and two with complex ones, since a conjugate dropped from G is
#: invisible on the first kind.
GRAM_CASES = [
    ("P n m a", (0, 0, 0), GAMMA, 1.5),
    ("P 4/m m m", (0, 0, 0), GAMMA, 2.0),
    ("P b c m", (0.308, 0.114, 0.07), (Fraction(1, 2), Fraction(0), Fraction(0)), 2.5),
    ("P 6_3 c m", (0.32080, 0, 0), GAMMA, 2.0),
]


def tensor_intensities(factors, amplitudes, shells):
    """The contraction the module evaluated before the Gram stack, kept as the oracle.

    Returns the per-shell intensity and its gradient in the amplitudes,
    straight from the ``(n_dom, n_free, n_hkl, 3)`` tensor.
    """
    total = np.tensordot(amplitudes, factors, axes=(0, 1))       # (n_dom, n_hkl, 3)
    per_hkl = np.sum(np.abs(total) ** 2, axis=(0, 2))
    grad = 2.0 * np.real(np.einsum("dhc,dqhc->hq", np.conj(total), factors))
    return (np.array([np.sum(per_hkl[list(m)]) for m in shells]),
            np.array([grad[list(m)].sum(axis=0) for m in shells]))


def unconjugated_gram(factors, shells):
    """Re Σ f·fᵀ with the conjugate left out: the slip the oracle has to catch."""
    n = factors.shape[1]
    out = np.empty((len(shells), n, n))
    for s, members in enumerate(shells):
        block = np.moveaxis(factors[:, :, list(members), :], 1, 0).reshape(n, -1)
        out[s] = np.real(block @ block.T)
    return out


def gram_error(grams, factors, shells, rng, draws=3):
    """Largest error of bᵀG_s b and 2·G_s·b against the tensor, relative to its largest."""
    worst = 0.0
    for _ in range(draws):
        b = rng.normal(size=factors.shape[1])
        intensity, gradient = tensor_intensities(factors, b, shells)
        worst = max(worst,
                    float(np.max(np.abs((grams @ b) @ b - intensity)) / np.max(intensity)),
                    float(np.max(np.abs(2.0 * (grams @ b) - gradient))
                          / np.max(np.abs(gradient))))
    return worst


@pytest.mark.parametrize("case", GRAM_CASES, ids=[c[0] for c in GRAM_CASES])
def test_the_gram_stack_is_the_tensor_contraction(case):
    """Intensities and gradients equal the tensor path's to 1e-12, and a wrong G fails.

    The Gram path is an exact reformulation, so the bar is round-off, not a
    tolerance.  The positive arm leaves the conjugate out of G, which is
    invisible exactly where the structure factors are real, so it is asserted
    on the cases whose factors are complex, and which cases those are is
    asserted too, so the arm cannot go quiet by the factors turning real.
    """
    group, site, k, d_min = case
    found = isotropy.candidates(group, site, k)
    reflections = isotropy.reflections(found.lattice, d_min)
    rng = np.random.default_rng(11)
    worst, wrong, complex_factors = 0.0, 0.0, False
    for candidate in found:
        f = isotropy.structure_factors(candidate, reflections)
        grams = isotropy.gram(f, reflections.shells)
        n = candidate.free_amplitudes
        assert grams.shape == (len(reflections.shells), n, n)
        assert np.array_equal(grams, np.transpose(grams, (0, 2, 1)))
        assert np.min(np.linalg.eigvalsh(grams)) >= -1e-12 * max(float(np.max(grams)), 1.0)
        worst = max(worst, gram_error(grams, f, reflections.shells, rng))
        # the public entry point goes through the same stack
        b = rng.normal(size=n)
        expected = tensor_intensities(f, b, reflections.shells)[0]
        got = isotropy.powder_intensities(candidate, b, reflections, factors=f)
        worst = max(worst, float(np.max(np.abs(got - expected)) / np.max(expected)))
        if np.max(np.abs(f.imag)) > 1e-6 * np.max(np.abs(f)):
            complex_factors = True
            wrong = max(wrong, gram_error(unconjugated_gram(f, reflections.shells),
                                          f, reflections.shells, rng))
    assert worst <= 1e-12, worst
    assert complex_factors == (group in ("P b c m", "P 6_3 c m"))
    if complex_factors:
        assert wrong > 1e-3, wrong


#: Classes measured on main at the default seed, draws and restarts, before
#: the fit moved onto the Gram stack.  Statistical verdicts (see
#: :func:`~rietx.crystallography.magnetic.isotropy.powder_equivalent`), so
#: this pins the protocol, not a property of the groups.
GRAM_PARTITIONS = [
    ("P 4/m m m", (0, 0, 0), GAMMA, 2.0, ((0,), (1, 2, 3))),
    ("P b c m", (0.308, 0.114, 0.07), (Fraction(1, 2), Fraction(0), Fraction(0)), 2.5,
     tuple((i,) for i in range(8))),
    ("P 6_3 c m", (0.32080, 0, 0), GAMMA, 2.0,
     ((0,), (1,), (2,), (3,), (4, 5), (6,), (7, 8), (9,))),
]


@pytest.mark.parametrize("case", GRAM_PARTITIONS, ids=[c[0] for c in GRAM_PARTITIONS])
def test_the_gram_path_leaves_the_modules_partitions_where_they_were(case):
    group, site, k, d_min, expected = case
    found = isotropy.candidates(group, site, k)
    reflections = isotropy.reflections(found.lattice, d_min)
    assert isotropy.equivalence_classes(found, reflections) == expected


def test_a_shell_the_family_cannot_light_settles_the_fit_without_one():
    """An absence the target fills is a proof; an absence it shares is dropped.

    Synthetic stack, two amplitudes, three shells, the third dark.  A target
    with intensity there is out of reach whatever b is, so the floor comes back
    and no start is drawn; a target that is dark there too is fitted on the
    two live shells and reached (b = (1, 1)/√2).
    """
    grams = np.zeros((3, 2, 2))
    grams[0] = np.eye(2)
    grams[1] = [[2.0, 1.0], [1.0, 2.0]]
    rng = np.random.default_rng(0)
    before = rng.bit_generator.state
    floor = isotropy._fit_residual(np.array([1.0, 3.0, 0.5]), grams, rng, rtol=1e-4)
    assert floor == pytest.approx(0.5 / 3.0)
    assert rng.bit_generator.state == before
    assert isotropy._fit_residual(np.array([1.0, 3.0, 0.0]), grams, rng) <= 1e-10


def test_identify_refuses_the_same_way_in_both_spglib_error_modes():
    """``spgrep/__init__.py`` (0.7.0) sets ``spglib.error.OLD_ERROR_HANDLING =
    False`` at import, and in that mode spglib **raises** where it used to
    return ``None``.  Before 2026-09-06 :func:`~.operators.identify` leaked a
    ``SpglibError`` in that mode where its docstring promises a ``ValueError``
    naming the unmatched entries — found on the merged magnetic-engine tree,
    where the operators and irreps test files first shared an xdist worker and
    three tests failed on gw4 alone.  The fix is in ``operators.py`` (catch the
    exception as well as the ``None``); this test asserts the refusal is the
    same authored ``ValueError`` in both modes, so the leak cannot come back
    unnoticed.  ``tests/conftest.py`` restores the flag per test.
    """
    spglib_error = pytest.importorskip("spglib.error")
    from rietx.crystallography.magnetic.operators import magnetic_group

    group = magnetic_group(283)          # the entry spglib cannot match at all
    with pytest.raises(ValueError, match="did not match"):
        identify(group)                  # the documented behaviour, default mode

    before = spglib_error.OLD_ERROR_HANDLING
    spglib_error.OLD_ERROR_HANDLING = False
    try:
        with pytest.raises(ValueError, match="did not match"):
            identify(group)              # the same refusal with the flag off
    finally:
        spglib_error.OLD_ERROR_HANDLING = before


# --------------------------------------------------------------------------
# G. The class count is a function of the family, not of its basis (#455)
# --------------------------------------------------------------------------

#: issue #455's reproduction case: two rank-1 directions of one two-copy
#: irrep, whose basis within the span is whatever the LAPACK returned.
P21C_SITE = (Fraction(11, 100), Fraction(13, 100), Fraction(17, 100))
P21C_K = (Fraction(0), Fraction(0), Fraction(1, 2))


def rotated_bases(found, rotation):
    """The issue's rotation: each family's basis turned within its own span.

    This is what a different LAPACK does to ``configurations`` (#455: span
    projectors agree to 1.5e-15 across Accelerate and OpenBLAS, the basis
    elements differ by up to 1.4), made reproducible on one machine.
    """
    from dataclasses import replace

    rng = np.random.default_rng(rotation)
    turned = []
    for c in found:
        q, _ = np.linalg.qr(rng.normal(size=(c.free_amplitudes,) * 2))
        turned.append(replace(c, configurations=np.tensordot(q, c.configurations,
                                                             axes=(1, 0))))
    return replace(found, candidates=tuple(turned))


def test_the_canonical_basis_is_fixed_by_the_span_alone():
    """Every rotation of the input basis gives one canonical basis, on the same span.

    Rotation 3 is the one that flipped the class count on one machine before
    the fix.  The positive arm is the raw bases: they differ by O(1), so an
    agreement below is not two copies of one array.
    """
    found = isotropy.candidates("P 1 21/c 1", P21C_SITE, P21C_K)
    base = [isotropy._canonical_basis(c).configurations for c in found]
    for rotation in range(6):
        turned = rotated_bases(found, rotation)
        for c, original, reference in zip(turned, found, base):
            assert float(np.max(np.abs(c.configurations - original.configurations))) > 0.1
            canonical = isotropy._canonical_basis(c).configurations
            assert np.allclose(canonical, reference, atol=1e-12, rtol=0.0), c.label
            flat = canonical.reshape(canonical.shape[0], -1)
            assert np.allclose(flat @ flat.T, np.eye(flat.shape[0]), atol=1e-12)
            raw = original.configurations.reshape(flat.shape[0], -1)
            # the same family: the raw basis lies in the canonical span
            assert np.allclose(raw @ flat.T @ flat, raw, atol=1e-12)


def test_a_rotated_basis_gives_the_same_classes():
    """Issue #455's machine-independent proof, reversed: a rotated basis no longer flips it.

    Before the fix ``((0, 1), (2,))`` became ``((0,), (1,), (2,))`` under
    rotation 3 at the default seed and ``restarts=4``, the cap of the day.
    This asserts at that cap, because the basis fix must remove the flip on
    its own: with :func:`isotropy._canonical_basis` replaced by the identity,
    rotation 0 splits the pair at ``restarts=4`` on macOS arm64 (early stop
    included), while with it every rotation 0-7 agrees at 1, 2 and 4
    restarts.  The equivalent draws need at most 3 restarts here at either
    cap, and at the default the two distinguishable pairs would pay 32
    restarts each (132-180 s on Linux CI).  Seed 7's flip, a restart-cap
    effect, is :func:`test_the_classes_do_not_move_with_the_rotation_or_the_seed`'s,
    whose grid holds it at the default cap.
    """
    found = isotropy.candidates("P 1 21/c 1", P21C_SITE, P21C_K)
    reflections = isotropy.reflections(found.lattice, 1.5)
    expected = ((0, 1), (2,))
    assert isotropy.equivalence_classes(found, reflections, restarts=4) == expected
    for rotation in (0, 3):
        assert isotropy.equivalence_classes(rotated_bases(found, rotation), reflections,
                                            restarts=4) == expected, rotation


@pytest.mark.slow
def test_the_classes_do_not_move_with_the_rotation_or_the_seed():
    """Six rotations × seeds 0-9 of the reproduction case, one partition (#455).

    Before the fix 2 of 18 runs split the pair (rotation 3 at the default
    seed, and seed 7 unrotated, of rotations 0-6 and seeds 0-9); after it,
    none of these 60 does.  2-8 min on one core by machine load, hence slow, with
    :func:`test_a_rotated_basis_gives_the_same_classes` its fast representative.
    """
    found = isotropy.candidates("P 1 21/c 1", P21C_SITE, P21C_K)
    reflections = isotropy.reflections(found.lattice, 1.5)
    seen = {(rotation, seed): isotropy.equivalence_classes(
                rotated_bases(found, rotation), reflections, seed=seed)
            for rotation in range(6) for seed in range(10)}
    assert set(seen.values()) == {((0, 1), (2,))}, seen


def test_the_fit_stops_at_the_first_restart_that_reproduces(monkeypatch):
    """With ``rtol`` one reproduction answers the question, so one fit is paid, not 32."""
    import scipy.optimize

    found = isotropy.candidates("P n m a", (0, 0, 0), GAMMA)
    reflections = isotropy.reflections(found.lattice, 1.8)
    candidate = isotropy._canonical_basis(found[0])
    factors = isotropy.structure_factors(candidate, reflections)
    rng = np.random.default_rng(0)
    amplitudes = isotropy._normalised_draw(candidate, reflections.lattice, rng)
    target = isotropy.powder_intensities(candidate, amplitudes, reflections,
                                         factors=factors)
    calls = []
    real = scipy.optimize.least_squares

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(scipy.optimize, "least_squares", counting)
    grams = isotropy.gram(factors, reflections.shells)
    stopped = isotropy._fit_residual(target, grams, np.random.default_rng(1),
                                     restarts=32, rtol=1e-4)
    assert stopped <= 1e-4 and len(calls) < 32
    calls.clear()
    isotropy._fit_residual(target, grams, np.random.default_rng(1), restarts=5)
    assert len(calls) == 5                 # no rtol: every restart runs


def test_an_already_stable_partition_is_unchanged_by_the_fix():
    """The control arm: a case whose classes never moved keeps them, member for member.

    ``P n m a`` at Γ, origin site, d_min = 1.5: four one-member classes on the
    code before #455's fix at seeds 20260906 and 0-2, and after it.  Every pair
    here is distinguishable, so it is also the case that pays the raised
    restart cap in full.
    """
    found = isotropy.candidates("P n m a", (0, 0, 0), GAMMA)
    reflections = isotropy.reflections(found.lattice, 1.5)
    for seed in (20260906, 0):
        assert isotropy.equivalence_classes(found, reflections, seed=seed) == \
            ((0,), (1,), (2,), (3,))


# --------------------------------------------------------------------------
# H. Which verdicts are proved and which are sampled (issue #565, part 1)
# --------------------------------------------------------------------------

def _pairs(relations, n):
    """The two directed verdicts of every unordered pair, keyed (i, j) with i < j."""
    verdicts = {(v.a, v.b): v for v in relations}
    return {(i, j): (verdicts[(i, j)], verdicts[(j, i)])
            for i in range(n) for j in range(i + 1, n)}


def _table_marks(found):
    """The P/S mark printed after each candidate's class number."""
    rows = str(found).splitlines()[4:4 + len(found)]
    return [row.split()[-1] for row in rows]


def test_every_cross_class_pair_of_the_pnma_candidates_is_proved():
    """The four LaMnO₃ candidates are told apart by certificates, and no amplitude is drawn.

    Every pair has a direction proved not contained, by the absence
    certificate: one candidate lights a shell the other cannot.  That claim
    is checked by a second route, :func:`isotropy.systematic_absences`, which
    reads the structure factors rather than the Gram stack.  Before the
    certificates each of the six pairs paid the full restart cap on a draw no
    fit could reproduce; now nothing is drawn at all, and the printed table
    marks all four classes P.
    """
    found = isotropy.analyse(isotropy.candidates("P n m a", (0, 0, 0), GAMMA), d_min=1.5)
    reflections = isotropy.reflections(found.lattice, 1.5)
    dark = [set(isotropy.systematic_absences(c, reflections).shells) for c in found]
    assert len(found.relations) == len(found) * (len(found) - 1)
    for (i, j), pair in _pairs(found.relations, len(found)).items():
        assert found.class_of(i) != found.class_of(j)
        assert any(v.status == "proved-not" for v in pair), pair
        for v in pair:
            if v.status == "proved-not":
                assert v.certificate == "absence"
                assert dark[v.b] - dark[v.a], (v, "b is dark nowhere a is lit")
    assert sum(v.draws for v in found.relations) == 0
    assert _table_marks(found) == ["P"] * 4
    assert "proved 6 (absence 6, subspace 0); sampled 0" in str(found)


def test_a_subspace_certificate_is_a_separation_a_fit_confirms():
    """Each subspace-proved direction is one no fit reaches; where every pair is equal, none fires.

    ``P 4/m m m`` at Γ: the moment along c against the in-plane ones.  For
    every direction the subspace certificate proves, a draw of ``a`` is
    fitted by ``b`` from 8 starts and must stay above ``rtol`` — an
    independent reading, by the route the certificate replaced.  The negative
    arm, where no certificate may fire, is
    :func:`test_a_cubic_collinear_site_gives_one_powder_equivalence_class`.
    """
    found = isotropy.candidates("P 4/m m m", (0, 0, 0), GAMMA)
    reflections = isotropy.reflections(found.lattice, 2.0)
    relations = isotropy.powder_relations(found, reflections)
    subspace = [v for v in relations if v.certificate == "subspace"]
    assert subspace
    canonical = [isotropy._canonical_basis(c) for c in found]
    grams = [isotropy.gram(isotropy.structure_factors(c, reflections), reflections.shells)
             for c in canonical]
    rng = np.random.default_rng(3)
    for v in subspace:
        amplitudes = isotropy._normalised_draw(canonical[v.a], reflections.lattice, rng)
        target = (grams[v.a] @ amplitudes) @ amplitudes
        assert isotropy._fit_residual(target, grams[v.b], rng, restarts=8) > 1e-4, v



def test_a_family_with_no_pattern_is_proved_inside_every_other():
    """The one certificate of containment: a family every shell is absent for.

    ``P n m a`` at (0, 0, ½), d_min 5.2, where S4(a)'s |F| is 6.1e-16: its
    zero pattern is reproduced by any family's zero model, and every other
    family lights a shell it cannot.  Before the certificates the first
    direction was skipped in silence and the second paid a fit.
    """
    found = isotropy.candidates("P n m a", (0, 0, 0.5), GAMMA)
    reflections = isotropy.reflections(found.lattice, 5.2)
    silent = [i for i, c in enumerate(found)
              if float(np.max(np.abs(isotropy.structure_factors(c, reflections)))) <= 1e-9]
    assert len(silent) == 1
    relations = isotropy.powder_relations(found, reflections)
    for v in relations:
        if v.a in silent:
            assert (v.status, v.certificate, v.draws) == ("proved-contained", "absence", 0)
        elif v.b in silent:
            assert (v.status, v.certificate, v.draws) == ("proved-not", "absence", 0)


#: Issue #565's known-answer case: the general site of the cubic P n -3 m:1
#: at (0, 0, ½), twelve families, three of each of four irreps.
KNOWN_ANSWER = ("P n -3 m:1", P21C_SITE, P21C_K)


def test_s1_against_s2_of_the_cubic_known_answer_is_sampled_not_proved():
    """S1 and S2 light the same shells and span the same intensities, so their verdicts are draws.

    Nothing in this module's certificates separates them — their spans
    coincide to 4e-15 both ways — so every S1/S2 direction of the full
    twelve-family set is sampled or unresolved, never proved, whatever the
    draws say.  The positive arm is in the same set: S3 and S4 are dark at
    shells S1 and S2 light, so all 36 directions from an S1 or S2 family to
    an S3 or S4 one are proved.  One draw and one restart, since what is
    asserted is which verdicts the draws were *asked* for, not what they
    answered (19 s at restarts 4, most of it fits).
    """
    found = isotropy.candidates(*KNOWN_ANSWER)
    relations = isotropy.powder_relations(found, isotropy.reflections(found.lattice, 1.5),
                                          draws=1, restarts=1)
    irrep = [c.irrep_label for c in found]
    between = [v for v in relations if {irrep[v.a], irrep[v.b]} == {"S1", "S2"}]
    assert len(between) == 18
    assert all(v.certificate not in ("absence", "subspace") for v in between)
    assert any(v.status.startswith("sampled") and v.draws > 0 for v in between)
    across = [v for v in relations
              if irrep[v.a] in ("S1", "S2") and irrep[v.b] in ("S3", "S4")]
    assert len(across) == 36
    assert all(v.status == "proved-not" for v in across)


def test_every_sampled_edge_prints_the_draws_it_actually_made(monkeypatch):
    """The n of every sampled pair is the number of draws that pair consumed, counted from outside.

    :func:`isotropy._normalised_draw` is wrapped to log which family each
    draw came from, and the log must be, draw for draw, the sequence the
    relations claim: each tested pair in order, a → b then b → a, ``draws``
    of each.  The printed n must be those numbers.  The set is five families
    of the cubic known-answer case (two S1, two S2, one S3) at restarts 4,
    which holds sampled-contained directions (3 draws, within an irrep),
    sampled-not ones stopped early (2 to 4 of 12 at this seed, across
    irreps), unresolved and proved ones (none), so a count that ignored the
    early stop or charged a proved pair would show, and so would a draw
    spent on a pair already proved distinct.
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#1", "S1(rank 1)#2", "S2(rank 1)#1", "S2(rank 1)#2", "S3(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in labels))
    assert [c.label for c in subset] == labels
    log = []
    real = isotropy._normalised_draw

    def counting(candidate, lattice, rng):
        log.append(candidate.label)
        return real(candidate, lattice, rng)

    monkeypatch.setattr(isotropy, "_normalised_draw", counting)
    result = isotropy.analyse(subset, d_min=1.5, restarts=4)
    # the S1 and S2 classes rest on draws; S3 is proved apart from all four
    assert _table_marks(result) == ["S", "S", "S", "S", "P"]
    statuses = {v.status for v in result.relations}
    assert {"sampled-contained", "sampled-not", "unresolved", "proved-not"} <= statuses
    assert all((v.reason is not None) == (v.status == "unresolved") for v in result.relations)
    assert any(v.status == "sampled-not" and v.draws < isotropy.CROSS_IRREP_DRAWS
               for v in result.relations)
    expected = []
    for (i, j), pair in _pairs(result.relations, len(subset)).items():
        if any(v.status == "proved-not" for v in pair):
            assert all(v.draws == 0 for v in pair), pair   # settled: nothing drawn
        for v in pair:
            expected += [labels[v.a]] * v.draws
            assert (v.draws > 0) == v.status.startswith("sampled")
    assert log == expected

    printed = [line for line in str(result).splitlines()
               if line.startswith("  ") and " n = " in line]
    sampled = [pair for pair in _pairs(result.relations, len(subset)).values()
               if not any(v.status == "proved-not" for v in pair)
               and any(v.status.startswith("sampled") for v in pair)]
    assert len(printed) == len(sampled)
    for line, pair in zip(printed, sampled):
        assert line.startswith(f"  {labels[pair[0].a]} ")
        counts = line.split(" n = ")[1]
        for v, shown in zip(pair, counts.split(", ")):
            assert shown.split()[0] == ("-" if v.status == "unresolved" else str(v.draws))
            assert ("not reproduced" in shown) == (v.undecided_draws > 0)


def test_the_default_draws_are_twelve_across_irreps_and_three_within(monkeypatch):
    """Issue #565's decision 3: 12 draws per direction between irreps, 3 inside one; a number overrides both.

    Every fit is replaced by a perfect reproduction, so each sampled
    direction runs its whole budget and ``draws`` *is* the budget.  The set
    is the draw-count test's five cubic families: S1 → S2 pairs are across
    irreps, S1 → S1 and S2 → S2 inside one, and S3 is proved apart, so it
    is never drawn.
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#1", "S1(rank 1)#2", "S2(rank 1)#1", "S2(rank 1)#2", "S3(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in labels))
    reflections = isotropy.reflections(found.lattice, 1.5)
    monkeypatch.setattr(isotropy, "_fit_residual", lambda *args, **kwargs: 0.0)
    irrep = [c.irrep_label for c in subset]
    for draws, across, within in ((None, 12, 3), (2, 2, 2)):
        relations = isotropy.powder_relations(subset, reflections, draws=draws)
        sampled = [v for v in relations if v.status.startswith("sampled")]
        assert {irrep[v.a] == irrep[v.b] for v in sampled} == {True, False}
        for v in sampled:
            assert v.status == "sampled-contained"
            assert v.draws == (within if irrep[v.a] == irrep[v.b] else across), v
        assert all(v.draws == 0 for v in relations if "S3" in (irrep[v.a], irrep[v.b]))


@pytest.mark.slow
def test_the_cubic_known_answer_has_four_classes_at_the_default_draws():
    """``P n -3 m:1`` at (0, 0, ½), general site: one class per irrep, as issue #565 proves.

    At 3 draws everywhere the same set gave two classes, S1 ∪ S2 and
    S3 ∪ S4, each joined by draws that happened to be reproduced; at the
    default 12 across irreps some draw of every such pair is not.  A sampled
    verdict at one seed, so this pins the protocol; the S1 ⊄ S2 proofs are a
    later certificate's.  130-180 s on one core by machine load, hence slow.
    """
    found = isotropy.analyse(isotropy.candidates(*KNOWN_ANSWER), d_min=1.5)
    by_irrep = {}
    for i, candidate in enumerate(found):
        by_irrep.setdefault(candidate.irrep_label, []).append(i)
    assert found.classes == tuple(tuple(members) for members in by_irrep.values())
    assert len(found.classes) == 4


def test_the_certificates_run_on_a_pair_union_find_has_already_joined(monkeypatch):
    """A join is transitive and a proof is not, so a joined pair still gets its certificates.

    The draw-count test's five cubic families, every fit replaced by a
    perfect reproduction, so S1 ∪ S2 is one class.  The positive arm: the
    certificates of S1(rank 1)#1 ↔ S3 are withheld, so that pair is drawn
    and joined, and S3 joins the class through it — as a later certificate
    that is not an equivalence (a stored Farkas witness, issue #565 part 2)
    can leave a proved separation inside a class.  Every other S3 pair is
    then reached already joined, and must still carry its ``proved-not``;
    the S1/S2 pairs reached joined carry ``reason="joined"`` and no draws.
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#1", "S1(rank 1)#2", "S2(rank 1)#1", "S2(rank 1)#2", "S3(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in labels))
    reflections = isotropy.reflections(found.lattice, 1.5)
    monkeypatch.setattr(isotropy, "_fit_residual", lambda *args, **kwargs: 0.0)
    real = isotropy._certify

    def withheld(a, b, *args):
        return None if {a, b} == {0, 4} else real(a, b, *args)

    monkeypatch.setattr(isotropy, "_certify", withheld)
    classes, relations = isotropy._classify(subset, reflections, draws=3,
                                            seed=20260906, rtol=1e-4, restarts=1)
    assert classes == ((0, 1, 2, 3, 4),)
    pairs = _pairs(relations, len(subset))
    for (i, j), pair in pairs.items():
        if 4 in (i, j) and 0 not in (i, j):
            assert any(v.status == "proved-not" and v.certificate is not None
                       for v in pair), pair
            assert all(v.draws == 0 for v in pair), pair
    joined = [v for v in relations if v.reason == "joined"]
    assert joined
    assert all(v.draws == 0 and v.status == "unresolved" for v in joined)
    assert all(4 not in (v.a, v.b) for v in joined)


#: A site 10⁻⁴ off the origin of ``P m -3 m``, where 21 of the 28 families
#: have a whole Gram stack below 1 (1e-11 to 3e-3) and are not silent.
NEAR_SPECIAL = ("P m -3 m", (1e-4, 0.0, 0.0), GAMMA)


@pytest.fixture(scope="module")
def near_special_stack():
    """The ``NEAR_SPECIAL`` candidates, structure factors and Gram stacks, built once for the tests below.

    Both tests read these and neither mutates them; building them is the
    cost the two tests shared (about 10 s each when each built its own).
    """
    found = isotropy.candidates(*NEAR_SPECIAL)
    reflections = isotropy.reflections(found.lattice, 1.5)
    canonical = [isotropy._canonical_basis(c) for c in found]
    factors = [isotropy.structure_factors(c, reflections) for c in canonical]
    grams = [isotropy.gram(f, reflections.shells) for f in factors]
    return found, reflections, factors, grams


@pytest.mark.xdist_group("magnetic-near-special")
def test_the_certificate_labels_do_not_move_with_an_overall_moment_scale(near_special_stack):
    """Only ratios of intensities are compared, so scaling every moment by one factor changes no certificate.

    Every structure factor is scaled by 10⁻², 1 and 10² (every Gram stack
    by 10⁻⁴, 1 and 10⁴), which keeps the same families silent, and the
    certificate on every ordered pair must be the same at each scale.  An
    absolute floor on the dark test moves 24 of the 756 labels at scale 1
    here alone, between ``absence`` and ``subspace``.
    """
    found, reflections, factors, grams = near_special_stack
    assert sum(float(np.max(np.abs(g))) < 1.0 and not isotropy._silent(f)
               for f, g in zip(factors, grams)) >= 20
    n = len(found)
    labels = {}
    for scale in (1e-2, 1.0, 1e2):
        scaled = [f * scale for f in factors]
        silent = [isotropy._silent(f) for f in scaled]
        g = [isotropy.gram(f, reflections.shells) for f in scaled]
        dark = [isotropy._certificate_dark(x, quiet) for x, quiet in zip(g, silent)]
        spans = [isotropy._intensity_span(x) for x in g]
        verdicts = [isotropy._certify(a, b, dark, spans, silent)
                    for a in range(n) for b in range(n) if a != b]
        labels[scale] = (tuple(silent),
                         tuple(v and (v.status, v.certificate) for v in verdicts))
    assert labels[1e-2] == labels[1.0] == labels[1e2]
    # a comparison of labels that were all None would pass; both certificates must occur
    certificates = {x[1] for x in labels[1.0][1] if x}
    assert {"absence", "subspace"} <= certificates


@pytest.mark.xdist_group("magnetic-near-special")
def test_a_stack_with_no_gap_at_the_rank_cut_gives_no_subspace_certificate(near_special_stack):
    """A singular value within three decades of the rank cut makes the span a choice of tolerance, so nothing is proved on it.

    Synthetic first: two shells whose Gram blocks differ by 1e-8 in one
    direction have a relative singular value of about 1e-8, inside
    (1e-12, 1e-6), and :func:`isotropy._intensity_span` returns None.
    Then the near-special ``P m -3 m`` set, where the gap closes on real
    families (their stack differs from a special position's by δ² ≈ 1e-8):
    no pair with such a family carries a subspace certificate.  Without the
    guard, the draws at ``rtol`` 1e-4 and those certificates disagree there,
    and the set splits into 16 classes where the draws alone give 11.
    """
    grams = np.array([np.eye(2), np.diag([1.0, 1.0 + 1e-8])])
    assert isotropy._intensity_span(grams) is None
    assert isotropy._intensity_span(np.array([np.eye(2), np.diag([1.0, 2.0])])).shape[1] == 2

    found, reflections, factors, grams = near_special_stack
    silent = [isotropy._silent(f) for f in factors]
    dark = [isotropy._certificate_dark(g, quiet) for g, quiet in zip(grams, silent)]
    spans = [isotropy._intensity_span(g) for g in grams]
    gapless = {i for i, span in enumerate(spans) if span is None}
    assert gapless
    gapped_subspace = 0
    for a in range(len(found)):
        for b in range(len(found)):
            if a == b:
                continue
            v = isotropy._certify(a, b, dark, spans, silent)
            if {a, b} & gapless:
                assert v is None or v.certificate != "subspace", (a, b, v)
            elif v is not None and v.certificate == "subspace":
                gapped_subspace += 1
    # the guard is not a blanket refusal: pairs of gapped families keep the certificate
    assert gapped_subspace
